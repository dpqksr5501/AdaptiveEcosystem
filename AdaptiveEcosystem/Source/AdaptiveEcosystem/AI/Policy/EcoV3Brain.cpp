#include "EcoV3Brain.h"

#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/Base64.h"
#include "Misc/FileHelper.h"
#include "Misc/OutputDevice.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

#include "EcoObservationV3.h"
#include "EcoSha256.h"
#include "EcoWorldV3.h"
#include "PolicyBrainV3Default.h"

#include <initializer_list>
#include <limits>

DEFINE_LOG_CATEGORY(LogEcoV3Brain);

// 10-29 기본 두뇌 (PolicyBrainV3Default.h — export_weights_v3.py --default-brain): 이 빌드가 관측을 만들 수 있는 계약이어야 한다.
// 실행 때 Default() 가 넣은 바이트를 파일 두뇌와 같은 Parse 검사로 다시 본다 — 여기서는 계약이 다른 두뇌를 넣은 빌드를 막는다
static_assert(EcoPolicyV3Default::kObsDim > 0 && EcoPolicyV3Default::kObsDim <= EcoPolicyV3::kMaxObsDim, "기본 두뇌 관측 칸 수가 망 입력 상한을 넘는다");
static_assert(EcoPolicyV3Default::kContractHash == EcoPolicyV3::kContractHashObs18Mask2 || EcoPolicyV3Default::kContractHash == EcoPolicyV3::kContractHashObs21Mask2
				  || EcoPolicyV3Default::kContractHash == EcoPolicyV3::kContractHashObs24Mask4
				  || EcoPolicyV3Default::kContractHash == EcoPolicyV3::kContractHashObs24Mask5,
			  "기본 두뇌의 계약 해시를 이 빌드가 받지 않는다 (EcoV3Brain 받는 계약 넷 — C++ 관측 코드를 함께 바꿔야 한다)");
static_assert(EcoPolicyV3Default::kFileBytes > 0 && sizeof(EcoPolicyV3Default::kFile) == static_cast<size_t>(EcoPolicyV3Default::kFileBytes),
			  "기본 두뇌 바이트 수가 배열 크기와 다르다");

static_assert(PLATFORM_LITTLE_ENDIAN, "두뇌 파일 가중치는 float32 리틀 엔디언 바이트다 — 큰 엔디언 플랫폼은 바이트를 뒤집어 읽어야 한다");
// 관측 21 계약은 내장 관측 18·판 2 계약(R1b) 뒤에 세 칸을 붙인 것이다 — 내장 계약이 바뀌면 이 표를 함께 고친다
static_assert(EcoPolicyV3::kContractHash == EcoPolicyV3::kContractHashObs18Mask2 && EcoPolicyV3::kObsDim == EcoObservationV3::kObsDim
				  && EcoPolicyV3::kMaskVersion == 2,
			  "관측 21 장애물 계약은 내장 관측 18·마스크 판 2 계약 위에 있다");
static_assert(EcoObservationV3::kObsDimObstacle <= EcoPolicyV3::kMaxObsDim, "관측 21 이 망 입력 상한을 넘는다");
// 10-24 두 길 두뇌 (이식 계획서 5-1): 관측 24 = 관측 21 + 길 세 칸
static_assert(EcoObservationV3::kObsDimRoute <= EcoPolicyV3::kMaxObsDim, "관측 24 가 망 입력 상한을 넘는다");
static_assert(EcoObservationV3::kObsDimRoute == EcoPolicyV3::kObsDim + EcoObservationV3::kNumObstacleObs + EcoObservationV3::kNumRouteObs,
			  "관측 24 계약 = 관측 18 · 장애물 세 칸 · 길 세 칸");

namespace EcoV3BrainImpl
{
	using namespace EcoV3Brain;
	namespace P3 = EcoPolicyV3;
	namespace O3 = EcoObservationV3;

	const TCHAR* const kBehaviorKo[P3::kNumBehaviors] = {TEXT("먹기"), TEXT("도망"), TEXT("숨기"), TEXT("얼기"), TEXT("잠")};

	// 관측 24 계약의 18 칸 뒤 여섯 이름 (장애물 세 칸 · 길 세 칸 — 파이썬 obs_names 차례, ContractObsName 이 i ≥ 18 을 여기서 읽는다)
	const char* const kRouteContractExtraNames[O3::kNumObstacleObs + O3::kNumRouteObs] = {
		O3::kObstacleObsNames[0], O3::kObstacleObsNames[1], O3::kObstacleObsNames[2],
		O3::kRouteObsNames[0],	  O3::kRouteObsNames[1],	O3::kRouteObsNames[2]};

	// 받는 계약 (EcoV3Brain.h 머리 주석 '받는 계약'). 0 = 내장 계약, 1 = R5 장애물 관측 21, 2·3 = 10-24 두 길 두뇌 관측 24 판 4·5
	const FContract kContracts[kNumContracts] = {
		{P3::kContractHash, P3::kObsDim, P3::kMaskVersion, 0, nullptr, TEXT("관측 18 · 마스크 판 2 (내장 R1b 와 같은 계약)")},
		{P3::kContractHashObs21Mask2, O3::kObsDimObstacle, 2, O3::kNumObstacleObs, O3::kObstacleObsNames,
		 TEXT("관측 21 · 마스크 판 2 (R5 장애물 관측 — 18 칸 + escape_room·obstacle_near·threat_hidden)")},
		{P3::kContractHashObs24Mask4, O3::kObsDimRoute, P3::kMaskVersionRoute, O3::kNumObstacleObs + O3::kNumRouteObs, kRouteContractExtraNames,
		 TEXT("관측 24 · 마스크 판 4 (두 길 두뇌 — 21 칸 + in_panic·shelter_reach·shelter_edge)")},
		{P3::kContractHashObs24Mask5, O3::kObsDimRoute, P3::kMaskVersionRouteGate, O3::kNumObstacleObs + O3::kNumRouteObs, kRouteContractExtraNames,
		 TEXT("관측 24 · 마스크 판 5 (두 길 두뇌 + 반사 밖 두뇌 FLEE 막음 — R7)")},
	};

#if !UE_BUILD_SHIPPING
	TAutoConsoleVariable<FString> CVarStartup(
		TEXT("eco.V3Brain.Startup"), TEXT(""),
		TEXT("통합 v3 Play 를 시작할 때 걸 사슴 두뇌 (EcoV3Brain.h '기본 두뇌'). 빈 값 = 기본 두뇌 R7e (이 프로세스 첫 Play·적응 고리 Play — 그 밖은 지금 두뇌 그대로). ")
			TEXT("'default'·'기본'·'R7e' = 기본 두뇌, 'builtin'·'내장'·'R1b'·'R1b-F' = 내장 R1b-F (10-28 까지의 기본), 그 밖 = 두뇌 파일 이름·경로. ")
			TEXT("거부되면 기록·화면에 알리고 빈 값처럼 고른다. 명령줄 -EcoV3Brain= 은 시작값."),
		ECVF_Default);
	TAutoConsoleVariable<float> CVarSwapAt(
		TEXT("eco.V3Brain.SwapAtSeconds"), -1.0f,
		TEXT("예정 두뇌 바꾸기 시각 (시뮬레이션 초 = 기록 줄의 초, 측정·시연용). -1 = 끔. 그 시각이 되는 결정 스텝 경계에서 eco.V3Brain.SwapFile 로 바꾼다. ")
			TEXT("명령줄 -EcoV3BrainSwapAt= 은 시작값."),
		ECVF_Default);
	TAutoConsoleVariable<FString> CVarSwapFile(
		TEXT("eco.V3Brain.SwapFile"), TEXT(""),
		TEXT("예정 두뇌 바꾸기의 두뇌 파일 (eco.V3Brain.SwapAtSeconds). 명령줄 -EcoV3BrainSwapTo= 은 시작값."), ECVF_Default);
	TAutoConsoleVariable<FString> CVarWatch(
		TEXT("eco.V3Brain.WatchFolder"), TEXT(""),
		TEXT("두뇌 폴더 감시 (기본 빈 값 = 끔). 통합 v3 Play 중 2 초마다 이 폴더(상대 경로는 프로젝트 기준)의 가장 새 *.json 이 바뀌면 불러와 다음 결정 스텝 ")
			TEXT("경계에서 바꾼다. eco.IntegratedV3.AutoAdapt 1 이고 비었으면 Saved/EcoAdapt/brains. 명령줄 -EcoV3BrainWatch= 은 시작값."),
		ECVF_Default);
	// 실시간 두뇌 교체 화면 (10-21, LIVE_ADAPT_SPEC.md 5.4 — 통합 서브시스템이 그린다)
	TAutoConsoleVariable<int32> CVarNotice(
		TEXT("eco.V3Brain.Notice"), 1,
		TEXT("두뇌 바꾸기·되돌리기·파일 거부·환경 바뀜·스냅숏 화면 알림과 적응 고리 상태 줄 (1 = 켬, 기본 — eco.V3Debug 와 따로). 그리는 화면이 있는 서버·단독만. ")
			TEXT("0 = 화면에 안 띄움 (기록 '[EcoV3I] 알림 |' 은 늘 남긴다)."),
		ECVF_Default);
	TAutoConsoleVariable<int32> CVarNoticeShot(
		TEXT("eco.V3Brain.NoticeShot"), 0,
		TEXT("두뇌 바꾸기·되돌리기 알림 1.5 초 뒤 화면을 찍는다 (0 = 끔, 기본 — 시연 증거, Saved/EcoAdapt/shots/). 그릴 수 없는 실행은 건너뛴다."),
		ECVF_Default);
	TAutoConsoleVariable<FString> CVarStatusFile(
		TEXT("eco.V3Brain.StatusFile"), TEXT(""),
		TEXT("적응 고리 상태 파일 (파이썬 live.py 가 쓰는 eco_v3_live_status JSON, 상대 경로는 프로젝트 기준). 빈 값 = 끔, eco.IntegratedV3.AutoAdapt 1 이면 ")
			TEXT("Saved/EcoAdapt/status.json. 2 초마다 읽어 화면 상태 줄 '적응 고리 | …' 에 쓴다."),
		ECVF_Default);
#endif

	FEcoV3BrainLoad Fail(EReject Reason, const FString& Message)
	{
		FEcoV3BrainLoad L;
		L.Reason = Reason;
		L.Message = Message;
		return L;
	}

	bool ReadStringArray(const FJsonObject& O, const TCHAR* Field, TArray<FString>& Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if (!O.TryGetArrayField(Field, Arr))
		{
			return false;
		}
		Out.Reset();
		for (const TSharedPtr<FJsonValue>& V : *Arr)
		{
			FString S;
			if (!V.IsValid() || !V->TryGetString(S))
			{
				return false;
			}
			Out.Add(S);
		}
		return true;
	}

	/** 숫자 배열 → float (double 로 읽어 float 로 — 파이썬이 float32 값을 그대로 적었으면 같은 비트). 수가 아니거나 길이가 다르면 거짓. */
	bool ReadFloats(const FJsonObject& O, const TCHAR* Field, int32 Want, float* Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if (!O.TryGetArrayField(Field, Arr) || Arr->Num() != Want)
		{
			return false;
		}
		for (int32 i = 0; i < Want; ++i)
		{
			double D = 0.0;
			if (!(*Arr)[i].IsValid() || !(*Arr)[i]->TryGetNumber(D))
			{
				return false;
			}
			Out[i] = static_cast<float>(D);
		}
		return true;
	}

	bool ReadInts(const FJsonObject& O, const TCHAR* Field, int32 Want, int32* Out)
	{
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if (!O.TryGetArrayField(Field, Arr) || Arr->Num() != Want)
		{
			return false;
		}
		for (int32 i = 0; i < Want; ++i)
		{
			double D = 0.0;
			if (!(*Arr)[i].IsValid() || !(*Arr)[i]->TryGetNumber(D) || D != FMath::FloorToDouble(D))
			{
				return false;
			}
			Out[i] = static_cast<int32>(D);
		}
		return true;
	}

	FString StringField(const FJsonObject* O, const TCHAR* Field)
	{
		FString S;
		if (O)
		{
			O->TryGetStringField(Field, S);
		}
		return S;
	}

	const FJsonObject* ObjectField(const FJsonObject& O, const TCHAR* Field)
	{
		const TSharedPtr<FJsonObject>* P = nullptr;
		return O.TryGetObjectField(Field, P) && P && P->IsValid() ? P->Get() : nullptr;
	}

	/** 한 층 (out × in 가중치 + out 편향) 읽기. */
	EReject ReadLayer(const FJsonObject& L, int32 WantOut, int32 WantIn, TArray<float>& OutW, TArray<float>& OutB, FString& Msg)
	{
		int32 OutDim = 0;
		int32 InDim = 0;
		FString Wb64;
		FString Bb64;
		if (!L.TryGetNumberField(TEXT("out"), OutDim) || !L.TryGetNumberField(TEXT("in"), InDim) || !L.TryGetStringField(TEXT("w_f32le_b64"), Wb64)
			|| !L.TryGetStringField(TEXT("b_f32le_b64"), Bb64))
		{
			Msg = TEXT("층 칸(out·in·w_f32le_b64·b_f32le_b64)이 없다");
			return EReject::Shape;
		}
		if (OutDim != WantOut || InDim != WantIn)
		{
			Msg = FString::Printf(TEXT("층 모양 %d×%d 이 계약 %d×%d 과 다르다"), OutDim, InDim, WantOut, WantIn);
			return EReject::Shape;
		}
		TArray<uint8> Wbytes;
		TArray<uint8> Bbytes;
		if (!FBase64::Decode(Wb64, Wbytes) || !FBase64::Decode(Bb64, Bbytes))
		{
			Msg = TEXT("base64 를 풀지 못했다");
			return EReject::Decode;
		}
		const int32 Nw = WantOut * WantIn;
		if (Wbytes.Num() != Nw * 4 || Bbytes.Num() != WantOut * 4)
		{
			Msg = FString::Printf(TEXT("풀린 바이트 %d·%d 가 모양의 %d·%d 와 다르다"), Wbytes.Num(), Bbytes.Num(), Nw * 4, WantOut * 4);
			return EReject::Decode;
		}
		OutW.SetNumUninitialized(Nw);
		OutB.SetNumUninitialized(WantOut);
		FMemory::Memcpy(OutW.GetData(), Wbytes.GetData(), Wbytes.Num());
		FMemory::Memcpy(OutB.GetData(), Bbytes.GetData(), Bbytes.Num());
		return EReject::None;
	}
}

// -----------------------------------------------------------------------------
// 도움 함수
// -----------------------------------------------------------------------------

const TCHAR* EcoV3Brain::RejectName(EReject Reason)
{
	switch (Reason)
	{
	case EReject::None: return TEXT("통과");
	case EReject::File: return TEXT("파일");
	case EReject::Json: return TEXT("JSON");
	case EReject::Format: return TEXT("형식");
	case EReject::Contract: return TEXT("계약 해시");
	case EReject::Dims: return TEXT("차원");
	case EReject::Names: return TEXT("이름");
	case EReject::Mask: return TEXT("마스크 판");
	case EReject::Thresholds: return TEXT("마스크 문턱");
	case EReject::Allowed: return TEXT("허용 칸");
	case EReject::Shape: return TEXT("층 모양");
	case EReject::Decode: return TEXT("가중치 풀기");
	case EReject::NonFinite: return TEXT("NaN·Inf");
	case EReject::Digest: return TEXT("sha256");
	case EReject::Golden: return TEXT("골든 자체 확인");
	case EReject::Play: return TEXT("다른 Play");
	}
	return TEXT("?");
}

const EcoV3Brain::FContract& EcoV3Brain::Contract(int32 Index)
{
	return EcoV3BrainImpl::kContracts[FMath::Clamp(Index, 0, kNumContracts - 1)];
}

const EcoV3Brain::FContract* EcoV3Brain::FindContract(uint64 Hash)
{
	for (const FContract& C : EcoV3BrainImpl::kContracts)
	{
		if (C.Hash == Hash)
		{
			return &C;
		}
	}
	return nullptr;
}

const char* EcoV3Brain::ContractObsName(const FContract& C, int32 i)
{
	return i < EcoPolicyV3::kObsDim ? EcoPolicyV3::kObsNames[i] : C.ExtraNames[i - EcoPolicyV3::kObsDim];
}

FString EcoV3Brain::RouteContractDiff(const FJsonObject& Root, int32 MaskVersion)
{
	namespace P3 = EcoPolicyV3;
	namespace O3 = EcoObservationV3;
	namespace W3 = EcoWorldV3;
	using EcoV3BrainImpl::ObjectField;
	// 숫자 칸 하나 (없거나 수가 아니면 NaN — 비교가 거짓이 된다)
	auto Num = [](const FJsonObject* O, const TCHAR* Field)
	{
		double V = std::numeric_limits<double>::quiet_NaN();
		if (O)
		{
			O->TryGetNumberField(Field, V);
		}
		return V;
	};
	// 글자 배열이 Want 와 같은 차례·같은 길이인가
	auto StringList = [](const FJsonObject* O, const TCHAR* Field, std::initializer_list<const TCHAR*> Want)
	{
		const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
		if (!O || !O->TryGetArrayField(Field, Arr) || Arr->Num() != static_cast<int32>(Want.size()))
		{
			return false;
		}
		int32 j = 0;
		for (const TCHAR* W : Want)
		{
			FString S;
			if (!(*Arr)[j].IsValid() || !(*Arr)[j]->TryGetString(S) || S != W)
			{
				return false;
			}
			++j;
		}
		return true;
	};
	const FJsonObject* Ct = ObjectField(Root, TEXT("contract"));
	const FJsonObject* Fr = Ct ? ObjectField(*Ct, TEXT("flight_route")) : nullptr;
	if (!Fr)
	{
		return TEXT("contract.flight_route 없음");
	}
	{
		const FJsonObject* Sl = ObjectField(*Fr, TEXT("slots"));
		const TArray<TSharedPtr<FJsonValue>>* Res = nullptr;
		double R0 = std::numeric_limits<double>::quiet_NaN();
		const bool bRes = Sl && Sl->TryGetArrayField(TEXT("reserved_masked"), Res) && Res->Num() == 1 && (*Res)[0].IsValid() && (*Res)[0]->TryGetNumber(R0);
		if (!(Num(Sl, TEXT("run")) == W3::kRouteSlotRun && Num(Sl, TEXT("shelter")) == W3::kRouteSlotShelter && bRes && R0 == W3::kRouteSlotReserved))
		{
			return TEXT("flight_route.slots");
		}
	}
	{
		const TArray<TSharedPtr<FJsonValue>>* Ob = nullptr;
		bool bOk = Fr->TryGetArrayField(TEXT("obs"), Ob) && Ob->Num() == O3::kNumRouteObs;
		for (int32 j = 0; bOk && j < O3::kNumRouteObs; ++j)
		{
			FString S;
			bOk = (*Ob)[j].IsValid() && (*Ob)[j]->TryGetString(S) && S == UTF8_TO_TCHAR(O3::kRouteObsNames[j]);
		}
		if (!bOk)
		{
			return TEXT("flight_route.obs");
		}
	}
	{
		// 결정 조건 on = 시작·무효·잠금 뒤 가능 바뀜 (world.py `_route_step` — EcoWorldV3 Detail::RouteStep 의 onset·invalid·refeas, 길 없음 cur < 0 은 C++ 교체 전용)
		const FJsonObject* De = ObjectField(*Fr, TEXT("decide"));
		if (!(Num(De, TEXT("lock_steps")) == W3::kRouteLockSteps
			  && StringList(De, TEXT("on"), {TEXT("onset"), TEXT("invalid"), TEXT("lock_and_feasible_changed")})
			  && StringList(De, TEXT("feasible"), {TEXT("shelter")}) && StringList(De, TEXT("refeas_from"), {TEXT("run")})))
		{
			return TEXT("flight_route.decide");
		}
	}
	{
		const FJsonObject* Sh = ObjectField(*Fr, TEXT("shelter"));
		if (!(Num(Sh, TEXT("max_edge_u")) == W3::kRouteShelterMaxEdgeU && Num(Sh, TEXT("cos_min")) == W3::kRouteShelterCosMin
			  && Num(Sh, TEXT("enter_margin_u")) == W3::kRouteShelterEnterU && Num(Sh, TEXT("exit_margin_u")) == W3::kRouteShelterExitU
			  && Num(Sh, TEXT("reach_norm_u")) == W3::kRouteShelterReachU && Num(Sh, TEXT("edge_norm_u")) == W3::kRouteShelterEdgeNormU))
		{
			return TEXT("flight_route.shelter");
		}
	}
	{
		FString Blocked;
		if (!Fr->TryGetStringField(TEXT("freeze_sleep_must_be_blocked"), Blocked) || Blocked != TEXT("effective_allowed"))
		{
			return TEXT("flight_route.freeze_sleep_must_be_blocked");
		}
	}
	// 판 5 는 contract.brain_flee_outside_reflex = false, 판 4 에는 그 칸이 없다 (null 은 없음으로 본다 — 평가기와 같다)
	const TSharedPtr<FJsonValue> Gate = Ct->TryGetField(TEXT("brain_flee_outside_reflex"));
	const bool bGateSet = Gate.IsValid() && !Gate->IsNull();
	bool bGateValue = true;
	if (bGateSet && !Gate->TryGetBool(bGateValue))
	{
		return TEXT("brain_flee_outside_reflex (참·거짓이 아니다)");
	}
	if (MaskVersion == P3::kMaskVersionRouteGate && (!bGateSet || bGateValue))
	{
		return TEXT("brain_flee_outside_reflex (판 5 는 false)");
	}
	if (MaskVersion == P3::kMaskVersionRoute && bGateSet)
	{
		return TEXT("brain_flee_outside_reflex (판 4 에는 없다)");
	}
	return FString();
}

FString EcoV3Brain::WeightsSha256(const EcoPolicyV3::FPolicyNetV3& Net)
{
	namespace P3 = EcoPolicyV3;
	EcoSha256::FState S;
	EcoSha256::Update(S, Net.W0, sizeof(float) * P3::kHiddenDim * Net.ObsDim);
	EcoSha256::Update(S, Net.B0, sizeof(float) * P3::kHiddenDim);
	EcoSha256::Update(S, Net.W1, sizeof(float) * P3::kHiddenDim * P3::kHiddenDim);
	EcoSha256::Update(S, Net.B1, sizeof(float) * P3::kHiddenDim);
	EcoSha256::Update(S, Net.W2, sizeof(float) * P3::kNumBehaviors * P3::kHiddenDim);
	EcoSha256::Update(S, Net.B2, sizeof(float) * P3::kNumBehaviors);
	uint8 Digest[EcoSha256::kDigestBytes];
	EcoSha256::Final(S, Digest);
	char Hex[2 * EcoSha256::kDigestBytes + 1];
	EcoSha256::ToHex(Digest, Hex);
	return FString(ANSI_TO_TCHAR(Hex));
}

FString EcoV3Brain::AllowedText(const uint8 Allowed[EcoPolicyV3::kNumBehaviors])
{
	FString Out;
	for (int32 b = 0; b < EcoPolicyV3::kNumBehaviors; ++b)
	{
		if (Allowed[b] != 0)
		{
			Out += Out.IsEmpty() ? FString(EcoV3BrainImpl::kBehaviorKo[b]) : FString(TEXT("·")) + EcoV3BrainImpl::kBehaviorKo[b];
		}
	}
	return Out.IsEmpty() ? FString(TEXT("없음")) : Out;
}

FString EcoV3Brain::StartupFile()
{
#if !UE_BUILD_SHIPPING
	return EcoV3BrainImpl::CVarStartup.GetValueOnGameThread().TrimStartAndEnd();
#else
	return FString();
#endif
}

float EcoV3Brain::SwapAtSeconds()
{
#if !UE_BUILD_SHIPPING
	return EcoV3BrainImpl::CVarSwapAt.GetValueOnGameThread();
#else
	return -1.0f;
#endif
}

FString EcoV3Brain::SwapFile()
{
#if !UE_BUILD_SHIPPING
	return EcoV3BrainImpl::CVarSwapFile.GetValueOnGameThread().TrimStartAndEnd();
#else
	return FString();
#endif
}

FString EcoV3Brain::WatchFolder()
{
#if !UE_BUILD_SHIPPING
	return EcoV3BrainImpl::CVarWatch.GetValueOnGameThread().TrimStartAndEnd();
#else
	return FString();
#endif
}

bool EcoV3Brain::NoticeEnabled()
{
#if !UE_BUILD_SHIPPING
	return EcoV3BrainImpl::CVarNotice.GetValueOnGameThread() != 0;
#else
	return false;
#endif
}

bool EcoV3Brain::NoticeShot()
{
#if !UE_BUILD_SHIPPING
	return EcoV3BrainImpl::CVarNoticeShot.GetValueOnGameThread() != 0;
#else
	return false;
#endif
}

FString EcoV3Brain::StatusFile()
{
#if !UE_BUILD_SHIPPING
	return EcoV3BrainImpl::CVarStatusFile.GetValueOnGameThread().TrimStartAndEnd();
#else
	return FString();
#endif
}

double EcoV3Brain::NowUnixSeconds()
{
	return (FDateTime::UtcNow() - FDateTime(1970, 1, 1)).GetTotalSeconds();
}

bool EcoV3Brain::ParseLiveStatus(const FString& JsonText, FEcoV3LiveStatus& Out, FString* OutError)
{
	using namespace EcoV3BrainImpl;
	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root.IsValid())
	{
		if (OutError)
		{
			*OutError = TEXT("JSON 으로 읽지 못했다");
		}
		return false;
	}
	FString Format;
	int32 Version = 0;
	if (!Root->TryGetStringField(TEXT("format"), Format) || Format != kLiveStatusFormat || !Root->TryGetNumberField(TEXT("version"), Version)
		|| Version != kLiveStatusVersion)
	{
		if (OutError)
		{
			*OutError = FString::Printf(TEXT("형식 '%s' 판 %d 이 '%s' 판 %d 가 아니다"), *Format, Version, kLiveStatusFormat, kLiveStatusVersion);
		}
		return false;
	}
	FEcoV3LiveStatus S;
	S.bValid = true;
	S.State = StringField(Root.Get(), TEXT("state"));
	S.Message = StringField(Root.Get(), TEXT("message"));
	S.LastResult = StringField(Root.Get(), TEXT("last_result"));
	S.Snapshot = StringField(Root.Get(), TEXT("snapshot"));
	S.Env = StringField(Root.Get(), TEXT("env"));
	Root->TryGetNumberField(TEXT("attempt"), S.Attempt);
	Root->TryGetNumberField(TEXT("round"), S.Round);
	Root->TryGetNumberField(TEXT("pid"), S.Pid);
	Root->TryGetNumberField(TEXT("updated_unix"), S.UpdatedUnix);
	if (!Root->TryGetNumberField(TEXT("progress"), S.Progress) || !FMath::IsFinite(S.Progress))
	{
		S.Progress = -1.0;
	}
	if (!FMath::IsFinite(S.UpdatedUnix))
	{
		S.UpdatedUnix = 0.0;
	}
	Out = S;
	return true;
}

FString EcoV3Brain::LiveStatusText(const FEcoV3LiveStatus& Status, bool bFileExists, double NowUnix)
{
	if (!bFileExists)
	{
		return TEXT("적응 고리 | 파이썬 감시 없음");
	}
	if (!Status.bValid)
	{
		return TEXT("적응 고리 | 상태 파일을 못 읽음");
	}
	if (!(Status.UpdatedUnix > 0.0))
	{
		return TEXT("적응 고리 | 응답 없음 (시각 없음)");
	}
	const double Age = NowUnix - Status.UpdatedUnix;
	if (Age <= kStatusFreshSeconds)
	{
		return FString::Printf(TEXT("적응 고리 | %s"), Status.Message.IsEmpty() ? *Status.State : *Status.Message);
	}
	return FString::Printf(TEXT("적응 고리 | 응답 없음 (%lld초 전)"), static_cast<long long>(FMath::FloorToDouble(FMath::Min(Age, 1e12))));
}

FString FEcoV3Brain::Describe() const
{
	FString Extra;
	if (bRoute())
	{
		// 10-24 두 길 두뇌 (판 4·5 — 도주 반사 중 두뇌가 RUN·SHELTER 를 고른다. 판 5 는 반사 밖 두뇌 FLEE 를 막는다)
		Extra += FString::Printf(TEXT(", 관측 %d 도망길%s"), ObsDim, bFleeGate() ? TEXT("·반사 밖 도망 막음") : TEXT(""));
	}
	else if (ObsDim > EcoPolicyV3::kObsDim)
	{
		Extra += FString::Printf(TEXT(", 관측 %d 장애물"), ObsDim);
	}
	if (AdaptRound > 0)
	{
		Extra += FString::Printf(TEXT(", 판 %d"), AdaptRound);
	}
	const FString Origin = bBuiltin	  ? FString(TEXT("내장 R1b PolicyWeightsV3.h"))
						   : bDefault ? FString::Printf(TEXT("기본 두뇌 %s — 빌드에 넣은 %s"), *Label, UTF8_TO_TCHAR(EcoPolicyV3Default::kFileName))
									  : FString::Printf(TEXT("파일 %s"), *FPaths::GetCleanFilename(SourceFile));
	return FString::Printf(TEXT("%s (%s, 허용 %s%s)"), *Id, *Origin, *EcoV3Brain::AllowedText(Allowed), *Extra);
}

FString FEcoV3Brain::RoundTag() const
{
	if (AdaptRound > 0)
	{
		return FString::Printf(TEXT("판 %d"), AdaptRound);
	}
	return bBuiltin || bDefault ? FString(TEXT("판 0")) : FString();
}

FString FEcoV3Brain::OriginText() const
{
	return bDefault ? FString::Printf(TEXT("기본 두뇌 %s"), *Label) : bBuiltin ? FString(TEXT("내장 두뇌")) : FString();
}

FString FEcoV3Brain::ShortId() const
{
	FString Name = ModelName;
	if (ModelName.Len() > 10)
	{
		// 앞 7 자 + '…'. 적응 고리 이름 live_r<판>_<실행> 은 판 번호 끝까지 남긴다 (판 10 넘어도 화면 id 가 서로 갈리게)
		int32 Keep = 7;
		constexpr int32 kLivePrefixLen = 6;   // 'live_r'
		if (ModelName.StartsWith(TEXT("live_r"), ESearchCase::CaseSensitive))
		{
			int32 End = kLivePrefixLen;
			while (End < ModelName.Len() && FChar::IsDigit(ModelName[End]))
			{
				++End;
			}
			Keep = End > kLivePrefixLen ? End : Keep;
		}
		Name = Keep < ModelName.Len() ? ModelName.Left(Keep) + TEXT("…") : ModelName;
	}
	return FString::Printf(TEXT("%s@%s"), *Name, *WeightsSha256.Left(4));
}

// -----------------------------------------------------------------------------
// 내장 두뇌·파일 읽기
// -----------------------------------------------------------------------------

FEcoV3BrainRef FEcoV3BrainRegistry::Builtin()
{
	static const FEcoV3BrainRef Brain = []()
	{
		namespace P3 = EcoPolicyV3;
		TSharedRef<FEcoV3Brain, ESPMode::ThreadSafe> B = MakeShared<FEcoV3Brain, ESPMode::ThreadSafe>();
		B->bBuiltin = true;
		B->ContractHash = P3::kContractHash;
		B->ObsDim = P3::kObsDim;
		B->Net = P3::kBuiltinNet;
		B->ModelName = UTF8_TO_TCHAR(P3::kModelName);
		B->Label = TEXT("R1b");
		B->WeightsSha256 = EcoV3Brain::WeightsSha256(B->Net);
		B->Id = FString::Printf(TEXT("%s@%s"), *B->ModelName, *B->WeightsSha256.Left(8));
		B->ModelSha256 = FString::Printf(TEXT("%016llx…"), static_cast<unsigned long long>(P3::kModelDigest));
		B->TrainWorld = TEXT("R1b (빌드에 들어간 내장 두뇌 — 10-28 까지의 게임 기본, 통합 모드는 얼기를 세계가 막아 R1b-F)");
		for (int32 b = 0; b < P3::kNumBehaviors; ++b)
		{
			B->Allowed[b] = P3::kAllowedMask[b];
		}
		return FEcoV3BrainRef(B);
	}();
	return Brain;
}

namespace EcoV3BrainImpl
{
	/** 두뇌 파일 글자 → 검사 → 두뇌 (Parse 의 몸. bDefaultBrain = 빌드에 넣은 기본 두뇌 — 같은 검사, 표시만 다르다). */
	FEcoV3BrainLoad ParseBrain(const FString& JsonText, const FString& Source, bool bDefaultBrain);
}

FEcoV3BrainRef FEcoV3BrainRegistry::Default()
{
	static const FEcoV3BrainRef Brain = []() -> FEcoV3BrainRef
	{
		namespace D = EcoPolicyV3Default;
		// 넣은 바이트 그대로 (UTF-8 JSON — 파일 두뇌와 같은 Parse). 바이트 sha256 = 헤더 값, 검사 통과, id = 헤더 id 여야 한다
		char Hex[2 * EcoSha256::kDigestBytes + 1];
		EcoSha256::HashHex(D::kFile, static_cast<size_t>(D::kFileBytes), Hex);
		const auto Conv = StringCast<TCHAR>(reinterpret_cast<const UTF8CHAR*>(D::kFile), D::kFileBytes);
		const FString Text(Conv.Length(), Conv.Get());
		const FEcoV3BrainLoad L = EcoV3BrainImpl::ParseBrain(Text, FString(), /*bDefaultBrain*/ true);
		const FString WantId = UTF8_TO_TCHAR(D::kBrainId);
		if (FCStringAnsi::Strcmp(Hex, D::kFileSha256) != 0 || !L.Ok() || L.Brain->Id != WantId)
		{
			UE_LOG(LogEcoV3Brain, Error, TEXT("[EcoV3Brain] 기본 두뇌(PolicyBrainV3Default.h %s, %s) 검사 실패 — 바이트 sha256 %s (헤더 %s) · %s: %s · id %s — 내장 두뇌 %s 로 대신한다"),
				   UTF8_TO_TCHAR(D::kFileName), *WantId, ANSI_TO_TCHAR(Hex), UTF8_TO_TCHAR(D::kFileSha256), EcoV3Brain::RejectName(L.Reason), *L.Message,
				   L.Brain.IsValid() ? *L.Brain->Id : TEXT("-"), *Builtin()->Id);
			return Builtin();
		}
		return L.Brain.ToSharedRef();
	}();
	return Brain;
}

FEcoV3BrainLoad FEcoV3BrainRegistry::Parse(const FString& JsonText, const FString& Source)
{
	return EcoV3BrainImpl::ParseBrain(JsonText, Source, /*bDefaultBrain*/ false);
}

FEcoV3BrainLoad EcoV3BrainImpl::ParseBrain(const FString& JsonText, const FString& Source, bool bDefaultBrain)
{
	using namespace EcoV3BrainImpl;
	namespace P3 = EcoPolicyV3;

	TSharedPtr<FJsonObject> Root;
	if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(JsonText), Root) || !Root.IsValid())
	{
		return Fail(EReject::Json, TEXT("JSON 으로 읽지 못했다"));
	}
	const FJsonObject& R = *Root;

	// 형식·판
	FString Format;
	int32 Version = 0;
	if (!R.TryGetStringField(TEXT("format"), Format) || Format != kFormat || !R.TryGetNumberField(TEXT("format_version"), Version))
	{
		return Fail(EReject::Format, FString::Printf(TEXT("형식이 '%s' 가 아니다 ('%s')"), kFormat, *Format));
	}
	if (Version != kFormatVersion)
	{
		return Fail(EReject::Format, FString::Printf(TEXT("형식 판 %d — 이 빌드는 %d 만 읽는다"), Version, kFormatVersion));
	}
	const FJsonObject* Model = ObjectField(R, TEXT("model"));
	const FString ModelName = StringField(Model, TEXT("name"));
	if (ModelName.IsEmpty())
	{
		return Fail(EReject::Format, TEXT("model.name 이 없다"));
	}

	// 계약 해시 (관측 순서·행동 순서·망 모양·마스크 판·문턱·선택 규칙)
	FString HashText;
	R.TryGetStringField(TEXT("contract_hash"), HashText);
	const uint64 Hash = HashText.StartsWith(TEXT("0x")) ? FCString::Strtoui64(*HashText + 2, nullptr, 16) : 0;
	const FContract* Ct = FindContract(Hash);
	if (!Ct)
	{
		return Fail(EReject::Contract,
					FString::Printf(TEXT("계약 해시 %s 가 이 빌드가 받는 0x%016llx (관측 18)·0x%016llx (관측 21 장애물)·0x%016llx (관측 24 도망길 판 4)·0x%016llx (관측 24 도망길 판 5) 가 ")
										TEXT("아니다 (관측·마스크 계약이 다른 모델 — C++ 관측 코드를 함께 바꿔야 한다)"),
									*HashText, static_cast<unsigned long long>(Contract(0).Hash), static_cast<unsigned long long>(Contract(1).Hash),
									static_cast<unsigned long long>(Contract(2).Hash), static_cast<unsigned long long>(Contract(3).Hash)));
	}
	const int32 WantObs = Ct->ObsDim;

	// 차원 (관측 = 그 계약의 칸 수)
	int32 ObsDim = 0;
	int32 Hidden = 0;
	int32 NumBeh = 0;
	if (!R.TryGetNumberField(TEXT("obs_dim"), ObsDim) || !R.TryGetNumberField(TEXT("hidden"), Hidden) || !R.TryGetNumberField(TEXT("num_behaviors"), NumBeh)
		|| ObsDim != WantObs || Hidden != P3::kHiddenDim || NumBeh != P3::kNumBehaviors)
	{
		return Fail(EReject::Dims, FString::Printf(TEXT("차원 관측 %d·은닉 %d·행동 %d 이 계약(%s)의 %d·%d·%d 과 다르다"), ObsDim, Hidden, NumBeh, Ct->Label, WantObs,
												 P3::kHiddenDim, P3::kNumBehaviors));
	}

	// 이름 순서
	TArray<FString> ObsNames;
	TArray<FString> BehNames;
	if (!ReadStringArray(R, TEXT("obs_names"), ObsNames) || !ReadStringArray(R, TEXT("behaviors"), BehNames) || ObsNames.Num() != WantObs
		|| BehNames.Num() != P3::kNumBehaviors)
	{
		return Fail(EReject::Names, TEXT("obs_names·behaviors 가 없거나 길이가 다르다"));
	}
	for (int32 i = 0; i < WantObs; ++i)
	{
		const char* Want = ContractObsName(*Ct, i);
		if (ObsNames[i] != UTF8_TO_TCHAR(Want))
		{
			return Fail(EReject::Names, FString::Printf(TEXT("관측 %d 칸 '%s' 이 계약의 '%s' 와 다르다"), i, *ObsNames[i], UTF8_TO_TCHAR(Want)));
		}
	}
	for (int32 b = 0; b < P3::kNumBehaviors; ++b)
	{
		if (BehNames[b] != UTF8_TO_TCHAR(P3::kBehaviorNames[b]))
		{
			return Fail(EReject::Names, FString::Printf(TEXT("행동 %d '%s' 이 이 빌드의 '%s' 와 다르다"), b, *BehNames[b], UTF8_TO_TCHAR(P3::kBehaviorNames[b])));
		}
	}

	// 마스크 판·문턱
	int32 MaskVersion = 0;
	if (!R.TryGetNumberField(TEXT("mask_version"), MaskVersion) || MaskVersion != Ct->MaskVersion)
	{
		return Fail(EReject::Mask, FString::Printf(TEXT("마스크 판 %d 이 계약의 %d 와 다르다"), MaskVersion, Ct->MaskVersion));
	}
	// 10-24 두 길 두뇌 (판 4·5, 이식 계획서 5-2 의 5·13-2): 계약 dict 의 flight_route·brain_flee_outside_reflex 를 이 빌드 상수와 견준다
	// (해시가 이미 덮지만 어긋난 칸 이름을 적는다 — 평가기 Tools/EcoV3Eval 과 같은 칸)
	if (P3::IsRouteMaskVersion(Ct->MaskVersion))
	{
		const FString Diff = RouteContractDiff(R, Ct->MaskVersion);
		if (!Diff.IsEmpty())
		{
			return Fail(EReject::Contract, FString::Printf(TEXT("두 길 두뇌 계약 칸이 이 빌드와 다르다: %s (%s)"), *Diff, Ct->Label));
		}
	}
	const FJsonObject* Th = ObjectField(R, TEXT("thresholds"));
	double Tr = 0.0;
	double Hc = 0.0;
	double Am = 0.0;
	double Ml = 0.0;
	if (!Th || !Th->TryGetNumberField(TEXT("threat_recency_obs"), Tr) || !Th->TryGetNumberField(TEXT("hide_cover_obs"), Hc)
		|| !Th->TryGetNumberField(TEXT("alarm_mask_obs"), Am) || !Th->TryGetNumberField(TEXT("mask_logit"), Ml)
		|| static_cast<float>(Tr) != P3::kThreatRecencyObs || static_cast<float>(Hc) != P3::kHideCoverObs || static_cast<float>(Am) != P3::kAlarmMaskObs
		|| static_cast<float>(Ml) != P3::kMaskLogit)
	{
		return Fail(EReject::Thresholds, FString::Printf(TEXT("마스크 문턱 (%g, %g, %g, %g) 이 이 빌드 (%g, %g, %g, %g) 와 다르다"), Tr, Hc, Am, Ml,
													   P3::kThreatRecencyObs, P3::kHideCoverObs, P3::kAlarmMaskObs, P3::kMaskLogit));
	}

	TSharedRef<FEcoV3Brain, ESPMode::ThreadSafe> B = MakeShared<FEcoV3Brain, ESPMode::ThreadSafe>();
	B->ContractHash = Ct->Hash;
	B->ObsDim = WantObs;
	B->MaskVersion = Ct->MaskVersion;

	// 허용 칸: 이름 목록 = 칸 (먹기는 늘 — 마스크가 비지 않게)
	{
		TArray<FString> AllowedNames;
		int32 AllowedMask[P3::kNumBehaviors] = {};
		if (!ReadStringArray(R, TEXT("allowed"), AllowedNames) || !ReadInts(R, TEXT("allowed_mask"), P3::kNumBehaviors, AllowedMask))
		{
			return Fail(EReject::Allowed, TEXT("allowed·allowed_mask 가 없다"));
		}
		for (const FString& N : AllowedNames)
		{
			const int32 b = BehNames.IndexOfByKey(N);
			if (b == INDEX_NONE || B->Allowed[b] != 0)
			{
				return Fail(EReject::Allowed, FString::Printf(TEXT("허용 이름 '%s' 이 행동이 아니거나 두 번 나온다"), *N));
			}
			B->Allowed[b] = 1;
		}
		for (int32 b = 0; b < P3::kNumBehaviors; ++b)
		{
			if (AllowedMask[b] != static_cast<int32>(B->Allowed[b]))
			{
				return Fail(EReject::Allowed, TEXT("allowed_mask 가 allowed 이름과 다르다"));
			}
		}
		if (B->Allowed[P3::kGraze] == 0)
		{
			return Fail(EReject::Allowed, TEXT("먹기(graze)가 허용되지 않는다 — 마스크가 빌 수 있다"));
		}
		if (B->bRoute() && (B->Allowed[P3::kFreeze] != 0 || B->Allowed[P3::kSleep] != 0))
		{
			// 판 4·5 는 칸 3·4 를 도주 중 길 칸으로 다시 쓴다 — 모델 허용에 얼기·잠이 있으면 거부 (이식 계획서 5-2 의 4. 걸 때 실제 허용은 SyncBrain 이 다시 본다)
			return Fail(EReject::Allowed, FString::Printf(TEXT("두 길 두뇌(마스크 판 %d)의 허용에 얼기·잠이 있다 (%s) — 칸 3·4 는 도주 중 길 칸이라 막혀야 한다"),
														  B->MaskVersion, *AllowedText(B->Allowed)));
		}
	}

	// 층
	{
		const TArray<TSharedPtr<FJsonValue>>* Layers = nullptr;
		if (!R.TryGetArrayField(TEXT("layers"), Layers) || Layers->Num() != 3)
		{
			return Fail(EReject::Shape, TEXT("층이 셋이 아니다"));
		}
		const int32 Want[3][2] = {{P3::kHiddenDim, WantObs}, {P3::kHiddenDim, P3::kHiddenDim}, {P3::kNumBehaviors, P3::kHiddenDim}};
		TArray<float>* Ws[3] = {&B->Layer0Weight, &B->Layer1Weight, &B->Layer2Weight};
		TArray<float>* Bs[3] = {&B->Layer0Bias, &B->Layer1Bias, &B->Layer2Bias};
		for (int32 k = 0; k < 3; ++k)
		{
			const TSharedPtr<FJsonObject> L = (*Layers)[k].IsValid() ? (*Layers)[k]->AsObject() : nullptr;
			if (!L.IsValid())
			{
				return Fail(EReject::Shape, FString::Printf(TEXT("층 %d 이 객체가 아니다"), k));
			}
			FString Msg;
			const EReject Why = ReadLayer(*L, Want[k][0], Want[k][1], *Ws[k], *Bs[k], Msg);
			if (Why != EReject::None)
			{
				return Fail(Why, FString::Printf(TEXT("층 %d: %s"), k, *Msg));
			}
		}
		for (int32 k = 0; k < 3; ++k)
		{
			for (const TArray<float>* Arr : {Ws[k], Bs[k]})
			{
				for (const float V : *Arr)
				{
					if (!FMath::IsFinite(V))
					{
						return Fail(EReject::NonFinite, FString::Printf(TEXT("층 %d 에 NaN·Inf 가 있다"), k));
					}
				}
			}
		}
		B->Net = {WantObs, B->Layer0Weight.GetData(), B->Layer0Bias.GetData(), B->Layer1Weight.GetData(), B->Layer1Bias.GetData(),
				  B->Layer2Weight.GetData(), B->Layer2Bias.GetData()};
	}

	// sha256 (가중치 바이트)
	{
		FString Want;
		R.TryGetStringField(TEXT("weights_sha256"), Want);
		B->WeightsSha256 = EcoV3Brain::WeightsSha256(B->Net);
		if (Want.IsEmpty() || !Want.Equals(B->WeightsSha256, ESearchCase::IgnoreCase))
		{
			return Fail(EReject::Digest, FString::Printf(TEXT("가중치 sha256 %s 이 파일에 적힌 %s 와 다르다"), *B->WeightsSha256.Left(16), *Want.Left(16)));
		}
	}

	// 골든 자체 확인: 파일 속 관측 + 마스크 → 이 빌드의 순전파(RunPolicyV3) → 로짓·행동이 파이썬과 같아야 한다
	{
		const FJsonObject* G = ObjectField(R, TEXT("golden"));
		const TArray<TSharedPtr<FJsonValue>>* Cases = nullptr;
		double Tol = 0.0;
		if (!G || !G->TryGetArrayField(TEXT("cases"), Cases) || !G->TryGetNumberField(TEXT("logit_tolerance"), Tol))
		{
			return Fail(EReject::Golden, TEXT("golden.cases·logit_tolerance 가 없다"));
		}
		if (!(Tol > 0.0) || Tol > kMaxLogitTolerance)
		{
			return Fail(EReject::Golden, FString::Printf(TEXT("허용 오차 %g 가 (0, %g] 밖이다"), Tol, kMaxLogitTolerance));
		}
		if (Cases->Num() < kMinGolden)
		{
			return Fail(EReject::Golden, FString::Printf(TEXT("골든 %d 사례 — %d 사례 이상이어야 한다"), Cases->Num(), kMinGolden));
		}
		float MaxErr = 0.0f;
		int32 BadAction = 0;
		int32 Worst = -1;
		for (int32 n = 0; n < Cases->Num(); ++n)
		{
			const TSharedPtr<FJsonObject> C = (*Cases)[n].IsValid() ? (*Cases)[n]->AsObject() : nullptr;
			float Obs[P3::kMaxObsDim];
			float Want[P3::kNumBehaviors];
			int32 MaskInt[P3::kNumBehaviors];
			int32 Action = -1;
			if (!C.IsValid() || !ReadFloats(*C, TEXT("obs"), WantObs, Obs) || !ReadFloats(*C, TEXT("logits"), P3::kNumBehaviors, Want)
				|| !ReadInts(*C, TEXT("mask"), P3::kNumBehaviors, MaskInt) || !C->TryGetNumberField(TEXT("action"), Action) || Action < 0
				|| Action >= P3::kNumBehaviors)
			{
				return Fail(EReject::Golden, FString::Printf(TEXT("골든 사례 %d 를 읽지 못했다"), n));
			}
			uint8 Mask[P3::kNumBehaviors];
			for (int32 b = 0; b < P3::kNumBehaviors; ++b)
			{
				Mask[b] = MaskInt[b] != 0 ? 1 : 0;
			}
			float Logits[P3::kNumBehaviors];
			const int32 Got = P3::RunPolicyV3(B->Net, Obs, Mask, Logits);
			for (int32 b = 0; b < P3::kNumBehaviors; ++b)
			{
				const float E = FMath::Abs(Logits[b] - Want[b]);
				if (!(E <= MaxErr))   // NaN 도 여기서 잡힌다
				{
					MaxErr = FMath::IsFinite(E) ? E : TNumericLimits<float>::Max();
					Worst = n;
				}
			}
			BadAction += Got != Action ? 1 : 0;
		}
		if (MaxErr > static_cast<float>(Tol) || BadAction > 0)
		{
			return Fail(EReject::Golden, FString::Printf(TEXT("골든 %d 사례: 최대 로짓 오차 %.3e (사례 %d, 허용 %.0e), 행동 다름 %d"), Cases->Num(), MaxErr, Worst, Tol,
													  BadAction));
		}
		B->GoldenCount = Cases->Num();
		B->GoldenTolerance = static_cast<float>(Tol);
		B->GoldenMaxError = MaxErr;
		B->GoldenWorld = StringField(G, TEXT("world_config"));
	}

	const FJsonObject* Train = ObjectField(R, TEXT("train"));
	B->ModelName = ModelName;
	B->ModelPath = StringField(Model, TEXT("path"));
	B->ModelSha256 = StringField(Model, TEXT("sha256"));
	B->TrainConfig = StringField(Train, TEXT("config"));
	B->TrainDigest = StringField(Train, TEXT("config_digest"));
	B->TrainWorld = StringField(Train, TEXT("world"));
	B->SourceFile = Source;
	B->Id = FString::Printf(TEXT("%s@%s"), *ModelName, *B->WeightsSha256.Left(8));
	if (bDefaultBrain)
	{
		// 10-29 기본 두뇌 (PolicyBrainV3Default.h): 같은 검사를 지난 같은 두뇌 — 출처 표시만 다르다 (디스크 파일이 아니다)
		B->bDefault = true;
		B->Label = UTF8_TO_TCHAR(EcoPolicyV3Default::kLabel);
		B->SourceFile.Empty();
	}

	// 적응 고리 'adapt' 블록 (선택 — 없거나 값이 깨졌으면 빈 칸으로 두고 거부하지 않는다. 가중치·골든 검사와 무관)
	if (const FJsonObject* Adapt = ObjectField(R, TEXT("adapt")))
	{
		B->bAdapt = true;
		double Round = 0.0;
		double Attempt = 0.0;
		Adapt->TryGetNumberField(TEXT("round"), Round);
		Adapt->TryGetNumberField(TEXT("attempt"), Attempt);
		B->AdaptRound = FMath::IsFinite(Round) ? static_cast<int32>(FMath::Clamp(Round, 0.0, 1e6)) : 0;
		B->AdaptAttempt = FMath::IsFinite(Attempt) ? static_cast<int32>(FMath::Clamp(Attempt, 0.0, 1e6)) : 0;
		B->AdaptRun = StringField(Adapt, TEXT("run"));
		B->AdaptSnapshot = StringField(Adapt, TEXT("snapshot"));
		B->AdaptEnv = StringField(Adapt, TEXT("env"));
		B->AdaptGate = StringField(Adapt, TEXT("gate"));
		B->AdaptPlayId = StringField(Adapt, TEXT("play_id"));
	}

	FEcoV3BrainLoad L;
	L.Path = Source;
	L.Brain = B;
	return L;
}

bool FEcoV3BrainRegistry::IsBuiltinName(const FString& Name)
{
	const FString N = Name.TrimStartAndEnd();
	return N.Equals(TEXT("builtin"), ESearchCase::IgnoreCase) || N == TEXT("내장") || N.Equals(TEXT("R1b"), ESearchCase::IgnoreCase)
		|| N.Equals(TEXT("R1b-F"), ESearchCase::IgnoreCase);
}

bool FEcoV3BrainRegistry::IsDefaultName(const FString& Name)
{
	const FString N = Name.TrimStartAndEnd();
	return N.Equals(TEXT("default"), ESearchCase::IgnoreCase) || N == TEXT("기본")
		|| N.Equals(UTF8_TO_TCHAR(EcoPolicyV3Default::kLabel), ESearchCase::IgnoreCase);
}

TArray<FString> FEcoV3BrainRegistry::SearchFolders()
{
	return {FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / TEXT("EcoBrains")),
			FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("EcoBrains"))};
}

FString FEcoV3BrainRegistry::Resolve(const FString& PathOrName, FString* OutTried)
{
	FString Arg = PathOrName.TrimStartAndEnd().TrimQuotes();
	FPaths::NormalizeFilename(Arg);
	TArray<FString> Candidates;
	auto Add = [&Candidates](const FString& P)
	{
		Candidates.Add(P);
		if (!P.EndsWith(TEXT(".json"), ESearchCase::IgnoreCase))
		{
			Candidates.Add(P + TEXT(".json"));
		}
	};
	if (Arg.IsEmpty())
	{
		return FString();
	}
	if (!FPaths::IsRelative(Arg))
	{
		Add(Arg);
	}
	else
	{
		Add(FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / Arg));
		for (const FString& Folder : SearchFolders())
		{
			Add(Folder / Arg);
		}
	}
	for (const FString& C : Candidates)
	{
		if (FPaths::FileExists(C))
		{
			return C;
		}
	}
	if (OutTried)
	{
		*OutTried = FString::Join(Candidates, TEXT(", "));
	}
	return FString();
}

FEcoV3BrainLoad FEcoV3BrainRegistry::LoadFile(const FString& PathOrName)
{
	if (IsBuiltinName(PathOrName))
	{
		FEcoV3BrainLoad L;
		L.Brain = Builtin();
		return L;
	}
	if (IsDefaultName(PathOrName))
	{
		FEcoV3BrainLoad L;
		L.Brain = Default();
		return L;
	}
	FString Tried;
	const FString Path = Resolve(PathOrName, &Tried);
	if (Path.IsEmpty())
	{
		FEcoV3BrainLoad L = EcoV3BrainImpl::Fail(EcoV3Brain::EReject::File, FString::Printf(TEXT("'%s' 을 찾지 못했다 (찾아본 곳: %s)"), *PathOrName, *Tried));
		L.Path = Tried;
		return L;
	}
	FString Text;
	if (!FFileHelper::LoadFileToString(Text, *Path))
	{
		FEcoV3BrainLoad L = EcoV3BrainImpl::Fail(EcoV3Brain::EReject::File, FString::Printf(TEXT("%s 를 읽지 못했다"), *Path));
		L.Path = Path;
		return L;
	}
	FEcoV3BrainLoad L = Parse(Text, Path);
	L.Path = Path;
	return L;
}

TArray<FString> FEcoV3BrainRegistry::ListFiles()
{
	TArray<FString> Out;
	for (const FString& Folder : SearchFolders())
	{
		TArray<FString> Names;
		IFileManager::Get().FindFiles(Names, *(Folder / TEXT("*.json")), true, false);
		Names.Sort();
		for (const FString& N : Names)
		{
			Out.Add(Folder / N);
		}
	}
	return Out;
}

// -----------------------------------------------------------------------------
// 저장소
// -----------------------------------------------------------------------------

namespace EcoV3BrainImpl
{
	/** 상대 경로는 프로젝트 폴더 기준 (eco.V3Brain.WatchFolder·StatusFile). */
	FString ProjectPath(const FString& Path)
	{
		return FPaths::IsRelative(Path) ? FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / Path) : Path;
	}

	/** 폴더 안 가장 새 *.json (시각이 같으면 경로가 큰 쪽). 없으면 빈 값. 파이썬의 *.json.tmp 는 걸리지 않는다. */
	FString NewestJson(const FString& Dir, FDateTime& OutStamp)
	{
		TArray<FString> Names;
		IFileManager::Get().FindFiles(Names, *(Dir / TEXT("*.json")), true, false);
		FString Newest;
		OutStamp = FDateTime::MinValue();
		for (const FString& N : Names)
		{
			const FString P = Dir / N;
			const FDateTime S = IFileManager::Get().GetTimeStamp(*P);
			if (S > OutStamp || (S == OutStamp && P > Newest))
			{
				Newest = P;
				OutStamp = S;
			}
		}
		return Newest;
	}
}

FEcoV3BrainRegistry::FEcoV3BrainRegistry()
	: Active(Builtin())
	, ActiveWhy(TEXT("내장 (처음)"))
{
}

FEcoV3BrainRegistry& FEcoV3BrainRegistry::Get()
{
	static FEcoV3BrainRegistry Registry;
	return Registry;
}

void FEcoV3BrainRegistry::Queue(const FEcoV3BrainRef& Brain, const FString& Why)
{
	QueueImpl(Brain, Why, TOptional<FEcoV3BrainHistoryEntry>());
}

void FEcoV3BrainRegistry::QueueImpl(const FEcoV3BrainRef& Brain, const FString& Why, TOptional<FEcoV3BrainHistoryEntry> RollbackEntry)
{
	check(IsInGameThread());
	if (Pending.IsValid())
	{
		UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 대기 두뇌 %s 를 버리고 새 대기 두뇌로 바꾼다"), *Pending->Id);
	}
	if (!RollbackEntry.IsSet() && !PendingRollback.IsEmpty())
	{
		// 대기 되돌림을 다른 두뇌가 덮었다: 꺼낸 칸들을 꺼낸 반대 순서로 쌓개에 돌려놓는다 (경계 전 두 번 되돌렸어도 되돌리기를 부르기 전 쌓개 그대로)
		for (int32 i = PendingRollback.Num() - 1; i >= 0; --i)
		{
			History.Add(MoveTemp(PendingRollback[i]));
		}
		PendingRollback.Reset();
	}
	Pending = Brain;
	PendingWhy = Why;
	if (RollbackEntry.IsSet())
	{
		PendingRollback.Add(MoveTemp(RollbackEntry.GetValue()));
	}
	UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 대기: %s — 까닭: %s | 다음 결정 스텝 경계에서 바뀐다 (지금 %s)"), *Brain->Describe(), *Why, *Active->Id);
}

bool FEcoV3BrainRegistry::CommitPending(FEcoV3BrainPtr* OutFrom, FString* OutWhy, bool* bOutRollback)
{
	if (!Pending.IsValid())
	{
		return false;
	}
	const bool bRollback = !PendingRollback.IsEmpty();
	if (OutFrom)
	{
		*OutFrom = Active;
	}
	if (OutWhy)
	{
		*OutWhy = PendingWhy;
	}
	if (bOutRollback)
	{
		*bOutRollback = bRollback;
	}
	// 되돌리기 쌓개: 나가는 두뇌를 쌓는다 (되돌림이면 쌓지 않는다 — 되돌린 두뇌로 다시 돌아가지 않게. 같은 id 로 바꾸면 쌓지 않는다)
	if (!bRollback && Pending->Id != Active->Id)
	{
		History.Add(FEcoV3BrainHistoryEntry{Active, ActiveWhy, PendingWhy});
		if (History.Num() > EcoV3Brain::kHistoryMax)
		{
			History.RemoveAt(0);
		}
	}
	Active = Pending.ToSharedRef();
	ActiveWhy = PendingWhy;
	bCommitted = true;
	bLastCommitRollback = bRollback;
	LastCommitWhy = PendingWhy;
	Pending.Reset();
	PendingWhy.Empty();
	PendingRollback.Reset();   // 되돌림이 바뀌었다 — 건너뛴 칸은 버린다 (되돌린 두뇌는 쌓지 않는다)
	++Generation;
	++SwapCount;
	return true;
}

bool FEcoV3BrainRegistry::DiscardPending(const FString& Why)
{
	check(IsInGameThread());
	if (!Pending.IsValid())
	{
		return false;
	}
	UE_LOG(LogEcoV3Brain, Warning, TEXT("[EcoV3Brain] 대기 두뇌 %s 를 버린다 — %s. 지금 두뇌 %s 그대로"), *Pending->Id, *Why, *Active->Id);
	// 대기 되돌림이었으면 꺼낸 칸들을 꺼낸 반대 순서로 쌓개에 돌려놓는다 (QueueImpl 이 대기 되돌림을 덮을 때와 같다)
	for (int32 i = PendingRollback.Num() - 1; i >= 0; --i)
	{
		History.Add(MoveTemp(PendingRollback[i]));
	}
	PendingRollback.Reset();
	Pending.Reset();
	PendingWhy.Empty();
	return true;
}

bool FEcoV3BrainRegistry::Rollback(const FString& Why, FString* OutMessage)
{
	check(IsInGameThread());
	if (History.IsEmpty())
	{
		const FString Msg = IsPendingRollback() ? FString::Printf(TEXT("더 앞 두뇌가 없다 — 대기 되돌림 %s 그대로"), *Pending->Id)
												: FString::Printf(TEXT("되돌릴 앞 두뇌가 없다 (쌓개 빔) — 지금 두뇌 %s 그대로"), *Active->Id);
		UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 되돌리기: %s"), *Msg);
		if (OutMessage)
		{
			*OutMessage = Msg;
		}
		return false;
	}
	if (IsPendingRollback())
	{
		// 이미 대기 중인 되돌림: 그 두뇌는 건너뛰고 하나 더 앞으로. 꺼낸 칸은 대기 되돌림 칸들에 남긴다 — 경계에서 바뀌면 버리고(되돌린 두뇌는 쌓지 않는다),
		// 다른 두뇌가 줄을 덮으면 함께 쌓개에 돌려놓는다
		UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 되돌리기: 대기 되돌림 %s 를 건너뛰고 하나 더 앞으로"), *Pending->Id);
		Pending.Reset();
		PendingWhy.Empty();
	}
	FEcoV3BrainHistoryEntry Entry = History.Pop();
	const FEcoV3BrainRef Brain = Entry.Brain;
	const FString FullWhy = FString::Printf(TEXT("되돌림 %s (%s 에서, 처음 까닭: %s)"), *Why, *Active->Id, *Entry.Why);
	QueueImpl(Brain, FullWhy, MoveTemp(Entry));
	if (OutMessage)
	{
		*OutMessage = FString::Printf(TEXT("되돌림 대기: %s — 다음 결정 스텝 경계에서 바뀐다 (남은 쌓개 %d)"), *Brain->Describe(), History.Num());
	}
	return true;
}

FEcoV3StartPick FEcoV3BrainRegistry::PickStart(const FString& Startup, bool bAutoAdapt) const
{
	FEcoV3StartPick P;
	P.Startup = Startup.TrimStartAndEnd();
	if (!P.Startup.IsEmpty())
	{
		// 1. eco.V3Brain.Startup·-EcoV3Brain= — 통과하면 그 두뇌 (적응 고리 Play 여도: 사람이 고른 시작 두뇌가 이긴다)
		P.StartupLoad = LoadFile(P.Startup);
		if (P.StartupLoad.Ok())
		{
			P.Brain = P.StartupLoad.Brain;
			P.Why = FString::Printf(TEXT("시작 두뇌 eco.V3Brain.Startup %s"), *P.Startup);
			return P;
		}
		P.bStartupRejected = true;
	}
	const FString Rejected = P.bStartupRejected ? FString::Printf(TEXT(" (시작 두뇌 '%s' 거부)"), *P.Startup) : FString();
	const FEcoV3BrainRef Def = Default();
	const FEcoV3Brain& Will = Pending.IsValid() ? *Pending : *Active;
	if (bAutoAdapt)
	{
		// 2. 적응 고리 Play 는 늘 기본 두뇌(판 0)에서: 레벨은 Play 마다 저장된 처음 상태로 돌아오므로 앞 Play 의 바뀐 환경에 맞춘 두뇌는 맞지 않는다
		//    (저장소의 지금 두뇌는 프로세스에 하나라 PIE 를 다시 시작해도 남는다)
		if (Will.Id == Def->Id)
		{
			P.Why = FString::Printf(TEXT("적응 고리 Play — 이미 기본 두뇌(판 0) %s%s"), *Def->Id, *Rejected);
			return P;
		}
		P.Brain = Def;
		P.Why = FString::Printf(TEXT("적응 고리 Play 시작 — %s(판 0)에서 시작%s"), *Def->OriginText(), *Rejected);
		return P;
	}
	if (!bCommitted && !Pending.IsValid())
	{
		// 3. 이 프로세스의 첫 통합 v3 Play (두뇌를 건 적 없음 — 지금 두뇌는 저장소 처음 두뇌 내장 R1b): 기본 두뇌
		P.Brain = Def;
		// 10-29 확인: Startup 을 줬지만 거부했으면 '빔' 이라 적지 않는다 (기록 '… (처음 Play) (시작 두뇌 '…' 거부)')
		P.Why = P.bStartupRejected ? FString::Printf(TEXT("%s (처음 Play)%s"), *Def->OriginText(), *Rejected)
								   : FString::Printf(TEXT("%s (처음 Play — eco.V3Brain.Startup 빔)"), *Def->OriginText());
		return P;
	}
	P.Why = FString::Printf(TEXT("지금 두뇌 그대로 %s (이 프로세스에서 이미 두뇌를 걸었다 — 기본으로 돌리려면 eco.V3Brain.Startup default)%s"), *Will.Id, *Rejected);
	return P;
}

FString FEcoV3BrainRegistry::EffectiveWatchFolder() const
{
#if !UE_BUILD_SHIPPING
	const FString Folder = EcoV3Brain::WatchFolder();
	return Folder.IsEmpty() ? DefaultWatchFolder : Folder;
#else
	return FString();
#endif
}

void FEcoV3BrainRegistry::PrimeWatch()
{
	PrimedFiles.Reset();
	const FString Folder = EffectiveWatchFolder();
	if (Folder.IsEmpty())
	{
		return;
	}
	const FString Dir = EcoV3BrainImpl::ProjectPath(Folder);
	// 그때 있던 *.json 을 모두 (경로, 시각) 으로 기억한다 — 더 새 파일이 지워져 오래된 파일이 다시 가장 새 파일이 돼도 읽지 않게
	TArray<FString> Names;
	IFileManager::Get().FindFiles(Names, *(Dir / TEXT("*.json")), true, false);
	for (const FString& N : Names)
	{
		const FString P = Dir / N;
		PrimedFiles.Add(P, IFileManager::Get().GetTimeStamp(*P));
	}
	FDateTime Stamp;
	const FString Newest = EcoV3BrainImpl::NewestJson(Dir, Stamp);
	WatchedFile = Newest;
	WatchedStamp = Newest.IsEmpty() ? FDateTime() : Stamp;
	NextWatchPoll = 0.0;
	UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 폴더 감시 준비: %s — %s"), *Dir,
		   Newest.IsEmpty() ? TEXT("파일 없음")
							: *FString::Printf(TEXT("지금 있는 파일 %d 개(가장 새 %s)는 읽지 않는다 (Play 뒤에 나타나거나 바뀐 파일만 바꾼다)"), PrimedFiles.Num(),
											   *FPaths::GetCleanFilename(Newest)));
}

void FEcoV3BrainRegistry::ClearWatchPrime()
{
	PrimedFiles.Reset();
}

bool FEcoV3BrainRegistry::PollWatch(double NowSeconds)
{
	const FString Folder = EffectiveWatchFolder();
	if (Folder.IsEmpty() || NowSeconds < NextWatchPoll)
	{
		return false;
	}
	NextWatchPoll = NowSeconds + EcoV3Brain::kWatchPollSeconds;
	FDateTime NewestStamp;
	const FString Newest = EcoV3BrainImpl::NewestJson(EcoV3BrainImpl::ProjectPath(Folder), NewestStamp);
	if (Newest.IsEmpty() || (Newest == WatchedFile && NewestStamp == WatchedStamp))
	{
		return false;
	}
	const FDateTime* const PrimedStamp = PrimedFiles.Find(Newest);
	if (PrimedStamp && *PrimedStamp == NewestStamp)
	{
		// PrimeWatch 때 이미 있던 파일 (더 새 파일이 지워졌거나 시각이 되돌아갔다): 읽지 않는다. 기억해 두고 바뀔 때까지 다시 보지 않는다
		WatchedFile = Newest;
		WatchedStamp = NewestStamp;
		UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 폴더 감시: %s 는 Play 시작 때부터 있던 파일 — 읽지 않는다 (Play 뒤에 나타나거나 바뀐 파일만 바꾼다)"), *Newest);
		return false;
	}
	const FEcoV3BrainLoad L = LoadFile(Newest);
	if (!L.Ok())
	{
		// 쓰는 중일 수 있는 파일 (파이썬은 .tmp 를 바꿔 끼우지만 손 복사·다른 도구는 반쯤 쓴 파일을 보일 수 있다): 새 파일이 읽기·JSON·풀기에서 깨졌으면
		// 기억하지 않고 다음 감시에 다시 읽는다. 오래된 파일이거나 다른 까닭이면 거부를 기억한다 (시각이 바뀔 때까지 다시 읽지 않는다)
		const double AgeSeconds = (FDateTime::UtcNow() - NewestStamp).GetTotalSeconds();
		const bool bTorn = L.Reason == EcoV3Brain::EReject::File || L.Reason == EcoV3Brain::EReject::Json || L.Reason == EcoV3Brain::EReject::Decode;
		if (bTorn && FMath::Abs(AgeSeconds) < EcoV3Brain::kWatchYoungSeconds)
		{
			UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 폴더 감시: %s 를 아직 못 읽었다 (%s, %.1f 초 전 파일 — 쓰는 중일 수 있다). 다음 감시에 다시 읽는다"), *Newest,
				   EcoV3Brain::RejectName(L.Reason), AgeSeconds);
			return false;
		}
		WatchedFile = Newest;
		WatchedStamp = NewestStamp;
		LastWatchReject.File = Newest;
		LastWatchReject.Reason = L.Reason;
		LastWatchReject.Message = L.Message;
		++LastWatchReject.Serial;
		UE_LOG(LogEcoV3Brain, Warning, TEXT("[EcoV3Brain] 폴더 감시: %s 거부 (%s) — %s. 지금 두뇌 %s 그대로 (파일 시각이 바뀌면 다시 읽는다)"), *Newest,
			   EcoV3Brain::RejectName(L.Reason), *L.Message, *Active->Id);
		return false;
	}
	WatchedFile = Newest;
	WatchedStamp = NewestStamp;
	if (!WatchPlayId.IsEmpty() && L.Brain->bAdapt && !L.Brain->AdaptPlayId.IsEmpty() && L.Brain->AdaptPlayId != WatchPlayId)
	{
		// 앞 Play 의 스냅숏에서 배운 두뇌 (파이썬 판이 새 Play 시작 뒤에 끝났다): 그 환경은 이 Play 에 없다. 받지 않고, 시각이 바뀔 때까지 다시 보지 않는다
		LastWatchReject.File = Newest;
		LastWatchReject.Reason = EcoV3Brain::EReject::Play;
		LastWatchReject.Message = FString::Printf(TEXT("Play %s 의 스냅숏에서 배운 두뇌 — 지금 Play 는 %s"), *L.Brain->AdaptPlayId, *WatchPlayId);
		++LastWatchReject.Serial;
		UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 폴더 감시: %s 건너뜀 — %s. 지금 두뇌 %s 그대로"), *Newest, *LastWatchReject.Message, *Active->Id);
		return false;
	}
	if (L.Brain->WeightsSha256 == Active->WeightsSha256 && !Pending.IsValid())
	{
		UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 폴더 감시: %s 는 지금 두뇌와 같은 가중치 (%s) — 바꾸지 않는다"), *Newest, *L.Brain->Id);
		return false;
	}
	Queue(L.Brain.ToSharedRef(), FString::Printf(TEXT("폴더 감시 eco.V3Brain.WatchFolder %s"), *Folder));
	return true;
}

FString FEcoV3BrainRegistry::EffectiveStatusFile() const
{
#if !UE_BUILD_SHIPPING
	const FString File = EcoV3Brain::StatusFile();
	return File.IsEmpty() ? DefaultStatusFile : File;
#else
	return FString();
#endif
}

bool FEcoV3BrainRegistry::PollStatus(double NowSeconds)
{
	const FString File = EffectiveStatusFile();
	if (File.IsEmpty())
	{
		StatusPath.Empty();
		return false;
	}
	const FString Path = EcoV3BrainImpl::ProjectPath(File);
	if (Path == StatusPath && NowSeconds < NextStatusPoll)
	{
		return false;
	}
	NextStatusPoll = NowSeconds + EcoV3Brain::kStatusPollSeconds;
	if (Path != StatusPath)
	{
		LiveStatus = FEcoV3LiveStatus();   // 다른 파일 — 앞 파일의 상태를 들고 가지 않는다
	}
	StatusPath = Path;
	bStatusFileExists = FPaths::FileExists(Path);
	if (!bStatusFileExists)
	{
		LiveStatus = FEcoV3LiveStatus();
		bStatusReadOk = false;
		return true;
	}
	// 깨진 글자면 앞서 읽은 상태 그대로 (updated_unix 가 120 초를 넘으면 '응답 없음'이 된다)
	FString Text;
	FEcoV3LiveStatus S;
	bStatusReadOk = FFileHelper::LoadFileToString(Text, *Path) && EcoV3Brain::ParseLiveStatus(Text, S);
	if (bStatusReadOk)
	{
		S.Path = Path;
		LiveStatus = S;
	}
	return true;
}

FString FEcoV3BrainRegistry::GetLiveStatusText(double NowUnix) const
{
	return StatusPath.IsEmpty() ? FString() : EcoV3Brain::LiveStatusText(LiveStatus, bStatusFileExists, NowUnix);
}

void FEcoV3BrainRegistry::ResetForTest()
{
	Active = Builtin();
	ActiveWhy = TEXT("내장 (처음)");
	Pending.Reset();
	PendingWhy.Empty();
	PendingRollback.Reset();
	History.Reset();
	bCommitted = false;
	bLastCommitRollback = false;
	LastCommitWhy.Empty();
	++Generation;
	WatchedFile.Empty();
	WatchedStamp = FDateTime();
	NextWatchPoll = 0.0;
	PrimedFiles.Reset();
	DefaultWatchFolder.Empty();
	WatchPlayId.Empty();
	// 거부 Serial 은 되돌리지 않는다 (서브시스템이 알린 번호와 겹치지 않게)
	LastWatchReject.File.Empty();
	LastWatchReject.Reason = EcoV3Brain::EReject::None;
	LastWatchReject.Message.Empty();
	DefaultStatusFile.Empty();
	StatusPath.Empty();
	NextStatusPoll = 0.0;
	bStatusFileExists = false;
	bStatusReadOk = false;
	LiveStatus = FEcoV3LiveStatus();
}

// -----------------------------------------------------------------------------
// 콘솔 (개발 빌드)
// -----------------------------------------------------------------------------

#if !UE_BUILD_SHIPPING
namespace EcoV3BrainImpl
{
	bool RefuseClient(UWorld* World, FOutputDevice& Ar)
	{
		if (World && World->GetNetMode() == NM_Client)
		{
			Ar.Log(TEXT("[EcoV3Brain] 클라이언트는 두뇌를 돌리지 않는다 (서버·단독만) — 서버 또는 단독 실행의 콘솔에서 바꾼다"));
			return true;
		}
		return false;
	}

	void CmdLoad(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		if (RefuseClient(World, Ar))
		{
			return;
		}
		if (Args.IsEmpty())
		{
			Ar.Log(TEXT("[EcoV3Brain] 쓰기: eco.V3Brain.Load <파일|default|builtin> — default = 기본 두뇌 R7e, builtin = 내장 R1b-F, 파일은 절대 경로이거나 ")
					   TEXT("<프로젝트>/EcoBrains·Saved/EcoBrains 안 이름 (eco.V3Brain.List)"));
			return;
		}
		const FString Arg = FString::Join(Args, TEXT(" "));
		const FEcoV3BrainLoad L = FEcoV3BrainRegistry::LoadFile(Arg);
		if (!L.Ok())
		{
			Ar.Logf(TEXT("[EcoV3Brain] 거부 (%s): %s — 지금 두뇌 %s 그대로"), EcoV3Brain::RejectName(L.Reason), *L.Message,
					*FEcoV3BrainRegistry::Get().GetActive()->Id);
			UE_LOG(LogEcoV3Brain, Warning, TEXT("[EcoV3Brain] eco.V3Brain.Load %s 거부 (%s): %s"), *Arg, EcoV3Brain::RejectName(L.Reason), *L.Message);
			return;
		}
		FEcoV3BrainRegistry::Get().Queue(L.Brain.ToSharedRef(), FString::Printf(TEXT("콘솔 eco.V3Brain.Load %s"), *Arg));
		if (L.Brain->bBuiltin || L.Brain->bDefault)
		{
			Ar.Logf(TEXT("[EcoV3Brain] %s %s 로 — 다음 결정 스텝 경계에서 바뀐다 (통합 v3 Play 중이 아니면 Play 를 시작할 때)"), *L.Brain->OriginText(), *L.Brain->Id);
		}
		else
		{
			Ar.Logf(TEXT("[EcoV3Brain] 검사 통과: %s | 골든 %d 사례 최대 로짓 오차 %.2e (허용 %.0e) | 학습 %s — 다음 결정 스텝 경계에서 바뀐다 (통합 v3 Play 중이 아니면 Play 를 시작할 때)"),
					*L.Brain->Describe(), L.Brain->GoldenCount, L.Brain->GoldenMaxError, L.Brain->GoldenTolerance, *L.Brain->TrainWorld);
		}
	}

	void PrintBrain(FOutputDevice& Ar, const TCHAR* Label, const FEcoV3Brain& B)
	{
		Ar.Logf(TEXT("[EcoV3Brain] %s: %s"), Label, *B.Describe());
		Ar.Logf(TEXT("[EcoV3Brain]   모델 %s (%s) · zip sha256 %s · 가중치 sha256 %s · 계약 0x%016llx (관측 %d · 마스크 판 %d%s)"), *B.ModelName,
				B.ModelPath.IsEmpty() ? TEXT("-") : *B.ModelPath, B.ModelSha256.IsEmpty() ? TEXT("-") : *B.ModelSha256.Left(16), *B.WeightsSha256.Left(16),
				static_cast<unsigned long long>(B.ContractHash), B.ObsDim, B.MaskVersion,
				B.bRoute() ? TEXT(" — 두 길 두뇌: 도주 반사 중 RUN·SHELTER 를 고른다") : TEXT(""));
		Ar.Logf(TEXT("[EcoV3Brain]   학습 %s%s%s"), *B.TrainWorld, B.TrainConfig.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" · 설정 %s"), *B.TrainConfig),
				B.TrainDigest.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *B.TrainDigest));
		if (!B.bBuiltin)
		{
			Ar.Logf(TEXT("[EcoV3Brain]   검사 통과: 골든 %d 사례 (세계 %s) 최대 로짓 오차 %.2e ≤ %.0e · %s"), B.GoldenCount, *B.GoldenWorld, B.GoldenMaxError,
					B.GoldenTolerance,
					B.bDefault ? *FString::Printf(TEXT("빌드에 넣은 두뇌 파일 %s (PolicyBrainV3Default.h, 바이트 sha256 %s…)"),
												  UTF8_TO_TCHAR(EcoPolicyV3Default::kFileName), *FString(UTF8_TO_TCHAR(EcoPolicyV3Default::kFileSha256)).Left(16))
							   : *FString::Printf(TEXT("파일 %s"), *B.SourceFile));
		}
		if (B.AdaptRound > 0 || !B.AdaptRun.IsEmpty())
		{
			Ar.Logf(TEXT("[EcoV3Brain]   적응 고리: 판 %d · 시도 %d · 실행 %s · 스냅숏 %s · 환경 %s · 관문 %s"), B.AdaptRound, B.AdaptAttempt, *B.AdaptRun, *B.AdaptSnapshot,
					*B.AdaptEnv, *B.AdaptGate);
		}
	}

	void CmdInfo(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		const FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
		PrintBrain(Ar, TEXT("지금 두뇌"), *Reg.GetActive());
		if (const FEcoV3BrainPtr P = Reg.GetPending())
		{
			PrintBrain(Ar, Reg.IsPendingRollback() ? TEXT("대기 두뇌 (되돌림, 다음 결정 스텝 경계에서)") : TEXT("대기 두뇌 (다음 결정 스텝 경계에서)"), *P);
			Ar.Logf(TEXT("[EcoV3Brain]   까닭: %s"), *Reg.GetPendingWhy());
		}
		Ar.Logf(TEXT("[EcoV3Brain] 바꾼 횟수 %d · 세대 %u · 기본 %s · 내장 %s · 서버·단독만 (이 월드 %s)"), Reg.GetSwapCount(), Reg.GetGeneration(),
				*FEcoV3BrainRegistry::Default()->Id, *FEcoV3BrainRegistry::Builtin()->Id,
				!World ? TEXT("없음") : World->GetNetMode() == NM_Client ? TEXT("클라이언트 — 두뇌를 돌리지 않음") : TEXT("서버·단독"));
		const float At = EcoV3Brain::SwapAtSeconds();
		const FString Watch = Reg.EffectiveWatchFolder();
		Ar.Logf(TEXT("[EcoV3Brain] 시작 두뇌 eco.V3Brain.Startup '%s'%s · 예정 바꾸기 %s · 폴더 감시 %s%s"), *EcoV3Brain::StartupFile(),
				EcoV3Brain::StartupFile().IsEmpty() ? (Reg.HasCommitted() ? TEXT(" (빔 — 다음 Play 는 지금 두뇌 그대로, 적응 고리 Play 는 기본)") : TEXT(" (빔 — 다음 Play 는 기본 두뇌)"))
													: TEXT(""),
				At >= 0.0f ? *FString::Printf(TEXT("%.1f초에 '%s'"), At, *EcoV3Brain::SwapFile()) : TEXT("끔"), Watch.IsEmpty() ? TEXT("끔") : *Watch,
				!Watch.IsEmpty() && EcoV3Brain::WatchFolder().IsEmpty() ? TEXT(" (적응 고리 기본)") : TEXT(""));
		Ar.Logf(TEXT("[EcoV3Brain] 되돌리기 쌓개 %d (eco.V3Brain.History·Rollback) · 지금 두뇌가 된 까닭: %s"), Reg.GetHistory().Num(), *Reg.GetActiveWhy());
		const FString Status = Reg.EffectiveStatusFile();
		Ar.Logf(TEXT("[EcoV3Brain] 적응 고리 상태 파일 %s%s"), Status.IsEmpty() ? TEXT("끔") : *Status,
				Status.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" — %s"), *Reg.GetLiveStatusText(EcoV3Brain::NowUnixSeconds())));
		Ar.Logf(TEXT("[EcoV3Brain] 찾는 폴더: %s"), *FString::Join(FEcoV3BrainRegistry::SearchFolders(), TEXT(" · ")));
	}

	void CmdRollback(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		if (RefuseClient(World, Ar))
		{
			return;
		}
		FString Msg;
		const bool bQueued = FEcoV3BrainRegistry::Get().Rollback(TEXT("콘솔 eco.V3Brain.Rollback"), &Msg);
		Ar.Logf(TEXT("[EcoV3Brain] %s%s"), *Msg, bQueued ? TEXT(" (통합 v3 Play 중이 아니면 Play 를 시작할 때)") : TEXT(""));
	}

	void CmdHistory(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		const FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
		const TArray<FEcoV3BrainHistoryEntry>& H = Reg.GetHistory();
		Ar.Logf(TEXT("[EcoV3Brain] 지금: %s — 까닭: %s"), *Reg.GetActive()->Describe(), *Reg.GetActiveWhy());
		if (const FEcoV3BrainPtr P = Reg.GetPending())
		{
			Ar.Logf(TEXT("[EcoV3Brain] 대기%s: %s — 까닭: %s"), Reg.IsPendingRollback() ? TEXT(" (되돌림)") : TEXT(""), *P->Describe(), *Reg.GetPendingWhy());
		}
		Ar.Logf(TEXT("[EcoV3Brain] 되돌리기 쌓개 %d / %d (새 것부터 — 1 이 다음 eco.V3Brain.Rollback)"), H.Num(), EcoV3Brain::kHistoryMax);
		for (int32 i = H.Num() - 1, n = 1; i >= 0; --i, ++n)
		{
			Ar.Logf(TEXT("[EcoV3Brain]   %d. %s — 들어온 까닭: %s · 바뀐 까닭: %s"), n, *H[i].Brain->Describe(), *H[i].Why, *H[i].ReplacedWhy);
		}
	}

	void CmdList(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		const TArray<FString> Files = FEcoV3BrainRegistry::ListFiles();
		Ar.Logf(TEXT("[EcoV3Brain] 두뇌 파일 %d (찾는 폴더 %s) · 기본(default) = %s · 내장(builtin) = %s · 지금 = %s"), Files.Num(),
				*FString::Join(FEcoV3BrainRegistry::SearchFolders(), TEXT(" · ")), *FEcoV3BrainRegistry::Default()->Describe(),
				*FEcoV3BrainRegistry::Builtin()->Id, *FEcoV3BrainRegistry::Get().GetActive()->Id);
		for (const FString& F : Files)
		{
			const FEcoV3BrainLoad L = FEcoV3BrainRegistry::LoadFile(F);
			if (L.Ok())
			{
				Ar.Logf(TEXT("[EcoV3Brain]   %s — %s · 학습 %s"), *FPaths::GetBaseFilename(F), *L.Brain->Describe(), *L.Brain->TrainWorld);
			}
			else
			{
				Ar.Logf(TEXT("[EcoV3Brain]   %s — 거부 (%s): %s"), *FPaths::GetBaseFilename(F), EcoV3Brain::RejectName(L.Reason), *L.Message);
			}
		}
	}

	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdLoadReg(
		TEXT("eco.V3Brain.Load"),
		TEXT("사슴 두뇌 바꾸기: eco.V3Brain.Load <파일|default|builtin> (default = 기본 두뇌 R7e, builtin = 내장 R1b-F). 검사(계약·차원·마스크·sha256·골든)를 통과하면 ")
			TEXT("다음 결정 스텝 경계에서 바뀐다 — Play 를 다시 시작하지 않는다. 서버·단독만 (EcoV3Brain.h)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdLoad));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdInfoReg(
		TEXT("eco.V3Brain.Info"), TEXT("지금 사슴 두뇌·대기 두뇌·바꾼 횟수·출처 (EcoV3Brain.h)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdInfo));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdListReg(
		TEXT("eco.V3Brain.List"), TEXT("찾는 폴더(<프로젝트>/EcoBrains·Saved/EcoBrains)의 두뇌 파일과 검사 결과 (EcoV3Brain.h)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdList));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdRollbackReg(
		TEXT("eco.V3Brain.Rollback"),
		TEXT("앞 사슴 두뇌로 되돌리기: 되돌리기 쌓개(앞 두뇌 16 개)의 맨 위를 줄에 넣는다 — 다음 결정 스텝 경계에서 바뀐다(Play 그대로). 되돌린 두뇌는 쌓지 않는다 ")
			TEXT("(두 번 = 둘 앞으로). 서버·단독만 (EcoV3Brain.h)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdRollback));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdHistoryReg(
		TEXT("eco.V3Brain.History"), TEXT("지금 두뇌와 되돌리기 쌓개(새 것부터, 들어온 까닭·바뀐 까닭) (EcoV3Brain.h)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdHistory));
}
#endif

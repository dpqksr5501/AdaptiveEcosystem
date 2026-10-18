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

DEFINE_LOG_CATEGORY(LogEcoV3Brain);

static_assert(PLATFORM_LITTLE_ENDIAN, "두뇌 파일 가중치는 float32 리틀 엔디언 바이트다 — 큰 엔디언 플랫폼은 바이트를 뒤집어 읽어야 한다");
// 관측 21 계약은 내장 관측 18·판 2 계약(R1b) 뒤에 세 칸을 붙인 것이다 — 내장 계약이 바뀌면 이 표를 함께 고친다
static_assert(EcoPolicyV3::kContractHash == EcoPolicyV3::kContractHashObs18Mask2 && EcoPolicyV3::kObsDim == EcoObservationV3::kObsDim
				  && EcoPolicyV3::kMaskVersion == 2,
			  "관측 21 장애물 계약은 내장 관측 18·마스크 판 2 계약 위에 있다");
static_assert(EcoObservationV3::kObsDimObstacle <= EcoPolicyV3::kMaxObsDim, "관측 21 이 망 입력 상한을 넘는다");

namespace EcoV3BrainImpl
{
	using namespace EcoV3Brain;
	namespace P3 = EcoPolicyV3;

	const TCHAR* const kBehaviorKo[P3::kNumBehaviors] = {TEXT("먹기"), TEXT("도망"), TEXT("숨기"), TEXT("얼기"), TEXT("잠")};

	// 받는 계약 (EcoV3Brain.h 머리 주석 '받는 계약'). 0 = 내장 계약, 1 = R5 장애물 관측 21
	const FContract kContracts[kNumContracts] = {
		{P3::kContractHash, P3::kObsDim, P3::kMaskVersion, 0, nullptr, TEXT("관측 18 · 마스크 판 2 (내장 R1b 와 같은 계약)")},
		{P3::kContractHashObs21Mask2, EcoObservationV3::kObsDimObstacle, 2, EcoObservationV3::kNumObstacleObs, EcoObservationV3::kObstacleObsNames,
		 TEXT("관측 21 · 마스크 판 2 (R5 장애물 관측 — 18 칸 + escape_room·obstacle_near·threat_hidden)")},
	};

#if !UE_BUILD_SHIPPING
	TAutoConsoleVariable<FString> CVarStartup(
		TEXT("eco.V3Brain.Startup"), TEXT(""),
		TEXT("통합 v3 Play 를 시작할 때 불러올 사슴 두뇌 파일 (EcoV3Brain.h). 빈 값 = 지금 두뇌 그대로(처음은 내장 R1b). 'builtin' = 내장. 명령줄 -EcoV3Brain= 은 시작값."),
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
			TEXT("경계에서 바꾼다. 명령줄 -EcoV3BrainWatch= 은 시작값."),
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

FString FEcoV3Brain::Describe() const
{
	return FString::Printf(TEXT("%s (%s, 허용 %s%s)"), *Id,
						   bBuiltin ? TEXT("내장 PolicyWeightsV3.h") : *FString::Printf(TEXT("파일 %s"), *FPaths::GetCleanFilename(SourceFile)),
						   *EcoV3Brain::AllowedText(Allowed), ObsDim > EcoPolicyV3::kObsDim ? *FString::Printf(TEXT(", 관측 %d 장애물"), ObsDim) : TEXT(""));
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
		B->WeightsSha256 = EcoV3Brain::WeightsSha256(B->Net);
		B->Id = FString::Printf(TEXT("%s@%s"), *B->ModelName, *B->WeightsSha256.Left(8));
		B->ModelSha256 = FString::Printf(TEXT("%016llx…"), static_cast<unsigned long long>(P3::kModelDigest));
		B->TrainWorld = TEXT("R1b (빌드에 들어간 게임 두뇌 — 통합 모드는 얼기를 세계가 막아 R1b-F)");
		for (int32 b = 0; b < P3::kNumBehaviors; ++b)
		{
			B->Allowed[b] = P3::kAllowedMask[b];
		}
		return FEcoV3BrainRef(B);
	}();
	return Brain;
}

FEcoV3BrainLoad FEcoV3BrainRegistry::Parse(const FString& JsonText, const FString& Source)
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
		return Fail(EReject::Contract, FString::Printf(TEXT("계약 해시 %s 가 이 빌드가 받는 0x%016llx (관측 18)·0x%016llx (관측 21 장애물) 가 아니다 (관측·마스크 계약이 다른 모델 — C++ 관측 코드를 함께 바꿔야 한다)"),
													 *HashText, static_cast<unsigned long long>(Contract(0).Hash), static_cast<unsigned long long>(Contract(1).Hash)));
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

	FEcoV3BrainLoad L;
	L.Path = Source;
	L.Brain = B;
	return L;
}

bool FEcoV3BrainRegistry::IsBuiltinName(const FString& Name)
{
	const FString N = Name.TrimStartAndEnd();
	return N.Equals(TEXT("builtin"), ESearchCase::IgnoreCase) || N == TEXT("내장");
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

FEcoV3BrainRegistry::FEcoV3BrainRegistry()
	: Active(Builtin())
{
}

FEcoV3BrainRegistry& FEcoV3BrainRegistry::Get()
{
	static FEcoV3BrainRegistry Registry;
	return Registry;
}

void FEcoV3BrainRegistry::Queue(const FEcoV3BrainRef& Brain, const FString& Why)
{
	check(IsInGameThread());
	if (Pending.IsValid())
	{
		UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 대기 두뇌 %s 를 버리고 새 대기 두뇌로 바꾼다"), *Pending->Id);
	}
	Pending = Brain;
	PendingWhy = Why;
	UE_LOG(LogEcoV3Brain, Log, TEXT("[EcoV3Brain] 대기: %s — 까닭: %s | 다음 결정 스텝 경계에서 바뀐다 (지금 %s)"), *Brain->Describe(), *Why, *Active->Id);
}

bool FEcoV3BrainRegistry::CommitPending(FEcoV3BrainPtr* OutFrom, FString* OutWhy)
{
	if (!Pending.IsValid())
	{
		return false;
	}
	if (OutFrom)
	{
		*OutFrom = Active;
	}
	if (OutWhy)
	{
		*OutWhy = PendingWhy;
	}
	Active = Pending.ToSharedRef();
	Pending.Reset();
	PendingWhy.Empty();
	++Generation;
	++SwapCount;
	return true;
}

bool FEcoV3BrainRegistry::PollWatch(double NowSeconds)
{
	const FString Folder = EcoV3Brain::WatchFolder();
	if (Folder.IsEmpty() || NowSeconds < NextWatchPoll)
	{
		return false;
	}
	NextWatchPoll = NowSeconds + EcoV3Brain::kWatchPollSeconds;
	const FString Dir = FPaths::IsRelative(Folder) ? FPaths::ConvertRelativePathToFull(FPaths::ProjectDir() / Folder) : Folder;
	TArray<FString> Names;
	IFileManager::Get().FindFiles(Names, *(Dir / TEXT("*.json")), true, false);
	FString Newest;
	FDateTime NewestStamp = FDateTime::MinValue();
	for (const FString& N : Names)
	{
		const FString P = Dir / N;
		const FDateTime S = IFileManager::Get().GetTimeStamp(*P);
		if (S > NewestStamp || (S == NewestStamp && P > Newest))
		{
			Newest = P;
			NewestStamp = S;
		}
	}
	if (Newest.IsEmpty() || (Newest == WatchedFile && NewestStamp == WatchedStamp))
	{
		return false;
	}
	WatchedFile = Newest;
	WatchedStamp = NewestStamp;
	const FEcoV3BrainLoad L = LoadFile(Newest);
	if (!L.Ok())
	{
		UE_LOG(LogEcoV3Brain, Warning, TEXT("[EcoV3Brain] 폴더 감시: %s 거부 (%s) — %s. 지금 두뇌 %s 그대로 (파일 시각이 바뀌면 다시 읽는다)"), *Newest,
			   EcoV3Brain::RejectName(L.Reason), *L.Message, *Active->Id);
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

void FEcoV3BrainRegistry::ResetForTest()
{
	Active = Builtin();
	Pending.Reset();
	PendingWhy.Empty();
	++Generation;
	WatchedFile.Empty();
	WatchedStamp = FDateTime();
	NextWatchPoll = 0.0;
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
			Ar.Log(TEXT("[EcoV3Brain] 쓰기: eco.V3Brain.Load <파일|builtin> — 파일은 절대 경로이거나 <프로젝트>/EcoBrains·Saved/EcoBrains 안 이름 (eco.V3Brain.List)"));
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
		if (L.Brain->bBuiltin)
		{
			Ar.Logf(TEXT("[EcoV3Brain] 내장 두뇌 %s 로 — 다음 결정 스텝 경계에서 바뀐다 (통합 v3 Play 중이 아니면 Play 를 시작할 때)"), *L.Brain->Id);
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
		Ar.Logf(TEXT("[EcoV3Brain]   모델 %s (%s) · zip sha256 %s · 가중치 sha256 %s · 계약 0x%016llx (관측 %d)"), *B.ModelName,
				B.ModelPath.IsEmpty() ? TEXT("-") : *B.ModelPath, B.ModelSha256.IsEmpty() ? TEXT("-") : *B.ModelSha256.Left(16), *B.WeightsSha256.Left(16),
				static_cast<unsigned long long>(B.ContractHash), B.ObsDim);
		Ar.Logf(TEXT("[EcoV3Brain]   학습 %s%s%s"), *B.TrainWorld, B.TrainConfig.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" · 설정 %s"), *B.TrainConfig),
				B.TrainDigest.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" (%s)"), *B.TrainDigest));
		if (!B.bBuiltin)
		{
			Ar.Logf(TEXT("[EcoV3Brain]   검사 통과: 골든 %d 사례 (세계 %s) 최대 로짓 오차 %.2e ≤ %.0e · 파일 %s"), B.GoldenCount, *B.GoldenWorld, B.GoldenMaxError,
					B.GoldenTolerance, *B.SourceFile);
		}
	}

	void CmdInfo(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		const FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
		PrintBrain(Ar, TEXT("지금 두뇌"), *Reg.GetActive());
		if (const FEcoV3BrainPtr P = Reg.GetPending())
		{
			PrintBrain(Ar, TEXT("대기 두뇌 (다음 결정 스텝 경계에서)"), *P);
			Ar.Logf(TEXT("[EcoV3Brain]   까닭: %s"), *Reg.GetPendingWhy());
		}
		Ar.Logf(TEXT("[EcoV3Brain] 바꾼 횟수 %d · 세대 %u · 내장 %s · 서버·단독만 (이 월드 %s)"), Reg.GetSwapCount(), Reg.GetGeneration(), *FEcoV3BrainRegistry::Builtin()->Id,
				!World ? TEXT("없음") : World->GetNetMode() == NM_Client ? TEXT("클라이언트 — 두뇌를 돌리지 않음") : TEXT("서버·단독"));
		const float At = EcoV3Brain::SwapAtSeconds();
		Ar.Logf(TEXT("[EcoV3Brain] 시작 두뇌 eco.V3Brain.Startup '%s' · 예정 바꾸기 %s · 폴더 감시 %s"), *EcoV3Brain::StartupFile(),
				At >= 0.0f ? *FString::Printf(TEXT("%.1f초에 '%s'"), At, *EcoV3Brain::SwapFile()) : TEXT("끔"),
				EcoV3Brain::WatchFolder().IsEmpty() ? TEXT("끔") : *EcoV3Brain::WatchFolder());
		Ar.Logf(TEXT("[EcoV3Brain] 찾는 폴더: %s"), *FString::Join(FEcoV3BrainRegistry::SearchFolders(), TEXT(" · ")));
	}

	void CmdList(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		const TArray<FString> Files = FEcoV3BrainRegistry::ListFiles();
		Ar.Logf(TEXT("[EcoV3Brain] 두뇌 파일 %d (찾는 폴더 %s) · 내장 = %s · 지금 = %s"), Files.Num(), *FString::Join(FEcoV3BrainRegistry::SearchFolders(), TEXT(" · ")),
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
		TEXT("사슴 두뇌 바꾸기: eco.V3Brain.Load <파일|builtin>. 검사(계약·차원·마스크·sha256·골든)를 통과하면 다음 결정 스텝 경계에서 바뀐다 — Play 를 다시 시작하지 않는다. ")
			TEXT("서버·단독만 (EcoV3Brain.h)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdLoad));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdInfoReg(
		TEXT("eco.V3Brain.Info"), TEXT("지금 사슴 두뇌·대기 두뇌·바꾼 횟수·출처 (EcoV3Brain.h)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdInfo));
	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdListReg(
		TEXT("eco.V3Brain.List"), TEXT("찾는 폴더(<프로젝트>/EcoBrains·Saved/EcoBrains)의 두뇌 파일과 검사 결과 (EcoV3Brain.h)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdList));
}
#endif

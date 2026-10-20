// 실행 중 가중치 로더(EcoV3Brain.h — 10-18 두뇌 바꾸기)의 자동화 시험. Mass 에서 바꾸는 시험은 EcoPolicyV3IntegratedTest.cpp Integrated.BrainSwap.
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Brain"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 묶음:
//   Brain.Sha256       SHA-256 FIPS 예제 넷, 내장 가중치 바이트 지문 = 파이썬이 쓴 R1b 두뇌 파일의 weights_sha256 (같은 모델)
//   Brain.LoadValid    저장소의 두뇌 파일 둘(<프로젝트>/EcoBrains — herbivore_rl/export_weights_v3.py --brain-file): 검사 통과, C++ 순전파가 파일 속 파이썬 골든과
//                      같다(로짓 허용 오차·행동), R1b 파일은 내장 가중치와 비트 단위로 같고 내장 골든(PolicyGoldenVectorsV3.h)에서 내장과 같은 로짓,
//                      R4 파일은 허용 칸이 먹기·도망·숨기이고 내장 골든에서 다른 결정을 낸다
//   Brain.LoadObs21    R5 관측 21 두뇌 파일(R1b-F + 장애물 세 칸 입력 열 0 — herbivore_rl/results/v3/r5/zero_extend.py): 검사 통과, 망 21 칸, 첫 층 = 내장 18 열 + 0 열
//                      (비트 단위), 내장 골든 × 아무 세 칸 = 내장 로짓, 두 계약 말고는 거부·계약과 칸 수·이름·마스크·층·골든이 어긋나면 거부 (11 가지 + R4 에 21 해시)
//   Brain.RejectBad    깨진 파일 24 가지(JSON·없는 파일·형식·판·계약 해시·차원·이름·마스크 판·문턱·허용 칸·층 모양·base64·NaN·sha256·바꾼 가중치·전치·
//                      골든 허용 오차·사례 수·행동)를 까닭과 함께 거부하고, 지금 두뇌는 그대로다
//   Brain.Registry     줄·경계·세대(Queue → CommitPending), 'builtin', 이름 찾기(.json 빼도), 목록, 콘솔 eco.V3Brain.Load·Info·List, 폴더 감시
//                      (새 파일만, 2 초 주기, 거부 파일은 시각이 바뀔 때까지 다시 읽지 않음)
//   Brain.History      (10-21 실시간 두뇌 교체) 되돌리기 쌓개: 바꿀 때마다 나가는 두뇌를 쌓고 되돌림은 쌓지 않음, 경계 전 두 번 = 둘 앞, 대기 되돌림을
//                      덮으면 쌓개 복구(경계 전 두 번 되돌렸어도 꺼낸 칸 둘 다), 같은 id 는 쌓지 않음, 상한 16, 콘솔 eco.V3Brain.Rollback·History, ResetForTest
//   Brain.Adapt        두뇌 파일 'adapt' 블록(판·시도·실행·스냅숏·환경·관문) 읽기, 없거나 깨져도 통과(판 0), 설명 ', 판 n'·판 글자·짧은 id(판 12 는 'live_r12…')
//   Brain.WatchLive    적응 고리 기본 감시 폴더(콘솔 변수가 이긴다), PrimeWatch(그때 있던 파일은 — 더 새 파일이 지워져 다시 가장 새 파일이 돼도 — 읽지 않고
//                      뒤에 나타난 파일만), 오래된 깨진 파일은
//                      거부 번호 + 1, 쓰는 중인 새 깨진 파일(3 초 안)은 기억하지 않고 같은 (경로, 시각) 을 다시 읽는다
//   Brain.LiveStatus   적응 고리 상태 파일(eco_v3_live_status 판 1) 읽기·화면 글자(120 초 안 메시지·응답 없음·파이썬 감시 없음)·2 초 주기·깨지면 앞 상태

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoObservationV3.h"
#include "../EcoSha256.h"
#include "../EcoV3Brain.h"
#include "../PolicyGoldenVectorsV3.h"
#include "Dom/JsonObject.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/Base64.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

#include <limits>

namespace EcoV3BrainTestImpl
{
	namespace P3 = EcoPolicyV3;
	using EcoV3Brain::EReject;

	const TCHAR* const kR1bFile = TEXT("v3_r1_g995_s3_20m");
	const TCHAR* const kR4File = TEXT("v3_r4_g995_s0_20m");
	const TCHAR* const kZeroObs21File = TEXT("v3_r1_g995_s3_obs21zero");   // R5 관측 21 = R1b-F + 새 세 열 0 (10-19)

	FString Sha(const char* Text)
	{
		char Hex[65];
		EcoSha256::HashHex(Text, std::strlen(Text), Hex);
		return FString(ANSI_TO_TCHAR(Hex));
	}

	bool ReadBrainText(FAutomationTestBase& T, const TCHAR* Name, FString& Out)
	{
		const FString Path = FEcoV3BrainRegistry::Resolve(Name);
		return T.TestFalse(FString::Printf(TEXT("%s 두뇌 파일을 찾는다"), Name), Path.IsEmpty())
			&& T.TestTrue(FString::Printf(TEXT("%s 읽기"), Name), FFileHelper::LoadFileToString(Out, *Path));
	}

	TSharedPtr<FJsonObject> ToJson(const FString& Text)
	{
		TSharedPtr<FJsonObject> Root;
		FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
		return Root;
	}

	FString ToText(const TSharedPtr<FJsonObject>& Root)
	{
		FString Out;
		const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> W = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out);
		FJsonSerializer::Serialize(Root.ToSharedRef(), W);
		return Out;
	}

	TArray<float> DecodeFloats(const FString& B64)
	{
		TArray<uint8> Bytes;
		FBase64::Decode(B64, Bytes);
		TArray<float> F;
		F.SetNumUninitialized(Bytes.Num() / 4);
		FMemory::Memcpy(F.GetData(), Bytes.GetData(), F.Num() * 4);
		return F;
	}

	FString EncodeFloats(const TArray<float>& F)
	{
		return FBase64::Encode(reinterpret_cast<const uint8*>(F.GetData()), static_cast<uint32>(F.Num() * 4));
	}

	TSharedPtr<FJsonObject> Layer(const TSharedPtr<FJsonObject>& Root, int32 k)
	{
		return Root->GetArrayField(TEXT("layers"))[k]->AsObject();
	}

	/** 세 층 가중치·편향 (시험에서 고친다). */
	struct FLayers
	{
		TArray<float> W[3];
		TArray<float> B[3];
	};

	/** 층 가중치를 고치고 weights_sha256 도 새 바이트로 맞춘다 (sha 검사는 통과하고 골든에서만 걸리게). */
	void EditWeightsKeepSha(const TSharedPtr<FJsonObject>& Root, TFunctionRef<void(FLayers&)> Edit)
	{
		FLayers Ly;
		for (int32 k = 0; k < 3; ++k)
		{
			Ly.W[k] = DecodeFloats(Layer(Root, k)->GetStringField(TEXT("w_f32le_b64")));
			Ly.B[k] = DecodeFloats(Layer(Root, k)->GetStringField(TEXT("b_f32le_b64")));
		}
		Edit(Ly);
		EcoSha256::FState S;
		for (int32 k = 0; k < 3; ++k)
		{
			Layer(Root, k)->SetStringField(TEXT("w_f32le_b64"), EncodeFloats(Ly.W[k]));
			Layer(Root, k)->SetStringField(TEXT("b_f32le_b64"), EncodeFloats(Ly.B[k]));
			EcoSha256::Update(S, Ly.W[k].GetData(), Ly.W[k].Num() * 4);
			EcoSha256::Update(S, Ly.B[k].GetData(), Ly.B[k].Num() * 4);
		}
		uint8 D[32];
		EcoSha256::Final(S, D);
		char Hex[65];
		EcoSha256::ToHex(D, Hex);
		Root->SetStringField(TEXT("weights_sha256"), FString(ANSI_TO_TCHAR(Hex)));
	}

	TArray<TSharedPtr<FJsonValue>> Strings(std::initializer_list<const TCHAR*> L)
	{
		TArray<TSharedPtr<FJsonValue>> Out;
		for (const TCHAR* S : L)
		{
			Out.Add(MakeShared<FJsonValueString>(S));
		}
		return Out;
	}

	TArray<TSharedPtr<FJsonValue>> Numbers(std::initializer_list<double> L)
	{
		TArray<TSharedPtr<FJsonValue>> Out;
		for (const double V : L)
		{
			Out.Add(MakeShared<FJsonValueNumber>(V));
		}
		return Out;
	}

	TSharedPtr<FJsonObject> Case(const TSharedPtr<FJsonObject>& Root, int32 n)
	{
		return Root->GetObjectField(TEXT("golden"))->GetArrayField(TEXT("cases"))[n]->AsObject();
	}

	/** 시험이 끝나면 저장소를 내장 두뇌로 되돌린다 (프로세스에 하나라 다른 시험·Play 에 남지 않게). */
	struct FRegistryGuard
	{
		FRegistryGuard() { FEcoV3BrainRegistry::Get().ResetForTest(); }
		~FRegistryGuard() { FEcoV3BrainRegistry::Get().ResetForTest(); }
	};
}

using namespace EcoV3BrainTestImpl;

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainSha256Test, "AdaptiveEcosystem.Policy.V3.Brain.Sha256",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainSha256Test::RunTest(const FString& Parameters)
{
	// FIPS 180-4 예제 (NIST CSRC 예제 값)
	TestEqual(TEXT("sha256('abc')"), Sha("abc"), FString(TEXT("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")));
	TestEqual(TEXT("sha256('')"), Sha(""), FString(TEXT("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")));
	TestEqual(TEXT("sha256(448 비트 문장)"), Sha("abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
			  FString(TEXT("248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1")));
	{
		// 백만 'a' 를 나눠 넣는다 (블록 경계를 가로지르는 Update)
		EcoSha256::FState S;
		const TArray<uint8> Chunk = [] { TArray<uint8> A; A.Init('a', 1001); return A; }();
		for (int32 i = 0; i < 1000; ++i)
		{
			EcoSha256::Update(S, Chunk.GetData(), i % 2 == 0 ? 999 : 1001);
		}
		uint8 D[32];
		EcoSha256::Final(S, D);
		char Hex[65];
		EcoSha256::ToHex(D, Hex);
		TestEqual(TEXT("sha256(백만 'a', 999·1001 바이트 조각)"), FString(ANSI_TO_TCHAR(Hex)),
				  FString(TEXT("cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0")));
	}

	// 내장 가중치 바이트 지문 = 파이썬 export_weights_v3.weights_bytes 의 sha256 (같은 R1b s3 모델의 두뇌 파일)
	FString Text;
	if (!ReadBrainText(*this, kR1bFile, Text))
	{
		return false;
	}
	const TSharedPtr<FJsonObject> Root = ToJson(Text);
	if (!TestTrue(TEXT("R1b 두뇌 파일 JSON"), Root.IsValid()))
	{
		return false;
	}
	const FEcoV3BrainRef B = FEcoV3BrainRegistry::Builtin();
	TestEqual(TEXT("내장 가중치 sha256 = 파이썬 weights_sha256"), B->WeightsSha256, Root->GetStringField(TEXT("weights_sha256")));
	TestEqual(TEXT("내장 두뇌 id = 파이썬 id (모델 이름@지문 앞 8)"), B->Id, Root->GetStringField(TEXT("id")));
	TestTrue(TEXT("내장 두뇌 표시"), B->bBuiltin);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainLoadValidTest, "AdaptiveEcosystem.Policy.V3.Brain.LoadValid",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainLoadValidTest::RunTest(const FString& Parameters)
{
	namespace G = EcoPolicyV3::Golden;
	const FRegistryGuard Guard;
	const FEcoV3BrainLoad R1b = FEcoV3BrainRegistry::LoadFile(kR1bFile);
	const FEcoV3BrainLoad R4 = FEcoV3BrainRegistry::LoadFile(kR4File);
	if (!TestTrue(FString::Printf(TEXT("R1b 파일 검사 통과 (%s: %s)"), EcoV3Brain::RejectName(R1b.Reason), *R1b.Message), R1b.Ok())
		|| !TestTrue(FString::Printf(TEXT("R4 파일 검사 통과 (%s: %s)"), EcoV3Brain::RejectName(R4.Reason), *R4.Message), R4.Ok()))
	{
		return false;
	}
	for (const FEcoV3BrainLoad* L : {&R1b, &R4})
	{
		const FEcoV3Brain& B = *L->Brain;
		TestFalse(TEXT("파일 두뇌"), B.bBuiltin);
		TestTrue(TEXT("골든 8 사례 이상"), B.GoldenCount >= EcoV3Brain::kMinGolden);
		TestTrue(TEXT("골든 최대 로짓 오차 ≤ 허용 오차 ≤ 1e-3"), B.GoldenMaxError <= B.GoldenTolerance && B.GoldenTolerance <= EcoV3Brain::kMaxLogitTolerance);
		TestEqual(TEXT("id = 모델 이름@가중치 sha256 앞 8"), B.Id, FString::Printf(TEXT("%s@%s"), *B.ModelName, *B.WeightsSha256.Left(8)));
		TestEqual(TEXT("망 = 관측 18"), B.Net.ObsDim, P3::kObsDim);
		TestTrue(TEXT("망이 두뇌 자기 배열을 가리킨다"), B.Net.W0 == B.Layer0Weight.GetData() && B.Net.B2 == B.Layer2Bias.GetData());
		TestFalse(TEXT("학습 세계 이름"), B.TrainWorld.IsEmpty());
		AddInfo(FString::Printf(TEXT("%s | 골든 %d 최대 오차 %.3e (허용 %.0e) | 학습 %s"), *B.Describe(), B.GoldenCount, B.GoldenMaxError, B.GoldenTolerance, *B.TrainWorld));
	}

	// C++ 순전파 = 파일 속 파이썬 골든 (로더가 이미 본 것을 시험이 따로 다시 센다)
	for (const TCHAR* Name : {kR1bFile, kR4File})
	{
		FString Text;
		if (!ReadBrainText(*this, Name, Text))
		{
			return false;
		}
		const TSharedPtr<FJsonObject> Root = ToJson(Text);
		const FEcoV3BrainLoad L = FEcoV3BrainRegistry::Parse(Text, Name);
		const TArray<TSharedPtr<FJsonValue>>& Cases = Root->GetObjectField(TEXT("golden"))->GetArrayField(TEXT("cases"));
		const float Tol = static_cast<float>(Root->GetObjectField(TEXT("golden"))->GetNumberField(TEXT("logit_tolerance")));
		float MaxErr = 0.0f;
		int32 BadAction = 0;
		TSet<int32> Actions;
		for (const TSharedPtr<FJsonValue>& Cv : Cases)
		{
			const TSharedPtr<FJsonObject> C = Cv->AsObject();
			float Obs[P3::kObsDim];
			uint8 Mask[P3::kNumBehaviors];
			const TArray<TSharedPtr<FJsonValue>>& O = C->GetArrayField(TEXT("obs"));
			const TArray<TSharedPtr<FJsonValue>>& M = C->GetArrayField(TEXT("mask"));
			const TArray<TSharedPtr<FJsonValue>>& Lg = C->GetArrayField(TEXT("logits"));
			for (int32 i = 0; i < P3::kObsDim; ++i)
			{
				Obs[i] = static_cast<float>(O[i]->AsNumber());
			}
			for (int32 b = 0; b < P3::kNumBehaviors; ++b)
			{
				Mask[b] = M[b]->AsNumber() != 0.0 ? 1 : 0;
			}
			float Logits[P3::kNumBehaviors];
			const int32 A = P3::RunPolicyV3(L.Brain->Net, Obs, Mask, Logits);
			for (int32 b = 0; b < P3::kNumBehaviors; ++b)
			{
				MaxErr = FMath::Max(MaxErr, FMath::Abs(Logits[b] - static_cast<float>(Lg[b]->AsNumber())));
			}
			BadAction += A != static_cast<int32>(C->GetNumberField(TEXT("action"))) ? 1 : 0;
			Actions.Add(A);
		}
		AddInfo(FString::Printf(TEXT("%s: 골든 %d 사례, 최대 로짓 오차 %.3e, 행동 다름 %d, 나온 행동 %d 가지"), Name, Cases.Num(), MaxErr, BadAction, Actions.Num()));
		TestTrue(FString::Printf(TEXT("%s: 로짓 |C++ − 파이썬| ≤ %.0e"), Name, Tol), MaxErr <= Tol);
		TestEqual(FString::Printf(TEXT("%s: 행동이 파이썬과 같다"), Name), BadAction, 0);
		TestTrue(FString::Printf(TEXT("%s: 골든이 행동 둘 이상을 지난다 (먹기만이 아니다)"), Name), Actions.Num() >= 2);
	}

	// R1b 파일 = 내장 가중치 (같은 모델) — 비트 단위
	{
		const P3::FPolicyNetV3& F = R1b.Brain->Net;
		const bool bSame = FMemory::Memcmp(F.W0, P3::kW0, sizeof(P3::kW0)) == 0 && FMemory::Memcmp(F.B0, P3::kB0, sizeof(P3::kB0)) == 0
						   && FMemory::Memcmp(F.W1, P3::kW1, sizeof(P3::kW1)) == 0 && FMemory::Memcmp(F.B1, P3::kB1, sizeof(P3::kB1)) == 0
						   && FMemory::Memcmp(F.W2, P3::kW2, sizeof(P3::kW2)) == 0 && FMemory::Memcmp(F.B2, P3::kB2, sizeof(P3::kB2)) == 0;
		TestTrue(TEXT("R1b 파일 가중치 = 내장 PolicyWeightsV3.h (비트 단위)"), bSame);
		TestEqual(TEXT("R1b 파일 id = 내장 id"), R1b.Brain->Id, FEcoV3BrainRegistry::Builtin()->Id);
		bool bAllowedSame = true;
		for (int32 b = 0; b < P3::kNumBehaviors; ++b)
		{
			bAllowedSame = bAllowedSame && R1b.Brain->Allowed[b] == P3::kAllowedMask[b];
		}
		TestTrue(TEXT("R1b 파일 허용 칸 = 내장 kAllowedMask (먹기·도망·숨기·얼기)"), bAllowedSame);
	}

	// 내장 골든(PolicyGoldenVectorsV3.h 본 묶음)에서: R1b 파일 = 내장 로짓 비트 단위, R4 는 다른 결정을 낸다
	{
		int32 R1bDiff = 0;
		int32 R4ActionDiff = 0;
		float R4MaxLogitDiff = 0.0f;
		for (int32 n = 0; n < G::kCount; ++n)
		{
			uint8 Mask[P3::kNumBehaviors];
			for (int32 b = 0; b < P3::kNumBehaviors; ++b)
			{
				Mask[b] = G::kMask[n * P3::kNumBehaviors + b];
			}
			const float* Obs = &G::kObs[n * P3::kObsDim];
			float Lb[P3::kNumBehaviors];
			float L1[P3::kNumBehaviors];
			float L4[P3::kNumBehaviors];
			const int32 Ab = P3::RunPolicyV3(P3::kBuiltinNet, Obs, Mask, Lb);
			const int32 A1 = P3::RunPolicyV3(R1b.Brain->Net, Obs, Mask, L1);
			const int32 A4 = P3::RunPolicyV3(R4.Brain->Net, Obs, Mask, L4);
			R1bDiff += (A1 != Ab || FMemory::Memcmp(L1, Lb, sizeof(Lb)) != 0) ? 1 : 0;
			R4ActionDiff += A4 != Ab ? 1 : 0;
			for (int32 b = 0; b < P3::kNumBehaviors; ++b)
			{
				R4MaxLogitDiff = FMath::Max(R4MaxLogitDiff, FMath::Abs(L4[b] - Lb[b]));
			}
		}
		AddInfo(FString::Printf(TEXT("내장 골든 %d 사례: R1b 파일 다름 %d · R4 행동 다름 %d · R4 로짓 차이 최대 %.3f"), G::kCount, R1bDiff, R4ActionDiff, R4MaxLogitDiff));
		TestEqual(TEXT("R1b 파일 = 내장 (로짓·행동 비트 단위)"), R1bDiff, 0);
		TestTrue(TEXT("R4 는 내장과 다른 두뇌다 (행동이 다른 사례가 있다)"), R4ActionDiff > 0);
	}

	// R4 허용 칸 = 먹기·도망·숨기 (학습 목록), 출처 기록
	const uint8 Want[P3::kNumBehaviors] = {1, 1, 1, 0, 0};
	TestTrue(TEXT("R4 허용 칸 = 먹기·도망·숨기"), FMemory::Memcmp(R4.Brain->Allowed, Want, sizeof(Want)) == 0);
	TestEqual(TEXT("R4 모델 이름"), R4.Brain->ModelName, FString(kR4File));
	TestTrue(TEXT("R4 학습 설정 = configs/v3_r4_train.yaml"), R4.Brain->TrainConfig == TEXT("configs/v3_r4_train.yaml"));
	TestEqual(TEXT("R4 모델 zip sha256 64 글자"), R4.Brain->ModelSha256.Len(), 64);
	TestNotEqual(TEXT("R4 가중치 지문 ≠ 내장"), R4.Brain->WeightsSha256, FEcoV3BrainRegistry::Builtin()->WeightsSha256);
	// 검사만 했다 — 저장소의 지금 두뇌는 그대로다
	TestTrue(TEXT("불러오기만으로는 지금 두뇌가 바뀌지 않는다"), &*FEcoV3BrainRegistry::Get().GetActive() == &*FEcoV3BrainRegistry::Builtin());
	return true;
}

// -----------------------------------------------------------------------------
// R5 관측 21 (10-19, 계약 2-4): R1b-F + 새 세 열 0 두뇌 파일 (herbivore_rl/results/v3/r5/zero_extend.py) — 두 계약만 받고 어긋나면 거부

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainLoadObs21Test, "AdaptiveEcosystem.Policy.V3.Brain.LoadObs21",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainLoadObs21Test::RunTest(const FString& Parameters)
{
	namespace G = EcoPolicyV3::Golden;
	namespace O3 = EcoObservationV3;
	const FRegistryGuard Guard;
	const FEcoV3BrainLoad Z = FEcoV3BrainRegistry::LoadFile(kZeroObs21File);
	if (!TestTrue(FString::Printf(TEXT("관측 21 두뇌 파일 검사 통과 (%s: %s)"), EcoV3Brain::RejectName(Z.Reason), *Z.Message), Z.Ok()))
	{
		return false;
	}
	const FEcoV3Brain& B = *Z.Brain;
	AddInfo(FString::Printf(TEXT("%s | 골든 %d 최대 오차 %.3e | 학습 %s"), *B.Describe(), B.GoldenCount, B.GoldenMaxError, *B.TrainWorld));
	TestEqual(TEXT("관측 21"), B.ObsDim, O3::kObsDimObstacle);
	TestEqual(TEXT("망 = 관측 21"), B.Net.ObsDim, O3::kObsDimObstacle);
	TestEqual(TEXT("계약 해시 = 관측 21·판 2"), B.ContractHash, P3::kContractHashObs21Mask2);
	TestTrue(TEXT("내장 두뇌 = 관측 18·내장 계약"), FEcoV3BrainRegistry::Builtin()->ObsDim == P3::kObsDim && FEcoV3BrainRegistry::Builtin()->ContractHash == P3::kContractHash);
	TestTrue(TEXT("설명에 '관측 21 장애물'"), B.Describe().Contains(TEXT("관측 21 장애물")));
	TestTrue(TEXT("허용 칸 = 내장 (먹기·도망·숨기·얼기 — 통합 모드는 세계가 얼기를 막는다)"), FMemory::Memcmp(B.Allowed, P3::kAllowedMask, sizeof(B.Allowed)) == 0);
	// 가중치 = 내장 + 새 세 열 0 (비트 단위)
	{
		int32 Bad = 0;
		for (int32 j = 0; j < P3::kHiddenDim; ++j)
		{
			for (int32 i = 0; i < O3::kObsDimObstacle; ++i)
			{
				const float W = B.Net.W0[j * O3::kObsDimObstacle + i];
				const float Want = i < P3::kObsDim ? P3::kW0[j * P3::kObsDim + i] : 0.0f;
				Bad += FMemory::Memcmp(&W, &Want, sizeof(float)) != 0 ? 1 : 0;
			}
		}
		const bool bRest = FMemory::Memcmp(B.Net.B0, P3::kB0, sizeof(P3::kB0)) == 0 && FMemory::Memcmp(B.Net.W1, P3::kW1, sizeof(P3::kW1)) == 0
						   && FMemory::Memcmp(B.Net.B1, P3::kB1, sizeof(P3::kB1)) == 0 && FMemory::Memcmp(B.Net.W2, P3::kW2, sizeof(P3::kW2)) == 0
						   && FMemory::Memcmp(B.Net.B2, P3::kB2, sizeof(P3::kB2)) == 0;
		TestEqual(TEXT("첫 층 = 내장 18 열 + 새 세 열 +0.0 (비트 단위)"), Bad, 0);
		TestTrue(TEXT("나머지 층 = 내장 (비트 단위)"), bRest);
		TestNotEqual(TEXT("가중치 지문은 내장과 다르다 (첫 층 모양이 다르다)"), B.WeightsSha256, FEcoV3BrainRegistry::Builtin()->WeightsSha256);
	}
	// 내장 골든 관측 18 + 아무 세 칸 → 로짓 = 내장 (비트 단위): 새 칸은 결정을 바꾸지 않는다
	{
		int32 Diff = 0;
		const float Extra[3][O3::kNumObstacleObs] = {{0.0f, 1.0f, 0.0f}, {0.37f, 0.11f, 1.0f}, {1.0f, 0.0f, 1.0f}};
		for (int32 n = 0; n < G::kCount; ++n)
		{
			uint8 Mask[P3::kNumBehaviors];
			for (int32 b = 0; b < P3::kNumBehaviors; ++b)
			{
				Mask[b] = G::kMask[n * P3::kNumBehaviors + b];
			}
			float Lb[P3::kNumBehaviors];
			const int32 Ab = P3::RunPolicyV3(P3::kBuiltinNet, &G::kObs[n * P3::kObsDim], Mask, Lb);
			for (const auto& E : Extra)
			{
				float In[O3::kObsDimObstacle];
				FMemory::Memcpy(In, &G::kObs[n * P3::kObsDim], sizeof(float) * P3::kObsDim);
				FMemory::Memcpy(In + P3::kObsDim, E, sizeof(E));
				float Lz[P3::kNumBehaviors];
				const int32 Az = P3::RunPolicyV3(B.Net, In, Mask, Lz);
				Diff += (Az != Ab || FMemory::Memcmp(Lz, Lb, sizeof(Lb)) != 0) ? 1 : 0;
			}
		}
		TestEqual(TEXT("내장 골든 × 세 칸 셋: 관측 21 두뇌 로짓·행동 = 내장 (비트 단위)"), Diff, 0);
	}

	// 거부: 두 계약 말고는 받지 않는다, 계약과 칸 수·이름·마스크·층 모양·골든이 어긋나면 거부
	FString Text;
	if (!ReadBrainText(*this, kZeroObs21File, Text))
	{
		return false;
	}
	struct FBad
	{
		const TCHAR* Name;
		EReject Want;
		TFunction<void(const TSharedPtr<FJsonObject>&)> Edit;
	};
	const TArray<FBad> Cases = {
		{TEXT("관측 21 파일에 관측 18 계약 해시"), EReject::Dims, [](const TSharedPtr<FJsonObject>& R) { R->SetStringField(TEXT("contract_hash"), TEXT("0x7eea0107339be4ce")); }},
		{TEXT("관측 21 계약에 obs_dim 18"), EReject::Dims, [](const TSharedPtr<FJsonObject>& R) { R->SetNumberField(TEXT("obs_dim"), 18); }},
		{TEXT("관측 21 계약에 obs_dim 19"), EReject::Dims, [](const TSharedPtr<FJsonObject>& R) { R->SetNumberField(TEXT("obs_dim"), 19); }},
		{TEXT("알 수 없는 계약 (R2 관측 19·판 3)"), EReject::Contract,
		 [](const TSharedPtr<FJsonObject>& R) { R->SetStringField(TEXT("contract_hash"), TEXT("0xf8c26c7d02542fae")); }},
		{TEXT("알 수 없는 계약 (한 자리 바꿈)"), EReject::Contract,
		 [](const TSharedPtr<FJsonObject>& R) { R->SetStringField(TEXT("contract_hash"), TEXT("0xbc4fc2d45c47c5fe")); }},
		{TEXT("장애물 칸 순서 (escape_room ↔ obstacle_near)"), EReject::Names,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 TArray<TSharedPtr<FJsonValue>> N = R->GetArrayField(TEXT("obs_names"));
			 N.Swap(18, 19);
			 R->SetArrayField(TEXT("obs_names"), N);
		 }},
		{TEXT("관측 이름 18 개뿐"), EReject::Names,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 TArray<TSharedPtr<FJsonValue>> N = R->GetArrayField(TEXT("obs_names"));
			 N.SetNum(18);
			 R->SetArrayField(TEXT("obs_names"), N);
		 }},
		{TEXT("관측 21 계약에 마스크 판 3"), EReject::Mask, [](const TSharedPtr<FJsonObject>& R) { R->SetNumberField(TEXT("mask_version"), 3); }},
		{TEXT("첫 층 64×18 (관측 21 계약)"), EReject::Shape, [](const TSharedPtr<FJsonObject>& R) { Layer(R, 0)->SetNumberField(TEXT("in"), 18); }},
		{TEXT("골든 관측 18 칸"), EReject::Golden,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 const TSharedPtr<FJsonObject> C = Case(R, 0);
			 TArray<TSharedPtr<FJsonValue>> O = C->GetArrayField(TEXT("obs"));
			 O.SetNum(18);
			 C->SetArrayField(TEXT("obs"), O);
		 }},
		{TEXT("새 열에 값 + sha256 맞춤 (골든이 새 칸을 읽어 잡는다)"), EReject::Golden,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 EditWeightsKeepSha(R,
								[](FLayers& Ly)
								{
									for (int32 j = 0; j < P3::kHiddenDim; ++j)
									{
										Ly.W[0][j * EcoObservationV3::kObsDimObstacle + EcoObservationV3::kObsEscapeRoom] = (j % 2) ? 2.0f : -2.0f;
									}
								});
		 }},
	};
	int32 Wrong = 0;
	for (const FBad& Bad : Cases)
	{
		const TSharedPtr<FJsonObject> Root = ToJson(Text);
		Bad.Edit(Root);
		const FEcoV3BrainLoad L = FEcoV3BrainRegistry::Parse(ToText(Root), Bad.Name);
		const bool bOk = L.Reason == Bad.Want && !L.Brain.IsValid();
		Wrong += bOk ? 0 : 1;
		AddInfo(FString::Printf(TEXT("%s → %s: %s"), Bad.Name, EcoV3Brain::RejectName(L.Reason), *L.Message));
		TestTrue(FString::Printf(TEXT("%s → 거부 '%s' (받은 까닭 '%s')"), Bad.Name, EcoV3Brain::RejectName(Bad.Want), EcoV3Brain::RejectName(L.Reason)), bOk);
	}
	TestEqual(TEXT("모든 어긋난 관측 21 파일이 맞는 까닭으로 거부된다"), Wrong, 0);
	// 관측 18 파일(R4)에 관측 21 계약 해시를 적으면 칸 수가 계약과 달라 거부
	{
		FString R4Text;
		if (ReadBrainText(*this, kR4File, R4Text))
		{
			const TSharedPtr<FJsonObject> Root = ToJson(R4Text);
			Root->SetStringField(TEXT("contract_hash"), TEXT("0xbc4fc2d45c47c5fd"));
			const FEcoV3BrainLoad L = FEcoV3BrainRegistry::Parse(ToText(Root), TEXT("R4 + 관측 21 해시"));
			TestEqual(TEXT("관측 18 파일에 관측 21 해시 → 차원"), static_cast<int32>(L.Reason), static_cast<int32>(EReject::Dims));
		}
	}
	TestTrue(TEXT("불러오기만으로는 지금 두뇌가 바뀌지 않는다"), &*FEcoV3BrainRegistry::Get().GetActive() == &*FEcoV3BrainRegistry::Builtin());
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainRejectBadTest, "AdaptiveEcosystem.Policy.V3.Brain.RejectBad",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainRejectBadTest::RunTest(const FString& Parameters)
{
	const FRegistryGuard Guard;
	FString Text;
	if (!ReadBrainText(*this, kR4File, Text))
	{
		return false;
	}
	// 바탕: 파일을 JSON 으로 읽어 다시 쓴 글자도 통과한다 (아래 고침이 JSON 왕복 탓으로 걸리지 않게)
	{
		const FEcoV3BrainLoad L = FEcoV3BrainRegistry::Parse(ToText(ToJson(Text)), TEXT("왕복"));
		if (!TestTrue(FString::Printf(TEXT("JSON 왕복 파일도 통과 (%s: %s)"), EcoV3Brain::RejectName(L.Reason), *L.Message), L.Ok()))
		{
			return false;
		}
	}
	const FEcoV3BrainRef Before = FEcoV3BrainRegistry::Get().GetActive();

	struct FBad
	{
		const TCHAR* Name;
		EReject Want;
		TFunction<void(const TSharedPtr<FJsonObject>&)> Edit;
	};
	const TArray<FBad> Cases = {
		{TEXT("형식 이름"), EReject::Format, [](const TSharedPtr<FJsonObject>& R) { R->SetStringField(TEXT("format"), TEXT("eco_v2_policy")); }},
		{TEXT("형식 판 2"), EReject::Format, [](const TSharedPtr<FJsonObject>& R) { R->SetNumberField(TEXT("format_version"), 2); }},
		{TEXT("모델 이름 없음"), EReject::Format, [](const TSharedPtr<FJsonObject>& R) { R->GetObjectField(TEXT("model"))->RemoveField(TEXT("name")); }},
		{TEXT("계약 해시 (R2 관측 19·판 3)"), EReject::Contract,
		 [](const TSharedPtr<FJsonObject>& R) { R->SetStringField(TEXT("contract_hash"), TEXT("0xf8c26c7d02542fae")); }},
		{TEXT("관측 칸 19"), EReject::Dims, [](const TSharedPtr<FJsonObject>& R) { R->SetNumberField(TEXT("obs_dim"), 19); }},
		{TEXT("관측 이름 순서 (1·2 칸 바꿈)"), EReject::Names,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 TArray<TSharedPtr<FJsonValue>> N = R->GetArrayField(TEXT("obs_names"));
			 N.Swap(1, 2);
			 R->SetArrayField(TEXT("obs_names"), N);
		 }},
		{TEXT("행동 이름 순서"), EReject::Names,
		 [](const TSharedPtr<FJsonObject>& R) { R->SetArrayField(TEXT("behaviors"), Strings({TEXT("graze"), TEXT("hide"), TEXT("flee"), TEXT("freeze"), TEXT("sleep")})); }},
		{TEXT("마스크 판 3"), EReject::Mask, [](const TSharedPtr<FJsonObject>& R) { R->SetNumberField(TEXT("mask_version"), 3); }},
		{TEXT("숨기 문턱 0.7"), EReject::Thresholds,
		 [](const TSharedPtr<FJsonObject>& R) { R->GetObjectField(TEXT("thresholds"))->SetNumberField(TEXT("hide_cover_obs"), 0.7); }},
		{TEXT("먹기 막힘"), EReject::Allowed,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 R->SetArrayField(TEXT("allowed"), Strings({TEXT("flee"), TEXT("hide")}));
			 R->SetArrayField(TEXT("allowed_mask"), Numbers({0, 1, 1, 0, 0}));
		 }},
		{TEXT("허용 이름·칸 어긋남"), EReject::Allowed, [](const TSharedPtr<FJsonObject>& R) { R->SetArrayField(TEXT("allowed_mask"), Numbers({1, 1, 1, 1, 0})); }},
		{TEXT("층 모양 63×18"), EReject::Shape, [](const TSharedPtr<FJsonObject>& R) { Layer(R, 0)->SetNumberField(TEXT("out"), 63); }},
		{TEXT("층 둘"), EReject::Shape,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 TArray<TSharedPtr<FJsonValue>> L = R->GetArrayField(TEXT("layers"));
			 L.RemoveAt(2);
			 R->SetArrayField(TEXT("layers"), L);
		 }},
		{TEXT("base64 잘림"), EReject::Decode,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 const FString S = Layer(R, 1)->GetStringField(TEXT("w_f32le_b64"));
			 Layer(R, 1)->SetStringField(TEXT("w_f32le_b64"), S.LeftChop(8));
		 }},
		{TEXT("NaN 가중치"), EReject::NonFinite,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 EditWeightsKeepSha(R, [](FLayers& Ly) { Ly.B[2][1] = std::numeric_limits<float>::quiet_NaN(); });
		 }},
		{TEXT("가중치 한 값 바꿈 (sha256 그대로)"), EReject::Digest,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 TArray<float> B = DecodeFloats(Layer(R, 1)->GetStringField(TEXT("b_f32le_b64")));
			 B[7] += 1e-3f;
			 Layer(R, 1)->SetStringField(TEXT("b_f32le_b64"), EncodeFloats(B));
		 }},
		{TEXT("가중치 바꿈 + sha256 맞춤 (골든이 잡는다)"), EReject::Golden,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 EditWeightsKeepSha(R, [](FLayers& Ly) { Ly.B[2][2] += 0.5f; });
		 }},
		{TEXT("첫 층 전치 + sha256 맞춤 (레이아웃 오류를 골든이 잡는다)"), EReject::Golden,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 EditWeightsKeepSha(R,
								[](FLayers& Ly)
								{
									// (64, 18) 행 우선을 (18, 64) 로 읽은 것처럼 — 같은 바이트 수, 다른 배치
									TArray<float> T;
									T.SetNumUninitialized(Ly.W[0].Num());
									for (int32 j = 0; j < P3::kHiddenDim; ++j)
									{
										for (int32 i = 0; i < P3::kObsDim; ++i)
										{
											T[i * P3::kHiddenDim + j] = Ly.W[0][j * P3::kObsDim + i];
										}
									}
									Ly.W[0] = T;
								});
		 }},
		{TEXT("골든 허용 오차 0.01"), EReject::Golden,
		 [](const TSharedPtr<FJsonObject>& R) { R->GetObjectField(TEXT("golden"))->SetNumberField(TEXT("logit_tolerance"), 0.01); }},
		{TEXT("골든 5 사례"), EReject::Golden,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 TArray<TSharedPtr<FJsonValue>> C = R->GetObjectField(TEXT("golden"))->GetArrayField(TEXT("cases"));
			 C.SetNum(5);
			 R->GetObjectField(TEXT("golden"))->SetArrayField(TEXT("cases"), C);
		 }},
		{TEXT("골든 행동 바꿈"), EReject::Golden,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 const TSharedPtr<FJsonObject> C = Case(R, 0);
			 C->SetNumberField(TEXT("action"), (static_cast<int32>(C->GetNumberField(TEXT("action"))) + 1) % P3::kNumBehaviors);
		 }},
		{TEXT("골든 로짓 1e-3 밀림"), EReject::Golden,
		 [](const TSharedPtr<FJsonObject>& R)
		 {
			 const TSharedPtr<FJsonObject> C = Case(R, 3);
			 TArray<TSharedPtr<FJsonValue>> L = C->GetArrayField(TEXT("logits"));
			 L[4] = MakeShared<FJsonValueNumber>(L[4]->AsNumber() + 1e-3);
			 C->SetArrayField(TEXT("logits"), L);
		 }},
	};

	int32 Wrong = 0;
	{
		const FEcoV3BrainLoad L = FEcoV3BrainRegistry::Parse(TEXT("{ 이것은 JSON 이 아니다"), TEXT("깨진 글자"));
		TestEqual(TEXT("JSON 아님 → JSON"), static_cast<int32>(L.Reason), static_cast<int32>(EReject::Json));
		TestFalse(TEXT("JSON 아님 → 두뇌 없음"), L.Brain.IsValid());
	}
	for (const FBad& Bad : Cases)
	{
		const TSharedPtr<FJsonObject> Root = ToJson(Text);
		Bad.Edit(Root);
		const FEcoV3BrainLoad L = FEcoV3BrainRegistry::Parse(ToText(Root), Bad.Name);
		const bool bOk = L.Reason == Bad.Want && !L.Brain.IsValid();
		Wrong += bOk ? 0 : 1;
		AddInfo(FString::Printf(TEXT("%s → %s: %s"), Bad.Name, EcoV3Brain::RejectName(L.Reason), *L.Message));
		TestTrue(FString::Printf(TEXT("%s → 거부 '%s' (받은 까닭 '%s')"), Bad.Name, EcoV3Brain::RejectName(Bad.Want), EcoV3Brain::RejectName(L.Reason)), bOk);
	}
	{
		const FEcoV3BrainLoad L = FEcoV3BrainRegistry::LoadFile(TEXT("없는_두뇌_파일_이름"));
		TestEqual(TEXT("없는 파일 → 파일"), static_cast<int32>(L.Reason), static_cast<int32>(EReject::File));
	}
	TestEqual(TEXT("모든 깨진 파일이 맞는 까닭으로 거부된다"), Wrong, 0);
	TestTrue(TEXT("거부해도 지금 두뇌는 그대로"), &*FEcoV3BrainRegistry::Get().GetActive() == &*Before && !FEcoV3BrainRegistry::Get().GetPending().IsValid());
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainRegistryTest, "AdaptiveEcosystem.Policy.V3.Brain.Registry",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainRegistryTest::RunTest(const FString& Parameters)
{
	const FRegistryGuard Guard;
	// 일부러 거부하는 두 경우의 경고 줄 (콘솔 없는 파일·폴더 감시 깨진 파일) — 기대한 경고다
	AddExpectedMessagePlain(TEXT("eco.V3Brain.Load 없는_두뇌 거부"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
	AddExpectedMessagePlain(TEXT("b_bad.json 거부"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
	FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
	const FEcoV3BrainRef Builtin = FEcoV3BrainRegistry::Builtin();
	const FEcoV3BrainLoad R4 = FEcoV3BrainRegistry::LoadFile(kR4File);
	if (!TestTrue(TEXT("R4 파일"), R4.Ok()))
	{
		return false;
	}

	// --- 줄·경계·세대 ---
	const uint32 G0 = Reg.GetGeneration();
	TestTrue(TEXT("처음 = 내장"), &*Reg.GetActive() == &*Builtin);
	TestFalse(TEXT("대기 없으면 바꾸지 않는다"), Reg.CommitPending());
	Reg.Queue(R4.Brain.ToSharedRef(), TEXT("시험"));
	TestTrue(TEXT("줄에 넣어도 경계 전에는 지금 두뇌 그대로"), &*Reg.GetActive() == &*Builtin && Reg.GetPending().IsValid());
	TestEqual(TEXT("줄에 넣어도 세대 그대로"), Reg.GetGeneration(), G0);
	FEcoV3BrainPtr From;
	FString Why;
	TestTrue(TEXT("경계에서 바꾼다"), Reg.CommitPending(&From, &Why));
	TestTrue(TEXT("지금 = R4, 앞 = 내장, 까닭"), &*Reg.GetActive() == &*R4.Brain && From.IsValid() && &*From == &*Builtin && Why == TEXT("시험"));
	TestEqual(TEXT("세대 + 1"), Reg.GetGeneration(), G0 + 1);
	TestFalse(TEXT("한 번만"), Reg.CommitPending());
	Reg.Queue(FEcoV3BrainRegistry::LoadFile(TEXT("builtin")).Brain.ToSharedRef(), TEXT("되돌림"));
	TestTrue(TEXT("builtin 으로 되돌림"), Reg.CommitPending() && &*Reg.GetActive() == &*Builtin);

	// --- 이름 찾기·목록 ---
	const FString P1 = FEcoV3BrainRegistry::Resolve(kR4File);
	const FString P2 = FEcoV3BrainRegistry::Resolve(FString(kR4File) + TEXT(".json"));
	TestTrue(TEXT("이름(.json 빼고) → <프로젝트>/EcoBrains/…json"), P1.EndsWith(FString(TEXT("EcoBrains/")) + kR4File + TEXT(".json")));
	TestEqual(TEXT("이름.json 도 같은 파일"), P2, P1);
	TestTrue(TEXT("절대 경로 그대로"), FEcoV3BrainRegistry::Resolve(P1) == P1);
	TestTrue(TEXT("'builtin'·'내장'"), FEcoV3BrainRegistry::IsBuiltinName(TEXT(" Builtin ")) && FEcoV3BrainRegistry::IsBuiltinName(TEXT("내장")));
	const TArray<FString> Files = FEcoV3BrainRegistry::ListFiles();
	TestTrue(TEXT("목록에 R1b·R4 파일"), Files.ContainsByPredicate([](const FString& F) { return F.EndsWith(FString(kR4File) + TEXT(".json")); })
											&& Files.ContainsByPredicate([](const FString& F) { return F.EndsWith(FString(kR1bFile) + TEXT(".json")); }));

	// --- 콘솔 (월드 없음 = 단독 취급) ---
	{
		IConsoleManager& CM = IConsoleManager::Get();
		TestTrue(TEXT("명령 eco.V3Brain.Load·Info·List"), CM.FindConsoleObject(TEXT("eco.V3Brain.Load")) && CM.FindConsoleObject(TEXT("eco.V3Brain.Info"))
															 && CM.FindConsoleObject(TEXT("eco.V3Brain.List")));
		CM.ProcessUserConsoleInput(*FString::Printf(TEXT("eco.V3Brain.Load %s"), kR4File), *GLog, nullptr);
		TestTrue(TEXT("Load 이름 → 대기 R4"), Reg.GetPending().IsValid() && Reg.GetPending()->Id == R4.Brain->Id);
		CM.ProcessUserConsoleInput(TEXT("eco.V3Brain.Load 없는_두뇌"), *GLog, nullptr);
		TestTrue(TEXT("없는 파일은 대기를 바꾸지 않는다"), Reg.GetPending().IsValid() && Reg.GetPending()->Id == R4.Brain->Id);
		CM.ProcessUserConsoleInput(TEXT("eco.V3Brain.Info"), *GLog, nullptr);
		CM.ProcessUserConsoleInput(TEXT("eco.V3Brain.List"), *GLog, nullptr);
		CM.ProcessUserConsoleInput(TEXT("eco.V3Brain.Load builtin"), *GLog, nullptr);
		TestTrue(TEXT("Load builtin → 대기 내장"), Reg.GetPending().IsValid() && &*Reg.GetPending() == &*Builtin);
		Reg.CommitPending();
	}

	// --- 폴더 감시 (eco.V3Brain.WatchFolder) ---
	{
		IConsoleVariable* Watch = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.V3Brain.WatchFolder"));
		if (!TestNotNull(TEXT("eco.V3Brain.WatchFolder"), Watch))
		{
			return false;
		}
		TestTrue(TEXT("폴더 감시 기본 끔"), Watch->GetString().IsEmpty());
		TestFalse(TEXT("끔이면 아무것도 안 한다"), Reg.PollWatch(1000.0));
		const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::AutomationTransientDir() / TEXT("EcoV3BrainWatch"));
		IFileManager::Get().DeleteDirectory(*Dir, false, true);
		IFileManager::Get().MakeDirectory(*Dir, true);
		ON_SCOPE_EXIT
		{
			Watch->Set(TEXT(""), ECVF_SetByCode);
			IFileManager::Get().DeleteDirectory(*Dir, false, true);
		};
		Watch->Set(*Dir, ECVF_SetByCode);
		Reg.ResetForTest();
		TestFalse(TEXT("빈 폴더 → 없음"), Reg.PollWatch(10.0));
		const FString A = Dir / TEXT("a_r4.json");
		IFileManager::Get().Copy(*A, *FEcoV3BrainRegistry::Resolve(kR4File));
		IFileManager::Get().SetTimeStamp(*A, FDateTime(2026, 10, 18, 12, 0, 0));
		TestFalse(TEXT("2 초 주기 안 → 아직"), Reg.PollWatch(11.0));
		TestTrue(TEXT("새 파일 → 대기"), Reg.PollWatch(12.5) && Reg.GetPending().IsValid() && Reg.GetPending()->Id == R4.Brain->Id);
		Reg.CommitPending();
		TestFalse(TEXT("같은 파일·같은 시각 → 다시 읽지 않는다"), Reg.PollWatch(15.0));
		const FString B = Dir / TEXT("b_bad.json");
		FFileHelper::SaveStringToFile(TEXT("{ 깨진 두뇌"), *B);
		IFileManager::Get().SetTimeStamp(*B, FDateTime(2026, 10, 18, 12, 1, 0));
		TestFalse(TEXT("더 새 파일이 깨졌으면 거부 (지금 두뇌 그대로)"), Reg.PollWatch(18.0));
		TestTrue(TEXT("거부 뒤 지금 = R4, 대기 없음"), Reg.GetActive()->Id == R4.Brain->Id && !Reg.GetPending().IsValid());
		TestFalse(TEXT("거부한 파일은 시각이 바뀔 때까지 다시 읽지 않는다"), Reg.PollWatch(21.0));
		IFileManager::Get().Copy(*B, *FEcoV3BrainRegistry::Resolve(kR1bFile));
		IFileManager::Get().SetTimeStamp(*B, FDateTime(2026, 10, 18, 12, 2, 0));
		TestTrue(TEXT("고친 파일(시각 바뀜) → 대기 R1b"), Reg.PollWatch(24.0) && Reg.GetPending().IsValid() && Reg.GetPending()->Id == Builtin->Id);
	}
	return true;
}

// -----------------------------------------------------------------------------
// 10-21 실시간 두뇌 교체 (LIVE_ADAPT_SPEC.md 5.4): 되돌리기 쌓개·'adapt' 블록·감시 준비·쓰는 중 파일·상태 파일

namespace EcoV3BrainTestImpl
{
	/**
	 * 바탕 두뇌 파일 글자(R4)의 모델 이름을 바꾸고 Round > 0 이면 'adapt' 블록을 붙여 다시 읽는다 — 가중치·골든 그대로라 검사를 통과하는 다른 id 의 두뇌
	 * (파이썬 live.py 가 내보낼 꼴, LIVE_ADAPT_SPEC.md 3절). OutText = 쓴 글자.
	 */
	FEcoV3BrainPtr ParseLive(const FString& BaseText, const FString& Name, int32 Round, FString* OutText = nullptr)
	{
		const TSharedPtr<FJsonObject> Root = ToJson(BaseText);
		if (!Root.IsValid())
		{
			return nullptr;
		}
		Root->GetObjectField(TEXT("model"))->SetStringField(TEXT("name"), Name);
		if (Round > 0)
		{
			const TSharedPtr<FJsonObject> A = MakeShared<FJsonObject>();
			A->SetNumberField(TEXT("round"), Round);
			A->SetNumberField(TEXT("attempt"), Round + 2);
			A->SetStringField(TEXT("run"), TEXT("live_20261021T1532_e2"));
			A->SetStringField(TEXT("snapshot"), TEXT("eco_v3_snapshot_s20003_t1800_e1.json"));
			A->SetStringField(TEXT("env"), TEXT("Barren 나무 0→20, 비 1.0"));
			A->SetStringField(TEXT("gate"), TEXT("포만 없는 세계 잡힘 31.2→28.4% (t −2.9), 게임 세계 나빠짐 없음"));
			A->SetStringField(TEXT("created_utc"), TEXT("2026-10-21T10:32:00Z"));
			Root->SetObjectField(TEXT("adapt"), A);
		}
		const FString Text = ToText(Root);
		if (OutText)
		{
			*OutText = Text;
		}
		return FEcoV3BrainRegistry::Parse(Text, Name + TEXT(".json")).Brain;
	}

	/** 쌓개가 이 두뇌들(오래된 것부터, 같은 객체)인가. */
	bool HistoryIs(const FEcoV3BrainRegistry& Reg, std::initializer_list<const FEcoV3Brain*> Want)
	{
		const TArray<FEcoV3BrainHistoryEntry>& H = Reg.GetHistory();
		if (H.Num() != static_cast<int32>(Want.size()))
		{
			return false;
		}
		int32 i = 0;
		for (const FEcoV3Brain* W : Want)
		{
			if (&*H[i++].Brain != W)
			{
				return false;
			}
		}
		return true;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainHistoryTest, "AdaptiveEcosystem.Policy.V3.Brain.History",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainHistoryTest::RunTest(const FString& Parameters)
{
	const FRegistryGuard Guard;
	FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
	FString R4Text;
	if (!ReadBrainText(*this, kR4File, R4Text))
	{
		return false;
	}
	const FEcoV3BrainPtr L1 = ParseLive(R4Text, TEXT("live_r1_t"), 1);
	const FEcoV3BrainPtr L2 = ParseLive(R4Text, TEXT("live_r2_t"), 2);
	const FEcoV3BrainPtr L3 = ParseLive(R4Text, TEXT("live_r3_t"), 3);
	if (!TestTrue(TEXT("판 1·2·3 두뇌 (R4 가중치, 다른 이름)"), L1.IsValid() && L2.IsValid() && L3.IsValid()))
	{
		return false;
	}
	const FEcoV3Brain* const PB = &*FEcoV3BrainRegistry::Builtin();
	const FEcoV3Brain* const P1 = L1.Get();
	const FEcoV3Brain* const P2 = L2.Get();
	const FEcoV3Brain* const P3b = L3.Get();
	TestTrue(TEXT("id 셋이 다르다"), L1->Id != L2->Id && L2->Id != L3->Id);

	// --- 처음: 쌓개가 비면 되돌리지 못한다 ---
	FString Msg;
	TestEqual(TEXT("처음 쌓개 빔"), Reg.GetHistory().Num(), 0);
	TestEqual(TEXT("처음 까닭"), Reg.GetActiveWhy(), FString(TEXT("내장 (처음)")));
	TestFalse(TEXT("쌓개가 비면 되돌리지 못한다"), Reg.Rollback(TEXT("시험"), &Msg));
	TestFalse(TEXT("… 대기도 없다"), Reg.GetPending().IsValid());

	// --- 바꿀 때마다 나가는 두뇌를 쌓는다 (오래된 것부터) ---
	bool bRb = true;
	Reg.Queue(L1.ToSharedRef(), TEXT("a"));
	TestTrue(TEXT("내장 → 판 1 (되돌림 아님)"), Reg.CommitPending(nullptr, nullptr, &bRb) && !bRb);
	Reg.Queue(L2.ToSharedRef(), TEXT("b"));
	Reg.CommitPending();
	Reg.Queue(L3.ToSharedRef(), TEXT("c"));
	Reg.CommitPending();
	TestTrue(TEXT("쌓개 = [내장, 판 1, 판 2], 지금 판 3"), HistoryIs(Reg, {PB, P1, P2}) && &*Reg.GetActive() == P3b);
	TestEqual(TEXT("쌓개 칸 = 들어온 까닭/바뀐 까닭"), Reg.GetHistory()[1].Why + TEXT("/") + Reg.GetHistory()[1].ReplacedWhy, FString(TEXT("a/b")));
	TestEqual(TEXT("지금 두뇌가 된 까닭"), Reg.GetActiveWhy(), FString(TEXT("c")));
	TestFalse(TEXT("마지막 바꾸기 = 되돌림 아님"), Reg.WasLastCommitRollback());

	// --- 되돌리기: 맨 위를 줄에 넣고 경계에서 바꾼다. 되돌림이 내보내는 두뇌는 쌓지 않는다 ---
	const uint32 G0 = Reg.GetGeneration();
	TestTrue(TEXT("되돌리기 → 대기 판 2 (되돌림)"), Reg.Rollback(TEXT("시험"), &Msg) && Reg.GetPending().IsValid() && Reg.GetPending().Get() == P2 && Reg.IsPendingRollback());
	TestTrue(TEXT("경계 전에는 지금 두뇌·세대 그대로, 꺼낸 칸은 쌓개에서 빠진다"), &*Reg.GetActive() == P3b && Reg.GetGeneration() == G0 && HistoryIs(Reg, {PB, P1}));
	FEcoV3BrainPtr From;
	FString Why;
	TestTrue(TEXT("경계에서 되돌림 (앞 = 판 3)"), Reg.CommitPending(&From, &Why, &bRb) && bRb && &*Reg.GetActive() == P2 && From.Get() == P3b);
	TestTrue(TEXT("되돌림 까닭에 처음 까닭"), Why.Contains(TEXT("되돌림")) && Why.Contains(TEXT("처음 까닭: b")));
	TestTrue(TEXT("판 3 은 쌓지 않는다"), HistoryIs(Reg, {PB, P1}));
	TestTrue(TEXT("저장소: 마지막 바꾸기 = 되돌림, 세대 + 1"), Reg.WasLastCommitRollback() && Reg.GetGeneration() == G0 + 1 && !Reg.IsPendingRollback());

	// --- 경계 전에 두 번 = 둘 앞으로 (건너뛴 두뇌는 버린다) ---
	TestTrue(TEXT("되돌리기 1 → 대기 판 1"), Reg.Rollback(TEXT("시험")) && Reg.GetPending().Get() == P1);
	TestTrue(TEXT("되돌리기 2 → 대기 내장 (판 1 건너뜀)"), Reg.Rollback(TEXT("시험")) && Reg.GetPending().Get() == PB && Reg.IsPendingRollback());
	TestTrue(TEXT("쌓개 빔"), Reg.GetHistory().IsEmpty());
	TestFalse(TEXT("더 앞이 없으면 거짓 — 대기 되돌림은 그대로"), Reg.Rollback(TEXT("시험"), &Msg));
	TestTrue(TEXT("… 대기 내장 그대로"), Reg.GetPending().Get() == PB && Reg.IsPendingRollback());
	TestTrue(TEXT("경계 → 내장, 쌓개 빔"), Reg.CommitPending() && &*Reg.GetActive() == PB && Reg.GetHistory().IsEmpty());

	// --- 대기 되돌림을 다른 두뇌가 덮으면 꺼낸 칸을 쌓개에 돌려놓는다 ---
	Reg.Queue(L1.ToSharedRef(), TEXT("a2"));
	Reg.CommitPending();
	Reg.Queue(L2.ToSharedRef(), TEXT("b2"));
	Reg.CommitPending();
	TestTrue(TEXT("되돌리기 → 대기 판 1"), Reg.Rollback(TEXT("시험")) && HistoryIs(Reg, {PB}));
	Reg.Queue(L3.ToSharedRef(), TEXT("폴더 감시"));
	TestTrue(TEXT("덮은 대기는 되돌림이 아니고 쌓개 = [내장, 판 1] 로 돌아간다"), !Reg.IsPendingRollback() && HistoryIs(Reg, {PB, P1}));
	Reg.CommitPending();
	TestTrue(TEXT("경계 → 판 3, 쌓개 = [내장, 판 1, 판 2]"), &*Reg.GetActive() == P3b && HistoryIs(Reg, {PB, P1, P2}));

	// --- 경계 전에 두 번 되돌린 대기를 다른 두뇌가 덮으면 꺼낸 칸 둘을 모두 (같은 순서로) 돌려놓는다 ---
	TestTrue(TEXT("되돌리기 두 번 → 대기 판 1 (판 2 건너뜀), 쌓개 = [내장]"),
			 Reg.Rollback(TEXT("시험")) && Reg.Rollback(TEXT("시험")) && Reg.GetPending().Get() == P1 && Reg.IsPendingRollback() && HistoryIs(Reg, {PB}));
	Reg.Queue(L3.ToSharedRef(), TEXT("폴더 감시 2"));
	TestTrue(TEXT("덮은 대기는 되돌림이 아니고 쌓개 = [내장, 판 1, 판 2] 로 돌아간다 (판 2 도 잃지 않는다)"), !Reg.IsPendingRollback() && HistoryIs(Reg, {PB, P1, P2}));
	Reg.CommitPending();
	TestTrue(TEXT("경계 → 판 3 (같은 id 라 쌓지 않음), 쌓개 그대로"), &*Reg.GetActive() == P3b && HistoryIs(Reg, {PB, P1, P2}));
	TestTrue(TEXT("되돌리기 → 대기 판 2 (돌려놓은 칸을 다시 쓴다)"), Reg.Rollback(TEXT("시험")) && Reg.GetPending().Get() == P2 && HistoryIs(Reg, {PB, P1}));
	Reg.Queue(L3.ToSharedRef(), TEXT("폴더 감시 3"));
	Reg.CommitPending();
	TestTrue(TEXT("… 덮고 경계 → 쌓개 [내장, 판 1, 판 2]"), &*Reg.GetActive() == P3b && HistoryIs(Reg, {PB, P1, P2}));

	// --- 같은 id 로 바꾸면 쌓지 않는다 ---
	Reg.Queue(L3.ToSharedRef(), TEXT("같은 두뇌"));
	Reg.CommitPending();
	TestTrue(TEXT("같은 id → 쌓개 그대로"), HistoryIs(Reg, {PB, P1, P2}));

	// --- 상한 16: 넘으면 가장 오래된 것을 버린다 ---
	for (int32 i = 0; i < 20; ++i)
	{
		Reg.Queue((i % 2 == 0 ? L1 : L2).ToSharedRef(), TEXT("돌림"));
		Reg.CommitPending();
	}
	TestEqual(TEXT("쌓개 상한 16"), Reg.GetHistory().Num(), EcoV3Brain::kHistoryMax);
	TestTrue(TEXT("가장 오래된 내장은 밀려났다"), &Reg.GetHistory()[0].Brain.Get() != PB);

	// --- 콘솔 eco.V3Brain.Rollback·History (월드 없음 = 단독 취급) ---
	{
		IConsoleManager& CM = IConsoleManager::Get();
		TestTrue(TEXT("명령 eco.V3Brain.Rollback·History"), CM.FindConsoleObject(TEXT("eco.V3Brain.Rollback")) && CM.FindConsoleObject(TEXT("eco.V3Brain.History")));
		const FEcoV3Brain* const Top = &Reg.GetHistory().Last().Brain.Get();
		CM.ProcessUserConsoleInput(TEXT("eco.V3Brain.Rollback"), *GLog, nullptr);
		TestTrue(TEXT("콘솔 되돌리기 → 대기 = 쌓개 맨 위"), Reg.GetPending().IsValid() && Reg.GetPending().Get() == Top && Reg.IsPendingRollback());
		CM.ProcessUserConsoleInput(TEXT("eco.V3Brain.History"), *GLog, nullptr);
		CM.ProcessUserConsoleInput(TEXT("eco.V3Brain.Info"), *GLog, nullptr);
	}

	// --- ResetForTest 는 쌓개·대기 되돌림을 지운다 ---
	Reg.ResetForTest();
	TestTrue(TEXT("ResetForTest → 쌓개 빔·대기 없음·처음 까닭"), Reg.GetHistory().IsEmpty() && !Reg.GetPending().IsValid() && !Reg.IsPendingRollback()
															   && !Reg.WasLastCommitRollback() && Reg.GetActiveWhy() == TEXT("내장 (처음)"));
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainAdaptTest, "AdaptiveEcosystem.Policy.V3.Brain.Adapt",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainAdaptTest::RunTest(const FString& Parameters)
{
	const FRegistryGuard Guard;
	FString R4Text;
	if (!ReadBrainText(*this, kR4File, R4Text))
	{
		return false;
	}
	// 'adapt' 블록이 있으면 읽는다 (가중치·골든 검사와 무관 — 통과)
	const FEcoV3BrainPtr L = ParseLive(R4Text, TEXT("live_r3_live_20261021T1532_e2"), 3);
	if (!TestTrue(TEXT("'adapt' 블록이 있는 파일 검사 통과"), L.IsValid()))
	{
		return false;
	}
	TestTrue(TEXT("adapt 블록 있음"), L->bAdapt);
	TestEqual(TEXT("판"), L->AdaptRound, 3);
	TestEqual(TEXT("시도"), L->AdaptAttempt, 5);
	TestEqual(TEXT("실행"), L->AdaptRun, FString(TEXT("live_20261021T1532_e2")));
	TestEqual(TEXT("스냅숏"), L->AdaptSnapshot, FString(TEXT("eco_v3_snapshot_s20003_t1800_e1.json")));
	TestEqual(TEXT("환경"), L->AdaptEnv, FString(TEXT("Barren 나무 0→20, 비 1.0")));
	TestEqual(TEXT("관문"), L->AdaptGate, FString(TEXT("포만 없는 세계 잡힘 31.2→28.4% (t −2.9), 게임 세계 나빠짐 없음")));
	TestTrue(TEXT("설명 끝에 ', 판 3)'"), L->Describe().EndsWith(TEXT(", 판 3)")));
	TestEqual(TEXT("판 글자"), L->RoundTag(), FString(TEXT("판 3")));
	TestEqual(TEXT("짧은 id = 이름 앞 7 자…@지문 앞 4"), L->ShortId(), FString::Printf(TEXT("live_r3…@%s"), *L->WeightsSha256.Left(4)));
	{
		// 판 10 넘으면 판 번호 끝까지 남긴다 (판 12 와 판 1x 가 화면에서 갈린다)
		const FEcoV3BrainPtr L12 = ParseLive(R4Text, TEXT("live_r12_live_20261021T1532_e2"), 12);
		TestTrue(TEXT("판 12 짧은 id = 'live_r12…@지문 앞 4'"), L12.IsValid() && L12->ShortId() == FString::Printf(TEXT("live_r12…@%s"), *L12->WeightsSha256.Left(4)));
		TestTrue(TEXT("판 12 판 글자"), L12.IsValid() && L12->RoundTag() == TEXT("판 12"));
	}
	TestEqual(TEXT("id = 모델 이름@지문 앞 8 (판 이름이 id 를 가른다)"), L->Id, FString::Printf(TEXT("live_r3_live_20261021T1532_e2@%s"), *L->WeightsSha256.Left(8)));
	AddInfo(L->Describe());

	// 블록이 없으면 빈 칸 (지금 파일 그대로 — 설명도 그대로)
	const FEcoV3BrainLoad R4 = FEcoV3BrainRegistry::Parse(R4Text, TEXT("R4"));
	if (!TestTrue(TEXT("R4 파일"), R4.Ok()))
	{
		return false;
	}
	TestTrue(TEXT("블록 없음 → 판 0·빈 칸"), !R4.Brain->bAdapt && R4.Brain->AdaptRound == 0 && R4.Brain->AdaptAttempt == 0 && R4.Brain->AdaptRun.IsEmpty()
												 && R4.Brain->AdaptSnapshot.IsEmpty() && R4.Brain->AdaptEnv.IsEmpty() && R4.Brain->AdaptGate.IsEmpty());
	TestFalse(TEXT("블록 없음 → 설명에 '판' 없음"), R4.Brain->Describe().Contains(TEXT("판 ")));
	TestTrue(TEXT("블록 없는 파일 두뇌 → 판 글자 없음"), R4.Brain->RoundTag().IsEmpty());
	TestEqual(TEXT("live_r 이 아닌 긴 이름 → 앞 7 자…"), R4.Brain->ShortId(), FString::Printf(TEXT("v3_r4_g…@%s"), *R4.Brain->WeightsSha256.Left(4)));
	TestEqual(TEXT("내장 → '판 0'"), FEcoV3BrainRegistry::Builtin()->RoundTag(), FString(TEXT("판 0")));
	TestFalse(TEXT("내장 → adapt 블록 없음"), FEcoV3BrainRegistry::Builtin()->bAdapt);

	// 깨진 블록도 거부하지 않는다 (판 = 0 으로)
	{
		const TSharedPtr<FJsonObject> Root = ToJson(R4Text);
		const TSharedPtr<FJsonObject> A = MakeShared<FJsonObject>();
		A->SetStringField(TEXT("round"), TEXT("셋"));
		A->SetNumberField(TEXT("attempt"), -4);
		Root->SetObjectField(TEXT("adapt"), A);
		const FEcoV3BrainLoad Bad = FEcoV3BrainRegistry::Parse(ToText(Root), TEXT("깨진 adapt"));
		TestTrue(FString::Printf(TEXT("깨진 adapt 값 → 통과 (%s: %s)"), EcoV3Brain::RejectName(Bad.Reason), *Bad.Message), Bad.Ok());
		TestTrue(TEXT("… 판 0·시도 0 (음수는 0)"), Bad.Ok() && Bad.Brain->bAdapt && Bad.Brain->AdaptRound == 0 && Bad.Brain->AdaptAttempt == 0);
	}
	{
		const TSharedPtr<FJsonObject> Root = ToJson(R4Text);
		Root->SetNumberField(TEXT("adapt"), 7);
		const FEcoV3BrainLoad Bad = FEcoV3BrainRegistry::Parse(ToText(Root), TEXT("adapt 가 객체 아님"));
		TestTrue(TEXT("adapt 가 객체가 아니면 → 통과, 블록 없음 취급"), Bad.Ok() && !Bad.Brain->bAdapt && Bad.Brain->AdaptRound == 0);
	}
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainWatchLiveTest, "AdaptiveEcosystem.Policy.V3.Brain.WatchLive",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainWatchLiveTest::RunTest(const FString& Parameters)
{
	const FRegistryGuard Guard;
	// 일부러 거부하는 오래된 깨진 파일의 경고 한 줄 — 기대한 경고다 (쓰는 중인 새 파일은 경고가 아니다)
	AddExpectedMessagePlain(TEXT("d_old_bad.json 거부"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
	FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
	IConsoleVariable* Watch = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.V3Brain.WatchFolder"));
	const FEcoV3BrainLoad R4 = FEcoV3BrainRegistry::LoadFile(kR4File);
	FString R1bText;
	if (!TestNotNull(TEXT("eco.V3Brain.WatchFolder"), Watch) || !TestTrue(TEXT("R4 파일"), R4.Ok()) || !ReadBrainText(*this, kR1bFile, R1bText))
	{
		return false;
	}
	const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::AutomationTransientDir() / TEXT("EcoV3BrainWatchLive"));
	IFileManager::Get().DeleteDirectory(*Dir, false, true);
	IFileManager::Get().MakeDirectory(*Dir, true);
	ON_SCOPE_EXIT
	{
		Watch->Set(TEXT(""), ECVF_SetByCode);
		FEcoV3BrainRegistry::Get().ResetForTest();
		IFileManager::Get().DeleteDirectory(*Dir, false, true);
	};

	// --- 기본 감시 폴더 (적응 고리): 콘솔 변수가 비었을 때만 쓴다 ---
	TestTrue(TEXT("처음 감시 끔"), Reg.EffectiveWatchFolder().IsEmpty());
	Reg.SetDefaultWatchFolder(Dir);
	TestEqual(TEXT("콘솔 변수가 비면 기본 폴더"), Reg.EffectiveWatchFolder(), Dir);
	Watch->Set(TEXT("Saved/다른_폴더"), ECVF_SetByCode);
	TestEqual(TEXT("콘솔 변수가 이긴다"), Reg.EffectiveWatchFolder(), FString(TEXT("Saved/다른_폴더")));
	Watch->Set(TEXT(""), ECVF_SetByCode);

	// --- PrimeWatch: 그때 있던 파일은 읽지 않는다 (가장 새 파일이 깨졌어도 거부로 치지 않는다) ---
	const FString OldGood = Dir / TEXT("a_old_obs21.json");
	IFileManager::Get().Copy(*OldGood, *FEcoV3BrainRegistry::Resolve(kZeroObs21File));
	IFileManager::Get().SetTimeStamp(*OldGood, FDateTime(2020, 1, 1, 9, 0, 0));
	const FString OldBad = Dir / TEXT("b_old_bad.json");
	FFileHelper::SaveStringToFile(TEXT("{ 깨진 두뇌"), *OldBad, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	IFileManager::Get().SetTimeStamp(*OldBad, FDateTime(2020, 1, 1, 9, 1, 0));
	const uint32 Serial0 = Reg.GetLastWatchReject().Serial;
	Reg.PrimeWatch();
	TestFalse(TEXT("준비 뒤 감시: 그때 있던 파일을 읽지 않는다"), Reg.PollWatch(100.0));
	TestTrue(TEXT("… 대기 없음·거부 없음"), !Reg.GetPending().IsValid() && Reg.GetLastWatchReject().Serial == Serial0);

	// --- 그때 있던 더 새 파일이 지워져 오래된 파일(관측 21 두뇌 — 읽으면 바꿀 수 있는 파일)이 다시 가장 새 파일이 돼도 읽지 않는다 ---
	IFileManager::Get().Delete(*OldBad);
	TestFalse(TEXT("Play 전부터 있던 파일이 다시 가장 새 파일 → 읽지 않는다"), Reg.PollWatch(102.5));
	TestTrue(TEXT("… 대기 없음·거부 없음"), !Reg.GetPending().IsValid() && Reg.GetLastWatchReject().Serial == Serial0);

	// --- 뒤에 나타난 파일은 바꾼다 ---
	const FString New = Dir / TEXT("c_live_r1.json");
	IFileManager::Get().Copy(*New, *FEcoV3BrainRegistry::Resolve(kR4File));
	IFileManager::Get().SetTimeStamp(*New, FDateTime(2020, 1, 1, 9, 2, 0));
	TestTrue(TEXT("Play 뒤에 나타난 파일 → 대기 R4"), Reg.PollWatch(105.0) && Reg.GetPending().IsValid() && Reg.GetPending()->Id == R4.Brain->Id);
	Reg.CommitPending();

	// --- 오래된 깨진 파일: 거부를 기억하고 번호를 올린다 (서브시스템이 한 번 알린다) ---
	const FString OldBad2 = Dir / TEXT("d_old_bad.json");
	FFileHelper::SaveStringToFile(TEXT("{ 깨진 두뇌"), *OldBad2, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	IFileManager::Get().SetTimeStamp(*OldBad2, FDateTime(2020, 1, 1, 9, 3, 0));
	TestFalse(TEXT("오래된 깨진 파일 → 거부"), Reg.PollWatch(107.5));
	{
		const FEcoV3WatchReject& Rej = Reg.GetLastWatchReject();
		TestTrue(TEXT("거부 번호 + 1, 파일·까닭 JSON"), Rej.Serial == Serial0 + 1 && Rej.File == OldBad2 && Rej.Reason == EReject::Json && !Rej.Message.IsEmpty());
	}
	TestFalse(TEXT("거부한 파일은 다시 읽지 않는다"), Reg.PollWatch(110.0));
	TestEqual(TEXT("… 거부 번호 그대로"), Reg.GetLastWatchReject().Serial, Serial0 + 1);

	// --- 쓰는 중인 새 파일 (깨짐 + 3 초 안): 거부로 치지 않고 기억하지 않는다 → 같은 (경로, 시각) 을 다음 감시에 다시 읽는다 ---
	const FString Young = Dir / TEXT("e_young.json");
	FFileHelper::SaveStringToFile(R1bText.Left(R1bText.Len() / 2), *Young, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	const FDateTime YoungStamp = FDateTime::UtcNow();
	IFileManager::Get().SetTimeStamp(*Young, YoungStamp);
	TestFalse(TEXT("반쯤 쓴 새 파일 → 아직"), Reg.PollWatch(112.5));
	TestTrue(TEXT("… 거부 아님 (번호 그대로)·대기 없음"), Reg.GetLastWatchReject().Serial == Serial0 + 1 && !Reg.GetPending().IsValid());
	FFileHelper::SaveStringToFile(R1bText, *Young, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	IFileManager::Get().SetTimeStamp(*Young, YoungStamp);
	TestTrue(TEXT("다 쓴 뒤 (같은 시각) → 다시 읽어 대기 R1b"),
			 Reg.PollWatch(115.0) && Reg.GetPending().IsValid() && Reg.GetPending()->Id == FEcoV3BrainRegistry::Builtin()->Id);
	TestEqual(TEXT("… 거부 번호 그대로"), Reg.GetLastWatchReject().Serial, Serial0 + 1);
	Reg.CommitPending();

	// --- Play 번호 (10-21): 다른 Play 의 스냅숏에서 배운 두뇌는 받지 않는다 (파일은 멀쩡 — 까닭 '다른 Play'), 같은 Play 면 바꾼다 ---
	FString R4Text;
	if (!ReadBrainText(*this, kR4File, R4Text))
	{
		return false;
	}
	const auto WithPlay = [&R4Text](const TCHAR* PlayId)
	{
		int32 Brace = INDEX_NONE;
		R4Text.FindChar(TEXT('{'), Brace);
		return R4Text.Left(Brace + 1) + FString::Printf(TEXT("\"adapt\": {\"round\": 1, \"attempt\": 1, \"run\": \"t\", \"play_id\": \"%s\"},"), PlayId) +
			   R4Text.Mid(Brace + 1);
	};
	Reg.SetWatchPlayId(TEXT("pNow"));
	const FString Other = Dir / TEXT("f_other_play.json");
	FFileHelper::SaveStringToFile(WithPlay(TEXT("pOld")), *Other, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	IFileManager::Get().SetTimeStamp(*Other, FDateTime(2020, 1, 1, 9, 4, 0) + FTimespan::FromDays(3650.0));
	TestFalse(TEXT("다른 Play 의 두뇌 → 받지 않는다"), Reg.PollWatch(117.5));
	{
		const FEcoV3WatchReject& Rej = Reg.GetLastWatchReject();
		TestTrue(TEXT("… 까닭 '다른 Play'·번호 + 1·대기 없음"),
				 Rej.Reason == EReject::Play && Rej.Serial == Serial0 + 2 && Rej.File == Other && !Reg.GetPending().IsValid());
	}
	const FString Same = Dir / TEXT("g_same_play.json");
	FFileHelper::SaveStringToFile(WithPlay(TEXT("pNow")), *Same, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	IFileManager::Get().SetTimeStamp(*Same, FDateTime(2020, 1, 1, 9, 5, 0) + FTimespan::FromDays(3650.0));
	TestTrue(TEXT("같은 Play 의 두뇌 → 대기 R4 (adapt.play_id 읽음)"),
			 Reg.PollWatch(120.0) && Reg.GetPending().IsValid() && Reg.GetPending()->Id == R4.Brain->Id && Reg.GetPending()->AdaptPlayId == TEXT("pNow"));
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoV3BrainLiveStatusTest, "AdaptiveEcosystem.Policy.V3.Brain.LiveStatus",
								 EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3BrainLiveStatusTest::RunTest(const FString& Parameters)
{
	const FRegistryGuard Guard;
	auto StatusJson = [](double Updated, const TCHAR* Message)
	{
		return FString::Printf(TEXT("{\"format\": \"eco_v3_live_status\", \"version\": 1, \"updated_unix\": %.3f, \"pid\": 1234, \"state\": \"training\", ")
								   TEXT("\"attempt\": 5, \"round\": 3, \"snapshot\": \"eco_v3_snapshot_s20003_t1800_e1.json\", \"env\": \"Barren 나무 0→20\", ")
								   TEXT("\"message\": \"%s\", \"progress\": 0.6, \"last_result\": \"기각: 1차 t −1.2 (문턱 −2.02)\"}"),
							   Updated, Message);
	};

	// --- 글자 읽기 (LIVE_ADAPT_SPEC.md 4절) ---
	const double U = 1760000000.5;
	FEcoV3LiveStatus S;
	if (!TestTrue(TEXT("상태 글자 읽기"), EcoV3Brain::ParseLiveStatus(StatusJson(U, TEXT("학습 중 1.2M/2M (모델 2개)")), S)))
	{
		return false;
	}
	TestTrue(TEXT("칸: 상태·시도·판·pid·시각·진행·스냅숏·환경·지난 결과"),
			 S.bValid && S.State == TEXT("training") && S.Attempt == 5 && S.Round == 3 && S.Pid == 1234 && S.UpdatedUnix == U && FMath::IsNearlyEqual(S.Progress, 0.6)
				 && S.Snapshot == TEXT("eco_v3_snapshot_s20003_t1800_e1.json") && S.Env == TEXT("Barren 나무 0→20")
				 && S.LastResult == TEXT("기각: 1차 t −1.2 (문턱 −2.02)"));
	TestEqual(TEXT("메시지"), S.Message, FString(TEXT("학습 중 1.2M/2M (모델 2개)")));
	{
		FEcoV3LiveStatus M;
		TestTrue(TEXT("형식·판만 있어도 읽는다"), EcoV3Brain::ParseLiveStatus(TEXT("{\"format\": \"eco_v3_live_status\", \"version\": 1}"), M));
		TestTrue(TEXT("… 없는 칸 = 기본값 (진행 -1)"), M.bValid && M.Progress == -1.0 && M.UpdatedUnix == 0.0 && M.Message.IsEmpty() && M.Round == 0);
	}
	{
		FEcoV3LiveStatus Keep = S;
		FString Err;
		TestFalse(TEXT("형식 이름이 다르면 거짓"), EcoV3Brain::ParseLiveStatus(TEXT("{\"format\": \"eco_v3_snapshot\", \"version\": 1}"), Keep, &Err));
		TestFalse(TEXT("판 2 → 거짓"), EcoV3Brain::ParseLiveStatus(TEXT("{\"format\": \"eco_v3_live_status\", \"version\": 2}"), Keep));
		TestFalse(TEXT("JSON 아님 → 거짓"), EcoV3Brain::ParseLiveStatus(TEXT("{ 깨진"), Keep, &Err));
		TestTrue(TEXT("거짓이면 Out 그대로·까닭"), Keep.Round == 3 && Keep.Message == S.Message && !Err.IsEmpty());
	}

	// --- 화면 글자: 120 초 안 = 메시지, 넘으면 응답 없음, 파일 없음, 못 읽음 ---
	TestEqual(TEXT("30 초 전 → 메시지"), EcoV3Brain::LiveStatusText(S, true, U + 30.0), FString(TEXT("적응 고리 | 학습 중 1.2M/2M (모델 2개)")));
	TestEqual(TEXT("120 초 전 → 아직 메시지"), EcoV3Brain::LiveStatusText(S, true, U + 120.0), FString(TEXT("적응 고리 | 학습 중 1.2M/2M (모델 2개)")));
	TestEqual(TEXT("121 초 전 → 응답 없음"), EcoV3Brain::LiveStatusText(S, true, U + 121.0), FString(TEXT("적응 고리 | 응답 없음 (121초 전)")));
	TestEqual(TEXT("파일 없음"), EcoV3Brain::LiveStatusText(S, false, U), FString(TEXT("적응 고리 | 파이썬 감시 없음")));
	TestEqual(TEXT("못 읽음"), EcoV3Brain::LiveStatusText(FEcoV3LiveStatus(), true, U), FString(TEXT("적응 고리 | 상태 파일을 못 읽음")));
	{
		FEcoV3LiveStatus NoMsg = S;
		NoMsg.Message.Empty();
		TestEqual(TEXT("메시지가 비면 상태"), EcoV3Brain::LiveStatusText(NoMsg, true, U + 1.0), FString(TEXT("적응 고리 | training")));
	}

	// --- 파일 읽기 (eco.V3Brain.StatusFile, 비면 적응 고리 기본 파일 — 2 초마다) ---
	FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
	IConsoleVariable* StatusVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.V3Brain.StatusFile"));
	if (!TestNotNull(TEXT("eco.V3Brain.StatusFile"), StatusVar))
	{
		return false;
	}
	TestTrue(TEXT("상태 파일 기본 끔"), StatusVar->GetString().IsEmpty() && Reg.EffectiveStatusFile().IsEmpty());
	TestFalse(TEXT("끔이면 읽지 않는다"), Reg.PollStatus(10.0));
	TestTrue(TEXT("끔이면 화면 글자 없음"), Reg.GetLiveStatusText(EcoV3Brain::NowUnixSeconds()).IsEmpty());
	const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::AutomationTransientDir() / TEXT("EcoV3LiveStatus"));
	const FString Path = Dir / TEXT("status.json");
	IFileManager::Get().DeleteDirectory(*Dir, false, true);
	IFileManager::Get().MakeDirectory(*Dir, true);
	ON_SCOPE_EXIT
	{
		StatusVar->Set(TEXT(""), ECVF_SetByCode);
		FEcoV3BrainRegistry::Get().ResetForTest();
		IFileManager::Get().DeleteDirectory(*Dir, false, true);
	};
	Reg.SetDefaultStatusFile(Path);
	TestEqual(TEXT("기본 상태 파일"), Reg.EffectiveStatusFile(), Path);
	TestTrue(TEXT("파일 없음 → 읽어 봄"), Reg.PollStatus(20.0));
	TestEqual(TEXT("… 파이썬 감시 없음"), Reg.GetLiveStatusText(EcoV3Brain::NowUnixSeconds()), FString(TEXT("적응 고리 | 파이썬 감시 없음")));
	FFileHelper::SaveStringToFile(StatusJson(EcoV3Brain::NowUnixSeconds(), TEXT("학습 중 1.2M/2M (모델 2개)")), *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	TestFalse(TEXT("2 초 주기 안 → 아직"), Reg.PollStatus(21.0));
	TestTrue(TEXT("주기 → 읽음"), Reg.PollStatus(22.0));
	TestEqual(TEXT("… 메시지"), Reg.GetLiveStatusText(EcoV3Brain::NowUnixSeconds()), FString(TEXT("적응 고리 | 학습 중 1.2M/2M (모델 2개)")));
	TestTrue(TEXT("… 상태 칸"), Reg.GetLiveStatus().bValid && Reg.GetLiveStatus().Round == 3 && Reg.GetLiveStatus().Path == Path);
	FFileHelper::SaveStringToFile(TEXT("{ 깨진"), *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
	TestTrue(TEXT("깨진 글자 → 읽어 봄"), Reg.PollStatus(24.0));
	TestTrue(TEXT("… 앞 상태 그대로"), Reg.GetLiveStatus().bValid && Reg.GetLiveStatus().Round == 3);
	// 콘솔 변수가 이긴다 (경로가 바뀌면 주기를 기다리지 않는다)
	const FString Other = Dir / TEXT("other_status.json");
	StatusVar->Set(*Other, ECVF_SetByCode);
	TestEqual(TEXT("콘솔 변수가 이긴다"), Reg.EffectiveStatusFile(), Other);
	TestTrue(TEXT("다른 파일 → 곧바로 읽어 봄"), Reg.PollStatus(24.5));
	TestTrue(TEXT("… 없는 파일 → 상태 비움·파이썬 감시 없음"), !Reg.GetLiveStatus().bValid
														  && Reg.GetLiveStatusText(EcoV3Brain::NowUnixSeconds()) == TEXT("적응 고리 | 파이썬 감시 없음"));
	return true;
}

#endif

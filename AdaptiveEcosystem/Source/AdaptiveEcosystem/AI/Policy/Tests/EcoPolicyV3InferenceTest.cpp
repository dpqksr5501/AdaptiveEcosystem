// v3 행동 고르기 정책 파리티 자동화 시험 — 엔진 **안에서** 파이썬 배포 경로(RepertoirePolicy argmax)와 대조한다.
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3"
//                        -unattended -nopause -nosplash -NullRHI
//                        -testexit="Automation Test Queue Empty"
//
// 골든은 `PolicyGoldenVectorsV3.h` 에 배열로 박혀 있다 (herbivore_rl/export_weights_v3.py 생성). 파일 I/O·레벨·월드가 없는
// 순수 수치 시험이다. 같은 골든을 herbivore_rl/tests/test_export_v3.py 가 g++ 로도 돌린다.
//
// 묶음 (자세한 정의는 생성 헤더 머리 주석):
//   GoldenParity   본 묶음 — 로짓 max |C++ - Python| <= kLogitTolerance, argmax 정확히 같음
//   NearTie        근접 동점 묶음 — 로짓 허용 오차는 같고, 행동은 파이썬 최대 로짓에서 kNearTieGap 안의 허용 칸 중 하나
//   ArgmaxTieRule  로짓을 직접 준 동점·빈 마스크 — torch argmax(낮은 번호)와 같음
//   MaskNotNetInput 마스크는 망 입력이 아니다 — 마스크를 바꿔도 로짓이 비트 단위로 같고, 고른 행동은 허용 칸이다
//   ActionMask     가능 칸(관측만)·정책 입력 마스크(허용 ∧ 가능 ∧ 결정)·문턱 바로 위·아래
//   ActionMaskAlarm 마스크 판 3 (경보 세계 관측 19) 문턱 격자, 그리고 경보 0 이면 판 3 = 판 2
//   Contract       생성 헤더의 계약 상수 (해시·차원·허용 칸)

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3Inference.h"
#include "../PolicyGoldenVectorsV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 익명 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoPolicyV3Test
{
	using namespace EcoPolicyV3;

	constexpr int32 kMaxReport = 5;   // 어긋난 사례를 몇 개까지 오류로 찍나

	FString MaskString(const uint8* Mask)
	{
		return FString::Printf(TEXT("%d%d%d%d%d"), Mask[0], Mask[1], Mask[2], Mask[3], Mask[4]);
	}

	bool MasksEqual(const uint8* A, const uint8* B)
	{
		for (int32 j = 0; j < kNumBehaviors; ++j)
		{
			if ((A[j] != 0) != (B[j] != 0))
			{
				return false;
			}
		}
		return true;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3GoldenParityTest,
	"AdaptiveEcosystem.Policy.V3.GoldenParity",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3GoldenParityTest::RunTest(const FString& Parameters)
{
	using namespace EcoPolicyV3;
	using namespace EcoPolicyV3::Golden;

	float MaxError = 0.0f;
	int32 WorstCase = INDEX_NONE;
	int32 ActionMismatch = 0;

	for (int32 n = 0; n < kCount; ++n)
	{
		float Logits[kNumBehaviors];
		const uint8* Mask = &kMask[n * kNumBehaviors];
		const int32 Action = RunPolicyV3(&kObs[n * kObsDim], Mask, Logits);

		for (int32 j = 0; j < kNumBehaviors; ++j)
		{
			const float Error = FMath::Abs(Logits[j] - kLogits[n * kNumBehaviors + j]);
			if (Error > MaxError)
			{
				MaxError = Error;
				WorstCase = n;
			}
		}
		if (Action != kAction[n])
		{
			if (ActionMismatch < EcoPolicyV3Test::kMaxReport)
			{
				AddError(FString::Printf(TEXT("사례 %d (시드 %d 스텝 %d 개체 %d, 마스크 %s): C++ 행동 %d, 파이썬 %d"), n,
										 kSource[n * 3], kSource[n * 3 + 1], kSource[n * 3 + 2],
										 *EcoPolicyV3Test::MaskString(Mask), Action, kAction[n]));
			}
			++ActionMismatch;
		}
	}

	AddInfo(FString::Printf(TEXT("모델 %s, 관측 %d, 본 골든 %d개, 최대 로짓 오차 %.3e (사례 %d), argmax 불일치 %d"),
							UTF8_TO_TCHAR(kModelName), kObsDim, kCount, MaxError, WorstCase, ActionMismatch));

	TestTrue(FString::Printf(TEXT("최대 로짓 오차 %.3e 가 허용치 %.0e 이내여야 한다"), MaxError, kLogitTolerance),
			 MaxError <= kLogitTolerance);
	TestEqual(TEXT("본 묶음 argmax 는 모두 파이썬과 같아야 한다"), ActionMismatch, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3NearTieTest,
	"AdaptiveEcosystem.Policy.V3.NearTie",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3NearTieTest::RunTest(const FString& Parameters)
{
	using namespace EcoPolicyV3;
	using namespace EcoPolicyV3::Golden;

	float MaxError = 0.0f;
	int32 ExactMatch = 0;

	for (int32 n = 0; n < kNearTieCount; ++n)
	{
		float Logits[kNumBehaviors];
		const uint8* Mask = &kNearTieMask[n * kNumBehaviors];
		const float* Expected = &kNearTieLogits[n * kNumBehaviors];
		const int32 Action = RunPolicyV3(&kNearTieObs[n * kObsDim], Mask, Logits);

		float PyMax = -FLT_MAX;
		int32 Allowed = 0;
		for (int32 j = 0; j < kNumBehaviors; ++j)
		{
			MaxError = FMath::Max(MaxError, FMath::Abs(Logits[j] - Expected[j]));
			if (Mask[j] != 0)
			{
				PyMax = FMath::Max(PyMax, Expected[j]);
				++Allowed;
			}
		}

		// 근접 동점이므로 1·2위가 모두 허용 칸이어야 한다 (골든이 그렇게 골랐다)
		TestTrue(FString::Printf(TEXT("근접 동점 %d 은 허용 칸이 둘 이상"), n), Allowed >= 2);
		TestTrue(FString::Printf(TEXT("근접 동점 %d: C++ 행동 %d 는 허용 칸"), n, Action), Mask[Action] != 0);
		TestTrue(FString::Printf(TEXT("근접 동점 %d: C++ 행동 %d 의 파이썬 로짓 %.7f 가 최대 %.7f 에서 %.0e 안"), n, Action,
								 Expected[Action], PyMax, kNearTieGap),
				 Expected[Action] >= PyMax - kNearTieGap);
		if (Action == kNearTieAction[n])
		{
			++ExactMatch;
		}
	}

	AddInfo(FString::Printf(TEXT("근접 동점 %d개 (1·2위 차 < %.0e), 최대 로짓 오차 %.3e, 파이썬 argmax 와 같은 사례 %d"),
							kNearTieCount, kNearTieGap, MaxError, ExactMatch));
	TestTrue(FString::Printf(TEXT("근접 동점 최대 로짓 오차 %.3e <= %.0e"), MaxError, kLogitTolerance),
			 MaxError <= kLogitTolerance);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3ArgmaxTieRuleTest,
	"AdaptiveEcosystem.Policy.V3.ArgmaxTieRule",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3ArgmaxTieRuleTest::RunTest(const FString& Parameters)
{
	using namespace EcoPolicyV3;
	using namespace EcoPolicyV3::Golden;

	for (int32 n = 0; n < kTieCount; ++n)
	{
		const uint8* Mask = &kTieMask[n * kNumBehaviors];
		const int32 Action = SelectAction(&kTieLogits[n * kNumBehaviors], Mask);
		TestEqual(FString::Printf(TEXT("동점 규칙 %d (마스크 %s)"), n, *EcoPolicyV3Test::MaskString(Mask)), Action,
				  kTieAction[n]);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3MaskNotNetInputTest,
	"AdaptiveEcosystem.Policy.V3.MaskNotNetInput",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3MaskNotNetInputTest::RunTest(const FString& Parameters)
{
	using namespace EcoPolicyV3;
	using namespace EcoPolicyV3::Golden;

	// 앞 16개 사례에 마스크 32가지를 모두 씌운다
	const int32 NumCases = FMath::Min(kCount, 16);
	int32 LogitChanged = 0;
	int32 BadChoice = 0;

	for (int32 n = 0; n < NumCases; ++n)
	{
		const float* Obs = &kObs[n * kObsDim];
		float Base[kNumBehaviors];
		ComputeLogits(Obs, Base);

		for (int32 Bits = 0; Bits < (1 << kNumBehaviors); ++Bits)
		{
			uint8 Mask[kNumBehaviors];
			for (int32 j = 0; j < kNumBehaviors; ++j)
			{
				Mask[j] = ((Bits >> j) & 1) != 0 ? 1 : 0;
			}
			float Logits[kNumBehaviors];
			const int32 Action = RunPolicyV3(Obs, Mask, Logits);
			for (int32 j = 0; j < kNumBehaviors; ++j)
			{
				if (FMemory::Memcmp(&Logits[j], &Base[j], sizeof(float)) != 0)
				{
					++LogitChanged;
				}
			}
			if (Bits == 0)
			{
				// 빈 마스크(설계상 없다): 파이썬처럼 0
				BadChoice += Action == kGraze ? 0 : 1;
				continue;
			}
			// 고른 칸은 허용 칸이고, 허용 칸 중 최댓값이며, 같은 최댓값의 더 낮은 허용 칸이 없다
			bool bOk = Mask[Action] != 0;
			for (int32 j = 0; j < kNumBehaviors && bOk; ++j)
			{
				if (Mask[j] != 0 && (Logits[j] > Logits[Action] || (j < Action && Logits[j] == Logits[Action])))
				{
					bOk = false;
				}
			}
			BadChoice += bOk ? 0 : 1;
		}
	}

	AddInfo(FString::Printf(TEXT("사례 %d개 x 마스크 32가지"), NumCases));
	TestEqual(TEXT("마스크를 바꿔도 로짓은 비트 단위로 같다 (망은 마스크 칸을 보지 않는다)"), LogitChanged, 0);
	TestEqual(TEXT("고른 행동은 허용 칸의 argmax (동점이면 낮은 번호)"), BadChoice, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3ActionMaskTest,
	"AdaptiveEcosystem.Policy.V3.ActionMask",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3ActionMaskTest::RunTest(const FString& Parameters)
{
	using namespace EcoPolicyV3;
	using namespace EcoPolicyV3::Golden;

	int32 FeasibleMismatch = 0;
	int32 ComposeMismatch = 0;
	int32 Composed = 0;

	for (int32 n = 0; n < kCount; ++n)
	{
		uint8 Feasible[kNumBehaviors];
		ComputeFeasibleMask(&kObs[n * kObsDim], Feasible);
		if (!EcoPolicyV3Test::MasksEqual(Feasible, &kFeasible[n * kNumBehaviors]))
		{
			if (FeasibleMismatch < EcoPolicyV3Test::kMaxReport)
			{
				AddError(FString::Printf(TEXT("사례 %d 가능 칸: C++ %s, 파이썬 %s"), n, *EcoPolicyV3Test::MaskString(Feasible),
										 *EcoPolicyV3Test::MaskString(&kFeasible[n * kNumBehaviors])));
			}
			++FeasibleMismatch;
		}

		// 정책 입력 마스크는 롤아웃 사례에서만 다시 만든다 (합성 마스크는 결정 정보가 없다)
		if (kKind[n] == kKindSynthetic)
		{
			continue;
		}
		uint8 Mask[kNumBehaviors];
		ComposeActionMask(Feasible, kReads[n] != 0, kWakeDecide[n] != 0, kBehavior[n], Mask);
		++Composed;
		if (!EcoPolicyV3Test::MasksEqual(Mask, &kMask[n * kNumBehaviors]))
		{
			if (ComposeMismatch < EcoPolicyV3Test::kMaxReport)
			{
				AddError(FString::Printf(TEXT("사례 %d 정책 입력 마스크: C++ %s, 파이썬 %s"), n, *EcoPolicyV3Test::MaskString(Mask),
										 *EcoPolicyV3Test::MaskString(&kMask[n * kNumBehaviors])));
			}
			++ComposeMismatch;
		}
	}

	int32 EdgeMismatch = 0;
	for (int32 n = 0; n < kMaskEdgeCount; ++n)
	{
		uint8 Feasible[kNumBehaviors];
		ComputeFeasibleMask(&kMaskEdgeObs[n * kObsDim], Feasible);
		if (!EcoPolicyV3Test::MasksEqual(Feasible, &kMaskEdgeFeasible[n * kNumBehaviors]))
		{
			if (EdgeMismatch < EcoPolicyV3Test::kMaxReport)
			{
				AddError(FString::Printf(TEXT("문턱 사례 %d: C++ %s, 파이썬 %s"), n, *EcoPolicyV3Test::MaskString(Feasible),
										 *EcoPolicyV3Test::MaskString(&kMaskEdgeFeasible[n * kNumBehaviors])));
			}
			++EdgeMismatch;
		}
	}

	AddInfo(FString::Printf(TEXT("가능 칸 %d개, 정책 입력 마스크 %d개, 문턱 바로 위·아래 %d개 (판 %d)"), kCount, Composed,
							kMaskEdgeCount, kMaskVersion));
	TestEqual(TEXT("가능 칸은 파이썬 feasible_mask 와 같다"), FeasibleMismatch, 0);
	TestEqual(TEXT("정책 입력 마스크는 파이썬 action_mask 와 같다"), ComposeMismatch, 0);
	TestEqual(TEXT("문턱 바로 위·아래 가능 칸은 파이썬과 같다"), EdgeMismatch, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3ActionMaskAlarmTest,
	"AdaptiveEcosystem.Policy.V3.ActionMaskAlarm",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3ActionMaskAlarmTest::RunTest(const FString& Parameters)
{
	using namespace EcoPolicyV3;
	using namespace EcoPolicyV3::Golden;

	const FMaskLayoutV3 AlarmLayout = {kAlarmObsDim, kAlarmPredCount, kAlarmThreatRecency, kAlarmCoverDist, kAlarmHeard};
	TestTrue(TEXT("경보 세계 배치에는 alarm_heard 칸이 있다 (판 3)"), AlarmLayout.AlarmHeard >= 0);
	TestTrue(TEXT("경보 세계 관측 칸 수는 상한 안"), kAlarmObsDim <= kMaxObsDim);

	int32 AlarmMismatch = 0;
	for (int32 n = 0; n < kAlarmCount; ++n)
	{
		uint8 Feasible[kNumBehaviors];
		ComputeFeasibleMask(AlarmLayout, &kAlarmObs[n * kAlarmObsDim], Feasible);
		if (!EcoPolicyV3Test::MasksEqual(Feasible, &kAlarmFeasible[n * kNumBehaviors]))
		{
			if (AlarmMismatch < EcoPolicyV3Test::kMaxReport)
			{
				AddError(FString::Printf(TEXT("판 3 사례 %d: C++ %s, 파이썬 %s"), n, *EcoPolicyV3Test::MaskString(Feasible),
										 *EcoPolicyV3Test::MaskString(&kAlarmFeasible[n * kNumBehaviors])));
			}
			++AlarmMismatch;
		}
	}
	TestEqual(TEXT("판 3 가능 칸은 파이썬 feasible_mask 와 같다"), AlarmMismatch, 0);

	// 경보를 듣지 않았으면(alarm_heard 0) 판 3 마스크는 판 2 와 같아야 한다 (계획서 3-4)
	int32 Differ = 0;
	for (int32 n = 0; n < kCount; ++n)
	{
		float AlarmObs[kMaxObsDim] = {};
		for (int32 i = 0; i < kAlarmObsDim; ++i)
		{
			const int32 From = kAlarmFromBuiltin[i];
			AlarmObs[i] = From >= 0 ? kObs[n * kObsDim + From] : 0.0f;
		}
		AlarmObs[kAlarmHeard] = 0.0f;

		uint8 V2[kNumBehaviors];
		uint8 V3[kNumBehaviors];
		ComputeFeasibleMask(&kObs[n * kObsDim], V2);
		ComputeFeasibleMask(AlarmLayout, AlarmObs, V3);
		Differ += EcoPolicyV3Test::MasksEqual(V2, V3) ? 0 : 1;
	}
	AddInfo(FString::Printf(TEXT("판 3 문턱 격자 %d개, 경보 0 비교 %d개"), kAlarmCount, kCount));
	TestEqual(TEXT("경보 0 이면 판 3 마스크 = 판 2 마스크"), Differ, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3ContractTest,
	"AdaptiveEcosystem.Policy.V3.Contract",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3ContractTest::RunTest(const FString& Parameters)
{
	using namespace EcoPolicyV3;

	AddInfo(FString::Printf(TEXT("모델 %s, 관측 %d, 마스크 판 %d, 계약 0x%016llx, 모델 지문 0x%016llx"),
							UTF8_TO_TCHAR(kModelName), kObsDim,
							kMaskVersion, static_cast<uint64>(kContractHash), static_cast<uint64>(kModelDigest)));

	TestTrue(TEXT("계약 해시는 알려진 값 (R1b 관측 18·판 2 또는 R2 관측 19·판 3)"),
			 kContractHash == kContractHashObs18Mask2 || kContractHash == kContractHashObs19Mask3);
	TestTrue(TEXT("판 3 골든의 계약 해시는 R2 계약"), Golden::kAlarmContractHash == kContractHashObs19Mask3);
	TestTrue(TEXT("GRAZE 는 늘 허용 (마스크가 비지 않는다)"), kAllowedMask[kGraze] != 0);
	TestTrue(TEXT("FLEE 는 늘 허용 (R1 명세 머리말)"), kAllowedMask[kFlee] != 0);

	// 판 3 경보 세계 관측은 이 모델 관측 + 맨 끝 alarm_heard 다 (관측 18 모델일 때)
	if (kObsAlarmHeard < 0)
	{
		TestEqual(TEXT("경보 세계 관측 = 이 모델 관측 + 1"), Golden::kAlarmObsDim, kObsDim + 1);
		TestEqual(TEXT("alarm_heard 는 맨 끝"), Golden::kAlarmHeard, kObsDim);
		for (int32 i = 0; i < kObsDim; ++i)
		{
			TestEqual(FString::Printf(TEXT("경보 세계 관측 %d 는 같은 칸"), i), Golden::kAlarmFromBuiltin[i], i);
		}
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

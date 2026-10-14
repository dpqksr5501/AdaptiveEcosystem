// 정책 결정과 피식 EMA 주기가 프레임 수가 아니라 시간을 따르는지 본다.
//
// 1 스텝 = StepSeconds(0.1333초) = 파이썬 1 스텝. 예전 언리얼은 "PolicyInterval(8) 프레임마다"로
// 셌다 — 60FPS 를 가정한 것이라 30FPS 에서는 결정과 EMA 감쇠가 절반 속도로 돌았다.
// 지금은 프레임 dt 를 논리 틱(1/60초)으로 바꿔 센다 (EcoPolicyClock.h).

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorConfig.h"
#include "../EcoBehaviorFragments.h"
#include "../EcoBehaviorProcessors.h"
#include "../EcoPolicyClock.h"
#include "../EcoRegionPredationSubsystem.h"
#include "EcoTestWorld.h"
#include "Mass/EcoMassFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"

#include <limits>

namespace EcoScheduleTestImpl
{
	/** 정책(+ 선택적으로 게더·포식) 프로세서와 초식 아키타입. 케이스마다 새로 만든다. */
	struct FScheduleRig
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager* EM = nullptr;
		FMassArchetypeHandle HerbArch;
		UEcoNeighborhoodGatherProcessor* Gather = nullptr;
		UEcoPolicyProcessor* Policy = nullptr;
		UEcoPredationProcessor* Predation = nullptr;
		TArray<FMassEntityHandle> Herbs;

		bool Init(FAutomationTestBase& Test)
		{
			if (!Test.TestNotNull(TEXT("테스트 월드"), Scoped.World))
			{
				return false;
			}
			UMassEntitySubsystem* Sub = Scoped.World->GetSubsystem<UMassEntitySubsystem>();
			if (!Test.TestNotNull(TEXT("UMassEntitySubsystem"), Sub))
			{
				return false;
			}
			EM = &Sub->GetMutableEntityManager();
			HerbArch = EM->CreateArchetype(EcoTest::HerbivoreComposition());
			const TSharedRef<FMassEntityManager> Shared = EM->AsShared();
			Gather = NewObject<UEcoNeighborhoodGatherProcessor>(Scoped.World);
			Policy = NewObject<UEcoPolicyProcessor>(Scoped.World);
			Predation = NewObject<UEcoPredationProcessor>(Scoped.World);
			for (UMassProcessor* P : {static_cast<UMassProcessor*>(Gather),
									  static_cast<UMassProcessor*>(Policy),
									  static_cast<UMassProcessor*>(Predation)})
			{
				P->CallInitialize(Scoped.World, Shared);
			}
			return true;
		}

		UEcoRegionPredationSubsystem* Sub() const
		{
			return Scoped.World->GetSubsystem<UEcoRegionPredationSubsystem>();
		}

		/** 위상 Phase 로 초식을 하나 만든다. 서로 멀리 떨어뜨린다. */
		FMassEntityHandle AddHerb(int32 Phase)
		{
			const FMassEntityHandle E = EM->CreateEntity(HerbArch);
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform()
				.SetLocation(FVector(3000.0f * Herbs.Num(), 0, 0));
			FEcoVitalsFragment& V = EM->GetFragmentDataChecked<FEcoVitalsFragment>(E);
			V.MaxEnergy = 100.0f;
			V.Energy = 50.0f;
			EM->GetFragmentDataChecked<FEcoPolicyRuntimeFragment>(E).LastPolicyStep = Phase;
			Herbs.Add(E);
			return E;
		}

		/** 피식 1건을 미리 넣는다. 첫 스텝에서 EMA = (1-d)·g 가 된다. */
		void PrimeEma()
		{
			Sub()->ReportAlivePopulation(1);
			Sub()->ReportPredation(FVector::ZeroVector);
		}

		/** 한 프레임. 결정한 개체는 Forage 가 -1 에서 [0,1] 로 바뀐다. 결정한 개체 수를 돌려준다. */
		int32 Frame(float FrameDt, TArray<int32>* PerEntityCount = nullptr, bool bWithPredation = false)
		{
			for (const FMassEntityHandle& E : Herbs)
			{
				EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action.Forage = -1.0f;
			}
			if (bWithPredation)
			{
				EcoTest::RunProcessor(*Gather, *EM, FrameDt);
			}
			EcoTest::RunProcessor(*Policy, *EM, FrameDt);
			if (bWithPredation)
			{
				EcoTest::RunProcessor(*Predation, *EM, FrameDt);
			}
			EcoTest::FlushPhase(*EM);
			int32 Decided = 0;
			for (int32 i = 0; i < Herbs.Num(); ++i)
			{
				if (EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(Herbs[i]).Action.Forage >= 0.0f)
				{
					++Decided;
					if (PerEntityCount) { ++(*PerEntityCount)[i]; }
				}
			}
			return Decided;
		}

		int32 Phase(int32 i) const
		{
			return EM->GetFragmentDataChecked<FEcoPolicyRuntimeFragment>(Herbs[i]).LastPolicyStep;
		}
	};

	/** e₁·dᵏ — 테스트 안에서 같은 float 식으로 계산한다. */
	float EmaAfter(int32 Steps)
	{
		float E = (1.0f - EcoBehaviorConfig::PredationEmaDecay) * EcoBehaviorConfig::PredationEmaGain;
		for (int32 k = 1; k < Steps; ++k)
		{
			E *= EcoBehaviorConfig::PredationEmaDecay;
		}
		return Steps > 0 ? E : 0.0f;
	}

	struct FFpsCase { float FrameDt; int32 Frames; const TCHAR* Name; };
	// 모두 3.2초 = 24 스텝이다.
	const FFpsCase FpsCases[] = {
		{1.0f / 30.0f, 96, TEXT("30FPS")},
		{1.0f / 60.0f, 192, TEXT("60FPS")},
		{1.0f / 120.0f, 384, TEXT("120FPS")},
		{1.0f / 20.0f, 64, TEXT("20FPS")},
		{1.0f / 10.0f, 32, TEXT("10FPS")},
	};
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoScheduleStepClockUnitsTest,
	"AdaptiveEcosystem.Policy.Schedule.StepClockUnits",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoScheduleStepClockUnitsTest::RunTest(const FString& Parameters)
{
	const float Step = EcoBehaviorConfig::StepSeconds;
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	TestTrue(TEXT("1 논리 틱 = 1/60초 (StepSeconds = PolicyInterval / 60)"),
			 FMath::IsNearlyEqual(Step, static_cast<float>(Interval) / 60.0f, 1e-7f));

	{
		EcoPolicy::FStepClock C;
		int32 Bad = 0;
		for (int32 i = 0; i < 100000; ++i) { Bad += (C.Advance(1.0f / 60.0f, Step, Interval) != 1) ? 1 : 0; }
		TestEqual(TEXT("60FPS 는 매 프레임 정확히 1틱, 오차가 쌓이지 않는다"), Bad, 0);
		TestEqual(TEXT("60FPS 나머지 0"), C.Remainder, 0.0);
	}
	{
		EcoPolicy::FStepClock C;
		int32 Sum = 0;
		for (int32 i = 0; i < 160; ++i) { Sum += C.Advance(1.0f / 50.0f, Step, Interval); }
		TestEqual(TEXT("50FPS 160프레임(3.2초) = 192틱"), Sum, 192);
	}
	{
		EcoPolicy::FStepClock C;
		int32 Sum = 0;
		for (int32 i = 0; i < 384; ++i) { Sum += C.Advance(1.0f / 120.0f, Step, Interval); }
		TestEqual(TEXT("120FPS 384프레임(3.2초) = 192틱"), Sum, 192);
	}
	{
		// 실제 vsync 60Hz: 프레임 시각은 n/60 근처에서 잡음(±0.3ms)으로 흔들린다. 매 프레임 정확히 1틱이어야
		// 결정 간격이 8프레임으로 고정된다(예전 동작·파이썬 매 스텝 결정). 버림 기준이면 약 1/4 프레임이
		// 0틱, 1/4 이 2틱이 된다.
		EcoPolicy::FStepClock C;
		FRandomStream Jitter(7);
		double Prev = 0.0;
		int32 Bad = 0;
		for (int32 n = 1; n <= 3600; ++n)
		{
			const double Now = n / 60.0 + Jitter.FRandRange(-0.0003f, 0.0003f);
			Bad += (C.Advance(static_cast<float>(Now - Prev), Step, Interval) != 1) ? 1 : 0;
			Prev = Now;
		}
		TestEqual(TEXT("잡음 섞인 60FPS 도 매 프레임 정확히 1틱"), Bad, 0);
	}
	struct FCase { float Dt; int32 Ticks; };
	for (const FCase& K : {FCase{1.0f / 20.0f, 3}, FCase{1.0f / 10.0f, 6}, FCase{1.0f / 5.0f, 12},
						   FCase{Step, Interval}, FCase{5.0f, 300}, FCase{20.0f, 64 * Interval}})
	{
		EcoPolicy::FStepClock C;
		TestEqual(FString::Printf(TEXT("dt %.4f초 → %d틱"), K.Dt, K.Ticks), C.Advance(K.Dt, Step, Interval), K.Ticks);
	}
	for (const float BadDt : {0.0f, -1.0f, std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity()})
	{
		EcoPolicy::FStepClock C;
		TestEqual(TEXT("0·음수·NaN·Inf 는 0틱"), C.Advance(BadDt, Step, Interval), 0);
		TestEqual(TEXT("나머지도 그대로"), C.Remainder, 0.0);
	}

	struct FPhaseCase { int32 Phase; int32 Ticks; bool bDecide; int32 After; };
	for (const FPhaseCase& K : {FPhaseCase{7, 1, true, 0}, FPhaseCase{0, 1, false, 1}, FPhaseCase{3, 64, true, 3},
								FPhaseCase{20, 1, true, 0}, FPhaseCase{3, 300, true, 7}})
	{
		int32 Phase = K.Phase;
		const bool bDecide = EcoPolicy::AdvanceDecisionPhase(Phase, K.Ticks, Interval);
		TestEqual(FString::Printf(TEXT("결정 위상 (%d,+%d) 결정 여부"), K.Phase, K.Ticks), bDecide, K.bDecide);
		TestEqual(FString::Printf(TEXT("결정 위상 (%d,+%d) 뒤 위상"), K.Phase, K.Ticks), Phase, K.After);
	}
	struct FStepCase { int32 Phase; int32 Ticks; int32 Steps; int32 After; };
	for (const FStepCase& K : {FStepCase{7, 1, 1, 0}, FStepCase{4, 12, 2, 0}, FStepCase{0, 512, 64, 0}})
	{
		int32 Phase = K.Phase;
		TestEqual(FString::Printf(TEXT("EMA 위상 (%d,+%d) 스텝 수"), K.Phase, K.Ticks),
				  EcoPolicy::ConsumeSteps(Phase, K.Ticks, Interval), K.Steps);
		TestEqual(FString::Printf(TEXT("EMA 위상 (%d,+%d) 뒤 위상"), K.Phase, K.Ticks), Phase, K.After);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoScheduleSixtyFpsLegacyTest,
	"AdaptiveEcosystem.Policy.Schedule.SixtyFpsMatchesLegacy",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoScheduleSixtyFpsLegacyTest::RunTest(const FString& Parameters)
{
	// 60FPS 에서는 예전 동작과 정확히 같아야 한다: 위상 k 개체는 8-k, 16-k, … 프레임에 결정한다.
	EcoScheduleTestImpl::FScheduleRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	for (int32 k = 0; k < Interval; ++k)
	{
		Rig.AddHerb(k);
	}
	int32 Mismatch = 0;
	for (int32 f = 1; f <= 24 * Interval; ++f)
	{
		for (const FMassEntityHandle& E : Rig.Herbs)
		{
			Rig.EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action.Forage = -1.0f;
		}
		EcoTest::RunProcessor(*Rig.Policy, *Rig.EM, 1.0f / 60.0f);
		for (int32 k = 0; k < Interval; ++k)
		{
			const bool bDecided = Rig.EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(Rig.Herbs[k]).Action.Forage >= 0.0f;
			const bool bExpected = ((f + k) % Interval) == 0;
			Mismatch += (bDecided != bExpected) ? 1 : 0;
		}
	}
	TestEqual(TEXT("60FPS 결정 프레임이 예전과 같다"), Mismatch, 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoScheduleDecisionRateTest,
	"AdaptiveEcosystem.Policy.Schedule.DecisionRateFpsIndependent",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoScheduleDecisionRateTest::RunTest(const FString& Parameters)
{
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	for (const EcoScheduleTestImpl::FFpsCase& Case : EcoScheduleTestImpl::FpsCases)
	{
		EcoScheduleTestImpl::FScheduleRig Rig;
		if (!Rig.Init(*this))
		{
			return false;
		}
		for (int32 k = 0; k < Interval; ++k)
		{
			Rig.AddHerb(k);
		}
		TArray<int32> Counts;
		Counts.Init(0, Interval);
		for (int32 f = 0; f < Case.Frames; ++f)
		{
			Rig.Frame(Case.FrameDt, &Counts);
		}
		for (int32 k = 0; k < Interval; ++k)
		{
			TestEqual(FString::Printf(TEXT("%s: 3.2초 동안 위상 %d 개체의 결정 수 = 24"), Case.Name, k), Counts[k], 24);
		}
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoScheduleEmaRateTest,
	"AdaptiveEcosystem.Policy.Schedule.PredationEmaFpsIndependent",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoScheduleEmaRateTest::RunTest(const FString& Parameters)
{
	// 피식 1건 뒤 3.2초(24 스텝) 동안의 감쇠가 FPS 와 무관해야 한다. 큰 프레임(5FPS)은 한 프레임에
	// 여러 스텝을 처리한다.
	const float Expected = EcoScheduleTestImpl::EmaAfter(24);
	TArray<EcoScheduleTestImpl::FFpsCase> Cases(EcoScheduleTestImpl::FpsCases, UE_ARRAY_COUNT(EcoScheduleTestImpl::FpsCases));
	Cases.Add({1.0f / 5.0f, 16, TEXT("5FPS")});
	for (const EcoScheduleTestImpl::FFpsCase& Case : Cases)
	{
		EcoScheduleTestImpl::FScheduleRig Rig;
		if (!Rig.Init(*this) || !TestNotNull(TEXT("피식 서브시스템"), Rig.Sub()))
		{
			return false;
		}
		Rig.PrimeEma();
		for (int32 f = 0; f < Case.Frames; ++f)
		{
			Rig.Frame(Case.FrameDt, nullptr, /*bWithPredation*/ true);
		}
		const float Got = Rig.Sub()->GetRawEma();
		TestTrue(FString::Printf(TEXT("%s: 24스텝 뒤 EMA %.6f == %.6f"), Case.Name, Got, Expected),
				 FMath::IsNearlyEqual(Got, Expected, 1e-6f));
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoScheduleLargeZeroDeltaTest,
	"AdaptiveEcosystem.Policy.Schedule.LargeAndZeroDelta",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoScheduleLargeZeroDeltaTest::RunTest(const FString& Parameters)
{
	const float Step = EcoBehaviorConfig::StepSeconds;
	struct FCase { float Dt; int32 Frames; int32 Decisions; int32 Phase; int32 EmaSteps; const TCHAR* Name; };
	const FCase Cases[] = {
		{Step, 1, 1, 3, 1, TEXT("(a) dt = 1스텝")},
		{5.0f, 1, 1, 7, 37, TEXT("(b) dt = 5초 = 300틱")},
		{20.0f, 1, 1, 3, 64, TEXT("(c) dt = 20초 → 상한 64스텝")},
	};
	for (const FCase& C : Cases)
	{
		EcoScheduleTestImpl::FScheduleRig Rig;
		if (!Rig.Init(*this) || !TestNotNull(TEXT("피식 서브시스템"), Rig.Sub()))
		{
			return false;
		}
		Rig.AddHerb(3);
		Rig.PrimeEma();
		int32 Decisions = 0;
		for (int32 f = 0; f < C.Frames; ++f)
		{
			Decisions += Rig.Frame(C.Dt, nullptr, true);
		}
		TestEqual(FString::Printf(TEXT("%s: 결정은 프레임당 최대 1번"), C.Name), Decisions, C.Decisions);
		TestEqual(FString::Printf(TEXT("%s: 위상"), C.Name), Rig.Phase(0), C.Phase);
		TestTrue(FString::Printf(TEXT("%s: EMA %.6f == %.6f (%d스텝)"), C.Name, Rig.Sub()->GetRawEma(),
								 EcoScheduleTestImpl::EmaAfter(C.EmaSteps), C.EmaSteps),
				 FMath::IsNearlyEqual(Rig.Sub()->GetRawEma(), EcoScheduleTestImpl::EmaAfter(C.EmaSteps), 1e-6f));
	}

	// (d) 0·음수·NaN·Inf 프레임은 시간이 흐르지 않은 것으로 본다.
	{
		EcoScheduleTestImpl::FScheduleRig Rig;
		if (!Rig.Init(*this) || !TestNotNull(TEXT("피식 서브시스템"), Rig.Sub()))
		{
			return false;
		}
		Rig.AddHerb(3);
		Rig.PrimeEma();
		int32 Decisions = 0;
		for (int32 f = 0; f < 16; ++f) { Decisions += Rig.Frame(0.0f, nullptr, true); }
		for (const float Bad : {-1.0f, std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity()})
		{
			for (int32 f = 0; f < 2; ++f) { Decisions += Rig.Frame(Bad, nullptr, true); }
		}
		TestEqual(TEXT("(d) 시간이 흐르지 않으면 결정하지 않는다"), Decisions, 0);
		TestEqual(TEXT("(d) 위상 그대로"), Rig.Phase(0), 3);
		TestEqual(TEXT("(d) EMA 스텝 없음"), Rig.Sub()->GetRawEma(), 0.0f);
		int32 FirstFrame = 0;
		for (int32 f = 1; f <= 8 && FirstFrame == 0; ++f)
		{
			if (Rig.Frame(1.0f / 60.0f, nullptr, true) > 0) { FirstFrame = f; }
		}
		TestEqual(TEXT("(d) 이어서 60FPS 로 돌리면 위상 3 개체는 5프레임째에 결정한다"), FirstFrame, 5);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoScheduleSpawnSentinelTest,
	"AdaptiveEcosystem.Policy.Schedule.SpawnPhaseSentinel",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoScheduleSpawnSentinelTest::RunTest(const FString& Parameters)
{
	// 트레잇 템플릿 값은 모든 개체에 복사된다. 템플릿에서 난수를 뽑으면 위상이 하나로 몰린다.
	// 그래서 트레잇은 -1(미배정)을 두고, 정책 프로세서가 엔티티 인덱스로 흩는다.
	EcoScheduleTestImpl::FScheduleRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	for (int32 k = 0; k < Interval; ++k)
	{
		Rig.AddHerb(-1);
	}
	for (int32 f = 1; f <= Interval; ++f)
	{
		TestEqual(FString::Printf(TEXT("%d프레임째에 정확히 1마리가 결정한다"), f), Rig.Frame(1.0f / 60.0f), 1);
	}
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

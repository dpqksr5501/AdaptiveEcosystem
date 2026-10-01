// §4.2 포획 규칙이 파이썬과 같은지 본다.
//
// 파이썬 env/world.py 의 포식자 스텝:
//   perceived = dist × (초식이 은신처 안이면 cover_hide_mult)
//   hunting   = pred_cd == 0
//   hit       = perceived <= pred_catch_r & hunting      ← 초식의 시야와 무관하다
//   포식자당 한 스텝 한 마리. 잡으면 pred_cd = pred_eat_cd
//
// 예전 UEcoPredationProcessor 는 초식이 **본** 포식자까지의 거리(DistPredMin)로 판정했다.
// 그 값은 초식 시야(120°) 안의 포식자만 센다. 그래서
//   - 뒤에서 쫓아온 포식자에게는 절대 잡히지 않았다 — 추격은 대개 뒤에서 일어난다
//   - 은신처가 포식자에게 아무 효과가 없었다 (bInCover 를 아무도 안 읽었다)
//   - 한 포식자가 한 틱에 여러 마리를, 쿨다운 없이 잡을 수 있었다
// 정책은 파이썬 규칙에서 학습됐으니, 언리얼 규칙이 다르면 비교 자체가 성립하지 않는다.

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorConfig.h"
#include "../EcoBehaviorFragments.h"
#include "../EcoBehaviorProcessors.h"
#include "../EcoRegionPredationSubsystem.h"
#include "../EcoWorldProviders.h"
#include "EcoTestWorld.h"
#include "Kismet/GameplayStatics.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassMovementFragments.h"

namespace EcoPredationTestImpl
{
	constexpr float Dt = 1.0f / 60.0f;

	/** 게더 → 지각 → 포식 세 프로세서와 엔티티 두 종류를 갖춘 최소 환경. */
	struct FRig
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager* EM = nullptr;
		FMassArchetypeHandle HerbArch;
		FMassArchetypeHandle PredArch;
		UEcoNeighborhoodGatherProcessor* Gather = nullptr;
		UEcoPerceptionProcessor* Perception = nullptr;
		UEcoPolicyProcessor* Policy = nullptr;
		UEcoPredationProcessor* Predation = nullptr;

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
			PredArch = EM->CreateArchetype({
				FTransformFragment::StaticStruct(),
				FMassVelocityFragment::StaticStruct(),
				FEcoPredatorStateFragment::StaticStruct(),
				FEcoPredatorTag::StaticStruct(),
			});

			const TSharedRef<FMassEntityManager> Shared = EM->AsShared();
			Gather = NewObject<UEcoNeighborhoodGatherProcessor>(Scoped.World);
			Perception = NewObject<UEcoPerceptionProcessor>(Scoped.World);
			Policy = NewObject<UEcoPolicyProcessor>(Scoped.World);
			Predation = NewObject<UEcoPredationProcessor>(Scoped.World);
			for (UMassProcessor* P : {static_cast<UMassProcessor*>(Gather),
									  static_cast<UMassProcessor*>(Perception),
									  static_cast<UMassProcessor*>(Policy),
									  static_cast<UMassProcessor*>(Predation)})
			{
				P->CallInitialize(Scoped.World, Shared);
			}
			return true;
		}

		/** Heading 은 속도로 준다 — 지각 프로세서가 속도에서 시야 방향을 만든다. */
		FMassEntityHandle AddHerbivore(const FVector& Location, const FVector& Heading)
		{
			const FMassEntityHandle E = EM->CreateEntity(HerbArch);
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform()
				.SetLocation(Location);
			EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value =
				Heading.GetSafeNormal() * 10.0f;
			return E;
		}

		FMassEntityHandle AddPredator(const FVector& Location)
		{
			const FMassEntityHandle E = EM->CreateEntity(PredArch);
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform()
				.SetLocation(Location);
			EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value = FVector(10, 0, 0);
			return E;
		}

		void Tick()
		{
			EcoTest::RunProcessor(*Gather, *EM, Dt);
			EcoTest::RunProcessor(*Perception, *EM, Dt);
			EcoTest::RunProcessor(*Predation, *EM, Dt);
			EcoTest::FlushPhase(*EM);
		}

		/** 실제 프레임 순서 (Gather → Perception → Policy → Predation, 페이즈 끝 반영). */
		void TickWithPolicy()
		{
			EcoTest::RunProcessor(*Gather, *EM, Dt);
			EcoTest::RunProcessor(*Perception, *EM, Dt);
			EcoTest::RunProcessor(*Policy, *EM, Dt);
			EcoTest::RunProcessor(*Predation, *EM, Dt);
			EcoTest::FlushPhase(*EM);
		}

		float HP(const FMassEntityHandle& E) const
		{
			return EM->GetFragmentDataChecked<FEcoVitalsFragment>(E).HP;
		}

		UEcoRegionPredationSubsystem* Sub() const
		{
			return Scoped.World->GetSubsystem<UEcoRegionPredationSubsystem>();
		}

		/** 포식자(원점)에서 멀리, 옛 지역 격자 여러 칸에 걸쳐 초식을 늘어놓는다. */
		void AddFillers(int32 Count, float Y, bool bDead = false)
		{
			for (int32 i = 0; i < Count; ++i)
			{
				const FMassEntityHandle E = AddHerbivore(FVector(-19000.0f + 300.0f * i, Y, 0.0f), FVector(1, 0, 0));
				if (bDead)
				{
					EM->GetFragmentDataChecked<FEcoVitalsFragment>(E).HP = 0.0f;
					EM->SwapTagsForEntity(E, FEcoAliveTag::StaticStruct(), FEcoPendingDeathTag::StaticStruct());
				}
			}
		}
	};

	/** 파이썬 world.py: ema += (1-decay) * (deaths / N) * gain — 사망 1건의 증가량. */
	float PerCatch(int32 Population)
	{
		return (1.0f - EcoBehaviorConfig::PredationEmaDecay)
			 * (1.0f / static_cast<float>(Population)) * EcoBehaviorConfig::PredationEmaGain;
	}

	constexpr float EmaTol = 1e-6f;
}

using namespace EcoPredationTestImpl;

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationFromBehindTest,
	"AdaptiveEcosystem.Policy.Predation.FromBehind",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationFromBehindTest::RunTest(const FString& Parameters)
{
	FRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}

	// 초식은 +X 로 달리고 포식자는 바로 뒤 150cm — 초식 시야(120°) 밖, 포획 거리(200cm) 안.
	const FMassEntityHandle H = Rig.AddHerbivore(FVector(0, 0, 0), FVector(1, 0, 0));
	Rig.AddPredator(FVector(-150, 0, 0));
	Rig.Tick();

	// 전제: 초식은 이 포식자를 못 본다. 그래야 이 테스트가 뜻하는 것을 검사한다.
	TestEqual(TEXT("전제: 뒤의 포식자는 초식 시야 밖이다"),
			  Rig.EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(H).PredatorCount, 0);
	TestEqual(TEXT("뒤에서 쫓아온 포식자에게도 잡혀야 한다 (파이썬 §4.2 는 초식 시야와 무관)"),
			  Rig.HP(H), 0.0f);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationOnePerTickCooldownTest,
	"AdaptiveEcosystem.Policy.Predation.OnePerTickAndCooldown",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationOnePerTickCooldownTest::RunTest(const FString& Parameters)
{
	FRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}

	// 포식자 하나 곁에 초식 둘, 둘 다 포획 거리 안. 둘 다 포식자를 바라본다 —
	// 시야 문제와 섞이지 않게 해서 "한 마리 제한"과 "쿨다운"만 본다.
	const FMassEntityHandle Near = Rig.AddHerbivore(FVector(100, 0, 0), FVector(-1, 0, 0));
	const FMassEntityHandle Far = Rig.AddHerbivore(FVector(0, 180, 0), FVector(0, -1, 0));
	Rig.AddPredator(FVector(0, 0, 0));

	Rig.Tick();
	TestEqual(TEXT("한 틱에 한 마리 — 가까운 쪽이 잡힌다"), Rig.HP(Near), 0.0f);
	TestTrue(TEXT("먼 쪽은 이번 틱에 살아 있어야 한다 (포식자당 한 스텝 한 마리)"),
			 Rig.HP(Far) > 0.0f);

	// 식사 쿨다운 = pred_eat_cd × StepSeconds. 부동소수 누적 오차로 ±1틱 흔들릴 수 있어
	// 경계 양쪽에 2틱씩 여유를 둔다.
	const int32 CooldownTicks =
		FMath::RoundToInt(EcoBehaviorConfig::PredEatCooldownS / Dt);
	for (int32 t = 0; t < CooldownTicks - 2; ++t)
	{
		Rig.Tick();
	}
	TestTrue(FString::Printf(TEXT("쿨다운(%d틱) 동안은 곁에 있어도 못 잡는다"), CooldownTicks),
			 Rig.HP(Far) > 0.0f);

	for (int32 t = 0; t < 4; ++t)
	{
		Rig.Tick();
	}
	TestEqual(TEXT("쿨다운이 끝나면 다시 잡는다"), Rig.HP(Far), 0.0f);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationCoverTest,
	"AdaptiveEcosystem.Policy.Predation.CoverHidesDistance",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationCoverTest::RunTest(const FString& Parameters)
{
	FRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}

	const UEcoDummyWorldProviderSubsystem* Dummy =
		Rig.Scoped.World->GetSubsystem<UEcoDummyWorldProviderSubsystem>();
	if (!TestNotNull(TEXT("더미 월드 제공자"), Dummy))
	{
		return false;
	}
	// 더미 은신처는 (±R, ±R), R = WorldExtent × 0.45 에 있다 (EcoWorldProviders.cpp).
	const float R = Dummy->WorldExtent * 0.45f;
	const FVector C(R, R, 0.0f);
	if (!TestTrue(TEXT("전제: 은신처 중심은 은신처 안이다"), Dummy->IsInCover(C)))
	{
		return false;
	}

	const float Hide = EcoBehaviorConfig::CoverHideMult;
	const float CatchR = EcoBehaviorConfig::PredCatchRadiusCm;

	// 150cm → 체감 150 × 2.5 = 375cm. 포획 거리 200cm 밖이다.
	const FMassEntityHandle Hidden = Rig.AddHerbivore(C + FVector(150, 0, 0), FVector(-1, 0, 0));
	Rig.AddPredator(C);
	Rig.Tick();
	TestTrue(FString::Printf(TEXT("은신처 안 150cm 는 체감 %.0fcm > %.0fcm — 잡히면 안 된다"),
							 150.0f * Hide, CatchR),
			 Rig.HP(Hidden) > 0.0f);

	// 70cm → 체감 175cm. 은신처 안이어도 이 거리면 잡힌다.
	const FMassEntityHandle Close = Rig.AddHerbivore(C + FVector(0, 70, 0), FVector(0, -1, 0));
	Rig.Tick();
	TestEqual(FString::Printf(TEXT("은신처 안 70cm 는 체감 %.0fcm <= %.0fcm — 잡혀야 한다"),
							  70.0f * Hide, CatchR),
			  Rig.HP(Close), 0.0f);
	return true;
}

// -----------------------------------------------------------------------------
// 관측 5(recent_predation)의 피식 EMA. 파이썬 world.py 는 전역 스칼라 하나다:
//   ema = decay*ema + (1-decay) * (그 스텝 피식 사망 수 / 개체 수 N) * gain
// 예전 언리얼은 개체마다 ReportPopulation(위치, 1) 을 부르고 받는 쪽이 max 를 취해 분모가 늘 1이었다.
// 피식 1건이 EMA 를 0.5 올렸다(파이썬 128마리면 0.0039). 지역별로 나뉘어 있기도 했다.
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationEmaPerCatchTest,
	"AdaptiveEcosystem.Policy.Predation.EmaPerCatchMatchesPython",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationEmaPerCatchTest::RunTest(const FString& Parameters)
{
	FRig Rig;
	if (!Rig.Init(*this) || !TestNotNull(TEXT("피식 서브시스템"), Rig.Sub()))
	{
		return false;
	}
	const FMassEntityHandle V = Rig.AddHerbivore(FVector(100, 0, 0), FVector(-1, 0, 0));
	Rig.AddFillers(127, 5000.0f);   // 산 초식 128
	Rig.AddPredator(FVector(0, 0, 0));

	Rig.Tick();   // 한 틱 — 자동 EMA 스텝은 아직 없다
	TestEqual(TEXT("전제: V 가 잡혔다"), Rig.HP(V), 0.0f);
	Rig.Sub()->Tick();
	const float Got = Rig.Sub()->Get(FVector(100, 0, 0));
	TestTrue(FString::Printf(TEXT("128마리 중 1건 = %.7f (파이썬과 같아야 한다), 실제 %.7f"), PerCatch(128), Got),
			 FMath::IsNearlyEqual(Got, PerCatch(128), EmaTol));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationEmaGlobalTest,
	"AdaptiveEcosystem.Policy.Predation.EmaIsGlobal",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationEmaGlobalTest::RunTest(const FString& Parameters)
{
	FRig Rig;
	if (!Rig.Init(*this) || !TestNotNull(TEXT("피식 서브시스템"), Rig.Sub()))
	{
		return false;
	}
	Rig.AddHerbivore(FVector(100, 0, 0), FVector(-1, 0, 0));
	Rig.AddHerbivore(FVector(40000, 0, 0), FVector(1, 0, 0));   // 먼 곳의 산 개체
	Rig.AddFillers(126, 5000.0f);
	Rig.AddPredator(FVector(0, 0, 0));

	Rig.Tick();
	Rig.Sub()->Tick();
	const float Here = Rig.Sub()->Get(FVector(100, 0, 0));
	const float Far = Rig.Sub()->Get(FVector(40000, 0, 0));
	const float Empty = Rig.Sub()->Get(FVector(1e6, 1e6, 0));
	TestTrue(FString::Printf(TEXT("포획 지점 %.7f == 기대 %.7f"), Here, PerCatch(128)),
			 FMath::IsNearlyEqual(Here, PerCatch(128), EmaTol));
	TestTrue(FString::Printf(TEXT("먼 곳도 같은 전역 값 (%.7f)"), Far), FMath::IsNearlyEqual(Far, Here, EmaTol));
	TestTrue(FString::Printf(TEXT("아무도 없는 곳도 같은 전역 값 (%.7f)"), Empty), FMath::IsNearlyEqual(Empty, Here, EmaTol));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationEmaDenominatorTest,
	"AdaptiveEcosystem.Policy.Predation.EmaDenominatorAliveMaxOverStep",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationEmaDenominatorTest::RunTest(const FString& Parameters)
{
	// 분모 = 스텝 동안 보고된 '포획 전 생존 초식 수'의 최대값 (= 파이썬 N). 죽은 개체는 세지 않는다.
	FRig Rig;
	if (!Rig.Init(*this) || !TestNotNull(TEXT("피식 서브시스템"), Rig.Sub()))
	{
		return false;
	}
	Rig.AddHerbivore(FVector(100, 0, 0), FVector(-1, 0, 0));
	Rig.AddFillers(127, 5000.0f);                       // 산 초식 128
	Rig.AddFillers(32, -5000.0f, /*bDead*/ true);       // 시체 32 — 분모에 들어가면 안 된다
	Rig.AddPredator(FVector(0, 0, 0));

	// PolicyInterval-1 틱: 자동 스텝 직전까지. 첫 틱에 128, 이후 127 이 보고된다 → 최대값 128.
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	for (int32 t = 0; t < Interval - 1; ++t)
	{
		Rig.Tick();
	}
	Rig.Sub()->Tick();
	const float Got = Rig.Sub()->Get(FVector(100, 0, 0));
	TestTrue(FString::Printf(TEXT("분모는 산 개체 최대값 128 → %.7f, 실제 %.7f"), PerCatch(128), Got),
			 FMath::IsNearlyEqual(Got, PerCatch(128), EmaTol));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationEmaStepOwnerTest,
	"AdaptiveEcosystem.Policy.Predation.EmaStepOwnedByPredationProcessor",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationEmaStepOwnerTest::RunTest(const FString& Parameters)
{
	// EMA 스텝은 포획을 보고하는 프로세서가 직접 한다. 정책 프로세서가 빠지거나 정책 대상
	// 아키타입이 없어도 피식 기록이 멈추면 안 된다.
	FRig Rig;
	if (!Rig.Init(*this) || !TestNotNull(TEXT("피식 서브시스템"), Rig.Sub()))
	{
		return false;
	}
	Rig.AddHerbivore(FVector(100, 0, 0), FVector(-1, 0, 0));
	Rig.AddFillers(127, 5000.0f);
	Rig.AddPredator(FVector(0, 0, 0));

	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	float First = 0.0f;
	for (int32 t = 0; t < 2 * Interval && First == 0.0f; ++t)
	{
		Rig.Tick();   // Policy 없이
		First = Rig.Sub()->Get(FVector(100, 0, 0));
	}
	TestTrue(TEXT("Policy 없이도 EMA 가 스텝한다"), First > 0.0f);
	TestTrue(FString::Printf(TEXT("첫 값 = %.7f, 실제 %.7f"), PerCatch(128), First),
			 FMath::IsNearlyEqual(First, PerCatch(128), EmaTol));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationObsReadsGlobalTest,
	"AdaptiveEcosystem.Policy.Predation.ObservationReadsGlobalEma",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationObsReadsGlobalTest::RunTest(const FString& Parameters)
{
	// 포획 → EMA 스텝 → 다음 결정의 관측 (world.py: 포획 → EMA → 관측). 포획 지점 근처의 개체와
	// 먼 개체가 같은 값을 본다.
	FRig Rig;
	if (!Rig.Init(*this) || !TestNotNull(TEXT("피식 서브시스템"), Rig.Sub()))
	{
		return false;
	}
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	Rig.AddHerbivore(FVector(100, 0, 0), FVector(-1, 0, 0));
	const FMassEntityHandle C = Rig.AddHerbivore(FVector(0, 3000, 0), FVector(1, 0, 0));   // 포획 지점 근처
	const FMassEntityHandle B = Rig.AddHerbivore(FVector(40000, 0, 0), FVector(1, 0, 0));  // 먼 곳
	Rig.AddFillers(125, 5000.0f);   // 산 초식 128
	Rig.AddPredator(FVector(0, 0, 0));
	// B, C 는 1틱째와 Interval+1 틱째에 결정한다 — 첫 EMA 스텝(Interval 틱째 끝) 바로 다음이다.
	for (const FMassEntityHandle& E : {B, C})
	{
		Rig.EM->GetFragmentDataChecked<FEcoPolicyRuntimeFragment>(E).LastPolicyStep = Interval - 1;
	}

	for (int32 t = 0; t < Interval + 1; ++t)
	{
		Rig.TickWithPolicy();
	}
	const float ObsB = Rig.EM->GetFragmentDataChecked<FEcoObservationFragment>(B).Observation.RecentPredation;
	const float ObsC = Rig.EM->GetFragmentDataChecked<FEcoObservationFragment>(C).Observation.RecentPredation;
	TestTrue(FString::Printf(TEXT("근처 개체 관측 %.7f == %.7f"), ObsC, PerCatch(128)),
			 FMath::IsNearlyEqual(ObsC, PerCatch(128), EmaTol));
	TestTrue(FString::Printf(TEXT("먼 개체 관측 %.7f == %.7f"), ObsB, PerCatch(128)),
			 FMath::IsNearlyEqual(ObsB, PerCatch(128), EmaTol));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationEmaFormulaTest,
	"AdaptiveEcosystem.Policy.Predation.EmaFormulaSequence",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationEmaFormulaTest::RunTest(const FString& Parameters)
{
	// 식 고정용. 기대값은 같은 float 식으로 테스트 안에서 계산한다.
	EcoTest::FScopedTestWorld Scoped;
	UEcoRegionPredationSubsystem* Sub =
		Scoped.World ? Scoped.World->GetSubsystem<UEcoRegionPredationSubsystem>() : nullptr;
	if (!TestNotNull(TEXT("피식 서브시스템"), Sub))
	{
		return false;
	}
	const float D = EcoBehaviorConfig::PredationEmaDecay;
	const float G = EcoBehaviorConfig::PredationEmaGain;
	auto Step = [&](float Prev, int32 Deaths, int32 Denom)
	{
		return D * Prev + (1.0f - D) * (static_cast<float>(Deaths) / static_cast<float>(Denom)) * G;
	};
	auto Deaths = [&](int32 N) { for (int32 i = 0; i < N; ++i) { Sub->ReportPredation(FVector::ZeroVector); } };

	Sub->ReportAlivePopulation(128); Deaths(3); Sub->Tick();
	const float E1 = Step(0.0f, 3, 128);
	TestTrue(TEXT("s1: 128마리 중 3건"), FMath::IsNearlyEqual(Sub->GetRawEma(), E1, EmaTol));

	Sub->ReportAlivePopulation(128); Sub->Tick();
	const float E2 = Step(E1, 0, 128);
	TestTrue(TEXT("s2: 사망 없음 → 감쇠만"), FMath::IsNearlyEqual(Sub->GetRawEma(), E2, EmaTol));

	Sub->ReportAlivePopulation(100); Sub->ReportAlivePopulation(90); Deaths(1); Sub->Tick();
	const float E3 = Step(E2, 1, 100);
	TestTrue(TEXT("s3: 스텝 안 최대값(100)을 분모로"), FMath::IsNearlyEqual(Sub->GetRawEma(), E3, EmaTol));

	Sub->Tick();
	const float E4 = Step(E3, 0, 1);
	TestTrue(TEXT("s4: 보고 없음 → 감쇠만"), FMath::IsNearlyEqual(Sub->GetRawEma(), E4, EmaTol));

	Deaths(2); Sub->Tick();
	const float E5 = Step(E4, 2, 2);
	TestTrue(TEXT("s5: 산 개체 0인데 사망 보고(방어값) → 비율 상한 1"), FMath::IsNearlyEqual(Sub->GetRawEma(), E5, EmaTol));

	Sub->ReportAlivePopulation(1); Deaths(1); Sub->Tick();
	Sub->ReportAlivePopulation(1); Deaths(1); Sub->Tick();
	TestTrue(TEXT("s7: 원시 EMA 는 1을 넘을 수 있다"), Sub->GetRawEma() > 1.0f);
	TestEqual(TEXT("s7: 관측은 1로 자른다"), Sub->GetRecentPredation(), 1.0f);
	TestEqual(TEXT("스텝 뒤 누적값은 비워진다"), Sub->GetPendingDeaths(), 0);
	TestEqual(TEXT("스텝 뒤 분모도 비워진다"), Sub->GetStepPopulation(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPredationSaveLoadTest,
	"AdaptiveEcosystem.Policy.Predation.SaveLoadGlobalEma",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoPredationSaveLoadTest::RunTest(const FString& Parameters)
{
	EcoTest::FScopedTestWorld Scoped;
	UEcoRegionPredationSubsystem* Sub =
		Scoped.World ? Scoped.World->GetSubsystem<UEcoRegionPredationSubsystem>() : nullptr;
	if (!TestNotNull(TEXT("피식 서브시스템"), Sub))
	{
		return false;
	}
	const FString SlotV2 = TEXT("EcoPredEmaTest_V2");
	const FString SlotV1 = TEXT("EcoPredEmaTest_V1");
	UGameplayStatics::DeleteGameInSlot(SlotV2, 0);
	UGameplayStatics::DeleteGameInSlot(SlotV1, 0);

	Sub->ReportAlivePopulation(128);
	Sub->ReportPredation(FVector::ZeroVector);
	Sub->Tick();
	const float E1 = Sub->GetRawEma();
	TestTrue(TEXT("저장 성공"), Sub->SaveToSlot(SlotV2));

	Sub->ReportAlivePopulation(128);
	Sub->Tick();
	TestTrue(TEXT("불러오기 성공"), Sub->LoadFromSlot(SlotV2));
	TestTrue(TEXT("저장 시점 값으로 돌아간다"), FMath::IsNearlyEqual(Sub->GetRawEma(), E1, EmaTol));
	TestEqual(TEXT("불러오면 누적값은 비어 있다"), Sub->GetPendingDeaths(), 0);

	// v1 지역별 저장(스키마 0)은 분모 버그 값이라 거부한다.
	UEcoPredationSaveGame* Old = Cast<UEcoPredationSaveGame>(
		UGameplayStatics::CreateSaveGameObject(UEcoPredationSaveGame::StaticClass()));
	if (TestNotNull(TEXT("옛 형식 저장 객체"), Old))
	{
		Old->SchemaVersion = 0;
		Old->Ema = 0.7f;
		TestTrue(TEXT("옛 형식 파일 쓰기"), UGameplayStatics::SaveGameToSlot(Old, SlotV1, 0));
		AddExpectedMessagePlain(TEXT("EcoRegionPredation: SchemaVersion"), ELogVerbosity::Warning,
								EAutomationExpectedMessageFlags::Contains, 1);
		TestFalse(TEXT("옛 형식은 불러오지 않는다"), Sub->LoadFromSlot(SlotV1));
		TestTrue(TEXT("값은 그대로다"), FMath::IsNearlyEqual(Sub->GetRawEma(), E1, EmaTol));
	}
	TestFalse(TEXT("없는 슬롯은 실패"), Sub->LoadFromSlot(TEXT("EcoPredEmaTest_None")));

	UGameplayStatics::DeleteGameInSlot(SlotV2, 0);
	UGameplayStatics::DeleteGameInSlot(SlotV1, 0);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

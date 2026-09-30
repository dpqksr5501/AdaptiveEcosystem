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
#include "../EcoWorldProviders.h"
#include "EcoTestWorld.h"
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

			HerbArch = EM->CreateArchetype({
				FTransformFragment::StaticStruct(),
				FMassVelocityFragment::StaticStruct(),
				FEcoSteeringGeometryFragment::StaticStruct(),
				FEcoObservationFragment::StaticStruct(),
				FEcoPolicyOutputFragment::StaticStruct(),
				FEcoPolicyRuntimeFragment::StaticStruct(),
				FEcoVitalsFragment::StaticStruct(),
				FEcoHerbivoreTag::StaticStruct(),
			});
			PredArch = EM->CreateArchetype({
				FTransformFragment::StaticStruct(),
				FMassVelocityFragment::StaticStruct(),
				FEcoPredatorStateFragment::StaticStruct(),
				FEcoPredatorTag::StaticStruct(),
			});

			const TSharedRef<FMassEntityManager> Shared = EM->AsShared();
			Gather = NewObject<UEcoNeighborhoodGatherProcessor>(Scoped.World);
			Perception = NewObject<UEcoPerceptionProcessor>(Scoped.World);
			Predation = NewObject<UEcoPredationProcessor>(Scoped.World);
			for (UMassProcessor* P : {static_cast<UMassProcessor*>(Gather),
									  static_cast<UMassProcessor*>(Perception),
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
		}

		float HP(const FMassEntityHandle& E) const
		{
			return EM->GetFragmentDataChecked<FEcoVitalsFragment>(E).HP;
		}
	};
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

#endif // WITH_DEV_AUTOMATION_TESTS

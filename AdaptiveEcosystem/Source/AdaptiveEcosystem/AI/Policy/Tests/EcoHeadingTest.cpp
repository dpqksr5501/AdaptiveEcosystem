// 조향이 개체의 바라보는 방향(yaw)을 쓰는지 본다.
//
// 파이썬 env/world.py: 움직일 때만 head = normalize(v), 멈추면 유지. 시야(FOV 120°)는 head 기준이다.
// 예전 UEcoSteeringProcessor 는 위치만 적분하고 회전을 쓰지 않았다. 그래서 멈춘 개체는 지각이
// Transform 전방(+X 고정)을 앞으로 봐서, 방금 도망쳐 온 방향의 포식자와 동료를 못 봤다.
// 복제되는 yaw 도 고정이었다.
//
// 기준값은 구현과 독립적으로 여기서 계산한다(EcoHeading.h 를 include 하지 않는다).

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorConfig.h"
#include "../EcoBehaviorFragments.h"
#include "../EcoBehaviorProcessors.h"
#include "../EcoNeighborhoodSubsystem.h"
#include "../EcoWorldProviders.h"
#include "EcoTestWorld.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassMovementFragments.h"

namespace EcoHeadingTestImpl
{
	constexpr float HeadingDt = 1.0f / 60.0f;

	struct FHeadingRig
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager* EM = nullptr;
		const UEcoDummyWorldProviderSubsystem* Dummy = nullptr;
		FMassArchetypeHandle HerbArch;
		FMassArchetypeHandle PredArch;
		UEcoNeighborhoodGatherProcessor* Gather = nullptr;
		UEcoPerceptionProcessor* Perception = nullptr;
		UEcoSteeringProcessor* Steering = nullptr;

		bool Init(FAutomationTestBase& Test)
		{
			if (!Test.TestNotNull(TEXT("테스트 월드"), Scoped.World))
			{
				return false;
			}
			UMassEntitySubsystem* Sub = Scoped.World->GetSubsystem<UMassEntitySubsystem>();
			Dummy = Scoped.World->GetSubsystem<UEcoDummyWorldProviderSubsystem>();
			if (!Test.TestNotNull(TEXT("UMassEntitySubsystem"), Sub)
				|| !Test.TestNotNull(TEXT("더미 월드 제공자"), Dummy)
				|| !Test.TestNotNull(TEXT("UEcoWorldProviderRegistry"), Scoped.World->GetSubsystem<UEcoWorldProviderRegistry>())
				|| !Test.TestNotNull(TEXT("UEcoNeighborhoodSubsystem"), Scoped.World->GetSubsystem<UEcoNeighborhoodSubsystem>()))
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
			Steering = NewObject<UEcoSteeringProcessor>(Scoped.World);
			for (UMassProcessor* P : {static_cast<UMassProcessor*>(Gather),
									  static_cast<UMassProcessor*>(Perception),
									  static_cast<UMassProcessor*>(Steering)})
			{
				P->CallInitialize(Scoped.World, Shared);
			}
			return true;
		}

		/** 정지, 회전 identity 로 만든다. */
		FMassEntityHandle AddHerbivore(const FVector& Location)
		{
			const FMassEntityHandle E = EM->CreateEntity(HerbArch);
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(Location);
			return E;
		}

		FMassEntityHandle AddPredator(const FVector& Location)
		{
			const FMassEntityHandle E = EM->CreateEntity(PredArch);
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(Location);
			return E;
		}

		/** 조향이 Dir 방향(무리 중심 항만)으로 가게 입력을 준다. */
		void Command(FMassEntityHandle E, const FVector& Dir)
		{
			FEcoSteeringGeometryFragment& G = EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E);
			G = FEcoSteeringGeometryFragment();
			G.ToCentroid = Dir.GetSafeNormal2D();
			FEcoPolicyActionV1& A = EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
			A.Forage = 0.0f;
			A.Cohesion = 1.0f;
			A.FleeDist = 0.0f;
			A.Cover = 0.0f;
		}

		/** 조향 입력을 모두 0으로 — Steer() 가 정확히 0을 낸다. */
		void Stop(FMassEntityHandle E)
		{
			EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E) = FEcoSteeringGeometryFragment();
			FEcoPolicyActionV1& A = EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
			A.Forage = 0.0f;
			A.Cohesion = 0.0f;
			A.FleeDist = 0.0f;
			A.Cover = 0.0f;
		}

		void RunSteer() { EcoTest::RunProcessor(*Steering, *EM, HeadingDt); EcoTest::FlushPhase(*EM); }
		void Sense()
		{
			EcoTest::RunProcessor(*Gather, *EM, HeadingDt);
			EcoTest::RunProcessor(*Perception, *EM, HeadingDt);
			EcoTest::FlushPhase(*EM);
		}

		FVector Fwd(FMassEntityHandle E) const
		{
			return EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetRotation().GetForwardVector();
		}
		FVector Vel(FMassEntityHandle E) const { return EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value; }
		FVector Pos(FMassEntityHandle E) const
		{
			return EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
		}
		const FEcoSteeringGeometryFragment& Geo(FMassEntityHandle E) const
		{
			return EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E);
		}
	};
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoHeadingYawFollowsVelocityTest,
	"AdaptiveEcosystem.Policy.Heading.YawFollowsVelocity",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoHeadingYawFollowsVelocityTest::RunTest(const FString& Parameters)
{
	EcoHeadingTestImpl::FHeadingRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	const FMassEntityHandle H = Rig.AddHerbivore(FVector::ZeroVector);
	const FVector D(FMath::Cos(FMath::DegreesToRadians(135.0f)), FMath::Sin(FMath::DegreesToRadians(135.0f)), 0.0f);
	Rig.Command(H, D);
	Rig.RunSteer();

	const float Speed = EcoBehaviorConfig::HerbSpeedCmS;
	TestTrue(FString::Printf(TEXT("전제: 속도 = 방향 × %.0f (%s)"), Speed, *Rig.Vel(H).ToString()),
			 Rig.Vel(H).Equals(D * Speed, 0.5));
	const FVector F = Rig.Fwd(H);
	TestTrue(FString::Printf(TEXT("전방 = 속도 방향 (dot %.6f)"), FVector::DotProduct(F, D)),
			 FVector::DotProduct(F, D) >= 1.0 - 1e-5);
	TestTrue(TEXT("Z축 회전만 쓴다"), FMath::Abs(F.Z) < 1e-5);
	const FRotator R = Rig.EM->GetFragmentDataChecked<FTransformFragment>(H).GetTransform().Rotator();
	TestTrue(FString::Printf(TEXT("yaw 135° (%.3f), pitch/roll 0"), R.Yaw),
			 FMath::Abs(R.Yaw - 135.0) < 0.01 && FMath::Abs(R.Pitch) < 0.01 && FMath::Abs(R.Roll) < 0.01);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoHeadingHeldWhenStoppedTest,
	"AdaptiveEcosystem.Policy.Heading.HeldWhenStopped",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoHeadingHeldWhenStoppedTest::RunTest(const FString& Parameters)
{
	// -X 로 움직였다가 멈춘 개체는 -X 를 계속 본다. 그래서 그쪽의 동료와 포식자가 시야에 남는다.
	EcoHeadingTestImpl::FHeadingRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	const FMassEntityHandle H = Rig.AddHerbivore(FVector::ZeroVector);
	const FMassEntityHandle K = Rig.AddHerbivore(FVector(-2000, 0, 0));
	Rig.AddPredator(FVector(-2000, 300, 0));

	Rig.Command(H, FVector(-1, 0, 0));
	Rig.Stop(K);
	Rig.RunSteer();
	TestTrue(TEXT("전제: H 는 -X 로 움직였다"), Rig.Vel(H).X < -1.0f);

	Rig.Stop(H);
	Rig.RunSteer();
	TestTrue(TEXT("전제: H 는 멈췄다"), Rig.Vel(H).IsNearlyZero());
	TestTrue(FString::Printf(TEXT("멈춰도 마지막 이동 방향을 유지한다 (전방 %s)"), *Rig.Fwd(H).ToString()),
			 FVector::DotProduct(Rig.Fwd(H), FVector(-1, 0, 0)) >= 1.0 - 1e-5);

	Rig.Sense();
	TestEqual(TEXT("앞쪽(-X)의 동료가 보인다"), Rig.Geo(H).KinCount, 1);
	TestEqual(TEXT("앞쪽(-X)의 포식자가 보인다"), Rig.Geo(H).PredatorCount, 1);
	const float Expected = FMath::Sqrt(FMath::Square(2000.0f - 15.0f) + FMath::Square(300.0f));
	TestTrue(FString::Printf(TEXT("포식자 거리 %.1f ≈ %.1f"), Rig.Geo(H).DistPredMin, Expected),
			 FMath::Abs(Rig.Geo(H).DistPredMin - Expected) < 1.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoHeadingBoundaryTest,
	"AdaptiveEcosystem.Policy.Heading.FollowsBoundaryVelocity",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoHeadingBoundaryTest::RunTest(const FString& Parameters)
{
	// 경계 반발까지 반영한 최종 속도 방향을 본다 — 지각이 읽는 값과 같아야 한다.
	EcoHeadingTestImpl::FHeadingRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	const float E = Rig.Dummy->WorldExtent;
	if (!TestTrue(TEXT("전제: 월드 경계가 충분히 크다"), E > 1000.0f))
	{
		return false;
	}
	const FMassEntityHandle H = Rig.AddHerbivore(FVector(E - 10.0f, 0, 0));
	Rig.Command(H, FVector(1, 0, 0));
	Rig.RunSteer();
	TestTrue(FString::Printf(TEXT("전제: 벽에 밀려 -X 로 꺾였다 (%s)"), *Rig.Vel(H).ToString()), Rig.Vel(H).X < 0.0f);
	TestTrue(FString::Printf(TEXT("전방은 최종 속도(-X)를 따른다 (%s)"), *Rig.Fwd(H).ToString()),
			 FVector::DotProduct(Rig.Fwd(H), FVector(-1, 0, 0)) >= 1.0 - 1e-5);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

// 죽은 개체가 관측·정책·조향을 계속 받지 않는지 본다.
//
// 예전에는 포획되면 HP 만 0이 되고 초식 쿼리 다섯 개가 생존 여부를 보지 않았다. 그래서 시체가
// 계속 움직이고, 이웃 색인에 들어가 동료로 세어지고, 포식자의 표적이 됐다. 테스트 레벨은
// 스포너가 같은 프레임에 되살려 이 문제를 가렸다.
//
// 지금 규칙:
//   - 초식 쿼리(Gather, Perception, Policy, Predation, Steering)는 FEcoAliveTag 를 요구한다
//   - 포획하면 HP=0 은 즉시, Alive → PendingDeath 교체는 지연 명령으로 넣는다(페이즈 끝 반영)
//   - 포식 판정은 조향 뒤에 돈다. 잡힌 개체는 그 틱의 정책·조향을 이미 마쳤고,
//     다음 틱부터는 Alive 가 없어 어디에도 걸리지 않는다

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorConfig.h"
#include "../EcoBehaviorFragments.h"
#include "../EcoBehaviorProcessors.h"
#include "../EcoNeighborhoodSubsystem.h"
#include "EcoTestWorld.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassCommandBuffer.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassMovementFragments.h"

namespace EcoAliveFilterTestImpl
{
	constexpr float AliveDt = 1.0f / 60.0f;

	/** 다섯 프로세서와 초식·포식자 아키타입. 테스트마다 돌릴 프로세서를 골라 넘긴다. */
	struct FAliveRig
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager* EM = nullptr;
		UEcoNeighborhoodSubsystem* Grid = nullptr;
		FMassArchetypeHandle HerbArch;
		FMassArchetypeHandle PredArch;
		UEcoNeighborhoodGatherProcessor* Gather = nullptr;
		UEcoPerceptionProcessor* Perception = nullptr;
		UEcoPolicyProcessor* Policy = nullptr;
		UEcoSteeringProcessor* Steering = nullptr;
		UEcoPredationProcessor* Predation = nullptr;

		bool Init(FAutomationTestBase& Test)
		{
			if (!Test.TestNotNull(TEXT("테스트 월드"), Scoped.World))
			{
				return false;
			}
			UMassEntitySubsystem* Sub = Scoped.World->GetSubsystem<UMassEntitySubsystem>();
			Grid = Scoped.World->GetSubsystem<UEcoNeighborhoodSubsystem>();
			if (!Test.TestNotNull(TEXT("UMassEntitySubsystem"), Sub)
				|| !Test.TestNotNull(TEXT("UEcoNeighborhoodSubsystem"), Grid))
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
			Steering = NewObject<UEcoSteeringProcessor>(Scoped.World);
			Predation = NewObject<UEcoPredationProcessor>(Scoped.World);
			for (UMassProcessor* P : {static_cast<UMassProcessor*>(Gather),
									  static_cast<UMassProcessor*>(Perception),
									  static_cast<UMassProcessor*>(Policy),
									  static_cast<UMassProcessor*>(Steering),
									  static_cast<UMassProcessor*>(Predation)})
			{
				P->CallInitialize(Scoped.World, Shared);
			}
			return true;
		}

		FMassEntityHandle AddHerb(const FVector& Location, const FVector& Heading)
		{
			const FMassEntityHandle E = EM->CreateEntity(HerbArch);
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(Location);
			EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value = Heading.GetSafeNormal() * 10.0f;
			return E;
		}

		FMassEntityHandle AddPred(const FVector& Location)
		{
			const FMassEntityHandle E = EM->CreateEntity(PredArch);
			EM->GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(Location);
			EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value = FVector(10, 0, 0);
			return E;
		}

		/** 넘겨받은 프로세서를 차례로 돌리고 페이즈 끝처럼 명령을 반영한다. */
		void Tick(std::initializer_list<UMassProcessor*> Processors)
		{
			for (UMassProcessor* P : Processors)
			{
				EcoTest::RunProcessor(*P, *EM, AliveDt);
			}
			EcoTest::FlushPhase(*EM);
		}

		void TickGatherPerceptionPredation() { Tick({Gather, Perception, Predation}); }

		float HP(FMassEntityHandle E) const { return EM->GetFragmentDataChecked<FEcoVitalsFragment>(E).HP; }
		const FEcoSteeringGeometryFragment& Geo(FMassEntityHandle E) const
		{
			return EM->GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E);
		}
	};
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoAliveCorpseLeavesNeighborhoodTest,
	"AdaptiveEcosystem.Policy.AliveFilter.CorpseLeavesNeighborhood",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoAliveCorpseLeavesNeighborhoodTest::RunTest(const FString& Parameters)
{
	EcoAliveFilterTestImpl::FAliveRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	// O 는 V 를 앞에 두고 같은 방향으로 선다. P 는 V 바로 앞 100cm (포획 거리 200cm 안).
	const FMassEntityHandle O = Rig.AddHerb(FVector(0, 0, 0), FVector(1, 0, 0));
	const FMassEntityHandle V = Rig.AddHerb(FVector(600, 0, 0), FVector(1, 0, 0));
	Rig.AddPred(FVector(700, 0, 0));

	Rig.TickGatherPerceptionPredation();
	TestEqual(TEXT("V 는 잡힌다"), Rig.HP(V), 0.0f);
	TestEqual(TEXT("O 는 700cm 라 살아 있다"), Rig.HP(O), 100.0f);
	TestEqual(TEXT("게더 시점에는 V 가 살아 있어 동료로 센다"), Rig.Geo(O).KinCount, 1);
	TestTrue(TEXT("포획된 V 는 Alive 가 빠지고"), !EcoTest::HasTag<FEcoAliveTag>(*Rig.EM, V));
	TestTrue(TEXT("PendingDeath 가 붙는다"), EcoTest::HasTag<FEcoPendingDeathTag>(*Rig.EM, V));

	Rig.TickGatherPerceptionPredation();
	TestEqual(TEXT("다음 틱 색인에는 O 와 P 만 있다"), Rig.Grid->Num(), 2);
	TestEqual(TEXT("O 는 시체를 동료로 세지 않는다"), Rig.Geo(O).KinCount, 0);
	TestTrue(TEXT("무리 중심 방향도 사라진다"), Rig.Geo(O).ToCentroid.IsNearlyZero());
	TestTrue(TEXT("시체에게서 비키지도 않는다"), Rig.Geo(O).Separation.Size() <= 1e-4);
	TestEqual(TEXT("포식자는 계속 보인다 (필터가 포식자를 지우지 않는다)"), Rig.Geo(O).PredatorCount, 1);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoAliveDeadAgentIsFrozenTest,
	"AdaptiveEcosystem.Policy.AliveFilter.DeadAgentIsFrozen",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoAliveDeadAgentIsFrozenTest::RunTest(const FString& Parameters)
{
	EcoAliveFilterTestImpl::FAliveRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.UseLearnedPolicy"));
	if (!TestNotNull(TEXT("eco.UseLearnedPolicy"), CVar))
	{
		return false;
	}
	const int32 SavedCVar = CVar->GetInt();
	CVar->Set(0, ECVF_SetByCode);

	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	const FMassEntityHandle A = Rig.AddHerb(FVector(0, 0, 0), FVector(1, 0, 0));
	const FMassEntityHandle D = Rig.AddHerb(FVector(500, 0, 0), FVector(1, 0, 0));
	Rig.EM->GetFragmentDataChecked<FEcoVitalsFragment>(D).HP = 0.0f;
	Rig.EM->GetFragmentDataChecked<FEcoPolicyRuntimeFragment>(D).LastPolicyStep = Interval - 1;
	// 처리 중이 아니므로 동기 API 로 시체를 만든다.
	Rig.EM->SwapTagsForEntity(D, FEcoAliveTag::StaticStruct(), FEcoPendingDeathTag::StaticStruct());

	Rig.Tick({Rig.Gather, Rig.Perception, Rig.Policy, Rig.Steering});
	TestEqual(TEXT("색인에는 산 개체 A 만 들어간다"), Rig.Grid->Num(), 1);
	TestEqual(TEXT("A 는 시체를 동료로 세지 않는다"), Rig.Geo(A).KinCount, 0);
	TestTrue(TEXT("A 는 시체에게서 비키지 않는다"), Rig.Geo(A).Separation.Size() <= 1e-4);

	for (int32 t = 1; t < 2 * Interval; ++t)
	{
		Rig.Tick({Rig.Gather, Rig.Perception, Rig.Policy, Rig.Steering});
	}

	const FVector Pos = Rig.EM->GetFragmentDataChecked<FTransformFragment>(D).GetTransform().GetLocation();
	TestTrue(FString::Printf(TEXT("시체는 움직이지 않는다 (%s)"), *Pos.ToString()),
			 Pos.Equals(FVector(500, 0, 0), 0.0));
	TestTrue(TEXT("시체의 속도는 그대로다 (조향이 안 돈다)"),
			 Rig.EM->GetFragmentDataChecked<FMassVelocityFragment>(D).Value.Equals(FVector(10, 0, 0), 0.0));
	const FEcoPolicyActionV1& Act = Rig.EM->GetFragmentDataChecked<FEcoPolicyOutputFragment>(D).Action;
	TestTrue(TEXT("시체는 정책을 돌지 않는다 (행동이 기본값)"),
			 Act.Forage == 0.0f && Act.Cohesion == 0.0f && Act.FleeDist == 0.0f && Act.Cover == 0.0f);
	TestEqual(TEXT("시체의 정책 위상은 그대로다"),
			  Rig.EM->GetFragmentDataChecked<FEcoPolicyRuntimeFragment>(D).LastPolicyStep, Interval - 1);

	float ObsD[7];
	float ObsDefault[7];
	Rig.EM->GetFragmentDataChecked<FEcoObservationFragment>(D).Observation.ToFloatArray(ObsD);
	FEcoPolicyObservationV1().ToFloatArray(ObsDefault);
	bool bSame = true;
	for (int32 i = 0; i < 7; ++i)
	{
		bSame &= (ObsD[i] == ObsDefault[i]);
	}
	TestTrue(TEXT("시체의 관측은 기본값이다"), bSame);

	CVar->Set(SavedCVar, ECVF_SetByCode);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoAlivePredationAfterSteeringTest,
	"AdaptiveEcosystem.Policy.AliveFilter.PredationAfterSteering",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoAlivePredationAfterSteeringTest::RunTest(const FString& Parameters)
{
	// 포획은 이동 뒤에 판정한다 (MASS_PROCESSOR_ORDER.md: Steering → … → Interaction → Lifecycle).
	// 그래야 잡힌 개체가 같은 틱에 정책·조향을 다시 받지 않는다. ExecutionOrder 는 config
	// 프로퍼티라 CDO 를 보면 ini 오버라이드까지 함께 확인된다.
	const FMassProcessorExecutionOrder& Order = GetDefault<UEcoPredationProcessor>()->GetExecutionOrder();
	TestTrue(TEXT("UEcoPredationProcessor 는 UEcoSteeringProcessor 뒤에 돈다"),
			 Order.ExecuteAfter.Contains(UEcoSteeringProcessor::StaticClass()->GetFName()));
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoAliveNoDoubleCatchTest,
	"AdaptiveEcosystem.Policy.AliveFilter.NoDoubleCatchSameTick",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoAliveNoDoubleCatchTest::RunTest(const FString& Parameters)
{
	// 태그 교체는 지연되므로, 같은 틱에 두 포식자가 한 개체를 잡는 것은 HP 검사만 막는다.
	// 그 검사를 지우면 이 테스트가 깨진다.
	EcoAliveFilterTestImpl::FAliveRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	const FMassEntityHandle V = Rig.AddHerb(FVector(0, 0, 0), FVector(1, 0, 0));
	const FMassEntityHandle P1 = Rig.AddPred(FVector(-100, 0, 0));
	const FMassEntityHandle P2 = Rig.AddPred(FVector(100, 0, 0));
	Rig.TickGatherPerceptionPredation();

	TestEqual(TEXT("V 는 잡힌다"), Rig.HP(V), 0.0f);
	const float C1 = Rig.EM->GetFragmentDataChecked<FEcoPredatorStateFragment>(P1).EatCooldown;
	const float C2 = Rig.EM->GetFragmentDataChecked<FEcoPredatorStateFragment>(P2).EatCooldown;
	const int32 Eaters = (C1 > 0.0f ? 1 : 0) + (C2 > 0.0f ? 1 : 0);
	TestEqual(TEXT("한 개체는 한 포식자만 먹는다"), Eaters, 1);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoAliveRespawnRoundTripTest,
	"AdaptiveEcosystem.Policy.AliveFilter.RespawnRoundTrip",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoAliveRespawnRoundTripTest::RunTest(const FString& Parameters)
{
	// 테스트 스포너가 기대는 태그 계약: 포획 → PendingDeath, 되살리면 다시 Alive.
	EcoAliveFilterTestImpl::FAliveRig Rig;
	if (!Rig.Init(*this))
	{
		return false;
	}
	Rig.AddHerb(FVector(0, 0, 0), FVector(1, 0, 0));
	const FMassEntityHandle V = Rig.AddHerb(FVector(600, 0, 0), FVector(1, 0, 0));
	Rig.AddPred(FVector(700, 0, 0));

	Rig.TickGatherPerceptionPredation();
	if (!TestTrue(TEXT("전제: 포획된 V 는 PendingDeath 상태다"),
				  EcoTest::HasTag<FEcoPendingDeathTag>(*Rig.EM, V)))
	{
		return true;
	}

	// 스포너 RespawnCaught 와 같은 순서
	FEcoVitalsFragment& Vitals = Rig.EM->GetFragmentDataChecked<FEcoVitalsFragment>(V);
	Vitals.HP = Vitals.MaxHP;
	Rig.EM->Defer().SwapTags<FEcoPendingDeathTag, FEcoAliveTag>(V);
	EcoTest::FlushPhase(*Rig.EM);

	Rig.TickGatherPerceptionPredation();
	TestEqual(TEXT("되살린 V 가 다시 색인에 들어간다"), Rig.Grid->Num(), 3);
	TestTrue(TEXT("V 는 다시 Alive 다"), EcoTest::HasTag<FEcoAliveTag>(*Rig.EM, V));
	TestTrue(TEXT("PendingDeath 는 빠졌다"), !EcoTest::HasTag<FEcoPendingDeathTag>(*Rig.EM, V));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

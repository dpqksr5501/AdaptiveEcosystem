#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "AI/Policy/Tests/EcoTestWorld.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoBehaviorProcessors.h"
#include "AI/Social/Alarm/EcoThreatDetectionProcessor.h"
#include "AI/Social/Alarm/EcoThreatSourceComponent.h"
#include "AI/Social/Alarm/EcoAlarmProcessors.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/Herd/EcoHerdProcessors.h"
#include "AI/Social/Shelter/EcoShelterProcessors.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassEntitySubsystem.h"
#include "MassProcessorDependencySolver.h"
#include "Components/BoxComponent.h"
#include "GameFramework/Actor.h"

namespace EcoSocialThreatTests
{
	struct FFixture
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager& EM;
		UEcoHerdSubsystem& Herds;
		int32 HerdIndex;
		FMassEntityHandle Observer;
		UEcoNeighborhoodGatherProcessor* Gather;
		UEcoThreatDetectionProcessor* Detect;
		UEcoAlarmPropagationProcessor* Propagate;
		UEcoSocialResponseProcessor* Respond;

		FFixture() : EM(Scoped.World->GetSubsystem<UMassEntitySubsystem>()->GetMutableEntityManager()),
			Herds(*Scoped.World->GetSubsystem<UEcoHerdSubsystem>()),
			HerdIndex(Herds.AllocateHerd(0, FVector(100, 0, 0)))
		{
			const TArray<const UScriptStruct*> Composition = {
				FTransformFragment::StaticStruct(), FMassVelocityFragment::StaticStruct(),
				FEcoIdentityFragment::StaticStruct(), FEcoHerdMemberFragment::StaticStruct(),
				FEcoAlarmStateFragment::StaticStruct(), FEcoSocialBehaviorFragment::StaticStruct(),
				FEcoPolicyOutputFragment::StaticStruct(), FEcoShelterIntentFragment::StaticStruct(),
				FEcoVitalsFragment::StaticStruct(), FEcoAliveTag::StaticStruct()
			};
			FEcoSocialSpeciesSharedFragment Social;
			FEcoSpeciesSharedFragment Species;
			FMassArchetypeSharedFragmentValues Shared;
			Shared.Add(EM.GetOrCreateSharedFragment(Social));
			Shared.Add(EM.GetOrCreateSharedFragment(Species));
			Shared.Sort();
			TArray<FMassEntityHandle> Entities;
			EM.BatchCreateEntities(EM.CreateArchetype(Composition), Shared, 1, Entities);
			Observer = Entities[0];
			EM.GetFragmentDataChecked<FTransformFragment>(Observer).GetMutableTransform().SetLocation(FVector(100, 0, 0));
			EM.GetFragmentDataChecked<FEcoIdentityFragment>(Observer).StableAgentId = 123;
			EM.GetFragmentDataChecked<FEcoHerdMemberFragment>(Observer).HerdRuntimeIndex = HerdIndex;
			auto& Raw = EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(Observer).Action;
			Raw.Forage = 0.8f; Raw.Cohesion = 0.5f; Raw.FleeDist = 0.2f; Raw.Cover = 0.1f;
			Gather = NewObject<UEcoNeighborhoodGatherProcessor>(Scoped.World);
			Detect = NewObject<UEcoThreatDetectionProcessor>(Scoped.World);
			Propagate = NewObject<UEcoAlarmPropagationProcessor>(Scoped.World);
			Respond = NewObject<UEcoSocialResponseProcessor>(Scoped.World);
			for (UMassProcessor* Processor : TArray<UMassProcessor*>{Gather, Detect, Propagate, Respond})
			{
				Processor->CallInitialize(Scoped.World, EM.AsShared());
			}
		}

		FMassEntityHandle Predator(const FVector& Position)
		{
			const TArray<const UScriptStruct*> Composition = { FTransformFragment::StaticStruct(),
				FMassVelocityFragment::StaticStruct(), FEcoPredatorTag::StaticStruct(), FEcoVitalsFragment::StaticStruct() };
			const FMassEntityHandle Entity = EM.CreateEntity(EM.CreateArchetype(Composition));
			EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform().SetLocation(Position);
			return Entity;
		}

		void Scan()
		{
			EcoTest::RunProcessor(*Gather, EM, 0.2f);
			EcoTest::RunProcessor(*Detect, EM, 0.2f);
		}

		const FEcoHerdRuntimeData& Data() const { return Herds.GetActiveHerds()[HerdIndex]; }
		FEcoAlarmStateFragment& Alarm() { return EM.GetFragmentDataChecked<FEcoAlarmStateFragment>(Observer); }
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSocialMassThreatTest, "AdaptiveEcosystem.Social.Threat.MassToShelter",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoSocialMassThreatTest::RunTest(const FString& Parameters)
{
	using namespace EcoSocialThreatTests;
	FFixture F;
	const FMassEntityHandle Predator = F.Predator(FVector(300, 0, 0));
	F.Scan();
	TestEqual(TEXT("Mass predator publishes herd alarm without harness"), F.Data().AlarmStrength, 1.0f);
	EcoTest::RunProcessor(*F.Propagate, F.EM, 0.016f);
	EcoTest::RunProcessor(*F.Respond, F.EM, 0.016f);
	TestTrue(TEXT("Nearby threat produces Panic"), F.Alarm().State == EEcoSocialState::Panic);
	const auto RawBefore = F.EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(F.Observer).Action;
	UEcoShelterSubsystem* Shelters = F.Scoped.World->GetSubsystem<UEcoShelterSubsystem>();
	Shelters->RegisterShelter(FVector(200, 200, 0), FVector::ForwardVector, 1.0f, 2, 50.0f);
	auto* Query = NewObject<UEcoShelterQueryProcessor>(F.Scoped.World);
	auto* Reserve = NewObject<UEcoShelterReservationProcessor>(F.Scoped.World);
	Query->CallInitialize(F.Scoped.World, F.EM.AsShared());
	Reserve->CallInitialize(F.Scoped.World, F.EM.AsShared());
	EcoTest::RunProcessor(*Query, F.EM, 0.016f);
	EcoTest::RunProcessor(*Reserve, F.EM, 0.016f);
	TestTrue(TEXT("Social response reaches Reserved shelter intent"),
		F.EM.GetFragmentDataChecked<FEcoShelterIntentFragment>(F.Observer).State == EEcoShelterIntentState::Reserved);
	const auto& RawAfter = F.EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(F.Observer).Action;
	TestTrue(TEXT("Raw PPO action preserved"), RawBefore.Forage == RawAfter.Forage && RawBefore.Cohesion == RawAfter.Cohesion
		&& RawBefore.FleeDist == RawAfter.FleeDist && RawBefore.Cover == RawAfter.Cover);

	F.EM.GetFragmentDataChecked<FTransformFragment>(Predator).GetMutableTransform().SetLocation(FVector(700, 0, 0));
	F.Scan();
	EcoTest::RunProcessor(*F.Propagate, F.EM, 0.016f);
	TestTrue(TEXT("Weaker reception updates moving threat position despite strong memory"), F.Alarm().LastThreatPosition.Equals(FVector(700, 0, 0)));
	F.EM.GetFragmentDataChecked<FEcoVitalsFragment>(Predator).HP = 0.0f;
	F.Scan();
	TestEqual(TEXT("Dead predator is removed on next scan"), F.Data().AlarmStrength, 0.0f);
	TestTrue(TEXT("Individual retains alarm memory on source loss"), F.Alarm().AlarmStrength > 0.0f);
	EcoTest::RunProcessor(*F.Propagate, F.EM, 10.0f);
	TestTrue(TEXT("Memory decays back to Calm"), F.Alarm().State == EEcoSocialState::Calm);
	F.EM.GetFragmentDataChecked<FEcoVitalsFragment>(Predator).HP = 100.0f;
	F.EM.GetFragmentDataChecked<FTransformFragment>(Predator).GetMutableTransform().SetLocation(FVector(-100, 0, 0));
	F.Scan();
	TestEqual(TEXT("Behind stationary observer (transform heading) is outside FOV"), F.Data().AlarmStrength, 0.0f);
	F.EM.GetFragmentDataChecked<FTransformFragment>(Predator).GetMutableTransform().SetLocation(FVector(20000, 0, 0));
	F.Scan();
	TestEqual(TEXT("Outside species view distance"), F.Data().AlarmStrength, 0.0f);
	F.EM.GetFragmentDataChecked<FTransformFragment>(F.Observer).GetMutableTransform().SetLocation(FVector(-100, 0, 0));
	F.EM.GetFragmentDataChecked<FTransformFragment>(Predator).GetMutableTransform().SetLocation(FVector::ZeroVector);
	F.Scan();
	TestTrue(TEXT("World origin is a valid threat position"), F.Data().AlarmStrength > 0.0f && F.Data().LastThreatPosition.IsZero());
	F.EM.AddTagToEntity(Predator, FEcoClientProxyTag::StaticStruct());
	F.Scan();
	TestEqual(TEXT("Client proxy cannot act as authoritative threat"), F.Data().AlarmStrength, 0.0f);
	F.EM.RemoveTagFromEntity(Predator, FEcoClientProxyTag::StaticStruct());
	F.EM.AddTagToEntity(F.Observer, FEcoPendingDeathTag::StaticStruct());
	F.Scan();
	TestEqual(TEXT("Dying observer cannot publish"), F.Data().AlarmStrength, 0.0f);
	F.EM.RemoveTagFromEntity(F.Observer, FEcoPendingDeathTag::StaticStruct());
	F.EM.DestroyEntity(Predator);
	F.Scan();
	TestEqual(TEXT("Destroyed source is cleared"), F.Data().AlarmStrength, 0.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSocialThreatOrderTest, "AdaptiveEcosystem.Social.Threat.ProcessorOrder",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoSocialThreatOrderTest::RunTest(const FString& Parameters)
{
	using namespace EcoSocialThreatTests;
	FFixture F;
	auto* Membership = NewObject<UEcoHerdMembershipProcessor>(F.Scoped.World);
	auto* Aggregate = NewObject<UEcoHerdAggregateProcessor>(F.Scoped.World);
	auto* Perception = NewObject<UEcoPerceptionProcessor>(F.Scoped.World);
	auto* Policy = NewObject<UEcoPolicyProcessor>(F.Scoped.World);
	auto* Query = NewObject<UEcoShelterQueryProcessor>(F.Scoped.World);
	auto* Reservation = NewObject<UEcoShelterReservationProcessor>(F.Scoped.World);
	TArray<UMassProcessor*> Processors = {Reservation, F.Respond, F.Propagate, F.Detect, Policy, Perception, F.Gather, Aggregate, Membership, Query};
	for (UMassProcessor* P : TArray<UMassProcessor*>{Membership, Aggregate, Perception, Policy, Query, Reservation})
	{
		P->CallInitialize(F.Scoped.World, F.EM.AsShared());
	}
	FMassProcessorDependencySolver Solver(Processors, false); // Include all declared nodes, regardless of test archetype pruning.
	TArray<FMassProcessorOrderInfo> Order;
	Solver.ResolveDependencies(Order);
	auto Index = [&](const UMassProcessor* Processor)
	{
		return Order.IndexOfByPredicate([&](const FMassProcessorOrderInfo& Info) { return Info.Processor == Processor; });
	};
	auto Before = [&](const TCHAR* Label, const UMassProcessor* First, const UMassProcessor* Second)
	{
		TestTrue(Label, Index(First) != INDEX_NONE && Index(Second) != INDEX_NONE && Index(First) < Index(Second));
	};
	Before(TEXT("Membership before aggregate"), Membership, Aggregate);
	Before(TEXT("Aggregate before real detection"), Aggregate, F.Detect);
	Before(TEXT("Gather before real detection"), F.Gather, F.Detect);
	Before(TEXT("Detection before alarm reception"), F.Detect, F.Propagate);
	Before(TEXT("Policy before Social Response"), Policy, F.Respond);
	Before(TEXT("Alarm before Social Response"), F.Propagate, F.Respond);
	Before(TEXT("Response before shelter query"), F.Respond, Query);
	Before(TEXT("Query before reservation"), Query, Reservation);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSocialActorThreatTest, "AdaptiveEcosystem.Social.Threat.ActorLOSAndLifecycle",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoSocialActorThreatTest::RunTest(const FString& Parameters)
{
	using namespace EcoSocialThreatTests;
	FFixture F;
	AActor* Source = F.Scoped.World->SpawnActor<AActor>();
	UBoxComponent* Body = NewObject<UBoxComponent>(Source);
	Source->SetRootComponent(Body);
	Body->SetBoxExtent(FVector(30, 30, 100));
	Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Body->SetCollisionResponseToAllChannels(ECR_Block);
	Body->RegisterComponent();
	Source->SetActorLocation(FVector(300, 0, 0));
	UEcoThreatSourceComponent* Component = NewObject<UEcoThreatSourceComponent>(Source);
	Source->AddInstanceComponent(Component);
	Component->RegisterComponent();
	// The isolated world has not routed InitializeActorsForPlay; activate explicitly as
	// normal initialized actors do during component registration.
	Component->Activate(true);
	Source->DispatchBeginPlay(); // Exercises production BeginPlay registration.
	TestTrue(TEXT("Component BeginPlay routed"), Component->HasBegunPlay());
	TArray<FEcoActorThreatSnapshot> Snapshots;
	F.Herds.GatherActorThreats(Snapshots);
	TestEqual(TEXT("Active actor source is registered"), Snapshots.Num(), 1);
	F.Scan();
	TestEqual(TEXT("Real actor component emits alarm; own body ignored by LOS"), F.Data().AlarmStrength, 1.0f);

	AActor* Wall = F.Scoped.World->SpawnActor<AActor>();
	UBoxComponent* WallCollision = NewObject<UBoxComponent>(Wall);
	Wall->SetRootComponent(WallCollision);
	WallCollision->SetBoxExtent(FVector(10, 100, 200));
	WallCollision->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	WallCollision->SetCollisionResponseToAllChannels(ECR_Block);
	WallCollision->RegisterComponent();
	Wall->SetActorLocation(FVector(200, 0, 0));
	F.Scan();
	TestEqual(TEXT("Visibility wall prevents initial detection"), F.Data().AlarmStrength, 0.0f);
	WallCollision->SetCollisionResponseToChannel(ECC_Visibility, ECR_Ignore);
	F.Scan();
	TestEqual(TEXT("Visibility Ignore permits detection"), F.Data().AlarmStrength, 1.0f);
	Component->bThreatEnabled = false;
	F.Scan();
	TestEqual(TEXT("Disabled component removes real input"), F.Data().AlarmStrength, 0.0f);
	Component->bThreatEnabled = true;
	Component->ThreatStrength = 0.4f;
	Source->SetActorLocation(FVector(500, 0, 0));
	F.Scan();
	TestTrue(TEXT("Moved actor uses new position and strength"), F.Data().LastThreatPosition.Equals(FVector(500, 0, 0)) && F.Data().AlarmStrength == 0.4f);
	Source->Destroy();
	F.Scan();
	TestEqual(TEXT("EndPlay unregisters source"), F.Data().AlarmStrength, 0.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSocialAlarmChannelsTest, "AdaptiveEcosystem.Social.Threat.ChannelAndSlotSafety",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoSocialAlarmChannelsTest::RunTest(const FString& Parameters)
{
	using namespace EcoSocialThreatTests;
	FFixture F;
	FEcoObservedHerdThreat Threat;
	Threat.HerdRuntimeIndex = F.HerdIndex;
	Threat.PersistentHerdId = F.Data().PersistentHerdId;
	Threat.Position = FVector(500, 0, 0);
	Threat.Strength = 1.0f;
	F.Herds.EmitHerdAlarm(F.HerdIndex, FVector(300, 0, 0), 0.7f);
	F.Herds.ApplyObservedHerdThreats(MakeArrayView(&Threat, 1));
	TestEqual(TEXT("Observed stronger input wins"), F.Data().AlarmStrength, 1.0f);
	F.Herds.ApplyObservedHerdThreats(TConstArrayView<FEcoObservedHerdThreat>());
	TestTrue(TEXT("Source loss preserves injected alarm and position"), F.Data().AlarmStrength == 0.7f && F.Data().LastThreatPosition.Equals(FVector(300, 0, 0)));
	F.Herds.ReleaseHerd(F.HerdIndex);
	F.HerdIndex = F.Herds.AllocateHerd(0, FVector::ZeroVector);
	F.Herds.ApplyObservedHerdThreats(MakeArrayView(&Threat, 1));
	TestEqual(TEXT("Stale observed event cannot affect reused slot"), F.Data().AlarmStrength, 0.0f);
	TestEqual(TEXT("Negative spatial radius rejected"), F.Herds.EmitSpatialAlarm(FVector::ZeroVector, -10.0f, 1.0f), 0);
	F.Herds.EmitHerdAlarm(F.HerdIndex, FVector::ZeroVector, 0.5f);
	F.Herds.DecayHerdAlarms(-1.0f, 0.2f);
	TestEqual(TEXT("Negative delta cannot increase alarm"), F.Data().AlarmStrength, 0.5f);
	F.Herds.ClearHerdAlarms();
	TestEqual(TEXT("Clear resets both channels"), F.Data().AlarmStrength, 0.0f);
	return true;
}

#endif

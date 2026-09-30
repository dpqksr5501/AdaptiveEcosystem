#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "AI/Policy/Tests/EcoTestWorld.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Shelter/EcoShelterLifecycleProcessor.h"
#include "AI/Social/Shelter/EcoShelterProcessors.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassEntitySubsystem.h"
#include "MassProcessorDependencySolver.h"

namespace EcoShelterLifecycleTests
{
	struct FFixture
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager& EM;
		UEcoShelterSubsystem& Shelters;
		UEcoShelterQueryProcessor* Query;
		UEcoShelterReservationProcessor* Reserve;
		UEcoShelterLifecycleProcessor* Lifecycle;
		FMassEntityHandle Agent;
		int32 ShelterIndex;

		FFixture() : EM(Scoped.World->GetSubsystem<UMassEntitySubsystem>()->GetMutableEntityManager()),
			Shelters(*Scoped.World->GetSubsystem<UEcoShelterSubsystem>())
		{
			ShelterIndex = Shelters.RegisterShelter(FVector::ZeroVector, FVector::ForwardVector, 1.0f, 1, 50.0f);
			Query = NewObject<UEcoShelterQueryProcessor>(Scoped.World);
			Reserve = NewObject<UEcoShelterReservationProcessor>(Scoped.World);
			Lifecycle = NewObject<UEcoShelterLifecycleProcessor>(Scoped.World);
			for (UMassProcessor* P : TArray<UMassProcessor*>{Query, Reserve, Lifecycle})
			{
				P->CallInitialize(Scoped.World, EM.AsShared());
			}
			Agent = Spawn(123);
		}

		FMassEntityHandle Spawn(int64 Id)
		{
			const TArray<const UScriptStruct*> Composition = {FTransformFragment::StaticStruct(), FEcoIdentityFragment::StaticStruct(),
				FEcoAlarmStateFragment::StaticStruct(), FEcoSocialBehaviorFragment::StaticStruct(), FEcoShelterIntentFragment::StaticStruct(),
				FEcoPolicyOutputFragment::StaticStruct(), FEcoSocialMovementRequestFragment::StaticStruct(), FEcoShelterMovementFeedbackFragment::StaticStruct(),
				FEcoVitalsFragment::StaticStruct(), FEcoTravelFragment::StaticStruct(), FEcoAliveTag::StaticStruct()};
			FEcoSocialSpeciesSharedFragment Social;
			FEcoSpeciesSharedFragment Species;
			FMassArchetypeSharedFragmentValues Shared;
			Shared.Add(EM.GetOrCreateSharedFragment(Social));
			Shared.Add(EM.GetOrCreateSharedFragment(Species));
			Shared.Sort();
			TArray<FMassEntityHandle> Entities;
			EM.BatchCreateEntities(EM.CreateArchetype(Composition), Shared, 1, Entities);
			const auto E = Entities[0];
			EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId = Id;
			EM.GetFragmentDataChecked<FTransformFragment>(E).GetMutableTransform().SetLocation(FVector(-500, 0, 0));
			auto& Raw = EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
			Raw.Forage = 0.8f; Raw.Cohesion = 0.5f; Raw.FleeDist = 0.2f; Raw.Cover = 0.1f;
			auto& SocialAction = EM.GetFragmentDataChecked<FEcoSocialBehaviorFragment>(E);
			SocialAction.ModulatedAction = Raw;
			SocialAction.ModulatedAction.Cover = 0.9f;
			return E;
		}

		void Run(UMassProcessor& P) { EcoTest::RunProcessor(P, EM, 0.016f); }
		void Acquire() { Run(*Query); Run(*Reserve); Run(*Lifecycle); }
		void Advance(double Seconds) { Scoped.World->TimeSeconds += Seconds; }
		void Position(const FVector& Value) { EM.GetFragmentDataChecked<FTransformFragment>(Agent).GetMutableTransform().SetLocation(Value); }
		FEcoShelterIntentFragment& Intent() { return EM.GetFragmentDataChecked<FEcoShelterIntentFragment>(Agent); }
		FEcoSocialMovementRequestFragment& Request() { return EM.GetFragmentDataChecked<FEcoSocialMovementRequestFragment>(Agent); }
		FEcoShelterMovementFeedbackFragment& Feedback() { return EM.GetFragmentDataChecked<FEcoShelterMovementFeedbackFragment>(Agent); }
		void Report(EEcoShelterMovementStatus Status) { Feedback().Report(Intent().ReservationId, Status); Run(*Lifecycle); }
		FEcoShelterSlot Slot() { FEcoShelterSlot Value; Shelters.GetSlotData(0, Value); return Value; }
	};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoShelterHandoffTest, "AdaptiveEcosystem.Social.ShelterLifecycle.HandoffAndArrival",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoShelterHandoffTest::RunTest(const FString& Parameters)
{
	using namespace EcoShelterLifecycleTests;
	FFixture F;
	F.Acquire();
	const int64 Token = F.Intent().ReservationId;
	TestTrue(TEXT("Reserved publishes a live travel request"), Token > 0 && F.Request().bValid && F.Request().Mode == EEcoSocialMovementMode::ShelterTravel);
	TestEqual(TEXT("Effective cover is Social output"), F.Request().EffectiveAction.Cover, 0.9f);
	const FVector OriginalPosition = F.EM.GetFragmentDataChecked<FTransformFragment>(F.Agent).GetTransform().GetLocation();
	F.Report(EEcoShelterMovementStatus::Moving);
	TestTrue(TEXT("Consumer acknowledgement starts Moving"), F.Intent().State == EEcoShelterIntentState::Moving);
	TestTrue(TEXT("Social acknowledgement does not integrate movement"),
		F.EM.GetFragmentDataChecked<FTransformFragment>(F.Agent).GetTransform().GetLocation().Equals(OriginalPosition));
	F.Report(EEcoShelterMovementStatus::Arrived);
	TestTrue(TEXT("Distant arrival claim cannot occupy"), F.Intent().State == EEcoShelterIntentState::Moving);
	F.Position(F.Request().TargetPosition);
	F.Report(EEcoShelterMovementStatus::Arrived);
	TestTrue(TEXT("Actual position plus matching arrival report occupies"), F.Intent().State == EEcoShelterIntentState::Occupied && F.Request().Mode == EEcoSocialMovementMode::ShelterHold);
	F.Advance(0.5);
	F.Position(F.Request().TargetPosition + FVector(80, 0, 0));
	F.Report(EEcoShelterMovementStatus::Arrived);
	TestTrue(TEXT("Occupied exit hysteresis tolerates jitter outside arrival radius"), F.Intent().State == EEcoShelterIntentState::Occupied);
	F.Position(F.Request().TargetPosition + FVector(121, 0, 0));
	F.Run(*F.Lifecycle);
	TestTrue(TEXT("Leaving occupied radius releases token and request"), F.Intent().State == EEcoShelterIntentState::None && F.Request().ReservationId == 0 && F.Slot().ReservedBy == 0);
	const auto& Raw = F.EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(F.Agent).Action;
	TestTrue(TEXT("Lifecycle preserves raw PPO"), Raw.Forage == 0.8f && Raw.Cohesion == 0.5f && Raw.FleeDist == 0.2f && Raw.Cover == 0.1f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoShelterLeaseSafetyTest, "AdaptiveEcosystem.Social.ShelterLifecycle.LeaseGenerationAndFeedback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoShelterLeaseSafetyTest::RunTest(const FString& Parameters)
{
	using namespace EcoShelterLifecycleTests;
	FFixture F;
	F.Acquire();
	const int64 OldToken = F.Intent().ReservationId;
	F.Report(EEcoShelterMovementStatus::Failed);
	TestEqual(TEXT("Path failure releases"), F.Slot().ReservedBy, int64(0));
	F.Advance(1.1);
	F.Acquire();
	const int64 NewToken = F.Intent().ReservationId;
	TestTrue(TEXT("Reacquisition gives a new lease generation"), NewToken > OldToken);
	F.Feedback().Report(OldToken, EEcoShelterMovementStatus::Failed);
	F.Run(*F.Lifecycle);
	TestEqual(TEXT("Late failure cannot cancel a newer lease"), F.Intent().ReservationId, NewToken);
	F.Shelters.ReleaseSlot(0, 123, OldToken);
	TestEqual(TEXT("Late direct release cannot cancel newer generation"), F.Slot().ReservationId, NewToken);
	F.Report(EEcoShelterMovementStatus::Moving);
	const double FeedbackTime = F.Intent().LastMovementFeedbackTime;
	F.Advance(1.0);
	F.Run(*F.Lifecycle);
	TestEqual(TEXT("Same feedback sequence is consumed only once"), F.Intent().LastMovementFeedbackTime, FeedbackTime);
	F.Advance(1.1);
	F.Run(*F.Lifecycle);
	TestEqual(TEXT("Missing heartbeat releases despite continued Cover demand"), F.Slot().ReservedBy, int64(0));
	F.Advance(1.1);
	F.Acquire();
	F.Report(EEcoShelterMovementStatus::Yielded);
	TestEqual(TEXT("Movement arbitration can yield and free the lease"), F.Slot().ReservedBy, int64(0));
	F.Advance(1.1); F.Acquire();
	const int64 UnacceptedToken = F.Intent().ReservationId;
	F.Advance(12.1); F.Run(*F.Lifecycle);
	TestTrue(TEXT("No movement consumer means bounded Reserved TTL, not automatic Moving"),
		UnacceptedToken != 0 && F.Intent().State == EEcoShelterIntentState::None && F.Slot().ReservedBy == 0);
	TestFalse(TEXT("Invalid agent ID cannot reserve"), F.Shelters.ReserveSlot(0, 0, 100.0));
	TestFalse(TEXT("Expired request cannot reserve"), F.Shelters.ReserveSlot(0, 123, 0.0));
	F.Shelters.UnregisterShelter(F.ShelterIndex);
	TestFalse(TEXT("Unregistered slot cannot be reserved"), F.Shelters.ReserveSlot(0, 123, 100.0));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoShelterProgressTest, "AdaptiveEcosystem.Social.ShelterLifecycle.ProgressAndRenewal",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoShelterProgressTest::RunTest(const FString& Parameters)
{
	using namespace EcoShelterLifecycleTests;
	FFixture F;
	F.Acquire();
	const int64 Token = F.Intent().ReservationId;
	F.Report(EEcoShelterMovementStatus::Moving);
	for (int32 I = 0; I < 8; ++I) { F.Advance(1.0); F.Report(EEcoShelterMovementStatus::Moving); }
	TestEqual(TEXT("Fresh heartbeat cannot keep a stuck entity reserved forever"), F.Slot().ReservedBy, int64(0));
	F.Advance(1.1);
	F.Acquire();
	F.Report(EEcoShelterMovementStatus::Moving);
	const double InitialExpiry = F.Slot().ReservationExpireTime;
	for (int32 I = 0; I < 14; ++I)
	{
		F.Advance(1.0);
		F.Position(FVector(-500 + (I + 1) * 20, 0, 0)); // Simulate the movement writer only in the test.
		F.Report(EEcoShelterMovementStatus::Moving);
	}
	TestTrue(TEXT("Real progress keeps reservation alive past initial TTL"), F.Intent().State == EEcoShelterIntentState::Moving && F.Slot().ReservationExpireTime > InitialExpiry && F.Intent().ReservationId != Token);
	F.EM.GetFragmentDataChecked<FEcoSocialBehaviorFragment>(F.Agent).ModulatedAction.Cover = 0.1f;
	F.Run(*F.Query); F.Run(*F.Reserve); F.Run(*F.Lifecycle);
	TestTrue(TEXT("Threat/cover demand termination releases Moving"), F.Slot().ReservedBy == 0 && F.Request().Mode == EEcoSocialMovementMode::None);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoShelterOwnerCleanupTest, "AdaptiveEcosystem.Social.ShelterLifecycle.OwnerCleanup",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoShelterOwnerCleanupTest::RunTest(const FString& Parameters)
{
	using namespace EcoShelterLifecycleTests;
	FFixture F;
	F.Acquire();
	F.EM.GetFragmentDataChecked<FEcoVitalsFragment>(F.Agent).HP = 0.0f;
	F.Run(*F.Lifecycle);
	TestTrue(TEXT("Death releases and clears request"), F.Slot().ReservedBy == 0 && !F.Request().bValid);
	F.EM.GetFragmentDataChecked<FEcoVitalsFragment>(F.Agent).HP = 100.0f;
	F.Advance(1.1); F.Acquire();
	F.EM.GetFragmentDataChecked<FEcoTravelFragment>(F.Agent).State = EEcoResidenceState::Traveling;
	F.Run(*F.Lifecycle);
	TestTrue(TEXT("Migration retains authority and cancels shelter request"), F.Slot().ReservedBy == 0 && !F.Request().bValid);
	F.EM.GetFragmentDataChecked<FEcoTravelFragment>(F.Agent).State = EEcoResidenceState::Resident;
	F.Advance(1.1); F.Acquire();
	F.EM.RemoveTagFromEntity(F.Agent, FEcoAliveTag::StaticStruct());
	F.Run(*F.Lifecycle);
	TestEqual(TEXT("Alive removal releases immediately on reconciliation"), F.Slot().ReservedBy, int64(0));
	F.EM.AddTagToEntity(F.Agent, FEcoAliveTag::StaticStruct());
	F.Advance(1.1); F.Acquire();
	F.EM.AddTagToEntity(F.Agent, FEcoClientProxyTag::StaticStruct());
	F.Run(*F.Lifecycle);
	TestTrue(TEXT("Proxy logical request is excluded and lease freed"), F.Slot().ReservedBy == 0 && !F.Request().bValid);
	F.EM.RemoveTagFromEntity(F.Agent, FEcoClientProxyTag::StaticStruct());
	F.Advance(1.1); F.Acquire();
	TestTrue(TEXT("Setup acquired lease before deletion"), F.Slot().ReservedBy == 123);
	F.EM.DestroyEntity(F.Agent);
	F.Run(*F.Lifecycle);
	TestEqual(TEXT("Despawn of last owner releases without waiting for TTL"), F.Slot().ReservedBy, int64(0));
	TestFalse(TEXT("Lifecycle is not pruned after last owner deletion"), F.Lifecycle->ShouldAllowQueryBasedPruning());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoShelterCompetitionTest, "AdaptiveEcosystem.Social.ShelterLifecycle.CompetitionAndOrder",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoShelterCompetitionTest::RunTest(const FString& Parameters)
{
	using namespace EcoShelterLifecycleTests;
	FFixture F;
	const auto Competitor = F.Spawn(42);
	F.Acquire();
	TestEqual(TEXT("Equal score slot competition uses smaller StableAgentId"), F.Slot().ReservedBy, int64(42));
	TestTrue(TEXT("Loser resets without clearing winner's reservation"), F.Intent().State == EEcoShelterIntentState::None && F.Slot().ReservationId > 0);
	TArray<UMassProcessor*> Processors = {F.Lifecycle, F.Reserve, F.Query};
	FMassProcessorDependencySolver Solver(Processors, false);
	TArray<FMassProcessorOrderInfo> Order;
	Solver.ResolveDependencies(Order);
	auto Index = [&](const UMassProcessor* P) { return Order.IndexOfByPredicate([&](const FMassProcessorOrderInfo& Info) { return Info.Processor == P; }); };
	TestTrue(TEXT("Query -> Reservation -> Lifecycle order is resolved"), Index(F.Query) >= 0 && Index(F.Query) < Index(F.Reserve) && Index(F.Reserve) < Index(F.Lifecycle));
	return true;
}

#endif

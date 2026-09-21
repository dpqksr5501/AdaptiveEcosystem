// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Shelter/EcoShelterProcessors.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Social/Alarm/EcoAlarmProcessors.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassCommonTypes.h"
#include "MassExecutionContext.h"
#include "MassEntityManager.h"
#include "Engine/World.h"

// -----------------------------------------------------------------------------
// UEcoShelterQueryProcessor
// -----------------------------------------------------------------------------

UEcoShelterQueryProcessor::UEcoShelterQueryProcessor()
	: EntityQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(UEcoSocialResponseProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true; // Ensures GameThread serialized LineTrace and safe queries
}

void UEcoShelterQueryProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoShelterIntentFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddSharedRequirement<FEcoSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoShelterQueryProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World)
	{
		return;
	}

	const UEcoShelterSubsystem* ShelterSubsystem = World->GetSubsystem<UEcoShelterSubsystem>();
	if (!ShelterSubsystem)
	{
		return;
	}

	const double CurrentTime = World->GetTimeSeconds();

	int32 MatchedEntitiesCount = 0;

	EntityQuery.ForEachEntityChunk(Context, [ShelterSubsystem, CurrentTime, &MatchedEntitiesCount](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		MatchedEntitiesCount += NumEntities;
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TConstArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetFragmentView<FEcoAlarmStateFragment>();
		TConstArrayView<FEcoSocialBehaviorFragment> SocialList = ChunkContext.GetFragmentView<FEcoSocialBehaviorFragment>();
		TArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetMutableFragmentView<FEcoShelterIntentFragment>();
		const FEcoSpeciesSharedFragment& SpeciesConfig = ChunkContext.GetSharedFragment<FEcoSpeciesSharedFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			FEcoShelterIntentFragment& Intent = IntentList[i];
			const FEcoPolicyActionV1& ModAction = SocialList[i].ModulatedAction;
			const FEcoAlarmStateFragment& Alarm = AlarmList[i];

			// 1. Evaluate whether agent requires shelter based on ModulatedAction.Cover and Alarm state
			const bool bNeedsShelter = (ModAction.Cover >= 0.25f) || (Alarm.State == EEcoSocialState::Panic);

			// 2. If agent was Reserved but no longer needs shelter (danger passed and cover urge dropped), flag for release
			if (Intent.State == EEcoShelterIntentState::Reserved && !bNeedsShelter)
			{
				// Transition to None while keeping TargetSlotIndex temporarily so downstream knows which slot to release
				Intent.State = EEcoShelterIntentState::None;
				continue;
			}

			// 3. If agent needs shelter and is unreserved, evaluate candidates
			if (bNeedsShelter && Intent.State == EEcoShelterIntentState::None)
			{
				if (CurrentTime >= Intent.NextQueryTime)
				{
					const FVector AgentLocation = TransformList[i].GetTransform().GetLocation();
					int32 TargetSlotIndex = INDEX_NONE_ECO;
					float CandidateScore = 0.0f;

					const int32 BestShelterIndex = ShelterSubsystem->FindBestAvailableShelter(
						AgentLocation,
						Alarm.LastThreatPosition,
						SpeciesConfig.CoverSearchRadius,
						TargetSlotIndex,
						CandidateScore
					);

					if (BestShelterIndex != INDEX_NONE_ECO && TargetSlotIndex != INDEX_NONE_ECO)
					{
						Intent.TargetShelterIndex = BestShelterIndex;
						Intent.TargetSlotIndex = TargetSlotIndex;
						Intent.CurrentScore = CandidateScore;
						Intent.State = EEcoShelterIntentState::Searching; // Proposed candidate ready for reconciliation!
						Intent.NextQueryTime = CurrentTime + 0.8; // 0.8s evaluation cooldown
					}
					else
					{
						// No suitable shelter found in radius
						Intent.NextQueryTime = CurrentTime + 1.5;
					}
				}
			}
		}
	});

#if !(UE_BUILD_SHIPPING)
	static int32 LastReportedMatchedCount = -1;
	if (MatchedEntitiesCount != LastReportedMatchedCount)
	{
		UE_LOG(LogTemp, Log, TEXT("[UEcoShelterQueryProcessor] Query matched %d entities in world."), MatchedEntitiesCount);
		LastReportedMatchedCount = MatchedEntitiesCount;
	}
#endif
}

// -----------------------------------------------------------------------------
// UEcoShelterReservationProcessor
// -----------------------------------------------------------------------------

UEcoShelterReservationProcessor::UEcoShelterReservationProcessor()
	: EntityQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(UEcoShelterQueryProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true; // Ensures GameThread serialized reconciliation & subsystem mutation
}

void UEcoShelterReservationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoShelterIntentFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoShelterReservationProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World)
	{
		return;
	}

	UEcoShelterSubsystem* ShelterSubsystem = World->GetSubsystem<UEcoShelterSubsystem>();
	if (!ShelterSubsystem)
	{
		return;
	}

	const double CurrentTime = World->GetTimeSeconds();

	// Step 1: Clean expired reservations
	ShelterSubsystem->CleanExpiredReservations(CurrentTime);

	// Step 2: Collect proposals and handle release requests (GameThread serialized)
	Proposals.Reset();

	EntityQuery.ForEachEntityChunk(Context, [this, ShelterSubsystem, CurrentTime](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoIdentityFragment> IdentityList = ChunkContext.GetFragmentView<FEcoIdentityFragment>();
		TArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetMutableFragmentView<FEcoShelterIntentFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			FEcoShelterIntentFragment& Intent = IntentList[i];
			const int64 AgentId = IdentityList[i].StableAgentId;
			const FMassEntityHandle Entity = ChunkContext.GetEntity(i);

			// Release handling: if agent transitioned to None but still held a reserved slot, release it
			if (Intent.State == EEcoShelterIntentState::None && Intent.TargetSlotIndex != INDEX_NONE_ECO)
			{
				ShelterSubsystem->ReleaseSlot(Intent.TargetSlotIndex, AgentId);
				Intent.Reset();
				continue;
			}

			// Active reservation validation: check if reservation expired or was taken
			if (Intent.State == EEcoShelterIntentState::Reserved)
			{
				FEcoShelterSlot SlotData;
				if (!ShelterSubsystem->GetSlotData(Intent.TargetSlotIndex, SlotData) || SlotData.ReservedBy != AgentId)
				{
					// Reservation lost or lapsed
					Intent.Reset();
				}
				continue;
			}

			// Collect candidate proposals
			if (Intent.State == EEcoShelterIntentState::Searching && Intent.TargetSlotIndex != INDEX_NONE_ECO)
			{
				FSlotProposal Proposal;
				Proposal.Entity = Entity;
				Proposal.StableAgentId = AgentId;
				Proposal.SlotIndex = Intent.TargetSlotIndex;
				Proposal.Score = Intent.CurrentScore;
				Proposals.Add(Proposal);
			}
		}
	});

	if (Proposals.Num() == 0)
	{
		return;
	}

	// Step 3: Deterministic Reconciliation
	// Sort proposals:
	// 1. SlotIndex (ascending)
	// 2. Score (descending)
	// 3. StableAgentId (ascending tie-break)
	Proposals.Sort([](const FSlotProposal& A, const FSlotProposal& B)
	{
		if (A.SlotIndex != B.SlotIndex)
		{
			return A.SlotIndex < B.SlotIndex;
		}
		if (!FMath::IsNearlyEqual(A.Score, B.Score, KINDA_SMALL_NUMBER))
		{
			return A.Score > B.Score; // Higher score wins
		}
		return A.StableAgentId < B.StableAgentId; // Smaller ID deterministic tie-break
	});

	// Step 4: Commit winners and reject competitors
	int32 CurrentSlotIndex = INDEX_NONE_ECO;
	bool bSlotAwarded = false;

	for (const FSlotProposal& Proposal : Proposals)
	{
		if (Proposal.SlotIndex != CurrentSlotIndex)
		{
			CurrentSlotIndex = Proposal.SlotIndex;
			bSlotAwarded = false;
		}

		FEcoShelterIntentFragment& Intent = EntityManager.GetFragmentDataChecked<FEcoShelterIntentFragment>(Proposal.Entity);

		if (!bSlotAwarded)
		{
			const double ReservationDuration = 12.0; // 12-second reservation window
			if (ShelterSubsystem->ReserveSlot(Proposal.SlotIndex, Proposal.StableAgentId, CurrentTime + ReservationDuration))
			{
				// Winning candidate lock
				FEcoShelterSlot SlotData;
				ShelterSubsystem->GetSlotData(Proposal.SlotIndex, SlotData);

				Intent.State = EEcoShelterIntentState::Reserved;
				Intent.TargetPosition = SlotData.Position;
				Intent.CurrentScore = Proposal.Score;
				bSlotAwarded = true;
				continue;
			}
		}

		// Lost competition or slot already locked: reset intent to None
		Intent.Reset();
		Intent.NextQueryTime = CurrentTime + 0.5; // Quick retry cooldown
	}
}

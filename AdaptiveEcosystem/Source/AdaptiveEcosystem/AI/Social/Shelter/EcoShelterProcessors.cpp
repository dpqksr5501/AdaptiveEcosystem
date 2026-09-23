// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Shelter/EcoShelterProcessors.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassCommonTypes.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"

// -----------------------------------------------------------------------------
// UEcoShelterQueryProcessor
// -----------------------------------------------------------------------------

UEcoShelterQueryProcessor::UEcoShelterQueryProcessor()
	: EntityQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	bAutoRegisterWithProcessingPhases = true;
}

void UEcoShelterQueryProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly);
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

	EntityQuery.ForEachEntityChunk(Context, [ShelterSubsystem, CurrentTime](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TConstArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetFragmentView<FEcoAlarmStateFragment>();
		TConstArrayView<FEcoPolicyOutputFragment> PolicyOutputList = ChunkContext.GetFragmentView<FEcoPolicyOutputFragment>();
		TArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetMutableFragmentView<FEcoShelterIntentFragment>();
		const FEcoSpeciesSharedFragment& SpeciesConfig = ChunkContext.GetSharedFragment<FEcoSpeciesSharedFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			FEcoShelterIntentFragment& Intent = IntentList[i];
			const FEcoPolicyActionV1& Action = PolicyOutputList[i].Action;
			const FEcoAlarmStateFragment& Alarm = AlarmList[i];

			// Only evaluate shelter search if agent expresses substantial cover urge or is in panic
			const bool bNeedsShelter = (Action.Cover >= 0.25f) || (Alarm.State == EEcoSocialState::Panic);

			if (bNeedsShelter && Intent.State != EEcoShelterIntentState::Reserved && Intent.State != EEcoShelterIntentState::Occupied)
			{
				if (CurrentTime >= Intent.NextQueryTime)
				{
					const FVector AgentLocation = TransformList[i].GetTransform().GetLocation();
					int32 TargetSlotIndex = INDEX_NONE_ECO;

					const int32 BestShelterIndex = ShelterSubsystem->FindBestAvailableShelter(
						AgentLocation,
						Alarm.LastThreatPosition,
						SpeciesConfig.CoverSearchRadius,
						TargetSlotIndex
					);

					if (BestShelterIndex != INDEX_NONE_ECO && TargetSlotIndex != INDEX_NONE_ECO)
					{
						Intent.TargetShelterIndex = BestShelterIndex;
						Intent.TargetSlotIndex = TargetSlotIndex;
						Intent.State = EEcoShelterIntentState::Searching;
						Intent.NextQueryTime = CurrentTime + 1.0; // 1-second evaluation cooldown
					}
					else
					{
						// No suitable shelter found in radius
						Intent.NextQueryTime = CurrentTime + 2.0;
					}
				}
			}
		}
	});
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
}

void UEcoShelterReservationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
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

	// Pass 1 & 2: Clean expired reservations and reconcile current proposals
	ShelterSubsystem->CleanExpiredReservations(CurrentTime);

	EntityQuery.ForEachEntityChunk(Context, [ShelterSubsystem, CurrentTime](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoIdentityFragment> IdentityList = ChunkContext.GetFragmentView<FEcoIdentityFragment>();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetMutableFragmentView<FEcoShelterIntentFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			FEcoShelterIntentFragment& Intent = IntentList[i];
			const int64 AgentId = IdentityList[i].StableAgentId;
			const FVector AgentLocation = TransformList[i].GetTransform().GetLocation();

			// Handle Searching agents attempting to lock their proposed slot
			if (Intent.State == EEcoShelterIntentState::Searching)
			{
				const double ReservationDuration = 12.0; // 12 seconds reserved travel window
				if (ShelterSubsystem->ReserveSlot(Intent.TargetSlotIndex, AgentId, CurrentTime + ReservationDuration))
				{
					// Reservation successfully locked
					Intent.State = EEcoShelterIntentState::Reserved;
				}
				else
				{
					// Slot was taken by a competitor; release proposal and retry later
					Intent.State = EEcoShelterIntentState::None;
					Intent.TargetSlotIndex = INDEX_NONE_ECO;
					Intent.TargetShelterIndex = INDEX_NONE_ECO;
				}
			}
			// Handle Reserved agents reaching shelter location
			else if (Intent.State == EEcoShelterIntentState::Reserved)
			{
				const TArray<FEcoShelterSlot>& Slots = ShelterSubsystem->GetShelterSlots();
				if (Slots.IsValidIndex(Intent.TargetSlotIndex) && Slots[Intent.TargetSlotIndex].ReservedBy == AgentId)
				{
					const float DistToSlot = FVector::Dist(AgentLocation, Slots[Intent.TargetSlotIndex].Position);
					if (DistToSlot <= 200.0f)
					{
						// Agent has arrived inside shelter refuge radius
						Intent.State = EEcoShelterIntentState::Occupied;
					}
				}
				else
				{
					// Reservation lost or expired
					Intent.State = EEcoShelterIntentState::None;
					Intent.TargetSlotIndex = INDEX_NONE_ECO;
					Intent.TargetShelterIndex = INDEX_NONE_ECO;
				}
			}
		}
	});
}

// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Shelter/EcoShelterProcessors.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Social/Shelter/EcoShelterEligibility.h"
#include "AI/Social/Shelter/EcoShelterDiagnostics.h"
#include "AI/Social/Alarm/EcoAlarmProcessors.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
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
	ExecutionFlags = int32(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
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
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
	EcoShelter::AddEligibilityRequirements(EntityQuery);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoShelterQueryProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World || World->GetNetMode() == NM_Client)
	{
		return;
	}

	const UEcoShelterSubsystem* ShelterSubsystem = World->GetSubsystem<UEcoShelterSubsystem>();
	if (!ShelterSubsystem)
	{
		return;
	}

	const double CurrentTime = World->GetTimeSeconds();

	EntityQuery.ForEachEntityChunk(Context, [ShelterSubsystem, CurrentTime, World](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		const auto IdentityList = ChunkContext.GetFragmentView<FEcoIdentityFragment>();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TConstArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetFragmentView<FEcoAlarmStateFragment>();
		TConstArrayView<FEcoSocialBehaviorFragment> SocialList = ChunkContext.GetFragmentView<FEcoSocialBehaviorFragment>();
		TArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetMutableFragmentView<FEcoShelterIntentFragment>();
		const FEcoSpeciesSharedFragment& SpeciesConfig = ChunkContext.GetSharedFragment<FEcoSpeciesSharedFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			if (!EcoShelter::IsEligible(ChunkContext, i)) { continue; }
			FEcoShelterIntentFragment& Intent = IntentList[i];
			const FEcoPolicyActionV1& ModAction = SocialList[i].ModulatedAction;
			const FEcoAlarmStateFragment& Alarm = AlarmList[i];

			// 1. Evaluate whether agent requires shelter based on ModulatedAction.Cover and Alarm state
			const bool bNeedsShelter = (ModAction.Cover >= 0.25f) || (Alarm.State == EEcoSocialState::Panic);

			// 2. If agent was Reserved but no longer needs shelter (danger passed and cover urge dropped), flag for release
			if (!bNeedsShelter)
			{
				if (Intent.State == EEcoShelterIntentState::Searching)
				{
					Intent.Reset(); // Proposal has no ownership to release.
				}
				else
				{
					Intent.State = EEcoShelterIntentState::None; // Keep token until serialized release.
				}
				continue;
			}
			if (Intent.State == EEcoShelterIntentState::None && Intent.TargetSlotIndex != INDEX_NONE_ECO) { continue; }

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
						Alarm.AlarmStrength > 0.05f,
						SpeciesConfig.CoverSearchRadius,
						TargetSlotIndex,
						CandidateScore
					);
					if (EcoShelterDiagnostics::GetLevel() >= 2)
					{
						UE_LOG(LogEcoSocialShelter, Log,
							TEXT("[Shelter][Search] World=%s Time=%.2f Agent=%lld Result=%s Shelter=%d Slot=%d Score=%.3f Cover=%.2f Alarm=%.2f Radius=%.1f Position=%s Threat=%s"),
							*GetNameSafe(World), CurrentTime, IdentityList[i].StableAgentId,
							BestShelterIndex != INDEX_NONE_ECO ? TEXT("Candidate") : TEXT("NoAvailableCandidate"), BestShelterIndex, TargetSlotIndex,
							CandidateScore, ModAction.Cover, Alarm.AlarmStrength, SpeciesConfig.CoverSearchRadius,
							*AgentLocation.ToCompactString(), *Alarm.LastThreatPosition.ToCompactString());
					}

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

}

// -----------------------------------------------------------------------------
// UEcoShelterReservationProcessor
// -----------------------------------------------------------------------------

UEcoShelterReservationProcessor::UEcoShelterReservationProcessor()
	: EntityQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionFlags = int32(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ExecutionOrder.ExecuteAfter.Add(UEcoShelterQueryProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true; // Ensures GameThread serialized reconciliation & subsystem mutation
}

void UEcoShelterReservationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoShelterIntentFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	EcoShelter::AddEligibilityRequirements(EntityQuery);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoShelterReservationProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World || World->GetNetMode() == NM_Client)
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

	EntityQuery.ForEachEntityChunk(Context, [this, ShelterSubsystem, CurrentTime, World](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoIdentityFragment> IdentityList = ChunkContext.GetFragmentView<FEcoIdentityFragment>();
		TArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetMutableFragmentView<FEcoShelterIntentFragment>();
		const FEcoShelterLifecycleSettings& Settings = ChunkContext.GetSharedFragment<FEcoSocialSpeciesSharedFragment>().Shelter;

		for (int32 i = 0; i < NumEntities; ++i)
		{
			if (!EcoShelter::IsEligible(ChunkContext, i)) { continue; }
			FEcoShelterIntentFragment& Intent = IntentList[i];
			const int64 AgentId = IdentityList[i].StableAgentId;
			const FMassEntityHandle Entity = ChunkContext.GetEntity(i);

			// Release handling: if agent transitioned to None but still held a reserved slot, release it
			if (Intent.State == EEcoShelterIntentState::None && Intent.TargetSlotIndex != INDEX_NONE_ECO)
			{
				if (EcoShelterDiagnostics::GetLevel() > 0 && Intent.ReservationId != 0)
				{
					UE_LOG(LogEcoSocialShelter, Log,
						TEXT("[Shelter][StateRelease] World=%s Time=%.2f Agent=%lld Reservation=%lld Slot=%d Reason=NoShelterDemand"),
						*GetNameSafe(World), CurrentTime, AgentId, Intent.ReservationId, Intent.TargetSlotIndex);
				}
				ShelterSubsystem->ReleaseSlot(Intent.TargetSlotIndex, AgentId, Intent.ReservationId);
				Intent.Reset();
				continue;
			}

			// Active reservation validation: check if reservation expired or was taken
			if (Intent.State == EEcoShelterIntentState::Reserved || Intent.State == EEcoShelterIntentState::Moving || Intent.State == EEcoShelterIntentState::Occupied)
			{
				if (!ShelterSubsystem->IsReservationValid(Intent.TargetSlotIndex, AgentId, Intent.ReservationId, CurrentTime))
				{
					// Reservation lost or lapsed
					if (EcoShelterDiagnostics::GetLevel() > 0)
					{
						UE_LOG(LogEcoSocialShelter, Log,
							TEXT("[Shelter][LeaseLost] World=%s Time=%.2f Agent=%lld Reservation=%lld State=%s Slot=%d Age=%.2f Reason=ExpiredOrMissing"),
							*GetNameSafe(World), CurrentTime, AgentId, Intent.ReservationId,
							EcoShelterDiagnostics::StateName(Intent.State), Intent.TargetSlotIndex, CurrentTime - Intent.ReservationGrantedTime);
					}
					Intent.Reset();
					Intent.NextQueryTime = CurrentTime + (Settings.IsValid() ? Settings.RetryCooldown : 1.0);
				}
				continue;
			}

			// Collect candidate proposals
			if (Intent.State == EEcoShelterIntentState::Searching && Intent.TargetSlotIndex != INDEX_NONE_ECO)
			{
				if (AgentId == 0 || !Settings.IsValid() || !FMath::IsFinite(Intent.CurrentScore))
				{
					Intent.Reset();
					continue;
				}
				FSlotProposal Proposal;
				Proposal.Entity = Entity;
				Proposal.StableAgentId = AgentId;
				Proposal.SlotIndex = Intent.TargetSlotIndex;
				Proposal.Score = Intent.CurrentScore;
				Proposal.ShelterIndex = Intent.TargetShelterIndex;
				Proposal.LeaseDuration = Settings.LeaseDuration;
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
		if (A.Score != B.Score)
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
			FEcoShelterSlot Candidate;
			if (ShelterSubsystem->GetSlotData(Proposal.SlotIndex, Candidate) && Candidate.ShelterRuntimeIndex == Proposal.ShelterIndex
				&& ShelterSubsystem->ReserveSlot(Proposal.SlotIndex, Proposal.StableAgentId, CurrentTime + Proposal.LeaseDuration, Proposal.Entity))
			{
				// Winning candidate lock
				FEcoShelterSlot SlotData;
				ShelterSubsystem->GetSlotData(Proposal.SlotIndex, SlotData);

				Intent.State = EEcoShelterIntentState::Reserved;
				Intent.TargetPosition = SlotData.Position;
				Intent.CurrentScore = Proposal.Score;
				Intent.ReservationId = SlotData.ReservationId;
				Intent.ReservationGrantedTime = CurrentTime;
				Intent.LastMovementFeedbackTime = CurrentTime;
				Intent.LastProgressTime = CurrentTime;
				Intent.BestTargetDistance = FVector::Dist(EntityManager.GetFragmentDataChecked<FTransformFragment>(Proposal.Entity).GetTransform().GetLocation(), SlotData.Position);
				Intent.LastConsumedFeedbackSequence = 0;
				bSlotAwarded = true;
				continue;
			}
		}

		// Lost competition or slot already locked: reset intent to None
		if (EcoShelterDiagnostics::GetLevel() >= 2)
		{
			UE_LOG(LogEcoSocialShelter, Log, TEXT("[Shelter][ReservationRejected] World=%s Time=%.2f Agent=%lld Slot=%d Score=%.3f Reason=CompetitionOrSlotUnavailable"),
				*GetNameSafe(World), CurrentTime, Proposal.StableAgentId, Proposal.SlotIndex, Proposal.Score);
		}
		Intent.Reset();
		Intent.NextQueryTime = CurrentTime + 0.5; // Quick retry cooldown
	}
}

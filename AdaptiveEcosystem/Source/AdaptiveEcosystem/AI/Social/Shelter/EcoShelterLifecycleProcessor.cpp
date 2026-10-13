#include "AI/Social/Shelter/EcoShelterLifecycleProcessor.h"
#include "AI/Social/Shelter/EcoShelterProcessors.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Social/Shelter/EcoShelterEligibility.h"
#include "AI/Social/Shelter/EcoShelterDiagnostics.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EntityFragments.h"
#include "MassCommonTypes.h"
#include "Engine/World.h"
#include "Misc/ScopeExit.h"

UEcoShelterLifecycleProcessor::UEcoShelterLifecycleProcessor() : EntityQuery(*this)
{
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionFlags = int32(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ExecutionOrder.ExecuteAfter.Add(UEcoShelterReservationProcessor::StaticClass()->GetFName());
	ExecutionOrder.ExecuteBefore.Add(UE::Mass::ProcessorGroupNames::Movement);
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true;
	QueryBasedPruning = EMassQueryBasedPruning::Never; // Last owner deletion must still trigger cleanup.
}

void UEcoShelterLifecycleProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoShelterIntentFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoSocialMovementRequestFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoShelterMovementFeedbackFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	EcoShelter::AddEligibilityRequirements(EntityQuery);
	// Include dead/proxy archetypes so their Social buffers and leases can be cleared.
}

void UEcoShelterLifecycleProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World || World->GetNetMode() == NM_Client) { return; }
	UEcoShelterSubsystem* Shelters = World->GetSubsystem<UEcoShelterSubsystem>();
	if (!Shelters) { return; }
	const double Now = World->GetTimeSeconds();
	const bool bLog = EcoShelterDiagnostics::GetLevel() > 0;
	if (!bLog)
	{
		NextDiagnosticsSummaryTime = 0.0;
		DiagnosticsFeedbackAccepted = DiagnosticsArrivalRejected = 0;
	}
	const bool bWriteSummary = bLog && Now >= NextDiagnosticsSummaryTime;
	int32 Matched = 0, ValidRequests = 0, NeedsShelter = 0, Searching = 0, Reserved = 0, Moving = 0, Occupied = 0;
	int32 Alert = 0, Panic = 0, MissingFeedbackBuffer = 0;
	FString Sample;
	ConfirmedReservations.Reset();
	Shelters->CleanExpiredReservations(Now);
	EntityQuery.ForEachEntityChunk(Context, [&](FMassExecutionContext& Chunk)
	{
		const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
		const auto Transforms = Chunk.GetFragmentView<FTransformFragment>();
		const auto Alarms = Chunk.GetFragmentView<FEcoAlarmStateFragment>();
		const auto Behavior = Chunk.GetFragmentView<FEcoSocialBehaviorFragment>();
		const auto Feedback = Chunk.GetFragmentView<FEcoShelterMovementFeedbackFragment>();
		auto Intents = Chunk.GetMutableFragmentView<FEcoShelterIntentFragment>();
		auto Requests = Chunk.GetMutableFragmentView<FEcoSocialMovementRequestFragment>();
		const auto& Settings = Chunk.GetSharedFragment<FEcoSocialSpeciesSharedFragment>().Shelter;
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			FEcoShelterIntentFragment& Intent = Intents[I];
			FEcoSocialMovementRequestFragment& Request = Requests[I];
			Request = {}; // Publish one authoritative snapshot; stale commands never survive release.
			const int64 AgentId = Ids[I].StableAgentId;
			const FVector Position = Transforms[I].GetTransform().GetLocation();
			ON_SCOPE_EXIT
			{
				if (bWriteSummary)
				{
					++Matched;
					ValidRequests += Request.bValid ? 1 : 0;
					NeedsShelter += Request.bValid && (Request.EffectiveAction.Cover >= 0.25f || Alarms[I].State == EEcoSocialState::Panic) ? 1 : 0;
					Alert += Request.bValid && Alarms[I].State == EEcoSocialState::Alert ? 1 : 0;
					Panic += Request.bValid && Alarms[I].State == EEcoSocialState::Panic ? 1 : 0;
					MissingFeedbackBuffer += Feedback.IsEmpty() ? 1 : 0;
					Searching += Intent.State == EEcoShelterIntentState::Searching ? 1 : 0;
					Reserved += Intent.State == EEcoShelterIntentState::Reserved ? 1 : 0;
					Moving += Intent.State == EEcoShelterIntentState::Moving ? 1 : 0;
					Occupied += Intent.State == EEcoShelterIntentState::Occupied ? 1 : 0;
					if (Sample.IsEmpty() && Intent.ReservationId != 0)
					{
						Sample = FString::Printf(TEXT("Agent=%lld Reservation=%lld State=%s Age=%.2f Distance=%.1f Cover=%.2f Alarm=%.2f ConsumedSeq=%lld FeedbackReservation=%lld FeedbackSeq=%lld"),
							AgentId, Intent.ReservationId, EcoShelterDiagnostics::StateName(Intent.State), Now - Intent.ReservationGrantedTime,
							FVector::Dist(Position, Intent.TargetPosition), Request.EffectiveAction.Cover, Alarms[I].AlarmStrength,
							Intent.LastConsumedFeedbackSequence, Feedback.IsEmpty() ? int64(0) : Feedback[I].ReservationId,
							Feedback.IsEmpty() ? int64(0) : Feedback[I].Sequence);
					}
				}
			};
			auto Release = [&](const TCHAR* Reason)
			{
				if (bLog && Intent.ReservationId != 0)
				{
					UE_LOG(LogEcoSocialShelter, Log,
						TEXT("[Shelter][StateRelease] World=%s Time=%.2f Agent=%lld Reservation=%lld State=%s Slot=%d Reason=%s"),
						*GetNameSafe(World), Now, AgentId, Intent.ReservationId, EcoShelterDiagnostics::StateName(Intent.State), Intent.TargetSlotIndex, Reason);
				}
				if (Intent.ReservationId != 0) { Shelters->ReleaseSlot(Intent.TargetSlotIndex, AgentId, Intent.ReservationId); }
				Intent.Reset();
				Intent.NextQueryTime = Now + (Settings.IsValid() ? Settings.RetryCooldown : 1.0);
			};
			const TCHAR* Ineligible = EcoShelter::IneligibilityReason(Chunk, I);
			if (Ineligible || AgentId == 0 || Position.ContainsNaN() || !Settings.IsValid())
			{
				Release(Ineligible ? Ineligible : AgentId == 0 ? TEXT("InvalidAgentId") : Position.ContainsNaN() ? TEXT("InvalidPosition") : TEXT("InvalidSettings"));
				continue;
			}
			const FEcoPolicyActionV1& Action = Behavior[I].ModulatedAction;
			if (!FMath::IsFinite(Action.Forage) || !FMath::IsFinite(Action.Cohesion) || !FMath::IsFinite(Action.FleeDist)
				|| !FMath::IsFinite(Action.Cover) || !FMath::IsFinite(Behavior[I].SocialCohesionMultiplier))
			{
				Release(TEXT("InvalidAction"));
				continue;
			}
			Request.bValid = true;
			Request.EffectiveAction = Action;
			const bool bNeedsShelter = Action.Cover >= 0.25f || Alarms[I].State == EEcoSocialState::Panic;
			const bool bActive = Intent.State == EEcoShelterIntentState::Reserved || Intent.State == EEcoShelterIntentState::Moving || Intent.State == EEcoShelterIntentState::Occupied;
			if (!bNeedsShelter || !bActive)
			{
				if (Intent.ReservationId != 0) { Release(bNeedsShelter ? TEXT("InactiveIntent") : TEXT("NoShelterDemand")); }
				continue;
			}
			FEcoShelterSlot Slot;
			if (!Shelters->IsReservationValid(Intent.TargetSlotIndex, AgentId, Intent.ReservationId, Now)
				|| !Shelters->GetSlotData(Intent.TargetSlotIndex, Slot) || Slot.ShelterRuntimeIndex != Intent.TargetShelterIndex
				|| Slot.OwnerEntity != Chunk.GetEntity(I))
			{
				Release(TEXT("InvalidLeaseOrOwner"));
				continue;
			}
			Intent.TargetPosition = Slot.Position;
			const float Distance = FVector::Dist(Position, Slot.Position);
			if (!Feedback.IsEmpty())
			{
				const auto& Result = Feedback[I];
				if (Result.ReservationId == Intent.ReservationId && Result.Sequence > Intent.LastConsumedFeedbackSequence)
				{
					if (bLog) { ++DiagnosticsFeedbackAccepted; }
					Intent.LastConsumedFeedbackSequence = Result.Sequence;
					if (Result.Status == EEcoShelterMovementStatus::Failed || Result.Status == EEcoShelterMovementStatus::Yielded)
					{
						Release(Result.Status == EEcoShelterMovementStatus::Failed ? TEXT("MovementFailed") : TEXT("MovementYielded"));
						continue;
					}
					const float ArrivalTolerance = Intent.State == EEcoShelterIntentState::Occupied ? Settings.ExitRadius : Settings.ArrivalRadius;
					const EEcoShelterIntentState PreviousState = Intent.State;
					if (Result.Status == EEcoShelterMovementStatus::Arrived && Distance <= ArrivalTolerance)
					{
						Intent.State = EEcoShelterIntentState::Occupied;
						Intent.LastMovementFeedbackTime = Now;
					}
					else if (Result.Status == EEcoShelterMovementStatus::Moving)
					{
						if (Intent.State == EEcoShelterIntentState::Reserved)
						{
							Intent.LastProgressTime = Now;
							Intent.BestTargetDistance = Distance;
						}
						if (Intent.State != EEcoShelterIntentState::Occupied) { Intent.State = EEcoShelterIntentState::Moving; }
						Intent.LastMovementFeedbackTime = Now;
					}
					else if (bLog && Result.Status == EEcoShelterMovementStatus::Arrived) { ++DiagnosticsArrivalRejected; }
					if (bLog && Intent.State != PreviousState)
					{
						UE_LOG(LogEcoSocialShelter, Log,
							TEXT("[Shelter][Transition] World=%s Time=%.2f Agent=%lld Reservation=%lld %s->%s Slot=%d Distance=%.1f Seq=%lld"),
							*GetNameSafe(World), Now, AgentId, Intent.ReservationId, EcoShelterDiagnostics::StateName(PreviousState),
							EcoShelterDiagnostics::StateName(Intent.State), Intent.TargetSlotIndex, Distance, Result.Sequence);
					}
				}
			}
			if (Intent.State == EEcoShelterIntentState::Moving && Distance <= Intent.BestTargetDistance - Settings.ProgressDistance)
			{
				Intent.BestTargetDistance = Distance;
				Intent.LastProgressTime = Now;
			}
			const bool bFeedbackTimeout = Intent.State != EEcoShelterIntentState::Reserved && Now - Intent.LastMovementFeedbackTime >= Settings.FeedbackTimeout;
			const bool bProgressTimeout = Intent.State == EEcoShelterIntentState::Moving && Now - Intent.LastProgressTime >= Settings.ProgressTimeout;
			const bool bOutsideOccupiedRadius = Intent.State == EEcoShelterIntentState::Occupied && Distance > Settings.ExitRadius;
			if (bFeedbackTimeout || bProgressTimeout || bOutsideOccupiedRadius)
			{
				Release(bFeedbackTimeout ? TEXT("FeedbackTimeout") : bProgressTimeout ? TEXT("NoProgress") : TEXT("LeftOccupiedRadius"));
				continue;
			}
			if (Intent.State != EEcoShelterIntentState::Reserved)
			{
				Shelters->RenewSlot(Intent.TargetSlotIndex, AgentId, Intent.ReservationId, Now + Settings.LeaseDuration);
				Shelters->GetSlotData(Intent.TargetSlotIndex, Slot);
			}
			ConfirmedReservations.Add(Intent.ReservationId);
			Request.Mode = Intent.State == EEcoShelterIntentState::Occupied ? EEcoSocialMovementMode::ShelterHold : EEcoSocialMovementMode::ShelterTravel;
			Request.ReservationId = Intent.ReservationId;
			Request.ShelterIndex = Intent.TargetShelterIndex;
			Request.SlotIndex = Intent.TargetSlotIndex;
			Request.TargetPosition = Slot.Position;
			Request.ArrivalRadius = Settings.ArrivalRadius;
			Request.ValidUntilWorldTime = Slot.ReservationExpireTime;
		}
	});
	// Managed slots whose owner was destroyed, lost required fragments, or became ineligible
	// were not confirmed. Legacy/manual leases without an owner retain their normal TTL.
	Shelters->ReleaseUnconfirmedReservations(ConfirmedReservations);
	if (bWriteSummary)
	{
		int32 ActiveShelters = 0, HeldSlots = 0;
		for (const FEcoShelterPoint& Point : Shelters->GetShelters()) { ActiveShelters += Point.RuntimeIndex != INDEX_NONE_ECO ? 1 : 0; }
		for (const FEcoShelterSlot& SummarySlot : Shelters->GetShelterSlots()) { HeldSlots += SummarySlot.ReservedBy != 0 ? 1 : 0; }
		UE_LOG(LogEcoSocialShelter, Log,
			TEXT("[Shelter][Summary] World=%s Time=%.2f NetMode=%d Matched=%d ValidRequests=%d Alert=%d Panic=%d NeedsShelter=%d Searching=%d Reserved=%d Moving=%d Occupied=%d ActiveShelters=%d HeldSlots=%d MissingFeedbackBuffer=%d FreshFeedback=%d ArrivalRejected=%d WaitingForMovementAck=%d"),
			*GetNameSafe(World), Now, int32(World->GetNetMode()), Matched, ValidRequests, Alert, Panic, NeedsShelter,
			Searching, Reserved, Moving, Occupied, ActiveShelters, HeldSlots, MissingFeedbackBuffer,
			DiagnosticsFeedbackAccepted, DiagnosticsArrivalRejected, Reserved);
		if (!Sample.IsEmpty()) { UE_LOG(LogEcoSocialShelter, Log, TEXT("[Shelter][Sample] World=%s %s"), *GetNameSafe(World), *Sample); }
		NextDiagnosticsSummaryTime = Now + 5.0;
		DiagnosticsFeedbackAccepted = DiagnosticsArrivalRejected = 0;
	}
}

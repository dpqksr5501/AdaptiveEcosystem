#include "Ecology/EcologySimulationSubsystem.h"
#include "Ecology/EcoFoodAllocation.h"
#include "World/EcoWorldClockSubsystem.h"
#include "AdaptiveEcosystem.h"

bool UEcologySimulationSubsystem::StartResourceSimulation(int32 Epoch, const FEcoFoodEventSettings& Day,
	const FEcoFoodEventSettings& Night, bool bLogChanges)
{
	if (!CanMutateAuthoritativeState(TEXT("StartResourceSimulation")) || ResourceEpoch != 0 || Epoch <= 0
		|| !Day.IsValid() || !Night.IsValid() || (Day.bEnabled && !RegionalStates.Contains(Day.RegionId))
		|| (Night.bEnabled && !RegionalStates.Contains(Night.RegionId))) return false;
	ResourceEpoch = Epoch;
	DayEvent = Day;
	NightEvent = Night;
	bPrintResourceChanges = bLogChanges;
	return true;
}

bool UEcologySimulationSubsystem::QueueManualStarvation(FName RegionId, const FEcoServerTimeSnapshot& RequestedAt)
{
	if (!CanMutateAuthoritativeState(TEXT("QueueManualStarvation")) || ResourceEpoch <= 0
		|| RequestedAt.WorldEpoch != ResourceEpoch || !EcoClock::IsValidPhase(RequestedAt.ServerTimeSeconds, RequestedAt.DayCycle)
		|| RequestedAt.ServerTimeSeconds < ResourceTime || RegionId.IsNone() || !RegionalStates.Contains(RegionId)
		|| PendingManualStarvation.Contains(RegionId)) return false;
	PendingManualStarvation.Add(RegionId, RequestedAt.ServerTimeSeconds);
	return true;
}

double UEcologySimulationSubsystem::GetNextScheduledTime(const FEcoServerTimeSnapshot& Time, bool bIncludeWaves) const
{
	double Next = Time.DayCycle.PhaseEndSeconds;
	const bool bDay = Time.DayCycle.Phase == EEcoDayPhase::Day;
	const FEcoFoodEventSettings& Event = bDay ? DayEvent : NightEvent;
	if (Event.bEnabled && (bDay ? LastDayEventCycle : LastNightEventCycle) != Time.DayCycle.CycleId)
	{
		Next = FMath::Min(Next, Time.DayCycle.PhaseStartSeconds
			+ (Time.DayCycle.PhaseEndSeconds - Time.DayCycle.PhaseStartSeconds) * Event.PhaseFraction);
	}
	if (bIncludeWaves)
	{
		for (const auto& Pair : SpawnCursors)
			Next = FMath::Min(Next, Pair.Value.GetNextDueTime(Time, SpawnSettings.FindChecked(Pair.Key)));
	}
	for (const auto& Pair : PendingManualStarvation)
		Next = FMath::Min(Next, Pair.Value);
	return FMath::Max(Time.ServerTimeSeconds, Next);
}

bool UEcologySimulationSubsystem::BeginResourceStep(const FEcoServerTimeSnapshot& Time, int64 StepId)
{
	if (!CanMutateAuthoritativeState(TEXT("BeginResourceStep")) || ResourceEpoch <= 0
		|| Time.WorldEpoch != ResourceEpoch || bResourceStepOpen || StepId != ResourceStepId + 1
		|| !EcoClock::IsValidPhase(Time.ServerTimeSeconds, Time.DayCycle) || Time.ServerTimeSeconds < ResourceTime) return false;
	for (FName RegionId : RegionIds)
	{
		const FRegionEcologyState& State = RegionalStates.FindChecked(RegionId);
		if (!FMath::IsFinite(State.FoodAmount) || !FMath::IsFinite(State.FoodCapacity)
			|| State.FoodAmount < 0.0f || State.FoodAmount > State.FoodCapacity) return false;
	}
	ResourceStepId = StepId;
	ResourceTime = Time.ServerTimeSeconds;
	bResourceStepOpen = true;
	bFeedingResolved = false;
	ResourceLedger.Reset();
	ResourceLedger.SetNum(RegionIds.Num());
	for (int32 I = 0; I < RegionIds.Num(); ++I)
		ResourceLedger[I].Before = RegionalStates.FindChecked(RegionIds[I]).FoodAmount;
	for (int32 I = 0; I < RegionIds.Num(); ++I)
	{
		const FName RegionId = RegionIds[I];
		const double* Due = PendingManualStarvation.Find(RegionId);
		if (!Due || *Due > ResourceTime) continue;
		FRegionEcologyState& State = RegionalStates.FindChecked(RegionId);
		FResourceLedger& Ledger = ResourceLedger[I];
		Ledger.EventLoss += State.FoodAmount;
		Ledger.bEvent = true;
		State.FoodAmount = 0.0f;
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Food Event] Source=Debug.Starvation Epoch=%d Step=%lld Due=%.3f Time=%.3f Region=%s ActualLoss=%.3f"),
			ResourceEpoch, ResourceStepId, *Due, ResourceTime, *RegionId.ToString(), Ledger.EventLoss);
		PendingManualStarvation.Remove(RegionId);
	}

	const bool bDay = Time.DayCycle.Phase == EEcoDayPhase::Day;
	const FEcoFoodEventSettings& Event = bDay ? DayEvent : NightEvent;
	int64& LastCycle = bDay ? LastDayEventCycle : LastNightEventCycle;
	const double Due = Time.DayCycle.PhaseStartSeconds
		+ (Time.DayCycle.PhaseEndSeconds - Time.DayCycle.PhaseStartSeconds) * Event.PhaseFraction;
	if (Event.bEnabled && LastCycle != Time.DayCycle.CycleId && Due <= ResourceTime)
	{
		FRegionEcologyState& State = RegionalStates.FindChecked(Event.RegionId);
		const double Before = State.FoodAmount;
		State.FoodAmount = static_cast<float>(FMath::Max(0.0, Before - Event.FoodLoss));
		FResourceLedger& Ledger = ResourceLedger[GetRegionRuntimeIndex(Event.RegionId)];
		const double ActualLoss = Before - State.FoodAmount;
		Ledger.EventLoss += ActualLoss;
		Ledger.bEvent = true;
		LastCycle = Time.DayCycle.CycleId;
		if (bPrintResourceChanges)
			UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Food Event] Epoch=%d Step=%lld Cycle=%lld Phase=%s Region=%s Due=%.3f Requested=%.3f ActualLoss=%.3f"),
				ResourceEpoch, ResourceStepId, Time.DayCycle.CycleId, bDay ? TEXT("Day") : TEXT("Night"),
				*Event.RegionId.ToString(), Due, Event.FoodLoss, ActualLoss);
	}
	return true;
}

bool UEcologySimulationSubsystem::ResolveFeeding(TConstArrayView<FEcoFeedRequest> Requests, TArray<FEcoFeedResult>& Results)
{
	Results.Reset();
	if (!CanMutateAuthoritativeState(TEXT("ResolveFeeding")) || !bResourceStepOpen || bFeedingResolved) return false;
	TArray<FEcoFeedRequest> Ordered;
	Ordered.Append(Requests.GetData(), Requests.Num());
	Ordered.Sort([](const FEcoFeedRequest& A, const FEcoFeedRequest& B) { return A.Food.StableAgentId < B.Food.StableAgentId; });
	int64 PreviousId = 0;
	// Reject the entire batch before touching shared food if any envelope is invalid/stale/duplicated.
	for (const FEcoFeedRequest& Request : Ordered)
	{
		const double* LastDue = LastAcceptedFeedTime.Find(Request.Food.StableAgentId);
		if (Request.WorldEpoch != ResourceEpoch || Request.StepId != ResourceStepId
			|| Request.Food.StableAgentId <= PreviousId || !RegionIds.IsValidIndex(Request.RegionIndex)
			|| RegionIds[Request.RegionIndex] != Request.Food.RegionId || !FMath::IsFinite(Request.DueTime)
			|| Request.DueTime < 0.0 || Request.DueTime > ResourceTime || (LastDue && Request.DueTime <= *LastDue)
			|| !FMath::IsFinite(Request.Food.RequestedAmount) || Request.Food.RequestedAmount <= 0.0f)
		{
			UE_LOG(LogAdaptiveEcosystem, Error, TEXT("[Eco Feed] Rejected batch: Step=%lld Agent=%lld Region=%s (invalid or stale envelope)"),
				ResourceStepId, Request.Food.StableAgentId, *Request.Food.RegionId.ToString());
			return false;
		}
		PreviousId = Request.Food.StableAgentId;
	}
	// Regional resources are mutated once per batch, never from the per-entity loop.
	for (int32 RegionIndex = 0; RegionIndex < RegionIds.Num(); ++RegionIndex)
	{
		TArray<double> Amounts;
		TArray<int32> RequestIndices;
		for (int32 I = 0; I < Ordered.Num(); ++I)
		{
			if (Ordered[I].RegionIndex == RegionIndex)
			{
				Amounts.Add(Ordered[I].Food.RequestedAmount);
				RequestIndices.Add(I);
			}
		}
		if (Amounts.IsEmpty()) continue;
		FRegionEcologyState& State = RegionalStates.FindChecked(RegionIds[RegionIndex]);
		TArray<double> Grants;
		if (!EcoFood::Allocate(State.FoodAmount, Amounts, Grants)) return false;
		double Granted = 0.0;
		double Requested = 0.0;
		for (int32 I = 0; I < Grants.Num(); ++I)
		{
			FEcoFeedResult& Result = Results.AddDefaulted_GetRef();
			Result.Request = Ordered[RequestIndices[I]];
			Result.GrantedAmount = Grants[I];
			Granted += Grants[I];
			Requested += Amounts[I];
			LastAcceptedFeedTime.Add(Result.Request.Food.StableAgentId, Result.Request.DueTime);
		}
		// Exhausting demand writes exact zero; no arbitrary epsilon removes positive food.
		State.FoodAmount = Requested >= State.FoodAmount ? 0.0f : static_cast<float>(FMath::Max(0.0, State.FoodAmount - Granted));
		ResourceLedger[RegionIndex].Granted = Granted;
		ResourceLedger[RegionIndex].Requests = Amounts.Num();
	}
	bFeedingResolved = true;
	return true;
}

bool UEcologySimulationSubsystem::CompleteResourceStep()
{
	if (!CanMutateAuthoritativeState(TEXT("CompleteResourceStep")) || !bResourceStepOpen || !bFeedingResolved) return false;
	TArray<FEcoResourceSnapshot> Next;
	for (int32 I = 0; I < RegionIds.Num(); ++I)
	{
		const FRegionEcologyState& State = RegionalStates.FindChecked(RegionIds[I]);
		const FResourceLedger& Ledger = ResourceLedger[I];
		FEcoResourceSnapshot& Snapshot = Next.AddDefaulted_GetRef();
		Snapshot.WorldEpoch = ResourceEpoch;
		Snapshot.StepId = ResourceStepId;
		Snapshot.Time = ResourceTime;
		Snapshot.RegionId = RegionIds[I];
		Snapshot.RegionIndex = I;
		Snapshot.Food = State.FoodAmount;
		Snapshot.Capacity = State.FoodCapacity;
		Snapshot.bDepleted = State.FoodAmount == 0.0f;
		Snapshot.EventLoss = Ledger.EventLoss;
		Snapshot.Consumed = Ledger.Granted;
		Snapshot.RoundingAdjustment = Ledger.Before - Ledger.EventLoss - Ledger.Granted - State.FoodAmount;
		const double Tolerance = 1.e-6 * FMath::Max(1.0, Ledger.Before);
		if (!FMath::IsFinite(Snapshot.RoundingAdjustment) || FMath::Abs(Snapshot.RoundingAdjustment) > Tolerance)
		{
			UE_LOG(LogAdaptiveEcosystem, Error, TEXT("[Eco Food] Resource conservation failed: Region=%s Step=%lld"), *RegionIds[I].ToString(), ResourceStepId);
			return false;
		}
		if (bPrintResourceChanges && (Ledger.bEvent || Ledger.Requests > 0))
			UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Food] Epoch=%d Step=%lld Time=%.3f Region=%s Before=%.6f EventLoss=%.6f Consumed=%.6f Rounding=%.9f After=%.6f Requests=%d Population=%d Depleted=%d"),
				ResourceEpoch, ResourceStepId, ResourceTime, *RegionIds[I].ToString(), Ledger.Before, Ledger.EventLoss,
				Ledger.Granted, Snapshot.RoundingAdjustment, State.FoodAmount, Ledger.Requests, State.Population, Snapshot.bDepleted);
	}
	CompletedResources = MoveTemp(Next);
	bResourceStepOpen = false;
	return true;
}

#include "Ecology/EcologySimulationSubsystem.h"

bool UEcologySimulationSubsystem::ConfigurePressure(const FEcoOvercrowdingSettings& Settings, double ConsumptionRate)
{
	if (!CanMutateAuthoritativeState(TEXT("ConfigurePressure")) || !InitialRequests.IsEmpty() || !Settings.IsValid()
		|| !FMath::IsFinite(ConsumptionRate) || ConsumptionRate < 0) return false;
	PressureSettings = Settings;
	PerAgentConsumptionRate = ConsumptionRate;
	return true;
}

bool UEcologySimulationSubsystem::RefreshPopulationPressure(double Time)
{
	if (!CanMutateAuthoritativeState(TEXT("RefreshPopulationPressure")) || !FMath::IsFinite(Time)) return false;
	for (auto& Pair : RegionalStates)
	{
		auto& S = Pair.Value;
		if (S.EcologicalComfortPopulation <= 0) return false;
		S.CrowdingRatio = static_cast<float>(S.ProjectedPopulation) / S.EcologicalComfortPopulation;
		const double Demand = S.ProjectedFoodConsumers * PerAgentConsumptionRate * PressureSettings.ForecastSeconds;
		S.FoodSatisfaction = Demand > 0 ? static_cast<float>(FMath::Clamp(S.FoodAmount / Demand, 0.0, 1.0)) : 1.0f;
		if (!PressureSettings.bEnabled || (S.CrowdingRatio <= PressureSettings.ExitCrowdingRatio
			&& S.FoodSatisfaction >= PressureSettings.ExitFoodSatisfaction))
		{
			S.bPressureActive = false;
			S.PressureSince = -1.0;
		}
		else if (!S.bPressureActive && (S.CrowdingRatio >= PressureSettings.EnterCrowdingRatio
			|| S.FoodSatisfaction <= PressureSettings.EnterFoodSatisfaction))
		{
			S.bPressureActive = true;
			S.PressureSince = Time;
		}
	}
	return true;
}

bool UEcologySimulationSubsystem::BuildMigrationPressure(TArray<FEcoMigrationPressureSnapshot>& Out) const
{
	Out.Reset();
	if (!IsInGameThread()) return false;
	for (FName Id : RegionIds)
	{
		const FRegionEcologyState* S = RegionalStates.Find(Id);
		if (!S) return false;
		Out.Add({S->Population, S->OutboundCount, S->IncomingCount, S->EcologicalComfortPopulation, S->bPressureActive, S->PressureSince});
	}
	return true;
}

bool UEcologySimulationSubsystem::RecordMigrations(TConstArrayView<FEcoMigrationOutcome> Arrivals)
{
	if (!CanMutateAuthoritativeState(TEXT("RecordMigrations")) || bResourceStepOpen) return false;
	TSet<int64> BatchIds;
	for (const auto& A : Arrivals)
	{
		if (A.WorldEpoch != ResourceEpoch || A.StepId != ResourceStepId || A.StableAgentId <= 0
			|| A.OriginRegionId == A.DestinationRegionId || !RegionalStates.Contains(A.OriginRegionId)
			|| !RegionalStates.Contains(A.DestinationRegionId) || BatchIds.Contains(A.StableAgentId)
			|| !FMath::IsFinite(A.DepartureTime) || !FMath::IsFinite(A.ArrivalTime) || A.ArrivalTime < A.DepartureTime) return false;
		BatchIds.Add(A.StableAgentId);
	}
	if (LastMigrationReceiptStep != ResourceStepId) { MigrationReceipts.Reset(); LastMigrationReceiptStep = ResourceStepId; }
	for (const auto& A : Arrivals)
	{
		if (MigrationReceipts.Contains(A.StableAgentId)) continue;
		MigrationReceipts.Add(A.StableAgentId);
		auto& Origin = RegionalStates.FindChecked(A.OriginRegionId);
		++Origin.MigrationOutCount;
		if (A.Reason == EEcoMigrationReason::Overcrowding) ++Origin.OvercrowdingDeparturesCompleted;
		++RegionalStates.FindChecked(A.DestinationRegionId).MigrationInCount;
	}
	return true;
}

bool UEcologySimulationSubsystem::RecordDeaths(TConstArrayView<FEcoDeathOutcome> Deaths, int64 NextStep)
{
	if (!CanMutateAuthoritativeState(TEXT("RecordDeaths")) || bResourceStepOpen || NextStep != ResourceStepId + 1) return false;
	TSet<int64> BatchIds;
	for (const auto& Death : Deaths)
	{
		if (Death.WorldEpoch != ResourceEpoch || Death.StepId != NextStep || Death.StableAgentId <= 0
			|| !RegionalStates.Contains(Death.RegionId) || !FMath::IsFinite(Death.Time)
			|| Death.Cause == EEcoDeathCause::None || BatchIds.Contains(Death.StableAgentId)) return false;
		BatchIds.Add(Death.StableAgentId);
	}
	if (LastDeathReceiptStep != NextStep) { DeathReceipts.Reset(); LastDeathReceiptStep = NextStep; }
	for (const auto& Death : Deaths)
	{
		if (DeathReceipts.Contains(Death.StableAgentId)) continue;
		DeathReceipts.Add(Death.StableAgentId);
		auto& State = RegionalStates.FindChecked(Death.RegionId);
		if (Death.Cause == EEcoDeathCause::Starvation) ++State.StarvationDeaths;
		else if (Death.Cause == EEcoDeathCause::Predation)
		{
			FEcoPredationEvent Event;
			Event.RegionId = Death.RegionId; Event.PreyStableAgentId = Death.StableAgentId;
			Event.PredatorStableAgentId = Death.PredatorStableAgentId;
			ApplyPredationEvent(Event);
		}
		else ++State.ExternalDeaths;
		// Receipt watermark is no longer needed once the unique lifetime has ended.
		LastAcceptedFeedTime.Remove(Death.StableAgentId);
		// No predation event for starvation or unattributed external damage.
	}
	return true;
}

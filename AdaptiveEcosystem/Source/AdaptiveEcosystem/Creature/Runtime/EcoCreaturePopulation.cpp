#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Network/EcoGameState.h"
#include "World/EcologyRegion.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

bool AEcoCreatureIntegrationSpawner::ReconcilePopulation()
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_Population);
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	TArray<FName> Order; Ecology->GetRegionIds(Order);
	TArray<FEcoRegionPopulationSnapshot> Metrics; Metrics.SetNum(Order.Num());
	for (int32 I = 0; I < Order.Num(); ++I) { Metrics[I].RegionId = Order[I]; Metrics[I].FoodConsumerCount = 0; }
	int32 Alive = 0; TSet<int64> Ids;
	for (const auto E : Owned)
	{
		if (!EM.IsEntityValid(E)) continue;
		const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		if (V.HP <= 0) continue;
		const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
		const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(E);
		const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(E);
		const int32 I = Region.CurrentRegionIndex;
		if (!Metrics.IsValidIndex(I) || Metrics[I].RegionId != Region.CurrentRegionId || Id.StableAgentId <= 0
            || Ids.Contains(Id.StableAgentId) || !FMath::IsFinite(V.Energy) || !FMath::IsFinite(V.MaxEnergy)
            || V.MaxEnergy <= 0 || !FMath::IsFinite(V.HP)) return false;
		Ids.Add(Id.StableAgentId); ++Alive;
		auto& M = Metrics[I]; ++M.Population;
		const bool Consumer = Id.SpeciesId == TEXT("Herbivore");
		M.FoodConsumerCount += Consumer;
		M.AverageEnergy += FMath::Clamp(V.Energy / V.MaxEnergy, 0.f, 1.f);
		M.ResidentCount += Travel.State == EEcoResidenceState::Resident;
		M.TravelingCount += Travel.State == EEcoResidenceState::Traveling;
		M.WaitingCount += Travel.State == EEcoResidenceState::WaitingForFood;
		if (Travel.State == EEcoResidenceState::Traveling)
		{
			const int32 Target = Travel.TargetRegionIndex;
			if (!Metrics.IsValidIndex(Target) || Metrics[Target].RegionId != Travel.TargetRegionId) return false;
			if (Target != I)
			{
				++M.OutboundCount; ++Metrics[Target].IncomingCount;
				M.FoodConsumerOutbound += Consumer; Metrics[Target].FoodConsumerIncoming += Consumer;
			}
		}
	}
	if (Alive != SuccessfulBirths - CommittedDeaths) return false;
	for (auto& M : Metrics)
	{
		M.AverageEnergy /= FMath::Max(1, M.Population);
		if (!Ecology->UpdatePopulationMetrics(M)) return false;
	}
	return true;
}

void AEcoCreatureIntegrationSpawner::PublishSummary()
{
	if (!ReconcilePopulation()) { FailRuntime(TEXT("Population conservation")); return; }
	if (Step <= 0) return;
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_Summary);
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	FEcoCompletedWorldSummary Summary; Summary.Time = CompletedTime;
	Summary.StepId = Step; Summary.Revision = ++SummaryRevision;
	for (const AEcologyRegion* Region : Regions)
	{
		FRegionEcologyState S;
		if (!Region || !Ecology->GetRegionState(Region->RegionId, S)) { FailRuntime(TEXT("Unloaded region")); return; }
		auto& R = Summary.Regions.AddDefaulted_GetRef(); R.RegionId = Region->RegionId;
		R.WorldEpoch = Summary.Time.WorldEpoch; R.SummaryRevision = Summary.Revision;
		R.Population = S.Population; R.AverageEnergy = S.AverageEnergy;
		R.Environment = S.CompletedEnvironment;
		R.EffectiveFoodRegenerationRate = S.FoodRegenerationRate * S.EffectiveRegenerationMultiplier;
		R.FoodAmount = S.FoodAmount; R.FoodCapacity = S.FoodCapacity; R.PredationHistory = S.PredationHistory;
		R.ResidentCount = S.ResidentCount; R.OutboundCount = S.OutboundCount; R.IncomingCount = S.IncomingCount;
		R.ProjectedPopulation = S.ProjectedPopulation; R.EcologicalComfortPopulation = S.EcologicalComfortPopulation;
		R.CrowdingRatio = S.CrowdingRatio; R.FoodSatisfaction = S.FoodSatisfaction;
		R.bPressureActive = S.bPressureActive; R.PressureSince = S.PressureSince;
		R.StarvationDeaths = S.StarvationDeaths; R.ExternalDeaths = S.ExternalDeaths;
		R.MigrationInCount = S.MigrationInCount; R.MigrationOutCount = S.MigrationOutCount;
		R.OvercrowdingDeparturesCompleted = S.OvercrowdingDeparturesCompleted;
		R.TravelingCount = S.TravelingCount; R.WaitingCount = S.WaitingCount;
	}
	TMap<FName, TMap<FName, int32>> SpeciesIndices;
	// Keep extinct rows: a zero population must still carry its death/migration receipts.
	for (const auto& Region : SpeciesTotals) for (const auto& Species : Region.Value)
	{
		const int32 Index = Summary.Species.AddDefaulted();
		auto& Row = Summary.Species[Index]; Row.RegionId = Region.Key; Row.SpeciesId = Species.Key;
		Row.Births = Species.Value.Births; Row.Deaths = Species.Value.Deaths;
		Row.MigrationIn = Species.Value.Incoming; Row.MigrationOut = Species.Value.Outgoing;
		SpeciesIndices.FindOrAdd(Region.Key).Add(Species.Key, Index);
	}
	for (const auto E : Owned)
	{
		if (!EM.IsEntityValid(E)) continue;
		const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E); if (V.HP <= 0) continue;
		const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
		const FName Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId;
		auto& Indices = SpeciesIndices.FindOrAdd(Region);
		int32* Index = Indices.Find(Id.SpeciesId);
		if (!Index)
		{
			const int32 New = Summary.Species.AddDefaulted();
			Summary.Species[New].RegionId = Region; Summary.Species[New].SpeciesId = Id.SpeciesId;
			Indices.Add(Id.SpeciesId, New); Index = Indices.Find(Id.SpeciesId);
		}
		auto& Row = Summary.Species[*Index]; ++Row.Population; Row.AverageEnergy += V.Energy / V.MaxEnergy;
	}
	for (auto& Row : Summary.Species)
	{
		if (Row.Population != Row.Births - Row.Deaths + Row.MigrationIn - Row.MigrationOut)
		{ FailRuntime(TEXT("Region/species population conservation")); return; }
		Row.AverageEnergy /= FMath::Max(1, Row.Population);
	}
	Summary.Species.Sort([](const FEcoSpeciesPopulationSummary& A, const FEcoSpeciesPopulationSummary& B)
	{ return A.RegionId == B.RegionId ? A.SpeciesId.LexicalLess(B.SpeciesId) : A.RegionId.LexicalLess(B.RegionId); });
	GetWorld()->GetGameState<AEcoGameState>()->PublishEcologySummary(Summary);
}

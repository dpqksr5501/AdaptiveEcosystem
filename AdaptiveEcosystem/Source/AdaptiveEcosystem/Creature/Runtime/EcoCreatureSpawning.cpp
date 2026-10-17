#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "Creature/Runtime/EcoCreatureNetworkTrait.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoMassNetworkBootstrap.h"
#include "Mass/EcoMassNetworkSubsystem.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplate.h"
#include "Network/EcoGameState.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcoWorldClockSubsystem.h"
#include "EngineUtils.h"
#include "Core/EcoRuntimeSettings.h"
#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"

bool AEcoCreatureIntegrationSpawner::BuildSpawnPositions(const FEcoCreatureSpawnGroup& Group, int32 Count, bool bPredator, TArray<FVector>& Out) const
{
	Out.Reset();
	const auto Found = Regions.FindByPredicate([&](const AEcologyRegion* R) { return R->RegionId == Group.RegionId; });
	if (!Found || Count < 0) return false;
	const auto& Authored = bPredator ? Group.WolfSpawnPoints : Group.HerbivoreSpawnPoints;
	if (!Authored.IsEmpty() && Authored.Num() < Count) return false;
	for (int32 I = 0; I < Count; ++I)
	{
		const double Angle = (I + (bPredator ? 2 : 0)) * 2.399963;
		const FVector Hint = Authored.IsEmpty() ? (*Found)->GetActorLocation()
			+ FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0) * (bPredator ? 1600 : 600) : Authored[I];
		FVector Ground;
		if (!EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Hint, Ground) || !(*Found)->ContainsPosition(Ground))
		{
			UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Invalid spawn ground Region=%s Predator=%d Candidate=%d Hint=%s"),
				*Group.RegionId.ToString(), bPredator, I, *Hint.ToCompactString());
			return false;
		}
		Out.Add(Ground);
	}
	return true;
}

bool AEcoCreatureIntegrationSpawner::StartAuthority()
{
	TArray<FString> Errors, Notes;
	if (!CollectSetupIssues(Errors, Notes))
	{
		for (const FString& Error : Errors) UE_LOG(LogTemp, Error, TEXT("[Eco Setup] %s"), *Error);
		return false;
	}
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
	auto* Registry = GetWorld()->GetSubsystem<UEcoWorldProviderRegistry>();
	if (!Ecology || !Clock || !Registry || Clock->IsClockRunning() || Regions.IsEmpty()
		|| Groups.IsEmpty() || GlobalPopulationLimit < 1 || GlobalPopulationLimit > 512
		|| !FMath::IsFinite(EnergyDrainPerSecond) || EnergyDrainPerSecond < 0
		|| !FMath::IsFinite(EnergyPerFood) || EnergyPerFood < 0 || !Migration.IsValid()) return false;
	if (!FMath::IsFinite(StarvationGraceSeconds) || StarvationGraceSeconds < 0
		|| !FMath::IsFinite(StarvationDamagePerSecond) || StarvationDamagePerSecond <= 0
		|| !FMath::IsFinite(PredatorEnergyDrainPerSecond) || PredatorEnergyDrainPerSecond < 0
		|| !FMath::IsFinite(PredatorEnergyPerCapture) || PredatorEnergyPerCapture < 0) return false;
	if (!FMath::IsFinite(InterpolationDelaySeconds) || InterpolationDelaySeconds < 0 || InterpolationDelaySeconds > 1
		|| !FMath::IsFinite(HostVisualDistance) || HostVisualDistance < 0
		|| !FMath::IsFinite(FarSimulationDistance) || FarSimulationDistance < 4000
		|| !FMath::IsFinite(FarPolicyIntervalMultiplier) || FarPolicyIntervalMultiplier < 1 || FarPolicyIntervalMultiplier > 8) return false;
	for (TActorIterator<AEcoMassNetworkBootstrap> It(GetWorld()); It; ++It)
	{ UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Use a separate level; M3 Bootstrap cannot share this coordinator.")); return false; }
	for (TActorIterator<AEcoCreatureIntegrationSpawner> It(GetWorld()); It; ++It)
	{ if (*It != this) { UE_LOG(LogTemp, Error, TEXT("[Eco Integration] Only one coordinator is allowed.")); return false; } }
	int64 Total = 0; TSet<FName> GroupIds;
	for (const auto& Group : Groups)
	{
		if (Group.RegionId.IsNone() || GroupIds.Contains(Group.RegionId) || Group.Herbivores < 0 || Group.Wolves < 0 || !Group.Schedule.IsValid()) return false;
		GroupIds.Add(Group.RegionId); Total += (IsSpeciesEnabled(false) ? int64(Group.Herbivores) : 0) + (IsSpeciesEnabled(true) ? Group.Wolves : 0);
		if (!Regions.ContainsByPredicate([&](const AEcologyRegion* R) { return R->RegionId == Group.RegionId; })) return false;
		if (Group.bUseFoodPatchPosition && (Group.FoodPatchPosition.ContainsNaN()
			|| !(*Regions.FindByPredicate([&](const AEcologyRegion* R) { return R->RegionId == Group.RegionId; }))->ContainsPosition(Group.FoodPatchPosition))) return false;
	}
	if (Total > GlobalPopulationLimit || (IsSpeciesEnabled(false) && !HerbivoreActorClass) || (IsSpeciesEnabled(true) && !WolfActorClass)) return false;
	// Validate every habitat before starting clock/resources or creating any Entity.
	for (const auto& Group : Groups)
	{
		TArray<FVector> Positions;
		if ((IsSpeciesEnabled(false) && !BuildSpawnPositions(Group, Group.Herbivores, false, Positions))
			|| (IsSpeciesEnabled(true) && !BuildSpawnPositions(Group, Group.Wolves, true, Positions))) return false;
	}
	if (!Ecology->ConfigurePopulationLimit(GlobalPopulationLimit)) return false;
	PopulationPressure.bEnabled = bEnablePopulationPressure;
	if (!PopulationPressure.IsValid() || MaxCatchUpSteps < 1 || MaxCatchUpSteps > 32
		|| !Ecology->ConfigurePressure(PopulationPressure, 1.0)) return false;
	for (AEcologyRegion* Region : Regions)
	{
		FRegionEcologyState State;
		if (!Region->MakeInitialEcologyState(State) || !Ecology->RegisterRegionState(State)) return false;
		GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->RegisterRegion(Region);
	}
	for (const auto& Group : Groups) if (!Ecology->RegisterSpawnSchedule(Group.RegionId, Group.Schedule)) return false;
	auto* GameState = GetWorld()->GetGameState<AEcoGameState>();
	if (!GameState) return false;
	FEcoFoodEventSettings Day, Night; Day.bEnabled = Night.bEnabled = false;
	if (!Clock->StartClock(GameState->GetWorldEpoch(), DaySeconds, NightSeconds)
		|| !Ecology->StartResourceSimulation(GameState->GetWorldEpoch(), Day, Night,
			GetDefault<UEcoRuntimeSettings>()->bPrintResourceChanges)) return false;
	Registry->SetFoodProvider(this); Registry->SetCoverProvider(this);
	if (auto* Slots = GetWorld()->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>()) Slots->bAllowFixtures = bEnableSpeciesAIFixtures;
	for (const auto& Group : Groups)
	{
		FEcoSpawnRequest Request;
		const int32 DeerCount = IsSpeciesEnabled(false) ? Group.Herbivores : 0;
		const int32 WolfCount = IsSpeciesEnabled(true) ? Group.Wolves : 0;
		if (DeerCount + WolfCount == 0) continue;
		if (!Ecology->RequestInitialSpawn(Group.RegionId, DeerCount + WolfCount, Clock->GetServerTime(), Request)) return false;
		const int32 Actual = Spawn(Group.RegionId, DeerCount, false) + Spawn(Group.RegionId, WolfCount, true);
		PublishSummary(); // Commit population before releasing this group's spawn reservation.
		if (!Ecology->CompleteSpawnRequest(Request.RequestId, Actual) || Actual != Request.Count) return false;
	}
	GameState->SetMassReplicationReady(true); GameState->SetWorldPhase(EEcoWorldPhase::Running);
	UE_LOG(LogTemp, Log, TEXT("[Eco Integration] Authority ready: Agents=%d Regions=%d PPO+Social+MassBubble"), Owned.Num(), Regions.Num());
	return true;
}

int32 AEcoCreatureIntegrationSpawner::Spawn(FName RegionId, int32 Count, bool bPredator)
{
	if (GetNetMode() == NM_Client || Count <= 0 || !IsSpeciesEnabled(bPredator)) return 0;
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>();
	const auto Found = Regions.FindByPredicate([&](const AEcologyRegion* R) { return R->RegionId == RegionId; });
	if (!Ecology || !Spawner || !Found) return 0;
	TArray<FVector> Positions;
	const auto* Group = Groups.FindByPredicate([&](const FEcoCreatureSpawnGroup& G) { return G.RegionId == RegionId; });
	if (!Group || !BuildSpawnPositions(*Group, Count, bPredator, Positions)) return 0;
	auto& EM = Spawner->GetEntityManagerChecked();
	TArray<FMassEntityHandle> Entities;
	const auto& Template = (bPredator ? WolfConfig : HerbivoreConfig)->GetOrCreateEntityTemplate(*GetWorld());
	auto Creation = Spawner->SpawnEntities(Template, Count, Entities);
	const FName Species = bPredator ? FName(TEXT("Wolf")) : FName(TEXT("Herbivore"));
	const int32 SpeciesIndex = Ecology->RegisterSpecies(Species);
	for (int32 I = 0; I < Entities.Num(); ++I)
	{
		auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entities[I]);
		Id.StableAgentId = Ecology->AllocateStableAgentId(); Id.SpeciesId = Species; Id.SpeciesRuntimeIndex = SpeciesIndex;
		auto& Membership = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entities[I]);
		Membership.CurrentRegionId = RegionId; Membership.CurrentRegionIndex = Ecology->GetRegionRuntimeIndex(RegionId);
		const auto Time = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime();
		auto& Runtime = EM.GetFragmentDataChecked<FEcoVitalsRuntimeFragment>(Entities[I]);
		Runtime.WorldEpoch = Time.WorldEpoch; Runtime.LastTime = Time.ServerTimeSeconds; Runtime.LastStepId = Step;
		if (auto* Policy = EM.GetFragmentDataPtr<FEcoPolicyRuntimeFragment>(Entities[I]))
			Policy->PolicyElapsedSeconds = double(Id.StableAgentId % EcoBehaviorConfig::PolicyInterval) / 60.0;
		auto& Lifetime = EM.GetFragmentDataChecked<FEcoLifetimeFragment>(Entities[I]);
		Lifetime.SpawnTimeSeconds = Time.ServerTimeSeconds; Lifetime.NextFeedTimeSeconds = Time.ServerTimeSeconds + 1.0;
		auto& Profile = EM.GetFragmentDataChecked<FEcoCreatureSurvivalFragment>(Entities[I]);
		Profile.Settings.bEnabled = !bPredator || bEnablePredatorSurvival;
		// v3 owns action-dependent metabolism; M4 still commits all death receipts and cleanup.
		if (EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entities[I])) Profile.Settings.bEnabled = false;
		Profile.Settings.BaseMetabolism = bPredator ? PredatorEnergyDrainPerSecond : EnergyDrainPerSecond;
		Profile.Settings.TravelMetabolism = 0.0f;
		Profile.Settings.FoodEnergyGain = EnergyPerFood;
		Profile.Settings.StarvationGraceSeconds = StarvationGraceSeconds;
		Profile.Settings.StarvationDamagePerSecond = StarvationDamagePerSecond;
		Profile.EnergyPerPredation = PredatorEnergyPerCapture;
		const double A = (I + (bPredator ? 2 : 0)) * 2.399963;
		const FVector Position = Positions[I];
		EM.GetFragmentDataChecked<FTransformFragment>(Entities[I]).GetMutableTransform() = FTransform(FRotator(0, FMath::RadiansToDegrees(A), 0), Position);
		Owned.Add(Entities[I]);
		UE_LOG(LogTemp, Log, TEXT("[Eco Integration][Spawn] Id=%lld Region=%s Species=%s Ground=%s"),
			Id.StableAgentId, *RegionId.ToString(), *Species.ToString(), *Position.ToCompactString());
	}
	Creation.Reset();
	SuccessfulBirths += Entities.Num();
	SpeciesTotals.FindOrAdd(RegionId).FindOrAdd(Species).Births += Entities.Num();
	return Entities.Num();
}

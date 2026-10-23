#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureNetworkTrait.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Mass/EcoMassNetworkBootstrap.h"
#include "World/EcologyRegion.h"
#include "AI/Social/Shelter/EcoShelterAnchor.h"
#include "Core/EcoRuntimeSettings.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "Network/EcoGameState.h"

bool AEcoCreatureIntegrationSpawner::CollectSetupIssues(TArray<FString>& Errors, TArray<FString>& Notes) const
{
	Errors.Reset(); Notes.Reset();
	UWorld* World = GetWorld();
	if (!World) { Errors.Add(TEXT("Coordinator has no World.")); return false; }
    if(bEnableEcosystemLife&&!bUseV3Policy)Errors.Add(TEXT("Ecosystem Life requires the supported Integrated Native V3 backend; V1/SpeciesAI life execution is not implemented."));
	int32 Coordinators = 0;
	for (TActorIterator<AEcoCreatureIntegrationSpawner> It(World); It; ++It) ++Coordinators;
	if (Coordinators != 1) Errors.Add(FString::Printf(TEXT("Keep exactly one EcoCreatureIntegrationSpawner; found %d."), Coordinators));
	for (TActorIterator<AEcoMassNetworkBootstrap> It(World); It; ++It)
		Errors.Add(FString::Printf(TEXT("Remove M3 Box Bootstrap %s from this creature level."), *It->GetName()));
	if (World->IsGameWorld() && World->GetNetMode() != NM_Client)
	{
		const auto* State = World->GetGameState<AEcoGameState>();
		if (!State || State->GetWorldEpoch() <= 0)
			Errors.Add(TEXT("World Settings: use EcoCreatureIntegrationGameMode (or its child), with initialized EcoGameState/WorldEpoch."));
	}
	else Notes.Add(TEXT("World Settings: select EcoCreatureIntegrationGameMode or a child; assigning only GameState does not initialize WorldEpoch."));
	const auto ValidateConfig = [&Errors](const UMassEntityConfigAsset* Config, bool bPredator)
	{
		const TCHAR* Field = bPredator ? TEXT("Wolf Config") : TEXT("Herbivore Config");
		const auto* Trait = Config ? Cast<UEcoCreatureNetworkTrait>(Config->FindTrait(UEcoCreatureNetworkTrait::StaticClass())) : nullptr;
		if (!Trait) { Errors.Add(FString::Printf(TEXT("%s: assign a saved EntityConfig with Eco Integrated Creature trait."), Field)); return; }
		if (Trait->bPredator != bPredator) Errors.Add(FString::Printf(TEXT("%s: Predator must be %s (%s)."), Field,
			bPredator ? TEXT("true") : TEXT("false"), *Config->GetPathName()));
		FString Error; if (!Trait->ValidateNetworkSettings(Error)) Errors.Add(FString::Printf(TEXT("%s: %s"), Field, *Error));
		if (Trait->bUseSpeciesAI && (!Trait->SpeciesAIProfile || Trait->SpeciesAIProfile->bPredator != bPredator
			|| !Trait->SpeciesAIProfile->Validate(Error))) Errors.Add(FString::Printf(TEXT("%s Species AI: %s"), Field, *Error));
	};
	if (IsSpeciesEnabled(false)) ValidateConfig(HerbivoreConfig, false);
	if (IsSpeciesEnabled(true)) ValidateConfig(WolfConfig, true);
	if (HerbivoreConfig && HerbivoreConfig == WolfConfig) Errors.Add(TEXT("Herbivore Config and Wolf Config must be separate role templates."));
	const auto ValidateVisual = [&Errors, &Notes](TSubclassOf<AEcoCreatureRepresentationActor> Class, FName Species, const TCHAR* Field)
	{
		const auto* Defaults = Class ? Class->GetDefaultObject<AEcoCreatureRepresentationActor>() : nullptr;
		if (!Defaults || Defaults->VisualSpeciesId != Species)
			Errors.Add(FString::Printf(TEXT("%s: use a passive representation with Visual Species Id=%s."), Field, *Species.ToString()));
		else if (!Defaults->VisualMesh || !Defaults->LocomotionBlendSpace)
			Notes.Add(FString::Printf(TEXT("%s has no mesh/Blend Space; use the saved BP_EcoDeer/BP_EcoWolf for team visuals."), Field));
	};
	if (IsSpeciesEnabled(false)) ValidateVisual(HerbivoreActorClass, TEXT("Herbivore"), TEXT("Herbivore Actor Class"));
	if (IsSpeciesEnabled(true)) ValidateVisual(WolfActorClass, TEXT("Wolf"), TEXT("Wolf Actor Class"));
	if (!GetDefault<UEcoRuntimeSettings>()->ConnectionBudget.IsValid()) Errors.Add(TEXT("Project Settings: invalid Connection Budget."));
	if (GlobalPopulationLimit < 1 || GlobalPopulationLimit > 512) Errors.Add(TEXT("Global Population Limit must be 1..512."));
	if (!FMath::IsFinite(DaySeconds) || DaySeconds < 1 || !FMath::IsFinite(NightSeconds) || NightSeconds < 1)
		Errors.Add(TEXT("Day Seconds and Night Seconds must be finite and at least 1."));
	if (!Migration.IsValid()) Errors.Add(TEXT("Migration settings are invalid."));
	if (!PopulationPressure.IsValid() || MaxCatchUpSteps < 1 || MaxCatchUpSteps > 32)
		Errors.Add(TEXT("Pressure settings or Max Catch Up Steps (1..32) are invalid."));
	if (!FMath::IsFinite(EnergyDrainPerSecond) || EnergyDrainPerSecond < 0 || !FMath::IsFinite(EnergyPerFood) || EnergyPerFood < 0
		|| !FMath::IsFinite(StarvationGraceSeconds) || StarvationGraceSeconds < 0
		|| !FMath::IsFinite(StarvationDamagePerSecond) || StarvationDamagePerSecond <= 0
		|| !FMath::IsFinite(PredatorEnergyDrainPerSecond) || PredatorEnergyDrainPerSecond < 0
		|| !FMath::IsFinite(PredatorEnergyPerCapture) || PredatorEnergyPerCapture < 0)
		Errors.Add(TEXT("Vitals/Predator settings must be finite and nonnegative; Starvation Damage must be positive."));
	if (!FMath::IsFinite(InterpolationDelaySeconds) || InterpolationDelaySeconds < 0 || InterpolationDelaySeconds > 1
		|| !FMath::IsFinite(HostVisualDistance) || HostVisualDistance < 0
		|| !FMath::IsFinite(FarSimulationDistance) || FarSimulationDistance < 4000
		|| !FMath::IsFinite(FarPolicyIntervalMultiplier) || FarPolicyIntervalMultiplier < 1 || FarPolicyIntervalMultiplier > 8)
		Errors.Add(TEXT("Visual/Scheduling settings: interpolation 0..1s, nonnegative Host distance, Far distance >=4000cm, multiplier 1..8."));
	if (bUseHabitatStreaming && (!FMath::IsFinite(HabitatStreamingRadius) || HabitatStreamingRadius < 3000))
		Errors.Add(TEXT("Habitat Streaming Radius must be finite and at least 3000cm."));
	TMap<FName, const AEcologyRegion*> RegionById;
	for (TActorIterator<AEcologyRegion> It(World); It; ++It)
	{
		const AEcologyRegion* Region = *It;
		if (Region->RegionId.IsNone() || RegionById.Contains(Region->RegionId))
		{ Errors.Add(FString::Printf(TEXT("Region %s: Region Id is empty or duplicated (%s)."), *Region->GetName(), *Region->RegionId.ToString())); continue; }
		RegionById.Add(Region->RegionId, Region);
		FRegionEcologyState State;
		if (!Region->MakeInitialEcologyState(State)) Errors.Add(FString::Printf(TEXT("Region %s: invalid Food/Capacity/regeneration/comfort values."), *Region->RegionId.ToString()));
		const auto& Weather = Region->EnvironmentState;
		if (!FMath::IsFinite(Weather.Temperature) || !FMath::IsFinite(Weather.Humidity) || Weather.Humidity < 0 || Weather.Humidity > 1
			|| !FMath::IsFinite(Weather.Rainfall) || Weather.Rainfall < 0 || Weather.Rainfall > 1)
			Errors.Add(FString::Printf(TEXT("Region %s: Temperature must be finite; Humidity/Rainfall must be 0..1."), *Region->RegionId.ToString()));
		if (!Region->RegionBounds || !Region->RegionBounds->GetComponentTransform().IsValid()
			|| Region->RegionBounds->GetUnscaledBoxExtent().ContainsNaN()
			|| Region->RegionBounds->GetUnscaledBoxExtent().GetMin() <= 0
			|| Region->RegionBounds->GetComponentTransform().GetScale3D().GetAbs().GetMin() <= UE_SMALL_NUMBER)
			Errors.Add(FString::Printf(TEXT("Region %s: bounds need a valid transform, positive extent and nonzero scale."), *Region->RegionId.ToString()));
		if (Region->ArrivalOffset.ContainsNaN() || !Region->ContainsPosition(Region->GetActorTransform().TransformPosition(Region->ArrivalOffset)))
			Errors.Add(FString::Printf(TEXT("Region %s: Arrival Offset is local-space and must stay inside Region Bounds."), *Region->RegionId.ToString()));
	}
	if (RegionById.IsEmpty()) Errors.Add(TEXT("No loaded EcologyRegion actors. Place regions and load their World Partition cells."));
	for (const auto& Pair : RegionById) for (FName Neighbor : Pair.Value->AdjacentRegionIds)
	{
		if (Neighbor == Pair.Key || !RegionById.Contains(Neighbor))
			Errors.Add(FString::Printf(TEXT("Region %s: Adjacent Region Id %s is self or missing."), *Pair.Key.ToString(), *Neighbor.ToString()));
		else if (!RegionById[Neighbor]->AdjacentRegionIds.Contains(Pair.Key))
			Notes.Add(FString::Printf(TEXT("Adjacency %s -> %s is one-way; add the reverse edge if return migration is intended."), *Pair.Key.ToString(), *Neighbor.ToString()));
	}
	int64 Total = 0; TSet<FName> GroupIds;
	if (Groups.IsEmpty()) Errors.Add(TEXT("Groups must contain at least one habitat."));
	if (bEnableSpeciesAIFixtures && EnabledSpecies == EEcoEnabledSpecies::Both)
		Errors.Add(TEXT("Species AI fixtures require DeerOnly or WolfOnly; production Both forbids fixture input/rewards."));
	for (const auto& Group : Groups)
	{
		const FString Label = Group.RegionId.ToString();
		if (Group.RegionId.IsNone() || GroupIds.Contains(Group.RegionId)) Errors.Add(FString::Printf(TEXT("Group %s: Region Id is empty or duplicated."), *Label));
		GroupIds.Add(Group.RegionId);
		const auto* RegionPtr = RegionById.Find(Group.RegionId);
		if (!RegionPtr) { Errors.Add(FString::Printf(TEXT("Group %s: matching EcologyRegion is missing."), *Label)); continue; }
		if (Group.Herbivores < 0 || Group.Wolves < 0 || !Group.Schedule.IsValid())
			Errors.Add(FString::Printf(TEXT("Group %s: counts must be nonnegative and Schedule valid."), *Label));
		const int64 Count = (IsSpeciesEnabled(false) ? int64(Group.Herbivores) : 0) + (IsSpeciesEnabled(true) ? Group.Wolves : 0); Total += Count;
		if (Count > Group.Schedule.RegionPopulationLimit)
			Errors.Add(FString::Printf(TEXT("Group %s: initial deer+wolves=%lld exceeds Schedule Region Population Limit=%d."), *Label, Count, Group.Schedule.RegionPopulationLimit));
		const auto CheckPoints = [&Errors, &Notes, &Group, RegionPtr](const TArray<FVector>& Points, int32 Required, const TCHAR* Field)
		{
			if (!Points.IsEmpty() && Points.Num() < Required) Errors.Add(FString::Printf(TEXT("Group %s: %s needs at least %d world-space entries."), *Group.RegionId.ToString(), Field, Required));
			if (Points.IsEmpty() && Required > 0) Notes.Add(FString::Printf(TEXT("Group %s: empty %s uses a ring around Region center. Author explicit positions on the large terrain."), *Group.RegionId.ToString(), Field));
			for (int32 I = 0; I < Points.Num(); ++I) if (Points[I].ContainsNaN() || !(*RegionPtr)->ContainsPosition(Points[I]))
				Errors.Add(FString::Printf(TEXT("Group %s: %s[%d] is invalid or outside Region Bounds."), *Group.RegionId.ToString(), Field, I));
		};
		if (IsSpeciesEnabled(false)) CheckPoints(Group.HerbivoreSpawnPoints, Group.Herbivores, TEXT("Herbivore Spawn Points"));
		if (IsSpeciesEnabled(true)) CheckPoints(Group.WolfSpawnPoints, Group.Wolves, TEXT("Wolf Spawn Points"));
		if (bEnableWaves && IsSpeciesEnabled(false) && !Group.HerbivoreSpawnPoints.IsEmpty() && Group.HerbivoreSpawnPoints.Num() < FMath::Max(Group.Schedule.DayCount, Group.Schedule.NightCount))
			Errors.Add(FString::Printf(TEXT("Group %s: Herbivore Spawn Points must also cover the largest requested wave."), *Label));
		if (Group.bUseFoodPatchPosition && (Group.FoodPatchPosition.ContainsNaN() || !(*RegionPtr)->ContainsPosition(Group.FoodPatchPosition)))
			Errors.Add(FString::Printf(TEXT("Group %s: Food Patch Position is world-space and must stay inside its region."), *Label));
	}
	if (Total > GlobalPopulationLimit) Errors.Add(FString::Printf(TEXT("Initial population %lld exceeds Global Population Limit=%d."), Total, GlobalPopulationLimit));
	if (FootstepAudioSet && !FootstepAudioSet->IsValidConfiguration()) Errors.Add(TEXT("Footstep Audio Set is assigned but invalid."));
	if (!FootstepAudioSet) Notes.Add(TEXT("Footstep Audio Set is empty: visual movement works, but creature footstep audio/noise cadence is disabled."));
	int32 Shelters = 0;
	for (TActorIterator<AEcoShelterAnchor> It(World); It; ++It) ++Shelters;
	if (!Shelters) Notes.Add(TEXT("No Shelter Anchor is loaded. Flee/alarm can run; shelter arrival/occupancy cannot be checked."));
#if WITH_EDITOR
	if (World->GetWorldPartition())
	{
		if (GetIsSpatiallyLoaded()) Notes.Add(TEXT("Coordinator: uncheck Is Spatially Loaded to keep the authority service alive."));
		for (const auto& Pair : RegionById) if (Pair.Value->GetIsSpatiallyLoaded())
			Notes.Add(FString::Printf(TEXT("Region %s: uncheck Is Spatially Loaded for the fixed-region runtime."), *Pair.Key.ToString()));
		for (TActorIterator<AEcoShelterAnchor> It(World); It; ++It) if (It->GetIsSpatiallyLoaded())
			Notes.Add(FString::Printf(TEXT("Shelter %s: uncheck Is Spatially Loaded to preserve reservation registration."), *It->GetName()));
	}
#endif
	Notes.Add(TEXT("This report does not trace ground or prove migration routes. Load terrain cells; runtime validates spawn ground before starting."));
	return Errors.IsEmpty();
}

void AEcoCreatureIntegrationSpawner::ValidateEditorSetup() const
{
	TArray<FString> Errors, Notes;
	CollectSetupIssues(Errors, Notes);
	for (const auto& Error : Errors) UE_LOG(LogTemp, Error, TEXT("[Eco Setup] %s"), *Error);
	for (const auto& Note : Notes) UE_LOG(LogTemp, Log, TEXT("[Eco Setup Note] %s"), *Note);
	UE_LOG(LogTemp, Log, TEXT("[Eco Setup] World=%s Coordinator=%s Errors=%d Notes=%d ReadOnly=1"),
		*GetNameSafe(GetWorld()), *GetName(), Errors.Num(), Notes.Num());
}

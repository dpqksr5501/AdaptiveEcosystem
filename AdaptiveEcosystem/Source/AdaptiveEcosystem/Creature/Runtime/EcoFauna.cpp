#include "Creature/Runtime/EcoFauna.h"

#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Creature/Representation/EcoForagePatchVisual.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityManager.h"
#include "MassEntityTemplateRegistry.h"
#include "MassMovementFragments.h"
#include "MassSpawnerSubsystem.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "World/EcoWorldClockSubsystem.h"
#include "World/EcoVegetationField.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"

namespace
{
    constexpr double FaunaBirthBufferSeconds = 5.;
    constexpr double FoodIntentLifetime = 2.;
    TAutoConsoleVariable<FString> CVarForageStockAudit(TEXT("eco.Fauna.ForageStockAudit"), TEXT(""),
        TEXT("Record growth and feed attempts for one authored plant patch."));

    TOptional<double> SampleForageSoil(const UEcoPolicyV3IntegratedSubsystem* Native, const FEcoFaunaHabitatPatch& Patch)
    {
        if (!Native || !Native->IsActive() || !Patch.IsPlantForage() || Patch.PlantMoistureNeed <= 0.f) return {};
        const auto* Context = Native->FindContext(Patch.RegionId);
        if (!Context || !Context->bSpatialFoodRegistered) return {};
        const auto& Grid = Context->Sim.Food;
        if (!Grid.Vegetation.bEnabled || !Grid.HasValidVegetationLayout()) return {};
        const auto Point = Context->CmToUnits(Patch.Center);
        const double Extent = Context->Sim.Config.WorldSize;
        if (Point.X < 0. || Point.Y < 0. || Point.X >= Extent || Point.Y >= Extent) return {};
        const auto Cell = Grid.CellOf(Point);
        if (!Grid.Habitats[Cell].bGroundUsable) return {};
        return Grid.VegetationCells[Cell].Moisture;
    }

    const AEcoVegetationHabitat* FindForageWater(UWorld& World, const FEcoFaunaHabitatPatch& Patch)
    {
        if (Patch.ForageWaterHabitatId.IsNone()) return nullptr;
        const AEcoVegetationHabitat* Source = nullptr;
        for (TActorIterator<AEcoVegetationHabitat> It(&World); It; ++It)
        {
            if (It->HabitatId != Patch.ForageWaterHabitatId || It->RegionId != Patch.RegionId) continue;
            if (Source || !It->bConnectedFreshWater || !It->IsValidHabitat() || !It->ContainsGround(Patch.Center))
                return nullptr;
            Source = *It;
        }
        return Source;
    }

    double AdvanceLocalForageSoil(UWorld& World, const FEcoFaunaHabitatPatch& Patch,
        const FRegionEnvironmentState& Weather, double Now, double Delta, double Stock, double Moisture)
    {
        const EcoVegetationV3::FConfig Config;
        EcoVegetationV3::FHabitat Habitat;
        if (const auto* Source = FindForageWater(World, Patch))
        {
            const double Rise = Patch.Center.Z - Source->EvaluateWaterLevelZ(Now, Weather.Rainfall);
            Habitat.Drainage = Source->Drainage;
            Habitat.Shade = Source->Shade;
            Habitat.WaterSupply = EcoVegetationV3::Unit(1. - FMath::Max(0., Rise) / Source->MaxSupplyRiseCm);
            Habitat.Flood = EcoVegetationV3::Unit(-Rise / 100.);
        }
        const double Light = Weather.DayPhase == EEcoDayPhase::Night ? 0.
            : Weather.DayPhase == EEcoDayPhase::Day ? 1. : .5;
        const EcoVegetationV3::FWeather SoilWeather{
            FMath::Clamp<double>(Weather.Rainfall, 0., 1.), Weather.Temperature, Light};
        return EcoVegetationV3::AdvanceMoisture(Config, SoilWeather, Habitat, Moisture,
            Stock / Patch.Capacity, 0., Delta);
    }
}

bool AEcoCreatureIntegrationSpawner::SubmitFaunaFoodIntent(int64 AgentId, EEcoFaunaFoodIntent Kind,
    int64 TargetAgentId, FName PatchId)
{
    if (!IsInGameThread() || !bAuthorityWorld || !bReady || GetNetMode() == NM_Client) return false;
    const auto* Agent = AgentLookup.Find(AgentId);
    const auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
    if (!Agent || !Clock || !Clock->IsClockRunning()) return false;
    const auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    if (!EM.IsEntityValid(*Agent) || !EM.GetFragmentDataPtr<FEcoFaunaFragment>(*Agent)
        || EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Agent).HP <= 0.f) return false;
    const FName Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(*Agent).CurrentRegionId;
    switch (Kind)
    {
    case EEcoFaunaFoodIntent::None:
        if (TargetAgentId != 0 || !PatchId.IsNone()) return false;
        FaunaFoodIntents.Remove(AgentId);
        return true;
    case EEcoFaunaFoodIntent::LivePrey:
        if (TargetAgentId == AgentId || !PatchId.IsNone() || !AgentLookup.Contains(TargetAgentId)) return false;
        break;
    case EEcoFaunaFoodIntent::Carcass:
        if (!PatchId.IsNone() || !FaunaCarcasses.Contains(TargetAgentId)) return false;
        break;
    case EEcoFaunaFoodIntent::HabitatPatch:
        if (TargetAgentId != 0 || PatchId.IsNone() || !FaunaHabitatPatches.ContainsByPredicate([&](const auto& Patch) {
            return Patch.Id == PatchId && Patch.RegionId == Region;
        })) return false;
        break;
    default:
        return false;
    }
    const double IssuedAt = Clock->GetServerTime().ServerTimeSeconds;
    FaunaFoodIntents.Add(AgentId, {Kind, Region, PatchId, TargetAgentId, IssuedAt});
    if (bAuditFaunaHunts)
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][FoodIntentAccepted] Agent=%lld Region=%s Kind=%d Target=%lld Patch=%s IssuedAt=%.9f"),
            AgentId, *Region.ToString(), int32(Kind), TargetAgentId, *PatchId.ToString(), IssuedAt);
    return true;
}

double AEcoCreatureIntegrationSpawner::RankFaunaFood(double Score, int64 AgentId, FName Region, double Now,
    EEcoFaunaFoodIntent Kind, int64 TargetAgentId, FName PatchId) const
{
    const auto* Intent = FaunaFoodIntents.Find(AgentId);
    if (!Intent || Intent->Region != Region || Now < Intent->IssuedAt || Now - Intent->IssuedAt >= FoodIntentLifetime
        || Intent->Kind != Kind || Intent->TargetAgentId != TargetAgentId || Intent->PatchId != PatchId) return Score;
    const double Ranked = Score * 1.75;
    if (bAuditFaunaHunts && Ranked > Score)
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][FoodIntentRanked] Agent=%lld Region=%s Kind=%d Target=%lld Patch=%s IssuedAt=%.9f At=%.9f BaseScore=%.9g RankedScore=%.9g"),
            AgentId, *Region.ToString(), int32(Kind), TargetAgentId, *PatchId.ToString(), Intent->IssuedAt, Now, Score, Ranked);
    return Ranked;
}

void UEcoFaunaTrait::BuildTemplate(FMassEntityTemplateBuildContext& Context, const UWorld& World) const
{
    Super::BuildTemplate(Context, World);
    Context.AddTag<FEcoIntegratedCreatureTag>();
    Context.AddFragment<FEcoCreaturePresentationFragment>();
    if (World.GetNetMode() == NM_Client && !Context.IsInspectingData()) return;
    Context.AddTag<FMassCustomMovementTag>();
    Context.AddFragment<FEcoCreatureLifecycleFragment>();
    Context.AddFragment<FEcoCreatureSurvivalFragment>();
    Context.AddFragment<FEcoCreatureFootstepFragment>();
    Context.AddFragment<FEcoFaunaFragment>();
}

bool UEcoPolicyV3IntegratedSubsystem::ConsumeFaunaFood(FName RegionId, const FVector& Position,
    double Requested, double NutritionHeadroom, double& OutNutrition)
{
    OutNutrition = 0.;
    auto* Context = FindContext(RegionId);
    auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    if (!IsActive() || !Context || !Context->bSpatialFoodRegistered || !Ecology) return false;
    const auto Point = Context->CmToUnits(Position);
    if (Point.X < 0. || Point.Y < 0. || Point.X > Context->Sim.Config.WorldSize || Point.Y > Context->Sim.Config.WorldSize)
        return true;
    auto& Grid = Context->Sim.Food;
    const auto Cell = Grid.CellOf(Point);
    const bool bNaturalVegetation = Grid.Vegetation.bHabitatDynamics && Grid.Habitats[Cell].bNatural;
    const double NutritionPerUnit = bNaturalVegetation ? Grid.VegetationCells[Cell].NutritionMultiplier() : 1.;
    const double Taken = FMath::Min3(Requested, Grid.Food[Cell], NutritionHeadroom / NutritionPerUnit);
    if (Taken < EcoFaunaNutrition::MinimumMeal) return true;
    const double Before = Grid.Total();
    const auto Sequence = Context->ResourceReceiptSequence + 1;
    if (!Ecology->CommitSpatialFood(RegionId, Sequence, Before, Taken, 0., Before - Taken, 0.)) return false;
    Context->ResourceReceiptSequence = Sequence;
    Grid.Food[Cell] -= Taken;
    Context->Sim.Stats.FoodEaten += Taken;
    OutNutrition = Taken * NutritionPerUnit;
    if (bNaturalVegetation)
    {
        Grid.VegetationCells[Cell].RecordBrowse(Taken, Grid.Cap[Cell]);
    }
    return true;
}

bool AEcoCreatureIntegrationSpawner::RegisterFaunaTemplate()
{
    if (FaunaSpecies.IsEmpty()) return true;
    const FName Name(TEXT("EcoFaunaConfig_v1"));
    FaunaConfig = FindObject<UMassEntityConfigAsset>(GetTransientPackage(), *Name.ToString());
    if (!FaunaConfig)
    {
        FaunaConfig = NewObject<UMassEntityConfigAsset>(GetTransientPackage(), Name, RF_Transient);
        auto* Trait = NewObject<UEcoFaunaTrait>(FaunaConfig, NAME_None, RF_Transient);
        FaunaConfig->GetMutableConfig().AddTrait(*Trait);
    }
    const auto& Template = FaunaConfig->GetOrCreateEntityTemplate(*GetWorld());
    if (!Template.IsValid()) return false;
    const auto& Composition = Template.GetCompositionDescriptor();
    const bool bValid = Composition.Contains<FEcoFaunaFragment>() == (GetNetMode() != NM_Client)
        && !Composition.Contains<FEcoPolicyRuntimeFragment>()
        && !Composition.Contains<FEcoPolicyOutputFragment>()
        && !Composition.Contains<FEcoHerbivoreTag>()
        && !Composition.Contains<FEcoPredatorTag>()
        && !Composition.Contains<FEcoStateTreeBehaviorTag>()
        && !Composition.Contains<FEcoGroundedNavigationTag>()
        && !Composition.Contains<FEcoIntegratedV3Fragment>()
        && !Composition.Contains<FEcoIntegratedPolicyV3Tag>()
        && !Composition.Contains<FEcoIntegratedThreatV3Tag>();
    if (!bValid)
        UE_LOG(LogTemp, Error, TEXT("[Eco Setup] Invalid fauna template: expected one rule-fauna writer on authority and presentation only on clients."));
    return bValid;
}

const FEcoFaunaSpecies* AEcoCreatureIntegrationSpawner::FindFauna(FName SpeciesId) const
{
    return FaunaSpecies.FindByPredicate([SpeciesId](const auto& Species) { return Species.SpeciesId == SpeciesId; });
}

bool AEcoCreatureIntegrationSpawner::ValidateFauna(TArray<FString>& Errors) const
{
    const int32 Before = Errors.Num();
    if (!FaunaSpecies.IsEmpty() && (!bUseV3Policy || !bEnableEcosystemLife || bEnableWaves || Migration.bEnabled))
        Errors.Add(TEXT("Ground fauna requires the opt-in Native v3 life map with legacy waves and migration disabled."));
    TSet<FName> Ids;
    for (const auto& Species : FaunaSpecies)
    {
        const auto* Visual = Species.VisualClass.GetDefaultObject();
        const auto Positive = [](float Value) { return FMath::IsFinite(Value) && Value > 0.f; };
        const auto NonNegative = [](float Value) { return FMath::IsFinite(Value) && Value >= 0.f; };
        if (Species.HeatResponseC.ContainsNaN() || (Species.HeatResponseC != FVector2D::ZeroVector
            && (Species.HeatResponseC.Y <= Species.HeatResponseC.X || Species.Locomotion != EEcoFaunaLocomotion::Ground)))
            Errors.Add(FString::Printf(TEXT("Invalid ground heat response for %s"), *Species.SpeciesId.ToString()));
        for (const auto& Preference : Species.PlantPreferences)
            if (!Species.UsesPlantFood() || Preference.Key == EEcoFaunaPlantGuild::Unspecified
                || !Positive(Preference.Value) || Preference.Value > 3.f)
                Errors.Add(FString::Printf(TEXT("Invalid forage preference for %s"), *Species.SpeciesId.ToString()));
        if (Species.SpeciesId.IsNone() || Ids.Contains(Species.SpeciesId)
            || Species.SpeciesId == TEXT("Herbivore") || Species.SpeciesId == TEXT("Wolf")
            || !Visual || Visual->VisualSpeciesId != Species.SpeciesId || !Visual->VisualMesh
            || !Visual->AnimationProfile || !Visual->AnimationProfile->IsValidProfile() || !Visual->BehaviorAnimationClass
            || !Positive(Species.WalkSpeed) || !Positive(Species.RunSpeed) || Species.RunSpeed < Species.WalkSpeed
            || !Positive(Species.BodyRadius) || Species.BodyRadius < 1.f || Species.BodyRadius > 100.f
            || !Positive(Species.EyeHeight) || !Positive(Species.SweepHeight) || !NonNegative(Species.StepHeight)
            || !NonNegative(Species.WadeDepth) || !NonNegative(Species.SprintDrain) || !Positive(Species.FatigueRecovery)
            || !NonNegative(Species.Maintenance) || !Positive(Species.AttackWindup) || !NonNegative(Species.AttackRecovery)
            || !Positive(Species.RestingMaintenanceFraction) || Species.RestingMaintenanceFraction < .1f
            || Species.RestingMaintenanceFraction > 1.f
            || !NonNegative(Species.ScentRange) || Species.ScentRange > 1200.f
            || !NonNegative(Species.DefenseDamage) || Species.DefenseDamage > 100.f
            || !NonNegative(Species.OffspringGuardRange) || (Species.OffspringGuardRange > 0.f && Species.DefenseDamage <= 0.f)
            || !NonNegative(Species.DayActivity) || Species.DayActivity > 1.f || !NonNegative(Species.NightActivity)
            || Species.NightActivity > 1.f || !Positive(Species.NightVision) || Species.NightVision > 1.f
            || !Positive(Species.Gestation) || !Positive(Species.BirthRecovery)
            || !Positive(Species.DeathSettleSeconds) || !Positive(Species.CarrionLifetime)
            || !NonNegative(Species.AdultCarrionEnergy) || Species.FeedingPlaces < 1 || Species.FeedingPlaces > 8
            || !Positive(Species.MaturitySeconds) || !Positive(Species.FoodPerMeal)
            || !Positive(Species.SightRange) || !Positive(Species.AdultMass) || !Positive(Species.AttackReach)
            || !Positive(Species.SightHalfAngle) || Species.SightHalfAngle > 180.f || !Positive(Species.GroundAcceleration)
            || !Positive(Species.MinGroundNormalZ) || Species.MinGroundNormalZ < .65f || Species.MinGroundNormalZ > 1.f
            || !NonNegative(Species.GroundTurnDegreesPerSecond)
            || !NonNegative(Species.SwimDepthFraction) || Species.SwimDepthFraction > 1.f
            || !NonNegative(Species.SpawningTemperatureC.X) || !NonNegative(Species.SpawningTemperatureC.Y)
            || Species.SpawningTemperatureC.Y > 40. || Species.SpawningTemperatureC.X > Species.SpawningTemperatureC.Y
            || !NonNegative(Species.MaxNurseryCurrent)
            || !NonNegative(Species.StalkRange) || !NonNegative(Species.CaregiverFollowRange) || !NonNegative(Species.RootingSeconds)
            || !NonNegative(Species.HabitatCarrionRange)
            || !NonNegative(Species.CarrionEnergyPerMeal)
            || !NonNegative(Species.CarrionHungerFraction) || Species.CarrionHungerFraction > .9f
            || !NonNegative(Species.MealStartFraction) || !Positive(Species.MealStopFraction)
            || Species.MealStopFraction > 1.f || Species.MealStopFraction <= FMath::Max(.25f, Species.MealStart())
            || !NonNegative(Species.PostMealRestSeconds) || !Positive(Species.PursuitLimitSeconds) || !Positive(Species.ThreatSenseRange)
            || !Positive(Species.ThreatSightHalfAngle) || Species.ThreatSightHalfAngle > 180.f
            || !NonNegative(Species.ThreatNearAwarenessRange)
            || !Positive(Species.RoutineHomeRadius)
            || !NonNegative(Species.SocialNeighborRadius) || !Positive(Species.SocialSpacing)
            || !NonNegative(Species.AdultMaleSocialAffinity) || Species.AdultMaleSocialAffinity > 1.f
            || (Species.Diet == EEcoFaunaDiet::Herbivore && (!Species.PreyRules.IsEmpty() || Species.CarrionEnergyPerMeal > 0.f))
            || (Species.Diet == EEcoFaunaDiet::Carnivore && !Species.IsAquatic()
                && Species.PreyRules.IsEmpty() && Species.CarrionEnergyPerMeal <= 0.f)
            || (Species.Locomotion == EEcoFaunaLocomotion::Flight && (!Positive(Species.FlightSpeed)
                || !Positive(Species.FlightCruiseHeight) || !Positive(Species.FlightCeiling)
                || Species.FlightCruiseHeight > Species.FlightCeiling || Visual->AnimationProfile->Poses.Num() != 12))
            || (Species.bCanDiveHunt && (Species.Locomotion != EEcoFaunaLocomotion::Flight || Species.PreyRules.IsEmpty()))
            || !NonNegative(Species.NestlingSeconds) || Species.NestlingSeconds > Species.MaturitySeconds
            || (Species.NestlingSeconds > 0.f && Species.Locomotion != EEcoFaunaLocomotion::Flight)
            || Species.RegionalLimit < 2)
        {
            Errors.Add(FString::Printf(TEXT("Invalid fauna species profile: %s"), *Species.SpeciesId.ToString()));
        }
        Ids.Add(Species.SpeciesId);
    }
    for (const auto& Species : FaunaSpecies)
    {
        TSet<FName> PreyIds;
        for (const auto& Rule : Species.PreyRules)
        {
            if (Rule.SpeciesId == Species.SpeciesId || !Ids.Contains(Rule.SpeciesId) || PreyIds.Contains(Rule.SpeciesId)
                || !FMath::IsFinite(Rule.Preference) || Rule.Preference <= 0.f
                || !FMath::IsFinite(Rule.MaxPursuitStart) || Rule.MaxPursuitStart < 0.f
                || !FMath::IsFinite(Rule.MaxPreyMassRatio) || Rule.MaxPreyMassRatio <= 0.f
                || !FMath::IsFinite(Rule.MaxHealthyMaturity) || !FMath::IsFinite(Rule.MaxInjuredMaturity)
                || !FMath::IsFinite(Rule.GuardRadius) || Rule.GuardRadius < 0.f
                || Rule.MaxHealthyMaturity < 0.f || Rule.MaxInjuredMaturity > 1.f || Rule.MaxInjuredMaturity < Rule.MaxHealthyMaturity)
                Errors.Add(FString::Printf(TEXT("Invalid fauna prey relationship: %s -> %s"),
                    *Species.SpeciesId.ToString(), *Rule.SpeciesId.ToString()));
            PreyIds.Add(Rule.SpeciesId);
        }
    }
    for (const auto& Group : Groups)
    {
        TSet<FName> Placements;
        for (const auto& Placement : Group.Fauna)
        {
            const auto* Species = FindFauna(Placement.SpeciesId);
            if (!Species || Placements.Contains(Placement.SpeciesId) || Placement.SpawnPoints.Num() > Species->RegionalLimit
                || Placement.SpawnPoints.ContainsByPredicate([](const FVector& Point) { return Point.ContainsNaN(); })
                || (!Placement.HabitatSpawnPoints.IsEmpty()
                    && (Placement.HabitatSpawnPoints.Num() != Placement.SpawnPoints.Num() || Placement.HabitatSpawnStage < 1
                        || Placement.HabitatSpawnStage > 3
                        || Placement.HabitatSpawnPoints.ContainsByPredicate([](const FVector& Point) { return Point.ContainsNaN(); }))))
            {
                Errors.Add(FString::Printf(TEXT("Invalid fauna placement: %s / %s"),
                    *Group.RegionId.ToString(), *Placement.SpeciesId.ToString()));
            }
            Placements.Add(Placement.SpeciesId);
        }
    }
    TSet<FName> NestIds;
    for (const auto& Perch : FaunaPerches)
    {
        const auto* Species = FindFauna(Perch.SpeciesId);
        if (!Species || Species->Locomotion != EEcoFaunaLocomotion::Flight
            || Perch.RegionId.IsNone() || Perch.Location.ContainsNaN()
            || (!Perch.NestId.IsNone() && (Species->NestlingSeconds <= 0.f || NestIds.Contains(Perch.NestId))))
            Errors.Add(FString::Printf(TEXT("Invalid fauna perch: %s / %s"),
                *Perch.RegionId.ToString(), *Perch.SpeciesId.ToString()));
        if (!Perch.NestId.IsNone()) NestIds.Add(Perch.NestId);
    }
    return Errors.Num() == Before;
}

bool AEcoCreatureIntegrationSpawner::BuildFaunaPositions(FName RegionId,
    const FEcoFaunaPlacement& Placement, TArray<FVector>& Out) const
{
    Out.Reset();
    const auto& Sites = FaunaHabitatStage >= Placement.HabitatSpawnStage && !Placement.HabitatSpawnPoints.IsEmpty()
        ? Placement.HabitatSpawnPoints : Placement.SpawnPoints;
    const auto* Species = FindFauna(Placement.SpeciesId);
    for (const auto& Point : Sites)
    {
        if (Species && Species->IsAquatic())
        {
            const double Clearance = FMath::Max(1., Species->BodyRadius * .65);
            EcoCreatureMovement::FFaunaWaterColumn Water;
            if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), RegionId, Point, Clearance, Water)) return false;
            const FVector Position(Point.X, Point.Y, Water.DepthHeight(Species->SwimDepthFraction, Clearance));
            const auto* Region = FindRegion(Position);
            if (!Region || Region->RegionId != RegionId) return false;
            Out.Add(Position);
            continue;
        }
        FVector Ground;
        if (!EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Point, Ground)) return false;
        const auto* Region = FindRegion(Ground);
        if (!Region || Region->RegionId != RegionId || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Ground, 0.f))
            return false;
        Out.Add(Ground);
    }
    return true;
}

bool AEcoCreatureIntegrationSpawner::InitializeFaunaHabitat()
{
    if (FaunaHabitatStage < 0 || FaunaHabitatStage > 3 || FaunaHabitatPatches.Num() > 64
        || (!FaunaSpecies.IsEmpty() && !FaunaPersistence.IsValid())) return false;
    FaunaPatchStock.Init(0.f, FaunaHabitatPatches.Num());
    FaunaLocalSoilMoisture.Reset();
    if (FaunaCoolingSites.Num() > 32) return false;
    TSet<FName> CoolingIds;
    for (auto& Site : FaunaCoolingSites)
    {
        FVector Ground;
        const auto* Species = FindFauna(Site.SpeciesId);
        if (Site.Id.IsNone() || CoolingIds.Contains(Site.Id) || !Species || Species->HeatResponseC == FVector2D::ZeroVector
            || Site.Center.ContainsNaN() || !FMath::IsFinite(Site.Radius) || Site.Radius <= 0.f
            || !(Site.DryRelief >= 0.f && Site.DryRelief <= Site.WetRelief && Site.WetRelief <= 1.f)
            || !EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Site.Center, Ground)
            || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Ground, Species->WadeDepth))
        {
            UE_LOG(LogTemp, Error, TEXT("[Eco Fauna] Invalid cooling site %s"), *Site.Id.ToString());
            return false;
        }
        const auto* Region = FindRegion(Ground);
        if (!Region || Region->RegionId != Site.RegionId) return false;
        Site.Center = Ground;
        CoolingIds.Add(Site.Id);
    }
    TSet<FName> Ids;
    for (int32 Index = 0; Index < FaunaHabitatPatches.Num(); ++Index)
    {
        auto& Patch = FaunaHabitatPatches[Index];
        if (Patch.Stage > FaunaHabitatStage) continue;
        const bool bSeasonal = Patch.SeasonalFullGrowthDepthCm > 0.f;
        bool bInitiallyExposed = false;
        FVector Ground = Patch.Center;
        const auto ResolveGround = [&]()
        {
            if (Patch.ShelterApproachPoints.IsEmpty())
                return EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Patch.Center, Ground);
            // Covered refuges author their floor height. A top-down spawn projection hits the roof.
            const auto* ShelterSpecies = FindFauna(Patch.ShelteredSpecies);
            FHitResult Floor;
            const FVector Hint = Patch.Center;
            if (!ShelterSpecies || !GetWorld()->LineTraceSingleByObjectType(Floor, Hint + FVector(0., 0., 1.),
                    Hint - FVector(0., 0., ShelterSpecies->StepHeight + 1.), FCollisionObjectQueryParams(ECC_WorldStatic),
                    FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaShelterFloor)))
                || Floor.ImpactNormal.Z < ShelterSpecies->MinGroundNormalZ
                || EcoCreatureMovement::CrossesExcludedArea(*GetWorld(), Floor.ImpactPoint, Floor.ImpactPoint)) return false;
            Ground = Floor.ImpactPoint;
            return true;
        };
        if (Patch.Id.IsNone() || Ids.Contains(Patch.Id) || Patch.Stage < 1 || Patch.Center.ContainsNaN()
            || !FMath::IsFinite(Patch.Capacity) || Patch.Capacity <= 0.f
            || !FMath::IsFinite(Patch.RegrowthPerSecond) || Patch.RegrowthPerSecond < 0.f
            || (Patch.bTrackLocalSoilMoisture && (!Patch.IsPlantForage() || Patch.PlantMoistureNeed <= 0.f))
            || (!Patch.bTrackLocalSoilMoisture && !Patch.ForageWaterHabitatId.IsNone())
            || (Patch.IsPlantForage() && (Patch.bSubmerged || Patch.PlantGrowthTemperature.ContainsNaN()
                || !(Patch.PlantGrowthTemperature.X < Patch.PlantGrowthTemperature.Y && Patch.PlantGrowthTemperature.Y < Patch.PlantGrowthTemperature.Z)
                || Patch.PlantGrowthRainfall.ContainsNaN() || Patch.PlantGrowthRainfall.X < 0. || Patch.PlantGrowthRainfall.Y < 0.
                || !FMath::IsFinite(Patch.PlantMoistureNeed) || Patch.PlantMoistureNeed < 0.f || Patch.PlantMoistureNeed > 1.f
                || !FMath::IsFinite(Patch.PlantDryLossPerSecond) || Patch.PlantDryLossPerSecond < 0.f
                || (Patch.PlantDryLossPerSecond > 0.f && Patch.PlantMoistureNeed <= 0.f)
                || Patch.Consumers.ContainsByPredicate([this](FName Kind) { const auto* Profile = FindFauna(Kind); return !Profile || !Profile->UsesPlantFood(); })))
            || !FMath::IsFinite(Patch.SeasonalFullGrowthDepthCm) || Patch.SeasonalFullGrowthDepthCm < 0.f
            || !FMath::IsFinite(Patch.SeasonalDryLossPerSecond) || Patch.SeasonalDryLossPerSecond < 0.f
            || (bSeasonal && !Patch.bSubmerged) || (!bSeasonal && Patch.SeasonalDryLossPerSecond > 0.f)
            || !FMath::IsFinite(Patch.EnergyPerMeal) || Patch.EnergyPerMeal <= 0.f
            || !FMath::IsFinite(Patch.ShelterRadius) || Patch.ShelterRadius < 0.f
            || !FMath::IsFinite(Patch.EntranceRadius) || Patch.EntranceRadius < 0.f
            || (Patch.bAquaticNursery && !Patch.bSubmerged)
            || (Patch.ShelterRadius > 0.f && (!FindFauna(Patch.ShelteredSpecies) || Patch.EntranceRadius <= 0.f))
            || Patch.Consumers.IsEmpty() || Patch.Consumers.ContainsByPredicate([this](FName Species) { return !FindFauna(Species); })
            || (!Patch.bSubmerged && (!ResolveGround()
                || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Ground, 0.f))))
        {
            UE_LOG(LogTemp, Error, TEXT("[Eco Fauna] Invalid habitat patch %s"), *Patch.Id.ToString());
            return false;
        }
        if (Patch.bSubmerged)
        {
            EcoCreatureMovement::FFaunaWaterColumn Water;
            const bool bHasColumn = bSeasonal
                ? EcoCreatureMovement::ProbeFaunaWaterColumn(*GetWorld(), Patch.RegionId, Ground, Water)
                : EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Patch.RegionId, Ground, 1., Water);
            if (Patch.ShelterRadius > 0.f || !bHasColumn || Ground.Z <= Water.Bottom
                || (!bSeasonal && Ground.Z >= Water.Surface)
                || Patch.Consumers.ContainsByPredicate([this](FName Kind) { return !FindFauna(Kind)->CanSwim(); }))
                return false;
            bInitiallyExposed = bSeasonal && Ground.Z >= Water.Surface;
        }
        if (Patch.bHasShoreEntry)
        {
            FVector Shore;
            EcoCreatureMovement::FFaunaWaterColumn Water;
            if (!Patch.bSubmerged || !EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Patch.ShorePoint, Shore, true)
                || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Shore, 0.)
                || !EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Patch.RegionId, Patch.WaterEntryPoint, 4., Water))
            {
                UE_LOG(LogTemp, Error, TEXT("[Eco Fauna] Patch %s requires a dry landing and a usable water entry"), *Patch.Id.ToString());
                return false;
            }
            const double Span = FVector::Dist(Shore, Patch.WaterEntryPoint);
            if (Span > 130.)
            {
                UE_LOG(LogTemp, Error, TEXT("[Eco Fauna] Patch %s entry is %.1f cm from projected landing (maximum 130 cm)"),
                    *Patch.Id.ToString(), Span);
                return false;
            }
            Patch.ShorePoint = Shore;
        }
        const auto* Region = FindRegion(Ground);
        if (!Region || Region->RegionId != Patch.RegionId) return false;
        Patch.Center = Ground;
        if (Patch.bTrackLocalSoilMoisture)
        {
            if (!Patch.ForageWaterHabitatId.IsNone() && !FindForageWater(*GetWorld(), Patch))
            {
                UE_LOG(LogTemp, Error, TEXT("[Eco Fauna] Patch %s has no unique connected forage water habitat at its center"),
                    *Patch.Id.ToString());
                return false;
            }
            FaunaLocalSoilMoisture.Add(Patch.Id, EcoVegetationV3::FCell{}.Moisture);
        }
        if (Patch.ForageAccessPoints.Num() > 8
            || (!Patch.ForageAccessPoints.IsEmpty() && (Patch.ShelterRadius > 0.f
                || (Patch.bSubmerged ? Patch.bHasShoreEntry : !Patch.IsPlantForage())))) return false;
        if (Patch.ShelterApproachPoints.Num() > 4 || (!Patch.ShelterApproachPoints.IsEmpty()
            && (Patch.bSubmerged || !Patch.ForageAccessPoints.IsEmpty()
                || Patch.ShelterRadius <= 0.f || !FindFauna(Patch.ShelteredSpecies)))) return false;
        for (auto& Point : Patch.ShelterApproachPoints)
        {
            FVector Projected;
            if (Point.ContainsNaN() || !EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Point, Projected)
                || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Projected, 0.f)
                || FindRegion(Projected) != Region
                || FVector::DistSquared2D(Projected, Patch.Center) <= FMath::Square(Patch.ShelterRadius)) return false;
            Point = Projected;
        }
        for (int32 PointIndex = 0; PointIndex < Patch.ForageAccessPoints.Num(); ++PointIndex)
        {
            auto& Point = Patch.ForageAccessPoints[PointIndex];
            if (Point.ContainsNaN()) return false;
            FVector Resolved = Point;
            if (Patch.bSubmerged)
            {
                EcoCreatureMovement::FFaunaWaterColumn Water;
                if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Patch.RegionId, Point, 1., Water)
                    || Point.Z <= Water.Bottom || Point.Z >= Water.Surface) return false;
            }
            else if (!EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Point, Resolved)
                || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Resolved, 0.f)) return false;
            if (FindRegion(Resolved) != Region) return false;
            for (int32 Prior = 0; Prior <= PointIndex; ++Prior)
                if (FVector::DistSquared(Resolved, Patch.ForagePoint(Prior)) <= FMath::Square(70.)) return false;
            Point = Resolved;
        }
        Ids.Add(Patch.Id);
        FaunaPatchStock[Index] = bInitiallyExposed ? 0.f : Patch.Capacity;
    }
    FaunaForageVisuals.Reset();
    const auto SupportsForageVisual = [this](const FEcoFaunaHabitatPatch& Patch)
    {
        return Patch.Stage <= FaunaHabitatStage && (Patch.IsPlantForage() || Patch.SeasonalFullGrowthDepthCm > 0.f);
    };
    if (FaunaHabitatPatches.ContainsByPredicate(SupportsForageVisual))
    {
        FaunaForageVisuals.SetNum(FaunaHabitatPatches.Num());
        for (TActorIterator<AEcoForagePatchVisual> It(GetWorld()); It; ++It)
        {
            const int32 Index = FaunaHabitatPatches.IndexOfByPredicate([&](const FEcoFaunaHabitatPatch& Patch)
                { return SupportsForageVisual(Patch) && Patch.Id == It->PatchId; });
            if (Index == INDEX_NONE || FaunaForageVisuals[Index].IsValid())
            {
                UE_LOG(LogTemp, Warning, TEXT("[Eco Fauna] Unmatched or duplicate forage visual %s"), *It->GetName());
                continue;
            }
            FaunaForageVisuals[Index] = *It;
        }
        PublishForageVisuals();
    }
    if (!FaunaHabitatPatches.IsEmpty())
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][HabitatReady] Stage=%d ActivePatches=%d"), FaunaHabitatStage, Ids.Num());
    return true;
}

const FEcoFaunaHabitatPatch* AEcoCreatureIntegrationSpawner::FindFaunaShelter(FName Region, FName Species,
    const FVector& Position, double Range, float ApproachEyeHeight) const
{
    const FEcoFaunaHabitatPatch* Best = nullptr;
    double BestDistance = FMath::Square(Range);
    for (const auto& Patch : FaunaHabitatPatches)
    {
        if (Patch.Stage > FaunaHabitatStage || Patch.RegionId != Region || Patch.ShelteredSpecies != Species
            || Patch.ShelterRadius <= 0.f) continue;
        if (Range <= 0.)
        {
            if (Patch.Shelters(Species, Position)) return &Patch;
            continue;
        }
        const double Distance = FVector::DistSquared(Position, Patch.Center);
        if (Distance < BestDistance)
        {
            if (ApproachEyeHeight > 0.f
                && GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, ApproachEyeHeight),
                    Patch.Center + FVector(0, 0, 5.), FCollisionObjectQueryParams(ECC_WorldStatic),
                    FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaShelterApproach)))) continue;
            Best = &Patch;
            BestDistance = Distance;
        }
    }
    return Best;
}

int32 AEcoCreatureIntegrationSpawner::CountFauna(FName RegionId, FName SpeciesId) const
{
    if (FaunaSpecies.IsEmpty()) return 0;
    const auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    int32 Count = 0;
    for (const auto Entity : Owned)
    {
        if (EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity)
            && EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP > 0
            && EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity).CurrentRegionId == RegionId
            && (SpeciesId.IsNone() || EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).SpeciesId == SpeciesId))
            ++Count;
    }
    return Count;
}

FIntPoint AEcoCreatureIntegrationSpawner::CountFaunaDiets(FName RegionId) const
{
    FIntPoint Counts(0, 0);
    for (const auto& Species : FaunaSpecies)
    {
        const int32 Count = CountFauna(RegionId, Species.SpeciesId);
        if (Species.UsesPlantFood()) Counts.X += Count;
        else Counts.Y += Count;
    }
    return Counts;
}

int32 AEcoCreatureIntegrationSpawner::SpawnFauna(FName RegionId, const FEcoFaunaSpecies& Species,
    const TArray<FVector>& Positions, const FEcoServerTimeSnapshot& Time)
{
    if (!bAuthorityWorld || !FaunaConfig || Positions.IsEmpty()) return 0;
    auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>();
    const int32 SpeciesIndex = Ecology->RegisterSpecies(Species.SpeciesId);
    const uint64 FounderSeed = uint64(101) ^ uint64(FEcoV3IntegratedSettings::FromConsole().Seed)
        ^ uint64(FEcoV3IntegratedSettings{}.Seed);
    auto& EM = Spawner->GetEntityManagerChecked();
    TArray<FMassEntityHandle> Entities;
    auto Creation = Spawner->SpawnEntities(FaunaConfig->GetOrCreateEntityTemplate(*GetWorld()), Positions.Num(), Entities);
    for (int32 Index = 0; Index < Entities.Num(); ++Index)
    {
        const auto Entity = Entities[Index];
        auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
        Id.StableAgentId = Ecology->AllocateStableAgentId();
        Id.SpeciesId = Species.SpeciesId;
        Id.SpeciesRuntimeIndex = SpeciesIndex;
        auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
        Region.CurrentRegionId = RegionId;
        Region.CurrentRegionIndex = Ecology->GetRegionRuntimeIndex(RegionId);
        auto& Runtime = EM.GetFragmentDataChecked<FEcoVitalsRuntimeFragment>(Entity);
        Runtime.WorldEpoch = Time.WorldEpoch;
        Runtime.LastTime = Time.ServerTimeSeconds;
        Runtime.LastStepId = Step;
        auto& Lifetime = EM.GetFragmentDataChecked<FEcoLifetimeFragment>(Entity);
        Lifetime.SpawnTimeSeconds = Time.ServerTimeSeconds;
        Lifetime.NextFeedTimeSeconds = Time.ServerTimeSeconds + 1.;
        auto& SurvivalProfile = EM.GetFragmentDataChecked<FEcoCreatureSurvivalFragment>(Entity);
        SurvivalProfile.EnergyPerPredation = 55.f;
        auto& Survival = SurvivalProfile.Settings;
        Survival.bEnabled = true;
        Survival.BaseMetabolism = Species.Maintenance;
        Survival.StarvationGraceSeconds = StarvationGraceSeconds;
        Survival.StarvationDamagePerSecond = StarvationDamagePerSecond;
        Survival.DeadRetentionSeconds = Species.DeathSettleSeconds + Species.CarrionLifetime + 2.;
        auto& Fauna = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entity);
        Fauna.Home = Fauna.Goal = Positions[Index];
        auto& Life = Fauna.Life;
        Life.bInitialized = Life.bNaturalPopulation = true;
        Life.Genome = Species.bIndividualResponse ? EcoLifeV3::NaturalFounder(FounderSeed, Id.StableAgentId, .07)
            : EcoLifeV3::Founder(FounderSeed, Id.StableAgentId);
        Fauna.NextDecision = Time.ServerTimeSeconds + 2. * EcoLifeV3::Unit(EcoLifeV3::Mix(uint64(Id.StableAgentId)));
        Fauna.NextThreatSense = Time.ServerTimeSeconds + .45 * EcoLifeV3::Unit(EcoLifeV3::Mix(uint64(Id.StableAgentId) + 1));
        Life.MaturitySeconds = Species.MaturitySeconds;
        Life.Born = Time.ServerTimeSeconds - Species.MaturitySeconds;
        Life.Sex = Index % 2 ? EcoLifeV3::ESex::Male : EcoLifeV3::ESex::Female;
        Life.NextBirth = Time.ServerTimeSeconds + 15.;
        EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform() = FTransform(Positions[Index]);
        Owned.Add(Entity);
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Spawn] Id=%lld Species=%s Region=%s"),
            Id.StableAgentId, *Species.SpeciesId.ToString(), *RegionId.ToString());
    }
    Creation.Reset();
    SuccessfulBirths += Entities.Num();
    SpeciesTotals.FindOrAdd(RegionId).FindOrAdd(Species.SpeciesId).Births += Entities.Num();
    return Entities.Num();
}

bool AEcoCreatureIntegrationSpawner::InspectFaunaHabitatStock(FName PatchId, float& Stock) const
{
    Stock = 0.f;
    if (!bAuthorityWorld || !bReady || PatchId.IsNone()) return false;
    const int32 Index = FaunaHabitatPatches.IndexOfByPredicate([&](const auto& Patch) {
        return Patch.Id == PatchId && Patch.Stage <= FaunaHabitatStage;
    });
    if (!FaunaPatchStock.IsValidIndex(Index)) return false;
    Stock = FaunaPatchStock[Index];
    return true;
}

bool AEcoCreatureIntegrationSpawner::InspectFaunaForageSoilMoisture(FName PatchId, double& Moisture) const
{
    Moisture = 0.;
    if (!bAuthorityWorld || !bReady || PatchId.IsNone()) return false;
    const auto* Patch = FaunaHabitatPatches.FindByPredicate([&](const auto& Candidate) {
        return Candidate.Id == PatchId && Candidate.Stage <= FaunaHabitatStage;
    });
    if (!Patch) return false;
    if (bUseNativeSoilForFaunaForage)
    {
        if (const auto Soil = SampleForageSoil(GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>(), *Patch); Soil.IsSet())
        {
            Moisture = Soil.GetValue();
            return true;
        }
    }
    if (const double* LocalSoil = FaunaLocalSoilMoisture.Find(PatchId))
    {
        Moisture = *LocalSoil;
        return true;
    }
    return false;
}

void AEcoCreatureIntegrationSpawner::UpdateFaunaHabitatStock(double Now)
{
    const double PatchDelta = FMath::Max(0., Now - LastFaunaPatchUpdate);
    LastFaunaPatchUpdate = Now;
    const auto* Native = bUseNativeSoilForFaunaForage ? GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
    const FName AuditPatch(*CVarForageStockAudit.GetValueOnGameThread());
    for (int32 Index = 0; Index < FaunaPatchStock.Num(); ++Index)
    {
        const auto& Patch = FaunaHabitatPatches[Index];
        if (Patch.Stage > FaunaHabitatStage) continue;
        auto& Stock = FaunaPatchStock[Index];
        FRegionEnvironmentState Weather;
        GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->GetEnvironmentState(Patch.RegionId, Weather);
        if (Patch.SeasonalFullGrowthDepthCm > 0.f)
        {
            EcoCreatureMovement::FFaunaWaterColumn Water;
            if (!EcoCreatureMovement::ProbeFaunaWaterColumn(*GetWorld(), Patch.RegionId, Patch.Center, Water, Now, Weather.Rainfall)) continue;
            const double Inundation = Water.Surface - Patch.Center.Z;
            const double Rate = Inundation > 0. && Patch.Center.Z > Water.Bottom
                ? Patch.RegrowthPerSecond * FMath::Clamp(Inundation / Patch.SeasonalFullGrowthDepthCm, 0., 1.)
                : -Patch.SeasonalDryLossPerSecond;
            const float Previous = Stock;
            Stock = FMath::Clamp(Stock + float(PatchDelta * Rate), 0.f, Patch.Capacity);
            if (!AuditPatch.IsNone() && Patch.Id == AuditPatch)
            {
                UE_LOG(LogTemp, Log, TEXT("[Eco Water Stock] Patch=%s At=%.17g Delta=%.17g Rain=%.9g Before=%.9g After=%.9g Capacity=%.9g Regen=%.9g Depth=%.17g Height=%.17g FullGrowthDepth=%.9g DryLoss=%.9g"),
                    *Patch.Id.ToString(), Now, PatchDelta, double(Weather.Rainfall), double(Previous), double(Stock),
                    double(Patch.Capacity), double(Patch.RegrowthPerSecond), Water.Surface - Water.Bottom,
                    Patch.Center.Z - Water.Bottom, double(Patch.SeasonalFullGrowthDepthCm), double(Patch.SeasonalDryLossPerSecond));
            }
            continue;
        }
        if (Patch.IsPlantForage())
        {
            auto Soil = SampleForageSoil(Native, Patch);
            if (double* LocalSoil = FaunaLocalSoilMoisture.Find(Patch.Id))
            {
                *LocalSoil = Soil.IsSet() ? Soil.GetValue()
                    : AdvanceLocalForageSoil(*GetWorld(), Patch, Weather, Now, PatchDelta, Stock, *LocalSoil);
                Soil = *LocalSoil;
            }
            const double Stress = Soil.IsSet() ? Patch.PlantDryStressFromMoisture(Soil.GetValue())
                : Patch.PlantDryStress(Weather.Rainfall, Weather.Humidity);
            const double Growth = Patch.PlantRecoveryMultiplier(Weather.Temperature, Weather.Rainfall) * FMath::Square(1. - Stress);
            const double Loss = Patch.PlantDryLossPerSecond * Stress * Stock / Patch.Capacity;
            const double Rate = Patch.RegrowthPerSecond * Growth - Loss;
            const float Previous = Stock;
            Stock = FMath::Clamp(Stock + float(PatchDelta * Rate), 0.f, Patch.Capacity);
            if (!AuditPatch.IsNone() && Patch.Id == AuditPatch)
            {
                UE_LOG(LogTemp, Log, TEXT("[Eco Forage Stock] Patch=%s At=%.17g Delta=%.17g T=%.17g Rain=%.17g Humidity=%.17g Soil=%.17g Before=%.17g After=%.17g Capacity=%.17g Regen=%.17g DryLoss=%.17g Need=%.17g Portion=%.17g Cold=%.17g Optimum=%.17g Hot=%.17g DryRain=%.17g WetRain=%.17g"),
                    *Patch.Id.ToString(), Now, PatchDelta, double(Weather.Temperature), double(Weather.Rainfall), double(Weather.Humidity),
                    Soil.Get(-1.), double(Previous), double(Stock), double(Patch.Capacity), double(Patch.RegrowthPerSecond),
                    double(Patch.PlantDryLossPerSecond), double(Patch.PlantMoistureNeed), double(Patch.EnergyPerMeal),
                    Patch.PlantGrowthTemperature.X, Patch.PlantGrowthTemperature.Y, Patch.PlantGrowthTemperature.Z,
                    Patch.PlantGrowthRainfall.X, Patch.PlantGrowthRainfall.Y);
            }
            continue;
        }
        const float Growth = FMath::Lerp(.75f, 1.25f, FMath::Clamp(Weather.Rainfall, 0.f, 1.f));
        const float Previous = Stock;
        Stock = FMath::Min(Patch.Capacity, Stock + float(PatchDelta) * Patch.RegrowthPerSecond * Growth);
        if (!AuditPatch.IsNone() && Patch.Id == AuditPatch && Patch.bSubmerged)
        {
            UE_LOG(LogTemp, Log, TEXT("[Eco Water Stock] Patch=%s At=%.17g Delta=%.17g Rain=%.9g Before=%.9g After=%.9g Capacity=%.9g Regen=%.9g"),
                *Patch.Id.ToString(), Now, PatchDelta, double(Weather.Rainfall), double(Previous), double(Stock),
                double(Patch.Capacity), double(Patch.RegrowthPerSecond));
        }
    }
}

void AEcoCreatureIntegrationSpawner::PublishForageVisuals()
{
    for (int32 Index = 0; Index < FaunaForageVisuals.Num(); ++Index)
    {
        if (AEcoForagePatchVisual* Visual = FaunaForageVisuals[Index].Get())
        {
            Visual->PublishStockFraction(FaunaPatchStock[Index] / FaunaHabitatPatches[Index].Capacity);
        }
    }
}

bool AEcoCreatureIntegrationSpawner::ProcessFauna(const FEcoServerTimeSnapshot& Time)
{
    if (FaunaSpecies.IsEmpty()) return true;
    auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const double Now = Time.ServerTimeSeconds;
    const FName AuditPatch(*CVarForageStockAudit.GetValueOnGameThread());
    static const int64 WaterPaymentAuditAgent = [] {
        int64 Requested = 0;
        FParse::Value(FCommandLine::Get(), TEXT("EcoIslandWaterFoodAuditAgent="), Requested);
        return Requested;
    }();
    for (auto It = FaunaFoodIntents.CreateIterator(); It; ++It)
        if (Now - It.Value().IssuedAt >= FoodIntentLifetime || !AgentLookup.Contains(It.Key())) It.RemoveCurrent();
    const bool bPersistence = UsesFaunaPersistence();
    UpdateFaunaHabitatStock(Now);
    for (auto It = FaunaCarcasses.CreateIterator(); It; ++It)
    {
        if (It.Value().ExpiresAt > Now && It.Value().Remaining > UE_SMALL_NUMBER) continue;
        const auto& Stock = It.Value();
        // A flying corpse may still land before body cleanup. The edible clock
        // is re-anchored on touchdown, so keep the original unopened stock.
        if (!Stock.bGrounded && Stock.Remaining > UE_SMALL_NUMBER)
        {
            const auto* Entity = AgentLookup.Find(It.Key());
            if (Entity && EM.IsEntityValid(*Entity))
            {
                const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(*Entity);
                const auto& Death = EM.GetFragmentDataChecked<FEcoDeathFragment>(*Entity);
                if (Fauna && Fauna->Flight != EEcoFaunaFlightPhase::Grounded && Death.bCommitted && Death.RemoveAfter > Now)
                    continue;
            }
        }
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][CarcassClosed] Id=%lld Unused=%.3f At=%.3f Reason=%s"),
            It.Key(), Stock.Remaining, Now, Stock.Remaining <= UE_SMALL_NUMBER ? TEXT("Depleted")
                : Stock.bGrounded ? TEXT("Expired") : TEXT("UnsettledExpired"));
        It.RemoveCurrent();
    }
    FeedWolvesFromCarrion(Now);
    for (const auto Entity : Owned)
    {
        auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
        auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
        if (!Fauna || Vitals.HP <= 0
            || EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State == EEcoResidenceState::Traveling) continue;
        auto& Lifetime = EM.GetFragmentDataChecked<FEcoLifetimeFragment>(Entity);
        if (Now < Lifetime.NextFeedTimeSeconds) continue;
        Lifetime.NextFeedTimeSeconds = Now + 1.;
        const auto* Species = FindFauna(EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).SpeciesId);
        const bool bAdaptive = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::FaunaMeal);
        const bool bNestling = Species->NestlingSeconds > 0.f && Fauna->Life.Origin == EcoLifeV3::EOrigin::NaturalBirth
            && Now - Fauna->Life.Born < Species->NestlingSeconds;
        const float Headroom = (bAdaptive ? Species->MealStopFraction : 1.f) * Vitals.MaxEnergy - Vitals.Energy;
        if ((!bNestling && (bAdaptive ? !Fauna->Life.MealCycle.bSeeking || Headroom <= 0.f : Vitals.Energy >= .9f * Vitals.MaxEnergy))
            || !EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value.IsNearlyZero()) continue;
        const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
        const auto& Position = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform().GetLocation();
        if (Fauna->Flight != EEcoFaunaFlightPhase::Grounded
            || (Now < Fauna->ThreatUntil && !FindFaunaShelter(Region.CurrentRegionId, Species->SpeciesId, Position, 0.))
            || Now < Fauna->RootingUntil || Fauna->AttackContact >= 0. || Fauna->GuardThreatId > 0) continue;
        Fauna->RootingUntil = -1.;
        const int64 AgentId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).StableAgentId;
        if (!bNestling && FaunaPatchStock.IsValidIndex(Fauna->PatchTarget))
        {
            const auto& Patch = FaunaHabitatPatches[Fauna->PatchTarget];
            auto& Stock = FaunaPatchStock[Fauna->PatchTarget];
            const int32 Access = Patch.HasForagePoint(Fauna->PatchAccessPoint) ? Fauna->PatchAccessPoint : 0;
            const FVector MealPoint = Patch.ForagePoint(Access);
            EcoCreatureMovement::FFaunaWaterColumn Water;
            EcoCreatureMovement::FFaunaWaterColumn AtAgent;
            const bool bWaterCandidate = Patch.bSubmerged && Fauna->TargetId <= 0 && (Species->IsAquatic() || Fauna->bSwimming);
            const bool bMealColumn = bWaterCandidate
                && EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, MealPoint, 1., Water);
            const bool bMealSubmerged = bMealColumn && MealPoint.Z > Water.Bottom && MealPoint.Z < Water.Surface;
            const bool bAgentColumn = bMealSubmerged
                && EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Position, 1., AtAgent);
            const bool bWaterMeal = bAgentColumn && Position.Z >= AtAgent.Bottom && Position.Z <= AtAgent.Surface;
            const bool bEligible = Patch.Stage <= FaunaHabitatStage && Patch.RegionId == Region.CurrentRegionId
                && Patch.Consumers.Contains(Species->SpeciesId)
                && (Patch.bSubmerged ? bWaterMeal : !Species->IsAquatic() && !Fauna->bSwimming
                    && EcoCreatureMovement::IsWadeableGround(*GetWorld(), MealPoint, Species->WadeDepth));
            const double DistanceSquared = FVector::DistSquared(MealPoint, Position);
            const bool bInReach = DistanceSquared <= FMath::Square(35.);
            const bool bCanFeed = bEligible && bInReach
                && (bWaterMeal ? EcoCreatureMovement::HasClearWaterSight(*GetWorld(), Position, MealPoint)
                    : !GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, Species->EyeHeight),
                    MealPoint + FVector(0, 0, 5.), FCollisionObjectQueryParams(ECC_WorldStatic),
                    FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaPatchMeal))));
            const float StockBefore = Stock;
            const float Meal = bCanFeed ? Patch.TakeMeal(Stock, Headroom) : 0.f;
            if (Patch.bSubmerged && WaterPaymentAuditAgent > 0 && AgentId == WaterPaymentAuditAgent)
            {
                const TCHAR* Gate = !bWaterCandidate ? TEXT("WaterCandidate") : !bMealSubmerged ? TEXT("MealWater")
                    : !bWaterMeal ? TEXT("AgentWater") : !bEligible ? TEXT("Eligibility")
                    : !bInReach ? TEXT("Distance") : !bCanFeed ? TEXT("Sight") : TEXT("Transaction");
                UE_LOG(LogTemp, Log, TEXT("[Eco Water Food][Payment] Agent=%lld At=%.9f Patch=%s Access=%d Gate=%s AgentColumn=%d AgentZ=%.9f AgentBottom=%.9f AgentSurface=%.9f MealColumn=%d MealZ=%.9f MealBottom=%.9f MealSurface=%.9f DistanceSquared=%.9g Headroom=%.9g MealCap=%.9g Before=%.9g Paid=%.9g After=%.9g"),
                    AgentId, Now, *Patch.Id.ToString(), Access, Gate, int32(bAgentColumn), Position.Z, AtAgent.Bottom, AtAgent.Surface,
                    int32(bMealColumn), MealPoint.Z, Water.Bottom, Water.Surface, DistanceSquared,
                    double(Headroom), double(Patch.EnergyPerMeal), double(StockBefore), double(Meal), double(Stock));
            }
            if (!AuditPatch.IsNone() && Patch.Id == AuditPatch && Patch.IsPlantForage())
            {
                const TCHAR* Gate = !bEligible ? TEXT("Eligibility") : !bInReach ? TEXT("Distance")
                    : !bCanFeed ? TEXT("Sight") : TEXT("Transaction");
                UE_LOG(LogTemp, Log, TEXT("[Eco Forage Payment] Patch=%s At=%.17g Agent=%lld Gate=%s DistanceSquared=%.17g Deficit=%.17g Paid=%.17g After=%.17g"),
                    *Patch.Id.ToString(), Now, AgentId, Gate, DistanceSquared, double(Headroom), double(Meal), double(Stock));
            }
            if (Meal > 0.f)
            {
                Vitals.Energy += Meal;
                Fauna->LastMeal = Now;
                RecordGameplayReason(AgentId, Region.CurrentRegionId, Now, TEXT("HabitatPatchEaten"), 0, Meal, Patch.Id);
                Fauna->RecordForageIntake(Position, Now, Meal, FaunaPersistence.ForageMemorySeconds);
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][PatchMeal] Patch=%s Species=%s Agent=%lld Amount=%.3f Remaining=%.3f Access=%d At=%.3f"),
                    *Patch.Id.ToString(), *Species->SpeciesId.ToString(), AgentId, Meal, Stock, Access, Now);
                continue;
            }
        }
        const bool bInWater = Species->IsAquatic() || Fauna->bSwimming;
        const double EyeOffset = bInWater ? 0. : Species->EyeHeight;
        if (auto* Carcass = FaunaCarcasses.Find(Fauna->CarrionTargetId);
            !bNestling && Carcass && Carcass->IsAvailable(Region.CurrentRegionId, *Species, Now, bInWater)
            && Carcass->CanApproach(AgentId, Now, bInWater)
            && FVector::DistSquared(Position, Carcass->Position) <= FMath::Square(Species->CarrionReach())
            && (bInWater ? EcoCreatureMovement::HasClearWaterSight(*GetWorld(), Position, Carcass->Position)
                : !GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, EyeOffset),
                Carcass->Position + FVector(0, 0, FMath::Min(15., EyeOffset)),
                FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaMeal)))))
        {
            const float BiteSize = Carcass->KillerId == AgentId ? Species->PredationEnergyPerMeal() : Species->CarrionEnergyPerMeal;
            const float Meal = Carcass->Bite(AgentId, Now, FMath::Min(BiteSize, Headroom), bInWater);
            if (Meal > 0.f)
            {
                Vitals.Energy += Meal;
                Fauna->LastMeal = Now;
                Fauna->LastCarrionMeal = Now;
                RecordGameplayReason(AgentId, Region.CurrentRegionId, Now, TEXT("CarrionEaten"), Fauna->CarrionTargetId, Meal);
                Fauna->RecordForageIntake(Position, Now, Meal, FaunaPersistence.ForageMemorySeconds);
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Scavenge] Eater=%lld Species=%s Carcass=%lld Amount=%.3f Remaining=%.3f At=%.3f Energy=%.3f MaxEnergy=%.3f"),
                    AgentId, *Species->SpeciesId.ToString(), Fauna->CarrionTargetId, Meal, Carcass->Remaining, Now, Vitals.Energy, Vitals.MaxEnergy);
                continue;
            }
            if (!bAdaptive) continue;
        }
        if (bInWater) continue;
        if (!Species->UsesPlantFood())
        {
            // Dependent young receive energy already held by a living parent in reach.
            if (Fauna->Life.AgeFraction(Now) >= 1. || Vitals.Energy >= .65f * Vitals.MaxEnergy) continue;
            for (int64 ParentId : {Fauna->Life.Caregiver,
                    Fauna->Life.Caregiver == Fauna->Life.ParentA ? Fauna->Life.ParentB : Fauna->Life.ParentA})
            {
                const auto* Parent = AgentLookup.Find(ParentId);
                if (!Parent || !EM.IsEntityValid(*Parent)
                    || EM.GetFragmentDataChecked<FEcoRegionFragment>(*Parent).CurrentRegionId != Region.CurrentRegionId) continue;
                auto& Adult = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Parent);
                if (Adult.HP <= 0.f) continue;
                const FVector ParentPosition = EM.GetFragmentDataChecked<FTransformFragment>(*Parent).GetTransform().GetLocation();
                if ((bNestling && (FMath::Abs(Position.Z - ParentPosition.Z) > 25.
                    || EM.GetFragmentDataChecked<FEcoFaunaFragment>(*Parent).Flight != EEcoFaunaFlightPhase::Grounded))
                    || FVector::DistSquared(Position, ParentPosition) > FMath::Square(bNestling ? 140. : 650.)
                    || GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, Species->EyeHeight),
                        ParentPosition + FVector(0, 0, Species->EyeHeight), FCollisionObjectQueryParams(ECC_WorldStatic),
                        FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaParentMeal)))) continue;
                const float Amount = FMath::Min(1.f, FMath::Max(0.f, Adult.Energy - .55f * Adult.MaxEnergy));
                if (Amount <= 0.f) continue;
                Adult.Energy -= Amount;
                Vitals.Energy += Amount;
                Fauna->LastMeal = Now;
                RecordGameplayReason(AgentId, Region.CurrentRegionId, Now, TEXT("ParentProvisioned"), ParentId, Amount);
                if (bAuditFaunaHunts)
                    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][ParentMeal] Species=%s Agent=%lld Amount=%.3f"),
                        *Species->SpeciesId.ToString(), AgentId, Amount);
                break;
            }
            continue;
        }
        // Rules-only regions may supply authored patches, but have no Native vegetation grid.
        // A stopped traveler in a transit region follows the same food contract as its residents.
        if (Groups.ContainsByPredicate([&](const FEcoCreatureSpawnGroup& Group)
            { return Group.RegionId == Region.CurrentRegionId && Group.bRulesOnly; })) continue;
        double Nutrition = 0.;
        if (!Native->ConsumeFaunaFood(Region.CurrentRegionId, Position, Species->FoodPerMeal,
            Headroom / EcoFaunaNutrition::PlantEnergyPerUnit, Nutrition)) return false;
        if (Nutrition > 0.)
        {
            const float Before = Vitals.Energy;
            Vitals.Energy = FMath::Min(Vitals.MaxEnergy, Before + float(Nutrition) * EcoFaunaNutrition::PlantEnergyPerUnit);
            const float Gained = Vitals.Energy - Before;
            RecordGameplayReason(AgentId, Region.CurrentRegionId, Now, TEXT("PlantsEaten"), 0, Gained);
            if (bAuditFaunaHunts)
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][PlantMeal] Species=%s Agent=%lld Amount=%.3f"),
                    *Species->SpeciesId.ToString(), AgentId, Gained);
            if (Gained > 0.f)
                Fauna->RecordForageIntake(Position, Now, Gained, FaunaPersistence.ForageMemorySeconds);
            Fauna->LastMeal = Now;
        }
    }

    const auto Resident = [&](int64 Id, FName Region, FName Species)
    {
        const auto* Entity = AgentLookup.Find(Id);
        if (!Entity || !EM.IsEntityValid(*Entity)) return FMassEntityHandle{};
        const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(*Entity);
        const auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity);
        if (!Fauna || Vitals.HP <= 0 || EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Entity).SpeciesId != Species
            || EM.GetFragmentDataChecked<FEcoRegionFragment>(*Entity).CurrentRegionId != Region)
            return FMassEntityHandle{};
        return *Entity;
    };
    const auto Eligible = [&](int64 Id, FName Region, FName Species)
    {
        const auto Entity = Resident(Id, Region, Species);
        if (!Entity.IsSet()) return FMassEntityHandle{};
        if (EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State == EEcoResidenceState::Traveling) return FMassEntityHandle{};
        const auto& Fauna = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entity);
        const auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
        if (Now < Fauna.ThreatUntil || Fauna.Flight != EEcoFaunaFlightPhase::Grounded || Fauna.AttackContact >= 0.
            || Fauna.Life.Generation == MAX_uint32 || !Fauna.Life.CanParent(Now, Vitals.Energy / Vitals.MaxEnergy, true, Vitals.HP / Vitals.MaxHP))
            return FMassEntityHandle{};
        return Entity;
    };
    const auto Position = [&](FMassEntityHandle Entity)
    {
        return EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform().GetLocation();
    };
    const auto IsNurserySuitable = [&](const FEcoFaunaHabitatPatch& Patch, const FEcoFaunaSpecies& Species)
    {
        EcoCreatureMovement::FFaunaWaterColumn Water;
        return EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Patch.RegionId, Patch.Center, Species.BodyRadius, Water)
            && Patch.Center.Z > Water.Bottom && Patch.Center.Z < Water.Surface
            && Water.TemperatureC >= Species.SpawningTemperatureC.X && Water.TemperatureC <= Species.SpawningTemperatureC.Y
            && Water.Current.SizeSquared2D() <= FMath::Square(Species.MaxNurseryCurrent);
    };
    const auto FindAquaticNursery = [&](FName Region, const FEcoFaunaSpecies& Species,
        const FVector& First, const FVector& Second) -> const FEcoFaunaHabitatPatch*
    {
        const FEcoFaunaHabitatPatch* Best = nullptr;
        double BestDistance = FMath::Square(270.) * 2.;
        for (const auto& Patch : FaunaHabitatPatches)
        {
            if (!Patch.bAquaticNursery || Patch.Stage > FaunaHabitatStage || Patch.RegionId != Region
                || !Patch.Consumers.Contains(Species.SpeciesId)) continue;
            const double A = FVector::DistSquared(First, Patch.Center);
            const double B = FVector::DistSquared(Second, Patch.Center);
            if (A > FMath::Square(270.) || B > FMath::Square(270.) || A + B >= BestDistance) continue;
            if (!IsNurserySuitable(Patch, Species)) continue;
            Best = &Patch;
            BestDistance = A + B;
        }
        return Best;
    };
    const auto FindBroodSite = [&](FName Region, const FEcoFaunaSpecies& Species, const FVector& First,
        const FVector& Second, FName RequiredId = NAME_None) -> const FEcoFaunaPerch*
    {
        const FEcoFaunaPerch* Best = nullptr;
        double BestDistance = TNumericLimits<double>::Max();
        for (const auto& Site : FaunaPerches)
        {
            if (Site.NestId.IsNone() || Site.RegionId != Region || Site.SpeciesId != Species.SpeciesId
                || (!RequiredId.IsNone() && Site.NestId != RequiredId)) continue;
            const double A = FVector::DistSquared(First, Site.Location);
            const double B = FVector::DistSquared(Second, Site.Location);
            if (FMath::Min(A, B) > FMath::Square(125.) || FMath::Max(A, B) > FMath::Square(700.)
                || A + B >= BestDistance) continue;
            const auto* SiteRegion = FindRegion(Site.Location);
            FVector Ground;
            if (!SiteRegion || SiteRegion->RegionId != Region
                || !EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Site.Location, Ground)
                || FMath::Abs(Ground.Z - Site.Location.Z) > 10.) continue;
            if (Owned.ContainsByPredicate([&](FMassEntityHandle Entity) {
                const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
                return Fauna && Fauna->Life.Origin == EcoLifeV3::EOrigin::NaturalBirth
                    && Now - Fauna->Life.Born < Species.NestlingSeconds
                    && EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).SpeciesId == Species.SpeciesId
                    && EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP > 0.f
                    && FVector::DistSquared(Fauna->Home, Site.Location) <= FMath::Square(100.);
            })) continue;
            Best = &Site;
            BestDistance = A + B;
        }
        return Best;
    };
    const auto HasBreedingFood = [&](FMassEntityHandle Hunter, const FEcoFaunaSpecies& Species)
    {
        if (!bPersistence && Species.UsesPlantFood()) return true;
        const auto& Fauna = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Hunter);
        const auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Hunter);
        const float Window = FaunaPersistence.ForageMemorySeconds;
        const float Demand = Species.Maintenance * Fauna.MaintenanceScale * FMath::Min(Species.Gestation, Window);
        const float Intake = Fauna.RecentForageIntake(Now, Window);
        // A potential prey count does not demonstrate that either parent can feed.
        if (!Species.UsesPlantFood() && (Fauna.LastForageIntakeAt < 0. || Now - Fauna.LastForageIntakeAt > Window))
            return false;
        return EcoFaunaFeeding::BreedingReserve(Vitals.Energy, Vitals.MaxEnergy, Intake) >= Demand;
    };
    for (int32 Index = FaunaBirths.Num() - 1; Index >= 0; --Index)
    {
        const auto Birth = FaunaBirths[Index];
        const auto ResidentA = Resident(Birth.ParentA, Birth.Region, Birth.Species);
        const auto ResidentB = Resident(Birth.ParentB, Birth.Region, Birth.Species);
        if (!ResidentA.IsSet() || !ResidentB.IsSet() || Now > Birth.Due + 20.)
        {
            FaunaBirths.RemoveAtSwap(Index);
            continue;
        }
        const auto* Species = FindFauna(Birth.Species);
        const FEcoFaunaHabitatPatch* Nursery = nullptr;
        if (Species->IsAquatic())
        {
            Nursery = FaunaHabitatPatches.FindByPredicate([&](const auto& Patch) {
                return Patch.Id == Birth.NurseryId && Patch.bAquaticNursery && Patch.Stage <= FaunaHabitatStage
                    && Patch.RegionId == Birth.Region && Patch.Consumers.Contains(Birth.Species);
            });
            EcoCreatureMovement::FFaunaWaterColumn Water;
            if (!Nursery || !EcoCreatureMovement::ProbeFaunaWaterColumn(*GetWorld(), Birth.Region, Nursery->Center, Water)
                || Nursery->Center.Z <= Water.Bottom || Nursery->Center.Z >= Water.Surface)
            {
                FaunaBirths.RemoveAtSwap(Index);
                for (const auto Parent : {ResidentA, ResidentB})
                {
                    auto& Life = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Parent).Life;
                    Life.NextBirth = FMath::Max(Life.NextBirth, Now + 30.);
                }
                RecordGameplayReason(Birth.ParentA, Birth.Region, Now, TEXT("BirthAquaticNurseryInterrupted"),
                    Birth.ParentB, 0., Birth.NurseryId);
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][AquaticNurseryInterrupted] Nursery=%s Species=%s Parents=%lld,%lld At=%.2f"),
                    *Birth.NurseryId.ToString(), *Birth.Species.ToString(), Birth.ParentA, Birth.ParentB, Now);
                continue;
            }
        }
        if (Now < Birth.Due) continue;
        const auto A = Eligible(Birth.ParentA, Birth.Region, Birth.Species);
        const auto B = Eligible(Birth.ParentB, Birth.Region, Birth.Species);
        if (!A.IsSet() || !B.IsSet() || FVector::DistSquared(Position(A), Position(B)) > FMath::Square(1500.))
            continue;
        const auto* BroodSite = Species->NestlingSeconds > 0.f
            ? FindBroodSite(Birth.Region, *Species, Position(A), Position(B), Birth.NestId) : nullptr;
        if (Species->NestlingSeconds > 0.f && !BroodSite) continue;
        FaunaBirths.RemoveAtSwap(Index);
        auto& ParentA = EM.GetFragmentDataChecked<FEcoFaunaFragment>(A).Life;
        auto& ParentB = EM.GetFragmentDataChecked<FEcoFaunaFragment>(B).Life;
        ParentA.NextBirth = ParentB.NextBirth = Now + 30.;
        if (CountFauna(Birth.Region, Birth.Species) >= Species->RegionalLimit) continue;
        if (!HasBreedingFood(A, *Species) || !HasBreedingFood(B, *Species))
        {
            RecordGameplayReason(Birth.ParentA, Birth.Region, Now, TEXT("BirthForageReserve"), Birth.ParentB);
            continue;
        }

        TArray<FVector> SpawnPoints;
        const FVector Center = (Position(A) + Position(B)) * .5;
        if (Nursery && (!IsNurserySuitable(*Nursery, *Species)
            || FVector::DistSquared(Position(A), Nursery->Center) > FMath::Square(270.)
            || FVector::DistSquared(Position(B), Nursery->Center) > FMath::Square(270.)))
        {
            RecordGameplayReason(Birth.ParentA, Birth.Region, Now, TEXT("BirthAquaticNurseryUnavailable"), Birth.ParentB);
            continue;
        }
        const auto* Shelter = FindFaunaShelter(Birth.Region, Birth.Species, Center, 0.);
        if (Shelter && (!Shelter->Shelters(Birth.Species, Position(A)) || !Shelter->Shelters(Birth.Species, Position(B))))
            Shelter = nullptr;
        if (Shelter && FaunaPatchStock[int32(Shelter - FaunaHabitatPatches.GetData())] < 3.f * Shelter->EnergyPerMeal)
            continue;
        for (int32 Attempt = 0; Attempt < 8; ++Attempt)
        {
            const double Angle = Attempt * 2.399963 + EcoLifeV3::Unit(uint64(Birth.ParentA)) * UE_TWO_PI;
            const FVector Hint = (BroodSite ? BroodSite->Location : Nursery ? Nursery->Center : Shelter ? Shelter->Center : Center)
                + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.)
                * (BroodSite ? 55. : Nursery ? 22. + Attempt * 8. : Shelter ? Shelter->ShelterRadius * .6 : 180. + Attempt * 30.);
            FEcoFaunaPlacement Placement;
            Placement.SpeciesId = Birth.Species;
            Placement.SpawnPoints.Add(Hint);
            if (!BuildFaunaPositions(Birth.Region, Placement, SpawnPoints)) continue;
            if (BroodSite && FMath::Abs(SpawnPoints[0].Z - BroodSite->Location.Z) > 10.)
            {
                SpawnPoints.Reset();
                continue;
            }
            if (!Owned.ContainsByPredicate([&](FMassEntityHandle Entity) {
                return EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP > 0
                    && FVector::DistSquared(SpawnPoints[0], Position(Entity))
                        < FMath::Square(Shelter || Nursery || BroodSite ? FMath::Max(12.f, Species->BodyRadius * 2.f) : 100.f);
            })) break;
            SpawnPoints.Reset();
        }
        if (SpawnPoints.IsEmpty())
        {
            RecordGameplayReason(Birth.ParentA, Birth.Region, Now, BroodSite ? TEXT("BirthNoNestClearance")
                : Nursery ? TEXT("BirthNoWaterClearance") : TEXT("BirthNoGround"), Birth.ParentB);
            continue;
        }

        const uint64 Seed = uint64(Birth.ParentA) ^ EcoLifeV3::Mix(Birth.ParentB) ^ EcoLifeV3::Mix(ParentA.Offspring);
        const auto Genome = EcoLifeV3::Inherit(ParentA.Genome, ParentB.Genome, Seed);
        const uint32 Generation = FMath::Max(ParentA.Generation, ParentB.Generation) + 1;
        const int64 Caregiver = ParentA.Sex == EcoLifeV3::ESex::Female ? Birth.ParentA : Birth.ParentB;
        FRegionEcologyState Region;
        if (!Ecology->GetRegionState(Birth.Region, Region)) return false;
        const double RequiredPlantReserve = Species->UsesPlantFood() && !Shelter
            ? (Region.ProjectedFoodConsumers + 1) * EcoFaunaNutrition::MinimumMeal * FaunaBirthBufferSeconds
            : 0.;
        FEcoSpawnRequest Reservation;
        if (!Ecology->RequestFaunaBirth(Birth.Region, Time, Reservation, RequiredPlantReserve))
        {
            UE_LOG(LogTemp, Error, TEXT("[Eco Fauna][BirthReservationRejected] Region=%s Species=%s PlantReserve=%.3f"),
                *Birth.Region.ToString(), *Birth.Species.ToString(), RequiredPlantReserve);
            return false;
        }
        const int32 Actual = Reservation.Count ? SpawnFauna(Birth.Region, *Species, SpawnPoints, Time) : 0;
        const bool bReconciled = ReconcilePopulation();
        if (!Ecology->CompleteSpawnRequest(Reservation.RequestId, Actual) || !bReconciled) return false;
        if (!Actual)
        {
            RecordGameplayReason(Birth.ParentA, Birth.Region, Now,
                Reservation.DiagnosticReason.IsNone() ? FName(TEXT("BirthSpawnFailed")) : Reservation.DiagnosticReason, Birth.ParentB);
            UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][BirthDeferred] Species=%s Region=%s Food=%.3f Population=%d Reservation=%d"),
                *Birth.Species.ToString(), *Birth.Region.ToString(), Region.FoodAmount, Region.Population, Reservation.Count);
            continue;
        }
        const auto Child = Owned.Last();
        RecordGameplayReason(Birth.ParentA, Birth.Region, Now, TEXT("BirthCommitted"),
            EM.GetFragmentDataChecked<FEcoIdentityFragment>(Child).StableAgentId);
        auto& Life = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Child).Life;
        Life.Genome = Genome;
        Life.Born = Now;
        Life.Origin = EcoLifeV3::EOrigin::NaturalBirth;
        Life.Sex = EcoLifeV3::Unit(Seed) < .5 ? EcoLifeV3::ESex::Female : EcoLifeV3::ESex::Male;
        Life.ParentA = Birth.ParentA;
        Life.ParentB = Birth.ParentB;
        Life.Caregiver = Species->IsAquatic() ? 0 : Caregiver;
        Life.Generation = Generation;
        auto& ChildVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Child);
        ChildVitals.Energy = 0.f;
        for (const auto Parent : {A, B})
        {
            auto& ParentLife = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Parent).Life;
            ParentLife.NextBirth = Now + Species->BirthRecovery;
            ++ParentLife.Offspring;
            auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Parent);
            const float Transfer = .2f * Vitals.MaxEnergy;
            Vitals.Energy -= Transfer;
            ChildVitals.Energy += Transfer;
        }
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][NaturalBirth] Child=%lld Species=%s Parents=%lld,%lld Generation=%u"),
            EM.GetFragmentDataChecked<FEcoIdentityFragment>(Child).StableAgentId, *Birth.Species.ToString(),
            Birth.ParentA, Birth.ParentB, Generation);
        if (Nursery)
        {
            RecordGameplayReason(Birth.ParentA, Birth.Region, Now, TEXT("AquaticHatch"),
                EM.GetFragmentDataChecked<FEcoIdentityFragment>(Child).StableAgentId);
            UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][AquaticHatch] Nursery=%s Child=%lld Species=%s"),
                *Nursery->Id.ToString(), EM.GetFragmentDataChecked<FEcoIdentityFragment>(Child).StableAgentId,
                *Birth.Species.ToString());
        }
        if (BroodSite)
        {
            const int64 ChildId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Child).StableAgentId;
            RecordGameplayReason(Birth.ParentA, Birth.Region, Now, TEXT("NestHatch"), ChildId);
            UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][NestHatch] Nest=%s Child=%lld Species=%s HeightZ=%.1f"),
                *BroodSite->NestId.ToString(), ChildId, *Birth.Species.ToString(), SpawnPoints[0].Z);
        }
    }

    if (Now < NextFaunaBirthScan) return true;
    NextFaunaBirthScan = Now + 5.;
    TMap<FName, TMap<FName, TArray<int64>>> BreedingCandidates;
    for (const auto& Entry : AgentLookup)
    {
        const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entry.Value);
        const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entry.Value);
        if (Eligible(Entry.Key, Region.CurrentRegionId, Id.SpeciesId).IsSet())
            BreedingCandidates.FindOrAdd(Region.CurrentRegionId).FindOrAdd(Id.SpeciesId).Add(Entry.Key);
    }
    for (const auto& Group : Groups)
    {
        auto* RegionCandidates = BreedingCandidates.Find(Group.RegionId);
        if (!RegionCandidates) continue;
        TArray<FName> UnplacedSpecies;
        RegionCandidates->GenerateKeyArray(UnplacedSpecies);
        TArray<FName> SpeciesOrder;
        // Keep the existing order for seeded species. Settlers can also breed in
        // a region that has habitat and capacity but no initial spawn placement.
        for (const auto& Placement : Group.Fauna)
            if (UnplacedSpecies.RemoveSwap(Placement.SpeciesId) > 0) SpeciesOrder.Add(Placement.SpeciesId);
        UnplacedSpecies.Sort(FNameLexicalLess());
        SpeciesOrder.Append(UnplacedSpecies);
        for (const FName SpeciesId : SpeciesOrder)
        {
            const auto* Species = FindFauna(SpeciesId);
            auto& Candidates = RegionCandidates->FindChecked(SpeciesId);
            if (!Species || Candidates.Num() < 2 || CountFauna(Group.RegionId, SpeciesId) >= Species->RegionalLimit
                || FaunaBirths.ContainsByPredicate([&](const auto& Birth) {
                    return Birth.Region == Group.RegionId && Birth.Species == SpeciesId;
                })) continue;
            Candidates.Sort();
            bool bPaired = false;
            for (int32 I = 0; I < Candidates.Num() && !bPaired; ++I)
            {
                const auto A = AgentLookup.FindChecked(Candidates[I]);
                if (!HasBreedingFood(A, *Species)) continue;
                const auto& LA = EM.GetFragmentDataChecked<FEcoFaunaFragment>(A).Life;
                for (int32 J = I + 1; J < Candidates.Num(); ++J)
                {
                    const auto B = AgentLookup.FindChecked(Candidates[J]);
                    if (!HasBreedingFood(B, *Species)) continue;
                    const auto& LB = EM.GetFragmentDataChecked<FEcoFaunaFragment>(B).Life;
                    if (LA.Sex == LB.Sex || LA.ParentA == Candidates[J] || LA.ParentB == Candidates[J]
                        || LB.ParentA == Candidates[I] || LB.ParentB == Candidates[I]
                        || (LA.ParentA && (LA.ParentA == LB.ParentA || LA.ParentA == LB.ParentB))
                        || (LA.ParentB && (LA.ParentB == LB.ParentA || LA.ParentB == LB.ParentB))
                        || FVector::DistSquared(Position(A), Position(B)) > FMath::Square(1000.)) continue;
                    const FVector APosition = Position(A);
                    const FVector BPosition = Position(B);
                    const auto* Nursery = Species->IsAquatic() ? FindAquaticNursery(Group.RegionId, *Species, APosition, BPosition) : nullptr;
                    if (Species->IsAquatic() && !Nursery) continue;
                    const auto* BroodSite = Species->NestlingSeconds > 0.f
                        ? FindBroodSite(Group.RegionId, *Species, APosition, BPosition) : nullptr;
                    if (Species->NestlingSeconds > 0.f && !BroodSite) continue;
                    FaunaBirths.Add({Group.RegionId, SpeciesId, Candidates[I], Candidates[J],
                        Now + Species->Gestation, BroodSite ? BroodSite->NestId : NAME_None, Nursery ? Nursery->Id : NAME_None});
                    if (Nursery)
                        RecordGameplayReason(Candidates[I], Group.RegionId, Now, TEXT("BirthAquaticNurseryReserved"),
                            Candidates[J], Now + Species->Gestation, Nursery->Id);
                    EM.GetFragmentDataChecked<FEcoFaunaFragment>(A).Goal = BroodSite ? APosition
                        : Nursery ? Nursery->Center : FMath::Lerp(APosition, BPosition, .35);
                    EM.GetFragmentDataChecked<FEcoFaunaFragment>(B).Goal = BroodSite ? BPosition
                        : Nursery ? Nursery->Center : FMath::Lerp(APosition, BPosition, .65);
                    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][BirthQueued] Species=%s Parents=%lld,%lld Due=%.2f Nursery=%s"),
                        *SpeciesId.ToString(), Candidates[I], Candidates[J], Now + Species->Gestation,
                        Nursery ? *Nursery->Id.ToString() : TEXT("None"));
                    bPaired = true;
                    break;
                }
            }
        }
    }
    return true;
}

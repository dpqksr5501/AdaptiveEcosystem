#include "Creature/Runtime/EcoFauna.h"

#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityManager.h"
#include "MassEntityTemplateRegistry.h"
#include "MassMovementFragments.h"
#include "MassSpawnerSubsystem.h"
#include "World/EcoWorldClockSubsystem.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"

namespace
{
    constexpr double FaunaBirthBufferSeconds = 5.;
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
    double Requested, double& OutNutrition)
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
    const double Taken = FMath::Min(Requested, Grid.Food[Cell]);
    if (Taken < EcoFaunaNutrition::MinimumMeal) return true;
    const double Before = Grid.Total();
    const auto Sequence = Context->ResourceReceiptSequence + 1;
    if (!Ecology->CommitSpatialFood(RegionId, Sequence, Before, Taken, 0., Before - Taken, 0.)) return false;
    Context->ResourceReceiptSequence = Sequence;
    Grid.Food[Cell] -= Taken;
    Context->Sim.Stats.FoodEaten += Taken;
    OutNutrition = Taken;
    if (Grid.Vegetation.bHabitatDynamics && Grid.Habitats[Cell].bNatural)
    {
        Grid.VegetationCells[Cell].RecordBrowse(Taken, Grid.Cap[Cell]);
        OutNutrition *= Grid.VegetationCells[Cell].NutritionMultiplier();
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
            || (Species.Diet == EEcoFaunaDiet::Herbivore && (!Species.PreyRules.IsEmpty() || Species.CarrionEnergyPerMeal > 0.f))
            || (Species.Diet == EEcoFaunaDiet::Carnivore && Species.PreyRules.IsEmpty() && Species.CarrionEnergyPerMeal <= 0.f)
            || (Species.Locomotion == EEcoFaunaLocomotion::Flight && (!Positive(Species.FlightSpeed)
                || !Positive(Species.FlightCruiseHeight) || !Positive(Species.FlightCeiling)
                || Species.FlightCruiseHeight > Species.FlightCeiling || Visual->AnimationProfile->Poses.Num() != 12))
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
    return Errors.Num() == Before;
}

bool AEcoCreatureIntegrationSpawner::BuildFaunaPositions(FName RegionId,
    const FEcoFaunaPlacement& Placement, TArray<FVector>& Out) const
{
    Out.Reset();
    const auto& Sites = FaunaHabitatStage >= Placement.HabitatSpawnStage && !Placement.HabitatSpawnPoints.IsEmpty()
        ? Placement.HabitatSpawnPoints : Placement.SpawnPoints;
    for (const auto& Point : Sites)
    {
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
    TSet<FName> Ids;
    for (int32 Index = 0; Index < FaunaHabitatPatches.Num(); ++Index)
    {
        auto& Patch = FaunaHabitatPatches[Index];
        if (Patch.Stage > FaunaHabitatStage) continue;
        FVector Ground;
        if (Patch.Id.IsNone() || Ids.Contains(Patch.Id) || Patch.Stage < 1 || Patch.Center.ContainsNaN()
            || !FMath::IsFinite(Patch.Capacity) || Patch.Capacity <= 0.f
            || !FMath::IsFinite(Patch.RegrowthPerSecond) || Patch.RegrowthPerSecond < 0.f
            || !FMath::IsFinite(Patch.EnergyPerMeal) || Patch.EnergyPerMeal <= 0.f
            || !FMath::IsFinite(Patch.ShelterRadius) || Patch.ShelterRadius < 0.f
            || !FMath::IsFinite(Patch.EntranceRadius) || Patch.EntranceRadius < 0.f
            || (Patch.ShelterRadius > 0.f && (!FindFauna(Patch.ShelteredSpecies) || Patch.EntranceRadius <= 0.f))
            || Patch.Consumers.IsEmpty() || Patch.Consumers.ContainsByPredicate([this](FName Species) { return !FindFauna(Species); })
            || !EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Patch.Center, Ground)
            || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Ground, 0.f))
        {
            UE_LOG(LogTemp, Error, TEXT("[Eco Fauna] Invalid habitat patch %s"), *Patch.Id.ToString());
            return false;
        }
        const auto* Region = FindRegion(Ground);
        if (!Region || Region->RegionId != Patch.RegionId) return false;
        Patch.Center = Ground;
        Ids.Add(Patch.Id);
        FaunaPatchStock[Index] = Patch.Capacity;
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
        Life.Genome = EcoLifeV3::Founder(FounderSeed, Id.StableAgentId);
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

bool AEcoCreatureIntegrationSpawner::ProcessFauna(const FEcoServerTimeSnapshot& Time)
{
    if (FaunaSpecies.IsEmpty()) return true;
    auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const double Now = Time.ServerTimeSeconds;
    const bool bPersistence = UsesFaunaPersistence();
    const double PatchDelta = FMath::Max(0., Now - LastFaunaPatchUpdate);
    LastFaunaPatchUpdate = Now;
    for (int32 Index = 0; Index < FaunaPatchStock.Num(); ++Index)
    {
        const auto& Patch = FaunaHabitatPatches[Index];
        if (Patch.Stage > FaunaHabitatStage) continue;
        FRegionEnvironmentState Weather;
        GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->GetEnvironmentState(Patch.RegionId, Weather);
        const float Growth = FMath::Lerp(.75f, 1.25f, FMath::Clamp(Weather.Rainfall, 0.f, 1.f));
        FaunaPatchStock[Index] = FMath::Min(Patch.Capacity, FaunaPatchStock[Index] + float(PatchDelta) * Patch.RegrowthPerSecond * Growth);
    }
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
        const float Headroom = (bAdaptive ? Species->MealStopFraction : 1.f) * Vitals.MaxEnergy - Vitals.Energy;
        if ((bAdaptive ? !Fauna->Life.MealCycle.bSeeking || Headroom <= 0.f : Vitals.Energy >= .9f * Vitals.MaxEnergy)
            || !EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value.IsNearlyZero()) continue;
        const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
        const auto& Position = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform().GetLocation();
        if (Fauna->Flight != EEcoFaunaFlightPhase::Grounded
            || (Now < Fauna->ThreatUntil && !FindFaunaShelter(Region.CurrentRegionId, Species->SpeciesId, Position, 0.))
            || Now < Fauna->RootingUntil || Fauna->AttackContact >= 0. || Fauna->GuardThreatId > 0) continue;
        Fauna->RootingUntil = -1.;
        const int64 AgentId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).StableAgentId;
        if (FaunaPatchStock.IsValidIndex(Fauna->PatchTarget))
        {
            const auto& Patch = FaunaHabitatPatches[Fauna->PatchTarget];
            auto& Stock = FaunaPatchStock[Fauna->PatchTarget];
            if (Patch.Stage <= FaunaHabitatStage && Patch.RegionId == Region.CurrentRegionId && Patch.Consumers.Contains(Species->SpeciesId)
                && FVector::DistSquared(Patch.Center, Position) <= FMath::Square(35.)
                && !GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, Species->EyeHeight),
                    Patch.Center + FVector(0, 0, 5.), FCollisionObjectQueryParams(ECC_WorldStatic),
                    FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaPatchMeal))))
            {
                const float Meal = Patch.TakeMeal(Stock, Headroom);
                if (Meal > 0.f)
                {
                    Vitals.Energy += Meal;
                    Fauna->LastMeal = Now;
                    RecordGameplayReason(AgentId, Region.CurrentRegionId, Now, TEXT("HabitatPatchEaten"), 0, Meal);
                    Fauna->RecordForageIntake(Position, Now, Meal, FaunaPersistence.ForageMemorySeconds);
                    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][PatchMeal] Patch=%s Species=%s Agent=%lld Amount=%.3f Remaining=%.3f"),
                        *Patch.Id.ToString(), *Species->SpeciesId.ToString(), AgentId, Meal, Stock);
                    continue;
                }
            }
        }
        if (auto* Carcass = FaunaCarcasses.Find(Fauna->CarrionTargetId);
            Carcass && Carcass->IsAvailable(Region.CurrentRegionId, *Species, Now)
            && Carcass->CanApproach(AgentId, Now)
            && FVector::DistSquared(Position, Carcass->Position) <= FMath::Square(Species->CarrionReach())
            && !GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, Species->EyeHeight),
                Carcass->Position + FVector(0, 0, FMath::Min(15.f, Species->EyeHeight)),
                FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaMeal))))
        {
            const float BiteSize = Species->CarrionEnergyPerMeal > 0.f ? Species->CarrionEnergyPerMeal
                : Carcass->KillerId == AgentId ? 6.f : 0.f;
            const float Meal = Carcass->Bite(AgentId, Now, FMath::Min(BiteSize, Headroom));
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
                if (FVector::DistSquared(Position, ParentPosition) > FMath::Square(650.)
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
        double Nutrition = 0.;
        const double Requested = bAdaptive ? FMath::Min(Species->FoodPerMeal, Headroom / EcoFaunaNutrition::PlantEnergyPerUnit)
            : Species->FoodPerMeal;
        if (!Native->ConsumeFaunaFood(Region.CurrentRegionId, Position, Requested, Nutrition)) return false;
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
        if (!Resident(Birth.ParentA, Birth.Region, Birth.Species).IsSet()
            || !Resident(Birth.ParentB, Birth.Region, Birth.Species).IsSet() || Now > Birth.Due + 20.)
        {
            FaunaBirths.RemoveAtSwap(Index);
            continue;
        }
        if (Now < Birth.Due) continue;
        const auto A = Eligible(Birth.ParentA, Birth.Region, Birth.Species);
        const auto B = Eligible(Birth.ParentB, Birth.Region, Birth.Species);
        if (!A.IsSet() || !B.IsSet() || FVector::DistSquared(Position(A), Position(B)) > FMath::Square(1500.))
            continue;
        FaunaBirths.RemoveAtSwap(Index);
        auto& ParentA = EM.GetFragmentDataChecked<FEcoFaunaFragment>(A).Life;
        auto& ParentB = EM.GetFragmentDataChecked<FEcoFaunaFragment>(B).Life;
        ParentA.NextBirth = ParentB.NextBirth = Now + 30.;
        const auto* Species = FindFauna(Birth.Species);
        if (CountFauna(Birth.Region, Birth.Species) >= Species->RegionalLimit) continue;
        if (!HasBreedingFood(A, *Species) || !HasBreedingFood(B, *Species))
        {
            RecordGameplayReason(Birth.ParentA, Birth.Region, Now, TEXT("BirthForageReserve"), Birth.ParentB);
            continue;
        }

        TArray<FVector> SpawnPoints;
        const FVector Center = (Position(A) + Position(B)) * .5;
        const auto* Shelter = FindFaunaShelter(Birth.Region, Birth.Species, Center, 0.);
        if (Shelter && (!Shelter->Shelters(Birth.Species, Position(A)) || !Shelter->Shelters(Birth.Species, Position(B))))
            Shelter = nullptr;
        if (Shelter && FaunaPatchStock[int32(Shelter - FaunaHabitatPatches.GetData())] < 3.f * Shelter->EnergyPerMeal)
            continue;
        for (int32 Attempt = 0; Attempt < 8; ++Attempt)
        {
            const double Angle = Attempt * 2.399963 + EcoLifeV3::Unit(uint64(Birth.ParentA)) * UE_TWO_PI;
            const FVector Hint = (Shelter ? Shelter->Center : Center) + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.)
                * (Shelter ? Shelter->ShelterRadius * .6 : 180. + Attempt * 30.);
            FEcoFaunaPlacement Placement;
            Placement.SpawnPoints.Add(Hint);
            if (!BuildFaunaPositions(Birth.Region, Placement, SpawnPoints)) continue;
            if (!Owned.ContainsByPredicate([&](FMassEntityHandle Entity) {
                return EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP > 0
                    && FVector::DistSquared(SpawnPoints[0], Position(Entity))
                        < FMath::Square(Shelter ? FMath::Max(12.f, Species->BodyRadius * 2.f) : 100.f);
            })) break;
            SpawnPoints.Reset();
        }
        if (SpawnPoints.IsEmpty())
        {
            RecordGameplayReason(Birth.ParentA, Birth.Region, Now, TEXT("BirthNoGround"), Birth.ParentB);
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
        if (!Ecology->RequestFaunaBirth(Birth.Region, Time, Reservation, RequiredPlantReserve)) return false;
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
        Life.Caregiver = Caregiver;
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
    }

    if (Now < NextFaunaBirthScan) return true;
    NextFaunaBirthScan = Now + 5.;
    for (const auto& Group : Groups)
    {
        for (const auto& Placement : Group.Fauna)
        {
            const auto* Species = FindFauna(Placement.SpeciesId);
            if (CountFauna(Group.RegionId, Placement.SpeciesId) >= Species->RegionalLimit
                || FaunaBirths.ContainsByPredicate([&](const auto& Birth) {
                    return Birth.Region == Group.RegionId && Birth.Species == Placement.SpeciesId;
                })) continue;
            TArray<int64> Candidates;
            for (const auto& Entry : AgentLookup)
                if (Eligible(Entry.Key, Group.RegionId, Placement.SpeciesId).IsSet()) Candidates.Add(Entry.Key);
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
                    FaunaBirths.Add({Group.RegionId, Placement.SpeciesId, Candidates[I], Candidates[J], Now + Species->Gestation});
                    const FVector APosition = Position(A);
                    const FVector BPosition = Position(B);
                    EM.GetFragmentDataChecked<FEcoFaunaFragment>(A).Goal = FMath::Lerp(APosition, BPosition, .35);
                    EM.GetFragmentDataChecked<FEcoFaunaFragment>(B).Goal = FMath::Lerp(APosition, BPosition, .65);
                    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][BirthQueued] Species=%s Parents=%lld,%lld Due=%.2f"),
                        *Placement.SpeciesId.ToString(), Candidates[I], Candidates[J], Now + Species->Gestation);
                    bPaired = true;
                    break;
                }
            }
        }
    }
    return true;
}

#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Player/EcoCreatureHitProxy.h"
#include "Player/EcoPlayerState.h"
#include "Player/EcoCombatRelevanceComponent.h"
#include "Player/EcoEquipmentComponent.h"
#include "Player/EcoAimComponent.h"
#include "Player/EcoWeaponFireComponent.h"
#include "Player/EcoWeaponActor.h"
#include "Player/EcoWeaponDefinition.h"
#include "Player/EcoHealthAttributeSet.h"
#include "Player/EcoAbilityAvatarComponent.h"
#include "Player/EcoGameplayAbility_ComboAttack.h"
#include "InputAction.h"
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoCreatureV3Trait.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "MassSpawnerSubsystem.h"
#include "MassMovementFragments.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplate.h"
#include "Mass/EntityFragments.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "World/EcoWorldClockSubsystem.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcoVegetationField.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoHerdMigration.h"
#include "Mass/EcoMassSurvival.h"
#include <limits>

struct FEcoCombatTestAccess
{
    static void Ready(AEcoCreatureIntegrationSpawner& S, const TArray<FMassEntityHandle>& Entities)
    { S.Owned=Entities; S.bReady=true; S.bEnableEcosystemLife=true; S.bEnablePlayerCombat=true; S.CombatEpoch=7; S.BuildAgentLookup(); }
    static void Queue(AEcoCreatureIntegrationSpawner& S, APawn& Player, int64 Target, float Damage, int32 Epoch=7, uint32 Avatar=0)
    {
        AEcoCreatureIntegrationSpawner::FComboDamage R;
        R.Player=&Player;R.Controller=Player.GetController();R.Target=Target;R.Damage=Damage;R.Epoch=Epoch;R.Avatar=Avatar;
        S.ComboDamage.Add(R);
    }
    static void Consume(AEcoCreatureIntegrationSpawner& S, const FEcoServerTimeSnapshot& T) { S.ProcessComboDamage(T); }
    static void Configure(UEcoAbilityAvatarComponent& C, UEcoAbilityInputConfig* Config) { C.InputConfig=Config; }
    static void Proxies(AEcoCreatureIntegrationSpawner& S) { S.UpdateHitProxies(); }
    static void Predation(AEcoCreatureIntegrationSpawner& S, double Now) { S.ProcessFaunaPredation(Now); }
    static void MoveFauna(AEcoCreatureIntegrationSpawner& S, double Now) { S.MoveFauna(.05f, Now); }
    static FMassEntityHandle SpawnFaunaAt(AEcoCreatureIntegrationSpawner& S, FName Region,
        const FEcoServerTimeSnapshot& Time, const FVector& Position = FVector::ZeroVector, FName SpeciesId = TEXT("Rat"))
    {
        S.bAuthorityWorld = true;
        auto& Profile = S.FaunaSpecies.AddDefaulted_GetRef();
        Profile.SpeciesId = SpeciesId;
        if (!S.RegisterFaunaTemplate() || S.SpawnFauna(Region, Profile, {Position}, Time) != 1)
            return {};
        return S.Owned.Last();
    }
    static void SetPassageRegions(AEcoCreatureIntegrationSpawner& S, AEcologyRegion& Source, AEcologyRegion& Destination)
    {
        S.Regions = { &Source, &Destination };
        S.Groups.Reset();
        for (const auto* Region : { &Source, &Destination })
            S.Groups.AddDefaulted_GetRef().RegionId = Region->RegionId;
        S.BuildAgentLookup();
    }
    static void SetSingleRegion(AEcoCreatureIntegrationSpawner& S, AEcologyRegion& Region) { S.Regions = {&Region}; }
    static void SetBreedingRegion(AEcoCreatureIntegrationSpawner& S, AEcologyRegion& Region)
    {
        SetSingleRegion(S, Region);
        S.Groups.Reset();
        S.Groups.AddDefaulted_GetRef().RegionId = Region.RegionId;
    }
    static void Passages(AEcoCreatureIntegrationSpawner& S, FMassEntityManager& EM,
        const FEcoServerTimeSnapshot& Time, TArray<FEcoMigrationOutcome>& Arrivals)
    { S.ReconcileFaunaPassages(EM, Time, Time.ServerTimeSeconds, 1, Arrivals); }
    static bool CanHunt(const AEcoCreatureIntegrationSpawner& S, const FMassEntityManager& Manager,
        FMassEntityHandle Hunter, FMassEntityHandle Prey, double Now)
    { return S.CanHuntFauna(Manager, Hunter, Prey, S.FaunaSpecies[0], Now, true); }
    static void RefreshHabitatStreaming(AEcoCreatureIntegrationSpawner& S) { S.UpdateHabitatStreaming(); }
    static bool InitializeHabitat(AEcoCreatureIntegrationSpawner& S) { return S.InitializeFaunaHabitat(); }
    static void UpdateHabitat(AEcoCreatureIntegrationSpawner& S, double Now) { S.UpdateFaunaHabitatStock(Now); }
    static TArray<float>& PatchStock(AEcoCreatureIntegrationSpawner& S) { return S.FaunaPatchStock; }
    static FEcoFaunaCarcass& CarcassStock(AEcoCreatureIntegrationSpawner& S, int64 Id) { return S.FaunaCarcasses.FindOrAdd(Id); }
    static const FEcoFaunaCarcass* FindCarcass(const AEcoCreatureIntegrationSpawner& S, int64 Id)
    { return S.FaunaCarcasses.Find(Id); }
    static void CommitCarcass(AEcoCreatureIntegrationSpawner& S, const FEcoDeathOutcome& Death)
    { S.CommitFaunaCarcass(Death, 0.f); }
    static bool SpawnHuntScene(AEcoCreatureIntegrationSpawner& S, FName Region, const FEcoServerTimeSnapshot& Time)
    {
        S.bAuthorityWorld = true;
        return S.RegisterFaunaTemplate()
            && S.SpawnFauna(Region, S.FaunaSpecies[0], {FVector::ZeroVector}, Time) == 1
            && S.SpawnFauna(Region, S.FaunaSpecies[1], {FVector(95., 0., 0.)}, Time) == 1
            && S.SpawnFauna(Region, S.FaunaSpecies[2], {FVector(95., 30., 0.)}, Time) == 1;
    }
    static bool FeedFauna(AEcoCreatureIntegrationSpawner& S, const FEcoServerTimeSnapshot& T) { return S.ProcessFauna(T); }
    static bool SpawnFaunaPair(AEcoCreatureIntegrationSpawner& S, FName Region, const FEcoServerTimeSnapshot& Time,
        const TArray<FVector>& Positions = {FVector(-110., -60., 0.), FVector(-110., 60., 0.)})
    {
        S.bAuthorityWorld = true;
        return S.RegisterFaunaTemplate() && S.SpawnFauna(Region, S.FaunaSpecies[0], Positions, Time) == 2;
    }
    static bool RefreshResidents(AEcoCreatureIntegrationSpawner& S) { return S.BuildAgentLookup() && S.ReconcilePopulation(); }
    static int32 FaunaCount(const AEcoCreatureIntegrationSpawner& S, FName Region) { return S.CountFauna(Region, TEXT("Rat")); }
    static const TArray<FMassEntityHandle>& Residents(const AEcoCreatureIntegrationSpawner& S) { return S.Owned; }
    static int32 PendingFaunaBirths(const AEcoCreatureIntegrationSpawner& S) { return S.FaunaBirths.Num(); }
    static FName ReservedNursery(const AEcoCreatureIntegrationSpawner& S)
    { return S.FaunaBirths.IsEmpty() ? NAME_None : S.FaunaBirths[0].NurseryId; }
};

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoPigCarrionMeal, "AdaptiveEcosystem.Fauna.Pig.SharedCarrionMeal",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoPigCarrionMeal::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* Spawner = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Region = W.World->SpawnActor<AEcologyRegion>();
    Region->RegionId = TEXT("PigMeadow");
    Region->RegionBounds->SetBoxExtent(FVector(500.));
    FEcoCombatTestAccess::SetSingleRegion(*Spawner, *Region);
    FEcoServerTimeSnapshot Time;
    Time.ServerTimeSeconds = 1.;
    const auto Entity = FEcoCombatTestAccess::SpawnFaunaAt(*Spawner, Region->RegionId, Time, FVector::ZeroVector, TEXT("Pig"));
    auto& EM = W.World->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    if (!TestTrue(TEXT("Pig is a rule-fauna resident"), EM.IsEntityValid(Entity))) return false;
    auto& Profile = Spawner->FaunaSpecies[0];
    Profile.Diet = EEcoFaunaDiet::Omnivore;
    Profile.CarrionEnergyPerMeal = 4.f;
    Profile.CarrionHungerFraction = .83f;
    Profile.ScentRange = 800.f;
    auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
    Vitals.Energy = .45f * Vitals.MaxEnergy;
    const float Before = Vitals.Energy;
    auto& Pig = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entity);
    for (const int64 Id : {400, 401})
    {
        auto& Stock = FEcoCombatTestAccess::CarcassStock(*Spawner, Id);
        Stock.Region = Region->RegionId;
        Stock.Species = Id == 400 ? TEXT("Herbivore") : TEXT("Pig");
        Stock.OpenAt = Id == 400 ? 4. : 0.;
        Stock.ExpiresAt = 24.;
        Stock.Remaining = 18.f;
    }
    FEcoCombatTestAccess::MoveFauna(*Spawner, 2.);
    TestEqual(TEXT("An unopened carcass and conspecific stock are both skipped"), Pig.CarrionTargetId, int64(0));
    EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform().SetLocation(FVector::ZeroVector);
    EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value = FVector::ZeroVector;
    Time.ServerTimeSeconds = 5.;
    FEcoCombatTestAccess::MoveFauna(*Spawner, Time.ServerTimeSeconds);
    if (!TestEqual(TEXT("Hungry pig selects accessible shared carrion"), Pig.CarrionTargetId, int64(400))) return false;
    if (!TestTrue(TEXT("The authority resource boundary commits the meal"), FEcoCombatTestAccess::FeedFauna(*Spawner, Time))) return false;
    TestEqual(TEXT("One bite is paid to the pig"), Vitals.Energy, Before + 4.f);
    TestEqual(TEXT("The same amount is charged to shared stock"), FEcoCombatTestAccess::CarcassStock(*Spawner, 400).Remaining, 14.f);
    TestEqual(TEXT("Conspecific stock remains untouched"), FEcoCombatTestAccess::CarcassStock(*Spawner, 401).Remaining, 18.f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoAquaticClockSpeed, "AdaptiveEcosystem.Fauna.Water.DayNightMovement",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoAquaticClockSpeed::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* Spawner = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Region = W.World->SpawnActor<AEcologyRegion>();
    Region->RegionId = TEXT("ClockPool");
    Region->RegionBounds->SetBoxExtent(FVector(500.));
    FEcoCombatTestAccess::SetSingleRegion(*Spawner, *Region);
    auto* Water = W.World->SpawnActor<AEcoVegetationHabitat>();
    Water->HabitatId = TEXT("ClockPoolWater");
    Water->RegionId = Region->RegionId;
    Water->Bounds->SetBoxExtent(FVector(300., 300., 100.));
    Water->bConnectedFreshWater = true;
    Water->bSupportsFaunaSwimming = true;
    Water->WaterSurfaceZ = 100.f;
    auto* Ground = W.World->SpawnActor<AActor>();
    auto* Box = NewObject<UBoxComponent>(Ground);
    Ground->SetRootComponent(Box);
    Ground->AddInstanceComponent(Box);
    Box->SetBoxExtent(FVector(250., 250., 10.));
    Box->SetCollisionObjectType(ECC_WorldStatic);
    Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Box->SetCollisionResponseToAllChannels(ECR_Block);
    Box->RegisterComponent();
    Ground->SetActorLocation(FVector(0., 0., -10.));
    auto* Clock = W.World->GetSubsystem<UEcoWorldClockSubsystem>();
    if (!TestTrue(TEXT("Authority clock starts"), Clock->StartClock(1, 60., 60.))) return false;
    FEcoServerTimeSnapshot Time;
    if (!Clock->GetSnapshotAt(0., Time)) return false;
    auto& EM = W.World->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const FVector Start(0., 0., 60.);
    const auto Entity = FEcoCombatTestAccess::SpawnFaunaAt(*Spawner, Region->RegionId, Time, Start, TEXT("AriakeCatfish"));
    if (!TestTrue(TEXT("Ariake catfish spawned"), EM.IsEntityValid(Entity))) return false;
    auto& Catfish = Spawner->FaunaSpecies[0];
    Catfish.Locomotion = EEcoFaunaLocomotion::Swimming;
    Catfish.BodyRadius = 4.f;
    Catfish.WalkSpeed = 42.f;
    Catfish.DayActivity = .26f;
    Catfish.NightActivity = .93f;
    Catfish.SightRange = 450.f;
    Spawner->FaunaHabitatStage = 1;
    auto& Patch = Spawner->FaunaHabitatPatches.AddDefaulted_GetRef();
    Patch.Id = TEXT("ClockPoolFood");
    Patch.RegionId = Region->RegionId;
    Patch.Center = Start + FVector(220., 0., 0.);
    Patch.bSubmerged = true;
    Patch.Consumers.Add(Catfish.SpeciesId);
    Patch.Capacity = 10.f;
    Patch.EnergyPerMeal = 2.f;
    if (!TestTrue(TEXT("The submerged food patch initializes"), FEcoCombatTestAccess::InitializeHabitat(*Spawner))) return false;
    FEcoCombatTestAccess::Ready(*Spawner, {Entity});
    auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform();
    auto& Fish = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entity);
    const FEcoFaunaFragment InitialFish = Fish;
    const auto MoveAt = [&](double Now)
    {
        Transform.SetLocation(Start);
        Fish = InitialFish;
        Fish.Goal = Start + FVector(200., 0., 0.);
        Fish.NextDecision = 1000.;
        FEcoCombatTestAccess::MoveFauna(*Spawner, Now);
        return FVector::Dist2D(Start, Transform.GetLocation());
    };
    const double DayDistance = MoveAt(30.);
    const double NightDistance = MoveAt(90.);
    const double ExpectedRatio = (.45 + .55 * .93) / (.45 + .55 * .26);
    TestTrue(TEXT("The catfish moves in both phases"), DayDistance > 0. && NightDistance > 0.);
    TestTrue(TEXT("The authority night phase increases swimming according to the authored activity"),
        FMath::IsNearlyEqual(NightDistance, DayDistance * ExpectedRatio, 1.e-4));
    AddInfo(FString::Printf(TEXT("Catfish 50ms horizontal movement, day %.6f cm, night %.6f cm"), DayDistance, NightDistance));

    auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
    const float HungryEnergy = .5f * Vitals.MaxEnergy;
    for (const double StartTime : {30., 90.})
    {
        Transform = FTransform(Start);
        Fish = InitialFish;
        Fish.NextDecision = StartTime;
        Vitals.Energy = HungryEnergy;
        EM.GetFragmentDataChecked<FEcoLifetimeFragment>(Entity).NextFeedTimeSeconds = StartTime;
        FEcoCombatTestAccess::MoveFauna(*Spawner, StartTime);
        const bool bNight = StartTime > 60.;
        TestEqual(TEXT("A 220 cm target is only selected at night"), Fish.PatchTarget, bNight ? 0 : INDEX_NONE);
        for (int32 Second = 0; Second <= 7; ++Second)
        {
            for (int32 Tick = 1; Tick <= 20 && Second > 0; ++Tick)
                FEcoCombatTestAccess::MoveFauna(*Spawner, StartTime + Second - 1. + .05 * Tick);
            if (!Clock->GetSnapshotAt(StartTime + Second, Time)
                || !FEcoCombatTestAccess::FeedFauna(*Spawner, Time)) return false;
            if (Vitals.Energy > HungryEnergy) break;
        }
        const float Paid = Vitals.Energy - HungryEnergy;
        TestEqual(TEXT("Only the night run reaches and takes its first meal"), Paid, bNight ? 2.f : 0.f);
        TestEqual(TEXT("The same patch pays from the original stock"),
            FEcoCombatTestAccess::PatchStock(*Spawner)[0], 10.f - Paid);
        AddInfo(FString::Printf(TEXT("Catfish %.0fs paid %.3f from the 220 cm patch"), StartTime, Paid));
    }
    // Hold the selected patch and hunger fixed while changing one execution condition.
    auto& Stock = FEcoCombatTestAccess::PatchStock(*Spawner)[0];
    double AttemptAt = 100.;
    const auto CheckPayment = [&](const TCHAR* Label, const FVector& Position, float Surface,
        const FVector& Velocity, float InitialStock, float ExpectedPayment)
    {
        Water->WaterSurfaceZ = Surface;
        Transform.SetLocation(Position);
        Fish = InitialFish;
        Fish.PatchTarget = 0;
        Fish.PatchAccessPoint = 0;
        Fish.Life.MealCycle.bSeeking = true;
        EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value = Velocity;
        EM.GetFragmentDataChecked<FEcoLifetimeFragment>(Entity).NextFeedTimeSeconds = AttemptAt;
        Vitals.Energy = HungryEnergy;
        Stock = InitialStock;
        if (!Clock->GetSnapshotAt(AttemptAt++, Time) || !FEcoCombatTestAccess::FeedFauna(*Spawner, Time))
        {
            AddError(FString::Printf(TEXT("%s: authority step failed"), Label));
            return;
        }
        TestEqual(FString::Printf(TEXT("%s: energy credited"), Label), Vitals.Energy, HungryEnergy + ExpectedPayment);
        TestEqual(FString::Printf(TEXT("%s: stock charged"), Label), Stock, InitialStock - ExpectedPayment);
        const bool bClear = EcoCreatureMovement::HasClearWaterSight(*W.World, Position, Patch.Center);
        const float StopFraction = Spawner->UsesAdaptiveRoutine(EEcoAdaptiveRoutine::FaunaMeal) ? Catfish.MealStopFraction : 1.f;
        AddInfo(FString::Printf(TEXT("WaterMealControl At=%.0f Agent=%s Point=%s Surface=%.9g Still=%d Sight=%d Headroom=%.9g MealCap=%.9g Before=%.9g Paid=%.9g After=%.9g"),
            Time.ServerTimeSeconds, *Position.ToString(), *Patch.Center.ToString(), double(Surface),
            int32(Velocity.IsNearlyZero()), int32(bClear), double(StopFraction * Vitals.MaxEnergy - HungryEnergy),
            double(Patch.EnergyPerMeal), double(InitialStock), double(Vitals.Energy - HungryEnergy), double(Stock)));
    };
    const FVector Approach(200., 0., 60.);
    CheckPayment(TEXT("Exposed selected patch"), FVector(200., 0., 50.), 55.f, FVector::ZeroVector, 10.f, 0.f);
    CheckPayment(TEXT("Agent above water with submerged patch"), FVector(200., 0., 85.), 80.f, FVector::ZeroVector, 10.f, 0.f);
    CheckPayment(TEXT("Target outside reach"), FVector(180., 0., 60.), 100.f, FVector::ZeroVector, 10.f, 0.f);
    CheckPayment(TEXT("Agent still swimming"), Approach, 100.f, FVector(10., 0., 0.), 10.f, 0.f);
    CheckPayment(TEXT("Subminimum stock"), Approach, 100.f, FVector::ZeroVector, .1f, 0.f);
    auto* Barrier = W.World->SpawnActor<AActor>();
    auto* BarrierBox = NewObject<UBoxComponent>(Barrier);
    Barrier->SetRootComponent(BarrierBox);
    Barrier->AddInstanceComponent(BarrierBox);
    BarrierBox->SetBoxExtent(FVector(2., 5., 5.));
    BarrierBox->SetCollisionObjectType(ECC_WorldStatic);
    BarrierBox->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    BarrierBox->SetCollisionResponseToAllChannels(ECR_Block);
    BarrierBox->RegisterComponent();
    Barrier->SetActorLocation(FVector(210., 0., 60.));
    CheckPayment(TEXT("Submerged barrier blocks sight"), Approach, 100.f, FVector::ZeroVector, 10.f, 0.f);
    Barrier->SetActorEnableCollision(false);
    CheckPayment(TEXT("Restored access"), Approach, 100.f, FVector::ZeroVector, 10.f, 2.f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoSeasonalAquaticPatch, "AdaptiveEcosystem.Fauna.Water.SeasonalFoodStock",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoSeasonalAquaticPatch::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* Spawner = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Region = W.World->SpawnActor<AEcologyRegion>();
    Region->RegionId = TEXT("SeasonalPool");
    Region->RegionBounds->SetBoxExtent(FVector(500.));
    FEcoCombatTestAccess::SetSingleRegion(*Spawner, *Region);
    auto* Water = W.World->SpawnActor<AEcoVegetationHabitat>();
    Water->HabitatId = TEXT("SeasonalShelf");
    Water->RegionId = Region->RegionId;
    Water->Bounds->SetBoxExtent(FVector(300., 300., 100.));
    Water->bConnectedFreshWater = true;
    Water->bSupportsFaunaSwimming = true;
    Water->WaterSurfaceZ = 20.f;
    auto* Ground = W.World->SpawnActor<AActor>();
    auto* Box = NewObject<UBoxComponent>(Ground);
    Ground->SetRootComponent(Box);
    Ground->AddInstanceComponent(Box);
    Box->SetBoxExtent(FVector(250., 250., 10.));
    Box->SetCollisionObjectType(ECC_WorldStatic);
    Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Box->SetCollisionResponseToAllChannels(ECR_Block);
    Box->RegisterComponent();
    Ground->SetActorLocation(FVector(0., 0., -10.));
    auto& Fish = Spawner->FaunaSpecies.AddDefaulted_GetRef();
    Fish.SpeciesId = TEXT("Carp");
    Fish.Locomotion = EEcoFaunaLocomotion::Swimming;
    Spawner->FaunaHabitatStage = 1;
    auto& Patch = Spawner->FaunaHabitatPatches.AddDefaulted_GetRef();
    Patch.Id = TEXT("ShelfFood");
    Patch.RegionId = Region->RegionId;
    Patch.Center = FVector(0., 0., 30.);
    Patch.bSubmerged = true;
    Patch.Consumers.Add(Fish.SpeciesId);
    Patch.Capacity = 10.f;
    Patch.RegrowthPerSecond = 1.f;
    Patch.SeasonalFullGrowthDepthCm = 20.f;
    Patch.SeasonalDryLossPerSecond = .5f;
    if (!TestTrue(TEXT("Exposed seasonal food can initialize over authored ground"), FEcoCombatTestAccess::InitializeHabitat(*Spawner))) return false;
    const auto& Stock = FEcoCombatTestAccess::PatchStock(*Spawner);
    FEcoCombatTestAccess::UpdateHabitat(*Spawner, 2.);
    TestEqual(TEXT("Exposed shelf starts empty and does not regenerate"), Stock[0], 0.f);
    Water->WaterSurfaceZ = 40.f;
    FEcoCombatTestAccess::UpdateHabitat(*Spawner, 6.);
    TestEqual(TEXT("Ten centimeters of inundation recover at half speed"), Stock[0], 2.f);
    Water->WaterSurfaceZ = 50.f;
    FEcoCombatTestAccess::UpdateHabitat(*Spawner, 8.);
    TestEqual(TEXT("Deep inundation reaches the authored growth rate"), Stock[0], 4.f);
    FEcoCombatTestAccess::UpdateHabitat(*Spawner, 8.);
    TestEqual(TEXT("Repeated resource timestamp cannot add stock"), Stock[0], 4.f);
    Water->WaterSurfaceZ = 20.f;
    FEcoCombatTestAccess::UpdateHabitat(*Spawner, 10.);
    TestEqual(TEXT("Receding water drains existing stock"), Stock[0], 3.f);
    FEcoCombatTestAccess::UpdateHabitat(*Spawner, 30.);
    TestEqual(TEXT("Extended exposure stays bounded at zero"), Stock[0], 0.f);
    Water->WaterSurfaceZ = 50.f;
    FEcoCombatTestAccess::UpdateHabitat(*Spawner, 45.);
    TestEqual(TEXT("Reinundation can recover to capacity"), Stock[0], 10.f);
    return true;
}

IMPLEMENT_COMPLEX_AUTOMATION_TEST(FEcoAquaticNurseryContinuity, "AdaptiveEcosystem.Fauna.Water.NurseryContinuity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
void FEcoAquaticNurseryContinuity::GetTests(TArray<FString>& Names, TArray<FString>& Commands) const
{
    Names = Commands = {TEXT("Continuous"), TEXT("ExposedThenRewetted"), TEXT("AnotherSiteBecomesCloser")};
}

bool FEcoAquaticNurseryContinuity::RunTest(const FString& Parameters)
{
    EcoTest::FScopedTestWorld W;
    auto* Spawner = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Region = W.World->SpawnActor<AEcologyRegion>();
    Region->RegionId = TEXT("NurseryPool");
    Region->RegionBounds->SetBoxExtent(FVector(500.));
    FEcoCombatTestAccess::SetBreedingRegion(*Spawner, *Region);
    auto* Water = W.World->SpawnActor<AEcoVegetationHabitat>();
    Water->HabitatId = TEXT("NurseryWater");
    Water->RegionId = Region->RegionId;
    Water->Bounds->SetBoxExtent(FVector(400., 400., 150.));
    Water->bConnectedFreshWater = true;
    Water->bSupportsFaunaSwimming = true;
    Water->WaterSurfaceZ = 100.f;
    auto* Ground = W.World->SpawnActor<AActor>();
    auto* Box = NewObject<UBoxComponent>(Ground);
    Ground->SetRootComponent(Box);
    Ground->AddInstanceComponent(Box);
    Box->SetBoxExtent(FVector(350., 350., 10.));
    Box->SetCollisionObjectType(ECC_WorldStatic);
    Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Box->SetCollisionResponseToAllChannels(ECR_Block);
    Box->RegisterComponent();
    Ground->SetActorLocation(FVector(0., 0., -10.));
    auto& Fish = Spawner->FaunaSpecies.AddDefaulted_GetRef();
    Fish.SpeciesId = TEXT("Carp");
    Fish.Locomotion = EEcoFaunaLocomotion::Swimming;
    Fish.BodyRadius = 5.f;
    Fish.Gestation = 10.f;
    Spawner->FaunaHabitatStage = 1;
    for (const bool bShallow : {true, false})
    {
        auto& Patch = Spawner->FaunaHabitatPatches.AddDefaulted_GetRef();
        Patch.Id = bShallow ? TEXT("ShallowNursery") : TEXT("DeepNursery");
        Patch.RegionId = Region->RegionId;
        Patch.Center = bShallow ? FVector(0., 0., 65.) : FVector(145., 0., 25.);
        Patch.bSubmerged = Patch.bAquaticNursery = true;
        Patch.Consumers.Add(Fish.SpeciesId);
        Patch.Capacity = 10.f;
    }
    auto* Ecology = W.World->GetSubsystem<UEcologySimulationSubsystem>();
    FRegionEcologyState State;
    State.RegionId = Region->RegionId;
    FEcoServerTimeSnapshot Time;
    Time.WorldEpoch = 1;
    FEcoFoodEventSettings NoFoodEvent;
    NoFoodEvent.bEnabled = false;
    if (!Ecology->RegisterRegionState(State) || !Ecology->RegisterSpawnSchedule(State.RegionId, {})
        || !Ecology->StartResourceSimulation(Time.WorldEpoch, NoFoodEvent, NoFoodEvent, false)
        || !FEcoCombatTestAccess::InitializeHabitat(*Spawner)
        || !FEcoCombatTestAccess::SpawnFaunaPair(*Spawner, State.RegionId, Time, {FVector(0., -30., 60.), FVector(0., 30., 60.)})
        || !FEcoCombatTestAccess::RefreshResidents(*Spawner))
    {
        AddError(TEXT("Aquatic nursery fixture could not initialize"));
        return false;
    }
    auto& EM = W.World->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto& Residents = FEcoCombatTestAccess::Residents(*Spawner);
    for (const auto Parent : Residents)
        EM.GetFragmentDataChecked<FEcoFaunaFragment>(Parent).RecordForageIntake(FVector::ZeroVector, 19., 5.f, 90.f);
    Time.ServerTimeSeconds = 20.;
    if (!TestTrue(TEXT("The authority processes the spawning step"), FEcoCombatTestAccess::FeedFauna(*Spawner, Time))
        || !TestEqual(TEXT("The nearer shallow site is reserved"), FEcoCombatTestAccess::ReservedNursery(*Spawner), FName(TEXT("ShallowNursery"))))
        return false;
    const bool bInterrupted = Parameters == TEXT("ExposedThenRewetted");
    Water->WaterSurfaceZ = bInterrupted ? 50.f : 100.f;
    Time.ServerTimeSeconds = 25.;
    TestTrue(TEXT("The authority processes the intervening water level"), FEcoCombatTestAccess::FeedFauna(*Spawner, Time));
    TestEqual(TEXT("Only the exposed reservation is cancelled"), FEcoCombatTestAccess::PendingFaunaBirths(*Spawner), bInterrupted ? 0 : 1);
    Water->WaterSurfaceZ = 100.f;
    if (Parameters == TEXT("AnotherSiteBecomesCloser"))
    {
        for (const auto Parent : Residents)
            EM.GetFragmentDataChecked<FTransformFragment>(Parent).GetMutableTransform().AddToTranslation(FVector(145., 0., 0.));
    }
    Time.ServerTimeSeconds = 30.;
    TestTrue(TEXT("Both scenarios reach the same hatch-time water level"), FEcoCombatTestAccess::FeedFauna(*Spawner, Time));
    if (!TestEqual(TEXT("Only continuous inundation yields a hatch"), Residents.Num(), bInterrupted ? 2 : 3)) return false;
    if (!bInterrupted)
    {
        const auto& Position = EM.GetFragmentDataChecked<FTransformFragment>(Residents.Last()).GetTransform().GetLocation();
        TestTrue(TEXT("The hatch remains at the originally reserved site"), Position.Size2D() < 85.);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoPlantForagePreferences, "AdaptiveEcosystem.Fauna.Habitat.SharedPlantForage",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoPlantForagePreferences::RunTest(const FString&)
{
    FEcoFaunaSpecies Grazer, Browser;
    Grazer.PlantPreferences.Add(EEcoFaunaPlantGuild::Grass, 1.4f);
    Browser.PlantPreferences.Add(EEcoFaunaPlantGuild::Browse, 1.4f);
    TestEqual(TEXT("Undeclared forage remains eligible at ordinary value"), Grazer.PlantPreference(EEcoFaunaPlantGuild::Forbs), 1.f);
    const auto Value = [](const auto& Species, EEcoFaunaPlantGuild Guild, double Energy) {
        return EcoFaunaFeeding::Value(Energy, 2.) * Species.PlantPreference(Guild);
    };
    TestTrue(TEXT("The same stock supports distinct choices"), Value(Grazer, EEcoFaunaPlantGuild::Grass, 5.) > Value(Grazer, EEcoFaunaPlantGuild::Browse, 5.)
        && Value(Browser, EEcoFaunaPlantGuild::Grass, 5.) < Value(Browser, EEcoFaunaPlantGuild::Browse, 5.));
    FEcoFaunaHabitatPatch Grass;
    Grass.PlantGuild = EEcoFaunaPlantGuild::Grass;
    Grass.PlantGrowthTemperature = FVector(0., 20., 40.);
    Grass.PlantGrowthRainfall = FVector2D(.5, 1.5);
    Grass.EnergyPerMeal = 2.f;
    float SharedStock = 3.f;
    TestEqual(TEXT("First consumer debits the shared reserve"), Grass.TakeMeal(SharedStock, 10.f), 2.f);
    TestEqual(TEXT("Second consumer gets the remaining stock"), Grass.TakeMeal(SharedStock, 10.f), 1.f);
    TestTrue(TEXT("A depleted preferred guild can lose to another eligible food"),
        Value(Grazer, EEcoFaunaPlantGuild::Grass, SharedStock) < Value(Grazer, EEcoFaunaPlantGuild::Browse, 5.));
    TestEqual(TEXT("Rain response interpolates at the growth optimum"), Grass.PlantRecoveryMultiplier(20., .5), 1.);
    TestEqual(TEXT("Cooler temperatures reduce recovery"), Grass.PlantRecoveryMultiplier(10., .5), .5);
    TestEqual(TEXT("Rain does not override heat limits"), Grass.PlantRecoveryMultiplier(41., 1.), 0.);
    TestEqual(TEXT("Older patches have no dry stress by default"), Grass.PlantDryStress(0., 0.), 0.);
    Grass.PlantMoistureNeed = .4f;
    TestTrue(TEXT("Dry air and no rain cause high stress"), Grass.PlantDryStress(0., .1) > .9);
    TestTrue(TEXT("Humidity moderates stress"), Grass.PlantDryStress(0., .7) < Grass.PlantDryStress(0., .1));
    TestEqual(TEXT("Wet weather clears dry stress"), Grass.PlantDryStress(.8, .7), 0.);
    TestEqual(TEXT("Moist soil relieves stress when rain has stopped"), Grass.PlantDryStressFromMoisture(.5), 0.);
    TestTrue(TEXT("Dry soil still limits plant recovery"), Grass.PlantDryStressFromMoisture(.1) > .7);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaHabitatStreaming, "AdaptiveEcosystem.Fauna.Habitat.StreamingSources",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFaunaHabitatStreaming::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* Spawner = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    Spawner->bUseHabitatStreaming = true;
    Spawner->bEnableHerdJourneys = false;
    Spawner->FaunaSpecies.AddDefaulted();
    Spawner->FaunaHabitatStage = 2;
    auto* Route = W.World->SpawnActor<AEcoHerdMigrationRoute>();
    Route->FromRegion = TEXT("Source");
    Route->ToRegion = TEXT("Destination");
    Route->Points = {FVector(20000., 0., 0.), FVector(30000., 0., 0.)};
    Route->bAllowRuleFaunaPassage = true;
    auto& Active = Spawner->FaunaHabitatPatches.AddDefaulted_GetRef();
    Active.Center = FVector(40000., 0., 0.);
    auto& Inactive = Spawner->FaunaHabitatPatches.AddDefaulted_GetRef();
    Inactive.Center = FVector(50000., 0., 0.);
    Inactive.Stage = 3;

    const auto HasPoint = [&](const FVector& Point)
    {
        return Spawner->HabitatStreamingSource->Shapes.ContainsByPredicate(
            [&](const auto& Shape) { return Shape.Location.Equals(Point); });
    };
    FEcoCombatTestAccess::RefreshHabitatStreaming(*Spawner);
    TestTrue(TEXT("Rule-fauna route keeps both endpoints and intermediate terrain loaded"),
        HasPoint(Route->Points[0]) && HasPoint(FVector(25000., 0., 0.)) && HasPoint(Route->Points[1]));
    TestTrue(TEXT("Authored food patch loads collision before its startup validation"), HasPoint(FVector(40000., 0., 0.)));
    TestFalse(TEXT("Inactive stage does not request patch collision"), HasPoint(Inactive.Center));

    FEcoCombatTestAccess::Ready(*Spawner, {});
    FEcoCombatTestAccess::RefreshHabitatStreaming(*Spawner);
    TestFalse(TEXT("Initial patch source is released after validation"), HasPoint(FVector(40000., 0., 0.)));
    TestTrue(TEXT("Rule-fauna route remains loaded after initialization"), HasPoint(Route->Points[1]));
    Route->bSharesHabitatReports = false;
    FEcoCombatTestAccess::RefreshHabitatStreaming(*Spawner);
    TestFalse(TEXT("A route unavailable to either backend releases its source"), HasPoint(Route->Points[1]));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaSpawnTimestamp, "AdaptiveEcosystem.Fauna.MotionClock.SpawnTimestamp",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFaunaSpawnTimestamp::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* Spawner = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Clock = W.World->GetSubsystem<UEcoWorldClockSubsystem>();
    auto* Ecology = W.World->GetSubsystem<UEcologySimulationSubsystem>();
    FRegionEcologyState Region;
    Region.RegionId = TEXT("SpawnClock");
    Region.FoodAmount = Region.FoodCapacity = 10.;
    if (!TestTrue(TEXT("Region is registered"), Ecology->RegisterRegionState(Region))
        || !TestTrue(TEXT("World clock has advanced to the end of a slow frame"),
            Clock->StartClock(7, 60., 60.) && Clock->AdvanceClock(1.25)))
        return false;

    FEcoServerTimeSnapshot TransactionTime;
    if (!TestTrue(TEXT("Catch-up transaction timestamp is available"), Clock->GetSnapshotAt(1., TransactionTime)))
        return false;
    const auto Entity = FEcoCombatTestAccess::SpawnFaunaAt(*Spawner, Region.RegionId, TransactionTime);
    auto& EM = W.World->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    if (!TestTrue(TEXT("Rule-fauna spawn succeeds during catch-up"), EM.IsEntityValid(Entity))) return false;
    const auto& Lifetime = EM.GetFragmentDataChecked<FEcoLifetimeFragment>(Entity);
    const auto& Runtime = EM.GetFragmentDataChecked<FEcoVitalsRuntimeFragment>(Entity);
    TestEqual(TEXT("Physical spawn is recorded at the transaction time"), Lifetime.SpawnTimeSeconds, 1.);
    TestEqual(TEXT("Metabolism starts at the transaction time"), Runtime.LastTime, 1.);
    TestEqual(TEXT("First feeding is due one second after the transaction"), Lifetime.NextFeedTimeSeconds, 2.);
    TestEqual(TEXT("Spawn does not change the world clock"), Clock->GetServerTime().ServerTimeSeconds, 1.25);
    return true;
}

IMPLEMENT_COMPLEX_AUTOMATION_TEST(FEcoRuleFaunaPassageMovement, "AdaptiveEcosystem.Fauna.Passage.GroundTransfer",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
void FEcoRuleFaunaPassageMovement::GetTests(TArray<FString>& Names, TArray<FString>& Commands) const
{
    Names = Commands = {TEXT("RegionalFood"), TEXT("HabitatPatch"), TEXT("CarcassEvidence"), TEXT("SettlersBreed")};
}

bool FEcoRuleFaunaPassageMovement::RunTest(const FString& Parameters)
{
    const bool bHabitatPatch = Parameters == TEXT("HabitatPatch");
    const bool bCarcass = Parameters == TEXT("CarcassEvidence");
    const bool bSettlers = Parameters == TEXT("SettlersBreed");
    EcoTest::FScopedTestWorld W;
    auto* Spawner = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Source = W.World->SpawnActor<AEcologyRegion>();
    auto* Destination = W.World->SpawnActor<AEcologyRegion>();
    Source->RegionId = TEXT("ForageOrigin");
    Destination->RegionId = TEXT("ForageDestination");
    Source->AdjacentRegionIds.Add(Destination->RegionId);
    Source->RegionBounds->SetBoxExtent(FVector(500., 500., 100.));
    Destination->RegionBounds->SetBoxExtent(FVector(500., 500., 100.));
    Source->SetActorLocation(FVector(-508., 0., 0.));
    Destination->SetActorLocation(FVector(508., 0., 0.));
    auto* Ground = W.World->SpawnActor<AActor>();
    auto* Box = NewObject<UBoxComponent>(Ground);
    Ground->SetRootComponent(Box);
    Ground->AddInstanceComponent(Box);
    Box->SetBoxExtent(FVector(1200., 600., 10.));
    Box->SetCollisionObjectType(ECC_WorldStatic);
    Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Box->SetCollisionResponseToAllChannels(ECR_Block);
    Box->RegisterComponent();
    Ground->SetActorLocation(FVector(0., 0., -10.));
    auto* Route = W.World->SpawnActor<AEcoHerdMigrationRoute>();
    Route->FromRegion = Source->RegionId;
    Route->ToRegion = Destination->RegionId;
    Route->Points = { FVector(-300., 0., 0.), FVector(300., 0., 0.) };
    Route->bAllowRuleFaunaPassage = true;

    auto* Ecology = W.World->GetSubsystem<UEcologySimulationSubsystem>();
    FRegionEcologyState Region;
    Region.RegionId = Source->RegionId;
    Region.FoodAmount = 0.;
    Region.FoodCapacity = 100.;
    if (!Ecology->RegisterRegionState(Region)) return false;
    Region.RegionId = Destination->RegionId;
    Region.FoodAmount = bHabitatPatch || bCarcass ? 0. : Region.FoodCapacity;
    if (!Ecology->RegisterRegionState(Region)) return false;
    FEcoServerTimeSnapshot Time;
    Time.ServerTimeSeconds = 1.;
    Time.WorldEpoch = 1;
    const auto Entity = FEcoCombatTestAccess::SpawnFaunaAt(*Spawner, Source->RegionId, Time, FVector(-110., 0., 0.));
    auto& EM = W.World->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    if (!TestTrue(TEXT("Rule-fauna agent starts in its origin"), EM.IsEntityValid(Entity))) return false;
    FEcoCombatTestAccess::SetPassageRegions(*Spawner, *Source, *Destination);
    if (bSettlers)
    {
        if (!TestTrue(TEXT("Two adults of opposite sex start in the source"),
            FEcoCombatTestAccess::SpawnFaunaPair(*Spawner, Source->RegionId, Time))) return false;
        const auto& Residents = FEcoCombatTestAccess::Residents(*Spawner);
        const auto A = Residents[1];
        const auto B = Residents[2];
        const int64 AId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(A).StableAgentId;
        const int64 BId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(B).StableAgentId;
        for (const auto Adult : {A, B})
        {
            auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Adult);
            Vitals.Energy = .2f * Vitals.MaxEnergy;
        }
        FEcoFoodEventSettings NoFoodEvent;
        NoFoodEvent.bEnabled = false;
        if (!TestTrue(TEXT("The destination has a schedule without a Rat spawn placement"),
                Ecology->RegisterSpawnSchedule(Destination->RegionId, FEcoSpawnScheduleSettings()))
            || !TestTrue(TEXT("The destination has a spatial food budget"),
                Ecology->RegisterSpatialFood(Destination->RegionId, 100., 100.))
            || !TestTrue(TEXT("The resource epoch starts"),
                Ecology->StartResourceSimulation(Time.WorldEpoch, NoFoodEvent, NoFoodEvent, false))) return false;
        TArray<FEcoMigrationOutcome> Transfers;
        for (int32 Step = 0; Step < 100 && Transfers.Num() < 2; ++Step)
        {
            Time.ServerTimeSeconds += .05;
            FEcoCombatTestAccess::MoveFauna(*Spawner, Time.ServerTimeSeconds);
            FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Transfers);
        }
        if (!TestEqual(TEXT("Both parents cross into the destination"), Transfers.Num(), 2)
            || !TestEqual(TEXT("Both are registered as destination residents"),
                FEcoCombatTestAccess::FaunaCount(*Spawner, Destination->RegionId), 2)) return false;
        for (const auto Adult : {A, B})
        {
            auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Adult);
            Vitals.Energy = Vitals.MaxEnergy;
        }
        if (!FEcoCombatTestAccess::RefreshResidents(*Spawner)) return false;
        Time.ServerTimeSeconds = 20.;
        if (!FEcoCombatTestAccess::FeedFauna(*Spawner, Time)
            || !TestEqual(TEXT("Settled parents queue one birth without a spawn placement"),
                FEcoCombatTestAccess::PendingFaunaBirths(*Spawner), 1)) return false;
        Time.ServerTimeSeconds += Spawner->FaunaSpecies[0].Gestation;
        if (!FEcoCombatTestAccess::FeedFauna(*Spawner, Time)
            || !TestEqual(TEXT("The child is born in the destination"),
                FEcoCombatTestAccess::FaunaCount(*Spawner, Destination->RegionId), 3)) return false;
        const auto& Child = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Residents.Last()).Life;
        TestTrue(TEXT("The child inherits the identities of the two arriving parents"),
            Child.Origin == EcoLifeV3::EOrigin::NaturalBirth && Child.Generation == 1 && Child.ParentA == AId && Child.ParentB == BId);
        FRegionEcologyState DestinationState;
        TestTrue(TEXT("The authority counts the child in the destination"),
            Ecology->GetRegionState(Destination->RegionId, DestinationState) && DestinationState.Population == 3);
        TestEqual(TEXT("The origin retains one resident"), FEcoCombatTestAccess::FaunaCount(*Spawner, Source->RegionId), 1);
        return true;
    }
    auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
    Vitals.Energy = .2f * Vitals.MaxEnergy;
    TArray<FEcoMigrationOutcome> Arrivals;
    const auto IsTraveling = [&]()
    {
        return EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State == EEcoResidenceState::Traveling;
    };
    if (bCarcass)
    {
        auto& Hunter = Spawner->FaunaSpecies[0];
        Hunter.Diet = EEcoFaunaDiet::Carnivore;
        Hunter.CarrionEnergyPerMeal = 3.f;
        Hunter.SightRange = 350.f;
        Hunter.ScentRange = 0.f;
        auto& Stock = FEcoCombatTestAccess::CarcassStock(*Spawner, 400);
        Stock.Species = TEXT("OtherSpecies");
        Stock.Region = Destination->RegionId;
        Stock.Position = FVector(900., 0., 0.);
        Stock.Remaining = 18.f;
        Stock.ExpiresAt = 200.;
        FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
        TestFalse(TEXT("Distant stock does not create a food advantage at the crossing"), IsTraveling());
        Stock.Position.X = 180.;
        Stock.ExpiresAt = 2.;
        FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
        TestFalse(TEXT("Stock that expires before reaching it does not justify departure"), IsTraveling());
        Stock.ExpiresAt = 200.;
        auto* Barrier = W.World->SpawnActor<AActor>();
        auto* Wall = NewObject<UBoxComponent>(Barrier);
        Barrier->SetRootComponent(Wall);
        Barrier->AddInstanceComponent(Wall);
        Wall->SetBoxExtent(FVector(5., 50., 70.));
        Wall->SetCollisionObjectType(ECC_WorldStatic);
        Wall->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        Wall->SetCollisionResponseToAllChannels(ECR_Block);
        Wall->RegisterComponent();
        Barrier->SetActorLocation(FVector(90., 0., 60.));
        FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
        TestFalse(TEXT("Stock behind a wall is unknown without a detectable scent"), IsTraveling());
        Wall->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    }
    if (bHabitatPatch)
    {
        Spawner->FaunaSpecies[0].Diet = EEcoFaunaDiet::Carnivore;
        Spawner->FaunaHabitatStage = 1;
        for (const auto* Area : {Source, Destination})
        {
            auto& Patch = Spawner->FaunaHabitatPatches.AddDefaulted_GetRef();
            Patch.Id = Patch.RegionId = Area->RegionId;
            Patch.Center = Area->GetActorLocation();
            Patch.Consumers = {TEXT("Rat")};
            Patch.Capacity = 18.f;
        }
        if (!TestTrue(TEXT("Both food patches project to the test ground"),
            FEcoCombatTestAccess::InitializeHabitat(*Spawner))) return false;
        auto& Stock = FEcoCombatTestAccess::PatchStock(*Spawner);
        FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
        TestFalse(TEXT("A stocked local patch prevents a journey to equal food"), IsTraveling());
        Stock[0] = Stock[1] = 0.f;
        FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
        TestFalse(TEXT("Empty patches do not pull an animal across the boundary"), IsTraveling());
        Stock[1] = 18.f;
        Spawner->FaunaHabitatPatches[1].Consumers.Reset();
        FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
        TestFalse(TEXT("Stock reserved for other species is not a food gain"), IsTraveling());
        Spawner->FaunaHabitatPatches[1].Consumers.Add(TEXT("Rat"));
    }
    FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
    TestTrue(TEXT("A hungry agent reserves an actual food destination"),
        EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State == EEcoResidenceState::Traveling);
    TestTrue(TEXT("Planning alone issues no arrival"), Arrivals.IsEmpty());
    for (int32 Step = 0; Step < 100 && Arrivals.IsEmpty(); ++Step)
    {
        Time.ServerTimeSeconds += .05;
        FEcoCombatTestAccess::MoveFauna(*Spawner, Time.ServerTimeSeconds);
        FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
    }
    if (!TestEqual(TEXT("Ground movement produces one crossing receipt"), Arrivals.Num(), 1)) return false;
    const auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform();
    TestTrue(TEXT("Arrival body is on the destination side"), Destination->ContainsPosition(Transform.GetLocation()));
    TestEqual(TEXT("Receipt matches new resident region"), Arrivals[0].DestinationRegionId,
        EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity).CurrentRegionId);
    Time.ServerTimeSeconds += .05;
    FEcoCombatTestAccess::Passages(*Spawner, EM, Time, Arrivals);
    TestEqual(TEXT("A completed transfer is not emitted again"), Arrivals.Num(), 1);
    return true;
}

namespace EcoCombatTest
{
    struct FPlayer
    {
        ACharacter* Pawn=nullptr; AEcoPlayerState* State=nullptr; APlayerController* PC=nullptr;
        explicit FPlayer(UWorld& World)
        {
            PC=World.SpawnActor<APlayerController>(); State=World.SpawnActor<AEcoPlayerState>();
            // Scoped test worlds have not initialized actors for play, so PostInitializeComponents
            // has not registered the controller in the world's player iterator yet.
            bool Registered=false;
            for (auto It=World.GetPlayerControllerIterator();It;++It) Registered|=It->Get()==PC;
            if (!Registered) World.AddController(PC);
            Pawn=World.SpawnActor<ACharacter>(); PC->PlayerState=State; PC->Possess(Pawn); Pawn->SetPlayerState(State);
            State->GetAbilitySystemComponent()->InitAbilityActorInfo(State,Pawn);
            State->InitializeHealthForAvatar(Pawn); State->RespawnDelay=0;
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoCombatProxy, "AdaptiveEcosystem.Combat.ProxyIdentityAndQuery", EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoCombatProxy::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* S=W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* P=W.World->SpawnActor<AEcoCreatureHitProxy>();
    P->Bind(S,7,123); P->Sync(FVector(500,0,0),1,false);
    TestFalse(TEXT("No representation or replication needed"),P->GetIsReplicated());
    TestEqual(TEXT("Query-only collider"),P->Shape->GetCollisionEnabled(),ECollisionEnabled::QueryOnly);
    TestEqual(TEXT("Stable agent identity"),P->StableAgentId,int64(123));
    TestEqual(TEXT("Body center follows logical ground"),P->GetActorLocation(),FVector(500,0,80));
    const uint32 Generation=P->BindingGeneration; P->ClearBinding();
    TestEqual(TEXT("Returned proxy cannot receive hits"),P->Shape->GetCollisionEnabled(),ECollisionEnabled::NoCollision);
    TestEqual(TEXT("Returned identity erased"),P->StableAgentId,int64(0));
    P->Bind(S,8,456);
    TestTrue(TEXT("Reused shape has fresh binding generation and epoch"),P->BindingGeneration>Generation&&P->WorldEpoch==8&&P->StableAgentId==456);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoCombatPlayerHealth, "AdaptiveEcosystem.Combat.PlayerHealthAuthorityAndAvatar", EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoCombatPlayerHealth::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W; EcoCombatTest::FPlayer P(*W.World);
    TestEqual(TEXT("GAS starts healthy"),P.State->GetHealth(),100.f);
    TestEqual(TEXT("Server effect applies actual damage"),P.State->ApplyCreatureDamage(P.Pawn,20,123),20.f);
    TestEqual(TEXT("Health is owned by the attribute set"),P.State->GetHealth(),80.f);
    TestEqual(TEXT("Nonfinite damage rejected"),P.State->ApplyCreatureDamage(P.Pawn,std::numeric_limits<float>::quiet_NaN(),123),0.f);
    P.State->bInvulnerable=true;
    TestEqual(TEXT("Invulnerability prevents damage"),P.State->ApplyCreatureDamage(P.Pawn,20,123),0.f);
    P.State->bInvulnerable=false;
    auto* Other=W.World->SpawnActor<ACharacter>();
    TestEqual(TEXT("Stale avatar cannot receive damage"),P.State->ApplyCreatureDamage(Other,20,123),0.f);
    TestEqual(TEXT("Lethal effect clamps actual damage"),P.State->ApplyCreatureDamage(P.Pawn,200,123),80.f);
    TestFalse(TEXT("HP zero is dead"),P.State->IsAlive());
    TestEqual(TEXT("Dead player cannot be hit again"),P.State->ApplyCreatureDamage(P.Pawn,20,123),0.f);
    const uint32 Generation=P.State->AvatarGeneration;
    P.PC->UnPossess(); P.PC->Possess(Other); Other->SetPlayerState(P.State);
    P.State->GetAbilitySystemComponent()->InitAbilityActorInfo(P.State,Other); P.State->InitializeHealthForAvatar(Other);
    TestTrue(TEXT("New avatar gets health and a new generation"),P.State->IsAlive()&&P.State->AvatarGeneration>Generation);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoCombatExactTarget, "AdaptiveEcosystem.Combat.ExactTargetQueueAndDeath", EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoCombatExactTarget::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W; EcoCombatTest::FPlayer P(*W.World);
    auto* S=W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Native=W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    FEcoV3IntegratedSettings Settings; Settings.StageSizeUnits=60; Native->ActivateForTest(Settings,false);
    EcoWorldV3::FWorldConfig Config;Config.NumHerbivores=2;Config.NumStalkers=Config.NumChasers=Config.NumRanged=0;
    auto* C=Native->AddContext(TEXT("Hunt"),0,FVector::ZeroVector,Config,2,0);
    if (!TestNotNull(TEXT("Native region"),C)) return false;
    auto* Mass=W.World->GetSubsystem<UMassSpawnerSubsystem>();auto& EM=Mass->GetEntityManagerChecked();
    auto* Asset=UEcoCreatureV3Trait::MakeConfig(W.World,false);
    const auto& Template=Asset->GetOrCreateEntityTemplate(*W.World);
    TArray<FMassEntityHandle> Entities;
    {auto Creation=Mass->SpawnEntities(Template,2,Entities);}
    for(int32 I=0;I<2;++I)
    {
        auto E=Entities[I];auto& Id=EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);Id.StableAgentId=101+I;Id.SpeciesId=TEXT("Herbivore");
        auto& R=EM.GetFragmentDataChecked<FEcoRegionFragment>(E);R.CurrentRegionId=TEXT("Hunt");R.CurrentRegionIndex=0;
        auto& L=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);L.bAdopted=true;L.ContextIndex=C->Index;L.Individual.bInitialized=true;
        EM.GetFragmentDataChecked<FEcoHerbivoreBodyV3Fragment>(E).Body.Pos={5.+I,5.};
        EM.GetFragmentDataChecked<FEcoVitalsRuntimeFragment>(E).WorldEpoch=7;
    }
    FEcoCombatTestAccess::Ready(*S,Entities);
    W.World->GetSubsystem<UEcoWorldClockSubsystem>()->StartClock(7,60,60);
    S->HostVisualDistance=0;
    FEcoCombatTestAccess::Proxies(*S);
    TestEqual(TEXT("Nearby logical animals have proxies without host visuals"),S->GetCombatDiagnostics().ActiveProxies,2);
    P.Pawn->SetActorLocation(FVector(50000,0,100));FEcoCombatTestAccess::Proxies(*S);
    TestEqual(TEXT("Distance returns proxies to pool"),S->GetCombatDiagnostics().ActiveProxies,0);
    TestTrue(TEXT("Proxy removal preserves logical animals"),EM.IsEntityValid(Entities[0])&&EM.IsEntityValid(Entities[1]));
    P.Pawn->SetActorLocation(FVector(1000,1000,100));FEcoCombatTestAccess::Proxies(*S);
    TestEqual(TEXT("Returning player rebinds existing pool"),S->GetCombatDiagnostics().ActiveProxies,2);

    FEcoServerTimeSnapshot T;T.WorldEpoch=7;T.ServerTimeSeconds=1;
    FEcoCombatTestAccess::Queue(*S,*P.Pawn,102,35,7,P.State->AvatarGeneration);
    FEcoCombatTestAccess::Consume(*S,T);
    TestEqual(TEXT("Selected target loses stage damage"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]).HP,65.f);
    TestEqual(TEXT("Closer nonselected animal never substituted"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[0]).HP,100.f);
    FEcoCombatTestAccess::Queue(*S,*P.Pawn,102,500,6,P.State->AvatarGeneration);
    FEcoCombatTestAccess::Queue(*S,*P.Pawn,102,500,7,P.State->AvatarGeneration+1);
    FEcoCombatTestAccess::Consume(*S,T);
    TestEqual(TEXT("Old epoch/avatar leave HP unchanged"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]).HP,65.f);
    FEcoCombatTestAccess::Queue(*S,*P.Pawn,102,80,7,P.State->AvatarGeneration);
    FEcoCombatTestAccess::Queue(*S,*P.Pawn,102,80,7,P.State->AvatarGeneration);
    FEcoCombatTestAccess::Consume(*S,T);
    TestEqual(TEXT("Lethal target remains at zero"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]).HP,0.f);
    TestEqual(TEXT("One nonlethal and one lethal commit; later hit rejected"),S->GetCombatDiagnostics().DamageCommitted,2);
    TArray<FEcoDeathOutcome> Deaths;FEcoSurvivalSettings Survival;Survival.bEnabled=false;
    TestTrue(TEXT("Existing survival consumes combat death"),EcoMassSurvival::Advance(EM,T,1,1,Survival,Deaths,true));
    TestEqual(TEXT("Exactly one death outcome"),Deaths.Num(),1);
    if(Deaths.Num()) TestTrue(TEXT("Death retains target, species and external cause"),Deaths[0].StableAgentId==102&&Deaths[0].SpeciesId==TEXT("Herbivore")&&Deaths[0].Cause==EEcoDeathCause::ExternalDamage);
    T.ServerTimeSeconds=2;EcoMassSurvival::Advance(EM,T,2,2,Survival,Deaths,true);
    TestEqual(TEXT("Next boundary does not kill again"),Deaths.Num(),0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoCombatAvatarRefresh, "AdaptiveEcosystem.Combat.AvatarRefreshGrantsMissingAbilitiesOnce", EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoCombatAvatarRefresh::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;EcoCombatTest::FPlayer P(*W.World);
    auto* Avatar=NewObject<UEcoAbilityAvatarComponent>(P.Pawn);P.Pawn->AddInstanceComponent(Avatar);Avatar->RegisterComponent();
    auto* Config=NewObject<UEcoAbilityInputConfig>(P.Pawn);
    FEcoAbilityInputBinding Binding;Binding.Action=NewObject<UInputAction>(Config);Binding.Ability=UEcoGameplayAbility_ComboAttack::StaticClass();
    Config->AbilityInputs.Add(Binding);FEcoCombatTestAccess::Configure(*Avatar,Config);
    auto* ASC=P.State->GetAbilitySystemComponent();
    TestEqual(TEXT("Existing correct avatar can still lack grants"),ASC->GetAvatarActor(),static_cast<AActor*>(P.Pawn));
    Avatar->RefreshAvatar();
    TestEqual(TEXT("Refresh grants configured ability even if actor info already exists"),ASC->GetActivatableAbilities().Num(),1);
    const uint32 Generation=P.State->AvatarGeneration;
    Avatar->RefreshAvatar();Avatar->RefreshAvatar();
    TestEqual(TEXT("Repeated refresh never duplicates ability"),ASC->GetActivatableAbilities().Num(),1);
    TestEqual(TEXT("Repeated refresh does not reset player life"),P.State->AvatarGeneration,Generation);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoCombatPresentationAdmission,"AdaptiveEcosystem.Combat.PerPlayerPresentationAdmission",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoCombatPresentationAdmission::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W; EcoCombatTest::FPlayer A(*W.World),B(*W.World);
    auto* S=W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto Add=[&](AActor* Owner)
    {
        auto* R=NewObject<UEcoCombatRelevanceComponent>(Owner); Owner->AddInstanceComponent(R); R->RegisterComponent();
        R->Offer.Coordinator=S;R->Offer.Epoch=7;R->Offer.Revision=1;R->Offer.Agents={101,102};return R;
    };
    auto* RA=Add(A.Pawn);auto* RB=Add(B.Pawn);
    TestFalse(TEXT("Server offer alone cannot authorize damage"),RA->CanAttack(S,7,101));
    RA->ServerPresented_Implementation(1,{101});RB->ServerPresented_Implementation(1,{102});
    TestTrue(TEXT("A can attack its represented animal"),RA->CanAttack(S,7,101));
    TestFalse(TEXT("A cannot attack B-only animal"),RA->CanAttack(S,7,102));
    TestTrue(TEXT("B can attack its represented animal"),RB->CanAttack(S,7,102));
    TestFalse(TEXT("B cannot attack A-only animal"),RB->CanAttack(S,7,101));
    RA->ServerPresented_Implementation(0,{102});
    TestFalse(TEXT("Stale acknowledgement rejected"),RA->CanAttack(S,7,102));
    TestFalse(TEXT("Wrong world epoch rejected"),RA->CanAttack(S,8,101));
    RA->ServerPresented_Implementation(1,{});
    TestFalse(TEXT("Presentation removal revokes damage"),RA->CanAttack(S,7,101));
    RA->ServerPresented_Implementation(1,{999});
    TestFalse(TEXT("Unassigned logical identity cannot be admitted"),RA->CanAttack(S,7,999));
    RA->ServerPresented_Implementation(1,{101,102});
    FEcoCombatOffer Next=RA->Offer;
    Next.Agents={101,103};
    RA->UpdateOffer(Next);
    TestTrue(TEXT("Retained target keeps its acknowledgement during unrelated churn"),RA->CanAttack(S,7,101));
    TestFalse(TEXT("Removed target loses its acknowledgement"),RA->CanAttack(S,7,102));
    TestFalse(TEXT("New target still needs its own acknowledgement"),RA->CanAttack(S,7,103));
    Next.Agents={101,102};
    RA->UpdateOffer(Next);
    TestFalse(TEXT("Returning target cannot reuse its removed acknowledgement"),RA->CanAttack(S,7,102));
    Next.Epoch=8;
    RA->UpdateOffer(Next);
    TestFalse(TEXT("World epoch change clears retained acknowledgements"),RA->CanAttack(S,8,101));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoGunPresentationHit,"AdaptiveEcosystem.Combat.GunPresentationTraceAndDamage",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoGunPresentationHit::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W; EcoCombatTest::FPlayer P(*W.World);
    auto* S=W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Native=W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    FEcoV3IntegratedSettings Settings;Settings.StageSizeUnits=60;Native->ActivateForTest(Settings,false);
    EcoWorldV3::FWorldConfig Config;Config.NumHerbivores=2;Config.NumStalkers=Config.NumChasers=Config.NumRanged=0;
    auto* C=Native->AddContext(TEXT("Gun"),0,FVector::ZeroVector,Config,2,0);
    if (!C) return false;
    auto* Mass=W.World->GetSubsystem<UMassSpawnerSubsystem>();auto& EM=Mass->GetEntityManagerChecked();
    auto* Asset=UEcoCreatureV3Trait::MakeConfig(W.World,false);
    TArray<FMassEntityHandle> Entities;{auto Creation=Mass->SpawnEntities(Asset->GetOrCreateEntityTemplate(*W.World),2,Entities);}
    for(int32 I=0;I<2;++I)
    {
        const auto E=Entities[I];auto& Id=EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);Id.StableAgentId=101+I;Id.SpeciesId=TEXT("Herbivore");
        auto& L=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);L.bAdopted=true;L.ContextIndex=C->Index;L.Individual.bInitialized=true;
        auto& Region=EM.GetFragmentDataChecked<FEcoRegionFragment>(E);Region.CurrentRegionId=TEXT("Gun");Region.CurrentRegionIndex=0;
        EM.GetFragmentDataChecked<FEcoHerbivoreBodyV3Fragment>(E).Body.Pos={5.+I*3.,0};
        EM.GetFragmentDataChecked<FEcoVitalsRuntimeFragment>(E).WorldEpoch=7;
    }
    auto* FaunaAsset=NewObject<UMassEntityConfigAsset>(W.World);
    FaunaAsset->GetMutableConfig().AddTrait(*NewObject<UEcoFaunaTrait>(FaunaAsset));
    TArray<FMassEntityHandle> FaunaEntities;
    {auto Creation=Mass->SpawnEntities(FaunaAsset->GetOrCreateEntityTemplate(*W.World),1,FaunaEntities);}
    if (!TestEqual(TEXT("One rule-driven animal spawned"),FaunaEntities.Num(),1)) return false;
    const auto Rat=FaunaEntities[0];
    Entities.Add(Rat);
    auto& RatIdentity=EM.GetFragmentDataChecked<FEcoIdentityFragment>(Rat);
    RatIdentity.StableAgentId=103;
    RatIdentity.SpeciesId=TEXT("Rat");
    auto& RatRegion=EM.GetFragmentDataChecked<FEcoRegionFragment>(Rat);
    RatRegion.CurrentRegionId=TEXT("Gun");
    RatRegion.CurrentRegionIndex=0;
    EM.GetFragmentDataChecked<FTransformFragment>(Rat).GetMutableTransform().SetLocation(FVector(180,0,60));
    EM.GetFragmentDataChecked<FEcoVitalsRuntimeFragment>(Rat).WorldEpoch=7;
    auto& RatProfile=S->FaunaSpecies.AddDefaulted_GetRef();
    RatProfile.SpeciesId=RatIdentity.SpeciesId;
    RatProfile.BodyRadius=3.5f;
    RatProfile.EyeHeight=6.f;
    EM.GetFragmentDataChecked<FEcoFaunaFragment>(Rat).Life.Born=-180.;
    FEcoCombatTestAccess::Ready(*S,Entities);W.World->GetSubsystem<UEcoWorldClockSubsystem>()->StartClock(7,60,60);
    FEcoCombatTestAccess::Proxies(*S);
    auto* R=NewObject<UEcoCombatRelevanceComponent>(P.Pawn);P.Pawn->AddInstanceComponent(R);R->RegisterComponent();
    R->Offer.Coordinator=S;R->Offer.Epoch=7;R->Offer.Revision=1;R->Offer.Agents={101,102,103};
    auto* Equipment=NewObject<UEcoEquipmentComponent>(P.Pawn);P.Pawn->AddInstanceComponent(Equipment);Equipment->RegisterComponent();
    auto* Aim=NewObject<UEcoAimComponent>(P.Pawn);P.Pawn->AddInstanceComponent(Aim);Aim->RegisterComponent();
    auto* Fire=NewObject<UEcoWeaponFireComponent>(P.Pawn);P.Pawn->AddInstanceComponent(Fire);Fire->RegisterComponent();
    auto* Weapon=W.World->SpawnActor<AEcoWeaponActor>();Weapon->SetOwner(P.Pawn);Weapon->bUseMuzzlePoint=true;
    auto* Data=NewObject<UEcoWeaponDefinition>(Weapon);Data->BaseDamage=30;Data->Range=1800;Weapon->Initialize(Data);Equipment->Weapon=Weapon;
    Weapon->SetActorLocation(FVector(0,0,64));TestTrue(TEXT("Equipped live player can aim"),Aim->SetAiming(true));
    FEcoServerTimeSnapshot Time;Time.WorldEpoch=7;Time.ServerTimeSeconds=0;
    Fire->ServerFire_Implementation(FVector(0,0,64),FVector::ForwardVector,Weapon);FEcoCombatTestAccess::Consume(*S,Time);
    TestEqual(TEXT("Unrepresented animal cannot lose HP"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[0]).HP,100.f);
    // First shot consumed its fire interval even though it missed. Use a fresh component for the next shot.
    auto* Fire2=NewObject<UEcoWeaponFireComponent>(P.Pawn);P.Pawn->AddInstanceComponent(Fire2);Fire2->RegisterComponent();Fire2->AmmoDamage=10;
    R->ServerPresented_Implementation(1,{102});
    Fire2->ServerFire_Implementation(FVector(0,0,64),FVector::ForwardVector,Weapon);FEcoCombatTestAccess::Consume(*S,Time);
    TestEqual(TEXT("Hidden nearer proxy is not an invisible shield"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[0]).HP,100.f);
    TestEqual(TEXT("Represented target receives gun plus ammo damage"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]).HP,60.f);
    Fire2->ServerFire_Implementation(FVector(0,0,64),FVector::ForwardVector,Weapon);FEcoCombatTestAccess::Consume(*S,Time);
    TestEqual(TEXT("Immediate repeat cannot bypass cadence"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]).HP,60.f);
    auto* Wall=W.World->SpawnActor<AActor>();
    auto* Box=NewObject<UBoxComponent>(Wall);Wall->SetRootComponent(Box);Wall->AddInstanceComponent(Box);
    Box->SetBoxExtent(FVector(40,200,200));Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Box->SetCollisionObjectType(ECC_WorldStatic);Box->SetCollisionResponseToAllChannels(ECR_Block);Box->RegisterComponent();
    Wall->SetActorLocation(FVector(1200,0,64));
    auto* Fire3=NewObject<UEcoWeaponFireComponent>(P.Pawn);P.Pawn->AddInstanceComponent(Fire3);Fire3->RegisterComponent();
    Fire3->ServerFire_Implementation(FVector(0,0,64),FVector::ForwardVector,Weapon);FEcoCombatTestAccess::Consume(*S,Time);
    TestEqual(TEXT("World blocker prevents damage to represented target"),EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]).HP,60.f);
    auto& RatVitals=EM.GetFragmentDataChecked<FEcoVitalsFragment>(Rat);
    TestEqual(TEXT("Unpresented rule-driven animal ignores all earlier shots"),RatVitals.HP,100.f);
    R->ServerPresented_Implementation(1,{103});
    auto* RatShot=NewObject<UEcoWeaponFireComponent>(P.Pawn);
    P.Pawn->AddInstanceComponent(RatShot);RatShot->RegisterComponent();
    RatShot->ServerFire_Implementation(FVector(0,0,64),FVector::ForwardVector,Weapon);
    FEcoCombatTestAccess::Consume(*S,Time);
    TestEqual(TEXT("Admitted shot traces the rat-sized authority proxy"),RatVitals.HP,70.f);
    TestTrue(TEXT("Surviving rat has recent threat evidence"),EM.GetFragmentDataChecked<FEcoFaunaFragment>(Rat).ThreatUntil>0.);
    RatVitals.HP=20.f;
    auto* LethalShot=NewObject<UEcoWeaponFireComponent>(P.Pawn);
    P.Pawn->AddInstanceComponent(LethalShot);LethalShot->RegisterComponent();
    LethalShot->ServerFire_Implementation(FVector(0,0,64),FVector::ForwardVector,Weapon);
    FEcoCombatTestAccess::Consume(*S,Time);
    TestEqual(TEXT("Lethal shot marks the rule-driven target dead"),RatVitals.HP,0.f);
    TArray<FEcoDeathOutcome> Deaths;
    FEcoSurvivalSettings Survival;Survival.bEnabled=false;
    TestTrue(TEXT("Survival consumes the hunting death"),EcoMassSurvival::Advance(EM,Time,1,1,Survival,Deaths,true));
    TestEqual(TEXT("One hunting death"),Deaths.Num(),1);
    if (Deaths.Num()==1) TestTrue(TEXT("Hunting death retains rat identity and cause"),
        Deaths[0].StableAgentId==103&&Deaths[0].SpeciesId==TEXT("Rat")&&Deaths[0].Cause==EEcoDeathCause::ExternalDamage);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaWindupMomentum, "AdaptiveEcosystem.Creature.Fauna.WindupMomentum",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFaunaWindupMomentum::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* S = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Region = W.World->SpawnActor<AEcologyRegion>();
    Region->RegionId = TEXT("Meadow");
    Region->RegionBounds->SetBoxExtent(FVector(1000., 1000., 100.));
    FEcoCombatTestAccess::SetSingleRegion(*S, *Region);
    auto* Ground = W.World->SpawnActor<AActor>();
    auto* Box = NewObject<UBoxComponent>(Ground);
    Ground->SetRootComponent(Box);
    Ground->AddInstanceComponent(Box);
    Box->SetBoxExtent(FVector(1000., 1000., 10.));
    Box->SetCollisionObjectType(ECC_WorldStatic);
    Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Box->SetCollisionResponseToAllChannels(ECR_Block);
    Box->RegisterComponent();
    Ground->SetActorLocation(FVector(0., 0., -10.));

    auto* Mass = W.World->GetSubsystem<UMassSpawnerSubsystem>();
    auto& EM = Mass->GetEntityManagerChecked();
    auto* Asset = NewObject<UMassEntityConfigAsset>(W.World);
    Asset->GetMutableConfig().AddTrait(*NewObject<UEcoFaunaTrait>(Asset));
    TArray<FMassEntityHandle> Entities;
    { auto Creation = Mass->SpawnEntities(Asset->GetOrCreateEntityTemplate(*W.World), 2, Entities); }
    if (!TestEqual(TEXT("Two rule fauna"), Entities.Num(), 2)) return false;
    const FName Names[] = {TEXT("Leopard"), TEXT("Pig")};
    S->FaunaSpecies.SetNum(2);
    for (int32 Index = 0; Index < Entities.Num(); ++Index)
    {
        auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entities[Index]);
        Id.StableAgentId = Index + 1;
        Id.SpeciesId = Names[Index];
        S->FaunaSpecies[Index].SpeciesId = Names[Index];
        EM.GetFragmentDataChecked<FEcoRegionFragment>(Entities[Index]).CurrentRegionId = Region->RegionId;
        auto& Life = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[Index]).Life;
        Life.Born = -200.;
        Life.MaturitySeconds = 60.;
    }
    auto& Hunter = S->FaunaSpecies[0];
    Hunter.Diet = EEcoFaunaDiet::Carnivore;
    Hunter.RunSpeed = 530.f;
    Hunter.AttackReach = 125.f;
    Hunter.PreyRules.AddDefaulted_GetRef().SpeciesId = Names[1];
    TestEqual(TEXT("Hunting requires no scavenging setting"), Hunter.CarrionEnergyPerMeal, 0.f);
    TestEqual(TEXT("Own kill keeps the existing default bite"), Hunter.PredationEnergyPerMeal(), 6.f);
    auto& HunterVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[0]);
    HunterVitals.Energy = .3f * HunterVitals.MaxEnergy;
    auto& HunterTransform = EM.GetFragmentDataChecked<FTransformFragment>(Entities[0]).GetMutableTransform();
    auto& PreyTransform = EM.GetFragmentDataChecked<FTransformFragment>(Entities[1]).GetMutableTransform();
    HunterTransform = FTransform::Identity;
    PreyTransform.SetLocation(FVector(105., 0., 0.));
    EM.GetFragmentDataChecked<FMassVelocityFragment>(Entities[0]).Value = FVector(350., 0., 0.);
    EM.GetFragmentDataChecked<FMassVelocityFragment>(Entities[1]).Value = FVector::ZeroVector;
    FEcoCombatTestAccess::Ready(*S, Entities);
    FEcoCombatTestAccess::MoveFauna(*S, 1.);
    const double Contact = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[0]).AttackContact;
    TestTrue(TEXT("Wind-up advances on its first swept step"), HunterTransform.GetLocation().X > 10.);
    if (!TestTrue(TEXT("Strike is scheduled after movement"), Contact > 1.)) return false;
    auto& PreyVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]);
    const float StartHP = PreyVitals.HP;
    FEcoCombatTestAccess::Predation(*S, 1.);
    TestEqual(TEXT("No early strike on wind-up"), PreyVitals.HP, StartHP);
    PreyTransform.SetLocation(FVector(300., 0., 0.));
    FEcoCombatTestAccess::Predation(*S, Contact);
    TestEqual(TEXT("Prey that escapes range before contact takes no damage"), PreyVitals.HP, StartHP);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaInjuredRatHunt, "AdaptiveEcosystem.Creature.Fauna.InjuredRatHunt",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFaunaInjuredRatHunt::RunTest(const FString&)
{
    for (const float RatHealth : {1.f, .5f})
    {
        EcoTest::FScopedTestWorld W;
        auto* S = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
        auto* Region = W.World->SpawnActor<AEcologyRegion>();
        Region->RegionId = TEXT("HuntMeadow");
        Region->RegionBounds->SetBoxExtent(FVector(1000., 1000., 100.));
        FEcoCombatTestAccess::SetBreedingRegion(*S, *Region);
        auto* Ecology = W.World->GetSubsystem<UEcologySimulationSubsystem>();
        W.World->GetSubsystem<UEcologyWorldSubsystem>()->RegisterRegion(Region);
        auto* Clock = W.World->GetSubsystem<UEcoWorldClockSubsystem>();
        FRegionEcologyState State;
        State.RegionId = Region->RegionId;
        FEcoFoodEventSettings NoFoodEvent;
        NoFoodEvent.bEnabled = false;
        FEcoServerTimeSnapshot Time;
        Time.WorldEpoch = 1;
        if (!TestTrue(TEXT("Authority region is registered"), Ecology->RegisterRegionState(State)
            && Ecology->RegisterSpawnSchedule(State.RegionId, {})
            && Clock->StartClock(Time.WorldEpoch, 60., 60.)
            && Clock->GetSnapshotAt(0., Time)
            && Ecology->StartResourceSimulation(Time.WorldEpoch, NoFoodEvent, NoFoodEvent, false))) return false;
        auto* Ground = W.World->SpawnActor<AActor>();
        auto* Box = NewObject<UBoxComponent>(Ground);
        Ground->SetRootComponent(Box);
        Ground->AddInstanceComponent(Box);
        Box->SetBoxExtent(FVector(1000., 1000., 10.));
        Box->SetCollisionObjectType(ECC_WorldStatic);
        Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        Box->SetCollisionResponseToAllChannels(ECR_Block);
        Box->RegisterComponent();
        Ground->SetActorLocation(FVector(0., 0., -10.));

        auto* Mass = W.World->GetSubsystem<UMassSpawnerSubsystem>();
        auto& EM = Mass->GetEntityManagerChecked();
        S->FaunaSpecies.SetNum(3);
        auto& Leopard = S->FaunaSpecies[0];
        Leopard.SpeciesId = TEXT("Leopard");
        Leopard.Diet = EEcoFaunaDiet::Carnivore;
        Leopard.AdultMass = 60.f;
        Leopard.RunSpeed = 530.f;
        Leopard.AttackReach = 125.f;
        Leopard.AttackWindup = .42f;
        Leopard.CarrionEnergyPerMeal = 9.f;
        Leopard.Maintenance = 0.f;
        auto& Rule = Leopard.PreyRules.AddDefaulted_GetRef();
        Rule.SpeciesId = TEXT("Rat");
        Rule.Preference = .14f;
        Rule.MaxPreyMassRatio = .1f;
        Rule.MaxPursuitStart = 320.f;
        auto& Rat = S->FaunaSpecies[1];
        Rat.SpeciesId = Rule.SpeciesId;
        Rat.AdultMass = .25f;
        Rat.AdultCarrionEnergy = 13.f;
        Rat.DefenseDamage = 0.f;
        Rat.EyeHeight = 5.f;
        Rat.DeathSettleSeconds = .85f;
        auto& Fox = S->FaunaSpecies[2];
        Fox.SpeciesId = TEXT("Fox");
        Fox.Diet = EEcoFaunaDiet::Carnivore;
        Fox.CarrionEnergyPerMeal = 7.f;
        Fox.AttackReach = 75.f;
        Fox.ScentRange = 1000.f;
        if (!TestTrue(TEXT("Three residents spawn through the authority"), FEcoCombatTestAccess::SpawnHuntScene(*S, State.RegionId, Time))) return false;
        const auto Entities = FEcoCombatTestAccess::Residents(*S);
        for (const auto Entity : Entities)
        {
            auto& Fauna = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entity);
            Fauna.Life.Genome.Size = 1.;
            Fauna.Stamina = 1.f;
            Fauna.NextDecision = 0.;
            Fauna.NextSense = 0.;
        }
        auto& Hunt = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[0]);
        auto& HunterVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[0]);
        auto& PreyVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]);
        HunterVitals.Energy = .5f * HunterVitals.MaxEnergy;
        PreyVitals.HP = RatHealth * PreyVitals.MaxHP;

        FEcoCombatTestAccess::Ready(*S, Entities);
        if (!TestTrue(TEXT("Initial population is registered"), FEcoCombatTestAccess::RefreshResidents(*S))) return false;
        FEcoCombatTestAccess::MoveFauna(*S, 1.);
        if (RatHealth == 1.f)
        {
            TestEqual(TEXT("Healthy rat does not trigger pursuit"), Hunt.TargetId, int64(0));
            TestTrue(TEXT("Healthy rat has no scheduled strike"), Hunt.AttackContact < 0.);
            TestEqual(TEXT("Healthy rat takes no damage"), PreyVitals.HP, PreyVitals.MaxHP);
            continue;
        }
        if (!TestEqual(TEXT("Injured rat becomes the target"), Hunt.TargetId, int64(2))) return false;
        const double Contact = Hunt.AttackContact;
        if (!TestTrue(TEXT("Selected rat has a scheduled contact"), Contact > 1.)) return false;
        FEcoCombatTestAccess::Predation(*S, 1.);
        TestEqual(TEXT("Windup does not deal early damage"), PreyVitals.HP, RatHealth * PreyVitals.MaxHP);
        const float BeforeFeeding = HunterVitals.Energy;
        if (!TestTrue(TEXT("Clock supplies the contact snapshot"), Clock->GetSnapshotAt(Contact, Time))) return false;
        FEcoCombatTestAccess::Predation(*S, Contact);
        TArray<FEcoDeathOutcome> Deaths;
        if (!TestTrue(TEXT("Survival commits one captured animal"),
            EcoMassSurvival::Advance(EM, Time, Contact, 1, FEcoSurvivalSettings{}, Deaths, true) && Deaths.Num() == 1)
            || !TestTrue(TEXT("Regional authority records the death"), Ecology->RecordDeaths(Deaths, 1))) return false;
        FEcoCombatTestAccess::CommitCarcass(*S, Deaths[0]);
        TestEqual(TEXT("Successful contact captures the injured rat"),
            EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]).HP, 0.f);
        TestTrue(TEXT("Death retains the hunter and predation cause"),
            EM.GetFragmentDataChecked<FEcoDeathFragment>(Entities[1]).PredatorStableAgentId == 1
            && EM.GetFragmentDataChecked<FEcoDeathFragment>(Entities[1]).Cause == EEcoDeathCause::Predation);
        const auto* Stock = FEcoCombatTestAccess::FindCarcass(*S, 2);
        if (!TestNotNull(TEXT("Captured rat produces a carcass"), Stock)) return false;
        TestEqual(TEXT("One stock holds the full rat yield"), Stock->Remaining, 13.f);
        TestEqual(TEXT("Capture does not feed the hunter before the carcass opens"), HunterVitals.Energy, BeforeFeeding);
        TestEqual(TEXT("The hunter retains its kill"), Hunt.CarrionTargetId, int64(2));
        const double SharedAt = Stock->ExclusiveUntil;
        auto& FoxVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[2]);
        auto& Scavenger = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[2]);
        FoxVitals.Energy = .5f * FoxVitals.MaxEnergy;
        const float FoxBeforeFeeding = FoxVitals.Energy;
        const FVector FoxPosition = EM.GetFragmentDataChecked<FTransformFragment>(Entities[2]).GetTransform().GetLocation();
        TestTrue(TEXT("Fox begins within feeding distance"), FVector::Dist(FoxPosition, Stock->Position) <= Fox.CarrionReach());
        FEcoCombatTestAccess::MoveFauna(*S, Contact + 1.);
        TestEqual(TEXT("The fox cannot select the hunter's meal during exclusivity"), Scavenger.CarrionTargetId, int64(0));
        EM.GetFragmentDataChecked<FMassVelocityFragment>(Entities[0]).Value = FVector::ZeroVector;
        if (!TestTrue(TEXT("Clock supplies the first feeding snapshot"), Clock->GetSnapshotAt(Contact + 1., Time))) return false;
        if (!TestTrue(TEXT("The carcass can pay its first bite"), FEcoCombatTestAccess::FeedFauna(*S, Time))) return false;
        Stock = FEcoCombatTestAccess::FindCarcass(*S, 2);
        if (!TestNotNull(TEXT("Partially eaten carcass remains registered"), Stock)) return false;
        TestEqual(TEXT("One bite adds nine energy"), HunterVitals.Energy, BeforeFeeding + 9.f);
        TestEqual(TEXT("Nine energy is debited from the same stock"), Stock->Remaining, 4.f);
        TestEqual(TEXT("The fox receives nothing during exclusivity"), FoxVitals.Energy, FoxBeforeFeeding);

        // Make the remaining stock available for the fox to choose after the killer leaves.
        EM.GetFragmentDataChecked<FTransformFragment>(Entities[0]).GetMutableTransform().SetLocation(FVector(-600., 0., 0.));
        EM.GetFragmentDataChecked<FTransformFragment>(Entities[2]).GetMutableTransform().SetLocation(FoxPosition);
        EM.GetFragmentDataChecked<FMassVelocityFragment>(Entities[2]).Value = FVector::ZeroVector;
        FEcoCombatTestAccess::MoveFauna(*S, SharedAt + .1);
        TestEqual(TEXT("The fox selects the same carcass after sharing opens"), Scavenger.CarrionTargetId, int64(2));
        if (!TestTrue(TEXT("Clock supplies the shared feeding snapshot"), Clock->GetSnapshotAt(SharedAt + .1, Time))) return false;
        if (!TestTrue(TEXT("The remaining shared stock can pay the fox"), FEcoCombatTestAccess::FeedFauna(*S, Time))) return false;
        Stock = FEcoCombatTestAccess::FindCarcass(*S, 2);
        if (!TestNotNull(TEXT("Depleted stock remains until cleanup"), Stock)) return false;
        TestEqual(TEXT("The fox receives exactly the remaining four energy"), FoxVitals.Energy, FoxBeforeFeeding + 4.f);
        TestEqual(TEXT("The same thirteen energy has now been fully paid"), Stock->Remaining, 0.f);
        if (!TestTrue(TEXT("Clock supplies the cleanup snapshot"), Clock->GetSnapshotAt(SharedAt + 1.1, Time))) return false;
        FEcoCombatTestAccess::FeedFauna(*S, Time);
        TestNull(TEXT("Depleted stock is removed"), FEcoCombatTestAccess::FindCarcass(*S, 2));
        TestEqual(TEXT("The fox cannot eat twice from the exhausted carcass"), FoxVitals.Energy, FoxBeforeFeeding + 4.f);
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaCounterTest, "AdaptiveEcosystem.Creature.Fauna.ContestedContact",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFaunaCounterTest::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W;
    auto* S = W.World->SpawnActor<AEcoCreatureIntegrationSpawner>();
    auto* Mass = W.World->GetSubsystem<UMassSpawnerSubsystem>();
    auto& EM = Mass->GetEntityManagerChecked();
    auto* Asset = NewObject<UMassEntityConfigAsset>(W.World);
    Asset->GetMutableConfig().AddTrait(*NewObject<UEcoFaunaTrait>(Asset));
    TArray<FMassEntityHandle> Entities;
    { auto Creation = Mass->SpawnEntities(Asset->GetOrCreateEntityTemplate(*W.World), 4, Entities); }
    if (!TestEqual(TEXT("Hunter and three rule-driven family members"), Entities.Num(), 4)) return false;
    S->FaunaSpecies.SetNum(2);
    const FName Names[] = {TEXT("Leopard"), TEXT("Pig"), TEXT("Pig"), TEXT("Pig")};
    for (int32 Index = 0; Index < Entities.Num(); ++Index)
    {
        auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entities[Index]);
        Id.StableAgentId = Index + 1;
        Id.SpeciesId = Names[Index];
        EM.GetFragmentDataChecked<FEcoRegionFragment>(Entities[Index]).CurrentRegionId = TEXT("Meadow");
        EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[Index]).Life.Born = -200.;
        EM.GetFragmentDataChecked<FTransformFragment>(Entities[Index]).GetMutableTransform().SetLocation(FVector(60. * Index, 0, 0));
        if (Index < 2)
        {
            S->FaunaSpecies[Index].SpeciesId = Names[Index];
            S->FaunaSpecies[Index].AdultMass = 60.f;
        }
    }
    auto& Rule = S->FaunaSpecies[0].PreyRules.AddDefaulted_GetRef();
    Rule.SpeciesId = Names[1]; Rule.MaxPreyMassRatio = 2.f; Rule.MaxHealthyMaturity = 1.f;
    S->FaunaSpecies[0].AttackReach = 120.f;
    S->FaunaSpecies[1].DefenseDamage = 18.f;
    FEcoCombatTestAccess::Ready(*S, Entities);
    auto& Hunt = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[0]);
    auto& PreyTransform = EM.GetFragmentDataChecked<FTransformFragment>(Entities[1]).GetMutableTransform();
    auto& PreyHP = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[1]).HP;
    auto& HunterHP = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entities[0]).HP;
    PreyTransform.SetRotation(FRotator(0, 180, 0).Quaternion());
    Hunt.AttackContact = 1.; Hunt.TargetId = 2;
    FEcoCombatTestAccess::Predation(*S, 1.);
    TestEqual(TEXT("Frontal defense hurts the hunter"), HunterHP, 82.f);
    TestEqual(TEXT("Counter prevented the capture"), PreyHP, 100.f);
    PreyTransform.SetRotation(FQuat::Identity);
    Hunt.AttackContact = 6.; Hunt.TargetId = 2;
    FEcoCombatTestAccess::Predation(*S, 6.);
    TestEqual(TEXT("Flank hit wounds resilient prey"), PreyHP, 55.f);
    auto& Young = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[1]);
    Young.Life.Born = 6.;
    Young.Life.Caregiver = Young.Life.ParentA = 3;
    Young.Life.ParentB = 4;
    S->FaunaSpecies[1].OffspringGuardRange = 400.f;
    EM.GetFragmentDataChecked<FTransformFragment>(Entities[2]).GetMutableTransform().SetLocation(FVector(30, 0, 0));
    EM.GetFragmentDataChecked<FTransformFragment>(Entities[3]).GetMutableTransform().SetLocation(FVector(32, 0, 0));
    Hunt.TargetId = 2;
    Hunt.AttackContact = 12.;
    FEcoCombatTestAccess::MoveFauna(*S, 11.95);
    TestEqual(TEXT("Movement selects the caregiver for the threatened juvenile"),
        EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[2]).GuardThreatId, int64(1));
    Hunt.AttackContact = 12.; Hunt.TargetId = 2;
    FEcoCombatTestAccess::Predation(*S, 12.);
    TestEqual(TEXT("Caregiver already in the attack lane intercepts"), HunterHP, 64.f);
    TestEqual(TEXT("The intercepted attack does not wound the young"), PreyHP, 55.f);
    EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[2]).Stamina = .1f;
    S->FaunaSpecies[1].bAllowSecondParentGuard = true;
    Hunt.AttackContact = 18.; Hunt.TargetId = 2;
    FEcoCombatTestAccess::Predation(*S, 18.);
    TestEqual(TEXT("Enabled second parent substitutes for the exhausted caregiver"), HunterHP, 46.f);
    S->FaunaSpecies[1].bAllowSecondParentGuard = false;
    Hunt.AttackContact = 24.; Hunt.TargetId = 2;
    FEcoCombatTestAccess::Predation(*S, 24.);
    TestEqual(TEXT("Caregiver-only profile does not recruit the second parent"), HunterHP, 46.f);
    TestEqual(TEXT("Without a valid screen the young can be wounded"), PreyHP, 10.f);

    auto& Caregiver = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entities[2]);
    Caregiver.Stamina = 1.f;
    auto& CaregiverTransform = EM.GetFragmentDataChecked<FTransformFragment>(Entities[2]).GetMutableTransform();
    CaregiverTransform.SetLocation(PreyTransform.GetLocation() + FVector(0., 160., 0.));
    PreyHP = 55.f;
    Hunt.AttackContact = 30.; Hunt.TargetId = 2;
    FEcoCombatTestAccess::Predation(*S, 30.);
    TestEqual(TEXT("Healthy caregiver nearby but outside the attack path cannot intercept"), HunterHP, 46.f);
    TestEqual(TEXT("A nearby caregiver provides no automatic protection"), PreyHP, 10.f);
    const FVector HunterPosition = EM.GetFragmentDataChecked<FTransformFragment>(Entities[0]).GetTransform().GetLocation();
    const FVector Between = (HunterPosition + PreyTransform.GetLocation()) * .5;
    EM.GetFragmentDataChecked<FTransformFragment>(Entities[3]).GetMutableTransform().SetLocation(Between);
    S->FaunaSpecies[1].bAllowSecondParentGuard = true;
    PreyHP = 55.f;
    Hunt.AttackContact = 30.; Hunt.TargetId = 2;
    FEcoCombatTestAccess::Predation(*S, 30.);
    TestEqual(TEXT("The second parent intercepts when the caregiver is outside the attack path"), HunterHP, 28.f);
    TestEqual(TEXT("The second parent's interception keeps the young's health unchanged"), PreyHP, 55.f);

    CaregiverTransform.SetLocation(Between);
    PreyHP = 55.f;
    Hunt.AttackContact = 30.; Hunt.TargetId = 2;
    FEcoCombatTestAccess::Predation(*S, 30.);
    TestEqual(TEXT("The caregiver intercepts when both parents can block"), HunterHP, 10.f);
    TestEqual(TEXT("Only the caregiver spends stamina when both parents can block"), Caregiver.Stamina, .85f);
    TestEqual(TEXT("Interception keeps the young's health unchanged"), PreyHP, 55.f);

    auto& Patch = S->FaunaHabitatPatches.AddDefaulted_GetRef();
    Patch.RegionId = TEXT("Meadow");
    Patch.ShelteredSpecies = Names[1];
    Patch.Center = PreyTransform.GetLocation();
    Patch.ShelterRadius = 25.f;
    Patch.EntranceRadius = 7.f;
    TestTrue(TEXT("The original phase retains contact"), FEcoCombatTestAccess::CanHunt(*S, EM, Entities[0], Entities[1], 24.));
    S->FaunaHabitatStage = 1;
    TestFalse(TEXT("A larger hunter cannot make contact inside the narrow shelter"),
        FEcoCombatTestAccess::CanHunt(*S, EM, Entities[0], Entities[1], 24.));
    PreyTransform.SetLocation(FVector(95, 0, 0));
    TestTrue(TEXT("Shelter does not protect prey outside its footprint"),
        FEcoCombatTestAccess::CanHunt(*S, EM, Entities[0], Entities[1], 24.));
    float Stock = 3.5f;
    TestEqual(TEXT("A patch credits only the requested energy"), Patch.TakeMeal(Stock, 1.f), 1.f);
    TestEqual(TEXT("The next eater receives only the remaining stock"), Patch.TakeMeal(Stock, 8.f), 2.5f);
    TestEqual(TEXT("An exhausted patch cannot issue another meal"), Patch.TakeMeal(Stock, 8.f), 0.f);
    EcoLifeV3::FMealCycle Cycle;
    Cycle.Update(.65, 1., .7, .9, 4.);
    TestTrue(TEXT("Hunger starts a meal"), Cycle.bSeeking);
    Cycle.Update(.8, 2., .7, .9, 4.);
    TestTrue(TEXT("Eating continues above the start threshold"), Cycle.bSeeking);
    Cycle.Update(.91, 3., .7, .9, 4.);
    TestTrue(TEXT("A completed meal starts a bounded rest"), Cycle.IsResting(3.));
    Cycle.Update(.69, 4., .7, .9, 4.);
    TestTrue(TEXT("Minor energy loss does not interrupt rest"), Cycle.IsResting(4.));
    Cycle.Update(.24, 5., .7, .9, 4.);
    TestTrue(TEXT("Critical hunger interrupts rest"), Cycle.bSeeking);
    FEcoFaunaCarcass Kill;
    Kill.KillerId = 1;
    Kill.OpenAt = 2.;
    Kill.ExclusiveUntil = 4.;
    Kill.ExpiresAt = 12.;
    Kill.Remaining = 10.f;
    TestTrue(TEXT("A hunter can keep approaching its kill when the sharing window opens"),
        Kill.RetainsKillerTarget(1, 5., true));
    TestTrue(TEXT("Keeping the target does not extend the exclusive reservation"), Kill.CanApproach(2, 5.));
    TestFalse(TEXT("A different animal does not own the kill"), Kill.RetainsKillerTarget(2, 5., true));
    TestFalse(TEXT("An expired kill cannot retain the target"), Kill.RetainsKillerTarget(1, 12., true));
    const FEcoFaunaPersistenceSettings Persistence;
    TestTrue(TEXT("Local encounters increase expected hunting value"),
        EcoFaunaFeeding::EncounterWeight(1, Persistence) < EcoFaunaFeeding::EncounterWeight(4, Persistence));
    FEcoFaunaFragment Forager;
    Forager.RecordForageIntake(FVector(200., 20., 0.), 10., 20.f, Persistence.ForageMemorySeconds);
    TestEqual(TEXT("Feeding records only the credited intake"), Forager.RecentForageIntake(10., Persistence.ForageMemorySeconds), 20.f);
    TestTrue(TEXT("Old intake loses relevance"), Forager.RecentForageIntake(100., Persistence.ForageMemorySeconds) < 8.f);
    TestEqual(TEXT("Stored surplus supports a well-fed parent between meals"),
        EcoFaunaFeeding::BreedingReserve(90., 100., 0.), 20.);
    TestEqual(TEXT("A parent at the minimum has only recent intake to forecast"),
        EcoFaunaFeeding::BreedingReserve(70., 100., 4.), 4.);
    TestTrue(TEXT("Nearby safe carrion beats costly hunt"), EcoFaunaFeeding::Value(12., .5) > EcoFaunaFeeding::Value(15., 2., 5.));
    TestTrue(TEXT("Nearby viable prey beats distant depleted carrion"), EcoFaunaFeeding::Value(15., .5, 2.) > EcoFaunaFeeding::Value(4., 4.));
    return true;
}
#endif

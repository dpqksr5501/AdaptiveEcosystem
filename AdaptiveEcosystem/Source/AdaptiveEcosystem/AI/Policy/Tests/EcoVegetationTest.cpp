#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/EcoWorldV3.h"
#include "AI/Policy/EcoLifeHistoryV3.h"
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "World/EcoVegetationField.h"
#include "World/EcoNaturalHabitatProfile.h"
#include "Components/BoxComponent.h"
#include "World/EcoRegionEnvironmentAdapter.h"
#include "World/EcologyRegion.h"
#include "Engine/StaticMeshActor.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoGrassProfileIsolation,
    "AdaptiveEcosystem.Vegetation.ProfileAndGridPresentationIsolation", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoGrassProfileIsolation::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld World;
    auto* Field = World.World->SpawnActor<AEcoVegetationField>();
    auto* GridField = World.World->SpawnActor<AEcoVegetationField>();
    auto* Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!Field || !GridField || !Mesh) return false;
    Field->Plants->SetStaticMesh(Mesh);
    Field->DryResidue->SetStaticMesh(Mesh);
    Field->Tracks->SetStaticMesh(Mesh);
    Field->NaturalProfile = NewObject<UEcoNaturalHabitatProfile>(Field);
    Field->RegionId = TEXT("ProfileIsolation");
    Field->VisualCellSizeCm = 400;
    auto& Cell = Field->Cells.AddDefaulted_GetRef();
    Cell.Food = FEcoVegetationVisualCell::EncodeAmount(.25);
    Cell.Capacity = FEcoVegetationVisualCell::EncodeAmount(.5);
    Cell.FoodFraction = 128;
    Cell.SiteFood[0] = 128;
    auto& Site = Field->GroundSites.AddDefaulted_GetRef();
    Site.Position = FVector(200,200,0);
    Site.Normal = FVector::UpVector;
    Field->MovementMarks.AddDefaulted();
    Field->OnRep_Cells();
    TestEqual(TEXT("Profile renderer retains its ground-verified site"), Field->Plants->GetInstanceCount(), 1);
    TestEqual(TEXT("Movement evidence survives site rendering"), Field->Tracks->GetInstanceCount(), 1);
    Field->RefreshPlants(FVector(200,200,500), 0);
    TestEqual(TEXT("Grid refresh cannot evict profile instances"), Field->Plants->GetInstanceCount(), 1);
    TestTrue(TEXT("Profile mode does not create a second grid instance cache"), Field->RenderedPlants.IsEmpty());
    Cell.SiteFood[0] = 0;
    Field->OnRep_Cells();
    TestEqual(TEXT("Local browse removes its site while cell biomass stays positive"), Field->Plants->GetInstanceCount(), 0);
    Cell.Food = 0; Cell.FoodFraction = 0; Cell.Stress = 200;
    Field->OnRep_Cells();
    TestEqual(TEXT("Non-edible dry residue remains visible"), Field->DryResidue->GetInstanceCount(), 1);
    GridField->Plants->SetStaticMesh(Mesh);
    GridField->Plants->AddInstance(FTransform::Identity);
    GridField->OnRep_Cells();
    TestEqual(TEXT("Profile callback cannot clear generic grid instances"), GridField->Plants->GetInstanceCount(), 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoGrassAmountEncoding, "AdaptiveEcosystem.Vegetation.GrassAmountEncoding", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoGrassAmountEncoding::RunTest(const FString&)
{
    using FCell = FEcoVegetationVisualCell;
    TestEqual(TEXT("Zero remains depleted"), FCell::EncodeAmount(0), uint16(0));
    TestEqual(TEXT("Negative amount is hidden"), FCell::EncodeAmount(-.1), uint16(0));
    TestEqual(TEXT("NaN is hidden"), FCell::EncodeAmount(std::numeric_limits<double>::quiet_NaN()), uint16(0));
    TestEqual(TEXT("Infinite amount cannot appear fully grown"), FCell::EncodeAmount(std::numeric_limits<double>::infinity()), uint16(0));
    TestEqual(TEXT("Positive sub-quantum food stays distinct from zero"), FCell::EncodeAmount(1.e-12), uint16(1));
    TestEqual(TEXT("Full native patch is exactly represented"), FCell::EncodeAmount(1), uint16(65535));
    TestEqual(TEXT("Display saturation preserves the bounded wire format"), FCell::EncodeAmount(2), uint16(65535));

    FCell Cell;
    Cell.Capacity = FCell::EncodeAmount(.5);
    TestFalse(TEXT("Depleted food renders no candidates"), Cell.HasRenderableFood());
    Cell.Food = FCell::EncodeAmount(1.e-12);
    TestTrue(TEXT("Positive tiny food permits a candidate"), Cell.HasRenderableFood());
    Cell.Capacity = 0;
    TestFalse(TEXT("Zero-capacity cell cannot render food"), Cell.HasRenderableFood());

    uint16 Previous = 0;
    for (int32 Index = 0; Index <= 4096; ++Index)
    {
        const double Amount = Index / 4096.;
        const uint16 Encoded = FCell::EncodeAmount(Amount);
        if (Encoded < Previous || FMath::Abs(Encoded / 65535. - Amount) > 1. / 65535.)
        {
            AddError(TEXT("Visual encoding must be monotonic and remain within one quantum"));
            return false;
        }
        if (FCell::EncodeAmount(Amount * .5) > Encoded)
        {
            AddError(TEXT("Food below capacity cannot exceed its encoded capacity"));
            return false;
        }
        Previous = Encoded;
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoGrassGroundRefreshFairness, "AdaptiveEcosystem.Vegetation.GrassGroundRefreshFairness", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoGrassGroundRefreshFairness::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld World;
    auto* Field = World.World->SpawnActor<AEcoVegetationField>();
    if (!TestNotNull(TEXT("Existing Field owns refresh scheduling"), Field)) return false;
    constexpr int32 Count = 1200;
    constexpr int32 Budget = 24;
    for (int32 Index = Count - 1; Index >= 0; --Index)
        Field->RenderedPlants.Add(Index).NextGroundCheck = 0;

    TestTrue(TEXT("Zero budget performs no ground work"), Field->GetDueGroundCandidates(0, 0).IsEmpty());
    TSet<int64> Visited;
    for (int32 Frame = 0; Frame < Count / Budget; ++Frame)
    {
        const double Now = Frame * .25;
        const auto Due = Field->GetDueGroundCandidates(Now, Budget);
        if (!TestEqual(TEXT("Refresh work stays within its reserved budget"), Due.Num(), Budget)) return false;
        for (int64 Key : Due)
        {
            if (Visited.Contains(Key))
            {
                AddError(TEXT("A previously checked candidate displaced an older waiting candidate"));
                return false;
            }
            Visited.Add(Key);
            // Both a missing streamed surface and a successful check schedule a retry.
            Field->RenderedPlants.FindChecked(Key).NextGroundCheck = Now + (Key % 2 ? 1. : 5.);
        }
    }
    TestEqual(TEXT("Every candidate, including the tail, receives its first check"), Visited.Num(), Count);
    Field->RenderedPlants.Reset();
    Field->RenderedPlants.Add(10).NextGroundCheck = 30;
    Field->RenderedPlants.Add(20).NextGroundCheck = 5;
    Field->RenderedPlants.Add(5).NextGroundCheck = 5;
    const auto Due = Field->GetDueGroundCandidates(10, 24);
    if (!TestEqual(TEXT("Future checks remain deferred"), Due.Num(), 2)) return false;
    TestEqual(TEXT("Equal deadlines use stable candidate order"), Due[0], int64(5));
    TestEqual(TEXT("Later equal-deadline candidate follows"), Due[1], int64(20));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoGrassVisualLifecycle, "AdaptiveEcosystem.Vegetation.GrassVisualLifecycle", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoGrassVisualLifecycle::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld World;
    auto* Field = World.World->SpawnActor<AEcoVegetationField>();
    auto* Floor = World.World->SpawnActor<AStaticMeshActor>();
    auto* Mesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    if (!Field || !Floor || !Mesh)
    {
        AddError(TEXT("Existing Field, floor fixture and engine mesh are required"));
        return false;
    }
    auto* Surface = Floor->GetStaticMeshComponent();
    Surface->SetMobility(EComponentMobility::Movable);
    Surface->SetStaticMesh(Mesh);
    Floor->SetActorScale3D(FVector(20, 20, 1));
    Floor->SetActorLocation(FVector(200, 200, -50));
    Surface->SetCollisionProfileName(TEXT("BlockAll"));
    FHitResult InitialGround;
    if (!TestTrue(TEXT("Actual collision floor is ready"),
        World.World->LineTraceSingleByChannel(InitialGround, FVector(200,200,400), FVector(200,200,-400), ECC_WorldStatic)))
        return false;

    Field->Plants->SetStaticMesh(Mesh);
    Field->RegionId = TEXT("GrassLifecycleFixture");
    Field->ConfigureGrid(400, 400, 23);
    Field->CandidatesPerCell = 9;
    Field->CandidateTracesPerUpdate = 128;
    auto& Cell = Field->VisualGrid.Cells.AddDefaulted_GetRef();
    Cell.Cell = 0;
    Cell.Position = FVector_NetQuantize10(FVector(200,200,0));
    Cell.Food = FEcoVegetationVisualCell::EncodeAmount(1);
    Cell.Capacity = FEcoVegetationVisualCell::EncodeAmount(1);
    const FVector Near(200,200,500);
    Field->RefreshPlants(Near, 0);
    if (!TestEqual(TEXT("Full cell creates actual ISM candidates"), Field->Plants->GetInstanceCount(), 9))
        return false;

    TMap<int64, FVector> OriginalGround;
    TMap<int64, FPrimitiveInstanceId> OriginalIds;
    for (const auto& Entry : Field->RenderedPlants)
    {
        const FVector Ground = Entry.Value.GroundPosition;
        TestTrue(TEXT("Generated candidate stays in its food cell"),
            Ground.X >= 0 && Ground.X <= 400 && Ground.Y >= 0 && Ground.Y <= 400);
        OriginalGround.Add(Entry.Key, Ground);
        OriginalIds.Add(Entry.Key, Entry.Value.Instance);
    }
    const auto CheckGroundPositions = [this, Field, &OriginalGround]()
    {
        for (const auto& Entry : Field->RenderedPlants)
        {
            const auto* Expected = OriginalGround.Find(Entry.Key);
            if (!Expected || !Entry.Value.bGroundReady || !Entry.Value.GroundPosition.Equals(*Expected, .01))
            {
                AddError(TEXT("A retained or recreated candidate changed its seeded ground position"));
                return false;
            }
        }
        return true;
    };

    Field->RefreshPlants(Near, .25);
    for (const auto& Entry : Field->RenderedPlants)
        TestTrue(TEXT("Unchanged candidate keeps its actual ISM ID"), Entry.Value.Instance == OriginalIds.FindChecked(Entry.Key));
    Cell.Food = FEcoVegetationVisualCell::EncodeAmount(.3);
    Field->RefreshPlants(Near, .5);
    TestEqual(TEXT("Reduced food changes actual candidate density"), Field->Plants->GetInstanceCount(), 3);
    for (const auto& Entry : Field->RenderedPlants)
        TestTrue(TEXT("Surviving candidate keeps its ISM ID"), Entry.Value.Instance == OriginalIds.FindChecked(Entry.Key));
    if (!CheckGroundPositions()) return false;

    Cell.Food = 0;
    Field->RefreshPlants(Near, .75);
    TestEqual(TEXT("Depletion removes all actual ISM instances"), Field->Plants->GetInstanceCount(), 0);
    TestTrue(TEXT("Depleted candidates leave no stale mapping"), Field->RenderedPlants.IsEmpty());
    Cell.Food = FEcoVegetationVisualCell::EncodeAmount(1.e-12);
    Field->RefreshPlants(Near, 1);
    TestEqual(TEXT("Positive tiny food renders one candidate"), Field->Plants->GetInstanceCount(), 1);
    if (!CheckGroundPositions()) return false;
    Cell.Food = Cell.Capacity;
    Field->RefreshPlants(Near, 1.25);
    TestEqual(TEXT("Recovered food returns full density"), Field->Plants->GetInstanceCount(), 9);
    if (!CheckGroundPositions()) return false;

    Field->RefreshPlants(FVector(1000000,200,500), 1.5);
    TestEqual(TEXT("Leaving visual range removes instances"), Field->Plants->GetInstanceCount(), 0);
    Field->RefreshPlants(Near, 2);
    TestEqual(TEXT("Reentry regenerates candidates"), Field->Plants->GetInstanceCount(), 9);
    if (!CheckGroundPositions()) return false;

    Surface->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Field->RefreshPlants(Near, 10);
    TestEqual(TEXT("Missing ground removes actual instances"), Field->Plants->GetInstanceCount(), 0);
    Surface->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Field->RefreshPlants(Near, 11.25);
    TestEqual(TEXT("Restored ground permits retry and display"), Field->Plants->GetInstanceCount(), 9);
    if (!CheckGroundPositions()) return false;

    Cell.Position = FVector_NetQuantize10(FVector(200,200,50));
    Field->RefreshPlants(Near, 11.5);
    TestEqual(TEXT("Changed anchor hides old surface instances before retry"), Field->Plants->GetInstanceCount(), 0);
    Field->RefreshPlants(Near, 11.75);
    TestEqual(TEXT("Changed anchor completes bounded ground retry"), Field->Plants->GetInstanceCount(), 9);
    return CheckGroundPositions();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoPairedBrowseRecovery,
    "AdaptiveEcosystem.Vegetation.PairedBrowseRecovery", EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoPairedBrowseRecovery::RunTest(const FString&)
{
    using namespace EcoVegetationV3;
    FConfig Config;Config.bEnabled=true;Config.bHabitatDynamics=true;
    FHabitat Habitat;Habitat.bNatural=true;
    FCell Control, Browsed;
    for(int Bite=0;Bite<16;++Bite)Browsed.RecordBrowse(.15,1);
    // Match the initial biomass and visible cohort so the comparison isolates prior browse pressure.
    Control.Development=Browsed.Development=.6;
    FOutcome A{.35},B{.35};
    double LargestGap=0;
    AddInfo(TEXT("PairedBrowse t=0 control=0.350000 browsed=0.350000"));
    for(int Step=1;Step<=900;++Step)
    {
        const FWeather Weather{Step>150&&Step<=450?.42:0.,18.,.8};
        const double BeforeA=A.Food,BeforeB=B.Food;
        A=Advance(Config,Weather,Habitat,Control,BeforeA,1,.006,EcoRepertoireV3::kStepSeconds);
        B=Advance(Config,Weather,Habitat,Browsed,BeforeB,1,.006,EcoRepertoireV3::kStepSeconds);
        if(!FMath::IsNearlyEqual(BeforeA+A.Growth-A.Loss,A.Food,1e-10)
            ||!FMath::IsNearlyEqual(BeforeB+B.Growth-B.Loss,B.Food,1e-10))
        {
            AddError(TEXT("A paired cell lost conservation"));return false;
        }
        LargestGap=FMath::Max(LargestGap,A.Food-B.Food);
        if(Step==150||Step==450||Step==900)
            AddInfo(FString::Printf(TEXT("PairedBrowse t=%.0f control=%.6f browsed=%.6f pressure=%.6f"),
                Step*EcoRepertoireV3::kStepSeconds,A.Food,B.Food,Browsed.BrowsePressure));
    }
    TestTrue(TEXT("Prior pressure alone delays recovery under the same rainfall"),LargestGap>.04&&B.Food<A.Food);
    TestTrue(TEXT("The browsed plot still recovers"),B.Food>.35);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoHabitatDynamics,
    "AdaptiveEcosystem.Vegetation.HabitatDynamics", EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoHabitatDynamics::RunTest(const FString&)
{
    using namespace EcoVegetationV3;
    FConfig Config;Config.bEnabled=true;Config.bHabitatDynamics=true;
    Config.Evaporation=Config.Drainage=Config.Uptake=0;
    FHabitat Grass;Grass.bNatural=true;
    FHabitat Shrub=Grass;Shrub.Plant=EPlant::Shrub;
    const FWeather Mild{0,18,1};
    constexpr double Dt=EcoRepertoireV3::kStepSeconds;
    FCell Control, Grazed, BrowsedShrub;
    for(int Bite=0;Bite<16;++Bite){
        Grazed.RecordBrowse(.2,1);
        BrowsedShrub.RecordBrowse(.2,1);
    }
    auto Reference=Advance(Config,Mild,Grass,Control,.35,1,.02,Dt);
    auto Pressured=Advance(Config,Mild,Grass,Grazed,.35,1,.02,Dt);
    TestTrue(TEXT("Repeated actual intake delays recovery at equal biomass and weather"),
        Grazed.BrowsePressure>.65 && Grazed.Development<Control.Development && Pressured.Growth<Reference.Growth);
    TestTrue(TEXT("Chewed plants retain a visible browse trace longer"),BrowseTraceSeconds(Grazed)>BrowseTraceSeconds(Control));
    double GrassFood=Pressured.Food,ShrubFood=Pressured.Food;
    for(int Step=0;Step<1500;++Step){
        GrassFood=Advance(Config,Mild,Grass,Grazed,GrassFood,1,.02,Dt).Food;
        ShrubFood=Advance(Config,Mild,Shrub,BrowsedShrub,ShrubFood,1,.02,Dt).Food;
    }
    TestTrue(TEXT("Grass recovers sooner than repeatedly browsed shrubs"),
        Grazed.BrowsePressure<BrowsedShrub.BrowsePressure && GrassFood>.35);

    FCell Low, Edge;FHabitat Basin=Grass;Basin.Drainage=.05;
    FHabitat Slope=Grass;Slope.Drainage=.65;
    for(int Step=0;Step<300;++Step){
        Advance(Config,{.65,18,1},Basin,Low,.5,1,0,Dt);
        Advance(Config,{.65,18,1},Slope,Edge,.5,1,0,Dt);
    }
    const double Wet=Low.SurfaceWater;
    Advance(Config,Mild,Basin,Low,.5,1,0,Dt);
    TestTrue(TEXT("Rain pools on retentive ground and persists after rain stops"),
        Edge.SurfaceWater==0 && Low.SurfaceWater>.3 && Low.SurfaceWater<Wet);

    FCell Fresh, Cured;Fresh.FreshFraction=1;Cured.FreshFraction=0;Cured.Stress=.8;
    TestTrue(TEXT("Equal eaten biomass can produce different energy"),
        EcoRepertoireV3::EnergyAfterIntake(.4,.2*Fresh.NutritionMultiplier())
        > EcoRepertoireV3::EnergyAfterIntake(.4,.2*Cured.NutritionMultiplier()));
    TestTrue(TEXT("Season is periodic and reaches distinct thermal conditions"),
        SeasonalTemperatureOffset(240)>5 && SeasonalTemperatureOffset(720)<-5
        && FMath::IsNearlyEqual(SeasonalTemperatureOffset(240),SeasonalTemperatureOffset(1200),1e-9));

    FCell Clearing;TestTrue(TEXT("Queue clearing"),Clearing.QueueDisturbance(.6));
    TestFalse(TEXT("Reject duplicate before commit"),Clearing.QueueDisturbance(.6));
    const auto Cleared=Advance(Config,Mild,Shrub,Clearing,.8,1,.02,Dt);
    const auto Next=Advance(Config,Mild,Shrub,Clearing,Cleared.Food,1,.02,Dt);
    TestTrue(TEXT("One clearing enters explicit loss, with no repeat charge"),
        Cleared.Loss>=.48 && Next.Loss<.01 && Clearing.PendingDisturbance==0
        && Clearing.Development<.5 && FMath::IsNearlyEqual(.8-Cleared.Loss+Cleared.Growth,Cleared.Food,1e-9));

    EcoLifeV3::FMemory Witness, Unaware;
    Witness.RememberHunt(40,20,30);Witness.RememberHunt(40,20,45);
    TestTrue(TEXT("Only witnesses avoid the site, and they can return after decay"),
        Witness.HuntRisk(40,20,45)>.42 && Witness.HuntRisk(65,20,45)==0
        && Witness.HuntRisk(40,20,270)<.2 && Unaware.HuntRisk(40,20,45)==0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoVegetationWeather, "AdaptiveEcosystem.Vegetation.WaterBudgetAndPlantTolerance", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoVegetationWeather::RunTest(const FString&)
{
    using namespace EcoVegetationV3;
    FConfig C; C.bEnabled = true; FCell Wet, Dry; FHabitat H;
    double WetFood = .1, DryFood = .1, WG = 0, WL = 0, DG = 0, DL = 0;
    for (int K = 0; K < 4500; ++K)
    {
        const auto A = Advance(C, {0.5,20,1}, H, Wet, WetFood, 1, .026, 2.0/15);
        const auto B = Advance(C, {0,30,1}, H, Dry, DryFood, 1, .026, 2.0/15);
        WetFood = A.Food; WG += A.Growth; WL += A.Loss;
        DryFood = B.Food; DG += B.Growth; DL += B.Loss;
    }
    TestTrue(TEXT("Rain accumulates soil moisture, dry heat depletes it"), Wet.Moisture > Dry.Moisture + .3);
    TestTrue(TEXT("Rain produces more retained food with the same starting balance"), WetFood > DryFood + .1);
    TestTrue(TEXT("Wet conservation"), FMath::IsNearlyEqual(.1 + WG - WL, WetFood, 1.e-10));
    TestTrue(TEXT("Dry conservation includes explicit losses"), FMath::IsNearlyEqual(.1 + DG - DL, DryFood, 1.e-10) && DL > 0);
    FCell Grass{.8,1}, Riparian{.8,1}; FHabitat Flood; Flood.Flood = 1;
    const auto G = Advance(C, {1,20,1}, Flood, Grass, .5, 1, .026, 2.0/15);
    Flood.Plant = EPlant::Riparian;
    const auto R = Advance(C, {1,20,1}, Flood, Riparian, .5, 1, .026, 2.0/15);
    TestTrue(TEXT("Flood is not an unlimited growth bonus; plants differ"), R.Growth > G.Growth && G.Loss > 0);
    FCell Empty; const auto Recovery = Advance(C, {.5,20,1}, H, Empty, 0, 1, .026, 2.0/15);
    TestTrue(TEXT("Grazed-to-zero cells can recover"), Recovery.Food > 0);
    const auto Before = Empty;
    const auto Bad = Advance(C, {std::numeric_limits<double>::quiet_NaN(),20,1}, H, Empty, .5, 1, .026, 2.0/15);
    TestTrue(TEXT("Malformed weather cannot corrupt state"), Bad.Food == .5 && Empty.Moisture == Before.Moisture);
    const auto Hitch = Advance(C, {.5,20,1}, H, Empty, .5, 1, .026, 1000);
    TestTrue(TEXT("No unbounded offline catch-up"), Hitch.Food == .5 && Empty.Moisture == Before.Moisture);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoVegetationLedger, "AdaptiveEcosystem.Vegetation.EnvironmentReceiptAndReplay", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoVegetationLedger::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W; auto* E = W.World->GetSubsystem<UEcologySimulationSubsystem>();
    FRegionEcologyState S; S.RegionId = TEXT("Soil");
    if (!TestTrue(TEXT("Authority region"), E->RegisterRegionState(S))) return false;
    TestTrue(TEXT("Register single balance"), E->RegisterSpatialFood(S.RegionId, 10, 8));
    TestTrue(TEXT("Consumption, growth and environmental loss have separate terms"), E->CommitSpatialFood(S.RegionId, 1, 8, 2, 1, 4, 3));
    TestFalse(TEXT("Duplicate receipt rejected"), E->CommitSpatialFood(S.RegionId, 1, 8, 2, 1, 4, 3));
    TestFalse(TEXT("Stale before rejected"), E->CommitSpatialFood(S.RegionId, 2, 8, 0, 0, 8));
    TestFalse(TEXT("Negative loss rejected"), E->CommitSpatialFood(S.RegionId, 2, 4, 0, 0, 5, -1));
    TestFalse(TEXT("Growth cannot conceal overdraft before regrowth"), E->CommitSpatialFood(S.RegionId, 2, 4, 3, 5, 3, 3));
    TestFalse(TEXT("NaN loss rejected"), E->CommitSpatialFood(S.RegionId, 2, 4, 0, 0, 4, std::numeric_limits<double>::quiet_NaN()));
    TestTrue(TEXT("Legacy six-argument callers still work"), E->CommitSpatialFood(S.RegionId, 2, 4, 1, .5, 3.5));
    E->GetRegionState(S.RegionId, S); TestEqual(TEXT("Actual authoritative balance"), S.FoodAmount, 3.5f);
    FEcoSpatialFoodAudit Audit; TestTrue(TEXT("Audit is available"), E->GetSpatialFoodAudit(S.RegionId, Audit));
    TestEqual(TEXT("Environment loss stays separate from animal consumption"), Audit.EnvironmentLost, 3.0);
    TestEqual(TEXT("Consumption accumulates once"), Audit.Consumed, 3.0);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoVegetationClosedLoop, "AdaptiveEcosystem.Vegetation.NativeFeedingAndLedger", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoVegetationClosedLoop::RunTest(const FString&)
{
    EcoWorldV3::FWorldConfig C; C.NumHerbivores = 16; C.NumStalkers = C.NumChasers = C.NumRanged = 0; C.bPlayerProxy = false; C.bRespawnDead = false;
    C.Vegetation.bEnabled = true;
    EcoWorldV3::FReferenceWorld R; R.Init(C);
    EcoTest::FScopedTestWorld W; auto* E = W.World->GetSubsystem<UEcologySimulationSubsystem>();
    FRegionEcologyState S; S.RegionId = TEXT("FeedingSoil"); E->RegisterRegionState(S);
    const double Initial = R.World.Food.Total(); E->RegisterSpatialFood(S.RegionId, Initial, Initial);
    for (int K = 0; K < 600; ++K)
    {
        auto& G = R.World.Food; G.VegetationWeather = {K < 300 ? .5 : 0.,20,1};
        const double Before = G.Total(), Ate = R.World.Stats.FoodEaten, Loss = G.EnvironmentLost, Growth = G.VegetationGrown;
        R.StepOnce();
        if (!TestTrue(TEXT("Every native step closes the real food transaction"), E->CommitSpatialFood(S.RegionId, K+1,
            Before, R.World.Stats.FoodEaten-Ate, G.VegetationGrown-Growth, G.Total(), G.EnvironmentLost-Loss))) return false;
    }
    E->GetRegionState(S.RegionId, S);
    TestTrue(TEXT("Native herbivores actually consumed food"), R.World.Stats.FoodEaten > 0);
    TestTrue(TEXT("Mass-independent authority amount matches native cells"), FMath::IsNearlyEqual(double(S.FoodAmount), R.World.Food.Total(), .001));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoVegetationOff, "AdaptiveEcosystem.Vegetation.OffKeepsNativeTrajectory", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoVegetationOff::RunTest(const FString&)
{
    EcoWorldV3::FWorldConfig C; C.NumHerbivores = 8; C.NumStalkers = 1; C.NumChasers = C.NumRanged = 0; C.bPlayerProxy = false;
    EcoWorldV3::FReferenceWorld A, B; A.Init(C); C.Vegetation.Infiltration = .5; B.Init(C);
    for (int K = 0; K < 300; ++K)
    {
        B.World.Food.VegetationWeather = {1,-50,0}; A.StepOnce(); B.StepOnce();
        if (A.World.Food.Food != B.World.Food.Food) { AddError(TEXT("OFF changed native food trajectory")); return false; }
    }
    TestEqual(TEXT("No soil allocation when OFF"), int32(A.World.Food.VegetationCells.size()), 0);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoVegetationAuthoring, "AdaptiveEcosystem.Vegetation.RejectUnsupportedHabitat", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoVegetationAuthoring::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W; auto* H = W.World->SpawnActor<AEcoVegetationHabitat>();
    if (!TestNotNull(TEXT("Actual authored input actor"), H)) return false;
    TestTrue(TEXT("Default ground input valid"), H->IsValidHabitat());
    H->Plant = 256; TestFalse(TEXT("Out-of-range int cannot wrap to the valid byte enum"), H->IsValidHabitat());
    H->Plant = 1; H->bConnectedFreshWater = true; H->WaterSurfaceZ = std::numeric_limits<float>::quiet_NaN();
    TestFalse(TEXT("Connected water requires a known finite level"), H->IsValidHabitat());
    H->WaterSurfaceZ = 0; H->MaxSupplyRiseCm = 0;
    TestFalse(TEXT("Invalid supply geometry is rejected, never silently treated as disconnected"), H->IsValidHabitat());
    H->MaxSupplyRiseCm = 100; TestTrue(TEXT("Supported connected riparian input"), H->IsValidHabitat());
    H->Shade = 1.5; TestFalse(TEXT("Unsupported shade range"), H->IsValidHabitat());
    H->Bounds->SetBoxExtent(FVector(100)); H->SetActorRotation(FRotator(0,45,0));
    TestTrue(TEXT("Rotated habitat contains its actual center"), H->ContainsGround(H->GetActorLocation()));
    TestFalse(TEXT("AABB corner outside rotated habitat cannot receive its water"), H->ContainsGround(H->GetActorLocation()+FVector(135,135,0)));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoVegetationClimate, "AdaptiveEcosystem.Vegetation.AuthoredClimateClock", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoVegetationClimate::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld W; auto* A=W.World->SpawnActor<AEcoRegionEnvironmentAdapter>(); float Rain=-1;
    if (!TestNotNull(TEXT("Actual World input producer"),A)) return false;
    TestFalse(TEXT("Existing maps do not cycle by default"),A->EvaluateCycleRainfall(0,Rain));
    A->bCycleRainfall=true; A->RainCycleSeconds=100;
    TestTrue(TEXT("Dry phase uses ecology time"),A->EvaluateCycleRainfall(20,Rain)&&Rain==0);
    TestTrue(TEXT("Smooth transition"),A->EvaluateCycleRainfall(45,Rain)&&FMath::IsNearlyEqual(Rain,.325f,.0001f));
    TestTrue(TEXT("Wet phase"),A->EvaluateCycleRainfall(60,Rain)&&Rain==A->WetRainfall);
    TestTrue(TEXT("Cycle wrap does not accumulate frame dt"),A->EvaluateCycleRainfall(100,Rain)&&Rain==0);
    A->RainPhaseOffsetSeconds=50;TestTrue(TEXT("Regions can have independent authored phases"),A->EvaluateCycleRainfall(10,Rain)&&Rain==A->WetRainfall);
    A->bApplyAuthoredWeather=true;TestFalse(TEXT("Two producers cannot overwrite the same input"),A->EvaluateCycleRainfall(60,Rain));
    A->bApplyAuthoredWeather=false;A->RainCycleSeconds=0;TestFalse(TEXT("Invalid period rejected"),A->EvaluateCycleRainfall(60,Rain));
    return true;
}
#if !UE_BUILD_SHIPPING
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoGrassDebugClimate, "AdaptiveEcosystem.Vegetation.GrassDebugClimate", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoGrassDebugClimate::RunTest(const FString&)
{
    EcoTest::FScopedTestWorld World;
    auto* Region = World.World->SpawnActor<AEcologyRegion>();
    auto* Neighbor = World.World->SpawnActor<AEcologyRegion>();
    if (!Region || !Neighbor) return false;

    FRegionEnvironmentState Authored;
    Authored.Rainfall = .25f;
    Authored.Temperature = 18.f;
    Region->SetEnvironmentState(Authored);
    Neighbor->SetEnvironmentState(Authored);
    TestTrue(TEXT("Authority accepts valid climate"), Region->SetGrassTestClimate(0, 30));
    TestFalse(TEXT("Out-of-range climate rejected"), Region->SetGrassTestClimate(1.1f, 20));
    TestFalse(TEXT("Nonfinite climate rejected"), Region->SetGrassTestClimate(0, std::numeric_limits<float>::quiet_NaN()));

    Authored.Rainfall = .65f;
    Region->SetEnvironmentState(Authored);
    const auto Effective = Region->GetEffectiveEnvironmentState();
    TestEqual(TEXT("Automatic producer does not displace effective rain"), Effective.Rainfall, 0.f);
    TestEqual(TEXT("Temperature override"), Effective.Temperature, 30.f);
    TestEqual(TEXT("Other region unaffected"), Neighbor->GetEffectiveEnvironmentState().Rainfall, .25f);

    Region->ClearGrassTestClimate();
    const auto Resumed = Region->GetEffectiveEnvironmentState();
    TestEqual(TEXT("Resume uses latest automatic value"), Resumed.Rainfall, .65f);
    TestEqual(TEXT("Resume restores normal temperature"), Resumed.Temperature, 18.f);
    return true;
}
#endif
#endif

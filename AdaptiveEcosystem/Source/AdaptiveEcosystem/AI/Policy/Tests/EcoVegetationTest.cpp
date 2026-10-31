#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/EcoWorldV3.h"
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "World/EcoVegetationField.h"
#include "Components/BoxComponent.h"
#include "World/EcoRegionEnvironmentAdapter.h"
#include <limits>

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
#endif

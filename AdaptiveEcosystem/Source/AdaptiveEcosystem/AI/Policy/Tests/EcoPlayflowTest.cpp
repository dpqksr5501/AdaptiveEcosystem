#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/EcoLifeLocomotion.h"
#include "AI/Policy/EcoVegetationExpansion.h"
#include "AI/Policy/EcoV3WeatherPresenter.h"
#include "World/EcoWorldClockSubsystem.h"
#include "Creature/Runtime/EcoEcosystemArchive.h"
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeContact,"AdaptiveEcosystem.Playflow.ContactAndBoundaryIntent",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeContact::RunTest(const FString&)
{
    using namespace EcoLifeMotion;
    const auto Passing=PassingAvoidance({-1,0},{1,0}),Opposite=PassingAvoidance({1,0},{-1,0});
    TestTrue(TEXT("Head-on moving bodies choose opposite passing sides without reversing escape"),Passing.X==0&&Passing.Y>0&&Opposite.X==0&&Opposite.Y<0);
    TestFalse(TEXT("Swept contact cannot tunnel through a stationary body"),AllowsMotion({0,0},{2,0},{1,0},.6));
    TestTrue(TEXT("An existing overlap may move outward"),AllowsMotion({0,0},{-.2,0},{.1,0},.6));
    TestFalse(TEXT("An existing overlap cannot deepen"),AllowsMotion({0,0},{.05,0},{.1,0},.6));
    const auto A=Separation({60,0},{60,0},1,151,153),B=Separation({60,0},{60,0},1,153,151);
    TestTrue(TEXT("Exact coincidence has finite opposite escape directions"),std::hypot(A.X,A.Y)>.99&&std::abs(A.X+B.X)+std::abs(A.Y+B.Y)<1.e-12);
    const auto Far=Separation({0,0},{3,0},1,1,2);TestTrue(TEXT("Distant neighbors do not perturb motion"),Far.X==0&&Far.Y==0);
    const auto Edge=BoundaryVelocity({60,0},{.3,-.3},60,1.5);
    TestTrue(TEXT("An outward corner intent turns inward without speeding up"),Edge.X<0&&Edge.Y>0&&std::abs(std::hypot(Edge.X,Edge.Y)-std::hypot(.3,.3))<1.e-12);
    const auto Interior=BoundaryVelocity({30,30},{.1,-.2},60,1.5);
    TestTrue(TEXT("Interior intent remains exactly unchanged"),Interior.X==.1&&Interior.Y==-.2);
    const auto Still=BoundaryVelocity({60,0},{0,0},60,1.5);TestTrue(TEXT("No free movement from a stationary intent"),Still.X==0&&Still.Y==0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeLighting,"AdaptiveEcosystem.Playflow.LightingMatchesNativeClock",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeLighting::RunTest(const FString&)
{
    FEcoServerTimeSnapshot Time;TestEqual(TEXT("Missing received clock cannot drive lights"),EcoV3WeatherFx::ClockDarkness(Time),-1.);
    Time.WorldEpoch=1;
    for(int32 Step=0;Step<900;++Step){
        Time.ServerTimeSeconds=Step*EcoRepertoireV3::kStepSeconds;
        if(!EcoClock::EvaluateFixedCycle(Time.ServerTimeSeconds,60,60,Time.DayCycle))return false;
        const auto Native=EcoObservationV3::DayNightPhase(Step,900,0,45);
        if(std::abs(EcoV3WeatherFx::ClockDarkness(Time)-Native.Dark)>1.e-12){AddError(TEXT("Presentation and native twilight disagree"));return false;}
    }
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeColonization,"AdaptiveEcosystem.Playflow.ColonizationConservesBiomassAndShelter",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeColonization::RunTest(const FString&)
{
    EcoWorldV3::FWorldConfig C;C.bEcosystemLife=true;C.Vegetation.bEnabled=true;C.WorldSize=6;C.FoodCell=2;
    C.Covers.clear();C.ShelterFood.bEnabled=false;C.Obstacles.bEnabled=false;
    EcoWorldV3::FWorldState W;EcoWorldV3::InitWorld(W,C);auto& G=W.Food;
    G.Cap.assign(9,0);G.Food.assign(9,0);G.Cap0.clear();G.Regen.assign(9,.02);
    G.Cap[4]=1;G.Food[4]=.4;G.VegetationWeather={.6,20,1};
    std::vector<uint8_t> Ground(9,1);
    const auto Before=G.Food;const auto Plan=EcoVegetationExpansion::Plan(G,C,Ground,225);
    TestEqual(TEXT("Only four immediate seeded neighbors; no same-cycle chain"),int32(Plan.size()),4);
    TestTrue(TEXT("Planning cannot write food or capacity"),Before==G.Food&&G.Cap[1]==0);
    EcoTest::FScopedTestWorld TestWorld;auto* E=TestWorld.World->GetSubsystem<UEcologySimulationSubsystem>();
    FRegionEcologyState State;State.RegionId=TEXT("Expansion");E->RegisterRegionState(State);E->RegisterSpatialFood(State.RegionId,1,.4);
    double Capacity=1;for(const auto& Site:Plan)Capacity+=Site.Capacity;
    TestTrue(TEXT("M4 accepts capacity-only habitat transaction"),E->AdjustSpatialFoodHabitat(State.RegionId,1,.4,0,Capacity,.4));
    for(const auto& Site:Plan)G.Cap[Site.Cell]=Site.Capacity;
    TestEqual(TEXT("Colonization itself never creates biomass"),G.Total(),.4);
    const double OldFood=G.Total();G.Regrow();
    TestTrue(TEXT("Only existing growth supplies new biomass"),G.VegetationGrown>0&&E->CommitSpatialFood(State.RegionId,2,OldFood,0,G.VegetationGrown,G.Total(),G.EnvironmentLost));
    G.Cap.assign(9,0);G.Cap[4]=1;G.Food=Before;G.Cap0=G.Cap;
    C.ShelterFood.bEnabled=true;C.ShelterFood.CapFrac=.2;G.CoverCell[1]=1;
    const auto Covered=EcoVegetationExpansion::Plan(G,C,Ground,225);
    const auto Found=std::find_if(Covered.begin(),Covered.end(),[](const auto& S){return S.Cell==1;});
    TestTrue(TEXT("Expansion preserves shelter food penalty and baseline"),Found!=Covered.end()&&Found->Capacity==Found->BaseCapacity*.2);
    Ground.assign(9,0);TestTrue(TEXT("Unconfirmed terrain cannot grow new habitat"),EcoVegetationExpansion::Plan(G,C,Ground,225).empty());
    Ground.assign(9,1);C.bEcosystemLife=false;TestTrue(TEXT("Old worlds cannot colonize"),EcoVegetationExpansion::Plan(G,C,Ground,225).empty());
    C.bEcosystemLife=true;G.Regen.assign(9,0);TestTrue(TEXT("Explicit suspended regeneration remains suspended"),EcoVegetationExpansion::Plan(G,C,Ground,225).empty());
    G.LastExpansionStep=225;G.ColonizedCells=4;TArray<uint8> Bytes;{FMemoryWriter Ar(Bytes);EcoCheckpoint::Grid(Ar,G);}
    EcoWorldV3::FFoodGrid Copy;{FMemoryReader Ar(Bytes);EcoCheckpoint::Grid(Ar,Copy);}
    TestEqual(TEXT("Restart retains expansion cadence"),Copy.LastExpansionStep,int64(225));
    TestEqual(TEXT("Restart retains colonized cell count"),Copy.ColonizedCells,4);
    return true;
}
#endif

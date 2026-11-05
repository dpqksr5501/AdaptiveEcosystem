#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/EcoNaturalHabitat.h"
#include "AI/Policy/EcoVegetationV3.h"
#include "AI/Policy/EcoWorldV3.h"
#include "World/EcoNaturalHabitatProfile.h"
#include "World/EcoVegetationField.h"
#include "Components/BoxComponent.h"
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoNaturalGrowth,"AdaptiveEcosystem.NaturalHabitat.EnvironmentAndGuilds",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoNaturalGrowth::RunTest(const FString&)
{
    auto* Profile=NewObject<UEcoNaturalHabitatProfile>();TestTrue(TEXT("Shared defaults are valid"),Profile->IsValidProfile());
    EcoVegetationV3::FConfig C;C.bEnabled=true;EcoVegetationV3::FHabitat H;Profile->Guilds[0].Apply(H);
    auto Grow=[&](double Temperature,double Light,double Moisture){EcoVegetationV3::FCell State{Moisture,0};return EcoVegetationV3::Advance(C,{0,Temperature,Light},H,State,.5,1,.02,.1333333333333333);};
    TestTrue(TEXT("Suitable light/water/temperature grows real biomass"),Grow(18,1,.5).Growth>0);
    TestEqual(TEXT("No new growth in complete darkness"),Grow(18,0,.5).Growth,0.);
    TestEqual(TEXT("No growth below the guild's cold limit"),Grow(-20,1,.5).Growth,0.);
    TestEqual(TEXT("No growth above the guild's heat limit"),Grow(60,1,.5).Growth,0.);
    const auto Dry=Grow(18,1,.01);TestTrue(TEXT("Drought reduces growth and causes a separate nonnegative loss"),Dry.Growth<Grow(18,1,.5).Growth&&Dry.Loss>0);
    const auto WetGrass=Grow(18,1,.90);Profile->Guilds[1].Apply(H);
    TestTrue(TEXT("Riparian guild tolerates saturated soil better than grass"),Grow(18,1,.90).Growth>WetGrass.Growth);
    H.bGroundUsable=false;const auto Barren=Grow(18,1,.6);TestEqual(TEXT("Confirmed non-growing ground cannot regenerate"),Barren.Growth,0.);
    TestEqual(TEXT("Environmental loss and growth conserve food"),Barren.Food,.5-Barren.Loss+Barren.Growth);
    Profile->Guilds[0].TemperatureOptimum=Profile->Guilds[0].TemperatureMin;
    TestFalse(TEXT("Invalid niche is rejected before use"),Profile->IsValidProfile());
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoNaturalSites,"AdaptiveEcosystem.NaturalHabitat.StableMosaicAndThreeDimensionalVolumes",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoNaturalSites::RunTest(const FString&)
{
    using namespace EcoNaturalHabitat;
    FGroundTraversal Traversal;
    TestFalse(TEXT("A high upper ledge cannot become a single ground step"),Traversal.AllowsHeight(0,150,30));
    TestFalse(TEXT("A cliff below cannot be projected into a free safe drop"),Traversal.AllowsHeight(0,-250,30));
    TestTrue(TEXT("A small supported step remains traversable"),Traversal.AllowsHeight(0,20,30));
    const auto Available=SettlementBudget(60,5,4,20,4,4,.03);
    const auto Stale=SettlementBudget(60,5,4,40,4,4,.03);
    TestTrue(TEXT("A dated food report may admit a sustainable small group"),Available.bAdmissible);
    TestFalse(TEXT("Already committed arrivals cannot disappear behind a stale population report"),Stale.bAdmissible);
    const auto A=Candidate(19,73,4,400),B=Candidate(19,73,4,400),C=Candidate(23,73,4,400);
    TestTrue(TEXT("Reload/client proposals retain the same stable seed result"),A.X==B.X&&A.Y==B.Y&&A.Yaw==B.Yaw);
    TestTrue(TEXT("Different region/profile seed changes placement"),A.X!=C.X||A.Y!=C.Y);
    for(int32 K=0;K<9;++K){const auto P=Candidate(19,73,K,400);TestTrue(TEXT("Jitter stays in its source food cell"),FMath::Abs(P.X)<200&&FMath::Abs(P.Y)<200);}
    TestTrue(TEXT("Environmental patch field is continuous across logical cell boundaries"),FMath::Abs(PatchDensity(400-1.e-3,0,1800,7)-PatchDensity(400+1.e-3,0,1800,7))<1.e-5);
    EcoTest::FScopedTestWorld World;auto* Volume=World.World->SpawnActor<AEcoVegetationHabitat>();
    Volume->Bounds->SetBoxExtent({1000,700,150});Volume->SetActorLocation({3000,4000,2000});Volume->SetActorRotation({0,37,0});
    TestTrue(TEXT("Authored elevated/rotated habitat contains its actual ground"),Volume->ContainsGround({3000,4000,2000}));
    TestFalse(TEXT("Same XY on the lower floor does not receive upper water/soil"),Volume->ContainsGround({3000,4000,1000}));
    TestTrue(TEXT("Habitat edge has a feathered weight"),Volume->BlendWeight(Volume->GetActorTransform().TransformPosition({950,0,0}))<.1);
    Volume->bConnectedFreshWater=true;Volume->WaterSurfaceZ=2050;
    TestFalse(TEXT("A ground backend rejects explicitly deep water"),EcoCreatureMovement::IsWadeableGround(*World.World,{3000,4000,2000},40));
    TestTrue(TEXT("A shallow authored bank remains traversable"),EcoCreatureMovement::IsWadeableGround(*World.World,{3000,4000,2030},40));
    TestTrue(TEXT("The unrelated lower floor does not inherit upper water"),EcoCreatureMovement::IsWadeableGround(*World.World,{3000,4000,1000},40));
    FBrowseEvidence Browse;Browse.Add(7,1,2,3,0);TestEqual(TEXT("No bite cue without actual intake"),Browse.Sequence,uint64(0));
    Browse.Add(7,1,2,3,.01);TestTrue(TEXT("A bite preserves its actual native cell and intake evidence"),Browse.Sequence==1&&Browse.Events[0].Cell==7&&Browse.Events[0].Amount==.01);
    Browse.Add(7,1,2,3,.01);TestTrue(TEXT("Repeated bites aggregate locally instead of evicting an entire herd's cues"),Browse.Sequence==2&&Browse.Events[0].Amount==.02&&Browse.Events[1].Cell==-1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoNaturalRefuge,"AdaptiveEcosystem.NaturalHabitat.InteriorRestAndVulnerableCover",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoNaturalRefuge::RunTest(const FString&)
{
    using namespace EcoNaturalHabitat;
    for(uint8 Source=0;Source<4;++Source)for(uint8 Variant=0;Variant<4;++Variant){
        const uint8 Flags=EcoPresentationFlags::WithAppearance(uint8(15|(Source<<4)),Variant);
        TestEqual(TEXT("Morph encoding preserves original sensory evidence and vitals flags"),uint8(Flags&63),uint8(15|(Source<<4)));
        TestEqual(TEXT("Each morph decodes independently of current sight/hearing/memory"),EcoPresentationFlags::Appearance(Flags),Variant);
    }
    TestFalse(TEXT("Crossing the footprint boundary is not rest arrival"),CanRest(2,.05,.15,false,20,20,3));
    TestFalse(TEXT("A visible threat prevents rest even inside"),CanRest(.1,2,.15,true,20,20,3));
    TestFalse(TEXT("A new arrival first remains vigilant"),CanRest(.1,2,.15,false,20,1,3));
    TestTrue(TEXT("A quiet, interior, settled occupant may rest"),CanRest(.1,2,.15,false,20,4,3));
    EcoRepertoireV3::FRepState Rep;EcoRepertoireV3::FDecisionObs Obs;Obs.bInCover=true;Obs.CoverK=0;
    auto RepConfig=EcoRepertoireV3::kR1bConfig;RepConfig.bFootprintArrival=false;
    EcoRepertoireV3::Enter(Rep,EcoRepertoireV3::kHide,Obs,RepConfig);
    const auto Lock=Rep.LockLeft;EcoRepertoireV3::Prepare(Rep,Obs,RepConfig);
    TestTrue(TEXT("Repeated footprint observations cannot re-lock arrival at the rim"),!Rep.bArrived&&Rep.LockLeft==Lock);
    for(int32 K=0;K<8;++K){const auto P=Interior(7,0,0,6,.2,K);TestTrue(TEXT("All interior proposals keep full body clearance"),std::hypot(P.X,P.Y)<5.6);}
    EcoWorldV3::FWorldConfig Config;Config.bProtectedRefuges=true;Config.bWildRefuges=true;
    TestFalse(TEXT("Wild cover never activates protected refuge walls"),EcoWorldV3::RefugeOwnsSafety(Config));
    EcoWorldV3::FWorldState W;W.Config.bNaturalHabitats=true;W.RepCfg.bFootprintArrival=false;
    EcoWorldV3::FHerbDecision Decision;Decision.KeepMode=EcoWorldV3::kKeepShelter;
    EcoWorldV3::FHerbView Herb;Herb.Rep=&Rep;Herb.Decision=&Decision;
    Rep.bArrived=false;Rep.LockLeft=30;const auto Sequence=Rep.Seq;
    EcoWorldV3::Detail::CommitFlight(W,Herb);
    TestTrue(TEXT("A persistent shelter reflex cannot restart natural approach every step"),Rep.Seq==Sequence&&Rep.LockLeft==30);
    EcoThreatV3::FThreatConfig ThreatConfig;EcoThreatV3::FPreyView Prey;Prey.bInCover=true;Prey.bNaturalCover=true;Prey.CoverDensity=.8;Prey.Behavior=EcoThreatV3::kPreyHide;Prey.bHideArrived=true;
    TestEqual(TEXT("Concealment does not reduce physically valid capture distance"),EcoThreatV3::PreyCatchMult(Prey,ThreatConfig),1.);
    TestTrue(TEXT("Interior vegetation can still reduce detection"),EcoThreatV3::PreyDetectMult(Prey,ThreatConfig)>1);
    Config.bWildRefuges=false;TestTrue(TEXT("Legacy protected world stays opt-in compatible"),EcoWorldV3::RefugeOwnsSafety(Config));
    return true;
}
#endif

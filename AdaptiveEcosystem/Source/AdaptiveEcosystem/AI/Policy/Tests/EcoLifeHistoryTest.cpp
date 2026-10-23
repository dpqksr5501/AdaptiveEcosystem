#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/EcoLifeHistoryV3.h"
#include "Creature/Runtime/EcoEcosystemArchive.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"
#include <limits>

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeBirthEnergy,"AdaptiveEcosystem.Life.NaturalBirthCannotCreateAdultFatReserve",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeBirthEnergy::RunTest(const FString&)
{
    EcoWorldV3::FWorldConfig C;C.bEcosystemLife=true;C.WildReserve.bEnabled=true;C.WildReserve.Init=1;
    EcoWorldV3::FWorldState W;EcoWorldV3::InitWorld(W,C);
    EcoWorldV3::FHerbBody Body;EcoWorldV3::FHerbDecision Decision;EcoWorldV3::FHerbPerception Perception;
    EcoRepertoireV3::FRepState Rep;EcoRepertoireV3::FControlOutput Control;
    EcoWorldV3::FHerbView View{&Rep,&Decision,&Body,&Perception,&Control};
    EcoWorldV3::AdoptHerb(W,View,{30,30},{1,0},41,true);
    TestEqual(TEXT("Parent-paid newborn energy"),Body.Energy,.4);
    TestEqual(TEXT("A newborn does not receive the free adult reserve"),Body.Reserve,0.);
    EcoWorldV3::AdoptHerb(W,View,{30,30},{1,0},42);
    TestEqual(TEXT("Initial/recovery founders preserve their explicit reserve"),Body.Reserve,1.);
    W.Config.bEcosystemLife=false;EcoWorldV3::AdoptHerb(W,View,{30,30},{1,0},43,true);
    TestEqual(TEXT("OFF retains legacy adoption semantics"),Body.Energy,W.RepCfg.InitEnergy);
    TestEqual(TEXT("OFF retains legacy reserve semantics"),Body.Reserve,1.);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeRegionalEvidence,"AdaptiveEcosystem.Life.RegionalEvidenceBoundsDecayAndDeduplicates",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeRegionalEvidence::RunTest(const FString&)
{
    EcoLifeV3::FRegionalDanger R;
    TestTrue(TEXT("A recognized local outcome enters the aggregate"),R.Record(1,10));
    TestFalse(TEXT("Witnesses cannot multiply the same episode"),R.Record(1,16));
    TestFalse(TEXT("Distinct requests cannot bypass the exposure limit"),R.Record(2,11));
    for(int32 I=0;I<100;++I)R.Record(I+2,20+I*6);
    TestTrue(TEXT("Repeated harm stays bounded"),R.At(614)>0&&R.At(614)<=1);
    TestTrue(TEXT("Old regional risk recovers"),R.At(2414)<R.At(614)*.003);
    TestEqual(TEXT("Future state is never read as past knowledge"),R.At(0),0.);
    return true;
}
#include "Network/Mass/EcoMassReplicationTypes.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeMemory,"AdaptiveEcosystem.Life.ObservedEncountersDecayAndDeduplicate",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeMemory::RunTest(const FString&)
{
    using namespace EcoLifeV3;EcoLifeV3::FMemory Harmless,Pursuit,Surprise;
    for(int I=0;I<5;++I){const double T=I*6.;
        Harmless.Observe(EEncounter::Harmless,I+1,T,T,10,0);
        Pursuit.Observe(EEncounter::Pursuit,I+1,T,T,10,0);
        Surprise.Observe(EEncounter::Surprise,I+1,T,T,10,0);
    }
    TestTrue(TEXT("Separate familiarity and fear axes"),Harmless.Familiarity>.2&&Harmless.Fear==0&&Pursuit.Fear>.35&&Pursuit.Familiarity==0);
    TestTrue(TEXT("Observed surprise and pursuit have distinct strengths"),Surprise.Fear>Pursuit.Fear);
    TestEqual(TEXT("Harmless repeat contact produces actual approach intent"),int(Harmless.Decide(24,10,true,false)),int(EResponse::Curious));
    TestEqual(TEXT("Repeated pursuit produces retreat intent"),int(Pursuit.Decide(24,10,true,false)),int(EResponse::Retreat));
    TestEqual(TEXT("Safety has priority over curiosity"),int(Harmless.Decide(24,10,false,false)),int(EResponse::Policy));
    TestEqual(TEXT("Approach stops at a six-unit safety distance"),int(Harmless.Decide(24,6,true,false)),int(EResponse::Policy));
    TestFalse(TEXT("An episode cannot be gained again through a shared path"),Harmless.Observe(EEncounter::Harmless,5,30,30,10,0));
    TestFalse(TEXT("Old evidence cannot refresh the memory"),Harmless.Observe(EEncounter::Harmless,99,0,30,10,0));
    const double Fear=Surprise.Fear;Surprise.Age(624);TestTrue(TEXT("No permanent farmed fear"),Surprise.Fear<Fear*.04);
    TestEqual(TEXT("No hidden current-location tracking after TTL"),int(Pursuit.Decide(50,10,true,false)),int(EResponse::Policy));
    EcoLifeV3::FMemory Unknown;
    TestTrue(TEXT("Real unknown-source damage can be remembered"),Unknown.Suffer(102,30,false,999,999,false));
    TestTrue(TEXT("Unknown attacker does not become human blame or a hidden coordinate"),Unknown.UnknownFear>0&&Unknown.Fear==0&&Unknown.LastDirect<0&&Unknown.LastX==0);
    TestFalse(TEXT("Duplicate damage episode cannot add memory twice"),Unknown.Suffer(102,31,false,999,999,false));
    TestTrue(TEXT("Known herd report is accepted"),Unknown.ReceiveReport(103,31,31,.5));
    TestTrue(TEXT("Shared report cannot create direct evidence"),Unknown.LastDirect<0);
    TestTrue(TEXT("Subsequent sound does not identify the damage source"),Unknown.Observe(EEncounter::Noise,106,40,40,10,0));
    TestFalse(TEXT("Unknown damage attribution survives unrelated encounter updates"),Unknown.bLastDamageKnown);
    TestFalse(TEXT("Shared reports cannot move time backwards"),Unknown.ReceiveReport(104,30,30,.5));
    TestFalse(TEXT("Non-finite shared confidence is rejected"),Unknown.ReceiveReport(105,40,40,std::numeric_limits<double>::quiet_NaN()));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeCoverRebind,"AdaptiveEcosystem.Life.CheckpointRebindsPhysicalCoverOrder",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeCoverRebind::RunTest(const FString&)
{
    std::vector<EcoObservationV3::FCoverInput> Saved{{10,10,4},{30,30,5},{0,0,0}},Live{{30,30,5},{10,10,4}};
    TArray<int32> Map;
    TestTrue(TEXT("Late registration order is not persistent identity"),EcoCheckpoint::MapCoverGeometry(Saved,Live,Map));
    TestTrue(TEXT("Saved policy target indices map to fresh physical bindings"),Map.Num()==3&&Map[0]==1&&Map[1]==0&&Map[2]==INDEX_NONE);
    Live[0].Radius=6;TestFalse(TEXT("A physically changed refuge cannot become an invisible saved wall"),EcoCheckpoint::MapCoverGeometry(Saved,Live,Map));
    Live={{10,10,4}};TestFalse(TEXT("A missing active refuge still rejects before mutation"),EcoCheckpoint::MapCoverGeometry(Saved,Live,Map));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeGenome,"AdaptiveEcosystem.Life.GenomeGrowthAndTransport",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeGenome::RunTest(const FString&)
{
    using namespace EcoLifeV3;const auto A=Founder(20,42),B=Founder(20,43),Copy=Founder(20,42);
    TestEqual(TEXT("Stable identity produces reproducible traits"),A.Speed,Copy.Speed);
    TestTrue(TEXT("Distinct identities retain diversity"),A.Speed!=B.Speed||A.Size!=B.Size);
    FIndividual Child;Child.bInitialized=true;Child.Origin=EOrigin::NaturalBirth;Child.Born=100;Child.Genome=Inherit(A,B,99);
    TestTrue(TEXT("Offspring traits remain bounded"),Child.Genome.IsValid());
    TestFalse(TEXT("Juveniles cannot parent"),Child.CanParent(279,1,true));
    TestTrue(TEXT("Mature nourished residents can parent"),Child.CanParent(280,.8,true));
    TestFalse(TEXT("Journey prevents birth delivery"),Child.CanParent(280,.8,false));
    TestTrue(TEXT("Growth affects visible size and real movement capability"),Child.BodyScale(100)<Child.BodyScale(280)&&Child.SpeedScale(100)<Child.SpeedScale(280));
    Child.Genome={1.1,1.1};TestTrue(TEXT("Fast/large genomes pay maintenance"),Child.Maintenance()>1.5);
    FReplicatedEcoMassAgent Dto;TestTrue(TEXT("Size-only change creates a transport delta"),Dto.SetPresentation(FVector::ZeroVector,1,255,255,0,0,96));
    TestEqual(TEXT("Late join DTO preserves juvenile scale"),Dto.GetBodyScale(),uint8(96));
    TestFalse(TEXT("Same size creates no duplicate delta"),Dto.SetPresentation(FVector::ZeroVector,1,255,255,0,0,96));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeCheckpointCodec,"AdaptiveEcosystem.Life.NativeCheckpointConservesSoilAndRandomStream",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeCheckpointCodec::RunTest(const FString&)
{
    EcoWorldV3::FWorldConfig Config;Config.WorldSize=60;Config.Vegetation.bEnabled=true;Config.bEcosystemLife=true;Config.Seed=47;
    EcoWorldV3::FWorldState Before;EcoWorldV3::InitWorld(Before,Config);
    for(int I=0;I<127;++I)Before.Food.Regrow();Before.T=127;
    TArray<uint8> Bytes;{FMemoryWriter A(Bytes);EcoCheckpoint::World(A,Before);TestFalse(TEXT("Save codec succeeds"),A.IsError());}
    EcoWorldV3::FWorldState After;{FMemoryReader A(Bytes);EcoCheckpoint::World(A,After);TestFalse(TEXT("Load codec succeeds"),A.IsError());}
    TestTrue(TEXT("Restored cell layout is supported"),EcoCheckpoint::ValidGrid(After.Food));
    TestEqual(TEXT("No food created by load"),After.Food.Total(),Before.Food.Total());
    TestEqual(TEXT("Soil memory is preserved"),After.Food.VegetationCells[0].Moisture,Before.Food.VegetationCells[0].Moisture);
    TestEqual(TEXT("The next random result is identical"),After.Rng.NextU64(),Before.Rng.NextU64());
    Before.Food.Regrow();After.Food.Regrow();TestEqual(TEXT("The next growth result is identical"),After.Food.Total(),Before.Food.Total());
    After.Food.Cap.clear();TestFalse(TEXT("Missing required cell arrays fail closed before mutation"),EcoCheckpoint::ValidGrid(After.Food));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeTraces,"AdaptiveEcosystem.Life.BoundedSpatialTracesAndCaptureAuthority",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeTraces::RunTest(const FString&)
{
    EcoTracesV3::FField Field;
    for(int32 I=0;I<1000;++I)Field.Add(I+1,double(I%5),double(I%7),0,10);
    int32 Count=0;Field.Query(2,3,11,[&](const auto&){++Count;});TestTrue(TEXT("Per query candidate budget"),Count>0&&Count<=16);
    Count=0;Field.Query(2,3,31,[&](const auto&){++Count;});TestEqual(TEXT("Expired traces cannot be investigated"),Count,0);
    Field.Rebuild();Count=0;Field.Query(2,3,11,[&](const auto&){++Count;});TestTrue(TEXT("Persistence rebuild restores spatial lookup"),Count>0&&Count<=16);
    EcoThreatV3::FThreatConfig Config;auto Spec=EcoThreatV3::MakeChaserSpec(.8,false,false,Config);
    EcoThreatV3::FPreyView Prey;Prey.X=.1;Prey.Y=.1;
    EcoThreatV3::FThreatStepInput Input;Input.Prey=&Prey;Input.NumPrey=1;Input.WorldSize=60;Input.bHuntingAllowed=false;
    EcoThreatV3::FThreatState State;
    const auto Denied=EcoThreatV3::Step(Spec,State,Input,Config);TestEqual(TEXT("Game-rule hunting gate forbids actual capture"),Denied.Caught,-1);
    Input.bHuntingAllowed=true;uint8 Mask=0;Input.CaptureAllowed=&Mask;State={};
    TestEqual(TEXT("Final authority LOS denial forbids actual capture"),EcoThreatV3::Step(Spec,State,Input,Config).Caught,-1);
    Input.CaptureAllowed=nullptr;State={};TestEqual(TEXT("A valid contact still uses the single native capture path"),EcoThreatV3::Step(Spec,State,Input,Config).Caught,0);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeVegetationSight,"AdaptiveEcosystem.Life.GrazingRemovesVegetationSightScreen",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeVegetationSight::RunTest(const FString&)
{
    EcoWorldV3::FWorldConfig C;C.WorldSize=60;C.Vegetation.bEnabled=true;
    EcoWorldV3::FWorldState W;EcoWorldV3::InitWorld(W,C);
    for(size_t I=0;I<W.Food.Food.size();++I){W.Food.Cap[I]=W.Food.Food[I]=1;W.Food.Habitats[I].Plant=EcoVegetationV3::EPlant::Shrub;W.Food.Habitats[I].Shade=.6;}
    TestTrue(TEXT("Dense living shrubs screen a six metre sight path"),W.Food.BlocksSight(10,10,20,10));
    for(auto& F:W.Food.Food)F=0;
    TestFalse(TEXT("Same cells lose screening when eaten"),W.Food.BlocksSight(10,10,20,10));
    W.Food.Vegetation.bEnabled=false;TestFalse(TEXT("OFF has no new sight semantics"),W.Food.BlocksSight(10,10,20,10));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoLifeMeat,"AdaptiveEcosystem.Life.CommittedCarcassNutritionAndStarvation",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoLifeMeat::RunTest(const FString&)
{
    EcoLifeV3::FIndividual Wolf;Wolf.bInitialized=true;Wolf.Nutrition=.5;
    TestTrue(TEXT("Committed source creates one bounded meal"),Wolf.AssignMeat(500,.6,0,5,5,0));
    TestFalse(TEXT("Same prey receipt cannot duplicate food"),Wolf.AssignMeat(500,.6,1,5,5,0));
    Wolf.PredatorStep(1,50,50,true,2./15);
    TestEqual(TEXT("Remote meal grants no nutrition"),Wolf.MeatConsumed,0.);
    for(int32 I=0;I<40;++I)Wolf.PredatorStep(2+I*2./15,5,5,false,2./15);
    TestTrue(TEXT("Actual contact transfers carcass nutrition"),Wolf.MeatConsumed>0&&Wolf.Nutrition>.5);
    Wolf.PredatorStep(25,50,50,false,2./15);
    TestTrue(TEXT("Produced = consumed + remaining + decay"),FMath::IsNearlyEqual(Wolf.MeatIssued,Wolf.MeatConsumed+Wolf.MeatWasted+Wolf.MealRemaining,1e-12));
    TestEqual(TEXT("Expired source is released"),Wolf.MealRemaining,0.);
    Wolf.Nutrition=.00001;TestFalse(TEXT("Predator can actually starve"),Wolf.PredatorStep(26,5,5,false,2./15));
    return true;
}
#endif

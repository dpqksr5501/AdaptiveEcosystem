#include "Misc/AutomationTest.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "AI/Policy/Tests/EcoTestWorld.h"
#include "AI/Policy/EcoCreatureV3Trait.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Player/EcoPlayerEcologyComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Network/Mass/EcoMassReplicationTypes.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplate.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Creature/Debug/EcoCreatureInspection.h"
#include "MassSpawnerSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"
#include <limits>
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUSpatialFood,"AdaptiveEcosystem.Creature.JYU.SpatialFoodConservationAndExclusiveWriter",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUSpatialFood::RunTest(const FString&) {
    EcoTest::FScopedTestWorld W;auto* E=W.World->GetSubsystem<UEcologySimulationSubsystem>();
    FRegionEcologyState S;S.RegionId=TEXT("JYUTest");S.FoodRegenerationRate=20;
    if(!TestTrue(TEXT("Register region"),E->RegisterRegionState(S)))return false;
    TestTrue(TEXT("Register exclusive native source"),E->RegisterSpatialFood(S.RegionId,100,80));
    TestFalse(TEXT("Cannot replace a live source"),E->RegisterSpatialFood(S.RegionId,100,40));
    TestTrue(TEXT("Conserving receipt"),E->CommitSpatialFood(S.RegionId,1,80,5,2,77));
    TestFalse(TEXT("Duplicate receipt"),E->CommitSpatialFood(S.RegionId,1,77,0,0,77));
    TestFalse(TEXT("Stale before"),E->CommitSpatialFood(S.RegionId,2,80,5,2,77));
    TestFalse(TEXT("Nonconserving receipt"),E->CommitSpatialFood(S.RegionId,2,77,5,2,70));
    TestFalse(TEXT("NaN rejected"),E->CommitSpatialFood(S.RegionId,2,77,0,0,std::numeric_limits<double>::quiet_NaN()));
    FEcoFoodConsumptionRequest R;R.RegionId=S.RegionId;R.StableAgentId=5;R.RequestedAmount=10;
    TestEqual(TEXT("Legacy direct consumption cannot be a second writer"),E->ApplyFoodConsumption(R),0.f);
    E->TickSimulation(1);E->GetRegionState(S.RegionId,S);
    TestEqual(TEXT("Generic regeneration cannot be a second writer"),S.FoodAmount,77.f);
    TestTrue(TEXT("Rejected receipts do not advance sequence"),E->CommitSpatialFood(S.RegionId,2,77,7,0,70));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUSavedAssets,"AdaptiveEcosystem.Creature.JYU.SavedProfilesAndBehaviorGraphs",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUSavedAssets::RunTest(const FString&) {
    EcoTest::FScopedTestWorld W;
    for(const FString Kind:{TEXT("Deer"),TEXT("Wolf")}) {
        FString Path=TEXT("/Game/JYU/Animation/DA_JYU_")+Kind+TEXT("_Animation");
        auto* P=LoadObject<UEcoCreatureAnimationProfile>(nullptr,*Path);
        if(!TestNotNull(TEXT("Saved profile"),P)||!TestTrue(TEXT("Matching clips and skeleton"),P->IsValidProfile()))return false;
        FString BP=TEXT("/Game/JYU/Creatures/BP_JYU_")+Kind+TEXT(".BP_JYU_")+Kind+TEXT("_C");
        UClass* Class=LoadClass<AEcoCreatureRepresentationActor>(nullptr,*BP);
        if(!TestNotNull(TEXT("Saved representation class"),Class))return false;
        auto* A=W.World->SpawnActor<AEcoCreatureRepresentationActor>(Class);
        TestTrue(TEXT("Saved behavior animation class and profile"),A->AnimationProfile==P && A->BehaviorAnimationClass && A->BehaviorAnimationClass->IsChildOf(UEcoCreatureAnimInstance::StaticClass()));
        TestEqual(TEXT("Four authored contact bones"),P->FootBones.Num(),4);
        const FName CorrectEnd=P->IKEndBones[0];P->IKEndBones[0]=P->FootBones[0];
        TestFalse(TEXT("Contact marker cannot be used as a shortened limb end"),P->IsValidProfile());P->IKEndBones[0]=CorrectEnd;
        const FName CorrectBody=P->BodyBone;P->BodyBone=TEXT("MissingBody");
        TestFalse(TEXT("Missing common body ancestor rejected"),P->IsValidProfile());P->BodyBone=CorrectBody;


        A->BindIdentity(500,TEXT("Herbivore")==A->VisualSpeciesId?FName(TEXT("Herbivore")):FName(TEXT("Wolf")));
        FEcoCreatureVisualState View;View.StableAgentId=500;View.SpeciesId=A->VisualSpeciesId;View.Sequence=1;
        A->ConsumeVisualState(View,.016f);
        auto* Instance=Cast<UEcoCreatureAnimInstance>(A->CreatureMesh->GetAnimInstance());
        if(TestNotNull(TEXT("Actual saved animation instance"),Instance)) {
            View.Sequence=2;View.bAlive=true;View.Activity=EEcoSpeciesActivity::Graze;View.SenseSource=EEcoSenseSource::Hearing;
            A->ConsumeVisualState(View,.016f);Instance->NativeUpdateAnimation(.2f);
            TestEqual(TEXT("Fresh sound briefly interrupts grazing with an alert pose"),Instance->AnimationIndex,2);
            Instance->NativeUpdateAnimation(1.f);
            TestEqual(TEXT("Persistent cue does not pin grazing in alert"),Instance->AnimationIndex,1);
            View.Sequence=3;View.Activity=EEcoSpeciesActivity::Sleep;View.SenseSource=EEcoSenseSource::Sight;
            A->ConsumeVisualState(View,.016f);Instance->NativeUpdateAnimation(.3f);
            TestEqual(TEXT("Sensory cue cannot override sleep"),Instance->AnimationIndex,5);
            View.Sequence=4;View.bAlive=false;A->ConsumeVisualState(View,.016f);Instance->NativeUpdateAnimation(.2f);
            TestEqual(TEXT("Death uses terminal pose"),Instance->AnimationIndex,8);
            A->ClearBinding();A->BindIdentity(501,A->VisualSpeciesId);
            TestEqual(TEXT("Rebinding resets previous death and IK state"),Instance->AnimationIndex,0);
            TestEqual(TEXT("Rebinding resets foot grounding alpha"),Instance->GroundIKAlpha,0.f);
        }
        float Hold=P->MinimumPoseHoldSeconds;P->MinimumPoseHoldSeconds=-1;
        TestFalse(TEXT("Invalid animation tuning rejected"),P->IsValidProfile());P->MinimumPoseHoldSeconds=Hold;
    }
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUTemplate,"AdaptiveEcosystem.Creature.JYU.CanonicalV3TemplateAndLifecycle",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUTemplate::RunTest(const FString&) {
    EcoTest::FScopedTestWorld W;
    for(bool Predator:{false,true}) {
        auto* C=UEcoCreatureV3Trait::MakeNetworkConfig(Predator);
        TestTrue(TEXT("Same role uses stable canonical config"),C==UEcoCreatureV3Trait::MakeNetworkConfig(Predator));
        const auto& T=C->GetOrCreateEntityTemplate(*W.World);if(!TestTrue(TEXT("Build template"),T.IsValid()))return false;
        const auto& D=T.GetTemplateData();
        TestTrue(TEXT("Common M4 survival and sensory receipts"),D.HasFragment<FEcoCreatureSurvivalFragment>()&&D.HasFragment<FEcoCreatureCueFragment>());
        TestFalse(TEXT("No legacy observation processor"),D.HasFragment<FEcoObservationFragment>());
        TestTrue(TEXT("Role-specific v3 brain"),Predator?D.HasFragment<FEcoThreatStateFragment>():D.HasFragment<FEcoHerbivoreBodyV3Fragment>());
    }
    TestTrue(TEXT("Deer and wolf config identities are distinct"),UEcoCreatureV3Trait::MakeNetworkConfig(false)!=UEcoCreatureV3Trait::MakeNetworkConfig(true));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUCue,"AdaptiveEcosystem.Creature.JYU.StationarySensoryTransportAndSurfaces",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUCue::RunTest(const FString&) {
    FReplicatedEcoMassAgent A;A.SetStableAgentId(10);A.SetPresentation(FVector::ZeroVector,17,255,255,0,100);
    auto Before=A.MakeRepresentationSnapshot();
    TestTrue(TEXT("Direction-only change transports"),A.SetPresentation(FVector::ZeroVector,17,255,255,0,-200));
    auto After=A.MakeRepresentationSnapshot();
    TestTrue(TEXT("Visual revision advances while movement clock remains unchanged"),After.VisualRevision>Before.VisualRevision&&After.SampleSequence==Before.SampleSequence);
    TestFalse(TEXT("No duplicate cue update"),A.SetPresentation(FVector::ZeroVector,17,255,255,0,-200));
    auto* Audio=NewObject<UEcoFootstepAudioSet>();auto* Snow=NewObject<UPhysicalMaterial>();Audio->SnowMaterials.Add(Snow);
    TestTrue(TEXT("Snow overrides forest fallback"),Audio->GetSurface(Snow,TEXT("Forest"))==EEcoFootstepSurface::Snow);
    TestTrue(TEXT("Unknown material retains region fallback"),Audio->GetSurface(nullptr,TEXT("Forest"))==EEcoFootstepSurface::Grass);
    TestTrue(TEXT("Missing snow sound stays silent"),Audio->GetSounds(EEcoFootstepSurface::Snow).IsEmpty());return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUAlarm,"AdaptiveEcosystem.Creature.JYU.AlarmNoiseIdentityAndExpiry",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUAlarm::RunTest(const FString&) {
    EcoTest::FScopedTestWorld W;auto* N=W.World->GetSubsystem<UEcoNoiseSubsystem>();
    TestEqual(TEXT("Invalid logical source rejected"),N->ReportCreatureAlarm(FVector::ZeroVector,0,TEXT("Herbivore")),int64(0));
    const int64 Id=N->ReportCreatureAlarm(FVector(100,200,0),42,TEXT("Herbivore"));
    TestTrue(TEXT("Authority emits alarm without visual Actor"),Id>0);
    TArray<FEcoNoiseEvent> Events;N->GatherRecent(Events);
    if(!TestEqual(TEXT("One immutable event"),Events.Num(),1))return false;
    TestTrue(TEXT("Persistent source and dedicated tag preserved"),Events[0].SourceAgentId==42 && Events[0].Tag==TEXT("Herd.Alarm") && Events[0].ThreatStrength>0);
    W.World->TimeSeconds+=1;N->GatherRecent(Events);
    TestTrue(TEXT("Expired alarms cannot be replayed by a later observer"),Events.IsEmpty());return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUInspectionBackend,"AdaptiveEcosystem.Creature.JYU.NativeThreatAndBackendInspection",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUInspectionBackend::RunTest(const FString&) {
    EcoTest::FScopedTestWorld W;
    auto* Spawner=W.World->GetSubsystem<UMassSpawnerSubsystem>();
    auto* Config=UEcoCreatureV3Trait::MakeNetworkConfig(false);
    TArray<FMassEntityHandle> Entities;
    {auto Creation=Spawner->SpawnEntities(Config->GetOrCreateEntityTemplate(*W.World),1,Entities);}
    if(!TestEqual(TEXT("Spawn actual v3 template"),Entities.Num(),1))return false;
    auto& Manager=Spawner->GetEntityManagerChecked();const auto Entity=Entities[0];
    auto& Identity=Manager.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
    Identity.StableAgentId=9011;Identity.SpeciesId=TEXT("Herbivore");
    auto& Perception=Manager.GetFragmentDataChecked<FEcoPerceptionCacheFragment>(Entity).Perception;
    Perception.Threat.Nearest=0;Perception.Threat.PredCount=1;Perception.Threat.DPredMin=2.5;Perception.Kin.KinAlarm=.5;
    Manager.GetFragmentDataChecked<FEcoBehaviorStateFragment>(Entity).Decision.bCommittedReads=true;
    FString Json;if(!TestTrue(TEXT("Inspect actual Mass entity without a visual actor"),UEcoCreatureInspectionLibrary::CaptureAgent(W.World,9011,Json)))return false;
    TSharedPtr<FJsonObject> Data;
    if(!TestTrue(TEXT("Valid diagnostic JSON"),FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Data)))return false;
    TestEqual(TEXT("Reports observed threat count"),Data->GetNumberField(TEXT("native_threat_count")),1.0);
    TestEqual(TEXT("Native distance explicitly converted to cm"),Data->GetNumberField(TEXT("native_threat_distance_cm")),500.0);
    TestEqual(TEXT("Native kin alarm is distinguishable from Social alarm"),Data->GetNumberField(TEXT("native_kin_alarm")),.5);
    TestTrue(TEXT("Native v3 has the connected Social runtime"),Data->GetBoolField(TEXT("social_runtime")));
    TestFalse(TEXT("Never claims excluded SpeciesAI movement is active"),Data->GetBoolField(TEXT("species_ai_movement")));
    TestEqual(TEXT("Observation includes actual trained dimensions"),Data->GetArrayField(TEXT("observation")).Num(),EcoPolicyV3::kObsDim);
    TestTrue(TEXT("Distinguishes policy evaluation from holding previous action"),Data->GetBoolField(TEXT("committed_policy_read")));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUThreatContext,"AdaptiveEcosystem.Creature.JYU.NativeThreatContextInspection",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUThreatContext::RunTest(const FString&) {
    EcoTest::FScopedTestWorld W;
    auto* Spawner=W.World->GetSubsystem<UMassSpawnerSubsystem>();
    TArray<FMassEntityHandle> Entities;
    {auto Creation=Spawner->SpawnEntities(UEcoCreatureV3Trait::MakeNetworkConfig(false)->GetOrCreateEntityTemplate(*W.World),1,Entities);}
    if(!TestEqual(TEXT("Spawn actual native deer"),Entities.Num(),1))return false;
    auto& M=Spawner->GetEntityManagerChecked();const auto E=Entities[0];
    M.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId=9012;
    auto* Sub=W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    Sub->ActivateForTest(FEcoV3IntegratedSettings{},false);
    EcoWorldV3::FWorldConfig Config;Config.Covers.push_back({20,20,6});
    auto* Region=Sub->AddContext(TEXT("SightTest"),0,FVector::ZeroVector,Config,1,1);
    Region->Sim.Dark=0;Region->Sim.ObsCfg.ThreatFovCos=std::cos(FMath::DegreesToRadians(150.));
    auto& Link=M.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);Link.bAdopted=true;Link.ContextIndex=Region->Index;
    auto& Body=M.GetFragmentDataChecked<FEcoHerbivoreBodyV3Fragment>(E).Body;Body.Pos={20,20};Body.Head={1,0};
    auto& State=M.GetFragmentDataChecked<FEcoBehaviorStateFragment>(E);
    State.Rep.SeeMult=State.Rep.SeeMultLast=.6;State.Rep.Behavior=EcoRepertoireV3::kHide;State.Rep.HideTarget=0;State.Rep.bArrived=true;
    M.GetFragmentDataChecked<FEcoPerceptionCacheFragment>(E).Perception.Cover.bInCover=true;
    auto& Request=M.GetFragmentDataChecked<FEcoSocialMovementRequestFragment>(E);Request.bValid=true;
    EcoObservationV3::FThreatInput Wolf;Wolf.X=18;Wolf.Y=20;Wolf.HearR=2;Wolf.bHunting=false;
    Region->Sim.ThreatIn.push_back(Wolf);
    auto Capture=[&](){FString Json;UEcoCreatureInspectionLibrary::CaptureAgent(W.World,9012,Json);TSharedPtr<FJsonObject> D;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),D);return D;};
    auto D=Capture();if(!TestTrue(TEXT("Valid diagnostic output"),D.IsValid()))return false;
    TestEqual(TEXT("Slow wolf directly behind is heard within 4m"),D->GetStringField(TEXT("nearest_wolf_reason")),FString(TEXT("HeardRestingWolf")));
    TestTrue(TEXT("Native sight is separated from hearing"),!D->GetBoolField(TEXT("nearest_wolf_sight_native"))&&D->GetBoolField(TEXT("nearest_wolf_heard_native")));
    TestFalse(TEXT("Resting wolf is not reported as hunting"),D->GetBoolField(TEXT("nearest_wolf_hunting")));
    TestTrue(TEXT("Hiding and cover facts remain explicit"),D->GetBoolField(TEXT("native_in_cover"))&&D->GetBoolField(TEXT("hide_arrived")));
    TestEqual(TEXT("Non-shelter Social request cannot replace the native cover target with zero"),D->GetStringField(TEXT("target")),Region->UnitsToCm(20,20,0).ToCompactString());
    TestEqual(TEXT("Current vision radius reflects the grazing multiplier"),D->GetNumberField(TEXT("native_vision_radius_cm")),2400.);
    auto& T=Region->Sim.ThreatIn[0];T.X=22;D=Capture();
    TestEqual(TEXT("Visible resting wolf is different from an unseen wolf"),D->GetStringField(TEXT("nearest_wolf_reason")),FString(TEXT("SeenRestingWolf")));
    T.bAsleep=true;D=Capture();TestEqual(TEXT("Sleep exclusion is explicit"),D->GetStringField(TEXT("nearest_wolf_reason")),FString(TEXT("Asleep")));
    T.bAsleep=false;T.bHunting=true;T.X=17.9;D=Capture();
    TestEqual(TEXT("Slow wolf in blind sector beyond hearing is actually unsensed"),D->GetStringField(TEXT("nearest_wolf_reason")),FString(TEXT("OutsideSightAndHearing")));
    T.HearR=20;D=Capture();TestEqual(TEXT("Running wolf behind is detected by sound"),D->GetStringField(TEXT("nearest_wolf_reason")),FString(TEXT("HeardHunter")));
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUSenseProvenance,"AdaptiveEcosystem.Creature.JYU.NativeSightAndHearingProvenance",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUSenseProvenance::RunTest(const FString&) {
    EcoObservationV3::FThreatInput Threat;Threat.X=-2;Threat.HearR=5;
    const auto Heard=EcoObservationV3::PerceiveThreats({0,0},{1,0},20,1,1,&Threat,1);
    TestEqual(TEXT("Wolf behind deer is detected by hearing"),Heard.PredCount,1);
    TestTrue(TEXT("Hearing is never mislabeled as direct sight"),Heard.bNearestHeard&&!Heard.bNearestSight);
    Threat.X=2;
    const auto Seen=EcoObservationV3::PerceiveThreats({0,0},{1,0},20,1,1,&Threat,1);
    TestTrue(TEXT("Sight and hearing can both contribute"),Seen.bNearestSight&&Seen.bNearestHeard);
    Threat.bAsleep=true;
    const auto Sleeping=EcoObservationV3::PerceiveThreats({0,0},{1,0},20,1,1,&Threat,1);
    TestTrue(TEXT("No stale sensory provenance on an ignored threat"),Sleeping.Nearest<0&&!Sleeping.bNearestSight&&!Sleeping.bNearestHeard);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoJYUPlayerGait,"AdaptiveEcosystem.Creature.JYU.PlayerGaitBounds",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FEcoJYUPlayerGait::RunTest(const FString&) {
    EcoTest::FScopedTestWorld W;auto* Character=W.World->SpawnActor<ACharacter>();
    auto* Bridge=NewObject<UEcoPlayerEcologyComponent>(Character);Character->AddInstanceComponent(Bridge);Bridge->RegisterComponent();
    Bridge->SetGait(EEcoPlayerGait::Run);TestEqual(TEXT("Run updates actual CharacterMovement"),Character->GetCharacterMovement()->MaxWalkSpeed,900.f);
    Bridge->SetGait(EEcoPlayerGait::Sneak);TestEqual(TEXT("Sneak movement matches authored gait"),Character->GetCharacterMovement()->MaxWalkSpeed,270.f);
    Bridge->SetGait(EEcoPlayerGait(255));TestTrue(TEXT("Malformed gait cannot change server movement"),Bridge->Gait==EEcoPlayerGait::Sneak&&Character->GetCharacterMovement()->MaxWalkSpeed==270.f);
    Bridge->SetGait(EEcoPlayerGait::Walk);TestEqual(TEXT("Walk restored"),Character->GetCharacterMovement()->MaxWalkSpeed,360.f);
    struct { EEcoPlayerGait NewGait; } Params{EEcoPlayerGait::Run};
    Bridge->ProcessEvent(Bridge->FindFunctionChecked(TEXT("SetGait")),&Params);
    TestTrue(TEXT("Reflected gait input reaches the movement bridge"),Bridge->Gait==EEcoPlayerGait::Run&&Character->GetCharacterMovement()->MaxWalkSpeed==900.f);return true;
}
#endif

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
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Components/CapsuleComponent.h"
#include "Components/BoxComponent.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityTemplate.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "World/EcoWorldClockSubsystem.h"
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
};

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
    FEcoCombatTestAccess::Ready(*S,Entities);W.World->GetSubsystem<UEcoWorldClockSubsystem>()->StartClock(7,60,60);
    FEcoCombatTestAccess::Proxies(*S);
    auto* R=NewObject<UEcoCombatRelevanceComponent>(P.Pawn);P.Pawn->AddInstanceComponent(R);R->RegisterComponent();
    R->Offer.Coordinator=S;R->Offer.Epoch=7;R->Offer.Revision=1;R->Offer.Agents={101,102};
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
    return true;
}
#endif

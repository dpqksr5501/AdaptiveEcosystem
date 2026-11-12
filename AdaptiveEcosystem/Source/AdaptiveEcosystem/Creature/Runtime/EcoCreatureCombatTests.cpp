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
#include "Mass/EntityFragments.h"
#include "GameFramework/Character.h"
#include "GameFramework/PlayerController.h"
#include "World/EcoWorldClockSubsystem.h"
#include "World/EcologyRegion.h"
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
        const FEcoServerTimeSnapshot& Time, const FVector& Position = FVector::ZeroVector)
    {
        S.bAuthorityWorld = true;
        auto& Profile = S.FaunaSpecies.AddDefaulted_GetRef();
        Profile.SpeciesId = TEXT("Rat");
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
    static void Passages(AEcoCreatureIntegrationSpawner& S, FMassEntityManager& EM,
        const FEcoServerTimeSnapshot& Time, TArray<FEcoMigrationOutcome>& Arrivals)
    { S.ReconcileFaunaPassages(EM, Time, Time.ServerTimeSeconds, 1, Arrivals); }
    static bool CanHunt(const AEcoCreatureIntegrationSpawner& S, const FMassEntityManager& Manager,
        FMassEntityHandle Hunter, FMassEntityHandle Prey, double Now)
    { return S.CanHuntFauna(Manager, Hunter, Prey, S.FaunaSpecies[0], Now, true); }
};

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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoRuleFaunaPassageMovement, "AdaptiveEcosystem.Fauna.Passage.GroundTransfer",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoRuleFaunaPassageMovement::RunTest(const FString&)
{
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
    Region.FoodAmount = Region.FoodCapacity;
    if (!Ecology->RegisterRegionState(Region)) return false;
    FEcoServerTimeSnapshot Time;
    Time.ServerTimeSeconds = 1.;
    const auto Entity = FEcoCombatTestAccess::SpawnFaunaAt(*Spawner, Source->RegionId, Time, FVector(-110., 0., 0.));
    auto& EM = W.World->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    if (!TestTrue(TEXT("Rule-fauna agent starts in its origin"), EM.IsEntityValid(Entity))) return false;
    auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
    Vitals.Energy = .2f * Vitals.MaxEnergy;
    FEcoCombatTestAccess::SetPassageRegions(*Spawner, *Source, *Destination);
    TArray<FEcoMigrationOutcome> Arrivals;
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

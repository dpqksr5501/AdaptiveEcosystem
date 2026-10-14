#include "Creature/Representation/EcoCreatureAnimationBuilder.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Creature/Representation/EcoCreatureAnimInstance.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Animation/AnimBlueprint.h"
#include "AI/Policy/EcoCreatureV3Trait.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/StaticMeshActor.h"
#include "Camera/CameraActor.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Creature/Debug/EcoCreatureInspection.h"
#include "Creature/Player/EcoPlayerEcologyComponent.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#if WITH_EDITOR
#include "LandscapeProxy.h"
#include "LandscapeComponent.h"
#include "EngineUtils.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionEditorLoaderAdapter.h"
#include "WorldPartition/LoaderAdapter/LoaderAdapterShape.h"
#include "UObject/UnrealType.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#endif

FEcoBuildPoseGraph& EcoPoseGraphAuthoring(){static FEcoBuildPoseGraph Delegate;return Delegate;}
bool UEcoCreatureAnimationBuilder::BuildPoseGraph(UAnimBlueprint* BP,UEcoCreatureAnimationProfile* Profile)
{
    return EcoPoseGraphAuthoring().IsBound() && EcoPoseGraphAuthoring().Execute(BP,Profile);
}

bool UEcoCreatureAnimationBuilder::ConfigureBehaviorRepresentation(UBlueprint* BP,UEcoCreatureAnimationProfile* P,TSubclassOf<UEcoCreatureAnimInstance> Class)
{
#if WITH_EDITOR
    if(!BP||!BP->GeneratedClass||!P||!P->IsValidProfile()||!Class||!BP->GetPathName().StartsWith(TEXT("/Game/JYU/"))) return false;
    auto* CDO=Cast<AEcoCreatureRepresentationActor>(BP->GeneratedClass->GetDefaultObject());
    if(!CDO)return false;
    BP->Modify();CDO->Modify();CDO->AnimationProfile=P;CDO->BehaviorAnimationClass=Class;
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    CDO=Cast<AEcoCreatureRepresentationActor>(BP->GeneratedClass->GetDefaultObject());
    return CDO&&CDO->AnimationProfile==P&&CDO->BehaviorAnimationClass==Class;
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::AddPlayerEcologyComponent(UBlueprint* BP,UEcoFootstepAudioSet* AudioSet)
{
#if WITH_EDITOR
    if(!BP||!BP->SimpleConstructionScript||!AudioSet||!BP->GetPathName().StartsWith(TEXT("/Game/JYU/")))return false;
    BP->Modify();
    USCS_Node* Node=nullptr;
    for(auto* Existing:BP->SimpleConstructionScript->GetAllNodes())
        if(Existing->ComponentClass==UEcoPlayerEcologyComponent::StaticClass())Node=Existing;
    if(!Node){Node=BP->SimpleConstructionScript->CreateNode(UEcoPlayerEcologyComponent::StaticClass(),TEXT("EcoPlayerEcology"));BP->SimpleConstructionScript->AddNode(Node);}
    auto* C=Cast<UEcoPlayerEcologyComponent>(Node->ComponentTemplate);if(!C)return false;
    C->AudioSet=AudioSet;
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    return BP->Status!=BS_Error;
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::ConfigureV3EntityConfig(UMassEntityConfigAsset* Config,bool bPredator)
{
#if WITH_EDITOR
    if(!Config||!Config->GetPathName().StartsWith(TEXT("/Game/JYU/")))return false;
    for(const auto* Trait:Config->GetConfig().GetTraits())if(!Trait->IsA<UEcoCreatureV3Trait>())return false;
    Config->Modify();
    auto* Trait=Cast<UEcoCreatureV3Trait>(Config->AddTrait(UEcoCreatureV3Trait::StaticClass()));
    if(!Trait)return false;
    Trait->bPredator=bPredator;Config->MarkPackageDirty();return true;
#else
    return false;
#endif
}
bool UEcoCreatureAnimationBuilder::ProjectPlacementPoint(UObject* Context,FVector Point,FVector& Out)
{
    UWorld* World=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    return World&&EcoCreatureMovement::ProjectSpawnPoint(*World,Point,Out);
}

bool UEcoCreatureAnimationBuilder::ConfigureIntegrationGameMode(UBlueprint* BP,TSubclassOf<APawn> Pawn,TSubclassOf<APlayerController> Controller)
{
#if WITH_EDITOR
    if(!BP||!BP->GeneratedClass||!Pawn||!Controller||!BP->GetPathName().StartsWith(TEXT("/Game/JYU/")))return false;
    auto* Mode=Cast<AGameModeBase>(BP->GeneratedClass->GetDefaultObject());if(!Mode)return false;
    BP->Modify();Mode->Modify();Mode->DefaultPawnClass=Pawn;Mode->PlayerControllerClass=Controller;Mode->HUDClass=AEcoCreatureInspectorHUD::StaticClass();
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    Mode=Cast<AGameModeBase>(BP->GeneratedClass->GetDefaultObject());
    return Mode&&Mode->DefaultPawnClass==Pawn&&Mode->PlayerControllerClass==Controller&&Mode->HUDClass==AEcoCreatureInspectorHUD::StaticClass();
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::PrepareCopiedWorld(UObject* Context)
{
#if WITH_EDITOR
    UWorld* W=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!W||W->WorldType!=EWorldType::Editor||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/")))return false;
    if(auto* WP=W->GetWorldPartition()) {
        auto* Loader=WP->CreateEditorLoaderAdapter<FLoaderAdapterShape>(W,FBox(FVector(-1000000),FVector(1000000)),TEXT("JYU copied world authoring"));
        Loader->GetLoaderAdapter()->Load();
    }
    return true;
#else
    return false;
#endif
}
bool UEcoCreatureAnimationBuilder::SetCopiedLandscapeMaterial(UObject* Context,UMaterialInterface* Material)
{
#if WITH_EDITOR
    UWorld* W=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!W||W->WorldType!=EWorldType::Editor||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/"))||!Material||!Material->GetPathName().StartsWith(TEXT("/Game/JYU/")))return false;
    int32 Count=0;
    for(TActorIterator<ALandscapeProxy> It(W);It;++It) {
        It->Modify();It->LandscapeMaterial=Material;It->UpdateAllComponentMaterialInstances(true);
        for(const auto& Component:It->LandscapeComponents) {Component->Modify();Component->MarkPackageDirty();}
        It->MarkPackageDirty();++Count;
    }
    return Count>0;
#else
    return false;
#endif
}

AActor* UEcoCreatureAnimationBuilder::SpawnVisualAuditActor(UObject* Context,TSubclassOf<AActor> ActorClass,FTransform Transform)
{
#if WITH_EDITOR
    UWorld* W=GEngine?GEngine->GetWorldFromContextObject(Context,EGetWorldErrorMode::ReturnNull):nullptr;
    if(!W||W->WorldType!=EWorldType::PIE||W->GetNetMode()!=NM_Standalone||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/"))||!ActorClass)return nullptr;
    if(!ActorClass->IsChildOf(AEcoCreatureRepresentationActor::StaticClass())&&!ActorClass->IsChildOf(AStaticMeshActor::StaticClass())&&!ActorClass->IsChildOf(ACameraActor::StaticClass()))return nullptr;
    FActorSpawnParameters Params;Params.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    return W->SpawnActor<AActor>(ActorClass,Transform,Params);
#else
    return nullptr;
#endif
}

bool UEcoCreatureAnimationBuilder::UpdateVisualAuditActor(AEcoCreatureRepresentationActor* Actor,UEcoCreatureAnimationProfile* Profile,FEcoCreatureVisualState State,float DeltaSeconds)
{
#if WITH_EDITOR
    UWorld* W=Actor?Actor->GetWorld():nullptr;
    if(!W||W->WorldType!=EWorldType::PIE||W->GetNetMode()!=NM_Standalone||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/"))||!Profile||!Profile->IsValidProfile())return false;
    if(!Actor->bBound&&!Actor->BindIdentity(State.StableAgentId,State.SpeciesId))return false;
    Actor->AnimationProfile=Profile;State.Sequence=Actor->VisualState.Sequence+1;State.WorldTime=W->GetTimeSeconds();
    State.bHasVitals=true;State.NormalizedHealth=State.NormalizedEnergy=1;
    return Actor->ConsumeVisualState(State,DeltaSeconds);
#else
    return false;
#endif
}

bool UEcoCreatureAnimationBuilder::SetAuditPlayerGait(APawn* Player,int32 GaitIndex)
{
#if WITH_EDITOR
    UWorld* W=Player?Player->GetWorld():nullptr;
    if(!W||W->WorldType!=EWorldType::PIE||W->GetNetMode()!=NM_Standalone||!W->GetPathName().StartsWith(TEXT("/Game/JYU/Maps/"))||!Player->IsPlayerControlled()||GaitIndex<0||GaitIndex>2)return false;
    auto* Bridge=Player->FindComponentByClass<UEcoPlayerEcologyComponent>();if(!Bridge)return false;
    Bridge->SetGait(EEcoPlayerGait(GaitIndex));return Bridge->Gait==EEcoPlayerGait(GaitIndex);
#else
    return false;
#endif
}

#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "EcoCreatureAnimationBuilder.generated.h"
class UAnimBlueprint;
class AEcoCreatureRepresentationActor;
class UBlueprint;
class UEcoCreatureAnimationProfile;
class UEcoCreatureAnimInstance;
class UEcoFootstepAudioSet;
class UMassEntityConfigAsset;
class APawn;
class APlayerController;
class UMaterialInterface;
DECLARE_DELEGATE_RetVal_TwoParams(bool,FEcoBuildPoseGraph,UAnimBlueprint*,UEcoCreatureAnimationProfile*);
ADAPTIVEECOSYSTEM_API FEcoBuildPoseGraph& EcoPoseGraphAuthoring();
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoCreatureAnimationBuilder : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Drives the real movement bridge only in the copied standalone PIE audit. */
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool SetAuditPlayerGait(APawn* Player,int32 GaitIndex);
    /** Temporary passive render fixtures only, restricted to the copied PIE world. */
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static AActor* SpawnVisualAuditActor(UObject* WorldContext,TSubclassOf<AActor> ActorClass,FTransform Transform);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool UpdateVisualAuditActor(AEcoCreatureRepresentationActor* Actor,UEcoCreatureAnimationProfile* Profile,FEcoCreatureVisualState State,float DeltaSeconds);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool PrepareCopiedWorld(UObject* WorldContext);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool SetCopiedLandscapeMaterial(UObject* WorldContext,UMaterialInterface* Material);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool BuildPoseGraph(UAnimBlueprint* Blueprint,UEcoCreatureAnimationProfile* Profile);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool AddPlayerEcologyComponent(UBlueprint* Blueprint,UEcoFootstepAudioSet* AudioSet);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool ConfigureV3EntityConfig(UMassEntityConfigAsset* Config,bool bPredator);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool ConfigureIntegrationGameMode(UBlueprint* Blueprint,TSubclassOf<APawn> Pawn,TSubclassOf<APlayerController> Controller);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor",meta=(WorldContext="WorldContext"))
    static bool ProjectPlacementPoint(UObject* WorldContext,FVector Point,FVector& OutPoint);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool ConfigureBehaviorRepresentation(UBlueprint* Blueprint,UEcoCreatureAnimationProfile* Profile,TSubclassOf<UEcoCreatureAnimInstance> AnimationClass);
};

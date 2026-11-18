#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "EcoCreatureAnimationBuilder.generated.h"
class UAnimBlueprint;
class AEcoCreatureRepresentationActor;
class AEcoCreatureIntegrationSpawner;
class UBlueprint;
class UEcoCreatureAnimationProfile;
class UEcoCreatureAnimInstance;
class UEcoFootstepAudioSet;
class UMassEntityConfigAsset;
class APawn;
class APlayerController;
class UMaterialInterface;
class UFXSystemAsset;
class USkeletalMesh;
class UStaticMesh;
DECLARE_DELEGATE_RetVal_TwoParams(bool,FEcoBuildPoseGraph,UAnimBlueprint*,UEcoCreatureAnimationProfile*);
ADAPTIVEECOSYSTEM_API FEcoBuildPoseGraph& EcoPoseGraphAuthoring();
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoCreatureAnimationBuilder : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintCallable,Category="Creature|Editor") static TArray<FName> GetSkeletalBoneNames(USkeletalMesh* Mesh);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor") static bool ConfigureNaturalPrecipitation(UFXSystemAsset* Asset,UMaterialInterface* Material);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor") static UStaticMesh* CreateNaturalPoolMesh(const FString& AssetPath,int32 Seed);
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
    /** Copied ecosystem map only. Same physical constraints as native movement, no actor/state writes. */
    UFUNCTION(BlueprintCallable,Category="Creature|Editor",meta=(WorldContext="WorldContext"))
    static bool ValidateCopiedGroundSegment(UObject* WorldContext,FVector From,FVector To);
    /** Read-only terrain/water capability check for any designer's open level. */
    UFUNCTION(BlueprintCallable,Category="Creature|Editor",meta=(WorldContext="WorldContext"))
    static bool ValidateHabitatGroundSegment(UObject* WorldContext,FVector From,FVector To);
    /** Sample rule-fauna collision and wading. NAME_None measures terrain without checking region membership. */
    UFUNCTION(BlueprintCallable,Category="Creature|Editor",meta=(WorldContext="WorldContext"))
    static bool ValidateFaunaGroundSegment(UObject* WorldContext,FName RegionId,FName SpeciesId,
        FVector From,FVector To,float BodyScale);
    /** Trace between two already elevated endpoints using rule fauna sight. */
    UFUNCTION(BlueprintCallable,Category="Creature|Editor",meta=(WorldContext="WorldContext"))
    static bool HasFaunaAuditSight(UObject* WorldContext,FVector From,FVector To);
    /** Reposition one founder before the first decision in the owned island PIE comparison. */
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool SetIslandAuditFounderPlacement(AEcoCreatureIntegrationSpawner* Spawner,int64 StableId,
        FName RegionId,FVector Location);
    /** Split one existing plant patch before simulation advances in the owned island PIE comparison. */
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool SplitIslandAuditForage(AEcoCreatureIntegrationSpawner* Spawner,FName PatchId,FName NewId,
        FVector Location,const TArray<FTransform>& OriginalPlants,const TArray<FTransform>& NewPlants);
    UFUNCTION(BlueprintCallable,Category="Creature|Editor")
    static bool ConfigureBehaviorRepresentation(UBlueprint* Blueprint,UEcoCreatureAnimationProfile* Profile,TSubclassOf<UEcoCreatureAnimInstance> AnimationClass);
};

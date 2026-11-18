#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "EcoCreatureRepresentationActor.generated.h"

class USkeletalMeshComponent;
class UStaticMeshComponent;
class UTextRenderComponent;
class USkeletalMesh;
class UBlendSpace;
class UAnimSequence;
class UEcoCreatureAnimationProfile;
class UEcoCreatureAnimInstance;
class UEcoFootstepAudioComponent;
class UEcoHealthBarComponent;

USTRUCT(BlueprintType)
struct FEcoCreatureAppearanceVariant
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere,BlueprintReadWrite) TObjectPtr<USkeletalMesh> Mesh;
    UPROPERTY(EditAnywhere,BlueprintReadWrite) TObjectPtr<UEcoCreatureAnimationProfile> Profile;
    UPROPERTY(EditAnywhere,BlueprintReadWrite) TSubclassOf<UEcoCreatureAnimInstance> AnimationClass;
    UPROPERTY(EditAnywhere,BlueprintReadWrite) FVector MeshScale=FVector::OneVector;
    UPROPERTY(EditAnywhere,BlueprintReadWrite) TArray<TObjectPtr<class UMaterialInterface>> GrowthMaterials;
};

/** Passive Mass representation. No controller, movement component, physics, or logical state writer. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoCreatureRepresentationActor : public AActor
{
	GENERATED_BODY()
public:
	AEcoCreatureRepresentationActor();
	virtual void OnConstruction(const FTransform& Transform) override;
	virtual FVector GetVelocity() const override;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Creature|Visual") TObjectPtr<USkeletalMeshComponent> CreatureMesh;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Creature|Visual") TObjectPtr<USkeletalMeshComponent> ImmatureMesh;
    UPROPERTY(EditDefaultsOnly,Category="Creature|Appearance") bool bContinuousGrowthAppearance=false;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Creature|Visual") TObjectPtr<UStaticMeshComponent> PlaceholderBody;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Creature|Visual") TObjectPtr<UTextRenderComponent> IdentityLabel;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Creature|Audio") TObjectPtr<UEcoFootstepAudioComponent> Footsteps;
	/** Inherited by every species Blueprint. Consumes the existing Mass health DTO only. */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Creature|UI") TObjectPtr<UEcoHealthBarComponent> HealthBar;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Audio") bool bUseFootstepNotifies = false;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual") FName VisualSpeciesId = TEXT("Herbivore");
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") TObjectPtr<USkeletalMesh> VisualMesh;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") TObjectPtr<UBlendSpace> LocomotionBlendSpace;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") TObjectPtr<UAnimSequence> DeathAnimation;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") TObjectPtr<UEcoCreatureAnimationProfile> AnimationProfile;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") TSubclassOf<UEcoCreatureAnimInstance> BehaviorAnimationClass;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") FRotator MeshRotation = FRotator::ZeroRotator;
    /** Actor-space correction for imported mesh pivots. Scales with the represented body. */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") FVector MeshOffset = FVector::ZeroVector;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation", meta=(ClampMin="0.01"))
    float VisualMeshScale = 1.f;
    /** 0 legacy, 1 antlered adult, 2 antlerless adult, 3 immature silhouette. No behavior/sex authority. */
    UPROPERTY(EditDefaultsOnly,Category="Creature|Appearance") TArray<FEcoCreatureAppearanceVariant> AppearanceVariants;
	/** Anatomical forward in the imported mesh's local space; independent of Actor +X. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") FVector MeshForwardAxis = FVector::ForwardVector;
	UFUNCTION(BlueprintPure, Category="Creature|Visual") FVector GetVisualForwardDirection() const;
	/** Native single-node Blend Space playback; can later be replaced by a skeleton-specific AnimBP. */
	void UpdateAnimation();
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual", meta=(ClampMin="0", Units="cm/s")) float IdleSpeed = 5.0f;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual", meta=(ClampMin="1", Units="cm/s")) float RunSpeed = 400.0f;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual", meta=(ClampMin="0")) float TurnInterpolationSpeed = 8.0f;
	/** Bound visual lag even after a reversal. Zero aligns immediately to actual velocity. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual", meta=(ClampMin="0", ClampMax="45", Units="deg")) float MaxFacingLagDegrees = 10.0f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual", meta=(ClampMin="0", ClampMax="70", Units="deg"))
    float FlightPitchLimit = 0.f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual", meta=(ClampMin="0", ClampMax="40", Units="deg"))
    float FlightBankLimit = 0.f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual", meta=(ClampMin="0", ClampMax="60", Units="deg"))
    float SwimPitchLimit = 0.f;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual") bool bAlwaysSwimming = false;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual") bool bSoftenAbruptFacing = false;
	/** Speed x signed turning, not strafing direction. Positive UE yaw is a right turn. */
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation", meta=(ClampMin="1")) float FullTurnRateDegrees = 180.0f;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") float VisualTurnAmount = 0.0f;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") float DirectionDegrees = 0.0f;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual", meta=(ClampMin="1", Units="cm")) float TeleportDistance = 2500.0f;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Visual") FEcoCreatureVisualState VisualState;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Visual") EEcoCreatureVisualMotion VisualMotion = EEcoCreatureVisualMotion::Idle;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Visual") bool bBound = false;
	bool BindIdentity(int64 AgentId, FName SpeciesId);
	void ClearBinding();
	/** C++ bridge only; BP consumes properties/event. Rejects wrong binding and stale/invalid updates. */
	bool ConsumeVisualState(const FEcoCreatureVisualState& State, float DeltaSeconds);
	UFUNCTION(BlueprintImplementableEvent, Category="Creature|Visual") void OnVisualStateUpdated();
protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	void RefreshAppearance();
    void ApplyAppearance(uint8 Variant);
    uint8 AppliedAppearance=255;
	float VisualYawRateDegrees = 0.f;
	float VisualPitchRateDegrees = 0.f;
	float VisualRollRateDegrees = 0.f;
	float ReversalDirection = 0.f;
	bool bHasMotionHeading = false;
	double LastFacingAuditTime = -1.0;
	FTimerHandle AlarmTimer;
	double LastAlarmTime = -10;
	void PlayAlarmCue();
private:
    void UpdateGroundSupport(float DeltaSeconds, bool bSnap);
    void ApplyGroundSupport(USkeletalMeshComponent& Mesh, float Lift) const;
    void FitGroundSupport(USkeletalMeshComponent* Mesh);
    void ResetGroundSupport();
    FDelegateHandle MainPoseFinalized;
    FDelegateHandle ImmaturePoseFinalized;
    FQuat GroundSupportRotation = FQuat::Identity;
    FVector GroundSupportPoint = FVector::ZeroVector;
    FVector GroundSupportNormal = FVector::UpVector;
    float GroundSupportBlend = 0.f;
    float MainGroundLift = 0.f;
    float ImmatureGroundLift = 0.f;
    bool bGroundSupportEvidence = false;
    bool bGroundSupportSnap = false;
};

UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoWolfRepresentation : public AEcoCreatureRepresentationActor
{
	GENERATED_BODY()
public: AEcoWolfRepresentation();
};

UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoHerbivoreRepresentation : public AEcoCreatureRepresentationActor
{
	GENERATED_BODY()
public: AEcoHerbivoreRepresentation();
};

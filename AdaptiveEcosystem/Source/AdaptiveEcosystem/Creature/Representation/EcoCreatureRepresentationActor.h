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
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Creature|Visual") TObjectPtr<UStaticMeshComponent> PlaceholderBody;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Creature|Visual") TObjectPtr<UTextRenderComponent> IdentityLabel;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Visual") FName VisualSpeciesId = TEXT("Herbivore");
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") TObjectPtr<USkeletalMesh> VisualMesh;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") TObjectPtr<UBlendSpace> LocomotionBlendSpace;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") TObjectPtr<UAnimSequence> DeathAnimation;
	UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Creature|Animation") FRotator MeshRotation = FRotator::ZeroRotator;
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
	void RefreshAppearance();
	double LastFacingAuditTime = -1.0;
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

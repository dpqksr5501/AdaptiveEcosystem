#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "EcoCreatureAnimInstance.generated.h"

/** AnimBP parent for Actor (not Character) representation; all inputs come from accepted visual snapshots. */
UCLASS(Transient, Blueprintable)
class ADAPTIVEECOSYSTEM_API UEcoCreatureAnimInstance : public UAnimInstance
{
	GENERATED_BODY()
public:
	virtual void NativeInitializeAnimation() override;
	virtual void NativeUpdateAnimation(float DeltaSeconds) override;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") float SpeedCmPerSecond = 0.0f;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") int32 AnimationIndex = 0;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") float DirectionDegrees = 0.0f;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") float TurnAmount = 0.0f;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") bool bAlive = false;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") bool bEating = false;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") bool bPursuingPrey = false;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") EEcoSpeciesActivity Activity = EEcoSpeciesActivity::Hold;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") EEcoCreatureVisualMotion VisualMotion = EEcoCreatureVisualMotion::Idle;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") float GroundIKAlpha=0;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") FVector GroundPoint0=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") FVector GroundPoint1=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") FVector GroundPoint2=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") FVector GroundPoint3=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") float GroundValid0=0;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") float GroundValid1=0;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") float GroundValid2=0;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") float GroundValid3=0;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") FVector GroundRootPoint=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") FVector GroundUp=FVector::UpVector;
    UPROPERTY(BlueprintReadOnly,Transient,Category="Creature|IK") float GroundWorldToComponent=1;
private:
    float PoseAgeSeconds=0;
    float SensoryAlertSeconds=0;
    EEcoSenseSource PreviousSense=EEcoSenseSource::None;
};

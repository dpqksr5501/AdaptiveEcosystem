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
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") float DirectionDegrees = 0.0f;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") bool bAlive = false;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") bool bEating = false;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") bool bPursuingPrey = false;
	UPROPERTY(BlueprintReadOnly, Transient, Category="Creature|Animation") EEcoCreatureVisualMotion VisualMotion = EEcoCreatureVisualMotion::Idle;
};

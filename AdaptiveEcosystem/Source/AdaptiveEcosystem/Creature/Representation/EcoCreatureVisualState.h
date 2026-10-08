#pragma once

#include "CoreMinimal.h"
#include "EcoCreatureVisualState.generated.h"

UENUM(BlueprintType)
enum class EEcoCreatureVisualMotion : uint8 { Idle, Walk, Run, Eating, Dead };

/** Representation-only input. Not a policy observation, movement command, or replication transport. */
USTRUCT(BlueprintType)
struct FEcoCreatureVisualState
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") int64 StableAgentId = 0;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") FName SpeciesId = NAME_None;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") FName RegionId = NAME_None;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") int64 Sequence = 0;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") double WorldTime = 0.0;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") FVector Position = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") FVector Velocity = FVector::ZeroVector;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") bool bHasVitals = false;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") float NormalizedHealth = 0.0f;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") float NormalizedEnergy = 0.0f;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") bool bAlive = true;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") bool bEating = false;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") bool bPursuingPrey = false;
	UPROPERTY(BlueprintReadOnly, Category="Creature|Visual") bool bDiscontinuity = false;
	bool IsValid() const;
};

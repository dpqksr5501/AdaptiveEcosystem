// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoIds.h"
#include "EcoEventTypes.generated.h"

/**
 * Game-thread reconciliation request produced from buffered Mass interactions.
 * This is an active-runtime contract and intentionally contains no UObject or
 * FMassEntityHandle reference.
 */
USTRUCT(BlueprintType)
struct FEcoFoodConsumptionRequest
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	FName RegionId = NAME_None;

	/** FEcoAgentId value. Zero represents an unknown or invalid instigator. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	int64 StableAgentId = EcoIds::InvalidAgentId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event", meta = (ClampMin = "0.0"))
	float RequestedAmount = 0.0f;
};

/** Authoritative predation event applied to regional threat history. */
USTRUCT(BlueprintType)
struct FEcoPredationEvent
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	FName RegionId = NAME_None;

	/** FEcoAgentId value for the predator, when known. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	int64 PredatorStableAgentId = EcoIds::InvalidAgentId;

	/** FEcoAgentId value for the prey, when known. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	int64 PreyStableAgentId = EcoIds::InvalidAgentId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event", meta = (ClampMin = "0.0"))
	float ThreatMagnitude = 0.25f;
};

/** Low-frequency regional aggregate produced from authoritative Mass state. */
USTRUCT(BlueprintType)
struct FEcoRegionPopulationSnapshot
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	FName RegionId = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event", meta = (ClampMin = "0"))
	int32 Population = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float AverageEnergy = 0.0f;
};

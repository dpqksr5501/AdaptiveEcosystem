// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoRepresentationTypes.h"
#include "EcologyNetworkTypes.generated.h"

/**
 * Active-runtime network contracts. These DTOs carry only authoritative Mass or
 * ecology summaries and intentionally contain no Legacy Evolution profile.
 * Subsystems are local services, not replication transports; these values belong
 * on GameState or a dedicated replicated actor/component.
 */
USTRUCT(BlueprintType)
struct FReplicatedEcoAgentState
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	int32 StateRevision = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	FEcoRepresentationSnapshot Snapshot;
};

/**
 * Low-frequency replicated region overview for clients/UI.
 */
USTRUCT(BlueprintType)
struct FReplicatedRegionSummary
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	FName RegionId;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	int32 WorldEpoch = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	int32 SummaryRevision = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	int32 Population = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float FoodAmount = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float FoodCapacity = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float PredationHistory = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float AverageEnergy = 0.0f;
};

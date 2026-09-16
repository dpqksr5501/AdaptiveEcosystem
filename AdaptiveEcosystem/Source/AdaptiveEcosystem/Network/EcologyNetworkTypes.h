// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoDataContracts.h"
#include "EcologyNetworkTypes.generated.h"

/**
 * Replicated species evolution state sent infrequently from Server to Clients.
 * Designed to be held by GameState or a dedicated replicated actor.
 * 
 * NOTE (Architecture Boundary):
 * Subsystems are NOT replication transports. Do not attempt to replicate
 * UEcologyServerSubsystem or UEcologyWorldSubsystem. Place replicated states in
 * AGameStateBase or replicated actor components.
 */
USTRUCT(BlueprintType)
struct FReplicatedSpeciesState
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	FName RegionId;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	FName SpeciesId;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	int32 Generation = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	int64 ProfileRevision = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	FSpeciesEvolutionProfile Profile;
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
	float Resource = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float Risk = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float AverageEnergy = 0.0f;
};

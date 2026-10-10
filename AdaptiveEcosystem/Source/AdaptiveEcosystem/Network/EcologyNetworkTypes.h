// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoRepresentationTypes.h"
#include "Core/EcoTimeTypes.h"
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
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	int32 ResidentCount = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	int32 OutboundCount = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	int32 IncomingCount = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	int32 ProjectedPopulation = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	int32 EcologicalComfortPopulation = 64;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	float CrowdingRatio = 0.0f;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	float FoodSatisfaction = 1.0f;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	bool bPressureActive = false;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	double PressureSince = -1.0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	int64 StarvationDeaths = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Migration") int64 MigrationInCount = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Migration") int64 MigrationOutCount = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Migration") int64 OvercrowdingDeparturesCompleted = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Pressure")
	int64 ExternalDeaths = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float FoodAmount = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float FoodCapacity = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float PredationHistory = 0.0f;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Migration")
	int32 TravelingCount = 0;
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Ecology|Migration")
	int32 WaitingCount = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network")
	float AverageEnergy = 0.0f;
};

/** One replication property prevents mixing separately delivered clock/resource/population revisions. */
USTRUCT(BlueprintType)
struct FEcoCompletedWorldSummary
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Network")
	FEcoServerTimeSnapshot Time;
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Network")
	int64 StepId = 0;
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Network")
	int32 Revision = 0;
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Network")
	TArray<FReplicatedRegionSummary> Regions;
};

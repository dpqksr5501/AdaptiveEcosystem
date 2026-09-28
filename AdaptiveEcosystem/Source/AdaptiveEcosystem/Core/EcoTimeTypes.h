#pragma once

#include "CoreMinimal.h"
#include "Core/EcoRegionTypes.h"
#include "EcoTimeTypes.generated.h"

/** A phase evaluated at a server elapsed time. No transport or subsystem ownership. */
USTRUCT(BlueprintType)
struct FEcoDayCycleState
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Time")
	int64 CycleId = 0;
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Time")
	EEcoDayPhase Phase = EEcoDayPhase::Day;
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Time")
	double PhaseStartSeconds = 0.0;
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Time")
	double PhaseEndSeconds = 60.0;
};

USTRUCT(BlueprintType)
struct FEcoServerTimeSnapshot
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Time")
	int32 WorldEpoch = 0;
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Time")
	double ServerTimeSeconds = 0.0;
	UPROPERTY(BlueprintReadOnly, Category="Ecology|Time")
	FEcoDayCycleState DayCycle;
};

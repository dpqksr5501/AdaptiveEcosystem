#pragma once

#include "CoreMinimal.h"
#include "Core/EcoTimeTypes.h"
#include "EcoSpawnTypes.generated.h"

USTRUCT(BlueprintType)
struct FEcoSpawnScheduleSettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ecology|Spawn", meta=(ClampMin="0.25"))
	double DayIntervalSeconds = 30.0;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ecology|Spawn", meta=(ClampMin="0.25"))
	double NightIntervalSeconds = 20.0;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ecology|Spawn", meta=(ClampMin="0"))
	int32 DayCount = 4;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ecology|Spawn", meta=(ClampMin="0"))
	int32 NightCount = 6;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Ecology|Spawn", meta=(ClampMin="1"))
	int32 RegionPopulationLimit = 64;
	bool IsValid() const
	{
		return FMath::IsFinite(DayIntervalSeconds) && DayIntervalSeconds >= 0.25
			&& FMath::IsFinite(NightIntervalSeconds) && NightIntervalSeconds >= 0.25
			&& DayCount >= 0 && NightCount >= 0 && RegionPopulationLimit > 0;
	}
};

/** Server-local value request. No UObject, entity handle or replication ownership. */
struct FEcoSpawnRequest
{
	int64 RequestId = 0;
	int32 WorldEpoch = 0;
	int64 CycleId = 0;
	EEcoDayPhase Phase = EEcoDayPhase::Day;
	int64 WaveIndex = 0;
	FName RegionId;
	int32 Count = 0;
	double ScheduledTime = 0.0;
	bool bInitial = false;
};

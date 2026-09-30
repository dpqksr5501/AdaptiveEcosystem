#pragma once

#include "CoreMinimal.h"
#include "Core/EcoEventTypes.h"
#include "EcoResourceTypes.generated.h"

/** Immutable for one play session. Entity lifetime owns the resulting reservations. */
USTRUCT(BlueprintType)
struct FEcoFeedingSettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, Category="Feeding")
	bool bEnabled = true;
	UPROPERTY(EditAnywhere, Category="Feeding", meta=(ClampMin="0.25"))
	double FirstFeedDelaySeconds = 20.0;
	UPROPERTY(EditAnywhere, Category="Feeding", meta=(ClampMin="0.25"))
	double IntervalSeconds = 10.0;
	UPROPERTY(EditAnywhere, Category="Feeding", meta=(ClampMin="0.0"))
	float Amount = 1.0f;
	bool IsValid() const
	{
		return FMath::IsFinite(FirstFeedDelaySeconds) && FirstFeedDelaySeconds >= 0.25
			&& FMath::IsFinite(IntervalSeconds) && IntervalSeconds >= 0.25
			&& FMath::IsFinite(Amount) && Amount > 0.0f;
	}
};

/** Ecology event settings. Phase fraction adapts to a future variable-length day provider. */
USTRUCT(BlueprintType)
struct FEcoFoodEventSettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, Category="Food Event")
	bool bEnabled = true;
	UPROPERTY(EditAnywhere, Category="Food Event")
	FName RegionId = TEXT("Forest_A");
	/** 0 = phase start; must be less than 1 (phase end is exclusive). */
	UPROPERTY(EditAnywhere, Category="Food Event", meta=(ClampMin="0.0", ClampMax="0.999"))
	double PhaseFraction = 25.0 / 60.0;
	UPROPERTY(EditAnywhere, Category="Food Event", meta=(ClampMin="0.0"))
	float FoodLoss = 40.0f;
	bool IsValid() const
	{
		return !bEnabled || (!RegionId.IsNone() && FMath::IsFinite(PhaseFraction)
			&& PhaseFraction >= 0.0 && PhaseFraction < 1.0 && FMath::IsFinite(FoodLoss) && FoodLoss >= 0.0f);
	}
};

/** Server-local envelopes. No UObject/EntityHandle crosses the Mass/Ecology boundary. */
struct FEcoFeedRequest
{
	FEcoFoodConsumptionRequest Food;
	int32 WorldEpoch = 0;
	int64 StepId = 0;
	int32 RegionIndex = INDEX_NONE;
	double DueTime = 0.0;
};

struct FEcoFeedResult
{
	FEcoFeedRequest Request;
	double GrantedAmount = 0.0;
};

/** Published only after the whole resource step has completed. */
struct FEcoResourceSnapshot
{
	int32 WorldEpoch = 0;
	int64 StepId = 0;
	double Time = 0.0;
	FName RegionId;
	int32 RegionIndex = INDEX_NONE;
	float Food = 0.0f;
	float Capacity = 0.0f;
	bool bDepleted = false;
	double EventLoss = 0.0;
	double Consumed = 0.0;
	double RoundingAdjustment = 0.0;
};

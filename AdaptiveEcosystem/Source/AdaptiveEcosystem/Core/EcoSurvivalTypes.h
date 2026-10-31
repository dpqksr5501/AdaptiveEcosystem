#pragma once

#include "CoreMinimal.h"
#include "EcoSurvivalTypes.generated.h"

UENUM(BlueprintType)
enum class EEcoDeathCause : uint8 { None, Starvation, ExternalDamage, Predation };

/** Session-immutable Box baseline. Energy units/second, HP units/second, Food -> Energy. */
USTRUCT(BlueprintType)
struct FEcoSurvivalSettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, Category="Survival") bool bEnabled = true;
	UPROPERTY(EditAnywhere, Category="Survival", meta=(ClampMin="0.0")) float BaseMetabolism = 1.0f;
	UPROPERTY(EditAnywhere, Category="Survival", meta=(ClampMin="0.0")) float TravelMetabolism = 0.5f;
	UPROPERTY(EditAnywhere, Category="Survival", meta=(ClampMin="0.0")) float FoodEnergyGain = 12.0f;
	UPROPERTY(EditAnywhere, Category="Survival", meta=(ClampMin="0.0")) double StarvationGraceSeconds = 5.0;
	UPROPERTY(EditAnywhere, Category="Survival", meta=(ClampMin="0.01")) float StarvationDamagePerSecond = 10.0f;
	UPROPERTY(EditAnywhere, Category="Survival", meta=(ClampMin="0.25")) double DeadRetentionSeconds = 2.0;
	bool IsValid() const
	{
		return FMath::IsFinite(BaseMetabolism) && BaseMetabolism >= 0 && FMath::IsFinite(TravelMetabolism) && TravelMetabolism >= 0
			&& FMath::IsFinite(FoodEnergyGain) && FoodEnergyGain >= 0 && FMath::IsFinite(StarvationGraceSeconds) && StarvationGraceSeconds >= 0
			&& FMath::IsFinite(StarvationDamagePerSecond) && StarvationDamagePerSecond > 0
			&& FMath::IsFinite(DeadRetentionSeconds) && DeadRetentionSeconds >= 0.25;
	}
};

USTRUCT(BlueprintType)
struct FEcoOvercrowdingSettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, Category="Pressure") bool bEnabled = true;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="1.0")) double ForecastSeconds = 30.0;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="1.0")) float EnterCrowdingRatio = 1.10f;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="0.0")) float ExitCrowdingRatio = 0.95f;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="0.0", ClampMax="1.0")) float EnterFoodSatisfaction = 0.75f;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="0.0", ClampMax="1.0")) float ExitFoodSatisfaction = 0.95f;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="0.0")) double SustainSeconds = 3.0;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="0.0")) double MinimumResidenceSeconds = 10.0;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="0.0")) double RetrySeconds = 3.0;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="1")) int32 MaxDeparturesPerRegion = 2;
	UPROPERTY(EditAnywhere, Category="Pressure", meta=(ClampMin="0.01")) float MinimumImprovement = 0.1f;
	UPROPERTY(EditAnywhere, Category="Pressure") bool bCheckTravelSurvival = true;
	bool IsValid() const
	{
		return FMath::IsFinite(ForecastSeconds) && ForecastSeconds >= 1 && FMath::IsFinite(EnterCrowdingRatio) && EnterCrowdingRatio >= 1
			&& FMath::IsFinite(ExitCrowdingRatio) && ExitCrowdingRatio >= 0 && ExitCrowdingRatio < EnterCrowdingRatio
			&& FMath::IsFinite(EnterFoodSatisfaction) && EnterFoodSatisfaction >= 0 && EnterFoodSatisfaction < 1
			&& FMath::IsFinite(ExitFoodSatisfaction) && ExitFoodSatisfaction > EnterFoodSatisfaction && ExitFoodSatisfaction <= 1
			&& FMath::IsFinite(SustainSeconds) && SustainSeconds >= 0 && FMath::IsFinite(MinimumResidenceSeconds) && MinimumResidenceSeconds >= 0
			&& FMath::IsFinite(RetrySeconds) && RetrySeconds >= 0 && MaxDeparturesPerRegion > 0
			&& FMath::IsFinite(MinimumImprovement) && MinimumImprovement > 0;
	}
};

struct FEcoDeathOutcome
{
	int32 WorldEpoch = 0;
	int64 StepId = 0;
	int64 StableAgentId = 0;
	FName RegionId;
	FName SpeciesId;
	EEcoDeathCause Cause = EEcoDeathCause::None;
	double Time = 0.0;
	int64 PredatorStableAgentId = 0;
};

/** Ephemeral decision input; count source is always authoritative Mass. */
struct FEcoMigrationPressureSnapshot
{
	int32 Population = 0;
	int32 Outbound = 0;
	int32 Incoming = 0;
	int32 ComfortPopulation = 64;
	bool bPressureActive = false;
	double PressureSince = -1.0;
	int32 Projected() const { return FMath::Max(0, Population - Outbound + Incoming); }
};

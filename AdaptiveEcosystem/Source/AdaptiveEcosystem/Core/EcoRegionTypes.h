// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoIds.h"
#include "EcoRegionTypes.generated.h"

/**
 * World day-night cycle phase.
 */
UENUM(BlueprintType)
enum class EEcoDayPhase : uint8
{
	Day      UMETA(DisplayName = "Day"),
	Dusk     UMETA(DisplayName = "Dusk"),
	Night    UMETA(DisplayName = "Night"),
	Dawn     UMETA(DisplayName = "Dawn")
};

/**
 * Macro weather state for regional environmental conditions.
 */
UENUM(BlueprintType)
enum class EEcoWeatherState : uint8
{
	Clear    UMETA(DisplayName = "Clear"),
	Rain     UMETA(DisplayName = "Rain"),
	Storm    UMETA(DisplayName = "Storm"),
	Drought  UMETA(DisplayName = "Drought")
};

/**
 * Physical environment parameters for a specific region.
 * Owned and updated by World / Level layer (e.g. AEcologyRegion, DayNight/Weather systems).
 */
USTRUCT(BlueprintType)
struct FRegionEnvironmentState
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	float Temperature = 20.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	float Humidity = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	float Rainfall = 0.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	EEcoDayPhase DayPhase = EEcoDayPhase::Day;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	EEcoWeatherState WeatherState = EEcoWeatherState::Clear;

	// Deprecated legacy fields retained for backward compatibility
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment|Legacy", meta = (DeprecatedProperty, DeprecationMessage = "Use FRegionEcologyState for authoritative biomass"))
	float VegetationDensity = 0.7f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment|Legacy", meta = (DeprecatedProperty, DeprecationMessage = "Use FRegionEcologyState for authoritative food amount"))
	float FoodAvailability = 0.8f;
};

/**
 * Authoritative regional ecology and resource state.
 * Owned and updated exclusively by Server / Ecology Simulation Subsystem.
 */
USTRUCT(BlueprintType)
struct FRegionEcologyState
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|State")
	FName RegionId = NAME_None;

	/** Current consumable food biomass within this region */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|State", meta = (ClampMin = "0.0"))
	float FoodAmount = 1000.0f;

	/** Maximum food carrying capacity for this region */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|State", meta = (ClampMin = "0.0"))
	float FoodCapacity = 2000.0f;

	/** Base food regeneration rate per second */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|State")
	float FoodRegenerationRate = 10.0f;

	/**
	 * Accumulated predation / hunting pressure history (0.0 .. 1.0).
	 * Increases on kill events and exponentially decays over time.
	 */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|State", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float PredationHistory = 0.0f;

	/** Authoritative alive logical entity count in this region */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|State")
	int32 Population = 0;

	/** Normalized average energy of living entities in this region */
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Ecology|State", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float AverageEnergy = 1.0f;
};

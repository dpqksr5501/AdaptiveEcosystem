// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "Core/EcoResourceTypes.h"
#include "Core/EcoMigrationTypes.h"
#include "EcoRuntimeSettings.generated.h"

/** Project-level switches for selecting explicitly opt-in legacy runtime paths. */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "Adaptive Ecosystem"))
class ADAPTIVEECOSYSTEM_API UEcoRuntimeSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	UPROPERTY(Config, EditAnywhere, Category="M3|Migration")
	FEcoMigrationSettings Migration;
	/** Read-only region summaries on host/client; authoritative agent IDs and arrows on host. */
	UPROPERTY(Config, EditAnywhere, Category="M3|Editor Test")
	bool bDrawMigrationDebug = true;
	UEcoRuntimeSettings()
	{
		DayFoodEvent.bEnabled = false;
		NightFoodEvent.RegionId = TEXT("Forest_B");
		NightFoodEvent.PhaseFraction = 0.25;
	}
	/** Restart PIE after changing simulation settings. */
	UPROPERTY(Config, EditAnywhere, Category="M3|Resources")
	FEcoFeedingSettings Feeding;
	UPROPERTY(Config, EditAnywhere, Category="M3|Resources")
	FEcoFoodEventSettings DayFoodEvent;
	UPROPERTY(Config, EditAnywhere, Category="M3|Resources")
	FEcoFoodEventSettings NightFoodEvent;
	UPROPERTY(Config, EditAnywhere, Category="M3|Resources")
	bool bPrintResourceChanges = true;
	UPROPERTY(Config, EditAnywhere, Category="M3|Population")
	bool bEnableSpawnWaves = true;
	UPROPERTY(Config, EditAnywhere, Category="M3|Population")
	bool bPrintDailyPopulation = true;
	UPROPERTY(Config, EditAnywhere, Category="M3|Population")
	bool bPrintDailyPopulationToScreen = true;
	/** Fixed-cycle fallback; a registered server day-cycle provider can replace phase evaluation. */
	UPROPERTY(Config, EditAnywhere, Category="M3|Clock", meta=(ClampMin="0.25"))
	double DayDurationSeconds = 60.0;
	UPROPERTY(Config, EditAnywhere, Category="M3|Clock", meta=(ClampMin="0.25"))
	double NightDurationSeconds = 60.0;
	UPROPERTY(Config, EditAnywhere, Category="M3|Clock")
	bool bPrintServerTime = true;
	UPROPERTY(Config, EditAnywhere, Category="M3|Clock")
	bool bPrintServerTimeToScreen = true;
	UPROPERTY(Config, EditAnywhere, Category="M3|Clock", meta=(ClampMin="0.25"))
	double ServerTimePrintInterval = 1.0;
	UPROPERTY(Config, EditAnywhere, Category="M3|Population", meta=(ClampMin="1"))
	int32 GlobalPopulationLimit = 128;
	UPROPERTY(Config, EditAnywhere, Category="M3|Population", meta=(ClampMin="1"))
	int32 RequiredRegionCount = 2;

	/**
	 * Creates the legacy LLM trait-evolution subsystem in authoritative game worlds.
	 * Disabled by default so the PPO + Mass runtime remains the only active path.
	 * A PIE session must be restarted after changing this value.
	 */
	UPROPERTY(Config, EditAnywhere, Category = "Legacy", meta = (DisplayName = "Enable Legacy Evolution Subsystem"))
	bool bEnableLegacyEvolutionSubsystem = false;
};

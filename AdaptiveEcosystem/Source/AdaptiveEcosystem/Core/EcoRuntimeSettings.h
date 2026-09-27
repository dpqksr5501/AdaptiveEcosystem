// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Engine/DeveloperSettings.h"
#include "EcoRuntimeSettings.generated.h"

/** Project-level switches for selecting explicitly opt-in legacy runtime paths. */
UCLASS(Config = Game, DefaultConfig, meta = (DisplayName = "Adaptive Ecosystem"))
class ADAPTIVEECOSYSTEM_API UEcoRuntimeSettings : public UDeveloperSettings
{
	GENERATED_BODY()

public:
	/**
	 * Creates the legacy LLM trait-evolution subsystem in authoritative game worlds.
	 * Disabled by default so the PPO + Mass runtime remains the only active path.
	 * A PIE session must be restarted after changing this value.
	 */
	UPROPERTY(Config, EditAnywhere, Category = "Legacy", meta = (DisplayName = "Enable Legacy Evolution Subsystem"))
	bool bEnableLegacyEvolutionSubsystem = false;
};

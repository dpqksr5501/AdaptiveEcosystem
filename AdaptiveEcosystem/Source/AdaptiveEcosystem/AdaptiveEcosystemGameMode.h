// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "AdaptiveEcosystemGameMode.generated.h"

/** Server-only coordinator for world lifecycle and Mass network bootstrap. */
UCLASS(Abstract)
class ADAPTIVEECOSYSTEM_API AAdaptiveEcosystemGameMode : public AGameModeBase
{
	GENERATED_BODY()

public:
	AAdaptiveEcosystemGameMode();

	virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;
	virtual void InitGameState() override;
	virtual void StartPlay() override;
	virtual void PostLogin(APlayerController* NewPlayer) override;
	virtual void Logout(AController* Exiting) override;

protected:
	/** Legacy asset field. Admission now uses project EcoSessionSettings on the server. */
	UPROPERTY(meta = (DeprecatedProperty, DeprecationMessage = "Use EcoSessionSettings.MaxRemoteClients."))
	int32 DefaultMaxPlayers = 11;

	/** Keep the world in BootstrappingMass when no configured bootstrap succeeds. */
	UPROPERTY(EditDefaultsOnly, Category = "Ecology|Mass")
	bool bRequireMassNetworkBootstrap = false;

private:
	void RefreshConnectedPlayerCount();

	int32 ConfiguredMaxPlayers = 11;
	int32 WorldEpoch = 1;
};


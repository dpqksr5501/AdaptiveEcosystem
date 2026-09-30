// Copyright Epic Games, Inc. All Rights Reserved.

#include "AdaptiveEcosystemGameMode.h"

#include "AdaptiveEcosystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "EngineUtils.h"
#include "GameFramework/GameSession.h"
#include "Kismet/GameplayStatics.h"
#include "Mass/EcoMassNetworkBootstrap.h"
#include "Network/EcoGameState.h"

AAdaptiveEcosystemGameMode::AAdaptiveEcosystemGameMode()
{
	GameStateClass = AEcoGameState::StaticClass();
}

void AAdaptiveEcosystemGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);

	ConfiguredMaxPlayers = FMath::Max(1, UGameplayStatics::GetIntOption(Options, TEXT("MaxPlayers"), DefaultMaxPlayers));
	WorldEpoch = FMath::Max(1, static_cast<int32>(GetTypeHash(FGuid::NewGuid()) & MAX_int32));
	if (GameSession)
	{
		GameSession->MaxPlayers = ConfiguredMaxPlayers;
	}
}

void AAdaptiveEcosystemGameMode::InitGameState()
{
	Super::InitGameState();

	if (AEcoGameState* EcoGameState = GetGameState<AEcoGameState>())
	{
		EcoGameState->InitializeAuthorityState(WorldEpoch, ConfiguredMaxPlayers);
	}
}

void AAdaptiveEcosystemGameMode::StartPlay()
{
	Super::StartPlay();

	AEcoGameState* EcoGameState = GetGameState<AEcoGameState>();
	if (!ensure(EcoGameState))
	{
		return;
	}

	EcoGameState->SetWorldPhase(EEcoWorldPhase::BootstrappingMass);
	RefreshConnectedPlayerCount();

	if (!GetWorld()->GetSubsystem<UEcologySimulationSubsystem>())
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("Authoritative ecology subsystem is unavailable; Mass bootstrap cannot own stable IDs."));
		return;
	}

	bool bFoundBootstrap = false;
	bool bMassReady = false;
	for (TActorIterator<AEcoMassNetworkBootstrap> It(GetWorld()); It; ++It)
	{
		bFoundBootstrap = true;
		bMassReady |= It->InitializeMassNetwork();
	}

	EcoGameState->SetMassReplicationReady(bMassReady);
	if (bMassReady || !bRequireMassNetworkBootstrap)
	{
		EcoGameState->SetWorldPhase(EEcoWorldPhase::Running);
	}
	else
	{
		UE_LOG(LogAdaptiveEcosystem, Error,
			TEXT("Mass network bootstrap is required but %s."),
			bFoundBootstrap ? TEXT("no configured bootstrap succeeded") : TEXT("no bootstrap actor exists in the level"));
	}
}

void AAdaptiveEcosystemGameMode::PostLogin(APlayerController* NewPlayer)
{
	Super::PostLogin(NewPlayer);
	RefreshConnectedPlayerCount();
}

void AAdaptiveEcosystemGameMode::Logout(AController* Exiting)
{
	Super::Logout(Exiting);
	RefreshConnectedPlayerCount();
}

void AAdaptiveEcosystemGameMode::RefreshConnectedPlayerCount()
{
	if (AEcoGameState* EcoGameState = GetGameState<AEcoGameState>())
	{
		EcoGameState->SetConnectedPlayerCount(GetNumPlayers());
	}
}

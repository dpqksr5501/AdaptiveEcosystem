// Copyright Epic Games, Inc. All Rights Reserved.

#include "AdaptiveEcosystemGameMode.h"

#include "AdaptiveEcosystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "EngineUtils.h"
#include "GameFramework/GameSession.h"
#include "Kismet/GameplayStatics.h"
#include "Mass/EcoMassNetworkBootstrap.h"
#include "Mass/EcoMassLifecycleSubsystem.h"
#include "Network/EcoGameState.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "GameFramework/PlayerController.h"
#include "Network/Session/EcoGameSession.h"
#include "Network/Session/EcoSessionSettings.h"

AAdaptiveEcosystemGameMode::AAdaptiveEcosystemGameMode()
{
	GameStateClass = AEcoGameState::StaticClass();
	GameSessionClass = AEcoGameSession::StaticClass();
}

void AAdaptiveEcosystemGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
	Super::InitGame(MapName, Options, ErrorMessage);

	ConfiguredMaxPlayers = GetDefault<UEcoSessionSettings>()->TotalPlayers(GetNetMode() == NM_DedicatedServer);
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
    bool bIntegration = false;
    for (TActorIterator<AEcoCreatureIntegrationSpawner> It(GetWorld()); It; ++It) bIntegration = true;
    if (auto* State = GetGameState<AEcoGameState>()) State->SetWorldPhase(EEcoWorldPhase::BootstrappingMass);
    Super::StartPlay();
    // Integration owns its clock, population and readiness, including asynchronous terrain loading.
    if (bIntegration) { RefreshConnectedPlayerCount(); return; }

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
	for (TActorIterator<AEcoMassNetworkBootstrap> It(GetWorld()); It; ++It)
	{
		bFoundBootstrap = true;
	}
	UEcoMassLifecycleSubsystem* Lifecycle = GetWorld()->GetSubsystem<UEcoMassLifecycleSubsystem>();
	const bool bMassReady = bFoundBootstrap && Lifecycle && Lifecycle->InitializePopulation();

	EcoGameState->SetMassReplicationReady(bMassReady);
	if (bMassReady || (!bFoundBootstrap && !bRequireMassNetworkBootstrap))
	{
        if (!bFoundBootstrap) EcoGameState->EnablePresentationClock();
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
    int32 Remaining = 0;
    for (auto It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
        if (const auto* PC = It->Get(); PC && PC != Exiting && PC->PlayerState && !PC->IsActorBeingDestroyed()) ++Remaining;
    if (auto* State = GetGameState<AEcoGameState>()) State->SetConnectedPlayerCount(Remaining);
}

void AAdaptiveEcosystemGameMode::RefreshConnectedPlayerCount()
{
	if (AEcoGameState* EcoGameState = GetGameState<AEcoGameState>())
	{
		EcoGameState->SetConnectedPlayerCount(GetNumPlayers());
	}
}

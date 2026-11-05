#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Network/Session/EcoGameSession.h"
#include "Network/EcoGameState.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

void AEcoCreatureIntegrationGameMode::PostLogin(APlayerController* NewPlayer)
{
    Super::PostLogin(NewPlayer);
    if (auto* State = GetGameState<AEcoGameState>()) State->SetConnectedPlayerCount(GetNumPlayers());
    UE_LOG(LogTemp, Log, TEXT("[EcoSession][Admission] Players=%d Capacity=%d NetMode=%d"),
        GetNumPlayers(), GameSession ? GameSession->MaxPlayers : 0, int32(GetNetMode()));
}

void AEcoCreatureIntegrationGameMode::Logout(AController* Exiting)
{
    Super::Logout(Exiting);
    // Logout runs before the controller is destroyed, so GetNumPlayers can still include Exiting.
    int32 Remaining = 0;
    for (auto It = GetWorld()->GetPlayerControllerIterator(); It; ++It)
        if (const APlayerController* Player = It->Get(); Player && Player != Exiting &&
            Player->PlayerState && !Player->IsActorBeingDestroyed()) ++Remaining;
    if (auto* State = GetGameState<AEcoGameState>()) State->SetConnectedPlayerCount(Remaining);
    UE_LOG(LogTemp, Log, TEXT("[EcoSession][Departure] Players=%d"), Remaining);
}


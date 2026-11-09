#include "Player/EcoPlayerCombatComponent.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "EngineUtils.h"
#include "GameFramework/Pawn.h"

bool UEcoPlayerCombatComponent::TryQueueMeleeStrike()
{
    auto* Pawn = Cast<APawn>(GetOwner());
    if (!Pawn || !Pawn->HasAuthority() || !Pawn->IsPlayerControlled())
        return false;

    AEcoCreatureIntegrationSpawner* Spawner = nullptr;
    for (TActorIterator<AEcoCreatureIntegrationSpawner> It(GetWorld()); It; ++It)
    {
        if (!It->bEnableEcosystemLife)
            continue;
        if (Spawner)
            return false;
        Spawner = *It;
    }

    return Spawner && Spawner->QueuePlayerStrike(*Pawn);
}

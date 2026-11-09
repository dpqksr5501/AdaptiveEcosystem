#pragma once

#include "Components/ActorComponent.h"
#include "Player/EcoCombatActionExecutor.h"
#include "EcoPlayerCombatComponent.generated.h"

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPlayerCombatComponent : public UActorComponent, public IEcoCombatActionExecutor
{
    GENERATED_BODY()

public:
    bool TryQueueMeleeStrike() override;
};

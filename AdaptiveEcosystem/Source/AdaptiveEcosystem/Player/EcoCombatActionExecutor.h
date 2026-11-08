#pragma once

#include "UObject/Interface.h"
#include "EcoCombatActionExecutor.generated.h"

UINTERFACE(MinimalAPI, meta=(CannotImplementInterfaceInBlueprint))
class UEcoCombatActionExecutor : public UInterface
{
    GENERATED_BODY()
};

class IEcoCombatActionExecutor
{
    GENERATED_BODY()

public:
    virtual bool TryQueueMeleeStrike() = 0;
};

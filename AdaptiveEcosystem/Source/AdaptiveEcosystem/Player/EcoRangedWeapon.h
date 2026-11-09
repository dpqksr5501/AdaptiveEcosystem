#pragma once
#include "UObject/Interface.h"
#include "EcoRangedWeapon.generated.h"
UINTERFACE(MinimalAPI,meta=(CannotImplementInterfaceInBlueprint))
class UEcoRangedWeapon : public UInterface { GENERATED_BODY() };
/** Native muzzle contract: a weapon may use an authored socket or explicit point. */
class ADAPTIVEECOSYSTEM_API IEcoRangedWeapon
{
    GENERATED_BODY()
public:
    virtual bool GetMuzzleTransform(FTransform& Out) const = 0;
};

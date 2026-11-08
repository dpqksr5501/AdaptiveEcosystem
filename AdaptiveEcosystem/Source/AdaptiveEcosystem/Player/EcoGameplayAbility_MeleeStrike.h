#pragma once

#include "Abilities/GameplayAbility.h"
#include "EcoGameplayAbility_MeleeStrike.generated.h"

UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API UEcoGameplayAbility_MeleeStrike : public UGameplayAbility
{
    GENERATED_BODY()

public:
    UEcoGameplayAbility_MeleeStrike();

protected:
    void ActivateAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo,
        const FGameplayAbilityActivationInfo ActivationInfo, const FGameplayEventData* TriggerEventData) override;
};

#pragma once
#include "Abilities/GameplayAbility.h"
#include "EcoGameplayAbility_Weapon.generated.h"
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoGameplayAbility_AimWeapon : public UGameplayAbility
{
    GENERATED_BODY()
public:
    UEcoGameplayAbility_AimWeapon();
    void ActivateAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,const FGameplayAbilityActivationInfo Activation,const FGameplayEventData* Event) override;
    void InputReleased(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,const FGameplayAbilityActivationInfo Activation) override;
    void EndAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,const FGameplayAbilityActivationInfo Activation,bool bReplicate,bool bCancelled) override;
};
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoGameplayAbility_FireWeapon : public UGameplayAbility
{
    GENERATED_BODY()
public:
    UEcoGameplayAbility_FireWeapon();
    void ActivateAbility(const FGameplayAbilitySpecHandle Handle,const FGameplayAbilityActorInfo* Info,const FGameplayAbilityActivationInfo Activation,const FGameplayEventData* Event) override;
};

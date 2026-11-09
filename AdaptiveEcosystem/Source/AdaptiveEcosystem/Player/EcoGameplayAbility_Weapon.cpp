#include "Player/EcoGameplayAbility_Weapon.h"
#include "Player/EcoAimComponent.h"
#include "Player/EcoWeaponFireComponent.h"
#include "NativeGameplayTags.h"
#include "GameFramework/Pawn.h"
UE_DEFINE_GAMEPLAY_TAG_STATIC(TAG_EcoAiming,"State.Weapon.Aiming");
UEcoGameplayAbility_AimWeapon::UEcoGameplayAbility_AimWeapon()
{
    InstancingPolicy=EGameplayAbilityInstancingPolicy::InstancedPerActor;
    NetExecutionPolicy=EGameplayAbilityNetExecutionPolicy::LocalPredicted;
    bReplicateInputDirectly=true;
    ActivationOwnedTags.AddTag(TAG_EcoAiming);
    FGameplayTagContainer Tags; Tags.AddTag(TAG_EcoAiming); SetAssetTags(Tags);
}
void UEcoGameplayAbility_AimWeapon::ActivateAbility(const FGameplayAbilitySpecHandle H,const FGameplayAbilityActorInfo* I,const FGameplayAbilityActivationInfo A,const FGameplayEventData* E)
{
    auto* C=I->AvatarActor.IsValid()?I->AvatarActor->FindComponentByClass<UEcoAimComponent>():nullptr;
    if (!C || !C->SetAiming(true) || !CommitAbility(H,I,A)) EndAbility(H,I,A,true,true);
}
void UEcoGameplayAbility_AimWeapon::InputReleased(const FGameplayAbilitySpecHandle H,const FGameplayAbilityActorInfo* I,const FGameplayAbilityActivationInfo A)
{ EndAbility(H,I,A,true,false); }
void UEcoGameplayAbility_AimWeapon::EndAbility(const FGameplayAbilitySpecHandle H,const FGameplayAbilityActorInfo* I,const FGameplayAbilityActivationInfo A,bool R,bool C)
{
    if (I && I->AvatarActor.IsValid()) if (auto* Aim=I->AvatarActor->FindComponentByClass<UEcoAimComponent>()) Aim->SetAiming(false);
    Super::EndAbility(H,I,A,R,C);
}
UEcoGameplayAbility_FireWeapon::UEcoGameplayAbility_FireWeapon()
{
    InstancingPolicy=EGameplayAbilityInstancingPolicy::InstancedPerActor;
    NetExecutionPolicy=EGameplayAbilityNetExecutionPolicy::LocalPredicted;
    ActivationRequiredTags.AddTag(TAG_EcoAiming);
}
void UEcoGameplayAbility_FireWeapon::ActivateAbility(const FGameplayAbilitySpecHandle H,const FGameplayAbilityActorInfo* I,const FGameplayAbilityActivationInfo A,const FGameplayEventData* E)
{
    auto* P=Cast<APawn>(I->AvatarActor.Get());
    if (P && P->IsLocallyControlled()) if (auto* Fire=P->FindComponentByClass<UEcoWeaponFireComponent>()) Fire->RequestFire();
    EndAbility(H,I,A,true,false);
}

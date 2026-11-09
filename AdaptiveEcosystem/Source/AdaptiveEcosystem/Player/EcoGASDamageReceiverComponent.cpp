#include "Player/EcoGASDamageReceiverComponent.h"
#include "Player/EcoHealthAttributeSet.h"
#include "Player/EcoPlayerState.h"
#include "AbilitySystemGlobals.h"
#include "AbilitySystemComponent.h"
#include "GameplayEffect.h"
#include "GameFramework/Pawn.h"
bool UEcoGASDamageReceiverComponent::SubmitPointDamage_Implementation(const FEcoPointDamage& R)
{
    if (!GetOwner()->HasAuthority() || !R.Instigator || !R.Instigator->HasAuthority() || R.Hit.GetActor()!=GetOwner()
        || !FMath::IsFinite(R.Damage) || R.Damage<=0 || R.Damage>10000) return false;
    auto* ASC=UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner());
    if (const auto* P=Cast<APawn>(GetOwner()))
        if (const auto* S=P->GetPlayerState<AEcoPlayerState>(); S && (!S->IsAlive() || S->bInvulnerable)) return false;
    if (!ASC || !ASC->GetSet<UEcoHealthAttributeSet>()) return false;
    auto* GE=NewObject<UGameplayEffect>(GetTransientPackage()); GE->DurationPolicy=EGameplayEffectDurationType::Instant;
    auto& M=GE->Modifiers.AddDefaulted_GetRef(); M.Attribute=UEcoHealthAttributeSet::GetHealthAttribute();
    M.ModifierOp=EGameplayModOp::Additive; M.ModifierMagnitude=FScalableFloat(-R.Damage);
    auto Context=ASC->MakeEffectContext(); Context.AddInstigator(R.Instigator,R.Weapon); Context.AddHitResult(R.Hit);
    FGameplayEffectSpec Spec(GE,Context,1); ASC->ApplyGameplayEffectSpecToSelf(Spec); return true;
}

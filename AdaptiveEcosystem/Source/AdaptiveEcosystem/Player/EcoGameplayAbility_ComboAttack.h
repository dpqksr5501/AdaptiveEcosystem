#pragma once
#include "Abilities/GameplayAbility.h"
#include "Player/EcoAttackWindowReceiver.h"
#include "Components/SkinnedMeshComponent.h"
#include "EcoGameplayAbility_ComboAttack.generated.h"
class UEcoMeleeHitComponent;
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API UEcoGameplayAbility_ComboAttack : public UGameplayAbility
{
    GENERATED_BODY()
public:
    UEcoGameplayAbility_ComboAttack();
    void InputPressed(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info, const FGameplayAbilityActivationInfo Activation) override;
    void ReceiveWindow(EEcoAttackWindow Window, bool bOpen, UAnimSequenceBase* Animation);
    UPROPERTY(BlueprintReadOnly, Category="Combo") int32 CurrentStep = INDEX_NONE;
protected:
    void ActivateAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo, const FGameplayEventData* Event) override;
    void EndAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* ActorInfo, const FGameplayAbilityActivationInfo ActivationInfo, bool bReplicate, bool bCancelled) override;
private:
    void CloseInput();

    UFUNCTION() void Finished();
    UFUNCTION() void Interrupted();
    UPROPERTY(Transient) TObjectPtr<UEcoMeleeHitComponent> HitComponent;

    bool bInputOpen = false;
    bool bQueued = false;
    EVisibilityBasedAnimTickOption OldTick = EVisibilityBasedAnimTickOption::OnlyTickPoseWhenRendered;
};

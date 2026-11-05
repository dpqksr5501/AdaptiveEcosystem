#include "Player/EcoGameplayAbility_ComboAttack.h"
#include "Player/EcoMeleeHitComponent.h"
#include "Player/EcoComboAttackData.h"
#include "AbilitySystemComponent.h"
#include "Abilities/Tasks/AbilityTask_PlayMontageAndWait.h"
#include "Animation/AnimMontage.h"
#include "GameFramework/Character.h"
#include "Components/SkeletalMeshComponent.h"
#include "Player/EcoPlayerState.h"
UEcoGameplayAbility_ComboAttack::UEcoGameplayAbility_ComboAttack()
{
    bReplicateInputDirectly = true;
    InstancingPolicy = EGameplayAbilityInstancingPolicy::InstancedPerActor;
    NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::ServerInitiated;
    NetSecurityPolicy = EGameplayAbilityNetSecurityPolicy::ServerOnlyTermination;
}
void UEcoGameplayAbility_ComboAttack::ActivateAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info, const FGameplayAbilityActivationInfo Activation, const FGameplayEventData* Event)
{
    HitComponent = Info->AvatarActor.IsValid() ? Info->AvatarActor->FindComponentByClass<UEcoMeleeHitComponent>() : nullptr;
    auto* Data = HitComponent ? HitComponent->AttackData.Get() : nullptr;
    const auto* Pawn = Cast<APawn>(Info->AvatarActor.Get());
    const auto* State = Pawn ? Pawn->GetPlayerState<AEcoPlayerState>() : nullptr;
    if ((State && !State->IsAlive()) || !Data || !Data->Montage || Data->Steps.IsEmpty() || !Info->GetAnimInstance()) { EndAbility(Handle, Info, Activation, true, true); return; }
    for (const auto& Step : Data->Steps)
        if (!Info->SkeletalMeshComponent->DoesSocketExist(Step.Socket) || Data->Montage->GetSectionIndex(Step.Section) == INDEX_NONE) { EndAbility(Handle, Info, Activation, true, true); return; }
    if (!CommitAbility(Handle, Info, Activation)) { EndAbility(Handle, Info, Activation, true, true); return; }
    HitComponent->SetAbility(this);
    CurrentStep = 0; bQueued = false;
    OldTick = Info->SkeletalMeshComponent->VisibilityBasedAnimTickOption;
    Info->SkeletalMeshComponent->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    auto* Task = UAbilityTask_PlayMontageAndWait::CreatePlayMontageAndWaitProxy(this, NAME_None, Data->Montage, 1.f, Data->Steps[0].Section);
    Task->OnCompleted.AddDynamic(this, &ThisClass::Finished);
    Task->OnInterrupted.AddDynamic(this, &ThisClass::Interrupted);
    Task->OnCancelled.AddDynamic(this, &ThisClass::Interrupted);
    Task->OnBlendOut.AddDynamic(this, &ThisClass::Finished);
    Task->ReadyForActivation();
    if (IsActive())
        for (const auto& Step : Data->Steps) GetAbilitySystemComponentFromActorInfo()->CurrentMontageSetNextSectionName(Step.Section, NAME_None);
    UE_LOG(LogTemp, Log, TEXT("[EcoCombo] Started Authority=%d"), Info->IsNetAuthority());
}
void UEcoGameplayAbility_ComboAttack::CloseInput()
{
    bInputOpen = false;

}
void UEcoGameplayAbility_ComboAttack::InputPressed(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info, const FGameplayAbilityActivationInfo Activation)
{
    if (bInputOpen && !bQueued && GetCurrentActorInfo()->IsNetAuthority()) { bQueued = true; UE_LOG(LogTemp, Log, TEXT("[EcoCombo] Queued Step=%d"), CurrentStep); }
}
void UEcoGameplayAbility_ComboAttack::ReceiveWindow(EEcoAttackWindow Window, bool bOpen, UAnimSequenceBase* Animation)
{
    if (!IsActive() || !HitComponent || Animation != HitComponent->AttackData->Montage || CurrentStep == INDEX_NONE) return;
    if (Window == EEcoAttackWindow::Input)
    {
        CloseInput();
        if (bOpen && HitComponent->AttackData->Steps.IsValidIndex(CurrentStep+1))
        {
            bInputOpen = true;

        }
    }
    else if (Window == EEcoAttackWindow::Hit)
    {
        if (bOpen) HitComponent->BeginHit(CurrentStep); else HitComponent->StopHit();
    }
    else if (GetCurrentActorInfo()->IsNetAuthority())
    {
        CloseInput(); HitComponent->StopHit();
        if (bQueued && HitComponent->AttackData->Steps.IsValidIndex(CurrentStep+1))
        {
            bQueued = false; ++CurrentStep;
            GetAbilitySystemComponentFromActorInfo()->CurrentMontageJumpToSection(HitComponent->AttackData->Steps[CurrentStep].Section);
            UE_LOG(LogTemp, Log, TEXT("[EcoCombo] Advance Step=%d"), CurrentStep);
        }
    }
}
void UEcoGameplayAbility_ComboAttack::Finished() { EndAbility(GetCurrentAbilitySpecHandle(), GetCurrentActorInfo(), GetCurrentActivationInfo(), true, false); }
void UEcoGameplayAbility_ComboAttack::Interrupted() { EndAbility(GetCurrentAbilitySpecHandle(), GetCurrentActorInfo(), GetCurrentActivationInfo(), true, true); }
void UEcoGameplayAbility_ComboAttack::EndAbility(const FGameplayAbilitySpecHandle Handle, const FGameplayAbilityActorInfo* Info, const FGameplayAbilityActivationInfo Activation, bool bReplicate, bool bCancelled)
{
    if (!IsActive()) return;
    CloseInput();
    if (HitComponent) { HitComponent->ResetAttack(); if (Info->SkeletalMeshComponent.IsValid() && CurrentStep != INDEX_NONE) Info->SkeletalMeshComponent->VisibilityBasedAnimTickOption = OldTick; }
    CurrentStep = INDEX_NONE; bQueued = false;
    UE_LOG(LogTemp, Log, TEXT("[EcoCombo] End Cancelled=%d"), bCancelled);
    Super::EndAbility(Handle, Info, Activation, bReplicate, bCancelled);
}

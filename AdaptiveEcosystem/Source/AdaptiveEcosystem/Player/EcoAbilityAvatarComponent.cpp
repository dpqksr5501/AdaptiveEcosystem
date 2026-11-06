#include "Player/EcoAbilityAvatarComponent.h"
#include "Player/EcoPlayerState.h"
#include "AbilitySystemComponent.h"
#include "EnhancedInputComponent.h"
#include "GameFramework/Pawn.h"
#include "Engine/World.h"
#include "InputAction.h"
#include "TimerManager.h"
#include "CoreGlobals.h"

void UEcoAbilityAvatarComponent::RefreshAvatar()
{
    auto* Pawn = CastChecked<APawn>(GetOwner());
    auto* State = Pawn->GetPlayerState<AEcoPlayerState>();
    auto* ASC = State ? State->GetAbilitySystemComponent() : nullptr;
    if (AbilitySystem.Get() != ASC)
    {
        ReleaseAvatar();
        AbilitySystem = ASC;
    }
    UE_LOG(LogTemp,Verbose,TEXT("[EcoAbility][Refresh] Pawn=%s State=%s Authority=%d ASC=%s ExistingAvatar=%s Bindings=%d"),
        *GetNameSafe(Pawn),*GetNameSafe(State),Pawn->HasAuthority(),*GetNameSafe(ASC),ASC?*GetNameSafe(ASC->GetAvatarActor()):TEXT("None"),GetBindings().Num());
    if (!ASC) return;
    if (ASC->GetAvatarActor() != Pawn) ASC->InitAbilityActorInfo(State, Pawn);
    State->InitializeHealthForAvatar(Pawn);
    if (!Pawn->HasAuthority())
        return;

    int32 NextInputId = 0;
    for (const FGameplayAbilitySpec& Spec : ASC->GetActivatableAbilities())
    {
        NextInputId = FMath::Max(NextInputId, Spec.InputID + 1);
    }
    for (const FEcoAbilityInputBinding& Binding : GetBindings())
    {
        if (!Binding.Action || !Binding.Ability)
            continue;

        if (auto* Spec = ASC->FindAbilitySpecFromClass(Binding.Ability))
        {
            if (Spec->InputID == INDEX_NONE)
            {
                Spec->InputID = NextInputId++;
                ASC->MarkAbilitySpecDirty(*Spec);
            }
        }
        else
        {
            ASC->GiveAbility(FGameplayAbilitySpec(Binding.Ability, 1, NextInputId++));
            UE_LOG(LogTemp,Verbose,TEXT("[EcoAbility][Granted] Pawn=%s Ability=%s Count=%d"),*GetNameSafe(Pawn),*GetNameSafe(Binding.Ability),ASC->GetActivatableAbilities().Num());
        }
    }
}

void UEcoAbilityAvatarComponent::ReleaseAvatar()
{
    ReleasePressedAbilities();
    if (auto* ASC = GetAbilitySystem())
    {
        ASC->CancelAllAbilities();
        ASC->ClearActorInfo();
    }
    AbilitySystem.Reset();
}

UAbilitySystemComponent* UEcoAbilityAvatarComponent::GetAbilitySystem() const
{
    auto* ASC = AbilitySystem.Get();
    return ASC && ASC->GetAvatarActor() == GetOwner() ? ASC : nullptr;
}

void UEcoAbilityAvatarComponent::BindInput(UEnhancedInputComponent& Input)
{
    ReleasePressedAbilities();
    if (auto* Previous = BoundInput.Get())
        for (uint32 Handle : BindingHandles)
            Previous->RemoveBindingByHandle(Handle);

    BindingHandles.Reset();
    BoundInput = &Input;
    for (const FEcoAbilityInputBinding& Binding : GetBindings())
    {
        if (Binding.Action && Binding.Ability)
        {
            BindingHandles.Add(Input.BindAction(Binding.Action, Binding.ActivationEvent,
                this, &UEcoAbilityAvatarComponent::PressAbility, static_cast<const UInputAction*>(Binding.Action.Get()), Binding.Ability).GetHandle());
            BindingHandles.Add(Input.BindAction(Binding.Action, ETriggerEvent::Completed,
                this, &UEcoAbilityAvatarComponent::ReleaseAbility, static_cast<const UInputAction*>(Binding.Action.Get())).GetHandle());
            BindingHandles.Add(Input.BindAction(Binding.Action, ETriggerEvent::Canceled,
                this, &UEcoAbilityAvatarComponent::ReleaseAbility, static_cast<const UInputAction*>(Binding.Action.Get())).GetHandle());
        }
    }
}

const TArray<FEcoAbilityInputBinding>& UEcoAbilityAvatarComponent::GetBindings() const
{
    return InputConfig ? InputConfig->AbilityInputs : AbilityInputs;
}

void UEcoAbilityAvatarComponent::PressAbility(const UInputAction* Action, TSubclassOf<UGameplayAbility> Ability)
{
    const auto* Pawn = Cast<APawn>(GetOwner());
    const auto* State = Pawn ? Pawn->GetPlayerState<AEcoPlayerState>() : nullptr;
    if ((State && !State->IsAlive()) || PressedActions.Contains(Action))
        return;

    if (auto* ASC = GetAbilitySystem())
    {
        if (auto* Spec = ASC->FindAbilitySpecFromClass(Ability); Spec && Spec->InputID != INDEX_NONE)
        {
            const bool bAlreadyPressed = PressedActions.FindKey(Ability) != nullptr;
            PressedActions.Add(Action, Ability);
            if (!bAlreadyPressed)
                ASC->AbilityLocalInputPressed(Spec->InputID);
        }
    }
}

void UEcoAbilityAvatarComponent::ReleaseAbility(const UInputAction* Action)
{
    TSubclassOf<UGameplayAbility> Ability;
    if (!PressedActions.RemoveAndCopyValue(Action, Ability) || PressedActions.FindKey(Ability))
        return;

    if (auto* ASC = GetAbilitySystem())
    {
        if (auto* Spec = ASC->FindAbilitySpecFromClass(Ability); Spec && Spec->InputID != INDEX_NONE)
            ASC->AbilityLocalInputReleased(Spec->InputID);
    }
}

void UEcoAbilityAvatarComponent::ReleasePressedAbilities()
{
    TArray<const UInputAction*> Actions;
    PressedActions.GetKeys(Actions);
    for (const UInputAction* Action : Actions)
        ReleaseAbility(Action);
}

void UEcoAbilityAvatarComponent::PressConfiguredAction(const UInputAction* Action)
{
    const auto* Pawn=Cast<APawn>(GetOwner());
    if(!Pawn||!Pawn->IsLocallyControlled()||!Action)return;
    if (DeferEditorInput(Action, true)) return;
    for(const auto& Binding:GetBindings())if(Binding.Action==Action&&Binding.Ability)
    { PressAbility(Action,Binding.Ability);return; }
}
void UEcoAbilityAvatarComponent::ReleaseConfiguredAction(const UInputAction* Action)
{
    const auto* Pawn=Cast<APawn>(GetOwner());
    if (Pawn && Pawn->IsLocallyControlled() && Action && DeferEditorInput(Action, false)) return;
    if(Pawn&&Pawn->IsLocallyControlled())ReleaseAbility(Action);
}

bool UEcoAbilityAvatarComponent::DeferEditorInput(const UInputAction* Action, bool bPressed)
{
#if WITH_EDITOR
    if (GAllowActorScriptExecutionInEditor && GetWorld() && GetWorld()->IsGameWorld())
    {
        const TWeakObjectPtr<const UInputAction> WeakAction(Action);
        const TWeakObjectPtr<UAbilitySystemComponent> ExpectedSystem(GetAbilitySystem());
        const auto* Pawn = Cast<APawn>(GetOwner());
        const TWeakObjectPtr<AController> ExpectedController(Pawn ? Pawn->GetController() : nullptr);
        GetWorld()->GetTimerManager().SetTimerForNextTick(FTimerDelegate::CreateWeakLambda(this,
            [this, WeakAction, ExpectedSystem, ExpectedController, bPressed]()
            {
                const auto* CurrentPawn = Cast<APawn>(GetOwner());
                if (!WeakAction.IsValid() || !ExpectedSystem.IsValid() || GetAbilitySystem() != ExpectedSystem.Get()
                    || !CurrentPawn || !CurrentPawn->IsLocallyControlled() || !ExpectedController.IsValid()
                    || CurrentPawn->GetController() != ExpectedController.Get()) return;
                if (bPressed) PressConfiguredAction(WeakAction.Get());
                else ReleaseConfiguredAction(WeakAction.Get());
            }));
        return true;
    }
#endif
    return false;
}

void UEcoAbilityAvatarComponent::BeginPlay()
{
    Super::BeginPlay();
    // A placed/standalone Pawn can be possessed before its PlayerState ASC initializes.
    // Rebind after component initialization; repeated refresh grants only missing abilities.
    RefreshAvatar();
}

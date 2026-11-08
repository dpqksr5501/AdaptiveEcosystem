#pragma once

#include "Components/ActorComponent.h"
#include "Player/EcoAbilityInputConfig.h"
#include "EcoAbilityAvatarComponent.generated.h"

class UAbilitySystemComponent;
class UEnhancedInputComponent;

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoAbilityAvatarComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    /** UI/controllers may submit only an action already present in this avatar's authored bindings. */
    UFUNCTION(BlueprintCallable, Category="Abilities|Input") void PressConfiguredAction(const UInputAction* Action);
    UFUNCTION(BlueprintCallable, Category="Abilities|Input") void ReleaseConfiguredAction(const UInputAction* Action);
    void RefreshAvatar();
    void ReleaseAvatar();
    void BindInput(UEnhancedInputComponent& Input);
    UAbilitySystemComponent* GetAbilitySystem() const;

protected:
    void BeginPlay() override;
private:
    /** Editor scripting forces RPCs local; execute scripted game input after that scope ends. */
    bool DeferEditorInput(const UInputAction* Action, bool bPressed);
    friend struct FEcoCombatTestAccess;
    void PressAbility(const UInputAction* Action, TSubclassOf<UGameplayAbility> Ability);
    void ReleaseAbility(const UInputAction* Action);
    void ReleasePressedAbilities();
    const TArray<FEcoAbilityInputBinding>& GetBindings() const;

    UPROPERTY(EditAnywhere, Category="Abilities")
    TObjectPtr<UEcoAbilityInputConfig> InputConfig;

    // Compatibility with saved Pawns that have not yet selected an Input Config asset.
    UPROPERTY(EditAnywhere, Category="Abilities")
    TArray<FEcoAbilityInputBinding> AbilityInputs;

    TWeakObjectPtr<UAbilitySystemComponent> AbilitySystem;
    TWeakObjectPtr<UEnhancedInputComponent> BoundInput;
    TArray<uint32> BindingHandles;
    TMap<const UInputAction*, TSubclassOf<UGameplayAbility>> PressedActions;
};

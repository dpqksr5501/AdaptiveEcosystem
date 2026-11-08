#pragma once

#include "Engine/DataAsset.h"
#include "InputTriggers.h"
#include "EcoAbilityInputConfig.generated.h"

class UGameplayAbility;
class UInputAction;

USTRUCT(BlueprintType)
struct FEcoAbilityInputBinding
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, Category="Abilities")
    TObjectPtr<UInputAction> Action;

    UPROPERTY(EditAnywhere, Category="Abilities")
    TSubclassOf<UGameplayAbility> Ability;

    /** Started activates on press. Triggered waits for the Input Action's triggers, such as Hold. */
    UPROPERTY(EditAnywhere, Category="Abilities", meta=(ValidEnumValues="Started,Triggered"))
    ETriggerEvent ActivationEvent = ETriggerEvent::Started;
};

/** Maps actions to GAS abilities. Physical keys and modifiers belong to an Input Mapping Context. */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoAbilityInputConfig : public UDataAsset
{
    GENERATED_BODY()

public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Abilities", meta=(TitleProperty="Action"))
    TArray<FEcoAbilityInputBinding> AbilityInputs;
};

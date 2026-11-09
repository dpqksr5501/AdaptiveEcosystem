#pragma once
#include "AttributeSet.h"
#include "AbilitySystemComponent.h"
#include "EcoHealthAttributeSet.generated.h"

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoHealthAttributeSet : public UAttributeSet
{
    GENERATED_BODY()
public:
    UEcoHealthAttributeSet();
    UPROPERTY(BlueprintReadOnly, ReplicatedUsing=OnRep_Health, Category="Health") FGameplayAttributeData Health;
    UPROPERTY(BlueprintReadOnly, ReplicatedUsing=OnRep_MaxHealth, Category="Health") FGameplayAttributeData MaxHealth;
    GAMEPLAYATTRIBUTE_PROPERTY_GETTER(UEcoHealthAttributeSet, Health)
    GAMEPLAYATTRIBUTE_VALUE_GETTER(Health)
    GAMEPLAYATTRIBUTE_VALUE_SETTER(Health)
    GAMEPLAYATTRIBUTE_VALUE_INITTER(Health)
    GAMEPLAYATTRIBUTE_PROPERTY_GETTER(UEcoHealthAttributeSet, MaxHealth)
    GAMEPLAYATTRIBUTE_VALUE_GETTER(MaxHealth)
    GAMEPLAYATTRIBUTE_VALUE_SETTER(MaxHealth)
    GAMEPLAYATTRIBUTE_VALUE_INITTER(MaxHealth)
    void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    void PreAttributeChange(const FGameplayAttribute& Attribute, float& NewValue) override;
    void PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data) override;
private:
    UFUNCTION() void OnRep_Health(const FGameplayAttributeData& Old);
    UFUNCTION() void OnRep_MaxHealth(const FGameplayAttributeData& Old);
};

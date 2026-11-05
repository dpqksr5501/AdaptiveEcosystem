#include "Player/EcoHealthAttributeSet.h"
#include "GameplayEffectExtension.h"
#include "Net/UnrealNetwork.h"

UEcoHealthAttributeSet::UEcoHealthAttributeSet() { InitMaxHealth(100); InitHealth(100); }
void UEcoHealthAttributeSet::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME_CONDITION_NOTIFY(UEcoHealthAttributeSet, Health, COND_None, REPNOTIFY_Always);
    DOREPLIFETIME_CONDITION_NOTIFY(UEcoHealthAttributeSet, MaxHealth, COND_None, REPNOTIFY_Always);
}
void UEcoHealthAttributeSet::PreAttributeChange(const FGameplayAttribute& Attribute, float& Value)
{
    Super::PreAttributeChange(Attribute, Value);
    if (Attribute == GetMaxHealthAttribute()) Value = FMath::IsFinite(Value) ? FMath::Max(1.f, Value) : 100.f;
    if (Attribute == GetHealthAttribute()) Value = FMath::IsFinite(Value) ? FMath::Clamp(Value, 0.f, GetMaxHealth()) : GetHealth();
}
void UEcoHealthAttributeSet::PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
    Super::PostGameplayEffectExecute(Data);
    if (Data.EvaluatedData.Attribute == GetHealthAttribute()) SetHealth(FMath::Clamp(GetHealth(), 0.f, GetMaxHealth()));
}
void UEcoHealthAttributeSet::OnRep_Health(const FGameplayAttributeData& Old) { GAMEPLAYATTRIBUTE_REPNOTIFY(UEcoHealthAttributeSet, Health, Old); }
void UEcoHealthAttributeSet::OnRep_MaxHealth(const FGameplayAttributeData& Old) { GAMEPLAYATTRIBUTE_REPNOTIFY(UEcoHealthAttributeSet, MaxHealth, Old); }

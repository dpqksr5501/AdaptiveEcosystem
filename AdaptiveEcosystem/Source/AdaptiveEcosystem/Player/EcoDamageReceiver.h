#pragma once
#include "UObject/Interface.h"
#include "EcoDamageReceiver.generated.h"
USTRUCT(BlueprintType)
struct FEcoPointDamage
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AActor> Instigator;
    UPROPERTY(BlueprintReadOnly) TObjectPtr<AActor> Weapon;
    UPROPERTY(BlueprintReadOnly) int64 Execution=0;
    UPROPERTY(BlueprintReadOnly) float Damage=0;
    UPROPERTY(BlueprintReadOnly) FHitResult Hit;
    UPROPERTY(BlueprintReadOnly) FVector Direction=FVector::ZeroVector;
};
UINTERFACE(BlueprintType)
class UEcoDamageReceiver : public UInterface { GENERATED_BODY() };
class ADAPTIVEECOSYSTEM_API IEcoDamageReceiver
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintNativeEvent,BlueprintCallable,Category="Combat") bool SubmitPointDamage(const FEcoPointDamage& Request);
};

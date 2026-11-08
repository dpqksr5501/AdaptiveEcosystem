#pragma once
#include "Engine/DataAsset.h"
#include "Engine/EngineTypes.h"
#include "EcoComboAttackData.generated.h"
class UAnimMontage;
USTRUCT(BlueprintType)
struct FEcoComboStep
{
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FName Section;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) FName Socket;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="1", Units="cm")) float Radius = 14.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="0")) float Damage = 30.f;
};
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoComboAttackData : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TObjectPtr<UAnimMontage> Montage;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<FEcoComboStep> Steps;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TEnumAsByte<ECollisionChannel>> TargetObjectTypes = { ECC_Pawn, ECC_PhysicsBody, ECC_WorldDynamic };
    UPROPERTY(EditAnywhere, BlueprintReadOnly) TEnumAsByte<ECollisionChannel> ObstructionChannel = ECC_Visibility;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="1", ClampMax="32")) int32 MaxTargetsPerStep = 8;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, meta=(ClampMin="100", ClampMax="800", Units="cm")) float MaxReachCm = 350.f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly) bool bDrawDebug = false;
};

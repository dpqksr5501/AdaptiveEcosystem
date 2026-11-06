#pragma once
#include "Engine/DataAsset.h"
#include "EcoWeaponDefinition.generated.h"
class UStaticMesh;
class USkeletalMesh;
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API UEcoWeaponDefinition : public UDataAsset
{
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon") TObjectPtr<UStaticMesh> StaticMesh;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon") TObjectPtr<USkeletalMesh> SkeletalMesh;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon") FName GripSocket = TEXT("socket_Gun");
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon") FName MuzzleSocket = TEXT("socket_Muzzle");
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon") FTransform GripOffset;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon", meta=(ClampMin="0.01",ClampMax="10000")) float BaseDamage = 30;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon", meta=(ClampMin="1",Units="cm")) float Range = 1800;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Weapon", meta=(ClampMin="0.05")) float FireInterval = .25f;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Aim") FVector AimOffset = FVector(0,60,15);
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Aim") float AimArmLength = 200;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Aim") float AimFOV = 65;
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Aim", meta=(ClampMin="0.01")) float BlendSeconds = .15f;
};

#pragma once
#include "GameFramework/Actor.h"
#include "Player/EcoRangedWeapon.h"
#include "EcoWeaponActor.generated.h"
class UStaticMeshComponent;
class USkeletalMeshComponent;
class USceneComponent;
class UEcoWeaponDefinition;
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoWeaponActor : public AActor, public IEcoRangedWeapon
{
    GENERATED_BODY()
public:
    AEcoWeaponActor();
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Weapon") TObjectPtr<UStaticMeshComponent> StaticMesh;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Weapon") TObjectPtr<USkeletalMeshComponent> SkeletalMesh;
    /** Explicit fallback only. Enable in the owned weapon Blueprint. */
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Weapon") TObjectPtr<USceneComponent> MuzzlePoint;
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Weapon") bool bUseMuzzlePoint = false;
    UPROPERTY(ReplicatedUsing=OnRep_Definition, BlueprintReadOnly, Category="Weapon") TObjectPtr<UEcoWeaponDefinition> Definition;
    void Initialize(UEcoWeaponDefinition* Data);
    bool GetMuzzleTransform(FTransform& Out) const override;
    void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UFUNCTION() void OnRep_Definition();
};

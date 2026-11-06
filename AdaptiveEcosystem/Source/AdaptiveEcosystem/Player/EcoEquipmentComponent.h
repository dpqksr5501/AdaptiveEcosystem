#pragma once
#include "Components/ActorComponent.h"
#include "EcoEquipmentComponent.generated.h"
class AEcoWeaponActor;
class UEcoWeaponDefinition;
UCLASS(ClassGroup=(Combat), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoEquipmentComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UEcoEquipmentComponent();
    UPROPERTY(EditAnywhere, Category="Weapon") TObjectPtr<UEcoWeaponDefinition> InitialWeapon;
    UPROPERTY(EditAnywhere, Category="Weapon") TSubclassOf<AEcoWeaponActor> WeaponClass;
    UPROPERTY(ReplicatedUsing=OnRep_Weapon, BlueprintReadOnly, Category="Weapon") TObjectPtr<AEcoWeaponActor> Weapon;
    UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category="Weapon") bool Equip(UEcoWeaponDefinition* Data);
    UFUNCTION(BlueprintCallable, BlueprintAuthorityOnly, Category="Weapon") void Unequip();
    void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
protected:
    void BeginPlay() override;
    void EndPlay(const EEndPlayReason::Type Reason) override;
    UFUNCTION() void OnRep_Weapon();
};

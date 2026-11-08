#include "Player/EcoEquipmentComponent.h"
#include "Player/EcoWeaponActor.h"
#include "Player/EcoWeaponDefinition.h"
#include "Player/EcoAimComponent.h"
#include "GameFramework/Character.h"
#include "Components/SkeletalMeshComponent.h"
#include "Net/UnrealNetwork.h"
#include "AbilitySystemGlobals.h"
#include "AbilitySystemComponent.h"
UEcoEquipmentComponent::UEcoEquipmentComponent() { SetIsReplicatedByDefault(true); WeaponClass=AEcoWeaponActor::StaticClass(); }
void UEcoEquipmentComponent::BeginPlay() { Super::BeginPlay(); if (GetOwner()->HasAuthority() && InitialWeapon) Equip(InitialWeapon); }
bool UEcoEquipmentComponent::Equip(UEcoWeaponDefinition* Data)
{
    auto* C=Cast<ACharacter>(GetOwner());
    if (!C || !C->HasAuthority() || !Data || !WeaponClass || !C->GetMesh()->DoesSocketExist(Data->GripSocket)) return false;
    if ((!Data->StaticMesh && !Data->SkeletalMesh) || !FMath::IsFinite(Data->BaseDamage) || Data->BaseDamage<=0 || Data->BaseDamage>10000
        || Data->GripOffset.ContainsNaN() || Data->AimOffset.ContainsNaN() || Data->AimOffset.Size()>150
        || !FMath::IsFinite(Data->AimArmLength) || Data->AimArmLength<0 || Data->AimArmLength>400
        || !FMath::IsFinite(Data->AimFOV) || Data->AimFOV<20 || Data->AimFOV>120
        || !FMath::IsFinite(Data->BlendSeconds) || Data->BlendSeconds<.01f
        || !FMath::IsFinite(Data->Range) || Data->Range<=0 || Data->Range>200000 || !FMath::IsFinite(Data->FireInterval) || Data->FireInterval<.05f) return false;
    FActorSpawnParameters Params; Params.Owner=C; Params.Instigator=C;
    auto* NewWeapon=GetWorld()->SpawnActor<AEcoWeaponActor>(WeaponClass,Params);
    if (!NewWeapon) return false;
    NewWeapon->Initialize(Data); FTransform Muzzle;
    if (!NewWeapon->GetMuzzleTransform(Muzzle)) { NewWeapon->Destroy(); return false; }
    Unequip(); Weapon=NewWeapon; OnRep_Weapon(); C->ForceNetUpdate(); return true;
}
void UEcoEquipmentComponent::Unequip()
{
    if (!GetOwner()->HasAuthority()) return;
    if (auto* ASC=UAbilitySystemGlobals::GetAbilitySystemComponentFromActor(GetOwner()))
    { FGameplayTagContainer Tags; Tags.AddTag(FGameplayTag::RequestGameplayTag(TEXT("State.Weapon.Aiming"))); ASC->CancelAbilities(&Tags); }
    if (auto* Aim=GetOwner()->FindComponentByClass<UEcoAimComponent>()) Aim->SetAiming(false);
    if (Weapon) Weapon->Destroy(); Weapon=nullptr;
}
void UEcoEquipmentComponent::OnRep_Weapon()
{
    auto* C=Cast<ACharacter>(GetOwner());
    if (C && Weapon && Weapon->Definition)
    {
        Weapon->AttachToComponent(C->GetMesh(),FAttachmentTransformRules::SnapToTargetNotIncludingScale,Weapon->Definition->GripSocket);
        Weapon->SetActorRelativeTransform(Weapon->Definition->GripOffset);
    }
}
void UEcoEquipmentComponent::EndPlay(const EEndPlayReason::Type Reason) { Unequip(); Super::EndPlay(Reason); }
void UEcoEquipmentComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{ Super::GetLifetimeReplicatedProps(OutLifetimeProps); DOREPLIFETIME(UEcoEquipmentComponent,Weapon); }

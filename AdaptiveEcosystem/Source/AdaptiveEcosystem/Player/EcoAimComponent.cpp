#include "Player/EcoAimComponent.h"
#include "Player/EcoEquipmentComponent.h"
#include "Player/EcoWeaponActor.h"
#include "Player/EcoWeaponDefinition.h"
#include "Player/EcoPlayerState.h"
#include "AdaptiveEcosystemCharacter.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Net/UnrealNetwork.h"
UEcoAimComponent::UEcoAimComponent() { SetIsReplicatedByDefault(true); PrimaryComponentTick.bCanEverTick=true; }
bool UEcoAimComponent::SetAiming(bool Value)
{
    auto* E=GetOwner()->FindComponentByClass<UEcoEquipmentComponent>();
    const auto* P=Cast<APawn>(GetOwner()); const auto* S=P?P->GetPlayerState<AEcoPlayerState>():nullptr;
    bAiming=Value && E && E->Weapon && S && S->IsAlive(); return bAiming;
}
void UEcoAimComponent::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick)
{
    Super::TickComponent(Delta,Type,Tick);
    auto* C=Cast<AAdaptiveEcosystemCharacter>(GetOwner()); if (!C) return;
    auto* E=C->FindComponentByClass<UEcoEquipmentComponent>(); auto* W=E?E->Weapon.Get():nullptr;
    auto* D=W?W->Definition.Get():nullptr; auto* S=C->GetPlayerState<AEcoPlayerState>();
    if (!D || !S || !S->IsAlive() || !C->GetController()) bAiming=false;
    if (bAiming && !bCaptured)
    {
        AimOffset=D->AimOffset; AimLength=D->AimArmLength; AimFOV=D->AimFOV; BlendSeconds=D->BlendSeconds;
        OldBoneTick=uint8(C->GetMesh()->VisibilityBasedAnimTickOption);
        C->GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
        DefaultOffset=C->GetCameraBoom()->SocketOffset; DefaultLength=C->GetCameraBoom()->TargetArmLength;
        DefaultFOV=C->GetFollowCamera()->FieldOfView; bOldYaw=C->bUseControllerRotationYaw;
        bOldOrient=C->GetCharacterMovement()->bOrientRotationToMovement; bCaptured=true;
    }
    if (!bCaptured) return;
    if (bAiming)
    {
        BlendSeconds=D->BlendSeconds;
        const float ProfileSpeed=1.f/FMath::Max(.01f,BlendSeconds);
        AimOffset=FMath::VInterpTo(AimOffset,D->AimOffset,Delta,ProfileSpeed);
        AimLength=FMath::FInterpTo(AimLength,D->AimArmLength,Delta,ProfileSpeed);
        AimFOV=FMath::FInterpTo(AimFOV,D->AimFOV,Delta,ProfileSpeed);
    }
    C->bUseControllerRotationYaw=bAiming?true:bOldYaw;
    C->GetCharacterMovement()->bOrientRotationToMovement=bAiming?false:bOldOrient;
    Alpha=FMath::FInterpConstantTo(Alpha,bAiming?1.f:0.f,Delta,1.f/FMath::Max(.01f,BlendSeconds));
    if (C->IsLocallyControlled())
    {
        C->GetCameraBoom()->SocketOffset=FMath::Lerp(DefaultOffset,AimOffset,Alpha);
        C->GetCameraBoom()->TargetArmLength=FMath::Lerp(DefaultLength,AimLength,Alpha);
        C->GetFollowCamera()->SetFieldOfView(FMath::Lerp(DefaultFOV,AimFOV,Alpha));
    }
    if (!bAiming && Alpha<=0) Restore();
}
void UEcoAimComponent::Restore()
{
    if (auto* C=Cast<AAdaptiveEcosystemCharacter>(GetOwner()); C && bCaptured)
    {
        C->GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption(OldBoneTick);
        C->GetCameraBoom()->SocketOffset=DefaultOffset; C->GetCameraBoom()->TargetArmLength=DefaultLength;
        C->GetFollowCamera()->SetFieldOfView(DefaultFOV); C->bUseControllerRotationYaw=bOldYaw;
        C->GetCharacterMovement()->bOrientRotationToMovement=bOldOrient;
    }
    bCaptured=false; Alpha=0;
}
void UEcoAimComponent::EndPlay(const EEndPlayReason::Type Reason) { Restore(); Super::EndPlay(Reason); }
void UEcoAimComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{ Super::GetLifetimeReplicatedProps(OutLifetimeProps); DOREPLIFETIME(UEcoAimComponent,bAiming); }

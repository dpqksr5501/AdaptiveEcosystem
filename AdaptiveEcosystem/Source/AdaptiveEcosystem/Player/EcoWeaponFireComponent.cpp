#include "Player/EcoWeaponFireComponent.h"
#include "Player/EcoEquipmentComponent.h"
#include "Player/EcoWeaponActor.h"
#include "Player/EcoWeaponDefinition.h"
#include "Player/EcoAimComponent.h"
#include "Player/EcoPlayerState.h"
#include "Player/EcoCombatRelevanceComponent.h"
#include "Player/EcoDamageReceiver.h"
#include "Creature/Player/EcoCreatureHitProxy.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "GameFramework/PlayerController.h"
#include "EngineUtils.h"
UEcoWeaponFireComponent::UEcoWeaponFireComponent() { SetIsReplicatedByDefault(true); }
void UEcoWeaponFireComponent::RequestFire()
{
    auto* P=Cast<APawn>(GetOwner()); auto* PC=P?Cast<APlayerController>(P->GetController()):nullptr;
    auto* E=GetOwner()->FindComponentByClass<UEcoEquipmentComponent>();
    if (!PC || !P->IsLocallyControlled() || !E || !E->Weapon) return;
    if (auto* R=P->FindComponentByClass<UEcoCombatRelevanceComponent>()) R->ReportPresented();
    FVector Origin; FRotator Rotation; PC->GetPlayerViewPoint(Origin,Rotation);
    ServerFire(Origin,Rotation.Vector(),E->Weapon);
}
bool UEcoWeaponFireComponent::Trace(const FVector& Start,const FVector& End,FHitResult& Hit) const
{
    const auto* R=GetOwner()->FindComponentByClass<UEcoCombatRelevanceComponent>();
    FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoGun),true,GetOwner());
    TArray<AActor*> Attached; GetOwner()->GetAttachedActors(Attached,true,true); Params.AddIgnoredActors(Attached);
    for (TActorIterator<AEcoCreatureHitProxy> It(GetWorld());It;++It)
        if (!R || !R->CanAttack(It->Coordinator.Get(),It->WorldEpoch,It->StableAgentId)) Params.AddIgnoredActor(*It);
    return GetWorld()->LineTraceSingleByChannel(Hit,Start,End,TraceChannel,Params);
}
void UEcoWeaponFireComponent::ServerFire_Implementation(FVector_NetQuantize Origin,FVector_NetQuantizeNormal Direction,AEcoWeaponActor* Expected)
{
    auto* P=Cast<APawn>(GetOwner()); const auto* S=P?P->GetPlayerState<AEcoPlayerState>():nullptr;
    auto* E=GetOwner()->FindComponentByClass<UEcoEquipmentComponent>(); auto* A=GetOwner()->FindComponentByClass<UEcoAimComponent>();
    auto* W=E?E->Weapon.Get():nullptr; auto* D=W?W->Definition.Get():nullptr;
    const auto* MuzzleProvider=Cast<IEcoRangedWeapon>(W);
    const double Now=GetWorld()->GetTimeSeconds(); FTransform M;
    if (!P || !P->IsPlayerControlled() || !S || !S->IsAlive() || !A || !A->bAiming || !W || W!=Expected || !D
        || Now<NextAllowedFire || (!MuzzleProvider || !MuzzleProvider->GetMuzzleTransform(M)) || Origin.ContainsNaN() || Direction.ContainsNaN()
        || FVector::DistSquared(Origin,P->GetActorLocation())>FMath::Square(650.f)
        || FVector::DotProduct(Direction.GetSafeNormal(),P->GetControlRotation().Vector())<.95f
        || FVector::DistSquared(M.GetLocation(),P->GetActorLocation())>FMath::Square(300.f)
        || !FMath::IsFinite(AmmoDamage) || AmmoDamage<0 || !FMath::IsFinite(D->BaseDamage+AmmoDamage)
        || D->BaseDamage+AmmoDamage<=0 || D->BaseDamage+AmmoDamage>10000 || !FMath::IsFinite(D->Range) || D->Range<=0 || D->Range>200000
        || !FMath::IsFinite(D->FireInterval) || D->FireInterval<.05f)
    { UE_LOG(LogTemp,Verbose,TEXT("[EcoGun][Reject] Aim=%d Weapon=%d Match=%d Alive=%d OriginDistance=%.1f MuzzleDistance=%.1f Dot=%.3f"),
        A?A->bAiming:0,W!=nullptr,W==Expected,S?S->IsAlive():0,FVector::Dist(Origin,GetOwner()->GetActorLocation()),
        FVector::Dist(M.GetLocation(),GetOwner()->GetActorLocation()),P?FVector::DotProduct(Direction.GetSafeNormal(),P->GetControlRotation().Vector()):0); return; }
    FVector Eye; FRotator EyeR; P->GetActorEyesViewPoint(Eye,EyeR);
    FHitResult Guard;
    if (Trace(Eye,Origin,Guard) || Trace(Eye,M.GetLocation(),Guard)) { UE_LOG(LogTemp,Verbose,TEXT("[EcoGun][Reject] Eye obstruction %s"),*GetNameSafe(Guard.GetActor())); return; }
    // Reject a muzzle embedded in a blocking world shape.
    FCollisionQueryParams OverlapParams(SCENE_QUERY_STAT(EcoGunMuzzle),false,P);
    OverlapParams.AddIgnoredActor(W);
    if (GetWorld()->OverlapBlockingTestByChannel(M.GetLocation(),FQuat::Identity,TraceChannel,FCollisionShape::MakeSphere(2),OverlapParams)) { UE_LOG(LogTemp,Verbose,TEXT("[EcoGun][Reject] Muzzle overlap")); return; }
    FHitResult CameraHit;
    const FVector Aim=Trace(Origin,Origin+Direction.GetSafeNormal()*D->Range,CameraHit)?CameraHit.ImpactPoint:Origin+Direction.GetSafeNormal()*D->Range;
    const FVector ShotDirection=(Aim-M.GetLocation()).GetSafeNormal();
    if (FVector::DotProduct(ShotDirection,Direction)<.1f) return;
    NextAllowedFire=Now+D->FireInterval; ++Execution; ShotDamage=D->BaseDamage+AmmoDamage;
    TGuardValue<bool> InShot(bInShot,true); FHitResult Hit;
    const FVector End=M.GetLocation()+ShotDirection*D->Range;
    const bool bHit=Trace(M.GetLocation(),End,Hit);
    MulticastShot(Execution,M.GetLocation(),bHit?Hit.ImpactPoint:End);
    if (!bHit) return;
    if (auto* Proxy=Cast<AEcoCreatureHitProxy>(Hit.GetActor()))
    { if (auto* C=Proxy->Coordinator.Get()) C->QueueWeaponContact(*this,*Proxy,Hit); return; }
    FEcoPointDamage Damage; Damage.Instigator=P; Damage.Weapon=W; Damage.Execution=Execution;
    Damage.Damage=ShotDamage; Damage.Hit=Hit; Damage.Direction=ShotDirection;
    auto* Target=Hit.GetActor(); if (!Target) return;
    if (Target->Implements<UEcoDamageReceiver>()) { IEcoDamageReceiver::Execute_SubmitPointDamage(Target,Damage); return; }
    for (auto* C:Target->GetComponents()) if (C->Implements<UEcoDamageReceiver>()) { IEcoDamageReceiver::Execute_SubmitPointDamage(C,Damage); break; }
}
void UEcoWeaponFireComponent::MulticastShot_Implementation(int64 Id,FVector_NetQuantize M,FVector_NetQuantize E) { OnShot.Broadcast(Id,M,E); }
void UEcoWeaponFireComponent::PublishDamageOutcome(const FEcoCombatDamageOutcome& O) { OnDamageOutcome.Broadcast(O); if (GetNetMode()!=NM_Standalone) ClientDamageOutcome(O); }
void UEcoWeaponFireComponent::ClientDamageOutcome_Implementation(const FEcoCombatDamageOutcome& O)
{ if (!GetOwner()->HasAuthority()) OnDamageOutcome.Broadcast(O); }

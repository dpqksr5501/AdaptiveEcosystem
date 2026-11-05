#include "Player/EcoMeleeHitComponent.h"
#include "Player/EcoGameplayAbility_ComboAttack.h"
#include "Components/SphereComponent.h"
#include "GameFramework/Character.h"
#include "Components/SkeletalMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "Creature/Player/EcoCreatureHitProxy.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Player/EcoPlayerState.h"
#include "EngineUtils.h"
UEcoMeleeHitComponent::UEcoMeleeHitComponent()
{
    SetIsReplicatedByDefault(true);
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickGroup = TG_PostPhysics;
}
void UEcoMeleeHitComponent::SetAbility(UEcoGameplayAbility_ComboAttack* InAbility)
{
    ResetAttack(); Ability = InAbility; ++AttackExecutionId; OpenedSteps.Reset();
}
bool UEcoMeleeHitComponent::HasAuthoritativeWindow() const
{
    const auto* Pawn = Cast<APawn>(GetOwner());
    const auto* State = Pawn ? Pawn->GetPlayerState<AEcoPlayerState>() : nullptr;
    return Pawn && Pawn->HasAuthority() && Pawn->IsPlayerControlled() && (!State || State->IsAlive())
        && Ability.IsValid() && Ability->IsActive() && Ability->CurrentStep == ActiveStep
        && ActiveStep != INDEX_NONE && AttackExecutionId > 0;
}
void UEcoMeleeHitComponent::EvaluateAtEcologyBoundary()
{
    TGuardValue<bool> Boundary(bAtBoundary, true); TickComponent(0, LEVELTICK_All, nullptr);
}
void UEcoMeleeHitComponent::PublishDamageOutcome(const FEcoCombatDamageOutcome& Outcome)
{
    OnDamageOutcome.Broadcast(Outcome);
    if (const auto* Pawn = Cast<APawn>(GetOwner()); Pawn && !Pawn->IsLocallyControlled()) ClientDamageOutcome(Outcome);
}
void UEcoMeleeHitComponent::ClientDamageOutcome_Implementation(const FEcoCombatDamageOutcome& Outcome) { OnDamageOutcome.Broadcast(Outcome); }
void UEcoMeleeHitComponent::ReceiveAttackWindow(EEcoAttackWindow Window, bool bOpen, UAnimSequenceBase* Animation)
{
    if (Ability.IsValid()) Ability->ReceiveWindow(Window, bOpen, Animation);
}
void UEcoMeleeHitComponent::BeginHit(int32 Step)
{
    if (OpenedSteps.Contains(Step)) return;
    StopHit();
    auto* Character = Cast<ACharacter>(GetOwner());
    if (!Character || !Character->HasAuthority() || !AttackData || !AttackData->Steps.IsValidIndex(Step)) return;
    Mesh = Character->GetMesh();
    const auto& Profile = AttackData->Steps[Step];
    if (!FMath::IsFinite(Profile.Radius) || Profile.Radius < 1 || Profile.Radius > 200
        || !FMath::IsFinite(Profile.Damage) || Profile.Damage < 0 || Profile.Damage > 10000
        || AttackData->MaxTargetsPerStep < 1 || AttackData->MaxTargetsPerStep > 32) return;
    if (!Mesh.IsValid() || !Mesh->DoesSocketExist(Profile.Socket)) return;
    if (!Sphere)
    {
        Sphere = NewObject<USphereComponent>(GetOwner(), TEXT("MeleeQuerySphere"));
        Sphere->SetCollisionEnabled(ECollisionEnabled::NoCollision);
        Sphere->SetCollisionResponseToAllChannels(ECR_Ignore);
        Sphere->SetGenerateOverlapEvents(false);
        Sphere->RegisterComponent();
    }
    Sphere->AttachToComponent(Mesh.Get(), FAttachmentTransformRules::SnapToTargetNotIncludingScale, Profile.Socket);
    Sphere->SetSphereRadius(Profile.Radius / FMath::Max(.001f, Sphere->GetComponentScale().GetAbsMax()));
    Sphere->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    ActiveStep = Step; OpenedSteps.Add(Step); HitCreatureIds.Reset();
    HitActors.Reset();
    Previous = Mesh->GetSocketLocation(Profile.Socket);
    SetComponentTickEnabled(true);
    TickComponent(0, LEVELTICK_All, nullptr);
    UE_LOG(LogTemp, Log, TEXT("[EcoCombo] HitOpen Step=%d Socket=%s"), Step, *Profile.Socket.ToString());
}
void UEcoMeleeHitComponent::TickComponent(float Delta, ELevelTick Type, FActorComponentTickFunction* Tick)
{
    Super::TickComponent(Delta, Type, Tick);
    if (!GetOwner()->HasAuthority() || !Mesh.IsValid() || !AttackData || !AttackData->Steps.IsValidIndex(ActiveStep)) return;
    if (!HasAuthoritativeWindow()) { StopHit(); return; }
    if (!bAtBoundary)
        for (TActorIterator<AEcoCreatureIntegrationSpawner> It(GetWorld()); It; ++It)
            if (It->IsRuntimeReady() && It->bEnableEcosystemLife && It->bEnablePlayerCombat) return;
    const auto Profile = AttackData->Steps[ActiveStep];
    const FVector Current = Mesh->GetSocketLocation(Profile.Socket);
    FCollisionObjectQueryParams Objects;
    for (auto Channel : AttackData->TargetObjectTypes) Objects.AddObjectTypesToQuery(Channel);
    FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoSocketAttack), false, GetOwner());
    TArray<AActor*> Attached; GetOwner()->GetAttachedActors(Attached, true, true);
    Params.AddIgnoredActors(Attached);
    TArray<FHitResult> Hits;
    GetWorld()->SweepMultiByObjectType(Hits, Previous, Current, FQuat::Identity, Objects, FCollisionShape::MakeSphere(Profile.Radius), Params);
    for (const auto& Hit : Hits)
    {
        auto* Target = Hit.GetActor();
        if (!IsValid(Target) || HitActors.Contains(Target) || HitActors.Num() >= AttackData->MaxTargetsPerStep) continue;
        auto* Proxy = Cast<AEcoCreatureHitProxy>(Target);
        if (Proxy && (Proxy->StableAgentId <= 0 || HitCreatureIds.Contains(Proxy->StableAgentId))) continue;
        if (FVector::DistSquared(GetOwner()->GetActorLocation(), Hit.ImpactPoint) > FMath::Square(AttackData->MaxReachCm)) continue;
        FHitResult Wall;
        FCollisionQueryParams Visibility = Params; Visibility.AddIgnoredActor(Target);
        FVector Origin; FRotator EyeRotation;
        GetOwner()->GetActorEyesViewPoint(Origin, EyeRotation);
        if (GetWorld()->LineTraceSingleByChannel(Wall, Origin, Hit.ImpactPoint, AttackData->ObstructionChannel, Visibility)) continue;
        HitActors.Add(Target); ++ContactCount;
        if (Proxy)
        {
            HitCreatureIds.Add(Proxy->StableAgentId);
            if (auto* Coordinator = Proxy->Coordinator.Get()) Coordinator->QueueComboContact(*this, *Proxy, Hit);
        }
        UE_LOG(LogTemp, Log, TEXT("[EcoCombo] Contact Step=%d Target=%s DamageCandidate=%.1f"), ActiveStep, *Target->GetName(), Profile.Damage);
        OnContact.Broadcast(Target, Hit, ActiveStep, Profile.Damage);
        if (ActiveStep == INDEX_NONE) break;
    }
    if (AttackData->bDrawDebug) { DrawDebugSphere(GetWorld(), Current, Profile.Radius, 12, FColor::Red, false, .05f); DrawDebugLine(GetWorld(), Previous, Current, FColor::Yellow, false, .1f); }
    Previous = Current;
}
void UEcoMeleeHitComponent::StopHit()
{
    SetComponentTickEnabled(false);
    if (Sphere) Sphere->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ActiveStep = INDEX_NONE; HitActors.Reset();
}
void UEcoMeleeHitComponent::ResetAttack() { StopHit(); Ability.Reset(); }
void UEcoMeleeHitComponent::EndPlay(const EEndPlayReason::Type Reason) { ResetAttack(); Super::EndPlay(Reason); }

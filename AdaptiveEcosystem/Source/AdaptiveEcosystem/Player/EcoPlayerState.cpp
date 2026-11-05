#include "Player/EcoPlayerState.h"
#include "AbilitySystemComponent.h"
#include "Player/EcoHealthAttributeSet.h"
#include "Player/EcoAbilityAvatarComponent.h"
#include "GameplayEffect.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerController.h"
#include "TimerManager.h"

AEcoPlayerState::AEcoPlayerState()
{
    HealthSet = CreateDefaultSubobject<UEcoHealthAttributeSet>(TEXT("Health"));
    AbilitySystem = CreateDefaultSubobject<UAbilitySystemComponent>(TEXT("AbilitySystem"));
    AbilitySystem->SetIsReplicated(true);
    AbilitySystem->SetReplicationMode(EGameplayEffectReplicationMode::Mixed);
}

UAbilitySystemComponent* AEcoPlayerState::GetAbilitySystemComponent() const
{
    return AbilitySystem;
}

void AEcoPlayerState::BeginPlay()
{
    Super::BeginPlay();
    AbilitySystem->GetGameplayAttributeValueChangeDelegate(UEcoHealthAttributeSet::GetHealthAttribute()).AddUObject(this, &ThisClass::HealthChanged);
    if (HasAuthority())
        AbilitySystem->AddLooseGameplayTags(ServerClassificationTags);
    if(auto* Pawn=GetPawn())if(auto* Avatar=Pawn->FindComponentByClass<UEcoAbilityAvatarComponent>())Avatar->RefreshAvatar();
}

void AEcoPlayerState::SetInvulnerable(bool bEnabled) { if(HasAuthority())bInvulnerable=bEnabled; }
float AEcoPlayerState::GetHealth() const { return HealthSet->GetHealth(); }
bool AEcoPlayerState::IsAlive() const { return GetHealth() > 0; }
void AEcoPlayerState::InitializeHealthForAvatar(APawn* Pawn)
{
    if (!HasAuthority() || !Pawn || HealthAvatar.Get() == Pawn) return;
    GetWorldTimerManager().ClearTimer(RespawnTimer);
    // Possession can precede component initialization (including test/server startup).
    if (!AbilitySystem->GetSet<UEcoHealthAttributeSet>()) AbilitySystem->AddAttributeSetSubobject(HealthSet.Get());
    HealthAvatar = Pawn; ++AvatarGeneration; bDeathHandled = false; LastCreatureAttacker = 0;
    AbilitySystem->SetNumericAttributeBase(UEcoHealthAttributeSet::GetHealthAttribute(), HealthSet->GetMaxHealth());
}
float AEcoPlayerState::ApplyCreatureDamage(APawn* ExpectedAvatar, float Damage, int64 AttackerId)
{
    if (!HasAuthority() || !IsAlive() || bInvulnerable || AttackerId <= 0 || !FMath::IsFinite(Damage) || Damage <= 0
        || !ExpectedAvatar || HealthAvatar.Get() != ExpectedAvatar || AbilitySystem->GetAvatarActor() != ExpectedAvatar
        || !ExpectedAvatar->IsPlayerControlled()) return 0;
    const float Before = GetHealth();
    LastCreatureAttacker = AttackerId;
    UGameplayEffect* Effect = NewObject<UGameplayEffect>(GetTransientPackage());
    Effect->DurationPolicy = EGameplayEffectDurationType::Instant;
    FGameplayModifierInfo& Modifier = Effect->Modifiers.AddDefaulted_GetRef();
    Modifier.Attribute = UEcoHealthAttributeSet::GetHealthAttribute();
    Modifier.ModifierOp = EGameplayModOp::Additive;
    Modifier.ModifierMagnitude = FScalableFloat(-FMath::Min(Damage, Before));
    FGameplayEffectSpec Spec(Effect, AbilitySystem->MakeEffectContext(), 1.f);
    AbilitySystem->ApplyGameplayEffectSpecToSelf(Spec);
    const float Applied = Before - GetHealth();
    UE_LOG(LogTemp, Log, TEXT("[EcoCombat][PlayerDamage] Player=%s Wolf=%lld Applied=%.2f HP=%.2f Avatar=%u"), *GetName(), AttackerId, Applied, GetHealth(), AvatarGeneration);
    return Applied;
}
void AEcoPlayerState::HealthChanged(const FOnAttributeChangeData& Change)
{
    OnHealthChanged.Broadcast(GetHealth(), HealthSet->GetMaxHealth());
    if (!IsAlive()) ApplyDeathToAvatar();
}
void AEcoPlayerState::ApplyDeathToAvatar()
{
    auto* Pawn = Cast<APawn>(AbilitySystem->GetAvatarActor());
    if (auto* Character = Cast<ACharacter>(Pawn)) { Character->GetCharacterMovement()->StopMovementImmediately(); Character->GetCharacterMovement()->DisableMovement(); }
    if (!HasAuthority() || bDeathHandled) return;
    bDeathHandled = true;
    AbilitySystem->CancelAllAbilities();
    UE_LOG(LogTemp, Log, TEXT("[EcoCombat][PlayerDeath] Player=%s Wolf=%lld Avatar=%u"), *GetName(), LastCreatureAttacker, AvatarGeneration);
    if (RespawnDelay > 0) GetWorldTimerManager().SetTimer(RespawnTimer, this, &ThisClass::Respawn, RespawnDelay, false);
}
void AEcoPlayerState::Respawn()
{
    auto* Old = HealthAvatar.Get();
    auto* PC = Old ? Cast<APlayerController>(Old->GetController()) : nullptr;
    auto* Mode = GetWorld()->GetAuthGameMode();
    if (!HasAuthority() || IsAlive() || !PC || PC->GetPawn() != Old || !Mode) return;
    PC->UnPossess(); Old->Destroy(); Mode->RestartPlayer(PC);
}
void AEcoPlayerState::EndPlay(const EEndPlayReason::Type Reason)
{
    GetWorldTimerManager().ClearTimer(RespawnTimer);
    Super::EndPlay(Reason);
}

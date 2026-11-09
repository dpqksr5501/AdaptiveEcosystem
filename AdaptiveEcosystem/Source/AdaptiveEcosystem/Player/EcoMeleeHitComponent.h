#pragma once
#include "Components/ActorComponent.h"
#include "Player/EcoAttackWindowReceiver.h"
#include "Player/EcoComboAttackData.h"
#include "Core/EcoCombatTypes.h"
#include "EcoMeleeHitComponent.generated.h"
class UEcoGameplayAbility_ComboAttack;
class USphereComponent;
class USkeletalMeshComponent;
DECLARE_DYNAMIC_MULTICAST_DELEGATE_FourParams(FEcoMeleeContact, AActor*, Target, const FHitResult&, Hit, int32, Step, float, Damage);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FEcoMeleeDamageOutcome, const FEcoCombatDamageOutcome&, Outcome);
/** Contacts are authoritative candidates only. Subscribers decide damage; no ecology dependency. */
UCLASS(ClassGroup=(Combat), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoMeleeHitComponent : public UActorComponent, public IEcoAttackWindowReceiver
{
    GENERATED_BODY()
public:
    UEcoMeleeHitComponent();
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat") TObjectPtr<UEcoComboAttackData> AttackData;
    UPROPERTY(BlueprintAssignable, Category="Combat") FEcoMeleeContact OnContact;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat") int32 ContactCount = 0;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat") int32 ActiveStep = INDEX_NONE;
    UPROPERTY(BlueprintAssignable, Category="Combat") FEcoMeleeDamageOutcome OnDamageOutcome;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat") int64 AttackExecutionId = 0;
    bool HasAuthoritativeWindow() const;
    void EvaluateAtEcologyBoundary();
    void PublishDamageOutcome(const FEcoCombatDamageOutcome& Outcome);
    UFUNCTION(Client, Reliable) void ClientDamageOutcome(const FEcoCombatDamageOutcome& Outcome);
    void SetAbility(UEcoGameplayAbility_ComboAttack* InAbility);
    void BeginHit(int32 Step);
    void StopHit();
    void ResetAttack();
    void ReceiveAttackWindow(EEcoAttackWindow Window, bool bOpen, UAnimSequenceBase* Animation) override;
    void TickComponent(float Delta, ELevelTick Type, FActorComponentTickFunction* Tick) override;
protected:
    void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    TWeakObjectPtr<UEcoGameplayAbility_ComboAttack> Ability;
    UPROPERTY(Transient) TObjectPtr<USphereComponent> Sphere;
    TWeakObjectPtr<USkeletalMeshComponent> Mesh;
    TSet<TWeakObjectPtr<AActor>> HitActors;
    FVector Previous = FVector::ZeroVector;
    TSet<int32> OpenedSteps;
    TSet<int64> HitCreatureIds;
    bool bAtBoundary = false;
};

#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Creature/Audio/EcoFootstepCadence.h"
#include "EcoPlayerEcologyComponent.generated.h"
class UEcoThreatSourceComponent;
class UEcoFootstepAudioComponent;
class UEcoFootstepAudioSet;
class UEcoWeaponFireComponent;
UENUM(BlueprintType)
enum class EEcoPlayerGait : uint8 { Walk, Sneak, Run };
/** Uses server CharacterMovement results. No client RPC can inject noise or choose a position. */
UCLASS(ClassGroup=(Ecology),meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoPlayerEcologyComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UEcoPlayerEcologyComponent();
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
    virtual void TickComponent(float DeltaTime,ELevelTick TickType,FActorComponentTickFunction* ThisTickFunction) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UPROPERTY(EditAnywhere,BlueprintReadOnly,Category="Player|Ecology") bool bThreatEnabled=true;
    UPROPERTY(EditAnywhere,Category="Player|Ecology",meta=(ClampMin="0",Units="cm")) float ShotNoiseRange=6500.f;
    /** Legacy keys are used until the first explicit SetGait call on this pawn. */
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Player|Ecology") bool bUseKeyboardGait=true;
    UPROPERTY(EditDefaultsOnly,Category="Player|Ecology",meta=(ClampMin="1",Units="cm/s")) float WalkSpeed=360.f;
    UPROPERTY(EditDefaultsOnly,Category="Player|Ecology",meta=(ClampMin="1",Units="cm/s")) float SneakSpeed=270.f;
    UPROPERTY(EditDefaultsOnly,Category="Player|Ecology",meta=(ClampMin="1",Units="cm/s")) float RunSpeed=900.f;
    UPROPERTY(EditAnywhere,BlueprintReadOnly,Category="Player|Ecology") TObjectPtr<UEcoFootstepAudioSet> AudioSet;
    UPROPERTY(ReplicatedUsing=OnRep_Gait,BlueprintReadOnly,Category="Player|Ecology") EEcoPlayerGait Gait=EEcoPlayerGait::Walk;
    UFUNCTION(BlueprintCallable,Category="Player|Ecology") void SetGait(EEcoPlayerGait NewGait);
    UFUNCTION(Server,Reliable) void ServerSetGait(EEcoPlayerGait NewGait);
    UFUNCTION(BlueprintCallable,Category="Player|Ecology") void TryStrike();
    UFUNCTION(Server,Reliable) void ServerTryStrike();
private:
    bool bStrikeHeld=false;
    bool bHasExplicitGaitInput=false;
    void ApplyLocalGait(EEcoPlayerGait NewGait);
    UFUNCTION() void OnRep_Gait();
    UFUNCTION() void ObserveConfirmedShot(int64 Execution, FVector Muzzle, FVector End);
    TWeakObjectPtr<UEcoWeaponFireComponent> ShotSource;
    int64 LastShotExecution=0;
    FEcoFootstepCadence ServerCadence;
    UPROPERTY(Transient) TObjectPtr<UEcoThreatSourceComponent> ThreatSource;
    UPROPERTY(Transient) TObjectPtr<UEcoFootstepAudioComponent> LocalAudio;
};

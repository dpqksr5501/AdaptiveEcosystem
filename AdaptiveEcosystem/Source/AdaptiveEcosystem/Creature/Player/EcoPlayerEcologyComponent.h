#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Creature/Audio/EcoFootstepCadence.h"
#include "EcoPlayerEcologyComponent.generated.h"
class UEcoThreatSourceComponent;
class UEcoFootstepAudioComponent;
class UEcoFootstepAudioSet;
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
    virtual void TickComponent(float DeltaTime,ELevelTick TickType,FActorComponentTickFunction* ThisTickFunction) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
    UPROPERTY(EditAnywhere,BlueprintReadOnly,Category="Player|Ecology") bool bThreatEnabled=true;
    /** Disable when an Enhanced Input/Blueprint binding supplies SetGait instead. */
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Player|Ecology") bool bUseKeyboardGait=true;
    UPROPERTY(EditAnywhere,BlueprintReadOnly,Category="Player|Ecology") TObjectPtr<UEcoFootstepAudioSet> AudioSet;
    UPROPERTY(ReplicatedUsing=OnRep_Gait,BlueprintReadOnly,Category="Player|Ecology") EEcoPlayerGait Gait=EEcoPlayerGait::Walk;
    UFUNCTION(BlueprintCallable,Category="Player|Ecology") void SetGait(EEcoPlayerGait NewGait);
    UFUNCTION(Server,Reliable) void ServerSetGait(EEcoPlayerGait NewGait);
    UFUNCTION(BlueprintCallable,Category="Player|Ecology") void TryStrike();
    UFUNCTION(Server,Reliable) void ServerTryStrike();
private:
    bool bStrikeHeld=false;
    UFUNCTION() void OnRep_Gait();
    FEcoFootstepCadence ServerCadence;
    UPROPERTY(Transient) TObjectPtr<UEcoThreatSourceComponent> ThreatSource;
    UPROPERTY(Transient) TObjectPtr<UEcoFootstepAudioComponent> LocalAudio;
};

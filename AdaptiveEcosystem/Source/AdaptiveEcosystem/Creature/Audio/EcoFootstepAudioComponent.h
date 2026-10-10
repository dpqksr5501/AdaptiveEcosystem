#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Creature/Audio/EcoFootstepCadence.h"
#include "Creature/Audio/EcoFootstepNotifyGate.h"
#include "Creature/Representation/EcoCreatureVisualState.h"
#include "EcoFootstepAudioComponent.generated.h"

class UEcoFootstepAudioSet;
class USoundBase;
class UAudioComponent;
struct FEcoCreatureVisualState;
class USkeletalMeshComponent;
class UPhysicalMaterial;

/** Passive local audio only. Never reports gameplay noise, even on a client-owned Actor. */
UCLASS(ClassGroup=(Ecology), meta=(BlueprintSpawnableComponent))
class ADAPTIVEECOSYSTEM_API UEcoFootstepAudioComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UEcoFootstepAudioComponent();
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Footsteps") TObjectPtr<UEcoFootstepAudioSet> AudioSet;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Footsteps") int32 PlayedCount = 0;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Footsteps") FName LastSurface;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Footsteps") TObjectPtr<USoundBase> LastSound;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Footsteps") TObjectPtr<UAudioComponent> LastPlayback;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Footsteps") TObjectPtr<UPhysicalMaterial> LastMaterial;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Footsteps") int32 NotifyPlayedCount = 0;
    UPROPERTY(BlueprintReadOnly, Transient, Category="Footsteps") int32 DistancePlayedCount = 0;
    bool bUseAnimationNotifies = false; // Authored representation setting; never auto-fallback to double playback.
    void ResetCadence() { Cadence.Reset(); NotifyGate.Reset(); LastIndex = INDEX_NONE; CachedState = {}; }
    void Consume(const FEcoCreatureVisualState& State, float Delta, bool bSnap);
    void NotifyContact(USkeletalMeshComponent* Mesh, FName FootBone);
private:
    void PlayContact(const FVector& Source, const TCHAR* Trigger);
    FEcoFootstepCadence Cadence;
    FEcoFootstepNotifyGate NotifyGate;
    FEcoCreatureVisualState CachedState;
    int32 LastIndex = INDEX_NONE;
    FRandomStream Random;
};

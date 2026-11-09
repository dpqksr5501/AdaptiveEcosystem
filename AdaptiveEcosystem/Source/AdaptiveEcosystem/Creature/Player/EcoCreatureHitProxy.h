#pragma once

#include "GameFramework/Actor.h"
#include "EcoCreatureHitProxy.generated.h"

class UCapsuleComponent;
class AEcoCreatureIntegrationSpawner;

/** Server-only query shape. Stable identity belongs to the creature, never this pooled actor. */
UCLASS(NotBlueprintable, Transient)
class ADAPTIVEECOSYSTEM_API AEcoCreatureHitProxy : public AActor
{
    GENERATED_BODY()
public:
    AEcoCreatureHitProxy();
    void Bind(AEcoCreatureIntegrationSpawner* InOwner, int32 Epoch, int64 Id);
    void ClearBinding();
    void Sync(const FVector& GroundPosition, float BodyScale, bool bPredator);
    void SyncCapsule(const FVector& GroundPosition, float Radius, float HalfHeight);
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) TObjectPtr<UCapsuleComponent> Shape;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) int64 StableAgentId = 0;
    UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly) int32 WorldEpoch = 0;
    uint32 BindingGeneration = 0;
    TWeakObjectPtr<AEcoCreatureIntegrationSpawner> Coordinator;
};

#pragma once

#include "Debug/EcoPolicyTestSpawner.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "EcoCreatureDemoSpawner.generated.h"

struct FEcoDemoVisualBinding
{
	FMassEntityHandle Entity;
	TWeakObjectPtr<AEcoCreatureRepresentationActor> Actor;
	int64 Sequence = 0;
	bool bPredator = false;
	int32 PredatorIndex = INDEX_NONE;
	bool bDiscontinuity = false;
};

/** Standalone flat test only. Reuses existing PPO and test predator writer; observes them after PostPhysics. */
UCLASS(Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcoCreatureDemoSpawner : public AEcoPolicyTestSpawner
{
	GENERATED_BODY()
public:
	AEcoCreatureDemoSpawner();
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	virtual void Tick(float DeltaSeconds) override;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Creature|Demo") TSubclassOf<AEcoCreatureRepresentationActor> WolfActorClass;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Creature|Demo") TSubclassOf<AEcoCreatureRepresentationActor> HerbivoreActorClass;
	UFUNCTION(BlueprintCallable, Category="Creature|Demo") void RebuildVisuals();
	UFUNCTION(BlueprintPure, Category="Creature|Demo") int32 GetRepresentedCreatureCount() const;
protected:
	virtual void OnTestEntityReset(FMassEntityHandle Entity) override;
private:
	void DestroyVisuals();
	void SyncVisuals(float DeltaSeconds);
	TArray<FEcoDemoVisualBinding> Bindings;
	bool bDemoActive = false;
};

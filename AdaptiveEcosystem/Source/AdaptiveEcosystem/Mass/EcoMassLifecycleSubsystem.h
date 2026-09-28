#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "EcoMassLifecycleSubsystem.generated.h"

class AEcoMassNetworkBootstrap;

/** Game-thread integration boundary. Owns orchestration, never food, time or agent logical state. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoMassLifecycleSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;
	void RequestInitialization() { bStartRequested = true; }
	bool InitializePopulation();
	bool IsPopulationReady() const { return bInitialized && !bFailed; }
	/** Authority-only; called at the pre-actor boundary, also usable by headless integration tests. */
	void AdvanceSimulation(double DeltaSeconds);
	bool ReconcilePopulation();
private:
	void OnWorldPreActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	bool Fail(const FString& Reason);
	void PublishReady(bool bReady);
	TArray<TWeakObjectPtr<AEcoMassNetworkBootstrap>> Spawners;
	FDelegateHandle TickHandle;
	bool bStartRequested = false;
	bool bInitialized = false;
	bool bFailed = false;
	double ProcessedTime = 0.0;
	double LastPrintTime = -1.0;
};

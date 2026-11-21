#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#if !UE_BUILD_SHIPPING
#include "Debug/EcoMoveTestSubsystem.h"
#include "Mass/EntityHandle.h"
#endif
#include "EcoCameraMassDebug.generated.h"

/** Local diagnostics for the observer camera's current subject. */
UCLASS()
class UEcoCameraMassDebug : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void OnWorldEndPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

#if !UE_BUILD_SHIPPING
	void SetEnabled(bool bEnable);
	void OpenDebugger();
	bool IsEnabled() const { return bEnabled; }
	int64 InspectionAgentId() const { return AgentId; }
	int64 NativeTarget() const { return AgentId; }
	void RecordNative(int64 Id, const FEcoMoveTestSample& Sample);
	FString Describe() const;

private:
	void PostActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	void ClearTarget();
	void ResolveTarget(int64 Id);
	void DrawMovement(const FVector& Location, const FVector& Velocity, double Now);
	void SelectMassEntity();
	void ClearMassSelection();
#if WITH_EDITOR
	void ConnectDebuggerTab();
	FString DescribeMassSelection() const;
#endif

	FDelegateHandle PostTickHandle;
	FMassEntityHandle Entity, MassSelection;
	TOptional<FEcoMoveTestSample> NativeSample;
	TArray<FVector> Trail;
	int64 AgentId = 0;
	int64 RequestedId = 0;
	FName Region;
	double NextTrailAt = 0.0;
	double NextResolveAt = 0.0;
	bool bEnabled = false;
#endif
};

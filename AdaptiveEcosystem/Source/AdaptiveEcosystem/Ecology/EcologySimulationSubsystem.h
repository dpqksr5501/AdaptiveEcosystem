// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Core/EcoEventTypes.h"
#include "Core/EcoIds.h"
#include "Core/EcoRegionTypes.h"
#include "AI/Policy/EcoPolicyContracts.h"
#include "EcologySimulationSubsystem.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnRegionPredationRecorded, FName, RegionId, float, NewPredationHistory);

/**
 * Authoritative World-scoped Subsystem managing dynamic ecology runtime state.
 * Responsible for authoritative regional food amount, carrying capacity,
 * predation history accumulation and decay, and PPO / Utility policy toggling.
 * 
 * Rules:
 * - Created only on Server and Standalone worlds.
 * - Single source of truth for regional food and predation history.
 * - Mutations are reconciled on the game thread after Mass work is buffered.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcologySimulationSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	UEcologySimulationSubsystem();

	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/** True only for a live Standalone, Listen Server, or Dedicated Server game world. */
	UFUNCTION(BlueprintPure, Category = "Ecology|Simulation")
	bool IsAuthoritativeWorld() const;

	/** Ticks regional food regeneration and decays accumulated predation history */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	void TickSimulation(float DeltaTime);

	// -------------------------------------------------------------------------
	// Region Ecology State Management
	// -------------------------------------------------------------------------

	/** Registers initial state for a region. This is not a general-purpose state replacement API. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	bool RegisterRegionState(const FRegionEcologyState& InState);

	/** Queries regional ecology state */
	UFUNCTION(BlueprintPure, Category = "Ecology|Simulation")
	bool GetRegionState(FName RegionId, FRegionEcologyState& OutState) const;

	/** Issues the next non-zero persistent logical ID in this authoritative world. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation|Identity")
	int64 AllocateStableAgentId();

	/** Applies one buffered consumption request to authoritative regional food. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	float ApplyFoodConsumption(const FEcoFoodConsumptionRequest& Request);

	/** Applies one buffered predation event to authoritative regional threat history. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	void ApplyPredationEvent(const FEcoPredationEvent& Event);

	/** Replaces only Mass-owned aggregate metrics; resource fields are untouched. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	bool UpdatePopulationMetrics(const FEcoRegionPopulationSnapshot& Snapshot);

	/** Compatibility wrapper. Prefer ApplyFoodConsumption with a buffered request. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation", meta = (DeprecatedFunction, DeprecationMessage = "Use ApplyFoodConsumption with FEcoFoodConsumptionRequest"))
	float ConsumeFood(FName RegionId, float RequestAmount);

	/** Compatibility wrapper. Prefer ApplyPredationEvent. */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation", meta = (DeprecatedFunction, DeprecationMessage = "Use ApplyPredationEvent with FEcoPredationEvent"))
	void RecordPredationEvent(FName RegionId, float ThreatMagnitude = 0.25f);

	/** Queries current predation history (0.0 .. 1.0) */
	UFUNCTION(BlueprintPure, Category = "Ecology|Simulation")
	float GetPredationHistory(FName RegionId) const;

	// -------------------------------------------------------------------------
	// Policy Runtime Mode
	// -------------------------------------------------------------------------

	/** If true, uses learned PPO policy weights; if false, falls back to Utility baseline */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy")
	bool bUsePPOPolicy = true;

	/** Predation history exponential decay rate per second */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Simulation")
	float PredationDecayRate = 0.05f;

	/** Broadcast when a predation event changes threat level */
	UPROPERTY(BlueprintAssignable, Category = "Ecology|Simulation")
	FOnRegionPredationRecorded OnRegionPredationRecorded;

private:
	bool CanMutateAuthoritativeState(const TCHAR* OperationName) const;
	static FRegionEcologyState MakeSanitizedRegionState(const FRegionEcologyState& InState);

	/** Map of authoritative regional states keyed by RegionId */
	UPROPERTY(Transient)
	TMap<FName, FRegionEcologyState> RegionalStates;

	/** Monotonic world-local allocator; zero is permanently reserved as invalid. */
	FEcoAgentId NextStableAgentId = 1;
};

// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
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
 * - Thread-safe aggregation entry point.
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

	/** Ticks regional food regeneration and decays accumulated predation history */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	void TickSimulation(float DeltaTime);

	// -------------------------------------------------------------------------
	// Region Ecology State Management
	// -------------------------------------------------------------------------

	/** Registers or initializes ecology state for a specific region */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	void RegisterRegionState(const FRegionEcologyState& InState);

	/** Queries regional ecology state */
	UFUNCTION(BlueprintPure, Category = "Ecology|Simulation")
	bool GetRegionState(FName RegionId, FRegionEcologyState& OutState) const;

	/** Sets or updates regional ecology state */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	void SetRegionState(const FRegionEcologyState& InState);

	/** Applies consumption to region's food biomass */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
	float ConsumeFood(FName RegionId, float RequestAmount);

	/** Records a predation/kill event in a region, raising threat level */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Simulation")
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
	/** Map of authoritative regional states keyed by RegionId */
	UPROPERTY(Transient)
	TMap<FName, FRegionEcologyState> RegionalStates;
};

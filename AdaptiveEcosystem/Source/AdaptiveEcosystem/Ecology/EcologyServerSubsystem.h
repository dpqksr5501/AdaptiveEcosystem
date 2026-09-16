// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Core/EcoDataContracts.h"
#include "EcologyServerSubsystem.generated.h"

/**
 * World-scoped authoritative server subsystem for ecology simulation and species state.
 * Owned by Server / Ecology layer.
 * 
 * Note: Does not perform replication directly (subsystems are not replication transports).
 * Replicated state will be hosted in GameState or dedicated replicated actors.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcologyServerSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	/**
	 * Queries the authoritative species evolution profile for a given Region and Species.
	 * Returns true if a profile exists.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server")
	bool GetSpeciesEvolutionProfile(FName RegionId, FName SpeciesId, FSpeciesEvolutionProfile& OutProfile) const;

	/**
	 * Sets or updates a species evolution profile on the server.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server")
	void SetSpeciesEvolutionProfile(const FSpeciesEvolutionProfile& InProfile);

	/**
	 * Creates a default dummy vertical slice profile (Forest_A x Wolf).
	 */
	UFUNCTION(BlueprintPure, Category = "Ecology|Server")
	static FSpeciesEvolutionProfile CreateDummyWolfProfile();

	// -------------------------------------------------------------------------
	// Extension Points for Future Server / Mass Integration (TODO)
	// -------------------------------------------------------------------------
	// - MassEntity logical simulation loop
	// - Resource / Risk / Energy aggregation
	// - Simulation LOD manager
	// - Player Pressure accumulator (FPlayerPressureState)
	// - Evolution trigger / AI Observation builder

private:
	/** Internal cache of authoritative profiles keyed by Composite Key (RegionId_SpeciesId) */
	UPROPERTY(Transient)
	TMap<FName, FSpeciesEvolutionProfile> AuthoritativeProfiles;

	/** Helper to build map key */
	static FName MakeProfileKey(FName RegionId, FName SpeciesId);
};

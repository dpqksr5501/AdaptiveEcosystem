// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Core/EcoDataContracts.h"
#include "Evolution/EvolutionValidator.h"
#include "EcologyServerSubsystem.generated.h"

/**
 * World-scoped authoritative server subsystem for ecology simulation and species state.
 * Owned by Server / Ecology layer.
 * 
 * Rules:
 * - Only created on Standalone, Listen Server, and Dedicated Server (Never on pure NM_Client).
 * - Not a replication transport (Subsystems do not replicate).
 * - All state mutations require server authority.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcologyServerSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** Only create this subsystem on server or standalone worlds */
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;

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
	 * Requires server authority (fails on NM_Client).
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server")
	void SetSpeciesEvolutionProfile(const FSpeciesEvolutionProfile& InProfile);

	/**
	 * Validates an AI evolution proposal via EvolutionValidator and commits it if valid.
	 * Returns true if proposal was accepted and committed.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server")
	bool CommitEvolutionProposal(
		FName RegionId,
		FName SpeciesId,
		const FEvolutionProposal& Proposal,
		int32 ExpectedWorldEpoch,
		int32 ExpectedContextRevision,
		FSpeciesEvolutionProfile& OutCommittedProfile,
		FString& OutRejectReason);

	/**
	 * Creates a default dummy vertical slice profile (Forest_A x Wolf).
	 */
	UFUNCTION(BlueprintPure, Category = "Ecology|Server")
	static FSpeciesEvolutionProfile CreateDummyWolfProfile();

	// -------------------------------------------------------------------------
	// Vegetation Evolution Profiles
	// -------------------------------------------------------------------------

	/**
	 * Queries authoritative vegetation evolution profile for a given Region and VegetationSpecies.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server|Vegetation")
	bool GetVegetationEvolutionProfile(FName RegionId, FName VegetationSpeciesId, FVegetationEvolutionProfile& OutProfile) const;

	/**
	 * Sets or updates a vegetation evolution profile on the server.
	 * Requires server authority (fails on NM_Client).
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server|Vegetation")
	void SetVegetationEvolutionProfile(const FVegetationEvolutionProfile& InProfile);

	/**
	 * Validates a vegetation evolution proposal via EvolutionValidator and commits it if valid.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server|Vegetation")
	bool CommitVegetationEvolutionProposal(
		FName RegionId,
		FName VegetationSpeciesId,
		const FVegetationEvolutionProposal& Proposal,
		int32 ExpectedWorldEpoch,
		int32 ExpectedContextRevision,
		FVegetationEvolutionProfile& OutCommittedProfile,
		FString& OutRejectReason);

	/**
	 * Creates a default dummy vertical slice vegetation profile (Forest_A x Grass_A).
	 */
	UFUNCTION(BlueprintPure, Category = "Ecology|Server|Vegetation")
	static FVegetationEvolutionProfile CreateDummyGrassProfile();

	// -------------------------------------------------------------------------
	// Ecology Events, Grazing Pressure & Dynamic Simulation
	// -------------------------------------------------------------------------

	/**
	 * Ingests an ecology event on the server to update pressure, resources, or environmental counters.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server|Events")
	void IngestEcologyEvent(const FEcologyEvent& Event);

	/**
	 * Records a herbivore grazing or player foraging interaction.
	 * Updates regional grazing pressure and applies consumption directly to the AEcologyRegion actor.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server|Events")
	void RecordGrazing(FName RegionId, FName VegetationSpeciesId, float GrazingAmount, int64 InstigatorAgentId = 0);

	/**
	 * Advances server ecology simulation by DeltaTime:
	 * 1. Drives vegetation regrowth and food recovery in active regions using authoritative profiles.
	 * 2. Decays accumulated pressures over time.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server|Simulation")
	void TickEcologySimulation(float DeltaTime);

	/** Queries accumulated grazing pressure for a region and vegetation species */
	UFUNCTION(BlueprintPure, Category = "Ecology|Server|Pressure")
	float GetGrazingPressure(FName RegionId, FName VegetationSpeciesId) const;

	/** Queries accumulated harvest pressure for a region and vegetation species */
	UFUNCTION(BlueprintPure, Category = "Ecology|Server|Pressure")
	float GetHarvestPressure(FName RegionId, FName VegetationSpeciesId) const;

	/** Queries accumulated player pressure for a region */
	UFUNCTION(BlueprintPure, Category = "Ecology|Server|Pressure")
	FPlayerPressureState GetPlayerPressure(FName RegionId) const;

	/** Builds a complete snapshot of FEvolutionContext for a monster species in a region */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server|Evolution")
	bool BuildMonsterEvolutionContext(FName RegionId, FName SpeciesId, int32 WorldEpoch, int32 ContextRevision, FEvolutionContext& OutContext) const;

	/** Builds a complete snapshot of FVegetationEvolutionContext for a vegetation species in a region */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Server|Evolution")
	bool BuildVegetationEvolutionContext(FName RegionId, FName VegetationSpeciesId, int32 WorldEpoch, int32 ContextRevision, FVegetationEvolutionContext& OutContext) const;

private:
	/** Internal cache of authoritative profiles keyed by Composite Key (RegionId_SpeciesId) */
	UPROPERTY(Transient)
	TMap<FName, FSpeciesEvolutionProfile> AuthoritativeProfiles;

	/** Internal cache of authoritative vegetation profiles keyed by Composite Key (RegionId_VegetationSpeciesId) */
	UPROPERTY(Transient)
	TMap<FName, FVegetationEvolutionProfile> AuthoritativeVegetationProfiles;

	/** Regional grazing pressures keyed by Composite Key (RegionId_VegetationSpeciesId) */
	UPROPERTY(Transient)
	TMap<FName, float> RegionalGrazingPressure;

	/** Regional harvest pressures keyed by Composite Key (RegionId_VegetationSpeciesId) */
	UPROPERTY(Transient)
	TMap<FName, float> RegionalHarvestPressure;

	/** Regional player pressures keyed by RegionId */
	UPROPERTY(Transient)
	TMap<FName, FPlayerPressureState> RegionalPlayerPressure;

	/** Helper to build map key */
	static FName MakeProfileKey(FName RegionId, FName SpeciesId);

	/** Helper to verify server authority */
	bool HasServerAuthority() const;
};

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

	/** Helper to verify server authority */
	bool HasServerAuthority() const;
};

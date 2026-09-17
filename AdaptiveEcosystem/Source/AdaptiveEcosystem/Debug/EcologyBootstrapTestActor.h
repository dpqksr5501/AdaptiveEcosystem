// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Core/EcoDataContracts.h"
#include "EcologyBootstrapTestActor.generated.h"

class ACreatureCharacter;

/**
 * Test harness actor for verifying the bootstrap vertical slice (Forest_A x Wolf).
 * Queries authoritative profiles from UEcologyServerSubsystem and injects them
 * into ACreatureCharacter via InitializeCreature(...), keeping production runtime clean.
 * Owned by Debug / Integration layer.
 */
UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API AEcologyBootstrapTestActor : public AActor
{
	GENERATED_BODY()

public:
	AEcologyBootstrapTestActor();

protected:
	virtual void BeginPlay() override;

public:
	/** Specific target creature to test (if unset, searches level or spawns one) */
	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Ecology|Debug")
	TWeakObjectPtr<ACreatureCharacter> TargetCreature;

	/** Optional creature class to spawn if no target creature is present */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug")
	TSubclassOf<ACreatureCharacter> CreatureClassToSpawn;

	/** Test region ID to query */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug")
	FName TestRegionId;

	/** Test species ID to query */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug")
	FName TestSpeciesId;

	/** Test vegetation species ID to query */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug")
	FName TestVegetationSpeciesId;

	/** If true, automatically executes test on BeginPlay */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Debug")
	bool bAutoRunOnBeginPlay;

	/**
	 * Runs the bootstrap vertical slice test: queries server profile and injects it into target creature.
	 * Also verifies the vegetation evolution pipeline (Forest_A x Grass_A).
	 * Can be triggered via Details panel button (CallInEditor) or console command (Exec).
	 */
	UFUNCTION(BlueprintCallable, CallInEditor, Exec, Category = "Ecology|Debug")
	bool RunBootstrapVerticalSliceTest();

	/**
	 * Specifically tests the vegetation evolution pipeline: creates a context, dummy proposal,
	 * validates, and commits a new vegetation generation profile.
	 */
	UFUNCTION(BlueprintCallable, CallInEditor, Exec, Category = "Ecology|Debug")
	bool RunVegetationEvolutionTest();

	/**
	 * Tests the comprehensive closed-loop eco-feedback system:
	 * 1. Herbivore grazing interaction consumes vegetation and accumulates grazing pressure.
	 * 2. Vegetation evolves via proposal -> increases GrazingResistance and RegenerationRate.
	 * 3. Server simulation tick regrows vegetation with new enhanced traits.
	 * 4. Depleted food availability triggers monster adaptation -> decreases BodyScale and increases Mobility.
	 * 5. Full validation, commit, and verification report.
	 */
	UFUNCTION(BlueprintCallable, CallInEditor, Exec, Category = "Ecology|Debug")
	bool RunEcosystemFeedbackLoopTest();
};


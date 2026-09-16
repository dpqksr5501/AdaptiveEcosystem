// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "EcoDataContracts.generated.h"

// -----------------------------------------------------------------------------
// 1. Environment State
// -----------------------------------------------------------------------------

/**
 * World environment parameters for a specific region.
 * Owned and updated by World / Level layer.
 */
USTRUCT(BlueprintType)
struct FRegionEnvironmentState
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	float Temperature = 20.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	float Humidity = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	float Rainfall = 0.2f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	float VegetationDensity = 0.7f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Environment")
	float FoodAvailability = 0.8f;
};

// -----------------------------------------------------------------------------
// 2. Player Pressure State
// -----------------------------------------------------------------------------

/**
 * Normalized (0..1) player interaction pressure accumulated over time.
 * Managed by Server / Ecology layer.
 */
USTRUCT(BlueprintType)
struct FPlayerPressureState
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float HuntingPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float EncounterPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float PursuitPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float ThreatPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float IntrusionPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float RoutePressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float SuppressionPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float DayPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float NightPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float DayHuntingPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Pressure")
	float NightHuntingPressure = 0.0f;
};

// -----------------------------------------------------------------------------
// 3. Species Trait Groups
// -----------------------------------------------------------------------------

/** Phenotype / Visual traits */
USTRUCT(BlueprintType)
struct FPhenotypeTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.5", ClampMax = "2.0"))
	float BodyScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.5", ClampMax = "2.0"))
	float LegScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.5", ClampMax = "2.0"))
	float BodyBoneScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.0", ClampMax = "2.0"))
	float ColorBrightness = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float ColorTintStrength = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float MorphWeight = 0.0f;
};

/** Gameplay / Combat / Movement traits */
USTRUCT(BlueprintType)
struct FGameplayTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Gameplay", meta = (ClampMin = "0.5", ClampMax = "2.0"))
	float MoveSpeedMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Gameplay", meta = (ClampMin = "0.5", ClampMax = "2.0"))
	float HealthMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Gameplay", meta = (ClampMin = "0.5", ClampMax = "2.0"))
	float AttackMultiplier = 1.0f;
};

/** Behavior / Utility AI / Psychological traits */
USTRUCT(BlueprintType)
struct FBehaviorTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Behavior", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Fear = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Behavior", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Aggression = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Behavior", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float GroupAffinity = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Behavior", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float HidePreference = 0.5f;
};

/** Ecology / Habitat / Activity traits */
USTRUCT(BlueprintType)
struct FEcologyTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Ecology", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float MigrationTendency = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Ecology", meta = (ClampMin = "0.5", ClampMax = "2.0"))
	float RoamRadiusMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Ecology", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float DayActivityPreference = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Ecology", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float NightActivityPreference = 0.5f;
};

// -----------------------------------------------------------------------------
// 4. Species Evolution Profile (Region x Species)
// -----------------------------------------------------------------------------

/**
 * Authoritative species profile committed by Server.
 * Read and applied by Creature Runtime.
 */
USTRUCT(BlueprintType)
struct FSpeciesEvolutionProfile
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Profile")
	FName RegionId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Profile")
	FName SpeciesId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Profile")
	int32 Generation = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Profile")
	int64 ProfileRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Profile")
	FPhenotypeTraits Phenotype;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Profile")
	FGameplayTraits Gameplay;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Profile")
	FBehaviorTraits Behavior;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Profile")
	FEcologyTraits Ecology;
};

// -----------------------------------------------------------------------------
// 5. Creature Spawn Data (Representation Contract)
// -----------------------------------------------------------------------------

/**
 * Minimal payload required to spawn or activate an active creature actor.
 */
USTRUCT(BlueprintType)
struct FCreatureSpawnData
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Spawn")
	int64 StableAgentId = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Spawn")
	int32 WorldEpoch = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Spawn")
	int32 ControlEpoch = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Spawn")
	FName RegionId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Spawn")
	FName SpeciesId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Spawn")
	int32 Generation = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Spawn")
	int64 ProfileRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Spawn")
	int32 RandomSeed = 0;
};

// -----------------------------------------------------------------------------
// 6. Evolution Context & Proposal (AI / LLM Boundaries)
// -----------------------------------------------------------------------------

/**
 * Snapshot passed to Evolution LLM / decision provider.
 */
USTRUCT(BlueprintType)
struct FEvolutionContext
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	int32 WorldEpoch = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	int32 ContextRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	FName RegionId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	FName SpeciesId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	FRegionEnvironmentState Environment;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	FPlayerPressureState Pressure;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	int32 Population = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	int32 Generation = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	FSpeciesEvolutionProfile CurrentProfile;
};

/**
 * Delta proposal generated by Evolution AI before server validation.
 */
USTRUCT(BlueprintType)
struct FEvolutionProposal
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	int32 WorldEpoch = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	int32 ContextRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	int32 ModelRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	int32 SchemaRevision = 0;

	// Phenotype deltas
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float BodyScaleDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float LegScaleDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float BodyBoneScaleDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float ColorBrightnessDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float ColorTintStrengthDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float MorphWeightDelta = 0.0f;

	// Gameplay deltas
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float MoveSpeedDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float HealthDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float AttackDelta = 0.0f;

	// Behavior deltas
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float FearDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float AggressionDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float GroupAffinityDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float HidePreferenceDelta = 0.0f;

	// Ecology deltas
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float MigrationDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float RoamRadiusDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float DayActivityDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Evolution")
	float NightActivityDelta = 0.0f;
};

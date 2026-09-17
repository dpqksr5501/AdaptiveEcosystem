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

// -----------------------------------------------------------------------------
// Trait Hard Limits & Constants (Shared between contracts and validator)
// -----------------------------------------------------------------------------

namespace EcoTraitLimits
{
	// Phenotype limits
	constexpr float BodyScaleMin = 0.80f;
	constexpr float BodyScaleMax = 1.20f;
	constexpr float LegScaleMin = 0.90f;
	constexpr float LegScaleMax = 1.10f;
	constexpr float BodyBoneScaleMin = 0.90f;
	constexpr float BodyBoneScaleMax = 1.10f;
	constexpr float ColorBrightnessMin = 0.70f;
	constexpr float ColorBrightnessMax = 1.20f;
	constexpr float ColorTintStrengthMin = 0.00f;
	constexpr float ColorTintStrengthMax = 1.00f;
	constexpr float MorphWeightMin = 0.00f;
	constexpr float MorphWeightMax = 1.00f;

	// Gameplay limits
	constexpr float MoveSpeedMultiplierMin = 0.80f;
	constexpr float MoveSpeedMultiplierMax = 1.25f;
	constexpr float HealthMultiplierMin = 0.80f;
	constexpr float HealthMultiplierMax = 1.25f;
	constexpr float AttackMultiplierMin = 0.80f;
	constexpr float AttackMultiplierMax = 1.25f;

	// Behavior limits
	constexpr float FearMin = 0.00f;
	constexpr float FearMax = 1.00f;
	constexpr float AggressionMin = 0.00f;
	constexpr float AggressionMax = 1.00f;
	constexpr float GroupAffinityMin = 0.00f;
	constexpr float GroupAffinityMax = 1.00f;
	constexpr float HidePreferenceMin = 0.00f;
	constexpr float HidePreferenceMax = 1.00f;

	// Ecology limits
	constexpr float MigrationTendencyMin = 0.00f;
	constexpr float MigrationTendencyMax = 1.00f;
	constexpr float RoamRadiusMultiplierMin = 0.50f;
	constexpr float RoamRadiusMultiplierMax = 2.00f;
	constexpr float DayActivityPreferenceMin = 0.00f;
	constexpr float DayActivityPreferenceMax = 1.00f;
	constexpr float NightActivityPreferenceMin = 0.00f;
	constexpr float NightActivityPreferenceMax = 1.00f;

	// Validation constraints
	constexpr float DefaultMaxDeltaPerGen = 0.10f;
	constexpr float DefaultMutationBudget = 0.35f;
}

/** Phenotype / Visual traits */
USTRUCT(BlueprintType)
struct FPhenotypeTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.80", ClampMax = "1.20"))
	float BodyScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.90", ClampMax = "1.10"))
	float LegScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.90", ClampMax = "1.10"))
	float BodyBoneScale = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.70", ClampMax = "1.20"))
	float ColorBrightness = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float ColorTintStrength = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Phenotype", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float MorphWeight = 0.0f;
};

/** Gameplay / Combat / Movement traits */
USTRUCT(BlueprintType)
struct FGameplayTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Gameplay", meta = (ClampMin = "0.80", ClampMax = "1.25"))
	float MoveSpeedMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Gameplay", meta = (ClampMin = "0.80", ClampMax = "1.25"))
	float HealthMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Gameplay", meta = (ClampMin = "0.80", ClampMax = "1.25"))
	float AttackMultiplier = 1.0f;
};

/** Behavior / Utility AI / Psychological traits */
USTRUCT(BlueprintType)
struct FBehaviorTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Behavior", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float Fear = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Behavior", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float Aggression = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Behavior", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float GroupAffinity = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Behavior", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float HidePreference = 0.5f;
};

/** Ecology / Habitat / Activity traits */
USTRUCT(BlueprintType)
struct FEcologyTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Ecology", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float MigrationTendency = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Ecology", meta = (ClampMin = "0.50", ClampMax = "2.00"))
	float RoamRadiusMultiplier = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Ecology", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float DayActivityPreference = 0.5f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Traits|Ecology", meta = (ClampMin = "0.00", ClampMax = "1.00"))
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

// -----------------------------------------------------------------------------
// 7. Vegetation Trait Limits & Constants
// -----------------------------------------------------------------------------

namespace EcoVegetationTraitLimits
{
	constexpr float GrowthRateMin = 0.70f;
	constexpr float GrowthRateMax = 1.30f;
	constexpr float RegenerationRateMin = 0.70f;
	constexpr float RegenerationRateMax = 1.30f;
	constexpr float GrazingResistanceMin = 0.00f;
	constexpr float GrazingResistanceMax = 1.00f;

	constexpr float DefaultMaxDeltaPerGen = 0.10f;
	constexpr float DefaultMutationBudget = 0.20f;
}

// -----------------------------------------------------------------------------
// 8. Vegetation Traits & Evolution Contracts
// -----------------------------------------------------------------------------

/**
 * Trait group representing long-term adaptive characteristics of a vegetation species.
 */
USTRUCT(BlueprintType)
struct FVegetationTraits
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Traits", meta = (ClampMin = "0.70", ClampMax = "1.30"))
	float GrowthRate = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Traits", meta = (ClampMin = "0.70", ClampMax = "1.30"))
	float RegenerationRate = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Traits", meta = (ClampMin = "0.00", ClampMax = "1.00"))
	float GrazingResistance = 0.5f;
};

/**
 * Authoritative species evolution profile for vegetation (Region x VegetationSpecies).
 */
USTRUCT(BlueprintType)
struct FVegetationEvolutionProfile
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Profile")
	FName RegionId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Profile")
	FName VegetationSpeciesId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Profile")
	int32 Generation = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Profile")
	int64 ProfileRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Profile")
	FVegetationTraits Traits;
};

/**
 * Snapshot passed to Evolution LLM / decision provider for vegetation adaptation.
 */
USTRUCT(BlueprintType)
struct FVegetationEvolutionContext
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	int32 WorldEpoch = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	int32 ContextRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	FName RegionId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	FName VegetationSpeciesId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	FRegionEnvironmentState Environment;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	float HarvestPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	float GrazingPressure = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	int32 Generation = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	FVegetationEvolutionProfile CurrentProfile;
};

/**
 * Delta proposal generated for vegetation species before server validation.
 */
USTRUCT(BlueprintType)
struct FVegetationEvolutionProposal
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	int32 WorldEpoch = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	int32 ContextRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	int32 ModelRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	int32 SchemaRevision = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	float GrowthRateDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	float RegenerationRateDelta = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Vegetation|Evolution")
	float GrazingResistanceDelta = 0.0f;
};

// -----------------------------------------------------------------------------
// 9. Ecology Events & Ingestion Contracts
// -----------------------------------------------------------------------------

/**
 * Event types ingested by the server ecology layer to track pressure and resource dynamics.
 */
UENUM(BlueprintType)
enum class EEcologyEventType : uint8
{
	CreatureKilled       UMETA(DisplayName = "Creature Killed"),
	CreatureDamaged      UMETA(DisplayName = "Creature Damaged"),
	CreatureGrazed       UMETA(DisplayName = "Creature Grazed"),
	VegetationHarvested  UMETA(DisplayName = "Vegetation Harvested"),
	Encounter            UMETA(DisplayName = "Encounter"),
	Pursuit              UMETA(DisplayName = "Pursuit"),
	RegionEntered        UMETA(DisplayName = "Region Entered"),
	RegionPresence       UMETA(DisplayName = "Region Presence"),
	ResourceChanged      UMETA(DisplayName = "Resource Changed"),
	EnvironmentChanged   UMETA(DisplayName = "Environment Changed")
};

/**
 * Authoritative event passed to UEcologyServerSubsystem to accumulate pressure or trigger updates.
 */
USTRUCT(BlueprintType)
struct FEcologyEvent
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	int64 EventId = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	int32 WorldEpoch = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	EEcologyEventType Type = EEcologyEventType::RegionPresence;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	FName RegionId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	FName SpeciesId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	int64 StableAgentId = 0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	float Magnitude = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Event")
	double SimTimeSeconds = 0.0;
};


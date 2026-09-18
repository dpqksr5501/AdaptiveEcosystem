// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoIds.h"
#include "EcoPolicyContracts.generated.h"

/**
 * PPO Policy and Utility Baseline Data Contracts V1.
 * Must maintain 100% parity with Python RL Environment (Tools/RL/).
 */
namespace EcoPolicyConstants
{
	constexpr int32 PolicySchemaVersion = 1;
	constexpr int32 ObservationDimension = 7;
	constexpr int32 ActionDimension = 4;

	constexpr float MaxPredatorCap = 5.0f;
	constexpr float MaxConspecificCap = 20.0f;
}

/**
 * 7-dimensional normalized observation vector for Policy V1.
 */
USTRUCT(BlueprintType)
struct FEcoPolicyObservationV1
{
	GENERATED_BODY()

	/** 0: Local food abundance ratio (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Observation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float FoodDensity = 0.0f;

	/** 1: Normalized count of predators in view (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Observation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float PredatorCount = 0.0f;

	/** 2: Normalized distance to nearest predator (0.0 = adjacent, 1.0 = out of view) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Observation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float PredatorDistance = 1.0f;

	/** 3: Normalized count of conspecifics in view (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Observation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float ConspecificCount = 0.0f;

	/** 4: Current energy ratio of agent (0.0 = starved, 1.0 = fully satiated) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Observation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Energy = 1.0f;

	/** 5: Recent regional predation history / threat level (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Observation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float RecentPredation = 0.0f;

	/** 6: Normalized distance to nearest cover / shelter (0.0 = inside cover, 1.0 = out of search radius) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Observation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float CoverDistance = 1.0f;

	/** Converts features into contiguous float array matching Python tensor order */
	void ToFloatArray(float OutFeatures[7]) const
	{
		OutFeatures[0] = FoodDensity;
		OutFeatures[1] = PredatorCount;
		OutFeatures[2] = PredatorDistance;
		OutFeatures[3] = ConspecificCount;
		OutFeatures[4] = Energy;
		OutFeatures[5] = RecentPredation;
		OutFeatures[6] = CoverDistance;
	}

	void FromFloatArray(const float InFeatures[7])
	{
		FoodDensity      = InFeatures[0];
		PredatorCount    = InFeatures[1];
		PredatorDistance = InFeatures[2];
		ConspecificCount = InFeatures[3];
		Energy           = InFeatures[4];
		RecentPredation  = InFeatures[5];
		CoverDistance    = InFeatures[6];
	}
};

/**
 * 4-dimensional normalized behavior steering weights output by Policy V1.
 */
USTRUCT(BlueprintType)
struct FEcoPolicyActionV1
{
	GENERATED_BODY()

	/** 0: Steering force multiplier towards nearest food (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Action", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Forage = 0.0f;

	/** 1: Flocking cohesion force multiplier towards flock center (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Action", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Cohesion = 0.0f;

	/** 2: Flee initiation distance threshold / panic multiplier (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Action", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float FleeDist = 0.0f;

	/** 3: Steering force multiplier towards nearest cover / shelter (0.0 .. 1.0) */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Policy|Action", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Cover = 0.0f;

	void ToFloatArray(float OutActions[4]) const
	{
		OutActions[0] = Forage;
		OutActions[1] = Cohesion;
		OutActions[2] = FleeDist;
		OutActions[3] = Cover;
	}

	void FromFloatArray(const float InActions[4])
	{
		Forage   = InActions[0];
		Cohesion = InActions[1];
		FleeDist = InActions[2];
		Cover    = InActions[3];
	}
};

/**
 * Canonical Utility AI Baseline calculation.
 * Produces deterministic actions matching the exact same signature as PPO.
 */
inline FEcoPolicyActionV1 EvaluateUtilityBaseline(const FEcoPolicyObservationV1& Obs)
{
	FEcoPolicyActionV1 Action;
	// 1. Forage: hungry agents strongly prioritize searching for food
	Action.Forage = FMath::Clamp(1.0f - Obs.Energy, 0.0f, 1.0f);

	// 2. Cohesion: higher predation history reinforces group cohesion
	Action.Cohesion = FMath::Clamp(Obs.RecentPredation * 0.8f + Obs.PredatorCount * 0.2f, 0.0f, 1.0f);

	// 3. FleeDist: closer predator or high predation history increases flee sensitivity
	Action.FleeDist = FMath::Clamp((1.0f - Obs.PredatorDistance) * 0.7f + Obs.RecentPredation * 0.3f, 0.0f, 1.0f);

	// 4. Cover: predator presence urges seeking cover
	Action.Cover = FMath::Clamp(Obs.PredatorCount * 0.8f + (1.0f - Obs.CoverDistance) * 0.2f, 0.0f, 1.0f);

	return Action;
}

// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "EcoIds.generated.h"

/**
 * Fundamental identifiers and compact hot-path indices for the AdaptiveEcosystem.
 */

/** Stable logical agent identifier persistent across LOD/Representation boundaries */
typedef int64 FEcoAgentId;

/** Invalid index constant for compact hot-path lookups */
constexpr int32 INDEX_NONE_ECO = -1;

/**
 * Compact runtime indices used in Mass hot loops to avoid repeated FName string hashing.
 */
USTRUCT(BlueprintType)
struct FEcoRuntimeIndices
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Ids")
	int32 RegionIndex = INDEX_NONE_ECO;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Ecology|Ids")
	int32 SpeciesIndex = INDEX_NONE_ECO;
};

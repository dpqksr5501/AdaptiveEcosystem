// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoDataContracts.h"
#include "EcologyLegacyNetworkTypes.generated.h"

/**
 * Legacy-only DTO retained for opt-in LLM trait-evolution experiments.
 * New replication code must use EcologyNetworkTypes.h and must not include this
 * header or serialize FSpeciesEvolutionProfile as core ecology state.
 */
USTRUCT(BlueprintType, meta = (Deprecated, DeprecationMessage = "Legacy Evolution DTO; use active Mass/ecology network summaries"))
struct FReplicatedSpeciesState
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network|Legacy")
	FName RegionId = NAME_None;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network|Legacy")
	FName SpeciesId = NAME_None;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network|Legacy")
	int32 Generation = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network|Legacy")
	int64 ProfileRevision = 0;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Network|Legacy")
	FSpeciesEvolutionProfile Profile;
};

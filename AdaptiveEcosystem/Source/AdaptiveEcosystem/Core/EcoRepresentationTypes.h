// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoIds.h"
#include "EcoRepresentationTypes.generated.h"

/**
 * Read-only logical snapshot consumed by Actor/client representation.
 * Representation may interpolate this data, but must never write it back as
 * authoritative Mass or ecology state.
 */
USTRUCT(BlueprintType)
struct FEcoRepresentationSnapshot
{
	GENERATED_BODY()

	/** FEcoAgentId value. Never an FMassEntityHandle or network transport ID. */
	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Representation")
	int64 StableAgentId = EcoIds::InvalidAgentId;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Representation")
	FName RegionId = NAME_None;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Representation")
	FName SpeciesId = NAME_None;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Representation")
	FVector_NetQuantize10 Location = FVector::ZeroVector;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Representation")
	FRotator Rotation = FRotator::ZeroRotator;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Representation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float NormalizedHealth = 1.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Representation", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float NormalizedEnergy = 1.0f;
};

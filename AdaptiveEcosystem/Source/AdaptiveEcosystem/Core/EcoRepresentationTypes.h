// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoIds.h"
#include "EcoRepresentationTypes.generated.h"

namespace EcoRepresentation
{
	inline uint8 QuantizeUnit(float Value)
	{
		return static_cast<uint8>(FMath::RoundToInt(FMath::Clamp(FMath::IsFinite(Value) ? Value : 0.f, 0.f, 1.f) * 255.f));
	}
}

/** Persistent visual state, independent of proxy relevance and Actor existence. */
UENUM(BlueprintType)
enum class EEcoVisualLifeState : uint8
{
	Alive,
	Dead
};

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

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Representation")
	EEcoVisualLifeState LifeState = EEcoVisualLifeState::Alive;

	/** Server GetRealTimeSeconds(), not ecology WorldClock or client wall time. */
	double ServerSampleRealTimeSeconds = 0.0;
	/** Connection/item-local serial; resets on a fresh Bubble Add. */
	uint32 SampleSequence = 0;
	uint32 VisualRevision = 0;
	uint32 MovementDiscontinuityRevision = 0;
};

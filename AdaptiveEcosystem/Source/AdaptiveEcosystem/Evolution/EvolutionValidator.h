// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "Core/EcoDataContracts.h"
#include "EvolutionValidator.generated.h"

/**
 * Result structure of an evolution proposal validation.
 */
USTRUCT(BlueprintType)
struct FEvolutionValidationResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Evolution")
	bool bAccepted = false;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Evolution")
	FString RejectReason;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Evolution")
	float TotalDeltaSum = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Evolution")
	FSpeciesEvolutionProfile CommittedProfile;
};

/**
 * Result structure of a vegetation evolution proposal validation.
 */
USTRUCT(BlueprintType)
struct FVegetationValidationResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Evolution")
	bool bAccepted = false;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Evolution")
	FString RejectReason;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Evolution")
	float TotalDeltaSum = 0.0f;

	UPROPERTY(BlueprintReadOnly, Category = "Ecology|Evolution")
	FVegetationEvolutionProfile CommittedProfile;
};

/**
 * Server-side validator that verifies and commits AI/LLM evolution proposals.
 * Enforces staleness checks, finite values, delta limits, mutation budget, and trait hard limits.
 * Owned by Server / Ecology / Evolution layer.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEvolutionValidator : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/**
	 * Validates an incoming proposal against current profile and context epoch/revision.
	 * If valid, applies clamped deltas within mutation budget and returns accepted result with new profile.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Evolution")
	static FEvolutionValidationResult ValidateAndApplyProposal(
		const FSpeciesEvolutionProfile& CurrentProfile,
		const FEvolutionProposal& Proposal,
		int32 ExpectedWorldEpoch,
		int32 ExpectedContextRevision,
		float MutationBudget = 0.35f,
		float MaxDeltaPerGen = 0.10f);

	/**
	 * Validates an incoming vegetation proposal against current profile and context epoch/revision.
	 * If valid, applies clamped deltas within mutation budget and returns accepted result with new profile.
	 */
	UFUNCTION(BlueprintCallable, Category = "Ecology|Evolution")
	static FVegetationValidationResult ValidateAndApplyVegetationProposal(
		const FVegetationEvolutionProfile& CurrentProfile,
		const FVegetationEvolutionProposal& Proposal,
		int32 ExpectedWorldEpoch,
		int32 ExpectedContextRevision,
		float MutationBudget = 0.20f,
		float MaxDeltaPerGen = 0.10f);

private:
	/** Checks whether a float is finite and not NaN/Inf */
	static bool IsValidFloat(float Value);
};

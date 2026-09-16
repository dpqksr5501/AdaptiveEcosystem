// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "Core/EcoDataContracts.h"
#include "EvolutionDecisionProvider.generated.h"

UINTERFACE(MinimalAPI, BlueprintType)
class UEvolutionDecisionProvider : public UInterface
{
	GENERATED_BODY()
};

/**
 * Interface defining the boundary for Evolution AI decision providers.
 * Owned by AI / LLM layer.
 * 
 * Flow:
 * FEvolutionContext Snapshot -> Async Task/Worker -> LLM Inference -> FEvolutionProposal -> EvolutionValidator -> Committed Profile
 * 
 * IMPORTANT ARCHITECTURAL BOUNDARY:
 * - RequestProposal(...) is strictly for immediate, non-blocking providers (Dummy, Rule-Based fallback).
 * - DO NOT execute blocking LLM inference (e.g. llama.cpp, HTTP requests) inside RequestProposal on the Game Thread.
 * - Runtime LLM inference MUST run asynchronously on background threads/tasks and deliver results via a thread-safe
 *   proposal queue to be validated by UEvolutionValidator and committed by UEcologyServerSubsystem.
 */
class ADAPTIVEECOSYSTEM_API IEvolutionDecisionProvider
{
	GENERATED_BODY()

public:
	/**
	 * Generates an immediate evolution proposal (rule-based/dummy fallback).
	 * Must NOT block the game thread for heavy computation or external I/O.
	 */
	UFUNCTION(BlueprintCallable, BlueprintNativeEvent, Category = "Ecology|Evolution")
	bool RequestProposal(const FEvolutionContext& Context, FEvolutionProposal& OutProposal);
};

/**
 * Default rule/dummy evolution decision provider used when LLM is disabled or offline.
 */
UCLASS(BlueprintType, Blueprintable)
class ADAPTIVEECOSYSTEM_API UDummyEvolutionDecisionProvider : public UObject, public IEvolutionDecisionProvider
{
	GENERATED_BODY()

public:
	virtual bool RequestProposal_Implementation(const FEvolutionContext& Context, FEvolutionProposal& OutProposal) override;
};

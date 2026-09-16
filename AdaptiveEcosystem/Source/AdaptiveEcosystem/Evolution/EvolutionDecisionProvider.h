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
 * FEvolutionContext -> Provider (Dummy or LLM) -> FEvolutionProposal -> Server Validator -> FSpeciesEvolutionProfile
 */
class ADAPTIVEECOSYSTEM_API IEvolutionDecisionProvider
{
	GENERATED_BODY()

public:
	/**
	 * Generates an evolution proposal given the snapshot context.
	 * Returns true if a proposal was successfully produced.
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

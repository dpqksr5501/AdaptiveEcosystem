// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoIds.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "Mass/EntityHandle.h"
#include "EcoShelterProcessors.generated.h"

/**
 * Periodically searches for defensible shelter slots for agents exhibiting high cover drive or panic state.
 * Generates reservation proposals evaluated downstream.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoShelterQueryProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoShelterQueryProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;
};

/**
 * Reconciles concurrent reservation proposals deterministically (Score -> StableAgentId).
 * Commits winning reservations to UEcoShelterSubsystem and updates agent intent state.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoShelterReservationProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoShelterReservationProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;

	struct FSlotProposal
	{
		FMassEntityHandle Entity;
		int64 StableAgentId = 0;
		int32 SlotIndex = INDEX_NONE_ECO;
		float Score = 0.0f;
	};

	TArray<FSlotProposal> Proposals;
};

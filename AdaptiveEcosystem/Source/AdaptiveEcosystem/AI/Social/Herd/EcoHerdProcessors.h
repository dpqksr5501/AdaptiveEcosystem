// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "EcoHerdProcessors.generated.h"

/**
 * Periodically evaluates spatial proximity to assign or detach agents from persistent herds.
 * Employs hysteresis (JoinRadius < LeaveRadius) and dwell timers to prevent membership thrashing.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoHerdMembershipProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoHerdMembershipProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;
};

/**
 * Aggregates individual member positions and velocities to maintain central herd metrics.
 * Runs in a two-pass reduction pattern to ensure thread safety without lock contention.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoHerdAggregateProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoHerdAggregateProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;

	/** Transient accumulator struct used during Pass 1 chunk reduction */
	struct FHerdAccumulator
	{
		FVector SumLocation = FVector::ZeroVector;
		FVector SumVelocity = FVector::ZeroVector;
		int32 MemberCount = 0;
		FMassEntityHandle BestRepresentative;
		float MinCenterDistSq = MAX_flt;
	};

	TArray<FHerdAccumulator> Accumulators;
};

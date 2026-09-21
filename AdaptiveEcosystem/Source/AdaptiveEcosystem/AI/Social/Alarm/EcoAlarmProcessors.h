// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "EcoAlarmProcessors.generated.h"

/**
 * Propagates alarm signals within herds and across spatial proximities.
 * Updates per-agent alarm strength using exponential time/distance decay and manages social state transitions.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoAlarmPropagationProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoAlarmPropagationProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;
};

/**
 * Modulates PPO policy output actions (Forage, Cohesion, FleeDist, Cover) according to social alert level.
 * Executes after Policy evaluation and before Steering force blending without altering the PPO contract.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoSocialResponseProcessor : public UMassProcessor
{
	GENERATED_BODY()

public:
	UEcoSocialResponseProcessor();

protected:
	virtual void ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager) override;
	virtual void Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context) override;

private:
	FMassEntityQuery EntityQuery;
};

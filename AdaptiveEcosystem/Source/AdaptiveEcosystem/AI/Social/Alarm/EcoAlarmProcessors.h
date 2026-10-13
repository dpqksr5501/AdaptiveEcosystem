// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassProcessor.h"
#include "MassEntityQuery.h"
#include "EcoAlarmProcessors.generated.h"

/**
 * Receives the selected herd threat with exponential distance attenuation and linear time decay.
 * Spatial manual broadcasts are explicit subsystem calls; no cross-herd gossip relay is implemented.
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
 * Executes after Policy evaluation without altering the PPO contract.
 * Downstream steering consumption of ModulatedAction is a separate integration task.
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
	double NextActionAuditLogTime = 0.0;
};

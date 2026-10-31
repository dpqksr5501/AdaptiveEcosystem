#pragma once

#include "CoreMinimal.h"
#include "EcoPolicyInference.h"

/** Worker-owned numeric snapshot. Contains no Entity, Fragment reference, or UObject. */
struct FEcoPolicyBatchItem
{
	float Observation[EcoPolicy::ObsDim] = {};
	float Action[EcoPolicy::ActDim] = {};
	bool bUsedFallback = false;
};

namespace EcoPolicyBatch
{
	/** Returns whether this batch actually used ParallelFor (64+ due items). */
	bool Evaluate(TArray<FEcoPolicyBatchItem>& Items, bool bLearned, bool bParallel);
}

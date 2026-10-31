#pragma once

#include "CoreMinimal.h"
#include "MassReplicationFragments.h"
#include "EcoMassNetworkSettings.generated.h"

/** Runtime connection-wide admission and local Actor budgets, independent of per-template LOD counts. */
USTRUCT(BlueprintType)
struct FEcoConnectionBudgetSettings
{
	GENERATED_BODY()
	UPROPERTY(EditAnywhere, Category="Budget", meta=(ClampMin="1"))
	int32 MaxRelevantAgents = 1000;
	UPROPERTY(EditAnywhere, Category="Budget", meta=(ClampMin="0"))
	int32 MaxActorRepresentations = 64;
	UPROPERTY(EditAnywhere, Category="Budget", meta=(ClampMin="1"))
	int32 MaxAddsPerUpdate = 64;
	bool IsValid() const
	{
		return MaxRelevantAgents > 0 && MaxActorRepresentations >= 0
			&& MaxActorRepresentations <= MaxRelevantAgents && MaxAddsPerUpdate > 0
			&& MaxAddsPerUpdate <= MaxRelevantAgents;
	}
};

namespace EcoMassNetwork
{
	/** Engine thresholds are the START of each grade: High=0, Medium=20m, Low=80m, Off=200m. */
	inline void ApplyExperimentalPreset(FMassReplicationParameters& Params)
	{
		const float Distances[] = {0.0f, 2000.0f, 8000.0f, 20000.0f};
		const float Intervals[] = {0.1f, 0.2f, 0.5f, 1.0f};
		const int32 Counts[] = {64, 256, 680, 0};
		for (int32 LOD = 0; LOD < EMassLOD::Max; ++LOD)
		{
			Params.LODDistance[LOD] = Distances[LOD];
			Params.UpdateInterval[LOD] = Intervals[LOD];
			Params.LODMaxCount[LOD] = Counts[LOD];
			Params.LODMaxCountPerViewer[LOD] = Counts[LOD];
		}
		Params.BufferHysteresisOnDistancePercentage = 10.0f;
	}

	inline bool ValidateParameters(const FMassReplicationParameters& Params, FString& Error)
	{
		for (int32 LOD = 0; LOD < EMassLOD::Max; ++LOD)
		{
			if (!FMath::IsFinite(Params.LODDistance[LOD]) || Params.LODDistance[LOD] < 0.0f
				|| (LOD == 0 && Params.LODDistance[LOD] != 0.0f)
				|| (LOD > 0 && Params.LODDistance[LOD] <= Params.LODDistance[LOD - 1])
				|| !FMath::IsFinite(Params.UpdateInterval[LOD]) || Params.UpdateInterval[LOD] <= 0.0f
				|| Params.LODMaxCount[LOD] < 0 || Params.LODMaxCountPerViewer[LOD] < 0)
			{
				Error = FString::Printf(TEXT("Invalid replication LOD %d: increasing cm distances (High=0), positive finite seconds and nonnegative counts required."), LOD);
				return false;
			}
		}
		if (!FMath::IsFinite(Params.BufferHysteresisOnDistancePercentage)
			|| Params.BufferHysteresisOnDistancePercentage < 0.0f || Params.BufferHysteresisOnDistancePercentage > 100.0f)
		{
			Error = TEXT("Replication hysteresis must be finite and within 0..100 percent.");
			return false;
		}
		Error.Reset();
		return true;
	}
}

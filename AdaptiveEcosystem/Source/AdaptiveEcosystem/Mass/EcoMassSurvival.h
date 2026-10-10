#pragma once
#include "Core/EcoSurvivalTypes.h"
#include "Core/EcoTimeTypes.h"
struct FMassEntityManager;

namespace EcoMassSurvival
{
	/** Authority-only, sequential, outside processing. Commits deferred tags before returning. */
	bool Advance(FMassEntityManager& Manager, const FEcoServerTimeSnapshot& Time, double ObservedTime,
		int64 StepId, const FEcoSurvivalSettings& Settings, TArray<FEcoDeathOutcome>& OutDeaths);
	bool RemoveExpired(FMassEntityManager& Manager, double ObservedTime);
}

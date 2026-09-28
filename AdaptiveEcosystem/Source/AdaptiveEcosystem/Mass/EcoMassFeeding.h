#pragma once
#include "Core/EcoResourceTypes.h"
#include "Core/EcoTimeTypes.h"

struct FMassEntityManager;

/** Explicit, synchronous Mass passes called only at the coordinator's game-thread boundary.
 * No UObject calls in entity loops and no parallel writes to the collection buffer.
 */
namespace EcoMassFeeding
{
	bool FindNextTime(FMassEntityManager& Manager, double After, double& OutTime);
	bool Collect(FMassEntityManager& Manager, const FEcoServerTimeSnapshot& Time, int64 StepId,
		const FEcoFeedingSettings& Settings, TArray<FEcoFeedRequest>& Out);
	bool Apply(FMassEntityManager& Manager, TConstArrayView<FEcoFeedResult> Results, double Interval);
}

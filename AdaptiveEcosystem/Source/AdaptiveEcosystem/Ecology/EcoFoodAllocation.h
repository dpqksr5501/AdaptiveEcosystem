#pragma once
#include "CoreMinimal.h"

namespace EcoFood
{
	/** Pure proportional allocation. Caller supplies a deterministic order (StableAgentId). */
	ADAPTIVEECOSYSTEM_API bool Allocate(double Available, TConstArrayView<double> Requested, TArray<double>& Grants);
}

#include "AI/Policy/EcoPolicyBatch.h"
#include "Async/ParallelFor.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

bool EcoPolicyBatch::Evaluate(TArray<FEcoPolicyBatchItem>& Items, bool bLearned, bool bParallel)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoPolicy_NumericBatch);
	const auto EvaluateOne = [&](int32 Index)
	{
		TRACE_CPUPROFILER_EVENT_SCOPE(EcoPolicy_NumericAgent);
		auto& Item = Items[Index];
		bool bValidObservation = true;
		for (int32 Feature = 0; Feature < EcoPolicy::ObsDim; ++Feature)
		{
			if (!FMath::IsFinite(Item.Observation[Feature]))
			{
				bValidObservation = false;
				Item.Observation[Feature] = (Feature == 2 || Feature == 6) ? 1.f : 0.f;
			}
		}
		if (bLearned) EcoPolicy::RunPolicy(Item.Observation, Item.Action);
		else EcoPolicy::RunUtilityPolicy(Item.Observation, Item.Action);
		bool bValidAction = true;
		for (const float Value : Item.Action) bValidAction &= FMath::IsFinite(Value);
		if (!bValidObservation || !bValidAction)
		{
			Item.bUsedFallback = true;
			EcoPolicy::RunUtilityPolicy(Item.Observation, Item.Action);
		}
		for (float& Value : Item.Action) Value = FMath::Clamp(FMath::IsFinite(Value) ? Value : 0.f, 0.f, 1.f);
	};
	const bool bUsedParallel = bParallel && Items.Num() >= 64;
	if (bUsedParallel) ParallelFor(Items.Num(), EvaluateOne);
	else for (int32 Index = 0; Index < Items.Num(); ++Index) EvaluateOne(Index);
	return bUsedParallel;
}

#include "EcoBehaviorProcessors.h"
#include "EcoBehaviorConfig.h"
#include "EcoBehaviorFragments.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Engine/World.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "EcoPolicyBatch.h"
#include "EcoRegionPredationSubsystem.h"
#include "EcoWorldProviders.h"
#include "HAL/IConsoleManager.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "AI/Policy/EcoObservationBuilder.h"

namespace
{
	/** §9.4 — 학습 정책과 §5.1 Utility 비교군을 런타임에 갈아끼운다. */
	static TAutoConsoleVariable<int32> CVarUseLearnedPolicy(
		TEXT("eco.UseLearnedPolicy"),
		1,
		TEXT("1이면 학습된 PPO 정책(RunPolicy), 0이면 §5.1 Utility 비교군(RunUtilityPolicy)."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarPredationSource(TEXT("eco.Policy.PredationSource"), 0,
		TEXT("0=regional Ecology/provider contract, 1=global training EMA. Explicit experiment; changes observation 5."));

	static TAutoConsoleVariable<int32> CVarParallelPolicy(TEXT("eco.Policy.Parallel"), 0,
		TEXT("Opt-in pure numeric batch workers (64+ due agents across chunks). Providers and Fragment commit stay on GameThread."));

}
UEcoPolicyProcessor::UEcoPolicyProcessor()
	: EntityQuery(*this)
{
	// §9.4 ExecutionFlags = Server. 스탠드얼론도 권위를 가지므로 함께 켠다 (AGENTS.md §2.2).
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPerceptionProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPolicyProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoSteeringGeometryFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoObservationFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoPolicyRuntimeFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoStateTreeBehaviorTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
}

void UEcoPolicyProcessor::Execute(FMassEntityManager& EntityManager,
								  FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const UEcoWorldProviderRegistry* Registry = World->GetSubsystem<UEcoWorldProviderRegistry>();
	UEcoRegionPredationSubsystem* Predation = World->GetSubsystem<UEcoRegionPredationSubsystem>();
	const IEcoWorldFoodProvider* Food = Registry ? Registry->GetFoodProvider() : nullptr;
	const IEcoWorldCoverProvider* Cover = Registry ? Registry->GetCoverProvider() : nullptr;

	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	const float SeeRadius = EcoBehaviorConfig::SeeRadiusCm;
	const bool bLearned = CVarUseLearnedPolicy.GetValueOnGameThread() != 0;
	const bool bParallel = CVarParallelPolicy.GetValueOnGameThread() != 0;
	const bool bGlobalPredation = CVarPredationSource.GetValueOnGameThread() != 0;
	const double Dt = Context.GetDeltaTimeSeconds();
	if (!FMath::IsFinite(Dt) || Dt < 0) return;
	const int32 LegacyTicks = LegacyClock.Advance(float(Dt), EcoBehaviorConfig::StepSeconds, Interval);
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoPolicy_Inference);
	TArray<FEcoPolicyBatchItem> Items;
	TMap<FMassEntityHandle, int32> DueItems;

	EntityQuery.ForEachEntityChunk(Context,
		[Food, Cover, Predation, Interval, SeeRadius, bGlobalPredation, Dt, LegacyTicks, &Items, &DueItems](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FEcoSteeringGeometryFragment> Geometries =
			Ctx.GetFragmentView<FEcoSteeringGeometryFragment>();
		const TConstArrayView<FEcoVitalsFragment> Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		const TArrayView<FEcoObservationFragment> Observations =
			Ctx.GetMutableFragmentView<FEcoObservationFragment>();
		const TArrayView<FEcoPolicyRuntimeFragment> Runtimes =
			Ctx.GetMutableFragmentView<FEcoPolicyRuntimeFragment>();

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (Vitals[i].HP <= 0) continue;
			auto& Runtime = Runtimes[i];
			Runtime.PolicyAliveSeconds += Dt;
			if (Ctx.GetFragmentView<FEcoIdentityFragment>().IsEmpty())
            {
                // Legacy flat RL path keeps the exported logical-tick contract.
                if (Runtime.LastPolicyStep < 0) Runtime.LastPolicyStep = int32(Ctx.GetEntity(i).Index % Interval);
                if (!EcoPolicy::AdvanceDecisionPhase(Runtime.LastPolicyStep, LegacyTicks, Interval)) continue;
            }
            else
            {
            const double Period = double(Interval) / 60.0 * FMath::Clamp(Runtime.DecisionIntervalMultiplier, 1.f, 8.f);
			if (Runtime.PolicyElapsedSeconds < 0) Runtime.PolicyElapsedSeconds = Runtime.LastPolicyStep / 60.0;
			Runtime.PolicyElapsedSeconds += Dt;
			if (Runtime.PolicyElapsedSeconds + 1.e-8 < Period) continue;
			Runtime.PolicyElapsedSeconds -= Period; // preserve decision debt after a hitch
			Runtime.LastPolicyStep = 0;
            }

			const FVector Self = Transforms[i].GetTransform().GetLocation();
			const FEcoSteeringGeometryFragment& G = Geometries[i];

			// --- §3.1 관측 7개. 정규화 상수는 전부 고정값이다 (§1.2) ---
			FEcoPolicyObservationV1& Obs = Observations[i].Observation;
			Obs = EcoObservation::Build(Self, G, Vitals[i], Food, Cover, Predation, bGlobalPredation);

			DueItems.Add(Ctx.GetEntity(i), Items.Num());
			auto& Item = Items.AddDefaulted_GetRef();
			Obs.ToFloatArray(Item.Observation);
		}
	});
	// One numeric batch across chunks: small Social archetypes can still reach the worker threshold.
	const bool bUsedParallel = EcoPolicyBatch::Evaluate(Items, bLearned, bParallel);
	// Barrier has completed. Reacquire views; never retain fragment references on a worker.
	EntityQuery.ForEachEntityChunk(Context, [&Items, &DueItems, bUsedParallel](FMassExecutionContext& Ctx)
	{
		const auto Outputs = Ctx.GetMutableFragmentView<FEcoPolicyOutputFragment>();
		const auto Runtimes = Ctx.GetMutableFragmentView<FEcoPolicyRuntimeFragment>();
		for (int32 I = 0; I < Ctx.GetNumEntities(); ++I)
		{
			const auto* Index = DueItems.Find(Ctx.GetEntity(I)); if (!Index) continue;
			const auto& Item = Items[*Index];
			Runtimes[I].InferenceFallbackCount += Item.bUsedFallback;
			++Runtimes[I].CompletedPolicyDecisions;
			Runtimes[I].ParallelPolicyDecisions += bUsedParallel;
			auto& Out = Outputs[I].Action;
			Out.Forage = Item.Action[0]; Out.Cohesion = Item.Action[1];
			Out.FleeDist = Item.Action[2]; Out.Cover = Item.Action[3];
		}
	});

}

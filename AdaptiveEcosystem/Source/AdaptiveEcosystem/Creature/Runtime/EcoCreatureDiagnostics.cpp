#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Core/EcoRuntimeSettings.h"
#include "Mass/EcoMassFragments.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "World/EcoWorldClockSubsystem.h"
#include "MassSpawnerSubsystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Mass/EntityFragments.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Ecology/EcologySimulationSubsystem.h"

void AEcoCreatureIntegrationSpawner::DumpRuntime(bool bDetails) const
{
	auto* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>();
	if (!Spawner || Spawner->GetEntityManagerChecked().IsProcessing()) return;
	const auto& EM = Spawner->GetEntityManagerChecked();
	int32 Alive = 0, Dead = 0, Far = 0;
	uint64 Decisions = 0, ParallelDecisions = 0; int64 Fallbacks = 0; double PolicySeconds = 0;
	double MaxPolicyDebt = 0;
	for (const auto E : Owned) if (EM.IsEntityValid(E))
	{
		const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		Alive += V.HP > 0; Dead += V.HP <= 0;
		if (const auto* Runtime = EM.GetFragmentDataPtr<FEcoPolicyRuntimeFragment>(E))
		{
			Far += Runtime->DecisionIntervalMultiplier > 1; MaxPolicyDebt = FMath::Max(MaxPolicyDebt, Runtime->PolicyElapsedSeconds);
			Decisions += Runtime->CompletedPolicyDecisions; Fallbacks += Runtime->InferenceFallbackCount;
			ParallelDecisions += Runtime->ParallelPolicyDecisions;
			PolicySeconds += Runtime->PolicyAliveSeconds;
			if (bDetails)
			{
				const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
				const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(E);
				const auto& Obs = EM.GetFragmentDataChecked<FEcoObservationFragment>(E).Observation;
				const auto& Action = EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
				const auto& Request = EM.GetFragmentDataChecked<FEcoSocialMovementRequestFragment>(E);
				const auto& Feed = EM.GetFragmentDataChecked<FEcoFeedingFragment>(E);
				UE_LOG(LogTemp, Log, TEXT("[Eco Agent Audit] Step=%lld Id=%lld Region=%s HP=%.3f Energy=%.3f Decisions=%llu AliveSeconds=%.3f Debt=%.3f ObsFood=%.4f ObsPredation=%.4f RawForage=%.4f SocialForage=%.4f LastFeed=%.3f Granted=%.3f TotalFood=%.3f"),
					Step, Id.StableAgentId, *Region.CurrentRegionId.ToString(), V.HP, V.Energy,
					Runtime->CompletedPolicyDecisions, Runtime->PolicyAliveSeconds, Runtime->PolicyElapsedSeconds,
					Obs.FoodDensity, Obs.RecentPredation, Action.Forage, Request.EffectiveAction.Forage,
					Feed.LastFeedTime, Feed.LastGrantedAmount, Feed.TotalGrantedAmount);
			}
		}
	}
	const auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
	const double Debt = Clock ? FMath::Max(0.0, Clock->GetServerTime().ServerTimeSeconds - LastResourceTime) : 0;
	const auto& Budget = GetDefault<UEcoRuntimeSettings>()->ConnectionBudget;
	UE_LOG(LogTemp, Log, TEXT("[Eco Integration Audit] World=%s Mode=%d Ready=%d Step=%lld Alive=%d Dead=%d Births=%lld Deaths=%lld ResourceDebt=%.3f PolicyDebt=%.3f FarPolicy=%d Actors=%d Pool=%d ActorBudget=%d AddBudget=%d"),
		*GetWorld()->GetName(), int32(GetNetMode()), bReady, Step, Alive, Dead, SuccessfulBirths, CommittedDeaths,
		Debt, MaxPolicyDebt, Far, Visuals.Num(), VisualPool.Num(), Budget.MaxActorRepresentations, Budget.MaxAddsPerUpdate);
	UE_LOG(LogTemp, Log, TEXT("[Eco Policy Audit] Decisions=%llu AgentSeconds=%.3f DecisionsPerAgentSecond=%.3f Fallbacks=%lld ParallelDecisions=%llu"),
		Decisions, PolicySeconds, PolicySeconds > 0 ? Decisions / PolicySeconds : 0, Fallbacks, ParallelDecisions);
	if (!bDetails) return;
	if (const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>())
	{
		TArray<FName> Ids; Ecology->GetRegionIds(Ids);
		for (FName Id : Ids)
		{
			FRegionEcologyState State; if (!Ecology->GetRegionState(Id, State)) continue;
			UE_LOG(LogTemp, Log, TEXT("[Eco Region Audit] Step=%lld Region=%s Pop=%d Food=%.3f Rain=%.3f Regeneration=%.3f Predation=%.4f Out=%d In=%d"),
				Step, *Id.ToString(), State.Population, State.FoodAmount, State.CompletedEnvironment.Rainfall,
				State.FoodRegenerationRate * State.EffectiveRegenerationMultiplier, State.PredationHistory, State.OutboundCount, State.IncomingCount);
		}
	}
	if (GetNetMode() == NM_Client)
	{
		FMassEntityQuery Query(Spawner->GetEntityManagerChecked().AsShared());
		Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::All);
		Query.AddRequirement<FEcoClientPresentationFragment>(EMassFragmentAccess::ReadOnly);
		auto Context = Spawner->GetEntityManagerChecked().CreateExecutionContext(0.f);
		Query.ForEachEntityChunk(Context, [](FMassExecutionContext& C)
		{
			for (const auto& Sample : C.GetFragmentView<FEcoClientPresentationFragment>())
				UE_LOG(LogTemp, Log, TEXT("[Eco Receive Audit] Id=%lld Sequence=%u VisualRevision=%u Movement=%llu Presentation=%llu Reset=%llu Rejected=%llu"),
					Sample.Current.StableAgentId, Sample.Current.SampleSequence, Sample.Current.VisualRevision,
					Sample.MovementUpdates, Sample.PresentationUpdates, Sample.ResetUpdates, Sample.RejectedUpdates);
		});
	}
}

#if !UE_BUILD_SHIPPING
static FAutoConsoleCommandWithWorldAndArgs EcoIntegrationDump(TEXT("eco.Integration.Dump"),
	TEXT("Manual integration counts, conservation and logical scheduling debt in the selected world."),
	FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
	{
		if (World && IsInGameThread()) for (TActorIterator<AEcoCreatureIntegrationSpawner> It(World); It; ++It) It->DumpRuntime(Args.Contains(TEXT("details")));
	}));
#endif

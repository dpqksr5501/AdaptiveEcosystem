#include "Mass/EcoMassLifecycleSubsystem.h"
#include "Mass/EcoMassNetworkBootstrap.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EcoMassFeeding.h"
#include "World/EcoWorldClockSubsystem.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Core/EcoRuntimeSettings.h"
#include "Network/EcoGameState.h"
#include "AdaptiveEcosystem.h"
#include "Engine/World.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"

bool UEcoMassLifecycleSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return Super::ShouldCreateSubsystem(Outer) && World && World->IsGameWorld() && World->GetNetMode() != NM_Client;
}

void UEcoMassLifecycleSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	Collection.InitializeDependency<UEcoWorldClockSubsystem>();
	Collection.InitializeDependency<UEcologyWorldSubsystem>();
	Collection.InitializeDependency<UEcologySimulationSubsystem>();
	Collection.InitializeDependency<UMassSpawnerSubsystem>();
	TickHandle = FWorldDelegates::OnWorldPreActorTick.AddUObject(this, &UEcoMassLifecycleSubsystem::OnWorldPreActorTick);
}

void UEcoMassLifecycleSubsystem::Deinitialize()
{
	FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);
	Spawners.Reset();
	bInitialized = false;
	bStartRequested = false;
	PreviousDawnPopulation.Reset();
	StepId = 0;
	LastReportedCycle = -1;
	ProcessedTime = 0.0;
	Super::Deinitialize();
}

void UEcoMassLifecycleSubsystem::PublishReady(bool bReady)
{
	if (AEcoGameState* State = GetWorld()->GetGameState<AEcoGameState>())
	{
		State->SetMassReplicationReady(bReady);
		State->SetWorldPhase(bReady ? EEcoWorldPhase::Running : EEcoWorldPhase::BootstrappingMass);
	}
}

bool UEcoMassLifecycleSubsystem::Fail(const FString& Reason)
{
	bFailed = true;
	PublishReady(false);
	UE_LOG(LogAdaptiveEcosystem, Error, TEXT("[Eco M3.1] Population stopped: %s"), *Reason);
	return false;
}

bool UEcoMassLifecycleSubsystem::InitializePopulation()
{
	if (!IsInGameThread() || !GetWorld() || !GetWorld()->IsGameWorld() || GetWorld()->GetNetMode() == NM_Client || bFailed) return false;
	if (bInitialized) return true;
	const UEcoRuntimeSettings* Settings = GetDefault<UEcoRuntimeSettings>();
	FeedingSettings = Settings->Feeding;
	bSpawnWaves = Settings->bEnableSpawnWaves;
	bReportDaily = Settings->bPrintDailyPopulation;
	bReportDailyToScreen = Settings->bPrintDailyPopulationToScreen;
	if (!FeedingSettings.IsValid() || !Settings->DayFoodEvent.IsValid() || !Settings->NightFoodEvent.IsValid())
		return Fail(TEXT("Invalid feeding or food-event settings. Restart PIE after correcting Project Settings."));
	UEcologySimulationSubsystem* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	UEcoWorldClockSubsystem* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
	UMassSpawnerSubsystem* Mass = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>();
	if (!Ecology || !Clock || !Mass || Mass->GetEntityManagerChecked().IsProcessing()) return Fail(TEXT("Authority services unavailable or Mass is processing."));
	FEcoDayCycleState Phase;
	if (Settings->RequiredRegionCount < 1 || Settings->GlobalPopulationLimit < 1
		|| !EcoClock::EvaluateFixedCycle(0.0, Settings->DayDurationSeconds, Settings->NightDurationSeconds, Phase))
		return Fail(TEXT("Invalid M3 project clock/population settings."));

	TMap<FName, AEcologyRegion*> Regions;
	for (TActorIterator<AEcologyRegion> It(GetWorld()); It; ++It)
	{
		FRegionEcologyState Initial;
		if (!It->MakeInitialEcologyState(Initial) || Regions.Contains(It->RegionId)
			|| !It->ContainsPosition(It->GetActorTransform().TransformPosition(It->ArrivalOffset)))
			return Fail(TEXT("Invalid/duplicate RegionId, Food settings or arrival position."));
		Regions.Add(It->RegionId, *It);
	}
	if (Regions.Num() < Settings->RequiredRegionCount) return Fail(FString::Printf(
		TEXT("Place at least %d EcologyRegion actors and bind one Mass Bootstrap to each."), Settings->RequiredRegionCount));
	if ((Settings->DayFoodEvent.bEnabled && !Regions.Contains(Settings->DayFoodEvent.RegionId))
		|| (Settings->NightFoodEvent.bEnabled && !Regions.Contains(Settings->NightFoodEvent.RegionId)))
		return Fail(TEXT("An enabled food event targets an unknown RegionId. Set its target or disable it in Project Settings."));
	for (const auto& Pair : Regions)
	{
		for (FName Neighbor : Pair.Value->AdjacentRegionIds)
			if (Neighbor == Pair.Key || !Regions.Contains(Neighbor)) return Fail(TEXT("Region adjacency references itself or an unregistered region."));
	}

	TMap<FName, AEcoMassNetworkBootstrap*> ByRegion;
	int64 TotalInitial = 0;
	for (TActorIterator<AEcoMassNetworkBootstrap> It(GetWorld()); It; ++It)
	{
		const FName RegionId = It->GetConfiguredRegionId();
		AEcologyRegion* const* Region = Regions.Find(RegionId);
		FString Error;
		if (!Region || ByRegion.Contains(RegionId)) return Fail(TEXT("Each Bootstrap must bind to a distinct registered Region."));
		if (!It->ValidateConfiguration(**Region, Error)) return Fail(It->GetName() + TEXT(": ") + Error);
		ByRegion.Add(RegionId, *It);
		TotalInitial += It->InitialAgentCount;
	}
	if (ByRegion.Num() != Regions.Num() || TotalInitial > Settings->GlobalPopulationLimit)
		return Fail(TEXT("All regions require a Bootstrap, and initial counts must fit the global cap."));
	if (Clock->IsClockRunning()) return Fail(TEXT("Clock was started outside the population coordinator."));
	FEcoServerTimeSnapshot InitialTime;
	if (!Clock->GetSnapshotAt(0.0, InitialTime)) return Fail(TEXT("Day-cycle provider rejected initial time."));
	const AEcoGameState* State = GetWorld()->GetGameState<AEcoGameState>();
	InitialTime.WorldEpoch = State ? FMath::Max(1, State->GetWorldEpoch()) : 1;
	if (!Ecology->ConfigurePopulationLimit(Settings->GlobalPopulationLimit)) return Fail(TEXT("Population limits already locked."));

	// All authoring inputs were checked before committing state or creating any population.
	TArray<FName> RegionOrder;
	Regions.GetKeys(RegionOrder);
	RegionOrder.Sort(FNameLexicalLess());
	Spawners.Reset();
	for (FName RegionId : RegionOrder)
	{
		AEcologyRegion& Region = *Regions[RegionId];
		AEcoMassNetworkBootstrap& Bootstrap = *ByRegion[RegionId];
		FRegionEcologyState Initial;
		Region.MakeInitialEcologyState(Initial);
		if (!Ecology->RegisterRegionState(Initial) || !Ecology->RegisterSpawnSchedule(RegionId, Bootstrap.SpawnSchedule))
			return Fail(TEXT("Region state or spawn schedule already registered."));
		Bootstrap.PrepareRuntime(Region, Ecology->GetRegionRuntimeIndex(RegionId), Ecology->RegisterSpecies(Bootstrap.SpeciesId), FeedingSettings.FirstFeedDelaySeconds);
		Spawners.Add(&Bootstrap);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Region] %s Food=%.2f Capacity=%.2f Regen=0"),
			*RegionId.ToString(), Initial.FoodAmount, Initial.FoodCapacity);
	}
	if (!ReconcilePopulation()) return Fail(TEXT("Invalid authority entity membership before initial spawn."));
	if (!Ecology->StartResourceSimulation(InitialTime.WorldEpoch, Settings->DayFoodEvent, Settings->NightFoodEvent, Settings->bPrintResourceChanges))
		return Fail(TEXT("Resource simulation configuration rejected."));
	for (const auto& Weak : Spawners)
	{
		AEcoMassNetworkBootstrap& Bootstrap = *Weak.Get();
		FEcoSpawnRequest Request;
		if (!Ecology->RequestInitialSpawn(Bootstrap.GetConfiguredRegionId(), Bootstrap.InitialAgentCount, InitialTime, Request))
			return Fail(TEXT("Initial spawn request rejected."));
		const int32 Actual = Bootstrap.ExecuteSpawnRequest(Request, 0.0);
		const bool bMetricsValid = ReconcilePopulation();
		Ecology->CompleteSpawnRequest(Request.RequestId, Actual);
		if (!bMetricsValid || Actual != Bootstrap.InitialAgentCount || !Bootstrap.IsMassNetworkInitialized())
			return Fail(TEXT("Initial spawn incomplete. Restart after correcting the configuration; this request will not be replayed."));
	}
	if (!Clock->StartClock(InitialTime.WorldEpoch, Settings->DayDurationSeconds, Settings->NightDurationSeconds))
		return Fail(TEXT("Authority clock could not start."));
	// Initial seeding is special. Phase-start events then run through the same ordered path as later steps.
	if (!ProcessEcologyStep(Clock->GetServerTime(), 0.0)) return false;
	bInitialized = true;
	PublishReady(true);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco M3.1] Ready: Regions=%d InitialAgents=%lld"), Regions.Num(), TotalInitial);
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco M3.2] Ready: Feeding=%d FirstFeed=%.2f Interval=%.2f Amount=%.2f Waves=%d DayEvent=%d NightEvent=%d"),
		FeedingSettings.bEnabled, FeedingSettings.FirstFeedDelaySeconds, FeedingSettings.IntervalSeconds, FeedingSettings.Amount,
		bSpawnWaves, Settings->DayFoodEvent.bEnabled, Settings->NightFoodEvent.bEnabled);
	return true;
}

bool UEcoMassLifecycleSubsystem::ReconcilePopulation()
{
	if (!IsInGameThread() || GetWorld()->GetNetMode() == NM_Client) return false;
	UMassSpawnerSubsystem* Spawner = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>();
	UEcologySimulationSubsystem* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	if (!Spawner || !Ecology) return false;
	FMassEntityManager& Manager = Spawner->GetEntityManagerChecked();
	if (Manager.IsProcessing()) return false;
	TArray<FName> RegionIds;
	Ecology->GetRegionIds(RegionIds);
	TArray<FEcoRegionPopulationSnapshot> Metrics;
	Metrics.SetNum(RegionIds.Num());
	for (int32 Index = 0; Index < RegionIds.Num(); ++Index) Metrics[Index].RegionId = RegionIds[Index];
	bool bValid = true;
	// This subsystem query has no processor owner to initialize it. Bind to this
	// world's manager before adding requirements (required by UE 5.8).
	FMassEntityQuery Query(Manager.AsShared());
	Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
	Query.ForEachEntityChunk(Context, [&Metrics, &bValid](FMassExecutionContext& Chunk)
	{
		const auto Regions = Chunk.GetFragmentView<FEcoRegionFragment>();
		const auto Vitals = Chunk.GetFragmentView<FEcoVitalsFragment>();
		for (int32 Index = 0; Index < Chunk.GetNumEntities(); ++Index)
		{
			const int32 RegionIndex = Regions[Index].CurrentRegionIndex;
			if (!Metrics.IsValidIndex(RegionIndex) || Metrics[RegionIndex].RegionId != Regions[Index].CurrentRegionId
				|| !FMath::IsFinite(Vitals[Index].Energy) || !FMath::IsFinite(Vitals[Index].MaxEnergy))
			{
				bValid = false;
				continue;
			}
			++Metrics[RegionIndex].Population;
			Metrics[RegionIndex].AverageEnergy += Vitals[Index].MaxEnergy > 0.0f
				? FMath::Clamp(Vitals[Index].Energy / Vitals[Index].MaxEnergy, 0.0f, 1.0f) : 0.0f;
		}
	});
	if (!bValid) return false;
	for (FEcoRegionPopulationSnapshot& Metric : Metrics)
	{
		Metric.AverageEnergy = Metric.Population > 0 ? Metric.AverageEnergy / Metric.Population : 0.0f;
		if (!Ecology->UpdatePopulationMetrics(Metric)) return false;
	}
	return true;
}

void UEcoMassLifecycleSubsystem::OnWorldPreActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
	if (World != GetWorld() || TickType != LEVELTICK_All || !World->HasBegunPlay() || bFailed) return;
	if (!bInitialized && bStartRequested) InitializePopulation();
	AdvanceSimulation(DeltaSeconds);
}

void UEcoMassLifecycleSubsystem::AdvanceSimulation(double DeltaSeconds)
{
	if (!IsInGameThread() || !IsPopulationReady() || GetWorld()->GetNetMode() == NM_Client) return;
	UEcoWorldClockSubsystem* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
	UEcologySimulationSubsystem* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	UMassSpawnerSubsystem* Mass = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>();
	if (!Clock->AdvanceClock(DeltaSeconds)) { Fail(TEXT("Invalid server time/day-cycle provider output.")); return; }
	const FEcoServerTimeSnapshot Now = Clock->GetServerTime();
	const UEcoRuntimeSettings* Settings = GetDefault<UEcoRuntimeSettings>();
	const double PrintInterval = FMath::IsFinite(Settings->ServerTimePrintInterval) ? FMath::Max(0.25, Settings->ServerTimePrintInterval) : 1.0;
	if (Settings->bPrintServerTime && (LastPrintTime < 0.0 || Now.ServerTimeSeconds - LastPrintTime >= PrintInterval))
	{
		Clock->PrintServerTime(Settings->bPrintServerTimeToScreen);
		LastPrintTime = Now.ServerTimeSeconds;
	}
	// This callback precedes actor/Mass ticks. Never spawn/query while an external Mass task is processing.
	if (Mass->GetEntityManagerChecked().IsProcessing()) return;
	constexpr double Step = 0.25;
	constexpr int32 MaxCatchUpSteps = 8;
	for (int32 Iteration = 0; Iteration < MaxCatchUpSteps; ++Iteration)
	{
		FEcoServerTimeSnapshot Previous;
		if (!Clock->GetSnapshotAt(ProcessedTime, Previous)) { Fail(TEXT("Provider must evaluate historical scheduler time.")); return; }
		double NextTime = FMath::Min(ProcessedTime + Step, Ecology->GetNextScheduledTime(Previous, bSpawnWaves));
		if (FeedingSettings.bEnabled)
		{
			double NextFeed;
			if (!EcoMassFeeding::FindNextTime(Mass->GetEntityManagerChecked(), ProcessedTime, NextFeed))
			{ Fail(TEXT("Invalid Mass feeding reservation.")); return; }
			NextTime = FMath::Min(NextTime, NextFeed);
		}
		if (NextTime > Now.ServerTimeSeconds) break;
		FEcoServerTimeSnapshot AtStep;
		if (!Clock->GetSnapshotAt(NextTime, AtStep)) { Fail(TEXT("Provider must evaluate historical scheduler time.")); return; }
		if (!ProcessEcologyStep(AtStep, Now.ServerTimeSeconds)) return;
		ProcessedTime = NextTime;
	}
}

bool UEcoMassLifecycleSubsystem::ProcessEcologyStep(const FEcoServerTimeSnapshot& Time, double ActualTime)
{
	UEcologySimulationSubsystem* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	FMassEntityManager& Manager = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	if (Manager.IsProcessing() || !ReconcilePopulation()) return Fail(TEXT("Invalid population membership at resource boundary."));
	if (!Ecology->BeginResourceStep(Time, ++StepId)) return Fail(TEXT("Resource step rejected (epoch/order/state)."));
	// Equal-time priority: environmental loss -> spawn -> feeding -> completed snapshot.
	if (bSpawnWaves)
	{
		for (const auto& Weak : Spawners)
		{
			AEcoMassNetworkBootstrap* Bootstrap = Weak.Get();
			if (!Bootstrap) return Fail(TEXT("A required Bootstrap was unloaded during the fixed-region scenario."));
			FEcoSpawnRequest Request;
			while (Ecology->PollSpawnWave(Bootstrap->GetConfiguredRegionId(), Time, Request))
			{
				const int32 Actual = Request.Count > 0 ? Bootstrap->ExecuteSpawnRequest(Request, ActualTime) : 0;
				const bool bMetricsValid = ReconcilePopulation();
				const bool bCompleted = Ecology->CompleteSpawnRequest(Request.RequestId, Actual);
				if (!bMetricsValid || !bCompleted || Actual != Request.Count) return Fail(TEXT("Wave spawn incomplete; request is terminal."));
				if (Request.Count == 0)
					UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Spawn Skipped] Region=%s Cycle=%lld Phase=%d Wave=%lld Due=%.3f (food/cap/zero count)"),
						*Request.RegionId.ToString(), Request.CycleId, static_cast<int32>(Request.Phase), Request.WaveIndex, Request.ScheduledTime);
			}
		}
	}
	TArray<FEcoFeedRequest> Requests;
	TArray<FEcoFeedResult> Results;
	if (!EcoMassFeeding::Collect(Manager, Time, StepId, FeedingSettings, Requests)) return Fail(TEXT("Invalid Mass feeding request."));
	if (!Ecology->ResolveFeeding(Requests, Results)) return Fail(TEXT("Feeding batch rejected; stopped without retry."));
	if (!EcoMassFeeding::Apply(Manager, Results, FeedingSettings.IntervalSeconds)) return Fail(TEXT("Feeding result no longer matches its entity."));
	if (!Ecology->CompleteResourceStep()) return Fail(TEXT("Resource conservation/snapshot failed."));
	ReportDailyPopulation(Time, ActualTime);
	return true;
}

void UEcoMassLifecycleSubsystem::ReportDailyPopulation(const FEcoServerTimeSnapshot& Time, double ActualTime)
{
	if (Time.DayCycle.Phase != EEcoDayPhase::Day || LastReportedCycle == Time.DayCycle.CycleId) return;
	LastReportedCycle = Time.DayCycle.CycleId;
	if (!bReportDaily) return;
	UEcologySimulationSubsystem* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	TArray<FName> RegionIds;
	Ecology->GetRegionIds(RegionIds);
	int32 Total = 0;
	for (FName RegionId : RegionIds)
	{
		FRegionEcologyState State;
		if (!Ecology->GetRegionState(RegionId, State)) continue;
		const int32* Previous = PreviousDawnPopulation.Find(RegionId);
		const int32 Delta = Previous ? State.Population - *Previous : 0;
		Total += State.Population;
		const FString Message = FString::Printf(TEXT("[Eco Daily][%s] Day=%lld Phase=Day Epoch=%d Step=%lld Due=%.3f Observed=%.3f Region=%s AliveEntities=%d Delta=%+d Food=%.3f/%.3f"),
			*GetWorld()->GetName(), Time.DayCycle.CycleId + 1, Time.WorldEpoch, StepId, Time.ServerTimeSeconds,
			ActualTime, *RegionId.ToString(), State.Population, Delta, State.FoodAmount, State.FoodCapacity);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("%s"), *Message);
		if (bReportDailyToScreen && GEngine && GetWorld()->GetNetMode() != NM_DedicatedServer)
			GEngine->AddOnScreenDebugMessage(static_cast<uint64>(HashCombine(GetUniqueID(), GetTypeHash(RegionId))), 8.0f, FColor::Green, Message);
		PreviousDawnPopulation.Add(RegionId, State.Population);
	}
	UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Daily Total] Day=%lld Epoch=%d Step=%lld AliveEntities=%d"),
		Time.DayCycle.CycleId + 1, Time.WorldEpoch, StepId, Total);
}

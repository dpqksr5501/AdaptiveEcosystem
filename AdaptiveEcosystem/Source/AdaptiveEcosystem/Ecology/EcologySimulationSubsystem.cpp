// Copyright Epic Games, Inc. All Rights Reserved.

#include "Ecology/EcologySimulationSubsystem.h"
#include "Engine/World.h"
#include "AdaptiveEcosystem.h"

UEcologySimulationSubsystem::UEcologySimulationSubsystem()
{
}

bool UEcologySimulationSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	if (!Super::ShouldCreateSubsystem(Outer))
	{
		return false;
	}

	const UWorld* World = Cast<UWorld>(Outer);
	if (!World)
	{
		return false;
	}

	// Editor preview worlds are not simulation authorities. PIE/Game worlds are.
	return World->IsGameWorld() && World->GetNetMode() != NM_Client;
}

void UEcologySimulationSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	RegionalStates.Reset();
	NextStableAgentId = 1;

	// Region authoring data is registered by the authority coordinator after all regions are ready.
}

void UEcologySimulationSubsystem::Deinitialize()
{
	RegionalStates.Reset();
	NextStableAgentId = 1;
	RegionIds.Reset();
	SpeciesIds.Reset();
	SpawnSettings.Reset();
	SpawnCursors.Reset();
	InitialRequests.Reset();
	PendingSpawns.Reset();
	NextSpawnRequestId = 1;
	ResourceEpoch = 0;
	ResourceStepId = 0;
	ResourceTime = -1.0;
	LastDayEventCycle = LastNightEventCycle = -1;
	bResourceStepOpen = false;
	bFeedingResolved = false;
	ResourceLedger.Reset();
	PendingManualStarvation.Reset();
	CompletedResources.Reset();
	LastAcceptedFeedTime.Reset();
	Super::Deinitialize();
}

bool UEcologySimulationSubsystem::IsAuthoritativeWorld() const
{
	const UWorld* World = GetWorld();
	return World && World->IsGameWorld() && World->GetNetMode() != NM_Client;
}

void UEcologySimulationSubsystem::TickSimulation(float DeltaTime)
{
	if (!FMath::IsFinite(DeltaTime) || DeltaTime <= 0.0f || !CanMutateAuthoritativeState(TEXT("TickSimulation")))
	{
		return;
	}

	for (auto& Pair : RegionalStates)
	{
		FRegionEcologyState& State = Pair.Value;

		State.FoodCapacity = FMath::Max(0.0f, State.FoodCapacity);
		State.FoodRegenerationRate = FMath::Max(0.0f, State.FoodRegenerationRate);
		State.FoodAmount = FMath::Clamp(
			State.FoodAmount + State.FoodRegenerationRate * DeltaTime,
			0.0f,
			State.FoodCapacity);

		// Exponential decay is stable for variable frame/step durations.
		if (State.PredationHistory > 0.0f)
		{
			const float DecayMultiplier = FMath::Exp(-FMath::Max(0.0f, PredationDecayRate) * DeltaTime);
			State.PredationHistory = FMath::Clamp(State.PredationHistory * DecayMultiplier, 0.0f, 1.0f);
			if (State.PredationHistory < UE_SMALL_NUMBER)
			{
				State.PredationHistory = 0.0f;
			}
		}
	}
}

bool UEcologySimulationSubsystem::RegisterRegionState(const FRegionEcologyState& InState)
{
	if (!CanMutateAuthoritativeState(TEXT("RegisterRegionState")) || InState.RegionId.IsNone()
		|| !FMath::IsFinite(InState.FoodAmount) || !FMath::IsFinite(InState.FoodCapacity)
		|| !FMath::IsFinite(InState.FoodRegenerationRate) || !FMath::IsFinite(InState.PredationHistory)
		|| !FMath::IsFinite(InState.AverageEnergy))
	{
		return false;
	}

	if (RegionalStates.Contains(InState.RegionId))
	{
		UE_LOG(LogAdaptiveEcosystem, Warning,
			TEXT("EcologySimulationSubsystem: Region '%s' is already registered; initial state was not replaced."),
			*InState.RegionId.ToString());
		return false;
	}

	RegionalStates.Add(InState.RegionId, MakeSanitizedRegionState(InState));
	RegionIds.Add(InState.RegionId);
	return true;
}

bool UEcologySimulationSubsystem::GetRegionState(FName RegionId, FRegionEcologyState& OutState) const
{
	if (!IsInGameThread())
	{
		ensureMsgf(false, TEXT("Ecology state must be queried on the game thread, outside Mass entity loops."));
		return false;
	}

	if (const FRegionEcologyState* Found = RegionalStates.Find(RegionId))
	{
		OutState = *Found;
		return true;
	}
	return false;
}

int64 UEcologySimulationSubsystem::AllocateStableAgentId()
{
	if (!CanMutateAuthoritativeState(TEXT("AllocateStableAgentId")))
	{
		return EcoIds::InvalidAgentId;
	}

	if (NextStableAgentId <= EcoIds::InvalidAgentId || NextStableAgentId == MAX_int64)
	{
		UE_LOG(LogAdaptiveEcosystem, Error, TEXT("EcologySimulationSubsystem: StableAgentId space is exhausted."));
		return EcoIds::InvalidAgentId;
	}

	return NextStableAgentId++;
}

float UEcologySimulationSubsystem::ApplyFoodConsumption(const FEcoFoodConsumptionRequest& Request)
{
	if (!CanMutateAuthoritativeState(TEXT("ApplyFoodConsumption"))
		|| Request.RegionId.IsNone()
		|| !FMath::IsFinite(Request.RequestedAmount)
		|| Request.RequestedAmount <= 0.0f)
	{
		return 0.0f;
	}

	if (FRegionEcologyState* Found = RegionalStates.Find(Request.RegionId))
	{
		Found->FoodAmount = FMath::Max(0.0f, Found->FoodAmount);
		const float Consumed = FMath::Min(Found->FoodAmount, Request.RequestedAmount);
		Found->FoodAmount = FMath::Max(0.0f, Found->FoodAmount - Consumed);
		return Consumed;
	}

	return 0.0f;
}

void UEcologySimulationSubsystem::ApplyPredationEvent(const FEcoPredationEvent& Event)
{
	if (!CanMutateAuthoritativeState(TEXT("ApplyPredationEvent")) || Event.RegionId.IsNone())
	{
		return;
	}

	if (FRegionEcologyState* Found = RegionalStates.Find(Event.RegionId))
	{
		Found->PredationHistory = FMath::Clamp(
			Found->PredationHistory + FMath::Max(0.0f, Event.ThreatMagnitude),
			0.0f,
			1.0f);
		OnRegionPredationRecorded.Broadcast(Event.RegionId, Found->PredationHistory);
	}
}

bool UEcologySimulationSubsystem::UpdatePopulationMetrics(const FEcoRegionPopulationSnapshot& Snapshot)
{
	if (!CanMutateAuthoritativeState(TEXT("UpdatePopulationMetrics")) || Snapshot.RegionId.IsNone())
	{
		return false;
	}

	if (FRegionEcologyState* Found = RegionalStates.Find(Snapshot.RegionId))
	{
		Found->Population = FMath::Max(0, Snapshot.Population);
		Found->TravelingCount = FMath::Clamp(Snapshot.TravelingCount, 0, Found->Population);
		Found->WaitingCount = FMath::Clamp(Snapshot.WaitingCount, 0, Found->Population - Found->TravelingCount);
		Found->AverageEnergy = FMath::Clamp(Snapshot.AverageEnergy, 0.0f, 1.0f);
		return true;
	}

	return false;
}

float UEcologySimulationSubsystem::ConsumeFood(FName RegionId, float RequestAmount)
{
	FEcoFoodConsumptionRequest Request;
	Request.RegionId = RegionId;
	Request.RequestedAmount = RequestAmount;
	return ApplyFoodConsumption(Request);
}

void UEcologySimulationSubsystem::RecordPredationEvent(FName RegionId, float ThreatMagnitude)
{
	FEcoPredationEvent Event;
	Event.RegionId = RegionId;
	Event.ThreatMagnitude = ThreatMagnitude;
	ApplyPredationEvent(Event);
}

float UEcologySimulationSubsystem::GetPredationHistory(FName RegionId) const
{
	if (const FRegionEcologyState* Found = RegionalStates.Find(RegionId))
	{
		return Found->PredationHistory;
	}
	return 0.0f;
}

bool UEcologySimulationSubsystem::CanMutateAuthoritativeState(const TCHAR* OperationName) const
{
	if (!IsInGameThread())
	{
		ensureMsgf(false,
			TEXT("%s must run during game-thread reconciliation, outside Mass entity loops."),
			OperationName);
		return false;
	}

	if (!IsAuthoritativeWorld())
	{
		UE_LOG(LogAdaptiveEcosystem, Warning,
			TEXT("EcologySimulationSubsystem: Rejected %s without Server/Standalone authority."),
			OperationName);
		return false;
	}

	return true;
}

FRegionEcologyState UEcologySimulationSubsystem::MakeSanitizedRegionState(const FRegionEcologyState& InState)
{
	FRegionEcologyState Result = InState;
	Result.FoodCapacity = FMath::Max(0.0f, Result.FoodCapacity);
	Result.FoodAmount = FMath::Clamp(Result.FoodAmount, 0.0f, Result.FoodCapacity);
	Result.FoodRegenerationRate = FMath::Max(0.0f, Result.FoodRegenerationRate);
	Result.PredationHistory = FMath::Clamp(Result.PredationHistory, 0.0f, 1.0f);
	Result.Population = FMath::Max(0, Result.Population);
	Result.AverageEnergy = FMath::Clamp(Result.AverageEnergy, 0.0f, 1.0f);
	return Result;
}

int32 UEcologySimulationSubsystem::GetRegionRuntimeIndex(FName RegionId) const
{
	return IsInGameThread() ? RegionIds.IndexOfByKey(RegionId) : INDEX_NONE;
}

int32 UEcologySimulationSubsystem::RegisterSpecies(FName SpeciesId)
{
	if (!CanMutateAuthoritativeState(TEXT("RegisterSpecies")) || SpeciesId.IsNone()) return INDEX_NONE;
	return SpeciesIds.AddUnique(SpeciesId);
}

bool UEcologySimulationSubsystem::ConfigurePopulationLimit(int32 Limit)
{
	if (!CanMutateAuthoritativeState(TEXT("ConfigurePopulationLimit")) || Limit <= 0 || !InitialRequests.IsEmpty()) return false;
	GlobalPopulationLimit = Limit;
	return true;
}

bool UEcologySimulationSubsystem::RegisterSpawnSchedule(FName RegionId, const FEcoSpawnScheduleSettings& Settings)
{
	if (!CanMutateAuthoritativeState(TEXT("RegisterSpawnSchedule")) || !RegionalStates.Contains(RegionId)
		|| !Settings.IsValid() || SpawnSettings.Contains(RegionId)) return false;
	SpawnSettings.Add(RegionId, Settings);
	SpawnCursors.Add(RegionId);
	return true;
}

bool UEcologySimulationSubsystem::ReserveSpawn(FName RegionId, FEcoSpawnRequest& Request)
{
	const FRegionEcologyState* State = RegionalStates.Find(RegionId);
	const FEcoSpawnScheduleSettings* Settings = SpawnSettings.Find(RegionId);
	if (!State || !Settings || NextSpawnRequestId == MAX_int64) return false;
	int32 GlobalAlive = 0;
	int32 RegionalReserved = 0;
	int32 GlobalReserved = 0;
	for (const auto& Pair : RegionalStates) GlobalAlive += Pair.Value.Population;
	for (const auto& Pair : PendingSpawns)
	{
		GlobalReserved += Pair.Value.Count;
		if (Pair.Value.RegionId == RegionId) RegionalReserved += Pair.Value.Count;
	}
	Request.RegionId = RegionId;
	Request.Count = EcoSpawn::AllowedCount(Request.Count, State->Population, GlobalAlive,
		RegionalReserved, GlobalReserved, Settings->RegionPopulationLimit, GlobalPopulationLimit, State->FoodAmount, Request.bInitial);
	Request.RequestId = NextSpawnRequestId++;
	PendingSpawns.Add(Request.RequestId, Request);
	return true;
}

bool UEcologySimulationSubsystem::RequestInitialSpawn(FName RegionId, int32 Count,
	const FEcoServerTimeSnapshot& Time, FEcoSpawnRequest& Out)
{
	if (!CanMutateAuthoritativeState(TEXT("RequestInitialSpawn")) || Count < 0 || Time.WorldEpoch <= 0
		|| !FMath::IsFinite(Time.ServerTimeSeconds) || Time.ServerTimeSeconds < 0 || InitialRequests.Contains(RegionId)) return false;
	Out = FEcoSpawnRequest();
	Out.WorldEpoch = Time.WorldEpoch;
	Out.bInitial = true;
	Out.Count = Count;
	Out.ScheduledTime = Time.ServerTimeSeconds;
	if (!ReserveSpawn(RegionId, Out)) return false;
	InitialRequests.Add(RegionId);
	return true;
}

bool UEcologySimulationSubsystem::PollSpawnWave(FName RegionId, const FEcoServerTimeSnapshot& Time, FEcoSpawnRequest& Out)
{
	if (!CanMutateAuthoritativeState(TEXT("PollSpawnWave")) || Time.WorldEpoch <= 0) return false;
	FEcoSpawnScheduleCursor* Cursor = SpawnCursors.Find(RegionId);
	const FEcoSpawnScheduleSettings* Settings = SpawnSettings.Find(RegionId);
	if (!Cursor || !Settings || !Cursor->ConsumeDueWave(Time, *Settings, Out)) return false;
	return ReserveSpawn(RegionId, Out);
}

bool UEcologySimulationSubsystem::CompleteSpawnRequest(int64 RequestId, int32 ActualCount)
{
	if (!CanMutateAuthoritativeState(TEXT("CompleteSpawnRequest"))) return false;
	const FEcoSpawnRequest* Request = PendingSpawns.Find(RequestId);
	if (!Request || ActualCount < 0 || ActualCount > Request->Count) return false;
	PendingSpawns.Remove(RequestId);
	return true;
}

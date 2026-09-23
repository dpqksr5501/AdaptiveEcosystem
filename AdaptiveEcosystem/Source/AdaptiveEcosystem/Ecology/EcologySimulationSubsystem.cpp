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

	// Initialize default Forest_A region state as vertical slice baseline
	FRegionEcologyState DefaultState;
	DefaultState.RegionId = FName(TEXT("Forest_A"));
	DefaultState.FoodAmount = 1500.0f;
	DefaultState.FoodCapacity = 2000.0f;
	DefaultState.FoodRegenerationRate = 20.0f;
	DefaultState.PredationHistory = 0.0f;
	// Population metrics begin empty and are supplied only by authoritative Mass aggregation.
	DefaultState.Population = 0;
	DefaultState.AverageEnergy = 0.0f;
	RegisterRegionState(DefaultState);
}

void UEcologySimulationSubsystem::Deinitialize()
{
	RegionalStates.Reset();
	NextStableAgentId = 1;
	Super::Deinitialize();
}

bool UEcologySimulationSubsystem::IsAuthoritativeWorld() const
{
	const UWorld* World = GetWorld();
	return World && World->IsGameWorld() && World->GetNetMode() != NM_Client;
}

void UEcologySimulationSubsystem::TickSimulation(float DeltaTime)
{
	if (DeltaTime <= 0.0f || !CanMutateAuthoritativeState(TEXT("TickSimulation")))
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
	if (!CanMutateAuthoritativeState(TEXT("RegisterRegionState")) || InState.RegionId.IsNone())
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

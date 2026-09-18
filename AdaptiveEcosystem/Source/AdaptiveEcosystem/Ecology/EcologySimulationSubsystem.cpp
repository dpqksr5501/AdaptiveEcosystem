// Copyright Epic Games, Inc. All Rights Reserved.

#include "Ecology/EcologySimulationSubsystem.h"
#include "Engine/World.h"

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

	// Active only on Server or Standalone worlds
	return World->GetNetMode() != NM_Client;
}

void UEcologySimulationSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	RegionalStates.Reset();

	// Initialize default Forest_A region state as vertical slice baseline
	FRegionEcologyState DefaultState;
	DefaultState.RegionId = FName(TEXT("Forest_A"));
	DefaultState.FoodAmount = 1500.0f;
	DefaultState.FoodCapacity = 2000.0f;
	DefaultState.FoodRegenerationRate = 20.0f;
	DefaultState.PredationHistory = 0.0f;
	DefaultState.Population = 100;
	DefaultState.AverageEnergy = 1.0f;
	RegionalStates.Add(DefaultState.RegionId, DefaultState);
}

void UEcologySimulationSubsystem::Deinitialize()
{
	RegionalStates.Reset();
	Super::Deinitialize();
}

void UEcologySimulationSubsystem::TickSimulation(float DeltaTime)
{
	if (DeltaTime <= 0.0f)
	{
		return;
	}

	for (auto& Pair : RegionalStates)
	{
		FRegionEcologyState& State = Pair.Value;

		// 1. Food Regeneration: regrow up to FoodCapacity
		if (State.FoodAmount < State.FoodCapacity)
		{
			State.FoodAmount = FMath::Min(State.FoodCapacity, State.FoodAmount + State.FoodRegenerationRate * DeltaTime);
		}

		// 2. Predation History Decay: exponentially decay towards 0.0
		if (State.PredationHistory > 0.0f)
		{
			State.PredationHistory = FMath::Max(0.0f, State.PredationHistory - PredationDecayRate * DeltaTime);
		}
	}
}

void UEcologySimulationSubsystem::RegisterRegionState(const FRegionEcologyState& InState)
{
	RegionalStates.FindOrAdd(InState.RegionId) = InState;
}

bool UEcologySimulationSubsystem::GetRegionState(FName RegionId, FRegionEcologyState& OutState) const
{
	if (const FRegionEcologyState* Found = RegionalStates.Find(RegionId))
	{
		OutState = *Found;
		return true;
	}
	return false;
}

void UEcologySimulationSubsystem::SetRegionState(const FRegionEcologyState& InState)
{
	RegionalStates.FindOrAdd(InState.RegionId) = InState;
}

float UEcologySimulationSubsystem::ConsumeFood(FName RegionId, float RequestAmount)
{
	if (RequestAmount <= 0.0f)
	{
		return 0.0f;
	}

	if (FRegionEcologyState* Found = RegionalStates.Find(RegionId))
	{
		const float Consumed = FMath::Min(Found->FoodAmount, RequestAmount);
		Found->FoodAmount = FMath::Max(0.0f, Found->FoodAmount - Consumed);
		return Consumed;
	}

	return 0.0f;
}

void UEcologySimulationSubsystem::RecordPredationEvent(FName RegionId, float ThreatMagnitude)
{
	if (FRegionEcologyState* Found = RegionalStates.Find(RegionId))
	{
		Found->PredationHistory = FMath::Clamp(Found->PredationHistory + ThreatMagnitude, 0.0f, 1.0f);
		OnRegionPredationRecorded.Broadcast(RegionId, Found->PredationHistory);
	}
}

float UEcologySimulationSubsystem::GetPredationHistory(FName RegionId) const
{
	if (const FRegionEcologyState* Found = RegionalStates.Find(RegionId))
	{
		return Found->PredationHistory;
	}
	return 0.0f;
}

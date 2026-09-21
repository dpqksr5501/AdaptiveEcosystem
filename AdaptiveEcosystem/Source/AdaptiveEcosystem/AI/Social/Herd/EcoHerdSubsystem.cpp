// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "Engine/World.h"

UEcoHerdSubsystem::UEcoHerdSubsystem()
{
}

bool UEcoHerdSubsystem::ShouldCreateSubsystem(UObject* Outer) const
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

void UEcoHerdSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	ActiveHerds.Reset();
	HerdSpeciesIndices.Reset();
	FreeSlots.Reset();
	NextPersistentHerdId = 1;
}

void UEcoHerdSubsystem::Deinitialize()
{
	ActiveHerds.Reset();
	HerdSpeciesIndices.Reset();
	FreeSlots.Reset();
	Super::Deinitialize();
}

int32 UEcoHerdSubsystem::AllocateHerd(int32 SpeciesRuntimeIndex, const FVector& InitialCenter)
{
	int32 SlotIndex = INDEX_NONE_ECO;
	if (FreeSlots.Num() > 0)
	{
		SlotIndex = FreeSlots.Pop(EAllowShrinking::No);
	}
	else
	{
		SlotIndex = ActiveHerds.AddDefaulted();
		HerdSpeciesIndices.AddDefaulted();
	}

	FEcoHerdRuntimeData& NewHerd = ActiveHerds[SlotIndex];
	NewHerd.RuntimeIndex = SlotIndex;
	NewHerd.PersistentHerdId = NextPersistentHerdId++;
	NewHerd.Center = InitialCenter;
	NewHerd.AverageVelocity = FVector::ZeroVector;
	NewHerd.MemberCount = 1;
	NewHerd.Representative.Reset();
	NewHerd.AlarmStrength = 0.0f;
	NewHerd.LastThreatPosition = FVector::ZeroVector;
	NewHerd.LastAggregateTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	NewHerd.LastTopologyUpdateTime = NewHerd.LastAggregateTime;

	HerdSpeciesIndices[SlotIndex] = SpeciesRuntimeIndex;

	return SlotIndex;
}

void UEcoHerdSubsystem::ReleaseHerd(int32 RuntimeIndex)
{
	if (ActiveHerds.IsValidIndex(RuntimeIndex) && ActiveHerds[RuntimeIndex].PersistentHerdId != 0)
	{
		ActiveHerds[RuntimeIndex].PersistentHerdId = 0;
		ActiveHerds[RuntimeIndex].MemberCount = 0;
		ActiveHerds[RuntimeIndex].Representative.Reset();
		HerdSpeciesIndices[RuntimeIndex] = INDEX_NONE_ECO;
		FreeSlots.Add(RuntimeIndex);
	}
}

bool UEcoHerdSubsystem::IsValidHerdIndex(int32 RuntimeIndex) const
{
	return ActiveHerds.IsValidIndex(RuntimeIndex) && ActiveHerds[RuntimeIndex].PersistentHerdId != 0;
}

bool UEcoHerdSubsystem::GetHerdData(int32 RuntimeIndex, FEcoHerdRuntimeData& OutData) const
{
	if (IsValidHerdIndex(RuntimeIndex))
	{
		OutData = ActiveHerds[RuntimeIndex];
		return true;
	}
	return false;
}

int32 UEcoHerdSubsystem::GetHerdSpeciesIndex(int32 RuntimeIndex) const
{
	if (HerdSpeciesIndices.IsValidIndex(RuntimeIndex))
	{
		return HerdSpeciesIndices[RuntimeIndex];
	}
	return INDEX_NONE_ECO;
}

void UEcoHerdSubsystem::UpdateHerdAggregate(int32 RuntimeIndex, const FVector& Center, const FVector& AvgVelocity, int32 MemberCount, FMassEntityHandle Representative)
{
	if (IsValidHerdIndex(RuntimeIndex))
	{
		FEcoHerdRuntimeData& Herd = ActiveHerds[RuntimeIndex];
		Herd.Center = Center;
		Herd.AverageVelocity = AvgVelocity;
		Herd.MemberCount = MemberCount;
		Herd.Representative = Representative;
		Herd.LastAggregateTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	}
}

int32 UEcoHerdSubsystem::FindNearestHerd(int32 SpeciesRuntimeIndex, const FVector& Location, float MaxRadius) const
{
	int32 BestIndex = INDEX_NONE_ECO;
	float BestDistSq = MaxRadius * MaxRadius;

	for (int32 i = 0; i < ActiveHerds.Num(); ++i)
	{
		if (!IsValidHerdIndex(i))
		{
			continue;
		}

		if (HerdSpeciesIndices[i] != SpeciesRuntimeIndex)
		{
			continue;
		}

		const float DistSq = FVector::DistSquared(Location, ActiveHerds[i].Center);
		if (DistSq < BestDistSq)
		{
			BestDistSq = DistSq;
			BestIndex = i;
		}
	}

	return BestIndex;
}

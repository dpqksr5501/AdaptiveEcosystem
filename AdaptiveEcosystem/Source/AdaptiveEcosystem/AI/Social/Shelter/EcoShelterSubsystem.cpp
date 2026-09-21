// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Engine/World.h"

UEcoShelterSubsystem::UEcoShelterSubsystem()
{
}

bool UEcoShelterSubsystem::ShouldCreateSubsystem(UObject* Outer) const
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

void UEcoShelterSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	Shelters.Reset();
	ShelterSlots.Reset();
	FreeShelterIndices.Reset();
}

void UEcoShelterSubsystem::Deinitialize()
{
	Shelters.Reset();
	ShelterSlots.Reset();
	FreeShelterIndices.Reset();
	Super::Deinitialize();
}

int32 UEcoShelterSubsystem::RegisterShelter(const FVector& Location, const FVector& Normal, float Quality, int32 Capacity)
{
	int32 ShelterIndex = INDEX_NONE_ECO;
	if (FreeShelterIndices.Num() > 0)
	{
		ShelterIndex = FreeShelterIndices.Pop(EAllowShrinking::No);
	}
	else
	{
		ShelterIndex = Shelters.AddDefaulted();
	}

	FEcoShelterPoint& NewShelter = Shelters[ShelterIndex];
	NewShelter.RuntimeIndex = ShelterIndex;
	NewShelter.Position = Location;
	NewShelter.SurfaceNormal = Normal.GetSafeNormal();
	NewShelter.Quality = FMath::Clamp(Quality, 0.0f, 1.0f);
	NewShelter.Capacity = FMath::Max(1, Capacity);

	// Allocate discrete reservation slots clustered around shelter position
	for (int32 SlotIdx = 0; SlotIdx < NewShelter.Capacity; ++SlotIdx)
	{
		const int32 NewSlotIndex = ShelterSlots.AddDefaulted();
		FEcoShelterSlot& Slot = ShelterSlots[NewSlotIndex];
		Slot.ShelterRuntimeIndex = ShelterIndex;
		Slot.SlotIndex = NewSlotIndex;
		const float Angle = static_cast<float>(SlotIdx);
		Slot.Position = Location + FVector(FMath::Cos(Angle) * 100.0f, FMath::Sin(Angle) * 100.0f, 0.0f);
		Slot.ReservedBy = 0;
		Slot.ReservationExpireTime = 0.0;
	}

	return ShelterIndex;
}

void UEcoShelterSubsystem::UnregisterShelter(int32 ShelterIndex)
{
	if (IsValidShelterIndex(ShelterIndex))
	{
		Shelters[ShelterIndex].RuntimeIndex = INDEX_NONE_ECO;

		// Invalidate all associated reservation slots
		for (FEcoShelterSlot& Slot : ShelterSlots)
		{
			if (Slot.ShelterRuntimeIndex == ShelterIndex)
			{
				Slot.ShelterRuntimeIndex = INDEX_NONE_ECO;
				Slot.ReservedBy = 0;
				Slot.ReservationExpireTime = 0.0;
			}
		}

		FreeShelterIndices.Add(ShelterIndex);
	}
}

bool UEcoShelterSubsystem::IsValidShelterIndex(int32 ShelterIndex) const
{
	return Shelters.IsValidIndex(ShelterIndex) && Shelters[ShelterIndex].RuntimeIndex != INDEX_NONE_ECO;
}

bool UEcoShelterSubsystem::ReserveSlot(int32 SlotIndex, int64 StableAgentId, double ExpireTime)
{
	if (!ShelterSlots.IsValidIndex(SlotIndex))
	{
		return false;
	}

	const double CurrentTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	FEcoShelterSlot& Slot = ShelterSlots[SlotIndex];

	// Slot must be unreserved or previously expired
	if (Slot.ReservedBy == 0 || Slot.ReservationExpireTime <= CurrentTime || Slot.ReservedBy == StableAgentId)
	{
		Slot.ReservedBy = StableAgentId;
		Slot.ReservationExpireTime = ExpireTime;
		return true;
	}

	return false;
}

void UEcoShelterSubsystem::ReleaseSlot(int32 SlotIndex, int64 StableAgentId)
{
	if (ShelterSlots.IsValidIndex(SlotIndex))
	{
		FEcoShelterSlot& Slot = ShelterSlots[SlotIndex];
		if (Slot.ReservedBy == StableAgentId)
		{
			Slot.ReservedBy = 0;
			Slot.ReservationExpireTime = 0.0;
		}
	}
}

void UEcoShelterSubsystem::ReleaseAgentReservations(int64 StableAgentId)
{
	if (StableAgentId == 0)
	{
		return;
	}

	for (FEcoShelterSlot& Slot : ShelterSlots)
	{
		if (Slot.ReservedBy == StableAgentId)
		{
			Slot.ReservedBy = 0;
			Slot.ReservationExpireTime = 0.0;
		}
	}
}

int32 UEcoShelterSubsystem::FindBestAvailableShelter(const FVector& AgentLocation, const FVector& ThreatLocation, float SearchRadius, int32& OutSlotIndex) const
{
	OutSlotIndex = INDEX_NONE_ECO;
	int32 BestShelterIndex = INDEX_NONE_ECO;
	float BestScore = -1.0f;

	const double CurrentTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	const float SearchRadiusSq = SearchRadius * SearchRadius;

	for (int32 i = 0; i < Shelters.Num(); ++i)
	{
		if (!IsValidShelterIndex(i))
		{
			continue;
		}

		const FEcoShelterPoint& Shelter = Shelters[i];
		const float DistSq = FVector::DistSquared(AgentLocation, Shelter.Position);
		if (DistSq > SearchRadiusSq)
		{
			continue;
		}

		// Look for first unreserved or expired slot belonging to this shelter
		int32 FoundAvailableSlot = INDEX_NONE_ECO;
		for (int32 SlotIdx = 0; SlotIdx < ShelterSlots.Num(); ++SlotIdx)
		{
			const FEcoShelterSlot& Slot = ShelterSlots[SlotIdx];
			if (Slot.ShelterRuntimeIndex == i && (Slot.ReservedBy == 0 || Slot.ReservationExpireTime <= CurrentTime))
			{
				FoundAvailableSlot = SlotIdx;
				break;
			}
		}

		if (FoundAvailableSlot == INDEX_NONE_ECO)
		{
			continue; // Shelter fully booked
		}

		// Calculate composite defensive score:
		// 1. Proximity score (0.0 .. 1.0)
		const float DistRatio = 1.0f - FMath::Sqrt(DistSq) / FMath::Max(1.0f, SearchRadius);

		// 2. Defensive orientation score relative to threat position
		float OcclusionScore = 0.5f;
		if (!ThreatLocation.IsZero())
		{
			const FVector DirToThreat = (ThreatLocation - Shelter.Position).GetSafeNormal();
			// Shelter normal facing away from threat offers higher shielding
			OcclusionScore = FMath::Clamp(FVector::DotProduct(Shelter.SurfaceNormal, -DirToThreat) * 0.5f + 0.5f, 0.0f, 1.0f);
		}

		// Composite score
		const float Score = Shelter.Quality * 0.4f + DistRatio * 0.35f + OcclusionScore * 0.25f;
		if (Score > BestScore)
		{
			BestScore = Score;
			BestShelterIndex = i;
			OutSlotIndex = FoundAvailableSlot;
		}
	}

	return BestShelterIndex;
}

void UEcoShelterSubsystem::CleanExpiredReservations(double CurrentTime)
{
	for (FEcoShelterSlot& Slot : ShelterSlots)
	{
		if (Slot.ReservedBy != 0 && Slot.ReservationExpireTime <= CurrentTime)
		{
			Slot.ReservedBy = 0;
			Slot.ReservationExpireTime = 0.0;
		}
	}
}

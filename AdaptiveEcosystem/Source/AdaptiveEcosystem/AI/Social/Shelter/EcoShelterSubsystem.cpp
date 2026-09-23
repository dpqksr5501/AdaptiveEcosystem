// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"

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

int32 UEcoShelterSubsystem::RegisterShelter(const FVector& Location, const FVector& Normal, float Quality, int32 Capacity, float Radius)
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

	const float SafeRadius = FMath::Max(50.0f, Radius);

	// Allocate discrete reservation slots distributed evenly in a circle around shelter center
	for (int32 SlotIdx = 0; SlotIdx < NewShelter.Capacity; ++SlotIdx)
	{
		const int32 NewSlotIndex = ShelterSlots.AddDefaulted();
		FEcoShelterSlot& Slot = ShelterSlots[NewSlotIndex];
		Slot.ShelterRuntimeIndex = ShelterIndex;
		Slot.SlotIndex = NewSlotIndex;
		
		// Angle = 2 * PI * SlotIdx / Capacity
		const float Angle = (float)SlotIdx / (float)NewShelter.Capacity * 2.0f * PI;
		Slot.Position = Location + FVector(FMath::Cos(Angle) * SafeRadius, FMath::Sin(Angle) * SafeRadius, 0.0f);
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

bool UEcoShelterSubsystem::CheckThreatOcclusion(const FVector& ThreatLocation, const FVector& TargetLocation) const
{
	const UWorld* World = GetWorld();
	if (!World || ThreatLocation.IsZero())
	{
		return false;
	}

	// Trace from eye-level of threat to shelter position
	const FVector Start = ThreatLocation + FVector(0.0f, 0.0f, 60.0f);
	const FVector End = TargetLocation + FVector(0.0f, 0.0f, 40.0f);

	FHitResult HitResult;

	// 1. Complex geometry trace with ECC_Visibility (detects Modeling Mode meshes, procedural walls, and static meshes)
	FCollisionQueryParams ComplexParams(SCENE_QUERY_STAT(EcoShelterOcclusionComplex), true);
	ComplexParams.bFindInitialOverlaps = true;

	bool bHit = World->LineTraceSingleByChannel(HitResult, Start, End, ECC_Visibility, ComplexParams);

	// 2. Camera channel fallback (often blocked by meshes that ignore visibility)
	if (!bHit)
	{
		bHit = World->LineTraceSingleByChannel(HitResult, Start, End, ECC_Camera, ComplexParams);
	}

	// 3. Object Type query (WorldStatic, WorldDynamic, PhysicsBody) with complex collision
	if (!bHit)
	{
		FCollisionObjectQueryParams ObjectParams;
		ObjectParams.AddObjectTypesToQuery(ECC_WorldStatic);
		ObjectParams.AddObjectTypesToQuery(ECC_WorldDynamic);
		ObjectParams.AddObjectTypesToQuery(ECC_PhysicsBody);
		bHit = World->LineTraceSingleByObjectType(HitResult, Start, End, ObjectParams, ComplexParams);
	}

	// 4. Simple collision fallback
	if (!bHit)
	{
		FCollisionQueryParams SimpleParams(SCENE_QUERY_STAT(EcoShelterOcclusionSimple), false);
		bHit = World->LineTraceSingleByChannel(HitResult, Start, End, ECC_Visibility, SimpleParams);
		if (!bHit)
		{
			FCollisionObjectQueryParams ObjectParams;
			ObjectParams.AddObjectTypesToQuery(ECC_WorldStatic);
			ObjectParams.AddObjectTypesToQuery(ECC_WorldDynamic);
			bHit = World->LineTraceSingleByObjectType(HitResult, Start, End, ObjectParams, SimpleParams);
		}
	}

	return bHit; // Blocked by level geometry = Defensively Occluded!
}

int32 UEcoShelterSubsystem::FindBestAvailableShelter(const FVector& AgentLocation, const FVector& ThreatLocation, float SearchRadius, int32& OutSlotIndex, float& OutScore) const
{
	OutSlotIndex = INDEX_NONE_ECO;
	OutScore = 0.0f;
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
		const float DistRatio = 1.0f - FMath::Clamp(FMath::Sqrt(DistSq) / FMath::Max(1.0f, SearchRadius), 0.0f, 1.0f);

		// 2. Real World Geometry LOS / Occlusion score
		float OcclusionScore = 0.5f;
		if (!ThreatLocation.IsZero())
		{
			const bool bBlocked = CheckThreatOcclusion(ThreatLocation, Shelter.Position);
			// Completely occluded by geometry gives 1.0, otherwise baseline 0.1
			OcclusionScore = bBlocked ? 1.0f : 0.1f;

			// Add normal orientation bonus (0.0 .. 0.15) if facing away from threat
			const FVector DirToThreat = (ThreatLocation - Shelter.Position).GetSafeNormal();
			const float NormalDot = FVector::DotProduct(Shelter.SurfaceNormal, -DirToThreat);
			if (NormalDot > 0.0f)
			{
				OcclusionScore = FMath::Clamp(OcclusionScore + NormalDot * 0.15f, 0.0f, 1.0f);
			}
		}

		// Composite score: Quality (25%), Distance (35%), Occlusion (40%)
		const float Score = Shelter.Quality * 0.25f + DistRatio * 0.35f + OcclusionScore * 0.40f;
		if (Score > BestScore)
		{
			BestScore = Score;
			BestShelterIndex = i;
			OutSlotIndex = FoundAvailableSlot;
			OutScore = Score;
		}
	}

	return BestShelterIndex;
}

bool UEcoShelterSubsystem::GetSlotData(int32 SlotIndex, FEcoShelterSlot& OutSlot) const
{
	if (ShelterSlots.IsValidIndex(SlotIndex))
	{
		OutSlot = ShelterSlots[SlotIndex];
		return true;
	}
	return false;
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

void UEcoShelterSubsystem::ResetAllReservations()
{
	for (FEcoShelterSlot& Slot : ShelterSlots)
	{
		Slot.ReservedBy = 0;
		Slot.ReservationExpireTime = 0.0;
	}
}


// Copyright Epic Games, Inc. All Rights Reserved.

#include "Debug/EcoShelterTestHarnessActor.h"
#include "Debug/EcoAlarmTestHarnessActor.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/EcoSocialTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntityUtils.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "DrawDebugHelpers.h"

AEcoShelterTestHarnessActor::AEcoShelterTestHarnessActor()
{
	PrimaryActorTick.bCanEverTick = true;
}

void AEcoShelterTestHarnessActor::EnsureQueriesInitialized(FMassEntityManager& EntityManager)
{
	if (bQueriesInitialized)
	{
		return;
	}

	DebugQuery.Initialize(EntityManager.AsShared());
	DebugQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddRequirement<FEcoShelterIntentFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);

	ResetQuery.Initialize(EntityManager.AsShared());
	ResetQuery.AddRequirement<FEcoShelterIntentFragment>(EMassFragmentAccess::ReadWrite);
	ResetQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);

	bQueriesInitialized = true;
}

FVector AEcoShelterTestHarnessActor::ResolveActiveThreatLocation() const
{
	if (!ThreatLocationOverride.IsZero())
	{
		return ThreatLocationOverride;
	}

	const UWorld* World = GetWorld();
	if (!World)
	{
		return FVector::ZeroVector;
	}

	const UEcoHerdSubsystem* HerdSub = World->GetSubsystem<UEcoHerdSubsystem>();
	if (HerdSub)
	{
		// 1. Check specified target herd
		FEcoHerdRuntimeData TargetHerdData;
		if (HerdSub->GetHerdData(ThreatHerdIndex, TargetHerdData))
		{
			if (TargetHerdData.AlarmStrength > 0.05f && !TargetHerdData.LastThreatPosition.IsZero())
			{
				return TargetHerdData.LastThreatPosition;
			}
		}

		// 2. Check any herd with active alarm
		const TArray<FEcoHerdRuntimeData>& AllHerds = HerdSub->GetActiveHerds();
		for (const FEcoHerdRuntimeData& Herd : AllHerds)
		{
			if (Herd.AlarmStrength > 0.05f && !Herd.LastThreatPosition.IsZero())
			{
				return Herd.LastThreatPosition;
			}
		}
	}

	// 3. Check for active AlarmTestHarness in the world
	for (TActorIterator<AEcoAlarmTestHarnessActor> It(GetWorld()); It; ++It)
	{
		if (It->bContinuousThreat || (World->GetTimeSeconds() - 0.0 < 5.0))
		{
			return It->GetActorLocation();
		}
	}

	return FVector::ZeroVector;
}

void AEcoShelterTestHarnessActor::ResetAllReservations()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	UEcoShelterSubsystem* ShelterSub = World->GetSubsystem<UEcoShelterSubsystem>();
	if (ShelterSub)
	{
		ShelterSub->ResetAllReservations();
	}

	FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(*World);
	EnsureQueriesInitialized(EntityManager);

	FMassExecutionContext Context(EntityManager);
	ResetQuery.ForEachEntityChunk(Context, [](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetMutableFragmentView<FEcoShelterIntentFragment>();
		for (int32 i = 0; i < NumEntities; ++i)
		{
			IntentList[i].Reset();
		}
	});

	UE_LOG(LogTemp, Log, TEXT("[AEcoShelterTestHarnessActor] Reset all shelter slot reservations and cleared agent intents."));
}

void AEcoShelterTestHarnessActor::PrintShelterOccupancyStatus()
{
	const UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	const UEcoShelterSubsystem* ShelterSub = World->GetSubsystem<UEcoShelterSubsystem>();
	if (!ShelterSub)
	{
		UE_LOG(LogTemp, Warning, TEXT("[AEcoShelterTestHarnessActor] UEcoShelterSubsystem not found!"));
		return;
	}

	const TArray<FEcoShelterPoint>& Shelters = ShelterSub->GetShelters();
	const TArray<FEcoShelterSlot>& Slots = ShelterSub->GetShelterSlots();
	const double CurrentTime = World->GetTimeSeconds();

	UE_LOG(LogTemp, Log, TEXT("========== [Shelter Subsystem Occupancy Status (Time: %.1f)] =========="), CurrentTime);
	for (int32 i = 0; i < Shelters.Num(); ++i)
	{
		if (!ShelterSub->IsValidShelterIndex(i))
		{
			continue;
		}

		const FEcoShelterPoint& Shelter = Shelters[i];
		int32 ReservedCount = 0;
		TArray<FString> SlotDetails;

		for (int32 s = 0; s < Slots.Num(); ++s)
		{
			const FEcoShelterSlot& Slot = Slots[s];
			if (Slot.ShelterRuntimeIndex == i)
			{
				const bool bReserved = (Slot.ReservedBy != 0 && Slot.ReservationExpireTime > CurrentTime);
				if (bReserved)
				{
					++ReservedCount;
					SlotDetails.Add(FString::Printf(TEXT("Slot #%d: Agent %lld (Expires in %.1fs)"),
						s, Slot.ReservedBy, Slot.ReservationExpireTime - CurrentTime));
				}
				else
				{
					SlotDetails.Add(FString::Printf(TEXT("Slot #%d: [Open]"), s));
				}
			}
		}

		UE_LOG(LogTemp, Log, TEXT("Shelter #%d at %s | Quality: %.2f | Capacity: %d | Occupancy: %d/%d"),
			i, *Shelter.Position.ToString(), Shelter.Quality, Shelter.Capacity, ReservedCount, Shelter.Capacity);

		for (const FString& Detail : SlotDetails)
		{
			UE_LOG(LogTemp, Log, TEXT("    %s"), *Detail);
		}
	}
	UE_LOG(LogTemp, Log, TEXT("========================================================================"));
}

void AEcoShelterTestHarnessActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UWorld* World = GetWorld();
	if (!World || World->GetNetMode() == NM_Client)
	{
		return;
	}

	const UEcoShelterSubsystem* ShelterSub = World->GetSubsystem<UEcoShelterSubsystem>();
	if (!ShelterSub)
	{
		return;
	}

	const TArray<FEcoShelterPoint>& Shelters = ShelterSub->GetShelters();
	const TArray<FEcoShelterSlot>& Slots = ShelterSub->GetShelterSlots();
	const double CurrentTime = World->GetTimeSeconds();
	const FVector ThreatLocation = ResolveActiveThreatLocation();

	// 1. Draw Shelter Anchors & Capacity HUD
	if (bDrawShelters)
	{
		for (int32 i = 0; i < Shelters.Num(); ++i)
		{
			if (!ShelterSub->IsValidShelterIndex(i))
			{
				continue;
			}

			const FEcoShelterPoint& Shelter = Shelters[i];

			// Count occupied slots
			int32 ReservedCount = 0;
			int32 TotalSlots = 0;
			for (const FEcoShelterSlot& Slot : Slots)
			{
				if (Slot.ShelterRuntimeIndex == i)
				{
					++TotalSlots;
					if (Slot.ReservedBy != 0 && Slot.ReservationExpireTime > CurrentTime)
					{
						++ReservedCount;
					}
				}
			}

			FColor ShelterColor = FColor::Green;
			if (ReservedCount == TotalSlots && TotalSlots > 0)
			{
				ShelterColor = FColor::Red; // Fully occupied
			}
			else if (ReservedCount > 0)
			{
				ShelterColor = FColor(255, 165, 0); // Partially occupied
			}

			// Draw boundary circle at ground level
			DrawDebugCircle(World, Shelter.Position, 180.0f, 32, ShelterColor, false, -1.0f, 0, 2.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
			DrawDebugSphere(World, Shelter.Position, 40.0f, 12, ShelterColor, false, -1.0f, 0, 1.5f);

			// Draw surface normal arrow
			if (!Shelter.SurfaceNormal.IsNearlyZero())
			{
				DrawDebugDirectionalArrow(World, Shelter.Position, Shelter.Position + Shelter.SurfaceNormal * 120.0f, 30.0f, FColor::Blue, false, -1.0f, 0, 2.0f);
			}

			// HUD text
			const FString ShelterLabel = FString::Printf(TEXT("[Shelter #%d]\nOcc: %d/%d\nQual: %.2f"),
				i, ReservedCount, TotalSlots, Shelter.Quality);
			DrawDebugString(World, Shelter.Position + FVector(0, 0, 80.0f), ShelterLabel, nullptr, ShelterColor, 0.0f, true, 1.1f);
		}
	}

	// 2. Draw Individual Slots
	if (bDrawSlots)
	{
		for (int32 s = 0; s < Slots.Num(); ++s)
		{
			const FEcoShelterSlot& Slot = Slots[s];
			if (Slot.ShelterRuntimeIndex == INDEX_NONE_ECO)
			{
				continue;
			}

			const bool bReserved = (Slot.ReservedBy != 0 && Slot.ReservationExpireTime > CurrentTime);
			const FColor SlotColor = bReserved ? FColor::Orange : FColor::Cyan;
			const float SlotRadius = bReserved ? 24.0f : 16.0f;

			DrawDebugSphere(World, Slot.Position, SlotRadius, 8, SlotColor, false, -1.0f, 0, 1.5f);

			if (bReserved)
			{
				const FString SlotLabel = FString::Printf(TEXT("Slot #%d\nAgent: %lld"), s, Slot.ReservedBy);
				DrawDebugString(World, Slot.Position + FVector(0, 0, 30.0f), SlotLabel, nullptr, FColor::Orange, 0.0f, true, 0.85f);
			}
			else
			{
				DrawDebugString(World, Slot.Position + FVector(0, 0, 25.0f), FString::Printf(TEXT("Slot #%d [Open]"), s), nullptr, FColor(100, 255, 255), 0.0f, true, 0.75f);
			}
		}
	}

	// 3. Draw Threat-relative Occlusion Raycasts
	if (bDrawOcclusionRaycasts && !ThreatLocation.IsZero())
	{
		const FVector RayStart = ThreatLocation + FVector(0, 0, 60.0f);

		for (int32 i = 0; i < Shelters.Num(); ++i)
		{
			if (!ShelterSub->IsValidShelterIndex(i))
			{
				continue;
			}

			const FEcoShelterPoint& Shelter = Shelters[i];
			const FVector RayEnd = Shelter.Position + FVector(0, 0, 40.0f);

			const bool bOccluded = ShelterSub->CheckThreatOcclusion(ThreatLocation, Shelter.Position);

			if (bOccluded)
			{
				// Line blocked by WorldStatic geometry: Defensively occluded (Safe)
				DrawDebugLine(World, RayStart, RayEnd, FColor::Green, false, -1.0f, 0, 2.5f);
				DrawDebugString(World, (RayStart + RayEnd) * 0.5f + FVector(0, 0, 30.0f),
					TEXT("[OCCLUDED - SAFE]"), nullptr, FColor::Green, 0.0f, true, 1.0f);
			}
			else
			{
				// Line clear: Visually exposed (Dangerous)
				DrawDebugLine(World, RayStart, RayEnd, FColor::Red, false, -1.0f, 0, 2.0f);
				DrawDebugString(World, (RayStart + RayEnd) * 0.5f + FVector(0, 0, 30.0f),
					TEXT("[EXPOSED - DANGER]"), nullptr, FColor::Red, 0.0f, true, 1.0f);
			}
		}
	}

	// 4. Draw Agent Intent Lines & HUD
	if (bDrawAgentIntentLines)
	{
		FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(*World);
		EnsureQueriesInitialized(EntityManager);

		FMassExecutionContext Context(EntityManager, DeltaSeconds);
		int32 DisplayBudget = MaxAgentHudCount;

		DebugQuery.ForEachEntityChunk(Context, [World, &DisplayBudget](FMassExecutionContext& ChunkContext)
		{
			const int32 NumEntities = ChunkContext.GetNumEntities();
			TConstArrayView<FEcoIdentityFragment> IdentityList = ChunkContext.GetFragmentView<FEcoIdentityFragment>();
			TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
			TConstArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetFragmentView<FEcoShelterIntentFragment>();
			TConstArrayView<FEcoSocialBehaviorFragment> SocialList = ChunkContext.GetFragmentView<FEcoSocialBehaviorFragment>();

			for (int32 i = 0; i < NumEntities; ++i)
			{
				const FEcoShelterIntentFragment& Intent = IntentList[i];
				if (Intent.State == EEcoShelterIntentState::None)
				{
					continue;
				}

				const FVector AgentPos = TransformList[i].GetTransform().GetLocation();
				const int64 AgentId = IdentityList[i].StableAgentId;
				const float EffectiveCover = SocialList[i].ModulatedAction.Cover;

				if (Intent.State == EEcoShelterIntentState::Reserved)
				{
					// Draw line to reserved slot target position
					DrawDebugLine(World, AgentPos + FVector(0, 0, 30.0f), Intent.TargetPosition + FVector(0, 0, 30.0f),
						FColor::Cyan, false, -1.0f, 0, 2.0f);

					if (DisplayBudget > 0)
					{
						--DisplayBudget;
						const FString IntentText = FString::Printf(
							TEXT("[RESERVED]\nAgent %lld -> S#%d/Slot#%d\nScore: %.2f | Cov: %.2f"),
							AgentId, Intent.TargetShelterIndex, Intent.TargetSlotIndex, Intent.CurrentScore, EffectiveCover);
						DrawDebugString(World, AgentPos + FVector(0, 0, 110.0f), IntentText, nullptr, FColor::Cyan, 0.0f, true, 0.9f);
					}
				}
				else if (Intent.State == EEcoShelterIntentState::Searching)
				{
					// Candidate proposal evaluated
					if (DisplayBudget > 0)
					{
						--DisplayBudget;
						const FString IntentText = FString::Printf(
							TEXT("[SEARCHING]\nAgent %lld -> S#%d (Score: %.2f)"),
							AgentId, Intent.TargetShelterIndex, Intent.CurrentScore);
						DrawDebugString(World, AgentPos + FVector(0, 0, 100.0f), IntentText, nullptr, FColor::Yellow, 0.0f, true, 0.85f);
					}
				}
			}
		});
	}
}

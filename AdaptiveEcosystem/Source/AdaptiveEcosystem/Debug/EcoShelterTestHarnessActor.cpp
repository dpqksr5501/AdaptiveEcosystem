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
#include "Debug/DebugDrawService.h"
#include "Engine/Canvas.h"
#include "CanvasItem.h"

AEcoShelterTestHarnessActor::AEcoShelterTestHarnessActor()
{
	PrimaryActorTick.bCanEverTick = true;
}

void AEcoShelterTestHarnessActor::BeginPlay()
{
	Super::BeginPlay();

	// Register lightweight 2D Canvas HUD projection delegate on Translucency (always active in editor, simulate, and game viewports)
	DebugDrawDelegateHandle = UDebugDrawService::Register(TEXT("Translucency"),
		FDebugDrawDelegate::CreateUObject(this, &AEcoShelterTestHarnessActor::DrawEntityHUD));
}

void AEcoShelterTestHarnessActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	if (DebugDrawDelegateHandle.IsValid())
	{
		UDebugDrawService::Unregister(DebugDrawDelegateHandle);
		DebugDrawDelegateHandle.Reset();
	}

	Super::EndPlay(EndPlayReason);
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
	DebugQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly);
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
				// Blocked by geometry: Safe green raycast
				DrawDebugLine(World, RayStart, RayEnd, FColor(0, 255, 100), false, -1.0f, 0, 2.5f);
			}
			else
			{
				// Exposed: Dangerous red raycast
				DrawDebugLine(World, RayStart, RayEnd, FColor(255, 60, 60), false, -1.0f, 0, 2.0f);
			}
		}
	}

	// 4. Draw Agent Intent Lines (Color-coded: Green = Safe, Orange = Exposed)
	if (bDrawAgentIntentLines)
	{
		FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(*World);
		EnsureQueriesInitialized(EntityManager);

		FMassExecutionContext Context(EntityManager, DeltaSeconds);

		DebugQuery.ForEachEntityChunk(Context, [World](FMassExecutionContext& ChunkContext)
		{
			const int32 NumEntities = ChunkContext.GetNumEntities();
			TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
			TConstArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetFragmentView<FEcoShelterIntentFragment>();

			for (int32 i = 0; i < NumEntities; ++i)
			{
				const FEcoShelterIntentFragment& Intent = IntentList[i];
				if (Intent.State == EEcoShelterIntentState::Reserved)
				{
					const FVector AgentPos = TransformList[i].GetTransform().GetLocation();
					// Green line for safe/occluded shelter, orange line for exposed shelter
					const FColor LineColor = (Intent.CurrentScore >= 0.7f) ? FColor(0, 255, 120) : FColor(255, 120, 0);
					DrawDebugLine(World, AgentPos + FVector(0, 0, 30.0f), Intent.TargetPosition + FVector(0, 0, 30.0f),
						LineColor, false, -1.0f, 0, 2.0f);
				}
			}
		});
	}
	// 5. Real-time On-Screen Display (OSD) in viewport top-left (Guaranteed visible in all modes)
	if (GEngine && ShelterSub && !ThreatLocation.IsZero())
	{
		for (int32 i = 0; i < Shelters.Num(); ++i)
		{
			if (ShelterSub->IsValidShelterIndex(i))
			{
				const bool bOcc = ShelterSub->CheckThreatOcclusion(ThreatLocation, Shelters[i].Position);
				const FColor OsdColor = bOcc ? FColor(50, 255, 100) : FColor(255, 140, 20);
				GEngine->AddOnScreenDebugMessage(9900 + i, 0.0f, OsdColor,
					FString::Printf(TEXT("[Shelter #%d] %s | OccScore: %.1f"),
						i, bOcc ? TEXT("SAFE (Behind Wall, Score ~0.95)") : TEXT("DANGER (Exposed, Score ~0.59)"),
						bOcc ? 1.0f : 0.1f));
			}
		}
	}
}

void AEcoShelterTestHarnessActor::DrawEntityHUD(UCanvas* Canvas, APlayerController* PC)
{
	if (!Canvas || !GEngine || !bDrawAgentIntentLines)
	{
		return;
	}

	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	const UEcoShelterSubsystem* ShelterSub = World->GetSubsystem<UEcoShelterSubsystem>();
	const FVector ThreatLocation = ResolveActiveThreatLocation();

	// 1. Draw Shelter HUD above each shelter point
	if (bDrawShelters && ShelterSub)
	{
		const TArray<FEcoShelterPoint>& Shelters = ShelterSub->GetShelters();
		const TArray<FEcoShelterSlot>& Slots = ShelterSub->GetShelterSlots();
		const double CurrentTime = World->GetTimeSeconds();

		for (int32 i = 0; i < Shelters.Num(); ++i)
		{
			if (!ShelterSub->IsValidShelterIndex(i))
			{
				continue;
			}

			const FEcoShelterPoint& Shelter = Shelters[i];
			const FVector WorldPos = Shelter.Position + FVector(0.0f, 0.0f, 90.0f);
			FVector2D ScreenPos2D;
			bool bInFrontOfCamera = false;
			if (Canvas->SceneView)
			{
				bInFrontOfCamera = Canvas->SceneView->WorldToPixel(WorldPos, ScreenPos2D);
			}
			else
			{
				const FVector Proj = Canvas->Project(WorldPos, true);
				bInFrontOfCamera = (Proj.Z > 0.0f);
				ScreenPos2D = FVector2D(Proj.X, Proj.Y);
			}

			if (!bInFrontOfCamera || ScreenPos2D.X < -100.0f || ScreenPos2D.X > Canvas->SizeX + 100.0f ||
				ScreenPos2D.Y < -100.0f || ScreenPos2D.Y > Canvas->SizeY + 100.0f)
			{
				continue;
			}

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

			const bool bOccluded = !ThreatLocation.IsZero() && ShelterSub->CheckThreatOcclusion(ThreatLocation, Shelter.Position);
			const FString ShelterText = FString::Printf(TEXT("SHELTER #%d [%s]\nSlots: %d/%d (OccScore: %.1f)"),
				i, bOccluded ? TEXT("SAFE (WALL)") : TEXT("EXPOSED"),
				ReservedCount, TotalSlots,
				bOccluded ? 1.0f : 0.1f);

			const FLinearColor Color = bOccluded ? FLinearColor(0.2f, 1.0f, 0.4f) : FLinearColor(1.0f, 0.3f, 0.2f);
			FCanvasTextItem Item(ScreenPos2D, FText::FromString(ShelterText), GEngine->GetSmallFont(), Color);
			Item.bCentreX = true;
			Item.bCentreY = true;
			Item.EnableShadow(FLinearColor::Black);
			Canvas->DrawItem(Item);
		}
	}

	// 2. Draw Threat Source HUD
	if (!ThreatLocation.IsZero())
	{
		const FVector WorldPos = ThreatLocation + FVector(0.0f, 0.0f, 120.0f);
		FVector2D ThreatScreenPos2D;
		bool bThreatVisible = false;
		if (Canvas->SceneView)
		{
			bThreatVisible = Canvas->SceneView->WorldToPixel(WorldPos, ThreatScreenPos2D);
		}
		else
		{
			const FVector Proj = Canvas->Project(WorldPos, true);
			bThreatVisible = (Proj.Z > 0.0f);
			ThreatScreenPos2D = FVector2D(Proj.X, Proj.Y);
		}

		if (bThreatVisible && ThreatScreenPos2D.X >= 0.0f && ThreatScreenPos2D.X <= Canvas->SizeX &&
			ThreatScreenPos2D.Y >= 0.0f && ThreatScreenPos2D.Y <= Canvas->SizeY)
		{
			FCanvasTextItem ThreatItem(ThreatScreenPos2D, FText::FromString(TEXT("[THREAT SOURCE]")), GEngine->GetSmallFont(), FLinearColor(1.0f, 0.25f, 0.25f));
			ThreatItem.bCentreX = true;
			ThreatItem.bCentreY = true;
			ThreatItem.EnableShadow(FLinearColor::Black);
			Canvas->DrawItem(ThreatItem);
		}
	}

	// 3. Draw Per-Entity HUD (Key essentials only!)
	FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(*World);
	EnsureQueriesInitialized(EntityManager);

	FMassExecutionContext Context(EntityManager);
	const FVector CameraPos = Canvas->SceneView ? Canvas->SceneView->ViewLocation : FVector::ZeroVector;
	const float MaxDistSq = 4000.0f * 4000.0f;

	DebugQuery.ForEachEntityChunk(Context, [this, Canvas, CameraPos, MaxDistSq](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TConstArrayView<FEcoShelterIntentFragment> IntentList = ChunkContext.GetFragmentView<FEcoShelterIntentFragment>();
		TConstArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetFragmentView<FEcoAlarmStateFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			const FVector EntityPos = TransformList[i].GetTransform().GetLocation();

			if (!CameraPos.IsZero() && FVector::DistSquared(EntityPos, CameraPos) > MaxDistSq)
			{
				continue;
			}

			FVector2D ScreenPos2D;
			bool bInFrontOfCamera = false;
			if (Canvas->SceneView)
			{
				bInFrontOfCamera = Canvas->SceneView->WorldToPixel(EntityPos + FVector(0.0f, 0.0f, 65.0f), ScreenPos2D);
			}
			else
			{
				const FVector Proj = Canvas->Project(EntityPos + FVector(0.0f, 0.0f, 65.0f), true);
				bInFrontOfCamera = (Proj.Z > 0.0f);
				ScreenPos2D = FVector2D(Proj.X, Proj.Y);
			}

			if (!bInFrontOfCamera || ScreenPos2D.X < -50.0f || ScreenPos2D.X > Canvas->SizeX + 50.0f ||
				ScreenPos2D.Y < -50.0f || ScreenPos2D.Y > Canvas->SizeY + 50.0f)
			{
				continue;
			}

			const FEcoShelterIntentFragment& Intent = IntentList[i];
			const FEcoAlarmStateFragment& Alarm = AlarmList[i];

			FString ShortText;
			FLinearColor TextColor = FLinearColor::White;

			if (Intent.State == EEcoShelterIntentState::Reserved)
			{
				const bool bSafe = (Intent.CurrentScore >= 0.7f);
				ShortText = FString::Printf(TEXT("S#%d [%s] %.2f"),
					Intent.TargetShelterIndex,
					bSafe ? TEXT("Safe") : TEXT("Danger"),
					Intent.CurrentScore);
				TextColor = bSafe ? FLinearColor(0.2f, 1.0f, 0.4f) : FLinearColor(1.0f, 0.5f, 0.1f);
			}
			else if (Intent.State == EEcoShelterIntentState::Searching)
			{
				ShortText = TEXT("Searching");
				TextColor = FLinearColor(1.0f, 0.9f, 0.2f);
			}
			else
			{
				switch (Alarm.State)
				{
				case EEcoSocialState::Panic:
					ShortText = TEXT("[Panic]");
					TextColor = FLinearColor(1.0f, 0.2f, 0.2f);
					break;
				case EEcoSocialState::Alert:
					ShortText = TEXT("[Alert]");
					TextColor = FLinearColor(1.0f, 0.6f, 0.1f);
					break;
				case EEcoSocialState::Regrouping:
					ShortText = TEXT("[Regroup]");
					TextColor = FLinearColor(1.0f, 0.3f, 1.0f);
					break;
				case EEcoSocialState::Recovering:
					ShortText = TEXT("[Recover]");
					TextColor = FLinearColor(0.2f, 0.9f, 1.0f);
					break;
				case EEcoSocialState::Calm:
				default:
					continue; // Clean viewport: no text for calm idle agents
				}
			}

			FCanvasTextItem TextItem(ScreenPos2D, FText::FromString(ShortText), GEngine->GetSmallFont(), TextColor);
			TextItem.bCentreX = true;
			TextItem.bCentreY = true;
			TextItem.EnableShadow(FLinearColor::Black);
			Canvas->DrawItem(TextItem);
		}
	});
}

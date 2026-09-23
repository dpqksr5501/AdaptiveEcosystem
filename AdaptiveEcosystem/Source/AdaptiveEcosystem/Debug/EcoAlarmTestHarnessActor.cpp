// Copyright Epic Games, Inc. All Rights Reserved.

#include "Debug/EcoAlarmTestHarnessActor.h"
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
#include "DrawDebugHelpers.h"

AEcoAlarmTestHarnessActor::AEcoAlarmTestHarnessActor()
{
	PrimaryActorTick.bCanEverTick = true;
}

void AEcoAlarmTestHarnessActor::TriggerThreatAtTargetHerd()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	UEcoHerdSubsystem* HerdSub = World->GetSubsystem<UEcoHerdSubsystem>();
	if (HerdSub)
	{
		HerdSub->EmitHerdAlarm(TargetHerdIndex, GetActorLocation(), ThreatStrength);
		LastThreatTriggerTime = World->GetTimeSeconds();
		UE_LOG(LogTemp, Log, TEXT("[AEcoAlarmTestHarnessActor] Injected threat to Herd #%d with strength %.2f"), TargetHerdIndex, ThreatStrength);
	}
}

void AEcoAlarmTestHarnessActor::TriggerThreatAtActorLocation()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	UEcoHerdSubsystem* HerdSub = World->GetSubsystem<UEcoHerdSubsystem>();
	if (HerdSub)
	{
		const int32 Count = HerdSub->EmitSpatialAlarm(GetActorLocation(), SpatialThreatRadius, ThreatStrength);
		LastThreatTriggerTime = World->GetTimeSeconds();
		UE_LOG(LogTemp, Log, TEXT("[AEcoAlarmTestHarnessActor] Injected spatial threat at %s (radius: %.0f, affected herds: %d)"),
			*GetActorLocation().ToString(), SpatialThreatRadius, Count);
	}
}

void AEcoAlarmTestHarnessActor::ClearAllAlarms()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	UEcoHerdSubsystem* HerdSub = World->GetSubsystem<UEcoHerdSubsystem>();
	if (HerdSub)
	{
		HerdSub->ClearHerdAlarms();
		UE_LOG(LogTemp, Log, TEXT("[AEcoAlarmTestHarnessActor] Cleared herd threat sources. Member agents will naturally decay to Calm."));
	}
}

void AEcoAlarmTestHarnessActor::EnsureQueriesInitialized(FMassEntityManager& EntityManager)
{
	if (bQueriesInitialized)
	{
		return;
	}

	DebugQuery.Initialize(EntityManager.AsShared());
	DebugQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
	DebugQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);

	HardResetQuery.Initialize(EntityManager.AsShared());
	HardResetQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadWrite);
	HardResetQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);

	bQueriesInitialized = true;
}

void AEcoAlarmTestHarnessActor::HardResetAllAlarms()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	UEcoHerdSubsystem* HerdSub = World->GetSubsystem<UEcoHerdSubsystem>();
	if (HerdSub)
	{
		HerdSub->ClearHerdAlarms();
	}

	FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(*World);
	EnsureQueriesInitialized(EntityManager);

	FMassExecutionContext Context(EntityManager);
	HardResetQuery.ForEachEntityChunk(Context, [](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetMutableFragmentView<FEcoAlarmStateFragment>();
		for (int32 i = 0; i < NumEntities; ++i)
		{
			AlarmList[i].AlarmStrength = 0.0f;
			AlarmList[i].State = EEcoSocialState::Calm;
			AlarmList[i].LastThreatPosition = FVector::ZeroVector;
		}
	});

	UE_LOG(LogTemp, Log, TEXT("[AEcoAlarmTestHarnessActor] Hard-reset all herds and agents to Calm."));
}

void AEcoAlarmTestHarnessActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	if (bContinuousThreat)
	{
		TriggerThreatAtActorLocation();
	}

	const FVector ActorLoc = GetActorLocation();

	// 1. Draw Threat Origin and Influence Area
	if (bDrawThreatArea)
	{
		// Pulsating center sphere
		const float TimeSinceTrigger = (float)(World->GetTimeSeconds() - LastThreatTriggerTime);
		const float PulseAlpha = FMath::Clamp(1.0f - (TimeSinceTrigger / 2.0f), 0.0f, 1.0f);
		const FColor ThreatCenterColor = PulseAlpha > 0.0f ? FColor::Red : FColor(200, 50, 50);
		const float CenterRadius = 80.0f + PulseAlpha * 40.0f;

		DrawDebugSphere(World, ActorLoc, CenterRadius, 16, ThreatCenterColor, false, -1.0f, 0, 3.0f);
		DrawDebugCircle(World, ActorLoc, SpatialThreatRadius, 48, FColor::Red, false, -1.0f, 0, 2.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);

		// Arrow to Target Herd center if valid
		const UEcoHerdSubsystem* HerdSub = World->GetSubsystem<UEcoHerdSubsystem>();
		if (HerdSub && HerdSub->IsValidHerdIndex(TargetHerdIndex))
		{
			FEcoHerdRuntimeData TargetHerd;
			if (HerdSub->GetHerdData(TargetHerdIndex, TargetHerd))
			{
				DrawDebugDirectionalArrow(World, ActorLoc, TargetHerd.Center, 60.0f, FColor::Orange, false, -1.0f, 0, 2.0f);
				DrawDebugString(World, (ActorLoc + TargetHerd.Center) * 0.5f + FVector(0, 0, 50.0f),
					FString::Printf(TEXT("Target Herd #%d (Alarm: %.2f)"), TargetHerdIndex, TargetHerd.AlarmStrength),
					nullptr, FColor::Orange, 0.0f, true, 1.0f);
			}
		}

		// Text above threat actor
		const FString ThreatText = FString::Printf(TEXT("[Threat Source]\nStrength: %.2f\nContinuous: %s"),
			ThreatStrength, bContinuousThreat ? TEXT("ON") : TEXT("OFF"));
		DrawDebugString(World, ActorLoc + FVector(0, 0, CenterRadius + 40.0f), ThreatText, nullptr, FColor::Red, 0.0f, true, 1.2f);
	}

	// 2. Draw Per-Entity Alarm State HUD
	if (bDrawEntityAlarmStates)
	{
		FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(*World);
		EnsureQueriesInitialized(EntityManager);

		FMassExecutionContext Context(EntityManager, DeltaSeconds);
		int32 DisplayTextBudget = 15; // Limit 3D text labels to avoid viewport clutter

		DebugQuery.ForEachEntityChunk(Context, [World, &DisplayTextBudget](FMassExecutionContext& ChunkContext)
		{
			const int32 NumEntities = ChunkContext.GetNumEntities();
			TConstArrayView<FEcoAlarmStateFragment> AlarmList = ChunkContext.GetFragmentView<FEcoAlarmStateFragment>();
			TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
			TConstArrayView<FEcoPolicyOutputFragment> PolicyList = ChunkContext.GetFragmentView<FEcoPolicyOutputFragment>();
			TConstArrayView<FEcoSocialBehaviorFragment> SocialList = ChunkContext.GetFragmentView<FEcoSocialBehaviorFragment>();

			for (int32 i = 0; i < NumEntities; ++i)
			{
				const FEcoAlarmStateFragment& Alarm = AlarmList[i];
				const FVector EntityPos = TransformList[i].GetTransform().GetLocation();
				const FEcoPolicyActionV1& RawAction = PolicyList[i].Action;
				const FEcoPolicyActionV1& ModAction = SocialList[i].ModulatedAction;

				FColor StateColor;
				float SphereRadius = 20.0f;
				const TCHAR* StateName = TEXT("Calm");

				switch (Alarm.State)
				{
				case EEcoSocialState::Panic:
					StateColor = FColor::Red;
					SphereRadius = 35.0f;
					StateName = TEXT("Panic");
					break;
				case EEcoSocialState::Alert:
					StateColor = FColor::Orange;
					SphereRadius = 28.0f;
					StateName = TEXT("Alert");
					break;
				case EEcoSocialState::Recovering:
					StateColor = FColor::Cyan;
					SphereRadius = 24.0f;
					StateName = TEXT("Recovering");
					break;
				case EEcoSocialState::Regrouping:
					StateColor = FColor::Magenta;
					SphereRadius = 24.0f;
					StateName = TEXT("Regrouping");
					break;
				case EEcoSocialState::Calm:
				default:
					StateColor = FColor::Green;
					SphereRadius = 18.0f;
					StateName = TEXT("Calm");
					break;
				}

				// Small colored indicator sphere above alarmed entity (skip Calm to maintain 120 FPS)
				if (Alarm.State != EEcoSocialState::Calm)
				{
					DrawDebugSphere(World, EntityPos + FVector(0, 0, 40.0f), SphereRadius, 8, StateColor, false, -1.0f, 0, 1.5f);
				}
			}
		});
	}
}

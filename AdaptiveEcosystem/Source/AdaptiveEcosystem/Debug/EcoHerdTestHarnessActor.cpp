// Copyright Epic Games, Inc. All Rights Reserved.

#include "Debug/EcoHerdTestHarnessActor.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassEntityManager.h"
#include "MassEntityUtils.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"
#include "DrawDebugHelpers.h"

AEcoHerdTestHarnessActor::AEcoHerdTestHarnessActor()
{
	PrimaryActorTick.bCanEverTick = true;
}

void AEcoHerdTestHarnessActor::BeginPlay()
{
	Super::BeginPlay();

	if (bAutoSpawnOnBeginPlay)
	{
		SpawnTestHerds();
	}
}

void AEcoHerdTestHarnessActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	ClearTestHerds();
	Super::EndPlay(EndPlayReason);
}

void AEcoHerdTestHarnessActor::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (!bDrawDebugHerds)
	{
		return;
	}

	const UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	const UEcoHerdSubsystem* HerdSubsystem = World->GetSubsystem<UEcoHerdSubsystem>();
	if (!HerdSubsystem)
	{
		return;
	}

	const TArray<FEcoHerdRuntimeData>& ActiveHerds = HerdSubsystem->GetActiveHerds();
	for (const FEcoHerdRuntimeData& Herd : ActiveHerds)
	{
		if (Herd.MemberCount <= 0 || Herd.RuntimeIndex == INDEX_NONE_ECO)
		{
			continue;
		}

		// Centroid representation
		DrawDebugSphere(World, Herd.Center, 60.0f, 16, FColor::Emerald, false, -1.0f, 0, 3.0f);

		// Hysteresis boundary rings (Join = 800, Leave = 1400)
		DrawDebugCircle(World, Herd.Center, 800.0f, 36, FColor::Green, false, -1.0f, 0, 2.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
		DrawDebugCircle(World, Herd.Center, 1400.0f, 36, FColor::Yellow, false, -1.0f, 0, 1.5f, FVector(1, 0, 0), FVector(0, 1, 0), false);

		// Average velocity vector
		if (!Herd.AverageVelocity.IsNearlyZero())
		{
			DrawDebugDirectionalArrow(World, Herd.Center, Herd.Center + Herd.AverageVelocity * 0.5f, 50.0f, FColor::Cyan, false, -1.0f, 0, 2.0f);
		}

		// Information tag
		const FString InfoText = FString::Printf(TEXT("Herd #%d (Persistent ID: %lld)\nMembers: %d\nAlarm: %.2f"),
			Herd.RuntimeIndex, Herd.PersistentHerdId, Herd.MemberCount, Herd.AlarmStrength);
		DrawDebugString(World, Herd.Center + FVector(0.0f, 0.0f, 120.0f), InfoText, nullptr, FColor::White, 0.0f, true, 1.2f);
	}
}

void AEcoHerdTestHarnessActor::SpawnTestHerds()
{
	ClearTestHerds();

	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(*World);

	// 1. Build Archetype descriptor with required fragments and tags
	TArray<const UScriptStruct*> FragmentsAndTags;
	FragmentsAndTags.Add(FTransformFragment::StaticStruct());
	FragmentsAndTags.Add(FMassVelocityFragment::StaticStruct());
	FragmentsAndTags.Add(FEcoIdentityFragment::StaticStruct());
	FragmentsAndTags.Add(FEcoHerdMemberFragment::StaticStruct());
	FragmentsAndTags.Add(FEcoSocialBehaviorFragment::StaticStruct());
	FragmentsAndTags.Add(FEcoAlarmStateFragment::StaticStruct());
	FragmentsAndTags.Add(FEcoShelterIntentFragment::StaticStruct());
	FragmentsAndTags.Add(FEcoPolicyOutputFragment::StaticStruct());
	FragmentsAndTags.Add(FEcoAliveTag::StaticStruct());

	// 2. Configure species shared parameters
	FEcoSocialSpeciesSharedFragment SpeciesShared;
	SpeciesShared.HerdJoinRadius = 800.0f;
	SpeciesShared.HerdLeaveRadius = 1400.0f;
	SpeciesShared.HerdMergeRadius = 1000.0f;
	SpeciesShared.JoinDwellTime = 0.5f;
	SpeciesShared.LeaveDwellTime = 1.0f;
	const FSharedStruct SharedConfig = EntityManager.GetOrCreateSharedFragment(SpeciesShared);

	FEcoSpeciesSharedFragment SpeciesBaseShared;
	SpeciesBaseShared.CoverSearchRadius = CoverSearchRadius;
	const FSharedStruct SpeciesBaseConfig = EntityManager.GetOrCreateSharedFragment(SpeciesBaseShared);

	FMassArchetypeSharedFragmentValues SharedValues;
	SharedValues.Add(SharedConfig);
	SharedValues.Add(SpeciesBaseConfig);

	const FMassArchetypeHandle Archetype = EntityManager.CreateArchetype(FragmentsAndTags);
	EntityManager.BatchCreateEntities(Archetype, SharedValues, EntityCount, SpawnedEntities);

	// 3. Initialize spatial distribution across clusters
	const FVector ActorLoc = GetActorLocation();
	const int32 SafeClusterCount = FMath::Max(1, ClusterCount);

	TArray<FVector> ClusterCenters;
	ClusterCenters.Reserve(SafeClusterCount);
	for (int32 c = 0; c < SafeClusterCount; ++c)
	{
		const float Angle = (float)c / (float)SafeClusterCount * 2.0f * PI;
		ClusterCenters.Add(ActorLoc + FVector(FMath::Cos(Angle) * AreaRadius * 0.6f, FMath::Sin(Angle) * AreaRadius * 0.6f, 0.0f));
	}

	for (int32 i = 0; i < SpawnedEntities.Num(); ++i)
	{
		const FMassEntityHandle Entity = SpawnedEntities[i];
		const int32 ClusterIdx = i % SafeClusterCount;
		const FVector& ClusterCenter = ClusterCenters[ClusterIdx];

		const FVector Offset(FMath::RandRange(-400.0f, 400.0f), FMath::RandRange(-400.0f, 400.0f), 0.0f);
		const FVector InitialPos = ClusterCenter + Offset;

		FTransformFragment& TransformFrag = EntityManager.GetFragmentDataChecked<FTransformFragment>(Entity);
		TransformFrag.SetTransform(FTransform(FRotator::ZeroRotator, InitialPos));

		FMassVelocityFragment& VelocityFrag = EntityManager.GetFragmentDataChecked<FMassVelocityFragment>(Entity);
		VelocityFrag.Value = FVector(FMath::RandRange(-30.0f, 30.0f), FMath::RandRange(-30.0f, 30.0f), 0.0f);

		FEcoIdentityFragment& IdentityFrag = EntityManager.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
		IdentityFrag.StableAgentId = 1000 + i;
		IdentityFrag.SpeciesId = FName(TEXT("PreySpeciesA"));
		IdentityFrag.SpeciesRuntimeIndex = 0;

		FEcoHerdMemberFragment& HerdFrag = EntityManager.GetFragmentDataChecked<FEcoHerdMemberFragment>(Entity);
		HerdFrag.HerdRuntimeIndex = INDEX_NONE_ECO;
		HerdFrag.MembershipConfidence = 0.0f;
		HerdFrag.JoinDwellTimer = 0.0f;
		HerdFrag.LeaveDwellTimer = 0.0f;

		FEcoPolicyOutputFragment& PolicyOutputFrag = EntityManager.GetFragmentDataChecked<FEcoPolicyOutputFragment>(Entity);
		PolicyOutputFrag.Action.Forage = 0.8f;
		PolicyOutputFrag.Action.Cohesion = 0.5f;
		PolicyOutputFrag.Action.FleeDist = 0.2f;
		PolicyOutputFrag.Action.Cover = 0.1f;

		FEcoAlarmStateFragment& AlarmFrag = EntityManager.GetFragmentDataChecked<FEcoAlarmStateFragment>(Entity);
		AlarmFrag.AlarmStrength = 0.0f;
		AlarmFrag.State = EEcoSocialState::Calm;
		AlarmFrag.LastThreatPosition = FVector::ZeroVector;

		FEcoSocialBehaviorFragment& SocialFrag = EntityManager.GetFragmentDataChecked<FEcoSocialBehaviorFragment>(Entity);
		SocialFrag.ModulatedAction = PolicyOutputFrag.Action;
		SocialFrag.SocialCohesionMultiplier = 1.0f;
		SocialFrag.bWantsNewHerd = false;

		FEcoShelterIntentFragment& ShelterFrag = EntityManager.GetFragmentDataChecked<FEcoShelterIntentFragment>(Entity);
		ShelterFrag.Reset();
	}

	// 4. Verify that UEcoShelterQueryProcessor requirements match the spawned entities
	FMassEntityQuery ShelterMatchingQuery;
	ShelterMatchingQuery.Initialize(EntityManager.AsShared());
	ShelterMatchingQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	ShelterMatchingQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	ShelterMatchingQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly);
	ShelterMatchingQuery.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadOnly);
	ShelterMatchingQuery.AddRequirement<FEcoShelterIntentFragment>(EMassFragmentAccess::ReadOnly);
	ShelterMatchingQuery.AddSharedRequirement<FEcoSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	ShelterMatchingQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);

	int32 MatchedCount = 0;
	FMassExecutionContext VerifyContext(EntityManager);
	ShelterMatchingQuery.ForEachEntityChunk(VerifyContext, [&MatchedCount](FMassExecutionContext& ChunkContext)
	{
		MatchedCount += ChunkContext.GetNumEntities();
	});

	UE_LOG(LogTemp, Log, TEXT("[AEcoHerdTestHarnessActor] Spawned %d entities across %d clusters. ShelterQuery matching check matched %d entities (CoverSearchRadius: %.1f)."),
		SpawnedEntities.Num(), SafeClusterCount, MatchedCount, CoverSearchRadius);
}

void AEcoHerdTestHarnessActor::ClearTestHerds()
{
	if (SpawnedEntities.Num() == 0)
	{
		return;
	}

	UWorld* World = GetWorld();
	if (World)
	{
		FMassEntityManager& EntityManager = UE::Mass::Utils::GetEntityManagerChecked(*World);
		EntityManager.BatchDestroyEntities(SpawnedEntities);
		UE_LOG(LogTemp, Log, TEXT("[AEcoHerdTestHarnessActor] Cleared %d test entities."), SpawnedEntities.Num());
	}

	SpawnedEntities.Empty();
}

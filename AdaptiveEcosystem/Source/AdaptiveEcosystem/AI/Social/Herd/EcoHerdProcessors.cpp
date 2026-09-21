// Copyright Epic Games, Inc. All Rights Reserved.

#include "AI/Social/Herd/EcoHerdProcessors.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassCommonTypes.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"

// -----------------------------------------------------------------------------
// UEcoHerdMembershipProcessor
// -----------------------------------------------------------------------------

UEcoHerdMembershipProcessor::UEcoHerdMembershipProcessor()
	: EntityQuery(*this)
	, ReconciliationQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true; // Ensures deterministic herd assignment
}

void UEcoHerdMembershipProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	// Pass 1: Parallel chunk evaluation of existing herd membership and join/leave hysteresis
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.RegisterWithProcessor(*this);

	// Pass 2: Single-threaded reconciliation for unassigned agents requiring new herd creation
	ReconciliationQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	ReconciliationQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	ReconciliationQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadWrite);
	ReconciliationQuery.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	ReconciliationQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	ReconciliationQuery.RegisterWithProcessor(*this);
}

void UEcoHerdMembershipProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	TimeSinceLastUpdate += Context.GetDeltaTimeSeconds();
	if (TimeSinceLastUpdate < UpdateInterval)
	{
		return;
	}

	const float DeltaTime = TimeSinceLastUpdate;
	TimeSinceLastUpdate = 0.0f;

	UWorld* World = Context.GetWorld();
	if (!World)
	{
		return;
	}

	UEcoHerdSubsystem* HerdSubsystem = World->GetSubsystem<UEcoHerdSubsystem>();
	if (!HerdSubsystem)
	{
		return;
	}

	// -------------------------------------------------------------------------
	// Pass 1: Evaluate existing membership and join proximity against established herds
	// -------------------------------------------------------------------------
	EntityQuery.ForEachEntityChunk(Context, [HerdSubsystem, DeltaTime](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoIdentityFragment> IdentityList = ChunkContext.GetFragmentView<FEcoIdentityFragment>();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TArrayView<FEcoHerdMemberFragment> MemberList = ChunkContext.GetMutableFragmentView<FEcoHerdMemberFragment>();
		const FEcoSocialSpeciesSharedFragment& SocialConfig = ChunkContext.GetSharedFragment<FEcoSocialSpeciesSharedFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			const FEcoIdentityFragment& Identity = IdentityList[i];
			const FVector AgentLocation = TransformList[i].GetTransform().GetLocation();
			FEcoHerdMemberFragment& Member = MemberList[i];
			const int32 SpeciesIdx = Identity.SpeciesRuntimeIndex;

			// Case 1: Agent currently belongs to a valid herd
			if (Member.HerdRuntimeIndex != INDEX_NONE_ECO)
			{
				FEcoHerdRuntimeData CurrentHerd;
				if (HerdSubsystem->GetHerdData(Member.HerdRuntimeIndex, CurrentHerd) && CurrentHerd.PersistentHerdId != 0)
				{
					const float DistToCenter = FVector::Dist(AgentLocation, CurrentHerd.Center);

					// Hysteresis detachment check (LeaveRadius > JoinRadius)
					if (DistToCenter > SocialConfig.HerdLeaveRadius)
					{
						Member.LeaveDwellTimer += DeltaTime;
						if (Member.LeaveDwellTimer >= SocialConfig.LeaveDwellTime)
						{
							// Sustained detachment -> leave herd
							Member.HerdRuntimeIndex = INDEX_NONE_ECO;
							Member.LeaveDwellTimer = 0.0f;
							Member.MembershipConfidence = 0.0f;
						}
					}
					else
					{
						// Recover leave timer while within herd radius
						Member.LeaveDwellTimer = FMath::Max(0.0f, Member.LeaveDwellTimer - DeltaTime);
						Member.MembershipConfidence = FMath::Clamp(1.0f - (DistToCenter / FMath::Max(1.0f, SocialConfig.HerdLeaveRadius)), 0.0f, 1.0f);
					}
				}
				else
				{
					// Herd was dissolved or index invalidated
					Member.HerdRuntimeIndex = INDEX_NONE_ECO;
					Member.LeaveDwellTimer = 0.0f;
					Member.MembershipConfidence = 0.0f;
				}
			}

			// Case 2: Agent has no herd -> check if any established herd is nearby
			if (Member.HerdRuntimeIndex == INDEX_NONE_ECO)
			{
				const int32 NearestHerdIndex = HerdSubsystem->FindNearestHerd(SpeciesIdx, AgentLocation, SocialConfig.HerdJoinRadius);
				if (NearestHerdIndex != INDEX_NONE_ECO)
				{
					Member.JoinDwellTimer += DeltaTime;
					if (Member.JoinDwellTimer >= SocialConfig.JoinDwellTime)
					{
						Member.HerdRuntimeIndex = NearestHerdIndex;
						Member.JoinDwellTimer = 0.0f;
						Member.MembershipConfidence = 0.5f;
					}
				}
				else
				{
					Member.JoinDwellTimer = FMath::Max(0.0f, Member.JoinDwellTimer - DeltaTime);
				}
			}
		}
	});

	// -------------------------------------------------------------------------
	// Pass 2: Single-threaded reconciliation for unassigned agents to spawn new herds
	// -------------------------------------------------------------------------
	ReconciliationQuery.ForEachEntityChunk(Context, [HerdSubsystem](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FEcoIdentityFragment> IdentityList = ChunkContext.GetFragmentView<FEcoIdentityFragment>();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TArrayView<FEcoHerdMemberFragment> MemberList = ChunkContext.GetMutableFragmentView<FEcoHerdMemberFragment>();
		const FEcoSocialSpeciesSharedFragment& SocialConfig = ChunkContext.GetSharedFragment<FEcoSocialSpeciesSharedFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			FEcoHerdMemberFragment& Member = MemberList[i];
			if (Member.HerdRuntimeIndex != INDEX_NONE_ECO)
			{
				continue;
			}

			const int32 SpeciesIdx = IdentityList[i].SpeciesRuntimeIndex;
			const FVector AgentLocation = TransformList[i].GetTransform().GetLocation();

			// Re-check nearest herd (might have been formed by earlier entity in this pass)
			const int32 NearestHerdIndex = HerdSubsystem->FindNearestHerd(SpeciesIdx, AgentLocation, SocialConfig.HerdJoinRadius);
			if (NearestHerdIndex != INDEX_NONE_ECO)
			{
				Member.HerdRuntimeIndex = NearestHerdIndex;
				Member.JoinDwellTimer = 0.0f;
				Member.MembershipConfidence = 0.7f;
			}
			else
			{
				// Thread-safe new herd allocation performed on single thread
				const int32 NewHerdIndex = HerdSubsystem->AllocateHerd(SpeciesIdx, AgentLocation);
				if (NewHerdIndex != INDEX_NONE_ECO)
				{
					Member.HerdRuntimeIndex = NewHerdIndex;
					Member.JoinDwellTimer = 0.0f;
					Member.MembershipConfidence = 1.0f;
				}
			}
		}
	});
}

// -----------------------------------------------------------------------------
// UEcoHerdAggregateProcessor
// -----------------------------------------------------------------------------

UEcoHerdAggregateProcessor::UEcoHerdAggregateProcessor()
	: EntityQuery(*this)
{
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(UEcoHerdMembershipProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true;
}

void UEcoHerdAggregateProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.RegisterWithProcessor(*this);
}

void UEcoHerdAggregateProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	TimeSinceLastUpdate += Context.GetDeltaTimeSeconds();
	if (TimeSinceLastUpdate < UpdateInterval)
	{
		return;
	}
	TimeSinceLastUpdate = 0.0f;

	UWorld* World = Context.GetWorld();
	if (!World)
	{
		return;
	}

	UEcoHerdSubsystem* HerdSubsystem = World->GetSubsystem<UEcoHerdSubsystem>();
	if (!HerdSubsystem)
	{
		return;
	}

	const TArray<FEcoHerdRuntimeData>& ActiveHerds = HerdSubsystem->GetActiveHerds();
	const int32 HerdCount = ActiveHerds.Num();
	if (HerdCount == 0)
	{
		return;
	}

	// Prepare reduction buffers
	Accumulators.SetNum(HerdCount);
	for (int32 i = 0; i < HerdCount; ++i)
	{
		Accumulators[i] = FHerdAccumulator();
	}

	// Pass 1: Accumulate member positions, velocities, and pick closest representative
	EntityQuery.ForEachEntityChunk(Context, [this, &ActiveHerds](FMassExecutionContext& ChunkContext)
	{
		const int32 NumEntities = ChunkContext.GetNumEntities();
		TConstArrayView<FTransformFragment> TransformList = ChunkContext.GetFragmentView<FTransformFragment>();
		TConstArrayView<FMassVelocityFragment> VelocityList = ChunkContext.GetFragmentView<FMassVelocityFragment>();
		TConstArrayView<FEcoHerdMemberFragment> MemberList = ChunkContext.GetFragmentView<FEcoHerdMemberFragment>();

		for (int32 i = 0; i < NumEntities; ++i)
		{
			const int32 HerdIdx = MemberList[i].HerdRuntimeIndex;
			if (Accumulators.IsValidIndex(HerdIdx) && ActiveHerds[HerdIdx].PersistentHerdId != 0)
			{
				const FVector Loc = TransformList[i].GetTransform().GetLocation();
				const FVector Vel = VelocityList[i].Value;
				FHerdAccumulator& Acc = Accumulators[HerdIdx];

				Acc.SumLocation += Loc;
				Acc.SumVelocity += Vel;
				Acc.MemberCount++;

				// Candidate representative: closest living entity to the herd's current center
				const float DistSq = FVector::DistSquared(Loc, ActiveHerds[HerdIdx].Center);
				if (DistSq < Acc.MinCenterDistSq)
				{
					Acc.MinCenterDistSq = DistSq;
					Acc.BestRepresentative = ChunkContext.GetEntity(i);
				}
			}
		}
	});

	// Pass 2: Single-threaded reconciliation to apply computed center and average velocity
	for (int32 i = 0; i < HerdCount; ++i)
	{
		if (ActiveHerds[i].PersistentHerdId == 0)
		{
			continue;
		}

		const FHerdAccumulator& Acc = Accumulators[i];
		if (Acc.MemberCount > 0)
		{
			const FVector NewCenter = Acc.SumLocation / static_cast<float>(Acc.MemberCount);
			const FVector NewAvgVel = Acc.SumVelocity / static_cast<float>(Acc.MemberCount);
			HerdSubsystem->UpdateHerdAggregate(i, NewCenter, NewAvgVel, Acc.MemberCount, Acc.BestRepresentative);
		}
		else
		{
			// Herd has zero members -> release slot
			HerdSubsystem->ReleaseHerd(i);
		}
	}
}

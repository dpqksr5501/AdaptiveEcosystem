// Copyright Epic Games, Inc. All Rights Reserved.

#include "Network/Mass/EcoMassReplicator.h"

#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassExecutionContext.h"
#include "MassReplicationFragments.h"
#include "MassReplicationTransformHandlers.h"
#include "Network/Mass/EcoMassClientBubble.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(EcoMassReplicator)

void UEcoMassReplicator::AddRequirements(FMassEntityQuery& EntityQuery)
{
	FMassReplicationProcessorPositionYawHandler::AddRequirements(EntityQuery);
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
}

void UEcoMassReplicator::ProcessClientReplication(FMassExecutionContext& Context, FMassReplicationContext& ReplicationContext)
{
#if UE_REPLICATION_COMPILE_SERVER_CODE
	FMassReplicationProcessorPositionYawHandler PositionYawHandler;
	FMassReplicationSharedFragment* ReplicationSharedFragment = nullptr;
	TConstArrayView<FEcoIdentityFragment> IdentityFragments;
	TConstArrayView<FEcoRegionFragment> RegionFragments;

	auto CacheViews = [&ReplicationSharedFragment, &PositionYawHandler, &IdentityFragments, &RegionFragments](FMassExecutionContext& ExecutionContext)
	{
		PositionYawHandler.CacheFragmentViews(ExecutionContext);
		IdentityFragments = ExecutionContext.GetFragmentView<FEcoIdentityFragment>();
		RegionFragments = ExecutionContext.GetFragmentView<FEcoRegionFragment>();
		ReplicationSharedFragment = &ExecutionContext.GetMutableSharedFragment<FMassReplicationSharedFragment>();
		check(ReplicationSharedFragment);
	};

	auto AddEntity = [&ReplicationSharedFragment, &PositionYawHandler, &IdentityFragments, &RegionFragments](
		FMassExecutionContext& ExecutionContext,
		const int32 EntityIndex,
		FReplicatedEcoMassAgent& ReplicatedAgent,
		const FMassClientHandle ClientHandle) -> FMassReplicatedAgentHandle
	{
		AEcoMassClientBubbleInfo& BubbleInfo =
			ReplicationSharedFragment->GetTypedClientBubbleInfoChecked<AEcoMassClientBubbleInfo>(ClientHandle);

		PositionYawHandler.AddEntity(EntityIndex, ReplicatedAgent.GetReplicatedPositionYawDataMutable());
		ReplicatedAgent.SetStableAgentId(IdentityFragments[EntityIndex].StableAgentId);
		ReplicatedAgent.SetSpeciesId(IdentityFragments[EntityIndex].SpeciesId);
		ReplicatedAgent.SetRegionId(RegionFragments[EntityIndex].CurrentRegionId);

		return BubbleInfo.GetSerializer().Bubble.AddAgent(ExecutionContext.GetEntity(EntityIndex), ReplicatedAgent);
	};

	auto ModifyEntity = [&ReplicationSharedFragment, &PositionYawHandler, &IdentityFragments, &RegionFragments](
		FMassExecutionContext&,
		const int32 EntityIndex,
		const EMassLOD::Type,
		const double,
		const FMassReplicatedAgentHandle Handle,
		const FMassClientHandle ClientHandle)
	{
		AEcoMassClientBubbleInfo& BubbleInfo =
			ReplicationSharedFragment->GetTypedClientBubbleInfoChecked<AEcoMassClientBubbleInfo>(ClientHandle);
		FEcoMassClientBubbleHandler& Bubble = BubbleInfo.GetSerializer().Bubble;

		PositionYawHandler.ModifyEntity<FEcoMassFastArrayItem>(Handle, EntityIndex, Bubble.GetTransformHandlerMutable());

		FEcoMassFastArrayItem& Item = Bubble.GetAgentItem(Handle);
		const FEcoIdentityFragment& Identity = IdentityFragments[EntityIndex];
		const FEcoRegionFragment& Region = RegionFragments[EntityIndex];
		if (Item.Agent.GetStableAgentId() != Identity.StableAgentId
			|| Item.Agent.GetSpeciesId() != Identity.SpeciesId
			|| Item.Agent.GetRegionId() != Region.CurrentRegionId)
		{
			Item.Agent.SetStableAgentId(Identity.StableAgentId);
			Item.Agent.SetSpeciesId(Identity.SpeciesId);
			Item.Agent.SetRegionId(Region.CurrentRegionId);
			Bubble.MarkItemDirty(Item);
		}
	};

	auto RemoveEntity = [&ReplicationSharedFragment](
		FMassExecutionContext&,
		const FMassReplicatedAgentHandle Handle,
		const FMassClientHandle ClientHandle)
	{
		AEcoMassClientBubbleInfo& BubbleInfo =
			ReplicationSharedFragment->GetTypedClientBubbleInfoChecked<AEcoMassClientBubbleInfo>(ClientHandle);
		BubbleInfo.GetSerializer().Bubble.RemoveAgentChecked(Handle);
	};

	CalculateClientReplication<FEcoMassFastArrayItem>(Context, ReplicationContext, CacheViews, AddEntity, ModifyEntity, RemoveEntity);
#endif
}

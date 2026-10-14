// Copyright Epic Games, Inc. All Rights Reserved.

#include "Network/Mass/EcoMassReplicator.h"

#include "AdaptiveEcosystem.h"
#include "HAL/IConsoleManager.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Engine/World.h"
#include "MassExecutionContext.h"
#include "MassReplicationFragments.h"
#include "MassReplicationTransformHandlers.h"
#include "Network/Mass/EcoMassClientBubble.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Core/EcoRuntimeSettings.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(EcoMassReplicator)

#if UE_REPLICATION_COMPILE_SERVER_CODE && !UE_BUILD_SHIPPING
namespace
{
	TAutoConsoleVariable<int32> TraceSamples(TEXT("eco.M4.TraceSamples"), 0,
		TEXT("Manual server sample trace: 0=off, 1=dirty/Add/Remove, 2=also unchanged interval checks. Process-wide across PIE worlds."));

	void TraceSample(const AEcoMassClientBubbleInfo& Bubble, const FEcoMassFastArrayItem& Item,
		const TCHAR* Reason, double CheckTime, double CheckDelta, bool bDirty)
	{
		const int32 TraceMode = TraceSamples.GetValueOnGameThread();
		if (TraceMode <= 0 || (!bDirty && TraceMode < 2)) return;
		const auto Sample = Item.Agent.MakeRepresentationSnapshot();
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("[M4 Sample] World=%s Bubble=%s ID=%lld LOD=%d Interval=%.3f CheckTime=%.6f CheckDelta=%.6f Sequence=%u VisualRevision=%u ResetRevision=%u SampleTime=%.6f Dirty=%d Reason=%s"),
			*Bubble.GetWorld()->GetName(), *Bubble.GetName(), Sample.StableAgentId,
			static_cast<int32>(Item.LastObservedLOD), Item.ConfiguredUpdateInterval, CheckTime, CheckDelta,
			Sample.SampleSequence, Sample.VisualRevision, Sample.MovementDiscontinuityRevision,
			Sample.ServerSampleRealTimeSeconds, bDirty, Reason);
	}
}
#endif

void UEcoMassReplicator::AddRequirements(FMassEntityQuery& EntityQuery)
{
	FMassReplicationProcessorPositionYawHandler::AddRequirements(EntityQuery);
	EntityQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoMovementDiscontinuityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoCreaturePresentationFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
}

void UEcoMassReplicator::ProcessClientReplication(FMassExecutionContext& Context, FMassReplicationContext& ReplicationContext)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoReplication_Connection);
#if UE_REPLICATION_COMPILE_SERVER_CODE
	FMassReplicationProcessorPositionYawHandler PositionYawHandler;
	FMassReplicationSharedFragment* ReplicationSharedFragment = nullptr;
	const FMassReplicationParameters* ReplicationParams = nullptr;
	TArrayView<FMassReplicatedAgentFragment> ReplicatedAgentFragments;
	TConstArrayView<FMassReplicationLODFragment> LODFragments;
	TConstArrayView<FEcoIdentityFragment> IdentityFragments;
	TConstArrayView<FEcoRegionFragment> RegionFragments;
	TConstArrayView<FEcoVitalsFragment> VitalsFragments;
	TConstArrayView<FEcoMovementDiscontinuityFragment> DiscontinuityFragments;
	const auto UpdateVisualState = [&VitalsFragments](FReplicatedEcoMassAgent& Agent, int32 Index, const FMassExecutionContext& ExecutionContext)
	{
		const FEcoVitalsFragment& Vitals = VitalsFragments[Index];
		return Agent.SetVisualState(Vitals.MaxHP > 0.0f ? Vitals.HP / Vitals.MaxHP : 0.0f,
			Vitals.MaxEnergy > 0.0f ? Vitals.Energy / Vitals.MaxEnergy : 0.0f,
			ExecutionContext.DoesArchetypeHaveTag<FEcoAliveTag>() ? EEcoVisualLifeState::Alive : EEcoVisualLifeState::Dead);
	};

	TConstArrayView<FEcoCreaturePresentationFragment> VisualFragments;

	auto CacheViews = [&](FMassExecutionContext& ExecutionContext)
	{
		PositionYawHandler.CacheFragmentViews(ExecutionContext);
		IdentityFragments = ExecutionContext.GetFragmentView<FEcoIdentityFragment>();
		RegionFragments = ExecutionContext.GetFragmentView<FEcoRegionFragment>();
		VitalsFragments = ExecutionContext.GetFragmentView<FEcoVitalsFragment>();
		DiscontinuityFragments = ExecutionContext.GetFragmentView<FEcoMovementDiscontinuityFragment>();
		VisualFragments = ExecutionContext.GetFragmentView<FEcoCreaturePresentationFragment>();
		ReplicationSharedFragment = &ExecutionContext.GetMutableSharedFragment<FMassReplicationSharedFragment>();
		ReplicationParams = &ExecutionContext.GetConstSharedFragment<FMassReplicationParameters>();
		ReplicatedAgentFragments = ExecutionContext.GetMutableFragmentView<FMassReplicatedAgentFragment>();
		LODFragments = ExecutionContext.GetFragmentView<FMassReplicationLODFragment>();
		check(ReplicationSharedFragment);
	};

	auto AddEntity = [&](
		FMassExecutionContext& ExecutionContext,
		const int32 EntityIndex,
		FReplicatedEcoMassAgent& ReplicatedAgent,
		const FMassClientHandle ClientHandle) -> FMassReplicatedAgentHandle
	{
		AEcoMassClientBubbleInfo& BubbleInfo =
			ReplicationSharedFragment->GetTypedClientBubbleInfoChecked<AEcoMassClientBubbleInfo>(ClientHandle);
		const auto& Budget = GetDefault<UEcoRuntimeSettings>()->ConnectionBudget;
		if (!BubbleInfo.GetSerializer().Bubble.ReserveAdd(GFrameCounter,
			BubbleInfo.GetSerializer().GetAgentItems().Num(), Budget.MaxRelevantAgents, Budget.MaxAddsPerUpdate))
			return FMassReplicatedAgentHandle(); // The engine retries an invalid handle while still relevant.

		PositionYawHandler.AddEntity(EntityIndex, ReplicatedAgent.GetReplicatedPositionYawDataMutable());
		ReplicatedAgent.SetStableAgentId(IdentityFragments[EntityIndex].StableAgentId);
		ReplicatedAgent.SetSpeciesId(IdentityFragments[EntityIndex].SpeciesId);
		ReplicatedAgent.SetRegionId(RegionFragments[EntityIndex].CurrentRegionId);
		UpdateVisualState(ReplicatedAgent, EntityIndex, ExecutionContext);
		ReplicatedAgent.SetMovementDiscontinuityRevision(DiscontinuityFragments[EntityIndex].Revision);
		ReplicatedAgent.StampSample(ExecutionContext.GetWorld()->GetRealTimeSeconds());
		if (!VisualFragments.IsEmpty())
		{
			const auto& V = VisualFragments[EntityIndex];
			ReplicatedAgent.SetPresentation(V.Velocity, V.Flags, V.Health, V.Energy, V.Activity);
		}

		FEcoMassClientBubbleHandler& Bubble = BubbleInfo.GetSerializer().Bubble;
		const FMassReplicatedAgentHandle Handle = Bubble.AddAgent(ExecutionContext.GetEntity(EntityIndex), ReplicatedAgent);
		FEcoMassFastArrayItem& Item = Bubble.GetAgentItem(Handle);
		Item.LastObservedLOD = LODFragments[EntityIndex].LOD;
		Item.LastTransformCheckRealTime = ExecutionContext.GetWorld()->GetRealTimeSeconds();
		Item.ConfiguredUpdateInterval = ReplicationParams->UpdateInterval[Item.LastObservedLOD];
		++Bubble.GetReplicationStatsMutable().Adds;
#if !UE_BUILD_SHIPPING
		TraceSample(BubbleInfo, Item, TEXT("Add"), Item.LastTransformCheckRealTime, 0.0, true);
#endif
		return Handle;
	};

	auto ModifyEntity = [&](
		FMassExecutionContext& ExecutionContext,
		const int32 EntityIndex,
		const EMassLOD::Type LOD,
		const double RealTime,
		const FMassReplicatedAgentHandle Handle,
		const FMassClientHandle ClientHandle)
	{
		AEcoMassClientBubbleInfo& BubbleInfo =
			ReplicationSharedFragment->GetTypedClientBubbleInfoChecked<AEcoMassClientBubbleInfo>(ClientHandle);
		FEcoMassClientBubbleHandler& Bubble = BubbleInfo.GetSerializer().Bubble;

		FEcoMassFastArrayItem& Item = Bubble.GetAgentItem(Handle);
		FMassReplicatedAgentData& AgentData = ReplicatedAgentFragments[EntityIndex].AgentData;
		check(LOD < EMassLOD::Off && AgentData.Handle == Handle);
		const bool bHighPromotion = LOD == EMassLOD::High && Item.LastObservedLOD != EMassLOD::High;
		// The engine helper has already overwritten AgentData.LOD. Keep the previous
		// observed grade on the connection's item, including on gated callbacks.
		Item.LastObservedLOD = LOD;
		Item.ConfiguredUpdateInterval = ReplicationParams->UpdateInterval[LOD];
		FEcoMassReplicationLODStats& Stats = Bubble.GetReplicationStatsMutable().LOD[LOD];
		Stats.HighPromotions += bHighPromotion;

		// Persistent important state is examined every callback, before the movement gate.
		const bool bVisualChanged = UpdateVisualState(Item.Agent, EntityIndex, ExecutionContext);
		const bool bReset = Item.Agent.GetMovementDiscontinuityRevision() != DiscontinuityFragments[EntityIndex].Revision;
		const FEcoCreaturePresentationFragment* Presentation = VisualFragments.IsEmpty() ? nullptr : &VisualFragments[EntityIndex];
		const bool bPresentationPriority = Presentation && (Item.Agent.GetVisualFlags() != Presentation->Flags
			|| Item.Agent.GetHealth() != Presentation->Health || Item.Agent.GetEnergy() != Presentation->Energy || Item.Agent.GetActivity() != Presentation->Activity);
		const FEcoIdentityFragment& Identity = IdentityFragments[EntityIndex];
		const FEcoRegionFragment& Region = RegionFragments[EntityIndex];
		const bool bIdentityChanged = Item.Agent.GetStableAgentId() != Identity.StableAgentId
			|| Item.Agent.GetSpeciesId() != Identity.SpeciesId
			|| Item.Agent.GetRegionId() != Region.CurrentRegionId;
		const bool bPriority = bVisualChanged || bPresentationPriority || bReset || bIdentityChanged;
		const double CheckDelta = RealTime - AgentData.LastUpdateTime;
		const bool bClockReset = CheckDelta < 0.0;
		if (!bPriority && !bHighPromotion && !bClockReset && CheckDelta < Item.ConfiguredUpdateInterval)
		{
			++Stats.Gated;
			return;
		}
		++Stats.Checks;
		Stats.PriorityChecks += bPriority;
		// SyncFromMass copies this back into the current client's AgentsData map.
		// Advance even for unchanged transforms, without dirtying a timestamp alone.
		AgentData.LastUpdateTime = RealTime;
		Item.LastTransformCheckRealTime = RealTime;
		// Velocity-only changes follow the connection interval; flags/vitals bypass it.
		const bool bPresentationChanged = Presentation && Item.Agent.SetPresentation(
			Presentation->Velocity, Presentation->Flags, Presentation->Health, Presentation->Energy, Presentation->Activity);

		const FReplicatedAgentPositionYawData PreviousTransform = Item.Agent.GetReplicatedPositionYawData();
		if (bReset)
		{
			// A reset carries the exact current transform, even below dirty tolerance.
			PositionYawHandler.AddEntity(EntityIndex, Item.Agent.GetReplicatedPositionYawDataMutable());
			Item.Agent.SetMovementDiscontinuityRevision(DiscontinuityFragments[EntityIndex].Revision);
		}
		else
		{
			PositionYawHandler.ModifyEntity<FEcoMassFastArrayItem>(Handle, EntityIndex, Bubble.GetTransformHandlerMutable());
		}
		const auto& CurrentTransform = Item.Agent.GetReplicatedPositionYawData();
		const bool bMovementChanged = bReset || bIdentityChanged
			|| PreviousTransform.GetPosition() != CurrentTransform.GetPosition()
			|| PreviousTransform.GetYaw() != CurrentTransform.GetYaw();
		const bool bChanged = bPriority || bPresentationChanged || bMovementChanged;
		if (bIdentityChanged)
		{
			Item.Agent.SetStableAgentId(Identity.StableAgentId);
			Item.Agent.SetSpeciesId(Identity.SpeciesId);
			Item.Agent.SetRegionId(Region.CurrentRegionId);
		}
		if (bChanged)
		{
			if (bMovementChanged) Item.Agent.StampSample(RealTime);
			Bubble.MarkItemDirty(Item);
			++Stats.DirtySamples;
		}
#if !UE_BUILD_SHIPPING
		TraceSample(BubbleInfo, Item, bReset ? TEXT("Reset") : bIdentityChanged ? TEXT("IdentityOrRegion")
			: bVisualChanged ? TEXT("Visual") : bHighPromotion ? TEXT("HighPromotion")
			: bClockReset ? TEXT("ClockReset") : TEXT("Interval"), RealTime, CheckDelta, bChanged);
#endif
	};

	auto RemoveEntity = [&ReplicationSharedFragment](
		FMassExecutionContext&,
		const FMassReplicatedAgentHandle Handle,
		const FMassClientHandle ClientHandle)
	{
		AEcoMassClientBubbleInfo& BubbleInfo =
			ReplicationSharedFragment->GetTypedClientBubbleInfoChecked<AEcoMassClientBubbleInfo>(ClientHandle);
		FEcoMassClientBubbleHandler& Bubble = BubbleInfo.GetSerializer().Bubble;
#if !UE_BUILD_SHIPPING
		TraceSample(BubbleInfo, Bubble.GetAgentItem(Handle), TEXT("Remove"), BubbleInfo.GetWorld()->GetRealTimeSeconds(), 0.0, true);
#endif
		Bubble.RemoveAgentChecked(Handle);
		++Bubble.GetReplicationStatsMutable().Removes;
	};

	CalculateClientReplication<FEcoMassFastArrayItem>(Context, ReplicationContext, CacheViews, AddEntity, ModifyEntity, RemoveEntity);
#endif
}

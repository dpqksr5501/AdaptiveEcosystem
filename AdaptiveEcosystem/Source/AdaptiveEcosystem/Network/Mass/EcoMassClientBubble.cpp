// Copyright Epic Games, Inc. All Rights Reserved.

#include "Network/Mass/EcoMassClientBubble.h"

#include "AdaptiveEcosystem.h"
#include "Mass/EcoMassFragments.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "MassSpawnerSubsystem.h"
#include "Net/UnrealNetwork.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(EcoMassClientBubble)

#if UE_REPLICATION_COMPILE_CLIENT_CODE
void FEcoMassClientBubbleHandler::PostReplicatedAdd(const TArrayView<int32> AddedIndices, const int32 FinalSize)
{
	UMassSpawnerSubsystem* SpawnerSubsystem = Serializer->GetSpawnerSubsystem();
	check(SpawnerSubsystem);
	TArray<int32> ReadyIndices;
	for (const int32 Index : AddedIndices)
	{
		const FEcoMassFastArrayItem& Item = (*Agents)[Index];
		const FMassEntityTemplateID TemplateID = Item.Agent.GetTemplateID();
		if (SpawnerSubsystem->GetMassEntityTemplate(TemplateID))
		{
			ReadyIndices.Add(Index);
		}
		else
		{
			if (PendingAddReplicationIDs.IsEmpty())
			{
				PendingAddsStartTime = GetWorld()->GetRealTimeSeconds();
				bReportedMissingTemplates = false;
			}
			PendingAddReplicationIDs.Add(Item.ReplicationID);
			if (!WaitingTemplateIDs.Contains(TemplateID))
			{
				WaitingTemplateIDs.Add(TemplateID);
				UE_LOG(LogAdaptiveEcosystem, Warning,
					TEXT("Deferring Eco Mass proxies: template %s is not registered in client world %s. Waiting for the local Bootstrap EntityConfig."),
					*TemplateID.ToString(), *GetWorld()->GetPathName());
			}
		}
	}

	ApplyAddedAgents(ReadyIndices);
}

void FEcoMassClientBubbleHandler::ApplyAddedAgents(const TArrayView<int32> AddedIndices)
{
	if (AddedIndices.IsEmpty())
	{
		return;
	}

	auto AddRequirements = [this](FMassEntityQuery& Query)
	{
		TransformHandler.AddRequirementsForSpawnQuery(Query);
		Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadWrite);
		Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadWrite);
	};

	auto CacheViews = [this](FMassExecutionContext& Context)
	{
		TransformHandler.CacheFragmentViewsForSpawnQuery(Context);
		IdentityFragments = Context.GetMutableFragmentView<FEcoIdentityFragment>();
		RegionFragments = Context.GetMutableFragmentView<FEcoRegionFragment>();
	};

	auto SetSpawnedData = [this](const FMassEntityView&, const FReplicatedEcoMassAgent& Agent, const int32 EntityIndex)
	{
		TransformHandler.SetSpawnedEntityData(EntityIndex, Agent.GetReplicatedPositionYawData());

		FEcoIdentityFragment& Identity = IdentityFragments[EntityIndex];
		Identity.StableAgentId = Agent.GetStableAgentId();
		Identity.SpeciesId = Agent.GetSpeciesId();

		FEcoRegionFragment& Region = RegionFragments[EntityIndex];
		Region.CurrentRegionId = Agent.GetRegionId();
	};

	auto SetModifiedData = [this](const FMassEntityView& EntityView, const FReplicatedEcoMassAgent& Agent)
	{
		SetModifiedEntityData(EntityView, Agent);
	};

	PostReplicatedAddHelper(AddedIndices, AddRequirements, CacheViews, SetSpawnedData, SetModifiedData);

	TransformHandler.ClearFragmentViewsForSpawnQuery();
	IdentityFragments = TArrayView<FEcoIdentityFragment>();
	RegionFragments = TArrayView<FEcoRegionFragment>();
}

void FEcoMassClientBubbleHandler::PostReplicatedChange(const TArrayView<int32> ChangedIndices, const int32 FinalSize)
{
	TArray<int32> ReadyIndices;
	for (const int32 Index : ChangedIndices)
	{
		// The FastArray already contains the latest payload. An unspawned entry
		// must not enter the engine's change helper, which requires a valid entity.
		if (!PendingAddReplicationIDs.Contains((*Agents)[Index].ReplicationID))
		{
			ReadyIndices.Add(Index);
		}
	}

	auto SetModifiedData = [this](const FMassEntityView& EntityView, const FReplicatedEcoMassAgent& Agent)
	{
		SetModifiedEntityData(EntityView, Agent);
	};

	PostReplicatedChangeHelper(ReadyIndices, SetModifiedData);
}

void FEcoMassClientBubbleHandler::PreReplicatedRemove(const TArrayView<int32> RemovedIndices, const int32 FinalSize)
{
	TArray<int32> SpawnedIndices;
	for (const int32 Index : RemovedIndices)
	{
		// Cancel pending adds without asking Mass to destroy an entity that has
		// never been registered. The base handler still owns normal removals.
		if (PendingAddReplicationIDs.Remove((*Agents)[Index].ReplicationID) == 0)
		{
			SpawnedIndices.Add(Index);
		}
	}
	Super::PreReplicatedRemove(SpawnedIndices, FinalSize);
}

void FEcoMassClientBubbleHandler::RetryPendingAdds()
{
	// A retry runs from the bubble tick, unlike the initial network callback.
	// Never create entities while a Mass processing phase holds the manager.
	if (Serializer->GetEntityManagerChecked().IsProcessing())
	{
		return;
	}

	UMassSpawnerSubsystem* SpawnerSubsystem = Serializer->GetSpawnerSubsystem();
	check(SpawnerSubsystem);
	TArray<int32> ReadyIndices;
	for (int32 Index = 0; Index < Agents->Num(); ++Index)
	{
		const FEcoMassFastArrayItem& Item = (*Agents)[Index];
		if (PendingAddReplicationIDs.Contains(Item.ReplicationID)
			&& SpawnerSubsystem->GetMassEntityTemplate(Item.Agent.GetTemplateID()))
		{
			ReadyIndices.Add(Index);
			PendingAddReplicationIDs.Remove(Item.ReplicationID);
		}
	}
	ApplyAddedAgents(ReadyIndices);
	if (!ReadyIndices.IsEmpty())
	{
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("Resumed %d deferred Eco Mass proxy entries in world %s (%d still waiting)."),
			ReadyIndices.Num(), *GetWorld()->GetPathName(), PendingAddReplicationIDs.Num());
	}

	if (!PendingAddReplicationIDs.IsEmpty() && !bReportedMissingTemplates
		&& GetWorld()->GetRealTimeSeconds() - PendingAddsStartTime >= 5.0)
	{
		bReportedMissingTemplates = true;
		UE_LOG(LogAdaptiveEcosystem, Error,
			TEXT("%d Eco Mass proxy entries are still waiting for client templates in %s. Check the Bootstrap is loaded on this client and uses the same EntityConfig asset/TemplateID as the server. Pending entries will retry until removed."),
			PendingAddReplicationIDs.Num(), *GetWorld()->GetPathName());
	}
}

void FEcoMassClientBubbleHandler::SetModifiedEntityData(const FMassEntityView& EntityView, const FReplicatedEcoMassAgent& Agent) const
{
	TransformHandler.SetModifiedEntityData(EntityView, Agent.GetReplicatedPositionYawData());

	FEcoIdentityFragment& Identity = EntityView.GetFragmentData<FEcoIdentityFragment>();
	Identity.StableAgentId = Agent.GetStableAgentId();
	Identity.SpeciesId = Agent.GetSpeciesId();

	FEcoRegionFragment& Region = EntityView.GetFragmentData<FEcoRegionFragment>();
	Region.CurrentRegionId = Agent.GetRegionId();
}
#endif

void FEcoMassClientBubbleHandler::Tick(const float DeltaTime)
{
#if UE_REPLICATION_COMPILE_CLIENT_CODE
	if (GetWorld()->GetNetMode() == NM_Client)
	{
		if (!PendingAddReplicationIDs.IsEmpty())
		{
			RetryPendingAdds();
		}
		if (!PendingAddReplicationIDs.IsEmpty())
		{
			// The engine's debug validator assumes every received entry already
			// has an entity. Defer that validation while templates are pending,
			// but continue normal removal bookkeeping.
			UpdateAgentsToRemove();
			return;
		}
		WaitingTemplateIDs.Reset();
	}
#endif
	Super::Tick(DeltaTime);
}

void FEcoMassClientBubbleHandler::Reset()
{
#if UE_REPLICATION_COMPILE_CLIENT_CODE
	PendingAddReplicationIDs.Reset();
	WaitingTemplateIDs.Reset();
	PendingAddsStartTime = 0.0;
	bReportedMissingTemplates = false;
	IdentityFragments = {};
	RegionFragments = {};
	TransformHandler.ClearFragmentViewsForSpawnQuery();
#endif
	Super::Reset();
}

AEcoMassClientBubbleInfo::AEcoMassClientBubbleInfo(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer)
{
	Serializers.Add(&Serializer);
}

void AEcoMassClientBubbleInfo::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);

	FDoRepLifetimeParams Params;
	Params.bIsPushBased = true;
	DOREPLIFETIME_WITH_PARAMS_FAST(AEcoMassClientBubbleInfo, Serializer, Params);
}

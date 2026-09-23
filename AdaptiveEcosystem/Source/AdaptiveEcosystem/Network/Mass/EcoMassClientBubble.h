// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassClientBubbleHandler.h"
#include "MassClientBubbleInfoBase.h"
#include "MassClientBubbleSerializerBase.h"
#include "MassEntityView.h"
#include "MassReplicationTransformHandlers.h"
#include "Network/Mass/EcoMassReplicationTypes.h"
#include "EcoMassClientBubble.generated.h"

/** Applies one client's replicated bubble to that client's local proxy entities. */
class FEcoMassClientBubbleHandler : public TClientBubbleHandlerBase<FEcoMassFastArrayItem>
{
public:
	using Super = TClientBubbleHandlerBase<FEcoMassFastArrayItem>;
	using FTransformHandler = TMassClientBubbleTransformHandler<FEcoMassFastArrayItem>;

	FEcoMassClientBubbleHandler()
		: TransformHandler(*this)
	{
	}

#if UE_REPLICATION_COMPILE_SERVER_CODE
	FTransformHandler& GetTransformHandlerMutable() { return TransformHandler; }
#endif

protected:
	virtual void Tick(float DeltaTime) override;
	virtual void Reset() override;

#if UE_REPLICATION_COMPILE_CLIENT_CODE
	virtual void PreReplicatedRemove(TArrayView<int32> RemovedIndices, int32 FinalSize) override;
	virtual void PostReplicatedAdd(TArrayView<int32> AddedIndices, int32 FinalSize) override;
	virtual void PostReplicatedChange(TArrayView<int32> ChangedIndices, int32 FinalSize) override;

private:
	void ApplyAddedAgents(TArrayView<int32> AddedIndices);
	void RetryPendingAdds();
	void SetModifiedEntityData(const FMassEntityView& EntityView, const FReplicatedEcoMassAgent& Agent) const;

	// FastArray indices move when entries are removed. ReplicationID identifies
	// the exact pending entry; always read its latest payload from Agents on retry.
	TSet<int32> PendingAddReplicationIDs;
	TSet<FMassEntityTemplateID> WaitingTemplateIDs;
	double PendingAddsStartTime = 0.0;
	bool bReportedMissingTemplates = false;

	TArrayView<struct FEcoIdentityFragment> IdentityFragments;
	TArrayView<struct FEcoRegionFragment> RegionFragments;
#endif

	FTransformHandler TransformHandler;
};

/** Replicated FastArray owned by exactly one client bubble actor. */
USTRUCT()
struct FEcoMassClientBubbleSerializer : public FMassClientBubbleSerializerBase
{
	GENERATED_BODY()

	FEcoMassClientBubbleSerializer()
	{
		Bubble.Initialize(Agents, *this);
	}

	bool NetDeltaSerialize(FNetDeltaSerializeInfo& DeltaParams)
	{
		return FFastArraySerializer::FastArrayDeltaSerialize<FEcoMassFastArrayItem, FEcoMassClientBubbleSerializer>(Agents, DeltaParams, *this);
	}

	FEcoMassClientBubbleHandler Bubble;

private:
	UPROPERTY(Transient)
	TArray<FEcoMassFastArrayItem> Agents;
};

template<>
struct TStructOpsTypeTraits<FEcoMassClientBubbleSerializer> : public TStructOpsTypeTraitsBase2<FEcoMassClientBubbleSerializer>
{
	enum
	{
		WithNetDeltaSerializer = true,
		WithCopy = false
	};
};

/** Per-connection replicated actor instantiated and owned by MassReplication. */
UCLASS()
class ADAPTIVEECOSYSTEM_API AEcoMassClientBubbleInfo : public AMassClientBubbleInfoBase
{
	GENERATED_BODY()

public:
	AEcoMassClientBubbleInfo(const FObjectInitializer& ObjectInitializer);

	FEcoMassClientBubbleSerializer& GetSerializer() { return Serializer; }

protected:
	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

private:
	UPROPERTY(Replicated, Transient)
	FEcoMassClientBubbleSerializer Serializer;
};

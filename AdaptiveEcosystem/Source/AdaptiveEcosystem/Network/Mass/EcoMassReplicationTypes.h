// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassClientBubbleHandler.h"
#include "MassReplicationTransformHandlers.h"
#include "MassReplicationTypes.h"
#include "EcoMassReplicationTypes.generated.h"

/** Minimal transport payload for one relevant ecological Mass agent. */
USTRUCT()
struct FReplicatedEcoMassAgent : public FReplicatedAgentBase
{
	GENERATED_BODY()

	const FReplicatedAgentPositionYawData& GetReplicatedPositionYawData() const { return PositionYaw; }
	FReplicatedAgentPositionYawData& GetReplicatedPositionYawDataMutable() { return PositionYaw; }

	int64 GetStableAgentId() const { return StableAgentId; }
	void SetStableAgentId(const int64 InStableAgentId) { StableAgentId = InStableAgentId; }

	FName GetSpeciesId() const { return SpeciesId; }
	void SetSpeciesId(const FName InSpeciesId) { SpeciesId = InSpeciesId; }

	FName GetRegionId() const { return RegionId; }
	void SetRegionId(const FName InRegionId) { RegionId = InRegionId; }

private:
	UPROPERTY(Transient)
	FReplicatedAgentPositionYawData PositionYaw;

	/** Persistent gameplay identity. This is intentionally distinct from FMassNetworkID. */
	UPROPERTY(Transient)
	int64 StableAgentId = 0;

	UPROPERTY(Transient)
	FName SpeciesId = NAME_None;

	UPROPERTY(Transient)
	FName RegionId = NAME_None;
};

/** Fast-array entry used by one connection-specific client bubble. */
USTRUCT()
struct FEcoMassFastArrayItem : public FMassFastArrayItemBase
{
	GENERATED_BODY()

	FEcoMassFastArrayItem() = default;
	FEcoMassFastArrayItem(const FReplicatedEcoMassAgent& InAgent, const FMassReplicatedAgentHandle InHandle)
		: FMassFastArrayItemBase(InHandle)
		, Agent(InAgent)
	{
	}

	using FReplicatedAgentType = FReplicatedEcoMassAgent;

	UPROPERTY()
	FReplicatedEcoMassAgent Agent;
};

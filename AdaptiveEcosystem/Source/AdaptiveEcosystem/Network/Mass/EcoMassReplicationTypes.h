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
	const FVector& GetVelocity() const { return Velocity; }
	uint8 GetVisualFlags() const { return VisualFlags; }
	uint8 GetHealth() const { return Health; }
	uint8 GetEnergy() const { return Energy; }
	bool SetPresentation(const FVector& InVelocity, uint8 InFlags, uint8 InHealth, uint8 InEnergy)
	{
		if (Velocity.Equals(InVelocity, 1.0f) && VisualFlags == InFlags && Health == InHealth && Energy == InEnergy) return false;
		Velocity = InVelocity; VisualFlags = InFlags; Health = InHealth; Energy = InEnergy; return true;
	}

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
	UPROPERTY(Transient) FVector_NetQuantize10 Velocity = FVector::ZeroVector;
	UPROPERTY(Transient) uint8 VisualFlags = 1;
	UPROPERTY(Transient) uint8 Health = 255;
	UPROPERTY(Transient) uint8 Energy = 255;
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

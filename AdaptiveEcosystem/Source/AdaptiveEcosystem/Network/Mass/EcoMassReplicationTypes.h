// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassClientBubbleHandler.h"
#include "MassReplicationTransformHandlers.h"
#include "MassReplicationTypes.h"
#include "Core/EcoRepresentationTypes.h"
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
	uint8 GetActivity() const { return Activity; }
	bool SetPresentation(const FVector& InVelocity, uint8 InFlags, uint8 InHealth, uint8 InEnergy, uint8 InActivity = 0)
	{
		if (Velocity.Equals(InVelocity, 1.0f) && VisualFlags == InFlags && Health == InHealth && Energy == InEnergy && Activity == InActivity) return false;
		Velocity = InVelocity; VisualFlags = InFlags; Health = InHealth; Energy = InEnergy; Activity = InActivity;
		++VisualRevision;
		return true;
	}

	bool SetVisualState(float InHealth, float InEnergy, EEcoVisualLifeState State)
	{
		const uint8 NewHealth = EcoRepresentation::QuantizeUnit(InHealth);
		const uint8 NewEnergy = EcoRepresentation::QuantizeUnit(InEnergy);
		if (HealthByte == NewHealth && EnergyByte == NewEnergy && LifeState == State) return false;
		HealthByte = NewHealth;
		EnergyByte = NewEnergy;
		LifeState = State;
		++VisualRevision;
		return true;
	}
	uint32 GetMovementDiscontinuityRevision() const { return MovementDiscontinuityRevision; }
	void SetMovementDiscontinuityRevision(uint32 Revision) { MovementDiscontinuityRevision = Revision; }
	void StampSample(double ServerRealTimeSeconds)
	{
		ServerSampleRealTimeSeconds = ServerRealTimeSeconds;
		++SampleSequence;
	}
	FEcoRepresentationSnapshot MakeRepresentationSnapshot() const
	{
		FEcoRepresentationSnapshot Result;
		Result.StableAgentId = StableAgentId;
		Result.SpeciesId = SpeciesId;
		Result.RegionId = RegionId;
		Result.Location = PositionYaw.GetPosition();
		Result.Rotation = FRotator(0.0f, FMath::RadiansToDegrees(PositionYaw.GetYaw()), 0.0f);
		Result.NormalizedHealth = HealthByte / 255.0f;
		Result.NormalizedEnergy = EnergyByte / 255.0f;
		Result.LifeState = LifeState;
		Result.ServerSampleRealTimeSeconds = ServerSampleRealTimeSeconds;
		Result.SampleSequence = SampleSequence;
		Result.VisualRevision = VisualRevision;
		Result.MovementDiscontinuityRevision = MovementDiscontinuityRevision;
		return Result;
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

	UPROPERTY(Transient)
	uint8 HealthByte = 255;
	UPROPERTY(Transient)
	uint8 EnergyByte = 255;
	UPROPERTY(Transient)
	EEcoVisualLifeState LifeState = EEcoVisualLifeState::Alive;
	UPROPERTY(Transient)
	double ServerSampleRealTimeSeconds = 0.0;
	UPROPERTY(Transient)
	uint32 SampleSequence = 0;
	UPROPERTY(Transient)
	uint32 VisualRevision = 0;
	UPROPERTY(Transient)
	uint32 MovementDiscontinuityRevision = 0;
	UPROPERTY(Transient) FVector_NetQuantize10 Velocity = FVector::ZeroVector;
	UPROPERTY(Transient) uint8 VisualFlags = 1;
	UPROPERTY(Transient) uint8 Health = 255;
	UPROPERTY(Transient) uint8 Energy = 255;
	UPROPERTY(Transient) uint8 Activity = 0;
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

	// Server-local scheduling diagnostics. Not UPROPERTY: never part of the payload.
	// Lives with this connection's entry, so removal/re-entry cannot retain old LOD state.
	EMassLOD::Type LastObservedLOD = EMassLOD::Off;
	double LastTransformCheckRealTime = 0.0;
	float ConfiguredUpdateInterval = 0.0f;
};

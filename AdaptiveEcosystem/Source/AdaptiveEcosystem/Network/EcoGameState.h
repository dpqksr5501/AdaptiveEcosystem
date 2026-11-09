// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "Network/EcoMatchTypes.h"
#include "Network/EcologyNetworkTypes.h"
#include "Network/EcoClockSchedule.h"
#include "EcoGameState.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnEcoAuthorityStateChanged);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnEcoClockPhaseChanged, FEcoServerTimeSnapshot, Time, bool, bInitialState);

/**
 * Replicated, low-frequency summary of the authoritative world.
 *
 * Per-agent Mass data deliberately does not live here. It is transported by
 * MassReplication client bubbles so relevance and update frequency can be
 * evaluated independently for every connection.
 */
UCLASS(BlueprintType)
class ADAPTIVEECOSYSTEM_API AEcoGameState : public AGameStateBase
{
	GENERATED_BODY()

public:
	AEcoGameState();
	virtual void Tick(float DeltaSeconds) override;
	virtual void OnRep_ReplicatedWorldTimeSecondsDouble() override;
	/** False before server time/schedule arrives or after lookahead expires. Read-only on every world. */
	UFUNCTION(BlueprintPure, Category="Ecology|Time")
	bool GetSynchronizedClock(FEcoServerTimeSnapshot& Time) const;
	/** Presentation notification; initial/late join state is not a historical gameplay event. */
	UPROPERTY(BlueprintAssignable, Category="Ecology|Time")
	FOnEcoClockPhaseChanged OnClockPhaseChanged;
	/** Empty test levels share a timeline without starting resource/population simulation. */
	void EnablePresentationClock();

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	/** Initializes a new authoritative world instance. Server only. */
	void InitializeAuthorityState(int32 InWorldEpoch, int32 InMaxPlayers);

	/** Changes the coarse world lifecycle. Server only. */
	void SetWorldPhase(EEcoWorldPhase InWorldPhase);

	/** Updates the active human player count. Server only. */
	void SetConnectedPlayerCount(int32 InConnectedPlayerCount);

	/** Reports whether the Mass network template and initial agents are ready. Server only. */
	void SetMassReplicationReady(bool bInMassReplicationReady);
	/** Transport only: accepts a completed authority snapshot, executes no simulation rules. */
	void PublishEcologySummary(const FEcoCompletedWorldSummary& Summary);
	UFUNCTION(BlueprintPure, Category="Ecology|Summary")
	FEcoCompletedWorldSummary GetEcologySummary() const { return EcologySummary; }
	/** Read only the relevant row, without copying the whole regional/species summary. */
	const FReplicatedRegionSummary* FindCompletedRegion(FName RegionId) const
	{
		return EcologySummary.Regions.FindByPredicate([RegionId](const auto& Row) { return Row.RegionId == RegionId; });
	}

	UFUNCTION(BlueprintPure, Category = "Ecology|Match")
	FGuid GetMatchInstanceId() const { return MatchInstanceId; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Match")
	int32 GetWorldEpoch() const { return WorldEpoch; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Match")
	EEcoWorldPhase GetWorldPhase() const { return WorldPhase; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Match")
	int32 GetMaxPlayers() const { return MaxPlayers; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Match")
	int32 GetConnectedPlayerCount() const { return ConnectedPlayerCount; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Match")
	int32 GetStateRevision() const { return StateRevision; }

	UFUNCTION(BlueprintPure, Category = "Ecology|Match")
	bool IsMassReplicationReady() const { return bMassReplicationReady; }

	UPROPERTY(BlueprintAssignable, Category = "Ecology|Match")
	FOnEcoAuthorityStateChanged OnAuthorityStateChanged;

protected:
	UFUNCTION()
	void OnRep_AuthorityState();

private:
	UPROPERTY(Replicated) FEcoClockSchedule ClockSchedule;
	bool bPresentationClock = false;
	bool bReceivedServerTime = false;
	double PresentationOrigin = 0;
	double LastClockPublication = -1;
	FEcoServerTimeSnapshot LastPresentedClock;
	void PublishClockSchedule();
	void CommitAuthorityChange();

	UPROPERTY(ReplicatedUsing = OnRep_AuthorityState, VisibleInstanceOnly, Category = "Ecology|Match")
	FGuid MatchInstanceId;

	UPROPERTY(ReplicatedUsing = OnRep_AuthorityState, VisibleInstanceOnly, Category = "Ecology|Match")
	int32 WorldEpoch = 0;

	UPROPERTY(ReplicatedUsing = OnRep_AuthorityState, VisibleInstanceOnly, Category = "Ecology|Match")
	EEcoWorldPhase WorldPhase = EEcoWorldPhase::Initializing;

	UPROPERTY(ReplicatedUsing = OnRep_AuthorityState, VisibleInstanceOnly, Category = "Ecology|Match")
	int32 MaxPlayers = 0;

	UPROPERTY(ReplicatedUsing = OnRep_AuthorityState, VisibleInstanceOnly, Category = "Ecology|Match")
	int32 ConnectedPlayerCount = 0;

	UPROPERTY(ReplicatedUsing = OnRep_AuthorityState, VisibleInstanceOnly, Category = "Ecology|Match")
	int32 StateRevision = 0;

	UPROPERTY(ReplicatedUsing = OnRep_AuthorityState, VisibleInstanceOnly, Category = "Ecology|Match")
	bool bMassReplicationReady = false;
	UPROPERTY(ReplicatedUsing=OnRep_AuthorityState, VisibleInstanceOnly, Category="Ecology|Summary")
	FEcoCompletedWorldSummary EcologySummary;
};

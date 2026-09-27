// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameStateBase.h"
#include "Network/EcoMatchTypes.h"
#include "EcoGameState.generated.h"

DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnEcoAuthorityStateChanged);

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

	virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;

	/** Initializes a new authoritative world instance. Server only. */
	void InitializeAuthorityState(int32 InWorldEpoch, int32 InMaxPlayers);

	/** Changes the coarse world lifecycle. Server only. */
	void SetWorldPhase(EEcoWorldPhase InWorldPhase);

	/** Updates the active human player count. Server only. */
	void SetConnectedPlayerCount(int32 InConnectedPlayerCount);

	/** Reports whether the Mass network template and initial agents are ready. Server only. */
	void SetMassReplicationReady(bool bInMassReplicationReady);

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
};

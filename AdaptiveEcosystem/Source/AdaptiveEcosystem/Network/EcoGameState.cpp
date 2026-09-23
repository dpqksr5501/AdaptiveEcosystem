// Copyright Epic Games, Inc. All Rights Reserved.

#include "Network/EcoGameState.h"

#include "Net/UnrealNetwork.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(EcoGameState)

AEcoGameState::AEcoGameState()
{
	bReplicates = true;
}

void AEcoGameState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);

	DOREPLIFETIME(AEcoGameState, MatchInstanceId);
	DOREPLIFETIME(AEcoGameState, WorldEpoch);
	DOREPLIFETIME(AEcoGameState, WorldPhase);
	DOREPLIFETIME(AEcoGameState, MaxPlayers);
	DOREPLIFETIME(AEcoGameState, ConnectedPlayerCount);
	DOREPLIFETIME(AEcoGameState, StateRevision);
	DOREPLIFETIME(AEcoGameState, bMassReplicationReady);
}

void AEcoGameState::InitializeAuthorityState(const int32 InWorldEpoch, const int32 InMaxPlayers)
{
	if (!HasAuthority())
	{
		return;
	}

	MatchInstanceId = FGuid::NewGuid();
	WorldEpoch = FMath::Max(1, InWorldEpoch);
	MaxPlayers = FMath::Max(1, InMaxPlayers);
	ConnectedPlayerCount = 0;
	WorldPhase = EEcoWorldPhase::WaitingForPlayers;
	bMassReplicationReady = false;
	CommitAuthorityChange();
}

void AEcoGameState::SetWorldPhase(const EEcoWorldPhase InWorldPhase)
{
	if (HasAuthority() && WorldPhase != InWorldPhase)
	{
		WorldPhase = InWorldPhase;
		CommitAuthorityChange();
	}
}

void AEcoGameState::SetConnectedPlayerCount(const int32 InConnectedPlayerCount)
{
	const int32 SanitizedCount = FMath::Max(0, InConnectedPlayerCount);
	if (HasAuthority() && ConnectedPlayerCount != SanitizedCount)
	{
		ConnectedPlayerCount = SanitizedCount;
		CommitAuthorityChange();
	}
}

void AEcoGameState::SetMassReplicationReady(const bool bInMassReplicationReady)
{
	if (HasAuthority() && bMassReplicationReady != bInMassReplicationReady)
	{
		bMassReplicationReady = bInMassReplicationReady;
		CommitAuthorityChange();
	}
}

void AEcoGameState::OnRep_AuthorityState()
{
	OnAuthorityStateChanged.Broadcast();
}

void AEcoGameState::CommitAuthorityChange()
{
	check(HasAuthority());
	++StateRevision;
	ForceNetUpdate();
	OnAuthorityStateChanged.Broadcast();
}

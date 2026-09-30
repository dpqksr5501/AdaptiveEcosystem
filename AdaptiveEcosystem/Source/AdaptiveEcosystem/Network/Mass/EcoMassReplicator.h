// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassReplicationProcessor.h"
#include "EcoMassReplicator.generated.h"

/** Server-only adapter from authoritative ecological fragments to client bubbles. */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoMassReplicator : public UMassReplicatorBase
{
	GENERATED_BODY()

public:
	virtual void AddRequirements(FMassEntityQuery& EntityQuery) override;
	virtual void ProcessClientReplication(FMassExecutionContext& Context, FMassReplicationContext& ReplicationContext) override;
};

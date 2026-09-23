// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "MassReplicationTypes.h"
#include "MassSubsystemBase.h"
#include "EcoMassNetworkSubsystem.generated.h"

class UMassReplicationSubsystem;

/**
 * World-scoped owner of the ecological Mass replication registration.
 *
 * MassReplication does not discover custom client bubble classes automatically.
 * This subsystem registers the ecological bubble during WorldSubsystem
 * PostInitialize, before actors can build Mass entity templates in BeginPlay.
 */
UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoMassNetworkSubsystem : public UMassSubsystemBase
{
	GENERATED_BODY()

public:
	/** True after this world's custom bubble class has been registered successfully. */
	bool IsBubbleInfoClassRegistered() const;

protected:
	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void PostInitialize() override;
	virtual void Deinitialize() override;

private:
	UPROPERTY(Transient)
	TObjectPtr<UMassReplicationSubsystem> ReplicationSubsystem;

	FMassBubbleInfoClassHandle BubbleInfoClassHandle;
};

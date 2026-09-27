// Copyright Epic Games, Inc. All Rights Reserved.

#include "Mass/EcoMassNetworkSubsystem.h"

#include "AdaptiveEcosystem.h"
#include "Engine/World.h"
#include "MassReplicationSubsystem.h"
#include "Network/Mass/EcoMassClientBubble.h"

#include UE_INLINE_GENERATED_CPP_BY_NAME(EcoMassNetworkSubsystem)

void UEcoMassNetworkSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);

	// Establish a deterministic initialization dependency. The bubble registry is
	// owned by UMassReplicationSubsystem and exists independently in every World.
	ReplicationSubsystem = Collection.InitializeDependency<UMassReplicationSubsystem>();

	// Keeps registration correct if this subsystem is ever created after the
	// normal WorldSubsystem initialization pass.
	HandleLateCreation();
}

void UEcoMassNetworkSubsystem::PostInitialize()
{
	Super::PostInitialize();

	if (!ensureMsgf(ReplicationSubsystem,
		TEXT("Eco Mass networking requires UMassReplicationSubsystem in every game world.")))
	{
		return;
	}

	BubbleInfoClassHandle = ReplicationSubsystem->RegisterBubbleInfoClass(AEcoMassClientBubbleInfo::StaticClass());
	if (ensureMsgf(BubbleInfoClassHandle.IsValid(),
		TEXT("Failed to register AEcoMassClientBubbleInfo with UMassReplicationSubsystem.")))
	{
		UE_LOG(LogAdaptiveEcosystem, Log,
			TEXT("Registered Eco Mass client bubble for world %s (NetMode: %d)."),
			*GetNameSafe(GetWorld()),
			GetWorld() ? static_cast<int32>(GetWorld()->GetNetMode()) : INDEX_NONE);
	}
}

void UEcoMassNetworkSubsystem::Deinitialize()
{
	BubbleInfoClassHandle.Invalidate();
	ReplicationSubsystem = nullptr;

	Super::Deinitialize();
}

bool UEcoMassNetworkSubsystem::IsBubbleInfoClassRegistered() const
{
	return ReplicationSubsystem
		&& BubbleInfoClassHandle.IsValid()
		&& ReplicationSubsystem->IsBubbleClassHandleValid(BubbleInfoClassHandle);
}

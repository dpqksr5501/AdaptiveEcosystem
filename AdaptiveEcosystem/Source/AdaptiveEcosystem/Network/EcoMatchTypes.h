// Copyright Epic Games, Inc. All Rights Reserved.

#pragma once

#include "CoreMinimal.h"
#include "EcoMatchTypes.generated.h"

/** Coarse authoritative world lifecycle replicated to every connected client. */
UENUM(BlueprintType)
enum class EEcoWorldPhase : uint8
{
	Initializing,
	WaitingForPlayers,
	BootstrappingMass,
	Running,
	Ending
};

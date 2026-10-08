#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "Creature/Audio/EcoFootstepCadence.h"
#include "EcoCreatureRuntimeTypes.generated.h"

/** Opt-in networked creature path. Never attached to the M3 Box or legacy demo. */
USTRUCT()
struct FEcoIntegratedCreatureTag : public FMassTag { GENERATED_BODY() };

/** Authority-only step history. Audio playback has an independent local cadence. */
USTRUCT()
struct FEcoCreatureFootstepFragment : public FMassFragment
{
    GENERATED_BODY()
    FEcoFootstepCadence Cadence;
};

/** Read-only presentation payload on clients; no client vitals or policy simulation. */
USTRUCT()
struct FEcoCreaturePresentationFragment : public FMassFragment
{
	GENERATED_BODY()
	FVector Velocity = FVector::ZeroVector;
	uint8 Flags = 1; // alive=1, eating=2, pursuing=4, vitals-known=8
	uint8 Health = 255;
	uint8 Energy = 255;
};

USTRUCT()
struct FEcoCreatureLifecycleFragment : public FMassFragment
{
	GENERATED_BODY()
	double DeathTime = -1.0;
	bool bPursuing = false;
	bool bPredated = false;
	double NextWanderTime = 0.0;
};

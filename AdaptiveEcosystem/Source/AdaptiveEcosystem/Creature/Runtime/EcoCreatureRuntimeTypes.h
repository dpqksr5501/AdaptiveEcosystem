#pragma once

#include "CoreMinimal.h"
#include "MassEntityTypes.h"
#include "Creature/Audio/EcoFootstepCadence.h"
#include "Core/EcoSurvivalTypes.h"
#include "AI/Social/Senses/EcoSensoryTypes.h"
#include "EcoCreatureRuntimeTypes.generated.h"

/** Opt-in networked creature path. Never attached to the M3 Box or legacy demo. */
USTRUCT()
struct FEcoIntegratedCreatureTag : public FMassTag { GENERATED_BODY() };

/** Immutable per-agent adapter, authored by the coordinator at spawn. Never replicated. */
USTRUCT()
struct FEcoCreatureSurvivalFragment : public FMassFragment
{
	GENERATED_BODY()
	FEcoSurvivalSettings Settings;
	float EnergyPerPredation = 0.0f;
};

/** Authority-only step history. Audio playback has an independent local cadence. */
USTRUCT()
struct FEcoCreatureFootstepFragment : public FMassFragment
{
    GENERATED_BODY()
    FEcoFootstepCadence Cadence;
};

/** Presentation evidence is independent of policy observations and never steers a Mass entity. */
USTRUCT()
struct FEcoCreatureCueFragment : public FMassFragment
{
    GENERATED_BODY()
    FEcoSensoryStateFragment Memory;
    double NextScan = 0;
    int16 FocusYaw = 0;
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
	uint8 Activity = 0;
	uint8 BodyScale = 128; // scale = byte / 128; authority computes from genome + age
	int16 FocusYaw = 0;
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

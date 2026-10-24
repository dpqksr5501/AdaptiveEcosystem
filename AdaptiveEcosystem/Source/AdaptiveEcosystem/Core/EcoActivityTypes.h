#pragma once
#include "CoreMinimal.h"
#include "EcoActivityTypes.generated.h"
/** Stable presentation codes; append new values without reordering shipped values. */
UENUM(BlueprintType)
enum class EEcoSpeciesActivity : uint8
{ Hold, Wander, Forage, Graze, Rest, Regroup, Flee, Recover, ShelterTravel, ShelterHold, Travel, Search, Pursue, Attack, Eat, Freeze, Sleep, Stalk, Pounce, Exhaust,
  AlertGraze, WeakTravel, SatedRest, Curious, Vigilant, Investigate };

#pragma once

#include "CoreMinimal.h"

class UWorld;
struct FEcoFaunaPreyRule;
struct FEcoFaunaSpecies;
struct FEcoVitalsFragment;
namespace EcoLifeV3 { struct FIndividual; }

namespace EcoFaunaDecision
{
    bool FitsFaunaPrey(const FEcoFaunaPreyRule& Rule, const FEcoFaunaSpecies& Hunter,
        const FEcoFaunaSpecies& Prey, const EcoLifeV3::FIndividual& HunterLife,
        const EcoLifeV3::FIndividual& PreyLife, const FEcoVitalsFragment& Health, double Now);
    bool HasClearSight(const UWorld& World, const FVector& Start, const FVector& End,
        float EyeHeight = 35.f, float TargetHeight = 35.f);
}

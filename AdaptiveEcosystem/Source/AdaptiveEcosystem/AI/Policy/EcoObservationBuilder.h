#pragma once
#include "AI/Policy/EcoPolicyContracts.h"
struct FEcoSteeringGeometryFragment;
struct FEcoVitalsFragment;
class IEcoWorldFoodProvider;
class IEcoWorldCoverProvider;
class UEcoRegionPredationSubsystem;
namespace EcoObservation
{
    // Shared encoder: comparison controllers must receive the same V1 values as PPO.
    FEcoPolicyObservationV1 Build(const FVector& Position,const FEcoSteeringGeometryFragment& Geometry,
        const FEcoVitalsFragment& Vitals,const IEcoWorldFoodProvider* Food,const IEcoWorldCoverProvider* Cover,
        const UEcoRegionPredationSubsystem* Predation,bool GlobalHistory);
}

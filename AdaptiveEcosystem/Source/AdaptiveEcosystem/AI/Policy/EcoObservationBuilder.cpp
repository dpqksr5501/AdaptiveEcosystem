#include "AI/Policy/EcoObservationBuilder.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoBehaviorConfig.h"
#include "AI/Policy/EcoWorldProviders.h"
#include "AI/Policy/EcoRegionPredationSubsystem.h"
#include "Mass/EcoMassFragments.h"
FEcoPolicyObservationV1 EcoObservation::Build(const FVector& Position,const FEcoSteeringGeometryFragment& G,
    const FEcoVitalsFragment& V,const IEcoWorldFoodProvider* Food,const IEcoWorldCoverProvider* Cover,
    const UEcoRegionPredationSubsystem* Predation,bool GlobalHistory)
{
    FEcoPolicyObservationV1 O;
    O.FoodDensity=Food?FMath::Clamp(Food->GetFoodDensity(Position,EcoBehaviorConfig::SeeRadiusCm),0.f,1.f):0;
    O.PredatorCount=FMath::Clamp(float(G.PredatorCount)/EcoBehaviorConfig::ObsPredCountNorm,0.f,1.f);
    O.PredatorDistance=FMath::Clamp(G.DistPredMin/EcoBehaviorConfig::SeeRadiusCm,0.f,1.f);
    O.ConspecificCount=FMath::Clamp(float(G.KinCount)/EcoBehaviorConfig::ObsKinCountNorm,0.f,1.f);
    O.Energy=FMath::Clamp(V.Energy/FMath::Max(V.MaxEnergy,KINDA_SMALL_NUMBER),0.f,1.f);
    const float Regional=Food?Food->GetRecentPredation(Position):-1;
    O.RecentPredation=GlobalHistory&&Predation?Predation->GetGlobal():Regional>=0?FMath::Clamp(Regional,0.f,1.f):(Predation?Predation->Get(Position):0);
    O.CoverDistance=Cover?FMath::Clamp(Cover->GetCoverDistance(Position)/EcoBehaviorConfig::ObsCoverNormCm,0.f,1.f):1;
    return O;
}

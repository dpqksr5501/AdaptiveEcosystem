#include "Creature/Runtime/EcoCreatureMovement.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"

bool EcoCreatureMovement::ConstrainStep(UWorld& World, FName RegionId, bool bTraveling,
    const FVector& Position, FVector& Destination)
{
    if (Position.ContainsNaN() || Destination.ContainsNaN()) return false;
    const auto* Regions = World.GetSubsystem<UEcologyWorldSubsystem>();
    const auto* Region = Regions ? Regions->GetRegion(RegionId) : nullptr;
    if (!Region || (!bTraveling && !Region->ContainsPosition(Destination))) return false;
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoCreatureStep), false);
    const FVector Lift(0,0,65);
    if (World.SweepSingleByChannel(Hit, Position + Lift, Destination + Lift, FQuat::Identity,
        ECC_WorldStatic, FCollisionShape::MakeSphere(30.f), Params)) return false;
    if (!World.LineTraceSingleByChannel(Hit, Destination + FVector(0,0,200), Destination - FVector(0,0,300), ECC_WorldStatic, Params)
        || Hit.ImpactNormal.Z < 0.65f) return false;
    Destination.Z = Hit.ImpactPoint.Z;
    return true;
}

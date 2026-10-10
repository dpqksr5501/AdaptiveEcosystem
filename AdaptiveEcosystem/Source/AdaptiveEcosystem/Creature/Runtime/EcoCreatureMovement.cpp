#include "Creature/Runtime/EcoCreatureMovement.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "EngineUtils.h"
#include "NavModifierVolume.h"
#include "NavAreas/NavArea_Null.h"

bool EcoCreatureMovement::CrossesExcludedArea(UWorld& World, const FVector& Start, const FVector& End)
{
    for (TActorIterator<ANavModifierVolume> It(&World); It; ++It)
    {
        const UClass* Area = It->GetAreaClass();
        if (Area && Area->IsChildOf(UNavArea_Null::StaticClass()) && !It->GetAreaClassToReplace()
            && FMath::LineBoxIntersection(It->GetNavigationBounds().ExpandBy(30.0), Start, End, End - Start)) return true;
    }
    return false;
}

bool EcoCreatureMovement::ProjectSpawnPoint(UWorld& World, const FVector& Hint, FVector& OutGround)
{
    if (Hint.ContainsNaN()) return false;
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoCreatureSpawnGround), false);
    if (!World.LineTraceSingleByChannel(Hit, Hint + FVector(0,0,5000), Hint - FVector(0,0,20000), ECC_WorldStatic, Params)
        || Hit.ImpactNormal.Z < 0.65f) return false;
    const FVector Ground = Hit.ImpactPoint;
    if (CrossesExcludedArea(World, Ground, Ground)
        || World.OverlapBlockingTestByChannel(Ground + FVector(0,0,65), FQuat::Identity,
            ECC_WorldStatic, FCollisionShape::MakeSphere(30.0f), Params)) return false;
    OutGround = Ground;
    return true;
}

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
    if ((!bTraveling && !Region->ContainsPosition(Destination)) || CrossesExcludedArea(World, Position, Destination)) return false;
    return true;
}

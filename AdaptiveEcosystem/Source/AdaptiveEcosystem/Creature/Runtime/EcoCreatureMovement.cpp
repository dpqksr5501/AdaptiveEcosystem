#include "Creature/Runtime/EcoCreatureMovement.h"
#include "World/EcoVegetationField.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
#include "Components/BoxComponent.h"
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
    if (!World.LineTraceSingleByObjectType(Hit, Hint + FVector(0,0,5000), Hint - FVector(0,0,20000), FCollisionObjectQueryParams(ECC_WorldStatic), Params)
        || Hit.ImpactNormal.Z < 0.65f) return false;
    const FVector Ground = Hit.ImpactPoint;
    if (CrossesExcludedArea(World, Ground, Ground)
        || World.OverlapBlockingTestByChannel(Ground + FVector(0,0,65), FQuat::Identity,
            ECC_WorldStatic, FCollisionShape::MakeSphere(30.0f), Params)) return false;
    OutGround = Ground;
    return true;
}

bool EcoCreatureMovement::ConstrainStep(UWorld& World, FName RegionId, bool bTraveling,
    const FVector& Position, FVector& Destination, float BodyRadiusCm,float MinGroundNormalZ)
{
    if (Position.ContainsNaN() || Destination.ContainsNaN()||!FMath::IsFinite(BodyRadiusCm)||BodyRadiusCm<20||BodyRadiusCm>40) return false;
    const auto* Regions = World.GetSubsystem<UEcologyWorldSubsystem>();
    const auto* Region = Regions ? Regions->GetRegion(RegionId) : nullptr;
    if (!Region || (!bTraveling && !Region->ContainsPosition(Destination))) return false;
    return ConstrainGroundStep(World,Position,Destination,BodyRadiusCm,MinGroundNormalZ)
        &&(bTraveling||Region->ContainsPosition(Destination));
}

bool EcoCreatureMovement::ConstrainGroundStep(UWorld& World,const FVector& Position,FVector& Destination,
    float BodyRadiusCm,float MinGroundNormalZ,float SweepHeightCm,float MaxRiseCm)
{
    if(Position.ContainsNaN()||Destination.ContainsNaN()||!FMath::IsFinite(BodyRadiusCm)||BodyRadiusCm<1||BodyRadiusCm>120
        ||!FMath::IsFinite(SweepHeightCm)||SweepHeightCm<0||!FMath::IsFinite(MaxRiseCm)
        ||!FMath::IsFinite(MinGroundNormalZ)||MinGroundNormalZ<.65f||MinGroundNormalZ>1)return false;
    FHitResult Hit;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoCreatureStep), false);
    const FVector Lift(0,0,SweepHeightCm > 0.f ? FMath::Max(BodyRadiusCm + 1.f, SweepHeightCm)
        : FMath::Max(65.f, BodyRadiusCm + 35.f));
    if (World.SweepSingleByChannel(Hit, Position + Lift, Destination + Lift, FQuat::Identity,
        ECC_WorldStatic, FCollisionShape::MakeSphere(BodyRadiusCm), Params)) return false;
    const FVector ProbeStart(Destination.X, Destination.Y, MaxRiseCm < 0 ? Destination.Z + 200. : Position.Z + MaxRiseCm + 1.);
    if (!World.LineTraceSingleByObjectType(Hit, ProbeStart, Destination - FVector(0,0,300), FCollisionObjectQueryParams(ECC_WorldStatic), Params)
        || Hit.ImpactNormal.Z < MinGroundNormalZ) return false;
    Destination.Z = Hit.ImpactPoint.Z;
    if (CrossesExcludedArea(World, Position, Destination)) return false;
    return true;
}
bool EcoCreatureMovement::IsWadeableGround(UWorld& World,const FVector& Ground,float MaxDepthCm)
{
    if(Ground.ContainsNaN()||!FMath::IsFinite(MaxDepthCm)||MaxDepthCm<0)return false;
    for(TActorIterator<AEcoVegetationHabitat> It(&World);It;++It){
        if(!It->bConnectedFreshWater||!It->ContainsGround(Ground))continue;
        if(!It->IsValidHabitat()||It->GetWaterLevelZ()-Ground.Z>MaxDepthCm)return false;
    }
    return true;
}

bool EcoCreatureMovement::IsWaterSurfaceCollision(const AActor* Actor)
{
    static const FName WaterBodyClass(TEXT("WaterBody"));
    for (const UClass* Class = Actor ? Actor->GetClass() : nullptr; Class; Class = Class->GetSuperClass())
    {
        if (Class->GetFName() == WaterBodyClass) return true;
    }
    return false;
}

bool EcoCreatureMovement::HasClearWaterSight(const UWorld& World, const FVector& Start, const FVector& End)
{
    FCollisionQueryParams Query(SCENE_QUERY_STAT(EcoFaunaWaterSight), false);
    FHitResult Hit;
    while (World.LineTraceSingleByObjectType(Hit, Start, End, FCollisionObjectQueryParams(ECC_WorldStatic), Query))
    {
        const AActor* Actor = Hit.GetActor();
        if (!IsWaterSurfaceCollision(Actor)) return false;
        Query.AddIgnoredActor(Actor);
    }
    return true;
}

bool EcoCreatureMovement::ProbeFaunaWaterColumn(UWorld& World, FName RegionId, const FVector& Point, FFaunaWaterColumn& Out,
    double SimulationSeconds, float Rainfall)
{
    if (Point.ContainsNaN()) return false;
    const AEcoVegetationHabitat* Source = nullptr;
    double Surface = 0.;
    for (TActorIterator<AEcoVegetationHabitat> It(&World); It; ++It)
    {
        if (!It->bSupportsFaunaSwimming || It->RegionId != RegionId || !It->IsValidHabitat() || !It->ContainsGround(Point)) continue;
        const double Level = SimulationSeconds >= 0. ? It->EvaluateWaterLevelZ(SimulationSeconds, Rainfall) : It->GetWaterLevelZ();
        if (!It->ContainsGround(FVector(Point.X, Point.Y, Level))) continue;
        if (!Source || It->Priority > Source->Priority
            || (It->Priority == Source->Priority && It->GetFName().LexicalLess(Source->GetFName())))
        {
            Source = *It;
            Surface = Level;
        }
    }
    if (!Source) return false;
    const double Lowest = Source->Bounds->Bounds.GetBox().Min.Z;
    FHitResult Bottom;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(EcoFaunaWaterBottom), false);
    const FVector Start(Point.X, Point.Y, Source->Bounds->Bounds.GetBox().Max.Z + .1);
    const FVector End(Point.X, Point.Y, Lowest - .1);
    while (World.LineTraceSingleByObjectType(Bottom, Start, End, FCollisionObjectQueryParams(ECC_WorldStatic), Query))
    {
        const AActor* HitActor = Bottom.GetActor();
        if (!IsWaterSurfaceCollision(HitActor)) break;
        // Water-plugin query collision is WorldStatic, including the ocean under inland rivers.
        Query.AddIgnoredActor(HitActor);
    }
    if (!Bottom.bBlockingHit || !Source->ContainsGround(Bottom.ImpactPoint)) return false;
    Out = {Bottom.ImpactPoint.Z, Surface, Source->FaunaWaterCurrent, Source->FaunaWaterTemperatureC,
        Source->FaunaWaterCoverDensity, Source->FaunaWaterCoverHeightCm};
    return true;
}

bool EcoCreatureMovement::SampleFaunaWater(UWorld& World, FName RegionId, const FVector& Point,
    double Clearance, FFaunaWaterColumn& Out)
{
    FFaunaWaterColumn Column;
    if (!FMath::IsFinite(Clearance) || Clearance <= 0. || !ProbeFaunaWaterColumn(World, RegionId, Point, Column)
        || Column.Surface - Column.Bottom < 2. * Clearance) return false;
    Out = Column;
    return true;
}

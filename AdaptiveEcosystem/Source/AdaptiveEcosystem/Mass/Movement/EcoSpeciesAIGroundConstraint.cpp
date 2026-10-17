#include "Mass/Movement/EcoSpeciesAIGroundConstraint.h"
#include "AI/Behavior/EcoSpeciesAIProfile.h"
#include "Mass/Movement/EcoSpeciesAIGroundSceneSubsystem.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Engine/World.h"
#include "CollisionQueryParams.h"
#include "CollisionShape.h"
bool EcoSpeciesAI::ConstrainGroundStep(UWorld& W,FName Region,bool Traveling,const FVector& Start,FVector& End,const UEcoSpeciesAIProfile& P)
{
    const auto* Regions=W.GetSubsystem<UEcologyWorldSubsystem>();const auto* R=Regions?Regions->GetRegion(Region):nullptr;
    if(!R||Start.ContainsNaN()||End.ContainsNaN()||(!Traveling&&!R->ContainsPosition(End)))return false;
    FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoSpeciesGround),false);FHitResult Hit;
    const FVector Lift(0,0,P.BodyHeight*.5f+2);
    if(W.SweepSingleByChannel(Hit,Start+Lift,End+Lift,FQuat::Identity,ECC_WorldStatic,
        FCollisionShape::MakeCapsule(P.BodyRadius,P.BodyHeight*.5f),Params))return false;
    if(!W.LineTraceSingleByChannel(Hit,End+FVector(0,0,200),End-FVector(0,0,300),ECC_WorldStatic,Params)||Hit.ImpactNormal.Z<.65f)return false;
    if(FMath::Abs(Hit.ImpactPoint.Z-Start.Z)>100)return false;End.Z=Hit.ImpactPoint.Z;
    auto* Scene=W.GetSubsystem<UEcoSpeciesAIGroundSceneSubsystem>();
    return Scene&&(Traveling||R->ContainsPosition(End))&&!Scene->CrossesExcluded(Start,End);
}

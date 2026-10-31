#pragma once
#include "CoreMinimal.h"
#include "Mass/EcoHerdMigration.h"

class AHUD;
class APlayerController;

struct FEcoMigrationDebugRegion
{
    FName Id;
    FVector Minimum, Maximum;
    double FoodFraction=0;
    int32 Population=0;
};
struct FEcoMigrationDebugRoute { FName From,To; TArray<FVector> Points; };
struct FEcoMigrationDebugMember
{
    int64 Agent=0, Plan=0;
    FName Region,Reason;
    FVector Position,Goal;
    bool bActive=false;
    int32 Waypoint=0;
};
struct FEcoMigrationDebugPlan
{
    int64 Id=0,Herd=0;
    FName Origin,Destination,Reason;
    EEcoHerdJourneyState State=EEcoHerdJourneyState::Preparing;
    int32 Members=0,Arrived=0,Dead=0,Blocked=0;
    bool bReturning=false;
    TArray<FVector> Points;
};
/** Copied values only. Drawing never writes simulation, policy, food or transforms. */
struct FEcoHerdMigrationDebugSnapshot
{
    double WorldSeconds=0;
    TArray<FEcoMigrationDebugRegion> Regions;
    TArray<FEcoMigrationDebugRoute> Routes;
    TArray<FEcoMigrationDebugPlan> Plans;
    TArray<FEcoMigrationDebugMember> Members;
};
namespace EcoHerdMigrationDebug
{
    ADAPTIVEECOSYSTEM_API bool Capture(UWorld& World,FEcoHerdMigrationDebugSnapshot& Out);
    ADAPTIVEECOSYSTEM_API bool ToJson(const FEcoHerdMigrationDebugSnapshot& Snapshot,FString& Out);
    int32 Mode(UWorld& World);
    void Toggle(UWorld& World);
    void Draw(AHUD& HUD,APlayerController& Player,FVector2D Size,const FEcoHerdMigrationDebugSnapshot& Snapshot,int64 FocusPlan,int32 Mode);
}

#pragma once

#include "CoreMinimal.h"
#include "Creature/Runtime/EcoCreatureMovement.h"

struct FEcoV3StaticMeshPath
{
    FVector End = FVector::ZeroVector;
    FHitResult Hit;
    EcoCreatureMovement::EStepBlock Block = EcoCreatureMovement::EStepBlock::None;
    bool bStaticContact = false;
};

/** Runtime only. Step numbers belong to the bound Native context. */
struct FEcoV3StaticMeshMemory
{
    FVector2D LastDirection = FVector2D::ZeroVector;
    int64 LastProgressStep = -1;
    int64 LastStaticHitStep = -1;
    int64 BlockedSinceStep = -1;
    int64 NearUntilStep = -1;
    int64 LastTangentStep = -1;
};

/** Aggregated across all regions and Native catch-up steps by the development recorder. */
struct FEcoV3StaticMeshMetrics
{
    EcoCreatureMovement::FGroundMoveStats Queries;
    int32 Deer = 0, Intent = 0, Checked = 0, Moved = 0, Stalled = 0;
    int32 Traveling = 0, Flight = 0, Arrived = 0;
    int32 DiscHits = 0, StaticHits = 0, InitialOverlaps = 0, AgentBlocks = 0;
    int32 Tangents = 0, TangentsAccepted = 0, TangentSweeps = 0, BudgetDenied = 0;
    int32 ContactRegions = 0, LegacyRegions = 0, ImportedRegions = 0;
    int64 LongestContactStall = 0;
    float MinBodyRadius = MAX_flt, MaxBodyRadius = 0.f;
    double NativeSeconds = 0., DiscSeconds = 0., TangentSeconds = 0.;

    void Accumulate(const FEcoV3StaticMeshMetrics& Other)
    {
        Queries.Sweeps += Other.Queries.Sweeps;
        Queries.GroundProbes += Other.Queries.GroundProbes;
        Queries.ExclusionChecks += Other.Queries.ExclusionChecks;
        Queries.SweepSeconds += Other.Queries.SweepSeconds;
        Queries.GroundSeconds += Other.Queries.GroundSeconds;
        Queries.ExclusionSeconds += Other.Queries.ExclusionSeconds;
        Deer += Other.Deer;
        Intent += Other.Intent;
        Checked += Other.Checked;
        Moved += Other.Moved;
        Stalled += Other.Stalled;
        Traveling += Other.Traveling;
        Flight += Other.Flight;
        Arrived += Other.Arrived;
        DiscHits += Other.DiscHits;
        StaticHits += Other.StaticHits;
        InitialOverlaps += Other.InitialOverlaps;
        AgentBlocks += Other.AgentBlocks;
        Tangents += Other.Tangents;
        TangentsAccepted += Other.TangentsAccepted;
        TangentSweeps += Other.TangentSweeps;
        BudgetDenied += Other.BudgetDenied;
        ContactRegions += Other.ContactRegions;
        LegacyRegions += Other.LegacyRegions;
        ImportedRegions += Other.ImportedRegions;
        LongestContactStall = FMath::Max(LongestContactStall, Other.LongestContactStall);
        MinBodyRadius = FMath::Min(MinBodyRadius, Other.MinBodyRadius);
        MaxBodyRadius = FMath::Max(MaxBodyRadius, Other.MaxBodyRadius);
        NativeSeconds += Other.NativeSeconds;
        DiscSeconds += Other.DiscSeconds;
        TangentSeconds += Other.TangentSeconds;
    }
};

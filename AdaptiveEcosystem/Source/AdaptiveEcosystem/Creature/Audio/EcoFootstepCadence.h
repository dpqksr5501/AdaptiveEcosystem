#pragma once
#include "CoreMinimal.h"

/** Distance-based fallback for in-place BS without foot-contact notifies. Never moves an agent. */
struct FEcoFootstepCadence
{
    FVector Previous = FVector::ZeroVector;
    double Distance = 0;
    double SinceStep = 0;
    bool bInitialized = false;
    void Reset() { *this = {}; }
    bool Advance(const FVector& Position, float Speed, bool bAlive, float Delta, float Stride, float MinimumSpeed, bool bSnap = false)
    {
        if (Position.ContainsNaN() || !FMath::IsFinite(Speed) || !FMath::IsFinite(Delta)
            || !FMath::IsFinite(Stride) || Stride <= 0 || !FMath::IsFinite(MinimumSpeed) || MinimumSpeed < 0)
        { Reset(); return false; }
        const double Moved = bInitialized ? FVector::Dist2D(Previous, Position) : 0;
        Previous = Position;
        if (!bInitialized || bSnap || !bAlive || Speed < MinimumSpeed || Delta <= 0 || Delta > 0.5f || Moved > 2500)
        { bInitialized = true; Distance = SinceStep = 0; return false; }
        SinceStep += Delta;
        Distance += Moved;
        if (Distance < Stride || SinceStep < 0.12) return false;
        Distance = FMath::Fmod(Distance, double(Stride));
        SinceStep = 0;
        return true; // At most one event; never catch up a burst after replication/hitches.
    }
};

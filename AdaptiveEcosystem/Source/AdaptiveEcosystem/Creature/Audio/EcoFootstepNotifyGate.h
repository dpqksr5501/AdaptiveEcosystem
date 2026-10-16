#pragma once
#include "CoreMinimal.h"

/** Local representation gate. A running animation alone is never proof of travel. */
struct FEcoFootstepNotifyGate
{
    FVector Previous = FVector::ZeroVector;
    double FreshAt = -1, LastContact = -1;
    float TravelCredit = 0;
    bool bInitialized = false, bMoving = false;
    void Reset() { *this = {}; }
    void Observe(const FVector& Position, float Speed, bool bAlive, float Delta, double Now, float MinimumSpeed, bool bSnap)
    {
        if (Position.ContainsNaN() || !FMath::IsFinite(Speed) || !FMath::IsFinite(Delta) || !FMath::IsFinite(Now)
            || !FMath::IsFinite(MinimumSpeed) || MinimumSpeed < 0 || Now < 0 || !bAlive)
        { Reset(); return; }
        const float Distance = bInitialized ? FVector::Dist2D(Previous, Position) : 0;
        if (!bInitialized || bSnap || Delta <= 0 || Delta > .5f || Distance > 2500 || (FreshAt >= 0 && Now < FreshAt))
        { Reset(); Previous = Position; bInitialized = true; FreshAt = Now; return; }
        Previous = Position; FreshAt = Now;
        bMoving = Speed >= MinimumSpeed && Distance > .01f;
        if (!bMoving) { TravelCredit = 0; return; }
        TravelCredit = FMath::Min(TravelCredit + Distance, 500.f);
    }
    bool Contact(double Now)
    {
        if (!bInitialized || !bMoving || !FMath::IsFinite(Now) || Now < FreshAt || Now - FreshAt > .25
            || TravelCredit < 10 || (LastContact >= 0 && (Now < LastContact || Now - LastContact < .07))) return false;
        LastContact = Now; TravelCredit = 0; return true;
    }
};

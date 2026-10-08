#pragma once
#include "CoreMinimal.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"

class UWorld;
namespace EcoCreatureMovement
{
/** Selection only: no Transform ownership and no mutation of the raw policy action. */
inline FVector SelectVelocity(const FVector& Position, FVector PolicyVelocity, float Speed, float Delta,
    double Now, const FEcoTravelFragment* Travel, const FEcoSocialMovementRequestFragment* Request,
    FEcoShelterMovementFeedbackFragment* Feedback)
{
    const bool HasToken = Request && Request->ReservationId > 0;
    auto Report = [&](EEcoShelterMovementStatus Status) { if (HasToken && Feedback) Feedback->Report(Request->ReservationId, Status); };
    if (Travel && Travel->State != EEcoResidenceState::Resident)
    {
        Report(EEcoShelterMovementStatus::Yielded);
        if (Travel->State == EEcoResidenceState::WaitingForFood) return FVector::ZeroVector;
        return (Travel->TargetPosition - Position).GetSafeNormal2D()
            * FMath::Min(Travel->MoveSpeed, float(FVector::Dist2D(Position, Travel->TargetPosition)) / FMath::Max(Delta, SMALL_NUMBER));
    }
    if (!Request || !Request->bValid || Request->Mode == EEcoSocialMovementMode::None) return PolicyVelocity;
    if (!FMath::IsFinite(Now) || Request->ValidUntilWorldTime <= Now || Request->TargetPosition.ContainsNaN()
        || !FMath::IsFinite(Request->ArrivalRadius) || Request->ArrivalRadius <= 0 || !HasToken)
    { Report(EEcoShelterMovementStatus::Failed); return FVector::ZeroVector; }
    const float Distance = FVector::Dist(Position, Request->TargetPosition);
    if (Distance <= Request->ArrivalRadius)
    { Report(EEcoShelterMovementStatus::Arrived); return FVector::ZeroVector; }
    if (Request->Mode == EEcoSocialMovementMode::ShelterHold)
    { Report(EEcoShelterMovementStatus::Failed); return FVector::ZeroVector; }
    Report(EEcoShelterMovementStatus::Moving);
    return (Request->TargetPosition - Position).GetSafeNormal2D()
        * FMath::Min(Speed, Distance / FMath::Max(Delta, SMALL_NUMBER));
}
/** Authoritative movement boundary: region containment, blocking geometry and ground projection. */
ADAPTIVEECOSYSTEM_API bool ConstrainStep(UWorld& World, FName RegionId, bool bTraveling,
    const FVector& Position, FVector& Destination);
}

#pragma once
#include "CoreMinimal.h"
#include "Core/EcoTimeTypes.h"
#include "EcoClockSchedule.generated.h"

/** A bounded server-authored timeline. Ecology seconds and UE world seconds are distinct. */
USTRUCT(BlueprintType)
struct FEcoClockSchedule
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FEcoServerTimeSnapshot Sample;
    UPROPERTY(BlueprintReadOnly) double ServerWorldSeconds = 0;
    UPROPERTY(BlueprintReadOnly) double Rate = 1;
    UPROPERTY(BlueprintReadOnly) TArray<FEcoDayCycleState> Phases;

    bool Evaluate(double ServerNow, FEcoServerTimeSnapshot& Out) const
    {
        if (Sample.WorldEpoch <= 0 || !FMath::IsFinite(ServerNow) || !FMath::IsFinite(ServerWorldSeconds)
            || !FMath::IsFinite(Sample.ServerTimeSeconds) || Sample.ServerTimeSeconds < 0
            || !FMath::IsFinite(Rate) || Rate < 0 || Rate > 1) return false;
        const double Time = Sample.ServerTimeSeconds + FMath::Max(0.0, ServerNow - ServerWorldSeconds) * Rate;
        for (const auto& Phase : Phases)
            if (Time >= Phase.PhaseStartSeconds && Time < Phase.PhaseEndSeconds)
            {
                Out = Sample;
                Out.ServerTimeSeconds = Time;
                Out.DayCycle = Phase;
                return true;
            }
        return false; // Expired schedule: never invent a custom provider's future.
    }
};

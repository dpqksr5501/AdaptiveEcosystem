#pragma once

#include "CoreMinimal.h"

namespace EcoFaunaMotionClock
{
    // Motion follows the simulation epoch. Render frames only determine how many
    // of these boundaries are ready, while attack deadlines can split an interval.
    inline constexpr int32 StepsPerSecond = 60;
    inline constexpr int32 MaxStepsPerFrame = 16;

    inline int64 CompletedStepAt(double Seconds)
    {
        return FMath::FloorToInt64(Seconds * StepsPerSecond + UE_SMALL_NUMBER);
    }

    inline double StepTime(int64 Step)
    {
        return double(Step) / StepsPerSecond;
    }

    inline double CompletedTimeAt(double Seconds)
    {
        return StepTime(CompletedStepAt(Seconds));
    }
}

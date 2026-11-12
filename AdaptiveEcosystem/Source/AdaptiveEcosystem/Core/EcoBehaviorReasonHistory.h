#pragma once

#include "CoreMinimal.h"

struct FEcoBehaviorReasonEvent
{
    double Time=0;
    FName Reason, Region;
    int64 NativeStep=0, RelatedAgent=0;
    double Amount=0;
};

struct FEcoBehaviorReasonHistory
{
    FEcoBehaviorReasonEvent Events[16];
    int32 Count=0;
    bool IsEmpty() const { return Count==0; }
    int32 Num() const { return Count; }
    const FEcoBehaviorReasonEvent& Last() const { return Events[Count-1]; }
    const FEcoBehaviorReasonEvent* begin() const { return Events; }
    const FEcoBehaviorReasonEvent* end() const { return Events+Count; }
    void Append(const FEcoBehaviorReasonEvent& Event)
    {
        if (Count == UE_ARRAY_COUNT(Events))
        {
            for (int32 I=1; I<Count; ++I) Events[I-1]=Events[I];
            --Count;
        }
        Events[Count++]=Event;
    }
};

#include "Creature/Representation/EcoCreatureBlendSpace.h"
#include "Animation/AnimSequence.h"

bool UEcoCreatureBlendSpaceLibrary::ConfigureLocomotion(UBlendSpace1D* BlendSpace, UAnimSequence* Idle, UAnimSequence* Walk, UAnimSequence* Run, float WalkSpeed, float RunSpeed)
{
#if WITH_EDITOR
    if (!BlendSpace || !Idle || !Walk || !Run || !Idle->GetSkeleton() || Idle->GetSkeleton() != Walk->GetSkeleton()
        || Idle->GetSkeleton() != Run->GetSkeleton() || Idle->bEnableRootMotion || Walk->bEnableRootMotion || Run->bEnableRootMotion
        || !FMath::IsFinite(WalkSpeed) || !FMath::IsFinite(RunSpeed) || WalkSpeed <= 0 || RunSpeed <= WalkSpeed) return false;
    BlendSpace->Modify(); BlendSpace->SetSkeleton(Idle->GetSkeleton());
    while (BlendSpace->GetBlendSamples().Num() > 0) BlendSpace->DeleteSample(BlendSpace->GetBlendSamples().Num()-1);
    auto& Parameter = const_cast<FBlendParameter&>(BlendSpace->GetBlendParameter(0));
    Parameter.DisplayName = TEXT("Speed"); Parameter.Min = 0; Parameter.Max = RunSpeed; Parameter.GridNum = 6;
    if (BlendSpace->AddSample(Idle, FVector::ZeroVector) == INDEX_NONE || BlendSpace->AddSample(Walk, FVector(WalkSpeed,0,0)) == INDEX_NONE
        || BlendSpace->AddSample(Run, FVector(RunSpeed,0,0)) == INDEX_NONE) return false;
    BlendSpace->ValidateSampleData(); BlendSpace->ResampleData(); BlendSpace->PostEditChange(); BlendSpace->MarkPackageDirty();
    return BlendSpace->GetBlendSamples().Num() == 3;
#else
    return false;
#endif
}

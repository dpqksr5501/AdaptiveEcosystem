#include "Creature/Representation/EcoCreatureBlendSpace.h"
#include "Animation/AnimSequence.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#if WITH_EDITOR
#include "Engine/Blueprint.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#endif

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

bool UEcoCreatureBlendSpaceLibrary::ConfigureRepresentation(UBlueprint* Blueprint, UBlendSpace* BlendSpace, FRotator Rotation, FVector ForwardAxis)
{
#if WITH_EDITOR
    if (!Blueprint || !Blueprint->GeneratedClass || !BlendSpace || Rotation.ContainsNaN() || ForwardAxis.ContainsNaN()
        || ForwardAxis.IsNearlyZero()) return false;
    auto* Defaults = Cast<AEcoCreatureRepresentationActor>(Blueprint->GeneratedClass->GetDefaultObject());
    if (!Defaults) return false;
    Blueprint->Modify(); Defaults->Modify();
    Defaults->LocomotionBlendSpace = BlendSpace;
    Defaults->MeshRotation = Rotation;
    Defaults->MeshForwardAxis = ForwardAxis.GetSafeNormal();
    // Saving a generated CDO alone leaves Blueprint's cached defaults stale;
    // compile-on-load can restore old values. Use the editor's default edit path.
    FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
    FKismetEditorUtilities::CompileBlueprint(Blueprint);
    Defaults = Cast<AEcoCreatureRepresentationActor>(Blueprint->GeneratedClass->GetDefaultObject());
    return Defaults && Defaults->LocomotionBlendSpace == BlendSpace && Defaults->MeshRotation.Equals(Rotation)
        && Defaults->MeshForwardAxis.Equals(ForwardAxis.GetSafeNormal());
#else
    return false;
#endif
}

bool UEcoCreatureBlendSpaceLibrary::ConfigureTurning(UBlendSpace* BlendSpace, UAnimSequence* Idle, UAnimSequence* Walk,
    UAnimSequence* WalkLeft, UAnimSequence* WalkRight, UAnimSequence* Run, UAnimSequence* RunLeft, UAnimSequence* RunRight,
    float WalkSpeed, float RunSpeed)
{
#if WITH_EDITOR
    if (!BlendSpace || BlendSpace->IsA<UBlendSpace1D>() || !Idle || !Idle->GetSkeleton()
        || !Walk || !WalkLeft || !WalkRight || !Run || bool(RunLeft) != bool(RunRight)
        || !FMath::IsFinite(WalkSpeed) || !FMath::IsFinite(RunSpeed) || WalkSpeed <= 0 || RunSpeed <= WalkSpeed) return false;
    const TArray<UAnimSequence*> Animations = {Idle, Walk, WalkLeft, WalkRight, Run, RunLeft ? RunLeft : Run, RunRight ? RunRight : Run};
    for (auto* Animation : Animations)
        if (Animation->GetSkeleton() != Idle->GetSkeleton() || Animation->bEnableRootMotion) return false;
    BlendSpace->Modify(); BlendSpace->SetSkeleton(Idle->GetSkeleton());
    while (BlendSpace->GetBlendSamples().Num() > 0) BlendSpace->DeleteSample(BlendSpace->GetBlendSamples().Num()-1);
    auto& Speed = const_cast<FBlendParameter&>(BlendSpace->GetBlendParameter(0));
    Speed.DisplayName = TEXT("Speed"); Speed.Min = 0; Speed.Max = RunSpeed; Speed.GridNum = 6;
    auto& Turn = const_cast<FBlendParameter&>(BlendSpace->GetBlendParameter(1));
    Turn.DisplayName = TEXT("Turn"); Turn.Min = -1; Turn.Max = 1; Turn.GridNum = 2;
    for (int32 Row = 0; Row < 3; ++Row)
    {
        const float RowSpeed = Row == 0 ? 0 : Row == 1 ? WalkSpeed : RunSpeed;
        for (int32 Column = 0; Column < 3; ++Column)
        {
            UAnimSequence* Animation = Row == 0 ? Idle : Row == 1 ? (Column == 0 ? WalkLeft : Column == 1 ? Walk : WalkRight)
                : Column == 0 ? Animations[5] : Column == 1 ? Run : Animations[6];
            if (BlendSpace->AddSample(Animation, FVector(RowSpeed, Column - 1, 0)) == INDEX_NONE) return false;
        }
    }
    BlendSpace->ValidateSampleData(); BlendSpace->ResampleData(); BlendSpace->PostEditChange(); BlendSpace->MarkPackageDirty();
    return BlendSpace->GetBlendSamples().Num() == 9;
#else
    return false;
#endif
}

#include "Creature/Representation/EcoCreatureShapeComponent.h"
#include "AI/Policy/EcoBodyDevelopment.h"
#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Engine/SkeletalMesh.h"

void UEcoCreatureShapeComponent::SetBodyDevelopment(uint32 Packed, const FQuat& MeshToBody,
    const UEcoCreatureAnimationProfile* Profile)
{
    USkeletalMesh* Mesh = GetSkeletalMeshAsset();
    if (CachedBody == Packed && CachedMesh.Get() == Mesh && CachedProfile.Get() == Profile && CachedOrientation.Equals(MeshToBody)) return;
    CachedMesh = Mesh;
    CachedProfile = Profile;
    CachedOrientation = MeshToBody;
    CachedBody = Packed;
#if WITH_EDITOR
    FrozenComparisonPose.Reset();
#endif
    JointOffsets.Reset();
    DisplacedJointCount = 0;
    const auto Development = EcoLifeV3::FBodyDevelopment::Unpack(Packed);
    if (!Mesh || Packed == EcoLifeV3::FBodyDevelopment::Neutral || !Development.IsValid()) return;

    const auto& Skeleton = Mesh->GetRefSkeleton();
    const int32 Count = Skeleton.GetNum();
    TArray<FTransform> Reference;
    Reference.SetNum(Count);
    FBox SkeletonBounds(ForceInit);
    for (int32 Index = 0; Index < Count; ++Index)
    {
        const int32 Parent = Skeleton.GetParentIndex(Index);
        const FTransform& Local = Skeleton.GetRefBonePose()[Index];
        Reference[Index] = Parent == INDEX_NONE ? Local : Local * Reference[Parent];
        if (Parent != INDEX_NONE) SkeletonBounds += MeshToBody.RotateVector(Reference[Index].GetLocation());
    }
    if (!SkeletonBounds.IsValid) return;

    // Ground IK has already placed its end and contact markers. Keep those bones and their descendants fixed.
    TArray<double> Blend;
    Blend.Init(1., Count);
    TBitArray<> Anchored(false, Count);
    if (Profile && Profile->bEnableGroundIK)
    {
        const auto Anchor = [&](const TArray<FName>& Markers)
        {
            for (const FName Name : Markers)
            {
                const int32 Index = Skeleton.FindBoneIndex(Name);
                if (Index == INDEX_NONE) continue;
                Anchored[Index] = true;
                const int32 Parent = Skeleton.GetParentIndex(Index);
                if (Parent != INDEX_NONE) Blend[Parent] = FMath::Min(Blend[Parent], .45);
            }
        };
        Anchor(Profile->FootBones);
        Anchor(Profile->IKEndBones);
    }

    JointOffsets.SetNumZeroed(Count);
    const FVector Center = SkeletonBounds.GetCenter();
    const double HalfLength = FMath::Max(UE_SMALL_NUMBER, SkeletonBounds.GetExtent().X);
    for (int32 Index = 1; Index < Count; ++Index)
    {
        const int32 Parent = Skeleton.GetParentIndex(Index);
        if (Anchored[Index] || (Parent != INDEX_NONE && Anchored[Parent]))
        {
            Anchored[Index] = true;
            continue;
        }
        const FVector Local = MeshToBody.RotateVector(Reference[Index].GetLocation()) - Center;
        const auto Delta = Development.Offset(Local.X, Local.Y, Local.Z, Local.X / HalfLength);
        JointOffsets[Index] = MeshToBody.UnrotateVector(FVector(Delta[0], Delta[1], Delta[2])) * Blend[Index];
    }
}

void UEcoCreatureShapeComponent::FinalizeBoneTransform()
{
    if (bNeedToFlipSpaceBaseBuffers && !JointOffsets.IsEmpty())
    {
        auto& Pose = GetEditableComponentSpaceTransforms();
        DisplacedJointCount = 0;
        for (const FBoneIndexType Index : FillComponentSpaceTransformsRequiredBones)
        {
            if (!Pose.IsValidIndex(Index) || !JointOffsets.IsValidIndex(Index)) continue;
            const FVector& Offset = JointOffsets[Index];
            if (Offset.IsNearlyZero()) continue;
            Pose[Index].AddToTranslation(Offset);
            ++DisplacedJointCount;
        }
    }
    Super::FinalizeBoneTransform();
}

int32 UEcoCreatureShapeComponent::ShowFrozenBodyComparison(bool bApplyDevelopment)
{
#if WITH_EDITOR
    if (!GetWorld() || GetWorld()->WorldType != EWorldType::PIE) return 0;
    HandleExistingParallelEvaluationTask(true, true);
    if (DisplacedJointCount == 0) return 0;
    SetComponentTickEnabled(false);
    if (FrozenComparisonPose.IsEmpty()) FrozenComparisonPose = GetComponentSpaceTransforms();
    auto& Pose = GetEditableComponentSpaceTransforms();
    Pose = FrozenComparisonPose;
    if (!bApplyDevelopment)
        for (const FBoneIndexType Index : FillComponentSpaceTransformsRequiredBones)
            if (Pose.IsValidIndex(Index) && JointOffsets.IsValidIndex(Index))
                Pose[Index].AddToTranslation(-JointOffsets[Index]);
    // Commit the visual buffer without another animation evaluation or a foot-fit callback.
    bNeedToFlipSpaceBaseBuffers = true;
    USkinnedMeshComponent::FinalizeBoneTransform();
    MarkRenderDynamicDataDirty();
    return DisplacedJointCount;
#else
    return 0;
#endif
}

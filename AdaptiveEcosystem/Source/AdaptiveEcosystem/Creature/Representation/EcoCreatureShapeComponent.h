#pragma once

#include "Components/SkeletalMeshComponent.h"
#include "EcoCreatureShapeComponent.generated.h"

/** Applies local body variation to either of the pooled visual rigs before finalized-pose listeners read it. */
UCLASS()
class UEcoCreatureShapeComponent : public USkeletalMeshComponent
{
    GENERATED_BODY()

public:
    void SetBodyDevelopment(uint32 Packed, const FQuat& MeshToBody, const class UEcoCreatureAnimationProfile* Profile);
    void FinalizeBoneTransform() override;
    int32 GetDisplacedJointCount() const { return DisplacedJointCount; }

    /** Editor PIE screenshot tool. Both views reuse one finalized animation pose. */
    UFUNCTION(BlueprintCallable, Category="Creature|Diagnostics")
    int32 ShowFrozenBodyComparison(bool bApplyDevelopment);

private:
    TWeakObjectPtr<USkeletalMesh> CachedMesh;
    TWeakObjectPtr<const UEcoCreatureAnimationProfile> CachedProfile;
    FQuat CachedOrientation = FQuat::Identity;
    uint32 CachedBody = 0x80808080u;
    int32 DisplacedJointCount = 0;
    TArray<FVector> JointOffsets;
#if WITH_EDITOR
    TArray<FTransform> FrozenComparisonPose;
#endif
};

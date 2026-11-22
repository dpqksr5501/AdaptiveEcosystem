#pragma once
#include "CoreMinimal.h"
#include "BoneControllers/AnimNode_SkeletalControlBase.h"
#include "EcoGroundFeetNode.generated.h"
USTRUCT()
struct FEcoGroundLeg {
    GENERATED_BODY()
    UPROPERTY(EditAnywhere,Category="Rig") FBoneReference Contact;
    UPROPERTY(EditAnywhere,Category="Rig") FBoneReference End;
    UPROPERTY(EditAnywhere,Category="Rig") float ContactHeight=0;
};
USTRUCT(BlueprintInternalUseOnly)
struct ADAPTIVEECOSYSTEM_API FAnimNode_EcoGroundFeet : public FAnimNode_SkeletalControlBase {
    GENERATED_BODY()
    UPROPERTY(EditAnywhere,Category="Rig") TArray<FEcoGroundLeg> Legs;
    UPROPERTY(EditAnywhere,Category="Rig") FBoneReference Body;
    UPROPERTY(EditAnywhere,Category="Rig") float MaximumBodyDrop=6;
    UPROPERTY(EditAnywhere,Category="Rig") float MaximumCorrection=12;
    UPROPERTY(EditAnywhere,Category="Rig") float Clearance=.5f;
    UPROPERTY(EditAnywhere, Category="Rig") float MaximumPlantCorrection = 0.f;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundPoint0=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundPoint1=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundPoint2=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundPoint3=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundNormal0=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundNormal1=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundNormal2=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundNormal3=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundRootPoint=FVector::ZeroVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) FVector GroundUp=FVector::UpVector;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) float GroundValid0=0;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) float GroundValid1=0;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) float GroundValid2=0;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) float GroundValid3=0;
    UPROPERTY(EditAnywhere,Category="Input",meta=(PinShownByDefault)) float GroundWorldToComponent=1;
protected:
    struct FPlantState
    {
        FVector WorldContact = FVector::ZeroVector;
        FVector Correction = FVector::ZeroVector;
        bool bAnchored = false;
        bool bWaitForSwing = false;
    };
    FPlantState PlantStates[4];
    float UpdateSeconds=0;
    float BodyDrop=0;
    float Offsets[4]={};
    FQuat RootCorrections[4] = {FQuat::Identity, FQuat::Identity, FQuat::Identity, FQuat::Identity};
    FQuat JointCorrections[4] = {FQuat::Identity, FQuat::Identity, FQuat::Identity, FQuat::Identity};
    virtual void UpdateInternal(const FAnimationUpdateContext& Context) override;
    virtual void InitializeBoneReferences(const FBoneContainer& RequiredBones) override;
    virtual bool IsValidToEvaluate(const USkeleton* Skeleton,const FBoneContainer& RequiredBones) override;
    virtual void EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext& Output,TArray<FBoneTransform>& OutBoneTransforms) override;
    FVector UpdatePlant(int32 Index, const FTransform& Component, const FVector& Contact, const FVector& Up,
        bool bNearFloor, bool bSwing);
};

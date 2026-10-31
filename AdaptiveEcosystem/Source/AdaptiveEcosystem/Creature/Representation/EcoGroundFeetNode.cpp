#include "Creature/Representation/EcoGroundFeetNode.h"
#include "Animation/AnimInstanceProxy.h"
#include "TwoBoneIK.h"
void FAnimNode_EcoGroundFeet::InitializeBoneReferences(const FBoneContainer& Bones) {
    Body.Initialize(Bones);
    for(float& Offset:Offsets)Offset=0;
    BodyDrop=0;
    for(auto& Leg:Legs){Leg.Contact.Initialize(Bones);Leg.End.Initialize(Bones);}
}
bool FAnimNode_EcoGroundFeet::IsValidToEvaluate(const USkeleton*,const FBoneContainer& Bones) {
    if(!Body.IsValidToEvaluate(Bones)||Legs.Num()!=4||GroundUp.ContainsNaN()||!FMath::IsFinite(GroundWorldToComponent)||GroundWorldToComponent<=0)return false;
    for(const auto& Leg:Legs)if(!Leg.Contact.IsValidToEvaluate(Bones)||!Leg.End.IsValidToEvaluate(Bones))return false;
    return true;
}
void FAnimNode_EcoGroundFeet::UpdateInternal(const FAnimationUpdateContext& Context) {
    FAnimNode_SkeletalControlBase::UpdateInternal(Context);UpdateSeconds=FMath::Clamp(Context.GetDeltaTime(),0.f,.1f);
}
void FAnimNode_EcoGroundFeet::EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext& Output,TArray<FBoneTransform>& Out) {
    const auto& Bones=Output.Pose.GetPose().GetBoneContainer();
    const FVector Points[]={GroundPoint0,GroundPoint1,GroundPoint2,GroundPoint3};
    const float Valid[]={GroundValid0,GroundValid1,GroundValid2,GroundValid3};
    const FVector Up=GroundUp.GetSafeNormal();if(Up.IsNearlyZero())return;
    float Corrections[4]={};float Stances[4]={};float DesiredBodyDrop=0;
    for(int32 Index=0;Index<Legs.Num();++Index) {
        if(Valid[Index]<=0||!FMath::IsFinite(Valid[Index])||Points[Index].ContainsNaN()){Offsets[Index]=0;continue;}
        const FVector Contact=Output.Pose.GetComponentSpaceTransform(Legs[Index].Contact.GetCompactPoseIndex(Bones)).GetLocation();
        // Stance is measured against the uncorrected animated root, not downhill distance to the ground.
        const float Lift=FVector::DotProduct(Contact-GroundRootPoint,Up)-Legs[Index].ContactHeight;
        Stances[Index]=FMath::Clamp(1.f-FMath::Max(0.f,Lift-4.f*GroundWorldToComponent)/(12.f*GroundWorldToComponent),0.f,1.f)*FMath::Clamp(Valid[Index],0.f,1.f);
        const float Height=FVector::DotProduct(Contact-Points[Index],Up)-Legs[Index].ContactHeight;
        const float Desired=FMath::Clamp(Clearance*GroundWorldToComponent-Height,-MaximumCorrection*GroundWorldToComponent,MaximumCorrection*GroundWorldToComponent)*Stances[Index];
        Offsets[Index]=Stances[Index]<=0?0:FMath::FInterpTo(Offsets[Index],Desired,UpdateSeconds,12.f);
        Corrections[Index]=Offsets[Index];DesiredBodyDrop=FMath::Min(DesiredBodyDrop,Desired*.5f);
    }
    BodyDrop=FMath::FInterpTo(BodyDrop,FMath::Clamp(DesiredBodyDrop,-MaximumBodyDrop*GroundWorldToComponent,0.f),UpdateSeconds,8.f);
    const FVector BodyOffset=Up*BodyDrop;
    if(!BodyOffset.IsNearlyZero()) {
        const auto BodyIndex=Body.GetCompactPoseIndex(Bones);
        FTransform T=Output.Pose.GetComponentSpaceTransform(BodyIndex);T.AddToTranslation(BodyOffset);Out.Add(FBoneTransform(BodyIndex,T));
    }
    for(int32 Index=0;Index<Legs.Num();++Index) {
        if(Valid[Index]<=0||Points[Index].ContainsNaN())continue;
        const auto& Leg=Legs[Index];const auto EndIndex=Leg.End.GetCompactPoseIndex(Bones);
        const auto JointIndex=Bones.GetParentBoneIndex(EndIndex);if(JointIndex==INDEX_NONE)continue;
        const auto RootIndex=Bones.GetParentBoneIndex(JointIndex);if(RootIndex==INDEX_NONE)continue;
        FTransform Root=Output.Pose.GetComponentSpaceTransform(RootIndex);
        FTransform Joint=Output.Pose.GetComponentSpaceTransform(JointIndex);
        FTransform End=Output.Pose.GetComponentSpaceTransform(EndIndex);
        const float Correction=Corrections[Index];
        if(Stances[Index]<=0)continue;
        const FVector Desired=End.GetLocation()+Up*Correction;
        Root.AddToTranslation(BodyOffset);Joint.AddToTranslation(BodyOffset);End.AddToTranslation(BodyOffset);
        const FVector Axis=(End.GetLocation()-Root.GetLocation()).GetSafeNormal();
        const FVector RootToJoint=Joint.GetLocation()-Root.GetLocation();
        const FVector Bend=RootToJoint-Axis*FVector::DotProduct(RootToJoint,Axis);
        // A nearly straight chain has no reliable bend plane: leave its original pose rather than flip the knee.
        if(Bend.SizeSquared()<1.f)continue;
        const FVector Pole=Joint.GetLocation()+Bend.GetSafeNormal()*50.f;
        const FQuat OriginalEndRotation=End.GetRotation();
        AnimationCore::SolveTwoBoneIK(Root,Joint,End,Pole,Desired,false,1.0,1.0);
        End.SetRotation(OriginalEndRotation); // preserve the animated hoof/wrist orientation and descendant contact marker.
        if(Root.ContainsNaN()||Joint.ContainsNaN()||End.ContainsNaN())continue;
        Out.Add(FBoneTransform(RootIndex,Root));Out.Add(FBoneTransform(JointIndex,Joint));Out.Add(FBoneTransform(EndIndex,End));
    }
    Out.Sort([](const FBoneTransform& A,const FBoneTransform& B){return A.BoneIndex<B.BoneIndex;});
}

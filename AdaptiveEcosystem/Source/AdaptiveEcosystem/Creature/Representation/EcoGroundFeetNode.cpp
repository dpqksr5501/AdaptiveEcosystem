#include "Creature/Representation/EcoGroundFeetNode.h"
#include "Animation/AnimInstanceProxy.h"
#include "TwoBoneIK.h"
void FAnimNode_EcoGroundFeet::InitializeBoneReferences(const FBoneContainer& Bones) {
    Body.Initialize(Bones);
    for(float& Offset:Offsets)Offset=0;
    for(FVector& Direction:LastBend)Direction=FVector::ZeroVector;
    BodyDrop=0;
    for(auto& Leg:Legs){Leg.Contact.Initialize(Bones);Leg.End.Initialize(Bones);}
}
bool FAnimNode_EcoGroundFeet::IsValidToEvaluate(const USkeleton*,const FBoneContainer& Bones) {
    if(!Body.IsValidToEvaluate(Bones)||(Legs.Num()!=2&&Legs.Num()!=4)||GroundUp.ContainsNaN()||!FMath::IsFinite(GroundWorldToComponent)||GroundWorldToComponent<=0)return false;
    for(const auto& Leg:Legs)if(!Leg.Contact.IsValidToEvaluate(Bones)||!Leg.End.IsValidToEvaluate(Bones))return false;
    return true;
}
void FAnimNode_EcoGroundFeet::UpdateInternal(const FAnimationUpdateContext& Context) {
    FAnimNode_SkeletalControlBase::UpdateInternal(Context);UpdateSeconds=FMath::Clamp(Context.GetDeltaTime(),0.f,.1f);
}
void FAnimNode_EcoGroundFeet::EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext& Output,TArray<FBoneTransform>& Out) {
    const auto& Bones=Output.Pose.GetPose().GetBoneContainer();
    const FVector Points[]={GroundPoint0,GroundPoint1,GroundPoint2,GroundPoint3};
    const FVector Normals[]={GroundNormal0,GroundNormal1,GroundNormal2,GroundNormal3};
    const float Valid[]={GroundValid0,GroundValid1,GroundValid2,GroundValid3};
    const FVector Up=GroundUp.GetSafeNormal();if(Up.IsNearlyZero())return;
    float Corrections[4]={};float RequiredLifts[4]={};float Stances[4]={};float DesiredBodyDrop=0;
    float GroundGaps[4]={};
    FVector GroundGradients[4]={Up,Up,Up,Up};
    const float MaximumLift=MaximumCorrection*GroundWorldToComponent;
    for(int32 Index=0;Index<Legs.Num();++Index) {
        if(Valid[Index]<=0||!FMath::IsFinite(Valid[Index])||Points[Index].ContainsNaN()){Offsets[Index]=0;continue;}
        const FVector Contact=Output.Pose.GetComponentSpaceTransform(Legs[Index].Contact.GetCompactPoseIndex(Bones)).GetLocation();
        // Stance is measured against the uncorrected animated root, not downhill distance to the ground.
        const float Lift=FVector::DotProduct(Contact-GroundRootPoint,Up)-Legs[Index].ContactHeight;
        Stances[Index]=FMath::Clamp(1.f-FMath::Max(0.f,Lift-4.f*GroundWorldToComponent)/(12.f*GroundWorldToComponent),0.f,1.f)*FMath::Clamp(Valid[Index],0.f,1.f);
        // The trace used the previous evaluated foot location. Project the new foot
        // onto the sampled support plane only within the local footprint.
        const FVector FromSample=Contact-Points[Index];
        float DistanceAboveGround=FVector::DotProduct(FromSample,Up);
        const FVector PlanarDelta=FromSample-Up*DistanceAboveGround;
        const float VerticalNormal=FVector::DotProduct(Normals[Index],Up);
        if(VerticalNormal>=.65f && PlanarDelta.SizeSquared()<=FMath::Square(40.f*GroundWorldToComponent)) {
            DistanceAboveGround+=FMath::Clamp(FVector::DotProduct(PlanarDelta,Normals[Index])/VerticalNormal,
                -10.f*GroundWorldToComponent,10.f*GroundWorldToComponent);
            GroundGradients[Index]=Normals[Index]/VerticalNormal;
        }
        GroundGaps[Index]=DistanceAboveGround;
        const float Height=DistanceAboveGround-Legs[Index].ContactHeight;
        const float Desired=FMath::Clamp(Clearance*GroundWorldToComponent-Height,-MaximumCorrection*GroundWorldToComponent,MaximumCorrection*GroundWorldToComponent)*Stances[Index];
        Offsets[Index]=Stances[Index]<=0?0:FMath::FInterpTo(Offsets[Index],Desired,UpdateSeconds,12.f);
        // A rising slope can intersect a swinging foot even when the clip marks it lifted.
        // Lift only the portion that has actually crossed the floor and leave clear swings unmodified.
        const float Penetration = -DistanceAboveGround;
        if (Penetration > 2.f * GroundWorldToComponent)
        {
            Stances[Index] = FMath::Max(Stances[Index], FMath::Clamp(Valid[Index], 0.f, 1.f));
            RequiredLifts[Index] = FMath::Min(Penetration + Clearance * GroundWorldToComponent,
                MaximumCorrection * GroundWorldToComponent);
            Offsets[Index] = FMath::Max(Offsets[Index], RequiredLifts[Index]);
        }
        Corrections[Index]=Offsets[Index];DesiredBodyDrop=FMath::Min(DesiredBodyDrop,Desired*.5f);
    }
    BodyDrop=FMath::FInterpTo(BodyDrop,FMath::Clamp(DesiredBodyDrop,-MaximumBodyDrop*GroundWorldToComponent,0.f),UpdateSeconds,8.f);
    const FVector BodyOffset=Up*BodyDrop;
    const auto BodyIndex=Body.GetCompactPoseIndex(Bones);
    if(!BodyOffset.IsNearlyZero()) {
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
        const FVector AnimatedEnd=End.GetLocation();
        if(Stances[Index]<=0) {
            const bool bBodyMovesFoot=EndIndex==BodyIndex||Bones.BoneIsChildOf(EndIndex,BodyIndex);
            const float InheritedDrop=bBodyMovesFoot?BodyDrop:0.f;
            if(GroundGaps[Index]+InheritedDrop>=0.f)continue;
            const float Lift=FMath::Min(-GroundGaps[Index]+.25f*GroundWorldToComponent,MaximumLift);
            End.AddToTranslation(Up*Lift);
            Out.Add(FBoneTransform(EndIndex,End));
            continue;
        }
        const FVector Desired=AnimatedEnd+Up*Correction;
        Root.AddToTranslation(BodyOffset);Joint.AddToTranslation(BodyOffset);End.AddToTranslation(BodyOffset);
        const FVector Axis=(End.GetLocation()-Root.GetLocation()).GetSafeNormal();
        const FVector RootToJoint=Joint.GetLocation()-Root.GetLocation();
        const FVector AnimatedBend=RootToJoint-Axis*FVector::DotProduct(RootToJoint,Axis);
        // Near full extension, keep the last stable direction projected onto the new chain axis.
        // Dropping the solve for those frames causes the foot to snap back to the clip.
        if(AnimatedBend.SizeSquared()>=1.f)LastBend[Index]=AnimatedBend.GetSafeNormal();
        const FVector PriorBend=LastBend[Index]-Axis*FVector::DotProduct(LastBend[Index],Axis);
        const FVector Bend=PriorBend.IsNearlyZero()?AnimatedBend:PriorBend;
        const bool HasBendPlane=!Bend.IsNearlyZero();
        if(HasBendPlane) {
            const FVector Pole=Joint.GetLocation()+Bend.GetSafeNormal()*50.f;
            const FQuat OriginalEndRotation=End.GetRotation();
            AnimationCore::SolveTwoBoneIK(Root,Joint,End,Pole,Desired,false,1.0,1.0);
            End.SetRotation(OriginalEndRotation); // Keep the animated hoof and descendant contact orientation.
            if(Root.ContainsNaN()||Joint.ContainsNaN()||End.ContainsNaN())continue;
            Out.Add(FBoneTransform(RootIndex,Root));Out.Add(FBoneTransform(JointIndex,Joint));
        } else if(EndIndex!=BodyIndex&&!Bones.BoneIsChildOf(EndIndex,BodyIndex)) {
            End.AddToTranslation(-BodyOffset);
        }
        // Preserve the animated end rotation, so translating the end also translates its contact marker.
        // Check the solved position, including body drop and horizontal shortening at full reach.
        const FVector EndDelta=End.GetLocation()-AnimatedEnd;
        const float VerticalLift=FVector::DotProduct(EndDelta,Up);
        const float SolvedGap=GroundGaps[Index]+FVector::DotProduct(EndDelta,GroundGradients[Index]);
        const float ContactLift=SolvedGap<0.f?-SolvedGap+.25f*GroundWorldToComponent:0.f;
        const float Residual=FMath::Clamp(FMath::Max(ContactLift,RequiredLifts[Index]-VerticalLift),
            0.f,FMath::Max(0.f,MaximumLift-VerticalLift));
        if(Residual>0.f) {
            End.AddToTranslation(Up*Residual);
        }
        if(!HasBendPlane&&Residual<=0.f)continue;
        Out.Add(FBoneTransform(EndIndex,End));
    }
    Out.Sort([](const FBoneTransform& A,const FBoneTransform& B){return A.BoneIndex<B.BoneIndex;});
}

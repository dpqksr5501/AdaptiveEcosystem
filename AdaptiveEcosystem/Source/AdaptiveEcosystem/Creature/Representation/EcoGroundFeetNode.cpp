#include "Creature/Representation/EcoGroundFeetNode.h"
#include "Animation/AnimInstanceProxy.h"
#include "TwoBoneIK.h"

namespace
{
FQuat LimitRotation(const FQuat& From, const FQuat& To, double MaxRadians)
{
    const double Angle = From.AngularDistance(To);
    return Angle > MaxRadians ? FQuat::Slerp(From, To, MaxRadians / Angle).GetNormalized() : To;
}
}

void FAnimNode_EcoGroundFeet::InitializeBoneReferences(const FBoneContainer& Bones) {
    Body.Initialize(Bones);
    for(float& Offset:Offsets)Offset=0;
    for (int32 Index = 0; Index < 4; ++Index)
    {
        RootCorrections[Index] = JointCorrections[Index] = FQuat::Identity;
        PlantStates[Index] = {};
    }
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

FVector FAnimNode_EcoGroundFeet::UpdatePlant(int32 Index, const FTransform& Component, const FVector& Contact,
    const FVector& Up, bool bNearFloor, bool bSwing)
{
    FPlantState& Plant = PlantStates[Index];
    if (bSwing) Plant.bWaitForSwing = false;
    if (!bNearFloor) Plant.bAnchored = false;
    if (bNearFloor && !Plant.bAnchored && !Plant.bWaitForSwing)
    {
        Plant.WorldContact = Component.TransformPosition(Contact);
        Plant.bAnchored = Plant.bWaitForSwing = true;
    }

    FVector Goal = FVector::ZeroVector;
    if (Plant.bAnchored)
    {
        const FVector ToAnchor = Component.InverseTransformPosition(Plant.WorldContact) - Contact;
        const FVector Planar = ToAnchor - Up * FVector::DotProduct(ToAnchor, Up);
        if (Planar.SizeSquared() <= FMath::Square(MaximumPlantCorrection * GroundWorldToComponent))
            Goal = Planar;
        else
            Plant.bAnchored = false;
    }
    Plant.Correction = FMath::VInterpTo(Plant.Correction, Goal, UpdateSeconds, Plant.bAnchored ? 36.f : 18.f);
    return Plant.Correction;
}

void FAnimNode_EcoGroundFeet::EvaluateSkeletalControl_AnyThread(FComponentSpacePoseContext& Output,TArray<FBoneTransform>& Out) {
    const auto& Bones=Output.Pose.GetPose().GetBoneContainer();
    const FVector Points[]={GroundPoint0,GroundPoint1,GroundPoint2,GroundPoint3};
    const FVector Normals[]={GroundNormal0,GroundNormal1,GroundNormal2,GroundNormal3};
    const float Valid[]={GroundValid0,GroundValid1,GroundValid2,GroundValid3};
    const FVector Up=GroundUp.GetSafeNormal();if(Up.IsNearlyZero())return;
    float Corrections[4]={};float RequiredLifts[4]={};float Stances[4]={};float DesiredBodyDrop=0;
    float GroundGaps[4]={};
    FVector PlanarCorrections[4] = {FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector, FVector::ZeroVector};
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
        if (MaximumPlantCorrection > 0.f)
        {
            // The input pose can still be above its contact height before
            // vertical IK runs. Accept the part within this leg's reach.
            const bool bNearFloor = Stances[Index] > .35f
                && Height <= (Clearance + MaximumCorrection) * GroundWorldToComponent;
            PlanarCorrections[Index] = UpdatePlant(Index, Output.AnimInstanceProxy->GetComponentTransform(), Contact, Up,
                bNearFloor, Stances[Index] < .2f || Height > (Clearance + MaximumCorrection) * GroundWorldToComponent);
        }
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
        if (Valid[Index] <= 0.f || !FMath::IsFinite(Valid[Index]) || Points[Index].ContainsNaN())
        {
            RootCorrections[Index] = JointCorrections[Index] = FQuat::Identity;
            PlantStates[Index] = {};
            continue;
        }
        const auto& Leg=Legs[Index];const auto EndIndex=Leg.End.GetCompactPoseIndex(Bones);
        const auto JointIndex=Bones.GetParentBoneIndex(EndIndex);if(JointIndex==INDEX_NONE)continue;
        const auto RootIndex=Bones.GetParentBoneIndex(JointIndex);if(RootIndex==INDEX_NONE)continue;
        FTransform Root=Output.Pose.GetComponentSpaceTransform(RootIndex);
        FTransform Joint=Output.Pose.GetComponentSpaceTransform(JointIndex);
        FTransform End=Output.Pose.GetComponentSpaceTransform(EndIndex);
        const FVector AnimatedEnd=End.GetLocation();
        const bool bRootFollowsBody = RootIndex == BodyIndex || Bones.BoneIsChildOf(RootIndex, BodyIndex);
        const FVector ChainOffset = bRootFollowsBody ? BodyOffset : FVector::ZeroVector;
        Root.AddToTranslation(ChainOffset);
        Joint.AddToTranslation(ChainOffset);
        End.AddToTranslation(ChainOffset);
        const FVector Axis=(End.GetLocation()-Root.GetLocation()).GetSafeNormal();
        const FVector RootToJoint=Joint.GetLocation()-Root.GetLocation();
        const FVector AnimatedBend=RootToJoint-Axis*FVector::DotProduct(RootToJoint,Axis);
        const FVector JointToEnd = End.GetLocation() - Joint.GetLocation();
        const FQuat AnimatedRoot = Root.GetRotation();
        const FQuat AnimatedJoint = Joint.GetRotation();
        const FQuat LocalJoint = AnimatedRoot.Inverse() * AnimatedJoint;
        FQuat GoalRoot = FQuat::Identity;
        FQuat GoalJoint = FQuat::Identity;
        const FVector Desired = AnimatedEnd + Up * Corrections[Index] + PlanarCorrections[Index];
        const FVector DesiredAxis = (Desired - Root.GetLocation()).GetSafeNormal();
        const double BendConfidence = FMath::SmoothStep(0.015, 0.10,
            AnimatedBend.Size() / FMath::Max(RootToJoint.Size(), UE_SMALL_NUMBER));
        if (Stances[Index] > 0.f && BendConfidence > 0. && !Axis.IsNearlyZero()
            && FVector::DotProduct(Axis, DesiredAxis) > .25)
        {
            // Transport the animated bend plane to the new reach axis. A pole
            // attached to the old knee can move to the other side of that axis.
            const FVector Bend = FQuat::FindBetweenNormals(Axis, DesiredAxis).RotateVector(AnimatedBend.GetSafeNormal());
            const FVector Pole = Root.GetLocation() + Bend * RootToJoint.Size();
            FTransform SolvedRoot = Root, SolvedJoint = Joint, SolvedEnd = End;
            AnimationCore::SolveTwoBoneIK(SolvedRoot, SolvedJoint, SolvedEnd, Pole, Desired, false, 1., 1.);
            if (!SolvedRoot.ContainsNaN() && !SolvedJoint.ContainsNaN())
            {
                GoalRoot = LimitRotation(FQuat::Identity, (AnimatedRoot.Inverse() * SolvedRoot.GetRotation()).GetNormalized(),
                    FMath::DegreesToRadians(28. * BendConfidence));
                const FQuat SolvedLocalJoint = SolvedRoot.GetRotation().Inverse() * SolvedJoint.GetRotation();
                GoalJoint = LimitRotation(FQuat::Identity, (LocalJoint.Inverse() * SolvedLocalJoint).GetNormalized(),
                    FMath::DegreesToRadians(38. * BendConfidence));
            }
        }
        const double RotationStep = FMath::DegreesToRadians(420. * UpdateSeconds);
        RootCorrections[Index] = LimitRotation(RootCorrections[Index], GoalRoot, RotationStep);
        JointCorrections[Index] = LimitRotation(JointCorrections[Index], GoalJoint, RotationStep);
        const bool bCorrected = !RootCorrections[Index].IsIdentity() || !JointCorrections[Index].IsIdentity();
        if (bCorrected)
        {
            Root.SetRotation((AnimatedRoot * RootCorrections[Index]).GetNormalized());
            Joint.SetRotation((Root.GetRotation() * LocalJoint * JointCorrections[Index]).GetNormalized());
            Joint.SetLocation(Root.GetLocation() + (Root.GetRotation() * AnimatedRoot.Inverse()).RotateVector(RootToJoint));
            End.SetLocation(Joint.GetLocation() + (Joint.GetRotation() * AnimatedJoint.Inverse()).RotateVector(JointToEnd));
            Out.Add(FBoneTransform(RootIndex, Root));
            Out.Add(FBoneTransform(JointIndex, Joint));
        }
        // Preserve the animated end rotation, so translating the end also translates its contact marker.
        // Check the solved position, including body drop and horizontal shortening at full reach.
        if (!PlanarCorrections[Index].IsNearlyZero())
        {
            const FVector EndTravel = End.GetLocation() - AnimatedEnd;
            const FVector PlanarTravel = EndTravel - Up * FVector::DotProduct(EndTravel, Up);
            // Favor the articulated solve. The remaining local movement of
            // the hoof is bounded while the joint rotations ease in.
            const double MaxResidual = FMath::Min(4.f, MaximumPlantCorrection / 3.f) * GroundWorldToComponent;
            End.AddToTranslation((PlanarCorrections[Index] - PlanarTravel).GetClampedToMaxSize(MaxResidual));
        }
        const FVector EndDelta=End.GetLocation()-AnimatedEnd;
        const float VerticalLift=FVector::DotProduct(EndDelta,Up);
        const float SolvedGap=GroundGaps[Index]+FVector::DotProduct(EndDelta,GroundGradients[Index]);
        // When rotation is limited (e.g. near a straight knee), recover only
        // the missing vertical reach and keep the clip's hoof orientation.
        // The support trace is from the previously evaluated marker. Allow
        // a small size-dependent margin for its motion during fast turning.
        const float Margin = FMath::Clamp(MaximumCorrection * .08f, .25f, 2.f);
        const float ContactLift = FMath::Max(0.f, Margin * GroundWorldToComponent - SolvedGap);
        const float StanceLift = Stances[Index] > 0.f ? FMath::Max(0.f, Corrections[Index] - VerticalLift) : 0.f;
        const float Residual=FMath::Clamp(FMath::Max3(ContactLift, StanceLift, RequiredLifts[Index]-VerticalLift),
            0.f,FMath::Max(0.f,MaximumLift-VerticalLift));
        if(Residual>0.f) {
            End.AddToTranslation(Up*Residual);
        }
        if (!bCorrected && Residual <= 0.f && PlanarCorrections[Index].IsNearlyZero()) continue;
        Out.Add(FBoneTransform(EndIndex,End));
    }
    Out.Sort([](const FBoneTransform& A,const FBoneTransform& B){return A.BoneIndex<B.BoneIndex;});
}

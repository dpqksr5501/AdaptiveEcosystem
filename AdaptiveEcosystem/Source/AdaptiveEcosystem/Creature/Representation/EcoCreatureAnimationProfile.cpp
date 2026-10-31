#include "Creature/Representation/EcoCreatureAnimationProfile.h"
#include "Animation/Skeleton.h"
bool UEcoCreatureAnimationProfile::IsValidProfile() const
{
    if (!Locomotion || !Locomotion->GetSkeleton() || Poses.Num()!=9 || !FMath::IsFinite(StationarySpeed) || StationarySpeed<0
        || !FMath::IsFinite(MinimumPoseHoldSeconds) || MinimumPoseHoldSeconds<0
        || !FMath::IsFinite(MaxFootCorrectionCm) || MaxFootCorrectionCm<0 || MaxFootCorrectionCm>50
        || !FMath::IsFinite(FootClearanceCm) || FootClearanceCm<0 || FootClearanceCm>20
        || (bEnableGroundIK && (FootBones.Num()!=4 || IKEndBones.Num()!=4 || ContactHeights.Num()!=4))) return false;
    if(bEnableGroundIK) {
        const auto& Rig=Locomotion->GetSkeleton()->GetReferenceSkeleton();const int32 Body=Rig.FindBoneIndex(BodyBone);
        if(Body==INDEX_NONE)return false;
        TSet<int32> ChainBones;
        for(int32 Leg=0;Leg<4;++Leg) {
            const int32 Contact=Rig.FindBoneIndex(FootBones[Leg]),End=Rig.FindBoneIndex(IKEndBones[Leg]);
            if(Contact==INDEX_NONE||End==INDEX_NONE||Rig.GetParentIndex(Contact)!=End)return false;
            int32 Bone=End;
            for(int32 Link=0;Link<3;++Link) {
                if(Bone==INDEX_NONE||Bone==Body||ChainBones.Contains(Bone))return false;
                ChainBones.Add(Bone);Bone=Rig.GetParentIndex(Bone);
            }
            while(Bone!=INDEX_NONE&&Bone!=Body)Bone=Rig.GetParentIndex(Bone);
            if(Bone!=Body)return false;
        }
    }
    for(float Height:ContactHeights) if(!FMath::IsFinite(Height)||Height<0||Height>50)return false;
    for(int32 I=1;I<Poses.Num();++I)
        if(!Poses[I].Clip || Poses[I].Clip->GetSkeleton()!=Locomotion->GetSkeleton()
            || !FMath::IsFinite(Poses[I].PlayRate) || Poses[I].PlayRate<=0 || !FMath::IsFinite(Poses[I].BlendSeconds) || Poses[I].BlendSeconds<0) return false;
    return true;
}

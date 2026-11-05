#include "Player/EcoComboAuthoringLibrary.h"
#include "Player/EcoAttackNotifies.h"
#include "Animation/AnimMontage.h"
#include "Animation/AnimSequence.h"
#include "Animation/Skeleton.h"
#include "Engine/SkeletalMeshSocket.h"
bool UEcoComboAuthoringLibrary::ConfigureComboMontage(UAnimMontage* Montage, const TArray<UAnimSequence*>& Sequences)
{
#if WITH_EDITOR
    if (!Montage || Sequences.Num()!=3) return false;
    for (auto* Sequence : Sequences) if (!Sequence || Sequence->GetSkeleton()!=Sequences[0]->GetSkeleton()) return false;
    Montage->Modify(); Montage->SetSkeleton(Sequences[0]->GetSkeleton());
    Montage->SlotAnimTracks.Reset(); Montage->CompositeSections.Reset(); Montage->Notifies.Reset();
    FSlotAnimationTrack Track; Track.SlotName = TEXT("DefaultSlot");
    const FName Sections[] = {TEXT("LeftPunch"), TEXT("RightPunch"), TEXT("Kick")};
    const FName Sockets[] = {TEXT("Attack_Hand_L"), TEXT("Attack_Hand_R"), TEXT("Attack_Foot")};
    const FName Bones[] = {TEXT("hand_l"), TEXT("hand_r"), TEXT("foot_l")};
    float Time=0;
    for (int32 I=0; I<3; ++I)
    {
        auto* Sequence=Sequences[I]; const float Length=Sequence->GetPlayLength();
        FAnimSegment Segment; Segment.SetAnimReference(Sequence); Segment.StartPos=Time; Segment.AnimStartTime=0; Segment.AnimEndTime=Length; Segment.AnimPlayRate=1; Segment.LoopingCount=1;
        Track.AnimTrack.AnimSegments.Add(Segment);
        Time+=Length;
    }
    Montage->SlotAnimTracks.Add(Track); Montage->SetCompositeLength(Time);
    Time=0;
    for (int32 I=0; I<3; ++I)
    {
        const float Length=Sequences[I]->GetPlayLength();
        Montage->AddAnimCompositeSection(Sections[I],Time);
        auto AddState=[&](UAnimNotifyState* State, float Start, float End)
        {
            FAnimNotifyEvent Event; Event.NotifyStateClass=State; Event.NotifyName=State->GetClass()->GetFName();
            Event.Link(Montage,Time+Length*Start); Event.SetDuration(Length*(End-Start)); Event.EndLink.Link(Montage,Time+Length*End);
            Event.MontageTickType=EMontageNotifyTickType::BranchingPoint;
            Montage->Notifies.Add(Event);
        };
        AddState(NewObject<UEcoAnimNotifyState_MeleeHitWindow>(Montage),.22f,.48f);
        if (I<2)
        {
            AddState(NewObject<UEcoAnimNotifyState_ComboInputWindow>(Montage),.32f,.73f);
            FAnimNotifyEvent Event; Event.Notify=NewObject<UEcoAnimNotify_ComboBranch>(Montage); Event.NotifyName=TEXT("EcoComboBranch"); Event.Link(Montage,Time+Length*.80f); Event.MontageTickType=EMontageNotifyTickType::BranchingPoint; Montage->Notifies.Add(Event);
        }
        Montage->CompositeSections[I].NextSectionName=NAME_None;
        auto* Skeleton=Montage->GetSkeleton();
        if (!Skeleton->FindSocket(Sockets[I]))
        {
            Skeleton->Modify(); auto* Socket=NewObject<USkeletalMeshSocket>(Skeleton); Socket->SocketName=Sockets[I]; Socket->BoneName=Bones[I]; Skeleton->Sockets.Add(Socket); Skeleton->MarkPackageDirty();
        }
        Time+=Length;
    }
    Montage->BlendIn.SetBlendTime(.08f); Montage->BlendOut.SetBlendTime(.1f);
    Montage->RefreshCacheData(); Montage->PostEditChange(); Montage->MarkPackageDirty();
    return true;
#else
    return false;
#endif
}

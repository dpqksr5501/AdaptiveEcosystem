#include "AI/Behavior/EcoSpeciesAIExecution.h"
#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"
FVector EcoSpeciesAI::ResidentGoal(const FEcoSpeciesAIInputFragment& I,const FVector& Goal,const UEcoSpeciesAIProfile& P)
{
    if(I.RegionExtent.IsNearlyZero())return I.Position;
    FVector Local=I.RegionFrame.InverseTransformPosition(Goal);
    const FVector Scale=I.RegionFrame.GetScale3D().GetAbs();
    const float X=FMath::Max(0.f,float(I.RegionExtent.X)-P.BodyRadius/FMath::Max(.001f,float(Scale.X)));
    const float Y=FMath::Max(0.f,float(I.RegionExtent.Y)-P.BodyRadius/FMath::Max(.001f,float(Scale.Y)));
    Local.X=FMath::Clamp(Local.X,-X,X);Local.Y=FMath::Clamp(Local.Y,-Y,Y);
    return I.RegionFrame.TransformPosition(Local);
}
FVector EcoSpeciesAI::WanderGoal(const FEcoSpeciesAIInputFragment& I,FEcoSpeciesAIExecutionFragment& E,int64 Id,double Now,const UEcoSpeciesAIProfile& P)
{
    if(Now>=E.GoalUntil)
    {
        FRandomStream Random(int32(HashCombine(GetTypeHash(Id),GetTypeHash(int32(Now/5)))));
        const float Angle=Random.FRandRange(-PI,PI),Radius=Random.FRandRange(P.WanderRadius*.25f,P.WanderRadius);
        E.RetainedGoal=I.Home+FVector(FMath::Cos(Angle),FMath::Sin(Angle),0)*Radius;E.GoalUntil=Now+5;
    }
    return ResidentGoal(I,E.RetainedGoal,P);
}
void EcoSpeciesAI::ExecuteDeer(const FEcoSpeciesAIInputFragment& I,const FEcoSpeciesAIDecisionFragment& D,
    const UEcoSpeciesAIProfile& P,FEcoSpeciesAIExecutionFragment& E,FEcoSpeciesAIMoveFragment& M,
    UEcoSpeciesAIInteractionSubsystem* Slots,FMassEntityHandle Entity,int64 Id,FName Region,double Now,const FEcoPolicyActionV1& EffectiveAction)
{
    EEcoSpeciesActivity Mode=I.bThreat?EEcoSpeciesActivity::Flee:D.Activity;
    if(Mode==EEcoSpeciesActivity::Forage&&EffectiveAction.Forage<=KINDA_SMALL_NUMBER)Mode=EEcoSpeciesActivity::Hold;
    if(!I.bThreat&&I.CalmSince>=0&&Now-I.CalmSince<P.CalmSeconds
        &&(E.Activity==EEcoSpeciesActivity::Flee||E.Activity==EEcoSpeciesActivity::Recover||D.Activity==EEcoSpeciesActivity::Flee))Mode=EEcoSpeciesActivity::Recover;
    if(!I.bThreat&&Mode==EEcoSpeciesActivity::Flee)Mode=EEcoSpeciesActivity::Wander;
    if(E.Activity!=Mode){M.Hold(Now);E.GoalUntil=0;}
    const bool WantsSlot=Mode==EEcoSpeciesActivity::Forage||Mode==EEcoSpeciesActivity::Rest;
    const auto WantedKind=Mode==EEcoSpeciesActivity::Rest?EEcoActivitySlotKind::Rest:EEcoActivitySlotKind::Graze;
    if((!WantsSlot||E.SlotKind!=WantedKind)&&E.SlotReservation>0){if(Slots)Slots->Release(E.SlotReservation);E.SlotReservation=0;}
    if(Mode==EEcoSpeciesActivity::Flee)
    {
        FVector Away=(I.Position-I.CuePosition).GetSafeNormal2D();if(Away.IsNearlyZero())Away=FVector((Id&1)?1:-1,0,0);
        if(M.Status==EEcoAINavigationStatus::Failed)Away=Away.RotateAngleAxis((Id&1)?60:-60,FVector::UpVector);
        if(E.Activity!=EEcoSpeciesActivity::Flee||Now>=E.GoalUntil||M.Status==EEcoAINavigationStatus::Failed
            ||FVector::Dist2D(I.Position,E.RetainedGoal)<=P.ArrivalRadius)
        {E.RetainedGoal=I.Position+Away*P.WanderRadius*FMath::Lerp(.5f,1.5f,FMath::Clamp(EffectiveAction.FleeDist,0.f,1.f));E.GoalUntil=Now+2;}
        M.SetTarget(ResidentGoal(I,E.RetainedGoal,P),P.RunSpeed,P.ArrivalRadius,Now,P);
    }
    else if(WantsSlot&&Slots)
    {
        FVector Goal;
        if(E.SlotReservation>0&&!Slots->Renew(E.SlotReservation,Id,Now,P.SlotLease,Goal))
        {Slots->Release(E.SlotReservation);E.SlotReservation=0;E.NextSlotAttempt=Now+1;}
        if(M.Status==EEcoAINavigationStatus::Failed&&E.SlotReservation>0)
        {Slots->RejectUnreachable(E.SlotReservation,Now);E.SlotReservation=0;E.NextSlotAttempt=Now+1;}
        if(!E.SlotReservation&&Now>=E.NextSlotAttempt)
        {
            E.SlotKind=WantedKind;
            E.SlotReservation=Slots->Claim(Entity,Id,Region,false,WantedKind,I.Position,Now,P.SlotLease,Goal);E.NextSlotAttempt=Now+1;
        }
        if(E.SlotReservation>0)
        {
            if(FVector::Dist(I.Position,Goal)<=P.ArrivalRadius&&Slots->Occupy(E.SlotReservation,Id))
            {M.Hold(Now);if(Mode==EEcoSpeciesActivity::Forage)Mode=EEcoSpeciesActivity::Graze;}
            else M.SetTarget(Goal,P.WalkSpeed,P.ArrivalRadius,Now,P);
        }
        else M.Hold(Now);
    }
    else if(Mode==EEcoSpeciesActivity::Regroup&&I.bHasGroup)M.SetTarget(ResidentGoal(I,I.GroupPosition,P),P.WalkSpeed*FMath::Lerp(.5f,1.f,FMath::Clamp(EffectiveAction.Cohesion,0.f,1.f)),P.ArrivalRadius,Now,P);
    else if(Mode==EEcoSpeciesActivity::Wander)M.SetTarget(WanderGoal(I,E,Id,Now,P),P.WalkSpeed,P.ArrivalRadius,Now,P);
    else M.Hold(Now);
    E.Activity=M.Activity=Mode;E.AppliedDecision=D.Sequence;
}

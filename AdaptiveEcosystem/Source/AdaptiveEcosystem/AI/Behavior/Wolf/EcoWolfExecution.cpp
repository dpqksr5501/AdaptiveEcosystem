#include "AI/Behavior/EcoSpeciesAIExecution.h"
void EcoSpeciesAI::ExecuteWolf(const FEcoSpeciesAIInputFragment& I,const FEcoSpeciesAIDecisionFragment& D,
    const UEcoSpeciesAIProfile& P,FEcoSpeciesAIExecutionFragment& E,FEcoSpeciesAIMoveFragment& M,FEcoSpeciesAIAttackFragment& A,int64 AgentId,double Now)
{
    EEcoSpeciesActivity Mode=D.Activity;
    if(E.PursuitStarted>=0&&Now-E.PursuitStarted>P.PursuitSeconds)
    {
        E.RejectedTarget=E.PursuitTarget;E.TargetCooldownUntil=Now+P.SearchSeconds;
        E.PursuitStarted=-1;Mode=EEcoSpeciesActivity::Rest;
    }
    if(I.Target==E.RejectedTarget&&Now<E.TargetCooldownUntil
        &&(Mode==EEcoSpeciesActivity::Pursue||Mode==EEcoSpeciesActivity::Search))Mode=EEcoSpeciesActivity::Rest;
    if(Now<A.CooldownUntil)Mode=EEcoSpeciesActivity::Eat;
    if(E.Activity!=Mode)M.Hold(Now);
    const bool Hunting=Mode==EEcoSpeciesActivity::Pursue||Mode==EEcoSpeciesActivity::Search;
    if(Hunting&&I.Target.IsValid())
    {
        if(!(E.PursuitTarget==I.Target)||E.PursuitStarted<0){M.Hold(Now);E.PursuitTarget=I.Target;E.PursuitStarted=Now;}
        if((E.PursuitStarted>=0&&Now-E.PursuitStarted>P.PursuitSeconds)||M.Failures>=3)
        {
            E.RejectedTarget=I.Target;E.TargetCooldownUntil=Now+P.SearchSeconds;E.PursuitStarted=-1;
            M.Failures=0;M.Hold(Now);Mode=EEcoSpeciesActivity::Rest;
        }
        else if(I.bFreshSight&&Now-I.CueTime<=.25&&FVector::Dist2D(I.Position,I.CuePosition)<=P.AttackRadius*.9f&&Now>=A.CooldownUntil)
        {
            M.Hold(Now);Mode=EEcoSpeciesActivity::Attack;
            if(A.Requested==A.Resolved&&Now>=A.RetryAfter){A.Target=I.Target;A.RequestedAt=Now;++A.Requested;}
        }
        else if(FVector::Dist2D(I.Position,I.CuePosition)<=FMath::Max(100.f,P.ArrivalRadius)&&!I.bFreshSight)
        {
            E.RejectedTarget=I.Target;E.TargetCooldownUntil=Now+P.SearchSeconds;E.PursuitStarted=-1;
            Mode=EEcoSpeciesActivity::Search;M.Hold(Now);
        }
        else M.SetTarget(ResidentGoal(I,I.CuePosition,P),I.bFreshSight?P.RunSpeed:P.WalkSpeed,P.ArrivalRadius,Now,P);
    }
    else
    {
        E.PursuitStarted=-1;
        if(Mode==EEcoSpeciesActivity::Wander)M.SetTarget(WanderGoal(I,E,AgentId,Now,P),P.WalkSpeed,P.ArrivalRadius,Now,P);
        else if(Mode!=EEcoSpeciesActivity::Rest||E.SlotReservation==0)M.Hold(Now);
    }
    E.Activity=M.Activity=Mode;E.AppliedDecision=D.Sequence;
}

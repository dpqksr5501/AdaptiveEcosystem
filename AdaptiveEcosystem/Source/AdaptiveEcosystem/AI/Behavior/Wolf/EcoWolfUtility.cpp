#include "AI/Behavior/EcoSpeciesAIBehavior.h"
void EcoSpeciesAI::ScoreWolf(FEcoSpeciesAIInputFragment& I,const UEcoSpeciesAIProfile& P,
    const FEcoSpeciesAIExecutionFragment& E,const FEcoSpeciesAIAttackFragment& A)
{
    I.HoldScore=I.bValid?0.f:1.f;I.WanderScore=I.bValid?.15f:0;
    I.ForageScore=I.RegroupScore=I.FleeScore=0;I.RestScore=FMath::Clamp((I.Energy-.5f)*1.4f,0.f,.7f);
    I.EatScore=I.Now<A.CooldownUntil?1.f:0;
    const bool Rejected=I.Target==E.RejectedTarget&&I.Now<E.TargetCooldownUntil;
    const bool TimedOut=E.PursuitStarted>=0&&I.Now-E.PursuitStarted>P.PursuitSeconds;
    I.HuntScore=I.Target.IsValid()&&!Rejected&&!TimedOut&&I.bHungry?FMath::Clamp(.5f+(1-I.Energy)*.45f,0.f,1.f):0.f;
    I.SearchScore=I.HuntScore>0&&!I.bFreshSight?I.HuntScore:0.f;if(!I.bFreshSight)I.HuntScore=0;
    if(I.EatScore>0)I.WanderScore=I.RestScore=I.HuntScore=I.SearchScore=0;
}

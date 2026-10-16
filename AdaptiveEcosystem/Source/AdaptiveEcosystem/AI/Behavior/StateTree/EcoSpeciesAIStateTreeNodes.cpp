#include "AI/Behavior/StateTree/EcoSpeciesAIStateTreeNodes.h"
#include "MassStateTreeDependency.h"
#include "StateTreeLinker.h"
#include "AI/Behavior/EcoSpeciesAIBehavior.h"
bool FEcoSpeciesAIInputEvaluator::Link(FStateTreeLinker& L){L.LinkExternalData(InputHandle);return true;}
void FEcoSpeciesAIInputEvaluator::GetDependencies(UE::MassBehavior::FStateTreeDependencyBuilder& B) const{B.AddReadOnly(InputHandle);}
void FEcoSpeciesAIInputEvaluator::TreeStart(FStateTreeExecutionContext& C) const{Tick(C,0);}
void FEcoSpeciesAIInputEvaluator::Tick(FStateTreeExecutionContext& C,float) const
{
    const auto& I=C.GetExternalData(InputHandle); auto& S=C.GetInstanceData<FEcoSpeciesAIScores>(*this);
    S.Wander=I.WanderScore;S.Forage=I.ForageScore;S.Rest=I.RestScore;S.Flee=I.FleeScore;
    S.Regroup=I.RegroupScore;S.Hunt=I.HuntScore;S.Search=I.SearchScore;S.Eat=I.EatScore;S.Hold=I.HoldScore;
}
bool FEcoSpeciesAIDecisionTask::Link(FStateTreeLinker& L)
{L.LinkExternalData(InputHandle);L.LinkExternalData(DecisionHandle);L.LinkExternalData(ProfileHandle);L.LinkExternalData(RawHandle);return true;}
void FEcoSpeciesAIDecisionTask::GetDependencies(UE::MassBehavior::FStateTreeDependencyBuilder& B) const
{B.AddReadOnly(InputHandle).AddReadWrite(DecisionHandle).AddReadOnly(ProfileHandle).AddReadWrite(RawHandle);}
EStateTreeRunStatus FEcoSpeciesAIDecisionTask::EnterState(FStateTreeExecutionContext& C,const FStateTreeTransitionResult&) const
{
    auto& D=C.GetExternalData(DecisionHandle); const auto& I=C.GetExternalData(InputHandle);
    const auto Activity=C.GetInstanceData<FEcoSpeciesAITaskData>(*this).Activity;
    if(D.Activity!=Activity){D.Activity=Activity;D.EnteredAt=I.Now;++D.Sequence;}
    C.GetExternalData(RawHandle).Action=EcoSpeciesAI::MakeRawAction(I,Activity);
    return EStateTreeRunStatus::Running;
}
EStateTreeRunStatus FEcoSpeciesAIDecisionTask::Tick(FStateTreeExecutionContext& C,float) const
{
    const auto& I=C.GetExternalData(InputHandle);const auto& D=C.GetExternalData(DecisionHandle);
    const auto* P=C.GetExternalData(ProfileHandle).Profile.Get();
    if(!P) return EStateTreeRunStatus::Failed;
    C.GetExternalData(RawHandle).Action=EcoSpeciesAI::MakeRawAction(I,D.Activity);
    // Completion reselects the utility root. No world/service calls on the StateTree worker.
    if(P->bPolicyOnly || !I.bValid || (D.Activity==EEcoSpeciesActivity::Hold&&I.bValid) || (I.bThreat && D.Activity!=EEcoSpeciesActivity::Flee && !I.bPredator)
        || I.EatScore>0 || I.Now-D.EnteredAt>=P->MinimumDwell) return EStateTreeRunStatus::Succeeded;
    return EStateTreeRunStatus::Running;
}

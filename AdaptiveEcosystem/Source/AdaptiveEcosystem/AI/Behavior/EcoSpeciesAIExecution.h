#pragma once
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "Mass/EntityHandle.h"
class UEcoSpeciesAIInteractionSubsystem;
namespace EcoSpeciesAI
{
    FVector ResidentGoal(const FEcoSpeciesAIInputFragment& Input,const FVector& Goal,const UEcoSpeciesAIProfile& Profile);
    void ExecuteDeer(const FEcoSpeciesAIInputFragment& Input,const FEcoSpeciesAIDecisionFragment& Decision,
        const UEcoSpeciesAIProfile& Profile,FEcoSpeciesAIExecutionFragment& Execution,FEcoSpeciesAIMoveFragment& Move,
        UEcoSpeciesAIInteractionSubsystem* Slots,FMassEntityHandle Entity,int64 AgentId,FName Region,double Now,const FEcoPolicyActionV1& EffectiveAction);
    void ExecuteWolf(const FEcoSpeciesAIInputFragment& Input,const FEcoSpeciesAIDecisionFragment& Decision,
        const UEcoSpeciesAIProfile& Profile,FEcoSpeciesAIExecutionFragment& Execution,FEcoSpeciesAIMoveFragment& Move,
        FEcoSpeciesAIAttackFragment& Attack,int64 AgentId,double Now);
    FVector WanderGoal(const FEcoSpeciesAIInputFragment& Input,FEcoSpeciesAIExecutionFragment& Execution,
        int64 AgentId,double Now,const UEcoSpeciesAIProfile& Profile);
}

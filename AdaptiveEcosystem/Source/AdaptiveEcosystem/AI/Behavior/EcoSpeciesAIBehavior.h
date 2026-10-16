#pragma once
#include "AI/Behavior/EcoSpeciesAIFragments.h"
namespace EcoSpeciesAI
{
    void ScoreDeer(FEcoSpeciesAIInputFragment& Input,const UEcoSpeciesAIProfile& Profile);
    void ScoreWolf(FEcoSpeciesAIInputFragment& Input,const UEcoSpeciesAIProfile& Profile,
        const FEcoSpeciesAIExecutionFragment& Execution,const FEcoSpeciesAIAttackFragment& Attack);
    FEcoPolicyActionV1 MakeRawAction(const FEcoSpeciesAIInputFragment& Input,EEcoSpeciesActivity Activity);
}

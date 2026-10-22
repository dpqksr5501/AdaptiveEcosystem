#include "AI/Behavior/EcoSpeciesAIBehavior.h"
void EcoSpeciesAI::ScoreDeer(FEcoSpeciesAIInputFragment& I,const UEcoSpeciesAIProfile& P)
{
    I.HoldScore=I.bValid?0.f:1.f;I.WanderScore=I.bValid?.12f:0.f;
    I.ForageScore=I.bFoodAvailable?FMath::Clamp((1-I.Energy)*(I.bHungry?1.5f:1.f),0.f,1.f):0.f;
    I.RestScore=I.bThreat?0.f:FMath::Clamp((I.Energy-.5f)*1.5f,0.f,.75f);
    I.RegroupScore=I.bHasGroup?.3f:0.f;I.FleeScore=I.bThreat?1.f:0.f;
    if(I.bThreat&&!P.bPolicyOnly){I.ForageScore=I.RestScore=I.RegroupScore=I.WanderScore=0;}
    I.HuntScore=I.SearchScore=I.EatScore=0;
}
FEcoPolicyActionV1 EcoSpeciesAI::MakeRawAction(const FEcoSpeciesAIInputFragment& I,EEcoSpeciesActivity Activity)
{
    FEcoPolicyActionV1 A;
    A.Forage=Activity==EEcoSpeciesActivity::Forage?FMath::Clamp(1-I.Energy,.1f,1.f):0.f;
    A.Cohesion=Activity==EEcoSpeciesActivity::Regroup?.9f:.15f;
    A.FleeDist=I.bThreat?1.f:.25f;A.Cover=I.bThreat?.9f:0.f;return A;
}

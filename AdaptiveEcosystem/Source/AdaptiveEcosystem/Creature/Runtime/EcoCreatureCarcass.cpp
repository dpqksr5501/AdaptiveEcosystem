#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "Mass/EcoMassFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"

void AEcoCreatureIntegrationSpawner::CommitNativeCarcass(const FEcoDeathOutcome& Death)
{
    auto& EM=GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Victim=AgentLookup.Find(Death.StableAgentId);if(!Victim||!EM.IsEntityValid(*Victim))return;
    auto* SourceLink=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(*Victim);if(!SourceLink||!SourceLink->Individual.bInitialized)return;
    SourceLink->Individual.AbandonMeat();
    if(Death.Cause!=EEcoDeathCause::Predation||Death.PredatorStableAgentId<=0)return;
    const auto* Body=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(*Victim);
    const auto* Primary=AgentLookup.Find(Death.PredatorStableAgentId);
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const auto* Context=Native?Native->GetContext(SourceLink->ContextIndex):nullptr;
    if(!Body||!Primary||!EM.IsEntityValid(*Primary)||!Context)return;
    const double Now=Context->Sim.T*EcoRepertoireV3::kStepSeconds;
    TArray<FMassEntityHandle> Receivers;
    for(const auto Entity:Owned){
        if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP<=0)continue;
        const auto* Wolf=EM.GetFragmentDataPtr<FEcoThreatStateFragment>(Entity);const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
        if(!Wolf||!Link||Link->bDead||!Link->bAdopted||Link->ContextIndex!=SourceLink->ContextIndex||!Link->Individual.bInitialized)continue;
        const auto& Life=Link->Individual;
        const bool Contributor=Entity==*Primary||(Life.LastHuntTarget==Death.StableAgentId&&Now>=Life.LastHuntTime&&Now-Life.LastHuntTime<=5);
        if(!Contributor||FMath::Square(Wolf->Agent.State.PosX-Body->Body.Pos.X)+FMath::Square(Wolf->Agent.State.PosY-Body->Body.Pos.Y)>144)continue;
        Receivers.Add(Entity);
    }
    if(Receivers.IsEmpty())return;
    const double Share=.6/Receivers.Num();double Issued=0;
    for(const auto Entity:Receivers){auto& Life=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Entity).Individual;
        if(Life.AssignMeat(Death.StableAgentId,Share,Now,Body->Body.Pos.X,Body->Body.Pos.Y,SourceLink->GroundZ))Issued+=Share;
    }
    UE_LOG(LogTemp,Log,TEXT("[EcoLife][Carcass] Prey=%lld Primary=%lld Receivers=%d NutritionIssued=%.9f Ledger=MeatNotVegetation"),
        Death.StableAgentId,Death.PredatorStableAgentId,Receivers.Num(),Issued);
}

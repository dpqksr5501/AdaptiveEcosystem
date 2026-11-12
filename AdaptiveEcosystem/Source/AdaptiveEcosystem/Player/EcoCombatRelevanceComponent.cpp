#include "Player/EcoCombatRelevanceComponent.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Network/Mass/EcoMassClientBubble.h"
#include "Core/EcoRuntimeSettings.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "EngineUtils.h"
#include "Net/UnrealNetwork.h"
UEcoCombatRelevanceComponent::UEcoCombatRelevanceComponent()
{ SetIsReplicatedByDefault(true); PrimaryComponentTick.bCanEverTick=true; }
void UEcoCombatRelevanceComponent::TickComponent(float Delta,ELevelTick Type,FActorComponentTickFunction* Tick)
{
    Super::TickComponent(Delta,Type,Tick);
    auto* P=Cast<APawn>(GetOwner()); if (!P || !P->IsPlayerControlled()) { Ready.Reset(); return; }
    const double Now=GetWorld()->GetRealTimeSeconds();
    if (P->HasAuthority() && Now>=NextRefresh)
    {
        NextRefresh=Now+.1; FEcoCombatOffer Next;
        for (TActorIterator<AEcoCreatureIntegrationSpawner> It(GetWorld());It;++It)
        {
            if (!It->bEnablePlayerCombat || !It->IsRuntimeReady()) continue;
            if (Next.Coordinator) { Next=FEcoCombatOffer(); break; } // Ambiguous world: fail closed.
            Next.Coordinator=*It;
            It->GetCombatCandidates(*P,Next.Epoch,Next.Agents);
        }
        if (!P->IsLocallyControlled())
        {
            TSet<int64> Admitted;
            for (TActorIterator<AEcoMassClientBubbleInfo> It(GetWorld());It;++It)
                if (It->GetOwner()==P->GetController())
                    for (const auto& Item:It->GetSerializer().GetAgentItems()) Admitted.Add(Item.Agent.GetStableAgentId());
            Next.Agents.RemoveAll([&](int64 Id){return !Admitted.Contains(Id);});
        }
        if (Next.Coordinator!=Offer.Coordinator || Next.Epoch!=Offer.Epoch || Next.Agents!=Offer.Agents)
        {
            UpdateOffer(MoveTemp(Next));
            GetOwner()->ForceNetUpdate(); if (P->IsLocallyControlled()) ReportPresented();
        }
    }
    if (P->IsLocallyControlled() && Now>=NextReport) { NextReport=Now+.2; ReportPresented(); }
}
void UEcoCombatRelevanceComponent::UpdateOffer(FEcoCombatOffer Next)
{
    if (Next.Coordinator!=Offer.Coordinator || Next.Epoch!=Offer.Epoch)
    {
        Presented.Reset();
        Ready.Reset();
        LastReady=-10;
    }
    else
    {
        // Keep the acknowledgement for targets continuously offered in this epoch.
        for (auto It=Ready.CreateIterator(); It; ++It)
            if (!Next.Agents.Contains(*It)) It.RemoveCurrent();
    }
    Next.Revision=Offer.Revision+1;
    Offer=MoveTemp(Next);
}
void UEcoCombatRelevanceComponent::SetPresented(AEcoCreatureIntegrationSpawner* C,const TArray<int64>& Ids)
{
    if (C!=Offer.Coordinator) return;
    const bool Changed=Presented!=Ids; Presented=Ids;
    if (Changed) ReportPresented();
}
void UEcoCombatRelevanceComponent::OnRep_Offer(const FEcoCombatOffer& Previous)
{
    if (Previous.Coordinator!=Offer.Coordinator || Previous.Epoch!=Offer.Epoch) Presented.Reset();
    ReportPresented();
}
void UEcoCombatRelevanceComponent::ReportPresented()
{
    const auto* P=Cast<APawn>(GetOwner()); if (!P || !P->IsLocallyControlled()) return;
    TArray<int64> Intersection;
    for (int64 Id:Presented) if (Offer.Agents.Contains(Id)) Intersection.Add(Id);
    ServerPresented(Offer.Revision,Intersection);
}
void UEcoCombatRelevanceComponent::ServerPresented_Implementation(uint32 Revision,const TArray<int64>& Ids)
{
    if (Revision!=Offer.Revision || Ids.Num()>Offer.Agents.Num()) return;
    Ready.Reset(); for (int64 Id:Ids) if (Offer.Agents.Contains(Id)) Ready.Add(Id);
    LastReady=GetWorld()->GetRealTimeSeconds();
}
bool UEcoCombatRelevanceComponent::CanAttack(const AEcoCreatureIntegrationSpawner* C,int32 Epoch,int64 Id) const
{
    return GetOwner()->HasAuthority() && C && Offer.Coordinator==C && Epoch>0 && Offer.Epoch==Epoch
        && Offer.Agents.Contains(Id) && Ready.Contains(Id) && GetWorld()->GetRealTimeSeconds()-LastReady<=.75;
}
void UEcoCombatRelevanceComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{ Super::GetLifetimeReplicatedProps(OutLifetimeProps); DOREPLIFETIME_CONDITION(UEcoCombatRelevanceComponent,Offer,COND_OwnerOnly); }

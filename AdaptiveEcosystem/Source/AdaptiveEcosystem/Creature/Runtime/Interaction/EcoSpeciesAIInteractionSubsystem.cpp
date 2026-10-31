#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"
#include "AI/Behavior/EcoSpeciesAIActors.h"
#include "SmartObjectSubsystem.h"
#include "SmartObjectComponent.h"
#include "SmartObjectRequestTypes.h"
#include "MassSmartObjectBehaviorDefinition.h"
#include "Mass/EcoMassFragments.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
bool UEcoSpeciesAIInteractionSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{const UWorld* W=Cast<UWorld>(Outer);return W&&W->IsGameWorld()&&W->GetNetMode()!=NM_Client&&Super::ShouldCreateSubsystem(Outer);}
namespace { FIntPoint SiteCell(const FVector& P){return {int32(FMath::FloorToInt(P.X/2000)),int32(FMath::FloorToInt(P.Y/2000))};} }
void UEcoSpeciesAIInteractionSubsystem::RegisterSite(AEcoSpeciesAIActivitySite& Site)
{check(IsInGameThread());Sites.AddUnique(&Site);SiteCells.FindOrAdd(SiteCell(Site.GetActorLocation())).AddUnique(&Site);}
void UEcoSpeciesAIInteractionSubsystem::GatherSites(const FVector& P,TArray<AEcoSpeciesAIActivitySite*>& Results) const
{
    const FIntPoint Center=SiteCell(P);
    for(int32 X=-3;X<=3;++X)for(int32 Y=-3;Y<=3;++Y)
        if(const auto* Cell=SiteCells.Find(Center+FIntPoint(X,Y)))for(const auto& Weak:*Cell)
            if(auto* Site=Weak.Get())Results.Add(Site);
}
void UEcoSpeciesAIInteractionSubsystem::UnregisterSite(AEcoSpeciesAIActivitySite& Site)
{
    TArray<int64> Remove;for(const auto& P:Reservations)if(P.Value.Site.Get()==&Site)Remove.Add(P.Key);
    for(int64 Id:Remove)Release(Id);Sites.Remove(&Site);
    for(auto It=SiteCells.CreateIterator();It;++It){It.Value().Remove(&Site);if(It.Value().IsEmpty())It.RemoveCurrent();}
}
int64 UEcoSpeciesAIInteractionSubsystem::RegisterFixture(AEcoSpeciesAIFixture& F){Fixtures.AddUnique(&F);return NextFixture++;}
void UEcoSpeciesAIInteractionSubsystem::UnregisterFixture(AEcoSpeciesAIFixture& F){Fixtures.Remove(&F);}
AEcoSpeciesAIFixture* UEcoSpeciesAIInteractionSubsystem::FindFixture(int64 Id) const
{for(const auto& F:Fixtures)if(F.IsValid()&&F->FixtureId==Id)return F.Get();return nullptr;}
bool UEcoSpeciesAIInteractionSubsystem::FindSite(FName Region,bool Predator,EEcoActivitySlotKind Kind,const FVector& P,FVector& Goal) const
{
    float Best=FMath::Square(6000.f);bool Found=false;
    TArray<AEcoSpeciesAIActivitySite*> Nearby;GatherSites(P,Nearby);
    for(const auto* S:Nearby)if(S->RegionId==Region&&S->bForPredator==Predator&&S->Kind==Kind)
    {const float D=FVector::DistSquared(P,S->GetActorLocation());if(D<Best){Best=D;Goal=S->GetActorLocation();Found=true;}}
    return Found;
}
int64 UEcoSpeciesAIInteractionSubsystem::Claim(FMassEntityHandle Entity,int64 AgentId,FName Region,bool Predator,
    EEcoActivitySlotKind Kind,const FVector& P,double Now,float Lease,FVector& Goal)
{
    check(IsInGameThread());auto* SO=GetWorld()->GetSubsystem<USmartObjectSubsystem>();if(!SO||AgentId<=0)return 0;
    TArray<AEcoSpeciesAIActivitySite*> Candidates;
    TArray<AEcoSpeciesAIActivitySite*> Nearby;GatherSites(P,Nearby);
    for(auto* S:Nearby)if(S->RegionId==Region&&S->bForPredator==Predator&&S->Kind==Kind
        &&FVector::DistSquared(P,S->GetActorLocation())<=FMath::Square(6000.f))Candidates.Add(S);
    Candidates.Sort([&](const auto& A,const auto& B){return FVector::DistSquared(P,A.GetActorLocation())<FVector::DistSquared(P,B.GetActorLocation());});
    for(auto* Site:Candidates)
    {
        if(RejectedSites.ContainsByPredicate([&](const FRejectedSite& R){return R.AgentId==AgentId&&R.Site.Get()==Site&&R.Until>Now;}))continue;
        FSmartObjectRequest Request;
        Request.QueryBox=FBox::BuildAABB(Site->GetActorLocation(),FVector(1000));
        const auto Handle=Site->SmartObject->GetRegisteredHandle();
        Request.Filter.Predicate=[Handle](FSmartObjectHandle Other){return Other==Handle;};
        Request.Filter.BehaviorDefinitionClasses.Add(USmartObjectMassBehaviorDefinition::StaticClass());
        TArray<FSmartObjectRequestResult> Results;SO->FindSmartObjects(Request,Results,FConstStructView());
        for(const auto& Result:Results)
        {
            const auto SlotPosition=SO->GetSlotLocation(Result);if(!SlotPosition.IsSet())continue;
            const auto Claim=SO->MarkSlotAsClaimed(Result.SlotHandle,ESmartObjectClaimPriority::Normal);
            if(!Claim.IsValid())continue;
            const int64 Id=NextReservation++;
            Reservations.Add(Id,{AgentId,Entity,Site,Claim,Now+Lease,false});
            SO->RegisterSlotInvalidationCallback(Claim,FOnSlotInvalidated::CreateWeakLambda(this,[this,Id](const FSmartObjectClaimHandle&,ESmartObjectSlotState)
            {InvalidatedReservations.Add(Id);}));
            Goal=SlotPosition.GetValue();++Claims;return Id;
        }
    }
    return 0;
}
bool UEcoSpeciesAIInteractionSubsystem::Renew(int64 Id,int64 AgentId,double Now,float Lease,FVector& Goal)
{
    auto* R=Reservations.Find(Id);auto* SO=GetWorld()->GetSubsystem<USmartObjectSubsystem>();
    if(!R||InvalidatedReservations.Contains(Id)||R->AgentId!=AgentId||R->Expires<=Now||!R->Site.IsValid()||!SO||!SO->IsClaimedSmartObjectValid(R->Handle))return false;
    const auto Position=SO->GetSlotLocation(R->Handle);if(!Position.IsSet())return false;
    R->Expires=Now+Lease;Goal=Position.GetValue();return true;
}
bool UEcoSpeciesAIInteractionSubsystem::Occupy(int64 Id,int64 AgentId)
{
    auto* R=Reservations.Find(Id);auto* SO=GetWorld()->GetSubsystem<USmartObjectSubsystem>();
    if(!R||InvalidatedReservations.Contains(Id)||R->AgentId!=AgentId||!SO||!SO->IsClaimedSmartObjectValid(R->Handle))return false;
    if(!R->bOccupied){if(!SO->MarkSlotAsOccupied<USmartObjectMassBehaviorDefinition>(R->Handle))return false;R->bOccupied=true;}
    return true;
}
void UEcoSpeciesAIInteractionSubsystem::Release(int64 Id)
{
    if(auto* R=Reservations.Find(Id))
    {
        if(auto* SO=GetWorld()->GetSubsystem<USmartObjectSubsystem>();SO&&SO->IsClaimedSmartObjectValid(R->Handle))
        {SO->UnregisterSlotInvalidationCallback(R->Handle);if(!InvalidatedReservations.Contains(Id))SO->MarkSlotAsFree(R->Handle);}
        Reservations.Remove(Id);InvalidatedReservations.Remove(Id);++Releases;
    }
}
void UEcoSpeciesAIInteractionSubsystem::Cleanup(FMassEntityManager& EM,double Now)
{
    RejectedSites.RemoveAll([Now](const FRejectedSite& R){return R.Until<=Now||!R.Site.IsValid();});
    TArray<int64> Remove;
    for(const auto& Pair:Reservations)
    {
        const auto& R=Pair.Value;const auto* V=EM.IsEntityValid(R.Entity)?EM.GetFragmentDataPtr<FEcoVitalsFragment>(R.Entity):nullptr;
        auto* SO=GetWorld()->GetSubsystem<USmartObjectSubsystem>();
        const auto* Region=V?EM.GetFragmentDataPtr<FEcoRegionFragment>(R.Entity):nullptr;
        if(!V||V->HP<=0||!R.Site.IsValid()||InvalidatedReservations.Contains(Pair.Key)||R.Expires<=Now
            ||!Region||Region->CurrentRegionId!=R.Site->RegionId||!SO||!SO->IsClaimedSmartObjectValid(R.Handle))Remove.Add(Pair.Key);
    }
    for(int64 Id:Remove)Release(Id);
}
void UEcoSpeciesAIInteractionSubsystem::RejectUnreachable(int64 Id,double Now)
{
    if(const auto* R=Reservations.Find(Id);R&&RejectedSites.Num()<1024)RejectedSites.Add({R->AgentId,R->Site,Now+10});
    Release(Id);
}
void UEcoSpeciesAIInteractionSubsystem::QueueFixtureReward(int64 AgentId,float Units,double EligibleAt)
{
    if(AgentId>0&&FMath::IsFinite(Units)&&Units>=0&&FMath::IsFinite(EligibleAt))
    {FixtureRewards.Add({AgentId,NextReceipt++,Units,EligibleAt});++FixtureCaptures;}
}
void UEcoSpeciesAIInteractionSubsystem::DrainFixtureRewards(double Through,TArray<FFixtureReward>& Results)
{
    for(const auto& R:FixtureRewards)if(R.EligibleAt<=Through)Results.Add(R);
    FixtureRewards.RemoveAll([Through](const auto& R){return R.EligibleAt<=Through;});
}
void UEcoSpeciesAIInteractionSubsystem::Deinitialize()
{TArray<int64> Ids;Reservations.GetKeys(Ids);for(int64 Id:Ids)Release(Id);Sites.Reset();SiteCells.Reset();InvalidatedReservations.Reset();RejectedSites.Reset();Fixtures.Reset();FixtureRewards.Reset();Super::Deinitialize();}

#include "Mass/EcoHerdMigration.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "MassEntityManager.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "Algo/Reverse.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Components/SceneComponent.h"

DEFINE_LOG_CATEGORY_STATIC(LogEcoHerdMigration,Log,All);
static TAutoConsoleVariable<int32> CVarHerdMigration(TEXT("eco.HerdMigration"),-1,TEXT("Native herd journeys: -1 uses the authored runtime opt-in, 0 stops new departures, 1 enables. Existing journeys finish safely."));
static TAutoConsoleVariable<float> CVarShortage(TEXT("eco.HerdMigration.ShortageFraction"),.25f,TEXT("Remaining native food fraction that starts sustained shortage."));
static TAutoConsoleVariable<float> CVarDwell(TEXT("eco.HerdMigration.ShortageSeconds"),8.f,TEXT("Seconds of continuous shortage before group departure."));
static TAutoConsoleVariable<float> CVarCooldown(TEXT("eco.HerdMigration.SettleSeconds"),45.f,TEXT("Minimum residence after a journey."));
static TAutoConsoleVariable<float> CVarTimeout(TEXT("eco.HerdMigration.StallSeconds"),25.f,TEXT("No-progress timeout; marks the journey blocked without teleporting."));

AEcoHerdMigrationRoute::AEcoHerdMigrationRoute(){PrimaryActorTick.bCanEverTick=false;SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("RouteRoot")));}
bool UEcoHerdMigrationSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{ const auto* W=Cast<UWorld>(Outer);return W&&W->IsGameWorld()&&W->GetNetMode()!=NM_Client; }
bool UEcoHerdMigrationSubsystem::IsEnabled() const {
    const int32 Mode=CVarHerdMigration.GetValueOnGameThread();if(Mode>=0)return Mode!=0;
    for(TActorIterator<AEcoCreatureIntegrationSpawner> It(GetWorld());It;++It)if(It->bEnableHerdJourneys)return true;
    return false;
}
bool UEcoHerdMigrationSubsystem::ApplyFoodFractionForAudit(FName Region,float Fraction,bool bSuspendRegeneration){
#if !UE_BUILD_SHIPPING
    if(GetWorld()->GetNetMode()==NM_Client||!GetWorld()->GetOutermost()->GetName().StartsWith(TEXT("/Game/JYU/Maps/"))
        ||!FMath::IsFinite(Fraction)||Fraction<0||Fraction>1)return false;
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* E=GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();auto* C=Native&&Native->IsActive()?Native->FindContext(Region):nullptr;
    if(!C||!C->bSpatialFoodRegistered||!E)return false;
    const double Before=C->Sim.Food.Total();double Capacity=0;for(const double Cap:C->Sim.Food.Cap)Capacity+=Cap;
    const double After=Before*Fraction;
    if(!E->AdjustSpatialFoodHabitat(Region,++C->ResourceReceiptSequence,Before,Before-After,Capacity,After))return false;
    for(double& Food:C->Sim.Food.Food)Food*=Fraction;
    if(bSuspendRegeneration){C->Sim.Config.FoodRegenBase=0;for(double& Regen:C->Sim.Food.Regen)Regen=0;}
    UE_LOG(LogEcoHerdMigration,Log,TEXT("[HerdMigration][AuditFoodLoss] Region=%s Before=%.6f After=%.6f SuspendRegen=%d"),*Region.ToString(),Before,After,bSuspendRegeneration);
    return true;
#else
    return false;
#endif
}
#if !UE_BUILD_SHIPPING
static FAutoConsoleCommandWithWorldAndArgs TestHerdDrought(TEXT("eco.HerdMigration.Test.Drought"),
    TEXT("Owned JYU map test only: drought <RegionId> removes native food with a ledger receipt and suspends regeneration. Restart Play to reset."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World){
        auto* Migration=World?World->GetSubsystem<UEcoHerdMigrationSubsystem>():nullptr;
        if(!Migration||Args.Num()!=1||!Migration->ApplyFoodFractionForAudit(FName(*Args[0]),0,true))
            UE_LOG(LogEcoHerdMigration,Warning,TEXT("[HerdMigration] Drought fixture rejected (owned authority map and region required)."));
    }));
#endif
const TCHAR* UEcoHerdMigrationSubsystem::StateName(EEcoHerdJourneyState S)
{
    switch(S){case EEcoHerdJourneyState::Preparing:return TEXT("Preparing");case EEcoHerdJourneyState::Traveling:return TEXT("Traveling");
    case EEcoHerdJourneyState::Resting:return TEXT("Resting");case EEcoHerdJourneyState::Regrouping:return TEXT("Regrouping");
    case EEcoHerdJourneyState::Settled:return TEXT("Settled");default:return TEXT("Blocked");}
}

bool UEcoHerdMigrationSubsystem::Reconcile(FMassEntityManager& Manager,const FEcoServerTimeSnapshot& Time,int64 Step,TArray<FEcoMigrationOutcome>& Arrivals)
{
    if(!IsInGameThread()||Manager.IsProcessing()||GetWorld()->GetNetMode()==NM_Client)return false;
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ecology=GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    auto* Herds=GetWorld()->GetSubsystem<UEcoHerdSubsystem>();
    if(!Native||!Native->IsActive()||!Ecology||!Herds)return true;
    // Existing journeys finish even if new departures are disabled at runtime.
    if(!IsEnabled()&&Plans.IsEmpty())return true;
    const double Now=Time.ServerTimeSeconds;
    struct FMember { int64 Id=0,Herd=0;FEcoRegionFragment* Region=nullptr;FEcoTravelFragment* Travel=nullptr;
        FEcoHerdTravelFragment* Journey=nullptr;FEcoIntegratedV3Fragment* Link=nullptr;FEcoHerbivoreBodyV3Fragment* Body=nullptr;
        FEcoBehaviorStateFragment* Behavior=nullptr;FVector Position;FMassEntityHandle Entity; };
    TArray<FMember> Agents;
    FMassEntityQuery Query(Manager.AsShared());
    Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoHerdTravelFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoBehaviorStateFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
    auto Context=Manager.CreateExecutionContext(0);
    Query.ForEachEntityChunk(Context,[&](FMassExecutionContext& C){
        const auto Ids=C.GetFragmentView<FEcoIdentityFragment>();const auto Members=C.GetFragmentView<FEcoHerdMemberFragment>();
        auto Regions=C.GetMutableFragmentView<FEcoRegionFragment>();auto Travels=C.GetMutableFragmentView<FEcoTravelFragment>();
        auto Js=C.GetMutableFragmentView<FEcoHerdTravelFragment>();auto Links=C.GetMutableFragmentView<FEcoIntegratedV3Fragment>();
        auto Bodies=C.GetMutableFragmentView<FEcoHerbivoreBodyV3Fragment>();auto Behaviors=C.GetMutableFragmentView<FEcoBehaviorStateFragment>();
        for(int32 I=0;I<C.GetNumEntities();++I){
            auto* R=Native->GetContext(Links[I].ContextIndex);FEcoHerdRuntimeData H;
            const bool HasHerd=Herds->GetHerdData(Members[I].HerdRuntimeIndex,H);
            if(!Links[I].bAdopted||Links[I].bDead||Bodies[I].Body.DeathCause!=EcoWorldV3::kDeathNone||!R
                ||(!HasHerd&&!Js[I].bActive))continue;
            FMember A;A.Id=Ids[I].StableAgentId;A.Herd=Js[I].bActive?Js[I].PersistentHerdId:H.PersistentHerdId;A.Region=&Regions[I];A.Travel=&Travels[I];
            A.Journey=&Js[I];A.Link=&Links[I];A.Body=&Bodies[I];A.Behavior=&Behaviors[I];A.Entity=C.GetEntity(I);
            A.Position=R->UnitsToCm(Bodies[I].Body.Pos.X,Bodies[I].Body.Pos.Y,Links[I].GroundZ);Agents.Add(A);
        }
    });
    Agents.Sort([](const FMember& A,const FMember& B){return A.Id<B.Id;});
    TMap<int64,TArray<int32>> Groups;TMap<int64,int32> ById;
    for(int32 I=0;I<Agents.Num();++I){Groups.FindOrAdd(Agents[I].Herd).Add(I);ById.Add(Agents[I].Id,I);}
    auto Change=[&](FEcoHerdJourney& P,EEcoHerdJourneyState State,FName Reason){
        if(P.State!=State||P.Reason!=Reason){P.State=State;P.Reason=Reason;P.Changed=Now;
            UE_LOG(LogEcoHerdMigration,Log,TEXT("[HerdMigration] Plan=%lld Herd=%lld State=%s Reason=%s From=%s To=%s Arrived=%d/%d"),
                P.Id,P.HerdId,StateName(State),*Reason.ToString(),*P.Origin.ToString(),*P.Destination.ToString(),P.Arrived,P.Members.Num());}
    };
    for(auto& Entry:Plans){
        auto& P=Entry.Value;if(P.State==EEcoHerdJourneyState::Settled)continue;
        auto* Target=Native->FindContext(P.Destination);if(!Target)return false;
        const bool DestinationEmpty=Target->Sim.Food.Total()<.5;
        bool NeedsReturn=DestinationEmpty;
        for(const int64 Id:P.Members)if(const auto* K=ById.Find(Id)){
            const auto& J=*Agents[*K].Journey;
            NeedsReturn|=J.bActive&&Now-J.LastProgressTime>2*FMath::Max(5.f,CVarTimeout.GetValueOnGameThread());
        }
        if(NeedsReturn&&!P.bReturning){
            P.bReturning=true;P.Destination=P.Origin;Algo::Reverse(P.Points);Target=Native->FindContext(P.Origin);
            if(!Target)return false;
            for(const int64 Id:P.Members)if(const auto* K=ById.Find(Id)){
                auto& A=Agents[*K];if(!A.Journey->bActive)continue;
                int32 Nearest=0;double Best=MAX_dbl;
                for(int32 I=0;I<P.Points.Num();++I){const double D=FVector::DistSquared2D(A.Position,P.Points[I]);if(D<Best){Nearest=I;Best=D;}}
                A.Journey->Waypoint=Nearest;A.Journey->BestDistance=MAX_dbl;A.Journey->LastProgressTime=Now;
                A.Travel->TargetRegionId=P.Origin;A.Travel->TargetRegionIndex=Target->RegionRuntimeIndex;A.Travel->TargetPosition=P.Points.Last();
            }
            Change(P,EEcoHerdJourneyState::Regrouping,DestinationEmpty?TEXT("DestinationDepletedReturn"):TEXT("BlockedRouteReturn"));
        }
        P.Arrived=P.Dead=P.Failed=0;FVector Center=FVector::ZeroVector;int32 Live=0;
        for(const int64 Id:P.Members){const auto* K=ById.Find(Id);if(!K){++P.Dead;continue;}Center+=Agents[*K].Position;++Live;}
        if(Live)Center/=Live;
        int32 ReadyAtRally=0;
        for(const int64 Id:P.Members)if(const auto* K=ById.Find(Id))ReadyAtRally+=FVector::Dist2D(Agents[*K].Position,P.Points[0])<FMath::Max(500.f,P.CorridorWidth);
        const bool Preparing=P.State==EEcoHerdJourneyState::Preparing&&Now-P.Started<6&&ReadyAtRally<FMath::CeilToInt(Live*.7);
        bool Rest=false,Spread=false;
        for(const int64 Id:P.Members)if(const auto* K=ById.Find(Id)){
            const auto& A=Agents[*K];if(!A.Journey->bActive)continue;
            Rest|=A.Body->Body.Energy<.08&&Now-P.Started>12&&FMath::Fmod(Now-P.Started,30.)<4;
            Spread|=FVector::Dist2D(A.Position,Center)>3500;
        }
        for(const int64 Id:P.Members){
            const auto* K=ById.Find(Id);if(!K)continue;auto& A=Agents[*K];auto& J=*A.Journey;
            J.MembershipUntil=GetWorld()->GetTimeSeconds()+10;
            if(!J.bActive){++P.Arrived;continue;}
            const int32 Last=P.Points.Num()-1;
            if(!Preparing&&J.Waypoint<Last&&FVector::Dist2D(A.Position,P.Points[J.Waypoint])<FMath::Max(250.f,P.CorridorWidth*.7f)){
                ++J.Waypoint;J.BestDistance=MAX_dbl;J.LastProgressTime=Now;
            }
            const FVector Finish=P.Points.Last();const auto Local=Target->CmToUnits(A.Position);
            const bool InsideTarget=Local.X>=0&&Local.Y>=0&&Local.X<=Target->Sim.Config.WorldSize&&Local.Y<=Target->Sim.Config.WorldSize;
            if(InsideTarget&&A.Region->CurrentRegionId!=P.Destination){
                FEcoMigrationOutcome O;O.WorldEpoch=Time.WorldEpoch;O.StepId=Step;O.StableAgentId=A.Id;
                O.OriginRegionId=A.Region->CurrentRegionId;O.DestinationRegionId=P.Destination;O.Reason=EEcoMigrationReason::FoodShortage;
                O.DepartureTime=A.Travel->DepartureTime;O.ArrivalTime=Now;
                // Context rebase preserves actual world position, identity, energy, reserve and herd.
                A.Body->Body.Pos=A.Body->Body.PrevPos=Local;A.Body->Body.Detour={};
                A.Link->ContextIndex=Target->Index;A.Link->PrevGroundZ=A.Link->GroundZ;
                A.Link->bRefreshObservation=true;
                A.Region->CurrentRegionId=P.Destination;A.Region->CurrentRegionIndex=Target->RegionRuntimeIndex;
                A.Behavior->Rep.HideTarget=-1;A.Behavior->Rep.bArrived=false;A.Behavior->Decision.bPrepared=false;
                Arrivals.Add(O);
            }
            if(J.Waypoint==Last&&InsideTarget&&FVector::Dist2D(A.Position,Finish)<FMath::Max(220.f,P.CorridorWidth)){
                *A.Travel=FEcoTravelFragment();A.Travel->LastArrivalTime=Now;J.bActive=false;J.Reason=TEXT("Arrived");++P.Arrived;continue;
            }
            const double D=FVector::Dist2D(A.Position,P.Points[J.Waypoint]);
            if(D+30<J.BestDistance){J.BestDistance=D;J.LastProgressTime=Now;}
            const bool Stalled=Now-J.LastProgressTime>FMath::Max(5.f,CVarTimeout.GetValueOnGameThread());P.Failed+=Stalled;
            J.Goal=P.Points[J.Waypoint];
            // Bounded formation offset: no shared single point and no position correction.
            const FVector Direction=(J.Goal-A.Position).GetSafeNormal2D();
            J.Goal+=FVector(-Direction.Y,Direction.X,0)*((int32(A.Id%7)-3)*FMath::Min(70.f,P.CorridorWidth/10));
            const bool LeaderWait=Spread&&FVector::Dist2D(A.Position,P.Points.Last())<FVector::Dist2D(Center,P.Points.Last());
            J.bPause=Rest||(Preparing&&FVector::Dist2D(A.Position,P.Points[0])<350)||(LeaderWait&&FMath::Fmod(Now-P.Started,12.)<5);
            J.Reason=Stalled?TEXT("PathBlocked"):Preparing?TEXT("GatheringForJourney"):Rest?TEXT("Resting"):J.bPause?TEXT("WaitingForHerd"):P.bReturning?TEXT("Returning"):TEXT("FoodShortageJourney");
            J.SpeedScale=Spread?.7f:1.f;
        }
        if(P.Arrived+P.Dead>=P.Members.Num()){
            Change(P,EEcoHerdJourneyState::Settled,TEXT("JourneyComplete"));P.CooldownUntil=Now+FMath::Max(1.f,CVarCooldown.GetValueOnGameThread());
        }else Change(P,Preparing?EEcoHerdJourneyState::Preparing:P.Failed?EEcoHerdJourneyState::Failed:Rest?EEcoHerdJourneyState::Resting:Spread?EEcoHerdJourneyState::Regrouping:EEcoHerdJourneyState::Traveling,
            Preparing?FName(TEXT("GatheringForJourney")):P.Failed?FName(TEXT("PathBlocked")):Rest?FName(TEXT("LowEnergyRest")):Spread?FName(TEXT("HerdSpread")):FName(TEXT("FoodShortage")));
    }
    for(auto It=Plans.CreateIterator();It;++It)if(It.Value().State==EEcoHerdJourneyState::Settled&&Now>It.Value().CooldownUntil
        &&!Groups.Contains(It.Key()))It.RemoveCurrent();
    for(auto It=ShortageSince.CreateIterator();It;++It)if(!Groups.Contains(It.Key()))It.RemoveCurrent();
    for(auto It=NextPlanAttempt.CreateIterator();It;++It)if(!Groups.Contains(It.Key()))It.RemoveCurrent();
    if(!IsEnabled())return true;
    TArray<int64> HerdIds;Groups.GetKeys(HerdIds);HerdIds.Sort();
    for(const int64 Herd:HerdIds){
        const auto& Members=Groups.FindChecked(Herd);if(Members.Num()<2)continue;
        if(const auto* P=Plans.Find(Herd);P&&(P->State!=EEcoHerdJourneyState::Settled||Now<P->CooldownUntil))continue;
        const FName Origin=Agents[Members[0]].Region->CurrentRegionId;auto* Source=Native->FindContext(Origin);if(!Source)continue;
        bool SameRegion=true;int32 Hungry=0;for(const int32 I:Members){SameRegion&=Agents[I].Region->CurrentRegionId==Origin;Hungry+=Agents[I].Body->Body.Energy<.4;}
        const bool Short=Source->FoodFraction()<FMath::Clamp(double(CVarShortage.GetValueOnGameThread()),.01,.95);
        if(!SameRegion||!Short){ShortageSince.Remove(Herd);continue;}
        double& Since=ShortageSince.FindOrAdd(Herd,Now);
        if(Now-Since<FMath::Max(0.f,CVarDwell.GetValueOnGameThread())||(Hungry==0&&Source->FoodFraction()>=.05))continue;
        if(Now<NextPlanAttempt.FindRef(Herd))continue;
        NextPlanAttempt.Add(Herd,Now+3);
        TArray<AEcoHerdMigrationRoute*> Routes;for(TActorIterator<AEcoHerdMigrationRoute> It(GetWorld());It;++It)if(It->bEnabled)Routes.Add(*It);
        Routes.Sort([](const AEcoHerdMigrationRoute& A,const AEcoHerdMigrationRoute& B){return A.GetPathName()<B.GetPathName();});
        TArray<FVector> BestPoints;FName Destination;float Width=600;double BestScore=0;
        for(const auto* Route:Routes){
            const bool Reverse=Route->bBidirectional&&Route->ToRegion==Origin;
            if(Route->FromRegion!=Origin&&!Reverse)continue;
            const FName Dest=Reverse?Route->FromRegion:Route->ToRegion;auto* Target=Native->FindContext(Dest);
            if(!Target||Dest==Origin||Route->Points.Num()<2)continue;
            if(Native->UsesTerrain()){
                const auto* Registry=GetWorld()->GetSubsystem<UEcologyWorldSubsystem>();
                const auto* Region=Registry?Registry->GetRegion(Origin):nullptr;
                if(!Region||!Region->AdjacentRegionIds.Contains(Dest))continue;
            }
            FRegionEcologyState State;if(!Ecology->GetRegionState(Dest,State))continue;
            int32 Incoming=0;for(const auto& E:Plans)if(E.Value.State!=EEcoHerdJourneyState::Settled&&E.Value.Destination==Dest)Incoming+=E.Value.Members.Num()-E.Value.Arrived-E.Value.Dead;
            // Authored adjacent route grants destination knowledge; population forecast includes live incoming plans.
            const double PerHead=State.FoodAmount/FMath::Max(1,State.Population+Incoming+Members.Num());
            FRegionEcologyState Own;if(!Ecology->GetRegionState(Origin,Own))continue;
            if(PerHead<=Own.FoodAmount/FMath::Max(1,Own.Population)*1.2||PerHead<.5)continue;
            auto Points=Route->Points;if(Reverse)Algo::Reverse(Points);
            const auto Start=Source->CmToUnits(Points[0]),End=Target->CmToUnits(Points.Last());
            if(Start.X<0||Start.Y<0||Start.X>Source->Sim.Config.WorldSize||Start.Y>Source->Sim.Config.WorldSize
                ||End.X<0||End.Y<0||End.X>Target->Sim.Config.WorldSize||End.Y>Target->Sim.Config.WorldSize)continue;
            bool Valid=true;double Length=0;
            for(int32 K=1;K<Points.Num();++K){Length+=FVector::Dist2D(Points[K-1],Points[K]);double Z=Points[K-1].Z;
                if(Native->UsesTerrain()&&!Native->TraceMove(Origin,Points[K-1],Points[K],Z,true)){Valid=false;break;}}
            const double Score=PerHead/(1+Length/10000.);if(!Valid||Score<=BestScore)continue;
            BestScore=Score;BestPoints=MoveTemp(Points);Destination=Dest;Width=FMath::Clamp(Route->CorridorWidth,100.f,1500.f);
        }
        if(BestPoints.IsEmpty()){
            for(const int32 I:Members)Agents[I].Journey->Reason=TEXT("NoViableKnownRoute");
            continue;
        }
        FEcoHerdJourney P;P.Id=NextPlan++;P.HerdId=Herd;P.Origin=Origin;P.Destination=Destination;P.Points=MoveTemp(BestPoints);
        P.Started=P.Changed=Now;P.CorridorWidth=Width;P.Reason=TEXT("Preparing");
        for(const int32 I:Members){auto& A=Agents[I];P.Members.Add(A.Id);auto& J=*A.Journey;J={};J.PlanId=P.Id;J.PersistentHerdId=Herd;
            J.bActive=true;J.Goal=P.Points[0];J.LastProgressTime=Now;J.MembershipUntil=GetWorld()->GetTimeSeconds()+10;J.Reason=TEXT("Preparing");
            A.Travel->State=EEcoResidenceState::Traveling;A.Travel->TargetRegionId=Destination;
            A.Travel->TargetRegionIndex=Native->FindContext(Destination)->RegionRuntimeIndex;A.Travel->TargetPosition=P.Points.Last();
            A.Travel->DepartureTime=Now;A.Travel->Reason=EEcoMigrationReason::FoodShortage;
            if(auto* Intent=Manager.GetFragmentDataPtr<FEcoShelterIntentFragment>(A.Entity)){
                if(auto* Shelters=GetWorld()->GetSubsystem<UEcoShelterSubsystem>())Shelters->ReleaseAgentReservations(A.Id);
                *Intent=FEcoShelterIntentFragment();
            }
        }
        Change(P,EEcoHerdJourneyState::Preparing,TEXT("FoodShortage"));Plans.Add(Herd,MoveTemp(P));ShortageSince.Remove(Herd);
    }
    return true;
}

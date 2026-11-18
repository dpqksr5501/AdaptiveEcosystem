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

static TAutoConsoleVariable<int32> CVarRegional(TEXT("eco.HerdMigration.Regional"),0,TEXT("Opt-in regional ordered individual departures; legacy herd mode remains available at 0."));
static TAutoConsoleVariable<float> CVarInterval(TEXT("eco.HerdMigration.DepartureSeconds"),3.f,TEXT("Minimum interval between regional approvals."));
static TAutoConsoleVariable<float> CVarKeep(TEXT("eco.HerdMigration.KeepFraction"),.25f,TEXT("Episode initial population fraction retained, except singleton evacuation."));
static TAutoConsoleVariable<float> CVarRecovery(TEXT("eco.HerdMigration.RecoveryFraction"),.35f,TEXT("Food fraction required to close an episode."));
static TAutoConsoleVariable<float> CVarRecoverySeconds(TEXT("eco.HerdMigration.RecoverySeconds"),15.f,TEXT("Continuous recovery before renewing an episode budget."));
static TAutoConsoleVariable<float> CVarHorizon(TEXT("eco.HerdMigration.FoodHorizonSeconds"),60.f,TEXT("Food demand forecast horizon; current stock only, no speculative regeneration."));
void UEcoHerdMigrationSubsystem::RegisterResident(FName Region,int64 Agent)
{
    check(IsInGameThread());
    if(!Region.IsNone()&&Agent>0){
        for(auto& Entry:RegionalStates)if(Entry.Key!=Region)Entry.Value.Residents.Remove(Agent);
        RegionalStates.FindOrAdd(Region).Residents.AddUnique(Agent);
    }
}

AEcoHerdMigrationRoute::AEcoHerdMigrationRoute(){PrimaryActorTick.bCanEverTick=false;SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("RouteRoot")));}
bool AEcoHerdMigrationRoute::IsValidRoute() const
{
    if(FromRegion.IsNone()||ToRegion.IsNone()||FromRegion==ToRegion||Points.Num()<2||Points.Num()>256
        ||!FMath::IsFinite(CorridorWidth)||CorridorWidth<=0)return false;
    double Length=0;
    for(int32 I=0;I<Points.Num();++I){
        if(Points[I].ContainsNaN())return false;
        if(I){const double Segment=FVector::Dist2D(Points[I-1],Points[I]);
            if(!FMath::IsFinite(Segment)||Segment>20000)return false;
            Length+=Segment;
        }
    }
    return Length>=1&&Length<=100000;
}
bool UEcoHerdMigrationSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{ const auto* W=Cast<UWorld>(Outer);return W&&W->IsGameWorld()&&W->GetNetMode()!=NM_Client; }
bool UEcoHerdMigrationSubsystem::IsEnabled() const {
    const int32 Mode=CVarHerdMigration.GetValueOnGameThread();if(Mode>=0)return Mode!=0;
    for(TActorIterator<AEcoCreatureIntegrationSpawner> It(GetWorld());It;++It)if(It->bEnableHerdJourneys)return true;
    return false;
}
bool UEcoHerdMigrationSubsystem::ApplyFoodFractionForAudit(FName Region,float Fraction,bool bSuspendRegeneration){
#if !UE_BUILD_SHIPPING
    const FString Map=GetWorld()->GetOutermost()->GetName();
    const bool bAuditMap=Map.StartsWith(TEXT("/Game/JYU/Maps/"))||Map==TEXT("/Game/JWJ/1102_Integration_JWJ");
    if(GetWorld()->GetNetMode()==NM_Client||!bAuditMap
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
    TEXT("JYU audit maps or JWJ 1102 integration only: drought <RegionId> removes native food with a ledger receipt and suspends regeneration. Restart Play to reset."),
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
    case EEcoHerdJourneyState::Settled:return TEXT("Settled");case EEcoHerdJourneyState::Abandoned:return TEXT("Abandoned");default:return TEXT("Blocked");}
}

bool UEcoHerdMigrationSubsystem::Reconcile(FMassEntityManager& Manager,const FEcoServerTimeSnapshot& Time,int64 Step,
    TArray<FEcoMigrationOutcome>& Arrivals,TConstArrayView<FEcoRegionSpatialSnapshot> Spaces)
{
    if(!IsInGameThread()||Manager.IsProcessing()||GetWorld()->GetNetMode()==NM_Client)return false;
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ecology=GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    auto* Herds=GetWorld()->GetSubsystem<UEcoHerdSubsystem>();
    if(!Native||!Native->IsActive()||!Ecology||!Herds)return true;
    // Existing journeys finish even if new departures are disabled at runtime.
    if(!IsEnabled()&&Plans.IsEmpty())return true;
    const double Now=Time.ServerTimeSeconds;
    auto RegionAvailable = [&](FName Region) {
        // The context-only automation harness has no streamed geometry.
        if (Spaces.IsEmpty()) return true;
        const int32 Index = Ecology->GetRegionRuntimeIndex(Region);
        return Spaces.IsValidIndex(Index) && Spaces[Index].RegionId == Region && Spaces[Index].bAvailable;
    };
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
            const bool bJourneyMember = Js[I].bActive || Js[I].bStranded;
            if(!Links[I].bAdopted||Links[I].bDead||Bodies[I].Body.DeathCause!=EcoWorldV3::kDeathNone||!R
                ||(CVarRegional.GetValueOnGameThread()==0&&!HasHerd&&!bJourneyMember))continue;
            FMember A;A.Id=Ids[I].StableAgentId;A.Herd=bJourneyMember?Js[I].PersistentHerdId:H.PersistentHerdId;A.Region=&Regions[I];A.Travel=&Travels[I];
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
        auto& P=Entry.Value;
        if (P.State == EEcoHerdJourneyState::Settled) continue;
        if (P.State == EEcoHerdJourneyState::Abandoned)
        {
            if (!P.bReturning || Now < P.CooldownUntil || !RegionAvailable(P.Origin)) continue;
            const auto* Home = Native->FindContext(P.Origin);
            if (!Home) continue;
            bool bResumed = false, bHasStrandedMember = false;
            for (const int64 Id : P.Members)
            {
                const int32* Index = ById.Find(Id);
                if (!Index) continue;
                auto& A = Agents[*Index];
                auto& J = *A.Journey;
                if (!J.bStranded || J.PlanId != P.Id) continue;
                bHasStrandedMember = true;
                if (!RegionAvailable(A.Region->CurrentRegionId)) continue;
                const double MaxDistance = FMath::Max(500., double(P.CorridorWidth) * 2.);
                double Best = FMath::Square(MaxDistance);
                int32 Waypoint = INDEX_NONE;
                for (int32 I = 0; I < P.Points.Num(); ++I)
                {
                    const double Distance = FVector::DistSquared2D(A.Position, P.Points[I]);
                    if (Distance >= Best) continue;
                    double GroundZ = A.Position.Z;
                    if (Native->UsesTerrain() && !Native->TraceMove(A.Region->CurrentRegionId, A.Position, P.Points[I], GroundZ, true)) continue;
                    Waypoint = I;
                    Best = Distance;
                }
                if (Waypoint == INDEX_NONE) continue;
                J.bStranded = false;
                J.bActive = true;
                J.bPause = false;
                J.Waypoint = Waypoint;
                J.Goal = P.Points[Waypoint];
                J.LastProgressTime = Now;
                J.BestDistance = MAX_dbl;
                A.Travel->State = EEcoResidenceState::Traveling;
                A.Travel->TargetRegionId = P.Origin;
                A.Travel->TargetRegionIndex = Home->RegionRuntimeIndex;
                A.Travel->TargetPosition = P.Points.Last();
                A.Travel->DepartureTime = Now;
                A.Travel->Reason = EEcoMigrationReason::ReturnHome;
                bResumed = true;
            }
            if (bHasStrandedMember) P.CooldownUntil = Now + 5.;
            if (!bResumed) continue;
            Change(P, EEcoHerdJourneyState::Regrouping, TEXT("ReturnRouteReopened"));
        }
        auto* Target=Native->FindContext(P.Destination);if(!Target)return false;
        const FName WaitReason = FEcoHerdTravelFragment::UnavailableRegionReason();
        const bool bReady = RegionAvailable(P.Origin) && RegionAvailable(P.Destination)
            && !P.Members.ContainsByPredicate([&](int64 Id) {
                const int32* K = ById.Find(Id);
                if (!K) return false;
                const auto& A = Agents[*K];
                return A.Journey->bActive && A.Journey->PlanId == P.Id && !RegionAvailable(A.Region->CurrentRegionId);
            });
        if (!bReady)
        {
            bool bWaiting = false;
            for (const int64 Id : P.Members)
            {
                const int32* K = ById.Find(Id);
                if (!K) continue;
                auto& J = *Agents[*K].Journey;
                if (!J.bActive || J.PlanId != P.Id) continue;
                J.bPause = true;
                J.Reason = WaitReason;
                J.MembershipUntil = GetWorld()->GetTimeSeconds() + 10;
                bWaiting = true;
            }
            if (bWaiting)
            {
                Change(P, P.State, WaitReason);
                continue;
            }
        }
        if (P.Reason == WaitReason)
        {
            const double PausedFor = FMath::Max(0., Now - P.Changed);
            P.Started += PausedFor;
            for (const int64 Id : P.Members)
            {
                const int32* K = ById.Find(Id);
                if (!K) continue;
                auto& J = *Agents[*K].Journey;
                if (J.PlanId == P.Id && J.IsWaitingForRegion()) J.LastProgressTime += PausedFor;
            }
        }
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
                A.Travel->Reason=EEcoMigrationReason::ReturnHome;
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
            // A second stalled leg is terminal. Clearing the stage guard outside
            // the current context would clamp/teleport the body on the next Step.
            if(P.bReturning&&Now-J.LastProgressTime>2*FMath::Max(5.f,CVarTimeout.GetValueOnGameThread())){
                const auto* Current=Native->GetContext(A.Link->ContextIndex);
                const auto Q=Current->CmToUnits(A.Position);
                J.bStranded=Q.X<0||Q.Y<0||Q.X>Current->Sim.Config.WorldSize||Q.Y>Current->Sim.Config.WorldSize;
                J.bActive=false;J.bPause=true;J.MembershipUntil=0;
                J.Reason=J.bStranded?TEXT("StrandedAfterReturnFailure"):TEXT("ReturnFailedResident");
                *A.Travel=FEcoTravelFragment();A.Travel->LastArrivalTime=Now;
                ++P.Failed;continue;
            }
            const int32 Last=P.Points.Num()-1;
            if(!Preparing&&J.Waypoint<Last&&FVector::Dist2D(A.Position,P.Points[J.Waypoint])<FMath::Max(250.f,P.CorridorWidth*.7f)){
                ++J.Waypoint;J.BestDistance=MAX_dbl;J.LastProgressTime=Now;
            }
            const FVector Finish=P.Points.Last();const auto Local=Target->CmToUnits(A.Position);
            const bool InsideTarget=Local.X>=0&&Local.Y>=0&&Local.X<=Target->Sim.Config.WorldSize&&Local.Y<=Target->Sim.Config.WorldSize;
            if(InsideTarget&&A.Region->CurrentRegionId!=P.Destination){
                FEcoMigrationOutcome O;O.WorldEpoch=Time.WorldEpoch;O.StepId=Step;O.StableAgentId=A.Id;
                O.OriginRegionId=A.Region->CurrentRegionId;O.DestinationRegionId=P.Destination;
                O.Reason=P.bReturning?EEcoMigrationReason::ReturnHome:EEcoMigrationReason::FoodShortage;
                O.DepartureTime=A.Travel->DepartureTime;O.ArrivalTime=Now;
                // Context rebase preserves actual world position, identity, energy, reserve and herd.
                A.Body->Body.Pos=A.Body->Body.PrevPos=Local;A.Body->Body.Detour={};
                A.Link->ContextIndex=Target->Index;A.Link->PrevGroundZ=A.Link->GroundZ;
                A.Link->bRefreshObservation=true;
                A.Region->CurrentRegionId=P.Destination;A.Region->CurrentRegionIndex=Target->RegionRuntimeIndex;
                RegisterResident(P.Destination,A.Id);
                A.Behavior->Rep.HideTarget=-1;A.Behavior->Rep.bArrived=false;A.Behavior->Decision.bPrepared=false;
                Arrivals.Add(O);
            }
            if(J.Waypoint==Last&&InsideTarget&&FVector::Dist2D(A.Position,Finish)<FMath::Max(220.f,P.CorridorWidth)){
                if(Target->Sim.Config.bNaturalHabitats){
                    A.Link->Individual.SettlementUntil=Now+45;A.Link->Individual.SettlementX=A.Body->Body.Pos.X;A.Link->Individual.SettlementY=A.Body->Body.Pos.Y;
                    A.Link->Individual.ForageCell=-1;A.Link->Individual.NextForageScan=0;
                }
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
        bool AnyActive=false,AnyAbandoned=false;
        for(const int64 Id:P.Members)if(const auto* K=ById.Find(Id)){
            const auto& J=*Agents[*K].Journey;AnyActive|=J.bActive;
            AnyAbandoned|=J.bStranded||J.Reason==TEXT("ReturnFailedResident");
        }
        if(!AnyActive){
            Change(P,AnyAbandoned?EEcoHerdJourneyState::Abandoned:EEcoHerdJourneyState::Settled,
                AnyAbandoned?TEXT("ReturnFailedNoTeleport"):TEXT("JourneyComplete"));
            P.CooldownUntil=Now+FMath::Max(1.f,CVarCooldown.GetValueOnGameThread());
        }else Change(P,Preparing?EEcoHerdJourneyState::Preparing:P.Failed?EEcoHerdJourneyState::Failed:Rest?EEcoHerdJourneyState::Resting:Spread?EEcoHerdJourneyState::Regrouping:EEcoHerdJourneyState::Traveling,
            Preparing?FName(TEXT("GatheringForJourney")):P.Failed?FName(TEXT("PathBlocked")):Rest?FName(TEXT("LowEnergyRest")):Spread?FName(TEXT("HerdSpread")):
            P.bReturning?FName(TEXT("Returning")):FName(TEXT("FoodShortage")));
    }
    for(auto It=Plans.CreateIterator();It;++It)if(IsTerminal(It.Value().State)&&Now>It.Value().CooldownUntil
         )It.RemoveCurrent();
    for(auto It=ShortageSince.CreateIterator();It;++It)if(!Groups.Contains(It.Key()))It.RemoveCurrent();
    for(auto It=NextPlanAttempt.CreateIterator();It;++It)if(!Groups.Contains(It.Key()))It.RemoveCurrent();
    if(!IsEnabled())return true;
    // Population is reconciled by the coordinator after this function. Include
    // this boundary's receipts without reserving those same bodies a second time.
    auto CurrentPopulation=[&](FName Region,int32 Committed){
        int32 Delta=0;for(const auto& A:Arrivals){Delta+=(A.DestinationRegionId==Region);Delta-=(A.OriginRegionId==Region);}
        return FMath::Max(0,Committed+Delta);
    };
    const bool Regional=CVarRegional.GetValueOnGameThread()!=0;
    struct FCandidate { int64 Herd; TArray<int32> Members; };
    TArray<FCandidate> Candidates;
    if(Regional){
        // Adoption records real registration order. Fallback covers worlds restored before adoption hooks.
        for(const auto& A:Agents)RegisterResident(A.Region->CurrentRegionId,A.Id);
        TArray<FName> Regions;RegionalStates.GetKeys(Regions);
        Regions.Sort([](FName A,FName B){return A.LexicalLess(B);});
        for(const FName Region:Regions){
            auto& R=RegionalStates.FindChecked(Region);
            R.Residents.RemoveAll([&](int64 Id){const auto* I=ById.Find(Id);return !I||Agents[*I].Region->CurrentRegionId!=Region;});
            auto* Source=Native->FindContext(Region);if(!Source||!RegionAvailable(Region))continue;
            int32 Outgoing=0;
            for(const int64 Id:R.Residents){const auto& A=Agents[ById.FindChecked(Id)];Outgoing+=A.Journey->bActive&&A.Travel->TargetRegionId!=Region;}
            R.Projected=FMath::Max(0,R.Residents.Num()-Outgoing);
            // EnergyDrain is per decision step; FoodEnergyPerUnit converts food to energy.
            // Use maximum configured gait demand as a conservative movement allowance, never actual intake (zero under starvation).
            const auto& RC=Source->Sim.RepCfg;
            const double Need=FMath::Max3(RC.GaitDrain[0],RC.GaitDrain[1],RC.GaitDrain[2])*RC.EnergyDrain/RC.FoodEnergyPerUnit*FMath::Max(1.f,CVarHorizon.GetValueOnGameThread())/EcoRepertoireV3::kStepSeconds;
            R.Supported=Need>0&&FMath::IsFinite(Need)?FMath::FloorToInt(FMath::Min(1000000.,Source->Sim.Food.Total()/Need)):0;
            const bool Short=Source->FoodFraction()<CVarShortage.GetValueOnGameThread();
            if(!R.bEpisode){
                if(!Short){R.ShortageSince=-1;R.Reason=TEXT("RegionSustainable");continue;}
                if(R.ShortageSince<0)R.ShortageSince=Now;
                if(Now-R.ShortageSince<FMath::Max(0.f,CVarDwell.GetValueOnGameThread())){R.Reason=TEXT("ShortageDwell");continue;}
                R.bEpisode=true;R.Initial=R.Residents.Num();R.KeepFloor=R.Initial<=1?0:FMath::CeilToInt(R.Initial*FMath::Clamp(CVarKeep.GetValueOnGameThread(),0.f,1.f));
                R.Approved.Reset();for(const int64 Id:R.Residents)if(Agents[ById.FindChecked(Id)].Journey->bActive)R.Approved.Add(Id);
            }
            if(Source->FoodFraction()>=CVarRecovery.GetValueOnGameThread()&&R.Projected<=R.Supported){
                if(R.RecoverySince<0)R.RecoverySince=Now;
                if(Now-R.RecoverySince>=FMath::Max(0.f,CVarRecoverySeconds.GetValueOnGameThread())){
                    R.bEpisode=false;R.ShortageSince=-1;R.RecoverySince=-1;R.Reason=TEXT("Recovered");continue;
                }
            }else R.RecoverySince=-1;
            if(R.Projected<=R.Supported){R.Reason=TEXT("RegionSustainable");continue;}
            if(R.Projected<=R.KeepFloor){R.Reason=TEXT("RetentionFloor");continue;}
            if(Now<R.NextDeparture){R.Reason=TEXT("DepartureInterval");continue;}
            R.Reason=TEXT("NoEligibleCandidate");
            for(const int64 Id:R.Residents){
                const int32 I=ById.FindChecked(Id);const auto& A=Agents[I];
                if(A.Journey->bActive||A.Journey->bStranded)continue;
                bool Cooling=false;for(const auto& P:Plans)if(P.Value.Members.Contains(Id))Cooling|=!IsTerminal(P.Value.State)||Now<P.Value.CooldownUntil;
                if(Cooling)continue;
                if(!R.Approved.Contains(Id)&&R.Approved.Num()>=R.Initial-R.KeepFloor){R.Reason=TEXT("EpisodeBudgetReached");continue;}
                Candidates.Add({A.Herd,{I}});
            }
        }
    }else{
        TArray<int64> HerdIds;Groups.GetKeys(HerdIds);HerdIds.Sort();
        for(const int64 Herd:HerdIds){
            auto Members=Groups.FindChecked(Herd).FilterByPredicate([&](int32 I){return !Agents[I].Journey->bStranded;});
            if(!Members.IsEmpty())Candidates.Add({Herd,MoveTemp(Members)});
        }
    }
    for(const auto& Candidate:Candidates){
        const int64 Herd=Candidate.Herd;const auto& Members=Candidate.Members;
        if(Members.IsEmpty())continue;
        const FName Origin=Agents[Members[0]].Region->CurrentRegionId;auto* Source=Native->FindContext(Origin);
        if(!Source||!RegionAvailable(Origin)){if(!Regional)ShortageSince.Remove(Herd);continue;}
        auto& RegionalState=RegionalStates.FindOrAdd(Origin);
        if(Regional){if(Now<RegionalState.NextDeparture)continue;}
        else{
            bool Busy=false;for(const auto& P:Plans)if(P.Value.HerdId==Herd)Busy|=!IsTerminal(P.Value.State)||Now<P.Value.CooldownUntil;
            if(Busy)continue;
        // A persistent herd may have one survivor. Life worlds use the same
        // journey/receipts for that individual; never invent a replacement herd.
        if(Members.Num()<2&&!Source->Sim.Config.bEcosystemLife)continue;
        bool SameRegion=true;int32 Hungry=0;for(const int32 I:Members){SameRegion&=Agents[I].Region->CurrentRegionId==Origin;Hungry+=Agents[I].Body->Body.Energy<.4;}
        const double Fraction=Source->FoodFraction();
        // Long physical journeys must not wait until weak bodies exhaust their
        // reserve. Only life worlds admit this early, majority-hungry shortage;
        // destination knowledge/value and the sustained dwell still apply.
        const bool ForecastShortage=Source->Sim.Config.bEcosystemLife&&Fraction<.5&&Hungry*2>=Members.Num();
        const bool Short=Fraction<FMath::Clamp(double(CVarShortage.GetValueOnGameThread()),.01,.95)||ForecastShortage;
        if(!SameRegion||!Short){ShortageSince.Remove(Herd);continue;}
        double& Since=ShortageSince.FindOrAdd(Herd,Now);
        if(Now-Since<FMath::Max(0.f,CVarDwell.GetValueOnGameThread())||(Hungry==0&&Source->FoodFraction()>=.05)){
            if(Source->Sim.Config.bEcosystemLife)for(const int32 I:Members)Agents[I].Journey->Reason=TEXT("AwaitingSustainedShortage");
            continue;
        }
            if(Now<NextPlanAttempt.FindRef(Herd))continue;
            NextPlanAttempt.Add(Herd,Now+3);
        }
        TArray<AEcoHerdMigrationRoute*> Routes;
        for (TActorIterator<AEcoHerdMigrationRoute> It(GetWorld()); It; ++It)
            if (It->bEnabled && !It->bRuleFaunaWaterPassage && It->IsValidRoute()) Routes.Add(*It);
        Routes.Sort([](const AEcoHerdMigrationRoute& A,const AEcoHerdMigrationRoute& B){return A.GetPathName()<B.GetPathName();});
        TArray<FVector> BestPoints;FName Destination;float Width=600;double BestScore=0;bool BudgetRejected=false;
        for(const auto* Route:Routes){
            const bool Reverse=Route->bBidirectional&&Route->ToRegion==Origin;
            if(Route->FromRegion!=Origin&&!Reverse)continue;
            const FName Dest=Reverse?Route->FromRegion:Route->ToRegion;auto* Target=Native->FindContext(Dest);
            if(!Target||Dest==Origin||!RegionAvailable(Dest)||Route->Points.Num()<2)continue;
            if(Native->UsesTerrain()){
                const auto* Registry=GetWorld()->GetSubsystem<UEcologyWorldSubsystem>();
                const auto* Region=Registry?Registry->GetRegion(Origin):nullptr;
                if(!Region||!Region->AdjacentRegionIds.Contains(Dest))continue;
            }
            FRegionEcologyState State;if(!Ecology->GetRegionState(Dest,State))continue;
            const FEcoKnownHabitat* Report=nullptr;
            if(Source->Sim.Config.bEcosystemLife){
                if(Route->bSharesHabitatReports){
                    auto* Existing=KnownHabitats.Find(Dest);
                    if(!Existing||Now-Existing->Observed>=30){
                        // Authored regional reports are delayed, quantized snapshots,
                        // not the target's exact live truth at every agent decision.
                        FEcoKnownHabitat K;K.Observed=Now;K.Food=FMath::FloorToDouble(State.FoodAmount/5)*5;
                        K.Population=FMath::DivideAndRoundUp(State.Population,4)*4;K.Risk=FMath::RoundToDouble(State.PredationHistory*4)/4;
                        K.Risk=FMath::Max(K.Risk,FMath::RoundToDouble(Target->KnownHumanDanger.At(Now)*4)/4);
                        const auto& F=Target->Sim.Food;double Water=0;
                        for(size_t I=0;I<F.Food.size();++I){
                            if(F.Vegetation.bEnabled){
                                auto Cell=F.VegetationCells[I];const auto O=EcoVegetationV3::Advance(F.Vegetation,F.VegetationWeather,F.Habitats[I],Cell,F.Food[I],F.Cap[I],F.Regen[I],EcoRepertoireV3::kStepSeconds);
                                K.Recovery+=O.Growth;Water+=F.Habitats[I].WaterSupply;
                            }else K.Recovery+=F.Regen[I]*(F.Cap[I]-F.Food[I]);
                        }
                        K.Recovery=FMath::FloorToDouble(K.Recovery/EcoRepertoireV3::kStepSeconds*30/5)*5;
                        K.Water=F.Food.empty()?0:Water/F.Food.size();
                        for(const auto& C:Target->Sim.Config.Covers)K.Shelter+=C.Radius>0?UE_PI*C.Radius*C.Radius:0;
                        K.Shelter=FMath::Clamp(K.Shelter/FMath::Square(Target->Sim.Config.WorldSize),0.,1.);
                        KnownHabitats.Add(Dest,K);
                    }
                }
                Report=KnownHabitats.Find(Dest);
                if(!Report||Now<Report->Observed||Now-Report->Observed>90)continue;
            }
            int32 Incoming=0;
            for(const auto& E:Plans)if(!IsTerminal(E.Value.State)&&E.Value.Destination==Dest)
                for(const int64 Id:E.Value.Members)if(const auto* K=ById.Find(Id)){
                    const auto& A=Agents[*K];
                    Incoming+=A.Journey->bActive&&A.Journey->PlanId==E.Value.Id&&A.Region->CurrentRegionId!=Dest;
                }
            // Authored adjacent route grants destination knowledge; population forecast includes live incoming plans.
            const double ExpectedFood=Report?Report->Food+Report->Recovery*.25:State.FoodAmount;
            const int32 CommittedPopulation=CurrentPopulation(Dest,State.Population);
            int32 ExpectedPopulation=Report?FMath::Max(Report->Population,Target->Sim.Config.bNaturalHabitats?CommittedPopulation:0):CommittedPopulation;
            if(Regional){
                ExpectedPopulation=0;for(const auto& A:Agents)ExpectedPopulation+=A.Region->CurrentRegionId==Dest;
                const auto& RC=Target->Sim.RepCfg;
                const double Need=FMath::Max3(RC.GaitDrain[0],RC.GaitDrain[1],RC.GaitDrain[2])*RC.EnergyDrain/RC.FoodEnergyPerUnit*FMath::Max(1.f,CVarHorizon.GetValueOnGameThread())/EcoRepertoireV3::kStepSeconds;
                if(!FMath::IsFinite(Need)||Need<=0||ExpectedFood<(ExpectedPopulation+Incoming+1)*Need){RegionalState.Reason=TEXT("DestinationCapacity");continue;}
            }
            double PerHead=ExpectedFood/FMath::Max(1,ExpectedPopulation+Incoming+Members.Num());
            FRegionEcologyState Own;if(!Ecology->GetRegionState(Origin,Own))continue;
            if(PerHead<=Own.FoodAmount/FMath::Max(1,CurrentPopulation(Origin,Own.Population))*1.2||PerHead<.5)continue;
            if(Report&&Target->Sim.Config.bNaturalHabitats){
                const auto& Rates=Target->Sim.RepCfg;
                const double FoodRate=Rates.EnergyDrain*FMath::Max(.85,Rates.GaitDrain[EcoRepertoireV3::kGaitStop])/Rates.FoodEnergyPerUnit/EcoRepertoireV3::kStepSeconds;
                const auto Budget=EcoNaturalHabitat::SettlementBudget(Report->Food,Report->Recovery,Report->Population,CommittedPopulation,
                    Incoming,Members.Num(),FoodRate,FMath::Clamp(double(CVarCooldown.GetValueOnGameThread()),60.,300.));
                if(!Budget.bAdmissible){BudgetRejected=true;continue;}PerHead=Budget.FoodPerHead;
            }
            auto Points=Route->Points;if(Reverse)Algo::Reverse(Points);
            const auto Start=Source->CmToUnits(Points[0]),End=Target->CmToUnits(Points.Last());
            if(Start.X<0||Start.Y<0||Start.X>Source->Sim.Config.WorldSize||Start.Y>Source->Sim.Config.WorldSize
                ||End.X<0||End.Y<0||End.X>Target->Sim.Config.WorldSize||End.Y>Target->Sim.Config.WorldSize)continue;
            bool Valid=true;double Length=0;
            for(int32 K=1;K<Points.Num();++K){Length+=Target->Sim.Config.bNaturalHabitats?FVector::Dist(Points[K-1],Points[K]):FVector::Dist2D(Points[K-1],Points[K]);double Z=Points[K-1].Z;
                if(Native->UsesTerrain()&&!Native->TraceMove(Origin,Points[K-1],Points[K],Z,true)){Valid=false;break;}}
            const double Confidence=Report?FMath::Clamp(1-(Now-Report->Observed)/180.,.5,1.):1.;
            const double Suitability=Report?(1-.5*Report->Risk)*(1+.1*Report->Water+.1*Report->Shelter)*Confidence:1.;
            const double Score=PerHead*Suitability/(1+Length/10000.);if(!Valid||Score<=BestScore)continue;
            BestScore=Score;BestPoints=MoveTemp(Points);Destination=Dest;Width=FMath::Clamp(Route->CorridorWidth,100.f,1500.f);
        }
        if(BestPoints.IsEmpty()){
            for(const int32 I:Members)Agents[I].Journey->Reason=BudgetRejected?TEXT("DestinationFoodBudgetInsufficient"):TEXT("NoViableKnownRoute");
            if(Regional)RegionalState.Reason=BudgetRejected?TEXT("DestinationFoodBudgetInsufficient"):TEXT("NoViableKnownRoute");
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
        Change(P,EEcoHerdJourneyState::Preparing,TEXT("FoodShortage"));const int64 Key=P.Id;Plans.Add(Key,MoveTemp(P));
        if(Regional){RegionalState.Approved.AddUnique(Agents[Members[0]].Id);RegionalState.NextDeparture=Now+FMath::Max(.01f,CVarInterval.GetValueOnGameThread());--RegionalState.Projected;RegionalState.Reason=TEXT("Approved");}
        else ShortageSince.Remove(Herd);
    }
    if(Regional)for(const auto& Entry:RegionalStates){const auto& R=Entry.Value;
        if(R.bEpisode&&FMath::Fmod(Now,3.)<.51)
            UE_LOG(LogEcoHerdMigration,Log,TEXT("[RegionalMigration] Region=%s Live=%d Projected=%d Supported=%d Keep=%d Approved=%d/%d Reason=%s"),*Entry.Key.ToString(),R.Residents.Num(),R.Projected,R.Supported,R.KeepFloor,R.Approved.Num(),R.Initial-R.KeepFloor,*R.Reason.ToString());
    }
    return true;
}

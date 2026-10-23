#include "Creature/Debug/EcoHerdMigrationDebug.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassEntitySubsystem.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/HUD.h"
#include "GameFramework/PlayerController.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

static TAutoConsoleVariable<int32> CVarMigrationDebug(TEXT("eco.HerdMigration.Debug"),-1,
    TEXT("-1: authored journey worlds, 0: hidden, 1: map/route/selected herd, 2: all active member goals. M toggles; [ ] cycle plans."));
int32 EcoHerdMigrationDebug::Mode(UWorld& W)
{
    if(W.GetNetMode()==NM_Client)return 0;
    const int32 Value=CVarMigrationDebug.GetValueOnGameThread();if(Value>=0)return FMath::Clamp(Value,0,2);
    const auto* M=W.GetSubsystem<UEcoHerdMigrationSubsystem>();return M&&(M->IsEnabled()||!M->GetPlans().IsEmpty())?1:0;
}
void EcoHerdMigrationDebug::Toggle(UWorld& W){IConsoleManager::Get().FindConsoleVariable(TEXT("eco.HerdMigration.Debug"))->Set(Mode(W)?0:1,ECVF_SetByConsole);}
bool EcoHerdMigrationDebug::Capture(UWorld& W,FEcoHerdMigrationDebugSnapshot& Out)
{
    Out={};
    if(!IsInGameThread()||W.GetNetMode()==NM_Client)return false;
    const auto* N=W.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const auto* M=W.GetSubsystem<UEcoHerdMigrationSubsystem>();
    auto* Mass=W.GetSubsystem<UMassEntitySubsystem>();
    if(!N||!N->IsActive()||!M||!Mass)return false;
    auto& EM=Mass->GetMutableEntityManager();if(EM.IsProcessing())return false;
    Out.WorldSeconds=W.GetTimeSeconds();TSet<FName> Connected;
    for(TActorIterator<AEcoHerdMigrationRoute> It(&W);It;++It)if(It->bEnabled&&It->IsValidRoute()){
        Out.Routes.Add({It->FromRegion,It->ToRegion,It->Points});Connected.Add(It->FromRegion);Connected.Add(It->ToRegion);
    }
    Out.Routes.Sort([](const auto& A,const auto& B){return A.From==B.From?A.To.LexicalLess(B.To):A.From.LexicalLess(B.From);});
    const auto* Ecology=W.GetSubsystem<UEcologySimulationSubsystem>();
    for(int32 I=0;I<N->NumContexts();++I)if(const auto* C=N->GetContext(I);C&&Connected.Contains(C->RegionId)){
        FRegionEcologyState State;FEcoMigrationDebugRegion R;R.Id=C->RegionId;R.Minimum=C->OriginCm;
        R.Maximum=C->UnitsToCm(C->Sim.Config.WorldSize,C->Sim.Config.WorldSize,C->OriginCm.Z);R.FoodFraction=C->FoodFraction();
        if(Ecology&&Ecology->GetRegionState(R.Id,State))R.Population=State.Population;
        Out.Regions.Add(R);
    }
    Out.Regions.Sort([](const auto& A,const auto& B){return A.Id.LexicalLess(B.Id);});
    for(const auto& Entry:M->GetPlans()){
        const auto& P=Entry.Value;FEcoMigrationDebugPlan D;D.Id=P.Id;D.Herd=P.HerdId;D.Origin=P.Origin;D.Destination=P.Destination;
        D.Reason=P.Reason;D.State=P.State;D.Members=P.Members.Num();D.Arrived=P.Arrived;D.Dead=P.Dead;D.Blocked=P.Failed;
        D.bReturning=P.bReturning;D.Points=P.Points;Out.Plans.Add(MoveTemp(D));
    }
    Out.Plans.Sort([](const auto& A,const auto& B){return A.Id<B.Id;});
    FMassEntityQuery Q(EM.AsShared());
    Q.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Q.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
    Q.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadOnly);
    Q.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadOnly);
    Q.AddRequirement<FEcoHerdTravelFragment>(EMassFragmentAccess::ReadOnly);
    Q.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
    Q.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
    auto Exec=EM.CreateExecutionContext(0);
    Q.ForEachEntityChunk(Exec,[&](FMassExecutionContext& C){
        const auto Id=C.GetFragmentView<FEcoIdentityFragment>();const auto Region=C.GetFragmentView<FEcoRegionFragment>();
        const auto Link=C.GetFragmentView<FEcoIntegratedV3Fragment>();const auto Body=C.GetFragmentView<FEcoHerbivoreBodyV3Fragment>();
        const auto Journey=C.GetFragmentView<FEcoHerdTravelFragment>();
        for(int32 I=0;I<C.GetNumEntities();++I){
            const auto* Stage=N->GetContext(Link[I].ContextIndex);
            if(!Stage||!Link[I].bAdopted||Link[I].bDead||Body[I].Body.DeathCause!=EcoWorldV3::kDeathNone)continue;
            const FVector P=Stage->UnitsToCm(Body[I].Body.Pos.X,Body[I].Body.Pos.Y,Link[I].GroundZ);
            if(P.ContainsNaN())continue;
            const auto& J=Journey[I];Out.Members.Add({Id[I].StableAgentId,J.PlanId,Region[I].CurrentRegionId,J.Reason,P,J.Goal,J.bActive,J.Waypoint});
        }
    });
    Out.Members.Sort([](const auto& A,const auto& B){return A.Agent<B.Agent;});return true;
}
bool EcoHerdMigrationDebug::ToJson(const FEcoHerdMigrationDebugSnapshot& S,FString& Out)
{
    auto Root=MakeShared<FJsonObject>();Root->SetNumberField(TEXT("schema"),1);Root->SetNumberField(TEXT("world_seconds"),S.WorldSeconds);
    auto Vector=[](const FVector& P){TArray<TSharedPtr<FJsonValue>> V;for(double N:{P.X,P.Y,P.Z})V.Add(MakeShared<FJsonValueNumber>(N));return V;};
    TArray<TSharedPtr<FJsonValue>> Regions,Plans,Members;
    for(const auto& R:S.Regions){auto J=MakeShared<FJsonObject>();J->SetStringField(TEXT("region"),R.Id.ToString());
        J->SetNumberField(TEXT("food_fraction"),R.FoodFraction);J->SetNumberField(TEXT("population"),R.Population);
        J->SetArrayField(TEXT("minimum"),Vector(R.Minimum));J->SetArrayField(TEXT("maximum"),Vector(R.Maximum));Regions.Add(MakeShared<FJsonValueObject>(J));}
    for(const auto& P:S.Plans){auto J=MakeShared<FJsonObject>();J->SetNumberField(TEXT("plan"),double(P.Id));J->SetNumberField(TEXT("herd"),double(P.Herd));
        J->SetStringField(TEXT("origin"),P.Origin.ToString());J->SetStringField(TEXT("destination"),P.Destination.ToString());
        J->SetStringField(TEXT("state"),UEcoHerdMigrationSubsystem::StateName(P.State));J->SetStringField(TEXT("reason"),P.Reason.ToString());
        J->SetNumberField(TEXT("members"),P.Members);J->SetNumberField(TEXT("arrived"),P.Arrived);J->SetNumberField(TEXT("dead"),P.Dead);
        J->SetBoolField(TEXT("returning"),P.bReturning);TArray<TSharedPtr<FJsonValue>> Points;
        for(const auto& Point:P.Points)Points.Add(MakeShared<FJsonValueArray>(Vector(Point)));J->SetArrayField(TEXT("points"),Points);Plans.Add(MakeShared<FJsonValueObject>(J));}
    for(const auto& M:S.Members){auto J=MakeShared<FJsonObject>();J->SetStringField(TEXT("agent"),LexToString(M.Agent));
        J->SetNumberField(TEXT("plan"),double(M.Plan));J->SetStringField(TEXT("region"),M.Region.ToString());J->SetStringField(TEXT("reason"),M.Reason.ToString());
        J->SetBoolField(TEXT("active"),M.bActive);J->SetNumberField(TEXT("waypoint"),M.Waypoint);
        J->SetArrayField(TEXT("position"),Vector(M.Position));J->SetArrayField(TEXT("goal"),Vector(M.Goal));Members.Add(MakeShared<FJsonValueObject>(J));}
    Root->SetArrayField(TEXT("regions"),Regions);Root->SetArrayField(TEXT("plans"),Plans);Root->SetArrayField(TEXT("members"),Members);
    Root->SetNumberField(TEXT("known_routes"),S.Routes.Num());
    return FJsonSerializer::Serialize(Root,TJsonWriterFactory<TCHAR,TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out));
}
namespace
{
FLinearColor StateColor(EEcoHerdJourneyState S){
    switch(S){case EEcoHerdJourneyState::Settled:return FLinearColor(.3f,1,.45f);case EEcoHerdJourneyState::Failed:return FLinearColor(1,.25f,.65f);
    case EEcoHerdJourneyState::Resting:return FLinearColor(.85f,.65f,1);case EEcoHerdJourneyState::Preparing:return FLinearColor(1,.8f,.25f);
    default:return FLinearColor(.2f,.85f,1);}
}
}
void EcoHerdMigrationDebug::Draw(AHUD& H,APlayerController& Player,FVector2D Size,const FEcoHerdMigrationDebugSnapshot& S,int64 Focus,int32 DebugMode)
{
    const float W=FMath::Clamp(float(Size.X*.32),300.f,430.f),X=Size.X-W-16,Y=16;
    const auto* P=S.Plans.FindByPredicate([&](const auto& V){return V.Id==Focus;});
    H.DrawRect(FLinearColor(.015f,.025f,.04f,.9f),X,Y,W,376);
    H.DrawText(TEXT("HERD MIGRATION   M: hide   [ ]: herd"),FLinearColor::White,X+12,Y+10,nullptr,.9f);
    const FLinearColor Cyan(.2f,.85f,1),Gold(1,.8f,.2f),Grey(.45f,.52f,.58f);
    H.DrawText(TEXT("Cyan route   Gold destination   Dots: real agents"),Grey,X+12,Y+31,nullptr,.75f);
    if(S.Routes.IsEmpty()){H.DrawText(TEXT("Waiting for authored route/runtime"),Gold,X+12,Y+70,nullptr,.9f);return;}
    FBox Bounds(ForceInit);for(const auto& R:S.Regions){Bounds+=R.Minimum;Bounds+=R.Maximum;}
    for(const auto& R:S.Routes)for(const auto& Point:R.Points)Bounds+=Point;
    const FVector Span=Bounds.GetSize();const float MapX=X+178,MapY=Y+56,MapW=W-194,MapH=204;
    const double Scale=FMath::Min(MapW/FMath::Max(1.,Span.X),MapH/FMath::Max(1.,Span.Y));
    const FVector2D Center(MapX+MapW*.5,MapY+MapH*.5);
    auto Map=[&](const FVector& V){const auto D=V-Bounds.GetCenter();return Center+FVector2D(D.X*Scale,-D.Y*Scale);};
    auto Line=[&](FVector2D A,FVector2D B,FLinearColor C,float Width=1){H.DrawLine(A.X,A.Y,B.X,B.Y,C,Width);};
    for(const auto& R:S.Regions){const auto A=Map(R.Minimum),B=Map(R.Maximum);
        const bool Target=P&&P->Destination==R.Id;const auto C=Target?Gold:Grey;
        Line(A,{A.X,B.Y},C,2);Line({A.X,B.Y},B,C,2);Line(B,{B.X,A.Y},C,2);Line({B.X,A.Y},A,C,2);
        const float LabelY=(A.Y+B.Y)*.5f-19;
        H.DrawText(R.Id.ToString(),C,X+12,LabelY,nullptr,1.05f);
        H.DrawText(FString::Printf(TEXT("Food %.0f%%   Pop %d"),100*R.FoodFraction,R.Population),
            R.FoodFraction<.25?Gold:FLinearColor::White,X+12,LabelY+21,nullptr,.9f);
    }
    for(const auto& R:S.Routes)for(int32 I=1;I<R.Points.Num();++I){
        Line(Map(R.Points[I-1]),Map(R.Points[I]),Cyan,2);
        DrawDebugLine(Player.GetWorld(),R.Points[I-1]+FVector(0,0,100),R.Points[I]+FVector(0,0,100),Cyan.ToFColor(true),false,0,1,3);
    }
    // A known corridor may be bidirectional. Arrow direction follows the selected plan,
    // including its reversed return path, rather than the authored route's storage order.
    if(P)for(int32 I=1;I<P->Points.Num();++I)
        DrawDebugDirectionalArrow(Player.GetWorld(),P->Points[I-1]+FVector(0,0,100),P->Points[I]+FVector(0,0,100),110,Cyan.ToFColor(true),false,0,1,5);
    for(const auto& M:S.Members){if(!Bounds.IsInsideXY(M.Position))continue;const auto Dot=Map(M.Position);
        FLinearColor C=Grey;float Radius=2;
        if(M.Plan>0){const auto* Plan=S.Plans.FindByPredicate([&](const auto& V){return V.Id==M.Plan;});
            C=Plan?StateColor(Plan->State):Grey;if(M.Plan==Focus){Radius=3;C=FLinearColor::White;}}
        H.DrawRect(C,Dot.X-Radius,Dot.Y-Radius,Radius*2,Radius*2);
        if(M.bActive&&(M.Plan==Focus||DebugMode>1)){
            DrawDebugSphere(Player.GetWorld(),M.Position+FVector(0,0,95),60,8,C.ToFColor(true),false,0,1,2);
            DrawDebugLine(Player.GetWorld(),M.Position+FVector(0,0,95),M.Goal+FVector(0,0,95),C.ToFColor(true),false,0,1,1);
        }
    }
    int32 Active=0,Completed=0;for(const auto& V:S.Plans){Active+=V.State!=EEcoHerdJourneyState::Settled;Completed+=V.State==EEcoHerdJourneyState::Settled;}
    H.DrawText(FString::Printf(TEXT("Active herds %d   Finished %d   Known routes %d"),Active,Completed,S.Routes.Num()),FLinearColor::White,X+12,Y+267,nullptr,.85f);
    if(P){
        int32 AtTarget=0,Live=0,Waypoint=0;for(const auto& M:S.Members)if(M.Plan==P->Id){++Live;AtTarget+=M.Region==P->Destination;Waypoint=FMath::Max(Waypoint,M.Waypoint);}
        H.DrawText(FString::Printf(TEXT("Herd %lld / Plan %lld   %s -> %s"),P->Herd,P->Id,*P->Origin.ToString(),*P->Destination.ToString()),Gold,X+12,Y+289,nullptr,.9f);
        H.DrawText(FString::Printf(TEXT("%s%s   waypoint %d/%d"),UEcoHerdMigrationSubsystem::StateName(P->State),P->bReturning?TEXT(" (return)"):TEXT(""),Waypoint+1,P->Points.Num()),StateColor(P->State),X+12,Y+311,nullptr,.9f);
        H.DrawText(FString::Printf(TEXT("In target %d/%d   Finished %d   Dead %d"),AtTarget,Live,P->Arrived,P->Dead),FLinearColor::White,X+12,Y+332,nullptr,.85f);
        H.DrawText(P->Reason.ToString(),Grey,X+12,Y+352,nullptr,.8f);
        if(!P->Points.IsEmpty()){
            const FVector Target=P->Points.Last()+FVector(0,0,100);
            DrawDebugSphere(Player.GetWorld(),Target,250,16,Gold.ToFColor(true),false,0,1,4);
            FVector2D Screen;if(Player.ProjectWorldLocationToScreen(Target+FVector(0,0,300),Screen)&&Screen.X>0&&Screen.X<Size.X&&Screen.Y>0&&Screen.Y<Size.Y)
                H.DrawText(FString::Printf(TEXT("DESTINATION: %s"),*P->Destination.ToString()),Gold,Screen.X,Screen.Y,nullptr,1.1f);
        }
    }else H.DrawText(TEXT("No departure. Sustained food shortage starts a journey."),Gold,X+12,Y+302,nullptr,.8f);
}

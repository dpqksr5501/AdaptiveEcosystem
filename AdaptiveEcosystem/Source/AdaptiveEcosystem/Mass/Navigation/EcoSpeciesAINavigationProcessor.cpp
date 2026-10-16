#include "AI/Behavior/EcoSpeciesAIProcessors.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"
#include "MassNavigationFragments.h"
#include "MassNavMeshNavigationFragments.h"
#include "MassNavMeshNavigationProcessors.h"
#include "NavigationSystem.h"
#include "NavCorridor.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformTime.h"
#include "Engine/World.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
namespace
{
    TAutoConsoleVariable<int32> PathBudget(TEXT("eco.SpeciesAI.PathQueries"),8,TEXT("Maximum synchronous full path queries per frame."));
    TAutoConsoleVariable<float> PathMilliseconds(TEXT("eco.SpeciesAI.PathMilliseconds"),2.f,TEXT("Soft GT path budget; one query is not interruptible."));
}
UEcoSpeciesAINavigationProcessor::UEcoSpeciesAINavigationProcessor():Query(*this)
{
    ExecutionFlags=int32(EProcessorExecutionFlags::Server|EProcessorExecutionFlags::Standalone);
    bRequiresGameThreadExecution=true;ProcessingPhase=EMassProcessingPhase::PrePhysics;
    ExecutionOrder.ExecuteInGroup=UE::Mass::ProcessorGroupNames::Tasks;
    ExecutionOrder.ExecuteAfter.Add(TEXT("EcoSpeciesAIActivityProcessor"));
    ExecutionOrder.ExecuteBefore.Add(UMassNavMeshPathFollowProcessor::StaticClass()->GetFName());
}
void UEcoSpeciesAINavigationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>&)
{
    Query.AddTagRequirement<FEcoGroundedNavigationTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
    Query.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSpeciesAIMoveFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FMassMoveTargetFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FMassNavMeshCachedPathFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FMassNavMeshShortPathFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FMassDesiredMovementFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FMassForceFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddConstSharedRequirement<FEcoSpeciesAISharedFragment>();
}
void UEcoSpeciesAINavigationProcessor::Execute(FMassEntityManager& EM,FMassExecutionContext& Context)
{
    TRACE_CPUPROFILER_EVENT_SCOPE(EcoSpeciesAI_Navigation);
    UWorld* W=GetWorld();if(!W)return;const double Now=W->GetTimeSeconds();
    struct FCandidate{FMassEntityHandle Entity;double Since;int64 Id;bool Urgent;};TArray<FCandidate> Pending;
    Query.ForEachEntityChunk(Context,[&](FMassExecutionContext& C)
    {
        auto Moves=C.GetMutableFragmentView<FEcoSpeciesAIMoveFragment>();auto Targets=C.GetMutableFragmentView<FMassMoveTargetFragment>();
        auto Paths=C.GetMutableFragmentView<FMassNavMeshShortPathFragment>();auto Cached=C.GetMutableFragmentView<FMassNavMeshCachedPathFragment>();
        auto Desired=C.GetMutableFragmentView<FMassDesiredMovementFragment>();auto Forces=C.GetMutableFragmentView<FMassForceFragment>();
        const auto T=C.GetFragmentView<FTransformFragment>();const auto Ids=C.GetFragmentView<FEcoIdentityFragment>();
        for(int32 I=0;I<C.GetNumEntities();++I)
        {
            auto& M=Moves[I];auto& Target=Targets[I];
            if(M.Speed<=0||M.Status==EEcoAINavigationStatus::None||M.Status==EEcoAINavigationStatus::Arrived)
            {
                if(Target.GetCurrentAction()!=EMassMovementAction::Stand)Target.CreateNewAction(EMassMovementAction::Stand,*W);
                Target.Center=T[I].GetTransform().GetLocation();Target.DesiredSpeed.Set(0);Paths[I].Reset();Cached[I].NavPath.Reset();Cached[I].Corridor.Reset();
                Desired[I].DesiredVelocity=FVector::ZeroVector;Forces[I].Value=FVector::ZeroVector;continue;
            }
            if(M.Status==EEcoAINavigationStatus::Following&&Cached[I].NavPath.IsValid()&&Cached[I].NavPath->IsValid())
            {
                Target.DesiredSpeed.Set(M.Speed);
                if(Paths[I].IsDone()&&Paths[I].bPartialResult&&Cached[I].Corridor.IsValid())
                {
                    Paths[I].RequestShortPath(Cached[I].Corridor,Cached[I].NavPathNextStartIndex,FMassNavMeshCachedPathFragment::NumLeadingPoints,M.Radius);
                    Cached[I].NavPathNextStartIndex+=uint16(FMath::Max(int32(Paths[I].NumPoints)-int32(FMassNavMeshShortPathFragment::NumPointsBeyondUpdate)-1,0));
                }
                continue;
            }
            if(Now<M.RetryAfter)continue;
            Pending.Add({C.GetEntity(I),M.RequestedAt,Ids[I].StableAgentId,M.Activity==EEcoSpeciesActivity::Flee||M.Activity==EEcoSpeciesActivity::Pursue});
        }
    });
    // Aging prevents ordinary wander requests from starving behind perpetual pursuit requests.
    Pending.Sort([Now](const auto& A,const auto& B){const double AP=A.Since-(A.Urgent?1:0),BP=B.Since-(B.Urgent?1:0);return AP==BP?A.Id<B.Id:AP<BP;});
    auto* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(W);int32 Count=0;const double Start=FPlatformTime::Seconds();
    for(const auto& Candidate:Pending)
    {
        if(Count>=FMath::Max(1,PathBudget.GetValueOnGameThread())||(Count>0&&(FPlatformTime::Seconds()-Start)*1000>=FMath::Max(.1f,PathMilliseconds.GetValueOnGameThread())))break;
        ++Count;const auto E=Candidate.Entity;if(!EM.IsEntityValid(E))continue;
        auto& M=EM.GetFragmentDataChecked<FEcoSpeciesAIMoveFragment>(E);
        const auto* P=EM.GetConstSharedFragmentDataPtr<FEcoSpeciesAISharedFragment>(E)->Profile.Get();if(!P)continue;
        auto& Target=EM.GetFragmentDataChecked<FMassMoveTargetFragment>(E);auto& Short=EM.GetFragmentDataChecked<FMassNavMeshShortPathFragment>(E);
        auto& Cache=EM.GetFragmentDataChecked<FMassNavMeshCachedPathFragment>(E);
        const FVector Position=EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
        auto Fail=[&](){M.Status=EEcoAINavigationStatus::Failed;M.RetryAfter=Now+P->RepathInterval;++M.Failures;
            Short.Reset();Cache.NavPath.Reset();Cache.Corridor.Reset();Target.CreateNewAction(EMassMovementAction::Stand,*W);Target.DesiredSpeed.Set(0);};
        if(!Nav||Now>M.Deadline){Fail();continue;}
        const FNavAgentProperties Agent(P->BodyRadius,P->BodyHeight);const ANavigationData* Data=Nav->GetNavDataForProps(Agent,Position);
        FNavLocation Projected;
        if(!Data||!Nav->ProjectPointToNavigation(M.Target,Projected,FVector(200,200,200),Data)
            ||FVector::DistSquared(Projected.Location,M.Target)>FMath::Square(FMath::Min(250.f,M.Radius))){Fail();continue;}
        if(FVector::DistSquared(Position,M.Target)<=FMath::Square(M.Radius)){M.Status=EEcoAINavigationStatus::Arrived;continue;}
        FPathFindingQuery Q(Nav,*Data,Position,Projected.Location);Q.SetAllowPartialPaths(false);
        const FPathFindingResult Result=Data->FindPath(Agent,Q);
        if(!Result.IsSuccessful()||!Result.Path.IsValid()||Result.Path->IsPartial()||Result.Path->GetPathPoints().Num()<2){Fail();continue;}
        Cache.NavPath=Result.Path;Cache.PathSource=EMassNavigationPathSource::NavMesh;Cache.Corridor=MakeShared<FNavCorridor>();
        FNavCorridorParams Parameters;Parameters.SetFromWidth(P->CorridorWidth);Parameters.PathOffsetFromBoundaries=P->BodyRadius;
        Cache.Corridor->BuildFromPath(*Result.Path,Data->GetDefaultQueryFilter(),Parameters);
        if(!Short.RequestShortPath(Cache.Corridor,0,0,M.Radius)){Fail();continue;}
        Cache.NavPathNextStartIndex=uint16(FMath::Max(int32(Short.NumPoints)-int32(FMassNavMeshShortPathFragment::NumPointsBeyondUpdate)-1,0));
        M.PlannedTarget=M.Target;M.PlannedRevision=M.Revision;M.Status=EEcoAINavigationStatus::Following;M.LastProgress=Now;M.BestDistance=FVector::Dist(Position,M.Target);M.RetryAfter=Now+P->RepathInterval;
        Target.Center=Position;Target.DesiredSpeed.Set(M.Speed);Target.CreateNewAction(EMassMovementAction::Move,*W);
    }
}

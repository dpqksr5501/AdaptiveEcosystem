#include "AI/Behavior/EcoSpeciesAIProcessors.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "Mass/Movement/EcoSpeciesAIGroundConstraint.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassMovementFragments.h"
#include "MassExecutionContext.h"
#include "AI/Social/EcoSocialFragments.h"
#include "World/EcoWorldClockSubsystem.h"
#include "Engine/World.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
UEcoSpeciesAIMovementProcessor::UEcoSpeciesAIMovementProcessor():Query(*this)
{
    ExecutionFlags=int32(EProcessorExecutionFlags::Server|EProcessorExecutionFlags::Standalone);
    bRequiresGameThreadExecution=true;ProcessingPhase=EMassProcessingPhase::PrePhysics;
    ExecutionOrder.ExecuteInGroup=UE::Mass::ProcessorGroupNames::Movement;
    ExecutionOrder.ExecuteAfter.Add(UE::Mass::ProcessorGroupNames::ApplyForces);
}
void UEcoSpeciesAIMovementProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>&)
{
    Query.AddTagRequirement<FEcoGroundedNavigationTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);Query.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);Query.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FMassDesiredMovementFragment>(EMassFragmentAccess::ReadWrite);Query.AddRequirement<FEcoSpeciesAIMoveFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoSpeciesAIInputFragment>(EMassFragmentAccess::ReadOnly);Query.AddRequirement<FEcoSpeciesAIExecutionFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSpeciesAIFeedingFragment>(EMassFragmentAccess::ReadWrite);Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSocialMovementRequestFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoShelterMovementFeedbackFragment>(EMassFragmentAccess::ReadWrite,EMassFragmentPresence::Optional);
    Query.AddConstSharedRequirement<FEcoSpeciesAISharedFragment>();
}
void UEcoSpeciesAIMovementProcessor::Execute(FMassEntityManager&,FMassExecutionContext& Context)
{
    TRACE_CPUPROFILER_EVENT_SCOPE(EcoSpeciesAI_Movement);
    UWorld* W=GetWorld();const float FrameDelta=Context.GetDeltaTimeSeconds();if(!W||!FMath::IsFinite(FrameDelta)||FrameDelta<=0)return;
    const float Delta=FMath::Min(FrameDelta,.1f);const double Now=W->GetTimeSeconds();
    const auto* Clock=W->GetSubsystem<UEcoWorldClockSubsystem>();const double EcologyStart=Clock?Clock->GetServerTime().ServerTimeSeconds:0;
    Query.ForEachEntityChunk(Context,[&](FMassExecutionContext& C)
    {
        auto T=C.GetMutableFragmentView<FTransformFragment>();auto Velocity=C.GetMutableFragmentView<FMassVelocityFragment>();
        auto Desired=C.GetMutableFragmentView<FMassDesiredMovementFragment>();auto Moves=C.GetMutableFragmentView<FEcoSpeciesAIMoveFragment>();
        auto Food=C.GetMutableFragmentView<FEcoSpeciesAIFeedingFragment>();const auto Input=C.GetFragmentView<FEcoSpeciesAIInputFragment>();
        const auto Exec=C.GetFragmentView<FEcoSpeciesAIExecutionFragment>();const auto Region=C.GetFragmentView<FEcoRegionFragment>();
        const auto Travel=C.GetFragmentView<FEcoTravelFragment>();const auto Vitals=C.GetFragmentView<FEcoVitalsFragment>();
        const auto Request=C.GetFragmentView<FEcoSocialMovementRequestFragment>();auto Feedback=C.GetMutableFragmentView<FEcoShelterMovementFeedbackFragment>();
        const auto* P=C.GetConstSharedFragment<FEcoSpeciesAISharedFragment>().Profile.Get();if(!P)return;
        for(int32 I=0;I<C.GetNumEntities();++I)
        {
            auto& M=Moves[I];const FVector Start=T[I].GetTransform().GetLocation();FVector Next=Start;
            M.ClampedSeconds+=FrameDelta-Delta;
            const bool CanMove=Vitals[I].HP>0&&M.Speed>0&&M.Status==EEcoAINavigationStatus::Following&&M.PlannedRevision==M.Revision;
            FVector V=CanMove?Desired[I].DesiredVelocity.GetClampedToMaxSize(M.Speed):FVector::ZeroVector;
            const int32 Substeps=FMath::Clamp(FMath::CeilToInt(V.Size()*Delta/FMath::Max(1.f,P->BodyRadius)),1,16);
            bool Blocked=false;
            for(int32 S=0;S<Substeps&&!V.IsNearlyZero();++S)
            {
                FVector End=Next+V*(Delta/Substeps);
                if(!EcoSpeciesAI::ConstrainGroundStep(*W,Region[I].CurrentRegionId,Travel[I].State==EEcoResidenceState::Traveling,Next,End,*P)){Blocked=true;break;}
                Next=End;
            }
            const FVector Actual=(Next-Start)/Delta;Velocity[I].Value=Actual;Desired[I].DesiredVelocity=Actual;
            auto& Transform=T[I].GetMutableTransform();Transform.SetLocation(Next);if(!Actual.IsNearlyZero())Transform.SetRotation(Actual.ToOrientationQuat());
            M.ActualTime=Now;
            const float Distance=FVector::Dist(Next,M.Target);
            if(CanMove&&Distance<=M.Radius){M.Status=EEcoAINavigationStatus::Arrived;Velocity[I].Value=Desired[I].DesiredVelocity=FVector::ZeroVector;}
            else if(CanMove&&Distance+10<M.BestDistance){M.BestDistance=Distance;M.LastProgress=Now;}
            else if(CanMove&&Now-M.LastProgress>P->PathTimeout)
            {M.Status=EEcoAINavigationStatus::Failed;M.RetryAfter=Now+P->RepathInterval;++M.Failures;}
            if(Blocked)++M.BlockedFrames;
            if(!Request.IsEmpty()&&!Feedback.IsEmpty()&&Request[I].bValid&&Request[I].ReservationId>0)
            {
                EEcoShelterMovementStatus Result=EEcoShelterMovementStatus::Yielded;
                if(M.Activity==EEcoSpeciesActivity::ShelterTravel||M.Activity==EEcoSpeciesActivity::ShelterHold)
                    Result=FVector::Dist(Next,Request[I].TargetPosition)<=Request[I].ArrivalRadius?EEcoShelterMovementStatus::Arrived:
                        (M.Status==EEcoAINavigationStatus::Failed?EEcoShelterMovementStatus::Failed:EEcoShelterMovementStatus::Moving);
                Feedback[I].Report(Request[I].ReservationId,Result);
            }
            if(Exec[I].Activity==EEcoSpeciesActivity::Graze&&Exec[I].SlotReservation>0&&Vitals[I].HP>0
                &&Travel[I].State==EEcoResidenceState::Resident&&!Input[I].bThreat&&Actual.Size2D()<=P->GrazeMaxSpeed)
                Food[I].Add(EcologyStart,EcologyStart+Delta,Region[I].CurrentRegionId);
        }
    });
}

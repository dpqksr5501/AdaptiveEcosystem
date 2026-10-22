#include "AI/Behavior/EcoSpeciesAIProcessors.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "AI/Behavior/EcoSpeciesAIActors.h"
#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"
#include "AI/Policy/EcoWorldProviders.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoBehaviorConfig.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "World/EcoWorldClockSubsystem.h"
#include "Engine/World.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
UEcoSpeciesAIAttackProcessor::UEcoSpeciesAIAttackProcessor():Query(*this),TargetQuery(*this)
{
    ExecutionFlags=int32(EProcessorExecutionFlags::Server|EProcessorExecutionFlags::Standalone);bRequiresGameThreadExecution=true;
    ProcessingPhase=EMassProcessingPhase::PrePhysics;ExecutionOrder.ExecuteAfter.Add(UE::Mass::ProcessorGroupNames::Movement);
}
void UEcoSpeciesAIAttackProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>&)
{
    Query.AddTagRequirement<FEcoGroundedNavigationTag>(EMassFragmentPresence::All);Query.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);TargetQuery.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);Query.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
    Query.AddRequirement<FEcoSpeciesAIAttackFragment>(EMassFragmentAccess::ReadWrite);Query.AddRequirement<FEcoSpeciesAIInputFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoPredatorStateFragment>(EMassFragmentAccess::ReadWrite);Query.AddConstSharedRequirement<FEcoSpeciesAISharedFragment>();
    TargetQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);TargetQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
    TargetQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
    TargetQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);TargetQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
    TargetQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadWrite);TargetQuery.AddRequirement<FEcoDeathFragment>(EMassFragmentAccess::ReadWrite);
    TargetQuery.AddRequirement<FEcoCreatureLifecycleFragment>(EMassFragmentAccess::ReadWrite);
    TargetQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);TargetQuery.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
}
void UEcoSpeciesAIAttackProcessor::Execute(FMassEntityManager& EM,FMassExecutionContext& Context)
{
    TRACE_CPUPROFILER_EVENT_SCOPE(EcoSpeciesAI_Attack);
    UWorld* W=GetWorld();if(!W)return;const double Now=W->GetTimeSeconds();
    TMap<int64,FMassEntityHandle> Targets;
    TargetQuery.ForEachEntityChunk(Context,[&](FMassExecutionContext& C)
    {const auto Id=C.GetFragmentView<FEcoIdentityFragment>();for(int32 I=0;I<C.GetNumEntities();++I)Targets.Add(Id[I].StableAgentId,C.GetEntity(I));});
    struct FPending{FMassEntityHandle Entity;int64 Id;double Time;};TArray<FPending> Pending;
    Query.ForEachEntityChunk(Context,[&](FMassExecutionContext& C)
    {
        auto Attack=C.GetMutableFragmentView<FEcoSpeciesAIAttackFragment>();auto Native=C.GetMutableFragmentView<FEcoPredatorStateFragment>();
        const auto Id=C.GetFragmentView<FEcoIdentityFragment>();
        for(int32 I=0;I<C.GetNumEntities();++I)
        {Native[I].EatCooldown=FMath::Max(0.f,float(Attack[I].CooldownUntil-Now));if(Attack[I].Requested>Attack[I].Resolved)Pending.Add({C.GetEntity(I),Id[I].StableAgentId,Attack[I].RequestedAt});}
    });
    Pending.Sort([](const auto& A,const auto& B){return A.Time==B.Time?A.Id<B.Id:A.Time<B.Time;});
    auto* Slots=W->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>();const auto* Clock=W->GetSubsystem<UEcoWorldClockSubsystem>();
    const auto* Registry=W->GetSubsystem<UEcoWorldProviderRegistry>();const auto* Cover=Registry?Registry->GetCoverProvider():nullptr;
    for(const auto& Request:Pending)
    {
        const auto E=Request.Entity;if(!EM.IsEntityValid(E))continue;
        auto& A=EM.GetFragmentDataChecked<FEcoSpeciesAIAttackFragment>(E);A.Resolved=A.Requested;
        A.RetryAfter=Now+.25; // Failed attacks cannot create an unbounded per-frame request storm.
        const auto& I=EM.GetFragmentDataChecked<FEcoSpeciesAIInputFragment>(E);const auto* P=EM.GetConstSharedFragmentDataPtr<FEcoSpeciesAISharedFragment>(E)->Profile.Get();
        const auto& V=EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);const auto& Travel=EM.GetFragmentDataChecked<FEcoTravelFragment>(E);
        if(!P||V.HP<=0||Travel.State!=EEcoResidenceState::Resident||!(I.Target==A.Target)||!I.bFreshSight||Now-I.CueTime>.25
            ||Now-A.RequestedAt>.25||Now<A.CooldownUntil){++A.Rejections;continue;}
        const FVector Start=EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
        FVector End;FMassEntityHandle Prey;AEcoSpeciesAIFixture* Fixture=nullptr;
        if(A.Target.Domain==EEcoAITargetDomain::Entity)
        {
            const auto* Found=Targets.Find(A.Target.Id);if(!Found||!EM.IsEntityValid(*Found)){++A.Rejections;continue;}
            Prey=*Found;End=EM.GetFragmentDataChecked<FTransformFragment>(Prey).GetTransform().GetLocation();
            if(EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId!=EM.GetFragmentDataChecked<FEcoRegionFragment>(Prey).CurrentRegionId
                ||EM.GetFragmentDataChecked<FEcoTravelFragment>(Prey).State!=EEcoResidenceState::Resident){++A.Rejections;continue;}
            if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(Prey).HP<=0){++A.Rejections;continue;}
        }
        else if(Slots&&Slots->bAllowFixtures)
        {Fixture=Slots->FindFixture(A.Target.Id);if(!Fixture||!Fixture->IsAvailable(Now)){++A.Rejections;continue;}End=Fixture->GetActorLocation();}
        else {++A.Rejections;continue;}
        const float Perceived=FVector::Dist2D(Start,End)*(Cover&&Cover->IsInCover(End)?EcoBehaviorConfig::CoverHideMult:1.f);
        FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoSpeciesAttack),true);if(Fixture)Params.AddIgnoredActor(Fixture);
        if(Perceived>P->AttackRadius||W->LineTraceSingleByChannel(Hit,Start+FVector(0,0,80),End+FVector(0,0,80),ECC_Visibility,Params))
        {++A.Rejections;continue;}
        if(Fixture)
        {
            if(!Fixture->TryCapture(Now)){++A.Rejections;continue;}
            Slots->QueueFixtureReward(Request.Id,Fixture->NutritionUnits,Clock?Clock->GetServerTime().ServerTimeSeconds+Context.GetDeltaTimeSeconds():0);
        }
        else
        {
            // Stamp a lethal candidate; the existing coordinator commits Death/Population/Reward once.
            EM.GetFragmentDataChecked<FEcoVitalsFragment>(Prey).HP=0;
            auto& Death=EM.GetFragmentDataChecked<FEcoDeathFragment>(Prey);Death.Cause=EEcoDeathCause::Predation;Death.PredatorStableAgentId=Request.Id;
            EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(Prey).bPredated=true;
        }
        ++A.Successes;A.CooldownUntil=Now+P->AttackCooldown;
        EM.GetFragmentDataChecked<FEcoPredatorStateFragment>(E).EatCooldown=P->AttackCooldown;
    }
}

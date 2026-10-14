#include "AI/Behavior/EcoSpeciesAIProcessors.h"
#include "AI/Behavior/EcoSpeciesAIExecution.h"
#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassExecutionContext.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Engine/World.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
UEcoSpeciesAIActivityProcessor::UEcoSpeciesAIActivityProcessor():Query(*this)
{
    ExecutionFlags=int32(EProcessorExecutionFlags::Server|EProcessorExecutionFlags::Standalone);bRequiresGameThreadExecution=true;
    ProcessingPhase=EMassProcessingPhase::PrePhysics;QueryBasedPruning=EMassQueryBasedPruning::Never;
    ExecutionOrder.ExecuteAfter.Add(UE::Mass::ProcessorGroupNames::Behavior);
    ExecutionOrder.ExecuteBefore.Add(UE::Mass::ProcessorGroupNames::Tasks);
}
void UEcoSpeciesAIActivityProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>&)
{
    Query.AddTagRequirement<FEcoGroundedNavigationTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);Query.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
    Query.AddRequirement<FEcoSpeciesAIInputFragment>(EMassFragmentAccess::ReadOnly);Query.AddRequirement<FEcoSpeciesAIDecisionFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSpeciesAIExecutionFragment>(EMassFragmentAccess::ReadWrite);Query.AddRequirement<FEcoSpeciesAIMoveFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoSpeciesAIAttackFragment>(EMassFragmentAccess::ReadWrite);Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSocialMovementRequestFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddConstSharedRequirement<FEcoSpeciesAISharedFragment>();
}
void UEcoSpeciesAIActivityProcessor::Execute(FMassEntityManager& EM,FMassExecutionContext& Context)
{
    TRACE_CPUPROFILER_EVENT_SCOPE(EcoSpeciesAI_Activity);
    UWorld* W=GetWorld();if(!W)return;const double Now=W->GetTimeSeconds();
    auto* Slots=W->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>();if(Slots)Slots->Cleanup(EM,Now);
    Query.ForEachEntityChunk(Context,[&](FMassExecutionContext& C)
    {
        const auto* P=C.GetConstSharedFragment<FEcoSpeciesAISharedFragment>().Profile.Get();if(!P)return;
        const auto Input=C.GetFragmentView<FEcoSpeciesAIInputFragment>();const auto Decision=C.GetFragmentView<FEcoSpeciesAIDecisionFragment>();
        auto Exec=C.GetMutableFragmentView<FEcoSpeciesAIExecutionFragment>();auto Moves=C.GetMutableFragmentView<FEcoSpeciesAIMoveFragment>();
        auto Attacks=C.GetMutableFragmentView<FEcoSpeciesAIAttackFragment>();const auto Id=C.GetFragmentView<FEcoIdentityFragment>();
        const auto Region=C.GetFragmentView<FEcoRegionFragment>();const auto V=C.GetFragmentView<FEcoVitalsFragment>();
        const auto Travel=C.GetFragmentView<FEcoTravelFragment>();const auto Social=C.GetFragmentView<FEcoSocialMovementRequestFragment>();
        const auto Raw=C.GetFragmentView<FEcoPolicyOutputFragment>();const auto Modulated=C.GetFragmentView<FEcoSocialBehaviorFragment>();
        const auto Alarms=C.GetFragmentView<FEcoAlarmStateFragment>();
        for(int32 N=0;N<C.GetNumEntities();++N)
        {
            auto& E=Exec[N];auto& M=Moves[N];
            const bool AuthorityOverride=V[N].HP<=0||!Input[N].bValid||Travel[N].State!=EEcoResidenceState::Resident
                ||(!Social.IsEmpty()&&Social[N].bValid&&Social[N].Mode!=EEcoSocialMovementMode::None);
            if(AuthorityOverride)
            {
                if(E.SlotReservation>0){if(Slots)Slots->Release(E.SlotReservation);E.SlotReservation=0;}
                if(V[N].HP<=0||!Input[N].bValid)M.Hold(Now);
                else if(Travel[N].State!=EEcoResidenceState::Resident)
                {
                    if(M.Activity!=EEcoSpeciesActivity::Travel)M.Hold(Now);
                    M.Activity=E.Activity=EEcoSpeciesActivity::Travel;
                    if(Travel[N].State==EEcoResidenceState::Traveling)M.SetTarget(Travel[N].TargetPosition,Travel[N].MoveSpeed,P->ArrivalRadius,Now,*P);else M.Hold(Now);
                }
                else
                {
                    const auto& R=Social[N];const auto Mode=R.Mode==EEcoSocialMovementMode::ShelterHold?EEcoSpeciesActivity::ShelterHold:EEcoSpeciesActivity::ShelterTravel;
                    if(M.Activity!=Mode)M.Hold(Now);M.Activity=E.Activity=Mode;
                    if(R.ValidUntilWorldTime<=Now||R.TargetPosition.ContainsNaN()||R.ReservationId<=0)M.Hold(Now);
                    else if(FVector::Dist(Input[N].Position,R.TargetPosition)<=R.ArrivalRadius)M.Hold(Now);
                    else M.SetTarget(R.TargetPosition,P->RunSpeed,R.ArrivalRadius,Now,*P);
                }
                continue;
            }
            if(P->bPredator)
            {
                if(Decision[N].Activity!=EEcoSpeciesActivity::Rest&&E.SlotReservation>0)
                {if(Slots)Slots->Release(E.SlotReservation);E.SlotReservation=0;}
                EcoSpeciesAI::ExecuteWolf(Input[N],Decision[N],*P,E,M,Attacks[N],Id[N].StableAgentId,Now);
                if(E.Activity==EEcoSpeciesActivity::Rest&&Slots)
                {
                    FVector Goal;
                    if(M.Status==EEcoAINavigationStatus::Failed&&E.SlotReservation>0)
                    {Slots->RejectUnreachable(E.SlotReservation,Now);E.SlotReservation=0;E.NextSlotAttempt=Now+1;}
                    if(E.SlotReservation>0&&!Slots->Renew(E.SlotReservation,Id[N].StableAgentId,Now,P->SlotLease,Goal))
                    {Slots->Release(E.SlotReservation);E.SlotReservation=0;E.NextSlotAttempt=Now+1;}
                    if(!E.SlotReservation&&Now>=E.NextSlotAttempt)
                    {E.SlotKind=EEcoActivitySlotKind::Rest;E.SlotReservation=Slots->Claim(C.GetEntity(N),Id[N].StableAgentId,Region[N].CurrentRegionId,true,E.SlotKind,Input[N].Position,Now,P->SlotLease,Goal);E.NextSlotAttempt=Now+1;}
                    if(E.SlotReservation>0)
                    {if(FVector::Dist(Input[N].Position,Goal)<=P->ArrivalRadius&&Slots->Occupy(E.SlotReservation,Id[N].StableAgentId))M.Hold(Now);else M.SetTarget(Goal,P->WalkSpeed,P->ArrivalRadius,Now,*P);}
                }
            }
            else
            {
                auto EffectiveInput=Input[N];
                // Consume this completed Social pass even when the next scheduled brain gather is later.
                if(!Alarms.IsEmpty()&&Alarms[N].State==EEcoSocialState::Panic&&Alarms[N].AlarmStrength>0&&!Alarms[N].LastThreatPosition.ContainsNaN())
                {EffectiveInput.bThreat=true;EffectiveInput.CuePosition=Alarms[N].LastThreatPosition;}
                EcoSpeciesAI::ExecuteDeer(EffectiveInput,Decision[N],*P,E,M,Slots,C.GetEntity(N),Id[N].StableAgentId,Region[N].CurrentRegionId,Now,
                    Modulated.IsEmpty()?Raw[N].Action:Modulated[N].ModulatedAction);
            }
        }
    });
}

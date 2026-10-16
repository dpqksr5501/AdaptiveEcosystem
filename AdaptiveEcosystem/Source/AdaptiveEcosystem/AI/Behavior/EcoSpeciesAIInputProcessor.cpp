#include "AI/Behavior/EcoSpeciesAIProcessors.h"
#include "AI/Behavior/EcoSpeciesAIBehavior.h"
#include "AI/Behavior/EcoSpeciesAIActors.h"
#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoWorldProviders.h"
#include "AI/Policy/EcoBehaviorConfig.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/Senses/EcoPredatorPerception.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassSimulationLOD.h"
#include "MassExecutionContext.h"
#include "MassSignalSubsystem.h"
#include "MassStateTreeTypes.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Engine/World.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Components/BoxComponent.h"
#include "AI/Policy/EcoObservationBuilder.h"
#include "AI/Policy/EcoRegionPredationSubsystem.h"
#include "HAL/IConsoleManager.h"

UEcoSpeciesAIInputProcessor::UEcoSpeciesAIInputProcessor():Query(*this)
{
    ExecutionFlags=int32(EProcessorExecutionFlags::Server|EProcessorExecutionFlags::Standalone);
    bRequiresGameThreadExecution=true;ProcessingPhase=EMassProcessingPhase::PrePhysics;
    ExecutionOrder.ExecuteAfter.Add(UE::Mass::ProcessorGroupNames::LOD);
    ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPerceptionProcessor"));
    ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPredatorPerceptionProcessor"));
    ExecutionOrder.ExecuteBefore.Add(UE::Mass::ProcessorGroupNames::Behavior);
    ExecutionOrder.ExecuteBefore.Add(TEXT("MassStateTreeActivationProcessor"));
}
void UEcoSpeciesAIInputProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>&)
{
    Query.AddTagRequirement<FEcoStateTreeBehaviorTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
    Query.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
    Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSpeciesAIInputFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddRequirement<FEcoSpeciesAIExecutionFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSpeciesAIAttackFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSteeringGeometryFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoObservationFragment>(EMassFragmentAccess::ReadWrite,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoSensoryStateFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoPreySenseFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FEcoSensoryProfileFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddRequirement<FMassSimulationLODFragment>(EMassFragmentAccess::ReadWrite,EMassFragmentPresence::Optional);
    Query.AddConstSharedRequirement<FEcoSpeciesAISharedFragment>();
    Query.AddSharedRequirement<FEcoSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    Query.AddSharedRequirement<FEcoPredatorSensesSharedFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
}
void UEcoSpeciesAIInputProcessor::Execute(FMassEntityManager&,FMassExecutionContext& Context)
{
    TRACE_CPUPROFILER_EVENT_SCOPE(EcoSpeciesAI_Input);
    UWorld* W=GetWorld();if(!W)return;
    const double Now=W->GetTimeSeconds();auto* Slots=W->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>();
    const auto* Herds=W->GetSubsystem<UEcoHerdSubsystem>();
    const auto* Geography=W->GetSubsystem<UEcologyWorldSubsystem>();
    const auto* Registry=W->GetSubsystem<UEcoWorldProviderRegistry>();const auto* Food=Registry?Registry->GetFoodProvider():nullptr;
    const auto* Cover=Registry?Registry->GetCoverProvider():nullptr;
    const auto* Predation=W->GetSubsystem<UEcoRegionPredationSubsystem>();
    const auto* PredationMode=IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Policy.PredationSource"));
    const bool GlobalHistory=PredationMode&&PredationMode->GetInt()!=0;
    auto* Signals=W->GetSubsystem<UMassSignalSubsystem>();TArray<FMassEntityHandle> Due;
    TArray<FVector> Viewers;for(auto It=W->GetPlayerControllerIterator();It;++It)
        if(const auto* PC=It->Get()){FVector Position;FRotator Rotation;PC->GetPlayerViewPoint(Position,Rotation);if(!Position.ContainsNaN())Viewers.Add(Position);}
    Query.ForEachEntityChunk(Context,[&](FMassExecutionContext& C)
    {
        const auto* P=C.GetConstSharedFragment<FEcoSpeciesAISharedFragment>().Profile.Get();if(!P)return;
        auto Inputs=C.GetMutableFragmentView<FEcoSpeciesAIInputFragment>();const auto Transforms=C.GetFragmentView<FTransformFragment>();
        const auto Vitals=C.GetFragmentView<FEcoVitalsFragment>();const auto Ids=C.GetFragmentView<FEcoIdentityFragment>();
        const auto Travel=C.GetFragmentView<FEcoTravelFragment>();
        const auto Regions=C.GetFragmentView<FEcoRegionFragment>();const auto Exec=C.GetFragmentView<FEcoSpeciesAIExecutionFragment>();
        const auto Attack=C.GetFragmentView<FEcoSpeciesAIAttackFragment>();const auto Geometry=C.GetFragmentView<FEcoSteeringGeometryFragment>();
        const auto Personal=C.GetFragmentView<FEcoSensoryStateFragment>();const auto Prey=C.GetFragmentView<FEcoPreySenseFragment>();
        const auto Members=C.GetFragmentView<FEcoHerdMemberFragment>();
        const auto Alarms=C.GetFragmentView<FEcoAlarmStateFragment>();
        const auto Profiles=C.GetFragmentView<FEcoSensoryProfileFragment>();
        const auto* SocialSpecies=C.GetSharedFragmentPtr<FEcoSocialSpeciesSharedFragment>();
        const auto* PredatorSpecies=C.GetSharedFragmentPtr<FEcoPredatorSensesSharedFragment>();
        const FEcoSensorySettings Settings=PredatorSpecies?PredatorSpecies->Settings:(SocialSpecies?SocialSpecies->Senses:FEcoSensorySettings());
        auto LOD=C.GetMutableFragmentView<FMassSimulationLODFragment>();auto Observations=C.GetMutableFragmentView<FEcoObservationFragment>();
        const auto& Species=C.GetSharedFragment<FEcoSpeciesSharedFragment>();
        for(int32 N=0;N<C.GetNumEntities();++N)
        {
            auto& I=Inputs[N];I.Now=Now;I.Position=Transforms[N].GetTransform().GetLocation();I.bPredator=P->bPredator;
            if(!I.Snapshot)I.Home=I.Position;
            I.bValid=Vitals[N].HP>0&&Ids[N].StableAgentId>0&&!I.Position.ContainsNaN();
            if(!I.bValid)continue;
            const bool PreviouslyUrgent=I.bThreat;
            const bool SocialPanic=!P->bPolicyOnly&&!Alarms.IsEmpty()&&Alarms[N].State==EEcoSocialState::Panic&&Alarms[N].AlarmStrength>0;
            if(SocialPanic&&!PreviouslyUrgent)I.NextDecision=FMath::Min(I.NextDecision,Now);
            double Distance=Viewers.IsEmpty()?double(P->FarDistance*P->FarDistance):DBL_MAX;
            for(const auto& Viewer:Viewers)Distance=FMath::Min(Distance,FVector::DistSquared(I.Position,Viewer));
            I.Tier=Distance<FMath::Square(P->MediumDistance)?0:(Distance<FMath::Square(P->FarDistance)?1:2);
            if(PreviouslyUrgent||SocialPanic||Attack[N].CooldownUntil>Now||Exec[N].SlotReservation>0||Exec[N].PursuitStarted>=0
                ||Travel[N].State!=EEcoResidenceState::Resident||Vitals[N].Energy<.15f*Vitals[N].MaxEnergy)I.Tier=0;
            if(!LOD.IsEmpty())LOD[N].LOD=I.Tier==0?EMassLOD::High:(I.Tier==1?EMassLOD::Medium:EMassLOD::Low);
            if(Now<I.NextDecision)continue;
            const auto* Region=Geography?Geography->GetRegion(Regions[N].CurrentRegionId):nullptr;
            if(!Region||!Region->RegionBounds){I.bValid=false;continue;}
            I.RegionFrame=Region->RegionBounds->GetComponentTransform();I.RegionExtent=Region->RegionBounds->GetUnscaledBoxExtent();
            const double Period=P->DecisionInterval*(P->bPolicyOnly?1:(I.Tier==0?1:(I.Tier==1?2:4)));
            if(I.NextDecision<=0)I.NextDecision=Now;
            I.NextDecision+=Period; // Preserve scheduling debt, one current snapshot per frame.
            I.Energy=FMath::Clamp(Vitals[N].Energy/FMath::Max(1.f,Vitals[N].MaxEnergy),0.f,1.f);
            if(I.Energy<P->HungryEnter)I.bHungry=true;else if(I.Energy>P->SatiatedExit)I.bHungry=false;
            I.FoodDensity=Food?Food->GetFoodDensity(I.Position,200):0.f;I.bThreat=false;I.bFreshSight=false;
            I.EvidenceConfidence=0;I.bHasGroup=false;
            if(I.Target.Domain==EEcoAITargetDomain::Fixture)
            {
                const auto* Fixture=Slots&&Slots->bAllowFixtures?Slots->FindFixture(I.Target.Id):nullptr;
                if(!Fixture||!Fixture->IsAvailable(Now)){I.Target={};I.FixtureCueConfidence=0;}
                else I.EvidenceConfidence=I.FixtureCueConfidence*FMath::Clamp(1.f-float((Now-I.CueTime)/6),0.f,1.f);
            }
            FEcoHerdRuntimeData Herd;
            if(!P->bPolicyOnly&&!Members.IsEmpty()&&Herds&&Herds->GetHerdData(Members[N].HerdRuntimeIndex,Herd))
            {I.bHasGroup=Herd.MemberCount>1;I.GroupPosition=Herd.Center;}
            if(!Prey.IsEmpty())
            {
                const auto& S=Prey[N];const auto Snapshot=S.Cue.MakeReadSnapshot(Now,Settings,Profiles.IsEmpty()?FEcoSensoryProfileFragment():Profiles[N],0);
                if(I.Target.Domain==EEcoAITargetDomain::Entity&&(!Snapshot.bHasPersonalThreat||S.TargetAgentId<=0))I.Target={};
                if(S.TargetAgentId>0&&Snapshot.bHasPersonalThreat)
                {I.Target={EEcoAITargetDomain::Entity,S.TargetAgentId};I.CuePosition=Snapshot.LastKnownPosition;I.CueTime=S.Cue.LastObservedTime;I.EvidenceConfidence=Snapshot.Confidence;
                    I.bFreshSight=S.Cue.LastDirectSense==EEcoSenseSource::Sight&&Now-I.CueTime<=.25;}
            }
            if(!Personal.IsEmpty())
            {
                const auto S=Personal[N].MakeReadSnapshot(Now,Settings,Profiles.IsEmpty()?FEcoSensoryProfileFragment():Profiles[N],0);
                if(S.bHasPersonalThreat){I.bThreat=true;I.CuePosition=S.LastKnownPosition;I.CueTime=Now-S.PersonalAgeSeconds;I.EvidenceConfidence=S.Confidence;}
                else if(S.bHasSharedThreat){I.bThreat=true;I.CuePosition=S.SharedReportedPosition;I.CueTime=Now-S.SharedEvidenceAgeSeconds;I.EvidenceConfidence=S.SharedAlarmStrength;}
            }
            // Explicit fixture candidates still go through FOV/range/LOS; never feed hidden live positions.
            float BestFixtureDistance=MAX_flt;bool FixtureSight=false;
            if(Slots&&Slots->bAllowFixtures&&!P->bPolicyOnly)for(const auto& Weak:Slots->GetFixtures())
            {
                const auto* F=Weak.Get();if(!F||F->bPrey!=P->bPredator||!F->IsAvailable(Now))continue;
                const FVector Delta=F->GetActorLocation()-I.Position;const float D=Delta.Size2D();
                if(D>Species.ViewDistance)continue;
                const bool InFOV=FVector::DotProduct(Transforms[N].GetTransform().GetRotation().GetForwardVector(),Delta.GetSafeNormal2D())
                    >=FMath::Cos(FMath::DegreesToRadians(Species.FOV*.5f));
                FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoSpeciesFixture),true);Params.AddIgnoredActor(F);
                const bool Occluded=W->LineTraceSingleByChannel(Hit,I.Position+FVector(0,0,80),F->GetActorLocation()+FVector(0,0,80),ECC_Visibility,Params);
                const bool Seen=F->bVisible&&InFOV&&!Occluded;
                const bool Heard=F->bMakesNoise&&D<Settings.HearingRange;
                if((!Seen&&!Heard)||(FixtureSight&&!Seen)||(Seen==FixtureSight&&D>=BestFixtureDistance))continue;
                BestFixtureDistance=D;FixtureSight=Seen;
                I.Target={EEcoAITargetDomain::Fixture,F->FixtureId};I.CuePosition=F->GetActorLocation();I.CueTime=Now;
                if(!Seen)
                {
                    // Hearing reports a reproducible coarse cue, never an exact hidden pose.
                    FRandomStream Noise(int32(HashCombine(GetTypeHash(Ids[N].StableAgentId),HashCombine(GetTypeHash(F->FixtureId),GetTypeHash(int32(Now))))));
                    I.CuePosition+=FVector(Noise.FRandRange(-300,300),Noise.FRandRange(-300,300),0);
                }
                I.FixtureCueConfidence=Seen?1.f:(Occluded?Settings.HearingConfidence*Settings.OccludedHearingMultiplier:Settings.HearingConfidence);
                I.EvidenceConfidence=I.FixtureCueConfidence;I.bFreshSight=Seen;I.bThreat=!P->bPredator;
            }
            if(I.Target.Domain==EEcoAITargetDomain::Fixture&&(Now-I.CueTime>6||!Slots||!Slots->bAllowFixtures))
            {I.Target={};I.bThreat=false;I.EvidenceConfidence=0;}
            else if(!P->bPredator&&I.EvidenceConfidence>0)I.bThreat=true;
            if(I.bThreat)I.CalmSince=-1;else if(I.CalmSince<0)I.CalmSince=Now;
            if(SocialPanic&&!Alarms[N].LastThreatPosition.ContainsNaN())
            {I.bThreat=true;I.CuePosition=Alarms[N].LastThreatPosition;I.CalmSince=-1;}
            const bool FoodSite=Slots&&Slots->FindSite(Regions[N].CurrentRegionId,P->bPredator,EEcoActivitySlotKind::Graze,I.Position,I.FoodPosition);
            I.bFoodAvailable=FoodSite&&Food&&Food->GetFoodDensity(I.FoodPosition,200)>0;
            if(P->bPolicyOnly&&!Observations.IsEmpty()&&!Geometry.IsEmpty())
            {
                auto& O=Observations[N].Observation;
                O=EcoObservation::Build(I.Position,Geometry[N],Vitals[N],Food,Cover,Predation,GlobalHistory);
                I.FoodDensity=O.FoodDensity;I.Energy=O.Energy;
                I.bThreat=O.PredatorCount>0;I.bHasGroup=O.ConspecificCount>0;I.bFoodAvailable=O.FoodDensity>0;
            }
            if(P->bPredator)EcoSpeciesAI::ScoreWolf(I,*P,Exec[N],Attack[N]);else EcoSpeciesAI::ScoreDeer(I,*P);
            ++I.Snapshot;Due.Add(C.GetEntity(N));
        }
    });
    if(Signals&&!Due.IsEmpty())Signals->SignalEntities(UE::Mass::Signals::NewStateTreeTaskRequired,Due);
}

#include "AI/Social/EcoPolicyV3SocialBridge.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/Herd/EcoHerdProcessors.h"
#include "AI/Social/Alarm/EcoThreatDetectionProcessor.h"
#include "AI/Social/Alarm/EcoAlarmProcessors.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassCommonTypes.h"
#include "Engine/World.h"

FEcoSocialSignalSnapshot EcoV3Social::ReadSignal(const FEcoSensoryStateFragment& Sense,const FEcoAlarmStateFragment& Alarm,
    int64 CurrentHerdId,double Now,const FEcoSensorySettings& Settings)
{
    FEcoSocialSignalSnapshot S;
    if(!FMath::IsFinite(Now))return S;
    const auto Read=Sense.MakeReadSnapshot(Now,Settings,FEcoSensoryProfileFragment(),CurrentHerdId);
    if(Read.bHasPersonalThreat){
        S.bValid=true;S.bDirect=Read.bFreshDirectEvidence;S.PersonalSource=Read.PersonalSource;
        S.ReportedPosition=Read.LastKnownPosition;S.Strength=Read.ThreatStrength*Read.Confidence;
        S.EvidenceTime=Sense.LastObservedTime;S.ReceivedTime=Sense.LastObservedTime;S.SourceKey=Sense.SourceKey;
    }else if(Read.bHasSharedThreat){
        S.bValid=true;S.ReportedPosition=Read.SharedReportedPosition;S.Strength=FMath::Min(Read.SharedAlarmStrength,Alarm.AlarmStrength);
        S.EvidenceTime=Sense.SharedEvidenceWorldTime;S.ReceivedTime=Sense.SharedReceivedWorldTime;S.PersistentHerdId=CurrentHerdId;
    }
    S.bValid=S.bValid&&S.Strength>0&&!S.ReportedPosition.ContainsNaN();return S;
}

FEcoPolicyActionV1 EcoV3Social::ProjectPolicy(int32 Request)
{
    namespace R = EcoRepertoireV3;
    FEcoPolicyActionV1 A;
    A.Forage = Request == R::kGraze ? 1.f : 0.f;
    A.Cohesion = static_cast<float>(R::kR1bConfig.GrazeCohesion);
    A.FleeDist = Request == R::kFlee ? 1.f : 0.f;
    A.Cover = Request == R::kHide ? 1.f : 0.f;
    return A;
}

bool EcoV3Social::IsShelterTarget(const FEcoV3RegionContext& Region,const FVector& Position)
{
    if(Position.ContainsNaN())return false;
    const auto P=Region.CmToUnits(Position);
    if(P.X<0||P.Y<0||P.X>Region.Sim.Config.WorldSize||P.Y>Region.Sim.Config.WorldSize)return false;
    for(const auto& Cover:Region.Sim.Config.Covers)
        if((P.X-Cover.X)*(P.X-Cover.X)+(P.Y-Cover.Y)*(P.Y-Cover.Y)<=Cover.Radius*Cover.Radius)return true;
    return false;
}

bool EcoV3Social::ApplyControl(const FEcoSocialMovementRequestFragment& Request, const FEcoAlarmStateFragment& Alarm,
    const FEcoV3RegionContext& Region, const FEcoIntegratedV3Fragment& Link, FEcoV3SocialBridgeFragment& Audit,
    const EcoWorldV3::FHerbView& H, bool bLeaseValid, double Now)
{
    namespace R = EcoRepertoireV3;
    const auto Previous=Audit.Applied;
    Audit.Applied = EEcoV3SocialControl::None;
    Audit.NativeBehavior = H.Rep ? H.Rep->Behavior : -1;
    Audit.AppliedReservation = 0;
    Audit.bRejectedUnsafeShelter = false;
    if (!Request.bValid || !H.IsValid() || H.Body->DeathCause != EcoWorldV3::kDeathNone) return false;
    const auto& A = Request.EffectiveAction;
    if (!FMath::IsFinite(A.Forage) || !FMath::IsFinite(A.Cohesion) || !FMath::IsFinite(A.FleeDist) || !FMath::IsFinite(A.Cover)) return false;
    auto& S = *H.Rep;
    const auto& W = Region.Sim;
    // Capacity allocates standing positions, not safety. A missing lease must never evict protected prey.
    if(W.Config.bProtectedRefuges&&EcoRefugeV3::Contains(W.Config.Covers,H.Body->Pos)
        &&(!bLeaseValid||Request.Mode==EEcoSocialMovementMode::None))return false;
    const auto& Cfg = W.RepCfg;
    auto In = EcoWorldV3::Detail::MakeControlInput(W, H);
    In.ToCentroid = R::Scale(In.ToCentroid, FMath::Clamp(double(A.Cohesion),0.,1.) / Cfg.GrazeCohesion);
    const FVector Position = Region.UnitsToCm(H.Body->Pos.X,H.Body->Pos.Y,Link.GroundZ);
    FVector Away = (Position - Alarm.LastThreatPosition).GetSafeNormal2D();
    if(H.Decision->KeepActive==EcoWorldV3::kKeepPanic&&R::IsNonZero(H.Decision->KeepDir))
        Away=FVector(H.Decision->KeepDir.X,H.Decision->KeepDir.Y,0);
    const bool bAlarm = Alarm.State == EEcoSocialState::Alert || Alarm.State == EEcoSocialState::Panic;
    bool bShelter = Request.Mode != EEcoSocialMovementMode::None && bLeaseValid && Request.ReservationId > 0
        && FMath::IsFinite(Request.ValidUntilWorldTime) && Now < Request.ValidUntilWorldTime
        && !Request.TargetPosition.ContainsNaN() && FMath::IsFinite(Request.ArrivalRadius) && Request.ArrivalRadius > 0;
    const auto Target = Region.CmToUnits(Request.TargetPosition);
    bShelter = bShelter && IsShelterTarget(Region,Request.TargetPosition);
    const FVector ToSlot = Request.TargetPosition - Position;
    // An urgent native escape never turns back through the perceived danger to claim a slot.
    if (bShelter && H.Decision->KeepActive == EcoWorldV3::kKeepPanic && ToSlot.Size2D() > Request.ArrivalRadius
        && FVector::DotProduct(ToSlot.GetSafeNormal2D(),Away) < 0) {
        bShelter = false; Audit.bRejectedUnsafeShelter = true;
    }
    if (bShelter && W.Allowed[R::kHide]) {
        if (S.Behavior != R::kHide) R::Enter(S,R::kHide,H.Decision->DecisionObs,Cfg);
        const bool bArrived = FVector::DistSquared(Position,Request.TargetPosition) <= FMath::Square(Request.ArrivalRadius)
            && (!W.Config.bProtectedRefuges || EcoRefugeV3::Contains(W.Config.Covers,H.Body->Pos));
        S.bArrived = bArrived;
        // HideTarget continues to mean the native cover index; the exact leased slot is separate.
        In.ToTarget = R::Normalize(R::Sub(Target,H.Body->Pos));
        In.PredCount = bAlarm || H.Decision->KeepActive == EcoWorldV3::kKeepPanic ? 1 : In.PredCount;
        if (!bArrived) S.HideTarget = H.Perception->Cover.CoverK >= 0 ? H.Perception->Cover.CoverK : S.HideTarget;
        *H.Control = R::Control(S,In,Cfg);
        const int32 Gait = bArrived ? R::kGaitStop : (In.PredCount>0 ? R::kGaitRun : R::kGaitWalk);
        H.Control->Gait = Gait;
        const double Speed = Cfg.HerbSpeed * Cfg.GaitSpeed[Gait];
        const double Distance = std::sqrt(R::SizeSquared(R::Sub(Target,H.Body->Pos)));
        H.Control->Velocity = R::Scale(In.ToTarget,FMath::Min(Speed,Distance));
        H.Control->DrainMult = Cfg.GaitDrain[Gait];
        H.Control->EatMult = 0;
        H.Control->SeeMult = 1;
        H.Control->bCrouch = H.Control->bStill = bArrived;
        H.Control->CoverMult = R::CoverMult(R::kHide,bArrived,Cfg);
        Audit.Applied = bArrived ? EEcoV3SocialControl::ShelterHold : EEcoV3SocialControl::ShelterTravel;
        Audit.AppliedReservation = Request.ReservationId;
    } else if (Alarm.State == EEcoSocialState::Panic && W.Allowed[R::kFlee] && !Away.IsNearlyZero()) {
        if(Previous!=EEcoV3SocialControl::Flee)
            Audit.SharedStartleLeft=S.Behavior==R::kGraze?Cfg.StartleSteps:S.StartleLeft;
        if (S.Behavior != R::kFlee) R::Enter(S,R::kFlee,H.Decision->DecisionObs,Cfg);
        S.StartleLeft=Audit.SharedStartleLeft;
        Audit.SharedStartleLeft=FMath::Max(0,Audit.SharedStartleLeft-1);
        S.Away = {Away.X,Away.Y};
        In.AwayFromPred = S.Away; In.PredCount = 1;
        // A shared report supplies the last reported position, never a hidden predator's live position.
        *H.Control = R::Control(S,In,Cfg);
        Audit.Applied = EEcoV3SocialControl::Flee;
    } else if (bAlarm && (S.Behavior == R::kGraze || S.Behavior == R::kSleep)) {
        if(S.Behavior==R::kSleep&&W.Allowed[R::kGraze])R::Enter(S,R::kGraze,H.Decision->DecisionObs,Cfg);
        // Alert is a real head-up retreat with reduced intake, not an animation-only interruption.
        const auto Direction = R::Normalize(R::Add(R::Scale({Away.X,Away.Y},Cfg.FleeWeight),R::Scale(In.ToCentroid,Cfg.GrazeCohesion)));
        H.Control->Velocity = R::Scale(Direction,Cfg.HerbSpeed*Cfg.GaitSpeed[R::kGaitWalk]);
        H.Control->Gait = R::IsNonZero(Direction) ? R::kGaitWalk : R::kGaitStop;
        H.Control->DrainMult = Cfg.GaitDrain[R::kGaitWalk];
        H.Control->EatMult = Cfg.GaitEat[R::kGaitWalk]*FMath::Clamp(double(A.Forage),0.,1.);
        H.Control->SeeMult = 1;
        Audit.Applied = EEcoV3SocialControl::Alert;
    } else if (bAlarm) {
        // Preserve native world-reflex direction when adding Social cohesion.
        EcoWorldV3::Detail::FlightControlInput(H,In);
        *H.Control = R::Control(S,In,Cfg);
    } else if (Alarm.State==EEcoSocialState::Recovering || Alarm.State==EEcoSocialState::Regrouping) {
        EcoWorldV3::Detail::FlightControlInput(H,In);
        *H.Control=R::Control(S,In,Cfg);
        if(S.Behavior==R::kGraze)H.Control->EatMult*=FMath::Clamp(double(A.Forage),0.,1.);
        Audit.Applied=EEcoV3SocialControl::Regroup;
    } else return false;
    S.Phase = R::PhaseOf(S,Cfg);
    return true;
}

UEcoPolicyV3SocialSenseProcessor::UEcoPolicyV3SocialSenseProcessor() : Query(*this)
{
    ProcessingPhase = EMassProcessingPhase::PrePhysics;
    ExecutionFlags = int32(EProcessorExecutionFlags::Server|EProcessorExecutionFlags::Standalone);
    ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
    ExecutionOrder.ExecuteAfter.Add(UEcoHerdAggregateProcessor::StaticClass()->GetFName());
    ExecutionOrder.ExecuteAfter.Add(UEcoThreatDetectionProcessor::StaticClass()->GetFName());
    ExecutionOrder.ExecuteBefore.Add(UEcoAlarmPropagationProcessor::StaticClass()->GetFName());
    bRequiresGameThreadExecution = true;
    bAutoRegisterWithProcessingPhases = true;
    QueryBasedPruning = EMassQueryBasedPruning::Never; // Clear the channel after the last observer disappears.
}
void UEcoPolicyV3SocialSenseProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& Manager)
{
    Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoBehaviorStateFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddRequirement<FEcoSensoryStateFragment>(EMassFragmentAccess::ReadWrite);
    Query.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
    Query.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
    Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
    Query.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
}
void UEcoPolicyV3SocialSenseProcessor::Execute(FMassEntityManager&, FMassExecutionContext& Context)
{
    UWorld* World = GetWorld();
    auto* Herds = World ? World->GetSubsystem<UEcoHerdSubsystem>() : nullptr;
    auto* Native = World ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
    if (!Herds || World->GetNetMode()==NM_Client) return;
    const double Now = World->GetTimeSeconds();
    if(Native&&Native->IsActive()&&Now<NextScan)return;
    NextScan=Now+.2; // Match the existing sensory scan budget; do not repeat terrain traces per render frame.
    TArray<FEcoNoiseEvent> Noises;
    if(auto* Noise=World->GetSubsystem<UEcoNoiseSubsystem>())Noise->GatherRecent(Noises);
    TArray<FEcoObservedHerdThreat> Best;
    Best.SetNum(Herds->GetActiveHerds().Num());
    if (Native && Native->IsActive()) Query.ForEachEntityChunk(Context,[&](FMassExecutionContext& Chunk){
        const auto Ids=Chunk.GetFragmentView<FEcoIdentityFragment>();
        const auto Members=Chunk.GetFragmentView<FEcoHerdMemberFragment>();
        const auto Bodies=Chunk.GetFragmentView<FEcoHerbivoreBodyV3Fragment>();
        const auto States=Chunk.GetFragmentView<FEcoBehaviorStateFragment>();
        const auto Links=Chunk.GetFragmentView<FEcoIntegratedV3Fragment>();
        const auto Vitals=Chunk.GetFragmentView<FEcoVitalsFragment>();
        auto Senses=Chunk.GetMutableFragmentView<FEcoSensoryStateFragment>();
        const auto& Config=Chunk.GetSharedFragment<FEcoSocialSpeciesSharedFragment>();
        for(int32 I=0;I<Chunk.GetNumEntities();++I) {
            auto& Sense=Senses[I];Sense.Age(Now,Config.Senses,1);
            const auto* Region=Links[I].bAdopted?Native->GetContext(Links[I].ContextIndex):nullptr;
            if(!Region||Links[I].bDead||Vitals[I].HP<=0) {Sense.Forget();continue;}
            const auto& W=Region->Sim;const auto& B=Bodies[I].Body;
            const FVector Position=Region->UnitsToCm(B.Pos.X,B.Pos.Y,Links[I].GroundZ);
            auto Publish=[&](const FVector& Threat,float Strength,uint64 Key,double Distance) {
                for(int32 K=0;K<Best.Num();++K) {
                    FEcoHerdRuntimeData Herd;
                    if(!Herds->GetHerdData(K,Herd)||Herds->GetHerdSpeciesIndex(K)!=Ids[I].SpeciesRuntimeIndex)continue;
                    if(K!=Members[I].HerdRuntimeIndex&&FVector::DistSquared(Herd.Center,Position)>FMath::Square(Config.AlarmRadius))continue;
                    const float Priority=Strength*FMath::Exp(-Config.AlarmDistanceDecay*float(Distance));
                    auto& Candidate=Best[K];
                    if(Priority<Candidate.Priority||(Priority==Candidate.Priority&&Key>=Candidate.SourceKey))continue;
                    Candidate.HerdRuntimeIndex=K;Candidate.PersistentHerdId=Herd.PersistentHerdId;
                    Candidate.Position=Threat;Candidate.Strength=Strength;Candidate.Priority=Priority;Candidate.SourceKey=Key;
                }
            };
            double BestDistance=1.e30;
            for(int32 M=0;M<int32(W.ThreatIn.size());++M) {
                const auto& T=W.ThreatIn[M];if(!T.bHunting||T.bAsleep)continue;
                const auto Seen=EcoObservationV3::PerceiveThreats(B.Pos,B.Head,EcoObservationV3::SeePredRadius(W.Dark,W.ObsCfg),States[I].Rep.SeeMult,States[I].Rep.SeeMult,&T,1,W.ObsCfg);
                if(!Seen.PredCount)continue;
                const FVector Threat=Region->UnitsToCm(T.X,T.Y,Links[I].GroundZ);
                bool Sight=Seen.bNearestSight;
                if(Sight) {
                    FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3SocialSight),true);
                    Sight=!World->LineTraceSingleByChannel(Hit,Position+FVector(0,0,80),Threat+FVector(0,0,80),ECC_Visibility,Params);
                }
                if(!Sight&&!Seen.bNearestHeard)continue;
                if(Seen.DPredMin<BestDistance) {
                    BestDistance=Seen.DPredMin;
                    Sense.Observe(Sight?EEcoSenseSource::Sight:EEcoSenseSource::Hearing,Threat,Sight?1:Config.Senses.HearingConfidence,
                        Sight?0:Config.Senses.HearingUncertainty,1,uint64(M+1),Now);
                }
                // Direct observer only: never relay SharedThreatPosition or Herd.Alarm noise.
                Publish(Threat,1,uint64(M+1),Seen.DPredMin*EcoRepertoireV3::kUnitCm);
            }
            const int64 Watermark=Sense.LastProcessedNoiseId;
            for(const auto& Noise:Noises) {
                Sense.LastProcessedNoiseId=FMath::Max(Sense.LastProcessedNoiseId,Noise.Id);
                if(Noise.Id<=Watermark||Noise.Tag!=TEXT("Player.Footstep")||Noise.ThreatStrength<=0)continue;
                const float Range=FMath::Min(Config.Senses.HearingRange,Noise.MaxRange)*Noise.Loudness;
                const double Distance=FVector::Distance(Position,Noise.Position);
                if(Distance>=Range||Range<=0)continue;
                const uint64 Key=(uint64(1)<<62)|uint64(Noise.Id);
                if(Sense.Source!=EEcoSenseSource::Sight)
                    Sense.Observe(EEcoSenseSource::Hearing,Noise.Position,Config.Senses.HearingConfidence,Config.Senses.HearingUncertainty,
                        Noise.ThreatStrength,Key,Noise.EmittedAt);
                Publish(Noise.Position,Noise.ThreatStrength,Key,Distance);
            }
        }
    });
    Herds->ApplyObservedHerdThreats(Best,true);
}

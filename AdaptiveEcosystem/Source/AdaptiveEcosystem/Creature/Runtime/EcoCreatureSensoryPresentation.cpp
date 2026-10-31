#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "AI/Social/Senses/EcoPredatorPerception.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"

void AEcoCreatureIntegrationSpawner::UpdateSensoryPresentation()
{
    auto& EM=GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const double Now=GetWorld()->GetTimeSeconds();
    TArray<FEcoNoiseEvent> Noises;
    if(auto* Noise=GetWorld()->GetSubsystem<UEcoNoiseSubsystem>())Noise->GatherRecent(Noises);
    const FEcoSensorySettings Settings;
    for(const auto E:Owned) {
        auto* Cue=EM.GetFragmentDataPtr<FEcoCreatureCueFragment>(E);
        if(!Cue||Now<Cue->NextScan)continue;
        Cue->NextScan=Now+.2;
        const auto PreviousSource=Cue->Memory.Source;
        const auto& Id=EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
        const auto& Vitals=EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
        if(Vitals.HP<=0){Cue->Memory.Forget();continue;}
        const FVector Position=EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
        const auto* Social=EM.GetFragmentDataPtr<FEcoSensoryStateFragment>(E);
        const auto* Prey=EM.GetFragmentDataPtr<FEcoPreySenseFragment>(E);
        if(Social) {
            Cue->Memory=*Social;
            // Shared reports affect only the passive cue here. They never become a new direct Social observation.
            if(Social->Source==EEcoSenseSource::None&&Social->SharedPersistentHerdId>0&&Social->SharedAlarmStrength>=Settings.MinimumConfidence
                &&Social->SharedEvidenceWorldTime>=0&&Now>=Social->SharedEvidenceWorldTime&&Now-Social->SharedEvidenceWorldTime<Settings.SharedInformationMaxAge)
                Cue->Memory.Observe(EEcoSenseSource::Hearing,Social->SharedThreatPosition,FMath::Min(Settings.HearingConfidence,Social->SharedAlarmStrength),
                    Settings.HearingUncertainty,Social->SharedAlarmStrength,uint64(Social->SharedPersistentHerdId),Social->SharedEvidenceWorldTime);
        }
        else if(Prey)Cue->Memory=Prey->Cue;
        else {
            Cue->Memory.Age(Now,Settings,1);
            const auto* Integration=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);
            const auto* Perception=EM.GetFragmentDataPtr<FEcoPerceptionCacheFragment>(E);
            const auto* Region=Integration&&Integration->bAdopted&&Native?Native->GetContext(Integration->ContextIndex):nullptr;
            if(Perception&&Region) {
                const int32 Index=Perception->Perception.Threat.Nearest;
                if(Index>=0&&Index<int32(Region->Sim.ThreatIn.size())) {
                    const auto& Target=Region->Sim.ThreatIn[Index];
                    const FVector P=Region->UnitsToCm(Target.X,Target.Y,Position.Z);
                    FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoPresentationSight),true);
                    if(Perception->Perception.Threat.bNearestSight&&!GetWorld()->LineTraceSingleByChannel(Hit,Position+FVector(0,0,80),P+FVector(0,0,80),ECC_Visibility,Params))
                        Cue->Memory.Observe(EEcoSenseSource::Sight,P,1,0,1,uint64(Index+1),Now);
                    else if(Perception->Perception.Threat.bNearestHeard&&Cue->Memory.Source!=EEcoSenseSource::Sight)
                        Cue->Memory.Observe(EEcoSenseSource::Hearing,P,Settings.HearingConfidence,Settings.HearingUncertainty,1,uint64(Index+1),Now);
                }
            }

            if(Integration&&Integration->LastSeenPreyKey>0&&Now-Integration->LastSeenPreyTime<=.25) {
                const FVector Target=Integration->LastSeenPreyPosition;
                FHitResult Hit;FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoNativePreySight),true);
                if(!GetWorld()->LineTraceSingleByChannel(Hit,Position+FVector(0,0,80),Target+FVector(0,0,80),ECC_Visibility,Params))
                    Cue->Memory.Observe(EEcoSenseSource::Sight,Target,1,0,1,uint64(Integration->LastSeenPreyKey),Integration->LastSeenPreyTime);
            }
            if(Cue->Memory.Source!=EEcoSenseSource::Sight)for(const auto& Noise:Noises) {
                if(Noise.Id<=Cue->Memory.LastProcessedNoiseId||Noise.SourceAgentId==Id.StableAgentId)continue;
                Cue->Memory.LastProcessedNoiseId=Noise.Id;
                const bool Relevant=Id.SpeciesId==TEXT("Wolf")?Noise.SourceSpeciesId==TEXT("Herbivore")||Noise.Instigator.IsValid():Noise.ThreatStrength>0;
                if(!Relevant)continue;
                const float Range=Noise.MaxRange*Noise.Loudness;
                if(FVector::DistSquared(Position,Noise.Position)<=FMath::Square(Range)) {
                    Cue->Memory.Observe(EEcoSenseSource::Hearing,Noise.Position,Settings.HearingConfidence,Settings.HearingUncertainty,FMath::Max(Noise.ThreatStrength,.1f),uint64(Noise.Id),Noise.EmittedAt);
                    const auto* Debug=IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Senses.NoiseLog"));
                    if(Noise.Tag==TEXT("Herd.Alarm")&&Debug&&Debug->GetInt()!=0)
                        UE_LOG(LogTemp,Log,TEXT("[Eco AlarmHeard] Listener=%lld Source=%lld Event=%lld DistanceCm=%.0f"),
                            Id.StableAgentId,Noise.SourceAgentId,Noise.Id,FVector::Distance(Position,Noise.Position));
                }
            }
        }
        // One authority alarm per region per cooldown. Heard alarms never emit another alarm (no gossip loop).
        const auto& Membership=EM.GetFragmentDataChecked<FEcoRegionFragment>(E);
        if(Id.SpeciesId==TEXT("Herbivore")&&Cue->Memory.Source==EEcoSenseSource::Sight&&PreviousSource!=EEcoSenseSource::Sight
            &&Now>=NextPresentationAlarm.FindRef(Membership.CurrentRegionId)) {
            if(auto* Noise=GetWorld()->GetSubsystem<UEcoNoiseSubsystem>())
                if(Noise->ReportCreatureAlarm(Position,Id.StableAgentId,Id.SpeciesId)>0)
                    NextPresentationAlarm.Add(Membership.CurrentRegionId,Now+3);
        }
        if(Cue->Memory.Source!=EEcoSenseSource::None)
            Cue->FocusYaw=int16(FMath::Clamp(FMath::RoundToInt(FRotator::NormalizeAxis((Cue->Memory.LastKnownPosition-Position).Rotation().Yaw)*182.0389f),-32768,32767));
    }
}

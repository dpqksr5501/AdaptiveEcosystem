#include "HAL/IConsoleManager.h"
#include "Engine/World.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "Mass/EntityFragments.h"
#include "Mass/EcoMassFragments.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Network/EcoGameState.h"
#include "Misc/EngineVersion.h"
#include "StateTree.h"
#include "MassStateTreeFragments.h"
#include "Mass/EcoMassTags.h"

#if !UE_BUILD_SHIPPING
namespace
{
    void Snapshot(UWorld* World,bool Export)
    {
        if(!World||!IsInGameThread())return;
        auto* Spawner=World->GetSubsystem<UMassSpawnerSubsystem>();if(!Spawner)return;
        if(World->GetNetMode()==NM_Client)
        {
            auto& EM=Spawner->GetEntityManagerChecked();FMassEntityQuery ClientQuery(EM.AsShared());
            ClientQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::All);
            ClientQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
            ClientQuery.AddRequirement<FEcoSpeciesAIInputFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
            ClientQuery.AddRequirement<FMassStateTreeInstanceFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
            int32 Proxies=0,UnexpectedLogic=0;auto Ctx=EM.CreateExecutionContext(0);
            ClientQuery.ForEachEntityChunk(Ctx,[&](FMassExecutionContext& C)
            {Proxies+=C.GetNumEntities();if(!C.GetFragmentView<FEcoSpeciesAIInputFragment>().IsEmpty()||!C.GetFragmentView<FMassStateTreeInstanceFragment>().IsEmpty())UnexpectedLogic+=C.GetNumEntities();});
            UE_LOG(LogTemp,Display,TEXT("[SpeciesAI Client] Proxies=%d UnexpectedLogic=%d Expected=0; use eco.M4.Dump for transport counts."),Proxies,UnexpectedLogic);return;
        }
        auto& EM=Spawner->GetEntityManagerChecked();FMassEntityQuery Query(EM.AsShared());
        Query.AddTagRequirement<FEcoStateTreeBehaviorTag>(EMassFragmentPresence::All);
        Query.AddRequirement<FEcoSpeciesAIInputFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoSpeciesAIDecisionFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoSpeciesAIExecutionFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoSpeciesAIMoveFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoSpeciesAIAttackFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoSpeciesAIFeedingFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoObservationFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
        Query.AddRequirement<FEcoPolicyOutputFragment>(EMassFragmentAccess::ReadOnly);
        Query.AddRequirement<FEcoSocialBehaviorFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
        Query.AddConstSharedRequirement<FEcoSpeciesAISharedFragment>();
        int32 Count=0,Deer=0,Wolf=0,V1=0,Pending=0,Following=0,Failed=0;int32 Tiers[3]={};int32 Activities[16]={};
        uint64 Snapshots=0,Hits=0,Rejected=0,Blocked=0;double Clamped=0,Dropped=0;
        FString CSV=TEXT("Schema,WorldTime,StableAgentId,Species,Region,Profile,PolicyOnly,Energy,HP,Decision,Activity,Tier,Snapshot,NavStatus,MoveRevision,Failures,BlockedFrames,ClampedSeconds,TargetDomain,TargetId,SlotReservation,AttackRequested,AttackResolved,AttackSuccess,AttackRejected,ExposureDroppedSeconds,ObservationValid,FoodNorm,PredCountNorm,PredDistNorm,KinNorm,EnergyNorm,PredationNorm,CoverNorm,RawForage,RawCohesion,RawFlee,RawCover,EffectiveForage,EffectiveCohesion,EffectiveFlee,EffectiveCover\n");
        TSet<FString> ProfileManifest;
        auto Context=EM.CreateExecutionContext(0);
        Query.ForEachEntityChunk(Context,[&](FMassExecutionContext& C)
        {
            const auto* P=C.GetConstSharedFragment<FEcoSpeciesAISharedFragment>().Profile.Get();if(!P)return;
            const auto Input=C.GetFragmentView<FEcoSpeciesAIInputFragment>();const auto Decision=C.GetFragmentView<FEcoSpeciesAIDecisionFragment>();
            const auto Exec=C.GetFragmentView<FEcoSpeciesAIExecutionFragment>();const auto Id=C.GetFragmentView<FEcoIdentityFragment>();
            const auto V=C.GetFragmentView<FEcoVitalsFragment>();const auto Region=C.GetFragmentView<FEcoRegionFragment>();
            const auto Move=C.GetFragmentView<FEcoSpeciesAIMoveFragment>();const auto Attack=C.GetFragmentView<FEcoSpeciesAIAttackFragment>();
            const auto Feed=C.GetFragmentView<FEcoSpeciesAIFeedingFragment>();
            const auto Observations=C.GetFragmentView<FEcoObservationFragment>();const auto Raw=C.GetFragmentView<FEcoPolicyOutputFragment>();
            const auto Social=C.GetFragmentView<FEcoSocialBehaviorFragment>();
            ProfileManifest.Add(FString::Printf(TEXT("%s Version=%d Predator=%d PolicyOnly=%d Tree=%s Decision=%.6f Dwell=%.3f Walk=%.3f Run=%.3f Repath=%.3f Lease=%.3f Food/s=%.3f AttackCooldown=%.3f\n"),
                *P->GetPathName(),P->Version,P->bPredator,P->bPolicyOnly,*GetPathNameSafe(P->StateTree),P->DecisionInterval,P->MinimumDwell,P->WalkSpeed,P->RunSpeed,P->RepathInterval,P->SlotLease,P->FoodUnitsPerSecond,P->AttackCooldown));
            for(int32 N=0;N<C.GetNumEntities();++N)
            {
                ++Count;if(P->bPredator)++Wolf;else ++Deer;V1+=P->bPolicyOnly;
                ++Tiers[FMath::Min(2,int32(Input[N].Tier))];++Activities[FMath::Min(15,int32(Exec[N].Activity))];
                Pending+=Move[N].Status==EEcoAINavigationStatus::Pending;Following+=Move[N].Status==EEcoAINavigationStatus::Following;
                Failed+=Move[N].Status==EEcoAINavigationStatus::Failed;Snapshots+=Input[N].Snapshot;
                Hits+=Attack[N].Successes;Rejected+=Attack[N].Rejections;Blocked+=Move[N].BlockedFrames;
                Clamped+=Move[N].ClampedSeconds;Dropped+=Feed[N].DroppedSeconds;
                if(Export)
                {
                    CSV+=FString::Printf(TEXT("2,%.3f,%lld,%s,%s,%s,%d,%.3f,%.3f,%d,%d,%d,%llu,%d,%llu,%u,%u,%.6f,%d,%lld,%lld,%llu,%llu,%llu,%llu,%.6f"),
                    World->GetTimeSeconds(),Id[N].StableAgentId,*Id[N].SpeciesId.ToString(),*Region[N].CurrentRegionId.ToString(),*P->GetPathName(),P->bPolicyOnly,
                    V[N].Energy,V[N].HP,int32(Decision[N].Activity),int32(Exec[N].Activity),Input[N].Tier,Input[N].Snapshot,int32(Move[N].Status),Move[N].Revision,
                    Move[N].Failures,Move[N].BlockedFrames,Move[N].ClampedSeconds,int32(Input[N].Target.Domain),Input[N].Target.Id,Exec[N].SlotReservation,
                    Attack[N].Requested,Attack[N].Resolved,Attack[N].Successes,Attack[N].Rejections,Feed[N].DroppedSeconds);
                    const bool ValidObservation=P->bPolicyOnly&&!Observations.IsEmpty();
                    const FEcoPolicyObservationV1 O=ValidObservation?Observations[N].Observation:FEcoPolicyObservationV1();
                    const auto& A=Raw[N].Action;const auto& Effective=Social.IsEmpty()?A:Social[N].ModulatedAction;
                    CSV+=FString::Printf(TEXT(",%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f\n"),
                        ValidObservation,O.FoodDensity,O.PredatorCount,O.PredatorDistance,O.ConspecificCount,O.Energy,O.RecentPredation,O.CoverDistance,
                        A.Forage,A.Cohesion,A.FleeDist,A.Cover,Effective.Forage,Effective.Cohesion,Effective.FleeDist,Effective.Cover);
                }
            }
        });
        const auto* Slots=World->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>();
        UE_LOG(LogTemp,Display,TEXT("[SpeciesAI] Entities=%d Deer=%d Wolf=%d V1=%d Tier(H/M/L)=%d/%d/%d Pending=%d Following=%d Failed=%d Snapshots=%llu Hits=%llu Rejected=%llu Blocked=%llu ClampedSeconds=%.3f ExposureDropped=%.3f Slots=%d Claims=%llu Releases=%llu FixtureCaptures=%llu"),
            Count,Deer,Wolf,V1,Tiers[0],Tiers[1],Tiers[2],Pending,Following,Failed,Snapshots,Hits,Rejected,Blocked,Clamped,Dropped,
            Slots?Slots->NumReservations():0,Slots?Slots->Claims:0,Slots?Slots->Releases:0,Slots?Slots->FixtureCaptures:0);
        for(int32 N=0;N<16;++N)if(Activities[N])UE_LOG(LogTemp,Display,TEXT("[SpeciesAI Activity] %s=%d"),*StaticEnum<EEcoSpeciesActivity>()->GetNameStringByValue(N),Activities[N]);
        if(Export)
        {
            const FString Directory=FPaths::ProjectSavedDir()/TEXT("SpeciesAI");IFileManager::Get().MakeDirectory(*Directory,true);
            const FString File=Directory/FString::Printf(TEXT("Snapshot_%s_%llu.csv"),*FDateTime::UtcNow().ToString(TEXT("%Y%m%d_%H%M%S")),GFrameCounter);
            const bool OK=FFileHelper::SaveStringToFile(CSV,*File,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
            const auto* State=World->GetGameState<AEcoGameState>();
            FString Manifest=FString::Printf(TEXT("SpeciesAI snapshot schema=2\nEngine=%s\nWorld=%s Epoch=%d WorldTime=%.6f Frame=%llu\nFixtures=%d\nSampling=manual snapshot; not a benchmark or automated test\nWanderSeed=StableAgentId + floor(WorldTime/5)\n"),
                *FEngineVersion::Current().ToString(),*World->GetName(),State?State->GetWorldEpoch():0,World->GetTimeSeconds(),GFrameCounter,Slots&&Slots->bAllowFixtures);
            for(const auto& Profile:ProfileManifest)Manifest+=Profile;
            FFileHelper::SaveStringToFile(Manifest,*(File+TEXT(".manifest.txt")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
            UE_LOG(LogTemp,Display,TEXT("[SpeciesAI CSV] Saved=%d %s"),OK,*File);
        }
    }
    FAutoConsoleCommandWithWorld Status(TEXT("eco.SpeciesAI.Status"),TEXT("Read authoritative species AI, path, slot and fixture counters."),
        FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W){Snapshot(W,false);}));
    FAutoConsoleCommandWithWorld Capture(TEXT("eco.SpeciesAI.Capture"),TEXT("Export an on-demand diagnostic snapshot to Saved/SpeciesAI. No automatic test or gameplay mutation."),
        FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* W){Snapshot(W,true);}));
}
#endif

#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoEcosystemArchive.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoHerdMigration.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassPresentationFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "World/EcoWorldClockSubsystem.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "Network/EcoGameState.h"
#include "Serialization/MemoryReader.h"
#include "Serialization/MemoryWriter.h"
#include "Serialization/ObjectAndNameAsStringProxyArchive.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "Modules/ModuleManager.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformProcess.h"
#include "HAL/IConsoleManager.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "UObject/StrongObjectPtr.h"

namespace EcoCheckpoint
{
    template<class T,class F> void Array(FArchive& A,TArray<T>& Values,int32 Limit,F Item)
    {
        int32 N=Values.Num();A<<N;if(A.IsError()||N<0||N>Limit){A.SetError();return;}
        if(A.IsLoading())Values.SetNum(N);
        for(auto& V:Values){if(A.IsError())break;Item(V);}
    }
    template<class K,class V,class F> void Map(FArchive& A,TMap<K,V>& Values,int32 Limit,F Item)
    {
        int32 N=Values.Num();A<<N;if(A.IsError()||N<0||N>Limit){A.SetError();return;}
        if(A.IsLoading()){
            Values.Reset();for(int32 I=0;I<N&&!A.IsError();++I){K Key;V Value{};A<<Key;Item(Value);
                if(Values.Contains(Key)){A.SetError();break;}Values.Add(Key,MoveTemp(Value));}
        }else for(auto& Pair:Values){K Key=Pair.Key;A<<Key;Item(Pair.Value);}
    }
    struct FAgent
    {
        int64 Id=0,Herd=0;FName Species,Region;FTransform Transform;
        FEcoVitalsFragment Vitals;FEcoVitalsRuntimeFragment Runtime;FEcoLifetimeFragment Lifetime;FEcoDeathFragment Death;
        FEcoCreatureLifecycleFragment Lifecycle;FEcoIntegratedV3Fragment Link;
        FEcoTravelFragment Travel;FEcoHerdTravelFragment Journey;
        EcoWorldV3::FHerbBody Body;EcoWorldV3::FHerbPerception Perception;EcoWorldV3::FHerbDecision Decision;
        EcoRepertoireV3::FRepState Rep;EcoRepertoireV3::FControlOutput Control;EcoWorldV3::FThreatAgent Wolf;
    };
    struct FRegion {
        FName Id;FVector Origin;double StartFood=0;int64 Sequence=0;EcoWorldV3::FWorldState Sim;EcoTracesV3::FField Traces;
        EcoLifeV3::FRegionalDanger HumanDanger;FRegionEnvironmentState Environment;TArray<double> CoverGround;
        int32 AdoptedDeer=0,AdoptedWolves=0;
        // Rebuilt from this world's physical shelters. Never serialized runtime handles.
        TArray<int32> ReboundShelters;TArray<int64> ReboundRegistrations;
    };
    struct FHerd { int64 Id=0;FName Species;FVector Center; };
    inline void Travel(FArchive& A,FEcoTravelFragment& T)
    {
        A<<T.TargetRegionId<<T.TargetPosition;Pod(A,T.State);Pod(A,T.MoveSpeed);Pod(A,T.Reason);
        Pod(A,T.DepartureTime);Pod(A,T.LastArrivalTime);Pod(A,T.NextDecisionTime);Pod(A,T.FailedTargetUntil);
    }
    inline void Journey(FArchive& A,FEcoHerdTravelFragment& J)
    {
        A<<J.PlanId<<J.PersistentHerdId<<J.Goal<<J.Reason;Pod(A,J.bActive);Pod(A,J.bPause);Pod(A,J.bStranded);
        Pod(A,J.SpeedScale);Pod(A,J.Waypoint);Pod(A,J.LastProgressTime);Pod(A,J.BestDistance);
    }
    inline void Agent(FArchive& A,FAgent& V)
    {
        A<<V.Id<<V.Herd<<V.Species<<V.Region<<V.Transform;
        Properties(A,V.Vitals);Pod(A,V.Runtime);Pod(A,V.Lifetime);Pod(A,V.Death);Pod(A,V.Lifecycle);
        Pod(A,V.Link.Individual);Pod(A,V.Link.bAdopted);Pod(A,V.Link.bDead);Pod(A,V.Link.DeathCause);
        Pod(A,V.Link.GroundZ);Pod(A,V.Link.PrevGroundZ);Pod(A,V.Link.BlockedMoves);Pod(A,V.Link.ReproducedStep);
        Travel(A,V.Travel);Journey(A,V.Journey);
        Pod(A,V.Body);Pod(A,V.Perception);Pod(A,V.Decision);Pod(A,V.Rep);Pod(A,V.Control);Pod(A,V.Wolf);
    }
    inline void Plan(FArchive& A,FEcoHerdJourney& P)
    {
        A<<P.Id<<P.HerdId<<P.Origin<<P.Destination<<P.Reason;Pod(A,P.State);
        Array(A,P.Members,512,[&](int64& Id){A<<Id;});Array(A,P.Points,256,[&](FVector& V){A<<V;});
        Pod(A,P.Started);Pod(A,P.Changed);Pod(A,P.CooldownUntil);Pod(A,P.CorridorWidth);
        Pod(A,P.Arrived);Pod(A,P.Dead);Pod(A,P.Failed);Pod(A,P.bReturning);
    }
    inline FString RuntimeHash()
    {
        static const FString Hash=[](){
#if IS_MONOLITHIC
            const FString Image=FPlatformProcess::ExecutablePath();
#else
            const FString Image=FModuleManager::Get().GetModuleFilename(TEXT("AdaptiveEcosystem"));
#endif
            const auto Digest=FMD5Hash::HashFile(*Image);return Digest.IsValid()?LexToString(Digest):FString();
        }();return Hash;
    }
    inline FString Path(const FString& Slot)
    {
        if(Slot.IsEmpty()||Slot.Len()>48)return {};
        for(TCHAR C:Slot)if(!FChar::IsAlnum(C)&&C!='_'&&C!='-')return {};
        return FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Ecosystem"),Slot+TEXT(".eco"));
    }
}

/** Narrow friend codec at the existing completed GT boundary, not another runtime owner. */
struct FEcoEcosystemCheckpoint
{
    static void Ledger(FArchive& A,UEcologySimulationSubsystem& E)
    {
        using namespace EcoCheckpoint;
        Map(A,E.RegionalStates,64,[&](auto& V){Properties(A,V);Properties(A,V.CompletedEnvironment);Pod(A,V.EffectiveRegenerationMultiplier);Pod(A,V.ProjectedFoodConsumers);});
        Array(A,E.RegionIds,64,[&](FName& V){A<<V;});Array(A,E.SpeciesIds,64,[&](FName& V){A<<V;});
        A<<E.NextStableAgentId<<E.NextSpawnRequestId;
        Map(A,E.SpawnSettings,64,[&](auto& V){Properties(A,V);});Map(A,E.SpawnCursors,64,[&](auto& V){Pod(A,V);});
        A<<E.InitialRequests;Pod(A,E.GlobalPopulationLimit);Properties(A,E.PressureSettings);Pod(A,E.PerAgentConsumptionRate);
        A<<E.LastDeathReceiptStep<<E.DeathReceipts<<E.LastMigrationReceiptStep<<E.MigrationReceipts;
        Properties(A,E.DayEvent);Properties(A,E.NightEvent);Pod(A,E.ResourceEpoch);A<<E.ResourceStepId;Pod(A,E.ResourceTime);
        A<<E.LastDayEventCycle<<E.LastNightEventCycle;
        Map(A,E.PendingManualStarvation,64,[&](double& V){A<<V;});Map(A,E.PendingManualFoodSupply,64,[&](auto& V){Pod(A,V);});
        Array(A,E.CompletedResources,64,[&](auto& V){
            A<<V.WorldEpoch<<V.StepId<<V.Time<<V.RegionId<<V.RegionIndex<<V.Food<<V.Capacity<<V.bDepleted;
            A<<V.EventLoss<<V.SuppliedFood<<V.Consumed<<V.RoundingAdjustment;
        });Map(A,E.LastAcceptedFeedTime,512,[&](double& V){A<<V;});
        Map(A,E.SpatialFood,64,[&](auto& V){Pod(A,V);});
    }
    static bool Run(AEcoCreatureIntegrationSpawner& S,const FString& Slot,bool Loading)
    {
        using namespace EcoCheckpoint;
        auto Reject=[&](const TCHAR* Reason){UE_LOG(LogTemp,Warning,TEXT("[EcoCheckpoint] %s rejected: %s"),Loading?TEXT("Load"):TEXT("Save"),Reason);return false;};
        const FString File=Path(Slot);
        if(File.IsEmpty()||!IsInGameThread()||S.GetNetMode()==NM_Client||!S.bReady||!S.bEnableEcosystemLife||S.bEnableWaves)return Reject(TEXT("authority, ready life-v1 world and valid local slot required; waves unsupported"));
        auto* W=S.GetWorld();auto* M=W->GetSubsystem<UMassSpawnerSubsystem>();auto* E=W->GetSubsystem<UEcologySimulationSubsystem>();
        auto* N=W->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();auto* Clock=W->GetSubsystem<UEcoWorldClockSubsystem>();
        auto* Herds=W->GetSubsystem<UEcoHerdSubsystem>();auto* Journeys=W->GetSubsystem<UEcoHerdMigrationSubsystem>();
        if(!M||!E||!N||!N->IsActive()||!Clock||!Herds||!Journeys||M->GetEntityManagerChecked().IsProcessing()
            ||E->bResourceStepOpen||!E->PendingSpawns.IsEmpty()||!S.BuildAgentLookup())return Reject(TEXT("not a completed authority boundary"));
        auto& EM=M->GetEntityManagerChecked();const int32 NewEpoch=Clock->Current.WorldEpoch;
        TStrongObjectPtr<UEcologySimulationSubsystem> Staged(NewObject<UEcologySimulationSubsystem>(W));
        TArray<FAgent> Agents;TArray<FRegion> Regions;TArray<FHerd> SavedHerds;
        TMap<int64,FEcoHerdJourney> Plans;TMap<int64,double> Shortage,Attempts;
        TMap<FName,FEcoKnownHabitat> HabitatReports;
        TMap<FName,double> HerbRecovery,WolfRecovery;
        TArray<AEcoCreatureIntegrationSpawner::FPendingBirth> Births;
        TMap<FName,TMap<FName,AEcoCreatureIntegrationSpawner::FSpeciesTotals>> Totals;
        int64 NextPlan=1,NextHerd=1,Step=0,Successful=0,Deaths=0,GlobalT=0;
        uint64 StrikeSerial=0;
        double ResourceTime=0,MigrationTime=0,BirthScan=0;
        FEcoServerTimeSnapshot Time,Completed;EcoPolicy::FStepClock NativeClock;int32 Phase=0;
        FString MapName=W->GetOutermost()->GetName();MapName=UWorld::RemovePIEPrefix(MapName);
        FString SavedMap=MapName,Build=RuntimeHash(),Brain=N->GetActiveBrain().Id;
        if(Build.IsEmpty())return Reject(TEXT("runtime image hash unavailable"));
        if(!Loading){
            for(int32 I=0;I<N->NumContexts();++I){const auto& C=*N->GetContext(I);
                if(!C.bSpatialFoodRegistered||C.Sim.Rng.External||!ValidGrid(C.Sim.Food))return Reject(TEXT("unsupported native context"));
                auto& R=Regions.AddDefaulted_GetRef();R.Id=C.RegionId;R.Origin=C.OriginCm;R.StartFood=C.StartFood;R.Sequence=C.ResourceReceiptSequence;R.Sim=C.Sim;R.Traces=C.MovementTraces;
                R.HumanDanger=C.KnownHumanDanger;
                R.CoverGround=C.CoverGroundZ;
                R.AdoptedDeer=C.AdoptedDeer;R.AdoptedWolves=C.AdoptedWolves;
                const auto* Actor=W->GetSubsystem<UEcologyWorldSubsystem>()->GetRegion(C.RegionId);
                if(!Actor)return Reject(TEXT("missing environment provider"));R.Environment=Actor->GetEnvironmentState();
            }
            for(const auto Entity:S.Owned){
                const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
                if(!Link||!Link->bAdopted||!Link->Individual.bInitialized)return Reject(TEXT("all owned agents must be adopted life-v1"));
                if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP<=0&&!EM.GetFragmentDataChecked<FEcoDeathFragment>(Entity).bCommitted)
                    return Reject(TEXT("pending native death outcome; retry after the resource boundary"));
                const auto& Id=EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);auto& A=Agents.AddDefaulted_GetRef();
                A.Id=Id.StableAgentId;A.Species=Id.SpeciesId;A.Region=EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity).CurrentRegionId;
                A.Transform=EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform();A.Vitals=EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
                A.Runtime=EM.GetFragmentDataChecked<FEcoVitalsRuntimeFragment>(Entity);A.Lifetime=EM.GetFragmentDataChecked<FEcoLifetimeFragment>(Entity);
                A.Death=EM.GetFragmentDataChecked<FEcoDeathFragment>(Entity);A.Lifecycle=EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(Entity);A.Link=*Link;
                A.Travel=EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity);
                if(const auto* Member=EM.GetFragmentDataPtr<FEcoHerdMemberFragment>(Entity)){FEcoHerdRuntimeData Data;if(Herds->GetHerdData(Member->HerdRuntimeIndex,Data))A.Herd=Data.PersistentHerdId;}
                if(const auto* J=EM.GetFragmentDataPtr<FEcoHerdTravelFragment>(Entity))A.Journey=*J;
                if(const auto* B=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(Entity)){
                    A.Body=B->Body;A.Perception=EM.GetFragmentDataChecked<FEcoPerceptionCacheFragment>(Entity).Perception;
                    const auto& Behavior=EM.GetFragmentDataChecked<FEcoBehaviorStateFragment>(Entity);A.Rep=Behavior.Rep;A.Decision=Behavior.Decision;
                    A.Control=EM.GetFragmentDataChecked<FEcoControlOutFragment>(Entity).Control;
                }else A.Wolf=EM.GetFragmentDataChecked<FEcoThreatStateFragment>(Entity).Agent;
            }
            Agents.Sort([](const FAgent& A,const FAgent& B){return A.Id<B.Id;});
            for(const auto& H:Herds->ActiveHerds)if(H.PersistentHerdId>0&&Herds->HerdSpeciesIndices.IsValidIndex(H.RuntimeIndex)
                &&E->SpeciesIds.IsValidIndex(Herds->HerdSpeciesIndices[H.RuntimeIndex]))SavedHerds.Add({H.PersistentHerdId,E->SpeciesIds[Herds->HerdSpeciesIndices[H.RuntimeIndex]],H.Center});
            Plans=Journeys->Plans;Shortage=Journeys->ShortageSince;Attempts=Journeys->NextPlanAttempt;NextPlan=Journeys->NextPlan;NextHerd=Herds->NextPersistentHerdId;
            HabitatReports=Journeys->KnownHabitats;
            Births=S.PendingBirths;BirthScan=S.NextBirthScan;Totals=S.SpeciesTotals;
            HerbRecovery=S.LastHerbRecovery;WolfRecovery=S.LastWolfRecovery;
            Step=S.Step;Successful=S.SuccessfulBirths;Deaths=S.CommittedDeaths;ResourceTime=S.LastResourceTime;MigrationTime=S.NextMigrationTime;
            StrikeSerial=S.StrikeSequence;
            Time=Clock->Current;Completed=S.CompletedTime;GlobalT=N->GlobalT;NativeClock=N->Clock;Phase=N->ClockPhase;
        }
        auto Serialize=[&](FArchive& A){
            A<<SavedMap<<Build<<Brain;
            if(Loading&&(SavedMap!=MapName||Build!=RuntimeHash()||Brain!=N->GetActiveBrain().Id)){A.SetError();return;}
            Properties(A,Time);Properties(A,Completed);A<<Step<<Successful<<Deaths<<GlobalT;
            A<<StrikeSerial;
            A<<ResourceTime<<MigrationTime<<BirthScan;Pod(A,NativeClock);A<<Phase;
            Array(A,Regions,64,[&](FRegion& R){A<<R.Id<<R.Origin<<R.StartFood<<R.Sequence;World(A,R.Sim);
                Pod(A,R.Traces.Events);Pod(A,R.Traces.Serial);Pod(A,R.Traces.Cursor);Pod(A,R.HumanDanger);Properties(A,R.Environment);
                Array(A,R.CoverGround,1024,[&](double& Z){A<<Z;});A<<R.AdoptedDeer<<R.AdoptedWolves;});
            Array(A,Agents,1024,[&](FAgent& V){Agent(A,V);});
            Array(A,SavedHerds,512,[&](FHerd& H){A<<H.Id<<H.Species<<H.Center;});
            Map(A,Plans,512,[&](FEcoHerdJourney& P){Plan(A,P);});Map(A,Shortage,512,[&](double& V){A<<V;});Map(A,Attempts,512,[&](double& V){A<<V;});
            Map(A,HabitatReports,64,[&](auto& V){Pod(A,V);});
            Map(A,HerbRecovery,64,[&](double& V){A<<V;});Map(A,WolfRecovery,64,[&](double& V){A<<V;});
            A<<NextPlan<<NextHerd;
            Array(A,Births,128,[&](auto& P){A<<P.ParentA<<P.ParentB<<P.Region<<P.Due<<P.bPredator;});
            Map(A,Totals,64,[&](auto& T){Map(A,T,64,[&](auto& V){Pod(A,V);});});
            Ledger(A,Loading?*Staged:*E);
        };
        TArray<uint8> Bytes;
        if(!Loading){
            FMemoryWriter Memory(Bytes);FObjectAndNameAsStringProxyArchive A(Memory,false);Serialize(A);
            if(A.IsError()||Bytes.Num()>16*1024*1024)return Reject(TEXT("serialization budget"));
            const uint32 Crc=FCrc::MemCrc32(Bytes.GetData(),Bytes.Num());uint32 Magic=0x45434f31,Version=1,Length=Bytes.Num();
            TArray<uint8> Output;FMemoryWriter Header(Output);Header<<Magic<<Version<<Length;uint32 Check=Crc;Header<<Check;Header.Serialize(Bytes.GetData(),Bytes.Num());
            IFileManager::Get().MakeDirectory(*FPaths::GetPath(File),true);
            if(!FFileHelper::SaveArrayToFile(Output,*(File+TEXT(".tmp")))||!IFileManager::Get().Move(*File,*(File+TEXT(".tmp")),true,true))return Reject(TEXT("atomic checkpoint write"));
            UE_LOG(LogTemp,Log,TEXT("[EcoCheckpoint] Saved Slot=%s Agents=%d Step=%lld Native=%lld Bytes=%d"),*Slot,Agents.Num(),Step,GlobalT,Output.Num());return true;
        }
        const int64 FileSize=IFileManager::Get().FileSize(*File);
        if(FileSize<16||FileSize>16*1024*1024||!FFileHelper::LoadFileToArray(Bytes,*File))return Reject(TEXT("missing/oversized checkpoint"));
        FMemoryReader Memory(Bytes);uint32 Magic=0,Version=0,Length=0,Crc=0;Memory<<Magic<<Version<<Length<<Crc;
        if(Magic!=0x45434f31||Version!=1||Length!=uint32(Bytes.Num()-16)||FCrc::MemCrc32(Bytes.GetData()+16,Length)!=Crc)return Reject(TEXT("version/length/checksum mismatch"));
        FObjectAndNameAsStringProxyArchive A(Memory,false);A.ArMaxSerializeSize=16*1024*1024;Serialize(A);
        if(A.IsError()||Memory.Tell()!=Bytes.Num()||SavedMap!=MapName||Build!=RuntimeHash()||Brain!=N->GetActiveBrain().Id
            ||Regions.Num()!=N->NumContexts()||Agents.Num()>2*S.GlobalPopulationLimit||!FMath::IsFinite(Time.ServerTimeSeconds)||Time.ServerTimeSeconds<0
            ||Step<0||GlobalT<0||Successful<Deaths||Staged->bResourceStepOpen)return Reject(TEXT("incompatible build/map/model or invalid state"));
        if(Step<S.Step||GlobalT<N->GlobalT)return Reject(TEXT("live rollback is unsupported; restore this checkpoint during server startup"));
        uint32 ResetRevision=0;for(const auto Entity:S.Owned)
            if(const auto* Reset=EM.GetFragmentDataPtr<FEcoMovementDiscontinuityFragment>(Entity))ResetRevision=FMath::Max(ResetRevision,Reset->Revision);
        if(ResetRevision==MAX_uint32)return Reject(TEXT("presentation reset revision exhausted"));++ResetRevision;
        TSet<FName> RegionNames;for(auto& R:Regions){
            const auto* C=N->FindContext(R.Id);if(!C||RegionNames.Contains(R.Id)||!C->OriginCm.Equals(R.Origin,.01)||C->Sim.Config.WorldSize!=R.Sim.Config.WorldSize
                ||!R.Sim.Config.bEcosystemLife||R.Sim.T!=GlobalT||!ValidGrid(R.Sim.Food)||!Staged->RegionalStates.Contains(R.Id))return Reject(TEXT("region layout mismatch"));
            if(R.AdoptedDeer<0||R.AdoptedWolves<0||R.AdoptedDeer>Successful||R.AdoptedWolves>Successful)return Reject(TEXT("invalid native adoption ordinal"));
            const auto* Food=Staged->SpatialFood.Find(R.Id);
            if(!std::isfinite(R.HumanDanger.Human)||R.HumanDanger.Human<0||R.HumanDanger.Human>1||!std::isfinite(R.HumanDanger.Updated)
                ||R.HumanDanger.Updated<0||R.HumanDanger.Updated>GlobalT*EcoRepertoireV3::kStepSeconds||!std::isfinite(R.HumanDanger.NextExposure)
                ||R.HumanDanger.NextExposure<R.HumanDanger.Updated)return Reject(TEXT("invalid recognized regional evidence"));
            if(!Food||Food->Sequence!=R.Sequence||!FMath::IsNearlyEqual(Food->Amount,R.Sim.Food.Total(),1e-5))return Reject(TEXT("native/ledger conservation mismatch"));
            // Resume only against the same physical refuge/obstacle geometry. No invisible saved walls.
            if(C->Sim.Config.Obstacles.Discs!=R.Sim.Config.Obstacles.Discs)return Reject(TEXT("physical obstacles changed"));
            TArray<int32> CoverMap;
            if(!MapCoverGeometry(R.Sim.Config.Covers,C->Sim.Config.Covers,CoverMap)||R.CoverGround.Num()!=CoverMap.Num())return Reject(TEXT("physical refuge layout changed or not ready"));
            R.ReboundShelters.Init(INDEX_NONE,CoverMap.Num());R.ReboundRegistrations.Init(0,CoverMap.Num());
            for(int32 K=0;K<CoverMap.Num();++K){const int32 Live=CoverMap[K];
                if(!std::isfinite(R.CoverGround[K]))return Reject(TEXT("invalid refuge height"));
                if(Live==INDEX_NONE)continue;
                if(!C->CoverGroundZ.IsValidIndex(Live)||FMath::Abs(C->CoverGroundZ[Live]-R.CoverGround[K])>1
                    ||!C->CoverShelterIndices.IsValidIndex(Live)||!C->CoverRegistrations.IsValidIndex(Live))return Reject(TEXT("physical refuge height/bindings changed"));
                if(R.Sim.Config.bProtectedRefuges){const auto* Shelters=W->GetSubsystem<UEcoShelterSubsystem>();const int32 Index=C->CoverShelterIndices[Live];
                    if(!Shelters||!Shelters->IsValidShelterIndex(Index)||Shelters->GetShelters()[Index].RegistrationId!=C->CoverRegistrations[Live])return Reject(TEXT("physical refuge registration not ready"));
                }
                R.ReboundShelters[K]=C->CoverShelterIndices[Live];R.ReboundRegistrations[K]=C->CoverRegistrations[Live];
            }
            RegionNames.Add(R.Id);
            for(const auto& T:R.Traces.Events)if(T.Id&&(!std::isfinite(T.X)||!std::isfinite(T.Y)||!std::isfinite(T.Z)||!std::isfinite(T.Time)
                ||std::abs(T.X)>100000||std::abs(T.Y)>100000||T.Time<0||T.Time>GlobalT*EcoRepertoireV3::kStepSeconds+1||T.Id>R.Traces.Serial||T.Source<=0))return Reject(TEXT("invalid movement evidence"));
        }
        for(const auto* History:{&HerbRecovery,&WolfRecovery})for(const auto& Pair:*History)
            if(!RegionNames.Contains(Pair.Key)||!std::isfinite(Pair.Value)||Pair.Value<0||Pair.Value>Time.ServerTimeSeconds)return Reject(TEXT("invalid recovery operation history"));
        TSet<int64> Ids;int32 Alive=0;for(const auto& V:Agents){
            const auto* C=N->FindContext(V.Region);const bool Herb=V.Species==TEXT("Herbivore");
            const bool FiniteBody=Herb?std::isfinite(V.Body.Pos.X)&&std::isfinite(V.Body.Pos.Y)&&std::isfinite(V.Body.Energy)&&std::isfinite(V.Body.Reserve):std::isfinite(V.Wolf.State.PosX)&&std::isfinite(V.Wolf.State.PosY);
            if(!C||V.Id<=0||Ids.Contains(V.Id)||(!Herb&&V.Species!=TEXT("Wolf"))||!V.Link.bAdopted||!V.Link.Individual.bInitialized||!V.Link.Individual.Genome.IsValid()
                ||!FiniteBody||V.Transform.ContainsNaN()||!FMath::IsFinite(V.Vitals.HP)||!FMath::IsFinite(V.Link.GroundZ)||!FMath::IsFinite(V.Link.Individual.Born)
                ||V.Id>=Staged->NextStableAgentId)return Reject(TEXT("invalid individual identity/body/genome"));
            const auto& Life=V.Link.Individual;
            if(!std::isfinite(Life.Nutrition)||Life.Nutrition<0||Life.Nutrition>1||!std::isfinite(Life.MealRemaining)||Life.MealRemaining<0||Life.MealRemaining>.6
                ||!std::isfinite(Life.MeatIssued)||!std::isfinite(Life.MeatConsumed)||!std::isfinite(Life.MeatWasted)
                ||!FMath::IsNearlyEqual(Life.MeatIssued,Life.MeatConsumed+Life.MeatWasted+Life.MealRemaining,1e-8))return Reject(TEXT("invalid carcass conservation"));
            Ids.Add(V.Id);Alive+=V.Vitals.HP>0;
        }
        // Retained corpses consume snapshot rows, not living population capacity.
        if(Alive>S.GlobalPopulationLimit||Alive!=Successful-Deaths||NextHerd<=0||NextPlan<=0||Staged->RegionIds!=E->RegionIds||Staged->GlobalPopulationLimit!=S.GlobalPopulationLimit)return Reject(TEXT("population/identity allocator mismatch"));
        for(const auto& Pair:Plans){const auto& P=Pair.Value;
            if(Pair.Key!=P.HerdId||P.Id<=0||P.Id>=NextPlan||P.Points.Num()<2||!RegionNames.Contains(P.Origin)||!RegionNames.Contains(P.Destination))return Reject(TEXT("invalid journey"));
            for(const auto& V:Agents)if(V.Journey.bActive&&V.Journey.PlanId==P.Id&&(V.Journey.Waypoint<0||V.Journey.Waypoint>=P.Points.Num()))return Reject(TEXT("invalid waypoint"));
        }
        // Prepare new entities before destroying anything. Roll back preparation on
        // allocation failure; malformed/incompatible snapshots never touch live state.
        const auto OldOwned=S.Owned;const auto OldTotals=S.SpeciesTotals;const int64 OldBirths=S.SuccessfulBirths,OldAllocator=E->NextStableAgentId;
        TArray<FMassEntityHandle> NewEntities;
        for(const auto& V:Agents){TArray<FVector> Position{V.Transform.GetLocation()};
            if(S.Spawn(V.Region,1,V.Species==TEXT("Wolf"),&Position)!=1){
                if(!NewEntities.IsEmpty())EM.BatchDestroyEntities(NewEntities);S.Owned=OldOwned;S.SpeciesTotals=OldTotals;S.SuccessfulBirths=OldBirths;E->NextStableAgentId=OldAllocator;
                return Reject(TEXT("entity preparation failed; previous world retained"));
            }
            NewEntities.Add(S.Owned.Last());
        }
        for(const auto Entity:OldOwned)if(auto* Shelters=W->GetSubsystem<UEcoShelterSubsystem>())Shelters->ReleaseAgentReservations(EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).StableAgentId);
        if(!OldOwned.IsEmpty())EM.BatchDestroyEntities(OldOwned);S.Owned=NewEntities;
        // Commit the prevalidated ledger atomically in this serialized GT operation.
        TArray<uint8> LedgerBytes;{FMemoryWriter MW(LedgerBytes);FObjectAndNameAsStringProxyArchive Ar(MW,false);Ledger(Ar,*Staged);}
        {FMemoryReader MR(LedgerBytes);FObjectAndNameAsStringProxyArchive Ar(MR,false);Ledger(Ar,*E);}
        E->ResourceEpoch=NewEpoch;E->PendingSpawns.Reset();E->ResourceLedger.Reset();E->bResourceStepOpen=false;E->bFeedingResolved=false;
        Clock->Current=Time;Clock->Current.WorldEpoch=NewEpoch;Clock->bRunning=true;
        N->GlobalT=GlobalT;N->Clock=NativeClock;N->ClockPhase=Phase;
        for(auto& R:Regions){auto* C=N->FindContext(R.Id);C->Sim=MoveTemp(R.Sim);C->ResourceReceiptSequence=R.Sequence;C->StartFood=R.StartFood;C->MovementTraces=MoveTemp(R.Traces);
            C->KnownHumanDanger=R.HumanDanger;
            C->AdoptedDeer=R.AdoptedDeer;C->AdoptedWolves=R.AdoptedWolves;
            C->CoverGroundZ=MoveTemp(R.CoverGround);C->CoverShelterIndices=MoveTemp(R.ReboundShelters);C->CoverRegistrations=MoveTemp(R.ReboundRegistrations);
            W->GetSubsystem<UEcologyWorldSubsystem>()->GetRegion(R.Id)->SetEnvironmentState(R.Environment);
            C->MovementTraces.Rebuild();
            C->LastStepFoodEaten=C->Sim.Stats.FoodEaten;C->LastLogStats=C->Sim.Stats;C->LastLogT=GlobalT;C->RecentEaten.Reset();}
        Herds->ActiveHerds.Reset();Herds->HerdSpeciesIndices.Reset();Herds->FreeSlots.Reset();Herds->NextPersistentHerdId=NextHerd;
        TMap<int64,int32> HerdIndices;
        for(const auto& H:SavedHerds){FEcoHerdRuntimeData Data;Data.PersistentHerdId=H.Id;Data.RuntimeIndex=Herds->ActiveHerds.Num();Data.Center=H.Center;
            HerdIndices.Add(H.Id,Data.RuntimeIndex);Herds->ActiveHerds.Add(Data);Herds->HerdSpeciesIndices.Add(E->SpeciesIds.Find(H.Species));}
        Herds->InjectedAlarms.Init({},SavedHerds.Num());Herds->ObservedAlarms.Init({},SavedHerds.Num());Herds->NativeV3Alarms.Init({},SavedHerds.Num());
        Journeys->Plans=MoveTemp(Plans);Journeys->ShortageSince=MoveTemp(Shortage);Journeys->NextPlanAttempt=MoveTemp(Attempts);Journeys->NextPlan=NextPlan;
        Journeys->KnownHabitats=MoveTemp(HabitatReports);
        for(int32 I=0;I<Agents.Num();++I){const auto& V=Agents[I];const auto Entity=NewEntities[I];
            auto& Identity=EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);Identity.StableAgentId=V.Id;Identity.SpeciesId=V.Species;Identity.SpeciesRuntimeIndex=E->SpeciesIds.Find(V.Species);
            auto& Region=EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);Region.CurrentRegionId=V.Region;Region.CurrentRegionIndex=E->GetRegionRuntimeIndex(V.Region);
            EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform()=V.Transform;
            if(auto* Reset=EM.GetFragmentDataPtr<FEcoMovementDiscontinuityFragment>(Entity))Reset->Revision=ResetRevision;
            EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity)=V.Vitals;auto& Runtime=EM.GetFragmentDataChecked<FEcoVitalsRuntimeFragment>(Entity);Runtime=V.Runtime;Runtime.WorldEpoch=NewEpoch;
            EM.GetFragmentDataChecked<FEcoLifetimeFragment>(Entity)=V.Lifetime;EM.GetFragmentDataChecked<FEcoDeathFragment>(Entity)=V.Death;
            EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(Entity)=V.Lifecycle;
            auto& Link=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Entity);Link=V.Link;Link.ContextIndex=N->FindContext(V.Region)->Index;
            auto& T=EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity);T=V.Travel;T.TargetRegionIndex=E->GetRegionRuntimeIndex(T.TargetRegionId);
            if(auto* J=EM.GetFragmentDataPtr<FEcoHerdTravelFragment>(Entity)){*J=V.Journey;J->MembershipUntil=J->bActive?W->GetTimeSeconds()+10:0;}
            if(auto* Member=EM.GetFragmentDataPtr<FEcoHerdMemberFragment>(Entity))Member->HerdRuntimeIndex=HerdIndices.Contains(V.Herd)?HerdIndices.FindChecked(V.Herd):INDEX_NONE;
            if(auto* B=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(Entity)){
                B->Body=V.Body;EM.GetFragmentDataChecked<FEcoPerceptionCacheFragment>(Entity).Perception=V.Perception;
                auto& Behavior=EM.GetFragmentDataChecked<FEcoBehaviorStateFragment>(Entity);Behavior.Rep=V.Rep;Behavior.Decision=V.Decision;Behavior.SyncSummary(V.Control);
                EM.GetFragmentDataChecked<FEcoControlOutFragment>(Entity).Control=V.Control;
            }else {
                auto& Wolf=EM.GetFragmentDataChecked<FEcoThreatStateFragment>(Entity).Agent;Wolf=V.Wolf;
                // These are one-step prey array indices, never persistent identity.
                Wolf.State.Target=-1;Wolf.Last.Target=-1;Wolf.Last.bHasTarget=false;
            }
            if(V.Vitals.HP<=0)EM.Defer().RemoveTag<FEcoAliveTag>(Entity);
        }
        S.Step=Step;S.SuccessfulBirths=Successful;S.CommittedDeaths=Deaths;S.LastResourceTime=ResourceTime;S.NextMigrationTime=MigrationTime;
        S.PendingBirths=MoveTemp(Births);S.NextBirthScan=BirthScan;S.SpeciesTotals=MoveTemp(Totals);S.CompletedTime=Completed;S.CompletedTime.WorldEpoch=NewEpoch;
        S.LastHerbRecovery=MoveTemp(HerbRecovery);S.LastWolfRecovery=MoveTemp(WolfRecovery);S.PendingRecoveries.Reset();
        S.StrikeSequence=StrikeSerial;S.PlayerStrikes.Reset();
        const bool Valid=S.BuildAgentLookup()&&S.ReconcilePopulation();if(!Valid){S.FailRuntime(TEXT("Checkpoint commit invariant"));return false;}
        S.UpdatePresentationAndNoise(0);S.PublishSummary();
        UE_LOG(LogTemp,Log,TEXT("[EcoCheckpoint] Loaded Slot=%s Agents=%d Step=%lld Native=%lld Epoch=%d TransientShelterLeasesCancelled=1"),*Slot,Agents.Num(),Step,GlobalT,NewEpoch);
        return true;
    }
};

bool AEcoCreatureIntegrationSpawner::SaveEcosystem(const FString& Slot){return FEcoEcosystemCheckpoint::Run(*this,Slot,false);}
bool AEcoCreatureIntegrationSpawner::LoadEcosystem(const FString& Slot){return FEcoEcosystemCheckpoint::Run(*this,Slot,true);}
static FAutoConsoleCommandWithWorldAndArgs SaveEco(TEXT("eco.Ecosystem.Save"),TEXT("Checkpoint the ready authority world: <local-slot>"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* W){if(W&&Args.Num()==1)for(TActorIterator<AEcoCreatureIntegrationSpawner> It(W);It;++It){It->SaveEcosystem(Args[0]);break;}}));
static FAutoConsoleCommandWithWorldAndArgs LoadEco(TEXT("eco.Ecosystem.Load"),TEXT("Validate then restore life-v1 checkpoint: <local-slot>"),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* W){if(W&&Args.Num()==1)for(TActorIterator<AEcoCreatureIntegrationSpawner> It(W);It;++It){It->LoadEcosystem(Args[0]);break;}}));

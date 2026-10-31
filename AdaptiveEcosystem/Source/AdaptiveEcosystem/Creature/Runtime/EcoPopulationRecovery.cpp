#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "World/EcoWorldClockSubsystem.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"

bool AEcoCreatureIntegrationSpawner::QueuePopulationRecovery(FName RegionId,bool bPredator)
{
    if(!IsInGameThread()||GetNetMode()==NM_Client||!bReady||!bEnableEcosystemLife||!bUseV3Policy
        ||!IsSpeciesEnabled(bPredator)||PendingRecoveries.Num()>=32)return false;
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    if(!Native||!Native->IsActive()||!Native->FindContext(RegionId)
        ||PendingRecoveries.ContainsByPredicate([&](const auto& P){return P.Region==RegionId&&P.bPredator==bPredator;}))return false;
    const double Now=GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
    const auto& History=bPredator?LastWolfRecovery:LastHerbRecovery;
    if(const double* Previous=History.Find(RegionId);Previous&&Now-*Previous<300)return false;
    PendingRecoveries.Add({RegionId,Now,bPredator});return true;
}
bool AEcoCreatureIntegrationSpawner::ProcessPopulationRecovery(const FEcoServerTimeSnapshot& Time)
{
    if(PendingRecoveries.IsEmpty())return true;
    auto* Ecology=GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    auto& EM=GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    for(int32 I=PendingRecoveries.Num()-1;I>=0;--I){
        const auto P=PendingRecoveries[I];if(Time.ServerTimeSeconds<P.Issued)continue;PendingRecoveries.RemoveAtSwap(I);
        if(Time.ServerTimeSeconds-P.Issued>15)continue;
        const FName Species=P.bPredator?FName(TEXT("Wolf")):FName(TEXT("Herbivore"));
        bool Empty=true;for(const auto E:Owned)
            if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(E).HP>0&&EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).SpeciesId==Species
                &&EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId==P.Region){Empty=false;break;}
        if(!Empty){UE_LOG(LogTemp,Log,TEXT("[EcoLife][RecoveryRejected] Region=%s Species=%s Reason=NotEmpty"),*P.Region.ToString(),*Species.ToString());continue;}
        FEcoSpawnRequest Request;if(!Ecology->RequestRecoverySpawn(P.Region,Time,Request,P.bPredator))return false;
        const auto* C=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>()->FindContext(P.Region);
        TArray<FVector> Positions;
        for(int32 K=0;K<32&&Positions.Num()<Request.Count;++K){
            const uint64 Seed=uint64(Request.RequestId)*131+uint64(K)*13;
            const double X=5+(C->SizeUnits-10)*EcoLifeV3::Unit(Seed),Y=5+(C->SizeUnits-10)*EcoLifeV3::Unit(Seed+1);
            FVector Ground;if(!EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(),C->UnitsToCm(X,Y,C->OriginCm.Z),Ground))continue;
            bool Clear=true;
            if(P.bPredator)for(const auto& Cover:C->Sim.Config.Covers)
                if(Cover.Radius>0&&FMath::Square(X-Cover.X)+FMath::Square(Y-Cover.Y)<FMath::Square(Cover.Radius+1)){Clear=false;break;}
            if(!Clear)continue;
            for(const auto E:Owned)if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(E).HP>0
                &&FVector::DistSquared2D(Ground,EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation())<40000){Clear=false;break;}
            for(const auto& Other:Positions)if(FVector::DistSquared2D(Ground,Other)<40000){Clear=false;break;}
            if(Clear)Positions.Add(Ground);
        }
        const int32 Before=Owned.Num(),Actual=Positions.IsEmpty()?0:Spawn(P.Region,Positions.Num(),P.bPredator,&Positions);
        if(!ReconcilePopulation()||!Ecology->CompleteSpawnRequest(Request.RequestId,Actual))return false;
        for(int32 K=Before;K<Owned.Num();++K){auto& Life=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Owned[K]).Individual;
            Life.Origin=EcoLifeV3::EOrigin::Recovery;Life.NextBirth=Time.ServerTimeSeconds+180;
        }
        if(Actual)(P.bPredator?LastWolfRecovery:LastHerbRecovery).Add(P.Region,Time.ServerTimeSeconds);
        UE_LOG(LogTemp,Log,TEXT("[EcoLife][Recovery] Request=%lld Region=%s Species=%s Actual=%d Origin=Recovery ParentIds=0 Generation=0"),Request.RequestId,*P.Region.ToString(),*Species.ToString(),Actual);
    }
    return true;
}
static FAutoConsoleCommandWithWorldAndArgs RecoverEco(TEXT("eco.Ecosystem.Recover"),TEXT("Explicit authority operation: <region> <Herbivore|Wolf>. Empty population only, two founders, 300s per-region/species cooldown."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World){
        if(!World||World->GetNetMode()==NM_Client||Args.Num()!=2||(Args[1]!=TEXT("Herbivore")&&Args[1]!=TEXT("Wolf")))return;
        for(TActorIterator<AEcoCreatureIntegrationSpawner> It(World);It;++It){It->QueuePopulationRecovery(FName(*Args[0]),Args[1]==TEXT("Wolf"));break;}
    }));

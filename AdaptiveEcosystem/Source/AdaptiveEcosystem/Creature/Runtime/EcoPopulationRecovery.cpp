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

namespace
{
    constexpr double RecoveryCooldownSeconds = 300.;
    constexpr int32 RecoveryPairSize = 2;
}

bool AEcoCreatureIntegrationSpawner::QueuePopulationRecovery(FName RegionId,bool bPredator)
{
    if (!IsInGameThread() || !bAuthorityWorld || !bReady || !bUseV3Policy || !IsSpeciesEnabled(bPredator)) return false;
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    if (!Native || !Native->IsActive() || !Native->FindContext(RegionId)) return false;
    return QueueRecovery(RegionId, bPredator ? FName(TEXT("Wolf")) : FName(TEXT("Herbivore")),
        bPredator ? &LastWolfRecovery : &LastHerbRecovery);
}

bool AEcoCreatureIntegrationSpawner::QueueFaunaRecovery(FName RegionId, FName SpeciesId)
{
    if (!IsInGameThread() || !FindFauna(SpeciesId)) return false;
    const bool bHasAuthoredSite = Groups.ContainsByPredicate([&](const auto& Group) {
        return Group.RegionId == RegionId && Group.Fauna.ContainsByPredicate([&](const auto& Placement) {
            return Placement.SpeciesId == SpeciesId;
        });
    });
    return bHasAuthoredSite && QueueRecovery(RegionId, SpeciesId, LastFaunaRecovery.Find(SpeciesId));
}

bool AEcoCreatureIntegrationSpawner::QueueRecovery(FName RegionId, FName SpeciesId, const TMap<FName, double>* History)
{
    if (!bAuthorityWorld || !bReady || !bEnableEcosystemLife || PendingRecoveries.Num() >= 32
        || PendingRecoveries.ContainsByPredicate([&](const auto& Pending) {
            return Pending.Region == RegionId && Pending.Species == SpeciesId;
        })) return false;
    const double Now = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
    const double* Previous = History ? History->Find(RegionId) : nullptr;
    if (Previous && Now - *Previous < RecoveryCooldownSeconds) return false;
    PendingRecoveries.Add({RegionId, SpeciesId, Now});
    return true;
}

bool AEcoCreatureIntegrationSpawner::ProcessFaunaRecovery(FName RegionId, const FEcoFaunaSpecies& Species,
    const FEcoServerTimeSnapshot& Time)
{
    const auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto IsAlive = [&](FMassEntityHandle Entity) {
        return EM.IsEntityValid(Entity) && EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP > 0.f;
    };
    const auto Reject = [&](const TCHAR* Reason) {
        UE_LOG(LogTemp, Log, TEXT("[EcoLife][RecoveryRejected] Region=%s Species=%s Reason=%s"),
            *RegionId.ToString(), *Species.SpeciesId.ToString(), Reason);
        return true;
    };
    for (const auto Entity : Owned)
    {
        if (!IsAlive(Entity) || EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).SpeciesId != Species.SpeciesId)
            continue;
        if (EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity).CurrentRegionId == RegionId)
            return Reject(TEXT("NotEmpty"));
        const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity);
        if (Travel.State == EEcoResidenceState::Traveling && Travel.TargetRegionId == RegionId)
            return Reject(TEXT("IncomingResident"));
    }

    const auto IsNear = [&](const FVector& A, const FVector& B) {
        return FVector::DistSquared(A, B) < FMath::Square(2. * Species.BodyRadius);
    };
    TArray<FVector> Pair;
    for (const auto& Group : Groups)
    {
        if (Group.RegionId != RegionId) continue;
        for (const auto& Placement : Group.Fauna)
        {
            TArray<FVector> Sites;
            if (Placement.SpeciesId != Species.SpeciesId || !BuildFaunaPositions(RegionId, Placement, Sites))
                continue;
            for (const FVector& Site : Sites)
            {
                if (Pair.ContainsByPredicate([&](const FVector& Other) { return IsNear(Site, Other); })
                    || Owned.ContainsByPredicate([&](FMassEntityHandle Entity) {
                        return IsAlive(Entity) && IsNear(Site,
                            EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform().GetLocation());
                    })) continue;
                Pair.Add(Site);
                if (Pair.Num() == RecoveryPairSize) break;
            }
            if (Pair.Num() == RecoveryPairSize) break;
        }
        if (Pair.Num() == RecoveryPairSize) break;
    }
    if (Pair.Num() != RecoveryPairSize) return Reject(TEXT("NoHabitatPair"));

    auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    FRegionEcologyState Region;
    if (!ReconcilePopulation() || !Ecology->GetRegionState(RegionId, Region)) return false;
    const double PlantReserve = Species.UsesPlantFood() ? FaunaBirthPlantReserve(Region, RecoveryPairSize) : 0.;
    FEcoSpawnRequest Request;
    if (!Ecology->RequestFaunaRecovery(RegionId, Time, Request, PlantReserve)) return false;
    const int32 Before = Owned.Num();
    const int32 Actual = Request.Count == RecoveryPairSize
        ? SpawnFauna(RegionId, Species, Pair, Time, EcoLifeV3::EOrigin::Recovery) : 0;
    const bool bClosed = Ecology->CompleteSpawnRequest(Request.RequestId, Actual);
    if (!bClosed || !ReconcilePopulation()) return false;
    if (!Actual)
    {
        const FString Reason = Request.DiagnosticReason.IsNone()
            ? (Request.Count == 0 ? TEXT("SpawnFailed") : TEXT("PairCapacity")) : Request.DiagnosticReason.ToString();
        return Reject(*Reason);
    }
    LastFaunaRecovery.FindOrAdd(Species.SpeciesId).Add(RegionId, Time.ServerTimeSeconds);
    for (int32 Index = Before; Index < Owned.Num(); ++Index)
        RecordTraitOutcome(EM, Owned[Index], Time, TEXT("recovery"));
    UE_LOG(LogTemp, Log, TEXT("[EcoLife][Recovery] Request=%lld Region=%s Species=%s Actual=%d Origin=Recovery ParentIds=0 Generation=0"),
        Request.RequestId, *RegionId.ToString(), *Species.SpeciesId.ToString(), Actual);
    return true;
}

bool AEcoCreatureIntegrationSpawner::ProcessPopulationRecovery(const FEcoServerTimeSnapshot& Time)
{
    if(PendingRecoveries.IsEmpty())return true;
    auto* Ecology=GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    auto& EM=GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    for(int32 I=PendingRecoveries.Num()-1;I>=0;--I){
        const auto P=PendingRecoveries[I];if(Time.ServerTimeSeconds<P.Issued)continue;PendingRecoveries.RemoveAtSwap(I);
        if(Time.ServerTimeSeconds-P.Issued>15)continue;
        if (const auto* Fauna = FindFauna(P.Species))
        {
            if (!ProcessFaunaRecovery(P.Region, *Fauna, Time)) return false;
            continue;
        }
        const FName Species = P.Species;
        const bool bPredator = Species == TEXT("Wolf");
        bool Empty=true;for(const auto E:Owned)
            if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(E).HP>0&&EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).SpeciesId==Species
                &&EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId==P.Region){Empty=false;break;}
        if(!Empty){UE_LOG(LogTemp,Log,TEXT("[EcoLife][RecoveryRejected] Region=%s Species=%s Reason=NotEmpty"),*P.Region.ToString(),*Species.ToString());continue;}
        FEcoSpawnRequest Request;
        if (!Ecology->RequestRecoverySpawn(P.Region, Time, Request, bPredator,
                bPredator ? CountFaunaDiets(P.Region) : FIntPoint::ZeroValue)) return false;
        const auto* C=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>()->FindContext(P.Region);
        TArray<FVector> Positions;
        for(int32 K=0;K<32&&Positions.Num()<Request.Count;++K){
            const uint64 Seed=uint64(Request.RequestId)*131+uint64(K)*13;
            const double X=5+(C->SizeUnits-10)*EcoLifeV3::Unit(Seed),Y=5+(C->SizeUnits-10)*EcoLifeV3::Unit(Seed+1);
            FVector Ground;if(!EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(),C->UnitsToCm(X,Y,C->OriginCm.Z),Ground))continue;
            bool Clear=true;
            if(bPredator)for(const auto& Cover:C->Sim.Config.Covers)
                if(Cover.Radius>0&&FMath::Square(X-Cover.X)+FMath::Square(Y-Cover.Y)<FMath::Square(Cover.Radius+1)){Clear=false;break;}
            if(!Clear)continue;
            for(const auto E:Owned)if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(E).HP>0
                &&FVector::DistSquared2D(Ground,EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation())<40000){Clear=false;break;}
            for(const auto& Other:Positions)if(FVector::DistSquared2D(Ground,Other)<40000){Clear=false;break;}
            if(Clear)Positions.Add(Ground);
        }
        const int32 Before=Owned.Num(),Actual=Positions.IsEmpty()?0:Spawn(P.Region,Positions.Num(),bPredator,Time,&Positions);
        if(!ReconcilePopulation()||!Ecology->CompleteSpawnRequest(Request.RequestId,Actual))return false;
        for(int32 K=Before;K<Owned.Num();++K){auto& Life=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Owned[K]).Individual;
            Life.Origin=EcoLifeV3::EOrigin::Recovery;Life.NextBirth=Time.ServerTimeSeconds+180;
            RecordTraitOutcome(EM,Owned[K],Time,TEXT("recovery"));
        }
        if(Actual)(bPredator?LastWolfRecovery:LastHerbRecovery).Add(P.Region,Time.ServerTimeSeconds);
        UE_LOG(LogTemp,Log,TEXT("[EcoLife][Recovery] Request=%lld Region=%s Species=%s Actual=%d Origin=Recovery ParentIds=0 Generation=0"),Request.RequestId,*P.Region.ToString(),*Species.ToString(),Actual);
    }
    return true;
}
static FAutoConsoleCommandWithWorldAndArgs RecoverEco(TEXT("eco.Ecosystem.Recover"),TEXT("Explicit authority operation: <region> <species>. Empty regional population, up to two founders, 300s per-region/species cooldown."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World){
        if (!World || World->GetNetMode() == NM_Client || Args.Num() != 2) return;
        for (TActorIterator<AEcoCreatureIntegrationSpawner> It(World); It; ++It)
        {
            const FName Region(*Args[0]), Species(*Args[1]);
            const bool bNative = Species == TEXT("Herbivore") || Species == TEXT("Wolf");
            const bool bQueued = bNative ? It->QueuePopulationRecovery(Region, Species == TEXT("Wolf"))
                : It->QueueFaunaRecovery(Region, Species);
            UE_LOG(LogTemp, Log, TEXT("[EcoLife][RecoveryQueue] Region=%s Species=%s Accepted=%d"),
                *Region.ToString(), *Species.ToString(), bQueued);
            break;
        }
    }));

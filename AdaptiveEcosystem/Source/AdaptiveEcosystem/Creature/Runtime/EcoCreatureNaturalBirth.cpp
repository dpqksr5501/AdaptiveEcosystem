#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoHerdMigration.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"

bool AEcoCreatureIntegrationSpawner::ProcessNaturalBirths(const FEcoServerTimeSnapshot& Time)
{
    if(!bEnableEcosystemLife)return true;
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    auto* Ecology=GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    if(!Native||!Native->IsActive()||!Ecology)return false;
    auto& EM=GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const double Now=Time.ServerTimeSeconds;
    auto NativePosition=[&](FMassEntityHandle E){
        if(const auto* B=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E))return B->Body.Pos;
        const auto& W=EM.GetFragmentDataChecked<FEcoThreatStateFragment>(E).Agent.State;return EcoWorldV3::FVec2{W.PosX,W.PosY};
    };
    auto Eligible=[&](int64 Id,FName Region,bool Predator)->FMassEntityHandle {
        const auto* E=AgentLookup.Find(Id);if(!E||!EM.IsEntityValid(*E))return {};
        const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(*E);
        const auto* Body=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(*E);
        const auto* Wolf=EM.GetFragmentDataPtr<FEcoThreatStateFragment>(*E);
        const auto* J=EM.GetFragmentDataPtr<FEcoHerdTravelFragment>(*E);
        if(!Link||Link->bDead||!Link->bAdopted||(Predator?(!Wolf||Wolf->Agent.bDead):(!Body||Body->Body.DeathCause!=0))
            ||EM.GetFragmentDataChecked<FEcoVitalsFragment>(*E).HP<=0
            ||EM.GetFragmentDataChecked<FEcoRegionFragment>(*E).CurrentRegionId!=Region
            ||Link->Individual.Generation>=64||!Link->Individual.CanParent(Now,Predator?Link->Individual.Nutrition:Body->Body.Energy,!(J&&(J->bActive||J->bStranded))))return {};
        return *E;
    };
    // At most one incubation per region and one scan/5s. Reservation is acquired
    // only at delivery; every terminal outcome completes/releases it this boundary.
    for(int32 I=PendingBirths.Num()-1;I>=0;--I){
        const auto P=PendingBirths[I];const auto A=Eligible(P.ParentA,P.Region,P.bPredator),B=Eligible(P.ParentB,P.Region,P.bPredator);
        if(!A.IsSet()||!B.IsSet()){PendingBirths.RemoveAtSwap(I);continue;}
        if(Now<P.Due)continue;
        PendingBirths.RemoveAtSwap(I);
        auto& LA=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(A).Individual;
        auto& LB=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(B).Individual;
        LA.NextBirth=LB.NextBirth=Now+30; // bounded retry on failed delivery
        auto* C=Native->FindContext(P.Region);if(!C)return false;
        const auto BA=NativePosition(A),BB=NativePosition(B);
        const auto& Link=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(A);
        if((BA.X-BB.X)*(BA.X-BB.X)+(BA.Y-BB.Y)*(BA.Y-BB.Y)>225)continue;
        FRegionEcologyState State;if(!Ecology->GetRegionState(P.Region,State)||(!P.bPredator&&State.FoodAmount/FMath::Max(1,State.Population)<1))continue;
        const FVector Center=C->UnitsToCm(BA.X,BA.Y,Link.GroundZ);
        TArray<FVector> Positions;
        for(int32 K=0;K<8;++K){
            const double Angle=K*2.399963+EcoLifeV3::Unit(uint64(P.ParentA)^uint64(P.ParentB))*UE_TWO_PI;
            FVector Ground;if(!EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(),Center+FVector(FMath::Cos(Angle),FMath::Sin(Angle),0)*(220+K*40),Ground))continue;
            const auto Q=C->CmToUnits(Ground);
            if(Q.X<0||Q.Y<0||Q.X>C->Sim.Config.WorldSize||Q.Y>C->Sim.Config.WorldSize)continue;
            if(P.bPredator&&EcoRefugeV3::Contains(C->Sim.Config.Covers,Q))continue;
            bool Clear=true;for(const auto E:Owned)if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(E).HP>0
                &&FVector::DistSquared2D(Ground,EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation())<10000){Clear=false;break;}
            if(Clear){Positions.Add(Ground);break;}
        }
        if(Positions.IsEmpty())continue;
        // Copy before spawning: entity creation may move/reallocate fragment storage.
        const auto Genome=EcoLifeV3::Inherit(LA.Genome,LB.Genome,uint64(P.ParentA)^EcoLifeV3::Mix(P.ParentB)^uint64(LA.Offspring));
        const uint32 Generation=FMath::Max(LA.Generation,LB.Generation)+1;
        FEcoSpawnRequest Reservation;if(!Ecology->RequestNaturalBirth(P.Region,Time,Reservation,P.bPredator))return false;
        const int32 Actual=Reservation.Count?Spawn(P.Region,1,P.bPredator,&Positions):0;
        if(!ReconcilePopulation()||!Ecology->CompleteSpawnRequest(Reservation.RequestId,Actual))return false;
        if(!Actual)continue;
        const auto Child=Owned.Last();auto& ChildLife=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Child).Individual;
        ChildLife={};ChildLife.bInitialized=true;ChildLife.Genome=Genome;ChildLife.Born=Now;
        ChildLife.ParentA=P.ParentA;ChildLife.ParentB=P.ParentB;ChildLife.Generation=Generation;ChildLife.Origin=EcoLifeV3::EOrigin::NaturalBirth;
        if(P.bPredator)ChildLife.Nutrition=.4;
        for(const auto E:{A,B}){
            auto& Parent=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E).Individual;
            Parent.NextBirth=Now+300;++Parent.Offspring;
            double Energy=0;
            if(P.bPredator){Parent.Nutrition-=.2;Energy=Parent.Nutrition;}
            else{auto& Body=EM.GetFragmentDataChecked<FEcoHerbivoreBodyV3Fragment>(E).Body;Body.Energy-=.2;Energy=Body.Energy;}
            auto& Vitals=EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);Vitals.Energy=float(Energy)*Vitals.MaxEnergy;
        }
        UE_LOG(LogTemp,Log,TEXT("[EcoLife][NaturalBirth] Child=%lld Parents=%lld,%lld Generation=%u Region=%s Speed=%.5f Size=%.5f Predator=%d"),
            EM.GetFragmentDataChecked<FEcoIdentityFragment>(Child).StableAgentId,P.ParentA,P.ParentB,Generation,*P.Region.ToString(),Genome.Speed,Genome.Size,P.bPredator);
    }
    if(Now<NextBirthScan)return true;NextBirthScan=Now+5;
    for(const auto& G:Groups)for(const bool Predator:{false,true}){
        if(PendingBirths.ContainsByPredicate([&](const FPendingBirth& P){return P.Region==G.RegionId&&P.bPredator==Predator;}))continue;
        TArray<int64> Candidates;
        for(const auto& E:AgentLookup)if(Eligible(E.Key,G.RegionId,Predator).IsSet())Candidates.Add(E.Key);
        Candidates.Sort();bool Found=false;
        for(int32 I=0;I<Candidates.Num()&&!Found;++I)for(int32 J=I+1;J<Candidates.Num()&&!Found;++J){
            const auto A=AgentLookup.FindChecked(Candidates[I]),B=AgentLookup.FindChecked(Candidates[J]);
            const auto& LA=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(A).Individual;
            const auto& LB=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(B).Individual;
            // Exclude parent/child and known full/half siblings. Unknown founders are not invented relatives.
            if(LA.ParentA==Candidates[J]||LA.ParentB==Candidates[J]||LB.ParentA==Candidates[I]||LB.ParentB==Candidates[I]
                ||(LA.ParentA&&(LA.ParentA==LB.ParentA||LA.ParentA==LB.ParentB))
                ||(LA.ParentB&&(LA.ParentB==LB.ParentA||LA.ParentB==LB.ParentB)))continue;
            const auto PA=NativePosition(A),PB=NativePosition(B);
            if((PA.X-PB.X)*(PA.X-PB.X)+(PA.Y-PB.Y)*(PA.Y-PB.Y)>100)continue;
            PendingBirths.Add({Candidates[I],Candidates[J],G.RegionId,Now+30,Predator});Found=true;
        }
    }
    return true;
}

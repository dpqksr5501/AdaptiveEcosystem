#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "World/EcoWorldClockSubsystem.h"
#include "GameFramework/Pawn.h"
#include "Engine/World.h"

bool AEcoCreatureIntegrationSpawner::QueuePlayerStrike(APawn& Player)
{
    if(!IsInGameThread()||GetNetMode()==NM_Client||!bEnableEcosystemLife||!bReady||Player.GetWorld()!=GetWorld()
        ||!Player.HasAuthority()||!Player.IsPlayerControlled()||PlayerStrikes.Num()>=32)return false;
    const double Now=GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
    const double RealNow=GetWorld()->GetTimeSeconds();
    for(auto It=StrikeCooldown.CreateIterator();It;++It)if(!It.Key().IsValid())It.RemoveCurrent();
    if(RealNow<StrikeCooldown.FindRef(&Player))return false;
    StrikeCooldown.Add(&Player,RealNow+1);
    PlayerStrikes.Add({&Player,Now});return true;
}
void AEcoCreatureIntegrationSpawner::ProcessPlayerStrikes(const FEcoServerTimeSnapshot& Time)
{
    if(!bEnableEcosystemLife||PlayerStrikes.IsEmpty())return;
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();if(!Native||!Native->IsActive()){PlayerStrikes.Reset();return;}
    auto& EM=GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    auto Position=[&](FMassEntityHandle E){
        const auto& L=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);const auto* C=Native->GetContext(L.ContextIndex);
        if(const auto* B=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E))return C->UnitsToCm(B->Body.Pos.X,B->Body.Pos.Y,L.GroundZ);
        const auto& Wolf=EM.GetFragmentDataChecked<FEcoThreatStateFragment>(E).Agent.State;return C->UnitsToCm(Wolf.PosX,Wolf.PosY,L.GroundZ);
    };
    auto ClearLine=[&](const FVector& A,const FVector& B){return !GetWorld()->LineTraceTestByObjectType(A,B,FCollisionObjectQueryParams(ECC_WorldStatic),FCollisionQueryParams(SCENE_QUERY_STAT(EcoPlayerStrike),false));};
    for(int32 I=PlayerStrikes.Num()-1;I>=0;--I){
        const auto Request=PlayerStrikes[I];if(Time.ServerTimeSeconds+1e-6<Request.Issued)continue;PlayerStrikes.RemoveAtSwap(I);
        auto* Player=Request.Player.Get();if(!Player||!Player->HasAuthority()||!Player->IsPlayerControlled()||Time.ServerTimeSeconds-Request.Issued>3)continue;
        const FVector From=Player->GetActorLocation();const FVector Forward=Player->GetActorForwardVector().GetSafeNormal2D();
        FVector PlayerEye;FRotator PlayerEyeRotation;Player->GetActorEyesViewPoint(PlayerEye,PlayerEyeRotation);
        FMassEntityHandle Best;double Distance=300;
        for(const auto Entity:Owned){
            const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
            if(!Link||!Link->bAdopted||Link->bDead||EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP<=0)continue;
            const FVector Point=Position(Entity)+FVector(0,0,65),Delta=Point-From;
            if(FMath::Abs(Delta.Z)>150||Delta.Size2D()>Distance||FVector::DotProduct(Delta.GetSafeNormal2D(),Forward)<.3||!ClearLine(From,Point))continue;
            Best=Entity;Distance=Delta.Size2D();
        }
        if(!Best.IsSet())continue;
        auto* Context=Native->GetContext(EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Best).ContextIndex);
        const double Now=Context->Sim.T*EcoRepertoireV3::kStepSeconds;
        const uint64 Episode=EcoLifeV3::Mix(++StrikeSequence)^0xA771ACCE55000000ULL;
        const FVector VictimPosition=Position(Best);
        auto Sees=[&](FMassEntityHandle E,const FVector& Target){
            const FVector P=Position(E);const FVector Delta=Target-P;FVector Heading;
            if(const auto* B=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E))Heading=FVector(B->Body.Head.X,B->Body.Head.Y,0);
            else {const auto& WolfState=EM.GetFragmentDataChecked<FEcoThreatStateFragment>(E).Agent.State;Heading=FVector(WolfState.HeadX,WolfState.HeadY,0);}
            const auto* C=Native->GetContext(EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E).ContextIndex);
            const bool Herb=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E)!=nullptr;
            const double Fov=Herb?C->Sim.ObsCfg.ThreatFovCos:C->Sim.ThreatCfg.PredFovCos;
            const double Radius=FMath::Min(12.,Herb?EcoWorldV3::SeePredNow(C->Sim):EcoWorldV3::WolfViewNow(C->Sim))*EcoRepertoireV3::kUnitCm;
            if(const auto* B=EM.GetFragmentDataPtr<FEcoBehaviorStateFragment>(E);B&&B->Rep.Behavior==EcoRepertoireV3::kSleep)return false;
            if(const auto* B=EM.GetFragmentDataPtr<FEcoThreatStateFragment>(E);B&&B->Agent.State.bAsleep)return false;
            const auto LocalP=C->CmToUnits(P),LocalTarget=C->CmToUnits(Target);
            if(C->Sim.Food.BlocksSight(LocalP.X,LocalP.Y,LocalTarget.X,LocalTarget.Y))return false;
            return Delta.Size2D()<=Radius&&FVector::DotProduct(Delta.GetSafeNormal2D(),Heading)>=Fov&&ClearLine(P+FVector(0,0,65),Target+FVector(0,0,65));
        };
        const bool Known=Sees(Best,PlayerEye-FVector(0,0,65));
        auto& Memory=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Best).Individual.Memory;
        const auto PlayerLocal=Context->CmToUnits(From);
        Memory.Suffer(Episode,Now,Known,PlayerLocal.X,PlayerLocal.Y,Known&&Memory.LastKind==EcoLifeV3::EEncounter::Pursuit);
        auto& Vitals=EM.GetFragmentDataChecked<FEcoVitalsFragment>(Best);Vitals.HP=FMath::Max(0.f,Vitals.HP-30.f);
        if(Vitals.HP<=0)EM.GetFragmentDataChecked<FEcoDeathFragment>(Best).Cause=EEcoDeathCause::ExternalDamage;
        TSet<int32> InformedHerds;
        if(Known)if(const auto* H=EM.GetFragmentDataPtr<FEcoHerdMemberFragment>(Best);H&&H->HerdRuntimeIndex>=0)InformedHerds.Add(H->HerdRuntimeIndex);
        bool Recognized=Known;
        for(const auto E:Owned){
            if(E==Best||EM.GetFragmentDataChecked<FEcoVitalsFragment>(E).HP<=0)continue;
            auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);if(!Link||!Link->bAdopted||!Link->Individual.bInitialized)continue;
            if(FVector::DistSquared2D(Position(E),VictimPosition)>1440000||!Sees(E,VictimPosition)||!Sees(E,PlayerEye-FVector(0,0,65)))continue;
            Recognized=true;
            const auto* C=Native->GetContext(Link->ContextIndex);const auto P=C->CmToUnits(From);
            Link->Individual.Memory.Observe(Vitals.HP<=0?EcoLifeV3::EEncounter::WitnessLoss:EcoLifeV3::EEncounter::Surprise,Episode,Now,Now,P.X,P.Y,.7);
            if(const auto* H=EM.GetFragmentDataPtr<FEcoHerdMemberFragment>(E);H&&H->HerdRuntimeIndex>=0)InformedHerds.Add(H->HerdRuntimeIndex);
        }
        for(const auto E:Owned){
            const auto* H=EM.GetFragmentDataPtr<FEcoHerdMemberFragment>(E);if(!H||!InformedHerds.Contains(H->HerdRuntimeIndex)
                ||EM.GetFragmentDataChecked<FEcoVitalsFragment>(E).HP<=0)continue;
            auto* L=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);if(!L||!L->bAdopted||FVector::DistSquared2D(Position(E),VictimPosition)>6250000)continue;
            L->Individual.Memory.ReceiveReport(Episode,Now,Now,.5);
        }
        if(Recognized)Context->KnownHumanDanger.Record(Episode,Now);
        UE_LOG(LogTemp,Log,TEXT("[EcoLife][PlayerStrike] Episode=%llu Victim=%lld Damage=30 HP=%.1f AttackerKnown=%d Kind=%d"),Episode,
            EM.GetFragmentDataChecked<FEcoIdentityFragment>(Best).StableAgentId,Vitals.HP,Known,int32(Memory.LastKind));
    }
}

#include "EcoPolicyV3IntegratedProcessors.h"

#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "DrawDebugHelpers.h"
#include "EcoHeading.h"
#include "EcoPolicyV3Fragments.h"
#include "EcoPolicyV3IntegratedFragments.h"
#include "EcoPolicyV3IntegratedSubsystem.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EcoHerdMigration.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Creature/Player/EcoPlayerEcologyComponent.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Player/EcoPlayerState.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "GameFramework/Pawn.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "MassCommonTypes.h"
#include "AI/Social/EcoPolicyV3SocialBridge.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "AI/Social/Shelter/EcoShelterLifecycleProcessor.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcologyRegion.h"
#include "EcoLifeLocomotion.h"

namespace EcoPolicyV3IntegratedProcImpl
{
    const FName NativeDeerSpecies(TEXT("Herbivore"));
    const FName NativeWolfSpecies(TEXT("Wolf"));

    void ExcludeOtherWriters(FMassEntityQuery& Query)
    {
        Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
        Query.AddRequirement<FEcoFaunaFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::None);
        Query.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::None);
        Query.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::None);
        Query.AddTagRequirement<FEcoStateTreeBehaviorTag>(EMassFragmentPresence::None);
        Query.AddTagRequirement<FEcoGroundedNavigationTag>(EMassFragmentPresence::None);
        Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
    }

	struct FMoveAdapter
	{
		const UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
        AEcoCreatureIntegrationSpawner* Combat = nullptr;
		FName RegionId;
		FEcoV3RegionContext* Ctx = nullptr;
		const TArray<FEcoIntegratedV3Fragment*>* HerbInts = nullptr;
		const TArray<FEcoIntegratedV3Fragment*>* WolfInts = nullptr;
        const TArray<FEcoV3DeerRec>* Deer = nullptr;
        const TArray<int32>* Rows = nullptr;
        const TArray<int64>* HerbIds=nullptr;
        const TArray<int64>* WolfKeys=nullptr;
        TArray<uint8> CaptureMask;
        UEcoShelterSubsystem* Shelters = nullptr;
        const UEcoHerdMigrationSubsystem* Journeys=nullptr;
        double Now = 0;
        double AuthorityNow = -1.;
        // Immutable pre-move positions, rebuilt once per native step. Contact
        // queries visit adjacent buckets, rather than every animal in the world.
        TMap<FIntPoint,TArray<int32>> BodyBuckets;
        TMap<int64,int32> FamilyRows;
	};

    bool Traveling(void* User,int32 Index){
        const auto& A=*static_cast<const FMoveAdapter*>(User);
        if(!A.Rows||!A.Rows->IsValidIndex(Index)||!A.Deer)return false;
        const auto* J=(*A.Deer)[(*A.Rows)[Index]].Journey;return J&&(J->bActive||J->bStranded);
    }
    void JourneyControlHook(void* User,int32 Index,const EcoWorldV3::FHerbView& H){
        const auto& A=*static_cast<const FMoveAdapter*>(User);
        const auto& D=(*A.Deer)[(*A.Rows)[Index]];const auto* J=D.Journey;
        if(!J)return;
        if(J->bStranded){
            H.Control->Velocity={0,0};H.Control->Gait=EcoRepertoireV3::kGaitStop;
            H.Control->DrainMult=1;H.Control->EatMult=0;H.Control->bStill=true;return;
        }
        if(!J->bActive)return;
        // Native personal danger wins. Shared alarm never creates an untrained flee override.
        if(H.Decision->KeepActive==EcoWorldV3::kKeepPanic||H.Decision->KeepActive==EcoWorldV3::kKeepShelter)return;
        namespace R=EcoRepertoireV3;const auto& C=A.Ctx->Sim.RepCfg;
        if(H.Rep->Behavior!=R::kGraze)R::Enter(*H.Rep,R::kGraze,H.Decision->DecisionObs,C);
        const FVector P=A.Ctx->UnitsToCm(H.Body->Pos.X,H.Body->Pos.Y,D.Int->GroundZ);
        FVector Goal=J->Goal;
        if(A.Ctx->Sim.Config.bEcosystemLife&&A.Journeys&&!J->bPause){
            if(const auto* Plan=A.Journeys->GetPlans().Find(J->PersistentHerdId)){
                const int32 Lanes=FMath::Clamp(FMath::FloorToInt(Plan->CorridorWidth/150),1,4);
                const int32 Lane=int32(EcoLifeV3::Mix(uint64(D.Id))%uint64(Lanes));
                const double Offset=(Lane-(Lanes-1)*.5)*FMath::Min(150.f,Plan->CorridorWidth/Lanes);
                const FVector Forward=(J->Goal-P).GetSafeNormal2D();Goal+=FVector(-Forward.Y,Forward.X,0)*Offset;
            }
        }
        const FVector Delta=Goal-P;
        FVector Separation=FVector::ZeroVector;
        for(const auto& Other:*A.Deer){
            if(Other.Id==D.Id||!Other.Journey||!Other.Journey->bActive||Other.Journey->PlanId!=J->PlanId||Other.Int->bDead)continue;
            const auto* Context=A.Sub->GetContext(Other.Int->ContextIndex);if(!Context)continue;
            const FVector Q=Context->UnitsToCm(Other.View.Body->Pos.X,Other.View.Body->Pos.Y,Other.Int->GroundZ);
            const FVector Away=P-Q;const double Distance=Away.Size2D();
            if(Distance>0.1&&Distance<220)Separation+=Away.GetSafeNormal2D()*(1-Distance/220);
            else if(Distance<=.1)Separation+=FVector(D.Id<Other.Id?-1:1,0,0);
        }
        const FVector Dir=(Delta.GetSafeNormal2D()+Separation.GetClampedToMaxSize(1)*.8).GetSafeNormal2D();
        H.Control->Gait=J->bPause?R::kGaitStop:R::kGaitWalk;
        const double Speed=C.HerbSpeed*C.GaitSpeed[H.Control->Gait]*J->SpeedScale;
        H.Control->Velocity={Dir.X*Speed,Dir.Y*Speed};
        H.Control->DrainMult=C.GaitDrain[H.Control->Gait];H.Control->EatMult=J->bPause?C.GaitEat[R::kGaitStop]:0;
        H.Control->SeeMult=1;H.Control->bCrouch=false;H.Control->bStill=J->bPause;
        H.Control->CoverMult=1;
        // Test bounded alternate headings through the existing terrain writer's constraints.
        if(A.Sub->UsesTerrain()&&!J->bPause){
            const FVector Step(Dir.X*Speed*R::kUnitCm,Dir.Y*Speed*R::kUnitCm,0);
            double Z=P.Z;
            if(!A.Sub->TraceMove(A.RegionId,P,P+Step,Z,true)){
                bool Found=false;
                for(const float Angle:{35.f,-35.f,70.f,-70.f}){
                    const FVector Alternative=Step.RotateAngleAxis(Angle,FVector::UpVector);
                    if(A.Sub->TraceMove(A.RegionId,P,P+Alternative,Z,true)){
                        H.Control->Velocity={Alternative.X/R::kUnitCm,Alternative.Y/R::kUnitCm};Found=true;break;
                    }
                }
                if(!Found)H.Control->Velocity={0,0};
            }
        }
    }

    void SocialControlHook(void* User,int32 Index,const EcoWorldV3::FHerbView& H)
    {
        const auto& A=*static_cast<const FMoveAdapter*>(User);
        if(!A.Rows||!A.Rows->IsValidIndex(Index)||!A.Deer)return;
        const auto& D=(*A.Deer)[(*A.Rows)[Index]];
        if(!D.SocialRequest||!D.Alarm||!D.SocialAudit)return;
        const auto& R=*D.SocialRequest;
        FEcoShelterSlot Slot;
        const bool Valid=A.Shelters&&A.Shelters->IsReservationValid(R.SlotIndex,D.Id,R.ReservationId,A.Now)
            &&A.Shelters->GetSlotData(R.SlotIndex,Slot)&&Slot.ShelterRuntimeIndex==R.ShelterIndex&&Slot.Position.Equals(R.TargetPosition,1);
        EcoV3Social::ApplyControl(R,*D.Alarm,*A.Ctx,*D.Int,*D.SocialAudit,H,Valid,A.Now);
        if(D.Feedback&&R.bValid&&R.ReservationId>0&&R.Mode!=EEcoSocialMovementMode::None
            &&D.SocialAudit->AppliedReservation==0)
            D.Feedback->Report(R.ReservationId,Valid?EEcoShelterMovementStatus::Yielded:EEcoShelterMovementStatus::Failed);
    }
    void ObservePlayers(const FMoveAdapter& A,EcoLifeV3::FMemory& Memory,const EcoWorldV3::FVec2& Position,
        const EcoWorldV3::FVec2& Head,double GroundZ,double Now,double Fov,double Radius,FName Species)
    {
        const auto* Set = A.Combat ? A.Combat->FootstepAudioSet.Get() : nullptr;
        const auto* Listener = Set ? Set->FindProfile(Species) : nullptr;
        if(Now<Memory.NextScan)return;
        Memory.NextScan=Now+(Listener?.35:1.);Memory.Age(Now);
        double Best=MAX_dbl;const EcoObservationV3::FThreatInput* Seen=nullptr;
        for(size_t K=0;K<A.Ctx->PlayerSamples.size();++K){
            const auto& Player=A.Ctx->PlayerSamples[K];
            if(!A.Ctx->PlayerEyeZ.IsValidIndex(int32(K)))continue;
            const double X=Player.X-Position.X,Y=Player.Y-Position.Y,D=FMath::Sqrt(X*X+Y*Y);
            if(D>FMath::Min(18.,Radius)||D>=Best||D<.01||(X*Head.X+Y*Head.Y)/D<Fov)continue;
            if(A.Ctx->Sim.Food.BlocksSight(Position.X,Position.Y,Player.X,Player.Y))continue;
            const FVector Start=A.Ctx->UnitsToCm(Position.X,Position.Y,GroundZ)+FVector(0,0,75);
            const FVector End=A.Ctx->UnitsToCm(Player.X,Player.Y,A.Ctx->PlayerEyeZ[int32(K)]);
            if(A.Sub->GetWorld()->LineTraceTestByObjectType(Start,End,FCollisionObjectQueryParams(ECC_WorldStatic),FCollisionQueryParams(SCENE_QUERY_STAT(EcoLifeEncounter),false)))continue;
            Seen=&Player;Best=D;
        }
        if(!Seen){
            Memory.PursuitExposure=FMath::Max(0.,Memory.PursuitExposure-1);
            // Read the position of the recorded emission.
            const FEcoLifeNoiseSample* Heard=nullptr;double Nearest=MAX_dbl;float BestSignal=0.f;
            for(const auto& N:A.Ctx->PlayerNoises){
                const double D=FMath::Sqrt(FMath::Square(N.X-Position.X)+FMath::Square(N.Y-Position.Y));
                if(Now<N.Time||Now-N.Time>UEcoNoiseSubsystem::EventLifetime)continue;
                const float SourceRange = Listener && N.Confidence > 0. ? float(N.Range * EcoRepertoireV3::kUnitCm / N.Confidence) : 0.f;
                const float DistanceCm = float(FMath::Sqrt(FMath::Square(D * EcoRepertoireV3::kUnitCm) + FMath::Square(GroundZ - N.Z)));
                const float Weather = float(A.Ctx->Sim.Weather.Hear);
                if (Listener)
                {
                    if (EcoFootsteps::HearingStrength(*Listener, DistanceCm, SourceRange, float(N.Confidence), Weather, false) <= BestSignal) continue;
                }
                else if(D>=Nearest||D>N.Range*A.Ctx->Sim.Weather.Hear)continue;
                const FVector Start=A.Ctx->UnitsToCm(Position.X,Position.Y,GroundZ)+FVector(0,0,75);
                const FVector End=A.Ctx->UnitsToCm(N.X,N.Y,N.Z)+FVector(0,0,75);
                const bool Blocked=A.Sub->GetWorld()->LineTraceTestByObjectType(Start,End,FCollisionObjectQueryParams(ECC_WorldStatic),FCollisionQueryParams(SCENE_QUERY_STAT(EcoLifeHearing),false));
                if (Listener)
                {
                    const float Signal = EcoFootsteps::HearingStrength(*Listener, DistanceCm, SourceRange, float(N.Confidence), Weather, Blocked);
                    if (Signal <= BestSignal) continue;
                    BestSignal = Signal;
                }
                else if(Blocked&&D>N.Range*A.Ctx->Sim.Weather.Hear*.25)continue;
                Heard=&N;Nearest=D;
            }
            if (Heard && Memory.Observe(Heard->bShot ? EcoLifeV3::EEncounter::Surprise : EcoLifeV3::EEncounter::Noise,EcoLifeV3::Mix(Heard->Id)^0xF00757E950000000ULL,
                Heard->Time,Now,Heard->X,Heard->Y,Listener?BestSignal:Heard->Confidence) && Listener)
            {
                const auto* Log = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Footsteps.HearingLog"));
                if (Log && Log->GetInt()) UE_LOG(LogTemp, Log,
                    TEXT("[Eco Footstep Hearing] Species=%s Source=%s Signal=%.3f Reaction=Memory"),
                    *Species.ToString(), Heard->bShot ? TEXT("Player.Shot") : TEXT("Player.Footstep"), BestSignal);
            }
            return;
        }
        const double Closing=((Position.X-Seen->X)*Seen->VelX+(Position.Y-Seen->Y)*Seen->VelY)/Best;
        const bool ClosingFast=Closing>.35&&Best<12;
        Memory.PursuitExposure=ClosingFast?FMath::Min(3.,Memory.PursuitExposure+1):FMath::Max(0.,Memory.PursuitExposure-1);
        const auto Kind=Memory.PursuitExposure>=2?EcoLifeV3::EEncounter::Pursuit:ClosingFast?EcoLifeV3::EEncounter::FastApproach:EcoLifeV3::EEncounter::Harmless;
        Memory.Observe(Kind,EcoLifeV3::Mix(uint64(Now/5)+1),Now,Now,Seen->X,Seen->Y);
    }
    void LifeLocomotion(const FMoveAdapter& A,int32 Index,const EcoWorldV3::FHerbView& H)
    {
        namespace R=EcoRepertoireV3;
        const auto& D=(*A.Deer)[(*A.Rows)[Index]];
        auto& Life=D.Int->Individual;Life.MotionReason=0;Life.FamilyMode=0;
        if(D.Journey&&(D.Journey->bStranded||(D.Journey->bActive&&D.Journey->bPause)))return;
        const bool Journey=D.Journey&&D.Journey->bActive;
        if(A.Sub->GetSettings().bSocialControl&&D.SocialAudit&&D.SocialAudit->AppliedReservation>0)return;
        const auto& W=A.Ctx->Sim;const auto& C=W.RepCfg;const auto& G=W.Food;
        const double Now=W.T*R::kStepSeconds;
        const bool Graze=!Journey&&H.Rep->Behavior==R::kGraze&&Life.Memory.Response==EcoLifeV3::EResponse::Policy
            &&H.Decision->KeepActive!=EcoWorldV3::kKeepPanic&&H.Decision->KeepActive!=EcoWorldV3::kKeepShelter;
        auto Walk=[&](R::FVec2 Direction){
            H.Control->Gait=R::kGaitWalk;H.Control->Velocity=R::Scale(R::Normalize(Direction),C.HerbSpeed*C.GaitSpeed[R::kGaitWalk]);
            H.Control->EatMult=C.GaitEat[R::kGaitWalk];H.Control->DrainMult=C.GaitDrain[R::kGaitWalk];H.Control->bStill=false;
        };
        const bool Settling=W.Config.bNaturalHabitats&&Now<Life.SettlementUntil;
        if(Graze&&H.Perception->Threat.PredCount==0&&(H.Body->Energy<.9||Settling)){
            const double Here=G.FoodAt(H.Body->Pos);
            const bool PreferSaferGround = G.Vegetation.bHabitatDynamics && H.Body->Energy >= .15;
            const auto HuntRisk = [&](const R::FVec2& P) {
                return Life.Memory.HuntRisk(P.X+A.Ctx->OriginCm.X/R::kUnitCm,P.Y+A.Ctx->OriginCm.Y/R::kUnitCm,Now);
            };
            const bool bPreferMove = PreferSaferGround
                && (HuntRisk(H.Body->Pos)>.42 || G.VegetationCells[G.CellOf(H.Body->Pos)].SurfaceWater>.55);
            // The learned .06 threshold exceeds entire small soil patches. A
            // hungry animal can stop for two real bites, instead of walking
            // forever over food it never considers sufficient to eat in place.
            const double Dispersed=std::hypot(H.Body->Pos.X-Life.SettlementX,H.Body->Pos.Y-Life.SettlementY);
            if(Here>=.012&&!bPreferMove&&(!Settling||Dispersed>4||H.Body->Energy<.15)){
                if(Settling&&Dispersed>4)Life.SettlementUntil=Now;
                H.Control->Velocity={};H.Control->Gait=R::kGaitStop;
                H.Control->EatMult=C.GaitEat[R::kGaitStop];H.Control->DrainMult=C.GaitDrain[R::kGaitStop];Life.MotionReason=1;
            }else{
                if(Life.ForageOriginX!=A.Ctx->OriginCm.X||Life.ForageOriginY!=A.Ctx->OriginCm.Y){
                    Life.ForageCell=-1;Life.NextForageScan=0;Life.ForageOriginX=A.Ctx->OriginCm.X;Life.ForageOriginY=A.Ctx->OriginCm.Y;
                }
                const double Range=EcoWorldV3::SeePredNow(W);
                if(Now>=Life.NextForageScan){
                    Life.NextForageScan=Now+1;Life.ForageCell=-1;
                    struct FCandidate{int32 Cell;double Score;};TArray<FCandidate> Candidates;
                    const int32 K=G.CellOf(H.Body->Pos),X=K%G.Gw,Y=K/G.Gw,Radius=FMath::CeilToInt(Range/G.Cell);
                    for(int32 J=FMath::Max(0,Y-Radius);J<=FMath::Min(G.Gw-1,Y+Radius);++J)
                        for(int32 I=FMath::Max(0,X-Radius);I<=FMath::Min(G.Gw-1,X+Radius);++I){
                            const int32 Cell=J*G.Gw+I;if(G.Food[Cell]<.02||(!G.Habitats.empty()&&!G.Habitats[Cell].bGroundUsable))continue;
                            const R::FVec2 Q{(I+.5)*G.Cell,(J+.5)*G.Cell},Delta=R::Sub(Q,H.Body->Pos);
                            const double Dist=std::hypot(Delta.X,Delta.Y);if(Dist>Range||Dist<.01)continue;
                            if((Delta.X*H.Body->Head.X+Delta.Y*H.Body->Head.Y)/Dist<W.ObsCfg.ThreatFovCos||G.BlocksSight(H.Body->Pos.X,H.Body->Pos.Y,Q.X,Q.Y))continue;
                            const auto* Bucket=A.BodyBuckets.Find(FIntPoint(FMath::FloorToInt((Q.X+A.Ctx->OriginCm.X/R::kUnitCm)/2),FMath::FloorToInt((Q.Y+A.Ctx->OriginCm.Y/R::kUnitCm)/2)));
                            const int32 Occupants=Bucket?Bucket->Num():0;
                            double Score=G.Food[Cell]/(1+Dist*.2)/(1+Occupants*(Life.bNaturalPopulation?2-Life.Genome.Sociability:1));
                            if(PreferSaferGround)
                                Score *= (1-.85*HuntRisk(Q))*(1-.65*G.VegetationCells[Cell].SurfaceWater);
                            if(Life.bNaturalPopulation)Score*=.92+.16*EcoLifeV3::Unit(uint64(D.Id)^EcoLifeV3::Mix(uint64(Cell)));
                            if(Settling){
                                const double FromArrival=std::hypot(Q.X-Life.SettlementX,Q.Y-Life.SettlementY);
                                if(FromArrival<4)continue;
                                Score*=1+EcoNaturalHabitat::Random(uint32(D.Id),uint32(Cell))*.7;
                                if(!G.Habitats.empty())Score*=1+.2*G.Habitats[Cell].WaterSupply;
                            }
                            Candidates.Add({Cell,Score});
                        }
                    Candidates.Sort([](const auto& L,const auto& Rhs){return L.Score==Rhs.Score?L.Cell<Rhs.Cell:L.Score>Rhs.Score;});
                    // Only four physical visibility/reachability checks per scan.
                    for(int32 I=0;I<FMath::Min(4,Candidates.Num());++I){
                        const int32 Cell=Candidates[I].Cell;const R::FVec2 Q{(Cell%G.Gw+.5)*G.Cell,(Cell/G.Gw+.5)*G.Cell};
                        const FVector P=A.Ctx->UnitsToCm(H.Body->Pos.X,H.Body->Pos.Y,D.Int->GroundZ);
                        const FVector Target=A.Ctx->UnitsToCm(Q.X,Q.Y,D.Int->GroundZ);double Z=D.Int->GroundZ;
                        if(A.Sub->UsesTerrain()&&!A.Sub->TraceMove(A.RegionId,P,Target,Z,false,30.f))continue;
                        if(A.Sub->GetWorld()->LineTraceTestByObjectType(P+FVector(0,0,60),FVector(Target.X,Target.Y,Z+30),
                            FCollisionObjectQueryParams(ECC_WorldStatic),FCollisionQueryParams(SCENE_QUERY_STAT(EcoLifeFoodSight),false)))continue;
                        Life.ForageCell=Cell;break;
                    }
                }
                if(Life.ForageCell>=0&&Life.ForageCell<int32(G.Food.size())&&G.Food[Life.ForageCell]>=.012){
                    const int32 Cell=Life.ForageCell;const R::FVec2 Q{(Cell%G.Gw+.5)*G.Cell,(Cell/G.Gw+.5)*G.Cell};
                    if(R::SizeSquared(R::Sub(Q,H.Body->Pos))<=Range*Range){Walk(R::Sub(Q,H.Body->Pos));Life.MotionReason=1;}
                }
            }
        }
        // Family is a local intent inside the existing Native writer. Never override danger,
        // a journey, hunger, Social reservations or a refuge arrival with attachment behavior.
        if(Life.bNaturalPopulation&&Life.AgeFraction(Now)<1&&!Journey){
            if(Life.FamilyOriginX!=A.Ctx->OriginCm.X||Life.FamilyOriginY!=A.Ctx->OriginCm.Y){
                Life.FamilySeen=-1;Life.NextFamilyScan=0;Life.FamilyOriginX=A.Ctx->OriginCm.X;Life.FamilyOriginY=A.Ctx->OriginCm.Y;
            }
            if(Now>=Life.NextFamilyScan){
                Life.NextFamilyScan=Now+1+EcoLifeV3::Unit(uint64(D.Id))*.3;
                auto Observe=[&](int32 Row){
                    const auto& Adult=(*A.Deer)[Row];const auto& Kin=Adult.Int->Individual;
                    if(Adult.Id==D.Id||Adult.Int->bDead||Adult.Vitals->HP<=0||Adult.Int->ContextIndex!=D.Int->ContextIndex
                        ||!Kin.bNaturalPopulation||Kin.Sex!=EcoLifeV3::ESex::Female||Kin.AgeFraction(Now)<1)return false;
                    const auto Q=Adult.View.Body->Pos;
                    if(R::SizeSquared(R::Sub(Q,H.Body->Pos))>144||FMath::Abs(Adult.Int->GroundZ-D.Int->GroundZ)>150)return false;
                    if(G.BlocksSight(H.Body->Pos.X,H.Body->Pos.Y,Q.X,Q.Y))return false;
                    const FVector From=A.Ctx->UnitsToCm(H.Body->Pos.X,H.Body->Pos.Y,D.Int->GroundZ)+FVector(0,0,60);
                    const FVector To=A.Ctx->UnitsToCm(Q.X,Q.Y,Adult.Int->GroundZ)+FVector(0,0,75);
                    if(A.Sub->GetWorld()->LineTraceTestByObjectType(From,To,FCollisionObjectQueryParams(ECC_WorldStatic),
                        FCollisionQueryParams(SCENE_QUERY_STAT(EcoFamilySight),false)))return false;
                    Life.FamilyObserved=Adult.Id;Life.FamilySeen=Now;Life.FamilyX=Q.X;Life.FamilyY=Q.Y;return true;
                };
                bool Seen=false;
                if(const auto* Row=A.FamilyRows.Find(Life.Caregiver))Seen=Observe(*Row);
                if(!Seen&&Life.FamilyObserved!=Life.Caregiver)if(const auto* Row=A.FamilyRows.Find(Life.FamilyObserved))Seen=Observe(*Row);
                // Lost/dead/separated caregiver: retain no remote target. A nearby adult can
                // become a social companion after the old sighting expires, without changing lineage.
                if(!Seen&&Now-Life.FamilySeen>30){
                    Life.FamilyObserved=0;
                    struct FCandidate{int32 Row;double Distance;};TArray<FCandidate> Candidates;
                    const FIntPoint Center(FMath::FloorToInt((H.Body->Pos.X+A.Ctx->OriginCm.X/R::kUnitCm)/2),FMath::FloorToInt((H.Body->Pos.Y+A.Ctx->OriginCm.Y/R::kUnitCm)/2));
                    for(int32 Y=-3;Y<=3;++Y)for(int32 X=-3;X<=3;++X)if(const auto* Bucket=A.BodyBuckets.Find(Center+FIntPoint(X,Y)))
                        for(const int32 Row:*Bucket){const auto& Adult=(*A.Deer)[Row];if(Adult.Int->ContextIndex==D.Int->ContextIndex&&Adult.Int->Individual.Sex==EcoLifeV3::ESex::Female)
                            Candidates.Add({Row,R::SizeSquared(R::Sub(Adult.View.Body->Pos,H.Body->Pos))});}
                    Candidates.Sort([](const auto& L,const auto& Rhs){return L.Distance==Rhs.Distance?L.Row<Rhs.Row:L.Distance<Rhs.Distance;});
                    for(int32 K=0;K<FMath::Min(4,Candidates.Num())&&!Seen;++K)Seen=Observe(Candidates[K].Row);
                }
            }
            if(Graze&&H.Perception->Threat.PredCount==0&&H.Body->Energy>.25){
                Life.FamilyMode=3;
                const int32 Cell=G.CellOf(H.Body->Pos);
                const bool Concealed=!G.Habitats.empty()&&G.Habitats[Cell].Plant==EcoVegetationV3::EPlant::Shrub&&G.Cap[Cell]>0&&G.Food[Cell]/G.Cap[Cell]>.45;
                if(Life.AgeFraction(Now)<.12&&Concealed){
                    Life.FamilyMode=1;++Life.FamilyHideSteps;H.Control->Velocity={};H.Control->Gait=R::kGaitStop;
                    H.Control->DrainMult=C.GaitDrain[R::kGaitStop];H.Control->EatMult=C.GaitEat[R::kGaitStop];H.Control->bStill=true;
                }else if(Life.FamilySeen>=0&&Now-Life.FamilySeen<=3){
                    const double Angle=EcoLifeV3::Unit(uint64(D.Id)+17)*UE_TWO_PI;
                    const R::FVec2 Target{Life.FamilyX+FMath::Cos(Angle)*1.4/Life.Genome.Sociability,Life.FamilyY+FMath::Sin(Angle)*1.4/Life.Genome.Sociability};
                    const auto Delta=R::Sub(Target,H.Body->Pos);const double Distance=std::hypot(Delta.X,Delta.Y);
                    if(Distance>1.2){
                        // Existing terrain sweep/collision decides whether this observed target is reachable.
                        Walk(Delta);H.Control->Velocity=R::ClampMagnitude(H.Control->Velocity,FMath::Max(0.,Distance-1.));
                        Life.FamilyMode=2;++Life.FamilyFollowSteps;
                    }
                }
            }
        }
        if(!H.Control->bStill&&H.Rep->Behavior!=R::kSleep&&H.Rep->Behavior!=R::kFreeze){
            const FIntPoint Center(FMath::FloorToInt((H.Body->Pos.X+A.Ctx->OriginCm.X/R::kUnitCm)/2),FMath::FloorToInt((H.Body->Pos.Y+A.Ctx->OriginCm.Y/R::kUnitCm)/2));
            R::FVec2 Separation;int32 Visited=0;
            for(int32 Y=-1;Y<=1;++Y)for(int32 X=-1;X<=1;++X)if(const auto* Bucket=A.BodyBuckets.Find(Center+FIntPoint(X,Y)))
                for(const int32 Row:*Bucket){
                    if(Visited++>=64)break;const auto& Other=(*A.Deer)[Row];if(Other.Id==D.Id)continue;
                    const auto* Context=A.Sub->GetContext(Other.Int->ContextIndex);if(!Context)continue;
                    const R::FVec2 Q{Other.View.Body->Pos.X+(Context->OriginCm.X-A.Ctx->OriginCm.X)/R::kUnitCm,
                        Other.View.Body->Pos.Y+(Context->OriginCm.Y-A.Ctx->OriginCm.Y)/R::kUnitCm};
                    const double Clearance=.5*(Life.BodyScale(Now)+Other.Int->Individual.BodyScale(Now));
                    Separation=R::Add(Separation,EcoLifeMotion::Separation(H.Body->Pos,Q,Clearance,uint64(D.Id),uint64(Other.Id)));
                }
            if(R::SizeSquared(Separation)>1.e-8){
                const double Existing=std::hypot(H.Control->Velocity.X,H.Control->Velocity.Y),WalkSpeed=C.HerbSpeed*C.GaitSpeed[R::kGaitWalk];
                // Freeze/arrived cover is never displaced. Moving escape keeps
                // its forward component; grazing yields even when it was stopped.
                if(!Graze&&Existing>1.e-8){
                    Separation=EcoLifeMotion::PassingAvoidance(Separation,R::Normalize(H.Control->Velocity));
                }
                H.Control->Velocity=R::ClampMagnitude(R::Add(H.Control->Velocity,R::Scale(R::ClampMagnitude(Separation,1),WalkSpeed*2.5)),FMath::Max(Existing,WalkSpeed));
                if(Graze){H.Control->Gait=R::kGaitWalk;H.Control->DrainMult=C.GaitDrain[R::kGaitWalk];H.Control->EatMult=C.GaitEat[R::kGaitWalk];}
                Life.MotionReason=2;
            }
            const auto Before=H.Control->Velocity;
            if(!Journey)H.Control->Velocity=EcoLifeMotion::BoundaryVelocity(H.Body->Pos,Before,W.Config.WorldSize,1.5);
            if(Before.X!=H.Control->Velocity.X||Before.Y!=H.Control->Velocity.Y)Life.MotionReason=3;
        }
    }

    void NaturalShelterControl(const FMoveAdapter& A,int32 Index,const EcoWorldV3::FHerbView& H)
    {
        namespace R=EcoRepertoireV3;
        if(!A.Ctx->Sim.Config.bNaturalHabitats)return;
        const auto& D=(*A.Deer)[(*A.Rows)[Index]];auto& Life=D.Int->Individual;auto& S=Life.Residence;
        if(Traveling(const_cast<FMoveAdapter*>(&A),Index)
            || (A.Sub->GetSettings().bSocialControl&&D.SocialAudit&&D.SocialAudit->AppliedReservation>0)
            || H.Decision->KeepActive == EcoWorldV3::kKeepPanic
            || Life.Memory.Response != EcoLifeV3::EResponse::Policy){
            S.Cover=-1;S.Phase=0;S.SettledSince=-1;return;
        }
        const bool Hide=H.Rep->Behavior==R::kHide,Sleep=H.Rep->Behavior==R::kSleep;
        if(!Hide&&!Sleep){S.Cover=-1;S.Phase=0;S.SettledSince=-1;return;}
        const auto& W=A.Ctx->Sim;const double Now=W.T*R::kStepSeconds,Body=.15*Life.BodyScale(Now);
        int32 Cover=Hide?H.Rep->HideTarget:-1;
        if(Sleep)for(int32 K=0;K<int32(W.Config.Covers.size());++K){const auto& C=W.Config.Covers[K];
            if(C.Radius>0&&std::hypot(C.X-H.Body->Pos.X,C.Y-H.Body->Pos.Y)<C.Radius){Cover=K;break;}}
        if(Cover<0||Cover>=int32(W.Config.Covers.size())||W.Config.Covers[Cover].Radius<=Body*3){
            S.Cover=-1;S.Phase=0;S.SettledSince=-1;return;
        }
        const auto& C=W.Config.Covers[Cover];
        const int64 Registration=A.Ctx->CoverRegistrations.IsValidIndex(Cover)?A.Ctx->CoverRegistrations[Cover]:0;
        if(S.OriginX!=A.Ctx->OriginCm.X||S.OriginY!=A.Ctx->OriginCm.Y||S.RequestedCover!=Cover||S.Registration!=Registration){
            S.Cover=-1;S.NextSearch=0;S.SettledSince=-1;S.OriginX=A.Ctx->OriginCm.X;S.OriginY=A.Ctx->OriginCm.Y;S.Registration=Registration;
            S.RequestedCover=Cover;
        }
        const bool Seen=H.Perception->Threat.PredCount>0;
        const double Depth=C.Radius-std::hypot(H.Body->Pos.X-C.X,H.Body->Pos.Y-C.Y);
        // Cover is an opportunity to break contact, not a promise to wait for a predator.
        if(Seen&&H.Perception->Threat.DPredMin<5){
            S.Cover=-1;S.Phase=4;S.SettledSince=-1;
            const auto Away=R::Normalize(H.Perception->Threat.AwayFromPred);
            H.Control->Velocity=R::Scale(Away,W.RepCfg.HerbSpeed*W.RepCfg.GaitSpeed[R::kGaitRun]);
            H.Control->Gait=R::kGaitRun;H.Control->DrainMult=W.RepCfg.GaitDrain[R::kGaitRun];
            H.Control->EatMult=0;H.Control->bStill=false;H.Control->bCrouch=false;H.Rep->bArrived=false;return;
        }
        auto Occupied=[&](double X,double Y){
            int32 Count=0;
            int32 Capacity=16;
            if(A.Shelters&&A.Ctx->CoverShelterIndices.IsValidIndex(Cover))for(const auto& Point:A.Shelters->GetShelters())
                if(Point.RuntimeIndex==A.Ctx->CoverShelterIndices[Cover]){Capacity=Point.Capacity;break;}
            for(const auto& Other:*A.Deer){
                if(Other.Id==D.Id||Other.Int->bDead||Other.View.Body->DeathCause!=EcoWorldV3::kDeathNone)continue;
                const auto* OtherCtx=A.Sub->GetContext(Other.Int->ContextIndex);if(!OtherCtx)continue;
                const auto& Place=Other.Int->Individual.Residence;
                if(OtherCtx==A.Ctx&&Place.Cover==Cover&&Place.Phase>=1&&Place.Phase<=3){
                    if(std::hypot(Place.X-X,Place.Y-Y)<1.0)return true;
                    ++Count;
                }
                const auto P=OtherCtx->UnitsToCm(Other.View.Body->Pos.X,Other.View.Body->Pos.Y,Other.Int->GroundZ);
                const auto Q=A.Ctx->UnitsToCm(X,Y,D.Int->GroundZ);
                if(FVector::DistSquared(P,Q)<FMath::Square(160.))return true;
            }
            return Count>=Capacity;
        };
        if(S.Cover>=0&&Now>=S.NextSearch){
            S.NextSearch=Now+1;
            if(Occupied(S.X,S.Y)){S.Cover=-1;S.SettledSince=-1;}
        }
        if(S.Cover<0&&Now>=S.NextSearch){
            S.NextSearch=Now+1+EcoNaturalHabitat::Random(uint32(D.Id),9);
            double Best=-1.e30;bool Found=false;
            for(int32 K=0;K<8;++K){
                const auto P=EcoNaturalHabitat::Interior(uint32(D.Id),C.X,C.Y,C.Radius,Body,K);
                if(Occupied(P.X,P.Y))continue;
                // Validate a sampled ground point and the initial physical step. The native
                // writer validates every subsequent step; a blocked approach is replanned.
                FVector Ground=A.Ctx->UnitsToCm(P.X,P.Y,D.Int->GroundZ);
                FVector Projected;
                if(!EcoCreatureMovement::ProjectSpawnPoint(*A.Sub->GetWorld(),Ground,Projected))continue;
                const double Distance=std::hypot(P.X-H.Body->Pos.X,P.Y-H.Body->Pos.Y);
                const auto Dir=R::Normalize({P.X-H.Body->Pos.X,P.Y-H.Body->Pos.Y});
                double Z=D.Int->GroundZ;
                if(!A.Sub->TraceMove(A.RegionId,A.Ctx->UnitsToCm(H.Body->Pos.X,H.Body->Pos.Y,Z),
                    A.Ctx->UnitsToCm(H.Body->Pos.X+Dir.X*.3,H.Body->Pos.Y+Dir.Y*.3,Z),Z,false,FMath::Clamp(float(Body*R::kUnitCm),20.f,40.f)))continue;
                if(FMath::Abs(Projected.Z-Ground.Z)>200)continue;
                const double Score=C.Radius-std::hypot(P.X-C.X,P.Y-C.Y)-Distance*.15
                    +(Seen?(P.X-C.X)*H.Perception->Threat.AwayFromPred.X+(P.Y-C.Y)*H.Perception->Threat.AwayFromPred.Y:0);
                if(Score>Best){Best=Score;S.X=P.X;S.Y=P.Y;Found=true;}
            }
            if(Found){S.Cover=Cover;S.Phase=1;S.LastProgress=Now;S.LastDistance=1.e9;}
            else {S.Phase=5;++S.SearchFailures;}
        }
        H.Control->bCrouch=false;H.Rep->bArrived=false;H.Control->EatMult=0;H.Control->SeeMult=1;
        if(S.Cover<0){
            // No valid interior place: continue an alert walk, never crouch on the rim.
            const auto Dir=Seen?H.Perception->Threat.AwayFromPred:H.Body->Head;
            H.Control->Velocity=R::Scale(R::Normalize(Dir),W.RepCfg.HerbSpeed*W.RepCfg.GaitSpeed[R::kGaitWalk]);
            H.Control->Gait=R::kGaitWalk;H.Control->DrainMult=W.RepCfg.GaitDrain[R::kGaitWalk];H.Control->bStill=false;return;
        }
        const double Distance=std::hypot(S.X-H.Body->Pos.X,S.Y-H.Body->Pos.Y);
        if(Distance<S.LastDistance-.05){S.LastDistance=Distance;S.LastProgress=Now;}
        if(Distance>std::max(.25,Body)){
            S.SettledSince=-1;S.Phase=1;
            const double Speed=std::min(Distance,W.RepCfg.HerbSpeed*W.RepCfg.GaitSpeed[R::kGaitWalk]);
            H.Control->Velocity=R::Scale(R::Normalize({S.X-H.Body->Pos.X,S.Y-H.Body->Pos.Y}),Speed);
            H.Control->Gait=R::kGaitWalk;H.Control->DrainMult=W.RepCfg.GaitDrain[R::kGaitWalk];H.Control->bStill=false;
            if(Now-S.LastProgress>5){S.Cover=-1;S.NextSearch=Now;S.Phase=5;++S.SearchFailures;}
        }else{
            if(S.SettledSince<0)S.SettledSince=Now;
            if(Seen||Life.Memory.Response==EcoLifeV3::EResponse::Retreat)S.SettledSince=Now;
            const bool Rest=EcoNaturalHabitat::CanRest(Distance,Depth,Body,Seen,H.Rep->Recency>.05?0:8,
                Now-S.SettledSince,3+EcoNaturalHabitat::Random(uint32(D.Id),3)*4);
            if(Rest&&S.Phase!=3&&Hide)H.Rep->LockLeft=W.RepCfg.LockHide;
            S.Phase=Rest?3:2;H.Control->Velocity={};H.Control->Gait=R::kGaitStop;
            H.Control->DrainMult=W.RepCfg.GaitDrain[R::kGaitStop];H.Control->bStill=true;H.Control->bCrouch=Rest&&Hide;
            H.Rep->bArrived=Rest&&Hide;
            if(Rest){if(Depth<Body*2)++S.EdgeRestSteps;else ++S.InteriorRestSteps;}
        }
    }

    void IntegratedControlHook(void* User,int32 Index,const EcoWorldV3::FHerbView& H){
        const auto& A=*static_cast<const FMoveAdapter*>(User);
        const auto& DeerRow = (*A.Deer)[(*A.Rows)[Index]];
        const bool bTraveling = Traveling(User,Index);
        const bool bWaitingForRegion = DeerRow.Journey && DeerRow.Journey->IsWaitingForRegion();
        const bool bUseSocialControl = !bTraveling && A.Sub->GetSettings().bSocialControl;
        if (bUseSocialControl)
            SocialControlHook(User,Index,H);
        else if (auto* Audit = DeerRow.SocialAudit)
        {
            // A lease applied in an earlier step must not claim the current journey.
            Audit->Applied = EEcoV3SocialControl::None;
            Audit->AppliedReservation = 0;
            Audit->bRejectedUnsafeShelter = false;
        }
        if (bTraveling && !bWaitingForRegion) JourneyControlHook(User,Index,H);
        auto& Life = DeerRow.Int->Individual;
        if(A.Ctx->Sim.Config.bEcosystemLife){
            if(Life.bInitialized){
                const double SimTime=A.Ctx->Sim.T*EcoRepertoireV3::kStepSeconds;
                auto& Memory=Life.Memory;
                const bool Awake=H.Rep->Behavior!=EcoRepertoireV3::kSleep;
                if(Awake)ObservePlayers(A,Memory,H.Body->Pos,H.Body->Head,(*A.Deer)[(*A.Rows)[Index]].Int->GroundZ,SimTime,A.Ctx->Sim.ObsCfg.ThreatFovCos,EcoWorldV3::SeePredNow(A.Ctx->Sim),TEXT("Herbivore"));
                const double X=Memory.LastX-H.Body->Pos.X,Y=Memory.LastY-H.Body->Pos.Y;
                const double Distance=FMath::Sqrt(X*X+Y*Y);
                const bool bSocialOwnsControl = bUseSocialControl && DeerRow.SocialAudit
                    && (DeerRow.SocialAudit->AppliedReservation > 0 || DeerRow.SocialAudit->Applied == EEcoV3SocialControl::Flee);
                const bool Safe=H.Decision->KeepActive!=EcoWorldV3::kKeepPanic&&H.Decision->KeepActive!=EcoWorldV3::kKeepShelter
                    &&Awake&&H.Perception->Threat.PredCount==0&&H.Body->Energy>.25&&!bSocialOwnsControl;
                const auto Response=Memory.Decide(SimTime,Distance,Safe,bTraveling);
                if(Response!=EcoLifeV3::EResponse::Policy){
                    const double Direction=Response==EcoLifeV3::EResponse::Retreat?-1:Response==EcoLifeV3::EResponse::Curious?1:0;
                    const double V=A.Ctx->Sim.RepCfg.HerbSpeed*(Direction<0?A.Ctx->Sim.RepCfg.GaitSpeed[EcoRepertoireV3::kGaitRun]:.3);
                    const double AppliedSpeed=Direction>0?FMath::Min(V,FMath::Max(0.,Distance-6)):V;
                    H.Control->Velocity={Direction*X/FMath::Max(.01,Distance)*AppliedSpeed,Direction*Y/FMath::Max(.01,Distance)*AppliedSpeed};
                    const bool UnknownEscape=!Memory.bLastDamageKnown&&Memory.UnknownFear>.15&&Memory.LastDamage>=0&&SimTime-Memory.LastDamage<8;
                    if(UnknownEscape)H.Control->Velocity={H.Body->Head.X*V,H.Body->Head.Y*V};
                    H.Control->Gait=Direction?EcoRepertoireV3::kGaitWalk:EcoRepertoireV3::kGaitStop;
                    H.Control->EatMult=0;H.Control->DrainMult=1;H.Control->bStill=!Direction;
                    if(Direction<0){H.Control->Gait=EcoRepertoireV3::kGaitRun;H.Control->DrainMult=A.Ctx->Sim.RepCfg.GaitDrain[EcoRepertoireV3::kGaitRun];}
                    if(UnknownEscape){H.Control->Gait=EcoRepertoireV3::kGaitWalk;H.Control->bStill=false;}
                    if(Direction<0||UnknownEscape){
                        const double ActualSpeed=FMath::Sqrt(FMath::Square(H.Control->Velocity.X)+FMath::Square(H.Control->Velocity.Y));
                        if(ActualSpeed>.001){
                            const auto Dir=EcoWorldV3::WildEdgeSteer(H.Body->Pos,{H.Control->Velocity.X/ActualSpeed,H.Control->Velocity.Y/ActualSpeed},
                                A.Ctx->Sim.Config.WorldSize,A.Ctx->Sim.Config.WildFlight.EdgeR);
                            H.Control->Velocity={Dir.X*ActualSpeed,Dir.Y*ActualSpeed};
                        }
                    }
                }
                LifeLocomotion(A,Index,H);
                NaturalShelterControl(A,Index,H);
                Life.bMealRestApplied = false;
                if (A.Combat && A.Combat->UsesAdaptiveRoutine(EEcoAdaptiveRoutine::DeerMeal))
                {
                    constexpr double MealStop = .9;
                    const double EnergyFraction = H.Body->Energy / A.Ctx->Sim.RepCfg.MaxEnergy;
                    const bool bLowReserve = A.Ctx->Sim.ReserveCap > 0. && H.Body->Reserve < .2;
                    const double Start = bLowReserve ? .8 : .65;
                    const bool bWasSeeking = Life.MealCycle.bSeeking;
                    Life.MealCycle.Update(EnergyFraction, SimTime, Start, MealStop, 4.);
                    if (bWasSeeking != Life.MealCycle.bSeeking)
                        UE_LOG(LogEcoPolicyV3I, Log, TEXT("[Eco MealCycle] Id=%lld Species=Herbivore Seeking=%d Energy=%.3f"),
                            (*A.Deer)[(*A.Rows)[Index]].Id, Life.MealCycle.bSeeking, H.Body->Energy);
                    const bool bOrdinaryGraze = Awake && !bTraveling && H.Perception->Threat.PredCount == 0
                        && H.Decision->KeepActive == EcoWorldV3::kKeepNone && Response == EcoLifeV3::EResponse::Policy
                        && H.Rep->Behavior == EcoRepertoireV3::kGraze && H.Control->EatMult > 0.;
                    if (bOrdinaryGraze && !Life.MealCycle.bSeeking)
                    {
                        H.Control->EatMult = 0.;
                        if (Life.MealCycle.IsResting(SimTime))
                        {
                            H.Control->Velocity = {};
                            H.Control->Gait = EcoRepertoireV3::kGaitStop;
                            H.Control->DrainMult = A.Ctx->Sim.RepCfg.GaitDrain[EcoRepertoireV3::kGaitStop];
                            H.Control->bStill = true;
                            Life.bMealRestApplied = true;
                        }
                    }
                    // The same meal rule owns the ceiling for alert grazing and journey pauses.
                    if (EnergyFraction >= MealStop && !bLowReserve)
                        H.Control->EatMult = 0.;
                }
                const double Speed=Life.SpeedScale(SimTime);
                H.Control->Velocity.X*=Speed;H.Control->Velocity.Y*=Speed;
                H.Control->DrainMult*=Life.Maintenance();
            }
        }
        if (bWaitingForRegion)
        {
            // Keep sensing and basal metabolism while the route geometry is unavailable.
            H.Control->Velocity = {};
            H.Control->Gait = EcoRepertoireV3::kGaitStop;
            H.Control->DrainMult = A.Ctx->Sim.RepCfg.GaitDrain[EcoRepertoireV3::kGaitStop]
                * (A.Ctx->Sim.Config.bEcosystemLife && Life.bInitialized ? Life.Maintenance() : 1.);
            H.Control->EatMult = 0.;
            H.Control->bStill = true;
        }
    }

    void EvidenceThreatHook(void* User,int32 Index,EcoWorldV3::FThreatAgent& Threat,EcoThreatV3::FThreatStepInput& Input)
    {
        auto& A=*static_cast<FMoveAdapter*>(User);
        if(!A.Ctx->Sim.Config.bEcosystemLife||!A.WolfInts||!A.WolfInts->IsValidIndex(Index))return;
        auto& Link=*(*A.WolfInts)[Index];auto& I=Link.Individual.Investigation;
        const double Now=A.Ctx->Sim.T*EcoRepertoireV3::kStepSeconds;
        auto& Life=Link.Individual;
        const int64 WolfId = A.WolfKeys && A.WolfKeys->IsValidIndex(Index) ? (*A.WolfKeys)[Index] : 0;
        if (A.Combat && WolfId > 0)
        {
            FVector Ignored;
            A.Combat->SelectWolfCarrion(WolfId, A.RegionId, FVector::ZeroVector, false, 0., Ignored);
        }
        const bool bAdaptive = A.Combat && A.Combat->UsesAdaptiveRoutine(EEcoAdaptiveRoutine::WolfMeal);
        Life.bMealRestApplied = false;
        if (bAdaptive)
        {
            const bool bWasSeeking = Life.MealCycle.bSeeking;
            Life.MealCycle.Update(Life.Nutrition, Now, .75, .92, 6.);
            if (bWasSeeking != Life.MealCycle.bSeeking)
                UE_LOG(LogEcoPolicyV3I, Log, TEXT("[Eco MealCycle] Id=%lld Species=Wolf Seeking=%d Energy=%.3f"),
                    WolfId, Life.MealCycle.bSeeking, Life.Nutrition);
        }
        const bool bMayFeed = !bAdaptive || Life.MealCycle.bSeeking;
        if(!Life.PredatorStep(Now,Threat.State.PosX,Threat.State.PosY,Threat.Last.bRunning,EcoRepertoireV3::kStepSeconds,
            bMayFeed,bAdaptive?.92:1.)){
            Threat.bDead=true;I.Cancel(Now);Life.AbandonMeat();Input.bHuntingAllowed=false;return;
        }
        if(Life.BaseSpeed<=0){Life.BaseSpeed=Threat.Spec.BaseSpeed;Life.BaseCatchRadius=Threat.Spec.CatchRadius;}
        Threat.Spec.BaseSpeed=Life.BaseSpeed*Life.SpeedScale(Now)*(Life.Nutrition<.15?.7:1.);
        Threat.Spec.CatchRadius=Life.BaseCatchRadius*Life.BodyScale(Now);
        Input.bHuntingAllowed=Input.bHuntingAllowed&&(bAdaptive?bMayFeed:Life.Nutrition<.9);
        if(Life.MealRemaining>0&&Now<Life.MealExpires&&(bAdaptive?bMayFeed:(Life.Nutrition<.9||Life.bFeedingMeat))){
            const double X=Life.MealX-Threat.State.PosX,Y=Life.MealY-Threat.State.PosY,D=FMath::Sqrt(X*X+Y*Y);
            Input.bHuntingAllowed=false;Input.bResourceApproach=true;Input.bResourceWait=D<=2.5;
            Input.ResourceDirX=X/FMath::Max(.01,D);Input.ResourceDirY=Y/FMath::Max(.01,D);
        }
        if(!Threat.State.bAsleep)ObservePlayers(A,Life.Memory,{Threat.State.PosX,Threat.State.PosY},{Threat.State.HeadX,Threat.State.HeadY},Link.GroundZ,Now,
            A.Ctx->Sim.ThreatCfg.PredFovCos,EcoWorldV3::WolfViewNow(A.Ctx->Sim),TEXT("Wolf"));
        const double HumanX=Life.Memory.LastX-Threat.State.PosX,HumanY=Life.Memory.LastY-Threat.State.PosY;
        const double HumanDistance=FMath::Sqrt(HumanX*HumanX+HumanY*HumanY);
        const auto Response=Life.Memory.Decide(Now,HumanDistance,!Threat.State.bAsleep&&Life.Nutrition>.2,false);
        if(Response!=EcoLifeV3::EResponse::Policy&&(Response!=EcoLifeV3::EResponse::Curious||Life.Nutrition>.5)){
            Input.bHuntingAllowed=false;Input.bResourceApproach=true;
            const double Direction=Response==EcoLifeV3::EResponse::Retreat?-1:Response==EcoLifeV3::EResponse::Curious?1:0;
            Input.bResourceWait=Direction==0||(Direction>0&&HumanDistance<=6);
            Input.ResourceDirX=Direction*HumanX/FMath::Max(.01,HumanDistance);Input.ResourceDirY=Direction*HumanY/FMath::Max(.01,HumanDistance);
            if(!Life.Memory.bLastDamageKnown&&Life.Memory.UnknownFear>.15&&Life.Memory.LastDamage>=0&&Now-Life.Memory.LastDamage<8){
                Input.bResourceWait=false;Input.ResourceDirX=Threat.State.HeadX;Input.ResourceDirY=Threat.State.HeadY;
            }
        }
        if (A.Combat && A.WolfKeys && A.WolfKeys->IsValidIndex(Index))
        {
            const FVector P=A.Ctx->UnitsToCm(Threat.State.PosX,Threat.State.PosY,Link.GroundZ);
            const bool Available=!Threat.State.bAsleep && Life.Nutrition>.2 && Life.MealRemaining<=0 && Response!=EcoLifeV3::EResponse::Retreat;
            if (A.Combat->GuideWolfPlayerCombat((*A.WolfKeys)[Index],*A.Ctx,P,FVector(Threat.State.HeadX,Threat.State.HeadY,0),Now,Available,Life.Memory.bLastDamageKnown && Life.Memory.LastDamage>=0 && Now-Life.Memory.LastDamage<20,Input))
            { I.Cancel(Now); return; }
        }
        if (A.Combat && WolfId > 0 && !Input.bResourceApproach && !Threat.State.bAsleep
            && (bAdaptive ? bMayFeed : Life.Nutrition < .75))
        {
            const FVector Position = A.Ctx->UnitsToCm(Threat.State.PosX, Threat.State.PosY, Link.GroundZ);
            FVector Food;
            const double ApproachSpeed = Threat.Spec.BaseSpeed * EcoRepertoireV3::kUnitCm / EcoRepertoireV3::kStepSeconds;
            if (A.Combat->SelectWolfCarrion(WolfId, A.RegionId, Position, true, ApproachSpeed, Food, A.AuthorityNow))
            {
                const FVector Direction = (Food - Position).GetSafeNormal2D();
                Input.bHuntingAllowed = false;
                Input.bResourceApproach = true;
                Input.bResourceWait = FVector::DistSquared2D(Position, Food) <= FMath::Square(95.);
                Input.ResourceDirX = Direction.X;
                Input.ResourceDirY = Direction.Y;
                I.Cancel(Now);
                return;
            }
        }
        if (bAdaptive && Life.MealCycle.IsResting(Now) && !Input.bResourceApproach && !Threat.State.bAsleep)
        {
            Input.bResourceApproach = true;
            Input.bResourceWait = true;
            Life.bMealRestApplied = true;
            I.Cancel(Now);
            return;
        }
        auto ClearLine=[&](double X,double Y,double Z){
            const FVector Start=A.Ctx->UnitsToCm(Threat.State.PosX,Threat.State.PosY,Link.GroundZ)+FVector(0,0,65);
            const FVector End=A.Ctx->UnitsToCm(X,Y,Z)+FVector(0,0,65);
            return !A.Ctx->Sim.Food.BlocksSight(Threat.State.PosX,Threat.State.PosY,X,Y)
                &&!A.Sub->GetWorld()->LineTraceTestByObjectType(Start,End,FCollisionObjectQueryParams(ECC_WorldStatic),FCollisionQueryParams(SCENE_QUERY_STAT(EcoHuntSight),false));
        };
        A.CaptureMask.Init(1,Input.NumPrey);
        for(int32 K=0;K<Input.NumPrey;++K){const auto& P=Input.Prey[K];
            if(FMath::Square(P.X-Threat.State.PosX)+FMath::Square(P.Y-Threat.State.PosY)<=FMath::Square(Threat.Spec.CatchRadius*3))
                A.CaptureMask[K]=ClearLine(P.X,P.Y,(*A.HerbInts)[K]->GroundZ)?1:0;
        }
        Input.CaptureAllowed=A.CaptureMask.GetData();
        if(I.Role==EcoTracesV3::ERole::Lead&&Now<I.Until&&A.HerbIds){
            const int32 Previous=A.HerbIds->Find(I.Target);if(Previous!=INDEX_NONE)Input.PreferredTarget=Previous;
        }
        auto Probe=Threat.State;const auto Perceived=EcoThreatV3::Step(Threat.Spec,Probe,Input,A.Ctx->Sim.ThreatCfg);
        if(!Perceived.bHunting){I.Cancel(Now);return;}
        if(Input.bPackHelp&&A.Ctx->Sim.PackGoalBuf.size()>size_t(Index)){
            const auto& Goal=A.Ctx->Sim.PackGoalBuf[Index];
            const int64 Target=A.HerbIds&&A.HerbIds->IsValidIndex(Goal.Prey)?(*A.HerbIds)[Goal.Prey]:0;
            if(Target){
                Life.LastHuntTarget=Target;Life.LastHuntTime=Now;
                if(I.Role!=EcoTracesV3::ERole::Intercept||I.Target!=Target||Now>=I.Until){
                    I.Role=EcoTracesV3::ERole::Intercept;I.Target=Target;I.Until=Now+3;I.Trace=0;
                    I.X=Goal.GoalX;I.Y=Goal.GoalY;
                }
                const double X=I.X-Threat.State.PosX,Y=I.Y-Threat.State.PosY,D=FMath::Sqrt(X*X+Y*Y);
                Input.bPackWait=D<1;Input.PackDirX=X/FMath::Max(.01,D);Input.PackDirY=Y/FMath::Max(.01,D);return;
            }
        }
        if(Perceived.bHasTarget){
            const int64 Target=A.HerbIds&&A.HerbIds->IsValidIndex(Perceived.Target)?(*A.HerbIds)[Perceived.Target]:0;
            Life.LastHuntTarget=Target;Life.LastHuntTime=Now;
            if(I.Role!=EcoTracesV3::ERole::Lead||I.Target!=Target||Now>=I.Until){I.Role=EcoTracesV3::ERole::Lead;I.Target=Target;I.Until=Now+3;I.Trace=0;}
            return;
        }
        if(I.Role==EcoTracesV3::ERole::Lead||I.Role==EcoTracesV3::ERole::Intercept)I.Cancel(Now);
        if(I.Trace){
            const double D=FMath::Sqrt(FMath::Square(I.X-Threat.State.PosX)+FMath::Square(I.Y-Threat.State.PosY));
            if(D+.15<I.BestDistance){I.BestDistance=D;I.LastProgress=Now;}
            if(Now>I.Until||Now-I.Started>12||Now-I.LastProgress>4||D<1){I.Cancel(Now);return;}
        }else if(Now>=I.NextQuery&&Now>=I.Cooldown){
            I.NextQuery=Now+1;const EcoTracesV3::FTrace* Best=nullptr;
            A.Ctx->MovementTraces.Query(Threat.State.PosX,Threat.State.PosY,Now,[&](const auto& T){
                if(T.Id<=I.LastUsed||(Best&&Best->Time>=T.Time))return;
                const double X=T.X-Threat.State.PosX,Y=T.Y-Threat.State.PosY,D=FMath::Sqrt(X*X+Y*Y);
                if(D<.5||(X*Threat.State.HeadX+Y*Threat.State.HeadY)/D<A.Ctx->Sim.ThreatCfg.PredFovCos||!ClearLine(T.X,T.Y,T.Z))return;
                Best=&T;
            });
            if(Best){I.Trace=I.LastUsed=Best->Id;I.X=Best->X;I.Y=Best->Y;I.Started=I.LastProgress=Now;I.Until=FMath::Min(Now+12,Best->Time+20);I.BestDistance=MAX_dbl;I.Role=EcoTracesV3::ERole::Investigate;}
        }
        if(I.Trace){const double X=I.X-Threat.State.PosX,Y=I.Y-Threat.State.PosY,D=FMath::Sqrt(X*X+Y*Y);
            Input.bPackHelp=true;Input.bPackWait=false;Input.PackDirX=X/FMath::Max(.01,D);Input.PackDirY=Y/FMath::Max(.01,D);}
    }

	/** 이번 Step 배열의 색인 = HerbInts/WolfInts 색인 (BuildViews 가 같은 순서로 채운다). 통과하면 그 개체의 지면 높이를 갱신한다. */
	bool MoveOne(const FMoveAdapter& A, FEcoIntegratedV3Fragment& F, double FromX, double FromY, double ToX, double ToY)
	{
		++A.Ctx->TerrainChecks;
		double Z = F.GroundZ;
        const float Radius=A.Ctx->Sim.Config.bEcosystemLife&&F.Individual.bInitialized?float(30*F.Individual.BodyScale(A.Ctx->Sim.T*EcoRepertoireV3::kStepSeconds)):30.f;
		const bool bOk = A.Sub->TraceMove(A.RegionId, A.Ctx->UnitsToCm(FromX, FromY, F.GroundZ), A.Ctx->UnitsToCm(ToX, ToY, F.GroundZ), Z,false,Radius);
		if (bOk)
		{
			F.GroundZ = Z;
		}
		else
		{
			++F.BlockedMoves;
		}
		return bOk;
	}

    bool ContactAllowsMove(const FMoveAdapter& A,int32 Index,const EcoWorldV3::FVec2& From,const EcoWorldV3::FVec2& To)
    {
        if(!A.Ctx->Sim.Config.bEcosystemLife)return true;
        namespace R=EcoRepertoireV3;const auto& D=(*A.Deer)[(*A.Rows)[Index]];
        const double Now=A.Ctx->Sim.T*R::kStepSeconds;
        const FIntPoint Center(FMath::FloorToInt((From.X+A.Ctx->OriginCm.X/R::kUnitCm)/2),FMath::FloorToInt((From.Y+A.Ctx->OriginCm.Y/R::kUnitCm)/2));
        int32 Visited=0;
        for(int32 Y=-1;Y<=1;++Y)for(int32 X=-1;X<=1;++X)if(const auto* Bucket=A.BodyBuckets.Find(Center+FIntPoint(X,Y)))
            for(const int32 Row:*Bucket){
                if(Visited++>=64)break;const auto& Other=(*A.Deer)[Row];if(Other.Id==D.Id)continue;
                const auto* Context=A.Sub->GetContext(Other.Int->ContextIndex);if(!Context)continue;
                const R::FVec2 Q{Other.View.Body->Pos.X+(Context->OriginCm.X-A.Ctx->OriginCm.X)/R::kUnitCm,
                    Other.View.Body->Pos.Y+(Context->OriginCm.Y-A.Ctx->OriginCm.Y)/R::kUnitCm};
                // Same 30cm scaled body radius as the terrain movement writer.
                const double Clearance=30*(D.Int->Individual.BodyScale(Now)+Other.Int->Individual.BodyScale(Now))/R::kUnitCm;
                if(!EcoLifeMotion::AllowsMotion(From,To,Q,Clearance)){++D.Int->Individual.ContactBlockedSteps;return false;}
            }
        return true;
    }

	bool HerbMoveHook(void* User, int32 Index, const EcoWorldV3::FVec2& From, const EcoWorldV3::FVec2& To)
	{
		const FMoveAdapter& A = *static_cast<const FMoveAdapter*>(User);
		if (!A.HerbInts || !A.HerbInts->IsValidIndex(Index))
		{
			return true;
		}
        if(!ContactAllowsMove(A,Index,From,To))return false;
        if(Traveling(User,Index)){
            auto& F=*(*A.HerbInts)[Index];double Z=F.GroundZ;
            const float Radius=A.Ctx->Sim.Config.bEcosystemLife&&F.Individual.bInitialized?float(30*F.Individual.BodyScale(A.Ctx->Sim.T*EcoRepertoireV3::kStepSeconds)):30.f;
            const bool Ok=A.Sub->TraceMove(A.RegionId,A.Ctx->UnitsToCm(From.X,From.Y,Z),A.Ctx->UnitsToCm(To.X,To.Y,Z),Z,true,Radius);
            if(Ok)F.GroundZ=Z;else ++F.BlockedMoves;return Ok;
        }
		return MoveOne(A, *(*A.HerbInts)[Index], From.X, From.Y, To.X, To.Y);
	}

	bool ThreatMoveHook(void* User, int32 Index, double FromX, double FromY, double ToX, double ToY)
	{
		const FMoveAdapter& A = *static_cast<const FMoveAdapter*>(User);
		if (!A.WolfInts || !A.WolfInts->IsValidIndex(Index))
		{
			return true;
		}
		return MoveOne(A, *(*A.WolfInts)[Index], FromX, FromY, ToX, ToY);
	}

	// 비축으로 사는 사슴의 Vitals 에너지 거울 하한 (0~1 비율). 화면 0% 로 보인다
	constexpr double kReserveMirrorFloor = 1.0e-3;

	float EnergyMirror(const EcoWorldV3::FHerbBody& B, const FEcoVitalsFragment& V)
	{
		// v3 에너지 E (0~1) × MaxEnergy — 조정자 요약(AverageEnergy)·표현 Energy 가 같은 척도로 읽는다
		// 야생 (w1) 지방 비축: 배(E)가 0 이어도 비축이 남은 산 사슴은 살아 있다. 팀 사슴 HP 감소(Vitals.Energy ≤ 0 이면 초당 HP −5,
		// Creature/Runtime/EcoCreatureIntegrationSpawner)가 v3 의 굶음 판정(C6: 배·비축 모두 0)보다 먼저 죽이지 않게 거울 값을 아주 작은 양수로 둔다.
		// 죽음은 지금처럼 v3 DeathCause → HP 0 한 길로만 넘긴다
		const double E = FMath::Clamp(B.Energy, 0.0, 1.0);
		const bool bLivingOnReserve = E <= 0.0 && B.Reserve > 0.0 && B.DeathCause == EcoWorldV3::kDeathNone;
		return static_cast<float>(bLivingOnReserve ? kReserveMirrorFloor : E) * V.MaxEnergy;
	}

	/** 산 사슴(List = Deer 색인) 에너지 평균·굶주림 수 → 컨텍스트 (먹기 표시·기록). */
	void TallyEnergy(FEcoV3RegionContext& Ctx, const TArray<FEcoV3DeerRec>& Deer, const TArray<int32>& List)
	{
		double Sum = 0.0;
		int32 Starving = 0;
		for (const int32 k : List)
		{
			const double E = FMath::Clamp(Deer[k].View.Body->Energy, 0.0, 1.0);
			Sum += E;
			Starving += E < EcoV3Integrated::kStarvingEnergy ? 1 : 0;
		}
		Ctx.MeanEnergy = List.IsEmpty() ? 0.0 : Sum / static_cast<double>(List.Num());
		Ctx.StarvingDeer = Starving;
		// 야생 (w1) 지방 비축 (켠 세계만): 비축 평균·최소, 비축으로 사는 사슴(배 0), 비축 바닥 가까움, 약함
		Ctx.MeanReserve = Ctx.MinReserve = 0.0;
		Ctx.OnReserveDeer = Ctx.LowReserveDeer = Ctx.WeakDeer = 0;
		if (Ctx.Sim.Config.WildReserve.bEnabled && !List.IsEmpty())
		{
			double RSum = 0.0;
			double RMin = 1.0;
			for (const int32 k : List)
			{
				const EcoWorldV3::FHerbBody& B = *Deer[k].View.Body;
				RSum += B.Reserve;
				RMin = FMath::Min(RMin, B.Reserve);
				Ctx.OnReserveDeer += B.Energy <= 0.0 ? 1 : 0;
				Ctx.LowReserveDeer += B.Reserve < EcoV3Integrated::kLowReserve ? 1 : 0;
				Ctx.WeakDeer += B.bWeak ? 1 : 0;
			}
			Ctx.MeanReserve = RSum / static_cast<double>(List.Num());
			Ctx.MinReserve = RMin;
		}
	}

	/**
	 * 경계 거리 기록 (사람 결정 10-15 (C), 규칙 켬·끔 모두 센다): 이 스텝 끝 산 사슴 중 식사 중(쿨다운 > 0)이고 깨어 있는 늑대의
	 * 15 m(kNearEatingWolfUnits) 안에 있는 사슴 수 → 컨텍스트 누적 (개체·스텝). 기록 전용.
	 */
	void TallyNearEatingWolves(FEcoV3RegionContext& Ctx, const TArray<FEcoV3DeerRec>& Deer, const TArray<int32>& DeerList,
							   const TArray<FEcoV3WolfRec>& Wolves, const TArray<int32>& WolfList)
	{
		const double R2 = EcoV3Integrated::kNearEatingWolfUnits * EcoV3Integrated::kNearEatingWolfUnits;
		for (const int32 k : DeerList)
		{
			const EcoWorldV3::FVec2 P = Deer[k].View.Body->Pos;
			for (const int32 w : WolfList)
			{
				const EcoWorldV3::FThreatAgent& A = *Wolves[w].Agent;
				if (A.State.Cooldown <= 0 || EcoWorldV3::ThreatAsleepNow(Ctx.Sim, A))
				{
					continue;
				}
				const double Dx = A.State.PosX - P.X;
				const double Dy = A.State.PosY - P.Y;
				if (Dx * Dx + Dy * Dy <= R2)
				{
					++Ctx.NearEatingDeerSteps;
					break;
				}
			}
		}
	}

	/**
	 * 10-27 쉬는 늑대 시야 기록 (측정 전용 — 거리 두기 규칙 켬·끔 모두 센다): 이 스텝 끝 산 사슴 가운데 쉬는 늑대(죽지 않았고 깨어 있고 사냥 중이 아님)의 시야(WolfViewNow) 안이고
	 * 눈길이 트였고(EyeClear) 은신처 밖이며 경계 거리(AlertR) 안에 사냥 중인 늑대가 없는 사슴 → 컨텍스트 누적 (개체·스텝), 그중 이번 스텝 이동이 0.001 단위
	 * 밑이면 '멈춤'. 측정 도구(scratch measure_calm.py 의 rest_exposed·rest_exposed_stopped)와 같은 뜻이다 (그쪽은 스텝 앞 자리, 여기는 스텝 끝 자리).
	 */
	void TallyRestWolfView(FEcoV3RegionContext& Ctx, const TArray<FEcoV3DeerRec>& Deer, const TArray<int32>& DeerList,
						   const TArray<FEcoV3WolfRec>& Wolves, const TArray<int32>& WolfList)
	{
		namespace WD = EcoWorldV3::Detail;
		const EcoWorldV3::FWorldState& W = Ctx.Sim;
		const double View = EcoWorldV3::WolfViewNow(W);
		const double View2 = View * View;
		const double AlertR2 = W.Config.WildFlight.AlertR * W.Config.WildFlight.AlertR;
		for (const int32 k : DeerList)
		{
			const EcoWorldV3::FHerbView& V = Deer[k].View;
			const EcoWorldV3::FHerbBody& B = *V.Body;
			if (B.DeathCause != EcoWorldV3::kDeathNone)
			{
				continue;
			}
			++Ctx.RestViewLiveSteps;
			if (V.Perception->Cover.bInCover)
			{
				continue;
			}
			bool bInView = false;
			bool bNearHunt = false;
			for (const int32 w : WolfList)
			{
				const EcoWorldV3::FThreatAgent& A = *Wolves[w].Agent;
				if (A.bDead)
				{
					continue;
				}
				const double Dx = A.State.PosX - B.Pos.X;
				const double Dy = A.State.PosY - B.Pos.Y;
				const double D2 = Dx * Dx + Dy * Dy;
				if (WD::FlightHunting(W, A))
				{
					bNearHunt = bNearHunt || D2 <= AlertR2;
				}
				else if (!bInView && D2 <= View2 && !EcoWorldV3::ThreatAsleepNow(W, A) && WD::EyeClear(W, B.Pos, A.State.PosX, A.State.PosY))
				{
					bInView = true;
				}
			}
			if (bInView && !bNearHunt)
			{
				++Ctx.RestViewDeerSteps;
				const double Mx = B.Pos.X - B.PrevPos.X;
				const double My = B.Pos.Y - B.PrevPos.Y;
				Ctx.RestViewStopSteps += Mx * Mx + My * My < 1e-6 ? 1 : 0;
			}
		}
	}
}

// -----------------------------------------------------------------------------
// UEcoPolicyV3IntegratedStepProcessor
// -----------------------------------------------------------------------------

UEcoPolicyV3IntegratedStepProcessor::UEcoPolicyV3IntegratedStepProcessor()
	: DeerQuery(*this)
	, WolfQuery(*this)
{
	// 논리 상태는 서버·단독에만 있다 (AGENTS.md 2절 2항)
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
    ExecutionOrder.ExecuteInGroup=UE::Mass::ProcessorGroupNames::Movement;
    ExecutionOrder.ExecuteAfter.Add(UEcoShelterLifecycleProcessor::StaticClass()->GetFName());

	// 지역 세계(서브시스템)를 함께 쓰고, 지형 제약에서 물리 질의를 부른다
	bRequiresGameThreadExecution = true;
}

void UEcoPolicyV3IntegratedStepProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
    DeerQuery.AddRequirement<FEcoSocialMovementRequestFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    DeerQuery.AddRequirement<FEcoAlarmStateFragment>(EMassFragmentAccess::ReadOnly,EMassFragmentPresence::Optional);
    DeerQuery.AddRequirement<FEcoShelterMovementFeedbackFragment>(EMassFragmentAccess::ReadWrite,EMassFragmentPresence::Optional);
    DeerQuery.AddRequirement<FEcoV3SocialBridgeFragment>(EMassFragmentAccess::ReadWrite,EMassFragmentPresence::Optional);
    DeerQuery.AddRequirement<FEcoHerdTravelFragment>(EMassFragmentAccess::ReadWrite,EMassFragmentPresence::Optional);

	DeerQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoDeathFragment>(EMassFragmentAccess::ReadWrite, EMassFragmentPresence::Optional);
	DeerQuery.AddRequirement<FEcoCreatureLifecycleFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoBehaviorStateFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoPerceptionCacheFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoControlOutFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::All);
	DeerQuery.AddTagRequirement<FEcoIntegratedThreatV3Tag>(EMassFragmentPresence::None);
	DeerQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EcoPolicyV3IntegratedProcImpl::ExcludeOtherWriters(DeerQuery);

	WolfQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadWrite);
    WolfQuery.AddRequirement<FEcoDeathFragment>(EMassFragmentAccess::ReadWrite,EMassFragmentPresence::Optional);
	WolfQuery.AddRequirement<FEcoCreatureLifecycleFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FEcoThreatStateFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FEcoPredatorStateFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddTagRequirement<FEcoIntegratedThreatV3Tag>(EMassFragmentPresence::All);
	WolfQuery.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::None);
	WolfQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EcoPolicyV3IntegratedProcImpl::ExcludeOtherWriters(WolfQuery);
}

void UEcoPolicyV3IntegratedStepProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
    auto* World = GetWorld();
    auto* Sub = World ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
    if (!Sub || !Sub->IsActive() || Sub->UsesAuthorityBoundaries()) return;
    ExecuteSteps(EntityManager, Context, Sub->AdvanceClock(Context.GetDeltaTimeSeconds()), World->GetTimeSeconds(), -1.);
}

void UEcoPolicyV3IntegratedStepProcessor::ExecuteAuthorityBoundary(FMassEntityManager& EntityManager,
    FMassExecutionContext& Context, double WorldSeconds, double AuthoritySeconds)
{
    ExecuteSteps(EntityManager, Context, 1, WorldSeconds, AuthoritySeconds);
}

void UEcoPolicyV3IntegratedStepProcessor::ExecuteSteps(FMassEntityManager& EntityManager, FMassExecutionContext& Context,
    int32 Steps, double Now, double AuthoritySeconds)
{
	using namespace EcoPolicyV3IntegratedProcImpl;
	UWorld* World = GetWorld();
	UEcoPolicyV3IntegratedSubsystem* Sub = World ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
	if (!Sub || !Sub->IsActive())
	{
		return;   // 스위치 끔 (기본): 아무것도 하지 않는다
	}
	// 전역 결정 시계 (평면 시험 경로의 시계와 따로). 컨텍스트가 생기기 전 스텝은 버린다
	const int32 NumCtx = Sub->NumContexts();
	if (NumCtx == 0)
	{
		return;
	}
	// 두뇌 바꾸기 (10-18, EcoV3Brain.h): 결정 스텝 경계 — 콘솔·폴더 감시·시작 두뇌로 대기 중인 두뇌를 여기서 바꾼다 (입양 첫 결정 앞)
	Sub->SyncBrain(/*bPollWatch*/ true);

	// --- 1. 모으기 (청크 순서는 아키타입·생성 순서에 따라 바뀌므로 StableAgentId 로 정렬한다) ---
	Deer.Reset();
	Wolves.Reset();
	DeerQuery.ForEachEntityChunk(Context, [this](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FEcoIdentityFragment> Ids = Ctx.GetFragmentView<FEcoIdentityFragment>();
        const auto Requests=Ctx.GetFragmentView<FEcoSocialMovementRequestFragment>();
        const auto Alarms=Ctx.GetFragmentView<FEcoAlarmStateFragment>();
        auto Feedback=Ctx.GetMutableFragmentView<FEcoShelterMovementFeedbackFragment>();
        auto SocialAudit=Ctx.GetMutableFragmentView<FEcoV3SocialBridgeFragment>();
        auto Journeys=Ctx.GetMutableFragmentView<FEcoHerdTravelFragment>();

		const TConstArrayView<FEcoRegionFragment> Regions = Ctx.GetFragmentView<FEcoRegionFragment>();
		const TConstArrayView<FTransformFragment> Xfs = Ctx.GetFragmentView<FTransformFragment>();
		const TArrayView<FEcoVitalsFragment> Vits = Ctx.GetMutableFragmentView<FEcoVitalsFragment>();
		const auto Deaths = Ctx.GetMutableFragmentView<FEcoDeathFragment>();
		const TArrayView<FEcoCreatureLifecycleFragment> Lives = Ctx.GetMutableFragmentView<FEcoCreatureLifecycleFragment>();
		const TArrayView<FEcoBehaviorStateFragment> States = Ctx.GetMutableFragmentView<FEcoBehaviorStateFragment>();
		const TArrayView<FEcoPerceptionCacheFragment> Percs = Ctx.GetMutableFragmentView<FEcoPerceptionCacheFragment>();
		const TArrayView<FEcoControlOutFragment> Ctrls = Ctx.GetMutableFragmentView<FEcoControlOutFragment>();
		const TArrayView<FEcoHerbivoreBodyV3Fragment> Bodies = Ctx.GetMutableFragmentView<FEcoHerbivoreBodyV3Fragment>();
		const TArrayView<FEcoIntegratedV3Fragment> Ints = Ctx.GetMutableFragmentView<FEcoIntegratedV3Fragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (Ids[i].SpeciesId != NativeDeerSpecies || Ids[i].StableAgentId <= 0 || Vits[i].HP <= 0.0f || Ints[i].bDead)
			{
				continue;   // 아직 정체성이 없거나, 이미 죽었다 (조정자가 Alive 를 떼고 지운다)
			}
			FEcoV3DeerRec& R = Deer.AddDefaulted_GetRef();
			R.Id = Ids[i].StableAgentId;
			R.Region = Regions[i].CurrentRegionId;
			R.Transform = &Xfs[i];
			R.Vitals = &Vits[i];
			R.Death = Deaths.IsEmpty() ? nullptr : &Deaths[i];
			R.Life = &Lives[i];
			R.State = &States[i];
			R.Int = &Ints[i];
			R.SocialRequest=Requests.IsEmpty()?nullptr:&Requests[i];
            R.Alarm=Alarms.IsEmpty()?nullptr:&Alarms[i];
            R.Feedback=Feedback.IsEmpty()?nullptr:&Feedback[i];
            R.SocialAudit=SocialAudit.IsEmpty()?nullptr:&SocialAudit[i];
            R.Journey=Journeys.IsEmpty()?nullptr:&Journeys[i];
            R.View.Rep = &States[i].Rep;
			R.View.Decision = &States[i].Decision;
			R.View.Body = &Bodies[i].Body;
			R.View.Perception = &Percs[i].Perception;
			R.View.Control = &Ctrls[i].Control;
		}
	});
	WolfQuery.ForEachEntityChunk(Context, [this](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FEcoIdentityFragment> Ids = Ctx.GetFragmentView<FEcoIdentityFragment>();
		const TConstArrayView<FEcoRegionFragment> Regions = Ctx.GetFragmentView<FEcoRegionFragment>();
		const TConstArrayView<FTransformFragment> Xfs = Ctx.GetFragmentView<FTransformFragment>();
		const auto Vits = Ctx.GetMutableFragmentView<FEcoVitalsFragment>();
        const auto Deaths=Ctx.GetMutableFragmentView<FEcoDeathFragment>();
		const TArrayView<FEcoCreatureLifecycleFragment> Lives = Ctx.GetMutableFragmentView<FEcoCreatureLifecycleFragment>();
		const TArrayView<FEcoThreatStateFragment> Agents = Ctx.GetMutableFragmentView<FEcoThreatStateFragment>();
		const TArrayView<FEcoIntegratedV3Fragment> Ints = Ctx.GetMutableFragmentView<FEcoIntegratedV3Fragment>();
		const TArrayView<FEcoPredatorStateFragment> Preds = Ctx.GetMutableFragmentView<FEcoPredatorStateFragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (Ids[i].SpeciesId != NativeWolfSpecies || Ids[i].StableAgentId <= 0 || Vits[i].HP <= 0.0f)
			{
				continue;
			}
			FEcoV3WolfRec& R = Wolves.AddDefaulted_GetRef();
			R.Id = Ids[i].StableAgentId;
			R.Region = Regions[i].CurrentRegionId;
			R.Transform = &Xfs[i];
			R.Life = &Lives[i];
			R.Agent = &Agents[i].Agent;
			R.Int = &Ints[i];
			R.PredState = &Preds[i];
            R.Vitals=&Vits[i];R.Death=Deaths.IsEmpty()?nullptr:&Deaths[i];
		}
	});
	Deer.Sort([](const FEcoV3DeerRec& A, const FEcoV3DeerRec& B) { return A.Id < B.Id; });
	Wolves.Sort([](const FEcoV3WolfRec& A, const FEcoV3WolfRec& B) { return A.Id < B.Id; });

	// --- 2. 지역별 목록 ---
	DeerByContext.SetNum(NumCtx);
	WolvesByContext.SetNum(NumCtx);
	for (int32 c = 0; c < NumCtx; ++c)
	{
		DeerByContext[c].Reset();
		WolvesByContext[c].Reset();
	}
	auto ContextOf = [this, Sub](const FEcoIntegratedV3Fragment& Int, FName Region) -> FEcoV3RegionContext*
	{
		FEcoV3RegionContext* Ctx = Int.bAdopted ? Sub->GetContext(Int.ContextIndex) : Sub->FindContext(Region);
		if (!Ctx && !ReportedMissingRegions.Contains(Region))
		{
			ReportedMissingRegions.Add(Region);
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 지역 %s 의 v3 무대가 없다 — 그 지역 개체는 서 있는다"), *Region.ToString());
		}
		return Ctx;
	};
	for (int32 k = 0; k < Deer.Num(); ++k)
	{
		if (FEcoV3RegionContext* Ctx = ContextOf(*Deer[k].Int, Deer[k].Region))
		{
			DeerByContext[Ctx->Index].Add(k);
		}
	}
	for (int32 k = 0; k < Wolves.Num(); ++k)
	{
		if (FEcoV3RegionContext* Ctx = ContextOf(*Wolves[k].Int, Wolves[k].Region))
		{
			WolvesByContext[Ctx->Index].Add(k);
		}
	}

    TArray<int64> StableViewIds;
	auto BuildViews = [this,&StableViewIds](int32 c)
	{
		Views.Reset();StableViewIds.Reset();
		HerbInts.Reset();
		ThreatPtrs.Reset();
		WolfInts.Reset();
		WolfIds.Reset();
		for (const int32 k : DeerByContext[c])
		{
			Views.Add(Deer[k].View);StableViewIds.Add(Deer[k].Id);
			HerbInts.Add(Deer[k].Int);
		}
		for (const int32 k : WolvesByContext[c])
		{
			ThreatPtrs.Add(Wolves[k].Agent);
			WolfInts.Add(Wolves[k].Int);
			WolfIds.Add(Wolves[k].Id);
		}
	};

    AEcoCreatureIntegrationSpawner* CombatOwner=nullptr;
    for(TActorIterator<AEcoCreatureIntegrationSpawner> It(World);It;++It)
        if(It->bUseV3Policy && It->bEnableEcosystemLife && It->IsRuntimeReady()) { CombatOwner=*It; break; }
    TArray<FEcoNoiseEvent> RecentNoises;
    if(auto* Noise=World->GetSubsystem<UEcoNoiseSubsystem>())Noise->GatherRecent(RecentNoises);
    for(int32 c=0;c<NumCtx;++c) {
        auto& Region=*Sub->GetContext(c);Region.Sim.ExternalThreats.clear();Region.PlayerSamples.clear();Region.PlayerEyeZ.Reset();Region.PlayerNoises.Reset();
        TArray<APawn*> Players;
        for(TActorIterator<APawn> It(World);It;++It)
            if(auto* Link=It->FindComponentByClass<UEcoPlayerEcologyComponent>();Link&&Link->bThreatEnabled&&It->IsPlayerControlled())
                if(const auto* State=It->GetPlayerState<AEcoPlayerState>();!State||State->IsAlive())Players.Add(*It);
        const FVector Center=Region.UnitsToCm(Region.SizeUnits*.5,Region.SizeUnits*.5,Region.OriginCm.Z);
        Players.Sort([&](const APawn& A,const APawn& B){
            const double DA=FVector::DistSquared2D(A.GetActorLocation(),Center),DB=FVector::DistSquared2D(B.GetActorLocation(),Center);
            return DA==DB?A.GetPathName()<B.GetPathName():DA<DB;
        });
        for(const auto* Player:Players) {
            if(Region.PlayerSamples.size()>=16)break;
            const auto P=Region.CmToUnits(Player->GetActorLocation());
            const FVector V=Player->GetVelocity()*EcoRepertoireV3::kStepSeconds/EcoRepertoireV3::kUnitCm;
            Region.PlayerSamples.push_back({P.X,P.Y,V.X,V.Y,false});
            FVector Eye;FRotator EyeRotation;Player->GetActorEyesViewPoint(Eye,EyeRotation);Region.PlayerEyeZ.Add(Eye.Z);
            if(!Region.Sim.Config.bEcosystemLife)Region.Sim.ExternalThreats.push_back(Region.PlayerSamples.back());
        }
        if(Region.Sim.Config.bEcosystemLife)for(int32 K=RecentNoises.Num()-1;K>=0&&Region.PlayerNoises.Num()<16;--K){
            const auto& Noise=RecentNoises[K];const auto* Pawn=Cast<APawn>(Noise.Instigator.Get());
            const auto* Bridge=Pawn?Pawn->FindComponentByClass<UEcoPlayerEcologyComponent>():nullptr;
            if(!EcoNoise::IsPlayerThreat(Noise.Tag)||!Pawn||!Pawn->IsPlayerControlled()||!Bridge||!Bridge->bThreatEnabled)continue;
            const double Age=Now-Noise.EmittedAt;if(Age<0||Age>UEcoNoiseSubsystem::EventLifetime)continue;
            const auto P=Region.CmToUnits(Noise.Position);
            Region.PlayerNoises.Add({uint64(Noise.Id),P.X,P.Y,Noise.Position.Z,FMath::Max(0.,Region.Sim.T*EcoRepertoireV3::kStepSeconds-Age),
                Noise.MaxRange*Noise.Loudness/EcoRepertoireV3::kUnitCm,Noise.Loudness,EcoNoise::IsPlayerShot(Noise.Tag)});
        }
    }
    // --- 3. 입양 (조정자가 막 만든 개체). 늑대 먼저 — 새 사슴의 첫 관측이 늑대를 보게 ---
	for (int32 c = 0; c < NumCtx; ++c)
	{
		FEcoV3RegionContext& Ctx = *Sub->GetContext(c);
		Sub->RefreshRefuges(Ctx);
		if (!Sub->IsActive()) return;
		for (const int32 k : WolvesByContext[c])
		{
			FEcoV3WolfRec& W = Wolves[k];
			if (W.Int->bAdopted)
			{
				continue;
			}
			const FTransform& Xf = W.Transform->GetTransform();
			const FVector Loc = Xf.GetLocation();
			const FVector Fwd = Xf.GetRotation().GetForwardVector();
			const EcoWorldV3::FVec2 P = Ctx.CmToUnits(Loc);
			// 종류 = 지역 안 순번 (StableAgentId 순, 짝수 잠행·홀수 추격). 밤잠 점진화의 늑대별 지연 해시 키는 StableAgentId 다
			// (파이썬은 세계 시드·위협 슬롯. 통합 모드는 지역들이 세션 시드 하나를 같이 쓰므로 순번을 쓰면 지역마다 지연이 똑같아진다)
			const EcoThreatV3::FThreatSpec Spec = EcoV3Integrated::WolfSpecForOrdinal(Ctx.AdoptedWolves++, Ctx.Sim.Config.PredSpeedMult);
			EcoWorldV3::AdoptThreat(Ctx.Sim, *W.Agent, Spec, P.X, P.Y, Fwd.X, Fwd.Y, W.Id);
			W.Int->bAdopted = true;
			W.Int->ContextIndex = Ctx.Index;
			W.Int->GroundZ = Loc.Z;
			W.Int->PrevGroundZ = Loc.Z;
		}
		NewRows.Reset();
		const TArray<int32>& List = DeerByContext[c];
		for (int32 r = 0; r < List.Num(); ++r)
		{
			FEcoV3DeerRec& D = Deer[List[r]];
			if (D.Int->bAdopted)
			{
				if(D.Int->bRefreshObservation){NewRows.Add(r);D.Int->bRefreshObservation=false;}
				continue;
			}
			const FTransform& Xf = D.Transform->GetTransform();
			const FVector Loc = Xf.GetLocation();
			const FVector Fwd = Xf.GetRotation().GetForwardVector();
			EcoWorldV3::AdoptHerb(Ctx.Sim, D.View, Ctx.CmToUnits(Loc), {Fwd.X, Fwd.Y}, EcoRepertoireV3::MakeAgentKeyFromStableId(D.Id),
                Ctx.Sim.Config.bEcosystemLife&&D.Int->Individual.Origin==EcoLifeV3::EOrigin::NaturalBirth);
			D.Int->bAdopted = true;
            if(auto* Migration=GetWorld()->GetSubsystem<UEcoHerdMigrationSubsystem>())Migration->RegisterResident(Ctx.RegionId,D.Id);
			D.Int->ContextIndex = Ctx.Index;
			D.Int->GroundZ = Loc.Z;
			D.Int->PrevGroundZ = Loc.Z;
			D.Vitals->Energy = EnergyMirror(*D.View.Body, *D.Vitals);
			++Ctx.AdoptedDeer;
			NewRows.Add(r);
		}
		if (!NewRows.IsEmpty())
		{
			BuildViews(c);
			EcoWorldV3::ObserveAndDecideRows(Ctx.Sim, Views.GetData(), Views.Num(), ThreatPtrs.GetData(), ThreatPtrs.Num(),
											 NewRows.GetData(), NewRows.Num(), Sub->ActiveNet());
			for (const int32 r : NewRows)
			{
				const FEcoV3DeerRec& D = Deer[List[r]];
				D.State->SyncSummary(*D.View.Control);
			}
		}
	}

	// --- 4. 결정 스텝: 모든 지역이 같은 전역 스텝 (계약 10-1) ---
	const double CpuStart = FPlatformTime::Seconds();
	for (int32 s = 0; s < Steps; ++s)
	{
		// 숲 자람 모드 (10-27, EcoV3ForestGrowth.cpp): 다 자랄 단계면 이 정확한 스텝에서 줄기 막이를 켜고 나무만 다시 읽는다 — 바로 아래 ApplyEnvChange 가 넣는다
		// (실시간 읽기 주기·프레임 나눔과 무관). 숲을 끄면 아무것도 하지 않는다
		Sub->ForestStepBoundary();
		// 환경 바뀜 (10-21 실시간 두뇌 교체, EcoV3EnvWatch.cpp): 레벨이 바꾼 나무·날씨를 이 경계(스텝 앞)에서 지역 세계에 넣는다 — 새 원판 안 산 사슴·늑대는
		// 밖으로 민다. 대기 변화가 없으면 아무것도 하지 않는다 (지금까지와 비트 단위로 같다)
		if (Sub->HasPendingEnvChange())
		{
#if UE_BUILD_SHIPPING
			Sub->ApplyEnvChange({}, {});
#else
			TArray<TArray<EcoWorldV3::FHerbBody*>> EnvBodies;
			TArray<TArray<EcoWorldV3::FThreatAgent*>> EnvAgents;
			EnvBodies.SetNum(NumCtx);
			EnvAgents.SetNum(NumCtx);
			for (int32 c = 0; c < NumCtx; ++c)
			{
				for (const int32 k : DeerByContext[c])
				{
					EnvBodies[c].Add(Deer[k].View.Body);
				}
				for (const int32 k : WolvesByContext[c])
				{
					EnvAgents[c].Add(Wolves[k].Agent);
				}
			}
			Sub->ApplyEnvChange(EnvBodies, EnvAgents);
#endif
		}
		// 전역 스텝 경계마다: 예정 바꾸기(eco.V3Brain.SwapAtSeconds)가 한 프레임 안의 정확한 스텝에서 걸리게. 이 스텝의 모든 지역이 같은 두뇌다
		Sub->SyncBrain(/*bPollWatch*/ false);
		// 환경 스냅숏 (10-18 적응 고리, EcoV3Snapshot.cpp): 예정 시각이면 이 스텝 앞 상태를 한 번 쓴다 (읽기만 — 세계를 바꾸지 않는다)
		Sub->MaybeScheduledSnapshot();
		// 자동·주기 스냅숏 (10-21): 환경 판이 가라앉은 뒤 판마다 한 번, eco.IntegratedV3.SnapshotEvery 주기 (읽기만)
		Sub->MaybeAutoSnapshot();
		const EcoPolicyV3::FPolicyNetV3& Net = Sub->ActiveNet();
		for (int32 c = 0; c < NumCtx; ++c)
		{
			FEcoV3RegionContext& Ctx = *Sub->GetContext(c);
			Sub->SyncContextClock(Ctx);
			if (Ctx.Sim.Food.Vegetation.bEnabled)
			{
				if (!Ctx.Sim.Food.HasValidVegetationLayout()) { Sub->RejectResourceContract(); return; }
				const auto* Regions = World->GetSubsystem<UEcologyWorldSubsystem>();
				const auto* Region = Regions ? Regions->GetRegion(Ctx.RegionId) : nullptr;
				if (!Region) { Sub->RejectResourceContract(); return; }
				const auto Input = Region->GetEffectiveEnvironmentState();
				auto& Weather = Ctx.Sim.Food.VegetationWeather;
				Weather = {Input.Rainfall, Input.Temperature, 1.0 - Ctx.Sim.Dark};
				if (!Weather.IsValid()) { Sub->RejectResourceContract(); return; }
			}
			BuildViews(c);
			// 두뇌 행동 몫 기록: 늑대를 앎 = 이 스텝 결정 관측(스텝 앞 기하)의 pred_count > 0 (FEcoV3BrainTally)
			KnowsPre.SetNumUninitialized(Views.Num());
			for (int32 r = 0; r < Views.Num(); ++r)
			{
				KnowsPre[r] = Views[r].Perception->Obs[EcoPolicyV3::kObsPredCount] > 0.0f ? 1 : 0;
			}
			for (FEcoIntegratedV3Fragment* Int : HerbInts)
			{
				Int->PrevGroundZ = Int->GroundZ;
			}
			for (FEcoIntegratedV3Fragment* Int : WolfInts)
			{
				Int->PrevGroundZ = Int->GroundZ;
			}
			FMoveAdapter Adapter;
			Adapter.Sub = Sub; Adapter.Combat=CombatOwner;
			Adapter.RegionId = Ctx.RegionId;
			Adapter.Ctx = &Ctx;
			Adapter.HerbInts = &HerbInts;
			Adapter.WolfInts = &WolfInts;
            Adapter.Deer=&Deer;Adapter.Rows=&DeerByContext[c];
            if(Ctx.Sim.Config.bEcosystemLife)for(int32 Row=0;Row<Deer.Num();++Row){
                Adapter.FamilyRows.Add(Deer[Row].Id,Row);
                const auto* BodyContext=Sub->GetContext(Deer[Row].Int->ContextIndex);if(!BodyContext)continue;
                const auto P=Deer[Row].View.Body->Pos;
                Adapter.BodyBuckets.FindOrAdd(FIntPoint(FMath::FloorToInt((P.X+BodyContext->OriginCm.X/EcoRepertoireV3::kUnitCm)/2),
                    FMath::FloorToInt((P.Y+BodyContext->OriginCm.Y/EcoRepertoireV3::kUnitCm)/2))).Add(Row);
            }
            Adapter.Shelters=World->GetSubsystem<UEcoShelterSubsystem>();Adapter.Now=Now;Adapter.AuthorityNow=AuthoritySeconds;
            Adapter.Journeys=World->GetSubsystem<UEcoHerdMigrationSubsystem>();
			EcoWorldV3::FStepHooks Hooks;
			Hooks.User = &Adapter;
			// 사슴 Social 행동 연결 (조연우 님 22eb1b6). eco.IntegratedV3.SocialControl 1 일 때만 건다 — 기본 0 (사람 결정 10-17 (8))
			Hooks.HerbControl = &IntegratedControlHook;
            Adapter.HerbIds=&StableViewIds;Adapter.WolfKeys=&WolfIds;
            Hooks.ThreatInput=&EvidenceThreatHook;
            Hooks.HerbTravel = &Traveling;
            Hooks.HerbMove = Sub->UsesTerrain() ? &HerbMoveHook : nullptr;
            Hooks.ThreatMove = Sub->UsesTerrain() ? &ThreatMoveHook : nullptr;
			const double BeforeFood = Ctx.Sim.Food.Total();
			const double BeforeEaten = Ctx.Sim.Stats.FoodEaten;
			const double BeforeLoss = Ctx.Sim.Food.EnvironmentLost;
			const double BeforeGrowth = Ctx.Sim.Food.VegetationGrown;
			// 10-24 두 길 두뇌 (기록만): 이 스텝에 실행한 반사 길 RUN·SHELTER 사슴-스텝 = 세계 길 통계의 스텝 차 (길 끔이면 늘 0)
			const int64 RouteRun0 = Ctx.Sim.Stats.Route.Steps[EcoWorldV3::kRouteRun];
			const int64 RouteShelter0 = Ctx.Sim.Stats.Route.Steps[EcoWorldV3::kRouteShelter];
			const EcoWorldV3::FStepReport Report = EcoWorldV3::Step(Ctx.Sim, Views.GetData(), Views.Num(), ThreatPtrs.GetData(),
																	ThreatPtrs.Num(), Net, &Hooks);
			{
				const int64 RunD = Ctx.Sim.Stats.Route.Steps[EcoWorldV3::kRouteRun] - RouteRun0;
				const int64 ShelterD = Ctx.Sim.Stats.Route.Steps[EcoWorldV3::kRouteShelter] - RouteShelter0;
				Ctx.BrainTally.AddRoute(RunD, ShelterD);
				Ctx.SinceSwapBrainTally.AddRoute(RunD, ShelterD);
				Ctx.RouteTally.Push(Ctx.Sim.Stats.Route);   // 최근 60 초 창 (결정 스텝마다 한 번 — 길 끔이어도 넣어 창이 시각과 맞는다)
			}
			// R5 장애물 관측 대조 기록 (eco.IntegratedV3.ObsParityLog — 기본 끔): 이 스텝 끝 관측의 세 칸과 그 입력 (읽기만)
			Sub->LogObsParity(Ctx, Views.GetData(), StableViewIds.GetData(), Views.Num());
			// 야생 (w3) 도망 기록 (10-21, 기록만): 이 스텝 뒤 열린 도망 합 — 10초 기록 줄·스냅숏 보고의 잘림 (이번 스텝에 죽은 사슴의 도망은 Step 이 이미 닫았다)
			if (Ctx.FlightOn())
			{
				Ctx.FlightOpen = EcoWorldV3::FlightOpenOf(Views.GetData(), Views.Num());
			}

            // Feedback uses the integrated native body and ground result, never the desired slot or render Actor position.
            for(int32 R=0;R<DeerByContext[c].Num();++R) {
                const auto& D=Deer[DeerByContext[c][R]];
                if(!D.Feedback||!D.SocialAudit||!D.SocialRequest||D.SocialAudit->AppliedReservation<=0||D.View.Body->DeathCause!=EcoWorldV3::kDeathNone)continue;
                const auto& Request=*D.SocialRequest;
                const FVector Actual=Ctx.UnitsToCm(D.View.Body->Pos.X,D.View.Body->Pos.Y,D.Int->GroundZ);
                const bool Arrived=FVector::DistSquared(Actual,Request.TargetPosition)<=FMath::Square(Request.ArrivalRadius)
                    &&(!Ctx.Sim.Config.bProtectedRefuges||EcoRefugeV3::Contains(Ctx.Sim.Config.Covers,D.View.Body->Pos));
                D.Feedback->Report(D.SocialAudit->AppliedReservation,Arrived?EEcoShelterMovementStatus::Arrived:EEcoShelterMovementStatus::Moving);
            }

			// 먹기 기록: 이번 스텝에 먹이 칸에서 실제로 먹은 사슴을 구간마다 한 번 센다 (먹고 같은 스텝에 죽은 사슴도). 번식 표시 시각.
			// Views·HerbInts 는 이번 Step 배열과 같은 순서다 (아래 죽음 넘기기가 List 를 줄여도 이 둘은 그대로)
			for (int32 r = 0; r < Views.Num(); ++r)
			{
				const EcoWorldV3::FHerbBody& Body = *Views[r].Body;
				FEcoIntegratedV3Fragment& Int = *HerbInts[r];
                if(Ctx.Sim.Config.bEcosystemLife&&Body.DeathCause==EcoWorldV3::kDeathNone){
                    if(Ctx.Sim.Config.bNaturalHabitats&&Body.LastIntake>0){
                        const int32 Cell=Ctx.Sim.Food.CellOf(Body.Pos);
                        // Native's actual consumed cell is the authority. A mouth-side
                        // cue stays within it; no animation notify writes resources.
                        const double X=FMath::Clamp(Body.Pos.X+Body.Head.X*.35,(Cell%Ctx.Sim.Food.Gw)*Ctx.Sim.Food.Cell+.01,(Cell%Ctx.Sim.Food.Gw+1)*Ctx.Sim.Food.Cell-.01);
                        const double Y=FMath::Clamp(Body.Pos.Y+Body.Head.Y*.35,(Cell/Ctx.Sim.Food.Gw)*Ctx.Sim.Food.Cell+.01,(Cell/Ctx.Sim.Food.Gw+1)*Ctx.Sim.Food.Cell-.01);
                        Ctx.BrowseEvidence.Add(Cell,X,Y,Ctx.Sim.T*EcoRepertoireV3::kStepSeconds,Body.LastIntake);
                    }
                    auto& Life=Int.Individual;const double SimNow=Ctx.Sim.T*EcoRepertoireV3::kStepSeconds;
                    if(SimNow>=Life.NextTrace&&FMath::Square(Body.Pos.X-Body.PrevPos.X)+FMath::Square(Body.Pos.Y-Body.PrevPos.Y)>.01){
                        Life.NextTrace=SimNow+2;Ctx.MovementTraces.Add(StableViewIds[r],Body.Pos.X,Body.Pos.Y,Int.GroundZ,SimNow);
                    }
                }
				// 사슴 얼기 막음 확인: 요청을 읽은 결정의 마스크에 얼기 칸이 열렸는가 (eco.IntegratedV3.NoFreeze 1 이면 늘 0)
				const EcoWorldV3::FHerbDecision& Dec = *Views[r].Decision;
				Ctx.FreezeMaskOpen += (Dec.bCommittedReads && Dec.CommittedMask[EcoRepertoireV3::kFreeze] != 0) ? 1 : 0;
				// 두뇌 행동 몫: 이 스텝에 실제로 한 행동, 도주 반사(도주·웅크림 덮기)는 따로 (R4 situ_eval.py 와 같은 정의)
				const bool bReflex = Dec.KeepActive == EcoWorldV3::kKeepPanic || Dec.KeepActive == EcoWorldV3::kKeepShelter;
				Ctx.BrainTally.Add(Dec.ExecutedBehavior, KnowsPre[r] != 0, bReflex);
				Ctx.SinceSwapBrainTally.Add(Dec.ExecutedBehavior, KnowsPre[r] != 0, bReflex);
				if (Body.LastIntake > 0.0 && Int.AteLogEpoch != Ctx.LogEpoch)
				{
					Int.AteLogEpoch = Ctx.LogEpoch;
					++Ctx.AteDeerInterval;
				}
				if (Body.bReproduced)
				{
					Int.ReproducedStep = Ctx.Sim.T;
				}
			}

			// 죽음 넘기기: HP 0 (+ 잡힘이면 bPredated). 사망 처리·지역 피식 사건·2 초 뒤 삭제는 팀 조정자가 한다.
			// 목록에서 빼서 이 프레임의 다음 스텝부터는 움직이거나 먹거나 잡히거나 동족으로 세어지지 않게 한다
			TArray<int32>& List = DeerByContext[c];
			for (int32 r = List.Num() - 1; r >= 0; --r)
			{
				FEcoV3DeerRec& D = Deer[List[r]];
				const EcoWorldV3::FHerbBody& B = *D.View.Body;
				if (B.DeathCause == EcoWorldV3::kDeathNone)
				{
					continue;
				}
				D.Int->bDead = true;
				D.Int->DeathCause = static_cast<uint8>(B.DeathCause);
				D.Int->PrevGroundZ = D.Int->GroundZ;   // 시체는 죽은 자리에 멈춘다
				D.Vitals->HP = 0.0f;
				D.Vitals->Energy = EnergyMirror(B, *D.Vitals);
				D.Life->bPredated = B.DeathCause == EcoWorldV3::kDeathCaught;
                if (D.Death)
                {
                    D.Death->Cause = B.DeathCause == EcoWorldV3::kDeathCaught ? EEcoDeathCause::Predation : EEcoDeathCause::Starvation;
                    D.Death->PredatorStableAgentId = B.CaughtBy >= 0 && WolvesByContext[c].IsValidIndex(B.CaughtBy)
                        ? Wolves[WolvesByContext[c][B.CaughtBy]].Id : 0;
                }
				D.State->SyncSummary(*D.View.Control);
				if (B.DeathCause == EcoWorldV3::kDeathCaught)
				{
					Ctx.RecentCatches.Add({Ctx.UnitsToCm(B.DeathPos.X, B.DeathPos.Y, D.Int->GroundZ), Now});
				}
				List.RemoveAt(r);
			}
			// 늑대 표현 자리표시: 포획 뒤 쿨다운 → '먹는 중', 표적을 쫓으면 '추격 중' (팀 표현 깃발). 팀 표현은 '먹는 중' 깃발 + 속도 0
			// (식사 중 제자리, 사람 결정 10-15 (B))이면 '먹는 중' 동작을 보인다. 식사·이어 사냥 기록 (TallyWolfStep)
			for (const int32 k : WolvesByContext[c])
			{
				const EcoWorldV3::FThreatAgent& A = *Wolves[k].Agent;
                if(A.bDead){
                    Wolves[k].Int->bDead=true;Wolves[k].Int->DeathCause=EcoWorldV3::kDeathStarved;
                    Wolves[k].Vitals->HP=0;Wolves[k].Vitals->Energy=0;
                    if(Wolves[k].Death)Wolves[k].Death->Cause=EEcoDeathCause::Starvation;
                    continue;
                }
				Wolves[k].PredState->EatCooldown = static_cast<float>(A.State.Cooldown * EcoRepertoireV3::kStepSeconds);
                if(Ctx.Sim.Config.bEcosystemLife&&Wolves[k].Int->Individual.LastMeatIntake>0)Wolves[k].PredState->EatCooldown=FMath::Max(.2f,Wolves[k].PredState->EatCooldown);
				Wolves[k].Life->bPursuing = A.Last.bHunting && A.Last.bHasTarget;
                const int32 Target=A.Last.Target;
                if(A.Last.bHasTarget&&Views.IsValidIndex(Target)&&Views[Target].Body->DeathCause==EcoWorldV3::kDeathNone) {
                    auto& Snapshot=*Wolves[k].Int;const auto& Body=*Views[Target].Body;
                    Snapshot.LastSeenPreyPosition=Ctx.UnitsToCm(Body.Pos.X,Body.Pos.Y,HerbInts[Target]->GroundZ);
                    Snapshot.LastSeenPreyKey=StableViewIds[Target];Snapshot.LastSeenPreyTime=Now;
                }

				Ctx.TallyWolfStep(A, Wolves[k].Id, Ctx.Sim.T - 1);
			}
			TallyNearEatingWolves(Ctx, Deer, List, Wolves, WolvesByContext[c]);   // 경계 거리 기록 (규칙 켬·끔 모두)
			TallyRestWolfView(Ctx, Deer, List, Wolves, WolvesByContext[c]);       // 10-27 쉬는 늑대 시야 기록 (측정 전용, 거리 두기 켬·끔 모두)
			TallyEnergy(Ctx, Deer, List);   // 기록 줄이 이 스텝 끝 에너지를 쓴다
			Sub->NotifyNightStep(Ctx, ThreatPtrs.GetData(), WolfIds.GetData(), ThreatPtrs.Num());   // 늑대 밤잠 사건 줄 (켠 세계만)
			Sub->NotifyContextStep(Ctx, Report);
            if (Ctx.bSpatialFoodRegistered)
            {
                const double AfterFood = Ctx.Sim.Food.Total();
                const double Eaten = Ctx.Sim.Stats.FoodEaten - BeforeEaten;
				const double Lost = Ctx.Sim.Food.EnvironmentLost - BeforeLoss;
				const double Grown = Ctx.Sim.Food.Vegetation.bEnabled ? Ctx.Sim.Food.VegetationGrown - BeforeGrowth : AfterFood - BeforeFood + Eaten;
                auto* Ecology = World->GetSubsystem<UEcologySimulationSubsystem>();
                if (!Ecology || !Ecology->CommitSpatialFood(Ctx.RegionId, ++Ctx.ResourceReceiptSequence, BeforeFood, Eaten, Grown, AfterFood, Lost))
                { UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] Resource conservation receipt rejected: %s"), *Ctx.RegionId.ToString()); Sub->RejectResourceContract(); return; }
            }
		}
		Sub->FinishGlobalStep();
	}
	if (Steps > 0)
	{
		Sub->AddStepCpuSeconds(FPlatformTime::Seconds() - CpuStart, Steps);
	}

	// --- 5. 에너지 거울, 요약 칸, 지역 집계 ---
	for (int32 c = 0; c < NumCtx; ++c)
	{
		FEcoV3RegionContext& Ctx = *Sub->GetContext(c);
		FMemory::Memzero(Ctx.BehaviorNow, sizeof(Ctx.BehaviorNow));
		FMemory::Memzero(Ctx.WolvesNow, sizeof(Ctx.WolvesNow));
		FMemory::Memzero(Ctx.KeepNow, sizeof(Ctx.KeepNow));
		FMemory::Memzero(Ctx.RouteNow, sizeof(Ctx.RouteNow));
		for (const int32 k : DeerByContext[c])
		{
			FEcoV3DeerRec& D = Deer[k];
			D.Vitals->Energy = EnergyMirror(*D.View.Body, *D.Vitals);
			D.State->SyncSummary(*D.View.Control);
			const int32 B = D.View.Rep->Behavior;
			if (B >= 0 && B < EcoRepertoireV3::kNumBehaviors)
			{
				++Ctx.BehaviorNow[B];
			}
			const int32 Km = D.View.Decision->KeepActive;   // 경계 거리 덮기 (규칙을 끄면 늘 0)
			if (Km >= 0 && Km < EcoWorldV3::kNumKeepModes)
			{
				++Ctx.KeepNow[Km];
			}
			// 10-24 두 길 두뇌: 다음 스텝 도주 덮기 사슴의 고른 길 (길 결정 스텝은 두뇌가 고른 칸 — 다음 A 가 적용한다, EcoV3Integrated::ShownRoute)
			const int32 Rt = EcoV3Integrated::ShownRoute(*D.View.Decision);
			if (D.View.Decision->KeepMode == EcoWorldV3::kKeepPanic && (Rt == EcoWorldV3::kRouteRun || Rt == EcoWorldV3::kRouteShelter))
			{
				++Ctx.RouteNow[Rt == EcoWorldV3::kRouteRun ? 0 : 1];
			}
		}
		WolvesByContext[c].RemoveAll([&](int32 K){return Wolves[K].Agent->bDead;});
		for (const int32 k : WolvesByContext[c])
		{
            if(Ctx.Sim.Config.bEcosystemLife)Wolves[k].Vitals->Energy=float(Wolves[k].Int->Individual.Nutrition)*Wolves[k].Vitals->MaxEnergy;
			++Ctx.WolvesNow[static_cast<int32>(EcoV3Integrated::WolfStateOf(*Wolves[k].Agent, Ctx.Sim.ThreatCfg))];
		}
		Ctx.AliveDeer = DeerByContext[c].Num();
		Ctx.Wolves = WolvesByContext[c].Num();
		TallyEnergy(Ctx, Deer, DeerByContext[c]);   // 스텝이 없는 프레임(입양만)에도 화면 집계가 맞게
	}
}

// -----------------------------------------------------------------------------
// UEcoPolicyV3IntegratedVisualProcessor
// -----------------------------------------------------------------------------

UEcoPolicyV3IntegratedVisualProcessor::UEcoPolicyV3IntegratedVisualProcessor()
	: DeerQuery(*this)
	, WolfQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteInGroup=UE::Mass::ProcessorGroupNames::Movement;
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPolicyV3IntegratedStepProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPolicyV3IntegratedVisualProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	// Alive 를 요구하지 않는다 — 죽은 개체도 조정자가 지울 때까지 죽은 자리에 멈춰 있어야 한다
	DeerQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FEcoBehaviorStateFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::All);
	DeerQuery.AddTagRequirement<FEcoIntegratedThreatV3Tag>(EMassFragmentPresence::None);
	EcoPolicyV3IntegratedProcImpl::ExcludeOtherWriters(DeerQuery);

	WolfQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FEcoThreatStateFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddTagRequirement<FEcoIntegratedThreatV3Tag>(EMassFragmentPresence::All);
	WolfQuery.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::None);
	EcoPolicyV3IntegratedProcImpl::ExcludeOtherWriters(WolfQuery);
}

void UEcoPolicyV3IntegratedVisualProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
    const auto* World = GetWorld();
    const auto* Sub = World ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
    if (!Sub || Sub->UsesAuthorityBoundaries()) return;
    PublishTransforms(EntityManager, Context, false);
}

void UEcoPolicyV3IntegratedVisualProcessor::PublishAuthorityBoundary(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
    PublishTransforms(EntityManager, Context, true);
}

void UEcoPolicyV3IntegratedVisualProcessor::PublishTransforms(FMassEntityManager& EntityManager,
    FMassExecutionContext& Context, bool bAuthorityBoundary)
{
	UWorld* World = GetWorld();
	UEcoPolicyV3IntegratedSubsystem* Sub = World ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
	if (!Sub || !Sub->IsActive() || Sub->NumContexts() == 0)
	{
		return;
	}
	const double Alpha = bAuthorityBoundary ? 1.0 : FMath::Clamp(static_cast<double>(Sub->GetVisualAlpha()), 0.0, 1.0);
	const bool bDebug = UEcoPolicyV3IntegratedSubsystem::IsDebugDrawEnabled();
	const double K = EcoRepertoireV3::kUnitCm / EcoRepertoireV3::kStepSeconds;   // 단위/스텝 → cm/s
	const int64 NowStep = Sub->GetGlobalStep();
	const bool bReserveOn = Sub->GetSettings().bWildReserve;   // 야생 (w1) 지방 비축 글자 (모든 지역이 같은 설정)

	DeerQuery.ForEachEntityChunk(Context, [Sub, Alpha, bDebug, K, World, NowStep, bReserveOn](FMassExecutionContext& Ctx)
	{
		const auto Ids = Ctx.GetFragmentView<FEcoIdentityFragment>();
		const TArrayView<FTransformFragment> Xfs = Ctx.GetMutableFragmentView<FTransformFragment>();
		const TArrayView<FMassVelocityFragment> Vels = Ctx.GetMutableFragmentView<FMassVelocityFragment>();
		const TConstArrayView<FEcoHerbivoreBodyV3Fragment> Bodies = Ctx.GetFragmentView<FEcoHerbivoreBodyV3Fragment>();
		const TConstArrayView<FEcoBehaviorStateFragment> States = Ctx.GetFragmentView<FEcoBehaviorStateFragment>();
		const TConstArrayView<FEcoIntegratedV3Fragment> Ints = Ctx.GetFragmentView<FEcoIntegratedV3Fragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const FEcoIntegratedV3Fragment& Int = Ints[i];
			const FEcoV3RegionContext* Rc = Int.bAdopted ? Sub->GetContext(Int.ContextIndex) : nullptr;
			if (!Rc || Ids[i].SpeciesId != EcoPolicyV3IntegratedProcImpl::NativeDeerSpecies)
			{
				continue;   // 아직 입양 전 — 조정자가 놓은 자리 그대로
			}
			const EcoWorldV3::FHerbBody& B = Bodies[i].Body;
			const double A = Int.bDead ? 1.0 : Alpha;
			const FVector Loc = Rc->UnitsToCm(B.PrevPos.X + (B.Pos.X - B.PrevPos.X) * A, B.PrevPos.Y + (B.Pos.Y - B.PrevPos.Y) * A,
											  Int.PrevGroundZ + (Int.GroundZ - Int.PrevGroundZ) * A);
			FTransform& Xf = Xfs[i].GetMutableTransform();
			Xf.SetLocation(Loc);
			if (B.Head.X != 0.0 || B.Head.Y != 0.0)
			{
				Xf.SetRotation(EcoHeading::YawQuatFromDir(FVector(B.Head.X, B.Head.Y, 0.0)));
			}
			Vels[i].Value = Int.bDead ? FVector::ZeroVector : FVector((B.Pos.X - B.PrevPos.X) * K, (B.Pos.Y - B.PrevPos.Y) * K, 0.0);
			if (bDebug)
			{
				const EcoRepertoireV3::FRepState& Rep = States[i].Rep;
				FString Label;
				FColor Color;
				if (Int.bDead)
				{
					Label = Int.DeathCause == EcoWorldV3::kDeathCaught ? TEXT("잡힘") : Int.DeathCause == EcoWorldV3::kDeathStarved ? TEXT("굶음") : TEXT("외부 피해");
					Color = FColor(120, 120, 120);
				}
				else
				{
					// 행동 + 에너지 % (+ 이번 결정 스텝에 먹은 몫, 굶주림, 번식) — EcoV3Integrated::DeerLabel
					// 팀 시계에 다시 맞추면 전역 스텝이 뒤로 갈 수 있다 — 음수 경과는 표시하지 않는다
					const int64 SinceRepro = NowStep - Int.ReproducedStep;
					const bool bRecentRepro = Int.ReproducedStep >= 0 && SinceRepro >= 0 && SinceRepro <= EcoV3Integrated::kReproMarkSteps;
					// 도주 반사 덮기 중이면 '경계(먹으며 멀어짐)'·'도주(안전해질 때까지)'·'웅크림(은신처·경계)' (야생 w3). 10-24 두 길 두뇌면 도주 글자가
					// 고른 길 '도주(트인 쪽)'·'도주(은신처)' (길 끈 두뇌는 Route 가 늘 NONE 이라 지금 그대로)
					Label = EcoV3Integrated::DeerLabel(Rep, B, bRecentRepro, Color, States[i].Decision.KeepActive,
													   bReserveOn, EcoV3Integrated::ShownRoute(States[i].Decision));
				}
				DrawDebugString(World, Loc + FVector(0.0, 0.0, 230.0), Label, nullptr, Color, 0.0f, true, 1.1f);
			}
		}
	});

	WolfQuery.ForEachEntityChunk(Context, [Sub, Alpha, bDebug, K, World](FMassExecutionContext& Ctx)
	{
		const auto Ids = Ctx.GetFragmentView<FEcoIdentityFragment>();
		const TArrayView<FTransformFragment> Xfs = Ctx.GetMutableFragmentView<FTransformFragment>();
		const TArrayView<FMassVelocityFragment> Vels = Ctx.GetMutableFragmentView<FMassVelocityFragment>();
		const TConstArrayView<FEcoThreatStateFragment> Agents = Ctx.GetFragmentView<FEcoThreatStateFragment>();
		const TConstArrayView<FEcoIntegratedV3Fragment> Ints = Ctx.GetFragmentView<FEcoIntegratedV3Fragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const FEcoIntegratedV3Fragment& Int = Ints[i];
			const FEcoV3RegionContext* Rc = Int.bAdopted ? Sub->GetContext(Int.ContextIndex) : nullptr;
			if (!Rc || Ids[i].SpeciesId != EcoPolicyV3IntegratedProcImpl::NativeWolfSpecies)
			{
				continue;
			}
			const EcoWorldV3::FThreatAgent& Ag = Agents[i].Agent;
			const EcoThreatV3::FThreatState& S = Ag.State;
			const FVector Loc = Rc->UnitsToCm(Ag.PrevX + (S.PosX - Ag.PrevX) * Alpha, Ag.PrevY + (S.PosY - Ag.PrevY) * Alpha,
											  Int.PrevGroundZ + (Int.GroundZ - Int.PrevGroundZ) * Alpha);
			FTransform& Xf = Xfs[i].GetMutableTransform();
			Xf.SetLocation(Loc);
			if (S.HeadX != 0.0 || S.HeadY != 0.0)
			{
				Xf.SetRotation(EcoHeading::YawQuatFromDir(FVector(S.HeadX, S.HeadY, 0.0)));
			}
			Vels[i].Value = FVector((S.PosX - Ag.PrevX) * K, (S.PosY - Ag.PrevY) * K, 0.0);
			if (bDebug)
			{
				// '늑대 눕는 중 (추격형) 걸음 40%', '늑대 깨는 중', 못 누운 까닭 — EcoV3Integrated::WolfLabel
				FColor Color;
				const FString Label = EcoV3Integrated::WolfLabel(Ag, Rc->Sim.ThreatCfg, Rc->Sim.Dark, Color);
				DrawDebugString(World, Loc + FVector(0.0, 0.0, 260.0), Label, nullptr, Color, 0.0f, true, 1.2f);
			}
		}
	});
}

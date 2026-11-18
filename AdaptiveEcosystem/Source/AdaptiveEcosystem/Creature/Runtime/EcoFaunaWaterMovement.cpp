#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoFaunaDecision.h"
#include "Creature/Runtime/EcoFaunaSightChannel.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassMovementFragments.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "World/EcologyRegion.h"

using EcoFaunaDecision::FitsFaunaPrey;
using EcoFaunaDecision::HasClearSight;

namespace EcoFaunaDecision
{
    bool FitsFaunaPrey(const FEcoFaunaPreyRule& Rule, const FEcoFaunaSpecies& Hunter,
        const FEcoFaunaSpecies& Prey, const EcoLifeV3::FIndividual& HunterLife,
        const EcoLifeV3::FIndividual& PreyLife, const FEcoVitalsFragment& Health, double Now)
    {
        const auto Mass = [Now](const auto& Life, float AdultMass)
        {
            return AdultMass * FMath::Pow(Life.Genome.Size, 3.) * FMath::Lerp(.12, 1., Life.AgeFraction(Now));
        };
        const double MaturityLimit = Health.HP < .6f * Health.MaxHP ? Rule.MaxInjuredMaturity : Rule.MaxHealthyMaturity;
        return HunterLife.AgeFraction(Now) >= 1. && PreyLife.AgeFraction(Now) <= MaturityLimit
            && Mass(PreyLife, Prey.AdultMass) <= Rule.MaxPreyMassRatio * Mass(HunterLife, Hunter.AdultMass);
    }
    bool HasClearSight(const UWorld& World, const FVector& Start, const FVector& End,
        float EyeHeight, float TargetHeight)
    {
        FCollisionObjectQueryParams Occluders(ECC_WorldStatic);
        Occluders.AddObjectTypesToQuery(SightCoverChannel);
        return !World.LineTraceTestByObjectType(Start + FVector(0, 0, EyeHeight), End + FVector(0, 0, TargetHeight),
            Occluders, FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaSight)));
    }
}

void AEcoCreatureIntegrationSpawner::MoveFaunaWaterCarcass(FMassEntityManager& EM,
    FMassEntityHandle Entity, const FEcoFaunaSpecies& Profile, float Delta, double Now)
{
    const auto* Species = &Profile;
    auto* Fauna = &EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entity);
    const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
    const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
    auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform();
    auto& Velocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value;
    const FVector Position = Transform.GetLocation();
    const double Dt = FMath::Min(Delta, .1f);
    Velocity = FVector::ZeroVector;
    auto* Stock = FaunaCarcasses.Find(Id.StableAgentId);
    if (!Stock) return;
    const double Clearance = FMath::Max(1., Species->BodyRadius * Fauna->Life.BodyScale(Now) * .4);
    EcoCreatureMovement::FFaunaWaterColumn Water;
    FVector Goal = Position;
    const bool bWet = EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Position,
        Clearance, Water);
    if (bWet)
    {
        Goal += Water.Current * Dt * (Stock->bFloats ? 1. : .2);
        EcoCreatureMovement::FFaunaWaterColumn Destination;
        if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Goal, Clearance, Destination))
        {
            Goal = Position;
            Destination = Water;
        }
        Goal.Z = Stock->bFloats ? Destination.Surface - Clearance : Destination.Bottom + Clearance;
    }
    else
    {
        FVector Ground;
        if (!EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Position, Ground)
            || FMath::Abs(Ground.Z - Position.Z) > 160.) return;
        Goal.Z = Ground.Z + Clearance;
    }
    const FVector Next = Position + (Goal - Position).GetClampedToMaxSize(35. * Dt);
    const FCollisionQueryParams Query(SCENE_QUERY_STAT(EcoFaunaWaterCarcass), false);
    if (!GetWorld()->SweepTestByObjectType(Position, Next, FQuat::Identity, FCollisionObjectQueryParams(ECC_WorldStatic),
            FCollisionShape::MakeSphere(FMath::Max(.5, Clearance - .25)), Query))
    {
        Transform.SetLocation(Next);
        Stock->Position = Next;
        Velocity = (Next - Position) / Delta;
    }
    const bool bAtLevel = FMath::Abs(Stock->Position.Z - Goal.Z) <= 1.;
    const bool bWaterborne = bWet && Stock->Position.Z <= Water.Surface && Stock->Position.Z >= Water.Bottom;
    const bool bGrounded = !bWet && bAtLevel;
    if (bGrounded && !Stock->bGrounded)
        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("WaterCarcassStranded"));
    if (bWaterborne && !Stock->bWaterborne)
        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("WaterCarcassSubmerged"));
    if (bWaterborne && bAtLevel && FMath::Abs(Position.Z - Goal.Z) > 1.)
        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now,
            Stock->bFloats ? TEXT("WaterCarcassSurface") : TEXT("WaterCarcassBottom"));
    Stock->bWaterborne = bWaterborne;
    Stock->bGrounded = bGrounded;
    return;
}

int64 AEcoCreatureIntegrationSpawner::FindFaunaWaterPrey(const FMassEntityManager& EM, FMassEntityHandle Entity,
    const FEcoFaunaSpecies& Profile, const FVector& From, double Now, bool bInWater, double ApproachSeconds,
    double& BestScore, FVector& Goal) const
{
    const auto* Species = &Profile;
    const auto* Fauna = &EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entity);
    const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
    const bool bAmphibious = Species->Locomotion == EEcoFaunaLocomotion::Amphibious;
    const double Caution = Species->bIndividualResponse ? Fauna->Life.Genome.Caution : 1.;
    const int64 HunterId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).StableAgentId;
    int64 BestId = 0;
    if (!bAmphibious || Now < Fauna->AttackReady || Fauna->Stamina < .25f) return BestId;
    for (const auto Target : Owned)
    {
        const auto& TargetId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Target);
        const auto* Rule = Species->PreyRules.FindByPredicate(
            [&](const auto& Entry) { return Entry.SpeciesId == TargetId.SpeciesId; });
        if (!Rule) continue;
        const auto* TargetProfile = FindFauna(TargetId.SpeciesId);
        if (!TargetProfile || !TargetProfile->IsAquatic()) continue;
        const FVector TargetPosition = EM.GetFragmentDataChecked<FTransformFragment>(Target).GetTransform().GetLocation();
        const double Distance = FVector::Dist(From, TargetPosition);
        const double SightRange = FMath::Min(325.f, Species->SightRange);
        if (Distance > SightRange) continue;
        const auto Reject = [&](FName Reason) {
            if (bAuditFaunaHunts)
                UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Target=%lld Medium=Water Event=Reject Reason=%s"),
                    HunterId, TargetId.StableAgentId, *Reason.ToString());
        };
        const auto* TargetFauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Target);
        const auto& TargetVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Target);
        if (!TargetFauna || TargetVitals.HP <= 0.f
            || EM.GetFragmentDataChecked<FEcoRegionFragment>(Target).CurrentRegionId != Region.CurrentRegionId)
        {
            Reject(TEXT("HuntTargetUnavailable"));
            continue;
        }
        if (!FitsFaunaPrey(*Rule, *Species, *TargetProfile, Fauna->Life, TargetFauna->Life, TargetVitals, Now))
        {
            Reject(TEXT("HuntTargetSizeOrMaturity"));
            continue;
        }
        EcoCreatureMovement::FFaunaWaterColumn TargetWater;
        if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, TargetPosition, 1., TargetWater)
            || TargetPosition.Z < TargetWater.Bottom || TargetPosition.Z > TargetWater.Surface)
        {
            Reject(TEXT("HuntTargetInOtherMedium"));
            continue;
        }
        const double VisibleRange = SightRange * FMath::Lerp(1., .18, TargetWater.VisualCoverAt(TargetPosition.Z));
        if (Distance > VisibleRange)
        {
            Reject(TEXT("HuntWaterVegetationCover"));
            continue;
        }
        FName Rejection = TEXT("HuntOccluded");
        if (bInWater ? !CanHuntFauna(EM, Entity, Target, *Species, Now, false, true, bAuditFaunaHunts ? &Rejection : nullptr)
            : !HasClearSight(*GetWorld(), From, TargetPosition, 0.f, 0.f))
        {
            Reject(Rejection);
            continue;
        }
        const double Risk = (1. - Fauna->Stamina) * 2. + Caution * TargetProfile->DefenseDamage;
        const double Score = RankFaunaFood(EcoFaunaFeeding::Value(Species->PredationEnergyPerMeal() * Rule->Preference,
            Distance / Species->WalkSpeed + ApproachSeconds, Risk),
            HunterId, Region.CurrentRegionId, Now, EEcoFaunaFoodIntent::LivePrey, TargetId.StableAgentId);
        if (bAuditFaunaHunts)
            UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Target=%lld Medium=Water Event=Candidate Evidence=Sight Score=%.3f"),
                HunterId, TargetId.StableAgentId, Score);
        if (Score <= BestScore) continue;
        BestScore = Score;
        BestId = TargetId.StableAgentId;
        Goal = TargetPosition;
    }
    return BestId;
}

void AEcoCreatureIntegrationSpawner::MoveFaunaInWater(FMassEntityManager& EM, FMassEntityHandle Entity,
    const FEcoFaunaSpecies& Profile, float Delta, double Now, double PhysicalCondition, float Darkness, bool bAdaptiveMeal)
{
    const auto* Species = &Profile;
    const auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
    const bool bAmphibious = Species->Locomotion == EEcoFaunaLocomotion::Amphibious;
    auto* Fauna = &EM.GetFragmentDataChecked<FEcoFaunaFragment>(Entity);
    const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
    const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
    auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform();
    auto& Velocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value;
    const FVector Position = Transform.GetLocation();
    const double Dt = FMath::Min(Delta, .1f);
    const bool bPassageTravel = Species->IsAquatic()
        && EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State == EEcoResidenceState::Traveling;
    Velocity = FVector::ZeroVector;
    const double Clearance = FMath::Max(1., Species->BodyRadius * Fauna->Life.BodyScale(Now) * .65);
    const double WaterMargin = Clearance + .35;
    const float Activity = Species->RoutineActivity(Darkness);
    const double Speed = Species->WalkSpeed * Fauna->Life.SpeedScale(Now)
        * PhysicalCondition * FMath::Lerp(.45, 1., double(Activity));
    constexpr float SwimStaminaPerSecond = .025f;
    const FCollisionQueryParams Query(SCENE_QUERY_STAT(EcoFaunaSwim), false);
    const FCollisionObjectQueryParams Static(ECC_WorldStatic);
    const auto CanCross = [&](const FVector& Start, const FVector& End) {
        FCollisionQueryParams SwimQuery = Query;
        const auto Shape = FCollisionShape::MakeSphere(FMath::Max(.5, Clearance - .2));
        FHitResult Hit;
        while (GetWorld()->SweepSingleByObjectType(Hit, Start, End, FQuat::Identity, Static, Shape, SwimQuery))
        {
            const AActor* Actor = Hit.GetActor();
            if (!EcoCreatureMovement::IsWaterSurfaceCollision(Actor)) return false;
            SwimQuery.AddIgnoredActor(Actor);
        }
        return true;
    };
    const float Energy = Vitals.Energy / FMath::Max(1.f, Vitals.MaxEnergy);
    const auto* WaterCarcass = FaunaCarcasses.Find(Fauna->CarrionTargetId);
    const bool bHasWaterFood = (FaunaPatchStock.IsValidIndex(Fauna->PatchTarget) && FaunaPatchStock[Fauna->PatchTarget] >= .2f)
        || Fauna->TargetId > 0 || (WaterCarcass && WaterCarcass->bWaterborne
            && WaterCarcass->Remaining > .2f && WaterCarcass->ExpiresAt > Now);
    const bool bReturning = bAmphibious && Fauna->ShorePhase == EEcoFaunaShorePhase::None
        && (Now >= Fauna->PhaseUntil || Energy >= Species->MealStopFraction
        || !bHasWaterFood || Fauna->Stamina < .15f || Now < Fauna->ThreatUntil);
    if (bReturning)
    {
        Fauna->AttackContact = -1.;
        Fauna->TargetId = 0;
        Fauna->CarrionTargetId = 0;
    }
    else if (Fauna->AttackContact >= 0.) return;
    if (Fauna->ShorePhase == EEcoFaunaShorePhase::None && bReturning)
    {
        if (Now >= Fauna->NextDecision)
        {
            Fauna->NextDecision = Now + 1.;
            EcoCreatureMovement::FFaunaWaterColumn EntryWater;
            EcoCreatureMovement::FFaunaWaterColumn CurrentWater;
            EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Position, Clearance, CurrentWater);
            const auto WithinSwimBudget = [&](const FVector& Entry) {
                const FVector Offset = Entry - Position;
                const double Travel = FMath::Max(0., Offset.Size() - 10.);
                const double Progress = FMath::Max(0., Speed + FVector::DotProduct(CurrentWater.Current, Offset.GetSafeNormal()));
                return Travel <= Progress * Fauna->Stamina / SwimStaminaPerSecond;
            };
            const bool bRecentRouteBlock = Now < Fauna->PatchBlockedUntil;
            const bool bCanUsePrevious = !Fauna->LandingPoint.IsZero() && !bRecentRouteBlock
                && WithinSwimBudget(Fauna->SwimEntry)
                && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Fauna->LandingPoint, 0.)
                && EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId,
                    Fauna->SwimEntry, Clearance, EntryWater)
                && Fauna->SwimEntry.Z >= EntryWater.Bottom + Clearance
                && Fauna->SwimEntry.Z <= EntryWater.Surface - Clearance;
            static const int64 ExitAuditAgent = [] {
                int64 Agent = 0;
                FParse::Value(FCommandLine::Get(), TEXT("EcoIslandWaterExitAuditAgent="), Agent);
                return Agent;
            }();
            const bool bAuditExit = ExitAuditAgent > 0 && ExitAuditAgent == Id.StableAgentId;
            if (bAuditExit)
                UE_LOG(LogTemp, Log, TEXT("[Eco Water Exit][Decision] Agent=%lld At=%.9f Previous=%d RecentBlock=%d Clearance=%.9g"),
                    Id.StableAgentId, Now, int32(bCanUsePrevious), int32(bRecentRouteBlock), Clearance);
            if (!bCanUsePrevious)
            {
                double BestDistance = MAX_dbl;
                FName BestPatch = NAME_None;
                for (const auto& Patch : FaunaHabitatPatches)
                {
                    if (!Patch.bHasShoreEntry || Patch.Stage > FaunaHabitatStage
                        || Patch.RegionId != Region.CurrentRegionId || !Patch.Consumers.Contains(Species->SpeciesId)) continue;
                    const auto AuditCandidate = [&](const TCHAR* Gate, double Distance = -1.) {
                        if (bAuditExit)
                            UE_LOG(LogTemp, Log, TEXT("[Eco Water Exit][Candidate] Agent=%lld At=%.9f Patch=%s Gate=%s DistanceSq=%.17g"),
                                Id.StableAgentId, Now, *Patch.Id.ToString(), Gate, Distance);
                    };
                    if (bRecentRouteBlock && FVector::DistSquared2D(Patch.WaterEntryPoint, Fauna->SwimEntry) < FMath::Square(16.))
                    {
                        AuditCandidate(TEXT("RecentBlock"));
                        continue;
                    }
                    if (!EcoCreatureMovement::IsWadeableGround(*GetWorld(), Patch.ShorePoint, 0.))
                    {
                        AuditCandidate(TEXT("Shore"));
                        continue;
                    }
                    if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId,
                            Patch.WaterEntryPoint, Clearance, EntryWater))
                    {
                        AuditCandidate(TEXT("Depth"));
                        continue;
                    }
                    FVector Entry = Patch.WaterEntryPoint;
                    Entry.Z = FMath::Clamp(Entry.Z, EntryWater.Bottom + Clearance, EntryWater.Surface - Clearance);
                    const double Distance = FVector::DistSquared(Position, Entry);
                    if (Distance >= BestDistance || !EcoCreatureMovement::HasClearWaterSight(*GetWorld(), Position, Entry)
                        || GetWorld()->LineTraceTestByObjectType(Position, Entry,
                            FCollisionObjectQueryParams(EcoFaunaDecision::SightCoverChannel),
                            FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaExitCover))))
                    {
                        AuditCandidate(Distance >= BestDistance ? TEXT("Farther") : TEXT("Occluded"), Distance);
                        continue;
                    }
                    if (!WithinSwimBudget(Entry))
                    {
                        AuditCandidate(TEXT("Stamina"), Distance);
                        continue;
                    }
                    AuditCandidate(TEXT("Clear"), Distance);
                    BestDistance = Distance;
                    BestPatch = Patch.Id;
                    Fauna->SwimEntry = Entry;
                    Fauna->LandingPoint = Patch.ShorePoint;
                }
                if (bAuditExit)
                    UE_LOG(LogTemp, Log, TEXT("[Eco Water Exit][Result] Agent=%lld At=%.9f Patch=%s"),
                        Id.StableAgentId, Now, *BestPatch.ToString());
                if (BestDistance < MAX_dbl)
                    RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("SwimAlternateExit"));
                else
                    Fauna->LandingPoint = FVector::ZeroVector;
            }
        }
        if (!Fauna->LandingPoint.IsZero() && FVector::DistSquared(Position, Fauna->SwimEntry) <= FMath::Square(10.)
            && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Fauna->LandingPoint, 0.))
            Fauna->ShorePhase = EEcoFaunaShorePhase::Exiting;
    }
    if (Fauna->ShorePhase != EEcoFaunaShorePhase::None)
    {
        const bool bEntering = Fauna->ShorePhase == EEcoFaunaShorePhase::Entering;
        const FVector BankCenter = Fauna->LandingPoint + FVector(0., 0., Clearance + 2.);
        EcoCreatureMovement::FFaunaWaterColumn EntryWater;
        const bool bEntryUsable = EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId,
            Fauna->SwimEntry, Clearance, EntryWater);
        if (bEntering && !bEntryUsable)
            Fauna->ShorePhase = EEcoFaunaShorePhase::Exiting;
        else if (!bEntering && !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Fauna->LandingPoint, 0.))
            Fauna->ShorePhase = EEcoFaunaShorePhase::None;
        else
        {
            const bool bUseLip = bEntering && FaunaHabitatPatches.ContainsByPredicate([&](const auto& Patch)
            {
                return Patch.bHasShoreEntry && !Patch.DryBankPoint.IsZero()
                    && Patch.RegionId == Region.CurrentRegionId && Patch.ShorePoint.Equals(Fauna->LandingPoint, 1.)
                    && FVector::DistSquared2D(Patch.WaterEntryPoint, Fauna->SwimEntry) <= 1.;
            });
            const bool bCrossLip = bUseLip && FVector::DistSquared2D(Position, Fauna->SwimEntry) > FMath::Square(.5);
            const FVector Goal = bCrossLip ? FVector(Fauna->SwimEntry.X, Fauna->SwimEntry.Y, BankCenter.Z)
                : bEntering ? Fauna->SwimEntry : BankCenter;
            const FVector Next = Position + (Goal - Position).GetClampedToMaxSize(Species->WalkSpeed * Dt * PhysicalCondition);
            const auto LiftFromGround = [&](FVector Point) {
                Point.Z = FMath::Max(Point.Z, BankCenter.Z);
                return Point;
            };
            if (bUseLip && !bCrossLip ? CanCross(Position, Next)
                : CanCross(LiftFromGround(Position), LiftFromGround(Next)))
            {
                Transform.SetLocation(Next);
                Velocity = (Next - Position) / Delta;
                if (!Velocity.IsNearlyZero()) Transform.SetRotation(Velocity.GetSafeNormal2D().ToOrientationQuat());
                if (!bCrossLip && FVector::DistSquared(Next, Goal) <= FMath::Square(2.))
                {
                    Fauna->ShorePhase = EEcoFaunaShorePhase::None;
                    Fauna->PhaseUntil = Now + 8.;
                    if (!bEntering)
                    {
                        Transform.SetLocation(Fauna->LandingPoint);
                        Fauna->bSwimming = false;
                        Fauna->NextDecision = Now;
                        Fauna->PatchTarget = INDEX_NONE;
                        const auto* Exit = FaunaHabitatPatches.FindByPredicate([&](const auto& Patch)
                        {
                            return Patch.bHasShoreEntry && !Patch.DryBankPoint.IsZero()
                                && Patch.Stage <= FaunaHabitatStage && Patch.RegionId == Region.CurrentRegionId
                                && Patch.Consumers.Contains(Species->SpeciesId)
                                && Patch.ShorePoint.Equals(Fauna->LandingPoint, 1.)
                                && FVector::DistSquared2D(Patch.WaterEntryPoint, Fauna->SwimEntry) <= 1.;
                        });
                        if (Exit && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Exit->DryBankPoint, 0.))
                        {
                            Fauna->Goal = Exit->DryBankPoint;
                            Fauna->ShorePhase = EEcoFaunaShorePhase::ClearingBank;
                            const double GroundSeconds = FVector::Dist2D(Fauna->LandingPoint, Fauna->Goal)
                                / FMath::Max(1., Species->WalkSpeed * PhysicalCondition);
                            Fauna->PhaseUntil = FMath::Max(Fauna->PhaseUntil, Now + GroundSeconds + 1.);
                        }
                        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("SwimExit"));
                    }
                    else RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("SwimEnter"));
                }
            }
            else Fauna->ShorePhase = bEntering ? EEcoFaunaShorePhase::Exiting : EEcoFaunaShorePhase::None;
        }
        return;
    }
    EcoCreatureMovement::FFaunaWaterColumn Water;
    if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Position, Clearance, Water))
    {
        // A receding crest can leave a swimmer within body length of a wet face.
        // Test nearby water explicitly and sweep a short retreat; never teleport it.
        constexpr double ProbeDistance = 18.;
        const double Retreat = FMath::Min(ProbeDistance, Species->WalkSpeed * Dt * PhysicalCondition);
        FVector Best = Position;
        double BestDepth = 0.;
        for (const FVector& Axis : {FVector::ForwardVector, -FVector::ForwardVector,
                FVector::RightVector, -FVector::RightVector})
        {
            FVector Candidate = Position + Axis * ProbeDistance;
            EcoCreatureMovement::FFaunaWaterColumn Nearby;
            if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Candidate,
                    WaterMargin, Nearby) || Nearby.Surface - Nearby.Bottom <= BestDepth) continue;
            Candidate = Position + Axis * Retreat;
            if (!CanCross(Position, Candidate)) continue;
            Best = Candidate;
            BestDepth = Nearby.Surface - Nearby.Bottom;
        }
        if (BestDepth > 0.)
        {
            Transform.SetLocation(Best);
            Velocity = (Best - Position) / Delta;
        }
        return;
    }
    if (bReturning && Fauna->LandingPoint.IsZero()) return;
    auto& Meal = Fauna->Life.MealCycle;
    if (bAdaptiveMeal)
        Meal.Update(Energy, Now, Species->MealStart(),
            Species->MealStopFraction - FMath::Max(.2f, Species->Maintenance) / Vitals.MaxEnergy,
            Species->PostMealRestSeconds);
    if (bAmphibious && !bReturning && Now >= Fauna->NextSense && Fauna->Stamina >= .25f
        && (!WaterCarcass || WaterCarcass->KillerId != Id.StableAgentId || WaterCarcass->Remaining <= .2f))
    {
        Fauna->NextSense = Now + .5;
        double BestScore = FaunaPatchStock.IsValidIndex(Fauna->PatchTarget)
            ? RankFaunaFood(EcoFaunaFeeding::Value(FMath::Min(FaunaPatchStock[Fauna->PatchTarget],
                FaunaHabitatPatches[Fauna->PatchTarget].EnergyPerMeal),
                FVector::Dist(Position, Fauna->Goal) / Species->WalkSpeed), Id.StableAgentId, Region.CurrentRegionId, Now,
                EEcoFaunaFoodIntent::HabitatPatch, 0, FaunaHabitatPatches[Fauna->PatchTarget].Id) : 0.;
        const int64 Previous = Fauna->TargetId;
        Fauna->TargetId = FindFaunaWaterPrey(EM, Entity, *Species, Position, Now, true, 0., BestScore, Fauna->Goal);
        if (Fauna->TargetId > 0 && Previous != Fauna->TargetId)
            RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("WaterPreySelected"), Fauna->TargetId);
        if (!Fauna->TargetId && FaunaHabitatPatches.IsValidIndex(Fauna->PatchTarget))
            Fauna->Goal = FaunaHabitatPatches[Fauna->PatchTarget].Center;
    }
    if (bAmphibious && !bReturning && Fauna->TargetId > 0)
    {
        const auto* Target = AgentLookup.Find(Fauna->TargetId);
        if (Target && CanHuntFauna(EM, Entity, *Target, *Species, Now, false, false))
        {
            Fauna->Goal = EM.GetFragmentDataChecked<FTransformFragment>(*Target).GetTransform().GetLocation();
            if (CanHuntFauna(EM, Entity, *Target, *Species, Now, true, true))
            {
                Fauna->AttackContact = Now + Species->AttackWindup;
                RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("WaterContactQueued"), Fauna->TargetId);
                return;
            }
        }
        else
        {
            RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("WaterPreyUnavailable"), Fauna->TargetId);
            Fauna->TargetId = 0;
        }
    }
    if (!bAmphibious && !bPassageTravel && Now >= Fauna->NextDecision)
    {
        static const int64 AuditAgent = [] {
            int64 Requested = 0;
            FParse::Value(FCommandLine::Get(), TEXT("EcoIslandWaterFoodAuditAgent="), Requested);
            return Requested;
        }();
        const bool bAudit = AuditAgent > 0 && AuditAgent == Id.StableAgentId;
        Fauna->NextDecision = Now + 1.;
        Fauna->PatchTarget = INDEX_NONE;
        Fauna->PatchAccessPoint = 0;
        Fauna->CarrionTargetId = 0;
        double BestScore = 0.;
        const bool bSeeking = bAdaptiveMeal ? Meal.bSeeking : Energy <= Species->MealStart();
        if (bSeeking)
        {
            const double Range = Species->SightRange * FMath::Lerp(.25, 1., double(Activity));
            for (int32 Index = 0; Index < FaunaHabitatPatches.Num(); ++Index)
            {
                const auto& Patch = FaunaHabitatPatches[Index];
                if (!Patch.bSubmerged || Patch.Stage > FaunaHabitatStage || Patch.RegionId != Region.CurrentRegionId
                    || !Patch.Consumers.Contains(Species->SpeciesId) || !FaunaPatchStock.IsValidIndex(Index))
                    continue;
                const float Stock = FaunaPatchStock[Index];
                for (int32 Access = 0; Access <= Patch.ForageAccessPoints.Num(); ++Access)
                {
                    const FVector Point = Patch.ForagePoint(Access);
                    const double Distance = FVector::Dist(Point, Position);
                    const auto AuditCandidate = [&](const TCHAR* Gate, double Score = 0.) {
                        if (bAudit)
                            UE_LOG(LogTemp, Log, TEXT("[Eco Water Food][Candidate] Agent=%lld At=%.9f Patch=%s Distance=%.9g Range=%.9g Stock=%.9g Gate=%s Score=%.17g Access=%d"),
                                Id.StableAgentId, Now, *Patch.Id.ToString(), Distance, Range, double(Stock), Gate, Score, Access);
                    };
                    if (Distance > Range || Stock < .2f || (Fauna->BlockedPatch == Index && Fauna->BlockedPatchAccessPoint == Access
                        && Now < Fauna->PatchBlockedUntil))
                    {
                        AuditCandidate(Distance > Range ? TEXT("Range") : Stock < .2f ? TEXT("Stock") : TEXT("RecentBlock"));
                        continue;
                    }
                    EcoCreatureMovement::FFaunaWaterColumn PatchWater;
                    if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Point,
                            Clearance, PatchWater)
                        || Point.Z <= PatchWater.Bottom || Point.Z >= PatchWater.Surface)
                    {
                        AuditCandidate(TEXT("Depth"));
                        continue;
                    }
                    bool bWaterborneEvidence = false;
                    if (!EcoCreatureMovement::HasClearWaterSight(*GetWorld(), Position, Point))
                    {
                        // Waterborne evidence is weaker and only useful through a continuous wet corridor.
                        const int32 Segments = FMath::Clamp(FMath::CeilToInt(Distance / 25.), 2, 24);
                        bool bConnected = true;
                        for (int32 Segment = 1; Segment < Segments && bConnected; ++Segment)
                        {
                            EcoCreatureMovement::FFaunaWaterColumn Crossing;
                            bConnected = EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId,
                                FMath::Lerp(Position, Point, double(Segment) / Segments), Clearance, Crossing);
                        }
                        if (!bConnected)
                        {
                            AuditCandidate(TEXT("WetCorridor"));
                            continue;
                        }
                        bWaterborneEvidence = true;
                    }
                    const double Score = RankFaunaFood(EcoFaunaFeeding::Value(FMath::Min(Stock, Patch.EnergyPerMeal),
                        Distance / Species->WalkSpeed), Id.StableAgentId, Region.CurrentRegionId, Now,
                        EEcoFaunaFoodIntent::HabitatPatch, 0, Patch.Id);
                    AuditCandidate(bWaterborneEvidence ? TEXT("Waterborne") : TEXT("Visible"), Score);
                    if (Score <= BestScore) continue;
                    BestScore = Score;
                    Fauna->PatchTarget = Index;
                    Fauna->PatchAccessPoint = Access;
                    Fauna->Goal = Point;
                }
            }
            if (Species->CarrionEnergyPerMeal > 0.f)
            {
                for (const auto& Pair : FaunaCarcasses)
                {
                    const auto& Stock = Pair.Value;
                    const double Distance = FVector::Dist(Stock.Position, Position);
                    const TCHAR* Rejection = Distance > Range ? TEXT("Range")
                        : !Stock.IsAvailable(Region.CurrentRegionId, *Species, Now, true) ? TEXT("Unavailable")
                        : !Stock.CanApproach(Id.StableAgentId, Now, true) ? TEXT("Access")
                        : !EcoCreatureMovement::HasClearWaterSight(*GetWorld(), Position, Stock.Position) ? TEXT("Occluded")
                        : nullptr;
                    if (Rejection && !bAudit) continue;
                    const double AvailableMeal = FMath::Min(double(Stock.Remaining), double(Species->CarrionEnergyPerMeal));
                    const double BaseScore = Rejection ? 0. : EcoFaunaFeeding::Value(AvailableMeal, Distance / Species->WalkSpeed);
                    const double Score = Rejection ? 0. : RankFaunaFood(BaseScore, Id.StableAgentId, Region.CurrentRegionId,
                        Now, EEcoFaunaFoodIntent::Carcass, Pair.Key);
                    if (bAudit)
                        UE_LOG(LogTemp, Log, TEXT("[Eco Water Food][CarcassCandidate] Agent=%lld At=%.9f Carcass=%lld Distance=%.9g Range=%.9g Stock=%.9g Meal=%.9g WalkSpeed=%.9g Gate=%s BaseScore=%.17g Score=%.17g"),
                            Id.StableAgentId, Now, Pair.Key, Distance, Range, double(Stock.Remaining), AvailableMeal,
                            double(Species->WalkSpeed), Rejection ? Rejection : TEXT("Visible"), BaseScore, Score);
                    if (Rejection) continue;
                    if (Score <= BestScore) continue;
                    BestScore = Score;
                    Fauna->PatchTarget = INDEX_NONE;
                    Fauna->CarrionTargetId = Pair.Key;
                    Fauna->Goal = Stock.Position;
                }
            }
        }
        if (bAudit)
        {
            const FName Selected = Fauna->PatchTarget == INDEX_NONE ? NAME_None : FaunaHabitatPatches[Fauna->PatchTarget].Id;
            UE_LOG(LogTemp, Log, TEXT("[Eco Water Food][Decision] Agent=%lld At=%.9f Seeking=%d Patch=%s Carcass=%lld Energy=%.9g Clearance=%.9g Position=%s Access=%d"),
                Id.StableAgentId, Now, int32(bSeeking), *Selected.ToString(), Fauna->CarrionTargetId,
                double(Energy), Clearance, *Position.ToString(), Fauna->PatchAccessPoint);
        }
        if (Fauna->PatchTarget == INDEX_NONE && Fauna->CarrionTargetId <= 0)
        {
            const uint64 Seed = uint64(Id.StableAgentId) ^ EcoLifeV3::Mix(++Fauna->DecisionCount);
            const double Angle = UE_TWO_PI * EcoLifeV3::Unit(Seed);
            const double Radius = Species->RoutineHomeRadius * FMath::Lerp(.1, .75, double(Activity));
            Fauna->Goal = Fauna->Home + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.) * Radius;
        }
    }
    FVector Goal = bReturning ? Fauna->SwimEntry : Fauna->Goal;
    if (!bReturning && WaterCarcass && Fauna->CarrionTargetId > 0)
        Goal = WaterCarcass->Position;
    const double Reach = Fauna->CarrionTargetId > 0 ? Species->CarrionReach() * .7 : FMath::Max(5., Clearance);
    if (!bReturning && !bPassageTravel && Fauna->PatchTarget == INDEX_NONE && Fauna->CarrionTargetId <= 0 && Fauna->TargetId <= 0)
        Goal.Z = Water.DepthHeight(Species->SwimDepthFraction, Clearance);
    else if (!bReturning && FVector::DistSquared(Position, Goal) <= FMath::Square(Reach))
        return;
    FVector Destination = Position + ((Goal - Position).GetClampedToMaxSize(Speed * Dt)
        + Water.Current * Dt);
    EcoCreatureMovement::FFaunaWaterColumn Next;
    const auto* DestinationRegion = FindRegion(Destination);
    if (DestinationRegion && DestinationRegion->RegionId == Region.CurrentRegionId
        && EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Destination, Clearance, Next))
    {
        const double Padding = FMath::Min(WaterMargin, (Next.Surface - Next.Bottom) * .5);
        Destination.Z = FMath::Clamp(Destination.Z, Next.Bottom + Padding, Next.Surface - Padding);
        bool bCanCross = CanCross(Position, Destination);
        if (!bCanCross)
        {
            // Keep depth until the full body clears the edge of a descending shelf.
            if (Position.Z >= Next.Bottom + Padding && Position.Z <= Next.Surface - Padding
                && Destination.Z < Position.Z)
            {
                Destination.Z = Position.Z;
                bCanCross = CanCross(Position, Destination);
            }
            if (!bCanCross)
            {
                // Lift within this movement budget before trying a rising shelf again.
                const double Rise = FMath::Min(Speed * Dt, Water.Surface - WaterMargin - Position.Z);
                if (Rise > 0.)
                {
                    Destination = Position + FVector(0., 0., Rise);
                    bCanCross = CanCross(Position, Destination);
                }
            }
        }
        if (bCanCross)
        {
            Velocity = (Destination - Position) / Delta;
            Transform.SetLocation(Destination);
            if (Velocity.SizeSquared() > 1.)
                Transform.SetRotation(FMath::RInterpConstantTo(Transform.Rotator(), Velocity.Rotation(), Dt, 180.).Quaternion());
            if (bAmphibious) Fauna->Stamina = FMath::Max(0.f, Fauna->Stamina - SwimStaminaPerSecond * float(Dt));
            return;
        }
    }
    Fauna->BlockedPatch = Fauna->PatchTarget;
    Fauna->BlockedPatchAccessPoint = Fauna->PatchAccessPoint;
    Fauna->PatchBlockedUntil = Now + 3.;
    Fauna->PatchTarget = INDEX_NONE;
    Fauna->NextDecision = Now + .25;
}

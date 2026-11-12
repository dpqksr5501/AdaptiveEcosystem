#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Misc/ScopeExit.h"

#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Mass/EcoHerdMigration.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassMovementFragments.h"
#include "MassSpawnerSubsystem.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/Pawn.h"
#include "Creature/Player/EcoPlayerEcologyComponent.h"
#include "Player/EcoPlayerState.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#endif

namespace
{
    TAutoConsoleVariable<int32> CVarFaunaHearingLog(TEXT("eco.Footsteps.HearingLog"), 0, TEXT("Log selected animal footstep evidence."));
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
        float EyeHeight = 35.f, float TargetHeight = 35.f)
    {
        return !World.LineTraceTestByObjectType(Start + FVector(0, 0, EyeHeight), End + FVector(0, 0, TargetHeight),
            FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaSight)));
    }

    bool ResolvePassageSeam(FVector& Entry, FVector& Exit, double CrossingRadius,
        TFunctionRef<bool(const FVector&, bool)> OwnsPoint)
    {
        if (FVector::Dist2D(Entry, Exit) <= CrossingRadius) return true;
        const FVector Start = Entry, End = Exit;
        const auto Boundary = [&](bool bOrigin)
        {
            double Inside = bOrigin ? 0. : 1.;
            double Outside = 1. - Inside;
            for (int32 Probe = 0; Probe < 20; ++Probe)
            {
                const double Mid = .5 * (Inside + Outside);
                if (OwnsPoint(FMath::Lerp(Start, End, Mid), bOrigin)) Inside = Mid;
                else Outside = Mid;
            }
            return FMath::Lerp(Start, End, Inside);
        };
        Entry = Boundary(true);
        Exit = Boundary(false);
        return FVector::Dist2D(Entry, Exit) <= CrossingRadius;
    }

    double LocalPlantStock(const FEcoV3RegionContext* Context, const FVector& Position)
    {
        if (!Context || !Context->bSpatialFoodRegistered) return 0.;
        const auto Point = Context->CmToUnits(Position);
        const double Size = Context->Sim.Config.WorldSize;
        if (Point.X < 0. || Point.Y < 0. || Point.X > Size || Point.Y > Size) return 0.;
        return Context->Sim.Food.Food[Context->Sim.Food.CellOf(Point)];
    }

    bool FindNearbyForage(UWorld& World, const FEcoV3RegionContext* Context, const AEcologyRegion& Region,
        const FVector& Position, FVector& Out)
    {
        if (!Context || !Context->bSpatialFoodRegistered) return false;
        const auto& Grid = Context->Sim.Food;
        const auto Point = Context->CmToUnits(Position);
        if (Point.X < 0. || Point.Y < 0. || Point.X > Context->Sim.Config.WorldSize || Point.Y > Context->Sim.Config.WorldSize)
            return false;
        const int32 Current = Grid.CellOf(Point);
        if (Grid.Food[Current] >= EcoFaunaNutrition::MinimumMeal)
        {
            Out = Position;
            return true;
        }
        struct FCandidate { FVector Position; double Score = 0.; };
        TArray<FCandidate, TInlineAllocator<121>> Candidates;
        constexpr int32 SearchCells = 5;
        const int32 X0 = Current % Grid.Gw;
        const int32 Y0 = Current / Grid.Gw;
        for (int32 Y = FMath::Max(0, Y0 - SearchCells); Y <= FMath::Min(Grid.Gw - 1, Y0 + SearchCells); ++Y)
        {
            for (int32 X = FMath::Max(0, X0 - SearchCells); X <= FMath::Min(Grid.Gw - 1, X0 + SearchCells); ++X)
            {
                const double Food = Grid.Food[Y * Grid.Gw + X];
                if (Food < EcoFaunaNutrition::MinimumMeal) continue;
                const double CenterX = (X + .5) * Grid.Cell;
                const double CenterY = (Y + .5) * Grid.Cell;
                const double Distance = FMath::Sqrt(FMath::Square(CenterX - Point.X) + FMath::Square(CenterY - Point.Y));
                Candidates.Add({Context->UnitsToCm(CenterX, CenterY, Position.Z), Food / (1. + Distance / Grid.Cell)});
            }
        }
        Candidates.StableSort([](const auto& A, const auto& B) { return A.Score > B.Score; });
        for (int32 Index = 0; Index < FMath::Min(8, Candidates.Num()); ++Index)
        {
            FVector Ground;
            if (!EcoCreatureMovement::ProjectSpawnPoint(World, Candidates[Index].Position, Ground)
                || !Region.ContainsPosition(Ground) || !EcoCreatureMovement::IsWadeableGround(World, Ground, 0.f)
                || !HasClearSight(World, Position, Ground)) continue;
            Out = Ground;
            return true;
        }
        return false;
    }
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaPassageSeamTest, "AdaptiveEcosystem.Fauna.Passage.AuthoredLegSeam",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFaunaPassageSeamTest::RunTest(const FString&)
{
    FVector Entry(-1000., 0., 0.), Exit(1000., 0., 0.);
    const auto Near = [](const FVector& Point, bool bOrigin) { return bOrigin ? Point.X <= -5. : Point.X >= 5.; };
    TestTrue(TEXT("Long authored leg resolves a short crossing"), ResolvePassageSeam(Entry, Exit, 30., Near));
    TestTrue(TEXT("Both endpoints remain inside their own region"), Near(Entry, true) && Near(Exit, false));
    Entry.X = -1000.;
    Exit.X = 1000.;
    TestFalse(TEXT("A real gap cannot be crossed by a seam rebase"), ResolvePassageSeam(Entry, Exit, 30.,
        [](const FVector& Point, bool bOrigin) { return bOrigin ? Point.X <= -40. : Point.X >= 40.; }));
    return true;
}
#endif

bool AEcoCreatureIntegrationSpawner::CanHuntFauna(const FMassEntityManager& EM, FMassEntityHandle Hunter,
    FMassEntityHandle Prey, const FEcoFaunaSpecies& Profile, double Now, bool bContact, bool bCheckVisibility, FName* Rejection) const
{
    const auto Reject = [Rejection](const TCHAR* Reason) { if (Rejection) *Rejection = FName(Reason); return false; };
    if (Hunter == Prey || !EM.IsEntityValid(Prey)) return Reject(TEXT("HuntTargetUnavailable"));
    const auto* Target = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Prey);
    if (!Target) return Reject(TEXT("HuntTargetBackend"));
    if (Target->Flight != EEcoFaunaFlightPhase::Grounded) return Reject(TEXT("HuntTargetAirborne"));
    const auto& Health = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Prey);
    const auto& PreyId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Prey);
    const auto* Rule = Profile.PreyRules.FindByPredicate([&](const auto& Entry) { return Entry.SpeciesId == PreyId.SpeciesId; });
    const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Hunter);
    if (!Rule) return Reject(TEXT("HuntDiet"));
    if (Health.HP <= 0.f) return Reject(TEXT("HuntTargetUnavailable"));
    if (EM.GetFragmentDataChecked<FEcoRegionFragment>(Prey).CurrentRegionId != Region.CurrentRegionId)
        return Reject(TEXT("HuntTargetOutsideRegion"));
    const auto& HunterLife = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Hunter).Life;
    const auto* TargetProfile = FindFauna(PreyId.SpeciesId);
    if (!TargetProfile || !FitsFaunaPrey(*Rule, Profile, *TargetProfile, HunterLife, Target->Life, Health, Now))
        return Reject(TEXT("HuntTargetSizeOrMaturity"));
    const auto& HunterTransform = EM.GetFragmentDataChecked<FTransformFragment>(Hunter).GetTransform();
    const FVector Start = HunterTransform.GetLocation();
    const FVector End = EM.GetFragmentDataChecked<FTransformFragment>(Prey).GetTransform().GetLocation();
    if (bCheckVisibility)
        if (const auto* Shelter = FindFaunaShelter(Region.CurrentRegionId, PreyId.SpeciesId, End, 0.);
            Shelter && Profile.BodyRadius * HunterLife.BodyScale(Now) > Shelter->EntranceRadius) return Reject(TEXT("HuntTargetInRefuge"));
    const double Radius = bContact ? Profile.AttackReach
        : Rule->MaxPursuitStart > 0.f ? FMath::Min(Profile.SightRange, Rule->MaxPursuitStart) : Profile.SightRange;
    const double FovCos = FMath::Cos(FMath::DegreesToRadians(Profile.SightHalfAngle));
    if (bCheckVisibility)
    {
        if (FVector::DistSquared(Start, End) > FMath::Square(Radius)) return Reject(TEXT("HuntOutOfReach"));
        if (!bContact && FVector::DotProduct((End - Start).GetSafeNormal2D(), HunterTransform.GetRotation().GetForwardVector()) < FovCos)
            return Reject(TEXT("HuntOutsideView"));
        if (!HasClearSight(*GetWorld(), Start, End, Profile.EyeHeight, TargetProfile->EyeHeight))
            return Reject(TEXT("HuntOccluded"));
    }
    if (TargetProfile->OffspringGuardRange <= 0.f && Rule->GuardRadius > 0.f && Target->Life.AgeFraction(Now) < 1.)
    {
        for (const auto Guard : Owned)
        {
            const auto* Nearby = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Guard);
            if (!Nearby || Nearby->Life.AgeFraction(Now) < 1. || Nearby->Flight != EEcoFaunaFlightPhase::Grounded) continue;
            if (EM.GetFragmentDataChecked<FEcoIdentityFragment>(Guard).SpeciesId != PreyId.SpeciesId
                || EM.GetFragmentDataChecked<FEcoRegionFragment>(Guard).CurrentRegionId != Region.CurrentRegionId) continue;
            const auto& GuardHealth = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Guard);
            if (GuardHealth.HP >= .7f * GuardHealth.MaxHP && FVector::DistSquared(End,
                    EM.GetFragmentDataChecked<FTransformFragment>(Guard).GetTransform().GetLocation()) <= FMath::Square(Rule->GuardRadius))
                return Reject(TEXT("HuntTargetGuarded"));
        }
    }
    return true;
}

FMassEntityHandle AEcoCreatureIntegrationSpawner::SelectFaunaGuard(const FMassEntityManager& EM,
    FMassEntityHandle Child, FMassEntityHandle Hunter, double Now) const
{
    const auto* Young = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Child);
    if (!Young || Young->Life.AgeFraction(Now) >= 1.) return {};
    const auto& ChildId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Child);
    const auto* Profile = FindFauna(ChildId.SpeciesId);
    if (!Profile || Profile->OffspringGuardRange <= 0.f) return {};
    const FName Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Child).CurrentRegionId;
    const FVector YoungPosition = EM.GetFragmentDataChecked<FTransformFragment>(Child).GetTransform().GetLocation();
    const FVector Danger = EM.GetFragmentDataChecked<FTransformFragment>(Hunter).GetTransform().GetLocation();
    if (FVector::DistSquared(YoungPosition, Danger) > FMath::Square(Profile->OffspringGuardRange)) return {};
    const int64 OtherParent = Young->Life.Caregiver == Young->Life.ParentA ? Young->Life.ParentB : Young->Life.ParentA;
    for (const int64 Id : {Young->Life.Caregiver, Profile->bAllowSecondParentGuard ? OtherParent : int64(0)})
    {
        const auto* Guard = Id > 0 ? AgentLookup.Find(Id) : nullptr;
        if (!Guard || !EM.IsEntityValid(*Guard)) continue;
        const auto* Adult = EM.GetFragmentDataPtr<FEcoFaunaFragment>(*Guard);
        const auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Guard);
        if (!Adult || Adult->Life.AgeFraction(Now) < 1. || Adult->bRecovering || Adult->Stamina < .30f
            || Adult->Flight != EEcoFaunaFlightPhase::Grounded || Vitals.HP < .55f * Vitals.MaxHP
            || Vitals.Energy < .25f * Vitals.MaxEnergy
            || EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Guard).SpeciesId != ChildId.SpeciesId
            || EM.GetFragmentDataChecked<FEcoRegionFragment>(*Guard).CurrentRegionId != Region) continue;
        const FVector Position = EM.GetFragmentDataChecked<FTransformFragment>(*Guard).GetTransform().GetLocation();
        if (FVector::DistSquared(Position, YoungPosition) <= FMath::Square(Profile->OffspringGuardRange)
            && HasClearSight(*GetWorld(), Position, Danger, Profile->EyeHeight)) return *Guard;
    }
    return {};
}

void AEcoCreatureIntegrationSpawner::ProcessFaunaPredation(double Now)
{
    if (FaunaSpecies.IsEmpty()) return;
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    for (const auto Hunter : Owned)
    {
        auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Hunter);
        if (!Fauna || Fauna->AttackContact < 0. || Now < Fauna->AttackContact) continue;
        Fauna->AttackContact = -1.;
        const int64 AttemptedTarget = Fauna->TargetId;
        const auto* Prey = AgentLookup.Find(AttemptedTarget);
        Fauna->TargetId = 0;
        const auto& HunterId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Hunter);
        const auto* Profile = FindFauna(HunterId.SpeciesId);
        Fauna->AttackReady = Now + Profile->AttackRecovery;
        Fauna->ChaseBegan = -1.;
        FName Rejection = TEXT("HuntTargetUnavailable");
        const FName HunterRegion = EM.GetFragmentDataChecked<FEcoRegionFragment>(Hunter).CurrentRegionId;
        if (!Prey || EM.GetFragmentDataChecked<FEcoVitalsFragment>(Hunter).HP <= 0.
            || !CanHuntFauna(EM, Hunter, *Prey, *Profile, Now, true, true, &Rejection))
        {
            RecordGameplayReason(HunterId.StableAgentId, HunterRegion, Now, Rejection, AttemptedTarget);
            if (UsesFaunaPursuitFix()) Fauna->AttackReady = Now + FMath::Min(.5f, Profile->AttackRecovery);
            if (bAuditFaunaHunts)
                UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Miss Reason=%s"),
                    HunterId.StableAgentId, *HunterId.SpeciesId.ToString(), *Rejection.ToString());
            continue;
        }
        const auto& PreyId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Prey);
        auto& HunterVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Hunter);
        auto& PreyVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Prey);
        auto& Defender = EM.GetFragmentDataChecked<FEcoFaunaFragment>(*Prey);
        const auto* PreyProfile = FindFauna(PreyId.SpeciesId);
        const auto& PreyTransform = EM.GetFragmentDataChecked<FTransformFragment>(*Prey).GetTransform();
        const FVector HunterPosition = EM.GetFragmentDataChecked<FTransformFragment>(Hunter).GetTransform().GetLocation();
        const auto Guard = SelectFaunaGuard(EM, *Prey, Hunter, Now);
        if (Guard.IsSet())
        {
            const auto& GuardTransform = EM.GetFragmentDataChecked<FTransformFragment>(Guard).GetTransform();
            const FVector GuardPosition = GuardTransform.GetLocation();
            const FVector YoungPosition = PreyTransform.GetLocation();
            const FVector ContactPoint = FMath::ClosestPointOnSegment(GuardPosition, HunterPosition, YoungPosition);
            if (FVector::DistSquared(GuardPosition, ContactPoint) <= FMath::Square(PreyProfile->BodyRadius + 35.f)
                && FVector::DotProduct(GuardPosition - YoungPosition, HunterPosition - YoungPosition) > 0.
                && HasClearSight(*GetWorld(), GuardPosition, HunterPosition, PreyProfile->EyeHeight, Profile->EyeHeight))
            {
                auto& Adult = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Guard);
                Adult.Stamina = FMath::Max(0.f, Adult.Stamina - .15f);
                HunterVitals.HP = FMath::Max(0.f, HunterVitals.HP - PreyProfile->DefenseDamage * float(Adult.Life.BodyScale(Now)));
                if (HunterVitals.HP <= 0.f)
                    EM.GetFragmentDataChecked<FEcoDeathFragment>(Hunter).Cause = EEcoDeathCause::ExternalDamage;
                Fauna->LastThreatPosition = GuardPosition;
                Fauna->ThreatUntil = Now + 2.;
                Fauna->AttackReady = Now + FMath::Max(4.f, Profile->AttackRecovery);
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][GuardIntercept] Guard=%lld Child=%lld Hunter=%lld Species=%s"),
                    EM.GetFragmentDataChecked<FEcoIdentityFragment>(Guard).StableAgentId, PreyId.StableAgentId,
                    HunterId.StableAgentId, *PreyId.SpeciesId.ToString());
                continue;
            }
        }
        const FVector ToHunter = (HunterPosition - PreyTransform.GetLocation()).GetSafeNormal2D();
        const float Defense = PreyProfile->DefenseDamage * float(Defender.Life.BodyScale(Now)
            * FMath::Lerp(.2, 1., Defender.Life.AgeFraction(Now)));
        if (Defense > 0.f && PreyVitals.HP >= .35f * PreyVitals.MaxHP
            && FVector::DotProduct(ToHunter, PreyTransform.GetRotation().GetForwardVector()) >= .25)
        {
            HunterVitals.HP = FMath::Max(0.f, HunterVitals.HP - Defense);
            if (HunterVitals.HP <= 0.f)
                EM.GetFragmentDataChecked<FEcoDeathFragment>(Hunter).Cause = EEcoDeathCause::ExternalDamage;
            Fauna->LastThreatPosition = PreyTransform.GetLocation();
            Fauna->ThreatUntil = Now + 2.;
            Fauna->AttackReady = Now + FMath::Max(4.f, Profile->AttackRecovery);
            UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Counterattack] Defender=%lld Hunter=%lld Damage=%.1f HunterHP=%.1f"),
                PreyId.StableAgentId, HunterId.StableAgentId, Defense, HunterVitals.HP);
            continue;
        }
        PreyVitals.HP = FMath::Max(0.f, PreyVitals.HP - PreyVitals.MaxHP * (Defense > 0.f ? .45f : 1.f));
        if (PreyVitals.HP > 0.f)
        {
            Defender.LastThreatPosition = HunterPosition;
            Defender.ThreatUntil = Now + 2.;
            if (UsesFaunaFollowWounded())
            {
                Fauna->TargetId = PreyId.StableAgentId;
                Fauna->LastPreyPosition = PreyTransform.GetLocation();
                Fauna->LastPreySeenUntil = Now + 2.;
            }
            UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Wounded] Hunter=%lld Prey=%lld HP=%.1f"),
                HunterId.StableAgentId, PreyId.StableAgentId, PreyVitals.HP);
            continue;
        }
        auto& Death = EM.GetFragmentDataChecked<FEcoDeathFragment>(*Prey);
        Death.Cause = EEcoDeathCause::Predation;
        Death.PredatorStableAgentId = HunterId.StableAgentId;
        RecordGameplayReason(HunterId.StableAgentId, HunterRegion, Now, TEXT("HuntCaptured"), PreyId.StableAgentId);
        EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(*Prey).bPredated = true;
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Predation] Hunter=%lld %s Prey=%lld %s"),
            HunterId.StableAgentId, *HunterId.SpeciesId.ToString(), PreyId.StableAgentId, *PreyId.SpeciesId.ToString());
    }
}

bool AEcoCreatureIntegrationSpawner::MoveFaunaFlight(const FEcoFaunaSpecies& Profile, FName RegionId,
    FEcoFaunaFragment& Fauna, const FVector& Position, double Now, double Delta, FVector& Destination) const
{
    UWorld& World = *GetWorld();
    const FCollisionObjectQueryParams Static(ECC_WorldStatic);
    const FCollisionQueryParams Query(SCENE_QUERY_STAT(EcoFaunaFlight));
    const auto GroundAt = [&](const FVector& Point, FVector& Ground)
    {
        FHitResult Hit;
        if (!World.LineTraceSingleByObjectType(Hit, Point + FVector(0, 0, 30), Point - FVector(0, 0, Profile.FlightCeiling + 400.f),
                Static, Query)) return false;
        Ground = Hit.ImpactPoint;
        const auto* Region = FindRegion(Ground);
        return Region && Region->RegionId == RegionId && Hit.ImpactNormal.Z >= .65f
            && EcoCreatureMovement::IsWadeableGround(World, Ground, 0.f);
    };
    const FVector Lift(0, 0, 18.);
    const auto IsClear = [&](const FVector& Start, const FVector& End)
    {
        return !World.SweepTestByObjectType(Start + Lift, End + Lift, FQuat::Identity, Static,
            FCollisionShape::MakeSphere(10.f), Query);
    };
    const auto FindAlternateLanding = [&]()
    {
        if (Now < Fauna.PhaseUntil) return false;
        Fauna.PhaseUntil = Now + .5;
        const double Radius = FMath::Clamp(Profile.FlightSpeed * .4, 80., 400.);
        for (const double Distance : {Radius * .5, Radius})
        {
            for (int32 I = 0; I < 8; ++I)
            {
                const FVector Above = Position + FVector::ForwardVector.RotateAngleAxis(45. * I, FVector::UpVector) * Distance;
                FVector Candidate;
                if (!GroundAt(Above, Candidate) || Candidate.Z > Position.Z
                    || Position.Z - Candidate.Z > Profile.FlightCeiling
                    || !IsClear(Position, Above) || !IsClear(Above, Candidate)) continue;
                Fauna.LandingPoint = Candidate;
                return true;
            }
        }
        return false;
    };
    const auto MoveTowardLanding = [&]()
    {
        const FVector Offset = Fauna.LandingPoint - Position;
        const double Distance = Offset.Size2D();
        if (Distance <= UE_SMALL_NUMBER) return false;
        Destination = Position + Offset.GetSafeNormal2D() * FMath::Min(Profile.FlightSpeed * Delta, Distance);
        return IsClear(Position, Destination);
    };
    FVector Ground;
    if (!GroundAt(Position, Ground))
    {
        const bool bAlreadyLanding = Fauna.Flight == EEcoFaunaFlightPhase::Landing;
        Fauna.Flight = EEcoFaunaFlightPhase::Landing;
        FVector ExistingGround;
        const FVector Above(Fauna.LandingPoint.X, Fauna.LandingPoint.Y, Position.Z);
        if (bAlreadyLanding && FVector::DistSquared2D(Position, Above) <= FMath::Square(400.)
            && GroundAt(Above, ExistingGround) && ExistingGround.Z <= Position.Z
            && IsClear(Above, ExistingGround) && MoveTowardLanding()) return true;
        return FindAlternateLanding() && MoveTowardLanding();
    }
    if (Fauna.Flight == EEcoFaunaFlightPhase::Takeoff && Now >= Fauna.PhaseUntil)
        Fauna.Flight = EEcoFaunaFlightPhase::Cruise;
    if (Fauna.Flight == EEcoFaunaFlightPhase::Cruise && FVector::DistSquared2D(Position, Fauna.LandingPoint) < FMath::Square(55.))
    {
        Fauna.Flight = EEcoFaunaFlightPhase::Landing;
        Fauna.LandingPoint = Ground;
    }
    if (Fauna.Flight == EEcoFaunaFlightPhase::Landing
        && FVector::DistSquared2D(Position, Fauna.LandingPoint) > FMath::Square(2.))
    {
        if (MoveTowardLanding()) return true;
        Fauna.LandingPoint = Ground;
    }

    const double AGL = Position.Z - Ground.Z;
    const FVector Direction = (Fauna.LandingPoint - Position).GetSafeNormal2D();
    Destination = Position;
    if (Fauna.Flight == EEcoFaunaFlightPhase::Cruise && AGL >= .6 * Profile.FlightCruiseHeight)
    {
        Destination += Direction * FMath::Min(Profile.FlightSpeed * Delta, FVector::Dist2D(Position, Fauna.LandingPoint));
        FVector NextGround;
        if (!GroundAt(Destination, NextGround) || Position.Z > NextGround.Z + Profile.FlightCeiling)
        {
            Fauna.LandingPoint = Ground;
            Fauna.Flight = EEcoFaunaFlightPhase::Landing;
            Destination = Position;
        }
        else Ground = NextGround;
    }
    const double Height = Fauna.Flight == EEcoFaunaFlightPhase::Landing ? 0. : Profile.FlightCruiseHeight;
    Destination.Z = FMath::Min(Ground.Z + Profile.FlightCeiling,
        FMath::FInterpConstantTo(Position.Z, Ground.Z + Height, Delta, Profile.FlightSpeed * .65));
    if (!IsClear(Position, Destination))
    {
        Fauna.LandingPoint = Ground;
        Fauna.Flight = EEcoFaunaFlightPhase::Landing;
        return FindAlternateLanding() && MoveTowardLanding();
    }
    if (Fauna.Flight == EEcoFaunaFlightPhase::Landing && Destination.Z <= Ground.Z + 2.)
    {
        Destination.Z = Ground.Z;
        Fauna.Flight = EEcoFaunaFlightPhase::Grounded;
        Fauna.Goal = Destination;
        Fauna.NextDecision = Now + 7.;
    }
    return true;
}

void AEcoCreatureIntegrationSpawner::ReconcileFaunaPassages(FMassEntityManager& EM,
    const FEcoServerTimeSnapshot& Time, double ObservedTime, int64 StepId, TArray<FEcoMigrationOutcome>& Arrivals)
{
    // Historical catch-up must not use a current-frame position to commit an old arrival.
    if (FaunaSpecies.IsEmpty() || ObservedTime - Time.ServerTimeSeconds > .1) return;
    const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
    const double Now = Time.ServerTimeSeconds;
    struct FPassage
    {
        FName From, To;
        FVector Entry, Exit;
        TArray<FVector> Approach;
    };
    TArray<FPassage> Passages;
    // This route opt-in is independent of legacy Mass migration, which cannot run with rule fauna.
    for (TActorIterator<AEcoHerdMigrationRoute> It(GetWorld()); It; ++It)
    {
        const auto& Route = **It;
        if (!Route.bEnabled || !Route.bAllowRuleFaunaPassage || !Route.bSharesHabitatReports || !Route.IsValidRoute()) continue;
        for (int32 I = 1; I < Route.Points.Num(); ++I)
        {
            FVector Entry = Route.Points[I - 1];
            FVector Exit = Route.Points[I];
            const auto* From = FindRegion(Entry);
            const auto* To = FindRegion(Exit);
            if (!From || !To || From->RegionId != Route.FromRegion || To->RegionId != Route.ToRegion) continue;
            // The authored segment can straddle a seam without its waypoints touching it.
            // Keep each end in its own region and leave the swept crossing to the movement writer.
            if (!ResolvePassageSeam(Entry, Exit, Migration.ArrivalRadius, [&](const FVector& P, bool bOrigin)
                { return FindRegion(P) == (bOrigin ? From : To); })) continue;
            const auto AddPassage = [&](const AEcologyRegion& Source, const AEcologyRegion& Destination,
                const FVector& Seam, const FVector& FarSide, int32 Index, int32 Direction)
            {
                if (!Source.AdjacentRegionIds.Contains(Destination.RegionId)) return;
                auto& Passage = Passages.Add_GetRef(FPassage{Source.RegionId, Destination.RegionId, Seam, FarSide, {Seam}});
                for (; Route.Points.IsValidIndex(Index) && FindRegion(Route.Points[Index]) == &Source; Index += Direction)
                    if (!Route.Points[Index].Equals(Passage.Approach[0], 1.))
                        Passage.Approach.Insert(Route.Points[Index], 0);
            };
            AddPassage(*From, *To, Entry, Exit, I - 1, -1);
            if (Route.bBidirectional) AddPassage(*To, *From, Exit, Entry, I, 1);
        }
    }
    if (Passages.IsEmpty() && !bAuditFaunaHunts && !Owned.ContainsByPredicate([&](FMassEntityHandle Entity)
        {
            return EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity)
                && EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State == EEcoResidenceState::Traveling;
        })) return;
    TMap<FName, int32> Load;
    TMap<FName, TMap<FName, int32>> FaunaLoad;
    TMap<FName, TArray<FMassEntityHandle>> GroundedResidents;
    TSet<int64> Caregivers;
    for (const auto Entity : Owned)
    {
        if (EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP <= 0.f) continue;
        const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
        const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity);
        ++Load.FindOrAdd(Region.CurrentRegionId);
        if (Travel.State == EEcoResidenceState::Traveling && Travel.TargetRegionId != Region.CurrentRegionId)
            ++Load.FindOrAdd(Travel.TargetRegionId);
        if (const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity))
        {
            const FName Species = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).SpeciesId;
            ++FaunaLoad.FindOrAdd(Region.CurrentRegionId).FindOrAdd(Species);
            if (Travel.State == EEcoResidenceState::Traveling && Travel.TargetRegionId != Region.CurrentRegionId)
                ++FaunaLoad.FindOrAdd(Travel.TargetRegionId).FindOrAdd(Species);
            if (Fauna->Life.AgeFraction(Now) < 1. && Fauna->Life.Caregiver > 0)
                Caregivers.Add(Fauna->Life.Caregiver);
            if (Fauna->Flight == EEcoFaunaFlightPhase::Grounded)
                GroundedResidents.FindOrAdd(Region.CurrentRegionId).Add(Entity);
        }
    }
    for (const auto& Birth : FaunaBirths)
    {
        Caregivers.Add(Birth.ParentA);
        Caregivers.Add(Birth.ParentB);
    }
    for (const auto Entity : Owned)
    {
        auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
        const auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
        if (!Fauna || Vitals.HP <= 0.f) continue;
        const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
        const auto* Species = FindFauna(Id.SpeciesId);
        auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
        auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity);
        auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform();
        const FVector Position = Transform.GetLocation();
        const bool bTraveling = Travel.State == EEcoResidenceState::Traveling;
        const bool bEligible = Species && Fauna->Flight == EEcoFaunaFlightPhase::Grounded
            && Fauna->Life.AgeFraction(Now) >= 1. && !Caregivers.Contains(Id.StableAgentId)
            && Now >= Fauna->ThreatUntil && Fauna->GuardThreatId == 0 && Fauna->CarrionTargetId == 0
            && Fauna->PatchTarget == INDEX_NONE && Now >= Fauna->RootingUntil
            && Fauna->TargetId == 0 && Fauna->AttackContact < 0.;
        const auto CancelTravel = [&]()
        {
            if (!bTraveling) return;
            --Load.FindOrAdd(Travel.TargetRegionId);
            --FaunaLoad.FindOrAdd(Travel.TargetRegionId).FindOrAdd(Id.SpeciesId);
            const double LastArrival = Travel.LastArrivalTime;
            Travel = FEcoTravelFragment();
            Travel.LastArrivalTime = LastArrival;
            Travel.NextDecisionTime = Now + 5.;
            Fauna->Goal = Position;
            Fauna->NextDecision = Now;
        };
        if (!bEligible)
        {
            CancelTravel();
            continue;
        }
        if (!bTraveling && (Now < Travel.NextDecisionTime || Vitals.Energy >= Species->MealStart() * Vitals.MaxEnergy)) continue;
        const auto ReportNoPassage = [&](const TCHAR* Reason)
        {
            if (bAuditFaunaHunts)
                UE_LOG(LogTemp, Log, TEXT("[Eco Passage Audit] Id=%lld Species=%s Region=%s Event=%s"),
                    Id.StableAgentId, *Id.SpeciesId.ToString(), *Region.CurrentRegionId.ToString(), Reason);
        };
        if (Passages.IsEmpty())
        {
            ReportNoPassage(TEXT("NoAuthoredSeam"));
            CancelTravel();
            continue;
        }
        FRegionEcologyState Origin;
        if (!Ecology->GetRegionState(Region.CurrentRegionId, Origin)) { CancelTravel(); continue; }
        const auto EstimateMeals = [&](FName Area, const FRegionEcologyState& State,
            const FVector& AccessPoint, double ETA, bool bNewResident)
        {
            const int32 Extra = bNewResident ? 1 : 0;
            const double PlantMeals = Species->UsesPlantFood()
                ? State.FoodAmount / (Species->FoodPerMeal * FMath::Max(1, State.ProjectedFoodConsumers + Extra)) : 0.;
            double PatchMeals = 0.;
            const auto* AreaResidents = FaunaLoad.Find(Area);
            for (int32 Index = 0; Index < FaunaPatchStock.Num(); ++Index)
            {
                const auto& Patch = FaunaHabitatPatches[Index];
                const float Stock = FaunaPatchStock[Index];
                if (Patch.RegionId != Area || Patch.Stage > FaunaHabitatStage || FMath::Min(Stock, Patch.EnergyPerMeal) < .2f
                    || !Patch.Consumers.Contains(Id.SpeciesId)
                    || (Fauna->BlockedPatch == Index && ETA < Fauna->PatchBlockedUntil)
                    || FVector::DistSquared(AccessPoint, Patch.Center) > FMath::Square(1.5 * Species->SightRange)
                    || !HasClearSight(*GetWorld(), AccessPoint, Patch.Center, Species->EyeHeight, 5.f)) continue;
                int32 Competitors = Extra;
                if (AreaResidents)
                    for (const auto& Resident : *AreaResidents)
                        if (Patch.Consumers.Contains(Resident.Key)) Competitors += Resident.Value;
                PatchMeals += Stock / (Patch.EnergyPerMeal * FMath::Max(1, Competitors));
            }
            double AnimalMeals = 0.;
            if (Species->CarrionEnergyPerMeal > 0.f)
                for (const auto& Pair : FaunaCarcasses)
                    if (Pair.Value.IsAvailable(Area, *Species, ETA) && Pair.Value.CanApproach(Id.StableAgentId, ETA))
                        AnimalMeals += Pair.Value.Remaining / Species->CarrionEnergyPerMeal;
            if (!Species->PreyRules.IsEmpty())
                if (const auto* Residents = GroundedResidents.Find(Area))
                    for (const auto Prey : *Residents)
                    {
                        if (Prey == Entity || EM.GetFragmentDataChecked<FEcoRegionFragment>(Prey).CurrentRegionId != Area) continue;
                        const FName Kind = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Prey).SpeciesId;
                        const auto* Rule = Species->PreyRules.FindByPredicate([Kind](const auto& R) { return R.SpeciesId == Kind; });
                        const auto* Profile = Rule ? FindFauna(Kind) : nullptr;
                        if (Profile && FitsFaunaPrey(*Rule, *Species, *Profile, Fauna->Life,
                            EM.GetFragmentDataChecked<FEcoFaunaFragment>(Prey).Life, EM.GetFragmentDataChecked<FEcoVitalsFragment>(Prey), Now))
                            AnimalMeals += 1.;
                    }
            const int32 AnimalConsumers = FMath::Max(1, Load.FindRef(Area) - State.ProjectedFoodConsumers + Extra);
            return PlantMeals + PatchMeals + AnimalMeals / AnimalConsumers;
        };
        const double LocalFood = EstimateMeals(Region.CurrentRegionId, Origin, Position, Now, false);
        const FPassage* Chosen = nullptr;
        int32 ChosenWaypoint = INDEX_NONE;
        double ChosenTravelSeconds = 0.;
        const TCHAR* Rejection = TEXT("NoOutgoingSeam");
        int32 Progress = 0;
        const auto RejectAt = [&](int32 Stage, const TCHAR* Reason)
        {
            if (Stage > Progress) { Progress = Stage; Rejection = Reason; }
        };
        double Best = 0.;
        for (const auto& Passage : Passages)
        {
            if (Passage.From != Region.CurrentRegionId
                || (bTraveling && (Passage.To != Travel.TargetRegionId || !Passage.Entry.Equals(Travel.TargetPosition, .1)))) continue;
            const auto* Group = Groups.FindByPredicate([&](const auto& G) { return G.RegionId == Passage.To; });
            const auto* TargetFauna = FaunaLoad.Find(Passage.To);
            const int32 SpeciesLoad = TargetFauna ? TargetFauna->FindRef(Id.SpeciesId) : 0;
            FRegionEcologyState Target;
            if (!Group || !Ecology->GetRegionState(Passage.To, Target)
                || Load.FindRef(Passage.To) - int32(bTraveling) >= Group->Schedule.RegionPopulationLimit
                || SpeciesLoad - int32(bTraveling) >= Species->RegionalLimit)
            { RejectAt(1, TEXT("DestinationCapacityOrUnavailable")); continue; }
            int32 Waypoint = INDEX_NONE;
            if (bTraveling)
            {
                Waypoint = Passage.Approach.IndexOfByPredicate([&](const FVector& Point) { return Point.Equals(Fauna->Goal, .1); });
                if (Waypoint != INDEX_NONE && Waypoint + 1 < Passage.Approach.Num()
                    && FVector::DistSquared2D(Position, Passage.Approach[Waypoint]) <= FMath::Square(25.))
                    ++Waypoint;
            }
            else
                for (int32 Index = Passage.Approach.Num() - 1; Index >= 0; --Index)
                {
                    const auto& Point = Passage.Approach[Index];
                    if (FVector::DistSquared2D(Position, Point) > FMath::Square(Species->SightRange)
                        || !HasClearSight(*GetWorld(), Position, Point, Species->EyeHeight, 5.f)) continue;
                    Waypoint = Index;
                    break;
                }
            if (Waypoint == INDEX_NONE) { RejectAt(2, TEXT("PassageApproachUnavailable")); continue; }
            double Distance = FVector::Dist2D(Position, Passage.Approach[Waypoint]);
            for (int32 Index = Waypoint + 1; Index < Passage.Approach.Num(); ++Index)
                Distance += FVector::Dist2D(Passage.Approach[Index - 1], Passage.Approach[Index]);
            const double TravelSeconds = Distance / Species->WalkSpeed;
            const double Gain = EstimateMeals(Passage.To, Target, Passage.Exit, Now + TravelSeconds, !bTraveling) - LocalFood;
            if (Gain <= 1.) { RejectAt(3, TEXT("InsufficientFoodGain")); continue; }
            const double Score = Gain / (1. + TravelSeconds);
            if (Score > Best || (Score == Best && Chosen && Passage.To.LexicalLess(Chosen->To)))
            {
                Best = Score;
                Chosen = &Passage;
                ChosenWaypoint = Waypoint;
                ChosenTravelSeconds = TravelSeconds;
            }
        }
        if (!Chosen) { ReportNoPassage(Rejection); CancelTravel(); continue; }
        if (!bTraveling)
        {
            Travel.State = EEcoResidenceState::Traveling;
            Travel.TargetRegionId = Chosen->To;
            Travel.TargetRegionIndex = Ecology->GetRegionRuntimeIndex(Chosen->To);
            Travel.TargetPosition = Chosen->Entry;
            Fauna->Goal = Chosen->Approach[ChosenWaypoint];
            Travel.MoveSpeed = Species->WalkSpeed;
            Travel.Reason = EEcoMigrationReason::FoodShortage;
            Travel.DepartureTime = Now;
            Travel.NextDecisionTime = Now + FMath::Max(10., 2. * ChosenTravelSeconds + 5.);
            ++Load.FindOrAdd(Chosen->To);
            ++FaunaLoad.FindOrAdd(Chosen->To).FindOrAdd(Id.SpeciesId);
            ReportNoPassage(TEXT("Departed"));
            continue;
        }
        if (Now >= Travel.NextDecisionTime) { CancelTravel(); continue; }
        if (!Fauna->Goal.Equals(Chosen->Approach[ChosenWaypoint], .1))
        {
            Fauna->Goal = Chosen->Approach[ChosenWaypoint];
            RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("PassageWaypoint"));
        }
        if (ChosenWaypoint + 1 < Chosen->Approach.Num()) continue;
        FVector Exit = Chosen->Exit;
        const double Scale = Fauna->Life.BodyScale(Now);
        if (FVector::Dist2D(Position, Exit) > FMath::Min(double(Species->WalkSpeed) * .5, Migration.ArrivalRadius)
            || !EcoCreatureMovement::ConstrainGroundStep(*GetWorld(), Position, Exit,
                FMath::Clamp(float(Species->BodyRadius * Scale), 1.f, 120.f), .65f,
                Species->SweepHeight * float(Scale), Species->StepHeight)
            || FMath::Abs(Exit.Z - Position.Z) > Species->StepHeight
            || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Exit, Species->WadeDepth)) continue;
        const auto* TargetRegion = FindRegion(Exit);
        if (!TargetRegion || TargetRegion->RegionId != Chosen->To) continue;
        // Complete the swept crossing and rebase residency at the same resource boundary.
        Arrivals.Add({Time.WorldEpoch, StepId, Id.StableAgentId, Region.CurrentRegionId, Chosen->To,
            Travel.Reason, Travel.DepartureTime, Now});
        --Load.FindOrAdd(Region.CurrentRegionId);
        --FaunaLoad.FindOrAdd(Region.CurrentRegionId).FindOrAdd(Id.SpeciesId);
        Region.CurrentRegionId = Chosen->To;
        Region.CurrentRegionIndex = Travel.TargetRegionIndex;
        RecordGameplayReason(Id.StableAgentId, Chosen->To, Now, TEXT("PassageArrived"));
        GroundedResidents.FindOrAdd(Chosen->To).Add(Entity);
        Transform.SetLocation(Exit);
        EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value = FVector::ZeroVector;
        Travel = FEcoTravelFragment();
        Travel.LastArrivalTime = Now;
        Travel.NextDecisionTime = Now + 30.;
        Fauna->Home = Fauna->Goal = Exit;
        Fauna->NextDecision = Now;
        Fauna->LastForageIntakeAt = -1.;
        Fauna->LastPreySeenUntil = Fauna->HeardPreyUntil = Fauna->ScentUntil = -1.;
        Fauna->LastScentId = 0;
        Fauna->BlockedPatch = INDEX_NONE;
        Fauna->BlockedCarrionId = 0;
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][PassageArrived] Id=%lld Species=%s Region=%s"),
            Id.StableAgentId, *Id.SpeciesId.ToString(), *Region.CurrentRegionId.ToString());
    }
}

void AEcoCreatureIntegrationSpawner::MoveFauna(float Delta, double Now)
{
    if (FaunaSpecies.IsEmpty() || Delta <= UE_SMALL_NUMBER) return;
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const bool bAdaptiveMeal = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::FaunaMeal);
    const bool bThreatVision = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::ThreatVision);
    const bool bShelterApproach = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::ShelterApproach);
    const bool bAdaptiveRoam = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::Roam);
    const bool bAdaptiveSprint = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::RoutineSprint);
    const bool bAdaptivePreyValue = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::PreyValue);
    const bool bAdaptivePursuitLimit = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::PursuitLimit);
    const bool bPursuitFix = UsesFaunaPursuitFix();
    const bool bCarrionAccess = UsesFaunaCarrionAccess();
    const bool bAttackAdvance = UsesFaunaAttackAdvance();
    const bool bFollowWounded = UsesFaunaFollowWounded();
    const bool bPersistence = UsesFaunaPersistence();
    const float ActivityBlend = bPersistence ? 1.f - FMath::Exp(-Delta / FaunaPersistence.ActivityMemorySeconds) : 0.f;
    TArray<FEcoNoiseEvent> Steps;
    if (FootstepAudioSet && !FootstepAudioSet->Profiles.IsEmpty())
        if (auto* Noise = GetWorld()->GetSubsystem<UEcoNoiseSubsystem>()) Noise->GatherRecent(Steps);
    TSet<int64> NestingParents;
    NestingParents.Reserve(FaunaBirths.Num() * 2);
    for (const auto& Birth : FaunaBirths)
    {
        NestingParents.Add(Birth.ParentA);
        NestingParents.Add(Birth.ParentB);
    }
    struct FGuardGoal { FVector Position; int64 HunterId; double Urgency; };
    TMap<FMassEntityHandle, FGuardGoal> GuardGoals;
    for (const auto Hunter : Owned)
    {
        const auto* Attack = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Hunter);
        if (!Attack || Attack->TargetId <= 0 || EM.GetFragmentDataChecked<FEcoVitalsFragment>(Hunter).HP <= 0.f) continue;
        const auto* Child = AgentLookup.Find(Attack->TargetId);
        if (!Child || !EM.IsEntityValid(*Child) || EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Child).HP <= 0.f) continue;
        const auto Guard = SelectFaunaGuard(EM, *Child, Hunter, Now);
        if (!Guard.IsSet()) continue;
        const FVector Young = EM.GetFragmentDataChecked<FTransformFragment>(*Child).GetTransform().GetLocation();
        const FVector Threat = EM.GetFragmentDataChecked<FTransformFragment>(Hunter).GetTransform().GetLocation();
        const FVector Between = Young + (Threat - Young).GetSafeNormal2D() * FMath::Min(100., FVector::Dist2D(Young, Threat) * .5);
        const int64 HunterId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Hunter).StableAgentId;
        const double Distance = FVector::DistSquared(Young, Threat);
        const auto* Current = GuardGoals.Find(Guard);
        if (!Current || Distance < Current->Urgency || (Distance == Current->Urgency && HunterId < Current->HunterId))
            GuardGoals.Add(Guard, {Between, HunterId, Distance});
    }
    for (const auto Entity : Owned)
    {
        auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
        const auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity);
        if (!Fauna || (Vitals.HP <= 0. && Fauna->Flight == EEcoFaunaFlightPhase::Grounded)) continue;
        const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
        const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
        const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity);
        const bool bPassageTravel = Travel.State == EEcoResidenceState::Traveling;
        const auto* Species = FindFauna(Id.SpeciesId);
        const auto* Context = Native ? Native->FindContext(Region.CurrentRegionId) : nullptr;
        auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform();
        auto& Velocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value;
        const FVector PreviousVelocity = Velocity;
        const FVector Position = Transform.GetLocation();
        const double Dt = FMath::Min(Delta, .1f);
        const auto CanMoveOnGround = [&](FVector& Destination)
        {
            const double BodyScale = Fauna->Life.BodyScale(Now);
            const float Radius = FMath::Clamp(float(Species->BodyRadius * BodyScale), 1.f, 120.f);
            if (!EcoCreatureMovement::ConstrainGroundStep(*GetWorld(), Position, Destination, Radius, .65f,
                    Species->SweepHeight * float(BodyScale), Species->StepHeight)) return false;
            const auto* DestinationRegion = FindRegion(Destination);
            return DestinationRegion && DestinationRegion->RegionId == Region.CurrentRegionId
                && FMath::Abs(Destination.Z - Position.Z) <= Species->StepHeight
                && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Destination, Species->WadeDepth);
        };
        Velocity = FVector::ZeroVector;
        ON_SCOPE_EXIT
        {
            if (bPersistence && Vitals.HP > 0.f)
            {
                const float FullSpeed = Fauna->Flight == EEcoFaunaFlightPhase::Grounded ? Species->RunSpeed : Species->FlightSpeed;
                const float Activity = float(FMath::Clamp(Velocity.Size() / FullSpeed, 0., 1.));
                const float Demand = FMath::Lerp(Species->RestingMaintenanceFraction, 1.f, Activity);
                Fauna->MaintenanceScale = FMath::Lerp(Fauna->MaintenanceScale, Demand, ActivityBlend);
            }
        };
        Fauna->bInvestigatingNoise = false;
        if (Fauna->Flight != EEcoFaunaFlightPhase::Grounded)
        {
            const auto PreviousFlight = Fauna->Flight;
            if (Vitals.HP <= 0. && PreviousFlight != EEcoFaunaFlightPhase::Landing)
            {
                Fauna->Flight = EEcoFaunaFlightPhase::Landing;
                Fauna->LandingPoint = Position;
                Fauna->PhaseUntil = Now;
            }
            FVector Destination;
            if (MoveFaunaFlight(*Species, Region.CurrentRegionId, *Fauna, Position, Now, Dt, Destination))
            {
                Velocity = (Destination - Position) / Delta;
                Transform.SetLocation(Destination);
                if (Vitals.HP > 0.f) Fauna->Stamina = FMath::Max(0.f, Fauna->Stamina - .5f * Species->SprintDrain * float(Dt));
                if (Vitals.HP <= 0.f && Fauna->Flight == EEcoFaunaFlightPhase::Grounded)
                {
                    Fauna->PhaseUntil = Now;
                    if (auto* Carcass = FaunaCarcasses.Find(Id.StableAgentId))
                    {
                        Carcass->Position = Destination;
                        Carcass->bGrounded = true;
                        const double Lifetime = Carcass->ExpiresAt - Carcass->OpenAt;
                        const double ExclusiveDuration = FMath::Max(0., Carcass->ExclusiveUntil - Carcass->OpenAt);
                        Carcass->OpenAt = Now + Species->DeathSettleSeconds;
                        Carcass->ExclusiveUntil = Carcass->OpenAt + ExclusiveDuration;
                        Carcass->ExpiresAt = Carcass->OpenAt + Lifetime;
                        auto& Death = EM.GetFragmentDataChecked<FEcoDeathFragment>(Entity);
                        Death.RemoveAfter = FMath::Max(Death.RemoveAfter, Carcass->ExpiresAt + 2.);
                    }
                }
                if (PreviousFlight != Fauna->Flight)
                    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Flight] Id=%lld Phase=%d HeightZ=%.1f"),
                        Id.StableAgentId, int32(Fauna->Flight), Destination.Z);
            }
        }
        else
        {
            if (PreviousVelocity.SizeSquared2D() <= FMath::Square(Species->WalkSpeed * Fauna->Life.SpeedScale(Now)))
                Fauna->Stamina = FMath::Min(1.f, Fauna->Stamina + Species->FatigueRecovery * float(Dt));
            if (Fauna->Stamina <= .15f) Fauna->bRecovering = true;
            else if (Fauna->Stamina >= .55f) Fauna->bRecovering = false;
            Fauna->bStalking = false;
            Fauna->bFollowingCaregiver = false;
            const float Darkness = Context ? float(Context->Sim.Dark) : 0.f;
            const float VisualThreatRange = Species->ThreatSenseRange
                * (bThreatVision ? FMath::Lerp(1.f, Species->NightVision, Darkness) : 1.f);
            auto& Meal = Fauna->Life.MealCycle;
            if (bAdaptiveMeal)
            {
                const bool bWasSeeking = Meal.bSeeking;
                const float MinimumBite = FMath::Max(.2f, EcoFaunaNutrition::MaintenancePerSecond);
                const float Stop = Species->MealStopFraction - MinimumBite / Vitals.MaxEnergy;
                Meal.Update(Vitals.Energy / Vitals.MaxEnergy, Now, Species->MealStart(),
                    Stop, Species->PostMealRestSeconds);
                if (bWasSeeking != Meal.bSeeking)
                    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][MealCycle] Id=%lld Species=%s Seeking=%d Energy=%.3f"),
                        Id.StableAgentId, *Id.SpeciesId.ToString(), Meal.bSeeking, Vitals.Energy / Vitals.MaxEnergy);
            }
            if (Now >= Fauna->NextThreatSense)
            {
                Fauna->NextThreatSense = Now + .45;
                double BestThreat = FMath::Square(VisualThreatRange);
                const double ThreatFovCos = FMath::Cos(FMath::DegreesToRadians(double(Species->ThreatSightHalfAngle)));
                const double ThreatNearRangeSq = FMath::Square(double(Species->ThreatNearAwarenessRange));
                for (const auto Other : Owned)
                {
                    const auto* Threat = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Other);
                    const auto* Wolf = EM.GetFragmentDataPtr<FEcoThreatStateFragment>(Other);
                    if ((!Threat || Threat->TargetId <= 0) && (!Wolf || !Wolf->Agent.Last.bHunting)) continue;
                    if (EM.GetFragmentDataChecked<FEcoVitalsFragment>(Other).HP <= 0.f
                        || EM.GetFragmentDataChecked<FEcoRegionFragment>(Other).CurrentRegionId != Region.CurrentRegionId) continue;
                    const FVector Danger = EM.GetFragmentDataChecked<FTransformFragment>(Other).GetTransform().GetLocation();
                    const FVector Offset = Danger - Position;
                    const double Distance = Offset.SizeSquared();
                    if (Distance >= BestThreat || !HasClearSight(*GetWorld(), Position, Danger, Species->EyeHeight)
                        || (Distance > ThreatNearRangeSq && FVector::DotProduct(
                            Offset.GetSafeNormal2D(), Transform.GetRotation().GetForwardVector()) < ThreatFovCos)) continue;
                    const auto* Hunter = FindFauna(EM.GetFragmentDataChecked<FEcoIdentityFragment>(Other).SpeciesId);
                    if (Hunter && !CanHuntFauna(EM, Other, Entity, *Hunter, Now, false, false)) continue;
                    Fauna->LastThreatPosition = Danger;
                    Fauna->ThreatUntil = Now + 1.5;
                    BestThreat = Distance;
                }
                if (const auto* Listener = FootstepAudioSet ? FootstepAudioSet->FindProfile(Id.SpeciesId) : nullptr)
                {
                    const FEcoNoiseEvent* ThreatNoise = nullptr;
                    const FEcoNoiseEvent* PreyNoise = nullptr;
                    float BestThreatSignal = 0.f, BestPreySignal = 0.f;
                    const float Weather = Context ? float(Context->Sim.Weather.Hear) : 1.f;
                    int64 Newest = Fauna->LastHeardFootstep;
                    for (const auto& Noise : Steps)
                    {
                        if (Noise.Id <= Fauna->LastHeardFootstep) continue;
                        Newest = FMath::Max(Newest, Noise.Id);
                        if (Noise.SourceAgentId == Id.StableAgentId
                            || (!Noise.RegionId.IsNone() && Noise.RegionId != Region.CurrentRegionId)) continue;
                        const bool bPlayer = EcoNoise::IsPlayerThreat(Noise.Tag);
                        const bool bCreature = Noise.Tag == TEXT("Footstep") && Noise.SourceAgentId > 0;
                        if (!bPlayer && !bCreature) continue;
                        const float Distance = float(FVector::Dist(Position, Noise.Position));
                        if (EcoFootsteps::HearingStrength(*Listener, Distance, Noise.MaxRange, Noise.Loudness, Weather, false) <= 0.f) continue;
                        if (bPlayer)
                        {
                            const auto* Pawn = Cast<APawn>(Noise.Instigator.Get());
                            const auto* Bridge = Pawn ? Pawn->FindComponentByClass<UEcoPlayerEcologyComponent>() : nullptr;
                            if (!Bridge || !Bridge->bThreatEnabled || !Pawn->IsPlayerControlled()) continue;
                            if (const auto* Health = Pawn->GetPlayerState<AEcoPlayerState>(); Health && !Health->IsAlive()) continue;
                        }
                        const bool bOccluded = !HasClearSight(*GetWorld(), Position, Noise.Position, Species->EyeHeight, 15.f);
                        const float Signal = EcoFootsteps::HearingStrength(*Listener, Distance, Noise.MaxRange, Noise.Loudness, Weather, bOccluded);
                        if (Signal <= 0.f) continue;
                        const auto* Source = bCreature ? AgentLookup.Find(Noise.SourceAgentId) : nullptr;
                        if (bCreature && (!Source || !EM.IsEntityValid(*Source)
                            || EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Source).HP <= 0.f)) continue;
                        const auto* SourceProfile = bCreature ? FindFauna(Noise.SourceSpeciesId) : nullptr;
                        const bool bThreat = bPlayer || (Noise.ThreatStrength > 0.f
                            && (Noise.SourceSpeciesId == TEXT("Wolf")
                                || (SourceProfile && CanHuntFauna(EM, *Source, Entity, *SourceProfile, Now, false, false))));
                        if (bThreat && Signal > BestThreatSignal)
                        {
                            BestThreatSignal = Signal;
                            ThreatNoise = &Noise;
                        }
                        else if (bCreature && !bThreat && Signal > BestPreySignal
                            && CanHuntFauna(EM, Entity, *Source, *Species, Now, false, false))
                        {
                            BestPreySignal = Signal;
                            PreyNoise = &Noise;
                        }
                    }
                    Fauna->LastHeardFootstep = Newest;
                    const auto LogEvidence = [&](const FEcoNoiseEvent& Noise, float Signal, const TCHAR* Reaction)
                    {
                        if (CVarFaunaHearingLog.GetValueOnGameThread()) UE_LOG(LogTemp, Log,
                            TEXT("[Eco Footstep Hearing] Listener=%lld Species=%s Source=%s Emitter=%lld Signal=%.3f Reaction=%s"),
                            Id.StableAgentId, *Id.SpeciesId.ToString(), *Noise.Tag.ToString(), Noise.SourceAgentId, Signal, Reaction);
                    };
                    if (ThreatNoise && BestThreat >= FMath::Square(VisualThreatRange))
                    {
                        Fauna->LastThreatPosition = ThreatNoise->Position;
                        Fauna->ThreatUntil = Now + 1.5;
                        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now,
                            EcoNoise::IsPlayerShot(ThreatNoise->Tag) ? TEXT("ShotHeard") : TEXT("ThreatHeard"),
                            ThreatNoise->SourceAgentId, BestThreatSignal);
                        LogEvidence(*ThreatNoise, BestThreatSignal, TEXT("Avoid"));
                    }
                    if (PreyNoise && Now >= Fauna->ThreatUntil)
                    {
                        Fauna->HeardPreyPosition = PreyNoise->Position;
                        Fauna->HeardPreyUntil = Now + 2.;
                        LogEvidence(*PreyNoise, BestPreySignal, TEXT("Investigate"));
                    }
                }
                else if (Context)
                {
                    const double SimNow = Context->Sim.T * EcoRepertoireV3::kStepSeconds;
                    for (const auto& Noise : Context->PlayerNoises)
                    {
                        if (SimNow - Noise.Time > .75 || Noise.Confidence < .25) continue;
                        const FVector Source = Context->UnitsToCm(Noise.X, Noise.Y, Noise.Z);
                        const double Distance = FVector::DistSquared(Position, Source);
                        if (Distance >= BestThreat || Distance > FMath::Square(Noise.Range * EcoRepertoireV3::kUnitCm)
                            || !HasClearSight(*GetWorld(), Position, Source, Species->EyeHeight)) continue;
                        Fauna->LastThreatPosition = Source;
                        Fauna->ThreatUntil = Now + 1.5;
                        BestThreat = Distance;
                    }
                }
            }
            const auto AuditCarrionRelease = [&](int64 StockId, const TCHAR* Reason)
            {
                if (!bAuditFaunaHunts || StockId <= 0) return;
                const auto* Released = FaunaCarcasses.Find(StockId);
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][CarrionRelease] Agent=%lld Species=%s Carcass=%lld At=%.3f Reason=%s Next=%lld LiveTarget=%lld Energy=%.3f MaxEnergy=%.3f Stamina=%.3f Remaining=%.3f DistanceCm=%.1f Killer=%d"),
                    Id.StableAgentId, *Id.SpeciesId.ToString(), StockId, Now, Reason, Fauna->CarrionTargetId,
                    Fauna->TargetId, Vitals.Energy, Vitals.MaxEnergy, Fauna->Stamina, Released ? Released->Remaining : -1.f,
                    Released ? FVector::Dist(Position, Released->Position) : -1., Released && Released->KillerId == Id.StableAgentId);
            };
            const auto ReleaseCarrion = [&](const TCHAR* Reason)
            {
                const int64 Previous = Fauna->CarrionTargetId;
                Fauna->CarrionTargetId = 0;
                AuditCarrionRelease(Previous, Reason);
            };
            const auto* Guard = GuardGoals.Find(Entity);
            if (Guard && Fauna->GuardThreatId != Guard->HunterId)
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][GuardApproach] Guard=%lld Species=%s Hunter=%lld"),
                    Id.StableAgentId, *Id.SpeciesId.ToString(), Guard->HunterId);
            Fauna->GuardThreatId = Guard ? Guard->HunterId : 0;
            if (Guard)
            {
                ReleaseCarrion(TEXT("Guard"));
                Fauna->PatchTarget = INDEX_NONE;
                Fauna->RootingUntil = -1.;
            }
            const bool bFleeing = !Guard && Now < Fauna->ThreatUntil;
            if (bFleeing)
            {
                Fauna->RootingUntil = -1.;
                ReleaseCarrion(TEXT("Threat"));
                Fauna->TargetId = 0;
                Fauna->AttackContact = -1.;
                Fauna->LastPreySeenUntil = -1.;
                Fauna->HeardPreyUntil = -1.;
                Fauna->ScentUntil = -1.;
                const auto* Shelter = FindFaunaShelter(Region.CurrentRegionId, Id.SpeciesId, Position, 650.,
                    bShelterApproach ? Species->EyeHeight : 0.f);
                Fauna->PatchTarget = Shelter && (bShelterApproach || HasClearSight(*GetWorld(), Position, Shelter->Center, Species->EyeHeight, 5.f))
                    ? int32(Shelter - FaunaHabitatPatches.GetData()) : INDEX_NONE;
            }
            const auto TryLaunch = [&](const FVector& Hint)
            {
                if (GetWorld()->SweepTestByObjectType(Position + FVector(0, 0, 18),
                    Position + FVector(0, 0, Species->FlightCruiseHeight), FQuat::Identity,
                    FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionShape::MakeSphere(10.f),
                    FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaTakeoff)))) return false;
                FEcoFaunaPlacement Landing;
                Landing.SpawnPoints.Add(Hint);
                TArray<FVector> Ground;
                if (!BuildFaunaPositions(Region.CurrentRegionId, Landing, Ground)) return false;
                Fauna->LandingPoint = Ground[0];
                Fauna->Flight = EEcoFaunaFlightPhase::Takeoff;
                Fauna->PhaseUntil = Now + .65;
                ReleaseCarrion(TEXT("Takeoff"));
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Flight] Id=%lld Phase=%d HeightZ=%.1f Escape=%d"),
                    Id.StableAgentId, int32(Fauna->Flight), Position.Z, bFleeing);
                return true;
            };
            const bool bCanFly = Species->Locomotion == EEcoFaunaLocomotion::Flight && Fauna->Life.AgeFraction(Now) >= 1.;
            if (bFleeing && bCanFly && Fauna->Stamina >= .20f && Vitals.Energy >= .25f * Vitals.MaxEnergy && Now >= Fauna->PhaseUntil)
            {
                const FVector Away = (Position - Fauna->LastThreatPosition).GetSafeNormal2D();
                if (!Away.IsNearlyZero() && TryLaunch(Position + Away * 2000.)) continue;
                Fauna->PhaseUntil = Now + .5;
            }
            if (!Guard && !bFleeing && Fauna->AttackContact >= 0. && !Fauna->bRecovering)
            {
                const auto* Target = AgentLookup.Find(Fauna->TargetId);
                if (Target && CanHuntFauna(EM, Entity, *Target, *Species, Now, false, false))
                {
                    const auto* PreyProfile = FindFauna(EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Target).SpeciesId);
                    const FVector TargetPosition = EM.GetFragmentDataChecked<FTransformFragment>(*Target).GetTransform().GetLocation();
                    const FVector ToTarget = TargetPosition - Position;
                    const FVector Heading = ToTarget.GetSafeNormal2D();
                    const auto& TargetVelocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(*Target).Value;
                    const bool bCommittedCharge = bAttackAdvance && Species->bFlankDefendedPrey
                        && PreyProfile && PreyProfile->DefenseDamage > 0.f;
                    const double RetreatSpeed = FVector::DotProduct(TargetVelocity, Heading);
                    if (PreyProfile && (bCommittedCharge || RetreatSpeed > 0.)
                        && ToTarget.SizeSquared2D() <= FMath::Square((bCommittedCharge ? 2.f : 1.25f) * Species->AttackReach)
                        && HasClearSight(*GetWorld(), Position, TargetPosition, Species->EyeHeight, PreyProfile->EyeHeight))
                    {
                        // Follow a withdrawing target during wind-up, using the same sweep and bite reach.
                        const double Scale = Fauna->Life.SpeedScale(Now);
                        const double CarrySpeed = FMath::Max(double(Species->WalkSpeed) * Scale,
                            FVector::DotProduct(PreviousVelocity, Heading));
                        const double Speed = bCommittedCharge ? Species->RunSpeed * Scale
                            : FMath::Min(CarrySpeed, RetreatSpeed);
                        const double Gap = (bCommittedCharge ? .4 : .65) * Species->AttackReach;
                        const double AdvanceDistance = FMath::Clamp(ToTarget.Size2D() - Gap, 0., Speed * Dt);
                        FVector Destination = Position + Heading * AdvanceDistance;
                        if (AdvanceDistance > UE_SMALL_NUMBER && CanMoveOnGround(Destination))
                        {
                            if (bAuditFaunaHunts && PreviousVelocity.IsNearlyZero())
                                UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Advance Prey=%lld"),
                                    Id.StableAgentId, *Id.SpeciesId.ToString(), Fauna->TargetId);
                            Velocity = (Destination - Position) / Delta;
                            Transform.SetLocation(Destination);
                            const float Demand = float(FMath::Clamp(Speed / (Species->RunSpeed * Scale), 0., 1.));
                            Fauna->Stamina = FMath::Max(0.f, Fauna->Stamina - Species->SprintDrain * Demand * float(Dt));
                            Transform.SetRotation(ToTarget.GetSafeNormal2D().ToOrientationQuat());
                        }
                    }
                }
                continue;
            }
            if (!Guard && (Now < Fauna->RootingUntil || Fauna->AttackContact >= 0.
                || (!bFleeing && Fauna->LastMeal >= 0. && Now - Fauna->LastMeal < 1.))) continue;
            const bool bHungry = bAdaptiveMeal ? Meal.bSeeking
                : Vitals.Energy < (Species->UsesPlantFood() ? .58f : .8f) * Vitals.MaxEnergy;
            // An ordinary meal should not grant early access to fallback stock shared with other species.
            const bool bNeedsSharedPlantPatch = bAdaptiveMeal ? Vitals.Energy < .58f * Vitals.MaxEnergy : bHungry;
            const auto* Claimed = FaunaCarcasses.Find(Fauna->CarrionTargetId);
            const bool bClaim = !Guard && !bFleeing && Claimed
                && Claimed->RetainsKillerTarget(Id.StableAgentId, Now, bCarrionAccess)
                && (bAdaptiveMeal ? bHungry : Vitals.Energy < .9f * Vitals.MaxEnergy);
            if (bClaim && Now < Claimed->OpenAt) continue;
            const bool bWantsCarrion = !Guard && !bFleeing && !bPassageTravel && Species->CarrionEnergyPerMeal > 0.f
                && (bAdaptiveMeal ? bHungry : Vitals.Energy < Species->CarrionHungerFraction * Vitals.MaxEnergy);
            const bool bUrgentCarrion = FaunaHabitatStage >= 3 && Species->HabitatCarrionRange > 0.f
                && !Fauna->bRecovering && Vitals.Energy < .45f * Vitals.MaxEnergy;
            const double CarrionTravelSpeed = Species->WalkSpeed + (bUrgentCarrion
                ? .7 * (Species->RunSpeed - Species->WalkSpeed) : 0.);
            const bool bFoodScan = Now >= Fauna->NextSense;
            if (!bClaim && !bWantsCarrion)
            {
                ReleaseCarrion(bAdaptiveMeal ? TEXT("MealCycleGate") : TEXT("CarrionHungerGate"));
            }
            else if (!bClaim && bFoodScan && Now >= Fauna->NextFoodSense)
            {
                Fauna->NextFoodSense = Now + .65;
                const int64 Previous = Fauna->CarrionTargetId;
                Fauna->CarrionTargetId = 0;
                double BestScore = 0.;
                for (const auto& Pair : FaunaCarcasses)
                {
                    if (Pair.Key == Fauna->BlockedCarrionId && Now < Fauna->BlockedCarrionUntil) continue;
                    const auto& Stock = Pair.Value;
                    const double Distance = FVector::Dist(Position, Stock.Position);
                    const float ScentLimit = Species->HabitatCarrionRange > 0.f ? Species->HabitatCarrionRange : Species->ScentRange;
                    const float CarrionRange = FMath::Max(Species->SightRange, ScentLimit);
                    if (Distance > CarrionRange || !Stock.IsAvailable(Region.CurrentRegionId, *Species, Now)
                        || !Stock.CanApproach(Id.StableAgentId, Now)
                        || Distance / CarrionTravelSpeed >= Stock.ExpiresAt - Now) continue;
                    const bool bSmelled = Species->ScentRange > 0.f
                        && Distance <= FMath::Min(ScentLimit, Species->ScentRange * FMath::Sqrt(Stock.Remaining / 20.f));
                    if (!bSmelled && (Distance > Species->SightRange || !HasClearSight(*GetWorld(), Position, Stock.Position, Species->EyeHeight,
                            FMath::Min(15.f, Species->EyeHeight)))) continue;
                    const double Score = EcoFaunaFeeding::Value(FMath::Min(Stock.Remaining, 3.f * Species->CarrionEnergyPerMeal),
                        Distance / CarrionTravelSpeed);
                    if (Score < BestScore || (Score == BestScore && Pair.Key >= Fauna->CarrionTargetId)) continue;
                    BestScore = Score;
                    Fauna->CarrionTargetId = Pair.Key;
                }
                if (bAuditFaunaHunts && Previous > 0 && Previous != Fauna->CarrionTargetId)
                {
                    const TCHAR* Reason = Fauna->CarrionTargetId > 0 ? TEXT("RescanSwitch")
                        : FaunaCarcasses.Contains(Previous) ? TEXT("RescanNoCandidate") : TEXT("StockRemoved");
                    AuditCarrionRelease(Previous, Reason);
                }
            }
            const auto* Stock = FaunaCarcasses.Find(Fauna->CarrionTargetId);
            const bool bAvailable = Stock && Stock->IsAvailable(Region.CurrentRegionId, *Species, Now);
            if (!bAvailable
                || (Now < Stock->ExclusiveUntil && Stock->KillerId != Id.StableAgentId))
            {
                ReleaseCarrion(!Stock ? TEXT("StockRemoved") : !bAvailable
                    ? TEXT("StockUnavailable") : TEXT("ExclusiveAccess"));
                Stock = nullptr;
            }
            const bool bSearching = !bClaim && !bFleeing && !bPassageTravel && !Fauna->bRecovering && bHungry && !Species->PreyRules.IsEmpty()
                && Fauna->Life.AgeFraction(Now) >= 1.;
            const bool bLocalPlantMeal = FaunaHabitatStage >= 2 && bFoodScan && Species->UsesPlantFood()
                && Context && Context->bSpatialFoodRegistered
                && Context->Sim.Food.Food[Context->Sim.Food.CellOf(Context->CmToUnits(Position))] >= Species->FoodPerMeal;
            const auto PatchScore = [&](int32 Index)
            {
                if (!FaunaPatchStock.IsValidIndex(Index) || FaunaPatchStock[Index] < .2f) return 0.;
                const auto& Patch = FaunaHabitatPatches[Index];
                if (Patch.Stage > FaunaHabitatStage || Patch.RegionId != Region.CurrentRegionId
                    || !Patch.Consumers.Contains(Id.SpeciesId)
                    || (Fauna->BlockedPatch == Index && Now < Fauna->PatchBlockedUntil)) return 0.;
                if (Species->UsesPlantFood() && Patch.ShelteredSpecies != Id.SpeciesId
                    && (!bNeedsSharedPlantPatch || FaunaPatchStock[Index] < Patch.EnergyPerMeal)) return 0.;
                const double Distance = FVector::Dist(Position, Patch.Center);
                if (bLocalPlantMeal && Patch.ShelteredSpecies != Id.SpeciesId && Distance > 35.) return 0.;
                if (Distance > Species->SightRange * 1.5
                    || !HasClearSight(*GetWorld(), Position, Patch.Center, Species->EyeHeight, 5.f)) return 0.;
                return EcoFaunaFeeding::Value(FMath::Min(FaunaPatchStock[Index], 3.f * Patch.EnergyPerMeal),
                    Distance / Species->WalkSpeed + 1.);
            };
            double PatchValue = 0.;
            if (!bFleeing && !Guard && !bPassageTravel)
            {
                if (bClaim || (bAdaptiveMeal ? !bHungry : Vitals.Energy >= .9f * Vitals.MaxEnergy)) Fauna->PatchTarget = INDEX_NONE;
                else if (bFoodScan)
                {
                    Fauna->PatchTarget = INDEX_NONE;
                    for (int32 Index = 0; Index < FaunaPatchStock.Num(); ++Index)
                    {
                        const double Value = PatchScore(Index);
                        if (Value <= PatchValue) continue;
                        PatchValue = Value;
                        Fauna->PatchTarget = Index;
                    }
                    if (Stock && PatchValue <= EcoFaunaFeeding::Value(
                        FMath::Min(Stock->Remaining, 3.f * Species->CarrionEnergyPerMeal),
                        FVector::Dist(Position, Stock->Position) / CarrionTravelSpeed))
                    {
                        Fauna->PatchTarget = INDEX_NONE;
                        PatchValue = 0.;
                    }
                }
                else if (FaunaPatchStock.IsValidIndex(Fauna->PatchTarget) && FaunaPatchStock[Fauna->PatchTarget] < .2f)
                    Fauna->PatchTarget = INDEX_NONE;
            }
            const bool bNesting = NestingParents.Contains(Id.StableAgentId);
            if (!Guard && !bPassageTravel && (!bAdaptiveMeal || !Meal.IsResting(Now)) && Now >= Fauna->NextDecision && (!bNesting || bHungry) && !bFleeing && !Stock
                && Fauna->PatchTarget == INDEX_NONE)
            {
                const uint32 Bout = ++Fauna->DecisionCount;
                const uint64 Seed = EcoLifeV3::Mix(uint64(Id.StableAgentId) ^ EcoLifeV3::Mix(Bout));
                const double Angle = EcoLifeV3::Unit(Seed) * UE_TWO_PI;
                const FVector Direction(FMath::Cos(Angle), FMath::Sin(Angle), 0.);
                const float Activity = Species->RoutineActivity(Darkness);
                if (bAdaptiveRoam)
                {
                    const double Radius = Species->RoutineHomeRadius
                        * FMath::Lerp(.55, 1., double(Activity))
                        * FMath::Lerp(.65, 1., double(Fauna->Stamina));
                    const double Distance = FVector::Dist2D(Position, Fauna->Home);
                    const double ReturnChance = FMath::Clamp(Distance / Radius - .35, 0., 1.);
                    Fauna->Goal = EcoLifeV3::Unit(Seed + 8) < ReturnChance ? Fauna->Home
                        : Fauna->Home + Direction * (Radius * FMath::Lerp(.3, 1., EcoLifeV3::Unit(Seed + 1)));
                }
                else
                    Fauna->Goal = Bout % 3 == 0 ? Fauna->Home
                        : Fauna->Home + Direction * (160. + 360. * EcoLifeV3::Unit(Seed + 1));
                Fauna->NextDecision = Now + 5. + 3. * EcoLifeV3::Unit(Seed + 2);
                if (!bHungry && EcoLifeV3::Unit(Seed + 7) >= Activity)
                {
                    Fauna->Goal = Position;
                    Fauna->RoutineRestUntil = Fauna->NextDecision;
                    continue;
                }
                Fauna->RoutineRestUntil = -1.;
                if (bSearching)
                {
                    const FVector Forward = Transform.GetRotation().GetForwardVector();
                    const FVector SearchHeading = Forward.RotateAngleAxis((EcoLifeV3::Unit(Seed) - .5) * 160., FVector::UpVector);
                    Fauna->Goal = Position + SearchHeading * Species->SightRange;
                    Fauna->NextDecision = Now + FMath::Clamp(Species->SightRange / Species->WalkSpeed, 5.f, 18.f);
                }
                if (bPersistence && bHungry && Fauna->LastForageIntakeAt >= 0.
                    && Now - Fauna->LastForageIntakeAt <= FaunaPersistence.ForageMemorySeconds
                    && Fauna->RecentForageIntake(Now, FaunaPersistence.ForageMemorySeconds) > 2.f * Species->Maintenance)
                {
                    const double Distance = FVector::Dist2D(Position, Fauna->ForageMemoryPosition);
                    if (Distance > Species->CarrionReach() && Distance <= 2. * Species->SightRange
                        && HasClearSight(*GetWorld(), Position, Fauna->ForageMemoryPosition, Species->EyeHeight, 5.f))
                        Fauna->Goal = Fauna->ForageMemoryPosition;
                }
                if (Context && Species->UsesPlantFood() && (bAdaptiveMeal ? bHungry : Vitals.Energy < .9f * Vitals.MaxEnergy))
                {
                    const auto* CurrentRegion = FindRegion(Position);
                    if (CurrentRegion && FindNearbyForage(*GetWorld(), Context, *CurrentRegion, Position, Fauna->Goal))
                    {
                        Fauna->NextDecision = Now + FMath::Clamp(FVector::Dist2D(Position, Fauna->Goal)
                            / FMath::Max(1.f, Species->WalkSpeed * .8f) + 2., 2., 25.);
                        if (Species->RootingSeconds > 0.f && Fauna->RootingUntil < 0. && Fauna->Goal.Equals(Position, 1.)
                            && PreviousVelocity.IsNearlyZero())
                        {
                            Fauna->RootingUntil = Now + Species->RootingSeconds * (.8 + .4 * EcoLifeV3::Unit(Seed + 3));
                            continue;
                        }
                    }
                }
                const double FlightChance = FMath::Lerp(.24, .08, double(Darkness)) * Activity;
                if (bCanFly && Fauna->Stamina >= .55f && EcoLifeV3::Unit(Seed + 4) < FlightChance
                    && Vitals.Energy >= .85f * Vitals.MaxEnergy && TryLaunch(Fauna->Home + Direction * 2000.)) continue;
            }

            TOptional<FVector> FlankGoal;
            if (bSearching && Now >= Fauna->AttackReady)
            {
                const double PursuitLimit = bAdaptivePursuitLimit ? Species->PursuitLimitSeconds : 12.;
                if (Fauna->ChaseBegan >= 0. && Now - Fauna->ChaseBegan > PursuitLimit)
                {
                    if (bAuditFaunaHunts)
                        UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Timeout"), Id.StableAgentId, *Id.SpeciesId.ToString());
                    RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("HuntPursuitTimeout"), Fauna->TargetId);
                    Fauna->TargetId = 0;
                    Fauna->ChaseBegan = -1.;
                    Fauna->LastPreySeenUntil = -1.;
                    Fauna->AttackReady = Now + 2.;
                    continue;
                }
                if (bFoodScan)
                {
                    Fauna->NextSense = Now + .45;
                    const int64 PreviousTarget = Fauna->TargetId;
                    Fauna->TargetId = 0;
                    double BestScore = 0.;
                    struct FPreyCandidate { FName Species; int64 Id; double Score; };
                    TArray<FPreyCandidate, TInlineAllocator<16>> Candidates;
                    TMap<FName, int32, TInlineSetAllocator<8>> Encounters;
                    TMap<FName, int32, TInlineSetAllocator<8>> Rejections;
                    int32 Eligible = 0;
                    const auto Consider = [&](int64 CandidateId, double Score)
                    {
                        if (Score > BestScore || (Score == BestScore && CandidateId < Fauna->TargetId))
                        {
                            Fauna->TargetId = CandidateId;
                            BestScore = Score;
                        }
                    };
                    for (const auto Prey : Owned)
                    {
                        const double Distance = FVector::Dist(Position, EM.GetFragmentDataChecked<FTransformFragment>(Prey).GetTransform().GetLocation());
                        const auto& PreyId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Prey);
                        const auto* Rule = Species->PreyRules.FindByPredicate([&](const auto& Entry) { return Entry.SpeciesId == PreyId.SpeciesId; });
                        if (!Rule || Distance > Species->SightRange) continue;
                        FName Rejection;
                        if (!CanHuntFauna(EM, Entity, Prey, *Species, Now, false, true, bAuditFaunaHunts ? &Rejection : nullptr))
                        {
                            if (bAuditFaunaHunts) ++Rejections.FindOrAdd(Rejection);
                            continue;
                        }
                        const auto& Health = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Prey);
                        const float Sight = FMath::Lerp(1.f, Species->NightVision, Darkness);
                        if (Distance > (Rule->MaxPursuitStart > 0.f ? FMath::Min(Species->SightRange, Rule->MaxPursuitStart)
                            : Species->SightRange) * Sight)
                        {
                            if (bAuditFaunaHunts) ++Rejections.FindOrAdd(TEXT("HuntNightRange"));
                            continue;
                        }
                        ++Eligible;
                        const double Vulnerability = 1. + .35 * (1. - Health.HP / Health.MaxHP);
                        const auto* PreyProfile = FindFauna(PreyId.SpeciesId);
                        const auto& PreyLife = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Prey).Life;
                        const double Maturity = PreyLife.AgeFraction(Now);
                        const double Resistance = PreyProfile->DefenseDamage * FMath::Lerp(.2, 1., Maturity)
                            * (Health.HP / Health.MaxHP);
                        const double Energy = FMath::Min(3. * Species->CarrionEnergyPerMeal,
                            PreyProfile->AdultCarrionEnergy > 0.f ? double(PreyProfile->AdultCarrionEnergy)
                            : 20. + 10. * FMath::Sqrt(PreyProfile->AdultMass * FMath::Lerp(.12, 1., Maturity)));
                        const double Handling = bAdaptivePreyValue && PreyProfile->DefenseDamage > 0.f
                            ? FMath::Max(0., FMath::CeilToDouble(Health.HP / (.45 * Health.MaxHP)) - 1.) * Species->AttackRecovery : 0.;
                        const double RiskWeight = bAdaptivePreyValue ? FMath::Lerp(.45, 1., double(Vitals.Energy / Vitals.MaxEnergy)) : 1.;
                        const double Score = EcoFaunaFeeding::Value(Energy * Rule->Preference * Vulnerability
                            * (PreyId.StableAgentId == PreviousTarget ? 1.15 : 1.),
                            Distance / Species->RunSpeed + Species->AttackWindup + Handling,
                            2. + Resistance * .55 * RiskWeight + (1. - Fauna->Stamina) * 5.);
                        if (bPersistence)
                        {
                            Candidates.Add({PreyId.SpeciesId, PreyId.StableAgentId, Score});
                            ++Encounters.FindOrAdd(PreyId.SpeciesId);
                        }
                        else Consider(PreyId.StableAgentId, Score);
                    }
                    for (const auto& Candidate : Candidates)
                        Consider(Candidate.Id, Candidate.Score * EcoFaunaFeeding::EncounterWeight(
                            Encounters.FindChecked(Candidate.Species), FaunaPersistence));
                    if (bAuditFaunaHunts)
                    {
                        UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Access Eligible=%d Carrion=%d Patch=%d"),
                            Id.StableAgentId, *Id.SpeciesId.ToString(), Eligible, int32(Stock != nullptr), int32(PatchValue > 0.));
                        for (const auto& Rejected : Rejections)
                            UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Reject Reason=%s Count=%d"),
                                Id.StableAgentId, *Id.SpeciesId.ToString(), *Rejected.Key.ToString(), Rejected.Value);
                    }
                    if (PatchValue > BestScore)
                    {
                        Fauna->TargetId = 0;
                        Fauna->ChaseBegan = -1.;
                    }
                    else if (Fauna->TargetId > 0) Fauna->PatchTarget = INDEX_NONE;
                    if (Stock && Fauna->PatchTarget == INDEX_NONE)
                    {
                        const double Carrion = EcoFaunaFeeding::Value(FMath::Min(Stock->Remaining, 3.f * Species->CarrionEnergyPerMeal),
                            FVector::Dist(Position, Stock->Position) / CarrionTravelSpeed);
                        const bool bChooseHunt = Fauna->TargetId > 0 && BestScore > Carrion * (PreviousTarget > 0 ? 1. : 1.15);
                        if (Fauna->TargetId > 0)
                            UE_LOG(LogTemp, Verbose, TEXT("[Eco Fauna][FoodChoice] Hunter=%lld Species=%s Live=%.2f Carrion=%.2f Selected=%s"),
                                Id.StableAgentId, *Id.SpeciesId.ToString(), BestScore, Carrion, bChooseHunt ? TEXT("Hunt") : TEXT("Carrion"));
                        if (bChooseHunt)
                        {
                            Stock = nullptr;
                            ReleaseCarrion(TEXT("LivePreyScore"));
                        }
                        else Fauna->TargetId = 0;
                    }
                    if (const auto* Prey = AgentLookup.Find(Fauna->TargetId))
                    {
                        const auto& PreyTransform = EM.GetFragmentDataChecked<FTransformFragment>(*Prey).GetTransform();
                        Fauna->LastPreyPosition = PreyTransform.GetLocation();
                        Fauna->LastPreySeenUntil = Now + 2.;
                        if (Fauna->ChaseBegan < 0. || (bPursuitFix && Fauna->TargetId != PreviousTarget))
                        {
                            Fauna->ChaseBegan = Now;
                            RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("HuntTargetAcquired"), Fauna->TargetId);
                            if (bAuditFaunaHunts)
                                UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Acquire Prey=%lld %s"),
                                    Id.StableAgentId, *Id.SpeciesId.ToString(), Fauna->TargetId,
                                    *EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Prey).SpeciesId.ToString());
                        }
                    }
                }
                if (Stock && Fauna->TargetId > 0)
                {
                    Stock = nullptr;
                    ReleaseCarrion(TEXT("LivePursuit"));
                }
                if (const auto* Prey = AgentLookup.Find(Fauna->TargetId))
                {
                    const auto& PreyTransform = EM.GetFragmentDataChecked<FTransformFragment>(*Prey).GetTransform();
                    const auto& PreyVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Prey);
                    const auto* PreyProfile = FindFauna(EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Prey).SpeciesId);
                    const FVector FromPrey = Position - PreyTransform.GetLocation();
                    const FVector Facing = PreyTransform.GetRotation().GetForwardVector().GetSafeNormal2D();
                    const bool bFlank = FaunaHabitatStage >= 3 && Species->bFlankDefendedPrey && PreyProfile
                        && PreyProfile->DefenseDamage > 0.f && PreyVitals.HP >= .35f * PreyVitals.MaxHP
                        && FromPrey.SizeSquared2D() < FMath::Square(3.f * Species->AttackReach)
                        && FVector::DotProduct(FromPrey.GetSafeNormal2D(), Facing) >= (bPursuitFix ? .25 : .15);
                    if (bFlank)
                    {
                        const FVector Side = FVector::CrossProduct(FVector::UpVector, Facing);
                        const double Sign = FVector::DotProduct(FromPrey, Side) < 0. ? -1. : 1.;
                        const FVector Route = PreyTransform.GetLocation() + Sign * Side * (1.1 * Species->AttackReach)
                            - Facing * (.45 * Species->AttackReach);
                        if (HasClearSight(*GetWorld(), Position, PreyTransform.GetLocation(), Species->EyeHeight, PreyProfile->EyeHeight)
                            && HasClearSight(*GetWorld(), Position, Route, Species->EyeHeight))
                            FlankGoal = Route;
                    }
                    const double Windup = FaunaHabitatStage >= 3 && Species->bFlankDefendedPrey
                        ? .5 * Species->AttackWindup : Species->AttackWindup;
                    const FVector PreyVelocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(*Prey).Value;
                    const double RetreatSpeed = FMath::Max(0., FVector::DotProduct(PreyVelocity, -FromPrey.GetSafeNormal2D()));
                    const double CarrySpeed = FMath::Max(double(Species->WalkSpeed) * Fauna->Life.SpeedScale(Now),
                        FVector::DotProduct(PreviousVelocity, -FromPrey.GetSafeNormal2D()));
                    const double ContactRange = FMath::Max(0., Species->AttackReach
                        - FMath::Max(0., RetreatSpeed - CarrySpeed) * Windup);
                    if (!bFlank && FromPrey.SizeSquared() <= FMath::Square(ContactRange)
                        && CanHuntFauna(EM, Entity, *Prey, *Species, Now, true))
                    {
                        Fauna->AttackContact = Now + Windup;
                        if (bAuditFaunaHunts)
                            UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Windup Prey=%lld"),
                                Id.StableAgentId, *Id.SpeciesId.ToString(), Fauna->TargetId);
                        continue;
                    }
                }
            }
            else
            {
                const auto* Target = bFollowWounded && bSearching && Fauna->TargetId > 0 ? AgentLookup.Find(Fauna->TargetId) : nullptr;
                if (Target && CanHuntFauna(EM, Entity, *Target, *Species, Now, false))
                {
                    Fauna->LastPreyPosition = EM.GetFragmentDataChecked<FTransformFragment>(*Target).GetTransform().GetLocation();
                    Fauna->LastPreySeenUntil = Now + 2.;
                    Stock = nullptr;
                    ReleaseCarrion(TEXT("WoundedPrey"));
                    Fauna->PatchTarget = INDEX_NONE;
                }
                else { Fauna->TargetId = 0; Fauna->ChaseBegan = -1.; Fauna->LastPreySeenUntil = -1.; }
            }
            if (bFoodScan && Now >= Fauna->NextSense) Fauna->NextSense = Now + .45;
            constexpr double CueArrivalDistance = 35.;
            const auto ClearReachedCue = [&](const FVector& Point, double& Until)
            {
                if (Now < Until && FVector::DistSquared2D(Position, Point) <= FMath::Square(CueArrivalDistance))
                    Until = -1.;
            };
            if (Fauna->TargetId == 0) ClearReachedCue(Fauna->LastPreyPosition, Fauna->LastPreySeenUntil);
            ClearReachedCue(Fauna->HeardPreyPosition, Fauna->HeardPreyUntil);
            ClearReachedCue(Fauna->ScentPosition, Fauna->ScentUntil);
            if (bFoodScan && bSearching && !Stock && Fauna->TargetId == 0 && Fauna->PatchTarget == INDEX_NONE
                && Context && Species->ScentRange > 0.f && Now >= Fauna->LastPreySeenUntil
                && Now >= Fauna->HeardPreyUntil && Now >= Fauna->ScentUntil)
            {
                FRegionEnvironmentState Weather;
                GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->GetEnvironmentState(Region.CurrentRegionId, Weather);
                const double Lifetime = FMath::Lerp(12., 4., double(FMath::Clamp(Weather.Rainfall, 0.f, 1.f)));
                const auto Local = Context->CmToUnits(Position);
                const EcoTracesV3::FTrace* Best = nullptr;
                double BestScore = 0.;
                if (const auto* Field = FaunaScent.Find(Region.CurrentRegionId))
                    Field->Query(Local.X, Local.Y, Now, [&](const auto& Cue)
                    {
                        if (Cue.Id <= Fauna->LastScentId || Now - Cue.Time >= Lifetime) return;
                        const auto* Source = AgentLookup.Find(Cue.Source);
                        if (!Source || !EM.IsEntityValid(*Source)) return;
                        const FName Kind = EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Source).SpeciesId;
                        if (!Species->PreyRules.ContainsByPredicate([Kind](const auto& Rule) { return Rule.SpeciesId == Kind; })) return;
                        const FVector Point = Context->UnitsToCm(Cue.X, Cue.Y, Cue.Z);
                        const double Distance = FVector::Dist(Position, Point);
                        if (Distance > Species->ScentRange
                            || FVector::DistSquared2D(Position, Point) <= FMath::Square(CueArrivalDistance)) return;
                        const double Score = (1. - (Now - Cue.Time) / Lifetime) / (1. + Distance / 250.);
                        if (Score > BestScore) { BestScore = Score; Best = &Cue; }
                    });
                if (Best)
                {
                    Fauna->LastScentId = Best->Id;
                    Fauna->ScentPosition = Context->UnitsToCm(Best->X, Best->Y, Best->Z);
                    Fauna->ScentUntil = Now + FMath::Min(5., Lifetime - (Now - Best->Time));
                    UE_LOG(LogTemp, Verbose, TEXT("[Eco Fauna][Scent] Hunter=%lld Species=%s Cue=%llu Age=%.2f"),
                        Id.StableAgentId, *Id.SpeciesId.ToString(), static_cast<unsigned long long>(Best->Id), Now - Best->Time);
                }
            }

            FVector Goal = Fauna->Goal;
            bool bRun = !bAdaptiveSprint && Fauna->DecisionCount % 5 == 0;
            double* InvestigatedUntil = nullptr;
            if (Guard)
            {
                Goal = Guard->Position;
                bRun = true;
            }
            else if (bFleeing)
            {
                FVector Away = (Position - Fauna->LastThreatPosition).GetSafeNormal2D();
                if (Now < Fauna->BlockedCarrionUntil && Fauna->BlockedCarrionId == 0)
                    Away = Away.RotateAngleAxis(Id.StableAgentId % 2 ? 65. : -65., FVector::UpVector);
                Goal = FaunaHabitatPatches.IsValidIndex(Fauna->PatchTarget)
                    ? FaunaHabitatPatches[Fauna->PatchTarget].Center : Position + Away * 600.;
                bRun = true;
            }
            else if (bPassageTravel)
            {
                Goal = Fauna->Goal;
                bRun = false;
            }
            else if (FaunaHabitatPatches.IsValidIndex(Fauna->PatchTarget))
            {
                Goal = FaunaHabitatPatches[Fauna->PatchTarget].Center;
                ReleaseCarrion(TEXT("HabitatPatch"));
                bRun = false;
            }
            else if (Stock)
            {
                const bool bInFeedingPosition = FVector::DistSquared(Position, Stock->Position) <= FMath::Square(.8 * Species->CarrionReach())
                    && HasClearSight(*GetWorld(), Position, Stock->Position, Species->EyeHeight, FMath::Min(15.f, Species->EyeHeight));
                Goal = bInFeedingPosition ? Position : Stock->Position;
                bRun = bUrgentCarrion && FVector::DistSquared2D(Position, Goal) > FMath::Square(140.);
            }
            else if (Fauna->TargetId > 0)
            {
                Goal = FlankGoal.Get(Fauna->LastPreyPosition);
                const double Range = FVector::Dist2D(Position, Goal);
                Fauna->bStalking = Range <= Species->StalkRange && Range > Species->AttackReach * 2.5;
                if (FaunaHabitatStage >= 3 && Species->bFlankDefendedPrey)
                    if (const auto* Target = AgentLookup.Find(Fauna->TargetId))
                        Fauna->bStalking &= Now >= EM.GetFragmentDataChecked<FEcoFaunaFragment>(*Target).ThreatUntil;
                bRun = !Fauna->bStalking;
            }
            else if (bSearching && Now < Fauna->LastPreySeenUntil)
            {
                Goal = Fauna->LastPreyPosition;
                bRun = false;
                InvestigatedUntil = &Fauna->LastPreySeenUntil;
            }
            else if (bSearching && Now < Fauna->HeardPreyUntil)
            {
                Goal = Fauna->HeardPreyPosition;
                bRun = false;
                InvestigatedUntil = &Fauna->HeardPreyUntil;
            }
            else if (bSearching && Now < Fauna->ScentUntil)
            {
                Goal = Fauna->ScentPosition;
                bRun = false;
                InvestigatedUntil = &Fauna->ScentUntil;
            }
            else if (!bHungry && (Now < Fauna->RoutineRestUntil || (bAdaptiveMeal && Meal.IsResting(Now))))
            {
                Goal = Position;
                bRun = false;
            }
            // A hungry dependent browser can stop and eat in its current cell.
            else if (bHungry && Species->CaregiverFollowRange > 0.f && Fauna->Life.AgeFraction(Now) < 1.
                && Species->UsesPlantFood() && LocalPlantStock(Context, Position) >= EcoFaunaNutrition::MinimumMeal)
            {
                Goal = Position;
                bRun = false;
            }
            else if (Species->CaregiverFollowRange > 0.f && Fauna->Life.AgeFraction(Now) < 1.
                && Vitals.Energy > .25f * Vitals.MaxEnergy)
            {
                const auto* Parent = AgentLookup.Find(Fauna->Life.Caregiver);
                if (Parent && EM.IsEntityValid(*Parent)
                    && EM.GetFragmentDataChecked<FEcoRegionFragment>(*Parent).CurrentRegionId == Region.CurrentRegionId
                    && EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Parent).HP > 0.f)
                {
                    const FVector ParentPosition = EM.GetFragmentDataChecked<FTransformFragment>(*Parent).GetTransform().GetLocation();
                    const FVector ToParent = ParentPosition - Position;
                    if (ToParent.SizeSquared2D() <= FMath::Square(Species->CaregiverFollowRange)
                        && HasClearSight(*GetWorld(), Position, ParentPosition))
                    {
                        const double Gap = FMath::Max(0., ToParent.Size2D() - 1.8 * Species->BodyRadius);
                        Goal = Position + ToParent.GetSafeNormal2D() * Gap;
                        bRun = Gap > 300.;
                        Fauna->bFollowingCaregiver = Gap > 18.;
                    }
                }
            }
            Fauna->bInvestigatingNoise = InvestigatedUntil != nullptr;
            const FVector Offset = Goal - Position;
            const double Distance = Offset.Size2D();
            bRun = bRun && !Fauna->bRecovering;
            const double Speed = Fauna->Life.SpeedScale(Now) * (bRun ? Species->RunSpeed : Species->WalkSpeed);
            const double Accel = Species->GroundAcceleration * Fauna->Life.SpeedScale(Now);
            const double StopRadius = bPassageTravel ? 2. : FMath::Min(18., .8 * Species->BodyRadius);
            const double StoppingSpeed = FMath::Sqrt(2. * Accel * FMath::Max(0., Distance - StopRadius));
            const FVector Desired = Offset.GetSafeNormal2D() * FMath::Min(Speed, StoppingSpeed);
            const FVector Motion = FMath::VInterpConstantTo(FVector(PreviousVelocity.X, PreviousVelocity.Y, 0.), Desired, Dt, Accel);
            if (Motion.IsNearlyZero()) continue;
            FVector Destination = Position + FVector(Motion.X, Motion.Y, 0.) * Dt;
            bool bCanAdvance = CanMoveOnGround(Destination);
            if (!bCanAdvance && (Stock || Fauna->PatchTarget != INDEX_NONE || bPassageTravel || Fauna->TargetId > 0) && !bFleeing && !Guard
                && Distance > StopRadius)
            {
                const FVector Direction = Offset.GetSafeNormal2D();
                const double StepLength = FMath::Min(Motion.Size2D(), Accel * Dt) * Dt;
                const double Side = Id.StableAgentId % 2 ? 1. : -1.;
                for (const double Turn : {35. * Side, -35. * Side, 70. * Side, -70. * Side})
                {
                    FVector Candidate = Position + Direction.RotateAngleAxis(Turn, FVector::UpVector) * StepLength;
                    if (FVector::DistSquared2D(Candidate, Goal) >= FMath::Square(Distance) || !CanMoveOnGround(Candidate)) continue;
                    Destination = Candidate;
                    bCanAdvance = true;
                    break;
                }
            }
            if (!bCanAdvance)
            {
                if (Stock)
                {
                    Fauna->BlockedCarrionId = Fauna->CarrionTargetId;
                    Fauna->BlockedCarrionUntil = Now + 5.;
                }
                if (bFleeing) { Fauna->BlockedCarrionId = 0; Fauna->BlockedCarrionUntil = Now + 1.; }
                if (Fauna->PatchTarget != INDEX_NONE)
                {
                    Fauna->BlockedPatch = Fauna->PatchTarget;
                    Fauna->PatchBlockedUntil = Now + 3.;
                    Fauna->PatchTarget = INDEX_NONE;
                }
                ReleaseCarrion(TEXT("BlockedRoute"));
                Fauna->NextFoodSense = Now + 1.;
                if (InvestigatedUntil) *InvestigatedUntil = -1.;
                Fauna->NextDecision = FMath::Min(Fauna->NextDecision, Now + .75);
                if (!bPassageTravel) Fauna->Goal = Position;
                continue;
            }
            Velocity = (Destination - Position) / Delta;
            if (bRun) Fauna->Stamina = FMath::Max(0.f, Fauna->Stamina - Species->SprintDrain * float(Dt));
            Transform.SetLocation(Destination);
            if (Context && Velocity.SizeSquared2D() >= FMath::Square(35.) && Now >= Fauna->NextScentDeposit)
            {
                const auto Local = Context->CmToUnits(Destination);
                FaunaScent.FindOrAdd(Region.CurrentRegionId).Add(Id.StableAgentId, Local.X, Local.Y, Destination.Z, Now);
                Fauna->NextScentDeposit = Now + 1.5;
            }
        }
        if (Velocity.SizeSquared2D() > 1.)
            Transform.SetRotation(Velocity.GetSafeNormal2D().ToOrientationQuat());
    }
}

#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"

#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Engine/World.h"
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

namespace
{
    TAutoConsoleVariable<int32> CVarFaunaHearingLog(TEXT("eco.Footsteps.HearingLog"), 0, TEXT("Log selected animal footstep evidence."));
    bool HasClearSight(const UWorld& World, const FVector& Start, const FVector& End,
        float EyeHeight = 35.f, float TargetHeight = 35.f)
    {
        return !World.LineTraceTestByObjectType(Start + FVector(0, 0, EyeHeight), End + FVector(0, 0, TargetHeight),
            FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaSight)));
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

bool AEcoCreatureIntegrationSpawner::CanHuntFauna(const FMassEntityManager& EM, FMassEntityHandle Hunter,
    FMassEntityHandle Prey, const FEcoFaunaSpecies& Profile, double Now, bool bContact, bool bCheckVisibility) const
{
    if (Hunter == Prey || !EM.IsEntityValid(Prey)) return false;
    const auto* Target = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Prey);
    if (!Target || Target->Flight != EEcoFaunaFlightPhase::Grounded) return false;
    const auto& Health = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Prey);
    const auto& PreyId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Prey);
    const auto* Rule = Profile.PreyRules.FindByPredicate([&](const auto& Entry) { return Entry.SpeciesId == PreyId.SpeciesId; });
    const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Hunter);
    if (!Rule || Health.HP <= 0.f || EM.GetFragmentDataChecked<FEcoRegionFragment>(Prey).CurrentRegionId != Region.CurrentRegionId)
        return false;
    const auto& HunterLife = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Hunter).Life;
    const auto Mass = [Now](const auto& Life, float AdultMass)
    {
        return AdultMass * FMath::Pow(Life.Genome.Size, 3.) * FMath::Lerp(.12, 1., Life.AgeFraction(Now));
    };
    const double MaturityLimit = Health.HP < .6f * Health.MaxHP ? Rule->MaxInjuredMaturity : Rule->MaxHealthyMaturity;
    if (HunterLife.AgeFraction(Now) < 1. || Target->Life.AgeFraction(Now) > MaturityLimit
        || Mass(Target->Life, FindFauna(PreyId.SpeciesId)->AdultMass) > Rule->MaxPreyMassRatio * Mass(HunterLife, Profile.AdultMass))
        return false;
    const auto& HunterTransform = EM.GetFragmentDataChecked<FTransformFragment>(Hunter).GetTransform();
    const FVector Start = HunterTransform.GetLocation();
    const FVector End = EM.GetFragmentDataChecked<FTransformFragment>(Prey).GetTransform().GetLocation();
    const auto* TargetProfile = FindFauna(PreyId.SpeciesId);
    if (bCheckVisibility)
        if (const auto* Shelter = FindFaunaShelter(Region.CurrentRegionId, PreyId.SpeciesId, End, 0.);
            Shelter && Profile.BodyRadius * HunterLife.BodyScale(Now) > Shelter->EntranceRadius) return false;
    const double Radius = bContact ? Profile.AttackReach
        : Rule->MaxPursuitStart > 0.f ? FMath::Min(Profile.SightRange, Rule->MaxPursuitStart) : Profile.SightRange;
    const double FovCos = FMath::Cos(FMath::DegreesToRadians(Profile.SightHalfAngle));
    if (bCheckVisibility && (FVector::DistSquared(Start, End) > FMath::Square(Radius)
        || (!bContact && FVector::DotProduct((End - Start).GetSafeNormal2D(), HunterTransform.GetRotation().GetForwardVector()) < FovCos)
        || !HasClearSight(*GetWorld(), Start, End, Profile.EyeHeight, TargetProfile->EyeHeight))) return false;
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
                return false;
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
        const auto* Prey = AgentLookup.Find(Fauna->TargetId);
        Fauna->TargetId = 0;
        const auto& HunterId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Hunter);
        const auto* Profile = FindFauna(HunterId.SpeciesId);
        Fauna->AttackReady = Now + Profile->AttackRecovery;
        Fauna->ChaseBegan = -1.;
        if (!Prey || EM.GetFragmentDataChecked<FEcoVitalsFragment>(Hunter).HP <= 0.
            || !CanHuntFauna(EM, Hunter, *Prey, *Profile, Now, true)) continue;
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
            UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Wounded] Hunter=%lld Prey=%lld HP=%.1f"),
                HunterId.StableAgentId, PreyId.StableAgentId, PreyVitals.HP);
            continue;
        }
        auto& Death = EM.GetFragmentDataChecked<FEcoDeathFragment>(*Prey);
        Death.Cause = EEcoDeathCause::Predation;
        Death.PredatorStableAgentId = HunterId.StableAgentId;
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
    FVector Ground;
    if (!GroundAt(Position, Ground)) return false;
    if (Fauna.Flight == EEcoFaunaFlightPhase::Takeoff && Now >= Fauna.PhaseUntil)
        Fauna.Flight = EEcoFaunaFlightPhase::Cruise;
    if (Fauna.Flight == EEcoFaunaFlightPhase::Cruise && FVector::DistSquared2D(Position, Fauna.LandingPoint) < FMath::Square(55.))
        Fauna.Flight = EEcoFaunaFlightPhase::Landing;

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
    const FVector Lift(0, 0, 18.);
    if (World.SweepTestByObjectType(Position + Lift, Destination + Lift, FQuat::Identity, Static,
        FCollisionShape::MakeSphere(10.f), Query))
    {
        Fauna.LandingPoint = Ground;
        Fauna.Flight = EEcoFaunaFlightPhase::Landing;
        return false;
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

void AEcoCreatureIntegrationSpawner::MoveFauna(float Delta, double Now)
{
    if (FaunaSpecies.IsEmpty() || Delta <= UE_SMALL_NUMBER) return;
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    TArray<FEcoNoiseEvent> Steps;
    if (FootstepAudioSet && !FootstepAudioSet->Profiles.IsEmpty())
        if (auto* Noise = GetWorld()->GetSubsystem<UEcoNoiseSubsystem>()) Noise->GatherRecent(Steps);
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
        const auto* Species = FindFauna(Id.SpeciesId);
        const auto* Context = Native ? Native->FindContext(Region.CurrentRegionId) : nullptr;
        auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform();
        auto& Velocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value;
        const FVector PreviousVelocity = Velocity;
        const FVector Position = Transform.GetLocation();
        const double Dt = FMath::Min(Delta, .1f);
        Velocity = FVector::ZeroVector;
        Fauna->bInvestigatingNoise = false;
        if (Fauna->Flight != EEcoFaunaFlightPhase::Grounded)
        {
            const auto PreviousFlight = Fauna->Flight;
            if (Vitals.HP <= 0.) Fauna->Flight = EEcoFaunaFlightPhase::Landing;
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
            if (Now >= Fauna->NextThreatSense)
            {
                Fauna->NextThreatSense = Now + .45;
                double BestThreat = FMath::Square(650.);
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
                        || (Distance > FMath::Square(280.) && FVector::DotProduct(
                            Offset.GetSafeNormal2D(), Transform.GetRotation().GetForwardVector()) < 0.)) continue;
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
                        const bool bPlayer = Noise.Tag == TEXT("Player.Footstep");
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
                    if (ThreatNoise && BestThreat >= FMath::Square(650.))
                    {
                        Fauna->LastThreatPosition = ThreatNoise->Position;
                        Fauna->ThreatUntil = Now + 1.5;
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
            const auto* Guard = GuardGoals.Find(Entity);
            if (Guard && Fauna->GuardThreatId != Guard->HunterId)
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][GuardApproach] Guard=%lld Species=%s Hunter=%lld"),
                    Id.StableAgentId, *Id.SpeciesId.ToString(), Guard->HunterId);
            Fauna->GuardThreatId = Guard ? Guard->HunterId : 0;
            if (Guard)
            {
                Fauna->CarrionTargetId = 0;
                Fauna->PatchTarget = INDEX_NONE;
                Fauna->RootingUntil = -1.;
            }
            const bool bFleeing = !Guard && Now < Fauna->ThreatUntil;
            if (bFleeing)
            {
                Fauna->RootingUntil = -1.;
                Fauna->CarrionTargetId = 0;
                Fauna->TargetId = 0;
                Fauna->AttackContact = -1.;
                Fauna->LastPreySeenUntil = -1.;
                Fauna->HeardPreyUntil = -1.;
                Fauna->ScentUntil = -1.;
                const auto* Shelter = FindFaunaShelter(Region.CurrentRegionId, Id.SpeciesId, Position, 650.);
                Fauna->PatchTarget = Shelter && HasClearSight(*GetWorld(), Position, Shelter->Center, Species->EyeHeight, 5.f)
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
                Fauna->CarrionTargetId = 0;
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
            if (!Guard && (Now < Fauna->RootingUntil || Fauna->AttackContact >= 0.
                || (!bFleeing && Fauna->LastMeal >= 0. && Now - Fauna->LastMeal < 1.))) continue;
            const bool bHungry = Vitals.Energy < (Species->UsesPlantFood() ? .58f : .8f) * Vitals.MaxEnergy;
            const float Darkness = Context ? float(Context->Sim.Dark) : 0.f;
            const auto* Claimed = FaunaCarcasses.Find(Fauna->CarrionTargetId);
            const bool bClaim = !bFleeing && Claimed && Claimed->KillerId == Id.StableAgentId
                && Now < Claimed->ExclusiveUntil && Vitals.Energy < .9f * Vitals.MaxEnergy;
            if (bClaim && Now < Claimed->OpenAt) continue;
            const bool bWantsCarrion = !Guard && !bFleeing && Species->CarrionEnergyPerMeal > 0.f
                && Vitals.Energy < Species->CarrionHungerFraction * Vitals.MaxEnergy;
            const bool bUrgentCarrion = FaunaHabitatStage >= 3 && Species->HabitatCarrionRange > 0.f
                && !Fauna->bRecovering && Vitals.Energy < .45f * Vitals.MaxEnergy;
            const double CarrionTravelSpeed = Species->WalkSpeed + (bUrgentCarrion
                ? .7 * (Species->RunSpeed - Species->WalkSpeed) : 0.);
            const bool bFoodScan = Now >= Fauna->NextSense;
            if (!bClaim && !bWantsCarrion) Fauna->CarrionTargetId = 0;
            else if (!bClaim && bFoodScan && Now >= Fauna->NextFoodSense)
            {
                Fauna->NextFoodSense = Now + .65;
                Fauna->CarrionTargetId = 0;
                double BestScore = 0.;
                for (const auto& Pair : FaunaCarcasses)
                {
                    if (Pair.Key == Fauna->BlockedCarrionId && Now < Fauna->BlockedCarrionUntil) continue;
                    const auto& Stock = Pair.Value;
                    const double Distance = FVector::Dist(Position, Stock.Position);
                    const float CarrionRange = FaunaHabitatStage >= 3
                        ? FMath::Max(Species->SightRange, Species->HabitatCarrionRange) : Species->SightRange;
                    if (Distance > CarrionRange || !Stock.IsAvailable(Region.CurrentRegionId, *Species, Now)
                        || !Stock.CanApproach(Id.StableAgentId, Now)
                        || Distance / CarrionTravelSpeed >= Stock.ExpiresAt - Now
                        || !HasClearSight(*GetWorld(), Position, Stock.Position, Species->EyeHeight, FMath::Min(15.f, Species->EyeHeight))) continue;
                    const double Score = EcoFaunaFeeding::Value(FMath::Min(Stock.Remaining, 3.f * Species->CarrionEnergyPerMeal),
                        Distance / CarrionTravelSpeed);
                    if (Score < BestScore || (Score == BestScore && Pair.Key >= Fauna->CarrionTargetId)) continue;
                    BestScore = Score;
                    Fauna->CarrionTargetId = Pair.Key;
                }
            }
            const auto* Stock = FaunaCarcasses.Find(Fauna->CarrionTargetId);
            if (!Stock || !Stock->IsAvailable(Region.CurrentRegionId, *Species, Now)
                || (Now < Stock->ExclusiveUntil && Stock->KillerId != Id.StableAgentId))
            {
                Stock = nullptr;
                Fauna->CarrionTargetId = 0;
            }
            const bool bSearching = !bClaim && !bFleeing && !Fauna->bRecovering && bHungry && !Species->PreyRules.IsEmpty()
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
                    && (!bHungry || FaunaPatchStock[Index] < Patch.EnergyPerMeal)) return 0.;
                const double Distance = FVector::Dist(Position, Patch.Center);
                if (bLocalPlantMeal && Patch.ShelteredSpecies != Id.SpeciesId && Distance > 35.) return 0.;
                if (Distance > Species->SightRange * 1.5
                    || !HasClearSight(*GetWorld(), Position, Patch.Center, Species->EyeHeight, 5.f)) return 0.;
                return EcoFaunaFeeding::Value(FMath::Min(FaunaPatchStock[Index], 3.f * Patch.EnergyPerMeal),
                    Distance / Species->WalkSpeed + 1.);
            };
            double PatchValue = 0.;
            if (!bFleeing && !Guard)
            {
                if (bClaim || Vitals.Energy >= .9f * Vitals.MaxEnergy) Fauna->PatchTarget = INDEX_NONE;
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
            const bool bNesting = FaunaBirths.ContainsByPredicate([&](const auto& Birth) {
                return Birth.ParentA == Id.StableAgentId || Birth.ParentB == Id.StableAgentId;
            });
            if (!Guard && Now >= Fauna->NextDecision && (!bNesting || bHungry) && !bFleeing && !Stock
                && Fauna->PatchTarget == INDEX_NONE)
            {
                const uint32 Bout = ++Fauna->DecisionCount;
                const uint64 Seed = EcoLifeV3::Mix(uint64(Id.StableAgentId) ^ EcoLifeV3::Mix(Bout));
                const double Angle = EcoLifeV3::Unit(Seed) * UE_TWO_PI;
                const FVector Direction(FMath::Cos(Angle), FMath::Sin(Angle), 0.);
                Fauna->Goal = Bout % 3 == 0 ? Fauna->Home
                    : Fauna->Home + Direction * (160. + 360. * EcoLifeV3::Unit(Seed + 1));
                Fauna->NextDecision = Now + 5. + 3. * EcoLifeV3::Unit(Seed + 2);
                const float Activity = Species->RoutineActivity(Darkness);
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
                if (Context && Species->UsesPlantFood() && Vitals.Energy < .9f * Vitals.MaxEnergy)
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
                if (Fauna->ChaseBegan >= 0. && Now - Fauna->ChaseBegan > 12.)
                {
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
                    for (const auto Prey : Owned)
                    {
                        const double Distance = FVector::Dist(Position, EM.GetFragmentDataChecked<FTransformFragment>(Prey).GetTransform().GetLocation());
                        if (Distance > Species->SightRange || !CanHuntFauna(EM, Entity, Prey, *Species, Now, false)) continue;
                        const auto& PreyId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Prey);
                        const auto& Health = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Prey);
                        const auto* Rule = Species->PreyRules.FindByPredicate([&](const auto& Entry) { return Entry.SpeciesId == PreyId.SpeciesId; });
                        const float Sight = FMath::Lerp(1.f, Species->NightVision, Darkness);
                        if (Distance > (Rule->MaxPursuitStart > 0.f ? FMath::Min(Species->SightRange, Rule->MaxPursuitStart)
                            : Species->SightRange) * Sight) continue;
                        const double Vulnerability = 1. + .35 * (1. - Health.HP / Health.MaxHP);
                        const auto* PreyProfile = FindFauna(PreyId.SpeciesId);
                        const auto& PreyLife = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Prey).Life;
                        const double Maturity = PreyLife.AgeFraction(Now);
                        const double Resistance = PreyProfile->DefenseDamage * FMath::Lerp(.2, 1., Maturity)
                            * (Health.HP / Health.MaxHP);
                        const double Energy = FMath::Min(3. * Species->CarrionEnergyPerMeal,
                            PreyProfile->AdultCarrionEnergy > 0.f ? double(PreyProfile->AdultCarrionEnergy)
                            : 20. + 10. * FMath::Sqrt(PreyProfile->AdultMass * FMath::Lerp(.12, 1., Maturity)));
                        const double Score = EcoFaunaFeeding::Value(Energy * Rule->Preference * Vulnerability
                            * (PreyId.StableAgentId == PreviousTarget ? 1.15 : 1.),
                            Distance / Species->RunSpeed + Species->AttackWindup,
                            2. + Resistance * .55 + (1. - Fauna->Stamina) * 5.);
                        if (Score < BestScore || (Score == BestScore && PreyId.StableAgentId >= Fauna->TargetId)) continue;
                        Fauna->TargetId = PreyId.StableAgentId;
                        BestScore = Score;
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
                            Fauna->CarrionTargetId = 0;
                        }
                        else Fauna->TargetId = 0;
                    }
                    if (const auto* Prey = AgentLookup.Find(Fauna->TargetId))
                    {
                        const auto& PreyTransform = EM.GetFragmentDataChecked<FTransformFragment>(*Prey).GetTransform();
                        Fauna->LastPreyPosition = PreyTransform.GetLocation();
                        Fauna->LastPreySeenUntil = Now + 2.;
                        if (Fauna->ChaseBegan < 0.) Fauna->ChaseBegan = Now;
                    }
                }
                if (Stock && Fauna->TargetId > 0)
                {
                    Stock = nullptr;
                    Fauna->CarrionTargetId = 0;
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
                        && FVector::DotProduct(FromPrey.GetSafeNormal2D(), Facing) >= .15;
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
                    else if (CanHuntFauna(EM, Entity, *Prey, *Species, Now, true))
                    {
                        Fauna->AttackContact = Now + (FaunaHabitatStage >= 3 && Species->bFlankDefendedPrey
                            ? .5f * Species->AttackWindup : Species->AttackWindup);
                        continue;
                    }
                }
            }
            else { Fauna->TargetId = 0; Fauna->ChaseBegan = -1.; Fauna->LastPreySeenUntil = -1.; }
            if (bFoodScan && Now >= Fauna->NextSense) Fauna->NextSense = Now + .45;
            if (Now < Fauna->ScentUntil && FVector::DistSquared2D(Position, Fauna->ScentPosition) <= FMath::Square(35.))
                Fauna->ScentUntil = -1.;
            if (bFoodScan && bSearching && !Stock && Fauna->TargetId == 0 && Fauna->PatchTarget == INDEX_NONE
                && Context && Species->ScentRange > 0.f)
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
                        if (Distance < 30. || Distance > Species->ScentRange) return;
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
            bool bRun = Fauna->DecisionCount % 5 == 0;
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
            else if (FaunaHabitatPatches.IsValidIndex(Fauna->PatchTarget))
            {
                Goal = FaunaHabitatPatches[Fauna->PatchTarget].Center;
                Fauna->CarrionTargetId = 0;
                bRun = false;
            }
            else if (Stock)
            {
                Goal = Stock->Position;
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
                Fauna->bInvestigatingNoise = true;
            }
            else if (bSearching && Now < Fauna->HeardPreyUntil)
            {
                Goal = Fauna->HeardPreyPosition;
                bRun = false;
                Fauna->bInvestigatingNoise = true;
            }
            else if (bSearching && Now < Fauna->ScentUntil)
            {
                Goal = Fauna->ScentPosition;
                bRun = false;
                Fauna->bInvestigatingNoise = true;
            }
            else if (!bHungry && Now < Fauna->RoutineRestUntil)
            {
                Goal = Position;
                bRun = false;
            }
            // Newborns inherit less than the ordinary hunger threshold. They can stay near
            // their parent and still feed whenever they stop. Critical hunger releases following.
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
            const FVector Offset = Goal - Position;
            const double Distance = Offset.Size2D();
            bRun = bRun && !Fauna->bRecovering;
            const double Speed = Fauna->Life.SpeedScale(Now) * (bRun ? Species->RunSpeed : Species->WalkSpeed);
            const double Accel = Species->GroundAcceleration * Fauna->Life.SpeedScale(Now);
            const double StoppingSpeed = FMath::Sqrt(2. * Accel * FMath::Max(0., Distance - FMath::Min(18., .8 * Species->BodyRadius)));
            const FVector Desired = Offset.GetSafeNormal2D() * FMath::Min(Speed, StoppingSpeed);
            const FVector Motion = FMath::VInterpConstantTo(FVector(PreviousVelocity.X, PreviousVelocity.Y, 0.), Desired, Dt, Accel);
            if (Motion.IsNearlyZero()) continue;
            FVector Destination = Position + FVector(Motion.X, Motion.Y, 0.) * Dt;
            const float Radius = FMath::Clamp(float(Species->BodyRadius * Fauna->Life.BodyScale(Now)), 1.f, 120.f);
            const bool bGrounded = EcoCreatureMovement::ConstrainGroundStep(*GetWorld(), Position, Destination, Radius, .65f,
                Species->SweepHeight * float(Fauna->Life.BodyScale(Now)), Species->StepHeight);
            const auto* DestinationRegion = bGrounded ? FindRegion(Destination) : nullptr;
            if (!DestinationRegion || DestinationRegion->RegionId != Region.CurrentRegionId
                || FMath::Abs(Destination.Z - Position.Z) > Species->StepHeight
                || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Destination, Species->WadeDepth))
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
                Fauna->CarrionTargetId = 0;
                Fauna->NextFoodSense = Now + 1.;
                if (Fauna->bInvestigatingNoise) Fauna->ScentUntil = -1.;
                Fauna->NextDecision = FMath::Min(Fauna->NextDecision, Now + .75);
                Fauna->Goal = Position;
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

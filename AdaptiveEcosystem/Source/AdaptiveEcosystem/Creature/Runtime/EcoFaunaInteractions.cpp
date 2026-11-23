#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"

#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoFaunaDecision.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassMovementFragments.h"
#include "MassSpawnerSubsystem.h"

namespace
{
    constexpr double ScanInterval = .20;
    constexpr double SignalLifetime = 1.8;
    constexpr double SignalCooldown = 4.;
    constexpr double ConfirmationWindow = 3.;
    constexpr double MealReturnWindow = 22.;
    constexpr double ExposureDistance = 550.;
    constexpr double DefenseCommitment = 2.4;
    constexpr double DefenseRecovery = 5.;

    FVector Location(const FMassEntityManager& Manager, FMassEntityHandle Entity)
    {
        return Manager.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform().GetLocation();
    }

    bool GroundSight(const UWorld& World, const FVector& From, const FVector& To, double EyeHeight, double TargetHeight)
    {
        return EcoFaunaDecision::HasClearSight(World, From, To, float(EyeHeight), float(TargetHeight));
    }

    bool ConnectedWater(UWorld& World, FName Region, const FVector& From, const FVector& To)
    {
        if (!EcoCreatureMovement::HasClearWaterSight(World, From, To)) return false;
        const int32 Segments = FMath::Max(1, FMath::CeilToInt(FVector::Dist(From, To) / 60.));
        for (int32 Index = 0; Index <= Segments; ++Index)
        {
            const FVector Position = FMath::Lerp(From, To, double(Index) / Segments);
            EcoCreatureMovement::FFaunaWaterColumn Column;
            if (!EcoCreatureMovement::SampleFaunaWater(World, Region, Position, 1., Column)
                || Position.Z <= Column.Bottom || Position.Z >= Column.Surface) return false;
        }
        return true;
    }

    bool CanPerceive(UWorld& World, FName Region, EEcoEncounterMedium Medium, const FTransform& Receiver,
        const FVector& Point, double Range, double HalfAngle, double EyeHeight, double TargetHeight)
    {
        const FVector Position = Receiver.GetLocation();
        const FVector Offset = Point - Position;
        if (Offset.SizeSquared() > FMath::Square(Range)) return false;
        const FVector Direction = Medium == EEcoEncounterMedium::Ground ? Offset.GetSafeNormal2D() : Offset.GetSafeNormal();
        if (Offset.SizeSquared() > FMath::Square(85.)
            && FVector::DotProduct(Direction, Receiver.GetRotation().GetForwardVector())
                < FMath::Cos(FMath::DegreesToRadians(HalfAngle))) return false;
        return Medium == EEcoEncounterMedium::Water ? ConnectedWater(World, Region, Position, Point)
            : GroundSight(World, Position, Point, EyeHeight, TargetHeight);
    }

    bool EligibleDefender(const FEcoFaunaSpecies& Species, const FEcoFaunaFragment& Fauna,
        const FEcoVitalsFragment& Vitals, double Now)
    {
        return Species.DefenseDamage > 0.f && Fauna.Life.AgeFraction(Now) >= 1.
            && Fauna.Stamina >= .35f && !Fauna.bRecovering && Vitals.HP >= .55f * Vitals.MaxHP
            && Vitals.Energy >= .25f * Vitals.MaxEnergy && Fauna.AttackContact < 0.
            && Now >= Fauna.ThreatUntil
            && !Fauna.bSwimming && Fauna.Flight == EEcoFaunaFlightPhase::Grounded;
    }
}

void AEcoCreatureIntegrationSpawner::UpdateFaunaInteractions(FMassEntityManager& Manager, double Now, float Darkness)
{
    if (!bAuthorityWorld || FaunaInteractionMode == 0 || Now < NextFaunaInteractionScan) return;
    NextFaunaInteractionScan = Now + ScanInterval;
    auto& World = *GetWorld();
    const auto Living = [&](int64 Id) -> const FMassEntityHandle*
    {
        const auto* Entity = AgentLookup.Find(Id);
        return Entity && Manager.IsEntityValid(*Entity)
            && Manager.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity).HP > 0.f ? Entity : nullptr;
    };
    const auto RegionOf = [&](FMassEntityHandle Entity)
    {
        return Manager.GetFragmentDataChecked<FEcoRegionFragment>(Entity).CurrentRegionId;
    };
    const auto SourceId = [&](FMassEntityHandle Entity) -> const FEcoIdentityFragment&
    {
        return Manager.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
    };
    for (auto It = FaunaHuntSignals.CreateIterator(); It; ++It)
        if (Now >= It.Value().At + SignalCooldown || !Living(It.Key())) It.RemoveCurrent();
    for (auto It = FaunaReactions.CreateIterator(); It; ++It)
        if (Now >= It.Value().ConfirmUntil + MealReturnWindow || !Living(It.Key())) It.RemoveCurrent();
    for (auto It = FaunaInterpositions.CreateIterator(); It; ++It)
        if (Now >= It.Value().RestUntil || !Living(It.Key())) It.RemoveCurrent();

    TMap<FName, TArray<FMassEntityHandle>> RegionalDefenders;
    for (const auto Entity : Owned)
    {
        const auto* Fauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
        if (!Fauna) continue;
        const auto* Species = FindFauna(SourceId(Entity).SpeciesId);
        if (Species && EligibleDefender(*Species, *Fauna, Manager.GetFragmentDataChecked<FEcoVitalsFragment>(Entity), Now)
            && Manager.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State != EEcoResidenceState::Traveling)
            RegionalDefenders.FindOrAdd(RegionOf(Entity)).Add(Entity);
    }

    for (const auto Hunter : Owned)
    {
        const auto& HunterId = SourceId(Hunter);
        const auto* HunterFauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(Hunter);
        const auto* NativeThreat = Manager.GetFragmentDataPtr<FEcoThreatStateFragment>(Hunter);
        const auto* NativeLink = NativeThreat ? Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Hunter) : nullptr;
        const int64 Target = HunterFauna ? HunterFauna->TargetId
            : NativeLink && NativeThreat->Agent.Last.bHunting ? NativeLink->LastSeenPreyKey : 0;
        const auto* Prey = Target > 0 ? Living(Target) : nullptr;
        if (!Prey || !Living(HunterId.StableAgentId)) continue;
        const FName Region = RegionOf(Hunter);
        if (Region.IsNone() || RegionOf(*Prey) != Region) continue;
        const auto& PreyId = SourceId(*Prey);
        const auto* Profile = FindFauna(PreyId.SpeciesId);
        const auto* Predator = FindFauna(HunterId.SpeciesId);
        const FVector Danger = Location(Manager, Hunter);
        const auto& Body = Manager.GetFragmentDataChecked<FTransformFragment>(*Prey).GetTransform();
        const FVector Position = Body.GetLocation();
        const auto Medium = EncounterMedium(Manager, *Prey);
        const double Range = Profile ? FMath::Min(1000.f, Profile->ThreatSenseRange * FMath::Lerp(1.f, Profile->NightVision, Darkness)) : 1000.;
        const double Eye = Profile ? Profile->EyeHeight : 55.;
        const double HunterEye = Predator ? Predator->EyeHeight : 55.;
        const FVector Velocity = Manager.GetFragmentDataChecked<FMassVelocityFragment>(*Prey).Value;
        const double EscapeSpeed = (Profile ? Profile->WalkSpeed : 150.) * (Medium == EEcoEncounterMedium::Water ? .55 : 1.);
        const bool bMovingAway = Velocity.SizeSquared() > FMath::Square(EscapeSpeed)
            && FVector::DotProduct(Velocity, Position - Danger) > 0.;
        auto* Existing = FaunaHuntSignals.Find(Target);
        if (CanPerceive(World, Region, Medium, Body, Danger, Range, Profile ? Profile->ThreatSightHalfAngle : 100., Eye, HunterEye))
        {
            if (!Existing || (Existing->At == Now && HunterId.StableAgentId < Existing->Hunter)
                || Existing->Region != Region || Existing->Medium != Medium)
                Existing = &FaunaHuntSignals.Add(Target, {HunterId.StableAgentId, Target, Now, Region, PreyId.SpeciesId, Medium, Position});
            if (Existing->Hunter == HunterId.StableAgentId)
            {
                Existing->DirectEscape = (Position - Danger).GetSafeNormal();
                Existing->DirectUntil = Now + ScanInterval * 2.;
            }
        }
        // The target can turn away as soon as it flees. Seeing its motion does not require
        // it to keep looking at the predator that originally triggered the cue.
        if (Existing && Existing->Hunter == HunterId.StableAgentId && Existing->Region == Region && Existing->Medium == Medium
            && Now < Existing->At + SignalLifetime && bMovingAway)
        {
            Existing->Escape = Velocity.GetSafeNormal();
            Existing->Position = Position;
        }
        if (Medium != EEcoEncounterMedium::Ground || EncounterMedium(Manager, Hunter) != EEcoEncounterMedium::Ground
            || FVector::DistSquared(Position, Danger) > FMath::Square(650.)) continue;
        // An adult defends its immediate space. A nearby vulnerable animal can use the opening.
        const auto* Defenders = RegionalDefenders.Find(Region);
        if (!Defenders) continue;
        for (const auto Guard : *Defenders)
        {
            if (Guard == Hunter || Guard == *Prey) continue;
            const auto& Identity = SourceId(Guard);
            if (Identity.SpeciesId == PreyId.SpeciesId) continue;
            const auto* GuardProfile = FindFauna(Identity.SpeciesId);
            auto* Previous = FaunaInterpositions.Find(Identity.StableAgentId);
            if (Previous && (Now >= Previous->CommitUntil
                || (Previous->Hunter != HunterId.StableAgentId && Previous->Hunter < HunterId.StableAgentId))) continue;
            const auto& GuardBody = Manager.GetFragmentDataChecked<FTransformFragment>(Guard).GetTransform();
            const FVector Origin = GuardBody.GetLocation();
            const double DefenseRange = FMath::Clamp(5. * GuardProfile->BodyRadius, 150., 500.);
            if (FVector::DistSquared(Origin, Position) > FMath::Square(DefenseRange)
                || FMath::Abs(Origin.Z - Position.Z) > GuardProfile->StepHeight + GuardProfile->BodyRadius
                || !CanPerceive(World, Region, Medium, GuardBody, Danger, DefenseRange,
                    GuardProfile->ThreatSightHalfAngle, GuardProfile->EyeHeight, HunterEye)) continue;
            const auto Direction = (Danger - Position).GetSafeNormal2D();
            if (Direction.IsNearlyZero()) continue;
            const FVector Goal = Position + Direction * FMath::Min(GuardProfile->BodyRadius * 2., FVector::Dist2D(Danger, Position) * .5);
            FVector Ground;
            if (!EcoCreatureMovement::ProjectSpawnPoint(World, Goal, Ground)
                || !EcoCreatureMovement::IsWadeableGround(World, Ground, GuardProfile->WadeDepth)) continue;
            if (!Previous || Previous->Hunter != HunterId.StableAgentId || Previous->Prey != Target)
            {
                RecordGameplayReason(Identity.StableAgentId, Region, Now, TEXT("FaunaDefenseOpportunity"), Target);
                const double CommitUntil = Previous ? Previous->CommitUntil : Now + DefenseCommitment;
                const double RestUntil = Previous ? Previous->RestUntil : CommitUntil + DefenseRecovery;
                Previous = &FaunaInterpositions.Add(Identity.StableAgentId,
                    {Target, HunterId.StableAgentId, Region, Ground, 0., CommitUntil, RestUntil});
            }
            Previous->Position = Ground;
            Previous->Until = FMath::Min(Previous->CommitUntil, Now + ScanInterval * 2.);
        }
    }

    for (const auto& Pair : FaunaHuntSignals)
        if (Pair.Value.At == Now)
            RecordGameplayReason(Pair.Key, Pair.Value.Region, Now, Pair.Value.Medium == EEcoEncounterMedium::Water
                ? TEXT("FaunaWaterThreatSeen") : TEXT("FaunaAlarmEmitted"), Pair.Value.Hunter);

    for (const auto Entity : Owned)
    {
        const auto& Identity = SourceId(Entity);
        if (!Living(Identity.StableAgentId)) continue;
        const FName Region = RegionOf(Entity);
        const auto Medium = EncounterMedium(Manager, Entity);
        const auto* Profile = FindFauna(Identity.SpeciesId);
        const auto& Body = Manager.GetFragmentDataChecked<FTransformFragment>(Entity).GetTransform();
        const double Sight = Profile ? Profile->ThreatSenseRange * FMath::Lerp(1.f, Profile->NightVision, Darkness) : 900.;
        const double Eye = Profile ? Profile->EyeHeight : 55.;
        const double HalfAngle = Profile ? Profile->ThreatSightHalfAngle : 100.;
        auto* Previous = FaunaReactions.Find(Identity.StableAgentId);
        if (Previous && Now <= Previous->ConfirmUntil && !Previous->bConfirmed && Previous->Key.Region == Region
            && Previous->Key.Medium == Medium)
        {
            const auto* Hunter = Living(Previous->Signal.Hunter);
            if (Hunter && RegionOf(*Hunter) == Region
                && CanPerceive(World, Region, Medium, Body, Location(Manager, *Hunter), Sight, HalfAngle, Eye,
                    Medium == EEcoEncounterMedium::Water ? 0. : 35.))
            {
                Previous->bConfirmed = true;
                FaunaExperience.FindOrAdd(Identity.StableAgentId).ObserveEncounter(Previous->Key, Now, 1.);
                RecordGameplayReason(Identity.StableAgentId, Region, Now, TEXT("FaunaCueConfirmed"), Previous->Signal.Source);
            }
        }
        if (Previous && Now < Previous->ConfirmUntil) continue;
        const FFaunaHuntSignal* Best = nullptr;
        double BestScore = 0.;
        FEcoEncounterKey BestKey;
        for (const auto& Pair : FaunaHuntSignals)
        {
            const auto& Signal = Pair.Value;
            if (Now >= Signal.At + SignalLifetime || Signal.Region != Region
                || Signal.Species == Identity.SpeciesId || Signal.Hunter == Identity.StableAgentId
                || (Previous && Previous->Signal.Source == Signal.Source && Previous->Signal.At == Signal.At)) continue;
            const double Distance = FVector::Dist(Body.GetLocation(), Signal.Position);
            if (Distance >= ExposureDistance || (Signal.Medium == EEcoEncounterMedium::Water) != (Medium == EEcoEncounterMedium::Water)) continue;
            const bool bVisibleEscape = !Signal.Escape.IsNearlyZero()
                && CanPerceive(World, Region, Medium, Body, Signal.Position, Sight, HalfAngle, Eye,
                    Medium == EEcoEncounterMedium::Water ? 0. : 25.);
            const bool bClear = bVisibleEscape || GroundSight(World, Body.GetLocation(), Signal.Position, Eye, 25.);
            if (Medium == EEcoEncounterMedium::Water && !bVisibleEscape) continue;
            const auto* Hunter = Living(Signal.Hunter);
            if (!Hunter || RegionOf(*Hunter) != Region) continue;
            const FEcoEncounterKey Key{bVisibleEscape ? EEcoEncounterKind::Escape : EEcoEncounterKind::Alarm,
                Medium, Region, Signal.Species};
            const auto* Memory = FindFaunaExperience(Identity.StableAgentId);
            const auto* Estimate = Memory ? Memory->FindEncounter(Key) : nullptr;
            const double Confidence = (bVisibleEscape ? 1. : bClear ? .8 : .3)
                * (1. - Distance / ExposureDistance) * (Estimate ? Estimate->Factor(Now) : 1.);
            if (Confidence < .18 || Confidence < BestScore
                || (Confidence == BestScore && Best && Signal.Source >= Best->Source)) continue;
            Best = &Signal;
            BestScore = Confidence;
            BestKey = Key;
        }
        if (!Best) continue;
        const FVector Escape = BestKey.Kind == EEcoEncounterKind::Escape ? Best->Escape : FVector::ZeroVector;
        FaunaReactions.Add(Identity.StableAgentId, {*Best, Now + (Escape.IsNearlyZero() ? .6 : 1.2),
            Now + ConfirmationWindow, Escape, BestKey});
        RecordGameplayReason(Identity.StableAgentId, Region, Now, Escape.IsNearlyZero()
            ? TEXT("FaunaAlarmHeard") : TEXT("FaunaEscapeSeen"), Best->Source, float(BestScore));
    }
}

const AEcoCreatureIntegrationSpawner::FFaunaReaction* AEcoCreatureIntegrationSpawner::ReadFaunaReaction(
    int64 Agent, FName Region, EEcoEncounterMedium Medium, double Now) const
{
    if (FaunaInteractionMode != 2 || !bAuthorityWorld) return nullptr;
    const auto* Reaction = FaunaReactions.Find(Agent);
    return Reaction && Reaction->Key.Region == Region && Reaction->Key.Medium == Medium
        && Now < Reaction->Until ? Reaction : nullptr;
}

void AEcoCreatureIntegrationSpawner::ApplyFaunaReaction(int64 Agent, double Now)
{
    auto& Reaction = FaunaReactions.FindChecked(Agent);
    if (Reaction.bApplied) return;
    Reaction.bApplied = true;
    RecordGameplayReason(Agent, Reaction.Key.Region, Now, TEXT("FaunaRespondedToCue"), Reaction.Signal.Source);
}

double AEcoCreatureIntegrationSpawner::ProtectionPreference(int64 Agent, int64 Neighbor, FName Region,
    FName NeighborSpecies, double Now) const
{
    if (FaunaInteractionMode != 2) return 1.;
    const auto* Memory = FindFaunaExperience(Agent);
    const auto* Evidence = Memory ? Memory->FindEncounter({EEcoEncounterKind::Defense,
        EEcoEncounterMedium::Ground, Region, NeighborSpecies}) : nullptr;
    if (!Evidence || Evidence->Factor(Now) < 1.02) return 1.;
    const auto& Manager = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Entity = AgentLookup.Find(Neighbor);
    const auto* Species = FindFauna(NeighborSpecies);
    if (!Species || !Entity || !Manager.IsEntityValid(*Entity)) return 1.;
    const auto* Fauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(*Entity);
    return Fauna && EligibleDefender(*Species, *Fauna, Manager.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity), Now)
        ? Evidence->Factor(Now) : 1.;
}

FVector AEcoCreatureIntegrationSpawner::DirectFaunaWaterEscape(int64 Agent, FName Region, double Now) const
{
    if (FaunaInteractionMode != 2 || !bAuthorityWorld) return FVector::ZeroVector;
    const auto* Signal = FaunaHuntSignals.Find(Agent);
    return Signal && Signal->Region == Region && Signal->Medium == EEcoEncounterMedium::Water
        && Now < Signal->DirectUntil ? Signal->DirectEscape : FVector::ZeroVector;
}

double AEcoCreatureIntegrationSpawner::InteractionFoodFactor(int64 Agent, FName Region,
    EEcoEncounterMedium Medium, const FVector& Position, double Now) const
{
    const auto* Reaction = ReadFaunaReaction(Agent, Region, Medium, Now);
    if (!Reaction) return 1.;
    const double Exposure = FMath::Max(0., 1. - FVector::Dist(Position, Reaction->Signal.Position) / ExposureDistance);
    return 1. - .4 * Exposure;
}

void AEcoCreatureIntegrationSpawner::ObserveFaunaReactionMeal(int64 Agent, FName Region, double Now, double Paid)
{
    if (FaunaInteractionMode != 2 || Paid <= UE_SMALL_NUMBER) return;
    auto* Reaction = FaunaReactions.Find(Agent);
    if (!Reaction || !Reaction->bApplied || Reaction->Key.Region != Region || Now < Reaction->Until
        || Now >= Reaction->ConfirmUntil + MealReturnWindow) return;
    Reaction->bApplied = false;
    RecordGameplayReason(Agent, Region, Now, TEXT("FaunaMealResumedAfterCue"), Reaction->Signal.Source, float(Paid));
}

bool AEcoCreatureIntegrationSpawner::BlocksFaunaCapture(int64 Hunter, int64 Prey, const FVector& Start,
    const FVector& End, double Now, bool bCommitContact)
{
    if (FaunaInteractionMode != 2 || !bAuthorityWorld) return false;
    auto& Manager = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Target = AgentLookup.Find(Prey);
    if (!Target || !Manager.IsEntityValid(*Target)) return false;
    const FName Region = Manager.GetFragmentDataChecked<FEcoRegionFragment>(*Target).CurrentRegionId;
    const FVector Ray = End - Start;
    int64 BestId = 0;
    FName BestSpecies;
    double BestAlong = 1.;
    for (auto& Pair : FaunaInterpositions)
    {
        auto& Defense = Pair.Value;
        if (Defense.Prey != Prey || Defense.Hunter != Hunter || Defense.Region != Region || Now >= Defense.Until) continue;
        const auto* Guard = AgentLookup.Find(Pair.Key);
        if (!Guard || !Manager.IsEntityValid(*Guard)
            || Manager.GetFragmentDataChecked<FEcoRegionFragment>(*Guard).CurrentRegionId != Region) continue;
        const auto& Identity = Manager.GetFragmentDataChecked<FEcoIdentityFragment>(*Guard);
        const auto* Species = FindFauna(Identity.SpeciesId);
        const auto* Fauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(*Guard);
        if (!Species || !Fauna || !EligibleDefender(*Species, *Fauna,
            Manager.GetFragmentDataChecked<FEcoVitalsFragment>(*Guard), Now)) continue;
        const FVector Position = Location(Manager, *Guard);
        const FVector Center = Position + FVector(0., 0., Species->EyeHeight * .5);
        const double Along = FVector::DotProduct(Center - Start, Ray) / FMath::Max(1., Ray.SizeSquared());
        const double Radius = Species->BodyRadius * Fauna->Life.BodyScale(Now);
        if (Along <= 0. || Along > BestAlong || (Along == BestAlong && Pair.Key >= BestId)
            || FVector::DistSquared(Start + Ray * Along, Center) > FMath::Square(Radius)
            || !GroundSight(*GetWorld(), Position, Start, Species->EyeHeight, 45.)) continue;
        BestId = Pair.Key;
        BestSpecies = Identity.SpeciesId;
        BestAlong = Along;
    }
    if (BestId == 0) return false;
    if (!bCommitContact) return true;
    auto& Defense = FaunaInterpositions.FindChecked(BestId);
    auto& Defender = Manager.GetFragmentDataChecked<FEcoFaunaFragment>(AgentLookup.FindChecked(BestId));
    Defender.Stamina = FMath::Max(0.f, Defender.Stamina - .12f);
    Defense.Until = Defense.CommitUntil = Now;
    Defense.RestUntil = Now + DefenseRecovery;
    FaunaExperience.FindOrAdd(Prey).ObserveEncounter({EEcoEncounterKind::Defense,
        EEcoEncounterMedium::Ground, Region, BestSpecies}, Now, 1.);
    RecordGameplayReason(Prey, Region, Now, TEXT("FaunaAttackIntercepted"), BestId);
    RecordGameplayReason(BestId, Region, Now, TEXT("FaunaDefenseIntercepted"), Prey);
    return true;
}

void AEcoCreatureIntegrationSpawner::ResetFaunaInteractions()
{
    FaunaHuntSignals.Reset();
    FaunaReactions.Reset();
    FaunaInterpositions.Reset();
    NextFaunaInteractionScan = 0.;
}

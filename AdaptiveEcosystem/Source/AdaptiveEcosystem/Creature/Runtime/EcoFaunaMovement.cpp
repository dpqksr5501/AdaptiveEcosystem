#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoFaunaDecision.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
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
#include "World/EcoWorldClockSubsystem.h"
#include "HAL/IConsoleManager.h"
#include "GameFramework/Pawn.h"
#include "Creature/Player/EcoPlayerEcologyComponent.h"
#include "Player/EcoPlayerState.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#endif

using EcoFaunaDecision::FitsFaunaPrey;
using EcoFaunaDecision::HasClearSight;

namespace
{
    int64 GroundFoodAuditAgent()
    {
        static const int64 AgentId = [] {
            int64 Requested = 0;
            FParse::Value(FCommandLine::Get(), TEXT("EcoGroundFoodAuditAgent="), Requested);
            return Requested;
        }();
        return AgentId;
    }

    int64 PassageAuditAgent()
    {
        static const int64 AgentId = [] {
            int64 Requested = 0;
            FParse::Value(FCommandLine::Get(), TEXT("EcoIslandPassageAuditAgent="), Requested);
            return Requested;
        }();
        return AgentId;
    }

    float GroundMaintenanceDemand(const FEcoFaunaSpecies& Species, double Speed)
    {
        return FMath::Lerp(Species.RestingMaintenanceFraction, 1.f,
            float(FMath::Clamp(Speed / Species.RunSpeed, 0., 1.)));
    }

    TAutoConsoleVariable<int32> CVarFaunaHearingLog(TEXT("eco.Footsteps.HearingLog"), 0, TEXT("Log selected animal footstep evidence."));
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
        const FVector& Position, const FEcoFaunaSpecies& Species, float BodyScale, FVector& Out)
    {
        if (!Context || !Context->bSpatialFoodRegistered) return false;
        const auto& Grid = Context->Sim.Food;
        const auto Point = Context->CmToUnits(Position);
        if (Point.X < 0. || Point.Y < 0. || Point.X > Context->Sim.Config.WorldSize || Point.Y > Context->Sim.Config.WorldSize)
            return false;
        const int32 Current = Grid.CellOf(Point);
        const float MinStock = Species.bIndividualResponse
            ? FMath::Max(EcoFaunaNutrition::MinimumMeal, .4f * Species.FoodPerMeal)
            : EcoFaunaNutrition::MinimumMeal;
        if (Grid.Food[Current] >= MinStock)
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
                if (Food < MinStock) continue;
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
            if (Species.bIndividualResponse)
            {
                FVector Entrance = Position + (Ground - Position).GetClampedToMaxSize2D(30.);
                if (!EcoCreatureMovement::ConstrainGroundStep(World, Position, Entrance,
                        FMath::Clamp(Species.BodyRadius * BodyScale, 1.f, 120.f), Species.MinGroundNormalZ,
                        Species.SweepHeight * BodyScale, Species.StepHeight)
                    || !EcoCreatureMovement::IsWadeableGround(World, Entrance, Species.WadeDepth)) continue;
            }
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoWaterCarcassStockTest, "AdaptiveEcosystem.Fauna.Water.CarcassAccess",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoWaterCarcassStockTest::RunTest(const FString&)
{
    FEcoFaunaCarcass Stock;
    Stock.Region = TEXT("TestPool");
    Stock.Species = TEXT("CommonCarp");
    Stock.OpenAt = 2.;
    Stock.ExpiresAt = 20.;
    Stock.KillerId = 12;
    Stock.ExclusiveUntil = 4.;
    Stock.FeedingPlaces = 1;
    Stock.Remaining = 6.f;
    Stock.bGrounded = false;
    Stock.bWaterborne = true;
    TestEqual(TEXT("Ground consumers cannot use submerged stock"), Stock.Bite(12, 3., 4.f), 0.f);
    TestEqual(TEXT("Exclusive claim prevents simultaneous consumption"), Stock.Bite(13, 3., 4.f, true), 0.f);
    TestEqual(TEXT("A reachable swimmer takes one bite"), Stock.Bite(12, 3., 4.f, true), 4.f);
    Stock.bGrounded = true;
    Stock.bWaterborne = false;
    TestEqual(TEXT("Stranding removes water access"), Stock.Bite(12, 5., 4.f, true), 0.f);
    TestEqual(TEXT("Stranded stock conserves the remaining amount"), Stock.Bite(13, 5., 4.f), 2.f);
    TestEqual(TEXT("Empty stock cannot be paid twice"), Stock.Bite(12, 6., 4.f), 0.f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FEcoFaunaPreyConditionTest, "AdaptiveEcosystem.Fauna.Hunt.SizeAgeAndHealth",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FEcoFaunaPreyConditionTest::RunTest(const FString&)
{
    FEcoFaunaSpecies Hunter, Prey;
    Hunter.AdultMass = 5.f;
    Prey.AdultMass = 3.f;
    FEcoFaunaPreyRule Rule;
    Rule.MaxHealthyMaturity = .45f;
    Rule.MaxInjuredMaturity = .8f;
    Rule.MaxPreyMassRatio = .45f;
    EcoLifeV3::FIndividual HunterLife, PreyLife;
    HunterLife.MaturitySeconds = PreyLife.MaturitySeconds = 100.;
    HunterLife.Born = 0.;
    PreyLife.Born = 40.;
    FEcoVitalsFragment Vitals;
    Vitals.HP = Vitals.MaxHP = 100.f;
    TestFalse(TEXT("Healthy older prey rejects the same reach"), FitsFaunaPrey(Rule, Hunter, Prey, HunterLife, PreyLife, Vitals, 100.));
    Vitals.HP = 40.f;
    TestTrue(TEXT("Injury changes eligibility at the same age and size"), FitsFaunaPrey(Rule, Hunter, Prey, HunterLife, PreyLife, Vitals, 100.));
    PreyLife.Genome.Size = 1.1;
    TestFalse(TEXT("The largest injured prey still exceeds the body mass ratio"),
        FitsFaunaPrey(Rule, Hunter, Prey, HunterLife, PreyLife, Vitals, 100.));
    PreyLife.Born = 75.;
    Vitals.HP = 100.f;
    TestTrue(TEXT("The same hunter can reach younger healthy prey"), FitsFaunaPrey(Rule, Hunter, Prey, HunterLife, PreyLife, Vitals, 100.));
    HunterLife.Born = 15.;
    TestFalse(TEXT("An immature hunter cannot execute a capture"), FitsFaunaPrey(Rule, Hunter, Prey, HunterLife, PreyLife, Vitals, 100.));
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
    const bool bHuntingInWater = Profile.IsAquatic() || EM.GetFragmentDataChecked<FEcoFaunaFragment>(Hunter).bSwimming;
    if ((TargetProfile->IsAquatic() || Target->bSwimming) != bHuntingInWater)
        return Reject(TEXT("HuntTargetInOtherMedium"));
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
        const FVector SightDirection = bHuntingInWater ? (End - Start).GetSafeNormal() : (End - Start).GetSafeNormal2D();
        if (!bContact && FVector::DotProduct(SightDirection, HunterTransform.GetRotation().GetForwardVector()) < FovCos)
            return Reject(TEXT("HuntOutsideView"));
        if (!HasClearSight(*GetWorld(), Start, End, bHuntingInWater ? 0.f : Profile.EyeHeight,
                bHuntingInWater ? 0.f : TargetProfile->EyeHeight))
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
    FMassEntityHandle Child, FMassEntityHandle Hunter, double Now, const FEcoFaunaSpecies* ContactHunterProfile) const
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
        if (FVector::DistSquared(Position, YoungPosition) > FMath::Square(Profile->OffspringGuardRange)
            || !HasClearSight(*GetWorld(), Position, Danger, Profile->EyeHeight)) continue;
        if (ContactHunterProfile)
        {
            const FVector ContactPoint = FMath::ClosestPointOnSegment(Position, Danger, YoungPosition);
            if (FVector::DistSquared(Position, ContactPoint) > FMath::Square(Profile->BodyRadius + 35.f)
                || FVector::DotProduct(Position - YoungPosition, Danger - YoungPosition) <= 0.
                || !HasClearSight(*GetWorld(), Position, Danger, Profile->EyeHeight, ContactHunterProfile->EyeHeight)) continue;
        }
        return *Guard;
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
            {
                const double Gap = Prey && EM.IsEntityValid(*Prey)
                    ? FVector::Dist(EM.GetFragmentDataChecked<FTransformFragment>(Hunter).GetTransform().GetLocation(),
                        EM.GetFragmentDataChecked<FTransformFragment>(*Prey).GetTransform().GetLocation()) : -1.;
                UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Miss Reason=%s Prey=%lld GapCm=%.1f ReachCm=%.1f"),
                    HunterId.StableAgentId, *HunterId.SpeciesId.ToString(), *Rejection.ToString(), AttemptedTarget, Gap, Profile->AttackReach);
            }
            continue;
        }
        const auto& PreyId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Prey);
        auto& HunterVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Hunter);
        auto& PreyVitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Prey);
        auto& Defender = EM.GetFragmentDataChecked<FEcoFaunaFragment>(*Prey);
        const auto* PreyProfile = FindFauna(PreyId.SpeciesId);
        const auto& PreyTransform = EM.GetFragmentDataChecked<FTransformFragment>(*Prey).GetTransform();
        const FVector HunterPosition = EM.GetFragmentDataChecked<FTransformFragment>(Hunter).GetTransform().GetLocation();
        const auto Guard = SelectFaunaGuard(EM, *Prey, Hunter, Now, Profile);
        if (Guard.IsSet())
        {
            const auto& GuardTransform = EM.GetFragmentDataChecked<FTransformFragment>(Guard).GetTransform();
            const FVector GuardPosition = GuardTransform.GetLocation();
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
        bool bWater = false;
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
                auto& Passage = Passages.Add_GetRef(FPassage{Source.RegionId, Destination.RegionId, Seam, FarSide, {Seam},
                    Route.bRuleFaunaWaterPassage});
                for (; Route.Points.IsValidIndex(Index) && FindRegion(Route.Points[Index]) == &Source; Index += Direction)
                    if (!Route.Points[Index].Equals(Passage.Approach[0], 1.))
                        Passage.Approach.Insert(Route.Points[Index], 0);
            };
            AddPassage(*From, *To, Entry, Exit, I - 1, -1);
            if (Route.bBidirectional) AddPassage(*To, *From, Exit, Entry, I, 1);
        }
    }
    TSet<FName> TransitRegions;
    TSet<FName> RulesOnlyRegions;
    for (const auto& Group : Groups)
        if (Group.bRulesOnly)
        {
            RulesOnlyRegions.Add(Group.RegionId);
            if (Group.bFaunaTransit) TransitRegions.Add(Group.RegionId);
        }
    if (Passages.IsEmpty() && !bAuditFaunaHunts && !Owned.ContainsByPredicate([&](FMassEntityHandle Entity)
        {
            return EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity)
                && EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity).State == EEcoResidenceState::Traveling;
        })) return;
    TMap<FName, int32> Load;
    TMap<FName, TMap<FName, int32>> FaunaLoad;
    TMap<FName, int32> TransitReservations;
    TMap<FName, TMap<FName, int32>> TransitSpeciesReservations;
    TMap<FName, TArray<FMassEntityHandle>> GroundedResidents;
    TSet<int64> Caregivers;
    const auto FindTransitEntry = [&](FName From, const FEcoTravelFragment& Travel)
    {
        return Passages.FindByPredicate([&](const FPassage& Passage)
        {
            return !Passage.bWater && Passage.From == From && TransitRegions.Contains(Passage.To)
                && Passage.Entry.Equals(Travel.TargetPosition, .1);
        });
    };
    const auto AdjustTransitReservation = [&](FName Area, FName Species, int32 Delta)
    {
        TransitReservations.FindOrAdd(Area) += Delta;
        TransitSpeciesReservations.FindOrAdd(Area).FindOrAdd(Species) += Delta;
    };
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
            {
                ++FaunaLoad.FindOrAdd(Travel.TargetRegionId).FindOrAdd(Species);
                if (const auto* Entry = FindTransitEntry(Region.CurrentRegionId, Travel))
                    AdjustTransitReservation(Entry->To, Species, 1);
            }
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
        const bool bAquatic = Species && Species->IsAquatic();
        auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
        auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity);
        auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform();
        const FVector Position = Transform.GetLocation();
        const bool bTraveling = Travel.State == EEcoResidenceState::Traveling;
        const bool bInTransit = TransitRegions.Contains(Region.CurrentRegionId);
        const bool bAuditPassage = Id.StableAgentId == PassageAuditAgent();
        const auto RecordPassageDecision = [&](const TCHAR* Reason) {
            if (!bAuditPassage) return;
            UE_LOG(LogTemp, Log, TEXT("[Eco Passage Decision] Id=%lld At=%.3f Region=%s Event=%s Energy=%.3f Patch=%s NextDecision=%.3f"),
                Id.StableAgentId, Now, *Region.CurrentRegionId.ToString(), Reason, Vitals.Energy,
                *(FaunaHabitatPatches.IsValidIndex(Fauna->PatchTarget)
                    ? FaunaHabitatPatches[Fauna->PatchTarget].Id : NAME_None).ToString(), Travel.NextDecisionTime);
        };
        const bool bEligible = Species && (bAquatic || !Fauna->bSwimming)
            && Fauna->Flight == EEcoFaunaFlightPhase::Grounded
            && Fauna->Life.AgeFraction(Now) >= 1. && !Caregivers.Contains(Id.StableAgentId)
            && Now >= Fauna->ThreatUntil && Fauna->GuardThreatId == 0 && Fauna->CarrionTargetId == 0
            && Fauna->PatchTarget == INDEX_NONE && Now >= Fauna->RootingUntil
            && Fauna->TargetId == 0 && Fauna->AttackContact < 0.;
        const auto CancelTravel = [&]()
        {
            if (!bTraveling) return;
            --Load.FindOrAdd(Travel.TargetRegionId);
            --FaunaLoad.FindOrAdd(Travel.TargetRegionId).FindOrAdd(Id.SpeciesId);
            if (const auto* Entry = FindTransitEntry(Region.CurrentRegionId, Travel))
                AdjustTransitReservation(Entry->To, Id.SpeciesId, -1);
            const double LastArrival = Travel.LastArrivalTime;
            Travel = FEcoTravelFragment();
            Travel.LastArrivalTime = LastArrival;
            Travel.NextDecisionTime = Now + 5.;
            Fauna->Goal = Position;
            Fauna->NextDecision = Now;
            if (bAquatic)
            {
                RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("WaterPassageCancelled"));
                if (bAuditFaunaHunts)
                    UE_LOG(LogTemp, Log, TEXT("[Eco Passage Audit] Id=%lld Species=%s Region=%s Event=WaterReservationReleased"),
                        Id.StableAgentId, *Id.SpeciesId.ToString(), *Region.CurrentRegionId.ToString());
            }
        };
        if (!bEligible)
        {
            RecordPassageDecision(Fauna->PatchTarget != INDEX_NONE ? TEXT("LocalPatchTarget") : TEXT("Ineligible"));
            CancelTravel();
            continue;
        }
        if (!bTraveling && Now < Travel.NextDecisionTime)
        {
            RecordPassageDecision(TEXT("DecisionCooldown"));
            continue;
        }
        const double MealStartEnergy = Species->MealStart() * Vitals.MaxEnergy;
        const bool bHungry = Vitals.Energy < MealStartEnergy;
        if (!bTraveling && !bInTransit && !bHungry && bAquatic) continue;
        const auto ReportNoPassage = [&](const TCHAR* Reason)
        {
            RecordPassageDecision(Reason);
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
        if (!Passages.ContainsByPredicate([&](const auto& Passage) {
            return Passage.From == Region.CurrentRegionId && Passage.bWater == bAquatic;
        }))
        {
            ReportNoPassage(TEXT("NoOutgoingSeam"));
            CancelTravel();
            continue;
        }
        FRegionEcologyState Origin;
        if (!Ecology->GetRegionState(Region.CurrentRegionId, Origin)) { CancelTravel(); continue; }
        const double WaterClearance = bAquatic ? FMath::Max(1., Species->BodyRadius * Fauna->Life.BodyScale(Now) * .65) : 1.;
        const float BodyScale = Fauna->Life.BodyScale(Now);
        const float GroundRadius = FMath::Clamp(Species->BodyRadius * BodyScale, 1.f, 120.f);
        const double HealthFraction = FMath::Clamp(double(Vitals.HP / FMath::Max(1.f, Vitals.MaxHP)), 0., 1.);
        const double WalkCondition = Species->bIndividualResponse
            ? FMath::Lerp(.55, 1., HealthFraction) * FMath::Lerp(.75, 1., double(Fauna->Stamina)) : 1.;
        const auto IsGroundStepUsable = [&](const FVector& From, FVector& To)
        {
            return EcoCreatureMovement::ConstrainGroundStep(*GetWorld(), From, To, GroundRadius,
                    Species->MinGroundNormalZ, Species->SweepHeight * BodyScale, Species->StepHeight)
                && FMath::Abs(To.Z - From.Z) <= Species->StepHeight
                && EcoCreatureMovement::IsWadeableGround(*GetWorld(), To, Species->WadeDepth);
        };
        const auto HasOpenGroundExit = [&](const FPassage& Passage)
        {
            // Authored passages share habitat reports. Check the short physical exit
            // before reserving the destination or approaching it from the corridor.
            const FVector Direction = (Passage.Exit - Passage.Entry).GetSafeNormal2D();
            const FVector Approach = Passage.Approach.Num() > 1
                ? Passage.Approach[Passage.Approach.Num() - 2] : Passage.Entry;
            const FVector Inward = Direction.IsNearlyZero() ? (Passage.Entry - Approach).GetSafeNormal2D() : Direction;
            const double Backtrack = FMath::Min(2. * GroundRadius + 60., FVector::Dist2D(Approach, Passage.Entry));
            FVector From = Passage.Entry - Inward * Backtrack;
            if (FindRegion(From) != FindRegion(Passage.Entry)
                || !EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), From, From)) return true;
            const FVector Start = From;
            const int32 Steps = FMath::Max(1, FMath::CeilToInt(FVector::Dist2D(Start, Passage.Exit) / 20.));
            for (int32 Index = 1; Index <= Steps; ++Index)
            {
                FVector To = FMath::Lerp(Start, Passage.Exit, double(Index) / Steps);
                To.Z = From.Z;
                if (!IsGroundStepUsable(From, To)) return false;
                From = To;
            }
            return FMath::Abs(From.Z - Passage.Exit.Z) <= Species->StepHeight;
        };
        const auto SampleWaterLeg = [&](const FVector& Start, const FVector& End, FName First, FName Second, bool bExactDepth)
        {
            // Bound speculative scans of long authored legs. The movement sweep and
            // exact short seam still validate each committed displacement.
            const int32 Segments = FMath::Clamp(FMath::CeilToInt(FVector::Dist(Start, End) / 18.), 1, 64);
            const FVector Direction = (End - Start).GetSafeNormal2D();
            for (int32 Step = 0; Step <= Segments; ++Step)
            {
                const FVector Point = FMath::Lerp(Start, End, double(Step) / Segments);
                const auto* At = FindRegion(Point);
                EcoCreatureMovement::FFaunaWaterColumn Water;
                if (!At || (At->RegionId != First && At->RegionId != Second)
                    || !EcoCreatureMovement::SampleFaunaWater(*GetWorld(), At->RegionId, Point, WaterClearance, Water)
                    || FVector::DotProduct(Water.Current, Direction) <= -.45 * Species->WalkSpeed * Fauna->Life.SpeedScale(Now)
                    || (bExactDepth && (Point.Z < Water.Bottom + WaterClearance || Point.Z > Water.Surface - WaterClearance)))
                    return false;
            }
            return true;
        };
        const auto EstimateMeals = [&](FName Area, const FRegionEcologyState& State,
            const FVector& AccessPoint, double ETA, bool bNewResident, bool bLocalPlants,
            double GroundReach = TNumericLimits<double>::Max())
        {
            const int32 Extra = bNewResident ? 1 : 0;
            const auto* Native = bLocalPlants ? GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
            const auto* Context = Native ? Native->FindContext(Area) : nullptr;
            FVector PlantSite;
            const auto* PlantRegion = Context ? FindRegion(AccessPoint) : nullptr;
            const double PlantStock = bLocalPlants
                ? (PlantRegion && PlantRegion->RegionId == Area && FindNearbyForage(*GetWorld(), Context, *PlantRegion,
                    AccessPoint, *Species, BodyScale, PlantSite)
                    && FVector::Dist2D(AccessPoint, PlantSite) < GroundReach ? LocalPlantStock(Context, PlantSite) : 0.)
                : State.FoodAmount;
            const double PlantMeals = Species->UsesPlantFood()
                ? PlantStock / (Species->FoodPerMeal * FMath::Max(1, State.ProjectedFoodConsumers + Extra)) : 0.;
            double PatchMeals = 0.;
            const auto* AreaResidents = FaunaLoad.Find(Area);
            for (int32 Index = 0; Index < FaunaPatchStock.Num(); ++Index)
            {
                const auto& Patch = FaunaHabitatPatches[Index];
                const float Stock = FaunaPatchStock[Index];
                if (Patch.bSubmerged != bAquatic || Patch.RegionId != Area || Patch.Stage > FaunaHabitatStage
                    || FMath::Min(Stock, Patch.EnergyPerMeal) < .2f
                    || !Patch.Consumers.Contains(Id.SpeciesId)) continue;
                bool bReachablePoint = false;
                for (int32 PointIndex = 0; PointIndex <= Patch.ForageAccessPoints.Num(); ++PointIndex)
                {
                    const FVector Point = Patch.ForagePoint(PointIndex);
                    if ((Fauna->BlockedPatch == Index && Fauna->BlockedPatchAccessPoint == PointIndex
                            && ETA < Fauna->PatchBlockedUntil)
                        || FVector::DistSquared(AccessPoint, Point) > FMath::Square(1.5 * Species->SightRange)) continue;
                    if (bAquatic)
                    {
                        EcoCreatureMovement::FFaunaWaterColumn Water;
                        if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Area, Point, WaterClearance, Water)
                            || Point.Z <= Water.Bottom || Point.Z >= Water.Surface
                            || !SampleWaterLeg(AccessPoint, Point, Area, Area, false)) continue;
                    }
                    else if (FVector::Dist2D(AccessPoint, Point) >= GroundReach
                        || !HasClearSight(*GetWorld(), AccessPoint, Point, Species->EyeHeight, 5.f)
                        || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Point, Species->WadeDepth)) continue;
                    bReachablePoint = true;
                    break;
                }
                if (!bReachablePoint) continue;
                int32 Competitors = Extra;
                if (AreaResidents)
                    for (const auto& Resident : *AreaResidents)
                        if (Patch.Consumers.Contains(Resident.Key)) Competitors += Resident.Value;
                PatchMeals += Species->PlantPreference(Patch.PlantGuild) * Stock / (Patch.EnergyPerMeal * FMath::Max(1, Competitors));
            }
            double AnimalMeals = 0.;
            if (Species->CarrionEnergyPerMeal > 0.f)
                for (const auto& Pair : FaunaCarcasses)
                {
                    const auto& Stock = Pair.Value;
                    if (!Stock.IsAvailable(Area, *Species, ETA, bAquatic) || !Stock.CanApproach(Id.StableAgentId, ETA, bAquatic)) continue;
                    if (FVector::Dist2D(AccessPoint, Stock.Position) >= GroundReach) continue;
                    const double Distance = FVector::Dist(AccessPoint, Stock.Position);
                    if (Distance / Species->WalkSpeed >= Stock.ExpiresAt - ETA) continue;
                    const float ScentLimit = Species->HabitatCarrionRange > 0.f ? Species->HabitatCarrionRange : Species->ScentRange;
                    const bool bScent = !bAquatic && Species->ScentRange > 0.f
                        && Distance <= FMath::Min(ScentLimit, Species->ScentRange * FMath::Sqrt(Stock.Remaining / 20.f));
                    const bool bDirectAccess = Distance <= Species->SightRange && (bAquatic
                        ? SampleWaterLeg(AccessPoint, Stock.Position, Area, Area, true)
                        : HasClearSight(*GetWorld(), AccessPoint, Stock.Position, Species->EyeHeight, FMath::Min(15.f, Species->EyeHeight)));
                    if (bScent || bDirectAccess) AnimalMeals += Stock.Remaining / Species->CarrionEnergyPerMeal;
                }
            if (!Species->PreyRules.IsEmpty())
                if (const auto* Residents = GroundedResidents.Find(Area))
                    for (const auto Prey : *Residents)
                    {
                        if (Prey == Entity || EM.GetFragmentDataChecked<FEcoRegionFragment>(Prey).CurrentRegionId != Area) continue;
                        const FName Kind = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Prey).SpeciesId;
                        const auto* Rule = Species->PreyRules.FindByPredicate([Kind](const auto& R) { return R.SpeciesId == Kind; });
                        const auto* Profile = Rule ? FindFauna(Kind) : nullptr;
                        if (!Profile) continue;
                        const auto& PreyFauna = EM.GetFragmentDataChecked<FEcoFaunaFragment>(Prey);
                        if ((Profile->IsAquatic() || PreyFauna.bSwimming) != bAquatic || !FitsFaunaPrey(*Rule, *Species, *Profile,
                            Fauna->Life, PreyFauna.Life, EM.GetFragmentDataChecked<FEcoVitalsFragment>(Prey), Now)) continue;
                        const FVector PreyPosition = EM.GetFragmentDataChecked<FTransformFragment>(Prey).GetTransform().GetLocation();
                        if (FVector::Dist2D(AccessPoint, PreyPosition) >= GroundReach
                            || FVector::DistSquared(AccessPoint, PreyPosition) > FMath::Square(Species->SightRange)) continue;
                        if (bAquatic ? SampleWaterLeg(AccessPoint, PreyPosition, Area, Area, true)
                            : HasClearSight(*GetWorld(), AccessPoint, PreyPosition, Species->EyeHeight, Profile->EyeHeight)) AnimalMeals += 1.;
                    }
            const int32 AnimalConsumers = FMath::Max(1, Load.FindRef(Area) - State.ProjectedFoodConsumers + Extra);
            return PlantMeals + PatchMeals + AnimalMeals / AnimalConsumers;
        };
        const double LocalFood = EstimateMeals(Region.CurrentRegionId, Origin, Position, Now, false, false);
        TOptional<double> LocalAccessibleFood;
        const FPassage* Chosen = nullptr;
        const FPassage* ChosenContinuation = nullptr;
        int32 ChosenWaypoint = INDEX_NONE;
        double ChosenTravelSeconds = 0.;
        double ChosenEnergyCost = 0.;
        const TCHAR* Rejection = TEXT("NoOutgoingSeam");
        int32 Progress = 0;
        const auto RejectAt = [&](int32 Stage, const TCHAR* Reason)
        {
            if (Stage > Progress) { Progress = Stage; Rejection = Reason; }
        };
        double Best = 0.;
        const auto HasRoom = [&](FName Area, int32 OwnReservation)
        {
            const auto* Group = Groups.FindByPredicate([&](const auto& G) { return G.RegionId == Area; });
            const auto* Residents = FaunaLoad.Find(Area);
            const auto* Reserved = TransitSpeciesReservations.Find(Area);
            return Group && Load.FindRef(Area) + TransitReservations.FindRef(Area) - OwnReservation < Group->Schedule.RegionPopulationLimit
                && (Residents ? Residents->FindRef(Id.SpeciesId) : 0)
                    + (Reserved ? Reserved->FindRef(Id.SpeciesId) : 0) - OwnReservation < Species->RegionalLimit;
        };
        for (const auto& Passage : Passages)
        {
            if (Passage.bWater != bAquatic || Passage.From != Region.CurrentRegionId
                || (bTraveling && !Passage.Entry.Equals(Travel.TargetPosition, .1))) continue;
            const bool bCrossesTransit = TransitRegions.Contains(Passage.To);
            if (bCrossesTransit && (bAquatic || bInTransit)) continue;
            const bool bCheckGroundEnergy = !bAquatic && !bInTransit &&
                (RulesOnlyRegions.Contains(Passage.From) || RulesOnlyRegions.Contains(Passage.To));
            if (!bCheckGroundEnergy && !bTraveling && !bInTransit && !bHungry) continue;
            if (!bCrossesTransit && bTraveling && Passage.To != Travel.TargetRegionId) continue;
            if (!HasRoom(Passage.To, int32(bTraveling)))
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
                        || (bAquatic ? !SampleWaterLeg(Position, Point, Passage.From, Passage.From, false)
                            : !HasClearSight(*GetWorld(), Position, Point, Species->EyeHeight, 5.f))) continue;
                    Waypoint = Index;
                    break;
                }
            if (Waypoint == INDEX_NONE) { RejectAt(2, TEXT("PassageApproachUnavailable")); continue; }
            if (bInTransit && !bAquatic && !HasOpenGroundExit(Passage))
            { RejectAt(2, TEXT("GroundExitBlocked")); continue; }
            if (bAquatic)
            {
                bool bConnected = SampleWaterLeg(Position, Passage.Approach[Waypoint], Passage.From, Passage.From, false)
                    && SampleWaterLeg(Passage.Entry, Passage.Exit, Passage.From, Passage.To, false);
                for (int32 Index = Waypoint + 1; bConnected && Index < Passage.Approach.Num(); ++Index)
                    bConnected = SampleWaterLeg(Passage.Approach[Index - 1], Passage.Approach[Index], Passage.From, Passage.From, false);
                if (!bConnected) { RejectAt(2, TEXT("WaterPassageClosed")); continue; }
            }
            double Distance = FVector::Dist2D(Position, Passage.Approach[Waypoint]);
            for (int32 Index = Waypoint + 1; Index < Passage.Approach.Num(); ++Index)
                Distance += FVector::Dist2D(Passage.Approach[Index - 1], Passage.Approach[Index]);
            const auto Evaluate = [&](const FPassage& Destination, const FPassage* Continuation, double TotalDistance)
            {
                FRegionEcologyState Target;
                if (!Ecology->GetRegionState(Destination.To, Target)
                    || (Continuation && !HasRoom(Destination.To, int32(bTraveling))))
                { RejectAt(1, TEXT("DestinationCapacityOrUnavailable")); return; }
                const double Speed = bCheckGroundEnergy ? Species->WalkSpeed * WalkCondition * Fauna->Life.SpeedScale(Now)
                    : Species->WalkSpeed;
                double TravelSeconds = TotalDistance / Speed;
                double EnergyCost = 0.;
                double GroundReach = TNumericLimits<double>::Max();
                if (bCheckGroundEnergy)
                {
                    // Waypoints advance at a resource boundary and ground movement slows near each target.
                    const int32 Legs = Passage.Approach.Num() - Waypoint
                        + (Continuation ? Continuation->Approach.Num() : 0);
                    TravelSeconds += Legs * (1. + Speed / (Species->GroundAcceleration * WalkCondition * Fauna->Life.SpeedScale(Now)));
                    const auto& Survival = EM.GetFragmentDataChecked<FEcoCreatureSurvivalFragment>(Entity).Settings;
                    const double Demand = UsesFaunaPersistence()
                        ? FMath::Max(Fauna->MaintenanceScale, GroundMaintenanceDemand(*Species, Speed)) : Fauna->MaintenanceScale;
                    EnergyCost = TravelSeconds * (Survival.BaseMetabolism * Demand + Survival.TravelMetabolism);
                    const double GroundDemand = Survival.BaseMetabolism * Demand;
                    if (GroundDemand > 0.)
                        GroundReach = Speed * FMath::Max(0., double(Vitals.Energy) - EnergyCost) / GroundDemand;
                }
                // No meals are taken while crossing a transit corridor. Keep an escape route
                // available after entry, even if the traveler no longer has enough energy.
                if (bCheckGroundEnergy && !LocalAccessibleFood.IsSet())
                    LocalAccessibleFood = EstimateMeals(Region.CurrentRegionId, Origin, Position, Now, false, true);
                const double LocalMeals = bCheckGroundEnergy ? LocalAccessibleFood.GetValue() : LocalFood;
                const double Gain = EstimateMeals(Destination.To, Target, Destination.Exit, Now + TravelSeconds,
                    !bTraveling, bCheckGroundEnergy) - LocalMeals;
                // Once inside a corridor, leaving remains possible if food was depleted or the journey was interrupted.
                if (!bInTransit && Gain <= 1.) { RejectAt(3, TEXT("InsufficientFoodGain")); return; }
                if (bCheckGroundEnergy && Vitals.Energy <= EnergyCost)
                {
                    if (bAuditFaunaHunts)
                        UE_LOG(LogTemp, Verbose, TEXT("[Eco Transit Estimate] Id=%lld Event=EnergyRejected Energy=%.2f Cost=%.2f ETA=%.2f"),
                            Id.StableAgentId, Vitals.Energy, EnergyCost, TravelSeconds);
                    RejectAt(4, TEXT("InsufficientTravelEnergy"));
                    return;
                }
                if (bCheckGroundEnergy && !bTraveling && Vitals.Energy - EnergyCost >= MealStartEnergy) return;
                // The seam is not a meal. Budget the remaining walk at local metabolism,
                // without promising that a straight-line estimate is a navigable path.
                if (bCheckGroundEnergy && GroundReach < TNumericLimits<double>::Max()
                    && EstimateMeals(Destination.To, Target, Destination.Exit, Now + TravelSeconds,
                        !bTraveling, true, GroundReach) - LocalMeals <= 1.)
                { RejectAt(5, TEXT("InsufficientPostArrivalEnergy")); return; }
                const double Score = FMath::Max(bInTransit ? 1. : 0., Gain) / (1. + TravelSeconds);
                const FName BestDestination = ChosenContinuation ? ChosenContinuation->To : Chosen ? Chosen->To : NAME_None;
                if (Score > Best || (Score == Best && Destination.To.LexicalLess(BestDestination)))
                {
                    Best = Score;
                    Chosen = &Passage;
                    ChosenContinuation = Continuation;
                    ChosenWaypoint = Waypoint;
                    ChosenTravelSeconds = TravelSeconds;
                    ChosenEnergyCost = EnergyCost;
                }
            };
            if (!bCrossesTransit) Evaluate(Passage, nullptr, Distance);
            else
            {
                for (const auto& Continuation : Passages)
                {
                    if (Continuation.bWater || Continuation.From != Passage.To || Continuation.To == Passage.From
                        || TransitRegions.Contains(Continuation.To)
                        || (bTraveling && Continuation.To != Travel.TargetRegionId)) continue;
                    if (!HasOpenGroundExit(Continuation))
                    { RejectAt(2, TEXT("GroundExitBlocked")); continue; }
                    double ThroughDistance = Distance + FVector::Dist2D(Passage.Exit, Continuation.Approach[0]);
                    for (int32 Index = 1; Index < Continuation.Approach.Num(); ++Index)
                        ThroughDistance += FVector::Dist2D(Continuation.Approach[Index - 1], Continuation.Approach[Index]);
                    Evaluate(Continuation, &Continuation, ThroughDistance);
                }
            }
        }
        if (!Chosen) { ReportNoPassage(Rejection); CancelTravel(); continue; }
        if (!bTraveling)
        {
            Travel.State = EEcoResidenceState::Traveling;
            Travel.TargetRegionId = ChosenContinuation ? ChosenContinuation->To : Chosen->To;
            Travel.TargetRegionIndex = Ecology->GetRegionRuntimeIndex(Travel.TargetRegionId);
            Travel.TargetPosition = Chosen->Entry;
            Fauna->Goal = Chosen->Approach[ChosenWaypoint];
            Travel.MoveSpeed = Species->WalkSpeed;
            Travel.Reason = EEcoMigrationReason::FoodShortage;
            Travel.DepartureTime = Now;
            Travel.NextDecisionTime = Now + FMath::Max(10., 2. * ChosenTravelSeconds + 5.);
            ++Load.FindOrAdd(Travel.TargetRegionId);
            ++FaunaLoad.FindOrAdd(Travel.TargetRegionId).FindOrAdd(Id.SpeciesId);
            if (ChosenContinuation) AdjustTransitReservation(Chosen->To, Id.SpeciesId, 1);
            if (ChosenEnergyCost > 0. && bAuditFaunaHunts)
                UE_LOG(LogTemp, Log, TEXT("[Eco Transit Estimate] Id=%lld Event=Departed At=%.2f Energy=%.2f Cost=%.2f ETA=%.2f"),
                    Id.StableAgentId, Now, Vitals.Energy, ChosenEnergyCost, ChosenTravelSeconds);
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
        if (FVector::Dist2D(Position, Exit) > FMath::Min(double(Species->WalkSpeed) * .5, Migration.ArrivalRadius)) continue;
        if (bAquatic)
        {
            EcoCreatureMovement::FFaunaWaterColumn Water;
            if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Chosen->To, Exit, WaterClearance, Water)) continue;
            Exit.Z = FMath::Clamp(Position.Z, Water.Bottom + WaterClearance, Water.Surface - WaterClearance);
            if (FVector::Dist(Position, Exit) > FMath::Min(double(Species->WalkSpeed) * .5, Migration.ArrivalRadius)
                || !SampleWaterLeg(Position, Exit, Chosen->From, Chosen->To, true)
                || GetWorld()->SweepTestByObjectType(Position, Exit, FQuat::Identity, FCollisionObjectQueryParams(ECC_WorldStatic),
                    FCollisionShape::MakeSphere(FMath::Max(.5, WaterClearance - .2)),
                    FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaWaterSeam), false))) continue;
        }
        else if (!IsGroundStepUsable(Position, Exit)) continue;
        const auto* TargetRegion = FindRegion(Exit);
        if (!TargetRegion || TargetRegion->RegionId != Chosen->To) continue;
        // Complete the swept crossing and rebase residency at the same resource boundary.
        Arrivals.Add({Time.WorldEpoch, StepId, Id.StableAgentId, Region.CurrentRegionId, Chosen->To,
            Travel.Reason, Travel.DepartureTime, Now});
        --Load.FindOrAdd(Region.CurrentRegionId);
        --FaunaLoad.FindOrAdd(Region.CurrentRegionId).FindOrAdd(Id.SpeciesId);
        Region.CurrentRegionId = Chosen->To;
        Region.CurrentRegionIndex = Ecology->GetRegionRuntimeIndex(Chosen->To);
        RecordGameplayReason(Id.StableAgentId, Chosen->To, Now,
            ChosenContinuation ? TEXT("PassageTransitEntered") : TEXT("PassageArrived"));
        GroundedResidents.FindOrAdd(Chosen->To).Add(Entity);
        Transform.SetLocation(Exit);
        EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value = FVector::ZeroVector;
        Fauna->Home = Fauna->Goal = Exit;
        Fauna->NextDecision = Now;
        Fauna->LastForageIntakeAt = -1.;
        Fauna->LastPreySeenUntil = Fauna->HeardPreyUntil = Fauna->ScentUntil = -1.;
        Fauna->LastScentId = 0;
        Fauna->BlockedPatch = INDEX_NONE;
        Fauna->BlockedCarrionId = 0;
        if (ChosenContinuation)
        {
            AdjustTransitReservation(Chosen->To, Id.SpeciesId, -1);
            ++Load.FindOrAdd(Chosen->To);
            ++FaunaLoad.FindOrAdd(Chosen->To).FindOrAdd(Id.SpeciesId);
            Travel.TargetPosition = ChosenContinuation->Entry;
            Fauna->Goal = ChosenContinuation->Approach[0];
            UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][PassageTransitEntered] Id=%lld Species=%s Region=%s Destination=%s"),
                Id.StableAgentId, *Id.SpeciesId.ToString(), *Region.CurrentRegionId.ToString(), *Travel.TargetRegionId.ToString());
            continue;
        }
        Travel = FEcoTravelFragment();
        Travel.LastArrivalTime = Now;
        Travel.NextDecisionTime = Now + 30.;
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][PassageArrived] Id=%lld Species=%s Region=%s"),
            Id.StableAgentId, *Id.SpeciesId.ToString(), *Region.CurrentRegionId.ToString());
    }
}

void AEcoCreatureIntegrationSpawner::MoveFauna(float Delta, double Now)
{
    if (FaunaSpecies.IsEmpty() || Delta <= UE_SMALL_NUMBER) return;
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
    FEcoServerTimeSnapshot MotionTime;
    // Rules-only regions have no Native context. Evaluate at this motion
    // boundary so catch-up frames do not apply the latest phase retroactively.
    const float WorldDarkness = Clock && Clock->IsClockRunning() && Clock->GetSnapshotAt(Now, MotionTime)
        ? float(FMath::Max(0., EcoClock::Darkness(MotionTime))) : 0.f;
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
    TMap<int64, FVector> ProvisionLandings;
    if (FaunaPerches.ContainsByPredicate([](const auto& Site) { return !Site.NestId.IsNone(); }))
    {
        for (const auto Child : Owned)
        {
            const auto* Young = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Child);
            if (!Young || Young->Life.Origin != EcoLifeV3::EOrigin::NaturalBirth) continue;
            const auto& ChildId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Child);
            const auto* Profile = FindFauna(ChildId.SpeciesId);
            const auto& Health = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Child);
            if (!Profile || Now - Young->Life.Born >= Profile->NestlingSeconds || Health.HP <= 0.f
                || Health.Energy >= .65f * Health.MaxEnergy) continue;
            const auto& ChildRegion = EM.GetFragmentDataChecked<FEcoRegionFragment>(Child);
            const auto* Site = FaunaPerches.FindByPredicate([&](const auto& Candidate) {
                return !Candidate.NestId.IsNone() && Candidate.SpeciesId == ChildId.SpeciesId
                    && Candidate.RegionId == ChildRegion.CurrentRegionId
                    && FVector::DistSquared(Candidate.Location, Young->Home) <= FMath::Square(90.);
            });
            if (!Site) continue;
            const FVector Landing = Site->Location + (Site->Location - Young->Home).GetSafeNormal2D() * 30.;
            ProvisionLandings.FindOrAdd(Young->Life.ParentA, Landing);
            ProvisionLandings.FindOrAdd(Young->Life.ParentB, Landing);
        }
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
        if (!Fauna) continue;
        const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Entity);
        const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(Entity);
        const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(Entity);
        const bool bPassageTravel = Travel.State == EEcoResidenceState::Traveling;
        const auto* Species = FindFauna(Id.SpeciesId);
        const auto* Context = Native ? Native->FindContext(Region.CurrentRegionId) : nullptr;
        const float Darkness = Context ? float(Context->Sim.Dark) : WorldDarkness;
        auto& Transform = EM.GetFragmentDataChecked<FTransformFragment>(Entity).GetMutableTransform();
        auto& Velocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value;
        const FVector PreviousVelocity = Velocity;
        const FVector Position = Transform.GetLocation();
        const double Dt = FMath::Min(Delta, .1f);
        if (Vitals.HP <= 0. && Fauna->Flight == EEcoFaunaFlightPhase::Grounded)
        {
            if (Species->IsAquatic() || Fauna->bSwimming) MoveFaunaWaterCarcass(EM, Entity, *Species, Delta, Now);
            continue;
        }
        if (Species->NestlingSeconds > 0.f && Fauna->Life.Origin == EcoLifeV3::EOrigin::NaturalBirth
            && Now - Fauna->Life.Born < Species->NestlingSeconds)
        {
            Velocity = FVector::ZeroVector;
            if (bPersistence)
                Fauna->MaintenanceScale = FMath::Lerp(Fauna->MaintenanceScale, Species->RestingMaintenanceFraction, ActivityBlend);
            continue;
        }
        float Heat = 0.f;
        float LocalRelief = 0.f;
        const FEcoFaunaCoolingSite* CoolingSite = nullptr;
        double CoolingValue = 0.;
        if (Species->HeatResponseC.Y > Species->HeatResponseC.X)
        {
            FRegionEnvironmentState Weather;
            GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->GetEnvironmentState(Region.CurrentRegionId, Weather);
            const auto& Range = Species->HeatResponseC;
            Heat = float(FMath::Clamp((Weather.Temperature - Range.X) / (Range.Y - Range.X), 0., 1.));
            if (Heat > 0.f)
            {
                for (const auto& Site : FaunaCoolingSites)
                {
                    if (Site.RegionId != Region.CurrentRegionId || Site.SpeciesId != Id.SpeciesId) continue;
                    const float Relief = FMath::Lerp(Site.DryRelief, Site.WetRelief, FMath::Clamp(Weather.Rainfall, 0.f, 1.f));
                    const double Distance = FVector::Dist(Position, Site.Center);
                    if (Distance > Species->SightRange || Relief <= 0.f
                        || !EcoCreatureMovement::IsWadeableGround(*GetWorld(), Site.Center, Species->WadeDepth)
                        || !HasClearSight(*GetWorld(), Position, Site.Center, Species->EyeHeight, 5.f)) continue;
                    if (Distance <= Site.Radius) LocalRelief = FMath::Max(LocalRelief, Relief);
                    const double Value = Heat * Relief / (1. + Distance / Species->SightRange);
                    if (Value <= CoolingValue) continue;
                    CoolingValue = Value;
                    CoolingSite = &Site;
                }
            }
        }
        const float ExposedHeat = Heat * (1.f - LocalRelief);
        const double HealthFraction = FMath::Clamp(double(Vitals.HP / FMath::Max(1.f, Vitals.MaxHP)), 0., 1.);
        const double Caution = Species->bIndividualResponse ? Fauna->Life.Genome.Caution : 1.;
        const double PhysicalCondition = Species->bIndividualResponse
            ? FMath::Lerp(.55, 1., HealthFraction) * FMath::Lerp(.75, 1., double(Fauna->Stamina)) : 1.;
        const bool bAmphibious = Species->Locomotion == EEcoFaunaLocomotion::Amphibious;
        if (Species->IsAquatic() || Fauna->bSwimming)
        {
            MoveFaunaInWater(EM, Entity, *Species, Delta, Now, PhysicalCondition, Darkness, bAdaptiveMeal);
            continue;
        }
        const auto CanMoveOnGround = [&](FVector& Destination)
        {
            const double BodyScale = Fauna->Life.BodyScale(Now);
            const float Radius = FMath::Clamp(float(Species->BodyRadius * BodyScale), 1.f, 120.f);
            if (!EcoCreatureMovement::ConstrainGroundStep(*GetWorld(), Position, Destination, Radius, Species->MinGroundNormalZ,
                    Species->SweepHeight * float(BodyScale), Species->StepHeight)) return false;
            const auto* DestinationRegion = FindRegion(Destination);
            return DestinationRegion && DestinationRegion->RegionId == Region.CurrentRegionId
                && FMath::Abs(Destination.Z - Position.Z) <= Species->StepHeight
                && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Destination, Species->WadeDepth);
        };
        Velocity = FVector::ZeroVector;
        if (Fauna->ShorePhase == EEcoFaunaShorePhase::ClearingBank)
        {
            const FVector Offset = Fauna->Goal - Position;
            if (Offset.SizeSquared2D() <= FMath::Square(3.))
            {
                RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("SwimDryBankReached"));
            }
            else if (Now < Fauna->PhaseUntil && Now >= Fauna->ThreatUntil
                && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Fauna->Goal, 0.))
            {
                FVector Destination = Position + Offset.GetSafeNormal2D()
                    * FMath::Min(Offset.Size2D(), Species->WalkSpeed * PhysicalCondition * Dt);
                if (CanMoveOnGround(Destination))
                {
                    Transform.SetLocation(Destination);
                    Velocity = (Destination - Position) / Delta;
                    Transform.SetRotation(Velocity.GetSafeNormal2D().ToOrientationQuat());
                    continue;
                }
            }
            Fauna->ShorePhase = EEcoFaunaShorePhase::None;
        }
        if (bAmphibious && Now >= Fauna->PhaseUntil && Now >= Fauna->ThreatUntil && Fauna->TargetId == 0
            && Vitals.Energy <= Species->MealStart() * Vitals.MaxEnergy && Fauna->Stamina >= .3f)
        {
            int32 Best = INDEX_NONE;
            int64 SelectedPrey = 0;
            bool bSelectedPatchUsable = false;
            double Score = 0.;
            const double Clearance = FMath::Max(1., Species->BodyRadius * Fauna->Life.BodyScale(Now) * .65);
            FVector Entry = FVector::ZeroVector;
            FVector FoodGoal = FVector::ZeroVector;
            for (int32 Index = 0; Index < FaunaHabitatPatches.Num(); ++Index)
            {
                const auto& Patch = FaunaHabitatPatches[Index];
                const double Distance = FVector::Dist2D(Position, Patch.ShorePoint);
                if (!Patch.bHasShoreEntry || Patch.Stage > FaunaHabitatStage || Patch.RegionId != Region.CurrentRegionId
                    || !Patch.Consumers.Contains(Id.SpeciesId) || Distance > Species->SightRange
                    || !FaunaPatchStock.IsValidIndex(Index)
                    || (Fauna->BlockedPatch == Index && Now < Fauna->PatchBlockedUntil)
                    || !EcoCreatureMovement::HasClearWaterSight(*GetWorld(),
                        Position + FVector(0., 0., Species->EyeHeight),
                        Patch.ShorePoint + FVector(0., 0., Species->EyeHeight)))
                    continue;
                EcoCreatureMovement::FFaunaWaterColumn Water;
                if (!EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Patch.WaterEntryPoint, Clearance, Water)
                    || Water.Current.Size2D() > Species->WalkSpeed * PhysicalCondition * .5)
                    continue;
                EcoCreatureMovement::FFaunaWaterColumn PatchWater;
                const bool bPatchUsable = FaunaPatchStock[Index] >= .2f
                    && EcoCreatureMovement::HasClearWaterSight(*GetWorld(), Patch.WaterEntryPoint, Patch.Center)
                    && EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Region.CurrentRegionId, Patch.Center, Clearance, PatchWater)
                    && Patch.Center.Z > PatchWater.Bottom && Patch.Center.Z < PatchWater.Surface;
                double Value = bPatchUsable ? RankFaunaFood(EcoFaunaFeeding::Value(FMath::Min(FaunaPatchStock[Index], Patch.EnergyPerMeal),
                    (Distance + FVector::Dist(Patch.Center, Patch.WaterEntryPoint) * 2.) / Species->WalkSpeed),
                    Id.StableAgentId, Region.CurrentRegionId, Now, EEcoFaunaFoodIntent::HabitatPatch, 0, Patch.Id) : 0.;
                FVector Goal = Patch.Center;
                const int64 Prey = FindFaunaWaterPrey(EM, Entity, *Species, Patch.WaterEntryPoint, Now, false,
                    2. + Distance / Species->WalkSpeed, Value, Goal);
                if (Value <= Score) continue;
                Score = Value;
                Best = Index;
                SelectedPrey = Prey;
                bSelectedPatchUsable = bPatchUsable;
                FoodGoal = Goal;
                Entry = FVector(Patch.WaterEntryPoint.X, Patch.WaterEntryPoint.Y,
                    FMath::Clamp(Patch.ShorePoint.Z + Clearance + 2., Water.Bottom + Clearance + 1., Water.Surface - Clearance));
            }
            if (Best != INDEX_NONE)
            {
                const auto& Patch = FaunaHabitatPatches[Best];
                const FVector Offset = Patch.ShorePoint - Position;
                if (Offset.SizeSquared2D() > FMath::Square(12.))
                {
                    FVector Destination = Position + Offset.GetSafeNormal2D() * FMath::Min(Offset.Size2D(), Species->WalkSpeed * Dt);
                    if (CanMoveOnGround(Destination))
                    {
                        Transform.SetLocation(Destination);
                        Velocity = (Destination - Position) / Delta;
                        Transform.SetRotation(Velocity.GetSafeNormal2D().ToOrientationQuat());
                        continue;
                    }
                }
                else
                {
                    FCollisionQueryParams EntryQuery(SCENE_QUERY_STAT(EcoFaunaWaterEntry), false);
                    FHitResult EntryHit;
                    const FVector EntryStart = Position + FVector(0., 0., Clearance + 2.);
                    const auto CanEnter = [&](const FVector& From, const FVector& To)
                    {
                        while (GetWorld()->SweepSingleByObjectType(EntryHit, From, To, FQuat::Identity,
                            FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionShape::MakeSphere(Clearance), EntryQuery))
                        {
                            if (!EcoCreatureMovement::IsWaterSurfaceCollision(EntryHit.GetActor())) return false;
                            EntryQuery.AddIgnoredActor(EntryHit.GetActor());
                        }
                        return true;
                    };
                    const FVector EntryAbove(Entry.X, Entry.Y, Patch.ShorePoint.Z + Clearance + 2.);
                    const bool bClearEntry = Patch.DryBankPoint.IsZero() ? CanEnter(EntryStart, Entry)
                        : CanEnter(EntryStart, EntryAbove) && CanEnter(EntryAbove, Entry);
                    if (bClearEntry)
                    {
                        Fauna->LandingPoint = Patch.ShorePoint;
                        Fauna->SwimEntry = Entry;
                        Fauna->Goal = FoodGoal;
                        Fauna->PatchTarget = bSelectedPatchUsable ? Best : INDEX_NONE;
                        Fauna->PatchAccessPoint = 0;
                        Fauna->TargetId = SelectedPrey;
                        Fauna->CarrionTargetId = 0;
                        Fauna->ShorePhase = EEcoFaunaShorePhase::Entering;
                        Fauna->bSwimming = true;
                        if (SelectedPrey > 0)
                            RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("WaterPreyAtEntry"), SelectedPrey);
                        continue;
                    }
                }
                Fauna->BlockedPatch = Best;
                Fauna->PatchBlockedUntil = Now + 3.;
            }
        }
        ON_SCOPE_EXIT
        {
            if (bPersistence && Vitals.HP > 0.f)
            {
                const float FullSpeed = Fauna->Flight == EEcoFaunaFlightPhase::Grounded ? Species->RunSpeed : Species->FlightSpeed;
                const float Activity = float(FMath::Clamp(Velocity.Size() / FullSpeed, 0., 1.));
                const float BaseDemand = Fauna->Flight == EEcoFaunaFlightPhase::Grounded
                    ? GroundMaintenanceDemand(*Species, Velocity.Size())
                    : FMath::Lerp(Species->RestingMaintenanceFraction, 1.f, Activity);
                const float Demand = FMath::Lerp(BaseDemand, 1.f, .18f * ExposedHeat);
                Fauna->MaintenanceScale = FMath::Lerp(Fauna->MaintenanceScale, Demand, ActivityBlend);
            }
        };
        Fauna->bInvestigatingNoise = false;
        if (Fauna->Flight != EEcoFaunaFlightPhase::Grounded)
        {
            const auto PreviousFlight = Fauna->Flight;
            if (Species->bCanDiveHunt && Fauna->Flight == EEcoFaunaFlightPhase::Cruise
                && Vitals.HP > 0.f && Now >= Fauna->NextSense && Now >= Fauna->AttackReady
                && Now >= Fauna->ThreatUntil && Fauna->Stamina >= .35f
                && Vitals.Energy < Species->MealStart() * Vitals.MaxEnergy)
            {
                Fauna->NextSense = Now + .45;
                if (bAuditFaunaHunts)
                    UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld At=%.3f Medium=Air Event=Scan Energy=%.3f HungerLimit=%.3f Stamina=%.3f"),
                        Id.StableAgentId, Now, Vitals.Energy, Species->MealStart() * Vitals.MaxEnergy, Fauna->Stamina);
                double BestScore = 0.;
                for (const auto Prey : Owned)
                {
                    const auto& PreyId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Prey);
                    const auto* Rule = Species->PreyRules.FindByPredicate([&](const auto& Candidate) {
                        return Candidate.SpeciesId == PreyId.SpeciesId;
                    });
                    if (!Rule) continue;
                    FName Rejection;
                    if (!CanHuntFauna(EM, Entity, Prey, *Species, Now, false, true, bAuditFaunaHunts ? &Rejection : nullptr))
                    {
                        if (bAuditFaunaHunts)
                            UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Target=%lld Medium=Air Event=Reject Reason=%s"),
                                Id.StableAgentId, PreyId.StableAgentId, *Rejection.ToString());
                        continue;
                    }
                    const FVector Target = EM.GetFragmentDataChecked<FTransformFragment>(Prey).GetTransform().GetLocation();
                    const auto* PreyProfile = FindFauna(PreyId.SpeciesId);
                    if (Position.Z - Target.Z < Species->AttackReach
                        || Position.Z - Target.Z > Species->FlightCruiseHeight) continue;
                    const double Risk = Caution * PreyProfile->DefenseDamage + (1. - Fauna->Stamina) * 5.;
                    const double Score = RankFaunaFood(EcoFaunaFeeding::Value(Species->PredationEnergyPerMeal() * Rule->Preference,
                        FVector::Dist(Position, Target) / Species->FlightSpeed, Risk),
                        Id.StableAgentId, Region.CurrentRegionId, Now, EEcoFaunaFoodIntent::LivePrey, PreyId.StableAgentId);
                    if (bAuditFaunaHunts)
                        UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Target=%lld Medium=Air Event=Candidate Evidence=Sight Score=%.3f"),
                            Id.StableAgentId, PreyId.StableAgentId, Score);
                    if (Score <= BestScore) continue;
                    BestScore = Score;
                    Fauna->TargetId = PreyId.StableAgentId;
                    Fauna->LandingPoint = Target;
                }
                if (BestScore > 0.)
                {
                    Fauna->Flight = EEcoFaunaFlightPhase::Dive;
                    Fauna->ChaseBegan = Now;
                    RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("DiveSelected"), Fauna->TargetId);
                }
            }
            if (Fauna->Flight == EEcoFaunaFlightPhase::Dive && Vitals.HP > 0.f)
            {
                if (Fauna->AttackContact >= 0.) continue;
                const auto* Prey = AgentLookup.Find(Fauna->TargetId);
                if (Prey && Now - Fauna->ChaseBegan < Species->PursuitLimitSeconds
                    && CanHuntFauna(EM, Entity, *Prey, *Species, Now, false, true))
                {
                    const FVector Target = EM.GetFragmentDataChecked<FTransformFragment>(*Prey).GetTransform().GetLocation();
                    const FVector Contact = Target + FVector(0., 0., Species->AttackReach * .38);
                    const FVector Destination = Position + (Contact - Position).GetClampedToMaxSize(
                        Species->FlightSpeed * Dt * PhysicalCondition);
                    const auto* NextRegion = FindRegion(Destination);
                    if (NextRegion && NextRegion->RegionId == Region.CurrentRegionId
                        && !GetWorld()->SweepTestByObjectType(Position, Destination, FQuat::Identity,
                            FCollisionObjectQueryParams(ECC_WorldStatic),
                            FCollisionShape::MakeSphere(FMath::Max(4.f, Species->BodyRadius * .45f)),
                            FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaDive), false)))
                    {
                        Fauna->LandingPoint = Target;
                        Velocity = (Destination - Position) / Delta;
                        Transform.SetLocation(Destination);
                        if (!Velocity.IsNearlyZero()) Transform.SetRotation(Velocity.ToOrientationQuat());
                        Fauna->Stamina = FMath::Max(0.f, Fauna->Stamina - Species->SprintDrain * float(Dt));
                        if (CanHuntFauna(EM, Entity, *Prey, *Species, Now, true, true))
                        {
                            Fauna->AttackContact = Now + Species->AttackWindup;
                            RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("DiveContactQueued"), Fauna->TargetId);
                        }
                        continue;
                    }
                }
                RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("DiveEnded"), Fauna->TargetId);
                Fauna->TargetId = 0;
                Fauna->Flight = EEcoFaunaFlightPhase::Landing;
                Fauna->PhaseUntil = Now;
            }
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
                {
                    if (Vitals.HP > 0.f && Fauna->Flight == EEcoFaunaFlightPhase::Grounded
                        && FaunaPerches.ContainsByPredicate([&](const auto& Perch)
                        {
                            return Perch.RegionId == Region.CurrentRegionId && Perch.SpeciesId == Id.SpeciesId
                                && FVector::DistSquared(Perch.Location, Destination) <= FMath::Square(60.);
                        }))
                        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("FlightPerchArrived"));
                    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Flight] Id=%lld Phase=%d HeightZ=%.1f"),
                        Id.StableAgentId, int32(Fauna->Flight), Destination.Z);
                }
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
                int64 SeenHunterId = 0;
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
                    const auto& HunterId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Other);
                    const auto* Hunter = FindFauna(HunterId.SpeciesId);
                    if (Hunter && !CanHuntFauna(EM, Other, Entity, *Hunter, Now, false, false)) continue;
                    SeenHunterId = HunterId.StableAgentId;
                    Fauna->LastThreatPosition = Danger;
                    Fauna->ThreatUntil = Now + 1.5 * Caution;
                    BestThreat = Distance;
                }
                if (bAuditFaunaHunts && SeenHunterId > 0)
                    UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Prey=%lld Hunter=%lld At=%.3f Event=ThreatSeen DistanceCm=%.1f"),
                        Id.StableAgentId, SeenHunterId, Now, FMath::Sqrt(BestThreat));
                if (const auto* Listener = FootstepAudioSet ? FootstepAudioSet->FindProfile(Id.SpeciesId) : nullptr)
                {
                    const FEcoNoiseEvent* ThreatNoise = nullptr;
                    const FEcoNoiseEvent* PreyNoise = nullptr;
                    float BestThreatSignal = 0.f, BestPreySignal = 0.f;
                    bool bThreatOccluded = false;
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
                            bThreatOccluded = bOccluded;
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
                        Fauna->ThreatUntil = Now + 1.5 * Caution;
                        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now,
                            EcoNoise::IsPlayerShot(ThreatNoise->Tag) ? TEXT("ShotHeard") : TEXT("ThreatHeard"),
                            ThreatNoise->SourceAgentId, BestThreatSignal);
                        LogEvidence(*ThreatNoise, BestThreatSignal, TEXT("Avoid"));
                        if (CVarFaunaHearingLog.GetValueOnGameThread() && EcoNoise::IsPlayerThreat(ThreatNoise->Tag))
                            UE_LOG(LogTemp, Log, TEXT("[Eco Player Hearing] Agent=%lld Species=%s EventId=%lld At=%.9f Source=%s SourceXYZ=%s ListenerXYZ=%s Range=%.9g Loudness=%.9g Weather=%.9g Occluded=%d Signal=%.9g"),
                                Id.StableAgentId, *Id.SpeciesId.ToString(), ThreatNoise->Id, Now, *ThreatNoise->Tag.ToString(),
                                *ThreatNoise->Position.ToString(), *Position.ToString(), double(ThreatNoise->MaxRange),
                                double(ThreatNoise->Loudness), double(Weather), int32(bThreatOccluded), double(BestThreatSignal));
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
                        Fauna->ThreatUntil = Now + 1.5 * Caution;
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
            TOptional<FVector> ShelterMovementGoal;
            bool bHeadingToShelterMouth = false;
            if (bFleeing)
            {
                Fauna->PatchAccessPoint = 0;
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
                const float BodyScale = float(Fauna->Life.BodyScale(Now));
                const float BodyRadius = FMath::Clamp(Species->BodyRadius * BodyScale, 1.f, 120.f);
                const FVector Lift(0., 0., FMath::Max(BodyRadius + 1.f, Species->SweepHeight * BodyScale));
                const auto ClearShelterLeg = [&](const FVector& From, const FVector& To)
                {
                    return !GetWorld()->SweepTestByChannel(From + Lift, To + Lift, FQuat::Identity, ECC_WorldStatic,
                        FCollisionShape::MakeSphere(BodyRadius), FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaShelterLeg)))
                        && !EcoCreatureMovement::CrossesExcludedArea(*GetWorld(), From, To);
                };
                double BestLength = Shelter && Shelter->ShelterApproachPoints.IsEmpty() && Fauna->PatchTarget != INDEX_NONE
                    ? FVector::Dist(Position, Shelter->Center) : 650.;
                for (int32 Index = 0; Index < FaunaHabitatPatches.Num(); ++Index)
                {
                    const auto& Patch = FaunaHabitatPatches[Index];
                    if (Patch.ShelterApproachPoints.IsEmpty() || Patch.Stage > FaunaHabitatStage
                        || Patch.RegionId != Region.CurrentRegionId || Patch.ShelteredSpecies != Id.SpeciesId
                        || FVector::DistSquared(Position, Patch.Center) >= FMath::Square(BestLength)) continue;
                    if (Fauna->PatchTarget == Index) Fauna->PatchTarget = INDEX_NONE;
                    const auto Consider = [&](const FVector& Goal, double Length, bool bMouth)
                    {
                        if (Length >= BestLength) return;
                        BestLength = Length;
                        ShelterMovementGoal = Goal;
                        bHeadingToShelterMouth = bMouth;
                        Fauna->PatchTarget = Index;
                    };
                    if (ClearShelterLeg(Position, Patch.Center)
                        && HasClearSight(*GetWorld(), Position, Patch.Center, Species->EyeHeight, 5.f))
                    {
                        Consider(Patch.Center, FVector::Dist(Position, Patch.Center), false);
                        continue;
                    }
                    for (const FVector& Mouth : Patch.ShelterApproachPoints)
                    {
                        const double Length = FVector::Dist(Position, Mouth) + FVector::Dist(Mouth, Patch.Center);
                        if (Length < BestLength && ClearShelterLeg(Position, Mouth) && ClearShelterLeg(Mouth, Patch.Center)
                            && HasClearSight(*GetWorld(), Position, Mouth, Species->EyeHeight, 5.f)) Consider(Mouth, Length, true);
                    }
                }
            }
            const auto TryLaunch = [&](const FVector& Hint, bool bExactLanding = false)
            {
                if (GetWorld()->SweepTestByObjectType(Position + FVector(0, 0, 18),
                    Position + FVector(0, 0, Species->FlightCruiseHeight), FQuat::Identity,
                    FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionShape::MakeSphere(10.f),
                    FCollisionQueryParams(SCENE_QUERY_STAT(EcoFaunaTakeoff)))) return false;
                FEcoFaunaPlacement Landing;
                Landing.SpawnPoints.Add(Hint);
                TArray<FVector> Ground;
                if (!BuildFaunaPositions(Region.CurrentRegionId, Landing, Ground)) return false;
                FVector LandingPoint = Ground[0];
                const auto IsOccupied = [&](const FVector& Candidate)
                {
                    return Owned.ContainsByPredicate([&](FMassEntityHandle Other)
                    {
                        if (Other == Entity || EM.GetFragmentDataChecked<FEcoVitalsFragment>(Other).HP <= 0.f) return false;
                        if (FVector::DistSquared(Candidate, EM.GetFragmentDataChecked<FTransformFragment>(Other)
                                .GetTransform().GetLocation()) < FMath::Square(55.)) return true;
                        const auto* OtherFauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Other);
                        return OtherFauna && OtherFauna->Flight != EEcoFaunaFlightPhase::Grounded
                            && OtherFauna->Flight != EEcoFaunaFlightPhase::Dive
                            && FVector::DistSquared(Candidate, OtherFauna->LandingPoint) < FMath::Square(55.);
                    });
                };
                if (bExactLanding && (FMath::Abs(LandingPoint.Z - Hint.Z) > 30. || IsOccupied(LandingPoint))) return false;
                double PerchDistance = FMath::Square(850.);
                for (const auto& Perch : FaunaPerches)
                {
                    if (bExactLanding) break;
                    const double Distance = FVector::DistSquared2D(Hint, Perch.Location);
                    if (Perch.SpeciesId != Id.SpeciesId || Perch.RegionId != Region.CurrentRegionId
                        || Distance >= PerchDistance || FVector::DistSquared2D(Position, Perch.Location) < FMath::Square(100.))
                        continue;
                    FVector Candidate;
                    const auto* CandidateRegion = FindRegion(Perch.Location);
                    if (!CandidateRegion || CandidateRegion->RegionId != Region.CurrentRegionId
                        || !EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Perch.Location, Candidate)
                        || FMath::Abs(Candidate.Z - Perch.Location.Z) > 10.) continue;
                    if (IsOccupied(Candidate)) continue;
                    LandingPoint = Candidate;
                    PerchDistance = Distance;
                }
                Fauna->LandingPoint = LandingPoint;
                Fauna->Flight = EEcoFaunaFlightPhase::Takeoff;
                Fauna->PhaseUntil = Now + .65;
                ReleaseCarrion(TEXT("Takeoff"));
                if (PerchDistance < FMath::Square(850.))
                    RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("FlightPerchSelected"));
                UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Flight] Id=%lld Phase=%d HeightZ=%.1f Escape=%d"),
                    Id.StableAgentId, int32(Fauna->Flight), Position.Z, bFleeing);
                return true;
            };
            const bool bCanFly = Species->Locomotion == EEcoFaunaLocomotion::Flight
                && (Species->NestlingSeconds > 0.f || Fauna->Life.AgeFraction(Now) >= 1.);
            if (bFleeing && bCanFly && Fauna->Stamina >= .20f && Vitals.Energy >= .25f * Vitals.MaxEnergy && Now >= Fauna->PhaseUntil)
            {
                const FVector Away = (Position - Fauna->LastThreatPosition).GetSafeNormal2D();
                if (!Away.IsNearlyZero() && TryLaunch(Position + Away * 2000.)) continue;
                Fauna->PhaseUntil = Now + .5;
            }
            if (bCanFly && !bFleeing && !Guard && !bPassageTravel && Now >= Fauna->PhaseUntil
                && Fauna->AttackContact < 0. && Fauna->Stamina >= .35f)
            {
                const auto* Landing = ProvisionLandings.Find(Id.StableAgentId);
                if (Landing && Vitals.Energy >= .65f * Vitals.MaxEnergy && Fauna->CarrionTargetId == 0
                    && (FVector::DistSquared(Position, *Landing) > FMath::Square(105.) || FMath::Abs(Position.Z - Landing->Z) > 25.))
                {
                    if (TryLaunch(*Landing, true))
                    {
                        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("NestProvisionReturn"));
                        continue;
                    }
                    Fauna->PhaseUntil = Now + 1.;
                }
                else if (Species->NestlingSeconds > 0.f && Fauna->Life.Origin == EcoLifeV3::EOrigin::NaturalBirth
                    && Fauna->Life.AgeFraction(Now) < 1. && Vitals.Energy >= .28f * Vitals.MaxEnergy
                    && FVector::DistSquared(Position, Fauna->Home) <= FMath::Square(105.))
                {
                    for (int32 Direction = 0; Direction < 8 && Fauna->Flight == EEcoFaunaFlightPhase::Grounded; ++Direction)
                    {
                        const FVector Probe = Position + FVector::ForwardVector.RotateAngleAxis(45. * Direction, FVector::UpVector) * 320.;
                        FVector Ground;
                        if (EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Probe, Ground) && Ground.Z < Position.Z - 45.)
                            TryLaunch(Ground, true);
                    }
                    if (Fauna->Flight != EEcoFaunaFlightPhase::Grounded)
                    {
                        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("JuvenileNestDeparture"));
                        continue;
                    }
                    Fauna->PhaseUntil = Now + 1.;
                }
            }
            const auto AdvanceDuringWindup = [&](FMassEntityHandle Target)
            {
                const auto* PreyProfile = FindFauna(EM.GetFragmentDataChecked<FEcoIdentityFragment>(Target).SpeciesId);
                if (!PreyProfile) return;
                const FVector TargetPosition = EM.GetFragmentDataChecked<FTransformFragment>(Target).GetTransform().GetLocation();
                const FVector ToTarget = TargetPosition - Position;
                const FVector Heading = ToTarget.GetSafeNormal2D();
                const auto& TargetVelocity = EM.GetFragmentDataChecked<FMassVelocityFragment>(Target).Value;
                const bool bCommittedCharge = bAttackAdvance && Species->bFlankDefendedPrey && PreyProfile->DefenseDamage > 0.f;
                if (ToTarget.SizeSquared2D() > FMath::Square((bCommittedCharge ? 2.f : 1.25f) * Species->AttackReach)
                    || !HasClearSight(*GetWorld(), Position, TargetPosition, Species->EyeHeight, PreyProfile->EyeHeight)) return;

                const double Scale = Fauna->Life.SpeedScale(Now);
                const double ForwardSpeed = FVector::DotProduct(PreviousVelocity, Heading);
                const double RetreatSpeed = FMath::Max(0., FVector::DotProduct(TargetVelocity, Heading));
                const double FollowSpeed = FMath::Min(FMath::Max(Species->WalkSpeed * Scale, ForwardSpeed), RetreatSpeed);
                const double BrakeSpeed = FMath::Max(0., ForwardSpeed - Species->GroundAcceleration * Scale * Dt);
                const double Speed = bCommittedCharge ? Species->RunSpeed * Scale : FMath::Max(FollowSpeed, BrakeSpeed);
                const double Gap = (bCommittedCharge ? .4 : .65) * Species->AttackReach;
                const double AdvanceDistance = FMath::Clamp(ToTarget.Size2D() - Gap, 0., Speed * Dt);
                FVector Destination = Position + Heading * AdvanceDistance;
                if (AdvanceDistance <= UE_SMALL_NUMBER || !CanMoveOnGround(Destination)) return;
                if (bAuditFaunaHunts && PreviousVelocity.IsNearlyZero())
                    UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Advance Prey=%lld"),
                        Id.StableAgentId, *Id.SpeciesId.ToString(), Fauna->TargetId);
                Velocity = (Destination - Position) / Delta;
                Transform.SetLocation(Destination);
                const float Demand = float(FMath::Clamp(Speed / (Species->RunSpeed * Scale), 0., 1.));
                Fauna->Stamina = FMath::Max(0.f, Fauna->Stamina - Species->SprintDrain * Demand * float(Dt));
                Transform.SetRotation(Heading.ToOrientationQuat());
            };
            if (!Guard && !bFleeing && Fauna->AttackContact >= 0. && !Fauna->bRecovering)
            {
                const auto* Target = AgentLookup.Find(Fauna->TargetId);
                if (Target && CanHuntFauna(EM, Entity, *Target, *Species, Now, false, false)) AdvanceDuringWindup(*Target);
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
            const auto CarrionScore = [&](int64 StockId, const FEcoFaunaCarcass& Stock)
            {
                const double Score = EcoFaunaFeeding::Value(FMath::Min(Stock.Remaining, 3.f * Species->CarrionEnergyPerMeal),
                    FVector::Dist(Position, Stock.Position) / CarrionTravelSpeed);
                return RankFaunaFood(Score, Id.StableAgentId, Region.CurrentRegionId, Now, EEcoFaunaFoodIntent::Carcass, StockId);
            };
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
                    const double Score = CarrionScore(Pair.Key, Stock);
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
            const bool bSearching = !Species->bCanDiveHunt && !bClaim && !bFleeing && !bPassageTravel && !Fauna->bRecovering
                && bHungry && !Species->PreyRules.IsEmpty()
                && Fauna->Life.AgeFraction(Now) >= 1.;
            const bool bLocalPlantMeal = FaunaHabitatStage >= 2 && bFoodScan && Species->UsesPlantFood()
                && Context && Context->bSpatialFoodRegistered
                && Context->Sim.Food.Food[Context->Sim.Food.CellOf(Context->CmToUnits(Position))] >= Species->FoodPerMeal;
            const bool bAuditGroundFood = bFoodScan && Id.StableAgentId == GroundFoodAuditAgent();
            const auto PatchScore = [&](int32 Index, int32& AccessPoint)
            {
                if (!FaunaPatchStock.IsValidIndex(Index) || FaunaPatchStock[Index] < .2f) return 0.;
                const auto& Patch = FaunaHabitatPatches[Index];
                if (Patch.bSubmerged || Patch.Stage > FaunaHabitatStage || Patch.RegionId != Region.CurrentRegionId
                    || !Patch.Consumers.Contains(Id.SpeciesId)) return 0.;
                if (!Patch.IsPlantForage() && Species->UsesPlantFood() && Patch.ShelteredSpecies != Id.SpeciesId
                    && (!bNeedsSharedPlantPatch || FaunaPatchStock[Index] < Patch.EnergyPerMeal)) return 0.;
                double Distance = Species->SightRange * 1.5;
                AccessPoint = INDEX_NONE;
                for (int32 PointIndex = 0; PointIndex <= Patch.ForageAccessPoints.Num(); ++PointIndex)
                {
                    if (Fauna->BlockedPatch == Index && Fauna->BlockedPatchAccessPoint == PointIndex
                        && Now < Fauna->PatchBlockedUntil) continue;
                    const FVector Point = Patch.ForagePoint(PointIndex);
                    const double Range = FVector::Dist(Position,Point);
                    if (Range > Distance || (AccessPoint != INDEX_NONE && Range == Distance)
                        || !HasClearSight(*GetWorld(),Position,Point,Species->EyeHeight,5.f)
                        || !EcoCreatureMovement::IsWadeableGround(*GetWorld(),Point,Species->WadeDepth)) continue;
                    AccessPoint = PointIndex;
                    Distance = Range;
                }
                if (AccessPoint == INDEX_NONE) return 0.;
                if (!Patch.IsPlantForage() && bLocalPlantMeal && Patch.ShelteredSpecies != Id.SpeciesId && Distance > 35.) return 0.;
                const double Value = EcoFaunaFeeding::Value(FMath::Min(FaunaPatchStock[Index], 3.f * Patch.EnergyPerMeal),
                    Distance / Species->WalkSpeed + 1.) * Species->PlantPreference(Patch.PlantGuild);
                if (Patch.IsPlantForage() && bLocalPlantMeal && Distance > 35.
                    && Value <= EcoFaunaFeeding::Value(Species->FoodPerMeal * EcoFaunaNutrition::PlantEnergyPerUnit, 1.)) return 0.;
                const double Ranked = RankFaunaFood(Value,
                    Id.StableAgentId, Region.CurrentRegionId, Now, EEcoFaunaFoodIntent::HabitatPatch, 0, Patch.Id);
                if (bAuditGroundFood && Ranked > 0.)
                    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][GroundFoodCandidate] Agent=%lld Region=%s At=%.9f Patch=%s Point=%d RangeCm=%.3f Stock=%.6f BaseScore=%.9g RankedScore=%.9g"),
                        Id.StableAgentId, *Region.CurrentRegionId.ToString(), Now, *Patch.Id.ToString(), AccessPoint,
                        Distance, FaunaPatchStock[Index], Value, Ranked);
                return Ranked;
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
                        int32 AccessPoint = 0;
                        const double Value = PatchScore(Index,AccessPoint);
                        if (Value <= PatchValue) continue;
                        PatchValue = Value;
                        Fauna->PatchTarget = Index;
                        Fauna->PatchAccessPoint = AccessPoint;
                    }
                    if (Stock && PatchValue <= CarrionScore(Fauna->CarrionTargetId, *Stock))
                    {
                        Fauna->PatchTarget = INDEX_NONE;
                        PatchValue = 0.;
                    }
                    if (bAuditGroundFood)
                    {
                        const FName Selected = FaunaHabitatPatches.IsValidIndex(Fauna->PatchTarget)
                            ? FaunaHabitatPatches[Fauna->PatchTarget].Id : NAME_None;
                        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][GroundFoodSelection] Agent=%lld Region=%s At=%.9f Patch=%s Score=%.9g"),
                            Id.StableAgentId, *Region.CurrentRegionId.ToString(), Now, *Selected.ToString(), PatchValue);
                    }
                }
                else if (FaunaPatchStock.IsValidIndex(Fauna->PatchTarget) && FaunaPatchStock[Fauna->PatchTarget] < .2f)
                    Fauna->PatchTarget = INDEX_NONE;
            }
            const float EnergyFraction = Vitals.Energy / FMath::Max(1.f, Vitals.MaxEnergy);
            const bool bCooling = CoolingSite && !Guard && !bFleeing && !bPassageTravel && !Stock
                && Fauna->PatchTarget == INDEX_NONE && Fauna->TargetId <= 0
                && Fauna->Life.AgeFraction(Now) >= 1. && CoolingValue > .27 + .44 * (1. - EnergyFraction);
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
                if (!bHungry && !bNesting && Species->SocialNeighborRadius > 0.f)
                {
                    const auto SocialAffinity = [&](const auto& Life) {
                        return Life.Sex == EcoLifeV3::ESex::Male && Life.AgeFraction(Now) >= 1.
                            ? Species->AdultMaleSocialAffinity : 1.f;
                    };
                    const float Affinity = SocialAffinity(Fauna->Life);
                    FVector Closest = FVector::ZeroVector;
                    double ClosestDistance = Species->SocialNeighborRadius * Affinity;
                    int64 ClosestId = 0;
                    for (const auto Neighbor : Owned)
                    {
                        if (Neighbor == Entity || Affinity <= 0.f
                            || EM.GetFragmentDataChecked<FEcoIdentityFragment>(Neighbor).SpeciesId != Id.SpeciesId
                            || EM.GetFragmentDataChecked<FEcoRegionFragment>(Neighbor).CurrentRegionId != Region.CurrentRegionId
                            || EM.GetFragmentDataChecked<FEcoVitalsFragment>(Neighbor).HP <= 0.f) continue;
                        const auto* NeighborFauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Neighbor);
                        if (!NeighborFauna) continue;
                        const FVector Site = EM.GetFragmentDataChecked<FTransformFragment>(Neighbor).GetTransform().GetLocation();
                        const double Distance = FVector::Dist2D(Site, Position);
                        if (Distance >= FMath::Min(ClosestDistance, double(Species->SocialNeighborRadius * SocialAffinity(NeighborFauna->Life)))
                            || !HasClearSight(*GetWorld(), Position, Site, Species->EyeHeight, Species->EyeHeight))
                            continue;
                        Closest = Site;
                        ClosestDistance = Distance;
                        ClosestId = EM.GetFragmentDataChecked<FEcoIdentityFragment>(Neighbor).StableAgentId;
                    }
                    if (ClosestId > 0)
                    {
                        const double Sociality = Fauna->Life.Genome.Sociability;
                        const double Spacing = Species->SocialSpacing * Fauna->Life.BodyScale(Now) / Sociality;
                        const FVector GroupGoal = Closest + (Position - Closest).GetSafeNormal2D() * Spacing;
                        Fauna->Goal = FMath::Lerp(Fauna->Goal, GroupGoal, FMath::Clamp(.5 * Sociality * Affinity, 0., .75));
                        if (Species->AdultMaleSocialAffinity < 1.f)
                            RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("ConspecificSpacing"), ClosestId, ClosestDistance);
                    }
                }
                if (!bCooling && !bHungry && EcoLifeV3::Unit(Seed + 7) >= Activity)
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
                    if (CurrentRegion && FindNearbyForage(*GetWorld(), Context, *CurrentRegion, Position, *Species,
                        float(Fauna->Life.BodyScale(Now)), Fauna->Goal))
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
                const bool bHuntFlight = Species->bCanDiveHunt && bHungry && !Fauna->bRecovering
                    && Now >= Fauna->AttackReady && Now >= Fauna->PhaseUntil;
                const double FlightChance = bHuntFlight ? FMath::Lerp(.12, .78, double(Activity)) * Fauna->Stamina
                    : FMath::Lerp(.24, .08, double(Darkness)) * Activity;
                const float MinStamina = bHuntFlight ? .38f : .55f;
                const float MinEnergy = bHuntFlight ? .15f : .85f;
                if (bCanFly && Fauna->Stamina >= MinStamina && Vitals.Energy >= MinEnergy * Vitals.MaxEnergy
                    && EcoLifeV3::Unit(Seed + 4) < FlightChance
                    && TryLaunch((bHuntFlight ? Position : Fauna->Home) + Direction * 2000.))
                {
                    if (bHuntFlight)
                        RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now, TEXT("HungryFlightSearch"));
                    continue;
                }
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
                            if (bAuditFaunaHunts)
                            {
                                ++Rejections.FindOrAdd(Rejection);
                                if (Species->bIndividualResponse)
                                    UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Target=%lld Medium=Ground Event=Reject Reason=%s"),
                                        Id.StableAgentId, PreyId.StableAgentId, *Rejection.ToString());
                            }
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
                        const double Energy = FMath::Min(3. * Species->PredationEnergyPerMeal(),
                            PreyProfile->AdultCarrionEnergy > 0.f ? double(PreyProfile->AdultCarrionEnergy)
                            : 20. + 10. * FMath::Sqrt(PreyProfile->AdultMass * FMath::Lerp(.12, 1., Maturity)));
                        const double Handling = bAdaptivePreyValue && PreyProfile->DefenseDamage > 0.f
                            ? FMath::Max(0., FMath::CeilToDouble(Health.HP / (.45 * Health.MaxHP)) - 1.) * Species->AttackRecovery : 0.;
                        const double RiskWeight = bAdaptivePreyValue ? FMath::Lerp(.45, 1., double(Vitals.Energy / Vitals.MaxEnergy)) : 1.;
                        const double ExpectedEnergy = Energy * Rule->Preference * Vulnerability
                            * (PreyId.StableAgentId == PreviousTarget ? 1.15 : 1.);
                        const double CostSeconds = Distance / Species->RunSpeed + Species->AttackWindup + Handling;
                        const double Risk = 2. + Resistance * .55 * RiskWeight * Caution
                            + (1. - Fauna->Stamina) * 5.
                            + (Species->bIndividualResponse ? (1. - HealthFraction) * Resistance * .4 : 0.);
                        const double BaseScore = EcoFaunaFeeding::Value(ExpectedEnergy, CostSeconds, Risk);
                        const double Score = RankFaunaFood(BaseScore, Id.StableAgentId, Region.CurrentRegionId, Now,
                            EEcoFaunaFoodIntent::LivePrey, PreyId.StableAgentId);
                        if (bAuditFaunaHunts)
                            UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Target=%lld Medium=Ground Event=Candidate Evidence=Sight At=%.9f HunterSpecies=%s TargetSpecies=%s PreyMaturity=%.9g PreyHealth=%.9g EnergyFraction=%.9g Stamina=%.9g ExpectedEnergy=%.17g CostSeconds=%.17g Risk=%.17g BaseScore=%.17g Score=%.17g"),
                                Id.StableAgentId, PreyId.StableAgentId, Now, *Id.SpeciesId.ToString(), *PreyId.SpeciesId.ToString(),
                                Maturity, double(Health.HP / Health.MaxHP), double(Vitals.Energy / Vitals.MaxEnergy),
                                double(Fauna->Stamina), ExpectedEnergy, CostSeconds, Risk, BaseScore, Score);
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
                    double ComparedCarrion = 0.;
                    if (Stock && Fauna->PatchTarget == INDEX_NONE)
                    {
                        const double Carrion = CarrionScore(Fauna->CarrionTargetId, *Stock);
                        ComparedCarrion = Carrion;
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
                    if (bAuditFaunaHunts && Eligible > 0)
                        UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=GroundChoice At=%.9f LiveScore=%.17g PatchScore=%.17g ComparedCarrionScore=%.17g SelectedPrey=%lld"),
                            Id.StableAgentId, *Id.SpeciesId.ToString(), Now, BestScore, PatchValue, ComparedCarrion, Fauna->TargetId);
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
                            UE_LOG(LogTemp, Log, TEXT("[Eco Hunt Audit] Hunter=%lld Species=%s Event=Windup Prey=%lld GapCm=%.1f RetreatCmSec=%.1f CarryCmSec=%.1f"),
                                Id.StableAgentId, *Id.SpeciesId.ToString(), Fauna->TargetId, FromPrey.Size(), RetreatSpeed, CarrySpeed);
                        // The range prediction just used this motion. Do not erase it on the first wind-up step.
                        AdvanceDuringWindup(*Prey);
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
                Goal = ShelterMovementGoal.IsSet() ? ShelterMovementGoal.GetValue()
                    : FaunaHabitatPatches.IsValidIndex(Fauna->PatchTarget)
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
                const auto& Patch = FaunaHabitatPatches[Fauna->PatchTarget];
                Goal = Patch.ForagePoint(Patch.HasForagePoint(Fauna->PatchAccessPoint) ? Fauna->PatchAccessPoint : 0);
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
            else if (bCooling)
            {
                const double Angle = (Id.StableAgentId % 8) * UE_TWO_PI / 8.;
                const FVector Candidate = CoolingSite->Center
                    + FVector(FMath::Cos(Angle), FMath::Sin(Angle), 0.) * (.7 * CoolingSite->Radius);
                FVector RestPoint = CoolingSite->Center;
                FVector Ground;
                if (EcoCreatureMovement::ProjectSpawnPoint(*GetWorld(), Candidate, Ground)
                    && FMath::Abs(Ground.Z - Candidate.Z) <= Species->StepHeight
                    && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Ground, Species->WadeDepth)
                    && HasClearSight(*GetWorld(), Position, Ground, Species->EyeHeight, 5.f))
                    RestPoint = Ground;
                const bool bArrived = FVector::DistSquared2D(Position, RestPoint) <= FMath::Square(25.);
                Goal = bArrived ? Position : RestPoint;
                bRun = false;
                RecordGameplayReason(Id.StableAgentId, Region.CurrentRegionId, Now,
                    bArrived ? TEXT("CoolingSiteRest") : TEXT("CoolingSiteApproach"), 0, CoolingValue);
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
                        const double Spacing = Species->bIndividualResponse ? 1. / Fauna->Life.Genome.Sociability : 1.;
                        const double Gap = FMath::Max(0., ToParent.Size2D() - 1.8 * Species->BodyRadius * Spacing);
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
            const double Speed = PhysicalCondition * Fauna->Life.SpeedScale(Now) * (bRun ? Species->RunSpeed : Species->WalkSpeed);
            const double Accel = Species->GroundAcceleration * Fauna->Life.SpeedScale(Now) * PhysicalCondition;
            const double StopRadius = bPassageTravel ? 2. : FMath::Min(18., .8 * Species->BodyRadius);
            const double StoppingSpeed = FMath::Sqrt(2. * Accel * FMath::Max(0., Distance - StopRadius));
            FVector Desired = Offset.GetSafeNormal2D() * FMath::Min(Speed, StoppingSpeed);
            if (Species->GroundTurnDegreesPerSecond > 0.f && !Desired.IsNearlyZero())
            {
                const double CurrentYaw = Transform.Rotator().Yaw;
                const double DesiredYaw = Desired.Rotation().Yaw;
                const double Angle = FMath::Abs(FMath::FindDeltaAngleDegrees(CurrentYaw, DesiredYaw));
                const double TurnScale = FMath::Lerp(1., .45, FMath::Clamp(PreviousVelocity.Size2D() / Species->RunSpeed, 0., 1.));
                const double Yaw = FMath::FixedTurn(CurrentYaw, DesiredYaw, Species->GroundTurnDegreesPerSecond * TurnScale * Dt);
                Desired = FRotator(0., Yaw, 0.).Vector() * Desired.Size2D() * FMath::Lerp(1., .30, Angle / 180.);
            }
            const FVector Motion = FMath::VInterpConstantTo(FVector(PreviousVelocity.X, PreviousVelocity.Y, 0.), Desired, Dt, Accel);
            if (Motion.IsNearlyZero()) continue;
            FVector Destination = Position + FVector(Motion.X, Motion.Y, 0.) * Dt;
            bool bCanAdvance = CanMoveOnGround(Destination);
            if (!bCanAdvance && (Stock || Fauna->PatchTarget != INDEX_NONE || bPassageTravel || Fauna->TargetId > 0 || bCooling) && !bFleeing && !Guard
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
                    Fauna->BlockedPatchAccessPoint = bFleeing ? 0 : Fauna->PatchAccessPoint;
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
            if (bHeadingToShelterMouth && bAuditFaunaHunts)
                UE_LOG(LogTemp, Log, TEXT("[Eco Shelter Approach] Agent=%lld At=%.3f Patch=%s Mouth=%s Position=%s"),
                    Id.StableAgentId, Now, *FaunaHabitatPatches[Fauna->PatchTarget].Id.ToString(),
                    *Goal.ToString(), *Destination.ToString());
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

#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"

#include "Engine/World.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassSpawnerSubsystem.h"
#include "World/EcoWorldClockSubsystem.h"

namespace
{
constexpr double MealEvidenceSeconds = 4.;
constexpr double WitnessRangeSquared = 450. * 450.;
constexpr double ThreatObservationSeconds = 3.;
constexpr double CompetitionSampleSeconds = 1.;
// Authority attempts may be a second apart. Bridge brief pauses within the same meal.
constexpr double FoodVisitGapSeconds = 2.5;
}

void AEcoCreatureIntegrationSpawner::RecordFaunaExperience(int64 AgentId, const FEcoExperienceKey& Key,
	double Now, EEcoExperienceOutcome Outcome)
{
	if (!IsInGameThread() || !RecordsFaunaExperience() || GetNetMode() == NM_Client || AgentId <= 0) return;
	auto& Memory = FaunaExperience.FindOrAdd(AgentId);
	if (Memory.Observe(Key, Now, Outcome)
		&& (Key.Activity == EEcoExperienceActivity::Passage || Key.Activity == EEcoExperienceActivity::Shore
			|| Key.Activity == EEcoExperienceActivity::Perch))
		Memory.LongTerm.ObserveExploration(Now, Outcome);
}

void AEcoCreatureIntegrationSpawner::RecordFaunaAssociation(int64 AgentId, int64 OtherId, double Now, bool bCareOrBirth)
{
	if (!IsInGameThread() || !RecordsFaunaExperience() || AgentId <= 0 || AgentId == OtherId || OtherId <= 0) return;
	FaunaExperience.FindOrAdd(AgentId).LongTerm.ObservePartner(OtherId, Now, bCareOrBirth);
}

void AEcoCreatureIntegrationSpawner::ObserveInterruptedForage(int64 AgentId, FName Species, FName Region,
	const FEcoFaunaFragment& Fauna, const FVector& Position, double Now)
{
	if (!RecordsFaunaExperience()) return;
	constexpr double ReachSquared = 100. * 100.;
	if (FaunaHabitatPatches.IsValidIndex(Fauna.PatchTarget))
	{
		const auto& Patch = FaunaHabitatPatches[Fauna.PatchTarget];
		const int32 Access = Fauna.PatchAccessPoint;
		if (Patch.RegionId == Region && Patch.Consumers.Contains(Species) && Patch.HasForagePoint(Access)
			&& FVector::DistSquared(Position, Patch.ForagePoint(Access)) <= ReachSquared)
			RecordFaunaExperience(AgentId, {EEcoExperienceActivity::Patch, Region, Patch.Id,
				FIntVector(Access, 0, 0)}, Now, EEcoExperienceOutcome::ThreatInterrupted);
	}
	if (const auto* Stock = FaunaCarcasses.Find(Fauna.CarrionTargetId); Stock && Stock->Region == Region
		&& Stock->Remaining > 0.f && Now >= Stock->OpenAt && Now < Stock->ExpiresAt
		&& FVector::DistSquared(Position, Stock->Position) <= ReachSquared)
		RecordFaunaExperience(AgentId, {EEcoExperienceActivity::Carrion, Region, Stock->Species}, Now,
			EEcoExperienceOutcome::ThreatInterrupted);
}

double AEcoCreatureIntegrationSpawner::ExperiencePreference(int64 AgentId, const FEcoExperienceKey& Key, double Now) const
{
	if (FaunaExperienceMode != 2) return 1.;
	const auto* Memory = FindFaunaExperience(AgentId);
	return Memory ? Memory->Preference(Key, Now) : 1.;
}

EEcoEncounterMedium AEcoCreatureIntegrationSpawner::EncounterMedium(const FMassEntityManager& Manager,
    FMassEntityHandle Entity) const
{
    const auto* Fauna = Manager.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
    if (!Fauna) return EEcoEncounterMedium::Ground;
    if (Fauna->Flight != EEcoFaunaFlightPhase::Grounded) return EEcoEncounterMedium::Air;
    const auto* Species = FindFauna(Manager.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).SpeciesId);
    return Fauna->bSwimming || (Species && Species->IsAquatic()) ? EEcoEncounterMedium::Water : EEcoEncounterMedium::Ground;
}

void AEcoCreatureIntegrationSpawner::RecordHuntEncounter(const FMassEntityManager& Manager, int64 HunterId,
    FName PreySpecies, FName Region, double Now, double Yield)
{
    if (!RecordsFaunaExperience()) return;
    const auto* Hunter = AgentLookup.Find(HunterId);
    if (!Hunter || !Manager.IsEntityValid(*Hunter)
        || Manager.GetFragmentDataChecked<FEcoIdentityFragment>(*Hunter).SpeciesId == PreySpecies) return;
    FaunaExperience.FindOrAdd(HunterId).ObserveEncounter({EEcoEncounterKind::Hunt, EncounterMedium(Manager, *Hunter),
        Region, PreySpecies}, Now, Yield);
}

void AEcoCreatureIntegrationSpawner::ObserveEncounterThreat(const FMassEntityManager& Manager, int64 PreyId,
    int64 HunterId, FName Region, const FVector& Position, double Now)
{
    if (!RecordsFaunaExperience() || PreyId == HunterId || Region.IsNone()) return;
    const auto* Prey = AgentLookup.Find(PreyId);
    const auto* Hunter = AgentLookup.Find(HunterId);
    if (!Prey || !Hunter || !Manager.IsEntityValid(*Prey) || !Manager.IsEntityValid(*Hunter)) return;
    const FName HunterSpecies = Manager.GetFragmentDataChecked<FEcoIdentityFragment>(*Hunter).SpeciesId;
    if (Manager.GetFragmentDataChecked<FEcoIdentityFragment>(*Prey).SpeciesId == HunterSpecies) return;
    auto* Pending = PendingEncounterThreats.Find(PreyId);
    if (Pending && Pending->FinishAt > Now)
    {
        if (Pending->Key.OtherSpecies == HunterSpecies && Pending->Key.Region == Region
            && Pending->Key.Medium == EncounterMedium(Manager, *Prey)) Pending->FinishAt = Now + ThreatObservationSeconds;
        return;
    }
    if (Pending) return; // Let the authority step settle the previous episode first.
    PendingEncounterThreats.Add(PreyId, {{EEcoEncounterKind::Risk, EncounterMedium(Manager, *Prey), Region,
        HunterSpecies, NAME_None, FEcoExperienceKey::PlantCell(Position)}, Now + ThreatObservationSeconds});
}

void AEcoCreatureIntegrationSpawner::ResolveEncounterEvidence(const FMassEntityManager& Manager, double Now)
{
    for (auto It = ActiveFoodVisits.CreateIterator(); It; ++It)
    {
        const auto* Entity = AgentLookup.Find(It.Key());
        if (!Entity || !Manager.IsEntityValid(*Entity) || Manager.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity).HP <= 0.)
        {
            It.RemoveCurrent();
            continue;
        }
        const auto Region = Manager.GetFragmentDataChecked<FEcoRegionFragment>(*Entity).CurrentRegionId;
        if (Now - It.Value().Last <= FoodVisitGapSeconds && Region == It.Value().Key.Region) continue;
        FinishFoodVisit(It.Key(), It.Value());
        It.RemoveCurrent();
    }
    for (auto It = PendingEncounterThreats.CreateIterator(); It; ++It)
    {
        const auto* Prey = AgentLookup.Find(It.Key());
        if (!Prey || !Manager.IsEntityValid(*Prey) || Manager.GetFragmentDataChecked<FEcoVitalsFragment>(*Prey).HP <= 0.)
        {
            It.RemoveCurrent();
            continue;
        }
        if (Now < It.Value().FinishAt) continue;
        FaunaExperience.FindOrAdd(It.Key()).ObserveEncounter(It.Value().Key, Now, 0.);
        It.RemoveCurrent();
    }
    for (auto It = EncounterMeals.CreateIterator(); It; ++It)
    {
        It.Value().RemoveAll([&](const FEncounterMeal& Meal) { return Now - Meal.At > MealEvidenceSeconds; });
        if (It.Value().IsEmpty()) It.RemoveCurrent();
    }
}

const AEcoCreatureIntegrationSpawner::FEncounterMeal* AEcoCreatureIntegrationSpawner::VisibleEncounterCompetitor(
    const FEncounterResource& Key, int64 AgentId, FName Species, const FVector& Position, double Now,
    const FMassEntityManager& Manager) const
{
    const auto* Meals = EncounterMeals.Find(Key);
    if (!Meals) return nullptr;
    for (int32 Index = Meals->Num() - 1; Index >= 0; --Index)
    {
        const auto& Meal = (*Meals)[Index];
        if (Meal.AgentId == AgentId || Meal.Species == Species || Now < Meal.At || Now - Meal.At > MealEvidenceSeconds
            || FVector::DistSquared(Position, Meal.Position) > WitnessRangeSquared) continue;
        const auto* Other = AgentLookup.Find(Meal.AgentId);
        if (!Other || !Manager.IsEntityValid(*Other) || EncounterMedium(Manager, *Other) != Key.Medium
            || Manager.GetFragmentDataChecked<FEcoVitalsFragment>(*Other).HP <= 0.
            || Manager.GetFragmentDataChecked<FEcoRegionFragment>(*Other).CurrentRegionId != Key.Region) continue;
        const auto& Transform = Manager.GetFragmentDataChecked<FTransformFragment>(*Other).GetTransform();
        if (FVector::DistSquared(Transform.GetLocation(), Position) > WitnessRangeSquared) continue;
        const auto* Subject = AgentLookup.Find(AgentId);
        if (!Subject || !Manager.IsEntityValid(*Subject)) continue;
        const auto& Facing = Manager.GetFragmentDataChecked<FTransformFragment>(*Subject).GetTransform();
        const FVector Offset = Transform.GetLocation() - Position;
        if (Offset.SizeSquared() > FMath::Square(80.)
            && FVector::DotProduct(Facing.GetRotation().GetForwardVector(), Offset.GetSafeNormal()) < .15) continue;
        const auto* OwnProfile = FindFauna(Species);
        const auto* OtherProfile = FindFauna(Meal.Species);
        const bool Visible = Key.Medium == EEcoEncounterMedium::Water
            ? EcoCreatureMovement::HasClearWaterSight(*GetWorld(), Position, Transform.GetLocation())
            : !GetWorld()->LineTraceTestByObjectType(Position + FVector(0., 0., OwnProfile ? OwnProfile->EyeHeight : 55.),
                Transform.GetLocation() + FVector(0., 0., OtherProfile ? OtherProfile->EyeHeight : 55.),
                FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoEncounterMeal)));
        if (Visible) return &Meal;
    }
    return nullptr;
}

void AEcoCreatureIntegrationSpawner::ObserveSharedMeal(const FMassEntityManager& Manager, int64 AgentId,
    FName Species, const FEncounterResource& Key, const FVector& Position, double Now, double Paid,
    double Requested, double StockBefore, double AllocationDemand, bool bFeedingPlaceDenied)
{
    if (RecordsFoodVisits()) SampleFoodVisit(AgentId, Key, Now, Paid, Requested);
    if (FaunaInteractionMode > 0 && bAuthorityWorld && Paid > UE_SMALL_NUMBER && Key.Kind == EEcoEncounterKind::Carrion)
    {
        const auto* Carcass = FaunaCarcasses.Find(Key.Instance);
        if (Carcass && !Carcass->ProducerSpecies.IsNone() && Carcass->ProducerSpecies != Species)
        {
            auto& Memory = FaunaExperience.FindOrAdd(AgentId);
            const FEcoEncounterKey Provision{EEcoEncounterKind::CarrionProvision, Key.Medium, Key.Region,
                Carcass->ProducerSpecies, NAME_None, Key.Cell};
            const auto* Previous = Memory.FindEncounter(Provision);
            if (!Previous || Now >= Previous->At + CompetitionSampleSeconds)
            {
                Memory.ObserveEncounter(Provision, Now, FMath::Clamp(Paid / FMath::Max(Paid, Requested), 0., 1.));
                RecordGameplayReason(AgentId, Key.Region, Now, TEXT("FaunaCarrionProvision"), Key.Instance, Paid, Carcass->ProducerSpecies);
            }
        }
    }
    // A full set of feeding places lowers the value of the visit, but does not
    // identify which animal used a place or how much stock it removed.
    if (bFeedingPlaceDenied || !RecordsFaunaExperience() || Species.IsNone() || Key.Region.IsNone()) return;
    if (Requested > UE_SMALL_NUMBER)
    {
        if (const auto* Other = VisibleEncounterCompetitor(Key, AgentId, Species, Position, Now, Manager))
        {
            const double Demand = FMath::Max(Requested, AllocationDemand);
            const double BeforeCompetitor = FMath::Min(Demand, StockBefore + Other->Paid);
            const double LostToUse = BeforeCompetitor - FMath::Min(Demand, StockBefore);
            if (LostToUse > UE_SMALL_NUMBER || Paid >= Requested - UE_SMALL_NUMBER)
            {
                auto& Memory = FaunaExperience.FindOrAdd(AgentId);
                const FEcoEncounterKey Context = Key.Against(Other->Species);
                const auto* Previous = Memory.FindEncounter(Context);
                if (!Previous || Now >= Previous->At + CompetitionSampleSeconds)
                    Memory.ObserveEncounter(Context, Now, .5 * (1. - FMath::Clamp(LostToUse / Demand, 0., 1.)));
            }
        }
    }
    if (Paid <= UE_SMALL_NUMBER) return;
    if (auto* Memory = FaunaExperience.Find(AgentId); Memory && !PendingEncounterThreats.Contains(AgentId))
    {
        const auto Cell = FEcoExperienceKey::PlantCell(Position);
        for (auto& Row : Memory->Encounters)
            if (Row.Key.Kind == EEcoEncounterKind::Risk && Row.Key.Region == Key.Region && Row.Key.Medium == Key.Medium
                && Row.Key.Cell == Cell && Now >= Row.At + ThreatObservationSeconds)
                Row.Observe(Now, .5); // Quiet meals move the estimate toward its prior.
    }
    auto& Meals = EncounterMeals.FindOrAdd(Key);
    Meals.RemoveAll([&](const auto& Row) { return Row.AgentId == AgentId; });
    if (Meals.Num() == 4) Meals.RemoveAt(0, EAllowShrinking::No);
    Meals.Add({AgentId, Species, Now, Paid, Position});
}

FEcoFoodVisitKey AEcoCreatureIntegrationSpawner::FoodVisitKey(const FEncounterResource& Resource, double Now) const
{
    FEcoServerTimeSnapshot Time;
    const auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
    const bool bNight = Clock && Clock->GetSnapshotAt(Now, Time) && Time.DayCycle.Phase == EEcoDayPhase::Night;
    return {Resource.Kind, Resource.Medium, Resource.Region, Resource.Site, Resource.Cell, bNight};
}

void AEcoCreatureIntegrationSpawner::SampleFoodVisit(int64 AgentId, const FEncounterResource& Resource,
    double Now, double Paid, double Requested)
{
    if (AgentId <= 0 || Resource.Region.IsNone() || !FMath::IsFinite(Now) || Now < 0.
        || !FMath::IsFinite(Requested) || Requested <= UE_SMALL_NUMBER || !FMath::IsFinite(Paid) || Paid < 0.) return;
    const auto Key = FoodVisitKey(Resource, Now);
    if (const auto* Old = ActiveFoodVisits.Find(AgentId))
    {
        if (Now < Old->Last) return;
        if (Old->Resource != Resource || Old->Key != Key || Now - Old->Last > FoodVisitGapSeconds)
        {
            FinishFoodVisit(AgentId, *Old);
            ActiveFoodVisits.Remove(AgentId);
        }
    }
    auto& Visit = ActiveFoodVisits.FindOrAdd(AgentId, FFoodVisit{Resource, Key, Now, Now});
    Visit.Last = Now;
    Visit.Requested += Requested;
    Visit.Paid += FMath::Min(Paid, Requested);
}

void AEcoCreatureIntegrationSpawner::FinishFoodVisit(int64 AgentId, const FFoodVisit& Visit)
{
    const double Fill = FMath::Clamp(Visit.Paid / Visit.Requested, 0., 1.);
    FaunaExperience.FindOrAdd(AgentId).ObserveFoodVisit(Visit.Key, Visit.Last, Visit.Last - Visit.First, Fill);
    RecordGameplayReason(AgentId, Visit.Key.Region, Visit.Last, TEXT("FoodVisitCompleted"), Visit.Resource.Instance, Fill);
}

double AEcoCreatureIntegrationSpawner::FoodVisitFactor(int64 AgentId, const FEncounterResource& Resource, double Now) const
{
    if (FaunaFoodVisitMode != 2 || !bAuthorityWorld) return 1.;
    const auto* Memory = FindFaunaExperience(AgentId);
    const auto* Active = ActiveFoodVisits.Find(AgentId);
    if ((!Memory || Memory->FoodVisits.IsEmpty()) && !Active) return 1.;
    const auto Key = FoodVisitKey(Resource, Now);
    const auto* Estimate = Memory ? Memory->FoodVisits.FindByPredicate([&](const auto& Row) { return Row.Key == Key; }) : nullptr;
    // A confirmed shortfall can redirect the next scan before another meal attempt or visit close.
    const bool bCurrentVisit = Active && Active->Resource == Resource && Active->Key == Key && Now >= Active->Last
        && Now - Active->Last <= FoodVisitGapSeconds && (Active->Last > Active->First || Active->Paid < Active->Requested);
    if (!Estimate && !bCurrentVisit) return 1.;
    const auto* Entity = AgentLookup.Find(AgentId);
    const auto& Manager = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    if (!Entity || !Manager.IsEntityValid(*Entity)) return 1.;
    const auto& Vitals = Manager.GetFragmentDataChecked<FEcoVitalsFragment>(*Entity);
    // Use the same low-energy boundary as the Native ground-safety preference.
    if (Vitals.MaxEnergy <= 0.f || Vitals.Energy <= .15f * Vitals.MaxEnergy) return 1.;
    if (bCurrentVisit)
    {
        auto Current = Estimate ? *Estimate : FEcoFoodVisitEstimate{};
        Current.Observe(Active->Last, Active->Last - Active->First, Active->Paid / Active->Requested);
        return Current.Factor(Now);
    }
    return Estimate ? Estimate->Factor(Now) : 1.;
}

double AEcoCreatureIntegrationSpawner::EncounterPlaceFactor(const FEcoFaunaExperience& Memory, FName Region,
    EEcoEncounterMedium Medium, const FVector& Destination, double Now) const
{
    const auto Cell = FEcoExperienceKey::PlantCell(Destination);
    double Factor = 1.;
    for (const auto& Row : Memory.Encounters)
        if (Row.Key.Kind == EEcoEncounterKind::Risk && Row.Key.Region == Region && Row.Key.Medium == Medium
            && Row.Key.Cell == Cell) Factor = FMath::Min(Factor, Row.Factor(Now));
    return Factor;
}

double AEcoCreatureIntegrationSpawner::EncounterFoodFactor(int64 AgentId, const FEncounterResource& Key,
    const FVector& Destination, double Now) const
{
    double Visit = FoodVisitFactor(AgentId, Key, Now) * InteractionFoodFactor(AgentId, Key.Region, Key.Medium, Destination, Now);
    if (FaunaInteractionMode == 2 && Key.Kind == EEcoEncounterKind::Carrion)
        if (const auto* Memory = FindFaunaExperience(AgentId))
        {
            double Provision = 1.;
            for (const auto& Row : Memory->Encounters)
                if (Row.Key.Kind == EEcoEncounterKind::CarrionProvision && Row.Key.Medium == Key.Medium
                    && Row.Key.Region == Key.Region && Row.Key.Cell == Key.Cell)
                    Provision = FMath::Max(Provision, Row.Factor(Now));
            Visit *= Provision;
        }
    if (FaunaExperienceMode != 2 || !bAuthorityWorld) return Visit;
    const auto* Experience = FindFaunaExperience(AgentId);
    if (!Experience || Experience->Encounters.IsEmpty()) return Visit;
    const double Risk = EncounterPlaceFactor(*Experience, Key.Region, Key.Medium, Destination, Now);
    if (!EncounterMeals.Contains(Key)) return Visit * Risk;
    const auto& Manager = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Subject = AgentLookup.Find(AgentId);
    if (!Subject || !Manager.IsEntityValid(*Subject)) return Visit * Risk;
    const auto& Id = Manager.GetFragmentDataChecked<FEcoIdentityFragment>(*Subject);
    const auto Position = Manager.GetFragmentDataChecked<FTransformFragment>(*Subject).GetTransform().GetLocation();
    const auto* Other = VisibleEncounterCompetitor(Key, AgentId, Id.SpeciesId, Position, Now, Manager);
    if (!Other) return Visit * Risk;
    const auto* Evidence = Experience->FindEncounter(Key.Against(Other->Species));
    return Visit * (Evidence ? FMath::Clamp(Risk * Evidence->Factor(Now), FEcoEncounterEstimate::MinFactor,
        FEcoEncounterEstimate::MaxFactor) : Risk);
}

void AEcoCreatureIntegrationSpawner::ObservePlantMeal(int64 AgentId, FName Region, FIntVector ResourceCell,
    const FVector& Position, double Now, double Paid, double Requested, double StockBefore, double AllocationDemand)
{
    ObserveFaunaReactionMeal(AgentId, Region, Now, Paid);
    if ((!RecordsFaunaExperience() && !RecordsFoodVisits()) || Requested <= 0.) return;
    const auto* Subject = AgentLookup.Find(AgentId);
    const auto& Manager = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    if (!Subject || !Manager.IsEntityValid(*Subject)) return;
    const auto& Id = Manager.GetFragmentDataChecked<FEcoIdentityFragment>(*Subject);
    ObserveSharedMeal(Manager, AgentId, Id.SpeciesId,
        {EEcoEncounterKind::Plants, EEcoEncounterMedium::Ground, Region, NAME_None, ResourceCell},
        Position, Now, Paid, Requested, StockBefore, AllocationDemand);
}

double AEcoCreatureIntegrationSpawner::RankPlantEncounter(int64 AgentId, FName Region, FIntVector ResourceCell,
    const FVector& Position, double Now) const
{
    return EncounterFoodFactor(AgentId, {EEcoEncounterKind::Plants, EEcoEncounterMedium::Ground,
        Region, NAME_None, ResourceCell}, Position, Now);
}

double AEcoCreatureIntegrationSpawner::RankPlantVisit(int64 AgentId, FName Region, FIntVector ResourceCell, double Now) const
{
    const auto* Reaction = ReadFaunaReaction(AgentId, Region, EEcoEncounterMedium::Ground, Now);
    const double Z = Reaction ? Reaction->Signal.Position.Z : 0.;
    return FoodVisitFactor(AgentId, {EEcoEncounterKind::Plants, EEcoEncounterMedium::Ground,
        Region, NAME_None, ResourceCell}, Now)
        * InteractionFoodFactor(AgentId, Region, EEcoEncounterMedium::Ground, FVector(ResourceCell.X, ResourceCell.Y, Z), Now);
}

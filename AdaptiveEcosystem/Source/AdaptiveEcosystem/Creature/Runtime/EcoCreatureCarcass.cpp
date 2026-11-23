#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "MassMovementFragments.h"
#include "World/EcoWorldClockSubsystem.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

namespace
{
    constexpr double WolfCarrionSearchCm = 1600.;
    constexpr double WolfCarrionContactCm = 115.;
    constexpr double WolfCarrionFeedSpeedCmPerSecond = 35.;
}

double AEcoCreatureIntegrationSpawner::CommitNativeCarcass(const FEcoDeathOutcome& Death)
{
    auto& EM=GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Victim=AgentLookup.Find(Death.StableAgentId);if(!Victim||!EM.IsEntityValid(*Victim))return 0.;
    auto* SourceLink=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(*Victim);if(!SourceLink||!SourceLink->Individual.bInitialized)return 0.;
    SourceLink->Individual.AbandonMeat();
    if(Death.Cause!=EEcoDeathCause::Predation||Death.PredatorStableAgentId<=0)return 0.;
    const auto* Body=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(*Victim);
    const auto* Primary=AgentLookup.Find(Death.PredatorStableAgentId);
    auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const auto* Context=Native?Native->GetContext(SourceLink->ContextIndex):nullptr;
    if(!Body||!Primary||!EM.IsEntityValid(*Primary)||!Context)return 0.;
    const double Now=Context->Sim.T*EcoRepertoireV3::kStepSeconds;
    TArray<FMassEntityHandle> Receivers;
    for(const auto Entity:Owned){
        if(EM.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP<=0)continue;
        const auto* Wolf=EM.GetFragmentDataPtr<FEcoThreatStateFragment>(Entity);const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
        if(!Wolf||!Link||Link->bDead||!Link->bAdopted||Link->ContextIndex!=SourceLink->ContextIndex||!Link->Individual.bInitialized)continue;
        const auto& Life=Link->Individual;
        const bool Contributor=Entity==*Primary||(Life.LastHuntTarget==Death.StableAgentId&&Now>=Life.LastHuntTime&&Now-Life.LastHuntTime<=5);
        if(!Contributor||FMath::Square(Wolf->Agent.State.PosX-Body->Body.Pos.X)+FMath::Square(Wolf->Agent.State.PosY-Body->Body.Pos.Y)>144)continue;
        Receivers.Add(Entity);
    }
    if(Receivers.IsEmpty())return 0.;
    const double Share=.6/Receivers.Num();double Issued=0;
    const bool bSharedCarcass = !FaunaSpecies.IsEmpty();
    const double Full = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::WolfMeal) ? .92 : 1.;
    for(const auto Entity:Receivers){auto& Life=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Entity).Individual;
        // Keep any share beyond the current meal's usable amount in the shared carcass.
        const double Reserved = bSharedCarcass ? FMath::Min(Share, Life.RoomForReservedMeat(Full)) : Share;
        if(Life.AssignMeat(Death.StableAgentId,Reserved,Now,Body->Body.Pos.X,Body->Body.Pos.Y,SourceLink->GroundZ))Issued+=Reserved;
    }
    UE_LOG(LogTemp,Log,TEXT("[EcoLife][Carcass] Prey=%lld Primary=%lld Receivers=%d NutritionIssued=%.9f Ledger=MeatNotVegetation"),
        Death.StableAgentId,Death.PredatorStableAgentId,Receivers.Num(),Issued);
    return Issued;
}

bool AEcoCreatureIntegrationSpawner::SelectWolfCarrion(int64 WolfId, FName Region, const FVector& Position,
    bool bCanScavenge, double ApproachSpeedCmPerSecond, FVector& Out, double AuthoritySeconds)
{
    if (FaunaSpecies.IsEmpty()) return false;
    WolfCarrionTargets.Remove(WolfId);
    if (!bCanScavenge || ApproachSpeedCmPerSecond <= UE_SMALL_NUMBER) return false;
    const double Now = AuthoritySeconds >= 0. ? AuthoritySeconds
        : GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
    double BestValue = 0.;
    int64 BestId = 0;
    for (const auto& Pair : FaunaCarcasses)
    {
        const auto& Stock = Pair.Value;
        const double Distance = FVector::Dist(Stock.Position, Position);
        if (Stock.Region != Region || Stock.Species == TEXT("Wolf") || !Stock.CanApproach(WolfId, Now)
            || Distance > WolfCarrionSearchCm) continue;
        const double TravelSeconds = FMath::Max(0., Distance - 95.) / ApproachSpeedCmPerSecond;
        // Bites are separated by a one-second resource interval.
        const double FeedingSeconds = Stock.ExpiresAt - Now - TravelSeconds;
        if (FeedingSeconds <= 0.) continue;
        const double Value = EcoFaunaFeeding::Value(
            FMath::Min(double(Stock.Remaining), 8. * FMath::CeilToDouble(FeedingSeconds)), TravelSeconds)
            * EncounterFoodFactor(WolfId, {EEcoEncounterKind::Carrion, EEcoEncounterMedium::Ground,
                Region, Stock.Species, FEcoExperienceKey::PlantCell(Stock.Position), Pair.Key}, Stock.Position, Now);
        if (Value < BestValue || (Value == BestValue && Pair.Key >= BestId)
            || GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, 55), Stock.Position + FVector(0, 0, 20),
                FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoWolfCarrion)))) continue;
        BestValue = Value;
        BestId = Pair.Key;
        Out = Stock.Position;
    }
    if (BestId <= 0) return false;
    WolfCarrionTargets.Add(WolfId, BestId);
    return true;
}

void AEcoCreatureIntegrationSpawner::FeedWolvesFromCarrion(double Now)
{
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    TArray<int64> Wolves;
    WolfCarrionTargets.GetKeys(Wolves);
    Wolves.Sort();
    for (const int64 WolfId : Wolves)
    {
        const auto* Handle = AgentLookup.Find(WolfId);
        const int64 StockId = WolfCarrionTargets.FindChecked(WolfId);
        auto* Stock = FaunaCarcasses.Find(StockId);
        if (!Stock || !Handle || !EM.IsEntityValid(*Handle))
        { WolfCarrionTargets.Remove(WolfId); continue; }
        auto* Link = EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(*Handle);
        const auto* Wolf = EM.GetFragmentDataPtr<FEcoThreatStateFragment>(*Handle);
        if (!Wolf || !Link || Link->bDead || Wolf->Agent.bDead || Wolf->Agent.State.bAsleep
            || Link->Individual.MealRemaining > 0. || EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Handle).HP <= 0.f) continue;
        auto& Lifetime = EM.GetFragmentDataChecked<FEcoLifetimeFragment>(*Handle);
        if (Now < Lifetime.NextFeedTimeSeconds) continue;
        const auto* Context = Native->GetContext(Link->ContextIndex);
        if (!Context || Context->RegionId != Stock->Region) continue;
        const FVector Position = Context->UnitsToCm(Wolf->Agent.State.PosX, Wolf->Agent.State.PosY, Link->GroundZ);
        if (FVector::DistSquared(Position, Stock->Position) > FMath::Square(WolfCarrionContactCm)
            || EM.GetFragmentDataChecked<FMassVelocityFragment>(*Handle).Value.SizeSquared2D() > FMath::Square(WolfCarrionFeedSpeedCmPerSecond)
            || GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, 55), Stock->Position + FVector(0, 0, 20),
                FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoWolfCarrionContact)))) continue;
        const bool bAdaptive = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::WolfMeal);
        if ((bAdaptive && !Link->Individual.MealCycle.bSeeking) || !Stock->CanApproach(WolfId, Now)) continue;
        const double Full = bAdaptive ? .92 : 1.;
        const float Requested = float(FMath::Min(8., (Full - Link->Individual.Nutrition) * 100.));
        const float StockBefore = Stock->Remaining;
        const float Meal = Stock->Bite(WolfId, Now, Requested);
        ObserveSharedMeal(EM, WolfId, EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Handle).SpeciesId,
            {EEcoEncounterKind::Carrion, EEcoEncounterMedium::Ground,
                Context->RegionId, Stock->Species, FEcoExperienceKey::PlantCell(Stock->Position), StockId},
            Position, Now, Meal, Requested, StockBefore, 0., Meal <= 0.f);
        if (Meal <= 0.f) continue;
        ObserveFaunaReactionMeal(WolfId, Context->RegionId, Now, Meal);
        Lifetime.NextFeedTimeSeconds = Now + 1.;
        Link->Individual.Nutrition = FMath::Min(1., Link->Individual.Nutrition + Meal / 100.);
        RecordFaunaExperience(WolfId, {EEcoExperienceActivity::Carrion, Context->RegionId, Stock->Species}, Now);
        RecordGameplayReason(WolfId, Context->RegionId, Now, TEXT("CarrionEaten"), StockId, Meal);
        if (auto* Presentation = EM.GetFragmentDataPtr<FEcoPredatorStateFragment>(*Handle)) Presentation->EatCooldown = 1.1f;
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Scavenge] Eater=%lld Species=Wolf Carcass=%lld Amount=%.3f Remaining=%.3f"),
            WolfId, StockId, Meal, Stock->Remaining);
    }
}

void AEcoCreatureIntegrationSpawner::FeedNativeWolfYoung(double Now)
{
    if (!bAuthorityWorld) return;
    auto* World = GetWorld();
    auto& Manager = World->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Native = World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    if (!Native) return;

    constexpr double AdultReserve = .55;
    constexpr double YoungCeiling = .65;
    constexpr double Portion = .01; // One energy unit on the Native 100-unit scale.
    constexpr double LocalRangeCm = 650.; // Same local transfer range as ground rule fauna.
    static const FName WolfSpecies(TEXT("Wolf"));
    TArray<int64, TInlineAllocator<16>> Dependents;
    for (const auto& [Id, Entity] : AgentLookup)
    {
        const auto* Link = Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
        if (Link && Link->Individual.Origin == EcoLifeV3::EOrigin::NaturalBirth && Link->Individual.AgeFraction(Now) < 1.
            && Manager.GetFragmentDataChecked<FEcoIdentityFragment>(Entity).SpeciesId == WolfSpecies)
            Dependents.Add(Id);
    }
    Dependents.Sort();

    for (int64 ChildId : Dependents)
    {
        const auto Child = AgentLookup.FindChecked(ChildId);
        auto& ChildLink = Manager.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Child);
        auto& ChildLife = ChildLink.Individual;
        const auto* ChildWolf = Manager.GetFragmentDataPtr<FEcoThreatStateFragment>(Child);
        auto& ChildVitals = Manager.GetFragmentDataChecked<FEcoVitalsFragment>(Child);
        auto& ChildLifetime = Manager.GetFragmentDataChecked<FEcoLifetimeFragment>(Child);
        if (!ChildWolf || !ChildLink.bAdopted || ChildLink.bDead || ChildWolf->Agent.bDead || ChildWolf->Agent.State.bAsleep
            || ChildWolf->Agent.Last.bRunning || ChildVitals.HP <= 0.f || Now < ChildLifetime.NextFeedTimeSeconds
            || ChildLife.MealRemaining > 0. || ChildLife.Nutrition >= YoungCeiling
            || ChildLife.Memory.Response != EcoLifeV3::EResponse::Policy) continue;
        const auto* Context = Native->GetContext(ChildLink.ContextIndex);
        if (!Context || Context->RegionId != Manager.GetFragmentDataChecked<FEcoRegionFragment>(Child).CurrentRegionId) continue;
        const auto& ChildState = ChildWolf->Agent.State;
        const FVector ChildPosition = Context->UnitsToCm(ChildState.PosX, ChildState.PosY, ChildLink.GroundZ);

        for (int64 ParentId : {ChildLife.ParentA, ChildLife.ParentB})
        {
            const auto* Parent = AgentLookup.Find(ParentId);
            if (!Parent || *Parent == Child || Manager.GetFragmentDataChecked<FEcoIdentityFragment>(*Parent).SpeciesId != WolfSpecies
                || Manager.GetFragmentDataChecked<FEcoRegionFragment>(*Parent).CurrentRegionId != Context->RegionId) continue;
            auto* ParentLink = Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(*Parent);
            const auto* ParentWolf = Manager.GetFragmentDataPtr<FEcoThreatStateFragment>(*Parent);
            auto& ParentVitals = Manager.GetFragmentDataChecked<FEcoVitalsFragment>(*Parent);
            if (!ParentLink || !ParentWolf || !ParentLink->bAdopted || ParentLink->bDead || ParentWolf->Agent.bDead
                || ParentWolf->Agent.State.bAsleep || ParentWolf->Agent.Last.bRunning || ParentVitals.HP <= 0.f
                || ParentLink->ContextIndex != ChildLink.ContextIndex || ParentLink->Individual.AgeFraction(Now) < 1.
                || ParentLink->Individual.Memory.Response != EcoLifeV3::EResponse::Policy) continue;

            auto& ParentNutrition = ParentLink->Individual.Nutrition;
            const double Amount = FMath::Min3(Portion, ParentNutrition - AdultReserve, YoungCeiling - ChildLife.Nutrition);
            if (Amount <= UE_SMALL_NUMBER) continue;
            const auto& ParentState = ParentWolf->Agent.State;
            const FVector ParentPosition = Context->UnitsToCm(ParentState.PosX, ParentState.PosY, ParentLink->GroundZ);
            const double Distance = FVector::Dist(ChildPosition, ParentPosition);
            double GroundZ = ParentPosition.Z;
            if (Distance > LocalRangeCm || (Native->UsesTerrain() && (!Native->TraceMove(Context->RegionId, ChildPosition, ParentPosition, GroundZ)
                    || FMath::Abs(GroundZ - ParentPosition.Z) > 60.))
                || World->LineTraceTestByObjectType(ChildPosition + FVector(0, 0, 55), ParentPosition + FVector(0, 0, 55),
                    FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoNativeWolfParentMeal)))) continue;

            const double AdultBefore = ParentNutrition;
            const double YoungBefore = ChildLife.Nutrition;
            ParentNutrition -= Amount;
            ChildLife.Nutrition += Amount;
            ParentVitals.Energy = float(ParentNutrition) * ParentVitals.MaxEnergy;
            ChildVitals.Energy = float(ChildLife.Nutrition) * ChildVitals.MaxEnergy;
            ChildLifetime.NextFeedTimeSeconds = Now + 1.;
            RecordGameplayReason(ChildId, Context->RegionId, Now, TEXT("ParentProvisioned"), ParentId, Amount * 100.);
            RecordFaunaExperience(ChildId, {EEcoExperienceActivity::Provision, Context->RegionId, WolfSpecies}, Now);
            RecordFaunaAssociation(ChildId, ParentId, Now, true);
            RecordFaunaAssociation(ParentId, ChildId, Now, true);
            if (bAuditTraitOutcomes)
                UE_LOG(LogTemp, Log, TEXT("[EcoLife][WolfProvision] Parent=%lld Child=%lld Region=%s At=%.6f Amount=%.9f ParentBefore=%.9f ParentAfter=%.9f ChildBefore=%.9f ChildAfter=%.9f DistanceCm=%.3f"),
                    ParentId, ChildId, *Context->RegionId.ToString(), Now, Amount, AdultBefore, ParentNutrition, YoungBefore, ChildLife.Nutrition, Distance);
            break;
        }
    }
}

FString AEcoCreatureIntegrationSpawner::CaptureNativeWolfForage(FName Region) const
{
    auto* World = GetWorld();
    if (!World || !bAuthorityWorld || !IsInGameThread()) return {};
    const auto* Native = World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
    const auto* Clock = World->GetSubsystem<UEcoWorldClockSubsystem>();
    auto* Spawner = World->GetSubsystem<UMassSpawnerSubsystem>();
    if (!Native || !Clock || !Spawner) return {};
    const auto& Manager = Spawner->GetEntityManagerChecked();
    if (Manager.IsProcessing()) return {};

    const double Now = Clock->GetServerTime().ServerTimeSeconds;
    const auto Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("at"), Now);
    Result->SetStringField(TEXT("region"), Region.ToString());
    Result->SetBoolField(TEXT("provisioning_enabled"), UsesNativeWolfProvisioning());
    TArray<TSharedPtr<FJsonValue>> Wolves;
    for (const auto& [Id, Entity] : AgentLookup)
    {
        if (!Manager.IsEntityValid(Entity)) continue;
        const auto* Wolf = Manager.GetFragmentDataPtr<FEcoThreatStateFragment>(Entity);
        const auto* Link = Manager.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(Entity);
        if (!Wolf || !Link || Link->bDead || Wolf->Agent.bDead || !Link->bAdopted || !Link->Individual.bInitialized) continue;
        const auto* Context = Native->GetContext(Link->ContextIndex);
        if (!Context || Context->RegionId != Region || Manager.GetFragmentDataChecked<FEcoVitalsFragment>(Entity).HP <= 0.) continue;

        const auto& Life = Link->Individual;
        const auto& Threat = Wolf->Agent;
        const FVector Position = Context->UnitsToCm(Threat.State.PosX, Threat.State.PosY, Link->GroundZ);
        const double Speed = Manager.GetFragmentDataChecked<FMassVelocityFragment>(Entity).Value.Size2D();
        const double SimTime = Context->Sim.T * EcoRepertoireV3::kStepSeconds;
        const auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("id"), LexToString(Id));
        Row->SetNumberField(TEXT("generation"), Life.Generation);
        Row->SetNumberField(TEXT("maturity"), Life.AgeFraction(SimTime));
        Row->SetNumberField(TEXT("nutrition"), Life.Nutrition);
        Row->SetNumberField(TEXT("reserved_meat_consumed"), Life.MeatConsumed);
        Row->SetNumberField(TEXT("reserved_meat_remaining"), Life.MealRemaining);
        Row->SetBoolField(TEXT("asleep"), Threat.State.bAsleep);
        Row->SetBoolField(TEXT("hunting"), Threat.Last.bHunting);
        Row->SetBoolField(TEXT("has_prey_target"), Threat.Last.bHasTarget);
        Row->SetStringField(TEXT("parent_target"), LexToString(Life.FamilyMode == 2 ? Life.FamilyObserved : 0));
        Row->SetNumberField(TEXT("speed_cm_s"), Speed);
        int32 Open = 0, InRange = 0, Visible = 0;
        double Nearest = TNumericLimits<double>::Max();
        const int64 Target = WolfCarrionTargets.FindRef(Id);
        for (const auto& [CarcassId, Stock] : FaunaCarcasses)
        {
            if (Stock.Region != Region || Stock.Species == TEXT("Wolf") || !Stock.CanApproach(Id, Now)) continue;
            ++Open;
            const double Distance = FVector::Dist(Position, Stock.Position);
            Nearest = FMath::Min(Nearest, Distance);
            if (Distance <= WolfCarrionSearchCm)
            {
                ++InRange;
                if (!World->LineTraceTestByObjectType(Position + FVector(0, 0, 55), Stock.Position + FVector(0, 0, 20),
                    FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoWolfCarrionSurvey)))) ++Visible;
            }
            if (Target == CarcassId)
            {
                Row->SetNumberField(TEXT("target_distance_cm"), Distance);
                Row->SetNumberField(TEXT("target_stock"), Stock.Remaining);
                Row->SetBoolField(TEXT("target_in_contact"), Distance <= WolfCarrionContactCm);
                Row->SetBoolField(TEXT("target_bite_speed"), Speed <= WolfCarrionFeedSpeedCmPerSecond);
            }
        }
        Row->SetStringField(TEXT("carrion_target"), LexToString(Target));
        Row->SetNumberField(TEXT("open_stock"), Open);
        Row->SetNumberField(TEXT("open_stock_in_range"), InRange);
        Row->SetNumberField(TEXT("clear_sight_in_range"), Visible);
        if (Open > 0) Row->SetNumberField(TEXT("nearest_open_stock_cm"), Nearest);
        Wolves.Add(MakeShared<FJsonValueObject>(Row));
    }
    Result->SetArrayField(TEXT("wolves"), MoveTemp(Wolves));
    FString Json;
    FJsonSerializer::Serialize(Result, TJsonWriterFactory<>::Create(&Json));
    return Json;
}

void AEcoCreatureIntegrationSpawner::CommitFaunaCarcass(const FEcoDeathOutcome& Death, float NativeReserved)
{
    auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const auto* Victim = AgentLookup.Find(Death.StableAgentId);
    if (!Victim || !EM.IsEntityValid(*Victim) || FaunaCarcasses.Contains(Death.StableAgentId)) return;
    const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(*Victim);
    const auto* Species = FindFauna(Death.SpeciesId);
    const float Settle = Species ? Species->DeathSettleSeconds : 1.3f;
    float Total = 100.f; // Normalized Native nutrition mapped onto the vitality scale.
    if (Fauna)
    {
        if (!Species) return;
        const auto& Life = Fauna->Life;
        const double Scale = FMath::Pow(Life.Genome.Size, 3.) * FMath::Lerp(.12, 1., Life.AgeFraction(Death.Time));
        Total = Species->AdultCarrionEnergy > 0.f ? float(Species->AdultCarrionEnergy * Scale)
            : float(FMath::Min(120., 20. + 10. * FMath::Sqrt(Species->AdultMass * Scale)));
    }

    FEcoFaunaCarcass Stock;
    Stock.Remaining = FMath::Max(0.f, Total - NativeReserved);
    float KillerMeal = 0.f;
    const auto* Killer = AgentLookup.Find(Death.PredatorStableAgentId);
    if (Death.Cause == EEcoDeathCause::Predation && Killer && EM.IsEntityValid(*Killer))
    {
        if (FaunaInteractionMode > 0)
            Stock.ProducerSpecies = EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Killer).SpeciesId;
        auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Killer);
        const auto& Survival = EM.GetFragmentDataChecked<FEcoCreatureSurvivalFragment>(*Killer);
        if (Vitals.HP > 0.f && Survival.Settings.bEnabled)
        {
            const float Requested = FMath::Min(Survival.EnergyPerPredation, Vitals.MaxEnergy - Vitals.Energy);
            if (auto* Hunter = EM.GetFragmentDataPtr<FEcoFaunaFragment>(*Killer))
            {
                Stock.KillerId = Death.PredatorStableAgentId;
                Hunter->CarrionTargetId = Death.StableAgentId;
                if (Hunter->bSwimming)
                    Hunter->PhaseUntil = FMath::Max(Hunter->PhaseUntil, Death.Time + Settle + 2.5);
            }
            else
            {
                KillerMeal = Stock.Take(Requested);
                Vitals.Energy += KillerMeal;
            }
        }
    }
    if (Stock.Remaining <= UE_SMALL_NUMBER) return;
    Stock.Position = EM.GetFragmentDataChecked<FTransformFragment>(*Victim).GetTransform().GetLocation();
    Stock.Region = Death.RegionId;
    Stock.Species = Death.SpeciesId;
    Stock.OpenAt = Death.Time + Settle;
    if (NativeReserved > 0.f) Stock.OpenAt = FMath::Max(Stock.OpenAt, Death.Time + 3.);
    Stock.ExclusiveUntil = Stock.OpenAt + (Stock.KillerId > 0 ? 2.5 : 0.);
    Stock.ExpiresAt = Stock.OpenAt + (Species ? Species->CarrionLifetime : 18.f);
    if (UsesFaunaCarrionAccess())
    {
        // Larger stocks give animals time to arrive and take more than a single bite.
        Stock.ExpiresAt += FMath::Min(15.f, Stock.Remaining / 8.f);
        auto& DeathState = EM.GetFragmentDataChecked<FEcoDeathFragment>(*Victim);
        DeathState.RemoveAfter = FMath::Max(DeathState.RemoveAfter, Stock.ExpiresAt + 2.);
    }
    Stock.FeedingPlaces = Species ? Species->FeedingPlaces : 3;
    EcoCreatureMovement::FFaunaWaterColumn Water;
    Stock.bWaterborne = Fauna && Species && (Species->IsAquatic() || Fauna->bSwimming)
        && EcoCreatureMovement::SampleFaunaWater(*GetWorld(), Stock.Region, Stock.Position, 1., Water);
    Stock.bFloats = Stock.bWaterborne && Species->Locomotion == EEcoFaunaLocomotion::Amphibious;
    Stock.bGrounded = (!Species || !Species->IsAquatic())
        && (!Fauna || (Fauna->Flight == EEcoFaunaFlightPhase::Grounded && !Fauna->bSwimming))
        && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Stock.Position, 0.f);
    FaunaCarcasses.Add(Death.StableAgentId, Stock);
    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Carcass] Id=%lld Species=%s Total=%.3f Native=%.3f Killer=%.3f Remaining=%.3f Medium=%s"),
        Death.StableAgentId, *Death.SpeciesId.ToString(), Total, NativeReserved, KillerMeal, Stock.Remaining,
        Stock.bWaterborne ? (Stock.bFloats ? TEXT("Floating") : TEXT("Sinking")) : (Stock.bGrounded ? TEXT("Ground") : TEXT("Unsettled")));
}

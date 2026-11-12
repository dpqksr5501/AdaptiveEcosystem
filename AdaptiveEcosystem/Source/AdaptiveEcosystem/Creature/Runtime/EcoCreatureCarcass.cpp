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
    for(const auto Entity:Receivers){auto& Life=EM.GetFragmentDataChecked<FEcoIntegratedV3Fragment>(Entity).Individual;
        if(Life.AssignMeat(Death.StableAgentId,Share,Now,Body->Body.Pos.X,Body->Body.Pos.Y,SourceLink->GroundZ))Issued+=Share;
    }
    UE_LOG(LogTemp,Log,TEXT("[EcoLife][Carcass] Prey=%lld Primary=%lld Receivers=%d NutritionIssued=%.9f Ledger=MeatNotVegetation"),
        Death.StableAgentId,Death.PredatorStableAgentId,Receivers.Num(),Issued);
    return Issued;
}

bool AEcoCreatureIntegrationSpawner::SelectWolfCarrion(int64 WolfId, FName Region, const FVector& Position,
    bool bCanScavenge, FVector& Out)
{
    if (FaunaSpecies.IsEmpty()) return false;
    WolfCarrionTargets.Remove(WolfId);
    if (!bCanScavenge) return false;
    const double Now = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
    double BestDistance = FMath::Square(1600.);
    int64 BestId = 0;
    for (const auto& Pair : FaunaCarcasses)
    {
        const auto& Stock = Pair.Value;
        const double Distance = FVector::DistSquared(Stock.Position, Position);
        if (Stock.Region != Region || Stock.Species == TEXT("Wolf") || !Stock.CanApproach(WolfId, Now)
            || Distance > BestDistance || (Distance == BestDistance && Pair.Key >= BestId)
            || GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, 55), Stock.Position + FVector(0, 0, 20),
                FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoWolfCarrion)))) continue;
        BestDistance = Distance;
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
        if (FVector::DistSquared(Position, Stock->Position) > FMath::Square(115.)
            || EM.GetFragmentDataChecked<FMassVelocityFragment>(*Handle).Value.SizeSquared2D() > FMath::Square(35.)
            || GetWorld()->LineTraceTestByObjectType(Position + FVector(0, 0, 55), Stock->Position + FVector(0, 0, 20),
                FCollisionObjectQueryParams(ECC_WorldStatic), FCollisionQueryParams(SCENE_QUERY_STAT(EcoWolfCarrionContact)))) continue;
        const bool bAdaptive = UsesAdaptiveRoutine(EEcoAdaptiveRoutine::WolfMeal);
        if (bAdaptive && !Link->Individual.MealCycle.bSeeking) continue;
        const double Full = bAdaptive ? .92 : 1.;
        const float Meal = Stock->Bite(WolfId, Now, float(FMath::Min(8., (Full - Link->Individual.Nutrition) * 100.)));
        if (Meal <= 0.f) continue;
        Lifetime.NextFeedTimeSeconds = Now + 1.;
        Link->Individual.Nutrition = FMath::Min(1., Link->Individual.Nutrition + Meal / 100.);
        RecordGameplayReason(WolfId, Context->RegionId, Now, TEXT("CarrionEaten"), StockId, Meal);
        if (auto* Presentation = EM.GetFragmentDataPtr<FEcoPredatorStateFragment>(*Handle)) Presentation->EatCooldown = 1.1f;
        UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Scavenge] Eater=%lld Species=Wolf Carcass=%lld Amount=%.3f Remaining=%.3f"),
            WolfId, StockId, Meal, Stock->Remaining);
    }
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
        auto& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Killer);
        const auto& Survival = EM.GetFragmentDataChecked<FEcoCreatureSurvivalFragment>(*Killer);
        if (Vitals.HP > 0.f && Survival.Settings.bEnabled)
        {
            const float Requested = FMath::Min(Survival.EnergyPerPredation, Vitals.MaxEnergy - Vitals.Energy);
            if (auto* Hunter = EM.GetFragmentDataPtr<FEcoFaunaFragment>(*Killer))
            {
                Stock.KillerId = Death.PredatorStableAgentId;
                Hunter->CarrionTargetId = Death.StableAgentId;
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
    Stock.bGrounded = (!Fauna || Fauna->Flight == EEcoFaunaFlightPhase::Grounded)
        && EcoCreatureMovement::IsWadeableGround(*GetWorld(), Stock.Position, 0.f);
    FaunaCarcasses.Add(Death.StableAgentId, Stock);
    UE_LOG(LogTemp, Log, TEXT("[Eco Fauna][Carcass] Id=%lld Species=%s Total=%.3f Native=%.3f Killer=%.3f Remaining=%.3f"),
        Death.StableAgentId, *Death.SpeciesId.ToString(), Total, NativeReserved, KillerMeal, Stock.Remaining);
}

#include "Mass/EcoMassMigration.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassCommonFragments.h"
#include "MassCommonTypes.h"
#include "MassMovementFragments.h"
#include "MassEntityManager.h"
#include "MassEntityView.h"
#include "MassExecutionContext.h"
#include "AdaptiveEcosystem.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Policy/EcoBehaviorFragments.h"

namespace
{
	FVector ArrivalFor(const FEcoRegionSpatialSnapshot& Space, int64 Id, float Spread)
	{
		// Stable ID produces a repeatable disk offset, independent of chunk/query ordering.
		const double Angle = static_cast<double>(Id % 1024) * 2.399963229728653;
		const double Radius = Spread * FMath::Sqrt(static_cast<double>((Id % 127) + 1) / 128.0);
		FVector Local = Space.BoundsTransform.InverseTransformPosition(Space.ArrivalPosition);
		Local += FVector(FMath::Cos(Angle) * Radius, FMath::Sin(Angle) * Radius, 0.0);
		const FVector Inner = Space.BoundsExtent * 0.95;
		Local.X = FMath::Clamp(Local.X, -Inner.X, Inner.X);
		Local.Y = FMath::Clamp(Local.Y, -Inner.Y, Inner.Y);
		Local.Z = FMath::Clamp(Local.Z, -Inner.Z, Inner.Z);
		return Space.BoundsTransform.TransformPosition(Local);
	}
}

bool EcoMassMigration::Reconcile(FMassEntityManager& Manager, const FEcoServerTimeSnapshot& Time,
	double ActualTime, int64 StepId, TConstArrayView<FEcoResourceSnapshot> Resources,
	TConstArrayView<FEcoRegionSpatialSnapshot> Spaces, const FEcoMigrationSettings& Settings,
	bool bDecisionDue, double FeedInterval, const FEcoOvercrowdingSettings* PressureSettings,
	const FEcoSurvivalSettings* SurvivalSettings, TConstArrayView<FEcoMigrationPressureSnapshot> Pressure, double ConsumptionRate,
	TArray<FEcoMigrationOutcome>* OutArrivals, bool bResetResidentVelocity)
{
	if (OutArrivals) OutArrivals->Reset();
	if (!IsInGameThread() || Manager.IsProcessing() || !Settings.IsValid() || Resources.Num() != Spaces.Num()
		|| !FMath::IsFinite(FeedInterval) || FeedInterval <= 0 || !FMath::IsFinite(ConsumptionRate) || ConsumptionRate < 0
		|| (PressureSettings && (!PressureSettings->IsValid() || Pressure.Num() != Spaces.Num()))
		|| (SurvivalSettings && !SurvivalSettings->IsValid())) return false;
	for (int32 I = 0; I < Resources.Num(); ++I)
		if (Resources[I].RegionIndex != I || Resources[I].RegionId != Spaces[I].RegionId
			|| Resources[I].StepId != StepId || Resources[I].WorldEpoch != Time.WorldEpoch
			|| Resources[I].Time != Time.ServerTimeSeconds) return false;
	if (!Settings.bEnabled) return true;
	struct FAgent
	{
		FMassEntityHandle Entity;
		FEcoIdentityFragment Identity;
		FEcoRegionFragment Region;
		FEcoTravelFragment Travel;
		FEcoLifetimeFragment Lifetime;
		FVector Position;
		float Energy = 0, HP = 0, MaxEnergy = 1;
		double ZeroEnergySeconds = 0;
		bool bArrived = false;
		EEcoMigrationReason ArrivalReason = EEcoMigrationReason::None;
		double DepartureTime = 0.0;
	};
	TArray<FAgent> Agents;
	bool bValid = true;
	FMassEntityQuery Query(Manager.AsShared());
	Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddRequirement<FEcoLifetimeFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddRequirement<FEcoFeedingFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoVitalsRuntimeFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Query.AddRequirement<FMassDesiredMovementFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	// Integrated wolves hunt prey; regional vegetation depletion only migrates herbivores.
	if (!bResetResidentVelocity) Query.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::None);
	FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
	Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& Chunk)
	{
		const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
		const auto Transforms = Chunk.GetFragmentView<FTransformFragment>();
		const auto Feeds = Chunk.GetFragmentView<FEcoFeedingFragment>();
		const auto Regions = Chunk.GetFragmentView<FEcoRegionFragment>();
		const auto Travels = Chunk.GetFragmentView<FEcoTravelFragment>();
		const auto Lives = Chunk.GetFragmentView<FEcoLifetimeFragment>();
		const auto Vitals = Chunk.GetFragmentView<FEcoVitalsFragment>();
		const auto Runtime = Chunk.GetFragmentView<FEcoVitalsRuntimeFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			if (Time.ServerTimeSeconds < Lives[I].SpawnTimeSeconds) continue;
			const int32 Index = Regions[I].CurrentRegionIndex;
			if (!Spaces.IsValidIndex(Index) || Feeds[I].bPending || Ids[I].StableAgentId <= 0
				|| Spaces[Index].RegionId != Regions[I].CurrentRegionId
				|| Transforms[I].GetTransform().GetLocation().ContainsNaN()
				|| !FMath::IsFinite(Vitals[I].Energy) || !FMath::IsFinite(Vitals[I].HP) || Vitals[I].MaxEnergy <= 0)
			{ bValid = false; continue; }
			FAgent& Agent = Agents.AddDefaulted_GetRef();
			Agent.Entity = Chunk.GetEntity(I);
			Agent.Identity = Ids[I];
			Agent.Region = Regions[I];
			Agent.Travel = Travels[I];
			Agent.Lifetime = Lives[I];
			Agent.Position = Transforms[I].GetTransform().GetLocation();
			Agent.Energy = Vitals[I].Energy;
			Agent.HP = Vitals[I].HP;
			Agent.MaxEnergy = Vitals[I].MaxEnergy;
			Agent.ZeroEnergySeconds = Runtime.IsEmpty() ? 0 : Runtime[I].ZeroEnergySeconds;
			if (Agent.Travel.State == EEcoResidenceState::Traveling
				&& (!Spaces.IsValidIndex(Agent.Travel.TargetRegionIndex)
					|| Agent.Travel.TargetRegionId != Spaces[Agent.Travel.TargetRegionIndex].RegionId)) bValid = false;
					
		}
	});
	if (!bValid) return false;
	TArray<int32> ScopedPopulation; ScopedPopulation.Init(0, Spaces.Num());
	for (const FAgent& A : Agents) ++ScopedPopulation[A.Region.CurrentRegionIndex];
	const auto HasFood = [&](int32 I) { return Resources.IsValidIndex(I) && Resources[I].Food > Settings.FoodEpsilon; };
	// Arrival is independent of the slower decision cadence and precedes new departures.
	for (FAgent& A : Agents)
	{
		if (A.Travel.State != EEcoResidenceState::Traveling || !HasFood(A.Travel.TargetRegionIndex)
			|| FVector::DistSquared(A.Position, A.Travel.TargetPosition) > FMath::Square(Settings.ArrivalRadius)
			|| !Spaces[A.Travel.TargetRegionIndex].Contains(A.Position)) continue;
		const int32 Destination = A.Travel.TargetRegionIndex;
		A.ArrivalReason = A.Travel.Reason;
		A.DepartureTime = A.Travel.DepartureTime;
		A.Region.CurrentRegionIndex = Destination;
		A.Region.CurrentRegionId = A.Travel.TargetRegionId;
		A.Travel = FEcoTravelFragment();
		A.Travel.LastArrivalTime = ActualTime;
		A.Lifetime.NextFeedTimeSeconds = ActualTime + FeedInterval;
		A.bArrived = true;
	}
	TArray<int32> Projected;
	// Release every failed incoming plan before any new candidate is scored.
	if (bDecisionDue)
	for (FAgent& A : Agents)
	{
		if (A.Travel.State != EEcoResidenceState::Traveling || HasFood(A.Travel.TargetRegionIndex)) continue;
		A.Travel.LastFailedTargetIndex = A.Travel.TargetRegionIndex;
		A.Travel.FailedTargetUntil = ActualTime + (PressureSettings && PressureSettings->bEnabled ? PressureSettings->RetrySeconds : Settings.DecisionIntervalSeconds);
		A.Travel.State = EEcoResidenceState::WaitingForFood;
		A.Travel.TargetRegionIndex = INDEX_NONE;
		A.Travel.TargetRegionId = NAME_None;
		A.Travel.MoveSpeed = 0;
	}
	Projected.Init(0, Spaces.Num());
	for (const FAgent& A : Agents)
	{
		++Projected[A.Region.CurrentRegionIndex];
		if (A.Travel.State == EEcoResidenceState::Traveling && A.Travel.TargetRegionIndex != A.Region.CurrentRegionIndex)
		{
			--Projected[A.Region.CurrentRegionIndex];
			++Projected[A.Travel.TargetRegionIndex];
		}
	}
	const bool bPressure = PressureSettings && PressureSettings->bEnabled;
	// All scoped agents consume regional food. Excluded predators still occupy habitat.
	// Separate the food forecast from total crowding without granting wolves vegetation meals.
	TArray<int32> ProjectedConsumers = Projected;
	if (bPressure)
		for (int32 I = 0; I < Projected.Num(); ++I)
			Projected[I] += FMath::Max(0, Pressure[I].Population - ScopedPopulation[I]);
	const auto Crowding = [&](int32 I, int32 Adjustment)
	{
		return bPressure ? static_cast<double>(FMath::Max(0, Projected[I] + Adjustment)) / FMath::Max(1, Pressure[I].ComfortPopulation) : 0.0;
	};
	const auto Satisfaction = [&](int32 I, int32 Adjustment)
	{
		const double Demand = FMath::Max(0, ProjectedConsumers[I] + Adjustment) * ConsumptionRate * (bPressure ? PressureSettings->ForecastSeconds : 1.0);
		return Demand > 0 ? FMath::Clamp(Resources[I].Food / Demand, 0.0, 1.0) : 1.0;
	};
	const auto Quality = [&](int32 I, int32 Adjustment) { return Satisfaction(I, Adjustment) - 0.5 * Crowding(I, Adjustment); };
	TArray<int32> Order;
	if (bDecisionDue)
	{
	for (int32 I = 0; I < Agents.Num(); ++I) Order.Add(I);
	Order.Sort([&](int32 A, int32 B)
	{
		const bool EmptyA = !HasFood(Agents[A].Region.CurrentRegionIndex);
		const bool EmptyB = !HasFood(Agents[B].Region.CurrentRegionIndex);
		if (EmptyA != EmptyB) return EmptyA;
		const float EnergyA = Agents[A].Energy / Agents[A].MaxEnergy, EnergyB = Agents[B].Energy / Agents[B].MaxEnergy;
		if (EnergyA != EnergyB) return EnergyA < EnergyB;
		if (Agents[A].Travel.LastArrivalTime != Agents[B].Travel.LastArrivalTime)
			return Agents[A].Travel.LastArrivalTime < Agents[B].Travel.LastArrivalTime;
		return Agents[A].Identity.StableAgentId < Agents[B].Identity.StableAgentId;
	});
	}
	TArray<int32> Departures;
	Departures.Init(0, Spaces.Num());
	if (bDecisionDue)
	for (int32 AgentIndex : Order)
	{
		FAgent& A = Agents[AgentIndex];
		const int32 Origin = A.Region.CurrentRegionIndex;
		if (A.bArrived) continue;
		if (A.Travel.State == EEcoResidenceState::Traveling && HasFood(A.Travel.TargetRegionIndex)) continue;
		const bool bEmpty = !HasFood(Origin);
		const bool bReturn = !bEmpty && A.Travel.State != EEcoResidenceState::Resident;
		if (ActualTime < A.Travel.NextDecisionTime) continue;
		const bool bReliefNeeded = bPressure && Pressure[Origin].bPressureActive
			&& Pressure[Origin].PressureSince >= 0
			&& Time.ServerTimeSeconds - Pressure[Origin].PressureSince >= PressureSettings->SustainSeconds
			&& (Crowding(Origin, 0) > PressureSettings->ExitCrowdingRatio || Satisfaction(Origin, 0) < PressureSettings->ExitFoodSatisfaction)
			&& ActualTime - A.Travel.LastArrivalTime >= PressureSettings->MinimumResidenceSeconds;
		if (!bEmpty && !bReturn && !bReliefNeeded) continue;
		if (!bReturn && bPressure && Departures[Origin] >= PressureSettings->MaxDeparturesPerRegion) continue;
		int32 Target = bReturn ? Origin : INDEX_NONE;
		double BestScore = -TNumericLimits<double>::Max();
		for (int32 Neighbor : Spaces[Origin].AdjacentIndices)
		{
			if (bReturn || !HasFood(Neighbor) || (Neighbor == A.Travel.LastFailedTargetIndex && ActualTime < A.Travel.FailedTargetUntil)) continue;
			const double Distance = FVector::Dist(A.Position, ArrivalFor(Spaces[Neighbor], A.Identity.StableAgentId, Settings.ArrivalSpread));
			if (bPressure && PressureSettings->bCheckTravelSurvival && SurvivalSettings && SurvivalSettings->bEnabled)
			{
				const double Rate = SurvivalSettings->BaseMetabolism + SurvivalSettings->TravelMetabolism;
				const double SurvivalTime = (A.Energy <= 0 ? 0.0 : Rate > 0 ? A.Energy / Rate : TNumericLimits<double>::Max())
					+ FMath::Max(0.0, SurvivalSettings->StarvationGraceSeconds - A.ZeroEnergySeconds)
					+ FMath::Max(0.0f, A.HP) / SurvivalSettings->StarvationDamagePerSecond;
				if (Distance / Settings.Speed >= SurvivalTime) continue;
			}
			if (bPressure && !bEmpty && Quality(Neighbor, 1) < Quality(Origin, 0) + PressureSettings->MinimumImprovement) continue;
			const double Score = bPressure ? Quality(Neighbor, 1) - 0.05 * Distance / 20000.0 : -Distance;
			if (Score > BestScore || (Score == BestScore && (Target == INDEX_NONE || Spaces[Neighbor].RegionId.LexicalLess(Spaces[Target].RegionId))))
			{ BestScore = Score; Target = Neighbor; }
		}
		if (Target == INDEX_NONE)
		{
			A.Travel.State = bEmpty ? EEcoResidenceState::WaitingForFood : EEcoResidenceState::Resident;
			A.Travel.TargetRegionIndex = INDEX_NONE;
			A.Travel.TargetRegionId = NAME_None;
			A.Travel.MoveSpeed = 0;
			A.Travel.Reason = EEcoMigrationReason::None;
			A.Travel.NextDecisionTime = ActualTime + (bPressure ? PressureSettings->RetrySeconds : Settings.DecisionIntervalSeconds);
			continue;
		}
		A.Travel.State = EEcoResidenceState::Traveling;
		A.Travel.TargetRegionIndex = Target;
		A.Travel.TargetRegionId = Spaces[Target].RegionId;
		A.Travel.TargetPosition = ArrivalFor(Spaces[Target], A.Identity.StableAgentId, Settings.ArrivalSpread);
		A.Travel.MoveSpeed = Settings.Speed;
		A.Travel.DepartureTime = ActualTime;
		A.Travel.Reason = bReturn ? EEcoMigrationReason::ReturnHome : bEmpty ? EEcoMigrationReason::FoodDepletion
			: Crowding(Origin, 0) > PressureSettings->ExitCrowdingRatio ? EEcoMigrationReason::Overcrowding : EEcoMigrationReason::FoodShortage;
		if (Target != Origin)
		{ --Projected[Origin]; ++Projected[Target]; --ProjectedConsumers[Origin]; ++ProjectedConsumers[Target]; ++Departures[Origin]; }
	}
	// No UObject calls or structural changes during the entity query.
	for (const FAgent& A : Agents)
	{
		FMassEntityView View(Manager, A.Entity);
		const FEcoTravelFragment Before = View.GetFragmentData<FEcoTravelFragment>();
		const FName From = View.GetFragmentData<FEcoRegionFragment>().CurrentRegionId;
		if (OutArrivals && A.bArrived && From != A.Region.CurrentRegionId)
			OutArrivals->Add({Time.WorldEpoch, StepId, A.Identity.StableAgentId, From, A.Region.CurrentRegionId,
				A.ArrivalReason, A.DepartureTime, ActualTime});
		View.GetFragmentData<FEcoRegionFragment>() = A.Region;
		View.GetFragmentData<FEcoTravelFragment>() = A.Travel;
		View.GetFragmentData<FEcoLifetimeFragment>() = A.Lifetime;
		if (bResetResidentVelocity && A.Travel.State != EEcoResidenceState::Traveling)
		{
			View.GetFragmentData<FMassDesiredMovementFragment>().DesiredVelocity = FVector::ZeroVector;
			View.GetFragmentData<FMassVelocityFragment>().Value = FVector::ZeroVector;
		}
		if (Settings.bPrintTransitions && (Before.State != A.Travel.State || Before.TargetRegionIndex != A.Travel.TargetRegionIndex || A.bArrived))
			UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Migration] Epoch=%d Step=%lld Time=%.3f Observed=%.3f ID=%lld From=%s Region=%s Target=%s State=%s Arrived=%d Reason=%s NextFeed=%.3f"),
				Time.WorldEpoch, StepId, Time.ServerTimeSeconds, ActualTime, A.Identity.StableAgentId, *From.ToString(), *A.Region.CurrentRegionId.ToString(),
				*A.Travel.TargetRegionId.ToString(), A.Travel.State == EEcoResidenceState::Resident ? TEXT("Resident") :
				A.Travel.State == EEcoResidenceState::Traveling ? TEXT("Traveling") : TEXT("WaitingForFood"),
				A.bArrived, *StaticEnum<EEcoMigrationReason>()->GetNameStringByValue(static_cast<int64>(A.bArrived ? A.ArrivalReason : A.Travel.Reason)), A.Lifetime.NextFeedTimeSeconds);
	}
	return true;
}

UEcoMigrationSteeringProcessor::UEcoMigrationSteeringProcessor() : EntityQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(UE::Mass::ProcessorGroupNames::ApplyForces);
	ExecutionOrder.ExecuteBefore.Add(UE::Mass::ProcessorGroupNames::Movement);
}

void UEcoMigrationSteeringProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FMassDesiredMovementFragment>(EMassFragmentAccess::ReadWrite);
	EntityQuery.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoIntegratedCreatureTag>(EMassFragmentPresence::None);
}

void UEcoMigrationSteeringProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	// Match the engine integration clamp so even a long frame cannot overshoot the target.
	const float Delta = FMath::Min(0.1f, Context.GetDeltaTimeSeconds());
	EntityQuery.ForEachEntityChunk(Context, [Delta](FMassExecutionContext& Chunk)
	{
		const auto Travel = Chunk.GetFragmentView<FEcoTravelFragment>();
		const auto Transforms = Chunk.GetFragmentView<FTransformFragment>();
		auto Moves = Chunk.GetMutableFragmentView<FMassDesiredMovementFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			Moves[I].DesiredVelocity = FVector::ZeroVector;
			if (Travel[I].State != EEcoResidenceState::Traveling || Delta <= 0.0f) continue;
			const FVector Offset = Travel[I].TargetPosition - Transforms[I].GetTransform().GetLocation();
			Moves[I].DesiredVelocity = Offset.GetSafeNormal() * FMath::Min(static_cast<double>(Travel[I].MoveSpeed), Offset.Size() / Delta);
		}
	});
}

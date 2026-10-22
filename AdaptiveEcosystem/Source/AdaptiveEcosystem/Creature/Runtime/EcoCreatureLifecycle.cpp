#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoMassMigration.h"
#include "Mass/EcoMassSurvival.h"
#include "MassMovementFragments.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcoWorldClockSubsystem.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "Core/EcoRepresentationTypes.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"
#include "Creature/Runtime/Interaction/EcoSpeciesAIInteractionSubsystem.h"

bool AEcoCreatureIntegrationSpawner::BuildAgentLookup()
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_AgentLookup);
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	AgentLookup.Reset();
	Owned.RemoveAll([&](FMassEntityHandle E) { return !EM.IsEntityValid(E); });
	for (const auto E : Owned)
	{
		const int64 Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId;
		if (Id <= 0 || AgentLookup.Contains(Id)) return false;
		AgentLookup.Add(Id, E);
	}
	return true;
}

void AEcoCreatureIntegrationSpawner::Reconcile(float Delta)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_Reconcile);
	auto* Clock = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>();
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	if (EM.IsProcessing() || !Clock->AdvanceClock(Delta)) return;
	const double Now = Clock->GetServerTime().ServerTimeSeconds;
	if (!BuildAgentLookup()) { FailRuntime(TEXT("Duplicate or invalid stable agent identity")); return; }
	// Bounded chronological catch-up: unfinished logical time remains as observable debt.
	const auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	for (int32 Pass = 0; Pass < MaxCatchUpSteps; ++Pass)
	{
		FEcoServerTimeSnapshot Previous;
		if (!Clock->GetSnapshotAt(LastResourceTime, Previous)) { FailRuntime(TEXT("Historical clock snapshot")); return; }
		double NextTime = FMath::Min(LastResourceTime + 1.0, Ecology->GetNextScheduledTime(Previous, bEnableWaves && IsSpeciesEnabled(false)));
		if (Migration.bEnabled) NextTime = FMath::Min(NextTime, NextMigrationTime);
		// Keep per-agent meal times aligned even when a phase/wave divides the second.
		for (const auto E : Owned)
		{
			const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
			const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
			const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(E);
			const double Due = EM.GetFragmentDataChecked<FEcoLifetimeFragment>(E).NextFeedTimeSeconds;
			if (V.HP > 0 && Id.SpeciesId == TEXT("Herbivore") && Travel.State == EEcoResidenceState::Resident && Due > LastResourceTime)
				NextTime = FMath::Min(NextTime, Due);
		}
		if (NextTime > Now) break;
		FEcoServerTimeSnapshot Time;
		if (!Clock->GetSnapshotAt(NextTime, Time) || !ProcessResourceStep(Time, Now))
		{ FailRuntime(TEXT("Creature resource/survival step")); return; }
		LastResourceTime = Time.ServerTimeSeconds;
	}
	if (!EcoMassSurvival::RemoveExpired(EM, Now, true) || !BuildAgentLookup())
	{ FailRuntime(TEXT("Creature death cleanup")); return; }
	UpdateSimulationLOD();
	UpdateSensoryPresentation();
	UpdatePresentationAndNoise(Delta);
}

bool AEcoCreatureIntegrationSpawner::ProcessResourceStep(const FEcoServerTimeSnapshot& Time, double ObservedTime)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_ResourceStep);
	auto* Ecology = GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	const int64 NextStep = Step + 1;
	TArray<FEcoDeathOutcome> Deaths;
	FEcoSurvivalSettings Fallback;
	if (!EcoMassSurvival::Advance(EM, Time, ObservedTime, NextStep, Fallback, Deaths, true)
		|| !Ecology->RecordDeaths(Deaths, NextStep)) return false;
	CommittedDeaths += Deaths.Num();
	for (const auto& Death : Deaths)
	{
		++SpeciesTotals.FindOrAdd(Death.RegionId).FindOrAdd(Death.SpeciesId).Deaths;
		// Award only committed, uniquely receipted predation, to a still-living predator.
		if (Death.Cause != EEcoDeathCause::Predation) continue;
		const auto* Predator = AgentLookup.Find(Death.PredatorStableAgentId);
		if (!Predator || !EM.IsEntityValid(*Predator)) continue;
		auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Predator);
		const auto* Profile = EM.GetFragmentDataPtr<FEcoCreatureSurvivalFragment>(*Predator);
		if (V.HP > 0 && Profile && Profile->Settings.bEnabled)
			V.Energy = FMath::Min(V.MaxEnergy, V.Energy + Profile->EnergyPerPredation);
	}
	// Fixture rewards are explicit test transactions, never actual prey/death/predation events.
	if (auto* Slots = GetWorld()->GetSubsystem<UEcoSpeciesAIInteractionSubsystem>())
	{
		TArray<UEcoSpeciesAIInteractionSubsystem::FFixtureReward> Rewards;
		Slots->DrainFixtureRewards(Time.ServerTimeSeconds, Rewards);
		for (const auto& Reward : Rewards) if (const auto* Target = AgentLookup.Find(Reward.AgentId); Target && EM.IsEntityValid(*Target))
		{
			auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(*Target);
			if (V.HP > 0) V.Energy = FMath::Min(V.MaxEnergy, V.Energy + Reward.Units);
		}
	}
	if (!ReconcilePopulation() || !Ecology->BeginResourceStep(Time, NextStep)) return false;
	Step = NextStep;
	// Same order as Box: survival/death, environment, wave spawn, feeding, arrival, migration.
	if (bEnableWaves && IsSpeciesEnabled(false)) for (const auto& G : Groups)
	{
		FEcoSpawnRequest Request;
		while (Ecology->PollSpawnWave(G.RegionId, Time, Request))
		{
			const int32 Actual = Spawn(G.RegionId, Request.Count, false);
			if (!ReconcilePopulation() || !Ecology->CompleteSpawnRequest(Request.RequestId, Actual) || Actual != Request.Count) return false;
		}
	}
	if (!BuildAgentLookup()) return false;
	TArray<FEcoFeedRequest> Requests;
	for (const auto E : Owned)
	{
		const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
		if (V.HP <= 0 || Id.SpeciesId != TEXT("Herbivore")) continue;
		if (EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E)) continue;
		const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(E);
		const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(E);
		const auto& Lifetime = EM.GetFragmentDataChecked<FEcoLifetimeFragment>(E);
		// Historical catch-up never grants meals before birth or observed arrival.
		if (Travel.State != EEcoResidenceState::Resident || Time.ServerTimeSeconds < Lifetime.NextFeedTimeSeconds) continue;
		auto& Feed = EM.GetFragmentDataChecked<FEcoFeedingFragment>(E);
		if (Feed.bPending) return false;
		const float Density = GetFoodDensity(EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation(), 200);
		const auto& Social = EM.GetFragmentDataChecked<FEcoSocialMovementRequestFragment>(E);
		const float Forage = Social.bValid ? Social.EffectiveAction.Forage : EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action.Forage;
		if (!FMath::IsFinite(Forage) || !FMath::IsFinite(Density)) return false;
		float Amount = FMath::Clamp(Forage, 0.f, 1.f) * Density;
		const auto* AI = EM.GetConstSharedFragmentDataPtr<FEcoSpeciesAISharedFragment>(E);
		if (AI && AI->Profile && !AI->Profile->bPolicyOnly)
		{
			auto& Exposure = EM.GetFragmentDataChecked<FEcoSpeciesAIFeedingFragment>(E);
			const double Seconds = Exposure.ConsumeThrough(Time.ServerTimeSeconds, Region.CurrentRegionId);
			const auto& Survival = EM.GetFragmentDataChecked<FEcoCreatureSurvivalFragment>(E);
			Amount = float(Seconds) * AI->Profile->FoodUnitsPerSecond * FMath::Clamp(Density, 0.f, 1.f);
			if (Survival.Settings.FoodEnergyGain > 0)
				Amount = FMath::Min(Amount, FMath::Max(0.f, V.MaxEnergy - V.Energy) / Survival.Settings.FoodEnergyGain);
		}
		if (Amount <= 0) continue;
		auto& Request = Requests.AddDefaulted_GetRef();
		Request.WorldEpoch = Time.WorldEpoch; Request.StepId = Step; Request.DueTime = Time.ServerTimeSeconds;
		Request.RegionIndex = Region.CurrentRegionIndex; Request.Food.RegionId = Region.CurrentRegionId;
		Request.Food.StableAgentId = Id.StableAgentId; Request.Food.RequestedAmount = Amount;
		Feed.PendingRequest = Request; Feed.bPending = true;
	}
	TArray<FEcoFeedResult> Results;
	if (!Ecology->ResolveFeeding(Requests, Results)) return false;
	// Validate the complete result set before any Energy update.
	for (const auto& Result : Results)
	{
		const auto* E = AgentLookup.Find(Result.Request.Food.StableAgentId);
		if (!E || !EM.IsEntityValid(*E)) return false;
		const auto& Feed = EM.GetFragmentDataChecked<FEcoFeedingFragment>(*E);
		const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(*E);
		if (!Feed.bPending || Result.Request.WorldEpoch != Time.WorldEpoch || Result.Request.StepId != Step
			|| Feed.PendingRequest.WorldEpoch != Time.WorldEpoch || Feed.PendingRequest.StepId != Step
			|| Feed.PendingRequest.Food.StableAgentId != Result.Request.Food.StableAgentId
			|| Feed.PendingRequest.RegionIndex != Result.Request.RegionIndex
			|| Feed.PendingRequest.Food.RegionId != Result.Request.Food.RegionId
			|| Feed.PendingRequest.Food.RequestedAmount != Result.Request.Food.RequestedAmount
			|| Feed.PendingRequest.DueTime != Result.Request.DueTime || Result.Request.DueTime != Time.ServerTimeSeconds
			|| !FMath::IsFinite(Result.GrantedAmount) || Result.GrantedAmount < 0
			|| Result.GrantedAmount > Result.Request.Food.RequestedAmount + 1.e-6
			|| Feed.LastFeedTime >= Result.Request.DueTime
			|| Region.CurrentRegionId != Result.Request.Food.RegionId
			|| Region.CurrentRegionIndex != Result.Request.RegionIndex
			|| EM.GetFragmentDataChecked<FEcoVitalsFragment>(*E).HP <= 0) return false;
	}
	for (const auto& Result : Results)
	{
		const auto E = AgentLookup.FindChecked(Result.Request.Food.StableAgentId);
		auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		const auto& Profile = EM.GetFragmentDataChecked<FEcoCreatureSurvivalFragment>(E);
		V.Energy = FMath::Min(V.MaxEnergy, V.Energy + float(Result.GrantedAmount) * Profile.Settings.FoodEnergyGain);
		auto& Feed = EM.GetFragmentDataChecked<FEcoFeedingFragment>(E);
		Feed.bPending = false; Feed.LastFeedTime = Result.Request.DueTime;
		Feed.LastGrantedAmount = Result.GrantedAmount; Feed.TotalGrantedAmount += Result.GrantedAmount;
		EM.GetFragmentDataChecked<FEcoLifetimeFragment>(E).NextFeedTimeSeconds = Time.ServerTimeSeconds + 1.0;
	}
	if (!Ecology->CompleteResourceStep()) return false;
	TArray<FName> RegionIds; Ecology->GetRegionIds(RegionIds);
	TArray<FEcoResourceSnapshot> Resources; Ecology->GetResourceSnapshots(Resources);
	TArray<FEcoRegionSpatialSnapshot> Spaces;
	if (!GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->BuildSpatialSnapshots(RegionIds, Spaces)) return false;
	TArray<FEcoMigrationOutcome> Arrivals;
	if (!EcoMassMigration::Reconcile(EM, Time, ObservedTime, Step, Resources, Spaces, Migration,
		false, 1.0, nullptr, nullptr, {}, 0.0, &Arrivals, false)
		|| !Ecology->RecordMigrations(Arrivals) || !ReconcilePopulation()
		|| !Ecology->RefreshPopulationPressure(Time.ServerTimeSeconds)) return false;
	for (const auto& Arrival : Arrivals)
	{
		const auto* Entity = AgentLookup.Find(Arrival.StableAgentId);
		if (!Entity || !EM.IsEntityValid(*Entity)) return false;
		const FName Species = EM.GetFragmentDataChecked<FEcoIdentityFragment>(*Entity).SpeciesId;
		++SpeciesTotals.FindOrAdd(Arrival.OriginRegionId).FindOrAdd(Species).Outgoing;
		++SpeciesTotals.FindOrAdd(Arrival.DestinationRegionId).FindOrAdd(Species).Incoming;
	}
	if (Time.ServerTimeSeconds >= NextMigrationTime)
	{
		TArray<FEcoMigrationPressureSnapshot> Pressure;
		FEcoSurvivalSettings Survival;
		Survival.BaseMetabolism = EnergyDrainPerSecond; Survival.TravelMetabolism = 0;
		Survival.StarvationGraceSeconds = StarvationGraceSeconds; Survival.StarvationDamagePerSecond = StarvationDamagePerSecond;
		if (!Ecology->BuildMigrationPressure(Pressure)
			|| !EcoMassMigration::Reconcile(EM, Time, ObservedTime, Step, Resources, Spaces, Migration,
				true, 1.0, &PopulationPressure, &Survival, Pressure, 1.0, nullptr, false)) return false;
		NextMigrationTime = Time.ServerTimeSeconds + Migration.DecisionIntervalSeconds;
	}
	if (!BuildAgentLookup() || !ReconcilePopulation() || !Ecology->RefreshPopulationPressure(Time.ServerTimeSeconds)) return false;
	CompletedTime = Time;
	PublishSummary();
	return bReady;
}

void AEcoCreatureIntegrationSpawner::UpdatePresentationAndNoise(float Delta)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_PresentationSnapshot);
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
	for (const auto E : Owned)
	{
		const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		const auto& Life = EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(E);
		auto& Present = EM.GetFragmentDataChecked<FEcoCreaturePresentationFragment>(E);
		Present.Velocity = V.HP > 0 ? EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value : FVector::ZeroVector;
		const auto* Predator = EM.GetFragmentDataPtr<FEcoPredatorStateFragment>(E);
		const auto* Execution = EM.GetFragmentDataPtr<FEcoSpeciesAIExecutionFragment>(E);
		const bool Eating = (Predator && Predator->EatCooldown > 0) || (Execution && Execution->Activity == EEcoSpeciesActivity::Graze);
		const bool Pursuing = Life.bPursuing || (Execution && Execution->Activity == EEcoSpeciesActivity::Pursue);
		Present.Flags = (V.HP > 0 ? 1 : 0) | (Eating ? 2 : 0) | (Pursuing ? 4 : 0) | 8;
		Present.Activity = Execution ? uint8(Execution->Activity) : uint8(EEcoSpeciesActivity::Hold);
        if (const auto* Behavior = EM.GetFragmentDataPtr<FEcoBehaviorStateFragment>(E))
        {
            const EEcoSpeciesActivity Activities[] = {EEcoSpeciesActivity::Graze, EEcoSpeciesActivity::Flee,
                Behavior->Rep.bArrived ? EEcoSpeciesActivity::ShelterHold : EEcoSpeciesActivity::ShelterTravel,
                EEcoSpeciesActivity::Freeze, EEcoSpeciesActivity::Sleep};
            Present.Activity = uint8(Behavior->BehaviorId < UE_ARRAY_COUNT(Activities) ? Activities[Behavior->BehaviorId] : EEcoSpeciesActivity::Hold);
            if (Behavior->BehaviorId == 0) Present.Flags |= 2;
        }
        if (const auto* Threat = EM.GetFragmentDataPtr<FEcoThreatStateFragment>(E))
        {
            const EEcoSpeciesActivity Activities[] = {EEcoSpeciesActivity::Wander, EEcoSpeciesActivity::Stalk,
                EEcoSpeciesActivity::Pounce, EEcoSpeciesActivity::Exhaust, EEcoSpeciesActivity::Pursue, EEcoSpeciesActivity::Eat, EEcoSpeciesActivity::Sleep,
                EEcoSpeciesActivity::Rest, EEcoSpeciesActivity::Wander};
            static_assert(UE_ARRAY_COUNT(Activities) == static_cast<uint8>(EcoV3Integrated::EWolfState::Count),
                "Every v3 wolf state must have a presentation activity.");
            const uint8 StateIndex = static_cast<uint8>(EcoV3Integrated::WolfStateOf(Threat->Agent));
            Present.Activity = uint8(StateIndex < UE_ARRAY_COUNT(Activities) ? Activities[StateIndex] : EEcoSpeciesActivity::Hold);
        }
		if (const auto* Cue = EM.GetFragmentDataPtr<FEcoCreatureCueFragment>(E)) {
            Present.Flags |= uint8(Cue->Memory.Source)<<4;
            Present.FocusYaw = Cue->FocusYaw;
        }
        Present.Health = EcoRepresentation::QuantizeUnit(V.HP / FMath::Max(V.MaxHP, 1.f));
		Present.Energy = EcoRepresentation::QuantizeUnit(V.Energy / FMath::Max(V.MaxEnergy, 1.f));
		// Observe the single movement writer's completed result. Never move the agent here.
		auto& Cadence = EM.GetFragmentDataChecked<FEcoCreatureFootstepFragment>(E).Cadence;
		if (FootstepAudioSet && FootstepAudioSet->IsValidConfiguration())
		{
			const FVector Position = EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
			const float Speed = Present.Velocity.Size2D();
			if (Cadence.Advance(Position, Speed, V.HP > 0, Delta, FootstepAudioSet->GetStride(Speed), FootstepAudioSet->MinimumSpeed))
				if (auto* Noise = GetWorld()->GetSubsystem<UEcoNoiseSubsystem>())
				{
					const auto& Identity = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
					const float Loudness = FMath::Lerp(0.45f, 1.f, FMath::Clamp((Speed - 250.f) / 650.f, 0.f, 1.f));
					Noise->ReportCreatureFootstep(Position, Loudness, FootstepAudioSet->NoiseRange,
						Identity.SpeciesId == TEXT("Wolf") ? FootstepAudioSet->PredatorThreat : 0.f,
						Identity.StableAgentId, Identity.SpeciesId);
				}
		}
		else Cadence.Reset();
	}
}

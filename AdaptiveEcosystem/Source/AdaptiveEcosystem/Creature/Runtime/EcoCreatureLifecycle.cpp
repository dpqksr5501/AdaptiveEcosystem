#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "Creature/Runtime/EcoFaunaMotionClock.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "Engine/World.h"
#include "Creature/Audio/EcoFootstepAudioSet.h"
#include "Player/EcoMeleeHitComponent.h"
#include "Player/EcoWeaponFireComponent.h"
#include "AI/Social/Senses/EcoNoiseSubsystem.h"
#include "AI/Policy/EcoBehaviorFragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedFragments.h"
#include "AI/Policy/EcoPolicyV3Fragments.h"
#include "AI/Policy/EcoPolicyV3IntegratedSubsystem.h"
#include "AI/Policy/EcoPolicyV3IntegratedProcessors.h"
#include "AI/Policy/EcoBehaviorConfig.h"
#include "MassExecutionContext.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/EcoPolicyV3SocialBridge.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Mass/EcoMassMigration.h"
#include "Mass/EcoHerdMigration.h"
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
	int32 RemainingResourceSteps = MaxCatchUpSteps;
	const auto AdvanceResources = [&](double Through)
	{
		for (; RemainingResourceSteps > 0; --RemainingResourceSteps)
		{
			FEcoServerTimeSnapshot Previous;
			if (!Clock->GetSnapshotAt(LastResourceTime, Previous)) { FailRuntime(TEXT("Historical clock snapshot")); return false; }
			double NextTime = FMath::Min(LastResourceTime + 1.0, Ecology->GetNextScheduledTime(Previous, bEnableWaves && IsSpeciesEnabled(false)));
			if (Migration.bEnabled) NextTime = FMath::Min(NextTime, NextMigrationTime);
			// Combat contacts wake the serialized survival/death/resource transaction.
			if (bEnableEcosystemLife && bEnablePlayerCombat)
			{
				double ContactTime = MAX_dbl;
				for (const auto& Request : ComboDamage) ContactTime = FMath::Min(ContactTime, Request.Issued);
				for (const auto& Pair : WolfCombat)
					if (Pair.Value.bPending) ContactTime = FMath::Min(ContactTime, Pair.Value.ContactTime);
				if (ContactTime < MAX_dbl) NextTime = FMath::Min(NextTime, FMath::Max(LastResourceTime + .001, ContactTime));
			}
			// Keep per-agent meal times aligned when a phase or wave divides the second.
			for (const auto E : Owned)
			{
				const auto& Id = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
				const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
				const auto& Travel = EM.GetFragmentDataChecked<FEcoTravelFragment>(E);
				const double Due = EM.GetFragmentDataChecked<FEcoLifetimeFragment>(E).NextFeedTimeSeconds;
				if (V.HP > 0 && Id.SpeciesId == TEXT("Herbivore") && Travel.State == EEcoResidenceState::Resident && Due > LastResourceTime
					&& !EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E))
					NextTime = FMath::Min(NextTime, Due);
				if (const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(E);
					Fauna && V.HP > 0 && Fauna->AttackContact > LastResourceTime)
					NextTime = FMath::Min(NextTime, Fauna->AttackContact);
			}
			if (NextTime > Through) break;
			FEcoServerTimeSnapshot Time;
			const int32 BeforeCount = Owned.Num();
			if (!Clock->GetSnapshotAt(NextTime, Time) || !ProcessResourceStep(Time, Through)
				|| (Owned.Num() != BeforeCount && !BuildAgentLookup()))
			{ FailRuntime(TEXT("Creature resource/survival step")); return false; }
			LastResourceTime = Time.ServerTimeSeconds;
		}
		return true;
	};
	if (FaunaSpecies.IsEmpty())
	{
		if (!AdvanceResources(Now)) return;
	}
	else
	{
		using namespace EcoFaunaMotionClock;
		auto* Native = GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
		if (!Native || !Native->IsActive() || !Native->UsesAuthorityBoundaries())
		{ FailRuntime(TEXT("Mixed fauna requires the authority clock")); return; }
		// Native contexts become ready in the pre-actor tick following authority startup.
		// Retain the initial time debt until both backends can process it.
		if (Native->NumContexts() == 0) return;
		if (!MixedNativeStep)
		{
			AuthorityClockWorldOrigin = GetWorld()->GetTimeSeconds() - Now;
			MixedNativeStep = NewObject<UEcoPolicyV3IntegratedStepProcessor>(this);
			MixedNativeTransforms = NewObject<UEcoPolicyV3IntegratedVisualProcessor>(this);
			MixedNativeStep->CallInitialize(GetWorld(), EM.AsShared());
			MixedNativeTransforms->CallInitialize(GetWorld(), EM.AsShared());
		}
		if (FaunaMotionTime < 0.) FaunaMotionTime = 0.;
		if (!AdvanceResources(FaunaMotionTime)) return;
		const int64 LastReadyStep = CompletedStepAt(Now);
		for (int32 Pass = 0; Pass < MaxStepsPerFrame && RemainingResourceSteps > 0; ++Pass)
		{
			const int64 NextStep = CompletedStepAt(FaunaMotionTime) + 1;
			if (NextStep > LastReadyStep) break;
			double End = StepTime(NextStep);
			for (const auto Entity : Owned)
				if (const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(Entity);
					Fauna && Fauna->AttackContact > FaunaMotionTime + UE_SMALL_NUMBER)
					End = FMath::Min(End, Fauna->AttackContact);
			MoveFauna(float(End - FaunaMotionTime), End);
			FaunaMotionTime = End;
			const int64 NativeBoundary = (Native->GetGlobalStep() + 1) * EcoBehaviorConfig::PolicyInterval;
			if (NextStep == NativeBoundary && End == StepTime(NextStep))
			{
				auto Context = EM.CreateExecutionContext(EcoBehaviorConfig::StepSeconds);
				Context.SetExecutionType(EMassExecutionContextType::Processor);
				Context.SetFlushDeferredCommands(false);
				MixedNativeStep->ExecuteAuthorityBoundary(EM, Context, AuthorityClockWorldOrigin + End, End);
				if (!Native->IsActive() || Native->GetGlobalStep() * EcoBehaviorConfig::PolicyInterval != NextStep)
				{ FailRuntime(TEXT("Native boundary did not advance")); return; }
				MixedNativeTransforms->PublishAuthorityBoundary(EM, Context);
			}
			if (!AdvanceResources(End)) return;
		}
	}
	const double CleanupTime = FaunaSpecies.IsEmpty() ? Now : FaunaMotionTime;
	if (!EcoMassSurvival::RemoveExpired(EM, CleanupTime, true) || !BuildAgentLookup())
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
    ProcessPlayerStrikes(Time);
    ProcessCombatDamage(Time);
    ProcessFaunaPredation(Time.ServerTimeSeconds);
	FEcoSurvivalSettings Fallback;
	if (!EcoMassSurvival::Advance(EM, Time, ObservedTime, NextStep, Fallback, Deaths, true)
		|| !Ecology->RecordDeaths(Deaths, NextStep)) return false;
	CommittedDeaths += Deaths.Num();
	for (const auto& Death : Deaths)
	{
        ++SpeciesTotals.FindOrAdd(Death.RegionId).FindOrAdd(Death.SpeciesId).Deaths;
        if (const auto* Kill = PendingHuntingDeaths.Find(Death.StableAgentId))
        {
            ++CombatDiagnostics.HuntingDeaths;
            auto Outcome=Kill->Outcome; Outcome.Result=EEcoDamageResult::DeathCommitted;
            if (auto* Source=Kill->Source.Get()) Source->PublishDamageOutcome(Outcome);
            if (auto* Weapon=Kill->WeaponSource.Get()) Weapon->PublishDamageOutcome(Outcome);
            PendingHuntingDeaths.Remove(Death.StableAgentId);
            UE_LOG(LogTemp,Log,TEXT("[EcoCombat][DeathCommitted] Id=%lld Species=%s Region=%s Step=%lld"),Death.StableAgentId,*Death.SpeciesId.ToString(),*Death.RegionId.ToString(),NextStep);
        }
        const double NativeNutrition = bEnableEcosystemLife ? CommitNativeCarcass(Death) : 0.;
        if (!FaunaSpecies.IsEmpty())
        {
            // Native nutrition is normalized; the fauna stock uses vitality energy.
            CommitFaunaCarcass(Death, float(NativeNutrition * 100.));
            continue;
        }
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
			const int32 Actual = Spawn(G.RegionId, Request.Count, false, Time);
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
	if (!GetWorld()->GetSubsystem<UEcologyWorldSubsystem>()->BuildSpatialSnapshots(RegionIds, Spaces, true)) return false;
	TArray<FEcoMigrationOutcome> Arrivals;
	if(auto* HerdMigration=GetWorld()->GetSubsystem<UEcoHerdMigrationSubsystem>())
        if(!HerdMigration->Reconcile(EM,Time,Step,Arrivals,Spaces))return false;
    TArray<FEcoMigrationOutcome> LegacyArrivals;
	if (!EcoMassMigration::Reconcile(EM, Time, ObservedTime, Step, Resources, Spaces, Migration,
		false, 1.0, nullptr, nullptr, {}, 0.0, &LegacyArrivals, false))return false;
    Arrivals.Append(LegacyArrivals);
    ReconcileFaunaPassages(EM, Time, ObservedTime, Step, Arrivals);
    if (!Ecology->RecordMigrations(Arrivals) || !ReconcilePopulation()
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
    if(!ProcessNaturalBirths(Time)||!ProcessFauna(Time)||!ProcessPopulationRecovery(Time)||(bEnableEcosystemLife&&!ReconcilePopulation()))return false;
    PublishForageVisuals();
	CompletedTime = Time;
	PublishSummary();
	return bReady;
}

void AEcoCreatureIntegrationSpawner::UpdatePresentationAndNoise(float Delta)
{
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoCreature_PresentationSnapshot);
	auto& EM = GetWorld()->GetSubsystem<UMassSpawnerSubsystem>()->GetEntityManagerChecked();
    const bool bEmitFootsteps = FootstepAudioSet && FootstepAudioSet->IsValidConfiguration();
	for (const auto E : Owned)
	{
		const auto& V = EM.GetFragmentDataChecked<FEcoVitalsFragment>(E);
		const auto& Life = EM.GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(E);
		auto& Present = EM.GetFragmentDataChecked<FEcoCreaturePresentationFragment>(E);
        const uint8 PreviousActivity = Present.Activity;
        Present.BodyScale=128;Present.Maturity=255;Present.CoatTone=128;
        if(bEnableEcosystemLife)if(const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);Link&&Link->Individual.bInitialized)
            {
            const double AgeNow=V.HP<=0&&Life.DeathTime>=0?Life.DeathTime:GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
            if(Link->Individual.bNaturalPopulation)Present.CoatTone=uint8(FMath::RoundToInt(FMath::Clamp((Link->Individual.Genome.Coat-.85)/.3,0.,1.)*255));
            Present.Maturity=uint8(FMath::RoundToInt(Link->Individual.AgeFraction(AgeNow)*255));
            Present.BodyScale=uint8(FMath::RoundToInt(Link->Individual.BodyScale(
                V.HP<=0 && Life.DeathTime>=0 ? Life.DeathTime :
                GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds)*128));
        }
		Present.Velocity = V.HP > 0 ? EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value : FVector::ZeroVector;
		const auto* Predator = EM.GetFragmentDataPtr<FEcoPredatorStateFragment>(E);
		const auto* Execution = EM.GetFragmentDataPtr<FEcoSpeciesAIExecutionFragment>(E);
		const bool Eating = (Predator && Predator->EatCooldown > 0) || (Execution && Execution->Activity == EEcoSpeciesActivity::Graze);
		const bool Pursuing = Life.bPursuing || (Execution && Execution->Activity == EEcoSpeciesActivity::Pursue);
		Present.Flags = (V.HP > 0 ? 1 : 0) | (Eating ? 2 : 0) | (Pursuing ? 4 : 0) | 8;
		Present.Activity = Execution ? uint8(Execution->Activity) : uint8(EEcoSpeciesActivity::Hold);
        if (const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(E))
        {
            const double Now = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
            const double AgeTime = V.HP <= 0 && Life.DeathTime >= 0. ? Life.DeathTime : Now;
            Present.BodyScale = uint8(FMath::RoundToInt(Fauna->Life.BodyScale(AgeTime) * 128.));
            Present.Maturity = EcoRepresentation::QuantizeUnit(Fauna->Life.AgeFraction(AgeTime));
            const bool bMeal = Fauna->LastMeal >= 0. && Now - Fauna->LastMeal < 1. && V.HP > 0;
            if (bMeal) Present.Flags |= 2;
            switch (Fauna->Flight)
            {
                case EEcoFaunaFlightPhase::Takeoff: Present.Activity = uint8(EEcoSpeciesActivity::Takeoff); break;
                case EEcoFaunaFlightPhase::Cruise: Present.Activity = uint8(EEcoSpeciesActivity::Fly); break;
                case EEcoFaunaFlightPhase::Landing: Present.Activity = uint8(EEcoSpeciesActivity::Land); break;
                case EEcoFaunaFlightPhase::Dive: Present.Activity = uint8(EEcoSpeciesActivity::Attack); break;
                default:
                    if (Fauna->bSwimming)
                        Present.Activity = uint8(Fauna->ShorePhase == EEcoFaunaShorePhase::Entering ? EEcoSpeciesActivity::EnterWater
                            : Fauna->ShorePhase == EEcoFaunaShorePhase::Exiting ? EEcoSpeciesActivity::ExitWater : EEcoSpeciesActivity::Swim);
                    else if (Fauna->AttackContact >= 0.) Present.Activity = uint8(EEcoSpeciesActivity::Attack);
                    else if (bMeal) Present.Activity = uint8(EEcoSpeciesActivity::Eat);
                    else if (Now < Fauna->ThreatUntil) Present.Activity = uint8(EEcoSpeciesActivity::Flee);
                    else if (Now < Fauna->RootingUntil) Present.Activity = uint8(EEcoSpeciesActivity::Forage);
                    else if (Fauna->CarrionTargetId > 0 || Fauna->bInvestigatingNoise) Present.Activity = uint8(EEcoSpeciesActivity::Investigate);
                    else if (Fauna->TargetId > 0)
                    {
                        Present.Activity = uint8(Fauna->bStalking ? EEcoSpeciesActivity::Stalk : EEcoSpeciesActivity::Pursue);
                        if (!Fauna->bStalking) Present.Flags |= 4;
                    }
                    else if (Fauna->bFollowingCaregiver && !Present.Velocity.IsNearlyZero())
                        Present.Activity = uint8(EEcoSpeciesActivity::Regroup);
                    else Present.Activity = uint8(Present.Velocity.IsNearlyZero() ? EEcoSpeciesActivity::Rest : EEcoSpeciesActivity::Wander);
                    break;
            }
        }
        if (const auto* Behavior = EM.GetFragmentDataPtr<FEcoBehaviorStateFragment>(E))
        {
            const EEcoSpeciesActivity Activities[] = {EEcoSpeciesActivity::Graze, EEcoSpeciesActivity::Flee,
                Behavior->Rep.bArrived ? EEcoSpeciesActivity::ShelterHold : EEcoSpeciesActivity::ShelterTravel,
                EEcoSpeciesActivity::Freeze, EEcoSpeciesActivity::Sleep};
            Present.Activity = uint8(Behavior->BehaviorId < UE_ARRAY_COUNT(Activities) ? Activities[Behavior->BehaviorId] : EEcoSpeciesActivity::Hold);
            if (Behavior->BehaviorId == 0) Present.Flags |= 2;
            if(NaturalHabitatProfile||!RegionHabitatProfiles.IsEmpty()){
                if(const auto* Body=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E)){
                    if(Body->Body.LastIntake<=1.e-9)Present.Flags&=~uint8(2);
                }
                if(EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E))if(const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);Link&&Link->Individual.bInitialized){
                    const double Now=V.HP<=0&&Life.DeathTime>=0?Life.DeathTime:
                        GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
                    const auto Id=EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId;
                    const uint8 Appearance=Link->Individual.bNaturalPopulation?(Link->Individual.Sex==EcoLifeV3::ESex::Male?1:2):
                        (Link->Individual.Growth(Now)<.97?3:uint8(1+EcoLifeV3::Mix(uint64(Id))%2));
                    Present.Flags=EcoPresentationFlags::WithAppearance(Present.Flags,Appearance);
                }
            }
            if(Behavior->Decision.KeepActive==EcoWorldV3::kKeepAlert&&Behavior->BehaviorId==EcoRepertoireV3::kGraze)
                Present.Activity=uint8(EEcoSpeciesActivity::AlertGraze);
            else if(const auto* Body=EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E);Body&&Body->Body.bWeak
                &&Present.Velocity.SizeSquared2D()>1)Present.Activity=uint8(EEcoSpeciesActivity::WeakTravel);
            if(const auto* J=EM.GetFragmentDataPtr<FEcoHerdTravelFragment>(E);J&&J->bActive
                &&Behavior->Decision.KeepActive!=EcoWorldV3::kKeepPanic&&Behavior->Decision.KeepActive!=EcoWorldV3::kKeepShelter){
                Present.Activity=uint8(J->bPause?EEcoSpeciesActivity::Rest:EEcoSpeciesActivity::Travel);
                if(!J->bPause)Present.Flags&=~uint8(2);
            }
            if(bEnableEcosystemLife)if(const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);Link&&Link->Individual.bInitialized){
                if (UsesAdaptiveRoutine(EEcoAdaptiveRoutine::DeerMeal))
                {
                    if (const auto* Body = EM.GetFragmentDataPtr<FEcoHerbivoreBodyV3Fragment>(E); Body && Body->Body.LastIntake <= 1.e-9)
                        Present.Flags &= ~uint8(2);
                    if (Link->Individual.bMealRestApplied)
                        Present.Activity = uint8(EEcoSpeciesActivity::SatedRest);
                }
                if(NaturalHabitatProfile){
                    switch(Link->Individual.Residence.Phase){
                        case 1:case 5:Present.Activity=uint8(EEcoSpeciesActivity::ShelterTravel);Present.Flags&=~uint8(2);break;
                        case 2:Present.Activity=uint8(EEcoSpeciesActivity::Vigilant);Present.Flags&=~uint8(2);break;
                        case 4:Present.Activity=uint8(EEcoSpeciesActivity::Flee);Present.Flags&=~uint8(2);break;
                        default:break;
                    }
                }
                switch(Link->Individual.Memory.Response){
                    case EcoLifeV3::EResponse::Curious:Present.Activity=uint8(EEcoSpeciesActivity::Curious);Present.Flags&=~uint8(2);break;
                    case EcoLifeV3::EResponse::Vigilant:Present.Activity=uint8(EEcoSpeciesActivity::Vigilant);Present.Flags&=~uint8(2);break;
                    case EcoLifeV3::EResponse::Retreat:Present.Activity=uint8(EEcoSpeciesActivity::Flee);Present.Flags&=~uint8(2);break;
                    default:break;
                }
            }
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
            if(Threat->Agent.State.SatLeft>0&&Threat->Agent.State.Cooldown<=0&&!Threat->Agent.State.bAsleep)
                Present.Activity=uint8(EEcoSpeciesActivity::SatedRest);
            if (UsesAdaptiveRoutine(EEcoAdaptiveRoutine::WolfMeal))
                if (const auto* Link = EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);
                    Link && Link->Individual.bMealRestApplied && !Threat->Agent.State.bAsleep)
                    Present.Activity = uint8(EEcoSpeciesActivity::SatedRest);
            if(bEnableEcosystemLife)if(const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);
                Link&&Link->Individual.Investigation.Role==EcoTracesV3::ERole::Investigate)Present.Activity=uint8(EEcoSpeciesActivity::Investigate);
            if(bEnableEcosystemLife)if(const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);
                Link&&Link->Individual.LastMeatIntake>0){Present.Activity=uint8(EEcoSpeciesActivity::Eat);Present.Flags|=2;}
            if(bEnableEcosystemLife)if(const auto* Link=EM.GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E);Link){
                const auto Response=Link->Individual.Memory.Response;
                if(Response==EcoLifeV3::EResponse::Curious)Present.Activity=uint8(EEcoSpeciesActivity::Curious);
                else if(Response==EcoLifeV3::EResponse::Vigilant)Present.Activity=uint8(EEcoSpeciesActivity::Vigilant);
                else if(Response==EcoLifeV3::EResponse::Retreat)Present.Activity=uint8(EEcoSpeciesActivity::Flee);
            }
        }
        if (const auto* Combat=WolfCombat.Find(EM.GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId);Combat&&Combat->Target.IsValid())
            Present.Activity=uint8(Combat->Due>=0||Combat->bPending?EEcoSpeciesActivity::Attack:EEcoSpeciesActivity::Pursue);
        if(auto* Audit=EM.GetFragmentDataPtr<FEcoV3SocialBridgeFragment>(E)){
            FName Reason=TEXT("NativePolicy");
            const auto* B=EM.GetFragmentDataPtr<FEcoBehaviorStateFragment>(E);
            const auto* J=EM.GetFragmentDataPtr<FEcoHerdTravelFragment>(E);
            if(V.HP<=0)Reason=TEXT("Dead");
            else if(B&&B->Decision.KeepActive==EcoWorldV3::kKeepPanic)Reason=TEXT("NativeThreatEscape");
            else if(B&&B->Decision.KeepActive==EcoWorldV3::kKeepShelter)Reason=TEXT("NativeRefugeSafety");
            else if(J&&J->bActive)Reason=J->Reason;
            else if(J&&J->bStranded)Reason=TEXT("JourneyAbandonedOutsideRegion");
            else if(bEnableEcosystemLife&&Present.Activity==uint8(EEcoSpeciesActivity::Curious))Reason=TEXT("ObservedHarmlessCuriosity");
            else if(bEnableEcosystemLife&&Present.Activity==uint8(EEcoSpeciesActivity::Vigilant))Reason=TEXT("RecentEncounterVigilance");
            else if(bEnableEcosystemLife&&Present.Activity==uint8(EEcoSpeciesActivity::Flee))Reason=TEXT("RecentEncounterRetreat");
            else if(bEnableEcosystemLife&&Present.Activity==uint8(EEcoSpeciesActivity::Investigate))Reason=TEXT("MovementTraceInvestigation");
            else if(Present.Activity==uint8(EEcoSpeciesActivity::AlertGraze))Reason=TEXT("NativeAlertGraze");
            else if(Present.Activity==uint8(EEcoSpeciesActivity::WeakTravel))Reason=TEXT("LowEnergyReserve");
            else if(Audit->Applied!=EEcoV3SocialControl::None)Reason=TEXT("LegacySocialOverride");
            else if(const auto* Sense=EM.GetFragmentDataPtr<FEcoSensoryStateFragment>(E)){
                const auto* Alarm=EM.GetFragmentDataPtr<FEcoAlarmStateFragment>(E);
                const auto* Member=EM.GetFragmentDataPtr<FEcoHerdMemberFragment>(E);
                const auto* Herds=GetWorld()->GetSubsystem<UEcoHerdSubsystem>();FEcoHerdRuntimeData Herd;
                const int64 HerdId=Member&&Herds&&Herds->GetHerdData(Member->HerdRuntimeIndex,Herd)?Herd.PersistentHerdId:0;
                const auto* Shared=EM.GetSharedFragmentDataPtr<FEcoSocialSpeciesSharedFragment>(E);
                const auto Signal=Alarm?EcoV3Social::ReadSignal(*Sense,*Alarm,HerdId,GetWorld()->GetTimeSeconds(),Shared?Shared->Senses:FEcoSensorySettings()):FEcoSocialSignalSnapshot();
                if(Signal.bValid&&Signal.PersonalSource==EEcoSenseSource::None)Reason=TEXT("SharedAlarmSignalOnly");
            }
            const auto* Native=GetWorld()->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
            Audit->RecordReason(GetWorld()->GetTimeSeconds(),Reason,EM.GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId,
                Native?Native->GetGlobalStep():0);
        }
		if (const auto* Cue = EM.GetFragmentDataPtr<FEcoCreatureCueFragment>(E)) {
            Present.Flags |= uint8(Cue->Memory.Source)<<4;
            Present.FocusYaw = Cue->FocusYaw;
        }
        if (V.HP <= 0.f && !FaunaSpecies.IsEmpty() && Life.DeathTime >= 0.)
        {
            const auto& Identity = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
            const auto* Profile = FindFauna(Identity.SpeciesId);
            const auto* Fauna = EM.GetFragmentDataPtr<FEcoFaunaFragment>(E);
            const double Now = GetWorld()->GetSubsystem<UEcoWorldClockSubsystem>()->GetServerTime().ServerTimeSeconds;
            const double SettleStart = Fauna ? FMath::Max(Life.DeathTime, Fauna->PhaseUntil) : Life.DeathTime;
            if ((!Fauna || Fauna->Flight == EEcoFaunaFlightPhase::Grounded)
                && Now >= SettleStart + (Profile ? Profile->DeathSettleSeconds : 1.3))
                Present.Activity = uint8(EEcoSpeciesActivity::CorpseSettled);
        }
        Present.Health = EcoRepresentation::QuantizeUnit(V.HP / FMath::Max(V.MaxHP, 1.f));
		Present.Energy = EcoRepresentation::QuantizeUnit(V.Energy / FMath::Max(V.MaxEnergy, 1.f));
		// Observe the single movement writer's completed result. Never move the agent here.
		auto& Cadence = EM.GetFragmentDataChecked<FEcoCreatureFootstepFragment>(E).Cadence;
		if (bEmitFootsteps)
		{
			const FVector Position = EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
			const float Speed = Present.Velocity.Size2D();
            const auto& Identity = EM.GetFragmentDataChecked<FEcoIdentityFragment>(E);
            const auto* Profile = FootstepAudioSet->FindProfile(Identity.SpeciesId);
            const float BodyScale = Present.BodyScale / 128.f;
            const float Spacing = Profile ? FootstepAudioSet->Evaluate(*Profile, EEcoFootstepSurface::Dry, Speed, BodyScale).Spacing
                : FootstepAudioSet->GetStride(Speed) * BodyScale;
            const float MinimumSpeed = Profile ? FMath::Min(FootstepAudioSet->MinimumSpeed, Profile->WalkSpeed * .35f)
                : FootstepAudioSet->MinimumSpeed;
            const bool bGrounded = V.HP > 0 && EcoFootsteps::IsGroundActivity(Present.Activity);
            const bool bTouchdown = Profile && bGrounded && PreviousActivity == uint8(EEcoSpeciesActivity::Land);
			if (Cadence.Advance(Position, Speed, bGrounded && !bTouchdown, Delta, Spacing, MinimumSpeed) || bTouchdown)
				if (auto* Noise = GetWorld()->GetSubsystem<UEcoNoiseSubsystem>())
				{
                    if (Profile)
                    {
                        FEcoFootstepContact Contact;
                        const auto& Region = EM.GetFragmentDataChecked<FEcoRegionFragment>(E);
                        if (!FootstepAudioSet->ResolveContact(*GetWorld(), Position, Region.CurrentRegionId, nullptr, Contact)) continue;
                        const auto Levels = FootstepAudioSet->Evaluate(*Profile, Contact.Surface, Speed, BodyScale);
                        const bool bDangerous = Pursuing || Present.Activity == uint8(EEcoSpeciesActivity::Stalk)
                            || Present.Activity == uint8(EEcoSpeciesActivity::Attack) || Present.Activity == uint8(EEcoSpeciesActivity::Pounce);
                        Noise->ReportCreatureFootstep(Contact.Position, Levels.Loudness, Levels.NoiseRange,
                            bDangerous ? Profile->Threat : 0.f, Identity.StableAgentId, Identity.SpeciesId, Region.CurrentRegionId);
                    }
                    else
                    {
                        const float Loudness = FMath::Lerp(0.45f, 1.f, FMath::Clamp((Speed - 250.f) / 650.f, 0.f, 1.f));
                        Noise->ReportCreatureFootstep(Position, Loudness, FootstepAudioSet->NoiseRange,
                            Identity.SpeciesId == TEXT("Wolf") ? FootstepAudioSet->PredatorThreat : 0.f,
                            Identity.StableAgentId, Identity.SpeciesId);
                    }
				}
		}
		else Cadence.Reset();
	}
}

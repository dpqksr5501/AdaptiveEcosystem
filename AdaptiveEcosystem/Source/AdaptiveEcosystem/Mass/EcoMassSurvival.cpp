#include "Mass/EcoMassSurvival.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassEntityManager.h"
#include "MassEntityView.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "MassCommandBuffer.h"
#include "MassMovementFragments.h"
#include "AdaptiveEcosystem.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Engine/World.h"

bool EcoMassSurvival::Advance(FMassEntityManager& Manager, const FEcoServerTimeSnapshot& Time, double ObservedTime,
	int64 StepId, const FEcoSurvivalSettings& Settings, TArray<FEcoDeathOutcome>& OutDeaths, bool bIntegratedCreatures)
{
	OutDeaths.Reset();
	if (!IsInGameThread() || Manager.IsProcessing() || !Settings.IsValid() || StepId <= 0 || Time.WorldEpoch <= 0
		|| !FMath::IsFinite(Time.ServerTimeSeconds) || !FMath::IsFinite(ObservedTime) || ObservedTime < Time.ServerTimeSeconds) return false;
	struct FUpdate
	{
		FMassEntityHandle Entity;
		FEcoVitalsFragment Vitals;
		FEcoVitalsRuntimeFragment Runtime;
		FEcoDeathOutcome Death;
		bool bDead = false;
		double Retention = 2.0;
	};
	TArray<FUpdate> Updates;
	bool bValid = true;
	FMassEntityQuery Query(Manager.AsShared());
	Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoVitalsRuntimeFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoDeathFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoFeedingFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoLifetimeFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoCreatureSurvivalFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	Query.AddRequirement<FMassDesiredMovementFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	Query.AddTagRequirement<FEcoIntegratedCreatureTag>(bIntegratedCreatures ? EMassFragmentPresence::All : EMassFragmentPresence::None);
	FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
	Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& Chunk)
	{
		const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
		const auto Regions = Chunk.GetFragmentView<FEcoRegionFragment>();
		const auto Vitals = Chunk.GetFragmentView<FEcoVitalsFragment>();
		const auto Runtime = Chunk.GetFragmentView<FEcoVitalsRuntimeFragment>();
		const auto Death = Chunk.GetFragmentView<FEcoDeathFragment>();
		const auto Travel = Chunk.GetFragmentView<FEcoTravelFragment>();
		const auto Feeding = Chunk.GetFragmentView<FEcoFeedingFragment>();
		const auto Lives = Chunk.GetFragmentView<FEcoLifetimeFragment>();
		const auto Profiles = Chunk.GetFragmentView<FEcoCreatureSurvivalFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			const auto& V = Vitals[I];
			const auto& R = Runtime[I];
			const auto& Profile = Profiles.IsEmpty() ? Settings : Profiles[I].Settings;
			if (!Profile.IsValid()) { bValid = false; continue; }
			if (Ids[I].StableAgentId <= 0 || Regions[I].CurrentRegionId.IsNone() || Death[I].bCommitted || Feeding[I].bPending
				|| R.WorldEpoch != Time.WorldEpoch || R.LastStepId >= StepId || !FMath::IsFinite(R.LastTime)
				|| !FMath::IsFinite(R.ZeroEnergySeconds) || R.ZeroEnergySeconds < 0
				|| !FMath::IsFinite(V.HP) || !FMath::IsFinite(V.MaxHP) || V.MaxHP <= 0
				|| !FMath::IsFinite(V.Energy) || !FMath::IsFinite(V.MaxEnergy) || V.MaxEnergy <= 0)
			{ bValid = false; continue; }
			// Catch-up never charges a future-born entity for time before its actual spawn.
			if (Time.ServerTimeSeconds < Lives[I].SpawnTimeSeconds) continue;
			if (Time.ServerTimeSeconds < R.LastTime) { bValid = false; continue; }
			FUpdate& U = Updates.AddDefaulted_GetRef();
			U.Entity = Chunk.GetEntity(I);
			U.Retention = Profile.DeadRetentionSeconds;
			U.Vitals = V;
			U.Runtime = R;
			U.Runtime.LastStepId = StepId;
			U.Runtime.LastTime = Time.ServerTimeSeconds;
			double DeathTime = Time.ServerTimeSeconds;
			EEcoDeathCause Cause = Death[I].Cause == EEcoDeathCause::None ? EEcoDeathCause::ExternalDamage : Death[I].Cause;
			if (Profile.bEnabled && V.HP > 0)
			{
				const double Dt = Time.ServerTimeSeconds - R.LastTime;
				const double Rate = Profile.BaseMetabolism + (Travel[I].State == EEcoResidenceState::Traveling ? Profile.TravelMetabolism : 0.0);
				const double StartEnergy = FMath::Clamp<double>(V.Energy, 0, V.MaxEnergy);
				const double ZeroAfter = StartEnergy <= 0 ? 0.0 : Rate > 0 ? StartEnergy / Rate : Dt;
				const double ZeroDuration = FMath::Max(0.0, Dt - ZeroAfter);
				const double PreviousZero = StartEnergy > 0 ? 0.0 : R.ZeroEnergySeconds;
				U.Vitals.Energy = static_cast<float>(FMath::Max(0.0, StartEnergy - Rate * Dt));
				U.Runtime.ZeroEnergySeconds = U.Vitals.Energy <= 0 ? PreviousZero + ZeroDuration : 0.0;
				const double DamageSeconds = FMath::Max(0.0, U.Runtime.ZeroEnergySeconds - Profile.StarvationGraceSeconds)
					- FMath::Max(0.0, PreviousZero - Profile.StarvationGraceSeconds);
				U.Vitals.HP = static_cast<float>(FMath::Max(0.0, V.HP - Profile.StarvationDamagePerSecond * DamageSeconds));
				if (U.Vitals.HP <= 0)
				{
					Cause = EEcoDeathCause::Starvation;
					DeathTime = R.LastTime + FMath::Min(Dt, ZeroAfter + FMath::Max(0.0, Profile.StarvationGraceSeconds - PreviousZero)
						+ V.HP / Profile.StarvationDamagePerSecond);
				}
			}
			U.bDead = U.Vitals.HP <= 0;
			if (U.bDead) U.Death = {Time.WorldEpoch, StepId, Ids[I].StableAgentId, Regions[I].CurrentRegionId, Ids[I].SpeciesId, Cause, DeathTime, Death[I].PredatorStableAgentId};
		}
	});
	if (!bValid) return false;
	// Entire pass validated before any state/tag is written.
	for (const FUpdate& U : Updates)
	{
		FMassEntityView View(Manager, U.Entity);
		View.GetFragmentData<FEcoVitalsFragment>() = U.Vitals;
		View.GetFragmentData<FEcoVitalsRuntimeFragment>() = U.Runtime;
		if (!U.bDead) continue;
		FEcoDeathFragment& Death = View.GetFragmentData<FEcoDeathFragment>();
		Death.bCommitted = true;
		Death.Cause = U.Death.Cause;
		Death.DeathTime = U.Death.Time;
		Death.RemoveAfter = ObservedTime + U.Retention;
		if (UWorld* World = Manager.GetWorld())
			if (auto* Shelter = World->GetSubsystem<UEcoShelterSubsystem>()) Shelter->ReleaseAgentReservations(U.Death.StableAgentId);
		View.GetFragmentData<FEcoTravelFragment>() = FEcoTravelFragment();
		View.GetFragmentData<FEcoFeedingFragment>() = FEcoFeedingFragment();
		View.GetFragmentData<FMassDesiredMovementFragment>().DesiredVelocity = FVector::ZeroVector;
		View.GetFragmentData<FMassVelocityFragment>().Value = FVector::ZeroVector;
		Manager.Defer().RemoveTag<FEcoAliveTag>(U.Entity);
		Manager.Defer().AddTag<FEcoPendingDeathTag>(U.Entity);
		OutDeaths.Add(U.Death);
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Death] Epoch=%d Step=%lld ID=%lld Region=%s Cause=%s Time=%.3f RemoveAfter=%.3f"),
			U.Death.WorldEpoch, StepId, U.Death.StableAgentId, *U.Death.RegionId.ToString(),
			U.Death.Cause == EEcoDeathCause::Starvation ? TEXT("Starvation") : U.Death.Cause == EEcoDeathCause::Predation ? TEXT("Predation") : TEXT("ExternalDamage"), U.Death.Time, Death.RemoveAfter);
	}
	if (!OutDeaths.IsEmpty()) Manager.FlushCommands();
	return true;
}

bool EcoMassSurvival::RemoveExpired(FMassEntityManager& Manager, double ObservedTime, bool bIntegratedCreatures)
{
	if (!IsInGameThread() || Manager.IsProcessing() || !FMath::IsFinite(ObservedTime)) return false;
	TArray<FMassEntityHandle> Remove;
	FMassEntityQuery Query(Manager.AsShared());
	Query.AddRequirement<FEcoDeathFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::None);
	Query.AddTagRequirement<FEcoIntegratedCreatureTag>(bIntegratedCreatures ? EMassFragmentPresence::All : EMassFragmentPresence::None);
	FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
	Query.ForEachEntityChunk(Context, [&](FMassExecutionContext& Chunk)
	{
		const auto Deaths = Chunk.GetFragmentView<FEcoDeathFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
			if (Deaths[I].bCommitted && Deaths[I].RemoveAfter <= ObservedTime) Remove.Add(Chunk.GetEntity(I));
	});
	if (!Remove.IsEmpty())
	{
		Manager.Defer().DestroyEntities(Remove);
		Manager.FlushCommands();
		UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Death Cleanup] Removed=%d Observed=%.3f"), Remove.Num(), ObservedTime);
	}
	return true;
}

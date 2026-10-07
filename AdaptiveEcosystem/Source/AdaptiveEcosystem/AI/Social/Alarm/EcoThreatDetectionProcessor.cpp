#include "AI/Social/Alarm/EcoThreatDetectionProcessor.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Herd/EcoHerdProcessors.h"
#include "AI/Social/Herd/EcoHerdSubsystem.h"
#include "AI/Policy/EcoBehaviorProcessors.h"
#include "AI/Policy/EcoNeighborhoodSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassCommonTypes.h"
#include "MassMovementFragments.h"
#include "MassExecutionContext.h"
#include "MassEntityView.h"
#include "MassActorSubsystem.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "World/EcologyWorldSubsystem.h"
#include "World/EcoWorldClockSubsystem.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"

static TAutoConsoleVariable<int32> CVarEcoSensesDebug(TEXT("eco.Senses.Debug"), 0,
	TEXT("Draw personal sight/hearing/memory knowledge (server/standalone only)."));

UEcoThreatDetectionProcessor::UEcoThreatDetectionProcessor() : EntityQuery(*this)
{
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionFlags = int32(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ExecutionOrder.ExecuteInGroup = UE::Mass::ProcessorGroupNames::Behavior;
	ExecutionOrder.ExecuteAfter.Add(UEcoHerdAggregateProcessor::StaticClass()->GetFName());
	ExecutionOrder.ExecuteAfter.Add(UEcoNeighborhoodGatherProcessor::StaticClass()->GetFName());
	bAutoRegisterWithProcessingPhases = true;
	bRequiresGameThreadExecution = true;
}

void UEcoThreatDetectionProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	EntityQuery.AddRequirement<FEcoHerdMemberFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FMassActorFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoSensoryStateFragment>(EMassFragmentAccess::ReadWrite, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoSensoryProfileFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	EntityQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	// Predator entities are outside the observer archetype. Declare indirect access so
	// the dependency solver accounts for their Vitals / representation writers as well.
	EntityQuery.AddIndirectFragmentRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddIndirectFragmentRequirement<FMassActorFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddSharedRequirement<FEcoSocialSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddSharedRequirement<FEcoSpeciesSharedFragment>(EMassFragmentAccess::ReadOnly);
	EntityQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	EntityQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	EntityQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
}

void UEcoThreatDetectionProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = Context.GetWorld();
	if (!World || World->GetNetMode() == NM_Client) { return; }
	UEcoHerdSubsystem* Herds = World->GetSubsystem<UEcoHerdSubsystem>();
	if (!Herds) { return; }
	const float DetectionDeltaSeconds = Context.GetDeltaTimeSeconds();
	if (!FMath::IsFinite(DetectionDeltaSeconds) || DetectionDeltaSeconds < 0.0f) { return; }
	TimeUntilScan -= DetectionDeltaSeconds;
	if (TimeUntilScan > 0.0f) { return; }
	TimeUntilScan = 0.2f; // At most one pass per frame; no catch-up trace bursts after a hitch.
	TRACE_CPUPROFILER_EVENT_SCOPE(EcoSensoryScan);
	const double Now = World->GetTimeSeconds();
	const bool bDraw = CVarEcoSensesDebug.GetValueOnGameThread() != 0 && World->GetNetMode() != NM_DedicatedServer;
	if (UEcoNoiseSubsystem* Noise = World->GetSubsystem<UEcoNoiseSubsystem>()) { Noise->GatherRecent(NoiseEvents); }
	else { NoiseEvents.Reset(); }
	const UEcologyWorldSubsystem* Regions = World->GetSubsystem<UEcologyWorldSubsystem>();
	const UEcoWorldClockSubsystem* Clock = World->GetSubsystem<UEcoWorldClockSubsystem>();

	const UEcoNeighborhoodSubsystem* Grid = World->GetSubsystem<UEcoNeighborhoodSubsystem>();
	Herds->GatherActorThreats(ActorThreats);
	BestThreats.SetNum(Herds->GetActiveHerds().Num());
	for (FEcoObservedHerdThreat& Threat : BestThreats) { Threat = {}; }

	EntityQuery.ForEachEntityChunk(Context, [&](FMassExecutionContext& Chunk)
	{
		const auto Members = Chunk.GetFragmentView<FEcoHerdMemberFragment>();
		const auto Transforms = Chunk.GetFragmentView<FTransformFragment>();
		const auto Velocities = Chunk.GetFragmentView<FMassVelocityFragment>();
		const auto Vitals = Chunk.GetFragmentView<FEcoVitalsFragment>();
		const auto Actors = Chunk.GetFragmentView<FMassActorFragment>();
		auto Senses = Chunk.GetMutableFragmentView<FEcoSensoryStateFragment>();
		const auto Profiles = Chunk.GetFragmentView<FEcoSensoryProfileFragment>();
		const auto Membership = Chunk.GetFragmentView<FEcoRegionFragment>();
		const auto& Social = Chunk.GetSharedFragment<FEcoSocialSpeciesSharedFragment>();
		const auto& Species = Chunk.GetSharedFragment<FEcoSpeciesSharedFragment>();
		if (!FMath::IsFinite(Species.ViewDistance) || Species.ViewDistance <= 0.0f
			|| !FMath::IsFinite(Species.FOV) || !FMath::IsFinite(Social.ThreatEyeHeight)
			|| !FMath::IsFinite(Social.AlarmDistanceDecay) || !Social.Senses.IsValid())
		{
			for (auto& Sense : Senses) { Sense.Forget(); }
			return;
		}
		// Limit malformed data before querying the uniform grid (radius controls cell iteration cost).
		const float CosHalfFov = FMath::Cos(FMath::DegreesToRadians(FMath::Clamp(Species.FOV, 0.0f, 360.0f) * 0.5f));
		const FVector EyeOffset(0.0f, 0.0f, FMath::Clamp(Social.ThreatEyeHeight, 0.0f, 500.0f));
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			const int32 HerdIndex = Members[I].HerdRuntimeIndex;
			FEcoSensoryStateFragment* Sense = Senses.IsEmpty() ? nullptr : &Senses[I];
			const FEcoSensoryProfileFragment Profile = Profiles.IsEmpty() ? FEcoSensoryProfileFragment() : Profiles[I];
			if (!Social.bDetectThreats || !Profile.IsValid()
				|| (!Vitals.IsEmpty() && (!FMath::IsFinite(Vitals[I].HP) || Vitals[I].HP <= 0.0f)))
			{
				if (Sense) { Sense->Forget(); }
				continue;
			}
			if (Sense) { Sense->Age(Now, Social.Senses, Profile.MemoryMultiplier); }
			const FVector Location = Transforms[I].GetTransform().GetLocation();
			if (Location.ContainsNaN()) { if (Sense) { Sense->Forget(); } continue; }
			FRegionEnvironmentState Environment;
			Environment.Rainfall = 0.0f; // No registered region means no fabricated rain input.
			if (Regions && !Membership.IsEmpty()) { Regions->GetEnvironmentState(Membership[I].CurrentRegionId, Environment); }
			// The running authority clock wins over a region's static authored DayPhase.
			if (Clock && Clock->IsClockRunning()) { Environment.DayPhase = Clock->GetServerTime().DayCycle.Phase; }
			const float Rain = FMath::IsFinite(Environment.Rainfall) ? FMath::Clamp(Environment.Rainfall, 0.0f, 1.0f) : 0.0f;
			const float NightScale = Environment.DayPhase == EEcoDayPhase::Night ? Social.Senses.NightVisionMultiplier : 1.0f;
			const float Radius = FMath::Clamp(Species.ViewDistance * Profile.VisionMultiplier * NightScale
				* FMath::Lerp(1.0f, Social.Senses.RainVisionMultiplier, Rain), 0.0f, 10000.0f);
			FEcoObservedHerdThreat LocalVisual;
			FVector Heading = Velocities[I].Value.GetSafeNormal2D();
			if (Heading.IsNearlyZero() || Heading.ContainsNaN())
			{
				Heading = Transforms[I].GetTransform().GetUnitAxis(EAxis::X).GetSafeNormal2D();
				if (Heading.IsNearlyZero() || Heading.ContainsNaN()) { Heading = FVector::ForwardVector; }
			}
			const FMassEntityHandle Observer = Chunk.GetEntity(I);
			const AActor* ObserverActor = Actors.IsEmpty() ? nullptr : Actors[I].Get();
			auto Consider = [&](const FVector& Position, float Strength, uint64 Key, const AActor* SourceActor)
			{
				if (Position.ContainsNaN() || !FMath::IsFinite(Strength) || Strength <= 0.0f
					|| (SourceActor && SourceActor == ObserverActor)) { return; }
				const FVector ToThreat = Position - Location;
				const float Distance = ToThreat.Size();
				if (Radius <= 0 || Distance > Radius) { return; }
				const FVector Direction = ToThreat.GetSafeNormal2D();
				if (!Direction.IsNearlyZero() && FVector::DotProduct(Heading, Direction) < CosHalfFov) { return; }
				const float Priority = Strength * FMath::Exp(-FMath::Max(0.0f, Social.AlarmDistanceDecay) * Distance);
				FEcoObservedHerdThreat& Best = LocalVisual;
				if (Priority < Best.Priority || (Priority == Best.Priority && Key >= Best.SourceKey)) { return; }
				if (Social.bThreatRequiresLineOfSight && Distance > KINDA_SMALL_NUMBER)
				{
					FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoSocialThreatLOS), false);
					Params.AddIgnoredActor(SourceActor);
					Params.AddIgnoredActor(ObserverActor);
					FHitResult Hit;
					if (World->LineTraceSingleByChannel(Hit, Location + EyeOffset, Position + EyeOffset, ECC_Visibility, Params)) { return; }
					Params.bTraceComplex = true;
					if (World->LineTraceSingleByChannel(Hit, Location + EyeOffset, Position + EyeOffset, ECC_Visibility, Params)) { return; }
				}
				Best.HerdRuntimeIndex = HerdIndex;
				Best.PersistentHerdId = Herds->IsValidHerdIndex(HerdIndex) ? Herds->GetActiveHerds()[HerdIndex].PersistentHerdId : 0;
				Best.Position = Position;
				Best.Strength = FMath::Clamp(Strength, 0.0f, 1.0f);
				Best.Priority = Priority; // Ranking only; reception attenuates once in AlarmPropagation.
				Best.SourceKey = Key;
			};

			if (Radius > 0 && Grid && Grid->IsBuilt())
			{
				Grid->QueryRadius(Location, Radius, CandidateIndices);
				for (const int32 Index : CandidateIndices)
				{
					const FEcoNeighborEntry& Entry = Grid->GetEntries()[Index];
					if (!Entry.bPredator || Entry.Entity == Observer || !EntityManager.IsEntityValid(Entry.Entity)) { continue; }
					const FMassEntityView View(EntityManager, Entry.Entity);
					if (View.HasTag<FEcoClientProxyTag>() || View.HasTag<FEcoPendingDeathTag>()) { continue; }
					const FEcoVitalsFragment* PredatorVitals = Chunk.GetIndirectConstFragmentPtr<FEcoVitalsFragment>(Entry.Entity);
					if (PredatorVitals && (!FMath::IsFinite(PredatorVitals->HP) || PredatorVitals->HP <= 0.0f)) { continue; }
					const FMassActorFragment* Actor = Chunk.GetIndirectConstFragmentPtr<FMassActorFragment>(Entry.Entity);
					const uint64 Key = (uint64(uint32(Entry.Entity.SerialNumber)) << 32) | uint32(Entry.Entity.Index);
					Consider(Entry.Location, 1.0f, Key, Actor ? Actor->Get() : nullptr);
				}
			}
			for (const FEcoActorThreatSnapshot& Threat : ActorThreats)
			{
				Consider(Threat.Position, Threat.Strength, Threat.SourceKey, Threat.Actor.Get());
			}
			FEcoObservedHerdThreat LocalHeard;
			float HeardConfidence = 0;
			const float HearingRange = FMath::Clamp(Social.Senses.HearingRange * Profile.HearingMultiplier
				* FMath::Lerp(1.0f, Social.Senses.RainHearingMultiplier, Rain), 0.0f, 10000.0f);
			// New templates have a per-agent watermark. Legacy templates remain sight-only.
			if (Sense)
			{
				const int64 PreviousNoiseId = Sense->LastProcessedNoiseId;
				for (const FEcoNoiseEvent& Noise : NoiseEvents)
				{
					Sense->LastProcessedNoiseId = FMath::Max(Sense->LastProcessedNoiseId, Noise.Id);
					if (Noise.Id <= PreviousNoiseId || Noise.ThreatStrength <= 0
						|| (ObserverActor && Noise.Instigator.Get() == ObserverActor)) { continue; }
					const float Range = FMath::Min(HearingRange, Noise.MaxRange);
					const float Distance = FVector::Dist(Location, Noise.Position);
					if (Range <= 0 || Distance >= Range) { continue; }
					float Confidence = Social.Senses.HearingConfidence * Noise.Loudness * (1.0f - Distance / Range);
					const float UpperPriority = Noise.ThreatStrength * Confidence
						* FMath::Exp(-FMath::Max(0.0f, Social.AlarmDistanceDecay) * Distance);
					if (Confidence < Social.Senses.MinimumConfidence || UpperPriority < LocalHeard.Priority) { continue; }
					FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoHearingOcclusion), false);
					Params.AddIgnoredActor(Noise.Instigator.Get());
					Params.AddIgnoredActor(ObserverActor);
					FHitResult Hit;
					bool bBlocked = World->LineTraceSingleByChannel(Hit, Location + EyeOffset, Noise.Position + EyeOffset, ECC_Visibility, Params);
					if (!bBlocked)
					{
						Params.bTraceComplex = true;
						bBlocked = World->LineTraceSingleByChannel(Hit, Location + EyeOffset, Noise.Position + EyeOffset, ECC_Visibility, Params);
					}
					if (bBlocked) { Confidence *= Social.Senses.OccludedHearingMultiplier; }
					const float Priority = Noise.ThreatStrength * Confidence
						* FMath::Exp(-FMath::Max(0.0f, Social.AlarmDistanceDecay) * Distance);
					if (Confidence < Social.Senses.MinimumConfidence || Priority < LocalHeard.Priority
						|| (Priority == LocalHeard.Priority && uint64(Noise.Id) >= LocalHeard.SourceKey)) { continue; }
					LocalHeard.Position = Noise.Position;
					LocalHeard.Strength = Noise.ThreatStrength * Confidence;
					LocalHeard.Priority = Priority;
					LocalHeard.SourceKey = uint64(Noise.Id);
					LocalHeard.HerdRuntimeIndex = HerdIndex;
					LocalHeard.PersistentHerdId = Herds->IsValidHerdIndex(HerdIndex) ? Herds->GetActiveHerds()[HerdIndex].PersistentHerdId : 0;
					HeardConfidence = Confidence;
				}
				if (LocalVisual.Strength > 0)
				{
					Sense->Observe(EEcoSenseSource::Sight, LocalVisual.Position, 1.0f, 0.0f, LocalVisual.Strength, LocalVisual.SourceKey, Now);
				}
				else if (LocalHeard.Strength > 0 && LocalHeard.Strength >= Sense->ThreatStrength * Sense->Confidence)
				{
					Sense->Observe(EEcoSenseSource::Hearing, LocalHeard.Position, HeardConfidence,
						Social.Senses.HearingUncertainty, LocalHeard.Strength / HeardConfidence, LocalHeard.SourceKey, Now);
				}
			}
			// Personal memories never feed back into the broadcast channel and cannot renew themselves.
			const FEcoObservedHerdThreat& LocalBest = LocalVisual.Priority >= LocalHeard.Priority ? LocalVisual : LocalHeard;
			if (Herds->IsValidHerdIndex(HerdIndex) && LocalBest.Strength > 0)
			{
				auto& Best = BestThreats[HerdIndex];
				if (LocalBest.Priority > Best.Priority || (LocalBest.Priority == Best.Priority && LocalBest.SourceKey < Best.SourceKey)) { Best = LocalBest; }
			}
			if (bDraw && Sense && Sense->Confidence > 0)
			{
				const FColor Color = Sense->Source == EEcoSenseSource::Sight ? FColor::Green
					: Sense->Source == EEcoSenseSource::Hearing ? FColor::Yellow : FColor::Cyan;
				DrawDebugLine(World, Location + EyeOffset, Sense->LastKnownPosition + EyeOffset, Color, false, 0.21f);
				DrawDebugSphere(World, Sense->LastKnownPosition, FMath::Max(20.0f, Sense->UncertaintyRadius), 12, Color, false, 0.21f);
				DrawDebugString(World, Location + EyeOffset, FString::Printf(TEXT("Sense=%d Confidence=%.2f Age=%.1fs Shared=%.2f"),
					int32(Sense->Source), Sense->Confidence, Now - Sense->LastObservedTime, Sense->SharedAlarmStrength), nullptr, Color, 0.21f);
			}
		}
	});
	Herds->ApplyObservedHerdThreats(BestThreats);
}

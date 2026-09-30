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
	const float Dt = Context.GetDeltaTimeSeconds();
	if (!FMath::IsFinite(Dt) || Dt < 0.0f) { return; }
	TimeUntilScan -= Dt;
	if (TimeUntilScan > 0.0f) { return; }
	TimeUntilScan = 0.2f; // At most one pass per frame; no catch-up trace bursts after a hitch.

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
		const auto& Social = Chunk.GetSharedFragment<FEcoSocialSpeciesSharedFragment>();
		const auto& Species = Chunk.GetSharedFragment<FEcoSpeciesSharedFragment>();
		if (!Social.bDetectThreats || !FMath::IsFinite(Species.ViewDistance) || Species.ViewDistance <= 0.0f
			|| !FMath::IsFinite(Species.FOV) || !FMath::IsFinite(Social.ThreatEyeHeight)
			|| !FMath::IsFinite(Social.AlarmDistanceDecay)) { return; }
		// Limit malformed data before querying the uniform grid (radius controls cell iteration cost).
		const float Radius = FMath::Min(Species.ViewDistance, 10000.0f);
		const float CosHalfFov = FMath::Cos(FMath::DegreesToRadians(FMath::Clamp(Species.FOV, 0.0f, 360.0f) * 0.5f));
		const FVector EyeOffset(0.0f, 0.0f, FMath::Clamp(Social.ThreatEyeHeight, 0.0f, 500.0f));
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			const int32 HerdIndex = Members[I].HerdRuntimeIndex;
			if (!Herds->IsValidHerdIndex(HerdIndex) || (!Vitals.IsEmpty() && (!FMath::IsFinite(Vitals[I].HP) || Vitals[I].HP <= 0.0f))) { continue; }
			const FVector Location = Transforms[I].GetTransform().GetLocation();
			if (Location.ContainsNaN()) { continue; }
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
				if (Distance > Radius) { return; }
				const FVector Direction = ToThreat.GetSafeNormal2D();
				if (!Direction.IsNearlyZero() && FVector::DotProduct(Heading, Direction) < CosHalfFov) { return; }
				const float Priority = Strength * FMath::Exp(-FMath::Max(0.0f, Social.AlarmDistanceDecay) * Distance);
				FEcoObservedHerdThreat& Best = BestThreats[HerdIndex];
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
				Best.PersistentHerdId = Herds->GetActiveHerds()[HerdIndex].PersistentHerdId;
				Best.Position = Position;
				Best.Strength = FMath::Clamp(Strength, 0.0f, 1.0f);
				Best.Priority = Priority; // Ranking only; reception attenuates once in AlarmPropagation.
				Best.SourceKey = Key;
			};

			if (Grid && Grid->IsBuilt())
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
		}
	});
	Herds->ApplyObservedHerdThreats(BestThreats);
}

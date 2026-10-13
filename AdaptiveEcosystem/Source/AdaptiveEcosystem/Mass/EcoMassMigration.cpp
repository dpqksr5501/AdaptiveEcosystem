#include "Mass/EcoMassMigration.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassCommonFragments.h"
#include "MassCommonTypes.h"
#include "MassMovementFragments.h"
#include "MassEntityManager.h"
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
	bool bDecisionDue, double FeedInterval, bool bResetResidentVelocity)
{
	if (!IsInGameThread() || Manager.IsProcessing() || Resources.Num() != Spaces.Num()) return false;
	for (int32 I = 0; I < Resources.Num(); ++I)
		if (Resources[I].RegionIndex != I || Resources[I].RegionId != Spaces[I].RegionId
			|| Resources[I].StepId != StepId || Resources[I].WorldEpoch != Time.WorldEpoch
			|| Resources[I].Time != Time.ServerTimeSeconds) return false;
	if (!Settings.bEnabled) return true;
	bool bValid = true;
	FMassEntityQuery Query(Manager.AsShared());
	Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddRequirement<FEcoLifetimeFragment>(EMassFragmentAccess::ReadWrite);
	Query.AddRequirement<FEcoFeedingFragment>(EMassFragmentAccess::ReadOnly);
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
		auto Regions = Chunk.GetMutableFragmentView<FEcoRegionFragment>();
		auto Travels = Chunk.GetMutableFragmentView<FEcoTravelFragment>();
		auto Lives = Chunk.GetMutableFragmentView<FEcoLifetimeFragment>();
		auto Moves = Chunk.GetMutableFragmentView<FMassDesiredMovementFragment>();
		auto Velocities = Chunk.GetMutableFragmentView<FMassVelocityFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
		{
			FEcoRegionFragment& Region = Regions[I];
			FEcoTravelFragment& Travel = Travels[I];
			const FVector Position = Transforms[I].GetTransform().GetLocation();
			if (!Spaces.IsValidIndex(Region.CurrentRegionIndex) || Feeds[I].bPending
				|| Spaces[Region.CurrentRegionIndex].RegionId != Region.CurrentRegionId || Position.ContainsNaN())
			{
				UE_LOG(LogAdaptiveEcosystem, Error, TEXT("[Eco Migration] Invalid input: ID=%lld Region=%s Index=%d PendingFeed=%d Position=%s Step=%lld"),
					Ids[I].StableAgentId, *Region.CurrentRegionId.ToString(), Region.CurrentRegionIndex, Feeds[I].bPending, *Position.ToCompactString(), StepId);
				bValid = false; continue;
			}
			const EEcoResidenceState Before = Travel.State;
			const int32 OldTarget = Travel.TargetRegionIndex;
			const FName From = Region.CurrentRegionId;
			bool bArrived = false;
			const auto HasFood = [&](int32 Index)
			{
				return Resources.IsValidIndex(Index) && Resources[Index].Food > Settings.FoodEpsilon;
			};
			if (bDecisionDue)
			{
				const bool bKeepTarget = Travel.State == EEcoResidenceState::Traveling && HasFood(Travel.TargetRegionIndex);
				if (!bKeepTarget)
				{
					int32 Target = INDEX_NONE;
					// A waiting/traveling agent away from its habitat must physically return before feeding.
					if (HasFood(Region.CurrentRegionIndex)) Target = Region.CurrentRegionIndex;
					else
					{
						double BestDistance = TNumericLimits<double>::Max();
						for (int32 Neighbor : Spaces[Region.CurrentRegionIndex].AdjacentIndices)
						{
							if (!HasFood(Neighbor)) continue;
							const double Distance = FVector::DistSquared(Position, Spaces[Neighbor].ArrivalPosition);
							if (Distance < BestDistance) { BestDistance = Distance; Target = Neighbor; }
						}
					}
					if (Target == Region.CurrentRegionIndex && Travel.State == EEcoResidenceState::Resident)
					{
						// Already resident; preserve its feeding reservation.
					}
					else if (Target != INDEX_NONE)
					{
						Travel.State = EEcoResidenceState::Traveling;
						Travel.TargetRegionIndex = Target;
						Travel.TargetRegionId = Spaces[Target].RegionId;
						Travel.TargetPosition = ArrivalFor(Spaces[Target], Ids[I].StableAgentId, Settings.ArrivalSpread);
						Travel.MoveSpeed = Settings.Speed;
					}
					else
					{
						Travel = FEcoTravelFragment();
						Travel.State = EEcoResidenceState::WaitingForFood;
					}
				}
			}
			// Commit only after engine movement from earlier frames, and only against current completed food.
			if (Travel.State == EEcoResidenceState::Traveling && HasFood(Travel.TargetRegionIndex)
				&& FVector::DistSquared(Position, Travel.TargetPosition) <= FMath::Square(Settings.ArrivalRadius)
				&& Spaces[Travel.TargetRegionIndex].Contains(Position))
			{
				Region.CurrentRegionIndex = Travel.TargetRegionIndex;
				Region.CurrentRegionId = Travel.TargetRegionId;
				Travel = FEcoTravelFragment();
				// Use observed arrival time, never a historical catch-up time; no accumulated missed meals.
				Lives[I].NextFeedTimeSeconds = ActualTime + FeedInterval;
				bArrived = true;
			}
			if (bResetResidentVelocity && Travel.State != EEcoResidenceState::Traveling)
			{
				Moves[I].DesiredVelocity = FVector::ZeroVector;
				Velocities[I].Value = FVector::ZeroVector;
			}
			if (Settings.bPrintTransitions && (Before != Travel.State || OldTarget != Travel.TargetRegionIndex || bArrived))
				UE_LOG(LogAdaptiveEcosystem, Log, TEXT("[Eco Migration] Epoch=%d Step=%lld Time=%.3f Observed=%.3f ID=%lld From=%s Region=%s Target=%s State=%s Arrived=%d NextFeed=%.3f"),
					Time.WorldEpoch, StepId, Time.ServerTimeSeconds, ActualTime, Ids[I].StableAgentId,
					*From.ToString(), *Region.CurrentRegionId.ToString(), *Travel.TargetRegionId.ToString(),
					Travel.State == EEcoResidenceState::Resident ? TEXT("Resident") : Travel.State == EEcoResidenceState::Traveling ? TEXT("Traveling") : TEXT("WaitingForFood"),
					bArrived, Lives[I].NextFeedTimeSeconds);
		}
	});
	return bValid;
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

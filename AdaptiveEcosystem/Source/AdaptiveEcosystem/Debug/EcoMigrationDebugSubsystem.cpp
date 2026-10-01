#include "Debug/EcoMigrationDebugSubsystem.h"
#include "Core/EcoRuntimeSettings.h"
#include "Network/EcoGameState.h"
#include "World/EcologyWorldSubsystem.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "MassSpawnerSubsystem.h"
#include "MassEntityManager.h"
#include "MassEntityQuery.h"
#include "MassExecutionContext.h"
#include "MassCommonFragments.h"
#include "DrawDebugHelpers.h"
#include "Engine/Engine.h"
#include "Engine/World.h"

bool UEcoMigrationDebugSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return !UE_BUILD_SHIPPING && Super::ShouldCreateSubsystem(Outer) && World
		&& World->IsGameWorld() && World->GetNetMode() != NM_DedicatedServer;
}

void UEcoMigrationDebugSubsystem::Tick(float DeltaTime)
{
	if (!GetDefault<UEcoRuntimeSettings>()->bDrawMigrationDebug) return;
	UWorld* World = GetWorld();
	const AEcoGameState* State = World->GetGameState<AEcoGameState>();
	const UEcologyWorldSubsystem* Geography = World->GetSubsystem<UEcologyWorldSubsystem>();
	if (!State || !Geography) return;
	const FEcoCompletedWorldSummary Summary = State->GetEcologySummary();
	if (Summary.StepId == 0) return;
	TArray<FName> RegionOrder;
	for (const auto& Row : Summary.Regions) RegionOrder.Add(Row.RegionId);
	TArray<FEcoRegionSpatialSnapshot> Spaces;
	if (!Geography->BuildSpatialSnapshots(RegionOrder, Spaces)) return;
	const TCHAR* Role = World->GetNetMode() == NM_Client ? TEXT("Client") : TEXT("Authority");
	for (int32 I = 0; I < Summary.Regions.Num(); ++I)
	{
		const auto& Row = Summary.Regions[I];
		const auto& Space = Spaces[I];
		const FColor Color = Row.FoodAmount > 0.0f ? FColor::Green : FColor::Red;
		DrawDebugBox(World, Space.BoundsTransform.GetLocation(), Space.BoundsExtent * Space.BoundsTransform.GetScale3D().GetAbs(),
			Space.BoundsTransform.GetRotation(), Color, false, -1.0f, 0, 3.0f);
		const FString Label = FString::Printf(TEXT("%s Food %.1f/%.1f Pop %d Traveling %d Waiting %d"),
			*Row.RegionId.ToString(), Row.FoodAmount, Row.FoodCapacity, Row.Population, Row.TravelingCount, Row.WaitingCount);
		DrawDebugString(World, Space.ArrivalPosition + FVector(0, 0, 180), Label, nullptr, Color, 0.0f, true);
		if (GEngine)
			GEngine->AddOnScreenDebugMessage(static_cast<uint64>(HashCombine(GetUniqueID(), GetTypeHash(Row.RegionId))),
				0.1f, Color, FString::Printf(TEXT("[Eco %s %s] %s"), Role, *World->GetName(), *Label));
	}
	if (GEngine)
		GEngine->AddOnScreenDebugMessage(static_cast<uint64>(HashCombine(GetUniqueID(), 0xEC033u)), 0.1f, FColor::Cyan,
			FString::Printf(TEXT("[Eco %s %s] Epoch %d Step %lld Rev %d Day %lld %s Remaining %.1fs (completed snapshot)"),
				Role, *World->GetName(), Summary.Time.WorldEpoch, Summary.StepId, Summary.Revision, Summary.Time.DayCycle.CycleId + 1,
				Summary.Time.DayCycle.Phase == EEcoDayPhase::Day ? TEXT("Day") : TEXT("Night"),
				Summary.Time.DayCycle.PhaseEndSeconds - Summary.Time.ServerTimeSeconds));
	// Clients have only relevance-filtered proxies. Full agent diagnostics are authority-only.
	if (World->GetNetMode() == NM_Client) return;
	UMassSpawnerSubsystem* Mass = World->GetSubsystem<UMassSpawnerSubsystem>();
	if (!Mass) return;
	FMassEntityManager& Manager = Mass->GetEntityManagerChecked();
	if (Manager.IsProcessing()) return;
	struct FAgentDraw { FVector Position; FVector Target; int64 Id; FName Region; EEcoResidenceState State; };
	TArray<FAgentDraw> Agents;
	FMassEntityQuery Query(Manager.AsShared());
	Query.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddRequirement<FEcoTravelFragment>(EMassFragmentAccess::ReadOnly);
	Query.AddTagRequirement<FEcoAuthorityTag>(EMassFragmentPresence::All);
	Query.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	FMassExecutionContext Context = Manager.CreateExecutionContext(0.0f);
	Query.ForEachEntityChunk(Context, [&Agents](FMassExecutionContext& Chunk)
	{
		const auto Transforms = Chunk.GetFragmentView<FTransformFragment>();
		const auto Ids = Chunk.GetFragmentView<FEcoIdentityFragment>();
		const auto Regions = Chunk.GetFragmentView<FEcoRegionFragment>();
		const auto Travel = Chunk.GetFragmentView<FEcoTravelFragment>();
		for (int32 I = 0; I < Chunk.GetNumEntities(); ++I)
			Agents.Add({Transforms[I].GetTransform().GetLocation(), Travel[I].TargetPosition,
				Ids[I].StableAgentId, Regions[I].CurrentRegionId, Travel[I].State});
	});
	for (const auto& Agent : Agents)
	{
		const bool bTraveling = Agent.State == EEcoResidenceState::Traveling;
		const FColor Color = bTraveling ? FColor::Cyan : Agent.State == EEcoResidenceState::WaitingForFood ? FColor::Orange : FColor::White;
		DrawDebugString(World, Agent.Position + FVector(0, 0, 80),
			FString::Printf(TEXT("ID %lld %s %s"), Agent.Id, *Agent.Region.ToString(), bTraveling ? TEXT("Traveling") :
				Agent.State == EEcoResidenceState::WaitingForFood ? TEXT("Waiting") : TEXT("Resident")), nullptr, Color, 0.0f, true);
		if (bTraveling) DrawDebugDirectionalArrow(World, Agent.Position, Agent.Target, 60.0f, Color, false, -1.0f, 0, 2.0f);
	}
}

#include "EcoBehaviorProcessors.h"
#include "EcoBehaviorConfig.h"
#include "EcoBehaviorFragments.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Engine/World.h"
#include "ProfilingDebugging/CpuProfilerTrace.h"
#include "EcoNeighborhoodSubsystem.h"
#include "EcoWorldProviders.h"

UEcoNeighborhoodGatherProcessor::UEcoNeighborhoodGatherProcessor()
	: HerbivoreQuery(*this)
	, PredatorQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	// 공유 색인을 쓰므로 게임 스레드에서만 돈다.
	bRequiresGameThreadExecution = true;
}

void UEcoNeighborhoodGatherProcessor::ConfigureQueries(
	const TSharedRef<FMassEntityManager>& EntityManager)
{
	HerbivoreQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	HerbivoreQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	HerbivoreQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	HerbivoreQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	HerbivoreQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	HerbivoreQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
	HerbivoreQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);

	PredatorQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	PredatorQuery.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::All);
	PredatorQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	PredatorQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
	PredatorQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
}

void UEcoNeighborhoodGatherProcessor::Execute(FMassEntityManager& EntityManager,
											  FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	UEcoNeighborhoodSubsystem* Grid = World->GetSubsystem<UEcoNeighborhoodSubsystem>();
	if (!Grid)
	{
		return;
	}
	const UEcoWorldProviderRegistry* Registry = World->GetSubsystem<UEcoWorldProviderRegistry>();
	const IEcoWorldCoverProvider* Cover = Registry ? Registry->GetCoverProvider() : nullptr;

	// 셀 크기를 시야 반경으로 잡는다 — 조회 때 3x3 이면 충분해진다.
	Grid->BeginFrame(EcoBehaviorConfig::SeeRadiusCm);

	auto GatherInto = [Grid, Cover](FMassExecutionContext& Ctx, bool bPredator)
	{
		const auto Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		const auto Ids = Ctx.GetFragmentView<FEcoIdentityFragment>();
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FMassVelocityFragment> Velocities =
			Ctx.GetFragmentView<FMassVelocityFragment>();

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (!Vitals.IsEmpty() && Vitals[i].HP <= 0) continue;
			const FVector Location = Transforms[i].GetTransform().GetLocation();
			FEcoNeighborEntry Entry;
			Entry.Entity = Ctx.GetEntity(i);
			Entry.Location = Location;
			Entry.bPredator = bPredator;
			Entry.SpeciesId = Ids.IsEmpty() ? NAME_None : Ids[i].SpeciesId;
			Entry.StableAgentId = Ids.IsEmpty() ? 0 : Ids[i].StableAgentId;
			Entry.bInCover = Cover ? Cover->IsInCover(Location) : false;

			// 진행 방향. 정지 상태면 전방 축으로 둔다 (시야 판정이 무너지지 않게).
			const FVector V = Velocities[i].Value;
			Entry.Heading = V.SizeSquared2D() > KINDA_SMALL_NUMBER
								? FVector(V.X, V.Y, 0.0f).GetSafeNormal()
								: Transforms[i].GetTransform().GetRotation().GetForwardVector();
			Grid->Add(Entry);
		}
	};

	HerbivoreQuery.ForEachEntityChunk(Context,
		[&GatherInto](FMassExecutionContext& Ctx) { GatherInto(Ctx, false); });
	PredatorQuery.ForEachEntityChunk(Context,
		[&GatherInto](FMassExecutionContext& Ctx) { GatherInto(Ctx, true); });

	Grid->Build();
}

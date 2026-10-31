#include "EcoPolicyV3Processors.h"

#include "EcoPolicyV3Fragments.h"
#include "EcoPolicyV3Subsystem.h"
#include "Engine/World.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"

// -----------------------------------------------------------------------------
// UEcoPolicyV3StepProcessor
// -----------------------------------------------------------------------------

UEcoPolicyV3StepProcessor::UEcoPolicyV3StepProcessor()
	: HerbivoreQuery(*this)
	, ThreatQuery(*this)
{
	// 논리 상태는 서버·단독에만 있다 (AGENTS.md 2절 2항)
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	// 세계 상태(서브시스템)를 함께 쓰고 전역 스텝을 한 번에 돌린다
	bRequiresGameThreadExecution = true;
}

void UEcoPolicyV3StepProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	HerbivoreQuery.AddRequirement<FEcoBehaviorStateFragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddRequirement<FEcoPerceptionCacheFragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddRequirement<FEcoControlOutFragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddTagRequirement<FEcoPolicyV3Tag>(EMassFragmentPresence::All);

	ThreatQuery.AddRequirement<FEcoThreatStateFragment>(EMassFragmentAccess::ReadWrite);
	ThreatQuery.AddTagRequirement<FEcoThreatV3Tag>(EMassFragmentPresence::All);
}

void UEcoPolicyV3StepProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	UEcoPolicyV3Subsystem* Sub = World ? World->GetSubsystem<UEcoPolicyV3Subsystem>() : nullptr;
	if (!Sub || !Sub->IsSessionActive())
	{
		return;
	}
	// 결정 시계: 프레임 dt → 논리 틱 → 결정 스텝 (v1 과 같은 시간 기준, FPS 와 무관)
	const int32 Steps = Sub->AdvanceClock(Context.GetDeltaTimeSeconds());
	if (Steps <= 0)
	{
		return;
	}

	EcoWorldV3::FWorldState& Sim = Sub->GetSim();
	const int32 N = Sim.Config.NumHerbivores;
	const int32 M = Sim.Config.NumThreats();

	// --- 슬롯 순서로 모은다. 청크 순서는 아키타입·생성 순서에 따라 바뀌므로 쓰지 않는다 ---
	HerbViews.Reset();
	HerbViews.SetNum(N);
	HerbStates.Reset();
	HerbStates.SetNumZeroed(N);
	ThreatViews.Reset();
	ThreatViews.SetNumZeroed(M);
	int32 Found = 0;
	int32 Bad = 0;
	HerbivoreQuery.ForEachEntityChunk(Context, [this, N, &Found, &Bad](FMassExecutionContext& Ctx)
	{
		const TArrayView<FEcoBehaviorStateFragment> States = Ctx.GetMutableFragmentView<FEcoBehaviorStateFragment>();
		const TArrayView<FEcoPerceptionCacheFragment> Percs = Ctx.GetMutableFragmentView<FEcoPerceptionCacheFragment>();
		const TArrayView<FEcoControlOutFragment> Ctrls = Ctx.GetMutableFragmentView<FEcoControlOutFragment>();
		const TArrayView<FEcoHerbivoreBodyV3Fragment> Bodies = Ctx.GetMutableFragmentView<FEcoHerbivoreBodyV3Fragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const int32 Slot = static_cast<int32>(Bodies[i].Body.Slot);
			if (Slot < 0 || Slot >= N || HerbStates[Slot] != nullptr)
			{
				++Bad;
				continue;
			}
			EcoWorldV3::FHerbView& V = HerbViews[Slot];
			V.Rep = &States[i].Rep;
			V.Decision = &States[i].Decision;
			V.Perception = &Percs[i].Perception;
			V.Control = &Ctrls[i].Control;
			V.Body = &Bodies[i].Body;
			HerbStates[Slot] = &States[i];
			++Found;
		}
	});
	int32 FoundThreats = 0;
	ThreatQuery.ForEachEntityChunk(Context, [this, M, &FoundThreats, &Bad](FMassExecutionContext& Ctx)
	{
		const TArrayView<FEcoThreatStateFragment> Agents = Ctx.GetMutableFragmentView<FEcoThreatStateFragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const int32 Slot = static_cast<int32>(Agents[i].Agent.Slot);
			if (Slot < 0 || Slot >= M || ThreatViews[Slot] != nullptr)
			{
				++Bad;
				continue;
			}
			ThreatViews[Slot] = &Agents[i].Agent;
			++FoundThreats;
		}
	});
	if (Found != N || FoundThreats != M || Bad > 0)
	{
		// 개체가 지워졌거나 다른 v3 개체군이 섞였다. 세계 스텝은 모든 슬롯이 있어야 뜻이 있다 — 돌지 않는다
		if (!bReportedBadSlots)
		{
			UE_LOG(LogEcoPolicyV3, Error, TEXT("[EcoV3] 슬롯이 맞지 않아 스텝을 멈춘다: 사슴 %d/%d, 위협 %d/%d, 겹치거나 범위 밖 %d"),
				   Found, N, FoundThreats, M, Bad);
			bReportedBadSlots = true;
		}
		return;
	}
	bReportedBadSlots = false;

	// --- 결정 스텝 (큰 프레임이면 여러 번, 최대 64) ---
	for (int32 s = 0; s < Steps; ++s)
	{
		const EcoWorldV3::FStepReport Report = EcoWorldV3::Step(Sim, HerbViews.GetData(), N, ThreatViews.GetData(), M);
		Sub->NotifyStepCompleted(Report);
	}
	for (int32 i = 0; i < N; ++i)
	{
		HerbStates[i]->SyncSummary(*HerbViews[i].Control);
	}
}

// -----------------------------------------------------------------------------
// UEcoPolicyV3VisualProcessor
// -----------------------------------------------------------------------------

UEcoPolicyV3VisualProcessor::UEcoPolicyV3VisualProcessor()
	: HerbivoreQuery(*this)
	, ThreatQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPolicyV3StepProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPolicyV3VisualProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	HerbivoreQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadOnly);
	HerbivoreQuery.AddTagRequirement<FEcoPolicyV3Tag>(EMassFragmentPresence::All);

	ThreatQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	ThreatQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	ThreatQuery.AddRequirement<FEcoThreatStateFragment>(EMassFragmentAccess::ReadOnly);
	ThreatQuery.AddTagRequirement<FEcoThreatV3Tag>(EMassFragmentPresence::All);
}

void UEcoPolicyV3VisualProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	const UEcoPolicyV3Subsystem* Sub = World ? World->GetSubsystem<UEcoPolicyV3Subsystem>() : nullptr;
	if (!Sub || !Sub->IsSessionActive())
	{
		return;
	}
	const float Alpha = Sub->GetVisualAlpha();

	HerbivoreQuery.ForEachEntityChunk(Context, [Sub, Alpha](FMassExecutionContext& Ctx)
	{
		const TArrayView<FTransformFragment> Transforms = Ctx.GetMutableFragmentView<FTransformFragment>();
		const TArrayView<FMassVelocityFragment> Velocities = Ctx.GetMutableFragmentView<FMassVelocityFragment>();
		const TConstArrayView<FEcoHerbivoreBodyV3Fragment> Bodies = Ctx.GetFragmentView<FEcoHerbivoreBodyV3Fragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			Sub->ComputeHerbVisual(Bodies[i].Body, Alpha, Transforms[i].GetMutableTransform(), Velocities[i].Value);
		}
	});
	ThreatQuery.ForEachEntityChunk(Context, [Sub, Alpha](FMassExecutionContext& Ctx)
	{
		const TArrayView<FTransformFragment> Transforms = Ctx.GetMutableFragmentView<FTransformFragment>();
		const TArrayView<FMassVelocityFragment> Velocities = Ctx.GetMutableFragmentView<FMassVelocityFragment>();
		const TConstArrayView<FEcoThreatStateFragment> Agents = Ctx.GetFragmentView<FEcoThreatStateFragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			Sub->ComputeThreatVisual(Agents[i].Agent, Alpha, Transforms[i].GetMutableTransform(), Velocities[i].Value);
		}
	});
}

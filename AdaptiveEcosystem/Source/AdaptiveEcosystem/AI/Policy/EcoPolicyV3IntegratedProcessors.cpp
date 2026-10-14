#include "EcoPolicyV3IntegratedProcessors.h"

#include "AI/Policy/EcoBehaviorFragments.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "DrawDebugHelpers.h"
#include "EcoHeading.h"
#include "EcoPolicyV3Fragments.h"
#include "EcoPolicyV3IntegratedFragments.h"
#include "EcoPolicyV3IntegratedSubsystem.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"

namespace EcoPolicyV3IntegratedProcImpl
{
	struct FMoveAdapter
	{
		const UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
		FName RegionId;
		FEcoV3RegionContext* Ctx = nullptr;
		const TArray<FEcoIntegratedV3Fragment*>* HerbInts = nullptr;
		const TArray<FEcoIntegratedV3Fragment*>* WolfInts = nullptr;
	};

	/** 이번 Step 배열의 색인 = HerbInts/WolfInts 색인 (BuildViews 가 같은 순서로 채운다). 통과하면 그 개체의 지면 높이를 갱신한다. */
	bool MoveOne(const FMoveAdapter& A, FEcoIntegratedV3Fragment& F, double FromX, double FromY, double ToX, double ToY)
	{
		++A.Ctx->TerrainChecks;
		double Z = F.GroundZ;
		const bool bOk = A.Sub->TraceMove(A.RegionId, A.Ctx->UnitsToCm(FromX, FromY, F.GroundZ), A.Ctx->UnitsToCm(ToX, ToY, F.GroundZ), Z);
		if (bOk)
		{
			F.GroundZ = Z;
		}
		else
		{
			++F.BlockedMoves;
		}
		return bOk;
	}

	bool HerbMoveHook(void* User, int32 Index, const EcoWorldV3::FVec2& From, const EcoWorldV3::FVec2& To)
	{
		const FMoveAdapter& A = *static_cast<const FMoveAdapter*>(User);
		if (!A.HerbInts || !A.HerbInts->IsValidIndex(Index))
		{
			return true;
		}
		return MoveOne(A, *(*A.HerbInts)[Index], From.X, From.Y, To.X, To.Y);
	}

	bool ThreatMoveHook(void* User, int32 Index, double FromX, double FromY, double ToX, double ToY)
	{
		const FMoveAdapter& A = *static_cast<const FMoveAdapter*>(User);
		if (!A.WolfInts || !A.WolfInts->IsValidIndex(Index))
		{
			return true;
		}
		return MoveOne(A, *(*A.WolfInts)[Index], FromX, FromY, ToX, ToY);
	}

	float EnergyMirror(const EcoWorldV3::FHerbBody& B, const FEcoVitalsFragment& V)
	{
		// v3 에너지 E (0~1) × MaxEnergy — 조정자 요약(AverageEnergy)·표현 Energy 가 같은 척도로 읽는다
		return static_cast<float>(FMath::Clamp(B.Energy, 0.0, 1.0)) * V.MaxEnergy;
	}
}

// -----------------------------------------------------------------------------
// UEcoPolicyV3IntegratedStepProcessor
// -----------------------------------------------------------------------------

UEcoPolicyV3IntegratedStepProcessor::UEcoPolicyV3IntegratedStepProcessor()
	: DeerQuery(*this)
	, WolfQuery(*this)
{
	// 논리 상태는 서버·단독에만 있다 (AGENTS.md 2절 2항)
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	// 지역 세계(서브시스템)를 함께 쓰고, 지형 제약에서 물리 질의를 부른다
	bRequiresGameThreadExecution = true;
}

void UEcoPolicyV3IntegratedStepProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	DeerQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoCreatureLifecycleFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoBehaviorStateFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoPerceptionCacheFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoControlOutFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::All);
	DeerQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	DeerQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);

	WolfQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FEcoRegionFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FEcoCreatureLifecycleFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FEcoThreatStateFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FEcoPredatorStateFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddTagRequirement<FEcoIntegratedThreatV3Tag>(EMassFragmentPresence::All);
	WolfQuery.AddTagRequirement<FEcoAliveTag>(EMassFragmentPresence::All);
	WolfQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
}

void UEcoPolicyV3IntegratedStepProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	using namespace EcoPolicyV3IntegratedProcImpl;
	UWorld* World = GetWorld();
	UEcoPolicyV3IntegratedSubsystem* Sub = World ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
	if (!Sub || !Sub->IsActive())
	{
		return;   // 스위치 끔 (기본): 아무것도 하지 않는다
	}
	// 전역 결정 시계 (평면 시험 경로의 시계와 따로). 컨텍스트가 생기기 전 스텝은 버린다
	const int32 Steps = Sub->AdvanceClock(Context.GetDeltaTimeSeconds());
	const int32 NumCtx = Sub->NumContexts();
	if (NumCtx == 0)
	{
		return;
	}

	// --- 1. 모으기 (청크 순서는 아키타입·생성 순서에 따라 바뀌므로 StableAgentId 로 정렬한다) ---
	Deer.Reset();
	Wolves.Reset();
	DeerQuery.ForEachEntityChunk(Context, [this](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FEcoIdentityFragment> Ids = Ctx.GetFragmentView<FEcoIdentityFragment>();
		const TConstArrayView<FEcoRegionFragment> Regions = Ctx.GetFragmentView<FEcoRegionFragment>();
		const TConstArrayView<FTransformFragment> Xfs = Ctx.GetFragmentView<FTransformFragment>();
		const TArrayView<FEcoVitalsFragment> Vits = Ctx.GetMutableFragmentView<FEcoVitalsFragment>();
		const TArrayView<FEcoCreatureLifecycleFragment> Lives = Ctx.GetMutableFragmentView<FEcoCreatureLifecycleFragment>();
		const TArrayView<FEcoBehaviorStateFragment> States = Ctx.GetMutableFragmentView<FEcoBehaviorStateFragment>();
		const TArrayView<FEcoPerceptionCacheFragment> Percs = Ctx.GetMutableFragmentView<FEcoPerceptionCacheFragment>();
		const TArrayView<FEcoControlOutFragment> Ctrls = Ctx.GetMutableFragmentView<FEcoControlOutFragment>();
		const TArrayView<FEcoHerbivoreBodyV3Fragment> Bodies = Ctx.GetMutableFragmentView<FEcoHerbivoreBodyV3Fragment>();
		const TArrayView<FEcoIntegratedV3Fragment> Ints = Ctx.GetMutableFragmentView<FEcoIntegratedV3Fragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (Ids[i].StableAgentId <= 0 || Vits[i].HP <= 0.0f || Ints[i].bDead)
			{
				continue;   // 아직 정체성이 없거나, 이미 죽었다 (조정자가 Alive 를 떼고 지운다)
			}
			FEcoV3DeerRec& R = Deer.AddDefaulted_GetRef();
			R.Id = Ids[i].StableAgentId;
			R.Region = Regions[i].CurrentRegionId;
			R.Transform = &Xfs[i];
			R.Vitals = &Vits[i];
			R.Life = &Lives[i];
			R.State = &States[i];
			R.Int = &Ints[i];
			R.View.Rep = &States[i].Rep;
			R.View.Decision = &States[i].Decision;
			R.View.Body = &Bodies[i].Body;
			R.View.Perception = &Percs[i].Perception;
			R.View.Control = &Ctrls[i].Control;
		}
	});
	WolfQuery.ForEachEntityChunk(Context, [this](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FEcoIdentityFragment> Ids = Ctx.GetFragmentView<FEcoIdentityFragment>();
		const TConstArrayView<FEcoRegionFragment> Regions = Ctx.GetFragmentView<FEcoRegionFragment>();
		const TConstArrayView<FTransformFragment> Xfs = Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FEcoVitalsFragment> Vits = Ctx.GetFragmentView<FEcoVitalsFragment>();
		const TArrayView<FEcoCreatureLifecycleFragment> Lives = Ctx.GetMutableFragmentView<FEcoCreatureLifecycleFragment>();
		const TArrayView<FEcoThreatStateFragment> Agents = Ctx.GetMutableFragmentView<FEcoThreatStateFragment>();
		const TArrayView<FEcoIntegratedV3Fragment> Ints = Ctx.GetMutableFragmentView<FEcoIntegratedV3Fragment>();
		const TArrayView<FEcoPredatorStateFragment> Preds = Ctx.GetMutableFragmentView<FEcoPredatorStateFragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (Ids[i].StableAgentId <= 0 || Vits[i].HP <= 0.0f)
			{
				continue;
			}
			FEcoV3WolfRec& R = Wolves.AddDefaulted_GetRef();
			R.Id = Ids[i].StableAgentId;
			R.Region = Regions[i].CurrentRegionId;
			R.Transform = &Xfs[i];
			R.Life = &Lives[i];
			R.Agent = &Agents[i].Agent;
			R.Int = &Ints[i];
			R.PredState = &Preds[i];
		}
	});
	Deer.Sort([](const FEcoV3DeerRec& A, const FEcoV3DeerRec& B) { return A.Id < B.Id; });
	Wolves.Sort([](const FEcoV3WolfRec& A, const FEcoV3WolfRec& B) { return A.Id < B.Id; });

	// --- 2. 지역별 목록 ---
	DeerByContext.SetNum(NumCtx);
	WolvesByContext.SetNum(NumCtx);
	for (int32 c = 0; c < NumCtx; ++c)
	{
		DeerByContext[c].Reset();
		WolvesByContext[c].Reset();
	}
	auto ContextOf = [this, Sub](const FEcoIntegratedV3Fragment& Int, FName Region) -> FEcoV3RegionContext*
	{
		FEcoV3RegionContext* Ctx = Int.bAdopted ? Sub->GetContext(Int.ContextIndex) : Sub->FindContext(Region);
		if (!Ctx && !ReportedMissingRegions.Contains(Region))
		{
			ReportedMissingRegions.Add(Region);
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 지역 %s 의 v3 무대가 없다 — 그 지역 개체는 서 있는다"), *Region.ToString());
		}
		return Ctx;
	};
	for (int32 k = 0; k < Deer.Num(); ++k)
	{
		if (FEcoV3RegionContext* Ctx = ContextOf(*Deer[k].Int, Deer[k].Region))
		{
			DeerByContext[Ctx->Index].Add(k);
		}
	}
	for (int32 k = 0; k < Wolves.Num(); ++k)
	{
		if (FEcoV3RegionContext* Ctx = ContextOf(*Wolves[k].Int, Wolves[k].Region))
		{
			WolvesByContext[Ctx->Index].Add(k);
		}
	}

	auto BuildViews = [this](int32 c)
	{
		Views.Reset();
		HerbInts.Reset();
		ThreatPtrs.Reset();
		WolfInts.Reset();
		for (const int32 k : DeerByContext[c])
		{
			Views.Add(Deer[k].View);
			HerbInts.Add(Deer[k].Int);
		}
		for (const int32 k : WolvesByContext[c])
		{
			ThreatPtrs.Add(Wolves[k].Agent);
			WolfInts.Add(Wolves[k].Int);
		}
	};

	// --- 3. 입양 (조정자가 막 만든 개체). 늑대 먼저 — 새 사슴의 첫 관측이 늑대를 보게 ---
	for (int32 c = 0; c < NumCtx; ++c)
	{
		FEcoV3RegionContext& Ctx = *Sub->GetContext(c);
		for (const int32 k : WolvesByContext[c])
		{
			FEcoV3WolfRec& W = Wolves[k];
			if (W.Int->bAdopted)
			{
				continue;
			}
			const FTransform& Xf = W.Transform->GetTransform();
			const FVector Loc = Xf.GetLocation();
			const FVector Fwd = Xf.GetRotation().GetForwardVector();
			const EcoWorldV3::FVec2 P = Ctx.CmToUnits(Loc);
			const EcoThreatV3::FThreatSpec Spec = EcoV3Integrated::WolfSpecForOrdinal(Ctx.AdoptedWolves++, Ctx.Sim.Config.PredSpeedMult);
			EcoWorldV3::AdoptThreat(Ctx.Sim, *W.Agent, Spec, P.X, P.Y, Fwd.X, Fwd.Y);
			W.Int->bAdopted = true;
			W.Int->ContextIndex = Ctx.Index;
			W.Int->GroundZ = Loc.Z;
			W.Int->PrevGroundZ = Loc.Z;
		}
		NewRows.Reset();
		const TArray<int32>& List = DeerByContext[c];
		for (int32 r = 0; r < List.Num(); ++r)
		{
			FEcoV3DeerRec& D = Deer[List[r]];
			if (D.Int->bAdopted)
			{
				continue;
			}
			const FTransform& Xf = D.Transform->GetTransform();
			const FVector Loc = Xf.GetLocation();
			const FVector Fwd = Xf.GetRotation().GetForwardVector();
			EcoWorldV3::AdoptHerb(Ctx.Sim, D.View, Ctx.CmToUnits(Loc), {Fwd.X, Fwd.Y}, EcoRepertoireV3::MakeAgentKeyFromStableId(D.Id));
			D.Int->bAdopted = true;
			D.Int->ContextIndex = Ctx.Index;
			D.Int->GroundZ = Loc.Z;
			D.Int->PrevGroundZ = Loc.Z;
			D.Vitals->Energy = EnergyMirror(*D.View.Body, *D.Vitals);
			++Ctx.AdoptedDeer;
			NewRows.Add(r);
		}
		if (!NewRows.IsEmpty())
		{
			BuildViews(c);
			EcoWorldV3::ObserveAndDecideRows(Ctx.Sim, Views.GetData(), Views.Num(), ThreatPtrs.GetData(), ThreatPtrs.Num(),
											 NewRows.GetData(), NewRows.Num());
			for (const int32 r : NewRows)
			{
				const FEcoV3DeerRec& D = Deer[List[r]];
				D.State->SyncSummary(*D.View.Control);
			}
		}
	}

	// --- 4. 결정 스텝: 모든 지역이 같은 전역 스텝 (계약 10-1) ---
	const double Now = World->GetTimeSeconds();
	const double CpuStart = FPlatformTime::Seconds();
	for (int32 s = 0; s < Steps; ++s)
	{
		for (int32 c = 0; c < NumCtx; ++c)
		{
			FEcoV3RegionContext& Ctx = *Sub->GetContext(c);
			Sub->SyncContextClock(Ctx);
			BuildViews(c);
			for (FEcoIntegratedV3Fragment* Int : HerbInts)
			{
				Int->PrevGroundZ = Int->GroundZ;
			}
			for (FEcoIntegratedV3Fragment* Int : WolfInts)
			{
				Int->PrevGroundZ = Int->GroundZ;
			}
			FMoveAdapter Adapter;
			Adapter.Sub = Sub;
			Adapter.RegionId = Ctx.RegionId;
			Adapter.Ctx = &Ctx;
			Adapter.HerbInts = &HerbInts;
			Adapter.WolfInts = &WolfInts;
			EcoWorldV3::FStepHooks Hooks;
			Hooks.User = &Adapter;
			Hooks.HerbMove = &HerbMoveHook;
			Hooks.ThreatMove = &ThreatMoveHook;
			const EcoWorldV3::FStepReport Report = EcoWorldV3::Step(Ctx.Sim, Views.GetData(), Views.Num(), ThreatPtrs.GetData(),
																	ThreatPtrs.Num(), EcoPolicyV3::kBuiltinNet,
																	Sub->UsesTerrain() ? &Hooks : nullptr);

			// 죽음 넘기기: HP 0 (+ 잡힘이면 bPredated). 사망 처리·지역 피식 사건·2 초 뒤 삭제는 팀 조정자가 한다.
			// 목록에서 빼서 이 프레임의 다음 스텝부터는 움직이거나 먹거나 잡히거나 동족으로 세어지지 않게 한다
			TArray<int32>& List = DeerByContext[c];
			for (int32 r = List.Num() - 1; r >= 0; --r)
			{
				FEcoV3DeerRec& D = Deer[List[r]];
				const EcoWorldV3::FHerbBody& B = *D.View.Body;
				if (B.DeathCause == EcoWorldV3::kDeathNone)
				{
					continue;
				}
				D.Int->bDead = true;
				D.Int->DeathCause = static_cast<uint8>(B.DeathCause);
				D.Int->PrevGroundZ = D.Int->GroundZ;   // 시체는 죽은 자리에 멈춘다
				D.Vitals->HP = 0.0f;
				D.Vitals->Energy = EnergyMirror(B, *D.Vitals);
				D.Life->bPredated = B.DeathCause == EcoWorldV3::kDeathCaught;
				D.State->SyncSummary(*D.View.Control);
				if (B.DeathCause == EcoWorldV3::kDeathCaught)
				{
					Ctx.RecentCatches.Add({Ctx.UnitsToCm(B.DeathPos.X, B.DeathPos.Y, D.Int->GroundZ), Now});
				}
				List.RemoveAt(r);
			}
			// 늑대 표현 자리표시: 포획 뒤 쿨다운 → '먹는 중', 표적을 쫓으면 '추격 중' (팀 표현 깃발)
			for (const int32 k : WolvesByContext[c])
			{
				const EcoWorldV3::FThreatAgent& A = *Wolves[k].Agent;
				Wolves[k].PredState->EatCooldown = static_cast<float>(A.State.Cooldown * EcoRepertoireV3::kStepSeconds);
				Wolves[k].Life->bPursuing = A.Last.bHunting && A.Last.bHasTarget;
			}
			Sub->NotifyContextStep(Ctx, Report);
		}
		Sub->FinishGlobalStep();
	}
	if (Steps > 0)
	{
		Sub->AddStepCpuSeconds(FPlatformTime::Seconds() - CpuStart, Steps);
	}

	// --- 5. 에너지 거울, 요약 칸, 지역 집계 ---
	for (int32 c = 0; c < NumCtx; ++c)
	{
		FEcoV3RegionContext& Ctx = *Sub->GetContext(c);
		FMemory::Memzero(Ctx.BehaviorNow, sizeof(Ctx.BehaviorNow));
		FMemory::Memzero(Ctx.WolvesNow, sizeof(Ctx.WolvesNow));
		for (const int32 k : DeerByContext[c])
		{
			FEcoV3DeerRec& D = Deer[k];
			D.Vitals->Energy = EnergyMirror(*D.View.Body, *D.Vitals);
			D.State->SyncSummary(*D.View.Control);
			const int32 B = D.View.Rep->Behavior;
			if (B >= 0 && B < EcoRepertoireV3::kNumBehaviors)
			{
				++Ctx.BehaviorNow[B];
			}
		}
		for (const int32 k : WolvesByContext[c])
		{
			++Ctx.WolvesNow[static_cast<int32>(EcoV3Integrated::WolfStateOf(*Wolves[k].Agent))];
		}
		Ctx.AliveDeer = DeerByContext[c].Num();
		Ctx.Wolves = WolvesByContext[c].Num();
	}
}

// -----------------------------------------------------------------------------
// UEcoPolicyV3IntegratedVisualProcessor
// -----------------------------------------------------------------------------

UEcoPolicyV3IntegratedVisualProcessor::UEcoPolicyV3IntegratedVisualProcessor()
	: DeerQuery(*this)
	, WolfQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPolicyV3IntegratedStepProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPolicyV3IntegratedVisualProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	// Alive 를 요구하지 않는다 — 죽은 개체도 조정자가 지울 때까지 죽은 자리에 멈춰 있어야 한다
	DeerQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	DeerQuery.AddRequirement<FEcoHerbivoreBodyV3Fragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FEcoBehaviorStateFragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadOnly);
	DeerQuery.AddTagRequirement<FEcoIntegratedPolicyV3Tag>(EMassFragmentPresence::All);
	DeerQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);

	WolfQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FMassVelocityFragment>(EMassFragmentAccess::ReadWrite);
	WolfQuery.AddRequirement<FEcoThreatStateFragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddRequirement<FEcoIntegratedV3Fragment>(EMassFragmentAccess::ReadOnly);
	WolfQuery.AddTagRequirement<FEcoIntegratedThreatV3Tag>(EMassFragmentPresence::All);
	WolfQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
}

void UEcoPolicyV3IntegratedVisualProcessor::Execute(FMassEntityManager& EntityManager, FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	UEcoPolicyV3IntegratedSubsystem* Sub = World ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
	if (!Sub || !Sub->IsActive() || Sub->NumContexts() == 0)
	{
		return;
	}
	const double Alpha = FMath::Clamp(static_cast<double>(Sub->GetVisualAlpha()), 0.0, 1.0);
	const bool bDebug = UEcoPolicyV3IntegratedSubsystem::IsDebugDrawEnabled();
	const double K = EcoRepertoireV3::kUnitCm / EcoRepertoireV3::kStepSeconds;   // 단위/스텝 → cm/s

	DeerQuery.ForEachEntityChunk(Context, [Sub, Alpha, bDebug, K, World](FMassExecutionContext& Ctx)
	{
		const TArrayView<FTransformFragment> Xfs = Ctx.GetMutableFragmentView<FTransformFragment>();
		const TArrayView<FMassVelocityFragment> Vels = Ctx.GetMutableFragmentView<FMassVelocityFragment>();
		const TConstArrayView<FEcoHerbivoreBodyV3Fragment> Bodies = Ctx.GetFragmentView<FEcoHerbivoreBodyV3Fragment>();
		const TConstArrayView<FEcoBehaviorStateFragment> States = Ctx.GetFragmentView<FEcoBehaviorStateFragment>();
		const TConstArrayView<FEcoIntegratedV3Fragment> Ints = Ctx.GetFragmentView<FEcoIntegratedV3Fragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const FEcoIntegratedV3Fragment& Int = Ints[i];
			const FEcoV3RegionContext* Rc = Int.bAdopted ? Sub->GetContext(Int.ContextIndex) : nullptr;
			if (!Rc)
			{
				continue;   // 아직 입양 전 — 조정자가 놓은 자리 그대로
			}
			const EcoWorldV3::FHerbBody& B = Bodies[i].Body;
			const double A = Int.bDead ? 1.0 : Alpha;
			const FVector Loc = Rc->UnitsToCm(B.PrevPos.X + (B.Pos.X - B.PrevPos.X) * A, B.PrevPos.Y + (B.Pos.Y - B.PrevPos.Y) * A,
											  Int.PrevGroundZ + (Int.GroundZ - Int.PrevGroundZ) * A);
			FTransform& Xf = Xfs[i].GetMutableTransform();
			Xf.SetLocation(Loc);
			if (B.Head.X != 0.0 || B.Head.Y != 0.0)
			{
				Xf.SetRotation(EcoHeading::YawQuatFromDir(FVector(B.Head.X, B.Head.Y, 0.0)));
			}
			Vels[i].Value = Int.bDead ? FVector::ZeroVector : FVector((B.Pos.X - B.PrevPos.X) * K, (B.Pos.Y - B.PrevPos.Y) * K, 0.0);
			if (bDebug)
			{
				const EcoRepertoireV3::FRepState& Rep = States[i].Rep;
				FString Label;
				FColor Color;
				if (Int.bDead)
				{
					Label = Int.DeathCause == EcoWorldV3::kDeathCaught ? TEXT("잡힘") : TEXT("굶음");
					Color = FColor(120, 120, 120);
				}
				else
				{
					Label = EcoV3Integrated::BehaviorNameKo(Rep.Behavior);
					if (Rep.Behavior == EcoRepertoireV3::kHide && Rep.bArrived)
					{
						Label += TEXT("(웅크림)");
					}
					Color = Rep.Behavior == EcoRepertoireV3::kGraze	 ? FColor(70, 200, 70)
							: Rep.Behavior == EcoRepertoireV3::kFlee ? FColor(255, 215, 0)
							: Rep.Behavior == EcoRepertoireV3::kHide ? FColor(60, 150, 255)
							: Rep.Behavior == EcoRepertoireV3::kFreeze ? FColor(245, 245, 245)
																	   : FColor(170, 70, 210);
				}
				DrawDebugString(World, Loc + FVector(0.0, 0.0, 230.0), Label, nullptr, Color, 0.0f, true, 1.1f);
			}
		}
	});

	WolfQuery.ForEachEntityChunk(Context, [Sub, Alpha, bDebug, K, World](FMassExecutionContext& Ctx)
	{
		const TArrayView<FTransformFragment> Xfs = Ctx.GetMutableFragmentView<FTransformFragment>();
		const TArrayView<FMassVelocityFragment> Vels = Ctx.GetMutableFragmentView<FMassVelocityFragment>();
		const TConstArrayView<FEcoThreatStateFragment> Agents = Ctx.GetFragmentView<FEcoThreatStateFragment>();
		const TConstArrayView<FEcoIntegratedV3Fragment> Ints = Ctx.GetFragmentView<FEcoIntegratedV3Fragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			const FEcoIntegratedV3Fragment& Int = Ints[i];
			const FEcoV3RegionContext* Rc = Int.bAdopted ? Sub->GetContext(Int.ContextIndex) : nullptr;
			if (!Rc)
			{
				continue;
			}
			const EcoWorldV3::FThreatAgent& Ag = Agents[i].Agent;
			const EcoThreatV3::FThreatState& S = Ag.State;
			const FVector Loc = Rc->UnitsToCm(Ag.PrevX + (S.PosX - Ag.PrevX) * Alpha, Ag.PrevY + (S.PosY - Ag.PrevY) * Alpha,
											  Int.PrevGroundZ + (Int.GroundZ - Int.PrevGroundZ) * Alpha);
			FTransform& Xf = Xfs[i].GetMutableTransform();
			Xf.SetLocation(Loc);
			if (S.HeadX != 0.0 || S.HeadY != 0.0)
			{
				Xf.SetRotation(EcoHeading::YawQuatFromDir(FVector(S.HeadX, S.HeadY, 0.0)));
			}
			Vels[i].Value = FVector((S.PosX - Ag.PrevX) * K, (S.PosY - Ag.PrevY) * K, 0.0);
			if (bDebug)
			{
				using EcoV3Integrated::EWolfState;
				const EWolfState St = EcoV3Integrated::WolfStateOf(Ag);
				const FColor Color = St == EWolfState::Pounce   ? FColor(255, 120, 0)
									 : St == EWolfState::Sleep	 ? FColor(60, 60, 160)
									 : St == EWolfState::Stalk || St == EWolfState::Chase ? FColor::Red
									 : St == EWolfState::Roam	 ? FColor(220, 150, 150)
																 : FColor(150, 150, 150);
				const FString Label = FString::Printf(TEXT("늑대 %s%s"), EcoV3Integrated::WolfStateNameKo(St),
													  Ag.Spec.Type == EcoThreatV3::EThreatType::Stalker ? TEXT(" (잠행형)") : TEXT(" (추격형)"));
				DrawDebugString(World, Loc + FVector(0.0, 0.0, 260.0), Label, nullptr, Color, 0.0f, true, 1.2f);
			}
		}
	});
}

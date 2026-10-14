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
#include "EcoRegionPredationSubsystem.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "AI/Social/Senses/EcoPredatorPerception.h"
#include "MassEntityManager.h"
#include "AI/Behavior/EcoSpeciesAIFragments.h"

UEcoPredationProcessor::UEcoPredationProcessor()
	: HerbivoreQuery(*this)
	, PredatorQuery(*this)
{
	ExecutionFlags = static_cast<int32>(EProcessorExecutionFlags::Server
									  | EProcessorExecutionFlags::Standalone);
	ProcessingPhase = EMassProcessingPhase::PrePhysics;
	// 필요한 건 이번 틱 이웃 색인(게더)뿐이다. 지각 뒤에 두는 건 기존 실행 순서를 유지하려고.
	ExecutionOrder.ExecuteAfter.Add(TEXT("EcoPerceptionProcessor"));
	bRequiresGameThreadExecution = true;
}

void UEcoPredationProcessor::ConfigureQueries(const TSharedRef<FMassEntityManager>& EntityManager)
{
	// Vitals 는 ReadWrite 로 선언한다. 실제 쓰기는 포식자 루프에서 핸들로 하지만,
	// 선언이 있어야 Mass 가 이 프로세서가 Vitals 를 쓴다는 걸 안다.
	HerbivoreQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	HerbivoreQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadWrite);
	HerbivoreQuery.AddRequirement<FEcoDeathFragment>(EMassFragmentAccess::ReadWrite, EMassFragmentPresence::Optional);
	HerbivoreQuery.AddRequirement<FEcoCreatureLifecycleFragment>(EMassFragmentAccess::ReadWrite, EMassFragmentPresence::Optional);
	HerbivoreQuery.AddTagRequirement<FEcoHerbivoreTag>(EMassFragmentPresence::All);
	HerbivoreQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	HerbivoreQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);

	PredatorQuery.AddRequirement<FTransformFragment>(EMassFragmentAccess::ReadOnly);
	PredatorQuery.AddRequirement<FEcoPredatorStateFragment>(EMassFragmentAccess::ReadWrite);
	PredatorQuery.AddRequirement<FEcoIdentityFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	PredatorQuery.AddRequirement<FEcoVitalsFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	PredatorQuery.AddRequirement<FEcoPreySenseFragment>(EMassFragmentAccess::ReadOnly, EMassFragmentPresence::Optional);
	PredatorQuery.AddTagRequirement<FEcoPredatorTag>(EMassFragmentPresence::All);
	PredatorQuery.AddTagRequirement<FEcoGroundedNavigationTag>(EMassFragmentPresence::None);
	PredatorQuery.AddTagRequirement<FEcoClientProxyTag>(EMassFragmentPresence::None);
	PredatorQuery.AddTagRequirement<FEcoPendingDeathTag>(EMassFragmentPresence::None);
}

void UEcoPredationProcessor::Execute(FMassEntityManager& EntityManager,
									 FMassExecutionContext& Context)
{
	UWorld* World = GetWorld();
	UEcoRegionPredationSubsystem* Predation =
		World ? World->GetSubsystem<UEcoRegionPredationSubsystem>() : nullptr;
	const UEcoNeighborhoodSubsystem* Grid =
		World ? World->GetSubsystem<UEcoNeighborhoodSubsystem>() : nullptr;
	if (!Predation || !Grid || !Grid->IsBuilt())
	{
		return;
	}

	// --- 지역 개체 수 (§3.1 EMA 의 분모). 살아 있는 개체만 센다 ---
	TArray<FVector> AlivePositions;
	HerbivoreQuery.ForEachEntityChunk(Context, [&AlivePositions](FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TConstArrayView<FEcoVitalsFragment> Vitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (Vitals[i].HP > 0.0f)
			{
				AlivePositions.Add(Transforms[i].GetTransform().GetLocation());
			}
		}
	});

	Predation->ReportPopulationSnapshot(AlivePositions);
	// --- 포획. 파이썬 env/world.py 의 포식자 스텝과 같은 규칙 ---
	//   pred_cd = max(pred_cd - 1, 0);  hunting = pred_cd == 0
	//   perceived = dist × (은신처면 cover_hide_mult)
	//   hit = perceived <= catch_r & hunting — 초식의 시야와 무관하다
	//   포식자당 한 마리(체감 거리 최소), 잡으면 pred_cd = pred_eat_cd
	const float Dt = Context.GetDeltaTimeSeconds();
	const float CatchRadius = EcoBehaviorConfig::PredCatchRadiusCm;
	const float HideMult = EcoBehaviorConfig::CoverHideMult;
	const float EatCooldown = EcoBehaviorConfig::PredEatCooldownS;
	const TArray<FEcoNeighborEntry>& Entries = Grid->GetEntries();

	PredatorQuery.ForEachEntityChunk(Context,
		[&EntityManager, Predation, Grid, World, &Entries, Dt, CatchRadius, HideMult, EatCooldown]
		(FMassExecutionContext& Ctx)
	{
		const TConstArrayView<FTransformFragment> Transforms =
			Ctx.GetFragmentView<FTransformFragment>();
		const TArrayView<FEcoPredatorStateFragment> States =
			Ctx.GetMutableFragmentView<FEcoPredatorStateFragment>();
		TArray<int32> Nearby;
		const auto PredatorIds = Ctx.GetFragmentView<FEcoIdentityFragment>();
		const auto PredatorVitals = Ctx.GetFragmentView<FEcoVitalsFragment>();
		const auto PreySenses = Ctx.GetFragmentView<FEcoPreySenseFragment>();

		for (int32 i = 0; i < Ctx.GetNumEntities(); ++i)
		{
			if (!PredatorVitals.IsEmpty() && PredatorVitals[i].HP <= 0) continue;
			FEcoPredatorStateFragment& S = States[i];
			S.EatCooldown = FMath::Max(S.EatCooldown - Dt, 0.0f);
			if (S.EatCooldown > 0.0f)
			{
				continue;   // 식사 중 — 파이썬 hunting == false
			}

			const FVector P = Transforms[i].GetTransform().GetLocation();
			// 체감 거리는 실제 거리 이상이므로 포획 반경으로 조회하면 후보가 빠지지 않는다.
			Grid->QueryRadius(P, CatchRadius, Nearby);

			int32 Best = INDEX_NONE;
			float BestPerceived = TNumericLimits<float>::Max();
			for (int32 Index : Nearby)
			{
				const FEcoNeighborEntry& E = Entries[Index];
				if (E.bPredator || !EntityManager.IsEntityValid(E.Entity))
				{
					continue;
				}
				const float Perceived =
					FVector::Dist2D(E.Location, P) * (E.bInCover ? HideMult : 1.0f);
				// Opt-in Creature wolves require fresh direct sight, plus current LOS at contact.
				// Legacy/Python-parity predator archetypes have no PreySense and keep their V1 rule.
				if (!PreySenses.IsEmpty())
				{
					const auto& Sense = PreySenses[i];
					if (Sense.Target != E.Entity || Sense.Cue.LastDirectSense != EEcoSenseSource::Sight
						|| Sense.Cue.Confidence <= 0 || World->GetTimeSeconds() < Sense.Cue.LastObservedTime
						|| World->GetTimeSeconds() - Sense.Cue.LastObservedTime > .25) continue;
					FHitResult Hit; FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoCreatureCaptureLOS), true);
					if (World->LineTraceSingleByChannel(Hit, P + FVector(0,0,80), E.Location + FVector(0,0,80), ECC_Visibility, Params)) continue;
				}
				if (Perceived > CatchRadius || Perceived >= BestPerceived)
				{
					continue;
				}
				// 같은 틱에 다른 포식자가 먼저 잡았을 수 있다.
				const FEcoVitalsFragment* V = EntityManager.GetFragmentDataPtr<FEcoVitalsFragment>(E.Entity);
				if (!V || V->HP <= 0.0f)
				{
					continue;
				}
				Best = Index;
				BestPerceived = Perceived;
			}
			if (Best == INDEX_NONE)
			{
				continue;
			}

			// 잡혔다. 파이썬은 슬롯을 즉시 리스폰하지만(§4.3) 여기서는 HP 를 0으로 두고
			// 생명주기는 Lifecycle 계층에 맡긴다 — 이 프로세서의 책임은 **판정과 지역 보고**다
			// (§9.6). 테스트 레벨에서는 AEcoPolicyTestSpawner 가 리스폰을 대신한다.
			EntityManager.GetFragmentDataChecked<FEcoVitalsFragment>(Entries[Best].Entity).HP = 0.0f;
			if (auto* Life = EntityManager.GetFragmentDataPtr<FEcoCreatureLifecycleFragment>(Entries[Best].Entity)) Life->bPredated = true;
			if (auto* Death = EntityManager.GetFragmentDataPtr<FEcoDeathFragment>(Entries[Best].Entity))
			{
				Death->Cause = EEcoDeathCause::Predation;
				Death->PredatorStableAgentId = PredatorIds.IsEmpty() ? 0 : PredatorIds[i].StableAgentId;
			}

			Predation->ReportPredation(Entries[Best].Location);
			S.EatCooldown = EatCooldown;
		}
	});
	PredationElapsedSeconds += FMath::Max(0.f, Dt);
	const double Period = EcoBehaviorConfig::StepSeconds;
	for (int32 Pass = 0; Pass < 8 && PredationElapsedSeconds + 1.e-8 >= Period; ++Pass)
	{ Predation->Tick(); PredationElapsedSeconds -= Period; }

}

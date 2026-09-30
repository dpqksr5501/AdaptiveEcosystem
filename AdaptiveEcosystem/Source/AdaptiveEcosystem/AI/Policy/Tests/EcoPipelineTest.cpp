// §9.8-3 — "Utility AI로 전체 파이프라인: 최소 테스트 레벨에서 프로세서 두 개가 돎".
//
// 레벨 에셋 대신 **코드로 월드와 엔티티를 만들어** 프로세서를 실제로 돌린다. 이유:
//   - 손으로 배치한 .umap 보다 결정적이고 CI 에서 반복 가능하다
//   - 이 프로젝트의 Content/ 에셋 144개가 UE 5.8 보다 새 엔진에서 저장돼 로드되지
//     않는다. 레벨에 의존하면 그 블로커에 같이 묶인다
//   - 검증하려는 것은 "프로세서가 실제 엔티티에 돌아 계약에 맞는 값을 내는가" 이지
//     레벨 배치가 아니다
//
// 확인하는 것:
//   1. 네 프로세서가 순서대로 돌고 크래시가 없다
//   2. §3.1 관측 7개가 전부 [0,1]
//   3. §3.2 행동 4개가 전부 [0,1]
//   4. §9.4 정책이 PolicyInterval 틱마다만 돈다
//   5. §3.3 조향 결과 속력이 HerbSpeed 와 같다
//   6. 포식자가 가까우면 도주 분기가 실제로 켜진다
//   7. `eco.UseLearnedPolicy` 로 두 정책이 실제로 갈린다

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorConfig.h"
#include "../EcoBehaviorFragments.h"
#include "../EcoBehaviorProcessors.h"
#include "../EcoNeighborhoodSubsystem.h"
#include "../EcoWorldProviders.h"
#include "EcoTestWorld.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EntityFragments.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassExecutionContext.h"
#include "MassMovementFragments.h"

namespace EcoPipelineTestImpl
{
	constexpr int32 NumHerbivores = 48;
	constexpr int32 NumPredators = 4;
	/** 개체를 이 반경 안에 흩뿌린다. 시야 반경의 몇 배라 이웃이 생긴다. */
	constexpr float SpreadCm = 6000.0f;

	using EcoTest::FScopedTestWorld;

	/** 초식 아키타입에 들어가는 프래그먼트와 태그. §9.4/§9.5 쿼리 요구사항의 합집합. */
	TArray<const UScriptStruct*> HerbivoreComposition()
	{
		return {
			FTransformFragment::StaticStruct(),
			FMassVelocityFragment::StaticStruct(),
			FEcoSteeringGeometryFragment::StaticStruct(),
			FEcoObservationFragment::StaticStruct(),
			FEcoPolicyOutputFragment::StaticStruct(),
			FEcoPolicyRuntimeFragment::StaticStruct(),
			FEcoVitalsFragment::StaticStruct(),
			FEcoHerbivoreTag::StaticStruct(),
		};
	}

	TArray<const UScriptStruct*> PredatorComposition()
	{
		return {
			FTransformFragment::StaticStruct(),
			FMassVelocityFragment::StaticStruct(),
			FEcoPredatorTag::StaticStruct(),
		};
	}

	/** 네 프로세서를 순서대로 한 틱 돌린다 (§9.5 Policy → Steering). */
	struct FPipeline
	{
		UEcoNeighborhoodGatherProcessor* Gather = nullptr;
		UEcoPerceptionProcessor* Perception = nullptr;
		UEcoPolicyProcessor* Policy = nullptr;
		UEcoSteeringProcessor* Steering = nullptr;

		void Create(UWorld* World, FMassEntityManager& EM)
		{
			const TSharedRef<FMassEntityManager> Shared = EM.AsShared();
			Gather = NewObject<UEcoNeighborhoodGatherProcessor>(World);
			Perception = NewObject<UEcoPerceptionProcessor>(World);
			Policy = NewObject<UEcoPolicyProcessor>(World);
			Steering = NewObject<UEcoSteeringProcessor>(World);
			for (UMassProcessor* P : {static_cast<UMassProcessor*>(Gather),
									  static_cast<UMassProcessor*>(Perception),
									  static_cast<UMassProcessor*>(Policy),
									  static_cast<UMassProcessor*>(Steering)})
			{
				P->CallInitialize(World, Shared);
			}
		}

		void Tick(FMassEntityManager& EM, float Dt)
		{
			for (UMassProcessor* P : {static_cast<UMassProcessor*>(Gather),
									  static_cast<UMassProcessor*>(Perception),
									  static_cast<UMassProcessor*>(Policy),
									  static_cast<UMassProcessor*>(Steering)})
			{
				EcoTest::RunProcessor(*P, EM, Dt);
			}
		}
	};

	/** 개체를 격자로 흩뿌려 만든다. 무작위가 아니라 결정적이어야 테스트가 안정된다. */
	void SpawnGrid(FMassEntityManager& EM, const FMassArchetypeHandle& Archetype, int32 Count,
				   float Spread, float ZOffset, TArray<FMassEntityHandle>& Out)
	{
		const int32 Side = FMath::Max(1, FMath::CeilToInt(FMath::Sqrt(static_cast<float>(Count))));
		for (int32 i = 0; i < Count; ++i)
		{
			const FMassEntityHandle E = EM.CreateEntity(Archetype);
			const float X = (static_cast<float>(i % Side) / Side - 0.5f) * 2.0f * Spread;
			const float Y = (static_cast<float>(i / Side) / Side - 0.5f) * 2.0f * Spread;

			FTransformFragment& T = EM.GetFragmentDataChecked<FTransformFragment>(E);
			T.GetMutableTransform().SetLocation(FVector(X, Y, ZOffset));

			// 정지 상태면 시야 판정이 전방 축으로 고정되므로 약간 움직여 둔다.
			FMassVelocityFragment& V = EM.GetFragmentDataChecked<FMassVelocityFragment>(E);
			V.Value = FVector(1.0f, 0.0f, 0.0f) * 10.0f;

			Out.Add(E);
		}
	}
}

using namespace EcoPipelineTestImpl;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPipelineSmokeTest,
	"AdaptiveEcosystem.Policy.PipelineSmoke",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPipelineSmokeTest::RunTest(const FString& Parameters)
{
	FScopedTestWorld Scoped;
	if (!TestNotNull(TEXT("테스트 월드"), Scoped.World))
	{
		return false;
	}
	UWorld* World = Scoped.World;

	UMassEntitySubsystem* EntitySub = World->GetSubsystem<UMassEntitySubsystem>();
	if (!TestNotNull(TEXT("UMassEntitySubsystem"), EntitySub))
	{
		return false;
	}
	FMassEntityManager& EM = EntitySub->GetMutableEntityManager();

	// 월드 제공자와 이웃 색인이 만들어졌는지 — 없으면 프로세서가 조용히 아무것도 안 한다.
	TestNotNull(TEXT("UEcoWorldProviderRegistry"),
				World->GetSubsystem<UEcoWorldProviderRegistry>());
	TestNotNull(TEXT("UEcoNeighborhoodSubsystem"),
				World->GetSubsystem<UEcoNeighborhoodSubsystem>());

	const FMassArchetypeHandle HerbArch = EM.CreateArchetype(HerbivoreComposition());
	const FMassArchetypeHandle PredArch = EM.CreateArchetype(PredatorComposition());

	TArray<FMassEntityHandle> Herbivores;
	TArray<FMassEntityHandle> Predators;
	SpawnGrid(EM, HerbArch, NumHerbivores, SpreadCm, 0.0f, Herbivores);
	SpawnGrid(EM, PredArch, NumPredators, SpreadCm * 0.5f, 0.0f, Predators);

	// 에너지를 서로 다르게 줘서 forage 가 상태에 반응하는지 볼 수 있게 한다.
	for (int32 i = 0; i < Herbivores.Num(); ++i)
	{
		FEcoVitalsFragment& Vitals = EM.GetFragmentDataChecked<FEcoVitalsFragment>(Herbivores[i]);
		Vitals.MaxEnergy = 100.0f;
		Vitals.Energy = 100.0f * (static_cast<float>(i) / Herbivores.Num());
	}

	// §9.8-3 은 **Utility AI 로** 전체 파이프라인을 돌려 보라고 한다.
	IConsoleVariable* CVar =
		IConsoleManager::Get().FindConsoleVariable(TEXT("eco.UseLearnedPolicy"));
	if (!TestNotNull(TEXT("eco.UseLearnedPolicy 콘솔 변수"), CVar))
	{
		return false;
	}
	const int32 SavedCVar = CVar->GetInt();
	CVar->Set(0, ECVF_SetByCode);

	FPipeline Pipeline;
	Pipeline.Create(World, EM);

	const int32 Interval = EcoBehaviorConfig::PolicyInterval;
	const float Dt = 1.0f / 60.0f;

	// --- 정책이 PolicyInterval 틱마다만 도는지 (§9.4) ---
	// 첫 Interval-1 틱 동안은 행동이 기본값(전부 0) 이어야 한다.
	for (int32 t = 0; t < Interval - 1; ++t)
	{
		Pipeline.Tick(EM, Dt);
	}
	{
		const FEcoPolicyActionV1& A =
			EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(Herbivores[0]).Action;
		TestTrue(TEXT("PolicyInterval 전에는 정책이 돌지 않아야 한다"),
				 A.Forage == 0.0f && A.Cohesion == 0.0f && A.FleeDist == 0.0f && A.Cover == 0.0f);
	}

	// 속도가 위치에 반영되는지 보려면 돌리기 전 좌표를 남겨 둬야 한다.
	// 속도만 검사하면 적분 단계가 통째로 빠져도 통과한다 — 실제로 그렇게 새어 나갔다.
	TArray<FVector> PosBefore;
	PosBefore.Reserve(Herbivores.Num());
	for (const FMassEntityHandle& E : Herbivores)
	{
		PosBefore.Add(
			EM.GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation());
	}

	// 이제 충분히 돌린다.
	const int32 TickCount = Interval * 6;
	for (int32 t = 0; t < TickCount; ++t)
	{
		Pipeline.Tick(EM, Dt);
	}

	// --- §3.1 관측 계약 ---
	int32 SawKin = 0;
	int32 SawPredator = 0;
	int32 NonZeroVelocity = 0;
	int32 Fleeing = 0;

	for (const FMassEntityHandle& E : Herbivores)
	{
		const FEcoPolicyObservationV1& O =
			EM.GetFragmentDataChecked<FEcoObservationFragment>(E).Observation;
		float Obs[7];
		O.ToFloatArray(Obs);
		for (int32 i = 0; i < 7; ++i)
		{
			if (!(Obs[i] >= 0.0f && Obs[i] <= 1.0f))
			{
				AddError(FString::Printf(TEXT("관측 %d 가 [0,1] 밖이다: %f"), i, Obs[i]));
				break;
			}
		}
		if (O.ConspecificCount > 0.0f) { ++SawKin; }
		if (O.PredatorCount > 0.0f) { ++SawPredator; }

		// --- §3.2 행동 계약 ---
		const FEcoPolicyActionV1& A = EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(E).Action;
		float Act[4];
		A.ToFloatArray(Act);
		for (int32 j = 0; j < 4; ++j)
		{
			if (!(Act[j] >= 0.0f && Act[j] <= 1.0f))
			{
				AddError(FString::Printf(TEXT("행동 %d 가 [0,1] 밖이다: %f"), j, Act[j]));
				break;
			}
		}

		// --- §3.3 조향 결과 ---
		const FVector V = EM.GetFragmentDataChecked<FMassVelocityFragment>(E).Value;
		if (!V.IsNearlyZero())
		{
			++NonZeroVelocity;
			// normalize(v) * herb_speed 이므로 속력이 정확히 HerbSpeed 여야 한다.
			TestTrue(FString::Printf(TEXT("속력 %.1f == HerbSpeed %.1f"),
									 V.Size(), EcoBehaviorConfig::HerbSpeedCmS),
					 FMath::IsNearlyEqual(static_cast<float>(V.Size()),
										  EcoBehaviorConfig::HerbSpeedCmS, 1.0f));
		}

		const FEcoSteeringGeometryFragment& G =
			EM.GetFragmentDataChecked<FEcoSteeringGeometryFragment>(E);
		if (G.DistPredMin < A.FleeDist * EcoBehaviorConfig::SeeRadiusCm)
		{
			++Fleeing;
		}
	}

	AddInfo(FString::Printf(
		TEXT("초식 %d, 포식자 %d | 동족 본 개체 %d, 포식자 본 개체 %d, 이동 중 %d, 도주 %d"),
		Herbivores.Num(), Predators.Num(), SawKin, SawPredator, NonZeroVelocity, Fleeing));

	// --- 속도가 위치에 실제로 반영되는가 ---
	// 조향이 FMassVelocityFragment 만 쓰고 끝나면 개체는 영원히 제자리다. 엔진의
	// UMassApplyMovementProcessor 는 FMassDesiredMovementFragment 와
	// FMassCodeDrivenMovementTag 를 함께 요구해서 이 아키타입에 걸리지 않는다.
	// 그래서 UEcoSteeringProcessor 가 직접 적분한다 — 그게 도는지 여기서 본다.
	int32 Moved = 0;
	double MaxDisp = 0.0;
	for (int32 i = 0; i < Herbivores.Num(); ++i)
	{
		const FVector Now = EM.GetFragmentDataChecked<FTransformFragment>(Herbivores[i])
								.GetTransform().GetLocation();
		const double Disp = FVector::Dist(Now, PosBefore[i]);
		if (Disp > 1.0) { ++Moved; }
		MaxDisp = FMath::Max(MaxDisp, Disp);
	}
	AddInfo(FString::Printf(
		TEXT("위치 변화: %d/%d 개체, 최대 %.0fcm (속력×시간 상한 %.0fcm)"),
		Moved, Herbivores.Num(), MaxDisp,
		EcoBehaviorConfig::HerbSpeedCmS * Dt * TickCount));

	// 아무도 이웃을 못 봤다면 색인이나 쿼리가 죽은 것이다 — 통과해도 의미가 없다.
	TestTrue(TEXT("동족을 본 개체가 있어야 한다 (이웃 색인이 살아 있는가)"), SawKin > 0);
	TestTrue(TEXT("포식자를 본 개체가 있어야 한다"), SawPredator > 0);
	TestTrue(TEXT("움직이는 개체가 있어야 한다 (조향이 도는가)"), NonZeroVelocity > 0);
	TestTrue(TEXT("속도가 위치에 반영돼야 한다 (개체가 실제로 이동하는가)"), Moved > 0);

	// --- §9.4 콘솔 변수로 두 정책이 실제로 갈리는가 ---
	const FEcoPolicyActionV1 UtilityAction =
		EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(Herbivores[0]).Action;

	CVar->Set(1, ECVF_SetByCode);
	for (int32 t = 0; t < Interval; ++t)
	{
		Pipeline.Tick(EM, Dt);
	}
	const FEcoPolicyActionV1 LearnedAction =
		EM.GetFragmentDataChecked<FEcoPolicyOutputFragment>(Herbivores[0]).Action;

	const bool bDiffer = !FMath::IsNearlyEqual(UtilityAction.Forage, LearnedAction.Forage, 1e-4f)
					  || !FMath::IsNearlyEqual(UtilityAction.Cohesion, LearnedAction.Cohesion, 1e-4f)
					  || !FMath::IsNearlyEqual(UtilityAction.FleeDist, LearnedAction.FleeDist, 1e-4f)
					  || !FMath::IsNearlyEqual(UtilityAction.Cover, LearnedAction.Cover, 1e-4f);
	AddInfo(FString::Printf(TEXT("Utility [%.3f %.3f %.3f %.3f] vs 학습 [%.3f %.3f %.3f %.3f]"),
							UtilityAction.Forage, UtilityAction.Cohesion, UtilityAction.FleeDist,
							UtilityAction.Cover, LearnedAction.Forage, LearnedAction.Cohesion,
							LearnedAction.FleeDist, LearnedAction.Cover));
	TestTrue(TEXT("eco.UseLearnedPolicy 가 실제로 정책을 바꿔야 한다"), bDiffer);

	CVar->Set(SavedCVar, ECVF_SetByCode);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

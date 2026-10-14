// 팀 통합 레벨용 v3 연결("몸은 팀 것, 머리만 우리 것")의 자동화 시험 (계획서 RL_V3_UNREAL_TRAINING_PLAN.md 4-5b).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Integrated"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 묶음:
//   Integrated.SwitchDefaultOff        eco.IntegratedPolicyVersion 기본 1, 끄면 서브시스템·처리기가 아무것도 하지 않는다. 명령줄은 시작값만 (콘솔로 끈다)
//   Integrated.TemplateComposition     v3 트레잇 템플릿: 몸 조각·자리표시·v3 조각이 있고 v1 초식·Social·팀 늑대 조각이 없다. 클라이언트 갈래는 최소
//   Integrated.SpawnPlan               무대 계획: 지역 안, 늑대 28 m 밖, 간격, 지면 검사, 같은 입력 = 같은 자리, 사슴 128 도 들어간다
//   Integrated.SpawnerOverride         조정자 바꾸기: 하나라도 실패하면 하나도 안 바꾼다, 시작 직전 검사 실패면 팀 값으로 되돌린다, 통과한 자리는 조정자 검사를 통과한다
//   Integrated.AdoptionKeys            입양은 세계 난수를 쓰지 않고, 키 = StableAgentId, 첫 관측은 키와 무관. Mass 입양은 생성 순서와 무관
//   Integrated.PerRegionContexts       지역마다 세계 하나 (먹이 패치 다름), 전역 스텝 하나, 학습 범위 확인 (은신처 반경·밀도 하한)
//   Integrated.MultiStepDeathExclusion 한 프레임 여러 스텝: 죽은 개체는 다음 스텝에 움직이지도·먹지도·다시 죽지도·동족으로 세어지지도 않는다
//   Integrated.BlockedMoveHooks        엔진 무관 이동 제약 콜백: 막힌 개체만 제자리, 늑대는 변위 0·방향 반전, 수 세기, 다 통과면 콜백 없음과 비트 단위로 같다
//   Integrated.TerrainBlocking         Mass + 실제 물리 (기운 바닥·벽·지역): 지면 높이·막힘 수가 맞는 개체에 붙고, 아무도 벽을 넘지 않는다
//   Integrated.FlatSessionUnaffected   평면 시험 세션과 한 월드: 두 경로의 시계·개체가 섞이지 않는다 (평면 경로는 기준 루프와 비트 단위로 같다)
//   Integrated.EndToEndMiniWorld       두 지역 × (사슴 16 + 늑대 2), 2000 스텝, 조정자 흉내(사망 → Alive 떼기 → 지우기)
//   Integrated.FeedingFeedback         먹기 되먹임: 기록(먹은 양)은 셀에서 덜어 낸 양과 같고, 먹기 중 먹은 사슴은 에너지가 오른다. 사슴 글자,
//                                      최근 10 초 고리 버퍼·구간에 먹은 사슴 수·에너지 평균·굶주림 수가 개체 조각과 맞는다
//   Integrated.GradualNight            늑대 밤잠 점진화 (eco.IntegratedV3.GradualNight 기본 1 → 설정 → 세계): 늑대 글자(눕는 중·깨는 중·못 누운 까닭),
//                                      Mass 1000 스텝 — 16 m 안에 사슴이 있거나 사냥 중이면 잠들지 않고, 해 진 뒤 바로 자지 않고, 새벽에 깬다

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoBehaviorConfig.h"
#include "../EcoBehaviorFragments.h"
#include "../EcoCreatureV3Trait.h"
#include "../EcoPolicyV3Fragments.h"
#include "../EcoPolicyV3IntegratedFragments.h"
#include "../EcoPolicyV3IntegratedProcessors.h"
#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoPolicyV3Processors.h"
#include "../EcoPolicyV3Subsystem.h"
#include "AI/Social/EcoSocialFragments.h"
#include "AI/Social/Senses/EcoPredatorPerception.h"
#include "AI/Social/Senses/EcoSensoryTypes.h"
#include "Algo/Reverse.h"
#include "CollisionQueryParams.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "Creature/Runtime/EcoCreatureNetworkTrait.h"
#include "Creature/Runtime/EcoCreatureRuntimeTypes.h"
#include "EcoTestWorld.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Mass/EcoMassFragments.h"
#include "Mass/EcoMassNetworkTrait.h"
#include "Mass/EcoMassTags.h"
#include "Mass/EntityFragments.h"
#include "MassEntityConfigAsset.h"
#include "MassEntityManager.h"
#include "MassEntitySubsystem.h"
#include "MassEntityTemplateRegistry.h"
#include "MassMovementFragments.h"
#include "MassSpawnerSubsystem.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"

namespace EcoPolicyV3IntegratedTestImpl
{
	using EcoWorldV3::FHerbView;
	using EcoWorldV3::FThreatAgent;
	using EcoWorldV3::FWorldConfig;

	/** 통합 시험 설정: 무대 60 단위(120 m), 사슴 16, 늑대 2. */
	FEcoV3IntegratedSettings TestSettings(int64 Seed = 31000)
	{
		FEcoV3IntegratedSettings S;
		S.Seed = Seed;
		S.DeerPerRegion = 16;
		S.WolvesPerRegion = 2;
		S.StageSizeUnits = 60.0;
		S.LogIntervalSeconds = 1000.0f;   // 시험 중 기록 줄을 줄인다
		return S;
	}

	/** 평평한 땅 (Z = 0) — 지면 검사 대역. */
	bool FlatGround(const FVector& Hint, FVector& Out)
	{
		Out = FVector(Hint.X, Hint.Y, 0.0);
		return true;
	}

	/** 한 시험 월드의 통합 v3 개체와 처리기 (조정자 없이 — 개체는 v3 트레잇 템플릿으로 직접 만든다). */
	struct FIntegratedHarness
	{
		EcoTest::FScopedTestWorld Scoped;
		FMassEntityManager* EM = nullptr;
		UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
		UEcoPolicyV3IntegratedStepProcessor* StepProc = nullptr;
		UEcoPolicyV3IntegratedVisualProcessor* VisualProc = nullptr;
		UMassEntityConfigAsset* DeerConfig = nullptr;
		UMassEntityConfigAsset* WolfConfig = nullptr;
		TArray<FMassEntityHandle> Deer;
		TArray<FMassEntityHandle> Wolves;
		TMap<FMassEntityHandle, int32> DeathFrame;   // 조정자 흉내: 죽음을 본 프레임
		int32 FrameCount = 0;
		int32 Destroyed = 0;

		bool Setup(FAutomationTestBase& Test, const FEcoV3IntegratedSettings& Settings, bool bActivate = true)
		{
			UWorld* World = Scoped.World;
			if (!Test.TestNotNull(TEXT("테스트 월드"), World))
			{
				return false;
			}
			UMassEntitySubsystem* Mass = World->GetSubsystem<UMassEntitySubsystem>();
			Sub = World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
			if (!Test.TestNotNull(TEXT("UMassEntitySubsystem"), Mass) || !Test.TestNotNull(TEXT("UEcoPolicyV3IntegratedSubsystem"), Sub))
			{
				return false;
			}
			EM = &Mass->GetMutableEntityManager();
			if (bActivate)
			{
				Sub->ActivateForTest(Settings, /*bTerrain*/ false);
			}
			DeerConfig = UEcoCreatureV3Trait::MakeConfig(World, false);
			WolfConfig = UEcoCreatureV3Trait::MakeConfig(World, true);
			const TSharedRef<FMassEntityManager> Shared = EM->AsShared();
			StepProc = NewObject<UEcoPolicyV3IntegratedStepProcessor>(World);
			VisualProc = NewObject<UEcoPolicyV3IntegratedVisualProcessor>(World);
			StepProc->CallInitialize(World, Shared);
			VisualProc->CallInitialize(World, Shared);
			return Test.TestNotNull(TEXT("v3 사슴 설정"), DeerConfig) && Test.TestNotNull(TEXT("v3 늑대 설정"), WolfConfig);
		}

		/** 지역 무대 하나 (은신처 = 1/4·3/4 지점 넷, 반경 CoverUnits). */
		FEcoV3RegionContext* AddRegion(FName RegionId, int32 RegionIndex, const FVector& OriginCm, int32 NumDeer, int32 NumWolves,
									   double CoverUnits = 6.0)
		{
			const FEcoV3IntegratedSettings& S = Sub->GetSettings();
			const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(S.StageSizeUnits, CoverUnits);
			const FWorldConfig C = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, RegionIndex, NumDeer, NumWolves, Covers);
			return Sub->AddContext(RegionId, RegionIndex, OriginCm, C, NumDeer, NumWolves);
		}

		/** 조정자 Spawn 흉내: 템플릿으로 만들고 정체성·지역·자리·방향을 쓴다. */
		TArray<FMassEntityHandle> Spawn(bool bWolf, FName RegionId, int32 RegionIndex, const TArray<FVector>& Points,
										const TArray<int64>& Ids)
		{
			UMassSpawnerSubsystem* Spawner = Scoped.World->GetSubsystem<UMassSpawnerSubsystem>();
			const FMassEntityTemplate& Template = (bWolf ? WolfConfig : DeerConfig)->GetOrCreateEntityTemplate(*Scoped.World);
			TArray<FMassEntityHandle> Out;
			{
				TSharedPtr<FMassEntityManager::FEntityCreationContext> Creation = Spawner->SpawnEntities(Template, Points.Num(), Out);
			}
			for (int32 i = 0; i < Out.Num(); ++i)
			{
				FEcoIdentityFragment& Id = EM->GetFragmentDataChecked<FEcoIdentityFragment>(Out[i]);
				Id.StableAgentId = Ids[i];
				Id.SpeciesId = bWolf ? FName(TEXT("Wolf")) : FName(TEXT("Herbivore"));
				FEcoRegionFragment& Region = EM->GetFragmentDataChecked<FEcoRegionFragment>(Out[i]);
				Region.CurrentRegionId = RegionId;
				Region.CurrentRegionIndex = RegionIndex;
				const double Yaw = static_cast<double>(Ids[i] % 1024) * 2.399963;   // 방향은 개체 번호로 (생성 순서와 무관)
				EM->GetFragmentDataChecked<FTransformFragment>(Out[i]).GetMutableTransform() =
					FTransform(FRotator(0.0, FMath::RadiansToDegrees(Yaw), 0.0), Points[i]);
			}
			(bWolf ? Wolves : Deer).Append(Out);
			return Out;
		}

		/** 한 지역에 계획 자리로 사슴·늑대를 만든다 (StableAgentId 는 FirstId 부터). */
		void SpawnRegion(FEcoV3RegionContext& Ctx, int32 NumDeer, int32 NumWolves, int64 FirstId, int32 GroupIndex)
		{
			const double Half = 0.5 * Ctx.SizeCm();
			const FVector Center = Ctx.OriginCm + FVector(Half, Half, 0.0);
			FEcoV3StagePlan Plan;
			UEcoPolicyV3IntegratedSubsystem::PlanStage(Ctx.RegionId, GroupIndex, Center, Center, Sub->GetSettings(), NumDeer, NumWolves, true,
													  [](const FVector&) { return true; }, &FlatGround, Plan);
			TArray<int64> WolfIds;
			TArray<int64> DeerIds;
			for (int32 m = 0; m < Plan.WolfPoints.Num(); ++m)
			{
				WolfIds.Add(FirstId + m);
			}
			for (int32 i = 0; i < Plan.DeerPoints.Num(); ++i)
			{
				DeerIds.Add(FirstId + Plan.WolfPoints.Num() + i);
			}
			Spawn(true, Ctx.RegionId, Ctx.RegionRuntimeIndex, Plan.WolfPoints, WolfIds);
			Spawn(false, Ctx.RegionId, Ctx.RegionRuntimeIndex, Plan.DeerPoints, DeerIds);
		}

		void Frame(float Dt)
		{
			EcoTest::RunProcessor(*StepProc, *EM, Dt);
			EcoTest::RunProcessor(*VisualProc, *EM, Dt);
			EcoTest::FlushPhase(*EM);
			++FrameCount;
		}

		void DecisionStep() { Frame(EcoBehaviorConfig::StepSeconds); }

		/** 조정자 Reconcile 흉내 (Mass 처리 밖): HP <= 0 → Alive 떼기, 15 프레임(2 초) 뒤 지우기. */
		void CoordinatorReconcile()
		{
			for (TArray<FMassEntityHandle>* List : {&Deer, &Wolves})
			{
				for (int32 k = List->Num() - 1; k >= 0; --k)
				{
					const FMassEntityHandle E = (*List)[k];
					if (!EM->IsEntityValid(E))
					{
						continue;
					}
					if (EM->GetFragmentDataChecked<FEcoVitalsFragment>(E).HP <= 0.0f && !DeathFrame.Contains(E))
					{
						DeathFrame.Add(E, FrameCount);
						EM->RemoveTagFromEntity(E, FEcoAliveTag::StaticStruct());
					}
					if (const int32* F = DeathFrame.Find(E); F && FrameCount - *F >= 15)
					{
						EM->DestroyEntity(E);
						++Destroyed;
					}
				}
			}
		}

		const FEcoV3RegionContext& Ctx(int32 i) const { return *Sub->GetContext(i); }
	};

	FHerbView DeerView(FMassEntityManager& EM, FMassEntityHandle E)
	{
		FHerbView V;
		FEcoBehaviorStateFragment& State = EM.GetFragmentDataChecked<FEcoBehaviorStateFragment>(E);
		V.Rep = &State.Rep;
		V.Decision = &State.Decision;
		V.Body = &EM.GetFragmentDataChecked<FEcoHerbivoreBodyV3Fragment>(E).Body;
		V.Perception = &EM.GetFragmentDataChecked<FEcoPerceptionCacheFragment>(E).Perception;
		V.Control = &EM.GetFragmentDataChecked<FEcoControlOutFragment>(E).Control;
		return V;
	}

	/** 엔진 무관 작은 통합 세계 (배열 저장). */
	struct FMiniWorld
	{
		EcoWorldV3::FWorldState W;
		std::vector<EcoRepertoireV3::FRepState> Reps;
		std::vector<EcoWorldV3::FHerbDecision> Decisions;
		std::vector<EcoWorldV3::FHerbBody> Bodies;
		std::vector<EcoWorldV3::FHerbPerception> Perceptions;
		std::vector<EcoRepertoireV3::FControlOutput> Controls;
		std::vector<FThreatAgent> Threats;
		std::vector<FHerbView> AllViews;

		void Init(const FWorldConfig& C, int32 N, int32 M)
		{
			EcoWorldV3::InitWorld(W, C);
			Reps.assign(N, {});
			Decisions.assign(N, {});
			Bodies.assign(N, {});
			Perceptions.assign(N, {});
			Controls.assign(N, {});
			Threats.assign(M, {});
			AllViews.resize(N);
			for (int32 i = 0; i < N; ++i)
			{
				AllViews[i] = {&Reps[i], &Decisions[i], &Bodies[i], &Perceptions[i], &Controls[i]};
			}
		}
	};

	FWorldConfig MiniConfig(int64 Seed, int32 NumDeer)
	{
		FEcoV3IntegratedSettings S = TestSettings(Seed);
		return UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, 0, NumDeer, 2, EcoWorldV3::QuadCovers(S.StageSizeUnits, 6.0));
	}

	/** 시험용 빌드 문맥: 처리 중인 트레잇 지정(엔진에서는 보호 함수)을 열어 트레잇 하나의 BuildTemplate 를 직접 부른다. */
	struct FTestBuildContext : public FMassEntityTemplateBuildContext
	{
		using FMassEntityTemplateBuildContext::FMassEntityTemplateBuildContext;
		using FMassEntityTemplateBuildContext::SetTraitBeingProcessed;
	};

	/** 자리 P 둘레 (±2 셀) 의 먹이와 용량을 0 으로 — 굶어 죽는 시험이 먹이 덕에 살아나지 않게. */
	void ClearFoodAround(EcoWorldV3::FWorldState& W, const EcoWorldV3::FVec2& P)
	{
		EcoWorldV3::FFoodGrid& F = W.Food;
		for (int32 dy = -2; dy <= 2; ++dy)
		{
			for (int32 dx = -2; dx <= 2; ++dx)
			{
				const int32 k = F.CellOf({P.X + dx * F.Cell, P.Y + dy * F.Cell});
				F.Food[static_cast<size_t>(k)] = 0.0;
				F.Cap[static_cast<size_t>(k)] = 0.0;
			}
		}
		F.ComputeFields(W.ObsCfg.SeeR);
	}

	/**
	 * 가짜 이동 제약 (엔진 무관): 정한 사슴 몸·늑대 하나의 이동만 늘 막는다. 색인 → 개체는 이번 Step 배열로 찾는다(죽은 개체를 빼면 색인이
	 * 밀리므로 개체 주소로 가른다). 부른 수·막은 수를 센다.
	 */
	struct FFakeMoveBlock
	{
		const std::vector<FHerbView>* Herbs = nullptr;
		const std::vector<FThreatAgent*>* Threats = nullptr;
		const EcoWorldV3::FHerbBody* BlockHerb = nullptr;
		const FThreatAgent* BlockThreat = nullptr;
		int64 HerbCalls = 0;
		int64 HerbRejects = 0;
		int64 ThreatCalls = 0;
		int64 ThreatRejects = 0;
		int64 BadIndex = 0;   // 콜백이 받은 색인이 이번 배열 밖

		static bool Herb(void* User, std::int32_t Index, const EcoWorldV3::FVec2& From, const EcoWorldV3::FVec2& To)
		{
			FFakeMoveBlock& F = *static_cast<FFakeMoveBlock*>(User);
			++F.HerbCalls;
			if (!F.Herbs || Index < 0 || Index >= static_cast<std::int32_t>(F.Herbs->size()))
			{
				++F.BadIndex;
				return true;
			}
			const bool bOk = (*F.Herbs)[static_cast<size_t>(Index)].Body != F.BlockHerb;
			F.HerbRejects += bOk ? 0 : 1;
			return bOk;
		}

		static bool Threat(void* User, std::int32_t Index, double FromX, double FromY, double ToX, double ToY)
		{
			FFakeMoveBlock& F = *static_cast<FFakeMoveBlock*>(User);
			++F.ThreatCalls;
			if (!F.Threats || Index < 0 || Index >= static_cast<std::int32_t>(F.Threats->size()))
			{
				++F.BadIndex;
				return true;
			}
			const bool bOk = (*F.Threats)[static_cast<size_t>(Index)] != F.BlockThreat;
			F.ThreatRejects += bOk ? 0 : 1;
			return bOk;
		}

		EcoWorldV3::FStepHooks Hooks(bool bHerb, bool bThreat)
		{
			EcoWorldV3::FStepHooks H;
			H.User = this;
			H.HerbMove = bHerb ? &FFakeMoveBlock::Herb : nullptr;
			H.ThreatMove = bThreat ? &FFakeMoveBlock::Threat : nullptr;
			return H;
		}
	};

	/** 콜백 시험용 작은 세계: 낮(t = 200) 에 사슴 N·늑대 2 (잠행 (12, 12), 추격 (48, 48)), 사슴 0 은 추격 늑대 5 단위 앞. */
	struct FHookWorld
	{
		FMiniWorld Mw;
		std::vector<FHerbView> Alive;
		std::vector<FThreatAgent*> Threats;

		void Init(int64 Seed, int32 N)
		{
			Mw.Init(MiniConfig(Seed, N), N, 2);
			Mw.W.T = 200;
			EcoWorldV3::UpdateDayNight(Mw.W);
			const FWorldConfig& C = Mw.W.Config;
			EcoWorldV3::AdoptThreat(Mw.W, Mw.Threats[0], EcoV3Integrated::WolfSpecForOrdinal(0, C.PredSpeedMult), 12.0, 12.0, 1.0, 0.0, 0);
			EcoWorldV3::AdoptThreat(Mw.W, Mw.Threats[1], EcoV3Integrated::WolfSpecForOrdinal(1, C.PredSpeedMult), 48.0, 48.0, -1.0, 0.0, 1);
			std::vector<std::int32_t> Rows;
			for (int32 i = 0; i < N; ++i)
			{
				const EcoWorldV3::FVec2 P = i == 0 ? EcoWorldV3::FVec2{43.0, 48.0}
												   : EcoWorldV3::FVec2{18.0 + 4.0 * (i % 5), 22.0 + 5.0 * (i / 5)};
				EcoWorldV3::AdoptHerb(Mw.W, Mw.AllViews[i], P, {FMath::Cos(i * 0.9), FMath::Sin(i * 0.9)},
									  EcoRepertoireV3::MakeAgentKeyFromStableId(500 + i));
				Rows.push_back(i);
			}
			Threats = {&Mw.Threats[0], &Mw.Threats[1]};
			EcoWorldV3::ObserveAndDecideRows(Mw.W, Mw.AllViews.data(), N, Threats.data(), 2, Rows.data(), N);
			Alive = Mw.AllViews;
		}

		/** 통합 처리기처럼: 한 스텝 뒤 죽은 개체를 다음 스텝 배열에서 뺀다. */
		EcoWorldV3::FStepReport StepOnce(const EcoWorldV3::FStepHooks* Hooks)
		{
			const EcoWorldV3::FStepReport R = EcoWorldV3::Step(Mw.W, Alive.data(), static_cast<std::int32_t>(Alive.size()), Threats.data(),
															   static_cast<std::int32_t>(Threats.size()), EcoPolicyV3::kBuiltinNet, Hooks);
			std::vector<FHerbView> Next;
			for (const FHerbView& V : Alive)
			{
				if (V.Body->DeathCause == EcoWorldV3::kDeathNone)
				{
					Next.push_back(V);
				}
			}
			Alive = Next;
			return R;
		}
	};

	/** 조정자에서 우리가 바꾸는 공개 속성 (같은지 비교). */
	struct FSpawnerSnap
	{
		const UMassEntityConfigAsset* Deer = nullptr;
		const UMassEntityConfigAsset* Wolf = nullptr;
		TArray<int32> Herbs;
		TArray<int32> Wolves;
		TArray<int32> RegionLimits;
		TArray<TArray<FVector>> HerbPts;
		TArray<TArray<FVector>> WolfPts;
		bool bMigration = false;
		bool bWaves = false;
		float Drain = 0.0f;
		float Food = 0.0f;
		double Day = 0.0;
		double Night = 0.0;
		int32 Global = 0;

		static FSpawnerSnap Take(const AEcoCreatureIntegrationSpawner& S)
		{
			FSpawnerSnap N;
			N.Deer = S.HerbivoreConfig.Get();
			N.Wolf = S.WolfConfig.Get();
			for (const FEcoCreatureSpawnGroup& G : S.Groups)
			{
				N.Herbs.Add(G.Herbivores);
				N.Wolves.Add(G.Wolves);
				N.RegionLimits.Add(G.Schedule.RegionPopulationLimit);
				N.HerbPts.Add(G.HerbivoreSpawnPoints);
				N.WolfPts.Add(G.WolfSpawnPoints);
			}
			N.bMigration = S.Migration.bEnabled;
			N.bWaves = S.bEnableWaves;
			N.Drain = S.EnergyDrainPerSecond;
			N.Food = S.EnergyPerFood;
			N.Day = S.DaySeconds;
			N.Night = S.NightSeconds;
			N.Global = S.GlobalPopulationLimit;
			return N;
		}

		bool operator==(const FSpawnerSnap& O) const
		{
			return Deer == O.Deer && Wolf == O.Wolf && Herbs == O.Herbs && Wolves == O.Wolves && RegionLimits == O.RegionLimits
				&& HerbPts == O.HerbPts && WolfPts == O.WolfPts && bMigration == O.bMigration && bWaves == O.bWaves && Drain == O.Drain
				&& Food == O.Food && Day == O.Day && Night == O.Night && Global == O.Global;
		}
	};

	/** 시험 월드에 정적 상자 (엔진 기본 정육면체, 100 cm). */
	AStaticMeshActor* SpawnBox(UWorld& World, const FVector& Location, const FRotator& Rotation, const FVector& Scale)
	{
		AStaticMeshActor* A = World.SpawnActor<AStaticMeshActor>();
		if (!A)
		{
			return nullptr;
		}
		A->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		A->SetActorScale3D(Scale);
		A->SetActorRotation(Rotation);
		A->SetActorLocation(Location);
		A->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
		return A;
	}

	/** 시험 월드에 지역 하나 (상자 반폭 Extent). */
	AEcologyRegion* SpawnRegionActor(UWorld& World, FName RegionId, const FVector& Center, const FVector& Extent)
	{
		AEcologyRegion* R = World.SpawnActor<AEcologyRegion>(Center, FRotator::ZeroRotator);
		if (R)
		{
			R->RegionId = RegionId;
			R->RegionBounds->SetBoxExtent(Extent);
		}
		return R;
	}

	/** 수직으로 아래를 쏴서 처음 맞는 면의 높이 (없으면 거짓). */
	bool TraceGroundZ(UWorld& World, const FVector& P, double& OutZ)
	{
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3ITestGround), false);
		if (!World.LineTraceSingleByChannel(Hit, FVector(P.X, P.Y, P.Z + 1500.0), FVector(P.X, P.Y, P.Z - 3000.0), ECC_WorldStatic, Params))
		{
			return false;
		}
		OutZ = Hit.ImpactPoint.Z;
		return true;
	}
}

using namespace EcoPolicyV3IntegratedTestImpl;

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedSwitchTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.SwitchDefaultOff",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedSwitchTest::RunTest(const FString& Parameters)
{
	IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.IntegratedPolicyVersion"));
	if (!TestNotNull(TEXT("eco.IntegratedPolicyVersion 콘솔 변수"), CVar))
	{
		return false;
	}
	const int32 Saved = CVar->GetInt();
	TestEqual(TEXT("eco.IntegratedPolicyVersion 기본값은 1 (팀 그대로)"), Saved, 1);
	const bool bCmd = FParse::Param(FCommandLine::Get(), TEXT("EcoIntegratedV3"));
	if (!bCmd)
	{
		TestEqual(TEXT("기본은 끔"), UEcoPolicyV3IntegratedSubsystem::GetRequestedVersion(), 1);

		// 명령줄 인자는 콘솔 변수 시작값(ECVF_SetByCommandline)으로만 들어간다 — 콘솔(코드)에서 1 을 넣으면 명령줄이 있어도 꺼진다
		IConsoleVariable* SeedVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.IntegratedV3.Seed"));
		const uint32 Pri = static_cast<uint32>(CVar->GetFlags() & ECVF_SetByMask);
		const uint32 SeedPri = SeedVar ? static_cast<uint32>(SeedVar->GetFlags() & ECVF_SetByMask) : 0u;
		if (SeedVar && Pri <= static_cast<uint32>(ECVF_SetByCommandline) && SeedPri <= static_cast<uint32>(ECVF_SetByCommandline))
		{
			const int32 SavedSeed = SeedVar->GetInt();
			UEcoPolicyV3IntegratedSubsystem::ApplyCommandLineToConsole(TEXT("-EcoIntegratedV3 -EcoV3Seed=4242"));
			TestEqual(TEXT("명령줄 -EcoIntegratedV3 는 켠다"), UEcoPolicyV3IntegratedSubsystem::GetRequestedVersion(), 3);
			TestEqual(TEXT("명령줄 -EcoV3Seed= 는 시드 콘솔 변수 시작값"), SeedVar->GetInt(), 4242);
			TestEqual(TEXT("명령줄 값의 우선순위는 SetByCommandline"), static_cast<uint32>(CVar->GetFlags() & ECVF_SetByMask),
					  static_cast<uint32>(ECVF_SetByCommandline));
			CVar->Set(1, ECVF_SetByCode);   // 콘솔에서 끄기와 같은 꼴 (콘솔 SetByConsole 은 SetByCode 보다도 높다)
			TestEqual(TEXT("명령줄이 있어도 콘솔 값으로 끈다"), UEcoPolicyV3IntegratedSubsystem::GetRequestedVersion(), 1);
			UEcoPolicyV3IntegratedSubsystem::ApplyCommandLineToConsole(TEXT("-EcoIntegratedV3"));
			TestEqual(TEXT("콘솔이 정한 뒤에는 명령줄이 다시 켜지 않는다"), UEcoPolicyV3IntegratedSubsystem::GetRequestedVersion(), 1);
			SeedVar->Set(SavedSeed, ECVF_SetByCode);
		}
		else
		{
			AddInfo(TEXT("이 프로세스에서 콘솔 변수가 이미 정해져 있어 명령줄 시작값 확인은 건너뛴다 (시험을 다시 돌린 경우)"));
		}

		CVar->Set(2, ECVF_SetByCode);
		TestEqual(TEXT("모르는 값은 끔"), UEcoPolicyV3IntegratedSubsystem::GetRequestedVersion(), 1);
	}
	CVar->Set(3, ECVF_SetByCode);
	TestEqual(TEXT("3 이면 켬"), UEcoPolicyV3IntegratedSubsystem::GetRequestedVersion(), 3);
	CVar->Set(Saved, ECVF_SetByCode);
	TestFalse(TEXT("eco.V3Debug 기본 끔"), IConsoleManager::Get().FindConsoleVariable(TEXT("eco.V3Debug"))->GetInt() != 0);

	// 끈 채 BeginPlay: 서브시스템이 켜지지 않고, 처리기는 v3 개체를 입양하지 않는다
	FIntegratedHarness H;
	if (!H.Setup(*this, TestSettings(), /*bActivate*/ false))
	{
		return false;
	}
	if (!bCmd)
	{
		H.Sub->OnWorldBeginPlay(*H.Scoped.World);
		TestFalse(TEXT("스위치를 끈 BeginPlay 뒤에도 꺼져 있다"), H.Sub->IsActive());
	}
	TArray<int64> Ids = {11};
	H.Spawn(false, TEXT("TestA"), 0, {FVector(500.0, 500.0, 0.0)}, Ids);
	for (int32 f = 0; f < 10; ++f)
	{
		H.DecisionStep();
	}
	const FEcoIntegratedV3Fragment& Int = H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(H.Deer[0]);
	TestFalse(TEXT("꺼져 있으면 처리기가 입양하지 않는다"), Int.bAdopted);
	TestTrue(TEXT("꺼져 있으면 자리도 그대로"),
			 H.EM->GetFragmentDataChecked<FTransformFragment>(H.Deer[0]).GetTransform().GetLocation().Equals(FVector(500.0, 500.0, 0.0)));
	TestEqual(TEXT("꺼져 있으면 무대가 없다"), H.Sub->NumContexts(), 0);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedTemplateTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.TemplateComposition",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedTemplateTest::RunTest(const FString& Parameters)
{
	EcoTest::FScopedTestWorld W;
	UWorld* World = W.World;
	UMassEntityConfigAsset* Deer = UEcoCreatureV3Trait::MakeConfig(World, false);
	UMassEntityConfigAsset* Wolf = UEcoCreatureV3Trait::MakeConfig(World, true);
	if (!TestNotNull(TEXT("사슴 설정"), Deer) || !TestNotNull(TEXT("늑대 설정"), Wolf))
	{
		return false;
	}
	// 팀 조정자 RegisterTemplates 와 같은 검사: FindTrait(UEcoCreatureNetworkTrait) 가 하위 클래스를 받아 준다
	TestNotNull(TEXT("사슴: FindTrait(팀 트레잇) 통과"), Deer->FindTrait(UEcoCreatureNetworkTrait::StaticClass()));
	TestNotNull(TEXT("늑대: FindTrait(팀 트레잇) 통과"), Wolf->FindTrait(UEcoCreatureNetworkTrait::StaticClass()));
	TestTrue(TEXT("설정 GUID 가 서로 다르다"), Deer->GetConfig().GetGuid() != Wolf->GetConfig().GetGuid());

	const FMassEntityTemplate& DT = Deer->GetOrCreateEntityTemplate(*World);
	const FMassEntityTemplate& WT = Wolf->GetOrCreateEntityTemplate(*World);
	if (!TestTrue(TEXT("템플릿이 만들어진다"), DT.IsValid() && WT.IsValid()))
	{
		return false;
	}
	TestTrue(TEXT("템플릿 번호가 다르다"), DT.GetTemplateID() != WT.GetTemplateID());
	const FMassEntityTemplateData& D = DT.GetTemplateData();
	const FMassEntityTemplateData& F = WT.GetTemplateData();

	// 사슴: 몸 (조정자가 Checked 로 읽는 것 전부) + 자리표시 + v3
	TestTrue(TEXT("사슴 몸: Transform·Identity·Region·Vitals·Travel·Velocity"),
			 D.HasFragment<FTransformFragment>() && D.HasFragment<FEcoIdentityFragment>() && D.HasFragment<FEcoRegionFragment>()
				 && D.HasFragment<FEcoVitalsFragment>() && D.HasFragment<FEcoTravelFragment>() && D.HasFragment<FMassVelocityFragment>());
	TestTrue(TEXT("사슴 몸: Lifecycle·Footstep·Presentation, Integrated·CustomMovement·Alive·Authority 태그"),
			 D.HasFragment<FEcoCreatureLifecycleFragment>() && D.HasFragment<FEcoCreatureFootstepFragment>()
				 && D.HasFragment<FEcoCreaturePresentationFragment>() && D.HasTag<FEcoIntegratedCreatureTag>()
				 && D.HasTag<FMassCustomMovementTag>() && D.HasTag<FEcoAliveTag>() && D.HasTag<FEcoAuthorityTag>());
	TestTrue(TEXT("사슴 종 공유 조각"), D.HasSharedFragment<FEcoSpeciesSharedFragment>());
	TestTrue(TEXT("사슴 자리표시: PolicyOutput·SocialMovementRequest (조정자 1초 정산이 Checked 로 읽는다)"),
			 D.HasFragment<FEcoPolicyOutputFragment>() && D.HasFragment<FEcoSocialMovementRequestFragment>());
	TestTrue(TEXT("사슴 v3: 행동 상태·지각·제어 출력·몸·연결 조각·통합 태그"),
			 D.HasFragment<FEcoBehaviorStateFragment>() && D.HasFragment<FEcoPerceptionCacheFragment>()
				 && D.HasFragment<FEcoControlOutFragment>() && D.HasFragment<FEcoHerbivoreBodyV3Fragment>()
				 && D.HasFragment<FEcoIntegratedV3Fragment>() && D.HasTag<FEcoIntegratedPolicyV3Tag>());
	TestFalse(TEXT("사슴에 v1 초식 태그·v1 정책 조각이 없다"),
			  D.HasTag<FEcoHerbivoreTag>() || D.HasFragment<FEcoObservationFragment>() || D.HasFragment<FEcoSteeringGeometryFragment>()
				  || D.HasFragment<FEcoPolicyRuntimeFragment>());
	TestFalse(TEXT("사슴에 Social 조각이 없다 (무리·경보·감각·은신처 의도·Social 행동·피드백)"),
			  D.HasFragment<FEcoHerdMemberFragment>() || D.HasFragment<FEcoAlarmStateFragment>() || D.HasFragment<FEcoSensoryStateFragment>()
				  || D.HasFragment<FEcoShelterIntentFragment>() || D.HasFragment<FEcoSocialBehaviorFragment>()
				  || D.HasFragment<FEcoShelterMovementFeedbackFragment>() || D.HasSharedFragment<FEcoSocialSpeciesSharedFragment>());
	TestFalse(TEXT("사슴에 평면 시험 태그·늑대 조각이 없다"),
			  D.HasTag<FEcoPolicyV3Tag>() || D.HasTag<FEcoThreatV3Tag>() || D.HasFragment<FEcoThreatStateFragment>() || D.HasTag<FEcoPredatorTag>());

	// 늑대: 몸 + 학습 위협 상태 + '먹는 중' 자리표시, 팀 늑대 감각·포식 태그 없음
	TestTrue(TEXT("늑대 몸: Identity·Region·Vitals·Travel·Lifecycle·Footstep·Presentation·Velocity"),
			 F.HasFragment<FEcoIdentityFragment>() && F.HasFragment<FEcoRegionFragment>() && F.HasFragment<FEcoVitalsFragment>()
				 && F.HasFragment<FEcoTravelFragment>() && F.HasFragment<FEcoCreatureLifecycleFragment>()
				 && F.HasFragment<FEcoCreatureFootstepFragment>() && F.HasFragment<FEcoCreaturePresentationFragment>()
				 && F.HasFragment<FMassVelocityFragment>() && F.HasTag<FMassCustomMovementTag>() && F.HasTag<FEcoIntegratedCreatureTag>());
	TestTrue(TEXT("늑대 v3: 위협 상태·연결 조각·통합 태그·PredatorState 자리표시"),
			 F.HasFragment<FEcoThreatStateFragment>() && F.HasFragment<FEcoIntegratedV3Fragment>() && F.HasTag<FEcoIntegratedThreatV3Tag>()
				 && F.HasFragment<FEcoPredatorStateFragment>());
	TestFalse(TEXT("늑대에 팀 포식 태그·먹잇감 감각·감각 설정이 없다"),
			  F.HasTag<FEcoPredatorTag>() || F.HasFragment<FEcoPreySenseFragment>() || F.HasFragment<FEcoSensoryProfileFragment>()
				  || F.HasSharedFragment<FEcoPredatorSensesSharedFragment>());
	TestFalse(TEXT("늑대에 사슴 조각·평면 시험 태그가 없다"),
			  F.HasTag<FEcoThreatV3Tag>() || F.HasTag<FEcoIntegratedPolicyV3Tag>() || F.HasFragment<FEcoPolicyOutputFragment>()
				  || F.HasFragment<FEcoSocialMovementRequestFragment>() || F.HasFragment<FEcoBehaviorStateFragment>());

	// 클라이언트 갈래: 할아버지(UEcoMassNetworkTrait) 구성 + Integrated 태그 + Presentation 만 (논리 조각 없음)
	for (UMassEntityConfigAsset* Config : {Deer, Wolf})
	{
		const UEcoCreatureV3Trait* Trait = Cast<UEcoCreatureV3Trait>(Config->FindTrait(UEcoCreatureV3Trait::StaticClass(), true));
		if (!TestNotNull(TEXT("v3 트레잇"), Trait))
		{
			return false;
		}
		FMassEntityTemplateData ClientData;
		FTestBuildContext ClientCtx(ClientData);
		ClientCtx.SetTraitBeingProcessed(Trait);
		Trait->BuildV3Composition(ClientCtx, *World, /*bClientProxy*/ true);
		const UEcoMassNetworkTrait* Base = GetDefault<UEcoMassNetworkTrait>();
		FMassEntityTemplateData BaseData;
		FTestBuildContext BaseCtx(BaseData);
		BaseCtx.SetTraitBeingProcessed(Base);
		Base->BuildTemplate(BaseCtx, *World);
		const FMassArchetypeCompositionDescriptor Diff = ClientData.GetCompositionDescriptor().CalculateDifference(BaseData.GetCompositionDescriptor());
		TestTrue(TEXT("클라이언트 갈래는 할아버지 구성을 다 갖는다"), ClientData.GetCompositionDescriptor().HasAll(BaseData.GetCompositionDescriptor()));
		TestEqual(TEXT("클라이언트 갈래가 더한 것은 둘 (Integrated 태그·Presentation)"), Diff.CountStoredTypes(), 2);
		TestTrue(TEXT("클라이언트 갈래에 Integrated 태그·Presentation"),
				 ClientData.HasTag<FEcoIntegratedCreatureTag>() && ClientData.HasFragment<FEcoCreaturePresentationFragment>());
		TestFalse(TEXT("클라이언트 갈래에 v3·자리표시·Lifecycle 조각이 없다"),
				  ClientData.HasFragment<FEcoIntegratedV3Fragment>() || ClientData.HasFragment<FEcoBehaviorStateFragment>()
					  || ClientData.HasFragment<FEcoThreatStateFragment>() || ClientData.HasFragment<FEcoPolicyOutputFragment>()
					  || ClientData.HasFragment<FEcoCreatureLifecycleFragment>() || ClientData.HasTag<FMassCustomMovementTag>());
	}
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedPlanTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.SpawnPlan",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedPlanTest::RunTest(const FString& Parameters)
{
	FEcoV3IntegratedSettings S = TestSettings(32000);
	S.DeerPerRegion = 48;
	// 지역 상자: x ∈ [-75000, 75000], y ∈ [25000, 75000] (팀 숲 지역과 같은 크기)
	auto InForest = [](const FVector& P) { return FMath::Abs(P.X) <= 75000.0 && P.Y >= 25000.0 && P.Y <= 75000.0; };
	// 물 대역: x ∈ [33000, 34000] 은 지면 검사 실패
	auto WetGround = [](const FVector& Hint, FVector& Out)
	{
		if (Hint.X >= 33000.0 && Hint.X <= 34000.0)
		{
			return false;
		}
		Out = FVector(Hint.X, Hint.Y, -1600.0);
		return true;
	};
	FEcoV3StagePlan A;
	const bool bOk = UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 0, FVector(34200.0, 46500.0, -1600.0), FVector(0.0, 50000.0, 0.0),
															   S, 48, 2, true, InForest, WetGround, A);
	TestTrue(TEXT("지면 검사로 사슴 48·늑대 2 를 다 채운다"), bOk && A.bComplete && A.bGrounded);
	TestTrue(TEXT("무대가 지역 안"), A.bStageInside);
	int32 Bad = 0;
	double MinWolfDeer = 1e30;
	double MinDeerDeer = 1e30;
	for (int32 i = 0; i < A.DeerPoints.Num(); ++i)
	{
		const FVector& P = A.DeerPoints[i];
		Bad += (A.IsInsideStage(P) && InForest(P) && !(P.X >= 33000.0 && P.X <= 34000.0) && P.Z == -1600.0) ? 0 : 1;
		for (const FVector& Wp : A.WolfPoints)
		{
			MinWolfDeer = FMath::Min(MinWolfDeer, FVector::Dist2D(P, Wp));
		}
		for (int32 j = i + 1; j < A.DeerPoints.Num(); ++j)
		{
			MinDeerDeer = FMath::Min(MinDeerDeer, FVector::Dist2D(P, A.DeerPoints[j]));
		}
	}
	AddInfo(FString::Printf(TEXT("늑대-사슴 최소 %.0f cm, 사슴끼리 최소 %.0f cm"), MinWolfDeer, MinDeerDeer));
	TestEqual(TEXT("무대 밖·지역 밖·물 위 사슴 자리"), Bad, 0);
	TestTrue(TEXT("늑대는 모든 사슴에게서 28 m 밖"), MinWolfDeer >= 2800.0);
	TestTrue(TEXT("사슴끼리 1.5 m 밖"), MinDeerDeer >= 150.0);

	FEcoV3StagePlan B;
	UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 0, FVector(34200.0, 46500.0, -1600.0), FVector(0.0, 50000.0, 0.0), S, 48, 2,
											  true, InForest, WetGround, B);
	TestTrue(TEXT("같은 입력이면 같은 자리 (결정적)"), A.DeerPoints == B.DeerPoints && A.WolfPoints == B.WolfPoints);
	FEcoV3StagePlan C;
	FEcoV3IntegratedSettings S2 = S;
	S2.Seed = 32001;
	UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 0, FVector(34200.0, 46500.0, -1600.0), FVector(0.0, 50000.0, 0.0), S2, 48, 2,
											  true, InForest, WetGround, C);
	TestTrue(TEXT("다른 시드면 다른 자리"), A.DeerPoints != C.DeerPoints);

	// 기본 사슴 수 128 (학습 N): 같은 지형(물 대역 포함)의 120 m 무대에 다 들어가고, 늑대 28 m 밖·간격도 지킨다
	FEcoV3IntegratedSettings S128 = S;
	S128.DeerPerRegion = FEcoV3IntegratedSettings().DeerPerRegion;
	TestEqual(TEXT("기본 사슴 수 = 학습 N 128"), S128.DeerPerRegion, 128);
	FEcoV3StagePlan Full;
	const bool bFull = UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 0, FVector(34200.0, 46500.0, -1600.0), FVector(0.0, 50000.0, 0.0),
																 S128, S128.DeerPerRegion, 2, true, InForest, WetGround, Full);
	double MinWolfDeer128 = 1e30;
	for (const FVector& P : Full.DeerPoints)
	{
		for (const FVector& Wp : Full.WolfPoints)
		{
			MinWolfDeer128 = FMath::Min(MinWolfDeer128, FVector::Dist2D(P, Wp));
		}
	}
	TestTrue(TEXT("사슴 128·늑대 2 를 다 채운다"), bFull && Full.DeerPoints.Num() == 128 && Full.WolfPoints.Num() == 2 && Full.WantDeer == 128);
	TestTrue(TEXT("사슴 128 에서도 늑대는 모든 사슴에게서 28 m 밖"), MinWolfDeer128 >= 2800.0);

	// 지역 가장자리 먹이 자리: 무대가 지역 안으로 옮겨진다
	FEcoV3StagePlan Edge;
	UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 1, FVector(34200.0, 26000.0, -1600.0), FVector(0.0, 50000.0, 0.0), S, 16, 2,
											  false, InForest, &FlatGround, Edge);
	TestTrue(TEXT("가장자리 먹이 자리면 무대 중심을 지역 안쪽으로 옮긴다"), Edge.bStageInside && Edge.CenterCm.Y > 26000.0);

	// 스트리밍 전 계획 (지면 없음): 힌트 그대로 다 채우되 '지면 검사 안 됨' 으로 표시한다
	FEcoV3StagePlan NoGround;
	auto NoTerrain = [](const FVector&, FVector&) { return false; };
	const bool bStrict = UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 0, FVector(34200.0, 46500.0, -1600.0),
																   FVector(0.0, 50000.0, 0.0), S, 48, 2, true, InForest, NoTerrain, NoGround);
	TestFalse(TEXT("지면이 없으면 엄격한 계획은 실패"), bStrict);
	UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("Forest"), 0, FVector(34200.0, 46500.0, -1600.0), FVector(0.0, 50000.0, 0.0), S, 48, 2,
											  false, InForest, NoTerrain, NoGround);
	TestTrue(TEXT("느슨한 계획은 힌트로 다 채우고 지면 검사 안 됨으로 표시"), NoGround.bComplete && !NoGround.bGrounded);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedAdoptionTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.AdoptionKeys",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedAdoptionTest::RunTest(const FString& Parameters)
{
	// --- 엔진 무관: 같은 자리, 키만 다른 두 세계 ---
	constexpr int32 N = 12;
	const FWorldConfig C = MiniConfig(33000, N);
	FMiniWorld SlotKeys;
	FMiniWorld StableKeys;
	SlotKeys.Init(C, N, 2);
	StableKeys.Init(C, N, 2);
	const uint64 RngBefore = StableKeys.W.Rng.State;
	const EcoThreatV3::FThreatSpec Stalker = EcoV3Integrated::WolfSpecForOrdinal(0, C.PredSpeedMult);
	const EcoThreatV3::FThreatSpec Chaser = EcoV3Integrated::WolfSpecForOrdinal(1, C.PredSpeedMult);
	for (FMiniWorld* Mw : {&SlotKeys, &StableKeys})
	{
		EcoWorldV3::AdoptThreat(Mw->W, Mw->Threats[0], Stalker, 5.0, 5.0, 1.0, 0.0, 0);
		EcoWorldV3::AdoptThreat(Mw->W, Mw->Threats[1], Chaser, 55.0, 55.0, -1.0, 0.0, 1);
	}
	std::vector<std::int32_t> Rows;
	for (int32 i = 0; i < N; ++i)
	{
		const EcoWorldV3::FVec2 P{20.0 + 2.0 * (i % 4), 20.0 + 3.0 * (i / 4)};
		const EcoWorldV3::FVec2 Hd{FMath::Cos(i * 0.7), FMath::Sin(i * 0.7)};
		EcoWorldV3::AdoptHerb(SlotKeys.W, SlotKeys.AllViews[i], P, Hd, EcoRepertoireV3::MakeAgentKey(static_cast<uint32>(i), 0));
		EcoWorldV3::AdoptHerb(StableKeys.W, StableKeys.AllViews[i], P, Hd, EcoRepertoireV3::MakeAgentKeyFromStableId(1000 + 7 * i));
		Rows.push_back(i);
	}
	TestEqual(TEXT("입양은 세계 난수를 쓰지 않는다"), StableKeys.W.Rng.State, RngBefore);
	std::vector<FThreatAgent*> TS = {&SlotKeys.Threats[0], &SlotKeys.Threats[1]};
	std::vector<FThreatAgent*> TK = {&StableKeys.Threats[0], &StableKeys.Threats[1]};
	EcoWorldV3::ObserveAndDecideRows(SlotKeys.W, SlotKeys.AllViews.data(), N, TS.data(), 2, Rows.data(), N);
	EcoWorldV3::ObserveAndDecideRows(StableKeys.W, StableKeys.AllViews.data(), N, TK.data(), 2, Rows.data(), N);
	int32 ObsDiff = 0;
	int32 JitterBad = 0;
	for (int32 i = 0; i < N; ++i)
	{
		for (int32 k = 0; k < EcoObservationV3::kObsDim; ++k)
		{
			ObsDiff += SlotKeys.Perceptions[i].Obs[k] == StableKeys.Perceptions[i].Obs[k] ? 0 : 1;
		}
		JitterBad += StableKeys.Reps[i].Jitter == EcoRepertoireV3::DecisionJitter(C.Seed, EcoRepertoireV3::MakeAgentKeyFromStableId(1000 + 7 * i), 3) ? 0 : 1;
		JitterBad += SlotKeys.Reps[i].Jitter == EcoRepertoireV3::DecisionJitter(C.Seed, EcoRepertoireV3::MakeAgentKey(static_cast<uint32>(i), 0), 3) ? 0 : 1;
	}
	TestEqual(TEXT("첫 관측은 키와 무관하다 (StableAgentId 키 = 슬롯 키와 같은 관측)"), ObsDiff, 0);
	TestEqual(TEXT("사건 결정 지연 = H(505, 세션 시드, 키)"), JitterBad, 0);
	TestTrue(TEXT("늑대 종류: 순번 0 잠행형, 1 추격형, 모두 주행성, 속력 0.8배"),
			 Stalker.Type == EcoThreatV3::EThreatType::Stalker && Chaser.Type == EcoThreatV3::EThreatType::Chaser && !Stalker.bNocturnal
				 && !Chaser.bNocturnal && !Chaser.bRanged && FMath::IsNearlyEqual(Chaser.BaseSpeed, 0.48, 1e-12));

	// --- Mass: 생성 순서가 달라도 (청크 순서) StableAgentId 순으로 같은 결과 ---
	auto Run = [this](bool bReverse, TArray<uint8>& OutBehaviors, TArray<double>& OutPos) -> bool
	{
		FIntegratedHarness H;
		if (!H.Setup(*this, TestSettings(33001)))
		{
			return false;
		}
		FEcoV3RegionContext* Ctx = H.AddRegion(TEXT("TestA"), 0, FVector(0.0, 0.0, 0.0), 16, 2);
		const FVector Center(6000.0, 6000.0, 0.0);
		FEcoV3StagePlan Plan;
		UEcoPolicyV3IntegratedSubsystem::PlanStage(TEXT("TestA"), 0, Center, Center, H.Sub->GetSettings(), 16, 2, true,
												  [](const FVector&) { return true; }, &FlatGround, Plan);
		TArray<int64> DeerIds;
		for (int32 i = 0; i < 16; ++i)
		{
			DeerIds.Add(100 + i);
		}
		TArray<int64> WolfIds = {50, 51};
		TArray<FVector> DeerPts = Plan.DeerPoints;
		TArray<FVector> WolfPts = Plan.WolfPoints;
		if (bReverse)
		{
			Algo::Reverse(DeerIds);
			Algo::Reverse(DeerPts);
			Algo::Reverse(WolfIds);
			Algo::Reverse(WolfPts);
			H.Spawn(false, TEXT("TestA"), 0, DeerPts, DeerIds);
			H.Spawn(true, TEXT("TestA"), 0, WolfPts, WolfIds);
		}
		else
		{
			H.Spawn(true, TEXT("TestA"), 0, WolfPts, WolfIds);
			H.Spawn(false, TEXT("TestA"), 0, DeerPts, DeerIds);
		}
		H.DecisionStep();
		// 입양 확인: 키 = StableAgentId, 자리 = Transform ÷ 200 − 원점, 늑대 종류 = StableAgentId 순번
		int32 Bad = 0;
		for (const FMassEntityHandle& E : H.Deer)
		{
			const int64 Id = H.EM->GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId;
			const FEcoIntegratedV3Fragment& Int = H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);
			const FHerbView V = DeerView(*H.EM, E);
			Bad += (Int.bAdopted && Int.ContextIndex == Ctx->Index
					&& V.Rep->Jitter == EcoRepertoireV3::DecisionJitter(Ctx->Sim.Config.Seed, EcoRepertoireV3::MakeAgentKeyFromStableId(Id), 3))
					   ? 0 : 1;
		}
		for (const FMassEntityHandle& E : H.Wolves)
		{
			const int64 Id = H.EM->GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId;
			const FThreatAgent& A = H.EM->GetFragmentDataChecked<FEcoThreatStateFragment>(E).Agent;
			const EcoThreatV3::EThreatType Want = Id == 50 ? EcoThreatV3::EThreatType::Stalker : EcoThreatV3::EThreatType::Chaser;
			Bad += A.Spec.Type == Want ? 0 : 1;
		}
		TestEqual(TEXT("입양: 키 = StableAgentId, 늑대 종류 = StableAgentId 순번"), Bad, 0);
		for (int32 s = 0; s < 200; ++s)
		{
			H.DecisionStep();
		}
		// StableAgentId 순으로 기록
		TArray<FMassEntityHandle> Sorted = H.Deer;
		Sorted.Sort([&H](const FMassEntityHandle& A, const FMassEntityHandle& B)
		{
			return H.EM->GetFragmentDataChecked<FEcoIdentityFragment>(A).StableAgentId < H.EM->GetFragmentDataChecked<FEcoIdentityFragment>(B).StableAgentId;
		});
		for (const FMassEntityHandle& E : Sorted)
		{
			const FHerbView V = DeerView(*H.EM, E);
			OutBehaviors.Add(static_cast<uint8>(V.Rep->Behavior));
			OutPos.Add(V.Body->Pos.X);
			OutPos.Add(V.Body->Pos.Y);
		}
		return true;
	};
	TArray<uint8> BehA, BehB;
	TArray<double> PosA, PosB;
	if (!Run(false, BehA, PosA) || !Run(true, BehB, PosB))
	{
		return false;
	}
	TestTrue(TEXT("생성 순서(청크 순서)가 달라도 200 스텝 뒤 행동·자리가 비트 단위로 같다"), BehA == BehB && PosA == PosB);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedContextsTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.PerRegionContexts",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedContextsTest::RunTest(const FString& Parameters)
{
	const FEcoV3IntegratedSettings S = TestSettings(34000);
	// 학습 범위: 늑대 2 (잠행 1 + 추격 1), 무대 60 단위, 은신처 반경 6 단위 넷 (약 12.6%) → 경고 없음
	const FWorldConfig Good = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, 0, 48, 2, EcoWorldV3::QuadCovers(60.0, 6.0));
	for (const FString& Why : UEcoPolicyV3Subsystem::CheckTrainingRange(Good))
	{
		AddError(FString::Printf(TEXT("통합 기본 설정이 학습 범위 밖: %s"), *Why));
	}
	TestTrue(TEXT("통합 설정: 부활 없음·고정 EMA 분모·지역 난수 갈래"),
			 !Good.bRespawnDead && Good.PredEmaDenominator == 48 && Good.RngStream == 1 && Good.DayPeriod == 900 && Good.NumStalkers == 1
				 && Good.NumChasers == 1 && Good.NumNocturnal == 0);
	const FWorldConfig OneWolf = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, 0, 48, 1, EcoWorldV3::QuadCovers(60.0, 6.0));
	TestTrue(TEXT("늑대 1 마리 무대는 학습 범위 경고가 난다"), UEcoPolicyV3Subsystem::CheckTrainingRange(OneWolf).Num() > 0);

	// 기본 사슴 수 128 = 학습 N: 피식 EMA 분모도 학습의 고정 128 과 같다
	const FWorldConfig Default128 = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(
		S, 0, FEcoV3IntegratedSettings().DeerPerRegion, 2, EcoWorldV3::QuadCovers(60.0, S.ExtraCoverRadiusUnits(60.0)));
	TestEqual(TEXT("기본 설정의 피식 EMA 분모 = 128 (학습과 같다)"), Default128.PredEmaDenominator, 128);

	// 무대 크기를 바꿔도 우리 은신처 4 개(반경 = 한 변 × 0.1, 4~9 단위)는 반경·넓이가 학습 범위 안이다
	for (const double Size : {60.0, 72.5, 85.0, 97.5, 110.0})
	{
		FEcoV3IntegratedSettings Sz = S;
		Sz.StageSizeUnits = Size;
		const double Ru = Sz.ExtraCoverRadiusUnits(Size);
		const FWorldConfig C = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Sz, 0, FEcoV3IntegratedSettings::kTrainDeer, 2,
																					 EcoWorldV3::QuadCovers(Size, Ru));
		const TArray<FString> Why = UEcoPolicyV3Subsystem::CheckTrainingRange(C);
		TestTrue(FString::Printf(TEXT("무대 %.1f 단위: 은신처 반경 %.2f 단위가 학습 4~9 안이고 경고가 없다 (%s)"), Size, Ru,
								 *FString::Join(Why, TEXT(", "))),
				 Ru >= 4.0 && Ru <= 9.0 && Why.IsEmpty());
		TestFalse(FString::Printf(TEXT("무대 %.1f 단위에 사슴 128 은 학습 밀도 하한 위"), Size),
				  FEcoV3IntegratedSettings::IsBelowTrainingDensity(FEcoV3IntegratedSettings::kTrainDeer, Size));
	}
	// 밀도 하한 = 128 / 110² 마리/단위²: 60 단위 무대는 38.1 마리 — 39 는 위, 38 은 아래
	TestFalse(TEXT("60 단위 무대에 사슴 39 는 하한 위"), FEcoV3IntegratedSettings::IsBelowTrainingDensity(39, 60.0));
	TestTrue(TEXT("60 단위 무대에 사슴 38 은 하한 아래"), FEcoV3IntegratedSettings::IsBelowTrainingDensity(38, 60.0));
	TestTrue(TEXT("110 단위 무대에 사슴 48 은 하한 아래 (예전 기본값이 큰 무대에서 학습 밖이던 까닭)"),
			 FEcoV3IntegratedSettings::IsBelowTrainingDensity(48, 110.0));

	FIntegratedHarness H;
	if (!H.Setup(*this, S))
	{
		return false;
	}
	FEcoV3RegionContext* A = H.AddRegion(TEXT("RegionA"), 0, FVector(0.0, 0.0, 0.0), 16, 2);
	FEcoV3RegionContext* B = H.AddRegion(TEXT("RegionB"), 1, FVector(0.0, 50000.0, 100.0), 16, 2);
	TestEqual(TEXT("지역 무대 둘"), H.Sub->NumContexts(), 2);
	TestTrue(TEXT("찾기"), H.Sub->FindContext(TEXT("RegionA")) == A && H.Sub->FindContext(TEXT("RegionB")) == B && !H.Sub->FindContext(TEXT("None")));
	TestTrue(TEXT("지역마다 먹이 패치가 다르다 (난수 갈래)"), A->Sim.Food.Cap != B->Sim.Food.Cap);
	TestTrue(TEXT("원점·크기"), A->OriginCm.Equals(FVector::ZeroVector) && B->OriginCm.Equals(FVector(0.0, 50000.0, 100.0)) && A->SizeUnits == 60.0);
	H.SpawnRegion(*A, 16, 2, 1, 0);
	H.SpawnRegion(*B, 16, 2, 100, 1);
	for (int32 s = 0; s < 120; ++s)
	{
		H.DecisionStep();
	}
	TestEqual(TEXT("전역 스텝"), H.Sub->GetGlobalStep(), static_cast<int64>(120));
	TestTrue(TEXT("두 지역이 같은 전역 스텝 t"), A->Sim.T == 120 && B->Sim.T == 120);
	TestEqual(TEXT("두 지역 같은 어둠"), A->Sim.Dark, B->Sim.Dark);
	TestTrue(TEXT("지역마다 따로 입양"), A->AdoptedDeer == 16 && B->AdoptedDeer == 16 && A->AdoptedWolves == 2 && B->AdoptedWolves == 2);
	// 지역 B 개체는 B 원점 기준 단위 자리, Transform 은 B 원점 + 단위 × 200
	int32 Bad = 0;
	for (const FMassEntityHandle& E : H.Deer)
	{
		const FEcoIntegratedV3Fragment& Int = H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);
		const FEcoV3RegionContext& Ctx = *H.Sub->GetContext(Int.ContextIndex);
		const FHerbView V = DeerView(*H.EM, E);
		const FVector Want = Ctx.UnitsToCm(V.Body->PrevPos.X, V.Body->PrevPos.Y, Int.PrevGroundZ);
		const FVector Got = H.EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
		Bad += (V.Body->Pos.X >= 0.0 && V.Body->Pos.X <= 60.0 && V.Body->Pos.Y >= 0.0 && V.Body->Pos.Y <= 60.0 && Got.Equals(Want, 0.01)) ? 0 : 1;
		const FName Region = H.EM->GetFragmentDataChecked<FEcoRegionFragment>(E).CurrentRegionId;
		Bad += Ctx.RegionId == Region ? 0 : 1;
	}
	TestEqual(TEXT("무대 안 자리·화면 대응·지역 소속"), Bad, 0);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedDeathTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.MultiStepDeathExclusion",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedDeathTest::RunTest(const FString& Parameters)
{
	// --- 엔진 무관: 굶어 죽은 개체를 빼면 다시 죽지 않고, 빼지 않으면 스텝마다 다시 '굶어 죽는다' ---
	auto RunMini = [](bool bExclude, int64& OutStarved, EcoWorldV3::FHerbBody& OutCorpse, int32& OutKinInputs)
	{
		constexpr int32 N = 3;
		FMiniWorld Mw;
		Mw.Init(MiniConfig(35000, N), N, 0);
		std::vector<std::int32_t> Rows = {0, 1, 2};
		EcoWorldV3::AdoptHerb(Mw.W, Mw.AllViews[0], {30.0, 30.0}, {1.0, 0.0}, 1);
		EcoWorldV3::AdoptHerb(Mw.W, Mw.AllViews[1], {28.0, 30.0}, {1.0, 0.0}, 2);
		EcoWorldV3::AdoptHerb(Mw.W, Mw.AllViews[2], {5.0, 5.0}, {1.0, 0.0}, 3);
		ClearFoodAround(Mw.W, {30.0, 30.0});
		EcoWorldV3::ObserveAndDecideRows(Mw.W, Mw.AllViews.data(), N, nullptr, 0, Rows.data(), N);
		Mw.Bodies[0].Energy = 0.0005;   // 대사 0.002 × 보행 배수 0.71 이상, 둘레에 먹이 없음 → 첫 스텝에 굶어 죽는다
		std::vector<FHerbView> Alive = Mw.AllViews;
		for (int32 s = 0; s < 3; ++s)
		{
			EcoWorldV3::Step(Mw.W, Alive.data(), static_cast<int32>(Alive.size()), nullptr, 0);
			if (s == 0)
			{
				OutCorpse = Mw.Bodies[0];
			}
			if (bExclude)
			{
				std::vector<FHerbView> Next;
				for (const FHerbView& V : Alive)
				{
					if (V.Body->DeathCause == EcoWorldV3::kDeathNone)
					{
						Next.push_back(V);
					}
				}
				Alive = Next;
			}
		}
		OutStarved = Mw.W.Stats.Starved;
		OutKinInputs = static_cast<int32>(Mw.W.KinIn.size());
		return Mw.Bodies[0];
	};
	int64 StarvedEx = 0, StarvedNo = 0;
	EcoWorldV3::FHerbBody CorpseEx, CorpseNo;
	int32 KinEx = 0, KinNo = 0;
	const EcoWorldV3::FHerbBody AfterEx = RunMini(true, StarvedEx, CorpseEx, KinEx);
	RunMini(false, StarvedNo, CorpseNo, KinNo);
	TestEqual(TEXT("빼면 굶음은 한 번"), StarvedEx, static_cast<int64>(1));
	TestEqual(TEXT("빼지 않으면 스텝마다 다시 굶어 죽는다 (빼야 하는 까닭)"), StarvedNo, static_cast<int64>(3));
	TestTrue(TEXT("죽은 스텝: 굶음 표시, PrevPos = Pos (화면이 튀지 않는다), 부활 없음"),
			 CorpseEx.DeathCause == EcoWorldV3::kDeathStarved && CorpseEx.PrevPos.X == CorpseEx.Pos.X && CorpseEx.PrevPos.Y == CorpseEx.Pos.Y
				 && !CorpseEx.bRespawned && CorpseEx.Generation == 0);
	TestTrue(TEXT("뺀 뒤 시체는 움직이지도 먹지도 않는다"),
			 AfterEx.Pos.X == CorpseEx.Pos.X && AfterEx.Pos.Y == CorpseEx.Pos.Y && AfterEx.Energy == CorpseEx.Energy
				 && AfterEx.DeathCause == EcoWorldV3::kDeathStarved);
	TestEqual(TEXT("뺀 뒤 동족 목록에 시체가 없다"), KinEx, 2);
	TestEqual(TEXT("빼지 않으면 동족 목록에 남는다"), KinNo, 3);

	// --- Mass: 한 프레임 3 스텝 — 잡힘·굶음이 스텝 안에서 넘겨지고 다음 스텝에서 빠진다 ---
	// 이 시험은 사망 넘기기만 본다. 늑대 밤잠 점진화(기본 켬)는 끈다: 켜면 t = 0(d = 0.5)에 입양한 늑대가 자고 있다가 늑대별 지연(0~22
	// 스텝)만큼 뒤에 깨어 2 초에 걸쳐 걸음을 올리므로 3 스텝 안에 잡지 못한다. 밤잠은 Integrated.GradualNight 시험이 본다
	FEcoV3IntegratedSettings DeathSettings = TestSettings(35001);
	DeathSettings.bGradualNight = false;
	FIntegratedHarness H;
	if (!H.Setup(*this, DeathSettings))
	{
		return false;
	}
	// 은신처는 반경 4 단위 (무대 1/4 지점) — 무대 가운데 사슴에게는 HIDE 가 닫혀 있다 (cover_dist 관측 ≥ 0.75)
	FEcoV3RegionContext* Ctx = H.AddRegion(TEXT("TestA"), 0, FVector::ZeroVector, 3, 1, 4.0);
	// 늑대 (30, 30) 오른쪽을 본다, 사슴 0 은 0.3 단위 앞 (잡힌다), 사슴 1 은 (50, 52) 먹이 없는 곳에서 굶는다, 사슴 2 는 (5, 50)
	// t = 0 은 새벽 전환(d = 0.5)이라 주행성 늑대가 첫 스텝에는 자고, 둘째 스텝(d < 0.5)에 잡는다
	H.Spawn(true, TEXT("TestA"), 0, {FVector(6000.0, 6000.0, 0.0)}, {10});
	H.Spawn(false, TEXT("TestA"), 0, {FVector(6060.0, 6000.0, 0.0), FVector(10000.0, 10400.0, 0.0), FVector(1000.0, 10000.0, 0.0)},
			{20, 21, 22});
	H.EM->GetFragmentDataChecked<FTransformFragment>(H.Wolves[0]).GetMutableTransform().SetRotation(FQuat::Identity);
	H.Frame(0.001f);   // 입양만 (스텝 0)
	TestEqual(TEXT("입양 프레임에는 스텝이 없다"), Ctx->Sim.T, static_cast<int64>(0));
	ClearFoodAround(Ctx->Sim, {50.0, 52.0});
	DeerView(*H.EM, H.Deer[1]).Body->Energy = 0.0005;
	H.Frame(3.0f * EcoBehaviorConfig::StepSeconds);   // 한 프레임 3 스텝
	TestEqual(TEXT("한 프레임 3 스텝"), Ctx->Sim.T, static_cast<int64>(3));
	const FEcoVitalsFragment& V0 = H.EM->GetFragmentDataChecked<FEcoVitalsFragment>(H.Deer[0]);
	const FEcoVitalsFragment& V1 = H.EM->GetFragmentDataChecked<FEcoVitalsFragment>(H.Deer[1]);
	const FEcoCreatureLifecycleFragment& L0 = H.EM->GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(H.Deer[0]);
	const FEcoCreatureLifecycleFragment& L1 = H.EM->GetFragmentDataChecked<FEcoCreatureLifecycleFragment>(H.Deer[1]);
	TestTrue(TEXT("잡힌 사슴: HP 0 + bPredated (조정자가 지역 피식 사건으로 넘긴다)"), V0.HP <= 0.0f && L0.bPredated);
	TestTrue(TEXT("굶은 사슴: HP 0, bPredated 아님"), V1.HP <= 0.0f && !L1.bPredated);
	TestEqual(TEXT("포획은 한 번"), Ctx->Sim.Stats.Caught, static_cast<int64>(1));
	TestEqual(TEXT("굶음은 한 번 (한 프레임 여러 스텝에서도)"), Ctx->Sim.Stats.Starved, static_cast<int64>(1));
	const FHerbView D0 = DeerView(*H.EM, H.Deer[0]);
	const FEcoIntegratedV3Fragment& I0 = H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(H.Deer[0]);
	const FVector Corpse = H.EM->GetFragmentDataChecked<FTransformFragment>(H.Deer[0]).GetTransform().GetLocation();
	TestTrue(TEXT("시체 화면 = 죽은 자리, 속도 0"),
			 I0.bDead && Corpse.Equals(Ctx->UnitsToCm(D0.Body->DeathPos.X, D0.Body->DeathPos.Y, I0.GroundZ), 0.01)
				 && H.EM->GetFragmentDataChecked<FMassVelocityFragment>(H.Deer[0]).Value.IsZero());
	// 조정자 흉내로 Alive 를 뗀 뒤 몇 프레임 더: 시체는 그대로, 다시 세지 않는다
	H.CoordinatorReconcile();
	for (int32 f = 0; f < 5; ++f)
	{
		H.DecisionStep();
		H.CoordinatorReconcile();
	}
	TestTrue(TEXT("Alive 를 뗀 시체는 그 자리에 남는다"),
			 H.EM->GetFragmentDataChecked<FTransformFragment>(H.Deer[0]).GetTransform().GetLocation().Equals(Corpse, 0.01));
	TestTrue(TEXT("그 뒤에도 포획·굶음 수가 그대로"), Ctx->Sim.Stats.Caught == 1 && Ctx->Sim.Stats.Starved == 1);
	TestEqual(TEXT("산 사슴 집계"), Ctx->AliveDeer, 1);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedFlatTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.FlatSessionUnaffected",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedFlatTest::RunTest(const FString& Parameters)
{
	FIntegratedHarness H;
	if (!H.Setup(*this, TestSettings(36000)))
	{
		return false;
	}
	UWorld* World = H.Scoped.World;
	FEcoV3RegionContext* Ctx = H.AddRegion(TEXT("TestA"), 0, FVector(-30000.0, 0.0, 0.0), 16, 2);
	H.SpawnRegion(*Ctx, 16, 2, 1, 0);

	// 같은 월드에 평면 시험 세션 (평면 처리기 둘)
	FWorldConfig Flat;
	Flat.Seed = 36001;
	Flat.WorldSize = 60.0;
	Flat.NumHerbivores = 24;
	Flat.NumStalkers = 2;
	Flat.NumChasers = 1;
	Flat.NumRanged = 0;
	Flat.NumNocturnal = 0;
	Flat.Covers = EcoWorldV3::QuadCovers(60.0, 7.0);
	UEcoPolicyV3Subsystem* FlatSub = World->GetSubsystem<UEcoPolicyV3Subsystem>();
	TArray<FMassEntityHandle> FlatHerbs, FlatThreats;
	if (!TestTrue(TEXT("평면 세션"), FlatSub && FlatSub->BeginSession(Flat, FVector(20000.0, 0.0, 0.0), 0.0f))
		|| !TestTrue(TEXT("평면 개체군"), FlatSub->SpawnPopulation(*H.EM, FlatHerbs, FlatThreats)))
	{
		return false;
	}
	UEcoPolicyV3StepProcessor* FlatStep = NewObject<UEcoPolicyV3StepProcessor>(World);
	UEcoPolicyV3VisualProcessor* FlatVisual = NewObject<UEcoPolicyV3VisualProcessor>(World);
	FlatStep->CallInitialize(World, H.EM->AsShared());
	FlatVisual->CallInitialize(World, H.EM->AsShared());
	EcoWorldV3::FReferenceWorld Ref;
	Ref.Init(Flat);

	// 평면 처리기가 통합 개체를 모으면 '슬롯이 맞지 않아' 오류 로그가 나고 이 시험은 실패한다
	constexpr int32 Steps = 60;
	for (int32 s = 0; s < Steps; ++s)
	{
		EcoTest::RunProcessor(*FlatStep, *H.EM, EcoBehaviorConfig::StepSeconds);
		EcoTest::RunProcessor(*H.StepProc, *H.EM, EcoBehaviorConfig::StepSeconds);
		EcoTest::RunProcessor(*FlatVisual, *H.EM, EcoBehaviorConfig::StepSeconds);
		EcoTest::RunProcessor(*H.VisualProc, *H.EM, EcoBehaviorConfig::StepSeconds);
		EcoTest::FlushPhase(*H.EM);
		Ref.StepOnce();
	}
	TestEqual(TEXT("평면 세션 t"), FlatSub->GetSim().T, static_cast<int64>(Steps));
	TestEqual(TEXT("통합 전역 t (시계가 따로)"), H.Sub->GetGlobalStep(), static_cast<int64>(Steps));
	// 평면 경로는 기준 루프와 비트 단위로 같다 — 통합 처리기가 평면 개체를 건드렸다면 갈린다
	int32 Diff = 0;
	for (int32 i = 0; i < FlatHerbs.Num(); ++i)
	{
		const FHerbView V = UEcoPolicyV3Subsystem::MakeHerbView(*H.EM, FlatHerbs[i]);
		const FHerbView& R = Ref.Views[i];
		Diff += (V.Body->Pos.X == R.Body->Pos.X && V.Body->Pos.Y == R.Body->Pos.Y && V.Body->Energy == R.Body->Energy
				 && V.Rep->Behavior == R.Rep->Behavior && V.Body->Generation == R.Body->Generation)
					? 0 : 1;
	}
	TestEqual(TEXT("평면 사슴 = 기준 루프 (비트 단위)"), Diff, 0);
	TestTrue(TEXT("평면 세계 EMA·먹이 = 기준 루프"), FlatSub->GetSim().PredEma == Ref.World.PredEma && FlatSub->GetSim().Food.Total() == Ref.World.Food.Total());
	int32 NotAdopted = 0;
	for (const FMassEntityHandle& E : FlatHerbs)
	{
		NotAdopted += H.EM->GetFragmentDataPtr<FEcoIntegratedV3Fragment>(E) == nullptr ? 1 : 0;
	}
	TestEqual(TEXT("평면 개체에는 통합 조각이 없다"), NotAdopted, FlatHerbs.Num());
	TestTrue(TEXT("통합 개체는 입양됐다"), Ctx->AdoptedDeer == 16 && Ctx->AdoptedWolves == 2);
	FlatSub->EndSession();
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedEndToEndTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.EndToEndMiniWorld",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedEndToEndTest::RunTest(const FString& Parameters)
{
	FIntegratedHarness H;
	if (!H.Setup(*this, TestSettings(37000)))
	{
		return false;
	}
	FEcoV3RegionContext* A = H.AddRegion(TEXT("RegionA"), 0, FVector(0.0, 0.0, 0.0), 16, 2);
	FEcoV3RegionContext* B = H.AddRegion(TEXT("RegionB"), 1, FVector(0.0, 40000.0, 0.0), 16, 2);
	H.SpawnRegion(*A, 16, 2, 1, 0);
	H.SpawnRegion(*B, 16, 2, 100, 1);

	constexpr int32 Steps = 2000;
	double MaxStalkerCmS = 0.0;
	double MaxChaserCmS = 0.0;
	double MaxDeerCmS = 0.0;
	int32 AllAsleepSteps = 0;
	int32 CorpseMoved = 0;
	int32 OutOfStage = 0;
	TMap<FMassEntityHandle, FVector> CorpseAt;
	for (int32 s = 0; s < Steps; ++s)
	{
		H.DecisionStep();
		H.CoordinatorReconcile();
		bool bAllAsleep = true;
		for (const FMassEntityHandle& E : H.Wolves)
		{
			if (!H.EM->IsEntityValid(E))
			{
				continue;
			}
			const FThreatAgent& Ag = H.EM->GetFragmentDataChecked<FEcoThreatStateFragment>(E).Agent;
			const double Speed = H.EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value.Size2D();
			double& Max = Ag.Spec.Type == EcoThreatV3::EThreatType::Stalker ? MaxStalkerCmS : MaxChaserCmS;
			Max = FMath::Max(Max, Speed);
			bAllAsleep = bAllAsleep && Ag.State.bAsleep;
			OutOfStage += (Ag.State.PosX < 0.0 || Ag.State.PosX > 60.0 || Ag.State.PosY < 0.0 || Ag.State.PosY > 60.0) ? 1 : 0;
		}
		AllAsleepSteps += bAllAsleep ? 1 : 0;
		for (const FMassEntityHandle& E : H.Deer)
		{
			if (!H.EM->IsEntityValid(E))
			{
				continue;
			}
			const FEcoIntegratedV3Fragment& Int = H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);
			const FVector Loc = H.EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
			if (Int.bDead)
			{
				if (const FVector* At = CorpseAt.Find(E))
				{
					CorpseMoved += Loc.Equals(*At, 0.01) ? 0 : 1;
				}
				else
				{
					CorpseAt.Add(E, Loc);
				}
				continue;
			}
			MaxDeerCmS = FMath::Max(MaxDeerCmS, H.EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value.Size2D());
			const EcoWorldV3::FHerbBody& Body = *DeerView(*H.EM, E).Body;
			OutOfStage += (Body.Pos.X < 0.0 || Body.Pos.X > 60.0 || Body.Pos.Y < 0.0 || Body.Pos.Y > 60.0) ? 1 : 0;
		}
	}
	int64 Use[5] = {};
	int64 Caught = 0, Starved = 0, Violations = 0;
	for (const FEcoV3RegionContext* C : {A, B})
	{
		for (int32 b = 0; b < 5; ++b)
		{
			Use[b] += C->Sim.Stats.BehaviorSteps[b];
		}
		Caught += C->Sim.Stats.Caught;
		Starved += C->Sim.Stats.Starved;
		Violations += C->Sim.Stats.MaskViolations;
	}
	AddInfo(FString::Printf(TEXT("%d 스텝: 사용 G %lld F %lld H %lld Fz %lld S %lld | 포획 %lld 굶음 %lld | 지운 개체 %d | 최고 속력 잠행 %.0f 추격 %.0f 사슴 %.0f cm/s | 늑대 모두 잔 스텝 %d | 산 사슴 A %d B %d"),
							Steps, Use[0], Use[1], Use[2], Use[3], Use[4], Caught, Starved, H.Destroyed, MaxStalkerCmS, MaxChaserCmS, MaxDeerCmS,
							AllAsleepSteps, A->AliveDeer, B->AliveDeer));
	for (int32 b = 0; b < 4; ++b)
	{
		TestTrue(FString::Printf(TEXT("행동 %s 가 나온다"), EcoV3Integrated::BehaviorNameKo(b)), Use[b] > 0);
	}
	TestEqual(TEXT("SLEEP 은 나오지 않는다 (R1b 마스크)"), Use[4], static_cast<int64>(0));
	TestTrue(TEXT("늑대가 사슴을 잡는다"), Caught > 0);
	TestEqual(TEXT("마스크 위반"), Violations, static_cast<int64>(0));
	TestTrue(TEXT("죽은 개체를 지워도 스텝이 계속된다"), H.Destroyed > 0 && A->Sim.T == Steps && B->Sim.T == Steps && H.Sub->GetGlobalStep() == Steps);
	TestEqual(TEXT("시체가 움직인 프레임"), CorpseMoved, 0);
	TestEqual(TEXT("무대 밖 자리"), OutOfStage, 0);
	TestTrue(TEXT("잠행형 최고 속력 ≤ 돌진 1350 cm/s"), MaxStalkerCmS <= 1350.0 + 1e-3);
	TestTrue(TEXT("추격형 최고 속력 ≤ 720 cm/s (사슴 뛰기의 0.8배)"), MaxChaserCmS <= 720.0 + 1e-3);
	TestTrue(TEXT("사슴 최고 속력 ≤ 뛰기 900 cm/s"), MaxDeerCmS <= 900.0 + 1e-3);
	TestTrue(TEXT("밤에는 주행성 늑대가 모두 잔다"), AllAsleepSteps > 0);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedSpawnerOverrideTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.SpawnerOverride",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedSpawnerOverrideTest::RunTest(const FString& Parameters)
{
	// 조정자 시작 조건 (조정자 Tick: BeginPlay 뒤 30 초를 넘으면 시간 초과, 0.25 초 미만이거나 스트리밍이 덜 끝났으면 기다림)
	TestFalse(TEXT("0.25 초 전에는 조정자가 시작하지 않는다"), UEcoPolicyV3IntegratedSubsystem::CoordinatorStartsThisFrame(0.24, true));
	TestTrue(TEXT("0.25 초 + 스트리밍 끝 → 이 프레임에 시작"), UEcoPolicyV3IntegratedSubsystem::CoordinatorStartsThisFrame(0.25, true));
	TestFalse(TEXT("스트리밍이 덜 끝났으면 기다린다"), UEcoPolicyV3IntegratedSubsystem::CoordinatorStartsThisFrame(5.0, false));
	TestTrue(TEXT("30 초까지는 시작"), UEcoPolicyV3IntegratedSubsystem::CoordinatorStartsThisFrame(30.0, true));
	TestFalse(TEXT("30 초를 넘으면 조정자는 시간 초과로 실패한다"), UEcoPolicyV3IntegratedSubsystem::CoordinatorStartsThisFrame(30.01, true));

	EcoTest::FScopedTestWorld W;
	UWorld* World = W.World;
	UEcoPolicyV3IntegratedSubsystem* Sub = World ? World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
	if (!TestNotNull(TEXT("UEcoPolicyV3IntegratedSubsystem"), Sub))
	{
		return false;
	}
	// 지역 A (바닥 있음), 지역 B (아직 바닥 없음 — 스트리밍 전 지형 흉내)
	AEcologyRegion* RA = SpawnRegionActor(*World, TEXT("TestOA"), FVector(0.0, 0.0, 0.0), FVector(9000.0, 9000.0, 3000.0));
	AEcologyRegion* RB = SpawnRegionActor(*World, TEXT("TestOB"), FVector(40000.0, 0.0, 0.0), FVector(9000.0, 9000.0, 3000.0));
	AStaticMeshActor* FloorA = SpawnBox(*World, FVector(0.0, 0.0, -50.0), FRotator::ZeroRotator, FVector(200.0, 200.0, 1.0));
	AEcoCreatureIntegrationSpawner* S = World->SpawnActor<AEcoCreatureIntegrationSpawner>();
	if (!TestNotNull(TEXT("지역 A"), RA) || !TestNotNull(TEXT("지역 B"), RB) || !TestNotNull(TEXT("바닥 A"), FloorA)
		|| !TestNotNull(TEXT("조정자"), S))
	{
		return false;
	}
	UMassEntityConfigAsset* TeamDeer = NewObject<UMassEntityConfigAsset>(S, TEXT("TeamDeerStandIn"), RF_Transient);
	UMassEntityConfigAsset* TeamWolf = NewObject<UMassEntityConfigAsset>(S, TEXT("TeamWolfStandIn"), RF_Transient);
	// 팀 값 흉내 (통합 레벨 배치 스크립트와 같은 꼴: 먹이 자리 둘레 몇 m 안 시작 자리, 늑대 1, 상한 64, 이주·웨이브 켬)
	auto ResetTeam = [&]()
	{
		S->HerbivoreConfig = TeamDeer;
		S->WolfConfig = TeamWolf;
		S->Groups.SetNum(2);
		for (int32 g = 0; g < 2; ++g)
		{
			FEcoCreatureSpawnGroup& G = S->Groups[g];
			G = FEcoCreatureSpawnGroup();
			G.RegionId = g == 0 ? FName(TEXT("TestOA")) : FName(TEXT("TestOB"));
			const FVector C = (g == 0 ? RA : RB)->GetActorLocation();
			G.Herbivores = 4;
			G.Wolves = 1;
			G.HerbivoreSpawnPoints = {C + FVector(300.0, 0.0, 0.0), C + FVector(0.0, 300.0, 0.0), C + FVector(-300.0, 0.0, 0.0),
									  C + FVector(0.0, -300.0, 0.0)};
			G.WolfSpawnPoints = {C + FVector(1600.0, 0.0, 0.0)};
			G.Schedule.RegionPopulationLimit = 16;
		}
		S->Migration.bEnabled = true;
		S->bEnableWaves = true;
		S->EnergyDrainPerSecond = 1.0f;
		S->EnergyPerFood = 5.0f;
		S->DaySeconds = 30.0;
		S->NightSeconds = 30.0;
		S->GlobalPopulationLimit = 64;
	};
	// 사슴 40·늑대 2 (40 은 60 단위 무대에서 학습 밀도 하한 38.1 위 — 밀도 경고가 나지 않는다)
	FEcoV3IntegratedSettings Settings = TestSettings(38000);
	Settings.DeerPerRegion = 40;
	// 실패 경로(1~3)가 남기는 오류 기록은 기대한 것이다 — 정해진 횟수만큼 나와야 한다
	AddExpectedErrorPlain(TEXT("무대에서 지면 검사를 통과한 시작 자리가 모자란다"), EAutomationExpectedErrorFlags::Contains, 1);
	AddExpectedErrorPlain(TEXT("의 지역 NoSuchRegion 를 찾지 못했다"), EAutomationExpectedErrorFlags::Contains, 1);
	AddExpectedErrorPlain(TEXT("시작 직전 지면 검사를 통과한 자리가 모자란다"), EAutomationExpectedErrorFlags::Contains, 1);
	AddExpectedErrorPlain(TEXT("조정자를 팀 값으로 되돌렸다"), EAutomationExpectedErrorFlags::Contains, 1);
	AddExpectedErrorPlain(TEXT("통합 v3 모드를 끈다"), EAutomationExpectedErrorFlags::Contains, 1);

	// 조정자 BuildSpawnPositions 와 같은 검사: 적힌 자리를 다시 지면 검사해도 같은 자리이고 지역 안
	auto CountBadPoints = [&](int32& OutTotal) -> int32
	{
		int32 Bad = 0;
		OutTotal = 0;
		for (int32 g = 0; g < S->Groups.Num(); ++g)
		{
			const FEcoCreatureSpawnGroup& G = S->Groups[g];
			const AEcologyRegion* Region = g == 0 ? RA : RB;
			Bad += (G.HerbivoreSpawnPoints.Num() >= G.Herbivores && G.WolfSpawnPoints.Num() >= G.Wolves) ? 0 : 1;
			Bad += G.Schedule.RegionPopulationLimit >= G.Herbivores + G.Wolves ? 0 : 1;
			for (const TArray<FVector>* Pts : {&G.HerbivoreSpawnPoints, &G.WolfSpawnPoints})
			{
				for (const FVector& P : *Pts)
				{
					FVector Again;
					Bad += (EcoCreatureMovement::ProjectSpawnPoint(*World, P, Again) && Again.Equals(P, 1.0) && Region->ContainsPosition(Again)) ? 0 : 1;
				}
			}
			OutTotal += G.Herbivores + G.Wolves;
		}
		return Bad;
	};

	// 1. 스트리밍 없는 조정자, 지역 B 에 지면이 없다 → 실패하고 조정자는 하나도 안 바뀐다 (앞 그룹 A 의 수·자리도 그대로)
	ResetTeam();
	S->bUseHabitatStreaming = false;
	const FSpawnerSnap Team1 = FSpawnerSnap::Take(*S);
	TestFalse(TEXT("1. B 지면 없음 (스트리밍 없음): 바꾸기 실패"), Sub->ApplyToSpawnerForTest(*S, Settings));
	TestTrue(TEXT("1. 실패하면 조정자 속성이 하나도 안 바뀐다 (앞 그룹 A 포함)"), FSpawnerSnap::Take(*S) == Team1);
	TestFalse(TEXT("1. 실패하면 꺼져 있다"), Sub->IsActive());

	// 2. 지역을 못 찾는 그룹 → 실패, 그대로
	ResetTeam();
	S->bUseHabitatStreaming = true;
	S->Groups[1].RegionId = TEXT("NoSuchRegion");
	const FSpawnerSnap Team2 = FSpawnerSnap::Take(*S);
	TestFalse(TEXT("2. 지역 없는 그룹: 바꾸기 실패"), Sub->ApplyToSpawnerForTest(*S, Settings));
	TestTrue(TEXT("2. 실패하면 조정자 속성이 하나도 안 바뀐다"), FSpawnerSnap::Take(*S) == Team2);

	// 3. 스트리밍 조정자: 계획은 힌트라 바꾸기는 된다. 시작 직전 검사에서도 B 지면이 없으면 팀 값으로 되돌리고 끈다
	ResetTeam();
	S->bUseHabitatStreaming = true;
	const FSpawnerSnap Team3 = FSpawnerSnap::Take(*S);
	if (TestTrue(TEXT("3. 스트리밍: 힌트 계획으로 바꾼다"), Sub->ApplyToSpawnerForTest(*S, Settings)))
	{
		TestTrue(TEXT("3. 바꾼 뒤: v3 설정·이주 끔·웨이브 끔·에너지 0·낮밤 60+60·사슴 40 늑대 2"),
				 S->HerbivoreConfig != TeamDeer && S->HerbivoreConfig && S->HerbivoreConfig->FindTrait(UEcoCreatureV3Trait::StaticClass(), true)
					 && !S->Migration.bEnabled && !S->bEnableWaves && S->EnergyDrainPerSecond == 0.0f && S->EnergyPerFood == 0.0f
					 && S->DaySeconds == 60.0 && S->NightSeconds == 60.0 && S->Groups[0].Herbivores == 40 && S->Groups[1].Wolves == 2);
		TestTrue(TEXT("3. 스트리밍 계획은 지면 검사 전 (조정자 시작 직전에 다시)"),
				 Sub->GetPlans().Num() == 2 && !Sub->GetPlans()[0].bGrounded && !Sub->GetPlans()[1].bGrounded);
		TestFalse(TEXT("3. 시작 직전 검사: B 지면 없음 → 실패"), Sub->ValidateSpawnPointsForTest());
		TestTrue(TEXT("3. 실패하면 팀 값으로 되돌린다 (빈 레벨 대신 팀 그대로)"), FSpawnerSnap::Take(*S) == Team3);
		TestFalse(TEXT("3. 되돌린 뒤 꺼져 있다"), Sub->IsActive());
	}

	// 4. 스트리밍 조정자, B 지면이 들어왔다 (스트리밍 완료 흉내) → 시작 직전 검사가 조정자 검사를 통과하는 자리로 덮어쓴다
	AStaticMeshActor* FloorB = SpawnBox(*World, FVector(40000.0, 0.0, -50.0), FRotator::ZeroRotator, FVector(200.0, 200.0, 1.0));
	TestNotNull(TEXT("바닥 B"), FloorB);
	ResetTeam();
	S->bUseHabitatStreaming = true;
	if (TestTrue(TEXT("4. 스트리밍: 바꾼다"), Sub->ApplyToSpawnerForTest(*S, Settings))
		&& TestTrue(TEXT("4. 시작 직전 검사 통과"), Sub->ValidateSpawnPointsForTest()))
	{
		int32 Total = 0;
		TestEqual(TEXT("4. 조정자 지면 검사(BuildSpawnPositions)에 걸리는 자리"), CountBadPoints(Total), 0);
		TestTrue(TEXT("4. 그룹마다 사슴 40·늑대 2"), S->Groups[0].Herbivores == 40 && S->Groups[0].Wolves == 2 && S->Groups[1].Herbivores == 40
														&& S->Groups[1].Wolves == 2);
		TestTrue(TEXT("4. 개체 상한 ≥ 합계"), S->GlobalPopulationLimit >= Total);
		TestTrue(TEXT("4. 검사한 계획은 지면 검사 끝"), Sub->GetPlans().Num() == 2 && Sub->GetPlans()[0].bGrounded && Sub->GetPlans()[1].bGrounded);
		TestTrue(TEXT("4. 켜져 있다"), Sub->IsActive());
	}

	// 5. 스트리밍 없는 조정자, 둘 다 지면 있음 → 바로 지면 검사한 자리 (조정자가 같은 BeginPlay 안에서 시작한다)
	ResetTeam();
	S->bUseHabitatStreaming = false;
	if (TestTrue(TEXT("5. 스트리밍 없음: 바꾼다"), Sub->ApplyToSpawnerForTest(*S, Settings)))
	{
		int32 Total = 0;
		TestEqual(TEXT("5. 조정자 지면 검사에 걸리는 자리"), CountBadPoints(Total), 0);
		TestTrue(TEXT("5. 계획이 바로 지면 검사 끝"), Sub->GetPlans().Num() == 2 && Sub->GetPlans()[0].bGrounded && Sub->GetPlans()[1].bGrounded);
	}
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedBlockedHooksTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.BlockedMoveHooks",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedBlockedHooksTest::RunTest(const FString& Parameters)
{
	constexpr int32 N = 10;

	// (d) 다 통과시키는 콜백 = 콜백 없음 (300 스텝, 비트 단위)
	{
		FHookWorld Ref;
		FHookWorld Hooked;
		Ref.Init(39000, N);
		Hooked.Init(39000, N);
		FFakeMoveBlock Pass;
		Pass.Herbs = &Hooked.Alive;
		Pass.Threats = &Hooked.Threats;
		const EcoWorldV3::FStepHooks Hooks = Pass.Hooks(true, true);
		int64 AliveSteps = 0;
		for (int32 s = 0; s < 300; ++s)
		{
			AliveSteps += static_cast<int64>(Hooked.Alive.size());
			Ref.StepOnce(nullptr);
			Hooked.StepOnce(&Hooks);
		}
		int32 Diff = 0;
		for (int32 i = 0; i < N; ++i)
		{
			const EcoWorldV3::FHerbBody& A = Ref.Mw.Bodies[i];
			const EcoWorldV3::FHerbBody& B = Hooked.Mw.Bodies[i];
			Diff += (A.Pos.X == B.Pos.X && A.Pos.Y == B.Pos.Y && A.Head.X == B.Head.X && A.Head.Y == B.Head.Y && A.Energy == B.Energy
					 && A.DeathCause == B.DeathCause && Ref.Mw.Reps[i].Behavior == Hooked.Mw.Reps[i].Behavior)
						? 0 : 1;
		}
		for (int32 m = 0; m < 2; ++m)
		{
			const EcoThreatV3::FThreatState& A = Ref.Mw.Threats[m].State;
			const EcoThreatV3::FThreatState& B = Hooked.Mw.Threats[m].State;
			Diff += (A.PosX == B.PosX && A.PosY == B.PosY && A.HeadX == B.HeadX && A.HeadY == B.HeadY && A.VelX == B.VelX && A.VelY == B.VelY) ? 0 : 1;
		}
		Diff += (Ref.Mw.W.Stats.Caught == Hooked.Mw.W.Stats.Caught && Ref.Mw.W.Stats.Starved == Hooked.Mw.W.Stats.Starved
				 && Ref.Mw.W.PredEma == Hooked.Mw.W.PredEma && Ref.Mw.W.Food.Total() == Hooked.Mw.W.Food.Total())
					? 0 : 1;
		AddInfo(FString::Printf(TEXT("(d) 300 스텝: 사슴 콜백 %lld, 늑대 콜백 %lld, 포획 %lld"), Pass.HerbCalls, Pass.ThreatCalls,
								Hooked.Mw.W.Stats.Caught));
		TestEqual(TEXT("(d) 다 통과시키는 콜백은 콜백 없음과 비트 단위로 같다"), Diff, 0);
		TestTrue(TEXT("(d) 콜백이 실제로 불렸다"), Pass.HerbCalls > 0 && Pass.ThreatCalls > 0);
		TestTrue(TEXT("(d) 움직인 산 개체만 부른다 (사슴 콜백 ≤ 산 사슴·스텝)"), Pass.HerbCalls <= AliveSteps);
		TestEqual(TEXT("(d) 막힘 0"), Hooked.Mw.W.Stats.BlockedHerbMoves + Hooked.Mw.W.Stats.BlockedThreatMoves, static_cast<int64>(0));
		TestEqual(TEXT("(d) 콜백 색인은 늘 이번 Step 배열 안"), Pass.BadIndex, static_cast<int64>(0));
	}

	// (a)(c) 사슴 하나만 막기: 막힌 사슴만 이동 전 자리, heading 은 가려던 쪽, 다른 사슴 이동은 콜백 없음과 같다
	{
		FHookWorld Probe;
		Probe.Init(39001, N);
		Probe.StepOnce(nullptr);
		int32 Target = -1;
		for (int32 i = 0; i < N && Target < 0; ++i)
		{
			const EcoWorldV3::FHerbBody& B = Probe.Mw.Bodies[i];
			Target = (B.DeathCause == EcoWorldV3::kDeathNone && (B.Pos.X != B.PrevPos.X || B.Pos.Y != B.PrevPos.Y)) ? i : -1;
		}
		if (!TestTrue(TEXT("(a) 이번 스텝에 움직이는 사슴이 있다"), Target >= 0))
		{
			return false;
		}
		FHookWorld Ref;
		FHookWorld Hooked;
		Ref.Init(39001, N);
		Hooked.Init(39001, N);
		FFakeMoveBlock Block;
		Block.Herbs = &Hooked.Alive;
		Block.Threats = &Hooked.Threats;
		Block.BlockHerb = &Hooked.Mw.Bodies[Target];
		const EcoWorldV3::FStepHooks Hooks = Block.Hooks(true, false);
		const EcoWorldV3::FVec2 Start = Hooked.Mw.Bodies[Target].Pos;
		Ref.StepOnce(nullptr);
		Hooked.StepOnce(&Hooks);
		const EcoWorldV3::FHerbBody& B = Hooked.Mw.Bodies[Target];
		const EcoWorldV3::FHerbBody& RB = Ref.Mw.Bodies[Target];
		TestTrue(TEXT("(a) 막힌 사슴은 이동 전 자리 (Pos = PrevPos = 시작)"),
				 B.Pos.X == Start.X && B.Pos.Y == Start.Y && B.PrevPos.X == Start.X && B.PrevPos.Y == Start.Y);
		TestTrue(TEXT("(a) 콜백 없는 세계에서는 그 사슴이 움직였다"), RB.Pos.X != RB.PrevPos.X || RB.Pos.Y != RB.PrevPos.Y);
		TestTrue(TEXT("(a) 막혀도 heading 은 가려던 쪽 (콜백 없는 세계와 같다)"), B.Head.X == RB.Head.X && B.Head.Y == RB.Head.Y);
		int32 Other = 0;
		for (int32 i = 0; i < N; ++i)
		{
			if (i != Target)
			{
				Other += (Hooked.Mw.Bodies[i].Pos.X == Ref.Mw.Bodies[i].Pos.X && Hooked.Mw.Bodies[i].Pos.Y == Ref.Mw.Bodies[i].Pos.Y) ? 0 : 1;
			}
		}
		TestEqual(TEXT("(a) 막히지 않은 사슴의 이동은 콜백 없음과 비트 단위로 같다"), Other, 0);
		TestTrue(TEXT("(c) 막힘 수 = 콜백이 거부한 수 = 1, 늑대 막힘 0"),
				 Hooked.Mw.W.Stats.BlockedHerbMoves == 1 && Block.HerbRejects == 1 && Hooked.Mw.W.Stats.BlockedThreatMoves == 0);
		TestEqual(TEXT("(c) 콜백 색인은 늘 이번 Step 배열 안"), Block.BadIndex, static_cast<int64>(0));
	}

	// (b) 늑대 하나만 막기: 이동 전 자리·변위 0·heading 반전, 늑대 판단(표적·포획)과 다른 늑대는 그대로
	{
		FHookWorld Probe;
		Probe.Init(39002, N);
		Probe.StepOnce(nullptr);
		int32 Target = -1;
		for (int32 m = 0; m < 2 && Target < 0; ++m)
		{
			const FThreatAgent& A = Probe.Mw.Threats[m];
			Target = (A.State.PosX != A.PrevX || A.State.PosY != A.PrevY) ? m : -1;
		}
		if (!TestTrue(TEXT("(b) 이번 스텝에 움직이는 늑대가 있다 (낮, t = 200)"), Target >= 0))
		{
			return false;
		}
		FHookWorld Ref;
		FHookWorld Hooked;
		Ref.Init(39002, N);
		Hooked.Init(39002, N);
		FFakeMoveBlock Block;
		Block.Herbs = &Hooked.Alive;
		Block.Threats = &Hooked.Threats;
		Block.BlockThreat = &Hooked.Mw.Threats[Target];
		const EcoWorldV3::FStepHooks Hooks = Block.Hooks(false, true);
		Ref.StepOnce(nullptr);
		Hooked.StepOnce(&Hooks);
		const FThreatAgent& A = Hooked.Mw.Threats[Target];
		const FThreatAgent& RA = Ref.Mw.Threats[Target];
		TestTrue(TEXT("(b) 막힌 늑대는 이동 전 자리"),
				 A.State.PosX == A.PrevX && A.State.PosY == A.PrevY && A.PrevX == RA.PrevX && A.PrevY == RA.PrevY);
		TestTrue(TEXT("(b) 막힌 늑대의 변위 0"), A.State.VelX == 0.0 && A.State.VelY == 0.0);
		TestTrue(TEXT("(b) 막힌 늑대의 heading 은 반대로 (학습 벽 반사를 흉내 낸 근사)"),
				 A.State.HeadX == -RA.State.HeadX && A.State.HeadY == -RA.State.HeadY && (RA.State.HeadX != 0.0 || RA.State.HeadY != 0.0));
		TestTrue(TEXT("(b) 늑대 판단은 그대로 (표적·사냥·포획 — 포획은 이동 전 위치로 이미 판정)"),
				 A.Last.bHasTarget == RA.Last.bHasTarget && A.Last.Target == RA.Last.Target && A.Last.bHunting == RA.Last.bHunting
					 && A.Last.Caught == RA.Last.Caught && Hooked.Mw.W.Stats.Caught == Ref.Mw.W.Stats.Caught);
		const FThreatAgent& O = Hooked.Mw.Threats[1 - Target];
		const FThreatAgent& RO = Ref.Mw.Threats[1 - Target];
		TestTrue(TEXT("(b) 막히지 않은 늑대는 콜백 없음과 같다"), O.State.PosX == RO.State.PosX && O.State.PosY == RO.State.PosY
																	 && O.State.HeadX == RO.State.HeadX && O.State.HeadY == RO.State.HeadY);
		TestTrue(TEXT("(c) 늑대 막힘 수 = 콜백이 거부한 수 = 1, 사슴 막힘 0"),
				 Hooked.Mw.W.Stats.BlockedThreatMoves == 1 && Block.ThreatRejects == 1 && Hooked.Mw.W.Stats.BlockedHerbMoves == 0);
	}

	// (e) 여러 스텝 내리 막혀도: 막힌 개체는 그 자리에 남고, 판단·에너지·스텝은 계속된다.
	//     막을 사슴 = 콜백 없는 같은 세계에서 120 스텝 동안 가장 많이 움직인 사슴 (먹기 걸음도 움직임이다 — 제자리 먹기만 하는 사슴은 막을 일이 없다)
	{
		int32 Target = -1;
		{
			FHookWorld Probe;
			Probe.Init(39003, N);
			TArray<int32> MovedSteps;
			MovedSteps.Init(0, N);
			for (int32 s = 0; s < 120; ++s)
			{
				Probe.StepOnce(nullptr);
				for (int32 i = 0; i < N; ++i)
				{
					const EcoWorldV3::FHerbBody& B = Probe.Mw.Bodies[i];
					MovedSteps[i] += (B.DeathCause == EcoWorldV3::kDeathNone && (B.Pos.X != B.PrevPos.X || B.Pos.Y != B.PrevPos.Y)) ? 1 : 0;
				}
			}
			for (int32 i = 0; i < N; ++i)
			{
				Target = (MovedSteps[i] > 0 && (Target < 0 || MovedSteps[i] > MovedSteps[Target])) ? i : Target;
			}
		}
		if (!TestTrue(TEXT("(e) 120 스텝 동안 움직이는 사슴이 있다"), Target >= 0))
		{
			return false;
		}
		FHookWorld Hooked;
		Hooked.Init(39003, N);
		FFakeMoveBlock Block;
		Block.Herbs = &Hooked.Alive;
		Block.Threats = &Hooked.Threats;
		Block.BlockHerb = &Hooked.Mw.Bodies[Target];
		Block.BlockThreat = &Hooked.Mw.Threats[0];   // 잠행 늑대
		const EcoWorldV3::FStepHooks Hooks = Block.Hooks(true, true);
		const EcoWorldV3::FVec2 Start0 = Hooked.Mw.Bodies[Target].Pos;
		const double StalkX = Hooked.Mw.Threats[0].State.PosX;
		const double StalkY = Hooked.Mw.Threats[0].State.PosY;
		const double E0 = Hooked.Mw.Bodies[Target].Energy;
		int32 Moved0 = 0;
		int32 StalkerMoved = 0;
		int32 Reads0 = 0;
		bool bNonGraze = false;
		for (int32 s = 0; s < 120; ++s)
		{
			const bool bAlive0 = Hooked.Mw.Bodies[Target].DeathCause == EcoWorldV3::kDeathNone;
			Hooked.StepOnce(&Hooks);
			const EcoWorldV3::FHerbBody& Body0 = Hooked.Mw.Bodies[Target];
			Moved0 += (Body0.Pos.X != Start0.X || Body0.Pos.Y != Start0.Y) ? 1 : 0;
			if (bAlive0)
			{
				Reads0 += Hooked.Mw.Decisions[Target].bCommittedReads ? 1 : 0;
				bNonGraze = bNonGraze || Hooked.Mw.Reps[Target].Behavior != EcoRepertoireV3::kGraze;
			}
			const EcoThreatV3::FThreatState& St = Hooked.Mw.Threats[0].State;
			StalkerMoved += (St.PosX != StalkX || St.PosY != StalkY) ? 1 : 0;
		}
		AddInfo(FString::Printf(TEXT("(e) 막힌 사슴 %d: 요청 읽음 %d 스텝, 먹기 밖 행동 %s, 결과 %s | 막힘 사슴 %lld 늑대 %lld"), Target, Reads0,
								bNonGraze ? TEXT("있음") : TEXT("없음"),
								Hooked.Mw.Bodies[Target].DeathCause == EcoWorldV3::kDeathCaught ? TEXT("잡힘")
								: Hooked.Mw.Bodies[Target].DeathCause == EcoWorldV3::kDeathStarved ? TEXT("굶음") : TEXT("삶"),
								Hooked.Mw.W.Stats.BlockedHerbMoves, Hooked.Mw.W.Stats.BlockedThreatMoves));
		TestEqual(TEXT("(e) 막힌 사슴은 120 스텝 내내 시작 자리 (죽어도 그 자리)"), Moved0, 0);
		TestTrue(TEXT("(e) 막혀도 판단은 계속된다 (요청을 읽는다)"), Reads0 > 0);
		TestTrue(TEXT("(e) 막혀도 에너지는 계속 바뀐다"), Hooked.Mw.Bodies[Target].Energy != E0);
		TestEqual(TEXT("(e) 막힌 늑대도 120 스텝 내내 시작 자리"), StalkerMoved, 0);
		TestTrue(TEXT("(e) 막힘 수 = 콜백이 거부한 수 (둘 다 0 보다 크다)"),
				 Hooked.Mw.W.Stats.BlockedHerbMoves == Block.HerbRejects && Hooked.Mw.W.Stats.BlockedThreatMoves == Block.ThreatRejects
					 && Block.HerbRejects > 0 && Block.ThreatRejects > 0);
		TestEqual(TEXT("(e) 세계 시각은 계속 간다"), Hooked.Mw.W.T, static_cast<int64>(320));
		TestEqual(TEXT("(e) 콜백 색인은 늘 이번 Step 배열 안 (죽은 개체를 빼도)"), Block.BadIndex, static_cast<int64>(0));
	}
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedTerrainTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.TerrainBlocking",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedTerrainTest::RunTest(const FString& Parameters)
{
	// Mass 처리기 + 팀 ConstrainStep (실제 물리): 기운 바닥(X 쪽 5°) 위 무대 60 단위, X = 6000 cm 에 무대 전체를 가르는 벽, 무대를 덮는 지역
	const FEcoV3IntegratedSettings S = TestSettings(40000);
	FIntegratedHarness H;
	if (!H.Setup(*this, S, /*bActivate*/ false))
	{
		return false;
	}
	H.Sub->ActivateForTest(S, /*bTerrain*/ true);
	UWorld& World = *H.Scoped.World;
	constexpr double WallX = 6000.0;
	const FVector Center(6000.0, 6000.0, 0.0);
	AStaticMeshActor* Floor = SpawnBox(World, FVector(6000.0, 6000.0, -50.0), FRotator(5.0, 0.0, 0.0), FVector(200.0, 200.0, 1.0));
	AStaticMeshActor* Wall = SpawnBox(World, FVector(WallX, 6000.0, 0.0), FRotator::ZeroRotator, FVector(1.0, 200.0, 12.0));
	AEcologyRegion* Region = SpawnRegionActor(World, TEXT("TestT"), Center, FVector(6000.0, 6000.0, 3000.0));
	UEcologyWorldSubsystem* Regions = World.GetSubsystem<UEcologyWorldSubsystem>();
	if (!TestNotNull(TEXT("바닥"), Floor) || !TestNotNull(TEXT("벽"), Wall) || !TestNotNull(TEXT("지역"), Region)
		|| !TestNotNull(TEXT("UEcologyWorldSubsystem"), Regions))
	{
		return false;
	}
	Regions->RegisterRegion(Region);
	FEcoV3RegionContext* Ctx = H.AddRegion(TEXT("TestT"), 0, FVector::ZeroVector, 16, 2);

	// 시작 자리: 실제 지면 검사 (벽 둘레 3 m 는 뺀다 — 벽 윗면에 서지 않게)
	FEcoV3StagePlan Plan;
	const bool bPlan = UEcoPolicyV3IntegratedSubsystem::PlanStage(
		TEXT("TestT"), 0, Center, Center, S, 16, 2, true,
		[Region](const FVector& P) { return Region->ContainsPosition(P) && FMath::Abs(P.X - WallX) > 300.0; },
		[&World](const FVector& Hint, FVector& Out) { return EcoCreatureMovement::ProjectSpawnPoint(World, Hint, Out); }, Plan);
	if (!TestTrue(TEXT("기운 바닥에 시작 자리를 다 놓는다"), bPlan))
	{
		return false;
	}
	TArray<int64> DeerIds;
	for (int32 i = 0; i < Plan.DeerPoints.Num(); ++i)
	{
		DeerIds.Add(10 + i);
	}
	H.Spawn(true, TEXT("TestT"), 0, Plan.WolfPoints, {1, 2});
	H.Spawn(false, TEXT("TestT"), 0, Plan.DeerPoints, DeerIds);
	H.Frame(0.001f);   // 입양만

	// 입양 때 벽 어느 쪽인가 (벽은 무대 전체를 가른다 — 아무도 넘을 수 없다)
	TMap<FMassEntityHandle, bool> East;
	TMap<FMassEntityHandle, double> StartZ;
	for (const TArray<FMassEntityHandle>* List : {&H.Deer, &H.Wolves})
	{
		for (const FMassEntityHandle& E : *List)
		{
			const FVector P = H.EM->GetFragmentDataChecked<FTransformFragment>(E).GetTransform().GetLocation();
			East.Add(E, P.X > WallX);
			StartZ.Add(E, P.Z);
		}
	}
	int32 Crossed = 0;
	int32 ZBad = 0;
	double MaxZErr = 0.0;
	double MaxZChange = 0.0;
	auto CheckOne = [&](const FMassEntityHandle E, const FVector& PosCm, double GroundZ)
	{
		Crossed += (PosCm.X > WallX) != East.FindChecked(E) ? 1 : 0;
		double Z = 0.0;
		if (TraceGroundZ(World, FVector(PosCm.X, PosCm.Y, GroundZ), Z))
		{
			MaxZErr = FMath::Max(MaxZErr, FMath::Abs(GroundZ - Z));
			ZBad += FMath::Abs(GroundZ - Z) > 1.0 ? 1 : 0;
		}
		else
		{
			++ZBad;
		}
		MaxZChange = FMath::Max(MaxZChange, FMath::Abs(GroundZ - StartZ.FindChecked(E)));
	};
	constexpr int32 Steps = 400;
	for (int32 s = 0; s < Steps; ++s)
	{
		H.DecisionStep();   // 조정자 흉내(삭제)는 하지 않는다 — 개체 조각의 막힘 수를 끝까지 센다
		for (const FMassEntityHandle& E : H.Deer)
		{
			const FEcoIntegratedV3Fragment& Int = H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);
			if (Int.bDead)
			{
				continue;
			}
			const EcoWorldV3::FHerbBody& B = *DeerView(*H.EM, E).Body;
			CheckOne(E, Ctx->UnitsToCm(B.Pos.X, B.Pos.Y, Int.GroundZ), Int.GroundZ);
		}
		for (const FMassEntityHandle& E : H.Wolves)
		{
			const FEcoIntegratedV3Fragment& Int = H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E);
			const EcoThreatV3::FThreatState& St = H.EM->GetFragmentDataChecked<FEcoThreatStateFragment>(E).Agent.State;
			CheckOne(E, Ctx->UnitsToCm(St.PosX, St.PosY, Int.GroundZ), Int.GroundZ);
		}
	}
	int64 FragHerb = 0;
	int64 FragWolf = 0;
	for (const FMassEntityHandle& E : H.Deer)
	{
		FragHerb += H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E).BlockedMoves;
	}
	for (const FMassEntityHandle& E : H.Wolves)
	{
		FragWolf += H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E).BlockedMoves;
	}
	const EcoWorldV3::FWorldStats& St = Ctx->Sim.Stats;
	AddInfo(FString::Printf(TEXT("%d 스텝: 지형 검사 %lld, 막힘 사슴 %lld (조각 합 %lld) 늑대 %lld (조각 합 %lld), 지면 높이 최대 오차 %.3f cm, 최대 높이 변화 %.0f cm, 포획 %lld"),
							Steps, Ctx->TerrainChecks, St.BlockedHerbMoves, FragHerb, St.BlockedThreatMoves, FragWolf, MaxZErr, MaxZChange, St.Caught));
	TestTrue(TEXT("지형 검사가 돌았다"), Ctx->TerrainChecks > 0);
	TestTrue(TEXT("벽에 실제로 막혔다"), St.BlockedHerbMoves + St.BlockedThreatMoves > 0);
	TestEqual(TEXT("사슴 조각 막힘 수 합 = 세계 사슴 막힘 수 (콜백 색인 = 그 개체)"), FragHerb, St.BlockedHerbMoves);
	TestEqual(TEXT("늑대 조각 막힘 수 합 = 세계 늑대 막힘 수"), FragWolf, St.BlockedThreatMoves);
	TestEqual(TEXT("벽을 넘은 개체·스텝"), Crossed, 0);
	TestEqual(TEXT("지면 높이가 그 개체 자리의 실제 지면과 다른 개체·스텝"), ZBad, 0);
	TestTrue(TEXT("기운 바닥을 따라 지면 높이가 실제로 바뀌었다"), MaxZChange > 5.0);
	TestEqual(TEXT("스텝이 계속됐다"), Ctx->Sim.T, static_cast<int64>(Steps));
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedFeedingTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.FeedingFeedback",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedFeedingTest::RunTest(const FString& Parameters)
{
	namespace R3 = EcoRepertoireV3;

	// --- (a) 엔진 무관: 낮(t = 200), 위협 없음, 먹이 재생 0 — 기록 = 셀에서 덜어 낸 양, 먹은 사슴은 에너지가 오른다 ---
	{
		constexpr int32 N = 6;
		FMiniWorld Mw;
		Mw.Init(MiniConfig(41000, N), N, 0);
		Mw.W.T = 200;
		EcoWorldV3::UpdateDayNight(Mw.W);
		EcoWorldV3::FFoodGrid& F = Mw.W.Food;
		for (double& R : F.Regen)
		{
			R = 0.0;   // 재생 0: 무대 먹이 감소 = 먹은 양 (그대로 맞춰 볼 수 있게)
		}
		int32 Rich = 0;
		for (int32 k = 0; k < static_cast<int32>(F.Cap.size()); ++k)
		{
			Rich = F.Cap[static_cast<size_t>(k)] > F.Cap[static_cast<size_t>(Rich)] ? k : Rich;
		}
		const EcoWorldV3::FVec2 RichPos{(static_cast<double>(Rich % F.Gw) + 0.5) * F.Cell, (static_cast<double>(Rich / F.Gw) + 0.5) * F.Cell};
		std::vector<std::int32_t> Rows;
		for (int32 i = 0; i < N; ++i)
		{
			// 사슴 0 은 가장 풍부한 칸, 나머지는 무대에 흩는다
			const EcoWorldV3::FVec2 P = i == 0 ? RichPos : EcoWorldV3::FVec2{8.0 + 9.0 * i, 50.0 - 7.0 * i};
			EcoWorldV3::AdoptHerb(Mw.W, Mw.AllViews[i], P, {1.0, 0.0}, EcoRepertoireV3::MakeAgentKeyFromStableId(700 + i));
			Rows.push_back(i);
		}
		EcoWorldV3::ObserveAndDecideRows(Mw.W, Mw.AllViews.data(), N, nullptr, 0, Rows.data(), N);
		const double FoodStart = F.Total();

		double MaxBookErr = 0.0;   // |개체 먹은 양 합 − 세계 기록 증가|
		double MaxGridErr = 0.0;   // |무대 먹이 감소 − 세계 기록 증가| (재생 0)
		int32 EatCountBad = 0;     // 세계 '먹은 개체·스텝' 증가 ≠ 먹은 양 > 0 인 사슴 수
		int32 FormulaBad = 0;      // 에너지 ≠ (지난 에너지 − 대사) + 먹은 양 × 0.5 (번식 스텝 제외)
		int32 NonGrazeAte = 0;     // 먹기 밖 행동으로 먹었다 (섭식 배수 0 이라 늘 0)
		int32 Rose = 0;            // 먹기 중, 먹은 몫 > 대사 → 에너지가 올랐다
		int32 NotRose = 0;
		int32 Repro = 0;
		int32 Died = 0;
		double Rich0Gain = 0.0;    // 사슴 0 의 첫 스텝 먹은 몫
		constexpr int32 Steps = 30;
		for (int32 s = 0; s < Steps; ++s)
		{
			const double Total0 = F.Total();
			const double Book0 = Mw.W.Stats.FoodEaten;
			const int64 EatSteps0 = Mw.W.Stats.EatSteps;
			double E0[N];
			for (int32 i = 0; i < N; ++i)
			{
				E0[i] = Mw.Bodies[i].Energy;
			}
			EcoWorldV3::Step(Mw.W, Mw.AllViews.data(), N, nullptr, 0);
			const double BookDelta = Mw.W.Stats.FoodEaten - Book0;
			double Sum = 0.0;
			int32 Ate = 0;
			for (int32 i = 0; i < N; ++i)
			{
				const EcoWorldV3::FHerbBody& Body = Mw.Bodies[i];
				Sum += Body.LastIntake;
				Ate += Body.LastIntake > 0.0 ? 1 : 0;
				Died += Body.DeathCause != EcoWorldV3::kDeathNone ? 1 : 0;
				const double Drain = R3::DrainAmount(Mw.Controls[i].DrainMult);
				const bool bGraze = Mw.Decisions[i].ExecutedBehavior == R3::kGraze;
				NonGrazeAte += (!bGraze && Body.LastIntake > 0.0) ? 1 : 0;
				if (Body.bReproduced)
				{
					++Repro;
					continue;
				}
				FormulaBad += FMath::Abs(Body.Energy - R3::EnergyAfterIntake(E0[i] - Drain, Body.LastIntake)) <= 1e-12 ? 0 : 1;
				// 먹은 몫이 대사보다 분명히 크다 (에너지 1 에 붙은 사슴은 수요 = 대사라 빠진다)
				if (bGraze && Body.LastIntake * R3::kR1bConfig.FoodEnergyPerUnit > Drain + 1e-9)
				{
					Rose += Body.Energy > E0[i] ? 1 : 0;
					NotRose += Body.Energy > E0[i] ? 0 : 1;
				}
			}
			if (s == 0)
			{
				Rich0Gain = Mw.Bodies[0].LastIntake;
			}
			MaxBookErr = FMath::Max(MaxBookErr, FMath::Abs(Sum - BookDelta));
			MaxGridErr = FMath::Max(MaxGridErr, FMath::Abs((Total0 - F.Total()) - BookDelta));
			EatCountBad += (Mw.W.Stats.EatSteps - EatSteps0) == Ate ? 0 : 1;
		}
		AddInfo(FString::Printf(TEXT("(a) %d 스텝: 먹은 양 %.3f (무대 먹이 %.3f → %.3f), 먹은 개체·스텝 %lld, 먹기 %lld, 에너지 오름 %d, 번식 %d, 사슴 0 첫 스텝 먹은 몫 %.4f"),
								Steps, Mw.W.Stats.FoodEaten, FoodStart, F.Total(), Mw.W.Stats.EatSteps,
								Mw.W.Stats.BehaviorSteps[R3::kGraze], Rose, Repro, Rich0Gain));
		TestEqual(TEXT("(a) 위협 없는 낮 30 스텝에 아무도 죽지 않는다"), Died, 0);
		TestTrue(TEXT("(a) 개체 먹은 양 합 = 세계 기록 증가 (스텝마다)"), MaxBookErr <= 1e-12);
		TestTrue(TEXT("(a) 재생 0 이면 무대 먹이 감소 = 세계 기록 증가 (기록은 셀에서 실제로 덜어 낸 양)"), MaxGridErr <= 1e-9);
		TestEqual(TEXT("(a) '먹은 개체·스텝' 기록 = 먹은 양 > 0 인 사슴 수"), EatCountBad, 0);
		TestEqual(TEXT("(a) 에너지 = 지난 에너지 − 대사 + 먹은 양 × 0.5 (기록한 먹은 양이 실제로 에너지에 들어간 몫)"), FormulaBad, 0);
		TestEqual(TEXT("(a) 먹기 밖 행동으로는 먹지 않는다"), NonGrazeAte, 0);
		TestTrue(TEXT("(a) 가장 풍부한 칸의 사슴은 첫 스텝에 한 스텝 최대(0.06 단위)를 먹는다"), FMath::Abs(Rich0Gain - R3::kR1bConfig.FoodEatRate) <= 1e-12);
		TestTrue(TEXT("(a) 먹기 중 먹은 몫이 대사보다 크면 에너지가 오른다 (그런 스텝이 있다)"), Rose > 0);
		TestEqual(TEXT("(a) 먹은 몫이 대사보다 큰데 에너지가 오르지 않은 스텝 (번식 제외)"), NotRose, 0);
		TestTrue(TEXT("(a) 무대 먹이가 줄었다"), F.Total() < FoodStart);
	}

	// --- (b) 사슴 글자 ---
	{
		using EcoV3Integrated::DeerLabel;
		R3::FRepState Rep;
		EcoWorldV3::FHerbBody Body;
		FColor Color;
		Rep.Behavior = R3::kGraze;
		Body.Energy = 0.72;
		Body.LastIntake = 0.06;
		TestEqual(TEXT("(b) 먹은 사슴: 행동 + 에너지 % + 먹은 몫(에너지 %p)"), DeerLabel(Rep, Body, false, Color), FString(TEXT("먹기 72% +3.0")));
		TestTrue(TEXT("(b) 먹기 색은 초록"), Color == FColor(70, 200, 70));
		Body.LastIntake = 0.0;
		TestEqual(TEXT("(b) 못 먹은 스텝은 표시가 없다"), DeerLabel(Rep, Body, false, Color), FString(TEXT("먹기 72%")));
		Body.Energy = 0.10;
		Body.LastIntake = 0.00005;
		TestEqual(TEXT("(b) 아주 적게 먹으면 '+' 만, 15% 아래면 굶주림"), DeerLabel(Rep, Body, false, Color), FString(TEXT("먹기 10% + 굶주림")));
		TestTrue(TEXT("(b) 굶주림은 빨강"), Color == FColor(255, 80, 80));
		Rep.Behavior = R3::kHide;
		Rep.bArrived = true;
		Body.Energy = 0.5;
		Body.LastIntake = 0.0;
		TestEqual(TEXT("(b) 웅크린 사슴, 번식 직후"), DeerLabel(Rep, Body, true, Color), FString(TEXT("숨기(웅크림) 50% 번식")));
		Rep.Behavior = R3::kFlee;
		Rep.bArrived = false;
		Body.Energy = 0.15;
		TestEqual(TEXT("(b) 15% 는 굶주림이 아니다 (아래만)"), DeerLabel(Rep, Body, false, Color), FString(TEXT("도망 15%")));
	}

	// --- (c) Mass: 고리 버퍼·구간 먹은 사슴·에너지 평균·굶주림이 개체 조각과 맞는다. 먹기 중 먹은 사슴은 에너지가 오른다 ---
	FIntegratedHarness H;
	if (!H.Setup(*this, TestSettings(41001)))
	{
		return false;
	}
	FEcoV3RegionContext* Ctx = H.AddRegion(TEXT("TestF"), 0, FVector::ZeroVector, 16, 2);
	double CapSum = 0.0;
	for (const double C : Ctx->Sim.Food.Cap)
	{
		CapSum += C;
	}
	TestTrue(TEXT("(c) 처음 먹이 = 셀 용량 합, 처음 비율 100%"), Ctx->StartFood > 0.0 && Ctx->StartFood == CapSum && Ctx->FoodFraction() == 1.0);
	TestEqual(TEXT("(c) 최근 10 초 창 = 결정 스텝 75 개"), Ctx->RecentEaten.Num(), EcoV3Integrated::kRecentEatSteps);
	H.SpawnRegion(*Ctx, 16, 2, 1, 0);
	H.Frame(0.001f);   // 입양만
	TestTrue(TEXT("(c) 입양 프레임의 에너지 평균 = 0.5 (스텝 없이도 집계)"), FMath::Abs(Ctx->MeanEnergy - 0.5) <= 1e-12 && Ctx->StarvingDeer == 0);

	auto Body = [&H](const FMassEntityHandle E) -> const EcoWorldV3::FHerbBody& { return *DeerView(*H.EM, E).Body; };
	auto IntOf = [&H](const FMassEntityHandle E) -> const FEcoIntegratedV3Fragment& { return H.EM->GetFragmentDataChecked<FEcoIntegratedV3Fragment>(E); };
	TArray<double> Book;
	int32 Rose = 0;
	int32 NotRose = 0;
	constexpr int32 Steps = 150;
	for (int32 s = 0; s < Steps; ++s)
	{
		TMap<FMassEntityHandle, double> PrevE;
		for (const FMassEntityHandle& E : H.Deer)
		{
			if (!IntOf(E).bDead)
			{
				PrevE.Add(E, Body(E).Energy);
			}
		}
		H.DecisionStep();
		Book.Add(Ctx->Sim.Stats.FoodEaten);
		for (const FMassEntityHandle& E : H.Deer)
		{
			const double* E0 = PrevE.Find(E);
			const EcoWorldV3::FHerbBody& Bd = Body(E);
			if (!E0 || IntOf(E).bDead || Bd.bReproduced)
			{
				continue;
			}
			const FEcoBehaviorStateFragment& St = H.EM->GetFragmentDataChecked<FEcoBehaviorStateFragment>(E);
			const double Drain = R3::DrainAmount(H.EM->GetFragmentDataChecked<FEcoControlOutFragment>(E).Control.DrainMult);
			if (St.Decision.ExecutedBehavior == R3::kGraze && Bd.LastIntake * R3::kR1bConfig.FoodEnergyPerUnit > Drain + 1e-9)
			{
				Rose += Bd.Energy > *E0 ? 1 : 0;
				NotRose += Bd.Energy > *E0 ? 0 : 1;
			}
		}
	}
	const double Last75 = Book.Last() - Book[Steps - 1 - EcoV3Integrated::kRecentEatSteps];
	int32 AteMarked = 0;
	int32 Alive = 0;
	int32 Starving = 0;
	double ESum = 0.0;
	for (const FMassEntityHandle& E : H.Deer)
	{
		AteMarked += IntOf(E).AteLogEpoch == Ctx->LogEpoch ? 1 : 0;
		if (!IntOf(E).bDead)
		{
			++Alive;
			ESum += Body(E).Energy;
			Starving += Body(E).Energy < EcoV3Integrated::kStarvingEnergy ? 1 : 0;
		}
	}
	AddInfo(FString::Printf(TEXT("(c) %d 스텝: 먹은 양 %.3f (최근 75 스텝 %.3f), 무대 먹이 처음의 %.1f%%, 먹은 사슴 %d, 산 사슴 %d, 에너지 평균 %.3f, 굶주림 %d, 에너지 오름 %d, 포획 %lld"),
							Steps, Ctx->Sim.Stats.FoodEaten, Ctx->RecentEatenSum(), 100.0 * Ctx->FoodFraction(), Ctx->AteDeerInterval, Alive,
							Ctx->MeanEnergy, Ctx->StarvingDeer, Rose, Ctx->Sim.Stats.Caught));
	TestTrue(TEXT("(c) 최근 10 초 먹은 양 = 기록의 마지막 75 스텝 차이"), FMath::Abs(Ctx->RecentEatenSum() - Last75) <= 1e-9);
	TestTrue(TEXT("(c) 통합 모드에서 실제로 먹는다 (먹은 양 > 0, 무대 먹이 < 100%)"), Ctx->Sim.Stats.FoodEaten > 0.0 && Ctx->FoodFraction() < 1.0 && Ctx->FoodFraction() > 0.0);
	TestTrue(TEXT("(c) 구간에 먹은 사슴 수 = 이 구간 표시가 붙은 사슴 조각 수 (0 보다 크다)"), Ctx->AteDeerInterval == AteMarked && AteMarked > 0);
	TestTrue(TEXT("(c) 에너지 평균·굶주림 수 = 산 사슴 조각"),
			 Alive > 0 && FMath::Abs(Ctx->MeanEnergy - ESum / Alive) <= 1e-12 && Ctx->StarvingDeer == Starving && Ctx->AliveDeer == Alive);
	TestTrue(TEXT("(c) 먹기 중 먹은 몫이 대사보다 크면 에너지가 오른다 (Mass 경로)"), Rose > 0);
	TestEqual(TEXT("(c) 먹은 몫이 대사보다 큰데 에너지가 오르지 않은 개체·스텝 (Mass, 번식 제외)"), NotRose, 0);

	// 기록 줄을 남기면 새 구간: 먹은 사슴 수가 0 이 되고, 다음 스텝에 먹은 사슴만 다시 센다
	Ctx->bReportedLowDensity = true;   // 사슴 16 은 60 단위 무대 밀도 하한 아래 — 시험에서는 경고 줄을 내지 않는다
	const int32 EpochBefore = Ctx->LogEpoch;
	H.Sub->LogContext(*Ctx);
	TestTrue(TEXT("(c) 기록 뒤 구간 번호 + 1, 먹은 사슴 0"), Ctx->LogEpoch == EpochBefore + 1 && Ctx->AteDeerInterval == 0);
	TSet<FMassEntityHandle> SteppedNow;   // 다음 스텝에 들어갈 사슴 = 지금 산 사슴
	for (const FMassEntityHandle& E : H.Deer)
	{
		if (!IntOf(E).bDead)
		{
			SteppedNow.Add(E);
		}
	}
	H.DecisionStep();
	int32 MarkedNow = 0;
	int32 MarkBad = 0;
	for (const FMassEntityHandle& E : H.Deer)
	{
		const bool bMarked = IntOf(E).AteLogEpoch == Ctx->LogEpoch;
		MarkedNow += bMarked ? 1 : 0;
		// 이 구간은 한 스텝뿐: 스텝에 들어간 사슴은 표시 = 이번 스텝 먹은 양 > 0 (그 스텝에 죽었어도), 그 전에 죽은 사슴은 표시가 없다
		MarkBad += SteppedNow.Contains(E) ? (bMarked != (Body(E).LastIntake > 0.0) ? 1 : 0) : (bMarked ? 1 : 0);
	}
	TestTrue(TEXT("(c) 다음 스텝: 구간 먹은 사슴 = 그 스텝에 먹은 사슴 (표시와 먹은 양이 맞는다)"), Ctx->AteDeerInterval == MarkedNow && MarkBad == 0);
	return true;
}

// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoPolicyV3IntegratedGradualNightTest,
	"AdaptiveEcosystem.Policy.V3.Integrated.GradualNight",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoPolicyV3IntegratedGradualNightTest::RunTest(const FString& Parameters)
{
	using EcoV3Integrated::EWolfState;

	// --- 스위치: eco.IntegratedV3.GradualNight 기본 1 → 설정 → 세계 설정 ---
	IConsoleVariable* CVar = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.IntegratedV3.GradualNight"));
	if (!TestNotNull(TEXT("eco.IntegratedV3.GradualNight 콘솔 변수"), CVar))
	{
		return false;
	}
	const int32 Saved = CVar->GetInt();
	TestEqual(TEXT("기본 1 (켬)"), Saved, 1);
	TestTrue(TEXT("설정 기본값도 켬"), FEcoV3IntegratedSettings().bGradualNight);
	TestTrue(TEXT("콘솔 1 → 설정 켬"), FEcoV3IntegratedSettings::FromConsole().bGradualNight);
	CVar->Set(0, ECVF_SetByCode);
	TestFalse(TEXT("콘솔 0 → 설정 끔"), FEcoV3IntegratedSettings::FromConsole().bGradualNight);
	CVar->Set(Saved, ECVF_SetByCode);
	{
		FEcoV3IntegratedSettings S = TestSettings();
		const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(S.StageSizeUnits, 6.0);
		TestTrue(TEXT("켠 설정 → 세계 bRealismNight"), UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, 0, 16, 2, Covers).bRealismNight);
		S.bGradualNight = false;
		TestFalse(TEXT("끈 설정 → 세계 bRealismNight 끔"), UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, 0, 16, 2, Covers).bRealismNight);
	}

	// --- 늑대 글자 ---
	{
		EcoThreatV3::FThreatConfig On;
		On.bRealismNight = true;
		const EcoThreatV3::FThreatConfig Off;
		auto Make = [](int32 Ordinal)
		{
			FThreatAgent A;
			A.Spec = EcoV3Integrated::WolfSpecForOrdinal(Ordinal, 0.8);
			A.State.NightAct = 15;
			return A;
		};
		FColor Color;
		FThreatAgent A = Make(1);
		A.State.bNightSettle = true;
		A.State.NightAct = 6;
		TestEqual(TEXT("눕는 중 글자"), EcoV3Integrated::WolfLabel(A, On, 1.0, Color), FString(TEXT("늑대 눕는 중 (추격형) 걸음 40%")));
		TestTrue(TEXT("눕는 중 상태"), EcoV3Integrated::WolfStateOf(A, On) == EWolfState::Settle);
		A = Make(0);
		A.State.NightAct = 3;
		TestEqual(TEXT("깨는 중 글자"), EcoV3Integrated::WolfLabel(A, On, 0.3, Color), FString(TEXT("늑대 깨는 중 (잠행형) 걸음 20%")));
		A = Make(1);
		A.LastNight.bBlockDeer = true;
		TestEqual(TEXT("사슴 곁 글자"), EcoV3Integrated::WolfLabel(A, On, 0.8, Color), FString(TEXT("늑대 배회 (추격형) · 사슴 곁이라 안 누움")));
		A = Make(1);
		A.Last.bHasTarget = true;
		A.Last.bHunting = true;
		A.State.bNightHunt = true;
		A.LastNight.bBlockHunt = true;
		TestEqual(TEXT("사냥 중 글자"), EcoV3Integrated::WolfLabel(A, On, 1.0, Color), FString(TEXT("늑대 추격 (추격형) · 사냥 중이라 안 누움")));
		A = Make(1);
		TestEqual(TEXT("깜깜해 새 사냥 안 함 글자"), EcoV3Integrated::WolfLabel(A, On, 1.0, Color),
				  FString(TEXT("늑대 배회 (추격형) · 깜깜해 새 사냥 안 함")));
		A.State.bAsleep = true;
		TestEqual(TEXT("잠 글자"), EcoV3Integrated::WolfLabel(A, On, 1.0, Color), FString(TEXT("늑대 잠 (추격형)")));
		A = FThreatAgent();
		A.Spec = EcoV3Integrated::WolfSpecForOrdinal(1, 0.8);   // 끈 판: 밤잠 칸은 기본값(활동도 0)이어도 깨는 중이 아니다
		TestEqual(TEXT("끈 판 글자는 지금 그대로"), EcoV3Integrated::WolfLabel(A, Off, 1.0, Color), FString(TEXT("늑대 배회 (추격형)")));
		TestEqual(TEXT("상태 이름 눕는 중·깨는 중"), FString(EcoV3Integrated::WolfStateNameKo(EWolfState::Settle)) + TEXT("/")
														+ EcoV3Integrated::WolfStateNameKo(EWolfState::Waking),
				  FString(TEXT("눕는 중/깨는 중")));
	}

	// --- Mass: 한 지역 사슴 16·늑대 2 를 해 질 녘 → 밤 → 새벽(1000 스텝) ---
	FIntegratedHarness H;
	if (!H.Setup(*this, TestSettings(38000)))
	{
		return false;
	}
	FEcoV3RegionContext* Ctx = H.AddRegion(TEXT("RegionN"), 0, FVector(0.0, 0.0, 0.0), 16, 2);
	H.SpawnRegion(*Ctx, 16, 2, 1, 0);
	Ctx->bReportedLowDensity = true;   // 시험에서는 밀도 하한 경고 줄을 내지 않는다
	TestTrue(TEXT("통합 세계에 밤잠 점진화가 켜진다"), Ctx->Sim.ThreatCfg.bRealismNight);
	const EcoThreatV3::FThreatConfig& Cfg = Ctx->Sim.ThreatCfg;
	int32 SettleFrames = 0;
	int32 WakingFrames = 0;
	int32 OnsetNear = 0;
	int32 OnsetHunting = 0;
	int32 AwakeDark = 0;
	int32 SleepMoved = 0;
	TSet<int32> Delays;
	TArray<double> OnsetSeconds;
	for (int32 s = 0; s < 1000; ++s)
	{
		H.DecisionStep();
		H.CoordinatorReconcile();
		for (const FMassEntityHandle& E : H.Wolves)
		{
			if (!H.EM->IsEntityValid(E))
			{
				continue;
			}
			const FThreatAgent& A = H.EM->GetFragmentDataChecked<FEcoThreatStateFragment>(E).Agent;
			const EWolfState St = EcoV3Integrated::WolfStateOf(A, Cfg);
			SettleFrames += St == EWolfState::Settle ? 1 : 0;
			WakingFrames += St == EWolfState::Waking ? 1 : 0;
			AwakeDark += (!A.State.bAsleep && Ctx->Sim.Dark >= Cfg.SleepDark) ? 1 : 0;
			Delays.Add(A.State.NightDelay);
			if (A.State.bAsleep && !A.LastNight.bOnset)
			{
				SleepMoved += H.EM->GetFragmentDataChecked<FMassVelocityFragment>(E).Value.Size2D() > 0.0 ? 1 : 0;
			}
			if (A.LastNight.bOnset)
			{
				double MinD = 1e300;
				for (const EcoThreatV3::FPreyView& P : Ctx->Sim.Prey)
				{
					MinD = FMath::Min(MinD, FMath::Sqrt(FMath::Square(P.X - A.State.PosX) + FMath::Square(P.Y - A.State.PosY)));
				}
				OnsetNear += MinD <= Cfg.NightSettleR ? 1 : 0;
				OnsetHunting += A.State.bNightHunt ? 1 : 0;
				OnsetSeconds.Add(Ctx->DarkStartT >= 0 ? static_cast<double>(Ctx->Sim.T - Ctx->DarkStartT) * EcoRepertoireV3::kStepSeconds : -1.0);
			}
		}
	}
	const EcoWorldV3::FWorldStats& Stats = Ctx->Sim.Stats;
	FString Onsets;
	for (const double Sec : OnsetSeconds)
	{
		Onsets += FString::Printf(TEXT(" %.1f"), Sec);
	}
	AddInfo(FString::Printf(TEXT("1000 스텝: 눕기 시작 %lld, 다시 일어남 %lld, 잠듦 %lld (해 진 뒤 초:%s), 깸 %lld, 사슴 곁이라 안 누움 %lld, 사냥 중이라 안 누움 %lld, ")
								TEXT("눕는 중 프레임 %d, 깨는 중 프레임 %d, 어둠 중 깨어 있음 %d, 지연 %d가지, 산 사슴 %d"),
							Stats.NightSettleStarts, Stats.NightSettleAborts, Stats.NightOnsets, *Onsets, Stats.NightWakes, Stats.NightBlockDeer,
							Stats.NightBlockHunt, SettleFrames, WakingFrames, AwakeDark, Delays.Num(), Ctx->AliveDeer));
	TestTrue(TEXT("늑대가 눕고 잠든다 (해 질 녘)"), Stats.NightSettleStarts > 0 && Stats.NightOnsets > 0);
	TestTrue(TEXT("새벽에 깬다"), Stats.NightWakes > 0);
	TestTrue(TEXT("눕는 중·깨는 중 상태가 화면 집계에 잡힌다"), SettleFrames > 0 && WakingFrames > 0);
	TestEqual(TEXT("잠드는 순간 16 m 안에 사슴이 없다"), OnsetNear, 0);
	TestEqual(TEXT("사냥 중에는 잠들지 않는다"), OnsetHunting, 0);
	TestEqual(TEXT("잠든 늑대는 움직이지 않는다 (화면 속도 0)"), SleepMoved, 0);
	TestTrue(TEXT("해 진 뒤 바로 자지 않는다 (어둠 중 깨어 있는 프레임이 있다)"), AwakeDark > 0);
	TestTrue(TEXT("늑대마다 다른 지연 (StableAgentId 해시)"), Delays.Num() >= 2);
	for (const FMassEntityHandle& E : H.Wolves)
	{
		if (H.EM->IsEntityValid(E))
		{
			const FThreatAgent& A = H.EM->GetFragmentDataChecked<FEcoThreatStateFragment>(E).Agent;
			const int64 Id = H.EM->GetFragmentDataChecked<FEcoIdentityFragment>(E).StableAgentId;
			TestEqual(TEXT("지연 = H(606, 세션 시드, StableAgentId) mod 23"), A.State.NightDelay,
					  EcoThreatV3::NightDelayOf(Ctx->Sim.Config.Seed, Id, EcoWorldV3::NightMaxDelay(Ctx->Sim)));
		}
	}
	for (const double Sec : OnsetSeconds)
	{
		// 눕기 시작 업데이트부터 활동도가 R 번 줄어야 잠든다 — 해 진 첫 업데이트에 바로 눕기 시작해도 R - 1 스텝 뒤다
		TestTrue(TEXT("잠듦은 해 진 뒤 (눕기 15 스텝 − 1) 이후다"), Sec >= (Cfg.NightRampSteps - 1) * EcoRepertoireV3::kStepSeconds - 1e-9);
	}
	TestEqual(TEXT("마스크 위반"), Stats.MaskViolations, static_cast<int64>(0));
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

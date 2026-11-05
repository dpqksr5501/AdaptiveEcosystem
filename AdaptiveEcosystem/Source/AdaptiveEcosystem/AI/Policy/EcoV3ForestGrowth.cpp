// 통합 v3 숲 자람 모드 (10-27 사용자 결정 '일단은 모드를 하나 만들어서 해당 모드에서는 숲이 점점 자라게 만들고 그걸 언리얼이 인식하면 그에 맞춰 두뇌 다시 만들어서
// 교체하는걸로 가자', 설계·구현 기록 Docs/RL_Policy/FOREST_GROWTH_MODE.md 1절, LIVE_ADAPT_SPEC.md 5.3).
//
// 레벨 팀이 할 '숲이 자라는 레벨 바뀜'을 흉내 내는 시험 모드다 — 세계 규칙이 아니다. v3 세계 규칙·배수·관측·두뇌·먹이 격자는 바꾸지 않는다.
// 다 자란 나무는 지금 레벨 나무와 똑같은 길로 세계에 들어간다: 꼬리표 EcoV3Trunk 줄기 막이 → 환경 감시 읽기 → 결정 스텝 경계 ApplyEnvChange. 먹이 격자는 그대로다.
//   1. 계획 (지역 세계가 생긴 직후 — TryCreateContexts 끝): 목표 수만큼 자리를 한꺼번에 고른다 (EcoV3ForestGrowth.h PlanSlots — Test.AddTrees 와 같은 규칙).
//   2. 묘목 (프레임 앞 HandlePreActorTick — Mass 처리 밖): 전역 스텝이 단계의 돋음 스텝 이상이면 그 단계의 숲 나무 액터(AEcoV3ForestTree)를 놓는다.
//      묘목은 줄기 막이 충돌이 없고 꼬리표 EcoV3Trunk 도 없어 GatherLevelTrunks 가 세지 않는다 — 세계·사슴·늑대·사람을 막지 않는다 (그리기만).
//   3. 다 자람 (처리기 결정 스텝 경계 ForestStepBoundary — HasPendingEnvChange 바로 앞): 전역 스텝이 단계의 다 자람 스텝이면 그 단계 나무의 줄기 막이를 켜고
//      (BlockAll·꼬리표 EcoV3Trunk), 나무만 곧바로 다시 읽어(PollEnvironment(true, true), 출처 forest_growth) 같은 경계의 ApplyEnvChange 가 넣는다.
//      그래서 실시간 읽기 주기·fps·프레임 나눔과 무관하게 같은 씨면 같은 스텝·같은 원판이다. 그새 생긴 다른 줄기(레벨 팀·Test.AddTrees)와 겹치는 그루는 뺀다.
//   4. 목표에 닿으면 더 돋지 않고 나무는 Play 가 끝날 때까지 그대로 있다 (파이썬 판이 끝까지 돌 수 있게).
// 거부 (아무것도 놓지 않고 까닭 한 줄): 그 지역 v3 무대 없음 · 환경 감시 끔 · 그 지역 장애물 끔·원판 가져옴 · 실행 중 무대 나무가 서 있음.
// 끄면(eco.IntegratedV3.ForestGrowth 0, 기본) 숲 코드는 Play 시작 기록 한 줄 말고는 돌지 않는다 — 액터·강제 읽기·스냅숏 칸이 없다 (지금과 비트 단위로 같다).

#include "EcoV3ForestGrowth.h"

#include "EcoPolicyV3IntegratedSubsystem.h"

#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/GameStateBase.h"
#include "HAL/IConsoleManager.h"
#include "Misc/App.h"
#include "Misc/OutputDevice.h"

#include "EcoV3ForestTree.h"

namespace EcoV3ForestImpl
{
#if !UE_BUILD_SHIPPING
	static TAutoConsoleVariable<int32> CVarForestGrowth(
		TEXT("eco.IntegratedV3.ForestGrowth"),
		0,
		TEXT("통합 v3 숲 자람 모드 (0 = 끔, 기본 — 10-27 시험 모드, 레벨 팀 작업 흉내·세계 규칙 아님). 1 이면 eco.IntegratedV3.ForestRegion 무대에 묘목이 단계마다 돋아 자라고, ")
		TEXT("다 자라는 결정 스텝 경계에서 줄기가 레벨 나무와 같은 길(꼬리표 EcoV3Trunk → 환경 감시)로 세계에 들어간다 (출처 forest_growth). 복제 액터라 리슨·데디케이티드에서도 같다. ")
		TEXT("Play 시작 때 한 번 읽는다. 명령줄 -EcoV3ForestGrowth (또는 =0|1) 는 시작값."),
		ECVF_Default);
	static TAutoConsoleVariable<FString> CVarForestRegion(
		TEXT("eco.IntegratedV3.ForestRegion"), TEXT("Barren"),
		TEXT("숲 자람 지역 (기본 Barren — 메마른 땅이 숲이 되는 이야기). Play 시작 때 읽는다. 명령줄 -EcoV3ForestRegion= 는 시작값."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarForestPerStage(
		TEXT("eco.IntegratedV3.ForestPerStage"), 6, TEXT("숲 자람 한 단계에 돋는 그루 수 (기본 6, 1~64). Play 시작 때 읽는다."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarForestStageSeconds(
		TEXT("eco.IntegratedV3.ForestStageSeconds"), 40.0f, TEXT("숲 자람 단계 간격 (시뮬레이션 초, 기본 40, 1~3600). Play 시작 때 읽는다."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarForestGrowSeconds(
		TEXT("eco.IntegratedV3.ForestGrowSeconds"), 20.0f,
		TEXT("숲 자람 묘목이 다 자라는 데 걸리는 시뮬레이션 초 (기본 20, 1~600). Play 시작 때 읽는다."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarForestTarget(
		TEXT("eco.IntegratedV3.ForestTarget"), 24, TEXT("숲 자람 목표 그루 수 — 여기서 멈춘다 (기본 24, 1~64). Play 시작 때 읽는다."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarForestStartSeconds(
		TEXT("eco.IntegratedV3.ForestStartSeconds"), 30.0f,
		TEXT("숲 자람 첫 단계 시뮬레이션 초 (기본 30 — 사슴이 자리 잡은 뒤, 0~36000). Play 시작 때 읽는다."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarForestSeed(
		TEXT("eco.IntegratedV3.ForestSeed"), -1, TEXT("숲 자람 자리 씨 (-1 = 세션 시드 eco.IntegratedV3.Seed, 기본). 같은 씨면 같은 자리. Play 시작 때 읽는다."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarForestSapling(
		TEXT("eco.IntegratedV3.ForestSapling"), 0.15f,
		TEXT("숲 자람 묘목 처음 크기 몫 (기본 0.15, 0.01~1 — 그리기만, 세계와 무관). Play 시작 때 읽는다."), ECVF_Default);
#endif

	/** 숲 화면 줄 키 (732000~732004 는 두뇌 알림·상태 줄 — EcoV3ForestTree.cpp 와 같다). */
	constexpr uint64 kNoticeKeyForest = 732005;
	/** 다 자란 뒤 화면 줄을 보이는 실시간 초. */
	constexpr double kDoneNoticeSeconds = 10.0;

	double SimSeconds(int64 Step)
	{
		return static_cast<double>(Step) * EcoRepertoireV3::kStepSeconds;
	}

	/** 'F00~F05' (자리 순번 범위). */
	FString SlotRange(const TArray<int32>& Slots)
	{
		if (Slots.IsEmpty())
		{
			return TEXT("없음");
		}
		return Slots.Num() == 1 ? FString::Printf(TEXT("F%02d"), Slots[0]) : FString::Printf(TEXT("F%02d~F%02d"), Slots[0], Slots.Last());
	}

	double ServerTime(const UWorld& World)
	{
		const AGameStateBase* GS = World.GetGameState();
		return GS ? GS->GetServerWorldTimeSeconds() : World.GetTimeSeconds();
	}
}

EcoV3Forest::FSettings UEcoPolicyV3IntegratedSubsystem::ForestSettingsFromConsole()
{
	EcoV3Forest::FSettings S;
#if !UE_BUILD_SHIPPING
	using namespace EcoV3ForestImpl;
	S.bOn = CVarForestGrowth.GetValueOnGameThread() != 0;
	const FString Region = CVarForestRegion.GetValueOnGameThread().TrimStartAndEnd();
	S.Region = Region.IsEmpty() ? FName(TEXT("Barren")) : FName(*Region);
	S.PerStage = CVarForestPerStage.GetValueOnGameThread();
	S.StageSeconds = CVarForestStageSeconds.GetValueOnGameThread();
	S.GrowSeconds = CVarForestGrowSeconds.GetValueOnGameThread();
	S.Target = CVarForestTarget.GetValueOnGameThread();
	S.StartSeconds = CVarForestStartSeconds.GetValueOnGameThread();
	S.Seed = CVarForestSeed.GetValueOnGameThread();
	S.SaplingFrac = CVarForestSapling.GetValueOnGameThread();
#endif
	return EcoV3Forest::Sanitize(S);
}

bool UEcoPolicyV3IntegratedSubsystem::StartForestForTest(const EcoV3Forest::FSettings& InSettings, FString& OutWhy)
{
	EndForest();
	EcoV3Forest::FSettings S = InSettings;
	S.bOn = true;
	return PlanForest(S, OutWhy);
}

bool UEcoPolicyV3IntegratedSubsystem::PlanForest(const EcoV3Forest::FSettings& InSettings, FString& OutWhy)
{
	using namespace EcoV3ForestImpl;
	using EcoRepertoireV3::kUnitCm;
	ForestSettings = EcoV3Forest::Sanitize(InSettings);
	const EcoV3Forest::FSettings& S = ForestSettings;
	bForestOn = false;
	UWorld* World = GetWorld();
	FEcoV3RegionContext* Ctx = FindContext(S.Region);
	auto Refuse = [&OutWhy, &S](const FString& Why)
	{
		OutWhy = Why;
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 숲 자람 | 거부 — %s (%s, 아무것도 놓지 않음)"), *Why, *S.Region.ToString());
		return false;
	};
	if (!World || !bActive)
	{
		return Refuse(TEXT("통합 v3 모드가 돌고 있지 않다"));
	}
	if (!Ctx)
	{
		TArray<FString> Have;
		for (const TUniquePtr<FEcoV3RegionContext>& C : Contexts)
		{
			Have.Add(C->RegionId.ToString());
		}
		return Refuse(FString::Printf(TEXT("지역 %s 의 v3 무대가 없다 — eco.IntegratedV3.ForestRegion 으로 고른다 (있는 지역: %s)"), *S.Region.ToString(),
									  Have.IsEmpty() ? TEXT("없음") : *FString::Join(Have, TEXT("·"))));
	}
	if (!IsEnvWatchEnabled())
	{
		return Refuse(TEXT("환경 감시가 꺼졌다 (eco.IntegratedV3.EnvWatch 0) — 줄기가 세계에 들어가지 않는다 (겉모습만 자라는 숲은 이 모드의 뜻이 아니다)"));
	}
	if (!Ctx->Sim.Config.Obstacles.bEnabled)
	{
		return Refuse(TEXT("그 지역 장애물이 꺼졌다 (eco.IntegratedV3.Obstacles 0) — 줄기가 세계에 들어가지 않는다"));
	}
	if (Ctx->bObstaclesImported)
	{
		return Refuse(TEXT("그 지역 원판을 가져왔다 (eco.IntegratedV3.ObstacleImport, 측정 전용) — 레벨 줄기를 읽지 않는다"));
	}
	if (Ctx->Trees.Num() > 0 && !Ctx->bLevelTrees)
	{
		return Refuse(FString::Printf(TEXT("그 지역에 실행 중 무대 나무 %d 그루가 서 있다 (eco.IntegratedV3.StageTrees 1) — 첫 줄기가 다 자라면 시작 규칙대로 무대 나무가 모두 빠진다"),
									  Ctx->Trees.Num()));
	}
	// 피할 원판: 지금 세계 원판 + 아직 세계에 넣지 않은 줄기 (대기 줄기, 시험용으로 놓은 짝)
	std::vector<double> Avoid = Ctx->Sim.Config.Obstacles.Discs;
	if (PendingEnv.IsValidIndex(Ctx->Index) && PendingEnv[Ctx->Index].bTrees)
	{
		Avoid.insert(Avoid.end(), PendingEnv[Ctx->Index].Trunks.begin(), PendingEnv[Ctx->Index].Trunks.end());
	}
	for (const FEcoV3TestTree& T : TestTrees)
	{
		if (T.Region == S.Region && T.Trunk.IsValid())
		{
			Avoid.insert(Avoid.end(), {T.X, T.Y, T.R});
		}
	}
	// 지면 검사에서 뺄 액터 = 우리 나무·줄기 막이 (줄기 막이 윗면을 땅으로 읽지 않게 — Test.AddTrees 와 같다)
	TArray<AActor*> Ignore;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (It->ActorHasTag(LevelTreeTag()) || It->ActorHasTag(LevelTrunkTag()))
		{
			Ignore.Add(*It);
		}
	}
	const int64 Seed = S.Seed >= 0 ? S.Seed : Settings.Seed;
	const FVector Origin = Ctx->OriginCm;
	int32 Missing = 0;
	EcoV3Forest::PlanSlots(
		S.Target, Ctx->SizeUnits, Ctx->Sim.Config.Covers, Avoid, EcoV3Forest::RngState(Seed, Ctx->RegionRuntimeIndex),
		[](double X, double Y, double Scale, double Yaw) { return UEcoPolicyV3IntegratedSubsystem::MakeLevelTree(X, Y, Scale, Yaw); },
		[World, &Origin, &Ignore](const EcoTreeLayoutV3::FTree& T, double& OutMinZ)
		{
			double MaxZ = 0.0;
			return UEcoPolicyV3IntegratedSubsystem::GroundStageTree(*World, Origin, T, OutMinZ, MaxZ, &Ignore);
		},
		ForestSlots, Missing);
	if (ForestSlots.IsEmpty())
	{
		return Refuse(FString::Printf(TEXT("자리를 하나도 못 찾았다 (목표 %d, 은신처·다른 원판·벽·땅 조건)"), S.Target));
	}
	ForestCtx = Ctx->Index;
	ForestState.Init(0, ForestSlots.Num());
	ForestActors.Init(nullptr, ForestSlots.Num());
	ForestNextSprout = 0;
	ForestNextMature = 0;
	ForestDoneRealTime = -1.0;
	NextForestNotice = 0.0;
	bForestOn = true;
	OutWhy.Empty();

	const int32 K = EcoV3Forest::NumStages(S, ForestSlots.Num());
	FString Schedule;
	for (int32 k = 0; k < K; ++k)
	{
		const int32 Num = FMath::Min(S.PerStage, ForestSlots.Num() - k * S.PerStage);
		Schedule += FString::Printf(TEXT("%s%d: 묘목 %.1f초(스텝 %lld)·다 자람 %.1f초(스텝 %lld) %d 그루"), k == 0 ? TEXT("") : TEXT(" · "), k + 1,
									SimSeconds(EcoV3Forest::SproutStep(S, k)), static_cast<long long>(EcoV3Forest::SproutStep(S, k)),
									SimSeconds(EcoV3Forest::MatureStep(S, k)), static_cast<long long>(EcoV3Forest::MatureStep(S, k)), Num);
	}
	FString Spots;
	for (const EcoV3Forest::FSlot& Sl : ForestSlots)
	{
		Spots += FString::Printf(TEXT(" · F%02d (%.3f, %.3f) r %.4f 크기 %.3f 방위 %.1f 땅 %.1f"), Sl.Index, Sl.Tree.X, Sl.Tree.Y, Sl.Tree.R, Sl.Tree.Scale, Sl.Tree.YawDeg,
								 Sl.GroundMinZ);
	}
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] 숲 자람 | 켬 (시험 모드 — 레벨 팀 작업 흉내, 세계 규칙 아님) — %s %d 그루 × %.0f초, 묘목 %.0f초, 목표 %d, 첫 단계 %.0f초, 씨 %lld | 자리 %d/%d%s | ")
			   TEXT("단계 %s | 자리:%s"),
		   *S.Region.ToString(), S.PerStage, S.StageSeconds, S.GrowSeconds, S.Target, S.StartSeconds, static_cast<long long>(Seed), ForestSlots.Num(), S.Target,
		   Missing > 0 ? *FString::Printf(TEXT(" (못 찾음 %d — 목표를 그만큼 줄임)"), Missing) : TEXT(""), *Schedule, *Spots);
	if (ForestSlots.Num() < BigChangeConfig().BigTrees)
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 숲 자람 | 놓을 수 %d < eco.IntegratedV3.BigTrees %d — 숲 자람만으로는 '큰 변화만' 다시 배우기 스냅숏이 나오지 않는다"),
			   ForestSlots.Num(), BigChangeConfig().BigTrees);
	}
	return true;
}

bool UEcoPolicyV3IntegratedSubsystem::SpawnForestTree(int32 Slot)
{
	UWorld* World = GetWorld();
	FEcoV3RegionContext* Ctx = GetContext(ForestCtx);
	if (!World || !Ctx || !ForestSlots.IsValidIndex(Slot))
	{
		return false;
	}
	if (ForestActors[Slot].IsValid())
	{
		return true;
	}
	const EcoV3Forest::FSlot& Sl = ForestSlots[Slot];
	FActorSpawnParameters Params;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	Params.ObjectFlags |= RF_Transient;   // 저장하지 않는다
	AEcoV3ForestTree* A = World->SpawnActor<AEcoV3ForestTree>(AEcoV3ForestTree::StaticClass(), FTransform::Identity, Params);
	if (!A)
	{
		return false;
	}
	FEcoV3ForestPlan P;
	P.OriginX = Ctx->OriginCm.X;
	P.OriginY = Ctx->OriginCm.Y;
	P.OriginZ = Ctx->OriginCm.Z;
	P.X = Sl.Tree.X;
	P.Y = Sl.Tree.Y;
	P.R = Sl.Tree.R;
	P.YawDeg = Sl.Tree.YawDeg;
	P.Scale = Sl.Tree.Scale;
	P.GroundMinZ = Sl.GroundMinZ;
	P.GrowStartServerTime = EcoV3ForestImpl::ServerTime(*World);
	P.GrowSeconds = static_cast<float>(ForestSettings.GrowSeconds);
	P.SaplingFrac = static_cast<float>(ForestSettings.SaplingFrac);
	P.RegionId = ForestSettings.Region;
	P.Index = Sl.Index;
	P.Target = ForestSlots.Num();
	A->InitPlan(P);
	ForestActors[Slot] = A;
	return true;
}

void UEcoPolicyV3IntegratedSubsystem::ForestPreActorTick()
{
	using namespace EcoV3ForestImpl;
	if (!bForestOn)
	{
		return;
	}
	const EcoV3Forest::FSettings& S = ForestSettings;
	const int32 K = EcoV3Forest::NumStages(S, ForestSlots.Num());
	while (ForestNextSprout < K && GlobalT >= EcoV3Forest::SproutStep(S, ForestNextSprout))
	{
		const int32 Stage = ForestNextSprout++;
		if (Stage < ForestNextMature)
		{
			continue;   // 다 자람 경계가 먼저 왔다 (그때 놓았다)
		}
		TArray<int32> Placed;
		for (int32 i = 0; i < ForestSlots.Num(); ++i)
		{
			if (EcoV3Forest::StageOfSlot(S, i) == Stage && ForestState[i] == 0 && SpawnForestTree(i))
			{
				ForestState[i] = 1;
				Placed.Add(i);
			}
		}
		const int64 At = EcoV3Forest::SproutStep(S, Stage);
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 숲 자람 | %.1f초 (전역 스텝 %lld) 묘목 %d 돋음 (%s) — 놓은 때 전역 스텝 %lld · 다 자람 %.1f초 (전역 스텝 %lld) · 묘목은 아무것도 막지 않음"),
			   SimSeconds(At), static_cast<long long>(At), Placed.Num(), *SlotRange(Placed), static_cast<long long>(GlobalT),
			   SimSeconds(EcoV3Forest::MatureStep(S, Stage)), static_cast<long long>(EcoV3Forest::MatureStep(S, Stage)));
	}
	DrawForestNotice();
}

void UEcoPolicyV3IntegratedSubsystem::ForestStepBoundary()
{
	using namespace EcoV3ForestImpl;
	using EcoRepertoireV3::kUnitCm;
	if (!bForestOn)
	{
		return;
	}
	const EcoV3Forest::FSettings& S = ForestSettings;
	const int32 K = EcoV3Forest::NumStages(S, ForestSlots.Num());
	UWorld* World = GetWorld();
	const FEcoV3RegionContext* Ctx = GetContext(ForestCtx);
	if (!World || !Ctx || ForestNextMature >= K || GlobalT < EcoV3Forest::MatureStep(S, ForestNextMature))
	{
		return;
	}
	bool bAny = false;
	while (ForestNextMature < K && GlobalT >= EcoV3Forest::MatureStep(S, ForestNextMature))
	{
		const int32 Stage = ForestNextMature++;
		// 그새 생긴 다른 줄기 (레벨 팀·Test.AddTrees — 지금 꼬리표 줄기 막이)와 겹치면 (중심 거리 < 두 반지름 합) 그 그루는 뺀다
		TArray<FVector> TrunksCm;
		GatherLevelTrunks(*World, TrunksCm);
		TArray<int32> Grown;
		TArray<int32> Dropped;
		for (int32 i = 0; i < ForestSlots.Num(); ++i)
		{
			if (EcoV3Forest::StageOfSlot(S, i) != Stage || ForestState[i] >= 2)
			{
				continue;
			}
			const EcoTreeLayoutV3::FTree& T = ForestSlots[i].Tree;
			bool bOverlap = false;
			for (const FVector& Tc : TrunksCm)
			{
				const double X = (Tc.X - Ctx->OriginCm.X) / kUnitCm;
				const double Y = (Tc.Y - Ctx->OriginCm.Y) / kUnitCm;
				bOverlap = bOverlap || FMath::Sqrt(FMath::Square(X - T.X) + FMath::Square(Y - T.Y)) < T.R + Tc.Z / kUnitCm;
			}
			if (bOverlap)
			{
				if (AActor* A = ForestActors[i].Get())
				{
					A->Destroy();
				}
				ForestActors[i] = nullptr;
				ForestState[i] = 3;
				Dropped.Add(i);
				UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 숲 자람 | %s F%02d 자리 겹침 — 뺌 (그새 생긴 다른 줄기와 겹친다)"), *S.Region.ToString(), i);
				continue;
			}
			// 묘목이 아직 없으면 (첫 단계 전에 다 자람 — 아주 짧은 자람 초·긴 프레임) 지금 놓는다. 세계에 닿는 값은 계획에서 정해져 같다
			if (!ForestActors[i].IsValid() && !SpawnForestTree(i))
			{
				ForestState[i] = 3;
				Dropped.Add(i);
				UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 숲 자람 | %s F%02d 액터를 놓지 못했다 — 뺌"), *S.Region.ToString(), i);
				continue;
			}
			if (AEcoV3ForestTree* A = Cast<AEcoV3ForestTree>(ForestActors[i].Get()))
			{
				A->SetMature();
			}
			ForestState[i] = 2;
			Grown.Add(i);
		}
		const int64 At = EcoV3Forest::MatureStep(S, Stage);
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 숲 자람 | %.1f초 (전역 스텝 %lld) %d 그루 다 자람 (%s) → 세계에 넣음 (출처 forest_growth)%s · %s 나무 %d/%d"), SimSeconds(At),
			   static_cast<long long>(GlobalT), Grown.Num(), *SlotRange(Grown),
			   Dropped.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" · 뺌 %d (%s)"), Dropped.Num(), *SlotRange(Dropped)), *S.Region.ToString(), ForestMatureCount(),
			   ForestSlots.Num());
		bAny = true;
	}
	if (ForestNextMature >= K)
	{
		ForestDoneRealTime = FPlatformTime::Seconds();
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 숲 자람 | 다 자랐다 — %s 나무 %d/%d (뺌 %d) · 더 돋지 않음, Play 끝까지 그대로"), *S.Region.ToString(), ForestMatureCount(),
			   ForestSlots.Num(), ForestSlots.Num() - ForestMatureCount() - ForestSaplingCount());
	}
	if (bAny)
	{
		// 나무만 곧바로 다시 읽기 (출처 forest_growth) — 같은 경계에서 처리기가 ApplyEnvChange 로 넣는다
		PollEnvironment(/*bForce*/ true, /*bTreesOnly*/ true);
	}
}

bool UEcoPolicyV3IntegratedSubsystem::IsForestGrowing() const
{
	return bForestOn && ForestNextMature < EcoV3Forest::NumStages(ForestSettings, ForestSlots.Num());
}

int32 UEcoPolicyV3IntegratedSubsystem::ForestMatureCount() const
{
	int32 N = 0;
	for (const uint8 St : ForestState)
	{
		N += St == 2 ? 1 : 0;
	}
	return N;
}

int32 UEcoPolicyV3IntegratedSubsystem::ForestSaplingCount() const
{
	int32 N = 0;
	for (const uint8 St : ForestState)
	{
		N += St == 1 ? 1 : 0;
	}
	return N;
}

int64 UEcoPolicyV3IntegratedSubsystem::ForestNextMatureStep() const
{
	return IsForestGrowing() ? EcoV3Forest::MatureStep(ForestSettings, ForestNextMature) : -1;
}

AActor* UEcoPolicyV3IntegratedSubsystem::GetForestActor(int32 Slot) const
{
	return ForestActors.IsValidIndex(Slot) ? ForestActors[Slot].Get() : nullptr;
}

void UEcoPolicyV3IntegratedSubsystem::DrawForestNotice()
{
	using namespace EcoV3ForestImpl;
	const UWorld* World = GetWorld();
	const double Now = FPlatformTime::Seconds();
	if (!bForestOn || Now < NextForestNotice || !EcoV3Brain::NoticeEnabled() || !GEngine || !FApp::CanEverRender() || (World && World->GetNetMode() == NM_Client))
	{
		return;
	}
	NextForestNotice = Now + 1.0;
	const FString Region = EcoV3BigChange::RegionNameKo(ForestSettings.Region);
	FString Text;
	if (IsForestGrowing())
	{
		const int32 Saplings = ForestSaplingCount();
		Text = Saplings > 0 ? FString::Printf(TEXT("숲이 자라는 중 — %s 나무 %d/%d (묘목 %d 그루 자라는 중)"), *Region, ForestMatureCount(), ForestSlots.Num(), Saplings)
							: FString::Printf(TEXT("숲이 자라는 중 — %s 나무 %d/%d (다음 묘목 %.0f초)"), *Region, ForestMatureCount(), ForestSlots.Num(),
											  SimSeconds(EcoV3Forest::SproutStep(ForestSettings, FMath::Max(ForestNextSprout, ForestNextMature))));
	}
	else if (ForestDoneRealTime >= 0.0 && Now - ForestDoneRealTime <= kDoneNoticeSeconds)
	{
		Text = FString::Printf(TEXT("숲이 다 자랐다 — %s 나무 %d/%d"), *Region, ForestMatureCount(), ForestSlots.Num());
	}
	if (!Text.IsEmpty())
	{
		GEngine->AddOnScreenDebugMessage(kNoticeKeyForest, 1.5f, FColor(150, 230, 140), Text);
	}
}

void UEcoPolicyV3IntegratedSubsystem::EndForest()
{
	bForestOn = false;
	ForestCtx = INDEX_NONE;
	ForestSlots.Reset();
	ForestState.Reset();
	ForestActors.Reset();
	ForestNextSprout = 0;
	ForestNextMature = 0;
	ForestDoneRealTime = -1.0;
	NextForestNotice = 0.0;
}

TArray<FString> UEcoPolicyV3IntegratedSubsystem::ForestInfoLines() const
{
	using namespace EcoV3ForestImpl;
	TArray<FString> Lines;
	const EcoV3Forest::FSettings& S = ForestSettings;
	if (!bForestOn)
	{
		Lines.Add(FString::Printf(TEXT("[EcoV3I] 숲 자람 | 끔 (eco.IntegratedV3.ForestGrowth %d — Play 시작 때 읽는다, 또는 거부됨)"), S.bOn ? 1 : 0));
		return Lines;
	}
	const int32 K = EcoV3Forest::NumStages(S, ForestSlots.Num());
	Lines.Add(FString::Printf(TEXT("[EcoV3I] 숲 자람 | %s · 목표 %d · 놓음 %d · 다 자람 %d · 묘목 %d · 단계 %d/%d 다 자람 · 다음 다 자람 전역 스텝 %lld · 지금 %.1f초 (전역 스텝 %lld)"),
							  *S.Region.ToString(), S.Target, ForestSlots.Num(), ForestMatureCount(), ForestSaplingCount(), ForestNextMature, K,
							  static_cast<long long>(ForestNextMatureStep()), SimSeconds(GlobalT), static_cast<long long>(GlobalT)));
	for (int32 i = 0; i < ForestSlots.Num(); ++i)
	{
		const EcoV3Forest::FSlot& Sl = ForestSlots[i];
		const AEcoV3ForestTree* A = Cast<AEcoV3ForestTree>(ForestActors[i].Get());
		static const TCHAR* const StateNames[4] = {TEXT("계획"), TEXT("묘목"), TEXT("다 자람"), TEXT("뺌")};
		Lines.Add(FString::Printf(TEXT("[EcoV3I] 숲 F%02d | 단계 %d · %s · (%.3f, %.3f) r %.4f · 액터 %s · 다 자람 %s · 줄기 충돌 %s · 줄기 변환 지문 %016llx"), i,
								  EcoV3Forest::StageOfSlot(S, i) + 1, StateNames[FMath::Clamp<int32>(ForestState[i], 0, 3)], Sl.Tree.X, Sl.Tree.Y, Sl.Tree.R,
								  A ? TEXT("있음") : TEXT("없음"), A && A->IsMature() ? TEXT("참") : TEXT("거짓"), A && A->TrunkCollisionOn() ? TEXT("켬") : TEXT("끔"),
								  static_cast<unsigned long long>(A ? A->TrunkHash() : 0)));
	}
	return Lines;
}

#if !UE_BUILD_SHIPPING
namespace EcoV3ForestImpl
{
	void CmdForestInfo(const TArray<FString>& Args, UWorld* World, FOutputDevice& Ar)
	{
		if (!World)
		{
			Ar.Log(TEXT("[EcoV3I] 월드가 없다"));
			return;
		}
		if (World->GetNetMode() != NM_Client)
		{
			const UEcoPolicyV3IntegratedSubsystem* Sub = World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
			if (!Sub || !Sub->IsActive())
			{
				Ar.Log(TEXT("[EcoV3I] 통합 v3 모드가 돌고 있지 않다"));
				return;
			}
			for (const FString& Line : Sub->ForestInfoLines())
			{
				Ar.Log(Line);   // 예약 명령(eco.IntegratedV3.Test.At)이면 Ar = GLog — 기록에 한 번 (EnvInfo 와 같다)
			}
			return;
		}
		// 클라이언트: 복제된 숲 나무 액터마다 (서버 줄과 견줄 값 — 다 자람·줄기 충돌·줄기 변환 지문)
		int32 Seen = 0;
		int32 Mature = 0;
		TArray<FString> Lines;
		for (TActorIterator<AEcoV3ForestTree> It(World); It; ++It)
		{
			const FEcoV3ForestPlan& P = It->GetPlan();
			++Seen;
			Mature += It->IsMature() ? 1 : 0;
			Lines.Add(FString::Printf(TEXT("[EcoV3I] 숲 F%02d (클라이언트) | %s (%.3f, %.3f) · 다 자람 %s · 줄기 충돌 %s · 줄기 변환 지문 %016llx"), P.Index, *P.RegionId.ToString(), P.X,
									  P.Y, It->IsMature() ? TEXT("참") : TEXT("거짓"), It->TrunkCollisionOn() ? TEXT("켬") : TEXT("끔"),
									  static_cast<unsigned long long>(It->TrunkHash())));
		}
		Lines.Sort();
		Lines.Insert(FString::Printf(TEXT("[EcoV3I] 숲 자람 (클라이언트) | 받은 숲 나무 %d · 다 자람 %d"), Seen, Mature), 0);
		for (const FString& Line : Lines)
		{
			Ar.Log(Line);
		}
	}

	FAutoConsoleCommandWithWorldArgsAndOutputDevice CmdForestInfoReg(
		TEXT("eco.IntegratedV3.ForestInfo"),
		TEXT("통합 v3 숲 자람 모드 보기: 서버·단독 = 계획·단계·다 자람 스텝·자리·액터, 클라이언트 = 받은 숲 나무 액터마다 다 자람·줄기 충돌·줄기 변환 지문 (서버와 견줌, EcoV3ForestGrowth.cpp)."),
		FConsoleCommandWithWorldArgsAndOutputDeviceDelegate::CreateStatic(&CmdForestInfo));
}
#endif

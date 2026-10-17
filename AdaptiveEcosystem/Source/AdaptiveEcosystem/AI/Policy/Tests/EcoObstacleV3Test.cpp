// v3 야생 2단계 3 자동화 시험 — C++ 세로 장애물(EcoThreatModel.h ObstacleSlide·SightBlocked·Step, EcoWorldV3.h FObstacleConfig·ObstaclePushOut·
// FFoodGrid::ApplyObstacleFood·C1·C2·E)을 파이썬(env_v2/world.py obstacles, configs/v3_wild2_obstacle_mirror.yaml)과 대조하고, 통합 모드의 레벨 읽기
// (EcoPolicyV3IntegratedSubsystem::ScanStageObstacles — 읽기만)를 시험한다 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 6절).
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.Obstacle"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 골든은 `ObstacleGoldenVectorsV3.h` (herbivore_rl/export_golden_v3_obstacle.py)이고, 검사 본문은 `ObstacleGoldenCheckV3.h` 다. 같은 검사를
// herbivore_rl/tests/test_wild2_obstacle.py 가 g++ 로도 돌린다(tests/cpp/obstacle_v3_main.cpp).
//
// 묶음:
//   Obstacle.Golden             설정(기본 끔·계수 = 거울 설정), 미끄러짐·시선·먹이·밀어내기·한 스텝 장면(PackPeek → PackGoals → Step) 비트 단위, 끄면 그대로
//   Obstacle.Run                기준 루프 900 스텝 (무대 60, 사슴 64, 늑대 4, 원판 = 거울 배치 367): 사슴·늑대가 원판(r + 몸) 안에 들지 않고 무대 밖에 나가지 않음,
//                               부딪힘이 있다, 같은 시드 = 같은 비트, 끄면(원판을 넣고 켬 칸만 끔) 원판 없는 세계와 비트 단위로 같다
//   Obstacle.LevelScan          시험 월드에 메시를 놓고 읽기: 충돌하는 상자 = 원판(가로 반지름·무대 단위), 충돌 없음·작음·낮음·은신처 원 안은 뺀다,
//                               인스턴스 메시는 인스턴스마다, 읽기 전후로 액터·컴포넌트가 그대로다, JSON 내보내기 → 가져오기가 같은 원판
//   Obstacle.IntegratedDefaults 통합 기본값: 장애물 켬(eco.IntegratedV3.Obstacles 1), 내보내기·가져오기 경로 없음, 세계 설정 켬 칸 — 원판이 없으면 세계 그대로

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "EcoTestWorld.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Engine/StaticMeshActor.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "ObstacleGoldenCheckV3.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoObstacleV3Test
{
	using EcoWorldV3::ObstacleCheck::FReport;

	void Report(FAutomationTestBase& Test, const TCHAR* What, const FReport& R)
	{
		Test.AddInfo(FString::Printf(TEXT("%s: 사례 %d, 어긋남 %d (처음 사례 %d 칸 %d), 셈 %d·%d·%d"), What, R.Cases, R.Failures, R.FirstCase, R.FirstField,
									 R.Count0, R.Count1, R.Count2));
		Test.TestTrue(*FString::Printf(TEXT("%s: 파이썬과 비트 단위로 같다"), What), R.Passed());
	}

	/** 기준 루프 세계: 무대 60, 사슴 64, 늑대 잠행 2·추격 2, 은신처 4 (반경 6) 안전·몸 여유 0.5, 포만·제자리 식사, 원판 = 골든 거울 배치. */
	EcoWorldV3::FWorldConfig RunConfig(bool bObstacles, bool bWithDiscs)
	{
		namespace G = EcoWorldV3::GoldenObstacle;
		EcoWorldV3::FWorldConfig C;
		C.WorldSize = G::kMirrorSize;
		C.Seed = 20003;
		C.NumHerbivores = 64;
		C.NumStalkers = 2;
		C.NumChasers = 2;
		C.NumRanged = 0;
		C.NumNocturnal = 0;
		C.Covers = EcoWorldV3::QuadCovers(C.WorldSize, 6.0);
		C.bShelterSafe = true;
		C.ShelterWolfMargin = 0.5;
		C.WildSatiation.bEnabled = true;
		C.PredEatCdOverride = 38;
		C.bEatInPlace = true;
		C.PackHunt.bEnabled = true;
		C.Obstacles.bEnabled = bObstacles;
		if (bWithDiscs)
		{
			const int32 Start = G::kSetIndex[0];
			const int32 Num = G::kSetIndex[1];
			C.Obstacles.Discs.assign(G::kSetDiscs + 3 * Start, G::kSetDiscs + 3 * (Start + Num));
		}
		return C;
	}

	bool SameBodies(const EcoWorldV3::FReferenceWorld& A, const EcoWorldV3::FReferenceWorld& B)
	{
		bool bSame = A.World.Rng.State == B.World.Rng.State;
		for (size_t i = 0; i < A.Bodies.size() && bSame; ++i)
		{
			bSame = A.Bodies[i].Pos.X == B.Bodies[i].Pos.X && A.Bodies[i].Pos.Y == B.Bodies[i].Pos.Y && A.Bodies[i].Energy == B.Bodies[i].Energy
					&& A.Reps[i].Behavior == B.Reps[i].Behavior;
		}
		for (size_t m = 0; m < A.Threats.size() && bSame; ++m)
		{
			bSame = A.Threats[m].State.PosX == B.Threats[m].State.PosX && A.Threats[m].State.PosY == B.Threats[m].State.PosY;
		}
		for (size_t k = 0; k < A.World.Food.Food.size() && bSame; ++k)
		{
			bSame = A.World.Food.Food[k] == B.World.Food.Food[k];
		}
		return bSame;
	}

	AStaticMeshActor* SpawnBox(UWorld* World, const FVector& At, const FVector& Scale, bool bCollide)
	{
		AStaticMeshActor* A = World->SpawnActor<AStaticMeshActor>(At, FRotator::ZeroRotator);
		A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		A->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		A->SetActorScale3D(Scale);
		A->GetStaticMeshComponent()->SetCollisionProfileName(bCollide ? TEXT("BlockAll") : TEXT("NoCollision"));
		return A;
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObstacleV3GoldenTest,
	"AdaptiveEcosystem.Policy.V3.Obstacle.Golden",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObstacleV3GoldenTest::RunTest(const FString& Parameters)
{
	using namespace EcoObstacleV3Test;
	namespace OC = EcoWorldV3::ObstacleCheck;
	namespace G = EcoWorldV3::GoldenObstacle;
	Report(*this, TEXT("설정"), OC::CheckConfig());
	const FReport Slides = OC::CheckSlides();
	Report(*this, TEXT("미끄러짐"), Slides);
	TestTrue(TEXT("미끄러짐: 부딪힘·물러남 수 = 골든"), Slides.Count0 == G::kSlideHits && Slides.Count1 == G::kSlideBacks && Slides.Count0 > 0 && Slides.Count1 > 0);
	const FReport Sights = OC::CheckSights();
	Report(*this, TEXT("시선"), Sights);
	TestTrue(TEXT("시선: 가림 수 = 골든"), Sights.Count0 == G::kSightBlocked && Sights.Count0 > 0);
	Report(*this, TEXT("먹이"), OC::CheckFood());
	const FReport Pushes = OC::CheckPushes();
	Report(*this, TEXT("밀어내기"), Pushes);
	TestTrue(TEXT("밀어내기: 옮김·못 옮김 수 = 골든"), Pushes.Count0 == G::kPushMoved && Pushes.Count1 == G::kPushFailed && Pushes.Count0 > 0);
	const FReport Steps = OC::CheckSteps();
	Report(*this, TEXT("한 스텝 장면"), Steps);
	TestTrue(TEXT("한 스텝 장면: 부딪힘·돌아섬·포획 수 = 골든"), Steps.Count0 == G::kStepHits && Steps.Count1 == G::kStepDeads && Steps.Count2 == G::kStepCatches
															 && Steps.Count0 > 0 && Steps.Count1 > 0);
	Report(*this, TEXT("끄면 그대로"), OC::CheckOffIgnores());
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObstacleV3RunTest,
	"AdaptiveEcosystem.Policy.V3.Obstacle.Run",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObstacleV3RunTest::RunTest(const FString& Parameters)
{
	using namespace EcoWorldV3;
	using namespace EcoObstacleV3Test;
	{
		FReferenceWorld Ref;
		Ref.Init(RunConfig(true, true));
		FWorldState& W = Ref.World;
		const FObstacleConfig& O = W.Config.Obstacles;
		TestTrue(TEXT("원판 367 이 세계에 들어갔다"), O.Active() && O.Num() == 367);
		int64 Inside = 0, Outside = 0;
		for (int32 t = 0; t < 900; ++t)
		{
			Step(W, Ref.Views.data(), Ref.NumHerbivores(), Ref.ThreatPtrs.data(), Ref.NumThreats());
			for (const FHerbBody& B : Ref.Bodies)
			{
				Inside += EcoThreatV3::InsideAnyObstacle(B.Pos.X, B.Pos.Y, O.Discs.data(), O.Num(), O.BodyR) ? 1 : 0;
				Outside += (B.Pos.X < 0.0 || B.Pos.Y < 0.0 || B.Pos.X > W.Config.WorldSize || B.Pos.Y > W.Config.WorldSize) ? 1 : 0;
			}
			for (const FThreatAgent& A : Ref.Threats)
			{
				Inside += EcoThreatV3::InsideAnyObstacle(A.State.PosX, A.State.PosY, O.Discs.data(), O.Num(), O.BodyR) ? 1 : 0;
				Outside += (A.State.PosX < 0.0 || A.State.PosY < 0.0 || A.State.PosX > W.Config.WorldSize || A.State.PosY > W.Config.WorldSize) ? 1 : 0;
			}
		}
		const FWorldStats& S = W.Stats;
		TestEqual(TEXT("사슴·늑대 중심은 늘 원판(r + 몸) 밖"), Inside, int64(0));
		TestEqual(TEXT("사슴·늑대는 무대 밖에 나가지 않는다"), Outside, int64(0));
		TestTrue(TEXT("사슴·늑대가 원판에 부딪혀 미끄러진다"), S.ObstacleDeerHit > 0 && S.ObstacleWolfHit > 0);
		TestTrue(TEXT("물러남 ≤ 부딪힘, 늑대·스텝 = 900 × 4"), S.ObstacleDeerBack <= S.ObstacleDeerHit && S.ObstacleWolfSteps == int64(900) * 4);
		TestTrue(TEXT("처음 원판 안 개체는 밖으로 옮겼다(못 옮긴 개체 없음)"), S.ObstaclePushFailed == 0);
		AddInfo(FString::Printf(TEXT("사슴·스텝 %lld 중 닿음 %lld 물러남 %lld · 늑대·스텝 %lld 중 닿음 %lld 되돌림 %lld 돌아섬 %lld · 밀어냄 %lld · 잡힘 %lld"),
								static_cast<long long>(S.ObstacleDeerSteps), static_cast<long long>(S.ObstacleDeerHit), static_cast<long long>(S.ObstacleDeerBack),
								static_cast<long long>(S.ObstacleWolfSteps), static_cast<long long>(S.ObstacleWolfHit), static_cast<long long>(S.ObstacleWolfBack),
								static_cast<long long>(S.ObstacleWolfDead), static_cast<long long>(S.ObstaclePushMoved), static_cast<long long>(S.Caught)));
	}
	// 같은 시드 = 같은 비트
	{
		FReferenceWorld A, B;
		A.Init(RunConfig(true, true));
		B.Init(RunConfig(true, true));
		bool bSame = true;
		for (int32 t = 0; t < 300 && bSame; ++t)
		{
			Step(A.World, A.Views.data(), A.NumHerbivores(), A.ThreatPtrs.data(), A.NumThreats());
			Step(B.World, B.Views.data(), B.NumHerbivores(), B.ThreatPtrs.data(), B.NumThreats());
			bSame = SameBodies(A, B);
		}
		TestTrue(TEXT("같은 시드 = 같은 비트"), bSame);
	}
	// 끄면 그대로: 원판을 넣고 켬 칸만 끈 세계 = 원판이 없는 세계 (평면 맵·기준 루프·골든 그대로), 켜도 원판이 없으면 그대로
	{
		FReferenceWorld Off, Base, Empty;
		Off.Init(RunConfig(false, true));
		Base.Init(RunConfig(false, false));
		Empty.Init(RunConfig(true, false));
		bool bSame = true, bSameEmpty = true;
		for (int32 t = 0; t < 300; ++t)
		{
			Step(Off.World, Off.Views.data(), Off.NumHerbivores(), Off.ThreatPtrs.data(), Off.NumThreats());
			Step(Base.World, Base.Views.data(), Base.NumHerbivores(), Base.ThreatPtrs.data(), Base.NumThreats());
			Step(Empty.World, Empty.Views.data(), Empty.NumHerbivores(), Empty.ThreatPtrs.data(), Empty.NumThreats());
			bSame = bSame && SameBodies(Off, Base);
			bSameEmpty = bSameEmpty && SameBodies(Empty, Base);
		}
		TestTrue(TEXT("끔(원판 있음) = 원판 없는 세계, 비트 단위"), bSame);
		TestTrue(TEXT("켬(원판 0 개) = 원판 없는 세계, 비트 단위"), bSameEmpty);
		TestTrue(TEXT("끄면 장애물 기록 0"), Off.World.Stats.ObstacleDeerSteps == 0 && Off.World.Stats.ObstacleWolfSteps == 0);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObstacleV3LevelScanTest,
	"AdaptiveEcosystem.Policy.V3.Obstacle.LevelScan",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoObstacleV3LevelScanTest::RunTest(const FString& Parameters)
{
	using namespace EcoObstacleV3Test;
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World))
	{
		return false;
	}
	// 무대 원점 (0, 0), 한 변 60 단위 = 12000 cm. 기본 상자 메시 = 100 cm 정육면체 (반폭 50 cm)
	const FVector Origin(0.0, 0.0, 0.0);
	SpawnBox(W.World, FVector(2000.0, 5000.0, 100.0), FVector(1.0, 1.0, 2.0), true);    // 원판: 반지름 50 cm = 0.25 단위, (10, 25)
	SpawnBox(W.World, FVector(5000.0, 3000.0, 100.0), FVector(1.0, 1.0, 2.0), false);   // 충돌 없음
	SpawnBox(W.World, FVector(6000.0, 3000.0, 100.0), FVector(0.3, 0.3, 2.0), true);    // 작음 (반지름 15 cm)
	SpawnBox(W.World, FVector(7000.0, 3000.0, 10.0), FVector(2.0, 2.0, 0.2), true);     // 낮음 (높이 20 cm)
	SpawnBox(W.World, FVector(3000.0, 3000.0, 100.0), FVector(1.0, 1.0, 2.0), true);    // 은신처 원 안 (중심 (15, 15), 반경 6)
	SpawnBox(W.World, FVector(-500.0, 3000.0, 100.0), FVector(1.0, 1.0, 2.0), true);    // 무대 밖
	// 인스턴스 메시: 충돌하는 인스턴스 둘 (반지름 100 cm = 0.5 단위)
	AActor* Holder = W.World->SpawnActor<AActor>();
	UInstancedStaticMeshComponent* Ism = NewObject<UInstancedStaticMeshComponent>(Holder);
	Holder->SetRootComponent(Ism);
	Ism->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
	Ism->SetCollisionProfileName(TEXT("BlockAll"));
	Ism->RegisterComponent();
	Ism->AddInstance(FTransform(FRotator::ZeroRotator, FVector(9000.0, 9000.0, 100.0), FVector(2.0, 2.0, 2.0)), true);
	Ism->AddInstance(FTransform(FRotator::ZeroRotator, FVector(9000.0, 1000.0, 100.0), FVector(2.0, 2.0, 2.0)), true);
	int32 ActorsBefore = 0;
	for (TActorIterator<AActor> It(W.World); It; ++It)
	{
		++ActorsBefore;
	}
	const int32 InstancesBefore = Ism->GetInstanceCount();
	const std::vector<EcoObservationV3::FCoverInput> Covers = {{15.0, 15.0, 6.0}};
	FEcoV3ObstacleScan Scan;
	UEcoPolicyV3IntegratedSubsystem::ScanStageObstacles(*W.World, Origin, 60.0, Covers, TSet<const AActor*>(), false, Scan);
	{
		FString Ds;
		for (int32 k = 0; k < Scan.Num(); ++k)
		{
			Ds += FString::Printf(TEXT(" (%.3f, %.3f, %.3f)"), Scan.Discs[3 * k], Scan.Discs[3 * k + 1], Scan.Discs[3 * k + 2]);
		}
		AddInfo(FString::Printf(TEXT("읽기: 메시 %d · 원판 %d:%s · 충돌 없음 %d · 작음 %d · 낮음 %d · 은신처 안 %d"), Scan.SeenMeshes, Scan.Num(), *Ds,
								Scan.NoCollision, Scan.Tiny, Scan.Low, Scan.InCover));
	}
	TestEqual(TEXT("원판 3 (상자 1 + 인스턴스 2)"), Scan.Num(), 3);
	TestEqual(TEXT("충돌 없음 1"), Scan.NoCollision, 1);
	TestEqual(TEXT("작음 1"), Scan.Tiny, 1);
	TestEqual(TEXT("낮음 1"), Scan.Low, 1);
	TestEqual(TEXT("은신처 원 안 1"), Scan.InCover, 1);
	if (Scan.Num() == 3)
	{
		// x 순 정렬: (10, 25, 0.25), (45, 5, 0.5), (45, 45, 0.5)
		TestTrue(TEXT("상자 원판 = (10, 25) 반지름 0.25 단위"), FMath::IsNearlyEqual(Scan.Discs[0], 10.0, 1e-6) && FMath::IsNearlyEqual(Scan.Discs[1], 25.0, 1e-6)
															  && FMath::IsNearlyEqual(Scan.Discs[2], 0.25, 1e-6));
		TestTrue(TEXT("인스턴스 원판 = (45, 5)·(45, 45) 반지름 0.5 단위"), FMath::IsNearlyEqual(Scan.Discs[3], 45.0, 1e-6) && FMath::IsNearlyEqual(Scan.Discs[4], 5.0, 1e-6)
																	   && FMath::IsNearlyEqual(Scan.Discs[5], 0.5, 1e-6) && FMath::IsNearlyEqual(Scan.Discs[7], 45.0, 1e-6));
	}
	int32 ActorsAfter = 0;
	for (TActorIterator<AActor> It(W.World); It; ++It)
	{
		++ActorsAfter;
	}
	TestTrue(TEXT("읽기만 한다: 액터·인스턴스 수 그대로"), ActorsAfter == ActorsBefore && Ism->GetInstanceCount() == InstancesBefore);
	TSet<const AActor*> Exclude;
	Exclude.Add(Holder);
	FEcoV3ObstacleScan Scan2;
	UEcoPolicyV3IntegratedSubsystem::ScanStageObstacles(*W.World, Origin, 60.0, Covers, Exclude, false, Scan2);
	TestEqual(TEXT("뺄 액터(우리 은신처)는 읽지 않는다"), Scan2.Num(), 1);

	// JSON 내보내기 → 가져오기
	UEcoPolicyV3IntegratedSubsystem* Sub = W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	if (TestNotNull(TEXT("통합 서브시스템"), Sub))
	{
		FEcoV3IntegratedSettings S;
		Sub->ActivateForTest(S, false);
		EcoWorldV3::FWorldConfig Cfg = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(S, 1, 16, 4, Covers);
		Cfg.Obstacles.Discs = Scan.Discs;
		FEcoV3RegionContext* Ctx = Sub->AddContext(FName(TEXT("Forest")), 1, Origin, Cfg, 16, 4);
		Ctx->ObstacleScan = FEcoV3ObstacleScan();   // 내보내기는 읽기 결과가 아니라 세계가 쓰는 원판을 적는다 (가져온 원판도 그대로 돌려준다)
		Ctx->bObstaclesImported = true;
		const FString Path = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"), TEXT("EcoV3ObstacleScanTest.json"));
		TestTrue(TEXT("내보내기"), Sub->ExportObstacles(Path));
		TMap<FName, std::vector<double>> Back;
		TestTrue(TEXT("가져오기"), UEcoPolicyV3IntegratedSubsystem::LoadObstacleImport(Path, Back));
		const std::vector<double>* D = Back.Find(FName(TEXT("Forest")));
		TestTrue(TEXT("가져온 원판 = 내보낸 원판 (비트 단위)"), D != nullptr && *D == Scan.Discs);
		TestTrue(TEXT("세계에 원판이 들어갔다"), Ctx->Sim.Config.Obstacles.Active() && Ctx->Sim.Config.Obstacles.Num() == 3);
		IFileManager::Get().Delete(*Path);
	}
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoObstacleV3IntegratedDefaultsTest,
	"AdaptiveEcosystem.Policy.V3.Obstacle.IntegratedDefaults",
	EAutomationTestFlags_ApplicationContextMask | EAutomationTestFlags::EngineFilter)

bool FEcoObstacleV3IntegratedDefaultsTest::RunTest(const FString& Parameters)
{
	const FEcoV3IntegratedSettings Def;
	TestTrue(TEXT("통합 기본: 장애물 켬 (레벨 원판)"), Def.bObstacles);
	TestTrue(TEXT("통합 기본: 내보내기·가져오기 경로 없음"), Def.ObstacleExportPath.IsEmpty() && Def.ObstacleImportPath.IsEmpty());
	TestFalse(TEXT("세계 설정 기본은 장애물 끔 (평면 맵·기준 루프·골든 그대로)"), EcoWorldV3::FWorldConfig().Obstacles.bEnabled);
	const std::vector<EcoObservationV3::FCoverInput> Covers = EcoWorldV3::QuadCovers(Def.StageSizeUnits, 6.0);
	const EcoWorldV3::FWorldConfig C = UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Def, 0, 128, Def.WolvesPerRegion, Covers);
	TestTrue(TEXT("세계 설정: 장애물 켬 칸, 원판은 아직 없음 (무대를 만들 때 레벨에서 읽는다)"), C.Obstacles.bEnabled && C.Obstacles.Discs.empty() && !C.Obstacles.Active());
	const EcoWorldV3::FObstacleConfig O;
	TestTrue(TEXT("세계 설정 장애물 계수 = 거울 설정 (몸 30 cm·가림·먹이 줄임)"), C.Obstacles.BodyR == O.BodyR && C.Obstacles.bBlockSight && C.Obstacles.bNoFood
																			  && O.BodyR == 0.15);
	FEcoV3IntegratedSettings Off = Def;
	Off.bObstacles = false;
	TestFalse(TEXT("Obstacles 0 → 세계 장애물 끔"), UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(Off, 0, 128, 4, Covers).Obstacles.bEnabled);
	return true;
}

#endif

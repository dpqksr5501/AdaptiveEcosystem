// 환경 바뀜 감시 자동화 시험 (10-21 실시간 두뇌 교체, EcoV3EnvWatch.cpp·EcoV3Snapshot.cpp — 설계 LIVE_ADAPT_SPEC.md 5.1~5.3).
// 처리기 경계(밀어내기·다른 지역 그대로·감시 끔 = 비트 단위로 같음)는 EcoPolicyV3IntegratedTest.cpp Integrated.EnvChangeBoundary 가 본다.
//
// 실행:
//   UnrealEditor-Cmd.exe <project> -ExecCmds="Automation RunTests AdaptiveEcosystem.Policy.V3.EnvWatch"
//                        -unattended -nopause -nosplash -NullRHI -testexit="Automation Test Queue Empty"
//
// 묶음:
//   EnvWatch.Trees         시험 바닥 위 숲 무대 (바위 하나 + 명령과 같은 나무 짝): 'A∪B 로 시작'(시작 레벨 읽기 ScanStageObstacles + MergeDiscs — TryCreateContexts 와
//                          같은 짜임)의 세계 원판·나무 표시·레벨 읽기 원판·줄기 수 = 'A 로 시작하고 Play 중에 B 를 더함' (비트 단위). A = 배치 표 12 그루, B = 표 12 그루 +
//                          표 밖 둘 + 은신처 원 안 하나 (원판에서 빠진다). B 를 지우면 'A 로 시작' 과 같다. 바뀐 것이 없으면 대기 변화 없음, 판 1 → 2, 먹이 격자 그대로.
//                          실행 중 무대 나무(StageTrees 1) 무대: 줄기 A 가 생기면 'A 로 시작'(무대 나무 원판 뺌), A 를 지우면 '무대 나무로 시작'(다시 넣음)
//   EnvWatch.Weather       지역 날씨 콘솔 변수 (Play 중): 세계 설정 날씨·배수(UpdateDayNight)·어둠 그대로·시간표 없음·다른 지역 그대로, 같은 값 = 대기 없음, 빈 값 = 팀 설계
//                          기본, 못 읽는 값 = 그대로(경고 한 줄). 팀 지역 환경: 비 0.4 → 비 0.4, 가뭄 → 맑음, 폭풍 세기 0 → 비 1. 날씨를 끈 세계는 무시
//   EnvWatch.TeamWeatherStart  시작 날씨 = 팀 날씨 출처 (10-27 사용자 결정 (C)): 지역을 맡아 실제로 쓰는 팀 환경 어댑터(비 주기·작성 날씨)가 있으면 팀 지역 환경으로
//                          시작(우리 고정 날씨 대신 — 그 날씨 덮기로 만든 세계와 날씨 칸이 비트 단위로 같다, 환경 판 0), 쓰는 길을 끈·거부되는 어댑터는 출처 아님,
//                          빈 지역 목록 = 모든 지역, 날씨를 고르는 덮기 글자가 이김(못 읽는 글자는 팀 값), TeamWeatherStart 0·감시 끔 = 옛 동작, 늦게 등록된 지역은
//                          처음 읽을 때 바뀜(team_env — 출처 없는 지역은 지금처럼 바탕만), 시작 뒤 팀 바뀜은 그대로 따른다
//   EnvWatch.PushOut       새 줄기 원판 안 사슴·늑대는 밖으로 (보간 앞 자리도), 밖 개체 자리는 그대로, 돌아가기 지움, 밀어내기 기록, 거울 칸
//   EnvWatch.Off           eco.IntegratedV3.EnvWatch 0: 나무를 더해도 대기 변화·판·원판 그대로 (옛 동작). 대기 중에 끄면 넣지 않는다
//   EnvWatch.AutoSnapshot  자동 스냅숏 (eco.IntegratedV3.AutoSnapshot 1): 판마다 한 번, 바뀜 뒤 3 초(23 스텝) 그대로일 때, 이름 _e<판>, 'env' 블록·level_trunks,
//                          .tmp 가 남지 않는다. 주기 스냅숏 (eco.IntegratedV3.SnapshotEvery 1): 계기 periodic, 24 스텝에 3 번
//   EnvWatch.TestStandIns  시험용 대역: Test.AddTrees 가 명령과 같은 꼬리표 짝을 무대 안 빈자리에 결정적으로 놓고 감시가 알아챈다 (출처 test), Test.RemoveTrees,
//                          Test.At (콘솔 — 시뮬레이션 초가 되면 한 번), 명령줄 -EcoV3TestAt= -EcoV3TestCmd= 쌍 여러 개, EnvInfo

#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "../EcoPolicyV3IntegratedSubsystem.h"
#include "../EcoWorldV3.h"
#include "../TreeLayoutV3.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "EcoTestWorld.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "World/EcoRegionEnvironmentAdapter.h"
#include "World/EcologyRegion.h"
#include "World/EcologyWorldSubsystem.h"

// 단일 번역 단위 빌드(unity)에서 다른 시험 파일의 이름과 겹치지 않게 이름 있는 네임스페이스에 둔다.
namespace EcoV3EnvWatchTestImpl
{
	using FSub = UEcoPolicyV3IntegratedSubsystem;
	using EcoObservationV3::FCoverInput;
	using EcoTreeLayoutV3::FTree;

	constexpr double kSize = EcoTreeLayoutV3::kStageSizeUnits;   // 60 단위 (120 m) — 배치 표 무대
	constexpr double kTopZ = 250.0;                              // 시험 바닥 윗면
	const FVector kOrigin(0.0, 0.0, kTopZ);                      // 무대 (0, 0)

	/** 바닥 상자 (윗면 Z = TopZ, 무대 (0, 0) 의 한 변 SideCm 정사각을 덮는다). */
	AStaticMeshActor* Floor(UWorld& World, double SideCm, double TopZ)
	{
		AStaticMeshActor* A = World.SpawnActor<AStaticMeshActor>(FVector(0.5 * SideCm, 0.5 * SideCm, TopZ - 50.0), FRotator::ZeroRotator);
		if (!A)
		{
			return nullptr;
		}
		A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		A->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		A->SetActorScale3D(FVector(SideCm / 100.0 + 20.0, SideCm / 100.0 + 20.0, 1.0));
		A->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
		return A;
	}

	/** 바위 (줄기 아닌 레벨 원판): 1 m × 1 m × 2 m 상자, BlockAll — 반지름 50 cm, 중심 (X, Y) 무대 단위. */
	AStaticMeshActor* Rock(UWorld& World, double X, double Y)
	{
		AStaticMeshActor* A = World.SpawnActor<AStaticMeshActor>(FVector(X * EcoRepertoireV3::kUnitCm, Y * EcoRepertoireV3::kUnitCm, kTopZ + 100.0), FRotator::ZeroRotator);
		if (!A)
		{
			return nullptr;
		}
		A->GetStaticMeshComponent()->SetMobility(EComponentMobility::Movable);
		A->GetStaticMeshComponent()->SetStaticMesh(LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube")));
		A->SetActorScale3D(FVector(1.0, 1.0, 2.0));
		A->GetStaticMeshComponent()->SetCollisionProfileName(TEXT("BlockAll"));
		return A;
	}

	struct FPair
	{
		AActor* Tree = nullptr;
		AActor* Trunk = nullptr;
	};

	/** 명령(EcoV3PlaceTreesCommandlet)과 같은 나무 + 줄기 막이 짝을 놓는다 (지면 = 줄기 아래 가장 낮은 땅). */
	bool PlaceTree(UWorld& World, const FTree& T, const FString& Id, FPair& Out)
	{
		UStaticMesh* TreeMesh = LoadObject<UStaticMesh>(nullptr, UTF8_TO_TCHAR(EcoTreeLayoutV3::kMeshPath));
		UStaticMesh* TrunkMesh = LoadObject<UStaticMesh>(nullptr, FSub::LevelTrunkMeshPath());
		double MinZ = 0.0;
		double MaxZ = 0.0;
		if (!TrunkMesh || !FSub::GroundStageTree(World, kOrigin, T, MinZ, MaxZ))
		{
			return false;
		}
		return FSub::SpawnLevelTreePair(World, T, kOrigin, MinZ, TreeMesh, *TrunkMesh, FName(*(FString(TEXT("EcoV3TreeId_")) + Id)), Out.Tree, Out.Trunk);
	}

	/** 시작 레벨 읽기 + 합치기 — TryCreateContexts 와 같은 짜임 (ScanStageObstacles(…, 지면 검사 참, 지역 이름) → MergeDiscs(레벨 읽기, 무대 나무 없음, 레벨 나무 표시)). */
	void StartCompose(UWorld& World, const std::vector<FCoverInput>& Covers, const AActor* FloorActor, FEcoV3ObstacleScan& OutScan, std::vector<double>& OutDiscs,
					  TArray<uint8>& OutIsTree)
	{
		TSet<const AActor*> Exclude;
		Exclude.Add(FloorActor);
		FSub::ScanStageObstacles(World, kOrigin, kSize, Covers, Exclude, /*bProbeGround*/ true, OutScan, TEXT("Forest"));
		OutDiscs = FSub::MergeDiscs(OutScan.Discs, {}, &OutIsTree, &OutScan.IsLevelTree);
	}

	void SetCVar(const TCHAR* Name, const TCHAR* Value)
	{
		if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name))
		{
			V->Set(Value, ECVF_SetByCode);
		}
	}

	FString GetCVar(const TCHAR* Name)
	{
		const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name);
		return V ? V->GetString() : FString();
	}

	TSharedPtr<FJsonObject> ReadJson(const FString& Path)
	{
		FString Text;
		if (!FFileHelper::LoadFileToString(Text, *Path))
		{
			return nullptr;
		}
		TSharedPtr<FJsonObject> Root;
		FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root);
		return Root;
	}

	/** 숲 무대 하나만 있는 켜진 서브시스템 (조정자 없이). */
	FEcoV3RegionContext* ForestContext(FAutomationTestBase& Test, UWorld& World, int64 Seed, UEcoPolicyV3IntegratedSubsystem*& OutSub,
									   const std::vector<double>* Discs = nullptr)
	{
		OutSub = World.GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
		if (!Test.TestNotNull(TEXT("통합 서브시스템"), OutSub))
		{
			return nullptr;
		}
		FEcoV3IntegratedSettings S;
		S.Seed = Seed;
		S.StageSizeUnits = kSize;
		S.WeatherForest = GetCVar(TEXT("eco.IntegratedV3.WeatherForest"));   // Play 시작 값 = 지금 콘솔 값 (날씨는 이 시험의 바뀜이 아니다)
		OutSub->ActivateForTest(S, /*bTerrain*/ false);
		EcoWorldV3::FWorldConfig C = FSub::MakeRegionWorldConfig(S, 1, 16, 2, EcoWorldV3::QuadCovers(kSize, 6.0), FName(TEXT("Forest")));
		if (Discs)
		{
			C.Obstacles.Discs = *Discs;
		}
		return OutSub->AddContext(FName(TEXT("Forest")), 1, kOrigin, C, 16, 2);
	}

	int32 Num3(const std::vector<double>& Flat)
	{
		return static_cast<int32>(Flat.size() / 3);
	}

	/** 팀 지역 하나 (지역 환경 = 날씨 State·비 세기 Rainfall) — 등록까지. */
	AEcologyRegion* TeamRegion(UWorld& World, FName Id, double Y, EEcoWeatherState State, float Rainfall)
	{
		AEcologyRegion* R = World.SpawnActor<AEcologyRegion>(FVector(0.0, Y, 0.0), FRotator::ZeroRotator);
		UEcologyWorldSubsystem* Regions = World.GetSubsystem<UEcologyWorldSubsystem>();
		if (!R || !Regions)
		{
			return nullptr;
		}
		R->RegionId = Id;
		FRegionEnvironmentState Env = R->GetEnvironmentState();
		Env.WeatherState = State;
		Env.Rainfall = Rainfall;
		R->SetEnvironmentState(Env);
		Regions->RegisterRegion(R);
		return R;
	}

	/** 팀 환경 어댑터 하나 (월드가 돌지 않아 쓰지는 않는다 — 출처 판정만 본다). Ids 가 비면 모든 지역. */
	AEcoRegionEnvironmentAdapter* TeamAdapter(UWorld& World, const TArray<FName>& Ids, bool bCycle, bool bAuthored)
	{
		AEcoRegionEnvironmentAdapter* A = World.SpawnActor<AEcoRegionEnvironmentAdapter>(FVector::ZeroVector, FRotator::ZeroRotator);
		if (A)
		{
			A->RegionIds = Ids;
			A->bCycleRainfall = bCycle;
			A->bApplyAuthoredWeather = bAuthored;
		}
		return A;
	}

	/** 날씨 배수 넷이 같다. */
	bool SameMults(const EcoWorldV3::FWeatherMults& A, const EcoWorldV3::FWeatherMults& B)
	{
		return A.Sight == B.Sight && A.Hear == B.Hear && A.DeerSpeed == B.DeerSpeed && A.WolfSpeed == B.WolfSpeed;
	}

	/** 월드의 줄기 막이 수 (지운 것 빼고). */
	int32 CountTagged(UWorld& World, FName Tag)
	{
		int32 N = 0;
		for (TActorIterator<AActor> It(&World); It; ++It)
		{
			N += It->ActorHasTag(Tag) ? 1 : 0;
		}
		return N;
	}
}

// -----------------------------------------------------------------------------
// 나무: 'A∪B 로 시작' = 'A 로 시작하고 Play 중에 B 를 더함'
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3EnvWatchTreesTest,
	"AdaptiveEcosystem.Policy.V3.EnvWatch.Trees",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3EnvWatchTreesTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3EnvWatchTestImpl;
	const EcoTreeLayoutV3::FStageTrees* Forest = FSub::FindStageTrees(TEXT("Forest"), kSize);
	if (!TestNotNull(TEXT("숲 배치 표"), Forest) || !TestEqual(TEXT("숲 24 그루"), Forest->Num, 24))
	{
		return false;
	}
	const std::vector<FCoverInput> Covers = EcoWorldV3::QuadCovers(kSize, 6.0);
	// A = 표 0~11, B = 표 12~23 + 표 밖 둘 (맞추지 않는 읽은 값) + 은신처 원 (15, 15, 6) 안 하나 (시작 읽기도 감시도 원판에서 뺀다)
	TArray<FTree> TreesA;
	TArray<FTree> TreesB;
	for (int32 k = 0; k < Forest->Num; ++k)
	{
		(k < 12 ? TreesA : TreesB).Add(Forest->Trees[k]);
	}
	TreesB.Add(FSub::MakeLevelTree(30.0, 30.0, 2.0, 40.0));
	TreesB.Add(FSub::MakeLevelTree(24.0, 33.0, 1.9, 200.0));
	TreesB.Add(FSub::MakeLevelTree(15.5, 15.5, 2.1, 10.0));
	const double RockX = 8.0;
	const double RockY = 30.0;

	// 1. 'A∪B 로 시작' — 시작 레벨 읽기 그대로
	FEcoV3ObstacleScan ScanAB;
	std::vector<double> DiscsAB;
	TArray<uint8> IsTreeAB;
	{
		EcoTest::FScopedTestWorld W1;
		if (!TestNotNull(TEXT("시험 월드 1"), W1.World))
		{
			return false;
		}
		AStaticMeshActor* F1 = Floor(*W1.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ);
		bool bPlaced = F1 && Rock(*W1.World, RockX, RockY);
		FPair P;
		for (int32 k = 0; k < TreesA.Num(); ++k)
		{
			bPlaced = bPlaced && PlaceTree(*W1.World, TreesA[k], FString::Printf(TEXT("Forest_A%02d"), k), P);
		}
		for (int32 k = 0; k < TreesB.Num(); ++k)
		{
			bPlaced = bPlaced && PlaceTree(*W1.World, TreesB[k], FString::Printf(TEXT("Forest_B%02d"), k), P);
		}
		if (!TestTrue(TEXT("월드 1: 바닥·바위·나무 짝 A∪B"), bPlaced))
		{
			return false;
		}
		StartCompose(*W1.World, Covers, F1, ScanAB, DiscsAB, IsTreeAB);
	}
	AddInfo(FString::Printf(TEXT("'A∪B 로 시작': 원판 %d (레벨 나무 %d · 표와 맞춤 %d · 다름 %d · 은신처 원 안 %d)"), Num3(DiscsAB), ScanAB.LevelTrees, ScanAB.LevelTreesSnapped,
							ScanAB.LevelTreesUnmatched, ScanAB.InCover));
	TestTrue(TEXT("시작 읽기: 바위 1 + 줄기 26 (은신처 원 안 줄기는 빠진다)"), Num3(DiscsAB) == 27 && ScanAB.LevelTrees == 26 && ScanAB.LevelTreesSnapped == 24
																			  && ScanAB.LevelTreesUnmatched == 2 && ScanAB.InCover == 1);

	// 2. 'A 로 시작' → Play 중에 B 를 더한다
	EcoTest::FScopedTestWorld W2;
	if (!TestNotNull(TEXT("시험 월드 2"), W2.World))
	{
		return false;
	}
	UWorld& World = *W2.World;
	AStaticMeshActor* F2 = Floor(World, kSize * EcoRepertoireV3::kUnitCm, kTopZ);
	bool bPlaced = F2 && Rock(World, RockX, RockY);
	for (int32 k = 0; k < TreesA.Num(); ++k)
	{
		FPair P;
		bPlaced = bPlaced && PlaceTree(World, TreesA[k], FString::Printf(TEXT("Forest_A%02d"), k), P);
	}
	if (!TestTrue(TEXT("월드 2: 바닥·바위·나무 짝 A"), bPlaced))
	{
		return false;
	}
	FEcoV3ObstacleScan ScanA;
	std::vector<double> DiscsA;
	TArray<uint8> IsTreeA;
	StartCompose(World, Covers, F2, ScanA, DiscsA, IsTreeA);
	UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
	FEcoV3RegionContext* Ctx = ForestContext(*this, World, 37500, Sub, &DiscsA);
	if (!Ctx)
	{
		return false;
	}
	Ctx->ObstacleScan = ScanA;   // TryCreateContexts 가 하는 것
	Ctx->ObstacleIsTree = IsTreeA;
	Ctx->bLevelTrees = true;
	TestTrue(TEXT("바탕: 세계에 넣은 줄기 12 · 무대 안 줄기 막이 12"), Num3(Ctx->EnvTrunks) == 12 && Ctx->EnvLevelTrunks == 12);
	TestTrue(TEXT("바뀐 것이 없으면 읽어도 대기 변화 없음 (지금과 비트 단위로 같다)"), Sub->PollEnvironment(true) && !Sub->HasPendingEnvChange());
	const std::vector<double> CapBefore = Ctx->Sim.Food.Cap;
	const std::vector<double> FoodBefore = Ctx->Sim.Food.Food;
	const uint64 RngBefore = Ctx->Sim.Rng.State;

	TArray<FPair> PairsB;
	for (int32 k = 0; k < TreesB.Num(); ++k)
	{
		FPair P;
		if (!TestTrue(*FString::Printf(TEXT("Play 중 나무 짝 B%02d"), k), PlaceTree(World, TreesB[k], FString::Printf(TEXT("Forest_B%02d"), k), P)))
		{
			return false;
		}
		PairsB.Add(P);
	}
	TestTrue(TEXT("읽기 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	TestTrue(TEXT("읽기만으로는 세계 원판이 그대로"), Ctx->Sim.Config.Obstacles.Discs == DiscsA);
	Sub->ApplyEnvChange({}, {});
	AddInfo(FString::Printf(TEXT("'A 로 시작 + B 더함': 원판 %d · 넣은 줄기 %d · 무대 안 줄기 막이 %d · 판 #%d"), Ctx->Sim.Config.Obstacles.Num(), Num3(Ctx->EnvTrunks),
							Ctx->EnvLevelTrunks, Sub->GetEnvRevision()));
	TestTrue(TEXT("세계 원판 = 'A∪B 로 시작' (비트 단위, (x, y, r) 순)"), Ctx->Sim.Config.Obstacles.Discs == DiscsAB);
	TestTrue(TEXT("나무 표시 = 'A∪B 로 시작'"), Ctx->ObstacleIsTree == IsTreeAB);
	TestTrue(TEXT("레벨 읽기 원판·레벨 나무 표시 = 'A∪B 로 시작'"), Ctx->ObstacleScan.Discs == ScanAB.Discs && Ctx->ObstacleScan.IsLevelTree == ScanAB.IsLevelTree);
	TestTrue(TEXT("레벨 나무 수·표와 맞춤·다름 = 'A∪B 로 시작'"), Ctx->ObstacleScan.LevelTrees == ScanAB.LevelTrees
															   && Ctx->ObstacleScan.LevelTreesSnapped == ScanAB.LevelTreesSnapped
															   && Ctx->ObstacleScan.LevelTreesUnmatched == ScanAB.LevelTreesUnmatched);
	TestTrue(TEXT("넣은 줄기 26 · 무대 안 줄기 막이 27 (은신처 원 안 포함) · 레벨 나무 무대"), Num3(Ctx->EnvTrunks) == 26 && Ctx->EnvLevelTrunks == 27 && Ctx->bLevelTrees);
	TestTrue(TEXT("디버그 그리기 높이 = 원판마다"), Ctx->ObstacleGroundZ.Num() == Ctx->Sim.Config.Obstacles.Num());
	TestTrue(TEXT("먹이 격자·세계 난수 그대로 (팀 자원 계약 — 먹이는 스텝에서만 바뀐다)"),
			 Ctx->Sim.Food.Cap == CapBefore && Ctx->Sim.Food.Food == FoodBefore && Ctx->Sim.Rng.State == RngBefore);
	TestEqual(TEXT("환경 판 1"), Sub->GetEnvRevision(), 1);
	if (TestEqual(TEXT("바뀜 한 줄"), Sub->GetEnvChanges().Num(), 1))
	{
		const FEcoV3EnvChange& Ch = Sub->GetEnvChanges()[0];
		TestTrue(TEXT("바뀜: 숲·나무·'나무 12→26 (+14 −0)'·출처 level·판 1"), Ch.Region == FName(TEXT("Forest")) && Ch.Kind == TEXT("trees")
																				 && Ch.Detail == TEXT("나무 12→26 (+14 −0)") && Ch.Source == TEXT("level") && Ch.Revision == 1);
	}
	TestTrue(TEXT("넣은 뒤 다시 읽으면 대기 변화 없음"), Sub->PollEnvironment(true) && !Sub->HasPendingEnvChange());

	// 3. B 를 지우면 'A 로 시작' 과 같다
	for (const FPair& P : PairsB)
	{
		P.Trunk->Destroy();
		P.Tree->Destroy();
	}
	TestTrue(TEXT("B 를 지움 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	Sub->ApplyEnvChange({}, {});
	TestTrue(TEXT("B 를 지운 세계 원판·나무 표시 = 'A 로 시작' (비트 단위)"), Ctx->Sim.Config.Obstacles.Discs == DiscsA && Ctx->ObstacleIsTree == IsTreeA);
	TestTrue(TEXT("B 를 지운 레벨 읽기 = 'A 로 시작'"), Ctx->ObstacleScan.Discs == ScanA.Discs && Ctx->ObstacleScan.IsLevelTree == ScanA.IsLevelTree
														  && Ctx->ObstacleScan.LevelTrees == ScanA.LevelTrees);
	TestEqual(TEXT("환경 판 2"), Sub->GetEnvRevision(), 2);
	TestTrue(TEXT("바뀜 둘째 줄 '나무 26→12 (+0 −14)'"), Sub->GetEnvChanges().Num() == 2 && Sub->GetEnvChanges()[1].Detail == TEXT("나무 26→12 (+0 −14)"));
	TestTrue(TEXT("처음·마지막 바뀐 스텝"), Sub->GetEnvFirstChangedStep() == Sub->GetGlobalStep() && Sub->GetEnvChangedStep() == Sub->GetGlobalStep());

	// 4. 실행 중 무대 나무 (eco.IntegratedV3.StageTrees 1): 시작 때 무대 안 줄기 막이가 없을 때만 놓는다 (TryCreateContexts) — Play 중 줄기 A 가 생기면
	//    'A 로 시작' 과 같고 (무대 나무 원판을 뺀다 — 표 값에 맞춘 줄기와 값이 같아 둘 다 두면 겹친다), A 를 지우면 '무대 나무로 시작' 과 같다 (다시 넣는다)
	{
		EcoTest::FScopedTestWorld W3;
		if (!TestNotNull(TEXT("시험 월드 3"), W3.World))
		{
			return false;
		}
		UWorld& World3 = *W3.World;
		AStaticMeshActor* F3 = Floor(World3, kSize * EcoRepertoireV3::kUnitCm, kTopZ);
		if (!TestTrue(TEXT("월드 3: 바닥·바위"), F3 && Rock(World3, RockX, RockY)))
		{
			return false;
		}
		FEcoV3ObstacleScan ScanRock;
		std::vector<double> DiscsRock;
		TArray<uint8> IsTreeRock;
		StartCompose(World3, Covers, F3, ScanRock, DiscsRock, IsTreeRock);
		std::vector<double> StageDiscs;   // 무대 나무 원판 = 배치 표 24 그루 (표 순서 = (x, y, r) 순)
		for (int32 k = 0; k < Forest->Num; ++k)
		{
			StageDiscs.insert(StageDiscs.end(), {Forest->Trees[k].X, Forest->Trees[k].Y, Forest->Trees[k].R});
		}
		TArray<uint8> IsTreeStage;
		const std::vector<double> DiscsStage = FSub::MergeDiscs(ScanRock.Discs, StageDiscs, &IsTreeStage, &ScanRock.IsLevelTree);   // TryCreateContexts 와 같은 짜임
		UEcoPolicyV3IntegratedSubsystem* Sub3 = nullptr;
		FEcoV3RegionContext* Ctx3 = ForestContext(*this, World3, 37510, Sub3, &DiscsStage);
		if (!Ctx3)
		{
			return false;
		}
		Ctx3->ObstacleScan = ScanRock;
		Ctx3->ObstacleIsTree = IsTreeStage;
		Ctx3->bLevelTrees = false;
		Ctx3->Trees.Discs = StageDiscs;   // 액터 없이 원판만 (숨기기·보이기는 액터가 있을 때만)
		Ctx3->Trees.Layout = Forest->Num;
		TestTrue(TEXT("무대 나무로 시작: 원판 바위 1 + 24, 바뀐 것이 없으면 대기 변화 없음"),
				 Num3(DiscsStage) == 25 && Sub3->PollEnvironment(true) && !Sub3->HasPendingEnvChange());
		TArray<FPair> PairsA3;
		for (int32 k = 0; k < TreesA.Num(); ++k)
		{
			FPair Pa;
			if (!TestTrue(*FString::Printf(TEXT("월드 3: Play 중 나무 짝 A%02d"), k), PlaceTree(World3, TreesA[k], FString::Printf(TEXT("Forest_A%02d"), k), Pa)))
			{
				return false;
			}
			PairsA3.Add(Pa);
		}
		TestTrue(TEXT("무대 나무 무대에 줄기 A → 대기 변화"), Sub3->PollEnvironment(true) && Sub3->HasPendingEnvChange());
		Sub3->ApplyEnvChange({}, {});
		TestTrue(TEXT("세계 원판·나무 표시 = 'A 로 시작' (무대 나무 원판을 뺐다 — 겹친 원판 없음)"), Ctx3->Sim.Config.Obstacles.Discs == DiscsA && Ctx3->ObstacleIsTree == IsTreeA);
		TestTrue(TEXT("레벨 읽기 = 'A 로 시작' · 레벨 나무 무대"),
				 Ctx3->ObstacleScan.Discs == ScanA.Discs && Ctx3->ObstacleScan.IsLevelTree == ScanA.IsLevelTree && Ctx3->bLevelTrees);
		TestTrue(TEXT("바뀜 '나무 0→12 (+12 −0) · 무대 나무 24 뺌'"),
				 Sub3->GetEnvChanges().Num() == 1 && Sub3->GetEnvChanges()[0].Detail == TEXT("나무 0→12 (+12 −0) · 무대 나무 24 뺌"));
		TestTrue(TEXT("넣은 뒤 다시 읽으면 대기 변화 없음"), Sub3->PollEnvironment(true) && !Sub3->HasPendingEnvChange());
		for (const FPair& Pa : PairsA3)
		{
			Pa.Trunk->Destroy();
			Pa.Tree->Destroy();
		}
		TestTrue(TEXT("줄기 A 를 지움 → 대기 변화"), Sub3->PollEnvironment(true) && Sub3->HasPendingEnvChange());
		Sub3->ApplyEnvChange({}, {});
		TestTrue(TEXT("세계 원판·나무 표시 = '무대 나무로 시작' (다시 넣었다)"),
				 Ctx3->Sim.Config.Obstacles.Discs == DiscsStage && Ctx3->ObstacleIsTree == IsTreeStage && !Ctx3->bLevelTrees);
		TestTrue(TEXT("레벨 읽기 = 바위만"), Ctx3->ObstacleScan.Discs == ScanRock.Discs && Ctx3->ObstacleScan.LevelTrees == 0);
		TestTrue(TEXT("바뀜 '나무 12→0 (+0 −12) · 무대 나무 24 다시 넣음'"),
				 Sub3->GetEnvChanges().Num() == 2 && Sub3->GetEnvChanges()[1].Detail == TEXT("나무 12→0 (+0 −12) · 무대 나무 24 다시 넣음"));
	}
	return true;
}

// -----------------------------------------------------------------------------
// 날씨: 우리 지역 날씨 콘솔 변수 (Play 중) · 팀 지역 환경
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3EnvWatchWeatherTest,
	"AdaptiveEcosystem.Policy.V3.EnvWatch.Weather",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3EnvWatchWeatherTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3EnvWatchTestImpl;
	namespace W3 = EcoWorldV3;
	const TCHAR* const Vars[3] = {TEXT("eco.IntegratedV3.WeatherForest"), TEXT("eco.IntegratedV3.WeatherHighland"), TEXT("eco.IntegratedV3.WeatherBarren")};
	FString SavedVars[3];
	for (int32 i = 0; i < 3; ++i)
	{
		SavedVars[i] = GetCVar(Vars[i]);
		SetCVar(Vars[i], TEXT(""));   // Play 시작 값 = 설정의 빈 값 (팀 설계 기본)
	}
	ON_SCOPE_EXIT
	{
		for (int32 i = 0; i < 3; ++i)
		{
			SetCVar(Vars[i], *SavedVars[i]);
		}
	};
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World))
	{
		return false;
	}
	UEcoPolicyV3IntegratedSubsystem* Sub = W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>();
	UEcologyWorldSubsystem* Regions = W.World->GetSubsystem<UEcologyWorldSubsystem>();
	AEcologyRegion* Team = W.World->SpawnActor<AEcologyRegion>(FVector(0.0, 80000.0, 0.0), FRotator::ZeroRotator);
	if (!TestNotNull(TEXT("통합 서브시스템"), Sub) || !TestNotNull(TEXT("UEcologyWorldSubsystem"), Regions) || !TestNotNull(TEXT("팀 지역"), Team))
	{
		return false;
	}
	// 팀 지역 (고지): 지역 세계를 만들기 전에 등록 — 그때 값(맑음·비 0.2)이 바탕이다
	Team->RegionId = TEXT("Highland");
	Regions->RegisterRegion(Team);
	FEcoV3IntegratedSettings S;
	S.Seed = 37700;
	Sub->ActivateForTest(S, /*bTerrain*/ false);
	const std::vector<FCoverInput> Covers = W3::QuadCovers(S.StageSizeUnits, 6.0);
	FEcoV3RegionContext* Forest = Sub->AddContext(TEXT("Forest"), 1, FVector(0.0, 0.0, 0.0), FSub::MakeRegionWorldConfig(S, 1, 16, 2, Covers, TEXT("Forest")), 16, 2);
	FEcoV3RegionContext* High = Sub->AddContext(TEXT("Highland"), 2, FVector(0.0, 80000.0, 0.0), FSub::MakeRegionWorldConfig(S, 2, 16, 2, Covers, TEXT("Highland")), 16, 2);
	FEcoV3RegionContext* Barren = Sub->AddContext(TEXT("Barren"), 0, FVector(0.0, -80000.0, 0.0), FSub::MakeRegionWorldConfig(S, 0, 16, 2, Covers, TEXT("Barren")), 16, 2);
	if (!TestTrue(TEXT("지역 세계 셋"), Forest && High && Barren))
	{
		return false;
	}
	TestTrue(TEXT("시작 날씨: 숲 비 1 · 고지 눈 1 · 메마른 땅 맑음 (팀 설계)"), Forest->Sim.WeatherKind == W3::kWeatherRain && High->Sim.WeatherKind == W3::kWeatherSnow
																			  && Barren->Sim.WeatherKind == W3::kWeatherClear && Barren->Sim.Config.Weather.bEnabled);
	TestTrue(TEXT("팀 지역 환경 바탕을 읽었다 (고지만)"), High->bEnvTeamKnown && !Forest->bEnvTeamKnown);
	auto Same = [](const W3::FWeatherMults& A, const W3::FWeatherMults& B) { return A.Sight == B.Sight && A.Hear == B.Hear && A.DeerSpeed == B.DeerSpeed && A.WolfSpeed == B.WolfSpeed; };
	const W3::FWeatherMults ForestMults = Forest->Sim.Weather;
	const W3::FWeatherMults HighMults = High->Sim.Weather;

	// 1. 콘솔 변수 (Play 중): 메마른 땅 맑음 → 비 0.5
	SetCVar(TEXT("eco.IntegratedV3.WeatherBarren"), TEXT("rain:0.5"));
	TestTrue(TEXT("콘솔 변수 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	TestEqual(TEXT("읽기만으로는 날씨 그대로"), Barren->Sim.Config.Weather.Kind, W3::kWeatherClear);
	const double DarkBefore = Barren->Sim.Dark;
	Sub->ApplyEnvChange({}, {});
	const W3::FWeatherConfig& Bx = Barren->Sim.Config.Weather;
	TestTrue(TEXT("세계 설정 날씨 = 비 0.5 (시간표 없음)"), Bx.Kind == W3::kWeatherRain && Bx.Intensity == 0.5 && Bx.Schedule.empty() && Bx.bEnabled);
	TestTrue(TEXT("지금 날씨·배수 = UpdateDayNight (비 0.5)"), Barren->Sim.WeatherKind == W3::kWeatherRain && Barren->Sim.WeatherIntensity == 0.5
															   && Same(Barren->Sim.Weather, W3::WeatherMults(Bx, W3::kWeatherRain, 0.5)) && Barren->Sim.Weather.Hear < 1.0);
	TestEqual(TEXT("어둠 그대로 (같은 T)"), Barren->Sim.Dark, DarkBefore);
	TestTrue(TEXT("다른 지역 그대로"), Same(Forest->Sim.Weather, ForestMults) && Same(High->Sim.Weather, HighMults) && Forest->Sim.Config.Weather.Kind == W3::kWeatherRain
										 && High->Sim.Config.Weather.Kind == W3::kWeatherSnow);
	TestEqual(TEXT("환경 판 1"), Sub->GetEnvRevision(), 1);
	if (TestEqual(TEXT("바뀜 한 줄"), Sub->GetEnvChanges().Num(), 1))
	{
		const FEcoV3EnvChange& Ch = Sub->GetEnvChanges()[0];
		TestTrue(TEXT("바뀜: 메마른 땅·날씨·'맑음→비 0.50'·출처 cvar:eco.IntegratedV3.WeatherBarren"),
				 Ch.Region == FName(TEXT("Barren")) && Ch.Kind == TEXT("weather") && Ch.Detail == TEXT("맑음→비 0.50") && Ch.Source == TEXT("cvar:eco.IntegratedV3.WeatherBarren"));
	}
	// 같은 날씨를 다른 글자로 = 바뀐 것 없음
	SetCVar(TEXT("eco.IntegratedV3.WeatherBarren"), TEXT("비:0.5"));
	TestTrue(TEXT("같은 날씨 (다른 글자) → 대기 변화 없음"), Sub->PollEnvironment(true) && !Sub->HasPendingEnvChange());

	// 2. 빈 값 = 팀 설계 기본 (메마른 땅 맑음)
	SetCVar(TEXT("eco.IntegratedV3.WeatherBarren"), TEXT(""));
	TestTrue(TEXT("빈 값 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	Sub->ApplyEnvChange({}, {});
	TestTrue(TEXT("빈 값 = 맑음 (배수 1)"), Bx.Kind == W3::kWeatherClear && Bx.Intensity == 0.0 && Barren->Sim.WeatherKind == W3::kWeatherClear
											  && Same(Barren->Sim.Weather, W3::FWeatherMults()));
	TestEqual(TEXT("환경 판 2"), Sub->GetEnvRevision(), 2);

	// 3. 못 읽는 값 = 그대로 (경고 한 줄)
	AddExpectedMessagePlain(TEXT("'fog' 를 못 읽었다"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 1);
	SetCVar(TEXT("eco.IntegratedV3.WeatherBarren"), TEXT("fog"));
	TestTrue(TEXT("못 읽는 값 → 대기 변화 없음"), Sub->PollEnvironment(true) && !Sub->HasPendingEnvChange());
	TestEqual(TEXT("환경 판 그대로 2"), Sub->GetEnvRevision(), 2);

	// 4. 팀 지역 환경 (팀 콘솔 eco.Environment.Rain 과 같은 꼴): 고지 비 0.4 → 가뭄(맑음) → 폭풍 세기 0 (비 1)
	FRegionEnvironmentState Env = Team->GetEnvironmentState();
	Env.WeatherState = EEcoWeatherState::Rain;
	Env.Rainfall = 0.4f;
	Team->SetEnvironmentState(Env);
	TestTrue(TEXT("팀 비 0.4 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	Sub->ApplyEnvChange({}, {});
	const W3::FWeatherConfig& Hx = High->Sim.Config.Weather;
	TestTrue(TEXT("고지 = 비 (세기 = 팀 Rainfall)"), Hx.Kind == W3::kWeatherRain && Hx.Intensity == static_cast<double>(0.4f) && High->Sim.WeatherKind == W3::kWeatherRain
														&& Same(High->Sim.Weather, W3::WeatherMults(Hx, W3::kWeatherRain, static_cast<double>(0.4f))));
	TestTrue(TEXT("바뀜: 고지·'눈 1.00→비 0.40'·출처 team_env·판 3"), Sub->GetEnvRevision() == 3 && Sub->GetEnvChanges().Last().Region == FName(TEXT("Highland"))
																	&& Sub->GetEnvChanges().Last().Detail == TEXT("눈 1.00→비 0.40")
																	&& Sub->GetEnvChanges().Last().Source == TEXT("team_env"));
	Env.WeatherState = EEcoWeatherState::Drought;
	Team->SetEnvironmentState(Env);
	TestTrue(TEXT("팀 가뭄 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	Sub->ApplyEnvChange({}, {});
	TestTrue(TEXT("가뭄 = 맑음"), Hx.Kind == W3::kWeatherClear && Hx.Intensity == 0.0 && Sub->GetEnvRevision() == 4);
	Env.WeatherState = EEcoWeatherState::Storm;
	Env.Rainfall = 0.0f;
	Team->SetEnvironmentState(Env);
	TestTrue(TEXT("팀 폭풍 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	Sub->ApplyEnvChange({}, {});
	TestTrue(TEXT("폭풍·비 세기 0 = 비 1"), Hx.Kind == W3::kWeatherRain && Hx.Intensity == 1.0 && Sub->GetEnvRevision() == 5);
	TestTrue(TEXT("팀 값이 그대로면 대기 변화 없음"), Sub->PollEnvironment(true) && !Sub->HasPendingEnvChange());

	// 5. 날씨를 끈 세계 (eco.IntegratedV3.Weather 0)는 무시한다 — 지금과 같다
	{
		EcoTest::FScopedTestWorld W2;
		UEcoPolicyV3IntegratedSubsystem* Sub2 = W2.World ? W2.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
		if (TestNotNull(TEXT("시험 월드 2"), Sub2))
		{
			FEcoV3IntegratedSettings Off;
			Off.Seed = 37701;
			Off.bWeather = false;
			Sub2->ActivateForTest(Off, false);
			FEcoV3RegionContext* B2 = Sub2->AddContext(TEXT("Barren"), 0, FVector::ZeroVector, FSub::MakeRegionWorldConfig(Off, 0, 16, 2, Covers, TEXT("Barren")), 16, 2);
			SetCVar(TEXT("eco.IntegratedV3.WeatherBarren"), TEXT("snow"));
			TestTrue(TEXT("날씨 끈 세계: 대기 변화 없음"), B2 && Sub2->PollEnvironment(true) && !Sub2->HasPendingEnvChange());
			TestTrue(TEXT("날씨 끈 세계: 판 0·날씨 꺼짐 그대로"), B2 && Sub2->GetEnvRevision() == 0 && !B2->Sim.Config.Weather.bEnabled);
		}
	}
	return true;
}

// -----------------------------------------------------------------------------
// 시작 날씨 = 팀 날씨 출처 (10-27 사용자 결정 (C) — 조연우 맵 날씨 시작 고침)
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3EnvWatchTeamWeatherStartTest,
	"AdaptiveEcosystem.Policy.V3.EnvWatch.TeamWeatherStart",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3EnvWatchTeamWeatherStartTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3EnvWatchTestImpl;
	namespace W3 = EcoWorldV3;
	const TCHAR* const Vars[5] = {TEXT("eco.IntegratedV3.WeatherForest"), TEXT("eco.IntegratedV3.WeatherHighland"), TEXT("eco.IntegratedV3.WeatherBarren"),
								  TEXT("eco.IntegratedV3.TeamWeatherStart"), TEXT("eco.IntegratedV3.EnvWatch")};
	FString SavedVars[5];
	for (int32 i = 0; i < 5; ++i)
	{
		SavedVars[i] = GetCVar(Vars[i]);
	}
	ON_SCOPE_EXIT
	{
		for (int32 i = 0; i < 5; ++i)
		{
			SetCVar(Vars[i], *SavedVars[i]);
		}
	};
	TestEqual(TEXT("TeamWeatherStart 기본 켬"), SavedVars[3], FString(TEXT("1")));
	for (int32 i = 0; i < 3; ++i)
	{
		SetCVar(Vars[i], TEXT(""));   // Play 중 콘솔 값 = 빈 값 (읽기가 콘솔 바뀜으로 보지 않게 — 시작 덮기 글자는 설정으로 준다)
	}
	SetCVar(Vars[3], TEXT("1"));
	SetCVar(Vars[4], TEXT("1"));
	const FName Forest(TEXT("Forest"));
	const FName Highland(TEXT("Highland"));
	const FName Barren(TEXT("Barren"));
	const std::vector<FCoverInput> Covers = W3::QuadCovers(FEcoV3IntegratedSettings().StageSizeUnits, 6.0);   // 날씨 시험과 같은 기본 무대
	auto MakeCtx = [&Covers](UEcoPolicyV3IntegratedSubsystem& Sub, const FEcoV3IntegratedSettings& S, FName Id, int32 Index, double Y)
	{
		return Sub.AddContext(Id, Index, FVector(0.0, Y, 0.0), FSub::MakeRegionWorldConfig(S, Index, 16, 2, Covers, Id), 16, 2);
	};

	// 1. 지역마다 맡는 어댑터: 숲 = 비 주기 (팀 맑음), 고지 = 작성 날씨 (팀 비 0.5), 메마른 땅 = 쓰는 길을 끈 어댑터 + 둘 다 켜 거부되는 어댑터 (팀 비 0.5 — 출처 아님)
	W3::FWeatherConfig HighCfg;
	struct FNow
	{
		std::int32_t Kind = -1;
		double Intensity = -1.0;
		W3::FWeatherMults Mults;
		double Dark = -1.0;
		std::int32_t StepsToTransition = -2;
		std::int64_t T = -1;
	} HighNow;   // 팀 값으로 시작한 고지의 지금 날씨·배수·어둠·T
	{
		EcoTest::FScopedTestWorld W;
		UEcoPolicyV3IntegratedSubsystem* Sub = W.World ? W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
		if (!TestNotNull(TEXT("시험 월드·통합 서브시스템"), Sub))
		{
			return false;
		}
		FEcoV3IntegratedSettings S;
		S.Seed = 37720;
		Sub->ActivateForTest(S, /*bTerrain*/ false);
		const bool bTeam = TeamRegion(*W.World, Forest, 0.0, EEcoWeatherState::Clear, 0.0f) && TeamRegion(*W.World, Highland, 80000.0, EEcoWeatherState::Rain, 0.5f)
						   && TeamRegion(*W.World, Barren, -80000.0, EEcoWeatherState::Rain, 0.5f);
		const bool bAdapters = TeamAdapter(*W.World, {Forest}, /*bCycle*/ true, /*bAuthored*/ false) && TeamAdapter(*W.World, {Highland}, false, true)
							   && TeamAdapter(*W.World, {Barren}, false, false) && TeamAdapter(*W.World, {Barren}, true, true);
		if (!TestTrue(TEXT("팀 지역 셋·어댑터 넷"), bTeam && bAdapters))
		{
			return false;
		}
		FEcoV3RegionContext* F = MakeCtx(*Sub, S, Forest, 1, 0.0);
		FEcoV3RegionContext* H = MakeCtx(*Sub, S, Highland, 2, 80000.0);
		FEcoV3RegionContext* B = MakeCtx(*Sub, S, Barren, 0, -80000.0);
		if (!TestTrue(TEXT("지역 세계 셋"), F && H && B))
		{
			return false;
		}
		TestTrue(TEXT("숲: 비 주기 어댑터 = 출처 → 팀 맑음으로 시작 (우리 고정 비 1 대신), 배수 1"),
				 F->bEnvTeamSource && F->bEnvStartFromTeam && F->EnvTeamSourceWho.Contains(TEXT("비 주기 180초")) && F->Sim.Config.Weather.bEnabled
					 && F->Sim.Config.Weather.Kind == W3::kWeatherClear && F->Sim.Config.Weather.Intensity == 0.0 && F->Sim.WeatherKind == W3::kWeatherClear
					 && SameMults(F->Sim.Weather, W3::FWeatherMults()));
		TestTrue(TEXT("고지: 작성 날씨 어댑터 = 출처 → 팀 비 0.5 로 시작 (우리 고정 눈 1 대신)"),
				 H->bEnvTeamSource && H->bEnvStartFromTeam && H->EnvTeamSourceWho.Contains(TEXT("작성 날씨")) && H->Sim.Config.Weather.Kind == W3::kWeatherRain
					 && H->Sim.Config.Weather.Intensity == 0.5 && H->Sim.WeatherKind == W3::kWeatherRain && H->Sim.WeatherIntensity == 0.5);
		TestTrue(TEXT("메마른 땅: 쓰는 길을 끈·거부되는 어댑터는 출처 아님 → 우리 고정 맑음 (팀 비 0.5 는 바탕만)"),
				 !B->bEnvTeamSource && !B->bEnvStartFromTeam && B->EnvTeamSourceWho.IsEmpty() && B->bEnvTeamKnown && B->Sim.Config.Weather.Kind == W3::kWeatherClear);
		TestTrue(TEXT("시작값이라 환경 판 0·바뀜 없음, 읽어도 대기 변화 없음"),
				 Sub->GetEnvRevision() == 0 && Sub->GetEnvChanges().IsEmpty() && Sub->PollEnvironment(true) && !Sub->HasPendingEnvChange());
		const TArray<FString> Info = Sub->EnvInfoLines();
		TestTrue(TEXT("EnvInfo: 숲 '시작 날씨 = 팀 값' · 메마른 땅 '팀 날씨 출처 없음'"),
				 Info.Num() == 4 && Info[1].Contains(TEXT("시작 날씨 = 팀 값")) && Info[3].Contains(TEXT("팀 날씨 출처 없음")));
		HighCfg = H->Sim.Config.Weather;
		HighNow = {H->Sim.WeatherKind, H->Sim.WeatherIntensity, H->Sim.Weather, H->Sim.Dark, H->Sim.StepsToTransition, H->Sim.T};

		// 시작 뒤 팀 바뀜은 지금까지처럼 따른다: 숲 팀 비 0.65 → 비 0.65 (출처 team_env, 판 1)
		AEcologyRegion* TeamForest = W.World->GetSubsystem<UEcologyWorldSubsystem>()->GetRegion(Forest);
		if (!TestNotNull(TEXT("팀 숲 지역"), TeamForest))
		{
			return false;
		}
		FRegionEnvironmentState Env = TeamForest->GetEnvironmentState();
		Env.WeatherState = EEcoWeatherState::Rain;
		Env.Rainfall = 0.65f;
		TeamForest->SetEnvironmentState(Env);
		TestTrue(TEXT("숲 팀 비 0.65 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
		Sub->ApplyEnvChange({}, {});
		TestTrue(TEXT("숲 = 비 0.65 · '맑음→비 0.65' · 출처 team_env · 판 1"),
				 F->Sim.Config.Weather.Kind == W3::kWeatherRain && F->Sim.Config.Weather.Intensity == static_cast<double>(0.65f) && Sub->GetEnvRevision() == 1
					 && Sub->GetEnvChanges().Num() == 1 && Sub->GetEnvChanges()[0].Region == Forest && Sub->GetEnvChanges()[0].Detail == TEXT("맑음→비 0.65")
					 && Sub->GetEnvChanges()[0].Source == TEXT("team_env"));
	}

	// 2. 같은 날씨를 덮기 글자로 고른 세계 (팀 출처 없음): 팀 값으로 시작한 고지와 날씨 칸이 비트 단위로 같다 — '그 날씨로 세계를 만든 것과 같다'
	{
		EcoTest::FScopedTestWorld W;
		UEcoPolicyV3IntegratedSubsystem* Sub = W.World ? W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
		if (!TestNotNull(TEXT("시험 월드 2"), Sub))
		{
			return false;
		}
		FEcoV3IntegratedSettings S;
		S.Seed = 37720;
		S.WeatherHighland = TEXT("rain:0.5");
		Sub->ActivateForTest(S, false);
		const FEcoV3RegionContext* Ref = MakeCtx(*Sub, S, Highland, 2, 80000.0);
		if (TestNotNull(TEXT("덮기 고지"), Ref))
		{
			const W3::FWeatherConfig& Rc = Ref->Sim.Config.Weather;
			TestTrue(TEXT("세계 설정 날씨 같음 (켬·종류·세기·시간표 없음·계수)"),
					 Rc.bEnabled == HighCfg.bEnabled && Rc.Kind == HighCfg.Kind && Rc.Intensity == HighCfg.Intensity && Rc.Schedule.empty() && HighCfg.Schedule.empty()
						 && Rc.RainSight == HighCfg.RainSight && Rc.RainHear == HighCfg.RainHear && Rc.SnowSight == HighCfg.SnowSight && Rc.SnowHear == HighCfg.SnowHear
						 && Rc.SnowDeerSpeed == HighCfg.SnowDeerSpeed && Rc.SnowWolfSpeed == HighCfg.SnowWolfSpeed && Rc.bObsVisibility == HighCfg.bObsVisibility);
			TestTrue(TEXT("지금 날씨·배수·어둠·T 같음"), Ref->Sim.WeatherKind == HighNow.Kind && Ref->Sim.WeatherIntensity == HighNow.Intensity
															 && SameMults(Ref->Sim.Weather, HighNow.Mults) && Ref->Sim.Dark == HighNow.Dark
															 && Ref->Sim.StepsToTransition == HighNow.StepsToTransition && Ref->Sim.T == HighNow.T);
			TestTrue(TEXT("덮기 세계는 팀 출처 없음"), !Ref->bEnvTeamSource && !Ref->bEnvStartFromTeam);
		}
	}

	// 3. 빈 지역 목록 어댑터 (모든 지역) + 덮기 글자: 숲 '눈 0.5' 가 이김, 메마른 땅 못 읽는 'fog' 는 팀 값, 고지는 팀 값
	{
		EcoTest::FScopedTestWorld W;
		UEcoPolicyV3IntegratedSubsystem* Sub = W.World ? W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
		if (!TestNotNull(TEXT("시험 월드 3"), Sub))
		{
			return false;
		}
		AddExpectedMessagePlain(TEXT("'fog' 를 못 읽었다"), ELogVerbosity::Warning, EAutomationExpectedMessageFlags::Contains, 0);   // WeatherFor (팀 설계 기본을 쓴다)
		FEcoV3IntegratedSettings S;
		S.Seed = 37721;
		S.WeatherForest = TEXT("snow:0.5");
		S.WeatherBarren = TEXT("fog");
		Sub->ActivateForTest(S, false);
		const bool bTeam = TeamRegion(*W.World, Forest, 0.0, EEcoWeatherState::Clear, 0.0f) && TeamRegion(*W.World, Highland, 80000.0, EEcoWeatherState::Clear, 0.0f)
						   && TeamRegion(*W.World, Barren, -80000.0, EEcoWeatherState::Rain, 0.5f) && TeamAdapter(*W.World, {}, true, false);
		FEcoV3RegionContext* F = bTeam ? MakeCtx(*Sub, S, Forest, 1, 0.0) : nullptr;
		FEcoV3RegionContext* H = bTeam ? MakeCtx(*Sub, S, Highland, 2, 80000.0) : nullptr;
		FEcoV3RegionContext* B = bTeam ? MakeCtx(*Sub, S, Barren, 0, -80000.0) : nullptr;
		if (TestTrue(TEXT("팀 지역 셋·모든 지역 어댑터·지역 세계 셋"), F && H && B))
		{
			TestTrue(TEXT("숲: 날씨를 고르는 덮기 글자가 이김 (눈 0.5, 출처는 있음)"),
					 F->bEnvTeamSource && !F->bEnvStartFromTeam && F->Sim.Config.Weather.Kind == W3::kWeatherSnow && F->Sim.Config.Weather.Intensity == 0.5);
			TestTrue(TEXT("고지: 빈 목록 = 모든 지역 → 팀 맑음 (눈 1 대신)"), H->bEnvStartFromTeam && H->EnvTeamSourceWho.Contains(TEXT("모든 지역"))
																				  && H->Sim.Config.Weather.Kind == W3::kWeatherClear);
			TestTrue(TEXT("메마른 땅: 못 읽는 덮기 글자는 고르지 않음 → 팀 비 0.5"),
					 B->bEnvStartFromTeam && B->Sim.Config.Weather.Kind == W3::kWeatherRain && B->Sim.Config.Weather.Intensity == 0.5);
			TestEqual(TEXT("환경 판 0"), Sub->GetEnvRevision(), 0);
		}
	}

	// 4. 끄개: TeamWeatherStart 0 → 숲 우리 고정 비 1 (10-27 전), 감시 끔 → 고지 우리 고정 눈 1 (옛 동작). 출처 판정은 그대로 적는다
	{
		EcoTest::FScopedTestWorld W;
		UEcoPolicyV3IntegratedSubsystem* Sub = W.World ? W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
		if (!TestNotNull(TEXT("시험 월드 4"), Sub))
		{
			return false;
		}
		FEcoV3IntegratedSettings S;
		S.Seed = 37722;
		Sub->ActivateForTest(S, false);
		const bool bTeam = TeamRegion(*W.World, Forest, 0.0, EEcoWeatherState::Clear, 0.0f) && TeamRegion(*W.World, Highland, 80000.0, EEcoWeatherState::Clear, 0.0f)
						   && TeamAdapter(*W.World, {Forest, Highland}, true, false);
		SetCVar(Vars[3], TEXT("0"));
		FEcoV3RegionContext* F = bTeam ? MakeCtx(*Sub, S, Forest, 1, 0.0) : nullptr;
		SetCVar(Vars[3], TEXT("1"));
		SetCVar(Vars[4], TEXT("0"));
		FEcoV3RegionContext* H = bTeam ? MakeCtx(*Sub, S, Highland, 2, 80000.0) : nullptr;
		SetCVar(Vars[4], TEXT("1"));
		if (TestTrue(TEXT("팀 지역 둘·어댑터·지역 세계 둘"), F && H))
		{
			TestTrue(TEXT("TeamWeatherStart 0: 숲 비 1 (우리 고정)"), F->bEnvTeamSource && !F->bEnvStartFromTeam && F->Sim.Config.Weather.Kind == W3::kWeatherRain
																			 && F->Sim.Config.Weather.Intensity == 1.0);
			TestTrue(TEXT("감시 끔: 고지 눈 1 (우리 고정)"), H->bEnvTeamSource && !H->bEnvStartFromTeam && H->Sim.Config.Weather.Kind == W3::kWeatherSnow
																 && H->Sim.Config.Weather.Intensity == 1.0);
			TestTrue(TEXT("뒤에 켜도 시작값은 되돌아보지 않는다 (팀 값 그대로 = 대기 변화 없음)"), Sub->PollEnvironment(true) && !Sub->HasPendingEnvChange());
		}
	}

	// 5. 늦게 등록된 지역: 출처가 맡으면 처음 읽을 때 팀 값을 바뀜(team_env)으로, 출처가 없으면 지금처럼 바탕만
	{
		EcoTest::FScopedTestWorld W;
		UEcoPolicyV3IntegratedSubsystem* Sub = W.World ? W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
		if (!TestNotNull(TEXT("시험 월드 5"), Sub))
		{
			return false;
		}
		FEcoV3IntegratedSettings S;
		S.Seed = 37723;
		Sub->ActivateForTest(S, false);
		const bool bAdapter = TeamAdapter(*W.World, {Forest}, true, false) != nullptr;
		FEcoV3RegionContext* F = bAdapter ? MakeCtx(*Sub, S, Forest, 1, 0.0) : nullptr;
		FEcoV3RegionContext* B = bAdapter ? MakeCtx(*Sub, S, Barren, 0, -80000.0) : nullptr;
		if (!TestTrue(TEXT("어댑터·지역 세계 둘"), F && B))
		{
			return false;
		}
		TestTrue(TEXT("팀 지역 전: 숲 출처는 있으나 우리 고정 비 1, 메마른 땅 맑음"),
				 !F->bEnvTeamKnown && F->bEnvTeamSource && !F->bEnvStartFromTeam && F->Sim.Config.Weather.Kind == W3::kWeatherRain && !B->bEnvTeamKnown
					 && !B->bEnvTeamSource && B->Sim.Config.Weather.Kind == W3::kWeatherClear);
		const bool bTeam = TeamRegion(*W.World, Forest, 0.0, EEcoWeatherState::Clear, 0.0f) && TeamRegion(*W.World, Barren, -80000.0, EEcoWeatherState::Rain, 0.5f);
		TestTrue(TEXT("팀 지역 둘 등록 → 대기 변화"), bTeam && Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
		Sub->ApplyEnvChange({}, {});
		TestTrue(TEXT("숲 = 팀 맑음 · '비 1.00→맑음' · 출처 team_env · 판 1, 메마른 땅 맑음 그대로 (바탕만)"),
				 F->Sim.Config.Weather.Kind == W3::kWeatherClear && F->Sim.WeatherKind == W3::kWeatherClear && Sub->GetEnvRevision() == 1
					 && Sub->GetEnvChanges().Num() == 1 && Sub->GetEnvChanges()[0].Region == Forest && Sub->GetEnvChanges()[0].Detail == TEXT("비 1.00→맑음")
					 && Sub->GetEnvChanges()[0].Source == TEXT("team_env") && B->bEnvTeamKnown && B->Sim.Config.Weather.Kind == W3::kWeatherClear);
		TestTrue(TEXT("다시 읽으면 대기 변화 없음"), Sub->PollEnvironment(true) && !Sub->HasPendingEnvChange());
	}
	return true;
}

// -----------------------------------------------------------------------------
// 밀어내기: 새 줄기 원판 안 사슴·늑대
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3EnvWatchPushOutTest,
	"AdaptiveEcosystem.Policy.V3.EnvWatch.PushOut",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3EnvWatchPushOutTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3EnvWatchTestImpl;
	using EcoWorldV3::FVec2;
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World) || !TestNotNull(TEXT("바닥"), Floor(*W.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ)))
	{
		return false;
	}
	UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
	FEcoV3RegionContext* Ctx = ForestContext(*this, *W.World, 37550, Sub);
	if (!Ctx)
	{
		return false;
	}
	// 사슴 셋·늑대 둘 (몸만 — 처리기 없이 경계 함수를 부른다. 처리기 경로는 Integrated.EnvChangeBoundary)
	EcoWorldV3::FHerbBody D[3];
	const FVec2 Start[3] = {{30.05, 30.0}, {10.0, 50.0}, {29.8, 30.1}};
	for (int32 i = 0; i < 3; ++i)
	{
		D[i].Pos = Start[i];
		D[i].PrevPos = {1.0, 1.0};
		D[i].Detour.Left = 7;
		D[i].Detour.Side = 1;
	}
	EcoWorldV3::FThreatAgent Wolf[2];
	Wolf[0].State.PosX = 30.0;
	Wolf[0].State.PosY = 29.9;
	Wolf[1].State.PosX = 50.0;
	Wolf[1].State.PosY = 10.0;
	for (EcoWorldV3::FThreatAgent& A : Wolf)
	{
		A.PrevX = 2.0;
		A.PrevY = 2.0;
		A.State.Detour.Left = 5;
	}
	Ctx->bObsParityDiscsLogged = true;
	FPair P;
	if (!TestTrue(TEXT("줄기 짝 (30, 30) 크기 2"), PlaceTree(*W.World, FSub::MakeLevelTree(30.0, 30.0, 2.0, 0.0), TEXT("Forest_T00"), P)))
	{
		return false;
	}
	TestTrue(TEXT("읽기 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	TArray<TArray<EcoWorldV3::FHerbBody*>> Bodies;
	Bodies.Add({&D[0], &D[1], &D[2]});
	TArray<TArray<EcoWorldV3::FThreatAgent*>> Agents;
	Agents.Add({&Wolf[0], &Wolf[1]});
	Sub->ApplyEnvChange(Bodies, Agents);

	const std::vector<double>& Discs = Ctx->Sim.Config.Obstacles.Discs;
	const double BodyR = Ctx->Sim.Config.Obstacles.BodyR;
	auto Inside = [&Discs, BodyR](double X, double Y) { return EcoThreatV3::InsideAnyObstacle(X, Y, Discs.data(), static_cast<std::int32_t>(Discs.size() / 3), BodyR); };
	AddInfo(FString::Printf(TEXT("원판 (%.4f, %.4f, %.4f) · 사슴 0 (%.4f, %.4f) · 사슴 2 (%.4f, %.4f) · 늑대 0 (%.4f, %.4f)"), Discs.size() >= 3 ? Discs[0] : 0.0,
							Discs.size() >= 3 ? Discs[1] : 0.0, Discs.size() >= 3 ? Discs[2] : 0.0, D[0].Pos.X, D[0].Pos.Y, D[2].Pos.X, D[2].Pos.Y, Wolf[0].State.PosX,
							Wolf[0].State.PosY));
	TestEqual(TEXT("세계 원판 = 놓은 줄기 하나"), Ctx->Sim.Config.Obstacles.Num(), 1);
	TestTrue(TEXT("시작 자리는 원판(반지름 + 몸) 안이었다"), Inside(Start[0].X, Start[0].Y) && Inside(Start[2].X, Start[2].Y) && Inside(30.0, 29.9));
	TestTrue(TEXT("원판 안 사슴 둘 → 밖으로, 보간 앞 자리도 같은 곳"), !Inside(D[0].Pos.X, D[0].Pos.Y) && !Inside(D[2].Pos.X, D[2].Pos.Y) && D[0].PrevPos.X == D[0].Pos.X
																		  && D[0].PrevPos.Y == D[0].Pos.Y && D[2].PrevPos.X == D[2].Pos.X && D[2].PrevPos.Y == D[2].Pos.Y);
	TestTrue(TEXT("원판 안 늑대 → 밖으로, 보간 앞 자리도"), !Inside(Wolf[0].State.PosX, Wolf[0].State.PosY) && Wolf[0].PrevX == Wolf[0].State.PosX
														   && Wolf[0].PrevY == Wolf[0].State.PosY);
	TestTrue(TEXT("밀린 거리는 원판 둘레 근처 (1 단위 밑)"), FMath::Sqrt(FMath::Square(D[0].Pos.X - 30.0) + FMath::Square(D[0].Pos.Y - 30.0)) < 1.0);
	TestTrue(TEXT("원판 밖 사슴·늑대 자리·보간 앞 자리 그대로"), D[1].Pos.X == 10.0 && D[1].Pos.Y == 50.0 && D[1].PrevPos.X == 1.0 && D[1].PrevPos.Y == 1.0
																 && Wolf[1].State.PosX == 50.0 && Wolf[1].State.PosY == 10.0 && Wolf[1].PrevX == 2.0);
	bool bDetourCleared = true;
	for (const EcoWorldV3::FHerbBody& B : D)
	{
		bDetourCleared = bDetourCleared && B.Detour.Left == 0 && B.Detour.Side == 0 && B.Detour.Steps == 0;
	}
	for (const EcoWorldV3::FThreatAgent& A : Wolf)
	{
		bDetourCleared = bDetourCleared && A.State.Detour.Left == 0;
	}
	TestTrue(TEXT("그 지역 돌아가기 상태를 모두 지운다"), bDetourCleared);
	TestTrue(TEXT("밀어내기 기록 (옮김 3, 실패 0)"), Ctx->Sim.Stats.ObstaclePushMoved == 3 && Ctx->Sim.Stats.ObstaclePushFailed == 0);
	TestTrue(TEXT("거울 칸: 나무 표시·그리기 높이·레벨 나무 무대·원판 대조 줄 다시"), Ctx->ObstacleIsTree.Num() == 1 && Ctx->ObstacleIsTree[0] == 1
																					 && Ctx->ObstacleGroundZ.Num() == 1 && Ctx->bLevelTrees && !Ctx->bObsParityDiscsLogged);
	TestTrue(TEXT("레벨 읽기 기록 = 줄기 하나 (표 밖)"), Ctx->ObstacleScan.Num() == 1 && Ctx->ObstacleScan.LevelTrees == 1 && Ctx->ObstacleScan.LevelTreesUnmatched == 1);
	return true;
}

// -----------------------------------------------------------------------------
// 감시 끔 (eco.IntegratedV3.EnvWatch 0) = 옛 동작
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3EnvWatchOffTest,
	"AdaptiveEcosystem.Policy.V3.EnvWatch.Off",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3EnvWatchOffTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3EnvWatchTestImpl;
	const FString Saved = GetCVar(TEXT("eco.IntegratedV3.EnvWatch"));
	ON_SCOPE_EXIT
	{
		SetCVar(TEXT("eco.IntegratedV3.EnvWatch"), *Saved);
	};
	TestEqual(TEXT("기본 켬"), Saved, FString(TEXT("1")));
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World) || !TestNotNull(TEXT("바닥"), Floor(*W.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ)))
	{
		return false;
	}
	UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
	FEcoV3RegionContext* Ctx = ForestContext(*this, *W.World, 37560, Sub);
	if (!Ctx)
	{
		return false;
	}
	SetCVar(TEXT("eco.IntegratedV3.EnvWatch"), TEXT("0"));
	TestFalse(TEXT("IsEnvWatchEnabled 거짓"), FSub::IsEnvWatchEnabled());
	FPair P;
	if (!TestTrue(TEXT("Play 중 나무 짝"), PlaceTree(*W.World, FSub::MakeLevelTree(30.0, 30.0, 2.0, 0.0), TEXT("Forest_T00"), P)))
	{
		return false;
	}
	TestFalse(TEXT("감시 끔: 읽지 않는다"), Sub->PollEnvironment(true));
	TestFalse(TEXT("감시 끔: 대기 변화 없음"), Sub->HasPendingEnvChange());
	Sub->ApplyEnvChange({}, {});
	TestTrue(TEXT("감시 끔: 원판·판 그대로 (Play 시작 때 고정)"), Ctx->Sim.Config.Obstacles.Num() == 0 && Sub->GetEnvRevision() == 0 && Sub->GetEnvChanges().IsEmpty());

	// 켜면 같은 나무를 본다 — 대기 중에 다시 끄면 넣지 않는다
	SetCVar(TEXT("eco.IntegratedV3.EnvWatch"), TEXT("1"));
	TestTrue(TEXT("다시 켜면 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	SetCVar(TEXT("eco.IntegratedV3.EnvWatch"), TEXT("0"));
	Sub->ApplyEnvChange({}, {});
	TestTrue(TEXT("대기 중에 끄면 넣지 않는다 (대기도 버린다)"), Ctx->Sim.Config.Obstacles.Num() == 0 && Sub->GetEnvRevision() == 0 && !Sub->HasPendingEnvChange());
	return true;
}

// -----------------------------------------------------------------------------
// 자동·주기 스냅숏 (EcoV3Snapshot.cpp)
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3EnvWatchAutoSnapshotTest,
	"AdaptiveEcosystem.Policy.V3.EnvWatch.AutoSnapshot",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3EnvWatchAutoSnapshotTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3EnvWatchTestImpl;
	// 10-27: 기본 규칙이 '큰 변화만'(eco.IntegratedV3.AutoSnapshotRule 1)으로 바뀌어, 이 시험(판마다 한 번 = 옛 동작)은 규칙 0 을 걸고 끝에 되돌린다.
	// 큰 변화 규칙은 AutoSnapshot.BigRule (순수)·EnvWatch.BigRule (서브시스템) 이 본다
	const TCHAR* const Vars[7] = {TEXT("eco.IntegratedV3.AutoSnapshot"),  TEXT("eco.IntegratedV3.AutoSnapshotOut"), TEXT("eco.IntegratedV3.AutoSnapshotSettle"),
								  TEXT("eco.IntegratedV3.SnapshotEvery"), TEXT("eco.IntegratedV3.WeatherBarren"),   TEXT("eco.IntegratedV3.WeatherForest"),
								  TEXT("eco.IntegratedV3.AutoSnapshotRule")};
	FString Saved[7];
	for (int32 i = 0; i < 7; ++i)
	{
		Saved[i] = GetCVar(Vars[i]);
	}
	const FString Dir = FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("Automation"), TEXT("EcoV3EnvSnapshots")));
	IFileManager::Get().DeleteDirectory(*Dir, /*RequireExists*/ false, /*Tree*/ true);
	ON_SCOPE_EXIT
	{
		for (int32 i = 0; i < 7; ++i)
		{
			SetCVar(Vars[i], *Saved[i]);
		}
		IFileManager::Get().DeleteDirectory(*Dir, false, true);
	};
	TestEqual(TEXT("기본: 자동 스냅숏 -1 (AutoAdapt 따름)"), Saved[0], FString(TEXT("-1")));
	TestEqual(TEXT("기본: 자동 스냅숏 규칙 1 (큰 변화만)"), Saved[6], FString(TEXT("1")));
	SetCVar(Vars[0], TEXT("1"));
	SetCVar(Vars[1], *Dir);
	SetCVar(Vars[2], TEXT("3"));
	SetCVar(Vars[3], TEXT("0"));
	SetCVar(Vars[4], TEXT(""));
	SetCVar(Vars[5], TEXT(""));   // 숲 날씨는 Play 시작 값(빈 값) 그대로 — 바뀜은 메마른 땅 하나
	SetCVar(Vars[6], TEXT("0"));  // 옛 동작 (판마다)
	auto Files = [&Dir](const TCHAR* Pattern)
	{
		TArray<FString> Found;
		IFileManager::Get().FindFiles(Found, *FPaths::Combine(Dir, Pattern), /*Files*/ true, /*Directories*/ false);
		Found.Sort();
		return Found;
	};

	EcoTest::FScopedTestWorld W;
	UEcoPolicyV3IntegratedSubsystem* Sub = W.World ? W.World->GetSubsystem<UEcoPolicyV3IntegratedSubsystem>() : nullptr;
	if (!TestNotNull(TEXT("통합 서브시스템"), Sub))
	{
		return false;
	}
	FEcoV3IntegratedSettings S;
	S.Seed = 37800;
	Sub->ActivateForTest(S, false);
	const std::vector<FCoverInput> Covers = EcoWorldV3::QuadCovers(S.StageSizeUnits, 6.0);
	Sub->AddContext(TEXT("Forest"), 1, FVector::ZeroVector, FSub::MakeRegionWorldConfig(S, 1, 16, 2, Covers, TEXT("Forest")), 16, 2);
	FEcoV3RegionContext* Barren =
		Sub->AddContext(TEXT("Barren"), 0, FVector(0.0, -80000.0, 0.0), FSub::MakeRegionWorldConfig(S, 0, 16, 2, Covers, TEXT("Barren")), 16, 2);
	for (int32 s = 0; s < 5; ++s)
	{
		Sub->MaybeAutoSnapshot();
		Sub->FinishGlobalStep();
	}
	TestEqual(TEXT("환경이 그대로면 자동 스냅숏 없음"), Files(TEXT("*.json")).Num(), 0);

	// 1. 환경 바뀜 #1 (전역 스텝 5) → 3 초 = 22.5 스텝 → 처음 넘는 경계 스텝 28 에서 한 번
	SetCVar(Vars[4], TEXT("rain"));
	Sub->PollEnvironment(true);
	Sub->ApplyEnvChange({}, {});
	const int64 T0 = Sub->GetGlobalStep();
	TestTrue(TEXT("환경 판 1 (메마른 땅 비)"), Sub->GetEnvRevision() == 1 && Barren && Barren->Sim.Config.Weather.Kind == EcoWorldV3::kWeatherRain);
	int64 WrittenAt = -1;
	for (int32 s = 0; s <= 40; ++s)
	{
		const int32 Before = Files(TEXT("*.json")).Num();
		Sub->MaybeAutoSnapshot();
		if (WrittenAt < 0 && Files(TEXT("*.json")).Num() > Before)
		{
			WrittenAt = Sub->GetGlobalStep();
		}
		Sub->FinishGlobalStep();
	}
	const FString Name1 = FString::Printf(TEXT("eco_v3_snapshot_s37800_t%lld_e1.json"), static_cast<long long>(T0 + 23));
	TestEqual(TEXT("바뀜 뒤 23 스텝 (3.07 초)에서"), WrittenAt, T0 + 23);
	TestTrue(*FString::Printf(TEXT("판마다 한 번 — 파일 하나 %s"), *Name1), Files(TEXT("*.json")).Num() == 1 && Files(TEXT("*.json"))[0] == Name1);
	TestEqual(TEXT(".tmp 가 남지 않는다 (바꿔 끼우기)"), Files(TEXT("*.tmp")).Num(), 0);
	{
		const TSharedPtr<FJsonObject> Root = ReadJson(FPaths::Combine(Dir, Name1));
		const TSharedPtr<FJsonObject>* Env = nullptr;
		if (TestTrue(TEXT("스냅숏 'env' 블록"), Root.IsValid() && Root->TryGetObjectField(TEXT("env"), Env) && Env && Env->IsValid()))
		{
			const FJsonObject& E = **Env;
			TestTrue(TEXT("env: watch·revision 1·changed_step·first_changed_step = 바뀐 스텝·trigger env_change"),
					 E.GetBoolField(TEXT("watch")) && static_cast<int32>(E.GetNumberField(TEXT("revision"))) == 1
						 && static_cast<int64>(E.GetNumberField(TEXT("changed_step"))) == T0 && static_cast<int64>(E.GetNumberField(TEXT("first_changed_step"))) == T0
						 && E.GetStringField(TEXT("trigger")) == TEXT("env_change"));
			const TArray<TSharedPtr<FJsonValue>>& Changes = E.GetArrayField(TEXT("changes"));
			if (TestEqual(TEXT("env.changes 한 줄"), Changes.Num(), 1))
			{
				const TSharedPtr<FJsonObject> C = Changes[0]->AsObject();
				TestTrue(TEXT("changes[0] = 판 1·스텝·메마른 땅·weather·'맑음→비 1.00'·cvar 출처"),
						 static_cast<int32>(C->GetNumberField(TEXT("revision"))) == 1 && static_cast<int64>(C->GetNumberField(TEXT("step"))) == T0
							 && C->GetStringField(TEXT("region")) == TEXT("Barren") && C->GetStringField(TEXT("kind")) == TEXT("weather")
							 && C->GetStringField(TEXT("detail")) == TEXT("맑음→비 1.00") && C->GetStringField(TEXT("source")) == TEXT("cvar:eco.IntegratedV3.WeatherBarren"));
			}
		}
		bool bTrunks = Root.IsValid();
		bool bRain = false;
		if (Root.IsValid())
		{
			for (const TSharedPtr<FJsonValue>& R : Root->GetArrayField(TEXT("regions")))
			{
				const TSharedPtr<FJsonObject> O = R->AsObject();
				double Trunks = -1.0;
				bTrunks = bTrunks && O->GetObjectField(TEXT("obstacles"))->TryGetNumberField(TEXT("level_trunks"), Trunks) && Trunks == 0.0;
				bRain = bRain
						|| (O->GetStringField(TEXT("region")) == TEXT("Barren")
							&& O->GetObjectField(TEXT("world"))->GetObjectField(TEXT("weather"))->GetStringField(TEXT("kind")) == TEXT("rain"));
			}
		}
		TestTrue(TEXT("지역마다 obstacles.level_trunks (0)"), bTrunks);
		TestTrue(TEXT("메마른 땅 세계 설정 날씨 = rain (파이썬이 읽는 칸)"), bRain);
	}

	// 2. 환경 바뀜 #2 → 둘째 파일 (_e2), 바뀜 두 줄
	SetCVar(Vars[4], TEXT("snow:0.5"));
	Sub->PollEnvironment(true);
	Sub->ApplyEnvChange({}, {});
	const int64 T1 = Sub->GetGlobalStep();
	for (int32 s = 0; s <= 30; ++s)
	{
		Sub->MaybeAutoSnapshot();
		Sub->FinishGlobalStep();
	}
	const FString Name2 = FString::Printf(TEXT("eco_v3_snapshot_s37800_t%lld_e2.json"), static_cast<long long>(T1 + 23));
	TestTrue(TEXT("판 2 → 둘째 파일"), Files(TEXT("*.json")).Num() == 2 && Files(TEXT("*.json")).Contains(Name2));
	{
		const TSharedPtr<FJsonObject> Root = ReadJson(FPaths::Combine(Dir, Name2));
		const TSharedPtr<FJsonObject>* Env = nullptr;
		TestTrue(TEXT("둘째: revision 2·바뀜 두 줄·처음 바뀐 스텝 그대로"),
				 Root.IsValid() && Root->TryGetObjectField(TEXT("env"), Env) && static_cast<int32>((*Env)->GetNumberField(TEXT("revision"))) == 2
					 && (*Env)->GetArrayField(TEXT("changes")).Num() == 2 && static_cast<int64>((*Env)->GetNumberField(TEXT("first_changed_step"))) == T0
					 && static_cast<int64>((*Env)->GetNumberField(TEXT("changed_step"))) == T1);
	}

	// 3. 주기 1 초: 켠 때부터 1·2·3 초 (스텝 +8·+15·+23) — 24 경계에 3 번, 계기 periodic
	SetCVar(Vars[3], TEXT("1"));
	int32 Periodic = 0;
	int32 PeriodicTrigger = 0;
	for (int32 s = 0; s < 24; ++s)
	{
		const TArray<FString> Before = Files(TEXT("*.json"));
		Sub->MaybeAutoSnapshot();
		for (const FString& F : Files(TEXT("*.json")))
		{
			if (!Before.Contains(F))
			{
				++Periodic;
				const TSharedPtr<FJsonObject> Root = ReadJson(FPaths::Combine(Dir, F));
				const TSharedPtr<FJsonObject>* Env = nullptr;
				PeriodicTrigger += Root.IsValid() && Root->TryGetObjectField(TEXT("env"), Env) && (*Env)->GetStringField(TEXT("trigger")) == TEXT("periodic") ? 1 : 0;
			}
		}
		Sub->FinishGlobalStep();
	}
	TestEqual(TEXT("주기 1 초: 24 경계(3.2 초)에 3 번"), Periodic, 3);
	TestEqual(TEXT("주기 스냅숏 계기 periodic"), PeriodicTrigger, 3);
	TestEqual(TEXT(".tmp 가 남지 않는다"), Files(TEXT("*.tmp")).Num(), 0);
	SetCVar(Vars[3], TEXT("0"));
	const int32 AfterOff = Files(TEXT("*.json")).Num();
	for (int32 s = 0; s < 30; ++s)
	{
		Sub->MaybeAutoSnapshot();
		Sub->FinishGlobalStep();
	}
	TestEqual(TEXT("주기를 끄면 더 쓰지 않는다 (판도 그대로)"), Files(TEXT("*.json")).Num(), AfterOff);
	return true;
}

// -----------------------------------------------------------------------------
// 시험용 대역 (레벨 팀 작업 흉내 — 세계 규칙 아님)
// -----------------------------------------------------------------------------

IMPLEMENT_SIMPLE_AUTOMATION_TEST(
	FEcoV3EnvWatchTestStandInsTest,
	"AdaptiveEcosystem.Policy.V3.EnvWatch.TestStandIns",
	EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FEcoV3EnvWatchTestStandInsTest::RunTest(const FString& Parameters)
{
	using namespace EcoV3EnvWatchTestImpl;
	IConsoleManager& CM = IConsoleManager::Get();
	TestTrue(TEXT("명령 Test.AddTrees·Test.RemoveTrees·Test.At·EnvInfo"), CM.FindConsoleObject(TEXT("eco.IntegratedV3.Test.AddTrees"))
																			  && CM.FindConsoleObject(TEXT("eco.IntegratedV3.Test.RemoveTrees"))
																			  && CM.FindConsoleObject(TEXT("eco.IntegratedV3.Test.At"))
																			  && CM.FindConsoleObject(TEXT("eco.IntegratedV3.EnvInfo")));
	EcoTest::FScopedTestWorld W;
	if (!TestNotNull(TEXT("시험 월드"), W.World) || !TestNotNull(TEXT("바닥"), Floor(*W.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ)))
	{
		return false;
	}
	UWorld& World = *W.World;
	UEcoPolicyV3IntegratedSubsystem* Sub = nullptr;
	FEcoV3RegionContext* Ctx = ForestContext(*this, World, 37900, Sub);
	if (!Ctx)
	{
		return false;
	}
	const FName TreeTag = FSub::LevelTreeTag();
	const FName TrunkTag = FSub::LevelTrunkTag();

	// 1. Test.AddTrees: 명령과 같은 꼬리표 짝, 무대 안 빈자리
	CM.ProcessUserConsoleInput(TEXT("eco.IntegratedV3.Test.AddTrees Forest 3 7"), *GLog, &World);
	TestTrue(TEXT("짝 셋 (나무 3 · 줄기 막이 3)"), CountTagged(World, TreeTag) == 3 && CountTagged(World, TrunkTag) == 3);
	int32 BadPair = 0;
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		if (!It->ActorHasTag(TrunkTag))
		{
			continue;
		}
		const AActor* Tree = It->GetAttachParentActor();
		const UStaticMeshComponent* C = Cast<AStaticMeshActor>(*It) ? Cast<AStaticMeshActor>(*It)->GetStaticMeshComponent() : nullptr;
		const UStaticMeshComponent* Tc = Cast<AStaticMeshActor>(Tree) ? Cast<AStaticMeshActor>(Tree)->GetStaticMeshComponent() : nullptr;
		bool bId = false;
		for (const FName& Tag : It->Tags)
		{
			bId = bId || (Tag.ToString().StartsWith(TEXT("EcoV3TreeId_Forest_T")) && Tree && Tree->ActorHasTag(Tag));
		}
		BadPair += (Tree && Tree->ActorHasTag(TreeTag) && bId && C && Tc && It->IsHidden() && C->GetCollisionResponseToChannel(ECC_WorldStatic) == ECR_Block
					&& Tc->GetCollisionEnabled() == ECollisionEnabled::NoCollision)
					   ? 0
					   : 1;
	}
	TestEqual(TEXT("짝: 줄기 막이가 나무에 붙음·같은 짝 꼬리표 EcoV3TreeId_Forest_T<n>·줄기 숨김 BlockAll·나무 충돌 없음"), BadPair, 0);
	TestTrue(TEXT("읽기 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	Sub->ApplyEnvChange({}, {});
	const std::vector<double> Placed = Ctx->Sim.Config.Obstacles.Discs;
	TestEqual(TEXT("세계 원판 3"), Num3(Placed), 3);
	TestTrue(TEXT("바뀜 '나무 0→3 (+3 −0)' 출처 test"), Sub->GetEnvChanges().Num() == 1 && Sub->GetEnvChanges()[0].Detail == TEXT("나무 0→3 (+3 −0)")
															&& Sub->GetEnvChanges()[0].Source == TEXT("test"));
	int32 BadSpot = 0;
	const double Wall = EcoTreeLayoutV3::kWallClearM * 100.0 / EcoRepertoireV3::kUnitCm;
	const double Clear = EcoTreeLayoutV3::kCoverClearM * 100.0 / EcoRepertoireV3::kUnitCm;
	for (int32 k = 0; k < Num3(Placed); ++k)
	{
		const double X = Placed[3 * k];
		const double Y = Placed[3 * k + 1];
		const double R = Placed[3 * k + 2];
		BadSpot += (X >= Wall + R - 1e-6 && Y >= Wall + R - 1e-6 && X <= kSize - Wall - R + 1e-6 && Y <= kSize - Wall - R + 1e-6) ? 0 : 1;
		for (const FCoverInput& Cv : Ctx->Sim.Config.Covers)
		{
			BadSpot += FMath::Sqrt(FMath::Square(X - Cv.X) + FMath::Square(Y - Cv.Y)) >= Cv.Radius + Clear + R - 1e-6 ? 0 : 1;
		}
		for (int32 j = k + 1; j < Num3(Placed); ++j)
		{
			BadSpot += FMath::Sqrt(FMath::Square(X - Placed[3 * j]) + FMath::Square(Y - Placed[3 * j + 1])) - R - Placed[3 * j + 2] >= 1.5 - 1e-6 ? 0 : 1;
		}
		BadSpot += (R >= EcoTreeLayoutV3::kTrunkRadiusMeshCm * EcoTreeLayoutV3::kScaleLo / EcoRepertoireV3::kUnitCm - 1e-3
					&& R <= EcoTreeLayoutV3::kTrunkRadiusMeshCm * EcoTreeLayoutV3::kScaleHi / EcoRepertoireV3::kUnitCm + 1e-3)
					   ? 0
					   : 1;
	}
	TestEqual(TEXT("자리: 벽 4 m·은신처 원 + 2 m·줄기 틈 3 m 밖, 크기 = 배치 표 범위"), BadSpot, 0);
	{
		// 같은 씨 = 같은 자리 (결정적)
		EcoTest::FScopedTestWorld W2;
		UEcoPolicyV3IntegratedSubsystem* Sub2 = nullptr;
		FEcoV3RegionContext* Ctx2 = W2.World && Floor(*W2.World, kSize * EcoRepertoireV3::kUnitCm, kTopZ) ? ForestContext(*this, *W2.World, 37901, Sub2) : nullptr;
		if (TestNotNull(TEXT("시험 월드 2"), Ctx2))
		{
			FString Message;
			TestEqual(TEXT("TestAddTrees 3 그루"), Sub2->TestAddTrees(TEXT("Forest"), 3, TOptional<int32>(7), Message), 3);
			Sub2->PollEnvironment(true);
			Sub2->ApplyEnvChange({}, {});
			TestTrue(TEXT("같은 씨 = 같은 원판 (세션 시드와 무관)"), Ctx2->Sim.Config.Obstacles.Discs == Placed);
		}
	}

	// 2. Test.RemoveTrees: 나중 것부터
	CM.ProcessUserConsoleInput(TEXT("eco.IntegratedV3.Test.RemoveTrees Forest 2"), *GLog, &World);
	TestTrue(TEXT("짝 하나 남음"), CountTagged(World, TreeTag) == 1 && CountTagged(World, TrunkTag) == 1);
	bool bFirstLeft = false;
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		bFirstLeft = bFirstLeft || (It->ActorHasTag(TrunkTag) && It->ActorHasTag(TEXT("EcoV3TreeId_Forest_T00")));
	}
	TestTrue(TEXT("남은 짝 = 처음 놓은 T00"), bFirstLeft);
	TestTrue(TEXT("읽기 → 대기 변화"), Sub->PollEnvironment(true) && Sub->HasPendingEnvChange());
	Sub->ApplyEnvChange({}, {});
	TestTrue(TEXT("세계 원판 1 · '나무 3→1 (+0 −2)'"), Ctx->Sim.Config.Obstacles.Num() == 1 && Sub->GetEnvChanges().Last().Detail == TEXT("나무 3→1 (+0 −2)"));

	// 3. Test.At: 시뮬레이션 1 초(스텝 7.5 → 경계 8)가 되면 한 번
	CM.ProcessUserConsoleInput(TEXT("eco.IntegratedV3.Test.At 1.0 eco.IntegratedV3.Test.AddTrees Forest 1 11; eco.IntegratedV3.Test.AddTrees Forest 1 12"), *GLog,
							   &World);
	if (TestEqual(TEXT("예약 하나"), Sub->GetTestSchedule().Num(), 1))
	{
		TestEqual(TEXT("예약 명령 (';' 그대로)"), Sub->GetTestSchedule()[0].Commands,
				  FString(TEXT("eco.IntegratedV3.Test.AddTrees Forest 1 11; eco.IntegratedV3.Test.AddTrees Forest 1 12")));
	}
	const int64 Start = Sub->GetGlobalStep();
	int64 RanAt = -1;
	for (int32 s = 0; s < 12; ++s)
	{
		const int32 Before = CountTagged(World, TrunkTag);
		Sub->RunTestSchedule();
		if (RanAt < 0 && CountTagged(World, TrunkTag) > Before)
		{
			RanAt = Sub->GetGlobalStep();
		}
		Sub->FinishGlobalStep();
	}
	TestEqual(TEXT("1 초가 되는 첫 경계 (전역 스텝 8)에서"), RanAt, Start + 8);
	TestTrue(TEXT("명령 둘 → 짝 셋 · 예약 비움 (한 번만)"), CountTagged(World, TrunkTag) == 3 && Sub->GetTestSchedule().IsEmpty());

	// 4. 명령줄 -EcoV3TestAt= -EcoV3TestCmd= (쌍 여러 개, 따옴표 안 ';'·공백 그대로)
	{
		const TArray<FEcoV3TestAt> SavedQueue = FSub::CommandLineTestAts();
		ON_SCOPE_EXIT
		{
			FSub::CommandLineTestAts() = SavedQueue;   // 프로세스에 하나 — 다른 Play 에 남지 않게
		};
		FSub::ApplyCommandLineToConsole(
			TEXT("-EcoV3TestAt=2.5 -EcoV3TestCmd=\"eco.IntegratedV3.EnvInfo; eco.IntegratedV3.Test.AddTrees Forest 1\" -EcoV3TestAt=4 -EcoV3TestCmd=\"eco.IntegratedV3.EnvInfo\""));
		const TArray<FEcoV3TestAt>& Q = FSub::CommandLineTestAts();
		TestTrue(TEXT("명령줄 예약 둘 (2.5 초: 명령 둘, 4 초: 명령 하나)"),
				 Q.Num() == 2 && Q[0].Seconds == 2.5 && Q[0].Commands == TEXT("eco.IntegratedV3.EnvInfo; eco.IntegratedV3.Test.AddTrees Forest 1") && Q[1].Seconds == 4.0
					 && Q[1].Commands == TEXT("eco.IntegratedV3.EnvInfo"));
	}

	// 5. EnvInfo: 머리 줄 + 지역마다 한 줄
	CM.ProcessUserConsoleInput(TEXT("eco.IntegratedV3.EnvInfo"), *GLog, &World);
	TestEqual(TEXT("EnvInfo 줄 = 1 + 지역 수"), Sub->EnvInfoLines().Num(), 1 + Sub->NumContexts());
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS

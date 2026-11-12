// R9 데모 플레이어 — 켜기·무대 자리·프레임 원천·녹화·글자 (설명은 EcoR9DemoSubsystem.h).

#include "EcoR9DemoSubsystem.h"

#include "EcoR9DemoState.h"

#include "AI/Policy/EcoV3ObserverCamera.h"
#include "Camera/CameraActor.h"
#include "CanvasItem.h"
#include "ContentStreaming.h"
#include "ShaderCompiler.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Debug/DebugDrawService.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/StaticMesh.h"
#include "Engine/TargetPoint.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/HUD.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PawnMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerStart.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "HAL/PlatformTime.h"
#include "Landscape.h"
#include "LandscapeProxy.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"
#include "UnrealClient.h"
#include "UnrealEngine.h"
#include "WorldPartition/WorldPartition.h"
#include "WorldPartition/WorldPartitionRuntimeCell.h"
#include "WorldPartition/WorldPartitionRuntimeHash.h"
#include "WorldPartition/WorldPartitionStreamingSource.h"

#include <limits>

DEFINE_LOG_CATEGORY(LogEcoR9Demo);

namespace EcoR9DemoSubsystemImpl
{
	static TAutoConsoleVariable<int32> CVarDemo(TEXT("eco.R9Demo"), 0,
		TEXT("R9 데모 플레이어 (EcoR9DemoSubsystem.h): 0 끔(기본) · 1 실시간 (eco.R9Demo.Brains 두뇌 폴더) · 2 재생 (eco.R9Demo.Replay 파일). ")
		TEXT("명령 없이 늘 켜려면 이 PC 의 Config/UserEngine.ini [ConsoleVariables] 에 eco.R9Demo=1. Play 중에 바꾸면 그 자리에서 시작·정지한다. ")
		TEXT("명령줄 -EcoR9Demo=<폴더>·-EcoR9Replay=<파일> 이 있으면 그것이 먼저다. 맵 제한 없음 — 기본은 그 맵의 땅 전체에 사슴·늑대·멧돼지를 푼다 ")
		TEXT("(eco.R9Demo.Area). 팀 생태 장치가 있어도 건드리지 않고 따로 돈다."),
		FConsoleVariableDelegate::CreateStatic(&UEcoR9DemoSubsystem::OnDemoCVarChanged));
	static TAutoConsoleVariable<FString> CVarBrains(TEXT("eco.R9Demo.Brains"), TEXT(""), TEXT("R9 데모 실시간 판 두뇌 폴더 ({deer,wolf,boar}.r9brain). 비면 <프로젝트>/Saved/R9Demo/brains."));
	static TAutoConsoleVariable<FString> CVarScene(TEXT("eco.R9Demo.Scene"), TEXT(""), TEXT("R9 데모 실시간 판 장면 파일 (비면 <두뇌 폴더>/scene.txt)."));
	static TAutoConsoleVariable<FString> CVarReplay(TEXT("eco.R9Demo.Replay"), TEXT(""), TEXT("R9 데모 재생 판 파일 (.r9rp — 파이썬 실행 기록). 비면 <프로젝트>/Saved/R9Demo/replay/demo.r9rp."));
	static TAutoConsoleVariable<FString> CVarAt(TEXT("eco.R9Demo.At"), TEXT(""),
		TEXT("R9 데모 무대 가운데 'x,y' (월드 m, 예: 783,-168). 비면 플레이어 시작점 둘레에서 트인 평지를 스스로 고른다. PIE 는 Play 전에 (명령줄 -EcoR9DemoAt= 와 같음)."));
	static TAutoConsoleVariable<FString> CVarPolicy(TEXT("eco.R9Demo.Policy"), TEXT("sample"),
		TEXT("R9 데모 실시간 판 행동 고르기: sample = 확률대로 (학습 때와 같음) · argmax = 가장 높은 칸."));
	static TAutoConsoleVariable<float> CVarSpeed(TEXT("eco.R9Demo.Speed"), 1.0f, TEXT("R9 데모 시간 배율 (0 = 멈춤). 보기만 바뀐다 — 스텝 규칙은 그대로."));
	static TAutoConsoleVariable<int32> CVarText(TEXT("eco.R9Demo.Text"), 1, TEXT("R9 데모 오른쪽 위 글 묶음 (0 = 모두 끔). H 키는 그 안의 단축키 목록만 숨기고 보인다 (옛 관찰 카메라와 같음)."));
	static TAutoConsoleVariable<int32> CVarCam(TEXT("eco.R9Demo.Cam"), 5,
		TEXT("R9 데모 카메라 (키 숫자와 같다 — 옛 관찰 카메라 꼴, EcoR9DemoCam.h): 0 자유 카메라 · 1 늑대 시점 · 2 사슴 시점 · 3 탑뷰 · 4 쿼터뷰 · ")
			TEXT("5 자동 추적 (기본 — 사냥·물기·반격·사체 먹기) · 6 멧돼지 시점 · 8 물소 · 9 표범 · 10 여우 (J 키 — 동물 세계). 무대가 서는 때·바뀔 때 읽는다."));
	static TAutoConsoleVariable<FString> CVarOnlyMap(TEXT("eco.R9Demo.OnlyMap"), TEXT(""),
		TEXT("R9 데모를 Play 시작 때 저절로 켜는 맵 (빈 값 = 모든 맵). 맵 경로 '/Game/EcoTest/Maps/LV_EcoV3_Island'·오브젝트 경로·짧은 이름, 쉼표로 여럿. ")
			TEXT("다른 맵은 예전처럼 아무것도 만들지 않는다. 명령줄 -EcoR9Demo= 깃발과 Play 중 직접 친 eco.R9Demo 1 은 거르지 않는다."));
	static TAutoConsoleVariable<int32> CVarHpBars(TEXT("eco.R9Demo.HpBars"), 1, TEXT("R9 데모: 다친 늑대·멧돼지 체력 막대 (실시간 판만 체력을 안다)."));
	static TAutoConsoleVariable<int32> CVarGrass(TEXT("eco.R9Demo.Grass"), 1, TEXT("R9 데모: 보이는 풀 (먹이 격자 값 그대로 — 먹으면 줄고 다시 자람)."));
	static TAutoConsoleVariable<int32> CVarLoop(TEXT("eco.R9Demo.Loop"), 1, TEXT("R9 데모: 재생 끝·실시간 다시 시작 스텝에서 처음부터 다시."));
	static TAutoConsoleVariable<int32> CVarRestartSteps(TEXT("eco.R9Demo.RestartSteps"), 4500,
		TEXT("R9 데모 실시간 판: 이 스텝(기본 4,500 = 10 분)마다 새 시드로 다시 시작 (학습 세계는 5,000 스텝마다 바뀌었다)."));
	static TAutoConsoleVariable<int32> CVarDaylight(TEXT("eco.R9Demo.Daylight"), 1,
		TEXT("R9 데모: 팀 하늘 관리자(BP_SkyManager)는 해를 초당 약 10° 돌려 36 초마다 밤이 온다. 1(기본) = 데모 동안만 해 속도를 0 으로 두고 해를 낮 높이(55°)에 고정 · ")
		TEXT("0 = 팀 하늘 그대로. 실행 중 값만 바꾸고 저장하지 않으며, 끝나면 해 속도를 되돌린다."));
	constexpr double kDayPitch = -55.0;   // 해 높이 55° (낮 오후) [어림 — 보기 좋은 각도]
	static TAutoConsoleVariable<FString> CVarBodies(TEXT("eco.R9Demo.Bodies"), TEXT("jyu"),
		TEXT("R9 데모 사슴·늑대 몸: jyu = 조연우 BP_JYU_Deer/Wolf (먹기·두리번·웅크림 자세) · team = 팀 BP_EcoDeer/Wolf (걷기·뛰기·죽음만)."));
	// 맵 제한을 없애면서 (2026-11-12 22:30) 같은 에디터에서 eco.R9Demo 1 을 켜 둔 채 다른 팀 자동화 시험을 돌리면 그 시험 월드(/Temp/…)에도 데모가 낄 수 있다.
	// 자동화 시험 중에는 이 값이 1 일 때만 서브시스템을 만든다 (R9 데모 시험만 켠다)
	static TAutoConsoleVariable<int32> CVarAllowInTests(TEXT("eco.R9Demo.AllowInTests"), 0,
		TEXT("R9 데모: 자동화 시험이 도는 동안에는 이 값이 1 일 때만 데모를 만든다 (R9 데모 시험이 잠깐 켠다 — 다른 팀 시험 월드에 데모가 끼지 않게). 평소 Play 에는 상관없음."));

	// 맵 전체 땅 모드 (2026-11-13)
	static TAutoConsoleVariable<int32> CVarArea(TEXT("eco.R9Demo.Area"), 0,
		TEXT("R9 데모 세계 크기: 0 = 그 맵의 쓸 수 있는 땅 전체 (기본 — 4 m 로 훑은 땅 지도 위에 무리 자리 여럿) · 1 ~ 120 = 예전 한 무대 (학습 세계 120 m, 장면 파일 그대로) · ")
		TEXT("그 밖 = 시작점 둘레 그 크기(m) 정사각만 큰 세계로 (상한 4000). 시작할 때 읽는다 (명령줄 -EcoR9DemoArea=)."));
	static TAutoConsoleVariable<int32> CVarHerds(TEXT("eco.R9Demo.Herds"), 6,
		TEXT("R9 데모 맵 전체 땅: 무리 자리 수 (1 ~ 8). 땅 위에서 서로 먼 자리 — 맵이 작으면 그보다 적게 선다. 시작할 때 읽는다."));
	static TAutoConsoleVariable<FString> CVarPerHerd(TEXT("eco.R9Demo.PerHerd"), TEXT("24,2,8"),
		TEXT("R9 데모 맵 전체 땅: 무리 자리마다 '사슴,늑대,멧돼지' (기본 24,2,8 — 학습 세계 24·4·8 둘레, 늑대는 자리마다 한 쌍). 총수 상한 400. 시작할 때 읽는다."));
	// 동물 세계 (2026-11-13 05:00 — 물소·표범·여우)
	static TAutoConsoleVariable<int32> CVarFauna(TEXT("eco.R9Demo.Fauna"), 1,
		TEXT("R9 데모 동물 세계: 1 (기본) = <두뇌 폴더>/fauna/ 에 buffalo·leopard·fox.r9brain 과 scene.txt(파이썬 동물 세계 장면)가 다 있으면 물소·표범·여우도 함께 푼다 ")
		TEXT("(없거나 시작에 실패하면 세 종만). 0 = 늘 사슴·늑대·멧돼지만. 시작할 때 읽는다 (명령줄 -EcoR9Fauna=)."));
	static TAutoConsoleVariable<FString> CVarFaunaPerHerd(TEXT("eco.R9Demo.FaunaPerHerd"), TEXT("4,1,2"),
		TEXT("R9 데모 동물 세계 맵 전체 땅: 무리 자리마다 '물소,표범,여우' (기본 4,1,2 — 파이썬 동물 세계 세계당 물소 0~6 · 표범 0~2 · 여우 0~4 둘레). 시작할 때 읽는다."));
	static TAutoConsoleVariable<int32> CVarHideOthers(TEXT("eco.R9Demo.HideOthers"), 1,
		TEXT("R9 데모: 1 (기본) = 맵에 이미 있는 예전 v3·Fauna 동물 몸(표현 액터)·섬 무대 먼 표식을 데모 동안 숨긴다 (보이는 것만 — 그쪽 시뮬레이션·코드·에셋은 그대로, 끄면 되돌림). 0 = 그대로."));
	static TAutoConsoleVariable<float> CVarBodyNear(TEXT("eco.R9Demo.BodyNear"), 220.0f,
		TEXT("R9 데모 큰 세계: 카메라에서 이만큼(m) 안 개체만 동물 몸 액터를 띄운다 (나머지는 작은 표식 — 기존 섬 무대 먼 표식 꼴)."));
	static TAutoConsoleVariable<int32> CVarBodyBudget(TEXT("eco.R9Demo.BodyBudget"), 90, TEXT("R9 데모 큰 세계: 동물 몸 액터 상한 (가까운 차례)."));
	static TAutoConsoleVariable<float> CVarGrassRadius(TEXT("eco.R9Demo.GrassRadius"), 128.0f,
		TEXT("R9 데모 큰 세계: 풀을 그리는 카메라 둘레 반 변 (m, 32 ~ 400). 먹이 격자 값은 세계 전체에 있고 그리기만 줄인다."));
	static TAutoConsoleVariable<FString> CVarBoarMesh(TEXT("eco.R9Demo.BoarMesh"), TEXT(""),
		TEXT("R9 데모 멧돼지 몸 덮어쓰기: 스켈레탈 메시 경로 (예 /Game/AnimalVarietyPack/Pig/Meshes/SK_Pig.SK_Pig) 또는 표현 BP 클래스 경로 (…_C). ")
		TEXT("비면 /Game/AnimalVarietyPack/Pig → /Game/JYU/Fauna → /Game 차례로 Pig·Boar·Hog·Swine·villsvin 이름을 찾는다. 무대를 세울 때 읽는다."));
	constexpr double kWholeCellCm = 400.0;           // 땅 지도 칸 4 m (코어 칸 = 2 단위)
	constexpr double kWholeMaxSideCm = 400000.0;     // 맵 전체 땅 상한 4 km (코어 2000 단위) [어림 — 섬 2.7 km 를 덮고 격자 100 만 칸 안]
	constexpr double kWholeMarginCm = 5000.0;        // 땅 경계 둘레 여유 50 m (ISLAND_STAGE.md 3.1 과 같음)
	constexpr double kWholeStreamTimeout = 75.0;     // 맵 전체 불러오기 상한 (처음 Nanite 지형 짓기 포함)
	constexpr double kWholeSteep = 1.17;             // 큰 세계 가파름: 이웃 칸 기울기 > 1.17 (법선 Z < 0.65 — 팀 이동 제약·섬 무대 ISLAND_STAGE.md 3.2 와 같은 문턱)
	constexpr double kTreeTrunkCm = 300.0;           // 큰 세계 나무: 줄기 둘레 3 m 칸만 막힘 (섬 무대 숲 칸 규칙 ISLAND_STAGE.md 7.1)
	const FName kHerdTagR9(TEXT("EcoR9Herd"));       // 사람이 놓은 무리 자리 (TargetPoint 꼬리표)
	const FName kHerdTagV3(TEXT("EcoV3IslandHerd")); // 예전 섬 무대 무리 자리 꼬리표 (있으면 같이 씀)
	const TCHAR* const kTreeWords[] = {TEXT("pine"), TEXT("tree"), TEXT("spruce"), TEXT("birch"), TEXT("beech"), TEXT("oak"), TEXT("fir"), TEXT("palm"),
									   TEXT("cactus"), TEXT("maple"), TEXT("cedar"), TEXT("willow")};
	const TCHAR* const kRockWords[] = {TEXT("rock"), TEXT("cliff"), TEXT("boulder"), TEXT("stone")};

	/** '사슴,늑대,멧돼지' → 세 수 (틀리면 거짓). */
	bool ParseTriple(const FString& Text, int32 Out[3], bool bAllowZero = false)
	{
		TArray<FString> F;
		Text.ParseIntoArray(F, TEXT(","), true);
		if (F.Num() != 3)
		{
			return false;
		}
		for (int32 k = 0; k < 3; ++k)
		{
			F[k].TrimStartAndEndInline();
			if (!F[k].IsNumeric())
			{
				return false;
			}
			Out[k] = FMath::Clamp(FCString::Atoi(*F[k]), 0, 128);
		}
		return bAllowZero || Out[0] + Out[1] + Out[2] > 0;
	}

	bool AnyWordIn(const FString& Lower, TConstArrayView<const TCHAR*> Words)
	{
		for (const TCHAR* W : Words)
		{
			if (Lower.Contains(W))
			{
				return true;
			}
		}
		return false;
	}

	// 자동 고르기: 시작점 둘레 정사각을 고리마다 넓혀 훑는다 — 반 변 200 · 400 · 800 m [어림]. 앞 고리에서 (기존 생태를 피한) 자리를 찾으면 멈춘다
	constexpr int32 kNumRings = 3;
	constexpr double kRingHalfCm[kNumRings] = {20000.0, 40000.0, 80000.0};
	constexpr double kScanCellCm = 400.0;       // 칸 4 m (먹이 칸과 같다)
	constexpr double kStageMarginCm = 2000.0;   // 무대 둘레 여유 20 m [어림]
	constexpr float kStageStreamRadius = 25000.0f;
	constexpr double kStreamTimeout = 45.0;     // 처음 Nanite 지형 짓기 약 17 초 (ISLAND_STAGE.md:558)
	constexpr double kHeightStepCm = 100.0;
	constexpr double kHeightMarginCm = 4000.0;
	constexpr double kObstaclePadCm = 100.0;    // 나무·바위 상자 둘레 1 m
	constexpr double kObstacleClearCm = 30.0;   // 땅보다 30 cm 넘게 솟아야 걸리는 것 (바닥 메시·낮은 판은 아님) [어림]
	constexpr double kObstacleReachCm = 300.0;  // 땅 위 3 m 안까지 내려와야 걸리는 것 (높이 뜬 지붕·장식은 아님) [어림]
	constexpr double kGroundPieceCm = 1000.0;   // 이만큼(10 m) 넓은 메시가 그 칸의 땅으로 읽혔으면 그 칸에서는 걸리는 것이 아니다 (바닥 조각) [어림]
	constexpr double kTraceHalfCm = 1000000.0;  // 바닥 메시 선 검사 위아래 10 km
	constexpr double kNoGroundDropCm = 90.0;    // 땅을 하나도 못 찾으면 시작점(몸 가운데)에서 이만큼 아래를 바닥으로 [어림]

	/** 고리 Ring 을 불러올 스트리밍 반지름 — 훑는 정사각 모서리까지 + 20 m. */
	float RingStreamRadius(int32 Ring)
	{
		return static_cast<float>(kRingHalfCm[FMath::Clamp(Ring, 0, kNumRings - 1)] * 1.42 + 2000.0);
	}

	/**
	 * 맵에 이미 있는 생태 장치 — 무대는 이 둘레를 되도록 피한다 (섞여 보이지 않게). 클래스 이름으로 본다 (팀 헤더에 기대지 않음, 하위 클래스 포함).
	 * bPoint = 경계 상자 대신 자리 ± Pad. 통합 조정자(EcoCreatureIntegrationSpawner)는 자리가 뜻이 없어(원점에 둠) 빼고, 그 개체는 지역 상자·몸으로 잡는다.
	 * 식생 장(EcoVegetationField)은 섬 전체를 덮을 수 있어 빼고 서식지 상자(EcoVegetationHabitat)로 잡는다.
	 * Pad 40 m [어림]: 팀 동물도 같은 조연우 몸(BP_JYU_Deer/Wolf)이라, 지역 가장자리의 팀 사슴이 전체 보기 화면에서 데모 사슴처럼 보이지 않게
	 * 무대 가장자리와 지역 상자 사이를 40 m 넘게 띄운다 (11-05 섬 높이로 어림 흉내: JWJ 1102 은 69 m, JYU 섬은 49 m 떨어짐 — anymap/IMPL.md).
	 */
	struct FAvoidKind
	{
		const TCHAR* Class;
		double PadCm;
		bool bPoint;
	};
	const FAvoidKind kAvoidKinds[] = {
		{TEXT("EcologyRegion"), 4000.0, false},
		{TEXT("EcoVegetationHabitat"), 4000.0, false},
		{TEXT("EcoShelterAnchor"), 2000.0, false},              // 은신처·보호 은신처 (EcoRefugeHabitat)
		{TEXT("EcoSpeciesAIActivitySite"), 2000.0, true},
		{TEXT("EcoPolicyTestSpawner"), 4000.0, true},           // 시험·데모 생성기 (둘레에 개체를 낳음)
		{TEXT("EcoCreatureRepresentationActor"), 3000.0, true}, // 이미 있는 팀 동물 몸
		{TEXT("EcoSpeciesAIFixture"), 3000.0, true},            // 움직이는 먹잇감 시험 개체
		{TEXT("EcologyBootstrapTestActor"), 4000.0, true},      // 옛 생물(CreatureCharacter) 생성기
		{TEXT("CreatureCharacter"), 3000.0, true},              // 옛 생물 몸 (플레이어 몸은 뺀다)
		{TEXT("MassSpawner"), 4000.0, true},                    // 엔진 Mass 생성기 (둘레에 개체를 낳음)
	};
	constexpr double kRouteExtraPadCm = 2000.0;                 // 무리 이주 길: 길 폭 반 + 20 m

	/** 팀 생태 장치로 셀 클래스 (기록 줄·플레이어 몸 그대로 두기). */
	const TCHAR* const kTeamEcoClasses[] = {
		TEXT("EcoCreatureIntegrationSpawner"), TEXT("EcologyRegion"), TEXT("EcoVegetationHabitat"), TEXT("EcoVegetationField"), TEXT("EcoHerdMigrationRoute"),
		TEXT("EcoShelterAnchor"), TEXT("EcoPolicyTestSpawner"), TEXT("EcoMassNetworkBootstrap"), TEXT("EcoCreatureRepresentationActor"),
		TEXT("EcoSpeciesAIFixture"), TEXT("EcologyBootstrapTestActor"), TEXT("CreatureCharacter"), TEXT("MassSpawner")};

	/** 클래스 이름 표 → FName 표 (액터마다 FString 을 만들지 않고 이름 번호로 비교하려고). */
	template <int32 Num>
	TArray<FName> ToNames(const TCHAR* const (&Names)[Num])
	{
		TArray<FName> Out;
		Out.Reserve(Num);
		for (const TCHAR* Name : Names)
		{
			Out.Add(FName(Name));
		}
		return Out;
	}

	FString Utf8(const std::string& S)
	{
		return FString(UTF8_TO_TCHAR(S.c_str()));
	}

	std::string ToUtf8(const FString& S)
	{
		return std::string(TCHAR_TO_UTF8(*S));
	}

	/** 동물 세계 파일 (EcoR9DemoWhole.h PickFaunaFiles 결과를 언리얼 글로). */
	struct FR9FaunaFiles
	{
		FString Dir;
		FString ScenePath;
		FString BrainPath[EcoR9Demo::kNumSpecies];
		FString Line;   // 기록 줄
	};

	/** 이번 판을 동물 장면으로 시작해 볼까 (파일이 다 있나). 아니면 거짓 + 까닭 (Out.Line). */
	bool ChooseFaunaFiles(const FEcoR9DemoSettings& Set, FR9FaunaFiles& Out)
	{
		const EcoR9Demo::FR9FaunaPick P = EcoR9Demo::PickFaunaFiles(Set.Fauna, Set.bSceneExplicit, ToUtf8(Set.BrainDir),
																	  [](const std::string& Path) { return FPaths::FileExists(Utf8(Path)); });
		Out = FR9FaunaFiles();
		Out.Dir = Utf8(P.Dir);
		Out.ScenePath = Utf8(P.ScenePath);
		for (int32 k = 0; k < EcoR9Demo::kNumSpecies; ++k)
		{
			Out.BrainPath[k] = Utf8(P.BrainPath[k]);
		}
		Out.Line = Utf8(P.Why);
		return P.bUse;
	}

	bool ParseXY(const FString& Text, FVector2D& Out)
	{
		TArray<FString> F;
		Text.ParseIntoArray(F, TEXT(","), true);
		if (F.Num() != 2)
		{
			return false;
		}
		for (FString& Field : F)
		{
			Field.TrimStartAndEndInline();
		}
		if (!F[0].IsNumeric() || !F[1].IsNumeric())
		{
			return false;
		}
		Out = FVector2D(FCString::Atod(*F[0]), FCString::Atod(*F[1]));
		return true;
	}

	/**
	 * 땅 높이: 지형이 먼저 (충돌 높이장 — 물리 쿼리 아님, EcoV3IslandStage.cpp ScanIslandMask 와 같은 꼴), 지형이 없는 자리는 바닥 메시
	 * (WorldStatic 물체만 위→아래 선 검사 — 폰·동물·움직이는 물체는 안 잡힘. 물 몸체는 뺀다: 바다 충돌 상자가 바닥처럼 잡히지 않게).
	 * 그래서 지형 없는 일반 맵(바닥 메시만 있는 시험 맵 따위)에서도 높이를 읽는다. 못 읽으면 거짓.
	 */
	struct FGroundProbe
	{
		UWorld* World = nullptr;
		TArray<ALandscapeProxy*> Lands;
		mutable FCollisionQueryParams Params;   // 설 수 없는 것(트리거·겹침 전용 상자·시작부터 겹친 큰 상자)은 한 번 걸리면 빼 둔다
		FCollisionObjectQueryParams Objects;
		bool bTrace = true;

		FGroundProbe(UWorld& InWorld, const TArray<TWeakObjectPtr<AActor>>& Ignore, bool bInTrace = true)
			: World(&InWorld), Params(SCENE_QUERY_STAT(EcoR9DemoGround), /*bTraceComplex*/ false), Objects(ECC_WorldStatic), bTrace(bInTrace)
		{
			for (TActorIterator<ALandscape> It(&InWorld); It; ++It)
			{
				Lands.Add(*It);
			}
			if (Lands.IsEmpty())
			{
				for (TActorIterator<ALandscapeProxy> It(&InWorld); It; ++It)
				{
					Lands.Add(*It);
				}
			}
			for (const TWeakObjectPtr<AActor>& A : Ignore)
			{
				if (const AActor* Actor = A.Get())
				{
					Params.AddIgnoredActor(Actor);
				}
			}
		}

		/** 지형 높이만. */
		bool Land(double X, double Y, float& OutZ) const
		{
			for (const ALandscapeProxy* L : Lands)
			{
				if (const TOptional<float> H = L->GetHeightAtLocation(FVector(X, Y, 0.0)); H.IsSet())
				{
					OutZ = H.GetValue();
					return true;
				}
			}
			return false;
		}

		/**
		 * 지형, 없으면 바닥 메시. bOutMesh = 바닥 메시에서 읽음. OutComp·OutItem = 그 바닥 메시 컴포넌트와 인스턴스 번호 (그 칸에서는 걸리는 것으로 보지 않으려고).
		 * 바닥 = 폰이 설 수 있는 것(ECC_Pawn 을 막는 WorldStatic) — 겹침 전용 WorldStatic(OverlapAll 날씨 트리거 상자 따위)이나 카메라만 막는 부피는 빼고 다시 쏜다.
		 */
		bool At(double X, double Y, float& OutZ, bool* bOutMesh = nullptr, const UPrimitiveComponent** OutComp = nullptr, int32* OutItem = nullptr) const
		{
			if (bOutMesh)
			{
				*bOutMesh = false;
			}
			if (OutComp)
			{
				*OutComp = nullptr;
			}
			if (Land(X, Y, OutZ))
			{
				return true;
			}
			if (!bTrace || !World)
			{
				return false;
			}
			for (int32 Try = 0; Try < 8; ++Try)
			{
				FHitResult Hit;
				if (!World->LineTraceSingleByObjectType(Hit, FVector(X, Y, kTraceHalfCm), FVector(X, Y, -kTraceHalfCm), Objects, Params))
				{
					return false;
				}
				const UPrimitiveComponent* Comp = Hit.GetComponent();
				if (!Comp)
				{
					return false;
				}
				if (!Hit.bStartPenetrating && Comp->GetCollisionResponseToChannel(ECC_Pawn) == ECR_Block)
				{
					OutZ = static_cast<float>(Hit.ImpactPoint.Z);
					if (bOutMesh)
					{
						*bOutMesh = true;
					}
					if (OutComp)
					{
						*OutComp = Comp;
					}
					if (OutItem)
					{
						*OutItem = Hit.Item;
					}
					return true;
				}
				Params.AddIgnoredComponent(Comp);   // 설 수 없는 것 — 이 검사기에서는 다시 보지 않는다
			}
			return false;
		}
	};

	/** 상자 → 엔진 없는 상자. */
	EcoR9Demo::FR9Box ToR9Box(const FBox& B)
	{
		EcoR9Demo::FR9Box R;
		R.MinX = B.Min.X;
		R.MinY = B.Min.Y;
		R.MinZ = B.Min.Z;
		R.MaxX = B.Max.X;
		R.MaxY = B.Max.Y;
		R.MaxZ = B.Max.Z;
		return R;
	}

	/** 액터가 이 클래스 이름 (또는 그 하위)인가 — 헤더에 기대지 않으려고 이름으로 본다. 이름 번호(FName)로 비교 (액터마다 문자열을 만들지 않음). */
	bool IsKindOfName(const AActor* Actor, FName ClassName)
	{
		for (const UClass* C = Actor ? Actor->GetClass() : nullptr; C; C = C->GetSuperClass())
		{
			if (C->GetFName() == ClassName)
			{
				return true;
			}
		}
		return false;
	}

	bool IsKindOfName(const AActor* Actor, const TCHAR* ClassName)
	{
		return IsKindOfName(Actor, FName(ClassName));
	}

	FString Clock(double Seconds)
	{
		const int32 T = FMath::Max(0, FMath::FloorToInt32(Seconds));
		return FString::Printf(TEXT("%d:%02d"), T / 60, T % 60);
	}
}

// -----------------------------------------------------------------------------
// 콘솔 값
// -----------------------------------------------------------------------------

namespace EcoR9DemoCVars
{
	int32 Cam() { return EcoR9DemoSubsystemImpl::CVarCam.GetValueOnGameThread(); }
	float Speed() { return EcoR9DemoSubsystemImpl::CVarSpeed.GetValueOnGameThread(); }
	bool Text() { return EcoR9DemoSubsystemImpl::CVarText.GetValueOnGameThread() != 0; }
	bool HpBars() { return EcoR9DemoSubsystemImpl::CVarHpBars.GetValueOnGameThread() != 0; }
	bool Grass() { return EcoR9DemoSubsystemImpl::CVarGrass.GetValueOnGameThread() != 0; }
	bool Loop() { return EcoR9DemoSubsystemImpl::CVarLoop.GetValueOnGameThread() != 0; }
	int32 RestartSteps() { return EcoR9DemoSubsystemImpl::CVarRestartSteps.GetValueOnGameThread(); }
	FString Bodies() { return EcoR9DemoSubsystemImpl::CVarBodies.GetValueOnGameThread(); }
	bool Daylight() { return EcoR9DemoSubsystemImpl::CVarDaylight.GetValueOnGameThread() != 0; }
	void SetText(bool bOn) { EcoR9DemoSubsystemImpl::CVarText->Set(bOn ? 1 : 0, ECVF_SetByConsole); }
	void SetCam(int32 Mode) { EcoR9DemoSubsystemImpl::CVarCam->Set(Mode, ECVF_SetByConsole); }
	bool HideOthers() { return EcoR9DemoSubsystemImpl::CVarHideOthers.GetValueOnGameThread() != 0; }
	float BodyNearM() { return FMath::Clamp(EcoR9DemoSubsystemImpl::CVarBodyNear.GetValueOnGameThread(), 20.0f, 2000.0f); }
	int32 BodyBudget() { return FMath::Clamp(EcoR9DemoSubsystemImpl::CVarBodyBudget.GetValueOnGameThread(), 0, 400); }
	float GrassRadiusM() { return FMath::Clamp(EcoR9DemoSubsystemImpl::CVarGrassRadius.GetValueOnGameThread(), 32.0f, 400.0f); }
	FString BoarMesh() { return EcoR9DemoSubsystemImpl::CVarBoarMesh.GetValueOnGameThread().TrimStartAndEnd(); }
	float HudScale()
	{
		const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Cam.HudScale"));   // 옛 관찰 카메라 글 배율 (같은 값)
		return V ? V->GetFloat() : 1.0f;
	}
}

// -----------------------------------------------------------------------------
// 설정
// -----------------------------------------------------------------------------

FEcoR9DemoSettings FEcoR9DemoSettings::Resolve(const TCHAR* CommandLine)
{
	using namespace EcoR9DemoSubsystemImpl;
	FEcoR9DemoSettings S;
	const TCHAR* Cmd = CommandLine ? CommandLine : TEXT("");
	FString V;
	S.OnlyMap = CVarOnlyMap.GetValueOnGameThread().TrimStartAndEnd();
	if (FParse::Value(Cmd, TEXT("EcoR9Replay="), V, false) && !V.IsEmpty())
	{
		S.Mode = EMode::Replay;
		S.ReplayPath = V;
		S.bFromCommandLine = true;
	}
	else if (FParse::Value(Cmd, TEXT("EcoR9Demo="), V, false))
	{
		S.Mode = EMode::Live;
		S.BrainDir = V;
		S.bFromCommandLine = true;
	}
	else if (FParse::Param(Cmd, TEXT("EcoR9Demo")))
	{
		S.Mode = EMode::Live;
		S.bFromCommandLine = true;
	}
	else
	{
		const int32 C = CVarDemo.GetValueOnGameThread();
		if (C == 1)
		{
			S.Mode = EMode::Live;
			S.BrainDir = CVarBrains.GetValueOnGameThread();
		}
		else if (C == 2)
		{
			S.Mode = EMode::Replay;
			S.ReplayPath = CVarReplay.GetValueOnGameThread();
		}
	}
	if (S.Mode == EMode::Off)
	{
		return S;
	}
	if (S.BrainDir.IsEmpty())
	{
		S.BrainDir = CVarBrains.GetValueOnGameThread();
	}
	if (S.BrainDir.IsEmpty())
	{
		S.BrainDir = FPaths::Combine(DefaultDir(), TEXT("brains"));   // 에디터 PIE: 콘솔 'eco.R9Demo 1' 만으로 돈다
	}
	if (S.Mode == EMode::Replay && S.ReplayPath.IsEmpty())
	{
		S.ReplayPath = FPaths::Combine(DefaultDir(), TEXT("replay"), TEXT("demo.r9rp"));
	}
	if (!FParse::Value(Cmd, TEXT("EcoR9Scene="), S.ScenePath, false))
	{
		S.ScenePath = CVarScene.GetValueOnGameThread();
	}
	S.bSceneExplicit = !S.ScenePath.IsEmpty();
	if (S.ScenePath.IsEmpty() && !S.BrainDir.IsEmpty())
	{
		S.ScenePath = FPaths::Combine(S.BrainDir, TEXT("scene.txt"));
	}
	uint64 Seed = 0;
	if (FParse::Value(Cmd, TEXT("EcoR9Seed="), Seed))
	{
		S.Seed = Seed;
	}
	FString Policy = CVarPolicy.GetValueOnGameThread();
	FParse::Value(Cmd, TEXT("EcoR9Policy="), Policy);
	S.bSample = !Policy.Equals(TEXT("argmax"), ESearchCase::IgnoreCase);
	FString AtText = CVarAt.GetValueOnGameThread();
	FParse::Value(Cmd, TEXT("EcoR9DemoAt="), AtText, false);
	S.bHasAt = !AtText.IsEmpty() && ParseXY(AtText, S.AtM);
	FString PrefText;
	if (FParse::Value(Cmd, TEXT("EcoR9DemoPref="), PrefText, false))
	{
		S.bHasPref = ParseXY(PrefText, S.PrefM);
	}
	FString Cap;
	if (FParse::Value(Cmd, TEXT("EcoR9Capture="), Cap, false))
	{
		TArray<FString> F;
		Cap.ParseIntoArray(F, TEXT(","), false);
		if (F.Num() >= 3)
		{
			S.CaptureSeconds = FCString::Atof(*F.Last());
			S.CaptureFps = FMath::Clamp(FCString::Atof(*F[F.Num() - 2]), 1.0f, 120.0f);
			F.RemoveAt(F.Num() - 2, 2);
			S.CaptureDir = FString::Join(F, TEXT(","));
		}
		else if (F.Num() >= 1)
		{
			S.CaptureDir = F[0];
			S.CaptureSeconds = 30.0f;
		}
		S.CaptureDir.TrimStartAndEndInline();
		if (S.CaptureSeconds <= 0.0f)
		{
			S.CaptureDir.Reset();
		}
	}
	FParse::Value(Cmd, TEXT("EcoR9DemoExitAfter="), S.ExitAfterSeconds);
	// 확인용 (11-13 04:40): 녹화에 화면 글 넣기 · 카메라 키 차례 — 둘 다 명령줄에만, 없으면 예전 그대로
	S.bCaptureUI = FParse::Param(Cmd, TEXT("EcoR9CaptureUI"));
	FParse::Value(Cmd, TEXT("EcoR9CamKeys="), S.CamKeys, false);
	// 맵 전체 땅 모드 (2026-11-13)
	S.AreaM = CVarArea.GetValueOnGameThread();
	FParse::Value(Cmd, TEXT("EcoR9DemoArea="), S.AreaM);
	S.AreaM = FMath::Clamp(S.AreaM, 0, 4000);
	S.Herds = FMath::Clamp(CVarHerds.GetValueOnGameThread(), 1, 8);
	int32 Triple[3] = {24, 2, 8};
	if (ParseTriple(CVarPerHerd.GetValueOnGameThread(), Triple))
	{
		for (int32 k = 0; k < 3; ++k)
		{
			S.PerHerd[k] = Triple[k];
		}
	}
	int32 FaunaTriple[3] = {4, 1, 2};
	if (ParseTriple(CVarFaunaPerHerd.GetValueOnGameThread(), FaunaTriple, /*bAllowZero*/ true))
	{
		for (int32 k = 0; k < 3; ++k)
		{
			S.PerHerd[3 + k] = FaunaTriple[k];
		}
	}
	S.Fauna = CVarFauna.GetValueOnGameThread();
	FParse::Value(Cmd, TEXT("EcoR9Fauna="), S.Fauna);
	S.Fauna = S.Fauna != 0 ? 1 : 0;
	S.bHideOthers = CVarHideOthers.GetValueOnGameThread() != 0;
	return S;
}

bool FEcoR9DemoSettings::MapAllowed(const FString& OnlyMap, const FString& WorldPackage)
{
	FString List = OnlyMap;
	List.ReplaceInline(TEXT(";"), TEXT(","));
	TArray<FString> Items;
	List.ParseIntoArray(Items, TEXT(","), true);
	const FString Pkg = UWorld::RemovePIEPrefix(WorldPackage);   // PIE 월드 '/Game/…/UEDPIE_0_LV_…' → '/Game/…/LV_…'
	const FString Short = FPackageName::GetShortName(Pkg);
	bool bAny = false;
	for (FString Item : Items)
	{
		Item.TrimStartAndEndInline();
		Item.TrimQuotesInline();
		if (Item.IsEmpty())
		{
			continue;
		}
		bAny = true;
		if (Item.StartsWith(TEXT("/")))
		{
			// 오브젝트 경로 '/Game/X/LV.LV' → 패키지 '/Game/X/LV'
			const FString ItemPkg = FPackageName::ObjectPathToPackageName(Item);
			if (ItemPkg.Equals(Pkg, ESearchCase::IgnoreCase))
			{
				return true;
			}
		}
		else if (Item.Equals(Short, ESearchCase::IgnoreCase))
		{
			return true;   // 짧은 이름 'LV_EcoV3_Island'
		}
	}
	return !bAny;   // 항목이 하나도 없으면 (빈 값·공백뿐) 모든 맵
}

FString FEcoR9DemoSettings::DefaultDir()
{
	return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("R9Demo")));
}

FString FEcoR9DemoSettings::FaunaDir() const
{
	return BrainDir.IsEmpty() ? FString() : FPaths::Combine(BrainDir, TEXT("fauna"));
}

// -----------------------------------------------------------------------------
// 서브시스템 수명
// -----------------------------------------------------------------------------

bool UEcoR9DemoSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	// 데디케이티드·클라이언트 전용 실행에는 만들지 않는다 (같은 프로세스의 PIE 클라이언트 월드는 StartDemo 의 넷 모드 검사가 거부한다).
	// 2026-11-13: Play 중 eco.R9Demo 를 켜고 끌 수 있게 게임·PIE 월드에는 늘 만든다 — 꺼져 있으면 아무것도 만들지 않고 틱도 바로 돌아간다
	// (액터 0 · 그리기 0. 시험 FlagOffNoop·PlayToggle)
	if (IsRunningDedicatedServer() || IsRunningClientOnly())
	{
		return false;
	}
	// 자동화 시험 중에는 R9 데모 시험이 eco.R9Demo.AllowInTests 1 로 켠 때만 만든다 (다른 팀 시험 월드에 끼지 않게 — UserEngine.ini 에 eco.R9Demo=1 이 있어도)
	if (GIsAutomationTesting && EcoR9DemoSubsystemImpl::CVarAllowInTests.GetValueOnGameThread() == 0)
	{
		return false;
	}
	return Super::ShouldCreateSubsystem(Outer);
}

bool UEcoR9DemoSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UEcoR9DemoSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	State = MakeShared<FEcoR9DemoState>();
	State->Settings = FEcoR9DemoSettings::Resolve(FCommandLine::Get());
	State->DrawHandle = UDebugDrawService::Register(TEXT("Game"), FDebugDrawDelegate::CreateUObject(this, &UEcoR9DemoSubsystem::DrawOverlay));
}

void UEcoR9DemoSubsystem::Deinitialize()
{
	if (State)
	{
		if (State->DrawHandle.IsValid())
		{
			UDebugDrawService::Unregister(State->DrawHandle);
			State->DrawHandle.Reset();
		}
		TeardownDemo(/*bRestoreView*/ false);
	}
	State.Reset();
	Super::Deinitialize();
}

void UEcoR9DemoSubsystem::TeardownDemo(bool bRestoreView)
{
	// 데모가 만든 것·바꾼 실행 중 값을 모두 되돌린다 (월드가 끝날 때 · Play 중 eco.R9Demo 0). 저장하는 것 없음
	if (!State)
	{
		return;
	}
	FEcoR9DemoState& S = *State;
	if (S.PrevCamEnable != MIN_int32 && S.PrevCamEnable != MIN_int32 + 1)
	{
		if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Cam.Enable")))
		{
			V->Set(S.PrevCamEnable, ECVF_SetByCode);
		}
	}
	S.PrevCamEnable = MIN_int32;
	if (!S.PrevRes.IsEmpty() && GEngine)
	{
		GEngine->Exec(GetWorld(), *S.PrevRes);   // 녹화 해상도를 앞 값으로 (설정 파일에 쓰지 않음)
	}
	S.PrevRes.Reset();
	if (S.PrevOnScreenMsgs >= 0 && GEngine)
	{
		GEngine->bEnableOnScreenDebugMessages = S.PrevOnScreenMsgs != 0;
	}
	S.PrevOnScreenMsgs = -1;
	ReleaseDaylight();
	const UWorld* World = GetWorld();
	const bool bWorldAlive = World && !World->bIsTearingDown;
	if (bWorldAlive)
	{
		HideOtherVisuals(false);
		ClearBodies();
		for (AActor* A : SpawnedActors)
		{
			if (IsValid(A))
			{
				A->Destroy();
			}
		}
		if (bRestoreView)
		{
			RestorePawn();
		}
	}
	S.HiddenOthers.Reset();
	S.HiddenComps.Reset();
	S.FrameLastReal = 0.0;   // 확인용 프레임 셈: 다시 켤 때 꺼져 있던 시간을 한 프레임으로 세지 않게
	S.Live.reset();
	SpawnedActors.Reset();
	Manager = nullptr;
	Camera = nullptr;
}

void UEcoR9DemoSubsystem::StartDemo(const TCHAR* Why)
{
	using namespace EcoR9DemoSubsystemImpl;
	if (!State)
	{
		return;
	}
	UWorld* World = GetWorld();
	if (!World || !(State->bWorldBegan || World->HasBegunPlay()))
	{
		return;   // Play 전 (OnWorldBeginPlay 가 부른다)
	}
	if (IsActive())
	{
		return;   // 이미 켜져 있다 — 두 번 만들지 않는다
	}
	if (State->Phase == EEcoR9DemoPhase::Refused)
	{
		// 검토 (11-13): 클라이언트·데디케이티드 월드는 넷 모드가 월드가 사는 동안 바뀌지 않는다 — 콘솔 값이 바뀔 때마다 정리(보기 대상 되돌리기 포함)·다시 거부하지 않는다
		return;
	}
	if (State->Phase == EEcoR9DemoPhase::Failed)
	{
		StopDemo(TEXT("다시 켜기 전 정리"));   // 상태를 새로 만든다 — 아래에서 다시 잡는다
	}
	FEcoR9DemoState& S = *State;
	S.Settings = FEcoR9DemoSettings::Resolve(FCommandLine::Get());
	if (S.Settings.Mode == FEcoR9DemoSettings::EMode::Off)
	{
		return;
	}
	++S.Starts;
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 시작 (%s) — 이 월드 %d 번째"), Why, S.Starts);
	OnWorldBeginPlayImpl(*World);
}

void UEcoR9DemoSubsystem::StopDemo(const TCHAR* Why)
{
	if (!State || State->Phase == EEcoR9DemoPhase::Off || State->Phase == EEcoR9DemoPhase::Refused)
	{
		return;   // 거부된 월드(클라이언트·데디케이티드)는 아무것도 만들거나 바꾸지 않았다 — 클라이언트 보기 대상을 건드리지 않는다
	}
	if (State->Phase == EEcoR9DemoPhase::Running)
	{
		LogSummary(Why);
	}
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 정지 (%s) — 만든 액터를 치우고 숨긴 것·카메라·플레이어 몸을 되돌린다"), Why);
	TeardownDemo(/*bRestoreView*/ true);
	// 상태를 새로 (설정·그리기 손잡이·시작 횟수·훑은 땅 지도는 남긴다 — 다시 켤 때 다시 훑지 않음)
	const TSharedPtr<FEcoR9DemoState> Old = State;
	State = MakeShared<FEcoR9DemoState>();
	State->Settings = Old->Settings;
	State->DrawHandle = Old->DrawHandle;
	State->Starts = Old->Starts;
	State->bWorldBegan = Old->bWorldBegan;
	State->WholeSpec = Old->WholeSpec;
	State->WholeCenter = Old->WholeCenter;
	State->LandBox = Old->LandBox;
	State->WholeLine = Old->WholeLine;
	State->AreaBox = Old->AreaBox;
	State->AreaLine = Old->AreaLine;
	State->Phase = EEcoR9DemoPhase::Off;
}

void UEcoR9DemoSubsystem::OnDemoCVarChanged(IConsoleVariable* Var)
{
	// Play 중 eco.R9Demo 를 바꾸면 지금 도는 게임·PIE 월드에서 바로 시작·정지 (UserEngine.ini 를 읽을 때도 불리지만 그때는 월드가 없다)
	if (!GEngine)
	{
		return;
	}
	for (const FWorldContext& Ctx : GEngine->GetWorldContexts())
	{
		UWorld* W = Ctx.World();
		if (!W || (W->WorldType != EWorldType::Game && W->WorldType != EWorldType::PIE) || W->bIsTearingDown)
		{
			continue;
		}
		UEcoR9DemoSubsystem* Sub = W->GetSubsystem<UEcoR9DemoSubsystem>();
		if (!Sub || !Sub->State || !(Sub->State->bWorldBegan || W->HasBegunPlay()))
		{
			continue;   // Play 전 월드 — OnWorldBeginPlay 가 그때 콘솔 값을 읽는다
		}
		const FEcoR9DemoSettings Want = FEcoR9DemoSettings::Resolve(FCommandLine::Get());
		if (Want.Mode == FEcoR9DemoSettings::EMode::Off)
		{
			Sub->StopDemo(TEXT("콘솔 eco.R9Demo 0"));
		}
		else if (Sub->State->Phase != EEcoR9DemoPhase::Off && Sub->State->Settings.Mode != Want.Mode)
		{
			Sub->StopDemo(TEXT("콘솔 eco.R9Demo 판 바뀜"));
			Sub->StartDemo(TEXT("콘솔 eco.R9Demo 판 바뀜"));
		}
		else
		{
			Sub->StartDemo(TEXT("콘솔 eco.R9Demo"));
		}
	}
	(void)Var;
}

TStatId UEcoR9DemoSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UEcoR9DemoSubsystem, STATGROUP_Tickables);
}

bool UEcoR9DemoSubsystem::IsRunning() const
{
	return State && State->Phase == EEcoR9DemoPhase::Running;
}

bool UEcoR9DemoSubsystem::IsActive() const
{
	return State && (State->Phase == EEcoR9DemoPhase::WaitScan || State->Phase == EEcoR9DemoPhase::WaitWhole || State->Phase == EEcoR9DemoPhase::WaitStage ||
					 State->Phase == EEcoR9DemoPhase::Running);
}

int32 UEcoR9DemoSubsystem::NumSpawnedActors() const
{
	int32 N = 0;
	for (const AActor* A : SpawnedActors)
	{
		N += IsValid(A) ? 1 : 0;
	}
	if (State)
	{
		for (const TPair<uint32, FEcoR9DemoBody>& P : State->Bodies)
		{
			N += (P.Value.Rep.IsValid() || P.Value.Boar.IsValid()) ? 1 : 0;
		}
	}
	return N;
}

int32 UEcoR9DemoSubsystem::NumBodies() const
{
	return State ? State->Bodies.Num() : 0;
}

int64 UEcoR9DemoSubsystem::NumStepsShown() const
{
	return State ? State->StepsShown : 0;
}

FVector UEcoR9DemoSubsystem::StageCenterCm() const
{
	return State ? State->StageCenter : FVector::ZeroVector;
}

FVector UEcoR9DemoSubsystem::SearchOriginCm() const
{
	return State ? State->SearchOrigin : FVector::ZeroVector;
}

int32 UEcoR9DemoSubsystem::NumAvoidZones() const
{
	return State ? State->NumAvoid : 0;
}

bool UEcoR9DemoSubsystem::HasTeamEco() const
{
	return State && State->bTeamEco;
}

bool UEcoR9DemoSubsystem::IsWhole() const
{
	return State && State->bWhole && State->Info.bWhole;
}

const EcoR9Demo::FR9WholeSpec* UEcoR9DemoSubsystem::WholeSpecForTest() const
{
	return State ? State->WholeSpec.get() : nullptr;
}

int32 UEcoR9DemoSubsystem::NumHerdSites() const
{
	return State ? static_cast<int32>(State->Info.HerdXY.size() / 2) : 0;
}

int32 UEcoR9DemoSubsystem::NumHiddenOthers() const
{
	int32 N = 0;
	if (State)
	{
		for (const TWeakObjectPtr<AActor>& A : State->HiddenOthers)
		{
			N += A.IsValid() && A->IsHidden() ? 1 : 0;
		}
	}
	return N;
}

int32 UEcoR9DemoSubsystem::NumBodyActors() const
{
	return State ? State->NumBodyActors : 0;
}

int32 UEcoR9DemoSubsystem::NumFarMarkers() const
{
	return State ? State->NumFar : 0;
}

int32 UEcoR9DemoSubsystem::NumStarts() const
{
	return State ? State->Starts : 0;
}

FVector UEcoR9DemoSubsystem::WholeCenterCm() const
{
	return State ? State->WholeCenter : FVector::ZeroVector;
}

FString UEcoR9DemoSubsystem::BoarBodyLine() const
{
	return State ? State->BoarLine : FString();
}

bool UEcoR9DemoSubsystem::IsFaunaScene() const
{
	return State && State->Info.NumSpecies > EcoR9Demo::kNumOldSpecies;
}

int32 UEcoR9DemoSubsystem::NumSceneSpecies() const
{
	return State && State->Phase == EEcoR9DemoPhase::Running ? State->Info.NumSpecies : 0;
}

int32 UEcoR9DemoSubsystem::NumShownOfSpecies(uint8 Species) const
{
	int32 N = 0;
	if (State && Species < EcoR9Demo::kNumSpecies)
	{
		for (const TPair<uint32, FEcoR9DemoBody>& P : State->Bodies)
		{
			N += P.Value.Species == Species && !P.Value.bDead && (P.Value.Rep.IsValid() || P.Value.Boar.IsValid()) ? 1 : 0;
		}
		if (const UInstancedStaticMeshComponent* Ism = State->FarIsm[Species].Get())
		{
			N += Ism->GetInstanceCount();
		}
	}
	return N;
}

FString UEcoR9DemoSubsystem::FaunaChoiceLine() const
{
	return State ? State->FaunaLine : FString();
}

void UEcoR9DemoSubsystem::DescribeTeamEco(UWorld& World)
{
	using namespace EcoR9DemoSubsystemImpl;
	// 맵에 팀 생태 장치·통합 v3 가 있어도 거부하지 않는다 (2026-11-12 22:30 사용자 '맵마다 또 설정을 해줘야돼???').
	// 세기만 하고 건드리지 않는다: R9 개체는 Mass 개체가 아니라 팀 시뮬레이션이 보지 못하고, 데모도 팀 개체·지역을 읽거나 쓰지 않는다.
	// Fauna 는 통합 조정자 안의 Mass 설정이라 조정자 수로 본다.
	FEcoR9DemoState& S = *State;
	const TArray<FName> Names = ToNames(kTeamEcoClasses);
	TArray<int32> Counts;
	Counts.SetNumZeroed(Names.Num());
	const APlayerController* PC = World.GetFirstPlayerController();
	const APawn* PlayerPawn = PC ? PC->GetPawn() : nullptr;
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		if (*It == PlayerPawn || SpawnedActors.Contains(*It))
		{
			continue;   // 플레이어 몸(옛 CreatureCharacter 일 수도)·데모가 만든 것은 팀 생태가 아니다
		}
		for (int32 i = 0; i < Names.Num(); ++i)
		{
			if (IsKindOfName(*It, Names[i]))
			{
				++Counts[i];
				break;
			}
		}
	}
	FString List;
	for (int32 i = 0; i < Names.Num(); ++i)
	{
		if (Counts[i] > 0)
		{
			List += FString::Printf(TEXT("%s%s %d"), List.IsEmpty() ? TEXT("") : TEXT(" · "), kTeamEcoClasses[i], Counts[i]);
		}
	}
	TArray<FString> V3;
	if (FParse::Param(FCommandLine::Get(), TEXT("EcoIntegratedV3")))
	{
		V3.Add(TEXT("-EcoIntegratedV3"));
	}
	// eco.IntegratedPolicyVersion 은 통합 조정자가 있어야 뜻이 있어 따로 보지 않는다 (조정자 수로 잡힘)
	if (const IConsoleVariable* Cv = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.IntegratedV3.IslandLive")); Cv && Cv->GetInt() != 0)
	{
		V3.Add(FString::Printf(TEXT("eco.IntegratedV3.IslandLive=%d"), Cv->GetInt()));
	}
	S.bTeamEco = !List.IsEmpty() || !V3.IsEmpty();
	if (S.bTeamEco)
	{
		S.TeamEcoNote = FString::Printf(TEXT("맵에 팀 생태가 있다 (%s%s%s) — 거부하지 않고 건드리지도 않는다. 데모만 따로 돈다 (서로 영향 없음). ")
										TEXT("무대는 그 지역 상자·동물에서 떨어진 곳을 먼저 고르고, 플레이어 몸은 시작 자리에 숨긴 채 둔다"),
										List.IsEmpty() ? TEXT("장치 없음") : *List, V3.IsEmpty() ? TEXT("") : TEXT(" | 통합 v3 "), *FString::Join(V3, TEXT(" ")));
	}
	else
	{
		S.TeamEcoNote.Reset();
	}
}

void UEcoR9DemoSubsystem::ChooseSearchOrigin(UWorld& World)
{
	// 자리 찾기 시작점 (맵마다 설정 없음): 명령줄 -EcoR9DemoPref → 플레이어 몸 (PlayerStart·PIE 카메라 자리 등 게임이 실제로 둔 곳) →
	// PlayerStart (이름 순 첫째 — 결정적) → 플레이어 시점 → 월드 원점
	FEcoR9DemoState& S = *State;
	if (S.Settings.bHasPref)
	{
		S.SearchOrigin = FVector(S.Settings.PrefM.X * 100.0, S.Settings.PrefM.Y * 100.0, 0.0);
		S.OriginLabel = TEXT("명령줄 -EcoR9DemoPref");
		return;
	}
	APlayerController* PC = World.GetFirstPlayerController();
	if (const APawn* Pawn = PC ? PC->GetPawn() : nullptr)
	{
		S.SearchOrigin = Pawn->GetActorLocation();
		S.OriginLabel = FString::Printf(TEXT("플레이어 몸 %s"), *Pawn->GetName());
		return;
	}
	const APlayerStart* Start = nullptr;
	for (TActorIterator<APlayerStart> It(&World); It; ++It)
	{
		if (!Start || It->GetName().Compare(Start->GetName(), ESearchCase::CaseSensitive) < 0)
		{
			Start = *It;
		}
	}
	if (Start)
	{
		S.SearchOrigin = Start->GetActorLocation();
		S.OriginLabel = FString::Printf(TEXT("PlayerStart %s"), *Start->GetName());
		return;
	}
	if (PC)
	{
		FVector Loc = FVector::ZeroVector;
		FRotator Rot = FRotator::ZeroRotator;
		PC->GetPlayerViewPoint(Loc, Rot);
		S.SearchOrigin = Loc;
		S.OriginLabel = TEXT("플레이어 시점");
		return;
	}
	S.SearchOrigin = FVector::ZeroVector;
	S.OriginLabel = TEXT("월드 원점 (플레이어 몸·PlayerStart 없음)");
}

void UEcoR9DemoSubsystem::RefreshProbeIgnore()
{
	// 바닥 선 검사에서 뺄 것: 물 몸체·물 구역 (바다 충돌 상자 3 km 가 WorldStatic 이라 바닥처럼 잡힌다), 플레이어 몸
	FEcoR9DemoState& S = *State;
	S.ProbeIgnore.Reset();
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		const FString Cls = It->GetClass()->GetName();
		if (Cls.StartsWith(TEXT("WaterBody")) || Cls.StartsWith(TEXT("WaterZone")))
		{
			S.ProbeIgnore.Add(*It);
		}
	}
	if (const APlayerController* PC = World->GetFirstPlayerController(); PC && PC->GetPawn())
	{
		S.ProbeIgnore.Add(PC->GetPawn());
	}
}

void UEcoR9DemoSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	if (!State)
	{
		return;
	}
	State->bWorldBegan = true;
	State->Settings = FEcoR9DemoSettings::Resolve(FCommandLine::Get());
	if (State->Settings.Mode == FEcoR9DemoSettings::EMode::Off)
	{
		return;   // 꺼짐 — 아무것도 만들지 않는다 (Play 중 eco.R9Demo 1 이면 그때 시작)
	}
	// 시작 맵에서만 (2026-11-13 03:30 사용자 — 편집기 시작 맵에서만 쓴다): 콘솔 값으로 켠 판은 eco.R9Demo.OnlyMap 밖 맵에서 아무것도 만들지 않는다.
	// 명령줄 깃발로 켠 판은 거르지 않는다. Play 중 직접 친 eco.R9Demo 1 도 거르지 않는다 (OnDemoCVarChanged → StartDemo)
	const FString Pkg = UWorld::RemovePIEPrefix(InWorld.GetPackage()->GetName());
	if (!State->Settings.bFromCommandLine && !FEcoR9DemoSettings::MapAllowed(State->Settings.OnlyMap, Pkg))
	{
		State->bMapFiltered = true;
		UE_LOG(LogEcoR9Demo, Log,
			   TEXT("[EcoR9Demo] 이 맵(%s)은 eco.R9Demo.OnlyMap(%s) 밖 — 켜지 않는다 (예전 그대로). 이 맵에서도 보려면 Play 중 콘솔 eco.R9Demo 1, ")
				   TEXT("어느 맵에서나 늘 켜려면 eco.R9Demo.OnlyMap 을 비운다"),
			   *Pkg, *State->Settings.OnlyMap);
		return;
	}
	StartDemo(TEXT("Play 시작"));
}

bool UEcoR9DemoSubsystem::WasMapFiltered() const
{
	return State && State->bMapFiltered;
}

void UEcoR9DemoSubsystem::OnWorldBeginPlayImpl(UWorld& InWorld)
{
	using namespace EcoR9DemoSubsystemImpl;
	FEcoR9DemoState& S = *State;
	const ENetMode Net = InWorld.GetNetMode();
	const FString Pkg = UWorld::RemovePIEPrefix(InWorld.GetPackage()->GetName());
	if (Net == NM_Client || Net == NM_DedicatedServer)
	{
		S.Phase = EEcoR9DemoPhase::Refused;
		S.Why = TEXT("서버·단독(보는 화면이 있는 곳)에서만 돈다");
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 거부 — %s. 아무것도 만들지 않는다."), *S.Why);
		return;
	}
	// 옛 관찰 카메라는 데모가 켜지는 때부터 끈다 (같은 숫자 키 0~5·H 를 두 카메라가 같이 읽지 않게, 우상단 글이 겹치지 않게 — 끌 때 되돌림)
	HoldObserverCamera();
	// 맵 이름 거르기는 OnWorldBeginPlay (eco.R9Demo.OnlyMap). 팀 생태 장치·통합 v3 는 세어 알리기만 한다
	DescribeTeamEco(InWorld);
	// 맵 전체 땅 (기본): 훑은 땅 지도가 있어야 코어를 시작할 수 있어 원천은 훑은 뒤에 연다 (ScanWhole). 생성기가 없는 코어면 예전 한 무대
	S.bWhole = S.Settings.WantsWhole() && EcoR9Demo::FR9LiveSource::Available();
	if (S.bWhole && !EcoR9Demo::FR9LiveSource::WholeAvailable())
	{
		S.bWhole = false;
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 이 빌드의 코어에 큰 세계 장면 생성기(EcoR9Scene.h)가 없다 — 맵 전체 땅 대신 예전 한 무대(120 m)로 돈다"));
	}
	if (!S.bWhole)
	{
		FString Err;
		if (!OpenSource(Err))
		{
			Fail(Err);
			return;
		}
	}
	// 무대를 불러오는 30~90 초 동안 폰(원점 땅 밑에 남)이 떨어지거나 원점 둘레 팀 날씨 트리거에 겹치지 않게 먼저 멈춘다.
	// 이 시점(액터 BeginPlay 앞)에 충돌을 끄면 시작 겹침도 생기지 않는다. 자리 옮기기는 무대가 선 뒤 ParkPawn.
	FreezePawn();
	if (!S.Settings.CaptureDir.IsEmpty() && GEngine)
	{
		// -RenderOffscreen 에서는 -ResX/-ResY 가 먹지 않는다 (r7e_game/film.md:80). 끝날 때 앞 값으로 되돌린다 (Deinitialize)
		const TCHAR* Mode = GSystemResolution.WindowMode == EWindowMode::Fullscreen ? TEXT("f")
							: (GSystemResolution.WindowMode == EWindowMode::WindowedFullscreen ? TEXT("wf") : TEXT("w"));
		if (GSystemResolution.ResX > 0 && GSystemResolution.ResY > 0)
		{
			S.PrevRes = FString::Printf(TEXT("r.SetRes %dx%d%s"), GSystemResolution.ResX, GSystemResolution.ResY, Mode);
		}
		GEngine->Exec(&InWorld, TEXT("r.SetRes 1920x1080wf"));
		// 녹화 프레임에 다른 코드의 화면 메시지가 끼지 않게 (촬영 감독과 같은 처리, EcoV3FilmDirector.cpp ApplyViewEnvironment). 우리 글자는 디버그 그리기라 그대로 보인다
		S.PrevOnScreenMsgs = GEngine->bEnableOnScreenDebugMessages ? 1 : 0;
		GEngine->bEnableOnScreenDebugMessages = false;
	}
	if (S.bWhole)
	{
		// 맵 전체 땅: 땅을 불러와 훑은 뒤(ScanWhole) 코어 큰 세계를 연다
		ChooseSearchOrigin(InWorld);
		BeginWhole(InWorld);
		return;
	}
	const TCHAR* ModeName = S.Settings.Mode == FEcoR9DemoSettings::EMode::Live ? TEXT("실시간 (언리얼 C++ 추론)") : TEXT("재생 (파이썬 실행 기록)");
	int32 NumLand = 0;
	for (TActorIterator<ALandscapeProxy> It(&InWorld); It; ++It)
	{
		++NumLand;
	}
	UE_LOG(LogEcoR9Demo, Log,
		   TEXT("[EcoR9Demo] 켬 — %s | 맵 %s (World Partition %s · 지형 액터 %d — 맵 제한 없음) | 세계 %.0f×%.0f 단위 · 스텝 %.4f 초 · 은신처 %d · 먹이 격자 %d · ")
			   TEXT("두뇌 %s · 고르기 %s · 시드 %llu"),
		   ModeName, *Pkg, InWorld.IsPartitionedWorld() ? TEXT("예") : TEXT("아님"), NumLand, S.Info.W, S.Info.H, S.Info.StepSeconds,
		   static_cast<int32>(S.Info.Shelters.size()), S.Info.G, *Utf8(S.Info.Brains), *Utf8(S.Info.Policy), static_cast<unsigned long long>(S.Info.Seed));
	// 동물 세계 고르기 줄 (종 수·몸 규칙·까닭) 은 OpenSource 가 판을 열 때마다 찍는다 (맵 전체 땅·다시 시작도 — 검토 11-13 06:10)
	if (!S.TeamEcoNote.IsEmpty())
	{
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] %s"), *S.TeamEcoNote);
	}
	if (S.Settings.bHasAt)
	{
		S.StageCenter = FVector(S.Settings.AtM.X * 100.0, S.Settings.AtM.Y * 100.0, 0.0);
		S.SearchOrigin = S.StageCenter;
		S.OriginLabel = TEXT("eco.R9Demo.At · -EcoR9DemoAt");
		S.StageLine = FString::Printf(TEXT("무대 가운데 (%.1f, %.1f) m — 콘솔 eco.R9Demo.At · 명령줄 -EcoR9DemoAt 로 줌 (자동 고르기 안 함)"), S.Settings.AtM.X,
									  S.Settings.AtM.Y);
		BeginStreamingAt(S.StageCenter, kStageStreamRadius);
		S.Phase = EEcoR9DemoPhase::WaitStage;
	}
	else
	{
		// 맵마다 설정 없이: 플레이어 시작점 둘레부터 넓혀 가며 고른다 (고리 0 = 200 m)
		ChooseSearchOrigin(InWorld);
		S.ScanRing = 0;
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 자리 찾기 시작점 (%.1f, %.1f, %.1f) m — %s. 둘레 %.0f → %.0f m 로 넓혀 가며 트인 평지를 찾는다"),
			   S.SearchOrigin.X / 100.0, S.SearchOrigin.Y / 100.0, S.SearchOrigin.Z / 100.0, *S.OriginLabel, kRingHalfCm[0] / 100.0,
			   kRingHalfCm[kNumRings - 1] / 100.0);
		BeginStreamingAt(S.SearchOrigin, RingStreamRadius(0));
		S.Phase = EEcoR9DemoPhase::WaitScan;
	}
	S.PhaseStart = InWorld.GetTimeSeconds();
}

void UEcoR9DemoSubsystem::Fail(const FString& Why)
{
	if (!State)
	{
		return;
	}
	State->Phase = EEcoR9DemoPhase::Failed;
	State->Why = Why;
	UE_LOG(LogEcoR9Demo, Error, TEXT("[EcoR9Demo] 실패 — %s"), *Why);
	// 검토 (11-13): 이제 Play 마다 저절로 켜지므로 (UserEngine.ini eco.R9Demo=1) 실패하면 멈추고 숨긴 플레이어 몸·숨긴 팀 동물·데모 카메라에 갇히지 않게
	// 데모가 만든 것·바꾼 것을 그 자리에서 되돌린다 (화면에는 실패 글만 남는다 — 상태(Phase·Why)는 그대로)
	TeardownDemo(/*bRestoreView*/ true);
	if (!State->Settings.CaptureDir.IsEmpty() || State->Settings.ExitAfterSeconds > 0.0f)
	{
		State->QuitCountdown = 10;   // 창 없는 실행이 멈춰 있지 않게
	}
}

// -----------------------------------------------------------------------------
// 프레임 원천
// -----------------------------------------------------------------------------

bool UEcoR9DemoSubsystem::OpenSource(FString& OutError)
{
	using namespace EcoR9DemoSubsystemImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	if (S.Settings.Mode == FEcoR9DemoSettings::EMode::Live)
	{
		if (!FR9LiveSource::Available())
		{
			OutError = TEXT("이 빌드에는 R9 코어(EcoR9Core.h)가 없다 — 재생 판(-EcoR9Replay=)을 쓴다");
			return false;
		}
		FR9LiveConfig C;
		C.BrainDir = ToUtf8(S.Settings.BrainDir);
		C.ScenePath = ToUtf8(S.Settings.ScenePath);
		C.Seed = S.Settings.Seed + static_cast<uint64>(S.RunIndex);
		C.bSample = S.Settings.bSample;
		if (S.bWhole)
		{
			C.Whole = S.WholeSpec;   // 맵 전체 땅: 장면 파일은 몸 표·상수만, 땅 지도 위에 큰 세계 장면 (다시 시작하면 새 시드로 새 장면, 땅 지도는 그대로)
		}
		// 파일은 언리얼이 읽어 바이트로 넘긴다 (한글 경로도 되게). 실행 중 파이썬 없음 — 두뇌 파일은 미리 바꿔 둔 float32 묶음
		// 동물 세계 (11-13 05:00): eco.R9Demo.Fauna 1 이고 <두뇌 폴더>/fauna/ 에 새 종 두뇌 셋 + scene.txt 가 다 있으면 그 장면 (ChooseFaunaFiles).
		// 동물 장면이 시작에 실패하면 까닭을 기록 줄에 남기고 세 종 장면으로 한 번 더 (발표 중 깨지지 않게 — 세 종 길은 지금과 같은 파일·같은 순서)
		FR9FaunaFiles Ff;
		const bool bTryFauna = ChooseFaunaFiles(S.Settings, Ff);
		S.FaunaLine = Ff.Line;
		TArray<uint8> Bytes;
		auto LoadInto = [&Bytes](const FString& Path, std::vector<std::uint8_t>& Out) -> bool
		{
			Bytes.Reset();
			if (!FFileHelper::LoadFileToArray(Bytes, *Path))
			{
				return false;
			}
			Out.assign(Bytes.GetData(), Bytes.GetData() + Bytes.Num());
			return true;
		};
		auto TryStart = [&](bool bFauna, FString& OutWhy) -> bool
		{
			FR9LiveConfig Cf = C;
			const FString ScenePath = bFauna ? Ff.ScenePath : S.Settings.ScenePath;
			std::vector<std::uint8_t> SceneBytes;
			if (!LoadInto(ScenePath, SceneBytes))
			{
				OutWhy = FString::Printf(TEXT("장면 파일을 못 읽음: '%s' (-EcoR9Scene= 또는 <두뇌 폴더>/scene.txt)"), *ScenePath);
				return false;
			}
			Cf.SceneText.assign(SceneBytes.begin(), SceneBytes.end());
			const int32 NumSp = bFauna ? kNumSpecies : kNumOldSpecies;
			for (int32 k = 0; k < NumSp; ++k)
			{
				const FString BrainPath =
					bFauna ? Ff.BrainPath[k] : FPaths::Combine(S.Settings.BrainDir, FString(UTF8_TO_TCHAR(SpeciesKey(static_cast<uint8>(k)))) + TEXT(".r9brain"));
				if (!LoadInto(BrainPath, Cf.BrainBytes[k]))
				{
					OutWhy = FString::Printf(TEXT("두뇌 파일을 못 읽음: '%s'"), *BrainPath);
					return false;
				}
			}
			if (!bFauna && S.Settings.bSceneExplicit)
			{
				// 장면을 직접 준 판: 그 장면이 동물 세계 판(6 종)일 수도 있어 새 종 두뇌도 있으면 실어 둔다 (세 종 장면이면 코어가 읽지 않음)
				for (int32 k = kNumOldSpecies; k < kNumSpecies; ++k)
				{
					const FString Name = FString(UTF8_TO_TCHAR(SpeciesKey(static_cast<uint8>(k)))) + TEXT(".r9brain");
					if (!LoadInto(FPaths::Combine(Ff.Dir, Name), Cf.BrainBytes[k]))
					{
						LoadInto(FPaths::Combine(S.Settings.BrainDir, Name), Cf.BrainBytes[k]);
					}
				}
			}
			S.Live = std::make_unique<FR9LiveSource>();
			std::string E;
			FR9Frame First;
			if (!S.Live->Init(Cf, S.Info, First, E))
			{
				OutWhy = FString::Printf(TEXT("코어 시작 실패 (장면 %s, 두뇌 %s): %s"), *ScenePath, bFauna ? *Ff.Dir : *S.Settings.BrainDir, *Utf8(E));
				S.Live.reset();
				return false;
			}
			if (bFauna && S.Info.NumSpecies <= kNumOldSpecies)
			{
				OutWhy = FString::Printf(TEXT("동물 장면 '%s' 를 코어가 세 종 장면으로 읽음 (6 종 장면 덤프가 아님)"), *ScenePath);
				S.Live.reset();
				return false;
			}
			S.Cur = MoveTemp(First);
			return true;
		};
		FString Why;
		bool bStarted = bTryFauna && TryStart(true, Why);
		if (bTryFauna && !bStarted)
		{
			S.FaunaLine = FString::Printf(TEXT("동물 장면 시작 실패 — 세 종으로 돈다: %s"), *Why);
			UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] %s"), *S.FaunaLine);
		}
		if (!bStarted && !TryStart(false, Why))
		{
			OutError = Why;
			return false;
		}
		// 동물 세계 고르기 (11-13 05:00): 종 수·몸 규칙·쓴 파일 또는 세 종으로 도는 까닭. 판을 열 때마다 (첫 Play · 맵 전체 땅 · 다시 시작) — Play 로그만 보고
		// '종 6 · 동물 세계 몸 규칙 켬' 인지 알 수 있게 (검토 11-13 06:10: 맵 전체 땅·다시 시작 길에서는 이 줄이 안 찍혔다)
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 판 %d · 종 %d (%s) | %s"), S.RunIndex, S.Info.NumSpecies, S.Info.bFauna ? TEXT("동물 세계 몸 규칙 켬") : TEXT("S′ 세계 규칙"),
			   *S.FaunaLine);
		S.bFoodKnown = S.Info.G > 0 && (S.Info.bWhole || !S.Cur.Grass.empty());
		S.bEventsKnown = true;
	}
	else
	{
		if (S.Replay.Frames.empty())
		{
			const FString Path = S.Settings.ReplayPath;
			TArray<uint8> Bytes;
			if (Path.IsEmpty() || !FFileHelper::LoadFileToArray(Bytes, *Path))
			{
				OutError = FString::Printf(TEXT("재생 파일을 못 읽음: '%s'"), *Path);
				return false;
			}
			std::string E;
			if (!ParseReplay(Bytes.GetData(), static_cast<std::size_t>(Bytes.Num()), S.Replay, E) || S.Replay.Frames.empty())
			{
				OutError = FString::Printf(TEXT("재생 파일 '%s': %s"), *Path, E.empty() ? TEXT("프레임 없음") : *Utf8(E));
				return false;
			}
			TSharedPtr<FJsonObject> J;
			const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Utf8(S.Replay.HeaderJson));
			if (!FJsonSerializer::Deserialize(Reader, J) || !J.IsValid())
			{
				OutError = FString::Printf(TEXT("재생 파일 '%s': JSON 머리를 못 읽음"), *Path);
				return false;
			}
			S.Info = FR9WorldInfo();
			double Num = 0.0;
			if (J->TryGetNumberField(TEXT("step_s"), Num) && Num > 0.0)
			{
				S.Info.StepSeconds = Num;
			}
			if (J->TryGetNumberField(TEXT("unit_cm"), Num) && Num > 0.0)
			{
				S.Info.UnitCm = Num;
			}
			if (J->TryGetNumberField(TEXT("seed"), Num))
			{
				S.Info.Seed = static_cast<uint64>(Num);
			}
			const TArray<TSharedPtr<FJsonValue>>* Arr = nullptr;
			if (J->TryGetArrayField(TEXT("world_units"), Arr) && Arr && Arr->Num() >= 2)
			{
				S.Info.W = (*Arr)[0]->AsNumber();
				S.Info.H = (*Arr)[1]->AsNumber();
			}
			if (J->TryGetArrayField(TEXT("shelters"), Arr) && Arr)
			{
				for (const TSharedPtr<FJsonValue>& V : *Arr)
				{
					const TArray<TSharedPtr<FJsonValue>>* Xyr = nullptr;
					if (V.IsValid() && V->TryGetArray(Xyr) && Xyr && Xyr->Num() >= 3)
					{
						S.Info.Shelters.push_back({(*Xyr)[0]->AsNumber(), (*Xyr)[1]->AsNumber(), (*Xyr)[2]->AsNumber()});
					}
				}
			}
			if (J->TryGetArrayField(TEXT("actions"), Arr) && Arr)
			{
				for (const TSharedPtr<FJsonValue>& V : *Arr)
				{
					S.Info.ActionNames.push_back(ToUtf8(V.IsValid() ? V->AsString() : FString()));
				}
			}
			FString Str;
			if (J->TryGetStringField(TEXT("policy"), Str))
			{
				S.Info.Policy = ToUtf8(Str);
			}
			if (J->TryGetStringField(TEXT("note"), Str))
			{
				S.Info.Note = ToUtf8(Str);
			}
			const TSharedPtr<FJsonObject>* Brains = nullptr;
			if (J->TryGetObjectField(TEXT("brains"), Brains) && Brains && Brains->IsValid())
			{
				FString All;
				for (const TPair<FString, TSharedPtr<FJsonValue>>& P : (*Brains)->Values)
				{
					All += FString::Printf(TEXT("%s%s=%s"), All.IsEmpty() ? TEXT("") : TEXT(", "), *P.Key, P.Value.IsValid() ? *P.Value->AsString() : TEXT("?"));
				}
				S.Info.Brains = ToUtf8(All);
			}
			// 곁 파일: 먹이 격자·사체 (.r9fd)
			const FString FoodPath = FPaths::ChangeExtension(Path, TEXT("r9fd"));
			TArray<uint8> FoodBytes;
			S.bFoodKnown = false;
			if (FPaths::FileExists(FoodPath) && FFileHelper::LoadFileToArray(FoodBytes, *FoodPath))
			{
				FR9FoodSide Food;
				std::string FE;
				if (ParseFoodSide(FoodBytes.GetData(), static_cast<std::size_t>(FoodBytes.Num()), Food, FE))
				{
					TSharedPtr<FJsonObject> FJ;
					const TSharedRef<TJsonReader<>> FR = TJsonReaderFactory<>::Create(Utf8(Food.HeaderJson));
					if (FJsonSerializer::Deserialize(FR, FJ) && FJ.IsValid())
					{
						S.Info.G = Food.G;
						if (FJ->TryGetNumberField(TEXT("cell_units"), Num) && Num > 0.0)
						{
							S.Info.CellUnits = Num;
						}
						const auto ReadCaps = [&FJ](const TCHAR* Key, std::vector<float>& Out)
						{
							const TArray<TSharedPtr<FJsonValue>>* CapArr = nullptr;
							if (FJ->TryGetArrayField(Key, CapArr) && CapArr)
							{
								for (const TSharedPtr<FJsonValue>& CV : *CapArr)
								{
									Out.push_back(static_cast<float>(CV.IsValid() ? CV->AsNumber() : 0.0));
								}
							}
						};
						ReadCaps(TEXT("grass_cap"), S.Info.GrassCap);
						ReadCaps(TEXT("root_cap"), S.Info.RootCap);
					}
					const std::size_t Attached = AttachFood(S.Replay.Frames, Food);
					S.bFoodKnown = Attached == S.Replay.Frames.size() && S.Info.G > 0;
					UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 곁 파일 %s — 먹이 격자 %d×%d, 프레임 %d/%d 붙임"), *FoodPath, Food.G, Food.G,
						   static_cast<int32>(Attached), static_cast<int32>(S.Replay.Frames.size()));
				}
				else
				{
					UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 곁 파일 %s 를 못 읽음: %s — 풀·사체 없이 재생"), *FoodPath, *Utf8(FE));
				}
			}
			// 곁 파일: 사건 시각표 (.events.json) — 물기 결과(죽임·상처·반격)를 가른다
			const FString EventsPath = FPaths::ChangeExtension(Path, TEXT("events.json"));
			FString EventsText;
			S.bEventsKnown = false;
			if (FPaths::FileExists(EventsPath) && FFileHelper::LoadFileToString(EventsText, *EventsPath))
			{
				TSharedPtr<FJsonObject> EJ;
				const TSharedRef<TJsonReader<>> ER = TJsonReaderFactory<>::Create(EventsText);
				const TArray<TSharedPtr<FJsonValue>>* Events = nullptr;
				if (FJsonSerializer::Deserialize(ER, EJ) && EJ.IsValid() && EJ->TryGetArrayField(TEXT("events"), Events) && Events)
				{
					const int64 Base = static_cast<int64>(S.Replay.Frames[0].Step);
					int32 Used = 0;
					for (const TSharedPtr<FJsonValue>& EV : *Events)
					{
						const TSharedPtr<FJsonObject>* EO = nullptr;
						if (!EV.IsValid() || !EV->TryGetObject(EO) || !EO || !EO->IsValid())
						{
							continue;
						}
						FString Kind;
						double Frame = -1.0, Wolf = 0.0, Prey = 0.0, Uid = 0.0;
						(*EO)->TryGetStringField(TEXT("kind"), Kind);
						(*EO)->TryGetNumberField(TEXT("frame"), Frame);
						(*EO)->TryGetNumberField(TEXT("wolf"), Wolf);
						(*EO)->TryGetNumberField(TEXT("prey"), Prey);
						(*EO)->TryGetNumberField(TEXT("uid"), Uid);
						FR9Event E2;
						if (Kind == TEXT("bite_kill"))
						{
							E2.Kind = ER9Event::BiteKill;
						}
						else if (Kind == TEXT("bite_wound"))
						{
							E2.Kind = ER9Event::BiteWound;
						}
						else if (Kind == TEXT("bite_counter"))
						{
							E2.Kind = ER9Event::Counter;
						}
						else if (Kind == TEXT("death_starve"))
						{
							E2.Kind = ER9Event::Starve;
						}
						else
						{
							continue;
						}
						E2.A = static_cast<uint32>(Wolf);
						E2.B = static_cast<uint32>(E2.Kind == ER9Event::Starve ? Uid : Prey);
						const int64 Idx = static_cast<int64>(Frame) - Base;
						if (Idx >= 0 && Idx < static_cast<int64>(S.Replay.Frames.size()))
						{
							S.Replay.Frames[static_cast<std::size_t>(Idx)].Events.push_back(E2);
							++Used;
						}
					}
					S.bEventsKnown = true;
					UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 곁 파일 %s — 사건 %d"), *EventsPath, Used);
				}
			}
			UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 재생 파일 %s — 프레임 %d%s"), *Path, static_cast<int32>(S.Replay.Frames.size()),
				   S.Replay.bTruncated ? TEXT(" (끝 스텝 덜 써짐 — 버림)") : TEXT(""));
		}
		S.ReplayCursor = 0;
		S.Cur = S.Replay.Frames[0];
	}
	float CapMax = S.Info.GrassCapMax;
	for (const float C : S.Info.GrassCap)
	{
		CapMax = FMath::Max(CapMax, C);
	}
	if (CapMax <= 0.0f)
	{
		for (const float C : S.Cur.Grass)
		{
			CapMax = FMath::Max(CapMax, C);
		}
	}
	S.GrassCapMax = CapMax > 1e-6f ? CapMax : 1.0f;
	if (S.Info.W <= 0.0 || S.Info.H <= 0.0 || S.Info.UnitCm <= 0.0)
	{
		OutError = TEXT("세계 크기가 이상하다");
		return false;
	}
	S.Prev = S.Cur;
	S.RebuildBothIndex();
	S.bHavePrev = true;
	S.Accum = 0.0;
	S.Alpha = 0.0;
	S.StepsShown = 0;
	S.FoodWin = EcoR9Demo::FR9FoodWindow();   // 새 판 — 풀 창을 다시 읽는다
	S.bWinPrevValid = false;
	return true;
}

bool UEcoR9DemoSubsystem::AdvanceFrame()
{
	FEcoR9DemoState& S = *State;
	if (S.Settings.Mode == FEcoR9DemoSettings::EMode::Live)
	{
		if (EcoR9DemoCVars::Loop() && EcoR9DemoCVars::RestartSteps() > 0 && S.StepsShown >= EcoR9DemoCVars::RestartSteps())
		{
			RestartRun(TEXT("다시 시작 스텝"));
			return IsRunning();
		}
		S.Prev = S.Cur;
		std::string E;
		const double T0 = FPlatformTime::Seconds();
		if (!S.Live || !S.Live->Next(S.Cur, E))
		{
			Fail(FString::Printf(TEXT("코어 스텝 실패: %s"), *EcoR9DemoSubsystemImpl::Utf8(E)));
			return false;
		}
		S.AdvanceMsSum += 1000.0 * (FPlatformTime::Seconds() - T0);
		++S.AdvanceCount;
	}
	else
	{
		if (S.ReplayCursor + 1 >= static_cast<int32>(S.Replay.Frames.size()))
		{
			if (EcoR9DemoCVars::Loop())
			{
				RestartRun(TEXT("재생 끝"));
				return IsRunning();
			}
			return true;   // 마지막 프레임에 머문다
		}
		S.Prev = S.Cur;
		++S.ReplayCursor;
		S.Cur = S.Replay.Frames[static_cast<std::size_t>(S.ReplayCursor)];
	}
	++S.StepsShown;
	S.RebuildIndex();
	OnFrameAdvanced();
	return true;
}

void UEcoR9DemoSubsystem::RestartRun(const TCHAR* Why)
{
	FEcoR9DemoState& S = *State;
	LogSummary(Why);
	ClearBodies();
	S.Markers.Reset();
	S.Recent.Reset();
	S.DeerKilled = S.BoarKilled = S.BoarWounded = S.Counters = S.WolvesKilled = S.Starved = S.Respawns = 0;
	FMemory::Memzero(S.Eats);
	FMemory::Memzero(S.BittenSp);
	FMemory::Memzero(S.StruckSp);
	FMemory::Memzero(S.StarvedSp);
	S.Gores = S.GoreKills = 0;
	for (double& D : S.DugUntil)
	{
		D = -1.0;
	}
	++S.RunIndex;
	FString Err;
	if (!OpenSource(Err))
	{
		Fail(Err);
		return;
	}
	if (S.Info.NumSpecies > EcoR9Demo::kNumOldSpecies)
	{
		LoadFaunaAssets();   // 세 종 판으로 시작했다가 새 두뇌가 생겨 동물 장면으로 바뀐 판 (처음 한 번만 읽음)
	}
	S.bAutoFollowing = false;
	S.FollowA = S.FollowB = 0;
	S.CamWhat.Reset();
	S.SubjectDeadAt = -1.0;
	if (S.Info.bWhole)
	{
		// 검토 (11-13): 큰 세계는 시드마다 은신처·무리 자리가 새로 생긴다 (EcoR9Scene.h BuildBigScene — Spec.Seed 로 은신처·패치·자리를 고름). 작은 세계는 장면 파일의
		// 은신처 그대로라 장식을 한 번만 세웠지만, 큰 세계는 보이는 수풀·바위가 옛 판 자리에 남아 '안 보이는 은신처'에 숨게 된다 — 장식·표식 액터를 새 판으로 다시 세운다
		if (AActor* OldDecor = S.Decor.Get())
		{
			SpawnedActors.Remove(OldDecor);
			OldDecor->Destroy();
		}
		S.Decor.Reset();
		SpawnStaticDecor();
		S.SiteIndex = 0;
		S.bSiteLocked = false;   // 새 판은 무리 자리가 새로 생긴다 — 고른 자리 번호를 들고 가지 않는다
	}
	UpdateFood();
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 다시 시작 (%s) — 판 %d, 시드 %llu"), Why, S.RunIndex, static_cast<unsigned long long>(S.Info.Seed));
}

// -----------------------------------------------------------------------------
// 무대 자리
// -----------------------------------------------------------------------------

void UEcoR9DemoSubsystem::BeginStreamingAt(const FVector& CenterCm, float RadiusCm)
{
	UWorld* World = GetWorld();
	FEcoR9DemoState& S = *State;
	if (!IsValid(Manager))
	{
		FActorSpawnParameters P;
		P.Name = MakeUniqueObjectName(World->PersistentLevel, AActor::StaticClass(), TEXT("EcoR9Demo_Manager"));
		P.ObjectFlags |= RF_Transient;
		P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Manager = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform(CenterCm), P);
		if (!Manager)
		{
			return;
		}
		Manager->SetReplicates(false);
		USceneComponent* Root = NewObject<USceneComponent>(Manager, TEXT("Root"));
		Manager->SetRootComponent(Root);
		Root->RegisterComponent();
		SpawnedActors.Add(Manager);
		// 스트리밍 원천은 World Partition 월드에만 (없는 월드에서 등록하면 엔진 check 에 걸린다)
		if (World->IsPartitionedWorld())
		{
			UWorldPartitionStreamingSourceComponent* Src = NewObject<UWorldPartitionStreamingSourceComponent>(Manager, TEXT("R9DemoStreaming"));
			Src->DisableStreamingSource();
			Src->RegisterComponent();
			Manager->AddInstanceComponent(Src);
			S.Streamer = Src;
		}
	}
	Manager->SetActorLocation(CenterCm);
	if (UWorldPartitionStreamingSourceComponent* Src = S.Streamer.Get())
	{
		Src->Shapes.Reset();
		FStreamingSourceShape& Shape = Src->Shapes.AddDefaulted_GetRef();
		Shape.bUseGridLoadingRange = false;
		Shape.Radius = RadiusCm;
		Shape.Location = FVector::ZeroVector;
		Src->EnableStreamingSource();
	}
	S.PhaseStart = World->GetTimeSeconds();
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 스트리밍 원천 (%.0f, %.0f) m 반지름 %.0f m%s"), CenterCm.X / 100.0, CenterCm.Y / 100.0, RadiusCm / 100.0,
		   S.Streamer.IsValid() ? TEXT("") : TEXT(" (World Partition 아님 — 기다리지 않음)"));
}

void UEcoR9DemoSubsystem::ScanCells(EcoR9Demo::FR9ScanGrid& G, TArray<uint8>* Kinds, TArray<EcoR9Demo::FR9CoverPoint>* Cover, FEcoR9ScanCounts& Out)
{
	// 훑기 격자 칸마다: 1 땅 높이 (지형, 없으면 바닥 메시) · 2 물 (바다·호수·강) · 3 가파름 · 4 걸리는 것 (나무·바위·건물). 고리 훑기와 맵 전체 훑기가 같이 쓴다
	using namespace EcoR9DemoSubsystemImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	const int32 N = G.Nx * G.Ny;
	if (Kinds)
	{
		Kinds->Init(kLandOpen, N);
	}
	// 1. 땅 높이: 지형, 없으면 바닥 메시 (지형 없는 일반 맵도). 바닥 메시 칸은 그 메시(인스턴스)를 적어 둔다 — 4 에서 제 땅을 걸리는 것으로 막지 않게
	RefreshProbeIgnore();
	const FGroundProbe Ground(*World, S.ProbeIgnore);
	int32 FromLand = 0, FromMesh = 0;
	TArray<const UPrimitiveComponent*> GroundComp;
	TArray<int32> GroundItem;
	GroundComp.Init(nullptr, N);
	GroundItem.Init(INDEX_NONE, N);
	for (int32 y = 0; y < G.Ny; ++y)
	{
		for (int32 x = 0; x < G.Nx; ++x)
		{
			float Z = 0.0f;
			bool bMesh = false;
			const int32 K = static_cast<int32>(G.Index(x, y));
			if (Ground.At(G.CellX(x), G.CellY(y), Z, &bMesh, &GroundComp[K], &GroundItem[K]))
			{
				G.Height[G.Index(x, y)] = Z;
				if (bMesh)
				{
					++FromMesh;
				}
				else
				{
					++FromLand;
				}
			}
		}
	}
	const int32 NoGround = N - FromLand - FromMesh;
	int32 Sea = 0, Water = 0;
	// 칸 종류 적기 (맵 전체 땅 — 코어 ELand): 이 단계에서 새로 막힌 칸에 종류를 붙인다
	auto Tag = [&G, Kinds](uint8 Kind)
	{
		if (!Kinds)
		{
			return;
		}
		for (int32 k = 0; k < Kinds->Num(); ++k)
		{
			if (G.Blocked[static_cast<std::size_t>(k)] != 0 && (*Kinds)[k] == EcoR9Demo::kLandOpen)
			{
				(*Kinds)[k] = Kind;
			}
		}
	};
	auto Mark = [&G](int32 X, int32 Y, int32& Counter)
	{
		uint8& B = G.Blocked[G.Index(X, Y)];
		if (B == 0)
		{
			B = 1;
			++Counter;
		}
	};
	const FBox ScanBox(FVector(G.X0, G.Y0, -1e7), FVector(G.X0 + G.Nx * G.CellCm, G.Y0 + G.Ny * G.CellCm, 1e7));
	auto Overlaps2D = [&ScanBox](const FBox& B)
	{
		return B.IsValid && B.Max.X >= ScanBox.Min.X && B.Min.X <= ScanBox.Max.X && B.Max.Y >= ScanBox.Min.Y && B.Min.Y <= ScanBox.Max.Y;
	};
	// 2. 물: 바다 = 수면 높이 + 1 m 아래 땅, 호수·강 = 그 물 몸체 충돌만 선 검사 (EcoV3IslandStage.cpp 와 같은 꼴). 물 몸체가 없는 맵은 건너뜀
	double OceanZ = -std::numeric_limits<double>::infinity();
	TArray<AActor*> Waters;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		const FString Cls = It->GetClass()->GetName();
		if (!Cls.StartsWith(TEXT("WaterBody")))
		{
			continue;
		}
		if (Cls.Contains(TEXT("Ocean")))
		{
			OceanZ = FMath::Max(OceanZ, It->GetActorLocation().Z);
		}
		else
		{
			Waters.Add(*It);
		}
	}
	if (FMath::IsFinite(OceanZ))
	{
		for (int32 y = 0; y < G.Ny; ++y)
		{
			for (int32 x = 0; x < G.Nx; ++x)
			{
				const float Z = G.Height[G.Index(x, y)];
				if (!FMath::IsNaN(Z) && Z <= OceanZ + 100.0)
				{
					Mark(x, y, Sea);
				}
			}
		}
	}
	FCollisionQueryParams WaterParams(SCENE_QUERY_STAT(EcoR9DemoWater), true);
	for (AActor* A : Waters)
	{
		TInlineComponentArray<UPrimitiveComponent*> Prims(A);
		TArray<UPrimitiveComponent*> Hits;
		FBox Box(ForceInit);
		for (UPrimitiveComponent* C : Prims)
		{
			if (C && C->IsRegistered() && C->IsQueryCollisionEnabled())
			{
				Hits.Add(C);
				Box += C->Bounds.GetBox();
			}
		}
		if (Hits.IsEmpty() || !Overlaps2D(Box))
		{
			continue;
		}
		const int32 Ix0 = FMath::Max(0, FMath::FloorToInt32((Box.Min.X - G.X0) / G.CellCm));
		const int32 Iy0 = FMath::Max(0, FMath::FloorToInt32((Box.Min.Y - G.Y0) / G.CellCm));
		const int32 Ix1 = FMath::Min(G.Nx - 1, FMath::FloorToInt32((Box.Max.X - G.X0) / G.CellCm));
		const int32 Iy1 = FMath::Min(G.Ny - 1, FMath::FloorToInt32((Box.Max.Y - G.Y0) / G.CellCm));
		for (int32 y = Iy0; y <= Iy1; ++y)
		{
			for (int32 x = Ix0; x <= Ix1; ++x)
			{
				const float CellGround = G.Height[G.Index(x, y)];
				if (FMath::IsNaN(CellGround))
				{
					continue;
				}
				const FVector Start(G.CellX(x), G.CellY(y), Box.Max.Z + 100.0);
				const FVector End(G.CellX(x), G.CellY(y), FMath::Min(Box.Min.Z, static_cast<double>(CellGround)) - 100.0);
				double Surface = -std::numeric_limits<double>::infinity();
				for (UPrimitiveComponent* C : Hits)
				{
					FHitResult Hit;
					if (C->LineTraceComponent(Hit, Start, End, WaterParams))
					{
						Surface = FMath::Max(Surface, Hit.ImpactPoint.Z);
					}
				}
				if (FMath::IsFinite(Surface) && CellGround < Surface + 100.0)
				{
					Mark(x, y, Water);
				}
			}
		}
	}
	Tag(EcoR9Demo::kLandVoid);   // 바다·호수·강
	// 3. 가파름: 이웃 칸 높이 차 / 칸 > 0.36 (약 20° — 평지 무대 고르기) [어림]. 맵 전체 땅은 1.17 (법선 Z < 0.65 — 팀 이동 제약·섬 무대와 같은 문턱)
	const int32 Steep = static_cast<int32>(MarkSteep(G, Kinds ? kWholeSteep : 0.36));
	Tag(EcoR9Demo::kLandSteep);
	// 4. 나무·바위·선인장·야자·건물 (정적·인스턴스 메시 경계 상자). 풀·눈 덮개 같은 낮은 장식은 뺀다.
	//    땅보다 30 cm 넘게 솟은 것만 막는다 — 지형 없는 맵의 바닥 메시(위가 곧 땅)는 막지 않는다
	static const TCHAR* const kDecorWords[] = {TEXT("grass"), TEXT("snow"), TEXT("flower"), TEXT("clover"), TEXT("fern"), TEXT("weed"), TEXT("decal"), TEXT("pebble")};
	int64 Objects = 0;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* A = *It;
		if (!A || A == Manager)
		{
			continue;
		}
		const FString Cls = A->GetClass()->GetName();
		if (Cls.Contains(TEXT("HLOD")) || Cls.StartsWith(TEXT("Landscape")) || Cls.StartsWith(TEXT("WaterBody")) || Cls.Contains(TEXT("Sky")))
		{
			continue;
		}
		TInlineComponentArray<UStaticMeshComponent*> Comps(A);
		for (UStaticMeshComponent* Comp : Comps)
		{
			const UStaticMesh* Mesh = Comp ? Comp->GetStaticMesh() : nullptr;
			if (!Mesh || !Comp->IsRegistered() || !Comp->IsVisible() || !Overlaps2D(Comp->Bounds.GetBox()))
			{
				continue;
			}
			const FString MeshName = Mesh->GetName().ToLower();
			bool bDecor = false;
			for (const TCHAR* W : kDecorWords)
			{
				bDecor = bDecor || MeshName.Contains(W);
			}
			if (bDecor)
			{
				continue;
			}
			if (const UInstancedStaticMeshComponent* Ism = Cast<UInstancedStaticMeshComponent>(Comp))
			{
				const FBox MeshBox = Mesh->GetBoundingBox();
				const int32 Count = Ism->GetInstanceCount();
				// 맵 전체 땅: 나무는 줄기 둘레 3 m 만 막고(섬 무대 숲 칸 규칙), 나무·큰 바위는 은신처 곁 후보점으로 적는다
				const bool bTree = Cover && AnyWordIn(MeshName, kTreeWords);
				const bool bRock = Cover && !bTree && AnyWordIn(MeshName, kRockWords);
				for (int32 i = 0; i < Count; ++i)
				{
					FTransform T;
					if (!Ism->GetInstanceTransform(i, T, /*bWorldSpace*/ true))
					{
						continue;
					}
					const FBox B = MeshBox.TransformBy(T);
					const FVector Size = B.GetSize();
					if (FMath::Max(Size.X, Size.Y) < 80.0 || Size.Z < 40.0 || !Overlaps2D(B))
					{
						continue;
					}
					if (bTree)
					{
						const FVector L = T.GetLocation();
						EcoR9Demo::FR9Box Trunk;
						Trunk.MinX = L.X - kTreeTrunkCm;
						Trunk.MaxX = L.X + kTreeTrunkCm;
						Trunk.MinY = L.Y - kTreeTrunkCm;
						Trunk.MaxY = L.Y + kTreeTrunkCm;
						Trunk.MinZ = B.Min.Z;
						Trunk.MaxZ = B.Max.Z;
						Objects += MarkObstacle(G, Trunk, 0.0, kObstacleClearCm, kObstacleReachCm);
						Cover->Add(EcoR9Demo::FR9CoverPoint{L.X, L.Y, 1.0});
						++Out.Trees;
						continue;
					}
					if (bRock && FMath::Max(Size.X, Size.Y) >= 200.0)
					{
						Cover->Add(EcoR9Demo::FR9CoverPoint{B.GetCenter().X, B.GetCenter().Y, FMath::Clamp(FMath::Max(Size.X, Size.Y) / 200.0, 1.0, 8.0)});
						++Out.Rocks;
					}
					// 넓은 조각(10 m 넘게)이 그 칸의 땅이면 (바닥 조각을 인스턴스로 깐 맵) 그 칸은 막지 않는다. 나무·덤불 줄기 꼭대기가 땅으로 읽힌 칸은
					// 작은 조각이라 그대로 막는다
					const bool bWide = FMath::Max(Size.X, Size.Y) >= kGroundPieceCm;
					Objects += MarkObstacleIf(G, ToR9Box(B), kObstaclePadCm, kObstacleClearCm, kObstacleReachCm,
											  [&GroundComp, &GroundItem, Ism, i, bWide](std::size_t Cell)
											  { return bWide && GroundComp[static_cast<int32>(Cell)] == Ism && GroundItem[static_cast<int32>(Cell)] == i; });
				}
			}
			else
			{
				const FBox B = Comp->Bounds.GetBox();
				const FVector Size = B.GetSize();
				if (FMath::Max(Size.X, Size.Y) > 20000.0 || FMath::Max(Size.X, Size.Y) < 80.0 || Size.Z < 40.0)
				{
					continue;
				}
				if (Cover && FMath::Max(Size.X, Size.Y) >= 200.0 && (AnyWordIn(MeshName, kRockWords) || AnyWordIn(MeshName, kTreeWords)))
				{
					Cover->Add(EcoR9Demo::FR9CoverPoint{B.GetCenter().X, B.GetCenter().Y, FMath::Clamp(FMath::Max(Size.X, Size.Y) / 200.0, 1.0, 8.0)});
					++Out.Rocks;
				}
				// 넓은 메시(10 m 넘게)가 그 칸의 땅이면 (지형 대신 언덕진 바닥 메시) 그 칸은 막지 않는다 — 가파름(3)이 언덕 비탈을 따로 막는다
				const bool bWide = FMath::Max(Size.X, Size.Y) >= kGroundPieceCm;
				Objects += MarkObstacleIf(G, ToR9Box(B), kObstaclePadCm, kObstacleClearCm, kObstacleReachCm,
										  [&GroundComp, Comp, bWide](std::size_t Cell) { return bWide && GroundComp[static_cast<int32>(Cell)] == Comp; });
			}
		}
	}
	Tag(EcoR9Demo::kLandObstacle);   // 나무·바위·건물
	Out.FromLand = FromLand;
	Out.FromMesh = FromMesh;
	Out.NoGround = NoGround;
	Out.Sea = Sea;
	Out.Water = Water;
	Out.Steep = Steep;
	Out.Objects += Objects;
}


bool UEcoR9DemoSubsystem::ScanAndPick(int32 Ring)
{
	using namespace EcoR9DemoSubsystemImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	const double T0 = FPlatformTime::Seconds();
	if (!S.bTeamEco)
	{
		// World Partition 맵은 팀 지역·조정자가 시작 때 아직 안 불렸을 수 있다 — 고리를 불러온 뒤 다시 센다
		DescribeTeamEco(*World);
		if (S.bTeamEco)
		{
			UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] %s"), *S.TeamEcoNote);
		}
	}
	Ring = FMath::Clamp(Ring, 0, kNumRings - 1);
	const bool bLast = Ring + 1 >= kNumRings;
	const double Half = kRingHalfCm[Ring];
	const FVector2D Pref(S.SearchOrigin.X, S.SearchOrigin.Y);
	FR9ScanGrid G;
	G.CellCm = kScanCellCm;
	G.Nx = G.Ny = FMath::RoundToInt32(2.0 * Half / kScanCellCm);
	G.X0 = Pref.X - Half;
	G.Y0 = Pref.Y - Half;
	const int32 N = G.Nx * G.Ny;
	G.Height.assign(static_cast<std::size_t>(N), std::numeric_limits<float>::quiet_NaN());
	G.Blocked.assign(static_cast<std::size_t>(N), 0);
	FEcoR9ScanCounts Counts;
	ScanCells(G, nullptr, nullptr, Counts);
	const int32 FromLand = Counts.FromLand, FromMesh = Counts.FromMesh, NoGround = Counts.NoGround, Sea = Counts.Sea, Water = Counts.Water, Steep = Counts.Steep;
	const int64 Objects = Counts.Objects;
	const FGroundProbe Ground(*World, S.ProbeIgnore);
	const FBox ScanBox(FVector(G.X0, G.Y0, -1e7), FVector(G.X0 + G.Nx * G.CellCm, G.Y0 + G.Ny * G.CellCm, 1e7));
	auto Overlaps2D = [&ScanBox](const FBox& B)
	{
		return B.IsValid && B.Max.X >= ScanBox.Min.X && B.Min.X <= ScanBox.Max.X && B.Max.Y >= ScanBox.Min.Y && B.Min.Y <= ScanBox.Max.Y;
	};
	// 5. 맵에 이미 있는 생태 (지역 상자·서식지·은신처·팀 동물·무리 이주 길) — 막지는 않고 '되도록 피함' 칸으로 둔다 (섞여 보이지 않게)
	int32 Zones = 0;
	int64 AvoidCells = 0;
	const FName RouteName(TEXT("EcoHerdMigrationRoute"));
	TArray<FName> AvoidNames;
	for (const FAvoidKind& K : kAvoidKinds)
	{
		AvoidNames.Add(FName(K.Class));
	}
	const APlayerController* FirstPC = World->GetFirstPlayerController();
	const APawn* PlayerPawn = FirstPC ? FirstPC->GetPawn() : nullptr;
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* A = *It;
		if (!A || A == Manager || A == PlayerPawn || SpawnedActors.Contains(A))
		{
			continue;
		}
		if (IsKindOfName(A, RouteName))
		{
			// 길 점 (TArray<FVector> Points, 월드 cm) 마디마다 상자 — 헤더 없이 이름으로 읽는다
			const FArrayProperty* Arr = FindFProperty<FArrayProperty>(A->GetClass(), TEXT("Points"));
			const FStructProperty* Inner = Arr ? CastField<FStructProperty>(Arr->Inner) : nullptr;
			if (!Inner || Inner->Struct != TBaseStructure<FVector>::Get())
			{
				continue;
			}
			double Width = 600.0;
			if (const FFloatProperty* W = FindFProperty<FFloatProperty>(A->GetClass(), TEXT("CorridorWidth")))
			{
				Width = W->GetPropertyValue_InContainer(A);
			}
			FScriptArrayHelper Help(Arr, Arr->ContainerPtrToValuePtr<void>(A));
			const double Pad = 0.5 * FMath::Max(0.0, Width) + kRouteExtraPadCm;
			for (int32 i = 0; i + 1 < Help.Num(); ++i)
			{
				const FVector P0 = *reinterpret_cast<const FVector*>(Help.GetRawPtr(i));
				const FVector P1 = *reinterpret_cast<const FVector*>(Help.GetRawPtr(i + 1));
				FBox Seg(ForceInit);
				Seg += P0;
				Seg += P1;
				AvoidCells += MarkAvoid(G, ToR9Box(Seg), Pad);
			}
			Zones += Help.Num() > 1 ? 1 : 0;
			continue;
		}
		for (int32 Kind = 0; Kind < AvoidNames.Num(); ++Kind)
		{
			if (!IsKindOfName(A, AvoidNames[Kind]))
			{
				continue;
			}
			const FAvoidKind& K = kAvoidKinds[Kind];
			FBox B(ForceInit);
			double Pad = K.PadCm;
			if (!K.bPoint)
			{
				FVector Origin = FVector::ZeroVector, Extent = FVector::ZeroVector;
				A->GetActorBounds(/*bOnlyCollidingComponents*/ false, Origin, Extent);
				if (Extent.X >= 100.0 || Extent.Y >= 100.0)
				{
					B = FBox(Origin - Extent, Origin + Extent);
				}
			}
			if (!B.IsValid)
			{
				B = FBox(A->GetActorLocation(), A->GetActorLocation());
				Pad = FMath::Max(Pad, 2000.0);
			}
			if (Overlaps2D(B.ExpandBy(Pad)))
			{
				AvoidCells += MarkAvoid(G, ToR9Box(B), Pad);
				++Zones;
			}
			break;
		}
	}
	S.NumAvoid = Zones;
	// 6. 고르기: 트인 평지 (기존 생태를 피해서) → 앞 고리면 넓힌다 → 마지막 고리면 기존 생태 곁이라도 → 가장 덜 막힌 곳 → 시작점
	FR9PickParams P;
	P.SideCm = FMath::Max(S.Info.W, S.Info.H) * S.Info.UnitCm;
	P.MarginCm = kStageMarginCm;
	P.PrefX = Pref.X;
	P.PrefY = Pref.Y;
	P.Stride = 3;
	P.bAvoid = G.HasAvoid();
	FR9PickResult R = PickStage(G, P);
	FString How;
	bool bFallback = false;   // 참 = 트인 평지가 아닌 마지막 길 (경고 줄)
	if (R.bOk)
	{
		How = G.HasAvoid() ? TEXT("트인 평지 (기존 생태에서 떨어진 곳)") : TEXT("트인 평지");
	}
	const double T1 = FPlatformTime::Seconds();
	const FString ScanLine = FString::Printf(
		TEXT("훑기 고리 %d/%d (시작점 둘레 %.0f m, %d×%d 칸 4 m) · 땅: 지형 %d · 바닥 메시 %d · 없음 %d · 막힘: 바다 %d · 호수·강 %d · 가파름 %d · 나무·바위·건물 %lld · ")
			TEXT("피할 생태 %d 곳 (%lld 칸) · %.2f 초"),
		Ring + 1, kNumRings, Half / 100.0, G.Nx, G.Ny, FromLand, FromMesh, NoGround, Sea, Water, Steep, static_cast<long long>(Objects), Zones,
		static_cast<long long>(AvoidCells), T1 - T0);
	if (!R.bOk && !bLast)
	{
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] %s | 이 둘레에는 %s — 둘레를 %.0f m 로 넓힌다"), *ScanLine,
			   G.HasAvoid() ? TEXT("기존 생태에서 떨어진 트인 평지가 없음") : TEXT("트인 평지가 없음"), kRingHalfCm[Ring + 1] / 100.0);
		return false;
	}
	if (!R.bOk && G.HasAvoid())
	{
		P.bAvoid = false;
		R = PickStage(G, P);
		if (R.bOk)
		{
			How = TEXT("트인 평지 (기존 생태에서 떨어진 자리가 없어 그 곁 — 팀 개체가 보일 수 있다)");
		}
	}
	bool bNoGround = false;
	if (!R.bOk)
	{
		bFallback = true;
		R = PickLeastBlocked(G, P);
		if (R.bOk)
		{
			bNoGround = !R.bHeightKnown;
			How = FString::Printf(TEXT("트인 평지를 못 찾음 — 가장 덜 막힌 곳 (무대 안 막힌·땅 없는 칸 %lld/%lld · 피할 칸 %lld)%s"),
								  static_cast<long long>(R.BlockedCells), static_cast<long long>(R.StageCells), static_cast<long long>(R.AvoidCells),
								  bNoGround ? TEXT(" — 땅을 하나도 못 읽어 시작점 높이에 평평하게 그린다") : TEXT(""));
		}
	}
	if (R.bOk)
	{
		const double Z = bNoGround ? S.SearchOrigin.Z - kNoGroundDropCm : R.MeanCm;
		S.StageCenter = FVector(R.Cx, R.Cy, Z);
		S.StageLine = FString::Printf(TEXT("무대 가운데 (%.1f, %.1f) m · %s · 높이 폭 %.1f m · 시작점(%s)에서 %.0f m · 후보 %lld · 여유 %.0f m"), R.Cx / 100.0,
									  R.Cy / 100.0, *How, R.RangeCm / 100.0, *S.OriginLabel, FVector2D::Distance(FVector2D(R.Cx, R.Cy), Pref) / 100.0,
									  static_cast<long long>(R.Candidates), R.MarginUsed / 100.0);
	}
	else
	{
		bFallback = true;
		float Z = 0.0f;
		S.StageCenter = FVector(Pref.X, Pref.Y, Ground.At(Pref.X, Pref.Y, Z) ? static_cast<double>(Z) : S.SearchOrigin.Z - kNoGroundDropCm);
		S.StageLine = FString::Printf(TEXT("트인 평지를 못 찾음 — 시작점(%s) (%.1f, %.1f) m 에 그대로 둠"), *S.OriginLabel, Pref.X / 100.0, Pref.Y / 100.0);
	}
	if (bFallback)
	{
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] %s | %s | 지형 액터 %d — 자리를 직접 주려면 Play 전에 eco.R9Demo.At x,y (m)"), *S.StageLine, *ScanLine,
			   Ground.Lands.Num());
	}
	else
	{
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] %s | %s | 지형 액터 %d"), *S.StageLine, *ScanLine, Ground.Lands.Num());
	}
	return true;
}

// -----------------------------------------------------------------------------
// 맵 전체 땅 모드 (2026-11-13) — 맵 땅을 불러와 4 m 로 훑고, 땅 지도를 코어 큰 세계 장면 생성기에 넘긴다
// -----------------------------------------------------------------------------

void UEcoR9DemoSubsystem::BeginWhole(UWorld& World)
{
	using namespace EcoR9DemoSubsystemImpl;
	FEcoR9DemoState& S = *State;
	const FVector O = S.SearchOrigin;
	const double MaxHalf = 0.5 * kWholeMaxSideCm;
	FBox Area(ForceInit);
	FString From;
	if (S.WholeSpec && S.AreaBox.IsValid)
	{
		// Play 중 다시 켬: 앞에 훑은 땅 지도를 그대로 쓴다 (다시 훑지 않음)
		Area = S.AreaBox;
		From = TEXT("앞에 훑은 땅 지도 그대로");
	}
	else if (S.Settings.AreaM > 120)
	{
		const double Half = 50.0 * FMath::Min(static_cast<double>(S.Settings.AreaM), kWholeMaxSideCm / 100.0);
		Area = FBox(FVector(O.X - Half, O.Y - Half, -1e7), FVector(O.X + Half, O.Y + Half, 1e7));
		From = FString::Printf(TEXT("eco.R9Demo.Area %d — 시작점 둘레 %d m 정사각"), S.Settings.AreaM, S.Settings.AreaM);
	}
	else
	{
		// 맵 전체: World Partition 이면 실행 세계 경계 (모든 셀 — 바다 몸체가 크면 넓을 수 있어 시작점 둘레 4 km 로 자름), 아니면 불린 지형 경계,
		// 지형이 없으면 폰이 설 수 있는 넓은 바닥 메시 경계, 그것도 없으면 시작점 둘레 240 m
		// 검토 (11-13): 위 '실행 세계 경계' 는 UWorldPartition::GetRuntimeWorldBounds 가 아니라 실행 해시의 스트리밍 칸 내용 경계 합으로 읽는다 (안 불린 칸 포함,
		// 늘 불리는 칸 — 바다·하늘·물 구역 — 은 빼서 바다 몸체로 넓어지지 않게). GetRuntimeWorldBounds 는 편집기 해시(EditorHash)가 있어야 값이 있는데
		// PIE·-game 월드에는 없다 (엔진 WorldPartition.h:514 DuplicateTransient · WorldPartition.cpp:787 -game 이면 nullptr) — 그대로면 Play 순간 불린
		// 지형 조각 몇 개 경계로 떨어져 섬 일부만 훑는다. 칸 경계가 비면 그때만 GetRuntimeWorldBounds (편집기 해시가 있는 월드)
		if (const UWorldPartition* WP = World.GetWorldPartition())
		{
			FBox B(ForceInit);
			int32 NumCells = 0;
			if (const UWorldPartitionRuntimeHash* Hash = WP->RuntimeHash.Get())
			{
				Hash->ForEachStreamingCells(
					[&B, &NumCells](const UWorldPartitionRuntimeCell* Cell)
					{
						if (Cell && !Cell->IsAlwaysLoaded())
						{
							const FBox& CellBox = Cell->GetContentBounds();
							if (CellBox.IsValid)
							{
								B += CellBox;
								++NumCells;
							}
						}
						return true;
					});
			}
			const TCHAR* BoundsFrom = TEXT("스트리밍 칸 내용 경계");
			if (!B.IsValid || B.GetSize().X <= 100.0 || B.GetSize().Y <= 100.0)
			{
				B = WP->GetRuntimeWorldBounds();   // 편집기 해시가 있는 월드에서만 값이 있다
				BoundsFrom = TEXT("실행 세계 경계");
			}
			if (B.IsValid && B.GetSize().X > 100.0 && B.GetSize().Y > 100.0)
			{
				// 늘 불리는 지형(스트리밍 칸에 들지 않음)은 지금 불린 경계로 더한다 — 지형을 늘 불리게 둔 WP 맵에서 땅이 빠지지 않게
				for (TActorIterator<ALandscapeProxy> It(&World); It; ++It)
				{
					FVector LC = FVector::ZeroVector, LE = FVector::ZeroVector;
					It->GetActorBounds(false, LC, LE);
					if (LE.X > 1.0 && LE.Y > 1.0)
					{
						B += FBox(LC - LE, LC + LE);
					}
				}
				Area = B;
				From = FString::Printf(TEXT("World Partition %s (칸 %d) + 불린 지형 %.0f × %.0f m"), BoundsFrom, NumCells, B.GetSize().X / 100.0, B.GetSize().Y / 100.0);
			}
		}
		if (!Area.IsValid)
		{
			for (TActorIterator<ALandscapeProxy> It(&World); It; ++It)
			{
				FVector C = FVector::ZeroVector, E = FVector::ZeroVector;
				It->GetActorBounds(false, C, E);
				if (E.X > 1.0 && E.Y > 1.0)
				{
					Area += FBox(C - E, C + E);
				}
			}
			if (Area.IsValid)
			{
				From = FString::Printf(TEXT("불린 지형 경계 %.0f × %.0f m"), Area.GetSize().X / 100.0, Area.GetSize().Y / 100.0);
			}
		}
		if (!Area.IsValid)
		{
			for (TActorIterator<AActor> It(&World); It; ++It)
			{
				TInlineComponentArray<UStaticMeshComponent*> Comps(*It);
				for (const UStaticMeshComponent* Comp : Comps)
				{
					if (!Comp || !Comp->IsRegistered() || Comp->GetCollisionResponseToChannel(ECC_Pawn) != ECR_Block)
					{
						continue;
					}
					const FBox B = Comp->Bounds.GetBox();
					if (FMath::Min(B.GetSize().X, B.GetSize().Y) >= 1000.0)
					{
						Area += B;
					}
				}
			}
			if (Area.IsValid)
			{
				From = FString::Printf(TEXT("지형 없음 — 넓은 바닥 메시 경계 %.0f × %.0f m"), Area.GetSize().X / 100.0, Area.GetSize().Y / 100.0);
			}
		}
		if (!Area.IsValid)
		{
			Area = FBox(O - FVector(12000.0, 12000.0, 1e7), O + FVector(12000.0, 12000.0, 1e7));
			From = TEXT("땅 경계를 모름 — 시작점 둘레 240 m");
		}
	}
	// 4 km 상한 (시작점 둘레로 자름 — 시작점이 상자 밖이면 상자 가운데 둘레)
	const FVector2D Pivot = Area.IsInsideOrOnXY(O) ? FVector2D(O.X, O.Y) : FVector2D(Area.GetCenter().X, Area.GetCenter().Y);
	FBox Clip(FVector(FMath::Max(Area.Min.X, Pivot.X - MaxHalf), FMath::Max(Area.Min.Y, Pivot.Y - MaxHalf), -1e7),
			  FVector(FMath::Min(Area.Max.X, Pivot.X + MaxHalf), FMath::Min(Area.Max.Y, Pivot.Y + MaxHalf), 1e7));
	if (!Clip.IsValid || Clip.Max.X <= Clip.Min.X || Clip.Max.Y <= Clip.Min.Y)
	{
		Clip = FBox(O - FVector(12000.0, 12000.0, 1e7), O + FVector(12000.0, 12000.0, 1e7));
	}
	S.AreaBox = Clip;
	S.AreaLine = From;
	const double Radius = 0.5 * FVector2D(Clip.GetSize().X, Clip.GetSize().Y).Size() + 5000.0;
	UE_LOG(LogEcoR9Demo, Log,
		   TEXT("[EcoR9Demo] 켬 — 실시간 (언리얼 C++ 추론) · 맵 전체 땅 | 맵 %s (World Partition %s) | 훑을 사각 x %.0f ~ %.0f m, y %.0f ~ %.0f m (%s) | ")
			   TEXT("시작점 (%.1f, %.1f) m — %s | 무리 자리 %d × (사슴 %d · 늑대 %d · 멧돼지 %d) | 두뇌 %s"),
		   *UWorld::RemovePIEPrefix(World.GetPackage()->GetName()), World.IsPartitionedWorld() ? TEXT("예") : TEXT("아님"), Clip.Min.X / 100.0, Clip.Max.X / 100.0,
		   Clip.Min.Y / 100.0, Clip.Max.Y / 100.0, *From, O.X / 100.0, O.Y / 100.0, *S.OriginLabel, S.Settings.Herds, S.Settings.PerHerd[0], S.Settings.PerHerd[1],
		   S.Settings.PerHerd[2], *S.Settings.BrainDir);
	if (!S.TeamEcoNote.IsEmpty())
	{
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] %s"), *S.TeamEcoNote);
	}
	BeginStreamingAt(FVector(Clip.GetCenter().X, Clip.GetCenter().Y, O.Z), static_cast<float>(Radius));
	S.Phase = EEcoR9DemoPhase::WaitWhole;
	S.PhaseStart = World.GetTimeSeconds();
}

bool UEcoR9DemoSubsystem::ScanWhole()
{
	using namespace EcoR9DemoSubsystemImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	if (S.WholeSpec)
	{
		return true;   // 앞에 훑은 땅 지도 (Play 중 다시 켬)
	}
	const double T0 = FPlatformTime::Seconds();
	if (!S.bTeamEco)
	{
		DescribeTeamEco(*World);   // 불러온 뒤 다시 센다 (플레이어 몸을 옮기지 않을지 정함)
	}
	// 1. 훑을 사각 전체를 4 m 칸으로 (지형 높이·물·가파름·나무·바위·건물)
	FR9ScanGrid G;
	G.CellCm = kWholeCellCm;
	G.X0 = FMath::FloorToDouble(S.AreaBox.Min.X / kWholeCellCm) * kWholeCellCm;
	G.Y0 = FMath::FloorToDouble(S.AreaBox.Min.Y / kWholeCellCm) * kWholeCellCm;
	G.Nx = FMath::Clamp(FMath::CeilToInt32((S.AreaBox.Max.X - G.X0) / kWholeCellCm), 1, FMath::RoundToInt32(kWholeMaxSideCm / kWholeCellCm));
	G.Ny = FMath::Clamp(FMath::CeilToInt32((S.AreaBox.Max.Y - G.Y0) / kWholeCellCm), 1, FMath::RoundToInt32(kWholeMaxSideCm / kWholeCellCm));
	const int32 N = G.Nx * G.Ny;
	G.Height.assign(static_cast<std::size_t>(N), std::numeric_limits<float>::quiet_NaN());
	G.Blocked.assign(static_cast<std::size_t>(N), 0);
	TArray<uint8> Kinds;
	TArray<FR9CoverPoint> Cover;
	FEcoR9ScanCounts Counts;
	ScanCells(G, &Kinds, &Cover, Counts);
	const double T1 = FPlatformTime::Seconds();
	// 2. 열린 땅 경계 → 세계 정사각 (둘레 50 m, 4 m 배수, 4 km 상한 — 훑기 칸과 모서리를 맞춤)
	int32 Ix0 = MAX_int32, Iy0 = MAX_int32, Ix1 = -1, Iy1 = -1;
	double ZSum = 0.0;
	int64 OpenN = 0;
	for (int32 y = 0; y < G.Ny; ++y)
	{
		for (int32 x = 0; x < G.Nx; ++x)
		{
			const std::size_t K = G.Index(x, y);
			if (G.IsOpen(K, false))
			{
				Ix0 = FMath::Min(Ix0, x);
				Iy0 = FMath::Min(Iy0, y);
				Ix1 = FMath::Max(Ix1, x);
				Iy1 = FMath::Max(Iy1, y);
				ZSum += G.Height[K];
				++OpenN;
			}
		}
	}
	if (OpenN == 0)
	{
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 맵 전체 땅: 열린 땅 칸이 하나도 없다 (땅: 지형 %d · 바닥 메시 %d · 없음 %d) — 예전 한 무대로 돈다"), Counts.FromLand,
			   Counts.FromMesh, Counts.NoGround);
		return false;
	}
	const double MinSide = S.Settings.AreaM > 120 ? 100.0 * S.Settings.AreaM : 12000.0;
	double Cx = 0.0, Cy = 0.0;
	const int32 Gf = SquareFromBounds(G.X0 + Ix0 * G.CellCm, G.Y0 + Iy0 * G.CellCm, G.X0 + (Ix1 + 1) * G.CellCm, G.Y0 + (Iy1 + 1) * G.CellCm, kWholeMarginCm,
									  kWholeCellCm, FMath::Min(MinSide, kWholeMaxSideCm), kWholeMaxSideCm, Cx, Cy);
	const double HalfSide = 0.5 * Gf * kWholeCellCm;
	const int32 Ox = FMath::RoundToInt32((Cx - HalfSide - G.X0) / kWholeCellCm);   // 정사각 모서리 = 훑기 칸 (Ox, Oy) — 훑기 밖이면 음수
	const int32 Oy = FMath::RoundToInt32((Cy - HalfSide - G.Y0) / kWholeCellCm);
	Cx = G.X0 + Ox * kWholeCellCm + HalfSide;
	Cy = G.Y0 + Oy * kWholeCellCm + HalfSide;
	FR9ScanGrid F;
	F.Nx = F.Ny = Gf;
	F.CellCm = kWholeCellCm;
	F.X0 = Cx - HalfSide;
	F.Y0 = Cy - HalfSide;
	F.Height.assign(static_cast<std::size_t>(Gf) * static_cast<std::size_t>(Gf), std::numeric_limits<float>::quiet_NaN());
	F.Blocked.assign(F.Height.size(), 1);
	std::vector<std::uint8_t> KindF(F.Height.size(), kLandVoid);
	for (int32 fy = 0; fy < Gf; ++fy)
	{
		const int32 sy = fy + Oy;
		if (sy < 0 || sy >= G.Ny)
		{
			continue;
		}
		for (int32 fx = 0; fx < Gf; ++fx)
		{
			const int32 sx = fx + Ox;
			if (sx < 0 || sx >= G.Nx)
			{
				continue;   // 훑기 밖 = 땅 없음
			}
			const std::size_t Ks = G.Index(sx, sy);
			const std::size_t Kf = F.Index(fx, fy);
			F.Height[Kf] = G.Height[Ks];
			F.Blocked[Kf] = G.Blocked[Ks];
			KindF[Kf] = Kinds[static_cast<int32>(Ks)];
		}
	}
	// 3. 코어 땅 지도 (y 뒤집음 — 화면 FR9StageMap 과 같은 차례, EcoR9DemoWhole.h)
	auto Spec = std::make_shared<FR9WholeSpec>();
	Spec->G = Gf;
	Spec->CellUnits = 2.0;
	FR9LandCounts Lc;
	if (!ScanToLand(F, KindF, Spec->Kind, &Lc))
	{
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 맵 전체 땅: 땅 지도를 못 만듦 (G %d) — 예전 한 무대로 돈다"), Gf);
		return false;
	}
	int64 Comps = 0;
	const int64 Main = LargestOpenComponent(Spec->Kind, Gf, &Comps);
	FR9StageMap M;
	M.Cx = Cx;
	M.Cy = Cy;
	M.W = M.H = Gf * Spec->CellUnits;
	M.UnitCm = 200.0;
	// 4. 은신처 곁 후보: 나무 덩어리 (16 m 묶음에 나무 3 그루 이상) · 큰 바위 (가로 2 m 넘음, 무게 = 크기) — 코어가 그 곁에 은신처를 먼저 둔다
	std::vector<FR9CoverPoint> Pts;
	Pts.reserve(static_cast<std::size_t>(Cover.Num()));
	for (const FR9CoverPoint& P : Cover)
	{
		double Ux = 0.0, Uy = 0.0;
		M.ToUnits(P.X, P.Y, Ux, Uy);
		if (Ux >= 0.0 && Uy >= 0.0 && Ux < M.W && Uy < M.H)
		{
			Pts.push_back(FR9CoverPoint{Ux, Uy, P.Weight});
		}
	}
	ClusterAnchors(Pts, 8.0, 3.0, 4000, Spec->Anchor);
	// 5. 사람이 놓은 무리 자리 (TargetPoint 꼬리표 EcoR9Herd, 없으면 예전 섬 무대 EcoV3IslandHerd — 이름 차례)
	TArray<ATargetPoint*> Points;
	for (TActorIterator<ATargetPoint> It(World); It; ++It)
	{
		if (It->Tags.Contains(kHerdTagR9))
		{
			Points.Add(*It);
		}
	}
	FString SiteFrom = TEXT("코어가 고름 (가장 큰 이어진 땅 안, 서로 가장 먼 점)");
	if (Points.IsEmpty())
	{
		for (TActorIterator<ATargetPoint> It(World); It; ++It)
		{
			if (It->Tags.Contains(kHerdTagV3))
			{
				Points.Add(*It);
			}
		}
	}
	Points.Sort([](const ATargetPoint& A, const ATargetPoint& B) { return A.GetFName().LexicalLess(B.GetFName()); });
	for (const ATargetPoint* Pt : Points)
	{
		double Ux = 0.0, Uy = 0.0;
		M.ToUnits(Pt->GetActorLocation().X, Pt->GetActorLocation().Y, Ux, Uy);
		if (Ux >= 0.0 && Uy >= 0.0 && Ux < M.W && Uy < M.H && static_cast<int32>(Spec->Sites.size() / 2) < S.Settings.Herds)
		{
			Spec->Sites.push_back(Ux);
			Spec->Sites.push_back(Uy);
		}
	}
	if (!Spec->Sites.empty())
	{
		SiteFrom = FString::Printf(TEXT("사람이 놓은 TargetPoint %d 곳 (꼬리표 %s)"), static_cast<int32>(Spec->Sites.size() / 2), *Points[0]->Tags[0].ToString());
	}
	// 6. 첫 무리 자리는 플레이어 시작점 가까이 (보자마자 동물이 보이게)
	double Px = -1.0, Py = -1.0;
	M.ToUnits(S.SearchOrigin.X, S.SearchOrigin.Y, Px, Py);
	if (Px >= 0.0 && Py >= 0.0 && Px < M.W && Py < M.H)
	{
		Spec->PrefX = Px;
		Spec->PrefY = Py;
	}
	Spec->Herds = S.Settings.Herds;
	for (int32 k = 0; k < EcoR9Demo::kNumSpecies; ++k)
	{
		Spec->PerHerd[k] = S.Settings.PerHerd[k];   // 뒤 셋(물소·표범·여우)은 동물 장면에서만 쓰인다 — 세 종 장면은 코어가 보지 않음
	}
	Spec->MaxAnimals = 400;
	S.WholeSpec = Spec;
	S.WholeCenter = FVector(Cx, Cy, ZSum / static_cast<double>(OpenN));
	S.LandBox = FBox(FVector(G.X0 + Ix0 * G.CellCm, G.Y0 + Iy0 * G.CellCm, S.WholeCenter.Z), FVector(G.X0 + (Ix1 + 1) * G.CellCm, G.Y0 + (Iy1 + 1) * G.CellCm, S.WholeCenter.Z));
	const double CellKm2 = (kWholeCellCm / 100000.0) * (kWholeCellCm / 100000.0);
	S.WholeLine = FString::Printf(
		TEXT("땅 지도 %d×%d (4 m, %.2f km 정사각, 가운데 (%.0f, %.0f) m) | 열림 %lld (%.2f km²) · 물·땅 없음 %lld · 가파름 %lld · 나무·바위·건물 %lld | 가장 큰 이어진 땅 %lld 칸 (덩어리 %lld) | ")
			TEXT("땅 경계 x %.0f ~ %.0f m, y %.0f ~ %.0f m | 훑기 %d×%d 칸: 지형 %d · 바닥 메시 %d · 없음 %d · 바다 %d · 호수·강 %d · 가파름 %d · 걸리는 것 %lld (나무 %lld · 큰 바위 %lld) | ")
			TEXT("은신처 곁 후보 %d | 무리 자리: %s | %.2f 초 (훑기 %.2f)"),
		Gf, Gf, Gf * kWholeCellCm / 100000.0, Cx / 100.0, Cy / 100.0, static_cast<long long>(Lc.Open), Lc.Open * CellKm2, static_cast<long long>(Lc.Void),
		static_cast<long long>(Lc.Steep), static_cast<long long>(Lc.Obstacle), static_cast<long long>(Main), static_cast<long long>(Comps), S.LandBox.Min.X / 100.0,
		S.LandBox.Max.X / 100.0, S.LandBox.Min.Y / 100.0, S.LandBox.Max.Y / 100.0, G.Nx, G.Ny, Counts.FromLand, Counts.FromMesh, Counts.NoGround, Counts.Sea, Counts.Water,
		Counts.Steep, static_cast<long long>(Counts.Objects), static_cast<long long>(Counts.Trees), static_cast<long long>(Counts.Rocks),
		static_cast<int32>(Spec->Anchor.size() / 2), *SiteFrom, FPlatformTime::Seconds() - T0, T1 - T0);
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 맵 전체 땅 — %s"), *S.WholeLine);
	return true;
}

double UEcoR9DemoSubsystem::GroundZ(double XCm, double YCm) const
{
	using namespace EcoR9DemoSubsystemImpl;
	const FEcoR9DemoState& S = *State;
	const EcoR9Demo::FR9HeightTable& H = S.Heights;
	if (H.Valid() && XCm >= H.X0 && YCm >= H.Y0 && XCm <= H.X0 + (H.Nx - 1) * H.Step && YCm <= H.Y0 + (H.Ny - 1) * H.Step)
	{
		return H.At(XCm, YCm);
	}
	if (UWorld* World = GetWorld())
	{
		const FGroundProbe Ground(*World, S.ProbeIgnore);
		float Z = 0.0f;
		if (Ground.At(XCm, YCm, Z))
		{
			return Z;
		}
	}
	return S.StageCenter.Z;
}

void UEcoR9DemoSubsystem::BuildStage()
{
	using namespace EcoR9DemoSubsystemImpl;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	const double T0 = FPlatformTime::Seconds();
	if (!S.bTeamEco)
	{
		DescribeTeamEco(*World);   // 무대 자리를 불러온 뒤 다시 센다 (플레이어 몸을 옮길지 정함 — ParkPawn)
		if (S.bTeamEco)
		{
			UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] %s"), *S.TeamEcoNote);
		}
	}
	S.Map.Cx = S.StageCenter.X;
	S.Map.Cy = S.StageCenter.Y;
	S.Map.W = S.Info.W;
	S.Map.H = S.Info.H;
	S.Map.UnitCm = S.Info.UnitCm;
	// 높이 표: 무대 + 40 m 띠, 1 m 간격 (보이는 높이만 — 행동은 평평한 세계 그대로). 맵 전체 땅은 지형이면 2 m, 바닥 메시면 4 m 간격
	// (섬 2.8 km 정사각 ≈ 1440² = 207 만 표본 — 지형 높이장 읽기라 물리 쿼리가 아니다)
	RefreshProbeIgnore();
	const FGroundProbe Ground(*World, S.ProbeIgnore);   // 지형, 없으면 바닥 메시 (지형 없는 맵도)
	EcoR9Demo::FR9HeightTable& H = S.Heights;
	H = EcoR9Demo::FR9HeightTable();
	H.Step = !S.Info.bWhole ? kHeightStepCm : (Ground.Lands.IsEmpty() ? 400.0 : 200.0);
	H.X0 = S.Map.Cx - 0.5 * S.Map.SideXCm() - kHeightMarginCm;
	H.Y0 = S.Map.Cy - 0.5 * S.Map.SideYCm() - kHeightMarginCm;
	H.Nx = FMath::CeilToInt32((S.Map.SideXCm() + 2.0 * kHeightMarginCm) / H.Step) + 1;
	H.Ny = FMath::CeilToInt32((S.Map.SideYCm() + 2.0 * kHeightMarginCm) / H.Step) + 1;
	H.Z.assign(static_cast<std::size_t>(H.Nx) * static_cast<std::size_t>(H.Ny), std::numeric_limits<float>::quiet_NaN());
	int32 NoGround = 0;
	for (int32 y = 0; y < H.Ny; ++y)
	{
		for (int32 x = 0; x < H.Nx; ++x)
		{
			float Z = 0.0f;
			if (Ground.At(H.X0 + x * H.Step, H.Y0 + y * H.Step, Z))
			{
				H.Z[static_cast<std::size_t>(y) * static_cast<std::size_t>(H.Nx) + static_cast<std::size_t>(x)] = Z;
			}
			else
			{
				++NoGround;
			}
		}
	}
	double Mean = 0.0, Lo = 0.0, Hi = 0.0;
	const bool bAny = H.Stats(Mean, Lo, Hi);
	H.Fallback = bAny ? Mean : S.StageCenter.Z;
	S.HeightHi = bAny ? Hi : H.Fallback;   // 카메라 섬 전체 보기 초점 높이 (가장 높은 땅 + 30 m)
	S.bHeightHi = bAny;
	S.StageCenter.Z = S.Info.bWhole ? S.WholeCenter.Z : H.At(S.StageCenter.X, S.StageCenter.Y);
	if (S.Info.bWhole && !S.Info.HerdXY.empty())
	{
		// 카메라 7 · G: 첫 무리 자리 (플레이어 시작점에 가장 가까운 자리 — 코어가 그 차례로 고름)
		S.SiteIndex = 0;
		S.bSiteLocked = false;
	}
	if (!bAny)
	{
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 무대 둘레 땅 높이(지형·바닥 메시)를 하나도 못 읽음 — 평평한 z=%.0f 로 그린다 (땅 없는 맵이거나 스트리밍 덜 됨)"),
			   H.Fallback);
	}
	else if (NoGround > 0)
	{
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 무대 둘레 높이 표본 %d/%d 에 땅이 없음 — 그 자리는 평균 높이 %.1f m 로 그린다 (바닥 끝 너머)"), NoGround, H.Nx * H.Ny,
			   H.Fallback / 100.0);
	}
	LoadVisualAssets();
	SpawnStaticDecor();
	UpdateFood();
	SyncBodies(0.0, 0.0f);
	EnsureCamera();
	ParkPawn();
	ApplyViewEnvironment();
	S.Phase = EEcoR9DemoPhase::Running;
	S.RunningSince = World->GetTimeSeconds();
	S.NextLog = S.RunningSince + 10.0;
	S.CamModeSince = S.RunningSince;
	// 처음 카메라 (옛 관찰 카메라 꼴 — EcoR9DemoCam.h): 콘솔 eco.R9Demo.Cam (키 숫자, 기본 5 자동 추적), 명령줄 -EcoR9Cam=<이름> 이 먼저.
	// 이름: free·wolf·deer·top·quarter·auto·boar · buffalo·leopard·fox (옛 이름 wide = 섬 전체 사선 보기, site = 첫 무리 자리 사선 보기)
	{
		const int32 Cv = EcoR9DemoCVars::Cam();
		EEcoR9DemoCam Start = EEcoR9DemoCam::Auto;
		EcoR9DemoCam::ModeFromInt(Cv, Start);
		FString CamParam;
		if (FParse::Value(FCommandLine::Get(), TEXT("EcoR9Cam="), CamParam))
		{
			static const TCHAR* const Names[] = {TEXT("free"), TEXT("wolf"), TEXT("deer"), TEXT("top"), TEXT("quarter"), TEXT("auto"), TEXT("boar")};
			for (int32 i = 0; i < 7; ++i)
			{
				if (CamParam.Equals(Names[i], ESearchCase::IgnoreCase))
				{
					Start = static_cast<EEcoR9DemoCam>(i);
				}
			}
			// 동물 세계 (11-13 05:00) — 모드 값 8 · 9 · 10
			Start = CamParam.Equals(TEXT("buffalo"), ESearchCase::IgnoreCase) ? EEcoR9DemoCam::Buffalo : Start;
			Start = CamParam.Equals(TEXT("leopard"), ESearchCase::IgnoreCase) ? EEcoR9DemoCam::Leopard : Start;
			Start = CamParam.Equals(TEXT("fox"), ESearchCase::IgnoreCase) ? EEcoR9DemoCam::Fox : Start;
			if (CamParam.Equals(TEXT("wide"), ESearchCase::IgnoreCase) || CamParam.Equals(TEXT("site"), ESearchCase::IgnoreCase))
			{
				Start = EEcoR9DemoCam::Quarter;   // 대상 없는 사선 보기
				if (S.Info.bWhole && !S.Info.HerdXY.empty())
				{
					S.SiteIndex = CamParam.Equals(TEXT("wide"), ESearchCase::IgnoreCase) ? static_cast<int32>(S.Info.HerdXY.size() / 2) : 0;
					S.bSiteLocked = true;
				}
			}
		}
		S.CamMode = Start == EEcoR9DemoCam::Free ? EEcoR9DemoCam::Auto : Start;   // 자유 카메라는 지금 카메라 자리에서 시작하므로 한 번 자리를 잡은 뒤
		S.FollowA = S.FollowB = 0;
		S.bCamInit = false;
		S.bCamSnap = true;
		SetCamMode(S.CamMode, TEXT("시작"));
		if (Start == EEcoR9DemoCam::Free)
		{
			UpdateCamera(0.0f);
			EnterFreeCam(TEXT("시작"));
		}
		S.LastCamCVar = EcoR9DemoCVars::Cam();
	}
	// 확인용 카메라 키 차례 (-EcoR9CamKeys=<초>:<키>,… — 무대가 선 때부터 센 초). 잘못된 항목은 기록 한 줄 남기고 건너뛴다
	S.CamKeyPlan.Reset();
	S.CamKeyNext = 0;
	S.CamKeyProbeLeft = 0;
	if (!S.Settings.CamKeys.IsEmpty())
	{
		TArray<FString> Items;
		S.Settings.CamKeys.ParseIntoArray(Items, TEXT(","), true);
		for (const FString& Item : Items)
		{
			FString Sec, KeyName;
			const FKey Key = Item.Split(TEXT(":"), &Sec, &KeyName) ? FKey(FName(*KeyName.TrimStartAndEnd())) : FKey();
			EcoR9DemoCam::EAction Ignored = EcoR9DemoCam::EAction::Help;
			if (Sec.IsNumeric() && Key.IsValid() && EcoR9DemoCam::ActionOf(Key, Ignored))
			{
				S.CamKeyPlan.Add(TPair<double, FKey>(FCString::Atod(*Sec), Key));
			}
			else
			{
				UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] -EcoR9CamKeys 항목 '%s' 를 못 읽음 (꼴: <초>:<키 이름>, 예 20:One) — 건너뜀"), *Item);
			}
		}
		S.CamKeyPlan.StableSort([](const TPair<double, FKey>& A, const TPair<double, FKey>& B) { return A.Key < B.Key; });
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 확인용 카메라 키 차례 %d 개 (-EcoR9CamKeys)"), S.CamKeyPlan.Num());
	}
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 무대 — %s | 높이 %d×%d 표본 (%.0f ~ %.0f m) | 몸 %d · 풀 덩어리 %d · 은신처 %d | %.2f 초"), *S.StageLine, H.Nx,
		   H.Ny, bAny ? Lo / 100.0 : H.Fallback / 100.0, bAny ? Hi / 100.0 : H.Fallback / 100.0, S.Bodies.Num(), S.TuftBase.Num(),
		   static_cast<int32>(S.Info.Shelters.size()), FPlatformTime::Seconds() - T0);
}

// -----------------------------------------------------------------------------
// 틱
// -----------------------------------------------------------------------------

void UEcoR9DemoSubsystem::Tick(float DeltaTime)
{
	using namespace EcoR9DemoSubsystemImpl;
	Super::Tick(DeltaTime);
	if (!State)
	{
		return;
	}
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	if (!World || S.Phase == EEcoR9DemoPhase::Off)
	{
		return;   // 꺼짐 — 아무것도 하지 않는다 (Play 중 eco.R9Demo 1 이면 StartDemo)
	}
	if (S.QuitCountdown >= 0)
	{
		if (S.QuitCountdown-- == 0)
		{
			RequestQuit(TEXT("녹화·끝내기 깃발"));
		}
		return;
	}
	const double Now = World->GetTimeSeconds();
	const UWorldPartitionStreamingSourceComponent* Src = S.Streamer.Get();
	const bool bStreamed = !Src || Src->IsStreamingCompleted();
	if (S.Phase == EEcoR9DemoPhase::WaitScan || S.Phase == EEcoR9DemoPhase::WaitStage || S.Phase == EEcoR9DemoPhase::WaitWhole)
	{
		FreezePawn();   // 폰이 OnWorldBeginPlay 뒤에 생기는 게임 모드도 있어 기다리는 동안 다시 본다
	}
	// 예전 v3·Fauna 동물 몸·먼 표식 숨기기 (보이는 것만, 틱마다 — 팀 코드가 카메라 둘레 몸을 새로 묶으면(BindIdentity) 다시 보이므로 계속 본다.
	// 표현 액터 수십 개 · 액터 수백 개 훑기라 가볍다)
	if (IsActive())
	{
		HideOtherVisuals(S.Settings.bHideOthers && EcoR9DemoCVars::HideOthers());
	}
	switch (S.Phase)
	{
	case EEcoR9DemoPhase::WaitWhole:
		if (Now - S.PhaseStart >= 0.5 && (bStreamed || Now - S.PhaseStart > kWholeStreamTimeout))
		{
			if (!bStreamed)
			{
				UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 맵 전체 땅 스트리밍이 %.0f 초 안에 안 끝남 — 불린 만큼 훑는다"), kWholeStreamTimeout);
			}
			bool bOk = ScanWhole();
			FString Err;
			if (bOk)
			{
				S.StageCenter = S.WholeCenter;
				bOk = OpenSource(Err);
				if (!bOk)
				{
					UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 맵 전체 땅 코어 시작 실패: %s — 예전 한 무대로 돈다"), *Err);
					S.WholeSpec.reset();
				}
			}
			if (bOk)
			{
				S.StageLine = FString::Printf(TEXT("맵 전체 땅 — 정사각 가운데 (%.0f, %.0f) m · 한 변 %.0f m · 무리 자리 %d · %s"), S.WholeCenter.X / 100.0, S.WholeCenter.Y / 100.0,
											  S.Info.W * S.Info.UnitCm / 100.0, static_cast<int32>(S.Info.HerdXY.size() / 2), *Utf8(S.Info.Brains));
				BuildStage();
			}
			else
			{
				// 예전 한 무대 (장면 파일 그대로 · 시작점 둘레 평지 고르기)
				S.bWhole = false;
				FString Err2;
				if (!OpenSource(Err2))
				{
					Fail(Err2);
					break;
				}
				S.ScanRing = 0;
				BeginStreamingAt(S.SearchOrigin, RingStreamRadius(0));
				S.Phase = EEcoR9DemoPhase::WaitScan;
			}
		}
		break;
	case EEcoR9DemoPhase::WaitScan:
		if (Now - S.PhaseStart >= 0.5 && (bStreamed || Now - S.PhaseStart > kStreamTimeout))
		{
			if (!bStreamed)
			{
				UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 시작점 둘레 %.0f m 스트리밍이 %.0f 초 안에 안 끝남 — 불린 만큼 훑는다"), kRingHalfCm[S.ScanRing] / 100.0,
					   kStreamTimeout);
			}
			if (ScanAndPick(S.ScanRing))
			{
				BeginStreamingAt(S.StageCenter, kStageStreamRadius);
				S.Phase = EEcoR9DemoPhase::WaitStage;
			}
			else
			{
				// 이 둘레에 없음 → 넓혀서 다시 불러온다 (World Partition 이 아니면 기다리지 않음)
				S.ScanRing = FMath::Min(S.ScanRing + 1, kNumRings - 1);
				BeginStreamingAt(S.SearchOrigin, RingStreamRadius(S.ScanRing));
			}
		}
		break;
	case EEcoR9DemoPhase::WaitStage:
		if (Now - S.PhaseStart >= 0.5 && (bStreamed || Now - S.PhaseStart > kStreamTimeout))
		{
			if (!bStreamed)
			{
				UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 무대 스트리밍이 %.0f 초 안에 안 끝남 — 불린 만큼으로 세운다"), kStreamTimeout);
			}
			if (S.Settings.bHasAt)
			{
				// 콘솔·명령줄 자리: 가운데 높이를 지금 읽는다 (지형, 없으면 바닥 메시)
				RefreshProbeIgnore();
				const FGroundProbe Ground(*World, S.ProbeIgnore);
				float Z = 0.0f;
				if (Ground.At(S.StageCenter.X, S.StageCenter.Y, Z))
				{
					S.StageCenter.Z = Z;
				}
				else
				{
					// 콘솔 값은 에디터를 끄기 전까지 남는다 — 다른 맵에서 쓰던 자리일 수 있다. 덮어쓰기는 그대로 지키되 알린다
					S.StageLine += TEXT(" · 이 자리에 땅이 없음");
					UE_LOG(LogEcoR9Demo, Warning,
						   TEXT("[EcoR9Demo] eco.R9Demo.At 자리 (%.1f, %.1f) m 에 땅(지형·바닥 메시)이 없음 — 다른 맵에서 쓰던 값일 수 있다. ")
							   TEXT("이 맵에서 스스로 고르게 하려면 Play 전에 eco.R9Demo.At 을 비운다 (eco.R9Demo.At \"\")"),
						   S.StageCenter.X / 100.0, S.StageCenter.Y / 100.0);
				}
			}
			BuildStage();
		}
		break;
	case EEcoR9DemoPhase::Running:
		TickRunning(DeltaTime);
		break;
	default:
		break;
	}
}

void UEcoR9DemoSubsystem::TickRunning(float DeltaTime)
{
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	const double Now = World->GetTimeSeconds();
	ApplyViewEnvironment();
	ParkPawn();
	HandleKeys();
	TickCamKeyPlan(Now);   // 확인용 (-EcoR9CamKeys) — 없으면 아무 일 없음
	if (EcoR9DemoCVars::Daylight())
	{
		HoldDaylight();
	}
	else
	{
		ReleaseDaylight();
	}
	// 확인용 (읽기만): 실제 프레임 간격 — 기록 줄 '프레임'
	const double RealNow = FPlatformTime::Seconds();
	if (S.FrameLastReal > 0.0)
	{
		const double FrameMs = 1000.0 * (RealNow - S.FrameLastReal);
		S.FrameMsSum += FrameMs;
		S.FrameMsMax = FMath::Max(S.FrameMsMax, FrameMs);
		++S.FrameCount;
	}
	S.FrameLastReal = RealNow;
	const double Step = S.Info.StepSeconds > 0.0 ? S.Info.StepSeconds : 2.0 / 15.0;
	const double Dt = FMath::IsFinite(DeltaTime) ? FMath::Clamp(static_cast<double>(DeltaTime), 0.0, 0.25) : 0.0;
	S.Accum += Dt * FMath::Max(0.0f, EcoR9DemoCVars::Speed());
	int32 Advanced = 0;
	while (S.Accum >= Step && Advanced < 4)
	{
		S.Accum -= Step;
		++Advanced;
		if (!AdvanceFrame() || S.Phase != EEcoR9DemoPhase::Running)
		{
			return;
		}
	}
	if (S.Accum >= Step)
	{
		S.Accum = FMath::Fmod(S.Accum, Step);   // 너무 느린 프레임 — 따라잡지 않고 건너뛴다
	}
	S.Alpha = FMath::Clamp(S.Accum / Step, 0.0, 1.0);
	S.SimSeconds = (static_cast<double>(S.StepsShown) + S.Alpha) * Step;
	SyncBodies(S.Alpha, static_cast<float>(Dt));
	UpdateMarkers(Now);
	UpdateCamera(static_cast<float>(Dt));
	LogCamKeyProbe();      // 확인용 (-EcoR9CamKeys) — 읽기만
	if (S.Info.bWhole)
	{
		UpdateFood();   // 큰 세계: 카메라가 움직이면 풀 창을 옮긴다 (바뀐 칸만 다시 씀)
	}
	{
		const double TickMs = 1000.0 * (FPlatformTime::Seconds() - RealNow);   // 확인용: 데모 틱 일 (스텝·몸·표식·카메라·풀)
		S.TickMsSum += TickMs;
		S.TickMsMax = FMath::Max(S.TickMsMax, TickMs);
	}
	TickCapture(static_cast<float>(Dt));
	if (Now >= S.NextLog)
	{
		S.NextLog = Now + 10.0;
		LogSummary(TEXT("10 초"));
	}
	if (S.Settings.ExitAfterSeconds > 0.0f && Now - S.RunningSince >= S.Settings.ExitAfterSeconds && S.QuitCountdown < 0)
	{
		LogSummary(TEXT("끝 (-EcoR9DemoExitAfter)"));
		S.QuitCountdown = 5;
	}
}

void UEcoR9DemoSubsystem::LogSummary(const TCHAR* Tag)
{
	FEcoR9DemoState& S = *State;
	int32 Alive[EcoR9Demo::kNumSpecies] = {};
	EcoR9Demo::CountAlive(S.Cur, Alive);
	// 동물 장면에서는 옛 셈이 더 넓은 뜻이다 (검토 11-13 06:10): 잡힌 사슴·멧돼지 = 늑대·표범·여우가 잡음, 상처 = 모든 종의 물려 다침,
	// 죽은 늑대 = 반격·표범·여우의 물기·물소 들이받기. 셈 값은 그대로 두고 이름만 바꾼다 (세 종 판은 글이 예전과 바이트 같음)
	const bool bFaunaNames = S.Info.NumSpecies > EcoR9Demo::kNumOldSpecies;
	UE_LOG(LogEcoR9Demo, Log,
		   TEXT("[EcoR9Demo] %s | %s 판 %d · 시간 %.1f 초 (스텝 %lld) | 산: 사슴 %d · 늑대 %d · 멧돼지 %d | %s: 사슴 %d · 멧돼지 %d · %s %d | 반격 %d · ")
			   TEXT("%s %d | 굶어 죽음 %d · 다시 남 %d | 몸 액터 %d | 카메라 %s"),
		   Tag, S.Settings.Mode == FEcoR9DemoSettings::EMode::Live ? TEXT("실시간") : TEXT("재생"), S.RunIndex, S.SimSeconds,
		   static_cast<long long>(S.StepsShown), Alive[0], Alive[1], Alive[2], bFaunaNames ? TEXT("물려 죽음(모든 포식자)") : TEXT("늑대가 잡음"), S.DeerKilled,
		   S.BoarKilled, bFaunaNames ? TEXT("물려 다침(모든 종)") : TEXT("멧돼지 상처"), S.BoarWounded, S.Counters,
		   bFaunaNames ? TEXT("반격·물기·들이받기에 죽은 늑대") : TEXT("반격에 죽은 늑대"), S.WolvesKilled, S.Starved, S.Respawns, S.Bodies.Num(), *S.CamLabel);
	// 먹기 (실제로 먹은 개체·스텝 — 풀/땅속/고기). 늑대 고기 = 사체 먹기
	const auto& E = S.Eats;
	const int32 Unknown = E[0][0] + E[1][0] + E[2][0];
	const FString UnknownText = Unknown > 0 ? FString::Printf(TEXT(" · 먹이 모름(재생) 사슴 %d · 늑대 %d · 멧돼지 %d"), E[0][0], E[1][0], E[2][0]) : FString();
	UE_LOG(LogEcoR9Demo, Log,
		   TEXT("[EcoR9Demo] %s | 먹기(개체·스텝, 풀/땅속/고기): 사슴 %d/%d/%d · 늑대 %d/%d/%d (사체 먹기 %d) · 멧돼지 %d/%d/%d%s | 사체 지금 %d"), Tag,
		   E[0][1], E[0][2], E[0][3], E[1][1], E[1][2], E[1][3], E[1][3], E[2][1], E[2][2], E[2][3], *UnknownText,
		   static_cast<int32>(S.Cur.Carcasses.size()));
	if (S.Info.NumSpecies > EcoR9Demo::kNumOldSpecies)
	{
		// 동물 세계 (물소·표범·여우): 산 · 물려/받혀/굶어 죽음 · 들이받기 · 먹기 (풀/땅속/고기)
		const auto& B = S.BittenSp;
		const auto& K = S.StruckSp;
		const auto& V = S.StarvedSp;
		UE_LOG(LogEcoR9Demo, Log,
			   TEXT("[EcoR9Demo] %s | 동물 세계: 산 물소 %d · 표범 %d · 여우 %d | 물려 죽음 사슴 %d · 늑대 %d · 멧돼지 %d · 물소 %d · 표범 %d · 여우 %d | ")
				   TEXT("받혀·받아침에 죽음 사슴 %d · 늑대 %d · 멧돼지 %d · 물소 %d · 표범 %d · 여우 %d | 굶어 죽음 물소 %d · 표범 %d · 여우 %d | 물소 들이받기 %d (죽임 %d) | ")
				   TEXT("먹기 물소 %d/%d/%d · 표범 %d/%d/%d · 여우 %d/%d/%d"),
			   Tag, Alive[3], Alive[4], Alive[5], B[0], B[1], B[2], B[3], B[4], B[5], K[0], K[1], K[2], K[3], K[4], K[5], V[3], V[4], V[5], S.Gores, S.GoreKills,
			   E[3][1], E[3][2], E[3][3], E[4][1], E[4][2], E[4][3], E[5][1], E[5][2], E[5][3]);
	}
	if (S.Settings.Mode == FEcoR9DemoSettings::EMode::Live)
	{
		// 결정 계산 비용 (코어 한 스텝 평균 — 결정 스텝은 관측·두뇌 포함). 실시간 필요량 초당 7.5 스텝
		const FString Cost = S.Live ? EcoR9DemoSubsystemImpl::Utf8(S.Live->CostLine()) : FString();
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] %s | 비용: 코어 스텝 평균 %.2f ms (%d 스텝)%s%s | 몸 액터 %d · 먼 표식 %d%s"), Tag,
			   S.AdvanceCount > 0 ? S.AdvanceMsSum / S.AdvanceCount : 0.0, S.AdvanceCount, Cost.IsEmpty() ? TEXT("") : TEXT(" · 마지막 결정 "), *Cost, S.NumBodyActors,
			   S.NumFar, S.Info.bWhole ? *FString::Printf(TEXT(" · 무리 자리 %d"), static_cast<int32>(S.Info.HerdXY.size() / 2)) : TEXT(""));
		if (S.Info.bWhole && S.Live)
		{
			// 확인용 (11-13 빌드·확인): 막힌 칸 위 산 개체(코어 double 좌표, 누적)·숨긴 예전 동물 (읽기만)
			std::int64_t OnBlocked = 0;
			std::int64_t AgentSteps = 0;
			S.Live->OnBlockedStats(OnBlocked, AgentSteps);
			int32 CompsHidden = 0;
			for (const TWeakObjectPtr<USceneComponent>& C : S.HiddenComps)
			{
				CompsHidden += C.IsValid() && !C->IsVisible() ? 1 : 0;
			}
			const int32 NF = S.FrameCount;
			UE_LOG(LogEcoR9Demo, Log,
				   TEXT("[EcoR9Demo] %s | 확인: 막힌 칸 위 산 개체 %lld (센 개체-스텝 %lld) · 숨긴 예전 동물 몸 %d · 숨긴 먼 표식 묶음 %d | 프레임 평균 %.2f ms (최대 %.1f ms, %d 프레임) · ")
					   TEXT("데모 틱 일 평균 %.2f ms (최대 %.1f ms)"),
				   Tag, static_cast<long long>(OnBlocked), static_cast<long long>(AgentSteps), NumHiddenOthers(), CompsHidden, NF > 0 ? S.FrameMsSum / NF : 0.0,
				   S.FrameMsMax, NF, NF > 0 ? S.TickMsSum / NF : 0.0, S.TickMsMax);
		}
		S.FrameMsSum = 0.0;
		S.FrameMsMax = 0.0;
		S.TickMsSum = 0.0;
		S.TickMsMax = 0.0;
		S.FrameCount = 0;
		S.AdvanceMsSum = 0.0;
		S.AdvanceCount = 0;
	}
}

// -----------------------------------------------------------------------------
// 보기 환경 (HUD 숨김·관찰 카메라 끔·폰 세움) — 이 실행에서만, 저장하지 않는다
// -----------------------------------------------------------------------------

void UEcoR9DemoSubsystem::ApplyViewEnvironment()
{
	FEcoR9DemoState& S = *State;
	if (S.bEnvApplied)
	{
		return;
	}
	HoldObserverCamera();
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (AHUD* Hud = PC ? PC->GetHUD() : nullptr)
	{
		S.bHudHidden = Hud->bShowHUD;
		Hud->bShowHUD = false;   // 팀 개체 살피기 HUD 는 R9 개체를 모른다 — 데모 글자만 둔다
		S.bEnvApplied = true;
	}
}

void UEcoR9DemoSubsystem::HoldObserverCamera()
{
	FEcoR9DemoState& S = *State;
	if (S.PrevCamEnable != MIN_int32)
	{
		return;   // 이미 끔 (또는 없음)
	}
	// 관찰 카메라(EcoV3ObserverCamera)는 키 0~5·H 를 쓰고 보기 대상을 잡는다 — 데모 동안만 끈다 (TeardownDemo 에서 되돌림)
	if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Cam.Enable")))
	{
		S.PrevCamEnable = V->GetInt();
		V->Set(0, ECVF_SetByCode);
	}
	else
	{
		S.PrevCamEnable = MIN_int32 + 1;   // 없음 — 되돌릴 것 없음 표시
	}
}

void UEcoR9DemoSubsystem::FreezePawn()
{
	FEcoR9DemoState& S = *State;
	if (S.bPawnFrozen)
	{
		return;
	}
	const UWorld* World = GetWorld();
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn)
	{
		return;
	}
	// 이 실행에서만: 이동을 끄고(떨어지지 않음) 충돌을 끄고(트리거에 겹치지 않음) 숨긴다. 저장하지 않는다 — 끌 때(StopDemo) 앞 상태로 되돌린다
	if (S.FrozenPawn.Get() != Pawn)
	{
		S.FrozenPawn = Pawn;
		S.bPawnWasHidden = Pawn->IsHidden();
		S.bPawnHadCollision = Pawn->GetActorEnableCollision();
		S.bPawnMoveWasActive = Pawn->GetMovementComponent() ? Pawn->GetMovementComponent()->IsActive() : false;
		S.PawnStart = Pawn->GetActorLocation();
	}
	if (UPawnMovementComponent* Move = Pawn->GetMovementComponent())
	{
		Move->StopMovementImmediately();
		Move->Deactivate();
	}
	Pawn->SetActorHiddenInGame(true);
	Pawn->SetActorEnableCollision(false);
	S.bPawnFrozen = true;
}

void UEcoR9DemoSubsystem::HoldDaylight()
{
	using namespace EcoR9DemoSubsystemImpl;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	if (!S.bSkySearched)
	{
		S.bSkySearched = true;
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			if (IsKindOfName(*It, TEXT("BP_SkyManager_C")))
			{
				S.Sky = *It;
				break;
			}
		}
		if (!S.Sky.IsValid())
		{
			// 섬 하늘 관리자가 없는 맵 (다른 팀 맵·시험 맵): 조용히 건너뛴다 — 그 맵의 하늘·낮밤은 그대로
			UE_LOG(LogEcoR9Demo, Verbose, TEXT("[EcoR9Demo] 섬 하늘 관리자(BP_SkyManager)가 없는 맵 — 하늘·낮밤은 그 맵 그대로"));
		}
	}
	AActor* Sky = S.Sky.Get();
	if (!Sky)
	{
		return;
	}
	UClass* Cls = Sky->GetClass();
	// 1. 해 속도 0 (실행 중 값만 — 저장하지 않음, ReleaseDaylight 에서 되돌림)
	if (!S.bSkyHeld)
	{
		if (FDoubleProperty* D = FindFProperty<FDoubleProperty>(Cls, TEXT("SunSpeed")))
		{
			S.PrevSunSpeed = D->GetPropertyValue_InContainer(Sky);
			D->SetPropertyValue_InContainer(Sky, 0.0);
			S.SunSpeedKind = 1;
		}
		else if (FFloatProperty* F = FindFProperty<FFloatProperty>(Cls, TEXT("SunSpeed")))
		{
			S.PrevSunSpeed = F->GetPropertyValue_InContainer(Sky);
			F->SetPropertyValue_InContainer(Sky, 0.0f);
			S.SunSpeedKind = 2;
		}
		S.bSkyHeld = true;
	}
	// 2. 해를 낮 높이에 (해 액터 회전 + 관리자가 쥔 현재 회전 값)
	// 팀 섬 맵의 관리자 칸: Sun (해 DirectionalLight 액터) · Moon · SunSpeed · DynamicSun(켜기 깃발) — 외부 액터 ZFZPZF1LV0UWHQQXC0TPPC
	USceneComponent* Sun = nullptr;
	for (const TCHAR* Name : {TEXT("Sun"), TEXT("DynamicSun")})
	{
		const FObjectPropertyBase* O = FindFProperty<FObjectPropertyBase>(Cls, Name);
		UObject* Obj = O ? O->GetObjectPropertyValue_InContainer(Sky) : nullptr;
		if (AActor* SunActor = Cast<AActor>(Obj))
		{
			Sun = SunActor->GetRootComponent();
		}
		else if (USceneComponent* SunComp = Cast<USceneComponent>(Obj))
		{
			Sun = SunComp;
		}
		if (Sun)
		{
			break;
		}
	}
	if (!Sun)
	{
		if (!S.bSkyLogged)
		{
			S.bSkyLogged = true;
			UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 팀 하늘: 해(Sun)를 못 찾음 — 해 속도만 %s"), S.SunSpeedKind ? TEXT("0 으로 둠") : TEXT("(SunSpeed 도 못 찾음)"));
		}
		return;
	}
	const FRotator Cur = Sun->GetComponentRotation();
	const FRotator Want(kDayPitch, Cur.Yaw, 0.0);
	if (FMath::Abs(FRotator::NormalizeAxis(Cur.Pitch - kDayPitch)) > 0.5 || FMath::Abs(FRotator::NormalizeAxis(Cur.Roll)) > 0.5)
	{
		Sun->SetWorldRotation(Want);
	}
	if (FStructProperty* R = FindFProperty<FStructProperty>(Cls, TEXT("SunCurrentRotation")); R && R->Struct == TBaseStructure<FRotator>::Get())
	{
		*R->ContainerPtrToValuePtr<FRotator>(Sky) = Want;
	}
	if (!S.bSunLogged)
	{
		S.bSunLogged = true;
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 팀 하늘: 데모 동안만 해 속도 %.3f → 0, 해 높이 %.0f° 에 고정 (%s · 저장 안 함, eco.R9Demo.Daylight 0 이면 그대로)"),
			   S.SunSpeedKind ? S.PrevSunSpeed : -1.0, -kDayPitch, *Sun->GetOwner()->GetName());
	}
}

void UEcoR9DemoSubsystem::ReleaseDaylight()
{
	if (!State || !State->bSkyHeld)
	{
		return;
	}
	FEcoR9DemoState& S = *State;
	if (AActor* Sky = S.Sky.Get())
	{
		UClass* Cls = Sky->GetClass();
		if (S.SunSpeedKind == 1)
		{
			if (FDoubleProperty* D = FindFProperty<FDoubleProperty>(Cls, TEXT("SunSpeed")))
			{
				D->SetPropertyValue_InContainer(Sky, S.PrevSunSpeed);
			}
		}
		else if (S.SunSpeedKind == 2)
		{
			if (FFloatProperty* F = FindFProperty<FFloatProperty>(Cls, TEXT("SunSpeed")))
			{
				F->SetPropertyValue_InContainer(Sky, static_cast<float>(S.PrevSunSpeed));
			}
		}
	}
	S.bSkyHeld = false;
	S.bSkyLogged = false;
	S.bSunLogged = false;
}

void UEcoR9DemoSubsystem::RequestQuit(const TCHAR* Why)
{
	if (GIsEditor)
	{
		// 에디터 PIE 에서는 에디터를 닫지 않는다 (녹화·끝내기 깃발은 창 없는 -game 실행용)
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 끝내기 요청(%s) — 에디터 안이라 끝내지 않는다"), Why);
		return;
	}
	FPlatformMisc::RequestExit(false, TEXT("EcoR9Demo"));
}

void UEcoR9DemoSubsystem::ParkPawn()
{
	FEcoR9DemoState& S = *State;
	if (S.bPawnParked)
	{
		return;
	}
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	APawn* Pawn = PC ? PC->GetPawn() : nullptr;
	if (!Pawn)
	{
		return;
	}
	// 원점 땅 밑에서 떨어지지 않게: 이동을 끄고 숨긴 채 무대 가장자리 땅 위에 둔다 (카메라가 보기 대상)
	S.bPawnFrozen = false;
	FreezePawn();
	if (S.bWhole)
	{
		// 맵 전체 땅: 무대 가장자리가 바다일 수 있어 옮기지 않는다 — 시작 자리에 숨기고 멈춰 둔다
		S.bPawnParked = true;
		return;
	}
	if (S.bTeamEco)
	{
		// 팀 생태가 있는 맵: 몸을 옮기지 않는다. 팀 v3 는 플레이어 몸 자리를 위협으로 읽어서(EcoPolicyV3IntegratedProcessors.cpp TActorIterator<APawn>),
		// 우리 무대 곁으로 옮기면 팀 동물이 데모 쪽에 반응할 수 있다. 시작 자리에 숨기고 멈춰 둔다 (게임이 처음 둔 그대로)
		S.bPawnParked = true;
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 팀 생태가 있는 맵 — 플레이어 몸은 시작 자리 (%.1f, %.1f) m 에 숨기고 멈춰 둔다 (옮기지 않음)"),
			   Pawn->GetActorLocation().X / 100.0, Pawn->GetActorLocation().Y / 100.0);
		return;
	}
	const double X = S.StageCenter.X - 0.5 * S.Map.SideXCm() - 1000.0;
	const double Y = S.StageCenter.Y;
	Pawn->SetActorLocation(FVector(X, Y, GroundZ(X, Y) + 200.0), false, nullptr, ETeleportType::TeleportPhysics);
	S.bPawnParked = true;
}

void UEcoR9DemoSubsystem::RestorePawn()
{
	// Play 중 끄기: 숨긴·멈춘 플레이어 몸과 보기 대상·팀 HUD 를 앞 상태로 (옮겼으면 처음 자리로)
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	APlayerController* PC = World ? World->GetFirstPlayerController() : nullptr;
	if (APawn* Pawn = S.FrozenPawn.Get())
	{
		if (S.bPawnParked && !S.bTeamEco && !S.bWhole)
		{
			Pawn->SetActorLocation(S.PawnStart, false, nullptr, ETeleportType::TeleportPhysics);
		}
		Pawn->SetActorHiddenInGame(S.bPawnWasHidden);
		Pawn->SetActorEnableCollision(S.bPawnHadCollision);
		if (UPawnMovementComponent* Move = Pawn->GetMovementComponent(); Move && S.bPawnMoveWasActive)
		{
			Move->Activate(true);
		}
		if (PC && PC->GetPawn() == Pawn)
		{
			PC->SetViewTarget(Pawn);
		}
	}
	else if (PC && PC->GetPawn())
	{
		PC->SetViewTarget(PC->GetPawn());
	}
	if (S.bHudHidden)
	{
		if (AHUD* Hud = PC ? PC->GetHUD() : nullptr)
		{
			Hud->bShowHUD = true;
		}
	}
	S.FrozenPawn.Reset();
	S.bPawnFrozen = false;
	S.bPawnParked = false;
	S.bHudHidden = false;
}

void UEcoR9DemoSubsystem::HideOtherVisuals(bool bHide)
{
	// 예전 v3·Fauna 동물 몸(우리 것이 아닌 표현 액터)·섬 무대 먼 표식을 보이는 것만 숨긴다. 그쪽 시뮬레이션·코드·에셋은 건드리지 않는다
	// (숨김은 실행 중 값 — 저장 안 함). bHide 거짓이면 숨긴 것을 되돌린다 (표현 액터는 아직 묶여 있을 때만 — 풀에 돌아간 것은 팀 코드가 숨긴 그대로)
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	if (!bHide)
	{
		for (const TWeakObjectPtr<AActor>& W : S.HiddenOthers)
		{
			if (AActor* A = W.Get())
			{
				const AEcoCreatureRepresentationActor* Rep = Cast<AEcoCreatureRepresentationActor>(A);
				if (!Rep || Rep->bBound)
				{
					A->SetActorHiddenInGame(false);
				}
			}
		}
		for (const TWeakObjectPtr<USceneComponent>& W : S.HiddenComps)
		{
			if (USceneComponent* C = W.Get())
			{
				C->SetVisibility(true);
			}
		}
		S.HiddenOthers.Reset();
		S.HiddenComps.Reset();
		return;
	}
	if (!World)
	{
		return;
	}
	for (TActorIterator<AEcoCreatureRepresentationActor> It(World); It; ++It)
	{
		AEcoCreatureRepresentationActor* Rep = *It;
		if (!Rep || Rep->IsHidden() || Rep->VisualState.StableAgentId >= 9000000000000LL || Rep->GetFName().ToString().StartsWith(TEXT("EcoR9Demo_")))
		{
			continue;   // 이미 숨음 · 우리 몸 (신원 9,000,000,000,000 + R9 uid — EcoR9DemoVisuals.cpp kStableIdBase)
		}
		Rep->SetActorHiddenInGame(true);
		S.HiddenOthers.AddUnique(Rep);
	}
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		if (It->GetClass() != AActor::StaticClass() || !It->GetName().StartsWith(TEXT("EcoV3_IslandMarkers")))
		{
			continue;   // 예전 섬 무대 먼 표식 (EcoV3IslandStage.cpp IslandTickMarkers — 액터 숨김을 4 Hz 로 되돌리므로 컴포넌트를 숨긴다)
		}
		TInlineComponentArray<UInstancedStaticMeshComponent*> Isms(*It);
		for (UInstancedStaticMeshComponent* Ism : Isms)
		{
			if (Ism && Ism->IsVisible())
			{
				Ism->SetVisibility(false);
				S.HiddenComps.AddUnique(Ism);
			}
		}
	}
}

// -----------------------------------------------------------------------------
// 녹화
// -----------------------------------------------------------------------------

void UEcoR9DemoSubsystem::TickCapture(float DeltaTime)
{
	FEcoR9DemoState& S = *State;
	const FEcoR9DemoSettings& Cfg = S.Settings;
	if (Cfg.CaptureDir.IsEmpty() || S.bCaptureDone)
	{
		return;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	if (S.CaptureClock < 0.0)
	{
		if (Now - S.RunningSince < 2.0)
		{
			return;   // 몸·애니·카메라가 자리 잡을 때까지
		}
		// 첫 프레임이 기본(회색) 재질이 되지 않게: 이 실행에서 새로 컴파일하는 셰이더(풀 ISM·기본 도형 MID 따위)가 끝날 때까지 기다린다.
		// 상한 60 월드 초 — run_player.sh 의 -seconds=<초+300> 안에 녹화가 끝나게 (스트리밍 자리 찾기 고리 3 + 무대 = 4×45 + 2 + 60 < 300)
		const int32 ShaderJobs = GShaderCompilingManager ? GShaderCompilingManager->GetNumRemainingJobs() : 0;
		if (ShaderJobs > 0 && Now - S.RunningSince < 62.0)
		{
			if (!S.bShaderWaitLogged)
			{
				UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 녹화 전 셰이더 컴파일을 기다림 — 남은 일 %d (상한 60 초)"), ShaderJobs);
				S.bShaderWaitLogged = true;
			}
			return;
		}
		// 첫 프레임 텍스처가 흐리지 않게 한 번 모두 불러온다 (최대 5 초 막음, 녹화 시작 때 한 번만)
		IStreamingManager::Get().StreamAllResources(5.0f);
		S.CaptureClock = 0.0;
		IFileManager::Get().MakeDirectory(*Cfg.CaptureDir, true);
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 녹화 시작 → %s (%.0f fps, %.1f 초) · 남은 셰이더 일 %d"), *Cfg.CaptureDir, Cfg.CaptureFps,
			   Cfg.CaptureSeconds, ShaderJobs);
	}
	else
	{
		S.CaptureClock += DeltaTime;
	}
	const int32 Due = FMath::FloorToInt32(S.CaptureClock * Cfg.CaptureFps) + 1;
	if (S.CaptureFrames < Due)
	{
		const FString Path = FPaths::Combine(Cfg.CaptureDir, FString::Printf(TEXT("f_%05d.png"), S.CaptureFrames));
		FScreenshotRequest::RequestScreenshot(Path, /*bInShowUI*/ Cfg.bCaptureUI, /*bAddFilenameSuffix*/ false);   // -EcoR9CaptureUI 면 오른쪽 위 글도
		++S.CaptureFrames;
	}
	if (S.CaptureClock >= Cfg.CaptureSeconds)
	{
		S.bCaptureDone = true;
		const FString Manifest = FString::Printf(
			TEXT("{\n  \"mode\": \"%s\",\n  \"frames\": %d,\n  \"fps\": %.3f,\n  \"seconds\": %.3f,\n  \"sim_seconds_end\": %.3f,\n  \"steps_shown\": %lld,\n")
				TEXT("  \"stage_center_cm\": [%.1f, %.1f, %.1f],\n  \"seed\": %llu,\n  \"policy\": \"%s\",\n  \"deer_killed\": %d,\n  \"boar_killed\": %d,\n")
				TEXT("  \"counters\": %d,\n  \"starved\": %d,\n  \"num_species\": %d,\n  \"note\": \"%s\"\n}\n"),
			Cfg.Mode == FEcoR9DemoSettings::EMode::Live ? TEXT("live") : TEXT("replay"), S.CaptureFrames, Cfg.CaptureFps, S.CaptureClock, S.SimSeconds,
			static_cast<long long>(S.StepsShown), S.StageCenter.X, S.StageCenter.Y, S.StageCenter.Z, static_cast<unsigned long long>(S.Info.Seed),
			*EcoR9DemoSubsystemImpl::Utf8(S.Info.Policy), S.DeerKilled, S.BoarKilled, S.Counters, S.Starved, S.Info.NumSpecies,   // 6 = 동물 장면 (deer/boar_killed 는 모든 포식자)
			Cfg.Mode == FEcoR9DemoSettings::EMode::Live ? TEXT("실시간: 파이썬에서 배운 두뇌를 언리얼 C++ 로 추론") : TEXT("파이썬 실행 기록 재생 (언리얼 실시간 추론 아님)"));
		FFileHelper::SaveStringToFile(Manifest, *FPaths::Combine(Cfg.CaptureDir, TEXT("capture.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
		LogSummary(TEXT("녹화 끝"));
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 녹화 끝 — 프레임 %d → %s"), S.CaptureFrames, *Cfg.CaptureDir);
		S.QuitCountdown = 30;   // PNG 쓰기 기다림
	}
}

// -----------------------------------------------------------------------------
// 화면 글 — 오른쪽 위 묶음 하나 (2026-11-13 03:30 사용자 '좌상단에 띄우지 말고 옛날처럼 우상단에'). 옛 관찰 카메라 DrawPanel 꼴 그대로:
// 어두운 반투명 바탕 · 흰 글자 · 엔진 작은 글꼴 · 맨 윗줄 'H 단축키 숨기기' · 단축키 목록 · 가는 줄 · 상태. 자리·배율은 옛 EcoV3Observe::LayoutPanel.
// 팀 HUD 는 데모 동안 숨겨 두므로(ApplyViewEnvironment) 팀 판 자리를 비킬 것이 없다.
// -----------------------------------------------------------------------------

void UEcoR9DemoSubsystem::DrawOverlay(UCanvas* Canvas, APlayerController* PC)
{
	using namespace EcoR9DemoSubsystemImpl;
	if (!State || !Canvas || !PC || PC->GetWorld() != GetWorld() || !EcoR9DemoCVars::Text() || !GEngine)
	{
		return;
	}
	const FEcoR9DemoState& S = *State;
	if (S.Phase == EEcoR9DemoPhase::Off || (S.Phase == EEcoR9DemoPhase::Refused && GetWorld()->GetNetMode() == NM_Client))
	{
		return;   // 꺼짐·맵 거르기 · 클라이언트 화면에는 아무것도 그리지 않는다 (거부 글도)
	}
	const bool bLive = S.Settings.Mode == FEcoR9DemoSettings::EMode::Live;
	struct FLine
	{
		FString Text;
		FLinearColor Color;
		bool bGapBefore = false;   // 이 줄 앞에 가는 줄 (단축키와 상태 사이)
	};
	TArray<FLine> Lines;
	const FLinearColor Title = FLinearColor(FColor(255, 215, 110));
	const FLinearColor KeyColor = FLinearColor(FColor(240, 240, 240));
	const FLinearColor White = FLinearColor(FColor(235, 235, 235));
	const FLinearColor Gray = FLinearColor(FColor(175, 175, 175));
	const double Wait = GetWorld() ? GetWorld()->GetTimeSeconds() - S.PhaseStart : 0.0;
	if (S.Phase == EEcoR9DemoPhase::Refused || S.Phase == EEcoR9DemoPhase::Failed)
	{
		Lines.Add({S.Phase == EEcoR9DemoPhase::Failed ? FString(TEXT("R9 데모 실패")) : FString(TEXT("R9 데모 꺼짐")), Title});
		Lines.Add({S.Why, White});
	}
	else if (S.Phase == EEcoR9DemoPhase::WaitWhole)
	{
		Lines.Add({TEXT("R9 데모 — 맵 땅을 불러오는 중"), Title});
		Lines.Add({FString::Printf(TEXT("%.0f × %.0f m · %.0f 초"), S.AreaBox.GetSize().X / 100.0, S.AreaBox.GetSize().Y / 100.0, Wait), White});
		Lines.Add({TEXT("다 불리면 땅을 훑고 사슴·늑대·멧돼지를 푼다"), Gray});
	}
	else if (S.Phase == EEcoR9DemoPhase::WaitScan)
	{
		Lines.Add({TEXT("R9 데모 — 무대 자리를 찾는 중"), Title});
		Lines.Add({FString::Printf(TEXT("시작점 둘레 %.0f m (%d/%d) · %.0f 초"), kRingHalfCm[S.ScanRing] / 100.0, S.ScanRing + 1, kNumRings, Wait), White});
	}
	else if (S.Phase != EEcoR9DemoPhase::Running)
	{
		Lines.Add({TEXT("R9 데모 — 무대 자리를 불러오는 중"), Title});
		Lines.Add({FString::Printf(TEXT("%.0f 초"), Wait), White});
	}
	else
	{
		const int32 SiteCount = S.Info.bWhole ? static_cast<int32>(S.Info.HerdXY.size() / 2) : 0;
		Lines.Add({S.bShowKeys ? FString(TEXT("R9 관찰 카메라      H  단축키 숨기기")) : FString(TEXT("R9 관찰 카메라      H  단축키 보이기")), Title});
		if (S.bShowKeys)
		{
			for (const FString& L : EcoR9DemoCam::KeyHelpLines(SiteCount > 0, S.Info.NumSpecies > EcoR9Demo::kNumOldSpecies))
			{
				Lines.Add({L, KeyColor});
			}
		}
		// 요약 (실시간·마릿수·잡힘·반격·굶음 — 11-13 왼쪽 위 글을 줄임)
		int32 Alive[EcoR9Demo::kNumSpecies] = {};
		EcoR9Demo::CountAlive(S.Cur, Alive);
		Lines.Add({FString::Printf(TEXT("%s   %s · 판 %d"), bLive ? TEXT("실시간 (언리얼 C++ 추론)") : TEXT("재생 (파이썬 기록 — 실시간 추론 아님)"), *Clock(S.SimSeconds), S.RunIndex + 1),
				   White, true});
		Lines.Add({FString::Printf(TEXT("산   사슴 %d · 늑대 %d · 멧돼지 %d%s"), Alive[0], Alive[1], Alive[2],
								   SiteCount > 0 ? *FString::Printf(TEXT(" · 무리 자리 %d"), SiteCount) : TEXT("")),
				   White});
		if (S.Info.NumSpecies > EcoR9Demo::kNumOldSpecies)
		{
			// 동물 세계 (11-13 05:00): 새 종 마릿수 · 종별 잡힘 · 물소 들이받기 (세 종 판은 아래 옛 줄 그대로)
			const auto& B = S.BittenSp;
			const auto& K = S.StruckSp;
			int32 StarvedAll = 0;
			for (const int32 V : S.StarvedSp)
			{
				StarvedAll += V;
			}
			Lines.Add({FString::Printf(TEXT("      물소 %d · 표범 %d · 여우 %d"), Alive[3], Alive[4], Alive[5]), White});
			Lines.Add({FString::Printf(TEXT("잡힘   사슴 %d · 늑대 %d · 멧돼지 %d · 물소 %d · 표범 %d · 여우 %d"), B[0], B[1], B[2], B[3], B[4], B[5]), White});
			Lines.Add({FString::Printf(TEXT("받기   물소 들이받기 %d (죽임 %d) · 반격 %d · 받혀 죽음 %d · 굶음 %d"), S.Gores, S.GoreKills, S.Counters,
									   K[0] + K[1] + K[2] + K[3] + K[4] + K[5], StarvedAll),
					   White});
		}
		else
		{
			Lines.Add({FString::Printf(TEXT("잡힘   사슴 %d · 멧돼지 %d · 반격 %d · 굶음 %d"), S.DeerKilled, S.BoarKilled, S.Counters, S.Starved), White});
		}
		// 카메라 (모드·대상·행동·가까운 상대·자동 추적 — EcoR9DemoCamera.cpp BuildCamLines)
		for (int32 i = 0; i < S.CamLines.Num(); ++i)
		{
			Lines.Add({S.CamLines[i], FLinearColor(S.CamColors.IsValidIndex(i) ? S.CamColors[i] : FColor::White), i == 0});
		}
		if (S.bShowKeys)
		{
			Lines.Add({TEXT("끄기   콘솔 eco.R9Demo 0"), Gray});
		}
	}
	// 화면 메시지와 같은 글꼴 (한글 됨 — 옛 관찰 카메라와 같음)
	UFont* Font = GEngine->GetSmallFont();
	if (!Font)
	{
		return;
	}
	float LineH = 0.0f;
	float MaxW = 0.0f;
	for (const FLine& L : Lines)
	{
		float XL = 0.0f, YL = 0.0f;
		Canvas->TextSize(Font, L.Text, XL, YL, 1.0f, 1.0f);
		MaxW = FMath::Max(MaxW, XL);
		LineH = FMath::Max(LineH, YL);
	}
	if (LineH <= 0.0f)
	{
		return;
	}
	constexpr float Pad = 9.0f;
	constexpr float Spacing = 1.2f;
	const float GapH = 0.5f * LineH;
	float ContentH = 2.0f * Pad;
	for (const FLine& L : Lines)
	{
		ContentH += LineH * Spacing + (L.bGapBefore ? GapH : 0.0f);
	}
	const FVector2D Size(Canvas->ClipX, Canvas->ClipY);
	const FVector2D Content(MaxW + 2.0f * Pad, ContentH);
	// 1280×720 에서 1.15 배, 1080p 에서 1.7 배 — eco.Cam.HudScale 로 더 키우고 줄인다 (옛 그대로)
	const float Base = FMath::Clamp(static_cast<float>(Size.Y) / 720.0f * 1.15f, 1.0f, 2.4f) * FMath::Clamp(EcoR9DemoCVars::HudScale(), 0.5f, 3.0f);
	const EcoV3Observe::FPanelLayout L = EcoV3Observe::LayoutPanel(Size, Content, Base, nullptr);
	FCanvasTileItem Back(FVector2D(L.X, L.Y), FVector2D(Content.X * L.Scale, Content.Y * L.Scale), FLinearColor(0.012f, 0.016f, 0.024f, 0.74f));
	Back.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Back);
	float Y = L.Y + Pad * L.Scale;
	for (const FLine& Line : Lines)
	{
		if (Line.bGapBefore)
		{
			// 단축키와 상태 사이 가는 줄
			Y += 0.5f * GapH * L.Scale;
			FCanvasTileItem Rule(FVector2D(L.X + Pad * L.Scale, Y), FVector2D((Content.X - 2.0f * Pad) * L.Scale, 1.0f), FLinearColor(1.0f, 1.0f, 1.0f, 0.25f));
			Rule.BlendMode = SE_BLEND_Translucent;
			Canvas->DrawItem(Rule);
			Y += 0.5f * GapH * L.Scale;
		}
		FCanvasTextItem Text(FVector2D(L.X + Pad * L.Scale, Y), FText::FromString(Line.Text), Font, Line.Color);
		Text.Scale = FVector2D(L.Scale, L.Scale);
		Text.EnableShadow(FLinearColor(0.0f, 0.0f, 0.0f, 0.9f));
		Canvas->DrawItem(Text);
		Y += LineH * Spacing * L.Scale;
	}
}

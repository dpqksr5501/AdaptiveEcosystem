// R9 데모 플레이어 — 켜기·무대 자리·프레임 원천·녹화·글자 (설명은 EcoR9DemoSubsystem.h).

#include "EcoR9DemoSubsystem.h"

#include "EcoR9DemoState.h"

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
#include "Misc/Parse.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/UnrealType.h"
#include "UnrealClient.h"
#include "UnrealEngine.h"
#include "WorldPartition/WorldPartitionStreamingSource.h"

#include <limits>

DEFINE_LOG_CATEGORY(LogEcoR9Demo);

namespace EcoR9DemoSubsystemImpl
{
	static TAutoConsoleVariable<int32> CVarDemo(TEXT("eco.R9Demo"), 0,
		TEXT("R9 데모 플레이어 (EcoR9DemoSubsystem.h): 0 끔(기본) · 1 실시간 (eco.R9Demo.Brains 두뇌 폴더) · 2 재생 (eco.R9Demo.Replay 파일). ")
		TEXT("Play 전에 바꾼다. 명령줄 -EcoR9Demo=<폴더>·-EcoR9Replay=<파일> 이 있으면 그것이 먼저다. 맵 제한 없음 — 지형·바닥이 있는 아무 맵에서 ")
		TEXT("무대 자리를 스스로 고른다 (팀 생태 장치가 있어도 건드리지 않고 따로 돈다)."));
	static TAutoConsoleVariable<FString> CVarBrains(TEXT("eco.R9Demo.Brains"), TEXT(""), TEXT("R9 데모 실시간 판 두뇌 폴더 ({deer,wolf,boar}.r9brain). 비면 <프로젝트>/Saved/R9Demo/brains."));
	static TAutoConsoleVariable<FString> CVarScene(TEXT("eco.R9Demo.Scene"), TEXT(""), TEXT("R9 데모 실시간 판 장면 파일 (비면 <두뇌 폴더>/scene.txt)."));
	static TAutoConsoleVariable<FString> CVarReplay(TEXT("eco.R9Demo.Replay"), TEXT(""), TEXT("R9 데모 재생 판 파일 (.r9rp — 파이썬 실행 기록). 비면 <프로젝트>/Saved/R9Demo/replay/demo.r9rp."));
	static TAutoConsoleVariable<FString> CVarAt(TEXT("eco.R9Demo.At"), TEXT(""),
		TEXT("R9 데모 무대 가운데 'x,y' (월드 m, 예: 783,-168). 비면 플레이어 시작점 둘레에서 트인 평지를 스스로 고른다. PIE 는 Play 전에 (명령줄 -EcoR9DemoAt= 와 같음)."));
	static TAutoConsoleVariable<FString> CVarPolicy(TEXT("eco.R9Demo.Policy"), TEXT("sample"),
		TEXT("R9 데모 실시간 판 행동 고르기: sample = 확률대로 (학습 때와 같음) · argmax = 가장 높은 칸."));
	static TAutoConsoleVariable<float> CVarSpeed(TEXT("eco.R9Demo.Speed"), 1.0f, TEXT("R9 데모 시간 배율 (0 = 멈춤). 보기만 바뀐다 — 스텝 규칙은 그대로."));
	static TAutoConsoleVariable<int32> CVarText(TEXT("eco.R9Demo.Text"), 1, TEXT("R9 데모 작은 글자 (마릿수·시간·판). H 키로도 끈다."));
	static TAutoConsoleVariable<int32> CVarCam(TEXT("eco.R9Demo.Cam"), 0,
		TEXT("R9 데모 카메라: 0 자동 (사냥·물기·반격·사체 먹기 따라가기, 없으면 전체) · 1 전체 · 2 사슴 · 3 늑대 · 4 멧돼지 · 5 위에서. 키 1~6 과 같다."));
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
	if (FParse::Value(Cmd, TEXT("EcoR9Replay="), V, false) && !V.IsEmpty())
	{
		S.Mode = EMode::Replay;
		S.ReplayPath = V;
	}
	else if (FParse::Value(Cmd, TEXT("EcoR9Demo="), V, false))
	{
		S.Mode = EMode::Live;
		S.BrainDir = V;
	}
	else if (FParse::Param(Cmd, TEXT("EcoR9Demo")))
	{
		S.Mode = EMode::Live;
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
	return S;
}

FString FEcoR9DemoSettings::DefaultDir()
{
	return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("R9Demo")));
}

// -----------------------------------------------------------------------------
// 서브시스템 수명
// -----------------------------------------------------------------------------

bool UEcoR9DemoSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	// 깃발이 없으면 만들지 않는다 — 보통 게임·에디터·자동화 시험에는 이 서브시스템이 없다. 데디케이티드·클라이언트 전용 실행에도 만들지 않는다
	// (같은 프로세스의 PIE 클라이언트 월드는 OnWorldBeginPlay 의 넷 모드 검사가 거부한다)
	if (IsRunningDedicatedServer() || IsRunningClientOnly() || FEcoR9DemoSettings::Resolve(FCommandLine::Get()).Mode == FEcoR9DemoSettings::EMode::Off)
	{
		return false;
	}
	// 맵 제한이 없어졌으니, 자동화 시험 중에는 R9 데모 시험이 eco.R9Demo.AllowInTests 1 로 켠 때만 만든다 (다른 팀 시험 월드에 끼지 않게)
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
		if (State->PrevCamEnable != MIN_int32)
		{
			if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.Cam.Enable")))
			{
				V->Set(State->PrevCamEnable, ECVF_SetByCode);
			}
		}
		if (!State->PrevRes.IsEmpty() && GEngine)
		{
			GEngine->Exec(GetWorld(), *State->PrevRes);   // 녹화 해상도를 앞 값으로 (설정 파일에 쓰지 않음)
		}
		if (State->PrevOnScreenMsgs >= 0 && GEngine)
		{
			GEngine->bEnableOnScreenDebugMessages = State->PrevOnScreenMsgs != 0;
		}
		ReleaseDaylight();
		const UWorld* World = GetWorld();
		if (World && !World->bIsTearingDown)
		{
			ClearBodies();
			for (AActor* A : SpawnedActors)
			{
				if (IsValid(A))
				{
					A->Destroy();
				}
			}
		}
		State->Live.reset();
	}
	SpawnedActors.Reset();
	Manager = nullptr;
	Camera = nullptr;
	State.Reset();
	Super::Deinitialize();
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
	return State && (State->Phase == EEcoR9DemoPhase::WaitScan || State->Phase == EEcoR9DemoPhase::WaitStage || State->Phase == EEcoR9DemoPhase::Running);
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
	using namespace EcoR9DemoSubsystemImpl;
	Super::OnWorldBeginPlay(InWorld);
	if (!State)
	{
		return;
	}
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
	// 맵 제한 없음 (맵 이름을 보지 않는다). 팀 생태 장치·통합 v3 는 세어 알리기만 한다
	DescribeTeamEco(InWorld);
	FString Err;
	if (!OpenSource(Err))
	{
		Fail(Err);
		return;
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
		// 파일은 언리얼이 읽어 바이트로 넘긴다 (한글 경로도 되게). 실행 중 파이썬 없음 — 두뇌 파일은 미리 바꿔 둔 float32 묶음
		TArray<uint8> Bytes;
		if (!FFileHelper::LoadFileToArray(Bytes, *S.Settings.ScenePath))
		{
			OutError = FString::Printf(TEXT("장면 파일을 못 읽음: '%s' (-EcoR9Scene= 또는 <두뇌 폴더>/scene.txt)"), *S.Settings.ScenePath);
			return false;
		}
		C.SceneText.assign(reinterpret_cast<const char*>(Bytes.GetData()), static_cast<std::size_t>(Bytes.Num()));
		static const TCHAR* const BrainFiles[3] = {TEXT("deer.r9brain"), TEXT("wolf.r9brain"), TEXT("boar.r9brain")};
		for (int32 k = 0; k < 3; ++k)
		{
			const FString BrainPath = FPaths::Combine(S.Settings.BrainDir, BrainFiles[k]);
			Bytes.Reset();
			if (!FFileHelper::LoadFileToArray(Bytes, *BrainPath))
			{
				OutError = FString::Printf(TEXT("두뇌 파일을 못 읽음: '%s'"), *BrainPath);
				return false;
			}
			C.BrainBytes[k].assign(Bytes.GetData(), Bytes.GetData() + Bytes.Num());
		}
		S.Live = std::make_unique<FR9LiveSource>();
		std::string E;
		FR9Frame First;
		if (!S.Live->Init(C, S.Info, First, E))
		{
			OutError = FString::Printf(TEXT("코어 시작 실패 (장면 %s, 두뇌 %s): %s"), *S.Settings.ScenePath, *S.Settings.BrainDir, *Utf8(E));
			return false;
		}
		S.Cur = MoveTemp(First);
		S.bFoodKnown = S.Info.G > 0 && !S.Cur.Grass.empty();
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
	float CapMax = 0.0f;
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
	S.bHavePrev = true;
	S.Accum = 0.0;
	S.Alpha = 0.0;
	S.StepsShown = 0;
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
		if (!S.Live || !S.Live->Next(S.Cur, E))
		{
			Fail(FString::Printf(TEXT("코어 스텝 실패: %s"), *EcoR9DemoSubsystemImpl::Utf8(E)));
			return false;
		}
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
	S.bAutoFollowing = false;
	S.FollowA = S.FollowB = 0;
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
	// 3. 가파름: 이웃 칸 높이 차 / 칸 > 0.36 (약 20°) [어림]
	const int32 Steep = static_cast<int32>(MarkSteep(G, 0.36));
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
		for (UStaticMeshComponent* C : Comps)
		{
			const UStaticMesh* Mesh = C ? C->GetStaticMesh() : nullptr;
			if (!Mesh || !C->IsRegistered() || !C->IsVisible() || !Overlaps2D(C->Bounds.GetBox()))
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
			if (const UInstancedStaticMeshComponent* Ism = Cast<UInstancedStaticMeshComponent>(C))
			{
				const FBox MeshBox = Mesh->GetBoundingBox();
				const int32 Count = Ism->GetInstanceCount();
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
				const FBox B = C->Bounds.GetBox();
				const FVector Size = B.GetSize();
				if (FMath::Max(Size.X, Size.Y) > 20000.0 || FMath::Max(Size.X, Size.Y) < 80.0 || Size.Z < 40.0)
				{
					continue;
				}
				// 넓은 메시(10 m 넘게)가 그 칸의 땅이면 (지형 대신 언덕진 바닥 메시) 그 칸은 막지 않는다 — 가파름(3)이 언덕 비탈을 따로 막는다
				const bool bWide = FMath::Max(Size.X, Size.Y) >= kGroundPieceCm;
				Objects += MarkObstacleIf(G, ToR9Box(B), kObstaclePadCm, kObstacleClearCm, kObstacleReachCm,
										  [&GroundComp, C, bWide](std::size_t Cell) { return bWide && GroundComp[static_cast<int32>(Cell)] == C; });
			}
		}
	}
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
	// 높이 표: 무대 + 40 m 띠, 1 m 간격 (보이는 높이만 — 행동은 평평한 세계 그대로)
	EcoR9Demo::FR9HeightTable& H = S.Heights;
	H = EcoR9Demo::FR9HeightTable();
	H.Step = kHeightStepCm;
	H.X0 = S.Map.Cx - 0.5 * S.Map.SideXCm() - kHeightMarginCm;
	H.Y0 = S.Map.Cy - 0.5 * S.Map.SideYCm() - kHeightMarginCm;
	H.Nx = FMath::CeilToInt32((S.Map.SideXCm() + 2.0 * kHeightMarginCm) / H.Step) + 1;
	H.Ny = FMath::CeilToInt32((S.Map.SideYCm() + 2.0 * kHeightMarginCm) / H.Step) + 1;
	H.Z.assign(static_cast<std::size_t>(H.Nx) * static_cast<std::size_t>(H.Ny), std::numeric_limits<float>::quiet_NaN());
	RefreshProbeIgnore();
	const FGroundProbe Ground(*World, S.ProbeIgnore);   // 지형, 없으면 바닥 메시 (지형 없는 맵도)
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
	S.StageCenter.Z = H.At(S.StageCenter.X, S.StageCenter.Y);
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
	const int32 Cv = EcoR9DemoCVars::Cam();
	FString CamParam;
	if (FParse::Value(FCommandLine::Get(), TEXT("EcoR9Cam="), CamParam))
	{
		static const TCHAR* const Names[] = {TEXT("auto"), TEXT("wide"), TEXT("deer"), TEXT("wolf"), TEXT("boar"), TEXT("top")};
		for (int32 i = 0; i < 6; ++i)
		{
			if (CamParam.Equals(Names[i], ESearchCase::IgnoreCase))
			{
				S.CamMode = static_cast<EEcoR9DemoCam>(i);
			}
		}
		S.LastCamCVar = Cv;
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
	if (!World)
	{
		return;
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
	if (S.Phase == EEcoR9DemoPhase::WaitScan || S.Phase == EEcoR9DemoPhase::WaitStage)
	{
		FreezePawn();   // 폰이 OnWorldBeginPlay 뒤에 생기는 게임 모드도 있어 기다리는 동안 다시 본다
	}
	switch (S.Phase)
	{
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
	if (EcoR9DemoCVars::Daylight())
	{
		HoldDaylight();
	}
	else
	{
		ReleaseDaylight();
	}
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
	const FEcoR9DemoState& S = *State;
	int32 Alive[EcoR9Demo::kNumSpecies] = {};
	EcoR9Demo::CountAlive(S.Cur, Alive);
	UE_LOG(LogEcoR9Demo, Log,
		   TEXT("[EcoR9Demo] %s | %s 판 %d · 시간 %.1f 초 (스텝 %lld) | 산: 사슴 %d · 늑대 %d · 멧돼지 %d | 늑대가 잡음: 사슴 %d · 멧돼지 %d · 멧돼지 상처 %d | 반격 %d · ")
			   TEXT("반격에 죽은 늑대 %d | 굶어 죽음 %d · 다시 남 %d | 몸 액터 %d | 카메라 %s"),
		   Tag, S.Settings.Mode == FEcoR9DemoSettings::EMode::Live ? TEXT("실시간") : TEXT("재생"), S.RunIndex, S.SimSeconds,
		   static_cast<long long>(S.StepsShown), Alive[0], Alive[1], Alive[2], S.DeerKilled, S.BoarKilled, S.BoarWounded, S.Counters, S.WolvesKilled, S.Starved,
		   S.Respawns, S.Bodies.Num(), *S.CamLabel);
	// 먹기 (실제로 먹은 개체·스텝 — 풀/땅속/고기). 늑대 고기 = 사체 먹기
	const auto& E = S.Eats;
	const int32 Unknown = E[0][0] + E[1][0] + E[2][0];
	const FString UnknownText = Unknown > 0 ? FString::Printf(TEXT(" · 먹이 모름(재생) 사슴 %d · 늑대 %d · 멧돼지 %d"), E[0][0], E[1][0], E[2][0]) : FString();
	UE_LOG(LogEcoR9Demo, Log,
		   TEXT("[EcoR9Demo] %s | 먹기(개체·스텝, 풀/땅속/고기): 사슴 %d/%d/%d · 늑대 %d/%d/%d (사체 먹기 %d) · 멧돼지 %d/%d/%d%s | 사체 지금 %d"), Tag,
		   E[0][1], E[0][2], E[0][3], E[1][1], E[1][2], E[1][3], E[1][3], E[2][1], E[2][2], E[2][3], *UnknownText,
		   static_cast<int32>(S.Cur.Carcasses.size()));
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
	if (S.PrevCamEnable == MIN_int32)
	{
		// 관찰 카메라(EcoV3ObserverCamera)는 키 1~5 를 쓰고 보기 대상을 잡는다 — 데모 동안만 끈다 (Deinitialize 에서 되돌림)
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
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (AHUD* Hud = PC ? PC->GetHUD() : nullptr)
	{
		Hud->bShowHUD = false;   // 팀 개체 살피기 HUD 는 R9 개체를 모른다 — 데모 글자만 둔다
		S.bEnvApplied = true;
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
	// 이 실행에서만: 이동을 끄고(떨어지지 않음) 충돌을 끄고(트리거에 겹치지 않음) 숨긴다. 저장하지 않는다
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
		FScreenshotRequest::RequestScreenshot(Path, /*bInShowUI*/ false, /*bAddFilenameSuffix*/ false);
		++S.CaptureFrames;
	}
	if (S.CaptureClock >= Cfg.CaptureSeconds)
	{
		S.bCaptureDone = true;
		const FString Manifest = FString::Printf(
			TEXT("{\n  \"mode\": \"%s\",\n  \"frames\": %d,\n  \"fps\": %.3f,\n  \"seconds\": %.3f,\n  \"sim_seconds_end\": %.3f,\n  \"steps_shown\": %lld,\n")
				TEXT("  \"stage_center_cm\": [%.1f, %.1f, %.1f],\n  \"seed\": %llu,\n  \"policy\": \"%s\",\n  \"deer_killed\": %d,\n  \"boar_killed\": %d,\n")
				TEXT("  \"counters\": %d,\n  \"starved\": %d,\n  \"note\": \"%s\"\n}\n"),
			Cfg.Mode == FEcoR9DemoSettings::EMode::Live ? TEXT("live") : TEXT("replay"), S.CaptureFrames, Cfg.CaptureFps, S.CaptureClock, S.SimSeconds,
			static_cast<long long>(S.StepsShown), S.StageCenter.X, S.StageCenter.Y, S.StageCenter.Z, static_cast<unsigned long long>(S.Info.Seed),
			*EcoR9DemoSubsystemImpl::Utf8(S.Info.Policy), S.DeerKilled, S.BoarKilled, S.Counters, S.Starved,
			Cfg.Mode == FEcoR9DemoSettings::EMode::Live ? TEXT("실시간: 파이썬에서 배운 두뇌를 언리얼 C++ 로 추론") : TEXT("파이썬 실행 기록 재생 (언리얼 실시간 추론 아님)"));
		FFileHelper::SaveStringToFile(Manifest, *FPaths::Combine(Cfg.CaptureDir, TEXT("capture.json")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
		LogSummary(TEXT("녹화 끝"));
		UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 녹화 끝 — 프레임 %d → %s"), S.CaptureFrames, *Cfg.CaptureDir);
		S.QuitCountdown = 30;   // PNG 쓰기 기다림
	}
}

// -----------------------------------------------------------------------------
// 작은 글자
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
		return;   // 클라이언트 화면에는 아무것도 그리지 않는다 (거부 글도)
	}
	const bool bLive = S.Settings.Mode == FEcoR9DemoSettings::EMode::Live;
	struct FLine
	{
		FString Text;
		FLinearColor Color;
		bool bBig = false;
	};
	TArray<FLine> Lines;
	const FLinearColor White(0.95f, 0.95f, 0.95f);
	const FLinearColor Gray(0.72f, 0.72f, 0.72f);
	const FLinearColor Gold(1.0f, 0.84f, 0.43f);
	if (S.Phase == EEcoR9DemoPhase::Refused || S.Phase == EEcoR9DemoPhase::Failed)
	{
		Lines.Add({FString::Printf(TEXT("R9 데모 %s — %s"), S.Phase == EEcoR9DemoPhase::Failed ? TEXT("실패") : TEXT("꺼짐"), *S.Why), Gold, false});
	}
	else if (S.Phase == EEcoR9DemoPhase::WaitScan)
	{
		const double Wait = GetWorld() ? GetWorld()->GetTimeSeconds() - S.PhaseStart : 0.0;
		Lines.Add({FString::Printf(TEXT("R9 데모 — 무대 자리를 찾는 중: 시작점 둘레 %.0f m (%d/%d) · %.0f 초"), EcoR9DemoSubsystemImpl::kRingHalfCm[S.ScanRing] / 100.0,
								   S.ScanRing + 1, EcoR9DemoSubsystemImpl::kNumRings, Wait),
				   Gold, false});
	}
	else if (S.Phase != EEcoR9DemoPhase::Running)
	{
		const double Wait = GetWorld() ? GetWorld()->GetTimeSeconds() - S.PhaseStart : 0.0;
		Lines.Add({FString::Printf(TEXT("R9 데모 — 무대 자리를 불러오는 중 (%.0f 초)"), Wait), Gold, false});
	}
	else
	{
		int32 Alive[EcoR9Demo::kNumSpecies] = {};
		EcoR9Demo::CountAlive(S.Cur, Alive);
		Lines.Add({bLive ? FString(TEXT("실시간 · 파이썬에서 배운 두뇌(사슴·늑대·멧돼지)를 언리얼 C++ 로 추론"))
						 : FString(TEXT("파이썬 실행 기록 재생 (언리얼 실시간 추론 아님)")),
				   Gold, true});
		Lines.Add({FString::Printf(TEXT("%s   사슴 %d · 늑대 %d · 멧돼지 %d"), *Clock(S.SimSeconds), Alive[0], Alive[1], Alive[2]), White, true});
		Lines.Add({FString::Printf(TEXT("늑대가 잡음: 사슴 %d · 멧돼지 %d   |   멧돼지 반격 %d   |   굶어 죽음 %d"), S.DeerKilled, S.BoarKilled, S.Counters, S.Starved),
				   White, false});
		if (!S.CamLabel.IsEmpty())
		{
			Lines.Add({S.CamLabel, White, false});
		}
		const FString Pick = S.Info.Policy == "argmax" ? TEXT("가장 높은 칸") : (S.Info.Policy == "sample" ? TEXT("확률대로 (학습 때와 같음)") : TEXT("?"));
		Lines.Add({FString::Printf(TEXT("행동 고르기: %s · 멧돼지 몸 = 갈색 자리표시 (에셋 없음)%s"), *Pick, S.bFoodKnown ? TEXT(" · 풀 = 먹이 격자 값") : TEXT("")),
				   Gray, false});
		Lines.Add({TEXT("1 자동 · 2 전체 · 3 사슴 · 4 늑대 · 5 멧돼지 · 6 위 · H 글자 끄기"), Gray, false});
	}
	// 화면 메시지와 같은 글꼴 (한글 됨 — EcoV3ObserverCamera.cpp:2493). 큰 줄은 배율만 키운다
	UFont* Font = GEngine->GetSmallFont();
	if (!Font)
	{
		return;
	}
	const float Scale = FMath::Clamp(Canvas->ClipY / 1080.0f, 0.6f, 2.5f) * 1.25f;
	const float Pad = 10.0f * Scale;
	float MaxW = 0.0f;
	float TotalH = 0.0f;
	TArray<float> Heights;
	TArray<float> Scales;
	for (const FLine& L : Lines)
	{
		const float Sc = L.bBig ? Scale * 1.3f : Scale;
		float XL = 0.0f, YL = 0.0f;
		Canvas->TextSize(Font, L.Text, XL, YL, Sc, Sc);
		MaxW = FMath::Max(MaxW, XL);
		Heights.Add(YL * 1.15f);
		Scales.Add(Sc);
		TotalH += YL * 1.15f;
	}
	const float X0 = 16.0f * Scale;
	const float Y0 = 16.0f * Scale;
	FCanvasTileItem Back(FVector2D(X0 - Pad, Y0 - Pad), FVector2D(MaxW + 2.0f * Pad, TotalH + 2.0f * Pad), FLinearColor(0.0f, 0.0f, 0.0f, 0.42f));
	Back.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Back);
	float Y = Y0;
	for (int32 i = 0; i < Lines.Num(); ++i)
	{
		FCanvasTextItem Item(FVector2D(X0, Y), FText::FromString(Lines[i].Text), Font, Lines[i].Color);
		Item.Scale = FVector2D(Scales[i], Scales[i]);
		Item.EnableShadow(FLinearColor::Black);
		Canvas->DrawItem(Item);
		Y += Heights[i];
	}
}

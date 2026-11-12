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
		TEXT("Play 전에 바꾼다. 명령줄 -EcoR9Demo=<폴더>·-EcoR9Replay=<파일> 이 있으면 그것이 먼저다. 팀 섬 원본 맵에서만 돈다."));
	static TAutoConsoleVariable<FString> CVarBrains(TEXT("eco.R9Demo.Brains"), TEXT(""), TEXT("R9 데모 실시간 판 두뇌 폴더 ({deer,wolf,boar}.r9brain). 비면 <프로젝트>/Saved/R9Demo/brains."));
	static TAutoConsoleVariable<FString> CVarScene(TEXT("eco.R9Demo.Scene"), TEXT(""), TEXT("R9 데모 실시간 판 장면 파일 (비면 <두뇌 폴더>/scene.txt)."));
	static TAutoConsoleVariable<FString> CVarReplay(TEXT("eco.R9Demo.Replay"), TEXT(""), TEXT("R9 데모 재생 판 파일 (.r9rp — 파이썬 실행 기록). 비면 <프로젝트>/Saved/R9Demo/replay/demo.r9rp."));
	static TAutoConsoleVariable<FString> CVarAt(TEXT("eco.R9Demo.At"), TEXT(""), TEXT("R9 데모 무대 가운데 'x,y' (m). 비면 자동으로 트인 평지를 고른다."));
	static TAutoConsoleVariable<FString> CVarPolicy(TEXT("eco.R9Demo.Policy"), TEXT("sample"),
		TEXT("R9 데모 실시간 판 행동 고르기: sample = 확률대로 (학습 때와 같음) · argmax = 가장 높은 칸."));
	static TAutoConsoleVariable<int32> CVarAnyMap(TEXT("eco.R9Demo.AnyMap"), 0, TEXT("1 이면 팀 섬 원본 맵이 아니어도 돈다 (시험용)."));
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

	constexpr double kScanHalfCm = 20000.0;     // 자동 고르기: 선호점 둘레 400 m 정사각을 훑는다 [어림]
	constexpr double kScanCellCm = 400.0;       // 칸 4 m (먹이 칸과 같다)
	constexpr double kStageMarginCm = 2000.0;   // 무대 둘레 여유 20 m [어림]
	constexpr float kScanStreamRadius = 30000.0f;
	constexpr float kStageStreamRadius = 25000.0f;
	constexpr double kStreamTimeout = 45.0;     // 처음 Nanite 지형 짓기 약 17 초 (ISLAND_STAGE.md:558)
	constexpr double kHeightStepCm = 100.0;
	constexpr double kHeightMarginCm = 4000.0;

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

	/** 지형 높이 (충돌 높이장 — 물리 쿼리 아님). 못 읽으면 거짓. EcoV3IslandStage.cpp ScanIslandMask 와 같은 꼴. */
	struct FLandHeights
	{
		TArray<ALandscapeProxy*> Lands;

		explicit FLandHeights(UWorld& World)
		{
			for (TActorIterator<ALandscape> It(&World); It; ++It)
			{
				Lands.Add(*It);
			}
			if (Lands.IsEmpty())
			{
				for (TActorIterator<ALandscapeProxy> It(&World); It; ++It)
				{
					Lands.Add(*It);
				}
			}
		}

		bool At(double X, double Y, float& OutZ) const
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
	};

	/** 액터가 이 클래스 이름 (또는 그 하위)인가 — 헤더에 기대지 않으려고 이름으로 본다. */
	bool IsKindOfName(const AActor* Actor, const TCHAR* ClassName)
	{
		for (const UClass* C = Actor ? Actor->GetClass() : nullptr; C; C = C->GetSuperClass())
		{
			if (C->GetName() == ClassName)
			{
				return true;
			}
		}
		return false;
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
		ParseXY(PrefText, S.PrefM);
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
	S.bAnyMap = FParse::Param(Cmd, TEXT("EcoR9DemoAnyMap")) || CVarAnyMap.GetValueOnGameThread() != 0;
	return S;
}

FString FEcoR9DemoSettings::DefaultDir()
{
	return FPaths::ConvertRelativePathToFull(FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("R9Demo")));
}

bool FEcoR9DemoSettings::MapAllowed(const FString& PackageName, bool bAnyMap)
{
	return bAnyMap || PackageName.Equals(IslandMap(), ESearchCase::IgnoreCase);
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

bool UEcoR9DemoSubsystem::RefuseReason(UWorld& World, FString& OutWhy) const
{
	using namespace EcoR9DemoSubsystemImpl;
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		if (IsKindOfName(*It, TEXT("EcoCreatureIntegrationSpawner")) || IsKindOfName(*It, TEXT("EcologyRegion")))
		{
			OutWhy = FString::Printf(TEXT("월드에 통합 조정자·생태 지역(%s)이 있다 — 라이브 맵·팀 장치와 섞지 않는다"), *It->GetName());
			return true;
		}
	}
	if (FParse::Param(FCommandLine::Get(), TEXT("EcoIntegratedV3")))
	{
		OutWhy = TEXT("-EcoIntegratedV3 (통합 v3) 가 켜졌다 — 같이 돌리지 않는다");
		return true;
	}
	if (const IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.IntegratedV3.IslandLive")); V && V->GetInt() != 0)
	{
		OutWhy = TEXT("eco.IntegratedV3.IslandLive 가 켜졌다 — 같이 돌리지 않는다");
		return true;
	}
	return false;
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
	FString Why;
	if (Net == NM_Client || Net == NM_DedicatedServer)
	{
		Why = TEXT("서버·단독(보는 화면이 있는 곳)에서만 돈다");
	}
	else if (!FEcoR9DemoSettings::MapAllowed(Pkg, S.Settings.bAnyMap))
	{
		Why = FString::Printf(TEXT("맵 %s — 팀 섬 원본(%s)에서만 돈다 (eco.R9Demo.AnyMap 1 이면 아무 맵)"), *Pkg, FEcoR9DemoSettings::IslandMap());
	}
	else
	{
		RefuseReason(InWorld, Why);
	}
	if (!Why.IsEmpty())
	{
		S.Phase = EEcoR9DemoPhase::Refused;
		S.Why = Why;
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 거부 — %s. 아무것도 만들지 않는다."), *Why);
		return;
	}
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
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 켬 — %s | 맵 %s | 세계 %.0f×%.0f 단위 · 스텝 %.4f 초 · 은신처 %d · 먹이 격자 %d · 두뇌 %s · 고르기 %s · 시드 %llu"),
		   ModeName, *Pkg, S.Info.W, S.Info.H, S.Info.StepSeconds, static_cast<int32>(S.Info.Shelters.size()), S.Info.G, *Utf8(S.Info.Brains), *Utf8(S.Info.Policy),
		   static_cast<unsigned long long>(S.Info.Seed));
	if (S.Settings.bHasAt)
	{
		S.StageCenter = FVector(S.Settings.AtM.X * 100.0, S.Settings.AtM.Y * 100.0, 0.0);
		S.StageLine = FString::Printf(TEXT("무대 가운데 (%.1f, %.1f) m — 명령줄·콘솔로 줌"), S.Settings.AtM.X, S.Settings.AtM.Y);
		BeginStreamingAt(S.StageCenter, kStageStreamRadius);
		S.Phase = EEcoR9DemoPhase::WaitStage;
	}
	else
	{
		BeginStreamingAt(FVector(S.Settings.PrefM.X * 100.0, S.Settings.PrefM.Y * 100.0, 0.0), kScanStreamRadius);
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

void UEcoR9DemoSubsystem::ScanAndPick()
{
	using namespace EcoR9DemoSubsystemImpl;
	using namespace EcoR9Demo;
	FEcoR9DemoState& S = *State;
	UWorld* World = GetWorld();
	const double T0 = FPlatformTime::Seconds();
	const FVector2D Pref = S.Settings.PrefM * 100.0;
	FR9ScanGrid G;
	G.CellCm = kScanCellCm;
	G.Nx = G.Ny = FMath::RoundToInt32(2.0 * kScanHalfCm / kScanCellCm);
	G.X0 = Pref.X - kScanHalfCm;
	G.Y0 = Pref.Y - kScanHalfCm;
	const int32 N = G.Nx * G.Ny;
	G.Height.assign(static_cast<std::size_t>(N), std::numeric_limits<float>::quiet_NaN());
	G.Blocked.assign(static_cast<std::size_t>(N), 0);
	const FLandHeights Land(*World);
	auto CellX = [&G](int32 Ix) { return G.X0 + (Ix + 0.5) * G.CellCm; };
	auto CellY = [&G](int32 Iy) { return G.Y0 + (Iy + 0.5) * G.CellCm; };
	for (int32 y = 0; y < G.Ny; ++y)
	{
		for (int32 x = 0; x < G.Nx; ++x)
		{
			float Z = 0.0f;
			if (Land.At(CellX(x), CellY(y), Z))
			{
				G.Height[G.Index(x, y)] = Z;
			}
		}
	}
	int32 NoGround = 0, Sea = 0, Water = 0, Steep = 0, Objects = 0;
	for (int32 k = 0; k < N; ++k)
	{
		NoGround += FMath::IsNaN(G.Height[static_cast<std::size_t>(k)]) ? 1 : 0;
	}
	auto Mark = [&G](int32 X, int32 Y, int32& Counter)
	{
		uint8& B = G.Blocked[G.Index(X, Y)];
		if (B == 0)
		{
			B = 1;
			++Counter;
		}
	};
	auto MarkBox = [&G, &Mark, &CellX, &CellY](const FBox& Box, double Pad, int32& Counter)
	{
		const int32 Ix0 = FMath::Max(0, FMath::FloorToInt32((Box.Min.X - Pad - G.X0) / G.CellCm));
		const int32 Iy0 = FMath::Max(0, FMath::FloorToInt32((Box.Min.Y - Pad - G.Y0) / G.CellCm));
		const int32 Ix1 = FMath::Min(G.Nx - 1, FMath::FloorToInt32((Box.Max.X + Pad - G.X0) / G.CellCm));
		const int32 Iy1 = FMath::Min(G.Ny - 1, FMath::FloorToInt32((Box.Max.Y + Pad - G.Y0) / G.CellCm));
		for (int32 y = Iy0; y <= Iy1; ++y)
		{
			for (int32 x = Ix0; x <= Ix1; ++x)
			{
				const double Px = CellX(x);
				const double Py = CellY(y);
				if (Px >= Box.Min.X - Pad && Px <= Box.Max.X + Pad && Py >= Box.Min.Y - Pad && Py <= Box.Max.Y + Pad)
				{
					Mark(x, y, Counter);
				}
			}
		}
	};
	const FBox ScanBox(FVector(G.X0, G.Y0, -1e7), FVector(G.X0 + G.Nx * G.CellCm, G.Y0 + G.Ny * G.CellCm, 1e7));
	auto Overlaps2D = [&ScanBox](const FBox& B)
	{
		return B.IsValid && B.Max.X >= ScanBox.Min.X && B.Min.X <= ScanBox.Max.X && B.Max.Y >= ScanBox.Min.Y && B.Min.Y <= ScanBox.Max.Y;
	};
	// 물: 바다 = 수면 높이 + 1 m 아래 땅, 호수·강 = 그 물 몸체 충돌만 선 검사 (EcoV3IslandStage.cpp 와 같은 꼴)
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
				const float Ground = G.Height[G.Index(x, y)];
				if (FMath::IsNaN(Ground))
				{
					continue;
				}
				const FVector Start(CellX(x), CellY(y), Box.Max.Z + 100.0);
				const FVector End(CellX(x), CellY(y), FMath::Min(Box.Min.Z, static_cast<double>(Ground)) - 100.0);
				double Surface = -std::numeric_limits<double>::infinity();
				for (UPrimitiveComponent* C : Hits)
				{
					FHitResult Hit;
					if (C->LineTraceComponent(Hit, Start, End, WaterParams))
					{
						Surface = FMath::Max(Surface, Hit.ImpactPoint.Z);
					}
				}
				if (FMath::IsFinite(Surface) && Ground < Surface + 100.0)
				{
					Mark(x, y, Water);
				}
			}
		}
	}
	// 가파름: 이웃 칸 높이 차 / 칸 > 0.36 (약 20°) [어림]
	for (int32 y = 0; y < G.Ny; ++y)
	{
		for (int32 x = 0; x < G.Nx; ++x)
		{
			const float Z = G.Height[G.Index(x, y)];
			if (FMath::IsNaN(Z))
			{
				continue;
			}
			float Worst = 0.0f;
			if (x + 1 < G.Nx && !FMath::IsNaN(G.Height[G.Index(x + 1, y)]))
			{
				Worst = FMath::Max(Worst, FMath::Abs(G.Height[G.Index(x + 1, y)] - Z));
			}
			if (y + 1 < G.Ny && !FMath::IsNaN(G.Height[G.Index(x, y + 1)]))
			{
				Worst = FMath::Max(Worst, FMath::Abs(G.Height[G.Index(x, y + 1)] - Z));
			}
			if (Worst / G.CellCm > 0.36)
			{
				Mark(x, y, Steep);
			}
		}
	}
	// 나무·바위·선인장·야자 (정적·인스턴스 메시 경계 상자). 풀·눈 덮개 같은 낮은 장식은 뺀다
	static const TCHAR* const kDecorWords[] = {TEXT("grass"), TEXT("snow"), TEXT("flower"), TEXT("clover"), TEXT("fern"), TEXT("weed"), TEXT("decal"), TEXT("pebble")};
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
					MarkBox(B, 100.0, Objects);
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
				MarkBox(B, 100.0, Objects);
			}
		}
	}
	FR9PickParams P;
	P.SideCm = FMath::Max(S.Info.W, S.Info.H) * S.Info.UnitCm;
	P.MarginCm = kStageMarginCm;
	P.PrefX = Pref.X;
	P.PrefY = Pref.Y;
	P.Stride = 3;
	const FR9PickResult R = PickStage(G, P);
	const double T1 = FPlatformTime::Seconds();
	if (R.bOk)
	{
		S.StageCenter = FVector(R.Cx, R.Cy, R.MeanCm);
		S.StageLine = FString::Printf(TEXT("무대 가운데 (%.1f, %.1f) m · 높이 폭 %.1f m · 선호점에서 %.0f m · 후보 %lld · 여유 %.0f m"), R.Cx / 100.0, R.Cy / 100.0,
									  R.RangeCm / 100.0, FVector2D::Distance(FVector2D(R.Cx, R.Cy), Pref) / 100.0, static_cast<long long>(R.Candidates),
									  R.MarginUsed / 100.0);
	}
	else
	{
		float Z = 0.0f;
		Land.At(Pref.X, Pref.Y, Z);
		S.StageCenter = FVector(Pref.X, Pref.Y, Z);
		S.StageLine = FString::Printf(TEXT("트인 평지를 못 찾음 — 선호점 (%.1f, %.1f) m 에 그대로 둠"), Pref.X / 100.0, Pref.Y / 100.0);
	}
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] %s | 훑기 %d×%d 칸(4 m) · 막힘: 지형 없음 %d · 바다 %d · 호수·강 %d · 가파름 %d · 나무·바위 %d · 지형 조각 %d · %.2f 초"),
		   *S.StageLine, G.Nx, G.Ny, NoGround, Sea, Water, Steep, Objects, Land.Lands.Num(), T1 - T0);
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
		const FLandHeights Land(*World);
		float Z = 0.0f;
		if (Land.At(XCm, YCm, Z))
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
	const FLandHeights Land(*World);
	for (int32 y = 0; y < H.Ny; ++y)
	{
		for (int32 x = 0; x < H.Nx; ++x)
		{
			float Z = 0.0f;
			if (Land.At(H.X0 + x * H.Step, H.Y0 + y * H.Step, Z))
			{
				H.Z[static_cast<std::size_t>(y) * static_cast<std::size_t>(H.Nx) + static_cast<std::size_t>(x)] = Z;
			}
		}
	}
	double Mean = 0.0, Lo = 0.0, Hi = 0.0;
	const bool bAny = H.Stats(Mean, Lo, Hi);
	H.Fallback = bAny ? Mean : S.StageCenter.Z;
	S.StageCenter.Z = H.At(S.StageCenter.X, S.StageCenter.Y);
	if (!bAny)
	{
		UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 무대 둘레 지형 높이를 하나도 못 읽음 — 평평한 z=%.0f 로 그린다 (스트리밍 덜 됨?)"), H.Fallback);
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
	UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 무대 섬 — %s | 높이 %d×%d 표본 (%.0f ~ %.0f m) | 몸 %d · 풀 덩어리 %d · 은신처 %d | %.2f 초"), *S.StageLine, H.Nx,
		   H.Ny, Lo / 100.0, Hi / 100.0, S.Bodies.Num(), S.TuftBase.Num(), static_cast<int32>(S.Info.Shelters.size()), FPlatformTime::Seconds() - T0);
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
				UE_LOG(LogEcoR9Demo, Warning, TEXT("[EcoR9Demo] 선호점 둘레 스트리밍이 %.0f 초 안에 안 끝남 — 불린 만큼 훑는다"), kStreamTimeout);
			}
			ScanAndPick();
			BeginStreamingAt(S.StageCenter, kStageStreamRadius);
			S.Phase = EEcoR9DemoPhase::WaitStage;
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
				// 명령줄 자리: 가운데 높이를 지금 읽는다
				const FLandHeights Land(*World);
				float Z = 0.0f;
				if (Land.At(S.StageCenter.X, S.StageCenter.Y, Z))
				{
					S.StageCenter.Z = Z;
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
			UE_LOG(LogEcoR9Demo, Log, TEXT("[EcoR9Demo] 팀 하늘 관리자(BP_SkyManager)가 없다 — 하늘은 그대로"));
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
		// 상한 60 월드 초 — run_player.sh 의 -seconds=<초+180> 안에 녹화가 끝나게 (스트리밍 2×45 + 2 + 60 < 180)
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

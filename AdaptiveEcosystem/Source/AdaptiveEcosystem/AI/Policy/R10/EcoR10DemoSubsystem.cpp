// R10 데모 — 켜기·땅 훑기·풀기·그리기·카메라·녹화 (머리말 EcoR10DemoSubsystem.h).

#include "AI/Policy/R10/EcoR10DemoSubsystem.h"

#include "AI/Policy/R10/EcoR10Core.h"
#include "AI/Policy/R10/EcoR10DemoMap.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Creature/Representation/EcoCreatureVisualState.h"

#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "CanvasItem.h"
#include "Components/TextRenderComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "ContentStreaming.h"
#include "Debug/DebugDrawService.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/Font.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/Pawn.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "InputCoreTypes.h"
#include "Landscape.h"
#include "LandscapeProxy.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "ShaderCompiler.h"
#include "UnrealClient.h"

#include <cmath>
#include <limits>
#include <string>
#include <vector>

DEFINE_LOG_CATEGORY_STATIC(LogEcoR10Demo, Log, All);

// -----------------------------------------------------------------------------
// 설정
// -----------------------------------------------------------------------------
namespace EcoR10DemoImpl
{
	static TAutoConsoleVariable<int32> CVarDemo(TEXT("eco.R10Demo"), 0,
		TEXT("R10 데모: 1 = 파이썬에서 배운 R10 두뇌 16 종을 이 맵 위에서 실시간으로 (서버·단독). 0 = 끔 (Play 중이면 바로 멈춤)."),
		FConsoleVariableDelegate::CreateStatic(&UEcoR10DemoSubsystem::OnCVarChanged), ECVF_Default);
	static TAutoConsoleVariable<FString> CVarDir(TEXT("eco.R10Demo.Dir"), TEXT(""),
		TEXT("R10 데모 두뇌 폴더 (species.txt + <종>.r10brain). 비면 <프로젝트>/Saved/R10Demo."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarArea(TEXT("eco.R10Demo.Area"), 300,
		TEXT("R10 데모 영역 한 변 (m, 60 ~ 1000). 플레이어 시작점 둘레 정사각."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarCell(TEXT("eco.R10Demo.Cell"), 1.0f,
		TEXT("R10 데모 지형 칸 (m, 0.5 ~ 4). 학습 맵과 같은 1 m 가 기본 — 먹이 용량이 칸마다 값이라."), ECVF_Default);
	static TAutoConsoleVariable<FString> CVarPer(TEXT("eco.R10Demo.PerSpecies"), TEXT("8,12"),
		TEXT("R10 데모 종마다 '시작 수,상한' (예 8,12)."), ECVF_Default);
	static TAutoConsoleVariable<float> CVarSpeed(TEXT("eco.R10Demo.Speed"), 1.0f, TEXT("R10 데모 빠르기 (1 = 학습 세계 시간 그대로)."), ECVF_Default);
	static TAutoConsoleVariable<int32> CVarSeed(TEXT("eco.R10Demo.Seed"), 1, TEXT("R10 데모 시드 (장면·확률 뽑기)."), ECVF_Default);
	static TAutoConsoleVariable<FString> CVarOnlyMap(TEXT("eco.R10Demo.OnlyMap"), TEXT(""),
		TEXT("R10 데모를 콘솔 값(eco.R10Demo 1)으로 켰을 때 이 맵들(패키지 경로 또는 짧은 이름, 쉼표)에서만 Play 때 켬. 비면 모든 맵. 명령줄·Play 중 직접 친 값은 거르지 않음."),
		ECVF_Default);
	static TAutoConsoleVariable<int32> CVarHide(TEXT("eco.R10Demo.HideOthers"), 1,
		TEXT("R10 데모 동안 맵의 다른 동물 표현 액터를 보이지 않게 (그쪽 시뮬레이션은 그대로)."), ECVF_Default);

	constexpr int64 kStableBase = 9100000000ll;   // 표현 액터 id (팀 개체·R9 데모와 겹치지 않게)
	const FName kRegion(TEXT("R10Demo"));
	constexpr double kDecisionS = EcoR10::kStepS * EcoR10::kDecisionSteps;

	/** 종 id → 표현 BP 경로 후보 · 자리표시 색 · 고기 먹는 몸(먹기 자세만). 그리기 전용 — 행동·규칙에 쓰지 않음. */
	struct FVis
	{
		const char* Id;
		const TCHAR* Paths[2];
		FColor Color;
		bool bMeat;
	};
	const FVis kVis[] = {
		{"deer", {TEXT("/Game/JYU/Creatures/BP_JYU_Deer.BP_JYU_Deer_C"), TEXT("/Game/JYU/Fauna/Deer/BP_Deer.BP_Deer_C")}, FColor(170, 120, 70), false},
		{"wolf", {TEXT("/Game/JYU/Creatures/BP_JYU_Wolf.BP_JYU_Wolf_C"), TEXT("/Game/JYU/Fauna/Wolf/BP_Wolf.BP_Wolf_C")}, FColor(90, 90, 100), true},
		{"boar", {TEXT("/Game/JYU/Fauna/Pig/BP_Pig.BP_Pig_C"), nullptr}, FColor(110, 70, 50), false},
		{"buffalo", {TEXT("/Game/JYU/Fauna/Buffalo/BP_Buffalo.BP_Buffalo_C"), nullptr}, FColor(60, 50, 45), false},
		{"leopard", {TEXT("/Game/JYU/Fauna/Leopard/BP_Leopard.BP_Leopard_C"), nullptr}, FColor(220, 170, 60), true},
		{"fox", {TEXT("/Game/JYU/Fauna/Fox/BP_Fox.BP_Fox_C"), nullptr}, FColor(230, 110, 30), true},
		{"rat", {TEXT("/Game/JYU/Fauna/Rat/BP_Rat.BP_Rat_C"), nullptr}, FColor(120, 110, 100), false},
		{"crow", {TEXT("/Game/JYU/Fauna/Crow/BP_Crow.BP_Crow_C"), nullptr}, FColor(20, 20, 25), true},
		{"ariake_catfish", {TEXT("/Game/JYU/ExpandedFauna/AriakeCatfish/BP_AriakeCatfish.BP_AriakeCatfish_C"), nullptr}, FColor(80, 90, 60), true},
		{"bighorn", {TEXT("/Game/JYU/ExpandedFauna/Bighorn/BP_Bighorn.BP_Bighorn_C"), nullptr}, FColor(160, 140, 110), false},
		{"common_carp", {TEXT("/Game/JYU/ExpandedFauna/CommonCarp/BP_CommonCarp.BP_CommonCarp_C"), nullptr}, FColor(200, 160, 60), false},
		{"golden_eagle", {TEXT("/Game/JYU/ExpandedFauna/GoldenEagle/BP_GoldenEagle.BP_GoldenEagle_C"), nullptr}, FColor(140, 90, 40), true},
		{"horse", {TEXT("/Game/JYU/ExpandedFauna/Horse/BP_Horse.BP_Horse_C"), nullptr}, FColor(130, 80, 50), false},
		{"jackrabbit", {TEXT("/Game/JYU/ExpandedFauna/Jackrabbit/BP_Jackrabbit.BP_Jackrabbit_C"), nullptr}, FColor(190, 170, 140), false},
		{"mink", {TEXT("/Game/JYU/ExpandedFauna/Mink/BP_Mink.BP_Mink_C"), nullptr}, FColor(70, 45, 30), true},
		{"small_fish", {TEXT("/Game/JYU/ExpandedFauna/UnidentifiedFish/BP_UnidentifiedFish.BP_UnidentifiedFish_C"), nullptr}, FColor(150, 170, 190), false},
	};

	const FVis* FindVis(const std::string& Id)
	{
		for (const FVis& V : kVis)
		{
			if (Id == V.Id)
			{
				return &V;
			}
		}
		return nullptr;
	}

	const TCHAR* ActionName(int32 A)
	{
		if (A == EcoR10::ActEat) return TEXT("먹기");
		if (A >= EcoR10::ActSlow0 && A < EcoR10::ActSlow0 + 8) return TEXT("걷기");
		if (A >= EcoR10::ActFast0 && A < EcoR10::ActFast0 + 8) return TEXT("뛰기");
		if (A == EcoR10::ActHide) return TEXT("숨기");
		if (A == EcoR10::ActWatch) return TEXT("지켜보기");
		if (A == EcoR10::ActUp) return TEXT("오르기");
		if (A == EcoR10::ActDown) return TEXT("내리기");
		if (A == EcoR10::ActDive) return TEXT("급강하");
		if (A == EcoR10::ActBurst) return TEXT("덮치기");
		return TEXT("?");
	}

	/** 'a,b' → 두 수. */
	bool ParsePair(const FString& Text, int32& A, int32& B)
	{
		TArray<FString> Parts;
		Text.ParseIntoArray(Parts, TEXT(","), true);
		if (Parts.Num() != 2 || !Parts[0].IsNumeric() || !Parts[1].IsNumeric())
		{
			return false;
		}
		A = FCString::Atoi(*Parts[0]);
		B = FCString::Atoi(*Parts[1]);
		return true;
	}

	bool AnyWord(const FString& Lower, std::initializer_list<const TCHAR*> Words)
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
}

/** 몸 하나 (uid 별). */
struct FEcoR10Body
{
	TWeakObjectPtr<AEcoCreatureRepresentationActor> Rep;
	TWeakObjectPtr<AActor> Ball;    // BP 가 없는 종의 자리표시
	int32 Species = -1;
	int64 Sequence = 0;
	bool bDead = false;
	double DeadAt = 0.0;
	double RemoveAt = -1.0;
	FVector Corpse = FVector::ZeroVector;
	float CorpseYaw = 0.0f;
	double AttackUntil = -1.0;
	bool bSnap = true;
	bool bSeen = false;
};

struct FEcoR10DemoState
{
	// 설정
	bool bWanted = false;
	bool bFromCmd = false;
	FString OnlyMap;
	FString Dir;
	int32 AreaM = 300;
	double CellM = 1.0;
	int32 Start = 8, Cap = 12;
	uint64 Seed = 1;
	bool bHasAt = false;
	FVector2D AtM = FVector2D::ZeroVector;
	FString CaptureDir;
	float CaptureFps = 10.0f, CaptureSeconds = 0.0f;
	float ExitAfter = 0.0f;
	float CamCycle = 0.0f;

	enum class EPhase : uint8 { Off, Waiting, Running, Failed };
	EPhase Phase = EPhase::Off;
	double PhaseSince = 0.0;
	double NextScanAt = 0.0;
	int32 ScanTries = 0;
	FString Why;

	// 자리: 코어 (0, 0) = 언리얼 (X0, Y0) cm, 코어 높이 0 = 언리얼 Z0 cm. 코어 x → 언리얼 X, 코어 y → 언리얼 Y (뒤집지 않음 — 거울 세계도
	// 학습 맵 분포 안이고, 감각·물리는 코어 좌표 안에서 일관된다. 화면 yaw = atan2(hy, hx))
	FVector Center = FVector::ZeroVector;
	FString CenterLabel;
	double X0 = 0.0, Y0 = 0.0, Z0 = 0.0;
	TArray<ALandscapeProxy*> Lands;

	// 코어
	EcoR10::FWorld World;
	std::vector<EcoR10::FSpecies> Species;
	std::vector<EcoR10::FBrain> Brains;
	std::vector<const EcoR10::FBrain*> BrainBySpecies;
	std::vector<float> Obs;
	std::vector<int> Actions;
	std::vector<double> PX, PY, PZ, PHx, PHy;
	std::vector<int64_t> PUid;
	std::vector<uint8_t> PAlive;
	double Acc = 0.0;
	int64 Decisions = 0;
	double RunningSince = 0.0;
	double NextLogAt = 30.0;
	FString MapLine, BrainLine, BodyLine;

	// 집계 (종별)
	TArray<int32> Births, Bites, DeathBy[4];   // 원인 1 물림 · 2 굶음 · 3 물·숨 · 0 그 밖 (코어 Cause 번호 — EcoR10Core.h)

	// 몸
	TMap<int64, FEcoR10Body> Bodies;
	TArray<TWeakObjectPtr<AActor>> Hidden;
	double NextHideAt = 0.0;

	// 카메라
	int32 CamSpecies = -1;
	int64 CamUid = 0;
	double CamLostAt = -1.0;
	bool bTop = false;
	bool bFree = false;
	bool bShowText = true;
	double Zoom = 1.0;
	FVector CamFocus = FVector::ZeroVector;
	double CamYaw = 0.0;
	double NextCycleAt = 0.0;

	// 녹화
	double CaptureClock = -1.0;
	int32 CaptureFrames = 0;
	bool bCaptureDone = false;
	int32 QuitCountdown = -1;
	bool bShaderWaitLogged = false;

	FDelegateHandle DrawHandle;
};

// -----------------------------------------------------------------------------
// 만들기·켜기
// -----------------------------------------------------------------------------

bool UEcoR10DemoSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	if (IsRunningDedicatedServer() || IsRunningClientOnly() || GIsAutomationTesting)
	{
		return false;
	}
	return Super::ShouldCreateSubsystem(Outer);
}

bool UEcoR10DemoSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

TStatId UEcoR10DemoSubsystem::GetStatId() const
{
	RETURN_QUICK_DECLARE_CYCLE_STAT(UEcoR10DemoSubsystem, STATGROUP_Tickables);
}

static void ResolveR10DemoSettings(FEcoR10DemoState& S)
{
	using namespace EcoR10DemoImpl;
	const TCHAR* Cmd = FCommandLine::Get();
	FString Dir;
	S.bFromCmd = false;
	if (FParse::Value(Cmd, TEXT("-EcoR10Demo="), Dir))
	{
		S.bFromCmd = true;
	}
	else if (FParse::Param(Cmd, TEXT("EcoR10Demo")))
	{
		S.bFromCmd = true;
	}
	S.bWanted = S.bFromCmd || CVarDemo.GetValueOnGameThread() != 0;
	S.OnlyMap = CVarOnlyMap.GetValueOnGameThread().TrimStartAndEnd();
	if (Dir.IsEmpty())
	{
		Dir = CVarDir.GetValueOnGameThread();
	}
	if (Dir.IsEmpty())
	{
		Dir = FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("R10Demo"));
	}
	S.Dir = FPaths::ConvertRelativePathToFull(Dir);
	S.AreaM = FMath::Clamp(CVarArea.GetValueOnGameThread(), 60, 1000);
	int32 Area = 0;
	if (FParse::Value(Cmd, TEXT("-EcoR10Area="), Area))
	{
		S.AreaM = FMath::Clamp(Area, 60, 1000);
	}
	S.CellM = FMath::Clamp(static_cast<double>(CVarCell.GetValueOnGameThread()), 0.5, 4.0);
	int32 A = 8, B = 12;
	FString Per = CVarPer.GetValueOnGameThread();
	FParse::Value(Cmd, TEXT("-EcoR10Per="), Per);
	if (ParsePair(Per, A, B))
	{
		S.Start = FMath::Clamp(A, 0, 60);
		S.Cap = FMath::Clamp(FMath::Max(A, B), 1, 80);
	}
	int32 Seed = CVarSeed.GetValueOnGameThread();
	FParse::Value(Cmd, TEXT("-EcoR10Seed="), Seed);
	S.Seed = static_cast<uint64>(FMath::Max(Seed, 0));
	FString At;
	S.bHasAt = false;
	if (FParse::Value(Cmd, TEXT("-EcoR10DemoAt="), At))
	{
		TArray<FString> P;
		At.ParseIntoArray(P, TEXT(","), true);
		if (P.Num() == 2)
		{
			S.AtM = FVector2D(FCString::Atod(*P[0]), FCString::Atod(*P[1]));
			S.bHasAt = true;
		}
	}
	FString Cap;
	if (FParse::Value(Cmd, TEXT("-EcoR10Capture="), Cap, /*bShouldStopOnSeparator*/ false))
	{
		TArray<FString> P;
		Cap.ParseIntoArray(P, TEXT(","), true);
		if (P.Num() >= 1)
		{
			S.CaptureDir = P[0];
		}
		if (P.Num() >= 2)
		{
			S.CaptureFps = FMath::Clamp(static_cast<float>(FCString::Atod(*P[1])), 1.0f, 60.0f);
		}
		if (P.Num() >= 3)
		{
			S.CaptureSeconds = FMath::Clamp(static_cast<float>(FCString::Atod(*P[2])), 0.5f, 600.0f);
		}
	}
	FParse::Value(Cmd, TEXT("-EcoR10ExitAfter="), S.ExitAfter);
	FParse::Value(Cmd, TEXT("-EcoR10CamCycle="), S.CamCycle);
}

// eco.R10Demo.OnlyMap 안의 맵인가 (R9 eco.R9Demo.OnlyMap 과 같은 꼴: '/Game/X/LV' · '/Game/X/LV.LV' · 'LV').
static bool R10MapAllowed(const FString& OnlyMap, const UWorld* W)
{
	if (OnlyMap.IsEmpty() || !W || !W->GetPackage())
	{
		return true;
	}
	const FString Pkg = UWorld::RemovePIEPrefix(W->GetPackage()->GetName());
	const FString Short = FPackageName::GetShortName(Pkg);
	FString List = OnlyMap;
	List.ReplaceInline(TEXT(";"), TEXT(","));
	TArray<FString> Items;
	List.ParseIntoArray(Items, TEXT(","), true);
	for (FString Item : Items)
	{
		Item.TrimStartAndEndInline();
		Item.TrimQuotesInline();
		if (Item.IsEmpty())
		{
			continue;
		}
		const FString ItemPkg = Item.StartsWith(TEXT("/")) ? FPackageName::ObjectPathToPackageName(Item) : Item;
		if (ItemPkg.Equals(Pkg, ESearchCase::IgnoreCase) || ItemPkg.Equals(Short, ESearchCase::IgnoreCase))
		{
			return true;
		}
	}
	return false;
}

static void ApplyR10MapFilter(FEcoR10DemoState& S, const UWorld* W)
{
	if (S.bWanted && !S.bFromCmd && !R10MapAllowed(S.OnlyMap, W))
	{
		S.bWanted = false;
		UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 이 맵은 eco.R10Demo.OnlyMap(%s) 밖 — 켜지 않음 (Play 중 콘솔 eco.R10Demo 1 로 켤 수 있음)"), *S.OnlyMap);
	}
}

void UEcoR10DemoSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	State = MakeShared<FEcoR10DemoState>();
	ResolveR10DemoSettings(*State);
	ApplyR10MapFilter(*State, GetWorld());
	State->DrawHandle = UDebugDrawService::Register(TEXT("Game"), FDebugDrawDelegate::CreateUObject(this, &UEcoR10DemoSubsystem::DrawOverlay));
	if (State->bWanted)
	{
		// R9 데모가 같은 실행에서 켜지지 않게 (R9 는 Play 시작 때 콘솔 값을 다시 읽는다 — 코드로 0, 저장하지 않음)
		if (IConsoleVariable* R9 = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo")))
		{
			if (R9->GetInt() != 0)
			{
				R9->Set(0, ECVF_SetByCode);
				UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] R10 데모를 켜서 이 실행의 R9 데모(eco.R9Demo)를 끔 (저장 안 함)"));
			}
		}
	}
}

void UEcoR10DemoSubsystem::Deinitialize()
{
	if (State)
	{
		if (State->DrawHandle.IsValid())
		{
			UDebugDrawService::Unregister(State->DrawHandle);
		}
		Teardown(false);
	}
	State.Reset();
	Super::Deinitialize();
}

void UEcoR10DemoSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	if (!State)
	{
		return;
	}
	ResolveR10DemoSettings(*State);
	ApplyR10MapFilter(*State, &InWorld);
	if (State->bWanted)
	{
		StartDemo(TEXT("Play 시작"));
	}
}

void UEcoR10DemoSubsystem::OnCVarChanged(IConsoleVariable* Var)
{
	if (!GEngine)
	{
		return;
	}
	for (const FWorldContext& Ctx : GEngine->GetWorldContexts())
	{
		UWorld* W = Ctx.World();
		if (!W || (W->WorldType != EWorldType::Game && W->WorldType != EWorldType::PIE) || W->bIsTearingDown || !W->HasBegunPlay())
		{
			continue;
		}
		if (UEcoR10DemoSubsystem* Sub = W->GetSubsystem<UEcoR10DemoSubsystem>())
		{
			if (Var && Var->GetInt() != 0)
			{
				if (IConsoleVariable* R9 = IConsoleManager::Get().FindConsoleVariable(TEXT("eco.R9Demo")))
				{
					if (R9->GetInt() != 0)
					{
						R9->Set(0, ECVF_SetByCode);   // R9 데모 멈춤 (R9 콜백이 그 월드에서 끈다)
					}
				}
				Sub->StartDemo(TEXT("콘솔 eco.R10Demo 1"));
			}
			else
			{
				Sub->StopDemo(TEXT("콘솔 eco.R10Demo 0"));
			}
		}
	}
}

void UEcoR10DemoSubsystem::StartDemo(const TCHAR* Why)
{
	if (!State || State->Phase == FEcoR10DemoState::EPhase::Waiting || State->Phase == FEcoR10DemoState::EPhase::Running)
	{
		return;
	}
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const ENetMode Net = World->GetNetMode();
	if (Net == NM_Client || Net == NM_DedicatedServer)
	{
		UE_LOG(LogEcoR10Demo, Warning, TEXT("[EcoR10Demo] 거부 — 서버·단독에서만 돈다"));
		State->Phase = FEcoR10DemoState::EPhase::Failed;
		return;
	}
	ResolveR10DemoSettings(*State);
	FString Err;
	if (!LoadInputs(Err))
	{
		Fail(Err);
		return;
	}
	State->Phase = FEcoR10DemoState::EPhase::Waiting;
	State->PhaseSince = World->GetTimeSeconds();
	State->NextScanAt = State->PhaseSince + 2.0;   // 지형·물 몸체·나무가 불릴 시간
	State->ScanTries = 0;
	UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 시작 (%s) — 두뇌 폴더 %s · 영역 %d m · 칸 %.1f m · 종마다 %d (상한 %d) · 시드 %llu"), Why, *State->Dir,
		   State->AreaM, State->CellM, State->Start, State->Cap, static_cast<unsigned long long>(State->Seed));
}

void UEcoR10DemoSubsystem::StopDemo(const TCHAR* Why)
{
	if (!State || State->Phase == FEcoR10DemoState::EPhase::Off)
	{
		return;
	}
	UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 멈춤 (%s)"), Why);
	Teardown(true);
}

void UEcoR10DemoSubsystem::Fail(const FString& Why)
{
	State->Phase = FEcoR10DemoState::EPhase::Failed;
	State->Why = Why;
	UE_LOG(LogEcoR10Demo, Error, TEXT("[EcoR10Demo] 실패 — %s"), *Why);
	if (State->ExitAfter > 0.0f || !State->CaptureDir.IsEmpty())
	{
		FPlatformMisc::RequestExit(false, TEXT("EcoR10Demo"));
	}
}

void UEcoR10DemoSubsystem::Teardown(bool bRestoreView)
{
	if (!State)
	{
		return;
	}
	FEcoR10DemoState& S = *State;
	for (AActor* A : SpawnedActors)
	{
		if (IsValid(A))
		{
			A->Destroy();
		}
	}
	SpawnedActors.Reset();
	for (TPair<int64, FEcoR10Body>& P : S.Bodies)
	{
		if (AActor* A = P.Value.Rep.Get())
		{
			A->Destroy();
		}
		if (AActor* A = P.Value.Ball.Get())
		{
			A->Destroy();
		}
	}
	S.Bodies.Reset();
	for (const TWeakObjectPtr<AActor>& H : S.Hidden)
	{
		if (AActor* A = H.Get())
		{
			A->SetActorHiddenInGame(false);
		}
	}
	S.Hidden.Reset();
	if (bRestoreView)
	{
		if (UWorld* W = GetWorld())
		{
			if (APlayerController* PC = W->GetFirstPlayerController())
			{
				if (APawn* Pawn = PC->GetPawn())
				{
					PC->SetViewTarget(Pawn);
				}
			}
		}
	}
	if (IsValid(Camera))
	{
		Camera->Destroy();
	}
	Camera = nullptr;
	S.Phase = FEcoR10DemoState::EPhase::Off;
}

bool UEcoR10DemoSubsystem::IsRunning() const
{
	return State && State->Phase == FEcoR10DemoState::EPhase::Running;
}

int32 UEcoR10DemoSubsystem::NumAlive() const
{
	if (!IsRunning())
	{
		return 0;
	}
	int32 N = 0;
	for (uint8 A : State->World.Alive)
	{
		N += A ? 1 : 0;
	}
	return N;
}

int64 UEcoR10DemoSubsystem::NumDecisions() const
{
	return State ? State->Decisions : 0;
}

int32 UEcoR10DemoSubsystem::NumSpecies() const
{
	return State ? static_cast<int32>(State->Species.size()) : 0;
}

// -----------------------------------------------------------------------------
// 입력: species.txt · <종>.r10brain
// -----------------------------------------------------------------------------

bool UEcoR10DemoSubsystem::LoadInputs(FString& OutError)
{
	FEcoR10DemoState& S = *State;
	FString Text;
	const FString SpeciesPath = FPaths::Combine(S.Dir, TEXT("species.txt"));
	if (!FFileHelper::LoadFileToString(Text, *SpeciesPath))
	{
		OutError = FString::Printf(TEXT("종 표 %s 를 못 읽음 — herbivore_rl/results/v3/r10/export_r10.py 로 만든다"), *SpeciesPath);
		return false;
	}
	std::string Err;
	S.Species.clear();
	const FTCHARToUTF8 Utf8(*Text);
	if (!EcoR10::LoadSpeciesTable(std::string(Utf8.Get(), Utf8.Length()), S.Species, &Err) || S.Species.empty())
	{
		OutError = FString::Printf(TEXT("종 표 %s 읽기 실패: %s"), *SpeciesPath, UTF8_TO_TCHAR(Err.c_str()));
		return false;
	}
	const int32 NS = static_cast<int32>(S.Species.size());
	S.Brains.clear();
	S.Brains.resize(static_cast<size_t>(NS));
	S.BrainBySpecies.assign(static_cast<size_t>(NS), nullptr);
	TArray<FString> Have, Rule;
	for (int32 k = 0; k < NS; ++k)
	{
		const FString Id = UTF8_TO_TCHAR(S.Species[static_cast<size_t>(k)].Id.c_str());
		TArray<uint8> Bytes;
		bool bRead = false;
		for (const FString& P : {FPaths::Combine(S.Dir, Id + TEXT(".r10brain")), FPaths::Combine(S.Dir, TEXT("brains"), Id + TEXT(".r10brain"))})
		{
			if (FFileHelper::LoadFileToArray(Bytes, *P, FILEREAD_Silent))
			{
				bRead = true;
				break;
			}
		}
		if (!bRead)
		{
			Rule.Add(Id);
			continue;
		}
		std::string BErr;
		if (!EcoR10::LoadBrain(Bytes.GetData(), static_cast<size_t>(Bytes.Num()), S.Brains[static_cast<size_t>(k)], &BErr))
		{
			UE_LOG(LogEcoR10Demo, Warning, TEXT("[EcoR10Demo] %s 두뇌 거부 (%s) — 규칙 두뇌로"), *Id, UTF8_TO_TCHAR(BErr.c_str()));
			Rule.Add(Id);
			continue;
		}
		S.BrainBySpecies[static_cast<size_t>(k)] = &S.Brains[static_cast<size_t>(k)];
		Have.Add(Id);
	}
	S.BrainLine = FString::Printf(TEXT("배운 두뇌 %d 종 [%s] · 규칙 두뇌 %d 종 [%s]"), Have.Num(), *FString::Join(Have, TEXT(" ")), Rule.Num(),
								  *FString::Join(Rule, TEXT(" ")));
	UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] %s"), *S.BrainLine);
	// 몸 클래스
	SpeciesClasses.Reset();
	SpeciesClasses.SetNum(NS);
	TArray<FString> NoBody;
	for (int32 k = 0; k < NS; ++k)
	{
		const EcoR10DemoImpl::FVis* V = EcoR10DemoImpl::FindVis(S.Species[static_cast<size_t>(k)].Id);
		UClass* Cls = nullptr;
		if (V)
		{
			for (const TCHAR* P : V->Paths)
			{
				if (P && !Cls)
				{
					Cls = LoadClass<AEcoCreatureRepresentationActor>(nullptr, P, nullptr, LOAD_NoWarn | LOAD_Quiet);
				}
			}
		}
		SpeciesClasses[k] = Cls;
		if (!Cls)
		{
			NoBody.Add(UTF8_TO_TCHAR(S.Species[static_cast<size_t>(k)].Id.c_str()));
		}
	}
	SphereMesh = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	BasicMaterial = LoadObject<UMaterialInterface>(nullptr, TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	S.BodyLine = NoBody.IsEmpty() ? FString::Printf(TEXT("몸: %d 종 모두 표현 BP"), NS)
								  : FString::Printf(TEXT("몸: 표현 BP %d 종 · 색 공 자리표시 %d 종 [%s]"), NS - NoBody.Num(), NoBody.Num(), *FString::Join(NoBody, TEXT(" ")));
	UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] %s"), *S.BodyLine);
	return true;
}

// -----------------------------------------------------------------------------
// 땅 훑기 → 코어 층 → 세계
// -----------------------------------------------------------------------------

void UEcoR10DemoSubsystem::ChooseCenter()
{
	FEcoR10DemoState& S = *State;
	UWorld* World = GetWorld();
	if (S.bHasAt)
	{
		S.Center = FVector(S.AtM.X * 100.0, S.AtM.Y * 100.0, 0.0);
		S.CenterLabel = TEXT("명령줄 -EcoR10DemoAt");
		return;
	}
	APlayerController* PC = World->GetFirstPlayerController();
	if (const APawn* Pawn = PC ? PC->GetPawn() : nullptr)
	{
		S.Center = Pawn->GetActorLocation();
		S.CenterLabel = FString::Printf(TEXT("플레이어 몸 %s"), *Pawn->GetName());
		return;
	}
	const APlayerStart* Start = nullptr;
	for (TActorIterator<APlayerStart> It(World); It; ++It)
	{
		if (!Start || It->GetName().Compare(Start->GetName(), ESearchCase::CaseSensitive) < 0)
		{
			Start = *It;
		}
	}
	if (Start)
	{
		S.Center = Start->GetActorLocation();
		S.CenterLabel = FString::Printf(TEXT("PlayerStart %s"), *Start->GetName());
		return;
	}
	S.Center = FVector::ZeroVector;
	S.CenterLabel = TEXT("월드 원점");
}

double UEcoR10DemoSubsystem::GroundCm(double X, double Y, double FallbackCm) const
{
	for (const ALandscapeProxy* L : State->Lands)
	{
		if (IsValid(L))
		{
			if (const TOptional<float> H = L->GetHeightAtLocation(FVector(X, Y, 0.0)); H.IsSet())
			{
				return H.GetValue();
			}
		}
	}
	return FallbackCm;
}

bool UEcoR10DemoSubsystem::ScanAndBuild(FString& OutError, bool bLastTry)
{
	using namespace EcoR10DemoImpl;
	FEcoR10DemoState& S = *State;
	UWorld* World = GetWorld();
	const double T0 = FPlatformTime::Seconds();
	ChooseCenter();
	S.Lands.Reset();
	for (TActorIterator<ALandscape> It(World); It; ++It)
	{
		S.Lands.Add(*It);
	}
	if (S.Lands.IsEmpty())
	{
		for (TActorIterator<ALandscapeProxy> It(World); It; ++It)
		{
			S.Lands.Add(*It);
		}
	}
	// 물이 영역에 들어오게 (헤엄 몸 — 물고기 3 종 — 은 물이 없으면 하나도 못 선다): 가운데에서 2 km 안 가장 가까운 호수·강(WaterBody, 바다 빼고)이
	// 영역 안쪽(가운데에서 0.3 × 한 변)에 없으면, 그 물가가 가운데에서 0.3 × 한 변 떨어진 자리에 오게 가운데를 옮긴다 (-EcoR10DemoAt 이면 옮기지 않음)
	if (!S.bHasAt)
	{
		const FVector2D C0(S.Center.X, S.Center.Y);
		double BestD = 200000.0;
		FVector2D BestP = C0;
		for (TActorIterator<AActor> It(World); It; ++It)
		{
			const FString Cls = It->GetClass()->GetName();
			if (!Cls.StartsWith(TEXT("WaterBody")) || Cls.Contains(TEXT("Ocean")))
			{
				continue;
			}
			const FBox B = It->GetComponentsBoundingBox(/*bNonColliding*/ true);
			if (!B.IsValid)
			{
				continue;
			}
			const FVector2D P(FMath::Clamp(C0.X, B.Min.X, B.Max.X), FMath::Clamp(C0.Y, B.Min.Y, B.Max.Y));
			const double D = FVector2D::Distance(P, C0);
			if (D < BestD)
			{
				BestD = D;
				BestP = P;
			}
		}
		const double Keep = 0.3 * S.AreaM * 100.0;
		if (BestD < 200000.0 && BestD > Keep)
		{
			const FVector2D Dir = (C0 - BestP).GetSafeNormal();
			const FVector2D NewC = BestP + Dir * Keep;
			UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 물이 영역 밖이라 가운데를 옮김: (%.0f, %.0f) → (%.0f, %.0f) m (가장 가까운 호수·강 %.0f m)"), C0.X / 100.0,
				   C0.Y / 100.0, NewC.X / 100.0, NewC.Y / 100.0, BestD / 100.0);
			S.Center = FVector(NewC.X, NewC.Y, S.Center.Z);
			S.CenterLabel += TEXT(" → 물가 쪽");
		}
	}
	const double CellCm = S.CellM * 100.0;
	const int32 N1 = FMath::Max(16, FMath::RoundToInt32(S.AreaM / S.CellM));
	const double HalfCm = 0.5 * N1 * CellCm;
	S.X0 = S.Center.X - HalfCm;
	S.Y0 = S.Center.Y - HalfCm;
	const int32 W = N1, H = N1;
	const int32 N = W * H;
	auto CellX = [&S, CellCm](int32 x) { return S.X0 + (x + 0.5) * CellCm; };
	auto CellY = [&S, CellCm](int32 y) { return S.Y0 + (y + 0.5) * CellCm; };
	TArray<double> Gz;
	Gz.Init(std::numeric_limits<double>::quiet_NaN(), N);
	FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoR10DemoGround), false);
	for (const TPair<int64, FEcoR10Body>& P : S.Bodies)
	{
		if (const AActor* A = P.Value.Rep.Get())
		{
			Params.AddIgnoredActor(A);
		}
	}
	const FCollisionObjectQueryParams Objects(ECC_WorldStatic);
	int32 FromLand = 0, FromTrace = 0;
	for (int32 y = 0; y < H; ++y)
	{
		for (int32 x = 0; x < W; ++x)
		{
			const double X = CellX(x), Y = CellY(y);
			const double L = GroundCm(X, Y, std::numeric_limits<double>::quiet_NaN());
			if (FMath::IsFinite(L))
			{
				Gz[y * W + x] = L;
				++FromLand;
				continue;
			}
			if (S.Lands.IsEmpty())
			{
				FHitResult Hit;
				if (World->LineTraceSingleByObjectType(Hit, FVector(X, Y, 200000.0), FVector(X, Y, -200000.0), Objects, Params))
				{
					Gz[y * W + x] = Hit.ImpactPoint.Z;
					++FromTrace;
				}
			}
		}
	}
	const int32 NoGround = N - FromLand - FromTrace;
	if (NoGround > N / 5 && !bLastTry)
	{
		OutError = FString::Printf(TEXT("땅 못 찾은 칸 %d / %d — 지형이 아직 다 안 불림 (다시 훑음)"), NoGround, N);
		return false;
	}
	// 기준 높이 = 땅 높이 가운데값 (코어 높이가 학습 맵처럼 0 둘레가 되게)
	{
		TArray<double> V;
		for (double Z : Gz)
		{
			if (FMath::IsFinite(Z))
			{
				V.Add(Z);
			}
		}
		V.Sort();
		S.Z0 = V.IsEmpty() ? S.Center.Z : V[V.Num() / 2];
	}
	EcoR10Demo::FR10Scan Sc;
	Sc.W = W;
	Sc.H = H;
	Sc.CellM = S.CellM;
	Sc.Ground.assign(static_cast<size_t>(N), std::numeric_limits<float>::quiet_NaN());
	Sc.WaterSurf.assign(static_cast<size_t>(N), std::numeric_limits<float>::quiet_NaN());
	Sc.Block.assign(static_cast<size_t>(N), 0);
	Sc.Canopy.assign(static_cast<size_t>(N), 0);
	Sc.Rock.assign(static_cast<size_t>(N), 0);
	Sc.Bush.assign(static_cast<size_t>(N), 0.0f);
	for (int32 k = 0; k < N; ++k)
	{
		if (FMath::IsFinite(Gz[k]))
		{
			Sc.Ground[static_cast<size_t>(k)] = static_cast<float>((Gz[k] - S.Z0) / 100.0);
		}
	}
	// 물: 바다 = 수면 높이 (WaterBodyOcean 액터 Z), 호수·강 = 그 물 몸체 충돌 선 검사 (R9 데모 훑기와 같은 꼴)
	const FBox Area(FVector(S.X0, S.Y0, -1e7), FVector(S.X0 + W * CellCm, S.Y0 + H * CellCm, 1e7));
	auto Over2D = [&Area](const FBox& B)
	{ return B.IsValid && B.Max.X >= Area.Min.X && B.Min.X <= Area.Max.X && B.Max.Y >= Area.Min.Y && B.Min.Y <= Area.Max.Y; };
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
	int32 WaterCells = 0;
	if (FMath::IsFinite(OceanZ))
	{
		for (int32 k = 0; k < N; ++k)
		{
			if (FMath::IsFinite(Gz[k]) && Gz[k] < OceanZ - 5.0)
			{
				Sc.WaterSurf[static_cast<size_t>(k)] = static_cast<float>((OceanZ - S.Z0) / 100.0);
				++WaterCells;
			}
		}
	}
	FCollisionQueryParams WaterParams(SCENE_QUERY_STAT(EcoR10DemoWater), true);
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
		if (Hits.IsEmpty() || !Over2D(Box))
		{
			continue;
		}
		const int32 Ix0 = FMath::Max(0, FMath::FloorToInt32((Box.Min.X - S.X0) / CellCm));
		const int32 Iy0 = FMath::Max(0, FMath::FloorToInt32((Box.Min.Y - S.Y0) / CellCm));
		const int32 Ix1 = FMath::Min(W - 1, FMath::FloorToInt32((Box.Max.X - S.X0) / CellCm));
		const int32 Iy1 = FMath::Min(H - 1, FMath::FloorToInt32((Box.Max.Y - S.Y0) / CellCm));
		for (int32 y = Iy0; y <= Iy1; ++y)
		{
			for (int32 x = Ix0; x <= Ix1; ++x)
			{
				const double G = Gz[y * W + x];
				if (!FMath::IsFinite(G))
				{
					continue;
				}
				const FVector Start(CellX(x), CellY(y), Box.Max.Z + 100.0);
				const FVector End(CellX(x), CellY(y), FMath::Min(Box.Min.Z, G) - 100.0);
				double Surface = -std::numeric_limits<double>::infinity();
				for (UPrimitiveComponent* C : Hits)
				{
					FHitResult Hit;
					if (C->LineTraceComponent(Hit, Start, End, WaterParams))
					{
						Surface = FMath::Max(Surface, Hit.ImpactPoint.Z);
					}
				}
				if (FMath::IsFinite(Surface) && G < Surface - 5.0)
				{
					float& Sf = Sc.WaterSurf[static_cast<size_t>(y * W + x)];
					if (!FMath::IsFinite(Sf))
					{
						++WaterCells;
					}
					Sf = FMath::IsFinite(Sf) ? FMath::Max(Sf, static_cast<float>((Surface - S.Z0) / 100.0)) : static_cast<float>((Surface - S.Z0) / 100.0);
				}
			}
		}
	}
	// 나무·바위·건물·덤불 (정적·인스턴스 메시 경계 상자)
	int32 Trees = 0, Rocks = 0, Bushes = 0, Buildings = 0;
	auto MarkBox = [&](const FBox& B, double PadCm, auto&& Fn)
	{
		const int32 Ix0 = FMath::Max(0, FMath::FloorToInt32((B.Min.X - PadCm - S.X0) / CellCm));
		const int32 Iy0 = FMath::Max(0, FMath::FloorToInt32((B.Min.Y - PadCm - S.Y0) / CellCm));
		const int32 Ix1 = FMath::Min(W - 1, FMath::FloorToInt32((B.Max.X + PadCm - S.X0) / CellCm));
		const int32 Iy1 = FMath::Min(H - 1, FMath::FloorToInt32((B.Max.Y + PadCm - S.Y0) / CellCm));
		for (int32 y = Iy0; y <= Iy1; ++y)
		{
			for (int32 x = Ix0; x <= Ix1; ++x)
			{
				Fn(y * W + x, x, y);
			}
		}
	};
	auto MarkDisc = [&](double Cx, double Cy, double RCm, auto&& Fn)
	{
		const FBox B(FVector(Cx - RCm, Cy - RCm, 0), FVector(Cx + RCm, Cy + RCm, 0));
		MarkBox(B, 0.0, [&](int32 k, int32 x, int32 y)
				{
					if (FMath::Square(CellX(x) - Cx) + FMath::Square(CellY(y) - Cy) <= RCm * RCm + 0.25 * CellCm * CellCm)
					{
						Fn(k);
					}
				});
	};
	auto Above = [&Gz](int32 k, double Z) { return !FMath::IsFinite(Gz[k]) || Z > Gz[k] + 50.0; };
	auto HandleBox = [&](const FString& MeshLower, const FBox& B, const FVector& Loc, bool bIsm)
	{
		const FVector Size = B.GetSize();
		const double Wd = FMath::Max(Size.X, Size.Y);
		if (Wd < 40.0 || Size.Z < 30.0 || !Over2D(B))
		{
			return;
		}
		if (AnyWord(MeshLower, {TEXT("pine"), TEXT("tree"), TEXT("spruce"), TEXT("birch"), TEXT("beech"), TEXT("oak"), TEXT("fir"), TEXT("palm"),
								TEXT("cactus"), TEXT("maple"), TEXT("cedar"), TEXT("willow")}))
		{
			if (Size.Z < 250.0)
			{
				// 작은 나무 = 덤불처럼 가림
				MarkDisc(Loc.X, Loc.Y, FMath::Max(60.0, 0.35 * Wd), [&](int32 k) { Sc.Bush[static_cast<size_t>(k)] = FMath::Min(1.0f, Sc.Bush[static_cast<size_t>(k)] + 0.5f); });
				++Bushes;
				return;
			}
			MarkDisc(Loc.X, Loc.Y, 45.0, [&](int32 k) { Sc.Block[static_cast<size_t>(k)] = 1; });   // 줄기 (반지름 0.45 m)
			MarkDisc(Loc.X, Loc.Y, FMath::Clamp(0.4 * Wd, 150.0, 600.0), [&](int32 k) { Sc.Canopy[static_cast<size_t>(k)] = 1; });
			Sc.Anchor.push_back((Loc.X - S.X0) / 100.0);
			Sc.Anchor.push_back((Loc.Y - S.Y0) / 100.0);
			++Trees;
			return;
		}
		if (AnyWord(MeshLower, {TEXT("bush"), TEXT("shrub"), TEXT("fern"), TEXT("hedge"), TEXT("reed")}))
		{
			MarkDisc(B.GetCenter().X, B.GetCenter().Y, FMath::Max(60.0, 0.45 * Wd), [&](int32 k) { Sc.Bush[static_cast<size_t>(k)] = FMath::Min(1.0f, Sc.Bush[static_cast<size_t>(k)] + 0.6f); });
			++Bushes;
			return;
		}
		if (AnyWord(MeshLower, {TEXT("grass"), TEXT("flower"), TEXT("clover"), TEXT("weed"), TEXT("decal"), TEXT("pebble"), TEXT("snow"), TEXT("leaf"), TEXT("moss")}))
		{
			return;
		}
		if (Wd > 20000.0)
		{
			return;   // 바닥 조각·하늘 따위
		}
		const bool bRock = AnyWord(MeshLower, {TEXT("rock"), TEXT("cliff"), TEXT("boulder"), TEXT("stone")});
		// 땅보다 50 cm 넘게 솟은 칸만 막음 (넓은 바닥 메시는 땅이라 막지 않음)
		const FBox Core = B.ExpandBy(FVector(-0.15 * Size.X, -0.15 * Size.Y, 0.0));
		MarkBox(Core, 0.0, [&](int32 k, int32, int32)
				{
					if (Above(k, B.Max.Z))
					{
						Sc.Block[static_cast<size_t>(k)] = 1;
						if (bRock)
						{
							Sc.Rock[static_cast<size_t>(k)] = 1;
						}
					}
				});
		if (bRock)
		{
			++Rocks;
			if (Wd >= 200.0)
			{
				Sc.Anchor.push_back((B.GetCenter().X - S.X0) / 100.0);
				Sc.Anchor.push_back((B.GetCenter().Y - S.Y0) / 100.0);
			}
		}
		else if (!bIsm)
		{
			++Buildings;
		}
	};
	for (TActorIterator<AActor> It(World); It; ++It)
	{
		AActor* A = *It;
		if (!A || SpawnedActors.Contains(A) || A->IsA<AEcoCreatureRepresentationActor>())
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
			if (!Mesh || !Comp->IsRegistered() || !Comp->IsVisible() || !Over2D(Comp->Bounds.GetBox()))
			{
				continue;
			}
			const FString MeshLower = Mesh->GetName().ToLower();
			if (const UInstancedStaticMeshComponent* Ism = Cast<UInstancedStaticMeshComponent>(Comp))
			{
				if (AnyWord(MeshLower, {TEXT("grass"), TEXT("flower"), TEXT("clover"), TEXT("weed"), TEXT("decal"), TEXT("pebble"), TEXT("leaf"), TEXT("moss")}))
				{
					continue;
				}
				const FBox MeshBox = Mesh->GetBoundingBox();
				const int32 Count = Ism->GetInstanceCount();
				for (int32 i = 0; i < Count; ++i)
				{
					FTransform T;
					if (Ism->GetInstanceTransform(i, T, /*bWorldSpace*/ true))
					{
						const FBox B = MeshBox.TransformBy(T);
						if (Over2D(B))
						{
							HandleBox(MeshLower, B, T.GetLocation(), true);
						}
					}
				}
			}
			else
			{
				HandleBox(MeshLower, Comp->Bounds.GetBox(), Comp->GetComponentLocation(), false);
			}
		}
	}
	EcoR10Demo::FR10MapCounts Counts;
	EcoR10::FMapLayers Layers;
	std::string Err;
	if (!EcoR10Demo::BuildLayers(Sc, S.Seed, 4.0, Layers, Counts, &Err))
	{
		OutError = FString::Printf(TEXT("지형 층 만들기 실패: %s"), UTF8_TO_TCHAR(Err.c_str()));
		return false;
	}
	// 세계
	EcoR10::FWorldConfig Cfg;
	Cfg.Map = std::move(Layers);
	Cfg.Species = S.Species;
	Cfg.Seed = S.Seed;
	Cfg.Respawn = true;
	for (int32 k = 0; k < static_cast<int32>(S.Species.size()); ++k)
	{
		EcoR10::FRosterEntry E;
		E.Species = k;
		E.Start = S.Start;
		E.Cap = S.Cap;
		Cfg.Roster.push_back(E);
	}
	if (!S.World.Init(Cfg, &Err))
	{
		OutError = FString::Printf(TEXT("R10 세계 시작 실패: %s"), UTF8_TO_TCHAR(Err.c_str()));
		return false;
	}
	const int32 NSlot = S.World.NumSlots();
	S.Obs.assign(static_cast<size_t>(NSlot) * EcoR10::kObsDim, 0.0f);
	S.Actions.assign(static_cast<size_t>(NSlot), EcoR10::ActWatch);
	S.PX = S.World.X;
	S.PY = S.World.Y;
	S.PZ = S.World.Z;
	S.PHx = S.World.Hx;
	S.PHy = S.World.Hy;
	S.PUid = S.World.Uid;
	S.PAlive = S.World.Alive;
	const int32 NS = static_cast<int32>(S.Species.size());
	S.Births.Init(0, NS);
	S.Bites.Init(0, NS);
	for (TArray<int32>& D : S.DeathBy)
	{
		D.Init(0, NS);
	}
	double FoodSum = 0.0;
	for (double F : Counts.FoodCapSum)
	{
		FoodSum += F;
	}
	S.MapLine = FString::Printf(TEXT("영역 %d m (%d×%d 칸, %.1f m) 가운데 %s (%.0f, %.0f m) · 땅 %d(지형 %d·선 %d)·없음 %d · 물 %d 칸 · 나무 %d · 바위 %d · 덤불 %d · 건물 %d · ")
									TEXT("막힘 %d · 갓 %d · 은신처 %d (%d 칸) · 먹이 용량 합 %.0f (풍부 %.2f) · 훑기 %.2f 초"),
								S.AreaM, W, H, S.CellM, *S.CenterLabel, S.Center.X / 100.0, S.Center.Y / 100.0, FromLand + FromTrace, FromLand, FromTrace, NoGround,
								WaterCells, Trees, Rocks, Bushes, Buildings, Counts.Blocked, Counts.Canopy, Counts.Shelters, Counts.ShelterCells, FoodSum,
								Counts.Abundance, FPlatformTime::Seconds() - T0);
	UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] %s"), *S.MapLine);
	TArray<FString> Per;
	for (int32 k = 0; k < NS; ++k)
	{
		int32 Alive = 0;
		for (int32 i = 0; i < NSlot; ++i)
		{
			Alive += (S.World.Alive[static_cast<size_t>(i)] && S.World.Sp[static_cast<size_t>(i)] == k) ? 1 : 0;
		}
		Per.Add(FString::Printf(TEXT("%s %d"), UTF8_TO_TCHAR(S.Species[static_cast<size_t>(k)].Id.c_str()), Alive));
	}
	UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 처음 개체 (슬롯 %d): %s"), NSlot, *FString::Join(Per, TEXT(" · ")));
	return true;
}

// -----------------------------------------------------------------------------
// 한 결정
// -----------------------------------------------------------------------------

void UEcoR10DemoSubsystem::StepSim()
{
	FEcoR10DemoState& S = *State;
	EcoR10::FWorld& Wd = S.World;
	S.PX = Wd.X;
	S.PY = Wd.Y;
	S.PZ = Wd.Z;
	S.PHx = Wd.Hx;
	S.PHy = Wd.Hy;
	S.PUid = Wd.Uid;
	S.PAlive = Wd.Alive;
	Wd.Observe(S.Obs);
	EcoR10::DecideActions(Wd, S.BrainBySpecies, S.Obs, S.Seed, Wd.Decisions, S.Actions);   // 결정 번호 = 코어 Decisions (개체마다 시드 U)
	Wd.Step(S.Actions.data());
	++S.Decisions;
	const double Now = GetWorld()->GetTimeSeconds();
	const int32 NS = static_cast<int32>(S.Species.size());
	for (const EcoR10::FEvent& E : Wd.Events)
	{
		const int32 A = E.A;
		if (A < 0 || A >= Wd.NumSlots())
		{
			continue;
		}
		const int32 Sp = Wd.Sp[static_cast<size_t>(A)];
		if (Sp < 0 || Sp >= NS)
		{
			continue;
		}
		if (E.Kind == EcoR10::EvDeath)
		{
			// 원인 (EcoR10::ECause): 1 물림 → 칸 1 · 3 굶음 → 칸 2 · 4 물 밖·숨 → 칸 3 · 반격(2)·상처(5) → 칸 0 (그 밖)
			const int32 C = E.Cause == EcoR10::CauseBitten ? 1 : E.Cause == EcoR10::CauseStarved ? 2 : E.Cause == EcoR10::CauseOutOfWater ? 3 : 0;
			++S.DeathBy[C][Sp];
			const int64 Uid = E.UidA > 0 ? E.UidA : S.PUid[static_cast<size_t>(A)];
			if (FEcoR10Body* B = S.Bodies.Find(Uid))
			{
				if (!B->bDead)
				{
					B->bDead = true;
					B->DeadAt = Now;
					B->RemoveAt = Now + 20.0;
					B->Corpse = BodyLocation(A, 1.0);
					if (const AActor* Body = B->Rep.IsValid() ? static_cast<const AActor*>(B->Rep.Get()) : B->Ball.Get())
					{
						B->Corpse = Body->GetActorLocation();
						B->CorpseYaw = Body->GetActorRotation().Yaw;
					}
				}
			}
		}
		else if (E.Kind == EcoR10::EvBirth)
		{
			S.Births[Sp] += FMath::Max(1, E.B);   // 태어남: A 어미 칸 · B 새끼 수
		}
		else if (E.Kind == EcoR10::EvBite)
		{
			++S.Bites[Sp];
			if (FEcoR10Body* B = S.Bodies.Find(E.UidA > 0 ? E.UidA : Wd.Uid[static_cast<size_t>(A)]))
			{
				B->AttackUntil = Now + 0.6;
			}
		}
	}
}

FVector UEcoR10DemoSubsystem::BodyLocation(int32 i, double Alpha) const
{
	const FEcoR10DemoState& S = *State;
	const EcoR10::FWorld& Wd = S.World;
	const size_t k = static_cast<size_t>(i);
	const bool bPrev = S.PUid.size() > k && S.PUid[k] == Wd.Uid[k] && S.PAlive[k];
	const double Cx = bPrev ? FMath::Lerp(S.PX[k], Wd.X[k], Alpha) : Wd.X[k];
	const double Cy = bPrev ? FMath::Lerp(S.PY[k], Wd.Y[k], Alpha) : Wd.Y[k];
	const double Cz = bPrev ? FMath::Lerp(S.PZ[k], Wd.Z[k], Alpha) : Wd.Z[k];
	const double X = S.X0 + Cx * 100.0, Y = S.Y0 + Cy * 100.0;
	const double CoreGround = S.Z0 + (Wd.DisplayZ(i) - (Wd.Airborne[k] ? Wd.Z[k] : 0.0)) * 100.0;
	if (Wd.Swimming[k])
	{
		return FVector(X, Y, S.Z0 + Cz * 100.0);
	}
	const double G = GroundCm(X, Y, CoreGround);
	if (Wd.Airborne[k])
	{
		return FVector(X, Y, G + Cz * 100.0);
	}
	return FVector(X, Y, G);
}

// -----------------------------------------------------------------------------
// 틱
// -----------------------------------------------------------------------------

void UEcoR10DemoSubsystem::Tick(float DeltaTime)
{
	Super::Tick(DeltaTime);
	if (!State)
	{
		return;
	}
	FEcoR10DemoState& S = *State;
	UWorld* World = GetWorld();
	if (!World || S.Phase == FEcoR10DemoState::EPhase::Off || S.Phase == FEcoR10DemoState::EPhase::Failed)
	{
		return;
	}
	const double Now = World->GetTimeSeconds();
	if (S.QuitCountdown > 0 && --S.QuitCountdown == 0)
	{
		FPlatformMisc::RequestExit(false, TEXT("EcoR10Demo"));
		return;
	}
	if (S.Phase == FEcoR10DemoState::EPhase::Waiting)
	{
		if (Now < S.NextScanAt)
		{
			return;
		}
		++S.ScanTries;
		const bool bLast = S.ScanTries >= 10;
		FString Err;
		if (!ScanAndBuild(Err, bLast))
		{
			if (bLast)
			{
				Fail(Err);
			}
			else
			{
				UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 훑기 %d 번째: %s"), S.ScanTries, *Err);
				S.NextScanAt = Now + 3.0;
			}
			return;
		}
		S.Phase = FEcoR10DemoState::EPhase::Running;
		S.RunningSince = Now;
		S.NextLogAt = 30.0;
		S.Acc = 0.0;
		S.NextCycleAt = Now + FMath::Max(1.0f, S.CamCycle);
		PickSubject(-1, 1);
		return;
	}
	// 돌기
	const float Speed = FMath::Clamp(EcoR10DemoImpl::CVarSpeed.GetValueOnGameThread(), 0.0f, 20.0f);
	S.Acc += FMath::Min(DeltaTime, 0.25f) * Speed;
	int32 Steps = 0;
	while (S.Acc >= EcoR10DemoImpl::kDecisionS && Steps < 6)
	{
		StepSim();
		S.Acc -= EcoR10DemoImpl::kDecisionS;
		++Steps;
	}
	if (S.Acc >= EcoR10DemoImpl::kDecisionS)
	{
		S.Acc = 0.0;   // 너무 밀렸으면 버림 (화면이 따라가게)
	}
	const double Alpha = FMath::Clamp(S.Acc / EcoR10DemoImpl::kDecisionS, 0.0, 1.0);
	SyncBodies(Alpha, DeltaTime);
	if (Now >= S.NextHideAt && EcoR10DemoImpl::CVarHide.GetValueOnGameThread() != 0)
	{
		HideOthers();
		S.NextHideAt = Now + 2.0;
	}
	HandleKeys();
	if (S.CamCycle > 0.0f && Now >= S.NextCycleAt)
	{
		S.NextCycleAt = Now + S.CamCycle;
		PickSubject(S.CamSpecies, 1);
	}
	UpdateCamera(DeltaTime);
	TickCapture(DeltaTime);
	if (S.ExitAfter > 0.0f && Now - S.RunningSince >= S.ExitAfter && S.QuitCountdown < 0)
	{
		LogSummary(TEXT("끝냄 (-EcoR10ExitAfter)"));
		S.QuitCountdown = 3;
	}
	if (Now - S.RunningSince >= S.NextLogAt)
	{
		S.NextLogAt += 30.0;
		LogSummary(TEXT("30 초마다"));
	}
}

void UEcoR10DemoSubsystem::LogSummary(const TCHAR* Tag)
{
	FEcoR10DemoState& S = *State;
	const EcoR10::FWorld& Wd = S.World;
	const int32 NS = static_cast<int32>(S.Species.size());
	TArray<FString> Parts;
	int32 Total = 0;
	for (int32 k = 0; k < NS; ++k)
	{
		int32 Alive = 0;
		for (int32 i = 0; i < Wd.NumSlots(); ++i)
		{
			Alive += (Wd.Alive[static_cast<size_t>(i)] && Wd.Sp[static_cast<size_t>(i)] == k) ? 1 : 0;
		}
		Total += Alive;
		Parts.Add(FString::Printf(TEXT("%s %d(물림 %d·굶음 %d·물 %d·기타 %d·물기 %d·남 %d)"), UTF8_TO_TCHAR(S.Species[static_cast<size_t>(k)].Id.c_str()), Alive,
								  S.DeathBy[1][k], S.DeathBy[2][k], S.DeathBy[3][k], S.DeathBy[0][k], S.Bites[k], S.Births[k]));
	}
	int32 Reps = 0, Balls = 0;
	for (const TPair<int64, FEcoR10Body>& P : S.Bodies)
	{
		Reps += P.Value.Rep.IsValid() ? 1 : 0;
		Balls += P.Value.Ball.IsValid() ? 1 : 0;
	}
	UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] %s — 결정 %lld · 시뮬 %.0f 초 · 산 %d (종 %d) · 몸 BP %d · 공 %d · %s"), Tag, S.Decisions,
		   S.Decisions * EcoR10DemoImpl::kDecisionS, Total, NS, Reps, Balls, *FString::Join(Parts, TEXT(" · ")));
}

// -----------------------------------------------------------------------------
// 몸
// -----------------------------------------------------------------------------

void UEcoR10DemoSubsystem::SyncBodies(double Alpha, float DeltaTime)
{
	using namespace EcoR10DemoImpl;
	FEcoR10DemoState& S = *State;
	EcoR10::FWorld& Wd = S.World;
	UWorld* World = GetWorld();
	const double Now = World->GetTimeSeconds();
	const int32 NSlot = Wd.NumSlots();
	for (TPair<int64, FEcoR10Body>& P : S.Bodies)
	{
		P.Value.bSeen = false;
	}
	for (int32 i = 0; i < NSlot; ++i)
	{
		const size_t k = static_cast<size_t>(i);
		if (!Wd.Alive[k] || Wd.Uid[k] <= 0)
		{
			continue;
		}
		const int64 Uid = Wd.Uid[k];
		const int32 Sp = Wd.Sp[k];
		if (Sp < 0 || Sp >= SpeciesClasses.Num())
		{
			continue;
		}
		const FVector Pos = BodyLocation(i, Alpha);
		const bool bPrev = S.PUid[k] == Uid && S.PAlive[k];
		const double Yaw1 = FMath::RadiansToDegrees(FMath::Atan2(Wd.Hy[k], Wd.Hx[k]));
		const double Yaw0 = bPrev ? FMath::RadiansToDegrees(FMath::Atan2(S.PHy[k], S.PHx[k])) : Yaw1;
		const double Yaw = Yaw0 + FMath::FindDeltaAngleDegrees(Yaw0, Yaw1) * Alpha;
		FEcoR10Body* B = S.Bodies.Find(Uid);
		if (!B)
		{
			FEcoR10Body NB;
			NB.Species = Sp;
			FActorSpawnParameters SP;
			SP.ObjectFlags |= RF_Transient;
			SP.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			if (UClass* Cls = SpeciesClasses[Sp])
			{
				SP.Name = MakeUniqueObjectName(World->PersistentLevel, Cls, *FString::Printf(TEXT("EcoR10_%s_%lld"), UTF8_TO_TCHAR(S.Species[static_cast<size_t>(Sp)].Id.c_str()), Uid));
				AEcoCreatureRepresentationActor* Rep = World->SpawnActor<AEcoCreatureRepresentationActor>(Cls, FTransform(FRotator(0.0, Yaw, 0.0), Pos), SP);
				if (Rep)
				{
					Rep->SetReplicates(false);
					if (Rep->BindIdentity(kStableBase + Uid, Rep->VisualSpeciesId))
					{
						if (Rep->IdentityLabel)
						{
							Rep->IdentityLabel->SetHiddenInGame(true);
						}
						NB.Rep = Rep;
					}
					else
					{
						Rep->Destroy();
					}
				}
			}
			if (!NB.Rep.IsValid() && SphereMesh)
			{
				AActor* Ball = World->SpawnActor<AActor>(AActor::StaticClass(), FTransform(Pos), SP);
				if (Ball)
				{
					UStaticMeshComponent* M = NewObject<UStaticMeshComponent>(Ball, TEXT("Body"));
					M->SetStaticMesh(SphereMesh);
					M->SetCollisionEnabled(ECollisionEnabled::NoCollision);
					M->SetWorldScale3D(FVector(0.6));
					Ball->SetRootComponent(M);
					M->RegisterComponent();
					if (BasicMaterial)
					{
						UMaterialInstanceDynamic* Mid = UMaterialInstanceDynamic::Create(BasicMaterial, M);
						const FVis* V = FindVis(S.Species[static_cast<size_t>(Sp)].Id);
						Mid->SetVectorParameterValue(TEXT("Color"), FLinearColor(V ? V->Color : FColor::Magenta));
						M->SetMaterial(0, Mid);
					}
					Ball->SetActorLocation(Pos);
					NB.Ball = Ball;
				}
			}
			B = &S.Bodies.Add(Uid, NB);
		}
		B->bSeen = true;
		if (B->bDead)
		{
			continue;
		}
		// 속도 (cm/s)
		FVector Vel = FVector::ZeroVector;
		if (bPrev)
		{
			Vel = FVector((Wd.X[k] - S.PX[k]) * 100.0, (Wd.Y[k] - S.PY[k]) * 100.0, (Wd.Z[k] - S.PZ[k]) * 100.0) / kDecisionS;
			if (!Wd.Airborne[k] && !Wd.Swimming[k])
			{
				Vel.Z = 0.0;
			}
		}
		const int32 A = Wd.Action[k];
		const FVis* V = FindVis(S.Species[static_cast<size_t>(Sp)].Id);
		EEcoSpeciesActivity Act = EEcoSpeciesActivity::Vigilant;
		if (Now < B->AttackUntil)
		{
			Act = EEcoSpeciesActivity::Attack;
		}
		else if (Wd.Airborne[k])
		{
			Act = A == EcoR10::ActDown ? EEcoSpeciesActivity::Land : EEcoSpeciesActivity::Fly;
		}
		else if (Wd.Swimming[k])
		{
			Act = EEcoSpeciesActivity::Swim;
		}
		else if (A == EcoR10::ActEat)
		{
			Act = (V && V->bMeat) ? EEcoSpeciesActivity::Eat : EEcoSpeciesActivity::Graze;
		}
		else if (A == EcoR10::ActBurst)
		{
			Act = EEcoSpeciesActivity::Pounce;
		}
		else if (A >= EcoR10::ActFast0 && A < EcoR10::ActFast0 + 8)
		{
			Act = EEcoSpeciesActivity::Travel;
		}
		else if (A >= EcoR10::ActSlow0 && A < EcoR10::ActSlow0 + 8)
		{
			Act = EEcoSpeciesActivity::Wander;
		}
		else if (A == EcoR10::ActHide)
		{
			Act = EEcoSpeciesActivity::ShelterHold;
		}
		else if (A == EcoR10::ActUp)
		{
			Act = EEcoSpeciesActivity::Takeoff;
		}
		if (AEcoCreatureRepresentationActor* Rep = B->Rep.Get())
		{
			FEcoCreatureVisualState Vs;
			Vs.StableAgentId = kStableBase + Uid;
			Vs.SpeciesId = Rep->VisualSpeciesId;
			Vs.RegionId = kRegion;
			Vs.Sequence = ++B->Sequence;
			Vs.WorldTime = Now;
			Vs.Position = Pos;
			Vs.Velocity = Vel;
			Vs.bAlive = true;
			Vs.BodyScale = 1.0f;
			Vs.Maturity = 1.0f;
			Vs.CoatTone = 0.5f;
			const float Hp = static_cast<float>(FMath::Clamp(Wd.Hp[k], 0.0, 1.0));
			Vs.bHasVitals = Hp < 0.999f;
			Vs.NormalizedHealth = Hp;
			Vs.NormalizedEnergy = static_cast<float>(FMath::Clamp(Wd.E[k], 0.0, 1.0));
			Vs.bEating = A == EcoR10::ActEat;
			Vs.bPursuingPrey = A == EcoR10::ActBurst;
			Vs.Activity = Act;
			Vs.FocusYawDegrees = static_cast<float>(Yaw);
			Vs.bDiscontinuity = B->bSnap;
			B->bSnap = false;
			Rep->ConsumeVisualState(Vs, DeltaTime);
		}
		else if (AActor* Ball = B->Ball.Get())
		{
			Ball->SetActorLocationAndRotation(Pos + FVector(0, 0, 30.0), FRotator(0.0, Yaw, 0.0));
		}
	}
	// 죽은 몸 (사체로 잠깐) · 사라진 몸
	TArray<int64> Gone;
	for (TPair<int64, FEcoR10Body>& P : S.Bodies)
	{
		FEcoR10Body& B = P.Value;
		if (B.bDead)
		{
			if (Now >= B.RemoveAt)
			{
				Gone.Add(P.Key);
				continue;
			}
			if (AEcoCreatureRepresentationActor* Rep = B.Rep.Get())
			{
				FEcoCreatureVisualState Vs;
				Vs.StableAgentId = kStableBase + P.Key;
				Vs.SpeciesId = Rep->VisualSpeciesId;
				Vs.RegionId = kRegion;
				Vs.Sequence = ++B.Sequence;
				Vs.WorldTime = Now;
				Vs.Position = B.Corpse;
				Vs.bAlive = false;
				Vs.Activity = Now - B.DeadAt > 1.5 ? EEcoSpeciesActivity::CorpseSettled : EEcoSpeciesActivity::Hold;
				Vs.FocusYawDegrees = B.CorpseYaw;
				Rep->ConsumeVisualState(Vs, DeltaTime);
			}
			else if (AActor* Ball = B.Ball.Get())
			{
				Ball->SetActorScale3D(FVector(0.6, 0.6, 0.2));
			}
			continue;
		}
		if (!B.bSeen)
		{
			Gone.Add(P.Key);   // 죽음 사건 없이 사라짐 (다시 남 자리 바뀜 등)
		}
	}
	for (int64 Id : Gone)
	{
		if (FEcoR10Body* B = S.Bodies.Find(Id))
		{
			if (AActor* A = B->Rep.Get())
			{
				A->Destroy();
			}
			if (AActor* A = B->Ball.Get())
			{
				A->Destroy();
			}
		}
		S.Bodies.Remove(Id);
	}
}

void UEcoR10DemoSubsystem::HideOthers()
{
	FEcoR10DemoState& S = *State;
	TSet<const AActor*> Mine;
	for (const TPair<int64, FEcoR10Body>& P : S.Bodies)
	{
		if (const AActor* A = P.Value.Rep.Get())
		{
			Mine.Add(A);
		}
	}
	for (TActorIterator<AEcoCreatureRepresentationActor> It(GetWorld()); It; ++It)
	{
		if (!Mine.Contains(*It) && !It->IsHidden())
		{
			It->SetActorHiddenInGame(true);
			S.Hidden.Add(*It);
		}
	}
}

// -----------------------------------------------------------------------------
// 카메라·키
// -----------------------------------------------------------------------------

void UEcoR10DemoSubsystem::PickSubject(int32 Species, int32 Dir)
{
	FEcoR10DemoState& S = *State;
	const EcoR10::FWorld& Wd = S.World;
	const int32 NS = static_cast<int32>(S.Species.size());
	if (NS <= 0)
	{
		return;
	}
	auto AliveOf = [&Wd](int32 Sp)
	{
		TArray<int32> Out;
		for (int32 i = 0; i < Wd.NumSlots(); ++i)
		{
			if (Wd.Alive[static_cast<size_t>(i)] && Wd.Sp[static_cast<size_t>(i)] == Sp)
			{
				Out.Add(i);
			}
		}
		return Out;
	};
	// 종 바꾸기 (Species < 0 이면 지금 종에서 Dir 만큼, 산 개체가 있는 종으로)
	int32 Sp = S.CamSpecies;
	for (int32 t = 0; t < NS; ++t)
	{
		Sp = ((Sp < 0 ? (Dir > 0 ? -1 : 0) : Sp) + (Dir > 0 ? 1 : NS - 1)) % NS;
		if (AliveOf(Sp).Num() > 0)
		{
			break;
		}
	}
	S.CamSpecies = Sp;
	const TArray<int32> L = AliveOf(Sp);
	S.CamUid = L.IsEmpty() ? 0 : Wd.Uid[static_cast<size_t>(L[0])];
	S.bTop = false;
	S.bFree = false;
	S.CamLostAt = -1.0;
	(void)Species;
}

void UEcoR10DemoSubsystem::HandleKeys()
{
	FEcoR10DemoState& S = *State;
	APlayerController* PC = GetWorld()->GetFirstPlayerController();
	if (!PC)
	{
		return;
	}
	const EcoR10::FWorld& Wd = S.World;
	if (PC->WasInputKeyJustPressed(EKeys::N))
	{
		PickSubject(-1, 1);
	}
	if (PC->WasInputKeyJustPressed(EKeys::P))
	{
		PickSubject(-1, -1);
	}
	if (PC->WasInputKeyJustPressed(EKeys::Period) || PC->WasInputKeyJustPressed(EKeys::Comma))
	{
		const int32 Dir = PC->WasInputKeyJustPressed(EKeys::Period) ? 1 : -1;
		TArray<int32> L;
		int32 Cur = -1;
		for (int32 i = 0; i < Wd.NumSlots(); ++i)
		{
			if (Wd.Alive[static_cast<size_t>(i)] && Wd.Sp[static_cast<size_t>(i)] == S.CamSpecies)
			{
				if (Wd.Uid[static_cast<size_t>(i)] == S.CamUid)
				{
					Cur = L.Num();
				}
				L.Add(i);
			}
		}
		if (!L.IsEmpty())
		{
			const int32 Next = ((Cur < 0 ? 0 : Cur) + Dir + L.Num()) % L.Num();
			S.CamUid = Wd.Uid[static_cast<size_t>(L[Next])];
		}
	}
	if (PC->WasInputKeyJustPressed(EKeys::T))
	{
		S.bTop = !S.bTop;
		S.bFree = false;
	}
	if (PC->WasInputKeyJustPressed(EKeys::F))
	{
		S.bFree = !S.bFree;
		if (S.bFree)
		{
			if (APawn* Pawn = PC->GetPawn())
			{
				PC->SetViewTarget(Pawn);
			}
		}
	}
	if (PC->WasInputKeyJustPressed(EKeys::H))
	{
		S.bShowText = !S.bShowText;
	}
	if (PC->WasInputKeyJustPressed(EKeys::Hyphen))
	{
		S.Zoom = FMath::Clamp(S.Zoom * 1.25, 0.3, 6.0);
	}
	if (PC->WasInputKeyJustPressed(EKeys::Equals))
	{
		S.Zoom = FMath::Clamp(S.Zoom / 1.25, 0.3, 6.0);
	}
}

void UEcoR10DemoSubsystem::UpdateCamera(float DeltaTime)
{
	FEcoR10DemoState& S = *State;
	UWorld* World = GetWorld();
	APlayerController* PC = World->GetFirstPlayerController();
	if (S.bFree || !PC)
	{
		return;
	}
	if (!IsValid(Camera))
	{
		FActorSpawnParameters SP;
		SP.ObjectFlags |= RF_Transient;
		Camera = World->SpawnActor<ACameraActor>(ACameraActor::StaticClass(), FTransform::Identity, SP);
		if (!Camera)
		{
			return;
		}
		Camera->GetCameraComponent()->bConstrainAspectRatio = false;
		Camera->GetCameraComponent()->SetFieldOfView(70.0f);
		Camera->GetCameraComponent()->PostProcessSettings.bOverride_MotionBlurAmount = true;   // 대상 바꿀 때 끊어 옮겨 번지지 않게
		Camera->GetCameraComponent()->PostProcessSettings.MotionBlurAmount = 0.0f;
		SpawnedActors.Add(Camera);
	}
	if (PC->GetViewTarget() != Camera)
	{
		PC->SetViewTarget(Camera);
	}
	const EcoR10::FWorld& Wd = S.World;
	const double Now = World->GetTimeSeconds();
	const double Alpha = FMath::Clamp(S.Acc / EcoR10DemoImpl::kDecisionS, 0.0, 1.0);
	FVector Want;
	FRotator Rot;
	if (S.bTop)
	{
		const double Side = S.AreaM * 100.0;
		Want = FVector(S.X0 + 0.5 * Side, S.Y0 + 0.5 * Side, S.Z0 + 0.9 * Side * S.Zoom);
		Rot = FRotator(-89.0, 0.0, 0.0);
		Camera->SetActorLocationAndRotation(Want, Rot);
		return;
	}
	// 대상 따라가기 (죽거나 사라지면 2 초 뒤 같은 종 가까운 개체)
	int32 Slot = -1;
	for (int32 i = 0; i < Wd.NumSlots(); ++i)
	{
		if (Wd.Alive[static_cast<size_t>(i)] && Wd.Uid[static_cast<size_t>(i)] == S.CamUid)
		{
			Slot = i;
			break;
		}
	}
	if (Slot < 0)
	{
		if (S.CamLostAt < 0.0)
		{
			S.CamLostAt = Now;
		}
		if (Now - S.CamLostAt > 2.0)
		{
			double Best = TNumericLimits<double>::Max();
			for (int32 i = 0; i < Wd.NumSlots(); ++i)
			{
				if (Wd.Alive[static_cast<size_t>(i)] && Wd.Sp[static_cast<size_t>(i)] == S.CamSpecies)
				{
					const double D = FVector::DistSquared(BodyLocation(i, Alpha), S.CamFocus);
					if (D < Best)
					{
						Best = D;
						Slot = i;
					}
				}
			}
			if (Slot < 0)
			{
				PickSubject(-1, 1);
				return;
			}
			S.CamUid = Wd.Uid[static_cast<size_t>(Slot)];
			S.CamLostAt = -1.0;
		}
	}
	else
	{
		S.CamLostAt = -1.0;
	}
	const FVector Focus = Slot >= 0 ? BodyLocation(Slot, Alpha) + FVector(0, 0, 60.0) : S.CamFocus;
	const double Blend = 1.0 - FMath::Exp(-6.0 * DeltaTime);
	S.CamFocus = S.CamFocus.IsZero() ? Focus : FMath::Lerp(S.CamFocus, Focus, Blend);
	if (Slot >= 0)
	{
		const double Yaw = FMath::RadiansToDegrees(FMath::Atan2(Wd.Hy[static_cast<size_t>(Slot)], Wd.Hx[static_cast<size_t>(Slot)]));
		S.CamYaw = S.CamYaw + FMath::FindDeltaAngleDegrees(S.CamYaw, Yaw) * (1.0 - FMath::Exp(-1.5 * DeltaTime));
	}
	const double Dist = 900.0 * S.Zoom;
	const FRotator R(-25.0, S.CamYaw + 30.0, 0.0);
	FVector Eye = S.CamFocus - R.Vector() * Dist;
	const double G = GroundCm(Eye.X, Eye.Y, Eye.Z - 1000.0);
	Eye.Z = FMath::Max(Eye.Z, G + 150.0);
	Camera->SetActorLocationAndRotation(Eye, (S.CamFocus - Eye).Rotation());
}

// -----------------------------------------------------------------------------
// 녹화·글
// -----------------------------------------------------------------------------

void UEcoR10DemoSubsystem::TickCapture(float DeltaTime)
{
	FEcoR10DemoState& S = *State;
	if (S.CaptureDir.IsEmpty() || S.bCaptureDone || S.CaptureSeconds <= 0.0f)
	{
		return;
	}
	const double Now = GetWorld()->GetTimeSeconds();
	if (S.CaptureClock < 0.0)
	{
		if (Now - S.RunningSince < 3.0)
		{
			return;
		}
		const int32 Jobs = GShaderCompilingManager ? GShaderCompilingManager->GetNumRemainingJobs() : 0;
		if (Jobs > 0 && Now - S.RunningSince < 90.0)
		{
			if (!S.bShaderWaitLogged)
			{
				UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 녹화 전 셰이더 컴파일 기다림 — 남은 일 %d"), Jobs);
				S.bShaderWaitLogged = true;
			}
			return;
		}
		IStreamingManager::Get().StreamAllResources(5.0f);
		S.CaptureClock = 0.0;
		IFileManager::Get().MakeDirectory(*S.CaptureDir, true);
		UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 녹화 시작 → %s (%.0f fps, %.1f 초)"), *S.CaptureDir, S.CaptureFps, S.CaptureSeconds);
	}
	else
	{
		S.CaptureClock += DeltaTime;
	}
	const int32 Due = FMath::FloorToInt32(S.CaptureClock * S.CaptureFps) + 1;
	if (S.CaptureFrames < Due)
	{
		FScreenshotRequest::RequestScreenshot(FPaths::Combine(S.CaptureDir, FString::Printf(TEXT("f_%05d.png"), S.CaptureFrames)), /*bShowUI*/ true, false);
		++S.CaptureFrames;
	}
	if (S.CaptureClock >= S.CaptureSeconds)
	{
		S.bCaptureDone = true;
		LogSummary(TEXT("녹화 끝"));
		UE_LOG(LogEcoR10Demo, Log, TEXT("[EcoR10Demo] 녹화 끝 — 프레임 %d → %s"), S.CaptureFrames, *S.CaptureDir);
		S.QuitCountdown = 30;
	}
}

void UEcoR10DemoSubsystem::DrawOverlay(UCanvas* Canvas, APlayerController* PC)
{
	if (!State || !Canvas || State->Phase != FEcoR10DemoState::EPhase::Running || !State->bShowText || PC == nullptr || PC->GetWorld() != GetWorld())
	{
		return;
	}
	FEcoR10DemoState& S = *State;
	const EcoR10::FWorld& Wd = S.World;
	UFont* Font = GEngine->GetSmallFont();
	TArray<FString> Lines;
	int32 Total = 0;
	const int32 NS = static_cast<int32>(S.Species.size());
	TArray<int32> Alive;
	Alive.Init(0, NS);
	for (int32 i = 0; i < Wd.NumSlots(); ++i)
	{
		if (Wd.Alive[static_cast<size_t>(i)] && Wd.Sp[static_cast<size_t>(i)] >= 0 && Wd.Sp[static_cast<size_t>(i)] < NS)
		{
			++Alive[Wd.Sp[static_cast<size_t>(i)]];
			++Total;
		}
	}
	Lines.Add(TEXT("R10 — 파이썬에서 배운 두뇌를 언리얼 C++ 로 실시간 추론 (확률 뽑기)"));
	Lines.Add(FString::Printf(TEXT("결정 %lld · %.0f 초 · 산 %d · 영역 %d m"), S.Decisions, S.Decisions * EcoR10DemoImpl::kDecisionS, Total, S.AreaM));
	for (int32 k = 0; k < NS; ++k)
	{
		Lines.Add(FString::Printf(TEXT("%s%s %d  죽음 물림 %d 굶음 %d 물 %d  남 %d"), k == S.CamSpecies ? TEXT("> ") : TEXT("  "),
								  UTF8_TO_TCHAR(S.Species[static_cast<size_t>(k)].Id.c_str()), Alive[k], S.DeathBy[1][k], S.DeathBy[2][k], S.DeathBy[3][k],
								  S.Births[k]));
	}
	for (int32 i = 0; i < Wd.NumSlots(); ++i)
	{
		if (Wd.Alive[static_cast<size_t>(i)] && Wd.Uid[static_cast<size_t>(i)] == S.CamUid)
		{
			Lines.Add(FString::Printf(TEXT("카메라: %s #%lld · %s · 기운 %.2f · 체력 %.2f%s%s"), UTF8_TO_TCHAR(S.Species[static_cast<size_t>(Wd.Sp[static_cast<size_t>(i)])].Id.c_str()),
									  S.CamUid, EcoR10DemoImpl::ActionName(Wd.Action[static_cast<size_t>(i)]), Wd.E[static_cast<size_t>(i)], Wd.Hp[static_cast<size_t>(i)],
									  Wd.Airborne[static_cast<size_t>(i)] ? TEXT(" · 공중") : TEXT(""), Wd.Swimming[static_cast<size_t>(i)] ? TEXT(" · 물속") : TEXT("")));
			break;
		}
	}
	Lines.Add(TEXT("N/P 종 · , . 개체 · T 위에서 · F 자유 · - = 거리 · H 글"));
	const float Scale = FMath::Clamp(Canvas->ClipY / 1080.0f, 0.8f, 2.0f);
	const float LineH = 15.0f * Scale;
	const float BoxW = 430.0f * Scale;
	const float X = Canvas->ClipX - BoxW - 16.0f;
	float Y = 16.0f;
	FCanvasTileItem Bg(FVector2D(X - 8.0f, Y - 6.0f), FVector2D(BoxW + 16.0f, LineH * Lines.Num() + 12.0f), FLinearColor(0, 0, 0, 0.45f));
	Bg.BlendMode = SE_BLEND_Translucent;
	Canvas->DrawItem(Bg);
	for (const FString& L : Lines)
	{
		FCanvasTextItem T(FVector2D(X, Y), FText::FromString(L), Font, FLinearColor::White);
		T.Scale = FVector2D(Scale, Scale);
		Canvas->DrawItem(T);
		Y += LineH;
	}
}

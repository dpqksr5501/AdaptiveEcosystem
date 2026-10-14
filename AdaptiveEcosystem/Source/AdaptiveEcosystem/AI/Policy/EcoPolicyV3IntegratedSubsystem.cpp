#include "EcoPolicyV3IntegratedSubsystem.h"

#include "AI/Social/Shelter/EcoShelterAnchor.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Core/EcoRuntimeSettings.h"
#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Creature/Runtime/EcoCreatureMovement.h"
#include "DrawDebugHelpers.h"
#include "EcoBehaviorConfig.h"
#include "EcoCreatureV3Trait.h"
#include "EcoPolicyV3Subsystem.h"
#include "Ecology/EcologySimulationSubsystem.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "MassEntityConfigAsset.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "World/EcoWorldClockSubsystem.h"
#include "World/EcologyRegion.h"

DEFINE_LOG_CATEGORY(LogEcoPolicyV3I);

namespace EcoPolicyV3IntegratedImpl
{
	static TAutoConsoleVariable<int32> CVarIntegratedVersion(
		TEXT("eco.IntegratedPolicyVersion"),
		1,
		TEXT("팀 통합 레벨(AEcoCreatureIntegrationSpawner)의 두뇌 판. 1 = 팀 그대로 (v1 + Social + 팀 늑대, 기본), ")
		TEXT("3 = 모든 사슴은 v3 R1b 학습 두뇌, 늑대는 학습 위협 규칙. Play 전에 바꾼다 (넷 모드 단독만 — PIE '오프라인 플레이'). ")
		TEXT("명령줄 -EcoIntegratedV3 는 시작값만 3 으로 둔다 (콘솔에서 1 을 넣으면 꺼진다)."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarDeerPerRegion(
		TEXT("eco.IntegratedV3.DeerPerRegion"),
		FEcoV3IntegratedSettings::kTrainDeer,
		TEXT("통합 v3 모드의 지역 무대마다 사슴 수 (기본 128 = 학습 N — 무대 120~220 m 어디서나 시작 밀도가 학습 범위 안, 피식 EMA 분모도 학습과 같다). ")
		TEXT("부활이 없어 줄기만 하고, 학습 밀도 하한(128/110² 마리/단위²) 아래로 내려가면 경고가 남는다. Play 전에 바꾼다. 명령줄 -EcoV3DeerPerRegion= 은 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarStageSizeM(
		TEXT("eco.IntegratedV3.StageSizeM"),
		120.0f,
		TEXT("통합 v3 모드의 지역 무대 한 변 (m, 학습 120~220). 먹이 자리를 중심으로 지역 상자 안에 둔다. 우리 은신처 반경은 한 변의 0.1 배 ")
		TEXT("(8~18 m 로 자름)라 크기를 바꿔도 은신처 넓이가 학습 범위 안이다. Play 전에 바꾼다."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarSeed(
		TEXT("eco.IntegratedV3.Seed"),
		20000,
		TEXT("통합 v3 모드의 세션 시드 (사건 결정 지연 해시·지역 세계 난수·시작 자리). 명령줄 -EcoV3Seed= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarDebug(
		TEXT("eco.V3Debug"),
		0,
		TEXT("통합 v3 모드 디버그 표시 (1 = 사슴 행동·늑대 상태 글자, 무대 사각형, 은신처 원, 지역 집계). 서버·단독만. 명령줄 -EcoV3Debug 는 시작값."),
		ECVF_Default);

	/** 시작 자리 난수의 첫 해시 입력 (세계 난수·지연 해시와 다른 값). */
	constexpr uint64 kPlanRngTag = 0x56334950ULL;   // "V3IP"

	constexpr double kStepSeconds = EcoRepertoireV3::kStepSeconds;

	/** 시작 직전 지면 검사는 많아야 이만큼 (조정자가 그 프레임에 시작하지 않으면 다음 프레임에 다시 — 시각이 어긋난 경우 대비). */
	constexpr int32 kMaxValidationPasses = 3;
	/** 조정자가 이 시간(BeginPlay 뒤) 안에 시작하지 못하면 통합 모드를 끈다 (조정자 스트리밍 시간 초과 30 초 + 여유). */
	constexpr double kGiveUpSeconds = 31.0;

	/** 팀 이동 제약을 부르는 토막 길이. ConstrainStep 은 옛 높이 + 65 cm 에서 반경 30 cm 구로 쓸어 보므로, 토막이 짧아야 비탈(법선 Z 0.65,
	 *  약 49°까지 허용)을 팀 이동처럼 오른다. 팀 조향은 프레임마다 약 15 cm 씩 부른다. */
	constexpr double kSubStepCm = 30.0;

	AEcologyRegion* FindRegion(UWorld* World, FName RegionId)
	{
		if (!World)
		{
			return nullptr;
		}
		for (TActorIterator<AEcologyRegion> It(World); It; ++It)
		{
			if (It->RegionId == RegionId)
			{
				return *It;
			}
		}
		return nullptr;
	}

	/**
	 * 조정자와 같은 지면 검사. 조정자는 시작할 때 받은 자리를 다시 ProjectSpawnPoint 로 검사하고 하나라도 실패하면 시작 전체를 거부한다
	 * (BuildSpawnPositions). 그래서 다시 검사해도 같은 자리(1 cm 안)가 나오는 점만 쓴다.
	 */
	bool ProjectLikeCoordinator(UWorld& World, const FVector& Hint, FVector& Out)
	{
		FVector G;
		FVector G2;
		if (!EcoCreatureMovement::ProjectSpawnPoint(World, Hint, G) || !EcoCreatureMovement::ProjectSpawnPoint(World, G, G2) || !G2.Equals(G, 1.0))
		{
			return false;
		}
		Out = G2;
		return true;
	}

	/** 지면 검사를 통과한 계획을 받아도 되는가: 다 채웠거나, 늑대를 다 찾고 사슴을 절반(최소 4) 넘게 찾았다. */
	bool AcceptGroundedPlan(const FEcoV3StagePlan& P, bool& bOutPartial)
	{
		bOutPartial = false;
		if (P.bComplete)
		{
			return true;
		}
		bOutPartial = P.WolfPoints.Num() == P.WantWolves && P.DeerPoints.Num() >= FMath::Min(P.WantDeer, FMath::Max(4, P.WantDeer / 2));
		return bOutPartial;
	}

	/** 그룹에 계획 자리를 쓴다 (조정자 BuildSpawnPositions 는 적어 둔 자리 앞에서부터 Count 개를 쓴다). */
	void WritePlanToGroup(const FEcoV3StagePlan& Plan, FEcoCreatureSpawnGroup& G)
	{
		G.Herbivores = Plan.DeerPoints.Num();
		G.Wolves = Plan.WolfPoints.Num();
		G.HerbivoreSpawnPoints = Plan.DeerPoints;
		G.WolfSpawnPoints = Plan.WolfPoints;
		G.Schedule.RegionPopulationLimit = FMath::Max(G.Schedule.RegionPopulationLimit, G.Herbivores + G.Wolves);
	}

	/** 명령줄 → 콘솔 변수 시작값은 프로세스에서 한 번 (처음 스위치를 읽을 때). */
	void EnsureCommandLineApplied()
	{
		static bool bDone = false;
		if (!bDone)
		{
			bDone = true;
			UEcoPolicyV3IntegratedSubsystem::ApplyCommandLineToConsole(FCommandLine::Get());
		}
	}
}

// -----------------------------------------------------------------------------
// 이름·늑대 성질
// -----------------------------------------------------------------------------

EcoV3Integrated::EWolfState EcoV3Integrated::WolfStateOf(const EcoWorldV3::FThreatAgent& A)
{
	if (A.State.bAsleep)
	{
		return EWolfState::Sleep;
	}
	if (A.Spec.Type == EcoThreatV3::EThreatType::Stalker)
	{
		if (A.State.StalkState == EcoThreatV3::EStalkState::Pounce)
		{
			return EWolfState::Pounce;
		}
		if (A.State.StalkState == EcoThreatV3::EStalkState::Exhaust)
		{
			return EWolfState::Exhaust;
		}
	}
	if (A.State.Cooldown > 0)
	{
		return EWolfState::Eat;
	}
	if (A.Last.bHasTarget)
	{
		return A.Spec.Type == EcoThreatV3::EThreatType::Stalker ? EWolfState::Stalk : EWolfState::Chase;
	}
	return EWolfState::Roam;
}

const TCHAR* EcoV3Integrated::WolfStateNameKo(EWolfState State)
{
	static const TCHAR* Names[static_cast<int32>(EWolfState::Count)] = {TEXT("배회"), TEXT("잠행"), TEXT("돌진"), TEXT("지침"),
																		  TEXT("추격"), TEXT("식사"), TEXT("잠")};
	const int32 I = static_cast<int32>(State);
	return (I >= 0 && I < static_cast<int32>(EWolfState::Count)) ? Names[I] : TEXT("?");
}

const TCHAR* EcoV3Integrated::BehaviorNameKo(int32 B)
{
	static const TCHAR* Names[EcoRepertoireV3::kNumBehaviors] = {TEXT("먹기"), TEXT("도망"), TEXT("숨기"), TEXT("얼기"), TEXT("잠")};
	return (B >= 0 && B < EcoRepertoireV3::kNumBehaviors) ? Names[B] : TEXT("?");
}

EcoThreatV3::FThreatSpec EcoV3Integrated::WolfSpecForOrdinal(int32 Ordinal, double PredSpeedMult)
{
	const EcoThreatV3::FThreatConfig Cfg;
	return (Ordinal % 2) == 0 ? EcoThreatV3::MakeStalkerSpec(PredSpeedMult, false, Cfg)
							  : EcoThreatV3::MakeChaserSpec(PredSpeedMult, false, false, Cfg);
}

FEcoV3IntegratedSettings FEcoV3IntegratedSettings::FromConsole()
{
	using namespace EcoPolicyV3IntegratedImpl;
	EnsureCommandLineApplied();
	FEcoV3IntegratedSettings S;
	S.Seed = CVarSeed.GetValueOnGameThread();
	S.DeerPerRegion = FMath::Clamp(CVarDeerPerRegion.GetValueOnGameThread(), 1, kTrainDeer);
	S.StageSizeUnits = FMath::Clamp(static_cast<double>(CVarStageSizeM.GetValueOnGameThread()) * 100.0 / EcoRepertoireV3::kUnitCm, 60.0, 110.0);
	return S;
}

// -----------------------------------------------------------------------------
// 스위치·생명주기
// -----------------------------------------------------------------------------

void UEcoPolicyV3IntegratedSubsystem::ApplyCommandLineToConsole(const TCHAR* CmdLine)
{
	if (!CmdLine)
	{
		return;
	}
	// 콘솔·코드가 이미 정한 변수는 건드리지 않는다 (낮은 우선순위로 쓰면 엔진이 무시하며 기록을 남긴다)
	auto SetIfUnset = [](const TCHAR* Name, const FString& Value)
	{
		IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(Name);
		if (V && static_cast<uint32>(V->GetFlags() & ECVF_SetByMask) <= static_cast<uint32>(ECVF_SetByCommandline))
		{
			V->Set(*Value, ECVF_SetByCommandline);
		}
	};
	if (FParse::Param(CmdLine, TEXT("EcoIntegratedV3")))
	{
		SetIfUnset(TEXT("eco.IntegratedPolicyVersion"), TEXT("3"));
	}
	if (FParse::Param(CmdLine, TEXT("EcoV3Debug")))
	{
		SetIfUnset(TEXT("eco.V3Debug"), TEXT("1"));
	}
	int32 SeedArg = 0;
	if (FParse::Value(CmdLine, TEXT("EcoV3Seed="), SeedArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.Seed"), LexToString(SeedArg));
	}
	int32 DeerArg = 0;
	if (FParse::Value(CmdLine, TEXT("EcoV3DeerPerRegion="), DeerArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.DeerPerRegion"), LexToString(DeerArg));
	}
}

int32 UEcoPolicyV3IntegratedSubsystem::GetRequestedVersion()
{
	EcoPolicyV3IntegratedImpl::EnsureCommandLineApplied();
	return EcoPolicyV3IntegratedImpl::CVarIntegratedVersion.GetValueOnGameThread() == 3 ? 3 : 1;
}

bool UEcoPolicyV3IntegratedSubsystem::IsDebugDrawEnabled()
{
	EcoPolicyV3IntegratedImpl::EnsureCommandLineApplied();
	return EcoPolicyV3IntegratedImpl::CVarDebug.GetValueOnGameThread() != 0;
}

void FEcoV3PreStartTickFunction::ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread,
											 const FGraphEventRef& MyCompletionGraphEvent)
{
	if (UEcoPolicyV3IntegratedSubsystem* Sub = Owner.Get())
	{
		Sub->HandlePreStartTick();
	}
}

bool UEcoPolicyV3IntegratedSubsystem::DoesSupportWorldType(const EWorldType::Type WorldType) const
{
	return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

void UEcoPolicyV3IntegratedSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	const bool bRequested = IsRequested();
	TArray<AEcoCreatureIntegrationSpawner*> Found;
	for (TActorIterator<AEcoCreatureIntegrationSpawner> It(&InWorld); It; ++It)
	{
		Found.Add(*It);
	}
	if (!bRequested)
	{
		// 기본: 아무것도 바꾸지 않는다 — 팀 레벨은 지금 그대로 돈다. 왜 팀 두뇌로 도는지 알 수 있게 한 줄만 남긴다
		if (!Found.IsEmpty())
		{
			UE_LOG(LogEcoPolicyV3I, Log,
				   TEXT("[EcoV3I] 통합 v3 모드 꺼짐 (기본) — 팀 두뇌로 돈다. 켜려면 Play 전에 콘솔에 eco.IntegratedPolicyVersion 3 (PIE 넷 모드 '오프라인 플레이', ")
					   TEXT("독립형 게임은 추가 실행 인수 -EcoIntegratedV3)"));
		}
		return;
	}
	if (Found.IsEmpty())
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 통합 모드가 요청됐지만 이 월드에 통합 조정자(AEcoCreatureIntegrationSpawner)가 없다 — 아무것도 바꾸지 않는다"));
		return;
	}
	if (InWorld.GetNetMode() != NM_Standalone)
	{
		UE_LOG(LogEcoPolicyV3I, Warning,
			   TEXT("[EcoV3I] 통합 v3 모드는 지금 넷 모드 단독(Standalone)만 지원한다 (넷 모드 %d). 팀 그대로 돈다 — PIE 는 넷 모드 '오프라인 플레이'로 띄운다. ")
				   TEXT("클라이언트 표시는 팀 합의 뒤"),
			   static_cast<int32>(InWorld.GetNetMode()));
		return;
	}
	if (Found.Num() > 1)
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 통합 조정자가 %d 개다 — 첫 번째(%s)만 바꾼다 (조정자도 하나만 허용한다)"), Found.Num(),
			   *GetNameSafe(Found[0]));
	}
	Settings = FEcoV3IntegratedSettings::FromConsole();
	bUseTerrain = true;
	BeginPlaySeconds = InWorld.GetTimeSeconds();
	if (!ApplyToSpawner(*Found[0]))
	{
		UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 조정자 설정을 바꾸지 못했다 — 통합 v3 모드를 켜지 않는다 (조정자는 하나도 바꾸지 않았다, 팀 그대로)"));
		return;
	}
	bActive = true;
	UpdateViewEnvironment();
	LogEverySteps = FMath::Max(1, FMath::RoundToInt32(Settings.LogIntervalSeconds / EcoBehaviorConfig::StepSeconds));
	PreTickHandle = FWorldDelegates::OnWorldPreActorTick.AddUObject(this, &UEcoPolicyV3IntegratedSubsystem::HandlePreActorTick);
	if (bStreamingSpawner && InWorld.PersistentLevel)
	{
		// 시작 직전 지면 검사: 엔진 스트리밍 갱신 뒤, 조정자 OnWorldPostActorTick 앞 (FEcoV3PreStartTickFunction 설명)
		PreStartTick.Owner = this;
		PreStartTick.bCanEverTick = true;
		PreStartTick.bStartWithTickEnabled = true;
		PreStartTick.bTickEvenWhenPaused = true;
		PreStartTick.TickGroup = TG_LastDemotable;
		PreStartTick.EndTickGroup = TG_LastDemotable;
		PreStartTick.RegisterTickFunction(InWorld.PersistentLevel);
	}
	const int32 Wolves = Settings.WolvesPerRegion;
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] 통합 모드 켬 — 조정자 %s | 모델 %s (관측 %d, 마스크 판 %d) | 지역 %d, 지역마다 사슴 %d·늑대 %d (잠행 %d·추격 %d, 모두 주행성, 속력 %.2f배) | ")
			   TEXT("무대 한 변 %.0f m | 시드 %lld | 이주·웨이브·1초 에너지 소모 끔, 낮밤 60+60초 | 시작 자리 지면 검사: %s"),
		   *GetNameSafe(Found[0]), UTF8_TO_TCHAR(EcoPolicyV3::kModelName), EcoPolicyV3::kObsDim, EcoPolicyV3::kMaskVersion, Plans.Num(),
		   Plans.IsEmpty() ? 0 : Plans[0].DeerPoints.Num(), Wolves, (Wolves + 1) / 2, Wolves / 2, Settings.PredSpeedMult,
		   Settings.StageSizeUnits * EcoRepertoireV3::kUnitCm / 100.0, static_cast<long long>(Settings.Seed),
		   bStreamingSpawner ? TEXT("서식지 스트리밍이 끝나는 프레임에 조정자 시작 직전 다시") : TEXT("끝 (스트리밍 없음 — 조정자가 BeginPlay 에서 시작)"));
}

void UEcoPolicyV3IntegratedSubsystem::Deinitialize()
{
	if (PreTickHandle.IsValid())
	{
		FWorldDelegates::OnWorldPreActorTick.Remove(PreTickHandle);
		PreTickHandle.Reset();
	}
	PreStartTick.UnRegisterTickFunction();
	bActive = false;
	RestoreViewEnvironment();
	Contexts.Reset();
	Plans.Reset();
	SpawnedCovers.Reset();
	OurShelterIndices.Reset();
	TeamValues = FEcoV3SpawnerTeamValues();
	TeamHerbivoreConfig = nullptr;
	TeamWolfConfig = nullptr;
	Super::Deinitialize();
}

void UEcoPolicyV3IntegratedSubsystem::ActivateForTest(const FEcoV3IntegratedSettings& InSettings, bool bTerrain)
{
	Settings = InSettings;
	bUseTerrain = bTerrain;
	bActive = true;
	bContextsCreated = true;
	bPointsFinal = true;
	LogEverySteps = FMath::Max(1, FMath::RoundToInt32(Settings.LogIntervalSeconds / EcoBehaviorConfig::StepSeconds));
}

bool UEcoPolicyV3IntegratedSubsystem::ApplyToSpawnerForTest(AEcoCreatureIntegrationSpawner& InSpawner, const FEcoV3IntegratedSettings& InSettings)
{
	Settings = InSettings;
	bUseTerrain = true;
	BeginPlaySeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	if (!ApplyToSpawner(InSpawner))
	{
		return false;
	}
	bActive = true;
	LogEverySteps = FMath::Max(1, FMath::RoundToInt32(Settings.LogIntervalSeconds / EcoBehaviorConfig::StepSeconds));
	return true;
}

void UEcoPolicyV3IntegratedSubsystem::Deactivate(const TCHAR* Why)
{
	UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 통합 v3 모드를 끈다: %s"), Why);
	bActive = false;
	RestoreViewEnvironment();
	bPointsFinal = true;   // 시작 직전 틱은 다음 프레임 앞(HandlePreActorTick)에 등록을 푼다 — 틱 안에서는 풀지 않는다
}

void UEcoPolicyV3IntegratedSubsystem::RestoreTeamValues(const TCHAR* Why)
{
	if (AEcoCreatureIntegrationSpawner* S = Spawner.Get(); S && TeamValues.bValid)
	{
		S->HerbivoreConfig = TeamHerbivoreConfig;
		S->WolfConfig = TeamWolfConfig;
		S->Groups = TeamValues.Groups;
		S->Migration = TeamValues.Migration;
		S->bEnableWaves = TeamValues.bEnableWaves;
		S->EnergyDrainPerSecond = TeamValues.EnergyDrainPerSecond;
		S->EnergyPerFood = TeamValues.EnergyPerFood;
		S->DaySeconds = TeamValues.DaySeconds;
		S->NightSeconds = TeamValues.NightSeconds;
		S->GlobalPopulationLimit = TeamValues.GlobalPopulationLimit;
		UE_LOG(LogEcoPolicyV3I, Error,
			   TEXT("[EcoV3I] 조정자를 팀 값으로 되돌렸다 (설정 %s·%s, 그룹 %d) — 조정자는 팀 그대로 시작한다. 서식지 스트리밍 원천은 v3 계획 자리로 잡혀 있어 ")
				   TEXT("팀 시작 자리가 무대 밖이면 조정자 시작이 실패할 수 있다"),
			   *GetNameSafe(TeamHerbivoreConfig.Get()), *GetNameSafe(TeamWolfConfig.Get()), TeamValues.Groups.Num());
	}
	Deactivate(Why);
}

// -----------------------------------------------------------------------------
// 계획 (엔진 상태 없이)
// -----------------------------------------------------------------------------

bool UEcoPolicyV3IntegratedSubsystem::PlanStage(FName RegionId, int32 GroupIndex, const FVector& DesiredCenterCm,
												const FVector& RegionCenterCm, const FEcoV3IntegratedSettings& S, int32 NumDeer,
												int32 NumWolves, bool bRequireGround, TFunctionRef<bool(const FVector&)> Contains,
												TFunctionRef<bool(const FVector&, FVector&)> Project, FEcoV3StagePlan& Out)
{
	Out = FEcoV3StagePlan();
	Out.RegionId = RegionId;
	Out.GroupIndex = GroupIndex;
	Out.WantDeer = NumDeer;
	Out.WantWolves = NumWolves;
	Out.SizeUnits = FMath::Clamp(S.StageSizeUnits, 60.0, 110.0);
	const double Half = 0.5 * Out.SizeUnits * EcoRepertoireV3::kUnitCm;

	// 무대가 지역 상자 안에 들게 한다 (네 모서리). 안 들면 지역 중심 쪽으로 옮긴다
	auto StageInside = [&Contains, Half](const FVector& C)
	{
		for (const double Sx : {-1.0, 1.0})
		{
			for (const double Sy : {-1.0, 1.0})
			{
				if (!Contains(FVector(C.X + Sx * Half, C.Y + Sy * Half, C.Z)))
				{
					return false;
				}
			}
		}
		return true;
	};
	FVector Center = DesiredCenterCm;
	if (!StageInside(Center))
	{
		for (int32 k = 1; k <= 20; ++k)
		{
			const double A = static_cast<double>(k) / 20.0;
			const FVector C(FMath::Lerp(DesiredCenterCm.X, RegionCenterCm.X, A), FMath::Lerp(DesiredCenterCm.Y, RegionCenterCm.Y, A),
							DesiredCenterCm.Z);
			if (StageInside(C))
			{
				Center = C;
				break;
			}
		}
	}
	Out.CenterCm = Center;
	Out.bStageInside = StageInside(Center);

	EcoWorldV3::FRng Rng;
	Rng.State = EcoRepertoireV3::HashChain3(EcoPolicyV3IntegratedImpl::kPlanRngTag, static_cast<uint64>(S.Seed),
											static_cast<uint64>(GroupIndex + 1));
	bool bAllGrounded = true;
	auto TryPoint = [&](const FVector& Hint, FVector& OutPoint) -> bool
	{
		FVector G;
		if (Project(Hint, G) && Contains(G) && Out.IsInsideStage(G, 100.0))
		{
			OutPoint = G;
			return true;
		}
		if (bRequireGround)
		{
			return false;
		}
		OutPoint = Hint;   // 스트리밍 전 계획: 힌트 그대로 둔다 (조정자 시작 직전 지면 검사로 바꾼다)
		bAllGrounded = false;
		return true;
	};

	// 늑대 먼저: 무대 모서리 쪽 (마주 보는 모서리부터), 늑대끼리 WolfMinStartDistCm × 1.5 밖. 모서리가 안 되면 무대 안 아무 데나
	auto FarFromWolves = [&Out](const FVector& P, double Dist)
	{
		for (const FVector& W : Out.WolfPoints)
		{
			if (FVector::DistSquared2D(W, P) < Dist * Dist)
			{
				return false;
			}
		}
		return true;
	};
	const double WolfGap = 1.5 * S.WolfMinStartDistCm;
	const double Corner = S.WolfStartCornerFrac * Out.SizeUnits * EcoRepertoireV3::kUnitCm;
	const FVector2D Corners[4] = {{1.0, 1.0}, {-1.0, -1.0}, {1.0, -1.0}, {-1.0, 1.0}};
	for (int32 c = 0; c < 4 && Out.WolfPoints.Num() < NumWolves; ++c)
	{
		const FVector Hint(Center.X + Corners[c].X * Corner, Center.Y + Corners[c].Y * Corner, Center.Z);
		FVector P;
		if (FarFromWolves(Hint, WolfGap) && TryPoint(Hint, P) && FarFromWolves(P, WolfGap))
		{
			Out.WolfPoints.Add(P);
		}
	}
	const double Room = Half - 300.0;
	for (int32 Try = 0; Try < 400 && Out.WolfPoints.Num() < NumWolves; ++Try)
	{
		const FVector Hint(Center.X + Rng.Uniform(-Room, Room), Center.Y + Rng.Uniform(-Room, Room), Center.Z);
		FVector P;
		if (FarFromWolves(Hint, WolfGap) && TryPoint(Hint, P) && FarFromWolves(P, WolfGap))
		{
			Out.WolfPoints.Add(P);
		}
	}

	// 사슴: 무대 전체 균등 (학습 세계의 시작과 같은 꼴), 모든 늑대에게서 WolfMinStartDistCm 밖, 서로 DeerMinSpacingCm 밖
	const double Spacing2 = FMath::Square(S.DeerMinSpacingCm);
	auto FarFromDeer = [&Out](const FVector& P, double Dist2)
	{
		for (const FVector& D : Out.DeerPoints)
		{
			if (FVector::DistSquared2D(D, P) < Dist2)
			{
				return false;
			}
		}
		return true;
	};
	const double DeerWolfGap = S.WolfMinStartDistCm + 100.0;
	const int32 MaxDeerTries = FMath::Max(64, NumDeer * 60);
	for (int32 Try = 0; Try < MaxDeerTries && Out.DeerPoints.Num() < NumDeer; ++Try)
	{
		const FVector Hint(Center.X + Rng.Uniform(-Room, Room), Center.Y + Rng.Uniform(-Room, Room), Center.Z);
		FVector P;
		if (FarFromWolves(Hint, DeerWolfGap) && FarFromDeer(Hint, Spacing2) && TryPoint(Hint, P) && FarFromWolves(P, DeerWolfGap)
			&& FarFromDeer(P, Spacing2))
		{
			Out.DeerPoints.Add(P);
		}
	}
	Out.bGrounded = bAllGrounded;
	Out.bComplete = Out.DeerPoints.Num() == NumDeer && Out.WolfPoints.Num() == NumWolves;
	return Out.bComplete && (!bRequireGround || Out.bGrounded);
}

EcoWorldV3::FWorldConfig UEcoPolicyV3IntegratedSubsystem::MakeRegionWorldConfig(
	const FEcoV3IntegratedSettings& S, int32 RegionRuntimeIndex, int32 PlannedDeer, int32 PlannedWolves,
	const std::vector<EcoObservationV3::FCoverInput>& Covers)
{
	EcoWorldV3::FWorldConfig C;
	C.WorldSize = FMath::Clamp(S.StageSizeUnits, 60.0, 110.0);
	C.Seed = S.Seed;                                          // 지연 해시 Seed = 세션 시드 (계약 12-3)
	C.NumHerbivores = FMath::Max(1, PlannedDeer);              // 학습 범위 확인용 (통합 Step 은 이번 스텝 산 수를 받는다)
	const int32 Wolves = FMath::Max(0, PlannedWolves);
	C.NumStalkers = (Wolves + 1) / 2;                          // WolfSpecForOrdinal 과 같은 구성 (짝수 순번 = 잠행)
	C.NumChasers = Wolves / 2;
	C.NumRanged = 0;
	C.NumNocturnal = 0;
	C.bPlayerProxy = false;
	C.PredSpeedMult = S.PredSpeedMult;
	C.DayPeriod = 900;                                         // 60 s + 60 s (팀 시계와 같은 길이)
	C.DayOffset = 0;
	C.TwilightSteps = 45;
	C.Covers = Covers;
	C.FoodRegenMult = 1.0;
	C.RngStream = static_cast<uint64>(FMath::Max(0, RegionRuntimeIndex)) + 1;   // 지역마다 다른 먹이 패치·늑대 선회 (0 은 평면 맵 몫)
	C.bRespawnDead = false;                                    // 제자리 부활 없음 (계약 12-3: 새 개체 = 새 StableAgentId)
	C.PredEmaDenominator = FMath::Max(1, PlannedDeer);         // 고정 분모 = 무대 처음 사슴 수 (학습의 고정 128 과 같은 꼴, 열린 질문 7)
	return C;
}

// -----------------------------------------------------------------------------
// 조정자 공개 속성 바꾸기 (OnWorldBeginPlay — 액터 BeginPlay 앞)
// -----------------------------------------------------------------------------

bool UEcoPolicyV3IntegratedSubsystem::ApplyToSpawner(AEcoCreatureIntegrationSpawner& S)
{
	using namespace EcoPolicyV3IntegratedImpl;
	UWorld* World = GetWorld();
	if (!World || S.Groups.IsEmpty())
	{
		return false;
	}
	const int32 Wolves = FMath::Clamp(Settings.WolvesPerRegion, 0, 12);
	int32 Deer = FMath::Clamp(Settings.DeerPerRegion, 1, FEcoV3IntegratedSettings::kTrainDeer);
	while (S.Groups.Num() * (Deer + Wolves) > 512 && Deer > 1)
	{
		--Deer;   // 조정자 개체 상한 512 안에 든다
	}
	const bool bStreaming = S.bUseHabitatStreaming;

	// 1. 모든 그룹의 계획을 지역 배열에 먼저 모은다 — 조정자는 아직 그대로다 (하나라도 실패하면 하나도 쓰지 않는다)
	TArray<FEcoV3StagePlan> NewPlans;
	TArray<FEcoCreatureSpawnGroup> NewGroups = S.Groups;
	TArray<bool> Partial;
	int64 Total = 0;
	for (int32 g = 0; g < NewGroups.Num(); ++g)
	{
		FEcoCreatureSpawnGroup& G = NewGroups[g];
		AEcologyRegion* Region = FindRegion(World, G.RegionId);
		if (!Region)
		{
			// 조정자도 지역이 없는 그룹으로는 시작하지 못한다(StartAuthority) — 우리는 아무것도 바꾸지 않는다
			UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 그룹 %d 의 지역 %s 를 찾지 못했다"), g, *G.RegionId.ToString());
			return false;
		}
		const FVector Desired = G.bUseFoodPatchPosition ? G.FoodPatchPosition : Region->GetActorLocation();
		auto Contains = [Region](const FVector& P) { return Region->ContainsPosition(P); };
		auto Project = [World](const FVector& Hint, FVector& Out) { return ProjectLikeCoordinator(*World, Hint, Out); };
		FEcoV3StagePlan Plan;
		bool bPartial = false;
		if (bStreaming)
		{
			// 지형이 덜 왔다: 이 계획은 힌트일 뿐이다(조정자가 이 자리로 스트리밍 원천 모양을 잡는다). 조정자 시작 직전 검사가 늘 다시 고른다
			PlanStage(G.RegionId, g, Desired, Region->GetActorLocation(), Settings, Deer, Wolves, false, Contains, Project, Plan);
			Plan.bGrounded = false;
			if (!Plan.bComplete)
			{
				UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 지역 %s 무대에 시작 자리를 다 놓지 못했다 (사슴 %d/%d, 늑대 %d/%d)"),
					   *G.RegionId.ToString(), Plan.DeerPoints.Num(), Deer, Plan.WolfPoints.Num(), Wolves);
				return false;
			}
		}
		else
		{
			// 스트리밍 없음: 조정자가 같은 UWorld::BeginPlay 안에서 바로 시작하므로 지금 지형이 조정자가 볼 지형이다
			PlanStage(G.RegionId, g, Desired, Region->GetActorLocation(), Settings, Deer, Wolves, true, Contains, Project, Plan);
			if (!AcceptGroundedPlan(Plan, bPartial))
			{
				UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 지역 %s 무대에서 지면 검사를 통과한 시작 자리가 모자란다 (사슴 %d/%d, 늑대 %d/%d)"),
					   *G.RegionId.ToString(), Plan.DeerPoints.Num(), Deer, Plan.WolfPoints.Num(), Wolves);
				return false;
			}
		}
		WritePlanToGroup(Plan, G);
		Total += G.Herbivores + G.Wolves;
		NewPlans.Add(Plan);
		Partial.Add(bPartial);
	}
	if (NewPlans.IsEmpty() || Total > 512)
	{
		return false;
	}

	// 2. 몸은 팀 것, 머리만 우리 것: 우리 트레잇 하나를 가진 실행 중 설정. 팀 DA 는 바꾸지 않는다
	UMassEntityConfigAsset* DeerConfig = UEcoCreatureV3Trait::MakeConfig(&S, false);
	UMassEntityConfigAsset* WolfConfig = UEcoCreatureV3Trait::MakeConfig(&S, true);
	if (!DeerConfig || !WolfConfig)
	{
		return false;
	}
	for (const UMassEntityConfigAsset* Old : {S.HerbivoreConfig.Get(), S.WolfConfig.Get()})
	{
		if (Old && (Old->GetConfig().GetGuid() == DeerConfig->GetConfig().GetGuid() || Old->GetConfig().GetGuid() == WolfConfig->GetConfig().GetGuid()))
		{
			UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 실행 중 설정의 GUID 가 팀 설정과 같다 — 템플릿이 섞이므로 켜지 않는다"));
			return false;
		}
	}

	// 3. 다 통과했다: 팀 값을 쥐어 두고 한꺼번에 쓴다
	TeamValues.Groups = S.Groups;
	TeamValues.Migration = S.Migration;
	TeamValues.bEnableWaves = S.bEnableWaves;
	TeamValues.EnergyDrainPerSecond = S.EnergyDrainPerSecond;
	TeamValues.EnergyPerFood = S.EnergyPerFood;
	TeamValues.DaySeconds = S.DaySeconds;
	TeamValues.NightSeconds = S.NightSeconds;
	TeamValues.GlobalPopulationLimit = S.GlobalPopulationLimit;
	TeamValues.bValid = true;
	TeamHerbivoreConfig = S.HerbivoreConfig;
	TeamWolfConfig = S.WolfConfig;

	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 설정 교체: 사슴 %s → %s, 늑대 %s → %s"), *GetNameSafe(S.HerbivoreConfig.Get()),
		   *DeerConfig->GetName(), *GetNameSafe(S.WolfConfig.Get()), *WolfConfig->GetName());
	if (S.DaySeconds != 60.0 || S.NightSeconds != 60.0)
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 낮밤 %.0f+%.0f초 → 60+60초 (학습 주기 900 스텝)"), S.DaySeconds, S.NightSeconds);
	}
	S.Groups = NewGroups;
	S.HerbivoreConfig = DeerConfig;
	S.WolfConfig = WolfConfig;
	// 학습 세계에 없는 것 끄기 + 에너지 주인은 v3 (Vitals 는 거울)
	S.Migration.bEnabled = false;
	S.bEnableWaves = false;
	S.EnergyDrainPerSecond = 0.0f;
	S.EnergyPerFood = 0.0f;
	S.DaySeconds = 60.0;
	S.NightSeconds = 60.0;
	S.GlobalPopulationLimit = static_cast<int32>(FMath::Clamp<int64>(FMath::Max<int64>(S.GlobalPopulationLimit, Total), 1, 512));

	Plans = MoveTemp(NewPlans);
	Spawner = &S;
	bStreamingSpawner = bStreaming;
	bPointsFinal = !bStreaming;
	ValidationPasses = 0;
	for (int32 k = 0; k < Plans.Num(); ++k)
	{
		const FEcoV3StagePlan& Plan = Plans[k];
		const FEcoCreatureSpawnGroup& G = S.Groups[Plan.GroupIndex];
		if (!Plan.bStageInside)
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 지역 %s: 무대 %.0f m 가 지역 상자에 다 들지 않는다 — 가장자리는 팀 이동 제약이 막는다"),
				   *G.RegionId.ToString(), Plan.SizeUnits * 2.0);
		}
		if (Partial[k])
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 지역 %s: 지면 검사를 통과한 사슴 자리가 %d/%d 라 그 수로 시작한다"), *G.RegionId.ToString(),
				   Plan.DeerPoints.Num(), Plan.WantDeer);
		}
		if (FEcoV3IntegratedSettings::IsBelowTrainingDensity(G.Herbivores, Plan.SizeUnits))
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 지역 %s: 사슴 %d 마리는 무대 %.0f 단위에서 학습 밀도 하한(%.1f 마리 = 128/110² 마리/단위²) 아래다"),
				   *G.RegionId.ToString(), G.Herbivores, Plan.SizeUnits,
				   FEcoV3IntegratedSettings::kTrainDeer * Plan.SizeUnits * Plan.SizeUnits / (110.0 * 110.0));
		}
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] 무대 계획 %s: 중심 (%.0f, %.0f), 한 변 %.0f m, 사슴 %d (무대 균등, 밀도 %.4f/m²), 늑대 %d (모든 사슴에게서 %.0f m 밖), 지면 검사 %s"),
			   *G.RegionId.ToString(), Plan.CenterCm.X, Plan.CenterCm.Y, Plan.SizeUnits * 2.0, G.Herbivores,
			   G.Herbivores / FMath::Square(Plan.SizeUnits * 2.0), G.Wolves, Settings.WolfMinStartDistCm / 100.0,
			   Plan.bGrounded ? TEXT("끝") : TEXT("조정자 시작 직전에 다시 (지금 자리는 스트리밍 힌트)"));
	}
	return true;
}

bool UEcoPolicyV3IntegratedSubsystem::ValidateSpawnPointsNow()
{
	using namespace EcoPolicyV3IntegratedImpl;
	AEcoCreatureIntegrationSpawner* S = Spawner.Get();
	UWorld* World = GetWorld();
	if (!bActive || !S || !World)
	{
		return false;
	}
	++ValidationPasses;
	// 모든 그룹을 지역 배열에 먼저 검사한다 — 하나라도 모자라면 조정자를 팀 값으로 되돌린다 (빈 레벨보다 팀 그대로가 낫다)
	TArray<FEcoV3StagePlan> NewPlans;
	TArray<FEcoCreatureSpawnGroup> NewGroups = S->Groups;
	TArray<bool> Partial;
	for (const FEcoV3StagePlan& Old : Plans)
	{
		FEcoCreatureSpawnGroup* G = NewGroups.IsValidIndex(Old.GroupIndex) ? &NewGroups[Old.GroupIndex] : nullptr;
		AEcologyRegion* Region = G ? FindRegion(World, G->RegionId) : nullptr;
		if (!Region)
		{
			RestoreTeamValues(TEXT("시작 직전 지면 검사: 그룹·지역을 찾지 못했다"));
			return false;
		}
		const FVector Desired = G->bUseFoodPatchPosition ? G->FoodPatchPosition : Region->GetActorLocation();
		auto Contains = [Region](const FVector& P) { return Region->ContainsPosition(P); };
		auto Project = [World](const FVector& Hint, FVector& Out) { return ProjectLikeCoordinator(*World, Hint, Out); };
		FEcoV3StagePlan Grounded;
		PlanStage(G->RegionId, Old.GroupIndex, Desired, Region->GetActorLocation(), Settings, Old.WantDeer, Old.WantWolves, true, Contains,
				  Project, Grounded);
		bool bPartial = false;
		if (!AcceptGroundedPlan(Grounded, bPartial))
		{
			UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 지역 %s: 시작 직전 지면 검사를 통과한 자리가 모자란다 (사슴 %d/%d, 늑대 %d/%d)"),
				   *G->RegionId.ToString(), Grounded.DeerPoints.Num(), Old.WantDeer, Grounded.WolfPoints.Num(), Old.WantWolves);
			RestoreTeamValues(TEXT("시작 직전 지면 검사로 시작 자리를 채우지 못했다"));
			return false;
		}
		Grounded.bGrounded = true;
		WritePlanToGroup(Grounded, *G);
		NewPlans.Add(Grounded);
		Partial.Add(bPartial);
	}
	S->Groups = NewGroups;
	Plans = MoveTemp(NewPlans);
	FString Summary;
	for (int32 k = 0; k < Plans.Num(); ++k)
	{
		Summary += FString::Printf(TEXT(" %s 사슴 %d/%d 늑대 %d/%d%s"), *Plans[k].RegionId.ToString(), Plans[k].DeerPoints.Num(), Plans[k].WantDeer,
								   Plans[k].WolfPoints.Num(), Plans[k].WantWolves, Partial[k] ? TEXT(" (사슴 일부만)") : TEXT(""));
	}
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 조정자 시작 직전 지면 검사 %d 번째 끝 (BeginPlay 뒤 %.2f 초):%s"), ValidationPasses,
		   World->GetTimeSeconds() - BeginPlaySeconds, *Summary);
	return true;
}

// -----------------------------------------------------------------------------
// 매 프레임 앞 (Mass 처리 밖)
// -----------------------------------------------------------------------------

void UEcoPolicyV3IntegratedSubsystem::HandlePreActorTick(UWorld* InWorld, ELevelTick TickType, float DeltaSeconds)
{
	if (InWorld != GetWorld() || TickType == LEVELTICK_ViewportsOnly)
	{
		return;
	}
	// 시작 직전 틱은 더 할 일이 없으면 여기(틱 그룹 밖)에서 등록을 푼다
	if ((!bActive || bPointsFinal) && PreStartTick.IsTickFunctionRegistered())
	{
		PreStartTick.UnRegisterTickFunction();
	}
	if (!bActive)
	{
		return;
	}
	UpdateViewEnvironment();
	if (!bContextsCreated)
	{
		TryCreateContexts();
		if (!bContextsCreated && bActive)
		{
			// 조정자가 시작하지 못했다: 시작 직전 검사를 다 썼거나 시간 초과. 매 프레임 다시 검사하지 않고 끈다
			const double Elapsed = InWorld->GetTimeSeconds() - BeginPlaySeconds;
			const bool bPassesUsed = bStreamingSpawner && ValidationPasses >= EcoPolicyV3IntegratedImpl::kMaxValidationPasses;
			if (bPassesUsed || Elapsed > EcoPolicyV3IntegratedImpl::kGiveUpSeconds)
			{
				Deactivate(*FString::Printf(TEXT("조정자가 시작하지 못했다 (BeginPlay 뒤 %.1f 초, 시작 직전 지면 검사 %d 번) — 레벨에 동물이 없을 수 있다. ")
												TEXT("위 [Eco Integration] 오류를 본다"),
											Elapsed, ValidationPasses));
			}
		}
	}
	if (bContextsCreated)
	{
		CheckClockDrift();
		if (IsDebugDrawEnabled())
		{
			DrawOverlay();
		}
	}
}

void UEcoPolicyV3IntegratedSubsystem::HandlePreStartTick()
{
	// TG_LastDemotable: 이 프레임의 엔진 스트리밍 갱신은 끝났고, 조정자 OnWorldPostActorTick 은 아직이다
	if (!bActive || bPointsFinal || !bStreamingSpawner || ValidationPasses >= EcoPolicyV3IntegratedImpl::kMaxValidationPasses)
	{
		return;
	}
	AEcoCreatureIntegrationSpawner* S = Spawner.Get();
	const UWorld* World = GetWorld();
	if (!S || !World)
	{
		return;
	}
	if (S->IsRuntimeReady())
	{
		bPointsFinal = true;
		return;
	}
	const bool bStreamDone = S->HabitatStreamingSource && S->HabitatStreamingSource->IsStreamingCompleted();
	if (!CoordinatorStartsThisFrame(World->GetTimeSeconds() - BeginPlaySeconds, bStreamDone))
	{
		return;   // 조정자도 이 프레임에는 시작하지 않는다 — 검사하지 않는다
	}
	ValidateSpawnPointsNow();
}

void UEcoPolicyV3IntegratedSubsystem::TryCreateContexts()
{
	AEcoCreatureIntegrationSpawner* S = Spawner.Get();
	UWorld* World = GetWorld();
	if (!S || !World || !S->IsRuntimeReady())
	{
		return;
	}
	bContextsCreated = true;
	bPointsFinal = true;

	// 전역 t 를 팀 시계에 맞춘다 (낮 시작 = 스텝 0, 60 초 = 450 스텝 — v3 어둠 식의 낮 시작과 같다)
	if (const UEcoWorldClockSubsystem* TeamClock = World->GetSubsystem<UEcoWorldClockSubsystem>(); TeamClock && TeamClock->IsClockRunning())
	{
		GlobalT = FMath::Max<int64>(0, FMath::RoundToInt64(TeamClock->GetServerTime().ServerTimeSeconds / EcoPolicyV3IntegratedImpl::kStepSeconds));
	}
	const UEcologySimulationSubsystem* Ecology = World->GetSubsystem<UEcologySimulationSubsystem>();
	UEcoShelterSubsystem* Shelters = World->GetSubsystem<UEcoShelterSubsystem>();

	for (const FEcoV3StagePlan& Plan : Plans)
	{
		if (!S->Groups.IsValidIndex(Plan.GroupIndex))
		{
			continue;
		}
		const FEcoCreatureSpawnGroup& G = S->Groups[Plan.GroupIndex];
		AEcologyRegion* Region = EcoPolicyV3IntegratedImpl::FindRegion(World, G.RegionId);
		const int32 RegionIndex = Ecology ? Ecology->GetRegionRuntimeIndex(G.RegionId) : Plan.GroupIndex;
		const double Half = 0.5 * Plan.SizeUnits * EcoRepertoireV3::kUnitCm;
		FVector CenterGround = Plan.CenterCm;
		EcoCreatureMovement::ProjectSpawnPoint(*World, Plan.CenterCm, CenterGround);
		FVector Origin = Plan.OriginCm();
		Origin.Z = CenterGround.Z;

		// 우리 은신처: 무대 1/4·3/4 지점 근처의 지면(경사·물·장애물 검사를 통과한 자리)에 AEcoShelterAnchor 를 놓는다.
		// 앵커는 BeginPlay 에서 팀 UEcoShelterSubsystem 에 등록된다 (팀 공개 API). v3 사슴은 원 목록으로만 읽고 예약하지 않는다.
		// 반경 = 무대 한 변 × 0.1 (4~9 단위로 자름) — 무대 크기를 바꿔도 반경·넓이가 학습 범위 안이다
		int32 Extra = 0;
		TArray<FVector> Placed;
		const float R = static_cast<float>(Settings.ExtraCoverRadiusUnits(Plan.SizeUnits) * EcoRepertoireV3::kUnitCm);
		for (int32 k = 0; k < Settings.ExtraCoverCount && Region && Shelters; ++k)
		{
			const double Base = UE_DOUBLE_PI * 0.25 + UE_DOUBLE_HALF_PI * k;
			for (int32 Attempt = 0; Attempt < 24; ++Attempt)
			{
				const double Turn = (Attempt % 2 == 0 ? 1.0 : -1.0) * ((Attempt + 1) / 2) * FMath::DegreesToRadians(15.0);
				const double Rad = 0.25 * Plan.SizeUnits * EcoRepertoireV3::kUnitCm * UE_DOUBLE_SQRT_2 * (Attempt < 12 ? 1.0 : 0.75);
				const FVector Hint(Plan.CenterCm.X + Rad * FMath::Cos(Base + Turn), Plan.CenterCm.Y + Rad * FMath::Sin(Base + Turn), CenterGround.Z);
				if (!Plan.IsInsideStage(Hint, R + 200.0))
				{
					continue;
				}
				bool bOverlap = false;
				for (const FVector& P : Placed)
				{
					bOverlap = bOverlap || FVector::Dist2D(P, Hint) < 2.0 * R + 400.0;
				}
				FVector Ground;
				if (bOverlap || !EcoCreatureMovement::ProjectSpawnPoint(*World, Hint, Ground) || !Region->ContainsPosition(Ground))
				{
					continue;
				}
				FActorSpawnParameters Params;
				Params.Name = MakeUniqueObjectName(World->PersistentLevel, AEcoShelterAnchor::StaticClass(),
												   *FString::Printf(TEXT("EcoV3_Cover_%s_%d"), *G.RegionId.ToString(), k));
				Params.bDeferConstruction = true;
				Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
				const FTransform Xf(Ground);
				if (AEcoShelterAnchor* Anchor = World->SpawnActor<AEcoShelterAnchor>(AEcoShelterAnchor::StaticClass(), Xf, Params))
				{
					Anchor->Radius = R;
					Anchor->Capacity = 4;
					Anchor->Quality = 0.65f;
					Anchor->FinishSpawning(Xf);
					SpawnedCovers.Add(Anchor);
					OurShelterIndices.Add(Anchor->ShelterRuntimeIndex);
					Placed.Add(Ground);
					++Extra;
				}
				break;
			}
		}

		// 은신처 원 목록 = 등록된 은신처 중 중심이 무대 안인 것, RuntimeIndex 순 (HIDE 목표 색인 고정).
		// 레벨 은신처는 반경이 학습 범위(4~9 단위 = 8~18 m)일 때만 넣는다 — 학습에서 본 적 없는 크기(예: 숲의 1.5 m)를 넣으면 근처 사슴이
		// 그 작은 원을 HIDE 목표로 골라 몰리고, cover_dist 관측·은신 판정(포획·탐지 배수)도 학습 밖 크기로 계산된다. 팀 Social 등록은 그대로다
		std::vector<EcoObservationV3::FCoverInput> Covers;
		TArray<double> CoverZ;
		int32 Team = 0;
		int32 Skipped = 0;
		if (Shelters)
		{
			TArray<FEcoShelterPoint> Inside;
			for (const FEcoShelterPoint& P : Shelters->GetShelters())
			{
				if (!Shelters->IsValidShelterIndex(P.RuntimeIndex) || !Plan.IsInsideStage(P.Position))
				{
					continue;
				}
				const bool bOurs = OurShelterIndices.Contains(P.RuntimeIndex);
				const double Ru = static_cast<double>(P.Radius) / EcoRepertoireV3::kUnitCm;
				if (!bOurs && (Ru < FEcoV3IntegratedSettings::kCoverRadiusLoUnits || Ru > FEcoV3IntegratedSettings::kCoverRadiusHiUnits))
				{
					++Skipped;
					continue;
				}
				Team += bOurs ? 0 : 1;
				Inside.Add(P);
			}
			Inside.Sort([](const FEcoShelterPoint& A, const FEcoShelterPoint& B) { return A.RuntimeIndex < B.RuntimeIndex; });
			for (const FEcoShelterPoint& P : Inside)
			{
				Covers.push_back({(P.Position.X - Origin.X) / EcoRepertoireV3::kUnitCm, (P.Position.Y - Origin.Y) / EcoRepertoireV3::kUnitCm,
								  static_cast<double>(P.Radius) / EcoRepertoireV3::kUnitCm});
				CoverZ.Add(P.Position.Z);
			}
		}
		const EcoWorldV3::FWorldConfig Config = MakeRegionWorldConfig(Settings, RegionIndex, G.Herbivores, G.Wolves, Covers);
		FEcoV3RegionContext* Ctx = AddContext(G.RegionId, RegionIndex, Origin, Config, G.Herbivores, G.Wolves);
		Ctx->TeamCovers = Team;
		Ctx->SkippedTeamCovers = Skipped;
		Ctx->ExtraCovers = Extra;
		Ctx->CoverGroundZ = CoverZ;
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] 지역 무대 %s (지역 번호 %d): 원점 (%.0f, %.0f, %.0f), 한 변 %.0f m | 사슴 %d 늑대 %d | 은신처 %d (레벨 %d + v3 %d, v3 반경 %.0f m, ")
				   TEXT("학습 범위 밖이라 뺀 레벨 은신처 %d) | t=%lld"),
			   *G.RegionId.ToString(), RegionIndex, Origin.X, Origin.Y, Origin.Z, Half * 2.0 / 100.0, G.Herbivores, G.Wolves,
			   static_cast<int32>(Covers.size()), Team, Extra, R / 100.0f, Skipped, static_cast<long long>(GlobalT));
		for (const FString& Why : UEcoPolicyV3Subsystem::CheckTrainingRange(Config))
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 지역 %s 학습 범위 밖: %s"), *G.RegionId.ToString(), *Why);
		}
	}
}

FEcoV3RegionContext* UEcoPolicyV3IntegratedSubsystem::AddContext(FName RegionId, int32 RegionRuntimeIndex, const FVector& OriginCm,
																 const EcoWorldV3::FWorldConfig& Config, int32 PlannedDeer,
																 int32 PlannedWolves)
{
	TUniquePtr<FEcoV3RegionContext> Ctx = MakeUnique<FEcoV3RegionContext>();
	Ctx->RegionId = RegionId;
	Ctx->RegionRuntimeIndex = RegionRuntimeIndex;
	Ctx->Index = Contexts.Num();
	Ctx->OriginCm = OriginCm;
	Ctx->SizeUnits = Config.WorldSize;
	Ctx->PlannedDeer = PlannedDeer;
	Ctx->PlannedWolves = PlannedWolves;
	EcoWorldV3::InitWorld(Ctx->Sim, Config);
	Ctx->Sim.T = GlobalT;
	EcoWorldV3::UpdateDayNight(Ctx->Sim);
	Ctx->LastLogT = GlobalT;
	FEcoV3RegionContext* Raw = Ctx.Get();
	Contexts.Add(MoveTemp(Ctx));
	return Raw;
}

FEcoV3RegionContext* UEcoPolicyV3IntegratedSubsystem::FindContext(FName RegionId)
{
	for (const TUniquePtr<FEcoV3RegionContext>& Ctx : Contexts)
	{
		if (Ctx->RegionId == RegionId)
		{
			return Ctx.Get();
		}
	}
	return nullptr;
}

void UEcoPolicyV3IntegratedSubsystem::CheckClockDrift()
{
	const UWorld* World = GetWorld();
	const UEcoWorldClockSubsystem* TeamClock = World ? World->GetSubsystem<UEcoWorldClockSubsystem>() : nullptr;
	if (!TeamClock || !TeamClock->IsClockRunning())
	{
		return;
	}
	const int64 TeamT = FMath::RoundToInt64(TeamClock->GetServerTime().ServerTimeSeconds / EcoPolicyV3IntegratedImpl::kStepSeconds);
	if (FMath::Abs(TeamT - GlobalT) > 4)
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 전역 스텝을 팀 시계에 다시 맞춘다 (v3 %lld → 팀 %lld)"), static_cast<long long>(GlobalT),
			   static_cast<long long>(TeamT));
		GlobalT = TeamT;
		for (const TUniquePtr<FEcoV3RegionContext>& Ctx : Contexts)
		{
			SyncContextClock(*Ctx);
		}
	}
}

void UEcoPolicyV3IntegratedSubsystem::SyncContextClock(FEcoV3RegionContext& Ctx) const
{
	if (Ctx.Sim.T != GlobalT)
	{
		Ctx.Sim.T = GlobalT;
		EcoWorldV3::UpdateDayNight(Ctx.Sim);
	}
}

int32 UEcoPolicyV3IntegratedSubsystem::AdvanceClock(float DeltaSeconds)
{
	if (!bActive)
	{
		return 0;
	}
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	return EcoPolicy::ConsumeSteps(ClockPhase, Clock.Advance(DeltaSeconds, EcoBehaviorConfig::StepSeconds, Interval), Interval);
}

float UEcoPolicyV3IntegratedSubsystem::GetVisualAlpha() const
{
	const int32 Interval = FMath::Max(EcoBehaviorConfig::PolicyInterval, 1);
	return FMath::Clamp(static_cast<float>(ClockPhase) / static_cast<float>(Interval), 0.0f, 1.0f);
}

// -----------------------------------------------------------------------------
// 기록·표시
// -----------------------------------------------------------------------------

void UEcoPolicyV3IntegratedSubsystem::NotifyContextStep(FEcoV3RegionContext& Ctx, const EcoWorldV3::FStepReport& Report)
{
	const UWorld* World = GetWorld();
	const double Now = World ? World->GetTimeSeconds() : 0.0;
	Ctx.RecentCatches.RemoveAll([Now](const FEcoV3IntegratedCatchMark& M) { return Now - M.Time > 2.0; });
	if (LogEverySteps > 0 && Ctx.Sim.T - Ctx.LastLogT >= LogEverySteps)
	{
		LogContext(Ctx);
	}
}

void UEcoPolicyV3IntegratedSubsystem::LogContext(FEcoV3RegionContext& Ctx)
{
	using namespace EcoV3Integrated;
	const EcoWorldV3::FWorldStats& S = Ctx.Sim.Stats;
	const EcoWorldV3::FWorldStats& P = Ctx.LastLogStats;
	const double Seconds = static_cast<double>(Ctx.Sim.T) * EcoRepertoireV3::kStepSeconds;

	FString TeamPhase = TEXT("팀 시계 없음");
	if (const UWorld* World = GetWorld())
	{
		if (const UEcoWorldClockSubsystem* TeamClock = World->GetSubsystem<UEcoWorldClockSubsystem>(); TeamClock && TeamClock->IsClockRunning())
		{
			const FEcoServerTimeSnapshot Snap = TeamClock->GetServerTime();
			TeamPhase = FString::Printf(TEXT("팀 시계 %s %.1f/%.0f초"), Snap.DayCycle.Phase == EEcoDayPhase::Day ? TEXT("낮") : TEXT("밤"),
										Snap.ServerTimeSeconds - Snap.DayCycle.PhaseStartSeconds,
										Snap.DayCycle.PhaseEndSeconds - Snap.DayCycle.PhaseStartSeconds);
		}
	}
	bool bAllFour = true;
	FString Now;
	FString Used;
	for (int32 b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
	{
		bAllFour = bAllFour && (b == EcoRepertoireV3::kSleep || S.BehaviorSteps[b] > 0);
		Now += FString::Printf(TEXT(" %s %d"), BehaviorNameKo(b), Ctx.BehaviorNow[b]);
		Used += FString::Printf(TEXT(" %s %lld"), BehaviorNameKo(b), static_cast<long long>(S.BehaviorSteps[b] - P.BehaviorSteps[b]));
	}
	FString WolfNow;
	for (int32 w = 0; w < static_cast<int32>(EWolfState::Count); ++w)
	{
		WolfNow += FString::Printf(TEXT(" %s %d"), WolfStateNameKo(static_cast<EWolfState>(w)), Ctx.WolvesNow[w]);
	}
	const double CpuAvgMs = StepCpuSteps > 0 ? 1000.0 * StepCpuSeconds / static_cast<double>(StepCpuSteps) : 0.0;
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] %s | %.1f초 %s d=%.2f (%s) | 사슴 산 %d/%d | 지금 행동:%s | 구간 사용(개체·스텝):%s | 늑대 %d:%s | ")
			   TEXT("포획 %lld (누적 %lld) 굶음 %lld (누적 %lld) | 지형 검사 이동 %lld, 막힘 사슴 %lld 늑대 %lld | 피식EMA %.3f | 마스크 위반 %lld | 네 행동 모두 씀=%s | ")
			   TEXT("결정 스텝 CPU(모든 지역) 평균 %.2f ms/스텝, 최대 %.1f ms/프레임"),
		   *Ctx.RegionId.ToString(), Seconds, Ctx.Sim.Dark >= 0.5 ? TEXT("밤") : TEXT("낮"), Ctx.Sim.Dark, *TeamPhase, Ctx.AliveDeer,
		   Ctx.AdoptedDeer, *Now, *Used, Ctx.Wolves, *WolfNow, static_cast<long long>(S.Caught - P.Caught),
		   static_cast<long long>(S.Caught), static_cast<long long>(S.Starved - P.Starved), static_cast<long long>(S.Starved),
		   static_cast<long long>(Ctx.TerrainChecks - Ctx.LastLogTerrainChecks),
		   static_cast<long long>(S.BlockedHerbMoves - P.BlockedHerbMoves), static_cast<long long>(S.BlockedThreatMoves - P.BlockedThreatMoves),
		   Ctx.Sim.PredEma, static_cast<long long>(S.MaskViolations), bAllFour ? TEXT("예") : TEXT("아니오"), CpuAvgMs,
		   1000.0 * StepCpuMaxFrameSeconds);
	// 부활이 없어서 산 사슴이 줄면 학습 밀도 하한 아래로 내려간다 — 그 뒤 동족 수·무리 중심·분리 입력은 학습 범위 밖일 수 있다 (한 번만 알린다)
	if (!Ctx.bReportedLowDensity && Ctx.AdoptedDeer > 0 && FEcoV3IntegratedSettings::IsBelowTrainingDensity(Ctx.AliveDeer, Ctx.SizeUnits))
	{
		Ctx.bReportedLowDensity = true;
		UE_LOG(LogEcoPolicyV3I, Warning,
			   TEXT("[EcoV3I] %s: 산 사슴 %d 마리 — 무대 %.0f 단위에서 학습 밀도 하한(%.1f 마리 = 128/110² 마리/단위²) 아래로 내려갔다. ")
				   TEXT("부활이 없어서 생기는 근사다 (이 뒤 동족 관측은 학습 범위 밖일 수 있다. 다시 보려면 Play 를 다시 누른다)"),
			   *Ctx.RegionId.ToString(), Ctx.AliveDeer, Ctx.SizeUnits,
			   FEcoV3IntegratedSettings::kTrainDeer * Ctx.SizeUnits * Ctx.SizeUnits / (110.0 * 110.0));
	}
	Ctx.LastLogT = Ctx.Sim.T;
	Ctx.LastLogStats = S;
	Ctx.LastLogTerrainChecks = Ctx.TerrainChecks;
}

bool UEcoPolicyV3IntegratedSubsystem::TraceMove(FName RegionId, const FVector& FromCm, const FVector& ToCm, double& OutZ) const
{
	OutZ = FromCm.Z;
	UWorld* World = GetWorld();
	if (!World)
	{
		return false;
	}
	const double Dist = FVector::Dist2D(FromCm, ToCm);
	if (Dist < 1.0)
	{
		return true;   // 길이 0 쓸기는 처음 겹침을 막힘으로 볼 수 있다 — 움직이지 않은 것으로 본다
	}
	const int32 Pieces = FMath::Max(1, FMath::CeilToInt32(Dist / EcoPolicyV3IntegratedImpl::kSubStepCm));
	FVector Cur = FromCm;
	for (int32 k = 1; k <= Pieces; ++k)
	{
		const double A = static_cast<double>(k) / static_cast<double>(Pieces);
		FVector Next(FMath::Lerp(FromCm.X, ToCm.X, A), FMath::Lerp(FromCm.Y, ToCm.Y, A), Cur.Z);
		if (!EcoCreatureMovement::ConstrainStep(*World, RegionId, false, Cur, Next))
		{
			return false;
		}
		Cur = Next;
	}
	OutZ = Cur.Z;
	return true;
}

void UEcoPolicyV3IntegratedSubsystem::UpdateViewEnvironment()
{
	if (!bActive)
	{
		return;
	}
	if (!bMigrationDebugHidden)
	{
		UEcoRuntimeSettings* RuntimeSettings = GetMutableDefault<UEcoRuntimeSettings>();
		bSavedMigrationDebug = RuntimeSettings->bDrawMigrationDebug;
		RuntimeSettings->bDrawMigrationDebug = false;   // 기본 객체만 바꾼다. SaveConfig 를 부르지 않는다
		bMigrationDebugHidden = true;
	}
	IConsoleVariable* Limit = IConsoleManager::Get().FindConsoleVariable(TEXT("r.DebugSafeZone.MaxDebugTextStringsPerActor"));
	const bool bDebug = IsDebugDrawEnabled();
	if (Limit && bDebug && !bTextLimitRaised)
	{
		SavedTextLimit = Limit->GetInt();
		Limit->Set(0, ECVF_SetByCode);
		bTextLimitRaised = true;
	}
	else if (Limit && !bDebug && bTextLimitRaised)
	{
		Limit->Set(SavedTextLimit, ECVF_SetByCode);
		bTextLimitRaised = false;
	}
}

void UEcoPolicyV3IntegratedSubsystem::RestoreViewEnvironment()
{
	if (bMigrationDebugHidden)
	{
		GetMutableDefault<UEcoRuntimeSettings>()->bDrawMigrationDebug = bSavedMigrationDebug;
		bMigrationDebugHidden = false;
	}
	if (bTextLimitRaised)
	{
		if (IConsoleVariable* Limit = IConsoleManager::Get().FindConsoleVariable(TEXT("r.DebugSafeZone.MaxDebugTextStringsPerActor")))
		{
			Limit->Set(SavedTextLimit, ECVF_SetByCode);
		}
		bTextLimitRaised = false;
	}
}

void UEcoPolicyV3IntegratedSubsystem::DrawOverlay()
{
	using namespace EcoV3Integrated;
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	const double Now = World->GetTimeSeconds();
	const bool bScreen = GEngine && Now >= NextScreenTally;
	if (bScreen)
	{
		NextScreenTally = Now + 1.0;
	}
	for (const TUniquePtr<FEcoV3RegionContext>& Ptr : Contexts)
	{
		const FEcoV3RegionContext& Ctx = *Ptr;
		const double Half = 0.5 * Ctx.SizeCm();
		const FVector Center = Ctx.OriginCm + FVector(Half, Half, 300.0);
		DrawDebugBox(World, Center, FVector(Half, Half, 0.0), FColor(30, 30, 30), false, -1.0f, 0, 20.0f);
		const FColor CoverColor(85, 102, 170);
		for (int32 k = 0; k < static_cast<int32>(Ctx.Sim.Config.Covers.size()); ++k)
		{
			const EcoObservationV3::FCoverInput& C = Ctx.Sim.Config.Covers[static_cast<size_t>(k)];
			const double Z = Ctx.CoverGroundZ.IsValidIndex(k) ? Ctx.CoverGroundZ[k] : Ctx.OriginCm.Z;
			const FVector P = Ctx.UnitsToCm(C.X, C.Y, Z + 60.0);
			const float R = static_cast<float>(C.Radius * EcoRepertoireV3::kUnitCm);
			DrawDebugCircle(World, P, R, 48, CoverColor, false, -1.0f, 0, 10.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
		}
		for (const FEcoV3IntegratedCatchMark& M : Ctx.RecentCatches)
		{
			DrawDebugSphere(World, M.Location + FVector(0, 0, 150.0), 350.0f, 12, FColor::Orange, false, -1.0f, 0, 8.0f);
		}
		FString Tally;
		for (int32 b = 0; b < EcoRepertoireV3::kSleep; ++b)
		{
			Tally += FString::Printf(TEXT(" %s %d"), BehaviorNameKo(b), Ctx.BehaviorNow[b]);
		}
		FString Wolves;
		for (int32 w = 0; w < static_cast<int32>(EWolfState::Count); ++w)
		{
			if (Ctx.WolvesNow[w] > 0)
			{
				Wolves += FString::Printf(TEXT(" %s %d"), WolfStateNameKo(static_cast<EWolfState>(w)), Ctx.WolvesNow[w]);
			}
		}
		const FString Line = FString::Printf(TEXT("v3 R1b %s | %s d=%.2f | 사슴 %d/%d:%s | 늑대%s | 포획 %lld 굶음 %lld"),
											 *Ctx.RegionId.ToString(), Ctx.Sim.Dark >= 0.5 ? TEXT("밤") : TEXT("낮"), Ctx.Sim.Dark,
											 Ctx.AliveDeer, Ctx.AdoptedDeer, *Tally, *Wolves,
											 static_cast<long long>(Ctx.Sim.Stats.Caught), static_cast<long long>(Ctx.Sim.Stats.Starved));
		DrawDebugString(World, Center + FVector(0, 0, 600.0), Line, nullptr, FColor::White, 0.0f, true, 1.4f);
		if (bScreen)
		{
			GEngine->AddOnScreenDebugMessage(static_cast<uint64>(730000 + Ctx.Index), 1.5f, FColor(180, 230, 180), Line);
		}
	}
}

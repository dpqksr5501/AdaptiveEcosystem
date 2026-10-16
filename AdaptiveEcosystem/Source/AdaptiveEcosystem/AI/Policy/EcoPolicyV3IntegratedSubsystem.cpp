#include "EcoPolicyV3IntegratedSubsystem.h"

#include "AI/Social/Shelter/EcoShelterAnchor.h"
#include "AI/Social/Shelter/EcoRefugeHabitat.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Core/EcoRuntimeSettings.h"
#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
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
#include "Misc/App.h"
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
		TEXT("3 = 모든 사슴은 v3 R1b 학습 두뇌, 늑대는 학습 위협 규칙. Play 전에 바꾼다 (서버·단독 권위, Client는 표현만). ")
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
	// 10-17 팀 브랜치 통합 (계획서 4-5b): 은신처 안전 규칙은 하나다. ShelterSafe 1(기본)이면 파이썬 realism_shelter 가 안전(표적·포획 제외·늑대 진입 금지)을
	// 맡고, 이 스위치는 실제 은신처 생명주기(지워진 은신처 비활성·늦게 등록된 은신처 추가·잃은 HIDE 목표 풀기·Social 도착은 원 안일 때만·[EcoRefuge] 기록)만 더한다.
	// ShelterSafe 0 일 때만 조연우 님 규칙(늑대 몸 여유 1 m·쓸고 지나가기 막기·갇힌 늑대 꺼내기·원 안 사슴 표적 제외)이 안전을 맡는다. 둘이 한꺼번에 적용되지 않는다
	static TAutoConsoleVariable<int32> CVarProtectedRefuges(TEXT("eco.IntegratedV3.ProtectedRefuges"),1,
		TEXT("통합 v3 실제 은신처 생명주기 (1 = 켬, 기본 — 조연우 님 a88eac8). 지워진 은신처는 원 목록에서 비활성(번호는 그대로), 늦게 등록된 무대 안 은신처는 끝에 더하고, ")
		TEXT("목표 은신처를 잃은 HIDE 사슴은 도주·먹기로 돌아가며, Social 도착은 몸이 원 안일 때만 인정한다. 안전 규칙은 eco.IntegratedV3.ShelterSafe 1 이면 파이썬 규칙이고, ")
		TEXT("ShelterSafe 0 일 때만 이 스위치가 팀 규칙(늑대 몸 여유 1 m·쓸고 지나가기 막기·갇힌 늑대 꺼내기)으로 안전을 맡는다. 0 = 생명주기도 끔. Play 전에 바꾼다. ")
		TEXT("명령줄 -EcoV3ProtectedRefuges= 는 시작값."),ECVF_Default);
	static TAutoConsoleVariable<int32> CVarSocialControl(TEXT("eco.IntegratedV3.SocialControl"),1,
		TEXT("통합 v3 사슴의 Social 행동 연결 (1 = 켬, 기본 — 조연우 님 22eb1b6). 무리 경보(Alert·Panic·Recovering)와 은신처 슬롯 예약이 v3 제어 뒤·이동 전에 ")
		TEXT("사슴 제어를 바꾼다(EcoWorldV3 FStepHooks::HerbControl). 0 = 연결하지 않는다(Social 처리기는 그대로 돌고 v3 사슴 움직임만 파이썬 세계 그대로 — 견줌용). ")
		TEXT("Play 전에 바꾼다. 명령줄 -EcoV3SocialControl= 는 시작값."),ECVF_Default);

	static TAutoConsoleVariable<int32> CVarGradualNight(
		TEXT("eco.IntegratedV3.GradualNight"),
		1,
		TEXT("통합 v3 모드의 늑대 밤잠 점진화 (1 = 켬, 기본 — 사람 결정 H1 10-14). 해 진 뒤 늑대마다 다른 지연이 지나고 사냥 중이 아니고 ")
		TEXT("16 m 안에 사슴이 없으면 2 초 동안 걸음을 늦추다 눕는다. 깜깜하면 새 사냥을 시작하지 않고 쫓던 사냥만 끝낸다. 새벽에는 하나씩 ")
		TEXT("깨어 걸음을 올린다 (파이썬 configs/v3_real1_night_on.yaml realism_night). 0 = 어둠 0.5 가 되는 순간 곧바로 잔다. Play 전에 바꾼다."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarNoFreeze(
		TEXT("eco.IntegratedV3.NoFreeze"),
		1,
		TEXT("통합 v3 모드의 사슴 얼기 막음 (1 = 막음, 기본 — 사람 결정 10-15 (A)). 마스크가 FREEZE 를 늘 막는다(R1b−F: R1b 가중치 그대로, ")
		TEXT("얼던 자리에서는 R1b 의 다음 선호 행동). 0 = R1b 그대로 얼기를 쓴다. Play 전에 바꾼다. 명령줄 -EcoV3NoFreeze= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarWolfEatSeconds(
		TEXT("eco.IntegratedV3.WolfEatSeconds"),
		5.0f,
		TEXT("통합 v3 모드의 늑대 식사 길이 (초, 기본 5 — 사람 결정 10-15 (B)). 잡은 늑대는 시체 곁에 서서 이만큼 먹고 곧바로 다시 사냥한다 ")
		TEXT("(포만 없음). 결정 스텝 = 반올림(초 ÷ 2/15) — 5 초 = 38 스텝(5.07 초). 0.67 이하 = 옛 규칙(학습 세계 5 스텝, 그동안 배회). ")
		TEXT("Play 전에 바꾼다. 명령줄 -EcoV3WolfEatSeconds= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarWildFlight(
		TEXT("eco.IntegratedV3.WildFlight"),
		1,
		TEXT("통합 v3 모드의 사슴 도주 반사 거리 (1 = 켬, 기본 — 사람 결정 10-15 (7) 야생 1단계 w3). 사냥 중인 늑대를 실제로 알아채면(시야·발소리) ")
		TEXT("경계 거리(AlertDistM 30 m) 안에서 먹으며 멀어지고, 도주 거리(PanicDistM 15 m) 안이거나 다가오면 안전 거리(SafeDistM 40 m) 밖·은신처까지 뛴다. ")
		TEXT("은신처 안이면 웅크린다. 먹는·쉬는 늑대는 경계만, 자는 늑대는 무시. 두뇌 위의 세계 규칙 (가중치 그대로). 경계 거리 실험 eco.IntegratedV3.KeepAway 를 ")
		TEXT("바꿨다. 0 = 두뇌 그대로. Play 전에 바꾼다. 명령줄 -EcoV3WildFlight= (옛 이름 -EcoV3KeepAway= 도 받음) 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarAlertDistM(
		TEXT("eco.IntegratedV3.AlertDistM"),
		30.0f,
		TEXT("통합 v3 모드 사슴 경계 거리 (m, 기본 30). 깨어 있는 늑대가 이 안이면 먹기를 멈추고 걸어서(360 cm/s) 멀어진다. Play 전에 바꾼다."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarPanicDistM(
		TEXT("eco.IntegratedV3.PanicDistM"),
		15.0f,
		TEXT("통합 v3 모드 사슴 위험 거리 (m, 기본 15). 늑대가 이 안이면(또는 다가오면) 뛰어서 안전해질 때까지 달아난다. Play 전에 바꾼다."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarSafeDistM(
		TEXT("eco.IntegratedV3.SafeDistM"),
		40.0f,
		TEXT("통합 v3 모드 사슴 안전 거리 (m, 기본 40). 깨어 있는 늑대가 모두 이 밖이고 아무도 쫓지 않으면 도망을 멈춘다 (경계·위험 거리보다 작으면 그 값으로 올린다). Play 전에 바꾼다."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarWildReserve(
		TEXT("eco.IntegratedV3.WildReserve"),
		1,
		TEXT("통합 v3 모드의 사슴 지방 비축 (1 = 켬, 기본 — 사람 결정 10-15 (7) 야생 1단계 w1). 배가 비어도(에너지 0) 몸의 비축으로 3일(게임 하루 2분 → 6분) ")
		TEXT("버티고, 비축까지 바닥나야 굶어 죽는다. 배가 70% 이상일 때 먹으면 먹은 몫의 1/4 이 비축으로 간다. 배가 바닥(10% 밑)인 사슴은 0.75 배로 ")
		TEXT("느리다. 값 = 파이썬 configs/v3_wild1_mirror.yaml wild_reserve. 0 = 에너지 0 이면 곧바로 굶어 죽는다(지금까지). Play 전에 바꾼다. ")
		TEXT("명령줄 -EcoV3WildReserve= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarWildSatiation(
		TEXT("eco.IntegratedV3.WildSatiation"),
		1,
		TEXT("통합 v3 모드의 늑대 포만 (1 = 켬, 기본 — 사람 결정 10-15 (7) 야생 1단계 w2). 사슴을 잡은 늑대는 먹기(WolfEatSeconds)가 끝나면 ")
		TEXT("반나절(450 스텝 = 60초) 동안 사냥하지 않고 0.3 배 속력으로 어슬렁거린다. 쉬는 늑대도 사슴 눈에 보인다. 값 = 파이썬 configs/v3_wild1_mirror.yaml ")
		TEXT("wild_satiation. 0 = 먹기가 끝나면 곧바로 사냥(지금까지). Play 전에 바꾼다. 명령줄 -EcoV3WildSatiation= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarFlightHoldAwake(
		TEXT("eco.IntegratedV3.FlightHoldAwake"),
		1,
		TEXT("통합 v3 모드 도주 붙잡기 (1 = 켬, 기본 — 10-16 hold_awake). 시작한 도주는 깨어 있는 늑대(먹기·배부름 포함) 모두가 안전 거리 밖일 때까지 이어진다. ")
		TEXT("0 = 사냥 중인 늑대만 붙잡는다(857da45, 늑대가 먹기 시작하면 도주가 풀린다). eco.IntegratedV3.WildFlight 1 일 때만 뜻이 있다. Play 전에 바꾼다. ")
		TEXT("명령줄 -EcoV3FlightHoldAwake= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarFlightEdgeAvoid(
		TEXT("eco.IntegratedV3.FlightEdgeAvoid"),
		1,
		TEXT("통합 v3 모드 가장자리 굽히기 (1 = 켬, 기본 — 10-16 edge_r 5 = 10 m). 무대 가장자리 10 m 안의 경계·도주 방향을 벽을 따라·모서리 밖으로 굽힌다. ")
		TEXT("0 = 굽히지 않는다(857da45). eco.IntegratedV3.WildFlight 1 일 때만 뜻이 있다. Play 전에 바꾼다. 명령줄 -EcoV3FlightEdgeAvoid= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarShelterSafe(
		TEXT("eco.IntegratedV3.ShelterSafe"),
		1,
		TEXT("통합 v3 모드의 은신처 안전·늑대 진입 금지 (1 = 켬, 기본 — 사용자 보고 10-16 '은신처 안에서도 잡힌다'). 은신처 원 안 사슴은 무엇을 하든 ")
		TEXT("늑대의 표적이 되지 않고 잡히지 않는다. 늑대는 은신처 원 안으로 들어가지 못하고 둘레를 따라 미끄러진다. 값 = 파이썬 configs/v3_wild1_mirror.yaml ")
		TEXT("realism_shelter (R3 값). 0 = 은신처 안에서도 잡힘(지금까지). Play 전에 바꾼다. 명령줄 -EcoV3ShelterSafe= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarRealismVision(
		TEXT("eco.IntegratedV3.RealismVision"),
		1,
		TEXT("통합 v3 모드의 사슴 위협 시야 (1 = 300°, 기본 — 사람 결정 10-15 (7) 야생 1단계, R3 realism_vision). 사슴은 옆·뒤의 늑대도 본다(바로 뒤 60° 만 사각). ")
		TEXT("반경·밤·고개 숙임 배수는 그대로. 0 = 앞쪽 120°(R1b 학습 세계). Play 전에 바꾼다. 명령줄 -EcoV3RealismVision= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarRealismHearing(
		TEXT("eco.IntegratedV3.RealismHearing"),
		1,
		TEXT("통합 v3 모드의 늑대 발소리 (1 = 켬, 기본 — 야생 1단계, R3 realism_hearing). 쫓아 달리는 늑대는 멀리(속력에 따라 최대 40 m), 어슬렁거리는·쉬는 ")
		TEXT("늑대는 4 m 안에서만, 서 있는 늑대는 들리지 않는다. 들리면 방향과 무관하게 알아챈다. 0 = 소리 없음(R1b 학습 세계). Play 전에 바꾼다. ")
		TEXT("명령줄 -EcoV3RealismHearing= 는 시작값."),
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

EcoV3Integrated::EWolfState EcoV3Integrated::WolfStateOf(const EcoWorldV3::FThreatAgent& A, const EcoThreatV3::FThreatConfig& Cfg)
{
	if (A.State.bAsleep)
	{
		return EWolfState::Sleep;
	}
	const bool bNight = Cfg.bRealismNight && !A.Spec.bNocturnal;
	if (bNight && A.State.bNightSettle)
	{
		return EWolfState::Settle;
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
	if (bNight && A.State.NightAct < Cfg.NightRampSteps)
	{
		return EWolfState::Waking;
	}
	return EWolfState::Roam;
}

const TCHAR* EcoV3Integrated::WolfStateNameKo(EWolfState State)
{
	static const TCHAR* Names[static_cast<int32>(EWolfState::Count)] = {TEXT("배회"), TEXT("잠행"), TEXT("돌진"), TEXT("지침"),
																		  TEXT("추격"), TEXT("식사"), TEXT("잠"),  TEXT("눕는 중"),
																		  TEXT("깨는 중")};
	const int32 I = static_cast<int32>(State);
	return (I >= 0 && I < static_cast<int32>(EWolfState::Count)) ? Names[I] : TEXT("?");
}

const TCHAR* EcoV3Integrated::BehaviorNameKo(int32 B)
{
	static const TCHAR* Names[EcoRepertoireV3::kNumBehaviors] = {TEXT("먹기"), TEXT("도망"), TEXT("숨기"), TEXT("얼기"), TEXT("잠")};
	return (B >= 0 && B < EcoRepertoireV3::kNumBehaviors) ? Names[B] : TEXT("?");
}

const TCHAR* EcoV3Integrated::KeepModeNameKo(int32 KeepMode)
{
	static const TCHAR* Names[EcoWorldV3::kNumKeepModes] = {TEXT("두뇌"), TEXT("경계(먹으며 멀어짐)"), TEXT("도주(안전해질 때까지)"),
															 TEXT("웅크림(은신처·경계)")};
	return (KeepMode >= 0 && KeepMode < EcoWorldV3::kNumKeepModes) ? Names[KeepMode] : TEXT("?");
}

FString EcoV3Integrated::DeerLabel(const EcoRepertoireV3::FRepState& Rep, const EcoWorldV3::FHerbBody& Body, bool bRecentRepro,
								   FColor& OutColor, int32 KeepMode, bool bReserveOn)
{
	const double E = FMath::Clamp(Body.Energy, 0.0, 1.0);
	// 도주 반사 거리 덮기 중이면 행동 이름 대신 덮기 이름 ('경계(먹으며 멀어짐) 64%', '도주(안전해질 때까지) 58%').
	// 경계는 두뇌가 먹기를 고른 동안만 (두뇌가 도망·숨기·잠이면 그 행동 이름 그대로 — world.py _wf_alert_control 과 같은 조건)
	const bool bKeep = KeepMode == EcoWorldV3::kKeepPanic || KeepMode == EcoWorldV3::kKeepShelter
					   || (KeepMode == EcoWorldV3::kKeepAlert && Rep.Behavior == EcoRepertoireV3::kGraze);
	FString Label = bKeep ? FString::Printf(TEXT("%s %d%%"), KeepModeNameKo(KeepMode), FMath::RoundToInt32(100.0 * E))
						  : FString::Printf(TEXT("%s%s %d%%"), BehaviorNameKo(Rep.Behavior),
											Rep.Behavior == EcoRepertoireV3::kHide && Rep.bArrived ? TEXT("(웅크림)") : TEXT(""),
											FMath::RoundToInt32(100.0 * E));
	if (Body.LastIntake > 0.0)
	{
		// 먹이 단위 × 0.5 = 에너지 (FoodEnergyPerUnit). 한 스텝 많아야 0.06 단위 = 3.0 %p
		const double GainPct = 100.0 * Body.LastIntake * EcoRepertoireV3::kR1bConfig.FoodEnergyPerUnit;
		Label += GainPct >= 0.05 ? FString::Printf(TEXT(" +%.1f"), GainPct) : FString(TEXT(" +"));
	}
	OutColor = Rep.Behavior == EcoRepertoireV3::kGraze	  ? FColor(70, 200, 70)
			   : Rep.Behavior == EcoRepertoireV3::kFlee	  ? FColor(255, 215, 0)
			   : Rep.Behavior == EcoRepertoireV3::kHide	  ? FColor(60, 150, 255)
			   : Rep.Behavior == EcoRepertoireV3::kFreeze ? FColor(245, 245, 245)
														  : FColor(170, 70, 210);
	if (bKeep)
	{
		OutColor = KeepMode == EcoWorldV3::kKeepAlert ? FColor(255, 175, 80)
				   : KeepMode == EcoWorldV3::kKeepPanic ? FColor(255, 110, 20)
														: FColor(60, 150, 255);
	}
	if (bReserveOn)
	{
		// 야생 (w1) 지방 비축: 배가 비어도 비축으로 버틴다. 굶음 = 배·비축 모두 0
		const int32 RPct = FMath::RoundToInt32(100.0 * FMath::Clamp(Body.Reserve, 0.0, 1.0));
		if (E < kStarvingEnergy)
		{
			Label += Body.Reserve > 0.0 ? FString::Printf(TEXT(" 배고픔 비축 %d%%"), RPct) : FString(TEXT(" 배고픔 비축 바닥"));
			OutColor = FColor(255, 80, 80);
		}
		else if (Body.Reserve < kLowReserve)
		{
			Label += FString::Printf(TEXT(" 비축 %d%%"), RPct);
		}
		if (Body.bWeak)
		{
			Label += TEXT(" 약함(느림)");
		}
	}
	else if (E < kStarvingEnergy)
	{
		Label += TEXT(" 굶주림");
		OutColor = FColor(255, 80, 80);
	}
	if (bRecentRepro)
	{
		Label += TEXT(" 번식");   // 에너지 0.9 초과 → 0.5 (학습 세계 규칙 — 학습 세계도 새끼는 나오지 않는다, 개체 수 128 고정)
	}
	return Label;
}

FString EcoV3Integrated::WolfLabel(const EcoWorldV3::FThreatAgent& A, const EcoThreatV3::FThreatConfig& Cfg, double Dark, FColor& OutColor)
{
	if (Cfg.bWildSatiation && A.Last.bSated && !A.State.bAsleep)
	{
		// 야생 (w2) 늑대 포만: 먹은 뒤 쉬며 어슬렁거림 (사냥하지 않는다). 남은 배부름 = SatLeft × 2/15 초
		OutColor = FColor(150, 210, 150);
		return FString::Printf(TEXT("늑대 배부름·쉼 %.0f초%s"), static_cast<double>(A.State.SatLeft) * EcoRepertoireV3::kStepSeconds,
							   A.Spec.Type == EcoThreatV3::EThreatType::Stalker ? TEXT(" (잠행형)") : TEXT(" (추격형)"));
	}
	const EWolfState St = WolfStateOf(A, Cfg);
	OutColor = St == EWolfState::Pounce								  ? FColor(255, 120, 0)
			   : St == EWolfState::Sleep							  ? FColor(60, 60, 160)
			   : St == EWolfState::Settle || St == EWolfState::Waking ? FColor(120, 120, 220)
			   : St == EWolfState::Stalk || St == EWolfState::Chase	  ? FColor::Red
			   : St == EWolfState::Roam								  ? FColor(220, 150, 150)
																	  : FColor(150, 150, 150);
	// 식사 중이면 남은 식사 = 쿨다운 × 2/15 초 ('늑대 식사 3.2초 (잠행형)')
	const FString EatLeft = St == EWolfState::Eat
								? FString::Printf(TEXT(" %.1f초"), static_cast<double>(A.State.Cooldown) * EcoRepertoireV3::kStepSeconds)
								: FString();
	FString Label = FString::Printf(TEXT("늑대 %s%s%s"), WolfStateNameKo(St), *EatLeft,
									A.Spec.Type == EcoThreatV3::EThreatType::Stalker ? TEXT(" (잠행형)") : TEXT(" (추격형)"));
	if (!Cfg.bRealismNight || A.Spec.bNocturnal || A.State.bAsleep)
	{
		return Label;
	}
	if ((St == EWolfState::Settle || St == EWolfState::Waking) && Cfg.NightRampSteps > 0)
	{
		Label += FString::Printf(TEXT(" 걸음 %d%%"), FMath::RoundToInt32(100.0 * A.State.NightAct / Cfg.NightRampSteps));
	}
	if (A.LastNight.bBlockDeer)
	{
		Label += TEXT(" · 사슴 곁이라 안 누움");
	}
	else if (A.LastNight.bBlockHunt)
	{
		Label += TEXT(" · 사냥 중이라 안 누움");
	}
	else if (St != EWolfState::Settle && Dark >= Cfg.NightHuntDark && !A.State.bNightHunt && !A.Last.bHunting)
	{
		Label += TEXT(" · 깜깜해 새 사냥 안 함");   // 눕는 중은 어차피 사냥하지 않으므로 붙이지 않는다
	}
	return Label;
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
	S.bGradualNight = CVarGradualNight.GetValueOnGameThread() != 0;
	S.bNoFreeze = CVarNoFreeze.GetValueOnGameThread() != 0;
	S.WolfEatSeconds = static_cast<double>(CVarWolfEatSeconds.GetValueOnGameThread());
	S.bWildFlight = CVarWildFlight.GetValueOnGameThread() != 0;
	S.AlertDistM = static_cast<double>(CVarAlertDistM.GetValueOnGameThread());
	S.PanicDistM = static_cast<double>(CVarPanicDistM.GetValueOnGameThread());
	S.SafeDistM = static_cast<double>(CVarSafeDistM.GetValueOnGameThread());
	S.bWildReserve = CVarWildReserve.GetValueOnGameThread() != 0;
	S.bWildSatiation = CVarWildSatiation.GetValueOnGameThread() != 0;
	S.bRealismVision = CVarRealismVision.GetValueOnGameThread() != 0;
	S.bRealismHearing = CVarRealismHearing.GetValueOnGameThread() != 0;
	S.bShelterSafe = CVarShelterSafe.GetValueOnGameThread() != 0;
	S.bFlightHoldAwake = CVarFlightHoldAwake.GetValueOnGameThread() != 0;
	S.bFlightEdgeAvoid = CVarFlightEdgeAvoid.GetValueOnGameThread() != 0;
	S.bProtectedRefuges = CVarProtectedRefuges.GetValueOnGameThread() != 0;
	S.bSocialControl = CVarSocialControl.GetValueOnGameThread() != 0;
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
	int32 NoFreezeArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3NoFreeze="), NoFreezeArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.NoFreeze"), LexToString(NoFreezeArg));
	}
	float EatArg = 5.0f;
	if (FParse::Value(CmdLine, TEXT("EcoV3WolfEatSeconds="), EatArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.WolfEatSeconds"), LexToString(EatArg));
	}
	int32 KeepArg = 1;
	// 도주 반사 거리. 옛 이름 -EcoV3KeepAway= (경계 거리 실험, 지움)도 같은 콘솔 변수로 받는다 — 새 이름이 있으면 새 이름이 이긴다
	if (FParse::Value(CmdLine, TEXT("EcoV3WildFlight="), KeepArg) || FParse::Value(CmdLine, TEXT("EcoV3KeepAway="), KeepArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.WildFlight"), LexToString(KeepArg));
	}
	int32 ReserveArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3WildReserve="), ReserveArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.WildReserve"), LexToString(ReserveArg));
	}
	int32 SatArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3WildSatiation="), SatArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.WildSatiation"), LexToString(SatArg));
	}
	int32 HoldArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3FlightHoldAwake="), HoldArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.FlightHoldAwake"), LexToString(HoldArg));
	}
	int32 EdgeArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3FlightEdgeAvoid="), EdgeArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.FlightEdgeAvoid"), LexToString(EdgeArg));
	}
	int32 ShelterArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3ShelterSafe="), ShelterArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.ShelterSafe"), LexToString(ShelterArg));
	}
	int32 RefugeArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3ProtectedRefuges="), RefugeArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.ProtectedRefuges"), LexToString(RefugeArg));
	}
	int32 SocialArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3SocialControl="), SocialArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.SocialControl"), LexToString(SocialArg));
	}
	int32 VisionArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3RealismVision="), VisionArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.RealismVision"), LexToString(VisionArg));
	}
	int32 HearingArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3RealismHearing="), HearingArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.RealismHearing"), LexToString(HearingArg));
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
	bool bRequested = IsRequested();
	TArray<AEcoCreatureIntegrationSpawner*> Found;
	for (TActorIterator<AEcoCreatureIntegrationSpawner> It(&InWorld); It; ++It)
	{
		Found.Add(*It);
	}
	for (const auto* Coordinator : Found) bRequested |= Coordinator->bUseV3Policy;
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
	if (InWorld.GetNetMode() == NM_Client)
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] Client: presentation only; canonical proxy templates registered by M4."));
		return;
	}
	if (Found.Num() > 1)
	{
		UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 통합 조정자가 %d 개다 — 첫 번째(%s)만 바꾼다 (조정자도 하나만 허용한다)"), Found.Num(),
			   *GetNameSafe(Found[0]));
	}
	Settings = FEcoV3IntegratedSettings::FromConsole();
	if (!IsRequested() && Found[0]->bUseV3Policy) Settings.DeerPerRegion = Found[0]->V3DeerPerRegion;
	if (Found[0]->bV3UseAuthoredShelters) Settings.ExtraCoverCount = 0;
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
			   TEXT("무대 한 변 %.0f m | 시드 %lld | 이주·웨이브·1초 에너지 소모 끔, 낮밤 60+60초 | 늑대 밤잠: %s | 시작 자리 지면 검사: %s"),
		   *GetNameSafe(Found[0]), UTF8_TO_TCHAR(EcoPolicyV3::kModelName), EcoPolicyV3::kObsDim, EcoPolicyV3::kMaskVersion, Plans.Num(),
		   Plans.IsEmpty() ? 0 : Plans[0].DeerPoints.Num(), Wolves, (Wolves + 1) / 2, Wolves / 2, Settings.PredSpeedMult,
		   Settings.StageSizeUnits * EcoRepertoireV3::kUnitCm / 100.0, static_cast<long long>(Settings.Seed),
		   Settings.bGradualNight ? TEXT("서서히 (eco.IntegratedV3.GradualNight 1 — 16 m 안 사슴·사냥 중이면 안 누움, 깜깜하면 새 사냥 없음, 늑대마다 지연, R1b 측정으로 허용)")
								  : TEXT("곧바로 (eco.IntegratedV3.GradualNight 0 — 어둠 0.5 에 바로 잠)"),
		   bStreamingSpawner ? TEXT("서식지 스트리밍이 끝나는 프레임에 조정자 시작 직전 다시") : TEXT("끝 (스트리밍 없음 — 조정자가 BeginPlay 에서 시작)"));
	const int32 EatSteps = Settings.WolfEatSteps();
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 사슴 얼기: %s | 늑대 식사: %s"),
		   Settings.bNoFreeze ? TEXT("막힘 (eco.IntegratedV3.NoFreeze 1, 사람 결정 10-15 (A) — R1b−F: 가중치 그대로, 마스크가 FREEZE 를 늘 막는다)")
							  : TEXT("열림 (eco.IntegratedV3.NoFreeze 0 — R1b 그대로 얼기를 쓴다)"),
		   *(Settings.LongWolfEat()
				 ? FString::Printf(TEXT("%.2f초 → %d 스텝 (%.2f초), 그동안 시체 곁에 서 있고 끝나면 곧바로 사냥 (eco.IntegratedV3.WolfEatSeconds, 사람 결정 10-15 (B), 포만 없음)"),
								   Settings.WolfEatSeconds, EatSteps, EatSteps * EcoRepertoireV3::kStepSeconds)
				 : FString::Printf(TEXT("옛 규칙 %d 스텝 (%.2f초, 그동안 배회 — 학습 세계 그대로. eco.IntegratedV3.WolfEatSeconds %.2f)"), EatSteps,
								   EatSteps * EcoRepertoireV3::kStepSeconds, Settings.WolfEatSeconds)));
	const EcoWorldV3::FWildFlightConfig Keep = Settings.WildFlightConfig();
	const double MPerUnit = EcoRepertoireV3::kUnitCm / 100.0;
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 사슴 도주 반사 거리: %s"),
		   *(Keep.bEnabled
				 ? FString::Printf(TEXT("켬 (eco.IntegratedV3.WildFlight 1, 야생 w3) — 사냥 중인 늑대를 알아채면 %.0f m 안 = 먹으며 멀어짐(경계), %.0f m 안이거나 다가옴 = ")
									   TEXT("%s %.0f m 밖·은신처까지 뜀(도주, 반대쪽 ±60° 은신처 쪽, %s), 은신처 안이면 웅크림, ")
									   TEXT("먹는·쉬는 늑대는 경계만 일으킴, 자는 늑대 무시"),
								   Keep.AlertR * MPerUnit, Keep.FlightR * MPerUnit,
								   Keep.bHoldAwake ? TEXT("깨어 있는 늑대 모두에게서") : TEXT("사냥 중인 늑대만 (eco.IntegratedV3.FlightHoldAwake 0)"),
								   Keep.SafeR * MPerUnit,
								   *(Keep.EdgeR > 0.0 ? FString::Printf(TEXT("가장자리 %.0f m 안은 벽을 따라·모서리 밖으로"), Keep.EdgeR * MPerUnit)
													  : FString(TEXT("가장자리 굽히기 끔 (eco.IntegratedV3.FlightEdgeAvoid 0)"))))
				 : FString(TEXT("끔 (eco.IntegratedV3.WildFlight 0 — 두뇌 그대로)"))));
	const EcoWorldV3::FWildReserveConfig Wr;
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 사슴 지방 비축: %s"),
		   *(Settings.bWildReserve
				 ? FString::Printf(TEXT("켬 (eco.IntegratedV3.WildReserve 1, 사람 결정 10-15 (7) 야생 w1) — 배가 비어도 비축으로 %.1f일(%d 스텝) 버팀, 굶음 = 배·비축 모두 0, ")
									   TEXT("배 %.0f%% 이상에서 먹으면 %.0f%% 가 비축으로, 배 %.0f%% 밑이면 %.2f배 느림"),
								   Wr.ReserveDays, static_cast<int32>(Wr.ReserveDays * 900.0 + 0.5), 100.0 * Wr.RefillE, 100.0 * Wr.RefillFrac,
								   100.0 * Wr.WeakE, Wr.WeakSpeed)
				 : FString(TEXT("끔 (eco.IntegratedV3.WildReserve 0 — 에너지 0 이면 곧바로 굶음)"))));
	const EcoWorldV3::FWildSatiationConfig Ws;
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 늑대 포만: %s"),
		   *(Settings.bWildSatiation
				 ? FString::Printf(TEXT("켬 (eco.IntegratedV3.WildSatiation 1, 야생 w2) — 먹기가 끝나면 %.1f일(%d 스텝 = %.0f초) 사냥하지 않고 %.1f배 속력으로 어슬렁거림, 사슴 눈에 보임"),
								   Ws.SatDays, EcoWorldV3::WildDaysToSteps(Ws.SatDays, 900),
								   EcoWorldV3::WildDaysToSteps(Ws.SatDays, 900) * EcoRepertoireV3::kStepSeconds, Ws.RestSpeed)
				 : FString(TEXT("끔 (eco.IntegratedV3.WildSatiation 0 — 먹기가 끝나면 곧바로 사냥)"))));
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 은신처: %s | 생명주기 %s"),
		   Settings.bShelterSafe ? TEXT("안전 (eco.IntegratedV3.ShelterSafe 1, 10-16) — 원 안 사슴은 표적·포획에서 빠지고 늑대는 둘레를 따라 미끄러짐")
		   : Settings.bProtectedRefuges ? TEXT("팀 규칙 안전 (eco.IntegratedV3.ShelterSafe 0·ProtectedRefuges 1 — 늑대 몸 여유 1 m, 쓸고 지나가기 막기, 파이썬과 다름)")
										: TEXT("끔 (eco.IntegratedV3.ShelterSafe 0 — 은신처 안에서도 잡힘)"),
		   Settings.bProtectedRefuges ? TEXT("켬 (eco.IntegratedV3.ProtectedRefuges 1 — 지워진 은신처 비활성·늦은 은신처 추가·잃은 HIDE 목표 풀기)")
									  : TEXT("끔 (eco.IntegratedV3.ProtectedRefuges 0)"));
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 사슴 Social 연결: %s"),
		   Settings.bSocialControl ? TEXT("켬 (eco.IntegratedV3.SocialControl 1, 22eb1b6) — 무리 경보·은신처 슬롯이 v3 제어 뒤·이동 전에 사슴 제어를 바꾼다")
								   : TEXT("끔 (eco.IntegratedV3.SocialControl 0 — v3 사슴 움직임은 파이썬 세계 그대로, Social 처리기는 기록만)"));
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 사슴 감지: 위협 시야 %s | 늑대 발소리 %s"),
		   Settings.bRealismVision ? TEXT("300° (eco.IntegratedV3.RealismVision 1 — 바로 뒤 60° 만 사각)") : TEXT("120° (eco.IntegratedV3.RealismVision 0 — R1b 그대로)"),
		   Settings.bRealismHearing ? TEXT("켬 (eco.IntegratedV3.RealismHearing 1 — 쫓아 달리면 최대 40 m, 어슬렁거리면 4 m, 서 있으면 없음)")
									: TEXT("끔 (eco.IntegratedV3.RealismHearing 0)"));
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
	C.bProtectedRefuges = S.bProtectedRefuges;
	C.FoodRegenMult = 1.0;
	C.RngStream = static_cast<uint64>(FMath::Max(0, RegionRuntimeIndex)) + 1;   // 지역마다 다른 먹이 패치·늑대 선회 (0 은 평면 맵 몫)
	C.bRespawnDead = false;                                    // 제자리 부활 없음 (계약 12-3: 새 개체 = 새 StableAgentId)
	C.PredEmaDenominator = FMath::Max(1, PlannedDeer);         // 고정 분모 = 무대 처음 사슴 수 (학습의 고정 128 과 같은 꼴, 열린 질문 7)
	C.bRealismNight = S.bGradualNight;                         // 늑대 밤잠 점진화 (eco.IntegratedV3.GradualNight, 사람 결정 H1)
	// 사슴 얼기 막음 (eco.IntegratedV3.NoFreeze, 사람 결정 10-15 (A)): 세계 허용 칸의 FREEZE 를 닫는다 — 실제 허용 = R1b 모델 ∧ 세계
	C.WorldAllowed[EcoRepertoireV3::kFreeze] = S.bNoFreeze ? 0 : 1;
	// 늑대 식사 (eco.IntegratedV3.WolfEatSeconds, 사람 결정 10-15 (B)): 학습 5 스텝보다 길 때만 쿨다운을 바꾸고 식사 동안 세운다
	if (S.LongWolfEat())
	{
		C.PredEatCdOverride = S.WolfEatSteps();
		C.bEatInPlace = true;
	}
	// 사슴 도주 반사 거리 (eco.IntegratedV3.WildFlight, 야생 w3 — 경계 거리 KeepAway 를 바꿨다): 끄면 기본값(꺼짐) 그대로
	C.WildFlight = S.WildFlightConfig();
	// 사슴 지방 비축 (eco.IntegratedV3.WildReserve, 사람 결정 10-15 (7) 야생 1단계 w1): 값 = configs/v3_wild1_mirror.yaml (FWildReserveConfig 기본값)
	C.WildReserve.bEnabled = S.bWildReserve;
	// 늑대 포만 (eco.IntegratedV3.WildSatiation, 야생 w2): 값 = configs/v3_wild1_mirror.yaml (FWildSatiationConfig 기본값, 하루 900 스텝 → 450 스텝)
	C.WildSatiation.bEnabled = S.bWildSatiation;
	// 감지 (eco.IntegratedV3.RealismVision·RealismHearing, R3 값 그대로 — FRealismVisionConfig·FHearingConfig 기본값)
	C.RealismVision.bEnabled = S.bRealismVision;
	C.RealismHearing.bEnabled = S.bRealismHearing;
	// 은신처 안전·늑대 진입 금지 (eco.IntegratedV3.ShelterSafe, 10-16 — R3 realism_shelter): 원 목록 = Covers (레벨에서 받은 은신처 + 우리 은신처)
	C.bShelterSafe = S.bShelterSafe;
	return C;
}

// -----------------------------------------------------------------------------
// 조정자 공개 속성 바꾸기 (OnWorldBeginPlay — 액터 BeginPlay 앞)
// -----------------------------------------------------------------------------

void UEcoPolicyV3IntegratedSubsystem::RefreshRefuges(FEcoV3RegionContext& Context)
{
    auto& W=Context.Sim;
    if(!W.Config.bProtectedRefuges||Context.CoverShelterIndices.Num()!=int32(W.Config.Covers.size()))return;
    const auto* Shelters=GetWorld()->GetSubsystem<UEcoShelterSubsystem>();if(!Shelters)return;
    bool Changed=false;
    for(int32 I=0;I<Context.CoverShelterIndices.Num();++I) {
        const int32 Index=Context.CoverShelterIndices[I];
        const bool Valid=Shelters->IsValidShelterIndex(Index)&&Context.CoverRegistrations.IsValidIndex(I)
            &&Shelters->GetShelters()[Index].RegistrationId==Context.CoverRegistrations[I];
        auto& Cover=W.Config.Covers[I];
        if(!Valid&&Cover.Radius>0){Cover.Radius=0;Changed=true;}
    }
    // Non-spatial refuge actors may register after terrain cells become ready. Append stable
    // targets, never recycle an old policy cover index for a new shelter registration.
    for(const auto& Point:Shelters->GetShelters()) {
        if(!Shelters->IsValidShelterIndex(Point.RuntimeIndex)||Context.CoverRegistrations.Contains(Point.RegistrationId))continue;
        const auto P=Context.CmToUnits(Point.Position);const double Radius=Point.Radius/EcoRepertoireV3::kUnitCm;
        if(Radius<FEcoV3IntegratedSettings::kCoverRadiusLoUnits||Radius>FEcoV3IntegratedSettings::kCoverRadiusHiUnits
            ||P.X<Radius||P.Y<Radius||P.X>W.Config.WorldSize-Radius||P.Y>W.Config.WorldSize-Radius)continue;
        W.Config.Covers.push_back({P.X,P.Y,Radius});Context.CoverShelterIndices.Add(Point.RuntimeIndex);
        Context.CoverRegistrations.Add(Point.RegistrationId);Context.CoverGroundZ.Add(Point.Position.Z);Changed=true;
    }
    if(Changed) {
        // Preserve food amounts and capacity. Only the removed refuge's regeneration modifier changes.
        auto& F=W.Food;
        for(int Y=0;Y<F.Gw;++Y)for(int X=0;X<F.Gw;++X) {
            const int K=Y*F.Gw+X;
            const bool In=EcoRefugeV3::Contains(W.Config.Covers,{(X+.5)*F.Cell,(Y+.5)*F.Cell});
            F.CoverCell[K]=In?1:0;
            F.Regen[K]=W.Config.FoodRegenBase*W.Config.FoodRegenMult*(In?W.Config.FoodCoverRegenMult:1.);
        }
    }
}

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
	UMassEntityConfigAsset* DeerConfig = UEcoCreatureV3Trait::MakeNetworkConfig(false);
	UMassEntityConfigAsset* WolfConfig = UEcoCreatureV3Trait::MakeNetworkConfig(true);
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
		TallyTeamWolfVisuals();
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
	UEcologySimulationSubsystem* Ecology = World->GetSubsystem<UEcologySimulationSubsystem>();
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
				if (AEcoShelterAnchor* Anchor = World->SpawnActor<AEcoShelterAnchor>(AEcoRefugeHabitat::StaticClass(), Xf, Params))
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
		TArray<int32> CoverIndices;TArray<int64> Registrations;
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
				CoverIndices.Add(P.RuntimeIndex);Registrations.Add(P.RegistrationId);
			}
		}
		const EcoWorldV3::FWorldConfig Config = MakeRegionWorldConfig(Settings, RegionIndex, G.Herbivores, G.Wolves, Covers);
		FEcoV3RegionContext* Ctx = AddContext(G.RegionId, RegionIndex, Origin, Config, G.Herbivores, G.Wolves);
		Ctx->TeamCovers = Team;
		Ctx->SkippedTeamCovers = Skipped;
		Ctx->ExtraCovers = Extra;
		Ctx->CoverGroundZ = CoverZ;
		Ctx->CoverShelterIndices=MoveTemp(CoverIndices);Ctx->CoverRegistrations=MoveTemp(Registrations);
		if (Ecology)
			Ctx->bSpatialFoodRegistered = Ecology->RegisterSpatialFood(G.RegionId, Ctx->StartFood, Ctx->StartFood);
		if (!Ctx->bSpatialFoodRegistered)
		{ UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] Spatial food registration rejected: %s"), *G.RegionId.ToString()); bActive = false; return; }
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
	Ctx->StartFood = Ctx->Sim.Food.Total();   // 처음 먹이 = 셀 용량 합 (재생은 용량을 넘지 않는다)
	Ctx->RecentEaten.Init(0.0, EcoV3Integrated::kRecentEatSteps);
	Ctx->RecentEatenPos = 0;
	Ctx->LastStepFoodEaten = Ctx->Sim.Stats.FoodEaten;
	Ctx->bPrevDark = Ctx->Sim.Dark >= Ctx->Sim.ThreatCfg.SleepDark;
	Ctx->bDarkKnown = true;
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
	Ctx.PushStepEaten();
	if (LogEverySteps > 0 && Ctx.Sim.T - Ctx.LastLogT >= LogEverySteps)
	{
		LogContext(Ctx);
	}
}

void UEcoPolicyV3IntegratedSubsystem::NotifyNightStep(FEcoV3RegionContext& Ctx, EcoWorldV3::FThreatAgent* const* Threats,
												   const int64* WolfIds, int32 NumWolves)
{
	const EcoThreatV3::FThreatConfig& Cfg = Ctx.Sim.ThreatCfg;
	if (!Cfg.bRealismNight)
	{
		return;
	}
	// 해 진·뜬 시각 (이번 스텝 끝 새 t 의 어둠 — 밤잠 업데이트가 쓴 값)
	const bool bDark = Ctx.Sim.Dark >= Cfg.SleepDark;
	if (!Ctx.bDarkKnown || bDark != Ctx.bPrevDark)
	{
		if (Ctx.bDarkKnown)
		{
			(bDark ? Ctx.DarkStartT : Ctx.LightStartT) = Ctx.Sim.T;
		}
		Ctx.bPrevDark = bDark;
		Ctx.bDarkKnown = true;
	}
	for (int32 m = 0; m < NumWolves; ++m)
	{
		const EcoWorldV3::FThreatAgent& A = *Threats[m];
		const EcoThreatV3::FNightUpdateResult& N = A.LastNight;
		if (!(N.bOnset || N.bWake || N.bSettleStart || N.bSettleAbort))
		{
			continue;
		}
		double MinUnits = -1.0;
		for (const EcoThreatV3::FPreyView& P : Ctx.Sim.Prey)
		{
			if (P.bAlive)
			{
				const double D = FMath::Sqrt(FMath::Square(P.X - A.State.PosX) + FMath::Square(P.Y - A.State.PosY));
				MinUnits = MinUnits < 0.0 ? D : FMath::Min(MinUnits, D);
			}
		}
		const TCHAR* What = N.bOnset ? TEXT("잠듦") : N.bWake ? TEXT("깸") : N.bSettleStart ? TEXT("눕기 시작") : TEXT("다시 일어남");
		const int64 Since = N.bWake ? Ctx.LightStartT : Ctx.DarkStartT;
		const FString SinceText = Since >= 0 ? FString::Printf(TEXT("%s %.1f초"), N.bWake ? TEXT("해 뜬 뒤") : TEXT("해 진 뒤"),
															  static_cast<double>(Ctx.Sim.T - Since) * EcoRepertoireV3::kStepSeconds)
											 : FString(TEXT("해 진·뜬 시각 모름"));
		const TCHAR* Why = !N.bSettleAbort ? TEXT("")
						   : !bDark		   ? TEXT(" (밝아짐)")
						   : N.bNear	   ? TEXT(" (사슴이 16 m 안에 들어옴)")
										   : TEXT(" (사냥 시작)");
		const FString Nearest = MinUnits >= 0.0 ? FString::Printf(TEXT("%.1f m"), MinUnits * EcoRepertoireV3::kUnitCm / 100.0) : FString(TEXT("없음"));
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 늑대 %lld (%s) %s%s: %s, d=%.2f, 가장 가까운 사슴 %s (눕지 않는 거리 %.0f m), 지연 %d 스텝, 걸음 %d/%d"),
			   *Ctx.RegionId.ToString(), static_cast<long long>(WolfIds ? WolfIds[m] : m),
			   A.Spec.Type == EcoThreatV3::EThreatType::Stalker ? TEXT("잠행형") : TEXT("추격형"), What, Why, *SinceText, Ctx.Sim.Dark,
			   *Nearest, Cfg.NightSettleR * EcoRepertoireV3::kUnitCm / 100.0, A.State.NightDelay, A.State.NightAct, Cfg.NightRampSteps);
	}
}

void FEcoV3RegionContext::TallyWolfStep(const EcoWorldV3::FThreatAgent& A, int64 WolfId, int64 StepIndex)
{
	using EcoV3Integrated::kChainWindowSteps;
	const int64* Last = WolfLastCatchStep.Find(WolfId);
	const int64 Since = Last ? StepIndex - *Last : -1;
	const int64 EatCd = Sim.ThreatCfg.PredEatCd;
	if (A.Last.bPounceStart)
	{
		++Eat.Pounces;
		Eat.ChainPounces += (Last && Since <= kChainWindowSteps) ? 1 : 0;
		Eat.PostEatPounces += (Last && Since <= EatCd + kChainWindowSteps) ? 1 : 0;
	}
	if (A.Last.Caught < 0 && A.State.Cooldown > 0)
	{
		// 식사 중: 이번 스텝에 쿨다운을 빼고도 남아 사냥하지 않았다 (잡은 스텝은 쿨다운이 0 이었으므로 여기 들지 않는다)
		++Eat.EatSteps;
		Eat.EatMoved += (A.State.VelX != 0.0 || A.State.VelY != 0.0) ? 1 : 0;
	}
	if (A.Last.Caught >= 0)
	{
		++Eat.Catches;
		++WolfCatchesById.FindOrAdd(WolfId);
		if (Last)
		{
			++Eat.RepeatCatches;
			Eat.PostEatCatches += Since <= EatCd + kChainWindowSteps ? 1 : 0;
		}
		WolfLastCatchStep.Add(WolfId, StepIndex);
	}
}

void UEcoPolicyV3IntegratedSubsystem::TallyTeamWolfVisuals()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}
	static const FName WolfSpecies(TEXT("Wolf"));
	// 팀 표현 액터는 읽기만 한다 (팀 조정자가 FEcoCreaturePresentationFragment 깃발 2 = EatCooldown > 0 으로 bEating 을 세운다)
	for (TActorIterator<AEcoCreatureRepresentationActor> It(World); It; ++It)
	{
		const AEcoCreatureRepresentationActor* Rep = *It;
		if (!Rep || !Rep->bBound || !Rep->VisualState.bAlive || !Rep->VisualState.bEating || Rep->VisualState.SpeciesId != WolfSpecies)
		{
			continue;
		}
		FEcoV3RegionContext* Ctx = FindContext(Rep->VisualState.RegionId);
		if (!Ctx)
		{
			continue;
		}
		++Ctx->Eat.EatFlagFrames;
		Ctx->Eat.EatMotionFrames += Rep->VisualMotion == EEcoCreatureVisualMotion::Eating ? 1 : 0;
		Ctx->Eat.EatWalkFrames += (Rep->VisualMotion == EEcoCreatureVisualMotion::Walk || Rep->VisualMotion == EEcoCreatureVisualMotion::Run) ? 1 : 0;
	}
}

void UEcoPolicyV3IntegratedSubsystem::LogContext(FEcoV3RegionContext& Ctx)
{
	using namespace EcoV3Integrated;
	const EcoWorldV3::FWorldStats& S = Ctx.Sim.Stats;
	const EcoWorldV3::FWorldStats& P = Ctx.LastLogStats;
	const double Seconds = static_cast<double>(Ctx.Sim.T) * EcoRepertoireV3::kStepSeconds;
	if(Ctx.Sim.Config.bProtectedRefuges)
		UE_LOG(LogEcoPolicyV3I,Log,TEXT("[EcoRefuge] NetMode=%d Region=%s Step=%lld ProtectedPreySteps=%lld Deflections=%lld Recoveries=%lld InsidePredatorSteps=%lld CaptureViolations=%lld"),
			int32(GetWorld()->GetNetMode()),*Ctx.RegionId.ToString(),static_cast<long long>(Ctx.Sim.T),
			static_cast<long long>(S.RefugeProtectedPreySteps),static_cast<long long>(S.RefugeConstrainedMoves),static_cast<long long>(S.RefugeRecoveries),
			static_cast<long long>(S.RefugeInsidePredatorSteps),static_cast<long long>(S.RefugeCaptureViolations));

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
	// 허용 행동(잠 빼고, 얼기를 막으면 얼기도 빼고)을 모두 썼는가
	bool bAllUsed = true;
	FString AllowedNames;
	FString Now;
	FString Used;
	for (int32 b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
	{
		const bool bCounted = b != EcoRepertoireV3::kSleep && Ctx.Sim.Allowed[b] != 0;
		bAllUsed = bAllUsed && (!bCounted || S.BehaviorSteps[b] > 0);
		if (bCounted)
		{
			AllowedNames += AllowedNames.IsEmpty() ? FString(BehaviorNameKo(b)) : FString(TEXT("·")) + BehaviorNameKo(b);
		}
		Now += FString::Printf(TEXT(" %s %d"), BehaviorNameKo(b), Ctx.BehaviorNow[b]);
		Used += FString::Printf(TEXT(" %s %lld"), BehaviorNameKo(b), static_cast<long long>(S.BehaviorSteps[b] - P.BehaviorSteps[b]));
	}
	FString WolfNow;
	for (int32 w = 0; w < static_cast<int32>(EWolfState::Count); ++w)
	{
		if (w < static_cast<int32>(EWolfState::Settle) || Ctx.Sim.ThreatCfg.bRealismNight)
		{
			WolfNow += FString::Printf(TEXT(" %s %d"), WolfStateNameKo(static_cast<EWolfState>(w)), Ctx.WolvesNow[w]);
		}
	}
	// 늑대 밤잠 점진화 (켠 세계만): 구간 눕기 시작·다시 일어남·잠듦·깸, 누울 차례인데 사슴·사냥 때문에 못 누운 늑대·업데이트, 어둠 중 깨어 있음
	FString Night;
	if (Ctx.Sim.ThreatCfg.bRealismNight)
	{
		const int64 DarkN = S.NightDarkUpdates - P.NightDarkUpdates;
		const int64 DarkAwake = S.NightDarkAwake - P.NightDarkAwake;
		Night = FString::Printf(
			TEXT(" | 늑대 밤잠(서서히): 눕기 시작 %lld · 다시 일어남 %lld · 잠듦 %lld · 깸 %lld · 사슴 곁이라 안 누움 %lld · 사냥 중이라 안 누움 %lld (늑대·업데이트) · 어둠 중 깨어 있음 %.0f%%"),
			static_cast<long long>(S.NightSettleStarts - P.NightSettleStarts), static_cast<long long>(S.NightSettleAborts - P.NightSettleAborts),
			static_cast<long long>(S.NightOnsets - P.NightOnsets), static_cast<long long>(S.NightWakes - P.NightWakes),
			static_cast<long long>(S.NightBlockDeer - P.NightBlockDeer), static_cast<long long>(S.NightBlockHunt - P.NightBlockHunt),
			DarkN > 0 ? 100.0 * static_cast<double>(DarkAwake) / static_cast<double>(DarkN) : 0.0);
	}
	const double CpuAvgMs = StepCpuSteps > 0 ? 1000.0 * StepCpuSeconds / static_cast<double>(StepCpuSteps) : 0.0;
	// 먹기: 구간 먹은 양(먹이 단위), 먹은 사슴 수, 먹기 개체·스텝 중 실제로 먹은 비율(먹이 없는 칸을 걷는 먹기는 못 먹는다), 무대 먹이, 에너지
	const int64 GrazeSteps = S.BehaviorSteps[EcoRepertoireV3::kGraze] - P.BehaviorSteps[EcoRepertoireV3::kGraze];
	const int64 AteSteps = S.EatSteps - P.EatSteps;
	const FString Feeding = FString::Printf(
		TEXT("먹이: 구간 먹은 양 %.2f (먹이 단위, 셀 하나 최대 1) · 먹은 사슴 %d · 먹기 중 실제로 먹은 비율 %.0f%% (%lld/%lld 개체·스텝) · ")
			TEXT("무대 먹이 처음의 %.1f%% · 사슴 에너지 평균 %.1f%% · 굶주림(15%% 아래) %d · 번식(에너지 0.5 로) %lld"),
		S.FoodEaten - P.FoodEaten, Ctx.AteDeerInterval, GrazeSteps > 0 ? 100.0 * static_cast<double>(AteSteps) / static_cast<double>(GrazeSteps) : 0.0,
		static_cast<long long>(AteSteps), static_cast<long long>(GrazeSteps), 100.0 * Ctx.FoodFraction(), 100.0 * Ctx.MeanEnergy, Ctx.StarvingDeer,
		static_cast<long long>(S.Reproduced - P.Reproduced));
	UE_LOG(LogEcoPolicyV3I, Log,
		   TEXT("[EcoV3I] %s | %.1f초 %s d=%.2f (%s) | 사슴 산 %d/%d | 지금 행동:%s | 구간 사용(개체·스텝):%s | 늑대 %d:%s%s | ")
			   TEXT("포획 %lld (누적 %lld) 굶음 %lld (누적 %lld) | %s | 지형 검사 이동 %lld, 막힘 사슴 %lld 늑대 %lld | 피식EMA %.3f | 마스크 위반 %lld | ")
			   TEXT("허용 행동(%s) 모두 씀=%s | 결정 스텝 CPU(모든 지역) 평균 %.2f ms/스텝, 최대 %.1f ms/프레임"),
		   *Ctx.RegionId.ToString(), Seconds, Ctx.Sim.Dark >= 0.5 ? TEXT("밤") : TEXT("낮"), Ctx.Sim.Dark, *TeamPhase, Ctx.AliveDeer,
		   Ctx.AdoptedDeer, *Now, *Used, Ctx.Wolves, *WolfNow, *Night, static_cast<long long>(S.Caught - P.Caught),
		   static_cast<long long>(S.Caught), static_cast<long long>(S.Starved - P.Starved), static_cast<long long>(S.Starved), *Feeding,
		   static_cast<long long>(Ctx.TerrainChecks - Ctx.LastLogTerrainChecks),
		   static_cast<long long>(S.BlockedHerbMoves - P.BlockedHerbMoves), static_cast<long long>(S.BlockedThreatMoves - P.BlockedThreatMoves),
		   Ctx.Sim.PredEma, static_cast<long long>(S.MaskViolations), *AllowedNames, bAllUsed ? TEXT("예") : TEXT("아니오"), CpuAvgMs,
		   1000.0 * StepCpuMaxFrameSeconds);
	// 둘째 줄: 사슴 얼기 막음·늑대 식사 (사람 결정 10-15 (A)(B)). 구간 = 지난 기록 줄 뒤
	{
		const FEcoV3WolfEatTally& E = Ctx.Eat;
		const FEcoV3WolfEatTally& L = Ctx.LastLogEat;
		const int32 Fz = EcoRepertoireV3::kFreeze;
		const bool bFreezeBlocked = Ctx.Sim.Allowed[Fz] == 0;
		const int32 EatCd = Ctx.Sim.ThreatCfg.PredEatCd;
		TArray<int64> Ids;
		Ctx.WolfCatchesById.GetKeys(Ids);
		Ids.Sort();
		FString PerWolf;
		for (const int64 Id : Ids)
		{
			PerWolf += FString::Printf(TEXT(" %lld:%d"), static_cast<long long>(Id), Ctx.WolfCatchesById.FindRef(Id));
		}
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 얼기·식사 | %.1f초 | 얼기 %s: 구간 실행 %lld (누적 %lld) · 얼기 칸이 열린 결정 구간 %lld (누적 %lld) | ")
				   TEXT("늑대 식사 %.2f초(%d 스텝) %s: 구간 포획 %lld (누적 %lld) · 식사 중 늑대·스텝 %lld, 그중 움직임 %lld · 돌진 %lld, 그중 이어 사냥(앞 포획 뒤 3초 안) %lld · ")
				   TEXT("식사 끝 3초 안 %lld · 앞 포획이 있는 포획 %lld, 그중 식사 끝 3초 안 %lld · 팀 화면 식사 깃발 늑대·프레임 %lld (먹는 중 동작 %lld, 걷기·뛰기 %lld) | ")
				   TEXT("늑대별 포획 누적:%s"),
			   *Ctx.RegionId.ToString(), Seconds, bFreezeBlocked ? TEXT("막힘") : TEXT("열림"),
			   static_cast<long long>(S.BehaviorSteps[Fz] - P.BehaviorSteps[Fz]), static_cast<long long>(S.BehaviorSteps[Fz]),
			   static_cast<long long>(Ctx.FreezeMaskOpen - Ctx.LastLogFreezeMaskOpen), static_cast<long long>(Ctx.FreezeMaskOpen),
			   EatCd * EcoRepertoireV3::kStepSeconds, EatCd, Ctx.Sim.ThreatCfg.bEatInPlace ? TEXT("제자리") : TEXT("배회 (옛 규칙)"),
			   static_cast<long long>(E.Catches - L.Catches), static_cast<long long>(E.Catches),
			   static_cast<long long>(E.EatSteps - L.EatSteps), static_cast<long long>(E.EatMoved - L.EatMoved),
			   static_cast<long long>(E.Pounces - L.Pounces), static_cast<long long>(E.ChainPounces - L.ChainPounces),
			   static_cast<long long>(E.PostEatPounces - L.PostEatPounces), static_cast<long long>(E.RepeatCatches - L.RepeatCatches),
			   static_cast<long long>(E.PostEatCatches - L.PostEatCatches), static_cast<long long>(E.EatFlagFrames - L.EatFlagFrames),
			   static_cast<long long>(E.EatMotionFrames - L.EatMotionFrames), static_cast<long long>(E.EatWalkFrames - L.EatWalkFrames),
			   PerWolf.IsEmpty() ? TEXT(" 없음") : *PerWolf);
		Ctx.LastLogEat = E;
		Ctx.LastLogFreezeMaskOpen = Ctx.FreezeMaskOpen;
	}
	// 셋째 줄: 사슴 경계 거리 (사람 결정 10-15 (C)). 구간 = 지난 기록 줄 뒤. '식사 중 늑대 15 m 안 사슴'은 규칙을 꺼도 센다 (켬·끔 비교)
	{
		const EcoWorldV3::FWildFlightConfig& K = Ctx.Sim.Config.WildFlight;
		const double MPerUnit = EcoRepertoireV3::kUnitCm / 100.0;
		const int64 Steps = S.Steps - P.Steps;
		const int64 Near = Ctx.NearEatingDeerSteps - Ctx.LastLogNearEatingDeerSteps;
		const int64 Ends = S.KeepPanicEnds - P.KeepPanicEnds;
		const int64 EndSteps = S.KeepPanicEndSteps - P.KeepPanicEndSteps;
		const int64 Caught = S.Caught - P.Caught;
		int64 CaughtKeep[EcoWorldV3::kNumKeepModes] = {};
		for (int32 k = 1; k < EcoWorldV3::kNumKeepModes; ++k)
		{
			CaughtKeep[k] = S.CaughtByKeep[k] - P.CaughtByKeep[k];
		}
		const int64 CaughtOutside = Caught - CaughtKeep[1] - CaughtKeep[2] - CaughtKeep[3];
		const FString Rule = K.bEnabled ? FString::Printf(TEXT("도주 반사 켬 (경계 %.0f m · 도주 %.0f m · 안전 %.0f m)"), K.AlertR * MPerUnit,
														  K.FlightR * MPerUnit, K.SafeR * MPerUnit)
										: FString(TEXT("끔 (두뇌 그대로)"));
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 경계 거리 | %.1f초 | %s | 구간 경계(멀어짐) 시작 %lld · 도망 시작 %lld · 은신처 웅크림 시작 %lld | ")
				   TEXT("덮기 개체·스텝 경계 %lld 도망 %lld 웅크림 %lld (두뇌 %lld) | 끝난 도망 %lld (은신처에서 %lld), 평균 %.1f초 · 도망 중 죽음 %lld | ")
				   TEXT("잡힌 사슴 %lld: 경계 중 %lld · 도망 중 %lld · 웅크림 중 %lld · 덮기 밖 %lld | ")
				   TEXT("식사 중 늑대 15 m 안 사슴 %lld 개체·스텝 (스텝당 %.2f 마리) | 지금 덮기: 경계 %d 도망 %d 웅크림 %d | 은신처 안 잡힘 %lld (누적 %lld)"),
			   *Ctx.RegionId.ToString(), Seconds, *Rule, static_cast<long long>(S.KeepAlertStarts - P.KeepAlertStarts),
			   static_cast<long long>(S.KeepPanicStarts - P.KeepPanicStarts), static_cast<long long>(S.KeepShelterStarts - P.KeepShelterStarts),
			   static_cast<long long>(S.KeepSteps[1] - P.KeepSteps[1]), static_cast<long long>(S.KeepSteps[2] - P.KeepSteps[2]),
			   static_cast<long long>(S.KeepSteps[3] - P.KeepSteps[3]), static_cast<long long>(S.KeepSteps[0] - P.KeepSteps[0]),
			   static_cast<long long>(Ends), static_cast<long long>(S.KeepPanicEndShelter - P.KeepPanicEndShelter),
			   Ends > 0 ? static_cast<double>(EndSteps) * EcoRepertoireV3::kStepSeconds / static_cast<double>(Ends) : 0.0,
			   static_cast<long long>(S.KeepPanicDied - P.KeepPanicDied), static_cast<long long>(Caught), static_cast<long long>(CaughtKeep[1]),
			   static_cast<long long>(CaughtKeep[2]), static_cast<long long>(CaughtKeep[3]), static_cast<long long>(CaughtOutside),
			   static_cast<long long>(Near),
			   Steps > 0 ? static_cast<double>(Near) / static_cast<double>(Steps) : 0.0, Ctx.KeepNow[1], Ctx.KeepNow[2], Ctx.KeepNow[3],
			   static_cast<long long>(S.CaughtInCover - P.CaughtInCover), static_cast<long long>(S.CaughtInCover));
		Ctx.LastLogNearEatingDeerSteps = Ctx.NearEatingDeerSteps;
	}
	// 넷째 줄: 야생 1단계 (사람 결정 10-15 (7)). 켠 규칙만 적는다. 구간 = 지난 기록 줄 뒤. 앞 세 줄의 칸·순서는 그대로다
	//   (results/v3/mirror/compare_unreal.py 가 첫 줄을 읽는다 — 이 줄은 '<지역> 야생 |' 꼴이라 그 정규식에 걸리지 않는다)
	if (Ctx.Sim.Config.WildReserve.bEnabled || Ctx.Sim.ThreatCfg.bWildSatiation)
	{
		const int64 LiveN = S.ReserveLiveSteps - P.ReserveLiveSteps;
		const FString Reserve = !Ctx.Sim.Config.WildReserve.bEnabled ? FString(TEXT("지방 비축 끔")) : FString::Printf(
			TEXT("지방 비축: 구간 꺼내 씀 %.3f · 채움 %.3f (에너지 단위, 용량 %.2f) · 약한 개체·스텝 %lld/%lld (%.1f%%) · 약한 채로 잡힘 %lld (누적 %lld) | ")
				TEXT("지금 비축 평균 %.0f%% 최소 %.0f%% · 배 비어 비축으로 사는 사슴 %d · 비축 %.0f%% 밑 %d · 약함 %d"),
			S.ReserveUsed - P.ReserveUsed, S.ReserveRefill - P.ReserveRefill, Ctx.Sim.ReserveCap,
			static_cast<long long>(S.WeakSteps - P.WeakSteps), static_cast<long long>(LiveN),
			LiveN > 0 ? 100.0 * static_cast<double>(S.WeakSteps - P.WeakSteps) / static_cast<double>(LiveN) : 0.0,
			static_cast<long long>(S.WeakCaught - P.WeakCaught), static_cast<long long>(S.WeakCaught), 100.0 * Ctx.MeanReserve,
			100.0 * Ctx.MinReserve, Ctx.OnReserveDeer, 100.0 * EcoV3Integrated::kLowReserve, Ctx.LowReserveDeer, Ctx.WeakDeer);
		const int64 WolfN = S.WolfSteps - P.WolfSteps;
		const FString Sat = !Ctx.Sim.ThreatCfg.bWildSatiation
								? FString(TEXT("늑대 포만 끔"))
								: FString::Printf(TEXT("늑대 포만(%d 스텝): 구간 늑대·스텝 %lld 중 배불러 쉼 %.0f%% · 먹는 중 %.0f%% · 포만을 건 포획 %lld (누적 %lld)"),
												  Ctx.Sim.ThreatCfg.SatSteps, static_cast<long long>(WolfN),
												  WolfN > 0 ? 100.0 * static_cast<double>(S.WolfSatedSteps - P.WolfSatedSteps) / static_cast<double>(WolfN) : 0.0,
												  WolfN > 0 ? 100.0 * static_cast<double>(S.WolfEatingSteps - P.WolfEatingSteps) / static_cast<double>(WolfN) : 0.0,
												  static_cast<long long>(S.WolfKills - P.WolfKills), static_cast<long long>(S.WolfKills));
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 야생 | %.1f초 | %s | %s"), *Ctx.RegionId.ToString(), Seconds, *Reserve, *Sat);
	}
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
	Ctx.AteDeerInterval = 0;   // 새 구간: 사슴 조각의 AteLogEpoch 가 이 번호와 다르면 아직 이 구간에 먹지 않았다
	++Ctx.LogEpoch;
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
	// 매 프레임 부르므로 찾기는 한 번만 (엔진이 FindConsoleObject 반복 호출 경고를 남긴다)
	static IConsoleVariable* const Limit = IConsoleManager::Get().FindConsoleVariable(TEXT("r.DebugSafeZone.MaxDebugTextStringsPerActor"));
	// 그릴 수 없는 실행(-NullRHI 헤드리스)에서는 한도를 풀지 않는다: HUD 가 그려지지 않아 엔진이 디버그 글자 목록(AHUD::DebugTextList)을
	// 비우지 않는다. 한도 0 이면 목록이 프레임마다 사슴·늑대 수만큼 늘고 글자를 더할 때마다 목록을 훑어 프레임이 점점 느려진다
	// (10-14 헤드리스 -EcoV3Debug: 프레임 15 → 914 에 20 fps → 1.7 fps). 한도 128 이면 목록이 128 줄에서 멈춘다. 글자 만들기는 그대로 돈다
	const bool bDebug = IsDebugDrawEnabled() && FApp::CanEverRender();
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
			// 얼기를 막았으면 '얼기(막힘) 0' — 늘 0 이어야 한다 (사람 결정 10-15 (A))
			Tally += FString::Printf(TEXT(" %s%s %d"), BehaviorNameKo(b), Ctx.Sim.Allowed[b] == 0 ? TEXT("(막힘)") : TEXT(""), Ctx.BehaviorNow[b]);
		}
		FString Wolves;
		for (int32 w = 0; w < static_cast<int32>(EWolfState::Count); ++w)
		{
			if (Ctx.WolvesNow[w] > 0)
			{
				Wolves += FString::Printf(TEXT(" %s %d"), WolfStateNameKo(static_cast<EWolfState>(w)), Ctx.WolvesNow[w]);
			}
		}
		if (Ctx.Sim.ThreatCfg.bRealismNight)
		{
			Wolves += TEXT(" (밤잠 서서히)");
		}
		// 늑대 식사 규칙: '늑대 식사 5초 제자리' (사람 결정 10-15 (B)), 옛 규칙이면 '늑대 식사 0.7초 배회'
		const int32 EatCd = Ctx.Sim.ThreatCfg.PredEatCd;
		Wolves += FString::Printf(TEXT(" | 늑대 식사 %s초 %s"),
								  *FString::SanitizeFloat(FMath::RoundToDouble(10.0 * EatCd * EcoRepertoireV3::kStepSeconds) / 10.0),
								  Ctx.Sim.ThreatCfg.bEatInPlace ? TEXT("제자리") : TEXT("배회"));
		// 사슴 경계 거리 (사람 결정 10-15 (C)): 지금 덮기 수
		if (Ctx.Sim.Config.WildFlight.bEnabled)
		{
			Tally += FString::Printf(TEXT(" | 경계(멀어짐) %d 도망(안전해질 때까지) %d 숨기(은신처·경계) %d"), Ctx.KeepNow[EcoWorldV3::kKeepAlert],
									 Ctx.KeepNow[EcoWorldV3::kKeepPanic], Ctx.KeepNow[EcoWorldV3::kKeepShelter]);
		}
		const FString Line = FString::Printf(TEXT("v3 %s %s | %s d=%.2f | 사슴 %d/%d:%s | 늑대%s | 포획 %lld 굶음 %lld"),
											 Ctx.Sim.Allowed[EcoRepertoireV3::kFreeze] == 0 ? TEXT("R1b−F") : TEXT("R1b"),
											 *Ctx.RegionId.ToString(), Ctx.Sim.Dark >= 0.5 ? TEXT("밤") : TEXT("낮"), Ctx.Sim.Dark,
											 Ctx.AliveDeer, Ctx.AdoptedDeer, *Tally, *Wolves,
											 static_cast<long long>(Ctx.Sim.Stats.Caught), static_cast<long long>(Ctx.Sim.Stats.Starved));
		// 둘째 줄: 먹기 되먹임 (v3 먹이 격자 — 팀 지역 FoodAmount 가 아니다)
		FString FoodLine = FString::Printf(TEXT("먹이 %s | 무대 먹이 처음의 %.0f%% | 최근 10초 먹은 양 %.1f | 사슴 에너지 평균 %.0f%% | 굶주림(15%% 아래) %d"),
										   *Ctx.RegionId.ToString(), 100.0 * Ctx.FoodFraction(), Ctx.RecentEatenSum(),
										   100.0 * Ctx.MeanEnergy, Ctx.StarvingDeer);
		// 야생 (w1) 지방 비축 (켠 세계만): 비축 평균·배 비어 비축으로 사는 사슴·비축 바닥 가까움·약함
		if (Ctx.Sim.Config.WildReserve.bEnabled)
		{
			FoodLine += FString::Printf(TEXT(" | 지방 비축 평균 %.0f%% · 비축으로 사는 사슴 %d · 비축 %.0f%% 밑 %d · 약함(느림) %d"), 100.0 * Ctx.MeanReserve,
										Ctx.OnReserveDeer, 100.0 * EcoV3Integrated::kLowReserve, Ctx.LowReserveDeer, Ctx.WeakDeer);
		}
		DrawDebugString(World, Center + FVector(0, 0, 600.0), Line + TEXT("\n") + FoodLine, nullptr, FColor::White, 0.0f, true, 1.4f);
		if (bScreen)
		{
			GEngine->AddOnScreenDebugMessage(static_cast<uint64>(730000 + Ctx.Index), 1.5f, FColor(180, 230, 180), Line);
			GEngine->AddOnScreenDebugMessage(static_cast<uint64>(731000 + Ctx.Index), 1.5f, FColor(230, 210, 150), FoodLine);
		}
	}
}

void UEcoPolicyV3IntegratedSubsystem::RejectResourceContract()
{
    Deactivate(TEXT("Resource conservation receipt rejected"));
    if(auto* Coordinator=Spawner.Get())Coordinator->FailRuntime(TEXT("V3 spatial resource contract rejected"));
}

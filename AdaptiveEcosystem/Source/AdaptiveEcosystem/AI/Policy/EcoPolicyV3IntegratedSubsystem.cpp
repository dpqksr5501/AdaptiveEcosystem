#include "EcoPolicyV3IntegratedSubsystem.h"

#include "AI/Social/Shelter/EcoShelterAnchor.h"
#include "AI/Social/Shelter/EcoRefugeHabitat.h"
#include "AI/Social/Shelter/EcoShelterSubsystem.h"
#include "Core/EcoRuntimeSettings.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/WorldPartitionStreamingSourceComponent.h"
#include "Creature/Representation/EcoCreatureRepresentationActor.h"
#include "Dom/JsonObject.h"
#include "Engine/CollisionProfile.h"
#include "Engine/StaticMesh.h"
#include "Engine/StaticMeshActor.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/Volume.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/BodySetup.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
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
#include "UnrealClient.h"
#include "World/EcoWorldClockSubsystem.h"
#include "World/EcologyRegion.h"
#include "World/EcoVegetationField.h"
#include "HAL/PlatformMemory.h"
#include "Engine/NetDriver.h"

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
	// 10-17 사람 결정 (RL_V2_PLAN.md '10-17 (8)'): 기본은 끔. 경보는 소리·고개 들기 같은 연출로만 쓴다는 10-13 결정과 맞추고,
	// 무리 반응은 뒤에 파이썬 야생 규칙으로 먼저 만든다. 켜면 팀 연결이 경계 먹기·가장자리 굽히기·은신처 보호를 덮어쓴다
	static TAutoConsoleVariable<int32> CVarSocialControl(TEXT("eco.IntegratedV3.SocialControl"),0,
		TEXT("통합 v3 사슴의 Social 행동 연결 (0 = 끔, 기본 — 사람 결정 10-17 (8)). 0 이면 Social 처리기(무리 경보·은신처 슬롯 예약)는 돌며 기록만 하고, ")
		TEXT("v3 사슴 움직임은 파이썬 세계 규칙 그대로다. 1 = 조연우 님 22eb1b6 연결을 건다: 무리 경보(Alert·Panic·Recovering)와 은신처 슬롯이 v3 제어 뒤·이동 전에 ")
		TEXT("사슴 제어를 바꾼다(EcoWorldV3 FStepHooks::HerbControl) — 먹는 늑대 곁 경계 먹기·가장자리 굽히기가 빠지고, 슬롯 없는 은신처 사슴이 밖으로 뛴다. ")
		TEXT("팀 장면 확인용. Play 전에 바꾼다. 명령줄 -EcoV3SocialControl= 는 시작값."),ECVF_Default);

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

	static TAutoConsoleVariable<float> CVarWolfBodyMargin(
		TEXT("eco.IntegratedV3.WolfBodyMargin"),
		1.0f,
		TEXT("통합 v3 모드의 늑대 몸 여유 (m, 기본 1 — 10-17, 파이썬 configs/v3_wild1_mirror.yaml realism_shelter.wolf_margin 0.5 단위). 늑대 중심은 ")
		TEXT("은신처 반지름 + 이 거리 밖에서 둘레를 따라 미끄러진다(늑대 몸이 은신처 바위·덤불 테두리를 파고들지 않는다). 사슴 쪽(원 안 안전·표적 제외)은 ")
		TEXT("반지름 그대로. eco.IntegratedV3.ShelterSafe 1 일 때만 쓴다(0 이면 팀 규칙이 자기 몸 여유로 안전을 맡는다 — 두 여유가 겹치지 않는다). ")
		TEXT("0 = 10-16 그대로(둘레 위). 0~5 m. Play 전에 바꾼다. 명령줄 -EcoV3WolfBodyMargin= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarShelterFood(
		TEXT("eco.IntegratedV3.ShelterFood"),
		1,
		TEXT("통합 v3 모드의 은신처 먹이 부족 (1 = 켬, 기본 — 10-17 야생 2단계 1, 사용자 결정 '은신처는 안전하지만 먹이가 적다'). 은신처 원과 조금이라도 겹치는 ")
		TEXT("먹이 셀의 용량과 재생 속도가 밖의 15% 다(파이썬 configs/v3_wild2_pack_mirror.yaml·v3_wild2_obstacle_mirror.yaml realism_cover_food). 배고픈 사슴은 밖으로 나와야 한다. ")
		TEXT("0 = 은신처 셀은 재생만 0.3배(R1b 학습 세계). Play 전에 바꾼다. 명령줄 -EcoV3ShelterFood= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarWolvesPerRegion(
		TEXT("eco.IntegratedV3.WolvesPerRegion"),
		4,
		TEXT("통합 v3 모드의 지역 무대마다 늑대 수 (기본 4 — 10-17 야생 2단계 2 늑대 무리, 잠행 2·추격 2, 짝수 순번 = 잠행-돌진형). 사슴 두뇌 R1b 의 학습 범위 ")
		TEXT("(보통 위협 2~12) 안이어야 하므로 0~12 로 자른다. 2 = 10-17 전 그대로. Play 전에 바꾼다. 명령줄 -EcoV3Wolves= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarPackHunt(
		TEXT("eco.IntegratedV3.PackHunt"),
		1,
		TEXT("통합 v3 모드의 늑대 무리 협동 사냥 (1 = 켬, 기본 — 10-17 야생 2단계 2, 파이썬 configs/v3_wild2_pack_mirror.yaml wild_pack). 한 늑대가 사슴을 쫓는 동안 ")
		TEXT("사냥 중이고 전력으로 달리지 않는 동료(120 m 안)가 그 사슴이 달아날 곳 — 향하는 은신처의 문(반지름 + 몸 여유), 없으면 도주선 앞 12 m — 으로 가서 ")
		TEXT("기다린다(2 m 안이면 멈춰 사슴 쪽을 본다). 늑대는 여전히 은신처에 못 들어가고 배부르면 쉰다. 0 = 늑대마다 따로 사냥(10-17 전). Play 전에 바꾼다. ")
		TEXT("명령줄 -EcoV3PackHunt= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarObstacles(
		TEXT("eco.IntegratedV3.Obstacles"),
		1,
		TEXT("통합 v3 모드의 세로 장애물 (1 = 켬, 기본 — 10-17 야생 2단계 3, 파이썬 configs/v3_wild2_obstacle_mirror.yaml obstacles). 무대 안 레벨의 충돌하는 나무·바위")
		TEXT("(스태틱 메시·폴리지 인스턴스, 팀 이동 제약과 같은 WorldStatic 막음)를 읽기만 해서 원판으로 만든다. 사슴·늑대는 원판 둘레를 따라 미끄러지고, ")
		TEXT("원판이 눈길을 가린다(발소리는 가리지 않는다). 원판 밑 먹이 셀은 그만큼 먹이가 적다. 원판이 없는 무대는 아무것도 바뀌지 않는다. ")
		TEXT("0 = 끔(10-17 야생 2단계 2 그대로). Play 전에 바꾼다. 명령줄 -EcoV3Obstacles= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarObstacleDetour(
		TEXT("eco.IntegratedV3.ObstacleDetour"),
		1,
		TEXT("통합 v3 모드의 장애물 돌아가기 (1 = 켬, 기본 — 10-17 장애물 끼임 고침, 파이썬 configs/v3_wild2_obstacle_mirror.yaml obstacles.detour). ")
		TEXT("사슴·늑대가 원판(나무 줄기·바위)에 막히면 가려던 쪽에서 가장 적게 돈 빈 방향으로 돌아가고, 앞 3 m 가 트일 때까지 같은 쪽으로 돈다(최대 6 초). ")
		TEXT("돕는 늑대는 2 초 넘게 돌아가거나 기어가면 5 초 동안 돕지 않는다. eco.IntegratedV3.Obstacles 1 이고 원판이 있을 때만 쓴다(원판이 없는 무대는 그대로). ")
		TEXT("0 = 미끄러짐만(10-17 야생 2단계 3 그대로). Play 전에 바꾼다. 명령줄 -EcoV3ObstacleDetour= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<FString> CVarObstacleExport(
		TEXT("eco.IntegratedV3.ObstacleExport"),
		TEXT(""),
		TEXT("통합 v3 모드의 장애물 원판 목록 JSON 경로 (빈 값 = 안 씀, 기본). 무대를 만든 뒤 지역마다 원판(무대 단위 x, y, r)을 쓴다 — 파이썬 거울 ")
		TEXT("results/v3/mirror/run_mirror.py --unreal-obstacles 가 같은 원판으로 돈다. 명령줄 -EcoV3ObstacleExport=<경로> 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<FString> CVarObstacleImport(
		TEXT("eco.IntegratedV3.ObstacleImport"),
		TEXT(""),
		TEXT("통합 v3 모드의 장애물 원판 가져오기 JSON 경로 (빈 값 = 안 씀, 기본). 측정 전용: 지역 이름이 같은 무대는 레벨에서 읽은 원판 대신 이 원판(무대 단위 x, y, r)을 ")
		TEXT("쓴다 — 레벨에 보이는 물체가 없는 원판이라 화면용이 아니다(eco.V3Debug 로만 보인다). 파이썬 거울이 만든 원판(results/v3/wild2/make_obstacle_maps.py)으로 ")
		TEXT("같은 원판 짝 비교를 할 때 쓴다. eco.IntegratedV3.Obstacles 1 일 때만. 명령줄 -EcoV3ObstacleImport=<경로> 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarStageTrees(
		TEXT("eco.IntegratedV3.StageTrees"),
		0,
		TEXT("통합 v3 모드의 실행 중 무대 나무 (0 = 끔, 기본 — 10-18 사용자 '일단 플레이시 장애물이 생성되게 하지 말고 그냥 우리 통합레벨에 배치를 해'). ")
		TEXT("나무는 통합 레벨에 놓은 액터다(폴더 EcoV3_Trees, 꼬리표 EcoV3Tree·EcoV3Trunk — 편집기 명령 -run=EcoV3PlaceTrees). 레벨 읽기가 줄기 막이를 원판으로 읽는다. ")
		TEXT("1 = 예비(10-17 그대로): 레벨 나무가 없는 무대에만 고정 배치 표(TreeLayoutV3.h — 숲 24·고지 9·메마른 땅 0 그루, 파이썬 make_tree_layout.py)대로 ")
		TEXT("팀 나무(Beech_Tree)를 충돌 없이 놓고 줄기 원판을 세계에 넣는다(파이썬 configs/v3_wild2_trees_mirror.yaml 과 같은 원판). 시작 자리는 줄기를 피한다. ")
		TEXT("eco.IntegratedV3.Obstacles 1 이고 무대 한 변 120 m 일 때만. Play 전에 바꾼다. 명령줄 -EcoV3StageTrees= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarWeather(
		TEXT("eco.IntegratedV3.Weather"),
		1,
		TEXT("통합 v3 모드의 지역 날씨 (1 = 켬, 기본 — 10-18 야생 3단계, 파이썬 configs/v3_wild3_mirror.yaml wild_weather). 팀 설계대로 숲 = 비, 고지 = 눈, 메마른 땅 = 맑음. ")
		TEXT("비는 사슴·늑대 시야 × 0.9 (사슴 탐지 40 → 36 m, 늑대 28 → 25.2 m)·사슴 청각 × 0.5, 눈은 시야 × 0.7·사슴 이동 × 0.6·늑대 이동 × 0.85, 관측 visibility × 시야. ")
		TEXT("비·눈은 eco.IntegratedV3.WeatherVisuals 1 이면 카메라 곁에 보인다. 0 = 날씨 없음(10-17 그대로). Play 전에 바꾼다. 명령줄 -EcoV3Weather= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<FString> CVarWeatherForest(
		TEXT("eco.IntegratedV3.WeatherForest"),
		TEXT(""),
		TEXT("통합 v3 모드 숲(Forest) 날씨 덮기 '날씨[:세기]' (날씨 = clear·rain·snow, 세기 0~1). 빈 값 = 팀 설계 기본(비 1). 측정·연출 전용 — 파이썬 거울과 다르면 짝 비교가 ")
		TEXT("맞지 않는다. Play 전에 바꾼다 (Play 중에 바꾸면 환경 감시 eco.IntegratedV3.EnvWatch 1 이 다음 결정 스텝 경계에서 넣는다 — 10-21). 명령줄 -EcoV3WeatherForest= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<FString> CVarWeatherHighland(
		TEXT("eco.IntegratedV3.WeatherHighland"),
		TEXT(""),
		TEXT("통합 v3 모드 고지(Highland) 날씨 덮기 '날씨[:세기]'. 빈 값 = 팀 설계 기본(눈 1). Play 전에 바꾼다 (Play 중에 바꾸면 환경 감시가 다음 결정 스텝 경계에서 넣는다). ")
		TEXT("명령줄 -EcoV3WeatherHighland= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<FString> CVarWeatherBarren(
		TEXT("eco.IntegratedV3.WeatherBarren"),
		TEXT(""),
		TEXT("통합 v3 모드 메마른 땅(Barren) 날씨 덮기 '날씨[:세기]'. 빈 값 = 팀 설계 기본(맑음). Play 전에 바꾼다 (Play 중에 바꾸면 환경 감시가 다음 결정 스텝 경계에서 넣는다). ")
		TEXT("명령줄 -EcoV3WeatherBarren= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<int32> CVarWeatherVisuals(
		TEXT("eco.IntegratedV3.WeatherVisuals"),
		1,
		TEXT("통합 v3 모드의 비·눈 연출 (1 = 켬, 기본 — 10-18). 카메라(보기 대상)가 비 오는 지역 안이면 카메라 곁에 팀 Rain_System 과 빗소리 A_Rain_Cue 를, 눈 오는 지역 안이면 ")
		TEXT("NS_Blizzard 를 켜고, 나오면 곧 끈다(빗소리도 멈춤). 레벨·애셋은 그대로. 그리기만 바뀐다(규칙·관측 그대로). 그릴 수 없는 실행·전용 서버는 늘 끔. ")
		TEXT("eco.IntegratedV3.Weather 0 이면 아무것도 하지 않는다. 0 = 연출 없음. 명령줄 -EcoV3WeatherVisuals= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarWeatherRainDensity(
		TEXT("eco.IntegratedV3.WeatherRainDensity"),
		1.0f,
		TEXT("통합 v3 모드 비 연출의 빗줄기 수 배수 (기본 1 = 팀 블루프린트 BP_SHC_RainRegionalWeather 와 같은 Rain_System User.SpawnRate 500 × 세기). 맑은 낮 하늘에서는 ")
		TEXT("팀 화면처럼 옅다 — 발표용으로 2~4 를 쓸 수 있다. 화면만 바뀐다(규칙·관측 그대로). 0.1~10 으로 자른다. 명령줄 -EcoV3WeatherRainDensity= 는 시작값."),
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

	static TAutoConsoleVariable<int32> CVarObsParityLog(
		TEXT("eco.IntegratedV3.ObsParityLog"),
		0,
		TEXT("통합 v3 모드의 R5 장애물 관측 대조 기록 (10-19, 계약 POLICY_CONTRACT_V3.md 2-4). 0 = 끔(기본). N > 0 이면 전역 스텝 N 개마다 지역마다 산 사슴마다 ")
		TEXT("'[EcoV3Obs]' 한 줄(입력·E·N·가림·관측 세 칸)과 지역마다 처음 한 번 원판 줄을 남기고, 관측 18 두뇌여도 세 칸을 만든다(결정은 그대로 — 망은 18 칸만 읽는다). ")
		TEXT("파이썬 herbivore_rl/results/v3/r5/unreal_parity.py 가 견준다. 측정 전용. Play 전에 바꾼다. 명령줄 -EcoV3ObsParityLog= 는 시작값."),
		ECVF_Default);

#if !UE_BUILD_SHIPPING
	// 10-22 숲 시야 (파이썬 obstacles.foliage 를 옮김 — 측정·실험 전용이라 개발 빌드만. Shipping 은 늘 끔)
	static TAutoConsoleVariable<int32> CVarFoliage(
		TEXT("eco.IntegratedV3.Foliage"),
		0,
		TEXT("통합 v3 모드의 숲 시야 (0 = 끔, 기본 — 10-22, 파이썬 features.obstacles.foliage 를 옮김. 개발 빌드 전용). 1 이면 나무 원판(레벨·무대 나무 줄기 — 바위는 빼고)마다 ")
		TEXT("반지름 eco.IntegratedV3.FoliageR 의 잎 원을 두고, 사슴·늑대 눈길이 잎 원들 안(겹친 몫은 한 번)을 eco.IntegratedV3.FoliageBlock 넘게 지나면 줄기처럼 가린다 — ")
		TEXT("사슴의 늑대 알아챔·늑대의 표적 고르기·관측 threat_hidden. 발소리는 그대로. R1b 두뇌는 이 세계에서 배우지 않았다(측정용). eco.IntegratedV3.Obstacles 1 일 때만. ")
		TEXT("Play 전에 바꾼다. 명령줄 -EcoV3Foliage= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarFoliageR(
		TEXT("eco.IntegratedV3.FoliageR"),
		6.0f,
		TEXT("숲 시야 잎 원 반지름 (m, 기본 6 = 파이썬 r 3.0 단위). 0.5~20 m. eco.IntegratedV3.Foliage 1 일 때만. Play 전에 바꾼다. 명령줄 -EcoV3FoliageR= 는 시작값."),
		ECVF_Default);

	static TAutoConsoleVariable<float> CVarFoliageBlock(
		TEXT("eco.IntegratedV3.FoliageBlock"),
		4.0f,
		TEXT("숲 시야 문턱 (m, 기본 4 = 파이썬 block 2.0 단위): 눈길이 잎 원들 안을 이만큼 이상 지나면 가린다 — 이보다 가까운 개체는 잎 속에서도 늘 보인다. 0.5~40 m. ")
		TEXT("eco.IntegratedV3.Foliage 1 일 때만. Play 전에 바꾼다. 명령줄 -EcoV3FoliageBlock= 는 시작값."),
		ECVF_Default);

	// 10-21 실시간 두뇌 교체 (LIVE_ADAPT_SPEC.md 5.2·5.4 — 개발 빌드만. Shipping 은 늘 끔이라 감시 폴더 기본도 없다)
	static TAutoConsoleVariable<int32> CVarAutoAdapt(
		TEXT("eco.IntegratedV3.AutoAdapt"),
		0,
		TEXT("통합 v3 모드 적응 고리 주 스위치 (0 = 끔, 기본 — 10-21 '게임 중 실시간 두뇌 교체'). 1 이면 두뇌 감시 폴더 기본 = Saved/EcoAdapt/brains (eco.V3Brain.WatchFolder 가 ")
		TEXT("비었을 때만)·상태 파일 기본 = Saved/EcoAdapt/status.json (eco.V3Brain.StatusFile 이 비었을 때만), Play 시작 때 그 폴더에 있던 두뇌 파일은 읽지 않고 ")
		TEXT("뒤에 나타난 파일만 바꾼다, 화면 상태 줄. 환경 변화 자동 스냅숏(eco.IntegratedV3.AutoSnapshot -1)도 이 값을 따른다. Play 전에 바꾼다. ")
		TEXT("명령줄 -EcoV3AutoAdapt (또는 -EcoV3AutoAdapt=0|1) 는 시작값."),
		ECVF_Default);
#endif

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

	// 실시간 두뇌 교체 화면 알림 키 (10-21 — 고정 키라 PIE 창이 여럿이어도 한 줄. 지역 화면 줄 730000·731000 + 지역과 겹치지 않는다)
	constexpr uint64 kNoticeKeyBrain = 732000;      // 새 두뇌·되돌림 (같은 키 — 마지막 것만)
	constexpr uint64 kNoticeKeyReject = 732001;     // 두뇌 파일 거부
	constexpr uint64 kNoticeKeyEnv = 732002;        // 환경 바뀜
	constexpr uint64 kNoticeKeySnapshot = 732003;   // 스냅숏 내보냄
	constexpr uint64 kNoticeKeyStatus = 732004;     // 상태 줄 (1 초마다)
	/** 바꾸기·되돌리기 알림을 찍는 지연 (실시간 초 — 알림이 화면에 그려진 뒤). */
	constexpr double kNoticeShotDelaySeconds = 1.5;

	/**
	 * 두뇌 알림 글자 (LIVE_ADAPT_SPEC.md 5.4): 되돌림 '두뇌 되돌림 → 판 2 (id)' (내장이면 '두뇌 되돌림 → 내장 두뇌 (판 0)', 판 없는 파일이면 id 만),
	 * 바꾸기 '새 두뇌 — 판 3 · id · 환경: … · 관문: … · 되돌리기 eco.V3Brain.Rollback' (빈 칸은 뺀다).
	 */
	FString BrainNoticeText(const FEcoV3Brain& B, bool bRollback)
	{
		const FString Round = B.RoundTag();
		if (bRollback)
		{
			return B.bBuiltin	  ? FString(TEXT("두뇌 되돌림 → 내장 두뇌 (판 0)"))
				   : Round.IsEmpty() ? FString::Printf(TEXT("두뇌 되돌림 → %s"), *B.Id)
									 : FString::Printf(TEXT("두뇌 되돌림 → %s (%s)"), *Round, *B.Id);
		}
		FString Text = B.bBuiltin	   ? FString::Printf(TEXT("새 두뇌 — 내장 두뇌 (판 0) · %s"), *B.Id)
					   : Round.IsEmpty() ? FString::Printf(TEXT("새 두뇌 — %s"), *B.Id)
										 : FString::Printf(TEXT("새 두뇌 — %s · %s"), *Round, *B.Id);
		if (!B.AdaptEnv.IsEmpty())
		{
			Text += FString::Printf(TEXT(" · 환경: %s"), *B.AdaptEnv);
		}
		if (!B.AdaptGate.IsEmpty())
		{
			Text += FString::Printf(TEXT(" · 관문: %s"), *B.AdaptGate);
		}
		Text += TEXT(" · 되돌리기 eco.V3Brain.Rollback");
		return Text;
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

const TCHAR* EcoV3Integrated::RouteNameKo(int32 Route)
{
	return Route == EcoWorldV3::kRouteRun ? TEXT("도주(트인 쪽)") : Route == EcoWorldV3::kRouteShelter ? TEXT("도주(은신처)") : nullptr;
}

FColor EcoV3Integrated::RouteColor(int32 Route, const FColor& Fallback)
{
	// 10-24 두 길 두뇌 (이식 계획서 12절 질문 9 — 정한 것): RUN 연노랑, SHELTER 하늘색. 반사 도주 주황(255,110,20)·웅크림 파랑(60,150,255)·
	// 두뇌 도망 노랑(255,215,0)·경계(255,175,80)와 겹치지 않게
	return Route == EcoWorldV3::kRouteRun ? FColor(255, 240, 120) : Route == EcoWorldV3::kRouteShelter ? FColor(110, 230, 255) : Fallback;
}

FString EcoV3Integrated::DeerLabel(const EcoRepertoireV3::FRepState& Rep, const EcoWorldV3::FHerbBody& Body, bool bRecentRepro,
								   FColor& OutColor, int32 KeepMode, bool bReserveOn, int32 Route)
{
	const double E = FMath::Clamp(Body.Energy, 0.0, 1.0);
	// 도주 반사 거리 덮기 중이면 행동 이름 대신 덮기 이름 ('경계(먹으며 멀어짐) 64%', '도주(안전해질 때까지) 58%').
	// 경계는 두뇌가 먹기를 고른 동안만 (두뇌가 도망·숨기·잠이면 그 행동 이름 그대로 — world.py _wf_alert_control 과 같은 조건)
	const bool bKeep = KeepMode == EcoWorldV3::kKeepPanic || KeepMode == EcoWorldV3::kKeepShelter
					   || (KeepMode == EcoWorldV3::kKeepAlert && Rep.Behavior == EcoRepertoireV3::kGraze);
	// 10-24 두 길 두뇌: 도주 덮기면 고른 길 ('도주(트인 쪽) 58%'·'도주(은신처) 58%'). 길이 없으면(길 끈 두뇌) 지금 글자 그대로
	const TCHAR* RouteKo = KeepMode == EcoWorldV3::kKeepPanic ? RouteNameKo(Route) : nullptr;
	FString Label = bKeep ? FString::Printf(TEXT("%s %d%%"), RouteKo ? RouteKo : KeepModeNameKo(KeepMode), FMath::RoundToInt32(100.0 * E))
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
				   : KeepMode == EcoWorldV3::kKeepPanic ? (RouteKo ? RouteColor(Route, FColor(255, 110, 20)) : FColor(255, 110, 20))
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
	S.WolfBodyMarginM = static_cast<double>(CVarWolfBodyMargin.GetValueOnGameThread());
	S.bShelterFood = CVarShelterFood.GetValueOnGameThread() != 0;
	S.WolvesPerRegion = FMath::Clamp(CVarWolvesPerRegion.GetValueOnGameThread(), 0, 12);
	S.bPackHunt = CVarPackHunt.GetValueOnGameThread() != 0;
	S.bFlightHoldAwake = CVarFlightHoldAwake.GetValueOnGameThread() != 0;
	S.bFlightEdgeAvoid = CVarFlightEdgeAvoid.GetValueOnGameThread() != 0;
	S.bProtectedRefuges = CVarProtectedRefuges.GetValueOnGameThread() != 0;
	S.bSocialControl = CVarSocialControl.GetValueOnGameThread() != 0;
	S.bObstacles = CVarObstacles.GetValueOnGameThread() != 0;
	S.bObstacleDetour = CVarObstacleDetour.GetValueOnGameThread() != 0;
#if !UE_BUILD_SHIPPING
	S.bFoliage = CVarFoliage.GetValueOnGameThread() != 0;
	{
		const double Rm = static_cast<double>(CVarFoliageR.GetValueOnGameThread());
		const double Bm = static_cast<double>(CVarFoliageBlock.GetValueOnGameThread());
		S.FoliageRM = FMath::IsFinite(Rm) ? FMath::Clamp(Rm, 0.5, 20.0) : 6.0;
		S.FoliageBlockM = FMath::IsFinite(Bm) ? FMath::Clamp(Bm, 0.5, 40.0) : 4.0;
	}
#endif
	S.ObstacleExportPath = CVarObstacleExport.GetValueOnGameThread();
	S.ObstacleImportPath = CVarObstacleImport.GetValueOnGameThread();
	S.bStageTrees = CVarStageTrees.GetValueOnGameThread() != 0;
	S.bWeather = CVarWeather.GetValueOnGameThread() != 0;
	S.WeatherForest = CVarWeatherForest.GetValueOnGameThread();
	S.WeatherHighland = CVarWeatherHighland.GetValueOnGameThread();
	S.WeatherBarren = CVarWeatherBarren.GetValueOnGameThread();
	S.bWeatherVisuals = CVarWeatherVisuals.GetValueOnGameThread() != 0;
	{
		const double Density = static_cast<double>(CVarWeatherRainDensity.GetValueOnGameThread());
		S.WeatherRainDensity = FMath::IsFinite(Density) ? FMath::Clamp(Density, 0.1, 10.0) : 1.0;
	}
	return S;
}

bool FEcoV3IntegratedSettings::ParseWeather(const FString& Text, int32& OutKind, double& OutIntensity)
{
	FString Body = Text.TrimStartAndEnd();
	Body.ReplaceInline(TEXT(","), TEXT(" "));
	Body.ReplaceInline(TEXT(":"), TEXT(" "));
	TArray<FString> Parts;
	Body.ParseIntoArrayWS(Parts);
	if (Parts.Num() < 1 || Parts.Num() > 2)
	{
		return false;
	}
	const FString Name = Parts[0].ToLower();
	int32 Kind = INDEX_NONE;
	if (Name == TEXT("clear") || Name == TEXT("맑음"))
	{
		Kind = EcoWorldV3::kWeatherClear;
	}
	else if (Name == TEXT("rain") || Name == TEXT("비"))
	{
		Kind = EcoWorldV3::kWeatherRain;
	}
	else if (Name == TEXT("snow") || Name == TEXT("눈"))
	{
		Kind = EcoWorldV3::kWeatherSnow;
	}
	if (Kind == INDEX_NONE)
	{
		return false;
	}
	double Intensity = Kind == EcoWorldV3::kWeatherClear ? 0.0 : 1.0;
	if (Parts.Num() == 2)
	{
		if (!Parts[1].IsNumeric())
		{
			return false;
		}
		const double V = FCString::Atod(*Parts[1]);
		if (!FMath::IsFinite(V))
		{
			return false;
		}
		Intensity = FMath::Clamp(V, 0.0, 1.0);
	}
	OutKind = Kind;
	OutIntensity = Kind == EcoWorldV3::kWeatherClear ? 0.0 : Intensity;
	return true;
}

EcoWorldV3::FWeatherConfig FEcoV3IntegratedSettings::WeatherFor(FName RegionId) const
{
	EcoWorldV3::FWeatherConfig W;
	if (!bWeather)
	{
		return W;
	}
	W.bEnabled = true;
	for (const EcoWorldV3::FRegionWeatherDefault& D : EcoWorldV3::kRegionWeatherDefaults)
	{
		if (RegionId == FName(UTF8_TO_TCHAR(D.Region)))
		{
			W.Kind = D.Kind;
			W.Intensity = D.Intensity;
		}
	}
	const FString* Override = RegionId == FName(TEXT("Forest"))	   ? &WeatherForest
							  : RegionId == FName(TEXT("Highland")) ? &WeatherHighland
							  : RegionId == FName(TEXT("Barren"))   ? &WeatherBarren
																	: nullptr;
	if (Override && !Override->IsEmpty())
	{
		int32 Kind = W.Kind;
		double Intensity = W.Intensity;
		if (ParseWeather(*Override, Kind, Intensity))
		{
			W.Kind = Kind;
			W.Intensity = Intensity;
		}
		else
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] %s 날씨 덮기 '%s' 를 못 읽었다 — 팀 설계 기본을 쓴다 ('날씨[:세기]', 날씨 = clear·rain·snow)"),
				   *RegionId.ToString(), **Override);
		}
	}
	return W;
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
	float MarginArg = 1.0f;
	if (FParse::Value(CmdLine, TEXT("EcoV3WolfBodyMargin="), MarginArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.WolfBodyMargin"), LexToString(MarginArg));
	}
	int32 ShelterFoodArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3ShelterFood="), ShelterFoodArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.ShelterFood"), LexToString(ShelterFoodArg));
	}
	int32 WolvesArg = 4;
	if (FParse::Value(CmdLine, TEXT("EcoV3Wolves="), WolvesArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.WolvesPerRegion"), LexToString(WolvesArg));
	}
	int32 PackArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3PackHunt="), PackArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.PackHunt"), LexToString(PackArg));
	}
	int32 RefugeArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3ProtectedRefuges="), RefugeArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.ProtectedRefuges"), LexToString(RefugeArg));
	}
	int32 SocialArg = 0;
	if (FParse::Value(CmdLine, TEXT("EcoV3SocialControl="), SocialArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.SocialControl"), LexToString(SocialArg));
	}
	int32 ObstacleArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3Obstacles="), ObstacleArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.Obstacles"), LexToString(ObstacleArg));
	}
	int32 DetourArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3ObstacleDetour="), DetourArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.ObstacleDetour"), LexToString(DetourArg));
	}
	FString ObstacleExportArg;
	if (FParse::Value(CmdLine, TEXT("EcoV3ObstacleExport="), ObstacleExportArg) && !ObstacleExportArg.IsEmpty())
	{
		SetIfUnset(TEXT("eco.IntegratedV3.ObstacleExport"), ObstacleExportArg);
	}
	FString ObstacleImportArg;
	if (FParse::Value(CmdLine, TEXT("EcoV3ObstacleImport="), ObstacleImportArg) && !ObstacleImportArg.IsEmpty())
	{
		SetIfUnset(TEXT("eco.IntegratedV3.ObstacleImport"), ObstacleImportArg);
	}
	int32 TreesArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3StageTrees="), TreesArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.StageTrees"), LexToString(TreesArg));
	}
#if !UE_BUILD_SHIPPING
	int32 FoliageArg = 0;
	if (FParse::Value(CmdLine, TEXT("EcoV3Foliage="), FoliageArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.Foliage"), LexToString(FoliageArg));
	}
	float FoliageRArg = 6.0f;
	if (FParse::Value(CmdLine, TEXT("EcoV3FoliageR="), FoliageRArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.FoliageR"), LexToString(FoliageRArg));
	}
	float FoliageBlockArg = 4.0f;
	if (FParse::Value(CmdLine, TEXT("EcoV3FoliageBlock="), FoliageBlockArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.FoliageBlock"), LexToString(FoliageBlockArg));
	}
#endif
	int32 WeatherArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3Weather="), WeatherArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.Weather"), LexToString(WeatherArg));
	}
	int32 WeatherVisualsArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3WeatherVisuals="), WeatherVisualsArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.WeatherVisuals"), LexToString(WeatherVisualsArg));
	}
	float RainDensityArg = 1.0f;
	if (FParse::Value(CmdLine, TEXT("EcoV3WeatherRainDensity="), RainDensityArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.WeatherRainDensity"), LexToString(RainDensityArg));
	}
	// 지역 날씨 덮기: 값 안의 ',' 는 명령줄에서 끊기므로 '날씨:세기' 꼴로 받는다 (FParse::Value 는 쉼표에서 멈추지 않게 한다)
	const TCHAR* const RegionWeatherArgs[3][2] = {{TEXT("EcoV3WeatherForest="), TEXT("eco.IntegratedV3.WeatherForest")},
												  {TEXT("EcoV3WeatherHighland="), TEXT("eco.IntegratedV3.WeatherHighland")},
												  {TEXT("EcoV3WeatherBarren="), TEXT("eco.IntegratedV3.WeatherBarren")}};
	for (const auto& Pair : RegionWeatherArgs)
	{
		FString Value;
		if (FParse::Value(CmdLine, Pair[0], Value, false) && !Value.IsEmpty())
		{
			SetIfUnset(Pair[1], Value);
		}
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
	// 두뇌 바꾸기 (10-18, EcoV3Brain.h — 개발 빌드. 파일 이름·경로는 쉼표에서 끊지 않는다)
	const TCHAR* const BrainArgs[3][2] = {{TEXT("EcoV3Brain="), TEXT("eco.V3Brain.Startup")},
										  {TEXT("EcoV3BrainSwapTo="), TEXT("eco.V3Brain.SwapFile")},
										  {TEXT("EcoV3BrainWatch="), TEXT("eco.V3Brain.WatchFolder")}};
	for (const auto& Pair : BrainArgs)
	{
		FString Value;
		if (FParse::Value(CmdLine, Pair[0], Value, false) && !Value.IsEmpty())
		{
			SetIfUnset(Pair[1], Value);
		}
	}
	float SwapAtArg = -1.0f;
	if (FParse::Value(CmdLine, TEXT("EcoV3BrainSwapAt="), SwapAtArg))
	{
		SetIfUnset(TEXT("eco.V3Brain.SwapAtSeconds"), LexToString(SwapAtArg));
	}
	// R5 장애물 관측 대조 기록 (10-19)
	int32 ObsParityArg = 0;
	if (FParse::Value(CmdLine, TEXT("EcoV3ObsParityLog="), ObsParityArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.ObsParityLog"), LexToString(ObsParityArg));
	}
	// 환경 스냅숏 (10-18 적응 고리, EcoV3Snapshot.cpp — 경로는 쉼표에서 끊지 않는다)
	float SnapshotAtArg = -1.0f;
	if (FParse::Value(CmdLine, TEXT("EcoV3SnapshotAt="), SnapshotAtArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.SnapshotAt"), LexToString(SnapshotAtArg));
	}
	FString SnapshotOutArg;
	if (FParse::Value(CmdLine, TEXT("EcoV3SnapshotOut="), SnapshotOutArg, false) && !SnapshotOutArg.IsEmpty())
	{
		SetIfUnset(TEXT("eco.IntegratedV3.SnapshotOut"), SnapshotOutArg);
	}
	// 적응 고리 (10-21 실시간 두뇌 교체 — 개발 빌드): -EcoV3AutoAdapt 는 1, -EcoV3AutoAdapt=0|1 은 그 값
	int32 AutoAdaptArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3AutoAdapt="), AutoAdaptArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.AutoAdapt"), LexToString(AutoAdaptArg));
	}
	else if (FParse::Param(CmdLine, TEXT("EcoV3AutoAdapt")))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.AutoAdapt"), TEXT("1"));
	}
	// 환경 바뀜 감시·자동 스냅숏 (10-21 실시간 두뇌 교체, EcoV3EnvWatch.cpp·EcoV3Snapshot.cpp — 개발 빌드. 폴더는 쉼표에서 끊지 않는다)
	int32 EnvWatchArg = 1;
	if (FParse::Value(CmdLine, TEXT("EcoV3EnvWatch="), EnvWatchArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.EnvWatch"), LexToString(EnvWatchArg));
	}
	int32 AutoSnapshotArg = -1;
	if (FParse::Value(CmdLine, TEXT("EcoV3AutoSnapshot="), AutoSnapshotArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.AutoSnapshot"), LexToString(AutoSnapshotArg));
	}
	float SnapshotEveryArg = 0.0f;
	if (FParse::Value(CmdLine, TEXT("EcoV3SnapshotEvery="), SnapshotEveryArg))
	{
		SetIfUnset(TEXT("eco.IntegratedV3.SnapshotEvery"), LexToString(SnapshotEveryArg));
	}
	FString AutoSnapshotOutArg;
	if (FParse::Value(CmdLine, TEXT("EcoV3AutoSnapshotOut="), AutoSnapshotOutArg, false) && !AutoSnapshotOutArg.IsEmpty())
	{
		SetIfUnset(TEXT("eco.IntegratedV3.AutoSnapshotOut"), AutoSnapshotOutArg);
	}
#if !UE_BUILD_SHIPPING
	// 시험용 예약 (10-21 — 시연 대본): -EcoV3TestAt=<초> -EcoV3TestCmd="명령1; 명령2" (쌍 여러 개, 명령은 따옴표 안 ';'·공백 그대로)
	ParseCommandLineTestAts(CmdLine);
#endif
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

bool UEcoPolicyV3IntegratedSubsystem::IsAutoAdaptEnabled()
{
#if !UE_BUILD_SHIPPING
	EcoPolicyV3IntegratedImpl::EnsureCommandLineApplied();
	return EcoPolicyV3IntegratedImpl::CVarAutoAdapt.GetValueOnGameThread() != 0;
#else
	return false;
#endif
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
	// 환경 바뀜 감시 (10-21, EcoV3EnvWatch.cpp): 액터 생김·지움 알림, 명령줄 예약, 시작 줄
	BeginEnvWatch(InWorld);
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
		   *(Settings.bShelterSafe
				 ? FString::Printf(TEXT("안전 (eco.IntegratedV3.ShelterSafe 1, 10-16) — 원 안 사슴은 표적·포획에서 빠지고 늑대는 반지름 + 몸 여유 %.2f m 둘레를 ")
								   TEXT("따라 미끄러짐 (eco.IntegratedV3.WolfBodyMargin, 10-17)"),
								   Settings.WolfBodyMarginUnits() * EcoRepertoireV3::kUnitCm / 100.0)
				 : FString(Settings.bProtectedRefuges
							   ? TEXT("팀 규칙 안전 (eco.IntegratedV3.ShelterSafe 0·ProtectedRefuges 1 — 늑대 몸 여유 1 m, 쓸고 지나가기 막기, 파이썬과 다름)")
							   : TEXT("끔 (eco.IntegratedV3.ShelterSafe 0 — 은신처 안에서도 잡힘)"))),
		   Settings.bProtectedRefuges ? TEXT("켬 (eco.IntegratedV3.ProtectedRefuges 1 — 지워진 은신처 비활성·늦은 은신처 추가·잃은 HIDE 목표 풀기)")
									  : TEXT("끔 (eco.IntegratedV3.ProtectedRefuges 0)"));
	const EcoWorldV3::FShelterFoodConfig Sf;
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 은신처 먹이: %s"),
		   *(Settings.bShelterFood
				 ? FString::Printf(TEXT("부족 (eco.IntegratedV3.ShelterFood 1, 기본 — 10-17 야생 2단계 1) — 은신처 원과 겹치는 셀의 용량 %.0f%%·재생 %.0f%% (밖 대비), ")
									   TEXT("배고픈 사슴은 밖으로 나와야 함"),
								   100.0 * Sf.CapFrac, 100.0 * Sf.RegenFrac)
				 : FString(TEXT("끔 (eco.IntegratedV3.ShelterFood 0 — 은신처 셀은 재생만 0.3배, R1b 학습 세계)"))));
	const EcoThreatV3::FPackHuntConfig Pk;
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 늑대 무리: 지역마다 %d (eco.IntegratedV3.WolvesPerRegion) | 협동 사냥 %s"), Wolves,
		   *(Settings.bPackHunt
				 ? FString::Printf(TEXT("켬 (eco.IntegratedV3.PackHunt 1, 10-17 야생 2단계 2) — 한 늑대가 쫓는 사슴이 %.0f m 안이면 사냥 중인 동료가 그 사슴이 향하는 ")
									   TEXT("은신처의 문(%.0f m·±%.0f° 안) 또는 도주선 앞 %.0f m 로 가서 %.0f m 안이면 기다림"),
								   Pk.JoinR * MPerUnit, Pk.DoorR * MPerUnit, FMath::RadiansToDegrees(FMath::Acos(Pk.DoorCos)), Pk.Lead * MPerUnit,
								   Pk.WaitR * MPerUnit)
				 : FString(TEXT("끔 (eco.IntegratedV3.PackHunt 0 — 늑대마다 따로 사냥)"))));
	const EcoThreatV3::FDetourConfig Dt;   // 돌아가기 값 = 기본값 (MakeRegionWorldConfig 는 켬 칸만 바꾼다)
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 세로 장애물: %s"),
		   *(Settings.bObstacles
				 ? FString::Printf(TEXT("켬 (eco.IntegratedV3.Obstacles 1, 10-17 야생 2단계 3) — 무대 안 레벨의 충돌하는 나무·바위를 원판으로 읽어 사슴·늑대가 둘레를 따라 미끄러지고 ")
									   TEXT("눈길이 가린다(발소리는 못 가림), 원판 밑 먹이는 덮인 몫만큼 적다. 원판이 없는 무대는 그대로 | 돌아가기 %s%s"),
								   Settings.bObstacleDetour
									   ? *FString::Printf(TEXT("켬 (eco.IntegratedV3.ObstacleDetour 1, 10-17 끼임 고침) — 막히면 가장 적게 돈 빈 방향으로, 앞 %.0f m 가 트일 때까지 같은 쪽 (최대 %.0f 초), ")
															 TEXT("돕는 늑대는 %.0f 초 넘게 막히면 %.0f 초 쉼"),
														 Dt.Probe * MPerUnit, Dt.MaxSteps * EcoRepertoireV3::kStepSeconds, Dt.HelpBlock * EcoRepertoireV3::kStepSeconds,
														 Dt.HelpDrop * EcoRepertoireV3::kStepSeconds)
									   : TEXT("끔 (eco.IntegratedV3.ObstacleDetour 0 — 미끄러짐만)"),
								   Settings.ObstacleImportPath.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" | 측정 전용 원판 가져오기: %s"), *Settings.ObstacleImportPath))
				 : FString(TEXT("끔 (eco.IntegratedV3.Obstacles 0 — 읽기만 하고 세계에 넣지 않는다)"))));
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 숲 시야: %s"),
		   *(Settings.bFoliage && Settings.bObstacles
				 ? FString::Printf(TEXT("켬 (eco.IntegratedV3.Foliage 1, 10-22 — 측정용, R1b 는 배우지 않은 세계) — 나무 원판마다 잎 원 %.1f m, 눈길이 잎 안을 %.1f m 이상 지나면 가림 ")
									   TEXT("(사슴의 늑대 알아챔·늑대 표적·관측 threat_hidden, 발소리 그대로)"),
								   Settings.FoliageRM, Settings.FoliageBlockM)
				 : FString(TEXT("끔 (eco.IntegratedV3.Foliage 0, 기본 — 줄기만 가림)"))));
	{
		FString Counts;
		for (const EcoTreeLayoutV3::FStageTrees& St : EcoTreeLayoutV3::kStages)
		{
			Counts += FString::Printf(TEXT(" %s %d"), UTF8_TO_TCHAR(St.Region), St.Num);
		}
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 무대 나무: %s"),
			   *(Settings.bStageTrees && Settings.bObstacles
					 ? FString::Printf(TEXT("실행 중 놓기 켬 (eco.IntegratedV3.StageTrees 1, 예비 — 10-17) — 레벨 나무(꼬리표 %s)가 없는 무대에만 배치 표 %s (지문 %s, 무대 한 변 %.0f m):%s 그루, ")
										   TEXT("팀 메시 %s 를 충돌 없이 놓고 줄기 원판(밑동 반경 %.2f cm × 크기 %.1f~%.1f)을 세계에 넣음, 시작 자리는 줄기를 피함 (파이썬 configs/v3_wild2_trees_mirror.yaml)"),
									   *LevelTrunkTag().ToString(), UTF8_TO_TCHAR(EcoTreeLayoutV3::kVersion), UTF8_TO_TCHAR(EcoTreeLayoutV3::kDigest),
									   EcoTreeLayoutV3::kStageSizeUnits * EcoRepertoireV3::kUnitCm / 100.0, *Counts, UTF8_TO_TCHAR(EcoTreeLayoutV3::kMeshPath),
									   EcoTreeLayoutV3::kTrunkRadiusMeshCm, EcoTreeLayoutV3::kScaleLo, EcoTreeLayoutV3::kScaleHi)
					 : Settings.bObstacles
						   ? FString::Printf(TEXT("실행 중 놓기 끔 (eco.IntegratedV3.StageTrees 0, 기본 — 10-18) — 나무는 통합 레벨 액터다(폴더 %s, 꼬리표 %s·%s). 레벨 읽기가 줄기 막이를 ")
												 TEXT("원판으로 읽고 배치 표 %s 자리와 %.0f cm 안이면 표 값을 쓴다, 시작 자리는 줄기를 피함"),
											 LevelTreeFolder(), *LevelTreeTag().ToString(), *LevelTrunkTag().ToString(), UTF8_TO_TCHAR(EcoTreeLayoutV3::kVersion),
											 kLevelTreeSnapCm)
						   : FString(TEXT("끔 (eco.IntegratedV3.Obstacles 0 — v3 세계에 원판이 없다. 레벨 나무 줄기 막이는 팀 이동 제약에서는 그대로 막는다)"))));
	}
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 사슴 Social 연결: %s"),
		   Settings.bSocialControl ? TEXT("켬 (eco.IntegratedV3.SocialControl 1, 22eb1b6 — 기본 아님) — 무리 경보·은신처 슬롯이 v3 제어 뒤·이동 전에 사슴 제어를 바꾼다, 파이썬과 다름")
								   : TEXT("끔 (eco.IntegratedV3.SocialControl 0, 기본 — 사람 결정 10-17 (8): v3 사슴 움직임은 파이썬 세계 그대로, Social 처리기는 기록만)"));
	{
		// 지역 날씨 (10-18 야생 3단계): 지역마다 날씨·덮기, 배수 계수, 연출
		const EcoWorldV3::FWeatherConfig Wc;
		FString Table;
		for (const EcoWorldV3::FRegionWeatherDefault& D : EcoWorldV3::kRegionWeatherDefaults)
		{
			const EcoWorldV3::FWeatherConfig R = Settings.WeatherFor(FName(UTF8_TO_TCHAR(D.Region)));
			Table += FString::Printf(TEXT("%s%s %s%s"), Table.IsEmpty() ? TEXT("") : TEXT(" · "), UTF8_TO_TCHAR(D.Region), UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(R.Kind)),
									 R.Kind == EcoWorldV3::kWeatherClear ? TEXT("") : *FString::Printf(TEXT(" %.2f"), R.Intensity));
			if (R.Kind != D.Kind || R.Intensity != D.Intensity)
			{
				Table += TEXT(" (덮음 — 팀 설계·파이썬 거울과 다름)");
			}
		}
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 지역 날씨: %s"),
			   *(Settings.bWeather
					 ? FString::Printf(TEXT("켬 (eco.IntegratedV3.Weather 1, 10-18 야생 3단계 — 파이썬 configs/v3_wild3_mirror.yaml) — %s | 비 = 시야 × %.2f·사슴 청각 × %.2f, ")
										   TEXT("눈 = 시야 × %.2f·사슴 청각 × %.2f·사슴 이동 × %.2f·늑대 이동 × %.2f (세기 1, 세기 I 는 1 − (1 − 값)·I) | 관측 visibility × 시야 | 연출 %s"),
									   *Table, Wc.RainSight, Wc.RainHear, Wc.SnowSight, Wc.SnowHear, Wc.SnowDeerSpeed, Wc.SnowWolfSpeed,
									   !Settings.bWeatherVisuals ? TEXT("끔 (eco.IntegratedV3.WeatherVisuals 0)")
									   : !FApp::CanEverRender()  ? TEXT("없음 (그리지 않는 실행)")
																 : TEXT("켬 (eco.IntegratedV3.WeatherVisuals 1 — 카메라가 비·눈 지역 안이면 카메라 곁에 팀 Rain_System·A_Rain_Cue·NS_Blizzard)"))
					 : FString(TEXT("끔 (eco.IntegratedV3.Weather 0 — 날씨 없음)"))));
	}
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 사슴 감지: 위협 시야 %s | 늑대 발소리 %s"),
		   Settings.bRealismVision ? TEXT("300° (eco.IntegratedV3.RealismVision 1 — 바로 뒤 60° 만 사각)") : TEXT("120° (eco.IntegratedV3.RealismVision 0 — R1b 그대로)"),
		   Settings.bRealismHearing ? TEXT("켬 (eco.IntegratedV3.RealismHearing 1 — 쫓아 달리면 최대 40 m, 어슬렁거리면 4 m, 서 있으면 없음)")
									: TEXT("끔 (eco.IntegratedV3.RealismHearing 0)"));
	{
		// 두뇌 바꾸기 (10-18, EcoV3Brain.h): 시작 두뇌는 줄에 넣어 첫 결정 스텝 경계(SyncBrain)에서 바꾼다 — 입양 첫 결정부터 그 두뇌다
		FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
		// 적응 고리 (10-21 실시간 두뇌 교체): 켜면 감시 폴더·상태 파일 기본을 정하고(콘솔 변수가 비었을 때만 쓰인다), 지금 폴더에 있는 두뇌 파일은
		// 읽지 않게 감시를 준비한다 — Play 뒤에 나타난 파일만 바꾼다. 끄면 앞 Play 가 남긴 기본을 지운다
		const bool bAutoAdapt = IsAutoAdaptEnabled();
		Reg.SetDefaultWatchFolder(bAutoAdapt ? FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("EcoAdapt/brains")) : FString());
		Reg.SetDefaultStatusFile(bAutoAdapt ? FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("EcoAdapt/status.json")) : FString());
		bAdaptDefaultsSet = bAutoAdapt;
		// Play 번호: 이 Play 의 스냅숏에 적고, 파이썬이 두뇌 파일 adapt.play_id 로 돌려준다 — 앞 Play 에서 시작한 판의 두뇌는 받지 않는다
		PlayId = bAutoAdapt ? FString::Printf(TEXT("p%s_%08x"), *FDateTime::UtcNow().ToString(TEXT("%Y%m%dT%H%M%S")), FGuid::NewGuid().A) : FString();
		Reg.SetWatchPlayId(PlayId);
		if (bAutoAdapt)
		{
			Reg.PrimeWatch();
		}
		ShownRejectSerial = Reg.GetLastWatchReject().Serial;   // 앞 Play 의 거부는 다시 알리지 않는다
		const FString Startup = EcoV3Brain::StartupFile();
		if (!Startup.IsEmpty())
		{
			const FEcoV3BrainLoad L = FEcoV3BrainRegistry::LoadFile(Startup);
			if (L.Ok())
			{
				Reg.Queue(L.Brain.ToSharedRef(), FString::Printf(TEXT("시작 두뇌 eco.V3Brain.Startup %s"), *Startup));
			}
			else
			{
				UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 시작 두뇌 eco.V3Brain.Startup '%s' 거부 (%s): %s — %s 로 시작한다"), *Startup,
					   EcoV3Brain::RejectName(L.Reason), *L.Message, *Reg.GetActive()->Id);
			}
		}
		if (bAutoAdapt && Startup.IsEmpty() && !Reg.GetActive()->bBuiltin)
		{
			// 적응 고리 Play 는 늘 내장 두뇌(판 0)에서 시작한다: 레벨은 Play 마다 저장된 처음 상태로 돌아오므로, 앞 Play 의 바뀐 환경에 맞춘 두뇌는 맞지 않는다
			// (저장소의 지금 두뇌는 프로세스에 하나라 PIE 를 다시 시작해도 남는다). 다른 두뇌로 시작하려면 eco.V3Brain.Startup
			Reg.Queue(FEcoV3BrainRegistry::Builtin(), TEXT("적응 고리 Play 시작 — 내장 두뇌(판 0)에서 시작"));
		}
		const float SwapAt = EcoV3Brain::SwapAtSeconds();
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] 사슴 두뇌: 지금 %s%s | 내장 %s | 예정 바꾸기 %s | 폴더 감시 %s | 바꾸기 eco.V3Brain.Load <파일|builtin> (결정 스텝 경계에서, Play 그대로), ")
				   TEXT("보기 eco.V3Brain.Info·List, 찾는 폴더 %s"),
			   *Reg.GetActive()->Describe(), Reg.GetPending().IsValid() ? *FString::Printf(TEXT(" → 첫 결정 스텝에 %s"), *Reg.GetPending()->Id) : TEXT(""),
			   *FEcoV3BrainRegistry::Builtin()->Id,
			   SwapAt >= 0.0f ? *FString::Printf(TEXT("%.1f초에 %s (eco.V3Brain.SwapAtSeconds·SwapFile — 측정·시연용)"), SwapAt, *EcoV3Brain::SwapFile())
							  : TEXT("끔"),
			   Reg.EffectiveWatchFolder().IsEmpty() ? TEXT("끔 (eco.V3Brain.WatchFolder)") : *Reg.EffectiveWatchFolder(),
			   *FString::Join(FEcoV3BrainRegistry::SearchFolders(), TEXT(" · ")));
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 적응 고리: %s | 화면 알림 %s · 화면 찍기 %s"),
			   bAutoAdapt ? *FString::Printf(TEXT("켬 (eco.IntegratedV3.AutoAdapt 1) — Play 번호 %s · 두뇌 감시 %s (Play 시작 때 있던 파일·다른 Play 의 두뇌는 읽지 않음) · 상태 파일 %s · ")
										      TEXT("되돌리기 eco.V3Brain.Rollback"),
										  *PlayId, *Reg.EffectiveWatchFolder(), *Reg.EffectiveStatusFile())
					   : TEXT("끔 (eco.IntegratedV3.AutoAdapt 0)"),
			   !EcoV3Brain::NoticeEnabled()		  ? TEXT("끔 (eco.V3Brain.Notice 0)")
			   : !(GEngine && FApp::CanEverRender()) ? TEXT("없음 (그리지 않는 실행 — 기록 '[EcoV3I] 알림 |' 만)")
													 : TEXT("켬 (eco.V3Brain.Notice 1)"),
			   EcoV3Brain::NoticeShot() ? TEXT("켬 (eco.V3Brain.NoticeShot 1 — Saved/EcoAdapt/shots)") : TEXT("끔"));
	}
}

void UEcoPolicyV3IntegratedSubsystem::Deinitialize()
{
	if (PreTickHandle.IsValid())
	{
		FWorldDelegates::OnWorldPreActorTick.Remove(PreTickHandle);
		PreTickHandle.Reset();
	}
	PreStartTick.UnRegisterTickFunction();
	EndEnvWatch();   // 환경 바뀜 감시 알림을 푼다 (10-21, EcoV3EnvWatch.cpp)
	bActive = false;
	RestoreViewEnvironment();
	Contexts.Reset();
	Plans.Reset();
	SpawnedCovers.Reset();
	SpawnedTrees.Reset();
	OurShelterIndices.Reset();
	TeamValues = FEcoV3SpawnerTeamValues();
	TeamHerbivoreConfig = nullptr;
	TeamWolfConfig = nullptr;
	ActiveBrain.Reset();   // 저장소(프로세스에 하나)의 지금 두뇌는 그대로 — 다음 Play 도 그 두뇌로 시작한다 (eco.V3Brain.Load builtin 으로 되돌린다)
	AppliedBrainGen = 0;
	if (bAdaptDefaultsSet)
	{
		// 적응 고리 기본 감시 폴더·상태 파일·감시 준비 기억은 이 Play 동안만 (되돌리기 쌓개·지금 두뇌는 저장소에 남는다)
		FEcoV3BrainRegistry::Get().SetDefaultWatchFolder(FString());
		FEcoV3BrainRegistry::Get().SetDefaultStatusFile(FString());
		FEcoV3BrainRegistry::Get().ClearWatchPrime();
		FEcoV3BrainRegistry::Get().SetWatchPlayId(FString());
		bAdaptDefaultsSet = false;
	}
	PendingShotAt = -1.0;
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

FVector UEcoPolicyV3IntegratedSubsystem::StageCenterCm(const FVector& DesiredCenterCm, const FVector& RegionCenterCm, double SizeUnits,
													   TFunctionRef<bool(const FVector&)> Contains, bool& bOutInside)
{
	const double Half = 0.5 * SizeUnits * EcoRepertoireV3::kUnitCm;
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
	bOutInside = StageInside(Center);
	return Center;
}

bool UEcoPolicyV3IntegratedSubsystem::PlanStage(FName RegionId, int32 GroupIndex, const FVector& DesiredCenterCm,
												const FVector& RegionCenterCm, const FEcoV3IntegratedSettings& S, int32 NumDeer,
												int32 NumWolves, bool bRequireGround, TFunctionRef<bool(const FVector&)> Contains,
												TFunctionRef<bool(const FVector&, FVector&)> Project, FEcoV3StagePlan& Out,
												const TArray<FVector>* LevelTrunksCm)
{
	Out = FEcoV3StagePlan();
	Out.RegionId = RegionId;
	Out.GroupIndex = GroupIndex;
	Out.WantDeer = NumDeer;
	Out.WantWolves = NumWolves;
	Out.SizeUnits = FMath::Clamp(S.StageSizeUnits, 60.0, 110.0);
	const double Half = 0.5 * Out.SizeUnits * EcoRepertoireV3::kUnitCm;

	// 무대가 지역 상자 안에 들게 한다 (네 모서리). 안 들면 지역 중심 쪽으로 옮긴다
	const FVector Center = StageCenterCm(DesiredCenterCm, RegionCenterCm, Out.SizeUnits, Contains, Out.bStageInside);
	Out.CenterCm = Center;

	EcoWorldV3::FRng Rng;
	Rng.State = EcoRepertoireV3::HashChain3(EcoPolicyV3IntegratedImpl::kPlanRngTag, static_cast<uint64>(S.Seed),
											static_cast<uint64>(GroupIndex + 1));
	// 줄기 원판(반지름 + 몸) 안 자리는 버린다 — 세계 원판 안 판정과 같은 식. 레벨 나무(10-18)가 이 무대에 있으면 그 원판(세계에 넣을 값과 같다),
	// 없고 실행 중 나무(eco.IntegratedV3.StageTrees, 10-17 — 예비)를 놓으면 표 원판. 둘 다 없으면 빈 목록 = 그대로
	if (S.bObstacles && LevelTrunksCm)
	{
		Out.TrunkDiscs = LevelTrunkDiscs(*LevelTrunksCm, RegionId, Out.OriginCm(), Out.SizeUnits);
		Out.bLevelTrunks = !Out.TrunkDiscs.empty();
	}
	if (!Out.bLevelTrunks && S.bStageTrees && S.bObstacles)
	{
		Out.TrunkDiscs = StageTreeDiscs(RegionId, Out.SizeUnits);
	}
	const std::vector<double>& Trunks = Out.TrunkDiscs;
	const double TrunkOx = Center.X - Half;
	const double TrunkOy = Center.Y - Half;
	const double TrunkBody = EcoWorldV3::FObstacleConfig().BodyR;
	auto InTrunk = [&Trunks, TrunkOx, TrunkOy, TrunkBody](const FVector& P)
	{
		return !Trunks.empty()
			   && EcoThreatV3::InsideAnyObstacle((P.X - TrunkOx) / EcoRepertoireV3::kUnitCm, (P.Y - TrunkOy) / EcoRepertoireV3::kUnitCm, Trunks.data(),
												 static_cast<std::int32_t>(Trunks.size() / 3), TrunkBody);
	};
	bool bAllGrounded = true;
	auto TryPoint = [&](const FVector& Hint, FVector& OutPoint) -> bool
	{
		if (InTrunk(Hint))
		{
			return false;   // 줄기 안 힌트: 다음 자리
		}
		FVector G;
		if (Project(Hint, G) && Contains(G) && Out.IsInsideStage(G, 100.0) && !InTrunk(G))
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
	const std::vector<EcoObservationV3::FCoverInput>& Covers, FName RegionId)
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
	// 늑대 몸 여유 (eco.IntegratedV3.WolfBodyMargin 1 m, 10-17 — realism_shelter.wolf_margin 0.5): 위협이 보는 원 반지름 + 이 값. ShelterSafe 0 이면 0
	// (그때는 팀 규칙이 PredatorRefugeMargin 으로 안전을 맡는다 — 두 여유가 한꺼번에 적용되지 않는다, RefugeOwnsSafety)
	C.ShelterWolfMargin = S.WolfBodyMarginUnits();
	// 은신처 먹이 부족 (eco.IntegratedV3.ShelterFood, 10-17 야생 2단계 1): 값 = configs/v3_wild2_mirror.yaml realism_cover_food (FShelterFoodConfig 기본값)
	C.ShelterFood.bEnabled = S.bShelterFood;
	// 늑대 무리 협동 사냥 (eco.IntegratedV3.PackHunt, 10-17 야생 2단계 2): 값 = configs/v3_wild2_pack_mirror.yaml wild_pack (FPackHuntConfig 기본값).
	// 늑대 몸 여유·은신처 원은 위 칸을 그대로 쓴다 (문 = 반지름 + ShelterWolfMargin)
	C.PackHunt.bEnabled = S.bPackHunt;
	// 세로 장애물 (eco.IntegratedV3.Obstacles, 10-17 야생 2단계 3): 켬 칸만 둔다 — 원판은 무대를 만들 때 레벨에서 읽어 넣는다 (원판이 없으면 세계는 그대로)
	C.Obstacles.bEnabled = S.bObstacles;
	// 장애물 돌아가기 (eco.IntegratedV3.ObstacleDetour, 10-17 끼임 고침): 값 = configs/v3_wild2_obstacle_mirror.yaml obstacles.detour_* (FDetourConfig 기본값)
	C.Obstacles.Detour.bEnabled = S.bObstacleDetour;
	// 숲 시야 (eco.IntegratedV3.Foliage, 10-22 — 개발 빌드, 기본 끔): 반지름·문턱 m → 단위. 나무 표는 무대를 만들 때 원판과 함께 넣는다 (ObstacleIsTree)
	C.Obstacles.Foliage.bEnabled = S.bFoliage;
	C.Obstacles.Foliage.R = S.FoliageRM * 100.0 / EcoRepertoireV3::kUnitCm;
	C.Obstacles.Foliage.Block = S.FoliageBlockM * 100.0 / EcoRepertoireV3::kUnitCm;
	// 지역 날씨 (eco.IntegratedV3.Weather, 10-18 야생 3단계): 그 지역의 팀 설계 날씨 (덮기 글자가 있으면 그것). 계수 = configs/v3_wild3_mirror.yaml (FWeatherConfig 기본값)
	C.Weather = S.WeatherFor(RegionId);
	// 감지 기록 (기록만 — 10초 여덟째 줄의 감지 띠·들어서만)
	C.bSenseStats = true;
	// 야생 (w3) 도망 기록 (10-21, 기록만 — 도주 반사를 켠 세계만 센다. 화면 eco.V3Debug 셋째 줄·두뇌 상태 줄, 10초 열째 줄 '<지역> 도망 |', 스냅숏 flight)
	C.bFlightStats = true;
	return C;
}

// -----------------------------------------------------------------------------
// 세로 장애물 읽기 (야생 2단계 3 — 레벨을 읽기만 한다)
// -----------------------------------------------------------------------------

double FEcoV3ObstacleScan::AreaFrac(double SizeUnits) const
{
	double A = 0.0;
	for (size_t k = 0; k + 2 < Discs.size(); k += 3)
	{
		A += UE_DOUBLE_PI * Discs[k + 2] * Discs[k + 2];
	}
	return SizeUnits > 0.0 ? A / (SizeUnits * SizeUnits) : 0.0;
}

namespace EcoPolicyV3IntegratedImpl
{
	/**
	 * 메시 하나의 충돌 상자 (단순 충돌이 있으면 그 상자, 없으면 — 복잡한 충돌을 단순으로 쓰는 메시 — 그리기 상자). 메시 공간 상자를 전체 변환(축마다 다른
	 * 크기 포함)으로 옮긴다 — FKAggregateGeom::CalcAABB(변환) 은 크기의 가장 작은 축 하나만 써서 납작한 바위·긴 줄기가 틀린다.
	 */
	FBox ObstacleCollisionBox(const UStaticMesh& Mesh, const FTransform& Xf)
	{
		if (const UBodySetup* Body = Mesh.GetBodySetup(); Body && Body->AggGeom.GetElementCount() > 0)
		{
			return Body->AggGeom.CalcAABB(FTransform::Identity).TransformBy(Xf);
		}
		return Mesh.GetBounds().GetBox().TransformBy(Xf);
	}

	/** 레벨 읽기가 원판으로 보는 컴포넌트 조건 = 팀 이동 제약(ConstrainStep: WorldStatic 채널로 쓸어 봄)이 막는 조건: 쿼리 충돌 켬 ∧ WorldStatic 막음. */
	bool BlocksTeamMovement(const UPrimitiveComponent& C)
	{
		return CollisionEnabledHasQuery(C.GetCollisionEnabled()) && C.GetCollisionResponseToChannel(ECC_WorldStatic) == ECR_Block;
	}
}

void UEcoPolicyV3IntegratedSubsystem::ScanStageObstacles(UWorld& World, const FVector& OriginCm, double SizeUnits,
														 const std::vector<EcoObservationV3::FCoverInput>& Covers,
														 const TSet<const AActor*>& Exclude, bool bProbeGround, FEcoV3ObstacleScan& Out, FName LayoutRegion)
{
	using EcoRepertoireV3::kUnitCm;
	Out = FEcoV3ObstacleScan();
	const double SizeCm = SizeUnits * kUnitCm;
	struct FDisc
	{
		double X, Y, R;
		uint8 bTree;   // 레벨 나무 줄기 막이 (10-18)
	};
	TArray<FDisc> Kept;
	const FName TrunkTag = LevelTrunkTag();
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		const AActor* A = *It;
		if (!A || Exclude.Contains(A) || A->IsA<APawn>() || A->IsA<AVolume>() || A->IsA<AEcoCreatureRepresentationActor>())
		{
			continue;
		}
		const bool bRefuge = A->IsA<AEcoShelterAnchor>();
		const bool bTrunk = A->ActorHasTag(TrunkTag);
		TInlineComponentArray<UStaticMeshComponent*> Comps(A);
		for (const UStaticMeshComponent* C : Comps)
		{
			const UStaticMesh* Mesh = C ? C->GetStaticMesh() : nullptr;
			if (!Mesh || !C->IsRegistered())
			{
				continue;
			}
			// 팀 이동 제약(ConstrainStep: WorldStatic 채널로 쓸어 봄)이 막는 것과 같은 조건
			const bool bCollide = EcoPolicyV3IntegratedImpl::BlocksTeamMovement(*C);
			const UInstancedStaticMeshComponent* Ism = Cast<UInstancedStaticMeshComponent>(C);
			const int32 Count = Ism ? Ism->GetInstanceCount() : 1;
			for (int32 i = 0; i < Count; ++i)
			{
				FTransform Xf = C->GetComponentTransform();
				if (Ism && !Ism->GetInstanceTransform(i, Xf, true))
				{
					continue;
				}
				const FBox Box = EcoPolicyV3IntegratedImpl::ObstacleCollisionBox(*Mesh, Xf);
				if (!Box.IsValid)
				{
					continue;
				}
				const FVector Ctr = Box.GetCenter();
				const double X = Ctr.X - OriginCm.X;
				const double Y = Ctr.Y - OriginCm.Y;
				if (X < 0.0 || Y < 0.0 || X > SizeCm || Y > SizeCm)
				{
					continue;   // 중심이 무대 밖
				}
				++Out.SeenMeshes;
				if (bRefuge)
				{
					++Out.RefugeDecor;
					continue;
				}
				if (!bCollide)
				{
					++Out.NoCollision;
					++Out.NoCollisionByMesh.FindOrAdd(Mesh->GetName());
					continue;
				}
				const FVector Ext = Box.GetExtent();
				const double Rcm = 0.5 * (Ext.X + Ext.Y);   // 가로 반지름 = 충돌 상자 가로 반폭의 평균 (둥근 줄기·바위에 맞춘 어림)
				if (Rcm < FEcoV3ObstacleScan::kMinRadiusCm)
				{
					++Out.Tiny;
					continue;
				}
				if (2.0 * Ext.Z < FEcoV3ObstacleScan::kMinHeightCm)
				{
					++Out.Low;
					continue;
				}
				double Xu = X / kUnitCm;
				double Yu = Y / kUnitCm;
				bool bInCover = false;
				for (const EcoObservationV3::FCoverInput& Cv : Covers)
				{
					bInCover = bInCover || (Cv.Radius > 0.0 && FMath::Square(Xu - Cv.X) + FMath::Square(Yu - Cv.Y) <= Cv.Radius * Cv.Radius);
				}
				if (bInCover)
				{
					++Out.InCover;
					continue;
				}
				double Ru = Rcm / kUnitCm;
				if (bTrunk)
				{
					// 레벨 나무 (10-18): 배치 표 자리와 1 cm 안이면 표 값 그대로 (파이썬 거울 tree_layout.json 과 비트 단위로 같게)
					++Out.LevelTrees;
					double Dev = 0.0;
					if (!LayoutRegion.IsNone() && SnapToLayout(LayoutRegion, SizeUnits, Xu, Yu, Ru, &Dev))
					{
						++Out.LevelTreesSnapped;
						Out.LevelTreeMaxSnapCm = FMath::Max(Out.LevelTreeMaxSnapCm, Dev);
					}
					else if (!LayoutRegion.IsNone())
					{
						++Out.LevelTreesUnmatched;
					}
				}
				Kept.Add({Xu, Yu, Ru, static_cast<uint8>(bTrunk ? 1 : 0)});
				++Out.KeptByMesh.FindOrAdd(Mesh->GetName());
				const double Edge = Ru + 2.0 * EcoWorldV3::FObstacleConfig().BodyR;
				Out.NearEdge += (Xu < Edge || Yu < Edge || Xu > SizeUnits - Edge || Yu > SizeUnits - Edge) ? 1 : 0;
			}
		}
	}
	// 액터 순서와 무관하게 같은 목록 (x, 다음 y, 다음 r 순). 상한을 넘으면 큰 것부터 남긴다
	if (Kept.Num() > FEcoV3ObstacleScan::kMaxDiscs)
	{
		Kept.Sort([](const FDisc& A, const FDisc& B) { return A.R > B.R || (A.R == B.R && (A.X < B.X || (A.X == B.X && A.Y < B.Y))); });
		Out.Capped = Kept.Num() - FEcoV3ObstacleScan::kMaxDiscs;
		Kept.SetNum(FEcoV3ObstacleScan::kMaxDiscs);
	}
	Kept.Sort([](const FDisc& A, const FDisc& B) { return A.X < B.X || (A.X == B.X && (A.Y < B.Y || (A.Y == B.Y && A.R < B.R))); });
	Out.Discs.reserve(static_cast<size_t>(Kept.Num()) * 3);
	Out.IsLevelTree.Reset(Kept.Num());
	for (const FDisc& D : Kept)
	{
		Out.Discs.push_back(D.X);
		Out.Discs.push_back(D.Y);
		Out.Discs.push_back(D.R);
		Out.IsLevelTree.Add(D.bTree);
	}
	if (!bProbeGround)
	{
		return;
	}
	// 기록만: 2 m 격자 지면 검사 (팀 이동 제약의 지면 조건 — 경사 법선 Z < 0.65 와 물 볼륨). 원판에는 넣지 않는다
	const int32 G = FMath::Max(1, FMath::FloorToInt32(SizeCm / 200.0));
	for (int32 gy = 0; gy < G; ++gy)
	{
		for (int32 gx = 0; gx < G; ++gx)
		{
			const FVector Hint(OriginCm.X + (gx + 0.5) * 200.0, OriginCm.Y + (gy + 0.5) * 200.0, OriginCm.Z);
			FHitResult Hit;
			FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3ObstacleGround), false);
			++Out.GroundCells;
			if (!World.LineTraceSingleByChannel(Hit, Hint + FVector(0, 0, 5000), Hint - FVector(0, 0, 20000), ECC_WorldStatic, Params))
			{
				++Out.NoGroundCells;
				continue;
			}
			Out.SteepCells += Hit.ImpactNormal.Z < 0.65 ? 1 : 0;
			Out.WaterCells += EcoCreatureMovement::CrossesExcludedArea(World, Hit.ImpactPoint, Hit.ImpactPoint) ? 1 : 0;
		}
	}
}

bool UEcoPolicyV3IntegratedSubsystem::LoadObstacleImport(const FString& Path, TMap<FName, std::vector<double>>& Out)
{
	Out.Reset();
	FString Text;
	TSharedPtr<FJsonObject> Root;
	if (!FFileHelper::LoadFileToString(Text, *Path) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root.IsValid())
	{
		return false;
	}
	const TArray<TSharedPtr<FJsonValue>>* Regions = nullptr;
	if (!Root->TryGetArrayField(TEXT("regions"), Regions))
	{
		return false;
	}
	for (const TSharedPtr<FJsonValue>& Rv : *Regions)
	{
		const TSharedPtr<FJsonObject> R = Rv.IsValid() ? Rv->AsObject() : nullptr;
		const TArray<TSharedPtr<FJsonValue>>* Discs = nullptr;
		FString Name;
		if (!R.IsValid() || !R->TryGetStringField(TEXT("region"), Name) || !R->TryGetArrayField(TEXT("discs"), Discs))
		{
			continue;
		}
		std::vector<double>& D = Out.FindOrAdd(FName(*Name));
		for (const TSharedPtr<FJsonValue>& Dv : *Discs)
		{
			const TArray<TSharedPtr<FJsonValue>>* T = nullptr;
			if (Dv.IsValid() && Dv->TryGetArray(T) && T->Num() == 3 && (*T)[2]->AsNumber() > 0.0)
			{
				D.push_back((*T)[0]->AsNumber());
				D.push_back((*T)[1]->AsNumber());
				D.push_back((*T)[2]->AsNumber());
			}
		}
	}
	return true;
}

// -----------------------------------------------------------------------------
// 무대 나무 (10-17 — 레벨은 바꾸지 않고 실행 중 액터만 놓는다)
// -----------------------------------------------------------------------------

const EcoTreeLayoutV3::FStageTrees* UEcoPolicyV3IntegratedSubsystem::FindStageTrees(FName RegionId, double SizeUnits)
{
	if (SizeUnits != EcoTreeLayoutV3::kStageSizeUnits)
	{
		return nullptr;   // 표는 한 변 120 m 무대에 맞춘 자리다 (다른 크기에 늘이면 은신처·벽 규칙이 깨진다)
	}
	for (const EcoTreeLayoutV3::FStageTrees& St : EcoTreeLayoutV3::kStages)
	{
		if (RegionId == FName(UTF8_TO_TCHAR(St.Region)))
		{
			return &St;
		}
	}
	return nullptr;
}

std::vector<double> UEcoPolicyV3IntegratedSubsystem::StageTreeDiscs(FName RegionId, double SizeUnits)
{
	std::vector<double> Out;
	if (const EcoTreeLayoutV3::FStageTrees* St = FindStageTrees(RegionId, SizeUnits))
	{
		Out.reserve(static_cast<size_t>(St->Num) * 3);
		for (int32 k = 0; k < St->Num; ++k)
		{
			Out.push_back(St->Trees[k].X);
			Out.push_back(St->Trees[k].Y);
			Out.push_back(St->Trees[k].R);
		}
	}
	return Out;
}

void UEcoPolicyV3IntegratedSubsystem::SpawnStageTrees(UWorld& World, FName RegionId, const FVector& OriginCm, double SizeUnits,
													  const std::vector<EcoObservationV3::FCoverInput>& Avoid, FEcoV3StageTrees& Out)
{
	using EcoRepertoireV3::kUnitCm;
	Out = FEcoV3StageTrees();
	const EcoTreeLayoutV3::FStageTrees* St = FindStageTrees(RegionId, SizeUnits);
	if (!St || St->Num <= 0)
	{
		return;
	}
	Out.Layout = St->Num;
	UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, UTF8_TO_TCHAR(EcoTreeLayoutV3::kMeshPath));
	if (!Mesh)
	{
		Out.SkippedNoMesh = St->Num;
		return;
	}
	const double Clear = EcoTreeLayoutV3::kCoverClearM * 100.0 / kUnitCm;
	for (int32 k = 0; k < St->Num; ++k)
	{
		const EcoTreeLayoutV3::FTree& T = St->Trees[k];
		// 은신처 곁 (표는 우리 은신처가 무대 1/4·3/4 지점이라고 보고 비워 두었다 — 다른 자리에 놓였거나 레벨 은신처면 여기서 뺀다)
		bool bNearCover = false;
		for (const EcoObservationV3::FCoverInput& A : Avoid)
		{
			bNearCover = bNearCover || (A.Radius > 0.0 && FMath::Sqrt(FMath::Square(T.X - A.X) + FMath::Square(T.Y - A.Y)) < A.Radius + Clear + T.R);
		}
		if (bNearCover)
		{
			++Out.SkippedCover;
			continue;
		}
		// 지면: 줄기 중심 + 둘레 6 곳(줄기 반지름, 60° 간격)의 가장 낮은 땅 (기울어진 땅에서도 밑동이 뜨지 않게). 팀 ProjectSpawnPoint 와 같은 선 길이
		double MinZ = 0.0;
		double MaxZ = 0.0;
		if (!GroundStageTree(World, OriginCm, T, MinZ, MaxZ))
		{
			++Out.SkippedNoGround;
			continue;
		}
		const FTransform Xf = LevelTreeTransform(T, OriginCm, MinZ);
		FActorSpawnParameters Params;
		if (World.PersistentLevel)
		{
			Params.Name = MakeUniqueObjectName(World.PersistentLevel, AStaticMeshActor::StaticClass(),
											   *FString::Printf(TEXT("EcoV3_Tree_%s_%02d"), *RegionId.ToString(), k));
		}
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Params.ObjectFlags |= RF_Transient;
		AStaticMeshActor* Actor = World.SpawnActor<AStaticMeshActor>(AStaticMeshActor::StaticClass(), Xf, Params);
		UStaticMeshComponent* Smc = Actor ? Actor->GetStaticMeshComponent() : nullptr;
		if (!Smc)
		{
			++Out.SkippedNoMesh;
			continue;
		}
		// 정적(Static) 컴포넌트는 등록된 뒤 메시를 바꿀 수 없다(SetStaticMesh 경고) — 움직임 가능으로 두고 넣는다. 이 액터는 움직이지 않는다
		Smc->SetMobility(EComponentMobility::Movable);
		Smc->SetCollisionProfileName(UCollisionProfile::NoCollision_ProfileName);
		Smc->SetCollisionEnabled(ECollisionEnabled::NoCollision);
		Smc->SetGenerateOverlapEvents(false);
		Smc->SetCanEverAffectNavigation(false);
		Smc->SetCastShadow(true);
		Smc->SetStaticMesh(Mesh);
		Actor->SetActorEnableCollision(false);
		Actor->Tags.Add(FName(TEXT("EcoV3StageTree")));
		Out.Discs.push_back(T.X);
		Out.Discs.push_back(T.Y);
		Out.Discs.push_back(T.R);
		Out.Actors.Add(Actor);
		Out.GroundZ.Add(MinZ);
		Out.MaxReliefCm = FMath::Max(Out.MaxReliefCm, MaxZ - MinZ);
	}
}

bool UEcoPolicyV3IntegratedSubsystem::GroundStageTree(UWorld& World, const FVector& OriginCm, const EcoTreeLayoutV3::FTree& T, double& OutMinZ,
													  double& OutMaxZ, const TArray<AActor*>* Ignore)
{
	using EcoRepertoireV3::kUnitCm;
	const FVector C(OriginCm.X + T.X * kUnitCm, OriginCm.Y + T.Y * kUnitCm, OriginCm.Z);
	bool bCenter = false;
	bool bAny = false;
	OutMinZ = 0.0;
	OutMaxZ = 0.0;
	for (int32 s = 0; s < 7; ++s)
	{
		FVector P = C;
		if (s > 0)
		{
			const double A = static_cast<double>(s - 1) * UE_DOUBLE_PI / 3.0;
			P.X += T.R * kUnitCm * FMath::Cos(A);
			P.Y += T.R * kUnitCm * FMath::Sin(A);
		}
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3TreeGround), false);
		if (Ignore)
		{
			Params.AddIgnoredActors(*Ignore);
		}
		if (World.LineTraceSingleByChannel(Hit, P + FVector(0, 0, 5000), P - FVector(0, 0, 20000), ECC_WorldStatic, Params))
		{
			OutMinZ = bAny ? FMath::Min(OutMinZ, Hit.ImpactPoint.Z) : Hit.ImpactPoint.Z;
			OutMaxZ = bAny ? FMath::Max(OutMaxZ, Hit.ImpactPoint.Z) : Hit.ImpactPoint.Z;
			bAny = true;
			bCenter = bCenter || s == 0;
		}
	}
	return bCenter;
}

// -----------------------------------------------------------------------------
// 레벨 나무 (10-18 — 통합 레벨에 놓은 나무 액터·줄기 막이, EcoV3PlaceTreesCommandlet)
// -----------------------------------------------------------------------------

FName UEcoPolicyV3IntegratedSubsystem::LevelTreeTag()
{
	static const FName Name(TEXT("EcoV3Tree"));
	return Name;
}

FName UEcoPolicyV3IntegratedSubsystem::LevelTrunkTag()
{
	static const FName Name(TEXT("EcoV3Trunk"));
	return Name;
}

const TCHAR* UEcoPolicyV3IntegratedSubsystem::LevelTreeFolder()
{
	return TEXT("EcoV3_Trees");
}

const TCHAR* UEcoPolicyV3IntegratedSubsystem::LevelTrunkMeshPath()
{
	return TEXT("/Engine/BasicShapes/Cylinder.Cylinder");
}

FTransform UEcoPolicyV3IntegratedSubsystem::LevelTreeTransform(const EcoTreeLayoutV3::FTree& T, const FVector& OriginCm, double GroundMinZ)
{
	using EcoRepertoireV3::kUnitCm;
	const FVector Pivot(OriginCm.X + T.PivotX * kUnitCm, OriginCm.Y + T.PivotY * kUnitCm, GroundMinZ - EcoTreeLayoutV3::kSinkCm);
	return FTransform(FRotator(0.0, T.YawDeg, 0.0), Pivot, FVector(T.Scale));
}

bool UEcoPolicyV3IntegratedSubsystem::LevelTrunkTransform(const EcoTreeLayoutV3::FTree& T, const FVector& OriginCm, double GroundMinZ,
														  const UStaticMesh& Cylinder, FTransform& Out)
{
	using EcoRepertoireV3::kUnitCm;
	// 레벨 읽기와 같은 상자 (단순 충돌 상자, 없으면 그리기 상자) — 메시 공간
	const FBox Local = EcoPolicyV3IntegratedImpl::ObstacleCollisionBox(Cylinder, FTransform::Identity);
	const FVector Ext = Local.GetExtent();
	if (!Local.IsValid || !(Ext.X > 0.0) || !(Ext.Y > 0.0) || !(Ext.Z > 0.0))
	{
		return false;
	}
	// 가로: 크기 × 반폭 평균 = R (cm). 세로: 밑면 = 땅 − 30 cm, 윗면 = 땅 + 4 m
	const double Rcm = T.R * kUnitCm;
	const double Sxy = Rcm / (0.5 * (Ext.X + Ext.Y));
	const double Bottom = GroundMinZ - kLevelTrunkSinkCm;
	const double Top = GroundMinZ + kLevelTrunkTopCm;
	const double Sz = (Top - Bottom) / (2.0 * Ext.Z);
	const FVector Ctr = Local.GetCenter();
	const FVector Loc(OriginCm.X + T.X * kUnitCm - Sxy * Ctr.X, OriginCm.Y + T.Y * kUnitCm - Sxy * Ctr.Y, Bottom - Sz * Local.Min.Z);
	Out = FTransform(FRotator::ZeroRotator, Loc, FVector(Sxy, Sxy, Sz));
	return true;
}

void UEcoPolicyV3IntegratedSubsystem::GatherLevelTrunks(UWorld& World, TArray<FVector>& OutCm)
{
	OutCm.Reset();
	const FName TrunkTag = LevelTrunkTag();
	for (TActorIterator<AActor> It(&World); It; ++It)
	{
		const AActor* A = *It;
		if (!A || !A->ActorHasTag(TrunkTag))
		{
			continue;
		}
		TInlineComponentArray<UStaticMeshComponent*> Comps(A);
		for (const UStaticMeshComponent* C : Comps)
		{
			const UStaticMesh* Mesh = C ? C->GetStaticMesh() : nullptr;
			// 레벨 읽기(ScanStageObstacles)가 원판으로 넣는 조건과 같다: 등록됨·팀 이동 제약이 막음·반지름·높이
			if (!Mesh || !C->IsRegistered() || !EcoPolicyV3IntegratedImpl::BlocksTeamMovement(*C))
			{
				continue;
			}
			const FBox Box = EcoPolicyV3IntegratedImpl::ObstacleCollisionBox(*Mesh, C->GetComponentTransform());
			if (!Box.IsValid)
			{
				continue;
			}
			const FVector Ext = Box.GetExtent();
			const double Rcm = 0.5 * (Ext.X + Ext.Y);
			if (Rcm < FEcoV3ObstacleScan::kMinRadiusCm || 2.0 * Ext.Z < FEcoV3ObstacleScan::kMinHeightCm)
			{
				continue;
			}
			const FVector Ctr = Box.GetCenter();
			OutCm.Add(FVector(Ctr.X, Ctr.Y, Rcm));
		}
	}
}

std::vector<double> UEcoPolicyV3IntegratedSubsystem::LevelTrunkDiscs(const TArray<FVector>& TrunksCm, FName RegionId, const FVector& OriginCm,
																	  double SizeUnits, int32* OutSnapped)
{
	using EcoRepertoireV3::kUnitCm;
	const double SizeCm = SizeUnits * kUnitCm;
	struct FDisc
	{
		double X, Y, R;
	};
	TArray<FDisc> Kept;
	int32 Snapped = 0;
	for (const FVector& T : TrunksCm)
	{
		// 레벨 읽기와 같은 셈 (중심이 무대 밖이면 뺀다, 무대 단위로 나눈 뒤 표와 맞춘다)
		const double X = T.X - OriginCm.X;
		const double Y = T.Y - OriginCm.Y;
		if (X < 0.0 || Y < 0.0 || X > SizeCm || Y > SizeCm)
		{
			continue;
		}
		double Xu = X / kUnitCm;
		double Yu = Y / kUnitCm;
		double Ru = T.Z / kUnitCm;
		Snapped += SnapToLayout(RegionId, SizeUnits, Xu, Yu, Ru) ? 1 : 0;
		Kept.Add({Xu, Yu, Ru});
	}
	Kept.Sort([](const FDisc& A, const FDisc& B) { return A.X < B.X || (A.X == B.X && (A.Y < B.Y || (A.Y == B.Y && A.R < B.R))); });
	std::vector<double> Out;
	Out.reserve(static_cast<size_t>(Kept.Num()) * 3);
	for (const FDisc& D : Kept)
	{
		Out.push_back(D.X);
		Out.push_back(D.Y);
		Out.push_back(D.R);
	}
	if (OutSnapped)
	{
		*OutSnapped = Snapped;
	}
	return Out;
}

bool UEcoPolicyV3IntegratedSubsystem::SnapToLayout(FName RegionId, double SizeUnits, double& X, double& Y, double& R, double* OutDevCm)
{
	using EcoRepertoireV3::kUnitCm;
	const EcoTreeLayoutV3::FStageTrees* St = FindStageTrees(RegionId, SizeUnits);
	if (!St || St->Num <= 0)
	{
		return false;
	}
	int32 Best = INDEX_NONE;
	double BestDev = 0.0;
	for (int32 k = 0; k < St->Num; ++k)
	{
		const EcoTreeLayoutV3::FTree& T = St->Trees[k];
		const double Dev = kUnitCm * FMath::Max3(FMath::Abs(X - T.X), FMath::Abs(Y - T.Y), FMath::Abs(R - T.R));
		if (Dev <= kLevelTreeSnapCm && (Best == INDEX_NONE || Dev < BestDev))
		{
			Best = k;
			BestDev = Dev;
		}
	}
	if (Best == INDEX_NONE)
	{
		return false;
	}
	X = St->Trees[Best].X;
	Y = St->Trees[Best].Y;
	R = St->Trees[Best].R;
	if (OutDevCm)
	{
		*OutDevCm = BestDev;
	}
	return true;
}

void UEcoPolicyV3IntegratedSubsystem::ProbeLevelTrunks(UWorld& World, FName RegionId, const FVector& OriginCm, double SizeUnits, FEcoV3TrunkProbe& Out)
{
	Out = FEcoV3TrunkProbe();
	TArray<FVector> Trunks;
	GatherLevelTrunks(World, Trunks);
	const double SizeCm = SizeUnits * EcoRepertoireV3::kUnitCm;
	const FName TreeTag = LevelTreeTag();
	const FName TrunkTag = LevelTrunkTag();
	// ConstrainStep 이 쓰는 것과 같은 구 쓸기 (옛 높이 + 65 cm, 반경 30 cm, WorldStatic) 로 무엇에 닿았나 본다
	auto HitOurTree = [&World, &TreeTag, &TrunkTag](const FVector& From, const FVector& To)
	{
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3TrunkProbe), false);
		const FVector Lift(0, 0, 65);
		if (!World.SweepSingleByChannel(Hit, From + Lift, To + Lift, FQuat::Identity, ECC_WorldStatic, FCollisionShape::MakeSphere(30.f), Params))
		{
			return false;
		}
		const AActor* A = Hit.GetActor();
		return A && (A->ActorHasTag(TreeTag) || A->ActorHasTag(TrunkTag));
	};
	auto Ground = [&World](const FVector& P, FVector& OutP)
	{
		FHitResult Hit;
		FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3TrunkProbeGround), false);
		if (!World.LineTraceSingleByChannel(Hit, P + FVector(0, 0, 5000), P - FVector(0, 0, 20000), ECC_WorldStatic, Params))
		{
			return false;
		}
		OutP = Hit.ImpactPoint;
		return true;
	};
	for (const FVector& T : Trunks)
	{
		if (T.X - OriginCm.X < 0.0 || T.Y - OriginCm.Y < 0.0 || T.X - OriginCm.X > SizeCm || T.Y - OriginCm.Y > SizeCm)
		{
			continue;
		}
		++Out.Trees;
		// 가로지르기: 줄기 가장자리 + 몸 + 10 cm 밖 서쪽 → 동쪽 (줄기 중심을 지나는 한 걸음). 높이는 그 자리의 땅
		const double Rcm = T.Z;
		const double Off = Rcm + 30.0 + 10.0;
		FVector From, Far;
		if (Ground(FVector(T.X - Off, T.Y, OriginCm.Z), From) && Ground(FVector(T.X + Off, T.Y, OriginCm.Z), Far))
		{
			FVector To = Far;
			const bool bBlocked = !EcoCreatureMovement::ConstrainStep(World, RegionId, false, From, To);
			Out.CrossBlocked += bBlocked ? 1 : 0;
			Out.CrossByTrunk += bBlocked && HitOurTree(From, Far) ? 1 : 0;
		}
		// 잎 아래 둘레: 줄기 가장자리 + 몸 30 cm + 1 m 의 원을 따라 30° 마다 30 cm 걸음 (잎은 반경 6~15 m 라 모두 잎 아래다)
		const double Ring = Rcm + 30.0 + FEcoV3TrunkProbe::kRingGapCm;
		for (int32 k = 0; k < FEcoV3TrunkProbe::kRingSteps; ++k)
		{
			const double A = static_cast<double>(k) * UE_DOUBLE_TWO_PI / FEcoV3TrunkProbe::kRingSteps;
			const double Step = 30.0 / Ring;   // 둘레를 따라 30 cm
			FVector P0, P1;
			if (!Ground(FVector(T.X + Ring * FMath::Cos(A), T.Y + Ring * FMath::Sin(A), OriginCm.Z), P0)
				|| !Ground(FVector(T.X + Ring * FMath::Cos(A + Step), T.Y + Ring * FMath::Sin(A + Step), OriginCm.Z), P1))
			{
				continue;
			}
			++Out.RingSteps;
			FVector To = P1;
			const bool bBlocked = !EcoCreatureMovement::ConstrainStep(World, RegionId, false, P0, To);
			Out.RingBlocked += bBlocked ? 1 : 0;
			Out.RingBlockedByTree += HitOurTree(P0, P1) ? 1 : 0;
		}
	}
}

std::vector<double> UEcoPolicyV3IntegratedSubsystem::MergeDiscs(const std::vector<double>& Level, const std::vector<double>& Trees, TArray<uint8>* OutIsTree,
															   const TArray<uint8>* LevelIsTree)
{
	struct FDisc
	{
		double X, Y, R;
		uint8 bTree;
	};
	TArray<FDisc> All;
	for (size_t k = 0; k + 2 < Level.size(); k += 3)
	{
		const int32 i = static_cast<int32>(k / 3);
		All.Add({Level[k], Level[k + 1], Level[k + 2], static_cast<uint8>(LevelIsTree && LevelIsTree->IsValidIndex(i) && (*LevelIsTree)[i] != 0 ? 1 : 0)});
	}
	for (size_t k = 0; k + 2 < Trees.size(); k += 3)
	{
		All.Add({Trees[k], Trees[k + 1], Trees[k + 2], 1});
	}
	// ScanStageObstacles 와 같은 순서 (x, 다음 y, 다음 r). 완전히 같은 원판은 레벨 것이 앞 (StableSort)
	All.StableSort([](const FDisc& A, const FDisc& B) { return A.X < B.X || (A.X == B.X && (A.Y < B.Y || (A.Y == B.Y && A.R < B.R))); });
	std::vector<double> Out;
	Out.reserve(static_cast<size_t>(All.Num()) * 3);
	if (OutIsTree)
	{
		OutIsTree->Reset(All.Num());
	}
	for (const FDisc& D : All)
	{
		Out.push_back(D.X);
		Out.push_back(D.Y);
		Out.push_back(D.R);
		if (OutIsTree)
		{
			OutIsTree->Add(D.bTree);
		}
	}
	return Out;
}

bool UEcoPolicyV3IntegratedSubsystem::ExportObstacles(const FString& Path) const
{
	if (Path.IsEmpty())
	{
		return false;
	}
	TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
	Root->SetNumberField(TEXT("session_seed"), static_cast<double>(Settings.Seed));
	Root->SetStringField(TEXT("units"), TEXT("stage units, 1 unit = 200 cm, x·y from stage origin"));
	Root->SetBoolField(TEXT("obstacles_on"), Settings.bObstacles);
	Root->SetBoolField(TEXT("stage_trees_on"), Settings.bStageTrees);
	Root->SetStringField(TEXT("tree_layout"), FString::Printf(TEXT("%s %s"), UTF8_TO_TCHAR(EcoTreeLayoutV3::kVersion), UTF8_TO_TCHAR(EcoTreeLayoutV3::kDigest)));
	TArray<TSharedPtr<FJsonValue>> Regions;
	for (const TUniquePtr<FEcoV3RegionContext>& Ctx : Contexts)
	{
		const FEcoV3ObstacleScan& S = Ctx->ObstacleScan;
		TSharedRef<FJsonObject> R = MakeShared<FJsonObject>();
		R->SetStringField(TEXT("region"), Ctx->RegionId.ToString());
		R->SetNumberField(TEXT("region_index"), Ctx->RegionRuntimeIndex);
		R->SetNumberField(TEXT("size"), Ctx->SizeUnits);
		auto Triple = [](double A, double B, double C)
		{
			TArray<TSharedPtr<FJsonValue>> V;
			V.Add(MakeShared<FJsonValueNumber>(A));
			V.Add(MakeShared<FJsonValueNumber>(B));
			V.Add(MakeShared<FJsonValueNumber>(C));
			return V;
		};
		R->SetArrayField(TEXT("origin_cm"), Triple(Ctx->OriginCm.X, Ctx->OriginCm.Y, Ctx->OriginCm.Z));
		// discs = 세계가 쓰는 원판 (레벨에서 읽었거나 가져온 원판). 장애물을 끈 세계는 레벨에서 읽은 원판을 적는다
		const std::vector<double>& Used = Ctx->Sim.Config.Obstacles.bEnabled ? Ctx->Sim.Config.Obstacles.Discs : S.Discs;
		TArray<TSharedPtr<FJsonValue>> Discs;
		for (size_t k = 0; k + 2 < Used.size(); k += 3)
		{
			Discs.Add(MakeShared<FJsonValueArray>(Triple(Used[k], Used[k + 1], Used[k + 2])));
		}
		R->SetArrayField(TEXT("discs"), Discs);
		R->SetBoolField(TEXT("imported"), Ctx->bObstaclesImported);
		R->SetNumberField(TEXT("level_discs"), S.Num());
		{
			// 무대 나무 (10-17): 놓은 줄기 원판 (discs 안에도 들어 있다), 표의 그루 수, 뺀 수
			const FEcoV3StageTrees& T = Ctx->Trees;
			TArray<TSharedPtr<FJsonValue>> TreeDiscs;
			for (size_t k = 0; k + 2 < T.Discs.size(); k += 3)
			{
				TreeDiscs.Add(MakeShared<FJsonValueArray>(Triple(T.Discs[k], T.Discs[k + 1], T.Discs[k + 2])));
			}
			R->SetArrayField(TEXT("tree_discs"), TreeDiscs);
			R->SetNumberField(TEXT("tree_layout_count"), T.Layout);
			R->SetNumberField(TEXT("tree_skipped_cover"), T.SkippedCover);
			R->SetNumberField(TEXT("tree_skipped_no_ground"), T.SkippedNoGround);
			R->SetNumberField(TEXT("tree_skipped_no_mesh"), T.SkippedNoMesh);
			R->SetNumberField(TEXT("tree_max_relief_cm"), T.MaxReliefCm);
		}
		{
			// 레벨 나무 (10-18): 레벨 읽기가 줄기 막이(꼬리표 EcoV3Trunk)에서 읽은 원판 (discs 안에도 들어 있다), 표와 맞춘 수, 시작 자리 원판, 이동 검사
			TArray<TSharedPtr<FJsonValue>> LevelTreeDiscs;
			for (int32 k = 0; k < S.Num(); ++k)
			{
				if (S.IsLevelTree.IsValidIndex(k) && S.IsLevelTree[k] != 0)
				{
					LevelTreeDiscs.Add(MakeShared<FJsonValueArray>(Triple(S.Discs[3 * k], S.Discs[3 * k + 1], S.Discs[3 * k + 2])));
				}
			}
			TArray<TSharedPtr<FJsonValue>> PlanDiscs;
			for (size_t k = 0; k + 2 < Ctx->PlanTrunkDiscs.size(); k += 3)
			{
				PlanDiscs.Add(MakeShared<FJsonValueArray>(Triple(Ctx->PlanTrunkDiscs[k], Ctx->PlanTrunkDiscs[k + 1], Ctx->PlanTrunkDiscs[k + 2])));
			}
			R->SetBoolField(TEXT("level_trees_on"), Ctx->bLevelTrees);
			R->SetArrayField(TEXT("level_tree_discs"), LevelTreeDiscs);
			R->SetNumberField(TEXT("level_trees_snapped"), S.LevelTreesSnapped);
			R->SetNumberField(TEXT("level_trees_unmatched"), S.LevelTreesUnmatched);
			R->SetNumberField(TEXT("level_tree_max_snap_cm"), S.LevelTreeMaxSnapCm);
			R->SetArrayField(TEXT("plan_trunk_discs"), PlanDiscs);
			const FEcoV3TrunkProbe& Pr = Ctx->TrunkProbe;
			TSharedRef<FJsonObject> Pj = MakeShared<FJsonObject>();
			Pj->SetNumberField(TEXT("trees"), Pr.Trees);
			Pj->SetNumberField(TEXT("cross_blocked"), Pr.CrossBlocked);
			Pj->SetNumberField(TEXT("cross_by_trunk"), Pr.CrossByTrunk);
			Pj->SetNumberField(TEXT("ring_steps"), Pr.RingSteps);
			Pj->SetNumberField(TEXT("ring_blocked"), Pr.RingBlocked);
			Pj->SetNumberField(TEXT("ring_blocked_by_tree"), Pr.RingBlockedByTree);
			R->SetObjectField(TEXT("trunk_probe"), Pj);
		}
		TArray<TSharedPtr<FJsonValue>> Covers;
		for (const EcoObservationV3::FCoverInput& Cv : Ctx->Sim.Config.Covers)
		{
			Covers.Add(MakeShared<FJsonValueArray>(Triple(Cv.X, Cv.Y, Cv.Radius)));
		}
		R->SetArrayField(TEXT("covers"), Covers);
		{
			// 지역 날씨 (10-18 야생 3단계): 이 무대 세계의 날씨 (파이썬 거울 wild_weather.regions 와 같아야 한다 — results/v3/wild3/compare_weather.py 가 본다)
			const EcoWorldV3::FWeatherConfig& Wx = Ctx->Sim.Config.Weather;
			static const TCHAR* const Names[EcoWorldV3::kNumWeatherKinds] = {TEXT("clear"), TEXT("rain"), TEXT("snow")};
			TSharedRef<FJsonObject> Wj = MakeShared<FJsonObject>();
			Wj->SetBoolField(TEXT("on"), Wx.bEnabled);
			Wj->SetStringField(TEXT("kind"), Names[FMath::Clamp(Wx.Kind, 0, EcoWorldV3::kNumWeatherKinds - 1)]);
			Wj->SetNumberField(TEXT("intensity"), Wx.Intensity);
			Wj->SetNumberField(TEXT("rain_sight"), Wx.RainSight);
			Wj->SetNumberField(TEXT("rain_hear"), Wx.RainHear);
			Wj->SetNumberField(TEXT("snow_sight"), Wx.SnowSight);
			Wj->SetNumberField(TEXT("snow_hear"), Wx.SnowHear);
			Wj->SetNumberField(TEXT("snow_deer_speed"), Wx.SnowDeerSpeed);
			Wj->SetNumberField(TEXT("snow_wolf_speed"), Wx.SnowWolfSpeed);
			Wj->SetBoolField(TEXT("obs_visibility"), Wx.bObsVisibility);
			Wj->SetNumberField(TEXT("schedule_rows"), static_cast<double>(Wx.Schedule.size()));
			R->SetObjectField(TEXT("weather"), Wj);
		}
		TSharedRef<FJsonObject> Counts = MakeShared<FJsonObject>();
		Counts->SetNumberField(TEXT("seen_meshes"), S.SeenMeshes);
		Counts->SetNumberField(TEXT("no_collision"), S.NoCollision);
		Counts->SetNumberField(TEXT("tiny"), S.Tiny);
		Counts->SetNumberField(TEXT("low"), S.Low);
		Counts->SetNumberField(TEXT("in_cover"), S.InCover);
		Counts->SetNumberField(TEXT("refuge_decor"), S.RefugeDecor);
		Counts->SetNumberField(TEXT("capped"), S.Capped);
		Counts->SetNumberField(TEXT("near_edge"), S.NearEdge);
		Counts->SetNumberField(TEXT("ground_cells"), S.GroundCells);
		Counts->SetNumberField(TEXT("steep_cells"), S.SteepCells);
		Counts->SetNumberField(TEXT("water_cells"), S.WaterCells);
		Counts->SetNumberField(TEXT("no_ground_cells"), S.NoGroundCells);
		R->SetObjectField(TEXT("counts"), Counts);
		Regions.Add(MakeShared<FJsonValueObject>(R));
	}
	Root->SetArrayField(TEXT("regions"), Regions);
	FString Text;
	const TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Text);
	if (!FJsonSerializer::Serialize(Root, Writer))
	{
		return false;
	}
	return FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
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
        // Reconcile clipping and capacity changes with the authoritative ledger before the next native step.
        auto& F=W.Food;
        const double BeforeFood=F.Total();
        for(int Y=0;Y<F.Gw;++Y)for(int X=0;X<F.Gw;++X) {
            const int K=Y*F.Gw+X;
            const bool In=EcoRefugeV3::Contains(W.Config.Covers,{(X+.5)*F.Cell,(Y+.5)*F.Cell});
            F.CoverCell[K]=In?1:0;
            F.Regen[K]=W.Config.FoodRegenBase*W.Config.FoodRegenMult*(In?W.Config.FoodCoverRegenMult:1.);
        }
        // 10-17 야생 2단계 1 (eco.IntegratedV3.ShelterFood): 은신처 먹이 부족을 바뀐 원 목록으로 다시 건다 — 지워진 은신처의 셀은 처음 용량으로 돌아가고
        // (먹이는 그대로, 재생으로 다시 찬다) 늦게 더한 은신처의 셀은 용량·재생이 15% 로 준다 (FFoodGrid::ApplyShelterFood)
        if(W.Config.ShelterFood.bEnabled)F.ApplyShelterFood(W.Config);
        if(Context.bSpatialFoodRegistered) {
            double Capacity=0;
            for(const double CellCapacity:F.Cap)Capacity+=CellCapacity;
            const double AfterFood=F.Total();
            auto* Ecology=GetWorld()->GetSubsystem<UEcologySimulationSubsystem>();
            if(!Ecology||!Ecology->AdjustSpatialFoodHabitat(Context.RegionId,++Context.ResourceReceiptSequence,
                BeforeFood,BeforeFood-AfterFood,Capacity,AfterFood)) {
                UE_LOG(LogEcoPolicyV3I,Error,TEXT("[EcoV3I] Refuge habitat resource adjustment rejected: %s"),*Context.RegionId.ToString());
                RejectResourceContract();
            }
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
	// 레벨 나무 줄기 막이 (10-18, 늘 불린 액터 — 스트리밍 전에도 있다). 시작 자리가 피한다
	TArray<FVector> LevelTrunks;
	GatherLevelTrunks(*World, LevelTrunks);
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
			PlanStage(G.RegionId, g, Desired, Region->GetActorLocation(), Settings, Deer, Wolves, false, Contains, Project, Plan, &LevelTrunks);
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
			PlanStage(G.RegionId, g, Desired, Region->GetActorLocation(), Settings, Deer, Wolves, true, Contains, Project, Plan, &LevelTrunks);
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
	TArray<FVector> LevelTrunks;   // 레벨 나무 줄기 막이 (10-18)
	GatherLevelTrunks(*World, LevelTrunks);
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
				  Project, Grounded, &LevelTrunks);
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
		TickEnvWatch();   // 환경 바뀜 감시·시험용 예약 (10-21, EcoV3EnvWatch.cpp — 읽기만, 세계는 결정 스텝 경계에서 바꾼다)
		TallyTeamWolfVisuals();
		if (IsDebugDrawEnabled())
		{
			DrawOverlay();
		}
	}
	if (bActive)
	{
		DrawBrainNotices();   // 실시간 두뇌 교체 상태 줄·화면 찍기 (eco.V3Debug 와 따로)
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
	// 장애물 원판 가져오기 (eco.IntegratedV3.ObstacleImport — 측정 전용). 지역 이름 → 원판 (x, y, r) × K
	TMap<FName, std::vector<double>> ImportedDiscs;
	if (Settings.bObstacles && !Settings.ObstacleImportPath.IsEmpty())
	{
		const FString Path = FPaths::ConvertRelativePathToFull(Settings.ObstacleImportPath);
		if (LoadObstacleImport(Path, ImportedDiscs))
		{
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 장애물 원판을 가져왔다 (측정 전용, 레벨에 보이는 물체 없음): %s — 지역 %d"), *Path, ImportedDiscs.Num());
		}
		else
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 장애물 원판 JSON 을 읽지 못했다: %s — 레벨에서 읽은 원판을 쓴다"), *Path);
		}
	}

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
		// 무대 나무 (eco.IntegratedV3.StageTrees, 10-17): 배치 표대로 충돌 없는 팀 나무를 놓는다 (원판은 아래에서 레벨 읽기 원판과 합친다).
		// 피할 원 = v3 은신처 원 + 우리가 놓은 앵커 자리(등록이 늦을 수 있다) + 무대에 걸친 모든 등록 은신처(학습 범위 밖이라 v3 원에서 뺀 레벨 은신처 포함).
		// 그 지역 원판을 가져왔으면(측정 전용 ObstacleImport) 놓지 않는다 — 가져온 원판이 세계 원판 전부다
		const std::vector<double>* Imported = Settings.bObstacles ? ImportedDiscs.Find(G.RegionId) : nullptr;
		// 레벨 나무 (10-18): 이 무대 안에 줄기 막이가 있으면 실행 중 나무는 놓지 않는다 (두 번 놓지 않게 — 시작 자리 계획과 같은 판정)
		TArray<FVector> LevelTrunks;
		GatherLevelTrunks(*World, LevelTrunks);
		const bool bLevelTrees = Settings.bObstacles && !LevelTrunkDiscs(LevelTrunks, G.RegionId, Origin, Plan.SizeUnits).empty();
		FEcoV3StageTrees Trees;
		if (Settings.bStageTrees && Settings.bObstacles && !Imported && !bLevelTrees)
		{
			std::vector<EcoObservationV3::FCoverInput> Avoid = Covers;
			for (const FVector& P : Placed)
			{
				Avoid.push_back({(P.X - Origin.X) / EcoRepertoireV3::kUnitCm, (P.Y - Origin.Y) / EcoRepertoireV3::kUnitCm, R / EcoRepertoireV3::kUnitCm});
			}
			if (Shelters)
			{
				for (const FEcoShelterPoint& P : Shelters->GetShelters())
				{
					if (Shelters->IsValidShelterIndex(P.RuntimeIndex) && Plan.IsInsideStage(P.Position, -static_cast<double>(P.Radius)))
					{
						Avoid.push_back({(P.Position.X - Origin.X) / EcoRepertoireV3::kUnitCm, (P.Position.Y - Origin.Y) / EcoRepertoireV3::kUnitCm,
										 static_cast<double>(P.Radius) / EcoRepertoireV3::kUnitCm});
					}
				}
			}
			SpawnStageTrees(*World, G.RegionId, Origin, Plan.SizeUnits, Avoid, Trees);
			SpawnedTrees.Append(Trees.Actors);
		}
		// 세로 장애물 (야생 2단계 3): 레벨을 읽기만 해서 무대 안의 충돌하는 나무·바위를 원판으로 만든다. 우리가 놓은 은신처 앵커와 무대 나무는 뺀다
		// (무대 나무는 충돌이 없어 원판이 되지 않지만 '충돌 없음' 셈에 섞이지 않게 — 그 원판은 표에서 바로 넣는다)
		FEcoV3ObstacleScan Scan;
		{
			TSet<const AActor*> Exclude;
			for (const TWeakObjectPtr<AActor>& Cover : SpawnedCovers)
			{
				if (const AActor* A = Cover.Get())
				{
					Exclude.Add(A);
				}
			}
			for (const TWeakObjectPtr<AActor>& Tree : SpawnedTrees)
			{
				if (const AActor* A = Tree.Get())
				{
					Exclude.Add(A);
				}
			}
			ScanStageObstacles(*World, Origin, Plan.SizeUnits, Covers, Exclude, true, Scan, G.RegionId);
		}
		EcoWorldV3::FWorldConfig Config = MakeRegionWorldConfig(Settings, RegionIndex, G.Herbivores, G.Wolves, Covers, G.RegionId);
		Config.Vegetation.bEnabled = AEcoVegetationField::IsRequested() || (Spawner.IsValid() && Spawner->bEnableVegetation);
        Config.bEcosystemLife = Spawner.IsValid() && Spawner->bEnableEcosystemLife;
		// 세로 장애물 (eco.IntegratedV3.Obstacles): 레벨에서 읽은 원판 + 무대 나무 줄기 원판 ((x, y, r) 순, 측정 때는 가져온 원판). 원판이 없으면 세계는 지금 그대로다
		TArray<uint8> IsTree;
		if (Config.Obstacles.bEnabled)
		{
			Config.Obstacles.Discs = Imported ? *Imported : MergeDiscs(Scan.Discs, Trees.Discs, &IsTree, &Scan.IsLevelTree);
		}
		// 숲 시야 나무 표 (10-22): 세계 원판마다 나무 줄기에서 왔나 — 바위 등 다른 충돌 메시에는 잎이 없다. 가져온 원판(측정 전용)은 표가 없어 모두 나무로 본다
		if (Config.Obstacles.bEnabled && !Imported && IsTree.Num() == Config.Obstacles.Num())
		{
			Config.Obstacles.Foliage.Trees.assign(IsTree.GetData(), IsTree.GetData() + IsTree.Num());
		}
		FEcoV3RegionContext* Ctx = AddContext(G.RegionId, RegionIndex, Origin, Config, G.Herbivores, G.Wolves);
		Ctx->ObstacleScan = MoveTemp(Scan);
		Ctx->bObstaclesImported = Settings.bObstacles && Imported != nullptr;
		Ctx->Trees = MoveTemp(Trees);
		Ctx->ObstacleIsTree = MoveTemp(IsTree);
		Ctx->bLevelTrees = bLevelTrees;
		Ctx->PlanTrunkDiscs = Plan.bLevelTrunks ? Plan.TrunkDiscs : std::vector<double>();
		if (bLevelTrees)
		{
			// 레벨 나무 이동 검사 (기록만): 팀 이동 제약이 줄기에서만 막고 잎 아래는 막지 않는가
			ProbeLevelTrunks(*World, G.RegionId, Origin, Plan.SizeUnits, Ctx->TrunkProbe);
		}
		{
			// 디버그 그리기 높이: 원판 중심 지면 (읽기만 하는 아래쪽 선 검사, 못 찾으면 무대 원점 높이)
			const std::vector<double>& Dl = Ctx->Sim.Config.Obstacles.Discs;
			for (size_t k = 0; k + 2 < Dl.size(); k += 3)
			{
				const FVector P = Ctx->UnitsToCm(Dl[k], Dl[k + 1], Origin.Z);
				FHitResult Hit;
				FCollisionQueryParams Params(SCENE_QUERY_STAT(EcoV3ObstacleDraw), false);
				Ctx->ObstacleGroundZ.Add(World->LineTraceSingleByChannel(Hit, P + FVector(0, 0, 5000), P - FVector(0, 0, 20000), ECC_WorldStatic, Params)
											 ? Hit.ImpactPoint.Z : Origin.Z);
			}
		}
		{
			const FEcoV3ObstacleScan& Sc = Ctx->ObstacleScan;
			auto Top = [](const TMap<FString, int32>& Map)
			{
				TArray<TPair<FString, int32>> Pairs = Map.Array();
				Pairs.Sort([](const TPair<FString, int32>& A, const TPair<FString, int32>& B) { return A.Value > B.Value || (A.Value == B.Value && A.Key < B.Key); });
				FString S;
				for (int32 k = 0; k < FMath::Min(4, Pairs.Num()); ++k)
				{
					S += FString::Printf(TEXT(" %s %d"), *Pairs[k].Key, Pairs[k].Value);
				}
				return S.IsEmpty() ? FString(TEXT(" 없음")) : S;
			};
			double RMean = 0.0, RMax = 0.0;
			for (int32 k = 0; k < Sc.Num(); ++k)
			{
				RMean += Sc.Discs[3 * k + 2];
				RMax = FMath::Max(RMax, Sc.Discs[3 * k + 2]);
			}
			RMean = Sc.Num() > 0 ? RMean / Sc.Num() : 0.0;
			const double MPerUnit = EcoRepertoireV3::kUnitCm / 100.0;
			if (Ctx->bObstaclesImported)
			{
				const EcoWorldV3::FObstacleConfig& Ob = Ctx->Sim.Config.Obstacles;
				double Area = 0.0;
				for (int32 k = 0; k < Ob.Num(); ++k)
				{
					Area += UE_DOUBLE_PI * Ob.Discs[3 * k + 2] * Ob.Discs[3 * k + 2];
				}
				UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 장애물 | 가져온 원판 %d (넓이 %.2f%%) 으로 돈다 — 측정 전용, 레벨에서 읽은 원판 %d 대신 (eco.IntegratedV3.ObstacleImport)"),
					   *G.RegionId.ToString(), Ob.Num(), 100.0 * Area / (Plan.SizeUnits * Plan.SizeUnits), Sc.Num());
			}
			UE_LOG(LogEcoPolicyV3I, Log,
				   TEXT("[EcoV3I] %s 장애물 | 원판 %d (반지름 평균 %.2f m·최대 %.2f m, 넓이 %.2f%%) %s | 무대 안 메시 %d: 충돌 없음 %d (많은 것:%s) · 작음(반지름 %.0f cm 밑) %d · ")
					   TEXT("낮음(%.0f cm 밑) %d · 은신처 원 안 %d · 은신처 장식 %d · 상한 넘침 %d · 무대 벽 곁 원판 %d | 원판 메시:%s | 지면 2 m 격자 %d 칸: 가파름 %d · 물 %d · 지면 없음 %d (기록만)"),
				   *G.RegionId.ToString(), Sc.Num(), RMean * MPerUnit, RMax * MPerUnit, 100.0 * Sc.AreaFrac(Plan.SizeUnits),
				   Settings.bObstacles ? TEXT("(eco.IntegratedV3.Obstacles 1 — 세계에 넣음)") : TEXT("(eco.IntegratedV3.Obstacles 0 — 읽기만, 세계에 넣지 않음)"),
				   Sc.SeenMeshes, Sc.NoCollision, *Top(Sc.NoCollisionByMesh), FEcoV3ObstacleScan::kMinRadiusCm, Sc.Tiny, FEcoV3ObstacleScan::kMinHeightCm,
				   Sc.Low, Sc.InCover, Sc.RefugeDecor, Sc.Capped, Sc.NearEdge, *Top(Sc.KeptByMesh), Sc.GroundCells, Sc.SteepCells, Sc.WaterCells, Sc.NoGroundCells);
		}
		{
			// 무대 나무 시작 줄 (10-17): 표 그루 수 → 놓은 수, 줄기 원판, 뺀 까닭. 표와 다르면 파이썬 거울(tree_layout.json)과 원판이 달라 경고
			const FEcoV3StageTrees& T = Ctx->Trees;
			bool bInTable = false;
			for (const EcoTreeLayoutV3::FStageTrees& St : EcoTreeLayoutV3::kStages)
			{
				bInTable = bInTable || (G.RegionId == FName(UTF8_TO_TCHAR(St.Region)) && St.Num > 0);
			}
			if (Ctx->bLevelTrees)
			{
				// 레벨 나무 (10-18): 레벨 읽기가 읽은 줄기 원판 · 표와 맞춘 수 · 시작 자리 계획과 같은가 · 이동 검사
				const FEcoV3ObstacleScan& Sc = Ctx->ObstacleScan;
				std::vector<double> WorldTrunks;
				double RLo = 0.0, RHi = 0.0;
				for (int32 k = 0; k < Sc.Num(); ++k)
				{
					if (Sc.IsLevelTree.IsValidIndex(k) && Sc.IsLevelTree[k] != 0)
					{
						const double Rm = Sc.Discs[3 * k + 2] * EcoRepertoireV3::kUnitCm / 100.0;
						RLo = WorldTrunks.empty() ? Rm : FMath::Min(RLo, Rm);
						RHi = WorldTrunks.empty() ? Rm : FMath::Max(RHi, Rm);
						WorldTrunks.insert(WorldTrunks.end(), {Sc.Discs[3 * k], Sc.Discs[3 * k + 1], Sc.Discs[3 * k + 2]});
					}
				}
				const EcoTreeLayoutV3::FStageTrees* St = FindStageTrees(G.RegionId, Plan.SizeUnits);
				const int32 TableNum = St ? St->Num : 0;
				const bool bPlanSame = Ctx->PlanTrunkDiscs == WorldTrunks;
				const bool bTableSame = WorldTrunks == StageTreeDiscs(G.RegionId, Plan.SizeUnits);
				const FEcoV3TrunkProbe& Pr = Ctx->TrunkProbe;
				UE_LOG(LogEcoPolicyV3I, Log,
					   TEXT("[EcoV3I] %s 나무 | 레벨 나무 줄기 %d (꼬리표 %s, 반지름 %.2f~%.2f m) — 배치 표 %s %d 그루와 맞춤 %d (읽은 값 ↔ 표 차이 최대 %.2g cm) · 표와 다름 %d | ")
						   TEXT("세계 원판 %s 표 · 시작 자리가 피한 원판 %d 은 세계 줄기 원판과 %s | 이동 검사(팀 ConstrainStep): 줄기 가로지르기 %d/%d 막힘 (줄기 막이에 닿음 %d) · ")
						   TEXT("잎 아래 둘레 걸음 %d 가운데 막힘 %d (우리 나무에 닿음 %d) | 실행 중 나무 놓지 않음"),
					   *G.RegionId.ToString(), Sc.LevelTrees, *LevelTrunkTag().ToString(), RLo, RHi, UTF8_TO_TCHAR(EcoTreeLayoutV3::kVersion), TableNum,
					   Sc.LevelTreesSnapped, Sc.LevelTreeMaxSnapCm, Sc.LevelTreesUnmatched, bTableSame ? TEXT("=") : TEXT("≠"),
					   static_cast<int32>(Ctx->PlanTrunkDiscs.size() / 3), bPlanSame ? TEXT("같다") : TEXT("다르다"), Pr.CrossBlocked, Pr.Trees, Pr.CrossByTrunk,
					   Pr.RingSteps, Pr.RingBlocked, Pr.RingBlockedByTree);
				if (!bTableSame || !bPlanSame || Pr.CrossByTrunk != Pr.Trees || Pr.RingBlockedByTree > 0)
				{
					UE_LOG(LogEcoPolicyV3I, Warning,
						   TEXT("[EcoV3I] %s 나무: 레벨 나무가 배치 표와 다르다(표 %d · 맞춤 %d · 다름 %d) 또는 시작 자리 원판이 세계 원판과 다르거나 이동 검사가 어긋났다 — ")
							   TEXT("파이썬 거울(results/v3/wild2/trees/tree_layout.json)과 원판이 다를 수 있다. 나무를 옮겼으면 -run=EcoV3PlaceTrees 로 다시 놓는다"),
						   *G.RegionId.ToString(), TableNum, Sc.LevelTreesSnapped, Sc.LevelTreesUnmatched);
				}
			}
			else if (T.Layout > 0)
			{
				double RLo = 0.0, RHi = 0.0, Area = 0.0;
				for (int32 k = 0; k < T.Num(); ++k)
				{
					const double Rm = T.Discs[3 * k + 2] * EcoRepertoireV3::kUnitCm / 100.0;
					RLo = k == 0 ? Rm : FMath::Min(RLo, Rm);
					RHi = k == 0 ? Rm : FMath::Max(RHi, Rm);
					Area += UE_DOUBLE_PI * T.Discs[3 * k + 2] * T.Discs[3 * k + 2];
				}
				UE_LOG(LogEcoPolicyV3I, Log,
					   TEXT("[EcoV3I] %s 나무 | 배치 표 %s %d 그루 → 놓음 %d (줄기 원판 반지름 %.2f~%.2f m, 넓이 %.3f%%, 밑동 아래 땅 높낮이 최대 %.0f cm, 가장 낮은 땅보다 %.0f cm 묻음, ")
						   TEXT("충돌 없음) · 뺌: 은신처 곁 %d · 지면 없음 %d · 메시·액터 없음 %d | 세계 원판 %d = 나무 %d + 레벨 %d (eco.IntegratedV3.StageTrees 1)"),
					   *G.RegionId.ToString(), UTF8_TO_TCHAR(EcoTreeLayoutV3::kVersion), T.Layout, T.Num(), RLo, RHi,
					   100.0 * Area / (Plan.SizeUnits * Plan.SizeUnits), T.MaxReliefCm, EcoTreeLayoutV3::kSinkCm, T.SkippedCover, T.SkippedNoGround,
					   T.SkippedNoMesh, Ctx->Sim.Config.Obstacles.Num(), T.Num(), Ctx->ObstacleScan.Num());
				if (!T.Complete())
				{
					UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] %s 나무: 표 %d 그루 가운데 %d 그루만 놓았다 — 파이썬 거울(results/v3/wild2/trees/tree_layout.json)과 원판이 다르다"),
						   *G.RegionId.ToString(), T.Layout, T.Num());
				}
			}
			else if (bInTable && Settings.bObstacles && !Imported)
			{
				UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 나무 | 레벨 나무(꼬리표 %s)가 무대에 없다 — %s"), *G.RegionId.ToString(), *LevelTrunkTag().ToString(),
					   Settings.bStageTrees ? (Plan.SizeUnits == EcoTreeLayoutV3::kStageSizeUnits ? TEXT("실행 중에도 놓지 못했다")
																							   : TEXT("무대 한 변이 배치 표와 달라 실행 중에도 놓지 않았다"))
											: TEXT("나무 없는 세계로 돈다 (편집기 명령 -run=EcoV3PlaceTrees 로 놓거나 -EcoV3StageTrees=1 로 실행 중에 놓는다)"));
			}
			else if (bInTable && Settings.bStageTrees)
			{
				UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 나무 | 놓지 않음 — %s"), *G.RegionId.ToString(),
					   !Settings.bObstacles ? TEXT("eco.IntegratedV3.Obstacles 0")
					   : Imported		   ? TEXT("이 지역 원판을 가져왔다 (eco.IntegratedV3.ObstacleImport, 측정 전용)")
										   : *FString::Printf(TEXT("무대 한 변 %.0f m 가 배치 표(%.0f m)와 다르다"), Plan.SizeUnits * 2.0,
															  EcoTreeLayoutV3::kStageSizeUnits * 2.0));
			}
		}
		Ctx->TeamCovers = Team;
		Ctx->SkippedTeamCovers = Skipped;
		Ctx->ExtraCovers = Extra;
		Ctx->CoverGroundZ = CoverZ;
		Ctx->CoverShelterIndices=MoveTemp(CoverIndices);Ctx->CoverRegistrations=MoveTemp(Registrations);
		if (Ecology)
			Ctx->bSpatialFoodRegistered = Ecology->RegisterSpatialFood(G.RegionId, Ctx->StartFood, Ctx->StartFood);
		if (!Ctx->bSpatialFoodRegistered)
		{ UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] Spatial food registration rejected: %s"), *G.RegionId.ToString()); bActive = false; return; }
		if (Config.Vegetation.bEnabled)
		{
			const auto FieldClass = Spawner.IsValid() && Spawner->VegetationFieldClass
				? Spawner->VegetationFieldClass : TSubclassOf<AEcoVegetationField>(AEcoVegetationField::StaticClass());
			auto* Field = World->SpawnActor<AEcoVegetationField>(FieldClass, Origin, FRotator::ZeroRotator);
			if (!Field) { RejectResourceContract(); return; }
			Field->RegionId = G.RegionId; Field->ContextIndex = Ctx->Index;
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoVegetation] Enabled %s: soil-v1, existing PPO unchanged, Python parity pending"), *G.RegionId.ToString());
		}
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] 지역 무대 %s (지역 번호 %d): 원점 (%.0f, %.0f, %.0f), 한 변 %.0f m | 사슴 %d 늑대 %d | 은신처 %d (레벨 %d + v3 %d, v3 반경 %.0f m, ")
				   TEXT("학습 범위 밖이라 뺀 레벨 은신처 %d) | t=%lld"),
			   *G.RegionId.ToString(), RegionIndex, Origin.X, Origin.Y, Origin.Z, Half * 2.0 / 100.0, G.Herbivores, G.Wolves,
			   static_cast<int32>(Covers.size()), Team, Extra, R / 100.0f, Skipped, static_cast<long long>(GlobalT));
		{
			// 지역 날씨 시작 줄 (10-18 야생 3단계): 이 무대의 날씨와 배수 (낮 기준 반경 — 밤에는 사슴 탐지가 (1 − 0.5·d) 배로 더 준다)
			const EcoWorldV3::FWorldState& Sw = Ctx->Sim;
			const double MPerUnit = EcoRepertoireV3::kUnitCm / 100.0;
			if (Sw.Config.Weather.bEnabled)
			{
				UE_LOG(LogEcoPolicyV3I, Log,
					   TEXT("[EcoV3I] %s 날씨 | %s %.2f%s — 사슴 위협 탐지 %.1f → %.1f m (낮) · 늑대 시야 %.1f → %.1f m · 사슴 청각 × %.2f · 사슴 이동 × %.2f · 늑대 이동 × %.2f · ")
						   TEXT("관측 visibility × %.2f (eco.IntegratedV3.Weather 1)"),
					   *G.RegionId.ToString(), UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(Sw.WeatherKind)), Sw.WeatherIntensity,
					   Sw.Config.Weather.Schedule.empty() ? TEXT(" (고정)") : TEXT(" (시간표)"), Sw.ObsCfg.SeeR * MPerUnit,
					   Sw.ObsCfg.SeeR * Sw.Weather.Sight * MPerUnit, Sw.ThreatCfg.PredViewR * MPerUnit, EcoWorldV3::WolfViewNow(Sw) * MPerUnit, Sw.Weather.Hear,
					   Sw.Weather.DeerSpeed, Sw.Weather.WolfSpeed, EcoWorldV3::ObsVisibilityMult(Sw));
			}
			else
			{
				UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 날씨 | 끔 (eco.IntegratedV3.Weather 0)"), *G.RegionId.ToString());
			}
		}
		for (const FString& Why : UEcoPolicyV3Subsystem::CheckTrainingRange(Config))
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 지역 %s 학습 범위 밖: %s"), *G.RegionId.ToString(), *Why);
		}
	}
	// 장애물 원판 JSON (eco.IntegratedV3.ObstacleExport — 파이썬 거울 짝 비교용). 경로를 주지 않으면 쓰지 않는다
	if (!Settings.ObstacleExportPath.IsEmpty())
	{
		const FString Path = FPaths::ConvertRelativePathToFull(Settings.ObstacleExportPath);
		if (ExportObstacles(Path))
		{
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 장애물 원판 목록을 썼다: %s (지역 %d)"), *Path, Contexts.Num());
		}
		else
		{
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 장애물 원판 목록을 쓰지 못했다: %s"), *Path);
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
	// 허용 칸 = 지금 두뇌 ∧ 세계 칸 (내장 두뇌면 InitWorld 그대로 — 두뇌가 바뀌면 SyncBrain 이 다시 정한다), 관측 칸 수 = 지금 두뇌의 계약 (18·21·24 —
	// R5 장애물 관측 계약 2-4, 10-24 두 길 두뇌), 두 길·반사 밖 FLEE 막음 = 지금 두뇌가 판 4·5 일 때만 (내장 두뇌면 모두 InitWorld 그대로). 걸 수 없는 두뇌
	// (예: 도주 반사를 끈 세계에 앞 Play 의 두 길 두뇌)는 첫 SyncBrain 이 이 월드에서 내장으로 되돌린다. 대조 기록을 켜면 18 두뇌여도 세 칸을 만든다 (결정 그대로)
	ApplyBrainToWorld(Ctx->Sim, GetActiveBrain());
	Ctx->Sim.bObstacleObsProbe = ObsParityEvery() > 0;
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
	InitContextEnv(*Raw);   // 환경 바뀜 감시 바탕 (10-21, EcoV3EnvWatch.cpp — 읽기만, 세계는 그대로)
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
// 두뇌 (10-18 실행 중 가중치 로더 — EcoV3Brain.h)
// -----------------------------------------------------------------------------

const FEcoV3Brain& UEcoPolicyV3IntegratedSubsystem::GetActiveBrain() const
{
	return ActiveBrain.IsValid() ? *ActiveBrain : *FEcoV3BrainRegistry::Get().GetActive();
}

FString UEcoPolicyV3IntegratedSubsystem::RouteBrainBlocker(const EcoWorldV3::FWorldState& W, const FEcoV3Brain& B)
{
	namespace R3 = EcoRepertoireV3;
	if (!B.bRoute())
	{
		return FString();
	}
	// 이식 계획서 12절 질문 12 (정한 것 — 권고대로 거부): 두 길은 도주 반사 안에서만 고른다. 반사가 없으면 판 5 는 도망을 시작할 길이 아예 없다
	if (!W.Config.WildFlight.bEnabled)
	{
		return FString::Printf(TEXT("도주 반사(eco.IntegratedV3.WildFlight)를 끈 세계 — 마스크 판 %d 두뇌는 반사 도주 안에서만 길을 고른다"), B.MaskVersion);
	}
	// 실제 허용 = 두뇌 ∧ 세계 칸 (rep_policy.check_route_allowed 의 effective_allowed — 이식 계획서 4절). 칸 3·4 는 도주 중 길 칸이라 막혀야 한다
	uint8 Eff[R3::kNumBehaviors] = {};
	for (int32 b = 0; b < R3::kNumBehaviors; ++b)
	{
		Eff[b] = (B.Allowed[b] != 0 && W.Config.WorldAllowed[b] != 0) ? 1 : 0;
	}
	if (Eff[R3::kFreeze] != 0 || Eff[R3::kSleep] != 0)
	{
		return FString::Printf(TEXT("실제 허용(두뇌 ∧ 세계) %s 에 얼기·잠이 남는다 — 판 %d 는 칸 3·4 를 길 칸으로 쓴다"), *EcoV3Brain::AllowedText(Eff), B.MaskVersion);
	}
	if (Eff[R3::kGraze] == 0)
	{
		return TEXT("실제 허용에 먹기가 없다 — 덮기 밖 결정 줄이 빌 수 있다");
	}
	return FString();
}

FString UEcoPolicyV3IntegratedSubsystem::BrainBlocker(const FEcoV3Brain& B) const
{
	for (const TUniquePtr<FEcoV3RegionContext>& Ctx : Contexts)
	{
		const FString Why = RouteBrainBlocker(Ctx->Sim, B);
		if (!Why.IsEmpty())
		{
			return FString::Printf(TEXT("%s: %s"), *Ctx->RegionId.ToString(), *Why);
		}
	}
	return FString();
}

void UEcoPolicyV3IntegratedSubsystem::ApplyBrainToWorld(EcoWorldV3::FWorldState& W, const FEcoV3Brain& B)
{
	EcoWorldV3::SetModelAllowed(W, B.Allowed);
	EcoWorldV3::SetModelObsDim(W, B.Net.ObsDim);
	// 10-24 두 길 두뇌 (이식 계획서 8-2 의 2·13-3): 세계 설정이 아니라 두뇌가 정한다 — 판 4·5 면 길, 판 5 면 반사 밖 FLEE 막음 (둘 다 도주 반사를 켠 세계만).
	// 판 2 두뇌는 둘 다 거짓이라 InitWorld 그대로다 (끈 세계 비트 동일)
	EcoWorldV3::SetModelRoute(W, B.bRoute());
	EcoWorldV3::SetModelFleeGate(W, B.bFleeGate());
}

void UEcoPolicyV3IntegratedSubsystem::SyncBrain(bool bPollWatch)
{
	FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
	const double Seconds = static_cast<double>(GlobalT) * EcoRepertoireV3::kStepSeconds;
	// 예정 바꾸기 (측정·시연용): 전역 스텝 × 2/15 초가 그 시각 이상인 첫 경계에서 한 번
	if (!bScheduledSwapDone)
	{
		const float At = EcoV3Brain::SwapAtSeconds();
		if (At >= 0.0f && Seconds + 1e-9 >= static_cast<double>(At))
		{
			bScheduledSwapDone = true;
			const FString File = EcoV3Brain::SwapFile();
			const FEcoV3BrainLoad L = FEcoV3BrainRegistry::LoadFile(File);
			if (L.Ok())
			{
				Reg.Queue(L.Brain.ToSharedRef(), FString::Printf(TEXT("예정 바꾸기 eco.V3Brain.SwapAtSeconds %.1f · SwapFile %s"), At, *File));
			}
			else
			{
				UE_LOG(LogEcoPolicyV3I, Error, TEXT("[EcoV3I] 예정 두뇌 바꾸기 '%s' 거부 (%s): %s — %s 그대로"), *File, EcoV3Brain::RejectName(L.Reason), *L.Message,
					   *GetActiveBrain().Id);
			}
		}
	}
	if (bPollWatch)
	{
		Reg.PollWatch(FPlatformTime::Seconds());
		// 폴더 감시 거부 알림 (거부마다 한 번 — 저장소가 거부할 때 Serial 을 올린다)
		const FEcoV3WatchReject& Rej = Reg.GetLastWatchReject();
		if (Rej.Serial != ShownRejectSerial)
		{
			ShownRejectSerial = Rej.Serial;
			if (!Rej.File.IsEmpty())
			{
				PostNotice(EcoV3Integrated::ENotice::Reject,
						   FString::Printf(TEXT("두뇌 파일 거부 — %s: %s"), *FPaths::GetCleanFilename(Rej.File), EcoV3Brain::RejectName(Rej.Reason)));
			}
		}
	}
	// 10-24 두 길 두뇌 걸기 전 검사 (이식 계획서 8-2 의 1): 대기 두뇌가 판 4·5 인데 어느 지역이 도주 반사를 껐거나 실제 허용(두뇌 ∧ 세계)에 얼기·잠이 남으면
	// 대기 두뇌를 버리고 지금 두뇌를 둔다 (거부 알림 — 폴더 감시 거부와 같은 꼴). 판 2 두뇌는 보지 않는다 (지금 그대로)
	if (const FEcoV3BrainPtr Pend = Reg.GetPending())
	{
		const FString Block = BrainBlocker(*Pend);
		if (!Block.IsEmpty())
		{
			const FString PendId = Pend->Id;
			Reg.DiscardPending(FString::Printf(TEXT("두 길 두뇌를 걸 수 없다 — %s"), *Block));
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 두뇌 거부 | %.1f초 (전역 스텝 %lld) | %s — %s | %s 그대로"), Seconds, static_cast<long long>(GlobalT),
				   *PendId, *Block, *GetActiveBrain().Id);
			PostNotice(EcoV3Integrated::ENotice::Reject, FString::Printf(TEXT("두뇌 거부 — %s: %s"), *PendId, *Block));
		}
	}
	FString Why;
	bool bRollback = false;
	const bool bSwapped = Reg.CommitPending(nullptr, &Why, &bRollback);
	if (ActiveBrain.IsValid() && AppliedBrainGen == Reg.GetGeneration())
	{
		return;
	}
	FEcoV3BrainRef Now = Reg.GetActive();
	const FEcoV3BrainPtr Before = ActiveBrain;
	{
		// 저장소의 지금 두뇌를 이 월드에 걸 수 없다 (앞 Play·다른 월드가 건 두 길 두뇌를 도주 반사를 끈 이 월드가 받음 — 대기 검사를 지나지 않은 길):
		// 저장소는 그대로 두고 이 월드만 앞 두뇌(처음이면 내장)를 쓴다
		const FString Block = BrainBlocker(*Now);
		if (!Block.IsEmpty())
		{
			const FEcoV3BrainRef Keep = Before.IsValid() ? Before.ToSharedRef() : FEcoV3BrainRegistry::Builtin();
			UE_LOG(LogEcoPolicyV3I, Warning, TEXT("[EcoV3I] 두뇌 거부 | %.1f초 (전역 스텝 %lld) | 저장소 두뇌 %s 를 이 월드에 걸 수 없다 — %s | 이 월드는 %s"), Seconds,
				   static_cast<long long>(GlobalT), *Now->Id, *Block, *Keep->Id);
			PostNotice(EcoV3Integrated::ENotice::Reject, FString::Printf(TEXT("두뇌 거부 — %s: %s"), *Now->Id, *Block));
			AppliedBrainGen = Reg.GetGeneration();
			if (Before.IsValid())
			{
				return;   // 지역 세계는 앞 두뇌 그대로다
			}
			Now = Keep;
		}
	}
	FString AllowedByRegion;
	for (const TUniquePtr<FEcoV3RegionContext>& Ctx : Contexts)
	{
		// 허용 칸 = 새 두뇌 ∧ 세계, 관측 칸 수 = 새 두뇌의 계약 (R5 장애물 관측 21 이면 이 스텝 끝 관측부터 세 칸을 더 만들고, 그 결정부터 새 두뇌가 21 칸을 읽는다),
		// 10-24 두 길 (판 4·5 두뇌만 — 이 스텝 H 부터 길 단계. 열린 도주는 길 없음 결정으로 새 두뇌가 곧바로 고르고, 길 없는 두뇌로 바꾸면 A 가 반사 방향으로 둔 뒤
		// H 가 길 상태를 지운다 — 이식 계획서 8-2 의 3)·반사 밖 FLEE 막음 (판 5)
		ApplyBrainToWorld(Ctx->Sim, *Now);
		Ctx->SinceSwapBrainTally = FEcoV3BrainTally();
		if (Before.IsValid() && Ctx->FlightOn())
		{
			// 도망 기록 두뇌 판 (EcoV3FlightTally.h): 지금 판의 합을 '교체 전'으로, 새 판은 0 에서 (결정 스텝 경계 — 열린 도망은 새 판에 든다)
			Ctx->FlightTally.OnBrainSwap(EcoV3Flight::FSum::Of(Ctx->Sim.Stats.Flight));
		}
		AllowedByRegion += FString::Printf(TEXT("%s%s %s%s"), AllowedByRegion.IsEmpty() ? TEXT("") : TEXT(" · "), *Ctx->RegionId.ToString(),
										   *EcoV3Brain::AllowedText(Ctx->Sim.Allowed),
										   Ctx->RouteOn() ? (Ctx->Sim.bFleeGate ? TEXT(" (두 길·반사 밖 도망 막음)") : TEXT(" (두 길)")) : TEXT(""));
	}
	if (AllowedByRegion.IsEmpty())
	{
		AllowedByRegion = TEXT("(지역 세계 없음)");
	}
	if (!Before.IsValid())
	{
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 두뇌 시작 | %.1f초 (전역 스텝 %lld) | %s%s | 허용(모델 ∧ 세계): %s"), Seconds, static_cast<long long>(GlobalT),
			   *Now->Describe(), bSwapped ? *FString::Printf(TEXT(" — 대기 두뇌로 시작 (%s)"), *Why) : TEXT(""), *AllowedByRegion);
	}
	else
	{
		LastBrainSwapStep = GlobalT;
		LastBrainSwapFrom = Before->Id;
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] 두뇌 바꿈 | %.1f초 (전역 스텝 %lld) | %s → %s | 까닭: %s | 허용(모델 ∧ 세계): %s | 사슴 몸·행동 상태 그대로 — 이 스텝은 앞 두뇌가 ")
				   TEXT("정한 요청을 실행하고, 이 스텝 끝 결정부터 새 두뇌 | 학습 %s | 골든 %d 사례 최대 로짓 오차 %.2e"),
			   Seconds, static_cast<long long>(GlobalT), *Before->Id, *Now->Describe(), bSwapped ? *Why : TEXT("저장소 되돌림"), *AllowedByRegion,
			   *Now->TrainWorld, Now->GoldenCount, Now->GoldenMaxError);
		// 화면 알림 (10-21 실시간 두뇌 교체): 되돌림이면 '두뇌 되돌림 → 판 n (id)', 아니면 '새 두뇌 — 판 n · id · 환경 · 관문 · 되돌리기 …'.
		// 다른 월드가 바꾼 것(같은 저장소)도 저장소의 마지막 바꾸기로 가른다
		++BrainSwapsThisPlay;
		const bool bWasRollback = bSwapped ? bRollback : Reg.WasLastCommitRollback();
		PostNotice(bWasRollback ? EcoV3Integrated::ENotice::Rollback : EcoV3Integrated::ENotice::Swap,
				   EcoPolicyV3IntegratedImpl::BrainNoticeText(*Now, bWasRollback));
	}
	ActiveBrain = Now;
	AppliedBrainGen = Reg.GetGeneration();
}

// -----------------------------------------------------------------------------
// R5 장애물 관측 대조 기록 (10-19, 계약 POLICY_CONTRACT_V3.md 2-4 — herbivore_rl/results/v3/r5/unreal_parity.py 가 읽는다)
// -----------------------------------------------------------------------------

int32 UEcoPolicyV3IntegratedSubsystem::ObsParityEvery()
{
	EcoPolicyV3IntegratedImpl::EnsureCommandLineApplied();
	return FMath::Max(0, EcoPolicyV3IntegratedImpl::CVarObsParityLog.GetValueOnGameThread());
}

void UEcoPolicyV3IntegratedSubsystem::LogObsParity(FEcoV3RegionContext& Ctx, const EcoWorldV3::FHerbView* Views, const int64* Ids, int32 Num)
{
	const int32 Every = ObsParityEvery();
	if (Every <= 0)
	{
		return;
	}
	// 결정 지문: 이 스텝의 사슴마다 (id, 읽음, 마스크, 다음 요청, 로짓 비트, 이번 스텝에 실행한 행동) — 두 판(예: 내장 대 관측 21 새 열 0)의 모든 결정이 같은지 본다
	auto Mix = [&Ctx](const void* Data, int32 Bytes)
	{
		const uint8* B = static_cast<const uint8*>(Data);
		for (int32 i = 0; i < Bytes; ++i)
		{
			Ctx.ObsParityDecisionHash = (Ctx.ObsParityDecisionHash ^ B[i]) * 1099511628211ULL;
		}
	};
	for (int32 r = 0; r < Num; ++r)
	{
		const EcoWorldV3::FHerbDecision& D = *Views[r].Decision;
		const uint8 Reads = D.Prep.bReads ? 1 : 0;
		Mix(&Ids[r], sizeof(int64));
		Mix(&Reads, 1);
		Mix(D.Mask, sizeof(D.Mask));
		Mix(&D.Request, sizeof(D.Request));
		Mix(D.Logits, sizeof(D.Logits));
		Mix(&D.ExecutedBehavior, sizeof(D.ExecutedBehavior));
		++Ctx.ObsParityDecisions;
	}
	if (Ctx.Sim.T % Every != 0 || !(Ctx.Sim.ObsDim >= EcoObservationV3::kObsDimObstacle || Ctx.Sim.bObstacleObsProbe))
	{
		return;
	}
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3Obs] %s 결정 | t %lld | 사슴·스텝 %lld | 지문 %016llx"), *Ctx.RegionId.ToString(), static_cast<long long>(Ctx.Sim.T),
		   static_cast<long long>(Ctx.ObsParityDecisions), static_cast<unsigned long long>(Ctx.ObsParityDecisionHash));
	// 실수는 %.17g (double 왕복), 관측 칸은 float 비트 16진 — 파이썬이 비트 단위로 견준다
	auto G17 = [](double V) { return FString::Printf(TEXT("%.17g"), V); };
	if (!Ctx.bObsParityDiscsLogged)
	{
		Ctx.bObsParityDiscsLogged = true;
		const EcoWorldV3::FObstacleConfig& Ob = Ctx.Sim.Config.Obstacles;
		const int32 K = Ob.Active() ? Ob.Num() : 0;
		FString Discs;
		for (int32 k = 0; k < K; ++k)
		{
			Discs += FString::Printf(TEXT(" %s,%s,%s"), *G17(Ob.Discs[3 * k]), *G17(Ob.Discs[3 * k + 1]), *G17(Ob.Discs[3 * k + 2]));
		}
		// 숲 시야 (10-22): 관측 가림이 쓰는 값 그대로 (ObstacleObsInputOf — 켬 = FoliageOn, 반지름·문턱 단위, 원판마다 나무 1·아님 0, 원판이 없으면 '-').
		// unreal_parity.py 가 켠 판이면 잎 원 중심 = 나무 원판으로 다시 잰다
		FString FolTrees;
		const uint8* FolTr = Ob.FoliageTrees();
		for (int32 k = 0; k < K; ++k)
		{
			FolTrees += (FolTr == nullptr || (k < static_cast<int32>(Ob.Foliage.Trees.size()) && FolTr[k] != 0)) ? TEXT("1") : TEXT("0");
		}
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3Obs] %s 원판 | 원판 %d | 몸 %s | 무대 %s | 가림 %d | 두뇌 %s 관측 %d | 분모 %s %s | 잎 %d %s %s %s |%s"),
			   *Ctx.RegionId.ToString(), K, *G17(Ob.bEnabled ? Ob.BodyR : 0.0), *G17(Ctx.Sim.Config.WorldSize), Ob.bEnabled && Ob.bBlockSight ? 1 : 0,
			   *GetActiveBrain().Id, Ctx.Sim.ObsDim, *G17(Ctx.Sim.ObstacleObsCfg.EscapeNorm), *G17(Ctx.Sim.ObstacleObsCfg.NearNorm), Ob.FoliageOn() ? 1 : 0,
			   *G17(Ob.Foliage.R), *G17(Ob.Foliage.Block), FolTrees.IsEmpty() ? TEXT("-") : *FolTrees, *Discs);
	}
	for (int32 r = 0; r < Num; ++r)
	{
		const EcoWorldV3::FHerbView& V = Views[r];
		if (V.Body->DeathCause != EcoWorldV3::kDeathNone)
		{
			continue;   // 이번 스텝에 죽은 사슴 (계산은 했지만 쓰지 않는다 — 계약 2-4)
		}
		const EcoWorldV3::FHerbPerception& P = *V.Perception;
		const EcoObservationV3::FObstacleObsInput In = EcoWorldV3::Detail::ObstacleObsInputOf(Ctx.Sim, P, *V.Body);
		uint32 Bits[EcoObservationV3::kNumObstacleObs];
		FMemory::Memcpy(Bits, P.ObstacleObs, sizeof(Bits));
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3Obs] %s | t %lld | id %lld | p %s %s | h %s %s | seen %d | a %s %s | j %s %s | E %s | N %s | hid %d | o %08x %08x %08x"),
			   *Ctx.RegionId.ToString(), static_cast<long long>(Ctx.Sim.T), static_cast<long long>(Ids[r]), *G17(In.Pos.X), *G17(In.Pos.Y), *G17(In.Head.X),
			   *G17(In.Head.Y), In.bSeen ? 1 : 0, *G17(In.Away.X), *G17(In.Away.Y), *G17(In.bSeen ? In.Threat.X : 0.0), *G17(In.bSeen ? In.Threat.Y : 0.0),
			   *G17(P.Obstacle.Escape), *G17(P.Obstacle.Near), P.Obstacle.bThreatHidden ? 1 : 0, Bits[0], Bits[1], Bits[2]);
		++Ctx.ObsParityLines;
	}
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
	if (Ctx.FlightOn())
	{
		Ctx.FlightTally.Push(EcoV3Flight::FSum::Of(Ctx.Sim.Stats.Flight));   // 도망 기록 최근 60 초 창·두뇌 판 (기록만)
	}
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
	// 다섯째 줄: 야생 2단계 기록 (10-17, 늘 적는다). 사냥 성공률(world.py hunt_update 와 같은 정의, 누적), 은신처 안 사슴 시간, 은신처 둘레 밖 잡힘.
	//   (results/v3/mirror/compare_unreal.py·results/v3/wild1/compare_unreal_wild.py 의 정규식은 '<지역> 사냥·은신처 |' 꼴에 걸리지 않는다 — 앞 네 줄 그대로)
	{
		auto Sum = [](const int64* Arr) { int64 Tot = 0; for (int32 k = 0; k < EcoWorldV3::kNumHuntKinds; ++k) { Tot += Arr[k]; } return Tot; };
		const int64 HS = Sum(S.HuntStarts), HE = Sum(S.HuntEnds), HW = Sum(S.HuntSuccess), HO = Sum(S.HuntOutside);
		const int32 Ch = static_cast<int32>(EcoThreatV3::EThreatType::Chaser);
		const int32 St = static_cast<int32>(EcoThreatV3::EThreatType::Stalker);
		auto Rate = [](int64 Num, int64 Den) { return Den > 0 ? 100.0 * static_cast<double>(Num) / static_cast<double>(Den) : 0.0; };
		const int64 LiveN = S.LiveDeerSteps - P.LiveDeerSteps;
		const int64 InN = S.ShelterDeerSteps - P.ShelterDeerSteps;
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 사냥·은신처 | %.1f초 | 사냥 누적: 시작 %lld · 끝 %lld · 성공 %lld · 사냥 밖 포획 %lld · 성공률 %.1f%% ")
				   TEXT("(추격형 시작 %lld 끝 %lld 성공 %lld · 잠행형 시작 %lld 끝 %lld 성공 %lld) · 구간 시작 %lld 끝 %lld 성공 %lld | ")
				   TEXT("은신처 안 사슴·스텝: 구간 %lld/%lld (%.1f%%) · 누적 %lld/%lld (%.1f%%) | 은신처 둘레 밖 잡힘 누적: 2 m 안 %lld · 4 m 안 %lld | ")
				   TEXT("은신처 먹이 %s"),
			   *Ctx.RegionId.ToString(), Seconds, static_cast<long long>(HS), static_cast<long long>(HE), static_cast<long long>(HW),
			   static_cast<long long>(HO), Rate(HW, HE), static_cast<long long>(S.HuntStarts[Ch]), static_cast<long long>(S.HuntEnds[Ch]),
			   static_cast<long long>(S.HuntSuccess[Ch]), static_cast<long long>(S.HuntStarts[St]), static_cast<long long>(S.HuntEnds[St]),
			   static_cast<long long>(S.HuntSuccess[St]), static_cast<long long>(HS - Sum(P.HuntStarts)),
			   static_cast<long long>(HE - Sum(P.HuntEnds)), static_cast<long long>(HW - Sum(P.HuntSuccess)), static_cast<long long>(InN),
			   static_cast<long long>(LiveN), LiveN > 0 ? 100.0 * static_cast<double>(InN) / static_cast<double>(LiveN) : 0.0,
			   static_cast<long long>(S.ShelterDeerSteps), static_cast<long long>(S.LiveDeerSteps),
			   S.LiveDeerSteps > 0 ? 100.0 * static_cast<double>(S.ShelterDeerSteps) / static_cast<double>(S.LiveDeerSteps) : 0.0,
			   static_cast<long long>(S.CaughtNearCover[0]), static_cast<long long>(S.CaughtNearCover[1]),
			   Ctx.Sim.Config.ShelterFood.bEnabled ? TEXT("부족 켬") : TEXT("부족 끔"));
	}
	// 여섯째 줄: 야생 2단계 2 늑대 무리 (10-17, 협동 사냥을 켰을 때만). 누적 늑대·스텝 가운데 앞장·돕기·기다림·은신처 문, 늑대 포획·협동 포획
	//   (world.py pack_stats·run_mirror.py 10초 줄 pack_* 와 같은 정의. 앞 다섯 줄의 정규식은 '<지역> 늑대 무리 |' 꼴에 걸리지 않는다)
	if (Ctx.Sim.ThreatCfg.Pack.bEnabled)
	{
		const int64 Wn = S.PackWolfSteps;
		auto Pc = [Wn](int64 X) { return Wn > 0 ? 100.0 * static_cast<double>(X) / static_cast<double>(Wn) : 0.0; };
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 늑대 무리 | %.1f초 | 늑대 %d | 누적 늑대·스텝 %lld: 앞장 %lld (%.1f%%) · 돕기 %lld (%.1f%%) · 기다림 %lld · 은신처 문 %lld | ")
				   TEXT("늑대 포획 누적 %lld · 협동 포획 %lld (다른 앞장 늑대도 쫓던 사슴)"),
			   *Ctx.RegionId.ToString(), Seconds, Ctx.Wolves, static_cast<long long>(Wn), static_cast<long long>(S.PackLeadSteps), Pc(S.PackLeadSteps),
			   static_cast<long long>(S.PackHelpSteps), Pc(S.PackHelpSteps), static_cast<long long>(S.PackWaitSteps),
			   static_cast<long long>(S.PackDoorSteps), static_cast<long long>(S.PackCatches), static_cast<long long>(S.PackCoopCatches));
	}
	// 일곱째 줄: 야생 2단계 3 세로 장애물 (10-17, 원판이 있을 때만 — 무대에 충돌하는 나무·바위가 없으면 적지 않는다). 누적 사슴·늑대 미끄러짐·물러남·돌아섬과
	//   원판 밖으로 옮긴 개체 (world.py obstacle_stats 와 같은 정의. 앞 여섯 줄의 정규식은 '<지역> 장애물 |' 꼴에 걸리지 않는다)
	if (Ctx.Sim.Config.Obstacles.Active())
	{
		const EcoWorldV3::FObstacleConfig& Ob = Ctx.Sim.Config.Obstacles;
		auto Pc = [](int64 X, int64 N) { return N > 0 ? 100.0 * static_cast<double>(X) / static_cast<double>(N) : 0.0; };
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 장애물 | %.1f초 | 원판 %d (%s, 몸 %.0f cm, 눈길 가림 %s, 먹이 줄임 %s) | 누적 사슴·스텝 %lld: 닿음 %lld (%.2f%%) · 물러남 %lld | ")
				   TEXT("늑대·스텝 %lld: 닿음 %lld (%.2f%%) · 되돌림 %lld · 돌아섬 %lld | 원판 밖으로 옮김 %lld (못 옮김 %lld)%s"),
			   *Ctx.RegionId.ToString(), Seconds, Ob.Num(),
			   Ctx.bObstaclesImported ? TEXT("가져온 원판 — 측정 전용")
			   : Ctx.Trees.Num() > 0  ? *FString::Printf(TEXT("무대 나무 %d + 레벨에서 읽음 %d"), Ctx.Trees.Num(), Ctx.ObstacleScan.Num())
			   : Ctx.ObstacleScan.LevelTrees > 0
				   ? *FString::Printf(TEXT("레벨 나무 %d + 그 밖 레벨에서 읽음 %d"), Ctx.ObstacleScan.LevelTrees, Ctx.ObstacleScan.Num() - Ctx.ObstacleScan.LevelTrees)
				   : TEXT("레벨에서 읽음"),
			   Ob.BodyR * EcoRepertoireV3::kUnitCm, Ob.bBlockSight ? TEXT("켬") : TEXT("끔"), Ob.bNoFood ? TEXT("켬") : TEXT("끔"),
			   static_cast<long long>(S.ObstacleDeerSteps), static_cast<long long>(S.ObstacleDeerHit), Pc(S.ObstacleDeerHit, S.ObstacleDeerSteps),
			   static_cast<long long>(S.ObstacleDeerBack), static_cast<long long>(S.ObstacleWolfSteps), static_cast<long long>(S.ObstacleWolfHit),
			   Pc(S.ObstacleWolfHit, S.ObstacleWolfSteps), static_cast<long long>(S.ObstacleWolfBack), static_cast<long long>(S.ObstacleWolfDead),
			   static_cast<long long>(S.ObstaclePushMoved), static_cast<long long>(S.ObstaclePushFailed),
			   Ob.Detour.bEnabled
				   ? *FString::Printf(TEXT(" | 돌아가기 | 사슴 바꿈 %lld (시작 %lld · 못 찾음 %lld) · 늑대 바꿈 %lld (시작 %lld · 못 찾음 %lld) · 돕기 그만둠 %lld"),
									  static_cast<long long>(S.DetourDeerUsed), static_cast<long long>(S.DetourDeerStart), static_cast<long long>(S.DetourDeerFail),
									  static_cast<long long>(S.DetourWolfUsed), static_cast<long long>(S.DetourWolfStart), static_cast<long long>(S.DetourWolfFail),
									  static_cast<long long>(S.DetourHelpDrop))
				   : TEXT(""));
	}
	// 여덟째 줄: 야생 3단계 지역 날씨와 감지 (10-18, 감지 기록을 켠 세계 — 통합 모드는 늘. 날씨를 끄면 '날씨 끔'). 지금 날씨·배수·늑대 시야, 날씨별 스텝 누적,
	//   산 사슴 × 깨어 있는 늑대 쌍의 거리 띠별 감지 누적과 들어서만 안 사슴·스텝 (run_mirror.py --diag band_pairs·band_seen·heard_live 와 같은 정의 — 기록만)
	if (Ctx.Sim.Config.bSenseStats)
	{
		const EcoWorldV3::FWeatherConfig& Wx = Ctx.Sim.Config.Weather;
		const EcoWorldV3::FWeatherMults& Mu = Ctx.Sim.Weather;
		auto Pc = [](int64 X, int64 N) { return N > 0 ? 100.0 * static_cast<double>(X) / static_cast<double>(N) : 0.0; };
		const FString WxNow = Wx.bEnabled
								  ? FString::Printf(TEXT("%s %.2f (시야 × %.2f · 사슴 청각 × %.2f · 사슴 이동 × %.2f · 늑대 이동 × %.2f, 늑대 시야 %.1f m)"),
													UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(Ctx.Sim.WeatherKind)), Ctx.Sim.WeatherIntensity, Mu.Sight, Mu.Hear,
													Mu.DeerSpeed, Mu.WolfSpeed, EcoWorldV3::WolfViewNow(Ctx.Sim) * EcoRepertoireV3::kUnitCm / 100.0)
								  : FString(TEXT("날씨 끔 (eco.IntegratedV3.Weather 0)"));
		FString Bands;
		static const TCHAR* const BandNames[EcoWorldV3::kNumSenseBands] = {TEXT("<5"), TEXT("5~10"), TEXT("10~15"), TEXT("15~30")};
		for (int32 b = 0; b < EcoWorldV3::kNumSenseBands; ++b)
		{
			Bands += FString::Printf(TEXT("%s%s m %lld/%lld (%.1f%%)"), b == 0 ? TEXT("") : TEXT(" · "), BandNames[b], static_cast<long long>(S.SenseSeen[b]),
									 static_cast<long long>(S.SensePairs[b]), Pc(S.SenseSeen[b], S.SensePairs[b]));
		}
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 날씨 | %.1f초 | %s | 날씨 스텝 누적 맑음 %lld · 비 %lld · 눈 %lld | 감지 누적(산 사슴 × 깨어 있는 늑대 쌍): %s | ")
				   TEXT("들어서만 안 사슴·스텝 %lld/%lld (%.2f%%)"),
			   *Ctx.RegionId.ToString(), Seconds, *WxNow, static_cast<long long>(S.WeatherSteps[EcoWorldV3::kWeatherClear]),
			   static_cast<long long>(S.WeatherSteps[EcoWorldV3::kWeatherRain]), static_cast<long long>(S.WeatherSteps[EcoWorldV3::kWeatherSnow]), *Bands,
			   static_cast<long long>(S.SenseHeardOnly), static_cast<long long>(S.SenseLiveSteps), Pc(S.SenseHeardOnly, S.SenseLiveSteps));
	}
	// 아홉째 줄: 사슴 두뇌 (10-18 두뇌 바꾸기, 늘 적는다). 지금 두뇌 id 와 구간 두뇌 스텝(도주 반사 밖)의 행동 몫, 그중 늑대를 알 때의 행동 몫
	//   (FEcoV3BrainTally — R4 situ_eval.py 와 같은 정의). 앞 여덟 줄의 정규식은 '<지역> 두뇌 |' 꼴에 걸리지 않는다
	{
		const FEcoV3BrainTally D = Ctx.BrainTally.Minus(Ctx.LastLogBrainTally);
		auto Shares = [](const int64* Arr, int64 Tot)
		{
			FString Out;
			for (int32 b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
			{
				Out += FString::Printf(TEXT("%s%s %lld (%.1f%%)"), b == 0 ? TEXT("") : TEXT(" · "), BehaviorNameKo(b), static_cast<long long>(Arr[b]),
									   Tot > 0 ? 100.0 * static_cast<double>(Arr[b]) / static_cast<double>(Tot) : 0.0);
			}
			return Out;
		};
		// 이 구간 안에서 바꿨으면 (스텝 LastLogT 뒤·지금 앞의 경계) 앞 두뇌도 적는다 — 구간 몫이 두 두뇌에 걸친다
		const bool bMixed = LastBrainSwapStep > Ctx.LastLogT && LastBrainSwapStep < Ctx.Sim.T;
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 두뇌 | %.1f초 | 두뇌 %s%s | 구간 두뇌 스텝(도주 반사 밖) %lld: %s | 그중 늑대를 앎 %lld: %s | 반사 스텝 %lld (늑대를 앎 %lld)"),
			   *Ctx.RegionId.ToString(), Seconds, *GetActiveBrain().Id,
			   bMixed ? *FString::Printf(TEXT(" (구간 중 바꿈: 전역 스텝 %lld 에 %s →)"), static_cast<long long>(LastBrainSwapStep), *LastBrainSwapFrom) : TEXT(""),
			   static_cast<long long>(D.Total()), *Shares(D.Steps, D.Total()), static_cast<long long>(D.KnowTotal()), *Shares(D.KnowSteps, D.KnowTotal()),
			   static_cast<long long>(D.Reflex), static_cast<long long>(D.ReflexKnow));
		Ctx.LastLogBrainTally = Ctx.BrainTally;
	}
	// 아홉째 줄 뒤 (10-24 두 길 두뇌, 이식 계획서 8-3 — 길 통계가 있는 세계만: 지금 판 4·5 두뇌이거나 앞서 걸었던 세계): 구간·누적의 실행한 반사 길 RUN·SHELTER 스텝,
	//   길 결정·은신처 고름(SHELTER 가 열린 결정 가운데)·무효·바꿈 (world.py route_stats 와 같은 칸 — 고름·열림·바꿈은 적용 때 센다). 아홉째 줄 '<지역> 두뇌 |' 꼴은
	//   그대로 두고 따로 적는다 (results/v3/brain_swap/compare_swap.py 정규식이 그 줄 끝을 본다)
	if (Ctx.RouteSeen())
	{
		const FEcoV3RouteSum Tot = FEcoV3RouteSum::Of(S.Route);
		const FEcoV3RouteSum Iv = Tot.Minus(FEcoV3RouteSum::Of(P.Route));
		UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s 길 | %.1f초 | %s | 구간 %s | 누적 %s · 도주 시작 %lld · 바꿈 %lld"), *Ctx.RegionId.ToString(), Seconds,
			   Ctx.RouteOn() ? (Ctx.Sim.bFleeGate ? TEXT("두 길 켬 (판 5 — 반사 밖 도망 막음)") : TEXT("두 길 켬 (판 4)")) : TEXT("두 길 끔 (앞 두뇌가 센 누적)"),
			   *Iv.Text(), *Tot.Text(), static_cast<long long>(Tot.Onsets), static_cast<long long>(Tot.Switches));
	}
	// 열째 줄: 야생 (w3) 도망 기록 (10-21, 도망 기록을 세는 세계만 — 정의는 EcoWorldV3.h 머리 주석 '도망 기록' = world.py flight_stats, 집계는 EcoV3FlightTally.h).
	//   구간(지난 기록 줄 뒤)에 끝난 도망의 끝 까닭별 수·평균 길이·스스로 벗어난 도망의 쫓긴 시간(10-23 부터 보고만), 최근 60 초 창, 누적(열린 도망 = 잘림,
	//   10-23 쫓긴 도망·숨음(지켜보는 중 포함)·지켜보는 동안 잡힘·굶음 — 옛 도망 단위 숨음 비율, 보고만. 10-24 쫓긴 사건·숨음(지켜보는 중 포함)·잡힘·굶음·
	//   이어진 도망 — 관문 1차 사건 숨음 비율·GH 의 재료), 두뇌 판 비교(사건 단위). 앞 아홉 줄의 정규식은 '<지역> 도망 |' 꼴에 걸리지 않는다
	if (Ctx.FlightOn())
	{
		const EcoV3Flight::FSum Iv = EcoV3Flight::FSum::Of(S.Flight).Minus(EcoV3Flight::FSum::Of(P.Flight));
		FString Causes;
		for (int32 c = 0; c < EcoWorldV3::kNumFlightCauses; ++c)
		{
			if (c == EcoWorldV3::kFlightTruncated)
			{
				continue;   // 잘림은 보고 때만 (끝나지 않은 도망)
			}
			Causes += FString::Printf(TEXT("%s%s %lld"), c == 0 ? TEXT("") : c == EcoWorldV3::kNumFlightOwn ? TEXT(" / ") : TEXT(" · "),
									  UTF8_TO_TCHAR(EcoWorldV3::FlightCauseNameKoUtf8(c)), static_cast<long long>(S.Flight.Num[c] - P.Flight.Num[c]));
		}
		const EcoWorldV3::FFlightReport Tot = EcoWorldV3::FlightReportOf(S.Flight, Ctx.FlightOpen);
		const int64 TotEnded = Tot.Started - Tot.Num[EcoWorldV3::kFlightTruncated];
		UE_LOG(LogEcoPolicyV3I, Log,
			   TEXT("[EcoV3I] %s 도망 | %.1f초 | 구간 시작 %lld · 끝 %lld (스스로: %s) · 평균 %.1f초 · 스스로 벗어난 도망 %lld번 쫓긴 %.1f초 | %s | ")
				   TEXT("누적 시작 %lld · 끝 %lld · 열린 %lld · 스스로 벗어남 %lld (%.1f%%) 쫓긴 %.1f초 · 은신처 원 안에서 끝 %lld · 반사 스텝 %lld/%lld · ")
					   TEXT("쫓긴 도망 %lld 중 숨음 %lld (지켜보는 중 %lld) · 숨은 뒤 10초 안 잡힘 %lld·굶음 %lld · ")
						   TEXT("쫓긴 사건 %lld 중 숨음 %lld (지켜보는 중 %lld) · 잡힘 %lld · 굶음 %lld · 잘림 %lld · 이어진 도망 %lld | 두뇌 판 (교체 %d번): %s"),
			   *Ctx.RegionId.ToString(), Seconds, static_cast<long long>(Iv.Started), static_cast<long long>(Iv.Ended), *Causes, Iv.MeanSeconds(),
			   static_cast<long long>(Iv.OwnN()), Iv.OwnChaseSeconds(), *EcoV3Flight::SummaryText(Ctx.FlightTally.Window()),
			   static_cast<long long>(Tot.Started), static_cast<long long>(TotEnded), static_cast<long long>(Tot.Num[EcoWorldV3::kFlightTruncated]),
			   static_cast<long long>(Tot.OwnN), TotEnded > 0 ? 100.0 * static_cast<double>(Tot.OwnN) / static_cast<double>(TotEnded) : 0.0,
			   Tot.OwnN > 0 ? static_cast<double>(Tot.OwnContact) * EcoRepertoireV3::kStepSeconds / static_cast<double>(Tot.OwnN) : 0.0,
			   static_cast<long long>(Tot.ShelterEnd), static_cast<long long>(Tot.ReflexSteps), static_cast<long long>(Tot.FleeSteps),
			   static_cast<long long>(Tot.Chased), static_cast<long long>(Tot.Hidden), static_cast<long long>(Tot.Watching),
			   static_cast<long long>(Tot.CoverCaught), static_cast<long long>(Tot.CoverStarved), static_cast<long long>(Tot.EpChased),
			   static_cast<long long>(Tot.EpHidden), static_cast<long long>(Tot.EpWatching), static_cast<long long>(Tot.EpCaught),
			   static_cast<long long>(Tot.EpStarved), static_cast<long long>(Tot.EpTruncated), static_cast<long long>(Tot.EpJoined), Ctx.FlightTally.Swaps,
			   *EcoV3Flight::CompareText(Ctx.FlightTally));
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

FString UEcoPolicyV3IntegratedSubsystem::CaptureStepPerformance() const
{
    auto J=MakeShared<FJsonObject>();auto Sorted=StepBatchMilliseconds,Equivalent=StepEquivalentMilliseconds;Sorted.Sort();Equivalent.Sort();
    const auto Memory=FPlatformMemory::GetStats();J->SetNumberField(TEXT("samples"),Sorted.Num());
    if(!Sorted.IsEmpty()){
        const int32 K=FMath::Clamp(FMath::CeilToInt(Sorted.Num()*.95)-1,0,Sorted.Num()-1);
        J->SetNumberField(TEXT("native_batch_p95_ms"),Sorted[K]);J->SetNumberField(TEXT("native_batch_max_ms"),Sorted.Last());
        J->SetNumberField(TEXT("native_step_equivalent_p95_ms"),Equivalent[K]);
    }
    J->SetNumberField(TEXT("native_steps_total"),double(StepCpuSteps));J->SetNumberField(TEXT("native_cpu_total_ms"),StepCpuSeconds*1000);
    J->SetNumberField(TEXT("process_used_physical_bytes"),double(Memory.UsedPhysical));J->SetNumberField(TEXT("process_peak_physical_bytes"),double(Memory.PeakUsedPhysical));
    J->SetBoolField(TEXT("client"),GetWorld()->GetNetMode()==NM_Client);J->SetNumberField(TEXT("contexts"),NumContexts());
    if(auto* Driver=GetWorld()->GetNetDriver()){
        Driver->LockNetDriverStats(false);
        J->SetNumberField(TEXT("net_received_total_bytes"),Driver->InTotalBytes);J->SetNumberField(TEXT("net_sent_total_bytes"),Driver->OutTotalBytes);
        J->SetNumberField(TEXT("net_received_bytes_per_second"),Driver->InBytesPerSecond);J->SetNumberField(TEXT("net_sent_bytes_per_second"),Driver->OutBytesPerSecond);
        Driver->UnlockNetDriverStats(false);
    }
    FString Out;FJsonSerializer::Serialize(J,TJsonWriterFactory<>::Create(&Out));return Out;
}

bool UEcoPolicyV3IntegratedSubsystem::TraceMove(FName RegionId, const FVector& FromCm, const FVector& ToCm, double& OutZ, bool bTraveling, float BodyRadiusCm) const
{
	OutZ = FMath::IsFinite(FromCm.Z) ? FromCm.Z : 0;
	UWorld* World = GetWorld();
	if (!World || FromCm.ContainsNaN() || ToCm.ContainsNaN()||!FMath::IsFinite(BodyRadiusCm)||BodyRadiusCm<20||BodyRadiusCm>40)
	{
		return false;
	}
	const double Dist = FVector::Dist2D(FromCm, ToCm);
	// Bound public route/step sweeps before float-to-int conversion or World queries.
	if (!FMath::IsFinite(Dist) || Dist > 1024 * EcoPolicyV3IntegratedImpl::kSubStepCm) return false;
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
		if (!EcoCreatureMovement::ConstrainStep(*World, RegionId, bTraveling, Cur, Next, BodyRadiusCm))
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
			if (C.Radius > 0.0 && Ctx.Sim.Config.ShelterWolfMargin > 0.0)
			{
				// 늑대 몸 여유 둘레 (10-17): 늑대 중심은 이 원 밖에 머문다 (가는 선)
				const float Rw = static_cast<float>((C.Radius + Ctx.Sim.Config.ShelterWolfMargin) * EcoRepertoireV3::kUnitCm);
				DrawDebugCircle(World, P, Rw, 48, FColor(60, 60, 90), false, -1.0f, 0, 3.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
			}
		}
		// 야생 2단계 3 세로 장애물 원판 (갈색 = 나무·바위 둘레, 옅은 선 = 몸 여유 둘레 — 사슴·늑대 중심이 들지 않는 원). 가져온 원판(측정 전용)은 주황,
		// 무대 나무 줄기 원판(10-17 실행 중 나무·10-18 레벨 나무 줄기 막이)은 초록
		{
			const EcoWorldV3::FObstacleConfig& Ob = Ctx.Sim.Config.Obstacles;
			const FColor ObColor = Ctx.bObstaclesImported ? FColor(230, 140, 40) : FColor(120, 80, 40);
			for (int32 k = 0; Ob.bEnabled && k < Ob.Num(); ++k)
			{
				const double Z = Ctx.ObstacleGroundZ.IsValidIndex(k) ? Ctx.ObstacleGroundZ[k] : Ctx.OriginCm.Z;
				const FVector P = Ctx.UnitsToCm(Ob.Discs[3 * k], Ob.Discs[3 * k + 1], Z + 40.0);
				const float R = static_cast<float>(Ob.Discs[3 * k + 2] * EcoRepertoireV3::kUnitCm);
				const bool bTree = Ctx.ObstacleIsTree.IsValidIndex(k) && Ctx.ObstacleIsTree[k] != 0;
				DrawDebugCircle(World, P, R, 16, bTree ? FColor(60, 200, 80) : ObColor, false, -1.0f, 0, 6.0f, FVector(1, 0, 0), FVector(0, 1, 0), false);
				DrawDebugCircle(World, P, R + static_cast<float>(Ob.BodyR * EcoRepertoireV3::kUnitCm), 16, FColor(90, 70, 50), false, -1.0f, 0, 1.5f,
								FVector(1, 0, 0), FVector(0, 1, 0), false);
			}
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
		// 지역 날씨 (10-18): 첫 줄 낮밤 옆에 '비 1.00' (끄거나 맑으면 '맑음')
		const FString WxTag = Ctx.Sim.Config.Weather.bEnabled && Ctx.Sim.WeatherKind != EcoWorldV3::kWeatherClear
								  ? FString::Printf(TEXT(" %s %.2f"), UTF8_TO_TCHAR(EcoWorldV3::WeatherNameKoUtf8(Ctx.Sim.WeatherKind)), Ctx.Sim.WeatherIntensity)
								  : FString(TEXT(" 맑음"));
		// 두뇌 (10-18 두뇌 바꾸기): 내장이면 'R1b−F'(얼기 막음)·'R1b', 파일 두뇌면 모델 이름. 바뀐 뒤 늑대를 알 때 숨기 몫 (FEcoV3BrainTally)
		const FEcoV3Brain& Brain = GetActiveBrain();
		// 10-24 두 길 두뇌면 '두뇌 <이름> 두 길' (판 5 는 '두 길·반사 밖 도망 막음')
		const FString BrainTag = Brain.bBuiltin ? FString(Ctx.Sim.Allowed[EcoRepertoireV3::kFreeze] == 0 ? TEXT("R1b−F") : TEXT("R1b"))
												: FString::Printf(TEXT("두뇌 %s%s"), *Brain.ModelName,
																  Ctx.RouteOn() ? (Ctx.Sim.bFleeGate ? TEXT(" 두 길·반사 밖 도망 막음") : TEXT(" 두 길")) : TEXT(""));
		const FEcoV3BrainTally& Since = Ctx.SinceSwapBrainTally;
		const int64 KnowN = Since.KnowTotal();
		const FString Line = FString::Printf(TEXT("v3 %s %s | %s%s d=%.2f | 사슴 %d/%d:%s | 늑대%s | 포획 %lld 굶음 %lld | 이 두뇌로 늑대를 알 때 숨기 %.1f%% (%lld 스텝)"),
											 *BrainTag, *Ctx.RegionId.ToString(), Ctx.Sim.Dark >= 0.5 ? TEXT("밤") : TEXT("낮"), *WxTag, Ctx.Sim.Dark,
											 Ctx.AliveDeer, Ctx.AdoptedDeer, *Tally, *Wolves,
											 static_cast<long long>(Ctx.Sim.Stats.Caught), static_cast<long long>(Ctx.Sim.Stats.Starved),
											 KnowN > 0 ? 100.0 * static_cast<double>(Since.KnowSteps[EcoRepertoireV3::kHide]) / static_cast<double>(KnowN) : 0.0,
											 static_cast<long long>(KnowN));
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
		// 셋째 줄: 야생 (w3) 도망 기록 (10-21, 도망 기록을 세는 세계만 — EcoV3FlightTally.h): 최근 60 초 창과 두뇌 판 비교 (쫓긴 = 스스로 벗어난 도망의 쫓긴
		// 시간, 10-24 쫓긴 사건 중 숨음·잡힘 = 관문 1차 사건 숨음 비율·지킴 GH 와 같은 몫 — 닫힌 사건)
		const FString FlightLine = Ctx.FlightOn() ? FString::Printf(TEXT("도망 %s | %s | %s"), *Ctx.RegionId.ToString(),
																	 *EcoV3Flight::SummaryText(Ctx.FlightTally.Window()),
																	 *EcoV3Flight::CompareText(Ctx.FlightTally))
												  : FString();
		// 넷째 줄: 10-24 두 길 두뇌 (이식 계획서 8-3 — 길을 켠 세계만): 최근 60 초 실행한 반사 길 몫·길 결정·은신처 고름·무효, 사슴 머리 위 글자는
		// '도주(트인 쪽)'(연노랑)·'도주(은신처)'(하늘색) — EcoV3Integrated::DeerLabel
		const FString RouteLine = Ctx.RouteOn() ? FString::Printf(TEXT("길 %s | 최근 %.0f초: %s | 지금 도주 트인 쪽 %d · 은신처 %d"), *Ctx.RegionId.ToString(),
																   static_cast<double>(Ctx.RouteTally.WindowSteps()) * EcoRepertoireV3::kStepSeconds,
																   *Ctx.RouteTally.Window().Text(), Ctx.RouteNow[0], Ctx.RouteNow[1])
												: FString();
		DrawDebugString(World, Center + FVector(0, 0, 600.0),
						Line + TEXT("\n") + FoodLine + (FlightLine.IsEmpty() ? FString() : TEXT("\n") + FlightLine) + (RouteLine.IsEmpty() ? FString() : TEXT("\n") + RouteLine),
						nullptr, FColor::White, 0.0f, true, 1.4f);
		if (bScreen)
		{
			GEngine->AddOnScreenDebugMessage(static_cast<uint64>(730000 + Ctx.Index), 1.5f, FColor(180, 230, 180), Line);
			GEngine->AddOnScreenDebugMessage(static_cast<uint64>(731000 + Ctx.Index), 1.5f, FColor(230, 210, 150), FoodLine);
			if (!FlightLine.IsEmpty())
			{
				// 키 733000 + 지역 (732000~732004 는 두뇌 알림·상태 줄)
				GEngine->AddOnScreenDebugMessage(static_cast<uint64>(733000 + Ctx.Index), 1.5f, FColor(255, 190, 140), FlightLine);
			}
			if (!RouteLine.IsEmpty())
			{
				GEngine->AddOnScreenDebugMessage(static_cast<uint64>(734000 + Ctx.Index), 1.5f, FColor(140, 225, 255), RouteLine);
			}
		}
	}
}

// -----------------------------------------------------------------------------
// 실시간 두뇌 교체 화면 (10-21, LIVE_ADAPT_SPEC.md 5.4 — eco.V3Debug 와 따로)
// -----------------------------------------------------------------------------

void UEcoPolicyV3IntegratedSubsystem::PostNotice(EcoV3Integrated::ENotice Kind, const FString& Text)
{
	using namespace EcoPolicyV3IntegratedImpl;
	using EcoV3Integrated::ENotice;
	// 기록은 늘 (헤드리스 실행의 증거)
	UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 알림 | %s"), *Text);
	const UWorld* World = GetWorld();
	if (!EcoV3Brain::NoticeEnabled() || !GEngine || !FApp::CanEverRender() || (World && World->GetNetMode() == NM_Client))
	{
		return;
	}
	uint64 Key = kNoticeKeyBrain;
	float Seconds = 10.0f;
	FColor Color(120, 255, 140);
	double Scale = 1.6;
	switch (Kind)
	{
	case ENotice::Swap:
		break;
	case ENotice::Rollback:
		Color = FColor(255, 210, 90);
		break;
	case ENotice::Reject:
		Key = kNoticeKeyReject;
		Seconds = 8.0f;
		Color = FColor(255, 110, 90);
		Scale = 1.3;
		break;
	case ENotice::Env:
		Key = kNoticeKeyEnv;
		Seconds = 8.0f;
		Color = FColor(140, 200, 255);
		Scale = 1.3;
		break;
	case ENotice::Snapshot:
		Key = kNoticeKeySnapshot;
		Seconds = 6.0f;
		Color = FColor(200, 200, 255);
		Scale = 1.2;
		break;
	}
	GEngine->AddOnScreenDebugMessage(Key, Seconds, Color, Text, /*bNewerOnTop*/ true, FVector2D(Scale, Scale));
	if ((Kind == ENotice::Swap || Kind == ENotice::Rollback) && EcoV3Brain::NoticeShot())
	{
		// 시연 증거: 알림이 그려진 뒤 (DrawBrainNotices 가 찍는다)
		PendingShotAt = FPlatformTime::Seconds() + kNoticeShotDelaySeconds;
		PendingShotPath = FPaths::ConvertRelativePathToFull(
			FPaths::ProjectSavedDir() / TEXT("EcoAdapt/shots")
			/ FString::Printf(TEXT("eco_v3_%s_%s_t%lld.png"), Kind == ENotice::Swap ? TEXT("swap") : TEXT("rollback"),
							  *FDateTime::Now().ToString(TEXT("%Y%m%d_%H%M%S")), static_cast<long long>(GlobalT)));
	}
}

void UEcoPolicyV3IntegratedSubsystem::DrawBrainNotices()
{
	using namespace EcoPolicyV3IntegratedImpl;
	FEcoV3BrainRegistry& Reg = FEcoV3BrainRegistry::Get();
	const double Now = FPlatformTime::Seconds();
	// 적응 고리 상태 파일 (2 초마다 — 그릴 수 없는 실행도 읽는다): 상태·시도·판·지난 결과가 바뀌면 기록 한 줄
	if (Reg.PollStatus(Now))
	{
		const FEcoV3LiveStatus& S = Reg.GetLiveStatus();
		const FString Key = S.bValid ? FString::Printf(TEXT("%s|%d|%d|%s"), *S.State, S.Attempt, S.Round, *S.LastResult) : FString(TEXT("-"));
		if (Key != LastLiveStatusKey)
		{
			LastLiveStatusKey = Key;
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] %s%s"), *Reg.GetLiveStatusText(EcoV3Brain::NowUnixSeconds()),
				   S.bValid ? *FString::Printf(TEXT(" (상태 %s · 시도 %d · 판 %d%s)"), *S.State, S.Attempt, S.Round,
											   S.LastResult.IsEmpty() ? TEXT("") : *FString::Printf(TEXT(" · 지난 결과 %s"), *S.LastResult))
							: TEXT(""));
		}
	}
	const bool bCanDraw = EcoV3Brain::NoticeEnabled() && GEngine && FApp::CanEverRender();
	// 미뤄 둔 화면 찍기 (eco.V3Brain.NoticeShot — 바꾸기·되돌리기 알림 1.5 초 뒤, 게임 화면만)
	if (PendingShotAt >= 0.0 && Now >= PendingShotAt)
	{
		PendingShotAt = -1.0;
		if (bCanDraw && !PendingShotPath.IsEmpty())
		{
			IFileManager::Get().MakeDirectory(*FPaths::GetPath(PendingShotPath), /*Tree*/ true);
			FScreenshotRequest::RequestScreenshot(PendingShotPath, /*bInShowUI*/ true, /*bAddFilenameSuffix*/ false, /*bHdrScreenshot*/ false, FIntRect(),
												  /*bInRestrictToGameViewport*/ true);
			UE_LOG(LogEcoPolicyV3I, Log, TEXT("[EcoV3I] 화면 찍기 | %s"), *PendingShotPath);
		}
	}
	// 상태 줄 (1 초마다, AutoAdapt 이거나 감시 폴더가 켜졌을 때만): '두뇌 판 3 (live_r3…@abcd) · 교체 3번 · 환경 #2 · 적응 고리 | <파이썬 상태>'
	if (!bCanDraw || Now < NextNoticeLine)
	{
		return;
	}
	NextNoticeLine = Now + 1.0;
	if (!IsAutoAdaptEnabled() && Reg.EffectiveWatchFolder().IsEmpty())
	{
		return;
	}
	const FEcoV3Brain& B = GetActiveBrain();
	const FString Round = B.RoundTag();
	FString Line = B.bBuiltin	   ? FString::Printf(TEXT("두뇌 판 0 (내장 %s)"), Settings.bNoFreeze ? TEXT("R1b−F") : TEXT("R1b"))
				   : Round.IsEmpty() ? FString::Printf(TEXT("두뇌 %s"), *B.ShortId())
									 : FString::Printf(TEXT("두뇌 %s (%s)"), *Round, *B.ShortId());
	if (B.bRoute())
	{
		// 10-24 두 길 두뇌 (이식 계획서 8-3): 판과 모든 지역 최근 60 초 길 요약
		FEcoV3RouteSum Win;
		for (const TUniquePtr<FEcoV3RegionContext>& Ctx : Contexts)
		{
			if (Ctx && Ctx->RouteOn())
			{
				Win = Win.Plus(Ctx->RouteTally.Window());
			}
		}
		Line += FString::Printf(TEXT(" · 두 길(마스크 판 %d) %s"), B.MaskVersion, *Win.Text());
	}
	Line += FString::Printf(TEXT(" · 교체 %d번 · 환경 #%d"), BrainSwapsThisPlay, EnvRevision);
	const FString Live = Reg.GetLiveStatusText(EcoV3Brain::NowUnixSeconds());
	if (!Live.IsEmpty())
	{
		Line += TEXT(" · ") + Live;
	}
	// 도망 요약 (10-21 — 모든 지역 합: 최근 60 초 창 · 교체 전 → 지금. 10-24 부터 쫓긴 사건 중 숨음·잡힘 몫 — EcoV3FlightTally.h)
	const FString FlightText = FlightStatusText();
	if (!FlightText.IsEmpty())
	{
		Line += TEXT(" · ") + FlightText;
	}
	GEngine->AddOnScreenDebugMessage(kNoticeKeyStatus, 1.5f, FColor(200, 220, 255), Line);
}

FString UEcoPolicyV3IntegratedSubsystem::FlightStatusText() const
{
	EcoV3Flight::FSum WinSum;
	EcoV3Flight::FSum PrevSum;
	EcoV3Flight::FSum CurSum;
	bool bAny = false;
	bool bHasPrev = false;
	for (const TUniquePtr<FEcoV3RegionContext>& Ctx : Contexts)
	{
		if (!Ctx || !Ctx->FlightOn())
		{
			continue;
		}
		bAny = true;
		WinSum = WinSum.Plus(Ctx->FlightTally.Window());
		PrevSum = PrevSum.Plus(Ctx->FlightTally.PrevGen);
		CurSum = CurSum.Plus(Ctx->FlightTally.CurrentGen());
		bHasPrev = bHasPrev || Ctx->FlightTally.bHasPrev;
	}
	return bAny ? FString::Printf(TEXT("%s · %s"), *EcoV3Flight::SummaryText(WinSum), *EcoV3Flight::CompareText(PrevSum, CurSum, bHasPrev)) : FString();
}

FString FEcoV3RouteSum::Text() const
{
	// 10-24 두 길 두뇌 화면·기록 글자 (FEcoV3RouteSum 머리 주석)
	const int64 Steps = RouteSteps();
	const FString StepsText = Steps > 0 ? FString::Printf(TEXT("길 RUN %.0f%% · 은신처 %.0f%% (반사 사슴-스텝 %lld)"),
														   100.0 * static_cast<double>(RunSteps) / static_cast<double>(Steps),
														   100.0 * static_cast<double>(ShelterSteps) / static_cast<double>(Steps), static_cast<long long>(Steps))
										: FString(TEXT("길 반사 스텝 없음"));
	return FString::Printf(TEXT("%s · 길 결정 %lld · 은신처 고름 %lld/%lld (열린 결정) · 무효 %lld"), *StepsText, static_cast<long long>(Decisions),
						   static_cast<long long>(PickedShelter), static_cast<long long>(Choice), static_cast<long long>(Invalid));
}

void UEcoPolicyV3IntegratedSubsystem::RejectResourceContract()
{
    Deactivate(TEXT("Resource conservation receipt rejected"));
    if(auto* Coordinator=Spawner.Get())Coordinator->FailRuntime(TEXT("V3 spatial resource contract rejected"));
}

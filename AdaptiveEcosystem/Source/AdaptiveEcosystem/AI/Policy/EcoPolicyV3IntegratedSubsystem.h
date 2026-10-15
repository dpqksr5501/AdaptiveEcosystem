// 팀 통합 레벨을 v3 R1b 두뇌로 돌리는 서비스 — "몸은 팀 것, 머리만 우리 것" (계획서 RL_V3_UNREAL_TRAINING_PLAN.md 4-5b).
//
// 스위치 (기본 끔. 끄면 아무것도 바꾸지 않는다 — 팀 레벨은 지금처럼 v1 + Social + 팀 늑대로 돈다):
//   편집기 콘솔에서 Play 전에  eco.IntegratedPolicyVersion 3     (1 = 끔, 기본)
//   명령줄                     -EcoIntegratedV3                   (헤드리스·독립형 게임 실행용)
//   명령줄 값은 콘솔 변수의 시작값(ECVF_SetByCommandline)으로만 들어간다. 그래서 콘솔에서 eco.IntegratedPolicyVersion 1 을 넣으면
//   명령줄이 있어도 꺼진다(-EcoV3Debug·-EcoV3Seed=·-EcoV3DeerPerRegion= 도 같다).
//   통합된 권위 경로는 Standalone / Listen / Dedicated Server 에서 실행한다. Client 는 같은 경로/GUID의 canonical
//   transient EntityConfig만 등록하고 논리 스텝은 실행하지 않는다. Bubble DTO로 표현만 수신한다.
//   편집기 콘솔 값은 별도 Standalone 프로세스로 전달되지 않으므로 추가 실행 인수에 -EcoIntegratedV3 를 넣는다.
//
// 맡는 것 (서버·단독만, AGENTS.md 2절 2항. 복제 통로가 아니다 — 2절 6항):
//   1. OnWorldBeginPlay (액터 BeginPlay 앞, UE 5.8 UWorld::BeginPlay): 팀 조정자 AEcoCreatureIntegrationSpawner 의 공개 속성만 바꾼다.
//      저장된 레벨은 그대로다(PIE 월드는 사본). 바꾸는 것: HerbivoreConfig·WolfConfig → UEcoCreatureV3Trait 설정, 이주 끔, 웨이브 끔,
//      1초 에너지 소모·섭식 에너지 0 (에너지 주인은 v3), 낮밤 60 + 60초, 개체 상한, 지역마다 사슴 수·늑대 2·시작 자리.
//      모든 그룹의 계획·설정 생성·GUID 검사가 다 통과한 뒤에만 한꺼번에 쓴다 — 하나라도 실패하면 조정자를 하나도 건드리지 않는다.
//      바꾸기 전 팀 값은 따로 쥐어 둔다(시작 직전 검사가 실패하면 되돌린다).
//   2. 시작 자리 지면 검사 (팀 공개 함수 EcoCreatureMovement::ProjectSpawnPoint — 지면·경사·장애물·물):
//      - 스트리밍 없는 조정자: BeginPlay 안에서 바로 시작하므로 OnWorldBeginPlay 의 검사가 조정자가 볼 지형과 같다.
//      - 서식지 스트리밍 조정자: OnWorldBeginPlay 의 계획은 힌트일 뿐이다(지형이 덜 왔다). 조정자와 같은 조건(BeginPlay 뒤 0.25 초 이상 +
//        스트리밍 원천 완료)이 된 프레임에, 엔진 스트리밍 갱신(UWorld::Tick 의 InternalUpdateStreamingState) 뒤·조정자 OnWorldPostActorTick
//        앞인 TG_LastDemotable 틱에서 다시 검사해 덮어쓴다. 그래서 조정자 StartAuthority 와 같은 지형을 본다. 검사는 많아야 3 번이다.
//        못 채우면 팀 값으로 되돌리고 통합 모드를 끈다. 사슴은 절반(최소 4) 넘게 찾고 늑대를 다 찾으면 그 수로 시작한다.
//      - 조정자가 31 초 안에 시작하지 못하면(조정자 시간 초과 30 초) 오류 한 줄을 남기고 통합 모드를 끈다 (매 프레임 다시 검사하지 않는다).
//   3. 조정자가 개체를 만든 다음 프레임 앞: 지역마다 무대(학습 크기 한 변 120~220 m 정사각, 먹이 자리 중심, 지역 상자 안)와 v3 세계
//      (EcoWorldV3::FWorldState) 를 만든다. 은신처 원 = 레벨의 UEcoShelterSubsystem 은신처 중 무대 안이고 반경이 학습 범위(4~9 단위 =
//      8~18 m)인 것 + 우리가 실행 중에 놓는 AEcoShelterAnchor 4개(반경 = 무대 한 변의 0.1 배를 4~9 단위로 자름 — 넓이 8.4~12.6%,
//      학습 5~30%). 학습 범위 밖 레벨 은신처는 v3 원 목록에서만 뺀다(팀 Social 등록은 그대로). 목록은 RuntimeIndex 순으로 고정한다.
//   4. 전역 결정 시계 하나 (7.5 Hz, 평면 시험 경로의 시계·세션과 따로) 와 전역 스텝 t. t 는 팀 UEcoWorldClockSubsystem 시각에 맞춰
//      시작한다(낮 시작 = 스텝 0, 60 초 = 450 스텝). 어둠은 t 에서 계산한다(계약 7-6). 어긋남이 4 스텝을 넘으면 다시 맞춘다.
//   5. 기록 [EcoV3I] (지역마다 10 초) 와 디버그 표시 (콘솔 변수 eco.V3Debug 1). 산 사슴 밀도가 학습 하한(128 / 110² 마리/단위²) 아래로
//      내려가면 지역마다 경고 한 줄을 남긴다 (부활이 없어서 생기는 근사).
//      먹기 되먹임: 사슴 글자 = 행동 + 에너지 % (+ 이번 결정 스텝에 먹은 몫, 굶주림, 번식), 지역 집계 둘째 줄 = 무대 먹이 처음 대비 %·
//      최근 10 초 먹은 양·에너지 평균·굶주림 수. 기록 줄에는 구간 먹은 양·먹은 사슴 수·먹기 중 실제로 먹은 비율·무대 먹이 %·에너지 평균.
//      먹이는 v3 먹이 격자만 바뀐다 — 팀 지역 FoodAmount 에는 쓰지 않는다 (FEcoV3RegionContext 섭식 칸 설명).
//   6. 늑대 밤잠 점진화 (사람 결정 H1 10-14, 콘솔 변수 eco.IntegratedV3.GradualNight 기본 1 — Play 전에 바꾼다):
//      파이썬 configs/v3_real1_night_on.yaml 의 realism_night 를 엔진 무관 위협 모델로 옮긴 것(EcoThreatModel.h bRealismNight)을 켠다.
//      늑대는 해가 진 뒤 늑대마다 다른 지연(0~22 스텝, H(606, 세션 시드, StableAgentId))이 지나고, 사냥 중이 아니고, 16 m(8 단위) 안에 사슴이 없을 때 2 초 동안 걸음을
//      늦추다 눕는다. 그동안 사냥이 시작되거나 사슴이 다가오면 다시 일어난다. 깜깜하면(d = 1) 새 사냥을 시작하지 않고 쫓던 사냥만 마저
//      끝낸다. 새벽에는 하나씩 깨어 2 초에 걸쳐 걸음을 올린다. 해 진 뒤 깨어 있는 늑대의 속력 하한은 0.5 배다.
//      R1b 두뇌는 그대로다(관측 18·마스크 판 2). 학습 세계 밖 규칙이지만 R1b 측정(results/v3/real1)으로 허용했다(R3 명세 H1).
//      화면: 늑대 글자 '눕는 중'·'깨는 중' + 걸음 %, 사슴이 가까워·사냥 중이라 못 누우면 그 까닭. 기록: 잠듦·깸·눕기 시작·다시 일어남
//      한 줄씩(해 진 뒤 초, 가장 가까운 사슴 m), 10 초 줄에 밤잠 집계. 0 으로 두면 지금까지처럼 d ≥ 0.5 가 되는 순간 곧바로 잔다.
//   7. 사슴 얼기 막음 (사람 결정 10-15 (A) '지금 바로 없앰', 콘솔 변수 eco.IntegratedV3.NoFreeze 기본 1 — Play 전에 바꾼다):
//      세계 허용 칸(EcoWorldV3 FWorldConfig::WorldAllowed)의 FREEZE 를 0 으로 둔다. 실제 허용 = R1b 모델 허용 ∧ 세계 칸이라 마스크가
//      FREEZE 를 늘 막는다(파이썬 rep_policy.effective_allowed 와 같은 꼴 = R1b−F). 가중치는 그대로다 — R1b 가 얼던 자리에서는 R1b 의
//      다음 선호 행동이 나온다(R3 재학습 전 측정: 대부분 먹기 78%·도망 17%). 화면 'v3 R1b−F', 사슴 집계 '얼기(막힘) 0', 기록 줄에
//      '얼기 막힘: 실행 n · 얼기 칸이 열린 결정 n' (늘 0 이어야 한다). 0 으로 두면 R1b 그대로 얼기를 쓴다.
//   8. 늑대 식사 시간 (사람 결정 10-15 (B) '먹는 시간 주기 (약 5초)', 콘솔 변수 eco.IntegratedV3.WolfEatSeconds 기본 5 — Play 전에 바꾼다):
//      잡은 늑대는 시체 곁에 서서 약 5 초 먹고, 끝나면 곧바로 다시 사냥한다(포만 없음 — 늑대는 과식하게 둔다). 결정 스텝으로
//      5 ÷ (2/15 초) = 37.5 → 반올림 38 스텝(5.07 초)이고, 위협 설정의 식사 쿨다운(FThreatConfig::PredEatCd, 학습 5)을 38 로 바꾸고
//      식사 동안 서 있게(bEatInPlace) 한다. 0.67 이하(5 스텝 이하)는 옛 규칙 그대로다(학습 세계와 같다: 5 스텝 = 0.67 초, 그동안 배회).
//      파이썬 R3 세계의 같은 규칙은 overrides.pred_eat_cd 38 + features.threats.eat_in_place 다(같은 스텝 수·같은 제자리 꼴).
//      팀 표현은 '먹는 중' 깃발(FEcoPredatorStateFragment::EatCooldown > 0)과 속도 0 이면 '먹는 중' 동작을 보인다 — 기록 줄이
//      팀 늑대 표현 액터의 동작을 프레임마다 세어 확인한다. 화면: 늑대 글자 '늑대 식사 n초'(남은 초), 지역 집계 '늑대 식사 5초 제자리'.
//      기록 줄: 구간 포획·식사 중 늑대·스텝(그중 움직임)·돌진(앞 포획 뒤 3 초 안 = 이어 사냥, 식사 끝 뒤 3 초 안)·늑대별 포획 누적.
//      R1b 학습 세계 밖 규칙이다 — 파이썬 측정(R1b−F, v3_r1_on·v3_real1_night_on, 보정 시드 20000~20019)에서 사망이 줄고 G_γ 가
//      올라 허용했다(계획서 4-5b).
//   9. 사슴 도주 반사 거리 (사람 결정 10-15 (7) 야생 1단계 w3, 콘솔 변수 eco.IntegratedV3.WildFlight 기본 1 — Play 전에 바꾼다. 명령줄
//      -EcoV3WildFlight= 는 시작값, 옛 이름 -EcoV3KeepAway= 도 받는다): 두뇌 위의 세계 규칙 (EcoWorldV3.h '야생 1단계 (w3)', FWildFlightConfig).
//      10-15 (C) 의 경계 거리 실험 KeepAway(콘솔 변수 eco.IntegratedV3.KeepAway)는 이 규칙으로 바꾸고 지웠다 — 옛 동작은 남기지 않았다.
//      사냥 중인 늑대(먹는·배부른·자는 늑대 빼고)를 실제로 알아채면(시야·발소리) eco.IntegratedV3.AlertDistM(30 m) 안에서 '경계' — 두뇌가
//      먹기면 걸으며 먹고 늑대 반대쪽으로 멀어진다. eco.IntegratedV3.PanicDistM(15 m) 안이거나 다가오면 '도주' — 사냥 중인 늑대가 모두
//      eco.IntegratedV3.SafeDistM(40 m) 밖이 될 때까지 뛰고, 반대쪽 ±60°·30 m 안 은신처가 있으면 그쪽으로. 은신처 안이면 웅크린다.
//      먹는·쉬는 늑대는 경계만 일으킨다. 기록 셋째 줄 '경계 거리'(이름 그대로): 경계·도주·웅크림 시작, 끝난 도주의 평균 길이, 잡힌 사슴을
//      덮기로 가른 수, 식사 중 늑대 15 m 안 사슴. 0 으로 두면 지금과 비트 단위로 같다 (세계 칸이 모두 기본값).
//  10. 야생 1단계 (사람 결정 10-15 (7) '바뀐 규칙을 언리얼에서 보이게', 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md, 값 = 파이썬
//      configs/v3_wild1_mirror.yaml, 하루 900 스텝). 규칙마다 콘솔 변수 하나(기본 1 — Play 를 누르면 보인다. Play 전에 바꾼다)와 명령줄 시작값:
//      지방 비축 eco.IntegratedV3.WildReserve (-EcoV3WildReserve=, EcoWorldV3.h FWildReserveConfig): 배가 비어도 비축으로 3일(6분) 버티고
//      배·비축 모두 0 이어야 굶어 죽는다. 배 10% 밑이면 0.75 배 느리다. 비축으로 사는 사슴의 Vitals 에너지 거울은 아주 작은 양수라 팀 HP 감소가
//      먼저 죽이지 않는다 (죽음은 v3 DeathCause 한 길). 화면: 사슴 글자 '배고픔 비축 63%'·'비축 바닥'·'약함(느림)', 지역 둘째 줄 비축 평균·
//      비축으로 사는 사슴. 기록 넷째 줄 '<지역> 야생 |': 꺼내 씀·채움·약한 개체·스텝·약한 채로 잡힘·지금 비축 평균·최소 (앞 세 줄은 그대로).
//      늑대 포만 eco.IntegratedV3.WildSatiation (-EcoV3WildSatiation=, EcoThreatModel.h FThreatConfig::bWildSatiation): 먹기(5초)가 끝나면
//      반나절(450 스텝 = 60초) 사냥하지 않고 0.3 배 속력으로 어슬렁거린다. 자지 않는 한 사슴에게 보인다. 화면: 늑대 글자 '늑대 배부름·쉼 42초'.
//      기록 넷째 줄: 배불러 쉰·먹는 늑대·스텝 비율, 포만을 건 포획.
//      감지 eco.IntegratedV3.RealismVision (-EcoV3RealismVision=, 위협 시야 300° — 바로 뒤 60° 만 사각)·eco.IntegratedV3.RealismHearing
//      (-EcoV3RealismHearing=, 늑대 걸음이 빠를수록 멀리 들림 4~40 m, 어슬렁거리는 늑대는 4 m): R3 세계 값 그대로. 보임과 같은 칸이라
//      두뇌 관측(위협 수·거리·접근)·사건이 함께 바뀐다 (EcoObservationV3.h FHearingConfig·HearingRadius·ThreatFovCos).
//
// 실제 스텝·입양·화면은 EcoPolicyV3IntegratedProcessors 가 한다.

#pragma once

#include "CoreMinimal.h"
#include "Core/EcoMigrationTypes.h"
#include "Creature/Runtime/EcoCreatureIntegrationSpawner.h"
#include "Engine/EngineBaseTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "Templates/Function.h"
#include "Templates/UniquePtr.h"

#include "EcoPolicyClock.h"
#include "EcoWorldV3.h"

#include "EcoPolicyV3IntegratedSubsystem.generated.h"

class AEcologyRegion;
class AActor;
class UMassEntityConfigAsset;
class UEcoPolicyV3IntegratedSubsystem;

DECLARE_LOG_CATEGORY_EXTERN(LogEcoPolicyV3I, Log, All);

namespace EcoV3Integrated
{
	/** 늑대 화면·기록 상태 (학습 위협 상태에서 읽는다). */
	enum class EWolfState : uint8
	{
		Roam,      // 배회
		Stalk,     // 잠행 (잠행형이 표적을 보고 천천히 다가감)
		Pounce,    // 돌진
		Exhaust,   // 지침 (돌진 실패 뒤)
		Chase,     // 추격 (추격형이 표적을 봄)
		Eat,       // 식사 (포획 뒤 쿨다운)
		Sleep,     // 잠 (주행성. 밤잠 점진화를 끄면 어둠 0.5 이상, 켜면 늑대별 잠)
		Settle,    // 눕는 중 (밤잠 점진화: 걸음을 늦추는 2 초)
		Waking,    // 깨는 중 (밤잠 점진화: 깨어 걸음을 올리는 중, 또는 눕다가 다시 일어나는 중)
		Count
	};

	/**
	 * 굶주림 표시 선: 에너지 15% 아래. 걷는 먹기(대사 0.002/스텝)로 75 스텝 = 10 초, 서서 먹기로 약 14 초, 뛰면 4 초 안에 굶어 죽는 선이다.
	 * 표시·기록 전용 (규칙이 아니다).
	 */
	inline constexpr double kStarvingEnergy = 0.15;
	// 야생 (w1) 화면·기록: 비축이 이 밑이면 '비축 바닥 가까움' (글자 빨강·기록 줄 수)
	inline constexpr double kLowReserve = 0.25;
	/** '최근 10 초 먹은 양' 창 = 결정 스텝 75 개 (7.5 Hz × 10 초, 시뮬레이션 시간). */
	inline constexpr int32 kRecentEatSteps = 75;
	/** 번식 표시를 남기는 결정 스텝 수 (약 1.5 초). */
	inline constexpr int64 kReproMarkSteps = 11;
	/** 이어 사냥 창 = 결정 스텝 22 개 (3 초, R3 재학습 전 측정 results/v3/r3/pre 의 '이어 사냥'과 같은 창). */
	inline constexpr int64 kChainWindowSteps = 22;
	/** 기록 '식사 중 늑대 15 m 안 사슴'의 거리 (단위 7.5 = 15 m 고정 — 경계 거리 콘솔 변수와 무관하게 규칙 켬·끔을 견준다). 기록 전용. */
	inline constexpr double kNearEatingWolfUnits = 7.5;

	/**
	 * 늑대 상태 (화면·기록). Cfg 는 그 지역 세계의 위협 설정 (FWorldState::ThreatCfg) — 밤잠 점진화를 켠 세계만 눕는 중·깨는 중이 나온다.
	 * 우선순위: 잠 > 눕는 중 > 돌진·지침 > 식사 > 추격·잠행 > 깨는 중 > 배회.
	 */
	ADAPTIVEECOSYSTEM_API EWolfState WolfStateOf(const EcoWorldV3::FThreatAgent& Agent,
												 const EcoThreatV3::FThreatConfig& Cfg = EcoThreatV3::FThreatConfig());
	ADAPTIVEECOSYSTEM_API const TCHAR* WolfStateNameKo(EWolfState State);

	/**
	 * 늑대 머리 위 글자 (eco.V3Debug 1): '늑대 눕는 중 (추격형) 걸음 40%'. 밤잠 점진화를 켠 세계에서 깨어 있는 주행성 늑대가 이번 스텝에
	 * 누울 차례인데 못 누웠으면 ' · 사슴 곁이라 안 누움' / ' · 사냥 중이라 안 누움', 눕는 중이 아닌데 깜깜해 새 사냥을 안 하면 ' · 깜깜해 새 사냥 안 함'.
	 * 식사 중이면 '늑대 식사 3.2초 (잠행형)' — 남은 식사 = 쿨다운 × 결정 스텝 2/15 초 (0.1 초 단위).
	 */
	ADAPTIVEECOSYSTEM_API FString WolfLabel(const EcoWorldV3::FThreatAgent& Agent, const EcoThreatV3::FThreatConfig& Cfg, double Dark,
											FColor& OutColor);
	ADAPTIVEECOSYSTEM_API const TCHAR* BehaviorNameKo(int32 Behavior);

	/**
	 * 산 사슴 머리 위 글자와 색 (eco.V3Debug 1). '먹기 72%' = 행동 + 에너지 %. 이번 결정 스텝에 먹이 칸에서 실제로 먹었으면
	 * ' +3.0' (먹은 몫을 에너지 %p 로, 0.05 미만이면 '+' 만), 에너지 15% 아래면 ' 굶주림'(빨강), bRecentRepro 면 ' 번식'.
	 * 색은 행동 색 (먹기 초록·도망 노랑·숨기 파랑·얼기 흰색), 굶주림만 빨강.
	 * KeepMode = 이번 스텝의 도주 반사 덮기 (FHerbDecision::KeepActive): 행동 이름 대신 '경계(먹으며 멀어짐)'(주황, 두뇌가 먹기일 때만)·
	 * '도주(안전해질 때까지)'(진한 주황)·'웅크림(은신처·경계)'(파랑). 0 이면 지금 그대로.
	 * bReserveOn = 지방 비축을 켠 세계 (야생 w1): 에너지 15% 아래면 ' 굶주림' 대신 ' 배고픔 비축 63%'(빨강, 비축으로 버티는 중),
	 * 비축 0 이면 ' 비축 바닥', 배 10% 밑이면 ' 약함(느림)'. 배는 괜찮은데 비축이 25% 밑이면 ' 비축 20%'. 거짓이면 지금 그대로.
	 */
	ADAPTIVEECOSYSTEM_API FString DeerLabel(const EcoRepertoireV3::FRepState& Rep, const EcoWorldV3::FHerbBody& Body, bool bRecentRepro,
											FColor& OutColor, int32 KeepMode = EcoWorldV3::kKeepNone, bool bReserveOn = false);
	/** 도주 반사 덮기 이름 (기록·화면): 두뇌 / 경계(먹으며 멀어짐) / 도주(안전해질 때까지) / 웅크림(은신처·경계). */
	ADAPTIVEECOSYSTEM_API const TCHAR* KeepModeNameKo(int32 KeepMode);

	/** 지역 늑대 순번(StableAgentId 순) → 성질. 짝수 = 잠행-돌진형, 홀수 = 근접 추격형. 모두 주행성(밤에 잔다), 원거리형 없음. */
	ADAPTIVEECOSYSTEM_API EcoThreatV3::FThreatSpec WolfSpecForOrdinal(int32 Ordinal, double PredSpeedMult);
}

/** 통합 모드 설정 (콘솔 변수·명령줄에서 읽는다. 시험은 직접 채운다). */
struct ADAPTIVEECOSYSTEM_API FEcoV3IntegratedSettings
{
	/** 학습 사슴 수 N (configs/default.yaml, 부활로 늘 128). 학습 밀도 하한 = 이 값 ÷ 맵 한 변 최대(110 단위)². */
	static constexpr int32 kTrainDeer = 128;
	/** 학습 은신처 반경 범위 (단위, UEcoPolicyV3Subsystem::CheckTrainingRange 와 같다 — 8~18 m). */
	static constexpr double kCoverRadiusLoUnits = 4.0;
	static constexpr double kCoverRadiusHiUnits = 9.0;

	int64 Seed = 20000;                 // 세션 시드 (지연 해시 Seed·세계 난수·시작 자리 난수)
	int32 DeerPerRegion = kTrainDeer;   // 학습 N 과 같은 128 — 무대 60~110 단위 어디서나 시작 밀도가 학습 범위 안이고, 피식 EMA 분모도 학습과 같다.
										// 부활이 없어 줄기만 한다 (60 단위 무대는 사망 90 마리까지 학습 밀도 하한 위)
	int32 WolvesPerRegion = 2;          // 잠행 1 + 추격 1 (학습 보통 위협 2~12, 잠행 비율 30~70%)
	double StageSizeUnits = 60.0;       // 무대 한 변 (단위, 학습 60~110 = 120~220 m)
	double PredSpeedMult = 0.8;         // 늑대 속력 = 사슴 뛰기 900 cm/s × 0.8 = 720 cm/s (학습 0.6~0.95)
	bool bGradualNight = true;          // 늑대 밤잠 점진화 (eco.IntegratedV3.GradualNight 기본 1, 사람 결정 H1 10-14). 거짓 = d ≥ 0.5 에 곧바로 잠
	bool bNoFreeze = true;              // 사슴 얼기 막음 (eco.IntegratedV3.NoFreeze 기본 1, 사람 결정 10-15 (A)). 거짓 = R1b 그대로 얼기를 쓴다
	double WolfEatSeconds = 5.0;        // 늑대 식사 길이 (초, eco.IntegratedV3.WolfEatSeconds 기본 5, 사람 결정 10-15 (B)). 0.67 이하 = 옛 규칙
	bool bWildFlight = true;            // 사슴 도주 반사 거리 (eco.IntegratedV3.WildFlight 기본 1, 야생 w3 — 경계 거리 KeepAway 를 바꿨다). 거짓 = 두뇌 그대로
	double AlertDistM = 30.0;           // 경계 거리 alert_r (m, eco.IntegratedV3.AlertDistM) — 사냥 중인 늑대를 이 안에서 알아채면 먹으며 멀어진다
	double PanicDistM = 15.0;           // 도주 거리 flight_r (m, eco.IntegratedV3.PanicDistM) — 이 안이거나 다가오면 뛰어서 달아난다
	double SafeDistM = 40.0;            // 안전 거리 safe_r (m, eco.IntegratedV3.SafeDistM) — 사냥 중인 늑대가 모두 이 밖일 때까지 도주
	bool bWildReserve = true;           // 사슴 지방 비축 (eco.IntegratedV3.WildReserve 기본 1, 사람 결정 10-15 (7) 야생 1단계 w1). 거짓 = E 0 이면 곧바로 굶음
	bool bWildSatiation = true;         // 늑대 포만 (eco.IntegratedV3.WildSatiation 기본 1, 야생 w2). 거짓 = 식사가 끝나면 곧바로 사냥
	bool bRealismVision = true;         // 위협 시야 300° (eco.IntegratedV3.RealismVision 기본 1, R3 realism_vision). 거짓 = 앞쪽 120°
	bool bRealismHearing = true;        // 늑대 발소리 (eco.IntegratedV3.RealismHearing 기본 1, R3 realism_hearing). 거짓 = 소리 없음
	int32 ExtraCoverCount = 4;          // 우리가 놓는 은신처 수 (무대 1/4·3/4 지점)
	double ExtraCoverRadiusFrac = 0.1;  // 우리 은신처 반경 = 무대 한 변 × 이 값을 4~9 단위로 자름 (ExtraCoverRadiusUnits)
	double WolfStartCornerFrac = 0.4;   // 늑대 시작 = 무대 중심에서 (±한 변 × 이 값, ±한 변 × 이 값) 모서리 쪽. 사슴은 무대 전체 균등
	double WolfMinStartDistCm = 2800.0; // 늑대는 모든 사슴에게서 28 m 밖에서 시작 (늑대 시야 14 단위)
	double DeerMinSpacingCm = 150.0;    // 시작 자리끼리 최소 간격
	float LogIntervalSeconds = 10.0f;   // [EcoV3I] 지역 기록 주기 (시뮬레이션 초)

	/**
	 * 우리 은신처 반경 (단위). 무대 60 단위 = 6 단위(12 m, 4 개 넓이 12.6%), 110 단위 = 9 단위(18 m, 8.4%) — 무대 크기를 바꿔도 반경·넓이가
	 * 학습 범위(반경 4~9 단위, 넓이 5~30%) 안이다.
	 */
	double ExtraCoverRadiusUnits(double SizeUnits) const
	{
		return FMath::Clamp(ExtraCoverRadiusFrac * SizeUnits, kCoverRadiusLoUnits, kCoverRadiusHiUnits);
	}

	/** 학습 세계의 식사 쿨다운 (결정 스텝, configs/default.yaml pred_eat_cd 5 = 0.67 초 — 위협 설정 기본값). */
	static int32 TrainEatSteps() { return EcoThreatV3::FThreatConfig().PredEatCd; }

	/**
	 * 늑대 식사 길이 (결정 스텝) = 반올림(초 ÷ 2/15 초), 0.5 는 올린다. 학습 5 스텝 아래로 내리지 않고 900 스텝(2 분)에서 자른다.
	 * 5 초 = 37.5 → 38 스텝 (5.07 초), 0.67 초 = 5.025 → 5 스텝 (옛 규칙), 1 초 = 7.5 → 8 스텝.
	 */
	int32 WolfEatSteps() const
	{
		if (!FMath::IsFinite(WolfEatSeconds))
		{
			return TrainEatSteps();
		}
		const int32 Steps = FMath::FloorToInt32(WolfEatSeconds / EcoRepertoireV3::kStepSeconds + 0.5);
		return FMath::Clamp(Steps, TrainEatSteps(), 900);
	}

	/** 식사가 학습보다 긴가 (그때만 쿨다운을 바꾸고 식사 동안 세운다). 아니면 옛 규칙 그대로 (5 스텝, 그동안 배회 — 학습 세계·골든과 같다). */
	bool LongWolfEat() const { return WolfEatSteps() > TrainEatSteps(); }

	/**
	 * 도주 반사 거리의 세계 칸 (m → 단위 = m × 100 ÷ 200). 끄면 기본값(꺼짐) 그대로라 세계가 읽는 값이 바꾸기 전과 같다.
	 * 음수·수가 아닌 값은 기본값으로, 0 ~ 200 m 로 자르고, 안전 거리는 경계·도주 거리보다 작지 않게 올린다 (도주가 풀리자마자 다시 걸리지 않게).
	 * 나머지 계수(접근 0.9·경계 무게 1.5·은신처 ±60°/30 m·웅크림·벽 2 m)는 FWildFlightConfig 기본값 = configs/v3_wild1_mirror.yaml.
	 */
	EcoWorldV3::FWildFlightConfig WildFlightConfig() const
	{
		EcoWorldV3::FWildFlightConfig K;
		if (!bWildFlight)
		{
			return K;
		}
		auto Units = [](double M, double Def)
		{
			const double V = FMath::IsFinite(M) && M >= 0.0 ? FMath::Min(M, 200.0) : Def;
			return V * 100.0 / EcoRepertoireV3::kUnitCm;
		};
		K.bEnabled = true;
		K.AlertR = Units(AlertDistM, 30.0);
		K.FlightR = Units(PanicDistM, 15.0);
		K.SafeR = FMath::Max(Units(SafeDistM, 40.0), FMath::Max(K.AlertR, K.FlightR));
		return K;
	}

	/** 사슴 Deer 마리가 한 변 SizeUnits 무대에서 학습 밀도 하한(128 / 110² 마리/단위²) 아래인가. */
	static bool IsBelowTrainingDensity(int32 Deer, double SizeUnits)
	{
		const double MaxSide = 110.0;
		return SizeUnits > 0.0 && static_cast<double>(Deer) * MaxSide * MaxSide < static_cast<double>(kTrainDeer) * SizeUnits * SizeUnits;
	}

	/** 콘솔 변수 eco.IntegratedV3.* 에서 읽는다 (명령줄 -EcoV3Seed= -EcoV3DeerPerRegion= 은 그 콘솔 변수의 시작값이다). */
	static FEcoV3IntegratedSettings FromConsole();
};

/** 한 지역 무대 계획 (조정자 시작 전에 정한다). */
struct ADAPTIVEECOSYSTEM_API FEcoV3StagePlan
{
	FName RegionId;
	int32 GroupIndex = INDEX_NONE;
	FVector CenterCm = FVector::ZeroVector;   // 무대 중심 (Z = 높이 힌트)
	double SizeUnits = 60.0;
	TArray<FVector> DeerPoints;               // 사슴 시작 자리 (cm)
	TArray<FVector> WolfPoints;               // 늑대 시작 자리 (cm)
	int32 WantDeer = 0;                       // 계획한 수 (다시 검사해도 이 수를 채우려 한다)
	int32 WantWolves = 0;
	bool bStageInside = false;                // 무대 네 모서리가 지역 상자 안
	bool bGrounded = false;                   // 모든 시작 자리를 지면 검사로 골랐다 (스트리밍 조정자는 시작 직전 검사 뒤에만 참)
	bool bComplete = false;                   // 사슴·늑대 수를 다 채웠다

	/** 무대 (0, 0) 의 cm (XY). */
	FVector OriginCm() const { return FVector(CenterCm.X - 0.5 * SizeUnits * 200.0, CenterCm.Y - 0.5 * SizeUnits * 200.0, CenterCm.Z); }
	bool IsInsideStage(const FVector& P, double MarginCm = 0.0) const
	{
		const double Half = 0.5 * SizeUnits * 200.0 - MarginCm;
		return FMath::Abs(P.X - CenterCm.X) <= Half && FMath::Abs(P.Y - CenterCm.Y) <= Half;
	}
};

/** 최근 포획 자리 (디버그 표시). */
struct FEcoV3IntegratedCatchMark
{
	FVector Location = FVector::ZeroVector;
	double Time = 0.0;
};

/**
 * 늑대 식사·이어 사냥·팀 화면 확인 집계 (누적, 사람 결정 10-15 (B)). 기록 줄은 지난 줄과의 차이를 쓴다. 기록·시험 전용 (규칙이 아니다).
 * '이어 사냥' = 그 늑대가 앞 포획 뒤 3 초 안에 시작한 돌진 (식사가 3 초보다 길면 늘 0). '식사 끝 3 초 안' = 앞 포획 뒤
 * (식사 스텝 + 22 스텝) 안 — 식사를 마치자마자 곁의 사슴에게 돌진했는가.
 */
struct FEcoV3WolfEatTally
{
	int64 Catches = 0;              // 늑대 포획 (늑대·스텝. 같은 사슴을 둘이 잡으면 둘 다 센다 — 파이썬 got 과 같다)
	int64 EatSteps = 0;             // 식사 중(포획 뒤 쿨다운으로 사냥하지 않음) 늑대·스텝
	int64 EatMoved = 0;             // 그중 움직인 늑대·스텝 (제자리 식사면 0)
	int64 Pounces = 0;              // 잠행형 돌진 시작
	int64 ChainPounces = 0;         // 그 늑대가 앞 포획 뒤 3 초(22 스텝) 안에 시작한 돌진
	int64 PostEatPounces = 0;       // 앞 포획 뒤 (식사 스텝 + 22 스텝) 안에 시작한 돌진
	int64 RepeatCatches = 0;        // 앞 포획이 있는 늑대의 포획
	int64 PostEatCatches = 0;       // 그중 앞 포획 뒤 (식사 스텝 + 22 스텝) 안 포획
	int64 EatFlagFrames = 0;        // 팀 늑대 표현 액터: 식사 깃발(bEating)이 선 늑대·프레임
	int64 EatMotionFrames = 0;      //   그중 팀 화면 동작이 '먹는 중'(서서 먹기)
	int64 EatWalkFrames = 0;        //   그중 걷기·뛰기 (깃발이 섰는데 움직인다 — 잡은 스텝의 이동을 보간하는 0.13 초가 여기 든다)
};

/** 한 지역의 v3 세계 (무대 하나 = 학습 세계 하나). */
struct ADAPTIVEECOSYSTEM_API FEcoV3RegionContext
{
	FName RegionId;
	int32 RegionRuntimeIndex = INDEX_NONE;
	int32 Index = INDEX_NONE;                 // 컨텍스트 색인 (FEcoIntegratedV3Fragment::ContextIndex)
	EcoWorldV3::FWorldState Sim;
	bool bSpatialFoodRegistered = false;
	int64 ResourceReceiptSequence = 0;
	FVector OriginCm = FVector::ZeroVector;   // 무대 (0, 0) 의 cm. Z = 무대 중심 지면 (기본 높이)
	double SizeUnits = 60.0;
	int32 PlannedDeer = 0;
	int32 PlannedWolves = 0;
	int32 AdoptedDeer = 0;
	int32 AdoptedWolves = 0;
	int32 TeamCovers = 0;                     // v3 원 목록에 넣은 레벨 은신처 (무대 안, 반경이 학습 범위)
	int32 SkippedTeamCovers = 0;              // 무대 안이지만 반경이 학습 범위(4~9 단위) 밖이라 v3 원 목록에서 뺀 레벨 은신처
	int32 ExtraCovers = 0;                    // 우리가 놓은 은신처
	TArray<double> CoverGroundZ;              // 은신처 원 중심의 높이 (디버그 그리기)
	bool bReportedLowDensity = false;         // 학습 밀도 하한 아래 경고를 남겼다

	// 프레임 끝 집계 (처리기가 채운다)
	int32 AliveDeer = 0;
	int32 BehaviorNow[EcoRepertoireV3::kNumBehaviors] = {};
	int32 WolvesNow[static_cast<int32>(EcoV3Integrated::EWolfState::Count)] = {};
	int32 Wolves = 0;

	// 섭식 (먹기 표시·기록). 먹이 단위 = v3 먹이 격자 값 (셀 4 m × 4 m 하나가 많아야 1, 사슴 한 마리는 한 스텝에 많아야 0.06 = 에너지 3%p).
	// 팀 지역 먹이 장부(FRegionEcologyState::FoodAmount)에는 쓰지 않는다 — 팀 재생률이 0 으로 고정이라(EcologyRegion.cpp
	// MakeInitialEcologyState) 한쪽으로만 줄어 거짓 고갈로 보인다
	double StartFood = 0.0;                   // 무대 먹이 처음 합 (= 셀 용량 합, AddContext)
	double MeanEnergy = 0.0;                  // 산 사슴 에너지 평균 (0~1, 결정 스텝마다·프레임 끝)
	int32 StarvingDeer = 0;                   // 산 사슴 중 에너지 kStarvingEnergy 아래
	// 야생 (w1) 지방 비축 (켠 세계만, 결정 스텝마다·프레임 끝. TallyEnergy)
	double MeanReserve = 0.0;                 // 산 사슴 비축 평균 (0~1)
	double MinReserve = 0.0;                  // 산 사슴 비축 최소
	int32 OnReserveDeer = 0;                  // 산 사슴 중 배가 비어(에너지 0) 비축으로 사는 수
	int32 LowReserveDeer = 0;                 // 산 사슴 중 비축 kLowReserve 아래
	int32 WeakDeer = 0;                       // 산 사슴 중 배 WeakE 밑 (느림)
	int32 AteDeerInterval = 0;                // 이번 기록 구간에 한 번이라도 먹은 사슴 (그 뒤 죽은 사슴 포함)
	int32 LogEpoch = 0;                       // 기록 구간 번호 (LogContext 마다 + 1)
	TArray<double> RecentEaten;               // 최근 kRecentEatSteps 결정 스텝의 스텝마다 먹은 양 (고리 버퍼)
	int32 RecentEatenPos = 0;
	double LastStepFoodEaten = 0.0;           // 지난 결정 스텝 끝의 Sim.Stats.FoodEaten (스텝 차이 계산)

	/** 결정 스텝 하나 끝: 이번 스텝 먹은 양을 고리 버퍼에 넣는다. */
	void PushStepEaten()
	{
		if (RecentEaten.Num() != EcoV3Integrated::kRecentEatSteps)
		{
			RecentEaten.Init(0.0, EcoV3Integrated::kRecentEatSteps);
			RecentEatenPos = 0;
		}
		RecentEaten[RecentEatenPos] = Sim.Stats.FoodEaten - LastStepFoodEaten;
		RecentEatenPos = (RecentEatenPos + 1) % EcoV3Integrated::kRecentEatSteps;
		LastStepFoodEaten = Sim.Stats.FoodEaten;
	}
	/** 최근 10 초(결정 스텝 75 개) 먹은 양 (먹이 단위). */
	double RecentEatenSum() const
	{
		double Sum = 0.0;
		for (const double V : RecentEaten)
		{
			Sum += V;
		}
		return Sum;
	}
	/** 무대 먹이 지금 합 ÷ 처음 합 (0~1). */
	double FoodFraction() const
	{
		return StartFood > 0.0 ? Sim.Food.Total() / StartFood : 0.0;
	}

	// 늑대 밤잠 점진화 기록 (해 진·뜬 시각 — 잠듦·깸 줄의 '해 진 뒤 초'). -1 = 아직 모른다
	int64 DarkStartT = -1;                    // 마지막으로 어둠(d ≥ 0.5)이 시작된 전역 스텝
	int64 LightStartT = -1;                   // 마지막으로 밝아진(d < 0.5) 전역 스텝
	bool bPrevDark = false;                   // 지난 결정 스텝 끝의 어둠 (d ≥ 0.5)
	bool bDarkKnown = false;                  // bPrevDark 가 정해졌다

	// 사슴 얼기 막음·늑대 식사 기록 (사람 결정 10-15 (A)(B), 처리기가 결정 스텝마다 채운다)
	int64 FreezeMaskOpen = 0;                 // 요청을 읽은 결정 중 마스크에 얼기 칸이 열린 수 (얼기를 막으면 늘 0)
	int64 LastLogFreezeMaskOpen = 0;
	FEcoV3WolfEatTally Eat;
	FEcoV3WolfEatTally LastLogEat;
	TMap<int64, int32> WolfCatchesById;       // 늑대 StableAgentId → 포획 누적 (기록 줄 '늑대별 포획')
	TMap<int64, int64> WolfLastCatchStep;     // 늑대 StableAgentId → 마지막으로 잡은 스텝 번호 (이어 사냥 판정)

	// 경계 거리 기록 (사람 결정 10-15 (C), 처리기가 채운다. 규칙 켬·끔 모두 센다)
	int64 NearEatingDeerSteps = 0;            // 식사 중(쿨다운 > 0)인 깨어 있는 늑대의 15 m 안에 있던 산 사슴 (개체·스텝, 스텝 끝)
	int64 LastLogNearEatingDeerSteps = 0;
	int32 KeepNow[EcoWorldV3::kNumKeepModes] = {};   // 프레임 끝 산 사슴의 덮기 (화면 집계)

	/**
	 * 늑대 하나의 결정 스텝 하나를 센다 (처리기가 Step 뒤에 부른다. StepIndex = 이번 스텝 번호 = Step 뒤 Sim.T − 1).
	 * 돌진 시작이면 앞 포획 뒤 경과로 이어 사냥·식사 끝 3 초 안을 가르고, 식사 중(잡지 않았고 쿨다운 > 0)이면 움직였는지 보고,
	 * 잡았으면 포획·늑대별 포획·앞 포획 뒤 경과를 센 뒤 마지막 포획 스텝을 바꾼다.
	 */
	void TallyWolfStep(const EcoWorldV3::FThreatAgent& A, int64 WolfId, int64 StepIndex);

	// 기록
	int64 TerrainChecks = 0;                  // 지형 제약으로 검사한 이동 수 (콜백이 실제로 도는지 보는 기록)
	int64 LastLogTerrainChecks = 0;
	int64 LastLogT = 0;
	EcoWorldV3::FWorldStats LastLogStats;
	TArray<FEcoV3IntegratedCatchMark> RecentCatches;

	FVector UnitsToCm(double X, double Y, double Z) const
	{
		return FVector(OriginCm.X + X * EcoRepertoireV3::kUnitCm, OriginCm.Y + Y * EcoRepertoireV3::kUnitCm, Z);
	}
	EcoWorldV3::FVec2 CmToUnits(const FVector& P) const
	{
		return {(P.X - OriginCm.X) / EcoRepertoireV3::kUnitCm, (P.Y - OriginCm.Y) / EcoRepertoireV3::kUnitCm};
	}
	double SizeCm() const { return SizeUnits * EcoRepertoireV3::kUnitCm; }
};

/**
 * 서식지 스트리밍 조정자의 시작 직전 지면 검사 틱. TG_LastDemotable 은 엔진 스트리밍 갱신(UWorld::Tick 의 InternalUpdateStreamingState)
 * 뒤이고 조정자의 OnWorldPostActorTick(StartAuthority) 앞이다 — 그 사이에는 스트리밍 상태가 바뀌지 않는다.
 */
struct FEcoV3PreStartTickFunction : public FTickFunction
{
	TWeakObjectPtr<UEcoPolicyV3IntegratedSubsystem> Owner;

	virtual void ExecuteTick(float DeltaTime, ELevelTick TickType, ENamedThreads::Type CurrentThread,
							 const FGraphEventRef& MyCompletionGraphEvent) override;
	virtual FString DiagnosticMessage() override { return TEXT("EcoV3I 시작 직전 지면 검사"); }
	virtual FName DiagnosticContext(bool bDetailed) override { return FName(TEXT("EcoV3IPreStart")); }
};

/** 조정자에서 우리가 바꾸는 공개 속성의 팀 값 (시작 직전 검사가 실패하면 되돌린다). */
struct FEcoV3SpawnerTeamValues
{
	TArray<FEcoCreatureSpawnGroup> Groups;
	FEcoMigrationSettings Migration;
	bool bEnableWaves = false;
	float EnergyDrainPerSecond = 0.0f;
	float EnergyPerFood = 0.0f;
	double DaySeconds = 60.0;
	double NightSeconds = 60.0;
	int32 GlobalPopulationLimit = 0;
	bool bValid = false;
};

UCLASS()
class ADAPTIVEECOSYSTEM_API UEcoPolicyV3IntegratedSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	/** 스위치: 콘솔 변수 eco.IntegratedPolicyVersion 이 3 이면 3, 그 밖은 1 (끔). 명령줄 -EcoIntegratedV3 는 그 콘솔 변수의 시작값이다. */
	static int32 GetRequestedVersion();
	static bool IsRequested() { return GetRequestedVersion() == 3; }
	/** 콘솔 변수 eco.V3Debug (명령줄 -EcoV3Debug 는 시작값). */
	static bool IsDebugDrawEnabled();

	/**
	 * 명령줄 인자 → 콘솔 변수 시작값. ECVF_SetByCommandline 우선순위로만 쓰고, 콘솔·코드가 이미 정한 변수는 건드리지 않는다
	 * (그래서 콘솔에서 끄면 명령줄이 다시 켜지 않는다). 처음 스위치를 읽을 때 진짜 명령줄로 한 번 부른다. 시험은 문자열을 넘긴다.
	 */
	static void ApplyCommandLineToConsole(const TCHAR* CmdLine);

	/**
	 * 서식지 스트리밍 조정자가 이 프레임 끝에 StartAuthority 를 부르는가 (조정자 Tick 과 같은 조건: BeginPlay 뒤 30 초를 넘으면 시간 초과,
	 * 0.25 초 미만이거나 스트리밍 원천이 덜 끝났으면 기다림).
	 */
	static bool CoordinatorStartsThisFrame(double SecondsSinceBeginPlay, bool bStreamingCompleted)
	{
		return SecondsSinceBeginPlay >= 0.25 && SecondsSinceBeginPlay <= 30.0 && bStreamingCompleted;
	}

	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;

	bool IsActive() const { return bActive; }
	/** Quiesce the native writer after a rejected authority resource transaction. */
	void RejectResourceContract();
	bool UsesTerrain() const { return bUseTerrain; }
	const FEcoV3IntegratedSettings& GetSettings() const { return Settings; }

	// ---- 계획 (엔진 상태 없이 시험할 수 있게 함수만 받는다) ----

	/**
	 * 한 지역 무대와 시작 자리. Contains = 지역 상자 안인가, Project = 지면 검사(성공하면 지면 점).
	 * bRequireGround 면 지면 검사를 통과한 점만 쓴다 (못 채우면 false). 아니면 검사에 실패한 점도 힌트로 쓴다(스트리밍 전 계획).
	 * 시작 자리 난수는 (세션 시드, 그룹 번호) 로 정해진다 — 같은 입력이면 같은 자리.
	 */
	static bool PlanStage(FName RegionId, int32 GroupIndex, const FVector& DesiredCenterCm, const FVector& RegionCenterCm,
						  const FEcoV3IntegratedSettings& S, int32 NumDeer, int32 NumWolves, bool bRequireGround,
						  TFunctionRef<bool(const FVector&)> Contains, TFunctionRef<bool(const FVector&, FVector&)> Project,
						  FEcoV3StagePlan& Out);

	/** 지역 v3 세계 설정 (무대 한 변·늑대 구성·낮밤 900·통합 모드 칸). Covers 는 무대 단위. */
	static EcoWorldV3::FWorldConfig MakeRegionWorldConfig(const FEcoV3IntegratedSettings& S, int32 RegionRuntimeIndex,
														  int32 PlannedDeer, int32 PlannedWolves,
														  const std::vector<EcoObservationV3::FCoverInput>& Covers);

	// ---- 처리기 쪽 ----

	/** 프레임 dt → 이번 프레임에 돌 전역 결정 스텝 수 (최대 64). 평면 시험 경로의 시계와 따로다. */
	int32 AdvanceClock(float DeltaSeconds);
	float GetVisualAlpha() const;
	int64 GetGlobalStep() const { return GlobalT; }
	/** 모든 컨텍스트가 결정 스텝 하나를 마쳤다 → 전역 t + 1. */
	void FinishGlobalStep() { ++GlobalT; }
	/** 컨텍스트의 t 를 전역 t 에 맞춘다 (어둠 다시 계산). */
	void SyncContextClock(FEcoV3RegionContext& Ctx) const;

	int32 NumContexts() const { return Contexts.Num(); }
	FEcoV3RegionContext* GetContext(int32 Index) { return Contexts.IsValidIndex(Index) ? Contexts[Index].Get() : nullptr; }
	const FEcoV3RegionContext* GetContext(int32 Index) const { return Contexts.IsValidIndex(Index) ? Contexts[Index].Get() : nullptr; }
	FEcoV3RegionContext* FindContext(FName RegionId);

	/** 처리기가 한 컨텍스트의 결정 스텝 하나를 마칠 때마다 부른다 (포획 표시·기록). */
	void NotifyContextStep(FEcoV3RegionContext& Ctx, const EcoWorldV3::FStepReport& Report);
	/**
	 * 늑대 밤잠 점진화 기록 (처리기가 결정 스텝 하나 뒤, NotifyContextStep 앞에 부른다): 해 진·뜬 시각을 갱신하고 늑대마다 이번 스텝의
	 * 밤잠 사건(잠듦·깸·눕기 시작·다시 일어남)을 한 줄씩 남긴다. 가장 가까운 사슴은 이번 스텝 이동 뒤 산 사슴(Sim.Prey)이다.
	 * Threats·WolfIds 는 이번 Step 배열과 같은 순서다. 밤잠 점진화를 끈 세계는 아무것도 하지 않는다.
	 */
	void NotifyNightStep(FEcoV3RegionContext& Ctx, EcoWorldV3::FThreatAgent* const* Threats, const int64* WolfIds, int32 NumWolves);
	/** [EcoV3I] 기록 줄을 지금 남긴다. */
	void LogContext(FEcoV3RegionContext& Ctx);
	/** 처리기가 한 프레임에 결정 스텝 Steps 개(모든 지역)를 돈 시간 (기록 줄의 '결정 스텝 CPU'). */
	void AddStepCpuSeconds(double Seconds, int32 Steps)
	{
		StepCpuSeconds += Seconds;
		StepCpuSteps += Steps;
		StepCpuMaxFrameSeconds = FMath::Max(StepCpuMaxFrameSeconds, Seconds);
	}

	/**
	 * 지형 제약 이동 검사: FromCm → ToCm 를 30 cm 이하 토막으로 나눠 팀 공개 함수 EcoCreatureMovement::ConstrainStep (지역 안·장애물·
	 * 지면·물) 을 부른다. 통과하면 OutZ = 끝 지면 높이, 막히면 거짓 (OutZ = FromCm.Z).
	 */
	bool TraceMove(FName RegionId, const FVector& FromCm, const FVector& ToCm, double& OutZ) const;

	// ---- 시험·조정자 없이 쓰는 길 ----

	/** 조정자 없이 켠다 (자동화 시험). bTerrain 이 거짓이면 지형 제약 콜백을 쓰지 않는다. */
	void ActivateForTest(const FEcoV3IntegratedSettings& InSettings, bool bTerrain);
	/** 컨텍스트 하나를 만든다 (t = 전역 t). 반환 포인터는 서브시스템이 끝날 때까지 유효하다. */
	FEcoV3RegionContext* AddContext(FName RegionId, int32 RegionRuntimeIndex, const FVector& OriginCm,
									const EcoWorldV3::FWorldConfig& Config, int32 PlannedDeer, int32 PlannedWolves);
	/** 시험: OnWorldBeginPlay 의 조정자 바꾸기만 (넷 모드·스위치 검사 없이). 성공하면 켜진 상태가 된다 (틱·델리게이트는 등록하지 않는다). */
	bool ApplyToSpawnerForTest(AEcoCreatureIntegrationSpawner& InSpawner, const FEcoV3IntegratedSettings& InSettings);
	/** 시험: 시작 직전 지면 검사를 지금 한 번 (실패하면 팀 값으로 되돌리고 끈다). */
	bool ValidateSpawnPointsForTest() { return ValidateSpawnPointsNow(); }
	/** 팀 늑대 표현 액터의 동작을 센다 (읽기만. 프레임마다 HandlePreActorTick 이 부르고, 시험도 부른다): 식사 깃발이 선 늑대가 '먹는 중' 동작인가. */
	void TallyTeamWolfVisuals();
	const TArray<FEcoV3StagePlan>& GetPlans() const { return Plans; }

protected:
	virtual bool DoesSupportWorldType(const EWorldType::Type WorldType) const override;

private:
	friend struct FEcoV3PreStartTickFunction;

	bool ApplyToSpawner(AEcoCreatureIntegrationSpawner& InSpawner);
	/** 시작 직전 지면 검사 (스트리밍 조정자). 실패하면 RestoreTeamValues + 끔. */
	bool ValidateSpawnPointsNow();
	void RestoreTeamValues(const TCHAR* Why);
	void Deactivate(const TCHAR* Why);
	void HandlePreActorTick(UWorld* InWorld, ELevelTick TickType, float DeltaSeconds);
	void HandlePreStartTick();
	void TryCreateContexts();
	void CheckClockDrift();
	void DrawOverlay();
	/**
	 * 보기 환경 (Play 동안만, 끝나면 되돌린다).
	 * - 엔진은 한 액터에 디버그 글자를 128개까지만 그린다(r.DebugSafeZone.MaxDebugTextStringsPerActor). 우리 글자는 모두 WorldSettings 에
	 *   붙으므로 eco.V3Debug 를 켠 동안만 한도를 푼다(0 = 한도 없음). 그릴 수 없는 실행(-NullRHI)에서는 풀지 않는다 — HUD 가 그려지지
	 *   않아 엔진이 글자 목록을 비우지 않으므로, 한도가 없으면 목록이 끝없이 늘어 프레임이 점점 느려진다.
	 * - 팀 이주 디버그 글자('ID n Forest Resident')는 v3 모드에서 이주를 꺼 두므로 뜻이 없고 행동 글자를 가린다. v3 모드 동안만
	 *   UEcoRuntimeSettings 기본 객체의 bDrawMigrationDebug 를 끈다. 설정 파일에는 쓰지 않는다.
	 */
	void UpdateViewEnvironment();
	void RestoreViewEnvironment();

	TWeakObjectPtr<AEcoCreatureIntegrationSpawner> Spawner;
	TArray<FEcoV3StagePlan> Plans;
	TArray<TUniquePtr<FEcoV3RegionContext>> Contexts;
	TArray<TWeakObjectPtr<AActor>> SpawnedCovers;
	TSet<int32> OurShelterIndices;            // 우리가 놓은 앵커의 UEcoShelterSubsystem RuntimeIndex (레벨 은신처와 가른다)
	FEcoV3IntegratedSettings Settings;

	/** 팀 값 (되돌리기용). 설정 에셋은 GC 가 보도록 UPROPERTY 로 쥔다 — 조정자는 바꾼 뒤 우리 설정만 가리킨다. */
	FEcoV3SpawnerTeamValues TeamValues;
	UPROPERTY(Transient)
	TObjectPtr<UMassEntityConfigAsset> TeamHerbivoreConfig;
	UPROPERTY(Transient)
	TObjectPtr<UMassEntityConfigAsset> TeamWolfConfig;

	FEcoV3PreStartTickFunction PreStartTick;

	bool bActive = false;
	bool bUseTerrain = true;
	bool bStreamingSpawner = false;   // 조정자가 서식지 스트리밍을 기다린 뒤 시작한다 (시작 직전 지면 검사가 필요하다)
	bool bPointsFinal = false;        // 시작 자리를 더 검사하지 않는다
	bool bContextsCreated = false;

	double BeginPlaySeconds = 0.0;    // OnWorldBeginPlay 시각 = 조정자 BeginPlay 의 StartedAt (같은 UWorld::BeginPlay 안이라 시각이 같다)
	int32 ValidationPasses = 0;       // 시작 직전 지면 검사 횟수 (많아야 kMaxValidationPasses)

	int64 GlobalT = 0;
	EcoPolicy::FStepClock Clock;
	int32 ClockPhase = 0;
	int32 LogEverySteps = 75;

	double StepCpuSeconds = 0.0;          // 시작부터 결정 스텝(모든 지역) 누적 시간
	int64 StepCpuSteps = 0;
	double StepCpuMaxFrameSeconds = 0.0;  // 한 프레임의 결정 스텝 시간 최댓값 (스텝이 몰린 프레임의 끊김)

	FDelegateHandle PreTickHandle;

	bool bTextLimitRaised = false;
	int32 SavedTextLimit = 128;
	bool bMigrationDebugHidden = false;
	bool bSavedMigrationDebug = true;
	double NextScreenTally = 0.0;
};

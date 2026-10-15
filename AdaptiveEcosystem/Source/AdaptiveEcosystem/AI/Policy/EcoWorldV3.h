// v3 R1b 세계 한 결정 스텝 — 엔진 무관 v3 헤더(EcoRepertoire.h·EcoObservationV3.h·EcoThreatModel.h·EcoPolicyV3Inference.h)를
// 계약 10-2 의 순서로 묶는 세계 층. 파이썬 herbivore_rl/env_v2/world.py 의 v3 경로(`step`·`reset`·`_respawn`·`_eat`·
// `_food_fields`·`_build_world` 먹이 격자)의 거울이다.
//
// **이 파일은 의도적으로 언리얼에 의존하지 않는다.** `<cmath>`·`<cstdint>`·`<vector>` 와 엔진 무관 v3 헤더만 쓴다.
// 같은 단계 함수를 두 곳이 부른다:
//   Mass 경로   UEcoPolicyV3StepProcessor — 조각(fragment)에 든 개체 상태를 슬롯 순서 보기(FHerbView)로 모아 부른다
//   기준 루프   FReferenceWorld          — 같은 상태를 std::vector 에 두고 부른다 (자동화 시험 Policy.V3.Mass.ReferenceParity)
// 두 경로의 차이는 저장 위치(조각 대 배열)·슬롯 순서 모으기·결정 시계·스폰뿐이라, 같은 시작이면 논리 상태가 비트 단위로 같아야 한다.
//
// 계약: AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md 10-2 (스텝 순서), 6-3 (이동·에너지), 7 (위협), 12-1 (단위).
// 세계: R1b 두뇌가 배운 경보 없는 세계 (사람 결정 10-13 (3)). 경보 M8·E7 은 없다.
// 단위: 파이썬 단위 (1단위 = 200 cm, 1스텝 = 8/60 s). 맵은 [0, WorldSize]² 정사각이다. cm 대응은 Mass 층(서브시스템)의 몫이다.
//
// 한 결정 스텝 (Step, 계약 10-2. 순서가 계약이다):
//   A  Arbiter Commit       지난 스텝 끝에 정한 요청(Prepare·마스크·망)을 반영한다
//   B  Control              행동별 제어기 (결정 관측 = 지난 스텝 끝 기하, 결정 때 위치·먹이 셀)
//   C1 초식 이동            맵 벽에서 멈춘다(자르기). heading = 속도 방향, FREEZE 는 위협 쪽
//   C2 ThreatStep           위협 슬롯 순서로 EcoThreatV3::Step. 선회·원거리 굴림·플레이어 모드 값은 세계 난수에서 뽑아 넣는다
//      포획 정리            ResolveCatches — 한 초식을 여럿이 잡아도 사망은 한 번
//   C4 섭식·대사            셀마다 수요 합 → 먹은 양 = min(수요, 셀 먹이) → 수요 비율로 나눔 (슬롯 순서 합)
//   C5 번식 · C6 사망 (잡힘 또는 E <= 0) · C7 피식 EMA (분모 N 고정) · C8 먹이 재생
//   D  t ← t + 1, Tick       D′ 새 t 의 어둠
//                           D″ (FWorldConfig::bRealismNight 일 때만) 늑대마다 밤잠 업데이트 EcoThreatV3::NightUpdate (사슴 위치 = C2 의
//                              이동 뒤 위치, 리스폰 전). 끄면 이 줄이 없다 — 평면 맵·기준 루프·골든은 지금 그대로다
//   E  관측                 먹이 장(blur·기울기) → 위협·동족·은신처 지각 → Perceive(away·recency) → 관측 18
//                           이번 스텝에 죽은 개체도 제자리에서 동족으로 센다(파이썬 그대로, 계약 2-3·열린 질문 5)
//   G  리스폰               죽은 슬롯을 새 세대로 (맵 전체 균등 위치) — 그 행만 E 를 다시 한다
//                           (통합 모드 bRespawnDead = false: 부활하지 않고 PrevPos = Pos 로 멈춘다. 다음 스텝부터는 부르는 쪽이 뺀다)
//   H  다음 요청            Prepare(결정 관측) → 마스크(판 2, 허용 = FWorldState::Allowed) → reads 면 망 argmax, 아니면 지금 행동
//
// 통합 모드 (팀 통합 레벨, AI/Policy/EcoPolicyV3IntegratedProcessors): 기본값은 모두 평면 시험 맵과 같다(ReferenceParity 그대로).
//   FWorldConfig::RngStream        세계 난수 갈래 (지역마다 다른 먹이 패치·늑대 선회). 0 = 지금과 같다
//   FWorldConfig::bRespawnDead     false = 제자리 부활 없음 (죽은 개체 = 사라질 개체, 새 개체 = 새 StableAgentId)
//   FWorldConfig::PredEmaDenominator  피식 EMA 분모 고정값. 0 = 지금처럼 N
//   FWorldConfig::bRealismNight    늑대 밤잠 점진화 (파이썬 configs/v3_real1_night_on.yaml realism_night). false = 지금과 같다.
//                                  켜면 잠은 늑대별 상태(InitThreat·AdoptThreat 의 NightInit, D″ NightUpdate)이고 관측도 그 상태를 읽는다
//   FWorldConfig::PredEatCdOverride·bEatInPlace  늑대 식사 길이(포획 뒤 쿨다운)와 식사 중 제자리 (사람 결정 10-15 (B)). 0·false = 지금과 같다
//   FWorldConfig::WorldAllowed     세계의 허용 행동 칸. 실제 허용 = 모델 kAllowedMask ∧ 이 칸 (FWorldState::Allowed, H 의 마스크).
//                                  모두 1 = 지금과 같다. 통합 모드는 FREEZE 를 막는다 (사람 결정 10-15 (A), 파이썬 effective_allowed)
//   FStepHooks                     이동 제약 콜백 (지형·장애물). C1 사슴 이동 바로 뒤, C2 위협마다 Step 바로 뒤에 부른다.
//                                  막히면 그 개체는 이번 스텝 이동 전 자리에 남는다 — 그래서 포획 거리·섭식 셀·관측이 모두 막힌 뒤 위치로 계산된다
//   AdoptHerb·AdoptThreat          주어진 위치·heading·키·종류로 만든다(세계 난수를 쓰지 않는다)
//   ObserveAndDecideRows           새로 입양한 행만 첫 관측·첫 요청
//   FHerbBody::LastIntake, FWorldStats::FoodEaten·EatSteps  섭식 기록 (통합 모드의 먹기 표시·기록). 늘 채우지만 어떤 계산에도
//                                  쓰지 않는다 — 평면 맵·기준 루프의 논리 상태는 비트 단위로 그대로다
//   FWorldConfig::WildFlight       야생 1단계 (w3) 도주 반사 거리 (사람 결정 10-15 (7), 두뇌 위의 세계 규칙 — 경계 거리 실험 KeepAway 를
//                                  바꿨다). 기본 끔 = 지금과 같다 — 새 줄은 모두 WildFlight.bEnabled 안에 있다. 아래 '야생 1단계 (w3)' 묶음 머리 주석
//   FWorldConfig::WildReserve      야생 1단계 (w1) 지방 비축 (사람 결정 10-15 (7)). 기본 끔 = 지금과 같다 — 새 줄은 모두 bEnabled 안
//                                  (B 약함 속도, C4 비축 꺼내기·채우기, C6 굶음 = E ≤ 0 ∧ R ≤ 0). 아래 '야생 1단계 (w1)' 묶음 머리 주석
// 계약 문서의 0번(요청 준비)을 H 로 옮긴 것은 계약 10-2 끝 주석('G 뒤에 두어도 된다')을 따른 것이다. Prepare 는 Commit 전까지
// 다른 무엇도 상태를 바꾸지 않으므로 Arbitrate 한 번과 비트 단위로 같다(계약 5-6).
//
// 난수 (계약 7-7, 11-1): 파이썬 numpy 스트림을 맞추지 않는다. 세계 난수 FRng(SplitMix64) 하나를 정한 순서로만 뽑는다 —
//   세계 생성: 먹이 잡음 Gw² 개 → 초식 슬롯마다 (x, y, 각) → 위협 슬롯마다 (x, y, 각, 플레이어면 모드 2개)
//   스텝마다:  위협 슬롯마다 선회 1개, 원거리형이면 초식 수만큼 굴림, 플레이어면 모드 2개 → 죽은 슬롯마다 (x, y, 각)
//   그래서 같은 시드·같은 설정이면 Mass 경로와 기준 루프가 같은 값을 받는다.

#pragma once

#include <cmath>
#include <cstdint>
#include <vector>

#include "EcoObservationV3.h"
#include "EcoPolicyV3Inference.h"
#include "EcoRepertoire.h"
#include "EcoThreatModel.h"

namespace EcoWorldV3
{
	using EcoRepertoireV3::FVec2;

	inline constexpr std::int32_t kDeathNone = 0;
	inline constexpr std::int32_t kDeathCaught = 1;
	inline constexpr std::int32_t kDeathStarved = 2;

	/** 세계 난수의 첫 해시 입력 (지연 해시 JITTER_TAG 505 와 다른 값 — 두 스트림이 겹치지 않게). */
	inline constexpr std::uint64_t kWorldRngTag = 0x57335247ULL;   // "W3RG"

	// ---- 결정적 난수 (SplitMix64). 값은 파이썬과 다르고 분포만 같다 ----

	struct FRng
	{
		std::uint64_t State = 0;

		std::uint64_t NextU64()
		{
			State += 0x9E3779B97F4A7C15ULL;
			return EcoRepertoireV3::Mix64(State);
		}

		/** [0, 1) 균등 (상위 53비트). */
		double NextU01() { return static_cast<double>(NextU64() >> 11) * (1.0 / 9007199254740992.0); }

		/** [Lo, Hi) 균등. */
		double Uniform(double Lo, double Hi) { return Lo + (Hi - Lo) * NextU01(); }
	};

	// ---- 야생 1단계 (w3) 도주 반사 거리 (사람 결정 10-15 (7), 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md 3-4, 파이썬 world.py '야생 1단계' (w3)
	//      `_wf_update`·`_wf_commit`·`_wf_alert_control`). 기본 끔 = R1b 학습 세계 그대로. 경계 거리 실험 KeepAway(0a55dd7)를 이 규칙으로 바꿨다 ----
	//
	// 두뇌 위의 세계 규칙이다 (가중치·관측 그대로). '알아챔' = 이 사슴의 위협 보임(관측과 같은 판정 — 시야·발소리, 자는 늑대는 안 보인다).
	// '사냥 중인 늑대' = 먹는 중(쿨다운)·배부름(SatLeft)·잠이 아니고 플레이어 휴식 모드가 아닌 위협. 스텝 끝(H)에 다음 스텝의 덮기를 정한다:
	//   은신처 원 안   사냥 중인 늑대를 AlertR(30 m) 안에서 알아채면 웅크림(HIDE 도착, bCrouch), 아니면 두뇌
	//   지난 도주      사냥 중인 늑대가 실거리 SafeR(40 m) 안이면 계속 도주 (쫓는 늑대는 돌아보며 안다)
	//   도주           사냥 중인 늑대를 FlightR(15 m) 안에서 알아챔, 또는 AlertR 안에서 알아챈 사냥 중인 늑대가 다가옴(이 사슴을 쫓음 ∨
	//                  접근 관측 ≥ Approach)
	//   경계           사냥 중인 늑대(bRestAlert 면 먹는·쉬는 늑대도)를 AlertR 안에서 알아챔
	// 실행:
	//   도주   두뇌 요청 대신 FLEE(뛰기, Commit 대신 CommitFlight). 방향 = SafeR 안 사냥 중인 늑대들 반대(거리 역수 가중 합). 그 방향 ±acos(ShelterCos)
	//          안에 가장자리 거리 ShelterR 안의 은신처가 있으면 가장 가까운 그 은신처 중심 쪽
	//   웅크림 두뇌 요청 대신 HIDE (은신처 안이라 곧바로 도착)
	//   경계   행동은 두뇌가 정한다. 두뇌가 GRAZE 면 걸으며 먹고(섭식 걷기 배수) 방향 = n(GRAZE 조향 + AlertW·알아챈 늑대들 반대), 고개를 든다(시야 배수 1)
	//   두 방향 모두 무대 벽 WallMargin 안이면 벽 쪽 성분을 지운다. 도주·웅크림이 풀리면 잠금 0·미뤄 둔 사건 지움(두뇌가 곧바로 고른다)
	// 값 = configs/v3_wild1_mirror.yaml wild_flight (단위: 1 = 2 m). 골든 WildGoldenVectorsV3.h '도주 장면'
	struct FWildFlightConfig
	{
		bool bEnabled = false;              // 끄면 아래 칸을 아무도 읽지 않는다
		double AlertR = 15.0;               // 경계 거리 alert_r (30 m)
		double FlightR = 7.5;               // 도주 거리 flight_r (15 m)
		double SafeR = 20.0;                // 안전 거리 safe_r (40 m). 도주는 사냥 중인 늑대가 모두 이 밖이 될 때까지
		double Approach = 0.9;              // '다가옴' 접근 관측 문턱 (사건 E2 와 같다 — 닫는 속력 720 cm/s)
		double AlertW = 1.5;                // 경계 방향의 무게 (GRAZE 조향에 더한다)
		bool bRestAlert = true;             // 먹는·쉬는 늑대도 경계를 일으킨다
		double ShelterCos = 0.5;            // 도주 방향 ±60° 안 은신처
		double ShelterR = 15.0;             // 은신처 가장자리까지 이 안 (30 m)
		bool bCrouch = true;                // 은신처 안에서 알아채면 웅크림
		double WallMargin = 1.0;            // 무대 벽 여유 (2 m)
	};

	// 덮기 (FHerbDecision::KeepMode·KeepActive). 파이썬 WF_NONE·WF_ALERT·WF_PANIC·WF_SHELTER 와 같은 번호
	inline constexpr std::int32_t kKeepNone = 0;      // 두뇌가 정한다
	inline constexpr std::int32_t kKeepAlert = 1;     // 경계: 두뇌 행동 그대로, GRAZE 면 걸으며 먹고 멀어짐
	inline constexpr std::int32_t kKeepPanic = 2;     // 도주(안전해질 때까지): FLEE + 뛰기
	inline constexpr std::int32_t kKeepShelter = 3;   // 은신처 안 웅크림: HIDE 도착
	inline constexpr std::int32_t kNumKeepModes = 4;

	// ---- 야생 1단계 (w1) 지방 비축 (사람 결정 10-15 (7), 명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md 3-1, 파이썬 world.py
	//      '야생 1단계' (w1)·`_wild_reserve_step`). 기본 끔 = R1b 학습 세계 그대로 ----
	//
	// 사슴마다 느린 비축 R ∈ [0, 1] (시작·새 개체 Init). 용량 C = ReserveDays × DayPeriod × EnergyDrain (E 단위 — 걷기 대사만으로
	// ReserveDays 일을 버틴다). C4 의 E 를 정한 뒤(C5 번식 앞): E < 0 이면 모자람을 R·C 에서 꺼낸다(다 채우면 E = 0).
	// E ≥ RefillE 이고 R < 1 이고 이번 스텝 먹었으면 먹은 에너지의 RefillFrac 을(빈자리 (1 − R)·C 까지) E 에서 R 로 옮긴다.
	// 굶음 = E ≤ 0 이고 R ≤ 0. 약함: 스텝 첫머리 E < WeakE × MaxEnergy 면 이동 속도 × WeakSpeed (대사·섭식은 보행 그대로).
	// 값 = configs/v3_wild1_mirror.yaml wild_reserve (골든 WildGoldenVectorsV3.h 가 확인한다)
	struct FWildReserveConfig
	{
		bool bEnabled = false;              // 끄면 아래 칸을 아무도 읽지 않는다 (FHerbBody::Reserve 는 늘 0)
		double ReserveDays = 3.0;           // 비축이 버티는 게임 하루 수 (900 스텝 하루 → 2700 스텝 = 6분)
		double Init = 1.0;                  // 시작·새 개체 비축 (가득)
		double RefillE = 0.7;               // 이 E 이상일 때 먹으면 채운다
		double RefillFrac = 0.25;           // 먹은 에너지 중 비축으로 가는 몫
		double WeakE = 0.1;                 // 이 E 밑이면 약함 (× MaxEnergy)
		double WeakSpeed = 0.75;            // 약한 사슴의 이동 속도 배수
	};

	/** 비축 용량 C (E 단위). 낮 고정 세계(DayPeriod ≤ 0)는 파이썬처럼 비축을 켤 수 없다 — 0 을 돌려 비축이 늘 바닥이게 한다. */
	inline double WildReserveCapacity(const FWildReserveConfig& R, std::int32_t DayPeriod, double EnergyDrain)
	{
		return DayPeriod > 0 ? R.ReserveDays * static_cast<double>(DayPeriod) * EnergyDrain : 0.0;
	}

	/** 비축 한 스텝의 기록 (통계). */
	struct FWildReserveDelta
	{
		double Used = 0.0;     // 비축에서 꺼낸 에너지 (E 단위)
		double Refill = 0.0;   // 비축으로 옮긴 에너지
	};

	/**
	 * 비축 한 스텝 (world.py `_wild_reserve_step` 한 행과 줄마다 같다). E = C4 의 새 에너지(max_energy 로 자른 값), GainE = 이번 스텝
	 * 먹은 에너지(먹이 × FoodEnergyPerUnit). 모자람을 다 채우면 E = 0, R 이 모자라면 R = 0 이고 E 는 남은 모자람(< 0).
	 */
	inline FWildReserveDelta WildReserveStep(double& E, double& R, double GainE, double Cap, const FWildReserveConfig& Cfg)
	{
		FWildReserveDelta Out;
		if (E < 0.0 && Cap > 0.0)
		{
			const double Want = -E / Cap;
			const double R0 = R;
			const bool bCovered = Want <= R0;
			E = bCovered ? 0.0 : E + R0 * Cap;
			R = bCovered ? R0 - Want : 0.0;
			Out.Used = (Want < R0 ? Want : R0) * Cap;
		}
		if (Cfg.RefillFrac > 0.0 && E >= Cfg.RefillE && R < 1.0 && GainE > 0.0)
		{
			const double A = Cfg.RefillFrac * GainE;
			const double B = (1.0 - R) * Cap;
			const double Mv = A < B ? A : B;
			E -= Mv;
			const double Rn = R + Mv / Cap;
			R = Rn < 1.0 ? Rn : 1.0;
			Out.Refill = Mv;
		}
		return Out;
	}

	// ---- 야생 1단계 (w2) 늑대 포만 (명세 3-2). 계산은 EcoThreatModel.h FThreatConfig::bWildSatiation (Step) — 여기는 하루 단위 계수다 ----
	struct FWildSatiationConfig
	{
		bool bEnabled = false;              // 끄면 FThreatConfig::bWildSatiation 거짓 (SatLeft 늘 0)
		double SatDays = 0.5;               // 배부름 게임 하루 수 → 스텝 = 반올림(일 × DayPeriod), 0.5 는 올림 (wild_days_to_steps)
		double RestSpeed = 0.3;             // 배부른 늑대의 배회 속력 배수
	};

	/** 게임 하루 단위 계수 → 스텝 (world.py wild_days_to_steps: floor(일 × 하루 + 0.5)). */
	inline std::int32_t WildDaysToSteps(double Days, std::int32_t Period)
	{
		return static_cast<std::int32_t>(std::floor(Days * static_cast<double>(Period) + 0.5));
	}

	// ---- R3 감지 (파이썬 realism_vision (a), 야생 1단계가 값 그대로 켠다 — 명세 3-3). 기본 끔 = R1b 학습 세계 그대로 ----
	// 사슴이 위협을 보는 시야각만 넓힌다(반경·밤·행동 배수 그대로). 동족 시야각(kin_fov_deg)은 거울 세계도 120° 그대로라 옮기지 않았다
	struct FRealismVisionConfig
	{
		bool bEnabled = false;
		double ThreatFovDeg = 300.0;        // 앞쪽 ±150°, 바로 뒤 60° 사각
	};
	inline constexpr double kBaseFovDeg = 120.0;   // 파이썬 cfg.fov_deg (FObservationConfig::FovCos 의 각)

	// ---- 세계 설정 (파이썬 단위). 기본값 = 평면 시험 맵용 R1b 학습 범위 안의 한 세계 ----

	struct FWorldConfig
	{
		double WorldSize = 100.0;           // 정사각 맵 한 변 (단위, 학습 60~110). 100 = 200 m
		std::int64_t Seed = 20000;          // 지연 해시 Seed(계약 5-5) 이자 세계 난수 시드
		std::int32_t NumHerbivores = 128;   // 초식 수 N (학습 128). 피식 EMA 분모이기도 하다

		// 위협 구성 (슬롯 순서: 잠행형 → 근접 추격형 → 원거리형 → 플레이어 대역). 학습 범위 확인은 Mass 층이 한다
		std::int32_t NumStalkers = 3;       // 잠행-돌진형 (학습 비율 30~70%)
		std::int32_t NumChasers = 2;        // 근접 추격형
		std::int32_t NumRanged = 1;         // 원거리형 (추격형의 한 갈래, 학습 0~50%)
		std::int32_t NumNocturnal = 1;      // 야행성 (보통 위협 슬롯 끝에서부터, 학습 0~25%)
		bool bPlayerProxy = false;          // 플레이어형 대역 (선택, 계약 7-5)
		double PredSpeedMult = 0.8;         // 근접형 속력 배수 (학습 U[0.6, 0.95] 의 한 값)

		// 낮밤 (계약 7-6). DayPeriod <= 0 이면 낮 고정 (d = 0, to_transition = 1)
		std::int32_t DayPeriod = 900;       // 60 s + 60 s (#21 게임 값, 학습 {600, 900, 1800} 안)
		std::int32_t DayOffset = 0;
		std::int32_t TwilightSteps = 45;    // τ = 0.05·T

		// 은신처 원 (단위)
		std::vector<EcoObservationV3::FCoverInput> Covers;

		// 먹이 격자 (configs/default.yaml)
		double FoodCell = 2.0;
		std::int32_t FoodPatchBlur = 5;
		double FoodPatchThreshold = 0.60;
		std::int32_t FoodGradBlur = 2;
		double FoodRegenBase = 0.026;
		double FoodRegenMult = 1.0;         // 학습 U[0.5, 2] 의 한 값
		double FoodCoverRegenMult = 0.3;

		// 통합 모드 (기본값 = 평면 시험 맵 그대로)
		std::uint64_t RngStream = 0;        // 세계 난수 첫 해시의 셋째 입력. 0 = 지금과 같다. 지역마다 다르게 주면 먹이 패치·선회가 갈린다
		bool bRespawnDead = true;           // false = 죽은 슬롯을 되살리지 않는다 (G 를 건너뛰고 PrevPos = Pos 로 멈춘다)
		std::int32_t PredEmaDenominator = 0; // 피식 EMA 분모. 0 이면 이번 스텝 N (평면 맵: 설정 사슴 수 = 학습의 고정 128 과 같은 꼴)
		// 늑대 밤잠 점진화 (EcoThreatModel.h FThreatConfig::bRealismNight 로 넘긴다). 기본 끔 = R1b 학습 세계 그대로 (평면 맵·기준 루프·골든)
		bool bRealismNight = false;
		// 늑대 식사 (사람 결정 10-15 (B)). PredEatCdOverride > 0 이면 FThreatConfig::PredEatCd(포획 뒤 쿨다운, 학습 5) 를 이 값으로 바꾸고,
		// bEatInPlace 이면 식사 동안 서 있는다(FThreatConfig::bEatInPlace). 기본 = R1b 학습 세계 그대로.
		// 파이썬 R3 세계의 같은 칸: overrides.pred_eat_cd 38 · features.threats.eat_in_place true (configs/v3_r3*.yaml)
		std::int32_t PredEatCdOverride = 0;
		bool bEatInPlace = false;
		// 세계의 허용 행동 칸 (파이썬 train.repertoire.allowed). 실제 허용 = 모델 허용(kAllowedMask) ∧ 이 칸 — 파이썬
		// rep_policy.effective_allowed 의 '모델 목록 ∩ 세계 목록' 과 같다. 기본 모두 1 = 모델 목록 그대로 (평면 맵·기준 루프·골든).
		// 통합 모드는 eco.IntegratedV3.NoFreeze 1 이면 FREEZE 칸을 0 으로 둔다 (사람 결정 10-15 (A), R1b−F)
		std::uint8_t WorldAllowed[EcoRepertoireV3::kNumBehaviors] = {1, 1, 1, 1, 1};
		// 야생 1단계 (w3) 도주 반사 거리 (통합 모드 eco.IntegratedV3.WildFlight — 경계 거리 실험 KeepAway 를 바꿨다). 기본 끔 = 지금 그대로
		FWildFlightConfig WildFlight;
		// 야생 1단계 (w1) 지방 비축 (사람 결정 10-15 (7), 통합 모드 eco.IntegratedV3.WildReserve). 기본 끔 = 지금 그대로 (평면 맵·기준 루프·골든).
		// 낮 고정 세계(DayPeriod ≤ 0)에서는 InitWorld 가 끈다 (파이썬도 daynight 없이 켤 수 없다)
		FWildReserveConfig WildReserve;
		// 야생 1단계 (w2) 늑대 포만 (통합 모드 eco.IntegratedV3.WildSatiation). 기본 끔. 낮 고정 세계에서는 InitWorld 가 끈다
		FWildSatiationConfig WildSatiation;
		// R3 감지 (통합 모드 eco.IntegratedV3.RealismVision·RealismHearing). 기본 끔. 발소리 계수는 EcoObservationV3::FHearingConfig
		FRealismVisionConfig RealismVision;
		EcoObservationV3::FHearingConfig RealismHearing;

		std::int32_t NumBaseThreats() const { return NumStalkers + NumChasers + NumRanged; }
		std::int32_t NumThreats() const { return NumBaseThreats() + (bPlayerProxy ? 1 : 0); }
	};

	/** 평면 시험 맵의 기본 은신처: 맵 1/4·3/4 지점 네 곳, 반경 Radius (단위). */
	inline std::vector<EcoObservationV3::FCoverInput> QuadCovers(double WorldSize, double Radius)
	{
		const double A = 0.25 * WorldSize;
		const double B = 0.75 * WorldSize;
		return {{A, A, Radius}, {B, A, Radius}, {A, B, Radius}, {B, B, Radius}};
	}

	// ---- 먹이 격자 (world._build_world·_food_fields·_eat·재생) ----

	namespace Detail
	{
		inline std::int32_t ClampI(std::int32_t V, std::int32_t Lo, std::int32_t Hi) { return V < Lo ? Lo : (V > Hi ? Hi : V); }

		/** 누적합 표 (G+1)² — np.cumsum(np.cumsum(A, 0), 1). 먼저 행 방향으로 쌓고 그다음 열 방향으로 쌓는다. */
		inline void BuildSat(const std::vector<double>& A, std::int32_t G, std::vector<double>& Sat, std::vector<double>& Tmp)
		{
			const std::int32_t S = G + 1;
			Sat.assign(static_cast<size_t>(S) * S, 0.0);
			Tmp.assign(static_cast<size_t>(G) * G, 0.0);
			for (std::int32_t y = 0; y < G; ++y)
			{
				for (std::int32_t x = 0; x < G; ++x)
				{
					const size_t k = static_cast<size_t>(y) * G + x;
					Tmp[k] = A[k] + (y > 0 ? Tmp[k - G] : 0.0);
				}
			}
			for (std::int32_t y = 0; y < G; ++y)
			{
				double Run = 0.0;
				for (std::int32_t x = 0; x < G; ++x)
				{
					Run += Tmp[static_cast<size_t>(y) * G + x];
					Sat[static_cast<size_t>(y + 1) * S + (x + 1)] = Run;
				}
			}
		}

		/** 반경 Br 셀 정사각 평균 (world._box_mean). 격자 밖은 잘라 낸 실제 셀 수로 나눈다. */
		inline void BoxMean(const std::vector<double>& Sat, std::int32_t G, std::int32_t Br, std::vector<double>& Out)
		{
			const std::int32_t S = G + 1;
			Out.assign(static_cast<size_t>(G) * G, 0.0);
			for (std::int32_t y = 0; y < G; ++y)
			{
				const std::int32_t R0 = ClampI(y - Br, 0, G);
				const std::int32_t R1 = ClampI(y + Br + 1, 0, G);
				for (std::int32_t x = 0; x < G; ++x)
				{
					const std::int32_t C0 = ClampI(x - Br, 0, G);
					const std::int32_t C1 = ClampI(x + Br + 1, 0, G);
					const double Box = Sat[static_cast<size_t>(R1) * S + C1] - Sat[static_cast<size_t>(R0) * S + C1]
									   - Sat[static_cast<size_t>(R1) * S + C0] + Sat[static_cast<size_t>(R0) * S + C0];
					Out[static_cast<size_t>(y) * G + x] = Box / static_cast<double>((R1 - R0) * (C1 - C0));
				}
			}
		}

		/** np.gradient (간격 1, 안쪽 중앙 차분, 가장자리 한쪽 차분). Gy = 행(y) 방향, Gx = 열(x) 방향. G < 2 면 0. */
		inline void Gradient(const std::vector<double>& F, std::int32_t G, std::vector<double>& Gx, std::vector<double>& Gy)
		{
			Gx.assign(static_cast<size_t>(G) * G, 0.0);
			Gy.assign(static_cast<size_t>(G) * G, 0.0);
			if (G < 2)
			{
				return;
			}
			for (std::int32_t y = 0; y < G; ++y)
			{
				for (std::int32_t x = 0; x < G; ++x)
				{
					const size_t k = static_cast<size_t>(y) * G + x;
					Gx[k] = x == 0 ? F[k + 1] - F[k] : (x == G - 1 ? F[k] - F[k - 1] : (F[k + 1] - F[k - 1]) / 2.0);
					Gy[k] = y == 0 ? F[k + G] - F[k] : (y == G - 1 ? F[k] - F[k - G] : (F[k + G] - F[k - G]) / 2.0);
				}
			}
		}
	}

	struct FFoodGrid
	{
		std::int32_t Gw = 0;                  // 격자 한 변 셀 수 = ceil(size ÷ cell)
		double Cell = 2.0;                    // 셀 한 변 (단위) = 400 cm
		std::int32_t GradBlur = 2;
		std::vector<double> Cap;              // 셀 용량 (패치)
		std::vector<double> Food;             // 지금 먹이
		std::vector<double> Regen;            // 재생률 (은신처 셀 × 0.3)
		std::vector<std::uint8_t> CoverCell;  // 셀 중심이 은신처 원 안
		std::vector<double> Blur;             // 관측 0 (반경 see_r 상자 평균)
		std::vector<double> GradX;            // 조향 기울기 (반경 GradBlur 상자 평균의 np.gradient)
		std::vector<double> GradY;
		std::vector<double> Sat;              // 작업 버퍼
		std::vector<double> Tmp;
		std::vector<double> Tmp2;
		std::vector<double> Demand;

		/** world._cell_index: ix = clip(int(x · (1/cell)), 0, gw − 1). 반환은 iy·Gw + ix. */
		std::int32_t CellOf(const FVec2& P) const
		{
			const double K = 1.0 / Cell;
			const std::int32_t Ix = Detail::ClampI(static_cast<std::int32_t>(P.X * K), 0, Gw - 1);
			const std::int32_t Iy = Detail::ClampI(static_cast<std::int32_t>(P.Y * K), 0, Gw - 1);
			return Iy * Gw + Ix;
		}

		double FoodAt(const FVec2& P) const { return Food[static_cast<size_t>(CellOf(P))]; }
		double BlurAt(const FVec2& P) const { return Blur[static_cast<size_t>(CellOf(P))]; }

		FVec2 GradAt(const FVec2& P) const
		{
			const size_t k = static_cast<size_t>(CellOf(P));
			return EcoRepertoireV3::Normalize({GradX[k], GradY[k]});
		}

		double Total() const
		{
			double S = 0.0;
			for (const double F : Food)
			{
				S += F;
			}
			return S;
		}

		/** 세계 생성 (world._build_world 먹이·은신처 셀·재생률). 잡음은 행 우선(iy, ix)으로 Gw² 개를 뽑는다. */
		void Build(const FWorldConfig& C, FRng& Rng)
		{
			Cell = C.FoodCell > 0.0 ? C.FoodCell : 2.0;
			GradBlur = C.FoodGradBlur;
			Gw = static_cast<std::int32_t>(std::ceil(C.WorldSize / Cell));
			Gw = Gw < 1 ? 1 : Gw;
			const size_t Cells = static_cast<size_t>(Gw) * Gw;

			std::vector<double> Noise(Cells);
			for (double& V : Noise)
			{
				V = Rng.NextU01();
			}
			std::vector<double> M;
			Detail::BuildSat(Noise, Gw, Sat, Tmp);
			Detail::BoxMean(Sat, Gw, C.FoodPatchBlur > 1 ? C.FoodPatchBlur : 1, M);
			double Lo = M[0], Hi = M[0];
			for (const double V : M)
			{
				Lo = V < Lo ? V : Lo;
				Hi = V > Hi ? V : Hi;
			}
			const double Den = (Hi - Lo) > EcoRepertoireV3::kEps ? (Hi - Lo) : EcoRepertoireV3::kEps;
			const double Th = C.FoodPatchThreshold;
			Cap.assign(Cells, 0.0);
			for (size_t k = 0; k < Cells; ++k)
			{
				const double Mn = (M[k] - Lo) / Den;
				const double V = (Mn - Th) / (1.0 - Th);
				Cap[k] = V < 0.0 ? 0.0 : (V > 1.0 ? 1.0 : V);
			}
			Food = Cap;

			CoverCell.assign(Cells, 0);
			Regen.assign(Cells, 0.0);
			for (std::int32_t y = 0; y < Gw; ++y)
			{
				const double Cy = (static_cast<double>(y) + 0.5) * Cell;
				for (std::int32_t x = 0; x < Gw; ++x)
				{
					const double Cx = (static_cast<double>(x) + 0.5) * Cell;
					bool bIn = false;
					for (const EcoObservationV3::FCoverInput& Cv : C.Covers)
					{
						const double Dx = Cx - Cv.X;
						const double Dy = Cy - Cv.Y;
						bIn = bIn || (Dx * Dx + Dy * Dy <= Cv.Radius * Cv.Radius);
					}
					const size_t k = static_cast<size_t>(y) * Gw + x;
					CoverCell[k] = bIn ? 1 : 0;
					Regen[k] = C.FoodRegenBase * C.FoodRegenMult * (bIn ? C.FoodCoverRegenMult : 1.0);
				}
			}
			ComputeFields(EcoObservationV3::kR1bObsConfig.SeeR);
		}

		/** world._food_fields: 관측 0 의 blur(반경 round(see_r ÷ cell) = 10셀)와 조향 기울기(반경 GradBlur 셀). */
		void ComputeFields(double SeeR)
		{
			Detail::BuildSat(Food, Gw, Sat, Tmp);
			const std::int32_t Rb = static_cast<std::int32_t>(std::lround(SeeR / Cell));
			Detail::BoxMean(Sat, Gw, Rb > 1 ? Rb : 1, Blur);
			Detail::BoxMean(Sat, Gw, GradBlur > 1 ? GradBlur : 1, Tmp2);
			Detail::Gradient(Tmp2, Gw, GradX, GradY);
		}

		/** 먹이 재생 (world.step 7): food ← clip(food + regen·(cap − food), 0, cap). */
		void Regrow()
		{
			for (size_t k = 0; k < Food.size(); ++k)
			{
				const double F = Food[k] + Regen[k] * (Cap[k] - Food[k]);
				Food[k] = F < 0.0 ? 0.0 : (F > Cap[k] ? Cap[k] : F);
			}
		}
	};

	// ---- 개체 상태 (Mass 조각 하나가 하나씩 담는다) ----

	/** 초식 몸 (FEcoHerbivoreBodyV3Fragment). 파이썬 단위. */
	struct FHerbBody
	{
		std::uint32_t Slot = 0;              // 파리티 모드 슬롯 (계약 12-3)
		std::uint32_t Generation = 0;        // 그 슬롯의 리스폰 횟수
		FVec2 Pos;
		FVec2 Head{1.0, 0.0};
		FVec2 PrevPos;                       // 이번 스텝 이동 전 위치 (화면 보간 전용). 리스폰이면 새 위치
		double Energy = 0.5;                 // E (max_energy 1)
		std::int32_t ReproCd = 0;
		std::int32_t DeathCause = kDeathNone; // 이번 스텝 사망 (리스폰한 뒤에도 남긴다 — 기록용)
		std::int32_t CaughtBy = -1;          // 잡은 위협 슬롯 (가장 낮은 색인)
		FVec2 DeathPos;
		bool bReproduced = false;
		bool bRespawned = false;
		double LastIntake = 0.0;             // 이번 스텝 C4 에서 먹은 먹이 (먹이 단위 = 셀에서 덜어 낸 몫, 에너지는 × 0.5). 기록·표시 전용 — 다른 계산에 쓰지 않는다
		// 야생 (w1) 지방 비축 (FWorldConfig::WildReserve 를 켠 세계만. 끄면 늘 0·거짓)
		double Reserve = 0.0;                // 비축 R (0~1, × 용량 FWorldState::ReserveCap = E 단위)
		bool bWeak = false;                  // 이번 스텝 첫머리 E < WeakE (이동 속도 × WeakSpeed)
	};

	/** 스텝 끝 지각 (FEcoPerceptionCacheFragment). 다음 스텝의 결정 관측·제어 입력이다. */
	struct FHerbPerception
	{
		EcoObservationV3::FThreatPerception Threat;
		EcoObservationV3::FKinPerception Kin;
		EcoObservationV3::FCoverPerception Cover;
		double FoodDensity = 0.0;
		FVec2 FoodGrad;
		float Obs[EcoObservationV3::kObsDim] = {};
	};

	/** 요청과 결정 기록 (FEcoBehaviorStateFragment 안). */
	struct FHerbDecision
	{
		EcoRepertoireV3::FDecisionObs DecisionObs;   // 다음 Commit 의 결정 관측 (지난 스텝 끝 기하 + 그때 에너지·어둠)
		EcoRepertoireV3::FArbiterPrep Prep;          // Prepare 결과 (a~e)
		std::int32_t Request = EcoRepertoireV3::kGraze;
		std::uint8_t Feasible[EcoRepertoireV3::kNumBehaviors] = {};
		std::uint8_t Mask[EcoRepertoireV3::kNumBehaviors] = {};
		float Logits[EcoRepertoireV3::kNumBehaviors] = {};
		bool bPrepared = false;

		// 이번 스텝 Commit 기록 (시험·디버그)
		EcoRepertoireV3::FArbiterResult Result;
		std::int32_t PrevBehavior = EcoRepertoireV3::kGraze;
		std::int32_t ExecutedBehavior = EcoRepertoireV3::kGraze;   // Commit 뒤 행동 (이 스텝에 실행한 행동. 리스폰이 RepState 를 지워도 남는다)
		std::int32_t CommittedRequest = EcoRepertoireV3::kGraze;
		bool bCommittedReads = false;
		std::uint8_t CommittedMask[EcoRepertoireV3::kNumBehaviors] = {};

		// 도주 반사 거리 (FWorldConfig::WildFlight 를 켠 세계만 쓴다. 끄면 늘 기본값)
		std::int32_t KeepMode = kKeepNone;     // 다음 스텝에 쓸 덮기 (스텝 끝 H 의 UpdateWildFlight 가 정한다)
		std::int32_t KeepActive = kKeepNone;   // 이번 스텝에 실행한 덮기 (화면·기록)
		FVec2 KeepDir;                         // 경계·도주 방향 (단위벡터, 스텝 끝 기하. 없으면 0)
		std::int32_t KeepPanicSteps = 0;       // 이번 도망이 이어진 스텝 수
	};

	/** 위협 하나 (FEcoThreatStateFragment). */
	struct FThreatAgent
	{
		std::uint32_t Slot = 0;
		EcoThreatV3::FThreatSpec Spec;
		EcoThreatV3::FThreatState State;
		EcoThreatV3::FThreatStepResult Last;   // 이번 스텝 결과 (디버그·기록)
		EcoThreatV3::FNightUpdateResult LastNight;   // 이번 스텝 끝 밤잠 업데이트 결과 (밤잠 점진화를 켰을 때만, 디버그·기록)
		double PrevX = 0.0;                    // 이번 스텝 이동 전 위치 (화면 보간 전용)
		double PrevY = 0.0;
	};

	/** 초식 하나의 상태 보기 (소유하지 않는다). Mass 는 조각 안을, 기준 루프는 배열 칸을 가리킨다. */
	struct FHerbView
	{
		EcoRepertoireV3::FRepState* Rep = nullptr;
		FHerbDecision* Decision = nullptr;
		FHerbBody* Body = nullptr;
		FHerbPerception* Perception = nullptr;
		EcoRepertoireV3::FControlOutput* Control = nullptr;

		bool IsValid() const { return Rep && Decision && Body && Perception && Control; }
	};

	/** 누적 기록 (서버 로그·시험). 개체·스텝 단위. */
	struct FWorldStats
	{
		std::int64_t Steps = 0;
		std::int64_t BehaviorSteps[EcoRepertoireV3::kNumBehaviors] = {};   // Commit 뒤 행동별 개체·스텝
		std::int64_t Entries[EcoRepertoireV3::kNumBehaviors] = {};         // 행동 진입 (전환) 수
		std::int64_t Decisions = 0;          // 요청을 읽은 수 (reads)
		std::int64_t Caught = 0;
		std::int64_t Starved = 0;            // 굶어 죽음 (같은 스텝에 잡힌 개체는 빼고)
		std::int64_t Reproduced = 0;
		std::int64_t MaskViolations = 0;     // 마스크가 막은 행동이 실행됐다 (늘 0 이어야 한다)
		std::int64_t BlockedHerbMoves = 0;   // 이동 제약 콜백이 막은 사슴 이동 (통합 모드만. 평면 맵은 늘 0)
		std::int64_t BlockedThreatMoves = 0; // 이동 제약 콜백이 막은 위협 이동
		// 섭식 기록 (통합 모드 화면·기록용. 논리에 쓰지 않으므로 평면 맵·기준 루프의 상태는 그대로다)
		double FoodEaten = 0.0;              // 누적 먹은 먹이 (먹이 단위, C4 에서 셀마다 덜어 낸 양의 셀 순서 합)
		std::int64_t EatSteps = 0;           // 실제로 먹은 개체·스텝 (먹은 양 > 0)
		// 늑대 밤잠 점진화 기록 (켰을 때만 센다. world.py realism_stats 의 같은 이름 칸)
		std::int64_t NightSettleStarts = 0;  // 눕기 시작 (settle_n)
		std::int64_t NightSettleAborts = 0;  // 눕다가 다시 일어남 (settle_abort_n)
		std::int64_t NightOnsets = 0;        // 잠듦 (onset_n)
		std::int64_t NightWakes = 0;         // 깸 (wake_n)
		std::int64_t NightBlockDeer = 0;     // 누울 차례인데 사슴이 가까워 못 누운 늑대·업데이트 (block_deer_n)
		std::int64_t NightBlockHunt = 0;     // 누울 차례인데 사냥 중이라 못 누운 늑대·업데이트 (block_hunt_n)
		std::int64_t NightDarkUpdates = 0;   // 어둠(d ≥ 0.5) 업데이트의 주행성 늑대·업데이트
		std::int64_t NightDarkAwake = 0;     // 그중 깨어 있음 (눕는 중 포함). 비율 = dark_awake_frac
		// 도주 반사 거리 기록 (켰을 때만 센다)
		std::int64_t KeepSteps[kNumKeepModes] = {};   // 덮기별 개체·스텝 (0 = 두뇌)
		std::int64_t KeepAlertStarts = 0;    // 경계(멀어짐) 시작
		std::int64_t KeepPanicStarts = 0;    // 도망 시작
		std::int64_t KeepShelterStarts = 0;  // 은신처 웅크림 시작
		std::int64_t KeepPanicEnds = 0;      // 끝난 도망 (안전 거리 밖 또는 은신처)
		std::int64_t KeepPanicEndShelter = 0; // 그중 은신처에서 끝남
		std::int64_t KeepPanicEndSteps = 0;  // 끝난 도망의 길이 합 (스텝)
		std::int64_t KeepPanicDied = 0;      // 도망 중 죽음 (잡힘·굶음)
		std::int64_t CaughtByKeep[kNumKeepModes] = {};   // 잡힌 사슴을 그 스텝의 덮기로 가른 수
		// 야생 (w1) 지방 비축 기록 (켰을 때만 센다. world.py wild_stats 의 같은 이름 칸)
		double ReserveUsed = 0.0;            // 비축에서 꺼내 쓴 에너지 합 (E 단위, reserve_used)
		double ReserveRefill = 0.0;          // 비축으로 옮긴 에너지 합 (reserve_refill)
		std::int64_t ReserveLiveSteps = 0;   // 비축을 적용한 개체·스텝
		std::int64_t WeakSteps = 0;          // 그중 약한 개체·스텝 (스텝 첫머리 E < WeakE)
		std::int64_t WeakCaught = 0;         // 약한 채로 잡힌 수
		// 야생 (w2) 늑대 포만 기록 (켰을 때만, 플레이어형 빼고. world.py wild_stats sated_frac·eating_frac·wolf_kills_n)
		std::int64_t WolfSteps = 0;          // 늑대·스텝
		std::int64_t WolfSatedSteps = 0;     // 그중 배불러 쉼
		std::int64_t WolfEatingSteps = 0;    // 그중 먹는 중 (쿨다운 줄인 뒤 > 0)
		std::int64_t WolfKills = 0;          // 포만을 건 포획
	};

	/**
	 * 이동 제약 콜백 (통합 모드의 지형·장애물). 엔진 무관 — 함수 포인터와 사용자 자료만 받는다. nullptr 이면 지금과 같다.
	 * Index 는 이번 Step 에 넘긴 배열의 색인이다. From = 이번 스텝 이동 전, To = 맵 벽 처리 뒤 자리 (파이썬 단위).
	 * 참이면 통과, 거짓이면 막힘 — 그 개체는 이번 스텝 이동 전 자리에 남는다 (학습 세계에는 없는 막힘. 근사로 기록한다).
	 * 움직이지 않은 개체(From == To)는 부르지 않는다.
	 */
	struct FStepHooks
	{
		void* User = nullptr;
		bool (*HerbMove)(void* User, std::int32_t Index, const FVec2& From, const FVec2& To) = nullptr;
		bool (*ThreatMove)(void* User, std::int32_t Index, double FromX, double FromY, double ToX, double ToY) = nullptr;
	};

	/** 세계 상태 (Mass 경로는 UEcoPolicyV3Subsystem 이 하나 가진다). */
	struct FWorldState
	{
		FWorldConfig Config;
		EcoRepertoireV3::FRepertoireConfig RepCfg;
		EcoObservationV3::FObservationConfig ObsCfg;
		EcoThreatV3::FThreatConfig ThreatCfg;
		// 실제 허용 행동 칸 = 모델 kAllowedMask ∧ Config.WorldAllowed (InitWorld 가 정한다). DecideHerb 의 마스크가 이 칸을 쓴다
		std::uint8_t Allowed[EcoRepertoireV3::kNumBehaviors] = {EcoPolicyV3::kAllowedMask[0], EcoPolicyV3::kAllowedMask[1],
																 EcoPolicyV3::kAllowedMask[2], EcoPolicyV3::kAllowedMask[3],
																 EcoPolicyV3::kAllowedMask[4]};
		FFoodGrid Food;
		FRng Rng;
		std::int64_t T = 0;                  // 전역 스텝 번호 (계약 10-1: 모든 개체가 같은 스텝)
		double Dark = 0.0;                   // d(t)
		std::int32_t StepsToTransition = -1; // r (낮 고정이면 -1 → to_transition 1)
		double PredEma = 0.0;                // 전역 피식 EMA
		double ReserveCap = 0.0;             // 야생 (w1) 비축 용량 C (E 단위, InitWorld 가 정한다. 끄면 0)
		FWorldStats Stats;
		std::vector<EcoObservationV3::FThreatInput> ExternalThreats;
		std::vector<FVec2> StepCatches;      // 이번 스텝에 잡힌 자리 (디버그)

		// 작업 버퍼 (스텝마다 다시 쓴다)
		std::vector<EcoObservationV3::FThreatInput> ThreatIn;
		std::vector<EcoObservationV3::FKinInput> KinIn;
		std::vector<EcoThreatV3::FPreyView> Prey;
		std::vector<double> Rolls;
		std::vector<std::int32_t> CaughtByThreat;
		std::vector<std::int32_t> Catcher;
		std::vector<double> Want;
		std::vector<double> EDrained;
		std::vector<std::int32_t> CellIdx;
	};

	// ---- 세계 생성·낮밤 ----

	/** 새 t 의 어둠 (계약 7-6). 낮 고정이면 d = 0, r = -1. */
	inline void UpdateDayNight(FWorldState& W)
	{
		if (W.Config.DayPeriod > 0)
		{
			const EcoObservationV3::FDayNight Dn =
				EcoObservationV3::DayNightPhase(W.T, W.Config.DayPeriod, W.Config.DayOffset, W.Config.TwilightSteps);
			W.Dark = Dn.Dark;
			W.StepsToTransition = Dn.StepsToTransition;
		}
		else
		{
			W.Dark = 0.0;
			W.StepsToTransition = -1;
		}
	}

	/** 세계 생성 (world.reset 의 세계 부분): 설정·계수·난수·먹이 격자·t = 0 의 어둠. 개체는 InitHerb·InitThreat 가 만든다. */
	inline void InitWorld(FWorldState& W, const FWorldConfig& C)
	{
		W = FWorldState();
		W.Config = C;
		if (W.Config.DayPeriod > 0 && W.Config.TwilightSteps <= 0)
		{
			const std::int32_t Tw = static_cast<std::int32_t>(std::lround(0.05 * W.Config.DayPeriod));
			W.Config.TwilightSteps = Tw > 1 ? Tw : 1;
		}
		W.RepCfg = EcoRepertoireV3::kR1bConfig;
		W.ObsCfg = EcoObservationV3::kR1bObsConfig;
		W.ThreatCfg = EcoThreatV3::FThreatConfig();
		W.ThreatCfg.bRealismNight = C.bRealismNight;
		if (C.PredEatCdOverride > 0)
		{
			W.ThreatCfg.PredEatCd = C.PredEatCdOverride;
		}
		W.ThreatCfg.bEatInPlace = C.bEatInPlace;
		// 야생 (w1): 하루 단위 계수라 낮 고정 세계에서는 끈다 (파이썬 _wild_reserve_params 가 daynight 없이 켜기를 거부한다)
		W.Config.WildReserve.bEnabled = C.WildReserve.bEnabled && W.Config.DayPeriod > 0;
		W.ReserveCap = W.Config.WildReserve.bEnabled
						   ? WildReserveCapacity(W.Config.WildReserve, W.Config.DayPeriod, W.RepCfg.EnergyDrain) : 0.0;
		// 야생 (w2) 늑대 포만: 하루 단위 배부름을 이 세계의 하루 스텝으로 (파이썬도 daynight 없이 켤 수 없다)
		W.Config.WildSatiation.bEnabled = C.WildSatiation.bEnabled && W.Config.DayPeriod > 0;
		W.ThreatCfg.bWildSatiation = W.Config.WildSatiation.bEnabled;
		W.ThreatCfg.SatSteps = W.Config.WildSatiation.bEnabled ? WildDaysToSteps(C.WildSatiation.SatDays, W.Config.DayPeriod) : 0;
		W.ThreatCfg.RestSpeed = C.WildSatiation.RestSpeed;
		// R3 감지: 위협 시야 문턱 cos·발소리 반경 자르기 (끄면 R1b 그대로 — FovCos 와 같은 값)
		W.ObsCfg.ThreatFovCos = C.RealismVision.bEnabled ? EcoObservationV3::FovCosOf(C.RealismVision.ThreatFovDeg, kBaseFovDeg, W.ObsCfg.FovCos)
														 : W.ObsCfg.FovCos;
		W.ObsCfg.bHearCapToSight = C.RealismHearing.bEnabled && C.RealismHearing.bCapToSight;
		for (std::int32_t b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
		{
			W.Allowed[b] = (EcoPolicyV3::kAllowedMask[b] != 0 && C.WorldAllowed[b] != 0) ? 1 : 0;
		}
		W.Rng.State = EcoRepertoireV3::HashChain3(kWorldRngTag, static_cast<std::uint64_t>(C.Seed), C.RngStream);
		W.Food.Build(W.Config, W.Rng);
		W.T = 0;
		W.PredEma = 0.0;
		UpdateDayNight(W);
	}

	/** 처음 나는 초식 (reset): 맵 균등 위치·무작위 heading·E 0.5·GRAZE 진입, 개체 키 = (슬롯, 세대 0). */
	inline void InitHerb(FWorldState& W, std::uint32_t Slot, const FHerbView& H)
	{
		const double Size = W.Config.WorldSize;
		*H.Body = FHerbBody();
		H.Body->Slot = Slot;
		H.Body->Generation = 0;
		H.Body->Pos = {W.Rng.Uniform(0.0, Size), W.Rng.Uniform(0.0, Size)};
		const double A = W.Rng.Uniform(0.0, 2.0 * 3.14159265358979323846);
		H.Body->Head = {std::cos(A), std::sin(A)};
		H.Body->PrevPos = H.Body->Pos;
		H.Body->Energy = W.RepCfg.InitEnergy;
		H.Body->ReproCd = 0;
		H.Body->Reserve = W.Config.WildReserve.bEnabled ? W.Config.WildReserve.Init : 0.0;   // 야생 (w1): 시작·새 개체 비축
		*H.Decision = FHerbDecision();
		*H.Perception = FHerbPerception();
		*H.Control = EcoRepertoireV3::FControlOutput();
		const double E01 = H.Body->Energy / W.RepCfg.MaxEnergy;
		EcoRepertoireV3::InitAgent(*H.Rep, E01 < 0.0 ? 0.0 : (E01 > 1.0 ? 1.0 : E01), W.Dark, W.Config.Seed,
								   EcoRepertoireV3::MakeAgentKey(Slot, 0), W.RepCfg);
	}

	/** 슬롯 번호로 위협 성질을 정한다 (잠행형 → 근접 추격형 → 원거리형 → 플레이어). 야행성은 보통 위협 슬롯 끝에서부터. */
	inline EcoThreatV3::FThreatSpec ThreatSpecForSlot(const FWorldState& W, std::int32_t Slot)
	{
		const FWorldConfig& C = W.Config;
		const std::int32_t NumBase = C.NumBaseThreats();
		if (Slot >= NumBase)
		{
			return EcoThreatV3::MakePlayerSpec(W.ThreatCfg);
		}
		const bool bNocturnal = Slot >= NumBase - C.NumNocturnal;
		if (Slot < C.NumStalkers)
		{
			return EcoThreatV3::MakeStalkerSpec(C.PredSpeedMult, bNocturnal, W.ThreatCfg);
		}
		const bool bRanged = Slot >= C.NumStalkers + C.NumChasers;
		return EcoThreatV3::MakeChaserSpec(C.PredSpeedMult, bRanged, bNocturnal, W.ThreatCfg);
	}

	/** 밤잠 점진화의 늑대별 지연 최대 ⌊spread × τ⌋ (낮 고정 세계는 0 — world.py `_rz_night_update` fresh 의 tw = 0). */
	inline std::int32_t NightMaxDelay(const FWorldState& W)
	{
		return W.Config.DayPeriod > 0 ? EcoThreatV3::NightMaxDelay(W.Config.TwilightSteps, W.ThreatCfg) : 0;
	}

	/**
	 * 위협의 처음 잠 상태. 밤잠 점진화를 켜면 NightInit (지연 = H(606, 세계 Seed, NightSlot) — 파이썬은 위협 슬롯 번호),
	 * 끄면 지금 어둠의 IsAsleep 훅 그대로.
	 */
	inline void InitThreatSleep(const FWorldState& W, FThreatAgent& A, std::int64_t NightSlot)
	{
		if (W.ThreatCfg.bRealismNight)
		{
			EcoThreatV3::NightInit(A.Spec, A.State, W.Dark, EcoThreatV3::NightDelayOf(W.Config.Seed, NightSlot, NightMaxDelay(W)),
								   W.ThreatCfg);
		}
		else
		{
			A.State.bAsleep = EcoThreatV3::IsAsleep(A.Spec, W.Dark, W.ThreatCfg);
		}
	}

	/** 지금 잠 (관측의 '굴에서 자는 위협은 안 보인다'). 켜면 늑대별 상태, 끄면 새 t 의 어둠으로 다시 판정한다. */
	inline bool ThreatAsleepNow(const FWorldState& W, const FThreatAgent& A)
	{
		return EcoThreatV3::IsAsleepNow(A.Spec, A.State, W.Dark, W.ThreatCfg);
	}

	/** 처음 나는 위협: 맵 균등 위치·무작위 heading·지난 변위 0, 플레이어는 첫 모드를 고른다. */
	inline void InitThreat(FWorldState& W, std::uint32_t Slot, FThreatAgent& A)
	{
		const double Size = W.Config.WorldSize;
		A = FThreatAgent();
		A.Slot = Slot;
		A.Spec = ThreatSpecForSlot(W, static_cast<std::int32_t>(Slot));
		A.State.PosX = W.Rng.Uniform(0.0, Size);
		A.State.PosY = W.Rng.Uniform(0.0, Size);
		const double Ang = W.Rng.Uniform(0.0, 2.0 * 3.14159265358979323846);
		A.State.HeadX = std::cos(Ang);
		A.State.HeadY = std::sin(Ang);
		InitThreatSleep(W, A, static_cast<std::int64_t>(Slot));
		if (A.Spec.Type == EcoThreatV3::EThreatType::Player)
		{
			const double U0 = W.Rng.NextU01();
			const double U1 = W.Rng.NextU01();
			EcoThreatV3::PickPlayerMode(A.State, U0, U1, W.ThreatCfg);
		}
		A.PrevX = A.State.PosX;
		A.PrevY = A.State.PosY;
	}

	// ---- 통합 모드 입양 (세계 난수를 쓰지 않는다 — 팀 조정자가 이미 정한 자리·방향을 받는다) ----

	namespace Detail
	{
		inline double Clamp0(double V, double Hi) { return V < 0.0 ? 0.0 : (V > Hi ? Hi : V); }
	}

	/**
	 * 통합 모드의 새 초식 (계약 12-3): 주어진 위치(맵 안으로 자름)·heading·개체 키, E 0.5, GRAZE 진입, seq 0.
	 * AgentKey = MakeAgentKeyFromStableId(StableAgentId), Seed = 세계 설정의 Seed(세션 시드). Slot·Generation 은 0 으로 둔다(쓰지 않는다).
	 * 첫 관측·첫 요청은 ObserveAndDecideRows 로 만든다.
	 */
	inline void AdoptHerb(FWorldState& W, const FHerbView& H, const FVec2& Pos, const FVec2& Head, std::uint64_t AgentKey)
	{
		const double Size = W.Config.WorldSize;
		*H.Body = FHerbBody();
		H.Body->Pos = {Detail::Clamp0(Pos.X, Size), Detail::Clamp0(Pos.Y, Size)};
		const FVec2 Hn = EcoRepertoireV3::Normalize(Head);
		H.Body->Head = EcoRepertoireV3::IsNonZero(Hn) ? Hn : FVec2{1.0, 0.0};
		H.Body->PrevPos = H.Body->Pos;
		H.Body->Energy = W.RepCfg.InitEnergy;
		H.Body->ReproCd = 0;
		H.Body->Reserve = W.Config.WildReserve.bEnabled ? W.Config.WildReserve.Init : 0.0;   // 야생 (w1): 시작·새 개체 비축
		*H.Decision = FHerbDecision();
		*H.Perception = FHerbPerception();
		*H.Control = EcoRepertoireV3::FControlOutput();
		const double E01 = H.Body->Energy / W.RepCfg.MaxEnergy;
		EcoRepertoireV3::InitAgent(*H.Rep, E01 < 0.0 ? 0.0 : (E01 > 1.0 ? 1.0 : E01), W.Dark, W.Config.Seed, AgentKey, W.RepCfg);
	}

	/**
	 * 통합 모드의 새 위협: 주어진 성질(잠행·추격, 야행성, 속력)·위치·heading. 플레이어 대역은 쓰지 않는다(모드 난수가 필요하다).
	 * NightSlot = 밤잠 점진화의 늑대별 지연 해시 키 (파이썬은 위협 슬롯 번호. 통합 모드는 늑대 StableAgentId). 끄면 쓰지 않는다.
	 */
	inline void AdoptThreat(FWorldState& W, FThreatAgent& A, const EcoThreatV3::FThreatSpec& Spec, double PosX, double PosY,
							double HeadX, double HeadY, std::int64_t NightSlot = 0)
	{
		const double Size = W.Config.WorldSize;
		A = FThreatAgent();
		A.Spec = Spec;
		A.State.PosX = Detail::Clamp0(PosX, Size);
		A.State.PosY = Detail::Clamp0(PosY, Size);
		double Hx = HeadX;
		double Hy = HeadY;
		EcoThreatV3::Normalize2(Hx, Hy);
		const bool bHead = Hx != 0.0 || Hy != 0.0;
		A.State.HeadX = bHead ? Hx : 1.0;
		A.State.HeadY = bHead ? Hy : 0.0;
		InitThreatSleep(W, A, NightSlot);
		A.PrevX = A.State.PosX;
		A.PrevY = A.State.PosY;
	}

	// ---- 관측 (계약 2-1 의 4~7) ----

	namespace Detail
	{
		inline void BuildThreatInputs(FWorldState& W, FThreatAgent* const* Threats, std::int32_t M)
		{
			W.ThreatIn.resize(static_cast<size_t>(M));
			for (std::int32_t m = 0; m < M; ++m)
			{
				const FThreatAgent& A = *Threats[m];
				EcoObservationV3::FThreatInput& In = W.ThreatIn[static_cast<size_t>(m)];
				In.X = A.State.PosX;
				In.Y = A.State.PosY;
				In.VelX = A.State.VelX;
				In.VelY = A.State.VelY;
				In.bAsleep = ThreatAsleepNow(W, A);   // 굴에서 자면 안 보인다 (끄면 새 t 의 어둠으로 다시 판정, 켜면 늑대별 상태)
				// R3 발소리 (켰을 때만): 지난 스텝 변위 크기 ÷ 사슴 걸음과 그 스텝의 걸음새 (world.py hearing_radius·pred_running)
				In.HearR = W.Config.RealismHearing.bEnabled
							   ? EcoObservationV3::HearingRadius(W.Config.RealismHearing,
																 std::sqrt(A.State.VelX * A.State.VelX + A.State.VelY * A.State.VelY) / W.ObsCfg.HerbSpeed,
																 A.Last.bRunning)
							   : 0.0;
			}
			W.ThreatIn.insert(W.ThreatIn.end(), W.ExternalThreats.begin(), W.ExternalThreats.end());
		}

		inline void BuildKinInputs(FWorldState& W, const FHerbView* Herbs, std::int32_t N)
		{
			W.KinIn.resize(static_cast<size_t>(N));
			for (std::int32_t i = 0; i < N; ++i)
			{
				EcoObservationV3::FKinInput& K = W.KinIn[static_cast<size_t>(i)];
				K.X = Herbs[i].Body->Pos.X;
				K.Y = Herbs[i].Body->Pos.Y;
				K.Behavior = Herbs[i].Rep->Behavior;
			}
		}

		/** 개체 하나의 스텝 끝 지각 + Perceive + 관측 18. 입력 목록(ThreatIn·KinIn)과 먹이 장은 미리 만들어 둔다. */
		inline void ObserveHerb(FWorldState& W, const FHerbView& H, std::int32_t Self, std::int32_t N, std::int32_t M)
		{
			FHerbPerception& P = *H.Perception;
			const FHerbBody& B = *H.Body;
			EcoRepertoireV3::FRepState& S = *H.Rep;
			const EcoObservationV3::FObservationConfig& OC = W.ObsCfg;

			P.Threat = EcoObservationV3::PerceiveThreats(B.Pos, B.Head, EcoObservationV3::SeePredRadius(W.Dark, OC), S.SeeMult,
														 S.SeeMultLast, W.ThreatIn.data(), static_cast<std::int32_t>(W.ThreatIn.size()), OC);
			P.Kin = EcoObservationV3::PerceiveKin(Self, B.Pos, B.Head, W.KinIn.data(), N, OC);
			P.Cover = EcoObservationV3::PerceiveCover(B.Pos, W.Config.Covers.data(),
													  static_cast<std::int32_t>(W.Config.Covers.size()), OC);
			P.FoodDensity = W.Food.BlurAt(B.Pos);
			P.FoodGrad = W.Food.GradAt(B.Pos);
			EcoRepertoireV3::Perceive(S, P.Threat.PredCount, P.Threat.AwayFromPred, W.RepCfg);

			EcoObservationV3::FObservationInput In;
			In.FoodDensity = P.FoodDensity;
			In.PredCount = P.Threat.PredCount;
			In.DPredMin = P.Threat.DPredMin;
			In.KinCount = P.Kin.KinCount;
			In.Energy = B.Energy;
			In.PredEma = W.PredEma;
			In.bHasCover = !W.Config.Covers.empty();
			In.CoverEdge = P.Cover.Edge;
			In.Dark = W.Dark;
			In.StepsToTransition = W.StepsToTransition;
			In.PredApproach = P.Threat.PredApproach;
			In.KinAlarm = P.Kin.KinAlarm;
			In.Behavior = S.Behavior;
			In.StepsIn = S.StepsIn;
			In.Recency = S.Recency;
			EcoObservationV3::BuildObservation(In, P.Obs, OC);
		}
	}

	/** 모든 초식의 스텝 끝 관측 (먹이 장을 새로 만든다). reset 과 스텝 E~F. */
	inline void ObserveAll(FWorldState& W, const FHerbView* Herbs, std::int32_t N, FThreatAgent* const* Threats, std::int32_t M)
	{
		W.Food.ComputeFields(W.ObsCfg.SeeR);
		Detail::BuildThreatInputs(W, Threats, M);
		Detail::BuildKinInputs(W, Herbs, N);
		for (std::int32_t i = 0; i < N; ++i)
		{
			Detail::ObserveHerb(W, Herbs[i], i, N, M);
		}
	}

	// ---- 다음 요청 (계약 5-6 Prepare → 마스크 → 망) ----

	/** 초식 하나의 다음 요청: 결정 관측 → Prepare → 가능·결정 마스크 → reads 면 망 argmax, 아니면 지금 행동. */
	inline void DecideHerb(FWorldState& W, const FHerbView& H, const EcoPolicyV3::FPolicyNetV3& Net = EcoPolicyV3::kBuiltinNet)
	{
		FHerbDecision& D = *H.Decision;
		EcoRepertoireV3::FRepState& S = *H.Rep;
		const FHerbPerception& P = *H.Perception;
		const double E01 = H.Body->Energy / W.RepCfg.MaxEnergy;
		D.DecisionObs = EcoObservationV3::ToDecisionObs(P.Threat, P.Cover, E01 < 0.0 ? 0.0 : (E01 > 1.0 ? 1.0 : E01), W.Dark);
		D.Prep = EcoRepertoireV3::Prepare(S, D.DecisionObs, W.RepCfg);
		if (W.Config.WildFlight.bEnabled && (D.KeepMode == kKeepPanic || D.KeepMode == kKeepShelter))
		{
			// 도주 반사 거리의 덮기(도주·웅크림): 두뇌(망)를 부르지 않는다. Prepare 는 위에서 돌렸다(사건 기준값·HIDE 도착을 지금 기하로 맞춘다).
			// 읽음을 꺼서 결정 수·마스크 기록에 들지 않게 하고, 요청 = 덮기 행동 (Commit 대신 CommitFlight 가 쓴다). 경계는 두뇌가 정한다
			D.Prep.bReads = false;
			D.Prep.bDecide = false;
			D.Prep.bWakeDecide = false;
			D.Request = D.KeepMode == kKeepShelter ? EcoRepertoireV3::kHide : EcoRepertoireV3::kFlee;
			for (std::int32_t b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
			{
				D.Feasible[b] = 0;
				D.Mask[b] = 0;
				D.Logits[b] = 0.0f;
			}
			D.bPrepared = true;
			return;
		}
		EcoPolicyV3::ComputeFeasibleMask(P.Obs, D.Feasible);
		// 허용 = 모델 ∧ 세계 (W.Allowed). 세계 칸이 모두 1 이면 kAllowedMask 그대로라 지금까지와 비트 단위로 같다
		EcoPolicyV3::ComposeActionMask(W.Allowed, D.Feasible, D.Prep.bReads, D.Prep.bWakeDecide, S.Behavior, D.Mask);
		if (D.Prep.bReads)
		{
			D.Request = EcoPolicyV3::RunPolicyV3(Net, P.Obs, D.Mask, D.Logits);
		}
		else
		{
			D.Request = S.Behavior;   // 읽지 않는다 — 파이썬은 망을 돌리지만 마스크가 지금 행동 한 칸이라 결과가 같다
			for (float& L : D.Logits)
			{
				L = 0.0f;
			}
		}
		D.bPrepared = true;
	}

	inline void DecideAll(FWorldState& W, const FHerbView* Herbs, std::int32_t N,
						  const EcoPolicyV3::FPolicyNetV3& Net = EcoPolicyV3::kBuiltinNet)
	{
		for (std::int32_t i = 0; i < N; ++i)
		{
			DecideHerb(W, Herbs[i], Net);
		}
	}

	/** 처음 관측과 첫 요청 (reset 끝). 스폰 직후 한 번 부른다. */
	inline void ObserveAndDecideAll(FWorldState& W, const FHerbView* Herbs, std::int32_t N, FThreatAgent* const* Threats,
									std::int32_t M, const EcoPolicyV3::FPolicyNetV3& Net = EcoPolicyV3::kBuiltinNet)
	{
		ObserveAll(W, Herbs, N, Threats, M);
		DecideAll(W, Herbs, N, Net);
	}

	/**
	 * 몇 행만 첫 관측과 첫 요청 (통합 모드 입양 직후). 동족·위협 목록은 넘긴 전체(Herbs·Threats)로 만든다.
	 * 다른 행의 지각·요청은 건드리지 않는다 (그 행들은 지난 스텝 H 에서 이미 준비됐다).
	 */
	inline void ObserveAndDecideRows(FWorldState& W, const FHerbView* Herbs, std::int32_t N, FThreatAgent* const* Threats,
									 std::int32_t M, const std::int32_t* Rows, std::int32_t NumRows,
									 const EcoPolicyV3::FPolicyNetV3& Net = EcoPolicyV3::kBuiltinNet)
	{
		W.Food.ComputeFields(W.ObsCfg.SeeR);
		Detail::BuildThreatInputs(W, Threats, M);
		Detail::BuildKinInputs(W, Herbs, N);
		for (std::int32_t r = 0; r < NumRows; ++r)
		{
			const std::int32_t i = Rows[r];
			if (i >= 0 && i < N)
			{
				Detail::ObserveHerb(W, Herbs[i], i, N, M);
			}
		}
		for (std::int32_t r = 0; r < NumRows; ++r)
		{
			const std::int32_t i = Rows[r];
			if (i >= 0 && i < N)
			{
				DecideHerb(W, Herbs[i], Net);
			}
		}
	}

	// ---- 한 결정 스텝 ----

	struct FStepReport
	{
		std::int32_t Caught = 0;
		std::int32_t Starved = 0;
		std::int32_t Reproduced = 0;
		std::int32_t Respawned = 0;
	};

	namespace Detail
	{
		/** 제어 입력 (world._rep_step inp). 기하는 지난 스텝 끝 지각, food_ok 는 결정 때 위치 셀의 섭식 전 먹이. */
		inline EcoRepertoireV3::FControlInput MakeControlInput(const FWorldState& W, const FHerbView& H)
		{
			const FHerbPerception& P = *H.Perception;
			const EcoRepertoireV3::FRepState& S = *H.Rep;
			const FHerbBody& B = *H.Body;
			EcoRepertoireV3::FControlInput In;
			In.FoodGrad = P.FoodGrad;
			In.ToCentroid = P.Kin.ToCentroid;
			In.Separation = P.Kin.Separation;
			In.AwayFromPred = P.Threat.AwayFromPred;
			In.PredCount = P.Threat.PredCount;
			const std::int32_t K = static_cast<std::int32_t>(W.Config.Covers.size());
			if (S.Behavior == EcoRepertoireV3::kHide && !S.bArrived && S.HideTarget >= 0 && S.HideTarget < K)
			{
				const EcoObservationV3::FCoverInput& Cv = W.Config.Covers[static_cast<size_t>(S.HideTarget)];
				In.ToTarget = EcoRepertoireV3::ToHideTarget(B.Pos, {Cv.X, Cv.Y});
			}
			In.bFoodOk = EcoRepertoireV3::IsFoodOk(W.Food.FoodAt(B.Pos), W.RepCfg);
			In.bInCover = H.Decision->DecisionObs.bInCover;
			In.Dark = W.Dark;
			return In;
		}

		inline bool InAnyCover(const FWorldState& W, const FVec2& P)
		{
			return EcoObservationV3::PerceiveCover(P, W.Config.Covers.data(), static_cast<std::int32_t>(W.Config.Covers.size()),
												   W.ObsCfg)
				.bInCover;
		}

		// ---- 야생 1단계 (w3) 도주 반사 거리 (FWorldConfig::WildFlight 를 켠 세계만 부른다) ----

		/** 사냥 중인 위협 (world.py `_wf_hunting`): 먹는 중(쿨다운)·잠·배부름이 아니고 플레이어 휴식 모드가 아니다. */
		inline bool FlightHunting(const FWorldState& W, const FThreatAgent& A)
		{
			return A.State.Cooldown == 0 && !ThreatAsleepNow(W, A) && (!W.ThreatCfg.bWildSatiation || A.State.SatLeft == 0)
				   && !(A.Spec.Type == EcoThreatV3::EThreatType::Player && A.State.PlayerMode == EcoThreatV3::EPlayerMode::Rest);
		}

		/**
		 * 스텝 끝(H, DecideAll 앞): 사슴마다 다음 스텝의 덮기·방향을 정한다 (world.py `_wf_update` 와 줄마다 같다). 지난 덮기 = 이번 스텝에
		 * 실행한 KeepActive. 알아챔은 E 의 관측과 같은 보임(W.ThreatIn — 시야·발소리·잠)을 위협마다 하나씩 다시 판정한다.
		 * 도주·웅크림이 풀리면 잠금 0·EvWait 지움. 이번 스텝에 죽은 사슴은 덮기를 지운다 (도주 중이었으면 '도주 중 죽음').
		 */
		inline void UpdateWildFlight(FWorldState& W, const FHerbView* Herbs, std::int32_t N, FThreatAgent* const* Threats, std::int32_t M)
		{
			namespace R3 = EcoRepertoireV3;
			const FWildFlightConfig& F = W.Config.WildFlight;
			const double Eps2 = R3::kEps * R3::kEps;
			const double SeePred = EcoObservationV3::SeePredRadius(W.Dark, W.ObsCfg);
			const double Size = W.Config.WorldSize;
			const std::int32_t K = static_cast<std::int32_t>(W.Config.Covers.size());
			constexpr std::int32_t kMaxM = 64;
			const std::int32_t Mc = M < kMaxM ? M : kMaxM;
			for (std::int32_t i = 0; i < N; ++i)
			{
				const FHerbView& H = Herbs[i];
				FHerbDecision& D = *H.Decision;
				R3::FRepState& S = *H.Rep;
				const std::int32_t Prev = D.KeepActive;
				if (H.Body->DeathCause != kDeathNone)
				{
					W.Stats.KeepPanicDied += Prev == kKeepPanic ? 1 : 0;
					D.KeepMode = kKeepNone;
					D.KeepDir = FVec2{};
					D.KeepPanicSteps = 0;
					if (H.Body->bRespawned)
					{
						D.KeepActive = kKeepNone;   // 새 세대 (평면 맵 부활 — 통합 모드는 부활하지 않는다)
					}
					continue;
				}
				const FVec2 P = H.Body->Pos;
				const bool bInCov = H.Perception->Cover.bInCover;
				bool bNoticedH = false, bAnyNr = false, bAnyNearH = false, bPanicNow = false;
				// 위협마다 판정을 먼저 모은다 (방향은 다음 덮기가 정해진 뒤 고른 늑대들로)
				bool Nh[kMaxM] = {}, Nr[kMaxM] = {}, NearH[kMaxM] = {};
				double Ex[kMaxM] = {}, Ey[kMaxM] = {}, Pd[kMaxM] = {}, Inv[kMaxM] = {};
				for (std::int32_t m = 0; m < Mc; ++m)
				{
					const FThreatAgent& A = *Threats[m];
					const bool bHunt = FlightHunting(W, A);
					const EcoObservationV3::FThreatInput& Ti = W.ThreatIn[static_cast<size_t>(m)];
					const bool bPv = EcoObservationV3::PerceiveThreats(P, H.Body->Head, SeePred, S.SeeMult, S.SeeMult, &Ti, 1, W.ObsCfg).PredCount == 1;
					Ex[m] = A.State.PosX - P.X;
					Ey[m] = A.State.PosY - P.Y;
					Pd[m] = std::sqrt(Ex[m] * Ex[m] + Ey[m] * Ey[m]);
					Inv[m] = 1.0 / (Pd[m] > R3::kEps ? Pd[m] : R3::kEps);
					const bool bAppr = EcoObservationV3::ApproachObs(A.State.VelX, A.State.VelY, Ex[m], Ey[m], Inv[m], W.ObsCfg) >= F.Approach;
					const bool bLocked = A.Last.bHasTarget && A.Last.Target == i;   // 이번 스텝 이 사슴을 쫓음 (world.py pred_target)
					const bool bComing = bHunt && (bLocked || bAppr);
					Nh[m] = bPv && bHunt && Pd[m] <= F.AlertR;
					Nr[m] = F.bRestAlert && bPv && !bHunt && Pd[m] <= F.AlertR;
					NearH[m] = bHunt && Pd[m] <= F.SafeR;
					bPanicNow = bPanicNow || (Nh[m] && (Pd[m] <= F.FlightR || bComing));
					bNoticedH = bNoticedH || Nh[m];
					bAnyNr = bAnyNr || Nr[m];
					bAnyNearH = bAnyNearH || NearH[m];
				}
				std::int32_t Next = kKeepNone;
				if (bInCov)
				{
					Next = (bNoticedH && F.bCrouch) ? kKeepShelter : kKeepNone;
				}
				else if ((Prev == kKeepPanic && bAnyNearH) || bPanicNow)
				{
					Next = kKeepPanic;
				}
				else if (bNoticedH || bAnyNr)
				{
					Next = kKeepAlert;
				}
				FVec2 Dir;
				if (Next == kKeepAlert || Next == kKeepPanic)
				{
					// 도주 = 안전 거리 안 사냥 중인 늑대들, 경계 = 알아챈 늑대들의 반대 (거리 역수 가중 합). 0 이면 가장 가까운 그 늑대 반대
					double Sx = 0.0, Sy = 0.0;
					std::int32_t J = -1;
					for (std::int32_t m = 0; m < Mc; ++m)
					{
						const bool bSel = Next == kKeepPanic ? NearH[m] : (Nh[m] || Nr[m]);
						if (!bSel)
						{
							continue;
						}
						const double Wt = 1.0 / (Pd[m] > 0.5 ? Pd[m] : 0.5);
						Sx += Ex[m] * Inv[m] * Wt;
						Sy += Ey[m] * Inv[m] * Wt;
						if (J < 0 || Pd[m] < Pd[J])
						{
							J = m;
						}
					}
					Dir = R3::Normalize(FVec2{-Sx, -Sy});
					if (!(Dir.X * Dir.X + Dir.Y * Dir.Y > Eps2) && J >= 0)
					{
						Dir = FVec2{-Ex[J] * Inv[J], -Ey[J] * Inv[J]};
					}
					if (Next == kKeepPanic && K > 0)
					{
						// 늑대 반대쪽(±acos(ShelterCos)) 은신처가 가장자리 ShelterR 안에 있으면 가장 가까운 그 은신처 중심 쪽 (동점 낮은 색인)
						std::int32_t Kb = -1;
						double Best = 0.0, Bvx = 0.0, Bvy = 0.0, Bdc = 1.0;
						for (std::int32_t k = 0; k < K; ++k)
						{
							const EcoObservationV3::FCoverInput& Cv = W.Config.Covers[static_cast<size_t>(k)];
							const double Vx = Cv.X - P.X;
							const double Vy = Cv.Y - P.Y;
							const double Dc = std::sqrt(Vx * Vx + Vy * Vy);
							const double Cs = (Vx * Dir.X + Vy * Dir.Y) / (Dc > R3::kEps ? Dc : R3::kEps);
							const double Em = Dc - Cv.Radius;
							if (Dc > R3::kEps && Em <= F.ShelterR && Cs >= F.ShelterCos && (Kb < 0 || Em < Best))
							{
								Kb = k;
								Best = Em;
								Bvx = Vx;
								Bvy = Vy;
								Bdc = Dc;
							}
						}
						if (Kb >= 0)
						{
							Dir = FVec2{Bvx / Bdc, Bvy / Bdc};
						}
					}
					// 무대 벽 여유 안이면 벽 쪽 성분을 지운다 (다 지워지면 그대로)
					const double Mg = F.WallMargin;
					FVec2 Sl = Dir;
					if ((P.X <= Mg && Sl.X < 0.0) || (P.X >= Size - Mg && Sl.X > 0.0))
					{
						Sl.X = 0.0;
					}
					if ((P.Y <= Mg && Sl.Y < 0.0) || (P.Y >= Size - Mg && Sl.Y > 0.0))
					{
						Sl.Y = 0.0;
					}
					Sl = R3::Normalize(Sl);
					Dir = (Sl.X * Sl.X + Sl.Y * Sl.Y > Eps2) ? Sl : Dir;
				}
				if (Prev == kKeepPanic && Next != kKeepPanic)
				{
					++W.Stats.KeepPanicEnds;
					W.Stats.KeepPanicEndShelter += bInCov ? 1 : 0;
					W.Stats.KeepPanicEndSteps += D.KeepPanicSteps;
					D.KeepPanicSteps = 0;
				}
				if ((Prev == kKeepPanic || Prev == kKeepShelter) && Next != kKeepPanic && Next != kKeepShelter)
				{
					// 풀림: 두뇌의 다음 결정을 깨끗하게 연다 (잠금이 끝난 것으로, 미뤄 둔 사건 결정 없음)
					S.LockLeft = S.LockLeft < 0 ? S.LockLeft : 0;
					S.EvWait = -1;
				}
				D.KeepDir = Dir;
				D.KeepMode = Next;
			}
		}

		/**
		 * A 의 덮기 Commit (도주·웅크림, Arbiter Commit 대신 — world.py `_wf_commit`): 행동이 다르면(또는 기상 중·HIDE 도착 전) Enter 로
		 * 들어간다 (진입 잠금·seq·위상, GRAZE → FLEE 놀람 정지 0.4 초, HIDE 는 은신처 원 안이라 곧바로 도착). 미뤄 둔 사건 결정은 버린다.
		 */
		inline EcoRepertoireV3::FArbiterResult CommitFlight(const FWorldState& W, const FHerbView& H)
		{
			namespace R3 = EcoRepertoireV3;
			FHerbDecision& D = *H.Decision;
			R3::FRepState& S = *H.Rep;
			const std::int32_t Target = D.KeepMode == kKeepShelter ? R3::kHide : R3::kFlee;
			R3::FArbiterResult R;
			R.bEvent = D.Prep.bEvent;
			R.bFire = D.Prep.bFire;
			R.EventBits = D.Prep.EventBits;
			if (S.Behavior != Target || S.bWaking || (Target == R3::kHide && !S.bArrived))
			{
				R3::Enter(S, Target, D.DecisionObs, W.RepCfg);
				R.bSwitch = true;
			}
			S.EvWait = -1;
			S.Phase = R3::PhaseOf(S, W.RepCfg);
			return R;
		}

		/** B 의 도주 제어 입력: FLEE 제어기의 위협 반대 = 덮기 방향 (보인 위협으로 둔다 — world.py `_rep_step` 의 wf PANIC 줄). */
		inline void FlightControlInput(const FHerbView& H, EcoRepertoireV3::FControlInput& In)
		{
			const FHerbDecision& D = *H.Decision;
			if (D.KeepActive == kKeepPanic && (D.KeepDir.X != 0.0 || D.KeepDir.Y != 0.0))
			{
				In.AwayFromPred = D.KeepDir;
				In.PredCount = In.PredCount > 0 ? In.PredCount : 1;
			}
		}

		/**
		 * B 의 경계 제어 (world.py `_wf_alert_control`): 두뇌 행동이 GRAZE 인 경계 사슴은 걸으며 먹고(보행·섭식·대사 = 걷기)
		 * GRAZE 조향 + AlertW·덮기 방향으로 멀어지며 고개를 든다(시야 배수 1). 다른 행동(두뇌의 FLEE·HIDE·SLEEP)은 그대로다.
		 */
		inline void FlightAlertControl(const FWorldState& W, const FHerbView& H, const EcoRepertoireV3::FControlInput& In)
		{
			namespace R3 = EcoRepertoireV3;
			const FHerbDecision& D = *H.Decision;
			if (D.KeepActive != kKeepAlert || H.Rep->Behavior != R3::kGraze || !(D.KeepDir.X != 0.0 || D.KeepDir.Y != 0.0))
			{
				return;
			}
			const R3::FRepertoireConfig& RC = W.RepCfg;
			const FVec2 Dv = R3::Add(R3::Add(R3::Add(R3::Scale(In.FoodGrad, RC.GrazeForage), R3::Scale(In.ToCentroid, RC.GrazeCohesion)),
											 R3::Scale(In.Separation, RC.SepWeight)),
									 R3::Scale(D.KeepDir, W.Config.WildFlight.AlertW));
			FVec2 Nv = R3::Normalize(Dv);
			if (!(Nv.X * Nv.X + Nv.Y * Nv.Y > R3::kEps * R3::kEps))
			{
				Nv = D.KeepDir;
			}
			R3::FControlOutput& O = *H.Control;
			O.Velocity = R3::Scale(Nv, RC.HerbSpeed * RC.GaitSpeed[R3::kGaitWalk]);
			O.Gait = R3::kGaitWalk;
			O.EatMult = RC.GaitEat[R3::kGaitWalk];
			O.DrainMult = RC.GaitDrain[R3::kGaitWalk];
			O.SeeMult = 1.0;
		}
	}

	/**
	 * 한 결정 스텝 (계약 10-2). Herbs 는 슬롯 순서(색인 = 슬롯), Threats 도 슬롯 순서다.
	 * 처음 부르기 전에 ObserveAndDecideAll 로 첫 관측·요청을 만들어 둔다.
	 * 통합 모드는 Herbs·Threats 를 StableAgentId 순으로 넘기고(동점 규칙의 '낮은 색인' = 낮은 StableAgentId),
	 * 산 개체만 넘긴다 — 이번 스텝에 죽은 개체(DeathCause != None)는 다음 Step 에서 빼야 한다. Hooks 가 nullptr 이면 지금과 같다.
	 */
	inline FStepReport Step(FWorldState& W, const FHerbView* Herbs, std::int32_t N, FThreatAgent* const* Threats, std::int32_t M,
							const EcoPolicyV3::FPolicyNetV3& Net = EcoPolicyV3::kBuiltinNet, const FStepHooks* Hooks = nullptr)
	{
		namespace R3 = EcoRepertoireV3;
		FStepReport Report;
		const R3::FRepertoireConfig& RC = W.RepCfg;
		W.StepCatches.clear();
		const bool bKeep = W.Config.WildFlight.bEnabled;   // 도주 반사 거리 (끄면 아래 bKeep 줄은 모두 건너뛴다 — 지금 그대로)
		const bool bReserve = W.Config.WildReserve.bEnabled;   // 야생 (w1) 지방 비축 (끄면 아래 bReserve 줄은 모두 건너뛴다 — 지금 그대로)

		// A. Arbiter Commit — 지난 스텝 끝에 Prepare·마스크·망으로 정한 요청
		for (std::int32_t i = 0; i < N; ++i)
		{
			const FHerbView& H = Herbs[i];
			FHerbDecision& D = *H.Decision;
			R3::FRepState& S = *H.Rep;
			if (!D.bPrepared)
			{
				// 방어: 첫 관측 없이 스텝이 왔다. 지금 지각으로 준비한다 (보통 경로는 ObserveAndDecideAll·지난 스텝 H 가 한다)
				DecideHerb(W, H, Net);
			}
			D.PrevBehavior = S.Behavior;
			D.CommittedRequest = D.Request;
			D.bCommittedReads = D.Prep.bReads;
			for (std::int32_t b = 0; b < R3::kNumBehaviors; ++b)
			{
				D.CommittedMask[b] = D.Mask[b];
			}
			const bool bOverride = bKeep && (D.KeepMode == kKeepPanic || D.KeepMode == kKeepShelter);
			if (bOverride)
			{
				D.Result = Detail::CommitFlight(W, H);   // 두뇌 요청 대신 도주(FLEE)·웅크림(HIDE) (Enter 로 진입)
			}
			else
			{
				D.Result = R3::Commit(S, D.Prep, D.Request, D.DecisionObs, RC);   // 경계는 두뇌가 정한다
			}
			if (bKeep)
			{
				const std::int32_t PrevActive = D.KeepActive;
				D.KeepActive = D.KeepMode;
				if (D.KeepActive != PrevActive)
				{
					W.Stats.KeepAlertStarts += D.KeepActive == kKeepAlert ? 1 : 0;
					W.Stats.KeepPanicStarts += D.KeepActive == kKeepPanic ? 1 : 0;
					W.Stats.KeepShelterStarts += D.KeepActive == kKeepShelter ? 1 : 0;
				}
				D.KeepPanicSteps += D.KeepActive == kKeepPanic ? 1 : 0;
				++W.Stats.KeepSteps[D.KeepActive];
			}
			D.ExecutedBehavior = S.Behavior;
			D.bPrepared = false;

			// 마스크 확인: 읽은 개체는 마스크 안 행동만, 읽지 않은 개체는 행동이 그대로다 (기상 끝은 SLEEP 전용).
			// 도주 반사 거리의 덮기는 세계 허용 칸 안 행동만 (FLEE·HIDE)
			const bool bAllowed = bOverride				? W.Allowed[S.Behavior] != 0
								  : D.bCommittedReads ? D.CommittedMask[S.Behavior] != 0
													  : (S.Behavior == D.PrevBehavior || D.Prep.bWoke);
			W.Stats.MaskViolations += bAllowed ? 0 : 1;
			W.Stats.Decisions += D.bCommittedReads ? 1 : 0;
			if (D.Result.bSwitch)
			{
				++W.Stats.Entries[S.Behavior];
			}
		}

		// B. 제어기 — 결정 관측(지난 스텝 끝 기하)과 결정 때 위치·먹이 셀
		for (std::int32_t i = 0; i < N; ++i)
		{
			const FHerbView& H = Herbs[i];
			if (bKeep)
			{
				// 도주: FLEE 제어기에 덮기 방향. 경계: 두뇌가 GRAZE 면 걸으며 먹고 멀어진다 (world.py _rep_step 의 wf 줄)
				R3::FControlInput In = Detail::MakeControlInput(W, H);
				Detail::FlightControlInput(H, In);
				*H.Control = R3::Control(*H.Rep, In, RC);
				Detail::FlightAlertControl(W, H, In);
			}
			else
			{
				*H.Control = R3::Control(*H.Rep, Detail::MakeControlInput(W, H), RC);
			}
			if (bReserve)
			{
				// 야생 (w1) 약함: 스텝 첫머리 E 가 WeakE 밑이면(비축으로 사는 몸) 이동 속도 × WeakSpeed (world.py step 1 의 v 줄이기).
				// 대사·섭식 배수는 보행 그대로다. heading 은 ApplyMove 가 줄인 속도의 방향으로 정한다 (방향은 그대로)
				FHerbBody& Bd = *H.Body;
				Bd.bWeak = Bd.Energy < W.Config.WildReserve.WeakE * RC.MaxEnergy;
				if (Bd.bWeak && W.Config.WildReserve.WeakSpeed < 1.0)
				{
					H.Control->Velocity.X *= W.Config.WildReserve.WeakSpeed;
					H.Control->Velocity.Y *= W.Config.WildReserve.WeakSpeed;
				}
			}
			R3::CommitSeeMult(*H.Rep, H.Control->SeeMult);
			++W.Stats.BehaviorSteps[H.Rep->Behavior];
		}

		// C1. 초식 이동 (벽에서 멈춤, heading = 속도 방향, FREEZE 는 위협 쪽)
		for (std::int32_t i = 0; i < N; ++i)
		{
			FHerbBody& B = *Herbs[i].Body;
			B.PrevPos = B.Pos;
			B.DeathCause = kDeathNone;
			B.CaughtBy = -1;
			B.bReproduced = false;
			B.bRespawned = false;
			R3::ApplyMove(B.Pos, B.Head, *Herbs[i].Control, W.Config.WorldSize);
			// 통합 모드: 지형·장애물 제약. 막히면 이동 전 자리 (heading 은 가려던 쪽 그대로)
			if (Hooks && Hooks->HerbMove && (B.Pos.X != B.PrevPos.X || B.Pos.Y != B.PrevPos.Y)
				&& !Hooks->HerbMove(Hooks->User, i, B.PrevPos, B.Pos))
			{
				B.Pos = B.PrevPos;
				++W.Stats.BlockedHerbMoves;
			}
		}

		// C2. 위협 스텝 (초식 이동 뒤 위치, 위협 이동 전 위치로 포획 거리)
		W.Prey.resize(static_cast<size_t>(N));
		for (std::int32_t i = 0; i < N; ++i)
		{
			const FHerbView& H = Herbs[i];
			EcoThreatV3::FPreyView& P = W.Prey[static_cast<size_t>(i)];
			P.X = H.Body->Pos.X;
			P.Y = H.Body->Pos.Y;
			P.Behavior = static_cast<std::uint8_t>(H.Rep->Behavior);
			P.bHideArrived = H.Rep->bArrived;
			P.bInCover = Detail::InAnyCover(W, H.Body->Pos);   // 이동 뒤 위치로 다시 판정 (world.py:2026)
			P.bAlive = true;                                    // 파이썬처럼 늘 산 개체다 (죽은 슬롯은 지난 스텝 끝에 리스폰했다)
		}
		W.Rolls.resize(static_cast<size_t>(N));
		W.CaughtByThreat.assign(static_cast<size_t>(M), -1);
		for (std::int32_t m = 0; m < M; ++m)
		{
			FThreatAgent& A = *Threats[m];
			EcoThreatV3::FThreatStepInput In;
			In.Prey = W.Prey.data();
			In.NumPrey = N;
			In.Dark = W.Dark;
			In.WorldSize = W.Config.WorldSize;
			In.WanderTurn = W.Rng.Uniform(-W.ThreatCfg.PredWanderTurn, W.ThreatCfg.PredWanderTurn);
			if (A.Spec.bRanged)
			{
				for (std::int32_t i = 0; i < N; ++i)
				{
					W.Rolls[static_cast<size_t>(i)] = W.Rng.NextU01();
				}
				In.RangedRoll = W.Rolls.data();
			}
			if (A.Spec.Type == EcoThreatV3::EThreatType::Player)
			{
				In.PlayerModeU0 = W.Rng.NextU01();
				In.PlayerModeU1 = W.Rng.NextU01();
			}
			A.PrevX = A.State.PosX;
			A.PrevY = A.State.PosY;
			const std::int32_t PreCd = A.State.Cooldown;
			A.Last = EcoThreatV3::Step(A.Spec, A.State, In, W.ThreatCfg);
			if (W.ThreatCfg.bWildSatiation && A.Spec.Type != EcoThreatV3::EThreatType::Player)
			{
				// 야생 (w2) 기록만: 늑대·스텝, 배불러 쉼, 먹는 중(쿨다운 줄인 뒤 > 0), 포만을 건 포획
				++W.Stats.WolfSteps;
				W.Stats.WolfSatedSteps += A.Last.bSated ? 1 : 0;
				W.Stats.WolfEatingSteps += PreCd - 1 > 0 ? 1 : 0;
				W.Stats.WolfKills += A.Last.Caught >= 0 ? 1 : 0;
			}
			// 통합 모드: 지형·장애물 제약. 포획은 이동 전 위치로 이미 판정했다(위 Step 9). 막히면 이동 전 자리·변위 0·heading 반전
			// (학습의 벽 반사를 흉내 낸 근사 — 장애물의 법선은 모른다)
			if (Hooks && Hooks->ThreatMove && (A.State.PosX != A.PrevX || A.State.PosY != A.PrevY)
				&& !Hooks->ThreatMove(Hooks->User, m, A.PrevX, A.PrevY, A.State.PosX, A.State.PosY))
			{
				A.State.PosX = A.PrevX;
				A.State.PosY = A.PrevY;
				A.State.VelX = 0.0;
				A.State.VelY = 0.0;
				A.State.HeadX = -A.State.HeadX;
				A.State.HeadY = -A.State.HeadY;
				++W.Stats.BlockedThreatMoves;
			}
			W.CaughtByThreat[static_cast<size_t>(m)] = A.Last.Caught;
		}
		W.Catcher.assign(static_cast<size_t>(N), -1);
		EcoThreatV3::ResolveCatches(W.CaughtByThreat.data(), M, W.Catcher.data(), N);

		// C4. 섭식·대사 (이동 뒤 셀, 셀마다 수요 합을 슬롯 순서로 쌓는다 — np.bincount)
		FFoodGrid& F = W.Food;
		W.Want.resize(static_cast<size_t>(N));
		W.EDrained.resize(static_cast<size_t>(N));
		W.CellIdx.resize(static_cast<size_t>(N));
		F.Demand.assign(F.Food.size(), 0.0);
		for (std::int32_t i = 0; i < N; ++i)
		{
			const FHerbView& H = Herbs[i];
			const double Ed = H.Body->Energy - R3::DrainAmount(H.Control->DrainMult, RC);
			const double Want = R3::EatWant(Ed, R3::EffectiveEatMult(H.Control->EatMult, W.Dark, RC), RC);
			const std::int32_t Cell = F.CellOf(H.Body->Pos);
			W.EDrained[static_cast<size_t>(i)] = Ed;
			W.Want[static_cast<size_t>(i)] = Want;
			W.CellIdx[static_cast<size_t>(i)] = Cell;
			F.Demand[static_cast<size_t>(Cell)] += Want;
		}
		for (size_t k = 0; k < F.Demand.size(); ++k)
		{
			const double Dm = F.Demand[k];
			const double Taken = Dm < F.Food[k] ? Dm : F.Food[k];
			F.Demand[k] = Dm > 0.0 ? Taken / Dm : 0.0;   // 이제 이 칸은 비율이다
			F.Food[k] -= Taken;
			W.Stats.FoodEaten += Taken;                   // 기록만 (아래 계산에 쓰지 않는다)
		}
		std::int32_t NumCaught = 0;
		for (std::int32_t i = 0; i < N; ++i)
		{
			FHerbBody& B = *Herbs[i].Body;
			const double Gain = W.Want[static_cast<size_t>(i)] * F.Demand[static_cast<size_t>(W.CellIdx[static_cast<size_t>(i)])];
			B.Energy = R3::EnergyAfterIntake(W.EDrained[static_cast<size_t>(i)], Gain, RC);
			B.LastIntake = Gain;                          // 기록만
			W.Stats.EatSteps += Gain > 0.0 ? 1 : 0;
			if (bReserve)
			{
				// 야생 (w1): 모자람은 비축에서, 남음은 비축으로 (world.py step 3) 의 _wild_reserve_step — 번식 C5 앞)
				const FWildReserveDelta Dr = WildReserveStep(B.Energy, B.Reserve, Gain * RC.FoodEnergyPerUnit, W.ReserveCap, W.Config.WildReserve);
				W.Stats.ReserveUsed += Dr.Used;
				W.Stats.ReserveRefill += Dr.Refill;
				++W.Stats.ReserveLiveSteps;
				W.Stats.WeakSteps += B.bWeak ? 1 : 0;
			}

			// C5. 번식
			B.bReproduced = R3::ApplyReproduction(B.Energy, B.ReproCd, RC);
			Report.Reproduced += B.bReproduced ? 1 : 0;

			// C6. 사망 (잡힘 또는 아사)
			const std::int32_t By = W.Catcher[static_cast<size_t>(i)];
			if (By >= 0)
			{
				B.DeathCause = kDeathCaught;
				B.CaughtBy = By;
				B.DeathPos = B.Pos;
				W.StepCatches.push_back(B.Pos);
				++NumCaught;
				if (bKeep)
				{
					++W.Stats.CaughtByKeep[Herbs[i].Decision->KeepActive];   // 기록만 (경계 중·도망 중·웅크림 중·덮기 밖)
				}
				W.Stats.WeakCaught += (bReserve && B.bWeak) ? 1 : 0;   // 야생 (w1) 기록만: 약한 채로 잡힘
			}
			else if (B.Energy <= 0.0 && (!bReserve || B.Reserve <= 0.0))   // 야생 (w1): 비축까지 바닥나야 굶어 죽는다
			{
				B.DeathCause = kDeathStarved;
				B.DeathPos = B.Pos;
				++Report.Starved;
			}
		}
		Report.Caught = NumCaught;

		// C7. 피식 EMA (분모 N 고정 — 파이썬 128 과 같은 꼴, 열린 질문 7. 통합 모드는 PredEmaDenominator 고정값). C8. 먹이 재생
		const std::int32_t EmaDen = W.Config.PredEmaDenominator > 0 ? W.Config.PredEmaDenominator : (N > 0 ? N : 1);
		W.PredEma = EcoObservationV3::UpdatePredationEma(W.PredEma, NumCaught, EmaDen, W.ObsCfg);
		F.Regrow();

		// D. t ← t + 1, Tick. D′. 새 t 의 어둠
		++W.T;
		for (std::int32_t i = 0; i < N; ++i)
		{
			R3::Tick(*Herbs[i].Rep);
		}
		UpdateDayNight(W);
		// D″. 늑대 밤잠 점진화 (켰을 때만): 새 t 의 어둠과 늑대 이동 뒤·리스폰 전 사슴 위치(W.Prey — C2 에서 모은 이동 뒤 위치, 이번 스텝에
		//     죽은 사슴도 그 자리에 있다)로 늑대마다 한 업데이트 (world.py `_daynight_update` → `_rz_night_update`, 관측 E 전)
		if (W.ThreatCfg.bRealismNight)
		{
			const bool bDarkNow = W.Dark >= W.ThreatCfg.SleepDark;
			for (std::int32_t m = 0; m < M; ++m)
			{
				FThreatAgent& A = *Threats[m];
				A.LastNight = EcoThreatV3::NightUpdate(A.Spec, A.State, W.Dark, W.Prey.data(), N, W.ThreatCfg);
				const EcoThreatV3::FNightUpdateResult& Nr = A.LastNight;
				W.Stats.NightSettleStarts += Nr.bSettleStart ? 1 : 0;
				W.Stats.NightSettleAborts += Nr.bSettleAbort ? 1 : 0;
				W.Stats.NightOnsets += Nr.bOnset ? 1 : 0;
				W.Stats.NightWakes += Nr.bWake ? 1 : 0;
				W.Stats.NightBlockDeer += Nr.bBlockDeer ? 1 : 0;
				W.Stats.NightBlockHunt += Nr.bBlockHunt ? 1 : 0;
				if (bDarkNow && !A.Spec.bNocturnal)
				{
					++W.Stats.NightDarkUpdates;
					W.Stats.NightDarkAwake += A.State.bAsleep ? 0 : 1;
				}
			}
		}

		// E~F. 관측 (죽은 개체도 제자리에서 동족으로 센다)
		ObserveAll(W, Herbs, N, Threats, M);

		// G. 리스폰 — 죽은 슬롯을 새 세대로, 그 행만 다시 관측한다
		//    통합 모드(bRespawnDead = false)는 되살리지 않는다: 시체는 죽은 자리에 멈춘다(PrevPos = Pos, 화면 보간이 튀지 않게).
		//    다음 스텝부터는 부르는 쪽이 이 개체를 빼므로 움직이지도, 먹지도, 잡히지도, 동족으로 세어지지도 않는다
		for (std::int32_t i = 0; i < N; ++i)
		{
			const FHerbView& H = Herbs[i];
			FHerbBody& B = *H.Body;
			if (B.DeathCause == kDeathNone)
			{
				continue;
			}
			if (!W.Config.bRespawnDead)
			{
				B.PrevPos = B.Pos;
				continue;
			}
			++B.Generation;
			B.Pos = {W.Rng.Uniform(0.0, W.Config.WorldSize), W.Rng.Uniform(0.0, W.Config.WorldSize)};
			const double A = W.Rng.Uniform(0.0, 2.0 * 3.14159265358979323846);
			B.Head = {std::cos(A), std::sin(A)};
			B.PrevPos = B.Pos;
			B.Energy = RC.InitEnergy;
			B.ReproCd = 0;
			B.Reserve = W.Config.WildReserve.bEnabled ? W.Config.WildReserve.Init : 0.0;   // 야생 (w1): 새 개체는 시작 비축으로
			B.bRespawned = true;
			const double E01 = B.Energy / RC.MaxEnergy;
			R3::RespawnAgent(*H.Rep, E01 < 0.0 ? 0.0 : (E01 > 1.0 ? 1.0 : E01), W.Dark, W.Config.Seed,
						 R3::MakeAgentKey(B.Slot, B.Generation), RC);
			++Report.Respawned;
		}
		if (Report.Respawned > 0)
		{
			Detail::BuildKinInputs(W, Herbs, N);   // 리스폰한 위치·행동(GRAZE)으로 (world._observe_subset)
			for (std::int32_t i = 0; i < N; ++i)
			{
				if (Herbs[i].Body->bRespawned)
				{
					Detail::ObserveHerb(W, Herbs[i], i, N, M);
				}
			}
		}

		// H. 다음 스텝 요청. 도주 반사 거리를 켠 세계는 먼저 스텝 끝 기하로 다음 스텝의 덮기를 정한다 (도주·웅크림이면 DecideHerb 가 망을 부르지 않는다)
		if (bKeep)
		{
			Detail::UpdateWildFlight(W, Herbs, N, Threats, M);
		}
		DecideAll(W, Herbs, N, Net);

		W.Stats.Caught += Report.Caught;
		W.Stats.Starved += Report.Starved;
		W.Stats.Reproduced += Report.Reproduced;
		++W.Stats.Steps;
		return Report;
	}

	// ---- 기준 루프 (조각 없이 배열로 같은 단계를 돈다 — 시험·g++ 하네스용) ----

	struct FReferenceWorld
	{
		FWorldState World;
		std::vector<EcoRepertoireV3::FRepState> Reps;
		std::vector<FHerbDecision> Decisions;
		std::vector<FHerbBody> Bodies;
		std::vector<FHerbPerception> Perceptions;
		std::vector<EcoRepertoireV3::FControlOutput> Controls;
		std::vector<FThreatAgent> Threats;
		std::vector<FHerbView> Views;
		std::vector<FThreatAgent*> ThreatPtrs;

		std::int32_t NumHerbivores() const { return static_cast<std::int32_t>(Views.size()); }
		std::int32_t NumThreats() const { return static_cast<std::int32_t>(ThreatPtrs.size()); }

		/** world.reset: 세계 → 초식 슬롯 순서 → 위협 슬롯 순서 → 첫 관측·요청. Mass 스폰과 같은 순서다. */
		void Init(const FWorldConfig& C)
		{
			InitWorld(World, C);
			const size_t N = static_cast<size_t>(C.NumHerbivores > 0 ? C.NumHerbivores : 0);
			const size_t M = static_cast<size_t>(C.NumThreats() > 0 ? C.NumThreats() : 0);
			Reps.assign(N, EcoRepertoireV3::FRepState());
			Decisions.assign(N, FHerbDecision());
			Bodies.assign(N, FHerbBody());
			Perceptions.assign(N, FHerbPerception());
			Controls.assign(N, EcoRepertoireV3::FControlOutput());
			Threats.assign(M, FThreatAgent());
			Views.resize(N);
			ThreatPtrs.resize(M);
			for (size_t i = 0; i < N; ++i)
			{
				Views[i] = {&Reps[i], &Decisions[i], &Bodies[i], &Perceptions[i], &Controls[i]};
				InitHerb(World, static_cast<std::uint32_t>(i), Views[i]);
			}
			for (size_t m = 0; m < M; ++m)
			{
				ThreatPtrs[m] = &Threats[m];
				InitThreat(World, static_cast<std::uint32_t>(m), Threats[m]);
			}
			ObserveAndDecideAll(World, Views.data(), NumHerbivores(), ThreatPtrs.data(), NumThreats());
		}

		FStepReport StepOnce() { return Step(World, Views.data(), NumHerbivores(), ThreatPtrs.data(), NumThreats()); }
	};
}

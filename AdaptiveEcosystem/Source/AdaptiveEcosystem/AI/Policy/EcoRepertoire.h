// v3 행동 레퍼토리 — 개체 하나의 행동 실행기(Arbiter)·행동별 제어기·이동·에너지. 파이썬 herbivore_rl/env_v2/repertoire.py
// (RepState·arbitrate·control·tick·perceive·reset_slots)와 world.py 의 개체 단위 줄(_rep_step·이동·_drain_eat·_eat·번식)의 거울이다.
//
// **이 파일은 의도적으로 언리얼에 의존하지 않는다.**
// `<cmath>`·`<cstdint>` 만 쓴다(EcoPolicyV3Inference.h 와 같은 이유). 엔진 없이 g++ 로도 골든을 대조할 수 있고
// (herbivore_rl/tests/test_repertoire_golden_v3.py), 같은 파일이 UE 자동화 시험(Tests/EcoRepertoireV3Test.cpp)에서도 그대로 돈다.
// UObject·Mass 와 무관한 순수 함수뿐이다. 개체 사이(셀 먹이 나누기, 이웃·위협 찾기)는 Mass 층의 몫이다.
//
// 계약: AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md 5절(Arbiter), 6절(제어기), 10절(스텝 순서), 12절(언리얼 대응).
// 세계: R1b 두뇌가 배운 경보 없는 세계 herbivore_rl/configs/v3_r1_on.yaml (사람 결정 10-13 (3) — 게임의 모든 사슴).
//       그래서 사건은 E1~E6 이다. E7(동족 경보)은 FRepertoireConfig::bKinAlarmEvent 로 막혀 있다(기본 false).
//
// 단위: **파이썬 단위로 계산한다** (계약 12-1). 길이 1단위 = 200 cm, 시간 1스텝 = 8/60 s = 0.1333 s.
//   Mass 층이 cm ÷ 200, cm/s ÷ 1500 으로 바꿔 넘기고, 결과를 다시 cm 로 바꾼다 (아래 UnitsToCm 등).
//   보행 속력: 정지 0, 걷기 0.24단위/스텝 = 360 cm/s, 뛰기 0.6단위/스텝 = 900 cm/s.
//
// 한 결정 스텝의 개체 순서 (계약 10-2, world.py step):
//   0  Prepare(상태, 결정 관측)          — a 도착, b 사건, c 지연, d 기상 끝 판정, e 결정 여부. 요청을 읽지 않는다
//      bReads 면 마스크(EcoPolicyV3::ComposeActionMask) + 망으로 요청을 만든다. 아니면 요청 = 지금 행동
//   A  Commit(상태, 준비, 요청)         — 기상 끝 진입, 바꾸기(Enter), 위상
//   B  Control(상태, 제어 입력)         — 속도·보행·섭식·대사·자기 탐지 배수·정지·웅크림·heading 덮기·은신 배수
//      CommitSeeMult(상태, 출력.SeeMult) — 다음 관측의 탐지 배수 (직전 배수는 사건 비교 시야로 간다)
//   C1 ApplyMove(위치, heading, 출력)   — 맵 벽에서 멈춘다(자르기)
//   C4 섭식·대사, C5 번식                — DrainAmount·EffectiveEatMult·EatWant·EnergyAfterIntake·ApplyReproduction
//   D  Tick(상태)                        — 스텝 끝 (t + 1 뒤)
//   E1 Perceive(상태, 이번 관측의 위협)  — away·threat_recency
//   G  RespawnAgent(상태, …)             — 죽은 개체 (파리티 모드). 통합 모드는 새 개체 InitAgent
//   Prepare + Commit 은 Arbitrate 한 번과 비트 단위로 같다 (파이썬 rep_peek 은 사본에 arbitrate 를 돌린다 — 계약 5-6).
//
// 개체 키 (계약 5-5·12-3):
//   파리티 시험 모드  AgentKey = MakeAgentKey(슬롯, 세대) = 슬롯·2^32 + 세대, Seed = 파이썬 세계 시드.
//                     세대 = 그 슬롯의 리스폰 횟수(0부터). 파이썬과 비트 단위로 같은 지연이 나온다.
//   통합 모드         AgentKey = MakeAgentKeyFromStableId(StableAgentId) = (uint64)StableAgentId, Seed = 세션 시드.
//                     리스폰 대신 새 개체(새 StableAgentId)가 나므로 새 키가 곧 새 세대다. 해시·분포는 같고 값만 다르다.
//                     seq 는 새 개체에서 0 으로 시작한다(InitAgent, 애니메이션 전용). 사람 확인 전이다(계약 13-2 열린 질문 3).

#pragma once

#include <cmath>
#include <cstdint>

namespace EcoRepertoireV3
{
	// ---- 번호 (계약 1-3, repertoire.py 계약 순서. 한 번 정한 뜻을 바꾸지 않는다) ----
	inline constexpr std::int32_t kGraze = 0;
	inline constexpr std::int32_t kFlee = 1;
	inline constexpr std::int32_t kHide = 2;
	inline constexpr std::int32_t kFreeze = 3;
	inline constexpr std::int32_t kSleep = 4;
	inline constexpr std::int32_t kNumBehaviors = 5;

	inline constexpr std::int32_t kPhaseEnter = 0;    // 진입
	inline constexpr std::int32_t kPhaseActive = 1;   // 지속
	inline constexpr std::int32_t kPhaseExit = 2;     // 이탈 (SLEEP 기상만)

	inline constexpr std::int32_t kGaitStop = 0;
	inline constexpr std::int32_t kGaitWalk = 1;
	inline constexpr std::int32_t kGaitRun = 2;

	inline constexpr std::int32_t kSeqMod = 256;               // seq 는 mod 256 (C++ uint8 복제 칸)
	inline constexpr std::uint64_t kJitterTag = 505;           // 사건 결정 지연 해시의 첫 입력 (repertoire.JITTER_TAG)
	inline constexpr double kEps = 1e-9;                       // steering.EPS — 정규화·방향 판정 문턱
	inline constexpr double kNoThreatDist = 1.0e300;           // '안 보임' 거리(파이썬 inf). 늘 수 > 0 으로 가려 읽는다

	// 사건 비트 (FArbiterResult::EventBits, 골든 기록용)
	inline constexpr std::uint32_t kEventE1 = 0x01;    // 사건 비교 시야의 보이는 위협 수가 늘었다
	inline constexpr std::uint32_t kEventE2 = 0x02;    // 8 안으로 들어옴, 또는 접근 관측 0.9 이상이 됨
	inline constexpr std::uint32_t kEventE3 = 0x04;    // SLEEP 중 위협이 보임 (두 두뇌에서 쓰이지 않음)
	inline constexpr std::uint32_t kEventE4 = 0x08;    // 에너지가 0.25 아래로 내려감
	inline constexpr std::uint32_t kEventE5 = 0x10;    // 어둠이 0.5 를 지남 (양방향)
	inline constexpr std::uint32_t kEventE6 = 0x20;    // HIDE 도착 (진입 스텝 제외)
	inline constexpr std::uint32_t kEventE7 = 0x40;    // 동족 경보 (bKinAlarmEvent 일 때만)

	// ---- 단위 (계약 12-1. 파이썬 1단위 = 200 cm, 1스텝 = 8/60 s) ----
	inline constexpr double kUnitCm = 200.0;
	inline constexpr double kStepSeconds = 8.0 / 60.0;

	constexpr double UnitsToCm(double Units) { return Units * kUnitCm; }
	constexpr double CmToUnits(double Cm) { return Cm / kUnitCm; }
	/** 단위/스텝 -> cm/s (0.6 -> 900). */
	constexpr double UnitsPerStepToCmPerSec(double UnitsPerStep) { return UnitsPerStep * kUnitCm / kStepSeconds; }
	/** cm/s -> 단위/스텝 (900 -> 0.6). */
	constexpr double CmPerSecToUnitsPerStep(double CmPerSec) { return CmPerSec * kStepSeconds / kUnitCm; }
	constexpr double StepsToSeconds(double Steps) { return Steps * kStepSeconds; }
	constexpr double SecondsToSteps(double Seconds) { return Seconds / kStepSeconds; }

	// ---- 2D 벡터 (double — 파이썬 float64 기하와 같은 정밀도. UE FVector 도 double 이다) ----
	struct FVec2
	{
		double X = 0.0;
		double Y = 0.0;
	};

	constexpr FVec2 Add(const FVec2& A, const FVec2& B) { return {A.X + B.X, A.Y + B.Y}; }
	constexpr FVec2 Sub(const FVec2& A, const FVec2& B) { return {A.X - B.X, A.Y - B.Y}; }
	/** 파이썬 `k * v` (스칼라 곱은 교환해도 같은 값이다). */
	constexpr FVec2 Scale(const FVec2& V, double K) { return {V.X * K, V.Y * K}; }
	constexpr FVec2 Neg(const FVec2& V) { return {-V.X, -V.Y}; }
	constexpr double SizeSquared(const FVec2& V) { return V.X * V.X + V.Y * V.Y; }
	/** 두 칸 중 하나라도 0 이 아니면 참 (파이썬 `(v != 0.0).any()`). */
	constexpr bool IsNonZero(const FVec2& V) { return V.X != 0.0 || V.Y != 0.0; }

	/** steering.normalize — |v| > 1e-9 면 v/|v|, 아니면 0 (UE GetSafeNormal 과 같은 뜻, 문턱 1e-9). */
	inline FVec2 Normalize(const FVec2& V)
	{
		const double N = std::sqrt(V.X * V.X + V.Y * V.Y);
		if (N > kEps)
		{
			return {V.X / N, V.Y / N};
		}
		return {};
	}

	/** steering.clamp_magnitude — v · min(1, MaxLen / max(|v|, 1e-9)). */
	inline FVec2 ClampMagnitude(const FVec2& V, double MaxLen)
	{
		const double N = std::sqrt(V.X * V.X + V.Y * V.Y);
		const double Den = N > kEps ? N : kEps;
		const double R = MaxLen / Den;
		const double K = R < 1.0 ? R : 1.0;
		return {V.X * K, V.Y * K};
	}

	/**
	 * 세계 계수 (파이썬 단위). 기본값 = R1b 판정·배포 세계 herbivore_rl/configs/v3_r1_on.yaml + configs/default.yaml.
	 * 골든 헤더(RepertoireGoldenVectorsV3.h)의 kWorldConstant* 표를 자동화 시험이 이 값과 하나씩 비교한다.
	 */
	struct FRepertoireConfig
	{
		// 잠금 (스텝) — repertoire 블록
		std::int32_t LockGraze = 12;          // 1.6 s
		std::int32_t LockFlee = 8;            // 1.07 s
		std::int32_t LockFreeze = 12;
		std::int32_t LockHide = 12;           // 도착 뒤
		std::int32_t HideTravelMax = 40;      // 도착 전 최대 (5.33 s)
		std::int32_t SleepEnter = 3;
		std::int32_t SleepHold = 60;
		std::int32_t SleepWake = 3;
		std::int32_t StartleSteps = 3;        // GRAZE -> FLEE 놀람 정지 (0.4 s)
		std::int32_t DecisionJitter = 3;      // 사건 결정 지연 0..3 스텝

		// 사건 문턱
		double EventNear = 8.0;               // 1600 cm
		double EventApproach = 0.9;
		double EventEnergy = 0.25;
		double EventDark = 0.5;
		bool bKinAlarmEvent = false;          // E7 (경보 세계 FSM_R2 전용). R1b 두뇌에는 켜지 않는다 (계약 1-1)

		// 지각
		double RecencyDecay = 0.95;
		double GrazeHeadDown = 0.6;           // M5 GRAZE 자기 탐지 배수
		double SleepSight = 0.3;

		// 제어기
		double GrazeForage = 0.83;
		double GrazeCohesion = 0.71;
		double GrazeEatMin = 0.06;            // 지금 셀 먹이 >= 이 값이면 멈춰 먹는다
		double SepWeight = 1.35;              // default.yaml
		double FleeWeight = 3.0;              // default.yaml
		double HerbSpeed = 0.6;               // 단위/스텝 = 900 cm/s
		double GaitSpeed[3] = {0.0, 0.4, 1.0};                         // × HerbSpeed
		double GaitEat[3] = {1.0, 0.5, 0.0};                           // 섭식 배수
		double CRest = 0.7142857142857143;                             // 대사 = c_rest + c_move·s²
		double CMove = 1.7857142857142858;
		double GaitDrain[3] = {0.7142857142857143, 1.0, 2.5};          // 파이썬 c_rest + c_move·s·s 의 float64 값 그대로
		double SleepRest = 0.6;               // SLEEP·은신처 안 대사 × (1 − 0.6·d)

		// 은신 배수 (은신처 안일 때, 행동별) · 정지 탐지
		double CoverMultCrouch = 4.0;
		double CoverMultGraze = 1.5;
		double CoverMultSleep = 2.5;
		double CoverMultOther = 1.0;
		double CStill = 1.8;

		// 에너지 (default.yaml, daynight.eat_night)
		double EnergyDrain = 0.002;
		double MaxEnergy = 1.0;
		double InitEnergy = 0.5;
		double FoodEatRate = 0.06;
		double FoodEnergyPerUnit = 0.5;
		double EatNight = 0.9;
		double ReproThreshold = 0.9;
		std::int32_t ReproCooldown = 200;
	};

	/** R1b 세계 (게임의 모든 사슴, 사람 결정 10-13 (3)). */
	inline constexpr FRepertoireConfig kR1bConfig{};

	/** 진입 잠금 표 (repertoire.parse_params `locks`). HIDE 는 도착까지의 최대, SLEEP 은 진입 + 최소 수면. */
	constexpr std::int32_t EntryLock(std::int32_t Behavior, const FRepertoireConfig& Cfg)
	{
		return Behavior == kGraze	 ? Cfg.LockGraze
			   : Behavior == kFlee	 ? Cfg.LockFlee
			   : Behavior == kHide	 ? Cfg.HideTravelMax
			   : Behavior == kFreeze ? Cfg.LockFreeze
									 : Cfg.SleepEnter + Cfg.SleepHold;
	}

	/**
	 * 개체 행동 상태 (repertoire.RepState 한 행, 계약 5-1. Mass FEcoBehaviorStateFragment 의 거울).
	 * SeeMult·SeeMultLast 는 파이썬 World._rep_see·_rep_see_last (개체마다 하나라 여기 둔다): 다음 관측의 자기 탐지 배수와
	 * 결정 관측을 만든 배수(사건 비교 시야). 경보 칸(M8)은 없다 — R1b 세계에는 경보가 없다.
	 */
	struct FRepState
	{
		std::int32_t Behavior = kGraze;
		std::int32_t Phase = kPhaseEnter;
		std::int32_t StepsIn = 0;           // 행동 경과 (진입 스텝 0)
		std::int32_t Seq = 0;               // 행동이 바뀔 때마다 +1, mod 256
		std::int32_t LockLeft = 12;         // <= 0 이면 결정 시점. 음수로 계속 내려간다(부호만 읽는다)
		std::int32_t StartleLeft = 0;
		bool bWaking = false;               // SLEEP 기상 중 (두 두뇌에서 쓰이지 않는다)
		std::int32_t WakeLeft = 0;
		std::int32_t WakeTarget = kGraze;
		bool bWakeEv = false;
		std::int32_t EvWait = -1;           // 대기 중인 사건 결정까지 남은 스텝, -1 = 없음
		std::int32_t HideTarget = -1;       // HIDE 가 고른 은신처 색인
		bool bArrived = false;              // HIDE 도착 (웅크림)
		std::int32_t PrevPc = 0;            // 직전 결정 관측의 보이는 위협 수 (실제 시야)
		bool bPrevNear = false;
		bool bPrevFast = false;
		bool bPrevLow = false;
		bool bPrevDark = false;
		FVec2 Away;                         // 마지막 위협 반대 방향 (단위), 본 적 없으면 0
		double Recency = 0.0;               // threat_recency
		std::int32_t Jitter = 0;            // 사건 결정 지연 [0, DecisionJitter]
		double SeeMult = 0.6;               // 다음 관측의 자기 탐지 배수 (World._rep_see)
		double SeeMultLast = 0.6;           // 직전 관측의 배수 (World._rep_see_last)
	};

	// ---- 결정 지연 해시 (계약 5-5, repertoire.mix_chain·decision_jitter) ----

	/** SplitMix64 마무리 함수. 넘침을 허용한다(uint64). */
	constexpr std::uint64_t Mix64(std::uint64_t Z)
	{
		Z ^= Z >> 30;
		Z *= 0xBF58476D1CE4E5B9ULL;
		Z ^= Z >> 27;
		Z *= 0x94D049BB133111EBULL;
		Z ^= Z >> 31;
		return Z;
	}

	/** H(x1, x2, x3): h = 0, x 마다 h = Mix64((h ^ x) + 0x9E3779B97F4A7C15). */
	constexpr std::uint64_t HashChain3(std::uint64_t X1, std::uint64_t X2, std::uint64_t X3)
	{
		std::uint64_t H = 0;
		H = Mix64((H ^ X1) + 0x9E3779B97F4A7C15ULL);
		H = Mix64((H ^ X2) + 0x9E3779B97F4A7C15ULL);
		H = Mix64((H ^ X3) + 0x9E3779B97F4A7C15ULL);
		return H;
	}

	/** 파리티 모드 개체 키 = 슬롯·2^32 + 세대 (repertoire.agent_keys). */
	constexpr std::uint64_t MakeAgentKey(std::uint32_t Slot, std::uint32_t Generation)
	{
		return (static_cast<std::uint64_t>(Slot) << 32) + static_cast<std::uint64_t>(Generation);
	}

	/** 통합 모드 개체 키 = (uint64)StableAgentId (계약 12-3). 새 개체 = 새 키 = 새 지연. */
	constexpr std::uint64_t MakeAgentKeyFromStableId(std::int64_t StableAgentId)
	{
		return static_cast<std::uint64_t>(StableAgentId);
	}

	/** H(505, Seed, AgentKey). Seed 는 int64 를 uint64 로 바꾼다(음수는 2^64 을 더한 값 — NumPy astype(uint64)). */
	constexpr std::uint64_t JitterHash(std::int64_t Seed, std::uint64_t AgentKey)
	{
		return HashChain3(kJitterTag, static_cast<std::uint64_t>(Seed), AgentKey);
	}

	/** 사건 결정 지연 = H mod (J + 1) ∈ [0, J]. J <= 0 이면 0. 개체가 날 때 한 번 정한다. */
	constexpr std::int32_t DecisionJitter(std::int64_t Seed, std::uint64_t AgentKey, std::int32_t JMax)
	{
		return JMax <= 0 ? 0
						 : static_cast<std::int32_t>(JitterHash(Seed, AgentKey) % static_cast<std::uint64_t>(JMax + 1));
	}

	// ---- 개체 생성·리스폰 (repertoire.RepState·reset_slots, world._repertoire_reset·_respawn) ----

	namespace Detail
	{
		inline void ResetCommon(FRepState& S, double Energy01, double Dark, std::int64_t Seed, std::uint64_t AgentKey,
								const FRepertoireConfig& Cfg)
		{
			S.Behavior = kGraze;
			S.Phase = kPhaseEnter;
			S.StepsIn = 0;
			S.LockLeft = Cfg.LockGraze;
			S.StartleLeft = 0;
			S.bWaking = false;
			S.WakeLeft = 0;
			S.WakeTarget = kGraze;
			S.bWakeEv = false;
			S.EvWait = -1;
			S.HideTarget = -1;
			S.bArrived = false;
			S.PrevPc = 0;
			S.bPrevNear = false;
			S.bPrevFast = false;
			S.bPrevLow = Energy01 < Cfg.EventEnergy;
			S.bPrevDark = Dark >= Cfg.EventDark;
			S.Away = {};
			S.Recency = 0.0;
			S.Jitter = DecisionJitter(Seed, AgentKey, Cfg.DecisionJitter);
			S.SeeMult = Cfg.GrazeHeadDown;
			S.SeeMultLast = Cfg.GrazeHeadDown;
		}
	}

	/**
	 * 처음 나는 개체 (reset, 또는 통합 모드의 새 개체): GRAZE 진입, 잠금 LockGraze, seq 0.
	 * Energy01 = E ÷ MaxEnergy (리스폰·시작 0.5), Dark = 지금 어둠 d.
	 */
	inline void InitAgent(FRepState& S, double Energy01, double Dark, std::int64_t Seed, std::uint64_t AgentKey,
						  const FRepertoireConfig& Cfg = kR1bConfig)
	{
		S.Seq = 0;
		Detail::ResetCommon(S, Energy01, Dark, Seed, AgentKey, Cfg);
	}

	/**
	 * 리스폰 (파리티 모드, 같은 슬롯의 새 세대 — repertoire.reset_slots): InitAgent 와 같고 seq 만 +1 (새 개체임을 알린다).
	 * Tick 뒤에 부른다(world.step: tick → 관측 → 리스폰). AgentKey 는 새 세대의 키다.
	 */
	inline void RespawnAgent(FRepState& S, double Energy01, double Dark, std::int64_t Seed, std::uint64_t AgentKey,
							 const FRepertoireConfig& Cfg = kR1bConfig)
	{
		S.Seq = (S.Seq + 1) % kSeqMod;
		Detail::ResetCommon(S, Energy01, Dark, Seed, AgentKey, Cfg);
	}

	// ---- Arbiter (계약 5-2) ----

	/**
	 * 결정 관측 = 직전 스텝 끝 기하(리스폰 행 포함) + 지금 에너지 + 지금 어둠 (world._rep_decision_obs).
	 * *Ev = 사건 비교 시야(이번 관측과 직전 관측의 탐지 배수 중 작은 쪽)로 센 값. 거리는 파이썬 단위 실거리.
	 */
	struct FDecisionObs
	{
		std::int32_t PredCount = 0;
		double DPredMin = kNoThreatDist;       // PredCount == 0 이면 읽지 않는다
		double PredApproach = 0.5;             // 가장 가까운 보이는 위협의 접근 관측 [0, 1] (float64)
		std::int32_t PredCountEv = 0;
		double DPredMinEv = kNoThreatDist;
		double PredApproachEv = 0.5;
		double Energy = 0.5;                   // clip(E ÷ MaxEnergy, 0, 1)
		double Dark = 0.0;                     // d(t)
		bool bInCover = false;
		std::int32_t CoverK = -1;              // 가장 가까운 은신처 (가장자리 거리, 동점 낮은 색인), 없으면 -1
		bool bAlarmNew = false;                // E7 입력 (bKinAlarmEvent 가 꺼져 있으면 읽지 않는다)
	};

	/** Prepare 결과 — Commit 에 그대로 넘긴다. bReads 가 '요청을 읽는다'(파이썬 rep_peek reads). */
	struct FArbiterPrep
	{
		bool bReads = false;         // bDecide || bWakeDecide
		bool bWakeDecide = false;    // 기상 결정 (마스크가 SLEEP 을 막는다)
		bool bWoke = false;
		bool bDecide = false;
		bool bEvent = false;
		bool bFire = false;
		bool bE7 = false;
		std::uint8_t EventBits = 0;
	};

	/** Arbitrate 반환 (repertoire.arbitrate 의 dict). */
	struct FArbiterResult
	{
		bool bDecide = false;        // 요청을 읽었다 (decide ∨ wake_dec)
		bool bSwitch = false;        // 행동이 바뀌었다 (기상 시작 제외, 기상 끝 포함)
		bool bEvent = false;
		bool bFire = false;
		bool bE7 = false;
		std::uint8_t EventBits = 0;
	};

	/** 위상 (repertoire.phase_of, 계약 5-4). */
	constexpr std::int32_t PhaseOf(const FRepState& S, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		std::int32_t Ph = S.StepsIn == 0 ? kPhaseEnter : kPhaseActive;
		if (S.Behavior == kFlee && S.StartleLeft > 0)
		{
			Ph = kPhaseEnter;
		}
		if (S.Behavior == kHide)
		{
			Ph = S.bArrived ? kPhaseActive : kPhaseEnter;
		}
		if (S.Behavior == kSleep)
		{
			Ph = S.bWaking ? kPhaseExit : (S.StepsIn < Cfg.SleepEnter ? kPhaseEnter : kPhaseActive);
		}
		return Ph;
	}

	/** 진입 (repertoire._enter, 계약 5-2 f). in_cover·cover_k 는 결정 관측 값이다. */
	inline void Enter(FRepState& S, std::int32_t NewBehavior, const FDecisionObs& Obs,
					  const FRepertoireConfig& Cfg = kR1bConfig)
	{
		const std::int32_t Old = S.Behavior;
		S.Behavior = NewBehavior;
		S.Seq = (S.Seq + 1) % kSeqMod;
		S.StepsIn = 0;
		S.LockLeft = EntryLock(NewBehavior, Cfg);
		S.StartleLeft = (NewBehavior == kFlee && Old == kGraze) ? Cfg.StartleSteps : 0;
		S.bWaking = false;
		S.bWakeEv = false;
		S.WakeLeft = 0;
		S.HideTarget = NewBehavior == kHide ? Obs.CoverK : -1;
		S.bArrived = NewBehavior == kHide && Obs.bInCover;
		if (S.bArrived)
		{
			S.LockLeft = Cfg.LockHide;   // 이미 은신처 안이면 곧바로 도착 (E6 없음)
		}
	}

	/**
	 * Arbiter 앞 절반 (계약 5-6 Prepare): a HIDE 도착, b 사건과 기준값 갱신, c 지연, d 기상 끝 판정, e 결정 여부.
	 * 요청을 읽지 않는다. 상태를 바꾸지만 바꾸는 칸은 모두 요청과 무관하다 — Prepare 뒤 Commit 은 Arbitrate 와 같다.
	 * 마스크의 '지금 행동 한 칸'은 Prepare 전(= 뒤, Prepare 는 행동을 바꾸지 않는다)의 Behavior 다.
	 */
	inline FArbiterPrep Prepare(FRepState& S, const FDecisionObs& Obs, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		FArbiterPrep P;

		// a. HIDE 도착
		const bool bArrive = S.Behavior == kHide && !S.bArrived && Obs.bInCover;
		if (bArrive)
		{
			S.bArrived = true;
			S.LockLeft = Cfg.LockHide;
		}
		const bool bE6 = bArrive && S.StepsIn > 0;

		// b. 사건. E1·E2 는 사건 비교 시야 값, 기준값은 실제 시야 값
		const bool bSeen = Obs.PredCount > 0;
		const bool bNear = bSeen && Obs.DPredMin < Cfg.EventNear;
		const bool bFast = bSeen && Obs.PredApproach >= Cfg.EventApproach;
		const bool bSeenEv = Obs.PredCountEv > 0;
		const bool bNearEv = bSeenEv && Obs.DPredMinEv < Cfg.EventNear;
		const bool bFastEv = bSeenEv && Obs.PredApproachEv >= Cfg.EventApproach;
		const bool bLow = Obs.Energy < Cfg.EventEnergy;
		const bool bDark = Obs.Dark >= Cfg.EventDark;

		const bool bE1 = Obs.PredCountEv > S.PrevPc;   // 수의 증가만 (하나 나가고 하나 들어오면 사건이 아니다)
		const bool bE2 = (bNearEv && !S.bPrevNear) || (bFastEv && !S.bPrevFast);
		const bool bE3 = S.Behavior == kSleep && bSeen;
		const bool bE4 = bLow && !S.bPrevLow;
		const bool bE5 = S.bPrevDark != bDark;
		const bool bE7 = Cfg.bKinAlarmEvent && Obs.bAlarmNew && (S.Behavior == kGraze || S.Behavior == kSleep);
		const std::uint8_t Bits = static_cast<std::uint8_t>(
			(bE1 ? kEventE1 : 0u) | (bE2 ? kEventE2 : 0u) | (bE3 ? kEventE3 : 0u) | (bE4 ? kEventE4 : 0u)
			| (bE5 ? kEventE5 : 0u) | (bE6 ? kEventE6 : 0u) | (bE7 ? kEventE7 : 0u));
		const bool bEvent = Bits != 0;

		S.PrevPc = Obs.PredCount;
		S.bPrevNear = bNear;
		S.bPrevFast = bFast;
		S.bPrevLow = bLow;
		S.bPrevDark = bDark;

		// c. 지연: 사건 t 의 결정은 t + Jitter 에 온다
		if (bEvent && S.EvWait < 0)
		{
			S.EvWait = S.Jitter;
		}
		const bool bFire = S.EvWait == 0;
		if (S.EvWait > 0)
		{
			--S.EvWait;
		}

		// d. 기상 끝 판정 (진입은 요청을 읽으므로 Commit 에서 한다)
		S.bWakeEv = S.bWakeEv || (bEvent && S.bWaking);
		const bool bWoke = S.bWaking && S.WakeLeft <= 0;
		const bool bWakeDecide = bWoke && S.bWakeEv;

		// e. 결정 여부. 파이썬은 기상 끝 진입 뒤에 계산하지만 깨는 개체는 !bWoke 로 빠지므로 값이 같다
		const bool bDecide = (S.LockLeft <= 0 || bFire) && !S.bWaking && !bWoke;
		if (bFire || bDecide || bWoke)
		{
			S.EvWait = -1;
		}

		P.bReads = bDecide || bWakeDecide;
		P.bWakeDecide = bWakeDecide;
		P.bWoke = bWoke;
		P.bDecide = bDecide;
		P.bEvent = bEvent;
		P.bFire = bFire;
		P.bE7 = bE7;
		P.EventBits = Bits;
		return P;
	}

	/**
	 * Arbiter 뒤 절반 (계약 5-6 Commit): d 기상 끝 진입, e 바꾸기·기상 시작, f Enter, g 위상.
	 * Request 는 bReads 일 때만 뜻이 있다(아니면 읽지 않는다 — 지금 행동을 넣어도 된다).
	 * Request == Behavior 면 아무것도 하지 않는다(잠금을 새로 걸지 않는다 — 잠금이 끝난 뒤에는 스텝마다 결정 시점).
	 */
	inline FArbiterResult Commit(FRepState& S, const FArbiterPrep& P, std::int32_t Request, const FDecisionObs& Obs,
								 const FRepertoireConfig& Cfg = kR1bConfig)
	{
		if (P.bWoke)
		{
			Enter(S, (P.bWakeDecide && Request != kSleep) ? Request : S.WakeTarget, Obs, Cfg);
		}
		const bool bChange = P.bDecide && Request != S.Behavior;
		const bool bToWake = bChange && S.Behavior == kSleep && Cfg.SleepWake > 0;
		if (bToWake)
		{
			S.bWaking = true;
			S.bWakeEv = false;
			S.WakeLeft = Cfg.SleepWake;
			S.WakeTarget = Request;
		}
		const bool bSwitch = bChange && !bToWake;
		if (bSwitch)
		{
			Enter(S, Request, Obs, Cfg);
		}
		S.Phase = PhaseOf(S, Cfg);

		FArbiterResult R;
		R.bDecide = P.bReads;
		R.bSwitch = bSwitch || P.bWoke;
		R.bEvent = P.bEvent;
		R.bFire = P.bFire;
		R.bE7 = P.bE7;
		R.EventBits = P.EventBits;
		return R;
	}

	/** 한 스텝 결정 (repertoire.arbitrate) = Prepare + Commit. */
	inline FArbiterResult Arbitrate(FRepState& S, std::int32_t Request, const FDecisionObs& Obs,
									const FRepertoireConfig& Cfg = kR1bConfig)
	{
		const FArbiterPrep P = Prepare(S, Obs, Cfg);
		return Commit(S, P, Request, Obs, Cfg);
	}

	/** 스텝 끝 (repertoire.tick, world.step D — t + 1 뒤). 위상은 바꾸지 않는다. */
	inline void Tick(FRepState& S)
	{
		S.StepsIn += 1;
		S.LockLeft -= 1;
		S.StartleLeft = S.StartleLeft - 1 > 0 ? S.StartleLeft - 1 : 0;
		S.WakeLeft = S.WakeLeft - 1 > 0 ? S.WakeLeft - 1 : 0;
	}

	/**
	 * 관측 뒤 away·threat_recency 갱신 (repertoire.perceive, world.step E1). PredCount·AwayFromPred 는 이번 관측(스텝 끝)
	 * 기하다. 보이면 recency ← 1, away ← 가장 가까운 위협 반대. 아니면 recency ← 0.95 · recency, away 그대로.
	 */
	inline void Perceive(FRepState& S, std::int32_t PredCount, const FVec2& AwayFromPred,
						 const FRepertoireConfig& Cfg = kR1bConfig)
	{
		if (PredCount > 0)
		{
			S.Recency = 1.0;
			S.Away = AwayFromPred;
		}
		else
		{
			S.Recency = S.Recency * Cfg.RecencyDecay;
		}
	}

	/** 제어기의 자기 탐지 배수를 다음 관측에 넘긴다 (world._rep_step: see_last ← see, see ← 새 값). */
	inline void CommitSeeMult(FRepState& S, double NewSeeMult)
	{
		S.SeeMultLast = S.SeeMult;
		S.SeeMult = NewSeeMult;
	}

	// ---- 제어기 (계약 6절, repertoire.control) ----

	/** 제어 입력 = 결정 관측 기하(직전 스텝 끝)와 결정 때 위치·먹이 셀. 방향은 단위벡터(없으면 0). */
	struct FControlInput
	{
		FVec2 FoodGrad;          // 먹이 기울기 (정규화)
		FVec2 ToCentroid;        // 보이는 동족 중심 쪽 (정규화)
		FVec2 Separation;        // 분리 (크기 <= 1)
		FVec2 AwayFromPred;      // 가장 가까운 보이는 위협 반대 (안 보이면 0)
		FVec2 ToTarget;          // HIDE 가 고른 은신처 **중심** 쪽 (ToHideTarget). HIDE·미도착이 아니면 읽지 않는다
		std::int32_t PredCount = 0;
		bool bFoodOk = false;    // 결정 때 위치 셀 먹이(섭식 전) >= GrazeEatMin (IsFoodOk)
		bool bInCover = false;   // 결정 관측의 in_cover
		double Dark = 0.0;       // d(t)
	};

	struct FControlOutput
	{
		FVec2 Velocity;               // 단위/스텝 (× UnitsPerStepToCmPerSec 로 cm/s)
		std::int32_t Gait = kGaitStop;
		double EatMult = 0.0;         // 섭식 배수 (밤 배수 전 — EffectiveEatMult)
		double DrainMult = 1.0;       // 대사 배수 (× EnergyDrain)
		double SeeMult = 1.0;         // 자기 위협 탐지 반경 배수 (다음 관측, CommitSeeMult)
		bool bStill = false;          // M1 정지 (위협 표적 체감 거리 × max(은신 배수, CStill))
		bool bCrouch = false;         // M6 웅크림 (도착 HIDE)
		bool bHasFace = false;        // heading 을 Face 로 덮는다 (FREEZE, 위협 방향을 알 때)
		FVec2 Face;                   // = −A (위협 쪽)
		double CoverMult = 1.0;       // 은신처 안일 때의 은신 배수 (밖이면 1 — 위협 모델이 이동 뒤 위치로 다시 판정)
	};

	/** 결정 때 위치 셀의 먹이(섭식 전)로 GRAZE 의 '먹이 충분'. */
	constexpr bool IsFoodOk(double CellFood, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		return CellFood >= Cfg.GrazeEatMin;
	}

	/** HIDE 목표 쪽 = normalize(은신처 중심 − 결정 때 위치) (world._rep_step to_target). */
	inline FVec2 ToHideTarget(const FVec2& Pos, const FVec2& CoverCenter)
	{
		return Normalize(Sub(CoverCenter, Pos));
	}

	/** 은신처 안일 때의 행동별 은신 배수 (repertoire.cover_mult). */
	constexpr double CoverMult(std::int32_t Behavior, bool bCrouch, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		return bCrouch ? Cfg.CoverMultCrouch
			   : Behavior == kGraze ? Cfg.CoverMultGraze
			   : Behavior == kSleep ? Cfg.CoverMultSleep
									: Cfg.CoverMultOther;
	}

	/**
	 * 행동별 제어기 (계약 6-2). S 는 Commit 뒤 상태(이번 스텝 행동). 합 순서는 파이썬과 같다(비트 단위 대조용).
	 *   GRAZE  n(0.83·G + 0.71·C + 1.35·Sep), 먹이 충분이면 정지 아니면 걷기, 섭식 GaitEat[보행], 탐지 × 0.6
	 *   FLEE   n(3·A + 0.71·C + 1.35·Sep), 놀람 중 정지 아니면 뛰기, A = 보이면 위협 반대 아니면 S.Away
	 *   HIDE   도착 전: 목표가 있으면 n(T + 1.35·Sep), 보이면 뛰기 아니면 걷기. 도착: 정지·웅크림
	 *   FREEZE 정지, heading ← −A (A ≠ 0 일 때)
	 *   SLEEP  정지, 탐지 × 0.3, 은신처 안이면 대사 × (1 − 0.6·d)
	 *   방향이 없으면(|raw|² <= 1e-18) 보행은 정지다(섭식 배수도 정지 값).
	 */
	inline FControlOutput Control(const FRepState& S, const FControlInput& In, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		FControlOutput Out;
		const bool bSeen = In.PredCount > 0;
		const FVec2 Sep = Scale(In.Separation, Cfg.SepWeight);
		const FVec2 Coh = Scale(In.ToCentroid, Cfg.GrazeCohesion);
		const FVec2 Away = bSeen ? In.AwayFromPred : S.Away;
		const bool bGraze = S.Behavior == kGraze;
		const bool bFlee = S.Behavior == kFlee;
		const bool bHide = S.Behavior == kHide;
		const bool bCrouch = bHide && S.bArrived;

		FVec2 Raw;
		if (bGraze)
		{
			Raw = Add(Add(Scale(In.FoodGrad, Cfg.GrazeForage), Coh), Sep);
		}
		else if (bFlee)
		{
			Raw = Add(Add(Scale(Away, Cfg.FleeWeight), Coh), Sep);
		}
		else if (bHide && !bCrouch && S.HideTarget >= 0)
		{
			Raw = Add(In.ToTarget, Sep);
		}
		const bool bHasDir = Raw.X * Raw.X + Raw.Y * Raw.Y > kEps * kEps;

		std::int32_t Gait = kGaitStop;
		if (bGraze)
		{
			Gait = In.bFoodOk ? kGaitStop : kGaitWalk;
		}
		else if (bFlee)
		{
			Gait = S.StartleLeft > 0 ? kGaitStop : kGaitRun;
		}
		else if (bHide && !bCrouch)
		{
			Gait = bSeen ? kGaitRun : kGaitWalk;
		}
		if (!bHasDir)
		{
			Gait = kGaitStop;
		}

		Out.Gait = Gait;
		Out.Velocity = Scale(Scale(Normalize(Raw), Cfg.HerbSpeed), Cfg.GaitSpeed[Gait]);
		Out.EatMult = bGraze ? Cfg.GaitEat[Gait] : 0.0;
		const bool bRest = S.Behavior == kSleep && In.bInCover;
		Out.DrainMult = Cfg.GaitDrain[Gait] * (bRest ? 1.0 - Cfg.SleepRest * In.Dark : 1.0);
		Out.SeeMult = bGraze ? Cfg.GrazeHeadDown : (S.Behavior == kSleep ? Cfg.SleepSight : 1.0);
		Out.bStill = S.Behavior == kFreeze || S.Behavior == kSleep || bCrouch;
		Out.bCrouch = bCrouch;
		Out.bHasFace = S.Behavior == kFreeze && IsNonZero(Away);
		Out.Face = Out.bHasFace ? Neg(Away) : FVec2{};
		Out.CoverMult = CoverMult(S.Behavior, bCrouch, Cfg);
		return Out;
	}

	// ---- 이동 (계약 6-3, world.step 1) ----

	/**
	 * 위치 ← clip(P + v, 0, WorldSize) (정사각 맵 벽에서 멈춘다), |v| > 1e-9 면 heading ← normalize(v),
	 * 그 뒤 FREEZE 는 heading ← Face. heading 은 벽 자르기 전 v 로 정한다.
	 * 맵 벽 처리는 학습 세계 그대로다 — 언리얼 레벨의 이동 막힘은 계약 13-2 열린 질문 11.
	 */
	inline void ApplyMove(FVec2& Pos, FVec2& Head, const FControlOutput& Out, double WorldSize)
	{
		const double X = Pos.X + Out.Velocity.X;
		const double Y = Pos.Y + Out.Velocity.Y;
		Pos.X = X < 0.0 ? 0.0 : (X > WorldSize ? WorldSize : X);
		Pos.Y = Y < 0.0 ? 0.0 : (Y > WorldSize ? WorldSize : Y);
		if (std::sqrt(SizeSquared(Out.Velocity)) > kEps)
		{
			Head = Normalize(Out.Velocity);
		}
		if (Out.bHasFace)
		{
			Head = Out.Face;
		}
	}

	// ---- 섭식·대사·번식 (계약 6-3, world._drain_eat·_eat·step 3~4) ----
	// 한 셀의 먹이를 여러 개체가 나누는 것(수요 합 → 먹은 양 = min(수요, 셀 먹이) → 수요 비율)은 세계 몫이다.
	// 개체 쪽: Drain = DrainAmount(DrainMult) → EDrained = E − Drain → Want = EatWant(EDrained, EffectiveEatMult(EatMult, d))
	//          → (세계가 Gain = Want × 셀 비율) → ENew = EnergyAfterIntake(EDrained, Gain) → ApplyReproduction → E <= 0 이면 아사.

	constexpr double DrainAmount(double DrainMult, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		return Cfg.EnergyDrain * DrainMult;
	}

	/** 섭식 배수 × 밤 배수 (1 − 0.9·d). */
	constexpr double EffectiveEatMult(double EatMult, double Dark, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		return EatMult * (1.0 - Cfg.EatNight * Dark);
	}

	/** 개체 수요 = clip((Max − E′) ÷ 0.5, 0, 0.06) × 섭식 배수(밤 배수 포함). */
	constexpr double EatWant(double EnergyDrained, double EatMultEff, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		const double W = (Cfg.MaxEnergy - EnergyDrained) / Cfg.FoodEnergyPerUnit;
		const double C = W < 0.0 ? 0.0 : (W > Cfg.FoodEatRate ? Cfg.FoodEatRate : W);
		return C * EatMultEff;
	}

	/** E_new = min(E′ + 먹은 양 × 0.5, Max). */
	constexpr double EnergyAfterIntake(double EnergyDrained, double Gain, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		const double E = EnergyDrained + Gain * Cfg.FoodEnergyPerUnit;
		return E < Cfg.MaxEnergy ? E : Cfg.MaxEnergy;
	}

	/** 번식: 쿨다운 − 1 (0 에서 멈춤), 그다음 E > 0.9 ∧ 쿨다운 0 이면 E ← 0.5, 쿨다운 ← 200. 번식했으면 참. */
	inline bool ApplyReproduction(double& Energy, std::int32_t& ReproCd, const FRepertoireConfig& Cfg = kR1bConfig)
	{
		ReproCd = ReproCd - 1 > 0 ? ReproCd - 1 : 0;
		if (Energy > Cfg.ReproThreshold && ReproCd == 0)
		{
			Energy = Cfg.InitEnergy;
			ReproCd = Cfg.ReproCooldown;
			return true;
		}
		return false;
	}
}

// v3 행동 고르기 정책 추론 — 파이썬 RepertoirePolicy(herbivore_rl/env_v2/rep_policy.py)의 배포 경로를 C++ 로 옮긴다.
//
// **이 파일은 의도적으로 언리얼에 의존하지 않는다.**
// `<cmath>`·`<cstdint>` 만 쓴다(v1 EcoPolicyInference.h 와 같은 이유). 엔진 없이 g++ 로도 골든을 대조할 수 있고
// (herbivore_rl/tests/test_export_v3.py), 같은 파일이 UE 자동화 시험(Tests/EcoPolicyV3InferenceTest.cpp)에서도 그대로 돈다.
// UObject·Mass 와 무관한 순수 함수뿐이다. 언리얼의 uint8·int32 는 std::uint8_t·std::int32_t 와 같은 타입이다.
//
// 파이썬 배포 경로 (env_v2/rollout.py RepLearned → rep_policy.rep_argmax = predict(deterministic=True)):
//   정책 입력 = [세계 관측 kObsDim | 마스크 5칸]
//   망 입력   = 앞 kObsDim 칸만 (RepObsSlice, 정책·가치 공유 특징 추출기). 마스크 칸은 망에 들어가지 않는다
//   로짓      = W2·tanh(W1·tanh(W0·obs + B0) + B1) + B2      kObsDim → 64 → 64 → 5 (SB3 policy_net + action_net)
//   막기      = 마스크 칸이 0 이면 로짓을 kMaskLogit(-1e9) 로 바꾼다 (MaskedEpsCategorical.proba_distribution)
//   선택      = 막은 로짓의 argmax, 최댓값이 여럿이면 가장 낮은 번호 (torch.argmax — MaskedEpsCategorical.mode)
//   ε 혼합·표본은 학습에만 쓴다. 배포는 argmax 하나다. 가치망은 내보내지 않는다.
//
// 마스크 m = 허용 ∧ 가능 ∧ 결정 (rep_policy.action_mask):
//   허용  kAllowedMask (모델의 rep_allowed — R1b 는 GRAZE·FLEE·HIDE·FREEZE, SLEEP 막힘)
//   가능  ComputeFeasibleMask — 관측만 본다 (rep_policy.feasible_mask)
//         '위협을 안다' = pred_count > 0 또는 threat_recency ≥ kThreatRecencyObs
//                         (판 3 은 alarm_heard ≥ kAlarmMaskObs 도 더한다)
//         FLEE·FREEZE 는 위협을 알 때, HIDE 는 위협을 알고 cover_dist < kHideCoverObs 일 때, GRAZE·SLEEP 은 늘
//   결정  ComposeActionMask — 요청을 읽지 않는 개체는 지금 행동 한 칸, 기상 결정은 SLEEP 을 막는다
//         결정 여부(bReads·bWakeDecide)는 Arbiter 몫이다(파이썬 World.rep_peek). 이 파일은 받기만 한다.
//   문턱 비교는 float 관측과 float 문턱의 비교다. 파이썬도 float32 관측 칸을 같은 문턱과 비교하므로 같은 입력이면 정확히 같다.
//
// 관측 칸 수(kObsDim)·마스크 판(kMaskVersion)·관측 칸 번호는 생성 헤더 상수다. 그래서 R1b(관측 18, 판 2)와
// R2(관측 19 = 18 + 맨 끝 alarm_heard, 판 3)를 같은 코드로 돌린다. 가중치와 마스크 칸 배치는 구조체(FPolicyNetV3·
// FMaskLayoutV3)로도 받으므로, 실행 중 가중치 로더(계획서 4-5 e3)가 다른 모델을 같은 함수로 돌릴 수 있다.
//
// 생성 헤더 (herbivore_rl/export_weights_v3.py, 손으로 고치지 않는다):
//   PolicyWeightsV3.h        가중치·차원·관측 이름·허용 칸·마스크 문턱·계약 해시
//   PolicyGoldenVectorsV3.h  골든 (본·근접 동점·동점 규칙·마스크 문턱·마스크 판 3)
//
// 가중치 레이아웃 ((out, in) 순서):
//   kW0[j*kObsDim + i]   Linear kObsDim -> 64
//   kW1[j*64 + i]        Linear 64 -> 64
//   kW2[j*64 + i]        Linear 64 -> 5

#pragma once

#include <cmath>
#include <cstdint>

#include "PolicyWeightsV3.h"

namespace EcoPolicyV3
{
	// 행동 번호 (herbivore_rl/env_v2/repertoire.py 계약 순서). 한 번 정한 번호의 뜻은 바꾸지 않는다.
	inline constexpr std::int32_t kGraze = 0;
	inline constexpr std::int32_t kFlee = 1;
	inline constexpr std::int32_t kHide = 2;
	inline constexpr std::int32_t kFreeze = 3;
	inline constexpr std::int32_t kSleep = 4;

	// 관측 칸 수의 상한 (스택 배열 크기). 계약은 18·19·21·24 이다.
	inline constexpr std::int32_t kMaxObsDim = 32;

	// 알려진 계약 해시 (export_weights_v3.contract_hash). 생성 헤더의 kContractHash 가 이 중 하나가 아니면 빌드가 멈춘다 —
	// 관측 순서·마스크 판·문턱이 바뀐 모델이 C++ 관측·마스크 코드를 고치지 않은 채 조용히 들어오지 않게.
	// 계약을 바꿀 때는 이 값과 관측을 만드는 쪽을 함께 고친다(herbivore_rl/tests/test_export_v3.py 가 파이썬 값과 대조한다).
	inline constexpr std::uint64_t kContractHashObs18Mask2 = 0x7eea0107339be4ceULL;   // R1b: 관측 18, 마스크 판 2
	inline constexpr std::uint64_t kContractHashObs19Mask3 = 0xf8c26c7d02542faeULL;   // R2: 관측 19 (+ alarm_heard), 판 3
	// R5: 관측 21 (18 + escape_room·obstacle_near·threat_hidden), 판 2 (계약 2-4). 내장 모델의 계약이 아니라 실행 중 두뇌 파일(EcoV3Brain.h)이 쓴다 —
	// 세 칸은 EcoObservationV3::ObstacleObsValues 가 만들고 EcoWorldV3::DecideHerb 가 관측 18 뒤에 붙인다
	inline constexpr std::uint64_t kContractHashObs21Mask2 = 0xbc4fc2d45c47c5fdULL;
	// 두 길 두뇌 (10-22 설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 16절, 이식 계획서 RL_V3_ROUTE_CPP_PORT_PLAN.md): 관측 24 (21 + in_panic·shelter_reach·shelter_edge —
	// EcoObservationV3::kRouteObsNames), 마스크 판 4 (도주 중 칸 1 = RUN·칸 4 = SHELTER·칸 3 막힘). export_weights_v3.contract_hash(관측 24, 판 4) — 계약 dict 의
	// flight_route 키(칸·관측·결정·SHELTER 문턱)까지 덮는다. 내장 모델이 아니라 실행 중 두뇌 파일·평가기가 쓴다
	inline constexpr std::uint64_t kContractHashObs24Mask4 = 0xe302dee198197444ULL;
	// 10-23 R7 판 5 = 판 4 + 반사 밖 두뇌 FLEE 막음 (설계 17절, 이식 계획서 13절 — 계약 dict 에 brain_flee_outside_reflex: false 키). R7e 판정 통과 두뇌의 계약
	inline constexpr std::uint64_t kContractHashObs24Mask5 = 0xad7bad5e1acaf071ULL;

	// ---- 마스크 판 4·5 (두 길 두뇌 — 파이썬 env_v2/rep_policy.py MASK_VERSION_ROUTE·MASK_VERSION_ROUTE_GATE, `_route_rows`·`_gate_free_rows`) ----
	inline constexpr std::int32_t kMaskVersionRoute = 4;        // 관측 in_panic 이 있는 세계: 도주 덮기 줄의 칸 1·4 가 길이다
	inline constexpr std::int32_t kMaskVersionRouteGate = 5;    // 판 4 + 덮기 밖 결정 줄에서 칸 1(FLEE) 막음 — 도주는 반사만 시작한다
	inline constexpr std::int32_t kRouteSlotRun = kFlee;        // 도주 중 칸 1 = RUN (반사 방향 그대로)
	inline constexpr std::int32_t kRouteSlotShelter = kSleep;   // 도주 중 칸 4 = SHELTER (늑대보다 먼저 닿는 은신처)
	inline constexpr std::int32_t kRouteSlotReserved = kFreeze; // 칸 3 = COVER 자리 (판 4·5 에서 늘 막힘)
	// 마스크 덮기 줄 종류 (rep_peek 의 override — 값은 EcoWorldV3::kKeep* 와 같다)
	inline constexpr std::int32_t kMaskOverrideNone = 0;
	inline constexpr std::int32_t kMaskOverridePanic = 2;
	inline constexpr std::int32_t kMaskOverrideCrouch = 3;

	/** 판 4·5 인가 (도주 중 칸 1·4 가 길 — 얼기·잠이 실제 허용에서 막혀야 한다). */
	constexpr bool IsRouteMaskVersion(std::int32_t MaskVersion) { return MaskVersion == kMaskVersionRoute || MaskVersion == kMaskVersionRouteGate; }

	namespace Detail
	{
		constexpr bool StrEq(const char* A, const char* B)
		{
			while (*A != '\0' && *A == *B)
			{
				++A;
				++B;
			}
			return *A == *B;
		}
	}

	// ---- 생성 헤더와의 계약 (컴파일 때 확인) ----
	static_assert(kNumBehaviors == 5, "v3 행동은 Discrete(5) 다");
	static_assert(Detail::StrEq(kBehaviorNames[kGraze], "graze") && Detail::StrEq(kBehaviorNames[kFlee], "flee")
				  && Detail::StrEq(kBehaviorNames[kHide], "hide") && Detail::StrEq(kBehaviorNames[kFreeze], "freeze")
				  && Detail::StrEq(kBehaviorNames[kSleep], "sleep"),
				  "행동 번호 순서가 파이썬 BEHAVIOR_NAMES 와 다르다");
	static_assert(kObsDim > 0 && kObsDim <= kMaxObsDim, "관측 칸 수가 범위를 벗어났다");
	static_assert(kHiddenDim == 64, "v3 망은 obs -> 64 -> 64 -> 5 다 (train.PPO_KWARGS)");
	static_assert(kMaskVersion == 2 || kMaskVersion == 3, "마스크 판은 2 또는 3 이다");
	static_assert((kMaskVersion == 3) == (kObsAlarmHeard >= 0), "판 3 은 관측에 alarm_heard 가 있을 때만이다");
	static_assert(kObsAlarmHeard < 0 || kObsAlarmHeard == kObsDim - 1, "alarm_heard 는 관측 맨 끝 칸이다 (R2 명세 5절)");
	static_assert(Detail::StrEq(kObsNames[kObsPredCount], "pred_count")
				  && Detail::StrEq(kObsNames[kObsThreatRecency], "threat_recency")
				  && Detail::StrEq(kObsNames[kObsCoverDist], "cover_dist"),
				  "마스크 가능 조건의 관측 칸 번호가 이름과 다르다");
	static_assert(kContractHash == kContractHashObs18Mask2 || kContractHash == kContractHashObs19Mask3,
				  "알 수 없는 v3 정책 계약 해시 — 관측·마스크 계약이 바뀌었다. EcoPolicyV3Inference.h 와 관측 코드를 함께 고친다");
	static_assert((kContractHash == kContractHashObs18Mask2) == (kObsDim == 18 && kMaskVersion == 2),
				  "계약 해시가 관측 칸 수·마스크 판과 맞지 않는다");

	/** 망 가중치 보기 (소유하지 않는다). 생성 헤더의 내장 모델은 kBuiltinNet 이다. */
	struct FPolicyNetV3
	{
		std::int32_t ObsDim;      // 18 (R1b), 19 (R2) 또는 21 (R5 장애물 관측 — 실행 중 두뇌 파일)
		const float* W0;          // [64 * ObsDim]
		const float* B0;          // [64]
		const float* W1;          // [64 * 64]
		const float* B1;          // [64]
		const float* W2;          // [5 * 64]
		const float* B2;          // [5]
	};

	inline constexpr FPolicyNetV3 kBuiltinNet = {kObsDim, kW0, kB0, kW1, kB1, kW2, kB2};

	/** 마스크 '가능' 조건이 읽는 관측 칸 번호. AlarmHeard < 0 이면 판 2, 아니면 판 3. */
	struct FMaskLayoutV3
	{
		std::int32_t ObsDim;
		std::int32_t PredCount;
		std::int32_t ThreatRecency;
		std::int32_t CoverDist;
		std::int32_t AlarmHeard;
	};

	inline constexpr FMaskLayoutV3 kBuiltinMaskLayout = {kObsDim, kObsPredCount, kObsThreatRecency, kObsCoverDist,
														 kObsAlarmHeard};

	/**
	 * 관측 Net.ObsDim 칸 -> 원 로짓 5 (막기 전). 마스크는 입력이 아니다 — 파이썬 망도 마스크 칸을 보지 않는다.
	 * 누적은 float, 편향부터 더하고 입력 번호 순서다. torch float32 와의 차는 골든에서 1e-6 수준이다.
	 */
	inline void ComputeLogits(const FPolicyNetV3& Net, const float* Obs, float OutLogits[kNumBehaviors])
	{
		float H1[kHiddenDim];
		float H2[kHiddenDim];

		for (int j = 0; j < kHiddenDim; ++j)
		{
			float S = Net.B0[j];
			for (int i = 0; i < Net.ObsDim; ++i)
			{
				S += Obs[i] * Net.W0[j * Net.ObsDim + i];
			}
			H1[j] = std::tanh(S);
		}

		for (int j = 0; j < kHiddenDim; ++j)
		{
			float S = Net.B1[j];
			for (int i = 0; i < kHiddenDim; ++i)
			{
				S += H1[i] * Net.W1[j * kHiddenDim + i];
			}
			H2[j] = std::tanh(S);
		}

		for (int j = 0; j < kNumBehaviors; ++j)
		{
			float S = Net.B2[j];
			for (int i = 0; i < kHiddenDim; ++i)
			{
				S += H2[i] * Net.W2[j * kHiddenDim + i];
			}
			OutLogits[j] = S;
		}
	}

	/** 내장 모델(PolicyWeightsV3.h)로 관측 kObsDim 칸 -> 원 로짓 5. */
	inline void ComputeLogits(const float* Obs, float OutLogits[kNumBehaviors])
	{
		ComputeLogits(kBuiltinNet, Obs, OutLogits);
	}

	/**
	 * 마스크 argmax. 막힌 칸(Mask[j] == 0)의 로짓을 kMaskLogit 으로 바꾼 뒤 가장 큰 칸을 고른다.
	 *
	 * 동점 규칙: 최댓값이 여럿이면 가장 낮은 번호 (torch.argmax 와 같다 — 엄격한 > 비교로 앞 칸을 지킨다. -0 과 +0 은 같다).
	 * 빈 마스크는 설계상 없다(GRAZE 가 늘 허용·가능). 들어오면 파이썬처럼 모든 칸이 kMaskLogit 이라 0(GRAZE)을 낸다.
	 * 관측은 [0, 1] 의 유한한 값이라 로짓에 NaN 이 없다고 본다.
	 */
	inline std::int32_t SelectAction(const float Logits[kNumBehaviors], const std::uint8_t Mask[kNumBehaviors])
	{
		std::int32_t Best = 0;
		float BestValue = Mask[0] != 0 ? Logits[0] : kMaskLogit;
		for (std::int32_t j = 1; j < kNumBehaviors; ++j)
		{
			const float Value = Mask[j] != 0 ? Logits[j] : kMaskLogit;
			if (Value > BestValue)
			{
				Best = j;
				BestValue = Value;
			}
		}
		return Best;
	}

	/**
	 * 관측 + 마스크 -> 행동 번호 (배포 argmax). OutLogits 에는 원 로짓(막기 전)을 쓴다 — 디버그 표시·골든 대조용.
	 * 파이썬 `rep_argmax(policy, policy_obs(obs, mask))` 와 같은 값이다.
	 */
	inline std::int32_t RunPolicyV3(const FPolicyNetV3& Net, const float* Obs, const std::uint8_t Mask[kNumBehaviors],
									float OutLogits[kNumBehaviors])
	{
		ComputeLogits(Net, Obs, OutLogits);
		return SelectAction(OutLogits, Mask);
	}

	/** 내장 모델로 RunPolicyV3. */
	inline std::int32_t RunPolicyV3(const float* Obs, const std::uint8_t Mask[kNumBehaviors],
									float OutLogits[kNumBehaviors])
	{
		return RunPolicyV3(kBuiltinNet, Obs, Mask, OutLogits);
	}

	/** 마스크 '가능' 칸 (rep_policy.feasible_mask). 관측만 본다. */
	inline void ComputeFeasibleMask(const FMaskLayoutV3& Layout, const float* Obs, std::uint8_t OutFeasible[kNumBehaviors])
	{
		bool bThreat = Obs[Layout.PredCount] > 0.0f || Obs[Layout.ThreatRecency] >= kThreatRecencyObs;
		if (Layout.AlarmHeard >= 0)
		{
			// 판 3 (v3 R2 M8): 동족 경보를 들었으면 위협을 안다
			bThreat = bThreat || Obs[Layout.AlarmHeard] >= kAlarmMaskObs;
		}
		OutFeasible[kGraze] = 1;
		OutFeasible[kFlee] = bThreat ? 1 : 0;
		OutFeasible[kHide] = (bThreat && Obs[Layout.CoverDist] < kHideCoverObs) ? 1 : 0;
		OutFeasible[kFreeze] = bThreat ? 1 : 0;
		OutFeasible[kSleep] = 1;
	}

	/** 내장 모델의 관측 칸 배치로 ComputeFeasibleMask. */
	inline void ComputeFeasibleMask(const float* Obs, std::uint8_t OutFeasible[kNumBehaviors])
	{
		ComputeFeasibleMask(kBuiltinMaskLayout, Obs, OutFeasible);
	}

	/**
	 * 정책 입력 마스크 m = 허용 ∧ 가능 ∧ 결정 (rep_policy.action_mask).
	 *
	 *   bReads == false (요청을 읽지 않는 개체)  -> 지금 행동 한 칸만 1 (log π = 0, 행동이 바뀌지 않는다)
	 *   bReads == true                           -> Allowed ∧ Feasible, 기상 결정(bWakeDecide)이면 SLEEP 을 막는다
	 *                                               (기상 결정의 SLEEP 요청은 wake_target 으로 바뀌어 다른 칸과 같은 뜻이 된다)
	 */
	inline void ComposeActionMask(const std::uint8_t Allowed[kNumBehaviors], const std::uint8_t Feasible[kNumBehaviors],
								  bool bReads, bool bWakeDecide, std::int32_t CurrentBehavior,
								  std::uint8_t OutMask[kNumBehaviors])
	{
		for (std::int32_t j = 0; j < kNumBehaviors; ++j)
		{
			if (bReads)
			{
				OutMask[j] = (Allowed[j] != 0 && Feasible[j] != 0) ? 1 : 0;
			}
			else
			{
				OutMask[j] = j == CurrentBehavior ? 1 : 0;
			}
		}
		if (bReads && bWakeDecide)
		{
			OutMask[kSleep] = 0;
		}
	}

	/** 내장 모델의 허용 칸(kAllowedMask)으로 ComposeActionMask. */
	inline void ComposeActionMask(const std::uint8_t Feasible[kNumBehaviors], bool bReads, bool bWakeDecide,
								  std::int32_t CurrentBehavior, std::uint8_t OutMask[kNumBehaviors])
	{
		ComposeActionMask(kAllowedMask, Feasible, bReads, bWakeDecide, CurrentBehavior, OutMask);
	}

	/**
	 * 마스크 판 4·5 의 덮기 줄과 판 5 의 반사 밖 FLEE 막음 (rep_policy.action_mask 의 `_route_rows`·`_gate_free_rows` — 이식 계획서 4절·13-1).
	 * InOutMask 는 판 2 마스크(ComposeActionMask — 허용 ∧ 가능 ∧ 결정)를 받아 고친다. 판 4·5 가 아니면 그대로 둔다.
	 *   Override       다음 스텝 덮기 (kMaskOverride* — 파이썬 rep_peek 의 override: 도주·웅크림, 그 밖(경계 포함)은 None)
	 *   bRouteDecide   도주 길 결정 스텝 (덮기 도주일 때만 읽는다)        bRouteNowShelter  지금 길이 SHELTER (도주 ∧ 결정 아님일 때만 읽는다)
	 *   ShelterReachObs 관측 22 (shelter_reach — > 0 이면 SHELTER 가능)   bReads            요청을 읽나 (덮기 밖이면 Arbiter 결정)
	 * 줄:  도주 ∧ 결정 → {1 RUN, 4 SHELTER (관측 22 > 0)}, 도주 ∧ 결정 아님 → 지금 길 한 칸 (RUN 1 · SHELTER 4), 웅크림 → {HIDE},
	 *      그 밖 → 판 2 그대로 — 판 5 이고 bReads 면 칸 1(FLEE)을 막는다(결정이 아닌 줄 = 지금 행동 한 칸은 그대로 — 반사가 끝난 뒤 잠금 중인 FLEE 포함).
	 * 칸 3 은 판 4·5 에서 늘 0 이다: 덮기 줄은 1·4 만 켜고, 그 밖 줄은 실제 허용이 막는다(판 4·5 두뇌를 걸 때 얼기·잠 허용 0 을 확인한다).
	 * GRAZE 는 늘 허용 ∧ 가능이라 판 5 막기로 빈 줄이 생기지 않는다(파이썬 `_gate_free_rows`).
	 */
	inline void ApplyRouteMaskRows(std::int32_t MaskVersion, std::int32_t Override, bool bRouteDecide, bool bRouteNowShelter, float ShelterReachObs,
								   bool bReads, std::uint8_t InOutMask[kNumBehaviors])
	{
		if (!IsRouteMaskVersion(MaskVersion))
		{
			return;
		}
		if (Override == kMaskOverridePanic || Override == kMaskOverrideCrouch)
		{
			for (std::int32_t j = 0; j < kNumBehaviors; ++j)
			{
				InOutMask[j] = 0;
			}
			if (Override == kMaskOverrideCrouch)
			{
				InOutMask[kHide] = 1;
				return;
			}
			InOutMask[kRouteSlotRun] = (bRouteDecide || !bRouteNowShelter) ? 1 : 0;
			InOutMask[kRouteSlotShelter] = ((bRouteDecide && ShelterReachObs > 0.0f) || (!bRouteDecide && bRouteNowShelter)) ? 1 : 0;
			return;
		}
		if (MaskVersion == kMaskVersionRouteGate && bReads)
		{
			InOutMask[kFlee] = 0;
		}
	}
}

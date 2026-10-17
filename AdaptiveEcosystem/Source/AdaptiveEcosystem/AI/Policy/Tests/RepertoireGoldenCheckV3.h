// v3 R1b 세계 개체 논리 골든 대조 — EcoRepertoire.h·EcoObservationV3.h 를 RepertoireGoldenVectorsV3.h 와 맞춘다.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>` 와 엔진 무관 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoRepertoireV3Test.cpp (AdaptiveEcosystem.Policy.V3.Repertoire.*, .Observation.*)
//   g++ 하네스       herbivore_rl/tests/cpp/parity_repertoire_v3_main.cpp (herbivore_rl/tests/test_repertoire_golden_v3.py)
// 검사 하나가 FReport 하나를 낸다: 사례 수, 어긋난 사례 수, 실수 최대 오차, 처음 어긋난 사례와 칸.
// 허용: 실수 |C++ − Python| <= Golden::kFloatTolerance, 정수·열거·불은 정확히 같다.
//
// Arbiter 열은 어긋난 스텝 뒤 상태를 골든 값으로 다시 맞춘다 — 한 번 어긋난 것이 뒤 스텝으로 번져 수가 부풀지 않게.

#pragma once

#include <cmath>
#include <cstdint>

#include "../EcoObservationV3.h"
#include "../EcoPolicyV3Inference.h"
#include "../EcoRepertoire.h"
#include "../RepertoireGoldenVectorsV3.h"

namespace EcoRepertoireV3::Check
{
	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례 (Arbiter 는 스텝)
		std::int32_t Skipped = 0;      // 문턱 근처·해당 없음으로 뺀 사례
		std::int32_t Failures = 0;     // 어긋난 사례
		double MaxError = 0.0;         // 실수 칸 최대 |C++ − Python|
		std::int32_t FloatCount = 0;   // 비교한 실수 칸
		std::int32_t FloatExact = 0;   // 그중 비트 단위로 같은 칸
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (검사마다 뜻은 아래 주석)

		bool Passed() const { return Failures == 0 && Cases > 0; }
	};

	namespace Detail
	{
		/** 사례 하나의 대조 상태. Field 는 처음 어긋난 칸. */
		struct FCase
		{
			FReport& R;
			std::int32_t Field = -1;

			explicit FCase(FReport& InR) : R(InR) {}

			void Int(std::int32_t Id, std::int64_t Got, std::int64_t Want)
			{
				if (Got != Want && Field < 0)
				{
					Field = Id;
				}
			}

			void Real(std::int32_t Id, double Got, double Want)
			{
				const double E = std::fabs(Got - Want);
				R.MaxError = E > R.MaxError ? E : R.MaxError;
				++R.FloatCount;
				R.FloatExact += Got == Want ? 1 : 0;
				if (!(E <= Golden::kFloatTolerance) && Field < 0)
				{
					Field = Id;
				}
			}

			/** 사례를 닫는다. 어긋났으면 참. */
			bool Close(std::int32_t CaseIndex)
			{
				++R.Cases;
				if (Field >= 0)
				{
					if (R.Failures == 0)
					{
						R.FirstCase = CaseIndex;
						R.FirstField = Field;
					}
					++R.Failures;
					return true;
				}
				return false;
			}
		};

		inline FRepState StateFromInts(const std::int32_t* V)
		{
			FRepState S;
			S.Behavior = V[0];
			S.Phase = V[1];
			S.StepsIn = V[2];
			S.Seq = V[3];
			S.LockLeft = V[4];
			S.StartleLeft = V[5];
			S.bWaking = V[6] != 0;
			S.WakeLeft = V[7];
			S.WakeTarget = V[8];
			S.bWakeEv = V[9] != 0;
			S.EvWait = V[10];
			S.HideTarget = V[11];
			S.bArrived = V[12] != 0;
			S.PrevPc = V[13];
			S.bPrevNear = V[14] != 0;
			S.bPrevFast = V[15] != 0;
			S.bPrevLow = V[16] != 0;
			S.bPrevDark = V[17] != 0;
			S.Jitter = V[18];
			return S;
		}

		/** 논리 칸 19개만 덮는다 (away·recency·탐지 배수는 그대로). */
		inline void SetStateInts(FRepState& S, const std::int32_t* V)
		{
			const FRepState T = StateFromInts(V);
			const FVec2 Away = S.Away;
			const double Recency = S.Recency;
			const double See = S.SeeMult;
			const double SeeLast = S.SeeMultLast;
			S = T;
			S.Away = Away;
			S.Recency = Recency;
			S.SeeMult = See;
			S.SeeMultLast = SeeLast;
		}

		inline void CompareState(FCase& C, const FRepState& S, const std::int32_t* Want)
		{
			const std::int64_t Got[19] = {S.Behavior, S.Phase, S.StepsIn, S.Seq, S.LockLeft, S.StartleLeft, S.bWaking ? 1 : 0,
										  S.WakeLeft, S.WakeTarget, S.bWakeEv ? 1 : 0, S.EvWait, S.HideTarget,
										  S.bArrived ? 1 : 0, S.PrevPc, S.bPrevNear ? 1 : 0, S.bPrevFast ? 1 : 0,
										  S.bPrevLow ? 1 : 0, S.bPrevDark ? 1 : 0, S.Jitter};
			for (std::int32_t f = 0; f < 19; ++f)
			{
				C.Int(f, Got[f], Want[f]);
			}
		}

		inline FDecisionObs StepObs(std::int32_t N)
		{
			const std::int32_t* I = &Golden::kStepObsInt[N * Golden::kObsIntCount];
			const double* D = &Golden::kStepObsReal[N * Golden::kObsRealCount];
			FDecisionObs O;
			O.PredCount = I[0];
			O.PredCountEv = I[1];
			O.bInCover = I[2] != 0;
			O.CoverK = I[3];
			O.DPredMin = D[0];
			O.PredApproach = D[1];
			O.DPredMinEv = D[2];
			O.PredApproachEv = D[3];
			O.Energy = D[4];
			O.Dark = D[5];
			O.bAlarmNew = Golden::kStepAlarmNew[N] != 0;
			return O;
		}

		inline bool Flag(std::int32_t N, std::uint8_t Bit) { return (Golden::kStepFlags[N] & Bit) != 0; }
	}

	/** 0. 세계 상수 — 골든 표의 모든 이름이 C++ 상수와 짝지어지고 값이 정확히 같다. FirstField = 표 번호. */
	inline FReport CheckConstants()
	{
		struct FNamed
		{
			const char* Name;
			double Value;
		};
		constexpr const FRepertoireConfig& C = kR1bConfig;
		constexpr const EcoObservationV3::FObservationConfig& O = EcoObservationV3::kR1bObsConfig;
		const FNamed Ours[] = {
			{"lock_graze", static_cast<double>(C.LockGraze)},
			{"lock_flee", static_cast<double>(C.LockFlee)},
			{"lock_freeze", static_cast<double>(C.LockFreeze)},
			{"lock_hide", static_cast<double>(C.LockHide)},
			{"hide_travel_max", static_cast<double>(C.HideTravelMax)},
			{"sleep_enter", static_cast<double>(C.SleepEnter)},
			{"sleep_hold", static_cast<double>(C.SleepHold)},
			{"sleep_wake", static_cast<double>(C.SleepWake)},
			{"startle_steps", static_cast<double>(C.StartleSteps)},
			{"decision_jitter", static_cast<double>(C.DecisionJitter)},
			{"event_near", C.EventNear},
			{"event_approach", C.EventApproach},
			{"event_energy", C.EventEnergy},
			{"event_dark", C.EventDark},
			{"recency_decay", C.RecencyDecay},
			{"graze_head_down", C.GrazeHeadDown},
			{"sleep_sight", C.SleepSight},
			{"graze_forage", C.GrazeForage},
			{"graze_cohesion", C.GrazeCohesion},
			{"graze_eat_min", C.GrazeEatMin},
			{"sleep_rest", C.SleepRest},
			{"cover_mult_crouch", C.CoverMultCrouch},
			{"cover_mult_graze", C.CoverMultGraze},
			{"cover_mult_sleep", C.CoverMultSleep},
			{"cover_mult_other", C.CoverMultOther},
			{"c_still", C.CStill},
			{"steps_norm", O.StepsNorm},
			{"sep_weight", C.SepWeight},
			{"flee_weight", C.FleeWeight},
			{"herb_speed", C.HerbSpeed},
			{"herb_speed", O.HerbSpeed},
			{"energy_drain", C.EnergyDrain},
			{"max_energy", C.MaxEnergy},
			{"max_energy", O.MaxEnergy},
			{"init_energy", C.InitEnergy},
			{"food_eat_rate", C.FoodEatRate},
			{"food_energy_per_unit", C.FoodEnergyPerUnit},
			{"repro_threshold", C.ReproThreshold},
			{"repro_cd", static_cast<double>(C.ReproCooldown)},
			{"see_r", O.SeeR},
			{"obs_pred_count_norm", O.ObsPredCountNorm},
			{"obs_kin_count_norm", O.ObsKinCountNorm},
			{"obs_cover_norm", O.ObsCoverNorm},
			{"sep_radius", O.SepRadius},
			{"predation_ema_decay", O.PredationEmaDecay},
			{"predation_ema_gain", O.PredationEmaGain},
			{"grid_unit_cm", kUnitCm},
			{"fov_cos", O.FovCos},
			{"step_seconds", kStepSeconds},
			{"gait_speed_0", C.GaitSpeed[0]},
			{"gait_speed_1", C.GaitSpeed[1]},
			{"gait_speed_2", C.GaitSpeed[2]},
			{"gait_eat_0", C.GaitEat[0]},
			{"gait_eat_1", C.GaitEat[1]},
			{"gait_eat_2", C.GaitEat[2]},
			{"drain_mult_0", C.GaitDrain[0]},
			{"drain_mult_1", C.GaitDrain[1]},
			{"drain_mult_2", C.GaitDrain[2]},
			{"c_rest", C.CRest},
			{"c_move", C.CMove},
			{"detect_night", O.DetectNight},
			{"eat_night", C.EatNight},
			{"transition_norm", O.TransitionNorm},
			{"jitter_tag", static_cast<double>(kJitterTag)},
			{"seq_mod", static_cast<double>(kSeqMod)},
			{"eps", kEps},
			{"alarm_event", C.bKinAlarmEvent ? 1.0 : 0.0},
			{"obs_dim", static_cast<double>(EcoObservationV3::kObsDim)},
		};
		const std::int32_t NumOurs = static_cast<std::int32_t>(sizeof(Ours) / sizeof(Ours[0]));

		FReport R;
		for (std::int32_t k = 0; k < Golden::kWorldConstantCount; ++k)
		{
			Detail::FCase Case(R);
			bool bMatched = false;
			for (std::int32_t m = 0; m < NumOurs; ++m)
			{
				if (EcoPolicyV3::Detail::StrEq(Ours[m].Name, Golden::kWorldConstantNames[k]))
				{
					bMatched = true;
					if (Ours[m].Value != Golden::kWorldConstantValues[k])
					{
						Case.Int(0, 1, 0);
					}
				}
			}
			if (!bMatched)
			{
				Case.Int(1, 1, 0);   // 짝이 없는 파이썬 상수 — C++ 상수를 더한다
			}
			Case.Close(k);
		}
		// C++ 쪽 이름이 모두 골든 표에 있다
		for (std::int32_t m = 0; m < NumOurs; ++m)
		{
			bool bFound = false;
			for (std::int32_t k = 0; k < Golden::kWorldConstantCount; ++k)
			{
				bFound = bFound || EcoPolicyV3::Detail::StrEq(Ours[m].Name, Golden::kWorldConstantNames[k]);
			}
			Detail::FCase Case(R);
			Case.Int(2, bFound ? 0 : 1, 0);
			Case.Close(Golden::kWorldConstantCount + m);
		}
		return R;
	}

	/** 1. 지연 해시. 칸: 0 H, 1 지연, 2 개체 키. */
	inline FReport CheckJitterHash()
	{
		FReport R;
		for (std::int32_t n = 0; n < Golden::kHashCount; ++n)
		{
			Detail::FCase Case(R);
			const std::int64_t Seed = Golden::kHashSeed[n];
			const std::uint64_t Key = Golden::kHashKey[n];
			Case.Int(0, JitterHash(Seed, Key) == Golden::kHashValue[n] ? 0 : 1, 0);
			Case.Int(1, DecisionJitter(Seed, Key, kR1bConfig.DecisionJitter), Golden::kHashJitter[n]);
			const std::uint64_t Made = Golden::kHashSlot[n] >= 0
										   ? MakeAgentKey(static_cast<std::uint32_t>(Golden::kHashSlot[n]),
														  static_cast<std::uint32_t>(Golden::kHashGeneration[n]))
										   : MakeAgentKeyFromStableId(static_cast<std::int64_t>(Key));
			Case.Int(2, Made == Key ? 0 : 1, 0);
			Case.Close(n);
		}
		return R;
	}

	enum class ESequenceMode
	{
		Arbitrate,        // Arbitrate 한 번
		PrepareCommit,    // Prepare → (reads·기상 결정 대조) → Commit
		ClosedLoop,       // Prepare → 마스크 → 망(RunPolicyV3) → Commit (관측을 실은 창만)
	};

	/**
	 * 2. Arbiter 열. 칸: 0..18 상태(kStateFieldNames), 19 decide, 20 switch, 21 event, 22 fire, 23 e7, 24 사건 비트,
	 * 25 reads, 26 기상 결정, 27 망 요청(닫힌 고리). 사례 = 스텝.
	 */
	inline FReport CheckSequences(ESequenceMode Mode)
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t s = 0; s < kSeqCount; ++s)
		{
			if (Mode == ESequenceMode::ClosedLoop && kSeqLoopStart[s] < 0)
			{
				continue;
			}
			FRepertoireConfig Cfg = kR1bConfig;
			Cfg.bKinAlarmEvent = kSeqAlarm[s] != 0;
			FRepState S = Detail::StateFromInts(&kSeqInitState[s * kStateFieldCount]);
			for (std::int32_t k = 0; k < kSeqLength[s]; ++k)
			{
				const std::int32_t n = kSeqStart[s] + k;
				const FDecisionObs O = Detail::StepObs(n);
				std::int32_t Request = kStepRequest[n];
				Detail::FCase Case(R);
				FArbiterResult Res;
				if (Mode == ESequenceMode::Arbitrate)
				{
					Res = Arbitrate(S, Request, O, Cfg);
				}
				else
				{
					const std::int32_t Before = S.Behavior;
					const FArbiterPrep P = Prepare(S, O, Cfg);
					Case.Int(25, P.bReads ? 1 : 0, Detail::Flag(n, kFlagReads) ? 1 : 0);
					Case.Int(26, P.bWakeDecide ? 1 : 0, Detail::Flag(n, kFlagWakeDecide) ? 1 : 0);
					if (Mode == ESequenceMode::ClosedLoop)
					{
						const float* Obs = &kLoopObs[(kSeqLoopStart[s] + k) * EcoPolicyV3::kObsDim];
						std::int32_t Chosen = Before;   // 읽지 않는 개체의 마스크는 지금 행동 한 칸 → argmax = 지금 행동
						if (P.bReads)
						{
							std::uint8_t Feasible[EcoPolicyV3::kNumBehaviors];
							std::uint8_t Mask[EcoPolicyV3::kNumBehaviors];
							float Logits[EcoPolicyV3::kNumBehaviors];
							EcoPolicyV3::ComputeFeasibleMask(Obs, Feasible);
							EcoPolicyV3::ComposeActionMask(Feasible, true, P.bWakeDecide, Before, Mask);
							Chosen = EcoPolicyV3::RunPolicyV3(Obs, Mask, Logits);
						}
						Case.Int(27, Chosen, Request);
						Request = Chosen;
					}
					Res = Commit(S, P, Request, O, Cfg);
				}
				Detail::CompareState(Case, S, &kStepState[n * kStateFieldCount]);
				Case.Int(19, Res.bDecide ? 1 : 0, Detail::Flag(n, kFlagDecide) ? 1 : 0);
				Case.Int(20, Res.bSwitch ? 1 : 0, Detail::Flag(n, kFlagSwitch) ? 1 : 0);
				Case.Int(21, Res.bEvent ? 1 : 0, Detail::Flag(n, kFlagEvent) ? 1 : 0);
				Case.Int(22, Res.bFire ? 1 : 0, Detail::Flag(n, kFlagFire) ? 1 : 0);
				Case.Int(23, Res.bE7 ? 1 : 0, Detail::Flag(n, kFlagE7) ? 1 : 0);
				Case.Int(24, Res.EventBits, kStepEvents[n]);
				if (Case.Close(n))
				{
					Detail::SetStateInts(S, &kStepState[n * kStateFieldCount]);
				}
				Tick(S);
				if (kStepRespawn[n] != 0)
				{
					RespawnAgent(S, kStepRespawnEnergy[n], kStepRespawnDark[n], kSeqSeed[s],
								 MakeAgentKey(static_cast<std::uint32_t>(kSeqSlot[s]),
											  static_cast<std::uint32_t>(kStepRespawnGeneration[n])),
								 Cfg);
				}
			}
		}
		return R;
	}

	/** 2′. 처음 나는 개체 (InitAgent) — 시작 상태가 새 개체인 열. 칸: 상태 0..18, 19 탐지 배수. */
	inline FReport CheckInitAgent()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t s = 0; s < kSeqCount; ++s)
		{
			if (kSeqFresh[s] == 0)
			{
				++R.Skipped;
				continue;
			}
			FRepState S;
			S.Seq = 77;   // InitAgent 가 0 으로 둔다
			InitAgent(S, kSeqInitEnergy[s], kSeqInitDark[s], kSeqSeed[s],
					  MakeAgentKey(static_cast<std::uint32_t>(kSeqSlot[s]), static_cast<std::uint32_t>(kSeqGeneration[s])));
			Detail::FCase Case(R);
			Detail::CompareState(Case, S, &kSeqInitState[s * kStateFieldCount]);
			Case.Real(19, S.SeeMult, kR1bConfig.GrazeHeadDown);
			Case.Close(s);
		}
		return R;
	}

	/** 3. 리스폰 (reset_slots). 칸: 상태 0..18, 19 recency·away·탐지 배수. */
	inline FReport CheckRespawn()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t n = 0; n < kRespawnCount; ++n)
		{
			FRepState S = Detail::StateFromInts(&kRespawnPre[n * kStateFieldCount]);
			S.Away = {0.3, -0.4};
			S.Recency = 0.7;
			S.SeeMult = 1.0;
			S.SeeMultLast = 0.3;
			RespawnAgent(S, kRespawnEnergy[n], kRespawnDark[n], kRespawnSeed[n],
						 MakeAgentKey(static_cast<std::uint32_t>(kRespawnSlot[n]),
									  static_cast<std::uint32_t>(kRespawnGeneration[n])));
			Detail::FCase Case(R);
			Detail::CompareState(Case, S, &kRespawnPost[n * kStateFieldCount]);
			Case.Real(19, S.Recency, 0.0);
			Case.Real(19, S.Away.X, 0.0);
			Case.Real(19, S.Away.Y, 0.0);
			Case.Real(19, S.SeeMult, kR1bConfig.GrazeHeadDown);
			Case.Real(19, S.SeeMultLast, kR1bConfig.GrazeHeadDown);
			Case.Close(n);
		}
		return R;
	}

	namespace Detail
	{
		inline FRepState ControlState(std::int32_t n)
		{
			const std::int32_t* I = &Golden::kCtlStateInt[n * 4];
			FRepState S;
			S.Behavior = I[0];
			S.StartleLeft = I[1];
			S.HideTarget = I[2];
			S.bArrived = I[3] != 0;
			S.Away = {Golden::kCtlAway[n * 2], Golden::kCtlAway[n * 2 + 1]};
			return S;
		}

		inline FControlInput ControlInput(std::int32_t n)
		{
			const double* V = &Golden::kCtlVecIn[n * 10];
			const std::int32_t* I = &Golden::kCtlIntIn[n * 3];
			FControlInput In;
			In.FoodGrad = {V[0], V[1]};
			In.ToCentroid = {V[2], V[3]};
			In.Separation = {V[4], V[5]};
			In.AwayFromPred = {V[6], V[7]};
			In.ToTarget = {V[8], V[9]};
			In.PredCount = I[0];
			In.bFoodOk = I[1] != 0;
			In.bInCover = I[2] != 0;
			In.Dark = Golden::kCtlDark[n];
			return In;
		}
	}

	/** 4. 제어기. 칸: 0 속도 x, 1 속도 y, 2 보행, 3 섭식, 4 대사, 5 탐지, 6 은신, 7 정지, 8 웅크림, 9 heading 덮기, 10 face x, 11 face y, 12 먹이 판정. */
	inline FReport CheckControl()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t n = 0; n < kControlCount; ++n)
		{
			const FRepState S = Detail::ControlState(n);
			const FControlInput In = Detail::ControlInput(n);
			const FControlOutput Out = Control(S, In);
			Detail::FCase Case(R);
			Case.Real(0, Out.Velocity.X, kCtlVelocity[n * 2]);
			Case.Real(1, Out.Velocity.Y, kCtlVelocity[n * 2 + 1]);
			Case.Int(2, Out.Gait, kCtlGait[n]);
			Case.Real(3, Out.EatMult, kCtlReal[n * 4]);
			Case.Real(4, Out.DrainMult, kCtlReal[n * 4 + 1]);
			Case.Real(5, Out.SeeMult, kCtlReal[n * 4 + 2]);
			Case.Real(6, Out.CoverMult, kCtlReal[n * 4 + 3]);
			Case.Int(7, Out.bStill ? 1 : 0, kCtlBool[n * 3]);
			Case.Int(8, Out.bCrouch ? 1 : 0, kCtlBool[n * 3 + 1]);
			Case.Int(9, Out.bHasFace ? 1 : 0, kCtlBool[n * 3 + 2]);
			Case.Real(10, Out.Face.X, kCtlFace[n * 2]);
			Case.Real(11, Out.Face.Y, kCtlFace[n * 2 + 1]);
			if (kCtlFoodCheck[n] != 0)
			{
				Case.Int(12, IsFoodOk(kCtlCellFood[n]) ? 1 : 0, kCtlIntIn[n * 3 + 1]);
			}
			Case.Close(n);
		}
		return R;
	}

	/** 4′. 이동 (골든 속도·heading 덮기로 ApplyMove). 칸: 0 위치 x, 1 위치 y, 2 heading x, 3 heading y. */
	inline FReport CheckMove()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t n = 0; n < kControlCount; ++n)
		{
			if (kCtlHasMove[n] == 0)
			{
				++R.Skipped;
				continue;
			}
			const double* M = &kCtlMove[n * 8];
			FControlOutput Out;
			Out.Velocity = {kCtlVelocity[n * 2], kCtlVelocity[n * 2 + 1]};
			Out.bHasFace = kCtlBool[n * 3 + 2] != 0;
			Out.Face = {kCtlFace[n * 2], kCtlFace[n * 2 + 1]};
			FVec2 Pos = {M[0], M[1]};
			FVec2 Head = {M[2], M[3]};
			ApplyMove(Pos, Head, Out, kCtlWorldSize[n]);
			Detail::FCase Case(R);
			Case.Real(0, Pos.X, M[4]);
			Case.Real(1, Pos.Y, M[5]);
			Case.Real(2, Head.X, M[6]);
			Case.Real(3, Head.Y, M[7]);
			Case.Close(n);
		}
		return R;
	}

	/**
	 * 4″. 섭식·대사·번식 (셀 나누기 비율은 세계 값). 각 단계는 골든의 앞 단계 값을 입력으로 받는다(단계별로 가른다).
	 * 칸: 0 E′, 1 섭식 배수(밤), 2 수요, 3 먹은 양, 4 E_new, 5 번식 뒤 E, 6 쿨다운, 7 번식함.
	 */
	inline FReport CheckEnergy()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t n = 0; n < kControlCount; ++n)
		{
			if (kCtlHasEnergy[n] == 0)
			{
				++R.Skipped;
				continue;
			}
			const double* E = &kCtlEnergy[n * 8];   // E, E′, 섭식 배수, 수요, 비율, 먹은 양, E_new, 번식 뒤 E
			const std::int32_t* Rp = &kCtlRepro[n * 3];
			Detail::FCase Case(R);
			Case.Real(0, E[0] - DrainAmount(kCtlReal[n * 4 + 1]), E[1]);
			Case.Real(1, EffectiveEatMult(kCtlReal[n * 4], kCtlDark[n]), E[2]);
			Case.Real(2, EatWant(E[1], E[2]), E[3]);
			Case.Real(3, E[3] * E[4], E[5]);
			Case.Real(4, EnergyAfterIntake(E[1], E[5]), E[6]);
			double Energy = E[6];
			std::int32_t Cd = Rp[0];
			const bool bRepro = ApplyReproduction(Energy, Cd);
			Case.Real(5, Energy, E[7]);
			Case.Int(6, Cd, Rp[1]);
			Case.Int(7, bRepro ? 1 : 0, Rp[2]);
			Case.Close(n);
		}
		return R;
	}

	/** 5. Perceive. 칸: 0 recency, 1 away x, 2 away y. */
	inline FReport CheckPerceive()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t n = 0; n < kPerceiveCount; ++n)
		{
			const double* V = &kPerReal[n * 8];
			FRepState S;
			S.Recency = V[0];
			S.Away = {V[1], V[2]};
			Perceive(S, kPerPredCount[n], {V[3], V[4]});
			Detail::FCase Case(R);
			Case.Real(0, S.Recency, V[5]);
			Case.Real(1, S.Away.X, V[6]);
			Case.Real(2, S.Away.Y, V[7]);
			Case.Close(n);
		}
		return R;
	}

	/** 6. 관측 만들기. 칸 = 관측 칸 번호 0..17. */
	inline FReport CheckObservationBuild()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t n = 0; n < kObsBuildCount; ++n)
		{
			const std::int32_t* I = &kObInt[n * 6];
			const double* D = &kObReal[n * 9];
			EcoObservationV3::FObservationInput In;
			In.FoodDensity = D[0];
			In.PredCount = I[0];
			In.DPredMin = D[1];
			In.KinCount = I[1];
			In.Energy = D[2];
			In.PredEma = D[3];
			In.bHasCover = I[2] != 0;
			In.CoverEdge = D[4];
			In.Dark = D[5];
			In.StepsToTransition = I[3];
			In.PredApproach = D[6];
			In.KinAlarm = D[7];
			In.Behavior = I[4];
			In.StepsIn = I[5];
			In.Recency = D[8];
			float Out[EcoObservationV3::kObsDim];
			EcoObservationV3::BuildObservation(In, Out);
			Detail::FCase Case(R);
			for (std::int32_t i = 0; i < EcoObservationV3::kObsDim; ++i)
			{
				Case.Real(i, Out[i], kObExpected[n * EcoObservationV3::kObsDim + i]);
			}
			Case.Close(n);
		}
		return R;
	}

	/**
	 * 7. 지각 스냅샷 (개체 하나 = 사례). 칸: 0 위협 수, 1 사건 비교 위협 수, 2 동족 수, 3 은신처, 4 은신처 안,
	 * 5 거리, 6·7 위협 반대, 8 접근, 9 사건 거리, 10 사건 접근, 11·12 무리 중심 쪽, 13·14 분리, 15 동족 경보, 16 은신 거리 관측,
	 * 17 가장자리, 18 탐지 기본 반경(스냅샷마다, 사례 -1 - s).
	 */
	inline FReport CheckPerception()
	{
		using namespace Golden;
		namespace Obs = EcoObservationV3;
		FReport R;
		for (std::int32_t s = 0; s < kSnapCount; ++s)
		{
			{
				Detail::FCase Case(R);
				Case.Real(18, Obs::SeePredRadius(kSnapDark[s]), kSnapSeePred[s]);
				Case.Close(-1 - s);
			}
			Obs::FKinInput Agents[kSnapMaxAgents];
			Obs::FThreatInput Threats[kSnapMaxThreats];
			Obs::FCoverInput Covers[kSnapMaxCovers];
			const std::int32_t A0 = kSnapAgentStart[s];
			const std::int32_t NumAgents = kSnapAgentCount[s];
			const std::int32_t NumThreats = kSnapThreatCount[s];
			const std::int32_t NumCovers = kSnapCoverCount[s];
			for (std::int32_t a = 0; a < NumAgents; ++a)
			{
				const double* V = &kSnapAgent[(A0 + a) * 6];
				Agents[a] = {V[0], V[1], kSnapAgentBehavior[A0 + a]};
			}
			for (std::int32_t m = 0; m < NumThreats; ++m)
			{
				const double* V = &kSnapThreat[(kSnapThreatStart[s] + m) * 4];
				Threats[m] = {V[0], V[1], V[2], V[3], kSnapThreatAsleep[kSnapThreatStart[s] + m] != 0};
			}
			for (std::int32_t k = 0; k < NumCovers; ++k)
			{
				const double* V = &kSnapCover[(kSnapCoverStart[s] + k) * 3];
				Covers[k] = {V[0], V[1], V[2]};
			}
			for (std::int32_t a = 0; a < NumAgents; ++a)
			{
				const std::int32_t Row = A0 + a;
				if (kSnapAgentCheck[Row] == 0)
				{
					++R.Skipped;
					continue;
				}
				const double* V = &kSnapAgent[Row * 6];
				const FVec2 Pos = {V[0], V[1]};
				const FVec2 Head = {V[2], V[3]};
				const Obs::FThreatPerception T =
					Obs::PerceiveThreats(Pos, Head, kSnapSeePred[s], V[4], V[5], Threats, NumThreats);
				const Obs::FKinPerception K = Obs::PerceiveKin(a, Pos, Head, Agents, NumAgents);
				const Obs::FCoverPerception C = Obs::PerceiveCover(Pos, Covers, NumCovers);
				const std::int32_t* WI = &kSnapExpInt[Row * 5];
				const double* WR = &kSnapExpReal[Row * 13];
				Detail::FCase Case(R);
				Case.Int(0, T.PredCount, WI[0]);
				Case.Int(1, T.PredCountEv, WI[1]);
				Case.Int(2, K.KinCount, WI[2]);
				Case.Int(3, C.CoverK, WI[3]);
				Case.Int(4, C.bInCover ? 1 : 0, WI[4]);
				Case.Real(5, T.DPredMin, WR[0]);
				Case.Real(6, T.AwayFromPred.X, WR[1]);
				Case.Real(7, T.AwayFromPred.Y, WR[2]);
				Case.Real(8, T.PredApproach, WR[3]);
				Case.Real(9, T.DPredMinEv, WR[4]);
				Case.Real(10, T.PredApproachEv, WR[5]);
				Case.Real(11, K.ToCentroid.X, WR[6]);
				Case.Real(12, K.ToCentroid.Y, WR[7]);
				Case.Real(13, K.Separation.X, WR[8]);
				Case.Real(14, K.Separation.Y, WR[9]);
				Case.Real(15, K.KinAlarm, WR[10]);
				Case.Real(16, C.CoverDist, WR[11]);
				Case.Real(17, C.Edge, WR[12]);
				Case.Close(Row);
			}
		}
		return R;
	}

	/** 8. 낮밤. 칸: 0 어둠, 1 남은 스텝. */
	inline FReport CheckDayNight()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t n = 0; n < kDayNightCount; ++n)
		{
			const std::int32_t* P = &kDnParam[n * 3];
			const EcoObservationV3::FDayNight D = EcoObservationV3::DayNightPhase(kDnT[n], P[0], P[1], P[2]);
			Detail::FCase Case(R);
			Case.Real(0, D.Dark, kDnDark[n]);
			Case.Int(1, D.StepsToTransition, kDnSteps[n]);
			Case.Close(n);
		}
		return R;
	}

	/** 9. 피식 EMA. 칸: 0 EMA. */
	inline FReport CheckPredationEma()
	{
		using namespace Golden;
		FReport R;
		for (std::int32_t n = 0; n < kEmaCount; ++n)
		{
			Detail::FCase Case(R);
			Case.Real(0, EcoObservationV3::UpdatePredationEma(kEmaBefore[n], kEmaCaught[n], kEmaAgents[n]), kEmaAfter[n]);
			Case.Close(n);
		}
		return R;
	}
}

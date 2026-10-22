// v3 위협 모델 밤잠 점진화 골든 대조 — EcoThreatModel.h (FThreatConfig::bRealismNight = true 의 NightInit·NightUpdate·Step)를
// ThreatNightGoldenVectorsV3.h (herbivore_rl/export_golden_v3_threat.py --night, 세계 configs/v3_real1_night_on.yaml)와 맞춘다.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<vector>` 와 엔진 무관 위협 모델 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoThreatNightV3Test.cpp (AdaptiveEcosystem.Policy.V3.ThreatNight.*)
//   g++ 하네스       herbivore_rl/tests/cpp/threat_night_v3_main.cpp (herbivore_rl/tests/test_threat_golden_v3.py)
// 검사 하나가 FReport 하나를 낸다: 사례 수, 어긋난 사례 수, 실수 최대 오차, 처음 어긋난 사례와 칸.
// 허용: 실수 |C++ − Python| <= GoldenNight::kFloatTolerance, 정수·열거·판정·사건은 정확히 같다.
//
// 칸 번호 (FReport::FirstField):
//   스텝  0 pos, 1 head, 2 vel, 3 speed, 4 target_perceived, 5~9 정수 상태(cooldown, stalk_state, stalk_left, player_mode,
//         player_left), 10 out_bits, 11 target, 12 caught, 13 hook_asleep, 14 night_hunt(스텝 뒤 bNightHunt), 15 daynight
//   업데이트 20~24 뒤 상태(잠, 활동도, 눕는 중, 어둠 경과, 기상 대기), 25 사건 비트, 26 속력 배수, 27 daynight
//   처음 상태 30 지연, 31~35 뒤 상태 / 해시 40 지연 / 설정 50 + 칸

#pragma once

#include <cmath>
#include <cstdint>
#include <vector>

#include "../EcoThreatModel.h"
#include "../ThreatNightGoldenVectorsV3.h"

namespace EcoThreatV3::NightCheck
{
	namespace G = EcoThreatV3::GoldenNight;

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례 (열은 스텝)
		std::int32_t Skipped = 0;      // 문턱 근처로 뺀 사례 (보고만 묶음의 어긋남 수도 여기에 센다)
		std::int32_t Failures = 0;     // 어긋난 사례
		double MaxError = 0.0;         // 실수 칸 최대 |C++ − Python|
		std::int32_t FloatCount = 0;   // 비교한 실수 칸
		std::int32_t FloatExact = 0;   // 그중 비트 단위로 같은 칸
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)

		bool Passed() const { return Failures == 0 && Cases > 0; }
	};

	namespace Detail
	{
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
				if (!(E <= G::kFloatTolerance) && Field < 0)
				{
					Field = Id;
				}
			}

			/** 사례를 닫는다. 어긋났으면 참. bReportOnly 면 어긋남을 실패가 아니라 Skipped 로 센다(문턱 근처 묶음). */
			bool Close(std::int32_t CaseIndex, bool bReportOnly = false)
			{
				++R.Cases;
				if (Field < 0)
				{
					return false;
				}
				if (bReportOnly)
				{
					++R.Skipped;
					return true;
				}
				if (R.Failures == 0)
				{
					R.FirstCase = CaseIndex;
					R.FirstField = Field;
				}
				++R.Failures;
				return true;
			}
		};

		/** 밤잠 점진화를 켠 설정 (나머지는 기본값 = 학습 세계). */
		inline FThreatConfig NightConfig()
		{
			FThreatConfig Cfg;
			Cfg.bRealismNight = true;
			return Cfg;
		}

		// ---- 스텝 사례 ----

		struct FStepCase
		{
			FThreatSpec Spec;
			FThreatState State;
			std::vector<FPreyView> Prey;
			std::vector<double> Roll;
			FThreatStepInput In;
		};

		inline FThreatSpec SpecOf(std::int32_t n)
		{
			FThreatSpec S;
			S.Type = static_cast<EThreatType>(G::kSpecType[n]);
			S.bRanged = G::kSpecRanged[n] != 0;
			S.bNocturnal = G::kSpecNocturnal[n] != 0;
			S.BaseSpeed = G::kSpecBaseSpeed[n];
			S.CatchRadius = G::kSpecCatchR[n];
			return S;
		}

		/** 스텝 소유 칸 (위치·heading·정수 상태·지난 사냥 중). */
		inline void LoadStepOwned(std::int32_t n, FThreatState& T)
		{
			T.PosX = G::kPrePos[n * 2];
			T.PosY = G::kPrePos[n * 2 + 1];
			T.HeadX = G::kPreHead[n * 2];
			T.HeadY = G::kPreHead[n * 2 + 1];
			T.Cooldown = G::kPreInt[n * 5];
			T.StalkState = static_cast<EStalkState>(G::kPreInt[n * 5 + 1]);
			T.StalkLeft = G::kPreInt[n * 5 + 2];
			T.PlayerMode = static_cast<EPlayerMode>(G::kPreInt[n * 5 + 3]);
			T.PlayerLeft = G::kPreInt[n * 5 + 4];
			T.bNightHunt = G::kCaseNightPre[n * 3 + 2] != 0;
		}

		/** 밤잠 업데이트 소유 칸 가운데 Step 이 읽는 것 (잠·활동도). */
		inline void LoadNightOwned(std::int32_t n, FThreatState& T)
		{
			T.bAsleep = G::kCaseNightPre[n * 3] != 0;
			T.NightAct = G::kCaseNightPre[n * 3 + 1];
		}

		inline void BuildStep(std::int32_t n, FStepCase& C)
		{
			C.Spec = SpecOf(n);
			C.State = FThreatState();
			LoadStepOwned(n, C.State);
			LoadNightOwned(n, C.State);
			C.Prey.clear();
			C.Roll.clear();
			for (std::int32_t k = 0; k < G::kPreyCount[n]; ++k)
			{
				const std::int32_t p = G::kPreyBegin[n] + k;
				FPreyView P;
				P.X = G::kPreyPos[p * 2];
				P.Y = G::kPreyPos[p * 2 + 1];
				P.Behavior = G::kPreyBehavior[p];
				P.bHideArrived = G::kPreyHideArrived[p] != 0;
				P.bInCover = G::kPreyInCover[p] != 0;
				P.bAlive = true;
				C.Prey.push_back(P);
				C.Roll.push_back(G::kPreyRoll[p]);
			}
			C.In = FThreatStepInput();
			C.In.Prey = C.Prey.empty() ? nullptr : C.Prey.data();
			C.In.NumPrey = static_cast<std::int32_t>(C.Prey.size());
			C.In.RangedRoll = C.Spec.bRanged ? C.Roll.data() : nullptr;
			C.In.Dark = G::kDark[n];
			C.In.WorldSize = G::kWorldSize[n];
			C.In.WanderTurn = G::kTurn[n];
			C.In.PlayerModeU0 = G::kModeU[n * 2];
			C.In.PlayerModeU1 = G::kModeU[n * 2 + 1];
		}

		inline void CompareStep(FCase& K, std::int32_t n, const FThreatState& T, const FThreatStepResult& R)
		{
			K.Real(0, T.PosX, G::kPostPos[n * 2]);
			K.Real(0, T.PosY, G::kPostPos[n * 2 + 1]);
			K.Real(1, T.HeadX, G::kPostHead[n * 2]);
			K.Real(1, T.HeadY, G::kPostHead[n * 2 + 1]);
			K.Real(2, T.VelX, G::kPostVel[n * 2]);
			K.Real(2, T.VelY, G::kPostVel[n * 2 + 1]);
			K.Real(3, R.Speed, G::kOutSpeed[n]);
			K.Real(4, R.TargetPerceived, G::kOutTargetPerceived[n]);
			const std::int64_t Ints[5] = {T.Cooldown, static_cast<std::int64_t>(T.StalkState), T.StalkLeft,
										  static_cast<std::int64_t>(T.PlayerMode), T.PlayerLeft};
			for (std::int32_t k = 0; k < 5; ++k)
			{
				K.Int(5 + k, Ints[k], G::kPostInt[n * 5 + k]);
			}
			const std::uint8_t Bits = static_cast<std::uint8_t>(
				(R.bAsleep ? G::kOutAsleep : 0) | (R.bHunting ? G::kOutHunting : 0) | (R.bHasTarget ? G::kOutHasTarget : 0) |
				(R.bWallHit ? G::kOutWall : 0) | (R.bPounceStart ? G::kOutPounceStart : 0) |
				(R.bChargeStart ? G::kOutChargeStart : 0) | (R.bNewPlayerMode ? G::kOutNewMode : 0));
			K.Int(10, Bits, G::kOutBits[n]);
			K.Int(11, R.Target, G::kOutTarget[n]);
			K.Int(11, T.Target, G::kOutTarget[n]);
			K.Int(12, R.Caught, G::kOutCaught[n]);
			K.Int(13, T.bAsleep ? 1 : 0, R.bAsleep ? 1 : 0);
			K.Int(14, T.bNightHunt ? 1 : 0, G::kCaseNightPostHunt[n]);
		}

		// ---- 업데이트 사례 ----

		struct FUpdCase
		{
			FThreatSpec Spec;
			FThreatState State;
			std::vector<FPreyView> Prey;
		};

		/** 업데이트 소유 칸 전부 + 지난 사냥 중 + 늑대 위치. */
		inline void LoadUpdPre(std::int32_t u, FThreatState& T)
		{
			T.bAsleep = G::kUpdPreInt[u * 6] != 0;
			T.NightAct = G::kUpdPreInt[u * 6 + 1];
			T.bNightSettle = G::kUpdPreInt[u * 6 + 2] != 0;
			T.NightDarkK = G::kUpdPreInt[u * 6 + 3];
			T.NightWait = G::kUpdPreInt[u * 6 + 4];
			T.bNightHunt = G::kUpdPreInt[u * 6 + 5] != 0;
			T.NightDelay = G::kUpdDelay[u];
		}

		inline void BuildUpdPrey(std::int32_t u, std::vector<FPreyView>& Prey)
		{
			Prey.clear();
			for (std::int32_t k = 0; k < G::kUpdPreyCount[u]; ++k)
			{
				const std::int32_t p = G::kUpdPreyBegin[u] + k;
				FPreyView P;
				P.X = G::kUpdPreyPos[p * 2];
				P.Y = G::kUpdPreyPos[p * 2 + 1];
				P.bAlive = true;
				Prey.push_back(P);
			}
		}

		inline void BuildUpd(std::int32_t u, FUpdCase& C)
		{
			C.Spec = FThreatSpec();
			C.Spec.bNocturnal = G::kUpdNocturnal[u] != 0;
			C.State = FThreatState();
			LoadUpdPre(u, C.State);
			C.State.PosX = G::kUpdWolfPos[u * 2];
			C.State.PosY = G::kUpdWolfPos[u * 2 + 1];
			BuildUpdPrey(u, C.Prey);
		}

		inline std::uint8_t EventBits(const FNightUpdateResult& R)
		{
			return static_cast<std::uint8_t>((R.bWake ? G::kEvWake : 0) | (R.bSettleStart ? G::kEvSettleStart : 0) |
											 (R.bSettleAbort ? G::kEvSettleAbort : 0) | (R.bOnset ? G::kEvOnset : 0) |
											 (R.bBlockDeer ? G::kEvBlockDeer : 0) | (R.bBlockHunt ? G::kEvBlockHunt : 0) |
											 (R.bNearChecked ? G::kEvNearChecked : 0) | (R.bNear ? G::kEvNear : 0));
		}

		inline void CompareUpd(FCase& K, std::int32_t u, const FThreatSpec& Spec, const FThreatState& T,
							   const FNightUpdateResult& R, const FThreatConfig& Cfg)
		{
			K.Int(20, T.bAsleep ? 1 : 0, G::kUpdPostInt[u * 5]);
			K.Int(21, T.NightAct, G::kUpdPostInt[u * 5 + 1]);
			K.Int(22, T.bNightSettle ? 1 : 0, G::kUpdPostInt[u * 5 + 2]);
			K.Int(23, T.NightDarkK, G::kUpdPostInt[u * 5 + 3]);
			K.Int(24, T.NightWait, G::kUpdPostInt[u * 5 + 4]);
			K.Int(25, EventBits(R), G::kUpdEvents[u]);
			K.Real(26, NightSpeedMult(Spec, T, G::kUpdDark[u], Cfg), G::kUpdSpeedMult[u]);
			K.Real(27, DayNightDark(G::kUpdClock[u * 4], G::kUpdClock[u * 4 + 1], G::kUpdClock[u * 4 + 2], G::kUpdClock[u * 4 + 3]),
				   G::kUpdDark[u]);
		}
	}

	/** 설정: FThreatConfig 기본값의 밤잠 칸 = 파이썬 realism_night 블록 (정확히), 켜는 칸 기본은 끔, 나머지 칸 = 학습 세계. */
	inline FReport CheckConfig()
	{
		FReport R;
		Detail::FCase K(R);
		const FThreatConfig Cfg;
		K.Int(50, Cfg.bRealismNight ? 1 : 0, 0);
		K.Real(51, Cfg.NightSettleR, G::kCfgNightSettleR);
		K.Real(52, Cfg.NightHuntDark, G::kCfgNightHuntDark);
		K.Real(53, Cfg.NightFloor, G::kCfgNightFloor);
		K.Real(54, Cfg.NightSpread, G::kCfgNightSpread);
		K.Int(55, Cfg.NightRampSteps, G::kCfgNightRampSteps);
		K.Int(56, Cfg.NightSettleR == G::kCfgNightSettleR && Cfg.NightHuntDark == G::kCfgNightHuntDark
					  && Cfg.NightFloor == G::kCfgNightFloor && Cfg.NightSpread == G::kCfgNightSpread ? 1 : 0, 1);
		K.Real(57, Cfg.SleepDark, G::kCfgSleepDark);
		K.Int(58, Cfg.bTwilightSlow ? 1 : 0, G::kCfgTwilightSlow ? 1 : 0);
		K.Real(59, Cfg.HerbSpeed, G::kCfgHerbSpeed);
		K.Real(60, Cfg.PredViewR, G::kCfgPredViewR);
		K.Real(61, Cfg.PredFovCos, G::kCfgPredFovCos);
		K.Int(62, Cfg.PredEatCd, G::kCfgPredEatCd);
		K.Real(63, Cfg.CStill, G::kCfgCStill);
		K.Real(64, Cfg.StalkDist, G::kCfgStalkDist);
		K.Int(65, Cfg.PounceSteps, G::kCfgPounceSteps);
		K.Int(66, Cfg.ExhaustSteps, G::kCfgExhaustSteps);
		K.Int(67, Cfg.PlayerCooldown, G::kCfgPlayerCooldown);
		// 정확히 같아야 한다 (허용 오차가 아니라 비트)
		K.Int(68, Cfg.SleepDark == G::kCfgSleepDark && Cfg.HerbSpeed == G::kCfgHerbSpeed && Cfg.PredFovCos == G::kCfgPredFovCos ? 1 : 0, 1);
		K.Close(0);
		return R;
	}

	/** 지연 해시: NightDelayOf(시드, 슬롯, 최대) = 파이썬 night_delays. */
	inline FReport CheckHash()
	{
		FReport R;
		for (std::int32_t h = 0; h < G::kHashCount; ++h)
		{
			Detail::FCase K(R);
			K.Int(40, NightDelayOf(G::kHashSeed[h], G::kHashSlot[h], G::kHashMaxDelay[h]), G::kHashDelay[h]);
			K.Close(h);
		}
		return R;
	}

	/** 처음 상태 (세계 생성): 지연 = NightDelayOf(시드, 슬롯, NightMaxDelay(τ)), NightInit 뒤 상태 = 파이썬 reset 뒤 상태. */
	inline FReport CheckInit()
	{
		FReport R;
		const FThreatConfig Cfg = Detail::NightConfig();
		for (std::int32_t i = 0; i < G::kInitCount; ++i)
		{
			Detail::FCase K(R);
			const std::int32_t Delay = NightDelayOf(G::kInitSeed[i], G::kInitSlot[i], NightMaxDelay(G::kInitTw[i], Cfg));
			K.Int(30, Delay, G::kInitDelay[i]);
			FThreatSpec Spec;
			Spec.bNocturnal = G::kInitNocturnal[i] != 0;
			FThreatState T;
			NightInit(Spec, T, G::kInitDark[i], Delay, Cfg);
			K.Int(31, T.bAsleep ? 1 : 0, G::kInitPostInt[i * 5]);
			K.Int(32, T.NightAct, G::kInitPostInt[i * 5 + 1]);
			K.Int(33, T.bNightSettle ? 1 : 0, G::kInitPostInt[i * 5 + 2]);
			K.Int(34, T.NightDarkK, G::kInitPostInt[i * 5 + 3]);
			K.Int(35, T.NightWait, G::kInitPostInt[i * 5 + 4]);
			K.Close(i);
		}
		return R;
	}

	/** 업데이트 사례 한 종류 (kKindMain·kKindEdge·kKindNear·kKindLife — 생애 열 업데이트도 하나씩 따로). 문턱 근처는 보고만. */
	inline FReport CheckUpdates(std::uint8_t Kind)
	{
		FReport R;
		const FThreatConfig Cfg = Detail::NightConfig();
		for (std::int32_t u = 0; u < G::kUpdCount; ++u)
		{
			if (G::kUpdKind[u] != Kind)
			{
				continue;
			}
			Detail::FUpdCase C;
			Detail::BuildUpd(u, C);
			const FNightUpdateResult Res =
				NightUpdate(C.Spec, C.State, G::kUpdDark[u], C.Prey.empty() ? nullptr : C.Prey.data(), static_cast<std::int32_t>(C.Prey.size()), Cfg);
			Detail::FCase K(R);
			Detail::CompareUpd(K, u, C.Spec, C.State, Res, Cfg);
			K.Close(u, Kind == G::kKindNear);
		}
		return R;
	}

	/** 스텝 사례 한 종류 (밤잠 상태는 사례마다 골든 값). 문턱 근처는 보고만. */
	inline FReport CheckSteps(std::uint8_t Kind)
	{
		FReport R;
		const FThreatConfig Cfg = Detail::NightConfig();
		for (std::int32_t n = 0; n < G::kNightCaseCount; ++n)
		{
			if (G::kCaseKind[n] != Kind)
			{
				continue;
			}
			Detail::FStepCase C;
			Detail::BuildStep(n, C);
			const FThreatStepResult Res = Step(C.Spec, C.State, C.In, Cfg);
			Detail::FCase K(R);
			Detail::CompareStep(K, n, C.State, Res);
			K.Real(15, DayNightDark(G::kClock[n * 4], G::kClock[n * 4 + 1], G::kClock[n * 4 + 2], G::kClock[n * 4 + 3]), G::kDark[n]);
			K.Close(n, Kind == G::kKindNear);
		}
		return R;
	}

	/**
	 * 롤아웃 스텝 열: 첫 스텝만 골든 상태, 그 뒤는 C++ 자기 출력의 스텝 소유 칸(위치·heading·정수 상태·bNightHunt)을 이어 쓴다.
	 * 밤잠 업데이트 소유 칸(잠·활동도)은 스텝마다 골든 값이다 (스텝 사이의 NightUpdate 는 생애 열이 본다).
	 */
	inline FReport CheckStepSequences()
	{
		FReport R;
		const FThreatConfig Cfg = Detail::NightConfig();
		for (std::int32_t s = 0; s < G::kSeqCount; ++s)
		{
			FThreatState Carry;
			for (std::int32_t k = 0; k < G::kSeqLength[s]; ++k)
			{
				const std::int32_t n = G::kSeqBegin[s] + k;
				Detail::FStepCase C;
				Detail::BuildStep(n, C);
				if (k > 0)
				{
					const FThreatState GoldState = C.State;
					C.State = Carry;
					C.State.bAsleep = GoldState.bAsleep;
					C.State.NightAct = GoldState.NightAct;
				}
				const FThreatStepResult Res = Step(C.Spec, C.State, C.In, Cfg);
				Detail::FCase K(R);
				Detail::CompareStep(K, n, C.State, Res);
				K.Close(n);
				Carry = C.State;
			}
		}
		return R;
	}

	/**
	 * 생애 열: 한 늑대를 이어진 세계 스텝 동안 Step(스텝 사례 골든 사슴) → NightUpdate(업데이트 사례 골든 사슴) 를 번갈아 부른다.
	 * 첫 스텝만 골든 상태(스텝 소유 칸 + 잠·활동도는 스텝 사례, 눕는 중·어둠 경과·기상 대기·지연은 같은 세계 스텝의 업데이트 사례)이고,
	 * 그 뒤는 C++ 자기 출력 상태를 그대로 이어 쓴다. 비교: 스텝마다 스텝 결과, 업데이트마다 업데이트 결과 (사례 = 세계 스텝 하나).
	 */
	inline FReport CheckLife(std::int32_t* OutOnsets = nullptr, std::int32_t* OutWakes = nullptr)
	{
		FReport R;
		std::int32_t Onsets = 0;
		std::int32_t Wakes = 0;
		const FThreatConfig Cfg = Detail::NightConfig();
		for (std::int32_t l = 0; l < G::kLifeCount; ++l)
		{
			FThreatState Carry;
			for (std::int32_t k = 0; k < G::kLifeLength[l]; ++k)
			{
				const std::int32_t n = G::kLifeStepBegin[l] + k;
				const std::int32_t u = G::kLifeUpdBegin[l] + k;
				Detail::FStepCase C;
				Detail::BuildStep(n, C);
				if (k == 0)
				{
					Detail::LoadUpdPre(u, C.State);   // 눕는 중·어둠 경과·기상 대기·지연 (잠·활동도·사냥 중은 같은 값이다)
					Detail::LoadNightOwned(n, C.State);
					C.State.bNightHunt = G::kCaseNightPre[n * 3 + 2] != 0;
				}
				else
				{
					C.State = Carry;
				}
				const FThreatStepResult Res = Step(C.Spec, C.State, C.In, Cfg);
				Detail::FCase K(R);
				Detail::CompareStep(K, n, C.State, Res);
				std::vector<FPreyView> Deer;
				Detail::BuildUpdPrey(u, Deer);
				const FNightUpdateResult Nr =
					NightUpdate(C.Spec, C.State, G::kUpdDark[u], Deer.empty() ? nullptr : Deer.data(), static_cast<std::int32_t>(Deer.size()), Cfg);
				Detail::CompareUpd(K, u, C.Spec, C.State, Nr, Cfg);
				K.Close(n);
				Onsets += Nr.bOnset ? 1 : 0;
				Wakes += Nr.bWake ? 1 : 0;
				Carry = C.State;
			}
		}
		if (OutOnsets)
		{
			*OutOnsets = Onsets;
		}
		if (OutWakes)
		{
			*OutWakes = Wakes;
		}
		return R;
	}

	/**
	 * 끈 판이 켠 판과 섞이지 않는다: 밤잠 점진화를 끄면(기본 설정) Step 은 밤잠 칸을 읽지도 쓰지도 않는다 — 같은 입력에 밤잠 칸만
	 * 다르게 넣어도 결과·상태가 같고, bNightHunt 를 바꾸지 않는다. 본 스텝 사례마다 확인한다.
	 */
	inline FReport CheckOffIgnoresNightState()
	{
		FReport R;
		const FThreatConfig Off;
		for (std::int32_t n = 0; n < G::kNightCaseCount; ++n)
		{
			if (G::kCaseKind[n] != G::kKindMain)
			{
				continue;
			}
			Detail::FStepCase A;
			Detail::FStepCase B;
			Detail::BuildStep(n, A);
			Detail::BuildStep(n, B);
			A.State.bAsleep = false;
			A.State.NightAct = 0;
			A.State.bNightHunt = false;
			B.State.bAsleep = true;
			B.State.NightAct = 7;
			B.State.bNightHunt = true;
			const FThreatStepResult RA = Step(A.Spec, A.State, A.In, Off);
			const FThreatStepResult RB = Step(B.Spec, B.State, B.In, Off);
			Detail::FCase K(R);
			K.Int(0, A.State.PosX == B.State.PosX && A.State.PosY == B.State.PosY && A.State.HeadX == B.State.HeadX
						 && A.State.HeadY == B.State.HeadY ? 1 : 0, 1);
			K.Int(3, RA.Speed == RB.Speed ? 1 : 0, 1);
			K.Int(10, RA.bAsleep == RB.bAsleep && RA.bHunting == RB.bHunting && RA.bHasTarget == RB.bHasTarget ? 1 : 0, 1);
			K.Int(12, RA.Caught, RB.Caught);
			K.Int(14, (A.State.bNightHunt ? 0 : 1) + (B.State.bNightHunt ? 1 : 0), 2);
			K.Int(13, RA.bAsleep ? 1 : 0, IsAsleep(A.Spec, A.In.Dark, Off) ? 1 : 0);
			K.Close(n);
		}
		return R;
	}
}

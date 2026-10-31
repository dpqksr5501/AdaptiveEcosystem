// v3 숲 시야 골든 대조 — EcoThreatModel.h (FoliageChord·FoliageBlocked·Step 의 표적 가림), EcoObservationV3.h (ObstacleObsValues 의 threat_hidden),
// EcoWorldV3.h (FObstacleConfig::Foliage — 사슴 위협 보임·도주 반사 알아챔·감지 기록, FlightPairOf·FlightUpdate 의 lost_foliage, 단계 함수 전체)를
// FoliageGoldenVectorsV3.h (herbivore_rl/export_golden_v3_foliage.py, 세계 configs/v3_wild3_obs_mirror.yaml + 숲 시야)와 맞춘다.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<cstring>`·`<vector>` 와 엔진 무관 v3 세계 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoFoliageV3Test.cpp (AdaptiveEcosystem.Policy.V3.Foliage.*)
//   g++ 하네스       herbivore_rl/tests/cpp/foliage_v3_main.cpp (herbivore_rl/tests/test_foliage_golden_v3.py)
// 모든 실수 칸은 파이썬과 같은 식·같은 순서라 비트 단위로 같아야 한다 (==, 지문은 sha256).
//
// 칸 번호 (FReport::FirstField):
//   정의      0 기본값 (r·block·끔)
//   눈길 길이 10 a → b 길이, 11 b → a 길이, 12 가림, 13 끔 = 0 (나무 없음)
//   관측      20 E, 21 N, 22 가림 (숲 시야 켬), 23 가림 (끔 = 줄기만)
//   쌍 장면   30 사냥 가능, 31 표적, 32 반경 안, 33 반경과 시야각 안, 34 가림, 35 은신처 표적 제외, 36 잎만 가림, 37 설정 상수
//   도망 기록 40 늑대 지난 표적(앞), 41~92 보고 (41 + 칸), 93~100 사슴 칸 (_fl_len·contact·reflex·chased·why·end_now·end_cov·why_fol), 101 늑대 지난 표적(뒤)
//   기준 루프 110 시작 상태 (먹이 격자·시작 에너지·늑대 속력), 111 지문, 112 기록 (잡힘·굶음·산·보고), 113 세계 난수 (뽑은 수 = 날 수열 끝)

#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>

#include "../EcoObservationV3.h"
#include "../EcoSha256.h"
#include "../EcoThreatModel.h"
#include "../EcoWorldV3.h"
#include "../FoliageGoldenVectorsV3.h"

namespace EcoWorldV3::FoliageCheck
{
	namespace G = EcoWorldV3::GoldenFoliage;
	namespace T3 = EcoThreatV3;
	namespace R3 = EcoRepertoireV3;

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례
		std::int32_t Failures = 0;     // 어긋난 사례
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)
		std::int64_t Count0 = 0;       // 묶음마다 C++ 이 낸 수: 눈길 = 가림 사례, 관측 = 잎만 가림, 쌍 = 잎만 가린 쌍, 도망 = 끝 lost_foliage 수, 루프 = 잎 놓침
		std::int64_t Count1 = 0;       // 눈길 = 잎 구간이 쌓아 두기 칸을 넘은 사례, 관측 = 가림, 쌍 = 표적 있는 늑대, 도망 = 원판 놓침, 루프 = 잡힘
		std::int64_t Count2 = 0;       // 눈길 = 손 사례 수, 관측 = 줄기 가림, 쌍 = 가린 쌍, 도망 = 시작 도망, 루프 = 시작 도망

		bool Passed() const { return Failures == 0 && Cases > 0; }
	};

	namespace Detail
	{
		struct FCase
		{
			std::int32_t Field = -1;

			void Int(std::int32_t Id, std::int64_t Got, std::int64_t Want)
			{
				if (Got != Want && Field < 0)
				{
					Field = Id;
				}
			}

			void Ok(std::int32_t Id, bool bOk)
			{
				if (!bOk && Field < 0)
				{
					Field = Id;
				}
			}

			/** double 비트 같음 (−0 과 +0 도 가른다). */
			void Bits(std::int32_t Id, double Got, double Want)
			{
				Ok(Id, std::memcmp(&Got, &Want, sizeof(double)) == 0);
			}
		};

		inline void Close(FReport& R, std::int32_t CaseId, const FCase& C)
		{
			++R.Cases;
			if (C.Field >= 0)
			{
				++R.Failures;
				if (R.FirstCase < 0)
				{
					R.FirstCase = CaseId;
					R.FirstField = C.Field;
				}
			}
		}

		inline const double* SetDiscs(std::int32_t Set) { return G::kSetDiscs + 3 * G::kSetStart[Set]; }
		inline const std::uint8_t* SetTrees(std::int32_t Set) { return G::kSetTrees + G::kSetStart[Set]; }
	}

	/** 정의: C++ 기본값(끔·r·block) = 파이썬 features.OPTIONAL_KEYS obstacles.foliage, 끈 설정은 숲 시야를 재지 않는다. */
	inline FReport CheckDefinitions()
	{
		FReport R;
		Detail::FCase C;
		const FFoliageConfig F;
		C.Ok(0, !F.bEnabled && F.R == G::kDefaultR && F.Block == G::kDefaultBlock && F.Trees.empty());
		FObstacleConfig O;
		O.bEnabled = true;
		O.Discs = {1.0, 1.0, 0.1};
		C.Ok(0, !O.FoliageConfigured() && !O.FoliageOn() && O.FoliageTrees() == nullptr);
		O.Foliage.bEnabled = true;
		C.Ok(0, O.FoliageConfigured() && O.FoliageOn());
		O.bBlockSight = false;   // 원판이 눈길을 가리지 않는 세계에는 잎도 없다 (파이썬은 받지 않는다)
		C.Ok(0, !O.FoliageConfigured() && !O.FoliageOn());
		O.bBlockSight = true;
		O.Foliage.Trees = {1, 0};   // 나무 표 길이 ≠ 원판 수 → 재지 않는다 (파이썬은 멈춘다)
		C.Ok(0, O.FoliageConfigured() && !O.FoliageOn());
		C.Ok(0, !FWorldConfig().Obstacles.Foliage.bEnabled);
		Detail::Close(R, 0, C);
		return R;
	}

	/** 눈길 길이: 사례마다 FoliageChord(a → b)·(b → a) = 파이썬 foliage_chord (비트), FoliageBlocked = 가림. 사례 = 눈길. */
	inline FReport CheckChord()
	{
		FReport R;
		for (std::int32_t c = 0; c < G::kChordCount; ++c)
		{
			const std::int32_t S = G::kChordSet[c];
			const double* In = G::kChordIn + 6 * c;
			const double* D = Detail::SetDiscs(S);
			const std::int32_t K = G::kSetNum[S];
			const std::uint8_t* Tr = G::kChordMasked[c] != 0 ? Detail::SetTrees(S) : nullptr;
			Detail::FCase C;
			const double Ab = T3::FoliageChord(In[0], In[1], In[2], In[3], D, K, Tr, In[4]);
			const double Ba = T3::FoliageChord(In[2], In[3], In[0], In[1], D, K, Tr, In[4]);
			C.Bits(10, Ab, G::kChordWant[c]);
			C.Bits(11, Ba, G::kChordWant[c]);
			const bool bBlk = T3::FoliageBlocked(In[0], In[1], In[2], In[3], D, K, Tr, In[4], In[5]);
			C.Int(12, bBlk ? 1 : 0, G::kChordBlocked[c]);
			// 나무가 하나도 없으면 0 (모든 원판을 바위로)
			const std::vector<std::uint8_t> NoTree(static_cast<size_t>(K), 0);
			C.Bits(13, T3::FoliageChord(In[0], In[1], In[2], In[3], D, K, NoTree.data(), In[4]), 0.0);
			R.Count0 += bBlk ? 1 : 0;
			R.Count1 += G::kChordSpans[c] > T3::kFoliageSpanCap ? 1 : 0;
			Detail::Close(R, c, C);
		}
		R.Count2 = G::kChordHand;
		return R;
	}

	/** 관측 threat_hidden: 거울 숲 원판·나무 표로 ObstacleObsValues (숲 시야 켬·끔) = 파이썬 obstacle_obs_values (E·N 비트, 가림). 사례 = 사슴. */
	inline FReport CheckObs()
	{
		FReport R;
		const std::int32_t S = 1;
		for (std::int32_t i = 0; i < G::kObsCount; ++i)
		{
			const double* In = G::kObsIn + 8 * i;
			EcoObservationV3::FObstacleObsInput Oi;
			Oi.Pos = {In[0], In[1]};
			Oi.Head = {In[2], In[3]};
			Oi.Away = {In[4], In[5]};
			Oi.Threat = {In[6], In[7]};
			Oi.bSeen = G::kObsSeen[i] != 0;
			Oi.Discs = Detail::SetDiscs(S);
			Oi.NumDiscs = G::kSetNum[S];
			Oi.BodyR = G::kObsBodyR;
			Oi.StageSize = G::kObsStageSize;
			Oi.bBlockSight = true;
			Oi.bFoliage = true;
			Oi.FoliageTrees = Detail::SetTrees(S);
			Oi.FoliageR = G::kDefaultR;
			Oi.FoliageBlock = G::kDefaultBlock;
			const EcoObservationV3::FObstacleObs On = EcoObservationV3::ObstacleObsValues(Oi);
			Oi.bFoliage = false;
			const EcoObservationV3::FObstacleObs Off = EcoObservationV3::ObstacleObsValues(Oi);
			Detail::FCase C;
			C.Bits(20, On.Escape, G::kObsWantE[i]);
			C.Bits(21, On.Near, G::kObsWantN[i]);
			C.Int(22, On.bThreatHidden ? 1 : 0, G::kObsWantHidden[i]);
			C.Int(23, Off.bThreatHidden ? 1 : 0, G::kObsTrunkHidden[i]);
			C.Bits(20, Off.Escape, On.Escape);
			C.Bits(21, Off.Near, On.Near);
			R.Count0 += (On.bThreatHidden && !Off.bThreatHidden) ? 1 : 0;
			R.Count1 += On.bThreatHidden ? 1 : 0;
			R.Count2 += Off.bThreatHidden ? 1 : 0;
			Detail::Close(R, i, C);
		}
		return R;
	}

	/**
	 * 쌍 장면: 같은 이동 전 상태·입력(숲 시야 켬)으로 위협 Step 사본의 사냥 가능·표적 = 파이썬 pred_target, FlightPairOf(모든 늑대 × 사슴) = 파이썬 `_fl_pred`·
	 * `_fl_pred_fol`. 설정은 export_golden_v3_flight.py 쌍 장면과 같다 (은신처 안전·포만·식사 제자리·밤잠 상태). 사례 = 장면.
	 */
	inline FReport CheckPairs()
	{
		FReport R;
		T3::FThreatConfig Cfg;
		Cfg.PredEatCd = G::kPairEatCd;
		Cfg.bEatInPlace = true;
		Cfg.bWildSatiation = true;
		Cfg.SatSteps = G::kPairSatSteps;
		Cfg.bShelterSafe = true;
		Cfg.bShelterBlock = true;
		Cfg.bRealismNight = true;
		const std::int32_t M = G::kPairWolves;
		const std::int32_t N = G::kPairPrey;
		{
			Detail::FCase C;
			C.Ok(37, Cfg.PredViewR == G::kPairViewR && Cfg.PredFovCos == G::kPairFovCos && Cfg.CStill == G::kPairCStill);
			C.Ok(37, Cfg.CoverMultCrouch == G::kPairCoverMult[0] && Cfg.CoverMultGraze == G::kPairCoverMult[1] && Cfg.CoverMultSleep == G::kPairCoverMult[2]
						 && Cfg.CoverMultOther == G::kPairCoverMult[3]);
			Detail::Close(R, -1, C);
		}
		std::vector<T3::FThreatSpec> Specs;
		for (std::int32_t m = 0; m < M; ++m)
		{
			Specs.push_back(G::kPairStalker[m] != 0 ? T3::MakeStalkerSpec(G::kPairPredSpeedMult, false, Cfg)
													: T3::MakeChaserSpec(G::kPairPredSpeedMult, false, false, Cfg));
		}
		std::vector<T3::FPreyView> Prey(static_cast<size_t>(N));
		for (std::int32_t s = 0; s < G::kPairScenes; ++s)
		{
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Pd = G::kPairPreyIn + 2 * (s * N + i);
				const std::int32_t* Pin = G::kPairPreyInI + 3 * (s * N + i);
				T3::FPreyView& V = Prey[static_cast<size_t>(i)];
				V = T3::FPreyView();
				V.X = Pd[0];
				V.Y = Pd[1];
				V.Behavior = static_cast<std::uint8_t>(Pin[0]);
				V.bHideArrived = Pin[1] != 0;
				V.bInCover = Pin[2] != 0;
			}
			T3::FThreatStepInput In;
			In.Prey = Prey.data();
			In.NumPrey = N;
			In.Dark = 0.0;
			In.WorldSize = G::kPairWorldSize;
			In.Obstacles = Detail::SetDiscs(1);
			In.NumObstacles = G::kSetNum[1];
			In.ObstacleBody = G::kPairBody;
			In.bObstacleSight = true;
			In.bFoliage = true;
			In.FoliageTrees = Detail::SetTrees(1);
			In.FoliageR = G::kDefaultR;
			In.FoliageBlock = G::kDefaultBlock;
			In.WeatherViewMult = G::kPairSight[s];
			Detail::FCase C;
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wd = G::kPairWolfIn + 4 * (s * M + m);
				const std::int32_t* Wi = G::kPairWolfInI + 5 * (s * M + m);
				T3::FThreatState T;
				T.PosX = Wd[0];
				T.PosY = Wd[1];
				T.HeadX = Wd[2];
				T.HeadY = Wd[3];
				T.Cooldown = Wi[0];
				T.SatLeft = Wi[1];
				T.StalkState = static_cast<T3::EStalkState>(Wi[2]);
				T.StalkLeft = Wi[3];
				T.bAsleep = Wi[4] != 0;
				T.NightAct = T.bAsleep ? 0 : Cfg.NightRampSteps;
				T3::FThreatState Copy = T;
				const T3::FThreatStepResult Res = T3::Step(Specs[static_cast<size_t>(m)], Copy, In, Cfg);
				C.Int(30, Res.bHunting ? 1 : 0, G::kPairHunt[s * M + m]);
				C.Int(31, Res.bHasTarget ? Res.Target : -1, G::kPairTarget[s * M + m]);
				R.Count1 += Res.bHasTarget ? 1 : 0;
				for (std::int32_t i = 0; i < N; ++i)
				{
					const FFlightPair Pr = FlightPairOf(T, Prey[static_cast<size_t>(i)], In, Cfg);
					const std::uint8_t Want = G::kPairFlags[(s * M + m) * N + i];
					C.Int(32, Pr.bRange ? 1 : 0, Want & 1);
					C.Int(33, Pr.bVis0 ? 1 : 0, (Want >> 1) & 1);
					C.Int(34, Pr.bBlocked ? 1 : 0, (Want >> 2) & 1);
					C.Int(35, Pr.bCover ? 1 : 0, (Want >> 3) & 1);
					C.Int(36, Pr.bFolOnly ? 1 : 0, (Want >> 4) & 1);
					R.Count0 += Pr.bFolOnly ? 1 : 0;
					R.Count2 += Pr.bBlocked ? 1 : 0;
				}
			}
			Detail::Close(R, s, C);
		}
		return R;
	}

	namespace Detail
	{
		inline FFlightDeerStep DeerOf(std::uint8_t Bits)
		{
			FFlightDeerStep D;
			D.bFlee = (Bits & 1) != 0;
			D.bReflex = (Bits & 2) != 0;
			D.bDone = (Bits & 4) != 0;
			D.bCaught = (Bits & 8) != 0;
			D.bInCov = (Bits & 16) != 0;
			D.bAlive0 = (Bits & 32) != 0;
			return D;
		}

		inline FFlightWolfStep WolfOf(std::uint8_t Bits, std::int32_t Target)
		{
			FFlightWolfStep Wf;
			Wf.Target = Target;
			Wf.bHuntEnd = (Bits & 1) != 0;
			Wf.bHuntSel = (Bits & 2) != 0;
			Wf.bPair = (Bits & 4) != 0;
			Wf.bRange = (Bits & 8) != 0;
			Wf.bVis0 = (Bits & 16) != 0;
			Wf.bBlocked = (Bits & 32) != 0;
			Wf.bCover = (Bits & 64) != 0;
			Wf.bFolOnly = (Bits & 128) != 0;
			return Wf;
		}

		/** 보고를 골든 52 칸 순서로 (도망 골든 49 칸 + lost_foliage n·steps·contact). */
		inline void Row(const FFlightReport& Rp, std::int64_t* Out)
		{
			std::int32_t k = 0;
			Out[k++] = Rp.Started;
			Out[k++] = Rp.LiveSteps;
			Out[k++] = Rp.FleeSteps;
			Out[k++] = Rp.ReflexSteps;
			for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
			{
				Out[k++] = Rp.Num[c];
			}
			for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
			{
				Out[k++] = Rp.Steps[c];
			}
			for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
			{
				Out[k++] = Rp.Contact[c];
			}
			Out[k++] = Rp.OwnN;
			Out[k++] = Rp.OwnSteps;
			Out[k++] = Rp.OwnContact;
			Out[k++] = Rp.ShelterEnd;
			for (std::int32_t h = 0; h <= kNumFlightHistEdges; ++h)
			{
				Out[k++] = Rp.Hist[h];
			}
			for (std::int32_t j = 0; j < 3; ++j)
			{
				Out[k++] = Rp.LostFoliage[j];
			}
		}
	}

	/** 도망 기록 장면: 재료(잎만 가림 비트 128 포함)로 FlightUpdate — 틱마다 지난 표적·보고 52 칸·사슴 칸 8·늑대 지난 표적 = 파이썬. 사례 = 틱. */
	inline FReport CheckFlightScenes()
	{
		FReport R;
		static_assert(G::kRowLen == 52 && G::kTrackLen == 8, "골든 칸 수");
		std::int32_t Deer = 0, Wolf = 0, Tick = 0, Trk = 0;
		for (std::int32_t s = 0; s < G::kFlSceneCount; ++s)
		{
			const std::int32_t N = G::kFlSceneN[s];
			const std::int32_t M = G::kFlSceneM[s];
			FFlightStats Stats;
			std::vector<FFlightTrack> Tracks(static_cast<size_t>(N));
			std::vector<FFlightTrack*> Ptrs(static_cast<size_t>(N));
			for (std::int32_t i = 0; i < N; ++i)
			{
				Ptrs[static_cast<size_t>(i)] = &Tracks[static_cast<size_t>(i)];
			}
			std::vector<FFlightDeerStep> Dd(static_cast<size_t>(N));
			std::vector<FFlightWolfStep> Wv(static_cast<size_t>(M));
			FFlightReport Last;
			for (std::int32_t k = 0; k < G::kFlSceneTicks[s]; ++k)
			{
				Detail::FCase C;
				for (std::int32_t m = 0; m < M; ++m)
				{
					C.Int(40, FlightPrevTarget(Ptrs.data(), N, m), G::kFlWolfPrev[Wolf + m]);
					Wv[static_cast<size_t>(m)] = Detail::WolfOf(G::kFlWolfBits[Wolf + m], G::kFlWolfTarget[Wolf + m]);
				}
				for (std::int32_t i = 0; i < N; ++i)
				{
					Dd[static_cast<size_t>(i)] = Detail::DeerOf(G::kFlDeer[Deer + i]);
				}
				FlightUpdate(Stats, Ptrs.data(), Dd.data(), N, Wv.data(), M);
				FFlightOpen O;
				for (const FFlightTrack& T : Tracks)
				{
					O.Add(T);
				}
				Last = FlightReportOf(Stats, O);
				std::int64_t Got[G::kRowLen] = {};
				Detail::Row(Last, Got);
				const std::int64_t* Want = G::kFlStats + static_cast<std::int64_t>(G::kRowLen) * Tick;
				for (std::int32_t j = 0; j < G::kRowLen; ++j)
				{
					C.Int(41 + j, Got[j], Want[j]);
				}
				for (std::int32_t i = 0; i < N; ++i)
				{
					const FFlightTrack& T = Tracks[static_cast<size_t>(i)];
					const std::int32_t* Wt = G::kFlTracks + Trk + G::kTrackLen * i;
					C.Int(93, T.Len, Wt[0]);
					C.Int(94, T.Contact, Wt[1]);
					C.Int(95, T.Reflex, Wt[2]);
					C.Int(96, T.bChased ? 1 : 0, Wt[3]);
					C.Int(97, T.Why, Wt[4]);
					C.Int(98, T.bEndNow ? 1 : 0, Wt[5]);
					C.Int(99, T.bEndCov ? 1 : 0, Wt[6]);
					C.Int(100, T.bWhyFol ? 1 : 0, Wt[7]);
				}
				for (std::int32_t m = 0; m < M; ++m)
				{
					C.Int(101, FlightPrevTarget(Ptrs.data(), N, m), G::kFlPrevAfter[Wolf + m]);
				}
				Detail::Close(R, Tick, C);
				Deer += N;
				Wolf += M;
				Trk += G::kTrackLen * N;
				++Tick;
			}
			R.Count0 += Last.LostFoliage[0];
			R.Count1 += Last.Num[kFlightObstacle];
			R.Count2 += Last.Started;
		}
		return R;
	}

	namespace Detail
	{
		/** 기준 루프 세계 하나 (평가기 Tools/EcoV3Eval FEval 과 같은 꼴 — 통합 모드처럼 산 사슴만 Step 에 넘긴다). */
		struct FLoopWorld
		{
			FWorldState W;
			std::vector<R3::FRepState> Reps;
			std::vector<FHerbDecision> Dec;
			std::vector<FHerbBody> Bodies;
			std::vector<FHerbPerception> Perc;
			std::vector<R3::FControlOutput> Ctl;
			std::vector<FThreatAgent> Threats;
			std::vector<FThreatAgent*> ThreatPtrs;
			std::vector<FHerbView> Live;
			std::vector<std::int32_t> LiveSlot;
			std::vector<std::int32_t> Cause;      // 0 산, 1 잡힘, 2 굶음 (world.py death_cause)
			std::int64_t Draws = 0;               // 날 수열에서 뽑은 수
			bool bRngOverflow = false;
			std::vector<std::uint8_t> Bytes;      // 지문 바이트 (재사용)
		};

		inline std::uint64_t RawHook(void* User)
		{
			FLoopWorld& L = *static_cast<FLoopWorld*>(User);
			constexpr std::int64_t Count = static_cast<std::int64_t>(sizeof(G::kWorldRaw) / sizeof(G::kWorldRaw[0]));
			if (L.Draws >= Count)
			{
				L.bRngOverflow = true;
				return 0;
			}
			return G::kWorldRaw[L.Draws++];
		}

		inline FHerbView ViewOf(FLoopWorld& L, std::int32_t s)
		{
			const size_t k = static_cast<size_t>(s);
			return FHerbView{&L.Reps[k], &L.Dec[k], &L.Bodies[k], &L.Perc[k], &L.Ctl[k]};
		}

		/**
		 * 시작 상태 (EcoV3Eval.cpp Init 과 같다): 설정(FillWorldConfig — bFoliage 거짓이면 숲 시야 끔, bJunk 면 끈 칸에 엉뚱한 r·block·나무 표), 먹이 격자,
		 * 사슴 입양(슬롯 키·파이썬 값 그대로), 늑대 입양, 날 난수, 내장 망 R1b + 관측 21 세계(망은 18 칸만 읽는다 — 관측 21 0 열 두뇌와 같은 로짓)로 첫 관측·첫 요청.
		 */
		inline void Init(FLoopWorld& L, bool bFoliage, bool bJunk, FCase& C)
		{
			FWorldConfig Cfg;
			G::FillWorldConfig(Cfg);
			Cfg.Covers.clear();
			for (std::int32_t k = 0; k < G::kWorldCoverCount; ++k)
			{
				Cfg.Covers.push_back({G::kWorldCovers[3 * k], G::kWorldCovers[3 * k + 1], G::kWorldCovers[3 * k + 2]});
			}
			Cfg.Obstacles.Discs.assign(G::kWorldDiscs, G::kWorldDiscs + 3 * G::kWorldDiscCount);
			Cfg.Obstacles.Foliage.Trees.assign(G::kWorldTrees, G::kWorldTrees + G::kWorldDiscCount);
			if (!bFoliage)
			{
				Cfg.Obstacles.Foliage.bEnabled = false;
				if (bJunk)
				{
					// 끈 숲 시야의 칸은 읽지 않는다: 아주 짧은 문턱·나무 표 모두 나무여도 세계가 같아야 한다
					Cfg.Obstacles.Foliage.R = 20.0;
					Cfg.Obstacles.Foliage.Block = 1e-6;
					Cfg.Obstacles.Foliage.Trees.assign(static_cast<size_t>(G::kWorldDiscCount), 1);
				}
			}
			InitWorld(L.W, Cfg);
			SetModelAllowed(L.W, EcoPolicyV3::kAllowedMask);
			SetModelObsDim(L.W, EcoObservationV3::kObsDimObstacle);
			FFoodGrid& Fg = L.W.Food;
			C.Ok(110, Fg.Gw == G::kWorldGw && Fg.Cell == G::kWorldCell);
			const size_t Cells = static_cast<size_t>(G::kWorldGw) * static_cast<size_t>(G::kWorldGw);
			C.Ok(110, sizeof(G::kWorldCap) / sizeof(double) == Cells);
			Fg.Cap.assign(G::kWorldCap, G::kWorldCap + Cells);
			Fg.Food.assign(G::kWorldFood, G::kWorldFood + Cells);
			Fg.Regen.assign(G::kWorldRegen, G::kWorldRegen + Cells);
			Fg.Cap0 = Fg.Cap;
			const std::int32_t N = G::kWorldN;
			const size_t Nz = static_cast<size_t>(N);
			L.Reps.assign(Nz, R3::FRepState());
			L.Dec.assign(Nz, FHerbDecision());
			L.Bodies.assign(Nz, FHerbBody());
			L.Perc.assign(Nz, FHerbPerception());
			L.Ctl.assign(Nz, R3::FControlOutput());
			L.Cause.assign(Nz, 0);
			L.Live.clear();
			L.LiveSlot.clear();
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Dv = G::kWorldDeer + 6 * i;
				const FHerbView H = ViewOf(L, i);
				const FVec2 P{Dv[0], Dv[1]};
				const FVec2 Hd{Dv[2], Dv[3]};
				C.Ok(110, Dv[4] == L.W.RepCfg.InitEnergy);
				AdoptHerb(L.W, H, P, Hd, R3::MakeAgentKey(static_cast<std::uint32_t>(i), 0));
				H.Body->Pos = P;   // 파이썬 값 그대로 (AdoptHerb 는 heading 을 다시 정규화한다)
				H.Body->PrevPos = P;
				H.Body->Head = Hd;
				H.Body->Slot = static_cast<std::uint32_t>(i);
				H.Body->Reserve = Dv[5];
				H.Body->ReproCd = G::kWorldDeerRepro[i];
				L.Live.push_back(H);
				L.LiveSlot.push_back(i);
			}
			const std::int32_t M = G::kWorldM;
			L.Threats.assign(static_cast<size_t>(M), FThreatAgent());
			L.ThreatPtrs.clear();
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wv = G::kWorldWolves + 5 * m;
				const T3::FThreatSpec Spec = G::kWorldWolfStalker[m] != 0 ? T3::MakeStalkerSpec(L.W.Config.PredSpeedMult, false, L.W.ThreatCfg)
																		 : T3::MakeChaserSpec(L.W.Config.PredSpeedMult, false, false, L.W.ThreatCfg);
				C.Ok(110, Spec.BaseSpeed == Wv[4]);
				FThreatAgent& A = L.Threats[static_cast<size_t>(m)];
				AdoptThreat(L.W, A, Spec, Wv[0], Wv[1], Wv[2], Wv[3], m);
				A.Slot = static_cast<std::uint32_t>(m);
				A.State.PosX = Wv[0];
				A.State.PosY = Wv[1];
				A.State.HeadX = Wv[2];   // 파이썬 값 그대로 (cos·sin)
				A.State.HeadY = Wv[3];
				A.PrevX = Wv[0];
				A.PrevY = Wv[1];
			}
			for (FThreatAgent& A : L.Threats)
			{
				L.ThreatPtrs.push_back(&A);
			}
			L.Draws = 0;
			L.bRngOverflow = false;
			L.W.Rng.External = &RawHook;
			L.W.Rng.ExternalUser = &L;
			ObserveAndDecideAll(L.W, L.Live.data(), static_cast<std::int32_t>(L.Live.size()), L.ThreatPtrs.data(), M);
		}

		inline void PutD(std::vector<std::uint8_t>& B, double V)
		{
			std::uint8_t T[8];
			std::memcpy(T, &V, 8);
			B.insert(B.end(), T, T + 8);
		}

		inline void PutF(std::vector<std::uint8_t>& B, float V)
		{
			std::uint8_t T[4];
			std::memcpy(T, &V, 4);
			B.insert(B.end(), T, T + 4);
		}

		inline void PutI(std::vector<std::uint8_t>& B, std::int32_t V)
		{
			std::uint8_t T[4];
			std::memcpy(T, &V, 4);
			B.insert(B.end(), T, T + 4);
		}

		/** 지문 (골든 생성기 머리 주석 '지문'). Alive0 = 그 스텝 첫머리에 산 슬롯, StepSlots = 이번 Step 에 넘긴 사슴의 슬롯 (없으면 표적 −1). */
		inline std::uint64_t Fingerprint(FLoopWorld& L, const std::vector<std::uint8_t>& Alive0, const std::vector<std::int32_t>* StepSlots)
		{
			std::vector<std::uint8_t>& B = L.Bytes;
			B.clear();
			const std::int32_t N = static_cast<std::int32_t>(L.Bodies.size());
			const std::int32_t M = static_cast<std::int32_t>(L.Threats.size());
			PutD(B, L.W.Dark);
			PutD(B, L.W.PredEma);
			for (std::int32_t f = 0; f < 6; ++f)
			{
				for (std::int32_t i = 0; i < N; ++i)
				{
					const FHerbBody& Bd = L.Bodies[static_cast<size_t>(i)];
					const double V[6] = {Bd.Pos.X, Bd.Pos.Y, Bd.Head.X, Bd.Head.Y, Bd.Energy, Bd.Reserve};
					PutD(B, V[f]);
				}
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				PutI(B, L.Cause[static_cast<size_t>(i)]);
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				PutI(B, L.Dec[static_cast<size_t>(i)].KeepMode);
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				if (Alive0[static_cast<size_t>(i)] != 0)
				{
					PutI(B, L.Reps[static_cast<size_t>(i)].Behavior);
				}
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				if (Alive0[static_cast<size_t>(i)] != 0)
				{
					const FHerbPerception& P = L.Perc[static_cast<size_t>(i)];
					for (std::int32_t k = 0; k < EcoObservationV3::kObsDim; ++k)
					{
						PutF(B, P.Obs[k]);
					}
					for (std::int32_t k = 0; k < EcoObservationV3::kNumObstacleObs; ++k)
					{
						PutF(B, P.ObstacleObs[k]);
					}
				}
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				const FHerbDecision& D = L.Dec[static_cast<size_t>(i)];
				if (L.Cause[static_cast<size_t>(i)] == 0 && D.KeepMode < 2)
				{
					PutI(B, D.Request);
				}
			}
			for (std::int32_t f = 0; f < 4; ++f)
			{
				for (std::int32_t m = 0; m < M; ++m)
				{
					const T3::FThreatState& T = L.Threats[static_cast<size_t>(m)].State;
					const double V[4] = {T.PosX, T.PosY, T.HeadX, T.HeadY};
					PutD(B, V[f]);
				}
			}
			for (std::int32_t m = 0; m < M; ++m)
			{
				PutI(B, L.Threats[static_cast<size_t>(m)].State.Cooldown);
			}
			for (std::int32_t m = 0; m < M; ++m)
			{
				PutI(B, L.Threats[static_cast<size_t>(m)].State.SatLeft);
			}
			for (std::int32_t m = 0; m < M; ++m)
			{
				const FThreatAgent& A = L.Threats[static_cast<size_t>(m)];
				std::int32_t Slot = -1;
				if (StepSlots != nullptr && A.Last.bHasTarget && A.Last.Target >= 0 && A.Last.Target < static_cast<std::int32_t>(StepSlots->size()))
				{
					Slot = (*StepSlots)[static_cast<size_t>(A.Last.Target)];
				}
				PutI(B, Slot);
			}
			EcoSha256::FState S;
			EcoSha256::Update(S, B.data(), B.size());
			std::uint8_t Dg[EcoSha256::kDigestBytes];
			EcoSha256::Final(S, Dg);
			std::uint64_t H = 0;
			for (std::int32_t k = 7; k >= 0; --k)
			{
				H = (H << 8) | Dg[k];
			}
			return H;
		}
	}

	/**
	 * 기준 루프: 파이썬 거울 세계와 같은 시작 상태·같은 세계 난수로 kWorldSteps 스텝 — 스텝마다 지문, kWorldEvery 스텝마다 기록 = 파이썬 (숲 시야 켬은
	 * kWorldHashOn·CheckOn, 끔은 kWorldHashOff·CheckOff). bJunk = 끔 판의 끈 칸을 엉뚱하게 채운다 (끔이면 읽지 않아야 한다). 사례 = 지문 (0 = 시작).
	 * 파이썬은 동족 차례 합 기하로 돌았다 (골든 생성기 머리 주석 '기준 루프').
	 */
	inline FReport CheckWorld(bool bFoliage, bool bJunk = false)
	{
		FReport R;
		Detail::FLoopWorld L;
		{
			Detail::FCase C;
			Detail::Init(L, bFoliage, bJunk, C);
			const std::vector<std::uint8_t> All(static_cast<size_t>(G::kWorldN), 1);
			C.Int(111, static_cast<std::int64_t>(Detail::Fingerprint(L, All, nullptr)), static_cast<std::int64_t>((bFoliage ? G::kWorldHashOn : G::kWorldHashOff)[0]));
			Detail::Close(R, 0, C);
		}
		const std::int32_t M = G::kWorldM;
		std::vector<std::uint8_t> Alive0(static_cast<size_t>(G::kWorldN), 1);
		std::vector<std::int32_t> StepSlots;
		std::int32_t Check = 0;
		for (std::int32_t t = 1; t <= G::kWorldSteps; ++t)
		{
			Detail::FCase C;
			for (size_t i = 0; i < Alive0.size(); ++i)
			{
				Alive0[i] = L.Cause[i] == 0 ? 1 : 0;
			}
			StepSlots = L.LiveSlot;
			Step(L.W, L.Live.data(), static_cast<std::int32_t>(L.Live.size()), L.ThreatPtrs.data(), M);
			size_t Keep = 0;
			for (size_t r = 0; r < L.Live.size(); ++r)
			{
				const std::int32_t Slot = L.LiveSlot[r];
				const FHerbBody& Bd = L.Bodies[static_cast<size_t>(Slot)];
				if (Bd.DeathCause != kDeathNone)
				{
					L.Cause[static_cast<size_t>(Slot)] = Bd.DeathCause == kDeathCaught ? 1 : 2;
					continue;   // 통합 모드: 다음 Step 부터 뺀다
				}
				L.Live[Keep] = L.Live[r];
				L.LiveSlot[Keep] = Slot;
				++Keep;
			}
			L.Live.resize(Keep);
			L.LiveSlot.resize(Keep);
			const std::uint64_t H = Detail::Fingerprint(L, Alive0, &StepSlots);
			C.Int(111, static_cast<std::int64_t>(H), static_cast<std::int64_t>((bFoliage ? G::kWorldHashOn : G::kWorldHashOff)[t]));
			if (t % G::kWorldEvery == 0 && Check < G::kWorldChecks)
			{
				std::int64_t Got[G::kWorldCheckLen] = {};
				for (const std::int32_t Cs : L.Cause)
				{
					Got[0] += Cs == 1 ? 1 : 0;
					Got[1] += Cs == 2 ? 1 : 0;
					Got[2] += Cs == 0 ? 1 : 0;
				}
				Detail::Row(FlightReportOf(L.W.Stats.Flight, FlightOpenOf(L.Live.data(), static_cast<std::int32_t>(L.Live.size()))), Got + 3);
				const std::int64_t* Want = (bFoliage ? G::kWorldCheckOn : G::kWorldCheckOff) + static_cast<std::int64_t>(G::kWorldCheckLen) * Check;
				for (std::int32_t j = 0; j < G::kWorldCheckLen; ++j)
				{
					C.Int(112, Got[j], Want[j]);
				}
				++Check;
			}
			Detail::Close(R, t, C);
		}
		Detail::FCase C;
		constexpr std::int64_t RawCount = static_cast<std::int64_t>(sizeof(G::kWorldRaw) / sizeof(G::kWorldRaw[0]));
		C.Ok(113, !L.bRngOverflow && L.Draws == RawCount);
		C.Int(112, Check, G::kWorldChecks);
		Detail::Close(R, G::kWorldSteps + 1, C);
		R.Count0 = L.W.Stats.Flight.LostFoliage[0];
		for (const std::int32_t Cs : L.Cause)
		{
			R.Count1 += Cs == 1 ? 1 : 0;
		}
		R.Count2 = L.W.Stats.Flight.Started;
		return R;
	}
}

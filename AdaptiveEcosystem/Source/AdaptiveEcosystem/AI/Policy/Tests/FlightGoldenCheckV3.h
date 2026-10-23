// v3 야생 (w3) 도망 기록 골든 대조 — EcoWorldV3.h (FlightUpdate·FlightClose·FlightReportOf·FlightPairOf·FlightPrevTarget, 단계 함수의 bFlightStats 줄)를
// FlightGoldenVectorsV3.h (herbivore_rl/export_golden_v3_flight.py, 세계 configs/v3_wild3_obs_mirror.yaml)와 맞춘다.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<cstring>`·`<vector>` 와 엔진 무관 v3 세계 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoFlightV3Test.cpp (AdaptiveEcosystem.Policy.V3.Flight.*)
//   g++ 하네스       herbivore_rl/tests/cpp/flight_v3_main.cpp (herbivore_rl/tests/test_flight_golden_v3.py)
// 도망 기록은 정수 셈이라 모든 칸이 == 로 같아야 한다. 쌍 장면의 거리·시야각 판정도 파이썬과 같은 식·같은 순서라 비트 단위로 같다.
//
// 칸 번호 (FReport::FirstField):
//   정의     0 까닭 수, 1 까닭 이름, 2 스스로 벗어남, 3 칸 경계, 4 놓침 → 끝 까닭, 5 숨은 뒤 지켜보기 길이·쫓긴 도망에서 빼는 끝 까닭 (10-23)
//   장면·루프 10 늑대 지난 표적(Step 앞, 파이썬 _fl_tgt), 11~59 보고 (11 + 보고 칸 — 골든 머리 주석 순서), 110~114 보고의 숨은 뒤 지켜보기 (10-23 — chased·
//            hidden·watching·cover_then_caught·cover_then_starved), 115 보고의 숨음 = 끝까지 지켜본 숨음 + 지켜보는 중 (10-23), 60~66 사슴 칸 (_fl_len·contact·
//            reflex·chased·why·end_now·end_cov), 67 사슴 지켜보기 칸 (_fl_watch 행 비트 — 10-23), 70 늑대 지난 표적(뒤)
//   쌍 장면  80 사냥 가능, 81 반경 안, 82 반경과 시야각 안, 83 원판이 가림, 84 은신처 표적 제외, 85 설정 상수
//   기준 루프 같음  90 위치·heading·에너지·죽음, 91 행동 상태, 92 결정·덮기, 93 위협 상태, 94 세계 난수·먹이·EMA, 95 기록(도망 말고), 96 끈 세계 도망 칸 0,
//            97 시작 = 끝 까닭 합, 98 FLEE 스텝 = 행동 칸, 99 반사 = 도주 덮기 칸, 100 산 사슴-스텝, 101 칸 합·쫓긴 ≤ 길이,
//            102 숨은 뒤 지켜보기 (숨음 + 지켜보는 동안 잡힘·굶음 = 은신처 끝, 숨음 = 끝까지 지켜본 숨음 + 지켜보는 중, 지켜보는 중 ≤ 숨음, 쫓긴 도망 ≥
//            은신처 끝 + 잡힘, 시계 = 스텝)

#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>

#include "../EcoWorldV3.h"
#include "../FlightGoldenVectorsV3.h"

namespace EcoWorldV3::FlightCheck
{
	namespace G = EcoWorldV3::GoldenFlight;
	namespace T3 = EcoThreatV3;

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례
		std::int32_t Failures = 0;     // 어긋난 사례
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)
		std::int64_t Count0 = 0;       // 묶음마다 C++ 이 낸 수: 장면·루프 = 끝 보고 시작 도망 합, 쌍 = 원판 가림 쌍, 같음 = 켠 세계 시작 도망
		std::int64_t Count1 = 0;       // 장면·루프 = 스스로 벗어남 합, 쌍 = 은신처 표적 제외 쌍, 같음 = 스스로 벗어남
		std::int64_t Count2 = 0;       // 장면·루프 = 0 이 아닌 끝 까닭 수 (11 가운데), 쌍 = 사냥 못 하는 늑대, 같음 = 0 이 아닌 끝 까닭 수
		std::int64_t Hidden = 0;       // 10-23 장면·루프·같음 = 끝 보고의 숨어 살아남은 도망 합 (지켜보는 중 포함)
		std::int64_t CoverDied = 0;    // 10-23 장면·루프·같음 = 끝 보고의 지켜보는 동안 잡힘·굶음 합

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

		/** 골든 사슴 재료 비트 (머리 주석 '칸 묶음'). */
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

		/** 골든 늑대 재료 비트 + 표적. 쌍 칸은 그 늑대의 지난 표적과의 값이다. */
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
			return Wf;
		}

		/**
		 * 보고를 골든 54 칸 순서로 (started, live_steps, flee_steps, reflex_steps, n·steps·contact × 11, own_n, own_steps, own_contact, shelter_end, hist × 8,
		 * 10-23 hide: chased, hidden, watching, cover_then_caught, cover_then_starved).
		 */
		inline void StatsRow(const FFlightReport& R, std::int64_t* Out)
		{
			std::int32_t k = 0;
			Out[k++] = R.Started;
			Out[k++] = R.LiveSteps;
			Out[k++] = R.FleeSteps;
			Out[k++] = R.ReflexSteps;
			for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
			{
				Out[k++] = R.Num[c];
			}
			for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
			{
				Out[k++] = R.Steps[c];
			}
			for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
			{
				Out[k++] = R.Contact[c];
			}
			Out[k++] = R.OwnN;
			Out[k++] = R.OwnSteps;
			Out[k++] = R.OwnContact;
			Out[k++] = R.ShelterEnd;
			for (std::int32_t h = 0; h <= kNumFlightHistEdges; ++h)
			{
				Out[k++] = R.Hist[h];
			}
			Out[k++] = R.Chased;
			Out[k++] = R.Hidden;
			Out[k++] = R.Watching;
			Out[k++] = R.CoverCaught;
			Out[k++] = R.CoverStarved;
		}

		/** 보고 칸 k 의 칸 번호 (머리 주석 — 앞 49 칸 11~59, 숨은 뒤 지켜보기 110~). */
		inline std::int32_t StatsField(std::int32_t k)
		{
			return k < 49 ? 11 + k : 110 + (k - 49);
		}

		/** 사슴 지켜보기 칸 비트 덩이 j (골든 kWatchChunkBits 비트씩 — 칸 j·B ~ j·B + B − 1, world.py _fl_watch 행의 0 아닌 칸). */
		inline std::int32_t WatchChunk(const FFlightTrack& T, std::int32_t j)
		{
			std::int32_t Out = 0;
			for (std::int32_t b = 0; b < G::kWatchChunkBits; ++b)
			{
				const std::int32_t Col = j * G::kWatchChunkBits + b;
				if (Col < kFlightHideWatchSteps && FlightWatchHas(T, Col))
				{
					Out |= 1 << b;
				}
			}
			return Out;
		}

		/** 재료 열 하나를 되풀이하는 그릇 (사슴 칸 + 누적). */
		struct FReplay
		{
			FFlightStats Stats;
			std::vector<FFlightTrack> Tracks;
			std::vector<FFlightTrack*> Ptrs;
			std::vector<FFlightDeerStep> Deer;
			std::vector<FFlightWolfStep> Wolves;

			explicit FReplay(std::int32_t N)
				: Tracks(static_cast<size_t>(N)), Ptrs(static_cast<size_t>(N)), Deer(static_cast<size_t>(N))
			{
				for (std::int32_t i = 0; i < N; ++i)
				{
					Ptrs[static_cast<size_t>(i)] = &Tracks[static_cast<size_t>(i)];
				}
			}

			std::int32_t N() const { return static_cast<std::int32_t>(Tracks.size()); }

			FFlightReport Report() const
			{
				FFlightOpen O;
				for (const FFlightTrack& T : Tracks)
				{
					O.Add(T);
				}
				return FlightReportOf(Stats, O);
			}

			/** 한 스텝: 늑대마다 C++ 이 사슴 비트로 찾은 지난 표적 = 파이썬 _fl_tgt 인지 보고(칸 10), 재료로 FlightUpdate. */
			void Step(Detail::FCase& C, const std::uint8_t* DeerBits, const std::uint8_t* WolfBits, const std::int32_t* Targets, const std::int32_t* Prev,
					  std::int32_t M)
			{
				const std::int32_t Nn = N();
				Wolves.resize(static_cast<size_t>(M));
				for (std::int32_t m = 0; m < M; ++m)
				{
					C.Int(10, FlightPrevTarget(Ptrs.data(), Nn, m), Prev[m]);
					Wolves[static_cast<size_t>(m)] = WolfOf(WolfBits[m], Targets[m]);
				}
				for (std::int32_t i = 0; i < Nn; ++i)
				{
					Deer[static_cast<size_t>(i)] = DeerOf(DeerBits[i]);
				}
				FlightUpdate(Stats, Ptrs.data(), Deer.data(), Nn, Wolves.data(), M);
			}

			/** 보고 49 칸·사슴 칸·늑대 지난 표적(뒤) = 골든. */
			void Compare(Detail::FCase& C, const std::int64_t* WantStats, const std::int32_t* WantTracks, const std::int32_t* WantPrev, std::int32_t M) const
			{
				std::int64_t Row[G::kStatsLen] = {};
				const FFlightReport Rp = Report();
				StatsRow(Rp, Row);
				for (std::int32_t k = 0; k < G::kStatsLen; ++k)
				{
					C.Int(StatsField(k), Row[k], WantStats[k]);
				}
				// 10-23 보고의 숨음(은신처 끝 − 지켜보는 동안 잡힘·굶음) = 끝까지 지켜본 숨음 + 지금 지켜보는 것 (사슴 칸이 모두 있다 — 파이썬 _fl_hidden + _fl_watch_open)
				C.Int(115, Stats.Hidden + Rp.Watching, Rp.Hidden);
				const std::int32_t Nn = N();
				for (std::int32_t i = 0; i < Nn; ++i)
				{
					const FFlightTrack& T = Tracks[static_cast<size_t>(i)];
					const std::int32_t* Wt = WantTracks + G::kTrackLen * i;
					C.Int(60, T.Len, Wt[0]);
					C.Int(61, T.Contact, Wt[1]);
					C.Int(62, T.Reflex, Wt[2]);
					C.Int(63, T.bChased ? 1 : 0, Wt[3]);
					C.Int(64, T.Why, Wt[4]);
					C.Int(65, T.bEndNow ? 1 : 0, Wt[5]);
					C.Int(66, T.bEndCov ? 1 : 0, Wt[6]);
					for (std::int32_t j = 0; j < G::kWatchChunks; ++j)
					{
						C.Int(67, WatchChunk(T, j), Wt[7 + j]);   // 10-23 숨은 뒤 지켜보기 칸
					}
				}
				for (std::int32_t m = 0; m < M; ++m)
				{
					C.Int(70, FlightPrevTarget(Ptrs.data(), Nn, m), WantPrev[m]);
				}
			}
		};

		inline void Tally(FReport& R, const FFlightReport& Rp)
		{
			R.Count0 += Rp.Started;
			R.Count1 += Rp.OwnN;
			for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
			{
				R.Count2 += Rp.Num[c] > 0 ? 1 : 0;
			}
			R.Hidden += Rp.Hidden;
			R.CoverDied += Rp.CoverCaught + Rp.CoverStarved;
		}
	}

	/** 정의: 끝 까닭 수·이름·스스로 벗어남·쫓긴 시간 칸 경계·놓침 까닭 → 끝 까닭 = 파이썬. */
	inline FReport CheckDefinitions()
	{
		FReport R;
		Detail::FCase C;
		C.Int(0, kNumFlightCauses, G::kNumCauses);
		for (std::int32_t c = 0; c < kNumFlightCauses && c < G::kNumCauses; ++c)
		{
			C.Ok(1, std::strcmp(FlightCauseName(c), G::kCauseNames[c]) == 0);
		}
		C.Int(2, kNumFlightOwn, G::kNumOwn);
		for (std::int32_t k = 0; k < G::kNumOwn; ++k)
		{
			C.Int(2, G::kOwn[k] < kNumFlightOwn ? 1 : 0, 1);   // 스스로 벗어남 = 앞 kNumFlightOwn 칸
		}
		C.Int(3, kNumFlightHistEdges, static_cast<std::int64_t>(sizeof(G::kHistSteps) / sizeof(G::kHistSteps[0])));
		for (std::int32_t k = 0; k < kNumFlightHistEdges; ++k)
		{
			C.Int(3, kFlightHistSteps[k], G::kHistSteps[k]);
		}
		C.Int(4, kNumFlDrops, static_cast<std::int64_t>(sizeof(G::kDropCause) / sizeof(G::kDropCause[0])));
		for (std::int32_t k = 0; k < kNumFlDrops; ++k)
		{
			C.Int(4, kFlDropCause[k], G::kDropCause[k]);
		}
		// 칸 경계 끝 사례 (np.searchsorted side='right')
		C.Int(3, FlightHistBin(0), 0);
		C.Int(3, FlightHistBin(7), 0);
		C.Int(3, FlightHistBin(8), 1);
		C.Int(3, FlightHistBin(599), 6);
		C.Int(3, FlightHistBin(600), 7);
		C.Int(0, FWorldConfig().bFlightStats ? 1 : 0, 0);   // 기본 끔
		// 10-23 숨은 뒤 지켜보기: 지켜보는 길이(스텝)·쫓긴 도망에서 빼는 끝 까닭, 골든 사슴 칸 덩이가 지켜보기 칸을 덮는다
		C.Int(5, kFlightHideWatchSteps, G::kHideWatchSteps);
		C.Int(5, kNumFlightNotChased, G::kNumNotChased);
		for (std::int32_t k = 0; k < kNumFlightNotChased && k < G::kNumNotChased; ++k)
		{
			C.Int(5, kFlightNotChased[k], G::kNotChased[k]);
		}
		C.Int(5, G::kWatchChunks * G::kWatchChunkBits >= kFlightHideWatchSteps ? 1 : 0, 1);
		C.Int(5, G::kTrackLen, 7 + G::kWatchChunks);
		Detail::Close(R, 0, C);
		return R;
	}

	/** 짜 맞춘 장면 (test_flight_v3 `_tick` 장면 셋 + 난수 장면): 틱마다 지난 표적·보고·사슴 칸·늑대 지난 표적 = 파이썬. 사례 = 틱. */
	inline FReport CheckScenes()
	{
		FReport R;
		std::int32_t Deer = 0, Wolf = 0, Tick = 0, Trk = 0;
		for (std::int32_t s = 0; s < G::kSceneCount; ++s)
		{
			const std::int32_t N = G::kSceneN[s];
			const std::int32_t M = G::kSceneM[s];
			Detail::FReplay Rp(N);
			for (std::int32_t k = 0; k < G::kSceneTicks[s]; ++k)
			{
				Detail::FCase C;
				Rp.Step(C, G::kSceneDeer + Deer, G::kSceneWolfBits + Wolf, G::kSceneWolfTarget + Wolf, G::kSceneWolfPrev + Wolf, M);
				Rp.Compare(C, G::kSceneStats + static_cast<std::int64_t>(G::kStatsLen) * Tick, G::kSceneTracks + Trk, G::kScenePrevAfter + Wolf, M);
				Detail::Close(R, Tick, C);
				Deer += N;
				Wolf += M;
				Trk += G::kTrackLen * N;
				++Tick;
			}
			Detail::Tally(R, Rp.Report());
		}
		return R;
	}

	/** 기준 루프 (거울 세계 600 스텝의 재료): 스텝마다 지난 표적, 100 스텝마다 보고·사슴 칸·늑대 지난 표적 = 파이썬. 사례 = 스텝. */
	inline FReport CheckLoop()
	{
		FReport R;
		const std::int32_t N = G::kLoopN;
		const std::int32_t M = G::kLoopM;
		Detail::FReplay Rp(N);
		std::int32_t Check = 0;
		for (std::int32_t t = 0; t < G::kLoopSteps; ++t)
		{
			Detail::FCase C;
			Rp.Step(C, G::kLoopDeer + N * t, G::kLoopWolfBits + M * t, G::kLoopWolfTarget + M * t, G::kLoopWolfPrev + M * t, M);
			if ((t + 1) % G::kLoopEvery == 0 && Check < G::kLoopChecks)
			{
				Rp.Compare(C, G::kLoopStats + static_cast<std::int64_t>(G::kStatsLen) * Check, G::kLoopTracks + G::kTrackLen * N * Check,
						   G::kLoopPrevAfter + M * Check, M);
				++Check;
			}
			Detail::Close(R, t, C);
		}
		Detail::FCase C;
		C.Int(11, Check, G::kLoopChecks);
		Detail::Close(R, G::kLoopSteps, C);
		Detail::Tally(R, Rp.Report());
		return R;
	}

	/**
	 * 쌍 장면: 같은 이동 전 상태·입력으로 FlightPairOf(모든 늑대 × 사슴)와 위협 Step 사본의 사냥 가능 = 파이썬 `_fl_pred`. 늑대 순번 = 골든 종류, 낮 d = 0,
	 * 은신처 안전(표적 제외)·원판 눈길 가림, 잠은 늑대별 상태(밤잠 점진화 켬 — 낮이라 새 사냥 막기는 걸리지 않는다). 사례 = 장면.
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
			C.Int(85, Cfg.PredViewR == G::kPairViewR ? 1 : 0, 1);
			C.Int(85, Cfg.PredFovCos == G::kPairFovCos ? 1 : 0, 1);
			C.Int(85, Cfg.CStill == G::kPairCStill ? 1 : 0, 1);
			C.Int(85, (Cfg.CoverMultCrouch == G::kPairCoverMult[0] && Cfg.CoverMultGraze == G::kPairCoverMult[1] && Cfg.CoverMultSleep == G::kPairCoverMult[2]
					   && Cfg.CoverMultOther == G::kPairCoverMult[3]) ? 1 : 0, 1);
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
			In.Obstacles = G::kPairDiscs;
			In.NumObstacles = G::kPairDiscCount;
			In.ObstacleBody = 0.15;
			In.bObstacleSight = true;
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
				C.Int(80, Res.bHunting ? 1 : 0, G::kPairHunt[s * M + m]);
				R.Count2 += Res.bHunting ? 0 : 1;
				for (std::int32_t i = 0; i < N; ++i)
				{
					const FFlightPair Pr = FlightPairOf(T, Prey[static_cast<size_t>(i)], In, Cfg);
					const std::uint8_t Want = G::kPairFlags[(s * M + m) * N + i];
					C.Int(81, Pr.bRange ? 1 : 0, Want & 1);
					C.Int(82, Pr.bVis0 ? 1 : 0, (Want >> 1) & 1);
					C.Int(83, Pr.bBlocked ? 1 : 0, (Want >> 2) & 1);
					C.Int(84, Pr.bCover ? 1 : 0, (Want >> 3) & 1);
					R.Count0 += Pr.bBlocked ? 1 : 0;
					R.Count1 += Pr.bCover ? 1 : 0;
				}
			}
			Detail::Close(R, s, C);
		}
		return R;
	}

	/** 기준 루프 같음 검사의 세계 (무대 60, 사슴 64, 늑대 잠행 2·추격 2, 은신처 4 안전, 도주 반사·포만·감지, 원판 = 골든 숲 배치, 부활 있음). */
	inline FWorldConfig RunConfig(bool bFlightStats)
	{
		FWorldConfig C;
		C.WorldSize = G::kPairWorldSize;
		C.Seed = 20021;
		C.NumHerbivores = 64;
		C.NumStalkers = 2;
		C.NumChasers = 2;
		C.NumRanged = 0;
		C.NumNocturnal = 0;
		C.Covers = QuadCovers(C.WorldSize, 6.0);
		C.bShelterSafe = true;
		C.ShelterWolfMargin = 0.5;
		C.WildFlight.bEnabled = true;
		C.WildFlight.bHoldAwake = true;
		C.WildFlight.EdgeR = 5.0;
		C.WildSatiation.bEnabled = true;
		C.PredEatCdOverride = 38;
		C.bEatInPlace = true;
		C.RealismVision.bEnabled = true;
		C.RealismHearing.bEnabled = true;
		C.Obstacles.bEnabled = true;
		C.Obstacles.Discs.assign(G::kPairDiscs, G::kPairDiscs + 3 * G::kPairDiscCount);
		C.bFlightStats = bFlightStats;
		return C;
	}

	/**
	 * 기록 켬 = 끔 (비트 단위): 같은 기준 루프를 bFlightStats 켬·끔으로 Steps 스텝 돌려 스텝마다 몸·행동·결정·덮기·위협·세계 난수·먹이·EMA·기록(도망 말고)이 같고
	 * 끈 세계의 도망 칸이 0 인지 본다(사례 = 스텝). 끝에 켠 세계의 보고: 시작 = 끝 까닭 합, FLEE 스텝 = 행동 칸 FLEE, 반사 = 도주 덮기 칸, 산 사슴-스텝 = N × 스텝,
	 * 쫓긴 ≤ 길이·안 쫓김 쫓긴 0·칸 합 = 스스로 벗어남.
	 */
	inline FReport CheckRunIdentity(std::int32_t Steps = 900, FFlightReport* OutReport = nullptr)
	{
		FReport R;
		FReferenceWorld A, B;
		A.Init(RunConfig(false));
		B.Init(RunConfig(true));
		const std::int32_t N = A.NumHerbivores();
		for (std::int32_t t = 0; t < Steps; ++t)
		{
			A.StepOnce();
			B.StepOnce();
			Detail::FCase C;
			for (std::int32_t i = 0; i < N; ++i)
			{
				const size_t I = static_cast<size_t>(i);
				const FHerbBody& Ba = A.Bodies[I];
				const FHerbBody& Bb = B.Bodies[I];
				C.Ok(90, Ba.Pos.X == Bb.Pos.X && Ba.Pos.Y == Bb.Pos.Y && Ba.Head.X == Bb.Head.X && Ba.Head.Y == Bb.Head.Y && Ba.Energy == Bb.Energy
							   && Ba.Reserve == Bb.Reserve && Ba.DeathCause == Bb.DeathCause && Ba.Generation == Bb.Generation && Ba.CaughtBy == Bb.CaughtBy);
				const EcoRepertoireV3::FRepState& Sa = A.Reps[I];
				const EcoRepertoireV3::FRepState& Sb = B.Reps[I];
				C.Ok(91, Sa.Behavior == Sb.Behavior && Sa.Phase == Sb.Phase && Sa.StepsIn == Sb.StepsIn && Sa.Seq == Sb.Seq && Sa.LockLeft == Sb.LockLeft
							   && Sa.StartleLeft == Sb.StartleLeft && Sa.EvWait == Sb.EvWait && Sa.HideTarget == Sb.HideTarget && Sa.bArrived == Sb.bArrived
							   && Sa.Recency == Sb.Recency && Sa.SeeMult == Sb.SeeMult && Sa.Away.X == Sb.Away.X && Sa.Away.Y == Sb.Away.Y);
				const FHerbDecision& Da = A.Decisions[I];
				const FHerbDecision& Db = B.Decisions[I];
				bool bSame = Da.Request == Db.Request && Da.ExecutedBehavior == Db.ExecutedBehavior && Da.KeepMode == Db.KeepMode && Da.KeepActive == Db.KeepActive
							 && Da.KeepDir.X == Db.KeepDir.X && Da.KeepDir.Y == Db.KeepDir.Y && Da.KeepPanicSteps == Db.KeepPanicSteps
							 && Da.bCommittedReads == Db.bCommittedReads;
				for (std::int32_t b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
				{
					bSame = bSame && Da.Logits[b] == Db.Logits[b] && Da.Mask[b] == Db.Mask[b];
				}
				for (std::int32_t k = 0; k < EcoObservationV3::kObsDim; ++k)
				{
					bSame = bSame && A.Perceptions[I].Obs[k] == B.Perceptions[I].Obs[k];
				}
				C.Ok(92, bSame);
				const FFlightTrack& Fa = Da.Flight;
				C.Ok(96, Fa.Len == 0 && Fa.Contact == 0 && Fa.Reflex == 0 && !Fa.bChased && Fa.Why == 0 && !Fa.bEndNow && !Fa.bEndCov && Fa.PrevBy == 0
							   && Fa.Watch[0] == 0 && Fa.Watch[1] == 0);
			}
			for (std::int32_t m = 0; m < A.NumThreats(); ++m)
			{
				const T3::FThreatState& Ta = A.Threats[static_cast<size_t>(m)].State;
				const T3::FThreatState& Tb = B.Threats[static_cast<size_t>(m)].State;
				C.Ok(93, Ta.PosX == Tb.PosX && Ta.PosY == Tb.PosY && Ta.HeadX == Tb.HeadX && Ta.HeadY == Tb.HeadY && Ta.VelX == Tb.VelX && Ta.VelY == Tb.VelY
							   && Ta.Cooldown == Tb.Cooldown && Ta.StalkState == Tb.StalkState && Ta.StalkLeft == Tb.StalkLeft && Ta.SatLeft == Tb.SatLeft
							   && Ta.Target == Tb.Target);
			}
			const FWorldState& Wa = A.World;
			const FWorldState& Wb = B.World;
			C.Ok(94, Wa.Rng.State == Wb.Rng.State && Wa.T == Wb.T && Wa.PredEma == Wb.PredEma && Wa.Food.Food == Wb.Food.Food && Wa.Dark == Wb.Dark);
			const FWorldStats& Xa = Wa.Stats;
			const FWorldStats& Xb = Wb.Stats;
			bool bStats = Xa.Caught == Xb.Caught && Xa.Starved == Xb.Starved && Xa.Reproduced == Xb.Reproduced && Xa.Decisions == Xb.Decisions
						  && Xa.MaskViolations == Xb.MaskViolations && Xa.KeepPanicStarts == Xb.KeepPanicStarts && Xa.KeepPanicEnds == Xb.KeepPanicEnds
						  && Xa.KeepPanicDied == Xb.KeepPanicDied && Xa.FoodEaten == Xb.FoodEaten && Xa.LiveDeerSteps == Xb.LiveDeerSteps
						  && Xa.ShelterDeerSteps == Xb.ShelterDeerSteps && Xa.ObstacleDeerHit == Xb.ObstacleDeerHit;
			for (std::int32_t b = 0; b < EcoRepertoireV3::kNumBehaviors; ++b)
			{
				bStats = bStats && Xa.BehaviorSteps[b] == Xb.BehaviorSteps[b] && Xa.Entries[b] == Xb.Entries[b];
			}
			for (std::int32_t k = 0; k < kNumKeepModes; ++k)
			{
				bStats = bStats && Xa.KeepSteps[k] == Xb.KeepSteps[k] && Xa.CaughtByKeep[k] == Xb.CaughtByKeep[k];
			}
			for (std::int32_t k = 0; k < kNumHuntKinds; ++k)
			{
				bStats = bStats && Xa.HuntStarts[k] == Xb.HuntStarts[k] && Xa.HuntSuccess[k] == Xb.HuntSuccess[k];
			}
			C.Ok(95, bStats);
			C.Ok(96, Xa.Flight.Started == 0 && Xa.Flight.LiveSteps == 0 && Xa.Flight.ReflexSteps == 0 && Xa.Flight.Clock == 0 && Xa.Flight.Hidden == 0
						 && Xa.Flight.CoverCaught == 0 && Xa.Flight.CoverStarved == 0);
			Detail::Close(R, t, C);
		}
		// 켠 세계의 보고 (지금 열린 도망 = 잘림)
		const FFlightReport Rp = FlightReportOf(B.World.Stats.Flight, FlightOpenOf(B.Views.data(), N));
		const FWorldStats& Sb = B.World.Stats;
		Detail::FCase C;
		std::int64_t SumN = 0, SumHist = 0;
		bool bLe = true;
		for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
		{
			SumN += Rp.Num[c];
			bLe = bLe && Rp.Contact[c] >= 0 && Rp.Contact[c] <= Rp.Steps[c] && Rp.Steps[c] >= Rp.Num[c];
		}
		for (std::int32_t h = 0; h <= kNumFlightHistEdges; ++h)
		{
			SumHist += Rp.Hist[h];
		}
		C.Int(97, Rp.Started, SumN);
		C.Int(98, Rp.FleeSteps, Sb.BehaviorSteps[EcoRepertoireV3::kFlee]);
		C.Int(99, Rp.ReflexSteps, Sb.KeepSteps[kKeepPanic]);
		C.Int(100, Rp.LiveSteps, static_cast<std::int64_t>(N) * Steps);
		C.Ok(101, bLe && Rp.Contact[kFlightUnchased] == 0 && SumHist == Rp.OwnN && Rp.ShelterEnd <= Rp.Started && Rp.Started > 0 && Rp.OwnN > 0);
		// 10-23 숨은 뒤 지켜보기 (부활 있는 세계 — 죽은 칸의 새 개체는 지켜보지 않는다): 숨음 + 지켜보는 동안 잡힘·굶음 = 은신처 끝, 지켜보는 중 ≤ 숨음,
		// 쫓긴 도망 = 끝난 도망 − 안 쫓김(잘림은 끝난 도망이 아니다) ≥ 은신처 끝 + 잡힘, 시계 = 스텝, 은신처 끝·숨음이 있다
		std::int64_t Ended = 0;
		for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
		{
			Ended += Sb.Flight.Num[c];
		}
		C.Ok(102, Rp.Hidden + Rp.CoverCaught + Rp.CoverStarved == Rp.Num[kFlightCover] && Rp.Hidden == Sb.Flight.Hidden + Rp.Watching
					  && Rp.Watching >= 0 && Rp.Watching <= Rp.Hidden
					  && Rp.Chased == Ended - Sb.Flight.Num[kFlightUnchased] && Rp.Chased >= Rp.Num[kFlightCover] + Rp.Num[kFlightCaught]
					  && Sb.Flight.Clock == Steps && Rp.Num[kFlightCover] > 0 && Rp.Hidden > 0);
		Detail::Close(R, Steps, C);
		R.Count0 = Rp.Started;
		R.Count1 = Rp.OwnN;
		for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
		{
			R.Count2 += Rp.Num[c] > 0 ? 1 : 0;
		}
		R.Hidden = Rp.Hidden;
		R.CoverDied = Rp.CoverCaught + Rp.CoverStarved;
		if (OutReport)
		{
			*OutReport = Rp;
		}
		return R;
	}
}

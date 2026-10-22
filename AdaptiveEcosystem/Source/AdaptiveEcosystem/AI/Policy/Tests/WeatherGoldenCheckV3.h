// v3 야생 3단계 지역 날씨 골든 대조 — EcoWorldV3.h (FWeatherConfig·WeatherAt·WeatherMults·UpdateDayNight·SeePredNow·ObsVisibilityMult·WolfViewNow·
// BuildThreatInputs 발소리·B 사슴 속도) 와 EcoThreatModel.h (Step 의 WeatherViewMult·WeatherSpeedMult, PackPeek) 를
// WeatherGoldenVectorsV3.h (herbivore_rl/export_golden_v3_weather.py, 세계 configs/v3_wild3_mirror.yaml 세로 장애물 끔)와 맞춘다.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<cstring>`·`<vector>` 와 엔진 무관 v3 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoWeatherV3Test.cpp (AdaptiveEcosystem.Policy.V3.Weather.*)
//   g++ 하네스       herbivore_rl/tests/cpp/weather_v3_main.cpp (herbivore_rl/tests/test_wild3_weather.py)
// 모든 칸이 비트 단위로 같아야 한다(실수도 == — 파이썬과 같은 순서로 계산한다).
//
// 칸 번호 (FReport::FirstField):
//   설정   0 + 계수 번호, 10 지역 표, 12 탐지 반경·시야·어둠 계수, 13 발소리·위협 시야각 계수
//   배수   20 시야, 21 사슴 청각, 22 사슴 이동, 23 위협 이동
//   시간표 25 날씨, 26 세기
//   낮밤   30 어둠, 31 탐지 반경, 32 visibility, 33 늑대 시야, 34 날씨, 35 세기, 36~39 배수 넷
//   지각   40 장면 어둠, 41 장면 탐지 반경, 42 소리 반경, 43 보이는 수, 44 가장 가까운 거리, 45 알아챔 (쌍)
//   스텝   50 늑대 시야, 51 위협 이동, 60 위치 x, 61 위치 y, 62 heading x, 63 heading y, 64 쿨다운, 65 배부름, 66 잠행 상태, 67 남은 수,
//          68 돕기, 69 기다림, 70 문, 71 고른 사슴, 72 표적, 73 잡은 사슴
//   끔     80 기준 루프 상태가 날씨 끈 세계와 다름, 81 첫 스텝 눈 이동 배수

#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>
#include <vector>

#include "../EcoWorldV3.h"
#include "../WeatherGoldenVectorsV3.h"

namespace EcoWorldV3::WeatherCheck
{
	namespace G = EcoWorldV3::GoldenWeather;
	namespace T3 = EcoThreatV3;
	namespace O3 = EcoObservationV3;

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례
		std::int32_t Failures = 0;     // 어긋난 사례
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)
		std::int32_t Changed = 0;      // 날씨가 결과를 바꾼 수 (지각: 날씨 없으면 알아챔이 다른 쌍, 스텝: 날씨 없으면 자리·표적이 다른 늑대) — 0 이면 골든이 무디다
		std::int32_t Count = 0;        // 묶음마다 센 것 (지각: 알아챔 쌍, 스텝: 포획, 끔: 비교한 스텝)

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

			void Real(std::int32_t Id, double Got, double Want)
			{
				if (!(Got == Want) && Field < 0)
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

		/** 지역 번호 → 그 지역 고정 날씨를 켠 날씨 설정 (거울 계수). */
		inline FWeatherConfig RegionWeather(std::int32_t RegionIndex, bool bObsVisibility = true)
		{
			FWeatherConfig W;
			W.bEnabled = true;
			W.Kind = G::kRegionKind[RegionIndex];
			W.Intensity = G::kRegionIntensity[RegionIndex];
			W.bObsVisibility = bObsVisibility;
			return W;
		}

		/** 낮밤·지각 세계: 거울 세계 낮밤 (900·0·45), R3 감지(위협 시야 300°·발소리), 무대 60. */
		inline FWorldConfig SceneWorld(const FWeatherConfig& Wx)
		{
			FWorldConfig C;
			C.WorldSize = 60.0;
			C.NumHerbivores = G::kPercN;
			C.NumStalkers = 2;
			C.NumChasers = 2;
			C.NumRanged = 0;
			C.NumNocturnal = 0;
			C.DayPeriod = G::kDnPeriod;
			C.DayOffset = G::kDnOffset;
			C.TwilightSteps = G::kDnTwilight;
			C.RealismVision.bEnabled = true;
			C.RealismHearing.bEnabled = true;
			C.Weather = Wx;
			return C;
		}
	}

	/** 설정: C++ 기본값 = 거울 설정 wild_weather 계수·지역 표, 날씨는 기본 끔, 탐지 반경·늑대 시야·발소리 계수 = 거울 세계. */
	inline FReport CheckConfig()
	{
		FReport R;
		const FWeatherConfig D;
		Detail::FCase C;
		C.Int(0, D.bEnabled ? 1 : 0, 0);
		C.Int(0, FWorldConfig().Weather.bEnabled ? 1 : 0, 0);
		C.Real(1, D.RainSight, G::kCfg_rain_sight);
		C.Real(2, D.RainHear, G::kCfg_rain_hear);
		C.Real(3, D.SnowSight, G::kCfg_snow_sight);
		C.Real(4, D.SnowHear, G::kCfg_snow_hear);
		C.Real(5, D.SnowDeerSpeed, G::kCfg_snow_deer_speed);
		C.Real(6, D.SnowWolfSpeed, G::kCfg_snow_wolf_speed);
		C.Int(7, D.bObsVisibility ? 1 : 0, G::kCfgObsVisibility ? 1 : 0);
		C.Int(8, D.Schedule.empty() ? 1 : 0, G::kCfgScheduleNone ? 1 : 0);
		C.Int(9, D.Kind, kWeatherClear);
		for (std::int32_t r = 0; r < G::kRegions; ++r)
		{
			C.Int(10, std::strcmp(kRegionWeatherDefaults[r].Region, G::kRegionNames[r]) == 0 ? 1 : 0, 1);
			C.Int(10, kRegionWeatherDefaults[r].Kind, G::kRegionKind[r]);
			C.Real(10, kRegionWeatherDefaults[r].Intensity, G::kRegionIntensity[r]);
		}
		C.Real(12, O3::kR1bObsConfig.SeeR, G::kSeeR);
		C.Real(12, T3::FThreatConfig().PredViewR, G::kPredViewR);
		C.Real(12, O3::kR1bObsConfig.DetectNight, G::kDetectNight);
		const O3::FHearingConfig H;
		C.Real(13, H.RQuiet, G::kHearRQuiet);
		C.Real(13, H.RLoud, G::kHearRLoud);
		C.Int(13, H.bCapToSight ? 1 : 0, G::kHearCapToSight ? 1 : 0);
		C.Real(13, O3::kR1bObsConfig.HerbSpeed, G::kHerbSpeed);
		C.Real(13, O3::FovCosOf(FRealismVisionConfig().ThreatFovDeg, kBaseFovDeg, O3::kR1bObsConfig.FovCos), G::kThreatFovCos);
		Detail::Close(R, 0, C);
		return R;
	}

	/** 배수: WeatherMults = 파이썬 weather_mults (계수 여섯·날씨·세기 사례마다 넷). */
	inline FReport CheckMults()
	{
		FReport R;
		for (std::int32_t c = 0; c < G::kMultCases; ++c)
		{
			const double* In = G::kMultIn + 8 * c;
			const double* Out = G::kMultOut + 4 * c;
			FWeatherConfig W;
			W.RainSight = In[0];
			W.RainHear = In[1];
			W.SnowSight = In[2];
			W.SnowHear = In[3];
			W.SnowDeerSpeed = In[4];
			W.SnowWolfSpeed = In[5];
			const FWeatherMults M = WeatherMults(W, static_cast<std::int32_t>(In[6]), In[7]);
			Detail::FCase C;
			C.Real(20, M.Sight, Out[0]);
			C.Real(21, M.Hear, Out[1]);
			C.Real(22, M.DeerSpeed, Out[2]);
			C.Real(23, M.WolfSpeed, Out[3]);
			Detail::Close(R, c, C);
		}
		return R;
	}

	/** 시간표: WeatherAt = 파이썬 weather_at (세계 셋 × t). */
	inline FReport CheckSchedule()
	{
		FReport R;
		for (std::int32_t s = 0; s < G::kSchedWorlds; ++s)
		{
			FWeatherConfig W;
			W.Kind = static_cast<std::int32_t>(G::kSchedConst[2 * s]);
			W.Intensity = G::kSchedConst[2 * s + 1];
			for (std::int32_t r = 0; r < G::kSchedRows; ++r)
			{
				const double* Row = G::kSchedRow + 4 * r;
				if (static_cast<std::int32_t>(Row[0]) == s)
				{
					W.Schedule.push_back(FWeatherRow{static_cast<std::int64_t>(Row[1]), static_cast<std::int32_t>(Row[2]), Row[3]});
				}
			}
			for (std::int32_t j = 0; j < G::kSchedTimes; ++j)
			{
				const FWeatherRow Got = WeatherAt(W, G::kSchedT[j]);
				const double* Want = G::kSchedOut + 2 * (s * G::kSchedTimes + j);
				Detail::FCase C;
				C.Int(25, Got.Kind, static_cast<std::int32_t>(Want[0]));
				C.Real(26, Got.Intensity, Want[1]);
				Detail::Close(R, s * G::kSchedTimes + j, C);
			}
		}
		return R;
	}

	/** 낮밤: InitWorld(같은 낮밤·지역 날씨) → T = t → UpdateDayNight 가 파이썬 _daynight_update 와 같은 어둠·탐지 반경·visibility·늑대 시야·날씨·배수. */
	inline FReport CheckDayNight()
	{
		FReport R;
		FWorldState W;
		std::int32_t Key = -1;
		for (std::int32_t c = 0; c < G::kDnCases; ++c)
		{
			const double* In = G::kDnIn + 5 * c;
			const double* Out = G::kDnOut + 10 * c;
			const std::int32_t Region = static_cast<std::int32_t>(In[0]);
			const bool bVis = In[1] != 0.0;
			const std::int32_t NewKey = Region * 2 + (bVis ? 1 : 0);
			Detail::FCase C;
			if (NewKey != Key)
			{
				InitWorld(W, Detail::SceneWorld(Detail::RegionWeather(Region, bVis)));
				Key = NewKey;
			}
			C.Int(34, W.Config.Weather.Kind, static_cast<std::int32_t>(In[3]));
			C.Real(35, W.Config.Weather.Intensity, In[4]);
			W.T = static_cast<std::int64_t>(In[2]);
			UpdateDayNight(W);
			C.Real(30, W.Dark, Out[0]);
			C.Real(31, SeePredNow(W), Out[1]);
			C.Real(32, O3::Visibility(W.Dark, W.ObsCfg) * ObsVisibilityMult(W), Out[2]);
			C.Real(33, WolfViewNow(W), Out[3]);
			C.Int(34, W.WeatherKind, static_cast<std::int32_t>(Out[4]));
			C.Real(35, W.WeatherIntensity, Out[5]);
			C.Real(36, W.Weather.Sight, Out[6]);
			C.Real(37, W.Weather.Hear, Out[7]);
			C.Real(38, W.Weather.DeerSpeed, Out[8]);
			C.Real(39, W.Weather.WolfSpeed, Out[9]);
			Detail::Close(R, c, C);
		}
		return R;
	}

	/**
	 * 지각: 지역 날씨 세계에 t 를 넣어 어둠·탐지 반경을 정하고, 늑대 상태로 Detail::BuildThreatInputs (발소리 × 사슴 청각) → 장면의 잠을 덮어 PerceiveThreats.
	 * 보이는 수·가장 가까운 거리·쌍마다 알아챔이 파이썬 _geometry 와 같아야 한다. Changed = 날씨 없는 반경·발소리로 알아챔이 달라지는 쌍.
	 */
	inline FReport CheckPerception()
	{
		FReport R;
		FWorldState W;
		std::vector<FThreatAgent> Agents(static_cast<size_t>(G::kPercM));
		std::vector<FThreatAgent*> Ptrs(static_cast<size_t>(G::kPercM));
		std::vector<O3::FThreatInput> Plain(static_cast<size_t>(G::kPercM));
		std::int32_t Key = -1;
		for (std::int32_t k = 0; k < G::kPercScenes; ++k)
		{
			const double* Sc = G::kPercScene + 4 * k;
			const std::int32_t Region = static_cast<std::int32_t>(Sc[0]);
			if (Region != Key)
			{
				InitWorld(W, Detail::SceneWorld(Detail::RegionWeather(Region)));
				Key = Region;
			}
			W.T = static_cast<std::int64_t>(Sc[1]);
			UpdateDayNight(W);
			Detail::FCase Cs;
			Cs.Real(40, W.Dark, Sc[2]);
			Cs.Real(41, SeePredNow(W), Sc[3]);
			for (std::int32_t m = 0; m < G::kPercM; ++m)
			{
				const double* Wv = G::kPercWolf + 7 * (k * G::kPercM + m);
				FThreatAgent& A = Agents[static_cast<size_t>(m)];
				A = FThreatAgent();
				A.State.PosX = Wv[0];
				A.State.PosY = Wv[1];
				A.State.VelX = Wv[2];
				A.State.VelY = Wv[3];
				A.Last.bRunning = Wv[4] != 0.0;
				Ptrs[static_cast<size_t>(m)] = &A;
			}
			W.ExternalThreats.clear();
			EcoWorldV3::Detail::BuildThreatInputs(W, Ptrs.data(), G::kPercM);
			for (std::int32_t m = 0; m < G::kPercM; ++m)
			{
				const double* Wv = G::kPercWolf + 7 * (k * G::kPercM + m);
				O3::FThreatInput& T = W.ThreatIn[static_cast<size_t>(m)];
				T.bAsleep = Wv[5] != 0.0;   // 장면의 잠 (파이썬 pred_asleep 을 장면마다 정했다)
				Cs.Real(42, T.HearR, Wv[6]);
				O3::FThreatInput& P = Plain[static_cast<size_t>(m)];
				P = T;
				P.HearR = O3::HearingRadius(W.Config.RealismHearing, std::sqrt(Wv[2] * Wv[2] + Wv[3] * Wv[3]) / W.ObsCfg.HerbSpeed, Wv[4] != 0.0);
			}
			Detail::Close(R, k * (G::kPercN + 1), Cs);
			const double SeePred = SeePredNow(W);
			const double SeePlain = O3::SeePredRadius(W.Dark, W.ObsCfg);
			for (std::int32_t i = 0; i < G::kPercN; ++i)
			{
				const double* Dv = G::kPercDeer + 5 * (k * G::kPercN + i);
				const FVec2 Pos{Dv[0], Dv[1]};
				const FVec2 Head{Dv[2], Dv[3]};
				const O3::FThreatPerception All = O3::PerceiveThreats(Pos, Head, SeePred, Dv[4], Dv[4], W.ThreatIn.data(), G::kPercM, W.ObsCfg);
				const std::int32_t Row = k * G::kPercN + i;
				Detail::FCase C;
				C.Int(43, All.PredCount, G::kPercCount[Row]);
				const double DMin = G::kPercDMin[Row];
				if (DMin >= 0.0)
				{
					C.Real(44, All.DPredMin, DMin);
				}
				else
				{
					C.Int(44, All.Nearest, -1);
				}
				for (std::int32_t m = 0; m < G::kPercM; ++m)
				{
					const bool bVis = O3::PerceiveThreats(Pos, Head, SeePred, Dv[4], Dv[4], &W.ThreatIn[static_cast<size_t>(m)], 1, W.ObsCfg).PredCount == 1;
					const bool bPlain = O3::PerceiveThreats(Pos, Head, SeePlain, Dv[4], Dv[4], &Plain[static_cast<size_t>(m)], 1, W.ObsCfg).PredCount == 1;
					C.Int(45, bVis ? 1 : 0, G::kPercVis[Row * G::kPercM + m]);
					R.Count += bVis ? 1 : 0;
					R.Changed += bVis != bPlain ? 1 : 0;
				}
				Detail::Close(R, k * (G::kPercN + 1) + 1 + i, C);
			}
		}
		return R;
	}

	/** 한 스텝 장면의 위협 설정 (PackGoldenCheckV3.h StepConfig 와 같은 꼴: 제자리 식사 38·포만 450·은신처 안전과 진입 금지·무리 켬, 낮). */
	inline T3::FThreatConfig StepConfig()
	{
		T3::FThreatConfig Cfg;
		Cfg.PredEatCd = G::kStepEatCd;
		Cfg.bEatInPlace = true;
		Cfg.bWildSatiation = true;
		Cfg.SatSteps = G::kStepSatSteps;
		Cfg.bShelterSafe = true;
		Cfg.bShelterBlock = true;
		Cfg.Pack.bEnabled = true;
		return Cfg;
	}

	/**
	 * 한 스텝 장면: EcoWorldV3 C2 와 같은 순서 — 모든 늑대 PackPeek → PackGoals → 늑대 순서로 Step. 날씨 배수 = WeatherMults(거울 계수, 장면 날씨·세기)를
	 * In.WeatherViewMult·WeatherSpeedMult 로 (무리 미리 보기도 같은 입력). Changed = 배수 1 로 돌리면 자리·표적이 다른 늑대.
	 */
	inline FReport CheckSteps()
	{
		FReport R;
		const T3::FThreatConfig Cfg = StepConfig();
		const std::int32_t M = G::kStepWolves;
		const std::int32_t N = G::kStepPrey;
		const std::int32_t K = G::kStepCoverCount;
		const FWeatherConfig Wx;   // 거울 계수 (기본값 — CheckConfig 가 본다)
		std::vector<double> Discs;
		for (std::int32_t k = 0; k < K; ++k)
		{
			Discs.push_back(G::kStepCover[3 * k]);
			Discs.push_back(G::kStepCover[3 * k + 1]);
			Discs.push_back(G::kStepCover[3 * k + 2] + G::kStepWolfMargin);
		}
		std::vector<T3::FThreatSpec> Specs;
		for (std::int32_t m = 0; m < M; ++m)
		{
			Specs.push_back(m % 2 == 0 ? T3::MakeStalkerSpec(G::kStepPredSpeedMult, false, Cfg) : T3::MakeChaserSpec(G::kStepPredSpeedMult, false, false, Cfg));
		}
		std::vector<T3::FPreyView> Prey(static_cast<size_t>(N));
		std::vector<T3::FThreatState> States(static_cast<size_t>(M));
		std::vector<T3::FPackWolf> Wolves(static_cast<size_t>(M));
		std::vector<T3::FPackGoal> Goals(static_cast<size_t>(M));
		std::vector<T3::FPackWolf> WolvesPlain(static_cast<size_t>(M));
		std::vector<T3::FPackGoal> GoalsPlain(static_cast<size_t>(M));
		for (std::int32_t s = 0; s < G::kStepScenes; ++s)
		{
			const double* Ws = G::kStepWeather + 4 * s;
			const FWeatherMults Mu = WeatherMults(Wx, static_cast<std::int32_t>(Ws[0]), Ws[1]);
			Detail::FCase Cw;
			Cw.Real(50, T3::FThreatConfig().PredViewR * Mu.Sight, Ws[2]);
			Cw.Real(51, Mu.WolfSpeed, Ws[3]);
			Detail::Close(R, s * (M + 1), Cw);
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Pd = G::kStepPreyIn + 5 * (s * N + i);
				T3::FPreyView& V = Prey[static_cast<size_t>(i)];
				V = T3::FPreyView();
				V.X = Pd[0];
				V.Y = Pd[1];
				V.MoveX = Pd[2];
				V.MoveY = Pd[3];
				V.bInCover = Pd[4] != 0.0;
				V.Behavior = T3::kPreyGraze;
			}
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wd = G::kStepWolfIn + 5 * (s * M + m);
				const std::int32_t* Wi = G::kStepWolfInI + 4 * (s * M + m);
				T3::FThreatState& T = States[static_cast<size_t>(m)];
				T = T3::FThreatState();
				T.PosX = Wd[0];
				T.PosY = Wd[1];
				T.HeadX = Wd[2];
				T.HeadY = Wd[3];
				T.Cooldown = Wi[0];
				T.SatLeft = Wi[1];
				T.StalkState = static_cast<T3::EStalkState>(Wi[2]);
				T.StalkLeft = Wi[3];
			}
			T3::FThreatStepInput Base;
			Base.Prey = Prey.data();
			Base.NumPrey = N;
			Base.Dark = 0.0;
			Base.WorldSize = G::kStepWorldSize;
			Base.Discs = Discs.data();
			Base.NumDiscs = K;
			T3::FThreatStepInput Plain = Base;   // 날씨 없음 (Changed 세기)
			Base.WeatherViewMult = Mu.Sight;
			Base.WeatherSpeedMult = Mu.WolfSpeed;
			for (std::int32_t m = 0; m < M; ++m)
			{
				Wolves[static_cast<size_t>(m)] = T3::PackPeek(Specs[static_cast<size_t>(m)], States[static_cast<size_t>(m)], Base, Cfg);
				WolvesPlain[static_cast<size_t>(m)] = T3::PackPeek(Specs[static_cast<size_t>(m)], States[static_cast<size_t>(m)], Plain, Cfg);
			}
			T3::PackGoals(Wolves.data(), M, Prey.data(), N, G::kStepCover, K, G::kStepWolfMargin, G::kStepWorldSize, Cfg.Pack, Goals.data());
			T3::PackGoals(WolvesPlain.data(), M, Prey.data(), N, G::kStepCover, K, G::kStepWolfMargin, G::kStepWorldSize, Cfg.Pack, GoalsPlain.data());
			for (std::int32_t m = 0; m < M; ++m)
			{
				const T3::FPackGoal& Gm = Goals[static_cast<size_t>(m)];
				T3::FThreatStepInput In = Base;
				In.WanderTurn = G::kStepWolfIn[5 * (s * M + m) + 4];
				In.bPackHelp = Gm.bHelp;
				In.bPackWait = Gm.bWait;
				In.PackDirX = Gm.DirX;
				In.PackDirY = Gm.DirY;
				T3::FThreatState TP = States[static_cast<size_t>(m)];
				T3::FThreatState& T = States[static_cast<size_t>(m)];
				const T3::FThreatStepResult Res = T3::Step(Specs[static_cast<size_t>(m)], T, In, Cfg);
				{
					const T3::FPackGoal& Gp = GoalsPlain[static_cast<size_t>(m)];
					T3::FThreatStepInput Ip = Plain;
					Ip.WanderTurn = In.WanderTurn;
					Ip.bPackHelp = Gp.bHelp;
					Ip.bPackWait = Gp.bWait;
					Ip.PackDirX = Gp.DirX;
					Ip.PackDirY = Gp.DirY;
					const T3::FThreatStepResult Rp = T3::Step(Specs[static_cast<size_t>(m)], TP, Ip, Cfg);
					R.Changed += (TP.PosX != T.PosX || TP.PosY != T.PosY || Rp.Target != Res.Target) ? 1 : 0;
				}
				const double* Od = G::kStepWolfOut + 4 * (s * M + m);
				const std::int32_t* Oi = G::kStepWolfOutI + 10 * (s * M + m);
				Detail::FCase C;
				C.Real(60, T.PosX, Od[0]);
				C.Real(61, T.PosY, Od[1]);
				C.Real(62, T.HeadX, Od[2]);
				C.Real(63, T.HeadY, Od[3]);
				C.Int(64, T.Cooldown, Oi[0]);
				C.Int(65, T.SatLeft, Oi[1]);
				C.Int(66, static_cast<std::int32_t>(T.StalkState), Oi[2]);
				C.Int(67, T.StalkLeft, Oi[3]);
				C.Int(68, Gm.bHelp ? 1 : 0, Oi[4]);
				C.Int(69, Gm.bWait ? 1 : 0, Oi[5]);
				C.Int(70, Gm.bDoor ? 1 : 0, Oi[6]);
				C.Int(71, Gm.Prey, Oi[7]);
				C.Int(72, Res.Target, Oi[8]);
				C.Int(73, Res.Caught, Oi[9]);
				R.Count += Res.Caught >= 0 ? 1 : 0;
				Detail::Close(R, s * (M + 1) + 1 + m, C);
			}
		}
		return R;
	}

	/** 끔·맑음 시험의 기준 루프 세계: 평면 맵 기본값 (무대 100, 사슴 Deer, 위협 6, 낮밤 900) + 날씨 Wx. */
	inline FWorldConfig RefConfig(const FWeatherConfig& Wx, std::int32_t Deer = 48)
	{
		FWorldConfig C;
		C.NumHerbivores = Deer;
		C.Seed = 20000;
		C.Covers = QuadCovers(C.WorldSize, 6.0);
		C.RealismHearing.bEnabled = true;   // 발소리 줄도 지나가게 (비 청각 배수 1 이면 같은 값)
		C.Weather = Wx;
		return C;
	}

	/** 두 기준 루프의 논리 상태가 비트 단위로 같은가 (사슴 몸·행동·관측, 위협 상태). */
	inline bool SameState(const FReferenceWorld& A, const FReferenceWorld& B)
	{
		if (A.NumHerbivores() != B.NumHerbivores() || A.NumThreats() != B.NumThreats() || A.World.PredEma != B.World.PredEma)
		{
			return false;
		}
		for (std::int32_t i = 0; i < A.NumHerbivores(); ++i)
		{
			const FHerbBody& X = A.Bodies[static_cast<size_t>(i)];
			const FHerbBody& Y = B.Bodies[static_cast<size_t>(i)];
			if (X.Pos.X != Y.Pos.X || X.Pos.Y != Y.Pos.Y || X.Head.X != Y.Head.X || X.Head.Y != Y.Head.Y || X.Energy != Y.Energy
				|| X.DeathCause != Y.DeathCause || X.Generation != Y.Generation || A.Reps[static_cast<size_t>(i)].Behavior != B.Reps[static_cast<size_t>(i)].Behavior
				|| A.Decisions[static_cast<size_t>(i)].Request != B.Decisions[static_cast<size_t>(i)].Request)
			{
				return false;
			}
			for (std::int32_t o = 0; o < O3::kObsDim; ++o)
			{
				if (A.Perceptions[static_cast<size_t>(i)].Obs[o] != B.Perceptions[static_cast<size_t>(i)].Obs[o])
				{
					return false;
				}
			}
		}
		for (std::int32_t m = 0; m < A.NumThreats(); ++m)
		{
			const T3::FThreatState& X = A.Threats[static_cast<size_t>(m)].State;
			const T3::FThreatState& Y = B.Threats[static_cast<size_t>(m)].State;
			if (X.PosX != Y.PosX || X.PosY != Y.PosY || X.HeadX != Y.HeadX || X.HeadY != Y.HeadY || X.Cooldown != Y.Cooldown
				|| X.StalkState != Y.StalkState || X.StalkLeft != Y.StalkLeft)
			{
				return false;
			}
		}
		return true;
	}

	/**
	 * 끄면 그대로: 기준 루프 Steps 스텝 동안 (1) 날씨 끔, (2) 날씨 켬 + 맑음, (3) 날씨 켬 + 비 세기 1 인데 배수가 모두 1, (4) 켬 + 눈 세기 0 이 스텝마다
	 * 비트 단위로 같다 (파이썬 tests/test_wild3_weather.py '맑은 지역·배수 1 인 비 = 나무 거울' 과 같은 시험). Count = 비교한 스텝.
	 */
	inline FReport CheckOffIdentical(std::int32_t Steps = 240)
	{
		FReport R;
		FWeatherConfig Clear;
		Clear.bEnabled = true;
		FWeatherConfig RainOne;
		RainOne.bEnabled = true;
		RainOne.Kind = kWeatherRain;
		RainOne.Intensity = 1.0;
		RainOne.RainSight = 1.0;
		RainOne.RainHear = 1.0;
		FWeatherConfig SnowZero;
		SnowZero.bEnabled = true;
		SnowZero.Kind = kWeatherSnow;
		SnowZero.Intensity = 0.0;
		FReferenceWorld Off, A, B, C3;
		Off.Init(RefConfig(FWeatherConfig()));
		A.Init(RefConfig(Clear));
		B.Init(RefConfig(RainOne));
		C3.Init(RefConfig(SnowZero));
		Detail::FCase C;
		C.Int(80, SameState(Off, A) && SameState(Off, B) && SameState(Off, C3) ? 1 : 0, 1);
		for (std::int32_t t = 0; t < Steps && C.Field < 0; ++t)
		{
			Off.StepOnce();
			A.StepOnce();
			B.StepOnce();
			C3.StepOnce();
			C.Int(80, SameState(Off, A) && SameState(Off, B) && SameState(Off, C3) ? 1 : 0, 1);
			++R.Count;
		}
		Detail::Close(R, 0, C);
		return R;
	}

	/**
	 * 첫 스텝 눈 이동: 시야·청각 배수 1·visibility 에 안 실음(결정이 같게)이고 눈 이동만 둔 세계는 첫 스텝 사슴 변위 = 날씨 끈 세계 변위 × SnowDeerSpeed,
	 * 위협 변위 = × SnowWolfSpeed (벽에 닿지 않은 개체만, 1e-12 안 — 파이썬 '눈 첫 스텝 이동 × 0.6·× 0.85'). Count = 견준 개체.
	 */
	inline FReport CheckSnowFirstStep()
	{
		FReport R;
		FWeatherConfig Snow;
		Snow.bEnabled = true;
		Snow.Kind = kWeatherSnow;
		Snow.Intensity = 1.0;
		Snow.SnowSight = 1.0;
		Snow.SnowHear = 1.0;
		Snow.bObsVisibility = false;
		FReferenceWorld Off, S;
		Off.Init(RefConfig(FWeatherConfig()));
		S.Init(RefConfig(Snow));
		Off.StepOnce();
		S.StepOnce();
		Detail::FCase C;
		const double Size = Off.World.Config.WorldSize;
		auto Inside = [Size](double X, double Y) { return X > 0.0 && Y > 0.0 && X < Size && Y < Size; };
		for (std::int32_t i = 0; i < Off.NumHerbivores(); ++i)
		{
			const FHerbBody& X = Off.Bodies[static_cast<size_t>(i)];
			const FHerbBody& Y = S.Bodies[static_cast<size_t>(i)];
			if (X.DeathCause != kDeathNone || !Inside(X.Pos.X, X.Pos.Y) || !Inside(Y.Pos.X, Y.Pos.Y))
			{
				continue;
			}
			const double Dx = (X.Pos.X - X.PrevPos.X) * Snow.SnowDeerSpeed;
			const double Dy = (X.Pos.Y - X.PrevPos.Y) * Snow.SnowDeerSpeed;
			if (std::fabs((Y.Pos.X - Y.PrevPos.X) - Dx) > 1e-12 || std::fabs((Y.Pos.Y - Y.PrevPos.Y) - Dy) > 1e-12)
			{
				C.Int(81, 0, 1);
			}
			++R.Count;
		}
		for (std::int32_t m = 0; m < Off.NumThreats(); ++m)
		{
			const FThreatAgent& X = Off.Threats[static_cast<size_t>(m)];
			const FThreatAgent& Y = S.Threats[static_cast<size_t>(m)];
			// 사슴 자리가 달라 표적·상태 기계가 갈린 위협은 속력이 달라도 된다 — 같은 표적·같은 잠행 상태인 위협만 견준다
			if (!Inside(X.State.PosX, X.State.PosY) || !Inside(Y.State.PosX, Y.State.PosY) || X.Last.bWallHit || Y.Last.bWallHit
				|| X.Last.Target != Y.Last.Target || X.State.StalkState != Y.State.StalkState || X.State.StalkLeft != Y.State.StalkLeft)
			{
				continue;
			}
			if (std::fabs(Y.Last.Speed - X.Last.Speed * Snow.SnowWolfSpeed) > 1e-12)
			{
				C.Int(81, 0, 1);
			}
			++R.Count;
		}
		Detail::Close(R, 0, C);
		return R;
	}
}

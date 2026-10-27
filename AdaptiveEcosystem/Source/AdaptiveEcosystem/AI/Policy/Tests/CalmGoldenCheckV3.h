// v3 10-27 고침 골든 대조 — EcoRepertoire.h (GrazeCalmDir·WallKeepDir·Control 의 GRAZE 걷기), EcoWorldV3.h (UpdateWildFlight 의 거리 두기 kKeepRest,
// 이어지는 거리 두기의 방향 관성, FlightRestControl·FlightRestBand, 경계 걷기에는 먹기 걷기 고침이 없음, Step 전체)를 CalmGoldenVectorsV3.h (herbivore_rl/export_golden_v3_calm.py,
// 세계 configs/v3_wild3_calm_mirror.yaml)와 맞춘다. 사용자 10-27 '평소 사슴이 제자리에서 빙빙 돈다'·'쉬는 늑대 곁에서 멈춰 있다'.
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<cstring>`·`<vector>` 와 엔진 무관 v3 세계 헤더만). 같은 검사를 두 곳이 부른다:
//   UE 자동화 시험   Tests/EcoCalmV3Test.cpp (AdaptiveEcosystem.Policy.V3.Calm.*)
//   g++ 하네스       herbivore_rl/tests/cpp/calm_v3_main.cpp (herbivore_rl/tests/test_calm_golden_v3.py)
// 모든 실수 칸은 파이썬과 같은 식·같은 순서라 비트 단위로 같아야 한다 (memcmp, 지문은 sha256).
//
// 칸 번호 (FReport::FirstField):
//   정의      0 C++ 기본 끔 (FRepertoireConfig·FWildFlightConfig·FGrazeCalmConfig), 1 InitWorld 가 옮김·거부, 2 덮기 번호
//   방향      10 원래 방향 x·y, 11 나온 방향 x·y
//   제어      20 속도 x·y, 21 보행
//   덮기 장면 30 다음 덮기, 31 방향 x·y, 32 잠금 (입력에 지난 덮기 방향 — 이어지는 거리 두기의 관성)
//   B 장면    40 속도 x·y, 41 보행, 42 섭식, 43 대사, 44 시야 배수
//   기준 루프 50 시작 상태 (먹이 격자·시작 에너지·늑대 속력·설정), 51 지문, 52 기록 (잡힘·굶음·산·덮기별 사슴-스텝·띠), 53 세계 난수 (뽑은 수 = 날 수열 끝)

#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

#include "../CalmGoldenVectorsV3.h"
#include "../EcoObservationV3.h"
#include "../EcoPolicyV3Inference.h"
#include "../EcoRepertoire.h"
#include "../EcoSha256.h"
#include "../EcoThreatModel.h"
#include "../EcoWorldV3.h"

namespace EcoWorldV3::CalmCheck
{
	namespace G = EcoWorldV3::GoldenCalm;
	namespace T3 = EcoThreatV3;
	namespace R3 = EcoRepertoireV3;

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례
		std::int32_t Failures = 0;     // 어긋난 사례
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)
		std::int64_t Count0 = 0;       // 묶음마다 C++ 이 낸 수: 방향 = 원래와 다른 방향, 장면 = 거리 두기, B = 띠가 바꾼 사슴, 루프 = 거리 두기 사슴-스텝
		std::int64_t Count1 = 0;       // 방향 = 원래 방향으로 돌아간 사례, 장면 = 경계, B = 거리 두기 제어, 루프 = 띠 방향 바꿈
		std::int64_t Count2 = 0;       // 장면 = 도주, B = 멈춤, 루프 = 잡힘

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

		/** 장면 세계: 기준 루프 0 의 설정(숲 — 날씨·감지·포만·밤잠 점진화·도주 반사·거리 두기)에 사슴 kSceneN. 늑대 수는 설정 그대로(4). */
		inline void InitScene(FReferenceWorld& Ref)
		{
			FWorldConfig C;
			G::kLoopTable[0].Fill(C);
			C.NumHerbivores = G::kSceneN;
			C.Obstacles.Discs.clear();
			Ref.Init(C);
		}

		/** 장면 세계에 원판 (x, y, r — r < 0 은 빈 칸)을 넣는다. 숲 시야는 끈 채다(나무 표 비움). */
		inline void SetDiscs(FWorldState& W, const double* D, std::int32_t K)
		{
			W.Config.Obstacles.Discs.clear();
			W.Config.Obstacles.Foliage.Trees.clear();
			for (std::int32_t k = 0; k < K; ++k)
			{
				if (D[3 * k + 2] >= 0.0)
				{
					W.Config.Obstacles.Discs.insert(W.Config.Obstacles.Discs.end(), {D[3 * k], D[3 * k + 1], D[3 * k + 2]});
				}
			}
		}
	}

	/** 정의: C++ 기본은 끔(파이썬 features.OPTIONAL_KEYS 끔 값), InitWorld 가 계수를 W.RepCfg 로 옮기고 음수·무한·도주 반사 끔은 거부, 덮기 번호. */
	inline FReport CheckDefinitions()
	{
		FReport R;
		Detail::FCase C;
		const R3::FRepertoireConfig Rc;
		C.Ok(0, Rc.GrazeEdgeR == 0.0 && Rc.GrazeEdgeW == 0.0 && Rc.GrazeInertia == 0.0 && Rc.GrazeWallMargin == 0.0 && !R3::GrazeCalmOn(Rc)
					&& !R3::GrazeCalmOn(R3::kR1bConfig));
		const FWildFlightConfig Fc;
		C.Ok(0, !Fc.bRestKeep && Fc.RestKeepMargin == 2.0 && Fc.RestKeepBand == 0.0 && !Fc.bRestKeepAsleep);
		const FGrazeCalmConfig Gc;
		C.Ok(0, Gc.EdgeR == 0.0 && Gc.EdgeW == 0.0 && Gc.Inertia == 0.0 && Gc.WallMargin == 0.0);
		C.Ok(2, kKeepRest == G::kKeepRestCode && kNumKeepModes == kKeepRest + 1);
		{
			FWorldConfig Wc;
			G::kLoopTable[0].Fill(Wc);
			FWorldState W;
			InitWorld(W, Wc);
			C.Ok(1, W.RepCfg.GrazeEdgeR == G::kGrazeEdgeR && W.RepCfg.GrazeEdgeW == G::kGrazeEdgeW && W.RepCfg.GrazeInertia == G::kGrazeInertia
						&& W.RepCfg.GrazeWallMargin == G::kGrazeWallMargin && R3::GrazeCalmOn(W.RepCfg));
			C.Ok(1, W.Config.WildFlight.bRestKeep == G::kRestKeep && W.Config.WildFlight.RestKeepMargin == G::kRestKeepMargin
						&& W.Config.WildFlight.RestKeepBand == G::kRestKeepBand && W.Config.WildFlight.bRestKeepAsleep == G::kRestKeepAsleep);
			FWorldConfig Bad = Wc;
			Bad.GrazeCalm.EdgeR = -1.0;
			Bad.GrazeCalm.Inertia = std::numeric_limits<double>::infinity();
			Bad.WildFlight.RestKeepBand = -2.0;
			InitWorld(W, Bad);
			C.Ok(1, W.RepCfg.GrazeEdgeR == 0.0 && W.RepCfg.GrazeInertia == 0.0 && !W.Config.WildFlight.bRestKeep);
			FWorldConfig NoFlight = Wc;
			NoFlight.WildFlight.bEnabled = false;
			InitWorld(W, NoFlight);
			C.Ok(1, !W.Config.WildFlight.bRestKeep && !W.Config.WildFlight.bRestKeepAsleep);
		}
		Detail::Close(R, 0, C);
		return R;
	}

	/** 방향 사례: GrazeCalmDir(raw, normalize(raw), 자리, heading, 무대, 계수) = 파이썬 `graze_calm_dir`. */
	inline FReport CheckDirections()
	{
		FReport R;
		for (std::int32_t k = 0; k < G::kDirCases; ++k)
		{
			const double* In = G::kDirIn + 10 * k;
			const double* Out = G::kDirOut + 4 * k;
			R3::FRepertoireConfig Cfg;
			Cfg.GrazeEdgeR = In[0];
			Cfg.GrazeEdgeW = In[1];
			Cfg.GrazeInertia = In[2];
			Cfg.GrazeWallMargin = In[3];
			const R3::FVec2 Raw{In[4], In[5]};
			const R3::FVec2 Head{In[6], In[7]};
			const R3::FVec2 Pos{In[8], In[9]};
			const R3::FVec2 Base = R3::Normalize(Raw);
			Detail::FCase C;
			C.Bits(10, Base.X, Out[0]);
			C.Bits(10, Base.Y, Out[1]);
			const R3::FVec2 D = R3::GrazeCalmDir(Raw, Base, Pos, Head, G::kDirSize, Cfg);
			C.Bits(11, D.X, Out[2]);
			C.Bits(11, D.Y, Out[3]);
			Detail::Close(R, k, C);
			const bool bSame = D.X == Base.X && D.Y == Base.Y;
			R.Count0 += bSame ? 0 : 1;
			R.Count1 += bSame && R3::GrazeCalmOn(Cfg) ? 1 : 0;
		}
		R.Count2 = G::kDirHand;
		return R;
	}

	/** 제어 사례: R3::Control (GRAZE, 계수 켬 — 설정 값) = 파이썬 `repertoire.control` 의 속도·보행. */
	inline FReport CheckControl()
	{
		FReport R;
		R3::FRepertoireConfig Cfg;
		Cfg.GrazeEdgeR = G::kGrazeEdgeR;
		Cfg.GrazeEdgeW = G::kGrazeEdgeW;
		Cfg.GrazeInertia = G::kGrazeInertia;
		Cfg.GrazeWallMargin = G::kGrazeWallMargin;
		for (std::int32_t k = 0; k < G::kCtlCases; ++k)
		{
			const double* V = G::kCtlIn + 10 * k;
			R3::FRepState S;
			S.Behavior = R3::kGraze;
			R3::FControlInput In;
			In.FoodGrad = {V[0], V[1]};
			In.ToCentroid = {V[2], V[3]};
			In.Separation = {V[4], V[5]};
			In.Pos = {V[6], V[7]};
			In.Head = {V[8], V[9]};
			In.WorldSize = G::kCtlSize;
			In.bFoodOk = G::kCtlFoodOk[k] != 0;
			const R3::FControlOutput O = R3::Control(S, In, Cfg);
			Detail::FCase C;
			C.Bits(20, O.Velocity.X, G::kCtlVel[2 * k]);
			C.Bits(20, O.Velocity.Y, G::kCtlVel[2 * k + 1]);
			C.Int(21, O.Gait, G::kCtlGait[k]);
			Detail::Close(R, k, C);
		}
		return R;
	}

	/** 덮기 장면: 장면 상태 → ObserveAll → UpdateWildFlight = 파이썬 `_geometry` → `_wf_update` 의 다음 덮기·방향·잠금 (사슴마다 사례 하나). */
	inline FReport CheckScenes()
	{
		FReport R;
		FReferenceWorld Ref;
		Detail::InitScene(Ref);
		FWorldState& W = Ref.World;
		const std::int32_t N = G::kSceneN;
		const std::int32_t M = G::kSceneM;
		{
			Detail::FCase C;
			C.Ok(30, Ref.NumHerbivores() == N && Ref.NumThreats() == M && W.Config.WildFlight.bRestKeep);
			C.Bits(31, WolfViewNow(W), G::kSceneWolfView);
			Detail::Close(R, -1, C);
		}
		for (std::int32_t k = 0; k < G::kScenes; ++k)
		{
			W.Config.Covers.clear();
			for (std::int32_t c = 0; c < 2; ++c)
			{
				const double* Cv = G::kSceneCover + (k * 2 + c) * 3;
				if (Cv[2] >= 0.0)
				{
					W.Config.Covers.push_back({Cv[0], Cv[1], Cv[2]});
				}
			}
			Detail::SetDiscs(W, G::kSceneDisc + k * 3 * 3, 3);
			W.Dark = G::kSceneDark[k];
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wv = G::kSceneWolf + (k * M + m) * 9;
				FThreatAgent& A = Ref.Threats[static_cast<size_t>(m)];
				A.State.PosX = Wv[0];
				A.State.PosY = Wv[1];
				A.State.VelX = Wv[2];
				A.State.VelY = Wv[3];
				A.Last.bRunning = Wv[4] != 0.0;
				A.State.Cooldown = static_cast<std::int32_t>(Wv[5]);
				A.State.SatLeft = static_cast<std::int32_t>(Wv[6]);
				A.State.bAsleep = Wv[7] != 0.0;
				A.Last.Target = static_cast<std::int32_t>(Wv[8]);
				A.Last.bHasTarget = A.Last.Target >= 0;
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Dv = G::kSceneDeerIn + (k * N + i) * 10;
				FHerbBody& B = Ref.Bodies[static_cast<size_t>(i)];
				B.Pos = {Dv[0], Dv[1]};
				B.Head = {Dv[2], Dv[3]};
				B.DeathCause = Dv[7] != 0.0 ? kDeathCaught : kDeathNone;
				B.bRespawned = false;
				R3::FRepState& S = Ref.Reps[static_cast<size_t>(i)];
				S.SeeMult = Dv[4];
				S.SeeMultLast = Dv[4];
				S.LockLeft = static_cast<std::int32_t>(Dv[6]);
				FHerbDecision& D = Ref.Decisions[static_cast<size_t>(i)];
				D.KeepActive = static_cast<std::int32_t>(Dv[5]);
				D.KeepMode = D.KeepActive;
				D.KeepDir = {Dv[8], Dv[9]};   // 지난 덮기 방향 (이어지는 거리 두기의 관성 kRestKeepInertia — 10-27 적대적 검토)
				D.Route = kRouteNone;
			}
			ObserveAll(W, Ref.Views.data(), N, Ref.ThreatPtrs.data(), M);
			EcoWorldV3::Detail::UpdateWildFlight(W, Ref.Views.data(), N, Ref.ThreatPtrs.data(), M);
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* O = G::kSceneDeerOut + (k * N + i) * 4;
				const FHerbDecision& D = Ref.Decisions[static_cast<size_t>(i)];
				Detail::FCase C;
				C.Int(30, D.KeepMode, static_cast<std::int64_t>(O[0]));
				C.Bits(31, D.KeepDir.X, O[1]);
				C.Bits(31, D.KeepDir.Y, O[2]);
				C.Int(32, Ref.Reps[static_cast<size_t>(i)].LockLeft, static_cast<std::int64_t>(O[3]));
				Detail::Close(R, k * N + i, C);
				R.Count0 += D.KeepMode == kKeepRest ? 1 : 0;
				R.Count1 += D.KeepMode == kKeepAlert ? 1 : 0;
				R.Count2 += D.KeepMode == kKeepPanic ? 1 : 0;
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				Ref.Bodies[static_cast<size_t>(i)].DeathCause = kDeathNone;
			}
		}
		return R;
	}

	/** B 장면: 덮기·제어 출력을 놓고 FlightRestControl → FlightRestBand = 파이썬 `_wf_rest_control` → `_wf_rest_band` (산 사슴만 — 통합 모드의 Step 처럼). */
	inline FReport CheckBScenes()
	{
		FReport R;
		FReferenceWorld Ref;
		Detail::InitScene(Ref);
		FWorldState& W = Ref.World;
		const std::int32_t N = G::kSceneN;
		const std::int32_t M = G::kSceneM;
		for (std::int32_t k = 0; k < G::kBScenes; ++k)
		{
			Detail::SetDiscs(W, G::kBDisc + k * 3 * 3, 3);
			W.Dark = G::kBDark[k];
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wv = G::kBWolf + (k * M + m) * 5;
				FThreatAgent& A = Ref.Threats[static_cast<size_t>(m)];
				A.State.PosX = Wv[0];
				A.State.PosY = Wv[1];
				A.State.Cooldown = static_cast<std::int32_t>(Wv[2]);
				A.State.SatLeft = static_cast<std::int32_t>(Wv[3]);
				A.State.bAsleep = Wv[4] != 0.0;
			}
			const std::int64_t Turn0 = W.Stats.RestBandTurnSteps;
			const std::int64_t Stop0 = W.Stats.RestBandStopSteps;
			for (std::int32_t i = 0; i < N; ++i)
			{
				const double* Dv = G::kBDeerIn + (k * N + i) * 17;
				const double* O = G::kBDeerOut + (k * N + i) * 6;
				const FHerbView& H = Ref.Views[static_cast<size_t>(i)];
				H.Body->Pos = {Dv[0], Dv[1]};
				H.Body->Head = {Dv[2], Dv[3]};
				H.Decision->KeepActive = static_cast<std::int32_t>(Dv[4]);
				H.Decision->KeepDir = {Dv[5], Dv[6]};
				H.Rep->Behavior = static_cast<std::int32_t>(Dv[7]);
				R3::FControlOutput& Ctl = *H.Control;
				Ctl.Velocity = {Dv[8], Dv[9]};
				Ctl.Gait = static_cast<std::int32_t>(Dv[10]);
				Ctl.EatMult = Dv[11];
				Ctl.DrainMult = Dv[12];
				Ctl.SeeMult = Dv[13];
				R3::FControlInput In;
				In.Separation = {Dv[14], Dv[15]};
				const bool bAlive = Dv[16] != 0.0;
				if (bAlive)
				{
					const bool bRestCtl = H.Decision->KeepActive == kKeepRest && H.Rep->Behavior == R3::kGraze
										  && (H.Decision->KeepDir.X != 0.0 || H.Decision->KeepDir.Y != 0.0);
					R.Count1 += bRestCtl ? 1 : 0;
					EcoWorldV3::Detail::FlightRestControl(W, H, In);
					EcoWorldV3::Detail::FlightRestBand(W, H, Ref.ThreatPtrs.data(), M);
				}
				Detail::FCase C;
				C.Bits(40, Ctl.Velocity.X, O[0]);
				C.Bits(40, Ctl.Velocity.Y, O[1]);
				C.Int(41, Ctl.Gait, static_cast<std::int64_t>(O[2]));
				C.Bits(42, Ctl.EatMult, O[3]);
				C.Bits(43, Ctl.DrainMult, O[4]);
				C.Bits(44, Ctl.SeeMult, O[5]);
				Detail::Close(R, k * N + i, C);
			}
			R.Count0 += W.Stats.RestBandTurnSteps - Turn0;
			R.Count2 += W.Stats.RestBandStopSteps - Stop0;
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
			const G::FLoopTable* T = nullptr;
			std::int64_t Draws = 0;               // 날 수열에서 뽑은 수
			bool bRngOverflow = false;
			std::vector<std::uint8_t> Bytes;      // 지문 바이트 (재사용)
		};

		inline std::uint64_t RawHook(void* User)
		{
			FLoopWorld& L = *static_cast<FLoopWorld*>(User);
			if (L.Draws >= L.T->RawCount)
			{
				L.bRngOverflow = true;
				return 0;
			}
			return L.T->Raw[L.Draws++];
		}

		/**
		 * 시작 상태 (EcoV3Eval.cpp Init 과 같다): 설정(루프 표 Fill — bOn 거짓이면 두 고침만 끈다, bJunk 면 끈 거리 두기 칸에 엉뚱한 여유·띠·자는 늑대),
		 * 먹이 격자, 사슴 입양(슬롯 키·파이썬 값 그대로), 늑대 입양, 날 난수, 내장 망 R1b(관측 18)로 첫 관측·첫 요청.
		 */
		inline void Init(FLoopWorld& L, const G::FLoopTable& T, bool bOn, bool bJunk, FCase& C)
		{
			L.T = &T;
			FWorldConfig Cfg;
			T.Fill(Cfg);
			C.Ok(50, Cfg.WildFlight.bRestKeep && Cfg.GrazeCalm.EdgeR == G::kGrazeEdgeR && Cfg.GrazeCalm.Inertia == G::kGrazeInertia);
			Cfg.Covers.clear();
			for (std::int32_t k = 0; k < T.CoverCount; ++k)
			{
				Cfg.Covers.push_back({T.Covers[3 * k], T.Covers[3 * k + 1], T.Covers[3 * k + 2]});
			}
			Cfg.Obstacles.Discs.assign(T.Discs, T.Discs + 3 * T.DiscCount);
			Cfg.Obstacles.Foliage.Trees.clear();
			if (!bOn)
			{
				Cfg.GrazeCalm = FGrazeCalmConfig();
				Cfg.WildFlight.bRestKeep = false;
				if (bJunk)
				{
					// 끈 거리 두기의 칸은 읽지 않는다: 엉뚱한 여유·띠·자는 늑대여도 세계가 같아야 한다
					Cfg.WildFlight.RestKeepMargin = 50.0;
					Cfg.WildFlight.RestKeepBand = 99.0;
					Cfg.WildFlight.bRestKeepAsleep = true;
				}
			}
			InitWorld(L.W, Cfg);
			SetModelAllowed(L.W, EcoPolicyV3::kAllowedMask);
			FFoodGrid& Fg = L.W.Food;
			C.Ok(50, Fg.Gw == T.Gw && Fg.Cell == T.Cell && static_cast<std::int64_t>(T.Gw) * T.Gw == T.Cells);
			Fg.Cap.assign(T.Cap, T.Cap + T.Cells);
			Fg.Food.assign(T.Food, T.Food + T.Cells);
			Fg.Regen.assign(T.Regen, T.Regen + T.Cells);
			Fg.Cap0 = Fg.Cap;
			const std::int32_t N = T.N;
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
				const double* Dv = T.Deer + 6 * i;
				const size_t k = static_cast<size_t>(i);
				const FHerbView H{&L.Reps[k], &L.Dec[k], &L.Bodies[k], &L.Perc[k], &L.Ctl[k]};
				const FVec2 P{Dv[0], Dv[1]};
				const FVec2 Hd{Dv[2], Dv[3]};
				C.Ok(50, Dv[4] == L.W.RepCfg.InitEnergy);
				AdoptHerb(L.W, H, P, Hd, R3::MakeAgentKey(static_cast<std::uint32_t>(i), 0));
				H.Body->Pos = P;   // 파이썬 값 그대로 (AdoptHerb 는 heading 을 다시 정규화한다)
				H.Body->PrevPos = P;
				H.Body->Head = Hd;
				H.Body->Slot = static_cast<std::uint32_t>(i);
				H.Body->Reserve = Dv[5];
				H.Body->ReproCd = T.DeerRepro[i];
				L.Live.push_back(H);
				L.LiveSlot.push_back(i);
			}
			const std::int32_t M = T.M;
			L.Threats.assign(static_cast<size_t>(M), FThreatAgent());
			L.ThreatPtrs.clear();
			for (std::int32_t m = 0; m < M; ++m)
			{
				const double* Wv = T.Wolves + 5 * m;
				const T3::FThreatSpec Spec = T.WolfStalker[m] != 0 ? T3::MakeStalkerSpec(L.W.Config.PredSpeedMult, false, L.W.ThreatCfg)
																   : T3::MakeChaserSpec(L.W.Config.PredSpeedMult, false, false, L.W.ThreatCfg);
				C.Ok(50, Spec.BaseSpeed == Wv[4]);
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

		/** 지문 (골든 생성기 머리 주석 '지문'). Alive0 = 그 스텝 첫머리에 산 슬롯. */
		inline std::uint64_t Fingerprint(FLoopWorld& L, const std::vector<std::uint8_t>& Alive0)
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
				}
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				const FHerbDecision& D = L.Dec[static_cast<size_t>(i)];
				if (L.Cause[static_cast<size_t>(i)] == 0 && D.KeepMode != kKeepPanic && D.KeepMode != kKeepShelter)
				{
					PutI(B, D.Request);
				}
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				const FHerbDecision& D = L.Dec[static_cast<size_t>(i)];
				if (L.Cause[static_cast<size_t>(i)] == 0 && (D.KeepMode == kKeepAlert || D.KeepMode == kKeepPanic || D.KeepMode == kKeepRest))
				{
					PutD(B, D.KeepDir.X);
					PutD(B, D.KeepDir.Y);
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
	 * 기준 루프 Li (루프 표 — 지역·시드): 파이썬 거울 세계와 같은 시작 상태·같은 세계 난수로 kLoopSteps 스텝 — 스텝마다 지문, kLoopEvery 스텝마다 기록 = 파이썬
	 * (두 고침 켬은 HashOn·CheckOn, 끔은 HashOff·CheckOff). bJunk = 끔 판의 끈 거리 두기 칸을 엉뚱하게 채운다 (끔이면 읽지 않아야 한다). 사례 = 지문 (0 = 시작).
	 */
	inline FReport CheckLoop(std::int32_t Li, bool bOn, bool bJunk = false)
	{
		FReport R;
		const G::FLoopTable& T = G::kLoopTable[Li];
		Detail::FLoopWorld L;
		{
			Detail::FCase C;
			Detail::Init(L, T, bOn, bJunk, C);
			const std::vector<std::uint8_t> All(static_cast<size_t>(T.N), 1);
			C.Int(51, static_cast<std::int64_t>(Detail::Fingerprint(L, All)), static_cast<std::int64_t>((bOn ? T.HashOn : T.HashOff)[0]));
			Detail::Close(R, 0, C);
		}
		const std::int32_t M = T.M;
		std::vector<std::uint8_t> Alive0(static_cast<size_t>(T.N), 1);
		std::int32_t Check = 0;
		for (std::int32_t t = 1; t <= G::kLoopSteps; ++t)
		{
			Detail::FCase C;
			for (size_t i = 0; i < Alive0.size(); ++i)
			{
				Alive0[i] = L.Cause[i] == 0 ? 1 : 0;
			}
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
			C.Int(51, static_cast<std::int64_t>(Detail::Fingerprint(L, Alive0)), static_cast<std::int64_t>((bOn ? T.HashOn : T.HashOff)[t]));
			if (t % G::kLoopEvery == 0 && Check < G::kLoopChecks)
			{
				std::int64_t Got[G::kLoopCheckLen] = {};
				for (const std::int32_t Cs : L.Cause)
				{
					Got[0] += Cs == 1 ? 1 : 0;
					Got[1] += Cs == 2 ? 1 : 0;
					Got[2] += Cs == 0 ? 1 : 0;
				}
				for (std::int32_t k = 0; k < kNumKeepModes; ++k)
				{
					Got[3 + k] = L.W.Stats.KeepSteps[k];
				}
				Got[8] = L.W.Stats.RestBandTurnSteps;
				Got[9] = L.W.Stats.RestBandStopSteps;
				const std::int64_t* Want = (bOn ? T.CheckOn : T.CheckOff) + static_cast<std::int64_t>(G::kLoopCheckLen) * Check;
				for (std::int32_t j = 0; j < G::kLoopCheckLen; ++j)
				{
					C.Int(52, Got[j], Want[j]);
				}
				++Check;
			}
			Detail::Close(R, t, C);
		}
		Detail::FCase C;
		C.Ok(53, !L.bRngOverflow && L.Draws == T.RawCount);
		C.Int(52, Check, G::kLoopChecks);
		C.Int(52, L.W.Stats.MaskViolations, 0);
		Detail::Close(R, G::kLoopSteps + 1, C);
		R.Count0 = L.W.Stats.KeepSteps[kKeepRest];
		R.Count1 = L.W.Stats.RestBandTurnSteps;
		for (const std::int32_t Cs : L.Cause)
		{
			R.Count2 += Cs == 1 ? 1 : 0;
		}
		return R;
	}
}

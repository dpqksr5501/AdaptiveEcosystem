// v3 두 길 두뇌(RUN·SHELTER) 골든 대조 — 엔진 함수 EcoWorldV3.h (Detail::RouteShelterGeometry·RouteStep·RouteApply·ClearRoute, FlightUpdate 의 도망 길 기록
// FFlightRouteStats·FlightRouteReportOf, 단계 함수의 bRoute 줄 전체), EcoObservationV3.h (WriteRouteObs), EcoPolicyV3Inference.h (ApplyRouteMaskRows — 마스크 판 4·5)를
// RouteGoldenVectorsV3.h (herbivore_rl/export_golden_v3_route.py, 세계 configs/v3_wild3_route_mirror.yaml)와 맞춘다. 이식 계획서 AdaptiveEcosystem/Docs/RL_Policy/
// RL_V3_ROUTE_CPP_PORT_PLAN.md 10-1 의 묶음 1~6 (+ 13-3 판 5 마스크 줄).
//
// 엔진에 의존하지 않는다(`<cmath>`·`<cstdint>`·`<cstring>`·`<limits>`·`<vector>` 와 엔진 무관 v3 세계 헤더만). 같은 검사를 두 곳이 부른다:
//   g++ 하네스       herbivore_rl/tests/cpp/route_v3_main.cpp (herbivore_rl/tests/test_route_port_v3.py)
//   UE 자동화 시험   Tests/EcoRouteV3Test.cpp (AdaptiveEcosystem.Policy.V3.Route.* — 이식 다음 단계에서 더한다)
// 모든 실수 칸은 파이썬과 같은 식·같은 순서라 비트 단위로 같아야 한다 (double·float 비트, ±∞ 는 골든 kInf 표기, 지문은 sha256).
//
// 칸 번호 (FReport::FirstField):
//   정의       0 계약 상수·이름·칸 번호가 엔진 상수와 같다
//   기하       10 k*, 11 가능, 12 유지, 13 μ*, 14 e*, 15 k* 방향, 16 유지 μ, 17 유지 방향
//   길 셈 줄   20~31 정수 출력 (decide·onset·route·k·age·feas·sok·cand_k·dec_prev·invalid·refeas·keep_ok), 32~38 실수 출력 (mu·e·dir·sh·keep_mu), 39 관측 21~23
//   적용       40 결정 줄이 아님, 41 sok·cand_k, 42 적용 앞 방향, 43 길, 44 k, 45 bad_shelter, 46 길 바꿈, 47 적용 뒤 방향
//   손 장면 통계 50~61 (onsets·onset_shelter·decisions·redecide_feas·switches·invalid_shelter·picked_run·picked_shelter·choice·bad_shelter·steps_run·steps_shelter)
//   마스크     70~74 칸, 75 칸 3 열림
//   다시 난    80 지운 길 상태, 81 지운 관측(terminal_obs 0), 82 다시 난 뒤 상태 (도주면 시작 결정 — 파이썬 부활 세계, C++ 은 부활 칸에 덮기가 없다: 계획서 12절 질문 3)
//   관측 사례  85
//   도망 길 기록 장면 90 늑대 지난 표적(앞), 91 길 덩어리 182 칸, 92 사슴 칸 (길별 반사 스텝 넷·마지막 끝 스텝·열린 도망 FLEE 스텝)
//   기준 루프  100 시작 상태 (먹이 격자·시작 에너지·늑대 속력·실제 허용 얼기·잠 0), 101 지문, 102 기록 (잡힘·굶음·산·도망 보고 52·길 통계 12·숨은 뒤 지켜보기 5),
//              103 끝 도망 길 덩어리, 104 세계 난수 (뽑은 수 = 날 수열 끝), 105 두뇌 가중치 sha256, 106 마스크 위반·관측 칸 어긋남 0

#pragma once

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <vector>

#include "../EcoObservationV3.h"
#include "../EcoPolicyV3Inference.h"
#include "../EcoSha256.h"
#include "../EcoWorldV3.h"
#include "../RouteGoldenVectorsV3.h"

namespace EcoWorldV3::RouteCheck
{
	namespace G = EcoWorldV3::GoldenRoute;
	namespace O3 = EcoObservationV3;
	namespace P3 = EcoPolicyV3;
	namespace R3 = EcoRepertoireV3;
	namespace T3 = EcoThreatV3;
	namespace WD = EcoWorldV3::Detail;   // 엔진 길 함수 (이 파일의 Detail 과 다른 이름공간)

	struct FReport
	{
		std::int32_t Cases = 0;        // 검사한 사례
		std::int32_t Failures = 0;     // 어긋난 사례
		std::int32_t FirstCase = -1;   // 처음 어긋난 사례 번호
		std::int32_t FirstField = -1;  // 그 사례에서 처음 어긋난 칸 (머리 주석)
		std::int64_t Count0 = 0;       // 묶음마다 C++ 이 낸 수: 기하 = 가능, 줄 = 결정, 적용 = SHELTER, 마스크 = 칸 4 열림, 장면 = refled, 루프 = SHELTER 고름
		std::int64_t Count1 = 0;       // 기하 = 유지, 줄 = 무효, 적용 = 바꿈, 마스크 = 판 5 막힘, 장면 = 원판 놓침, 루프 = 길 결정
		std::int64_t Count2 = 0;       // 기하 = 벽 여유로 바뀐 방향, 줄 = 도주 줄, 마스크 = 덮기 줄, 장면 = 쫓기는 스텝, 루프 = 잡힘

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

			/** double 비트 같음 (−0 과 +0 도 가른다). ±∞ 는 골든 kInf (1e300) 표기와 견준다. */
			void D(std::int32_t Id, double Got, double Want)
			{
				if (std::isinf(Got))
				{
					Ok(Id, (Got > 0.0 ? G::kInf : -G::kInf) == Want);
					return;
				}
				Ok(Id, std::memcmp(&Got, &Want, sizeof(double)) == 0);
			}

			/** float 비트 같음. */
			void F(std::int32_t Id, float Got, float Want) { Ok(Id, std::memcmp(&Got, &Want, sizeof(float)) == 0); }
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

		constexpr std::int32_t kRowIntN = 12, kRowInN = 6, kRowOutIN = 12, kRowOutDN = 7, kApplyIntN = 8, kApplyDN = 4, kStatsN = 14;
		constexpr std::int32_t kGeoIntN = 3, kGeoInN = 6, kGeoOutIN = 3, kGeoOutDN = 7, kMaskIntN = 17, kRespawnIntN = 14;

		/** 골든 은신처 묶음 → 엔진 은신처 원. */
		inline std::vector<O3::FCoverInput> CoverSet(std::int32_t Set)
		{
			std::vector<O3::FCoverInput> Out;
			const std::int32_t First = G::kCoverSetIndex[2 * Set];
			const std::int32_t Count = G::kCoverSetIndex[2 * Set + 1];
			for (std::int32_t k = 0; k < Count; ++k)
			{
				const double* C = G::kCoverSetData + 3 * (First + k);
				Out.push_back({C[0], C[1], C[2]});
			}
			return Out;
		}

		inline std::int32_t MaskKind(const char* Name)
		{
			for (std::int32_t k = 0; k < static_cast<std::int32_t>(sizeof(G::kMaskKinds) / sizeof(G::kMaskKinds[0])); ++k)
			{
				if (std::strcmp(G::kMaskKinds[k], Name) == 0)
				{
					return k;
				}
			}
			return -1;
		}

		/** 길 셈 줄 r 의 엔진 입력·전 상태 (골든 kRowInt·kRowIn). D 는 전 상태만 채운 결정 칸, Dir 은 반사 최종 방향. */
		struct FRowSetup
		{
			FHerbDecision D;
			float RouteObs[O3::kNumRouteObs] = {0.5f, 0.5f, 0.5f};   // 지움·쓰기를 보려고 0 이 아닌 값으로 시작한다
			WD::FRouteStepInput In;
			FVec2 Dir;
			std::vector<O3::FCoverInput> Covers;
		};

		inline void SetupRow(std::int32_t r, FRowSetup& S)
		{
			const std::int32_t* I = G::kRowInt + kRowIntN * r;
			const double* In = G::kRowIn + kRowInN * r;
			S.D = FHerbDecision();
			S.D.Route = I[7];
			S.D.RouteK = I[8];
			S.D.RouteAge = I[9];
			S.D.RouteFeas = I[10];
			for (float& V : S.RouteObs)
			{
				V = 0.5f;
			}
			S.Covers = CoverSet(0);
			S.In = WD::FRouteStepInput();
			S.In.Prev = I[3];
			S.In.Next = I[4];
			S.In.P = FVec2{In[0], In[1]};
			S.In.A0 = FVec2{In[2], In[3]};
			S.In.Q = G::kTickThreat + 2 * G::kThreats * I[1];
			S.In.SBits = static_cast<std::uint64_t>(I[11]);
			S.In.M = G::kThreats;
			S.In.Covers = S.Covers.data();
			S.In.NumCovers = static_cast<std::int32_t>(S.Covers.size());
			S.In.Size = G::kWorldSize;
			S.In.Mg = G::kWallMargin;
			S.Dir = FVec2{In[4], In[5]};
		}

		/** 길 셈 줄 하나를 엔진으로 돌려 골든과 견준다. Stats 에 엔진 셈과 실행한 길(산 사슴)을 더한다. */
		inline WD::FRouteStepResult RunRow(std::int32_t r, FRowSetup& S, FRouteStats& Stats, FCase& C)
		{
			SetupRow(r, S);
			const std::int32_t* I = G::kRowInt + kRowIntN * r;
			if (I[5] != 0 && I[6] >= 0 && I[6] < kNumRoutes)
			{
				++Stats.Steps[I[6]];   // UpdateWildFlight 의 실행한 길 셈 (스텝 첫머리 산 사슴)
			}
			const WD::FRouteStepResult R = WD::RouteStep(S.D, S.RouteObs, S.In, S.Dir, Stats);
			const std::int32_t* Oi = G::kRowOutI + kRowOutIN * r;
			const double* Od = G::kRowOutD + kRowOutDN * r;
			const std::int32_t Got[kRowOutIN] = {R.bDecide ? 1 : 0, R.bOnset ? 1 : 0, S.D.Route, S.D.RouteK, S.D.RouteAge, S.D.RouteFeas,
												 S.D.bRouteSok ? 1 : 0, S.D.RouteCandK, S.D.RouteDecPrev, R.bInvalid ? 1 : 0, R.bRefeas ? 1 : 0, R.bKeepOk ? 1 : 0};
			for (std::int32_t j = 0; j < kRowOutIN; ++j)
			{
				C.Int(20 + j, Got[j], Oi[j]);
			}
			const double GotD[kRowOutDN] = {S.D.RouteMu, S.D.RouteE, S.Dir.X, S.Dir.Y, S.D.RouteShelterDir.X, S.D.RouteShelterDir.Y, R.KeepMu};
			for (std::int32_t j = 0; j < kRowOutDN; ++j)
			{
				C.D(32 + j, GotD[j], Od[j]);
			}
			for (std::int32_t j = 0; j < O3::kNumRouteObs; ++j)
			{
				C.F(39, S.RouteObs[j], G::kRowObs[3 * r + j]);
			}
			// 결정 스텝의 길은 RUN·덮기 방향은 반사 그대로, 결정 표시는 다음 A 까지 남는다
			C.Ok(31, S.D.bRouteDecide == R.bDecide);
			return R;
		}

		/** 적용 a 를 엔진으로 (그 줄을 다시 돌린 결정 칸 위에) — 다음 A 첫머리의 RouteApply. */
		inline void RunApply(std::int32_t a, FRouteStats& Stats, FCase& C)
		{
			const std::int32_t* I = G::kApplyInt + kApplyIntN * a;
			const double* Dv = G::kApplyD + kApplyDN * a;
			const std::int32_t r = I[0];
			FRowSetup S;
			FRouteStats Tmp;
			FCase Ignore;
			const WD::FRouteStepResult R = RunRow(r, S, Tmp, Ignore);
			C.Ok(40, R.bDecide);
			C.Int(41, S.D.bRouteSok ? 1 : 0, I[2]);
			C.Int(41, S.D.RouteCandK, I[3]);
			C.D(42, S.Dir.X, Dv[0]);
			C.D(42, S.Dir.Y, Dv[1]);
			// 다음 스텝 덮기 = 도주 (H 의 KeepMode), 덮기 방향 = 그 H 의 방향, 두뇌 출력 = 골든 요청
			S.D.KeepMode = kKeepPanic;
			S.D.KeepDir = S.Dir;
			S.D.RouteRequest = I[1];
			S.D.bRouteReads = true;
			const std::int64_t Bad0 = Stats.BadShelter, Sw0 = Stats.Switches;
			WD::RouteApply(S.D, true, Stats);
			C.Int(43, S.D.Route, I[4]);
			C.Int(44, S.D.RouteK, I[5]);
			C.Int(45, Stats.BadShelter - Bad0, I[6]);
			C.Int(46, Stats.Switches - Sw0, I[7]);
			C.D(47, S.D.KeepDir.X, Dv[2]);
			C.D(47, S.D.KeepDir.Y, Dv[3]);
			C.Ok(40, S.D.bCommittedRouteReads);
		}

		inline void StatsRow(const FRouteStats& S, std::int64_t Out[12])
		{
			Out[0] = S.Onsets;
			Out[1] = S.OnsetShelter;
			Out[2] = S.Decisions;
			Out[3] = S.RedecideFeas;
			Out[4] = S.Switches;
			Out[5] = S.Invalid[kRouteShelter];
			Out[6] = S.Picked[kRouteRun];
			Out[7] = S.Picked[kRouteShelter];
			Out[8] = S.Choice;
			Out[9] = S.BadShelter;
			Out[10] = S.Steps[kRouteRun];
			Out[11] = S.Steps[kRouteShelter];
		}

		/** 도망 길 덩어리 182 칸 (export_golden_v3_route.flight_route_row 순서). */
		inline void FlightRouteRow(const FFlightRouteReport& R, std::int64_t* Out)
		{
			std::int32_t k = 0;
			const std::int64_t(*Parts[3])[kNumFlightCauses] = {R.N, R.Steps, R.Contact};
			for (const auto* P : Parts)
			{
				for (std::int32_t r = 0; r < kNumFlightRouteRows; ++r)
				{
					for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
					{
						Out[k++] = P[r][c];
					}
				}
			}
			for (const std::int64_t* P : {R.DropObstacle, R.Chased, R.Hidden})
			{
				for (std::int32_t r = 0; r < kNumFlightRouteRows; ++r)
				{
					Out[k++] = P[r];
				}
			}
			Out[k++] = R.Refled;
			Out[k++] = kFlightRefleeSteps;
		}
	}

	/** 정의: 골든 상수 = 엔진 상수 (이식 계획서 10-1 의 표). */
	inline FReport CheckDefinitions()
	{
		FReport R;
		Detail::FCase C;
		C.Ok(0, G::kContractHashObs24Mask4 == P3::kContractHashObs24Mask4 && G::kObsDim == O3::kObsDimRoute && G::kRouteObsFirst == O3::kObsInPanic
					&& O3::kObsShelterReach == G::kRouteObsFirst + 1 && O3::kObsShelterEdge == G::kRouteObsFirst + 2 && G::kMaskVersion == P3::kMaskVersionRoute);
		C.Ok(0, G::kSlotRun == kRouteSlotRun && G::kSlotShelter == kRouteSlotShelter && G::kSlotReserved == kRouteSlotReserved);
		C.Ok(0, G::kRouteNone == kRouteNone && G::kRouteRun == kRouteRun && G::kRouteShelter == kRouteShelter && G::kFeasShelter == kRouteFeasShelter
					&& G::kLockSteps == kRouteLockSteps);
		C.Ok(0, G::kModeNone == kKeepNone && G::kModeAlert == kKeepAlert && G::kModePanic == kKeepPanic && G::kModeShelter == kKeepShelter);
		C.Ok(0, G::kMaxEdgeU == kRouteShelterMaxEdgeU && G::kCosMin == kRouteShelterCosMin && G::kEnterU == kRouteShelterEnterU
					&& G::kExitU == kRouteShelterExitU && G::kReachNormU == kRouteShelterReachU && G::kEdgeNormU == kRouteShelterEdgeNormU);
		C.Ok(0, G::kFsRefleeSteps == kFlightRefleeSteps && G::kFsNotLast == kFlightNotLast && G::kEps == R3::kEps
					&& G::kFlightRouteLen == 3 * kNumFlightRouteRows * kNumFlightCauses + 3 * kNumFlightRouteRows + 2);
		C.Ok(0, G::kThreatRecencyObs == P3::kThreatRecencyObs && G::kHideCoverObs == P3::kHideCoverObs && G::kObsPredCount == O3::kObsPredCount
					&& G::kObsThreatRecency == O3::kObsThreatRecency && G::kObsCoverDist == O3::kObsCoverDist);
		for (std::int32_t j = 0; j < O3::kNumRouteObs; ++j)
		{
			C.Ok(0, std::strcmp(G::kRouteObsNames[j], O3::kRouteObsNames[j]) == 0);
		}
		C.Ok(0, Detail::MaskKind("gate") >= 0 && Detail::MaskKind("hand") >= 0);
		// 기본 꺼짐 (끈 세계는 지금 그대로)
		const FWorldConfig Wc;
		const FWorldState Ws;
		const FHerbDecision Dd;
		C.Ok(0, !Wc.WildFlight.bRoute && !Ws.bFleeGate && Dd.Route == kRouteNone && Dd.RouteK == -1 && Dd.RouteRequest == -1 && !Dd.bRouteDecide);
		Detail::Close(R, 0, C);
		return R;
	}

	/** 묶음 1 SHELTER 기하: 사례마다 Detail::RouteShelterGeometry = 파이썬 `_route_shelter` (비트). 사례 = 골든 사례 번호. */
	inline FReport CheckGeometry()
	{
		using namespace Detail;
		FReport R;
		for (std::int32_t c = 0; c < G::kGeoCases; ++c)
		{
			FCase C;
			const std::int32_t* I = G::kGeoInt + kGeoIntN * c;
			const double* In = G::kGeoIn + kGeoInN * c;
			const std::vector<O3::FCoverInput> Cov = CoverSet(I[0]);
			const WD::FRouteShelterGeo Gm = WD::RouteShelterGeometry(FVec2{In[0], In[1]}, FVec2{In[2], In[3]}, G::kGeoThreat + 2 * G::kThreats * c,
															  static_cast<std::uint64_t>(G::kGeoS[c]), G::kThreats, Cov.data(),
															  static_cast<std::int32_t>(Cov.size()), I[1], In[4], In[5]);
			const std::int32_t* Oi = G::kGeoOutI + kGeoOutIN * c;
			const double* Od = G::kGeoOutD + kGeoOutDN * c;
			const bool bKeep = I[1] >= 0;
			C.Int(10, Gm.K, Oi[0]);
			C.Int(11, Gm.K >= 0 ? 1 : 0, Oi[1]);
			C.Int(12, (bKeep && Gm.bKeepOk) ? 1 : 0, Oi[2]);
			C.D(13, Gm.Mu, Od[0]);
			C.D(14, Gm.E, Od[1]);
			C.D(15, Gm.Dir.X, Od[2]);
			C.D(15, Gm.Dir.Y, Od[3]);
			C.D(16, bKeep ? Gm.KeepMu : 0.0, Od[4]);
			C.D(17, Gm.KeepDir.X, Od[5]);
			C.D(17, Gm.KeepDir.Y, Od[6]);
			Close(R, c, C);
			R.Count0 += Gm.K >= 0 ? 1 : 0;
			R.Count1 += (bKeep && Gm.bKeepOk) ? 1 : 0;
			if (Gm.K >= 0)
			{
				const double Vx = Cov[static_cast<size_t>(Gm.K)].X - In[0];
				const double Vy = Cov[static_cast<size_t>(Gm.K)].Y - In[1];
				const double Dc = std::sqrt(Vx * Vx + Vy * Vy);
				R.Count2 += (Gm.Dir.X != Vx / Dc || Gm.Dir.Y != Vy / Dc) ? 1 : 0;
			}
		}
		return R;
	}

	/** 묶음 2·3 길 셈 줄: 줄마다 Detail::RouteStep = 파이썬 `_route_step` (결정·길 상태·방향·관측 21~23 비트). 사례 = 줄 번호. */
	inline FReport CheckRows()
	{
		using namespace Detail;
		FReport R;
		FRouteStats Stats;
		for (std::int32_t r = 0; r < G::kRows; ++r)
		{
			FCase C;
			FRowSetup S;
			const WD::FRouteStepResult Rs = RunRow(r, S, Stats, C);
			Close(R, r, C);
			R.Count0 += Rs.bDecide ? 1 : 0;
			R.Count1 += Rs.bInvalid ? 1 : 0;
			R.Count2 += S.In.Next == kKeepPanic ? 1 : 0;
		}
		return R;
	}

	/** 묶음 2 적용: 적용마다 Detail::RouteApply = 파이썬 `_route_apply` (길·k·덮기 방향·bad·바꿈). 사례 = 적용 번호. */
	inline FReport CheckApplies()
	{
		using namespace Detail;
		FReport R;
		for (std::int32_t a = 0; a < G::kApplies; ++a)
		{
			FCase C;
			FRouteStats Stats;
			RunApply(a, Stats, C);
			Close(R, a, C);
			R.Count0 += Stats.Picked[kRouteShelter];
			R.Count1 += Stats.Switches;
		}
		return R;
	}

	/** 묶음 2 손 장면 길 통계: 장면마다 0 에서 엔진 셈(길 단계·적용·실행한 길)을 차례로 더한 값 = 틱마다 적은 route_stats. 사례 = 통계 줄. */
	inline FReport CheckSceneStats()
	{
		using namespace Detail;
		FReport R;
		std::int32_t s = 0;
		for (std::int32_t sc = 0; sc < G::kScenes; ++sc)
		{
			const std::int32_t R0 = G::kSceneIndex[4 * sc], Rn = G::kSceneIndex[4 * sc + 1], A0 = G::kSceneIndex[4 * sc + 2], An = G::kSceneIndex[4 * sc + 3];
			FRouteStats Stats;
			for (std::int32_t r = R0; r < R0 + Rn; ++r, ++s)
			{
				FCase C;
				FRowSetup S;
				FCase Ignore;
				RunRow(r, S, Stats, Ignore);
				for (std::int32_t a = A0; a < A0 + An; ++a)
				{
					if (G::kApplyInt[kApplyIntN * a] == r)
					{
						RunApply(a, Stats, Ignore);
					}
				}
				const std::int32_t* St = G::kStatsInt + kStatsN * s;
				C.Int(50, St[0], 0);
				std::int64_t Got[12] = {};
				StatsRow(Stats, Got);
				for (std::int32_t j = 0; j < 12; ++j)
				{
					C.Int(50 + j, Got[j], St[2 + j]);
				}
				Close(R, s, C);
			}
		}
		return R;
	}

	/** 묶음 4 마스크 판 4·5 줄: 판 2 (ComposeActionMask) → ApplyRouteMaskRows = 파이썬 action_mask (판 5 는 종류 'gate'). 사례 = 줄. */
	inline FReport CheckMask()
	{
		using namespace Detail;
		FReport R;
		const std::int32_t GateKind = MaskKind("gate");
		for (std::int32_t r = 0; r < G::kMaskRows; ++r)
		{
			FCase C;
			const std::int32_t* I = G::kMaskInt + kMaskIntN * r;
			const float* Ob = G::kMaskObs + G::kObsDim * r;
			std::uint8_t Allowed[P3::kNumBehaviors] = {};
			for (std::int32_t j = 0; j < P3::kNumBehaviors; ++j)
			{
				Allowed[j] = static_cast<std::uint8_t>(I[7 + j] != 0 ? 1 : 0);
			}
			std::uint8_t Feas[P3::kNumBehaviors] = {};
			P3::ComputeFeasibleMask(Ob, Feas);
			std::uint8_t M[P3::kNumBehaviors] = {};
			P3::ComposeActionMask(Allowed, Feas, I[4] != 0, I[5] != 0, I[6], M);
			const bool bGate = I[0] == GateKind;
			P3::ApplyRouteMaskRows(bGate ? P3::kMaskVersionRouteGate : P3::kMaskVersionRoute, I[1], I[2] != 0, I[3] == kRouteShelter,
								   Ob[O3::kObsShelterReach], I[4] != 0, M);
			for (std::int32_t j = 0; j < P3::kNumBehaviors; ++j)
			{
				C.Int(70 + j, M[j], I[12 + j]);
			}
			C.Ok(75, M[kRouteSlotReserved] == 0);
			Close(R, r, C);
			R.Count0 += M[kRouteSlotShelter] != 0 ? 1 : 0;
			R.Count1 += (bGate && I[1] == kKeepNone && I[4] != 0 && Allowed[P3::kFlee] && Feas[P3::kFlee] && M[P3::kFlee] == 0) ? 1 : 0;
			R.Count2 += (I[1] == kKeepPanic || I[1] == kKeepShelter) ? 1 : 0;
		}
		return R;
	}

	/**
	 * 다시 난 개체 (파이썬 부활 세계): 길 상태가 있던 사슴이 죽으면 엔진 죽음 분기(ClearRoute)가 길 상태·관측 21~23 을 지운다 = 파이썬 죽은 사슴 terminal_obs 0·
	 * 지운 칸. 다시 난 뒤 상태는 파이썬 규칙(도주면 시작 결정, 아니면 지움)과 맞는지만 본다 — C++ 은 부활 칸에 그 스텝 덮기가 없다(계획서 12절 질문 3). 사례 = 사건.
	 */
	inline FReport CheckRespawn()
	{
		using namespace Detail;
		FReport R;
		for (std::int32_t r = 0; r < G::kRespawnRows; ++r)
		{
			FCase C;
			const std::int32_t* I = G::kRespawnInt + kRespawnIntN * r;
			const float* Ob = G::kRespawnObs + 6 * r;
			FHerbDecision D;
			D.Route = I[4];
			D.RouteK = I[5];
			D.RouteAge = I[6];
			D.RouteFeas = I[7];
			D.bRouteDecide = true;
			D.bRouteSok = true;
			D.RouteCandK = 1;
			float Obs[O3::kNumRouteObs] = {1.0f, 0.5f, 0.5f};
			C.Ok(80, D.Route >= 0);
			WD::ClearRoute(D, Obs);
			C.Ok(80, D.Route == kRouteNone && D.RouteK == -1 && D.RouteAge == 0 && D.RouteFeas == 0 && !D.bRouteDecide && !D.bRouteSok && D.RouteCandK == -1
						 && D.RouteDecPrev == kRouteNone);
			for (std::int32_t j = 0; j < O3::kNumRouteObs; ++j)
			{
				C.F(81, Obs[j], Ob[3 + j]);
			}
			const bool bPanic = I[8] == G::kModePanic;
			const bool bCleared = I[9] == G::kRouteNone && I[10] == -1 && I[11] == 0 && I[12] == 0 && !I[13];
			const bool bOnset = I[9] == G::kRouteRun && I[10] == -1 && I[11] == 0 && I[13];
			C.Ok(82, bPanic ? bOnset : bCleared);
			C.Ok(82, (Ob[0] != 0.0f) == bPanic);
			Close(R, r, C);
		}
		return R;
	}

	/** 묶음 3 관측 세 칸 사례: EcoObservationV3::WriteRouteObs (float 비트). 사례 = 사례 번호. */
	inline FReport CheckObsCases()
	{
		FReport R;
		for (std::int32_t c = 0; c < G::kObsCases; ++c)
		{
			Detail::FCase C;
			const double Mu = G::kObsCaseIn[2 * c] >= G::kInf ? std::numeric_limits<double>::infinity() : G::kObsCaseIn[2 * c];
			float Got[O3::kNumRouteObs] = {};
			O3::WriteRouteObs(G::kObsCaseInt[2 * c] != 0, G::kObsCaseInt[2 * c + 1] != 0, Mu, G::kObsCaseIn[2 * c + 1], Got);
			for (std::int32_t j = 0; j < O3::kNumRouteObs; ++j)
			{
				C.F(85, Got[j], G::kObsCaseOut[3 * c + j]);
			}
			Detail::Close(R, c, C);
		}
		return R;
	}

	/**
	 * 묶음 6 도망 길 기록 장면: 틱마다 재료(사슴 비트·실행한 길·늑대 비트·표적)로 FlightUpdate(+ FFlightRouteStats, StepNow = kFsTickT − 1) —
	 * 늑대 지난 표적(앞) = 파이썬 _fl_tgt, 그 뒤 길 덩어리 182 칸 (FlightRouteReportOf — 끝 까닭별 by_route·잘림 포함)·사슴 칸 = 골든. 사례 = 틱.
	 */
	inline FReport CheckFlightScene()
	{
		FReport R;
		const std::int32_t N = G::kFsN, M = G::kThreats;
		FFlightStats Stats;
		FFlightRouteStats Rs;
		std::vector<FFlightTrack> Tracks(static_cast<size_t>(N));
		std::vector<FFlightTrack*> Ptrs(static_cast<size_t>(N));
		std::vector<FFlightDeerStep> Deer(static_cast<size_t>(N));
		std::vector<FFlightWolfStep> Wolves(static_cast<size_t>(M));
		for (std::int32_t i = 0; i < N; ++i)
		{
			Ptrs[static_cast<size_t>(i)] = &Tracks[static_cast<size_t>(i)];
		}
		for (std::int32_t t = 0; t < G::kFsTicks; ++t)
		{
			Detail::FCase C;
			const std::int32_t* Db = G::kFsDeer + N * t;
			const std::int32_t* Dr = G::kFsRoute + N * t;
			const std::int32_t* Wv = G::kFsWolf + 3 * M * t;
			for (std::int32_t m = 0; m < M; ++m)
			{
				const std::int32_t B = Wv[3 * m];
				C.Int(90, FlightPrevTarget(Ptrs.data(), N, m), Wv[3 * m + 2]);
				FFlightWolfStep& Wf = Wolves[static_cast<size_t>(m)];
				Wf = FFlightWolfStep();
				Wf.Target = Wv[3 * m + 1];
				Wf.bHuntEnd = (B & 1) != 0;
				Wf.bHuntSel = (B & 2) != 0;
				Wf.bPair = (B & 4) != 0;
				Wf.bRange = (B & 8) != 0;
				Wf.bVis0 = (B & 16) != 0;
				Wf.bBlocked = (B & 32) != 0;
				Wf.bCover = (B & 64) != 0;
			}
			for (std::int32_t i = 0; i < N; ++i)
			{
				const std::int32_t B = Db[i];
				FFlightDeerStep& Dd = Deer[static_cast<size_t>(i)];
				Dd = FFlightDeerStep();
				Dd.bFlee = (B & 1) != 0;
				Dd.bReflex = (B & 2) != 0;
				Dd.bDone = (B & 4) != 0;
				Dd.bCaught = (B & 8) != 0;
				Dd.bInCov = (B & 16) != 0;
				Dd.bAlive0 = (B & 32) != 0;
				Dd.Route = Dr[i];
			}
			FlightUpdate(Stats, Ptrs.data(), Deer.data(), N, Wolves.data(), M, &Rs, static_cast<std::int64_t>(G::kFsTickT[t]) - 1);
			FFlightOpen Open;
			for (const FFlightTrack& T : Tracks)
			{
				Open.Add(T);
			}
			std::int64_t Row[G::kFlightRouteLen] = {};
			Detail::FlightRouteRow(FlightRouteReportOf(FRouteStats(), Rs, Open), Row);
			const std::int64_t* Want = G::kFsBlock + static_cast<std::int64_t>(G::kFlightRouteLen) * t;
			for (std::int32_t k = 0; k < G::kFlightRouteLen; ++k)
			{
				C.Int(91, Row[k], Want[k]);
			}
			const std::int64_t* Tr = G::kFsTrack + static_cast<std::int64_t>(G::kFsTrackLen) * N * t;
			for (std::int32_t i = 0; i < N; ++i)
			{
				const FFlightTrack& T = Tracks[static_cast<size_t>(i)];
				const std::int64_t Got[6] = {T.RouteSteps[0], T.RouteSteps[1], T.RouteSteps[2], T.RouteSteps[3], T.LastEndT, T.Len};
				for (std::int32_t j = 0; j < 6; ++j)
				{
					C.Int(92, Got[j], Tr[6 * i + j]);
				}
			}
			Detail::Close(R, t, C);
		}
		R.Count0 = Rs.Refled;
		for (std::int32_t r = 0; r < kNumFlightRouteRows; ++r)
		{
			R.Count1 += Rs.DropObstacle[r];
			R.Count2 += Rs.Chased[r];
		}
		return R;
	}

	namespace Detail
	{
		/** 기준 루프 두뇌 (머리 주석 — 내장 R1b 를 24 열로 늘리고 출력층 칸 4 = 칸 1, 편향 칸 4 = 칸 1 + 델타). 망 보기는 이 그릇의 배열을 가리킨다. */
		struct FLoopBrain
		{
			std::vector<float> W0, B0, W1, B1, W2, B2;
			P3::FPolicyNetV3 Net{};

			explicit FLoopBrain(float Delta)
			{
				const std::int32_t In = O3::kObsDimRoute;
				W0.assign(static_cast<size_t>(P3::kHiddenDim) * In, 0.0f);
				for (std::int32_t j = 0; j < P3::kHiddenDim; ++j)
				{
					for (std::int32_t i = 0; i < P3::kObsDim; ++i)
					{
						W0[static_cast<size_t>(j * In + i)] = P3::kW0[j * P3::kObsDim + i];
					}
				}
				B0.assign(P3::kB0, P3::kB0 + P3::kHiddenDim);
				W1.assign(P3::kW1, P3::kW1 + P3::kHiddenDim * P3::kHiddenDim);
				B1.assign(P3::kB1, P3::kB1 + P3::kHiddenDim);
				W2.assign(P3::kW2, P3::kW2 + P3::kNumBehaviors * P3::kHiddenDim);
				B2.assign(P3::kB2, P3::kB2 + P3::kNumBehaviors);
				for (std::int32_t i = 0; i < P3::kHiddenDim; ++i)
				{
					W2[static_cast<size_t>(P3::kSleep * P3::kHiddenDim + i)] = W2[static_cast<size_t>(P3::kFlee * P3::kHiddenDim + i)];
				}
				B2[P3::kSleep] = B2[P3::kFlee] + Delta;
				Net = P3::FPolicyNetV3{In, W0.data(), B0.data(), W1.data(), B1.data(), W2.data(), B2.data()};
			}

			/** 가중치 sha256 (export_weights_v3.weights_bytes 차례 = W0·B0·W1·B1·W2·B2 float32 리틀 엔디언 — 평가기 EcoV3Eval Sha256Hex 와 같다). */
			void Sha256Hex(char Out[2 * EcoSha256::kDigestBytes + 1]) const
			{
				EcoSha256::FState S;
				EcoSha256::Update(S, W0.data(), sizeof(float) * W0.size());
				EcoSha256::Update(S, B0.data(), sizeof(float) * B0.size());
				EcoSha256::Update(S, W1.data(), sizeof(float) * W1.size());
				EcoSha256::Update(S, B1.data(), sizeof(float) * B1.size());
				EcoSha256::Update(S, W2.data(), sizeof(float) * W2.size());
				EcoSha256::Update(S, B2.data(), sizeof(float) * B2.size());
				std::uint8_t D[EcoSha256::kDigestBytes];
				EcoSha256::Final(S, D);
				EcoSha256::ToHex(D, Out);
			}
		};

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
			std::int64_t Draws = 0;
			bool bRngOverflow = false;
			std::vector<std::uint8_t> Bytes;
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

		/** 시작 상태 (EcoV3Eval.cpp Init 과 같다 + 두 길 두뇌: SetModelObsDim(24)·SetModelRoute(참)). */
		inline void InitLoop(FLoopWorld& L, const P3::FPolicyNetV3& Net, FCase& C)
		{
			FWorldConfig Cfg;
			G::FillWorldConfig(Cfg);
			Cfg.Covers.clear();
			for (std::int32_t k = 0; k < G::kWorldCoverCount; ++k)
			{
				Cfg.Covers.push_back({G::kWorldCovers[3 * k], G::kWorldCovers[3 * k + 1], G::kWorldCovers[3 * k + 2]});
			}
			Cfg.Obstacles.Discs.clear();
			for (std::int32_t k = 0; k < G::kWorldDiscCount; ++k)
			{
				const double* Dv = G::kWorldDiscs + G::kWorldDiscCols * k;
				Cfg.Obstacles.Discs.insert(Cfg.Obstacles.Discs.end(), {Dv[0], Dv[1], Dv[2]});
			}
			InitWorld(L.W, Cfg);
			static constexpr std::uint8_t kRouteAllowed[P3::kNumBehaviors] = {1, 1, 1, 0, 0};   // 두뇌 파일 allowed (graze·flee·hide)
			SetModelAllowed(L.W, kRouteAllowed);
			SetModelObsDim(L.W, O3::kObsDimRoute);
			SetModelRoute(L.W, true);
			C.Ok(100, L.W.Config.WildFlight.bRoute && L.W.ObsDim == O3::kObsDimRoute && L.W.Allowed[P3::kFreeze] == 0 && L.W.Allowed[P3::kSleep] == 0);
			FFoodGrid& Fg = L.W.Food;
			C.Ok(100, Fg.Gw == G::kWorldGw && Fg.Cell == G::kWorldCell);
			const size_t Cells = static_cast<size_t>(G::kWorldGw) * static_cast<size_t>(G::kWorldGw);
			C.Ok(100, sizeof(G::kWorldCap) / sizeof(double) == Cells);
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
				const size_t k = static_cast<size_t>(i);
				const FHerbView H{&L.Reps[k], &L.Dec[k], &L.Bodies[k], &L.Perc[k], &L.Ctl[k]};
				const FVec2 P{Dv[0], Dv[1]};
				const FVec2 Hd{Dv[2], Dv[3]};
				C.Ok(100, Dv[4] == L.W.RepCfg.InitEnergy);
				AdoptHerb(L.W, H, P, Hd, R3::MakeAgentKey(static_cast<std::uint32_t>(i), 0));
				H.Body->Pos = P;
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
				C.Ok(100, Spec.BaseSpeed == Wv[4]);
				FThreatAgent& A = L.Threats[static_cast<size_t>(m)];
				AdoptThreat(L.W, A, Spec, Wv[0], Wv[1], Wv[2], Wv[3], m);
				A.Slot = static_cast<std::uint32_t>(m);
				A.State.PosX = Wv[0];
				A.State.PosY = Wv[1];
				A.State.HeadX = Wv[2];
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
			ObserveAndDecideAll(L.W, L.Live.data(), static_cast<std::int32_t>(L.Live.size()), L.ThreatPtrs.data(), M, Net);
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

		/** 지문 (골든 머리 주석 '기준 루프 지문' — FoliageGoldenCheckV3 지문 + 길 칸·도주 덮기 방향). */
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
					for (std::int32_t k = 0; k < O3::kObsDim; ++k)
					{
						PutF(B, P.Obs[k]);
					}
					for (std::int32_t k = 0; k < O3::kNumObstacleObs; ++k)
					{
						PutF(B, P.ObstacleObs[k]);
					}
					for (std::int32_t k = 0; k < O3::kNumRouteObs; ++k)
					{
						PutF(B, P.RouteObs[k]);
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
			// 길 칸 (칸마다 스텝 끝 산 슬롯 — route_req = 길 결정 ∧ 도주 사슴의 두뇌 출력, 아니면 −1)
			for (std::int32_t f = 0; f < 6; ++f)
			{
				for (std::int32_t i = 0; i < N; ++i)
				{
					if (L.Cause[static_cast<size_t>(i)] != 0)
					{
						continue;
					}
					const FHerbDecision& D = L.Dec[static_cast<size_t>(i)];
					const std::int32_t Req = (D.bRouteDecide && D.KeepMode == kKeepPanic) ? D.RouteRequest : -1;
					const std::int32_t V[6] = {D.Route, D.RouteK, D.RouteAge, D.RouteFeas, D.bRouteDecide ? 1 : 0, Req};
					PutI(B, V[f]);
				}
			}
			// 도주 덮기 방향 (스텝 끝 산 ∧ 도주 슬롯, 행 우선 — H 뒤·다음 A 앞의 KeepDir)
			for (std::int32_t i = 0; i < N; ++i)
			{
				const FHerbDecision& D = L.Dec[static_cast<size_t>(i)];
				if (L.Cause[static_cast<size_t>(i)] == 0 && D.KeepMode == kKeepPanic)
				{
					PutD(B, D.KeepDir.X);
					PutD(B, D.KeepDir.Y);
				}
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

		/** 기록 줄 72 칸: 잡힘·굶음·산 + 도망 보고 52 (FoliageGoldenCheckV3 Row 순서) + 길 통계 12 + 숨은 뒤 지켜보기 5. */
		inline void CheckRow(const FLoopWorld& L, std::int64_t* Out)
		{
			std::int32_t k = 0;
			std::int64_t Caught = 0, Starved = 0, Alive = 0;
			for (const std::int32_t Cs : L.Cause)
			{
				Caught += Cs == 1 ? 1 : 0;
				Starved += Cs == 2 ? 1 : 0;
				Alive += Cs == 0 ? 1 : 0;
			}
			Out[k++] = Caught;
			Out[k++] = Starved;
			Out[k++] = Alive;
			const FFlightReport Rp = FlightReportOf(L.W.Stats.Flight, FlightOpenOf(L.Live.data(), static_cast<std::int32_t>(L.Live.size())));
			Out[k++] = Rp.Started;
			Out[k++] = Rp.LiveSteps;
			Out[k++] = Rp.FleeSteps;
			Out[k++] = Rp.ReflexSteps;
			for (const std::int64_t* P : {Rp.Num, Rp.Steps, Rp.Contact})
			{
				for (std::int32_t c = 0; c < kNumFlightCauses; ++c)
				{
					Out[k++] = P[c];
				}
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
			StatsRow(L.W.Stats.Route, Out + k);
			k += 12;
			Out[k++] = Rp.Chased;
			Out[k++] = Rp.Hidden;
			Out[k++] = Rp.Watching;
			Out[k++] = Rp.CoverCaught;
			Out[k++] = Rp.CoverStarved;
		}
	}

	/**
	 * 묶음 5 기준 루프 (두뇌 Brain — 0 route0, 1 늘 SHELTER 시험 두뇌): 파이썬 거울 세계와 같은 시작 상태·같은 세계 난수로 kWorldSteps 스텝 — 스텝마다 지문,
	 * kWorldEvery 스텝마다 기록 72 칸, 끝 도망 길 덩어리 = 파이썬. 망은 엔진이 내장 R1b 로 만든 24 열 두뇌(sha256 = 두뇌 파일). 사례 = 지문 (0 = 시작).
	 */
	inline FReport CheckWorld(std::int32_t Brain)
	{
		using namespace Detail;
		FReport R;
		const FLoopBrain Br(G::kWorldBrainDelta[Brain]);
		FLoopWorld L;
		{
			FCase C;
			char Hex[2 * EcoSha256::kDigestBytes + 1];
			Br.Sha256Hex(Hex);
			C.Ok(105, std::strcmp(Hex, G::kWorldBrainSha256[Brain]) == 0);
			InitLoop(L, Br.Net, C);
			const std::vector<std::uint8_t> All(static_cast<size_t>(G::kWorldN), 1);
			C.Int(101, static_cast<std::int64_t>(Fingerprint(L, All, nullptr)), static_cast<std::int64_t>(G::kWorldHash[Brain * (G::kWorldSteps + 1)]));
			Close(R, 0, C);
		}
		const std::int32_t M = G::kWorldM;
		std::vector<std::uint8_t> Alive0(static_cast<size_t>(G::kWorldN), 1);
		std::vector<std::int32_t> StepSlots;
		std::int32_t Check = 0;
		for (std::int32_t t = 1; t <= G::kWorldSteps; ++t)
		{
			FCase C;
			for (size_t i = 0; i < Alive0.size(); ++i)
			{
				Alive0[i] = L.Cause[i] == 0 ? 1 : 0;
			}
			StepSlots = L.LiveSlot;
			Step(L.W, L.Live.data(), static_cast<std::int32_t>(L.Live.size()), L.ThreatPtrs.data(), M, Br.Net);
			size_t Keep = 0;
			for (size_t r = 0; r < L.Live.size(); ++r)
			{
				const std::int32_t Slot = L.LiveSlot[r];
				const FHerbBody& Bd = L.Bodies[static_cast<size_t>(Slot)];
				if (Bd.DeathCause != kDeathNone)
				{
					L.Cause[static_cast<size_t>(Slot)] = Bd.DeathCause == kDeathCaught ? 1 : 2;
					continue;
				}
				L.Live[Keep] = L.Live[r];
				L.LiveSlot[Keep] = Slot;
				++Keep;
			}
			L.Live.resize(Keep);
			L.LiveSlot.resize(Keep);
			const std::uint64_t H = Fingerprint(L, Alive0, &StepSlots);
			C.Int(101, static_cast<std::int64_t>(H), static_cast<std::int64_t>(G::kWorldHash[Brain * (G::kWorldSteps + 1) + t]));
			if (t % G::kWorldEvery == 0 && Check < G::kWorldChecks)
			{
				std::int64_t Got[G::kWorldCheckLen] = {};
				CheckRow(L, Got);
				const std::int64_t* Want = G::kWorldCheck + static_cast<std::int64_t>(G::kWorldCheckLen) * (Brain * G::kWorldChecks + Check);
				for (std::int32_t j = 0; j < G::kWorldCheckLen; ++j)
				{
					C.Int(102, Got[j], Want[j]);
				}
				++Check;
			}
			Close(R, t, C);
		}
		FCase C;
		constexpr std::int64_t RawCount = static_cast<std::int64_t>(sizeof(G::kWorldRaw) / sizeof(G::kWorldRaw[0]));
		C.Ok(104, !L.bRngOverflow && L.Draws == RawCount);
		C.Int(102, Check, G::kWorldChecks);
		std::int64_t Row[G::kFlightRouteLen] = {};
		FlightRouteRow(FlightRouteReportOf(L.W.Stats.Route, L.W.Stats.FlightRoute, FlightOpenOf(L.Live.data(), static_cast<std::int32_t>(L.Live.size()))),
					   Row);
		for (std::int32_t k = 0; k < G::kFlightRouteLen; ++k)
		{
			C.Int(103, Row[k], G::kWorldFlightRoute[Brain * G::kFlightRouteLen + k]);
		}
		C.Int(106, L.W.Stats.MaskViolations, 0);
		C.Int(106, L.W.Stats.ObsLayoutMismatch, 0);
		Close(R, G::kWorldSteps + 1, C);
		R.Count0 = L.W.Stats.Route.Picked[kRouteShelter];
		R.Count1 = L.W.Stats.Route.Decisions;
		for (const std::int32_t Cs : L.Cause)
		{
			R.Count2 += Cs == 1 ? 1 : 0;
		}
		return R;
	}
}

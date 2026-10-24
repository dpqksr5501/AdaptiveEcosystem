// 두 길 두뇌(RUN·SHELTER) 스칼라 참조 하네스 — 언리얼 없이 설계 RL_V3_FLIGHT_ROUTE_DESIGN.md 16-3·16-4·16-5 의 C++ 꼴 식(사슴 하나, 은신처 순서대로,
// double)이 골든 RouteGoldenVectorsV3.h(herbivore_rl/export_golden_v3_route.py)와 비트 단위로 같은 값을 내는지 본다:
//   SHELTER 기하(k*·μ*·e*·방향·유지 μ·유지 방향), 길 셈 한 줄(결정·무효·가능 바뀜·길·k·age·feas·관측 21~23·덮기 방향), 적용 한 줄(칸 4 ∧ 가능 → SHELTER),
//   손 장면 길 통계(틱마다 누적), 마스크 판 4 한 줄, 다시 난 개체(길 상태 지움·terminal_obs 0), 관측 세 칸 사례(WriteRouteObs float 비트),
//   도망 길 기록 장면의 길 칸(길별 반사 스텝·마지막 끝 스텝·놓침·쫓김·가림·refled — 끝 까닭별 by_route 는 UE Route.FlightRecord),
//   기준 루프 머리 칸(배열 크기·두뇌 편향·근접 동점 없음 — 지문·기록 자체는 세계 전체가 필요해 이식 단계의 Route.World 시험이 본다).
//   계획서: AdaptiveEcosystem/Docs/RL_Policy/RL_V3_ROUTE_CPP_PORT_PLAN.md 10-1.
// 엔진 코드가 아니라 식의 참조다 — 10-24 C++ 이식 뒤 엔진 함수로 같은 골든을 보는 하네스는 route_v3_main.cpp (검사 본문 AI/Policy/Tests/RouteGoldenCheckV3.h)다.
//
//   g++ -std=c++17 -O2 -ffp-contract=off -I <AI/Policy 폴더 — 골든 헤더 자리> route_ref_main.cpp   (FMA 축약은 μ·e 의 마지막 비트를 바꿀 수 있다)
//   하나라도 어긋나면 종료 코드 1, 다 맞으면 'PASS'.
//
// 자동 실행: herbivore_rl/tests/test_route_port_v3.py

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

#include "RouteGoldenVectorsV3.h"

namespace G = EcoWorldV3::GoldenRoute;

namespace
{
	constexpr int kRowIntN = 12, kRowInN = 6, kRowOutIN = 12, kRowOutDN = 7, kApplyIntN = 8, kApplyDN = 4, kStatsN = 14;
	constexpr int kGeoIntN = 3, kGeoInN = 6, kGeoOutIN = 3, kGeoOutDN = 7, kMaskIntN = 17, kRespawnIntN = 14;
	int GFails = 0;

	void Fail(const char* What, int Index, double Got, double Want)
	{
		if (GFails < 40)
		{
			std::printf("FAIL %s [%d]: %.17g != %.17g\n", What, Index, Got, Want);
		}
		++GFails;
	}

	// 골든 값 비교 (±∞ 는 kInf 로 적었다)
	bool SameD(double Got, double Want)
	{
		if (std::isinf(Got))
		{
			return (Got > 0.0 ? G::kInf : -G::kInf) == Want;
		}
		return Got == Want;
	}

	struct FVec
	{
		double X = 0.0;
		double Y = 0.0;
	};

	// env_v2/world.py wf_wall_keep: 축마다 벽 여유 안이고 그 벽 쪽이면 성분을 지우고 단위화 (다 지워지면 그대로)
	FVec WallKeep(double Px, double Py, FVec D, double Size, double Mg)
	{
		FVec S = D;
		if ((Px <= Mg && S.X < 0.0) || (Px >= Size - Mg && S.X > 0.0))
		{
			S.X = 0.0;
		}
		if ((Py <= Mg && S.Y < 0.0) || (Py >= Size - Mg && S.Y > 0.0))
		{
			S.Y = 0.0;
		}
		const double N = std::sqrt(S.X * S.X + S.Y * S.Y);
		FVec U;
		if (N > G::kEps)
		{
			U.X = S.X / N;
			U.Y = S.Y / N;
		}
		return (U.X * U.X + U.Y * U.Y > G::kEps * G::kEps) ? U : D;
	}

	struct FGeo
	{
		int K = -1;
		double Mu = 0.0, E = 0.0;
		FVec Dir;
		double KeepMu = -std::numeric_limits<double>::infinity();
		FVec KeepDir;
	};

	// SHELTER 기하 (사슴 하나 — world.py _route_shelter 와 같은 식·같은 순서). Q (M×2), SBits = S 늑대, Cov (C×3)
	FGeo Shelter(double Px, double Py, double A0x, double A0y, const double* Q, int M, int SBits, const double* Cov, int C, int KeepK, double Size,
				 double Mg)
	{
		const double Inf = std::numeric_limits<double>::infinity();
		FGeo R;
		double BestE = Inf;
		for (int k = 0; k < C; ++k)
		{
			const double Vx = Cov[3 * k] - Px;
			const double Vy = Cov[3 * k + 1] - Py;
			const double Dc = std::sqrt(Vx * Vx + Vy * Vy);
			const double Ed = Dc - Cov[3 * k + 2];
			const double Ds = Dc > G::kEps ? Dc : G::kEps;
			const double Ux = Vx / Ds, Uy = Vy / Ds;
			const double Ex = Px + Ed * Ux, Ey = Py + Ed * Uy;
			double Mn = Inf;
			for (int m = 0; m < M; ++m)
			{
				if (!(SBits & (1 << m)))
				{
					continue;
				}
				const double Dx = Q[2 * m] - Ex, Dy = Q[2 * m + 1] - Ey;
				const double D = std::sqrt(Dx * Dx + Dy * Dy);
				Mn = D < Mn ? D : Mn;
			}
			const double Mu = Mn - Ed;
			const double Cs = (Vx * A0x + Vy * A0y) / Ds;
			const bool bCand = Dc > G::kEps && Ed > 0.0 && Ed <= G::kMaxEdgeU && Cs >= G::kCosMin && Mu >= G::kEnterU;
			if (bCand && Ed < BestE)
			{
				BestE = Ed;
				R.K = k;
				R.Mu = Mu;
				R.E = Ed;
				R.Dir = WallKeep(Px, Py, FVec{Vx / Ds, Vy / Ds}, Size, Mg);
			}
			if (k == KeepK)
			{
				R.KeepMu = Mu;
				R.KeepDir = WallKeep(Px, Py, FVec{Vx / Ds, Vy / Ds}, Size, Mg);
			}
		}
		return R;
	}

	const double* CoverSet(int Set, int& C)
	{
		C = G::kCoverSetIndex[2 * Set + 1];
		return G::kCoverSetData + 3 * G::kCoverSetIndex[2 * Set];
	}

	float Obs(double V, double Norm)
	{
		const double X = V / Norm;
		return static_cast<float>(X < 0.0 ? 0.0 : (X > 1.0 ? 1.0 : X));
	}

	void CheckGeo()
	{
		for (int c = 0; c < G::kGeoCases; ++c)
		{
			const std::int32_t* I = G::kGeoInt + kGeoIntN * c;
			const double* In = G::kGeoIn + kGeoInN * c;
			int C = 0;
			const double* Cov = CoverSet(I[0], C);
			const FGeo R = Shelter(In[0], In[1], In[2], In[3], G::kGeoThreat + 2 * G::kThreats * c, G::kThreats, G::kGeoS[c], Cov, C, I[1], In[4], In[5]);
			const std::int32_t* Oi = G::kGeoOutI + kGeoOutIN * c;
			const double* Od = G::kGeoOutD + kGeoOutDN * c;
			const bool bKeep = I[1] >= 0;
			if (R.K != Oi[0]) Fail("geo k", c, R.K, Oi[0]);
			if ((R.K >= 0) != (Oi[1] != 0)) Fail("geo ok", c, R.K >= 0, Oi[1]);
			if ((bKeep && R.KeepMu >= G::kExitU) != (Oi[2] != 0)) Fail("geo keep_ok", c, bKeep && R.KeepMu >= G::kExitU, Oi[2]);
			if (!SameD(R.Mu, Od[0])) Fail("geo mu", c, R.Mu, Od[0]);
			if (!SameD(R.E, Od[1])) Fail("geo e", c, R.E, Od[1]);
			if (R.Dir.X != Od[2] || R.Dir.Y != Od[3]) Fail("geo dir", c, R.Dir.X, Od[2]);
			if (!SameD(bKeep ? R.KeepMu : 0.0, Od[4])) Fail("geo keep_mu", c, R.KeepMu, Od[4]);
			if (R.KeepDir.X != Od[5] || R.KeepDir.Y != Od[6]) Fail("geo keep_dir", c, R.KeepDir.X, Od[5]);
		}
	}

	// 길 셈 한 줄 (설계 16-3, world.py `_route_step` 두뇌 길)
	struct FRowOut
	{
		int Decide = 0, Onset = 0, Route = G::kRouteNone, K = -1, Age = 0, Feas = 0, Sok = 0, CandK = -1, DecPrev = -1, Invalid = 0, Refeas = 0,
			KeepOk = 0;
		double Mu = 0.0, E = 0.0, KeepMu = 0.0;
		FVec Dir, Sh;
		float Ob[3] = {0.0f, 0.0f, 0.0f};
	};

	FRowOut RouteStep(int r)
	{
		const std::int32_t* I = G::kRowInt + kRowIntN * r;
		const double* In = G::kRowIn + kRowInN * r;
		const int Prev = I[3], Next = I[4], BRoute = I[7], BK = I[8], BAge = I[9], BFeas = I[10], SBits = I[11];
		FRowOut O;
		O.Dir = FVec{In[4], In[5]};
		if (Next != G::kModePanic)
		{
			return O;                                                    // 도주가 아니면 길 상태를 지운다 (방향은 반사 줄 그대로)
		}
		const bool bOn = Prev != G::kModePanic;
		const int Cur = bOn ? G::kRouteNone : BRoute;
		const int KeepK = Cur == G::kRouteShelter ? BK : -1;
		int C = 0;
		const double* Cov = CoverSet(0, C);
		const FGeo Gm = Shelter(In[0], In[1], In[2], In[3], G::kTickThreat + 2 * G::kThreats * I[1], G::kThreats, SBits, Cov, C, KeepK, G::kWorldSize,
								G::kWallMargin);
		const bool bSok = Gm.K >= 0;
		const int Feas = bSok ? G::kFeasShelter : 0;
		const bool bKeepOk = KeepK >= 0 && Gm.KeepMu >= G::kExitU;
		const bool bInval = Cur == G::kRouteShelter && !bKeepOk;
		const int Age = bOn ? 0 : BAge + 1;
		const bool bRefeas = Cur >= 0 && !bInval && Age >= G::kLockSteps && Feas != BFeas && Cur != G::kRouteShelter;
		const bool bDec = bOn || Cur < 0 || bInval || bRefeas;
		O.Decide = bDec;
		O.Onset = bOn;
		O.Route = bDec ? G::kRouteRun : Cur;
		O.K = O.Route == G::kRouteShelter ? BK : -1;
		O.Age = bDec ? 0 : Age;
		O.Feas = bDec ? Feas : BFeas;
		O.Sok = bSok;
		O.CandK = Gm.K;
		O.DecPrev = bDec ? Cur : -1;
		O.Invalid = bInval;
		O.Refeas = bRefeas;
		O.KeepOk = Cur == G::kRouteShelter && bKeepOk;
		O.KeepMu = Cur == G::kRouteShelter ? Gm.KeepMu : 0.0;
		O.Mu = bSok ? Gm.Mu : 0.0;
		O.E = bSok ? Gm.E : 0.0;
		O.Sh = Gm.Dir;
		if (O.Route == G::kRouteShelter)
		{
			O.Dir = Gm.KeepDir;                                          // 유지 중 = 유지 은신처 쪽 (결정 스텝은 RUN — 두뇌가 다음 스텝에 고른다)
		}
		O.Ob[0] = 1.0f;
		O.Ob[1] = bSok ? Obs(Gm.Mu, G::kReachNormU) : 0.0f;
		O.Ob[2] = bSok ? Obs(Gm.E, G::kEdgeNormU) : 0.0f;
		return O;
	}

	void CheckRows()
	{
		for (int r = 0; r < G::kRows; ++r)
		{
			const FRowOut O = RouteStep(r);
			const std::int32_t* Oi = G::kRowOutI + kRowOutIN * r;
			const double* Od = G::kRowOutD + kRowOutDN * r;
			const int Got[kRowOutIN] = {O.Decide, O.Onset, O.Route, O.K, O.Age, O.Feas, O.Sok, O.CandK, O.DecPrev, O.Invalid, O.Refeas, O.KeepOk};
			for (int j = 0; j < kRowOutIN; ++j)
			{
				if (Got[j] != Oi[j]) Fail("row int", r * 100 + j, Got[j], Oi[j]);
			}
			const double GotD[kRowOutDN] = {O.Mu, O.E, O.Dir.X, O.Dir.Y, O.Sh.X, O.Sh.Y, O.KeepMu};
			for (int j = 0; j < kRowOutDN; ++j)
			{
				if (!SameD(GotD[j], Od[j])) Fail("row double", r * 100 + j, GotD[j], Od[j]);
			}
			for (int j = 0; j < 3; ++j)
			{
				if (O.Ob[j] != G::kRowObs[3 * r + j]) Fail("row obs", r * 100 + j, O.Ob[j], G::kRowObs[3 * r + j]);
			}
		}
	}

	// 적용 한 줄 (다음 스텝 첫머리 `_route_apply`): 칸 4 ∧ 가능 → SHELTER (k*, k* 쪽), 아니면 RUN (방향 그대로)
	void CheckApplies()
	{
		for (int a = 0; a < G::kApplies; ++a)
		{
			const std::int32_t* I = G::kApplyInt + kApplyIntN * a;
			const double* D = G::kApplyD + kApplyDN * a;
			const int r = I[0];
			const std::int32_t* Oi = G::kRowOutI + kRowOutIN * r;
			const double* Od = G::kRowOutD + kRowOutDN * r;
			if (!Oi[0]) Fail("apply on non-decision row", a, 0, 1);
			if (I[2] != Oi[6] || I[3] != Oi[7]) Fail("apply sok/cand_k", a, I[2], Oi[6]);
			if (D[0] != Od[2] || D[1] != Od[3]) Fail("apply before dir", a, D[0], Od[2]);
			const bool bSh = I[1] == G::kSlotShelter && Oi[6];
			const int Route = bSh ? G::kRouteShelter : G::kRouteRun;
			const int K = bSh ? Oi[7] : -1;
			const double Dx = bSh ? Od[4] : D[0], Dy = bSh ? Od[5] : D[1];
			const int Bad = I[1] == G::kSlotShelter && !Oi[6];
			const int Sw = Oi[8] >= 0 && Route != Oi[8];
			if (Route != I[4]) Fail("apply route", a, Route, I[4]);
			if (K != I[5]) Fail("apply k", a, K, I[5]);
			if (Bad != I[6]) Fail("apply bad", a, Bad, I[6]);
			if (Sw != I[7]) Fail("apply switch", a, Sw, I[7]);
			if (Dx != D[2] || Dy != D[3]) Fail("apply dir", a, Dx, D[2]);
		}
	}

	// 손 장면 길 통계: 장면마다 0 에서 줄·적용을 차례로 더한 값 = 틱마다 적은 route_stats
	void CheckSceneStats()
	{
		int s = 0;      // 통계 줄 (손 장면 통계는 앞쪽에 틱 순서로)
		for (int sc = 0; sc < G::kScenes; ++sc)
		{
			const int R0 = G::kSceneIndex[4 * sc], Rn = G::kSceneIndex[4 * sc + 1], A0 = G::kSceneIndex[4 * sc + 2], An = G::kSceneIndex[4 * sc + 3];
			long long Acc[12] = {};
			for (int r = R0; r < R0 + Rn; ++r, ++s)
			{
				const std::int32_t* I = G::kRowInt + kRowIntN * r;
				const std::int32_t* Oi = G::kRowOutI + kRowOutIN * r;
				Acc[0] += Oi[1];                         // onsets
				Acc[1] += Oi[1] && Oi[6];                // onset_shelter
				Acc[2] += Oi[0];                         // decisions
				Acc[3] += Oi[10];                        // redecide_feas
				Acc[5] += Oi[9];                         // invalid_shelter
				Acc[10] += I[5] && I[6] == G::kRouteRun; // steps_run (산 사슴의 실행한 길)
				Acc[11] += I[5] && I[6] == G::kRouteShelter;
				for (int a = A0; a < A0 + An; ++a)
				{
					const std::int32_t* P = G::kApplyInt + kApplyIntN * a;
					if (P[0] != r)
					{
						continue;
					}
					Acc[4] += P[7];                          // switches
					Acc[6] += P[4] == G::kRouteRun;          // picked_run
					Acc[7] += P[4] == G::kRouteShelter;      // picked_shelter
					Acc[8] += P[2];                          // choice (SHELTER 가 열린 결정)
					Acc[9] += P[6];                          // bad_shelter
				}
				const std::int32_t* St = G::kStatsInt + kStatsN * s;
				if (St[0] != 0) Fail("scene stats source", s, St[0], 0);
				for (int j = 0; j < 12; ++j)
				{
					if (Acc[j] != St[2 + j]) Fail("scene stats", s * 100 + j, static_cast<double>(Acc[j]), St[2 + j]);
				}
			}
		}
	}

	// 마스크 판 4 한 줄 (종류 'gate' 는 판 5 = 판 4 + 덮기 밖 결정 줄의 칸 1 막힘 — 이식 계획서 13-1)
	int GateKind()
	{
		for (int k = 0; k < static_cast<int>(sizeof(G::kMaskKinds) / sizeof(G::kMaskKinds[0])); ++k)
		{
			if (std::strcmp(G::kMaskKinds[k], "gate") == 0)
			{
				return k;
			}
		}
		return -1;
	}

	void CheckMask()
	{
		const int Gate = GateKind();
		if (Gate < 0) Fail("mask gate kind", 0, -1, 0);
		for (int r = 0; r < G::kMaskRows; ++r)
		{
			const std::int32_t* I = G::kMaskInt + kMaskIntN * r;
			const float* O = G::kMaskObs + G::kObsDim * r;
			const int Ov = I[1], Rd = I[2], Now = I[3], Reads = I[4], Wake = I[5], Beh = I[6];
			const bool bThreat = O[G::kObsPredCount] > 0.0f || O[G::kObsThreatRecency] >= G::kThreatRecencyObs;
			int M[5];
			const int Feas[5] = {1, bThreat, bThreat && O[G::kObsCoverDist] < G::kHideCoverObs, bThreat, 1};
			for (int j = 0; j < 5; ++j)
			{
				M[j] = I[7 + j] && Feas[j];
			}
			M[4] = M[4] && !Wake;
			if (!Reads)
			{
				for (int j = 0; j < 5; ++j)
				{
					M[j] = j == Beh;
				}
			}
			if (Ov == G::kModePanic)
			{
				const bool bSok = O[G::kRouteObsFirst + 1] > 0.0f;
				const bool bNowSh = Now == G::kRouteShelter;
				for (int j = 0; j < 5; ++j)
				{
					M[j] = 0;
				}
				M[G::kSlotRun] = Rd || !bNowSh;
				M[G::kSlotShelter] = (Rd && bSok) || (!Rd && bNowSh);
			}
			else if (Ov == G::kModeShelter)
			{
				for (int j = 0; j < 5; ++j)
				{
					M[j] = j == 2;
				}
			}
			else if (I[0] == Gate && Reads)
			{
				M[G::kSlotRun] = 0;                                          // 판 5: 덮기 밖 결정 줄은 FLEE 막음 (rep_policy.py `_gate_free_rows`)
			}
			if (M[G::kSlotReserved]) Fail("mask slot 3 open", r, 1, 0);
			for (int j = 0; j < 5; ++j)
			{
				if (M[j] != I[12 + j]) Fail("mask", r * 10 + j, M[j], I[12 + j]);
			}
		}
	}

	// 관측 세 칸 사례 (계획서 3절 WriteRouteObs — float 비트)
	void WriteRouteObs(bool bPanic, bool bOk, double Mu, double E, float Out[3])
	{
		Out[0] = bPanic ? 1.0f : 0.0f;
		Out[1] = bPanic && bOk ? Obs(Mu, G::kReachNormU) : 0.0f;
		Out[2] = bPanic && bOk ? Obs(E, G::kEdgeNormU) : 0.0f;
	}

	void CheckObsCases()
	{
		for (int c = 0; c < G::kObsCases; ++c)
		{
			const double Mu = G::kObsCaseIn[2 * c] >= G::kInf ? std::numeric_limits<double>::infinity() : G::kObsCaseIn[2 * c];
			float Got[3];
			WriteRouteObs(G::kObsCaseInt[2 * c] != 0, G::kObsCaseInt[2 * c + 1] != 0, Mu, G::kObsCaseIn[2 * c + 1], Got);
			for (int j = 0; j < 3; ++j)
			{
				if (Got[j] != G::kObsCaseOut[3 * c + j]) Fail("obs case", c * 10 + j, Got[j], G::kObsCaseOut[3 * c + j]);
			}
		}
	}

	// 기준 루프 머리 칸 (세계 전체가 필요한 지문·기록은 C++ 이식 단계의 Route.World 시험이 본다 — 여기서는 크기·두뇌 줄만)
	void CheckWorldShape()
	{
		const int Nb = G::kWorldBrains;
		if (sizeof(G::kWorldHash) / sizeof(G::kWorldHash[0]) != static_cast<size_t>(Nb * (G::kWorldSteps + 1))) Fail("world hash size", 0, 0, 0);
		if (sizeof(G::kWorldCheck) / sizeof(G::kWorldCheck[0]) != static_cast<size_t>(Nb * G::kWorldChecks * G::kWorldCheckLen)) Fail("world check size", 0, 0, 0);
		if (sizeof(G::kWorldFlightRoute) / sizeof(G::kWorldFlightRoute[0]) != static_cast<size_t>(Nb * G::kFlightRouteLen)) Fail("world route size", 0, 0, 0);
		if (sizeof(G::kWorldRaw) / sizeof(G::kWorldRaw[0]) != static_cast<size_t>(G::kWorldSteps * G::kWorldM)) Fail("world raw size", 0, 0, 0);
		if (sizeof(G::kWorldDeer) / sizeof(G::kWorldDeer[0]) != static_cast<size_t>(6 * G::kWorldN)) Fail("world deer size", 0, 0, 0);
		if (sizeof(G::kWorldCap) / sizeof(G::kWorldCap[0]) != static_cast<size_t>(G::kWorldGw * G::kWorldGw)) Fail("world food size", 0, 0, 0);
		if (G::kWorldBrainDelta[0] != -2.0f || G::kWorldBrainDelta[1] != 2.0f) Fail("world brain delta", 0, G::kWorldBrainDelta[0], -2.0);
		if (!(G::kWorldMinTopGap > 1e-4)) Fail("world near tie", 0, G::kWorldMinTopGap, 1e-4);
	}

	// 도망 길 기록 장면 (계획서 10-1 의 6): 재료만으로 셀 수 있는 길 칸 — 길별 반사 스텝·마지막 살아 끝난 도망의 끝 스텝·열린 도망 길이(사슴 칸), 원판 놓침
	// (늑대마다)·쫓김·가림(사슴마다)·refled (길 덩어리 꼬리). 끝 까닭별 by_route 는 도망 기록 전체(끝 까닭)가 필요해 이식 단계의 Route.FlightRecord 가 본다.
	void CheckFlightScene()
	{
		constexpr int kNone = 4, kRoutes = 5, kCauses = 11;
		constexpr int kTail = 3 * kRoutes * kCauses;    // drop_obstacle 5 · chased_steps 5 · hidden_steps 5 · refled · refled_steps
		const int N = G::kFsN, M = G::kThreats;
		long long Rs[64][4] = {}, Last[64], L[64] = {};
		long long Drop[kRoutes] = {}, Chased[kRoutes] = {}, Hidden[kRoutes] = {}, Refled = 0;
		for (int i = 0; i < N; ++i)
		{
			Last[i] = G::kFsNotLast;
		}
		for (int t = 0; t < G::kFsTicks; ++t)
		{
			const long long Tn = G::kFsTickT[t];          // world.py self.t (이번 스텝 번호 = Tn − 1)
			const std::int32_t* D = G::kFsDeer + N * t;
			const std::int32_t* R = G::kFsRoute + N * t;
			const std::int32_t* W = G::kFsWolf + 3 * M * t;
			bool Ex[64], Done[64];
			int Ri[64], Re[64];
			for (int i = 0; i < N; ++i)
			{
				Ex[i] = (D[i] & 1) && (D[i] & 32);
				Done[i] = (D[i] & 4) != 0;
				Re[i] = (D[i] & 2) ? R[i] : -1;
				Ri[i] = Re[i] >= 0 ? Re[i] : kNone;
			}
			for (int i = 0; i < N; ++i)                  // 1) 살아 끝난 도망: 닫고 끝 스텝(지난 스텝)을 남긴다
			{
				if (L[i] > 0 && !Ex[i])
				{
					L[i] = 0;
					Rs[i][0] = Rs[i][1] = Rs[i][2] = Rs[i][3] = 0;
					Last[i] = Tn - 2;
				}
			}
			for (int i = 0; i < N; ++i)                  // 2) 새 도망: 끝난 뒤 kFsRefleeSteps 안이면 refled
			{
				if (Ex[i] && L[i] == 0 && (Tn - 1) - Last[i] <= G::kFsRefleeSteps)
				{
					++Refled;
				}
			}
			bool Seen[64] = {}, Chase[64] = {};
			for (int m = 0; m < M; ++m)                  // 놓침(늑대마다)·쫓김·가림 — 쌍 = (늑대, 지난 표적)
			{
				const int B = W[3 * m], Tgt = W[3 * m + 1], Tp = W[3 * m + 2];
				if (Tp < 0 || Tp >= N)
				{
					continue;
				}
				Chase[Tp] = true;
				if (!(B & 32))
				{
					Seen[Tp] = true;
				}
				const bool bObstacle = (B & 4) && (B & 1) && (B & 2) && (B & 8) && (B & 32);   // np.select 순서: 그만둠 → 반경 → 원판
				if (Tgt != Tp && Ex[Tp] && bObstacle)
				{
					++Drop[Ri[Tp]];
				}
			}
			for (int i = 0; i < N; ++i)
			{
				if (Ex[i] && Chase[i])
				{
					++Chased[Ri[i]];
					Hidden[Ri[i]] += Seen[i] ? 0 : 1;      // 장면의 쌍 칸은 늘 있다 (비트 4)
				}
				if (Ex[i] && Re[i] >= 0)
				{
					++Rs[i][Re[i]];
				}
				L[i] += Ex[i] ? 1 : 0;
				if (Ex[i] && Done[i])                    // 3) FLEE 중 죽음: 그 스텝에 닫는다
				{
					L[i] = 0;
					Rs[i][0] = Rs[i][1] = Rs[i][2] = Rs[i][3] = 0;
				}
				if (Done[i])
				{
					Last[i] = G::kFsNotLast;
				}
			}
			const std::int64_t* Tr = G::kFsTrack + G::kFsTrackLen * N * t;
			for (int i = 0; i < N; ++i)
			{
				const long long Got[6] = {Rs[i][0], Rs[i][1], Rs[i][2], Rs[i][3], Last[i], L[i]};
				for (int j = 0; j < 6; ++j)
				{
					if (Got[j] != Tr[6 * i + j]) Fail("flight scene track", t * 1000 + i * 10 + j, static_cast<double>(Got[j]), static_cast<double>(Tr[6 * i + j]));
				}
			}
			const std::int64_t* Bk = G::kFlightRouteLen * t + G::kFsBlock + kTail;
			for (int r = 0; r < kRoutes; ++r)
			{
				if (Drop[r] != Bk[r]) Fail("flight scene drop_obstacle", t * 10 + r, static_cast<double>(Drop[r]), static_cast<double>(Bk[r]));
				if (Chased[r] != Bk[kRoutes + r]) Fail("flight scene chased", t * 10 + r, static_cast<double>(Chased[r]), static_cast<double>(Bk[kRoutes + r]));
				if (Hidden[r] != Bk[2 * kRoutes + r]) Fail("flight scene hidden", t * 10 + r, static_cast<double>(Hidden[r]), static_cast<double>(Bk[2 * kRoutes + r]));
			}
			if (Refled != Bk[3 * kRoutes] || Bk[3 * kRoutes + 1] != G::kFsRefleeSteps) Fail("flight scene refled", t, static_cast<double>(Refled), static_cast<double>(Bk[3 * kRoutes]));
		}
		if (Refled != 1) Fail("flight scene refled total", 0, static_cast<double>(Refled), 1.0);
	}

	// 다시 난 개체: 길 상태가 있던 사슴이 죽어 다시 나면 길 상태가 지워지고(새 개체가 곧바로 도주면 시작 결정), 죽은 사슴의 terminal_obs 길 칸은 0
	void CheckRespawn()
	{
		for (int r = 0; r < G::kRespawnRows; ++r)
		{
			const std::int32_t* I = G::kRespawnInt + kRespawnIntN * r;
			const float* O = G::kRespawnObs + 6 * r;
			if (I[4] < 0) Fail("respawn before route", r, I[4], 0);
			const bool bPanic = I[8] == G::kModePanic;
			const bool bCleared = I[9] == G::kRouteNone && I[10] == -1 && I[11] == 0 && I[12] == 0 && !I[13];
			const bool bOnset = I[9] == G::kRouteRun && I[10] == -1 && I[11] == 0 && I[13];
			if (bPanic ? !bOnset : !bCleared) Fail("respawn after state", r, I[9], G::kRouteNone);
			if ((O[0] != 0.0f) != bPanic) Fail("respawn obs in_panic", r, O[0], bPanic);
			for (int j = 3; j < 6; ++j)
			{
				if (O[j] != 0.0f) Fail("respawn terminal obs", r * 10 + j, O[j], 0.0);
			}
		}
	}
}

int main()
{
	CheckGeo();
	CheckRows();
	CheckApplies();
	CheckSceneStats();
	CheckMask();
	CheckRespawn();
	CheckObsCases();
	CheckFlightScene();
	CheckWorldShape();
	if (GFails)
	{
		std::printf("FAILS %d\n", GFails);
		return 1;
	}
	std::printf("PASS geo %d rows %d applies %d scenes %d mask %d respawn %d obs %d flight-scene %d world %dx%d\n", G::kGeoCases, G::kRows,
				G::kApplies, G::kScenes, G::kMaskRows, G::kRespawnRows, G::kObsCases, G::kFsTicks, G::kWorldBrains, G::kWorldSteps);
	return 0;
}

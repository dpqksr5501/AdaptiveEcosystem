// R5 장애물 관측 스칼라 참조 하네스 — 언리얼 없이 계약 POLICY_CONTRACT_V3.md 2-4 의 C++ 꼴 식(사슴 하나, 원판 순서대로, double)이
// 골든 ObstacleObsGoldenVectorsV3.h(herbivore_rl/export_golden_v3_obstacle_obs.py)와 비트 단위로 같은 값(E·N double, 가림, 관측 세 칸 float)을 내는지 본다.
// 엔진 코드가 아니라 식의 참조다 — C++ 단계는 EcoObservationV3 의 함수로 같은 검사를 UE 자동화 시험과 함께 둔다.
//
//   g++ -std=c++17 -O2 -I <골든 헤더 폴더> obstacle_obs_ref_main.cpp  (FMA 축약을 켜는 -march=native 는 E 의 마지막 비트를 바꾼다 — 계약 2-4 '정밀도')
//   하나라도 어긋나면 종료 코드 1, 다 맞으면 'PASS'.
//
// 자동 실행: herbivore_rl/tests/test_obstacle_obs_golden.py

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <limits>

#include "ObstacleObsGoldenVectorsV3.h"

namespace G = EcoObservationV3::GoldenObstacleObs;

namespace
{
	double Clip01(double X) { return X < 0.0 ? 0.0 : (X > 1.0 ? 1.0 : X); }

	struct FOut
	{
		double E = 0.0;
		double N = 0.0;
		bool bHidden = false;
	};

	FOut Slots(double X, double Y, double Hx, double Hy, bool bSeen, double Ax, double Ay, double Jx, double Jy, const double* D, int Num, double B,
			   double S, bool bBlock)
	{
		const double Inf = std::numeric_limits<double>::infinity();
		double Wx = Hx, Wy = Hy;
		if (bSeen && std::sqrt(Ax * Ax + Ay * Ay) > G::kEps)
		{
			Wx = Ax;
			Wy = Ay;
		}
		const double Nw = std::sqrt(Wx * Wx + Wy * Wy);
		const double Ux = Nw > G::kEps ? Wx / Nw : 1.0;
		const double Uy = Nw > G::kEps ? Wy / Nw : 0.0;
		const double Tx = Ux > 0.0 ? (S - X) / Ux : (Ux < 0.0 ? X / (-Ux) : Inf);
		const double Ty = Uy > 0.0 ? (S - Y) / Uy : (Uy < 0.0 ? Y / (-Uy) : Inf);
		FOut R;
		R.E = Tx < Ty ? Tx : Ty;
		if (!(R.E > 0.0))
		{
			R.E = 0.0;
		}
		R.N = Inf;
		for (int k = 0; k < Num; ++k)
		{
			const double Fx = X - D[3 * k];
			const double Fy = Y - D[3 * k + 1];
			const double Rk = D[3 * k + 2] + B;
			const double Cc = Fx * Fx + Fy * Fy - Rk * Rk;
			const double Bb = Fx * Ux + Fy * Uy;
			const double Dd = Bb * Bb - Cc;
			if (Cc >= 0.0 && Bb < 0.0 && Dd >= 0.0)
			{
				const double T = -Bb - std::sqrt(Dd);
				R.E = T < R.E ? T : R.E;
			}
			const double Nk = std::sqrt(Fx * Fx + Fy * Fy) - Rk;
			R.N = Nk < R.N ? Nk : R.N;
		}
		if (bSeen && bBlock)
		{
			const double Dx = X - Jx;
			const double Dy = Y - Jy;
			const double DD = Dx * Dx + Dy * Dy;
			for (int k = 0; k < Num && !R.bHidden; ++k)
			{
				const double Gx = D[3 * k] - Jx;
				const double Gy = D[3 * k + 1] - Jy;
				double T = DD > 0.0 ? (Gx * Dx + Gy * Dy) / DD : 0.0;
				T = T < 0.0 ? 0.0 : (T > 1.0 ? 1.0 : T);
				const double Qx = Jx + T * Dx - D[3 * k];
				const double Qy = Jy + T * Dy - D[3 * k + 1];
				R.bHidden = Qx * Qx + Qy * Qy < D[3 * k + 2] * D[3 * k + 2];
			}
		}
		return R;
	}
}

int main()
{
	int Bad = 0, Hidden = 0, First = -1;
	for (int c = 0; c < G::kCases; ++c)
	{
		const std::int32_t* I = G::kCaseInt + 4 * c;
		const double* In = G::kCaseIn + 10 * c;
		const double* D = G::kSetDiscs + 3 * G::kSetIndex[2 * I[1]];
		const FOut R = Slots(In[0], In[1], In[2], In[3], I[2] != 0, In[4], In[5], In[6], In[7], D, G::kSetIndex[2 * I[1] + 1], In[8], In[9], I[3] != 0);
		const double N = std::isinf(R.N) ? G::kNoDist : R.N;
		const float O[3] = {static_cast<float>(Clip01(R.E / G::kEscapeNorm)), static_cast<float>(Clip01((R.N > 0.0 ? R.N : 0.0) / G::kNearNorm)),
							R.bHidden ? 1.0f : 0.0f};
		const bool bOk = std::memcmp(&R.E, &G::kCaseOut[2 * c], sizeof(double)) == 0 && std::memcmp(&N, &G::kCaseOut[2 * c + 1], sizeof(double)) == 0
						 && static_cast<int>(R.bHidden) == G::kCaseHidden[c] && std::memcmp(O, &G::kCaseObs[3 * c], sizeof(O)) == 0;
		if (!bOk)
		{
			if (First < 0)
			{
				First = c;
				std::printf("first mismatch case %d: E %.17g / %.17g, N %.17g / %.17g, hidden %d / %d\n", c, R.E, G::kCaseOut[2 * c], N,
							G::kCaseOut[2 * c + 1], static_cast<int>(R.bHidden), G::kCaseHidden[c]);
			}
			++Bad;
		}
		Hidden += R.bHidden ? 1 : 0;
	}
	const bool bCounts = Hidden == G::kHiddenCases && G::kCases == G::kHandCases + G::kSceneCases + G::kRolloutCases && G::kObsDim == 21 && G::kFirstSlot == 18;
	std::printf("cases=%d mismatch=%d hidden=%d counts=%s\n", G::kCases, Bad, Hidden, bCounts ? "ok" : "bad");
	if (Bad == 0 && bCounts)
	{
		std::printf("PASS\n");
		return 0;
	}
	return 1;
}

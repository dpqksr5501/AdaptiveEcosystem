// EcoR10DemoMap.h — R10 데모: 언리얼이 훑은 땅을 R10 코어 지형 층(EcoR10::FMapLayers)으로 바꾸는 엔진 없는 부분 (2026-11-19).
//
// 언리얼 쪽(EcoR10DemoSubsystem.cpp)은 칸마다 땅 높이·수면·막힘·나무 갓·덤불·바위만 훑어 FR10Scan 에 담는다.
// 이 헤더가 그것을 파이썬 r10/mapgen.py 와 같은 규칙으로 코어 층을 만든다:
//   - 물 칸: 수면이 땅보다 5 cm 넘게 높은 칸 (WaterSys 1, WaterSurf0Z = 수면, WaterBedZ = 땅). 물 아닌 칸은 mapgen 처럼 수면 = 땅 − 1 m.
//   - 가림(cover_sight) = clip(덤불 + 0.8 × 나무 갓 + 1.0 × 바위, 0, 1) × 땅 — mapgen 과 같은 식 (덤불은 맵의 실제 덤불·고사리 메시에서).
//   - 은신처(cover_body) = 반지름 3~7 m 원, 나무 덩어리·큰 바위 곁 (mapgen 은 맵마다 0~8 개 — 120 m 정사각마다 4 개 꼴로 넓힘), 땅 칸만.
//     가림 = max(가림, 0.7 × 은신처) (mapgen 그대로).
//   - 먹이 8 층: mapgen 의 먹이 군락 규칙 그대로 (값 노이즈 패치 → 문턱 → 종류별 자리 조건: 풀 = 땅·그늘 < 0.3, 잎 = 땅, 나뭇잎 = 땅·그늘 > 0.05,
//     젖은 풀밭 = 땅·물가, 뿌리 = 땅, 벌레 = 어디나, 물풀 = 물, 떠내려옴 = 물·물살 — 물살 0 이라 없음). 바닥 용량·재생은 mapgen FOOD_BASE.
//   - 수위 주기: 진폭 0.1 m (물 있을 때) — 맵 물 몸체 수면은 그대로 두고 코어 안에서만 조금 오르내림. 물살 0.
// 난수: numpy 와 비트 같지는 않다 (언리얼 맵 전용 장면). 같은 시드면 같은 장면 (std::mt19937_64).
// 지킴: 세계 규칙·감각·두뇌는 코어(EcoR10Core.h) 그대로. 여기는 시작 장면 입력만 만든다. 표준 라이브러리만.
#pragma once

#include "EcoR10Core.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <random>
#include <string>
#include <vector>

namespace EcoR10Demo
{
	/** 언리얼 훑기 결과 (칸 차례 iy*W+ix, 코어 좌표 m — 언리얼 X → 코어 x, 언리얼 Y → 코어 y, 높이는 기준 높이 Z0 를 뺀 m). */
	struct FR10Scan
	{
		int W = 0, H = 0;
		double CellM = 1.0;
		std::vector<float> Ground;        // 땅 높이 m (NaN = 땅 못 찾음 → 막힘)
		std::vector<float> WaterSurf;     // 수면 높이 m (NaN = 물 없음)
		std::vector<uint8_t> Block;       // 나무 줄기·바위·건물
		std::vector<uint8_t> Canopy;      // 나무 갓
		std::vector<uint8_t> Rock;        // 바위 (가림 1.0)
		std::vector<float> Bush;          // 덤불·고사리 가림 0~1
		std::vector<double> Anchor;       // 은신처 곁 후보점 (x0, y0, x1, y1, …, 코어 m)
	};

	/** 만든 층 요약 (기록 줄). */
	struct FR10MapCounts
	{
		int Cells = 0, NoGround = 0, Water = 0, Blocked = 0, Canopy = 0, Shelters = 0, ShelterCells = 0;
		double FoodCapSum[EcoR10::kNumFoods] = {};
		double Abundance = 1.0;
	};

	namespace Detail
	{
		/** mapgen._upsample: 거친 격자 g (gh×gw) 를 (h×w) 로 쌍선형 보간. */
		inline void Upsample(const std::vector<double>& G, int Gh, int Gw, int H, int W, std::vector<double>& Out)
		{
			Out.assign(static_cast<size_t>(H) * W, 0.0);
			std::vector<int> X0(W), X1(W), Y0(H), Y1(H);
			std::vector<double> Fx(W), Fy(H);
			for (int x = 0; x < W; ++x)
			{
				const double S = W > 1 ? static_cast<double>(x) * (Gw - 1) / (W - 1) : 0.0;
				X0[x] = static_cast<int>(std::floor(S));
				X1[x] = std::min(X0[x] + 1, Gw - 1);
				Fx[x] = S - X0[x];
			}
			for (int y = 0; y < H; ++y)
			{
				const double S = H > 1 ? static_cast<double>(y) * (Gh - 1) / (H - 1) : 0.0;
				Y0[y] = static_cast<int>(std::floor(S));
				Y1[y] = std::min(Y0[y] + 1, Gh - 1);
				Fy[y] = S - Y0[y];
			}
			for (int y = 0; y < H; ++y)
			{
				for (int x = 0; x < W; ++x)
				{
					const double A = G[Y0[y] * Gw + X0[x]] * (1 - Fx[x]) + G[Y0[y] * Gw + X1[x]] * Fx[x];
					const double B = G[Y1[y] * Gw + X0[x]] * (1 - Fx[x]) + G[Y1[y] * Gw + X1[x]] * Fx[x];
					Out[static_cast<size_t>(y) * W + x] = A * (1 - Fy[y]) + B * Fy[y];
				}
			}
		}

		/** mapgen.noise: 값 노이즈 여러 겹 → 대략 [-1, 1]. */
		inline std::vector<double> Noise(std::mt19937_64& Rng, int H, int W, int Octaves, double BaseCells)
		{
			std::uniform_real_distribution<double> U(-1.0, 1.0);
			std::vector<double> Out(static_cast<size_t>(H) * W, 0.0), Up;
			double Amp = 1.0, Tot = 0.0;
			for (int o = 0; o < Octaves; ++o)
			{
				const double Cells = BaseCells / std::pow(2.0, o);
				const int Gh = std::max(2, static_cast<int>(std::ceil(H / Cells)) + 1);
				const int Gw = std::max(2, static_cast<int>(std::ceil(W / Cells)) + 1);
				std::vector<double> G(static_cast<size_t>(Gh) * Gw);
				for (double& V : G)
				{
					V = U(Rng);
				}
				Upsample(G, Gh, Gw, H, W, Up);
				for (size_t k = 0; k < Out.size(); ++k)
				{
					Out[k] += Amp * Up[k];
				}
				Tot += Amp;
				Amp *= 0.5;
			}
			for (double& V : Out)
			{
				V /= Tot;
			}
			return Out;
		}

		/** mapgen.blur: 상자 흐림 (반지름 r 칸, 가장자리는 늘림). */
		inline std::vector<double> Blur(const std::vector<double>& A, int H, int W, int R)
		{
			if (R <= 0)
			{
				return A;
			}
			const int Ph = H + 2 * R, Pw = W + 2 * R;
			std::vector<double> C(static_cast<size_t>(Ph + 1) * (Pw + 1), 0.0);   // 누적합 (위·왼쪽 0 줄)
			for (int y = 0; y < Ph; ++y)
			{
				const int Sy = std::min(std::max(y - R, 0), H - 1);
				double Row = 0.0;
				for (int x = 0; x < Pw; ++x)
				{
					const int Sx = std::min(std::max(x - R, 0), W - 1);
					Row += A[static_cast<size_t>(Sy) * W + Sx];
					C[static_cast<size_t>(y + 1) * (Pw + 1) + (x + 1)] = C[static_cast<size_t>(y) * (Pw + 1) + (x + 1)] + Row;
				}
			}
			const int K = 2 * R + 1;
			std::vector<double> Out(static_cast<size_t>(H) * W);
			for (int y = 0; y < H; ++y)
			{
				for (int x = 0; x < W; ++x)
				{
					auto At = [&C, Pw](int Yy, int Xx) { return C[static_cast<size_t>(Yy) * (Pw + 1) + Xx]; };
					const double S = At(y + K, x + K) - At(y, x + K) - At(y + K, x) + At(y, x);
					Out[static_cast<size_t>(y) * W + x] = S / (K * K);
				}
			}
			return Out;
		}
	}

	/** mapgen FOOD_BASE (셀당 용량, 재생/s) — grass, forbs, browse, wet_meadow, roots, insects, aquatic, drift. */
	inline const double* FoodBase()
	{
		static const double T[EcoR10::kNumFoods][2] = {{1.0, 0.0020}, {0.8, 0.0015}, {1.2, 0.0010}, {1.2, 0.0025},
													   {0.6, 0.0008}, {0.3, 0.0030}, {0.8, 0.0020}, {0.4, 0.0040}};
		return &T[0][0];
	}

	/**
	 * 훑기 → 코어 층. 실패(크기 0·배열 크기 틀림)면 거짓.
	 * ShelterPer120 = 120 m 정사각마다 은신처 수 (mapgen 은 맵마다 0~8, 가운데 4).
	 */
	inline bool BuildLayers(const FR10Scan& In, uint64_t Seed, double ShelterPer120, EcoR10::FMapLayers& M, FR10MapCounts& Out, std::string* Err)
	{
		const int W = In.W, H = In.H;
		const size_t N = static_cast<size_t>(W) * H;
		if (W < 8 || H < 8 || In.Ground.size() != N || In.WaterSurf.size() != N || In.Block.size() != N || In.Canopy.size() != N
			|| In.Rock.size() != N || In.Bush.size() != N)
		{
			if (Err)
			{
				*Err = "R10 훑기 배열 크기가 맞지 않음";
			}
			return false;
		}
		std::mt19937_64 Rng(Seed * 0x9E3779B97F4A7C15ull + 0x5210);
		std::uniform_real_distribution<double> U01(0.0, 1.0);
		auto Uni = [&Rng, &U01](double Lo, double Hi) { return Lo + (Hi - Lo) * U01(Rng); };

		M = EcoR10::FMapLayers();
		M.W = W;
		M.H = H;
		M.CellM = In.CellM;
		M.GroundZ.assign(N, 0.0f);
		M.WaterBedZ.assign(N, 0.0f);
		M.WaterSurf0Z.assign(N, 0.0f);
		M.CoverSight.assign(N, 0.0f);
		M.CurrentX.assign(N, 0.0f);
		M.CurrentY.assign(N, 0.0f);
		M.WaterSys.assign(N, 0);
		M.Block.assign(N, 0);
		M.Shelter.assign(N, 0);
		M.Canopy.assign(N, 0);
		Out = FR10MapCounts();
		Out.Cells = static_cast<int>(N);

		// 땅 못 찾은 칸: 가장 낮은 땅 높이 + 막힘
		float MinZ = 0.0f;
		bool bAny = false;
		for (size_t k = 0; k < N; ++k)
		{
			if (std::isfinite(In.Ground[k]))
			{
				MinZ = bAny ? std::min(MinZ, In.Ground[k]) : In.Ground[k];
				bAny = true;
			}
		}
		if (!bAny)
		{
			if (Err)
			{
				*Err = "R10 훑기: 땅을 한 칸도 못 찾음 (지형이 아직 안 불렸나)";
			}
			return false;
		}
		std::vector<double> WaterAny(N, 0.0), CanopyD(N, 0.0);
		std::vector<uint8_t> Land(N, 0);
		for (size_t k = 0; k < N; ++k)
		{
			const bool bGround = std::isfinite(In.Ground[k]);
			const float Z = bGround ? In.Ground[k] : MinZ;
			M.GroundZ[k] = Z;
			const bool bWater = bGround && std::isfinite(In.WaterSurf[k]) && In.WaterSurf[k] > Z + 0.05f;
			if (bWater)
			{
				M.WaterSys[k] = 1;
				M.WaterSurf0Z[k] = In.WaterSurf[k];
				M.WaterBedZ[k] = Z;
				WaterAny[k] = 1.0;
				++Out.Water;
			}
			else
			{
				M.WaterSurf0Z[k] = Z - 1.0f;   // mapgen: surf0 = z − 1 (물 없는 칸)
				M.WaterBedZ[k] = Z;
			}
			const bool bBlock = !bGround || (!bWater && In.Block[k] != 0);
			M.Block[k] = bBlock ? 1 : 0;
			M.Canopy[k] = (!bWater && In.Canopy[k] != 0) ? 1 : 0;
			CanopyD[k] = M.Canopy[k];
			Land[k] = (bGround && !bWater) ? 1 : 0;
			Out.NoGround += bGround ? 0 : 1;
			Out.Blocked += bBlock ? 1 : 0;
			Out.Canopy += M.Canopy[k];
		}
		// 가림: mapgen cover_sight = clip(bush + 0.8 canopy + 1.0 rocks, 0, 1) * land
		for (size_t k = 0; k < N; ++k)
		{
			const double C = std::min(1.0, std::max(0.0, static_cast<double>(In.Bush[k]) + 0.8 * M.Canopy[k] + 1.0 * (In.Rock[k] ? 1.0 : 0.0)));
			M.CoverSight[k] = static_cast<float>(C * Land[k]);
		}
		// 은신처: 나무·바위 곁 후보점에서 (없으면 땅 아무 곳), 반지름 3~7 m, 땅 칸만
		const double AreaM2 = W * In.CellM * H * In.CellM;
		const int NumShelter = std::max(2, std::min(60, static_cast<int>(std::lround(AreaM2 / (120.0 * 120.0) * ShelterPer120))));
		const int NAnchor = static_cast<int>(In.Anchor.size() / 2);
		for (int s = 0; s < NumShelter; ++s)
		{
			double Cx = 0, Cy = 0;
			bool bOk = false;
			for (int Try = 0; Try < 40 && !bOk; ++Try)
			{
				if (NAnchor > 0)
				{
					const int A = static_cast<int>(U01(Rng) * NAnchor) % NAnchor;
					const double Ang = Uni(0.0, 6.283185307179586), R = Uni(2.0, 6.0);
					Cx = In.Anchor[2 * A] + R * std::cos(Ang);
					Cy = In.Anchor[2 * A + 1] + R * std::sin(Ang);
				}
				else
				{
					Cx = Uni(0.0, W * In.CellM);
					Cy = Uni(0.0, H * In.CellM);
				}
				const int Ix = static_cast<int>(std::floor(Cx / In.CellM)), Iy = static_cast<int>(std::floor(Cy / In.CellM));
				bOk = Ix >= 0 && Iy >= 0 && Ix < W && Iy < H && Land[static_cast<size_t>(Iy) * W + Ix] && !M.Block[static_cast<size_t>(Iy) * W + Ix];
			}
			if (!bOk)
			{
				continue;
			}
			const double R = Uni(3.0, 7.0);
			const int Rc = static_cast<int>(std::ceil(R / In.CellM)) + 1;
			const int Ix = static_cast<int>(std::floor(Cx / In.CellM)), Iy = static_cast<int>(std::floor(Cy / In.CellM));
			for (int y = std::max(0, Iy - Rc); y <= std::min(H - 1, Iy + Rc); ++y)
			{
				for (int x = std::max(0, Ix - Rc); x <= std::min(W - 1, Ix + Rc); ++x)
				{
					const size_t k = static_cast<size_t>(y) * W + x;
					if (Land[k] && std::hypot((x + 0.5) * In.CellM - Cx, (y + 0.5) * In.CellM - Cy) < R && !M.Shelter[k])
					{
						M.Shelter[k] = 1;
						M.CoverSight[k] = std::max(M.CoverSight[k], 0.7f);
						++Out.ShelterCells;
					}
				}
			}
			++Out.Shelters;
		}
		// 먹이 군락 (mapgen 그대로)
		M.FoodAmount.assign(N * EcoR10::kNumFoods, 0.0f);
		M.FoodCap.assign(N * EcoR10::kNumFoods, 0.0f);
		M.FoodRegen.assign(N * EcoR10::kNumFoods, 0.0f);
		M.FoodDry.assign(N * EcoR10::kNumFoods, 0.0f);
		const double Abund = Uni(0.5, 2.0);
		Out.Abundance = Abund;
		const std::vector<double> NearW = Detail::Blur(WaterAny, H, W, 3);
		const std::vector<double> Shade = Detail::Blur(CanopyD, H, W, 3);
		const double* FB = FoodBase();
		std::vector<double> Cap(N);
		std::vector<double> Regen(N);
		std::vector<std::vector<double>> CapAll(EcoR10::kNumFoods), RegenAll(EcoR10::kNumFoods);
		for (int f = 0; f < EcoR10::kNumFoods; ++f)
		{
			const double BaseCap = FB[2 * f], BaseRegen = FB[2 * f + 1];
			const double Scale = Uni(15.0, 40.0);
			std::vector<double> Patch = Detail::Noise(Rng, H, W, 3, Scale);
			const double Cut = Uni(-0.1, 0.3);
			const double RegenJ = Uni(0.6, 1.4);
			CapAll[f].assign(N, 0.0);
			RegenAll[f].assign(N, 0.0);
			for (size_t k = 0; k < N; ++k)
			{
				const bool bLand = Land[k] != 0;
				const bool bWater = WaterAny[k] > 0.5;
				bool bWhere = false;
				switch (f)
				{
				case 0: bWhere = bLand && Shade[k] < 0.3; break;        // grass
				case 1: bWhere = bLand; break;                          // forbs
				case 2: bWhere = bLand && Shade[k] > 0.05; break;       // browse
				case 3: bWhere = bLand && NearW[k] > 0.05; break;       // wet_meadow
				case 4: bWhere = bLand; break;                          // roots
				case 5: bWhere = true; break;                           // insects
				case 6: bWhere = bWater; break;                         // aquatic
				default: bWhere = false; break;                         // drift (물살 0)
				}
				const double P = std::min(1.0, std::max(0.0, std::min(1.0, std::max(0.0, Patch[k] - Cut)) * 2.0));
				const double C = bWhere ? P * BaseCap * Abund * (1.0 - M.Block[k]) : 0.0;
				CapAll[f][k] = C;
				RegenAll[f][k] = C > 0.0 ? BaseRegen * Abund * RegenJ : 0.0;
			}
		}
		const double AmountJ = Uni(0.3, 1.0);   // mapgen: amount = cap × U(0.3, 1.0) (한 수)
		const double DryJ = Uni(0.0, 0.3);      // mapgen: dry = regen × U(0, 0.3)
		for (int f = 0; f < EcoR10::kNumFoods; ++f)
		{
			for (size_t k = 0; k < N; ++k)
			{
				const size_t j = static_cast<size_t>(f) * N + k;
				M.FoodCap[j] = static_cast<float>(CapAll[f][k]);
				M.FoodAmount[j] = static_cast<float>(CapAll[f][k] * AmountJ);
				M.FoodRegen[j] = static_cast<float>(RegenAll[f][k]);
				M.FoodDry[j] = static_cast<float>(RegenAll[f][k] * DryJ);
				Out.FoodCapSum[f] += CapAll[f][k];
			}
		}
		// 수위 주기: 물이 있으면 작게
		M.Water = EcoR10::FWaterCycle();
		M.Water.AmpM = Out.Water > 0 ? 0.1 : 0.0;
		M.Water.RiseS = Uni(20, 60);
		M.Water.HighS = Uni(10, 40);
		M.Water.FallS = Uni(30, 80);
		M.Water.LowS = Uni(20, 60);
		M.Water.PhaseS = Uni(0, 200);
		M.Water.RainRiseM = 0.0;
		return M.Check(Err);
	}
}

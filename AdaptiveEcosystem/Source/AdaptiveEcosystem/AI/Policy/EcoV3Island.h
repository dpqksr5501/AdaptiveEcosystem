// 섬 무대 땅/물 지도 (2026-11-05, Docs/RL_Policy/ISLAND_STAGE.md 3절) — 엔진 없는 순수 헤더.
//
// 섬 무대 모드(eco.IntegratedV3.Island, 복사 맵 /Game/EcoTest/Maps/LV_EcoV3_Island 의 조정자 bV3IslandStage)는 지역 세계 하나를 섬 전체 정사각으로 만들고,
// 정사각 벽 대신 이 지도의 '막힌 칸'(바다·호수·가파름·숲·큰 바위·지형 없음)을 못 가는 곳으로 쓴다. 지도는 서버·단독이 Play 시작 때 한 번 훑어 만든다
// (EcoV3IslandStage.cpp). 칸은 먹이 칸과 같은 2 단위(4 m)이고 무대 원점 (0, 0) 에서 시작한다 — 먹이 칸 (ix, iy) = 지도 칸 (ix, iy).
//
// 세계 규칙에 넣는 곳 (모두 FWorldConfig::Island 가 있을 때만 — 없으면 지금 그대로, 비트 단위로 같다):
//   - 먹이 격자 Build: 막힌 칸은 용량 0 (먹이가 나지 않는다)
//   - 사슴 이동: 다음 자리가 막힌 칸이면 x 만 → y 만 순서로 미끄러지고, 둘 다 안 되면 제자리 (Slide). heading 은 가려던 쪽 그대로
//   - 사슴 해안 굽힘: 해안 거리 kShoreEdgeR 안에서 해안 쪽으로 가면 그 몫을 해안을 따라가는 쪽으로 돌린다 (ShoreSteer — 가장자리 굽히기 WildEdgeSteer 의 꼴)
//   - 늑대 이동: 다음 자리가 막힌 칸이면 제자리에 두고 heading 을 해안 안쪽 법선으로 반사한다 (Reflect — 벽 반사의 꼴)
//   - 관측 escape_room: min(벽, 그 방향 첫 막힌 칸) — 0.5 단위 걸음 (RayBlocked)
//
// 격자 밖은 '막힘'으로 보지 않는다 (정사각 벽이 따로 막는다). 그래서 모든 칸이 열린 지도는 모든 규칙에서 아무것도 하지 않는다 — 자동화 시험
// Policy.V3.Island.OpenMaskNoOp 이 이를 지킨다.

#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <vector>

namespace EcoV3Island
{
	/** 칸 종류 (기록 줄 순서). kLand 만 열려 있다. */
	enum ECell : std::uint8_t
	{
		kLand = 0,       // 땅 (먹이가 나고 다닐 수 있다)
		kNoGround = 1,   // 지형 없음 (높이를 못 읽음 — 스트리밍이 덜 됐거나 지형 밖)
		kSea = 2,        // 바다 (땅 높이 ≤ 바다 수면 + 여유)
		kLake = 3,       // 호수·강 (물 몸체 충돌 아래이고 땅 < 수면 + 여유)
		kSteep = 4,      // 가파름 (법선 Z < 문턱)
		kForest = 5,     // 숲 (칸 가운데에서 나무 반지름 안에 나무 인스턴스)
		kRock = 6,       // 큰 바위 (바위 인스턴스 상자 + 여유 안)
		kNumKinds = 7
	};

	inline const char* KindNameKoUtf8(std::int32_t K)
	{
		switch (K)
		{
		case kLand: return "땅";
		case kNoGround: return "지형 없음";
		case kSea: return "바다";
		case kLake: return "호수";
		case kSteep: return "가파름";
		case kForest: return "숲";
		case kRock: return "바위";
		default: return "?";
		}
	}

	/** 사슴 해안 굽힘 거리 (단위 — 10 m, 도주 가장자리 굽히기 FWildFlightConfig::EdgeR 5 와 같다). */
	inline constexpr double kShoreEdgeR = 5.0;
	/** escape_room 광선 길이 상한 (단위). 관측 분모 10 단위보다 길게 본다. */
	inline constexpr double kRayMax = 16.0;
	/** 광선 걸음 (단위). */
	inline constexpr double kRayStep = 0.5;

	struct FLandMask
	{
		std::int32_t Gw = 0;               // 한 변 칸 수 (정사각)
		double Cell = 2.0;                 // 칸 한 변 (단위)
		std::vector<std::uint8_t> Kind;    // 행 우선 iy·Gw + ix
		std::vector<float> Dist;           // 칸 가운데에서 가장 가까운 막힌 칸 가운데까지 (칸 수, 8 이웃 거리 변환). 막힌 칸 0. 막힌 칸이 없으면 큰 값
		double LandTopZ = 0.0;             // 땅 칸 지형의 가장 높은 곳 (엔진 높이 cm — 훑기가 채운다. 세계 규칙에는 쓰지 않는다, 카메라 탑뷰 초점 높이)

		bool Valid() const { return Gw > 0 && Kind.size() == static_cast<size_t>(Gw) * static_cast<size_t>(Gw); }
		bool InGrid(std::int32_t X, std::int32_t Y) const { return X >= 0 && Y >= 0 && X < Gw && Y < Gw; }
		size_t Index(std::int32_t X, std::int32_t Y) const { return static_cast<size_t>(Y) * static_cast<size_t>(Gw) + static_cast<size_t>(X); }
		std::int32_t CellCoord(double V) const { return static_cast<std::int32_t>(std::floor(V / Cell)); }

		/** 칸이 막혔나 (격자 밖은 막히지 않음 — 정사각 벽이 따로 막는다). */
		bool CellBlocked(std::int32_t X, std::int32_t Y) const { return InGrid(X, Y) && Kind[Index(X, Y)] != kLand; }
		bool IsOpen(double X, double Y) const
		{
			if (!(X == X) || !(Y == Y))
			{
				return false;
			}
			return !CellBlocked(CellCoord(X), CellCoord(Y));
		}

		/** 해안 거리 (단위): 막힌 칸 둘레까지의 어림 = (칸 거리 − 0.5) × Cell. 막힌 칸·지도 없음 0, 막힌 칸이 없으면 큰 값. */
		double ShoreDist(double X, double Y) const
		{
			if (!Valid() || Dist.size() != Kind.size())
			{
				return std::numeric_limits<double>::infinity();
			}
			const std::int32_t Cx = CellCoord(X);
			const std::int32_t Cy = CellCoord(Y);
			if (!InGrid(Cx, Cy))
			{
				return std::numeric_limits<double>::infinity();
			}
			const double D = static_cast<double>(Dist[Index(Cx, Cy)]);
			return D <= 0.0 ? 0.0 : std::max(0.0, (D - 0.5) * Cell);
		}

		/** 해안 안쪽 법선 (막힌 곳에서 멀어지는 쪽 단위벡터, 거리장 중앙 차분). 거리장이 평평하면 (0, 0). */
		void InwardNormal(double X, double Y, double& Nx, double& Ny) const
		{
			Nx = 0.0;
			Ny = 0.0;
			if (!Valid() || Dist.size() != Kind.size())
			{
				return;
			}
			const std::int32_t Cx = CellCoord(X);
			const std::int32_t Cy = CellCoord(Y);
			auto D = [this, Cx, Cy](std::int32_t Dx, std::int32_t Dy) -> double
			{
				const std::int32_t Px = std::min(std::max(Cx + Dx, 0), Gw - 1);
				const std::int32_t Py = std::min(std::max(Cy + Dy, 0), Gw - 1);
				return static_cast<double>(Dist[Index(Px, Py)]);
			};
			if (!InGrid(Cx, Cy))
			{
				return;
			}
			// 3×3 소벨 (대각 이웃까지 — 한 칸 차분보다 덜 들쭉날쭉하다)
			const double Gx = (D(1, -1) + 2.0 * D(1, 0) + D(1, 1)) - (D(-1, -1) + 2.0 * D(-1, 0) + D(-1, 1));
			const double Gy = (D(-1, 1) + 2.0 * D(0, 1) + D(1, 1)) - (D(-1, -1) + 2.0 * D(0, -1) + D(1, -1));
			const double L = std::sqrt(Gx * Gx + Gy * Gy);
			if (L > 1e-9 && std::isfinite(L))
			{
				Nx = Gx / L;
				Ny = Gy / L;
			}
		}

		/** 8 이웃 두 번 훑기 거리 변환 (곧은 1, 대각 √2). 막힌 칸 0. 막힌 칸이 없으면 모든 칸이 큰 값으로 남는다. */
		void BuildDistance()
		{
			const float Big = 1.0e9f;
			Dist.assign(Kind.size(), Big);
			if (!Valid())
			{
				return;
			}
			for (size_t k = 0; k < Kind.size(); ++k)
			{
				if (Kind[k] != kLand)
				{
					Dist[k] = 0.0f;
				}
			}
			const float D1 = 1.0f;
			const float D2 = 1.41421356f;
			auto Relax = [this](std::int32_t Nx, std::int32_t Ny, float W, float& V)
			{
				if (InGrid(Nx, Ny))
				{
					const float C = Dist[Index(Nx, Ny)] + W;
					V = C < V ? C : V;
				}
			};
			for (std::int32_t Y = 0; Y < Gw; ++Y)
			{
				for (std::int32_t X = 0; X < Gw; ++X)
				{
					float V = Dist[Index(X, Y)];
					Relax(X - 1, Y, D1, V);
					Relax(X, Y - 1, D1, V);
					Relax(X - 1, Y - 1, D2, V);
					Relax(X + 1, Y - 1, D2, V);
					Dist[Index(X, Y)] = V;
				}
			}
			for (std::int32_t Y = Gw - 1; Y >= 0; --Y)
			{
				for (std::int32_t X = Gw - 1; X >= 0; --X)
				{
					float V = Dist[Index(X, Y)];
					Relax(X + 1, Y, D1, V);
					Relax(X, Y + 1, D1, V);
					Relax(X + 1, Y + 1, D2, V);
					Relax(X - 1, Y + 1, D2, V);
					Dist[Index(X, Y)] = V;
				}
			}
		}

		std::int64_t Count(std::int32_t K) const
		{
			std::int64_t N = 0;
			for (const std::uint8_t V : Kind)
			{
				N += V == K ? 1 : 0;
			}
			return N;
		}

		/** 지문 (FNV-1a 64: 칸 수·칸 크기(1/1000 단위)·칸 종류 바이트). 같은 지형·물·나무면 같다. */
		std::uint64_t Fingerprint() const
		{
			std::uint64_t H = 1469598103934665603ULL;
			auto Mix = [&H](std::uint8_t B)
			{
				H ^= B;
				H *= 1099511628211ULL;
			};
			const std::int64_t Head[2] = {Gw, static_cast<std::int64_t>(std::llround(Cell * 1000.0))};
			for (const std::int64_t V : Head)
			{
				for (int b = 0; b < 8; ++b)
				{
					Mix(static_cast<std::uint8_t>((static_cast<std::uint64_t>(V) >> (8 * b)) & 0xFF));
				}
			}
			for (const std::uint8_t V : Kind)
			{
				Mix(V);
			}
			return H;
		}

		/**
		 * 사슴 미끄러짐: P → Q 가 막힌 칸으로 가면 (Qx, Py) → (Px, Qy) 순서로 열린 쪽 (한 축이라도 움직이는 쪽), 둘 다 안 되면 해안을 따라 (P 의 안쪽 법선에
		 * 수직인 두 방향 가운데 가려던 쪽과 가까운 쪽, 같은 걸음 길이), 그것도 막히면 P. 0 = 그대로, 1 = 미끄러짐, 2 = 제자리.
		 * P 가 막힌 칸이면 (시작 자리 어긋남 등) 막지 않는다 — 갇히지 않게.
		 */
		std::int32_t Slide(double Px, double Py, double& Qx, double& Qy) const
		{
			if (IsOpen(Qx, Qy) || !IsOpen(Px, Py))
			{
				return 0;
			}
			if (Qx != Px && IsOpen(Qx, Py))
			{
				Qy = Py;
				return 1;
			}
			if (Qy != Py && IsOpen(Px, Qy))
			{
				Qx = Px;
				return 1;
			}
			const double Vx = Qx - Px;
			const double Vy = Qy - Py;
			const double Len = std::sqrt(Vx * Vx + Vy * Vy);
			double Nx = 0.0, Ny = 0.0;
			InwardNormal(Px, Py, Nx, Ny);
			if (Len > 1e-9 && (Nx != 0.0 || Ny != 0.0))
			{
				// 접선 (−Ny, Nx) 를 가려던 쪽 부호로 (0 이면 왼쪽)
				const double Sg = (Vx * -Ny + Vy * Nx) < 0.0 ? -1.0 : 1.0;
				for (const double S : {Sg, -Sg})
				{
					const double Tx = Px + S * -Ny * Len;
					const double Ty = Py + S * Nx * Len;
					if (IsOpen(Tx, Ty))
					{
						Qx = Tx;
						Qy = Ty;
						return 1;
					}
				}
			}
			Qx = Px;
			Qy = Py;
			return 2;
		}

		/** 늑대 반사: heading (Hx, Hy) 를 P 의 안쪽 법선 n 으로 반사 (H·n < 0 일 때 H − 2(H·n)n). 법선이 없으면 뒤집는다. 단위화한다. */
		void Reflect(double Px, double Py, double& Hx, double& Hy) const
		{
			double Nx = 0.0, Ny = 0.0;
			InwardNormal(Px, Py, Nx, Ny);
			if (Nx == 0.0 && Ny == 0.0)
			{
				Hx = -Hx;
				Hy = -Hy;
			}
			else
			{
				const double Dot = Hx * Nx + Hy * Ny;
				if (Dot < 0.0)
				{
					Hx = Hx - 2.0 * Dot * Nx;
					Hy = Hy - 2.0 * Dot * Ny;
				}
				else
				{
					// 이미 안쪽을 본다 (막힌 칸이 법선 반대편 모서리에 있다): 법선 쪽으로 돈다
					Hx = Nx;
					Hy = Ny;
				}
			}
			const double L = std::sqrt(Hx * Hx + Hy * Hy);
			if (L > 1e-12)
			{
				Hx /= L;
				Hy /= L;
			}
		}

		/** (X, Y) 에서 단위 방향 (Ux, Uy) 로 kRayStep 걸음마다 볼 때 처음 막힌 거리 (단위). MaxD 안에 없으면 +∞. */
		double RayBlocked(double X, double Y, double Ux, double Uy, double MaxD = kRayMax) const
		{
			const std::int32_t Steps = static_cast<std::int32_t>(std::floor(MaxD / kRayStep));
			for (std::int32_t s = 1; s <= Steps; ++s)
			{
				const double T = s * kRayStep;
				if (!IsOpen(X + Ux * T, Y + Uy * T))
				{
					return T;
				}
			}
			return std::numeric_limits<double>::infinity();
		}

		/**
		 * 해안 굽힘 (사슴 이동 방향, 크기는 그대로): 해안 거리 E < EdgeR 이고 (Vx, Vy) 가 해안 쪽(V·n < 0)이면 해안 쪽 성분의 W = 1 − E/EdgeR 몫을
		 * 해안을 따라가는 쪽으로 돌린다 (가장자리 굽히기 WildEdgeSteer 한 축의 꼴 — 따라갈 쪽은 V 의 접선 성분 부호, 0 이면 법선을 왼쪽으로 돈 쪽).
		 * 바꿨으면 참.
		 */
		bool ShoreSteer(double Px, double Py, double& Vx, double& Vy, double EdgeR = kShoreEdgeR) const
		{
			const double Sp = std::sqrt(Vx * Vx + Vy * Vy);
			if (!(Sp > 1e-9) || !(EdgeR > 0.0) || !IsOpen(Px, Py))
			{
				return false;
			}
			const double E = ShoreDist(Px, Py);
			if (!(E < EdgeR))
			{
				return false;
			}
			double Nx = 0.0, Ny = 0.0;
			InwardNormal(Px, Py, Nx, Ny);
			if (Nx == 0.0 && Ny == 0.0)
			{
				return false;
			}
			const double Dx = Vx / Sp;
			const double Dy = Vy / Sp;
			const double Dn = Dx * Nx + Dy * Ny;
			if (!(Dn < 0.0))
			{
				return false;
			}
			const double W = 1.0 - E / EdgeR;
			const double B = -Dn * W;
			// 접선 t = 법선을 왼쪽으로 돈 쪽 (−Ny, Nx). D 의 접선 성분 부호를 따른다
			const double Tx0 = -Ny;
			const double Ty0 = Nx;
			const double Dt = Dx * Tx0 + Dy * Ty0;
			const double Sg = Dt < 0.0 ? -1.0 : 1.0;
			double Sx = Dx + B * Nx + B * Sg * Tx0;
			double Sy = Dy + B * Ny + B * Sg * Ty0;
			const double L = std::sqrt(Sx * Sx + Sy * Sy);
			if (!(L > 1e-9))
			{
				return false;
			}
			Vx = Sx / L * Sp;
			Vy = Sy / L * Sp;
			return true;
		}

		/** 가장 가까운 열린 칸 가운데 (칸 거리 MaxCells 안, 고리 차례 — 같은 고리는 y·x 가 작은 쪽 먼저). 없으면 거짓. */
		bool NearestOpen(double X, double Y, double& OutX, double& OutY, std::int32_t MaxCells = 64) const
		{
			if (!Valid())
			{
				return false;
			}
			const std::int32_t Cx = CellCoord(X);
			const std::int32_t Cy = CellCoord(Y);
			double Best = std::numeric_limits<double>::infinity();
			for (std::int32_t R = 0; R <= MaxCells; ++R)
			{
				for (std::int32_t Yy = Cy - R; Yy <= Cy + R; ++Yy)
				{
					for (std::int32_t Xx = Cx - R; Xx <= Cx + R; ++Xx)
					{
						if (std::max(std::abs(Xx - Cx), std::abs(Yy - Cy)) != R || !InGrid(Xx, Yy) || Kind[Index(Xx, Yy)] != kLand)
						{
							continue;
						}
						const double Ox = (Xx + 0.5) * Cell;
						const double Oy = (Yy + 0.5) * Cell;
						const double D = (Ox - X) * (Ox - X) + (Oy - Y) * (Oy - Y);
						if (D < Best)
						{
							Best = D;
							OutX = Ox;
							OutY = Oy;
						}
					}
				}
				if (Best < std::numeric_limits<double>::infinity())
				{
					return true;
				}
			}
			return false;
		}

		/** 땅 칸 경계 상자 (단위, [X0, X1] × [Y0, Y1] — 칸 가장자리). 땅이 없으면 거짓. */
		bool LandBounds(double& X0, double& Y0, double& X1, double& Y1) const
		{
			std::int32_t Lx = Gw, Ly = Gw, Hx = -1, Hy = -1;
			for (std::int32_t Y = 0; Y < Gw; ++Y)
			{
				for (std::int32_t X = 0; X < Gw; ++X)
				{
					if (Kind[Index(X, Y)] == kLand)
					{
						Lx = std::min(Lx, X);
						Ly = std::min(Ly, Y);
						Hx = std::max(Hx, X);
						Hy = std::max(Hy, Y);
					}
				}
			}
			if (Hx < 0)
			{
				return false;
			}
			X0 = Lx * Cell;
			Y0 = Ly * Cell;
			X1 = (Hx + 1) * Cell;
			Y1 = (Hy + 1) * Cell;
			return true;
		}

		/** 땅 칸 가운데의 평균 (단위). 땅이 없으면 거짓. */
		bool LandCentroid(double& OutX, double& OutY) const
		{
			double Sx = 0.0, Sy = 0.0;
			std::int64_t N = 0;
			for (std::int32_t Y = 0; Y < Gw; ++Y)
			{
				for (std::int32_t X = 0; X < Gw; ++X)
				{
					if (Kind[Index(X, Y)] == kLand)
					{
						Sx += (X + 0.5) * Cell;
						Sy += (Y + 0.5) * Cell;
						++N;
					}
				}
			}
			if (N == 0)
			{
				return false;
			}
			OutX = Sx / static_cast<double>(N);
			OutY = Sy / static_cast<double>(N);
			return true;
		}
	};

	/** 무리 자리 고르기 입력 (단위). */
	struct FSiteParams
	{
		double SizeUnits = 60.0;     // 무리 자리 정사각 한 변 (학습 무대 한 변)
		double ClearUnits = 15.0;    // 자리 둘레 여유 (해안·숲·호수에서 이만큼 더 떨어진다, 30 m)
		double GapUnits = 200.0;     // 자리 가운데끼리 가장 가까운 거리 (400 m)
		std::int32_t Count = 4;
		double PrefX = 0.0;          // 첫 자리는 이 점에 가장 가까운 후보 (섬 땅 무게중심)
		double PrefY = 0.0;
		std::int32_t StrideCells = 5;   // 후보 간격 (칸 — 20 m)
	};

	struct FSiteResult
	{
		std::vector<double> Sites;      // (x, y) × n, 단위 — 자리 정사각 가운데
		std::int64_t Candidates = 0;    // 여유 정사각이 모두 땅인 후보 수
		double ClearUsed = 0.0;         // 실제로 쓴 여유 (후보가 없으면 반씩 줄인다)
	};

	/** 정사각 [X0, X1) × [Y0, Y1) (칸) 의 막힌 칸 수 (합계표 S 는 (Gw+1)² 행 우선). */
	inline std::int64_t BlockedIn(const std::vector<std::int32_t>& S, std::int32_t Gw, std::int32_t X0, std::int32_t Y0, std::int32_t X1, std::int32_t Y1)
	{
		const std::int32_t W = Gw + 1;
		return static_cast<std::int64_t>(S[static_cast<size_t>(Y1) * W + X1]) - S[static_cast<size_t>(Y0) * W + X1] - S[static_cast<size_t>(Y1) * W + X0]
			   + S[static_cast<size_t>(Y0) * W + X0];
	}

	/** 정사각 (가운데 Cx, Cy, 한 변 Side — 단위) 안 칸이 모두 땅인가 (격자 밖으로 나가면 거짓). */
	inline bool SquareOpen(const FLandMask& M, double Cx, double Cy, double Side)
	{
		if (!M.Valid())
		{
			return false;
		}
		const std::int32_t X0 = M.CellCoord(Cx - 0.5 * Side);
		const std::int32_t Y0 = M.CellCoord(Cy - 0.5 * Side);
		const std::int32_t X1 = M.CellCoord(Cx + 0.5 * Side - 1e-9);
		const std::int32_t Y1 = M.CellCoord(Cy + 0.5 * Side - 1e-9);
		if (X0 < 0 || Y0 < 0 || X1 >= M.Gw || Y1 >= M.Gw)
		{
			return false;
		}
		for (std::int32_t Y = Y0; Y <= Y1; ++Y)
		{
			for (std::int32_t X = X0; X <= X1; ++X)
			{
				if (M.Kind[M.Index(X, Y)] != kLand)
				{
					return false;
				}
			}
		}
		return true;
	}

	/**
	 * 무리 자리 고르기 (결정적): 후보 = StrideCells 칸 간격 격자점 가운데 (자리 한 변 + 2·여유) 정사각 안 칸이 모두 땅인 점. 첫 자리는 (PrefX, PrefY) 에 가장
	 * 가까운 후보, 다음은 이미 고른 자리들까지 가장 가까운 거리가 가장 큰 후보 (가장 먼 점 고르기 — 같으면 먼저 본 후보 = y·x 가 작은 쪽). 그 거리가 GapUnits
	 * 밑이면 멈춘다. 후보가 하나도 없으면 여유를 반씩 줄여 (0 까지) 다시 본다.
	 */
	inline FSiteResult PickHerdSites(const FLandMask& M, const FSiteParams& P)
	{
		FSiteResult R;
		if (!M.Valid() || P.Count <= 0)
		{
			return R;
		}
		const std::int32_t G = M.Gw;
		std::vector<std::int32_t> S(static_cast<size_t>(G + 1) * static_cast<size_t>(G + 1), 0);
		for (std::int32_t Y = 0; Y < G; ++Y)
		{
			std::int32_t Row = 0;
			for (std::int32_t X = 0; X < G; ++X)
			{
				Row += M.Kind[M.Index(X, Y)] != kLand ? 1 : 0;
				S[static_cast<size_t>(Y + 1) * (G + 1) + (X + 1)] = S[static_cast<size_t>(Y) * (G + 1) + (X + 1)] + Row;
			}
		}
		const std::int32_t Stride = std::max(1, P.StrideCells);
		std::vector<double> Cand;
		double Clear = std::max(0.0, P.ClearUnits);
		for (int Attempt = 0; Attempt < 6 && Cand.empty(); ++Attempt)
		{
			const double Half = 0.5 * P.SizeUnits + Clear;
			const std::int32_t Hc = static_cast<std::int32_t>(std::ceil(Half / M.Cell));
			for (std::int32_t Y = Hc; Y + Hc <= G; Y += Stride)
			{
				for (std::int32_t X = Hc; X + Hc <= G; X += Stride)
				{
					if (BlockedIn(S, G, X - Hc, Y - Hc, X + Hc, Y + Hc) == 0)
					{
						Cand.push_back(X * M.Cell);
						Cand.push_back(Y * M.Cell);
					}
				}
			}
			R.ClearUsed = Clear;
			if (Cand.empty())
			{
				Clear = Clear > 1.0 ? 0.5 * Clear : 0.0;
			}
		}
		const size_t Nc = Cand.size() / 2;
		R.Candidates = static_cast<std::int64_t>(Nc);
		if (Nc == 0)
		{
			return R;
		}
		std::vector<double> Near(Nc, std::numeric_limits<double>::infinity());
		size_t First = 0;
		double BestD = std::numeric_limits<double>::infinity();
		for (size_t c = 0; c < Nc; ++c)
		{
			const double Dx = Cand[2 * c] - P.PrefX;
			const double Dy = Cand[2 * c + 1] - P.PrefY;
			const double D = Dx * Dx + Dy * Dy;
			if (D < BestD)
			{
				BestD = D;
				First = c;
			}
		}
		size_t Pick = First;
		for (std::int32_t n = 0; n < P.Count; ++n)
		{
			R.Sites.push_back(Cand[2 * Pick]);
			R.Sites.push_back(Cand[2 * Pick + 1]);
			double Far = -1.0;
			size_t Next = Nc;
			for (size_t c = 0; c < Nc; ++c)
			{
				const double Dx = Cand[2 * c] - Cand[2 * Pick];
				const double Dy = Cand[2 * c + 1] - Cand[2 * Pick + 1];
				Near[c] = std::min(Near[c], std::sqrt(Dx * Dx + Dy * Dy));
				if (Near[c] > Far)
				{
					Far = Near[c];
					Next = c;
				}
			}
			if (Next >= Nc || Far < P.GapUnits)
			{
				break;
			}
			Pick = Next;
		}
		return R;
	}
}

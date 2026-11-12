// R9 데모 플레이어 — 맵 전체 땅 모드의 엔진 없는 부분 (2026-11-13, 발표용).
//
// 사용자 요구 (11-13 01:10): "굳이 명령으로 넣지 않고 지금 맵에서 플레이하면 바로 사슴 늑대가 전지역에 풀리는것처럼 돼지도 같이 풀리도록".
// 그래서 학습한 세 종(사슴·늑대·멧돼지)을 맵 전체 땅의 여러 무리 자리에 함께 푼다 (eco.R9Demo.Area 0 = 맵 전체, 기본).
//
// 이 헤더는 표준 라이브러리만 쓴다 (g++ 로 따로 시험 — scratchpad/r9/ue_demo/whole/tests/). 하는 일:
//   1. 훑기 격자(FR9ScanGrid — 언리얼 cm, 칸 sy 가 클수록 언리얼 +Y) → 코어 땅 지도 Kind (CORE_API.md 1 절 ELand 번호, 칸 iy 가 클수록 코어 +y).
//      화면 좌표는 지금 FR9StageMap 그대로 y 를 뒤집는다: 코어 칸 (ix, iy) = 훑기 칸 (ix, G−1−iy). 코어는 언리얼 좌표를 모른다 (땅 지도만 받음).
//   2. 땅 경계 상자 → 세계 정사각 (칸 4 m 배수, 둘레 여유, 상한 4 km)
//   3. 나무 덩어리·큰 바위 → 은신처 곁 후보점 (코어 LandMap::Anchor)
//   4. 풀 그리기 창 (카메라 둘레 칸만 — 큰 세계 격자 전체를 그리지 않음)
//   5. 몸 액터 배정 (카메라에 가까운 개체만 몸, 나머지는 작은 표식 — 늘었다 줄었다 깜빡이지 않게 여유를 둠)
//   6. 멧돼지 에셋 이름 고르기 (Pig·Boar·Hog·Swine·villsvin) · 애니 이름 → 상태 (Idle·Walk·Trot·Run·Eat·Death …)
// 규칙(코어)은 바꾸지 않는다 — 땅 지도를 만들어 넘기고, 화면에 무엇을 그릴지만 고른다.

#pragma once

#include "EcoR9DemoFrame.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace EcoR9Demo
{
	/** 코어 땅 종류 (CORE_API.md 1 절 EcoR9::ELand 와 같은 번호). 0 이 아니면 모두 막힌 칸. */
	enum ER9Land : std::uint8_t
	{
		kLandOpen = 0,       // 다닐 수 있는 땅
		kLandVoid = 1,       // 바다·호수·강·땅 없음·사각 밖
		kLandSteep = 2,      // 가파름
		kLandObstacle = 3    // 나무·바위·건물 (은신처 곁 후보)
	};

	struct FR9LandCounts
	{
		std::int64_t Open = 0;
		std::int64_t Void = 0;
		std::int64_t Steep = 0;
		std::int64_t Obstacle = 0;
	};

	/** 훑기 칸 (Sx, Sy) → 코어 칸 번호 (iy·G + ix, y 뒤집음). */
	inline std::size_t ScanToCoreIndex(std::int32_t G, std::int32_t Sx, std::int32_t Sy)
	{
		return static_cast<std::size_t>(G - 1 - Sy) * static_cast<std::size_t>(G) + static_cast<std::size_t>(Sx);
	}

	/**
	 * 훑기 격자 (Nx = Ny = G) + 훑기 칸 종류 → 코어 차례 Kind (G×G). ScanKind 가 비면 Blocked·Height 로 정한다 (높이 없음 = Void, 막힘 = Obstacle).
	 * 높이가 없는 칸(땅 없음)은 종류가 무엇이든 Void. 정사각이 아니거나 크기가 틀리면 거짓.
	 */
	inline bool ScanToLand(const FR9ScanGrid& S, const std::vector<std::uint8_t>& ScanKind, std::vector<std::uint8_t>& OutKind, FR9LandCounts* Counts = nullptr)
	{
		if (!S.Valid() || S.Nx != S.Ny)
		{
			return false;
		}
		const std::int32_t G = S.Nx;
		const std::size_t N = static_cast<std::size_t>(G) * static_cast<std::size_t>(G);
		const bool bKind = ScanKind.size() == N;
		OutKind.assign(N, kLandVoid);
		FR9LandCounts C;
		for (std::int32_t sy = 0; sy < G; ++sy)
		{
			for (std::int32_t sx = 0; sx < G; ++sx)
			{
				const std::size_t K = S.Index(sx, sy);
				std::uint8_t L = kLandOpen;
				if (std::isnan(S.Height[K]))
				{
					L = kLandVoid;
				}
				else if (bKind)
				{
					L = ScanKind[K] <= static_cast<std::uint8_t>(kLandObstacle) ? ScanKind[K] : static_cast<std::uint8_t>(kLandObstacle);
					if (L == kLandOpen && S.Blocked[K] != 0)
					{
						L = kLandObstacle;   // 종류를 못 적은 막힌 칸
					}
				}
				else if (S.Blocked[K] != 0)
				{
					L = kLandObstacle;
				}
				OutKind[ScanToCoreIndex(G, sx, sy)] = L;
				switch (L)
				{
				case kLandOpen: ++C.Open; break;
				case kLandVoid: ++C.Void; break;
				case kLandSteep: ++C.Steep; break;
				default: ++C.Obstacle; break;
				}
			}
		}
		if (Counts)
		{
			*Counts = C;
		}
		return true;
	}

	/** 4-이웃으로 이어진 열린 칸 덩어리 가운데 가장 큰 것의 칸 수 (기록 줄용 — 시작·다시 남 자리는 코어가 같은 규칙으로 정한다, CORE_API 2 절). */
	inline std::int64_t LargestOpenComponent(const std::vector<std::uint8_t>& Kind, std::int32_t G, std::int64_t* OutComponents = nullptr)
	{
		const std::size_t N = static_cast<std::size_t>(G) * static_cast<std::size_t>(G);
		if (G <= 0 || Kind.size() != N)
		{
			return 0;
		}
		std::vector<std::int32_t> Label(N, -1);
		std::vector<std::size_t> Stack;
		std::int64_t Best = 0;
		std::int32_t Comps = 0;
		for (std::size_t Start = 0; Start < N; ++Start)
		{
			if (Kind[Start] != kLandOpen || Label[Start] >= 0)
			{
				continue;
			}
			std::int64_t Size = 0;
			Stack.clear();
			Stack.push_back(Start);
			Label[Start] = Comps;
			while (!Stack.empty())
			{
				const std::size_t K = Stack.back();
				Stack.pop_back();
				++Size;
				const std::int32_t X = static_cast<std::int32_t>(K % static_cast<std::size_t>(G));
				const std::int32_t Y = static_cast<std::int32_t>(K / static_cast<std::size_t>(G));
				const std::int32_t Nx[4] = {X - 1, X + 1, X, X};
				const std::int32_t Ny[4] = {Y, Y, Y - 1, Y + 1};
				for (int d = 0; d < 4; ++d)
				{
					if (Nx[d] < 0 || Ny[d] < 0 || Nx[d] >= G || Ny[d] >= G)
					{
						continue;
					}
					const std::size_t J = static_cast<std::size_t>(Ny[d]) * static_cast<std::size_t>(G) + static_cast<std::size_t>(Nx[d]);
					if (Kind[J] == kLandOpen && Label[J] < 0)
					{
						Label[J] = Comps;
						Stack.push_back(J);
					}
				}
			}
			Best = std::max(Best, Size);
			++Comps;
		}
		if (OutComponents)
		{
			*OutComponents = Comps;
		}
		return Best;
	}

	/**
	 * 땅 경계 상자 (cm) → 세계 정사각: 가운데 = 상자 가운데를 칸에 맞춤, 한 변 = 긴 변 + 2·여유를 칸 배수로 올림, [최소, 최대] 로 자름.
	 * 최대에 걸리면 상자 가운데를 지키고 잘린다 (상자 밖 땅은 세계 밖). 반환 G = 한 변 칸 수.
	 */
	inline std::int32_t SquareFromBounds(double MinX, double MinY, double MaxX, double MaxY, double MarginCm, double CellCm, double MinSideCm, double MaxSideCm,
										 double& OutCx, double& OutCy)
	{
		if (!(MaxX >= MinX) || !(MaxY >= MinY) || CellCm <= 0.0)
		{
			OutCx = 0.0;
			OutCy = 0.0;
			return 0;
		}
		const double Long = std::max(MaxX - MinX, MaxY - MinY) + 2.0 * std::max(0.0, MarginCm);
		double Side = std::ceil(Long / CellCm - 1e-9) * CellCm;
		Side = std::min(std::max(Side, std::ceil(MinSideCm / CellCm - 1e-9) * CellCm), std::floor(MaxSideCm / CellCm + 1e-9) * CellCm);
		OutCx = std::round(0.5 * (MinX + MaxX) / CellCm) * CellCm;
		OutCy = std::round(0.5 * (MinY + MaxY) / CellCm) * CellCm;
		return static_cast<std::int32_t>(std::lround(Side / CellCm));
	}

	/** 덮개 점 하나 (나무·큰 바위 — 코어 단위, 무게 = 나무 1 · 큰 바위 크기). */
	struct FR9CoverPoint
	{
		double X = 0.0;
		double Y = 0.0;
		double Weight = 1.0;
	};

	/**
	 * 나무 덩어리·큰 바위 → 은신처 곁 후보점 (코어 단위 x0,y0,x1,y1,…): 점을 Bucket 단위 정사각에 모아 무게 합이 MinWeight 이상인 묶음의 무게중심을
	 * 무게가 큰 차례로 (같으면 칸 차례 — 결정적). 많아도 MaxOut 까지. 코어가 그 곁에 은신처 원을 둔다 (CORE_API 2 절 '나무/바위 곁을 먼저').
	 */
	inline void ClusterAnchors(const std::vector<FR9CoverPoint>& Points, double BucketUnits, double MinWeight, std::size_t MaxOut, std::vector<double>& Out)
	{
		Out.clear();
		if (Points.empty() || BucketUnits <= 0.0)
		{
			return;
		}
		struct FBucket
		{
			std::int64_t Key = 0;
			double Sx = 0.0;
			double Sy = 0.0;
			double W = 0.0;
		};
		std::vector<FBucket> All;
		All.reserve(Points.size());
		for (const FR9CoverPoint& P : Points)
		{
			if (!std::isfinite(P.X) || !std::isfinite(P.Y) || !(P.Weight > 0.0))
			{
				continue;
			}
			const std::int64_t Bx = static_cast<std::int64_t>(std::floor(P.X / BucketUnits));
			const std::int64_t By = static_cast<std::int64_t>(std::floor(P.Y / BucketUnits));
			FBucket B;
			B.Key = By * 1000003LL + Bx;
			B.Sx = P.X * P.Weight;
			B.Sy = P.Y * P.Weight;
			B.W = P.Weight;
			All.push_back(B);
		}
		std::sort(All.begin(), All.end(), [](const FBucket& A, const FBucket& B) { return A.Key < B.Key; });
		std::vector<FBucket> Merged;
		for (const FBucket& B : All)
		{
			if (!Merged.empty() && Merged.back().Key == B.Key)
			{
				Merged.back().Sx += B.Sx;
				Merged.back().Sy += B.Sy;
				Merged.back().W += B.W;
			}
			else
			{
				Merged.push_back(B);
			}
		}
		std::stable_sort(Merged.begin(), Merged.end(), [](const FBucket& A, const FBucket& B) { return A.W > B.W; });
		for (const FBucket& B : Merged)
		{
			if (B.W < MinWeight || Out.size() / 2 >= MaxOut)
			{
				break;
			}
			Out.push_back(B.Sx / B.W);
			Out.push_back(B.Sy / B.W);
		}
	}

	// -------------------------------------------------------------------------
	// 풀 그리기 창 (코어 칸) — 큰 세계 격자는 카메라 둘레 칸만 읽고 그린다 (CORE_API 6 절: 한 프레임에 격자 전체 복사 금지)
	// -------------------------------------------------------------------------

	struct FR9FoodWindow
	{
		std::int32_t X0 = 0;   // 코어 칸
		std::int32_t Y0 = 0;
		std::int32_t Nx = 0;   // 창 칸 수 (격자 가장자리에서는 잘림)
		std::int32_t Ny = 0;

		bool Valid() const { return Nx > 0 && Ny > 0; }
		std::int32_t Cells() const { return Nx * Ny; }
		bool operator==(const FR9FoodWindow& O) const { return X0 == O.X0 && Y0 == O.Y0 && Nx == O.Nx && Ny == O.Ny; }
		bool operator!=(const FR9FoodWindow& O) const { return !(*this == O); }
	};

	/**
	 * 창 놓기: 초점 (코어 단위) 칸을 가운데로 한 변 Side 칸 정사각, 왼쪽 아래 모서리를 Snap 칸에 맞춘다 (카메라가 조금 움직일 때마다 다시 쓰지 않게).
	 * 격자보다 크면 격자 전체 (작은 세계 = 지금처럼 격자 전체). 격자 밖으로 나가는 부분은 자른다.
	 */
	inline FR9FoodWindow PlaceFoodWindow(std::int32_t G, double CellUnits, double FocusX, double FocusY, std::int32_t Side, std::int32_t Snap)
	{
		FR9FoodWindow W;
		if (G <= 0 || CellUnits <= 0.0 || Side <= 0)
		{
			return W;
		}
		if (Side >= G)
		{
			W.Nx = W.Ny = G;
			return W;
		}
		const std::int32_t S = std::max(1, Snap);
		const double Fx = std::isfinite(FocusX) ? FocusX / CellUnits : 0.5 * G;
		const double Fy = std::isfinite(FocusY) ? FocusY / CellUnits : 0.5 * G;
		auto Corner = [&](double F) -> std::int32_t
		{
			const double Raw = std::floor(F - 0.5 * Side);
			const std::int32_t Snapped = static_cast<std::int32_t>(std::floor((Raw + 0.5 * S) / S)) * S;
			return std::min(std::max(Snapped, 0), G - Side);
		};
		W.X0 = Corner(Fx);
		W.Y0 = Corner(Fy);
		W.Nx = Side;
		W.Ny = Side;
		return W;
	}

	// -------------------------------------------------------------------------
	// 몸 액터 배정 — 카메라에 가까운 개체만 몸 (나머지는 작은 표식)
	// -------------------------------------------------------------------------

	/**
	 * Dist[i] = 카메라까지 거리 (cm, 음수·NaN = 몸 없음 대상 아님), HasBody[i] = 지금 몸이 있나. 지금 몸이 있는 개체는 Near × Keep 안이면 먼저 지킨다
	 * (거리 차례). 그다음 Near 안 새 개체를 가까운 차례로 Budget 까지. Want[i] = 1 이면 몸. 같은 입력이면 같은 결과 (거리 같으면 번호 차례). 몸 수.
	 */
	inline std::int32_t PickBodies(const std::vector<double>& Dist, const std::vector<std::uint8_t>& HasBody, double NearCm, double Keep, std::int32_t Budget,
								   std::vector<std::uint8_t>& Want)
	{
		const std::size_t N = Dist.size();
		Want.assign(N, 0);
		if (Budget <= 0 || HasBody.size() != N)
		{
			return 0;
		}
		std::vector<std::size_t> Order;
		Order.reserve(N);
		for (std::size_t i = 0; i < N; ++i)
		{
			if (Dist[i] >= 0.0 && std::isfinite(Dist[i]))
			{
				Order.push_back(i);
			}
		}
		std::stable_sort(Order.begin(), Order.end(), [&Dist](std::size_t A, std::size_t B) { return Dist[A] < Dist[B]; });
		std::int32_t Used = 0;
		const double KeepCm = NearCm * std::max(1.0, Keep);
		for (const std::size_t i : Order)
		{
			if (Used >= Budget || Dist[i] > KeepCm)
			{
				break;
			}
			if (HasBody[i])
			{
				Want[i] = 1;
				++Used;
			}
		}
		for (const std::size_t i : Order)
		{
			if (Used >= Budget || Dist[i] > NearCm)
			{
				break;
			}
			if (!Want[i])
			{
				Want[i] = 1;
				++Used;
			}
		}
		return Used;
	}

	// -------------------------------------------------------------------------
	// 멧돼지 몸 에셋 이름 고르기 (팀 돼지 = AnimalVarietyPack Pig — 이 PC 에 없을 수 있음)
	// -------------------------------------------------------------------------

	inline std::string ToLowerAscii(std::string S)
	{
		for (char& C : S)
		{
			if (C >= 'A' && C <= 'Z')
			{
				C = static_cast<char>(C - 'A' + 'a');
			}
		}
		return S;
	}

	inline bool HasWord(const std::string& Lower, const char* Word) { return Lower.find(Word) != std::string::npos; }

	/** 이름(소문자)이 돼지·멧돼지인가 — 점수 (0 = 아님). 멧돼지 이름이 집돼지보다 조금 높다. 'hedgehog'·'pigeon'·'billboard' 따위는 뺀다. */
	inline int BoarNameScore(const std::string& Lower)
	{
		// 이름에 조각만 든 다른 것 (고슴도치·기니피그·비둘기·물감·판자·빌보드)
		for (const char* Not : {"hedgehog", "guinea", "pigeon", "pigment", "board", "spigot"})
		{
			if (HasWord(Lower, Not))
			{
				return 0;
			}
		}
		int Score = 0;
		if (HasWord(Lower, "boar") || HasWord(Lower, "villsvin") || HasWord(Lower, "wildschwein"))
		{
			Score = std::max(Score, 30);
		}
		if (HasWord(Lower, "warthog") || HasWord(Lower, "hog"))
		{
			Score = std::max(Score, 25);
		}
		if (HasWord(Lower, "pig") || HasWord(Lower, "swine"))
		{
			Score = std::max(Score, 20);
		}
		if (Score > 0 && (HasWord(Lower, "piglet") || HasWord(Lower, "baby")))
		{
			Score -= 5;   // 새끼 메시보다 어른 메시
		}
		return Score;
	}

	/** 애니 쓰임. */
	enum class ER9AnimRole : std::uint8_t
	{
		None = 0,
		Idle,
		Walk,
		Run,
		Eat,
		Death,
		Alert,
		Attack,
		Num
	};

	/**
	 * 애니 이름(소문자) → 쓰임과 점수 (높을수록 좋음, 0 = 안 씀). 뿌리 움직임(_rm)·돌기·맞음·점프 따위 변형은 낮춘다.
	 * 예: anim_pig_idlebreathe → Idle, anim_pig_walk → Walk, anim_pig_run/trot/gallop → Run, eat/graze/root/sniff/dig → Eat, death/die/dead → Death,
	 * lookaround/alert → Alert, attack/bite/charge → Attack.
	 */
	inline ER9AnimRole AnimRoleOf(const std::string& InLower, int& OutScore)
	{
		OutScore = 0;
		// 'breathe'·'wheat' 안의 'eat' 를 먹기로 읽지 않게 먼저 지운다
		std::string Lower = InLower;
		for (const char* Mask : {"breathe", "wheat", "sweat", "great", "treat"})
		{
			for (std::size_t P = Lower.find(Mask); P != std::string::npos; P = Lower.find(Mask, P))
			{
				Lower.replace(P, std::string(Mask).size(), std::string(Mask) == "breathe" ? "idle___" : "_____");
			}
		}
		struct FRule
		{
			const char* Word;
			ER9AnimRole Role;
			int Score;
		};
		static const FRule Rules[] = {
			{"death", ER9AnimRole::Death, 50}, {"die", ER9AnimRole::Death, 40},	 {"dead", ER9AnimRole::Death, 45},
			{"eat", ER9AnimRole::Eat, 50},	   {"graze", ER9AnimRole::Eat, 48},	 {"root", ER9AnimRole::Eat, 46},
			{"sniff", ER9AnimRole::Eat, 40},   {"dig", ER9AnimRole::Eat, 38},	 {"lookaround", ER9AnimRole::Alert, 50},
			{"alert", ER9AnimRole::Alert, 48}, {"attack", ER9AnimRole::Attack, 50}, {"charge", ER9AnimRole::Attack, 45},
			{"bite", ER9AnimRole::Attack, 40}, {"gallop", ER9AnimRole::Run, 46}, {"run", ER9AnimRole::Run, 50},
			{"trot", ER9AnimRole::Run, 44},	   {"walk", ER9AnimRole::Walk, 50},	 {"idle", ER9AnimRole::Idle, 40},
		};
		ER9AnimRole Role = ER9AnimRole::None;
		for (const FRule& R : Rules)
		{
			if (HasWord(Lower, R.Word) && R.Score > OutScore)
			{
				Role = R.Role;
				OutScore = R.Score;
			}
		}
		if (Role == ER9AnimRole::None)
		{
			return Role;
		}
		// 'idlegraze' 같은 섞인 이름은 서 있기(40)보다 먹기·두리번(48 ~ 50) — 위 점수가 그렇게 고른다
		static const char* const Worse[] = {"_rm", "turn", "hit", "jump", "togo", "goto", "backup", "rest", "sleep", "swim", "fall", "land", "start", "stop", "loop_end"};
		for (const char* W : Worse)
		{
			if (HasWord(Lower, W))
			{
				OutScore -= 20;
			}
		}
		if (Role == ER9AnimRole::Idle && HasWord(Lower, "aggress"))
		{
			OutScore -= 10;   // 'IdleAggressive' 보다 그냥 서 있기
		}
		if (OutScore <= 0)
		{
			OutScore = 0;
			return ER9AnimRole::None;
		}
		return Role;
	}
}

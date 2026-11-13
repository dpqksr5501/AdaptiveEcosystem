// R9 몸 움직임 막힌 칸 장면 시험 (엔진 없음, 2026-11-13 — RL_R9_TURN_EFFORT_DESIGN.md 7-2 '막힌 칸 장면 시험'). 자동화 AdaptiveEcosystem.R9Demo.MotionBlocked 와
// 언리얼 밖 대조기(scratchpad/r9/motion_impl/cpp)가 같은 함수를 부른다.
//
// 왜: 언리얼 섬의 막힌 칸 미끄럼(EcoR9Core.h SlideX/SlideY ← EcoR9Scene.h BuildBigScene 의 OutP.Blocked)은 파이썬 학습 세계·ParityChain(120 m 평지)이
//     지나지 않는다. 그래서 막힌 칸이 많은 작은 큰 세계 장면을 만들어 무작위 행동으로 돌리고 M1 회전 한계가 지켜지는지 본다.
// 무엇을 보나 (산 몸-스텝마다, 그 스텝에 죽거나 다시 난 칸은 뺌):
//   - 벽 아닌 스텝: 머리 회전 ≤ θ (h0·h1 ≥ cos θ − 1e-12) — 이 파일이 지난 속도로 따로 셈한 cos θ 로 (코어 통계 TurnOver 와 따로) · 코어가 남긴 cos θ 와 비트 같음
//   - 벽(막힌 칸) 스텝: 수 · 머리 회전 최대 · θ 넘게 돈 수 (3-4 의 예외 — 재기만, 판정 아님)
//   - 대조 판(회전 한계 끔, 같은 장면): 벽 아닌 스텝에서도 θ 넘게 도는 일이 있어야 한다 (이 시험이 무디지 않음)
// 행동은 결정마다 칸별 난수 (걷기 45% · 뛰기 30% · 먹기 10% · 살피기 7% · 숨기 8%, 방향 8 개 고르게 — 정확히 뒤 명령 포함). 두뇌·파이썬 없음.
// 장면 몸 표·상수는 움직임 장면 덤프(chain_motion.txt 의 @scene)에서 읽는다. 세계 규칙은 EcoR9Core.h 그대로 — 이 파일은 재기만 한다.

#pragma once

#include "EcoR9Core.h"
#include "EcoR9Scene.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

// 코어와 같이 이 헤더 안만 /fp:precise (cos θ 를 코어와 비트로 견주므로 — /fp:fast 로 빌드하면 1 − sl² 등이 1 ulp 갈릴 수 있음, 대조기에서 확인)
#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(precise, on, push)
#endif

namespace EcoR9MotionCheck
{
	struct FBlockedResult
	{
		bool bRan = false;
		std::string Error;
		bool bTurn = false;            // 이 판에서 회전 한계를 켰나 (대조 판은 끔)
		int G = 0;                     // 땅 지도 한 변 칸 수
		long BlockedCells = 0;         // 막힌 칸 (둘레 물 포함)
		int Bodies = 0;
		long Steps = 0;
		long BodySteps = 0;            // 견준 산 몸-스텝
		long NonWall = 0;              // 벽 아닌 몸-스텝
		long Over = 0;                 // 그 가운데 머리가 θ 넘게 돈 수 (이 파일의 셈)
		double NonWallMaxRatio = 0.0;  // 벽 아닌 스텝의 (머리 회전 각 / θ) 최대 — 켠 판은 1 이하
		long CoreOver = 0;             // 코어 통계 Tot.TurnOver 합 (켠 판만)
		long ClMismatch = 0;           // 코어 LastTurnCl ≠ 이 파일의 cos θ (켠 판만, 비트로)
		long Clips = 0;                // 회전 한계가 방향을 자른 몸-스텝 (코어 LastTurnClip)
		long WallSteps = 0;            // 벽(막힌 칸) 미끄러짐 몸-스텝
		long WallOver = 0;             // 그 가운데 θ 넘게 돈 수 (예외)
		double WallMaxDeg = 0.0;       // 벽 스텝의 가장 큰 머리 회전 (도)
		long EdgeWall = 0;             // 세계 가장자리(0·Size)에 닿은 벽 스텝 (둘레가 물이라 0 이어야 함 — 모두 막힌 칸 미끄럼)
		long MoveSteps = 0;            // 코어 통계 (켠 판만): 움직인 몸-스텝 · 그 가운데 벽 닿음
		long WallHitSteps = 0;

		/** 회전 한계를 켠 판의 합격: 벽 아닌 스텝 θ 넘음 0 (이 파일·코어 모두) · cos θ 비트 같음 · 막힌 칸 벽 스텝과 자름이 실제로 있었음. */
		bool PassOn() const
		{
			return bRan && bTurn && Over == 0 && CoreOver == 0 && ClMismatch == 0 && NonWall > 0 && WallSteps > 0 && Clips > 0 && EdgeWall == 0;
		}

		std::string Line() const
		{
			char Buf[768];
			std::snprintf(Buf, sizeof(Buf),
						  "회전 한계 %s · 땅 %d² 칸 (막힌 칸 %ld) · 몸 %d · 스텝 %ld | 산 몸-스텝 %ld: 벽 아님 %ld (θ 넘음 %ld · 코어 %ld · 최대 각/θ %.6f) · "
						  "막힌 칸 벽 %ld (θ 넘음 %ld · 최대 %.1f°, 가장자리 %ld) | 자름 %ld · cos θ 다름 %ld | 코어 통계: 벽 닿음 %ld / 움직인 %ld",
						  bTurn ? "켬" : "끔(대조)", G, BlockedCells, Bodies, Steps, BodySteps, NonWall, Over, CoreOver, NonWallMaxRatio, WallSteps, WallOver, WallMaxDeg,
						  EdgeWall, Clips, ClMismatch, WallHitSteps, MoveSteps);
			return std::string(Buf) + (Error.empty() ? std::string() : " | " + Error);
		}
	};

	namespace MotionDetail
	{
		/** 막힌 칸이 많은 땅 지도: 둘레 한 칸 물, 9 칸마다 2×2 나무/바위, 30 칸마다 + 꼴 담 (길이 20), 해시로 흩은 외톨 바위 3%. */
		inline EcoR9::LandMap BlockedLand(int G, double Cell, uint64_t Seed)
		{
			EcoR9::LandMap L;
			L.G = G;
			L.Cell = Cell;
			L.Kind.assign(static_cast<size_t>(G) * static_cast<size_t>(G), EcoR9::LandOpen);
			for (int Iy = 0; Iy < G; ++Iy)
			{
				for (int Ix = 0; Ix < G; ++Ix)
				{
					uint8_t K = EcoR9::LandOpen;
					const int Mx = Ix % 30, My = Iy % 30;
					if ((Ix % 9 == 4 || Ix % 9 == 5) && (Iy % 9 == 4 || Iy % 9 == 5))
					{
						K = EcoR9::LandObstacle;
					}
					else if ((My == 15 && Mx >= 5 && Mx < 25) || (Mx == 15 && My >= 5 && My < 25))
					{
						K = EcoR9::LandSteep;
					}
					else if (EcoR9::HashUnit(Seed * 1000003ull + static_cast<uint64_t>(Iy) * static_cast<uint64_t>(G) + static_cast<uint64_t>(Ix)) < 0.03)
					{
						K = EcoR9::LandObstacle;
					}
					if (Ix == 0 || Iy == 0 || Ix == G - 1 || Iy == G - 1)
					{
						K = EcoR9::LandVoid;
					}
					L.Kind[static_cast<size_t>(Iy) * static_cast<size_t>(G) + static_cast<size_t>(Ix)] = K;
				}
			}
			return L;
		}

		/** 이 파일이 따로 셈한 cos θ (설계 3-1 — 서 있음 규칙 뒤 지난 속도로). 코어 TurnLimit 와 같은 식이지만 다른 코드 줄. */
		inline double ConeCos(const EcoR9::Params& P, int k, const EcoR9::Vec2d& Vel)
		{
			double Vx = Vel.x, Vy = Vel.y;
			if (!(Vx * Vx + Vy * Vy > EcoR9::kEps * EcoR9::kEps))
			{
				Vx = 0.0;
				Vy = 0.0;
			}
			const double S0 = std::sqrt(Vx * Vx + Vy * Vy);
			if (S0 * P.TurnS[k] > P.LatU[k])
			{
				const double Sl = P.LatU[k] / std::max(S0, P.LatU[k]);
				return std::sqrt(1.0 - Sl * Sl);
			}
			return P.TurnC[k];
		}

		inline double AngleDeg(double CosV)
		{
			return std::acos(std::min(1.0, std::max(-1.0, CosV))) * (180.0 / 3.14159265358979323846);
		}
	}

	/**
	 * 막힌 칸 장면 한 판. SceneText = 움직임 장면 덤프 (motion_on · motion_turn 이 켜진 @scene). bTurn 거짓이면 같은 장면에서 움직임 규칙만 끈 대조 판.
	 * 땅 지도 G × G (장면 cell 그대로), 무리 자리 3 곳 (종마다 24·2·8·4·1·2 — 세 종 장면은 앞 셋), Steps 스텝.
	 */
	inline FBlockedResult RunBlocked(const std::string& SceneText, bool bTurn, uint64_t Seed, int Steps, int G = 100)
	{
		FBlockedResult R;
		R.bTurn = bTurn;
		std::vector<EcoR9::DumpBlock> Blocks;
		std::string Err;
		EcoR9::Params Base;
		if (!EcoR9::ParseDump(SceneText, Blocks, &Err) || Blocks.empty() || Blocks[0].Head.empty() || Blocks[0].Head[0] != "scene" ||
			!EcoR9::LoadParams(Blocks[0], Base, &Err))
		{
			R.Error = "장면 읽기 실패: " + Err;
			return R;
		}
		if (!Base.MotionOn || !Base.MotionTurn)
		{
			R.Error = "움직임 장면이 아니다 (motion_on · motion_turn 이 없음)";
			return R;
		}
		if (!bTurn)
		{
			Base.MotionOn = false;      // 대조 판: 옛 줄 그대로 (몸 표 TurnC·TurnS·LatU 는 남겨 이 파일의 cos θ 셈에만 씀)
			Base.MotionTurn = false;
		}
		const EcoR9::LandMap Land = MotionDetail::BlockedLand(G, Base.Cell, Seed);
		EcoR9::BigSpec Spec;
		Spec.Seed = Seed;
		Spec.Herds = 3;
		const int Per[EcoR9::kMaxSpecies] = {24, 2, 8, 4, 1, 2};
		for (int k = 0; k < EcoR9::kMaxSpecies; ++k)
		{
			Spec.PerHerd[k] = Per[k];
		}
		Spec.MaxAnimals = 400;
		EcoR9::Params P;
		EcoR9::State St0;
		EcoR9::BigInfo Info;
		if (!EcoR9::BuildBigScene(Base, Land, Spec, P, St0, Info, &Err))
		{
			R.Error = "큰 세계 장면 만들기 실패: " + Err;
			return R;
		}
		EcoR9::World W;
		if (!W.Init(P, St0, &Err))
		{
			R.Error = "세계 시작 실패: " + Err;
			return R;
		}
		R.G = P.G;
		for (uint8_t B : P.Blocked)
		{
			R.BlockedCells += B ? 1 : 0;
		}
		R.Bodies = P.NumSlots;
		const size_t S = static_cast<size_t>(P.NumSlots);
		EcoR9::Pcg32Random WorldRng(Seed, 0xda3e39cb94b95bdbull);
		EcoR9::Pcg32Random ActRng(Seed * 7919u + 17u, 0x5851f42d4c957f2dull);
		std::vector<int> Acts(S, EcoR9::ActWatch);
		std::vector<EcoR9::Vec2d> H0(S), V0(S);
		std::vector<uint8_t> Alive0(S, 0);
		for (int t = 0; t < Steps; ++t)
		{
			if ((W.St.T % 2) == 0)
			{
				for (size_t s = 0; s < S; ++s)
				{
					int A = EcoR9::ActWatch;
					if (W.St.Alive[s])
					{
						const uint32_t Rv = ActRng.NextBelow(100u);
						if (Rv < 45u) { A = 1 + static_cast<int>(ActRng.NextBelow(8u)); }
						else if (Rv < 75u) { A = 9 + static_cast<int>(ActRng.NextBelow(8u)); }
						else if (Rv < 85u) { A = EcoR9::ActEat; }
						else if (Rv < 92u) { A = EcoR9::ActWatch; }
						else { A = EcoR9::ActShelter; }
					}
					Acts[s] = A;
				}
				W.Decide(Acts.data());
			}
			for (size_t s = 0; s < S; ++s)
			{
				H0[s] = W.St.Head[s];
				V0[s] = W.St.Vel[s];
				Alive0[s] = W.St.Alive[s];
			}
			W.Step(WorldRng);
			++R.Steps;
			for (size_t s = 0; s < S; ++s)
			{
				if (!Alive0[s] || !W.St.Alive[s] || W.LastDead[s])
				{
					continue;
				}
				++R.BodySteps;
				const int k = W.St.Sp[s];
				const double Cl = MotionDetail::ConeCos(P, k, V0[s]);
				const EcoR9::Vec2d H1 = W.St.Head[s];
				const double Hc = H0[s].x * H1.x + H0[s].y * H1.y;
				if (bTurn)
				{
					R.ClMismatch += W.LastTurnCl[s] == Cl ? 0 : 1;
					R.Clips += W.LastTurnClip[s];
				}
				if (W.LastWall[s])
				{
					++R.WallSteps;
					R.WallOver += Hc < Cl - 1e-12 ? 1 : 0;
					R.WallMaxDeg = std::max(R.WallMaxDeg, MotionDetail::AngleDeg(Hc));
					const EcoR9::Vec2d& Ps = W.St.Pos[s];
					R.EdgeWall += (Ps.x <= 0.0 || Ps.y <= 0.0 || Ps.x >= P.Size || Ps.y >= P.Size) ? 1 : 0;
				}
				else
				{
					++R.NonWall;
					R.Over += Hc < Cl - 1e-12 ? 1 : 0;
					const double Theta = MotionDetail::AngleDeg(Cl);
					if (Theta > 0.0)
					{
						R.NonWallMaxRatio = std::max(R.NonWallMaxRatio, MotionDetail::AngleDeg(Hc) / Theta);
					}
				}
			}
		}
		for (int k = 0; k < P.NumSpecies; ++k)
		{
			R.CoreOver += static_cast<long>(W.Tot.TurnOver[k]);
			R.MoveSteps += static_cast<long>(W.Tot.MoveSteps[k]);
			R.WallHitSteps += static_cast<long>(W.Tot.WallHitSteps[k]);
		}
		R.bRan = true;
		return R;
	}
}

#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(pop)
#endif

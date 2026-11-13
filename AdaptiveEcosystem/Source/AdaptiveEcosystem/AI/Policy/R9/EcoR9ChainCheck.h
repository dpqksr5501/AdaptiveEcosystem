// R9 코어 이어 돌리기 대조 (엔진 없음, 2026-11-13 검토 반영). 언리얼 모듈 안에서 컴파일된 코어가 파이썬과 같은지 자동화(AdaptiveEcosystem.R9Demo.ParityChain)가 본다.
//
// 파이썬 덤프(scratchpad/r9/ue_demo/fauna/parity/dump_fauna.py --chain-every)의 처음 장면에서 시작해 행동·난수만 덤프에서 받고 상태는 C++ 혼자 끝까지 이어 간다.
// 상태가 실린 @decision·@final 에서 상태(대조기와 같은 허용 차)·관측(float32 그대로)을 견준다. 한 번 어긋나도 되돌리지 않는다 (어긋남이 쌓이는지 봄).
// scratchpad 대조기 r9_parity.cpp 의 'chain' 과 같은 셈이다 (그 대조기는 g++·MSVC 로 따로 빌드 — 언리얼 빌드 옵션·unity 묶음에서도 같은지는 이 파일로 본다).
// 덤프 파일은 저장소에 넣지 않는다 (<Saved>/R9Demo/parity/ 에 둔다 — 없으면 시험이 건너뜀).

#pragma once

#include "EcoR9Core.h"

#include <cmath>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>

namespace EcoR9ChainCheck
{
	struct FChainResult
	{
		bool bRan = false;          // 덤프를 읽고 끝까지 돌림
		std::string Error;          // 못 돌린 까닭
		int NumSpecies = 0;
		bool bFauna = false;
		bool bMotion = false;       // 몸 움직임 M1 회전 한계 켬 (장면 motion_on · motion_turn — RL_R9_TURN_EFFORT_DESIGN.md 7-2)
		long Decisions = 0;
		long Steps = 0;
		long Checks = 0;            // 상태·관측을 견준 곳 (@decision·@final)
		long Compared = 0;          // 견준 상태 값 수
		long Bad = 0;               // 허용 차를 넘은 상태 값
		long ObsBad = 0;            // float32 로 다른 관측 칸
		long DeadBad = 0;           // 죽은 칸이 다른 스텝
		long Underflow = 0;         // 덤프 난수가 모자라거나 남은 스텝
		long GoreMismatch = 0;      // 들이받기 순서를 쓴 스텝이 다름
		long Bites = 0;
		long Gores = 0;
		long Deaths = 0;
		long TurnClips = 0;         // 몸 움직임: 회전 한계가 방향을 자른 스텝 (코어 통계 Tot.TurnClip 합)
		long TurnOver = 0;          // 몸 움직임: 벽 아닌 스텝에서 θ 넘게 돈 몸 (0 이어야 함)
		long MoveSteps = 0;         // 몸 움직임: 움직인 몸-스텝 · 그 가운데 벽 닿음
		long WallHitSteps = 0;
		double MaxDiff = 0.0;       // 상태 값 가장 큰 차
		std::string FirstBad;       // 처음 어긋난 곳

		bool Pass() const { return bRan && Bad == 0 && ObsBad == 0 && DeadBad == 0 && Underflow == 0 && GoreMismatch == 0 && TurnOver == 0; }

		std::string Line() const
		{
			char Buf[640];
			std::snprintf(Buf, sizeof(Buf),
						  "종 %d (동물 세계 %s · 회전 한계 %s) · 결정 %ld · 스텝 %ld · 대조 %ld 곳 (상태 값 %ld) | 사건: 물기 %ld · 들이받기 %ld · 죽음 %ld | 어긋남: 상태 %ld (최대 차 %.3g) · "
						  "관측 %ld · 죽은 칸 %ld · 난수 %ld · 들이받기 순서 %ld",
						  NumSpecies, bFauna ? "켬" : "끔", bMotion ? "켬" : "끔", Decisions, Steps, Checks, Compared, Bites, Gores, Deaths, Bad, MaxDiff, ObsBad, DeadBad,
						  Underflow, GoreMismatch);
			std::string Out(Buf);
			if (bMotion)
			{
				std::snprintf(Buf, sizeof(Buf), " | 회전 자름 %ld · θ 넘음 %ld · 벽 닿음 %ld / 움직인 %ld", TurnClips, TurnOver, WallHitSteps, MoveSteps);
				Out += Buf;
			}
			return Out + (FirstBad.empty() ? std::string() : " | 처음: " + FirstBad) + (Error.empty() ? std::string() : " | " + Error);
		}
	};

	namespace ChainDetail
	{
		/** 값 하나 견주기 (대조기 Cmp::D 와 같은 뜻 — 같은 부호 무한대 = 같음, NaN = 다름). */
		inline void Real(FChainResult& R, const char* Name, double Got, double Want, double Tol, const std::string& Where)
		{
			++R.Compared;
			double Df = std::fabs(Got - Want);
			if (std::isinf(Got) && std::isinf(Want) && (Got > 0) == (Want > 0))
			{
				Df = 0.0;
			}
			if (std::isnan(Df))
			{
				Df = 1e300;
			}
			R.MaxDiff = Df > R.MaxDiff ? Df : R.MaxDiff;
			if (Df > Tol)
			{
				if (R.Bad == 0)
				{
					char Buf[256];
					std::snprintf(Buf, sizeof(Buf), "%s %s got %.17g want %.17g", Where.c_str(), Name, Got, Want);
					R.FirstBad = Buf;
				}
				++R.Bad;
			}
		}

		inline void Int(FChainResult& R, const char* Name, int64_t Got, int64_t Want, const std::string& Where)
		{
			++R.Compared;
			if (Got != Want)
			{
				if (R.Bad == 0)
				{
					char Buf[256];
					std::snprintf(Buf, sizeof(Buf), "%s %s got %lld want %lld", Where.c_str(), Name, static_cast<long long>(Got), static_cast<long long>(Want));
					R.FirstBad = Buf;
				}
				++R.Bad;
			}
		}

		inline void Vec2(FChainResult& R, const char* Name, const std::vector<EcoR9::Vec2d>& A, const std::vector<EcoR9::Vec2d>& B, double Tol, const std::string& Where)
		{
			if (A.size() != B.size())
			{
				Int(R, Name, static_cast<int64_t>(A.size()), static_cast<int64_t>(B.size()), Where + " size");
				return;
			}
			for (size_t K = 0; K < A.size(); ++K)
			{
				Real(R, Name, A[K].x, B[K].x, Tol, Where);
				Real(R, Name, A[K].y, B[K].y, Tol, Where);
			}
		}

		template <typename T>
		inline void Reals(FChainResult& R, const char* Name, const std::vector<T>& A, const std::vector<T>& B, double Tol, const std::string& Where)
		{
			if (A.size() != B.size())
			{
				Int(R, Name, static_cast<int64_t>(A.size()), static_cast<int64_t>(B.size()), Where + " size");
				return;
			}
			for (size_t K = 0; K < A.size(); ++K)
			{
				Real(R, Name, static_cast<double>(A[K]), static_cast<double>(B[K]), Tol, Where);
			}
		}

		template <typename T>
		inline void Ints(FChainResult& R, const char* Name, const std::vector<T>& A, const std::vector<T>& B, const std::string& Where)
		{
			if (A.size() != B.size())
			{
				Int(R, Name, static_cast<int64_t>(A.size()), static_cast<int64_t>(B.size()), Where + " size");
				return;
			}
			for (size_t K = 0; K < A.size(); ++K)
			{
				Int(R, Name, static_cast<int64_t>(A[K]), static_cast<int64_t>(B[K]), Where);
			}
		}

		/** 상태 견주기 (대조기 r9_parity.cpp CompareState 와 같은 칸·같은 허용 차). */
		inline void CompareState(FChainResult& R, const EcoR9::State& Got, const EcoR9::State& Want, const std::string& Where)
		{
			Int(R, "t", Got.T, Want.T, Where);
			Vec2(R, "pos", Got.Pos, Want.Pos, 1e-9, Where);
			Vec2(R, "head", Got.Head, Want.Head, 1e-9, Where);
			Vec2(R, "vel", Got.Vel, Want.Vel, 1e-9, Where);
			Vec2(R, "disp", Got.Disp, Want.Disp, 1e-9, Where);
			Vec2(R, "dir_cmd", Got.DirCmd, Want.DirCmd, 1e-9, Where);
			Vec2(R, "knock_dir", Got.KnockDir, Want.KnockDir, 1e-9, Where);
			Reals(R, "E", Got.E, Want.E, 1e-9, Where);
			Reals(R, "R", Got.R, Want.R, 1e-9, Where);
			Reals(R, "stam", Got.Stam, Want.Stam, 1e-9, Where);
			Reals(R, "hp", Got.Hp, Want.Hp, 1e-9, Where);
			Reals(R, "born", Got.Born, Want.Born, 1e-9, Where);
			Reals(R, "next_birth", Got.NextBirth, Want.NextBirth, 1e-9, Where);
			Reals(R, "g_speed", Got.GSpeed, Want.GSpeed, 1e-12, Where);
			Reals(R, "g_size", Got.GSize, Want.GSize, 1e-12, Where);
			Reals(R, "resp_t", Got.RespT, Want.RespT, 0.0, Where);
			Ints(R, "kin_id", Got.KinId, Want.KinId, Where);
			Ints(R, "uid", Got.Uid, Want.Uid, Where);
			Ints(R, "sex", Got.Sex, Want.Sex, Where);
			Ints(R, "act", Got.Act, Want.Act, Where);
			Ints(R, "bite_cd", Got.BiteCd, Want.BiteCd, Where);
			Ints(R, "knock_left", Got.KnockLeft, Want.KnockLeft, Where);
			Ints(R, "gore_cd", Got.GoreCd, Want.GoreCd, Where);
			Ints(R, "generation", Got.Generation, Want.Generation, Where);
			Ints(R, "offspring", Got.Offspring, Want.Offspring, Where);
			Ints(R, "alive", Got.Alive, Want.Alive, Where);
			Ints(R, "stam_lock", Got.StamLock, Want.StamLock, Where);
			Ints(R, "mating", Got.Mating, Want.Mating, Where);
			Reals(R, "mem", Got.Mem, Want.Mem, 1e-9, Where);
			Reals(R, "grass", Got.Grass, Want.Grass, 1e-12, Where);
			Reals(R, "root", Got.Root, Want.Root, 1e-12, Where);
			Ints(R, "carc_ok", Got.CarcOk, Want.CarcOk, Where);
			if (Got.CarcOk.size() == Want.CarcOk.size() && Got.CarcPos.size() >= Want.CarcOk.size() && Want.CarcPos.size() >= Want.CarcOk.size() &&
				Got.CarcMeat0.size() >= Want.CarcOk.size() && Want.CarcMeat0.size() >= Want.CarcOk.size() && Got.CarcT.size() >= Want.CarcOk.size() &&
				Want.CarcT.size() >= Want.CarcOk.size() && Got.CarcKin.size() >= Want.CarcOk.size() && Want.CarcKin.size() >= Want.CarcOk.size() &&
				Got.CarcPlaces.size() >= Want.CarcOk.size() && Want.CarcPlaces.size() >= Want.CarcOk.size())
			{
				for (size_t K = 0; K < Want.CarcOk.size(); ++K)
				{
					if (!Want.CarcOk[K])
					{
						continue;
					}
					Real(R, "carc_pos", Got.CarcPos[K].x, Want.CarcPos[K].x, 1e-9, Where);
					Real(R, "carc_pos", Got.CarcPos[K].y, Want.CarcPos[K].y, 1e-9, Where);
					Real(R, "carc_meat0", Got.CarcMeat0[K], Want.CarcMeat0[K], 1e-12, Where);
					Real(R, "carc_t", Got.CarcT[K], Want.CarcT[K], 0.0, Where);
					Int(R, "carc_kin", Got.CarcKin[K], Want.CarcKin[K], Where);
					Int(R, "carc_places", Got.CarcPlaces[K], Want.CarcPlaces[K], Where);
				}
			}
			Reals(R, "carc_meat", Got.CarcMeat, Want.CarcMeat, 1e-12, Where);
			Int(R, "next_uid", Got.NextUid, Want.NextUid, Where);
			Int(R, "n_pairs", static_cast<int64_t>(Got.Pairs.size()), static_cast<int64_t>(Want.Pairs.size()), Where);
			if (Got.Pairs.size() == Want.Pairs.size())
			{
				for (size_t K = 0; K < Got.Pairs.size(); ++K)
				{
					Int(R, "pair", Got.Pairs[K].A, Want.Pairs[K].A, Where);
					Int(R, "pair", Got.Pairs[K].B, Want.Pairs[K].B, Where);
					Real(R, "pair_due", Got.Pairs[K].Due, Want.Pairs[K].Due, 0.0, Where);
					Int(R, "pair_slot", Got.Pairs[K].Slot, Want.Pairs[K].Slot, Where);
				}
			}
		}

		/** 관측 견주기 (float32 그대로 — 대조기 CompareObs 와 같은 뜻). */
		inline void CompareObs(FChainResult& R, const EcoR9::World& W, const EcoR9::DumpBlock& B, const std::vector<float>& Got)
		{
			const EcoR9::DumpEntry* E = B.Find("obs");
			if (!E)
			{
				return;
			}
			const size_t N = static_cast<size_t>(W.P.NumSlots) * static_cast<size_t>(EcoR9::kObsDim);
			if (E->F.size() < N || Got.size() < N)
			{
				++R.ObsBad;
				return;
			}
			for (size_t Ix = 0; Ix < N; ++Ix)
			{
				R.ObsBad += Got[Ix] == static_cast<float>(E->F[Ix]) ? 0 : 1;
			}
		}

		/** 한 스텝의 덤프 난수 (물기·들이받기 순서, 다시 남 뽑기 다섯 줄 묶음 — 대조기 BuildInjected 와 같음). */
		inline bool BuildInjected(const EcoR9::DumpBlock& B, const EcoR9::Params& P, EcoR9::InjectedRandom& Rng)
		{
			Rng = EcoR9::InjectedRandom{};
			if (const EcoR9::DumpEntry* Pe = B.Find("bite_permutation"))
			{
				for (size_t K = 0; K < Pe->Count(); ++K)
				{
					Rng.Perm.push_back(static_cast<int>(Pe->AsDouble(K)));
				}
			}
			if (const EcoR9::DumpEntry* Ge = B.Find("gore_permutation"))
			{
				for (size_t K = 0; K < Ge->Count(); ++K)
				{
					Rng.GorePerm.push_back(static_cast<int>(Ge->AsDouble(K)));
				}
			}
			std::vector<const EcoR9::DumpEntry*> Seq;
			for (const EcoR9::DumpEntry& En : B.Entries)
			{
				if (En.Name == "resp_random" || En.Name == "resp_uniform" || En.Name == "resp_integers")
				{
					Seq.push_back(&En);
				}
			}
			if (Seq.size() % 5 != 0)
			{
				return false;
			}
			for (size_t q = 0; q + 4 < Seq.size(); q += 5)
			{
				EcoR9::RespawnDraw D;
				D.UForm = Seq[q]->AsDouble(0);
				D.UPick = Seq[q + 1]->AsDouble(0);
				D.Cand.assign(Seq[q + 2]->F.begin(), Seq[q + 2]->F.end());
				D.HeadIdx = static_cast<int>(Seq[q + 3]->AsDouble(0));
				D.Fat = Seq[q + 4]->AsDouble(0);
				if (D.Cand.size() != static_cast<size_t>(2 * P.RespawnCandidates))
				{
					return false;
				}
				Rng.Draws.push_back(D);
			}
			return true;
		}

		inline std::string BlockTag(const EcoR9::DumpBlock& B)
		{
			std::string S;
			for (const std::string& H : B.Head)
			{
				S += (S.empty() ? "" : " ") + H;
			}
			return S;
		}
	}

	/** 덤프 글 전체 → 이어 돌리기 대조. Text 는 파일 바이트 그대로 (std::string — 끝 '\0' 이 있어야 함). */
	inline FChainResult RunChain(const std::string& Text)
	{
		FChainResult R;
		std::vector<EcoR9::DumpBlock> Blocks;
		std::string Err;
		if (!EcoR9::ParseDump(Text, Blocks, &Err) || Blocks.empty() || Blocks[0].Head.empty() || Blocks[0].Head[0] != "scene")
		{
			R.Error = "덤프 읽기 실패: " + Err;
			return R;
		}
		EcoR9::Params P;
		EcoR9::State St0;
		if (!EcoR9::LoadParams(Blocks[0], P, &Err) || !EcoR9::LoadState(Blocks[0], P, St0, &Err))
		{
			R.Error = "처음 장면 읽기 실패: " + Err;
			return R;
		}
		R.NumSpecies = P.NumSpecies;
		R.bFauna = P.FaunaOn;
		R.bMotion = P.MotionOn && P.MotionTurn;
		EcoR9::World W;
		if (!W.Init(P, St0, &Err))
		{
			R.Error = "세계 시작 실패: " + Err;
			return R;
		}
		std::vector<float> Obs;
		std::vector<int> Acts(static_cast<size_t>(P.NumSlots));
		for (size_t bi = 1; bi < Blocks.size(); ++bi)
		{
			const EcoR9::DumpBlock& B = Blocks[bi];
			const std::string& H = B.Head.empty() ? std::string() : B.Head[0];
			if (H == "decision" || H == "final")
			{
				if (B.Find("slot_sp"))
				{
					EcoR9::State Want;
					if (!EcoR9::LoadState(B, P, Want, &Err))
					{
						R.Error = ChainDetail::BlockTag(B) + ": " + Err;
						return R;
					}
					ChainDetail::CompareState(R, W.St, Want, ChainDetail::BlockTag(B));
					W.BuildObs(Obs);
					ChainDetail::CompareObs(R, W, B, Obs);
					++R.Checks;
				}
				if (H == "final")
				{
					break;
				}
				const EcoR9::DumpEntry* Act = B.Find("actions");
				if (!Act || Act->Count() < Acts.size())
				{
					R.Error = ChainDetail::BlockTag(B) + ": 행동 줄 없음";
					return R;
				}
				for (size_t s = 0; s < Acts.size(); ++s)
				{
					Acts[s] = static_cast<int>(Act->AsInt(s));
				}
				W.Decide(Acts.data());
				++R.Decisions;
				continue;
			}
			if (H != "step")
			{
				continue;
			}
			EcoR9::InjectedRandom Rng;
			if (!ChainDetail::BuildInjected(B, P, Rng))
			{
				R.Error = ChainDetail::BlockTag(B) + ": 다시 남 난수 줄이 맞지 않음";
				return R;
			}
			W.Step(Rng);
			++R.Steps;
			R.Underflow += (Rng.Underflow || Rng.NextDraw != Rng.Draws.size()) ? 1 : 0;
			R.GoreMismatch += Rng.GoreUsed != (B.Find("gore_permutation") != nullptr) ? 1 : 0;
			std::vector<int64_t> GotDead;
			std::vector<int64_t> WantDead;
			for (size_t s = 0; s < W.LastDead.size(); ++s)
			{
				if (W.LastDead[s])
				{
					GotDead.push_back(static_cast<int64_t>(s));
				}
			}
			if (const EcoR9::DumpEntry* De = B.Find("dead"))
			{
				for (size_t q = 0; q < De->Count(); ++q)
				{
					WantDead.push_back(De->AsInt(q));
				}
			}
			R.DeadBad += GotDead != WantDead ? 1 : 0;
			for (const EcoR9::Event& Ev : W.Events)
			{
				R.Bites += Ev.Kind == EcoR9::EvBite ? 1 : 0;
				R.Gores += Ev.Kind == EcoR9::EvGore ? 1 : 0;
				R.Deaths += Ev.Kind == EcoR9::EvDeath ? 1 : 0;
			}
		}
		for (int k = 0; k < P.NumSpecies; ++k)
		{
			R.TurnClips += static_cast<long>(W.Tot.TurnClip[k]);
			R.TurnOver += static_cast<long>(W.Tot.TurnOver[k]);
			R.MoveSteps += static_cast<long>(W.Tot.MoveSteps[k]);
			R.WallHitSteps += static_cast<long>(W.Tot.WallHitSteps[k]);
		}
		R.bRan = true;
		return R;
	}
}

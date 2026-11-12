// R9 데모 플레이어 — 실시간 판 프레임 원천 (엔진 없음). 코어(EcoR9Core.h, CORE.md 6 절의 쓰는 법)에 맞추는 곳은 이 파일뿐이다.
//
// 한 스텝 = EcoR9::World::Tick (t 가 짝수면 관측 → 두뇌 → 결정, 그다음 Step). 화면 프레임은 그 끝 상태 + 이번 스텝 사건(World::Events)으로 만든다.
// 재생 파일 v1 의 깃발과 같은 뜻으로 맞춘다 (make_replay.py 머리 note):
//   bit0 산 · bit1 이 스텝 실제로 먹이 얻음 · bit2 실제 걸음 뛰기 · bit3 은신처 안 · bit4 이 스텝 물기 사건(문 늑대와 물린 먹이 둘 다, 반격 포함) ·
//   bit5 새로 남 · bit6 물려 죽음 · bit7 굶어/기타 죽음(반격으로 죽은 늑대 = bit7 + bit4). 죽은 개체는 죽은 스텝에만 bit0 꺼진 채 한 번 나온다.
// 학습 세계는 죽은 칸을 같은 스텝에 다시 채우므로(다시 남) 죽은 개체의 uid 는 스텝 앞 uid 표에서 찾는다.

#include "EcoR9DemoLiveSource.h"

#if defined(__has_include)
#if __has_include("EcoR9Core.h")
#include "EcoR9Core.h"
#define ECO_R9_DEMO_HAS_CORE 1
#endif
#endif
#ifndef ECO_R9_DEMO_HAS_CORE
#define ECO_R9_DEMO_HAS_CORE 0
#endif

// 언리얼 빌드(WITH_ENGINE)는 파일을 FFileHelper 로 읽어 바이트로 넘긴다 — 이 파일은 std 파일 읽기를 g++ 시험에서만 쓴다
#if !defined(WITH_ENGINE)
#include <fstream>
#include <iterator>
#define ECO_R9_DEMO_STD_FILES 1
#else
#define ECO_R9_DEMO_STD_FILES 0
#endif

namespace EcoR9Demo
{
#if ECO_R9_DEMO_HAS_CORE

	struct FR9LiveSource::FImpl
	{
		EcoR9::World World;
		EcoR9::Brain Brains[3];
		EcoR9::Pcg32Random Rng;
		std::vector<float> Obs;
		std::vector<std::int64_t> UidBefore;   // 스텝 앞 칸 → uid (사건·죽은 개체용)
		std::vector<int> KinToSpecies;         // 친족 id → 종 (사체 종)
		bool bSample = true;
		std::uint32_t StepCount = 0;
	};

	namespace LiveImpl
	{
		inline bool ReadAll(const std::string& Path, std::vector<std::uint8_t>& Out)
		{
#if ECO_R9_DEMO_STD_FILES
			std::ifstream F(Path, std::ios::binary);
			if (!F)
			{
				return false;
			}
			Out.assign(std::istreambuf_iterator<char>(F), std::istreambuf_iterator<char>());
			return true;
#else
			(void)Path;
			(void)Out;
			return false;
#endif
		}

		inline std::string JoinPath(const std::string& Dir, const char* Name)
		{
			if (Dir.empty())
			{
				return Name;
			}
			const char Last = Dir.back();
			return (Last == '/' || Last == '\\') ? Dir + Name : Dir + "/" + Name;
		}

		inline std::uint32_t U32(std::int64_t V) { return V > 0 ? static_cast<std::uint32_t>(V) : 0u; }

		/** 세계 상태 + 이번 스텝 사건 → 화면 프레임. UidBefore 가 비면 첫 장면 (사건 없음). */
		inline void Fill(FR9LiveSource::FImpl& I, std::uint32_t Step, FR9Frame& Out)
		{
			const EcoR9::World& W = I.World;
			const EcoR9::State& St = W.St;
			const EcoR9::Params& P = W.P;
			const std::size_t S = static_cast<std::size_t>(P.NumSlots);
			const bool bAfterStep = I.UidBefore.size() == S;
			Out.Step = Step;
			Out.Agents.clear();
			Out.Carcasses.clear();
			Out.Events.clear();
			std::vector<std::uint8_t> NewSlot(S, 0);
			std::vector<std::uint8_t> BiteSlot(S, 0);
			if (bAfterStep)
			{
				for (const EcoR9::Event& E : W.Events)
				{
					if (E.Kind == EcoR9::EvRespawn && E.A >= 0 && static_cast<std::size_t>(E.A) < S)
					{
						NewSlot[static_cast<std::size_t>(E.A)] = 1;
					}
				}
			}
			// 산 개체 (다시 난 칸은 새 uid)
			for (std::size_t s = 0; s < S; ++s)
			{
				if (!St.Alive[s])
				{
					continue;
				}
				const int K = St.Sp[s];
				FR9Agent A;
				A.Id = U32(St.Uid[s]);
				A.Species = static_cast<std::uint8_t>(K);
				A.Action = static_cast<std::uint8_t>(St.Act[s] >= 0 && St.Act[s] < EcoR9::kNumActions ? St.Act[s] : EcoR9::ActWatch);
				std::uint8_t Flags = kFlagAlive;
				if (bAfterStep)
				{
					const double Gain = W.LastGainU[s * 3u] + W.LastGainU[s * 3u + 1u] + W.LastGainU[s * 3u + 2u];
					if (Gain > 0.0 && !NewSlot[s])
					{
						Flags = static_cast<std::uint8_t>(Flags | kFlagEating);
						int BestF = 0;
						for (int f = 1; f < 3; ++f)
						{
							if (W.LastGainU[s * 3u + static_cast<std::size_t>(f)] > W.LastGainU[s * 3u + static_cast<std::size_t>(BestF)])
							{
								BestF = f;
							}
						}
						A.Food = static_cast<std::int8_t>(BestF);
					}
					if (W.LastGait[s] == EcoR9::GaitRun && !NewSlot[s])
					{
						Flags = static_cast<std::uint8_t>(Flags | kFlagRunning);
					}
					if (NewSlot[s])
					{
						Flags = static_cast<std::uint8_t>(Flags | kFlagNew);
					}
				}
				if (W.InShelter(static_cast<int>(s)))
				{
					Flags = static_cast<std::uint8_t>(Flags | kFlagInShelter);
				}
				A.Flags = Flags;
				const double Mat = P.Maturity[K] > 0.0 ? (static_cast<double>(St.T) - St.Born[s]) / P.Maturity[K] : 1.0;
				const double Af = Mat < 0.0 ? 0.0 : (Mat > 1.0 ? 1.0 : Mat);
				A.Age = static_cast<std::uint8_t>(Af < 1.0 ? 1 : 0);
				A.X = static_cast<float>(St.Pos[s].x);
				A.Y = static_cast<float>(St.Pos[s].y);
				A.Hx = static_cast<float>(St.Head[s].x);
				A.Hy = static_cast<float>(St.Head[s].y);
				A.Hp = static_cast<float>(St.Hp[s]);
				A.Energy = static_cast<float>(St.E[s]);
				A.Scale = static_cast<float>(W.SizeScale(static_cast<int>(s)));
				A.Maturity = static_cast<float>(Af);
				Out.Agents.push_back(A);
			}
			if (bAfterStep)
			{
				// 죽은 개체 (스텝 앞 uid) — 재생 깃발과 같은 뜻
				for (const EcoR9::Event& E : W.Events)
				{
					if (E.Kind != EcoR9::EvDeath || E.A < 0 || static_cast<std::size_t>(E.A) >= S)
					{
						continue;
					}
					FR9Agent D;
					D.Id = U32(I.UidBefore[static_cast<std::size_t>(E.A)]);
					D.Species = static_cast<std::uint8_t>(E.B >= 0 && E.B < 3 ? E.B : 0);
					D.Action = EcoR9::ActWatch;
					D.Flags = static_cast<std::uint8_t>(E.Code == EcoR9::CauseBite ? static_cast<int>(kFlagBittenDead)
																				   : static_cast<int>(kFlagOtherDead) | (E.Code == EcoR9::CauseCounter ? static_cast<int>(kFlagBite) : 0));
					D.X = static_cast<float>(E.X);
					D.Y = static_cast<float>(E.Y);
					D.Hx = static_cast<float>(E.Value);
					D.Hy = static_cast<float>(E.Value2);
					Out.Agents.push_back(D);
				}
				// 물기 사건 → 화면 사건 + 두 쪽 깃발
				for (const EcoR9::Event& E : W.Events)
				{
					if (E.Kind == EcoR9::EvBite && E.A >= 0 && E.B >= 0 && static_cast<std::size_t>(E.A) < S && static_cast<std::size_t>(E.B) < S)
					{
						FR9Event Ev;
						Ev.Kind = E.Code == EcoR9::BiteKill ? ER9Event::BiteKill : (E.Code == EcoR9::BiteWound ? ER9Event::BiteWound : ER9Event::Counter);
						Ev.A = U32(I.UidBefore[static_cast<std::size_t>(E.A)]);
						Ev.B = U32(I.UidBefore[static_cast<std::size_t>(E.B)]);
						Ev.X = static_cast<float>(E.X);
						Ev.Y = static_cast<float>(E.Y);
						Out.Events.push_back(Ev);
						BiteSlot[static_cast<std::size_t>(E.A)] = 1;
						BiteSlot[static_cast<std::size_t>(E.B)] = 1;
					}
					else if (E.Kind == EcoR9::EvDeath && E.Code == EcoR9::CauseStarve && E.A >= 0 && static_cast<std::size_t>(E.A) < S)
					{
						FR9Event Ev;
						Ev.Kind = ER9Event::Starve;
						Ev.B = U32(I.UidBefore[static_cast<std::size_t>(E.A)]);
						Ev.X = static_cast<float>(E.X);
						Ev.Y = static_cast<float>(E.Y);
						Out.Events.push_back(Ev);
					}
				}
				for (std::size_t s = 0; s < S; ++s)
				{
					if (!BiteSlot[s])
					{
						continue;
					}
					const std::uint32_t Id = U32(I.UidBefore[s]);
					for (FR9Agent& A : Out.Agents)
					{
						if (A.Id == Id)
						{
							A.Flags = static_cast<std::uint8_t>(A.Flags | kFlagBite);
						}
					}
				}
			}
			// 사체 (종 = 친족 id → 종)
			for (std::size_t c = 0; c < St.CarcOk.size(); ++c)
			{
				if (!St.CarcOk[c])
				{
					continue;
				}
				FR9Carcass C;
				C.X = static_cast<float>(St.CarcPos[c].x);
				C.Y = static_cast<float>(St.CarcPos[c].y);
				C.Meat = static_cast<float>(St.CarcMeat[c]);
				C.Meat0 = static_cast<float>(St.CarcMeat0[c]);
				const std::int64_t Kin = St.CarcKin[c];
				C.Species = static_cast<std::uint8_t>(Kin >= 0 && static_cast<std::size_t>(Kin) < I.KinToSpecies.size() && I.KinToSpecies[static_cast<std::size_t>(Kin)] >= 0
														  ? I.KinToSpecies[static_cast<std::size_t>(Kin)]
														  : 0);
				Out.Carcasses.push_back(C);
			}
			Out.Grass.resize(St.Grass.size());
			for (std::size_t k = 0; k < St.Grass.size(); ++k)
			{
				Out.Grass[k] = static_cast<float>(St.Grass[k]);
			}
			Out.Root.resize(St.Root.size());
			for (std::size_t k = 0; k < St.Root.size(); ++k)
			{
				Out.Root[k] = static_cast<float>(St.Root[k]);
			}
		}
	}

	FR9LiveSource::FR9LiveSource() : Impl(std::make_unique<FImpl>()) {}
	FR9LiveSource::~FR9LiveSource() = default;

	bool FR9LiveSource::Available() { return true; }

	bool FR9LiveSource::Init(const FR9LiveConfig& Config, FR9WorldInfo& OutInfo, FR9Frame& OutFirst, std::string& Err)
	{
		Impl = std::make_unique<FImpl>();
		FImpl& I = *Impl;
		std::string SceneText = Config.SceneText;
		if (SceneText.empty())
		{
			std::vector<std::uint8_t> Bytes;
			if (!LiveImpl::ReadAll(Config.ScenePath, Bytes))
			{
				Err = "장면 파일을 못 읽음: " + Config.ScenePath;
				return false;
			}
			SceneText.assign(Bytes.begin(), Bytes.end());
		}
		std::vector<EcoR9::DumpBlock> Blocks;
		if (!EcoR9::ParseDump(SceneText, Blocks, &Err) || Blocks.empty())
		{
			Err = "장면 파일 읽기 실패: " + Err;
			return false;
		}
		const EcoR9::DumpBlock* Scene = &Blocks[0];
		for (const EcoR9::DumpBlock& B : Blocks)
		{
			if (!B.Head.empty() && B.Head[0] == "scene")
			{
				Scene = &B;
				break;
			}
		}
		EcoR9::Params P;
		EcoR9::State S0;
		if (!EcoR9::LoadParams(*Scene, P, &Err) || !EcoR9::LoadState(*Scene, P, S0, &Err))
		{
			Err = "장면 상수·상태 읽기 실패: " + Err;
			return false;
		}
		static const char* const Names[3] = {"deer.r9brain", "wolf.r9brain", "boar.r9brain"};
		static const char* const Species[3] = {"deer", "wolf", "boar"};
		std::string Summary;
		for (int k = 0; k < 3; ++k)
		{
			std::vector<std::uint8_t> Bytes = Config.BrainBytes[k];
			const std::string Path = LiveImpl::JoinPath(Config.BrainDir, Names[k]);
			if (Bytes.empty() && !LiveImpl::ReadAll(Path, Bytes))
			{
				Err = "두뇌 파일을 못 읽음: " + Path;
				return false;
			}
			if (Bytes.empty() || !EcoR9::LoadBrain(Bytes.data(), Bytes.size(), I.Brains[k], &Err) || !I.Brains[k].Valid())
			{
				Err = std::string("두뇌 파일 ") + Names[k] + " 읽기 실패: " + Err;
				return false;
			}
			if (I.Brains[k].Species != Species[k])
			{
				Err = std::string("두뇌 파일 ") + Names[k] + " 의 종이 " + I.Brains[k].Species + " 이다";
				return false;
			}
			Summary += (k ? ", " : "") + std::string(Species[k]) + "=" + I.Brains[k].PayloadSha256.substr(0, 8);
		}
		if (!I.World.Init(P, S0, &Err))
		{
			Err = "세계 시작 실패: " + Err;
			return false;
		}
		I.Rng.Reseed(Config.Seed, 0xda3e39cb94b95bdbull);
		I.bSample = Config.bSample;
		I.StepCount = 0;
		I.UidBefore.clear();
		const EcoR9::State& St = I.World.St;
		for (std::size_t s = 0; s < St.KinId.size() && s < St.Sp.size(); ++s)
		{
			const std::int64_t Kin = St.KinId[s];
			if (Kin >= 0 && Kin < 1024)
			{
				if (I.KinToSpecies.size() <= static_cast<std::size_t>(Kin))
				{
					I.KinToSpecies.resize(static_cast<std::size_t>(Kin) + 1, -1);
				}
				I.KinToSpecies[static_cast<std::size_t>(Kin)] = St.Sp[s];
			}
		}
		OutInfo = FR9WorldInfo();
		OutInfo.W = P.Size;
		OutInfo.H = P.Size;
		OutInfo.StepSeconds = 2.0 / 15.0;
		OutInfo.UnitCm = 200.0;
		OutInfo.G = P.G;
		OutInfo.CellUnits = P.Cell;
		for (std::size_t k = 0; k < P.ShelX.size() && k < P.ShelY.size() && k < P.ShelR.size(); ++k)
		{
			FR9Shelter Sh;
			Sh.X = P.ShelX[k];
			Sh.Y = P.ShelY[k];
			Sh.R = P.ShelR[k];
			OutInfo.Shelters.push_back(Sh);
		}
		for (const double V : St.GrassCap)
		{
			OutInfo.GrassCap.push_back(static_cast<float>(V));
		}
		for (const double V : St.RootCap)
		{
			OutInfo.RootCap.push_back(static_cast<float>(V));
		}
		OutInfo.Seed = Config.Seed;
		OutInfo.Policy = Config.bSample ? "sample" : "argmax";
		OutInfo.Brains = Summary + " (scene seed " + std::to_string(P.Seed) + ")";
		OutInfo.Note = "실시간: 파이썬에서 배운 두뇌 셋을 언리얼 C++ 로 추론";
		for (int a = 0; a < kNumActions; ++a)
		{
			OutInfo.ActionNames.push_back(ActionName(static_cast<std::uint8_t>(a)));
		}
		LiveImpl::Fill(I, 0, OutFirst);
		return true;
	}

	bool FR9LiveSource::Next(FR9Frame& Out, std::string& Err)
	{
		if (!Impl || Impl->World.NumSlots() <= 0)
		{
			Err = "코어가 시작되지 않았다";
			return false;
		}
		FImpl& I = *Impl;
		I.UidBefore = I.World.St.Uid;
		const EcoR9::Brain* BrainPtrs[3] = {&I.Brains[0], &I.Brains[1], &I.Brains[2]};
		I.World.Tick(BrainPtrs, I.Rng, I.bSample, I.Obs);
		++I.StepCount;
		LiveImpl::Fill(I, I.StepCount, Out);
		return true;
	}

	std::uint32_t FR9LiveSource::Steps() const { return Impl ? Impl->StepCount : 0u; }

#else   // 코어 없음 — 재생 판만

	struct FR9LiveSource::FImpl
	{
	};

	FR9LiveSource::FR9LiveSource() : Impl(std::make_unique<FImpl>()) {}
	FR9LiveSource::~FR9LiveSource() = default;

	bool FR9LiveSource::Available() { return false; }

	bool FR9LiveSource::Init(const FR9LiveConfig& Config, FR9WorldInfo& OutInfo, FR9Frame& OutFirst, std::string& Err)
	{
		(void)Config;
		(void)OutInfo;
		(void)OutFirst;
		Err = "이 빌드에는 R9 코어(EcoR9Core.h)가 없다 — 재생 판(-EcoR9Replay=)만 된다";
		return false;
	}

	bool FR9LiveSource::Next(FR9Frame& Out, std::string& Err)
	{
		(void)Out;
		Err = "코어 없음";
		return false;
	}

	std::uint32_t FR9LiveSource::Steps() const { return 0; }

#endif
}

#undef ECO_R9_DEMO_HAS_CORE
#undef ECO_R9_DEMO_STD_FILES

// R9 데모 플레이어 — 엔진 없는 부분 (2026-11-12, 발표용).
//
// 언리얼 화면 쪽(UEcoR9DemoSubsystem)은 이 헤더의 '프레임'만 읽는다. 프레임을 만드는 곳은 둘이다.
//   - 실시간 판 (FR9LiveSource, EcoR9DemoLiveSource.h): 엔진 없는 R9 코어(EcoR9Core.h)가 한 스텝(2/15 초)마다 만든다.
//   - 재생 판 (ParseReplay): 파이썬 실행 기록 파일(R9RP1)을 읽는다. 화면에 '파이썬 실행 기록 재생'이라고 밝힌다.
// 표준 라이브러리만 쓴다 (g++ 로 따로 시험한다 — scratchpad/r9/ue_demo/player_tests/).
//
// 단위: R9 세계 단위 1 = 2 m = 200 cm, 1 스텝 = 2/15 초. 세계는 [0, W] × [0, H] 평평한 정사각.
// 좌표 바꾸기 (FR9StageMap): X = Cx + (x − W/2)·200, Y = Cy − (y − H/2)·200 — y 를 뒤집어 R9 의 왼쪽(반시계) 돌기가
// 언리얼 위에서 본 화면에서도 반시계로 보이게 한다. 머리 (hx, hy) → yaw = atan2(−hy, hx) (도).

#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace EcoR9Demo
{
	/** 종 번호 (재생 파일·코어 같은 차례). */
	enum ER9Species : std::uint8_t
	{
		kDeer = 0,
		kWolf = 1,
		kBoar = 2,
		kNumSpecies = 3
	};

	/** 개체 깃발 (재생 파일 v1 의 flags 와 같은 비트). */
	enum ER9Flag : std::uint8_t
	{
		kFlagAlive = 1u << 0,        // 산
		kFlagEating = 1u << 1,       // 이 스텝 실제로 먹음 (먹은 양 > 0)
		kFlagRunning = 1u << 2,      // 실제 걸음이 뛰기
		kFlagInShelter = 1u << 3,    // 은신처 원 안
		kFlagBite = 1u << 4,         // 이 스텝 물기 사건 (늑대 = 물었다, 먹잇감 = 물렸다)
		kFlagNew = 1u << 5,          // 이 스텝 새로 남
		kFlagBittenDead = 1u << 6,   // 물려 죽음 (반격으로 죽은 늑대도 여기)
		kFlagOtherDead = 1u << 7     // 굶어/기타 죽음
	};

	/** 행동 번호 (R9 행동 19 개). */
	enum ER9Action : std::uint8_t
	{
		kActEat = 0,
		kActWalk0 = 1,      // 1..8  = WALK_0 .. WALK_315
		kActRun0 = 9,       // 9..16 = RUN_0 .. RUN_315
		kActShelter = 17,
		kActWatch = 18,
		kNumActions = 19
	};

	inline bool IsWalk(std::uint8_t A) { return A >= kActWalk0 && A < kActRun0; }
	inline bool IsRun(std::uint8_t A) { return A >= kActRun0 && A < kActShelter; }

	/** 개체 하나 (한 스텝 끝 상태). 재생 기록 한 줄과 같은 뜻 + 실시간 판에서만 아는 값(음수 = 모름). */
	struct FR9Agent
	{
		std::uint32_t Id = 0;          // uid (1 부터, 다시 나면 새 번호)
		std::uint8_t Species = kDeer;
		std::uint8_t Action = kActWatch;
		std::uint8_t Flags = 0;
		std::uint8_t Age = 0;          // 0 어른, 1 어림
		float X = 0.0f;                // 단위
		float Y = 0.0f;
		float Hx = 1.0f;               // 머리 단위벡터
		float Hy = 0.0f;
		// 실시간 판만 (모르면 음수)
		float Hp = -1.0f;              // 0..1 (사슴은 늘 1)
		float Energy = -1.0f;          // 0..1
		float Scale = -1.0f;           // 몸 크기 배율 g_size × 성장 (성체 메시 기준)
		float Maturity = -1.0f;        // 나이비 0..1
		std::int8_t Food = -1;         // 이 스텝 가장 많이 먹은 먹이 0 풀 · 1 땅속 · 2 고기(사체) (실시간 판만, 안 먹음·모름 = -1) — 기록 줄 셈용

		bool Alive() const { return (Flags & kFlagAlive) != 0; }
		bool Dead() const { return !Alive(); }
	};

	/** 사체 하나 (실시간 판만). */
	struct FR9Carcass
	{
		float X = 0.0f;
		float Y = 0.0f;
		float Meat = 0.0f;
		float Meat0 = 0.0f;
		std::uint8_t Species = kDeer;   // 죽은 종 (kin)
	};

	/** 사건 (실시간 판만 — 재생 판은 깃발로 대신한다). */
	enum class ER9Event : std::uint8_t
	{
		BiteKill = 0,    // 늑대 A 가 B 를 물어 죽임
		BiteWound = 1,   // 늑대 A 가 멧돼지 B 를 물어 다치게 함
		Counter = 2,     // 멧돼지 B 가 늑대 A 를 받아침 (A 가 밀려남)
		Starve = 3       // B 굶어 죽음
	};

	struct FR9Event
	{
		ER9Event Kind = ER9Event::BiteKill;
		std::uint32_t A = 0;   // 늑대 uid (없으면 0)
		std::uint32_t B = 0;   // 먹잇감·죽은 개체 uid
		float X = 0.0f;        // 일어난 자리 (단위)
		float Y = 0.0f;
	};

	/** 한 스텝 끝 화면 자료. Grass·Root 가 비면 모름(재생 판). */
	struct FR9Frame
	{
		std::uint32_t Step = 0;
		std::vector<FR9Agent> Agents;       // 산 개체 + 이 스텝에 죽은 개체(깃발 bit6·bit7)
		std::vector<FR9Carcass> Carcasses;
		std::vector<FR9Event> Events;
		std::vector<float> Grass;         // G×G, [iy][ix] 행 우선
		std::vector<float> Root;
	};

	struct FR9Shelter
	{
		double X = 0.0;
		double Y = 0.0;
		double R = 0.0;
	};

	/** 판 하나의 변하지 않는 값. */
	struct FR9WorldInfo
	{
		double W = 60.0;                       // 세계 한 변 (단위)
		double H = 60.0;
		double StepSeconds = 2.0 / 15.0;
		double UnitCm = 200.0;
		std::int32_t G = 0;                    // 먹이 격자 한 변 칸 수 (0 = 격자 없음)
		double CellUnits = 2.0;
		std::vector<FR9Shelter> Shelters;
		std::vector<float> GrassCap;           // G×G (보이는 풀 크기 기준)
		std::vector<float> RootCap;
		std::uint64_t Seed = 0;
		std::string Policy;                    // "argmax" · "sample"
		std::string Brains;                    // 두뇌 설명 (기록 줄·화면 글)
		std::string Note;
		std::vector<std::string> ActionNames;  // 19 개 (재생 머리에서)
		// 맵 전체 땅 모드 (2026-11-13) — 작은 세계는 비거나 기본값
		bool bWhole = false;                   // 큰 세계 (프레임에 먹이 격자를 싣지 않음 — FR9LiveSource::ReadFood)
		float GrassCapMax = 0.0f;              // 가장 큰 풀 용량 (큰 세계는 GrassCap 을 싣지 않고 이 값만)
		std::vector<double> HerdXY;            // 무리 자리 가운데 (x0, y0, … 단위) — 카메라 7 번
		std::int64_t LandCells = 0;            // 열린 칸 · 가장 큰 이어진 땅 칸 (기록 줄)
		std::int64_t MainCells = 0;
		std::int32_t ShelterAnchored = 0;      // 나무·바위 곁에 둔 은신처 수
	};

	// -------------------------------------------------------------------------
	// 재생 파일 v1 (리틀 엔디언)
	//   'R9RP1\n' 6 바이트 → UTF-8 JSON 머리 한 줄('\n' 끝) → 스텝마다 uint32 frame, uint16 count, count × 24 바이트
	//   기록 = uint32 id, uint8 species, uint8 action, uint8 flags, uint8 age, float32 x, y, hx, hy
	// -------------------------------------------------------------------------

	inline constexpr char kReplayMagic[6] = {'R', '9', 'R', 'P', '1', '\n'};
	inline constexpr std::size_t kReplayRecordBytes = 24;

	struct FR9Replay
	{
		std::string HeaderJson;       // 머리 한 줄 ('\n' 뺌) — 뜻 풀이는 언리얼 쪽(FJsonSerializer)
		std::vector<FR9Frame> Frames;
		bool bTruncated = false;      // 끝 스텝이 덜 써짐 (그 스텝은 버림)
	};

	inline std::uint32_t ReadU32(const std::uint8_t* P)
	{
		return static_cast<std::uint32_t>(P[0]) | (static_cast<std::uint32_t>(P[1]) << 8) | (static_cast<std::uint32_t>(P[2]) << 16) |
			   (static_cast<std::uint32_t>(P[3]) << 24);
	}
	inline std::uint16_t ReadU16(const std::uint8_t* P)
	{
		return static_cast<std::uint16_t>(static_cast<std::uint16_t>(P[0]) | (static_cast<std::uint16_t>(P[1]) << 8));
	}
	inline float ReadF32(const std::uint8_t* P)
	{
		const std::uint32_t Bits = ReadU32(P);
		float V = 0.0f;
		std::memcpy(&V, &Bits, sizeof(V));
		return V;
	}

	/**
	 * 재생 파일 바이트 → 머리 + 스텝들. 마법 글자·머리 줄이 없거나 기록 값이 이상하면(종 ≥ 3, 행동 ≥ 19, 좌표·머리가 수가 아님) 거짓과 까닭.
	 * 끝 스텝이 덜 써졌으면 그 스텝만 버리고 참 (bTruncated). 결정적 — 같은 바이트면 같은 결과.
	 */
	inline bool ParseReplay(const std::uint8_t* Data, std::size_t Size, FR9Replay& Out, std::string& Err)
	{
		Out = FR9Replay();
		Err.clear();
		if (!Data || Size < sizeof(kReplayMagic) || std::memcmp(Data, kReplayMagic, sizeof(kReplayMagic)) != 0)
		{
			Err = "R9RP1 마법 글자가 없다";
			return false;
		}
		std::size_t Pos = sizeof(kReplayMagic);
		const std::uint8_t* Nl = static_cast<const std::uint8_t*>(std::memchr(Data + Pos, '\n', Size - Pos));
		if (!Nl)
		{
			Err = "JSON 머리 줄 끝('\\n')이 없다";
			return false;
		}
		Out.HeaderJson.assign(reinterpret_cast<const char*>(Data + Pos), static_cast<std::size_t>(Nl - (Data + Pos)));
		Pos = static_cast<std::size_t>(Nl - Data) + 1;
		while (Pos < Size)
		{
			if (Size - Pos < 6)
			{
				Out.bTruncated = true;
				break;
			}
			FR9Frame F;
			F.Step = ReadU32(Data + Pos);
			const std::uint16_t Count = ReadU16(Data + Pos + 4);
			Pos += 6;
			if (Size - Pos < static_cast<std::size_t>(Count) * kReplayRecordBytes)
			{
				Out.bTruncated = true;
				break;
			}
			F.Agents.resize(Count);
			for (std::uint16_t i = 0; i < Count; ++i)
			{
				const std::uint8_t* R = Data + Pos + static_cast<std::size_t>(i) * kReplayRecordBytes;
				FR9Agent& A = F.Agents[i];
				A.Id = ReadU32(R);
				A.Species = R[4];
				A.Action = R[5];
				A.Flags = R[6];
				A.Age = R[7];
				A.X = ReadF32(R + 8);
				A.Y = ReadF32(R + 12);
				A.Hx = ReadF32(R + 16);
				A.Hy = ReadF32(R + 20);
				if (A.Species >= kNumSpecies || A.Action >= kNumActions || !std::isfinite(A.X) || !std::isfinite(A.Y) || !std::isfinite(A.Hx) ||
					!std::isfinite(A.Hy))
				{
					Err = "스텝 " + std::to_string(F.Step) + " 기록 " + std::to_string(i) + " 값이 이상하다";
					return false;
				}
			}
			Pos += static_cast<std::size_t>(Count) * kReplayRecordBytes;
			Out.Frames.push_back(std::move(F));
		}
		return true;
	}

	/** 시험·도구용: 프레임 → 재생 파일 바이트 (ParseReplay 의 거꾸로). */
	inline void AppendU32(std::vector<std::uint8_t>& B, std::uint32_t V)
	{
		for (int k = 0; k < 4; ++k)
		{
			B.push_back(static_cast<std::uint8_t>((V >> (8 * k)) & 0xFFu));
		}
	}
	inline void AppendF32(std::vector<std::uint8_t>& B, float V)
	{
		std::uint32_t Bits = 0;
		std::memcpy(&Bits, &V, sizeof(V));
		AppendU32(B, Bits);
	}
	inline std::vector<std::uint8_t> WriteReplay(const std::string& HeaderJson, const std::vector<FR9Frame>& Frames)
	{
		std::vector<std::uint8_t> B(kReplayMagic, kReplayMagic + sizeof(kReplayMagic));
		B.insert(B.end(), HeaderJson.begin(), HeaderJson.end());
		B.push_back('\n');
		for (const FR9Frame& F : Frames)
		{
			AppendU32(B, F.Step);
			const std::size_t N = std::min<std::size_t>(F.Agents.size(), 65535u);
			B.push_back(static_cast<std::uint8_t>(N & 0xFFu));
			B.push_back(static_cast<std::uint8_t>((N >> 8) & 0xFFu));
			for (std::size_t i = 0; i < N; ++i)
			{
				const FR9Agent& A = F.Agents[i];
				AppendU32(B, A.Id);
				B.push_back(A.Species);
				B.push_back(A.Action);
				B.push_back(A.Flags);
				B.push_back(A.Age);
				AppendF32(B, A.X);
				AppendF32(B, A.Y);
				AppendF32(B, A.Hx);
				AppendF32(B, A.Hy);
			}
		}
		return B;
	}

	// -------------------------------------------------------------------------
	// 곁 파일 R9FD1 (선택, 재생 파일과 같은 이름 .r9fd) — 먹이 격자·사체
	//   'R9FD1\n' → JSON 머리 한 줄 (G, cell_units, frames, eat_min, grass_cap[G·G], root_cap[G·G], cover_cell …)
	//   → 프레임마다 uint32 frame, float16 grass[G·G], float16 root[G·G], uint8 n, n × 20 바이트
	//     (uint8 carc_slot, uint8 species, uint16 0, float32 x, y, meat, meat0)
	// -------------------------------------------------------------------------

	inline constexpr char kFoodMagic[6] = {'R', '9', 'F', 'D', '1', '\n'};
	inline constexpr std::size_t kFoodCarcassBytes = 20;

	/** IEEE 754 반정밀도 → float (numpy float16 '<f2' 와 같다). */
	inline float HalfToFloat(std::uint16_t H)
	{
		const std::uint32_t Sign = static_cast<std::uint32_t>(H & 0x8000u) << 16;
		const std::uint32_t Exp = (H >> 10) & 0x1Fu;
		std::uint32_t Mant = H & 0x3FFu;
		std::uint32_t Bits = 0;
		if (Exp == 0)
		{
			if (Mant == 0)
			{
				Bits = Sign;
			}
			else
			{
				// 정규화 안 된 수: 2^-14 × mant/1024
				int E = -1;
				do
				{
					++E;
					Mant <<= 1;
				} while ((Mant & 0x400u) == 0);
				Mant &= 0x3FFu;
				Bits = Sign | (static_cast<std::uint32_t>(127 - 15 - E) << 23) | (Mant << 13);
			}
		}
		else if (Exp == 0x1Fu)
		{
			Bits = Sign | 0x7F800000u | (Mant << 13);
		}
		else
		{
			Bits = Sign | ((Exp + (127 - 15)) << 23) | (Mant << 13);
		}
		float V = 0.0f;
		std::memcpy(&V, &Bits, sizeof(V));
		return V;
	}

	/** JSON 머리에서 정수 칸 하나만 (예: "G": 30). 없으면 거짓. 언리얼 쪽은 FJsonSerializer 로 전부 읽는다 — 이것은 G 를 먼저 알려고. */
	inline bool JsonIntField(const std::string& Json, const char* Key, long long& Out)
	{
		const std::string Pat = std::string("\"") + Key + "\"";
		std::size_t P = Json.find(Pat);
		if (P == std::string::npos)
		{
			return false;
		}
		P = Json.find(':', P + Pat.size());
		if (P == std::string::npos)
		{
			return false;
		}
		++P;
		while (P < Json.size() && (Json[P] == ' ' || Json[P] == '\t'))
		{
			++P;
		}
		bool bNeg = false;
		if (P < Json.size() && Json[P] == '-')
		{
			bNeg = true;
			++P;
		}
		long long V = 0;
		bool bAny = false;
		while (P < Json.size() && Json[P] >= '0' && Json[P] <= '9')
		{
			V = V * 10 + (Json[P] - '0');
			++P;
			bAny = true;
		}
		if (!bAny)
		{
			return false;
		}
		Out = bNeg ? -V : V;
		return true;
	}

	struct FR9FoodFrame
	{
		std::uint32_t Step = 0;
		std::vector<float> Grass;
		std::vector<float> Root;
		std::vector<FR9Carcass> Carcasses;
	};

	struct FR9FoodSide
	{
		std::string HeaderJson;
		std::int32_t G = 0;
		std::vector<FR9FoodFrame> Frames;
		bool bTruncated = false;
	};

	inline bool ParseFoodSide(const std::uint8_t* Data, std::size_t Size, FR9FoodSide& Out, std::string& Err)
	{
		Out = FR9FoodSide();
		Err.clear();
		if (!Data || Size < sizeof(kFoodMagic) || std::memcmp(Data, kFoodMagic, sizeof(kFoodMagic)) != 0)
		{
			Err = "R9FD1 마법 글자가 없다";
			return false;
		}
		std::size_t Pos = sizeof(kFoodMagic);
		const std::uint8_t* Nl = static_cast<const std::uint8_t*>(std::memchr(Data + Pos, '\n', Size - Pos));
		if (!Nl)
		{
			Err = "R9FD1 JSON 머리 줄 끝이 없다";
			return false;
		}
		Out.HeaderJson.assign(reinterpret_cast<const char*>(Data + Pos), static_cast<std::size_t>(Nl - (Data + Pos)));
		Pos = static_cast<std::size_t>(Nl - Data) + 1;
		long long G = 0;
		if (!JsonIntField(Out.HeaderJson, "G", G) || G <= 0 || G > 512)
		{
			Err = "R9FD1 머리에 G 가 없다";
			return false;
		}
		Out.G = static_cast<std::int32_t>(G);
		const std::size_t Cells = static_cast<std::size_t>(G) * static_cast<std::size_t>(G);
		const std::size_t Fixed = 4 + Cells * 2 * 2 + 1;
		while (Pos < Size)
		{
			if (Size - Pos < Fixed)
			{
				Out.bTruncated = true;
				break;
			}
			FR9FoodFrame F;
			F.Step = ReadU32(Data + Pos);
			Pos += 4;
			F.Grass.resize(Cells);
			F.Root.resize(Cells);
			for (std::size_t k = 0; k < Cells; ++k)
			{
				F.Grass[k] = HalfToFloat(ReadU16(Data + Pos + 2 * k));
			}
			Pos += 2 * Cells;
			for (std::size_t k = 0; k < Cells; ++k)
			{
				F.Root[k] = HalfToFloat(ReadU16(Data + Pos + 2 * k));
			}
			Pos += 2 * Cells;
			const std::size_t N = Data[Pos];
			Pos += 1;
			if (Size - Pos < N * kFoodCarcassBytes)
			{
				Out.bTruncated = true;
				break;
			}
			for (std::size_t c = 0; c < N; ++c)
			{
				const std::uint8_t* R = Data + Pos + c * kFoodCarcassBytes;
				FR9Carcass Cc;
				Cc.Species = R[1];
				Cc.X = ReadF32(R + 4);
				Cc.Y = ReadF32(R + 8);
				Cc.Meat = ReadF32(R + 12);
				Cc.Meat0 = ReadF32(R + 16);
				F.Carcasses.push_back(Cc);
			}
			Pos += N * kFoodCarcassBytes;
			Out.Frames.push_back(std::move(F));
		}
		return true;
	}

	/** 곁 파일 프레임을 재생 프레임에 붙인다 (frame 번호가 같은 것끼리). 붙인 수. */
	inline std::size_t AttachFood(std::vector<FR9Frame>& Frames, const FR9FoodSide& Food)
	{
		std::size_t Done = 0;
		std::size_t j = 0;
		for (FR9Frame& F : Frames)
		{
			while (j < Food.Frames.size() && Food.Frames[j].Step < F.Step)
			{
				++j;
			}
			if (j < Food.Frames.size() && Food.Frames[j].Step == F.Step)
			{
				F.Grass = Food.Frames[j].Grass;
				F.Root = Food.Frames[j].Root;
				F.Carcasses = Food.Frames[j].Carcasses;
				++Done;
			}
		}
		return Done;
	}

	// -------------------------------------------------------------------------
	// 무대 자리 (언리얼 cm ↔ R9 단위)
	// -------------------------------------------------------------------------

	struct FR9StageMap
	{
		double Cx = 0.0;        // 무대 정사각 가운데 (언리얼 cm)
		double Cy = 0.0;
		double W = 60.0;        // 세계 한 변 (단위)
		double H = 60.0;
		double UnitCm = 200.0;

		void ToWorld(double X, double Y, double& OutX, double& OutY) const
		{
			OutX = Cx + (X - 0.5 * W) * UnitCm;
			OutY = Cy - (Y - 0.5 * H) * UnitCm;
		}
		void ToUnits(double WX, double WY, double& OutX, double& OutY) const
		{
			OutX = 0.5 * W + (WX - Cx) / UnitCm;
			OutY = 0.5 * H - (WY - Cy) / UnitCm;
		}
		/** R9 벡터 (단위/스텝 따위) → 언리얼 벡터 (cm 같은 배율). y 를 뒤집는다. */
		void VecToWorld(double Vx, double Vy, double& OutX, double& OutY) const
		{
			OutX = Vx * UnitCm;
			OutY = -Vy * UnitCm;
		}
		/** 머리 → 언리얼 yaw (도). 머리가 0 이면 0. */
		static double YawDeg(double Hx, double Hy)
		{
			if (Hx * Hx + Hy * Hy <= 1e-18)
			{
				return 0.0;
			}
			return std::atan2(-Hy, Hx) * (180.0 / 3.14159265358979323846);
		}
		double SideXCm() const { return W * UnitCm; }
		double SideYCm() const { return H * UnitCm; }
	};

	/** 각도 사이 (도, 짧은 쪽). */
	inline double LerpYawDeg(double A, double B, double T)
	{
		double D = std::fmod(B - A, 360.0);
		if (D > 180.0)
		{
			D -= 360.0;
		}
		else if (D < -180.0)
		{
			D += 360.0;
		}
		double R = A + D * T;
		R = std::fmod(R + 180.0, 360.0);
		if (R < 0.0)
		{
			R += 360.0;
		}
		return R - 180.0;
	}

	// -------------------------------------------------------------------------
	// 무대 자리 고르기 — 아무 맵의 트인 평지 (맵마다 설정 없음)
	// -------------------------------------------------------------------------

	/** 훑은 지도 (칸 가운데 높이·막힘). 칸 (ix, iy) 가운데 = (X0 + (ix + 0.5)·Cell, Y0 + (iy + 0.5)·Cell) cm. */
	struct FR9ScanGrid
	{
		std::int32_t Nx = 0;
		std::int32_t Ny = 0;
		double CellCm = 400.0;
		double X0 = 0.0;
		double Y0 = 0.0;
		std::vector<float> Height;          // cm, NaN = 땅 없음 (지형·바닥 메시 모두 없음)
		std::vector<std::uint8_t> Blocked;  // 1 = 막힘 (물·가파름·나무·바위·건물·땅 없음)
		std::vector<std::uint8_t> Avoid;    // 1 = 되도록 피함 (맵에 이미 있는 생태 지역·서식지·동물 둘레). 비어 있으면 없음

		bool Valid() const
		{
			const std::size_t N = static_cast<std::size_t>(Nx) * static_cast<std::size_t>(Ny);
			return Nx > 0 && Ny > 0 && CellCm > 0.0 && Height.size() == N && Blocked.size() == N;
		}
		bool HasAvoid() const { return !Avoid.empty() && Avoid.size() == Height.size(); }
		std::size_t Index(std::int32_t X, std::int32_t Y) const { return static_cast<std::size_t>(Y) * static_cast<std::size_t>(Nx) + static_cast<std::size_t>(X); }
		double CellX(std::int32_t Ix) const { return X0 + (static_cast<double>(Ix) + 0.5) * CellCm; }
		double CellY(std::int32_t Iy) const { return Y0 + (static_cast<double>(Iy) + 0.5) * CellCm; }
		bool IsOpen(std::size_t K, bool bWithAvoid) const
		{
			return Blocked[K] == 0 && !std::isnan(Height[K]) && !(bWithAvoid && HasAvoid() && Avoid[K] != 0);
		}
	};

	/** 상자 (cm). */
	struct FR9Box
	{
		double MinX = 0.0;
		double MinY = 0.0;
		double MinZ = 0.0;
		double MaxX = 0.0;
		double MaxY = 0.0;
		double MaxZ = 0.0;
	};

	namespace R9GridImpl
	{
		/** 칸 가운데가 상자 + Pad 안인 칸마다 Fn(칸 번호) — 격자 밖은 건너뜀. */
		template <typename FnT>
		inline void ForCellsIn(const FR9ScanGrid& G, const FR9Box& B, double Pad, FnT&& Fn)
		{
			if (!G.Valid())
			{
				return;
			}
			const double Lx = B.MinX - Pad;
			const double Ly = B.MinY - Pad;
			const double Hx = B.MaxX + Pad;
			const double Hy = B.MaxY + Pad;
			if (!(Hx >= Lx) || !(Hy >= Ly))
			{
				return;   // NaN·뒤집힌 상자
			}
			const double Fx0 = std::floor((Lx - G.X0) / G.CellCm);
			const double Fy0 = std::floor((Ly - G.Y0) / G.CellCm);
			const double Fx1 = std::floor((Hx - G.X0) / G.CellCm);
			const double Fy1 = std::floor((Hy - G.Y0) / G.CellCm);
			if (Fx1 < 0.0 || Fy1 < 0.0 || Fx0 >= static_cast<double>(G.Nx) || Fy0 >= static_cast<double>(G.Ny))
			{
				return;
			}
			const std::int32_t Ix0 = static_cast<std::int32_t>(std::max(0.0, Fx0));
			const std::int32_t Iy0 = static_cast<std::int32_t>(std::max(0.0, Fy0));
			const std::int32_t Ix1 = static_cast<std::int32_t>(std::min(static_cast<double>(G.Nx - 1), Fx1));
			const std::int32_t Iy1 = static_cast<std::int32_t>(std::min(static_cast<double>(G.Ny - 1), Fy1));
			for (std::int32_t y = Iy0; y <= Iy1; ++y)
			{
				for (std::int32_t x = Ix0; x <= Ix1; ++x)
				{
					const double Px = G.CellX(x);
					const double Py = G.CellY(y);
					if (Px >= Lx && Px <= Hx && Py >= Ly && Py <= Hy)
					{
						Fn(G.Index(x, y));
					}
				}
			}
		}
	}

	/**
	 * 걸리는 것(나무·바위·건물) 상자를 막힘으로 표시. 칸 땅보다 ClearCm 넘게 솟고(바닥 메시·낮은 판은 빼기) 땅 위 ReachCm 안까지 내려온
	 * (높이 뜬 지붕·하늘 장식은 빼기) 상자만. 땅 높이가 없는 칸은 이미 막힘이라 건드리지 않는다. Skip(칸 번호) 가 참인 칸도 건드리지 않는다
	 * (그 칸의 땅이 바로 이 메시 — 지형 대신 언덕진 바닥 메시를 쓰는 맵에서, 바닥 메시 상자 꼭대기가 낮은 칸 땅보다 높다고 막지 않게). 새로 막은 칸 수.
	 */
	template <typename SkipT>
	inline std::int64_t MarkObstacleIf(FR9ScanGrid& G, const FR9Box& B, double PadCm, double ClearCm, double ReachCm, SkipT&& Skip)
	{
		std::int64_t N = 0;
		R9GridImpl::ForCellsIn(G, B, PadCm,
							   [&](std::size_t K)
							   {
								   const float Ground = G.Height[K];
								   if (std::isnan(Ground) || G.Blocked[K] != 0 || Skip(K))
								   {
									   return;
								   }
								   const double Gz = static_cast<double>(Ground);
								   if (B.MaxZ > Gz + ClearCm && B.MinZ < Gz + ReachCm)
								   {
									   G.Blocked[K] = 1;
									   ++N;
								   }
							   });
		return N;
	}

	inline std::int64_t MarkObstacle(FR9ScanGrid& G, const FR9Box& B, double PadCm, double ClearCm = 30.0, double ReachCm = 300.0)
	{
		return MarkObstacleIf(G, B, PadCm, ClearCm, ReachCm, [](std::size_t) { return false; });
	}

	/** 되도록 피할 상자 (기존 생태 지역·서식지·동물 둘레) 표시 — 높이는 보지 않는다. 새로 표시한 칸 수. */
	inline std::int64_t MarkAvoid(FR9ScanGrid& G, const FR9Box& B, double PadCm)
	{
		if (!G.Valid())
		{
			return 0;
		}
		if (!G.HasAvoid())
		{
			G.Avoid.assign(G.Height.size(), 0);
		}
		std::int64_t N = 0;
		R9GridImpl::ForCellsIn(G, B, PadCm,
							   [&](std::size_t K)
							   {
								   if (G.Avoid[K] == 0)
								   {
									   G.Avoid[K] = 1;
									   ++N;
								   }
							   });
		return N;
	}

	/** 가파름: 오른쪽·위 이웃 칸과 높이 차 / 칸 > MaxSlope 인 칸을 막음 (0.36 ≈ 20°). 새로 막은 칸 수. */
	inline std::int64_t MarkSteep(FR9ScanGrid& G, double MaxSlope = 0.36)
	{
		std::int64_t N = 0;
		if (!G.Valid())
		{
			return N;
		}
		for (std::int32_t y = 0; y < G.Ny; ++y)
		{
			for (std::int32_t x = 0; x < G.Nx; ++x)
			{
				const float Z = G.Height[G.Index(x, y)];
				if (std::isnan(Z))
				{
					continue;
				}
				float Worst = 0.0f;
				if (x + 1 < G.Nx && !std::isnan(G.Height[G.Index(x + 1, y)]))
				{
					Worst = std::max(Worst, std::fabs(G.Height[G.Index(x + 1, y)] - Z));
				}
				if (y + 1 < G.Ny && !std::isnan(G.Height[G.Index(x, y + 1)]))
				{
					Worst = std::max(Worst, std::fabs(G.Height[G.Index(x, y + 1)] - Z));
				}
				std::uint8_t& B = G.Blocked[G.Index(x, y)];
				if (static_cast<double>(Worst) / G.CellCm > MaxSlope && B == 0)
				{
					B = 1;
					++N;
				}
			}
		}
		return N;
	}

	struct FR9PickParams
	{
		double SideCm = 12000.0;     // 무대 한 변 (120 m)
		double MarginCm = 2000.0;    // 무대 둘레 여유 (막힌 칸이 없어야 하는 띠)
		double PrefX = 0.0;          // 시작점 (cm) — 가까울수록 좋다
		double PrefY = 0.0;
		std::int32_t Stride = 5;     // 후보 간격 (칸)
		double DistWeight = 0.02;    // 점수 = 높이 폭(m) + 시작점 거리(m) × 이 값
		bool bAvoid = false;         // 참이면 Avoid 칸도 막힌 칸처럼 본다 (기존 생태에서 떨어진 곳만)
	};

	struct FR9PickResult
	{
		bool bOk = false;
		double Cx = 0.0;
		double Cy = 0.0;
		double RangeCm = 0.0;        // 무대 안 높이 폭 (가장 높은 − 가장 낮은)
		double MeanCm = 0.0;
		std::int64_t Candidates = 0;
		double MarginUsed = 0.0;
		std::int64_t BlockedCells = 0;   // (가장 덜 막힌 곳) 무대 안 막힌·땅 없는 칸
		std::int64_t AvoidCells = 0;     // (가장 덜 막힌 곳) 무대 안 피할 칸
		std::int64_t StageCells = 0;     // (가장 덜 막힌 곳) 무대 안 칸 전체
		bool bHeightKnown = false;       // MeanCm·RangeCm 이 땅 높이에서 왔다 (거짓 = 무대 안 땅을 하나도 못 읽음)
	};

	namespace R9GridImpl
	{
		/** 누적합 (Nx+1)×(Ny+1) — Pred(칸 번호) 가 참인 칸 수. */
		template <typename PredT>
		inline std::vector<std::int32_t> PrefixSum(const FR9ScanGrid& M, PredT&& Pred)
		{
			const std::size_t Ws = static_cast<std::size_t>(M.Nx + 1);
			std::vector<std::int32_t> S(Ws * static_cast<std::size_t>(M.Ny + 1), 0);
			for (std::int32_t y = 0; y < M.Ny; ++y)
			{
				std::int32_t Row = 0;
				for (std::int32_t x = 0; x < M.Nx; ++x)
				{
					Row += Pred(M.Index(x, y)) ? 1 : 0;
					S[static_cast<std::size_t>(y + 1) * Ws + static_cast<std::size_t>(x + 1)] = S[static_cast<std::size_t>(y) * Ws + static_cast<std::size_t>(x + 1)] + Row;
				}
			}
			return S;
		}

		/** 칸 [X0, X1) × [Y0, Y1) 안 개수. */
		inline std::int64_t CountIn(const std::vector<std::int32_t>& S, std::int32_t Nx, std::int32_t X0, std::int32_t Y0, std::int32_t X1, std::int32_t Y1)
		{
			const std::size_t Ws = static_cast<std::size_t>(Nx + 1);
			return static_cast<std::int64_t>(S[static_cast<std::size_t>(Y1) * Ws + static_cast<std::size_t>(X1)]) -
				   S[static_cast<std::size_t>(Y0) * Ws + static_cast<std::size_t>(X1)] - S[static_cast<std::size_t>(Y1) * Ws + static_cast<std::size_t>(X0)] +
				   S[static_cast<std::size_t>(Y0) * Ws + static_cast<std::size_t>(X0)];
		}

		/** 칸 [X0, X1) × [Y0, Y1) 안 높이 (땅 없는 칸 빼고) 가장 낮은·높은·평균. 없으면 거짓. */
		inline bool HeightStats(const FR9ScanGrid& M, std::int32_t X0, std::int32_t Y0, std::int32_t X1, std::int32_t Y1, double& Lo, double& Hi, double& Mean)
		{
			Lo = std::numeric_limits<double>::infinity();
			Hi = -std::numeric_limits<double>::infinity();
			double Sum = 0.0;
			std::int64_t N = 0;
			for (std::int32_t yy = std::max(0, Y0); yy < std::min(M.Ny, Y1); ++yy)
			{
				for (std::int32_t xx = std::max(0, X0); xx < std::min(M.Nx, X1); ++xx)
				{
					const float H = M.Height[M.Index(xx, yy)];
					if (std::isnan(H))
					{
						continue;
					}
					Lo = std::min(Lo, static_cast<double>(H));
					Hi = std::max(Hi, static_cast<double>(H));
					Sum += static_cast<double>(H);
					++N;
				}
			}
			Mean = N > 0 ? Sum / static_cast<double>(N) : 0.0;
			return N > 0;
		}
	}

	/**
	 * 무대 고르기 (결정적): 후보 = Stride 칸 간격 점 가운데 (한 변 + 2·여유) 정사각 안 칸이 모두 열리고 높이가 있는 점
	 * (bAvoid 면 피할 칸도 없어야 함). 점수 = 무대 정사각 안 높이 폭(m) + 시작점까지 거리(m) × DistWeight. 가장 작은 것
	 * (같으면 먼저 본 것 = y·x 가 작은 쪽). 후보가 없으면 여유를 반씩 줄여 (0 까지) 다시 본다. 그래도 없으면 bOk 거짓.
	 */
	inline FR9PickResult PickStage(const FR9ScanGrid& M, const FR9PickParams& P)
	{
		FR9PickResult R;
		if (!M.Valid() || P.SideCm <= 0.0)
		{
			return R;
		}
		const std::int32_t Nx = M.Nx;
		const std::int32_t Ny = M.Ny;
		const bool bWithAvoid = P.bAvoid;
		const std::vector<std::int32_t> S = R9GridImpl::PrefixSum(M, [&M, bWithAvoid](std::size_t k) { return !M.IsOpen(k, bWithAvoid); });
		auto BlockedIn = [&S, Nx](std::int32_t X0, std::int32_t Y0, std::int32_t X1, std::int32_t Y1) -> std::int64_t
		{
			return R9GridImpl::CountIn(S, Nx, X0, Y0, X1, Y1);
		};
		const std::int32_t Stride = std::max(1, P.Stride);
		const std::int32_t HalfStage = static_cast<std::int32_t>(std::ceil(0.5 * P.SideCm / M.CellCm));
		double Margin = std::max(0.0, P.MarginCm);
		for (int Attempt = 0; Attempt < 8; ++Attempt)
		{
			const std::int32_t Hc = static_cast<std::int32_t>(std::ceil((0.5 * P.SideCm + Margin) / M.CellCm));
			double BestScore = std::numeric_limits<double>::infinity();
			std::int64_t Cands = 0;
			for (std::int32_t y = Hc; y + Hc <= Ny; y += Stride)
			{
				for (std::int32_t x = Hc; x + Hc <= Nx; x += Stride)
				{
					if (BlockedIn(x - Hc, y - Hc, x + Hc, y + Hc) != 0)
					{
						continue;
					}
					++Cands;
					double Lo = std::numeric_limits<double>::infinity();
					double Hi = -std::numeric_limits<double>::infinity();
					double Sum = 0.0;
					std::int64_t N = 0;
					for (std::int32_t yy = std::max(0, y - HalfStage); yy < std::min(Ny, y + HalfStage); ++yy)
					{
						for (std::int32_t xx = std::max(0, x - HalfStage); xx < std::min(Nx, x + HalfStage); ++xx)
						{
							const double Hh = static_cast<double>(M.Height[M.Index(xx, yy)]);
							Lo = std::min(Lo, Hh);
							Hi = std::max(Hi, Hh);
							Sum += Hh;
							++N;
						}
					}
					const double Cx = M.X0 + static_cast<double>(x) * M.CellCm;
					const double Cy = M.Y0 + static_cast<double>(y) * M.CellCm;
					const double Dist = std::sqrt((Cx - P.PrefX) * (Cx - P.PrefX) + (Cy - P.PrefY) * (Cy - P.PrefY));
					const double Range = N > 0 ? Hi - Lo : 0.0;
					const double Score = Range / 100.0 + (Dist / 100.0) * P.DistWeight;
					if (Score < BestScore)
					{
						BestScore = Score;
						R.bOk = true;
						R.Cx = Cx;
						R.Cy = Cy;
						R.RangeCm = Range;
						R.MeanCm = N > 0 ? Sum / static_cast<double>(N) : 0.0;
						R.bHeightKnown = N > 0;
					}
				}
			}
			R.Candidates = Cands;
			R.MarginUsed = Margin;
			if (R.bOk)
			{
				return R;
			}
			if (Margin <= 0.0)
			{
				break;
			}
			Margin = Margin > 100.0 ? 0.5 * Margin : 0.0;
		}
		return R;
	}

	/**
	 * 트인 평지가 없을 때의 마지막 길 (결정적): 무대 정사각(여유 없이) 안 막힌 칸(막힘·땅 없음)이 가장 적은 곳,
	 * 같으면 피할 칸이 적은 곳, 같으면 시작점에 가까운 곳, 같으면 먼저 본 곳. 격자가 무대보다 작으면 bOk 거짓.
	 */
	inline FR9PickResult PickLeastBlocked(const FR9ScanGrid& M, const FR9PickParams& P)
	{
		FR9PickResult R;
		if (!M.Valid() || P.SideCm <= 0.0)
		{
			return R;
		}
		const std::int32_t Nx = M.Nx;
		const std::int32_t Ny = M.Ny;
		const std::int32_t Hs = static_cast<std::int32_t>(std::ceil(0.5 * P.SideCm / M.CellCm));
		if (2 * Hs > Nx || 2 * Hs > Ny)
		{
			return R;
		}
		const std::vector<std::int32_t> SB = R9GridImpl::PrefixSum(M, [&M](std::size_t k) { return !M.IsOpen(k, false); });
		const bool bAv = M.HasAvoid();
		const std::vector<std::int32_t> SA = R9GridImpl::PrefixSum(M, [&M, bAv](std::size_t k) { return bAv && M.Avoid[k] != 0; });
		const std::int32_t Stride = std::max(1, P.Stride);
		std::int64_t BestB = std::numeric_limits<std::int64_t>::max();
		std::int64_t BestA = std::numeric_limits<std::int64_t>::max();
		double BestD = std::numeric_limits<double>::infinity();
		std::int32_t Bx = -1, By = -1;
		std::int64_t Cands = 0;
		for (std::int32_t y = Hs; y + Hs <= Ny; y += Stride)
		{
			for (std::int32_t x = Hs; x + Hs <= Nx; x += Stride)
			{
				++Cands;
				const std::int64_t B = R9GridImpl::CountIn(SB, Nx, x - Hs, y - Hs, x + Hs, y + Hs);
				const std::int64_t A = R9GridImpl::CountIn(SA, Nx, x - Hs, y - Hs, x + Hs, y + Hs);
				const double Cx = M.X0 + static_cast<double>(x) * M.CellCm;
				const double Cy = M.Y0 + static_cast<double>(y) * M.CellCm;
				const double D = std::sqrt((Cx - P.PrefX) * (Cx - P.PrefX) + (Cy - P.PrefY) * (Cy - P.PrefY));
				if (B < BestB || (B == BestB && (A < BestA || (A == BestA && D < BestD))))
				{
					BestB = B;
					BestA = A;
					BestD = D;
					Bx = x;
					By = y;
				}
			}
		}
		if (Bx < 0)
		{
			return R;
		}
		R.bOk = true;
		R.Cx = M.X0 + static_cast<double>(Bx) * M.CellCm;
		R.Cy = M.Y0 + static_cast<double>(By) * M.CellCm;
		double Lo = 0.0, Hi = 0.0, Mean = 0.0;
		if (R9GridImpl::HeightStats(M, Bx - Hs, By - Hs, Bx + Hs, By + Hs, Lo, Hi, Mean))
		{
			R.RangeCm = Hi - Lo;
			R.MeanCm = Mean;
			R.bHeightKnown = true;
		}
		R.Candidates = Cands;
		R.MarginUsed = 0.0;
		R.BlockedCells = BestB;
		R.AvoidCells = BestA;
		R.StageCells = static_cast<std::int64_t>(2 * Hs) * static_cast<std::int64_t>(2 * Hs);
		return R;
	}

	// -------------------------------------------------------------------------
	// 높이 표 (무대 위 1 m 간격) — 보이는 높이만. 행동은 평평한 세계 기준 그대로
	// -------------------------------------------------------------------------

	struct FR9HeightTable
	{
		std::int32_t Nx = 0;
		std::int32_t Ny = 0;
		double X0 = 0.0;        // 표본 (0, 0) 자리 cm
		double Y0 = 0.0;
		double Step = 100.0;    // cm
		double Fallback = 0.0;  // 표 밖·빈 표본
		std::vector<float> Z;   // NaN = 모름

		bool Valid() const { return Nx > 1 && Ny > 1 && Z.size() == static_cast<std::size_t>(Nx) * static_cast<std::size_t>(Ny); }

		double Sample(std::int32_t X, std::int32_t Y) const
		{
			X = std::clamp(X, 0, Nx - 1);
			Y = std::clamp(Y, 0, Ny - 1);
			const float V = Z[static_cast<std::size_t>(Y) * static_cast<std::size_t>(Nx) + static_cast<std::size_t>(X)];
			return std::isnan(V) ? Fallback : static_cast<double>(V);
		}

		/** (x, y) cm 의 높이 (두 점 사이 잇기). 표가 없으면 Fallback. */
		double At(double WX, double WY) const
		{
			if (!Valid())
			{
				return Fallback;
			}
			const double Fx = std::clamp((WX - X0) / Step, 0.0, static_cast<double>(Nx - 1));
			const double Fy = std::clamp((WY - Y0) / Step, 0.0, static_cast<double>(Ny - 1));
			const std::int32_t Ix = std::min(static_cast<std::int32_t>(Fx), Nx - 2);
			const std::int32_t Iy = std::min(static_cast<std::int32_t>(Fy), Ny - 2);
			const double Tx = Fx - Ix;
			const double Ty = Fy - Iy;
			const double A = Sample(Ix, Iy) * (1.0 - Tx) + Sample(Ix + 1, Iy) * Tx;
			const double B = Sample(Ix, Iy + 1) * (1.0 - Tx) + Sample(Ix + 1, Iy + 1) * Tx;
			return A * (1.0 - Ty) + B * Ty;
		}

		/** 경사 (dz/dx, dz/dy) — 중앙 차분. */
		void Slope(double WX, double WY, double& Dx, double& Dy) const
		{
			const double E = Step;
			Dx = (At(WX + E, WY) - At(WX - E, WY)) / (2.0 * E);
			Dy = (At(WX, WY + E) - At(WX, WY - E)) / (2.0 * E);
		}

		/** 표본 모두 (빈 것 빼고)의 평균·가장 낮은·가장 높은. 없으면 거짓. */
		bool Stats(double& Mean, double& Lo, double& Hi) const
		{
			double S = 0.0;
			std::int64_t N = 0;
			Lo = std::numeric_limits<double>::infinity();
			Hi = -std::numeric_limits<double>::infinity();
			for (const float V : Z)
			{
				if (std::isnan(V))
				{
					continue;
				}
				S += V;
				++N;
				Lo = std::min(Lo, static_cast<double>(V));
				Hi = std::max(Hi, static_cast<double>(V));
			}
			Mean = N > 0 ? S / static_cast<double>(N) : 0.0;
			return N > 0;
		}
	};

	// -------------------------------------------------------------------------
	// 프레임 읽기 도우미
	// -------------------------------------------------------------------------

	/** 프레임에서 id 로 찾기 (선형 — 개체는 100 마리 안). 없으면 nullptr. */
	inline const FR9Agent* FindAgent(const FR9Frame& F, std::uint32_t Id)
	{
		for (const FR9Agent& A : F.Agents)
		{
			if (A.Id == Id)
			{
				return &A;
			}
		}
		return nullptr;
	}

	/** 종별 산 개체 수. */
	inline void CountAlive(const FR9Frame& F, std::int32_t Out[kNumSpecies])
	{
		for (int s = 0; s < kNumSpecies; ++s)
		{
			Out[s] = 0;
		}
		for (const FR9Agent& A : F.Agents)
		{
			if (A.Alive() && A.Species < kNumSpecies)
			{
				++Out[A.Species];
			}
		}
	}

	/** 행동 이름 (짧게, 기록 줄·화면 글용). */
	inline const char* ActionName(std::uint8_t A)
	{
		static const char* const Names[kNumActions] = {"EAT",	 "WALK_0",	 "WALK_45",	 "WALK_90",	 "WALK_135", "WALK_180", "WALK_225",
													   "WALK_270", "WALK_315", "RUN_0",	 "RUN_45",	 "RUN_90",	 "RUN_135",	 "RUN_180",
													   "RUN_225",	 "RUN_270",	 "RUN_315",	 "SHELTER", "WATCH"};
		return A < kNumActions ? Names[A] : "?";
	}
}

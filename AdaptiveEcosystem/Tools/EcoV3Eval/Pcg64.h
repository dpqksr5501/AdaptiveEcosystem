// numpy PCG64 (np.random.default_rng 의 비트 생성기) 이어 받기 — 네이티브 평가기 EcoV3Eval 전용 (표준 헤더만).
// 파이썬 거울 세계가 reset 뒤 남긴 상태(bit_generator.state 의 state·inc, 128 비트 십진 문자열)를 받아 같은 64 비트 수열을 낸다.
// numpy pcg64.h 와 같은 식: 한 걸음 state ← state × 0x2360ED051FC65DA44385DF649FCCF645 + inc (mod 2^128),
// 출력 XSL-RR = rotr64(hi ^ lo, hi >> 58) (걸음 뒤 상태). 실수 하나 = (출력 >> 11) × 2^−53 (numpy next_double, EcoWorldV3 FRng::NextU01 과 같은 식).
// 시험: EcoV3Eval.exe --pcg-selftest (파이썬 ceval.py selftest 가 numpy 와 견준다).

#pragma once

#include <cstdint>
#include <stdexcept>
#include <string>

namespace EcoV3Eval
{
	struct FU128
	{
		std::uint64_t Hi = 0;
		std::uint64_t Lo = 0;
	};

	/** 64 × 64 → 128 (이식형 — 32 비트 조각). */
	inline FU128 Mul64(std::uint64_t A, std::uint64_t B)
	{
		const std::uint64_t A0 = A & 0xFFFFFFFFULL, A1 = A >> 32;
		const std::uint64_t B0 = B & 0xFFFFFFFFULL, B1 = B >> 32;
		const std::uint64_t P00 = A0 * B0;
		const std::uint64_t P01 = A0 * B1;
		const std::uint64_t P10 = A1 * B0;
		const std::uint64_t P11 = A1 * B1;
		const std::uint64_t Mid = (P00 >> 32) + (P01 & 0xFFFFFFFFULL) + (P10 & 0xFFFFFFFFULL);
		FU128 R;
		R.Lo = (Mid << 32) | (P00 & 0xFFFFFFFFULL);
		R.Hi = P11 + (P01 >> 32) + (P10 >> 32) + (Mid >> 32);
		return R;
	}

	/** A × B (mod 2^128). */
	inline FU128 MulMod(const FU128& A, const FU128& B)
	{
		FU128 R = Mul64(A.Lo, B.Lo);
		R.Hi += A.Hi * B.Lo + A.Lo * B.Hi;
		return R;
	}

	inline FU128 AddMod(const FU128& A, const FU128& B)
	{
		FU128 R;
		R.Lo = A.Lo + B.Lo;
		R.Hi = A.Hi + B.Hi + (R.Lo < A.Lo ? 1ULL : 0ULL);
		return R;
	}

	/** 십진 문자열 (0 ≤ x < 2^128) → 128 비트. */
	inline FU128 ParseU128(const std::string& Text)
	{
		if (Text.empty())
		{
			throw std::runtime_error("PCG64 상태 문자열이 비었다");
		}
		FU128 R;
		const FU128 Ten{0, 10};
		for (const char C : Text)
		{
			if (C < '0' || C > '9')
			{
				throw std::runtime_error("PCG64 상태는 십진 문자열이어야 한다: " + Text);
			}
			R = AddMod(MulMod(R, Ten), FU128{0, static_cast<std::uint64_t>(C - '0')});
		}
		return R;
	}

	struct FPcg64
	{
		FU128 State;
		FU128 Inc;
		std::uint64_t Draws = 0;   // 뽑은 수 (기록)

		static constexpr FU128 kMult{0x2360ED051FC65DA4ULL, 0x4385DF649FCCF645ULL};

		std::uint64_t Next()
		{
			State = AddMod(MulMod(State, kMult), Inc);
			const std::uint64_t X = State.Hi ^ State.Lo;
			const unsigned Rot = static_cast<unsigned>(State.Hi >> 58);
			++Draws;
			return (X >> Rot) | (X << ((64u - Rot) & 63u));
		}

		/** EcoWorldV3::FRng::External 에 넣는 함수. */
		static std::uint64_t Hook(void* User) { return static_cast<FPcg64*>(User)->Next(); }
	};
}

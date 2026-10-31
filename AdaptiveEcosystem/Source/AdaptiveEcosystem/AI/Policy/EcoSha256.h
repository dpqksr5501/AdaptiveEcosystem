// SHA-256 (FIPS 180-4) — 실행 중 가중치 로더(EcoV3Brain.h)가 두뇌 파일 가중치 바이트의 지문을 파이썬 hashlib.sha256 과 대조할 때 쓴다.
//
// **이 파일은 의도적으로 언리얼에 의존하지 않는다** (`<cstddef>`·`<cstdint>`·`<cstring>` 만). 엔진 해시 함수가 플랫폼마다 있는지
// 확인할 필요가 없고(GenericPlatformMisc::GetSHA256Signature 는 플랫폼 구현에 달렸다), 빌드 설정(Build.cs)을 바꾸지 않는다.
// 시험: Tests/EcoV3BrainTest.cpp (FIPS 예제 'abc'·빈 문자열·448 비트 문장·백만 'a', 내장 가중치 = 파이썬 두뇌 파일 weights_sha256).

#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>

namespace EcoSha256
{
	inline constexpr std::size_t kDigestBytes = 32;

	struct FState
	{
		std::uint32_t H[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au, 0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};
		std::uint8_t Buf[64] = {};
		std::size_t BufLen = 0;
		std::uint64_t TotalBytes = 0;
	};

	namespace Detail
	{
		inline constexpr std::uint32_t kK[64] = {
			0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
			0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
			0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
			0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
			0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
			0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
			0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
			0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u, 0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};

		inline std::uint32_t Rotr(std::uint32_t X, int N) { return (X >> N) | (X << (32 - N)); }

		inline void Block(std::uint32_t H[8], const std::uint8_t* P)
		{
			std::uint32_t W[64];
			for (int t = 0; t < 16; ++t)
			{
				W[t] = (static_cast<std::uint32_t>(P[4 * t]) << 24) | (static_cast<std::uint32_t>(P[4 * t + 1]) << 16)
					   | (static_cast<std::uint32_t>(P[4 * t + 2]) << 8) | static_cast<std::uint32_t>(P[4 * t + 3]);
			}
			for (int t = 16; t < 64; ++t)
			{
				const std::uint32_t S0 = Rotr(W[t - 15], 7) ^ Rotr(W[t - 15], 18) ^ (W[t - 15] >> 3);
				const std::uint32_t S1 = Rotr(W[t - 2], 17) ^ Rotr(W[t - 2], 19) ^ (W[t - 2] >> 10);
				W[t] = W[t - 16] + S0 + W[t - 7] + S1;
			}
			std::uint32_t A = H[0], B = H[1], C = H[2], D = H[3], E = H[4], F = H[5], G = H[6], Hh = H[7];
			for (int t = 0; t < 64; ++t)
			{
				const std::uint32_t S1 = Rotr(E, 6) ^ Rotr(E, 11) ^ Rotr(E, 25);
				const std::uint32_t Ch = (E & F) ^ (~E & G);
				const std::uint32_t T1 = Hh + S1 + Ch + kK[t] + W[t];
				const std::uint32_t S0 = Rotr(A, 2) ^ Rotr(A, 13) ^ Rotr(A, 22);
				const std::uint32_t Maj = (A & B) ^ (A & C) ^ (B & C);
				const std::uint32_t T2 = S0 + Maj;
				Hh = G;
				G = F;
				F = E;
				E = D + T1;
				D = C;
				C = B;
				B = A;
				A = T1 + T2;
			}
			H[0] += A;
			H[1] += B;
			H[2] += C;
			H[3] += D;
			H[4] += E;
			H[5] += F;
			H[6] += G;
			H[7] += Hh;
		}
	}

	inline void Update(FState& S, const void* Data, std::size_t Len)
	{
		const std::uint8_t* P = static_cast<const std::uint8_t*>(Data);
		S.TotalBytes += Len;
		while (Len > 0)
		{
			const std::size_t Take = (64 - S.BufLen) < Len ? (64 - S.BufLen) : Len;
			std::memcpy(S.Buf + S.BufLen, P, Take);
			S.BufLen += Take;
			P += Take;
			Len -= Take;
			if (S.BufLen == 64)
			{
				Detail::Block(S.H, S.Buf);
				S.BufLen = 0;
			}
		}
	}

	inline void Final(FState& S, std::uint8_t Out[kDigestBytes])
	{
		const std::uint64_t Bits = S.TotalBytes * 8u;
		const std::uint8_t One = 0x80;
		const std::uint8_t Zero = 0x00;
		Update(S, &One, 1);
		while (S.BufLen != 56)
		{
			Update(S, &Zero, 1);
		}
		std::uint8_t Len[8];
		for (int i = 0; i < 8; ++i)
		{
			Len[i] = static_cast<std::uint8_t>(Bits >> (56 - 8 * i));
		}
		Update(S, Len, 8);
		for (int i = 0; i < 8; ++i)
		{
			Out[4 * i] = static_cast<std::uint8_t>(S.H[i] >> 24);
			Out[4 * i + 1] = static_cast<std::uint8_t>(S.H[i] >> 16);
			Out[4 * i + 2] = static_cast<std::uint8_t>(S.H[i] >> 8);
			Out[4 * i + 3] = static_cast<std::uint8_t>(S.H[i]);
		}
	}

	/** 지문 32 바이트 → 소문자 16진 64 글자 + 끝 0 (파이썬 hexdigest 와 같은 꼴). */
	inline void ToHex(const std::uint8_t Digest[kDigestBytes], char Out[2 * kDigestBytes + 1])
	{
		static constexpr char kHex[] = "0123456789abcdef";
		for (std::size_t i = 0; i < kDigestBytes; ++i)
		{
			Out[2 * i] = kHex[Digest[i] >> 4];
			Out[2 * i + 1] = kHex[Digest[i] & 0x0f];
		}
		Out[2 * kDigestBytes] = '\0';
	}

	/** 한 번에: Data[0, Len) 의 SHA-256 → 16진 64 글자. */
	inline void HashHex(const void* Data, std::size_t Len, char Out[2 * kDigestBytes + 1])
	{
		FState S;
		Update(S, Data, Len);
		std::uint8_t D[kDigestBytes];
		Final(S, D);
		ToHex(D, Out);
	}
}

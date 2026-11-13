// R9 생애 골든 (설계 RL_R9_MULTISPECIES_DESIGN.md 12절 시험 14) — 언리얼 생애 함수를 엔진 없이 컴파일해 골든 값을 JSON 으로 찍는다.
//
//   g++ -std=c++17 -O2 -ffp-contract=off -Wall -Wextra -Werror -Wshadow -Wno-unused-parameter
//       -I <AdaptiveEcosystem/Source/AdaptiveEcosystem/AI/Policy> life_golden_r9_main.cpp -o life_golden_r9
//   ./life_golden_r9 > life_golden_r9.json
//
// 이 파일이 include 하는 것: EcoLifeHistoryV3.h (언리얼 모듈 원본, 읽기만 — 엔진 의존 없음).
// 옮겨 적은 것 하나: 시작 사슴 나이 서수 Rank (EcoCreatureSpawning.cpp 177~178). 그 파일은 엔진(FMath·Mass)을 써서 컴파일할 수
// 없으므로 두 줄을 그대로 옮겼다(FMath::GreatestCommonDivisor → std::gcd, int32 산술 그대로).
//
// 출력: 실수는 IEEE 비트(16 자리 16 진 문자열), 정수 해시는 16 진 문자열. 파이썬 tests/test_r9_life.py 가 같은 입력으로
// env_v2/r9_life.py 를 돌려 비트 단위로 맞춘다. 손으로 낸 골든은 쓰지 않는다(12절 14).
// 자동 실행: herbivore_rl/tests/test_r9_life.py (g++ 가 있으면 다시 컴파일해 저장된 JSON 과 같은지도 본다).

#include <cinttypes>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <numeric>
#include <utility>
#include <vector>

#include "EcoLifeHistoryV3.h"

using EcoLifeV3::Mix;
using EcoLifeV3::Unit;

static std::uint64_t Bits(double V)
{
    std::uint64_t B = 0;
    std::memcpy(&B, &V, sizeof(B));
    return B;
}

static bool GFirst = true;
static void Sep() { std::printf(GFirst ? "\n" : ",\n"); GFirst = false; }
static void H(std::uint64_t V) { std::printf("\"0x%016" PRIx64 "\"", V); }
static void D(double V) { H(Bits(V)); }

// EcoCreatureSpawning.cpp 177~178 그대로 (int32 산술).
static std::int32_t Rank(std::int32_t I, std::int32_t Count, std::uint64_t Seed)
{
    std::int32_t Stride = 31;
    while (std::gcd(Stride, Count) != 1) ++Stride;
    return (I * Stride + std::int32_t(Mix(Seed) % std::uint64_t(Count))) % Count;
}

int main()
{
    // 씨앗: 상수 몇 개 + R9 꼴 세계 씨앗 S_w = Mix(seed), S_q = Mix(S_w + q + 1) (시험 시드 44350~44352 — 판정·학습 범위 밖).
    std::vector<std::uint64_t> Seeds = {0ULL, 1ULL, 101ULL, 0x9e3779b97f4a7c15ULL, 0xffffffffffffffffULL, 0x00000000deadbeefULL};
    for (std::uint64_t S = 44350; S < 44353; ++S)
    {
        const std::uint64_t W = Mix(S);
        Seeds.push_back(W);
        for (std::uint64_t Q = 0; Q < 4; ++Q) Seeds.push_back(Mix(W + Q + 1));
    }
    std::vector<std::uint64_t> Ids = {1, 2, 3, 17, 31, 64, 65, 84, 100, 479, 480, 911, 1000, 4096, 123456789ULL,
                                      0x7fffffffffffffffULL, 0xffffffffffffffffULL};

    std::printf("{\n\"source\": \"EcoLifeHistoryV3.h engine-free + EcoCreatureSpawning.cpp 177-178 Rank transcription\",\n");

    // Mix / Unit
    std::printf("\"mix\": [");
    GFirst = true;
    std::vector<std::uint64_t> Vals = {0ULL, 1ULL, 2ULL, 911ULL, 912ULL, 0x9e3779b97f4a7c15ULL, 0xffffffffffffffffULL, 0x8000000000000000ULL};
    std::uint64_t X = 44350;
    for (int I = 0; I < 56; ++I) { X = Mix(X + std::uint64_t(I)); Vals.push_back(X); }
    for (const auto V : Vals) { Sep(); std::printf("["); H(V); std::printf(", "); H(Mix(V)); std::printf(", "); D(Unit(V)); std::printf("]"); }
    std::printf("\n],\n");

    // Founder / NaturalFounder (speed, size)
    std::printf("\"founder\": [");
    GFirst = true;
    for (const auto S : Seeds) for (const auto Id : Ids)
    {
        const auto G = EcoLifeV3::Founder(S, Id);
        Sep(); std::printf("["); H(S); std::printf(", "); H(Id); std::printf(", "); D(G.Speed); std::printf(", "); D(G.Size); std::printf("]");
    }
    std::printf("\n],\n");
    std::printf("\"natural_founder\": [");
    GFirst = true;
    for (const double Var : {0.0, 0.08, 0.1, 0.15})
        for (std::size_t SI = 0; SI < Seeds.size(); SI += 2) for (const auto Id : Ids)
        {
            const auto S = Seeds[SI];
            const auto G = EcoLifeV3::NaturalFounder(S, Id, Var);
            Sep(); std::printf("["); H(S); std::printf(", "); H(Id); std::printf(", "); D(Var); std::printf(", "); D(G.Speed);
            std::printf(", "); D(G.Size); std::printf("]");
        }
    std::printf("\n],\n");

    // Inherit: parents from founders, seeds in both Unreal forms — Native NB 73 (A ^ Mix(B) ^ offspring) and Fauna FAc 557
    // (A ^ Mix(B) ^ Mix(offspring)) — plus clamp cases.
    std::printf("\"inherit\": [");
    GFirst = true;
    for (std::size_t I = 0; I < Seeds.size(); ++I)
        for (std::uint64_t A = 1; A < 4; ++A)
            for (std::uint64_t Off = 0; Off < 3; ++Off)
            {
                const std::uint64_t B = A + 7 + I;
                const auto GA = (I % 2) ? EcoLifeV3::NaturalFounder(Seeds[I], A, .08) : EcoLifeV3::Founder(Seeds[I], A);
                const auto GB = (I % 2) ? EcoLifeV3::NaturalFounder(Seeds[I], B, .08) : EcoLifeV3::Founder(Seeds[I], B);
                for (const std::uint64_t Seed : {A ^ Mix(B) ^ Off, A ^ Mix(B) ^ Mix(Off)})
                {
                    const auto C = EcoLifeV3::Inherit(GA, GB, Seed);
                    Sep(); std::printf("["); D(GA.Speed); std::printf(", "); D(GA.Size); std::printf(", "); D(GB.Speed); std::printf(", ");
                    D(GB.Size); std::printf(", "); H(Seed); std::printf(", "); D(C.Speed); std::printf(", "); D(C.Size); std::printf("]");
                }
            }
    {
        EcoLifeV3::FGenome Lo, Hi;
        Lo.Speed = Lo.Size = .9; Hi.Speed = Hi.Size = 1.1;
        for (const auto S : Seeds)
            for (const auto& Pair : {std::make_pair(Lo, Lo), std::make_pair(Hi, Hi), std::make_pair(Lo, Hi)})
            {
                const auto C = EcoLifeV3::Inherit(Pair.first, Pair.second, S);
                Sep(); std::printf("["); D(Pair.first.Speed); std::printf(", "); D(Pair.first.Size); std::printf(", "); D(Pair.second.Speed);
                std::printf(", "); D(Pair.second.Size); std::printf(", "); H(S); std::printf(", "); D(C.Speed); std::printf(", "); D(C.Size);
                std::printf("]");
            }
    }
    std::printf("\n],\n");

    // FPopulationProfile::FounderAge — Unreal seconds and the R9 step values (maturity, juvenile fraction, max age) the world uses.
    std::printf("\"founder_age\": [");
    GFirst = true;
    struct FAgeCase { double Maturity, Juvenile, MaxAge; };
    const FAgeCase AgeCases[] = {{360, .25, 1800}, {2700, .25, 13500}, {2700, .1, 13500}, {1350, 0, 6750},
                                 {1350, .3, 6750}, {900, .4, 4500}, {180, .6, 180}};
    for (const auto& C : AgeCases)
    {
        EcoLifeV3::FPopulationProfile P;
        P.MaturitySeconds = C.Maturity; P.JuvenileFraction = C.Juvenile; P.MaxFounderAge = C.MaxAge;
        for (const int Count : {0, 1, 3, 7, 24, 64})
            for (std::size_t SI = 0; SI < Seeds.size(); SI += 7)
                for (int Ord = 0; Ord < (Count > 0 ? Count : 2); Ord += (Count > 24 ? 3 : 1))
                {
                    Sep(); std::printf("["); D(C.Maturity); std::printf(", "); D(C.Juvenile); std::printf(", "); D(C.MaxAge); std::printf(", ");
                    H(Seeds[SI]); std::printf(", %d, %d, ", Ord, Count); D(P.FounderAge(Seeds[SI], Ord, Count)); std::printf("]");
                }
    }
    std::printf("\n],\n");

    // Rank (SP 177~178)
    std::printf("\"rank\": [");
    GFirst = true;
    for (const int Count : {1, 2, 7, 16, 24, 31, 62, 64, 93, 96, 400})
        for (std::size_t SI = 0; SI < Seeds.size(); SI += 4)
            for (int I = 0; I < Count; I += (Count > 64 ? 7 : 1))
            {
                Sep(); std::printf("[%d, %d, ", I, Count); H(Seeds[SI]); std::printf(", %d]", int(Rank(I, Count, Seeds[SI])));
            }
    std::printf("\n],\n");

    // FPopulationProfile::Sex
    std::printf("\"sex\": [");
    GFirst = true;
    for (const double F : {.6, .5})
        for (const auto S : Seeds)
            for (std::uint64_t Id = 1; Id < 21; ++Id)
            {
                EcoLifeV3::FPopulationProfile P;
                P.FemaleFraction = F;
                Sep(); std::printf("["); H(S); std::printf(", "); H(Id); std::printf(", "); D(F); std::printf(", %d]", int(P.Sex(S, Id)));
            }
    std::printf("\n],\n");

    // FIndividual AgeFraction / Growth / BodyScale / SpeedScale / Maintenance (LH 196~203)
    std::printf("\"growth\": [");
    GFirst = true;
    for (const bool Natural : {false, true})
        for (const double Maturity : {360., 180., 120., 2700., 1350., 900.})
            for (const double Born : {-100., 37.5})
                for (const double Frac : {-.1, 0., .01, .25, .5, .75, .999, 1., 1.5})
                    for (const auto& G : {EcoLifeV3::Founder(Seeds[6], 3), EcoLifeV3::NaturalFounder(Seeds[7], 5, .08)})
                    {
                        EcoLifeV3::FIndividual L;
                        L.bNaturalPopulation = Natural; L.MaturitySeconds = Maturity; L.Born = Born; L.Genome = G;
                        const double Now = Born + Frac * Maturity;
                        Sep(); std::printf("[%d, ", int(Natural)); D(Maturity); std::printf(", "); D(Born); std::printf(", "); D(Now);
                        std::printf(", "); D(G.Speed); std::printf(", "); D(G.Size); std::printf(", "); D(L.AgeFraction(Now));
                        std::printf(", "); D(L.Growth(Now)); std::printf(", "); D(L.BodyScale(Now)); std::printf(", ");
                        D(L.SpeedScale(Now)); std::printf(", "); D(L.Maintenance()); std::printf("]");
                    }
    {
        EcoLifeV3::FGenome Fast;
        Fast.Speed = 1.1; Fast.Size = 1.1;
        EcoLifeV3::FIndividual L;
        L.Genome = Fast; L.MaturitySeconds = 900; L.bNaturalPopulation = true;
        Sep(); std::printf("[1, "); D(900.); std::printf(", "); D(0.); std::printf(", "); D(450.); std::printf(", "); D(Fast.Speed);
        std::printf(", "); D(Fast.Size); std::printf(", "); D(L.AgeFraction(450)); std::printf(", "); D(L.Growth(450)); std::printf(", ");
        D(L.BodyScale(450)); std::printf(", "); D(L.SpeedScale(450)); std::printf(", "); D(L.Maintenance()); std::printf("]");
    }
    std::printf("\n],\n");

    // FIndividual::CanParent (LH 204~206) at the boundaries: Resident = true, bInitialized = true, Health in [0, 1].
    std::printf("\"can_parent\": [");
    GFirst = true;
    for (const double Maturity : {2700., 1350.})
        for (const double Age : {Maturity - 1, Maturity - 1e-9, Maturity, Maturity + 1})
            for (const double Wait : {-1., 0., 1e-9, 1.})
                for (const double Energy : {.69999999, .7, 1.})
                    for (const double Health : {.69999999, .7, 1.})
                        for (const double Speed : {.95, 1.1000001})
                        {
                            EcoLifeV3::FIndividual L;
                            L.bInitialized = true; L.MaturitySeconds = Maturity; L.Genome.Speed = Speed; L.Genome.Size = 1.;
                            const double Now = 5000.;
                            L.Born = Now - Age; L.NextBirth = Now + Wait;
                            Sep(); std::printf("["); D(Now); std::printf(", "); D(L.Born); std::printf(", "); D(Maturity); std::printf(", ");
                            D(L.NextBirth); std::printf(", "); D(Energy); std::printf(", "); D(Health); std::printf(", "); D(Speed);
                            std::printf(", "); D(1.); std::printf(", %d]", int(L.CanParent(Now, Energy, true, Health)));
                        }
    std::printf("\n]\n}\n");
    return 0;
}

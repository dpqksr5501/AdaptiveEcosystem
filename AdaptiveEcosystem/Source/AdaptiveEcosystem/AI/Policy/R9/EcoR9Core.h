// EcoR9Core.h — R9 데모 학습 세계(스냅숏 b3b8e668 + s_world 변형 S__N)를 엔진과 무관한 C++17 로 옮긴 것 (헤더 전용).
//
// 무엇: 세계 상태 · 한 스텝(이동 → 물기 → 먹기 → 대사 → [짝 맺기] → 죽음·사체 → 다시 자람 → 다시 남 → 감각 기억) ·
//       관측 115 칸 · 행동 19 개 실행 · MLP 추론(115 → 64 → 64 → 19, tanh, float32 가중치) · 두뇌 파일(.r9brain) 읽기 ·
//       장면/대조 덤프(R9DUMP 1) 읽기 · 화면용 사건 목록.
// 근거: scratchpad/r9/ue_demo/SPEC_PORT.md 5·6·7 절, 견본 py/ref_step.py · py/ref_obs.py (줄 차례를 그대로 따름).
// 지킴: 표준 라이브러리만, 예외·RTTI 없음(언리얼 모듈에서도 컴파일), 실행 중 파이썬 없음, 새 손규칙 없음(학습 세계 그대로).
// 수치: 상태는 double, 관측은 double 로 셈 → [-1, 1] 자름 → float32. 합은 파이썬과 같은 차례로 더함(행렬곱·두 갈래 합 없음).
//       MSVC 에서는 이 헤더 안만 /fp:precise 로 묶는다(곱셈·덧셈 합치기·차례 바꾸기 금지 — 파이썬과 같은 값을 내려고).
#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(precise, on, push)
#endif

namespace EcoR9
{
// --------------------------------------------------------------------------------------------------------------------
// 상수
// --------------------------------------------------------------------------------------------------------------------
constexpr int kObsDim = 115;
constexpr int kNumActions = 19;
constexpr int kNumSpecies = 3;
constexpr int kNumFoods = 3;
constexpr double kEps = 1e-9;

enum ESpecies : int { SpDeer = 0, SpWolf = 1, SpBoar = 2 };
enum EFood : int { FoodGrass = 0, FoodRoot = 1, FoodMeat = 2 };
enum EAction : int { ActEat = 0, ActWalk0 = 1, ActRun0 = 9, ActShelter = 17, ActWatch = 18 };
enum ECause : int { CauseNone = 0, CauseBite = 1, CauseCounter = 2, CauseStarve = 3 };
enum EBiteOutcome : int { BiteKill = 0, BiteWound = 1, BiteCounter = 2 };
enum EGait : int { GaitStand = 0, GaitWalk = 1, GaitRun = 2 };

inline const char* SpeciesName(int Sp)
{
    return Sp == SpDeer ? "deer" : (Sp == SpWolf ? "wolf" : (Sp == SpBoar ? "boar" : "?"));
}

// 두뇌 파일 머리의 obs_names 와 맞춰 보는 표 (s_world S′ 관측 115 칸 — SPEC_PORT 6-2).
inline const char* const* ObsNames()
{
    static const char* const Names[kObsDim] = {
        "energy", "reserve", "stamina", "health", "own_size", "age_frac", "birth_wait", "food_density", "food_here",
        "in_shelter", "shelter_x", "shelter_y", "shelter_edge", "free_0", "free_1", "free_2", "free_3", "free_4", "free_5",
        "free_6", "free_7", "own_speed", "mating", "food_dir_0", "food_dir_1", "food_dir_2", "food_dir_3", "food_dir_4",
        "food_dir_5", "food_dir_6", "food_dir_7",
        "o0_present", "o0_rel_x", "o0_rel_y", "o0_dist", "o0_vel_x", "o0_vel_y", "o0_approach", "o0_approach_mem", "o0_facing", "o0_size", "o0_not_seen",
        "o1_present", "o1_rel_x", "o1_rel_y", "o1_dist", "o1_vel_x", "o1_vel_y", "o1_approach", "o1_approach_mem", "o1_facing", "o1_size", "o1_not_seen",
        "o2_present", "o2_rel_x", "o2_rel_y", "o2_dist", "o2_vel_x", "o2_vel_y", "o2_approach", "o2_approach_mem", "o2_facing", "o2_size", "o2_not_seen",
        "o3_present", "o3_rel_x", "o3_rel_y", "o3_dist", "o3_vel_x", "o3_vel_y", "o3_approach", "o3_approach_mem", "o3_facing", "o3_size", "o3_not_seen",
        "o4_present", "o4_rel_x", "o4_rel_y", "o4_dist", "o4_vel_x", "o4_vel_y", "o4_approach", "o4_approach_mem", "o4_facing", "o4_size", "o4_not_seen",
        "o5_present", "o5_rel_x", "o5_rel_y", "o5_dist", "o5_vel_x", "o5_vel_y", "o5_approach", "o5_approach_mem", "o5_facing", "o5_size", "o5_not_seen",
        "kin_count", "kin_run_frac", "kin_flow_x", "kin_flow_y",
        "k0_present", "k0_rel_x", "k0_rel_y", "k0_vel_x", "k0_vel_y", "k0_size", "k0_mate_ok",
        "k1_present", "k1_rel_x", "k1_rel_y", "k1_vel_x", "k1_vel_y", "k1_size", "k1_mate_ok"};
    return Names;
}

struct Vec2d
{
    double x = 0.0;
    double y = 0.0;
};

// --------------------------------------------------------------------------------------------------------------------
// 해시 (L:63-73 — 64 비트 감김 그대로)
// --------------------------------------------------------------------------------------------------------------------
inline uint64_t HashMix(uint64_t V)
{
    V += 0x9E3779B97F4A7C15ull;
    V = (V ^ (V >> 30)) * 0xBF58476D1CE4E5B9ull;
    V = (V ^ (V >> 27)) * 0x94D049BB133111EBull;
    return V ^ (V >> 31);
}

inline double HashUnit(uint64_t V)
{
    return static_cast<double>(HashMix(V) >> 11) * (1.0 / 9007199254740992.0);
}

inline int64_t FloorDiv(int64_t A, int64_t B)
{
    int64_t Q = A / B;
    if ((A % B != 0) && ((A < 0) != (B < 0)))
    {
        --Q;
    }
    return Q;
}

inline double Clamp(double V, double Lo, double Hi)
{
    return std::min(std::max(V, Lo), Hi);
}

// --------------------------------------------------------------------------------------------------------------------
// 덤프 읽기 (R9DUMP 1 — SPEC_PORT 10-2). 장면 파일·대조 파일 모두 이 꼴.
// --------------------------------------------------------------------------------------------------------------------
struct DumpEntry
{
    std::string Name;
    char Kind = 'd';               // 'd' f64 · 'f' f32 · 'i' i64 · 'u' u64 · 'b' 참거짓
    std::vector<int> Shape;
    std::vector<double> F;         // d, f
    std::vector<int64_t> I;        // i, b
    std::vector<uint64_t> U;       // u
    size_t Count() const { return Kind == 'u' ? U.size() : ((Kind == 'i' || Kind == 'b') ? I.size() : F.size()); }
    double AsDouble(size_t Idx) const
    {
        if (Kind == 'u') { return static_cast<double>(U[Idx]); }
        if (Kind == 'i' || Kind == 'b') { return static_cast<double>(I[Idx]); }
        return F[Idx];
    }
    int64_t AsInt(size_t Idx) const
    {
        if (Kind == 'u') { return static_cast<int64_t>(U[Idx]); }
        if (Kind == 'i' || Kind == 'b') { return I[Idx]; }
        return static_cast<int64_t>(F[Idx]);
    }
};

struct DumpBlock
{
    std::vector<std::string> Head;     // "@decision 12" → {"decision", "12"}
    std::vector<DumpEntry> Entries;    // 줄 차례 그대로 (같은 이름이 여러 번 나올 수 있음: resp_*)
    const DumpEntry* Find(const char* Name) const
    {
        for (const DumpEntry& E : Entries)
        {
            if (E.Name == Name) { return &E; }
        }
        return nullptr;
    }
};

namespace Detail
{
inline const char* SkipSpaces(const char* P, const char* End)
{
    while (P < End && (*P == ' ' || *P == '\t' || *P == '\r')) { ++P; }
    return P;
}

inline const char* ReadWord(const char* P, const char* End, std::string& Out)
{
    P = SkipSpaces(P, End);
    const char* B = P;
    while (P < End && *P != ' ' && *P != '\t' && *P != '\r' && *P != '\n') { ++P; }
    Out.assign(B, static_cast<size_t>(P - B));
    return P;
}

inline void SetErr(std::string* Err, const std::string& Msg)
{
    if (Err) { *Err = Msg; }
}
} // namespace Detail

// Text 는 끝에 '\0' 이 있어야 함 (std::string 이면 늘 있음). strtod 계열은 "C" 숫자 표기를 가정.
inline bool ParseDump(const std::string& Text, std::vector<DumpBlock>& Out, std::string* Err)
{
    Out.clear();
    const char* P = Text.c_str();
    const char* End = P + Text.size();
    // 첫 줄
    const char* Nl = static_cast<const char*>(std::memchr(P, '\n', static_cast<size_t>(End - P)));
    std::string First(P, Nl ? static_cast<size_t>(Nl - P) : static_cast<size_t>(End - P));
    while (!First.empty() && (First.back() == '\r' || First.back() == ' ')) { First.pop_back(); }
    if (First != "R9DUMP 1")
    {
        Detail::SetErr(Err, "not an R9DUMP 1 file");
        return false;
    }
    P = Nl ? Nl + 1 : End;
    std::string Word;
    while (P < End)
    {
        const char* LineEnd = static_cast<const char*>(std::memchr(P, '\n', static_cast<size_t>(End - P)));
        if (!LineEnd) { LineEnd = End; }
        const char* Q = Detail::SkipSpaces(P, LineEnd);
        if (Q >= LineEnd)
        {
            P = LineEnd + 1;
            continue;
        }
        if (*Q == '@')
        {
            DumpBlock Blk;
            ++Q;
            while (Q < LineEnd)
            {
                Q = Detail::ReadWord(Q, LineEnd, Word);
                if (!Word.empty()) { Blk.Head.push_back(Word); }
                Q = Detail::SkipSpaces(Q, LineEnd);
            }
            Out.push_back(std::move(Blk));
            P = LineEnd + 1;
            continue;
        }
        if (Out.empty())
        {
            Detail::SetErr(Err, "data line before any @ block");
            return false;
        }
        DumpEntry E;
        Q = Detail::ReadWord(Q, LineEnd, E.Name);
        std::string KindW;
        Q = Detail::ReadWord(Q, LineEnd, KindW);
        if (KindW == "f64") { E.Kind = 'd'; }
        else if (KindW == "f32") { E.Kind = 'f'; }
        else if (KindW == "i64") { E.Kind = 'i'; }
        else if (KindW == "u64") { E.Kind = 'u'; }
        else if (KindW == "b") { E.Kind = 'b'; }
        else
        {
            Detail::SetErr(Err, "unknown kind '" + KindW + "' for " + E.Name);
            return false;
        }
        char* NumEnd = nullptr;
        Q = Detail::SkipSpaces(Q, LineEnd);
        const long Nd = std::strtol(Q, &NumEnd, 10);
        Q = NumEnd;
        size_t Total = 1;
        for (long D = 0; D < Nd; ++D)
        {
            const long Dim = std::strtol(Q, &NumEnd, 10);
            if (NumEnd == Q || NumEnd > LineEnd)
            {
                Detail::SetErr(Err, "bad shape for " + E.Name);
                return false;
            }
            Q = NumEnd;
            E.Shape.push_back(static_cast<int>(Dim));
            Total *= static_cast<size_t>(Dim);
        }
        if (E.Kind == 'd' || E.Kind == 'f') { E.F.reserve(Total); }
        else if (E.Kind == 'u') { E.U.reserve(Total); }
        else { E.I.reserve(Total); }
        for (size_t K = 0; K < Total; ++K)
        {
            Q = Detail::SkipSpaces(Q, LineEnd);
            if (Q >= LineEnd)
            {
                Detail::SetErr(Err, "too few values for " + E.Name);
                return false;
            }
            if (E.Kind == 'd' || E.Kind == 'f')
            {
                const double V = std::strtod(Q, &NumEnd);
                E.F.push_back(E.Kind == 'f' ? static_cast<double>(static_cast<float>(V)) : V);
            }
            else if (E.Kind == 'u')
            {
                E.U.push_back(static_cast<uint64_t>(std::strtoull(Q, &NumEnd, 10)));
            }
            else
            {
                E.I.push_back(static_cast<int64_t>(std::strtoll(Q, &NumEnd, 10)));
            }
            if (NumEnd == Q)
            {
                Detail::SetErr(Err, "bad number in " + E.Name);
                return false;
            }
            Q = NumEnd;
        }
        Out.back().Entries.push_back(std::move(E));
        P = LineEnd + 1;
    }
    return true;
}

// --------------------------------------------------------------------------------------------------------------------
// 장면 상수 (몸 표·공통 상수·정규화·감각 — 덤프 @scene 에서 읽음, C++ 은 YAML 을 읽지 않음)
// --------------------------------------------------------------------------------------------------------------------
struct Params
{
    int64_t Seed = 0;
    int Counts[3] = {0, 0, 0};
    double Size = 60.0;
    double Cell = 2.0;
    int G = 30;
    int SpLo[3] = {0, 0, 0};
    int SpHi[3] = {0, 0, 0};
    int NumSlots = 0;
    int NumCarcass = 0;
    double RunMult[3] = {1, 1, 1};
    double JuvFrac[3] = {0, 0, 0};
    uint64_t SeedW = 0;
    uint64_t SeedQ[4] = {0, 0, 0, 0};
    std::vector<double> ShelX, ShelY, ShelR;
    // 몸 표 [종]
    double Size0[3], WalkSpeed[3], RunSpeed[3], Accel[3], StamDrain[3], StamRecover[3], SeeR[3], FovCos[3], HeadDown[3],
        SmellR[3], Drain[3], ReserveCap[3], RefillE[3], RefillFrac[3], WeakE[3], WeakSpeed[3], HpRegen[3], BiteR[3],
        Maturity[3], MassKg[3], FoodDensityRef[3], FoodHereRef[3], MaxFounderAge[3], FounderVariation[3],
        FirstBirthBase[3], FirstBirthSpread[3], FemaleFrac[3], ChildFemaleFrac[3], MateR[3], BirthR[3], BirthGrace[3];
    bool HasHp[3], ShelterEnter[3], CounterOn[3], GrowthSmooth[3], PendingNeedsParent[3];
    int FounderKind[3], SexMode[3];
    bool Eats[3][3];
    double EatRate[3][3], EPerUnit[3][3];
    bool Bites[3][3];
    int DietRank[3][3];
    bool PairBlock[3][kNumActions], BirthBlock[3][kNumActions];
    double GaitDrain[3];
    bool LifeOn = false;
    // const_*
    double StaminaLock, StaminaUnlock, WoundSpeed, EatMin, BiteConeCos, BiteApproachMin;
    int BiteCooldown;
    double CounterHpMin, CounterConeCos, CounterDamage, CounterLerp0, CounterLerp1, CounterKnockStep;
    int CounterKnockSteps, CounterNobiteSteps;
    double CounterSelfDamage, BiteBase, CarcMeatFrac, CarcKgPerUnit;
    int CarcPlaces;
    double CarcEatR, CarcDecaySteps, ShelterPush;
    double BreedEMin, BreedHpMin, BreedGestation, BreedRecover, BreedRetry, BreedCost, BreedChildE, BreedChildFat;
    int64_t BreedScanNum, BreedScanDen;
    double BreedGenerationCap, BreedClearR;
    double FatInitLo, FatInitHi, StartEnergy, RespawnNewbornFrac, RespawnFarR;
    int RespawnCandidates;
    double RespawnRingR0, RespawnRingDr;
    // norm_* · sense_*
    double NormPos, NormVel, NormSize, NormKinCount, NormKinRunSpeed, NormFlow, NormFree, NormEdge, NormSpeed, NormBirthWait,
        NormFoodR, NormFoodBoxCells, NormHereR;
    double HearSilent, HearQuiet, HearSpan, HearRQuiet, HearRLoud, MemKeep, MemGain, MemDecay;
    double Dir8[8][2], Golden8[8][2];

    bool BitesAny(int Sp) const { return Bites[Sp][0] || Bites[Sp][1] || Bites[Sp][2]; }
};

namespace Detail
{
struct Getter
{
    const DumpBlock& B;
    std::string* Err;
    bool Ok = true;

    const DumpEntry* Need(const char* Name, size_t Count)
    {
        const DumpEntry* E = B.Find(Name);
        if (!E)
        {
            if (Ok) { SetErr(Err, std::string("missing ") + Name); }
            Ok = false;
            return nullptr;
        }
        if (Count != 0 && E->Count() != Count)
        {
            if (Ok) { SetErr(Err, std::string("size mismatch ") + Name); }
            Ok = false;
            return nullptr;
        }
        return E;
    }
    double D(const char* Name)
    {
        const DumpEntry* E = Need(Name, 1);
        return E ? E->AsDouble(0) : 0.0;
    }
    int64_t I(const char* Name)
    {
        const DumpEntry* E = Need(Name, 1);
        return E ? E->AsInt(0) : 0;
    }
    void D3(const char* Name, double* Out, size_t N = 3)
    {
        const DumpEntry* E = Need(Name, N);
        for (size_t K = 0; K < N; ++K) { Out[K] = E ? E->AsDouble(K) : 0.0; }
    }
    void B3(const char* Name, bool* Out, size_t N = 3)
    {
        const DumpEntry* E = Need(Name, N);
        for (size_t K = 0; K < N; ++K) { Out[K] = E ? (E->AsInt(K) != 0) : false; }
    }
    void I3(const char* Name, int* Out, size_t N = 3)
    {
        const DumpEntry* E = Need(Name, N);
        for (size_t K = 0; K < N; ++K) { Out[K] = E ? static_cast<int>(E->AsInt(K)) : 0; }
    }
};
} // namespace Detail

inline bool LoadParams(const DumpBlock& Blk, Params& P, std::string* Err)
{
    Detail::Getter Gt{Blk, Err};
    P.Seed = Gt.I("seed");
    Gt.I3("counts", P.Counts);
    P.Size = Gt.D("world_size");
    P.Cell = Gt.D("cell");
    P.G = static_cast<int>(Gt.I("G"));
    Gt.I3("sp_lo", P.SpLo);
    Gt.I3("sp_hi", P.SpHi);
    P.NumSlots = P.SpHi[2];
    P.NumCarcass = static_cast<int>(Gt.I("carcass_slots"));
    Gt.D3("run_mult", P.RunMult);
    Gt.D3("juv_frac", P.JuvFrac);
    if (const DumpEntry* E = Gt.Need("s_w", 1)) { P.SeedW = E->Kind == 'u' ? E->U[0] : static_cast<uint64_t>(E->AsInt(0)); }
    if (const DumpEntry* E = Gt.Need("s_q", 4))
    {
        for (size_t K = 0; K < 4; ++K) { P.SeedQ[K] = E->Kind == 'u' ? E->U[K] : static_cast<uint64_t>(E->AsInt(K)); }
    }
    P.ShelX.clear();
    P.ShelY.clear();
    P.ShelR.clear();
    if (const DumpEntry* E = Gt.Need("shelters", 0))
    {
        const size_t N = E->Shape.empty() ? 0 : static_cast<size_t>(E->Shape[0]);
        for (size_t K = 0; K < N; ++K)
        {
            P.ShelX.push_back(E->F[3 * K + 0]);
            P.ShelY.push_back(E->F[3 * K + 1]);
            P.ShelR.push_back(E->F[3 * K + 2]);
        }
    }
    Gt.D3("body_size0", P.Size0);
    Gt.D3("body_walk_speed", P.WalkSpeed);
    Gt.D3("body_run_speed", P.RunSpeed);
    Gt.D3("body_accel", P.Accel);
    Gt.D3("body_stam_drain", P.StamDrain);
    Gt.D3("body_stam_recover", P.StamRecover);
    Gt.D3("body_see_r", P.SeeR);
    Gt.D3("body_fov_cos", P.FovCos);
    Gt.D3("body_head_down", P.HeadDown);
    Gt.D3("body_smell_r", P.SmellR);
    Gt.D3("body_drain", P.Drain);
    Gt.D3("body_reserve_cap", P.ReserveCap);
    Gt.D3("body_refill_e", P.RefillE);
    Gt.D3("body_refill_frac", P.RefillFrac);
    Gt.D3("body_weak_e", P.WeakE);
    Gt.D3("body_weak_speed", P.WeakSpeed);
    Gt.D3("body_hp_regen", P.HpRegen);
    Gt.D3("body_bite_r", P.BiteR);
    Gt.D3("body_maturity", P.Maturity);
    Gt.D3("body_mass_kg", P.MassKg);
    Gt.D3("body_food_density_ref", P.FoodDensityRef);
    Gt.D3("body_food_here_ref", P.FoodHereRef);
    Gt.D3("body_max_founder_age", P.MaxFounderAge);
    Gt.D3("body_founder_variation", P.FounderVariation);
    Gt.D3("body_first_birth_base", P.FirstBirthBase);
    Gt.D3("body_first_birth_spread", P.FirstBirthSpread);
    Gt.D3("body_female_frac", P.FemaleFrac);
    Gt.D3("body_child_female_frac", P.ChildFemaleFrac);
    Gt.D3("body_mate_r", P.MateR);
    Gt.D3("body_birth_r", P.BirthR);
    Gt.D3("body_birth_grace", P.BirthGrace);
    Gt.B3("body_has_hp", P.HasHp);
    Gt.B3("body_shelter_enter", P.ShelterEnter);
    Gt.B3("body_counter", P.CounterOn);
    Gt.B3("body_growth_smooth", P.GrowthSmooth);
    Gt.B3("body_pending_needs_parent", P.PendingNeedsParent);
    Gt.I3("body_founder_kind", P.FounderKind);
    Gt.I3("body_sex_mode", P.SexMode);
    {
        bool Tmp[9];
        double TmpD[9];
        int TmpI[9];
        Gt.B3("body_eats", Tmp, 9);
        for (int K = 0; K < 9; ++K) { P.Eats[K / 3][K % 3] = Tmp[K]; }
        Gt.D3("body_eat_rate", TmpD, 9);
        for (int K = 0; K < 9; ++K) { P.EatRate[K / 3][K % 3] = TmpD[K]; }
        Gt.D3("body_e_per_unit", TmpD, 9);
        for (int K = 0; K < 9; ++K) { P.EPerUnit[K / 3][K % 3] = TmpD[K]; }
        Gt.B3("body_bites", Tmp, 9);
        for (int K = 0; K < 9; ++K) { P.Bites[K / 3][K % 3] = Tmp[K]; }
        Gt.I3("diet_rank", TmpI, 9);
        for (int K = 0; K < 9; ++K) { P.DietRank[K / 3][K % 3] = TmpI[K]; }
        bool Blk19[3 * kNumActions];
        Gt.B3("body_pair_block", Blk19, 3 * kNumActions);
        for (int K = 0; K < 3 * kNumActions; ++K) { P.PairBlock[K / kNumActions][K % kNumActions] = Blk19[K]; }
        Gt.B3("body_birth_block", Blk19, 3 * kNumActions);
        for (int K = 0; K < 3 * kNumActions; ++K) { P.BirthBlock[K / kNumActions][K % kNumActions] = Blk19[K]; }
        double D16[16];
        Gt.D3("dir8", D16, 16);
        for (int K = 0; K < 16; ++K) { P.Dir8[K / 2][K % 2] = D16[K]; }
        Gt.D3("golden8", D16, 16);
        for (int K = 0; K < 16; ++K) { P.Golden8[K / 2][K % 2] = D16[K]; }
    }
    Gt.D3("gait_drain", P.GaitDrain);
    P.LifeOn = Gt.I("life_on") != 0;
    P.StaminaLock = Gt.D("const_stamina_lock");
    P.StaminaUnlock = Gt.D("const_stamina_unlock");
    P.WoundSpeed = Gt.D("const_wound_speed");
    P.EatMin = Gt.D("const_eat_min");
    P.BiteConeCos = Gt.D("const_bite_cone_cos");
    P.BiteApproachMin = Gt.D("const_bite_approach_min");
    P.BiteCooldown = static_cast<int>(Gt.D("const_bite_cooldown"));
    P.CounterHpMin = Gt.D("const_counter_hp_min");
    P.CounterConeCos = Gt.D("const_counter_cone_cos");
    P.CounterDamage = Gt.D("const_counter_damage");
    P.CounterLerp0 = Gt.D("const_counter_lerp0");
    P.CounterLerp1 = Gt.D("const_counter_lerp1");
    P.CounterKnockStep = Gt.D("const_counter_knock_step");
    P.CounterKnockSteps = static_cast<int>(Gt.D("const_counter_knock_steps"));
    P.CounterNobiteSteps = static_cast<int>(Gt.D("const_counter_nobite_steps"));
    P.CounterSelfDamage = Gt.D("const_counter_self_damage");
    P.BiteBase = Gt.D("const_bite_base");
    P.CarcMeatFrac = Gt.D("const_carc_meat_frac");
    P.CarcKgPerUnit = Gt.D("const_carc_kg_per_unit");
    P.CarcPlaces = static_cast<int>(Gt.D("const_carc_places"));
    P.CarcEatR = Gt.D("const_carc_eat_r");
    P.CarcDecaySteps = Gt.D("const_carc_decay_steps");
    P.ShelterPush = Gt.D("const_shelter_push");
    P.BreedEMin = Gt.D("const_breed_e_min");
    P.BreedHpMin = Gt.D("const_breed_hp_min");
    P.BreedGestation = Gt.D("const_breed_gestation");
    P.BreedRecover = Gt.D("const_breed_recover");
    P.BreedRetry = Gt.D("const_breed_retry");
    P.BreedCost = Gt.D("const_breed_cost");
    P.BreedChildE = Gt.D("const_breed_child_e");
    P.BreedChildFat = Gt.D("const_breed_child_fat");
    P.BreedScanNum = static_cast<int64_t>(Gt.D("const_breed_scan_num"));
    P.BreedScanDen = static_cast<int64_t>(Gt.D("const_breed_scan_den"));
    P.BreedGenerationCap = Gt.D("const_breed_generation_cap");
    P.BreedClearR = Gt.D("const_breed_clear_r");
    P.FatInitLo = Gt.D("const_fat_init_lo");
    P.FatInitHi = Gt.D("const_fat_init_hi");
    P.StartEnergy = Gt.D("const_start_energy");
    P.RespawnNewbornFrac = Gt.D("const_respawn_newborn_frac");
    P.RespawnFarR = Gt.D("const_respawn_far_r");
    P.RespawnCandidates = static_cast<int>(Gt.D("const_respawn_candidates"));
    P.RespawnRingR0 = Gt.D("const_respawn_ring_r0");
    P.RespawnRingDr = Gt.D("const_respawn_ring_dr");
    P.NormPos = Gt.D("norm_pos");
    P.NormVel = Gt.D("norm_vel");
    P.NormSize = Gt.D("norm_size");
    P.NormKinCount = Gt.D("norm_kin_count");
    P.NormKinRunSpeed = Gt.D("norm_kin_run_speed");
    P.NormFlow = Gt.D("norm_flow");
    P.NormFree = Gt.D("norm_free");
    P.NormEdge = Gt.D("norm_edge");
    P.NormSpeed = Gt.D("norm_speed");
    P.NormBirthWait = Gt.D("norm_birth_wait");
    P.NormFoodR = Gt.D("norm_food_r");
    P.NormFoodBoxCells = Gt.D("norm_food_box_cells");
    P.NormHereR = Gt.D("norm_here_r");
    P.HearSilent = Gt.D("sense_hear_silent");
    P.HearQuiet = Gt.D("sense_hear_quiet");
    P.HearSpan = Gt.D("sense_hear_span");
    P.HearRQuiet = Gt.D("sense_hear_r_quiet");
    P.HearRLoud = Gt.D("sense_hear_r_loud");
    P.MemKeep = Gt.D("sense_mem_keep");
    P.MemGain = Gt.D("sense_mem_gain");
    P.MemDecay = Gt.D("sense_mem_decay");
    if (Gt.Ok && (P.NumSlots <= 0 || P.G <= 0 || P.NumCarcass <= 0 || P.RespawnCandidates <= 0 || P.BreedScanDen <= 0))
    {
        Detail::SetErr(Err, "bad scene sizes");
        return false;
    }
    return Gt.Ok;
}

// --------------------------------------------------------------------------------------------------------------------
// 세계 상태 (덤프 FULL 줄 그대로)
// --------------------------------------------------------------------------------------------------------------------
struct Pair
{
    int A = 0, B = 0;
    int64_t UA = 0, UB = 0;
    double Due = 0.0;
    int Sp = 0;
};

struct State
{
    int64_t T = 0;
    std::vector<int> Sp;
    std::vector<Vec2d> Pos, Head, Vel, Disp, DirCmd, KnockDir;
    std::vector<double> E, R, Stam, Hp, Born, NextBirth, GSpeed, GSize, RespT;
    std::vector<int64_t> KinId, Uid, Sex, Generation, ParentA, ParentB, Offspring;
    std::vector<int> Act, BiteCd, KnockLeft;
    std::vector<uint8_t> Alive, StamLock, Mating;
    std::vector<double> Mem;   // [i * S + j]
    std::vector<double> Grass, GrassCap, GrassRegen, Root, RootCap, RootRegen;   // [iy * G + ix]
    std::vector<uint8_t> CoverCell;
    std::vector<uint8_t> CarcOk;
    std::vector<Vec2d> CarcPos;
    std::vector<double> CarcMeat, CarcMeat0, CarcT;
    std::vector<int64_t> CarcKin;
    int64_t NextUid = 1;
    std::vector<Pair> Pairs;
};

inline bool LoadState(const DumpBlock& Blk, const Params& P, State& St, std::string* Err)
{
    Detail::Getter Gt{Blk, Err};
    const size_t S = static_cast<size_t>(P.NumSlots);
    const size_t GG = static_cast<size_t>(P.G) * static_cast<size_t>(P.G);
    const size_t M = static_cast<size_t>(P.NumCarcass);
    St.T = Gt.I("t");
    auto V2 = [&Gt](const char* Name, std::vector<Vec2d>& Out, size_t N) {
        const DumpEntry* E = Gt.Need(Name, 2 * N);
        Out.assign(N, Vec2d{});
        if (!E) { return; }
        for (size_t K = 0; K < N; ++K) { Out[K] = Vec2d{E->F[2 * K], E->F[2 * K + 1]}; }
    };
    auto V1 = [&Gt](const char* Name, std::vector<double>& Out, size_t N) {
        const DumpEntry* E = Gt.Need(Name, N);
        Out.assign(N, 0.0);
        if (!E) { return; }
        for (size_t K = 0; K < N; ++K) { Out[K] = E->AsDouble(K); }
    };
    auto VI = [&Gt](const char* Name, std::vector<int64_t>& Out, size_t N) {
        const DumpEntry* E = Gt.Need(Name, N);
        Out.assign(N, 0);
        if (!E) { return; }
        for (size_t K = 0; K < N; ++K) { Out[K] = E->AsInt(K); }
    };
    auto VI32 = [&Gt](const char* Name, std::vector<int>& Out, size_t N) {
        const DumpEntry* E = Gt.Need(Name, N);
        Out.assign(N, 0);
        if (!E) { return; }
        for (size_t K = 0; K < N; ++K) { Out[K] = static_cast<int>(E->AsInt(K)); }
    };
    auto VB = [&Gt](const char* Name, std::vector<uint8_t>& Out, size_t N) {
        const DumpEntry* E = Gt.Need(Name, N);
        Out.assign(N, 0);
        if (!E) { return; }
        for (size_t K = 0; K < N; ++K) { Out[K] = E->AsInt(K) != 0 ? 1 : 0; }
    };
    VI32("slot_sp", St.Sp, S);
    V2("pos", St.Pos, S);
    V2("head", St.Head, S);
    V2("vel", St.Vel, S);
    V2("disp", St.Disp, S);
    V2("dir_cmd", St.DirCmd, S);
    V2("knock_dir", St.KnockDir, S);
    V1("E", St.E, S);
    V1("R", St.R, S);
    V1("stam", St.Stam, S);
    V1("hp", St.Hp, S);
    V1("born", St.Born, S);
    V1("next_birth", St.NextBirth, S);
    V1("g_speed", St.GSpeed, S);
    V1("g_size", St.GSize, S);
    V1("resp_t", St.RespT, S);
    VI("kin_id", St.KinId, S);
    VI("uid", St.Uid, S);
    VI("sex", St.Sex, S);
    VI32("act", St.Act, S);
    VI32("bite_cd", St.BiteCd, S);
    VI32("knock_left", St.KnockLeft, S);
    VI("generation", St.Generation, S);
    VI("parent_a", St.ParentA, S);
    VI("parent_b", St.ParentB, S);
    VI("offspring", St.Offspring, S);
    VB("alive", St.Alive, S);
    VB("stam_lock", St.StamLock, S);
    VB("mating", St.Mating, S);
    V1("mem", St.Mem, S * S);
    V1("grass", St.Grass, GG);
    V1("grass_cap", St.GrassCap, GG);
    V1("grass_regen", St.GrassRegen, GG);
    V1("root", St.Root, GG);
    V1("root_cap", St.RootCap, GG);
    V1("root_regen", St.RootRegen, GG);
    VB("cover_cell", St.CoverCell, GG);
    VB("carc_ok", St.CarcOk, M);
    V2("carc_pos", St.CarcPos, M);
    V1("carc_meat", St.CarcMeat, M);
    V1("carc_meat0", St.CarcMeat0, M);
    V1("carc_t", St.CarcT, M);
    VI("carc_kin", St.CarcKin, M);
    St.NextUid = Gt.I("next_uid");
    St.Pairs.clear();
    if (const DumpEntry* E = Blk.Find("pair"))
    {
        const size_t N = E->Shape.empty() ? 0 : static_cast<size_t>(E->Shape[0]);
        for (size_t K = 0; K < N; ++K)
        {
            Pair Pr;
            Pr.A = static_cast<int>(E->AsInt(3 * K + 0));
            Pr.B = static_cast<int>(E->AsInt(3 * K + 1));
            Pr.Due = static_cast<double>(E->AsInt(3 * K + 2));
            if (Pr.A < 0 || Pr.B < 0 || static_cast<size_t>(Pr.A) >= S || static_cast<size_t>(Pr.B) >= S)
            {
                Detail::SetErr(Err, "bad pair slot");
                return false;
            }
            Pr.UA = St.Uid[static_cast<size_t>(Pr.A)];
            Pr.UB = St.Uid[static_cast<size_t>(Pr.B)];
            Pr.Sp = St.Sp[static_cast<size_t>(Pr.A)];
            St.Pairs.push_back(Pr);
        }
    }
    if (Gt.Ok)
    {
        for (size_t K = 0; K < S; ++K)
        {
            if (St.Sp[K] < 0 || St.Sp[K] > 2 || St.Act[K] < 0 || St.Act[K] >= kNumActions)
            {
                Detail::SetErr(Err, "bad slot species/action");
                return false;
            }
        }
    }
    return Gt.Ok;
}

// --------------------------------------------------------------------------------------------------------------------
// 난수 (SPEC_PORT 8 절). 물기 순서·다시 남은 이 인터페이스로 받는다 — 실시간은 Pcg32Random, 대조는 덤프 값 주입.
// --------------------------------------------------------------------------------------------------------------------
struct RespawnDraw
{
    double UForm = 0.0;
    double UPick = 0.0;
    std::vector<double> Cand;   // 후보 nCand 개 (x0, y0, x1, y1, …) ∈ [0, Size)
    int HeadIdx = 0;            // 0..7
    double Fat = 0.0;           // 지방 몫 = U[FatInitLo, FatInitHi)
};

class IStepRandom
{
public:
    virtual ~IStepRandom() = default;
    // Out[0..N) = 0..N-1 의 순열 (늑대 칸 물기 순서)
    virtual void BitePermutation(int N, int* Out) = 0;
    virtual void Respawn(const Params& P, RespawnDraw& Out) = 0;
};

class Pcg32Random final : public IStepRandom
{
public:
    explicit Pcg32Random(uint64_t InSeed = 0x853c49e6748fea9bull, uint64_t InStream = 0xda3e39cb94b95bdbull) { Reseed(InSeed, InStream); }

    void Reseed(uint64_t InSeed, uint64_t InStream)
    {
        StateV = 0u;
        Inc = (InStream << 1u) | 1u;
        NextU32();
        StateV += InSeed;
        NextU32();
    }

    uint32_t NextU32()
    {
        const uint64_t Old = StateV;
        StateV = Old * 6364136223846793005ull + Inc;
        const uint32_t XorShifted = static_cast<uint32_t>(((Old >> 18u) ^ Old) >> 27u);
        const uint32_t Rot = static_cast<uint32_t>(Old >> 59u);
        return (XorShifted >> Rot) | (XorShifted << ((0u - Rot) & 31u));
    }

    // [0, 1) 53 비트
    double NextDouble()
    {
        const uint64_t A = NextU32() >> 5;
        const uint64_t B = NextU32() >> 6;
        return static_cast<double>(A * 67108864ull + B) * (1.0 / 9007199254740992.0);
    }

    // [0, N) 고르게 (거절 샘플링)
    uint32_t NextBelow(uint32_t N)
    {
        if (N <= 1u) { return 0u; }
        const uint32_t Threshold = (0u - N) % N;
        for (;;)
        {
            const uint32_t R = NextU32();
            if (R >= Threshold) { return R % N; }
        }
    }

    void BitePermutation(int N, int* Out) override
    {
        for (int K = 0; K < N; ++K) { Out[K] = K; }
        for (int K = N - 1; K > 0; --K)
        {
            const int J = static_cast<int>(NextBelow(static_cast<uint32_t>(K + 1)));
            std::swap(Out[K], Out[J]);
        }
    }

    void Respawn(const Params& P, RespawnDraw& Out) override
    {
        Out.UForm = NextDouble();
        Out.UPick = NextDouble();
        Out.Cand.resize(static_cast<size_t>(2 * P.RespawnCandidates));
        for (double& C : Out.Cand) { C = NextDouble() * P.Size; }
        Out.HeadIdx = static_cast<int>(NextBelow(8u));
        Out.Fat = P.FatInitLo + (P.FatInitHi - P.FatInitLo) * NextDouble();
    }

private:
    uint64_t StateV = 0;
    uint64_t Inc = 1;
};

// 대조용: 미리 정해 둔 값을 차례로 돌려줌
class InjectedRandom final : public IStepRandom
{
public:
    std::vector<int> Perm;
    std::vector<RespawnDraw> Draws;
    size_t NextDraw = 0;
    bool Underflow = false;

    void BitePermutation(int N, int* Out) override
    {
        for (int K = 0; K < N; ++K)
        {
            if (static_cast<size_t>(K) < Perm.size()) { Out[K] = Perm[static_cast<size_t>(K)]; }
            else
            {
                Out[K] = K;
                Underflow = true;
            }
        }
    }

    void Respawn(const Params& P, RespawnDraw& Out) override
    {
        if (NextDraw < Draws.size()) { Out = Draws[NextDraw++]; }
        else
        {
            Underflow = true;
            Out = RespawnDraw{};
            Out.Cand.assign(static_cast<size_t>(2 * P.RespawnCandidates), 0.0);
        }
    }
};

// --------------------------------------------------------------------------------------------------------------------
// 두뇌 (.r9brain — export_brains.py). 115 → 64 → 64 → 19, tanh, 관측 변환 없음.
// --------------------------------------------------------------------------------------------------------------------
namespace Detail
{
// SHA-256 (두뇌 본문 확인용)
inline void Sha256(const uint8_t* Data, size_t Len, uint8_t OutDigest[32])
{
    static const uint32_t Kt[64] = {
        0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u, 0xd807aa98u, 0x12835b01u,
        0x243185beu, 0x550c7dc3u, 0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
        0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau, 0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u,
        0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u, 0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
        0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u, 0x19a4c116u, 0x1e376c08u,
        0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u, 0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
        0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};
    uint32_t Hs[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au, 0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};
    auto Rotr = [](uint32_t X, uint32_t N) { return (X >> N) | (X << (32u - N)); };
    const uint64_t BitLen = static_cast<uint64_t>(Len) * 8u;
    const size_t Padded = ((Len + 9u + 63u) / 64u) * 64u;
    uint8_t Chunk[64];
    for (size_t Off = 0; Off < Padded; Off += 64u)
    {
        for (size_t K = 0; K < 64u; ++K)
        {
            const size_t Pos = Off + K;
            uint8_t V = 0;
            if (Pos < Len) { V = Data[Pos]; }
            else if (Pos == Len) { V = 0x80u; }
            else if (Pos >= Padded - 8u) { V = static_cast<uint8_t>((BitLen >> (8u * (Padded - 1u - Pos))) & 0xffu); }
            Chunk[K] = V;
        }
        uint32_t Wt[64];
        for (int K = 0; K < 16; ++K)
        {
            const size_t B4 = static_cast<size_t>(4 * K);
            Wt[K] = (static_cast<uint32_t>(Chunk[B4]) << 24) | (static_cast<uint32_t>(Chunk[B4 + 1]) << 16) |
                    (static_cast<uint32_t>(Chunk[B4 + 2]) << 8) | static_cast<uint32_t>(Chunk[B4 + 3]);
        }
        for (int K = 16; K < 64; ++K)
        {
            const uint32_t S0 = Rotr(Wt[K - 15], 7) ^ Rotr(Wt[K - 15], 18) ^ (Wt[K - 15] >> 3);
            const uint32_t S1 = Rotr(Wt[K - 2], 17) ^ Rotr(Wt[K - 2], 19) ^ (Wt[K - 2] >> 10);
            Wt[K] = Wt[K - 16] + S0 + Wt[K - 7] + S1;
        }
        uint32_t A = Hs[0], B = Hs[1], C = Hs[2], D = Hs[3], E = Hs[4], F = Hs[5], Gv = Hs[6], H = Hs[7];
        for (int K = 0; K < 64; ++K)
        {
            const uint32_t S1 = Rotr(E, 6) ^ Rotr(E, 11) ^ Rotr(E, 25);
            const uint32_t Ch = (E & F) ^ ((~E) & Gv);
            const uint32_t T1 = H + S1 + Ch + Kt[K] + Wt[K];
            const uint32_t S0 = Rotr(A, 2) ^ Rotr(A, 13) ^ Rotr(A, 22);
            const uint32_t Mj = (A & B) ^ (A & C) ^ (B & C);
            const uint32_t T2 = S0 + Mj;
            H = Gv;
            Gv = F;
            F = E;
            E = D + T1;
            D = C;
            C = B;
            B = A;
            A = T1 + T2;
        }
        Hs[0] += A; Hs[1] += B; Hs[2] += C; Hs[3] += D; Hs[4] += E; Hs[5] += F; Hs[6] += Gv; Hs[7] += H;
    }
    for (int K = 0; K < 8; ++K)
    {
        OutDigest[4 * K + 0] = static_cast<uint8_t>(Hs[K] >> 24);
        OutDigest[4 * K + 1] = static_cast<uint8_t>(Hs[K] >> 16);
        OutDigest[4 * K + 2] = static_cast<uint8_t>(Hs[K] >> 8);
        OutDigest[4 * K + 3] = static_cast<uint8_t>(Hs[K]);
    }
}

inline std::string HexOf(const uint8_t* Bytes, size_t N)
{
    static const char Digits[] = "0123456789abcdef";
    std::string Out;
    Out.reserve(2 * N);
    for (size_t K = 0; K < N; ++K)
    {
        Out.push_back(Digits[Bytes[K] >> 4]);
        Out.push_back(Digits[Bytes[K] & 15u]);
    }
    return Out;
}

// 아주 작은 JSON 찾기: "Key": 뒤의 값 시작 위치 (없으면 npos). 머리는 export_brains.py 가 쓴 한 줄.
inline size_t JsonValuePos(const std::string& J, const char* Key)
{
    const std::string Pat = std::string("\"") + Key + "\":";
    size_t P = J.find(Pat);
    if (P == std::string::npos) { return P; }
    P += Pat.size();
    while (P < J.size() && J[P] == ' ') { ++P; }
    return P;
}

inline bool JsonString(const std::string& J, const char* Key, std::string& Out)
{
    size_t P = JsonValuePos(J, Key);
    if (P == std::string::npos || P >= J.size() || J[P] != '"') { return false; }
    const size_t E = J.find('"', P + 1);
    if (E == std::string::npos) { return false; }
    Out = J.substr(P + 1, E - P - 1);
    return true;
}

inline bool JsonInt(const std::string& J, const char* Key, long long& Out)
{
    size_t P = JsonValuePos(J, Key);
    if (P == std::string::npos) { return false; }
    char* End = nullptr;
    Out = std::strtoll(J.c_str() + P, &End, 10);
    return End != J.c_str() + P;
}

// "Key": ["a", "b", …] → 문자열 목록
inline bool JsonStringList(const std::string& J, const char* Key, std::vector<std::string>& Out)
{
    Out.clear();
    size_t P = JsonValuePos(J, Key);
    if (P == std::string::npos || P >= J.size() || J[P] != '[') { return false; }
    ++P;
    while (P < J.size())
    {
        while (P < J.size() && (J[P] == ' ' || J[P] == ',')) { ++P; }
        if (P < J.size() && J[P] == ']') { return true; }
        if (P >= J.size() || J[P] != '"') { return false; }
        const size_t E = J.find('"', P + 1);
        if (E == std::string::npos) { return false; }
        Out.push_back(J.substr(P + 1, E - P - 1));
        P = E + 1;
    }
    return false;
}
} // namespace Detail

struct Brain
{
    std::string Species;
    std::string HeaderJson;
    std::string PayloadSha256;
    std::string BodyHash;
    int In = 0, H1 = 0, H2 = 0, Out = 0;
    std::vector<float> W0, B0, W1, B1, W2, B2;
    bool Valid() const { return In == kObsDim && Out == kNumActions && H1 > 0 && H2 > 0 && !W0.empty(); }
};

inline bool LoadBrain(const uint8_t* Data, size_t Len, Brain& Out, std::string* Err)
{
    Out = Brain{};
    const uint8_t* Nl = static_cast<const uint8_t*>(std::memchr(Data, '\n', Len));
    if (!Nl)
    {
        Detail::SetErr(Err, "brain: no header line");
        return false;
    }
    const size_t HeadLen = static_cast<size_t>(Nl - Data);
    Out.HeaderJson.assign(reinterpret_cast<const char*>(Data), HeadLen);
    const std::string& J = Out.HeaderJson;
    std::string Fmt, Act;
    if (!Detail::JsonString(J, "format", Fmt) || Fmt != "R9BRAIN 1")
    {
        Detail::SetErr(Err, "brain: format is not R9BRAIN 1");
        return false;
    }
    Detail::JsonString(J, "species", Out.Species);
    Detail::JsonString(J, "body_hash", Out.BodyHash);
    if (!Detail::JsonString(J, "activation", Act) || Act != "tanh")
    {
        Detail::SetErr(Err, "brain: activation is not tanh");
        return false;
    }
    long long ObsDim = 0, NAct = 0, PayloadBytes = 0;
    if (!Detail::JsonInt(J, "obs_dim", ObsDim) || !Detail::JsonInt(J, "n_actions", NAct) || !Detail::JsonInt(J, "payload_bytes", PayloadBytes))
    {
        Detail::SetErr(Err, "brain: missing obs_dim/n_actions/payload_bytes");
        return false;
    }
    {
        size_t P = Detail::JsonValuePos(J, "hidden");
        if (P == std::string::npos || J[P] != '[')
        {
            Detail::SetErr(Err, "brain: missing hidden");
            return false;
        }
        char* End = nullptr;
        const long long A = std::strtoll(J.c_str() + P + 1, &End, 10);
        while (*End == ' ' || *End == ',') { ++End; }
        const long long B = std::strtoll(End, &End, 10);
        Out.H1 = static_cast<int>(A);
        Out.H2 = static_cast<int>(B);
    }
    Out.In = static_cast<int>(ObsDim);
    Out.Out = static_cast<int>(NAct);
    if (Out.In != kObsDim || Out.Out != kNumActions || Out.H1 <= 0 || Out.H2 <= 0 || Out.H1 > 1024 || Out.H2 > 1024)
    {
        Detail::SetErr(Err, "brain: shape is not 115 -> h -> h -> 19");
        return false;
    }
    std::vector<std::string> Names;
    if (!Detail::JsonStringList(J, "obs_names", Names) || Names.size() != static_cast<size_t>(kObsDim))
    {
        Detail::SetErr(Err, "brain: obs_names missing or not 115");
        return false;
    }
    const char* const* Want = ObsNames();
    for (size_t K = 0; K < Names.size(); ++K)
    {
        if (Names[K] != Want[K])
        {
            Detail::SetErr(Err, "brain: obs_names differ at " + std::to_string(K) + " (" + Names[K] + ")");
            return false;
        }
    }
    const size_t NIn = static_cast<size_t>(Out.In), NH1 = static_cast<size_t>(Out.H1), NH2 = static_cast<size_t>(Out.H2),
                 NOut = static_cast<size_t>(Out.Out);
    const size_t NFloats = NH1 * NIn + NH1 + NH2 * NH1 + NH2 + NOut * NH2 + NOut;
    const size_t BodyLen = Len - HeadLen - 1u;
    if (PayloadBytes < 0 || static_cast<size_t>(PayloadBytes) != NFloats * 4u || BodyLen != NFloats * 4u)
    {
        Detail::SetErr(Err, "brain: payload size mismatch");
        return false;
    }
    const uint8_t* Body = Nl + 1;
    std::string WantSha;
    if (Detail::JsonString(J, "payload_sha256", WantSha))
    {
        uint8_t Dg[32];
        Detail::Sha256(Body, BodyLen, Dg);
        Out.PayloadSha256 = Detail::HexOf(Dg, 32);
        if (Out.PayloadSha256 != WantSha)
        {
            Detail::SetErr(Err, "brain: payload sha256 mismatch");
            return false;
        }
    }
    size_t Off = 0;
    auto Take = [Body, &Off](std::vector<float>& V, size_t N) {
        V.resize(N);
        for (size_t K = 0; K < N; ++K)
        {
            const uint8_t* B4 = Body + Off + 4u * K;
            const uint32_t U = static_cast<uint32_t>(B4[0]) | (static_cast<uint32_t>(B4[1]) << 8) | (static_cast<uint32_t>(B4[2]) << 16) |
                               (static_cast<uint32_t>(B4[3]) << 24);
            float F;
            std::memcpy(&F, &U, sizeof(F));
            V[K] = F;
        }
        Off += 4u * N;
    };
    Take(Out.W0, NH1 * NIn);
    Take(Out.B0, NH1);
    Take(Out.W1, NH2 * NH1);
    Take(Out.B1, NH2);
    Take(Out.W2, NOut * NH2);
    Take(Out.B2, NOut);
    return true;
}

// logits = W2·tanh(W1·tanh(W0·x + B0) + B1) + B2. 가중치·입력·출력은 float32, 곱의 합은 double 로 모은 뒤 float32 로 내림
// (numpy float32 BLAS 와 1e-6 수준 차 — SPEC_PORT 10-4 의 잰 값 2.5e-6).
inline void BrainForward(const Brain& Bn, const float* X, float* Logits)
{
    const size_t NIn = static_cast<size_t>(Bn.In), NH1 = static_cast<size_t>(Bn.H1), NH2 = static_cast<size_t>(Bn.H2),
                 NOut = static_cast<size_t>(Bn.Out);
    float Hid1[1024];
    float Hid2[1024];
    for (size_t R = 0; R < NH1; ++R)
    {
        double Acc = 0.0;
        const float* Wr = &Bn.W0[R * NIn];
        for (size_t C = 0; C < NIn; ++C) { Acc += static_cast<double>(Wr[C]) * static_cast<double>(X[C]); }
        Acc += static_cast<double>(Bn.B0[R]);
        Hid1[R] = static_cast<float>(std::tanh(static_cast<double>(static_cast<float>(Acc))));
    }
    for (size_t R = 0; R < NH2; ++R)
    {
        double Acc = 0.0;
        const float* Wr = &Bn.W1[R * NH1];
        for (size_t C = 0; C < NH1; ++C) { Acc += static_cast<double>(Wr[C]) * static_cast<double>(Hid1[C]); }
        Acc += static_cast<double>(Bn.B1[R]);
        Hid2[R] = static_cast<float>(std::tanh(static_cast<double>(static_cast<float>(Acc))));
    }
    for (size_t R = 0; R < NOut; ++R)
    {
        double Acc = 0.0;
        const float* Wr = &Bn.W2[R * NH2];
        for (size_t C = 0; C < NH2; ++C) { Acc += static_cast<double>(Wr[C]) * static_cast<double>(Hid2[C]); }
        Acc += static_cast<double>(Bn.B2[R]);
        Logits[R] = static_cast<float>(Acc);
    }
}

// 가장 높은 칸 (같으면 낮은 번호 — BR:197)
inline int ArgmaxLowest(const float* Logits, int N)
{
    int Best = 0;
    for (int K = 1; K < N; ++K)
    {
        if (Logits[K] > Logits[Best]) { Best = K; }
    }
    return Best;
}

// 확률 뽑기 (학습 때와 같음 — BR:85-94): z = double(logit) − log(−log u), argmax, 같으면 낮은 번호. u = 0 이면 −inf.
inline int GumbelPick(const float* Logits, int N, const double* U)
{
    int Best = 0;
    double BestZ = -std::numeric_limits<double>::infinity();
    for (int K = 0; K < N; ++K)
    {
        double Z;
        if (U[K] <= 0.0) { Z = -std::numeric_limits<double>::infinity(); }
        else { Z = static_cast<double>(Logits[K]) - std::log(-std::log(U[K])); }
        if (K == 0 || Z > BestZ)
        {
            Best = K;
            BestZ = Z;
        }
    }
    return Best;
}

// --------------------------------------------------------------------------------------------------------------------
// 화면용 사건 · 통계
// --------------------------------------------------------------------------------------------------------------------
enum EEventKind : int
{
    EvBite = 1,          // A 늑대 칸, B 먹이 칸, Code EBiteOutcome, X/Y 먹이 자리
    EvDeath = 2,         // A 칸, Code ECause, X/Y 자리, Value 머리 x, Value2 머리 y, B 종
    EvCarcassAdd = 3,    // A 사체 번호, B 죽은 칸, Code 죽은 종, X/Y, Value 고기
    EvCarcassGone = 4,   // A 사체 번호 (다 먹힘·썩음·덮어씀)
    EvEat = 5,           // A 칸, Code EFood, Value 먹은 양(먹이 단위), Value2 얻은 E, B 격자 셀(iy*G+ix) 또는 사체 번호
    EvRespawn = 6,       // A 칸, Code 1 갓난 꼴 · 0 먼 꼴, X/Y
    EvPairStart = 7,     // A, B 칸 (짝 맺기 켬)
    EvBirthCredit = 8,   // A, B 칸 (출산 몫, 새 몸은 생기지 않음)
};

struct Event
{
    int Kind = 0;
    int A = -1;
    int B = -1;
    int Code = 0;
    double X = 0.0, Y = 0.0;
    double Value = 0.0, Value2 = 0.0;
};

struct Stats
{
    int64_t Steps = 0;
    int64_t Decisions = 0;
    double EatenUnits[3][3] = {};   // [먹은 종][풀·땅속·고기]
    double EatenE[3][3] = {};
    int64_t BitesOut[3][3] = {};    // [물린 종][죽임·상처·반격]
    int64_t Deaths[3][4] = {};      // [종][없음·물림·반격·굶음]
    int64_t Respawns[3] = {};
    int64_t Actions[3][kNumActions] = {};
    double ESum[3] = {};
    int64_t ENum[3] = {};
    int64_t BirthCredits[3] = {};
};

// --------------------------------------------------------------------------------------------------------------------
// 세계
// --------------------------------------------------------------------------------------------------------------------
class World
{
public:
    Params P;
    State St;
    Stats Tot;                      // 누적 통계
    std::vector<Event> Events;      // 마지막 Step() 의 사건 (차례대로)

    // 마지막 Step() 의 중간값 (화면·디버그용 — dbg_*)
    std::vector<int> LastGait, LastEKind;
    std::vector<double> LastEMult, LastEdge1, LastGainU;   // LastGainU[s * 3 + f]
    std::vector<uint8_t> LastDead;
    std::vector<int> LastCause;

    bool Init(const Params& InP, const State& InSt, std::string* Err)
    {
        P = InP;
        St = InSt;
        const size_t S = static_cast<size_t>(P.NumSlots);
        if (St.Sp.size() != S || St.Mem.size() != S * S)
        {
            Detail::SetErr(Err, "state size mismatch");
            return false;
        }
        BiterSlots.clear();
        Events.clear();
        for (int Sp = 0; Sp < 3; ++Sp)
        {
            if (P.BitesAny(Sp))
            {
                for (int K = P.SpLo[Sp]; K < P.SpHi[Sp]; ++K) { BiterSlots.push_back(K); }
            }
        }
        // 물기 순서는 '물 수 있는 종의 칸' 차례 (ref_step biters) — 칸 차례로 다시 모음
        std::sort(BiterSlots.begin(), BiterSlots.end());
        Resize();
        Tot = Stats{};
        return true;
    }

    int NumSlots() const { return P.NumSlots; }

    // ---- 4 절 파생값 (지금 t 기준) ----
    void Derive()
    {
        const double Tf = static_cast<double>(St.T);
        const size_t S = static_cast<size_t>(P.NumSlots);
        for (size_t s = 0; s < S; ++s)
        {
            const int k = St.Sp[s];
            const double a = Clamp((Tf - St.Born[s]) / P.Maturity[k], 0.0, 1.0);
            const double g = 0.75 + 0.25 * (P.GrowthSmooth[k] ? a * a * (3 - 2 * a) : a);
            Af[s] = a;
            Gr[s] = g;
            BScale[s] = St.GSize[s] * g;
            SpdScale[s] = St.GSpeed[s] * (0.8 + 0.2 * g);
            const double gz = St.GSize[s];
            Maint[s] = gz * gz * gz * (1 + std::max(0.0, St.GSpeed[s] - 1) * 2);
            Mature[s] = a >= 1.0 ? 1 : 0;
        }
    }

    // ---- 5-0 결정: 행동을 받아 act·dir_cmd 를 고정 ----
    void Decide(const int* Actions)
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        for (size_t s = 0; s < S; ++s)
        {
            int a = St.Alive[s] ? Actions[s] : ActWatch;
            if (a < 0 || a >= kNumActions) { a = ActWatch; }
            St.Act[s] = a;
            const int j = (a >= 1 && a <= 8) ? a - 1 : ((a >= 9 && a <= 16) ? a - 9 : -1);
            if (j >= 0)
            {
                St.DirCmd[s] = Rot(St.Head[s], P.Dir8[j][0], P.Dir8[j][1]);
            }
            else
            {
                St.DirCmd[s] = Vec2d{};
            }
            if (St.Alive[s])
            {
                const int k = St.Sp[s];
                Tot.Actions[k][a] += 1;
                Tot.ESum[k] += St.E[s];
                Tot.ENum[k] += 1;
            }
        }
        Tot.Decisions += 1;
    }

    // 산 칸마다 두뇌로 행동을 고름. Brains[종] 이 null 이면 그 종은 WATCH. U 는 확률 뽑기용 난수(없으면 가장 높은 칸).
    void ChooseActions(const float* Obs, const Brain* const* Brains, Pcg32Random* Rng, bool bStochastic, int* ActionsOut,
                       float* LogitsOut = nullptr) const
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        float Lg[kNumActions];
        double U[kNumActions];
        for (size_t s = 0; s < S; ++s)
        {
            ActionsOut[s] = ActWatch;
            if (!St.Alive[s]) { continue; }
            const Brain* Bn = Brains[St.Sp[s]];
            if (!Bn || !Bn->Valid()) { continue; }
            BrainForward(*Bn, Obs + s * static_cast<size_t>(kObsDim), Lg);
            if (LogitsOut) { std::memcpy(LogitsOut + s * static_cast<size_t>(kNumActions), Lg, sizeof(Lg)); }
            if (bStochastic && Rng)
            {
                for (int K = 0; K < kNumActions; ++K) { U[K] = Rng->NextDouble(); }
                ActionsOut[s] = GumbelPick(Lg, kNumActions, U);
            }
            else
            {
                ActionsOut[s] = ArgmaxLowest(Lg, kNumActions);
            }
        }
    }

    // 실시간 한 스텝: t 가 짝수면 먼저 관측 → 두뇌 → 결정, 그다음 Step. ObsScratch 는 S*115.
    void Tick(const Brain* const* Brains, Pcg32Random& Rng, bool bStochastic, std::vector<float>& ObsScratch)
    {
        if ((St.T % 2) == 0)
        {
            BuildObs(ObsScratch);
            std::vector<int> Acts(static_cast<size_t>(P.NumSlots), ActWatch);
            ChooseActions(ObsScratch.data(), Brains, &Rng, bStochastic, Acts.data());
            Decide(Acts.data());
        }
        Step(Rng);
    }

    // ---- 5-1 한 스텝 ----
    void Step(IStepRandom& Rng)
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        const double Sz = P.Size;
        Events.clear();
        Derive();
        std::fill(LastDead.begin(), LastDead.end(), static_cast<uint8_t>(0));
        std::fill(LastCause.begin(), LastCause.end(), 0);
        // 1 이동 (5-2)
        for (size_t s = 0; s < S; ++s) { P0[s] = St.Pos[s]; }
        std::fill(LastGait.begin(), LastGait.end(), 0);
        std::fill(LastEKind.begin(), LastEKind.end(), -1);
        std::fill(LastEMult.begin(), LastEMult.end(), 0.0);
        for (size_t s = 0; s < S; ++s)
        {
            V1[s] = Vec2d{};
            if (!St.Alive[s]) { continue; }
            const int k = St.Sp[s];
            const int a = St.Act[s];
            double Base = 0.0, Dx = 0.0, Dy = 0.0;
            if (a == ActEat)
            {
                const int f = FirstFood(s, P0[s].x, P0[s].y);
                if (f >= 0)
                {
                    LastEKind[s] = f;
                    LastEMult[s] = 1.0;
                }
            }
            else if (a >= 1 && a <= 16)
            {
                Dx = St.DirCmd[s].x;
                Dy = St.DirCmd[s].y;
                if (a <= 8 || St.StamLock[s])
                {
                    LastGait[s] = GaitWalk;
                    Base = P.WalkSpeed[k];
                }
                else
                {
                    LastGait[s] = GaitRun;
                    Base = P.RunSpeed[k] * P.RunMult[k];
                }
            }
            const double HpF = P.WoundSpeed + (1.0 - P.WoundSpeed) * St.Hp[s];
            const double Weak = St.E[s] < P.WeakE[k] ? P.WeakSpeed[k] : 1.0;
            const double Tsp = Base * SpdScale[s] * HpF * Weak;
            const double Tvx = Dx * Tsp, Tvy = Dy * Tsp;
            const Vec2d V0 = St.Vel[s];
            const double Dvx = Tvx - V0.x, Dvy = Tvy - V0.y;
            const double N = std::sqrt(Dvx * Dvx + Dvy * Dvy);
            const double Acc = P.Accel[k];
            if (N > Acc)
            {
                const double Scl = Acc / std::max(N, kEps);
                V1[s] = Vec2d{V0.x + Dvx * Scl, V0.y + Dvy * Scl};
            }
            else
            {
                V1[s] = Vec2d{Tvx, Tvy};
            }
        }
        bool AnyNe = false;
        for (size_t s = 0; s < S; ++s)
        {
            if (St.Alive[s] && !P.ShelterEnter[St.Sp[s]]) { AnyNe = true; }
        }
        for (size_t s = 0; s < S; ++s)
        {
            Vec2d P1;
            {
                const double Psx = P0[s].x + V1[s].x;
                P1.x = Clamp(Psx, 0.0, Sz);
                if (P1.x != Psx) { V1[s].x = P1.x - P0[s].x; }
                const double Psy = P0[s].y + V1[s].y;
                P1.y = Clamp(Psy, 0.0, Sz);
                if (P1.y != Psy) { V1[s].y = P1.y - P0[s].y; }
            }
            Vec2d P2 = P1;
            if (St.Alive[s] && St.KnockLeft[s] > 0)
            {
                P2 = Vec2d{Clamp(P1.x + St.KnockDir[s].x * P.CounterKnockStep, 0.0, Sz), Clamp(P1.y + St.KnockDir[s].y * P.CounterKnockStep, 0.0, Sz)};
                St.KnockLeft[s] -= 1;
            }
            if (AnyNe && St.Alive[s] && !P.ShelterEnter[St.Sp[s]])
            {
                for (size_t c = 0; c < P.ShelX.size(); ++c)
                {
                    const double Rr = P.ShelR[c] + P.ShelterPush;
                    const double Vx = P2.x - P.ShelX[c], Vy = P2.y - P.ShelY[c];
                    const double Dd = std::sqrt(Vx * Vx + Vy * Vy);
                    if (Dd < Rr)
                    {
                        double Ux = 1.0, Uy = 0.0;
                        if (Dd > kEps)
                        {
                            Ux = Vx / std::max(Dd, kEps);
                            Uy = Vy / std::max(Dd, kEps);
                        }
                        P2 = Vec2d{P.ShelX[c] + Ux * Rr, P.ShelY[c] + Uy * Rr};
                    }
                }
                P2 = Vec2d{Clamp(P2.x, 0.0, Sz), Clamp(P2.y, 0.0, Sz)};
            }
            St.Disp[s] = St.Alive[s] ? Vec2d{P2.x - P0[s].x, P2.y - P0[s].y} : Vec2d{};
            const double Vx = V1[s].x, Vy = V1[s].y;
            if (Vx * Vx + Vy * Vy > kEps * kEps)
            {
                const double N = std::sqrt(Vx * Vx + Vy * Vy);
                St.Head[s] = Vec2d{Vx / N, Vy / N};
            }
            St.Pos[s] = P2;
            St.Vel[s] = V1[s];
        }
        for (size_t s = 0; s < S; ++s)
        {
            LastEdge1[s] = Edge(St.Pos[s].x, St.Pos[s].y);
            DrainStep[s] = P.Drain[St.Sp[s]] * P.GaitDrain[LastGait[s]] * Maint[s];
        }
        // 2 물기·반격 (5-3)
        StepBite(Rng);
        // 3 먹기 (5-4)
        StepEat();
        // 4 대사 (5-5)
        StepMetabolism();
        // 5 짝 맺기 (5-6)
        if (P.LifeOn) { StepBreed(); }
        // 6 죽음·사체 (5-7)
        StepDeaths();
        // 7 다시 자람·사체 썩음 (5-8)
        StepRegrow();
        // 8 다시 남 (5-9)
        for (size_t s = 0; s < S; ++s)
        {
            if (LastDead[s])
            {
                RespawnDraw Dr;
                Rng.Respawn(P, Dr);
                Respawn(s, Dr);
            }
        }
        // 9 감각 기억 (5-10)
        PerceiveMem();
        St.T += 1;
        Tot.Steps += 1;
    }

    // ---- 6 절 관측 115 칸 (지금 상태 기준, 기억은 바꾸지 않음). Out 은 S*115, 죽은 칸 0 ----
    void BuildObs(std::vector<float>& Out) const
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        const int G = P.G;
        const double Cell = P.Cell, Sz = P.Size;
        Out.assign(S * static_cast<size_t>(kObsDim), 0.0f);
        const double Tf = static_cast<double>(St.T);
        std::vector<double> AfL(S), SizeObs(S), Spd(S), Hr(S);
        std::vector<uint8_t> MatureL(S);
        for (size_t s = 0; s < S; ++s)
        {
            const int k = St.Sp[s];
            const double a = Clamp((Tf - St.Born[s]) / P.Maturity[k], 0.0, 1.0);
            const double g = 0.75 + 0.25 * (P.GrowthSmooth[k] ? a * a * (3 - 2 * a) : a);
            AfL[s] = a;
            SizeObs[s] = P.Size0[k] * (St.GSize[s] * g);
            MatureL[s] = a >= 1.0 ? 1 : 0;
            Spd[s] = std::sqrt(St.Disp[s].x * St.Disp[s].x + St.Disp[s].y * St.Disp[s].y);
            Hr[s] = HearR(Spd[s]);
        }
        const int Br = std::max(1, static_cast<int>(std::nearbyint(P.NormFoodR / Cell)));
        std::vector<double> Fbg, Fbr;
        BoxMean(St.Grass, Br, G, Fbg);
        BoxMean(St.Root, Br, G, Fbr);
        struct Row
        {
            double Dist;
            int J;
            double Dx, Dy, Invd;
            bool Vis;
            double Appr;
        };
        struct CRow
        {
            int C;
            double Cdx, Cdy, Cd, Ccos;
            bool Other, Sens;
        };
        std::vector<Row> Rows;
        std::vector<CRow> CRows;
        Rows.reserve(S);
        for (size_t i = 0; i < S; ++i)
        {
            if (!St.Alive[i]) { continue; }
            const int k = St.Sp[i];
            double O[kObsDim];
            for (double& V : O) { V = 0.0; }
            const double Px = St.Pos[i].x, Py = St.Pos[i].y;
            const double Hx = St.Head[i].x, Hy = St.Head[i].y;
            const double See = P.SeeR[k] * (St.Act[i] == ActEat ? P.HeadDown[k] : 1.0);
            const double Fov = P.FovCos[k], Smr = P.SmellR[k];
            Rows.clear();
            for (size_t j = 0; j < S; ++j)
            {
                if (j == i || !St.Alive[j]) { continue; }
                const double Dx = St.Pos[j].x - Px, Dy = St.Pos[j].y - Py;
                const double Dist = std::sqrt(Dx * Dx + Dy * Dy);
                const double Invd = 1.0 / std::max(Dist, kEps);
                const double CosA = (Dx * Hx + Dy * Hy) * Invd;
                const bool Vis = Dist <= See && CosA >= Fov;
                const bool Perc = Vis || Dist <= Hr[j] || Dist <= Smr;
                if (!Perc) { continue; }
                const double Appr = Clamp((-(St.Disp[j].x * Dx + St.Disp[j].y * Dy)) * Invd / P.NormVel, -1.0, 1.0);
                Rows.push_back(Row{Dist, static_cast<int>(j), Dx, Dy, Invd, Vis, Appr});
            }
            CRows.clear();
            for (size_t c = 0; c < St.CarcOk.size(); ++c)
            {
                if (!St.CarcOk[c]) { continue; }
                const double Cdx = St.CarcPos[c].x - Px, Cdy = St.CarcPos[c].y - Py;
                const double Cd = std::sqrt(Cdx * Cdx + Cdy * Cdy);
                const double Ccos = (Cdx * Hx + Cdy * Hy) / std::max(Cd, kEps);
                const bool Other = St.CarcKin[c] != St.KinId[i];
                const bool Sens = ((Cd <= See && Ccos >= Fov) || Cd <= Smr) && Other && St.CarcMeat[c] > 0.0;
                CRows.push_back(CRow{static_cast<int>(c), Cdx, Cdy, Cd, Ccos, Other, Sens});
            }
            // 자기
            O[0] = St.E[i];
            O[1] = St.R[i];
            O[2] = St.Stam[i];
            O[3] = St.Hp[i];
            O[4] = SizeObs[i] / P.NormSize;
            O[5] = AfL[i];
            O[6] = std::max(0.0, St.NextBirth[i] - Tf) / P.NormBirthWait;
            int Ix = 0, Iy = 0;
            CellOf(Px, Py, Ix, Iy);
            const size_t CellI = static_cast<size_t>(Iy) * static_cast<size_t>(G) + static_cast<size_t>(Ix);
            const double Wg = P.Eats[k][0] ? P.EPerUnit[k][0] : 0.0;
            const double Wr = P.Eats[k][1] ? P.EPerUnit[k][1] : 0.0;
            const double Wm = P.Eats[k][2] ? P.EPerUnit[k][2] : 0.0;
            const double DensGrid = Wg * Fbg[CellI] + Wr * Fbr[CellI];
            const double HereGrid = Wg * St.Grass[CellI] + Wr * St.Root[CellI];
            double Dm = 0.0, Hm = 0.0;
            for (const CRow& Cr : CRows)
            {
                if (Cr.Sens && Cr.Cd <= P.NormFoodR) { Dm = Dm + St.CarcMeat[static_cast<size_t>(Cr.C)]; }
                if (Cr.Other && Cr.Cd <= P.NormHereR) { Hm = Hm + St.CarcMeat[static_cast<size_t>(Cr.C)]; }
            }
            O[7] = (DensGrid + Wm * Dm / P.NormFoodBoxCells) / P.FoodDensityRef[k];
            O[8] = (HereGrid + Wm * Hm) / P.FoodHereRef[k];
            int Best = -1;
            double EdgeV = std::numeric_limits<double>::infinity();
            for (size_t n = 0; n < P.ShelX.size(); ++n)
            {
                const double Ex = Px - P.ShelX[n], Ey = Py - P.ShelY[n];
                const double Ev = std::sqrt(Ex * Ex + Ey * Ey) - P.ShelR[n];
                if (Ev < EdgeV)
                {
                    Best = static_cast<int>(n);
                    EdgeV = Ev;
                }
            }
            const bool Inside = EdgeV <= 0.0;
            O[9] = Inside ? 1.0 : 0.0;
            if (Best >= 0 && !Inside)
            {
                const Vec2d Uv = Unit(P.ShelX[static_cast<size_t>(Best)] - Px, P.ShelY[static_cast<size_t>(Best)] - Py);
                O[10] = Uv.x * Hx + Uv.y * Hy;
                O[11] = -Uv.x * Hy + Uv.y * Hx;
            }
            O[12] = std::min(std::max(EdgeV, 0.0), 1e9) / P.NormEdge;
            Vec2d Dd8[8];
            for (int j8 = 0; j8 < 8; ++j8)
            {
                Dd8[j8] = Rot(St.Head[i], P.Dir8[j8][0], P.Dir8[j8][1]);
                const double Ux = Dd8[j8].x, Uy = Dd8[j8].y;
                const double Inf = std::numeric_limits<double>::infinity();
                const double Tx = Ux > kEps ? (Sz - Px) / Ux : (Ux < -kEps ? Px / -Ux : Inf);
                const double Ty = Uy > kEps ? (Sz - Py) / Uy : (Uy < -kEps ? Py / -Uy : Inf);
                O[13 + j8] = std::min(Tx, Ty) / P.NormFree;
            }
            O[21] = Spd[i] / P.NormSpeed;
            O[22] = St.Mating[i] ? 1.0 : 0.0;
            // food_dir 23..30 (6-3)
            {
                const double Re = See, Rs = Smr;
                auto Wgt = [Re, Rs, Fov](double Dv, double CosA) {
                    const double Ws = (Dv <= Re && CosA >= Fov) ? 1.0 - Dv / std::max(Re, 1e-9) : 0.0;
                    const double Wn = Dv <= Rs ? 1.0 - Dv / std::max(Rs, 1e-9) : 0.0;
                    return std::max(Ws, Wn);
                };
                auto Sector = [&Dd8](double Vx, double Vy) {
                    int Bj = 0;
                    double Bv = -std::numeric_limits<double>::infinity();
                    for (int j8 = 0; j8 < 8; ++j8)
                    {
                        const double V = Vx * Dd8[j8].x + Vy * Dd8[j8].y;
                        if (V > Bv)
                        {
                            Bj = j8;
                            Bv = V;
                        }
                    }
                    return Bj;
                };
                double Parts[2][8] = {};
                for (int f = 0; f < 2; ++f)
                {
                    if (!P.Eats[k][f]) { continue; }
                    const std::vector<double>& Grid = f == 0 ? St.Grass : St.Root;
                    const double Ef = P.EPerUnit[k][f];
                    const int N = static_cast<int>(std::ceil(std::max(Re, Rs) / Cell)) + 1;
                    for (int Oy = -N; Oy <= N; ++Oy)
                    {
                        for (int Ox = -N; Ox <= N; ++Ox)
                        {
                            const int Cx = Ix + Ox, Cy = Iy + Oy;
                            if (!(Cx >= 0 && Cx < G && Cy >= 0 && Cy < G) || (Ox == 0 && Oy == 0)) { continue; }
                            const double Gv = Grid[static_cast<size_t>(Cy) * static_cast<size_t>(G) + static_cast<size_t>(Cx)];
                            if (Gv < P.EatMin) { continue; }
                            const double Vx = (Cx + 0.5) * Cell - Px;
                            const double Vy = (Cy + 0.5) * Cell - Py;
                            const double Dv = std::sqrt(Vx * Vx + Vy * Vy);
                            const double Invd = 1.0 / std::max(Dv, 1e-9);
                            const double CosA = (Vx * Hx + Vy * Hy) * Invd;
                            const int Sec = Sector(Vx, Vy);
                            Parts[f][Sec] += Gv * Wgt(Dv, CosA) * Ef;
                        }
                    }
                }
                double Pm[8] = {};
                if (P.Eats[k][2])
                {
                    for (const CRow& Cr : CRows)
                    {
                        const double Meat = St.CarcMeat[static_cast<size_t>(Cr.C)];
                        if (Cr.Other && Meat > 0.0 && Cr.Cd > P.NormHereR && ((Cr.Cd <= Re && Cr.Ccos >= Fov) || Cr.Cd <= Rs))
                        {
                            Pm[Sector(Cr.Cdx, Cr.Cdy)] += Meat * Wgt(Cr.Cd, Cr.Ccos) * P.EPerUnit[k][2];
                        }
                    }
                }
                for (int j8 = 0; j8 < 8; ++j8)
                {
                    const double X = ((0.0 + Parts[0][j8]) + Parts[1][j8]) + Pm[j8];
                    O[23 + j8] = X / (X + P.FoodHereRef[k]);
                }
            }
            // 다른 종 · 동족
            std::sort(Rows.begin(), Rows.end(), [](const Row& L, const Row& Rr) { return L.Dist < Rr.Dist || (L.Dist == Rr.Dist && L.J < Rr.J); });
            int NOth = 0;
            int KinCnt = 0;
            double NRun = 0.0, Fx = 0.0, Fy = 0.0;
            int NKinSlot = 0;
            for (const Row& Rw : Rows)
            {
                const size_t j = static_cast<size_t>(Rw.J);
                if (St.KinId[j] != St.KinId[i])
                {
                    if (NOth >= 6) { continue; }
                    const int B0 = 31 + 11 * NOth;
                    O[B0] = 1.0;
                    O[B0 + 1] = (Rw.Dx * Hx + Rw.Dy * Hy) / P.NormPos;
                    O[B0 + 2] = (-Rw.Dx * Hy + Rw.Dy * Hx) / P.NormPos;
                    O[B0 + 3] = Rw.Dist / P.NormPos;
                    O[B0 + 4] = (St.Disp[j].x * Hx + St.Disp[j].y * Hy) / P.NormVel;
                    O[B0 + 5] = (-St.Disp[j].x * Hy + St.Disp[j].y * Hx) / P.NormVel;
                    O[B0 + 6] = Rw.Appr;
                    O[B0 + 7] = St.Mem[i * S + j];
                    O[B0 + 8] = -(St.Head[j].x * Rw.Dx + St.Head[j].y * Rw.Dy) * Rw.Invd;
                    O[B0 + 9] = SizeObs[j] / P.NormSize;
                    O[B0 + 10] = Rw.Vis ? 0.0 : 1.0;
                    ++NOth;
                }
                else
                {
                    if (NKinSlot < 2)
                    {
                        const int B0 = 101 + 7 * NKinSlot;
                        O[B0] = 1.0;
                        O[B0 + 1] = (Rw.Dx * Hx + Rw.Dy * Hy) / P.NormPos;
                        O[B0 + 2] = (-Rw.Dx * Hy + Rw.Dy * Hx) / P.NormPos;
                        O[B0 + 3] = (St.Disp[j].x * Hx + St.Disp[j].y * Hy) / P.NormVel;
                        O[B0 + 4] = (-St.Disp[j].x * Hy + St.Disp[j].y * Hx) / P.NormVel;
                        O[B0 + 5] = SizeObs[j] / P.NormSize;
                        const int64_t Si = St.Sex[i], Sj = St.Sex[j];
                        const bool Comp = (Si == 0 && Sj == 0) || (Si != 0 && Sj != 0 && Si != Sj);
                        O[B0 + 6] = (MatureL[j] && Comp) ? 1.0 : 0.0;
                        ++NKinSlot;
                    }
                }
            }
            // 동족 요약: 느낀 동족을 칸 차례로 더함
            {
                std::vector<int> Ks;
                for (const Row& Rw : Rows)
                {
                    if (St.KinId[static_cast<size_t>(Rw.J)] == St.KinId[i]) { Ks.push_back(Rw.J); }
                }
                std::sort(Ks.begin(), Ks.end());
                for (int jj : Ks)
                {
                    const size_t j = static_cast<size_t>(jj);
                    NRun = NRun + (Spd[j] > P.NormKinRunSpeed ? 1.0 : 0.0);
                    Fx = Fx + St.Disp[j].x;
                    Fy = Fy + St.Disp[j].y;
                }
                KinCnt = static_cast<int>(Ks.size());
            }
            O[97] = static_cast<double>(KinCnt) / P.NormKinCount;
            if (KinCnt > 0)
            {
                const double Cf = static_cast<double>(KinCnt);
                O[98] = NRun / Cf;
                const double Mfx = Fx / Cf, Mfy = Fy / Cf;
                O[99] = (Mfx * Hx + Mfy * Hy) / P.NormFlow;
                O[100] = (-Mfx * Hy + Mfy * Hx) / P.NormFlow;
            }
            float* Dst = &Out[i * static_cast<size_t>(kObsDim)];
            for (int c = 0; c < kObsDim; ++c) { Dst[c] = static_cast<float>(Clamp(O[c], -1.0, 1.0)); }
        }
    }

    // 지금 위치가 어느 은신처 안인지 (화면용: 가장자리 거리 ≤ 0)
    bool InShelter(int Slot) const
    {
        const size_t s = static_cast<size_t>(Slot);
        return Edge(St.Pos[s].x, St.Pos[s].y) <= 0.0;
    }

    double SizeScale(int Slot) const   // 크기 배율 g_size × gr (성체 메시 기준)
    {
        const size_t s = static_cast<size_t>(Slot);
        const int k = St.Sp[s];
        const double a = Clamp((static_cast<double>(St.T) - St.Born[s]) / P.Maturity[k], 0.0, 1.0);
        const double g = 0.75 + 0.25 * (P.GrowthSmooth[k] ? a * a * (3 - 2 * a) : a);
        return St.GSize[s] * g;
    }

private:
    std::vector<int> BiterSlots;
    std::vector<double> Af, Gr, BScale, SpdScale, Maint, DrainStep;
    std::vector<uint8_t> Mature;
    std::vector<Vec2d> P0, V1;
    std::vector<double> GainE;
    std::vector<double> CellDemand;
    std::vector<uint8_t> CellTouched;
    std::vector<int> TouchedList;

    void Resize()
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        const size_t GG = static_cast<size_t>(P.G) * static_cast<size_t>(P.G);
        Af.assign(S, 0.0);
        Gr.assign(S, 0.0);
        BScale.assign(S, 0.0);
        SpdScale.assign(S, 0.0);
        Maint.assign(S, 0.0);
        DrainStep.assign(S, 0.0);
        Mature.assign(S, 0);
        P0.assign(S, Vec2d{});
        V1.assign(S, Vec2d{});
        GainE.assign(S, 0.0);
        LastGait.assign(S, 0);
        LastEKind.assign(S, -1);
        LastEMult.assign(S, 0.0);
        LastEdge1.assign(S, 0.0);
        LastGainU.assign(S * 3u, 0.0);
        LastDead.assign(S, 0);
        LastCause.assign(S, 0);
        CellDemand.assign(GG, 0.0);
        CellTouched.assign(GG, 0);
        TouchedList.clear();
        Derive();
    }

    static Vec2d Rot(const Vec2d& H, double C, double Sn) { return Vec2d{H.x * C - H.y * Sn, H.x * Sn + H.y * C}; }

    static Vec2d Unit(double Vx, double Vy)
    {
        const double N = std::sqrt(Vx * Vx + Vy * Vy);
        return N > kEps ? Vec2d{Vx / N, Vy / N} : Vec2d{};
    }

    void CellOf(double X, double Y, int& Ix, int& Iy) const
    {
        const double Inv = 1.0 / P.Cell;
        Ix = std::min(std::max(static_cast<int>(X * Inv), 0), P.G - 1);
        Iy = std::min(std::max(static_cast<int>(Y * Inv), 0), P.G - 1);
    }

    double HearR(double Spd) const
    {
        if (Spd < P.HearSilent) { return 0.0; }
        const double Tt = Clamp((Spd - P.HearQuiet) / P.HearSpan, 0.0, 1.0);
        return P.HearRQuiet + (P.HearRLoud - P.HearRQuiet) * Tt;
    }

    double Edge(double X, double Y) const
    {
        double E = std::numeric_limits<double>::infinity();
        for (size_t c = 0; c < P.ShelX.size(); ++c)
        {
            const double Dx = X - P.ShelX[c], Dy = Y - P.ShelY[c];
            E = std::min(E, std::sqrt(Dx * Dx + Dy * Dy) - P.ShelR[c]);
        }
        return E;
    }

    bool Outside(double X, double Y, double Margin) const
    {
        for (size_t c = 0; c < P.ShelX.size(); ++c)
        {
            const double Dx = X - P.ShelX[c], Dy = Y - P.ShelY[c];
            if (!(std::sqrt(Dx * Dx + Dy * Dy) > P.ShelR[c] + Margin)) { return false; }
        }
        return true;
    }

    double MassRatio(size_t s) const
    {
        const double g = St.GSize[s];
        return g * g * g * (0.12 + (1.0 - 0.12) * Af[s]);
    }

    // R8:163-172 같은 차례: 행 누적 → 열 누적 → 네 귀퉁이
    static void BoxMean(const std::vector<double>& F, int Br, int G, std::vector<double>& Out)
    {
        const size_t Gs = static_cast<size_t>(G);
        std::vector<double> C1(Gs * Gs, 0.0);
        for (size_t x = 0; x < Gs; ++x)
        {
            double Acc = 0.0;
            for (size_t y = 0; y < Gs; ++y)
            {
                Acc = Acc + F[y * Gs + x];
                C1[y * Gs + x] = Acc;
            }
        }
        const size_t G1 = Gs + 1u;
        std::vector<double> Sat(G1 * G1, 0.0);
        for (size_t y = 0; y < Gs; ++y)
        {
            double Acc = 0.0;
            for (size_t x = 0; x < Gs; ++x)
            {
                Acc = Acc + C1[y * Gs + x];
                Sat[(y + 1u) * G1 + (x + 1u)] = Acc;
            }
        }
        std::vector<int> R0(Gs), R1(Gs);
        for (int q = 0; q < G; ++q)
        {
            R0[static_cast<size_t>(q)] = std::min(std::max(q - Br, 0), G);
            R1[static_cast<size_t>(q)] = std::min(std::max(q + Br + 1, 0), G);
        }
        Out.assign(Gs * Gs, 0.0);
        for (size_t y = 0; y < Gs; ++y)
        {
            for (size_t x = 0; x < Gs; ++x)
            {
                const size_t Y0 = static_cast<size_t>(R0[y]), Y1 = static_cast<size_t>(R1[y]);
                const size_t X0 = static_cast<size_t>(R0[x]), X1 = static_cast<size_t>(R1[x]);
                const double Box = ((Sat[Y1 * G1 + X1] - Sat[Y0 * G1 + X1]) - Sat[Y1 * G1 + X0]) + Sat[Y0 * G1 + X0];
                Out[y * Gs + x] = Box / static_cast<double>((R1[y] - R0[y]) * (R1[x] - R0[x]));
            }
        }
    }

    int FirstFood(size_t s, double X, double Y) const
    {
        const int k = St.Sp[s];
        int Ix = 0, Iy = 0;
        CellOf(X, Y, Ix, Iy);
        const size_t Ci = static_cast<size_t>(Iy) * static_cast<size_t>(P.G) + static_cast<size_t>(Ix);
        int BestRank = 99, Bf = -1;
        for (int f = 0; f < 3; ++f)
        {
            if (!P.Eats[k][f]) { continue; }
            bool Ok = false;
            if (f == FoodGrass) { Ok = St.Grass[Ci] >= P.EatMin; }
            else if (f == FoodRoot) { Ok = St.Root[Ci] >= P.EatMin; }
            else
            {
                for (size_t c = 0; c < St.CarcOk.size(); ++c)
                {
                    if (St.CarcOk[c] && St.CarcMeat[c] > 0.0 && St.CarcKin[c] != St.KinId[s])
                    {
                        const double Dx = St.CarcPos[c].x - X, Dy = St.CarcPos[c].y - Y;
                        if (std::sqrt(Dx * Dx + Dy * Dy) <= P.CarcEatR)
                        {
                            Ok = true;
                            break;
                        }
                    }
                }
            }
            if (Ok && P.DietRank[k][f] < BestRank)
            {
                BestRank = P.DietRank[k][f];
                Bf = f;
            }
        }
        return Bf;
    }

    void Kill(size_t s, int Cause)
    {
        LastDead[s] = 1;
        St.Alive[s] = 0;
        LastCause[s] = Cause;
    }

    void StepBite(IStepRandom& Rng)
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        const size_t NB = BiterSlots.size();
        for (int w : BiterSlots)
        {
            const size_t ws = static_cast<size_t>(w);
            St.BiteCd[ws] = std::max(St.BiteCd[ws] - 1, 0);
        }
        // 후보 목록 (이동 뒤 위치·머리·자기 속도)
        std::vector<std::vector<std::pair<double, int>>> Can(NB);
        std::vector<uint8_t> HasCan(NB, 0);
        for (size_t bi = 0; bi < NB; ++bi)
        {
            const size_t w = static_cast<size_t>(BiterSlots[bi]);
            if (!(St.Alive[w] && St.BiteCd[w] == 0)) { continue; }
            const int k = St.Sp[w];
            const double Reach = P.BiteR[k] * BScale[w];
            for (size_t j = 0; j < S; ++j)
            {
                if (!St.Alive[j] || !P.Bites[k][St.Sp[j]] || !(LastEdge1[j] > 0.0)) { continue; }
                const double Dx = St.Pos[j].x - St.Pos[w].x, Dy = St.Pos[j].y - St.Pos[w].y;
                const double Dist = std::sqrt(Dx * Dx + Dy * Dy);
                const double Invd = 1.0 / std::max(Dist, kEps);
                const bool Cone = (Dx * St.Head[w].x + Dy * St.Head[w].y) * Invd >= P.BiteConeCos;
                const bool Appr = (Dx * St.Vel[w].x + Dy * St.Vel[w].y) * Invd > P.BiteApproachMin;
                if (Dist <= Reach && Cone && Appr) { Can[bi].push_back(std::make_pair(Dist, static_cast<int>(j))); }
            }
            if (!Can[bi].empty()) { HasCan[bi] = 1; }
        }
        std::vector<int> Perm(NB, 0);
        if (NB > 0) { Rng.BitePermutation(static_cast<int>(NB), Perm.data()); }
        for (size_t q = 0; q < NB; ++q)
        {
            const int Wi = Perm[q];
            if (Wi < 0 || static_cast<size_t>(Wi) >= NB) { continue; }
            const size_t bi = static_cast<size_t>(Wi);
            const size_t w = static_cast<size_t>(BiterSlots[bi]);
            if (!HasCan[bi] || !St.Alive[w]) { continue; }
            bool Found = false;
            double BestD = 0.0;
            int BestJ = -1;
            for (const std::pair<double, int>& Cd : Can[bi])
            {
                if (!St.Alive[static_cast<size_t>(Cd.second)]) { continue; }
                if (!Found || Cd.first < BestD || (Cd.first == BestD && Cd.second < BestJ))
                {
                    Found = true;
                    BestD = Cd.first;
                    BestJ = Cd.second;
                }
            }
            if (!Found) { continue; }
            ResolveBite(w, static_cast<size_t>(BestJ));
        }
    }

    void ResolveBite(size_t w, size_t j)
    {
        const int kj = St.Sp[j];
        int Outcome = BiteWound;
        if (!P.HasHp[kj])
        {
            Kill(j, CauseBite);
            St.BiteCd[w] = P.BiteCooldown;
            Outcome = BiteKill;
        }
        else
        {
            const double Twx = St.Pos[w].x - St.Pos[j].x, Twy = St.Pos[w].y - St.Pos[j].y;
            const double Tl = std::sqrt(Twx * Twx + Twy * Twy);
            Vec2d Tu{1.0, 0.0};
            if (Tl > kEps) { Tu = Vec2d{Twx / Tl, Twy / Tl}; }
            const double Front = St.Head[j].x * Tu.x + St.Head[j].y * Tu.y;
            if (P.CounterOn[kj] && St.Hp[j] >= P.CounterHpMin && Front >= P.CounterConeCos)
            {
                const double Dmg = P.CounterDamage * BScale[j] * (P.CounterLerp0 + (P.CounterLerp1 - P.CounterLerp0) * Af[j]);
                St.Hp[w] = std::max(0.0, St.Hp[w] - Dmg);
                St.KnockDir[w] = Tu;
                St.KnockLeft[w] = P.CounterKnockSteps;
                St.BiteCd[w] = P.CounterNobiteSteps;
                St.Hp[j] = std::max(0.0, St.Hp[j] - P.CounterSelfDamage);
                Outcome = BiteCounter;
                if (St.Hp[w] <= 0.0) { Kill(w, CauseCounter); }
            }
            else
            {
                const double Loss = Clamp(P.BiteBase / MassRatio(j), P.BiteBase, 1.0);
                St.Hp[j] = std::max(0.0, St.Hp[j] - Loss);
                St.BiteCd[w] = P.BiteCooldown;
                if (St.Hp[j] <= 0.0)
                {
                    Kill(j, CauseBite);
                    Outcome = BiteKill;
                }
            }
        }
        Tot.BitesOut[kj][Outcome] += 1;
        Event Ev;
        Ev.Kind = EvBite;
        Ev.A = static_cast<int>(w);
        Ev.B = static_cast<int>(j);
        Ev.Code = Outcome;
        Ev.X = St.Pos[j].x;
        Ev.Y = St.Pos[j].y;
        Events.push_back(Ev);
    }

    void StepEat()
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        const size_t G = static_cast<size_t>(P.G);
        std::fill(LastGainU.begin(), LastGainU.end(), 0.0);
        std::vector<double> EDr(S);
        for (size_t s = 0; s < S; ++s)
        {
            EDr[s] = St.E[s] - DrainStep[s];
            GainE[s] = 0.0;
        }
        std::vector<double> Want(S, 0.0);
        std::vector<size_t> CellIdx(S, 0);
        for (int f = 0; f < 2; ++f)
        {
            std::vector<double>& Grid = f == 0 ? St.Grass : St.Root;
            TouchedList.clear();
            for (size_t s = 0; s < S; ++s)
            {
                Want[s] = 0.0;
                if (St.Alive[s] && LastEKind[s] == f)
                {
                    const int k = St.Sp[s];
                    Want[s] = Clamp((1.0 - EDr[s]) / P.EPerUnit[k][f], 0.0, P.EatRate[k][f]) * LastEMult[s];
                    int Ix = 0, Iy = 0;
                    CellOf(St.Pos[s].x, St.Pos[s].y, Ix, Iy);
                    const size_t Ci = static_cast<size_t>(Iy) * G + static_cast<size_t>(Ix);
                    CellIdx[s] = Ci;
                    if (!CellTouched[Ci])
                    {
                        CellTouched[Ci] = 1;
                        CellDemand[Ci] = 0.0;
                        TouchedList.push_back(static_cast<int>(Ci));
                    }
                    CellDemand[Ci] = CellDemand[Ci] + Want[s];
                }
            }
            // 셀마다 frac (CellDemand 자리에 frac 을 덮어씀)
            for (int CiI : TouchedList)
            {
                const size_t Ci = static_cast<size_t>(CiI);
                const double Dm = CellDemand[Ci];
                const double Taken = std::min(Dm, Grid[Ci]);
                const double Frac = Dm > 0 ? Taken / Dm : 0.0;
                Grid[Ci] = Grid[Ci] - Taken;
                CellDemand[Ci] = Frac;
            }
            for (size_t s = 0; s < S; ++s)
            {
                if (St.Alive[s] && LastEKind[s] == f)
                {
                    const double Gu = Want[s] * CellDemand[CellIdx[s]];
                    const int k = St.Sp[s];
                    LastGainU[s * 3u + static_cast<size_t>(f)] = Gu;
                    GainE[s] = GainE[s] + Gu * P.EPerUnit[k][f];
                    Tot.EatenUnits[k][f] += Gu;
                    Tot.EatenE[k][f] += Gu * P.EPerUnit[k][f];
                    if (Gu > 0.0)
                    {
                        Event Ev;
                        Ev.Kind = EvEat;
                        Ev.A = static_cast<int>(s);
                        Ev.B = static_cast<int>(CellIdx[s]);
                        Ev.Code = f;
                        Ev.X = St.Pos[s].x;
                        Ev.Y = St.Pos[s].y;
                        Ev.Value = Gu;
                        Ev.Value2 = Gu * P.EPerUnit[k][f];
                        Events.push_back(Ev);
                    }
                }
            }
            for (int CiI : TouchedList) { CellTouched[static_cast<size_t>(CiI)] = 0; }
        }
        // 고기
        struct Eater
        {
            int C;
            double D;
            int Sl;
        };
        std::vector<Eater> Eaters;
        for (size_t s = 0; s < S; ++s)
        {
            if (!(St.Alive[s] && LastEKind[s] == FoodMeat)) { continue; }
            bool Found = false;
            double BestD = 0.0;
            int BestC = -1;
            for (size_t c = 0; c < St.CarcOk.size(); ++c)
            {
                if (St.CarcOk[c] && St.CarcMeat[c] > 0.0 && St.CarcKin[c] != St.KinId[s])
                {
                    const double Dx = St.CarcPos[c].x - St.Pos[s].x, Dy = St.CarcPos[c].y - St.Pos[s].y;
                    const double Dd = std::sqrt(Dx * Dx + Dy * Dy);
                    if (Dd <= P.CarcEatR && (!Found || Dd < BestD))
                    {
                        Found = true;
                        BestD = Dd;
                        BestC = static_cast<int>(c);
                    }
                }
            }
            if (Found) { Eaters.push_back(Eater{BestC, BestD, static_cast<int>(s)}); }
        }
        if (!Eaters.empty())
        {
            const size_t M = St.CarcOk.size();
            std::vector<uint8_t> Keep(S, 0);
            for (size_t c = 0; c < M; ++c)
            {
                std::vector<std::pair<double, int>> Grp;
                for (const Eater& Ea : Eaters)
                {
                    if (Ea.C == static_cast<int>(c)) { Grp.push_back(std::make_pair(Ea.D, Ea.Sl)); }
                }
                if (Grp.empty()) { continue; }
                std::sort(Grp.begin(), Grp.end());
                for (size_t q = 0; q < Grp.size() && q < static_cast<size_t>(P.CarcPlaces); ++q) { Keep[static_cast<size_t>(Grp[q].second)] = 1; }
            }
            std::vector<double> CDemand(M, 0.0), CFrac(M, 0.0);
            std::vector<uint8_t> CHas(M, 0);
            std::vector<double> WantM(S, 0.0);
            std::vector<int> WantC(S, -1);
            // Eaters 는 이미 칸 차례
            for (const Eater& Ea : Eaters)
            {
                const size_t s = static_cast<size_t>(Ea.Sl);
                if (!Keep[s]) { continue; }
                const int k = St.Sp[s];
                WantM[s] = Clamp((1.0 - EDr[s]) / P.EPerUnit[k][2], 0.0, P.EatRate[k][2]) * LastEMult[s];
                WantC[s] = Ea.C;
                const size_t c = static_cast<size_t>(Ea.C);
                CDemand[c] = CDemand[c] + WantM[s];
                CHas[c] = 1;
            }
            for (size_t c = 0; c < M; ++c)
            {
                if (!CHas[c]) { continue; }
                const double Dm = CDemand[c];
                const double Taken = std::min(Dm, St.CarcMeat[c]);
                CFrac[c] = Dm > 0 ? Taken / Dm : 0.0;
                St.CarcMeat[c] = St.CarcMeat[c] - Taken;
            }
            for (size_t s = 0; s < S; ++s)
            {
                if (WantC[s] < 0) { continue; }
                const size_t c = static_cast<size_t>(WantC[s]);
                const double Gu = WantM[s] * CFrac[c];
                const int k = St.Sp[s];
                LastGainU[s * 3u + 2u] = Gu;
                GainE[s] = GainE[s] + Gu * P.EPerUnit[k][2];
                Tot.EatenUnits[k][2] += Gu;
                Tot.EatenE[k][2] += Gu * P.EPerUnit[k][2];
                if (Gu > 0.0)
                {
                    Event Ev;
                    Ev.Kind = EvEat;
                    Ev.A = static_cast<int>(s);
                    Ev.B = static_cast<int>(c);
                    Ev.Code = FoodMeat;
                    Ev.X = St.Pos[s].x;
                    Ev.Y = St.Pos[s].y;
                    Ev.Value = Gu;
                    Ev.Value2 = Gu * P.EPerUnit[k][2];
                    Events.push_back(Ev);
                }
            }
            for (size_t c = 0; c < M; ++c)
            {
                if (St.CarcOk[c] && St.CarcMeat[c] <= 1e-12)
                {
                    St.CarcMeat[c] = 0.0;
                    St.CarcOk[c] = 0;
                    PushCarcGone(static_cast<int>(c));
                }
            }
        }
        // 대사에서 쓰도록 e_dr 를 남김
        EDrKeep.swap(EDr);
    }

    std::vector<double> EDrKeep;

    void PushCarcGone(int C)
    {
        Event Ev;
        Ev.Kind = EvCarcassGone;
        Ev.A = C;
        Ev.X = St.CarcPos[static_cast<size_t>(C)].x;
        Ev.Y = St.CarcPos[static_cast<size_t>(C)].y;
        Events.push_back(Ev);
    }

    void StepMetabolism()
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        for (size_t s = 0; s < S; ++s)
        {
            if (!St.Alive[s]) { continue; }
            const int k = St.Sp[s];
            const double Cc = P.ReserveCap[k];
            double e = std::min(EDrKeep[s] + GainE[s], 1.0);
            double R = St.R[s];
            if (e < 0.0)
            {
                const double Want = -e / Cc;
                if (Want <= R)
                {
                    e = 0.0;
                    R = R - Want;
                }
                else
                {
                    e = e + R * Cc;
                    R = 0.0;
                }
            }
            if (e >= P.RefillE[k] && R < 1.0 && GainE[s] > 0.0 && P.RefillFrac[k] > 0.0)
            {
                const double m = std::min(P.RefillFrac[k] * GainE[s], (1.0 - R) * Cc);
                e = e - m;
                R = std::min(R + m / Cc, 1.0);
            }
            St.E[s] = e;
            St.R[s] = R;
            if (LastGait[s] == GaitRun) { St.Stam[s] = std::max(St.Stam[s] - P.StamDrain[k], 0.0); }
            else { St.Stam[s] = std::min(St.Stam[s] + P.StamRecover[k], 1.0); }
            if (St.Stam[s] <= P.StaminaLock + 1e-9) { St.StamLock[s] = 1; }
            else if (St.Stam[s] >= P.StaminaUnlock - 1e-9) { St.StamLock[s] = 0; }
            if (P.HasHp[k]) { St.Hp[s] = std::min(St.Hp[s] + P.HpRegen[k], 1.0); }
        }
    }

    bool CanParent(size_t s) const
    {
        const int k = St.Sp[s];
        const double Hpv = P.HasHp[k] ? St.Hp[s] : 1.0;
        const bool Live = St.Alive[s] && St.Hp[s] > 0 && LastCause[s] == 0;
        const double Tf = static_cast<double>(St.T);
        return Live && Hpv >= P.BreedHpMin && (Tf - St.Born[s] >= P.Maturity[k]) && Tf >= St.NextBirth[s] && St.E[s] >= P.BreedEMin &&
               0.9 <= St.GSpeed[s] && St.GSpeed[s] <= 1.1 && 0.9 <= St.GSize[s] && St.GSize[s] <= 1.1 &&
               static_cast<double>(St.Generation[s]) < P.BreedGenerationCap;
    }

    void StepBreed()
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        const double Tf = static_cast<double>(St.T);
        std::vector<uint8_t> Elig(S), Live(S);
        for (size_t s = 0; s < S; ++s)
        {
            Elig[s] = CanParent(s) ? 1 : 0;
            Live[s] = (St.Alive[s] && St.Hp[s] > 0 && LastCause[s] == 0) ? 1 : 0;
        }
        std::vector<Pair> KeepPairs;
        for (const Pair& Pr : St.Pairs)
        {
            const size_t a = static_cast<size_t>(Pr.A), b = static_cast<size_t>(Pr.B);
            const int k = Pr.Sp;
            const bool UidOk = St.Uid[a] == Pr.UA && St.Uid[b] == Pr.UB;
            const bool KeepP = UidOk && Live[a] && Live[b] && ((!P.PendingNeedsParent[k]) || (Elig[a] && Elig[b]));
            const bool Due = KeepP && Tf >= Pr.Due;
            const double Grace = P.BirthGrace[k];
            const bool Waits = Grace > 0;
            const bool Bb = P.BirthBlock[k][St.Act[a]] || P.BirthBlock[k][St.Act[b]];
            const bool OkPar = Elig[a] && Elig[b] && !Bb;
            const double Dx = St.Pos[a].x - St.Pos[b].x, Dy = St.Pos[a].y - St.Pos[b].y;
            const bool CloseEnough = Dx * Dx + Dy * Dy <= P.BirthR[k] * P.BirthR[k];
            const bool Over = Due && Waits && Tf > Pr.Due + Grace;
            const bool Go = (Due && Waits && !Over && OkPar && CloseEnough) || (Due && !Waits && OkPar);
            const bool Cancel = (!KeepP) || Over || (Due && !Waits && !OkPar);
            if (Go)
            {
                St.NextBirth[a] = Tf + P.BreedRetry;
                St.NextBirth[b] = Tf + P.BreedRetry;
                if (CloseEnough)
                {
                    const size_t Two[2] = {a, b};
                    for (size_t q : Two)
                    {
                        St.E[q] = St.E[q] - P.BreedCost;
                        St.NextBirth[q] = Tf + P.BreedRecover;
                        St.Offspring[q] = St.Offspring[q] + 1;
                    }
                    Tot.BirthCredits[k] += 2;
                    Event Ev;
                    Ev.Kind = EvBirthCredit;
                    Ev.A = Pr.A;
                    Ev.B = Pr.B;
                    Ev.X = St.Pos[a].x;
                    Ev.Y = St.Pos[a].y;
                    Events.push_back(Ev);
                }
            }
            if (!(Go || Cancel)) { KeepPairs.push_back(Pr); }
        }
        St.Pairs.swap(KeepPairs);
        std::vector<uint8_t> MatingV(S, 0);
        for (const Pair& Pr : St.Pairs)
        {
            MatingV[static_cast<size_t>(Pr.A)] = 1;
            MatingV[static_cast<size_t>(Pr.B)] = 1;
        }
        const int64_t T = St.T;
        if (FloorDiv(P.BreedScanNum * T, P.BreedScanDen) != FloorDiv(P.BreedScanNum * T - P.BreedScanNum, P.BreedScanDen))
        {
            std::vector<uint8_t> Elig2(S);
            for (size_t s = 0; s < S; ++s) { Elig2[s] = CanParent(s) ? 1 : 0; }
            for (int k = 0; k < 3; ++k)
            {
                std::vector<int> Idx;
                for (int s = P.SpLo[k]; s < P.SpHi[k]; ++s)
                {
                    const size_t su = static_cast<size_t>(s);
                    if (Elig2[su] && !MatingV[su] && !P.PairBlock[k][St.Act[su]]) { Idx.push_back(s); }
                }
                if (Idx.size() < 2) { continue; }
                std::sort(Idx.begin(), Idx.end(), [this](int L, int Rr) { return St.Uid[static_cast<size_t>(L)] < St.Uid[static_cast<size_t>(Rr)]; });
                std::vector<uint8_t> Used(Idx.size(), 0);
                const double Mr2 = P.MateR[k] * P.MateR[k];
                for (size_t qi = 0; qi < Idx.size(); ++qi)
                {
                    if (Used[qi]) { continue; }
                    for (size_t qj = qi + 1; qj < Idx.size(); ++qj)
                    {
                        if (Used[qj]) { continue; }
                        const size_t a = static_cast<size_t>(Idx[qi]), b = static_cast<size_t>(Idx[qj]);
                        const int64_t Si = St.Sex[a], Sj = St.Sex[b];
                        const bool Comp = (Si == 0 && Sj == 0) || (Si != 0 && Sj != 0 && Si != Sj);
                        const double Dx = St.Pos[a].x - St.Pos[b].x, Dy = St.Pos[a].y - St.Pos[b].y;
                        if (Comp && Dx * Dx + Dy * Dy <= Mr2)
                        {
                            Used[qi] = 1;
                            Used[qj] = 1;
                            Pair Np;
                            Np.A = static_cast<int>(a);
                            Np.B = static_cast<int>(b);
                            Np.UA = St.Uid[a];
                            Np.UB = St.Uid[b];
                            Np.Due = Tf + P.BreedGestation;
                            Np.Sp = k;
                            St.Pairs.push_back(Np);
                            MatingV[a] = 1;
                            MatingV[b] = 1;
                            Event Ev;
                            Ev.Kind = EvPairStart;
                            Ev.A = Np.A;
                            Ev.B = Np.B;
                            Ev.X = St.Pos[a].x;
                            Ev.Y = St.Pos[a].y;
                            Events.push_back(Ev);
                            break;
                        }
                    }
                }
            }
        }
        St.Mating.swap(MatingV);
    }

    void StepDeaths()
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        for (size_t s = 0; s < S; ++s)
        {
            if (St.Alive[s] && St.E[s] <= 0.0 && St.R[s] <= 0.0) { Kill(s, CauseStarve); }
        }
        const size_t M = St.CarcOk.size();
        for (size_t s = 0; s < S; ++s)
        {
            if (!LastDead[s]) { continue; }
            const int k = St.Sp[s];
            Tot.Deaths[k][LastCause[s]] += 1;
            {
                Event Ev;
                Ev.Kind = EvDeath;
                Ev.A = static_cast<int>(s);
                Ev.B = k;
                Ev.Code = LastCause[s];
                Ev.X = St.Pos[s].x;
                Ev.Y = St.Pos[s].y;
                Ev.Value = St.Head[s].x;
                Ev.Value2 = St.Head[s].y;
                Events.push_back(Ev);
            }
            const double Meat = P.MassKg[k] * MassRatio(s) * P.CarcMeatFrac / P.CarcKgPerUnit;
            size_t C = M;
            for (size_t c = 0; c < M; ++c)
            {
                if (!St.CarcOk[c])
                {
                    C = c;
                    break;
                }
            }
            if (C == M)
            {
                C = 0;
                for (size_t c = 1; c < M; ++c)
                {
                    if (St.CarcMeat[c] < St.CarcMeat[C]) { C = c; }
                }
                PushCarcGone(static_cast<int>(C));
            }
            St.CarcOk[C] = 1;
            St.CarcPos[C] = St.Pos[s];
            St.CarcMeat[C] = Meat;
            St.CarcMeat0[C] = Meat;
            St.CarcT[C] = static_cast<double>(St.T);
            St.CarcKin[C] = St.KinId[s];
            Event Ev;
            Ev.Kind = EvCarcassAdd;
            Ev.A = static_cast<int>(C);
            Ev.B = static_cast<int>(s);
            Ev.Code = k;
            Ev.X = St.Pos[s].x;
            Ev.Y = St.Pos[s].y;
            Ev.Value = Meat;
            Ev.Value2 = std::atan2(St.Head[s].y, St.Head[s].x);
            Events.push_back(Ev);
        }
    }

    void StepRegrow()
    {
        const size_t GG = St.Grass.size();
        for (size_t c = 0; c < GG; ++c) { St.Grass[c] = St.Grass[c] + St.GrassRegen[c] * (St.GrassCap[c] - St.Grass[c]); }
        for (size_t c = 0; c < GG; ++c) { St.Root[c] = St.Root[c] + St.RootRegen[c] * (St.RootCap[c] - St.Root[c]); }
        for (size_t c = 0; c < St.CarcOk.size(); ++c)
        {
            if (!St.CarcOk[c]) { continue; }
            const double Dec = std::min(St.CarcMeat0[c] / P.CarcDecaySteps, St.CarcMeat[c]);
            St.CarcMeat[c] = St.CarcMeat[c] - Dec;
            if (St.CarcMeat[c] <= 1e-12)
            {
                St.CarcMeat[c] = 0.0;
                St.CarcOk[c] = 0;
                PushCarcGone(static_cast<int>(c));
            }
        }
    }

    void Respawn(size_t s, const RespawnDraw& Dr)
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        const int k = St.Sp[s];
        const int64_t Uid = St.NextUid;
        St.NextUid += 1;
        const bool Enter = P.ShelterEnter[k];
        bool HavePos = false, Newborn = false;
        Vec2d NewPos;
        if (Dr.UForm < P.RespawnNewbornFrac)
        {
            std::vector<int> Adults;
            for (int q = P.SpLo[k]; q < P.SpHi[k]; ++q)
            {
                if (St.Alive[static_cast<size_t>(q)] && Mature[static_cast<size_t>(q)]) { Adults.push_back(q); }
            }
            if (!Adults.empty())
            {
                const int NA = static_cast<int>(Adults.size());
                const size_t a = static_cast<size_t>(Adults[static_cast<size_t>(std::min(static_cast<int>(Dr.UPick * NA), NA - 1))]);
                for (int jj = 0; jj < 8; ++jj)
                {
                    const double Rr = P.RespawnRingR0 + P.RespawnRingDr * jj;
                    const double Qx = St.Pos[a].x + Rr * P.Golden8[jj][0];
                    const double Qy = St.Pos[a].y + Rr * P.Golden8[jj][1];
                    if (!(0.0 <= Qx && Qx <= P.Size && 0.0 <= Qy && Qy <= P.Size)) { continue; }
                    if (!Enter && !Outside(Qx, Qy, 0.0)) { continue; }
                    bool Crowded = false;
                    for (size_t q = 0; q < S; ++q)
                    {
                        if (!St.Alive[q]) { continue; }
                        const double Ox = St.Pos[q].x - Qx, Oy = St.Pos[q].y - Qy;
                        if (std::sqrt(Ox * Ox + Oy * Oy) < P.BreedClearR)
                        {
                            Crowded = true;
                            break;
                        }
                    }
                    if (Crowded) { continue; }
                    NewPos = Vec2d{Qx, Qy};
                    HavePos = true;
                    Newborn = true;
                    break;
                }
            }
        }
        if (!HavePos)
        {
            const double Margin = Enter ? 0.0 : P.ShelterPush;
            int BestOk = -1, BestI = 0;
            double BestV = -std::numeric_limits<double>::infinity();
            const int NC = P.RespawnCandidates;
            for (int ci = 0; ci < NC; ++ci)
            {
                const double Cx = Dr.Cand[static_cast<size_t>(2 * ci)], Cy = Dr.Cand[static_cast<size_t>(2 * ci + 1)];
                const bool Out = Outside(Cx, Cy, Margin);
                double DMin = 1e9;
                bool Any = false;
                for (size_t q = 0; q < S; ++q)
                {
                    if (!St.Alive[q] || St.Sp[q] == k) { continue; }
                    const double Ox = Cx - St.Pos[q].x, Oy = Cy - St.Pos[q].y;
                    const double Dq = std::sqrt(Ox * Ox + Oy * Oy);
                    if (!Any || Dq < DMin)
                    {
                        DMin = Dq;
                        Any = true;
                    }
                }
                if (Out && DMin >= P.RespawnFarR && BestOk < 0) { BestOk = ci; }
                const double V = Out ? DMin : DMin - 1e6;
                if (V > BestV)
                {
                    BestI = ci;
                    BestV = V;
                }
            }
            const int Ci = BestOk >= 0 ? BestOk : BestI;
            NewPos = Vec2d{Dr.Cand[static_cast<size_t>(2 * Ci)], Dr.Cand[static_cast<size_t>(2 * Ci + 1)]};
        }
        const uint64_t Sq = P.SeedQ[0];
        const uint64_t Uu = static_cast<uint64_t>(Uid);
        double Gsp, Gsz;
        if (P.FounderKind[k] == 1)
        {
            const double V = Clamp(P.FounderVariation[k], 0.0, 0.1);
            Gsp = 1 + 2 * V * (HashUnit(Sq ^ Uu) - 0.5);
            Gsz = 1 + 2 * V * (HashUnit(Sq + Uu + 17u) - 0.5);
        }
        else
        {
            Gsp = 0.95 + 0.1 * HashUnit(P.SeedW ^ Uu);
            Gsz = 0.95 + 0.1 * HashUnit(P.SeedW + Uu + 17u);
        }
        int64_t Sx = 0;
        if (P.SexMode[k] == 1) { Sx = HashUnit(Sq ^ HashMix(Uu + 911u)) < P.FemaleFrac[k] ? 1 : 2; }
        else if (P.SexMode[k] == 2) { Sx = HashUnit(P.SeedW ^ HashMix(Uu)) < P.ChildFemaleFrac[k] ? 1 : 2; }
        const double Tf = static_cast<double>(St.T);
        double BornV, E0, R0, Nbt;
        if (Newborn)
        {
            BornV = Tf;
            E0 = P.BreedChildE;
            R0 = P.BreedChildFat;
            Nbt = Tf;
        }
        else
        {
            const uint64_t Seed = k == 0 ? Sq : (Sq ^ HashMix(static_cast<uint64_t>(1000 + k)));
            const bool Young = HashUnit(Seed ^ HashMix(Uu + 1301u)) < P.JuvFrac[k];
            const double U = HashUnit(Seed + Uu * 31u);
            const double Mt = P.Maturity[k], Mx = P.MaxFounderAge[k];
            const double Age = Young ? Mt * (0.18 + 0.72 * U) : Mt + (Mx - Mt) * U;
            BornV = Tf - Age;
            E0 = P.StartEnergy;
            R0 = Dr.Fat;
            const double Spread = P.FirstBirthSpread[k];
            Nbt = Tf + P.FirstBirthBase[k] + Spread * (Spread > 0 ? HashUnit(Sq ^ Uu) : 0.0);
        }
        St.Alive[s] = 1;
        St.Uid[s] = Uid;
        St.Pos[s] = NewPos;
        const int Hi = std::min(std::max(Dr.HeadIdx, 0), 7);
        St.Head[s] = Vec2d{P.Dir8[Hi][0], P.Dir8[Hi][1]};
        St.Vel[s] = Vec2d{};
        St.Disp[s] = Vec2d{};
        St.DirCmd[s] = Vec2d{};
        St.KnockDir[s] = Vec2d{};
        St.E[s] = E0;
        St.R[s] = R0;
        St.Stam[s] = 1.0;
        St.Hp[s] = 1.0;
        St.StamLock[s] = 0;
        St.Born[s] = BornV;
        St.NextBirth[s] = Nbt;
        St.Sex[s] = Sx;
        St.GSpeed[s] = Gsp;
        St.GSize[s] = Gsz;
        St.ParentA[s] = 0;
        St.ParentB[s] = 0;
        St.Offspring[s] = 0;
        St.Generation[s] = 0;
        St.Mating[s] = 0;
        St.Act[s] = ActWatch;
        St.BiteCd[s] = 0;
        St.KnockLeft[s] = 0;
        St.RespT[s] = Tf;
        for (size_t q = 0; q < S; ++q)
        {
            St.Mem[s * S + q] = 0.0;
            St.Mem[q * S + s] = 0.0;
        }
        {
            std::vector<Pair> Kept;
            for (const Pair& Pr : St.Pairs)
            {
                if (Pr.A != static_cast<int>(s) && Pr.B != static_cast<int>(s)) { Kept.push_back(Pr); }
            }
            St.Pairs.swap(Kept);
            std::fill(St.Mating.begin(), St.Mating.end(), static_cast<uint8_t>(0));
            for (const Pair& Pr : St.Pairs)
            {
                St.Mating[static_cast<size_t>(Pr.A)] = 1;
                St.Mating[static_cast<size_t>(Pr.B)] = 1;
            }
        }
        Tot.Respawns[k] += 1;
        Event Ev;
        Ev.Kind = EvRespawn;
        Ev.A = static_cast<int>(s);
        Ev.Code = Newborn ? 1 : 0;
        Ev.X = NewPos.x;
        Ev.Y = NewPos.y;
        Events.push_back(Ev);
    }

    void PerceiveMem()
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        std::vector<double> Hr(S, 0.0);
        for (size_t j = 0; j < S; ++j)
        {
            if (!St.Alive[j]) { continue; }
            const double Sp = std::sqrt(St.Disp[j].x * St.Disp[j].x + St.Disp[j].y * St.Disp[j].y);
            Hr[j] = HearR(Sp);
        }
        for (size_t i = 0; i < S; ++i)
        {
            if (!St.Alive[i]) { continue; }
            const int k = St.Sp[i];
            const double See = P.SeeR[k] * (St.Act[i] == ActEat ? P.HeadDown[k] : 1.0);
            const double Hx = St.Head[i].x, Hy = St.Head[i].y;
            for (size_t j = 0; j < S; ++j)
            {
                if (!St.Alive[j]) { continue; }
                double& Mv = St.Mem[i * S + j];
                if (j == i)
                {
                    Mv = P.MemDecay * Mv;
                    continue;
                }
                const double Dx = St.Pos[j].x - St.Pos[i].x, Dy = St.Pos[j].y - St.Pos[i].y;
                const double Dist = std::sqrt(Dx * Dx + Dy * Dy);
                const double Invd = 1.0 / std::max(Dist, kEps);
                const double CosA = (Dx * Hx + Dy * Hy) * Invd;
                const bool Perc = (Dist <= See && CosA >= P.FovCos[k]) || Dist <= Hr[j] || Dist <= P.SmellR[k];
                if (Perc)
                {
                    const double Appr = Clamp((-(St.Disp[j].x * Dx + St.Disp[j].y * Dy)) * Invd / P.NormVel, -1.0, 1.0);
                    Mv = P.MemKeep * Mv + P.MemGain * Appr;
                }
                else
                {
                    Mv = P.MemDecay * Mv;
                }
            }
        }
    }
};

} // namespace EcoR9

#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(pop)
#endif

// EcoR9Core.h — R9 데모 학습 세계(스냅숏 b3b8e668 + s_world 변형 S__N)를 엔진과 무관한 C++17 로 옮긴 것 (헤더 전용).
//
// 무엇: 세계 상태 · 한 스텝(이동 → 물기 → 먹기 → 대사 → [짝 맺기] → 죽음·사체 → 다시 자람 → 다시 남 → 감각 기억) ·
//       관측 115 칸 · 행동 19 개 실행 · MLP 추론(115 → 64 → 64 → 19, tanh, float32 가중치) · 두뇌 파일(.r9brain) 읽기 ·
//       장면/대조 덤프(R9DUMP 1) 읽기 · 화면용 사건 목록.
// 동물 세계 (2026-11-13): 장면 덤프에 fauna_on 이 있으면 저장소 파이썬 configs/v3_r9_fauna.yaml 세계 (6 종: + 물소·표범·여우,
//       R1 몸무게 상처 · P1 은신처 안 물기 · R2 들이받기(2b) · R3 무늬 · R6 사체 먹는 자리 · R7 종별 번식 쉼 — RL_R9_SPECIES_TRAITS.md 4 절,
//       r9_world.py `if self.body.fauna` 갈래). 없으면 S′ 줄 그대로 (세 종 장면은 예전과 비트 같음). 대조: scratchpad/r9/ue_demo/fauna/CORE_FAUNA.md.
// 몸 움직임 (2026-11-13, RL_R9_TURN_EFFORT_DESIGN.md 3-1·7-2): 장면 덤프에 motion_on 이 있으면 파이썬 body_common.motion 세계
//       (configs/v3_r9_fauna_motion.yaml — M1 회전 한계만. M2 motion_effort 는 사용자 결정 전이라 LoadParams 가 거부). 없으면 옛 줄 그대로.
//       장면에 종별 body_hash 가 있으면 CheckBrainBody 로 두뇌 머리글 body_hash 와 대조한다 (없으면 — 옛 scene.txt — 대조하지 않음).
// 근거: scratchpad/r9/ue_demo/SPEC_PORT.md 5·6·7 절, 견본 py/ref_step.py · py/ref_obs.py (줄 차례를 그대로 따름).
// 지킴: 표준 라이브러리만, 예외·RTTI 없음(언리얼 모듈에서도 컴파일), 실행 중 파이썬 없음, 새 손규칙 없음(학습 세계 그대로).
// 수치: 상태는 double, 관측은 double 로 셈 → [-1, 1] 자름 → float32. 합은 파이썬과 같은 차례로 더함(행렬곱·두 갈래 합 없음).
//       MSVC 에서는 이 헤더 안만 /fp:precise 로 묶는다(곱셈·덧셈 합치기·차례 바꾸기 금지 — 파이썬과 같은 값을 내려고).
#pragma once

#include <algorithm>
#include <chrono>
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
constexpr int kNumSpecies = 3;       // S′ 세 종 (사슴·늑대·멧돼지). 장면이 쓰는 종 수는 Params::NumSpecies (3 또는 6)
constexpr int kMaxSpecies = 6;       // 동물 세계 1 단계: + 물소·표범·여우 (파이썬 ALL_SPECIES 앞 6 — 쥐·까마귀는 3 단계라 없음)
constexpr int kNumFoods = 3;
constexpr double kEps = 1e-9;
constexpr double kTurnTie = 1e-12;   // 몸 움직임 M1: |외적| 이 이 안이면 정확히 뒤 명령 → uid 홀짝으로 돌 쪽 (파이썬 r9_world.TURN_TIE, 설계 7-4 ①)

enum ESpecies : int { SpDeer = 0, SpWolf = 1, SpBoar = 2, SpBuffalo = 3, SpLeopard = 4, SpFox = 5 };
enum EFood : int { FoodGrass = 0, FoodRoot = 1, FoodMeat = 2 };
enum EAction : int { ActEat = 0, ActWalk0 = 1, ActRun0 = 9, ActShelter = 17, ActWatch = 18 };
enum ECause : int { CauseNone = 0, CauseBite = 1, CauseCounter = 2, CauseStarve = 3 };   // 동물 R2 들이받기 죽음 = CauseCounter (앞 무기 상처)
enum EBiteOutcome : int { BiteKill = 0, BiteWound = 1, BiteCounter = 2 };
enum EGoreOutcome : int { GoreWound = 0, GoreKill = 1 };
enum EGait : int { GaitStand = 0, GaitWalk = 1, GaitRun = 2 };

// 종 이름 = 파이썬 ALL_SPECIES 차례 (두뇌 파일 <이름>.r9brain · 덤프 종 번호)
inline const char* SpeciesName(int Sp)
{
    static const char* const Names[kMaxSpecies] = {"deer", "wolf", "boar", "buffalo", "leopard", "fox"};
    return (Sp >= 0 && Sp < kMaxSpecies) ? Names[Sp] : "?";
}

// 이름 → 종 번호 (없으면 -1)
inline int SpeciesIndex(const char* Name)
{
    for (int k = 0; k < kMaxSpecies; ++k)
    {
        if (Name && std::strcmp(Name, SpeciesName(k)) == 0) { return k; }
    }
    return -1;
}

// 동물 R1 AGE23[i] = (0.12 + 0.88 i / 64)^(2/3), i = 0..64 — r9_life.AGE23 와 비트 같은 리터럴 표 (스텝 안 초월함수 없음).
// 장면 덤프의 fauna_age23 가 있으면 LoadParams 가 이 표와 비트로 맞춰 본다.
constexpr int kAgeSteps = 64;
inline const double* Age23Table()
{
    static const double T[kAgeSteps + 1] = {
        // r9_life.AGE23 (repr — 되읽으면 비트 같음)
        0.24328807982293602, 0.26153462489381174, 0.2791652434273126, 0.29625554120917763, 0.3128662372837987,
        0.32904702875048814, 0.3448392445770989, 0.36027772422164656, 0.3753921822977319, 0.39020822214313605,
        0.40474810328071, 0.4190313324446481, 0.4330751255952941, 0.4468947739306174, 0.46050393733004835,
        0.47391488216834066, 0.48713867593828164, 0.5001853479504513, 0.5130640231073832, 0.5257830340989972,
        0.5383500161503573, 0.5507719875460606, 0.5630554184715868, 0.5752062901905356, 0.5872301461753295,
        0.5991321364971819, 0.6109170565368951, 0.6225893808851991, 0.6341532931479239, 0.6456127122484134,
        0.6569713157204956, 0.6682325604049393, 0.6793997008967243, 0.690475806036628, 0.7014637736962304,
        0.7123663440686385, 0.723186111646582, 0.7339255360438897, 0.7445869517948185, 0.7551725772475343,
        0.7656845226526584, 0.7761247975347162, 0.7864953174231691, 0.7967979100101663, 0.8070343207939528,
        0.8172062182598147, 0.8273151986443402, 0.8373627903234936, 0.8473504578604057, 0.8572796057447937,
        0.8671515818524191, 0.8769676806499508, 0.8867291461679031, 0.8964371747619719, 0.906092917681004,
        0.9156974834580003, 0.9252519401389316, 0.9347573173626941, 0.9442146083042591, 0.9536247714919266,
        0.9629887325085715, 0.9723073855858682, 0.9815815950996584, 0.9908121969739031, 1.0,
    };
    return T;
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
    int NumSpecies = 3;               // 장면의 종 수 (덤프 sp_lo 길이): S′ 3 · 동물 세계 6. 종 번호 = 파이썬 ALL_SPECIES 차례
    int Counts[kMaxSpecies] = {};
    double Size = 60.0;
    double Cell = 2.0;
    int G = 30;
    int SpLo[kMaxSpecies] = {};
    int SpHi[kMaxSpecies] = {};
    int NumSlots = 0;
    int NumCarcass = 0;
    double RunMult[kMaxSpecies] = {1, 1, 1, 1, 1, 1};
    double JuvFrac[kMaxSpecies] = {};
    uint64_t SeedW = 0;
    uint64_t SeedQ[4] = {0, 0, 0, 0};
    std::vector<double> ShelX, ShelY, ShelR;
    // 몸 표 [종] (NumSpecies 칸까지 씀)
    double Size0[kMaxSpecies], WalkSpeed[kMaxSpecies], RunSpeed[kMaxSpecies], Accel[kMaxSpecies], StamDrain[kMaxSpecies],
        StamRecover[kMaxSpecies], SeeR[kMaxSpecies], FovCos[kMaxSpecies], HeadDown[kMaxSpecies], SmellR[kMaxSpecies], Drain[kMaxSpecies],
        ReserveCap[kMaxSpecies], RefillE[kMaxSpecies], RefillFrac[kMaxSpecies], WeakE[kMaxSpecies], WeakSpeed[kMaxSpecies],
        HpRegen[kMaxSpecies], BiteR[kMaxSpecies], Maturity[kMaxSpecies], MassKg[kMaxSpecies], FoodDensityRef[kMaxSpecies],
        FoodHereRef[kMaxSpecies], MaxFounderAge[kMaxSpecies], FounderVariation[kMaxSpecies], FirstBirthBase[kMaxSpecies],
        FirstBirthSpread[kMaxSpecies], FemaleFrac[kMaxSpecies], ChildFemaleFrac[kMaxSpecies], MateR[kMaxSpecies], BirthR[kMaxSpecies],
        BirthGrace[kMaxSpecies];
    bool HasHp[kMaxSpecies], ShelterEnter[kMaxSpecies], CounterOn[kMaxSpecies], GrowthSmooth[kMaxSpecies], PendingNeedsParent[kMaxSpecies];
    int FounderKind[kMaxSpecies], SexMode[kMaxSpecies];
    bool Eats[kMaxSpecies][3];
    double EatRate[kMaxSpecies][3], EPerUnit[kMaxSpecies][3];
    bool Bites[kMaxSpecies][kMaxSpecies];
    int DietRank[kMaxSpecies][3];
    bool PairBlock[kMaxSpecies][kNumActions], BirthBlock[kMaxSpecies][kNumActions];
    double GaitDrain[3];
    bool LifeOn = false;
    // 출산 뒤 다음 번식까지 (동물 R7 종별 recover). 덤프에 body_recover 가 없으면(옛 S′ 장면) 모두 const_breed_recover
    double Recover[kMaxSpecies];
    // ---- 동물 세계 (파이썬 body_common.fauna, RL_R9_SPECIES_TRAITS.md 4 절). 거짓이면 S′ 줄 그대로 (비트 같음) ----
    bool FaunaOn = false;
    double BiteK[kMaxSpecies] = {}, Hide[kMaxSpecies] = {}, StrikeK[kMaxSpecies] = {}, GoreR[kMaxSpecies] = {}, Camo[kMaxSpecies] = {};
    bool Gore[kMaxSpecies] = {};
    double C23[kMaxSpecies][kMaxSpecies] = {};   // (kg_a / kg_b)^(2/3) — 파이썬 load_body 가 셈한 값을 덤프에서 받음 (스텝 안 거듭제곱 없음)
    double FaunaGoreCone = 0.5, FaunaGoreAppr = 0.03;
    int FaunaGoreCd = 8;
    double FaunaCamoS0 = 0.18, FaunaCamoSpan = 0.42, FaunaCpPer = 3.0;
    int FaunaCpMin = 1, FaunaCpMax = 8;
    bool CamoOn = false;                         // FaunaOn 이고 어느 종이든 camo < 1 (파이썬 _camo_on)
    // ---- 몸 움직임 (파이썬 body_common.motion, RL_R9_TURN_EFFORT_DESIGN.md 3-1·7-2). MotionOn 거짓이면 옛 줄 그대로 (비트 같음) ----
    bool MotionOn = false;                       // 장면에 motion_on 1 (블록이 있음 — 통계 MoveSteps·WallHitSteps 를 셈)
    bool MotionTurn = false;                     // M1 회전 한계 (motion_turn)
    bool MotionEffort = false;                   // M2 속도를 바꾸는 힘 — 아직 구현하지 않음 (LoadParams 가 1 을 거부, 사용자 결정 11-13)
    // M1 종별 값: cos Δb · sin Δb (Δb = turn_dps × 2/15 초) · 옆 가속 lat_accel_mps2 / 112.5 (단위/스텝²) — 파이썬 load_body 가 불러올 때 한 번
    // 셈한 값을 덤프에서 받음 (스텝 안 삼각함수 없음, fauna_c23 과 같은 꼴)
    double TurnC[kMaxSpecies] = {}, TurnS[kMaxSpecies] = {}, LatU[kMaxSpecies] = {};
    // 종별 몸 해시 (덤프 body_hash — r9_body.body_hash, 설계 7-2). 있으면 CheckBrainBody 가 두뇌 머리글 body_hash 와 대조. 옛 장면은 줄이 없음 → 대조 안 함
    bool HasBodyHash = false;
    uint64_t BodyHash[kMaxSpecies] = {};
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

    // ---- 큰 세계 (EcoR9Scene.h BuildBigScene 이 채움). 파이썬 장면은 모두 비어 있고 BigWorld 거짓 → 지금과 비트 같음 ----
    std::vector<uint8_t> Blocked;     // G*G, 1 = 막힌 칸 (물·가파름·나무/바위/건물·땅 없음). 비면 막힌 칸 없음
    std::vector<uint8_t> Spawnable;   // G*G, 1 = 시작·다시 남 자리 (가장 큰 이어진 땅의 열린 칸). 비면 막히지 않은 모든 칸
    std::vector<int> SlotHerd;        // NumSlots, 칸 → 무리 자리 번호 (−1 = 없음). 비면 무리 없음 (다시 남 = 학습 세계 전체)
    std::vector<double> HerdX, HerdY; // 무리 자리 가운데 (단위)
    double HerdSide = 60.0;           // 무리 둘레 정사각 한 변 (다시 남 먼 꼴 후보 구역, 학습 세계 한 변)
    bool BigWorld = false;            // 참 = 먹이 밀도(관측 7)를 산 개체 칸에서만 직접 셈 (뜻 같음, 덧셈 차례가 달라 비트는 다름)
    // 장면 덤프에 있으면 읽는 세계 값 (세계 규칙은 쓰지 않음 — 큰 세계 생성기가 먹이 재생·친족 번호를 같게 만들 때 씀)
    double GrassRegenMult = 1.0, RootRegenMult = 1.0;
    int KinPerm[kMaxSpecies] = {0, 1, 2, 3, 4, 5};

    bool BitesAny(int Sp) const
    {
        for (int k = 0; k < NumSpecies; ++k)
        {
            if (Bites[Sp][k]) { return true; }
        }
        return false;
    }
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
    {
        // 종 수 = sp_lo 길이 (S′ 3 · 동물 세계 6). 몸 표 줄은 모두 이 길이로 읽는다.
        const DumpEntry* E = Blk.Find("sp_lo");
        const int Ns = E ? static_cast<int>(E->Count()) : 0;
        if (Ns < kNumSpecies || Ns > kMaxSpecies)
        {
            Detail::SetErr(Err, "sp_lo: species count must be 3..6");
            return false;
        }
        P.NumSpecies = Ns;
    }
    const size_t NS = static_cast<size_t>(P.NumSpecies);
    P.Seed = Gt.I("seed");
    Gt.I3("counts", P.Counts, NS);
    P.Size = Gt.D("world_size");
    P.Cell = Gt.D("cell");
    P.G = static_cast<int>(Gt.I("G"));
    Gt.I3("sp_lo", P.SpLo, NS);
    Gt.I3("sp_hi", P.SpHi, NS);
    P.NumSlots = P.SpHi[NS - 1];
    P.NumCarcass = static_cast<int>(Gt.I("carcass_slots"));
    Gt.D3("run_mult", P.RunMult, NS);
    Gt.D3("juv_frac", P.JuvFrac, NS);
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
    Gt.D3("body_size0", P.Size0, NS);
    Gt.D3("body_walk_speed", P.WalkSpeed, NS);
    Gt.D3("body_run_speed", P.RunSpeed, NS);
    Gt.D3("body_accel", P.Accel, NS);
    Gt.D3("body_stam_drain", P.StamDrain, NS);
    Gt.D3("body_stam_recover", P.StamRecover, NS);
    Gt.D3("body_see_r", P.SeeR, NS);
    Gt.D3("body_fov_cos", P.FovCos, NS);
    Gt.D3("body_head_down", P.HeadDown, NS);
    Gt.D3("body_smell_r", P.SmellR, NS);
    Gt.D3("body_drain", P.Drain, NS);
    Gt.D3("body_reserve_cap", P.ReserveCap, NS);
    Gt.D3("body_refill_e", P.RefillE, NS);
    Gt.D3("body_refill_frac", P.RefillFrac, NS);
    Gt.D3("body_weak_e", P.WeakE, NS);
    Gt.D3("body_weak_speed", P.WeakSpeed, NS);
    Gt.D3("body_hp_regen", P.HpRegen, NS);
    Gt.D3("body_bite_r", P.BiteR, NS);
    Gt.D3("body_maturity", P.Maturity, NS);
    Gt.D3("body_mass_kg", P.MassKg, NS);
    Gt.D3("body_food_density_ref", P.FoodDensityRef, NS);
    Gt.D3("body_food_here_ref", P.FoodHereRef, NS);
    Gt.D3("body_max_founder_age", P.MaxFounderAge, NS);
    Gt.D3("body_founder_variation", P.FounderVariation, NS);
    Gt.D3("body_first_birth_base", P.FirstBirthBase, NS);
    Gt.D3("body_first_birth_spread", P.FirstBirthSpread, NS);
    Gt.D3("body_female_frac", P.FemaleFrac, NS);
    Gt.D3("body_child_female_frac", P.ChildFemaleFrac, NS);
    Gt.D3("body_mate_r", P.MateR, NS);
    Gt.D3("body_birth_r", P.BirthR, NS);
    Gt.D3("body_birth_grace", P.BirthGrace, NS);
    Gt.B3("body_has_hp", P.HasHp, NS);
    Gt.B3("body_shelter_enter", P.ShelterEnter, NS);
    Gt.B3("body_counter", P.CounterOn, NS);
    Gt.B3("body_growth_smooth", P.GrowthSmooth, NS);
    Gt.B3("body_pending_needs_parent", P.PendingNeedsParent, NS);
    Gt.I3("body_founder_kind", P.FounderKind, NS);
    Gt.I3("body_sex_mode", P.SexMode, NS);
    {
        const int Ns = P.NumSpecies;
        bool Tmp[kMaxSpecies * kMaxSpecies];
        double TmpD[kMaxSpecies * kMaxSpecies];
        int TmpI[kMaxSpecies * 3];
        Gt.B3("body_eats", Tmp, NS * 3);
        for (int K = 0; K < Ns * 3; ++K) { P.Eats[K / 3][K % 3] = Tmp[K]; }
        Gt.D3("body_eat_rate", TmpD, NS * 3);
        for (int K = 0; K < Ns * 3; ++K) { P.EatRate[K / 3][K % 3] = TmpD[K]; }
        Gt.D3("body_e_per_unit", TmpD, NS * 3);
        for (int K = 0; K < Ns * 3; ++K) { P.EPerUnit[K / 3][K % 3] = TmpD[K]; }
        Gt.B3("body_bites", Tmp, NS * NS);
        for (int K = 0; K < Ns * Ns; ++K) { P.Bites[K / Ns][K % Ns] = Tmp[K]; }
        Gt.I3("diet_rank", TmpI, NS * 3);
        for (int K = 0; K < Ns * 3; ++K) { P.DietRank[K / 3][K % 3] = TmpI[K]; }
        bool Blk19[kMaxSpecies * kNumActions];
        Gt.B3("body_pair_block", Blk19, NS * kNumActions);
        for (int K = 0; K < Ns * kNumActions; ++K) { P.PairBlock[K / kNumActions][K % kNumActions] = Blk19[K]; }
        Gt.B3("body_birth_block", Blk19, NS * kNumActions);
        for (int K = 0; K < Ns * kNumActions; ++K) { P.BirthBlock[K / kNumActions][K % kNumActions] = Blk19[K]; }
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
    if (const DumpEntry* E = Blk.Find("const_grass_regen_mult")) { if (E->Count() == 1) { P.GrassRegenMult = E->AsDouble(0); } }
    if (const DumpEntry* E = Blk.Find("const_root_regen_mult")) { if (E->Count() == 1) { P.RootRegenMult = E->AsDouble(0); } }
    if (const DumpEntry* E = Blk.Find("kin_perm"))
    {
        if (E->Count() == NS) { for (size_t K = 0; K < NS; ++K) { P.KinPerm[K] = static_cast<int>(E->AsInt(K)); } }
    }
    // 동물 R7: 종별 출산 뒤 쉼 (옛 장면 = 모두 const_breed_recover)
    for (size_t K = 0; K < static_cast<size_t>(kMaxSpecies); ++K) { P.Recover[K] = P.BreedRecover; }
    if (const DumpEntry* E = Blk.Find("body_recover"))
    {
        if (E->Count() == NS) { for (size_t K = 0; K < NS; ++K) { P.Recover[K] = E->AsDouble(K); } }
    }
    // 동물 세계 (fauna_on 줄이 있을 때만 — 없으면 S′ 그대로). 종이 넷 이상인 장면은 동물 세계여야 한다 (파이썬 v3_r9_fauna.yaml)
    P.FaunaOn = false;
    P.CamoOn = false;
    if (const DumpEntry* E = Blk.Find("fauna_on"))
    {
        P.FaunaOn = E->Count() == 1 && E->AsInt(0) != 0;
    }
    if (P.NumSpecies > kNumSpecies && !P.FaunaOn)
    {
        Detail::SetErr(Err, "scene has more than three species but no fauna_on");
        return false;
    }
    if (P.FaunaOn)
    {
        Gt.D3("body_bite_k", P.BiteK, NS);
        Gt.D3("body_hide", P.Hide, NS);
        Gt.D3("body_strike_k", P.StrikeK, NS);
        Gt.D3("body_gore_r", P.GoreR, NS);
        Gt.D3("body_camo", P.Camo, NS);
        Gt.B3("body_gore", P.Gore, NS);
        double C[kMaxSpecies * kMaxSpecies];
        Gt.D3("fauna_c23", C, NS * NS);
        for (size_t K = 0; K < NS * NS; ++K) { P.C23[K / NS][K % NS] = C[K]; }
        P.FaunaGoreCone = Gt.D("const_fauna_gore_cone");
        P.FaunaGoreAppr = Gt.D("const_fauna_gore_appr");
        P.FaunaGoreCd = static_cast<int>(Gt.D("const_fauna_gore_cd"));
        P.FaunaCamoS0 = Gt.D("const_fauna_camo_s0");
        P.FaunaCamoSpan = Gt.D("const_fauna_camo_span");
        P.FaunaCpPer = Gt.D("const_fauna_cp_per");
        P.FaunaCpMin = static_cast<int>(Gt.D("const_fauna_cp_min"));
        P.FaunaCpMax = static_cast<int>(Gt.D("const_fauna_cp_max"));
        if (const DumpEntry* E = Gt.Need("fauna_age23", static_cast<size_t>(kAgeSteps + 1)))
        {
            const double* T = Age23Table();
            for (int K = 0; K <= kAgeSteps; ++K)
            {
                if (E->AsDouble(static_cast<size_t>(K)) != T[K])
                {
                    Detail::SetErr(Err, "fauna_age23 differs from the literal AGE23 table at " + std::to_string(K));
                    return false;
                }
            }
        }
        for (size_t K = 0; K < NS; ++K)
        {
            if (!(P.Hide[K] > 0.0))
            {
                Detail::SetErr(Err, "fauna: hide must be > 0");
                return false;
            }
            if (P.Camo[K] < 1.0) { P.CamoOn = true; }
        }
    }
    // 종별 몸 해시 (설계 7-2): body_hash 줄이 있을 때만 — 옛 scene.txt 에는 없다 (그때는 두뇌 몸 해시를 대조하지 않음)
    P.HasBodyHash = false;
    if (const DumpEntry* E = Blk.Find("body_hash"))
    {
        if (E->Kind != 'u' || E->Count() != NS)
        {
            Detail::SetErr(Err, "body_hash: need one u64 per species");
            return false;
        }
        for (size_t K = 0; K < NS; ++K) { P.BodyHash[K] = E->U[K]; }
        P.HasBodyHash = true;
    }
    // 몸 움직임 (설계 7-2): motion_on 줄이 있을 때만 — 없으면 꺼짐이라 옛 scene.txt 도 그대로 읽힌다
    P.MotionOn = false;
    P.MotionTurn = false;
    P.MotionEffort = false;
    if (const DumpEntry* E = Blk.Find("motion_on"))
    {
        P.MotionOn = E->Count() == 1 && E->AsInt(0) != 0;
    }
    if (P.MotionOn)
    {
        P.MotionTurn = Gt.I("motion_turn") != 0;
        P.MotionEffort = Gt.I("motion_effort") != 0;
        if (P.MotionEffort)
        {
            // 사용자 결정 (2026-11-13 11:55): 첫 바퀴는 M1 만. 파이썬 _check_motion 도 effort: true 를 거부한다
            Detail::SetErr(Err, "motion_effort: M2 (speed-change effort) is not implemented yet (user decision pending); first round is M1 only");
            return false;
        }
        if (!P.HasBodyHash)
        {
            // 움직임 세계의 두뇌는 늘 몸 해시로 대조한다 (회전 한계 없는 몸에서 배운 두뇌를 막음). dump_fauna.py 는 늘 body_hash 를 싣는다
            Detail::SetErr(Err, "motion scene without body_hash");
            return false;
        }
        if (P.MotionTurn)
        {
            Gt.D3("body_turn_c", P.TurnC, NS);
            Gt.D3("body_turn_s", P.TurnS, NS);
            Gt.D3("body_lat_u", P.LatU, NS);
            for (size_t K = 0; K < NS && Gt.Ok; ++K)
            {
                // 0 < Δb < 45° (cos > sin > 0 — DIR8 각과 겹치지 않음, 파이썬 6-1 검사) · cos² + sin² = 1 · 옆 가속 > 0
                const double C = P.TurnC[K], S = P.TurnS[K];
                if (!(S > 0.0 && C > S && std::fabs(C * C + S * S - 1.0) <= 1e-12 && P.LatU[K] > 0.0))
                {
                    Detail::SetErr(Err, "motion: bad body_turn_c / body_turn_s / body_lat_u");
                    return false;
                }
            }
        }
    }
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
    if (Gt.Ok && (P.NumSlots <= 0 || P.G <= 0 || P.NumCarcass <= 0 || P.RespawnCandidates <= 0 || P.BreedScanDen <= 0 ||
                  (P.FaunaOn && !(P.FaunaCamoSpan > 0.0))))
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
    int Slot = 0;     // 파이썬 LifeState 짝 칸 번호 p. St.Pairs 는 이 차례 — 새 짝은 비어 있는 가장 낮은 칸 (r9_life._scan 의 free[nf])
};

struct State
{
    int64_t T = 0;
    std::vector<int> Sp;
    std::vector<Vec2d> Pos, Head, Vel, Disp, DirCmd, KnockDir;
    std::vector<double> E, R, Stam, Hp, Born, NextBirth, GSpeed, GSize, RespT;
    std::vector<int64_t> KinId, Uid, Sex, Generation, ParentA, ParentB, Offspring;
    std::vector<int> Act, BiteCd, KnockLeft;
    std::vector<int> GoreCd;          // 동물 R2 들이받기 쉼 (덤프에 gore_cd 가 없으면 0)
    std::vector<uint8_t> Alive, StamLock, Mating;
    std::vector<double> Mem;   // [i * S + j]
    std::vector<double> Grass, GrassCap, GrassRegen, Root, RootCap, RootRegen;   // [iy * G + ix]
    std::vector<uint8_t> CoverCell;
    std::vector<uint8_t> CarcOk;
    std::vector<Vec2d> CarcPos;
    std::vector<double> CarcMeat, CarcMeat0, CarcT;
    std::vector<int64_t> CarcKin;
    std::vector<int> CarcPlaces;      // 동물 R6 사체마다 먹는 자리 (덤프에 carc_places 가 없으면 const_carc_places — S′ 는 읽지 않음)
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
    // 동물 세계 줄 (있을 때만 — 옛 S′ 덤프에는 없음)
    St.GoreCd.assign(S, 0);
    if (const DumpEntry* E = Blk.Find("gore_cd"))
    {
        if (E->Count() == S) { for (size_t K = 0; K < S; ++K) { St.GoreCd[K] = static_cast<int>(E->AsInt(K)); } }
    }
    St.CarcPlaces.assign(M, P.CarcPlaces);
    if (const DumpEntry* E = Blk.Find("carc_places"))
    {
        if (E->Count() == M) { for (size_t K = 0; K < M; ++K) { St.CarcPlaces[K] = static_cast<int>(E->AsInt(K)); } }
    }
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
            Pr.Slot = static_cast<int>(K);
            St.Pairs.push_back(Pr);
        }
        // 짝 칸 번호 (덤프에 pair_slot 이 있으면 — 없으면 줄 차례 0, 1, …)
        if (const DumpEntry* Ps = Blk.Find("pair_slot"))
        {
            if (Ps->Count() == St.Pairs.size())
            {
                for (size_t K = 0; K < N; ++K) { St.Pairs[K].Slot = static_cast<int>(Ps->AsInt(K)); }
            }
        }
    }
    if (Gt.Ok)
    {
        for (size_t K = 0; K < S; ++K)
        {
            if (St.Sp[K] < 0 || St.Sp[K] >= P.NumSpecies || St.Act[K] < 0 || St.Act[K] >= kNumActions)
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
    // 동물 R2: 들이받는 칸 순서 (파이썬 rng_gore). 들이받는 몸이 있는 장면만 스텝마다 부른다 (S′ 장면은 부르지 않음 — 난수 흐름 그대로)
    virtual void GorePermutation(int N, int* Out) = 0;
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

    void GorePermutation(int N, int* Out) override { BitePermutation(N, Out); }

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
    std::vector<int> GorePerm;
    std::vector<RespawnDraw> Draws;
    size_t NextDraw = 0;
    bool Underflow = false;
    bool GoreUsed = false;

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

    void GorePermutation(int N, int* Out) override
    {
        GoreUsed = true;
        for (int K = 0; K < N; ++K)
        {
            if (static_cast<size_t>(K) < GorePerm.size()) { Out[K] = GorePerm[static_cast<size_t>(K)]; }
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

// u64 → 파이썬 r9_body.hash_hex 꼴 "0x" + 소문자 16 자리 (두뇌 머리글 body_hash 와 같은 글)
inline std::string BodyHashHex(uint64_t H)
{
    static const char Digits[] = "0123456789abcdef";
    std::string Out = "0x";
    for (int Sh = 60; Sh >= 0; Sh -= 4) { Out.push_back(Digits[(H >> Sh) & 15u]); }
    return Out;
}

// 두뇌 몸 해시 대조 (RL_R9_TURN_EFFORT_DESIGN.md 7-2 — 파이썬 r9_brains.load_brain 의 body_hash 검사, swap_brain.py 와 같은 뜻). LoadBrain 뒤에 종마다 부른다.
// 장면에 body_hash 줄이 있을 때만 본다: 옛 scene.txt (줄 없음) 와 그 두뇌는 그대로 받는다. 다르면 다른 몸(예: 회전 한계가 없던 몸)에서 배운 두뇌라
// 거부한다 — 파이썬 rebody_r9.py 로 그 몸에 옮긴 npz 를 내보내야 한다. 움직임 장면은 body_hash 가 꼭 있다 (LoadParams).
inline bool CheckBrainBody(const Params& P, int Sp, const Brain& Bn, std::string* Err)
{
    if (!P.HasBodyHash) { return true; }
    if (Sp < 0 || Sp >= P.NumSpecies)
    {
        Detail::SetErr(Err, "brain body check: species out of range");
        return false;
    }
    const std::string Want = BodyHashHex(P.BodyHash[Sp]);
    if (Bn.BodyHash != Want)
    {
        Detail::SetErr(Err, std::string("brain ") + SpeciesName(Sp) + ": body_hash " + (Bn.BodyHash.empty() ? std::string("(none)") : Bn.BodyHash) +
                                " != scene body " + Want + (P.MotionOn ? " (motion scene)" : "") + ": trained on another body (rebody it first)");
        return false;
    }
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
    EvBite = 1,          // A 문 칸(늑대·표범·여우), B 물린 칸, Code EBiteOutcome, X/Y 물린 자리. 동물 세계: Value 깎인 HP(상처 = 물린 몸 · 반격 = 문 몸),
                         //   Value2 1 = 물린 몸이 은신처 안 (P1: 들어갈 수 있는 몸만 안을 묾)
    EvDeath = 2,         // A 칸, Code ECause, X/Y 자리, Value 머리 x, Value2 머리 y, B 종
    EvCarcassAdd = 3,    // A 사체 번호, B 죽은 칸, Code 죽은 종, X/Y, Value 고기
    EvCarcassGone = 4,   // A 사체 번호 (다 먹힘·썩음·덮어씀)
    EvEat = 5,           // A 칸, Code EFood, Value 먹은 양(먹이 단위), Value2 얻은 E, B 격자 셀(iy*G+ix) 또는 사체 번호
    EvRespawn = 6,       // A 칸, Code 1 갓난 꼴 · 0 먼 꼴, X/Y
    EvPairStart = 7,     // A, B 칸 (짝 맺기 켬)
    EvBirthCredit = 8,   // A, B 칸 (출산 몫, 새 몸은 생기지 않음)
    EvGore = 9,          // 동물 R2: A 들이받은 칸(물소), B 받힌 칸, Code EGoreOutcome, X/Y 받힌 자리, Value 깎인 HP, Value2 다가간 속력
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
    double EatenUnits[kMaxSpecies][3] = {};   // [먹은 종][풀·땅속·고기]
    double EatenE[kMaxSpecies][3] = {};
    int64_t BitesOut[kMaxSpecies][3] = {};    // [물린 종][죽임·상처·반격]
    int64_t Deaths[kMaxSpecies][4] = {};      // [종][없음·물림·반격(들이받기 포함)·굶음]
    int64_t Respawns[kMaxSpecies] = {};
    int64_t Actions[kMaxSpecies][kNumActions] = {};
    double ESum[kMaxSpecies] = {};
    int64_t ENum[kMaxSpecies] = {};
    int64_t BirthCredits[kMaxSpecies] = {};
    // 동물 세계만 (파이썬 st bite_pairs·bite_in_shelter·gore·gore_hp·strike_hp_by 와 같은 뜻)
    int64_t BitePairs[kMaxSpecies][kMaxSpecies][3] = {};   // [문 종][물린 종][죽임·상처·반격]
    int64_t BiteInShelter[kMaxSpecies][kMaxSpecies] = {};  // [문 종][물린 종] 은신처 안 물기
    int64_t Gores[kMaxSpecies][kMaxSpecies][2] = {};       // [들이받은 종][받힌 종][상처·죽임]
    double GoreHp[kMaxSpecies][kMaxSpecies] = {};          // [들이받은 종][받힌 종] 깎인 HP 합
    double StrikeHpBy[kMaxSpecies] = {};                   // 반격·들이받기로 깎인 HP 합 (깎인 몸의 종)
    // 몸 움직임만 (파이썬 st move_steps·wall_hit_steps·turn_clip·turn_over — TURN_EFFORT 7-1·8-3. motion_on 장면에서만 셈, 세계는 바꾸지 않음)
    int64_t MoveSteps[kMaxSpecies] = {};      // 제 속도(accel 자른 뒤·벽 앞)가 EPS 보다 큰 산 몸-스텝
    int64_t WallHitSteps[kMaxSpecies] = {};   // 그 가운데 벽·막힌 칸에 닿은 스텝 (벽 미끄러짐 — M1 의 유일한 예외, 3-4)
    int64_t TurnClip[kMaxSpecies] = {};       // 회전 한계가 방향을 자른 WALK/RUN 스텝 (motion_turn)
    int64_t TurnOver[kMaxSpecies] = {};       // 벽 아닌 스텝에서 머리가 θ 넘게 돈 산 몸 (motion_turn — 0 이어야 함)
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
    // 몸 움직임 (TURN_EFFORT 3-1·3-4): 이 스텝 제 이동이 벽·막힌 칸에 닿아 미끄러졌나 (늘 셈) · 회전 한계가 방향을 잘랐나 ·
    // 그 몸의 cos θ (motion_turn 일 때 산 몸마다 — 파이썬 _turn_limit 의 cl. 아니면 −2)
    std::vector<uint8_t> LastWall, LastTurnClip;
    std::vector<double> LastTurnCl;

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
        {
            const size_t GG = static_cast<size_t>(P.G) * static_cast<size_t>(P.G);
            if ((!P.Blocked.empty() && P.Blocked.size() != GG) || (!P.Spawnable.empty() && P.Spawnable.size() != GG) ||
                St.Grass.size() != GG || St.Root.size() != GG || St.GrassCap.size() != GG || St.RootCap.size() != GG)
            {
                Detail::SetErr(Err, "grid size mismatch");
                return false;
            }
            if (!P.SlotHerd.empty())
            {
                if (P.SlotHerd.size() != S || P.HerdX.size() != P.HerdY.size() || !(P.HerdSide > 0.0))
                {
                    Detail::SetErr(Err, "herd table mismatch");
                    return false;
                }
                for (int H : P.SlotHerd)
                {
                    if (H >= static_cast<int>(P.HerdX.size()))
                    {
                        Detail::SetErr(Err, "bad herd index");
                        return false;
                    }
                }
            }
        }
        if (St.GoreCd.size() != S) { St.GoreCd.assign(S, 0); }
        if (St.CarcPlaces.size() != St.CarcOk.size()) { St.CarcPlaces.assign(St.CarcOk.size(), P.CarcPlaces); }
        BiterSlots.clear();
        GorerSlots.clear();
        Events.clear();
        for (int Sp = 0; Sp < P.NumSpecies; ++Sp)
        {
            if (P.BitesAny(Sp))
            {
                for (int K = P.SpLo[Sp]; K < P.SpHi[Sp]; ++K) { BiterSlots.push_back(K); }
            }
            // 동물 R2: 들이받는 몸 (파이썬 _gorers — S′ 에는 없음)
            if (P.FaunaOn && P.Gore[Sp])
            {
                for (int K = P.SpLo[Sp]; K < P.SpHi[Sp]; ++K) { GorerSlots.push_back(K); }
            }
        }
        // 물기 순서는 '물 수 있는 종의 칸' 차례 (ref_step biters) — 칸 차례로 다시 모음
        std::sort(BiterSlots.begin(), BiterSlots.end());
        std::sort(GorerSlots.begin(), GorerSlots.end());
        Resize();
        Tot = Stats{};
        LastCost = CostStats{};
        // 감각이 닿는 가장 먼 거리 (눈·코·소리) → 이웃 찾기 칸 격자 한 변 (+1 여유: 칸 경계에서 반올림 차가 나도 이웃을 놓치지 않게)
        SenseR = std::max(P.HearRQuiet, P.HearRLoud);
        // 눈 = SeeR × (먹는 중이면 HeadDown). 지금 장면은 HeadDown 0.6 (≤ 1) 이라 값이 같지만, 1 넘는 장면에서도 이웃을 놓치지 않게 (검토 11-13)
        for (int k = 0; k < P.NumSpecies; ++k) { SenseR = std::max(SenseR, std::max(P.SeeR[k] * std::max(1.0, P.HeadDown[k]), P.SmellR[k])); }
        HashB = std::max(1.0, SenseR + 1.0);
        HashN = std::max(1, static_cast<int>(std::ceil(P.Size / HashB)) + 1);
        BuildShelterIndex();
        ResetGrowLists();
        return true;
    }

    int NumSlots() const { return P.NumSlots; }

    // ---- 큰 세계 도움 함수 ----
    // 막힌 칸 위인가 (막힌 칸이 없으면 늘 거짓). 격자 밖 좌표는 가장자리 칸으로 본다 (CellOf 와 같음).
    bool IsBlockedAt(double X, double Y) const
    {
        if (P.Blocked.empty()) { return false; }
        int Ix = 0, Iy = 0;
        CellOf(X, Y, Ix, Iy);
        return P.Blocked[static_cast<size_t>(Iy) * static_cast<size_t>(P.G) + static_cast<size_t>(Ix)] != 0;
    }

    // 시작·다시 남 자리로 쓸 수 있나 (Spawnable 이 있으면 그것, 없으면 막히지 않은 칸)
    bool SpawnOkAt(double X, double Y) const
    {
        if (P.Spawnable.empty()) { return !IsBlockedAt(X, Y); }
        int Ix = 0, Iy = 0;
        CellOf(X, Y, Ix, Iy);
        return P.Spawnable[static_cast<size_t>(Iy) * static_cast<size_t>(P.G) + static_cast<size_t>(Ix)] != 0;
    }

    int HerdOf(int Slot) const
    {
        return (Slot >= 0 && static_cast<size_t>(Slot) < P.SlotHerd.size()) ? P.SlotHerd[static_cast<size_t>(Slot)] : -1;
    }

    // 다시 자람이 도는 칸 목록을 다시 만든다 (용량 0 칸은 값도 0 이라 건너뛰어도 비트 같다). 바깥에서 GrassCap·RootCap 을 바꿨으면 부른다.
    void ResetGrowLists()
    {
        GrowGrass.clear();
        GrowRoot.clear();
        for (size_t c = 0; c < St.GrassCap.size(); ++c)
        {
            if (St.GrassCap[c] != 0.0 || St.Grass[c] != 0.0) { GrowGrass.push_back(static_cast<int>(c)); }
            if (St.RootCap[c] != 0.0 || St.Root[c] != 0.0) { GrowRoot.push_back(static_cast<int>(c)); }
        }
        GrowFor = St.GrassCap.size();
    }

    // 마지막 Tick 의 계산 비용 (결정 스텝만 관측·두뇌가 0 이 아님)
    struct CostStats
    {
        double ObsMs = 0.0, BrainMs = 0.0, StepMs = 0.0;
        int64_t PairChecks = 0;    // 감각 이웃 후보 짝 (관측 + 기억)
        int64_t BrainCalls = 0;
        int64_t RegrowCells = 0;
        bool Decision = false;
    };
    CostStats LastCost;

    // 은신처가 이보다 많으면 칸 색인을 쓴다 (Init 전에 바꾸면 적용 — 시험에서 전수 비교용). 결과는 같다.
    size_t ShelterIndexMin = 32;

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
        using Clock = std::chrono::steady_clock;
        CostStats Cost;
        PairCount = 0;
        if ((St.T % 2) == 0)
        {
            const Clock::time_point T0 = Clock::now();
            BuildObs(ObsScratch);
            const Clock::time_point T1 = Clock::now();
            std::vector<int> Acts(static_cast<size_t>(P.NumSlots), ActWatch);
            ChooseActions(ObsScratch.data(), Brains, &Rng, bStochastic, Acts.data());
            Decide(Acts.data());
            const Clock::time_point T2 = Clock::now();
            Cost.Decision = true;
            Cost.ObsMs = std::chrono::duration<double, std::milli>(T1 - T0).count();
            Cost.BrainMs = std::chrono::duration<double, std::milli>(T2 - T1).count();
            for (size_t s = 0; s < St.Alive.size(); ++s)
            {
                if (St.Alive[s] && Brains[St.Sp[s]] && Brains[St.Sp[s]]->Valid()) { Cost.BrainCalls += 1; }
            }
        }
        const Clock::time_point T3 = Clock::now();
        Step(Rng);
        Cost.StepMs = std::chrono::duration<double, std::milli>(Clock::now() - T3).count();
        Cost.PairChecks = PairCount;
        Cost.RegrowCells = static_cast<int64_t>(GrowGrass.size() + GrowRoot.size());
        LastCost = Cost;
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
        std::fill(LastTurnClip.begin(), LastTurnClip.end(), static_cast<uint8_t>(0));
        std::fill(LastTurnCl.begin(), LastTurnCl.end(), -2.0);
        // 몸 움직임 (TURN_EFFORT 3-1): turn 이나 effort 가 켜진 세계만 서 있음 규칙 (블록만 있고 둘 다 꺼지면 옛 비트 — 파이썬 _motion_v0, M-13)
        const bool MotionV0 = P.MotionOn && (P.MotionTurn || P.MotionEffort);
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
            Vec2d V0 = St.Vel[s];
            if (MotionV0)
            {
                // 서 있음 = |v0|² ≤ EPS² → 0 (머리 갱신과 같은 판정, 7-4 ⑤). 회전 자르기·accel 자르기 모두 이 v0 를 쓴다 (파이썬 v0m)
                if (!(V0.x * V0.x + V0.y * V0.y > kEps * kEps)) { V0 = Vec2d{}; }
                if (P.MotionTurn) { LastTurnClip[s] = TurnLimit(s, k, a >= 1 && a <= 16, V0, Dx, Dy) ? 1 : 0; }
            }
            const double Tvx = Dx * Tsp, Tvy = Dy * Tsp;
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
        const bool Blk = !P.Blocked.empty();
        std::vector<int>& ShCand = ShScratch;
        for (size_t s = 0; s < S; ++s)
        {
            // 몸 움직임 통계 (파이썬 _motion_stats): 제 속도(accel 자른 뒤 · 벽 앞)가 움직이나
            const bool Moving = P.MotionOn && St.Alive[s] && V1[s].x * V1[s].x + V1[s].y * V1[s].y > kEps * kEps;
            const Vec2d H0 = St.Head[s];
            Vec2d P1;
            {
                // 벽과 막힌 칸 모두 축마다 따로 (x 먼저, 그다음 y) — 막히면 지금 칸 경계까지만 가고 다른 축은 그대로 미끄러진다
                const double Psx = P0[s].x + V1[s].x;
                P1.x = Clamp(Psx, 0.0, Sz);
                if (Blk) { P1.x = SlideX(P0[s].x, P0[s].y, P1.x); }
                if (P1.x != Psx) { V1[s].x = P1.x - P0[s].x; }
                const double Psy = P0[s].y + V1[s].y;
                P1.y = Clamp(Psy, 0.0, Sz);
                if (Blk) { P1.y = SlideY(P1.x, P0[s].y, P1.y); }
                if (P1.y != Psy) { V1[s].y = P1.y - P0[s].y; }
                LastWall[s] = (P1.x != Psx || P1.y != Psy) ? 1 : 0;   // 벽 미끄러짐 (파이썬 _wall.any) — M1 회전 한계의 유일한 예외 (3-4)
            }
            Vec2d P2 = P1;
            if (St.Alive[s] && St.KnockLeft[s] > 0)
            {
                P2 = Vec2d{Clamp(P1.x + St.KnockDir[s].x * P.CounterKnockStep, 0.0, Sz), Clamp(P1.y + St.KnockDir[s].y * P.CounterKnockStep, 0.0, Sz)};
                if (Blk) { P2 = SlideTo(P1, P2); }
                St.KnockLeft[s] -= 1;
            }
            if (AnyNe && St.Alive[s] && !P.ShelterEnter[St.Sp[s]])
            {
                ShelterCandidates(P2.x, P2.y, 2.0 * (ShMaxR + P.ShelterPush) + 1.0, ShCand);
                for (int Ci : ShCand)
                {
                    const size_t c = static_cast<size_t>(Ci);
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
                        const Vec2d Pushed{P.ShelX[c] + Ux * Rr, P.ShelY[c] + Uy * Rr};
                        P2 = Blk ? SlideTo(P2, Vec2d{Clamp(Pushed.x, 0.0, Sz), Clamp(Pushed.y, 0.0, Sz)}) : Pushed;
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
            if (P.MotionOn && St.Alive[s])
            {
                // 통계만 (세계는 바꾸지 않음): 움직인 스텝 · 그 가운데 벽 닿음 · 회전 한계가 자름 · 벽 아닌 스텝에서 θ 넘게 돎 (0 이어야 함)
                const int k = St.Sp[s];
                Tot.MoveSteps[k] += Moving ? 1 : 0;
                Tot.WallHitSteps[k] += (Moving && LastWall[s]) ? 1 : 0;
                if (P.MotionTurn)
                {
                    const double Hc = H0.x * St.Head[s].x + H0.y * St.Head[s].y;
                    Tot.TurnClip[k] += LastTurnClip[s];
                    Tot.TurnOver[k] += (!LastWall[s] && Hc < LastTurnCl[s] - 1e-12) ? 1 : 0;
                }
            }
        }
        for (size_t s = 0; s < S; ++s)
        {
            LastEdge1[s] = Edge(St.Pos[s].x, St.Pos[s].y);
            DrainStep[s] = P.Drain[St.Sp[s]] * P.GaitDrain[LastGait[s]] * Maint[s];
        }
        // 2 물기·반격 (5-3)
        StepBite(Rng);
        // 2b 들이받기 (동물 R2 — 들이받는 몸이 없는 장면은 난수도 뽑지 않음)
        if (!GorerSlots.empty()) { StepGore(Rng); }
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
        // (VisF: 동물 R3 — 아래 Spd 다음에 셈)
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
        std::vector<double> VisF;
        if (P.CamoOn) { CamoVis(Spd, VisF); }
        const int Br = std::max(1, static_cast<int>(std::nearbyint(P.NormFoodR / Cell)));
        std::vector<double> Fbg, Fbr;
        if (!P.BigWorld)
        {
            BoxMean(St.Grass, Br, G, Fbg);
            BoxMean(St.Root, Br, G, Fbr);
        }
        const bool Blk = !P.Blocked.empty();
        BuildHash();
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
            // 동물 R3: 보이는 거리 = See × VisF[j] (무늬 — 귀·코·사체 감각은 그대로)
            // 느낄 수 있는 개체는 칸 격자 이웃(SenseR 안)뿐. 아래에서 (거리, 칸) 차례로 정렬하므로 찾는 차례는 결과와 무관하다.
            int Bx = 0, By = 0;
            BucketOf(Px, Py, Bx, By);
            for (int Qy = std::max(By - 1, 0); Qy <= std::min(By + 1, HashN - 1); ++Qy)
            {
                for (int Qx = std::max(Bx - 1, 0); Qx <= std::min(Bx + 1, HashN - 1); ++Qx)
                {
                    for (int jj = HashHead[static_cast<size_t>(Qy) * static_cast<size_t>(HashN) + static_cast<size_t>(Qx)]; jj >= 0;
                         jj = HashNext[static_cast<size_t>(jj)])
                    {
                        const size_t j = static_cast<size_t>(jj);
                        if (j == i) { continue; }
                        PairCount += 1;
                        const double Dx = St.Pos[j].x - Px, Dy = St.Pos[j].y - Py;
                        const double Dist = std::sqrt(Dx * Dx + Dy * Dy);
                        const double Invd = 1.0 / std::max(Dist, kEps);
                        const double CosA = (Dx * Hx + Dy * Hy) * Invd;
                        const bool Vis = (P.CamoOn ? Dist <= See * VisF[j] : Dist <= See) && CosA >= Fov;
                        const bool Perc = Vis || Dist <= Hr[j] || Dist <= Smr;
                        if (!Perc) { continue; }
                        const double Appr = Clamp((-(St.Disp[j].x * Dx + St.Disp[j].y * Dy)) * Invd / P.NormVel, -1.0, 1.0);
                        Rows.push_back(Row{Dist, static_cast<int>(j), Dx, Dy, Invd, Vis, Appr});
                    }
                }
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
            double DensGrid;
            if (!P.BigWorld) { DensGrid = Wg * Fbg[CellI] + Wr * Fbr[CellI]; }
            else
            {
                const double Bg = Wg != 0.0 ? BoxAt(St.Grass, Ix, Iy, Br) : 0.0;
                const double Bro = Wr != 0.0 ? BoxAt(St.Root, Ix, Iy, Br) : 0.0;
                DensGrid = Wg * Bg + Wr * Bro;
            }
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
            const double EdgeV = NearestShelter(Px, Py, Best);
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
                double Tf8 = std::min(Tx, Ty);
                // 막힌 칸이 있으면 '벽 또는 첫 막힌 칸' 까지 (NormFree 넘으면 관측이 1 로 잘리므로 그 안만 찾는다)
                if (Blk) { Tf8 = std::min(Tf8, RayBlocked(Px, Py, Ux, Uy, P.NormFree)); }
                O[13 + j8] = Tf8 / P.NormFree;
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

    // 동물 R1: (M_a / M_b)^(2/3) = C23[종a][종b] × ((g_a·g_a) / (g_b·g_b)) × (AGE23[i_a] / AGE23[i_b]), i = floor(af × 64 + 0.5)
    // (파이썬 r9_world._p23 — 곱·나눗셈 차례 그대로). Af 는 이 스텝 Derive 값.
    double P23(size_t a, size_t b) const
    {
        const double* T = Age23Table();
        const double Ga = St.GSize[a], Gb = St.GSize[b];
        const int Ia = AgeIndex(Af[a]), Ib = AgeIndex(Af[b]);
        return P.C23[St.Sp[a]][St.Sp[b]] * ((Ga * Ga) / (Gb * Gb)) * (T[Ia] / T[Ib]);
    }

    static int AgeIndex(double A)
    {
        const int I = static_cast<int>(std::floor(A * static_cast<double>(kAgeSteps) + 0.5));
        return std::min(std::max(I, 0), kAgeSteps);
    }

private:
    std::vector<int> BiterSlots;
    std::vector<int> GorerSlots;
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
        LastWall.assign(S, 0);
        LastTurnClip.assign(S, 0);
        LastTurnCl.assign(S, -2.0);
        CellDemand.assign(GG, 0.0);
        CellTouched.assign(GG, 0);
        TouchedList.clear();
        Derive();
    }

    static Vec2d Rot(const Vec2d& H, double C, double Sn) { return Vec2d{H.x * C - H.y * Sn, H.x * Sn + H.y * C}; }

    // 몸 움직임 M1 회전 한계 (RL_R9_TURN_EFFORT_DESIGN.md 3-1 — 파이썬 r9_world._turn_limit 과 같은 셈·같은 괄호 차례, 곱·합·나눗셈·sqrt 만).
    // 한 스텝 머리 회전 ≤ θ = min(Δb, asin(a_lat / |v0|)): 빠르면 (s0 · sin Δb > a_u) 미끄럼 한계 sin θ = a_u / s0, 아니면 몸 한계 Δb.
    // V0 = 서 있음 규칙 뒤 지난 속도 (0 이거나 머리와 나란함). cos θ 는 산 몸마다 LastTurnCl 에 남긴다 (통계 TurnOver).
    // Cmd (WALK_j·RUN_j) 이고 한 스텝에 못 닿는 방향 (|D|² > EPS² 이고 D·H < cos θ) 이면 D 를 머리에서 θ 만큼 외적 쪽으로 돌린 방향으로 바꾸고 참.
    // 정확히 뒤 명령 (|외적| ≤ 1e-12) 은 uid 짝수 = 왼쪽 · 홀수 = 오른쪽 (몸마다 고정, 숨은 상태 없음 — 7-4 ①).
    bool TurnLimit(size_t s, int k, bool Cmd, const Vec2d& V0, double& Dx, double& Dy)
    {
        const Vec2d H = St.Head[s];
        const double S0 = std::sqrt(V0.x * V0.x + V0.y * V0.y);
        const double Au = P.LatU[k];
        double Sl = P.TurnS[k];
        double Cl = P.TurnC[k];
        if (S0 * P.TurnS[k] > Au)
        {
            Sl = Au / std::max(S0, Au);   // 파이썬 au / np.maximum(s0, au) — 고른 칸에서는 s0 > au 라 au / s0 와 같음 (7-4 ③)
            Cl = std::sqrt(1.0 - Sl * Sl);
        }
        LastTurnCl[s] = Cl;
        if (!Cmd || !(Dx * Dx + Dy * Dy > kEps * kEps) || !(Dx * H.x + Dy * H.y < Cl)) { return false; }
        const double X = H.x * Dy - H.y * Dx;
        const bool Left = X > kTurnTie || (std::fabs(X) <= kTurnTie && (St.Uid[s] & 1) == 0);
        const Vec2d R = Rot(H, Cl, Left ? Sl : -Sl);
        Dx = R.x;
        Dy = R.y;
        return true;
    }

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

    // 동물 R3: vis_j = camo_j + (1 − camo_j) × clip((s_j − s0) / span, 0, 1), s_j = 지난 스텝 변위 크기 (소리 곡선과 같은 '움직임 크기')
    void CamoVis(const std::vector<double>& Spd, std::vector<double>& Out) const
    {
        const size_t S = Spd.size();
        Out.assign(S, 1.0);
        for (size_t j = 0; j < S; ++j)
        {
            const double Cm = P.Camo[St.Sp[j]];
            Out[j] = Cm + (1.0 - Cm) * Clamp((Spd[j] - P.FaunaCamoS0) / P.FaunaCamoSpan, 0.0, 1.0);
        }
    }

    double HearR(double Spd) const
    {
        if (Spd < P.HearSilent) { return 0.0; }
        const double Tt = Clamp((Spd - P.HearQuiet) / P.HearSpan, 0.0, 1.0);
        return P.HearRQuiet + (P.HearRLoud - P.HearRQuiet) * Tt;
    }

    double Edge(double X, double Y) const
    {
        if (ShIndexed)
        {
            int Best = -1;
            return NearestShelter(X, Y, Best);
        }
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
        if (ShIndexed)
        {
            std::vector<int> Cand;
            ShelterCandidates(X, Y, ShMaxR + std::max(Margin, 0.0) + 1.0, Cand);
            for (int Ci : Cand)
            {
                const size_t c = static_cast<size_t>(Ci);
                const double Dx = X - P.ShelX[c], Dy = Y - P.ShelY[c];
                if (!(std::sqrt(Dx * Dx + Dy * Dy) > P.ShelR[c] + Margin)) { return false; }
            }
            return true;
        }
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
            // 동물 P1: 은신처에 들어갈 수 있는 몸은 안의 몸도 묾 (S′: 은신처 밖만)
            const bool InsideOk = P.FaunaOn && P.ShelterEnter[k];
            for (size_t j = 0; j < S; ++j)
            {
                if (!St.Alive[j] || !P.Bites[k][St.Sp[j]] || !((LastEdge1[j] > 0.0) || InsideOk)) { continue; }
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
        if (P.FaunaOn)
        {
            ResolveBiteFauna(w, j);
            return;
        }
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

    // 동물 R1 물기 (파이썬 _resolve_bite_fauna): 상처 = min(1, bite_k[문 몸] × P23(문, 물린) / hide[물린 몸]). 정면 반격(S′ 와 같은 조건)은
    // 문 몸에 strike_k[물린 몸] × P23(물린, 문) / hide[문 몸] — 밀림·물기 쉼·반격 자기 상처는 S′ 값. HP 없는 몸은 바로 죽음.
    void ResolveBiteFauna(size_t w, size_t j)
    {
        const int kj = St.Sp[j], kw = St.Sp[w];
        int Outcome = BiteWound;
        double Lost = 0.0;
        const bool Inside = !(LastEdge1[j] > 0.0);
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
                const double Dmg = P.StrikeK[kj] * P23(j, w) / P.Hide[kw];
                St.Hp[w] = std::max(0.0, St.Hp[w] - Dmg);
                Tot.StrikeHpBy[kw] += Dmg;
                St.KnockDir[w] = Tu;
                St.KnockLeft[w] = P.CounterKnockSteps;
                St.BiteCd[w] = P.CounterNobiteSteps;
                St.Hp[j] = std::max(0.0, St.Hp[j] - P.CounterSelfDamage);
                Outcome = BiteCounter;
                Lost = Dmg;
                if (St.Hp[w] <= 0.0) { Kill(w, CauseCounter); }
            }
            else
            {
                const double Loss = std::min(1.0, P.BiteK[kw] * P23(w, j) / P.Hide[kj]);
                St.Hp[j] = std::max(0.0, St.Hp[j] - Loss);
                St.BiteCd[w] = P.BiteCooldown;
                Lost = Loss;
                if (St.Hp[j] <= 0.0)
                {
                    Kill(j, CauseBite);
                    Outcome = BiteKill;
                }
            }
        }
        Tot.BitesOut[kj][Outcome] += 1;
        Tot.BitePairs[kw][kj][Outcome] += 1;
        if (Inside) { Tot.BiteInShelter[kw][kj] += 1; }
        Event Ev;
        Ev.Kind = EvBite;
        Ev.A = static_cast<int>(w);
        Ev.B = static_cast<int>(j);
        Ev.Code = Outcome;
        Ev.X = St.Pos[j].x;
        Ev.Y = St.Pos[j].y;
        Ev.Value = Lost;
        Ev.Value2 = Inside ? 1.0 : 0.0;
        Events.push_back(Ev);
    }

    // 동물 R2 들이받기 (파이썬 _gore, 물기 다음 2b). 순서 = 들이받는 칸의 순열(스텝마다 뽑음). 이번 스텝 걸음이 뛰기이고 살아 있고
    // gore_cd == 0 인 몸만. 목표 = 머리 앞 원뿔(cos >= cone) · gore_r × g_size × 자람 안 · 그쪽으로 자기 속도 성분 > approach_min 인
    // 다른 종의 산 몸 중 가장 가까운 것 (같으면 낮은 칸), 은신처 안 몸은 들이받는 몸이 들어갈 수 있을 때만 (P1). 어느 몸에 뛸지는 두뇌가 정함.
    void StepGore(IStepRandom& Rng)
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        const size_t NG = GorerSlots.size();
        std::vector<int> Perm(NG, 0);
        Rng.GorePermutation(static_cast<int>(NG), Perm.data());
        for (int g : GorerSlots)
        {
            const size_t gs = static_cast<size_t>(g);
            St.GoreCd[gs] = std::max(St.GoreCd[gs] - 1, 0);
        }
        struct GCand
        {
            double D;
            int J;
            double Vt;
        };
        std::vector<std::vector<GCand>> Can(NG);
        bool Any = false;
        for (size_t gi = 0; gi < NG; ++gi)
        {
            const size_t g = static_cast<size_t>(GorerSlots[gi]);
            if (!(St.Alive[g] && St.GoreCd[g] == 0 && LastGait[g] == GaitRun)) { continue; }
            const int k = St.Sp[g];
            const double Reach = P.GoreR[k] * BScale[g];
            const bool InsideOk = P.ShelterEnter[k];
            for (size_t j = 0; j < S; ++j)
            {
                if (!St.Alive[j] || St.Sp[j] == k || !((LastEdge1[j] > 0.0) || InsideOk)) { continue; }
                const double Dx = St.Pos[j].x - St.Pos[g].x, Dy = St.Pos[j].y - St.Pos[g].y;
                const double Dist = std::sqrt(Dx * Dx + Dy * Dy);
                const double Invd = 1.0 / std::max(Dist, kEps);
                const bool Cone = (Dx * St.Head[g].x + Dy * St.Head[g].y) * Invd >= P.FaunaGoreCone;
                const double Vt = (Dx * St.Vel[g].x + Dy * St.Vel[g].y) * Invd;
                if (Dist <= Reach && Cone && Vt > P.FaunaGoreAppr)
                {
                    Can[gi].push_back(GCand{Dist, static_cast<int>(j), Vt});
                    Any = true;
                }
            }
        }
        if (!Any) { return; }
        for (size_t q = 0; q < NG; ++q)
        {
            const int Gi = Perm[q];
            if (Gi < 0 || static_cast<size_t>(Gi) >= NG) { continue; }
            const size_t gi = static_cast<size_t>(Gi);
            const size_t g = static_cast<size_t>(GorerSlots[gi]);
            if (Can[gi].empty() || !St.Alive[g]) { continue; }
            const GCand* Best = nullptr;
            for (const GCand& C : Can[gi])
            {
                if (!St.Alive[static_cast<size_t>(C.J)]) { continue; }
                if (!Best || C.D < Best->D || (C.D == Best->D && C.J < Best->J)) { Best = &C; }
            }
            if (!Best) { continue; }
            ResolveGore(g, static_cast<size_t>(Best->J), Best->Vt);
        }
    }

    // 동물 R2 결과 (파이썬 _resolve_gore): 받힌 HP − strike_k[들이받은 몸] × P23(들이받은, 받힌) / hide[받힌 몸] × clip(vt / run_speed, 0, 1),
    // 받힌 몸 밀림(반격 밀림 값), 받힌 몸이 무는 몸이면 물기 쉼 max(bite_cd, nobite), 들이받은 몸은 반격 자기 상처 · gore_cd 쉼.
    // 죽음 = CauseCounter (앞 무기 상처). 들이받은 몸의 자기 상처로는 죽음을 보지 않는다 (파이썬 그대로).
    void ResolveGore(size_t g, size_t j, double Vt)
    {
        const int kg = St.Sp[g], kj = St.Sp[j];
        const double Share = std::min(std::max(Vt / P.RunSpeed[kg], 0.0), 1.0);
        int Outcome = GoreWound;
        double Dmg = 0.0;
        if (!P.HasHp[kj])
        {
            Dmg = 1.0;
            Kill(j, CauseCounter);
            Outcome = GoreKill;
        }
        else
        {
            Dmg = P.StrikeK[kg] * P23(g, j) / P.Hide[kj] * Share;
            St.Hp[j] = std::max(0.0, St.Hp[j] - Dmg);
            const double Tx = St.Pos[j].x - St.Pos[g].x, Ty = St.Pos[j].y - St.Pos[g].y;
            const double Tl = std::sqrt(Tx * Tx + Ty * Ty);
            St.KnockDir[j] = Tl > kEps ? Vec2d{Tx / Tl, Ty / Tl} : Vec2d{1.0, 0.0};
            St.KnockLeft[j] = P.CounterKnockSteps;
            if (P.BitesAny(kj)) { St.BiteCd[j] = std::max(St.BiteCd[j], P.CounterNobiteSteps); }
            if (St.Hp[j] <= 0.0)
            {
                Kill(j, CauseCounter);
                Outcome = GoreKill;
            }
        }
        St.Hp[g] = std::max(0.0, St.Hp[g] - P.CounterSelfDamage);
        St.GoreCd[g] = P.FaunaGoreCd;
        Tot.Gores[kg][kj][Outcome] += 1;
        Tot.GoreHp[kg][kj] += Dmg;
        Tot.StrikeHpBy[kj] += Dmg;
        Event Ev;
        Ev.Kind = EvGore;
        Ev.A = static_cast<int>(g);
        Ev.B = static_cast<int>(j);
        Ev.Code = Outcome;
        Ev.X = St.Pos[j].x;
        Ev.Y = St.Pos[j].y;
        Ev.Value = Dmg;
        Ev.Value2 = Vt;
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
                // 먹는 자리: S′ = const_carc_places · 동물 R6 = 사체마다 (죽은 몸 크기)
                const size_t Places = static_cast<size_t>(std::max(P.FaunaOn ? St.CarcPlaces[c] : P.CarcPlaces, 0));
                for (size_t q = 0; q < Grp.size() && q < Places; ++q) { Keep[static_cast<size_t>(Grp[q].second)] = 1; }
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
                        St.NextBirth[q] = Tf + P.Recover[k];   // 동물 R7 종별 (S′ 장면은 모두 const_breed_recover)
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
            for (int k = 0; k < P.NumSpecies; ++k)
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
                            // 비어 있는 가장 낮은 짝 칸에 넣고 칸 차례를 지킴 (파이썬 free[nf] — 짝 차례가 파이썬 줄 차례와 같게)
                            {
                                int FreeSlot = 0;
                                for (;;)
                                {
                                    bool Taken = false;
                                    for (const Pair& Q : St.Pairs)
                                    {
                                        if (Q.Slot == FreeSlot)
                                        {
                                            Taken = true;
                                            break;
                                        }
                                    }
                                    if (!Taken) { break; }
                                    ++FreeSlot;
                                }
                                Np.Slot = FreeSlot;
                                size_t At = St.Pairs.size();
                                for (size_t Q = 0; Q < St.Pairs.size(); ++Q)
                                {
                                    if (St.Pairs[Q].Slot > FreeSlot)
                                    {
                                        At = Q;
                                        break;
                                    }
                                }
                                St.Pairs.insert(St.Pairs.begin() + static_cast<std::ptrdiff_t>(At), Np);
                            }
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
            St.CarcPlaces[C] = P.FaunaOn ? CarcassPlacesOf(s) : P.CarcPlaces;
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

    // 동물 R6: clamp(floor(per_size × size0 × g_size × 자람 + 0.5), min, max) (파이썬 _carcass_places — 이 스텝 BScale)
    int CarcassPlacesOf(size_t s) const
    {
        const int V = static_cast<int>(std::floor(P.FaunaCpPer * P.Size0[St.Sp[s]] * BScale[s] + 0.5));
        return std::min(std::max(V, P.FaunaCpMin), P.FaunaCpMax);
    }

    void StepRegrow()
    {
        // 칸마다 따로인 식이라 차례는 상관없다. 용량 0·값 0 인 칸(막힌 칸·먹이 안 나는 칸)은 x + r(0 − 0) = x 라 건너뛰어도 비트 같다.
        if (GrowFor != St.GrassCap.size()) { ResetGrowLists(); }
        for (int Ci : GrowGrass)
        {
            const size_t c = static_cast<size_t>(Ci);
            St.Grass[c] = St.Grass[c] + St.GrassRegen[c] * (St.GrassCap[c] - St.Grass[c]);
        }
        for (int Ci : GrowRoot)
        {
            const size_t c = static_cast<size_t>(Ci);
            St.Root[c] = St.Root[c] + St.RootRegen[c] * (St.RootCap[c] - St.Root[c]);
        }
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
        // 큰 세계: 무리 자리가 있으면 갓난 꼴은 같은 무리 성체 곁, 먼 꼴은 무리 자리 둘레 정사각 안. 자리는 Spawnable 칸만.
        const int Herd = HerdOf(static_cast<int>(s));
        const bool HasHerd = Herd >= 0 && static_cast<size_t>(Herd) < P.HerdX.size();
        const bool Land = !P.Blocked.empty() || !P.Spawnable.empty();
        if (Dr.UForm < P.RespawnNewbornFrac)
        {
            std::vector<int> Adults;
            for (int q = P.SpLo[k]; q < P.SpHi[k]; ++q)
            {
                if (HasHerd && HerdOf(q) != Herd) { continue; }
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
                    if (Land && !SpawnOkAt(Qx, Qy)) { continue; }
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
            // 후보 c ∈ [0, Size) 를 무리 둘레 정사각 [X0, X0 + Side) 로 옮긴다 (무리 없으면 그대로 — 학습 세계)
            double HX0 = 0.0, HY0 = 0.0, HSide = P.Size;
            if (HasHerd)
            {
                HSide = std::min(P.HerdSide, P.Size);
                HX0 = Clamp(P.HerdX[static_cast<size_t>(Herd)] - 0.5 * HSide, 0.0, P.Size - HSide);
                HY0 = Clamp(P.HerdY[static_cast<size_t>(Herd)] - 0.5 * HSide, 0.0, P.Size - HSide);
            }
            auto CandAt = [&](int ci, double& Cx, double& Cy) {
                Cx = Dr.Cand[static_cast<size_t>(2 * ci)];
                Cy = Dr.Cand[static_cast<size_t>(2 * ci + 1)];
                if (HasHerd)
                {
                    Cx = HX0 + Cx / P.Size * HSide;
                    Cy = HY0 + Cy / P.Size * HSide;
                }
            };
            for (int ci = 0; ci < NC; ++ci)
            {
                double Cx = 0.0, Cy = 0.0;
                CandAt(ci, Cx, Cy);
                const bool LandOk = !Land || SpawnOkAt(Cx, Cy);
                const bool Out = LandOk && Outside(Cx, Cy, Margin);
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
                const double V = Out ? DMin : (LandOk ? DMin - 1e6 : DMin - 2e6);
                if (V > BestV)
                {
                    BestI = ci;
                    BestV = V;
                }
            }
            const int Ci = BestOk >= 0 ? BestOk : BestI;
            CandAt(Ci, NewPos.x, NewPos.y);
            if (Land && !SpawnOkAt(NewPos.x, NewPos.y))
            {
                // 후보 64 개가 모두 막힌 칸 — 무리 자리(없으면 그 후보) 곁 가장 가까운 Spawnable 칸.
                // 반경은 격자 전체 (검토 11-13: 64 칸이면 무리 없는 세계에서 바다 한가운데 후보가 뽑힐 때 못 찾고 막힌 칸에 남을 수 있었다.
                // 처음 찾은 고리에서 멈추므로 보통은 곧 끝난다)
                const Vec2d From = HasHerd ? Vec2d{P.HerdX[static_cast<size_t>(Herd)], P.HerdY[static_cast<size_t>(Herd)]} : NewPos;
                Vec2d Near;
                if (NearestSpawnable(From.x, From.y, P.G, Near)) { NewPos = Near; }
            }
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
        St.GoreCd[s] = 0;
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
        std::vector<double> Hr(S, 0.0), SpdM(S, 0.0), VisF;
        for (size_t j = 0; j < S; ++j)
        {
            if (!St.Alive[j]) { continue; }
            const double Sp = std::sqrt(St.Disp[j].x * St.Disp[j].x + St.Disp[j].y * St.Disp[j].y);
            SpdM[j] = Sp;
            Hr[j] = HearR(Sp);
        }
        if (P.CamoOn) { CamoVis(SpdM, VisF); }   // 동물 R3 (관측과 같은 식)
        // 느낄 수 있는 짝은 칸 격자 이웃(SenseR 안)뿐 — 나머지는 '못 느낌' 식(감쇠) 그대로. 식·값은 전수 비교와 같다.
        BuildHash();
        PercStamp.assign(S, 0);
        PercAppr.assign(S, 0.0);
        int64_t Stamp = 0;
        for (size_t i = 0; i < S; ++i)
        {
            if (!St.Alive[i]) { continue; }
            const int k = St.Sp[i];
            const double See = P.SeeR[k] * (St.Act[i] == ActEat ? P.HeadDown[k] : 1.0);
            const double Hx = St.Head[i].x, Hy = St.Head[i].y;
            Stamp += 1;
            int Bx = 0, By = 0;
            BucketOf(St.Pos[i].x, St.Pos[i].y, Bx, By);
            for (int Qy = std::max(By - 1, 0); Qy <= std::min(By + 1, HashN - 1); ++Qy)
            {
                for (int Qx = std::max(Bx - 1, 0); Qx <= std::min(Bx + 1, HashN - 1); ++Qx)
                {
                    for (int jj = HashHead[static_cast<size_t>(Qy) * static_cast<size_t>(HashN) + static_cast<size_t>(Qx)]; jj >= 0;
                         jj = HashNext[static_cast<size_t>(jj)])
                    {
                        const size_t j = static_cast<size_t>(jj);
                        if (j == i) { continue; }
                        PairCount += 1;
                        const double Dx = St.Pos[j].x - St.Pos[i].x, Dy = St.Pos[j].y - St.Pos[i].y;
                        const double Dist = std::sqrt(Dx * Dx + Dy * Dy);
                        const double Invd = 1.0 / std::max(Dist, kEps);
                        const double CosA = (Dx * Hx + Dy * Hy) * Invd;
                        const bool Seen = P.CamoOn ? Dist <= See * VisF[j] : Dist <= See;
                        const bool Perc = (Seen && CosA >= P.FovCos[k]) || Dist <= Hr[j] || Dist <= P.SmellR[k];
                        if (Perc)
                        {
                            PercStamp[j] = Stamp;
                            PercAppr[j] = Clamp((-(St.Disp[j].x * Dx + St.Disp[j].y * Dy)) * Invd / P.NormVel, -1.0, 1.0);
                        }
                    }
                }
            }
            for (size_t j = 0; j < S; ++j)
            {
                if (!St.Alive[j]) { continue; }
                double& Mv = St.Mem[i * S + j];
                if (j != i && PercStamp[j] == Stamp)
                {
                    Mv = P.MemKeep * Mv + P.MemGain * PercAppr[j];
                }
                else
                {
                    Mv = P.MemDecay * Mv;
                }
            }
        }
    }

    // ---- 이웃 찾기 칸 격자 (공간 해시) — 산 개체만, 한 변 HashB = SenseR + 1 ----
    double SenseR = 20.0, HashB = 21.0;
    int HashN = 1;
    mutable std::vector<int> HashHead, HashNext;
    std::vector<int64_t> PercStamp;
    std::vector<double> PercAppr;
    mutable int64_t PairCount = 0;

    void BucketOf(double X, double Y, int& Bx, int& By) const
    {
        Bx = std::min(std::max(static_cast<int>(std::floor(X / HashB)), 0), HashN - 1);
        By = std::min(std::max(static_cast<int>(std::floor(Y / HashB)), 0), HashN - 1);
    }

    void BuildHash() const
    {
        const size_t S = static_cast<size_t>(P.NumSlots);
        HashHead.assign(static_cast<size_t>(HashN) * static_cast<size_t>(HashN), -1);
        HashNext.assign(S, -1);
        for (size_t s = S; s-- > 0;)
        {
            if (!St.Alive[s]) { continue; }
            int Bx = 0, By = 0;
            BucketOf(St.Pos[s].x, St.Pos[s].y, Bx, By);
            const size_t B = static_cast<size_t>(By) * static_cast<size_t>(HashN) + static_cast<size_t>(Bx);
            HashNext[s] = HashHead[B];
            HashHead[B] = static_cast<int>(s);
        }
    }

    // ---- 은신처 칸 색인 (은신처가 많을 때만; 결과는 전수와 같다 — 같은 식, 같은 차례, 같은 동점 처리) ----
    double ShB = 16.0, ShMaxR = 0.0;
    int ShN = 0;
    bool ShIndexed = false;
    std::vector<int> ShStart, ShList;   // 칸 b 의 은신처 = ShList[ShStart[b] .. ShStart[b+1]) (번호 오름차순)
    std::vector<int> ShScratch;

    void ShBucketOf(double X, double Y, int& Bx, int& By) const
    {
        Bx = std::min(std::max(static_cast<int>(std::floor(X / ShB)), 0), ShN - 1);
        By = std::min(std::max(static_cast<int>(std::floor(Y / ShB)), 0), ShN - 1);
    }

    void BuildShelterIndex()
    {
        const size_t NS = P.ShelX.size();
        ShMaxR = 0.0;
        for (size_t c = 0; c < NS; ++c) { ShMaxR = std::max(ShMaxR, P.ShelR[c]); }
        ShIndexed = NS > ShelterIndexMin;
        ShStart.clear();
        ShList.clear();
        if (!ShIndexed) { return; }
        ShN = std::max(1, static_cast<int>(std::ceil(P.Size / ShB)) + 1);
        const size_t NB = static_cast<size_t>(ShN) * static_cast<size_t>(ShN);
        ShStart.assign(NB + 1u, 0);
        std::vector<size_t> Bk(NS);
        for (size_t c = 0; c < NS; ++c)
        {
            int Bx = 0, By = 0;
            ShBucketOf(P.ShelX[c], P.ShelY[c], Bx, By);
            Bk[c] = static_cast<size_t>(By) * static_cast<size_t>(ShN) + static_cast<size_t>(Bx);
            ShStart[Bk[c] + 1u] += 1;
        }
        for (size_t b = 0; b < NB; ++b) { ShStart[b + 1u] += ShStart[b]; }
        ShList.assign(NS, 0);
        std::vector<int> Fill(ShStart.begin(), ShStart.end() - 1);
        for (size_t c = 0; c < NS; ++c) { ShList[static_cast<size_t>(Fill[Bk[c]]++)] = static_cast<int>(c); }
    }

    // 가운데가 (X, Y) 에서 Radius 안일 수 있는 은신처 번호 (오름차순). 색인이 없으면 모두.
    void ShelterCandidates(double X, double Y, double Radius, std::vector<int>& Out) const
    {
        Out.clear();
        const size_t NS = P.ShelX.size();
        if (!ShIndexed)
        {
            for (size_t c = 0; c < NS; ++c) { Out.push_back(static_cast<int>(c)); }
            return;
        }
        const int Rb = static_cast<int>(std::ceil(Radius / ShB)) + 1;
        int Bx = 0, By = 0;
        ShBucketOf(X, Y, Bx, By);
        for (int Qy = std::max(By - Rb, 0); Qy <= std::min(By + Rb, ShN - 1); ++Qy)
        {
            for (int Qx = std::max(Bx - Rb, 0); Qx <= std::min(Bx + Rb, ShN - 1); ++Qx)
            {
                const size_t B = static_cast<size_t>(Qy) * static_cast<size_t>(ShN) + static_cast<size_t>(Qx);
                for (int q = ShStart[B]; q < ShStart[B + 1u]; ++q) { Out.push_back(ShList[static_cast<size_t>(q)]); }
            }
        }
        std::sort(Out.begin(), Out.end());
    }

    // 가장자리 거리(√(dx²+dy²) − r)가 가장 작은 은신처 (같으면 번호 작은 쪽) — BuildObs 의 Best·EdgeV 와 Edge() 의 값.
    double NearestShelter(double X, double Y, int& Best) const
    {
        Best = -1;
        double BestE = std::numeric_limits<double>::infinity();
        const size_t NS = P.ShelX.size();
        auto Try = [&](size_t n) {
            const double Ex = X - P.ShelX[n], Ey = Y - P.ShelY[n];
            const double Ev = std::sqrt(Ex * Ex + Ey * Ey) - P.ShelR[n];
            if (Ev < BestE || (Ev == BestE && Best >= 0 && static_cast<int>(n) < Best))
            {
                Best = static_cast<int>(n);
                BestE = Ev;
            }
        };
        if (!ShIndexed)
        {
            for (size_t n = 0; n < NS; ++n) { Try(n); }
            return BestE;
        }
        int Bx = 0, By = 0;
        ShBucketOf(X, Y, Bx, By);
        const int KMax = std::max(std::max(Bx, ShN - 1 - Bx), std::max(By, ShN - 1 - By));
        for (int K = 0; K <= KMax; ++K)
        {
            // 고리 K 의 은신처 가운데까지 ≥ (K − 1)·ShB → 가장자리 ≥ (K − 1)·ShB − 가장 큰 반지름. 한 고리 더 여유를 두고 멈춘다.
            if (Best >= 0 && static_cast<double>(K - 2) * ShB - ShMaxR > BestE) { break; }
            for (int Qy = By - K; Qy <= By + K; ++Qy)
            {
                if (Qy < 0 || Qy >= ShN) { continue; }
                const bool EdgeRow = (Qy == By - K || Qy == By + K);
                for (int Qx = Bx - K; Qx <= Bx + K; Qx += (EdgeRow || K == 0) ? 1 : 2 * K)
                {
                    if (Qx < 0 || Qx >= ShN) { continue; }
                    const size_t B = static_cast<size_t>(Qy) * static_cast<size_t>(ShN) + static_cast<size_t>(Qx);
                    for (int q = ShStart[B]; q < ShStart[B + 1u]; ++q) { Try(static_cast<size_t>(ShList[static_cast<size_t>(q)])); }
                }
            }
        }
        return BestE;
    }

    // ---- 막힌 칸 미끄러짐 (축 하나씩). 지금 칸에서 목표 칸 쪽으로 칸을 하나씩 보며, 처음 막힌 칸 앞 경계에서 멈춘다 ----
    bool CellBlockedIdx(int Ix, int Iy) const
    {
        if (Ix < 0 || Iy < 0 || Ix >= P.G || Iy >= P.G) { return false; }
        return P.Blocked[static_cast<size_t>(Iy) * static_cast<size_t>(P.G) + static_cast<size_t>(Ix)] != 0;
    }

    double SlideAxis(double From, double To, double Other, bool bX) const
    {
        const double Inv = 1.0 / P.Cell;
        auto CellC = [this, Inv](double V) { return std::min(std::max(static_cast<int>(V * Inv), 0), P.G - 1); };
        const int C0 = CellC(From), C1 = CellC(To), Co = CellC(Other);
        if (C0 == C1) { return To; }
        const int Dir = C1 > C0 ? 1 : -1;
        for (int c = C0 + Dir;; c += Dir)
        {
            if (bX ? CellBlockedIdx(c, Co) : CellBlockedIdx(Co, c))
            {
                // 앞 칸(c − Dir)의 경계까지. 오른쪽(위)으로 가면 경계 바로 아래 값, 왼쪽(아래)으로 가면 경계 값 그대로
                double V = Dir > 0 ? std::nextafter(static_cast<double>(c) * P.Cell, -std::numeric_limits<double>::infinity())
                                   : static_cast<double>(c + 1) * P.Cell;
                for (int Guard = 0; Guard < 4 && CellC(V) != c - Dir; ++Guard)
                {
                    V = std::nextafter(V, From);
                }
                if (CellC(V) != c - Dir) { V = From; }
                return V;
            }
            if (c == C1) { break; }
        }
        return To;
    }

    double SlideX(double X0, double Y0, double X1) const { return SlideAxis(X0, X1, Y0, true); }
    double SlideY(double X1, double Y0, double Y1) const { return SlideAxis(Y0, Y1, X1, false); }

    // A → B 를 x 먼저, 그다음 y 로 미끄러지며 옮김 (반격 밀림·은신처 밀어냄용)
    Vec2d SlideTo(const Vec2d& A, const Vec2d& B) const
    {
        Vec2d R;
        R.x = SlideX(A.x, A.y, B.x);
        R.y = SlideY(R.x, A.y, B.y);
        return R;
    }

    // (X, Y) 에서 단위 방향 (Ux, Uy) 로 처음 막힌 칸에 들어가는 거리 (MaxT 안에 없으면 무한). 출발 칸은 보지 않는다.
    double RayBlocked(double X, double Y, double Ux, double Uy, double MaxT) const
    {
        const double Inf = std::numeric_limits<double>::infinity();
        const double Cl = P.Cell;
        int Ix = 0, Iy = 0;
        CellOf(X, Y, Ix, Iy);
        const int StepX = Ux > kEps ? 1 : (Ux < -kEps ? -1 : 0);
        const int StepY = Uy > kEps ? 1 : (Uy < -kEps ? -1 : 0);
        double TMaxX = StepX > 0 ? (static_cast<double>(Ix + 1) * Cl - X) / Ux : (StepX < 0 ? (X - static_cast<double>(Ix) * Cl) / -Ux : Inf);
        double TMaxY = StepY > 0 ? (static_cast<double>(Iy + 1) * Cl - Y) / Uy : (StepY < 0 ? (Y - static_cast<double>(Iy) * Cl) / -Uy : Inf);
        const double TDx = StepX != 0 ? Cl / std::fabs(Ux) : Inf;
        const double TDy = StepY != 0 ? Cl / std::fabs(Uy) : Inf;
        for (int Guard = 0; Guard < 4 * P.G + 8; ++Guard)
        {
            double T;
            if (TMaxX < TMaxY)
            {
                T = TMaxX;
                Ix += StepX;
                TMaxX += TDx;
            }
            else
            {
                T = TMaxY;
                Iy += StepY;
                TMaxY += TDy;
            }
            if (!(T <= MaxT)) { return Inf; }
            if (Ix < 0 || Iy < 0 || Ix >= P.G || Iy >= P.G) { return Inf; }
            if (CellBlockedIdx(Ix, Iy)) { return std::max(T, 0.0); }
        }
        return Inf;
    }

    // 큰 세계: 칸 (Ix, Iy) 둘레 반경 Br 칸 평균 (BoxMean 과 같은 창·같은 나눗수, 덧셈 차례만 다름)
    double BoxAt(const std::vector<double>& F, int Ix, int Iy, int Br) const
    {
        const int G = P.G;
        const int X0 = std::min(std::max(Ix - Br, 0), G), X1 = std::min(std::max(Ix + Br + 1, 0), G);
        const int Y0 = std::min(std::max(Iy - Br, 0), G), Y1 = std::min(std::max(Iy + Br + 1, 0), G);
        double Sum = 0.0;
        for (int y = Y0; y < Y1; ++y)
        {
            const double* Row = &F[static_cast<size_t>(y) * static_cast<size_t>(G)];
            for (int x = X0; x < X1; ++x) { Sum += Row[x]; }
        }
        return Sum / static_cast<double>((Y1 - Y0) * (X1 - X0));
    }

    // 다시 자람 칸 목록
    std::vector<int> GrowGrass, GrowRoot;
    size_t GrowFor = 0;

    // 가장 가까운 Spawnable 칸 가운데 (나선, 반경 MaxR 칸). 없으면 거짓.
    bool NearestSpawnable(double X, double Y, int MaxR, Vec2d& Out) const
    {
        int Ix = 0, Iy = 0;
        CellOf(X, Y, Ix, Iy);
        // 고리 R 의 칸만 본다 (윗줄·아랫줄은 모두, 가운데 줄은 양 끝 둘만 — 같은 차례). 반경을 격자 전체로 늘려도 O(G²) 안에서 끝난다 (검토 11-13).
        for (int R = 0; R <= MaxR; ++R)
        {
            double BestD = std::numeric_limits<double>::infinity();
            bool Found = false;
            for (int Qy = Iy - R; Qy <= Iy + R; ++Qy)
            {
                if (Qy < 0 || Qy >= P.G) { continue; }
                const bool EdgeRow = Qy == Iy - R || Qy == Iy + R;
                for (int Qx = Ix - R; Qx <= Ix + R; Qx += (EdgeRow || R == 0) ? 1 : 2 * R)
                {
                    if (Qx < 0 || Qx >= P.G) { continue; }
                    const double Cx = (Qx + 0.5) * P.Cell, Cy = (Qy + 0.5) * P.Cell;
                    if (!SpawnOkAt(Cx, Cy)) { continue; }
                    const double D = (Cx - X) * (Cx - X) + (Cy - Y) * (Cy - Y);
                    if (D < BestD)
                    {
                        BestD = D;
                        Out = Vec2d{Cx, Cy};
                        Found = true;
                    }
                }
            }
            if (Found) { return true; }
        }
        return false;
    }
};

} // namespace EcoR9

#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(pop)
#endif

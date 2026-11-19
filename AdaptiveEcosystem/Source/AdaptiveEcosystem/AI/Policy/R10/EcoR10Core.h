// EcoR10Core.h — R10 파이썬 세계(herbivore_rl/r10: world · senses · terrain.WaterCycle · policy · rule_brain)를
//                엔진과 무관한 C++17 로 옮긴 것 (헤더 전용, 2026-11-19).
//
// 무엇: 세계 하나(파이썬 K = 1)의 한 결정(= 2 걸음: 이동 → 접촉 → 먹기 → 대사 → 생애 → 죽음·사체 → 먹이 재생·수위) ·
//       감각 S1 206 칸 · 마스크(감각에서) · 두뇌 forward(206 → h1 → h2 → 24, tanh, float32) · 확률 뽑기 · 공통 규칙 두뇌 ·
//       종 표(species.txt 'R10SPECIES 1') · 두뇌 파일(<종>.r10brain 'R10BRAIN 1') 읽기. 파일은 herbivore_rl/results/v3/r10/export_r10.py 가 만든다.
// 지킴: 세계 규칙·감각·보상 숫자는 파이썬 그대로 (새 손규칙·길찾기 없음). 종 이름은 규칙에 쓰지 않는다 (종 표 숫자만).
//       표준 라이브러리만, 예외·RTTI 없음, 실행 중 파이썬 없음. 지역 변수는 소문자 (언리얼 shadow 경고 = 오류 — 멤버는 대문자).
// 수치: 상태는 double, 감각은 double 로 셈 → [-1, 1] 자름 → × 감각 마스크 × 살아 있음 → float32. MSVC 에서는 이 헤더 안만 /fp:precise.
// 대조 (11-19, g++ 15 ucrt64 -O2): 파이썬 world.World(K = 1, jitter = False) 와 같은 난수(IRandom 에 파이썬이 쓴 값을 그대로 넣음)·
//       같은 행동으로 4 장면(언덕·강 / 골짜기·호수 / 고원·습지 다시 남 / 작은 맵 번식·나는 몸) 440 결정 — 감각·상태 차이 0 (비트 같음),
//       규칙 두뇌 결정 25,600 개 같음, 두뇌 로짓 < 5e-6 · 확률 뽑기 같음. MSVC 는 초월함수 끝자리가 다를 수 있어 목표는 감각 1e-5 · 상태 1e-6.
// 감각은 senses.py 11-19 사체 냄새(고기·사체 먹는 몸: smell 반경 안 사체를 가장 가까운 8 방향 food 칸에)까지 포함.
// 난수 차례 (파이썬 World.rng 와 같음): Init = 로스터 차례로 시작 개체 _spawn → (DrawWeather 면) 날씨 5 개 ·
//       걸음마다 접촉에 물 수 있는 짝이 있으면 permutation(슬롯 수) · 생애 낳기 _spawn(near) · 결정 끝 다시 남 _spawn.
// 실행 판 확률 뽑기의 U 는 세계 난수가 아니라 HashUnit(Seed, uid, 결정 번호) — 개체마다 시드(계약 select).
#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <map>
#include <string>
#include <vector>

#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(precise, on, push)
#endif

namespace EcoR10
{
// --------------------------------------------------------------------------------------------------------------------
// 계약 상수 (r10/contract.py)
// --------------------------------------------------------------------------------------------------------------------
constexpr int kObsDim = 206, kNumActions = 24, kNumFoods = 8, kNumDiet = 10, kBodyDim = 18;
constexpr double kStepS = 2.0 / 15.0;
constexpr int kDecisionSteps = 2, kDaySteps = 900;
constexpr uint64_t kIoHash = 0xaadfc469c517fc96ull;
enum EAction : int { ActEat = 0, ActSlow0 = 1, ActFast0 = 9, ActHide = 17, ActWatch = 18, ActUp = 19, ActDown = 20, ActDive = 21, ActBurst = 22 };
constexpr int kSpareAction = 23;

constexpr int kNumDir = 8, kNumOther = 8, kOtherFields = 12, kDirFields = 6;
constexpr int kSelfLo = 0, kBodyLo = 16, kDirLo = 34, kHereLo = 82, kOtherLo = 88, kKinLo = 184, kEnvLo = 188, kSpareLo = 194;
// 감각 칸 번호 (contract.OBS_NAMES)
constexpr int kObsEnergy = 0, kObsAirborne = 13, kObsBurstReady = 14;
constexpr int kObsSwim = kBodyLo + 4, kObsFly = kBodyLo + 6, kObsDietMeat = kBodyLo + 15, kObsKill = kBodyLo + 16, kObsBurst = kBodyLo + 17;
constexpr int kObsFoodHere = kHereLo + 0, kObsCarcassHere = kHereLo + 1;
// 다른 동물 한 칸 12 (contract.OTHER_SLOT_FIELDS)
enum EOtherField : int { OfPresent = 0, OfX, OfY, OfApproach, OfSpeed, OfSizeRatio, OfMassRatio, OfInWater, OfInAir, OfHeightDiff, OfSameKin, OfFacing };
// 먹이 층 (terrain.FOOD_KINDS) · 먹이 선호 (species.DIET_KEYS = 먹이 층 8 + 고기 · 사체)
enum EFood : int { FoodGrass = 0, FoodForbs, FoodBrowse, FoodWetMeadow, FoodRoots, FoodInsects, FoodAquatic, FoodDrift };
constexpr int kDietMeat = 8, kDietCarrion = 9;

enum EEventKind : int { EvDeath = 0, EvBirth = 1, EvBite = 2 };
enum ECause : int { CauseNone = 0, CauseBitten = 1, CauseCounter = 2, CauseStarved = 3, CauseOutOfWater = 4, CauseWounds = 5 };
inline const char* CauseName(int Cause)
{
    switch (Cause)
    {
    case CauseBitten: return "bitten";
    case CauseCounter: return "counter";
    case CauseStarved: return "starved";
    case CauseOutOfWater: return "out_of_water";
    case CauseWounds: return "wounds";
    default: return "none";
    }
}

constexpr double kPi = 3.14159265358979323846;
constexpr double kDegToRad = kPi / 180.0;   // numpy deg2rad 와 같은 곱
constexpr double kRadToDeg = 180.0 / kPi;   // numpy rad2deg

// 정규화 (contract.NORM)
constexpr double kDistRef = 2.0, kDistMax = 60.0, kSpeedRef = 1.0, kSpeedMax = 25.0, kHeightRef = 0.5, kHeightMax = 60.0;
constexpr double kDepthRef = 0.25, kDepthMax = 5.0, kCurRef = 0.1, kCurMax = 2.0, kFoodRef = 1.0, kRatioLog2Max = 10.0, kKinCountMax = 12.0;

// --------------------------------------------------------------------------------------------------------------------
// 작은 도움 (numpy 와 같은 뜻)
// --------------------------------------------------------------------------------------------------------------------
inline double Clamp(double V, double Lo, double Hi) { return std::min(std::max(V, Lo), Hi); }   // np.clip = minimum(maximum(x, lo), hi)

/** contract.lg: clip(log1p(max(x, 0) / ref) / log1p(mx / ref), 0, 1) */
inline double Lg(double V, double Ref, double Mx) { return Clamp(std::log1p(std::max(V, 0.0) / Ref) / std::log1p(Mx / Ref), 0.0, 1.0); }

/** contract.slg: sign(x) · lg(|x|) */
inline double Slg(double V, double Ref, double Mx)
{
    const double s = (V > 0.0) ? 1.0 : ((V < 0.0) ? -1.0 : 0.0);
    return s * Lg(std::fabs(V), Ref, Mx);
}

/** contract.ratio: clip(log2(a / b) / 10, -1, 1) */
inline double Ratio(double A, double B) { return Clamp(std::log2(std::max(A, 1e-9) / std::max(B, 1e-9)) / kRatioLog2Max, -1.0, 1.0); }

/** np.remainder (나머지 부호 = 나누는 수 부호) */
inline double NpRemainder(double A, double B)
{
    double m = std::fmod(A, B);
    if (m != 0.0) { if ((B < 0.0) != (m < 0.0)) { m += B; } }
    else { m = std::copysign(0.0, B); }
    return m;
}

/** 머리 기준 8 방향 (contract.DIR8 — |값| < 1e-12 는 0 으로). 이동에만 쓴다 (감각 _rot 은 그냥 cos·sin). */
inline void Dir8(int J, double& OutC, double& OutS)
{
    const double ang = (45.0 * J) * kDegToRad;
    OutC = std::cos(ang);
    OutS = std::sin(ang);
    if (std::fabs(OutC) < 1e-12) { OutC = 0.0; }
    if (std::fabs(OutS) < 1e-12) { OutS = 0.0; }
}

/** 행동 → (머리 기준 방향 j 또는 −1, 빠르기 0 서기 · 1 천천히 · 2 빠르게) — world._dir_of_action */
inline void DirOfAction(int A, int& OutJ, int& OutGait)
{
    OutJ = -1;
    OutGait = 0;
    if (A >= ActSlow0 && A < ActSlow0 + 8) { OutJ = A - ActSlow0; OutGait = 1; }
    else if (A >= ActFast0 && A < ActFast0 + 8) { OutJ = A - ActFast0; OutGait = 2; }
}

// 개체마다 확률 뽑기 U (실행 판). SplitMix64 섞기 → [0, 1) 53 비트.
inline uint64_t HashMix(uint64_t V)
{
    V += 0x9E3779B97F4A7C15ull;
    V = (V ^ (V >> 30)) * 0xBF58476D1CE4E5B9ull;
    V = (V ^ (V >> 27)) * 0x94D049BB133111EBull;
    return V ^ (V >> 31);
}
inline double HashUnit(uint64_t Seed, int64_t Uid, int64_t Decision)
{
    const uint64_t h = HashMix(HashMix(Seed ^ 0x52313000ull) ^ HashMix(static_cast<uint64_t>(Uid) * 0xD1B54A32D192ED03ull) ^
                               HashMix(static_cast<uint64_t>(Decision) + 0x8CB92BA72F3D8DD7ull));
    return static_cast<double>(h >> 11) * (1.0 / 9007199254740992.0);
}

// --------------------------------------------------------------------------------------------------------------------
// 난수 (파이썬 numpy Generator 와 같은 세 쓰임: random() · uniform(lo, hi) · permutation(n))
// --------------------------------------------------------------------------------------------------------------------
class IRandom
{
public:
    virtual ~IRandom() {}
    virtual double Random() = 0;                                     // [0, 1)
    virtual double Uniform(double Lo, double Hi) = 0;                // lo + (hi − lo) · random()
    virtual void Permutation(int N, std::vector<int>& Out) = 0;      // 0 ~ N−1 섞음
};

/** 실행용 PCG32 (O'Neill). 파이썬과 같은 값은 아니다 — 같은 시드면 같은 세계. */
class FPcg32Random final : public IRandom
{
public:
    explicit FPcg32Random(uint64_t InSeed = 1, uint64_t InStream = 0x5210ull) { Reseed(InSeed, InStream); }
    void Reseed(uint64_t InSeed, uint64_t InStream)
    {
        State = 0u;
        Inc = (InStream << 1u) | 1u;
        NextU32();
        State += InSeed;
        NextU32();
    }
    uint32_t NextU32()
    {
        const uint64_t old = State;
        State = old * 6364136223846793005ull + Inc;
        const uint32_t xs = static_cast<uint32_t>(((old >> 18u) ^ old) >> 27u);
        const uint32_t rot = static_cast<uint32_t>(old >> 59u);
        return (xs >> rot) | (xs << ((32u - rot) & 31u));
    }
    double Random() override
    {
        const uint64_t hi = static_cast<uint64_t>(NextU32() >> 5);   // 27 비트
        const uint64_t lo = static_cast<uint64_t>(NextU32() >> 6);   // 26 비트
        return static_cast<double>((hi << 26) | lo) * (1.0 / 9007199254740992.0);
    }
    double Uniform(double Lo, double Hi) override { return Lo + (Hi - Lo) * Random(); }
    void Permutation(int N, std::vector<int>& Out) override
    {
        Out.resize(static_cast<size_t>(std::max(N, 0)));
        for (int k = 0; k < N; ++k) { Out[static_cast<size_t>(k)] = k; }
        for (int k = N - 1; k > 0; --k)
        {
            const int r = static_cast<int>(Random() * static_cast<double>(k + 1));
            std::swap(Out[static_cast<size_t>(k)], Out[static_cast<size_t>(std::min(r, k))]);
        }
    }

private:
    uint64_t State = 0;
    uint64_t Inc = 1;
};

/** 대조 시험용: 파이썬이 쓴 난수를 차례대로 돌려준다. Data = [종류, 개수, 값…] 의 이음 (종류 0 random · 1 uniform · 2 permutation). */
class FInjectedRandom final : public IRandom
{
public:
    std::vector<double> Data;
    size_t Pos = 0;
    bool Bad = false;
    std::string Err;

    double Random() override { return Take(0); }
    double Uniform(double, double) override { return Take(1); }
    void Permutation(int N, std::vector<int>& Out) override
    {
        Out.assign(static_cast<size_t>(std::max(N, 0)), 0);
        for (int k = 0; k < N; ++k) { Out[static_cast<size_t>(k)] = k; }
        if (!Expect(2)) { return; }
        const int n = static_cast<int>(Data[Pos + 1]);
        if (n != N) { Fail("permutation length"); return; }
        for (int k = 0; k < n; ++k) { Out[static_cast<size_t>(k)] = static_cast<int>(Data[Pos + 2 + static_cast<size_t>(k)]); }
        Pos += 2 + static_cast<size_t>(n);
    }

private:
    bool Expect(int Kind)
    {
        if (Bad) { return false; }
        if (Pos + 2 > Data.size()) { Fail("ran out of injected randoms"); return false; }
        if (static_cast<int>(Data[Pos]) != Kind) { Fail("kind mismatch (want " + std::to_string(Kind) + " got " + std::to_string(static_cast<int>(Data[Pos])) + ")"); return false; }
        return true;
    }
    double Take(int Kind)
    {
        if (!Expect(Kind)) { return 0.5; }
        const double v = Data[Pos + 2];
        Pos += 3;
        return v;
    }
    void Fail(const std::string& Msg)
    {
        if (!Bad) { Bad = true; Err = Msg + " at " + std::to_string(Pos); }
    }
};

// --------------------------------------------------------------------------------------------------------------------
// 지형 (terrain.MapCard · WaterCycle)
// --------------------------------------------------------------------------------------------------------------------
struct FWaterCycle
{
    double AmpM = 0, RiseS = 40, HighS = 20, FallS = 50, LowS = 40, PhaseS = 0, RainRiseM = 0;

    /** terrain.WaterCycle.offset — 수위 오프셋 m */
    double Offset(double TSec, double Rain) const
    {
        const double period = RiseS + HighS + FallS + LowS;
        if (AmpM <= 0.0 || period <= 0.0) { return RainRiseM * Rain; }
        const double u = NpRemainder(TSec + PhaseS, period);
        double f = 0.0;
        if (u < RiseS) { f = u / RiseS; }
        else if (u < RiseS + HighS) { f = 1.0; }
        else if (u < RiseS + HighS + FallS) { f = 1.0 - (u - RiseS - HighS) / FallS; }
        else { f = 0.0; }
        return AmpM * (f - 0.5) + RainRiseM * Rain;
    }
};

struct FMapLayers   // = terrain.MapCard. 칸 차례 iy*W+ix, x·y 는 m (0 ~ W*CellM)
{
    int W = 0, H = 0;
    double CellM = 1.0;
    std::vector<float> GroundZ, WaterBedZ, WaterSurf0Z, CoverSight, CurrentX, CurrentY;   // W*H
    std::vector<uint8_t> WaterSys, Block, Shelter, Canopy;                              // W*H 0/1 (Shelter = cover_body)
    std::vector<float> FoodAmount, FoodCap, FoodRegen, FoodDry;                         // kNumFoods*W*H, k*W*H + cell
    FWaterCycle Water;

    size_t Cells() const { return static_cast<size_t>(W) * static_cast<size_t>(H); }

    /** 빈 맵 (평평 0 m, 물·막힘·먹이 없음) */
    void Blank(int InW, int InH, double InCellM)
    {
        W = InW;
        H = InH;
        CellM = InCellM;
        const size_t n = Cells();
        GroundZ.assign(n, 0.0f);
        WaterBedZ.assign(n, -1.0f);
        WaterSurf0Z.assign(n, -1.0f);
        CoverSight.assign(n, 0.0f);
        CurrentX.assign(n, 0.0f);
        CurrentY.assign(n, 0.0f);
        WaterSys.assign(n, 0);
        Block.assign(n, 0);
        Shelter.assign(n, 0);
        Canopy.assign(n, 0);
        FoodAmount.assign(n * kNumFoods, 0.0f);
        FoodCap.assign(n * kNumFoods, 0.0f);
        FoodRegen.assign(n * kNumFoods, 0.0f);
        FoodDry.assign(n * kNumFoods, 0.0f);
    }

    /** terrain.MapCard.check 와 같은 검사 (크기 · 유한 · 먹이 [0, cap] · 물 바닥 ≤ 땅) */
    bool Check(std::string* Err) const
    {
        auto fail = [Err](const std::string& Msg) { if (Err) { *Err = Msg; } return false; };
        if (W <= 0 || H <= 0 || !(CellM > 0.0)) { return fail("map size"); }
        const size_t n = Cells();
        const std::vector<float>* fl[] = {&GroundZ, &WaterBedZ, &WaterSurf0Z, &CoverSight, &CurrentX, &CurrentY};
        for (const std::vector<float>* v : fl)
        {
            if (v->size() != n) { return fail("map layer size"); }
            for (float f : *v) { if (!std::isfinite(f)) { return fail("map layer non-finite"); } }
        }
        const std::vector<uint8_t>* bl[] = {&WaterSys, &Block, &Shelter, &Canopy};
        for (const std::vector<uint8_t>* v : bl) { if (v->size() != n) { return fail("map flag layer size"); } }
        const std::vector<float>* fd[] = {&FoodAmount, &FoodCap, &FoodRegen, &FoodDry};
        for (const std::vector<float>* v : fd)
        {
            if (v->size() != n * kNumFoods) { return fail("food layer size"); }
            for (float f : *v) { if (!std::isfinite(f)) { return fail("food layer non-finite"); } }
        }
        for (size_t k = 0; k < n * kNumFoods; ++k)
        {
            if (FoodCap[k] < 0.0f || FoodAmount[k] > FoodCap[k] + 1e-6f) { return fail("food amount must be in [0, cap]"); }
        }
        for (size_t k = 0; k < n; ++k)
        {
            if (WaterSys[k] && WaterBedZ[k] > GroundZ[k] + 1e-4f) { return fail("water bed above ground"); }
        }
        return true;
    }
};

// --------------------------------------------------------------------------------------------------------------------
// 종 표 (export_r10.py species.txt — world._set_body 가 슬롯에 넣는 값 그대로)
// --------------------------------------------------------------------------------------------------------------------
struct FSpecies
{
    std::string Id;
    std::string NameKo;
    // body (없는 값 = 0)
    double MassKg = 0, RadiusM = 0, WalkMps = 0, RunMps = 0, SwimMps = 0, SwimFastMps = 0, FlyMps = 0, CruiseMps = 0, DiveMps = 0;
    double AccelMps2 = 0, TurnDps = 0, LatAccelMps2 = 0, MaxSlopeDeg = 0, StepM = 0, StaminaS = 0, StaminaRecoverS = 0;
    double BurstMps = 0, BurstS = 0, BurstExhaustMps = 0, BurstExhaustS = 0;
    // medium
    bool Ground = false, Swim = false, Fly = false, NeedsWater = false;
    double WadeDepthM = 0, SwimDepthFrac = 0, CruiseHeightM = 0, CeilingM = 0, TakeoffS = 0;
    // senses (fov_cos = cos(min(fov, 360) / 2))
    double SightM = 0, FovCos = 0, SmellM = 0, NightVision = 0;
    // eat · metabolism (drain_per_step = drain_per_day / 900, swim_cost·fly_cost 없으면 1)
    double RatePerS = 0, EnergyPerUnit = 0, DrainPerStep = 0, ReserveDays = 0, RunCost = 1, SwimCost = 1, FlyCost = 1;
    // combat · life
    double KillMassRatio = 0, ReachM = 0, AttackCdS = 0, Defense = 0, CounterReachM = 0;
    double MaturityDays = 1, Litter = 1, GestationDays = 0;
    double Diet[kNumDiet] = {};
    float BodyVec[kBodyDim] = {};
    bool AMask[kNumActions] = {};
    bool OMask[kObsDim] = {};
    bool HasBurstCard = false;   // 카드에 body.burst_mps 가 있음 (amask 덮치기 칸)
};

namespace Detail
{
struct FFieldD { const char* Name; double FSpecies::*Ptr; };
struct FFieldB { const char* Name; bool FSpecies::*Ptr; };

inline const std::vector<FFieldD>& DoubleFields()
{
    static const std::vector<FFieldD> F = {
        {"mass_kg", &FSpecies::MassKg}, {"radius_m", &FSpecies::RadiusM}, {"walk_mps", &FSpecies::WalkMps}, {"run_mps", &FSpecies::RunMps},
        {"swim_mps", &FSpecies::SwimMps}, {"swim_fast_mps", &FSpecies::SwimFastMps}, {"fly_mps", &FSpecies::FlyMps},
        {"cruise_mps", &FSpecies::CruiseMps}, {"dive_mps", &FSpecies::DiveMps}, {"accel_mps2", &FSpecies::AccelMps2},
        {"turn_dps", &FSpecies::TurnDps}, {"lat_accel_mps2", &FSpecies::LatAccelMps2}, {"max_slope_deg", &FSpecies::MaxSlopeDeg},
        {"step_m", &FSpecies::StepM}, {"stamina_s", &FSpecies::StaminaS}, {"stamina_recover_s", &FSpecies::StaminaRecoverS},
        {"burst_mps", &FSpecies::BurstMps}, {"burst_s", &FSpecies::BurstS}, {"burst_exhaust_mps", &FSpecies::BurstExhaustMps},
        {"burst_exhaust_s", &FSpecies::BurstExhaustS},
        {"wade_depth_m", &FSpecies::WadeDepthM}, {"swim_depth_frac", &FSpecies::SwimDepthFrac}, {"cruise_height_m", &FSpecies::CruiseHeightM},
        {"ceiling_m", &FSpecies::CeilingM}, {"takeoff_s", &FSpecies::TakeoffS},
        {"sight_m", &FSpecies::SightM}, {"fov_cos", &FSpecies::FovCos}, {"smell_m", &FSpecies::SmellM}, {"night_vision", &FSpecies::NightVision},
        {"rate_per_s", &FSpecies::RatePerS}, {"energy_per_unit", &FSpecies::EnergyPerUnit}, {"drain_per_step", &FSpecies::DrainPerStep},
        {"reserve_days", &FSpecies::ReserveDays}, {"run_cost", &FSpecies::RunCost}, {"swim_cost", &FSpecies::SwimCost},
        {"fly_cost", &FSpecies::FlyCost},
        {"kill_mass_ratio", &FSpecies::KillMassRatio}, {"reach_m", &FSpecies::ReachM}, {"attack_cd_s", &FSpecies::AttackCdS},
        {"defense", &FSpecies::Defense}, {"counter_reach_m", &FSpecies::CounterReachM},
        {"maturity_days", &FSpecies::MaturityDays}, {"litter", &FSpecies::Litter}, {"gestation_days", &FSpecies::GestationDays},
    };
    return F;
}
inline const std::vector<FFieldB>& BoolFields()
{
    static const std::vector<FFieldB> F = {
        {"ground", &FSpecies::Ground}, {"swim", &FSpecies::Swim}, {"fly", &FSpecies::Fly}, {"needs_water", &FSpecies::NeedsWater},
        {"has_burst", &FSpecies::HasBurstCard},
    };
    return F;
}

inline void SplitWords(const std::string& Line, std::vector<std::string>& Out)
{
    Out.clear();
    size_t k = 0;
    while (k < Line.size())
    {
        while (k < Line.size() && (Line[k] == ' ' || Line[k] == '\t' || Line[k] == '\r')) { ++k; }
        if (k >= Line.size()) { break; }
        const size_t b = k;
        while (k < Line.size() && Line[k] != ' ' && Line[k] != '\t' && Line[k] != '\r') { ++k; }
        Out.push_back(Line.substr(b, k - b));
    }
}

inline bool ParseDouble(const std::string& S, double& Out)
{
    if (S.empty()) { return false; }
    char* end = nullptr;
    Out = std::strtod(S.c_str(), &end);
    return end && *end == '\0' && std::isfinite(Out);
}

inline void SetErr(std::string* Err, const std::string& Msg) { if (Err) { *Err = Msg; } }

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
    uint32_t hs[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au, 0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u};
    auto rotr = [](uint32_t V, uint32_t N) { return (V >> N) | (V << (32u - N)); };
    const uint64_t bitLen = static_cast<uint64_t>(Len) * 8u;
    const size_t padded = ((Len + 9u + 63u) / 64u) * 64u;
    uint8_t chunk[64];
    for (size_t off = 0; off < padded; off += 64u)
    {
        for (size_t k = 0; k < 64u; ++k)
        {
            const size_t pos = off + k;
            uint8_t v = 0;
            if (pos < Len) { v = Data[pos]; }
            else if (pos == Len) { v = 0x80u; }
            else if (pos >= padded - 8u) { v = static_cast<uint8_t>((bitLen >> (8u * (padded - 1u - pos))) & 0xffu); }
            chunk[k] = v;
        }
        uint32_t wt[64];
        for (int k = 0; k < 16; ++k)
        {
            const size_t b4 = static_cast<size_t>(4 * k);
            wt[k] = (static_cast<uint32_t>(chunk[b4]) << 24) | (static_cast<uint32_t>(chunk[b4 + 1]) << 16) |
                    (static_cast<uint32_t>(chunk[b4 + 2]) << 8) | static_cast<uint32_t>(chunk[b4 + 3]);
        }
        for (int k = 16; k < 64; ++k)
        {
            const uint32_t s0 = rotr(wt[k - 15], 7) ^ rotr(wt[k - 15], 18) ^ (wt[k - 15] >> 3);
            const uint32_t s1 = rotr(wt[k - 2], 17) ^ rotr(wt[k - 2], 19) ^ (wt[k - 2] >> 10);
            wt[k] = wt[k - 16] + s0 + wt[k - 7] + s1;
        }
        uint32_t a = hs[0], b = hs[1], c = hs[2], d = hs[3], e = hs[4], f = hs[5], g = hs[6], h = hs[7];
        for (int k = 0; k < 64; ++k)
        {
            const uint32_t s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
            const uint32_t ch = (e & f) ^ ((~e) & g);
            const uint32_t t1 = h + s1 + ch + Kt[k] + wt[k];
            const uint32_t s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
            const uint32_t mj = (a & b) ^ (a & c) ^ (b & c);
            const uint32_t t2 = s0 + mj;
            h = g;
            g = f;
            f = e;
            e = d + t1;
            d = c;
            c = b;
            b = a;
            a = t1 + t2;
        }
        hs[0] += a; hs[1] += b; hs[2] += c; hs[3] += d; hs[4] += e; hs[5] += f; hs[6] += g; hs[7] += h;
    }
    for (int k = 0; k < 8; ++k)
    {
        OutDigest[4 * k + 0] = static_cast<uint8_t>(hs[k] >> 24);
        OutDigest[4 * k + 1] = static_cast<uint8_t>(hs[k] >> 16);
        OutDigest[4 * k + 2] = static_cast<uint8_t>(hs[k] >> 8);
        OutDigest[4 * k + 3] = static_cast<uint8_t>(hs[k]);
    }
}

inline std::string HexOf(const uint8_t* Bytes, size_t N)
{
    static const char digits[] = "0123456789abcdef";
    std::string out;
    out.reserve(2 * N);
    for (size_t k = 0; k < N; ++k)
    {
        out.push_back(digits[(Bytes[k] >> 4) & 0xf]);
        out.push_back(digits[Bytes[k] & 0xf]);
    }
    return out;
}

// 아주 작은 JSON 읽기 (머리글 한 줄: "key": "문자열" 또는 숫자). 중첩 없음 가정.
inline size_t JsonValuePos(const std::string& J, const char* Key)
{
    const std::string pat = std::string("\"") + Key + "\"";
    size_t p = J.find(pat);
    if (p == std::string::npos) { return std::string::npos; }
    p = J.find(':', p + pat.size());
    if (p == std::string::npos) { return std::string::npos; }
    ++p;
    while (p < J.size() && (J[p] == ' ' || J[p] == '\t')) { ++p; }
    return p;
}
inline bool JsonString(const std::string& J, const char* Key, std::string& Out)
{
    const size_t p = JsonValuePos(J, Key);
    if (p == std::string::npos || p >= J.size() || J[p] != '"') { return false; }
    const size_t e = J.find('"', p + 1);
    if (e == std::string::npos) { return false; }
    Out = J.substr(p + 1, e - p - 1);
    return true;
}
inline bool JsonNumber(const std::string& J, const char* Key, double& Out)
{
    const size_t p = JsonValuePos(J, Key);
    if (p == std::string::npos) { return false; }
    char* end = nullptr;
    Out = std::strtod(J.c_str() + p, &end);
    return end != J.c_str() + p;
}
}  // namespace Detail

/** species.txt ('R10SPECIES 1') 읽기. 종 차례 = 파일 차례 (로스터 FRosterEntry::Species 는 이 번호). */
inline bool LoadSpeciesTable(const std::string& Text, std::vector<FSpecies>& Out, std::string* Err)
{
    Out.clear();
    std::vector<std::string> lines;
    {
        size_t b = 0;
        while (b <= Text.size())
        {
            size_t e = Text.find('\n', b);
            if (e == std::string::npos) { e = Text.size(); }
            lines.push_back(Text.substr(b, e - b));
            b = e + 1;
        }
    }
    std::vector<std::string> w;
    size_t li = 0;
    while (li < lines.size()) { Detail::SplitWords(lines[li], w); if (!w.empty()) { break; } ++li; }
    if (li >= lines.size() || w.size() < 2 || w[0] != "R10SPECIES" || w[1] != "1") { Detail::SetErr(Err, "not an R10SPECIES 1 file"); return false; }
    FSpecies* cur = nullptr;
    int got = 0;
    for (++li; li < lines.size(); ++li)
    {
        Detail::SplitWords(lines[li], w);
        if (w.empty() || w[0][0] == '#') { continue; }
        const std::string& key = w[0];
        if (key == "io_hash")
        {
            if (w.size() < 2 || std::strtoull(w[1].c_str(), nullptr, 16) != kIoHash) { Detail::SetErr(Err, "species table io_hash mismatch"); return false; }
            continue;
        }
        if (key == "count") { continue; }
        if (key == "species")
        {
            if (w.size() < 2) { Detail::SetErr(Err, "species without id"); return false; }
            Out.emplace_back();
            cur = &Out.back();
            cur->Id = w[1];
            got = 0;
            continue;
        }
        if (!cur) { Detail::SetErr(Err, "value before species line: " + key); return false; }
        if (key == "end") { cur = nullptr; continue; }
        if (key == "name_ko")
        {
            const size_t p = lines[li].find("name_ko");
            std::string rest = lines[li].substr(p + 7);
            while (!rest.empty() && (rest[0] == ' ' || rest[0] == '\t')) { rest.erase(0, 1); }
            while (!rest.empty() && (rest.back() == '\r' || rest.back() == ' ')) { rest.pop_back(); }
            cur->NameKo = rest;
            continue;
        }
        auto readN = [&](size_t N, std::vector<double>& V) -> bool
        {
            if (w.size() != N + 1) { return false; }
            V.resize(N);
            for (size_t k = 0; k < N; ++k) { if (!Detail::ParseDouble(w[k + 1], V[k])) { return false; } }
            return true;
        };
        std::vector<double> v;
        if (key == "diet")
        {
            if (!readN(kNumDiet, v)) { Detail::SetErr(Err, cur->Id + ": diet"); return false; }
            for (int k = 0; k < kNumDiet; ++k) { cur->Diet[k] = v[static_cast<size_t>(k)]; }
            continue;
        }
        if (key == "body_vec")
        {
            if (!readN(kBodyDim, v)) { Detail::SetErr(Err, cur->Id + ": body_vec"); return false; }
            for (int k = 0; k < kBodyDim; ++k) { cur->BodyVec[k] = static_cast<float>(v[static_cast<size_t>(k)]); }
            continue;
        }
        if (key == "amask")
        {
            if (!readN(kNumActions, v)) { Detail::SetErr(Err, cur->Id + ": amask"); return false; }
            for (int k = 0; k < kNumActions; ++k) { cur->AMask[k] = v[static_cast<size_t>(k)] != 0.0; }
            continue;
        }
        if (key == "omask")
        {
            if (!readN(kObsDim, v)) { Detail::SetErr(Err, cur->Id + ": omask"); return false; }
            for (int k = 0; k < kObsDim; ++k) { cur->OMask[k] = v[static_cast<size_t>(k)] != 0.0; }
            continue;
        }
        bool done = false;
        for (const Detail::FFieldD& f : Detail::DoubleFields())
        {
            if (key == f.Name)
            {
                double d = 0;
                if (w.size() != 2 || !Detail::ParseDouble(w[1], d)) { Detail::SetErr(Err, cur->Id + ": bad " + key); return false; }
                cur->*(f.Ptr) = d;
                ++got;
                done = true;
                break;
            }
        }
        if (done) { continue; }
        for (const Detail::FFieldB& f : Detail::BoolFields())
        {
            if (key == f.Name)
            {
                if (w.size() != 2) { Detail::SetErr(Err, cur->Id + ": bad " + key); return false; }
                cur->*(f.Ptr) = (w[1] == "1" || w[1] == "true");
                ++got;
                done = true;
                break;
            }
        }
        if (!done) { Detail::SetErr(Err, cur->Id + ": unknown key " + key); return false; }
        if (got > static_cast<int>(Detail::DoubleFields().size() + Detail::BoolFields().size())) { Detail::SetErr(Err, cur->Id + ": duplicate keys"); return false; }
    }
    if (Out.empty()) { Detail::SetErr(Err, "no species"); return false; }
    return true;
}

/** 종 id → 종 표 번호 (없으면 −1) */
inline int FindSpecies(const std::vector<FSpecies>& Table, const std::string& Id)
{
    for (size_t k = 0; k < Table.size(); ++k) { if (Table[k].Id == Id) { return static_cast<int>(k); } }
    return -1;
}

// --------------------------------------------------------------------------------------------------------------------
// 두뇌 (policy.forward_np · mask_from_obs · sample_np)
// --------------------------------------------------------------------------------------------------------------------
struct FBrain
{
    std::string Species;
    int In = 0, H1 = 0, H2 = 0, Out = 0;
    std::vector<float> W0, B0, W1, B1, W2, B2;   // W0 (H1 × In) 행 우선 · W1 (H2 × H1) · W2 (Out × H2)
    double Decisions = 0;
    std::string CardSha;
};

/** <종>.r10brain: 첫 줄 JSON 머리글 + '\n' + float32 W0,B0,W1,B1,W2,B2 (작은 끝). io_hash · 크기 · payload_sha256 검사. */
inline bool LoadBrain(const uint8_t* Data, size_t Len, FBrain& Out, std::string* Err)
{
    const uint8_t* nl = static_cast<const uint8_t*>(std::memchr(Data, '\n', std::min<size_t>(Len, 65536)));
    if (!nl) { Detail::SetErr(Err, "brain: no header line"); return false; }
    const std::string head(reinterpret_cast<const char*>(Data), static_cast<size_t>(nl - Data));
    std::string fmt, io, act;
    if (!Detail::JsonString(head, "format", fmt) || fmt != "R10BRAIN 1") { Detail::SetErr(Err, "brain: format is not R10BRAIN 1"); return false; }
    if (!Detail::JsonString(head, "io_hash", io) || std::strtoull(io.c_str(), nullptr, 16) != kIoHash) { Detail::SetErr(Err, "brain: io_hash " + io + " != contract"); return false; }
    if (!Detail::JsonString(head, "activation", act) || act != "tanh") { Detail::SetErr(Err, "brain: activation"); return false; }
    double obsDim = 0, nAct = 0, h1 = 0, h2 = 0, payload = 0;
    if (!Detail::JsonNumber(head, "obs_dim", obsDim) || !Detail::JsonNumber(head, "n_actions", nAct) || !Detail::JsonNumber(head, "h1", h1) ||
        !Detail::JsonNumber(head, "h2", h2) || !Detail::JsonNumber(head, "payload_bytes", payload))
    {
        Detail::SetErr(Err, "brain: header fields");
        return false;
    }
    if (static_cast<int>(obsDim) != kObsDim || static_cast<int>(nAct) != kNumActions || h1 < 1 || h2 < 1 || h1 > 4096 || h2 > 4096)
    {
        Detail::SetErr(Err, "brain: shape");
        return false;
    }
    Out = FBrain();
    Detail::JsonString(head, "species", Out.Species);
    Detail::JsonString(head, "card_sha", Out.CardSha);
    Detail::JsonNumber(head, "decisions", Out.Decisions);
    Out.In = kObsDim;
    Out.H1 = static_cast<int>(h1);
    Out.H2 = static_cast<int>(h2);
    Out.Out = kNumActions;
    const size_t nf = static_cast<size_t>(Out.H1) * Out.In + Out.H1 + static_cast<size_t>(Out.H2) * Out.H1 + Out.H2 +
                      static_cast<size_t>(Out.Out) * Out.H2 + Out.Out;
    const uint8_t* body = nl + 1;
    const size_t bodyLen = Len - static_cast<size_t>(body - Data);
    if (static_cast<size_t>(payload) != nf * 4u || bodyLen != nf * 4u) { Detail::SetErr(Err, "brain: payload size"); return false; }
    std::string wantSha;
    if (Detail::JsonString(head, "payload_sha256", wantSha))
    {
        uint8_t dg[32];
        Detail::Sha256(body, bodyLen, dg);
        if (Detail::HexOf(dg, 32) != wantSha) { Detail::SetErr(Err, "brain: payload sha256 mismatch"); return false; }
    }
    std::vector<float> all(nf);
    std::memcpy(all.data(), body, nf * 4u);   // 작은 끝 가정 (x64·ARM64)
    size_t o = 0;
    auto take = [&](std::vector<float>& V, size_t N) { V.assign(all.begin() + static_cast<std::ptrdiff_t>(o), all.begin() + static_cast<std::ptrdiff_t>(o + N)); o += N; };
    take(Out.W0, static_cast<size_t>(Out.H1) * Out.In);
    take(Out.B0, static_cast<size_t>(Out.H1));
    take(Out.W1, static_cast<size_t>(Out.H2) * Out.H1);
    take(Out.B1, static_cast<size_t>(Out.H2));
    take(Out.W2, static_cast<size_t>(Out.Out) * Out.H2);
    take(Out.B2, static_cast<size_t>(Out.Out));
    for (float f : all) { if (!std::isfinite(f)) { Detail::SetErr(Err, "brain: non-finite weight"); return false; } }
    return true;
}

/** policy.forward_np — 로짓 24 (마스크 전). float32 셈. */
inline void BrainLogits(const FBrain& Bn, const float* Obs, float* OutLogits)
{
    std::vector<float> h1(static_cast<size_t>(Bn.H1)), h2(static_cast<size_t>(Bn.H2));
    for (int r = 0; r < Bn.H1; ++r)
    {
        const float* wr = Bn.W0.data() + static_cast<size_t>(r) * Bn.In;
        float s = 0.0f;
        for (int k = 0; k < Bn.In; ++k) { s += Obs[k] * wr[k]; }
        h1[static_cast<size_t>(r)] = std::tanh(s + Bn.B0[static_cast<size_t>(r)]);
    }
    for (int r = 0; r < Bn.H2; ++r)
    {
        const float* wr = Bn.W1.data() + static_cast<size_t>(r) * Bn.H1;
        float s = 0.0f;
        for (int k = 0; k < Bn.H1; ++k) { s += h1[static_cast<size_t>(k)] * wr[k]; }
        h2[static_cast<size_t>(r)] = std::tanh(s + Bn.B1[static_cast<size_t>(r)]);
    }
    for (int r = 0; r < Bn.Out; ++r)
    {
        const float* wr = Bn.W2.data() + static_cast<size_t>(r) * Bn.H2;
        float s = 0.0f;
        for (int k = 0; k < Bn.H2; ++k) { s += h2[static_cast<size_t>(k)] * wr[k]; }
        OutLogits[r] = s + Bn.B2[static_cast<size_t>(r)];
    }
}

/** policy.mask_from_obs — 몸이 못 하는 행동을 감각의 몸 벡터(b_swim·b_fly·b_burst)와 burst_ready 로 막는다. */
inline void MaskFromObs(const float* Obs, bool* OutMask)
{
    for (int k = 0; k < kNumActions; ++k) { OutMask[k] = true; }
    const bool fly = Obs[kObsFly] > 0.5f;
    const bool swim = Obs[kObsSwim] > 0.5f;
    OutMask[ActUp] = fly || swim;
    OutMask[ActDown] = fly || swim;
    OutMask[ActDive] = fly;
    OutMask[ActBurst] = (Obs[kObsBurst] > 0.0f) && (Obs[kObsBurstReady] > 0.5f);
    OutMask[kSpareAction] = false;
}

/** policy.sample_np 와 같은 뽑기: 막힌 칸 −1e9 → softmax (double) → 누적합 < u 인 칸 수. 합은 numpy 8 갈래 합 차례. */
inline int SampleFromLogits(const float* Logits, const bool* Mask, double U)
{
    double lg[kNumActions];
    double mx = -std::numeric_limits<double>::infinity();
    for (int k = 0; k < kNumActions; ++k)
    {
        lg[k] = Mask[k] ? static_cast<double>(Logits[k]) : -1e9;
        mx = std::max(mx, lg[k]);
    }
    double pr[kNumActions];
    for (int k = 0; k < kNumActions; ++k) { pr[k] = std::exp(lg[k] - mx); }
    double r8[8];
    for (int k = 0; k < 8; ++k) { r8[k] = pr[k]; }
    for (int k = 8; k < kNumActions; k += 8) { for (int q = 0; q < 8; ++q) { r8[q] += pr[k + q]; } }
    const double tot = ((r8[0] + r8[1]) + (r8[2] + r8[3])) + ((r8[4] + r8[5]) + (r8[6] + r8[7]));
    int cnt = 0;
    double cum = 0.0;
    for (int k = 0; k < kNumActions; ++k)
    {
        cum += pr[k] / tot;
        if (cum < U) { ++cnt; }
    }
    return std::min(cnt, kNumActions - 1);
}

/** 막히지 않은 칸 가운데 가장 큰 로짓 (진단용 — 계약 select 는 확률 뽑기) */
inline int ArgmaxMasked(const float* Logits, const bool* Mask)
{
    int best = ActWatch;
    double bv = -std::numeric_limits<double>::infinity();
    for (int k = 0; k < kNumActions; ++k)
    {
        if (Mask[k] && static_cast<double>(Logits[k]) > bv) { bv = Logits[k]; best = k; }
    }
    return best;
}

/** rule_brain.decide 한 개체판 — 종 이름 없이 감각만 읽는 공통 규칙 두뇌 (잣대 · 두뇌 없는 종). */
inline int RuleDecide(const float* ObsF)
{
    double obs[kObsDim];
    for (int k = 0; k < kObsDim; ++k) { obs[k] = static_cast<double>(ObsF[k]); }
    bool mask[kNumActions];
    MaskFromObs(ObsF, mask);
    const double big = std::log2(1.5) / kRatioLog2Max;
    const double pounceLg = Lg(12.0, kDistRef, kDistMax);
    const double pounceCos = std::cos(30.0 * kDegToRad);
    auto dirOfVector = [](double Lx, double Ly) -> int
    {
        const double ang = std::atan2(Ly, Lx);
        const long long j = static_cast<long long>(std::nearbyint(ang / (kPi / 4.0)));
        return static_cast<int>(((j % 8) + 8) % 8);
    };
    double freeD[kNumDir], foodD[kNumDir];
    for (int j = 0; j < kNumDir; ++j)
    {
        freeD[j] = obs[kDirLo + j * kDirFields + 0];
        foodD[j] = obs[kDirLo + j * kDirFields + 5];
    }
    const double energy = obs[kObsEnergy];
    const bool airborne = obs[kObsAirborne] > 0.5;
    const bool canFly = obs[kObsFly] > 0.5;
    const double meat = obs[kObsDietMeat];
    const double kill = obs[kObsKill] * 4.0;
    const double foodHere = obs[kObsFoodHere] + obs[kObsCarcassHere] * ((meat > 0.2) ? 1.0 : 0.0);
    const double* o = obs + kOtherLo;
    bool bigv[kNumOther], smallv[kNumOther];
    const double lim = (kill > 0.0) ? std::log2(std::max(kill, 1e-6)) / kRatioLog2Max : -std::numeric_limits<double>::infinity();
    bool anyBig = false, anySmall = false;
    for (int n = 0; n < kNumOther; ++n)
    {
        const double* f = o + n * kOtherFields;
        const bool other = (f[OfPresent] > 0.5) && (f[OfSameKin] < 0.5);
        bigv[n] = other && (f[OfSizeRatio] > big) && (f[OfApproach] > 0.05);
        smallv[n] = other && (f[OfMassRatio] <= lim);
        anyBig = anyBig || bigv[n];
        anySmall = anySmall || smallv[n];
    }
    int act = ActWatch;
    bool done = false;
    // 1 도망
    if (anyBig)
    {
        int k = 0;
        while (!bigv[k]) { ++k; }
        const double lx = o[k * kOtherFields + OfX], ly = o[k * kOtherFields + OfY];
        const int j = dirOfVector(-lx, -ly);
        int j2 = 0;
        double bs = -std::numeric_limits<double>::infinity();
        for (int q = 0; q < kNumDir; ++q)
        {
            const int dd = ((((q - j + 4) % 8) + 8) % 8) - 4;
            const double sc = freeD[q] - 0.3 * std::fabs(static_cast<double>(dd));
            if (sc > bs) { bs = sc; j2 = q; }
        }
        act = (canFly && !airborne) ? static_cast<int>(ActUp) : ActFast0 + j2;
        done = true;
    }
    // 2 사냥
    if (!done && kill > 0.0 && energy < 0.7 && anySmall)
    {
        int k = 0;
        double bd = std::numeric_limits<double>::infinity();
        for (int n = 0; n < kNumOther; ++n)
        {
            const double d = smallv[n] ? std::hypot(o[n * kOtherFields + OfX], o[n * kOtherFields + OfY]) : std::numeric_limits<double>::infinity();
            if (d < bd) { bd = d; k = n; }
        }
        const double tx = o[k * kOtherFields + OfX], ty = o[k * kOtherFields + OfY];
        const int j = dirOfVector(tx, ty);
        int a = ActFast0 + j;
        if (airborne) { a = (o[k * kOtherFields + OfHeightDiff] < -0.05) ? static_cast<int>(ActDive) : ActFast0 + j; }
        const double td = std::hypot(tx, ty);
        if (mask[ActBurst] && td <= pounceLg && tx >= pounceCos * td) { a = ActBurst; }
        act = a;
        done = true;
    }
    // 3 먹기
    if (!done && foodHere > 0.05 && energy < 0.95)
    {
        act = airborne ? static_cast<int>(ActDown) : static_cast<int>(ActEat);
        done = true;
    }
    // 4 먹이 쪽
    if (!done)
    {
        double fm = -std::numeric_limits<double>::infinity();
        for (int j = 0; j < kNumDir; ++j) { fm = std::max(fm, foodD[j]); }
        if (fm > 0.02)
        {
            int jb = 0;
            double bv = -std::numeric_limits<double>::infinity();
            for (int j = 0; j < kNumDir; ++j)
            {
                const double sc = foodD[j] * ((freeD[j] > 0.05) ? 1.0 : 0.0);
                if (sc > bv) { bv = sc; jb = j; }
            }
            act = ActSlow0 + jb;
        }
    }
    return mask[act] ? act : static_cast<int>(ActWatch);
}

// --------------------------------------------------------------------------------------------------------------------
// 세계 (world.World, K = 1)
// --------------------------------------------------------------------------------------------------------------------
struct FRules   // = world.Rules (respawn_decisions 는 FWorldConfig::RespawnDecisions)
{
    double BiteConeCos = 0.5, ApproachMinMps = 0.4, CounterConeCos = 0.25, CounterHpMin = 0.35, BiteDamageK = 0.5, CounterCdS = 4.0;
    double WadeSlow = 0.5, SwimClearK = 0.65, HoverM = 0.5, LandSlopeDeg = 49.5, AirClearM = 2.0, DiveContactK = 2.0, BreathS = 20.0;
    double ShelterBiteRadiusM = 0.25, ReserveRefill = 0.25, ReserveDrawBelow = 0.25, CarcassMeatPerKg = 0.6, CarcassLifeS = 300.0;
    double MateEMin = 0.6, BirthEMin = 0.4, BirthCost = 0.3, RainSight = 0.9, SnowSpeed = 0.85;
    double RewardAlive = 0.01, RewardBirth = 10.0, RewardDeath = -10.0;
    int CarcassSlots = 32;
};

struct FRosterEntry { int Species = 0; int Start = 0; int Cap = 0; };

struct FWorldConfig
{
    FMapLayers Map;
    std::vector<FSpecies> Species;
    std::vector<FRosterEntry> Roster;   // 종마다 한 줄 (같은 종 두 줄 거부). 슬롯 = 로스터 차례로 Cap 칸씩
    FRules Rules;
    uint64_t Seed = 1;
    double Rain = 0, Snow = 0, Temp = 0.5;
    bool Respawn = true;                // 학습 세계처럼 죽은 칸을 RespawnDecisions 결정 뒤 되살림 (파이썬 train=True). 끄면 평가 세계(train=False)
    int RespawnDecisions = 50;
    bool DrawWeather = false;           // 참 = 파이썬처럼 날씨를 세계 난수로 뽑음 (대조용). 거짓 = Rain·Snow·Temp
};

struct FEvent
{
    int Kind = 0;      // 0 죽음 · 1 태어남 · 2 물기
    int A = -1, B = -1;   // 죽음: A 죽은 칸 · B 죽인 칸 / 태어남: A 어미 칸 · B 새끼 수 / 물기: A 무는 칸 · B 물린 칸
    int Cause = 0;     // 죽음 ECause · 물기 1 = 반격 받음
    double X = 0, Y = 0;
    int64_t UidA = 0, UidB = 0;
    double Value = 0;  // 물기 피해
};

struct FCarcass { double X = 0, Y = 0, Z = 0, Meat = 0; int Species = -1; };   // Z = 그 칸 땅 높이 (화면용 절대 m)

class FWorld
{
public:
    // ---- 슬롯마다 공개 상태 (읽기 전용으로 쓴다)
    std::vector<uint8_t> Alive, Airborne, Swimming;
    std::vector<int> Sp, Action;
    std::vector<int64_t> Uid;
    std::vector<double> X, Y, Z, Hx, Hy, Speed, E, Hp, AgeDays;
    std::vector<FEvent> Events;   // 마지막 Step 의 사건 (차례대로)

    // ---- 나머지 상태 (대조 시험·화면에서 읽음 — 바깥에서 쓰지 말 것)
    std::vector<double> Vx, Vy, TakeoffLeft, R, Stam, PregLeft, BirthWait, Breath, AttackCd, BurstLeft, ExhaustLeft, Reward, BirthsStep, Gain;
    std::vector<uint8_t> Sex, Pregnant, BurstNow, Done;
    std::vector<int64_t> DeadWait, RespawnWait;
    std::vector<int> CarcWk, CarcKin;
    std::vector<double> CarcX, CarcY, CarcZ, CarcMeat, CarcAge;
    std::map<int, int> Father;
    int64_t NextUid = 1;
    int64_t T = 0;                // 걸음 수 (world.t)
    int64_t Decisions = 0;
    double Level = 0, LevelPrev = 0;
    double Rain = 0, Snow = 0, Temp = 0.5;
    int Mw = 0, Mh = 0;
    double CellM = 1.0;
    std::vector<double> GZ, GBed, GSurf0, GCurX, GCurY, GCover, GFood;   // 먹이 양(바뀜)은 double · 먹이 층: k*cells + c
    std::vector<float> GCap, GRegen, GDry;                               // 읽기만 하는 먹이 층은 float (double 로 넓히면 파이썬 값과 같음)
    std::vector<uint8_t> GWSys, GBlock, GShelter, GCanopy;
    std::vector<FSpecies> Species;
    std::vector<int> CapOf;       // 종 번호 → 로스터 상한 (없으면 0)
    FRules Rules;
    FWaterCycle Water;
    bool bRespawn = true;

    bool Init(const FWorldConfig& Cfg, std::string* Err) { return Init(Cfg, Err, nullptr); }

    /** Inject 가 있으면 그 난수를 쓴다 (대조 시험 — 수명은 부르는 쪽). 없으면 Cfg.Seed 의 PCG32. */
    bool Init(const FWorldConfig& Cfg, std::string* Err, IRandom* Inject)
    {
        if (!Cfg.Map.Check(Err)) { return false; }
        if (Cfg.Species.empty()) { Detail::SetErr(Err, "no species"); return false; }
        Species = Cfg.Species;
        Rules = Cfg.Rules;
        Water = Cfg.Map.Water;
        bRespawn = Cfg.Respawn;
        CapOf.assign(Species.size(), 0);
        int slots = 0;
        for (const FRosterEntry& re : Cfg.Roster)
        {
            if (re.Species < 0 || re.Species >= static_cast<int>(Species.size())) { Detail::SetErr(Err, "roster species index"); return false; }
            if (CapOf[static_cast<size_t>(re.Species)] != 0 || re.Cap <= 0) { Detail::SetErr(Err, "roster: duplicate species or cap <= 0"); return false; }
            CapOf[static_cast<size_t>(re.Species)] = re.Cap;
            slots += re.Cap;
        }
        if (slots <= 0) { Detail::SetErr(Err, "no slots"); return false; }
        Rng = Inject ? Inject : &OwnRng;
        if (!Inject) { OwnRng.Reseed(Cfg.Seed, 0x52100001ull); }
        // 지형 (float32 → double, 파이썬 _build_maps)
        Mw = Cfg.Map.W;
        Mh = Cfg.Map.H;
        CellM = Cfg.Map.CellM;
        NCells = Cfg.Map.Cells();
        auto toD = [](const std::vector<float>& V, std::vector<double>& Dst) { Dst.assign(V.begin(), V.end()); };
        toD(Cfg.Map.GroundZ, GZ);
        toD(Cfg.Map.WaterBedZ, GBed);
        toD(Cfg.Map.WaterSurf0Z, GSurf0);
        toD(Cfg.Map.CurrentX, GCurX);
        toD(Cfg.Map.CurrentY, GCurY);
        toD(Cfg.Map.CoverSight, GCover);
        toD(Cfg.Map.FoodAmount, GFood);
        GCap = Cfg.Map.FoodCap;
        GRegen = Cfg.Map.FoodRegen;
        GDry = Cfg.Map.FoodDry;
        GWSys = Cfg.Map.WaterSys;
        GBlock = Cfg.Map.Block;
        GShelter = Cfg.Map.Shelter;
        GCanopy = Cfg.Map.Canopy;
        MapCache = Cfg.Map;
        bFoodDirty = false;
        ActiveFood.clear();
        bRegrowSparse = false;
        Level = 0.0;
        LevelPrev = 0.0;
        T = 0;
        Decisions = 0;
        // 슬롯
        const size_t n = static_cast<size_t>(slots);
        NSlots = slots;
        auto zd = [n](std::vector<double>& V) { V.assign(n, 0.0); };
        auto zb = [n](std::vector<uint8_t>& V) { V.assign(n, 0); };
        zd(X); zd(Y); zd(Z); zd(Speed); zd(E); zd(Hp); zd(AgeDays); zd(Vx); zd(Vy); zd(TakeoffLeft); zd(R); zd(Stam); zd(PregLeft);
        zd(BirthWait); zd(Breath); zd(AttackCd); zd(BurstLeft); zd(ExhaustLeft); zd(Reward); zd(BirthsStep); zd(Gain); zd(Hy);
        Hx.assign(n, 1.0);
        zb(Alive); zb(Airborne); zb(Swimming); zb(Sex); zb(Pregnant); zb(BurstNow); zb(Done);
        Sp.assign(n, -1);
        Action.assign(n, ActWatch);
        Uid.assign(n, 0);
        DeadWait.assign(n, 0);
        RespawnWait.assign(n, static_cast<int64_t>(Cfg.RespawnDecisions));
        Father.clear();
        NextUid = 1;
        Events.clear();
        int used = 0;
        for (const FRosterEntry& re : Cfg.Roster)
        {
            for (int k = 0; k < re.Cap; ++k) { Sp[static_cast<size_t>(used + k)] = re.Species; }
            const int n0 = std::min(re.Start, re.Cap);
            for (int k = 0; k < n0; ++k) { Spawn(used + k, 0.7, false, 0.0, 0.0); }
            used += re.Cap;
        }
        // 날씨 (파이썬: uniform · random · uniform · random · uniform)
        if (Cfg.DrawWeather)
        {
            const double r0 = Rng->Uniform(0.0, 1.0);
            const double r1 = (Rng->Random() < 0.4) ? 1.0 : 0.0;
            const double s0 = Rng->Uniform(0.0, 1.0);
            const double s1 = (Rng->Random() < 0.15) ? 1.0 : 0.0;
            const double t0 = Rng->Uniform(0.2, 0.8);
            Rain = r0 * r1;
            Snow = s0 * s1;
            Temp = t0;
        }
        else
        {
            Rain = Cfg.Rain;
            Snow = Cfg.Snow;
            Temp = Cfg.Temp;
        }
        const size_t nc = static_cast<size_t>(std::max(Rules.CarcassSlots, 1));
        CarcWk.assign(nc, -1);
        CarcKin.assign(nc, -1);
        CarcX.assign(nc, 0.0);
        CarcY.assign(nc, 0.0);
        CarcZ.assign(nc, 0.0);
        CarcMeat.assign(nc, 0.0);
        CarcAge.assign(nc, 0.0);
        UpdateWater();
        return true;
    }

    int NumSlots() const { return NSlots; }
    int64_t StepCount() const { return T; }
    double WaterLevel() const { return Level; }
    void SetWeather(double InRain, double InSnow, double InTemp) { Rain = InRain; Snow = InSnow; Temp = InTemp; }
    const FSpecies& P(int I) const { return Species[static_cast<size_t>(Sp[static_cast<size_t>(I)])]; }

    /** senses.abs_height — 절대 높이 m (나는 몸 = 땅 + 높이, 헤엄 몸 = z, 땅 몸 = 땅) */
    double DisplayZ(int I) const
    {
        const size_t i = static_cast<size_t>(I);
        const double gz = GZ[Cell(X[i], Y[i])];
        return Airborne[i] ? gz + Z[i] : (Swimming[i] ? Z[i] : gz);
    }

    std::vector<FCarcass> LiveCarcasses() const
    {
        std::vector<FCarcass> out;
        for (size_t k = 0; k < CarcWk.size(); ++k)
        {
            if (CarcWk[k] >= 0 && CarcMeat[k] > 0.0)
            {
                FCarcass c;
                c.X = CarcX[k];
                c.Y = CarcY[k];
                c.Z = GZ[Cell(CarcX[k], CarcY[k])];
                c.Meat = CarcMeat[k];
                c.Species = CarcKin[k];
                out.push_back(c);
            }
        }
        return out;
    }

    /** 먹이 양이 갱신된 지형 (먹이는 Step 뒤 처음 부를 때 한 번 float 로 옮김) */
    const FMapLayers& Map() const
    {
        if (bFoodDirty)
        {
            for (size_t k = 0; k < GFood.size(); ++k) { MapCache.FoodAmount[k] = static_cast<float>(GFood[k]); }
            bFoodDirty = false;
        }
        return MapCache;
    }
    double FoodAt(int Kind, int CellIndex) const { return GFood[static_cast<size_t>(Kind) * NCells + static_cast<size_t>(CellIndex)]; }

    // ---- 지형 질의 (world.cidx · inside · depth_at · surface_at)
    size_t Cell(double Px, double Py) const
    {
        const double fx = std::floor(Px / CellM), fy = std::floor(Py / CellM);
        const long long ix = std::isfinite(fx) ? static_cast<long long>(Clamp(fx, 0.0, static_cast<double>(Mw - 1))) : 0;
        const long long iy = std::isfinite(fy) ? static_cast<long long>(Clamp(fy, 0.0, static_cast<double>(Mh - 1))) : 0;
        return static_cast<size_t>(iy) * static_cast<size_t>(Mw) + static_cast<size_t>(ix);
    }
    bool Inside(double Px, double Py) const { return Px >= 0.0 && Py >= 0.0 && Px < Mw * CellM && Py < Mh * CellM; }
    double DepthAt(size_t C) const { return GWSys[C] ? std::max(GSurf0[C] + Level - GBed[C], 0.0) : 0.0; }
    double SurfaceAt(size_t C) const { return GWSys[C] ? GSurf0[C] + Level : GZ[C]; }
    double Clearance(int I) const { return P(I).RadiusM * Rules.SwimClearK; }
    double EnergyValue(int I) const
    {
        const size_t i = static_cast<size_t>(I);
        const FSpecies& p = P(I);
        return E[i] + R[i] * p.ReserveDays * static_cast<double>(kDaySteps) * p.DrainPerStep;
    }
    bool BurstReady(int I) const
    {
        const size_t i = static_cast<size_t>(I);
        return Alive[i] && P(I).BurstMps > 0.0 && !Airborne[i] && !Swimming[i] && BurstLeft[i] <= 0.0 && ExhaustLeft[i] <= 0.0;
    }

    double SlopeDeg(size_t C) const
    {
        const long long w = Mw;
        const long long ix = static_cast<long long>(C) % w, iy = static_cast<long long>(C) / w;
        const size_t xr = static_cast<size_t>(iy * w + std::min(ix + 1, w - 1));
        const size_t xl = static_cast<size_t>(iy * w + std::max(ix - 1, 0LL));
        const size_t yu = static_cast<size_t>(std::min(iy + 1, static_cast<long long>(Mh) - 1) * w + ix);
        const size_t yd = static_cast<size_t>(std::max(iy - 1, 0LL) * w + ix);
        const double gx = (GZ[xr] - GZ[xl]) / 2.0;
        const double gy = (GZ[yu] - GZ[yd]) / 2.0;
        return std::atan(std::hypot(gx, gy) / CellM) * kRadToDeg;
    }

    /** world._pass_ok — 땅·헤엄 몸이 (x0,y0)→(x1,y1) 로 갈 수 있나 (끝점만) */
    bool PassOk(int I, double X0, double Y0, double X1, double Y1) const
    {
        const FSpecies& p = P(I);
        const size_t c0 = Cell(X0, Y0), c1 = Cell(X1, Y1);
        const bool same = c0 == c1;
        const bool inside = Inside(X1, Y1);
        const double d1 = DepthAt(c1);
        const double clr = Clearance(I);
        const double rise = GZ[c1] - GZ[c0];
        const double dist = std::max(std::hypot(X1 - X0, Y1 - Y0), 1e-6);
        const double runLen = std::max(dist, CellM);
        const bool slopeOk = (rise <= p.StepM) || (std::atan2(rise, runLen) * kRadToDeg <= p.MaxSlopeDeg);
        const bool landOk = !GBlock[c1] && slopeOk && ((d1 <= p.WadeDepthM) || (p.Swim && d1 >= 2.0 * clr));
        const bool waterOk = d1 >= 2.0 * clr;
        const bool ok = p.NeedsWater ? waterOk : landOk;
        return inside && (same || ok);
    }

    bool PlaceOk(int I, double Px, double Py) const
    {
        const FSpecies& p = P(I);
        const size_t c = Cell(Px, Py);
        const double d = DepthAt(c);
        const double clr = Clearance(I);
        const bool ok = Inside(Px, Py) && !GBlock[c];
        const bool waterOk = d >= 2.0 * clr;
        const bool landOk = d <= std::max(p.WadeDepthM, 0.0);
        return ok && (p.NeedsWater ? waterOk : (landOk || (p.Swim && waterOk)));
    }

    /** world._spawn — 빈 칸 i 에 새 개체 (bNear 면 (NearX, NearY) 둘레 0.5~3 m) */
    bool Spawn(int I, double AdultFrac, bool bNear, double NearX, double NearY)
    {
        const size_t i = static_cast<size_t>(I);
        const FSpecies& p = P(I);
        const double wm = Mw * CellM, hm = Mh * CellM;
        double px = 0.0, py = 0.0;
        bool found = false;
        for (int tr = 0; tr < 60; ++tr)
        {
            if (!bNear)
            {
                px = Rng->Uniform(0.5, wm - 0.5);
                py = Rng->Uniform(0.5, hm - 0.5);
            }
            else
            {
                const double a = Rng->Uniform(0.0, 2.0 * kPi);
                const double r = Rng->Uniform(0.5, 3.0);
                px = NearX + r * std::cos(a);
                py = NearY + r * std::sin(a);
            }
            if (PlaceOk(I, px, py)) { found = true; break; }
        }
        if (!found) { Alive[i] = 0; return false; }
        const double ha = Rng->Uniform(0.0, 2.0 * kPi);
        X[i] = px;
        Y[i] = py;
        Hx[i] = std::cos(ha);
        Hy[i] = std::sin(ha);
        Speed[i] = 0.0;
        Vx[i] = 0.0;
        Vy[i] = 0.0;
        const size_t c = Cell(px, py);
        Airborne[i] = 0;
        TakeoffLeft[i] = 0.0;
        if (p.NeedsWater || (p.Swim && DepthAt(c) > p.WadeDepthM))
        {
            const double bed = GBed[c], surf = SurfaceAt(c);
            const double clr = Clearance(I);
            const double frac = (p.SwimDepthFrac != 0.0) ? p.SwimDepthFrac : 0.5;
            Z[i] = bed + clr + (surf - bed - 2.0 * clr) * frac;
            Swimming[i] = 1;
        }
        else
        {
            Z[i] = 0.0;
            Swimming[i] = 0;
        }
        E[i] = Rng->Uniform(0.6, 0.9);
        R[i] = Rng->Uniform(0.2, 0.6);
        Stam[i] = 1.0;
        Hp[i] = 1.0;
        const double mat = std::max(p.MaturityDays, 1e-3);
        const bool adult = Rng->Random() < AdultFrac;
        AgeDays[i] = mat * (adult ? Rng->Uniform(1.0, 3.0) : Rng->Uniform(0.05, 0.9));
        Sex[i] = (Rng->Random() < 0.5) ? 1 : 0;
        PregLeft[i] = 0.0;
        Pregnant[i] = 0;
        BirthWait[i] = 0.0;
        Breath[i] = 1.0;
        AttackCd[i] = 0.0;
        BurstLeft[i] = 0.0;
        ExhaustLeft[i] = 0.0;
        Alive[i] = 1;
        DeadWait[i] = 0;
        Uid[i] = NextUid++;
        return true;
    }

    // ---------------------------------------------------------------------------------------------- 한 결정
    /** world.step — 한 결정(2 걸음). 막힌 행동(종 행동 마스크 밖)은 지켜보기로 바꾼다. */
    void Step(const int* Actions)
    {
        Events.clear();
        const size_t n = static_cast<size_t>(NSlots);
        std::vector<double> e0(n);
        std::vector<uint8_t> was(n);
        for (size_t i = 0; i < n; ++i)
        {
            const int a = Actions ? Actions[i] : static_cast<int>(ActWatch);
            const bool bad = a < 0 || a >= kNumActions || !P(static_cast<int>(i)).AMask[a];
            Action[i] = bad ? static_cast<int>(ActWatch) : a;
            Reward[i] = 0.0;
            Done[i] = 0;
            BirthsStep[i] = 0.0;
            e0[i] = EnergyValue(static_cast<int>(i));
            was[i] = Alive[i];
        }
        for (int s = 0; s < kDecisionSteps; ++s)
        {
            Move();
            Contact();
            Eat();
            Metabolism();
            Life();
            Deaths();
            Regrow();
            ++T;
            UpdateWater();
        }
        for (size_t i = 0; i < n; ++i)
        {
            const double e1 = EnergyValue(static_cast<int>(i));
            const bool died = was[i] && !Alive[i];
            double r = was[i] ? Rules.RewardAlive + (e1 - e0[i]) * (Alive[i] ? 1.0 : 0.0) + Rules.RewardBirth * BirthsStep[i] : 0.0;
            if (died) { r = Rules.RewardDeath; }
            Reward[i] = r;
            Done[i] = died ? 1 : 0;
        }
        if (bRespawn) { RespawnStep(); }
        bFoodDirty = true;
        ++Decisions;
    }

    // ---------------------------------------------------------------------------------------------- 감각 (senses.observe)
    void Observe(std::vector<float>& Obs) const
    {
        const size_t n = static_cast<size_t>(NSlots);
        Obs.assign(n * kObsDim, 0.0f);
        const double tsec = static_cast<double>(T) * kStepS;
        const double light = 0.5 + 0.5 * std::cos(2.0 * kPi * (tsec / (static_cast<double>(kDaySteps) * kStepS)));
        // 슬롯마다 미리
        std::vector<size_t> cs(n);
        std::vector<double> hz(n), sightEff(n);
        std::vector<uint8_t> nearSurf(n), hiding(n);
        for (size_t i = 0; i < n; ++i)
        {
            const FSpecies& p = Species[static_cast<size_t>(Sp[i])];
            cs[i] = Cell(X[i], Y[i]);
            const double gz = GZ[cs[i]];
            hz[i] = Airborne[i] ? gz + Z[i] : (Swimming[i] ? Z[i] : gz);
            nearSurf[i] = Z[i] >= SurfaceAt(cs[i]) - 0.5;
            hiding[i] = (Action[i] == ActHide) && (Speed[i] < 0.2);
            const double nv = p.NightVision;
            sightEff[i] = p.SightM * (nv + (1.0 - nv) * light) * ((Rain > 0.5) ? Rules.RainSight : 1.0);
        }
        static const double rayD[] = {0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 60.0};
        static const double foodD[] = {1.0, 2.5, 5.0, 9.0};
        const double spread[] = {-15.0 * kDegToRad, 0.0 * kDegToRad, 15.0 * kDegToRad};
        const double trend = (Level - LevelPrev) / kStepS;
        std::vector<std::pair<double, int>> visList;
        visList.reserve(n);
        double ob[kObsDim];
        for (size_t i = 0; i < n; ++i)
        {
            if (!Alive[i]) { continue; }
            const int ii = static_cast<int>(i);
            const FSpecies& p = Species[static_cast<size_t>(Sp[i])];
            for (int k = 0; k < kObsDim; ++k) { ob[k] = 0.0; }
            const size_t c = cs[i];
            // ---- 자기 16
            const double mat = std::max(p.MaturityDays, 1e-6);
            const bool adult = AgeDays[i] >= mat;
            const double bed = GBed[c], surf = SurfaceAt(c);
            const double col = std::max(surf - bed, 1e-6);
            ob[0] = Clamp(E[i], 0.0, 1.0);
            ob[1] = Clamp(R[i], 0.0, 1.0);
            ob[2] = Stam[i];
            ob[3] = Clamp(Hp[i], 0.0, 1.0);
            ob[4] = Clamp(AgeDays[i] / (2.0 * mat), 0.0, 1.0);
            ob[5] = (adult && !Pregnant[i] && BirthWait[i] <= 0.0) ? 1.0 : 0.0;
            ob[6] = Pregnant[i] ? 1.0 - Clamp(PregLeft[i] / std::max(p.GestationDays, 1e-6), 0.0, 1.0) : 0.0;
            ob[7] = Lg(Speed[i], 1.0, 25.0);
            ob[8] = Airborne[i] ? Lg(Z[i], 0.5, 60.0) : 0.0;
            ob[9] = Swimming[i] ? Clamp((Z[i] - bed) / col, 0.0, 1.0) : 0.0;
            ob[10] = Swimming[i] ? 1.0 : 0.0;
            ob[11] = GShelter[c] ? 1.0 : 0.0;
            ob[12] = Clamp(Breath[i], 0.0, 1.0);
            ob[13] = Airborne[i] ? 1.0 : 0.0;
            ob[14] = BurstReady(ii) ? 1.0 : 0.0;
            ob[15] = (BurstLeft[i] > 0.0) ? Clamp(BurstLeft[i] / std::max(p.BurstS, 1e-6), 0.0, 1.0)
                                          : -Clamp(ExhaustLeft[i] / std::max(p.BurstExhaustS, 1e-6), 0.0, 1.0);
            // ---- 몸 18
            for (int k = 0; k < kBodyDim; ++k) { ob[kBodyLo + k] = static_cast<double>(p.BodyVec[k]); }
            // ---- 8 방향 × 6
            const bool highAir = Airborne[i] && Z[i] >= Rules.AirClearM;
            const double sight = p.SightM;
            const double smell = std::max(p.SmellM, sight * 0.5);
            double fw[kNumFoods];
            for (int k = 0; k < kNumFoods; ++k) { fw[k] = p.Diet[k]; }
            // 사체 고기도 '그쪽 먹이' 로 (senses.py 11-19): 고기·사체를 먹는 몸, smell 반경 안, 제 종 사체 제외 → 가장 가까운 8 방향 칸
            double carcDir[kNumDir] = {};
            const double meatW = std::max(p.Diet[kDietMeat], p.Diet[kDietCarrion]);
            if (meatW > 0.0)
            {
                for (size_t k = 0; k < CarcWk.size(); ++k)
                {
                    if (CarcWk[k] < 0 || !(CarcMeat[k] > 0.0) || CarcKin[k] == Sp[i]) { continue; }
                    const double ddx = CarcX[k] - X[i], ddy = CarcY[k] - Y[i];
                    if (!(std::hypot(ddx, ddy) <= smell)) { continue; }
                    const double clx = ddx * Hx[i] + ddy * Hy[i];
                    const double cly = -ddx * Hy[i] + ddy * Hx[i];
                    const long long jr = static_cast<long long>(std::nearbyint(std::atan2(cly, clx) / (kPi / 4.0)));
                    carcDir[((jr % kNumDir) + kNumDir) % kNumDir] += CarcMeat[k] * meatW;
                }
            }
            for (int j = 0; j < kNumDir; ++j)
            {
                const double ang = (45.0 * j) * kDegToRad;
                const double ca = std::cos(ang), sa = std::sin(ang);
                const double dx = Hx[i] * ca - Hy[i] * sa, dy = Hx[i] * sa + Hy[i] * ca;
                double freeM = 0.0, coverMax = 0.0;
                bool going = true;
                double px = X[i], py = Y[i];
                for (double d : rayD)
                {
                    const double tx = X[i] + dx * d, ty = Y[i] + dy * d;
                    bool ok = false;
                    if (highAir) { ok = Inside(tx, ty); }
                    else if (Airborne[i]) { ok = Inside(tx, ty) && !GBlock[Cell(tx, ty)]; }
                    else { ok = PassOk(ii, px, py, tx, ty); }
                    going = going && ok && (d <= std::max(sight, 1.0));
                    if (going) { freeM = d; }
                    if (d <= 4.0) { coverMax = std::max(coverMax, GCover[Cell(tx, ty)]); }
                    px = tx;
                    py = ty;
                }
                const double ax = X[i] + dx * 2.0, ay = Y[i] + dy * 2.0;
                const size_t cA = Cell(ax, ay);
                const double rise = GZ[cA] - GZ[c];
                const double dep = DepthAt(cA);
                const double cur = GCurX[cA] * dx + GCurY[cA] * dy;
                double food = 0.0;
                for (double d : foodD)
                {
                    for (double sAng : spread)
                    {
                        const double cs2 = std::cos(sAng), sn2 = std::sin(sAng);
                        const double ex = dx * cs2 - dy * sn2, ey = dx * sn2 + dy * cs2;
                        const double fx = X[i] + ex * d, fy = Y[i] + ey * d;
                        const size_t cf = Cell(fx, fy);
                        if (d <= smell && Inside(fx, fy)) { food += FoodWeighted(cf, fw); }
                        else { food += 0.0; }
                    }
                }
                food += carcDir[j];
                const int base = kDirLo + j * kDirFields;
                ob[base + 0] = Lg(freeM, kDistRef, kDistMax);
                ob[base + 1] = Slg(rise, kHeightRef, kHeightMax);
                ob[base + 2] = Lg(dep, kDepthRef, kDepthMax);
                ob[base + 3] = Slg(cur, kCurRef, kCurMax);
                ob[base + 4] = coverMax;
                ob[base + 5] = food / (food + kFoodRef);
            }
            // ---- 발밑 6
            const double foodHere = FoodWeighted(c, fw);
            const bool eatsMeat = (p.Diet[kDietMeat] + p.Diet[kDietCarrion]) > 0.0;
            double meatHere = 0.0;
            if (eatsMeat)
            {
                for (size_t k = 0; k < CarcWk.size(); ++k)
                {
                    if (CarcWk[k] >= 0 && CarcMeat[k] > 0.0)
                    {
                        const double dd = std::hypot(CarcX[k] - X[i], CarcY[k] - Y[i]);
                        if (dd <= 1.0 + p.RadiusM) { meatHere += CarcMeat[k]; }
                    }
                }
            }
            double shelterD = GShelter[c] ? 0.0 : 60.0;
            for (int j = 0; j < kNumDir; ++j)
            {
                const double ang = (45.0 * j) * kDegToRad;
                const double ca = std::cos(ang), sa = std::sin(ang);
                const double dx = Hx[i] * ca - Hy[i] * sa, dy = Hx[i] * sa + Hy[i] * ca;
                for (double d : rayD)
                {
                    const double tx = X[i] + dx * d, ty = Y[i] + dy * d;
                    const bool hit = GShelter[Cell(tx, ty)] && Inside(tx, ty);
                    if (hit && d < shelterD) { shelterD = d; }
                }
            }
            ob[kHereLo + 0] = foodHere / (foodHere + kFoodRef);
            ob[kHereLo + 1] = meatHere / (meatHere + 5.0);
            ob[kHereLo + 2] = Swimming[i] ? Lg(surf - Z[i], 0.25, 5.0) : 0.0;
            ob[kHereLo + 3] = Swimming[i] ? Lg(Z[i] - bed, 0.25, 5.0) : (Airborne[i] ? Lg(Z[i], 0.5, 60.0) : 0.0);
            ob[kHereLo + 4] = SlopeDeg(c) / 90.0;
            ob[kHereLo + 5] = 1.0 - Lg(shelterD, kDistRef, kDistMax);
            // ---- 다른 동물 8 × 12 · 같은 종 4
            visList.clear();
            int kinCnt = 0;
            double kinX = 0.0, kinY = 0.0, kinSpd = 0.0;
            for (size_t jv = 0; jv < n; ++jv)
            {
                if (jv == i || !Alive[jv]) { continue; }
                const double dxm = X[jv] - X[i], dym = Y[jv] - Y[i];
                const double dist = std::hypot(dxm, dym);
                const double ux = dxm / std::max(dist, 1e-6), uy = dym / std::max(dist, 1e-6);
                const double cosv = Hx[i] * ux + Hy[i] * uy;
                const double rngEff = sightEff[i] * (hiding[jv] ? 0.5 : 1.0);
                if (!(dist <= rngEff) || !(cosv >= p.FovCos)) { continue; }
                const bool cross = Swimming[i] != Swimming[jv];
                const bool waterOk = !cross || (Swimming[jv] ? nearSurf[jv] : nearSurf[i]);
                if (!waterOk) { continue; }
                double visCover = 0.0;
                for (double f : {0.33, 0.66})
                {
                    const double mx = X[i] + dxm * f, my = Y[i] + dym * f;
                    visCover = std::max(visCover, GCover[Cell(mx, my)]);
                }
                if (!((visCover < 0.7) || Airborne[i] || Airborne[jv] || (dist < 2.0))) { continue; }
                visList.push_back(std::make_pair(dist, static_cast<int>(jv)));
                if (Sp[jv] == Sp[i])
                {
                    ++kinCnt;
                    kinX += dxm;
                    kinY += dym;
                    kinSpd += std::hypot(Vx[jv], Vy[jv]);
                }
            }
            std::sort(visList.begin(), visList.end());   // (거리, 번호) — argsort stable 과 같은 차례
            const int nv = std::min(static_cast<int>(visList.size()), kNumOther);
            for (int q = 0; q < nv; ++q)
            {
                const size_t jv = static_cast<size_t>(visList[static_cast<size_t>(q)].second);
                const double dd = visList[static_cast<size_t>(q)].first;
                const double rx = X[jv] - X[i], ry = Y[jv] - Y[i];
                const double lx = (rx * Hx[i] + ry * Hy[i]) / std::max(dd, 1e-6);
                const double ly = (-rx * Hy[i] + ry * Hx[i]) / std::max(dd, 1e-6);
                const double lgd = Lg(dd, kDistRef, kDistMax);
                const double rvx = Vx[jv] - Vx[i], rvy = Vy[jv] - Vy[i];
                const double approach = -(rvx * rx + rvy * ry) / std::max(dd, 1e-6);
                const double tmx = -rx / std::max(dd, 1e-6), tmy = -ry / std::max(dd, 1e-6);
                const double facing = Hx[jv] * tmx + Hy[jv] * tmy;
                const FSpecies& pj = Species[static_cast<size_t>(Sp[jv])];
                double* f = ob + kOtherLo + q * kOtherFields;
                f[OfPresent] = 1.0;
                f[OfX] = lgd * lx;
                f[OfY] = lgd * ly;
                f[OfApproach] = Slg(approach, kSpeedRef, kSpeedMax);
                f[OfSpeed] = Lg(std::hypot(Vx[jv], Vy[jv]), kSpeedRef, kSpeedMax);
                f[OfSizeRatio] = Ratio(pj.RadiusM, p.RadiusM);
                f[OfMassRatio] = Ratio(pj.MassKg, p.MassKg);
                f[OfInWater] = Swimming[jv] ? 1.0 : 0.0;
                f[OfInAir] = Airborne[jv] ? 1.0 : 0.0;
                f[OfHeightDiff] = Slg(hz[jv] - hz[i], kHeightRef, kHeightMax);
                f[OfSameKin] = (Sp[jv] == Sp[i]) ? 1.0 : 0.0;
                f[OfFacing] = facing;
            }
            {
                const double cnt = static_cast<double>(kinCnt);
                const double cxk = kinX / std::max(cnt, 1.0), cyk = kinY / std::max(cnt, 1.0);
                const double cd = std::hypot(cxk, cyk);
                const double kl = Lg(cd, kDistRef, kDistMax);
                ob[kKinLo + 0] = Clamp(cnt / kKinCountMax, 0.0, 1.0);
                ob[kKinLo + 1] = kl * (cxk * Hx[i] + cyk * Hy[i]) / std::max(cd, 1e-6);
                ob[kKinLo + 2] = kl * (-cxk * Hy[i] + cyk * Hx[i]) / std::max(cd, 1e-6);
                ob[kKinLo + 3] = Lg(kinSpd / std::max(cnt, 1.0), 1.0, 25.0);
            }
            // ---- 환경 6
            ob[kEnvLo + 0] = light;
            ob[kEnvLo + 1] = Rain;
            ob[kEnvLo + 2] = Snow;
            ob[kEnvLo + 3] = Temp;
            ob[kEnvLo + 4] = Slg(trend, 0.005, 0.1);
            ob[kEnvLo + 5] = 0.0;
            float* out = Obs.data() + i * kObsDim;
            for (int k = 0; k < kObsDim; ++k) { out[k] = p.OMask[k] ? static_cast<float>(Clamp(ob[k], -1.0, 1.0)) : 0.0f; }
        }
    }

private:
    FPcg32Random OwnRng;
    IRandom* Rng = nullptr;
    int NSlots = 0;
    size_t NCells = 0;
    mutable FMapLayers MapCache;
    mutable bool bFoodDirty = false;
    std::vector<uint32_t> ActiveFood;
    bool bRegrowSparse = false;

    double FoodWeighted(size_t C, const double* Fw) const
    {
        double s = 0.0;
        for (int k = 0; k < kNumFoods; ++k) { s += GFood[static_cast<size_t>(k) * NCells + C] * Fw[k]; }
        return s;
    }

    void UpdateWater()
    {
        LevelPrev = Level;
        Level = Water.Offset(static_cast<double>(T) * kStepS, Rain);
    }

    // ---------------------------------------------------------------------------------------------- 이동 (world._move · _vertical)
    void Move()
    {
        const size_t n = static_cast<size_t>(NSlots);
        for (size_t i = 0; i < n; ++i)
        {
            const int ii = static_cast<int>(i);
            const FSpecies& p = P(ii);
            const int a = Action[i];
            int j = -1, gait = 0;
            DirOfAction(a, j, gait);
            const bool al = Alive[i] != 0;
            const size_t c0 = Cell(X[i], Y[i]);
            const double depth0 = DepthAt(c0);
            const bool inDeep = depth0 > std::max(p.WadeDepthM, 0.0);
            const bool swimNow = al && p.Swim && (inDeep || p.NeedsWater);
            const bool flying = al && Airborne[i];
            const double wadeF = 1.0 - Rules.WadeSlow * Clamp(depth0 / std::max(p.WadeDepthM, 1e-6), 0.0, 1.0) * ((depth0 > 0.0) ? 1.0 : 0.0);
            const double groundV = (gait == 2 ? p.RunMps : (gait == 1 ? p.WalkMps : 0.0)) * (swimNow ? 1.0 : wadeF);
            const double swimV = gait == 2 ? p.SwimFastMps : (gait == 1 ? p.SwimMps : 0.0);
            const bool high = Z[i] >= 0.6 * p.CruiseHeightM;
            double flyV = gait == 2 ? (high ? p.CruiseMps : 1.3 * p.FlyMps) : (gait == 1 ? p.FlyMps : 0.0);
            if (a == ActDive) { flyV = p.FlyMps; }
            const bool stamLock = Stam[i] <= 0.0;
            double vT = flying ? flyV : (swimNow ? swimV : groundV);
            if (stamLock && gait == 2) { vT = flying ? p.FlyMps : (swimNow ? p.SwimMps : p.WalkMps); }
            const bool start = (a == ActBurst) && BurstReady(ii);
            if (start) { BurstLeft[i] = p.BurstS; }
            const bool bursting = al && BurstLeft[i] > 1e-9 && !swimNow && !flying;
            BurstNow[i] = bursting ? 1 : 0;
            if (bursting) { vT = p.BurstMps * wadeF; }
            if (al && ExhaustLeft[i] > 1e-9 && !bursting) { vT = std::min(vT, p.BurstExhaustMps); }
            vT = vT * (0.5 + 0.5 * Hp[i]) * ((Snow > 0.5) ? Rules.SnowSpeed : 1.0) * (al ? 1.0 : 0.0);
            // 원하는 방향
            const bool moving = j >= 0;
            double ca = 0.0, sa = 0.0;
            Dir8(std::max(j, 0), ca, sa);
            const double dx = moving ? Hx[i] * ca - Hy[i] * sa : Hx[i];
            const double dy = moving ? Hx[i] * sa + Hy[i] * ca : Hy[i];
            // 회전 한계
            const double curAng = std::atan2(Hy[i], Hx[i]);
            const double want = std::atan2(dy, dx);
            const double dang = NpRemainder(want - curAng + kPi, 2.0 * kPi) - kPi;
            const double spd = std::max(Speed[i], 0.1);
            const double maxTurn = std::min(p.TurnDps * kDegToRad, p.LatAccelMps2 / spd) * kStepS;
            const double turn = Clamp(dang, -maxTurn, maxTurn) * (moving ? 1.0 : 0.0);
            const double ang = curAng + turn;
            Hx[i] = std::cos(ang);
            Hy[i] = std::sin(ang);
            // 가속 한계
            const double dv = Clamp(vT - Speed[i], -p.AccelMps2 * kStepS * 2.0, p.AccelMps2 * kStepS);
            Speed[i] = std::max(Speed[i] + dv, 0.0) * (al ? 1.0 : 0.0);
            const double stepM = Speed[i] * kStepS;
            double nx = X[i] + Hx[i] * stepM;
            double ny = Y[i] + Hy[i] * stepM;
            if (swimNow)
            {
                nx = nx + GCurX[c0] * kStepS;
                ny = ny + GCurY[c0] * kStepS;
            }
            const bool freeAir = flying && Z[i] >= Rules.AirClearM;
            const bool lowAir = flying && !freeAir;
            const double x0 = X[i], y0 = Y[i];
            auto canGo = [&](double Tx, double Ty) -> bool
            {
                if (freeAir) { return true; }
                if (lowAir) { return Inside(Tx, Ty) && !GBlock[Cell(Tx, Ty)]; }
                return PassOk(ii, x0, y0, Tx, Ty);
            };
            const bool ok = canGo(nx, ny);
            const bool okx = canGo(nx, y0);
            const bool oky = canGo(x0, ny);
            double fx = ok ? nx : (okx ? nx : x0);
            double fy = ok ? ny : ((!okx && oky) ? ny : y0);
            if (!ok && !okx && !oky) { Speed[i] = 0.0; }
            const double wm = Mw * CellM, hm = Mh * CellM;
            fx = Clamp(fx, 0.01, wm - 0.01);
            fy = Clamp(fy, 0.01, hm - 0.01);
            Vx[i] = (fx - x0) / kStepS * (al ? 1.0 : 0.0);
            Vy[i] = (fy - y0) / kStepS * (al ? 1.0 : 0.0);
            if (al)
            {
                X[i] = fx;
                Y[i] = fy;
            }
            // 덮치기·지침 시계
            const bool had = BurstLeft[i] > 1e-9;
            if (had && bursting) { BurstLeft[i] = BurstLeft[i] - kStepS; }
            else if (had) { BurstLeft[i] = 0.0; }
            const bool ended = had && BurstLeft[i] <= 1e-9;
            if (ended) { BurstLeft[i] = 0.0; }
            const double ex = std::max(ExhaustLeft[i] - kStepS, 0.0);
            ExhaustLeft[i] = ended ? p.BurstExhaustS : ((ex <= 1e-9) ? 0.0 : ex);
        }
        Vertical();
    }

    void Vertical()
    {
        const size_t n = static_cast<size_t>(NSlots);
        const double dt = kStepS;
        for (size_t i = 0; i < n; ++i)
        {
            const int ii = static_cast<int>(i);
            const FSpecies& p = P(ii);
            const int a = Action[i];
            const bool al = Alive[i] != 0;
            const size_t c = Cell(X[i], Y[i]);
            // 나는 몸
            const bool fly = al && p.Fly;
            const bool landed = fly && !Airborne[i];
            const bool canTakeoff = landed && a == ActUp && !GCanopy[c] && Stam[i] > 0.05;
            if (canTakeoff) { Airborne[i] = 1; }
            TakeoffLeft[i] = canTakeoff ? p.TakeoffS : std::max(TakeoffLeft[i] - dt, 0.0);
            const bool air = fly && Airborne[i];
            const double climb = (TakeoffLeft[i] > 0.0) ? std::max(p.CruiseHeightM, 1.0) / std::max(p.TakeoffS, 0.1) * 0.3 : 0.65 * p.FlyMps;
            double dz = (a == ActUp) ? climb : ((a == ActDown) ? -0.65 * p.FlyMps : ((a == ActDive) ? -p.DiveMps : 0.0));
            if (TakeoffLeft[i] > 0.0) { dz = std::max(dz, climb); }
            double zNew = Clamp(Z[i] + dz * dt, 0.0, std::max(p.CeilingM, 1.0));
            const double slopeHere = SlopeDeg(c);
            const bool canLand = (!GWSys[c] || DepthAt(c) <= 0.0) && (slopeHere <= Rules.LandSlopeDeg) && !GCanopy[c];
            if (!canLand) { zNew = std::max(zNew, Rules.HoverM); }
            const bool touch = air && zNew <= 0.0 && TakeoffLeft[i] <= 0.0;
            const bool landNow = touch && canLand;
            if (air) { Z[i] = zNew; }
            if (landNow)
            {
                Airborne[i] = 0;
                Z[i] = 0.0;
            }
            // 헤엄 몸
            const double depth = DepthAt(c);
            const bool sw = al && p.Swim && ((depth > std::max(p.WadeDepthM, 0.0)) || p.NeedsWater);
            const bool newly = sw && !Swimming[i];
            Swimming[i] = sw ? 1 : 0;
            const double bed = GBed[c], surf = SurfaceAt(c);
            const double clr = Clearance(ii);
            const double lo = bed + clr, hi = std::max(surf - clr, bed + clr);
            const double dzs = (a == ActUp) ? 0.5 * p.SwimMps : ((a == ActDown) ? -0.5 * p.SwimMps : 0.0);
            const double zs = newly ? (lo + hi) / 2.0 : Z[i];
            if (sw) { Z[i] = Clamp(zs + dzs * dt, lo, hi); }
            if (al && !sw && !(fly && Airborne[i])) { Z[i] = 0.0; }
        }
    }

    // ---------------------------------------------------------------------------------------------- 접촉 (world._contact)
    void Contact()
    {
        const int sl = NSlots;
        const size_t n = static_cast<size_t>(sl);
        std::vector<double> px(n), py(n);
        std::vector<int> med(n);
        std::vector<uint8_t> sheltered(n);
        for (size_t i = 0; i < n; ++i)
        {
            px[i] = X[i] - Vx[i] * kStepS;
            py[i] = Y[i] - Vy[i] * kStepS;
            med[i] = Airborne[i] ? 2 : (Swimming[i] ? 1 : 0);
            sheltered[i] = (GShelter[Cell(X[i], Y[i])] && !Airborne[i]) ? 1 : 0;
        }
        std::vector<int> target(n, -1);
        bool any = false;
        for (size_t i = 0; i < n; ++i)
        {
            if (!Alive[i]) { continue; }
            const FSpecies& pi = P(static_cast<int>(i));
            if (!(pi.KillMassRatio > 0.0) || !(AttackCd[i] <= 0.0)) { continue; }
            const bool smallI = pi.RadiusM <= Rules.ShelterBiteRadiusM;
            double best = std::numeric_limits<double>::infinity();
            int bj = -1;
            for (size_t jv = 0; jv < n; ++jv)
            {
                if (!Alive[jv] || Sp[jv] == Sp[i]) { continue; }
                const FSpecies& pj = P(static_cast<int>(jv));
                if (!(pj.MassKg <= pi.MassKg * pi.KillMassRatio)) { continue; }
                const double dx1 = X[jv] - X[i], dy1 = Y[jv] - Y[i];
                const double dx0 = px[jv] - px[i], dy0 = py[jv] - py[i];
                const double ddx = dx1 - dx0, ddy = dy1 - dy0;
                const double tc = Clamp(-(dx0 * ddx + dy0 * ddy) / std::max(ddx * ddx + ddy * ddy, 1e-12), 0.0, 1.0);
                const double dist = std::hypot(dx0 + tc * ddx, dy0 + tc * ddy);
                if (!(dist <= pi.ReachM + pj.RadiusM)) { continue; }
                const bool mid = tc < 1.0 - 1e-9;
                const double dx = mid ? dx0 : dx1, dy = mid ? dy0 : dy1;
                const double dd = std::hypot(dx, dy);
                const double cosf = (Hx[i] * dx + Hy[i] * dy) / std::max(dd, 1e-6);
                const double appr = (Vx[i] * dx + Vy[i] * dy) / std::max(dd, 1e-6);
                if (!(cosf >= Rules.BiteConeCos) || !(appr > Rules.ApproachMinMps)) { continue; }
                const bool diveTouch = med[i] == 2 && Z[i] <= pi.RadiusM * Rules.DiveContactK && med[jv] != 2;
                const bool sameMed = (med[i] == med[jv]) || diveTouch;
                if (!sameMed) { continue; }
                if (sheltered[jv] && !smallI) { continue; }
                if (dist < best) { best = dist; bj = static_cast<int>(jv); }
            }
            if (bj >= 0) { target[i] = bj; any = true; }
        }
        if (any)
        {
            std::vector<int> order;
            Rng->Permutation(sl, order);
            std::vector<uint8_t> taken(n, 0);
            for (int oi : order)
            {
                const size_t gi = static_cast<size_t>(oi);
                if (target[gi] < 0) { continue; }
                const size_t gj = static_cast<size_t>(target[gi]);
                if (taken[gj] || !Alive[gj]) { continue; }
                taken[gj] = 1;
                const FSpecies& pi = P(static_cast<int>(gi));
                const FSpecies& pj = P(static_cast<int>(gj));
                AttackCd[gi] = pi.AttackCdS;
                if (BurstLeft[gi] > 0.0)
                {
                    BurstLeft[gi] = 0.0;
                    ExhaustLeft[gi] = pi.BurstExhaustS;
                }
                double dmg = Clamp(Rules.BiteDamageK * pi.MassKg * pi.KillMassRatio / pj.MassKg, 0.2, 1.0);
                const double bx = X[gi] - X[gj], by = Y[gi] - Y[gj];
                const double bd = std::max(std::hypot(bx, by), 1e-6);
                const bool front = (Hx[gj] * bx + Hy[gj] * by) / bd >= Rules.CounterConeCos;
                const bool countered = pj.Defense > 0.0 && front && Hp[gj] >= Rules.CounterHpMin && bd <= pj.CounterReachM + pi.RadiusM;
                if (countered)
                {
                    Hp[gi] -= pj.Defense / 100.0;
                    AttackCd[gi] = std::max(AttackCd[gi], Rules.CounterCdS);
                    dmg *= 0.5;
                }
                Hp[gj] -= dmg;
                FEvent ev;
                ev.Kind = EvBite;
                ev.A = static_cast<int>(gi);
                ev.B = static_cast<int>(gj);
                ev.Cause = countered ? 1 : 0;
                ev.X = X[gj];
                ev.Y = Y[gj];
                ev.UidA = Uid[gi];
                ev.UidB = Uid[gj];
                ev.Value = dmg;
                Events.push_back(ev);
                if (Hp[gj] <= 0.0) { Kill(static_cast<int>(gj), CauseBitten, static_cast<int>(gi)); }
                if (Hp[gi] <= 0.0) { Kill(static_cast<int>(gi), CauseCounter, static_cast<int>(gj)); }
            }
        }
        for (size_t i = 0; i < n; ++i) { AttackCd[i] = std::max(AttackCd[i] - kStepS, 0.0); }
    }

    // ---------------------------------------------------------------------------------------------- 먹기 · 대사 (world._eat · _metabolism)
    void Eat()
    {
        const size_t n = static_cast<size_t>(NSlots);
        std::vector<int> idx;
        for (size_t i = 0; i < n; ++i) { if (Alive[i] && Action[i] == ActEat) { idx.push_back(static_cast<int>(i)); } }
        if (idx.empty()) { return; }
        const size_t m = idx.size();
        std::vector<size_t> cIdx(m), key(m);
        std::vector<double> want(m), demand(m), gain(m, 0.0), bestScore(m);
        std::vector<int> best(m);
        std::vector<uint8_t> has(m);
        for (size_t q = 0; q < m; ++q)
        {
            const int i = idx[q];
            const size_t iu = static_cast<size_t>(i);
            const FSpecies& p = P(i);
            const size_t c = Cell(X[iu], Y[iu]);
            cIdx[q] = c;
            want[q] = p.RatePerS * kStepS;
            const bool inWater = Swimming[iu] != 0;
            const bool nearSurface = Z[iu] >= SurfaceAt(c) - 2.0 * Clearance(i);
            const bool onLand = !inWater && !Airborne[iu];
            int bk = 0;
            double bv = -std::numeric_limits<double>::infinity();
            for (int k = 0; k < kNumFoods; ++k)
            {
                bool reach = onLand;
                if (k == FoodAquatic) { reach = inWater; }
                else if (k == FoodDrift) { reach = inWater && nearSurface; }
                else if (k == FoodInsects) { reach = onLand || inWater; }
                const double avail = GFood[static_cast<size_t>(k) * NCells + c] * (reach ? 1.0 : 0.0);
                const double sc = avail * p.Diet[k];
                if (sc > bv) { bv = sc; bk = k; }
            }
            best[q] = bk;
            bestScore[q] = bv;
            has[q] = bv > 1e-6;
            demand[q] = has[q] ? want[q] : 0.0;
            key[q] = static_cast<size_t>(bk) * NCells + c;
        }
        // 칸마다 몫 나누기 (np.unique · bincount)
        std::map<size_t, double> tot;
        for (size_t q = 0; q < m; ++q) { tot[key[q]] += demand[q]; }
        std::map<size_t, double> frac;
        for (const auto& kv : tot)
        {
            const double food = GFood[kv.first];
            const double takenU = std::min(kv.second, food);
            frac[kv.first] = (kv.second > 0.0) ? takenU / std::max(kv.second, 1e-12) : 0.0;
            GFood[kv.first] -= takenU;
        }
        for (size_t q = 0; q < m; ++q)
        {
            const FSpecies& p = P(idx[q]);
            const double got = demand[q] * frac[key[q]];
            gain[q] = got * p.EnergyPerUnit * p.Diet[best[q]];
        }
        // 고기: 가까운 사체 (1 m + 반지름), 고기·사체를 먹는 몸
        bool anyCarc = false;
        for (int w : CarcWk) { if (w >= 0) { anyCarc = true; break; } }
        bool anyMeat = false;
        for (size_t q = 0; q < m; ++q) { const FSpecies& p = P(idx[q]); if (p.Diet[kDietCarrion] + p.Diet[kDietMeat] > 0.0) { anyMeat = true; break; } }
        if (anyCarc && anyMeat)
        {
            for (size_t q = 0; q < m; ++q)
            {
                const int i = idx[q];
                const size_t iu = static_cast<size_t>(i);
                const FSpecies& p = P(i);
                const double meatW = p.Diet[kDietCarrion] + p.Diet[kDietMeat];
                if (meatW <= 0.0 || (has[q] && bestScore[q] > 0.0)) { continue; }
                int ci = -1;
                double bd = std::numeric_limits<double>::infinity();
                for (size_t k = 0; k < CarcWk.size(); ++k)
                {
                    if (CarcWk[k] >= 0 && CarcMeat[k] > 0.0 && CarcKin[k] != Sp[iu])
                    {
                        const double dd = std::hypot(CarcX[k] - X[iu], CarcY[k] - Y[iu]);
                        if (dd < bd) { bd = dd; ci = static_cast<int>(k); }
                    }
                }
                if (ci < 0 || bd > 1.0 + p.RadiusM) { continue; }
                const size_t cu = static_cast<size_t>(ci);
                const double eat = std::min(want[q] * 4.0, CarcMeat[cu]);
                CarcMeat[cu] -= eat;
                gain[q] += eat * p.EnergyPerUnit * std::max(p.Diet[kDietCarrion], p.Diet[kDietMeat]);
            }
        }
        for (size_t q = 0; q < m; ++q) { Gain[static_cast<size_t>(idx[q])] = gain[q]; }
    }

    void Metabolism()
    {
        const size_t n = static_cast<size_t>(NSlots);
        for (size_t i = 0; i < n; ++i)
        {
            const int ii = static_cast<int>(i);
            const FSpecies& p = P(ii);
            const bool al = Alive[i] != 0;
            const double gain = Gain[i];
            Gain[i] = 0.0;
            int j = -1, gait = 0;
            DirOfAction(Action[i], j, gait);
            const bool fast = gait == 2 || Action[i] == ActDive || BurstNow[i];
            double mult = fast ? p.RunCost : 1.0;
            if (Swimming[i]) { mult = mult * p.SwimCost; }
            if (Airborne[i]) { mult = mult * p.FlyCost; }
            double e = E[i] - p.DrainPerStep * mult + gain;
            const double refill = (E[i] >= 0.7) ? Rules.ReserveRefill * gain : 0.0;
            const double capE = std::max(p.ReserveDays * static_cast<double>(kDaySteps) * p.DrainPerStep, 1e-9);
            e = e - refill;
            R[i] = Clamp(R[i] + refill / capE, 0.0, 1.0);
            const double need = std::max(Rules.ReserveDrawBelow - e, 0.0);
            const double draw = std::min(need, R[i] * capE);
            e = e + draw;
            R[i] = Clamp(R[i] - draw / capE, 0.0, 1.0);
            if (al) { E[i] = std::min(e, 1.0); }
            const bool use = fast || (Airborne[i] && Action[i] == ActUp);
            Stam[i] = use ? Stam[i] - kStepS / std::max(p.StaminaS, 1e-3) : Stam[i] + kStepS / std::max(p.StaminaRecoverS, 1e-3);
            Stam[i] = Clamp(Stam[i], 0.0, 1.0);
            if (al) { Hp[i] = std::min(Hp[i] + 0.02 * kStepS / 10.0, 1.0); }
            const size_t c = Cell(X[i], Y[i]);
            const bool shortW = p.NeedsWater && DepthAt(c) < 2.0 * Clearance(ii);
            Breath[i] = shortW ? Breath[i] - kStepS / Rules.BreathS : std::min(Breath[i] + kStepS / Rules.BreathS, 1.0);
            if (al) { AgeDays[i] = AgeDays[i] + 1.0 / static_cast<double>(kDaySteps); }
        }
    }

    // ---------------------------------------------------------------------------------------------- 생애 (world._life)
    void Life()
    {
        const size_t n = static_cast<size_t>(NSlots);
        const double day = 1.0 / static_cast<double>(kDaySteps);
        std::vector<uint8_t> adult(n), fem(n), male(n);
        bool anyFem = false;
        for (size_t i = 0; i < n; ++i)
        {
            adult[i] = Alive[i] && AgeDays[i] >= P(static_cast<int>(i)).MaturityDays;
            BirthWait[i] = std::max(BirthWait[i] - day, 0.0);
        }
        for (size_t i = 0; i < n; ++i)
        {
            fem[i] = adult[i] && !Sex[i] && PregLeft[i] <= 0.0 && BirthWait[i] <= 0.0 && E[i] >= Rules.MateEMin;
            anyFem = anyFem || fem[i];
        }
        if (anyFem)
        {
            for (size_t i = 0; i < n; ++i) { male[i] = adult[i] && Sex[i] && E[i] >= Rules.MateEMin; }
            for (size_t i = 0; i < n; ++i)
            {
                if (!fem[i]) { continue; }
                int cm = -1;
                double bd = std::numeric_limits<double>::infinity();
                for (size_t k = 0; k < n; ++k)
                {
                    if (male[k] && Sp[k] == Sp[i])
                    {
                        const double d = std::hypot(X[k] - X[i], Y[k] - Y[i]);
                        if (d < bd) { bd = d; cm = static_cast<int>(k); }
                    }
                }
                if (cm < 0) { continue; }
                const FSpecies& p = P(static_cast<int>(i));
                if (bd <= p.RadiusM + P(cm).RadiusM + 1.0)
                {
                    Pregnant[i] = 1;
                    PregLeft[i] = std::max(p.GestationDays, day);
                    Father[static_cast<int>(i)] = cm;
                }
            }
        }
        std::vector<uint8_t> ready(n, 0);
        for (size_t i = 0; i < n; ++i)
        {
            PregLeft[i] = Pregnant[i] ? PregLeft[i] - day : 0.0;
            ready[i] = Alive[i] && Pregnant[i] && PregLeft[i] <= 0.0;
            if (ready[i]) { Pregnant[i] = 0; }
        }
        for (size_t i = 0; i < n; ++i)
        {
            if (!ready[i]) { continue; }
            const int ii = static_cast<int>(i);
            if (E[i] < Rules.BirthEMin) { Father.erase(ii); continue; }
            const int si = Sp[i];
            std::vector<int> freeSlots;
            int nAlive = 0;
            for (size_t k = 0; k < n; ++k)
            {
                if (Sp[k] != si) { continue; }
                if (Alive[k]) { ++nAlive; }
                else if (DeadWait[k] == 0) { freeSlots.push_back(static_cast<int>(k)); }
            }
            const FSpecies& p = P(ii);
            const int litter = std::max(1, static_cast<int>(std::nearbyint(p.Litter)));
            const int room = std::max(0, CapOf[static_cast<size_t>(si)] - nAlive);
            const int lim = std::min(std::min(litter, room), static_cast<int>(freeSlots.size()));
            int born = 0;
            for (int q = 0; q < lim; ++q)
            {
                const int f = freeSlots[static_cast<size_t>(q)];
                if (Spawn(f, 0.0, true, X[i], Y[i]))
                {
                    AgeDays[static_cast<size_t>(f)] = 0.0;
                    E[static_cast<size_t>(f)] = 0.6;
                    ++born;
                }
            }
            if (born)
            {
                E[i] -= Rules.BirthCost;
                BirthsStep[i] += born;
                const auto it = Father.find(ii);
                if (it != Father.end())
                {
                    const int fa = it->second;
                    Father.erase(it);
                    if (Alive[static_cast<size_t>(fa)]) { BirthsStep[static_cast<size_t>(fa)] += born; }
                }
                BirthWait[i] = std::max(p.GestationDays, 0.1);
                FEvent ev;
                ev.Kind = EvBirth;
                ev.A = ii;
                ev.B = born;
                ev.X = X[i];
                ev.Y = Y[i];
                ev.UidA = Uid[i];
                Events.push_back(ev);
            }
        }
    }

    // ---------------------------------------------------------------------------------------------- 죽음 · 사체 · 먹이 · 되살리기
    void Kill(int I, int Cause, int Killer)
    {
        const size_t i = static_cast<size_t>(I);
        if (!Alive[i]) { return; }
        Alive[i] = 0;
        Pregnant[i] = 0;
        Father.erase(I);
        FEvent ev;
        ev.Kind = EvDeath;
        ev.A = I;
        ev.B = Killer;
        ev.Cause = Cause;
        ev.X = X[i];
        ev.Y = Y[i];
        ev.UidA = Uid[i];
        ev.UidB = (Killer >= 0) ? Uid[static_cast<size_t>(Killer)] : 0;
        Events.push_back(ev);
        size_t ci = CarcWk.size();
        for (size_t k = 0; k < CarcWk.size(); ++k) { if (CarcMeat[k] <= 0.0) { ci = k; break; } }
        if (ci == CarcWk.size())
        {
            ci = 0;
            for (size_t k = 1; k < CarcWk.size(); ++k) { if (CarcAge[k] > CarcAge[ci]) { ci = k; } }
        }
        CarcWk[ci] = 0;
        CarcX[ci] = X[i];
        CarcY[ci] = Y[i];
        CarcZ[ci] = 0.0;
        CarcMeat[ci] = P(I).MassKg * Rules.CarcassMeatPerKg;
        CarcAge[ci] = 0.0;
        CarcKin[ci] = Sp[i];
        DeadWait[i] = RespawnWait[i];
    }

    void Deaths()
    {
        const size_t n = static_cast<size_t>(NSlots);
        for (size_t i = 0; i < n; ++i) { if (Alive[i] && E[i] <= 0.0 && R[i] <= 0.0) { Kill(static_cast<int>(i), CauseStarved, -1); } }
        for (size_t i = 0; i < n; ++i) { if (Alive[i] && Breath[i] <= 0.0) { Kill(static_cast<int>(i), CauseOutOfWater, -1); } }
        for (size_t i = 0; i < n; ++i) { if (Alive[i] && Hp[i] <= 0.0) { Kill(static_cast<int>(i), CauseWounds, -1); } }
    }

    void Regrow()
    {
        const double dt = kStepS;
        if (!bRegrowSparse)
        {
            // 첫 번은 모든 칸. 용량 0 칸은 그 뒤 늘 정확히 0 (min(max(x, 0), 0) — 먹기도 0 만 뺌) 이라 다음부터는 용량 있는 칸만 (값 같음)
            ActiveFood.clear();
            for (size_t k = 0; k < GFood.size(); ++k)
            {
                GFood[k] = std::min(std::max(GFood[k] + (static_cast<double>(GRegen[k]) - static_cast<double>(GDry[k])) * dt, 0.0), static_cast<double>(GCap[k]));
                if (!(GCap[k] == 0.0f)) { ActiveFood.push_back(static_cast<uint32_t>(k)); }
            }
            bRegrowSparse = true;
        }
        else
        {
            for (uint32_t k : ActiveFood)
            {
                GFood[k] = std::min(std::max(GFood[k] + (static_cast<double>(GRegen[k]) - static_cast<double>(GDry[k])) * dt, 0.0), static_cast<double>(GCap[k]));
            }
        }
        for (size_t k = 0; k < CarcAge.size(); ++k)
        {
            CarcAge[k] += dt;
            if (CarcAge[k] > Rules.CarcassLifeS) { CarcMeat[k] = 0.0; }
        }
    }

    void RespawnStep()
    {
        const size_t n = static_cast<size_t>(NSlots);
        for (size_t i = 0; i < n; ++i) { if (!Alive[i] && DeadWait[i] > 0) { DeadWait[i] -= 1; } }
        for (size_t i = 0; i < n; ++i)
        {
            if (Alive[i] || DeadWait[i] != 0 || Uid[i] <= 0) { continue; }
            int nAlive = 0;
            for (size_t k = 0; k < n; ++k) { if (Alive[k] && Sp[k] == Sp[i]) { ++nAlive; } }
            if (nAlive < CapOf[static_cast<size_t>(Sp[i])]) { Spawn(static_cast<int>(i), 0.7, false, 0.0, 0.0); }
        }
    }
};

/** 결정마다 행동 고르기: 두뇌가 있는 종 = 확률 뽑기 (U = HashUnit(Seed, uid, Decision)), 없는 종 = 공통 규칙 두뇌. 죽은 칸 = 지켜보기. */
inline void DecideActions(const FWorld& W, const std::vector<const FBrain*>& BrainBySpecies, const std::vector<float>& Obs, uint64_t Seed,
                          int64_t Decision, std::vector<int>& OutActions)
{
    const int n = W.NumSlots();
    OutActions.assign(static_cast<size_t>(n), ActWatch);
    float logits[kNumActions];
    bool mask[kNumActions];
    for (int i = 0; i < n; ++i)
    {
        const size_t iu = static_cast<size_t>(i);
        if (!W.Alive[iu]) { continue; }
        const float* o = Obs.data() + iu * kObsDim;
        const int sp = W.Sp[iu];
        const FBrain* bn = (sp >= 0 && sp < static_cast<int>(BrainBySpecies.size())) ? BrainBySpecies[static_cast<size_t>(sp)] : nullptr;
        if (bn)
        {
            BrainLogits(*bn, o, logits);
            MaskFromObs(o, mask);
            OutActions[iu] = SampleFromLogits(logits, mask, HashUnit(Seed, W.Uid[iu], Decision));
        }
        else
        {
            OutActions[iu] = RuleDecide(o);
        }
    }
}
}  // namespace EcoR10

#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(pop)
#endif

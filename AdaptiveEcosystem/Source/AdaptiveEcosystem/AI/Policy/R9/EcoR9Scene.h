// EcoR9Scene.h — R9 큰 세계 장면 생성기 (엔진 없음, 헤더 전용, 2026-11-13).
//
// 무엇: 언리얼이 훑은 땅 지도(4 m 칸, 열린 땅·물·가파름·나무/바위)를 받아, 학습 세계(120 m 정사각, 파이썬 r9_world._init_world)의
//       생성 규칙을 그 땅 전체에 펼친 장면(Params + State)을 만든다. 그다음 EcoR9::World::Init 으로 돌린다.
//       - 시작·다시 남 자리 = 4-이웃으로 이어진 가장 큰 열린 땅.
//       - 무리 자리 K 곳 = 둘레가 트인 곳 가운데 서로 가장 먼 점. 자리마다 사슴·늑대·멧돼지를 학습 세계 배치 규칙으로 놓음.
//       - 은신처 = 120 m 타일마다 학습 세계 개수(3~6) × 땅 비율, 반지름 4~7, 가운데끼리 18 이상, 원이 모두 열린 땅. 나무/바위 곁 먼저.
//       - 먹이 = 학습 세계 패치 생성기(잡음 → 흐림 → 정규화 → 문턱). 정규화 최소·최대는 120 m 타일 평균(ISLAND_STAGE I.6 의 1),
//         풀 용량은 열린 칸 평균이 학습 세계(용량 합 70 / 900 칸)와 같게. 막힌 칸 용량·재생 0, 은신처 칸 × 0.15.
// 근거: herbivore_rl/env_v2/r9_world.py 846-1172 (_init_world·_patch·_place_try·_place_founders), r9_life.py 90-216 (시작 개체 해시),
//       configs/v3_r9.yaml world·placement·food (장면 덤프에 없는 생성 값 — 아래 GenRules 기본값).
// 지킴: 세계 규칙·관측·두뇌는 EcoR9Core.h 그대로. 이 파일은 시작 장면만 만든다. 길찾기·손규칙 없음. 표준 라이브러리만, 예외 없음.
// 동물 세계 (2026-11-13): 종 고리는 장면 종 수 Base.NumSpecies (세 종 장면 3 — 지금과 같은 차례·같은 값, 동물 장면 6 = + 물소·표범·여우).
//       새 종도 파이썬 _place_founders 와 같이 '늑대가 아닌 종' 규칙으로 놓는다 (늑대에서 14.5 이상, 은신처 못 들어가는 몸은 원 + 0.5 밖).
#pragma once

#include "EcoR9Core.h"

#include <cstdint>
#include <string>
#include <vector>

#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(precise, on, push)
#endif

namespace EcoR9
{
// 땅 칸 종류 (언리얼 훑기 → 코어). 0 이 아니면 모두 막힌 칸이다. 종류는 은신처 곁 고르기에만 쓴다.
enum ELand : uint8_t
{
    LandOpen = 0,       // 다닐 수 있는 땅
    LandVoid = 1,       // 바다·호수·강·땅 없음·훑은 사각 밖
    LandSteep = 2,      // 가파름
    LandObstacle = 3,   // 나무·바위·건물 (은신처 곁 후보)
};

struct LandMap
{
    int G = 0;                    // 한 변 칸 수 (정사각, 코어 격자와 같다)
    double Cell = 2.0;            // 칸 한 변 (단위 = 2 m). 장면 덤프의 cell 과 같아야 한다
    std::vector<uint8_t> Kind;    // G*G, ELand, 차례 iy * G + ix
    std::vector<double> Anchor;   // 선택: 은신처 곁 후보점 (x0, y0, x1, y1, … 단위). 비면 LandObstacle 칸을 쓴다
};

// 학습 세계 생성 값 (configs/v3_r9.yaml — 장면 덤프 scene.txt 에 들어 있지 않은 것). [어림] 은 큰 세계에서 새로 정한 값.
struct GenRules
{
    int ShelterCountLo = 3, ShelterCountHi = 6;   // world.shelters.count (120 m 정사각 하나에)
    double ShelterRLo = 4.0, ShelterRHi = 7.0;    // world.shelters.radius
    double ShelterMinGap = 18.0;                  // world.shelters.min_gap (가운데끼리)
    double ShelterWallGap = 8.0;                  // world.shelters.wall_gap (가운데가 세계 벽에서)
    int ShelterTries = 2000;                      // world.shelters.tries
    double AnchorReach = 3.0;                     // [어림] 은신처 원 가장자리에서 나무/바위까지 이만큼 안이면 '곁' (6 m)
    int GrassBlur = 5;                            // food.grass.patch_blur
    double GrassThr = 0.6;                        // food.grass.patch_threshold
    double RegenBase = 0.002;                     // food.grass.regen_base
    double GrassCoverMult = 0.15;                 // food.grass.cover_mult
    int RootBlur = 5;                             // food.root.patch_blur
    double RootThr = 0.7;                         // food.root.patch_threshold
    double RootRegenQ = 1.0;                      // food.root.regen_q
    double RootCoverMult = 0.15;                  // food.root.cover_mult
    double TrainGrassTotal = 70.0;                // food.train_grass_total (학습 세계 900 칸의 풀 용량 합, 은신처 배수 전)
    double TrainGrassTotalFauna = 90.0;           // 동물 세계 v3_r9_fauna.yaml food.train_grass_total (물소 몫 — 장면에 fauna_on 이 있을 때만)
    double TrainCells = 900.0;                    // 학습 세계 칸 수 (30 × 30)
    double WolfGap = 10.0;                        // placement.wolf_gap
    double PreyFromWolf = 14.5;                   // placement.prey_from_wolf
    double ShelterMargin = 0.5;                   // placement.shelter_margin (늑대)
    int PlaceTries = 200;                         // placement.tries
    double SiteOpenMin = 0.6;                     // [어림] 무리 자리 후보: 둘레 Tile 정사각의 시작 가능 칸 비율 하한 (없으면 낮춰 감)
};

struct BigSpec
{
    uint64_t Seed = 1;                 // 장면 난수 (같은 땅·같은 시드 → 같은 장면)
    int Herds = 6;                     // 무리 자리 수 K
    int PerHerd[kMaxSpecies] = {24, 2, 8, 0, 0, 0};   // 자리마다 사슴·늑대·멧돼지 [어림 — 학습 세계 시작(24·4·8) 둘레, 늑대는 한 쌍]
                                                      // · 물소·표범·여우 (동물 장면만 — 세 종 장면은 뒤 셋을 보지 않음)
    int MaxAnimals = 400;              // 총수 상한 (넘으면 자리 수를 줄임)
    double Tile = 60.0;                // 학습 세계 한 변 (단위) = 패치 정규화 타일 = 무리 둘레 정사각 한 변
    int CarcassPerHerd = 48;           // 사체 칸 = 이 값 × 자리 수 (학습 세계 한 세계 48)
    std::vector<double> Sites;         // 선택: 무리 자리 (x0, y0, …) 단위 — 주면 그 곁 가장 가까운 시작 가능 칸, 비면 스스로 고름
    double PrefX = -1.0, PrefY = -1.0; // 선택: 첫 자리를 이 점 가까이 (단위). 음수 = 가장 트인 곳부터
    GenRules Rules;
};

struct BigInfo
{
    int G = 0;
    double Size = 0.0;
    int64_t OpenCells = 0, MainCells = 0;    // 열린 칸 · 가장 큰 이어진 땅 칸
    int64_t Components = 0;                  // 열린 땅 덩어리 수
    int Counts[kMaxSpecies] = {0, 0, 0, 0, 0, 0};
    std::vector<double> Sites;               // 무리 자리 (x, y 단위)
    std::vector<double> SiteOpen;            // 자리 둘레 Tile 정사각의 시작 가능 칸 비율
    int Shelters = 0, ShelterAnchored = 0;
    double GrassCapSum = 0.0, RootCapSum = 0.0;
    double GrassFrac = 0.0, RootFrac = 0.0;  // 열린 칸 가운데 용량 > 0 비율
    double GrassMeanOpen = 0.0;              // 열린 칸 풀 용량 평균 (은신처 배수 뒤)
    std::string Note;                        // 경고 (한국어, 줄마다 '\n')
};

namespace SceneDetail
{
constexpr uint64_t TagGrass = 8102, TagRoot = 9103, TagShelter = 9104, TagPlace = 9105, TagSite = 9107;

inline uint64_t Gcd(uint64_t A, uint64_t B)
{
    while (B != 0)
    {
        const uint64_t T = A % B;
        A = B;
        B = T;
    }
    return A;
}

// r9_life.founder_rank
inline int FounderRank(int Index, int Count, uint64_t Seed)
{
    const uint64_t N = static_cast<uint64_t>(Count);
    uint64_t Stride = 31;
    while (Gcd(Stride, N) != 1) { ++Stride; }
    return static_cast<int>((static_cast<uint64_t>(Index) * Stride + HashMix(Seed) % N) % N);
}

// r9_life.founder_age
inline double FounderAge(double Maturity, double JuvFrac, double MaxAge, uint64_t Seed, int Ordinal, int Count)
{
    const int Young = static_cast<int>(std::floor(static_cast<double>(std::max(0, Count)) * JuvFrac));
    const double U = HashUnit(Seed + static_cast<uint64_t>(Ordinal) * 31u);
    if (Ordinal < Young) { return Maturity * (0.18 + 0.72 * (static_cast<double>(Ordinal) + U) / static_cast<double>(std::max(1, Young))); }
    return Maturity + (MaxAge - Maturity) * U;
}

// 8-이웃 두 번 훑기 거리 변환 (칸 수: 곧은 1, 대각 √2). Src 칸 0. Src 가 없으면 큰 값.
inline void Chamfer(int G, const std::vector<uint8_t>& Src, std::vector<float>& D)
{
    const float Big = 1.0e9f, Dg = 1.41421356f;
    const size_t GG = static_cast<size_t>(G) * static_cast<size_t>(G);
    D.assign(GG, Big);
    for (size_t c = 0; c < GG; ++c)
    {
        if (Src[c]) { D[c] = 0.0f; }
    }
    auto At = [G, &D](int X, int Y) -> float& { return D[static_cast<size_t>(Y) * static_cast<size_t>(G) + static_cast<size_t>(X)]; };
    for (int Y = 0; Y < G; ++Y)
    {
        for (int X = 0; X < G; ++X)
        {
            float V = At(X, Y);
            if (X > 0) { V = std::min(V, At(X - 1, Y) + 1.0f); }
            if (Y > 0)
            {
                V = std::min(V, At(X, Y - 1) + 1.0f);
                if (X > 0) { V = std::min(V, At(X - 1, Y - 1) + Dg); }
                if (X + 1 < G) { V = std::min(V, At(X + 1, Y - 1) + Dg); }
            }
            At(X, Y) = V;
        }
    }
    for (int Y = G - 1; Y >= 0; --Y)
    {
        for (int X = G - 1; X >= 0; --X)
        {
            float V = At(X, Y);
            if (X + 1 < G) { V = std::min(V, At(X + 1, Y) + 1.0f); }
            if (Y + 1 < G)
            {
                V = std::min(V, At(X, Y + 1) + 1.0f);
                if (X + 1 < G) { V = std::min(V, At(X + 1, Y + 1) + Dg); }
                if (X > 0) { V = std::min(V, At(X - 1, Y + 1) + Dg); }
            }
            At(X, Y) = V;
        }
    }
}

// 반경 Br 칸 상자 평균 (가장자리는 잘린 창의 실제 칸 수로 나눔 — r8_world._box_mean 과 같은 뜻)
inline void BoxMeanGrid(const std::vector<double>& F, int G, int Br, std::vector<double>& Out)
{
    const size_t Gs = static_cast<size_t>(G), G1 = Gs + 1u;
    std::vector<double> Sat(G1 * G1, 0.0);
    for (size_t y = 0; y < Gs; ++y)
    {
        double Row = 0.0;
        for (size_t x = 0; x < Gs; ++x)
        {
            Row += F[y * Gs + x];
            Sat[(y + 1u) * G1 + (x + 1u)] = Sat[y * G1 + (x + 1u)] + Row;
        }
    }
    Out.assign(Gs * Gs, 0.0);
    for (int y = 0; y < G; ++y)
    {
        const int Y0 = std::max(y - Br, 0), Y1 = std::min(y + Br + 1, G);
        for (int x = 0; x < G; ++x)
        {
            const int X0 = std::max(x - Br, 0), X1 = std::min(x + Br + 1, G);
            const size_t a = static_cast<size_t>(Y1) * G1 + static_cast<size_t>(X1), b = static_cast<size_t>(Y0) * G1 + static_cast<size_t>(X1);
            const size_t c = static_cast<size_t>(Y1) * G1 + static_cast<size_t>(X0), d = static_cast<size_t>(Y0) * G1 + static_cast<size_t>(X0);
            Out[static_cast<size_t>(y) * Gs + static_cast<size_t>(x)] = (Sat[a] - Sat[b] - Sat[c] + Sat[d]) / static_cast<double>((Y1 - Y0) * (X1 - X0));
        }
    }
}

// 학습 세계 패치 (r9_world._patch): 고른 잡음 → 반경 Blur 상자 흐림 → 최소·최대 정규화 → 문턱. 큰 격자는 최소·최대를 TileC 칸 타일들의 평균으로.
inline void Patch(uint64_t Seed, uint64_t Tag, int G, int TileC, int Blur, double Thr, std::vector<double>& Out)
{
    Pcg32Random R(Seed, Tag);
    const size_t GG = static_cast<size_t>(G) * static_cast<size_t>(G);
    std::vector<double> Noise(GG);
    for (double& V : Noise) { V = R.NextDouble(); }
    std::vector<double> M;
    BoxMeanGrid(Noise, G, std::max(1, Blur), M);
    double Mn = 0.0, Mx = 0.0;
    if (G <= TileC)
    {
        Mn = *std::min_element(M.begin(), M.end());
        Mx = *std::max_element(M.begin(), M.end());
    }
    else
    {
        double SMn = 0.0, SMx = 0.0;
        int NT = 0;
        for (int Ty = 0; Ty < G; Ty += TileC)
        {
            for (int Tx = 0; Tx < G; Tx += TileC)
            {
                if (Ty + TileC > G || Tx + TileC > G) { continue; }   // 온전한 타일만 (가장자리 조각 타일은 표본이 적어 넓이가 좁다)
                double A = std::numeric_limits<double>::infinity(), B = -std::numeric_limits<double>::infinity();
                for (int y = Ty; y < Ty + TileC; ++y)
                {
                    for (int x = Tx; x < Tx + TileC; ++x)
                    {
                        const double V = M[static_cast<size_t>(y) * static_cast<size_t>(G) + static_cast<size_t>(x)];
                        A = std::min(A, V);
                        B = std::max(B, V);
                    }
                }
                SMn += A;
                SMx += B;
                ++NT;
            }
        }
        Mn = SMn / std::max(1, NT);
        Mx = SMx / std::max(1, NT);
    }
    const double Den = std::max(Mx - Mn, 1e-9);
    Out.assign(GG, 0.0);
    for (size_t c = 0; c < GG; ++c)
    {
        const double V = (M[c] - Mn) / Den;
        Out[c] = Clamp((V - Thr) / (1.0 - Thr), 0.0, 1.0);
    }
}
} // namespace SceneDetail

inline bool BuildBigScene(const Params& Base, const LandMap& Land, const BigSpec& Spec, Params& OutP, State& OutSt, BigInfo& Info, std::string* Err)
{
    using namespace SceneDetail;
    Info = BigInfo{};
    const int G = Land.G;
    const size_t GG = static_cast<size_t>(G) * static_cast<size_t>(G);
    if (G <= 0 || Land.Kind.size() != GG)
    {
        Detail::SetErr(Err, "land map size mismatch");
        return false;
    }
    if (!(Land.Cell > 0.0) || std::fabs(Land.Cell - Base.Cell) > 1e-12)
    {
        Detail::SetErr(Err, "land cell must equal scene cell");
        return false;
    }
    const GenRules& Ru = Spec.Rules;
    const double Cell = Land.Cell;
    const double Size = static_cast<double>(G) * Cell;
    const double Tile = std::max(Spec.Tile, 4.0 * Cell);
    const int TileC = std::max(1, static_cast<int>(std::lround(Tile / Cell)));
    auto Idx = [G](int X, int Y) { return static_cast<size_t>(Y) * static_cast<size_t>(G) + static_cast<size_t>(X); };
    auto CellOfV = [Cell, G](double V) { return std::min(std::max(static_cast<int>(V / Cell), 0), G - 1); };
    Info.G = G;
    Info.Size = Size;

    // ---- 1 막힌 칸 · 가장 큰 이어진 땅 ----
    std::vector<uint8_t> Blocked(GG, 0), Spawn(GG, 0);
    for (size_t c = 0; c < GG; ++c)
    {
        Blocked[c] = Land.Kind[c] != LandOpen ? 1 : 0;
        Info.OpenCells += Blocked[c] ? 0 : 1;
    }
    {
        std::vector<int> Label(GG, -1);
        std::vector<int> Stack;
        int BestLabel = -1;
        int64_t BestN = 0;
        int NL = 0;
        for (size_t c0 = 0; c0 < GG; ++c0)
        {
            if (Blocked[c0] || Label[c0] >= 0) { continue; }
            int64_t N = 0;
            Stack.clear();
            Stack.push_back(static_cast<int>(c0));
            Label[c0] = NL;
            while (!Stack.empty())
            {
                const int c = Stack.back();
                Stack.pop_back();
                ++N;
                const int X = c % G, Y = c / G;
                const int Nx[4] = {X - 1, X + 1, X, X}, Ny[4] = {Y, Y, Y - 1, Y + 1};
                for (int q = 0; q < 4; ++q)
                {
                    if (Nx[q] < 0 || Ny[q] < 0 || Nx[q] >= G || Ny[q] >= G) { continue; }
                    const size_t n = Idx(Nx[q], Ny[q]);
                    if (Blocked[n] || Label[n] >= 0) { continue; }
                    Label[n] = NL;
                    Stack.push_back(static_cast<int>(n));
                }
            }
            if (N > BestN)
            {
                BestN = N;
                BestLabel = NL;
            }
            ++NL;
        }
        Info.Components = NL;
        Info.MainCells = BestN;
        for (size_t c = 0; c < GG; ++c) { Spawn[c] = (BestLabel >= 0 && Label[c] == BestLabel) ? 1 : 0; }
    }
    if (Info.MainCells <= 0)
    {
        Detail::SetErr(Err, "no open land");
        return false;
    }
    // 시작 가능 칸 누적합 (둘레 트임 셈)
    const size_t G1 = static_cast<size_t>(G) + 1u;
    std::vector<int64_t> SatS(G1 * G1, 0);
    for (int y = 0; y < G; ++y)
    {
        int64_t Row = 0;
        for (int x = 0; x < G; ++x)
        {
            Row += Spawn[Idx(x, y)];
            SatS[static_cast<size_t>(y + 1) * G1 + static_cast<size_t>(x + 1)] = SatS[static_cast<size_t>(y) * G1 + static_cast<size_t>(x + 1)] + Row;
        }
    }
    auto OpenFrac = [&](double Cx, double Cy) {
        // Cx, Cy 가운데 Tile 정사각 (세계 밖은 막힌 셈) 의 시작 가능 칸 비율
        const int X0 = static_cast<int>(std::floor((Cx - 0.5 * Tile) / Cell)), Y0 = static_cast<int>(std::floor((Cy - 0.5 * Tile) / Cell));
        const int X1 = X0 + TileC, Y1 = Y0 + TileC;
        const int A0 = std::max(X0, 0), B0 = std::max(Y0, 0), A1 = std::min(X1, G), B1 = std::min(Y1, G);
        if (A1 <= A0 || B1 <= B0) { return 0.0; }
        const int64_t N = SatS[static_cast<size_t>(B1) * G1 + static_cast<size_t>(A1)] - SatS[static_cast<size_t>(B0) * G1 + static_cast<size_t>(A1)] -
                          SatS[static_cast<size_t>(B1) * G1 + static_cast<size_t>(A0)] + SatS[static_cast<size_t>(B0) * G1 + static_cast<size_t>(A0)];
        return static_cast<double>(N) / static_cast<double>(TileC * TileC);
    };
    auto SpawnAt = [&](double X, double Y) { return X >= 0.0 && Y >= 0.0 && X <= Size && Y <= Size && Spawn[Idx(CellOfV(X), CellOfV(Y))] != 0; };
    auto NearestSpawnCell = [&](double X, double Y, double& Ox, double& Oy) {
        const int Ix = CellOfV(X), Iy = CellOfV(Y);
        for (int R = 0; R < G; ++R)
        {
            double BestD = std::numeric_limits<double>::infinity();
            bool Found = false;
            for (int Qy = Iy - R; Qy <= Iy + R; ++Qy)
            {
                if (Qy < 0 || Qy >= G) { continue; }
                const bool EdgeRow = Qy == Iy - R || Qy == Iy + R;
                for (int Qx = Ix - R; Qx <= Ix + R; Qx += (EdgeRow || R == 0) ? 1 : 2 * R)
                {
                    if (Qx < 0 || Qx >= G || !Spawn[Idx(Qx, Qy)]) { continue; }
                    const double Cx = (Qx + 0.5) * Cell, Cy = (Qy + 0.5) * Cell;
                    const double D = (Cx - X) * (Cx - X) + (Cy - Y) * (Cy - Y);
                    if (D < BestD)
                    {
                        BestD = D;
                        Ox = Cx;
                        Oy = Cy;
                        Found = true;
                    }
                }
            }
            if (Found) { return true; }
        }
        return false;
    };

    // ---- 2 무리 자리 ----
    const int NS = std::min(std::max(Base.NumSpecies, 1), kMaxSpecies);   // 장면 종 수 (세 종 장면 3 — 아래 고리가 지금과 같다)
    int PerTot = 0;
    for (int k = 0; k < NS; ++k) { PerTot += std::max(0, Spec.PerHerd[k]); }
    if (PerTot <= 0 || Spec.Herds <= 0)
    {
        Detail::SetErr(Err, "no animals requested");
        return false;
    }
    int K = std::min(Spec.Herds, std::max(1, Spec.MaxAnimals / PerTot));
    if (K < Spec.Herds) { Info.Note += "총수 상한 " + std::to_string(Spec.MaxAnimals) + " 때문에 무리 자리를 " + std::to_string(K) + " 곳으로 줄임\n"; }
    std::vector<double> Sites;
    if (!Spec.Sites.empty())
    {
        for (size_t q = 0; q + 1 < Spec.Sites.size() && static_cast<int>(Sites.size() / 2) < K; q += 2)
        {
            double Ox = 0.0, Oy = 0.0;
            if (NearestSpawnCell(Spec.Sites[q], Spec.Sites[q + 1], Ox, Oy))
            {
                Sites.push_back(Ox);
                Sites.push_back(Oy);
            }
        }
    }
    else
    {
        // 후보 = 5 칸(20 m) 간격 시작 가능 칸 가운데 둘레가 트인 곳. 첫 자리 = Pref 에 가장 가까운(없으면 가장 트인) 후보, 다음은 가장 먼 점.
        const int Stride = 5;
        std::vector<double> Cand, CandOpen;
        for (double Thr = Ru.SiteOpenMin; Cand.empty(); Thr = Thr > 0.05 ? Thr - 0.15 : -1.0)
        {
            for (int y = Stride / 2; y < G; y += Stride)
            {
                for (int x = Stride / 2; x < G; x += Stride)
                {
                    if (!Spawn[Idx(x, y)]) { continue; }
                    const double Cx = (x + 0.5) * Cell, Cy = (y + 0.5) * Cell;
                    const double F = OpenFrac(Cx, Cy);
                    if (F >= Thr)
                    {
                        Cand.push_back(Cx);
                        Cand.push_back(Cy);
                        CandOpen.push_back(F);
                    }
                }
            }
            if (Thr < 0.0) { break; }
            if (Cand.empty()) { Info.Note += "둘레가 트인 무리 자리 후보가 없어 트임 하한을 낮춤\n"; }
        }
        const size_t Nc = CandOpen.size();
        if (Nc == 0)
        {
            Detail::SetErr(Err, "no herd site candidate");
            return false;
        }
        size_t First = 0;
        if (Spec.PrefX >= 0.0 && Spec.PrefY >= 0.0)
        {
            double BestD = std::numeric_limits<double>::infinity();
            for (size_t c = 0; c < Nc; ++c)
            {
                const double D = (Cand[2 * c] - Spec.PrefX) * (Cand[2 * c] - Spec.PrefX) + (Cand[2 * c + 1] - Spec.PrefY) * (Cand[2 * c + 1] - Spec.PrefY);
                if (CandOpen[c] >= Ru.SiteOpenMin - 1e-12 && D < BestD)
                {
                    BestD = D;
                    First = c;
                }
            }
        }
        else
        {
            for (size_t c = 1; c < Nc; ++c)
            {
                if (CandOpen[c] > CandOpen[First]) { First = c; }
            }
        }
        std::vector<double> Near(Nc, std::numeric_limits<double>::infinity());
        size_t Pick = First;
        const double Gap = 0.5 * Tile;
        for (int n = 0; n < K; ++n)
        {
            Sites.push_back(Cand[2 * Pick]);
            Sites.push_back(Cand[2 * Pick + 1]);
            double Far = -1.0;
            size_t Next = Nc;
            for (size_t c = 0; c < Nc; ++c)
            {
                const double Dx = Cand[2 * c] - Cand[2 * Pick], Dy = Cand[2 * c + 1] - Cand[2 * Pick + 1];
                Near[c] = std::min(Near[c], std::sqrt(Dx * Dx + Dy * Dy));
                // 가장 먼 점 — 같으면 더 트인 곳, 그것도 같으면 먼저 본 후보
                if (Near[c] > Far || (Near[c] == Far && Next < Nc && CandOpen[c] > CandOpen[Next]))
                {
                    Far = Near[c];
                    Next = c;
                }
            }
            if (n + 1 < K && (Next >= Nc || Far < Gap))
            {
                Info.Note += "땅이 좁아 서로 " + std::to_string(static_cast<int>(Gap * 2.0)) + " m 넘게 떨어진 무리 자리가 " + std::to_string(n + 1) +
                             " 곳뿐\n";
                break;
            }
            Pick = Next;
        }
    }
    K = static_cast<int>(Sites.size() / 2);
    if (K <= 0)
    {
        Detail::SetErr(Err, "no herd site on land");
        return false;
    }
    Info.Sites = Sites;
    for (int h = 0; h < K; ++h) { Info.SiteOpen.push_back(OpenFrac(Sites[2 * static_cast<size_t>(h)], Sites[2 * static_cast<size_t>(h) + 1u])); }

    // ---- 3 은신처 (120 m 타일마다 학습 세계 개수 × 땅 비율) ----
    std::vector<double> ShX, ShY, ShR;
    {
        std::vector<float> DB, DO;
        Chamfer(G, Blocked, DB);
        std::vector<uint8_t> AnchorSrc(GG, 0);
        bool AnyAnchor = false;
        if (!Land.Anchor.empty())
        {
            for (size_t q = 0; q + 1 < Land.Anchor.size(); q += 2)
            {
                const double Ax = Land.Anchor[q], Ay = Land.Anchor[q + 1];
                if (!(Ax >= 0.0 && Ay >= 0.0 && Ax <= Size && Ay <= Size)) { continue; }
                AnchorSrc[Idx(CellOfV(Ax), CellOfV(Ay))] = 1;
                AnyAnchor = true;
            }
        }
        else
        {
            for (size_t c = 0; c < GG; ++c)
            {
                if (Land.Kind[c] == LandObstacle)
                {
                    AnchorSrc[c] = 1;
                    AnyAnchor = true;
                }
            }
        }
        if (AnyAnchor) { Chamfer(G, AnchorSrc, DO); }
        const double Sq2 = 1.41421356237;
        const double Bk = std::max(Ru.ShelterMinGap, 1.0);
        const int NBk = std::max(1, static_cast<int>(std::ceil(Size / Bk)) + 1);
        std::vector<std::vector<int>> Buckets(static_cast<size_t>(NBk) * static_cast<size_t>(NBk));
        auto GapOk = [&](double X, double Y) {
            const int Bx = std::min(static_cast<int>(X / Bk), NBk - 1), By = std::min(static_cast<int>(Y / Bk), NBk - 1);
            for (int Qy = std::max(By - 1, 0); Qy <= std::min(By + 1, NBk - 1); ++Qy)
            {
                for (int Qx = std::max(Bx - 1, 0); Qx <= std::min(Bx + 1, NBk - 1); ++Qx)
                {
                    for (int n : Buckets[static_cast<size_t>(Qy) * static_cast<size_t>(NBk) + static_cast<size_t>(Qx)])
                    {
                        const double Dx = X - ShX[static_cast<size_t>(n)], Dy = Y - ShY[static_cast<size_t>(n)];
                        if (std::sqrt(Dx * Dx + Dy * Dy) < Ru.ShelterMinGap) { return false; }
                    }
                }
            }
            return true;
        };
        // 원(+ 밀어냄 0.5)이 막힌 칸에 닿지 않는가 — 거리장으로 먼저 거르고, 원 둘레 칸을 정확히 본다
        auto CircleOpen = [&](double X, double Y, double R) {
            const double Rr = R + Ru.ShelterMargin;
            if (X - Rr < 0.0 || Y - Rr < 0.0 || X + Rr > Size || Y + Rr > Size) { return false; }
            const size_t C = Idx(CellOfV(X), CellOfV(Y));
            if (!Spawn[C]) { return false; }
            if (static_cast<double>(DB[C]) * Cell < Rr - Sq2 * Cell) { return false; }
            const int X0 = CellOfV(X - Rr), X1 = CellOfV(X + Rr), Y0 = CellOfV(Y - Rr), Y1 = CellOfV(Y + Rr);
            for (int y = Y0; y <= Y1; ++y)
            {
                for (int x = X0; x <= X1; ++x)
                {
                    if (!Spawn[Idx(x, y)])
                    {
                        // 칸 사각에서 원 가운데까지 가장 가까운 거리
                        const double Nx = Clamp(X, x * Cell, (x + 1) * Cell), Ny = Clamp(Y, y * Cell, (y + 1) * Cell);
                        if ((Nx - X) * (Nx - X) + (Ny - Y) * (Ny - Y) <= Rr * Rr) { return false; }
                    }
                }
            }
            return true;
        };
        auto Anchored = [&](double X, double Y, double R) {
            if (!AnyAnchor) { return false; }
            return static_cast<double>(DO[Idx(CellOfV(X), CellOfV(Y))]) * Cell <= R + Ru.AnchorReach + Sq2 * Cell;
        };
        Pcg32Random Rs(Spec.Seed, TagShelter);
        const double Wg = Ru.ShelterWallGap;
        for (int Ty = 0; Ty < G; Ty += TileC)
        {
            for (int Tx = 0; Tx < G; Tx += TileC)
            {
                const int Tx1 = std::min(Tx + TileC, G), Ty1 = std::min(Ty + TileC, G);
                int64_t NOpen = 0;
                for (int y = Ty; y < Ty1; ++y)
                {
                    for (int x = Tx; x < Tx1; ++x) { NOpen += Spawn[Idx(x, y)]; }
                }
                // 개수 뽑기는 땅이 없는 타일에서도 같은 차례로 한다 (타일마다 난수 수가 같게)
                const int N0 = Ru.ShelterCountLo + static_cast<int>(Rs.NextBelow(static_cast<uint32_t>(std::max(0, Ru.ShelterCountHi - Ru.ShelterCountLo) + 1)));
                const double Uround = Rs.NextDouble();
                const double LandF = static_cast<double>(NOpen) / static_cast<double>(TileC * TileC);
                const int N = static_cast<int>(std::floor(static_cast<double>(N0) * LandF + Uround));
                const double X0 = std::max(Tx * Cell, Wg), Y0 = std::max(Ty * Cell, Wg);
                const double X1 = std::min(Tx1 * Cell, Size - Wg), Y1 = std::min(Ty1 * Cell, Size - Wg);
                for (int n = 0; n < N && NOpen > 0 && X1 > X0 && Y1 > Y0; ++n)
                {
                    const double R = Ru.ShelterRLo + (Ru.ShelterRHi - Ru.ShelterRLo) * Rs.NextDouble();
                    bool Placed = false;
                    // 앞 절반 시도는 나무/바위 곁만, 뒤 절반은 아무 열린 곳
                    for (int Tr = 0; Tr < Ru.ShelterTries && !Placed; ++Tr)
                    {
                        const double Cx = X0 + (X1 - X0) * Rs.NextDouble();
                        const double Cy = Y0 + (Y1 - Y0) * Rs.NextDouble();
                        const bool NeedAnchor = AnyAnchor && Tr < Ru.ShelterTries / 2;
                        if (!CircleOpen(Cx, Cy, R) || !GapOk(Cx, Cy)) { continue; }
                        const bool Anc = Anchored(Cx, Cy, R);
                        if (NeedAnchor && !Anc) { continue; }
                        const int Bx = std::min(static_cast<int>(Cx / Bk), NBk - 1), By = std::min(static_cast<int>(Cy / Bk), NBk - 1);
                        Buckets[static_cast<size_t>(By) * static_cast<size_t>(NBk) + static_cast<size_t>(Bx)].push_back(static_cast<int>(ShX.size()));
                        ShX.push_back(Cx);
                        ShY.push_back(Cy);
                        ShR.push_back(R);
                        Info.ShelterAnchored += Anc ? 1 : 0;
                        Placed = true;
                    }
                }
            }
        }
    }
    Info.Shelters = static_cast<int>(ShX.size());
    // 은신처 칸 (r9_world 207: 칸 가운데가 원 안)
    std::vector<uint8_t> Cover(GG, 0);
    for (size_t n = 0; n < ShX.size(); ++n)
    {
        const double A = ShX[n], B = ShY[n], R = ShR[n];
        for (int y = CellOfV(B - R); y <= CellOfV(B + R); ++y)
        {
            for (int x = CellOfV(A - R); x <= CellOfV(A + R); ++x)
            {
                const double Cx = (x + 0.5) * Cell, Cy = (y + 0.5) * Cell;
                if ((Cx - A) * (Cx - A) + (Cy - B) * (Cy - B) <= R * R) { Cover[Idx(x, y)] = 1; }
            }
        }
    }

    // ---- 4 먹이 격자 ----
    std::vector<double> Cap, RCap;
    Patch(Spec.Seed, TagGrass, G, TileC, Ru.GrassBlur, Ru.GrassThr, Cap);
    Patch(Spec.Seed, TagRoot, G, TileC, Ru.RootBlur, Ru.RootThr, RCap);
    double PreSum = 0.0;
    for (size_t c = 0; c < GG; ++c)
    {
        if (Blocked[c])
        {
            Cap[c] = 0.0;
            RCap[c] = 0.0;
            continue;
        }
        PreSum += Cap[c];   // 은신처 배수 전 (학습 세계 train_grass_total 과 같은 셈)
        if (Cover[c])
        {
            Cap[c] *= Ru.GrassCoverMult;
            RCap[c] *= Ru.RootCoverMult;
        }
    }
    const double GrassTotal = Base.FaunaOn ? Ru.TrainGrassTotalFauna : Ru.TrainGrassTotal;   // 세 종 장면은 70 그대로
    const double Scale = PreSum > 0.0 ? GrassTotal / Ru.TrainCells * static_cast<double>(Info.OpenCells) / PreSum : 1.0;
    const double Gm = Base.GrassRegenMult, Rm = Base.RootRegenMult;

    // ---- 5 Params ----
    OutP = Base;
    OutP.Seed = static_cast<int64_t>(Spec.Seed);
    OutP.Size = Size;
    OutP.Cell = Cell;
    OutP.G = G;
    OutP.SeedW = HashMix(Spec.Seed);   // r9_life.life_seeds
    for (int q = 0; q < 4; ++q) { OutP.SeedQ[q] = HashMix(OutP.SeedW + static_cast<uint64_t>(q) + 1u); }
    OutP.ShelX = ShX;
    OutP.ShelY = ShY;
    OutP.ShelR = ShR;
    OutP.Blocked = Blocked;
    OutP.Spawnable = Spawn;
    OutP.HerdX.clear();
    OutP.HerdY.clear();
    for (int h = 0; h < K; ++h)
    {
        OutP.HerdX.push_back(Sites[2 * static_cast<size_t>(h)]);
        OutP.HerdY.push_back(Sites[2 * static_cast<size_t>(h) + 1u]);
    }
    OutP.HerdSide = Tile;
    OutP.BigWorld = true;
    int Lo = 0;
    for (int k = 0; k < NS; ++k)
    {
        OutP.Counts[k] = K * std::max(0, Spec.PerHerd[k]);
        OutP.SpLo[k] = Lo;
        Lo += OutP.Counts[k];
        OutP.SpHi[k] = Lo;
        Info.Counts[k] = OutP.Counts[k];
    }
    OutP.NumSlots = Lo;
    OutP.NumCarcass = std::max(1, Spec.CarcassPerHerd) * K;
    const size_t S = static_cast<size_t>(OutP.NumSlots);
    OutP.SlotHerd.assign(S, -1);
    for (int k = 0; k < NS; ++k)
    {
        for (int h = 0; h < K; ++h)
        {
            for (int i = 0; i < Spec.PerHerd[k]; ++i) { OutP.SlotHerd[static_cast<size_t>(OutP.SpLo[k] + h * Spec.PerHerd[k] + i)] = h; }
        }
    }

    // ---- 6 State: 격자 ----
    State& St = OutSt;
    St = State{};
    St.T = 0;
    St.Grass.assign(GG, 0.0);
    St.GrassCap.assign(GG, 0.0);
    St.GrassRegen.assign(GG, 0.0);
    St.Root.assign(GG, 0.0);
    St.RootCap.assign(GG, 0.0);
    St.RootRegen.assign(GG, 0.0);
    St.CoverCell = Cover;
    int64_t NG = 0, NR = 0;
    for (size_t c = 0; c < GG; ++c)
    {
        if (Blocked[c]) { continue; }
        St.GrassCap[c] = Cap[c] * Scale;
        St.Grass[c] = St.GrassCap[c];
        St.GrassRegen[c] = Ru.RegenBase * Gm * (Cover[c] ? Ru.GrassCoverMult : 1.0);
        St.RootCap[c] = RCap[c];
        St.Root[c] = RCap[c];
        St.RootRegen[c] = Ru.RegenBase * Ru.RootRegenQ * Rm * (Cover[c] ? Ru.RootCoverMult : 1.0);
        Info.GrassCapSum += St.GrassCap[c];
        Info.RootCapSum += St.RootCap[c];
        NG += St.GrassCap[c] > 0.0 ? 1 : 0;
        NR += St.RootCap[c] > 0.0 ? 1 : 0;
    }
    Info.GrassFrac = static_cast<double>(NG) / static_cast<double>(std::max<int64_t>(1, Info.OpenCells));
    Info.RootFrac = static_cast<double>(NR) / static_cast<double>(std::max<int64_t>(1, Info.OpenCells));
    Info.GrassMeanOpen = Info.GrassCapSum / static_cast<double>(std::max<int64_t>(1, Info.OpenCells));

    // ---- 7 State: 칸 ----
    St.Sp.assign(S, 0);
    St.Pos.assign(S, Vec2d{});
    St.Head.assign(S, Vec2d{1.0, 0.0});
    St.Vel.assign(S, Vec2d{});
    St.Disp.assign(S, Vec2d{});
    St.DirCmd.assign(S, Vec2d{});
    St.KnockDir.assign(S, Vec2d{});
    St.E.assign(S, 0.0);
    St.R.assign(S, 0.0);
    St.Stam.assign(S, 1.0);
    St.Hp.assign(S, 1.0);
    St.Born.assign(S, 0.0);
    St.NextBirth.assign(S, 0.0);
    St.GSpeed.assign(S, 1.0);
    St.GSize.assign(S, 1.0);
    St.RespT.assign(S, 0.0);
    St.KinId.assign(S, 0);
    St.Uid.assign(S, 0);
    St.Sex.assign(S, 0);
    St.Generation.assign(S, 0);
    St.ParentA.assign(S, 0);
    St.ParentB.assign(S, 0);
    St.Offspring.assign(S, 0);
    St.Act.assign(S, ActWatch);
    St.BiteCd.assign(S, 0);
    St.KnockLeft.assign(S, 0);
    St.Alive.assign(S, 0);
    St.StamLock.assign(S, 0);
    St.Mating.assign(S, 0);
    St.Mem.assign(S * S, 0.0);
    const size_t M = static_cast<size_t>(OutP.NumCarcass);
    St.CarcOk.assign(M, 0);
    St.CarcPos.assign(M, Vec2d{});
    St.CarcMeat.assign(M, 0.0);
    St.CarcMeat0.assign(M, 0.0);
    St.CarcT.assign(M, 0.0);
    St.CarcKin.assign(M, -1);
    St.Pairs.clear();
    for (int k = 0; k < NS; ++k)
    {
        for (int s = OutP.SpLo[k]; s < OutP.SpHi[k]; ++s)
        {
            St.Sp[static_cast<size_t>(s)] = k;
            St.KinId[static_cast<size_t>(s)] = OutP.KinPerm[k];
        }
    }
    // 칸 차례 = uid 차례 (학습 세계 train: 종 차례 사슴 → 늑대 → 멧돼지 (→ 물소 → 표범 → 여우), 종 안에서는 무리 차례)
    for (size_t s = 0; s < S; ++s) { St.Uid[s] = static_cast<int64_t>(s) + 1; }
    St.NextUid = static_cast<int64_t>(S) + 1;

    // 배치 (r9_world._place_founders 꼴): 늑대 먼저(은신처 원 + 0.5 밖, 다른 늑대에서 10), 그다음 사슴·멧돼지(은신처 밖, 모든 늑대에서 14.5).
    // 큰 세계에서 더한 것: 구역 = 무리 자리 둘레 Tile 정사각, 자리는 시작 가능 칸만, 못 찾으면 무리 자리 가운데.
    {
        Pcg32Random Rp(Spec.Seed, TagPlace);
        std::vector<double> WolfX, WolfY;
        auto OutsideSh = [&](double X, double Y, double Margin) {
            for (size_t n = 0; n < ShX.size(); ++n)
            {
                if (std::fabs(X - ShX[n]) > ShR[n] + Margin + 1.0 || std::fabs(Y - ShY[n]) > ShR[n] + Margin + 1.0) { continue; }
                const double Dx = X - ShX[n], Dy = Y - ShY[n];
                if (!(std::sqrt(Dx * Dx + Dy * Dy) > ShR[n] + Margin)) { return false; }
            }
            return true;
        };
        std::vector<int> Order;
        for (int s = OutP.SpLo[SpWolf]; s < OutP.SpHi[SpWolf]; ++s) { Order.push_back(s); }
        for (int s = 0; s < static_cast<int>(S); ++s)
        {
            if (St.Sp[static_cast<size_t>(s)] != SpWolf) { Order.push_back(s); }
        }
        std::vector<double> Fat(S, 0.0);
        std::vector<int> HeadI(S, 0);
        for (int s : Order)
        {
            const size_t su = static_cast<size_t>(s);
            const int k = St.Sp[su];
            const int h = OutP.SlotHerd[su];
            const double HSide = std::min(Tile, Size);
            const double Rx0 = Clamp(Sites[2 * static_cast<size_t>(h)] - 0.5 * HSide, 0.0, Size - HSide);
            const double Ry0 = Clamp(Sites[2 * static_cast<size_t>(h) + 1u] - 0.5 * HSide, 0.0, Size - HSide);
            const double Margin = OutP.ShelterEnter[k] ? 0.0 : Ru.ShelterMargin;
            const bool IsWolf = k == SpWolf;
            const double Need = IsWolf ? Ru.WolfGap : Ru.PreyFromWolf;
            bool Have = false, HaveBest = false;
            double Bx = 0.0, By = 0.0, BestSc = -std::numeric_limits<double>::infinity();
            for (int Tr = 0; Tr < Ru.PlaceTries; ++Tr)
            {
                const double Cx = Rx0 + HSide * Rp.NextDouble();
                const double Cy = Ry0 + HSide * Rp.NextDouble();
                if (!SpawnAt(Cx, Cy) || !OutsideSh(Cx, Cy, Margin)) { continue; }
                double Sc = 1e9;
                for (size_t w = 0; w < WolfX.size(); ++w)
                {
                    const double Dx = WolfX[w] - Cx, Dy = WolfY[w] - Cy;
                    Sc = std::min(Sc, std::sqrt(Dx * Dx + Dy * Dy));
                }
                if (Sc >= Need)
                {
                    Bx = Cx;
                    By = Cy;
                    Have = true;
                    break;
                }
                if (Sc > BestSc)
                {
                    BestSc = Sc;
                    Bx = Cx;
                    By = Cy;
                    HaveBest = true;
                }
            }
            if (!Have && !HaveBest)
            {
                Bx = Sites[2 * static_cast<size_t>(h)];
                By = Sites[2 * static_cast<size_t>(h) + 1u];
            }
            St.Pos[su] = Vec2d{Bx, By};
            if (IsWolf)
            {
                WolfX.push_back(Bx);
                WolfY.push_back(By);
            }
            HeadI[su] = static_cast<int>(Rp.NextBelow(8u));
            Fat[su] = OutP.FatInitLo + (OutP.FatInitHi - OutP.FatInitLo) * Rp.NextDouble();
        }
        // 생애 값 (해시, r9_life — 시작 개체): 무리·종 묶음마다 차례 i, 묶음 수 n
        const uint64_t Sw = OutP.SeedW, Sq = OutP.SeedQ[0];
        for (size_t s = 0; s < S; ++s)
        {
            const int k = St.Sp[s];
            const int h = OutP.SlotHerd[s];
            const int n = Spec.PerHerd[k];
            const int i = static_cast<int>(s) - OutP.SpLo[k] - h * n;
            const uint64_t Uu = static_cast<uint64_t>(St.Uid[s]);
            if (OutP.FounderKind[k] == 1)
            {
                const double V = Clamp(OutP.FounderVariation[k], 0.0, 0.1);
                St.GSpeed[s] = 1 + 2 * V * (HashUnit(Sq ^ Uu) - 0.5);
                St.GSize[s] = 1 + 2 * V * (HashUnit(Sq + Uu + 17u) - 0.5);
            }
            else
            {
                St.GSpeed[s] = 0.95 + 0.1 * HashUnit(Sw ^ Uu);
                St.GSize[s] = 0.95 + 0.1 * HashUnit(Sw + Uu + 17u);
            }
            if (OutP.SexMode[k] == 1) { St.Sex[s] = HashUnit(Sq ^ HashMix(Uu + 911u)) < OutP.FemaleFrac[k] ? 1 : 2; }
            else if (OutP.SexMode[k] == 2) { St.Sex[s] = (i % 2) ? 2 : 1; }
            else { St.Sex[s] = 0; }
            // 나이 씨앗: 학습 세계 age_seed. [어림] 무리마다 같은 나이 표가 되풀이되지 않게 무리 1 부터는 Mix(무리) 를 섞는다
            uint64_t Aseed = k == SpDeer ? Sq : (Sq ^ HashMix(static_cast<uint64_t>(1000 + k)));
            if (h > 0) { Aseed ^= HashMix(0x5EED0000ull + static_cast<uint64_t>(h)); }
            const double Age = FounderAge(OutP.Maturity[k], OutP.JuvFrac[k], OutP.MaxFounderAge[k], Aseed, FounderRank(i, n, Aseed), n);
            const double Spread = OutP.FirstBirthSpread[k];
            St.Alive[s] = 1;
            St.Head[s] = Vec2d{OutP.Dir8[HeadI[s]][0], OutP.Dir8[HeadI[s]][1]};
            St.E[s] = OutP.StartEnergy;
            St.R[s] = Fat[s];
            St.Born[s] = -Age;
            St.NextBirth[s] = 0.0 + OutP.FirstBirthBase[k] + Spread * (Spread > 0 ? HashUnit(Sq ^ Uu) : 0.0);
        }
    }
    return true;
}

} // namespace EcoR9

#if defined(_MSC_VER) && !defined(__clang__)
#pragma float_control(pop)
#endif

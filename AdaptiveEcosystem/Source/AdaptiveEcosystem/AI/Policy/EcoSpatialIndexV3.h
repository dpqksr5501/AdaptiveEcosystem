#pragma once

// Engine-independent, snapshot-only broad phase. Original row order is retained
// for floating-point sums, target ties, and Python/native parity.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <unordered_map>
#include <vector>

namespace EcoSpatialV3
{
    struct FRows
    {
        const std::vector<std::int32_t>* Indices = nullptr;
        std::int32_t Count(std::int32_t FullCount) const { return Indices ? static_cast<std::int32_t>(Indices->size()) : FullCount; }
        std::int32_t At(std::int32_t Row) const { return Indices ? (*Indices)[Row] : Row; }
    };

    struct FMeasure
    {
        std::uint64_t Calls = 0, FullCandidates = 0, Candidates = 0;
        double Milliseconds = 0;
    };

    struct FScope
    {
        FMeasure* Measure;
        std::chrono::steady_clock::time_point Start;
        explicit FScope(FMeasure* In) : Measure(In)
        {
            if (Measure) Start = std::chrono::steady_clock::now();
        }
        ~FScope()
        {
            if (Measure) Measure->Milliseconds += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - Start).count();
        }
        void Count(std::int32_t Full, std::int32_t Actual)
        {
            if (Measure) { ++Measure->Calls; Measure->FullCandidates += Full; Measure->Candidates += Actual; }
        }
    };

    struct FDiagnostics
    {
        bool bEnabled = false;
        FMeasure Kin, Threat, Wolf, Build;
        void Reset() { Kin = {}; Threat = {}; Wolf = {}; Build = {}; }
    };

    class FGrid
    {
        struct FPoint { double X, Y; };
        std::unordered_map<std::uint64_t, std::vector<std::int32_t>> Cells;
        std::vector<FPoint> Points;
        double CellSize = 20;
        bool bValid = true;
        static std::uint64_t Key(std::int32_t X, std::int32_t Y)
        {
            return (static_cast<std::uint64_t>(static_cast<std::uint32_t>(X)) << 32) | static_cast<std::uint32_t>(Y);
        }
        bool Cell(double P, std::int32_t& Out) const
        {
            const double V = std::floor(P / CellSize);
            if (!std::isfinite(V) || V < -2147483647.0 || V > 2147483646.0) return false;
            Out = static_cast<std::int32_t>(V); return true;
        }
    public:
        template<class Position>
        void Build(std::int32_t N, double Size, Position Get)
        {
            Cells.clear(); Points.clear(); bValid = std::isfinite(Size) && Size > 0;
            CellSize = bValid ? Size : 20;
            Points.reserve(N);
            for (std::int32_t I = 0; I < N; ++I)
            {
                const auto P = Get(I); Points.push_back({P.X, P.Y});
                std::int32_t X, Y;
                if (!Cell(P.X, X) || !Cell(P.Y, Y)) { bValid = false; continue; }
                Cells[Key(X, Y)].push_back(I);
            }
        }

        // Conservative square-cell candidates; exact original math runs in the
        // consumer. Broad-phase padding avoids rounding away boundary pairs.
        FRows Query(double X, double Y, double Radius, std::vector<std::int32_t>& Out) const
        {
            Out.clear();
            if (!bValid || Points.size() < 64 || !std::isfinite(Radius) || Radius < 0) return {};
            const double R = Radius + (1.0 + std::abs(Radius)) * 1.e-9;
            std::int32_t X0, X1, Y0, Y1;
            if (!Cell(X-R, X0) || !Cell(X+R, X1) || !Cell(Y-R, Y0) || !Cell(Y+R, Y1)) return {};
            const auto Width = static_cast<std::int64_t>(X1)-X0+1;
            const auto Height = static_cast<std::int64_t>(Y1)-Y0+1;
            // Very large query: full scan is cheaper and preserves semantics.
            if (Width > 4096 || Height > 4096 || Width*Height > static_cast<std::int64_t>(Points.size())*4+64) return {};
            for (std::int64_t Cy=Y0; Cy<=Y1; ++Cy)
                for (std::int64_t Cx=X0; Cx<=X1; ++Cx)
                {
                    const auto It=Cells.find(Key(static_cast<std::int32_t>(Cx), static_cast<std::int32_t>(Cy)));
                    if (It!=Cells.end())
                    {
                        // Dense neighborhoods: avoid sorting a near-global list.
                        if (Out.size()+It->second.size() > Points.size()/4) return {};
                        Out.insert(Out.end(), It->second.begin(), It->second.end());
                    }
                }
            std::sort(Out.begin(), Out.end());
            return {&Out};
        }
    };
}

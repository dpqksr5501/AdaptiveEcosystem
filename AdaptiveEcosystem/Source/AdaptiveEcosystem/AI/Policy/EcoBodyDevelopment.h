#pragma once

#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>

namespace EcoLifeV3
{
    /** Signed spatial modes of the whole body. The rig supplies geometry, never a species-specific target bone. */
    struct FBodyDevelopment
    {
        static constexpr double Limit = .15;
        double Fore = 0., Aft = 0., Span = 0., Rise = 0.;

        std::array<double, 4> Values() const { return {Fore, Aft, Span, Rise}; }

        bool IsValid() const
        {
            const auto Axes = Values();
            return std::all_of(Axes.begin(), Axes.end(), [](double Axis) {
                return std::isfinite(Axis) && std::abs(Axis) <= Limit;
            });
        }

        FBodyDevelopment AtGrowth(double Growth) const { return {Fore * Growth, Aft * Growth, Span * Growth, Rise * Growth}; }

        std::uint32_t Pack() const
        {
            const auto Byte = [](double Value) { return std::uint32_t(std::lround(800. * Value) + 128); };
            return Byte(Fore) | (Byte(Aft) << 8) | (Byte(Span) << 16) | (Byte(Rise) << 24);
        }

        static constexpr std::uint32_t Neutral = 0x80808080u;

        static FBodyDevelopment Unpack(std::uint32_t Packed)
        {
            const auto Axis = [Packed](unsigned Shift) { return (double((Packed >> Shift) & 255u) - 128.) / 800.; };
            return {Axis(0), Axis(8), Axis(16), Axis(24)};
        }

        /** Reference-space deformation around the body center. Ground contacts are constrained by the rig. */
        std::array<double, 3> Offset(double Along, double Across, double Up, double Longitudinal) const
        {
            const double FrontWeight = .5 * (1. + std::clamp(Longitudinal, -1., 1.));
            const double LocalGrowth = Aft + (Fore - Aft) * FrontWeight;
            return {Along * LocalGrowth, Across * (Span + .20 * LocalGrowth), Up * (Rise + .15 * LocalGrowth)};
        }
    };
}

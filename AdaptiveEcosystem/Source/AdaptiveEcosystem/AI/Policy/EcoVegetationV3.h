#pragma once

// Engine-free, opt-in habitat model. Time is native simulation seconds; food keeps
// the existing FFoodGrid units. This is a game model, not a hydrology simulation.
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace EcoVegetationV3
{
    enum class EPlant : std::uint8_t { Grass, Riparian, Shrub };
    struct FConfig
    {
        bool bEnabled = false;
        double Infiltration = 0.018; // normalized moisture / simulated second at rain=1
        double Evaporation = 0.002;
        double Drainage = 0.010;
        double Uptake = 0.001;
        double StressLoss = 0.004; // fraction of remaining food / simulated second
        bool IsValid() const
        {
            return std::isfinite(Infiltration) && Infiltration >= 0 && Infiltration <= 1
                && std::isfinite(Evaporation) && Evaporation >= 0 && Evaporation <= 1
                && std::isfinite(Drainage) && Drainage >= 0 && Drainage <= 1
                && std::isfinite(Uptake) && Uptake >= 0 && Uptake <= 1
                && std::isfinite(StressLoss) && StressLoss >= 0 && StressLoss <= 1;
        }
    };
    struct FWeather
    {
        double Rain = 0.2, Temperature = 20, Light = 1;
        bool IsValid() const { return std::isfinite(Rain) && Rain >= 0 && Rain <= 1
            && std::isfinite(Temperature) && Temperature >= -100 && Temperature <= 100
            && std::isfinite(Light) && Light >= 0 && Light <= 1; }
    };
    struct FHabitat
    {
        EPlant Plant = EPlant::Grass;
        double Drainage = 0.5, Shade = 0, WaterSupply = 0, Flood = 0;
        bool bGroundUsable = true;
        bool IsValid() const
        {
            return static_cast<unsigned>(Plant) <= static_cast<unsigned>(EPlant::Shrub)
                && std::isfinite(Drainage) && Drainage >= 0 && Drainage <= 1
                && std::isfinite(Shade) && Shade >= 0 && Shade <= 1
                && std::isfinite(WaterSupply) && WaterSupply >= 0 && WaterSupply <= 1
                && std::isfinite(Flood) && Flood >= 0 && Flood <= 1;
        }
    };
    struct FCell { double Moisture = 0.5, Stress = 0; };
    struct FOutcome { double Food = 0, Growth = 0, Loss = 0; };
    inline double Unit(double V) { return std::clamp(V, 0.0, 1.0); }

    // Caller owns sequence/dedup and supplies a bounded dt, never wall-clock catch-up.
    inline FOutcome Advance(const FConfig& C, const FWeather& W, const FHabitat& H,
        FCell& S, double Food, double Capacity, double RegenPerStep, double Dt)
    {
        FOutcome O{Food, 0, 0};
        if (!C.bEnabled || !C.IsValid() || !W.IsValid() || !H.IsValid()
            || !std::isfinite(Dt) || Dt <= 0 || Dt > 0.25
            || !std::isfinite(Food) || !std::isfinite(Capacity) || Capacity < 0 || Food < 0 || Food > Capacity
            || !std::isfinite(RegenPerStep) || RegenPerStep < 0
            || !std::isfinite(S.Moisture) || S.Moisture < 0 || S.Moisture > 1
            || !std::isfinite(S.Stress) || S.Stress < 0 || S.Stress > 1) return O;
        const double Heat = std::clamp((W.Temperature + 5) / 25, 0.0, 2.0);
        const double Density = Capacity > 0 ? Food / Capacity : 0;
        const double Rate = C.Infiltration * W.Rain * (1 - 0.5 * H.Drainage)
            + 0.01 * H.WaterSupply + 0.03 * H.Flood
            - C.Evaporation * Heat * (0.25 + 0.75 * W.Light) * (1 - 0.5 * H.Shade)
            - C.Drainage * H.Drainage * S.Moisture - C.Uptake * Density;
        S.Moisture = Unit(S.Moisture + Rate * Dt);
        const double Lo = H.Plant == EPlant::Riparian ? 0.45 : (H.Plant == EPlant::Shrub ? 0.18 : 0.30);
        const double Hi = H.Plant == EPlant::Riparian ? 0.95 : (H.Plant == EPlant::Shrub ? 0.65 : 0.75);
        const double Dry = Unit((Lo - S.Moisture) / Lo);
        const double Wet = Unit((S.Moisture - Hi) / (1 - Hi));
        const double FloodStress = H.Flood * (H.Plant == EPlant::Riparian ? 0.1 : 1.0);
        const double TargetStress = std::max({Dry, Wet, FloodStress, H.bGroundUsable ? 0.0 : 1.0});
        S.Stress = Unit(S.Stress + (TargetStress - S.Stress) * (1 - std::exp(-Dt / 8.0)));
        // Loss precedes growth; both are explicit non-negative ledger terms.
        O.Loss = H.bGroundUsable ? Food * (1 - std::exp(-C.StressLoss * S.Stress * Dt)) : Food;
        const double Remaining = Food - O.Loss;
        const double TempSuit = Unit(1 - std::abs(W.Temperature - 20) / 30);
        const double Suit = (1 - TargetStress) * (0.2 + 0.8 * W.Light) * TempSuit;
        O.Growth = H.bGroundUsable ? std::min(Capacity - Remaining, RegenPerStep * Suit * (Capacity - Remaining)) : 0;
        O.Food = Remaining + O.Growth;
        return O;
    }
}

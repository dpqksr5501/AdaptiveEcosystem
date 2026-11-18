#pragma once

// Engine-free, opt-in habitat model. Time is native simulation seconds; food keeps
// the existing FFoodGrid units. This is a game model, not a hydrology simulation.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include "EcoNaturalHabitat.h"

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
        bool bHabitatDynamics = false;
        bool IsValid() const
        {
            return (!bHabitatDynamics || bEnabled) && std::isfinite(Infiltration) && Infiltration >= 0 && Infiltration <= 1
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
        bool bNatural = false;
        double MoistureMin=.30,MoistureMax=.75,TemperatureMin=-5,TemperatureOptimum=18,TemperatureMax=45,ShadeTolerance=.5,SiteSuitability=1;
        double MaturationSeconds=60;
        bool IsValid() const
        {
            return static_cast<unsigned>(Plant) <= static_cast<unsigned>(EPlant::Shrub)
                && std::isfinite(Drainage) && Drainage >= 0 && Drainage <= 1
                && std::isfinite(Shade) && Shade >= 0 && Shade <= 1
                && std::isfinite(WaterSupply) && WaterSupply >= 0 && WaterSupply <= 1
                && std::isfinite(Flood) && Flood >= 0 && Flood <= 1
                && (!bNatural||(std::isfinite(MoistureMin)&&std::isfinite(MoistureMax)&&MoistureMin>0&&MoistureMax<1&&MoistureMin<MoistureMax
                    &&std::isfinite(TemperatureMin)&&std::isfinite(TemperatureOptimum)&&std::isfinite(TemperatureMax)
                    &&TemperatureMin>=-100&&TemperatureMax<=100&&TemperatureMin<TemperatureOptimum&&TemperatureOptimum<TemperatureMax
                    &&std::isfinite(ShadeTolerance)&&ShadeTolerance>=0&&ShadeTolerance<=1
                    &&std::isfinite(SiteSuitability)&&SiteSuitability>=0&&SiteSuitability<=1
                    &&std::isfinite(MaturationSeconds)&&MaturationSeconds>=10&&MaturationSeconds<=7200));
        }
    };
    inline double Unit(double V) { return std::clamp(V, 0.0, 1.0); }
    inline bool IsFraction(double V) { return std::isfinite(V) && V >= 0 && V <= 1; }
    struct FCell
    {
        double Moisture = .5, Stress = 0, Development = 1;
        double BrowsePressure = 0, SurfaceWater = 0, FreshFraction = .4;
        double Disturbance = 0, PendingDisturbance = 0;

        bool IsValid() const
        {
            return IsFraction(Moisture) && IsFraction(Stress) && IsFraction(Development)
                && IsFraction(BrowsePressure) && IsFraction(SurfaceWater) && IsFraction(FreshFraction)
                && IsFraction(Disturbance) && IsFraction(PendingDisturbance);
        }
        void RecordBrowse(double Taken, double Capacity)
        {
            if (Taken > 0 && Capacity > 0)
            {
                const double Fraction = Taken / Capacity;
                BrowsePressure = Unit(BrowsePressure + (1 - BrowsePressure) * .55 * Fraction);
                Development *= 1 - .24 * Fraction * BrowsePressure;
            }
        }
        double NutritionMultiplier() const
        {
            return .84 + .26 * FreshFraction - .19 * Stress;
        }
        bool QueueDisturbance(double Severity)
        {
            if (!IsFraction(Severity) || Severity == 0 || PendingDisturbance > 0 || Disturbance > .1) return false;
            PendingDisturbance = Severity;
            return true;
        }
    };
    struct FOutcome { double Food = 0, Growth = 0, Loss = 0; };

    inline double SeasonalTemperatureOffset(double SimulationSeconds)
    {
        constexpr double PeriodSeconds = 960;
        constexpr double FullTurn = 6.283185307179586;
        return 6 * std::sin(std::fmod(SimulationSeconds, PeriodSeconds) * FullTurn / PeriodSeconds);
    }

    inline double BrowseTraceSeconds(const FCell& Cell)
    {
        return 20 + 70 * Cell.BrowsePressure;
    }

    inline double AdvanceMoisture(const FConfig& C, const FWeather& W, const FHabitat& H,
        double Moisture, double Density, double SurfaceWater, double Dt)
    {
        const double Heat = std::clamp((W.Temperature + 5) / 25, 0.0, 2.0);
        const double Rate = C.Infiltration * W.Rain * (1 - 0.5 * H.Drainage)
            + 0.01 * H.WaterSupply + 0.03 * H.Flood + .006 * SurfaceWater
            - C.Evaporation * Heat * (0.25 + 0.75 * W.Light) * (1 - 0.5 * H.Shade)
            - C.Drainage * H.Drainage * Moisture - C.Uptake * Density;
        return Unit(Moisture + Rate * Dt);
    }

    // Caller owns sequence/dedup and supplies a bounded dt, never wall-clock catch-up.
    inline FOutcome Advance(const FConfig& C, const FWeather& W, const FHabitat& H,
        FCell& S, double Food, double Capacity, double RegenPerStep, double Dt)
    {
        FOutcome O{Food, 0, 0};
        if (!C.bEnabled || !C.IsValid() || !W.IsValid() || !H.IsValid()
            || !std::isfinite(Dt) || Dt <= 0 || Dt > 0.25
            || !std::isfinite(Food) || !std::isfinite(Capacity) || Capacity < 0 || Food < 0 || Food > Capacity
            || !std::isfinite(RegenPerStep) || RegenPerStep < 0
            || !S.IsValid()) return O;
        const bool Dynamics = C.bHabitatDynamics && H.bNatural;
        double DisturbanceLoss = 0;
        if (Dynamics)
        {
            DisturbanceLoss = Food * S.PendingDisturbance;
            S.Development *= 1 - S.PendingDisturbance;
            S.Disturbance = std::max(S.Disturbance, S.PendingDisturbance);
            S.PendingDisturbance = 0;
            const double Retention = Unit(1 - 2 * H.Drainage);
            const double PoolRate = .028 * W.Rain * Retention - (.005 + .025 * H.Drainage) * S.SurfaceWater;
            S.SurfaceWater = Unit(S.SurfaceWater + PoolRate * Dt);
        }
        const double Density = Capacity > 0 ? Food / Capacity : 0;
        S.Moisture = AdvanceMoisture(C, W, H, S.Moisture, Density, Dynamics ? S.SurfaceWater : 0., Dt);
        const double Lo = H.bNatural ? H.MoistureMin : H.Plant == EPlant::Riparian ? 0.45 : (H.Plant == EPlant::Shrub ? 0.18 : 0.30);
        const double Hi = H.bNatural ? H.MoistureMax : H.Plant == EPlant::Riparian ? 0.95 : (H.Plant == EPlant::Shrub ? 0.65 : 0.75);
        const double Dry = Unit((Lo - S.Moisture) / Lo);
        const double Wet = Unit((S.Moisture - Hi) / (1 - Hi));
        const double Flood = Dynamics ? std::max(H.Flood, .55 * S.SurfaceWater) : H.Flood;
        const double FloodStress = Flood * (H.Plant == EPlant::Riparian ? 0.1 : 1.0);
        const double TargetStress = std::max({Dry, Wet, FloodStress, H.bGroundUsable ? 0.0 : 1.0,H.bNatural?(1-H.SiteSuitability):0.});
        S.Stress = Unit(S.Stress + (TargetStress - S.Stress) * (1 - std::exp(-Dt / 8.0)));
        // Loss precedes growth; both are explicit non-negative ledger terms.
        O.Loss = H.bGroundUsable
            ? DisturbanceLoss + (Food - DisturbanceLoss) * (1 - std::exp(-C.StressLoss * S.Stress * Dt)) : Food;
        const double Remaining = Food - O.Loss;
        const double TempSuit = H.bNatural?EcoNaturalHabitat::Triangle(W.Temperature,H.TemperatureMin,H.TemperatureOptimum,H.TemperatureMax):Unit(1 - std::abs(W.Temperature - 20) / 30);
        const double LightSuit=H.bNatural?W.Light*(1-H.Shade*(1-H.ShadeTolerance)):(0.2+0.8*W.Light);
        double Suit = (1 - TargetStress) * LightSuit * TempSuit;
        if (Dynamics)
        {
            const double RecoverySeconds = H.Plant == EPlant::Shrub ? 300 : 140;
            const double Recovery = std::exp(-Dt * (.25 + .75 * Suit) / RecoverySeconds);
            S.BrowsePressure *= Recovery;
            S.Disturbance *= Recovery;
            Suit *= (1 - .78 * S.BrowsePressure) * (1 - .60 * S.Disturbance);
        }
        if(H.bNatural){
            // A depleted stand recruits gradually from a simplified seed/root bank.
            // Thermal/light/moisture time advances within the Native food transaction only.
            if(Capacity<=0||!H.bGroundUsable)S.Development=0;
            else{
                if(Remaining<=1.e-8)S.Development=0;
                S.Development=Unit(S.Development+Dt*Suit/H.MaturationSeconds);
            }
        }
        O.Growth = H.bGroundUsable ? std::min(Capacity - Remaining, RegenPerStep * Suit * (Capacity - Remaining)*(H.bNatural?.2+.8*S.Development:1.)) : 0;
        O.Food = Remaining + O.Growth;
        if (Dynamics)
        {
            const double Fresh = S.FreshFraction * std::exp(-Dt * (1 + S.Stress) / 100);
            S.FreshFraction = O.Food > 0 ? Unit((Remaining * Fresh + O.Growth) / O.Food) : 0;
        }
        return O;
    }
}

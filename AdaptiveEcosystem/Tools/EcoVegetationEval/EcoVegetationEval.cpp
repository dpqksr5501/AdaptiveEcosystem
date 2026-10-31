// Engine-free soil-v1/native integration evaluation. This is not Python parity,
// a terrain test, or a server performance benchmark. Emits JSON to stdout.
#include "EcoWorldV3.h"
#include <algorithm>
#include <chrono>
#include <iomanip>
#include <iostream>
#include <string>

int main()
{
    std::cout << std::setprecision(12) << "{\"schema\":1,\"world\":\"native-soil-v1\",\"python_parity\":false,\"terrain\":false,\"runs\":[";
    bool First = true;
    for (int Seed : {11, 23, 47}) for (int Climate = 0; Climate < 4; ++Climate)
    {
        EcoWorldV3::FWorldConfig C;
        C.Seed = Seed; C.NumHerbivores = 48; C.NumStalkers = 2; C.NumChasers = 2; C.NumRanged = 0;
        C.bPlayerProxy = false; C.bRespawnDead = false; C.Vegetation.bEnabled = Climate != 0;
        EcoWorldV3::FReferenceWorld R; R.Init(C);
        auto& G = R.World.Food;
        const double Initial = G.Total(); std::vector<double> Cpu; double MaxError = 0;
        for (int Step = 0; Step < 4500; ++Step)
        {
            G.VegetationWeather = {Climate == 1 ? 0.5 : (Climate == 3 ? 1.0 : 0.0), Climate == 2 ? 30.0 : 20.0, 1.0};
            if (Climate == 3) for (auto& H : G.Habitats) H.Flood = 1;
            const double Before = G.Total(), Ate = R.World.Stats.FoodEaten, Grown = G.VegetationGrown, Lost = G.EnvironmentLost;
            const auto Start = std::chrono::steady_clock::now(); R.StepOnce();
            Cpu.push_back(std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - Start).count());
            if (Climate != 0)
                MaxError = std::max(MaxError, std::abs(Before - (R.World.Stats.FoodEaten-Ate) + (G.VegetationGrown-Grown) - (G.EnvironmentLost-Lost) - G.Total()));
            // Match integration's removal of dead slots from subsequent logical steps.
            std::erase_if(R.Views, [](const auto& H) { return H.Body->DeathCause != EcoWorldV3::kDeathNone; });
        }
        std::sort(Cpu.begin(), Cpu.end());
        double Moisture = 0; for (const auto& S : G.VegetationCells) Moisture += S.Moisture;
        if (!First) std::cout << ','; First = false;
        static const char* Names[] = {"off", "rain", "dry", "flood_grass"};
        std::cout << "{\"seed\":" << Seed << ",\"climate\":\"" << Names[Climate] << "\",\"simulation_seconds\":600,\"initial_deer\":48,\"wolves\":4"
            << ",\"survivors\":" << R.Views.size() << ",\"caught\":" << R.World.Stats.Caught << ",\"starved\":" << R.World.Stats.Starved
            << ",\"initial_food\":" << Initial << ",\"food\":" << G.Total() << ",\"consumed\":" << R.World.Stats.FoodEaten
            << ",\"grown\":" << G.VegetationGrown << ",\"environment_lost\":" << G.EnvironmentLost
            << ",\"mean_moisture\":" << (G.VegetationCells.empty() ? 0 : Moisture/G.VegetationCells.size())
            << ",\"balance_checked\":" << (Climate != 0 ? "true" : "false")
            << ",\"max_step_balance_error\":" << MaxError << ",\"native_reference_step_p95_us\":" << Cpu[4274] << '}';
        if (MaxError > 1.e-6) return 2;
    }
    std::cout << "]}\n";
}

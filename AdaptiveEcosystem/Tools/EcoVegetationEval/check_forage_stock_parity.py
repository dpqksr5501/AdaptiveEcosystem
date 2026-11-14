"""Compare a Python forage transaction with the Unreal stock arithmetic.

Pass a path to MSVC vcvars64.bat. The probe compiles the selected method bodies
from the working tree against a minimal math shim and uses a temporary directory.
The authority log and fixture replay modes only require the Python standard library.
"""

import argparse
import json
import math
import re
import struct
import subprocess
import tempfile
from collections import Counter
from pathlib import Path


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def clamp(value, upper=1.):
    return min(upper, max(0., value))


DEFAULT_PATCH = (9., .2, .06, .45, 2.8, 0., 18., 42., .75, 1.25)


def python_transaction(temperature, rain, humidity, moisture, stock, dt, deficits, patch):
    capacity, regen, dry_loss, need, portion = map(f32, patch[:5])
    cold, optimum, hot, dry_rain, wet_rain = patch[5:]
    rain, humidity, stock = map(f32, (rain, humidity, stock))
    if moisture < 0:
        moisture = clamp(rain) + .35 * (clamp(humidity) - clamp(rain))
    stress = clamp(1. - moisture / need) if need > 0. else 0.
    thermal = clamp(min((temperature - cold) / (optimum - cold), (hot - temperature) / (hot - optimum)))
    growth = thermal * (dry_rain + (wet_rain - dry_rain) * clamp(rain)) * (1. - stress) ** 2
    rate = regen * growth - dry_loss * stress * stock / capacity
    stock = clamp(f32(stock + f32(dt * rate)), capacity)
    before_meals = stock
    payments = []
    for deficit in deficits:
        payment = min(stock, portion, f32(deficit))
        if payment < f32(.2):
            payment = 0.
        stock = f32(stock - payment)
        payments.append(payment)
    return [stress, before_meals, *payments, stock]


def source_probe():
    runtime = Path(__file__).resolve().parents[2] / "Source/AdaptiveEcosystem/Creature/Runtime"
    header = (runtime / "EcoFauna.h").read_text(encoding="utf-8")
    body = (runtime / "EcoFauna.cpp").read_text(encoding="utf-8")
    plant = header[header.index("    double PlantRecoveryMultiplier("):header.index("    bool Shelters(")]
    meals = header[header.index("    float TakeMeal("):header.index("};", header.index("    float TakeMeal("))]
    start = body.index("            const double Growth = Patch.PlantRecoveryMultiplier(")
    stock_assignment = body.index("            Stock = FMath::Clamp(", start)
    update = body[start:body.index("\n", stock_assignment)]
    return '''#include <algorithm>
#include <iomanip>
#include <iostream>
struct FVector { double X, Y, Z; };
struct FVector2D { double X, Y; };
struct FMath {
    template<class T> static T Min(T a, T b) { return std::min(a, b); }
    template<class T> static T Min3(T a, T b, T c) { return std::min({a,b,c}); }
    template<class T> static T Clamp(T x, T lo, T hi) { return std::clamp(x,lo,hi); }
    template<class T> static T Lerp(T a,T b,T u) { return a + (b-a)*u; }
    template<class T> static T Square(T x) { return x*x; }
};
struct PatchType {
    FVector PlantGrowthTemperature{0.,18.,42.};
    FVector2D PlantGrowthRainfall{.75,1.25};
    float Capacity=9.f, RegrowthPerSecond=.2f, PlantDryLossPerSecond=.06f, PlantMoistureNeed=.45f, EnergyPerMeal=2.8f;
''' + plant + meals + '''};
int main() {
    PatchType Patch;
    struct { double Temperature; float Rainfall, Humidity; } Weather;
    double Soil, PatchDelta;
    float Stock = 0.f, InputStock, First, Second;
    std::cout << std::setprecision(17);
    while (std::cin >> Weather.Temperature >> Weather.Rainfall >> Weather.Humidity >> Soil >> InputStock >> PatchDelta >> First >> Second
                    >> Patch.Capacity >> Patch.RegrowthPerSecond >> Patch.PlantDryLossPerSecond >> Patch.PlantMoistureNeed >> Patch.EnergyPerMeal
                    >> Patch.PlantGrowthTemperature.X >> Patch.PlantGrowthTemperature.Y >> Patch.PlantGrowthTemperature.Z
                    >> Patch.PlantGrowthRainfall.X >> Patch.PlantGrowthRainfall.Y) {
        if (InputStock >= 0.f) Stock = InputStock;
        const double Stress = Soil < 0. ? Patch.PlantDryStress(Weather.Rainfall, Weather.Humidity) : Patch.PlantDryStressFromMoisture(Soil);
''' + update + '''
        auto before = Stock;
        auto first = Patch.TakeMeal(Stock, First);
        auto second = Patch.TakeMeal(Stock, Second);
        std::cout << Stress << ' ' << before << ' ' << first << ' ' << second << ' ' << Stock << '\\n';
    }
}
'''


def island_sequences():
    fixture = Path(__file__).resolve().parents[2] / "Docs/RL_Policy/Examples/island_forage_soil_actual_20261114.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    profiles = {  # author_jyu_herbivore_forage.py GROWTH and DRY_RESPONSE
        "IslandForageWestMeadow": (.30, 2., 19., 38., .48, 1.14),
        "IslandForageFloodplainApproach": (.54, 2., 17., 36., .28, 1.36),
        "IslandForageApproachForbs": (.43, 5., 17., 33., .22, 1.27),
    }
    for name, (need, *growth) in profiles.items():
        budget = data["patch_budget"][name]
        patch = (budget["capacity"], budget["regrowth_per_second"], budget["dry_loss_per_second"],
                 need, budget["energy_per_meal"], *growth)
        yield [(18., rain, .5, moisture, budget["capacity"] * .25 if tick == 0 else -1., 2. / 15.,
                (5., 5.) if tick % 40 == 39 else (0., 0.), patch)
               for tick, (rain, moisture) in enumerate([(0., .20)] * 150 + [(.7, .62)] * 450 + [(0., .38)] * 225)]


AUTHORITY_EVENT = re.compile(r"\[Eco Forage (Stock|Payment)\] (.+)")


def replay_authority(events, label):
    tracked = {}
    growth_count = payment_count = 0
    rejections = Counter()
    for kind, row in events:
        patch, *fields = row.split()
        values = {k: v if k == "Gate" else float(v) for k, v in (field.split("=", 1) for field in fields)}
        if kind == "Stock":
            before = values["Before"]
            if patch in tracked:
                previous_time, previous_stock, _ = tracked[patch]
                if before != previous_stock or values["At"] < previous_time:
                    raise AssertionError(f"Discontinuous stock for {patch}: {row}")
            params = tuple(values[key] for key in ("Capacity", "Regen", "DryLoss", "Need", "Portion",
                                                    "Cold", "Optimum", "Hot", "DryRain", "WetRain"))
            _, after, *_ = python_transaction(values["T"], values["Rain"], values["Humidity"], values["Soil"],
                                              before, values["Delta"], (0., 0.), params)
            growth_count += 1
        else:
            previous_time, before, params = tracked[patch]
            if previous_time != values["At"]:
                raise AssertionError(f"Payment without matching stock tick for {patch}: {row}")
            gate = values.get("Gate", "Transaction")
            if gate not in {"Eligibility", "Distance", "Sight", "Transaction"}:
                raise AssertionError(f"Unknown feed gate: {row}")
            if gate != "Eligibility" and "DistanceSquared" in values:
                if (values["DistanceSquared"] > 35. ** 2) != (gate == "Distance"):
                    raise AssertionError(f"Distance decision mismatch: {row}")
            expected = 0.
            if gate == "Transaction":
                candidate = min(before, f32(params[4]), f32(values["Deficit"]))
                if candidate >= f32(.2):
                    expected = candidate
            if expected != values["Paid"]:
                raise AssertionError(f"Payment mismatch for {patch}: {row}")
            after = f32(before - expected)
            if expected > 0.:
                payment_count += 1
            else:
                rejections[gate if gate != "Transaction" else "BelowMinimum"] += 1
        if after != values["After"]:
            raise AssertionError(f"Stock mismatch for {patch}: expected {after}, {row}")
        tracked[patch] = (values["At"], after, params)
    if not growth_count or not payment_count:
        raise ValueError(f"Expected recorded growth and successful payments: {label}")
    print(f"{label}: {growth_count} authority stock updates and {payment_count} payments matched exactly")
    if rejections:
        print(f"Unpaid attempts with unchanged stock: {dict(rejections)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("vcvars", type=Path, nargs="?")
    mode.add_argument("--authority-log", type=Path, help="Replay logged Unreal stock and payment events")
    mode.add_argument("--authority-fixture", type=Path, help="Replay each trace in a portable Unreal log excerpt")
    args = parser.parse_args()
    if args.authority_log:
        events = AUTHORITY_EVENT.findall(args.authority_log.read_text(encoding="utf-8-sig", errors="replace"))
        replay_authority(events, args.authority_log.name)
        return
    if args.authority_fixture:
        fixture = json.loads(args.authority_fixture.read_text(encoding="utf-8"))
        if fixture["schema_version"] != 1 or not fixture["traces"]:
            parser.error("expected a non-empty forage authority fixture with schema_version 1")
        for trace in fixture["traces"]:
            events = [AUTHORITY_EVENT.fullmatch(line).groups() for line in trace["events"]]
            replay_authority(events, f"seed {trace['seed']}")
        return
    weather = ((18., .7, .4), (28., 0., .2), (45., 1., .9))
    cases = [(*conditions, soil, stock, dt, deficits, DEFAULT_PATCH)
             for conditions in weather for soil in (-1., .05, .25, .60)
             for stock in (.19, .2, .425, 3.1, 8.95)
             for dt in (0., .133333333333, 1.) for deficits in ((0., 0.), (.19, 2.), (5., 5.))]
    independent_count = len(cases)
    for sequence in island_sequences():
        cases.extend(sequence)
    with tempfile.TemporaryDirectory() as path:
        work = Path(path)
        (work / "probe.cpp").write_text(source_probe(), encoding="utf-8")
        (work / "build.cmd").write_text(f'@call "{args.vcvars.resolve(strict=True)}" >nul\n'
                                       'if errorlevel 1 exit /b 1\ncl /nologo /std:c++17 /EHsc probe.cpp\n', encoding="utf-8")
        subprocess.run(["cmd.exe", "/d", "/c", "build.cmd"], cwd=work, check=True)
        payload = "".join(" ".join(map(str, (*row[:-2], *row[-2], *row[-1]))) + "\n" for row in cases)
        result = subprocess.run([str(work / "probe.exe")], cwd=work, input=payload,
                                capture_output=True, text=True, check=True)
    maximum = 0.
    previous_stock = 0.
    for case, row in zip(cases, result.stdout.splitlines(), strict=True):
        temperature, rain, humidity, soil, stock, dt, deficits, patch = case
        expected = python_transaction(temperature, rain, humidity, soil,
                                      stock if stock >= 0. else previous_stock, dt, deficits, patch)
        previous_stock = expected[-1]
        actual = [float(value) for value in row.split()]
        maximum = max(maximum, *(abs(a-b) for a, b in zip(expected, actual, strict=True)))
        if not all(math.isclose(a, b, abs_tol=1e-10, rel_tol=0.) for a, b in zip(expected, actual, strict=True)):
            raise AssertionError((case, expected, actual))
    print(f"{independent_count} independent and {len(cases) - independent_count} chained forage transactions, "
          f"maximum absolute error {maximum:.3g}")


if __name__ == "__main__":
    main()

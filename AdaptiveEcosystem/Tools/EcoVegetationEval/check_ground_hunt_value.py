"""Recalculate ground hunt candidate values and check logged choice outcomes."""

import argparse
from collections import Counter, defaultdict
import json
from math import isclose
from pathlib import Path
import re


def hunt_value(expected_energy, travel_and_handling_seconds, risk):
    return max(0., expected_energy - risk) / (1. + travel_and_handling_seconds)


def read_cases(log, species):
    candidates = defaultdict(list)
    cases = []
    with log.open(encoding="utf-8-sig", errors="replace") as source:
        for line in source:
            if "[Eco Hunt Audit]" not in line or "At=" not in line:
                continue
            fields = dict(re.findall(r"(\w+)=(\S+)", line))
            if fields.get("HunterSpecies", fields.get("Species")) != species:
                continue
            key = fields.get("Hunter"), fields["At"]
            if fields["Event"] == "Candidate" and fields.get("Medium") == "Ground":
                sample = {field: float(fields[field]) for field in (
                    "PreyMaturity", "PreyHealth", "EnergyFraction", "Stamina", "ExpectedEnergy", "CostSeconds",
                    "Risk", "BaseScore", "Score")}
                candidates[key].append(dict(sample, target=fields["Target"], target_species=fields["TargetSpecies"]))
            if fields["Event"] == "GroundChoice":
                cases.append({"at": float(fields["At"]), "hunter": fields["Hunter"], "candidates": candidates.pop(key, []),
                              "live": float(fields["LiveScore"]), "patch": float(fields["PatchScore"]),
                              "carrion": float(fields["ComparedCarrionScore"]), "selected": fields["SelectedPrey"]})
    if candidates:
        raise AssertionError("Found scored candidates without their ground choice")
    return cases


def verify(cases):
    if not cases:
        raise AssertionError("Expected at least one ground food choice")
    outcomes, targets = Counter(), Counter()
    for case in cases:
        candidates = case["candidates"]
        if not candidates:
            raise AssertionError(f"Missing candidates at {case['at']}")
        for prey in candidates:
            targets[prey["target_species"]] += 1
            value = hunt_value(prey["ExpectedEnergy"], prey["CostSeconds"], prey["Risk"])
            if not isclose(value, prey["BaseScore"], rel_tol=1e-12, abs_tol=1e-12):
                raise AssertionError(f"Candidate score mismatch at {case['at']}")
        if case["selected"] != "0":
            if not any(prey["target"] == case["selected"] and prey["Score"] > 0. for prey in candidates):
                raise AssertionError(f"Selected prey has no positive candidate score at {case['at']}")
            outcomes["live_selected"] += 1
        elif all(prey["BaseScore"] == 0. for prey in candidates):
            outcomes["all_candidates_zero"] += 1
        else:
            outcomes["positive_candidates_without_live_selection"] += 1
    return {"choices": len(cases), "candidates_by_species": dict(targets), "outcomes": dict(outcomes)}


def compare_leopard_rat_states(cases):
    """Vary one state at a time for the first recorded, undefended adult rat encounter."""
    sample = cases[0]["candidates"][0]
    if (sample["target_species"] != "Rat" or sample["PreyMaturity"] != 1. or sample["PreyHealth"] != 1.
            or not isclose(sample["Risk"], 2. + (1. - sample["Stamina"]) * 5., abs_tol=1e-8)):
        raise AssertionError("Expected a healthy adult rat with zero resistance")

    energy = sample["ExpectedEnergy"]
    seconds = sample["CostSeconds"]
    observed_risk = sample["Risk"]
    recovered_risk = 2.
    hungrier_energy_fraction = sample["EnergyFraction"] * .5
    # The matched encounter has zero prey resistance. Even with the adaptive
    # coefficient enabled, the hunger multiplier cannot change that term.
    fatigue_risk = (1. - sample["Stamina"]) * 5.
    risk_weight = .45 + .55 * hungrier_energy_fraction
    hungrier_risk = 2. + 0. * risk_weight + fatigue_risk
    injured_energy = energy * (1. + .35 * (1. - .5))
    rows = {
        "observed": hunt_value(energy, seconds, observed_risk),
        "hungrier_same_encounter": hunt_value(energy, seconds, hungrier_risk),
        "injured_rat_same_stamina": hunt_value(injured_energy, seconds, observed_risk),
        "recovered_same_rat": hunt_value(energy, seconds, recovered_risk),
        "injured_rat_after_recovery": hunt_value(injured_energy, seconds, recovered_risk),
    }
    if rows["observed"] != rows["hungrier_same_encounter"] or rows["recovered_same_rat"] != 0.:
        raise AssertionError("Hunger or recovery alone should not make the healthy rat profitable")
    if rows["injured_rat_after_recovery"] <= 0.:
        raise AssertionError("Recovery and prey injury should produce a positive score")
    return {"at": cases[0]["at"], "observed_stamina": sample["Stamina"],
            "hungrier_energy_fraction": hungrier_energy_fraction, "injured_rat_health": .5,
            "stamina_threshold_for_positive_score": 1. - (injured_energy - 2.) / 5.,
            "base_scores": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--species", default="Leopard")
    parser.add_argument("--compare-rat-states", action="store_true")
    args = parser.parse_args()
    if args.input.suffix.lower() != ".json":
        cases = read_cases(args.input, args.species)
        print(json.dumps(verify(cases), indent=2))
        if args.compare_rat_states:
            print(json.dumps(compare_leopard_rat_states(cases), indent=2))
        return
    fixture = json.loads(args.input.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != 1 or not fixture.get("runs"):
        parser.error("expected ground hunt cases with schema_version 1")
    for run in fixture["runs"]:
        result = verify(run["cases"])
        if result != run["summary"]:
            raise AssertionError(f"Seed {run['seed']}: summary disagrees with candidates and choices")
        print(f"Seed {run['seed']}: {result}")
        if args.compare_rat_states:
            print(json.dumps(compare_leopard_rat_states(run["cases"]), indent=2))


if __name__ == "__main__":
    main()

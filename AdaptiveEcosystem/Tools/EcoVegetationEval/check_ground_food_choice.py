"""Check ground-forage ranking and compare observed access and payment receipts."""

import argparse
import json
import math
from pathlib import Path


def active_request(requests, at, region, lifetime):
    latest = next((row for row in reversed(requests) if row["issued_at"] <= at), None)
    if latest and latest["region"] == region and at - latest["issued_at"] < lifetime:
        return latest["patch"]
    return None


def check_ranking(run, rules):
    for decision in run["decisions"]:
        request = active_request(run["requests"], decision["at"], decision["region"], rules["request_lifetime"])
        best, selected = 0., "None"
        for candidate in decision["candidates"]:
            patch = candidate["patch"]
            budget = run["patches"][patch]
            stock = candidate["stock"]
            if stock < rules["minimum_stock"]:
                raise AssertionError(f"Unavailable patch entered ranking: {patch}")
            base = (min(stock, 3 * budget["energy_per_meal"]) * rules["plant_preference"][budget["guild"]]
                    / (2 + candidate["distance_cm"] / rules["walk_speed_cm_s"]))
            score = base * rules["request_multiplier"] if patch == request else base
            if not (math.isclose(base, candidate["base_score"], rel_tol=2e-5)
                    and math.isclose(score, candidate["ranked_score"], rel_tol=2e-5)):
                raise AssertionError(f"{run['label']} {decision['at']}: score mismatch for {patch}")
            if score > best:
                best, selected = score, patch
        if selected != decision["selected"]:
            raise AssertionError(f"{run['label']} {decision['at']}: expected {selected}")
    print(f"{run['label']}: {len(run['decisions'])} ground decisions matched")


def candidate_inputs(decision):
    return [(c["patch"], c["access_point"], c["distance_cm"], c["stock"]) for c in decision["candidates"]]


def check_switch(control, trial, rules):
    start, changed = (run["decisions"][0] for run in (control, trial))
    if start["at"] != changed["at"]:
        raise AssertionError("Control and request must start at the same decision")
    if candidate_inputs(start) != candidate_inputs(changed) or start["selected"] == changed["selected"]:
        raise AssertionError("Expected a target switch using identical eligible candidates")
    for run, decision in ((control, start), (trial, changed)):
        first_payment = next(row for row in run["observed_payments"] if row["at"] > decision["at"])
        if first_payment["patch"] != decision["selected"] or first_payment["paid"] < rules["minimum_stock"]:
            raise AssertionError("Expected the next observed payment from the initially chosen patch")


def check_patch_trial(trial, rules, changed_field):
    control, treatment = trial["runs"]
    affected = trial["changed_patch"]
    if control["patches"].keys() != treatment["patches"].keys():
        raise AssertionError("Expected identical forage patch IDs")
    budget_changes = {(patch, field) for patch in control["patches"] for field in control["patches"][patch]
                      if control["patches"][patch][field] != treatment["patches"][patch][field]}
    if budget_changes != {(affected, changed_field)}:
        raise AssertionError(f"{changed_field} must be the only forage budget change")
    for run in (control, treatment):
        check_ranking(run, rules)
    control_decisions = {row["at"]: row for row in control["decisions"]}
    paired = 0
    differences = 0
    for row in treatment["decisions"]:
        baseline = control_decisions.get(row["at"])
        if baseline is None:
            continue
        if candidate_inputs(row) == candidate_inputs(baseline) and any(c["patch"] == affected for c in row["candidates"]):
            paired += 1
            differences += row["selected"] != baseline["selected"]
    if not paired:
        raise AssertionError("Expected same-input decisions in the two plant guild runs")
    if differences != trial["expected_same_input_switches"]:
        raise AssertionError("Unexpected number of controlled target switches")
    print(f"Seed {trial['seed']}: {paired} same-input decisions; {changed_field} changed {differences} selections")
    if changed_field == "energy_per_meal":
        cap = treatment["patches"][affected][changed_field]
        if not math.isclose(cap, .5 * control["patches"][affected][changed_field]):
            raise AssertionError("Expected a halved meal cap")
        receipts = [p for p in treatment["observed_payments"] if p["patch"] == affected]
        if not receipts or any(p["paid"] > cap + .0005 for p in receipts):
            raise AssertionError("Expected consumption within the smaller meal cap")


def check_payment_gates(run):
    counts = {}
    for attempt in run["attempts"]:
        gate = attempt["gate"]
        stock, remaining, paid = (attempt[key] for key in ("stock", "remaining", "paid"))
        if gate in {"Distance", "Sight", "Transaction"} and (
            (attempt["distance_squared"] > 35 ** 2) != (gate == "Distance")
        ):
            raise AssertionError("Distance gate disagrees with the 35 cm eating reach")
        if gate not in {"Eligibility", "Distance", "Sight", "Transaction"}:
            raise AssertionError(f"Unknown ground payment gate {gate}")
        candidate = min(stock, run["energy_per_meal"], attempt["headroom"])
        expected = candidate if gate == "Transaction" and candidate >= .2 else 0.
        if paid != expected or not math.isclose(remaining, stock - paid, abs_tol=1e-6):
            raise AssertionError(f"{run['seed']} {attempt['at']}: payment or stock mismatch")
        outcome = "Paid" if paid else "BelowMinimum" if gate == "Transaction" else gate
        counts[outcome] = counts.get(outcome, 0) + 1
    if "Paid" not in counts or "BelowMinimum" not in counts:
        raise AssertionError("Expected both payment and an attempt below the minimum")
    print(f"{run['seed']}: {counts}")


def check_shore_access(pair):
    control, saved = pair["root_only"], pair["bank_access"]
    for field in ("stock_at_start", "meal_cap", "surface_z_cm", "root_cm", "start_cm", "wade_depth_cm"):
        if control[field] != saved[field]:
            raise AssertionError(f"Shore access starting state differs: {field}")
    inundation = control["surface_z_cm"] - control["root_cm"][2]
    for species, limit in control["wade_depth_cm"].items():
        passes_root = inundation <= limit
        if any(checks != {"to_patch": True, "from_patch": True}
               for checks in control["low_water_routes"][species].values()):
            raise AssertionError(f"Expected clear ground at low water for {species}")
        for checks in control["active_water_routes"][species].values():
            if checks != {"to_patch": passes_root, "from_patch": passes_root}:
                raise AssertionError(f"Root depth alone did not explain the sampled {species} routes")
    if (control["min_sampled_root_distance_cm"] > 35 or control["payments"]
            or control["stock_at_end"] < control["meal_cap"]):
        raise AssertionError("Expected root contact range without payment in high water")
    if control["surface_z_cm"] - saved["extra_access_cm"][2] > saved["wade_depth_cm"]["Horse"]:
        raise AssertionError("Expected a wadeable alternate shore point")
    if not saved["payments"] or any(row["access"] != 1 or not 0 < row["amount"] <= saved["meal_cap"] + .0005
                                    for row in saved["payments"]):
        raise AssertionError("Expected one shared stock to pay via the alternate point")
    print(f"Seed {pair['seed']}: root was within reach without payment; {len(saved['payments'])} bank payments")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture["schema_version"] != 1 or not any(fixture.get(key) for key in ("ranking", "guild_trials", "meal_trials", "shore_access")):
        parser.error("expected ground forage fixtures with schema_version 1")
    for run in fixture.get("ranking", ()):
        check_ranking(run, fixture["rules"])
    if fixture.get("controlled_switch"):
        ranking = {run["label"]: run for run in fixture["ranking"]}
        control, trial = fixture["controlled_switch"]
        check_switch(ranking[control], ranking[trial], fixture["rules"])
    for run in fixture.get("guild_trials", ()):
        check_patch_trial(run, fixture["rules"], "guild")
    for run in fixture.get("meal_trials", ()):
        check_patch_trial(run, fixture["rules"], "energy_per_meal")
    for run in fixture.get("payment_gates", ()):
        check_payment_gates(run)
    for pair in fixture.get("shore_access", ()):
        check_shore_access(pair)


if __name__ == "__main__":
    main()

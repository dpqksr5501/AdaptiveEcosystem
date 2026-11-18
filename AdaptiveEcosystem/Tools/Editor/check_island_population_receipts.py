"""Compare two island population reports and check logged regional food balances."""

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path
import re

from summarize_fauna_runtime import compare_island_baseline, summarize


def milestones(report):
    expected_seconds = {1, 1800, 3600}
    result = {}
    for row in report["samples"]:
        seconds = row["completed_clock"]["authority_seconds"]
        if seconds not in expected_seconds:
            continue
        if seconds in result:
            raise AssertionError(f"Duplicate population milestone at {seconds} seconds")
        living = [agent for agent in row["agents"] if agent["hp"] > 0]
        roster = Counter(agent["species"] for agent in living)
        if roster != row["population"] or len({agent["stable_id"] for agent in living}) != len(living):
            raise AssertionError(f"Population disagrees with living IDs at {seconds} seconds")
        result[int(seconds)] = {"population": dict(roster), "authored_stock": sum(row["stocks"].values())}
    if result.keys() != expected_seconds:
        raise AssertionError("Expected the 1, 1800 and 3600 second population samples")
    return result


def compare_population_samples(baseline, trial):
    """Compare scheduled samples and retain both actual authority times."""
    def scheduled_samples(report):
        slots = {}
        for sample in report["samples"]:
            at = sample["completed_clock"]["authority_seconds"]
            # The startup sample is scheduled at 1s. Later samples are scheduled every 30s.
            scheduled = 1 if at < 30 else int(at // 30) * 30
            if scheduled in slots:
                raise AssertionError(f"Duplicate population sample in slot {scheduled}")
            slots[scheduled] = (at, sample["population"])
        return slots

    before, after = scheduled_samples(baseline), scheduled_samples(trial)
    if before.keys() != after.keys():
        raise AssertionError("Population reports have different scheduled sample coverage")
    first_difference = None
    max_difference = Counter()
    max_time_difference = 0.
    for scheduled in sorted(before):
        (before_at, before_counts), (after_at, after_counts) = before[scheduled], after[scheduled]
        max_time_difference = max(max_time_difference, abs(before_at - after_at))
        difference = {species: after_counts.get(species, 0) - before_counts.get(species, 0)
                      for species in sorted(before_counts.keys() | after_counts.keys())
                      if before_counts.get(species, 0) != after_counts.get(species, 0)}
        if difference and first_difference is None:
            first_difference = {"scheduled_seconds": scheduled, "baseline_authority_seconds": before_at,
                                "trial_authority_seconds": after_at, "trial_minus_baseline": difference}
        for species, delta in difference.items():
            max_difference[species] = max(max_difference[species], abs(delta))
    return {"matched_slots": len(before), "first_difference": first_difference,
            "max_absolute_difference_by_species": dict(sorted(max_difference.items())),
            "max_sample_time_difference_seconds": max_time_difference}


def species_outcomes(report, trace):
    start, end = report["samples"][0]["population"], report["samples"][-1]["population"]
    births, deaths = trace["natural_births"], trace["known_death_causes"]
    meal_logs = trace["logged_first_timed_meal_by_agent"]
    transitions = trace["logged_food_receipt_transitions_by_species"]
    outcomes = {}
    for species in sorted(start.keys() | end.keys() | births.keys() | deaths.keys() | meal_logs.keys()):
        initial, final = start.get(species, 0), end.get(species, 0)
        born, causes = births.get(species, 0), deaths.get(species, {})
        meals = meal_logs.get(species, {})
        timed = meals.get("first_timed_payment_by_agent", {})
        untimed = meals.get("agents_with_untimed_payment", [])
        outcomes[species] = {
            "initial_alive": initial,
            "final_alive": final,
            "logged_births": born,
            "deaths_by_cause": causes,
            "unexplained_population_delta": final - (initial + born - sum(causes.values())),
            "agents_with_timed_payment": len(timed),
            "agents_with_untimed_payment": len(untimed),
            "first_timed_payment_authority_seconds": min(
                (row["authority_seconds"] for row in timed.values()), default=None),
            "food_receipt_transitions": transitions.get(species, {}),
        }
    cohorts = trace.get("feeding_by_birth_cohort", {}).get("species", {})
    for species, stages in cohorts.items():
        for row in stages.values():
            evidence = row["feeding_evidence"]
            timed = set(evidence["first_timed_log_by_id"])
            untimed = set(evidence["untimed_log_ids"])
            history = set(evidence["sampled_history_only_ids"])
            history.update(evidence["sampled_native_plant_intake_by_id"])
            missing = set(evidence["without_individual_receipt_ids"])
            if len(timed | untimed | history | missing) != row["count"] or missing & (timed | untimed | history):
                raise AssertionError(f"{species}: feeding evidence does not cover the cohort")
        outcomes[species]["feeding_cohorts"] = {
            stage: {"count": row["count"], "final_alive": row["alive_in_final_sample"],
                    "deaths_by_cause": row["logged_death_causes"], **row["feeding_evidence"]}
            for stage, row in stages.items()
        }
    return {"species": outcomes, "death_causes_without_species": trace["unmatched_death_causes"],
            "native_deer_plant_units": trace["native_deer_plant_units"],
            "native_wolf_reserved_nutrition": trace["native_wolf_reserved_nutrition"]}


def check_log(log):
    fields = ("Before", "Supplied", "EventLoss", "Consumed", "Rounding", "After")
    checked = Counter()
    last_steps = {}
    max_residual = Decimal(0)
    guards = 0
    with log.open(encoding="utf-8-sig", errors="replace") as file:
        for line in file:
            guards += "[Eco Fauna][GuardIntercept]" in line
            if "[Eco Food] Resource conservation failed" in line:
                raise AssertionError(line.strip())
            if "[Eco Food] Epoch=" not in line:
                continue
            values = dict(re.findall(r"(\w+)=(\S+)", line))
            before, supplied, loss, consumed, rounding, after = (Decimal(values[field]) for field in fields)
            key = (values["Epoch"], values["Region"])
            step = int(values["Step"])
            if step <= last_steps.get(key, -1) or min(before, supplied, loss, consumed, after) < 0:
                raise AssertionError(f"Invalid ledger order or amount: {line.strip()}")
            last_steps[key] = step
            residual = abs(before + supplied - loss - consumed - rounding - after)
            # Five food quantities are printed to six decimal places, rounding to nine.
            if residual > Decimal("0.000002501"):
                raise AssertionError(f"Resource balance mismatch: {line.strip()}")
            max_residual = max(max_residual, residual)
            checked[values["Region"]] += 1
    if not checked:
        raise AssertionError("No regional food ledger rows were checked")
    return {"rows_by_region": dict(checked), "max_printed_balance_residual": float(max_residual), "guard_intercepts": guards}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "trial", "log"):
        parser.add_argument(name, type=Path)
    parser.add_argument("--baseline-log", type=Path, help="Include species outcomes from both authority logs")
    parser.add_argument("--expect-policy-change", action="append", default=[], metavar="SPECIES",
                        help="Require a recorded policy change for each named species only")
    args = parser.parse_args()
    baseline, trial = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.baseline, args.trial))
    initial = compare_island_baseline(baseline, trial, policy_species=args.expect_policy_change)
    if not initial["matches"]:
        raise AssertionError(f"Initial conditions changed: {initial}")
    result = {"same_initial_conditions": initial, "baseline": milestones(baseline),
              "trial": milestones(trial), "sample_comparison": compare_population_samples(baseline, trial),
              "authority_log": check_log(args.log)}
    if args.baseline_log is not None:
        result["species_outcomes"] = {
            "baseline": species_outcomes(baseline, summarize(args.baseline, args.baseline_log)),
            "trial": species_outcomes(trial, summarize(args.trial, args.log)),
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

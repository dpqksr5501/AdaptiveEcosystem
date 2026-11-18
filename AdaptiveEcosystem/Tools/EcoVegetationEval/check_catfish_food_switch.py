"""Link audited catfish food candidates, chosen targets and committed meals."""

import argparse
from collections import Counter
import json
from math import isclose
from pathlib import Path
import re


def read_audit(path, agent):
    decisions, meals, candidates = [], [], []
    with path.open(encoding="utf-8-sig", errors="replace") as log:
        for line in log:
            water_food = "[Eco Water Food]" in line
            if not water_food and not any(event in line for event in ("[PatchMeal]", "[Scavenge]")):
                continue
            fields = dict(re.findall(r"(\w+)=([^\s]+)", line))
            if fields.get("Agent", fields.get("Eater")) != str(agent):
                continue
            if water_food:
                if "[Decision]" in line:
                    target = fields["Patch"] if fields["Patch"] != "None" else fields["Carcass"]
                    decisions.append((float(fields["At"]), target, candidates))
                    candidates = []
                else:
                    source = fields.get("Patch", fields.get("Carcass"))
                    candidate = {"source": source, "gate": fields["Gate"], "score": float(fields["Score"]),
                                 "distance_cm": float(fields["Distance"]), "range_cm": float(fields["Range"]),
                                 "stock": float(fields["Stock"])}
                    if "Meal" in fields:
                        candidate["meal_cap_with_stock"] = float(fields["Meal"])
                        candidate["base_score"] = float(fields["BaseScore"])
                        candidate["walk_speed_cm_s"] = float(fields["WalkSpeed"])
                    candidates.append(candidate)
            else:
                meals.append({"at": float(fields["At"]), "source": fields.get("Patch", fields.get("Carcass")),
                              "amount": float(fields["Amount"]), "remaining": float(fields["Remaining"])})
    return decisions, meals


def verify(decisions, meals):
    if not decisions or not meals:
        raise AssertionError("Expected water decisions and committed meals")
    scored_carcasses = 0
    for at, target, candidates in decisions:
        for entry in candidates:
            if "base_score" in entry:
                if entry["gate"] == "Visible":
                    scored_carcasses += 1
                    expected = entry["meal_cap_with_stock"] / (1. + entry["distance_cm"] / entry["walk_speed_cm_s"])
                    if not isclose(entry["base_score"], expected, rel_tol=1e-7):
                        raise AssertionError(f"{at}: carcass base score mismatch {entry}")
                elif entry["score"] != 0. or entry["base_score"] != 0.:
                    raise AssertionError(f"{at}: rejected carcass entered ranking {entry}")
        best = max((entry["score"] for entry in candidates), default=0.)
        eligible = {entry["source"] for entry in candidates if entry["score"] > 0. and entry["score"] == best}
        if (target not in eligible and eligible) or (not eligible and target != "0"):
            raise AssertionError(f"{at}: {target} disagrees with eligible top scores {eligible}")

    changes = []
    for before, after in zip(meals, meals[1:]):
        if before["source"].isdigit() == after["source"].isdigit():
            continue
        matching = [(at, candidates) for at, target, candidates in decisions
                    if target == after["source"] and before["at"] - .0005 <= at <= after["at"] + .0005]
        if not matching or after["amount"] <= 0.:
            raise AssertionError(f"No matching target choice for receipt {after}")
        at, candidates = matching[-1]
        changes.append({"before": before, "after": after, "selection_at": at,
                        "candidate_count": len(candidates),
                        "rejected_by_gate": dict(Counter(entry["gate"] for entry in candidates if entry["score"] <= 0.)),
                        "previous_source_at_selection": next((entry for entry in candidates
                                                             if entry["source"] == before["source"]), None),
                        "ranked_candidates": [entry for entry in candidates if entry["score"] > 0.]})
    if not scored_carcasses or not changes:
        raise AssertionError("Expected a choice between plant/invertebrate patches and carcasses")
    return {"decisions": len(decisions), "scored_carcasses": scored_carcasses,
            "committed_meals": len(meals), "transitions": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Unreal authority log or portable decision fixture")
    parser.add_argument("--agent", type=int, default=102)
    args = parser.parse_args()
    if args.input.suffix.lower() != ".json":
        print(json.dumps(verify(*read_audit(args.input, args.agent)), indent=2))
        return
    fixture = json.loads(args.input.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != 1 or not fixture.get("runs"):
        parser.error("expected water food decisions with schema_version 1")
    for run in fixture["runs"]:
        result = verify(run["decisions"], run["meals"])
        if len(result["transitions"]) != run["expected_transitions"]:
            raise AssertionError(f"Unexpected transition count for seed {run['seed']}")
        print(f"Seed {run['seed']}: {result['decisions']} decisions, {result['scored_carcasses']} scores, "
              f"{len(result['transitions'])} food kind changes matched")


if __name__ == "__main__":
    main()

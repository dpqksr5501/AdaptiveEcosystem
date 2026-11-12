"""Pair one runtime report with its authority log, without sampling meals or deaths."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re


def summarize(report_path, log_path):
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    if not report.get("completed") or not report.get("samples"):
        raise ValueError(f"Incomplete runtime report: {report_path}")

    species_by_id = {}
    deaths_by_id = {}
    captured_by = Counter()
    captured_targets = Counter()
    nutrition = defaultdict(Counter)
    hunts = defaultdict(Counter)
    access_rejections = defaultdict(Counter)
    contact_rejections = defaultdict(Counter)
    passages = defaultdict(Counter)
    unknown = Counter()
    resource_line = None

    with log_path.open(encoding="utf-8-sig", errors="replace") as source:
        for line in source:
            fields = dict(re.findall(r"(\w+)=([^\s]+)", line))
            species = fields.get("Species")
            if species and ("[Spawn]" in line or "[NaturalBirth]" in line):
                if key := fields.get("Id", fields.get("Child")):
                    species_by_id[key] = species
            if "[Eco Death]" in line and "ID" in fields:
                deaths_by_id[fields["ID"]] = fields["Cause"]
            if "[Eco Fauna][Predation]" in line:
                if event := re.search(r"Hunter=(\d+) (\w+) Prey=(\d+) (\w+)", line):
                    hunter_id, hunter, prey_id, prey = event.groups()
                    captured_by[hunter] += 1
                    captured_targets[prey] += 1
                    species_by_id[hunter_id] = hunter
                    species_by_id[prey_id] = prey
            if species and "Amount" in fields:
                for meal in ("Scavenge", "PatchMeal", "PlantMeal", "ParentMeal"):
                    if f"[Eco Fauna][{meal}]" in line:
                        nutrition[species][meal] += float(fields["Amount"])
            if species and "[Eco Hunt Audit]" in line:
                event = fields["Event"]
                if event == "Access":
                    hunts[species]["scans"] += 1
                    for key in ("Eligible", "Carrion", "Patch"):
                        hunts[species]["scans_with_" + key.lower()] += int(int(fields[key]) > 0)
                elif event == "Reject":
                    access_rejections[species][fields["Reason"]] += int(fields["Count"])
                else:
                    hunts[species][event] += 1
                    if event == "Miss" and "Reason" in fields:
                        contact_rejections[species][fields["Reason"]] += 1
            if species and "[Eco Passage Audit]" in line:
                passages[species][fields["Event"]] += 1
            if species and "[Eco Fauna][PassageArrived]" in line:
                passages[species]["Arrived"] += 1
            if "[Eco Integration Audit]" in line and "MotionDebt" in fields:
                resource_line = {key: fields[key] for key in ("ResourceDebt", "PolicyDebt", "MotionDebt")}

    causes = defaultdict(Counter)
    for agent, reason in deaths_by_id.items():
        species = species_by_id.get(agent)
        if species:
            causes[species][reason] += 1
        else:
            unknown[reason] += 1

    return {
        "run": report["name"],
        "seconds": report["samples"][-1]["seconds"],
        "population": report["samples"][-1]["species"],
        "regional_population": report["samples"][-1]["regional_species"],
        "native_deer_plant_units": report.get("native_deer_intake", {}).get("total"),
        "sampled_native_wolf_meat": report.get("sampled_native_wolf_meat"),
        "confirmed_vitality_energy": {
            species: {meal: round(amount, 3) for meal, amount in meals.items()}
            for species, meals in nutrition.items()
        },
        "captured_by": captured_by,
        "captured_targets": captured_targets,
        "hunt_events": hunts,
        "access_rejections": access_rejections,
        "contact_rejections": contact_rejections,
        "passage_events": passages,
        "known_death_causes": causes,
        "unmatched_death_causes": unknown,
        "clock_debt_seconds": resource_line,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("authority_log", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.report, args.authority_log), indent=2))

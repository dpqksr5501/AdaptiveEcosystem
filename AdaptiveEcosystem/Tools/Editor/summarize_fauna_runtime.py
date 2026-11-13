"""Pair one runtime report with its authority log, without sampling meals or deaths."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from statistics import median


def summarize(report_path, log_path, fixed_fps=None):
    if report_path.suffix == ".jsonl":
        report, expanded = expanded_report(report_path)
    else:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        expanded = {}
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
    candidate_evidence = defaultdict(Counter)
    carrion_times = defaultdict(set)
    deer_windows = defaultdict(list)
    wolf_reserved = []
    natural_births = defaultdict(set)
    hatches = defaultdict(Counter)
    logged_meal_times = defaultdict(set)
    frame, previous_frame = 0, None
    clock_errors = []
    unknown = Counter()
    resource_line = None

    with log_path.open(encoding="utf-8-sig", errors="replace") as source:
        for line in source:
            fields = dict(re.findall(r"(\w+)=([^\s]+)", line))
            species = fields.get("Species")
            log_seconds = None
            if fixed_fps and (stamp := re.match(r"^\[[^\]]+\]\[\s*(\d+)\]", line)):
                new_frame = int(stamp.group(1))
                if previous_frame is not None:
                    frame += (new_frame - previous_frame) % 1000
                previous_frame = new_frame
                log_seconds = frame / fixed_fps
            if "먹이: 구간 먹은 양" in line:
                window = re.search(r"\[EcoV3I\] (\S+) \| .*먹이: 구간 먹은 양 ([0-9.]+)", line)
                if window:
                    deer_windows[window.group(1)].append(float(window.group(2)))
            if "[EcoLife][Carcass]" in line and "NutritionIssued" in fields:
                wolf_reserved.append(float(fields["NutritionIssued"]))
            if species and ("[Spawn]" in line or "[NaturalBirth]" in line):
                if key := fields.get("Id", fields.get("Child")):
                    species_by_id[key] = species
            if "[NaturalBirth]" in line and (child := fields.get("Child")):
                newborn_species = species or ("Wolf" if fields.get("Predator") == "1" else "Herbivore")
                natural_births[newborn_species].add(child)
            if species and ("[AquaticHatch]" in line or "[NestHatch]" in line):
                site = fields.get("Nursery", fields.get("Nest"))
                if site:
                    hatches[species][site] += 1
            if "[Eco Death]" in line and "ID" in fields:
                deaths_by_id[fields["ID"]] = fields["Cause"]
            if "[Eco Fauna][Predation]" in line:
                if event := re.search(r"Hunter=(\d+) (\w+) Prey=(\d+) (\w+)", line):
                    hunter_id, hunter, prey_id, prey = event.groups()
                    captured_by[hunter] += 1
                    captured_targets[prey] += 1
                    species_by_id[hunter_id] = hunter
                    species_by_id[prey_id] = prey
            if hunter := species_by_id.get(fields.get("Hunter")):
                for event in ("Wounded", "Counterattack", "GuardIntercept"):
                    if f"[Eco Fauna][{event}]" in line:
                        hunts[hunter][event] += 1
            if species and "Amount" in fields:
                for meal in ("Scavenge", "PatchMeal", "PlantMeal", "ParentMeal"):
                    if f"[Eco Fauna][{meal}]" in line:
                        nutrition[species][meal] += float(fields["Amount"])
                        agent = fields.get("Agent", fields.get("Eater"))
                        if agent and log_seconds is not None:
                            logged_meal_times[(species, agent)].add(float(fields.get("At", log_seconds)))
                            if "At" in fields:
                                clock_errors.append(abs(log_seconds - float(fields["At"])))
                if "[Eco Fauna][Scavenge]" in line and "At" in fields:
                    carrion_times[(species, fields["Eater"])].add(float(fields["At"]))
            if "[Eco Hunt Audit]" in line and fields.get("Medium"):
                candidate_species = species or species_by_id.get(fields.get("Hunter"))
                if candidate_species:
                    key = (fields["Medium"], fields.get("Reason", fields["Event"]))
                    candidate_evidence[candidate_species]["/".join(key)] += 1
            if species and "[Eco Hunt Audit]" in line and not fields.get("Medium"):
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

    measured_deer = report.get("native_deer_intake", {}).get("total")
    window_deer = round(sum(sum(windows) for windows in deer_windows.values()), 3) if deer_windows else None
    frame_time_error = max(clock_errors) if clock_errors else None
    return {
        "run": report["name"],
        "seconds": report["samples"][-1]["seconds"],
        "population": report["samples"][-1]["species"],
        "regional_population": report["samples"][-1]["regional_species"],
        "native_deer_plant_units": measured_deer if measured_deer is not None else window_deer,
        "native_deer_intake_source": "captured_steps" if measured_deer is not None else "rounded_native_intervals" if deer_windows else None,
        "native_deer_logged_intervals": {region: len(windows) for region, windows in deer_windows.items()},
        "sampled_native_wolf_meat": report.get("sampled_native_wolf_meat"),
        "native_wolf_reserved_nutrition": round(sum(wolf_reserved), 6) if wolf_reserved else None,
        "confirmed_vitality_energy": {
            species: {meal: round(amount, 3) for meal, amount in meals.items()}
            for species, meals in nutrition.items()
        },
        "captured_by": captured_by,
        "captured_targets": captured_targets,
        "hunt_events": hunts,
        "access_rejections": access_rejections,
        "contact_rejections": contact_rejections,
        "candidate_evidence_by_medium": candidate_evidence,
        "committed_carrion_meal_gap_seconds": summarize_gaps(carrion_times),
        "logged_meal_gap_seconds": summarize_gaps(logged_meal_times) if frame_time_error is not None and frame_time_error <= .25 else {},
        "max_logged_meal_clock_error_seconds": round(frame_time_error, 4) if frame_time_error is not None else None,
        "passage_events": passages,
        "known_death_causes": causes,
        "natural_births": {species: len(children) for species, children in natural_births.items()},
        "hatches_by_site": hatches,
        "unmatched_death_causes": unknown,
        "clock_debt_seconds": resource_line,
        **expanded,
    }


def summarize_gaps(meals):
    gaps = defaultdict(list)
    for (species, _), times in meals.items():
        ordered = sorted(times)
        gaps[species].extend(after - before for before, after in zip(ordered, ordered[1:]))
    return {species: {"count": len(values), "median": round(median(values), 3), "max": round(max(values), 3)}
            for species, values in gaps.items() if values}


def expanded_report(path):
    status = json.loads(path.with_name(f"{path.stem}_status.json").read_text(encoding="utf-8-sig"))
    if status.get("error"):
        raise ValueError(f"Incomplete expanded run: {status['error']}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line]
    if not rows or len(rows) != status["frames"]:
        raise ValueError(f"Runtime sample count disagrees with {path.stem}_status.json")
    snapshots = [{"seconds": row["time"], "species": row["populations"], "regional_species": {}}
                 for row in rows if row["populations"]]
    events = defaultdict(set)
    meals = defaultdict(set)
    for sample in rows:
        for key, agent in {**sample.get("authority", {}), **sample.get("dead", {})}.items():
            for event in agent.get("gameplay_reason_history", ()):
                reason = event["reason"]
                marker = (key, event["time"], reason, event["related_id"])
                events[agent["species"]].add(marker)
                if event["amount"] > 0 and reason in ("PlantsEaten", "HabitatPatchEaten", "CarrionEaten", "ParentProvisioned"):
                    meals[(agent["species"], key)].add(event["time"])
    return {"name": path.stem, "samples": snapshots, "completed": True}, {
        "population_at_30_and_60_min": {str(t): sample["species"] for t in (1800, 3600)
                                       if (sample := next((s for s in snapshots if s["seconds"] >= t), None))},
        "water_crest_changes": status.get("crest_states", []),
        "sampled_authority_reasons": {species: Counter(event[2] for event in markers) for species, markers in events.items()},
        "sampled_meal_gap_seconds": summarize_gaps(meals),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("authority_log", type=Path)
    parser.add_argument("--fixed-fps", type=float, help="Read meal intervals from known fixed-FPS frame stamps")
    args = parser.parse_args()
    if args.fixed_fps is not None and args.fixed_fps <= 0:
        parser.error("--fixed-fps must be positive")
    print(json.dumps(summarize(args.report, args.authority_log, args.fixed_fps), indent=2))

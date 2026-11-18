"""Pair one runtime report with its authority log, without sampling meals or deaths."""
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import re
from statistics import median


def summarize(report_path, log_path, fixed_fps=None, *, audit_carcasses=False):
    island = None
    if report_path.suffix == ".jsonl":
        report, expanded = expanded_report(report_path)
    else:
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        expanded = {}
        if "record_gameplay_reasons" in report:
            island = report
            report, expanded = island_report(report_path, report)
    if not report.get("completed") or not report.get("samples"):
        raise ValueError(f"Incomplete runtime report: {report_path}")

    species_by_id = {}
    deaths_by_id = {}
    captured_by = Counter()
    captured_targets = Counter()
    nutrition = defaultdict(Counter)
    patch_payments = defaultdict(Counter)
    timed_patch_transactions = defaultdict(list)
    patch_payment_times = defaultdict(list)
    patch_eaters = defaultdict(set)
    patch_access_payments = defaultdict(lambda: defaultdict(Counter))
    hunts = defaultdict(Counter)
    ground_scan_opportunities = defaultdict(Counter)
    hunt_hunters = defaultdict(lambda: defaultdict(set))
    access_rejections = defaultdict(Counter)
    contact_rejections = defaultdict(Counter)
    passages = defaultdict(Counter)
    candidate_evidence = defaultdict(Counter)
    carrion_times = defaultdict(set)
    carcass_stock = {}
    carcass_closures = {}
    carcass_payments = defaultdict(list)
    carcass_releases = defaultdict(list)
    carcass_hunters = {}
    logged_food_sources = defaultdict(list)
    logged_food_receipts = defaultdict(list)
    first_timed_meal = {}
    untimed_meal_agents = defaultdict(set)
    food_intent_trace = {}
    deer_windows = defaultdict(list)
    deer_grazing_steps = defaultdict(Counter)
    wolf_reserved = []
    natural_births = defaultdict(set)
    hatches = defaultdict(Counter)
    nursery_by_child = {}
    logged_meal_times = defaultdict(set)
    frame, previous_frame = 0, None
    clock_errors = []
    unknown = Counter()
    resource_line = None

    with log_path.open(encoding="utf-8-sig", errors="replace") as source:
        for line in source:
            fields = dict(re.findall(r"(\w+)=([^\s]+)", line))
            species = fields.get("Species")
            if "[Eco Fauna][FoodIntentAccepted]" in line or "[Eco Fauna][FoodIntentRanked]" in line:
                key = (fields["Agent"], fields["IssuedAt"], fields["Region"], fields["Kind"],
                       fields["Target"], fields["Patch"])
                agent, issued, region, kind, target, patch = key
                trace = food_intent_trace.setdefault(key, {
                    "agent_id": agent, "issued_at": float(issued), "region": region,
                    "kind": int(kind), "target_id": target, "patch_id": patch, "accepted": False, "rankings": [],
                })
                if "BaseScore" in fields:
                    trace["rankings"].append({"at": float(fields["At"]), "base_score": float(fields["BaseScore"]),
                                              "ranked_score": float(fields["RankedScore"])})
                else:
                    trace["accepted"] = True
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
                    steps = re.search(r"실제로 먹은 비율 \d+% \((\d+)/(\d+) 개체·스텝\)", line)
                    if steps:
                        counts = deer_grazing_steps[window.group(1)]
                        counts["windows"] += 1
                        counts["intake_steps"] += int(steps.group(1))
                        counts["graze_action_steps"] += int(steps.group(2))
            if "[Eco Fauna][Carcass]" in line and "Remaining" in fields:
                carcass_stock[fields["Id"]] = {
                    "species": species, "medium": fields["Medium"], "total": float(fields["Total"]),
                    "native_reserved": float(fields["Native"]), "immediate_killer_payment": float(fields["Killer"]),
                    "initial_shared_stock": float(fields["Remaining"]),
                }
            if "[Eco Fauna][CarcassClosed]" in line:
                carcass_closures[fields["Id"]] = {
                    "unused_stock": float(fields["Unused"]), "authority_seconds": float(fields["At"]),
                    "reason": fields["Reason"],
                }
            if "[EcoLife][Carcass]" in line and "NutritionIssued" in fields:
                wolf_reserved.append(float(fields["NutritionIssued"]))
                carcass_hunters[fields["Prey"]] = fields["Primary"]
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
                    if "[AquaticHatch]" in line and (child := fields.get("Child")):
                        nursery_by_child[child] = site
            if "[Eco Death]" in line and "ID" in fields:
                deaths_by_id[fields["ID"]] = fields["Cause"]
            if "[Eco Fauna][Predation]" in line:
                if event := re.search(r"Hunter=(\d+) (\w+) Prey=(\d+) (\w+)", line):
                    hunter_id, hunter, prey_id, prey = event.groups()
                    captured_by[hunter] += 1
                    captured_targets[prey] += 1
                    species_by_id[hunter_id] = hunter
                    species_by_id[prey_id] = prey
                    carcass_hunters[prey_id] = hunter_id
                    hunt_hunters[hunter]["capture"].add(hunter_id)
            if "[Eco Fauna][CarrionRelease]" in line:
                carcass_releases[fields["Carcass"]].append({
                    "agent_id": fields["Agent"], "species": species, "reason": fields["Reason"],
                    "authority_seconds": float(fields["At"]), "remaining": float(fields["Remaining"]),
                })
            if hunter := species_by_id.get(fields.get("Hunter")):
                for event in ("Wounded", "Counterattack", "GuardIntercept"):
                    if f"[Eco Fauna][{event}]" in line:
                        hunts[hunter][event] += 1
            if species and "Amount" in fields:
                for meal in ("Scavenge", "PatchMeal", "PlantMeal", "ParentMeal"):
                    if f"[Eco Fauna][{meal}]" in line:
                        amount = float(fields["Amount"])
                        nutrition[species][meal] += amount
                        agent = fields.get("Agent", fields.get("Eater"))
                        if agent:
                            source = fields["Patch"] if meal == "PatchMeal" else meal
                            remaining = float(fields["Remaining"]) if meal == "PatchMeal" else None
                            logged_food_sources[(species, agent)].append((source, remaining))
                            if amount > 0:
                                logged_food_receipts[(species, agent)].append({
                                    "kind": meal, "source_id": fields.get("Patch", fields.get("Carcass")),
                                    "authority_seconds": float(fields["At"]) if "At" in fields else None,
                                    "amount": amount,
                                    "remaining": float(fields["Remaining"]) if "Remaining" in fields else None,
                                })
                            if amount > 0 and "At" in fields:
                                key = (species, agent)
                                at = float(fields["At"])
                                previous = first_timed_meal.get(key)
                                if previous is None or at < previous["authority_seconds"]:
                                    first_timed_meal[key] = {"authority_seconds": at, "meal": meal,
                                                             "source": fields.get("Patch", fields.get("Carcass")),
                                                             "amount": amount}
                            elif amount > 0:
                                untimed_meal_agents[species].add(agent)
                        if meal == "PatchMeal" and (patch := fields.get("Patch")):
                            patch_payments[patch][species] += float(fields["Amount"])
                            if agent and amount > 0 and "At" in fields:
                                timed_patch_transactions[(patch, float(fields["At"]))].append({
                                    "species": species, "agent_id": agent, "paid": amount,
                                    "remaining": float(fields["Remaining"]),
                                })
                            if island and "population_target_seconds" in island and "At" in fields:
                                patch_payment_times[patch].append(float(fields["At"]))
                            if (access := fields.get("Access")) is not None:
                                patch_access_payments[patch][access][species] += float(fields["Amount"])
                            if agent:
                                patch_eaters[patch].add(agent)
                        if agent and log_seconds is not None:
                            logged_meal_times[(species, agent)].add(float(fields.get("At", log_seconds)))
                            if "At" in fields:
                                clock_errors.append(abs(log_seconds - float(fields["At"])))
                if "[Eco Fauna][Scavenge]" in line and "At" in fields:
                    carrion_times[(species, fields["Eater"])].add(float(fields["At"]))
                if "[Eco Fauna][Scavenge]" in line:
                    carcass_payments[fields["Carcass"]].append({
                        "agent_id": fields["Eater"], "species": species, "amount": float(fields["Amount"]),
                        "remaining": float(fields["Remaining"]), "authority_seconds": float(fields["At"]) if "At" in fields else None,
                    })
            if "[Eco Hunt Audit]" in line and fields.get("Medium"):
                candidate_species = species or species_by_id.get(fields.get("Hunter"))
                if candidate_species:
                    key = (fields["Medium"], fields.get("Reason", fields["Event"]))
                    candidate_evidence[candidate_species]["/".join(key)] += 1
            if species and "[Eco Hunt Audit]" in line and not fields.get("Medium"):
                event = fields["Event"]
                if event == "Access":
                    hunts[species]["scans"] += 1
                    hunt_hunters[species]["ground_scan"].add(fields["Hunter"])
                    options = tuple(label for field, label in (("Eligible", "live"), ("Carrion", "carrion"),
                                                               ("Patch", "patch")) if int(fields[field]) > 0)
                    ground_scan_opportunities[species]["+".join(options) or "none"] += 1
                    for key in ("Eligible", "Carrion", "Patch"):
                        hunts[species]["scans_with_" + key.lower()] += int(int(fields[key]) > 0)
                elif event == "Reject":
                    access_rejections[species][fields["Reason"]] += int(fields["Count"])
                else:
                    hunts[species][event] += 1
                    if event in ("Acquire", "Windup", "Timeout", "Miss"):
                        hunt_hunters[species][event].add(fields["Hunter"])
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
    if island and island.get("shore_rain"):
        expanded["sampled_shore_and_hatch_outcomes"] = summarize_shore_and_hatches(island, nursery_by_child)
    if island and island.get("nursery_fry"):
        expanded["sampled_nursery_fry"] = summarize_nursery_fry(island["nursery_fry"])
    if island:
        expanded["feeding_by_birth_cohort"] = summarize_birth_cohorts(
            island, natural_births, deaths_by_id, first_timed_meal, untimed_meal_agents)
        if phase_activity := summarize_phase_activity(island["samples"]):
            expanded["sampled_activity_by_clock_phase"] = phase_activity
        if island.get("patch_budget"):
            expanded["sampled_ground_forage_stock"] = summarize_ground_forage_stock(island)
        if "population_target_seconds" in island:
            expanded["island_authored_stock_samples"] = summarize_population_stock(island, patch_payment_times)
    if audit_carcasses:
        missing = (carcass_payments.keys() | carcass_closures.keys()) - carcass_stock.keys()
        if not carcass_stock or missing:
            raise AssertionError(f"Incomplete carcass creation records: {sorted(missing)}")
        expanded["carcass_balance_audit"] = {
            "created": len(carcass_stock), "closed": len(carcass_closures),
            "payments": sum(map(len, carcass_payments.values())),
            "max_payment_residual": audit_carcass_balances(carcass_stock, carcass_payments, carcass_closures),
            "shared_across_species": {
                carcass: payments for carcass, payments in carcass_payments.items()
                if len({payment["species"] for payment in payments}) > 1
            },
        }
    return {
        "run": report["name"],
        "seconds": report["samples"][-1]["seconds"],
        "population": report["samples"][-1]["species"],
        "regional_population": report["samples"][-1]["regional_species"],
        "native_deer_plant_units": measured_deer if measured_deer is not None else window_deer,
        "native_deer_intake_source": "captured_steps" if measured_deer is not None else "rounded_native_intervals" if deer_windows else None,
        "native_deer_logged_intervals": {region: len(windows) for region, windows in deer_windows.items()},
        "native_deer_grazing_by_region": {
            region: {**counts, "plant_units": round(sum(deer_windows[region]), 3),
                     "intake_steps_per_graze_action_step": round(counts["intake_steps"] / counts["graze_action_steps"], 4)
                     if counts["graze_action_steps"] else None}
            for region, counts in sorted(deer_grazing_steps.items()) if counts["windows"] == len(deer_windows[region])
        },
        "sampled_native_wolf_meat": report.get("sampled_native_wolf_meat"),
        "native_wolf_reserved_nutrition": round(sum(wolf_reserved), 6) if wolf_reserved else None,
        "confirmed_vitality_energy": {
            species: {meal: round(amount, 3) for meal, amount in meals.items()}
            for species, meals in nutrition.items()
        },
        "logged_first_timed_meal_by_agent": summarize_first_timed_meals(first_timed_meal, untimed_meal_agents),
        "habitat_patch_payments": {
            patch: {"agents": len(patch_eaters[patch]), "energy_by_species": {
                species: round(amount, 3) for species, amount in payments.items()}}
            for patch, payments in sorted(patch_payments.items())
        },
        "habitat_patch_access_payments": {
            patch: {access: {species: round(amount, 3) for species, amount in payments.items()}
                    for access, payments in sorted(points.items())}
            for patch, points in sorted(patch_access_payments.items())
        },
        "captured_by": captured_by,
        "captured_targets": captured_targets,
        "hunt_events": hunts,
        "ground_scan_food_opportunities": ground_scan_opportunities,
        "hunt_logged_agent_counts": {
            species: {event: len(agents) for event, agents in stages.items()}
            for species, stages in sorted(hunt_hunters.items())
        },
        "access_rejections": access_rejections,
        "contact_rejections": contact_rejections,
        "candidate_evidence_by_medium": candidate_evidence,
        "committed_carrion_meal_gap_seconds": summarize_gaps(carrion_times),
        "carcass_use": {
            agent: summarize_carcass(stock, carcass_payments[agent], carcass_releases[agent],
                                     deaths_by_id.get(agent), carcass_hunters.get(agent), carcass_closures.get(agent))
            for agent, stock in carcass_stock.items()
        },
        "carcass_payment_ids_without_creation": sorted(carcass_payments.keys() - carcass_stock.keys(), key=int),
        "logged_food_source_changes": summarize_food_source_changes(logged_food_sources),
        "logged_food_receipt_transitions_by_species": summarize_food_receipt_transitions(logged_food_receipts),
        "logged_shared_patch_payments": summarize_shared_patch_payments(timed_patch_transactions, natural_births),
        "logged_food_intents": list(food_intent_trace.values()),
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


def summarize_shared_patch_payments(transactions, births):
    rows = []
    for (patch, when), payments in transactions.items():
        if len({payment["agent_id"] for payment in payments}) < 2:
            continue
        rows.append({
            "patch": patch, "authority_seconds": when,
            "reported_remainder": payments[-1]["remaining"],
            "payments_in_log_order": [
                {**payment, "runtime_birth_logged": payment["agent_id"] in births.get(payment["species"], ())}
                for payment in payments
            ],
        })
    return rows


def summarize_first_timed_meals(first_meals, untimed_agents):
    by_species = defaultdict(dict)
    for (species, agent), meal in first_meals.items():
        by_species[species][agent] = {**meal, "has_untimed_payment": agent in untimed_agents[species]}
    return {species: {"first_timed_payment_by_agent": by_species[species],
                      "agents_with_untimed_payment": sorted(untimed_agents[species], key=int)}
            for species in sorted(by_species.keys() | untimed_agents.keys())}


def summarize_gaps(meals):
    gaps = defaultdict(list)
    for (species, _), times in meals.items():
        ordered = sorted(times)
        gaps[species].extend(after - before for before, after in zip(ordered, ordered[1:]))
    return {species: {"count": len(values), "median": round(median(values), 3), "max": round(max(values), 3)}
            for species, values in gaps.items() if values}


def summarize_food_source_changes(payments):
    rows = defaultdict(dict)
    for (species, agent), entries in sorted(payments.items()):
        switches = Counter()
        after_low_stock = Counter()
        for (before, remaining), (after, _) in zip(entries, entries[1:]):
            if before == after:
                continue
            switch = f"{before} -> {after}"
            switches[switch] += 1
            if remaining is not None and remaining < .2:
                after_low_stock[switch] += 1
        if switches:
            rows[species][agent] = {"changes": switches, "previous_patch_left_below_minimum": after_low_stock}
    return rows


def summarize_food_receipt_transitions(receipts):
    """Distinguish a switch to another carcass from a change of feeding kind."""
    by_species = defaultdict(list)
    for (species, agent), meals in receipts.items():
        for before, after in zip(meals, meals[1:]):
            same_kind = before["kind"] == after["kind"]
            if same_kind and (before["source_id"] is None or after["source_id"] is None
                              or before["source_id"] == after["source_id"]):
                continue
            start, end = (meal["authority_seconds"] for meal in (before, after))
            by_species[species].append({
                "agent_id": agent, "before": before, "after": after,
                "kind_changed": not same_kind,
                "seconds_between_receipts": round(end - start, 3) if start is not None and end is not None else None,
            })
    return dict(by_species)


def summarize_carcass(stock, payments, releases, death_cause, hunter_id, closure):
    energy = Counter()
    consumers = set()
    for payment in payments:
        energy[payment["species"]] += payment["amount"]
        consumers.add(payment["agent_id"])
    remaining = payments[-1]["remaining"] if payments else stock["initial_shared_stock"]
    return {
        **stock, "death_cause": death_cause, "primary_hunter_id": hunter_id,
        "primary_hunter_received_shared_payment": hunter_id in consumers if hunter_id else None,
        "shared_payments": len(payments), "consumer_count": len(consumers),
        "energy_by_consumer_species": {species: round(amount, 3) for species, amount in sorted(energy.items())},
        "first_shared_payment": payments[0] if payments else None,
        "last_logged_shared_stock": remaining,
        "logged_stock_minus_payments_and_remaining": round(stock["initial_shared_stock"] - sum(energy.values()) - remaining, 3),
        "closure": closure,
        "logged_stock_minus_payments_and_unused_at_closure": (
            round(stock["initial_shared_stock"] - sum(energy.values()) - closure["unused_stock"], 3)
            if closure else None),
        "release_events": releases,
    }


def audit_carcass_balances(stocks, payments_by_id, closures):
    """Check stock changes in log order, including Native payments without a timestamp."""
    max_residual = 0.
    for carcass, stock in stocks.items():
        remaining = stock["initial_shared_stock"]
        initial_total = stock["native_reserved"] + stock["immediate_killer_payment"] + remaining
        if abs(initial_total - stock["total"]) > .002001:
            raise AssertionError(f"Carcass {carcass}: initial allocation disagrees with total")
        for payment in payments_by_id.get(carcass, ()):
            amount, next_remaining = payment["amount"], payment["remaining"]
            residual = abs(remaining - amount - next_remaining)
            if amount < 0. or next_remaining < 0. or residual > .001501:
                raise AssertionError(f"Carcass {carcass}: invalid stock debit {payment}")
            max_residual = max(max_residual, residual)
            remaining = next_remaining
        if carcass in closures and abs(closures[carcass]["unused_stock"] - remaining) > .001001:
            raise AssertionError(f"Carcass {carcass}: closing stock disagrees with the latest balance")
    return round(max_residual, 6)


def compare_island_baseline(reference, trial, *, policy_species=()):
    for report in (reference, trial):
        if report.get("errors") or not report.get("samples") or "agents" not in report["samples"][0]:
            raise ValueError("Baseline comparison requires two successful island reports with agent samples")

    population_report = "population_target_seconds" in reference
    if population_report != ("population_target_seconds" in trial):
        raise ValueError("Compare two population reports or two short island reports")
    budget_key = "authored_capacities" if population_report else "patch_budget"
    if any(budget_key not in report for report in (reference, trial)):
        raise ValueError(f"Both island reports must contain {budget_key}")

    before, after = (report["samples"][0] for report in (reference, trial))
    policy_species = set(policy_species)
    if policy_species and not population_report:
        raise ValueError("Policy replacement comparison requires population reports with species backends")
    if policy_species and any(not report.get("initial_patch_inputs") for report in (reference, trial)):
        raise ValueError("Policy replacement comparison requires initial_patch_inputs in both reports; recapture the baseline")
    if policy_species - (before["population"].keys() & after["population"].keys()):
        raise ValueError("Expected replacement species must exist in both starting populations")
    differences = []
    for name, left, right in (
        ("initial_population", before["population"], after["population"]),
        ("initial_patch_stock", before["stocks"], after["stocks"]),
    ):
        if left != right:
            differences.append(name)
    policy_changes = defaultdict(list)
    if reference.get("deer_brain") != trial.get("deer_brain"):
        if "Herbivore" in policy_species:
            policy_changes["Herbivore"].append({"field": "deer_brain", "baseline": reference.get("deer_brain"),
                                               "trial": trial.get("deer_brain")})
        else:
            differences.append("deer_brain")
    if population_report:
        left, right = (report["initial_backends"] for report in (reference, trial))
        for species in sorted(left.keys() | right.keys()):
            if left.get(species) == right.get(species):
                continue
            if species in policy_species:
                policy_changes[species].append({"field": "backend", "baseline": left.get(species), "trial": right.get(species)})
            elif "initial_backends" not in differences:
                differences.append("initial_backends")
        for field in ("initial_routes", "population_target_seconds", "population_dilation",
                      "population_uses_forage_soil"):
            if reference[field] != trial[field]:
                differences.append(field)
        for field in ("completed_clock", "region_food"):
            if before[field] != after[field]:
                differences.append(f"initial_{field}")

    def initial_agents(sample):
        return {row["stable_id"]: row for row in sample["agents"] if row["hp"] > 0}

    left_agents, right_agents = initial_agents(before), initial_agents(after)
    same_ids = left_agents.keys() & right_agents.keys()
    identity_fields = ("species", "region", "hp", "energy", "body_scale")
    if left_agents.keys() != right_agents.keys() or any(
        left_agents[agent].get(field) != right_agents[agent].get(field) for agent in same_ids for field in identity_fields
    ):
        differences.append("initial_agents")
    for agent in sorted(same_ids, key=int):
        left, right = left_agents[agent], right_agents[agent]
        for field in ("brain", "policy_contract"):
            if left.get(field) == right.get(field):
                continue
            if left["species"] in policy_species:
                policy_changes[left["species"]].append({"field": field, "agent_id": agent,
                                                       "baseline": left.get(field), "trial": right.get(field)})
            elif "initial_agents" not in differences:
                differences.append("initial_agents")
    moved = sorted((agent for agent in same_ids if left_agents[agent]["position"] != right_agents[agent]["position"]), key=int)
    if moved:
        differences.append("initial_position")
    left_patches, right_patches = (report[budget_key] for report in (reference, trial))
    comparable = ("region", "consumers", "capacity", "regrowth_per_second", "dry_loss_per_second",
                  "energy_per_meal", "submerged", "nursery")
    changed_patches = sorted(left_patches.keys() ^ right_patches.keys())
    for patch in sorted(left_patches.keys() & right_patches.keys()):
        left, right = left_patches[patch], right_patches[patch]
        if population_report:
            if left != right:
                changed_patches.append(patch)
            continue
        optional = ("stage", "plant_guild", "sheltered_species", "shelter_radius_cm", "entrance_radius_cm")
        if (any(left.get(field) != right.get(field) for field in comparable)
                or any(field in left and field in right and left[field] != right[field] for field in optional)):
            changed_patches.append(patch)
    if changed_patches:
        differences.append(budget_key)
    left_inputs, right_inputs = (report.get("initial_patch_inputs") for report in (reference, trial))
    changed_inputs = []
    if left_inputs is not None and right_inputs is not None:
        left_patches, right_patches = left_inputs["patches"], right_inputs["patches"]
        changed_inputs = sorted(name for name in left_patches.keys() | right_patches.keys()
                                if left_patches.get(name) != right_patches.get(name))
        if (changed_inputs or left_inputs["patch_order"] != right_inputs["patch_order"]
                or left_inputs["active_stage"] != right_inputs["active_stage"]):
            differences.append("initial_patch_inputs")
    result = {"matches": not differences, "differences": differences, "changed_patches": changed_patches,
              "agents_with_different_initial_position": moved}
    if left_inputs is not None or right_inputs is not None:
        result.update(checked_initial_patch_inputs=left_inputs is not None and right_inputs is not None,
                      changed_patch_inputs=changed_inputs)
    if policy_species:
        missing = sorted(species for species in policy_species
                         if not any(change["field"] != "policy_contract" and change["trial"]
                                    for change in policy_changes[species]))
        result.update(policy_changes=dict(policy_changes), expected_policy_changes_not_observed=missing)
        result["matches"] = not differences and not missing
    return result


def summarize_ground_forage_stock(report):
    minimum = .2
    active_stage = report.get("active_habitat_stage")
    candidates = defaultdict(list)
    for patch, budget in report["patch_budget"].items():
        if budget["submerged"] or (active_stage is not None and budget.get("stage", 0) > active_stage):
            continue
        for species in budget["consumers"]:
            candidates[budget["region"], species].append(patch)
    counts = defaultdict(dict)
    for (region, species), patches in sorted(candidates.items()):
        row = Counter()
        first_all_low = None
        for sample in report["samples"]:
            if not any(agent["hp"] > 0 and agent["region"] == region and agent["species"] == species
                       for agent in sample["agents"]):
                continue
            low = sum(sample["stocks"][patch] < minimum for patch in patches)
            row["samples_with_living_resident"] += 1
            row["samples_with_all_patches_below_minimum"] += low == len(patches)
            row["samples_with_some_patches_below_minimum"] += 0 < low < len(patches)
            if low == len(patches) and first_all_low is None:
                first_all_low = sample["time"]
        if row:
            counts[region][species] = {"patch_ids": sorted(patches), **row,
                                       "first_sample_all_below_minimum": first_all_low}
    return {"selection_minimum": minimum, "active_habitat_stage": active_stage, "regions": counts}


def summarize_phase_activity(samples):
    regions = defaultdict(lambda: defaultdict(lambda: defaultdict(Counter)))
    for sample in samples:
        clock = sample.get("completed_clock")
        if not clock or "phase_start_seconds" not in clock or "phase_end_seconds" not in clock:
            continue
        now = clock["authority_seconds"]
        start, end = clock["phase_start_seconds"], clock["phase_end_seconds"]
        phase = clock["phase"]
        if phase not in {"day", "night"} or not start <= now < end:
            raise ValueError(f"Invalid completed clock sample: {clock}")
        if min(now - start, end - now) < .1 * (end - start):
            phase = f"{phase}_twilight"
        for agent in sample["agents"]:
            if agent["hp"] > 0 and "activity" in agent and "region" in agent:
                activity = agent["activity"].rsplit("::", 1)[-1]
                regions[agent["region"]][agent["species"]][phase][activity] += 1
    return regions


def summarize_birth_cohorts(report, births, deaths, first_timed_meal, untimed_meal_agents):
    samples = report["samples"]
    first, last = samples[0], samples[-1]
    initial = defaultdict(set)
    final_alive = set()
    observed_ids = set()
    payments = defaultdict(dict)
    observed_alive = set()
    energy_samples = defaultdict(list)
    birth_times = {}
    native_intake = {}
    for row in first["agents"]:
        if row["hp"] > 0:
            initial[row["species"]].add(row["stable_id"])
    for row in last["agents"]:
        if row["hp"] > 0:
            final_alive.add(row["stable_id"])
    for sample in samples:
        for row in sample["agents"]:
            agent = row["stable_id"]
            observed_ids.add(agent)
            if row["hp"] > 0:
                observed_alive.add(agent)
                if row.get("last_intake", 0.) > 0.:
                    native_intake.setdefault(agent, {
                        "sample_authority_seconds": sample.get("completed_clock", {}).get("authority_seconds"),
                        "reported_last_step_plant_units": row["last_intake"],
                    })
                if "energy_fraction" in row:
                    energy_samples[agent].append((sample["time"], row["energy_fraction"]))
            for event in row.get("gameplay_reason_history", ()):
                reason = event["reason"]
                if reason == "BirthCommitted":
                    birth_times[event["related_id"]] = event["time"]
                if (reason in {"PlantsEaten", "HabitatPatchEaten", "CarrionEaten", "ParentProvisioned"}
                        and event["amount"] > 0 and first["time"] <= event["time"] <= last["time"]):
                    times = payments[agent]
                    times[reason] = min(times.get(reason, event["time"]), event["time"])
    unclassified = observed_ids - set().union(*initial.values(), *births.values())
    rows = {}
    for species in sorted(initial.keys() | births.keys()):
        cohorts = {}
        born = births.get(species, set())
        for name, agents in (("initial_alive", initial[species]), ("logged_births", born)):
            source_counts = Counter(reason for agent in agents for reason in payments[agent])
            timed = {agent for agent in agents if (species, agent) in first_timed_meal}
            untimed = agents & untimed_meal_agents.get(species, set())
            sampled = {agent for agent in agents if payments[agent]}
            native = agents & native_intake.keys()
            cohorts[name] = {
                "count": len(agents), "observed_alive": len(agents & observed_alive),
                "alive_in_final_sample": len(agents & final_alive),
                "logged_death_causes": Counter(deaths[agent] for agent in agents if agent in deaths),
                "with_recorded_payment": sum(bool(payments[agent]) for agent in agents),
                "with_recorded_payment_by_reason": source_counts,
                "feeding_evidence": {
                    "first_timed_log_by_id": {
                        agent: first_timed_meal[(species, agent)] for agent in sorted(timed, key=int)
                    },
                    "untimed_log_ids": sorted(untimed, key=int),
                    "sampled_history_only_ids": sorted(sampled - timed - untimed, key=int),
                    "sampled_native_plant_intake_by_id": {
                        agent: native_intake[agent] for agent in sorted(native, key=int)
                    },
                    "without_individual_receipt_ids": sorted(agents - (timed | untimed | sampled | native), key=int),
                },
                "sampled_energy_after_first_payment": summarize_energy_after_payment(agents, payments, energy_samples),
            }
        cohorts["logged_births"]["first_payment_after_birth_seconds_by_id"] = {
            agent: round(min(payments[agent].values()) - birth_times[agent], 3)
            for agent in sorted(born & birth_times.keys(), key=int)
            if payments[agent] and min(payments[agent].values()) >= birth_times[agent]
        }
        rows[species] = cohorts
    return {"species": rows, "observed_ids_without_initial_or_birth_evidence": sorted(unclassified, key=int)}


def summarize_energy_after_payment(agents, payments, energy_samples):
    window = 30.
    low = .4
    rows = {}
    for agent in sorted(agents, key=int):
        if not payments[agent]:
            continue
        first = min(payments[agent].values())
        series = energy_samples.get(agent, ())
        before = next((energy for at, energy in reversed(series) if at < first), None)
        after = [(at, energy) for at, energy in series if first <= at <= first + window]
        if before is None or not after:
            continue
        at, last = after[-1]
        peak = max(energy for _, energy in after)
        rows[agent] = {
            "first_recorded_payment_seconds": first,
            "before_energy_fraction": before,
            "max_sampled_energy_fraction": peak,
            "last_sampled_energy_fraction": last,
            "last_sample_seconds_after_payment": round(at - first, 3),
            "sample_count": len(after),
            "rose_above_prior_sample_by_1pp": peak > before + .01,
            "last_sample_below_low_energy": last < low,
        }
    return {"window_seconds": window, "low_energy_fraction": low, "agents": rows}


def compare_sampled_feeding_activity(samples, payments):
    # Activity is the published enum, not the independent feeding flag. Swimming
    # and flight can take priority over Eat in the representation.
    payment_times = {key: sorted(times) for key, times in payments.items()}
    counts = defaultdict(Counter)
    for sample in samples:
        for agent in sample["agents"]:
            if agent["hp"] <= 0 or "activity" not in agent or "world_seconds" not in agent:
                continue
            species = agent["species"]
            activity = agent["activity"].rsplit("::", 1)[-1]
            is_feeding_activity = activity in {"Eat", "Graze", "AlertGraze"}
            row = counts[species]
            row["alive_samples"] += 1
            row["feeding_activity_samples"] += is_feeding_activity
            times = payment_times.get((species, agent["stable_id"]), ())
            now = agent["world_seconds"]
            index = bisect_right(times, now)
            recent_payment = index > 0 and now - times[index - 1] < 1.
            row["recent_recorded_payment_samples"] += recent_payment
            row["feeding_activity_with_recent_payment_samples"] += is_feeding_activity and recent_payment
    return dict(sorted(counts.items()))


def summarize_feeding_track(track):
    payment_reasons = {"PlantsEaten", "HabitatPatchEaten", "CarrionEaten", "ParentProvisioned"}
    feeding_activities = {"Eat", "Graze", "AlertGraze"}
    samples = defaultdict(list)
    payments = defaultdict(dict)
    for frame in track["samples"]:
        for agent in frame["agents"]:
            agent_id = agent["stable_id"]
            if agent["hp"] > 0:
                samples[agent_id].append(agent)
            for event in agent.get("gameplay_reason_history", ()):
                if event["reason"] in payment_reasons and event["amount"] > 0:
                    key = (event["time"], event["reason"], event["related_id"], event.get("resource_id"))
                    payments[agent_id][key] = event["amount"]

    result = {}
    for agent_id, rows in sorted(samples.items(), key=lambda item: int(item[0])):
        events = payments[agent_id]
        energy_by_time = Counter()
        by_source = Counter()
        for (time, reason, _, _), amount in events.items():
            energy_by_time[time] += amount
            by_source[reason] += amount
        times = sorted(energy_by_time)
        gaps = [after - before for before, after in zip(times, times[1:])]
        longer_gaps = [gap for gap in gaps if gap > 1.25]
        burst_energy = []
        for index, time in enumerate(times):
            if index == 0 or gaps[index - 1] > 1.25:
                burst_energy.append(0.)
            burst_energy[-1] += energy_by_time[time]
        result[agent_id] = {
            "species": rows[0]["species"],
            "alive_samples": len(rows),
            "feeding_activity_samples": sum(row["activity"].rsplit("::", 1)[-1] in feeding_activities for row in rows),
            "below_40_percent_energy_samples": sum(row["energy_fraction"] < .4 for row in rows),
            "last_alive_energy_fraction": round(rows[-1]["energy_fraction"], 4),
            "payment_count": len(events),
            "payment_energy_by_source": {key: round(value, 3) for key, value in sorted(by_source.items())},
            "first_payment_authority_seconds": round(times[0], 3) if times else None,
            "payment_burst_count": len(burst_energy),
            "median_energy_per_burst": round(median(burst_energy), 3) if burst_energy else None,
            "median_gap_between_bursts_authority_seconds": round(median(longer_gaps), 3) if longer_gaps else None,
        }
        native_rows = [row for row in rows if "last_plant_intake" in row]
        if native_rows:
            native_feeding_rows = [row for row in native_rows
                                   if row["activity"].rsplit("::", 1)[-1] in feeding_activities]
            native_intake = {
                "available_samples": len(native_rows),
                "feeding_activity_samples": len(native_feeding_rows),
                "positive_intake_samples": sum(row["last_plant_intake"] > 0 for row in native_rows),
                "positive_intake_and_feeding_activity_samples": sum(
                    row["last_plant_intake"] > 0 for row in native_feeding_rows),
            }
            signals = [row for row in native_rows if "presentation_eating" in row]
            if signals:
                native_intake["presentation_signal_samples"] = len(signals)
                native_intake["presentation_eating_samples"] = sum(row["presentation_eating"] for row in signals)
                native_intake["presentation_eating_without_positive_intake_samples"] = sum(
                    row["presentation_eating"] and row["last_plant_intake"] <= 1e-9 for row in signals)
            missed_cells = [row for row in native_feeding_rows
                            if row["last_plant_intake"] <= 1e-9 and "native_food_remaining" in row]
            if missed_cells:
                native_intake["feeding_activity_without_intake_with_cell_samples"] = len(missed_cells)
                native_intake["remaining_food_at_or_below_epsilon_samples"] = sum(
                    row["native_food_remaining"] <= 1e-9 for row in missed_cells)
                native_intake["distinct_cells_in_these_samples"] = len({row["native_food_cell"] for row in missed_cells})
            result[agent_id]["native_last_step_intake_samples"] = native_intake
    return {"interval_pie_seconds": track["interval_seconds"], "within_burst_gap_authority_seconds": 1.25,
            "agents": result}


def sampled_species_proximity(report, species_pair, radius_cm):
    first, second = species_pair
    closest = None
    closest_same_region = None
    comparable_samples = near_samples = same_region_samples = same_region_near_samples = 0
    near_pairs = set()
    for sample in report["samples"]:
        agents = defaultdict(list)
        for row in sample["agents"]:
            if row["species"] in species_pair and row["hp"] > 0:
                xyz = re.fullmatch(r"V\(X=([^,]+), Y=([^,]+), Z=([^\)]+)\)", row["position"])
                if not xyz:
                    raise ValueError(f"Unsupported Unreal position: {row['position']}")
                agents[row["species"]].append((row, tuple(map(float, xyz.groups()))))
        if not agents[first] or not agents[second]:
            continue
        comparable_samples += 1
        any_near = any_same_region = any_same_region_near = False
        for a, a_pos in agents[first]:
            for b, b_pos in agents[second]:
                distance = math.dist(a_pos, b_pos)
                pair = (a["stable_id"], b["stable_id"])
                near = distance <= radius_cm
                same_region = a["region"] == b["region"]
                if near:
                    near_pairs.add(pair)
                    any_near = True
                any_same_region |= same_region
                any_same_region_near |= near and same_region
                nearest = closest is None or distance < closest["distance_cm"]
                nearest_same_region = same_region and (closest_same_region is None or distance < closest_same_region["distance_cm"])
                if nearest or nearest_same_region:
                    pair_sample = {"game_seconds": sample["time"], "distance_cm": distance,
                                   "agent_ids": pair, "regions": [a["region"], b["region"]]}
                    if authority := sample.get("completed_clock"):
                        pair_sample["authority_seconds"] = authority["authority_seconds"]
                    if nearest:
                        closest = pair_sample
                    if nearest_same_region:
                        closest_same_region = pair_sample
        near_samples += any_near
        same_region_samples += any_same_region
        same_region_near_samples += any_same_region_near
    return {"species": species_pair, "radius_cm": radius_cm, "comparable_samples": comparable_samples,
            "samples_with_pair_inside_radius": near_samples, "pairs_inside_radius": sorted(near_pairs),
            "samples_with_pair_in_same_region": same_region_samples,
            "samples_with_pair_in_same_region_inside_radius": same_region_near_samples,
            "closest": closest, "closest_same_region": closest_same_region}


def summarize_nursery_fry(trial):
    start = trial["events"]["lowered"]["world_seconds"]
    end = trial["events"]["restored"]["world_seconds"]
    hatch = trial["hatch"]
    samples = [row for row in trial["samples"] if row["present"]]
    initial_position = samples[0]["position_cm"]
    drawdown_samples = [row for row in samples if start <= row["world_seconds"] < end]
    water_samples = [row for row in drawdown_samples if row["water_column_cm"]]
    in_water = [row for row in water_samples if row["water_column_cm"][0] <= row["position_cm"][2]
                <= row["water_column_cm"][1]]
    payments = sorted(trial["payments"], key=lambda event: event["time"])
    restored_at = trial["events"]["restored"]["completed_authority_seconds"]
    payments_by_patch = defaultdict(list)
    for event in payments:
        payments_by_patch[event["resource_id"]].append(event)
    return {
        "mode": trial["mode"],
        "child_id": hatch["related_id"],
        "hatch_authority_seconds": hatch["time"],
        "trial_window_world_seconds": [start, end],
        "present_samples_during_trial": len(drawdown_samples),
        "sampled_water_columns_during_trial": len(water_samples),
        "samples_with_center_in_column": len(in_water),
        "max_planar_displacement_during_trial_cm": max(
            math.dist(initial_position[:2], row["position_cm"][:2]) for row in drawdown_samples),
        "first_sample_in_column_after_start_world_seconds": (
            in_water[0]["world_seconds"] - start if in_water else None),
        "first_payment_since_hatch_authority_seconds": payments[0]["time"] - hatch["time"] if payments else None,
        "payments_before_restore_authority_count": sum(event["time"] < restored_at for event in payments),
        "payments_by_patch": {
            patch: {"first_authority_seconds": events[0]["time"],
                    "total_energy": sum(event["amount"] for event in events)}
            for patch, events in sorted(payments_by_patch.items())
        },
        "min_sampled_hp": min(row["hp"] for row in samples),
        "last_observed_energy": samples[-1]["energy"],
    }


def summarize_shore_and_hatches(report, nursery_by_child):
    water = report["shore_rain"]
    water_times = [row["time"] for row in water]
    surface = [row["surface_z"] for row in water]
    peak = max(surface)
    samples = report["samples"]
    hatches = {agent: (species, time) for species, agent, time in report.get("aquatic_hatches", ())}
    shore_actions = defaultdict(set)
    first_payments = {}
    for sample in samples:
        for row in sample["agents"]:
            agent = row["stable_id"]
            for event in row.get("gameplay_reason_history", ()):
                reason, time = event["reason"], event["time"]
                if row["species"] == "Mink" and reason in {"SwimEnter", "SwimExit"}:
                    shore_actions[agent].add((time, reason))
                if agent in hatches and reason == "HabitatPatchEaten" and event["amount"] > 0 and time >= hatches[agent][1]:
                    first_payments[agent] = min(time, first_payments.get(agent, time))
    shore_agents = {}
    for agent in samples[0]["agents"]:
        if agent["species"] != "Mink":
            continue
        agent_id = agent["stable_id"]
        rows = []
        for time, reason in sorted(shore_actions[agent_id]):
            index = bisect_right(water_times, time)
            before = water[index - 1] if index else None
            after = water[index] if index < len(water) else None
            rows.append({"event": reason, "authority_seconds": time, "water_samples": [before, after],
                         "both_samples_near_peak": bool(before and after and
                             min(before["surface_z"], after["surface_z"]) >= peak - .1)})
        shore_agents[agent_id] = rows
    final_hp = {row["stable_id"]: row["hp"] for row in samples[-1]["agents"]}
    return {
        "clock_note": "Water brackets use PIE world sample time. Event time uses the authority clock.",
        "water_rise_cm": peak - min(surface),
        "minimum_sampled_bank_clearance_cm": min(row["bank_above_surface_cm"] for row in water),
        "initial_mink_actions": shore_agents,
        "aquatic_hatches": [{
            "agent_id": agent, "species": species, "nursery_id_from_log": nursery_by_child.get(agent),
            "hatch_authority_seconds": time, "first_recorded_patch_payment_seconds": first_payments.get(agent),
            "final_sample_hp": final_hp.get(agent),
        } for agent, (species, time) in sorted(hatches.items(), key=lambda item: item[1][1])],
    }


def summarize_population_stock(report, payment_times):
    summary = {}
    samples = report["samples"]
    last_time = samples[-1]["completed_clock"]["authority_seconds"]
    for patch, capacity in report["authored_capacities"].items():
        rows = [(sample["completed_clock"]["authority_seconds"], sample["stocks"][patch])
                for sample in samples if patch in sample["stocks"]]
        if not rows:
            continue
        low = [time for time, stock in rows if stock < .2]
        last_payment = max((time for time in payment_times.get(patch, ()) if time <= last_time), default=None)
        recovered = next(((time, stock) for time, stock in rows
                          if low and time > low[0] and stock >= min(1., capacity)), None)
        soil = [sample["forage_soil_moisture"][patch] for sample in samples
                if patch in sample.get("forage_soil_moisture", {})]
        summary[patch] = {"capacity": capacity, "samples": len(rows), "samples_below_0_2": len(low),
                          "first_sample_below_0_2_at": low[0] if low else None,
                          "first_recovery_sample": {"authority_seconds": recovered[0], "stock": round(recovered[1], 3)}
                          if recovered else None, "last_logged_payment_at": last_payment,
                          "soil_moisture_range": [min(soil), max(soil)] if soil else None,
                          "final_stock": round(rows[-1][1], 3)}
    return summary


def island_report(path, report):
    if report["errors"] or not report["samples"]:
        raise ValueError(f"Incomplete island run: {report['errors']}")
    meals = defaultdict(Counter)
    sources = defaultdict(Counter)
    energy_by_source = defaultdict(Counter)
    energy_by_patch = defaultdict(Counter)
    exposure = Counter()
    founder_ids = defaultdict(set)
    observed_ids = defaultdict(set)
    last_alive_ids = defaultdict(set)
    first_feeding = defaultdict(dict)
    feeding_reasons = {"PlantsEaten", "HabitatPatchEaten", "CarrionEaten", "ParentProvisioned"}
    seen = set()
    samples = report["samples"]
    for snapshot, target in ((samples[0], founder_ids), (samples[-1], last_alive_ids)):
        for agent in snapshot["agents"]:
            if agent["hp"] > 0:
                target[agent["species"]].add(agent["stable_id"])
    for before, after in zip(samples, samples[1:]):
        seconds = after["time"] - before["time"]
        for snapshot in (before, after):
            for species, count in snapshot["population"].items():
                exposure[species] += count * seconds / 2
    for sample in samples:
        for agent in sample["agents"]:
            key = (agent["species"], agent["stable_id"])
            if agent["hp"] > 0:
                observed_ids[key[0]].add(key[1])
            for event in agent.get("gameplay_reason_history", ()):
                reason = event["reason"]
                if (reason not in feeding_reasons or event["amount"] <= 0
                        or not samples[0]["time"] <= event["time"] <= samples[-1]["time"]):
                    continue
                resource = event.get("resource_id")
                marker = (key, event["time"], reason, event["related_id"], resource)
                if marker in seen:
                    continue
                seen.add(marker)
                meals[key][event["time"]] += event["amount"]
                times = first_feeding[key[0]]
                times[key[1]] = min(times.get(key[1], event["time"]), event["time"])
                sources[key[0]][reason] += 1
                energy_by_source[key[0]][reason] += event["amount"]
                if reason == "HabitatPatchEaten" and resource:
                    energy_by_patch[resource][key[0]] += event["amount"]
    if report["record_gameplay_reasons"] and not seen:
        raise ValueError(f"Missing authority feeding history: {path}")
    # A transaction can occur once per second. Group nearby observed payments
    # for comparison without treating the groups as physiological meals.
    burst_gap_seconds = 1.25
    burst_sizes = defaultdict(list)
    burst_energy = defaultdict(list)
    between_bursts = defaultdict(list)
    for (species, _), times in meals.items():
        ordered = sorted(times)
        size = 1
        energy = times[ordered[0]]
        for before, after in zip(ordered, ordered[1:]):
            gap = after - before
            if gap <= burst_gap_seconds:
                size += 1
            else:
                burst_sizes[species].append(size)
                burst_energy[species].append(energy)
                between_bursts[species].append(gap)
                size = 1
                energy = 0
            energy += times[after]
        burst_sizes[species].append(size)
        burst_energy[species].append(energy)
    meadow = {}
    if report.get("meadow_trial"):
        # Rule-fauna food selection rejects stocks below 0.2 before scoring.
        patches = {patch: budget["capacity"] for patch, budget in report["patch_budget"].items()
                   if budget["region"] == "Grassland"}
        capacity = sum(patches.values())
        unavailable = [sum(cap for patch, cap in patches.items() if row["stocks"][patch] < .2)
                       for row in samples]
        meadow = {"meadow_availability": {
            "samples": len(samples),
            "samples_all_patches_below_selection_minimum": sum(amount == capacity for amount in unavailable),
            "mean_unavailable_capacity_fraction": round(sum(unavailable) / (capacity * len(samples)), 4),
            "selection_minimum": .2,
        }}
    population_run = "population_target_seconds" in report
    snapshots = [{"seconds": (sample["completed_clock"]["authority_seconds"] if population_run else sample["time"]),
                  "species": sample["population"], "regional_species": sample.get("regional_population", {})}
                 for sample in report["samples"]]
    milestones = {
        str(target): {"authority_seconds": row["completed_clock"]["authority_seconds"],
                      "population": row["population"], "regional_population": row["regional_population"],
                      "authored_stock": round(sum(row["stocks"].values()), 3),
                      "region_food": row["region_food"]}
        for target in (1800, 3600)
        if population_run and (row := next((sample for sample in samples
                                            if sample["completed_clock"]["authority_seconds"] >= target), None))
    }
    return {"name": path.parent.name, "samples": snapshots, "completed": True}, {
        **({"island_population_milestones": milestones,
            "initial_backends": report["initial_backends"]} if population_run else {}),
        "sampled_authority_feeding_coverage": {
            species: {
                "initial_alive": len(founder_ids[species]),
                "observed_alive": len(ids),
                "final_alive": len(last_alive_ids[species]),
                "initial_agents_with_recorded_payment": len(founder_ids[species] & first_feeding[species].keys()),
                "agents_with_recorded_payment": len(first_feeding[species]),
                "first_recorded_payment_at": min(first_feeding[species].values(), default=None),
            }
            for species, ids in sorted(observed_ids.items())
        },
        "sampled_authority_feeding_event_counts": sources,
        "sampled_authority_patch_energy_by_species": {
            patch: {species: round(amount, 3) for species, amount in amounts.items()}
            for patch, amounts in sorted(energy_by_patch.items())
        },
        "sampled_authority_feeding_gap_seconds": summarize_gaps(meals),
        "sampled_feeding_activity": {
            "approximate_recent_payment_window_seconds": 1.,
            "clock_note": "Legacy snapshots compare PIE world time to recorded authority time; use feeding_track for both clocks.",
            "activity_values": ["Eat", "Graze", "AlertGraze"],
            "species": compare_sampled_feeding_activity(samples, meals),
        },
        "sampled_authority_feeding_energy": {
            species: {
                "estimated_population_seconds": round(seconds, 3),
                "recorded_energy_by_source": {reason: round(energy, 3)
                                              for reason, energy in energy_by_source[species].items()},
                "recorded_energy_per_population_minute": round(sum(energy_by_source[species].values()) * 60 / seconds, 3),
            }
            for species, seconds in exposure.items() if seconds > 0 and species in energy_by_source
        },
        "sampled_authority_feeding_bursts": {
            "max_within_burst_gap_seconds": burst_gap_seconds,
            "species": {
                species: {"count": len(sizes), "median_payments": median(sizes),
                          "max_payments": max(sizes),
                          "median_recorded_energy": round(median(burst_energy[species]), 3),
                          "median_between_burst_seconds": round(median(between_bursts[species]), 3)
                          if between_bursts[species] else None}
                for species, sizes in burst_sizes.items()
            },
        },
        **meadow,
        **({"high_frequency_feeding_track": summarize_feeding_track(report["feeding_track"])}
           if "feeding_track" in report else {}),
    }


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
    parser.add_argument("--audit-carcasses", action="store_true", help="Check ledger lines from creation through closure")
    parser.add_argument("--proximity", nargs=2, metavar=("SPECIES_A", "SPECIES_B"),
                        help="Compare living agents of two species in island PIE snapshots")
    parser.add_argument("--proximity-radius-cm", type=float, default=500.,
                        help="Distance for snapshot proximity counts")
    parser.add_argument("--compare-baseline", type=Path,
                        help="Compare initial island roster, brain, stock and patch budgets with another island PIE report")
    parser.add_argument("--expect-policy-change", action="append", default=[], metavar="SPECIES",
                        help="With --compare-baseline, require a recorded policy change for this species only")
    args = parser.parse_args()
    if args.fixed_fps is not None and args.fixed_fps <= 0:
        parser.error("--fixed-fps must be positive")
    if args.expect_policy_change and not args.compare_baseline:
        parser.error("--expect-policy-change requires --compare-baseline")
    output = summarize(args.report, args.authority_log, args.fixed_fps, audit_carcasses=args.audit_carcasses)
    if args.proximity:
        if args.proximity[0] == args.proximity[1]:
            parser.error("--proximity needs two distinct species")
        if not math.isfinite(args.proximity_radius_cm) or args.proximity_radius_cm <= 0:
            parser.error("--proximity-radius-cm must be finite and positive")
        report = json.loads(args.report.read_text(encoding="utf-8-sig"))
        if not report.get("samples") or "agents" not in report["samples"][0]:
            parser.error("--proximity requires an island PIE report")
        output["sampled_species_proximity"] = sampled_species_proximity(report, args.proximity, args.proximity_radius_cm)
    if args.compare_baseline:
        reference = json.loads(args.compare_baseline.read_text(encoding="utf-8-sig"))
        trial = json.loads(args.report.read_text(encoding="utf-8-sig"))
        output["island_baseline_comparison"] = compare_island_baseline(reference, trial, policy_species=args.expect_policy_change)
    print(json.dumps(output, indent=2))
    if args.compare_baseline and not output["island_baseline_comparison"]["matches"]:
        raise SystemExit(1)

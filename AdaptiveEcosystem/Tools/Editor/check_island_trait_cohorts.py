"""Join island cohort snapshots to authoritative life-cycle events."""

import argparse
import json
import re
from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
from itertools import combinations
from math import dist
from pathlib import Path
from statistics import mean, median


# EcoLifeHistoryV3.h parent midpoint variation, before clamping to gene bounds.
GENES = {"speed_gene": .02, "size_gene": .02, "caution_gene": .02,
         "sociability_gene": .02, "coat_gene": .015}
FUNCTIONAL_GENES = {"propulsion_gene": .03, "endurance_gene": .03, "form_gene": .03}
SHAPE_GENES = ("shape_fore_gene", "shape_aft_gene", "shape_span_gene", "shape_rise_gene")
IMMUTABLE = ("species", "parent_a", "parent_b", "generation", "origin", "born", *GENES)
PATCH_MEAL = re.compile(r"\[PatchMeal\] Patch=(\S+) Species=(\S+) Agent=(\d+) Amount=([\d.]+).* At=([\d.]+)")
PATCH_ACCESS_RECEIPT = re.compile(r" Remaining=([\d.]+) Access=(\d+) At=")
CARRION_MEAL = re.compile(r"\[Scavenge\] Eater=\d+ Species=(\S+) Carcass=\d+ Amount=([\d.]+).* At=([\d.]+)")
NATIVE_WOLF_BITE = re.compile(r"\[Scavenge\] Eater=(\d+) Species=Wolf Carcass=\d+ Amount=([\d.]+)")
NATIVE_WOLF_PROVISION = re.compile(
    r"\[EcoLife\]\[WolfProvision\] Parent=(\d+) Child=(\d+) Region=(\S+) At=([\d.]+) Amount=([\d.]+) "
    r"ParentBefore=([\d.]+) ParentAfter=([\d.]+) ChildBefore=([\d.]+) ChildAfter=([\d.]+) DistanceCm=([\d.]+)$")
NATIVE_WOLF_BIRTH_QUEUE = re.compile(r"\[EcoLife\]\[BirthQueued\] Region=(\w+) Predator=1 Parents=(\d+),(\d+) Due=([\d.]+)")
NATIVE_WOLF_BIRTH_DEFER = re.compile(r"\[EcoLife\]\[BirthDeferred\] Region=(\w+) Predator=1 Food=([\d.]+) Consumers=(\d+) Population=(\d+)")
NATIVE_WOLF_BIRTH_CANCEL = re.compile(r"\[Eco Birth Audit\] Region=(\w+) Predator=1 Event=Cancelled EnergyOnly=(\d+)")
NATIVE_WOLF_BIRTH_SEPARATED = re.compile(r"\[EcoLife\]\[BirthPairSeparated\] Region=(\w+) Parents=(\d+),(\d+) At=([\d.]+) DistanceCm=([\d.]+) Allow=([01])")
FAUNA_BIRTH_QUEUE = re.compile(r"\[Eco Fauna\]\[BirthQueued\] Species=(\S+) Parents=(\d+),(\d+) Due=([\d.]+) Nursery=(\S+)")
HABITAT_MEAL = re.compile(r"\[Eco (Refuge|Aquatic) Meal\] Patch=(\S+)(?: Species=(\S+))? At=([\d.]+) "
                          r"Agent=(\d+) Generation=(\d+) AgeFraction=([\d.]+) Gate=(\w+) "
                          r"RangeCm=([\d.]+) Before=([\d.]+) Paid=([\d.]+) After=([\d.]+)")
DEATH_CAUSES = ("none", "starvation", "external_damage", "predation")  # EEcoDeathCause
WATER_REFILL = re.compile(r"\[Eco Water Stock\] Patch=(\S+) At=\S+ Delta=(\S+) Rain=(\S+) "
                          r"Before=(\S+) After=(\S+) Capacity=(\S+) Regen=(\S+)$")
POSITION = re.compile(r"V\(X=([-\d.]+), Y=([-\d.]+), Z=([-\d.]+)\)")
PARENT_ENERGY_FRACTION = .7  # EcoLifeHistoryV3.h; the sampled presentation fraction is quantized.


def values(rows):
    return {key: mean(row[key] for row in rows) for key in (*GENES, *FUNCTIONAL_GENES, *SHAPE_GENES)
            if all(key in row for row in rows)} if rows else None


def gene_ranges(rows):
    result = {}
    for gene in (*GENES, *FUNCTIONAL_GENES, *SHAPE_GENES):
        if not rows or not all(gene in row for row in rows):
            continue
        observed = [row[gene] for row in rows]
        result[gene] = {"min": min(observed), "median": median(observed), "max": max(observed)}
    return result


def sampled_mating_opportunities(cohorts, samples):
    """Summarize simultaneous adult mates for natural descendants at paired sample times."""
    samples_by_time = {sample["completed_clock"]["authority_seconds"]: sample["agents"] for sample in samples}
    summary = defaultdict(Counter)
    best_nearby_pairs = {}
    for cohort in cohorts:
        sampled_agents = samples_by_time.get(cohort["completed_seconds"])
        if sampled_agents is None:
            continue
        sampled_by_id = {str(agent["stable_id"]): agent for agent in sampled_agents}
        adults = defaultdict(list)
        for row in cohort["agents"]:
            native_wolf = row["species"] == "Wolf" and row["backend"] == "native_v3"
            if row["maturity"] >= 1. and (row["sex"] in (1, 2) or native_wolf):
                adults[row["species"]].append(row)
        for species, rows in adults.items():
            if not any(row["generation"] > 0 for row in rows):
                continue
            observed = {"with_mature_descendant"}
            for a, b in combinations(rows, 2):
                native_wolves = species == "Wolf" and a["backend"] == b["backend"] == "native_v3"
                if (not native_wolves and a["sex"] == b["sex"]) or max(a["generation"], b["generation"]) == 0:
                    continue
                parents_a = {a["parent_a"], a["parent_b"]} - {"0"}
                parents_b = {b["parent_a"], b["parent_b"]} - {"0"}
                if a["id"] in parents_b or b["id"] in parents_a or parents_a & parents_b:
                    continue
                if a["region"] != b["region"]:
                    observed.add("with_compatible_mate_in_another_region")
                    continue
                observed.add("with_compatible_regional_mate")
                first, second = (sampled_by_id.get(row["id"]) for row in (a, b))
                if not first or not second or first["region"] != a["region"] or second["region"] != b["region"]:
                    continue
                position_a = POSITION.fullmatch(first["position"])
                position_b = POSITION.fullmatch(second["position"])
                if not position_a or not position_b:
                    continue
                observed.add("with_compatible_regional_mate_position_sample")
                dimensions = 2 if native_wolves else 3
                distance_cm = dist(tuple(map(float, position_a.groups()[:dimensions])), tuple(map(float, position_b.groups()[:dimensions])))
                distance_limit_cm = 2000. if native_wolves else 1000.
                if distance_cm <= distance_limit_cm:
                    distance_field = "with_compatible_mate_within_20m" if native_wolves else "with_compatible_mate_within_10m"
                    observed.add(distance_field)
                    if distance_cm <= 1000.:
                        observed.add("with_compatible_mate_within_10m")
                    lower_energy = min(first["energy_fraction"], second["energy_fraction"])
                    best_pair = best_nearby_pairs.get(species)
                    if best_pair is None or lower_energy > best_pair["lower_energy_fraction"]:
                        best_nearby_pairs[species] = {
                            "authority_seconds": cohort["completed_seconds"],
                            "region": a["region"],
                            "distance_cm": round(distance_cm, 3),
                            "lower_energy_fraction": lower_energy,
                            "partners": [{"id": row["id"], "generation": row["generation"],
                                          "energy_fraction": sample["energy_fraction"]}
                                         for row, sample in ((a, first), (b, second))],
                        }
                    if lower_energy >= PARENT_ENERGY_FRACTION:
                        observed.add(f"{distance_field}_and_sampled_energy")
                        if distance_cm <= 1000.:
                            observed.add("with_compatible_mate_within_10m_and_sampled_energy")
            summary[species].update(observed)
    fields = ("with_mature_descendant", "with_compatible_mate_in_another_region", "with_compatible_regional_mate",
              "with_compatible_regional_mate_position_sample", "with_compatible_mate_within_10m",
              "with_compatible_mate_within_10m_and_sampled_energy")
    return {species: {field: counts[field] for field in fields} | ({
                field: counts[field] for field in ("with_compatible_mate_within_20m",
                                                   "with_compatible_mate_within_20m_and_sampled_energy")
            } if species == "Wolf" else {}) | {
                "best_nearby_pair_lower_energy_fraction":
                    best_nearby_pairs.get(species, {}).get("lower_energy_fraction"),
                "best_nearby_pair": best_nearby_pairs.get(species),
            } for species, counts in summary.items()}


def region_balances(first, last, events):
    def key(row, region="region"):
        return (row[region], row["species"])

    before, after = (Counter(map(key, snapshot["agents"])) for snapshot in (first, last))
    births, deaths, recovery, arrivals = (
        Counter(map(key, events[kind])) for kind in ("birth", "death", "recovery", "migration"))
    departures = Counter(key(row, "previous_region") for row in events["migration"])
    balances = defaultdict(dict)
    addresses = before.keys() | after.keys() | births.keys() | deaths.keys() | recovery.keys() | arrivals.keys() | departures.keys()
    for region, species in sorted(addresses):
        address = (region, species)
        expected = before[address] + births[address] + recovery[address] + arrivals[address] - deaths[address] - departures[address]
        balances[region][species] = {
            "initial": before[address], "final": after[address], "births": births[address],
            "deaths": deaths[address], "recovery": recovery[address], "arrivals": arrivals[address],
            "departures": departures[address], "unexplained": after[address] - expected,
        }
    return balances


def managed_stock_intervals(report, payments_by_site):
    result = {}
    samples = report["samples"]
    for site, payments in payments_by_site.items():
        profile = report["initial_patch_inputs"]["patches"][site]
        intervals = []
        for before, after in zip(samples, samples[1:]):
            t0, t1 = (row["completed_clock"]["authority_seconds"] for row in (before, after))
            amounts = [amount for when, amount in payments if t0 + .0005 < when <= t1 + .0005]
            paid = sum(amounts)
            regenerated = after["stocks"][site] - before["stocks"][site] + paid
            # UpdateFaunaHabitatStock uses a rainfall multiplier of 0.75–1.25 for these reserves.
            limit = (t1 - t0) * profile["regrowth_per_second"] * 1.25
            tolerance = .002 + .0005 * len(amounts)  # log precision in stock payments and timestamps
            intervals.append({"end": t1, "paid": paid, "inferred_regrowth": regenerated,
                              "consistent": -tolerance <= regenerated <= limit + tolerance})
        result[site] = intervals
    return result


def summarize_land_forage_access(report, receipts, seen):
    summary = {}
    for site, rows in receipts.items():
        patch = report["initial_patch_inputs"]["patches"][site]
        delivery = defaultdict(Counter)
        capacity = patch["capacity"]
        growth_limit = patch["regrowth_per_second"] * max(patch["plant_growth_rainfall"])
        loss_limit = patch["plant_dry_loss_per_second"]
        tolerance = .002 + .001 * (growth_limit + loss_limit)  # Printed stock and authority time use three decimals.
        previous = None
        shared_tick_payments = 0
        for species, agent, at, amount, after, access in rows:
            before = after + amount
            if access > len(patch["forage_access_points"]) or amount <= 0. or before > capacity + tolerance:
                raise ValueError(f"Invalid forage access or balance for {site}/{agent} at {at}")
            if previous is not None:
                previous_at, previous_after, previous_access = previous
                elapsed = at - previous_at
                lower = max(0., previous_after - elapsed * loss_limit)
                upper = min(capacity, previous_after + elapsed * growth_limit)
                if elapsed < 0. or not lower - tolerance <= before <= upper + tolerance:
                    raise ValueError(f"Forage access did not share its patch balance for {site} at {at}")
                shared_tick_payments += elapsed == 0. and access != previous_access
            previous = at, after, access
            identity = seen.get(agent)
            if identity is None or identity["species"] != species:
                raise ValueError(f"Forage access receipt lacked a matching species and lineage for {site}/{agent}")
            delivery[species, identity["generation"], access].update(payments=1, paid_energy=amount)
        summary[site] = {"shared_tick_payments_at_different_points": shared_tick_payments,
                         "delivery": [{"species": species, "generation": generation, "access": access,
                                       "payments": counts["payments"], "paid_energy": round(counts["paid_energy"], 3)}
                                      for (species, generation, access), counts in sorted(delivery.items())]}
    return summary


def summarize_native_food_survey(report, events):
    survey = report["wolf_food_survey"]
    snapshots = {row["completed_clock"]["authority_seconds"]: row["agents"] for row in report["samples"]}
    samples = survey["samples"]
    if len(samples) != len(snapshots) or not samples:
        raise ValueError("Missing Grassland survey snapshots")
    low = []
    by_deer = defaultdict(list)
    extended_approaches = 0
    observed_approaches = set()
    for site in samples:
        if abs(site["total_stock"] - site["ledger_stock"]) > 1e-6:
            raise ValueError("Grassland Native grid and authority stock differ")
        agents = {str(row["stable_id"]): row for row in snapshots[site["at"]]}
        for nearby in site["deer_below_30_percent_energy"]:
            agent = agents[str(nearby["id"])]
            target = agent.get("local_forage_cell", -1)
            if (agent.get("forage_scan_wait", 0.) > 1. and agent.get("motion_reason") == 1
                    and target >= 0 and target != agent["native_food_cell"]):
                extended_approaches += 1
                observed_approaches.add(str(nearby["id"]))
            row = {"at": site["at"], "distance": nearby["nearest_usable_stock_distance_cm"],
                   "local_stock": agent["native_food_remaining"], "intake": agent["last_plant_intake"]}
            low.append(row)
            by_deer[str(nearby["id"])].append(row)
    opening = report["samples"][0]["vegetation"]["Grassland"]
    closing = report["samples"][-1]["vegetation"]["Grassland"]
    if any(abs(grid["consumed"] - grid["ledger_consumed"]) > 1e-6 for grid in (opening, closing)):
        raise ValueError("Grassland Native plant consumption differs from the authority ledger")
    losses = Counter()
    before_starvation = []
    for event in events["death"]:
        if event["species"] != "Herbivore" or event["region"] != "Grassland":
            continue
        cause = DEATH_CAUSES[event["death_cause"]]
        losses[cause] += 1
        if cause == "starvation":
            recent = [row for row in by_deer[event["id"]] if 0. <= event["sample_seconds"] - row["at"] <= 30.5]
            if recent:
                before_starvation.append(recent[-1])
    distances = [row["distance"] for row in low if row["distance"] is not None]
    if survey.get("forage_approach") is False and extended_approaches:
        raise ValueError("Control exceeded its one-second forage scan interval")
    return {"forage_approach": survey.get("forage_approach"), "regional_samples": len(samples),
            "low_energy_samples": len(low), "deer_sampled": len(by_deer),
            "low_energy_samples_with_intake": sum(row["intake"] > 0. for row in low),
            "low_energy_samples_local_stock_below_002": sum(row["local_stock"] < .02 for row in low),
            "low_energy_median_nearest_stock_cm": median(distances) if distances else None,
            "extended_approach_samples": extended_approaches, "extended_approach_deer": len(observed_approaches),
            "grassland_native_plants_consumed": closing["consumed"] - opening["consumed"],
            "grassland_native_plants_grown": closing["grown"] - opening["grown"],
            "grassland_deer_deaths": dict(losses), "starvation_deaths_with_recent_sample": len(before_starvation),
            "starvation_deaths_with_local_stock_below_002": sum(row["local_stock"] < .02 for row in before_starvation),
            "starvation_deaths_with_stock_within_6m": sum(row["distance"] is not None and row["distance"] <= 600.
                                                              for row in before_starvation),
            "grassland_final_population": report["samples"][-1]["regional_population"].get("Grassland", {})}


def check_native_wolf_provision(receipts, events, enabled):
    births = {row["id"]: row for row in events["birth"] if row["species"] == "Wolf"}
    previous = {}
    transfers = defaultdict(list)
    if receipts and not enabled:
        raise ValueError("Native wolf provisions were paid with the option off")
    for parent, child, region, *amounts in receipts:
        at, amount, parent_before, parent_after, child_before, child_after, distance = map(float, amounts)
        birth = births.get(child)
        if (not birth or parent not in (birth["parent_a"], birth["parent_b"])
                or not birth["born"] <= at < birth["born"] + 180.
                or not 0. < amount <= .010000001 or parent_after < .549999999 or child_after > .650000001
                or at - previous.get(child, -1.) < .999998 or distance > 650.001
                or abs((parent_before - parent_after) - amount) > 2e-9
                or abs((child_after - child_before) - amount) > 2e-9):
            raise ValueError(f"Invalid Native wolf provision at {region}/{at} from {parent} to {child}")
        previous[child] = at
        transfers[child].append({"parent": parent, "region": region, "at": at, "normalized_nutrition": amount,
                                 "parent_before": parent_before, "parent_after": parent_after,
                                 "child_before": child_before, "child_after": child_after, "distance_cm": distance})
    return transfers


def summarize_native_wolf_forage(samples, events, paid, provisions):
    if not samples or not samples[0]["wolves"]:
        raise ValueError("Native wolf foraging survey missed the starting animals")
    by_wolf = defaultdict(list)
    provisioning = samples[0].get("provisioning_enabled", False)
    transfers = check_native_wolf_provision(provisions, events, provisioning)
    births = {row["id"]: row for row in events["birth"] if row["species"] == "Wolf"}
    previous = -1.
    for sample in samples:
        if (sample["at"] <= previous or sample["region"] != "Grassland"
                or sample.get("provisioning_enabled", False) != provisioning):
            raise ValueError("Native wolf foraging survey samples are out of order or region")
        previous = sample["at"]
        for wolf in sample["wolves"]:
            if not 0 <= wolf["clear_sight_in_range"] <= wolf["open_stock_in_range"] <= wolf["open_stock"]:
                raise ValueError("Native wolf foraging survey did not preserve the carrion filters")
            parent_target = wolf.get("parent_target", "0")
            if parent_target != "0":
                birth = births.get(wolf["id"])
                if not provisioning or not birth or parent_target not in (birth["parent_a"], birth["parent_b"]):
                    raise ValueError("Native wolf selected an unrelated provisioning target")
            by_wolf[wolf["id"]].append(wolf | {"at": sample["at"]})

    findings = {}
    for agent, rows in by_wolf.items():
        deaths = [event for event in events["death"] if event["id"] == agent and event["species"] == "Wolf"]
        distances = [row["nearest_open_stock_cm"] for row in rows if "nearest_open_stock_cm" in row]
        selected = [row for row in rows if row["carrion_target"] != "0"]
        findings[agent] = {"generation": rows[0]["generation"], "samples": len(rows),
                           "sample_interval": [rows[0]["at"], rows[-1]["at"]],
                           "with_open_stock_in_region": sum(row["open_stock"] > 0 for row in rows),
                           "with_open_stock_in_range": sum(row["open_stock_in_range"] > 0 for row in rows),
                           "with_open_stock_in_clear_sight": sum(row["clear_sight_in_range"] > 0 for row in rows),
                           "with_selected_carrion": len(selected),
                           "at_selected_carrion_bite_distance_and_speed": sum(row.get("target_in_contact", False)
                               and row.get("target_bite_speed", False) for row in selected),
                           "hunting_with_prey_target": sum(row["hunting"] and row["has_prey_target"] for row in rows),
                           "nearest_open_stock_cm": min(distances) if distances else None,
                           "logged_carrion_energy": round(paid[agent], 3),
                           "with_parent_target": sum(row.get("parent_target", "0") != "0" for row in rows),
                           "parent_transfer_count": len(transfers[agent]),
                           "parent_transfer_energy": round(sum(row["normalized_nutrition"] * 100.
                                                               for row in transfers[agent]), 5),
                           "sampled_reserved_meat_consumed": max(row["reserved_meat_consumed"] for row in rows),
                           "death_cause": DEATH_CAUSES[deaths[0]["death_cause"]] if deaths else None,
                           "death_seconds": deaths[0]["sample_seconds"] if deaths else None}
    return {"samples": len(samples), "wolves": findings, "provisioning_enabled": provisioning,
            "parent_transfer_receipts": {child: rows for child, rows in transfers.items() if rows}}


def summarize_native_wolf_birth_requests(founders, log_path, first_seconds, last_seconds, *,
                                         resume_marker=None, reservation=None):
    """Reconstruct the Native prey count at each logged delivery decision."""
    living = dict(founders)
    pending = {}
    attempts = []
    region_scope = None
    if reservation is not None:
        region_scope = "Grassland"
        parents = reservation["parents"]
        initial = {"region": region_scope, "parents": parents, "due": reservation["due"],
                   "parent_generations": [living[parent]["generation"] for parent in parents],
                   "outcome": "no_terminal_receipt"}
        pending[region_scope] = initial
        attempts.append(initial)
    with log_path.open(encoding="utf-8-sig") as log:
        if resume_marker is not None and not any(resume_marker in line for line in log):
            raise ValueError(f"Missing wolf birth checkpoint marker in {log_path}")
        for line in log:
            if "[EcoTrait] " in line:
                event = json.loads(line.split("[EcoTrait] ", 1)[1])
                if not first_seconds < event["sample_seconds"] <= last_seconds:
                    continue
                kind, agent = event["event"], event["id"]
                if kind in {"birth", "recovery", "migration"}:
                    living[agent] = event
                elif kind == "death":
                    living.pop(agent, None)
                if kind == "birth" and event["species"] == "Wolf":
                    attempt = pending.get(event["region"])
                    if attempt and set(attempt["parents"]) == {event["parent_a"], event["parent_b"]}:
                        local = Counter(row["species"] for row in living.values() if row["region"] == event["region"])
                        attempt.update(outcome="born", child=agent, generation=event["generation"], born=event["born"],
                                       native_prey=local["Herbivore"], native_wolves=local["Wolf"] - 1,
                                       required_native_prey=8 * local["Wolf"])
                        del pending[event["region"]]
            elif (queued := NATIVE_WOLF_BIRTH_QUEUE.search(line)):
                region, first, second, due = queued.groups()
                if region_scope and region != region_scope:
                    continue
                parents = [first, second]
                row = {"region": region, "parents": parents,
                       "parent_generations": [living.get(parent, {}).get("generation") for parent in parents],
                       "due": float(due), "outcome": "no_terminal_receipt"}
                pending[region] = row
                attempts.append(row)
            elif (deferred := NATIVE_WOLF_BIRTH_DEFER.search(line)):
                region, food, consumers, population = deferred.groups()
                attempt = pending.pop(region, None)
                if attempt:
                    species = Counter(row["species"] for row in living.values() if row["region"] == region)
                    attempt.update(outcome="deferred", region_food=float(food), all_food_consumers=int(consumers),
                                   authority_population=int(population), reconstructed_population=sum(species.values()),
                                   native_prey=species["Herbivore"], native_wolves=species["Wolf"],
                                   required_native_prey=8 * (species["Wolf"] + 1))
            elif (cancelled := NATIVE_WOLF_BIRTH_CANCEL.search(line)):
                region, energy_only = cancelled.groups()
                attempt = pending.pop(region, None)
                if attempt:
                    attempt.update(outcome="cancelled", parents_below_energy_gate=int(energy_only))
            elif (separated := NATIVE_WOLF_BIRTH_SEPARATED.search(line)):
                region, first, second, stamp, distance, allowed = separated.groups()
                if region_scope and region != region_scope:
                    continue
                attempt = pending.get(region)
                if not attempt or attempt["parents"] != [first, second]:
                    raise ValueError(f"Native wolf separation did not match a reserved pair: {region}/{stamp}")
                attempt.update(parent_distance_at_delivery_cm=float(distance), checked_at=float(stamp))
                if allowed == "0":
                    attempt["outcome"] = "parent_separation"
                    del pending[region]
    return attempts


def summarize_rule_breeding(log_path, cohorts):
    first, last = cohorts[0], cohorts[-1]
    lineage = {row["id"]: row for row in first["agents"]}
    latest_request = {}
    requests = defaultdict(list)
    with log_path.open(encoding="utf-8-sig") as log:
        for line in log:
            if queued := FAUNA_BIRTH_QUEUE.search(line):
                species, a, b, due, nursery = queued.groups()
                parents = [lineage.get(a), lineage.get(b)]
                if not all(parents) or any(parent["species"] != species for parent in parents):
                    raise ValueError(f"Unlinked rule parents {species}/{a},{b}")
                generations = [parent["generation"] for parent in parents]
                request = {"parents": [a, b], "parent_generations": generations, "expected_generation": 1 + max(generations),
                           "due": float(due), "nursery": nursery, "child": None}
                requests[species].append(request)
                latest_request[species, a, b] = request
            if "[EcoTrait] " not in line:
                continue
            row = json.loads(line.split("[EcoTrait] ", 1)[1])
            if (row["epoch"] != first["epoch"] or row["event"] not in {"birth", "recovery"}
                    or not first["completed_seconds"] < row["sample_seconds"] <= last["completed_seconds"]):
                continue
            lineage[row["id"]] = row
            if row["event"] != "birth" or row["backend"] != "rule":
                continue
            request = latest_request.pop((row["species"], row["parent_a"], row["parent_b"]), None)
            # The scheduler retains reservations up to 20 seconds after Due. The text log rounds Due to two decimals.
            if (request is None or row["generation"] != request["expected_generation"]
                    or not -.0051 <= row["born"] - request["due"] <= 20.0051):
                raise ValueError(f"No matching rule birth reservation for {row['species']}/{row['id']}")
            request.update(child=row["id"], born=row["born"], region=row["region"],
                           size_gene=row["size_gene"], speed_gene=row["speed_gene"])
    result = {}
    for species, records in requests.items():
        summary = result[species] = {"queued_by_generation": dict(Counter(row["expected_generation"] for row in records)),
                                     "committed_by_generation": dict(Counter(row["expected_generation"] for row in records if row["child"])),
                                     "descendant_requests": []}
        for row in records:
            if row["expected_generation"] < 2:
                continue
            outcome = "committed" if row["child"] else "no_commit_observed"
            if not row["child"] and row["due"] + 20. >= last["completed_seconds"]:
                outcome = "delivery_window_incomplete"
            summary["descendant_requests"].append(dict(row, outcome=outcome))
    return result


def read_run(report_path, log_path):
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    evidence = report["trait_evidence"]
    first, *_, last = evidence["cohorts"]
    epoch = first["epoch"]
    maintenance = first.get("heritable_fauna_maintenance", False)
    approach = first.get("aquatic_nursery_approach", False)
    continuity = first.get("predator_continuity", False)
    covered_refuge_forage = first.get("covered_refuge_forage", False)
    refuge_rotation = first.get("covered_refuge_meal_rotation", False)
    aquatic_rotation = first.get("aquatic_patch_meal_rotation", False)
    land_plant_rotation = first.get("land_plant_meal_rotation", False)
    founders = {row["id"]: row for row in first["agents"]}
    seen = dict(founders)
    mature = set()
    parents = defaultdict(list)
    events = defaultdict(list)
    death_causes = defaultdict(Counter)
    death_causes_by_generation = defaultdict(lambda: defaultdict(Counter))
    patch_meals = defaultdict(Counter)
    patch_meals_by_agent = Counter()
    carrion_meals = Counter()
    native_wolf_bites = Counter()
    native_wolf_provisions = []
    hunt_deaths = Counter()
    hunt_victims = defaultdict(list)
    player_damage = defaultdict(Counter)
    hatches = {}
    nest_hatches = {}
    refuge_births = {}
    habitat_access = defaultdict(Counter)
    habitat_participants = defaultdict(set)
    latest_habitat_payment = {}
    managed_food_patches = {row["patch_id"] for row in report.get("predator_habitat", {}).values()}
    managed_food_patches.update(row["patch"] for row in report.get("eagle_families", {}).get("food", ()))
    neighborhood = report.get("aquatic_neighborhoods")
    if neighborhood:
        managed_food_patches.update(("IslandRiverGravelInsects", neighborhood["catfish"]["patch"],
                                     neighborhood["small_fish"]["source"], neighborhood["small_fish"]["patch"]))
    managed_food = Counter()
    managed_payments = {site: [] for site in managed_food_patches}
    managed_food_before_birth = defaultdict(dict)
    land_access_receipts = {site: [] for site in report.get("land_forage_access", {})}
    latest_trait = None
    with log_path.open(encoding="utf-8-sig") as log:
        for line in log:
            if "wolf_carrion_survey" in report and (wolf_bite := NATIVE_WOLF_BITE.search(line)):
                native_wolf_bites[wolf_bite[1]] += float(wolf_bite[2])
            if "[EcoLife][WolfProvision]" in line:
                wolf_provision = NATIVE_WOLF_PROVISION.search(line)
                if not wolf_provision:
                    raise ValueError("Malformed Native wolf provision receipt")
                native_wolf_provisions.append(wolf_provision.groups())
            if "[Eco Refuge Meal]" in line or "[Eco Aquatic Meal]" in line:
                receipt = HABITAT_MEAL.search(line)
                if receipt is None:
                    raise ValueError("Invalid habitat meal record")
                medium, site, species_name, stamp, agent, generation, age, gate, _distance, before, amount, after = receipt.groups()
                if first["completed_seconds"] < float(stamp) <= last["completed_seconds"]:
                    before, amount, after = map(float, (before, amount, after))
                    if abs(before - amount - after) > .000002 or ((gate == "Paid") != (amount > 0.)):
                        raise ValueError(f"Habitat meal does not balance at {site}/{stamp}/{agent}")
                    age_group = f"generation_{generation}_{'adult' if float(age) >= 1. else 'juvenile'}"
                    key = (medium, species_name if medium == "Aquatic" else None, age_group)
                    habitat_participants[key].add(agent)
                    habitat_access[key][gate] += 1
                    if amount > 0.:
                        habitat_access[key]["paid_energy"] += amount
                        latest_habitat_payment[site] = stamp, agent, generation
                    elif gate == "Unavailable":
                        previous = latest_habitat_payment.get(site)
                        if previous and previous[0] == stamp and previous[1] != agent:
                            habitat_access[key]["unavailable_after_other_payment"] += 1
                            if previous[2] == "0":
                                habitat_access[key]["unavailable_after_founder_payment"] += 1
            if "[RefugeBirth]" in line and latest_trait and latest_trait["event"] == "birth":
                birth = re.search(r"\[RefugeBirth\] Shelter=(\S+) Child=(\d+) Species=(\S+) HeightZ=([-\d.]+)", line)
                if birth and birth[2] == latest_trait["id"] and birth[3] == latest_trait["species"]:
                    refuge_births[birth[2]] = {"site": birth[1], "floor_z_cm": float(birth[4])}
            if "Hatch]" in line and latest_trait and latest_trait["event"] == "birth":
                hatch = re.search(r"\[(AquaticHatch|NestHatch)\] (?:Nursery|Nest)=(\S+) Child=(\d+) Species=(\S+)", line)
                if hatch:
                    kind, site, child, name = hatch.groups()
                    if child == latest_trait["id"] and name == latest_trait["species"]:
                        (hatches if kind == "AquaticHatch" else nest_hatches)[child] = site
            if "[PatchMeal]" in line:
                paid = PATCH_MEAL.search(line)
                if paid:
                    site, species, agent, value, time = paid.groups()
                    amount, at = float(value), float(time)
                    if first["completed_seconds"] < at <= last["completed_seconds"]:
                        patch_meals[species][site] += amount
                        patch_meals_by_agent[species, agent] += amount
                        if site in land_access_receipts:
                            access_receipt = PATCH_ACCESS_RECEIPT.search(line)
                            if access_receipt is None:
                                raise ValueError(f"Missing forage access receipt for {site}/{agent} at {at}")
                            after, access = access_receipt.groups()
                            land_access_receipts[site].append((species, agent, at, amount, float(after), int(access)))
                    if site in managed_food_patches:
                        managed_food[agent] += amount
                        managed_payments[site].append((at, amount))
            if "[Scavenge]" in line:
                paid = CARRION_MEAL.search(line)
                if paid and first["completed_seconds"] < float(paid[3]) <= last["completed_seconds"]:
                    carrion_meals[paid[1]] += float(paid[2])
            if "[EcoTrait] " not in line:
                continue
            row = json.loads(line.split("[EcoTrait] ", 1)[1])
            latest_trait = None
            if row["epoch"] != epoch or not first["completed_seconds"] < row["sample_seconds"] <= last["completed_seconds"]:
                continue
            latest_trait = row
            kind = row["event"]
            events[kind].append(row)
            if kind == "death":
                cause = row.get("death_cause", -1)
                name = DEATH_CAUSES[cause] if 0 <= cause < len(DEATH_CAUSES) else "unknown"
                death_causes[row["species"]][name] += 1
                death_causes_by_generation[row["species"]][row["generation"]][name] += 1
                if row["player_hunt_receipt"]:
                    hunt_deaths[row["species"]] += 1
                    hunt_victims[row["species"]].append({key: row[key] for key in (
                        "id", "region", "sex", "generation", "maturity", "size_gene", "speed_gene", "sample_seconds")})
            if kind == "player_hit":
                player_damage[row["species"]][row["id"]] += row["damage"]
            if kind == "recovery" and (row["origin"] != 2 or row["generation"] != 0
                                       or row["parent_a"] != "0" or row["parent_b"] != "0"):
                raise ValueError(f"Invalid recovery founder provenance for {row['id']}")
            if kind == "birth":
                parent_ids = (row["parent_a"], row["parent_b"])
                if row["origin"] != 1 or "0" in parent_ids or len(set(parent_ids)) != 2:
                    raise ValueError(f"Invalid natural birth lineage for {row['id']}")
                pair = [seen.get(parent_id) for parent_id in parent_ids]
                if all(pair):
                    if {parent["species"] for parent in pair} != {row["species"]}:
                        raise ValueError(f"Mismatched parent species for {row['id']}")
                    if row["generation"] != 1 + max(parent["generation"] for parent in pair):
                        raise ValueError(f"Mismatched generation for {row['id']}")
                    for gene, variation in (GENES | FUNCTIONAL_GENES).items():
                        if gene == "coat_gene" and first.get("coat_palette", False):
                            a, b = (parent[gene] for parent in pair)
                            candidates = [.75 * a + .25 * b, .25 * a + .75 * b]
                            if not any(max(.85, value - .02) - 1e-9 <= row[gene] <= min(1.15, value + .02) + 1e-9
                                       for value in candidates):
                                raise ValueError(f"Coat outside parent variation for {row['id']}")
                            continue
                        if gene in FUNCTIONAL_GENES and gene not in row and all(gene not in parent for parent in pair):
                            continue
                        if abs(row[gene] - mean(parent[gene] for parent in pair)) > variation + 1e-9:
                            raise ValueError(f"Inheritance outside parent variation for {row['id']}/{gene}")
                        if gene in FUNCTIONAL_GENES and not .82 <= row[gene] <= 1.18:
                            raise ValueError(f"Functional gene outside valid range for {row['id']}/{gene}")
                    for gene in SHAPE_GENES:
                        if gene not in row and all(gene not in parent for parent in pair):
                            continue
                        a, b = (parent[gene] for parent in pair)
                        candidates = [.75 * a + .25 * b, .25 * a + .75 * b]
                        if not -.15 <= row[gene] <= .15 or not any(
                                max(-.15, value - .02) - 1e-9 <= row[gene] <= min(.15, value + .02) + 1e-9
                                for value in candidates):
                            raise ValueError(f"Body shape outside inherited variation for {row['id']}/{gene}")
                    parents[row["species"]].extend(pair)
                if row["species"] in report.get("predator_habitat", {}):
                    managed_food_before_birth[row["species"]][row["id"]] = {parent: managed_food[parent] for parent in parent_ids}
            check_identity(seen, row)
            if row["maturity"] >= 1.:
                mature.add(row["id"])
    for cohort in evidence["cohorts"]:
        ids = set()
        if (cohort["epoch"] != epoch or cohort["heritable_flight"] != first["heritable_flight"]
                or cohort.get("heritable_fauna_maintenance", False) != maintenance
                or cohort.get("aquatic_nursery_approach", False) != approach
                or cohort.get("predator_continuity", False) != continuity
                or cohort.get("covered_refuge_forage", False) != covered_refuge_forage
                or cohort.get("covered_refuge_meal_rotation", False) != refuge_rotation
                or cohort.get("aquatic_patch_meal_rotation", False) != aquatic_rotation
                or cohort.get("land_plant_meal_rotation", False) != land_plant_rotation
                or cohort.get("functional_traits", False) != first.get("functional_traits", False)):
            raise ValueError("Authority epoch or trait rule changed during cohort sampling")
        for row in cohort["agents"]:
            if row["id"] in ids:
                raise ValueError(f"Duplicate stable ID {row['id']}")
            ids.add(row["id"])
            check_identity(seen, row)
            if row["maturity"] >= 1.:
                mature.add(row["id"])
    living = {row["id"] for row in last["agents"]}
    born = {row["id"] for row in events["birth"]}
    recovered = {row["id"] for row in events["recovery"]}
    deaths_by_id = {row["id"]: row for row in events["death"]}
    died = set(deaths_by_id)
    if (len(born) != len(events["birth"]) or len(recovered) != len(events["recovery"])
            or len(died) != len(events["death"]) or recovered & (founders.keys() | born)):
        raise ValueError("Duplicate or overlapping committed birth, recovery or death")
    accounted = (founders.keys() | born | recovered) - died

    mating_samples = sampled_mating_opportunities(evidence["cohorts"], report["samples"])
    patch_meals_by_generation = defaultdict(Counter)
    unlinked_patch_meals = Counter()
    for (species_name, agent), paid in patch_meals_by_agent.items():
        identity = seen.get(agent)
        if identity is None:
            unlinked_patch_meals[species_name] += paid
        elif identity["species"] != species_name:
            raise ValueError(f"Patch payment species differed from the agent's identity for {agent}")
        else:
            patch_meals_by_generation[species_name][identity["generation"]] += paid
    species = {}
    for name in sorted({row["species"] for row in founders.values()}):
        start = [row for row in founders.values() if row["species"] == name]
        offspring = [row for row in events["birth"] if row["species"] == name]
        adult_start = [row for row in start if row["maturity"] >= 1.]
        regional_births = defaultdict(lambda: defaultdict(list))
        for row in offspring:
            regional_births[row["region"]][row["generation"]].append(row)
        attempts = evidence.get("cruise", {}).get(name, [])
        observed = [row for cohort in evidence["cohorts"] for row in cohort["agents"] if row["species"] == name]
        offspring_ids = {row["id"] for row in offspring}
        mature_offspring_energy = (row["energy"] for row in observed if row["id"] in offspring_ids and row["maturity"] >= 1.)
        adult_appearance = [row for row in observed if row["maturity"] >= 1. and "visual_body_scale" in row]
        population = [(sample["completed_clock"]["authority_seconds"], sample["population"].get(name, 0))
                      for sample in report["samples"]]
        species[name] = {
            "initial_alive": len(start), "final_alive": sum(seen[i]["species"] == name for i in living),
            "living_by_generation": dict(Counter(row["generation"] for row in last["agents"] if row["species"] == name)),
            "initial_backends": report.get("initial_backends", {}).get(name, []),
            "first_absent_sample_seconds": next((when for when, count in population if not count), None),
            "peak_sampled_alive": max(count for _, count in population),
            "deaths_by_cause": dict(death_causes[name]),
            "death_causes_by_generation": death_causes_by_generation[name],
            "habitat_paid_energy_by_site": dict(patch_meals[name]),
            "habitat_paid_energy_by_generation": {generation: round(amount, 3)
                                                   for generation, amount in patch_meals_by_generation[name].items()},
            "habitat_paid_energy_without_lineage": round(unlinked_patch_meals[name], 3),
            "timed_carrion_paid_energy": carrion_meals[name],
            "births_by_generation": dict(Counter(row["generation"] for row in offspring)),
            "offspring_observed_mature": sum(row["id"] in mature for row in offspring),
            "mature_offspring_by_generation": dict(Counter(row["generation"] for row in offspring if row["id"] in mature)),
            "mature_offspring_peak_sampled_energy": max(mature_offspring_energy, default=None),
            "sampled_descendant_mating_opportunities": mating_samples.get(name, {}),
            "parents_with_linked_offspring": len({row["id"] for row in parents[name]}),
            "births_with_both_parents_linked": len(parents[name]) // 2,
            "parent_contributions": dict(Counter(row["id"] for row in parents[name])),
            "natural_offspring": [{field: row[field] for field in ("id", "parent_a", "parent_b", "region", "generation",
                                                                   "sex", "born", *GENES)} | {
                "observed_mature": row["id"] in mature, "living_at_end": row["id"] in living,
                "habitat_paid_energy": round(patch_meals_by_agent[name, row["id"]], 3),
                "death_seconds": deaths_by_id.get(row["id"], {}).get("sample_seconds"),
                "death_cause": deaths_by_id.get(row["id"], {}).get("death_cause"),
            } for row in offspring],
            "player_hunt_deaths": hunt_deaths[name],
            "player_hunt_victims": hunt_victims[name],
            "committed_player_damage": sum(player_damage[name].values()),
            "player_damage_by_target": dict(player_damage[name]),
            "founder_means": values(start), "parent_contribution_means": values(parents[name]),
            "adult_founder_means": values(adult_start),
            "surviving_adult_founder_means": values([row for row in adult_start if row["id"] in living]),
            "offspring_means": values(offspring),
            "aquatic_hatches_by_site": dict(Counter(hatches[row["id"]] for row in offspring if row["id"] in hatches)),
            "nest_hatches_by_site": dict(Counter(nest_hatches[row["id"]] for row in offspring if row["id"] in nest_hatches)),
            "covered_refuge_births": {row["id"]: refuge_births[row["id"]] for row in offspring if row["id"] in refuge_births},
            "offspring_by_natal_region_and_generation": {
                region: {generation: {"count": len(rows), "matured": sum(row["id"] in mature for row in rows),
                                      "living_at_end": sum(row["id"] in living for row in rows),
                                      "means": values(rows),
                                      "gene_ranges": gene_ranges(rows),
                                      "parent_contributions": dict(Counter(
                                          row[key] for row in rows for key in ("parent_a", "parent_b")))}
                         for generation, rows in cohorts.items()}
                for region, cohorts in regional_births.items()
            },
        }
        if name in report.get("predator_habitat", {}):
            species[name]["parent_managed_forage_before_birth"] = managed_food_before_birth[name]
        releases = [row for row in events["recovery"] if row["species"] == name]
        if releases:
            species[name]["recovery_founders"] = [
                {field: row[field] for field in ("id", "region", "sample_seconds", *IMMUTABLE)} | {
                    "living_at_end": row["id"] in living,
                    "habitat_paid_energy": round(patch_meals_by_agent[name, row["id"]], 3),
                } for row in releases]
        if adult_appearance:
            species[name]["adult_authority_appearance"] = {
                "individuals": len({row["id"] for row in adult_appearance}),
                "scaled_values": sorted({row["visual_body_scale"] for row in adult_appearance}),
                "within_quantization": sum(abs(row["visual_body_scale"] - row["body_scale"]) <= .5 / 128. + 1e-9
                                           for row in adult_appearance),
                "samples": len(adult_appearance),
            }
        functional_adults = [row for row in adult_appearance if "visual_inherited_width" in row]
        if functional_adults:
            axes = ("visual_inherited_length", "visual_inherited_width", "propulsion_multiplier",
                    "activity_cost_multiplier", "rest_cost_multiplier", "form_reach_multiplier",
                    "body_width_multiplier", "body_height_multiplier", "swim_clearance_multiplier")
            species[name]["functional_adult_ranges"] = {
                key: [min(row[key] for row in functional_adults), max(row[key] for row in functional_adults)]
                for key in axes if all(key in row for row in functional_adults)
            }
        if attempts:
            cap_ratios = [row["horizontal_speed_cm_s"] / row["cruise_cap_cm_s"] for row in attempts]
            drains = [row["stamina_drain_per_second"] for row in attempts
                      if row.get("stamina_drain_per_second") is not None and row["horizontal_speed_cm_s"] > 0.]
            species[name]["cruise"] = {
                "samples": len(attempts), "movers": len({row["id"] for row in attempts if row["horizontal_speed_cm_s"] > 0}),
                "cap_range_cm_s": [min(row["cruise_cap_cm_s"] for row in attempts),
                                   max(row["cruise_cap_cm_s"] for row in attempts)],
                "measured_speed_range_cm_s": [min(row["horizontal_speed_cm_s"] for row in attempts),
                                              max(row["horizontal_speed_cm_s"] for row in attempts)],
                "at_cap_samples": sum(abs(ratio - 1.) < .01 for ratio in cap_ratios),
            }
            if drains:
                species[name]["cruise"]["stamina_drain_per_second_range"] = [min(drains), max(drains)]
        rates = [row["maintenance_energy_per_second"] for row in start if "maintenance_energy_per_second" in row]
        if rates:
            species[name]["founder_maintenance_rate_range"] = [min(rates), max(rates)]
    summary = {"heritable_flight": first["heritable_flight"], "heritable_fauna_maintenance": maintenance,
               "functional_traits": first.get("functional_traits", False),
               "aquatic_nursery_approach": approach, "predator_continuity": continuity,
               "covered_refuge_forage": covered_refuge_forage,
               "covered_refuge_meal_rotation": refuge_rotation,
               "aquatic_patch_meal_rotation": aquatic_rotation,
               "land_plant_meal_rotation": land_plant_rotation,
               "last_seconds": last["completed_seconds"],
               "events": {kind: len(rows) for kind, rows in events.items()},
               "alive_missing_from_receipts": sorted(living - accounted),
               "receipts_missing_from_alive": sorted(accounted - living), "species": species,
               "regional_balances": region_balances(first, last, events)}
    selection = report.get("combat_selection", {})
    policy = selection.get("policy")
    if policy in {"VisibleLargest", "VisibleSmallest"}:
        candidates = sorted((row for row in founders.values() if row["species"] == "Herbivore"
                             and row["region"] == "Grassland" and row["generation"] == 0
                             and row["sex"] == 2 and row["maturity"] >= 1. and row["hp"] > 0.),
                            key=lambda row: int(row["id"]))
        body_scales = {row["visual_body_scale"] for row in candidates}
        if len(body_scales) < 2:
            raise ValueError("Visual selection lacked two distinct candidate scales")
        rank = max if policy == "VisibleLargest" else min
        expected = rank(candidates, key=lambda row: row["visual_body_scale"])
        target_id = expected["id"]
        visual = selection.get("first_shot_visual", {})
        actor_scale = visual.get("actor_scale", ())
        if (str(selection["target"]) != target_id or str(visual.get("target")) != target_id
                or visual.get("body_scale") != expected["visual_body_scale"] or not visual.get("mesh")
                or len(actor_scale) != 3
                or not all(abs(scale - expected["visual_body_scale"]) < .0001 for scale in actor_scale)):
            raise ValueError("Visual selection did not use the expected living representation")
        if {agent: paid for counts in player_damage.values() for agent, paid in counts.items()} != {target_id: 100.}:
            raise ValueError("Visual selection had unmatched authoritative damage")
        victims = [victim for rows in hunt_victims.values() for victim in rows]
        if len(victims) != 1 or victims[0]["id"] != target_id or victims[0]["region"] != "Grassland":
            raise ValueError("Visual selection lacked its only expected Grassland hunting death")
        summary["visual_hunt_selection"] = {"policy": policy, "candidate_ids": [row["id"] for row in candidates],
                                            "body_scales": sorted(body_scales), "visual_at_first_shot": visual,
                                            "victim": victims[0]}
    if "combat_repeat" in report:
        episodes = [report[key] for key in ("combat_carrion", "combat_repeat")]
        ids = [str(episode["victim"]) for episode in episodes]
        victims = {row["id"]: dict(row, species=species_name)
                   for species_name, rows in hunt_victims.items() for row in rows}
        if (len(set(ids)) != 2 or set(victims) != set(ids) or sum(hunt_deaths.values()) != 2
                or {agent: paid for counts in player_damage.values() for agent, paid in counts.items()}
                != dict.fromkeys(ids, 100.)):
            raise ValueError("Repeat hunt lacked its two isolated authoritative deaths and damage totals")
        if (len({victim["region"] for victim in victims.values()}) != 1
                or victims[ids[0]]["sample_seconds"] >= victims[ids[1]]["sample_seconds"]
                or any(episode.get("release_hp") != 0 or len(episode.get("shots", ())) != 4 for episode in episodes)):
            raise ValueError("Repeat hunt did not complete two four-shot episodes in order in one region")
        summary["repeated_hunt"] = [victims[agent] for agent in ids]
    if "initial_patch_inputs" in report:
        inputs = json.dumps(report["initial_patch_inputs"], sort_keys=True, separators=(",", ":"))
        summary["initial_patch_input_hash"] = sha256(inputs.encode("utf-8")).hexdigest()
    if "fauna_persistence_enabled" in report:
        summary["fauna_persistence_enabled"] = report["fauna_persistence_enabled"]
    if "eagle_families" in report:
        summary["eagle_families"] = report["eagle_families"]
    if "wolf_food_survey" in report:
        summary["native_food_survey"] = summarize_native_food_survey(report, events)
    if "wolf_carrion_survey" in report:
        summary["native_wolf_forage"] = summarize_native_wolf_forage(report["wolf_carrion_survey"], events,
                                                                    native_wolf_bites, native_wolf_provisions)
    if "wolf_territory_layout" in report:
        summary["native_wolf_birth_requests"] = summarize_native_wolf_birth_requests(
            founders, log_path, first["completed_seconds"], last["completed_seconds"])
    if "buffalo_guard_trial" in report:
        trial = report["buffalo_guard_trial"]
        calves = {row["id"]: row for row in events["birth"] if row["species"] == "Buffalo" and row["region"] == "Grassland"}
        attempts = Counter()
        interceptions = []
        for sample in trial["samples"]:
            for agent in sample["agents"]:
                if agent["species"] == "Leopard" and agent["prey"] in calves:
                    attempts[agent["prey"]] += 1
        pattern = re.compile(r"\[Eco Fauna\]\[GuardIntercept\] Guard=(\d+) Child=(\d+) Hunter=(\d+) Species=Buffalo"
                             r" At=([\d.]+) BodyScale=([\d.]+) Damage=([\d.]+) StaminaBefore=([\d.]+) StaminaAfter=([\d.]+)")
        with log_path.open(encoding="utf-8-sig") as log:
            for line in log:
                if not (hit := pattern.search(line)):
                    continue
                guard, child, hunter, at, scale, damage, before, after = hit.groups()
                calf = calves.get(child)
                if (not calf or guard not in (calf["parent_a"], calf["parent_b"]) or float(at) < calf["born"]
                        or abs(float(before) - float(after) - .15) > .0002 or float(damage) <= 0.):
                    raise ValueError("Buffalo guard contact did not match a live birth, a parent and the stamina cost")
                interceptions.append({"guard": guard, "child": child, "hunter": hunter, "at": float(at),
                                      "body_scale": float(scale), "damage": float(damage), "stamina_spent": .15})
        summary["buffalo_guard_trial"] = {"samples": len(trial["samples"]), "natural_calves": list(calves),
                                          "leopard_target_samples": dict(attempts), "interceptions": interceptions}
    if managed_food_patches:
        summary["managed_stock_intervals"] = managed_stock_intervals(report, managed_payments)
    if land_access_receipts:
        summary["land_forage_access"] = summarize_land_forage_access(report, land_access_receipts, seen)
    for key, totals in habitat_access.items():
        medium, species_name, age_group = key
        target = summary.setdefault(f"{medium.lower()}_meal_access", {})
        if species_name:
            target = target.setdefault(species_name, {})
        target[age_group] = {**totals, "paid_energy": round(totals["paid_energy"], 3),
                             "agents": len(habitat_participants[key])}
    return summary, founders


def check_identity(seen, row):
    existing = seen.setdefault(row["id"], row)
    if any(existing.get(key) != row.get(key) for key in (*IMMUTABLE, *FUNCTIONAL_GENES, *SHAPE_GENES)):
        raise ValueError(f"Identity, origin or genome changed for {row['id']}")


def overview(run):
    """Keep the evidence needed to triage all species together."""
    fields = ("initial_backends", "initial_alive", "final_alive", "living_by_generation",
              "first_absent_sample_seconds", "deaths_by_cause", "death_causes_by_generation", "births_by_generation",
              "births_with_both_parents_linked", "mature_offspring_by_generation",
              "mature_offspring_peak_sampled_energy", "sampled_descendant_mating_opportunities",
              "habitat_paid_energy_by_generation", "habitat_paid_energy_without_lineage")
    compact = {key: run[key] for key in ("last_seconds", "events", "initial_patch_input_hash", "functional_traits",
                                         "fauna_persistence_enabled", "visual_hunt_selection", "repeated_hunt",
                                         "land_forage_access", "native_food_survey", "native_wolf_forage",
                                         "native_wolf_birth_requests", "buffalo_guard_trial") if key in run}
    compact["population_receipts_match"] = (
        not run["alive_missing_from_receipts"] and not run["receipts_missing_from_alive"]
        and not any(row["unexplained"] for species in run["regional_balances"].values() for row in species.values())
    )
    compact["species"] = {
        name: {key: row[key] for key in fields} | {
            "habitat_paid_energy": round(sum(row["habitat_paid_energy_by_site"].values()), 3),
            "timed_carrion_paid_energy": round(row["timed_carrion_paid_energy"], 3),
        } | ({"functional_adult_ranges": row["functional_adult_ranges"]} if "functional_adult_ranges" in row else {})
        for name, row in run["species"].items()
    }
    return compact


def compare_forage_layouts(reference_path, trial_path, reference_log, trial_log):
    from check_island_population_receipts import check_log, compare_population_samples
    from summarize_fauna_runtime import compare_island_baseline

    reports = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    layouts = []
    for report in reports:
        if report["samples"][-1]["completed_clock"]["authority_seconds"] < report["population_target_seconds"]:
            raise ValueError("Forage access comparison requires completed population reports")
        patches = report["initial_patch_inputs"]["patches"]
        layout = {}
        for site, change in report.get("land_forage_access", {}).items():
            points = patches[site]["forage_access_points"]
            if (not points or [point[:2] for point in points] != [point[:2] for point in change["points_cm"]]
                    or change.get("authority_points_cm", points) != points):
                raise ValueError(f"Forage access did not match the staged and authority points for {site}")
            layout[site] = points
        layouts.append(layout)
    if layouts[0] == layouts[1]:
        raise ValueError("Expected different forage access layouts")
    declared_sites = layouts[0].keys() | layouts[1].keys()
    normalized = []
    for report, layout in zip(reports, layouts):
        inputs = deepcopy(report["initial_patch_inputs"])
        for site in declared_sites:
            patch = inputs["patches"][site]
            if patch["forage_access_points"] != layout.get(site, []):
                raise ValueError(f"Unexpected forage access points for {site}")
            patch["forage_access_points"] = []
        normalized.append(dict(report, initial_patch_inputs=inputs))
    initial = compare_island_baseline(*normalized)
    if not initial["matches"]:
        raise ValueError(f"Forage comparison changed more than the declared access points: {initial}")
    rules = reports[0]["trait_evidence"]["cohorts"][0]
    compared_rules = reports[1]["trait_evidence"]["cohorts"][0]
    if (any(rules[key] != compared_rules.get(key) for key in rules if isinstance(rules[key], bool))
            or reports[0]["fauna_persistence_enabled"] != reports[1]["fauna_persistence_enabled"]):
        raise ValueError("Forage access layout requires the same active behavior and persistence rules")
    return {"matched_other_initial_inputs": initial, "reference_points_cm": layouts[0],
            "comparison_points_cm": layouts[1], "population_samples": compare_population_samples(*reports),
            "food_ledgers": {"reference": check_log(reference_log), "comparison": check_log(trial_log)}}


def compare_forage_guild(reference_path, trial_path, reference_log, trial_log, reference_run, trial_run):
    from check_island_population_receipts import check_log
    from summarize_fauna_runtime import compare_island_baseline, summarize

    reference, trial = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    change = trial["forage_guild_trial"]
    site = change["patch"]
    original_guild = reference["initial_patch_inputs"]["patches"][site]["plant_guild"]
    normalized_trial = deepcopy(trial["initial_patch_inputs"])
    trial_site = normalized_trial["patches"][site]
    if (reference.get("forage_guild_trial") or site != "IslandForageWestMeadow" or trial_site["submerged"]
            or original_guild.split(".")[-1].split(":")[0] != change["from"]
            or trial_site["plant_guild"].split(".")[-1].split(":")[0] != change["to"]
            or change["to"] != "WET_MEADOW"):
        raise ValueError("The guild comparison requires its declared WestMeadow grass-to-wet-meadow change")
    trial_site["plant_guild"] = original_guild
    initial = compare_island_baseline(reference, dict(trial, initial_patch_inputs=normalized_trial))
    if not initial["matches"]:
        raise ValueError(f"Forage guild comparison changed other starting inputs: {initial}")
    first = reference["trait_evidence"]["cohorts"][0]
    rules = {key: value for key, value in first.items() if isinstance(value, bool)}
    results = {}
    for label, report, run, path, log in zip(("reference", "trial"), (reference, trial), (reference_run, trial_run),
                                              (reference_path, trial_path), (reference_log, trial_log), strict=True):
        cohorts = report["trait_evidence"]["cohorts"]
        if (any(any(row.get(key) != value for key, value in rules.items()) for row in cohorts)
                or report["fauna_persistence_enabled"] != reference["fauna_persistence_enabled"]):
            raise ValueError("Forage guild comparison changed the behavior rules")
        if not overview(run)["population_receipts_match"] or run["last_seconds"] < report["population_target_seconds"]:
            raise ValueError(f"Incomplete population receipts for guild {label}")
        results[label] = {
            "birth_requests": summarize_rule_breeding(log, cohorts),
            "patch_payments_by_species": {species: {patch: round(amount, 3) for patch, amount in sorted(row["habitat_paid_energy_by_site"].items())}
                                          for species, row in run["species"].items() if row["habitat_paid_energy_by_site"]},
            "regional_food": check_log(log),
            "carcass_payments": summarize(path, log, audit_carcasses=True)["carcass_balance_audit"]["payments"],
        }
    return {"guild_change": change, "matched_other_initial_inputs": initial, "results": results}


def audit_fixed_water_stock(log_path, site, expected_rate, *, after_marker=None, opening_stock=None,
                            replay_from=None, capacity=None, closing_stock=None):
    previous = opening_stock
    clock_site = replay_from or site
    refills = payments = 0
    growth = paid_total = max_residual = 0.
    with log_path.open(encoding="utf-8-sig") as log:
        for line in log:
            if after_marker is not None:
                if after_marker in line:
                    after_marker = None
                continue
            refill = WATER_REFILL.search(line)
            meal = HABITAT_MEAL.search(line)
            if refill and refill[1] == clock_site:
                delta, rain, before, after, row_capacity, rate = map(float, refill.groups()[1:])
                if not replay_from and abs(rate - expected_rate) > 1e-6:
                    raise ValueError(f"Unexpected regeneration at {site} in {log_path}")
                if replay_from:
                    before, row_capacity, rate = previous, capacity, expected_rate
                expected = min(row_capacity, before + delta * rate * (.75 + .5 * min(1., max(0., rain))))
                if replay_from:
                    after = expected
                refills += 1
                growth += after - before
            elif meal and meal[1] == "Aquatic" and meal[2] == site and meal[8] == "Paid":
                before, paid, after = map(float, meal.groups()[9:12])
                expected = before - paid
                payments += 1
                paid_total += paid
            else:
                continue
            residual = max(abs(expected - after), abs(previous - before) if previous is not None else 0.)
            if residual > 2e-6:
                raise ValueError(f"Broken aquatic stock ledger for {site} in {log_path}: {line.rstrip()}")
            max_residual = max(max_residual, residual)
            previous = after
    if after_marker is not None or not refills or not payments:
        raise ValueError(f"Missing growth or actual food payments for {site} in {log_path}")
    if closing_stock is not None and abs(previous - closing_stock) > 2e-6:
        raise ValueError(f"Stock receipts did not reach the authority's final stock at {site} in {log_path}")
    return {"refills": refills, "payments": payments, "regrown": round(growth, 6), "paid": round(paid_total, 6),
            "max_residual": max_residual}


def compare_eagle_family_layouts(reference_path, trial_path):
    reports = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    by_mode = {report["eagle_families"]["mode"]: report for report in reports}
    if len(by_mode) != 2 or "Landscape" not in by_mode:
        return None
    landscape = by_mode["Landscape"]
    trial = next(report for mode, report in by_mode.items() if mode != "Landscape")
    first, second = (report["eagle_families"] for report in (landscape, trial))
    fields = ("family_starts_cm", "nests_cm", "regional_limit", "founders")
    if any(first[field] != second[field] for field in fields):
        raise ValueError("The eagle food comparison changed the founders, their sites, or the regional limit")
    source, reserve = (report["initial_patch_inputs"] for report in (landscape, trial))
    food = second.get("food", [])
    added_food = [stock["patch"] for stock in food]
    restored_inputs = dict(reserve, patches={key: value for key, value in reserve["patches"].items()
                                            if key not in added_food},
                           patch_order=[key for key in reserve["patch_order"] if key not in added_food])
    if restored_inputs != source or reserve["patch_order"] != [*source["patch_order"], *added_food]:
        raise ValueError("The eagle food comparison changed something beyond the added feeding reserves")
    starts = [{str(row["stable_id"]): row for row in report["samples"][0]["agents"]} for report in (landscape, trial)]
    relocations = {row["id"]: row for row in second.get("prey_placements", ())}
    fields = ("species", "region", "position", "hp", "energy", "body_scale")
    if any({key: row.get(field) for key, row in starts[0].items() if key not in relocations}
           != {key: row.get(field) for key, row in starts[1].items() if key not in relocations} for field in fields):
        raise ValueError("The eagle food comparison changed the starting authority samples")
    for key, relocation in relocations.items():
        before, after = (sample[key] for sample in starts)
        if (before["species"] != "Jackrabbit" or after["species"] != "Jackrabbit"
                or before["region"] != relocation["from_region"] or after["region"] != relocation["to_region"]):
            raise ValueError(f"The prey relocation did not match the starting regions for {key}")
    return {"same_founder_and_nest_placement": True, "same_existing_habitat": True,
            "added_food": food, "prey_relocations": list(relocations.values())}


def compare_aquatic_regrowth(reference_path, trial_path, reference_log, trial_log, reference_run, trial_run):
    from check_island_population_receipts import check_log, compare_population_samples
    from summarize_fauna_runtime import compare_island_baseline

    reference, trial = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    local_supply = trial.get("aquatic_neighborhood_supply")
    changes = local_supply or trial.get("aquatic_forage_regrowth", {})
    if local_supply:
        if (len(changes) != 4 or reference.get("aquatic_neighborhood_supply")
                or not reference.get("aquatic_neighborhoods")
                or reference["aquatic_neighborhoods"] != trial.get("aquatic_neighborhoods")
                or reference.get("aquatic_forage_regrowth") != trial.get("aquatic_forage_regrowth")
                or reference.get("aquatic_species_limits") != trial.get("aquatic_species_limits")
                or reference.get("carp_capacity_change") or trial.get("carp_capacity_change")
                or reference.get("small_fish_capacity_change") or trial.get("small_fish_capacity_change")):
            raise ValueError("The local supply comparison requires the same layout, background rates, and fish limits")
    elif reference.get("aquatic_forage_regrowth") or trial.get("carp_capacity_change") or len(changes) != 5:
        raise ValueError("Expected a saved-island reference and five changed aquatic forage rates")
    ref_inputs = reference["initial_patch_inputs"]["patches"]
    normalized = deepcopy(trial["initial_patch_inputs"])
    for site, rates in changes.items():
        before, after = ref_inputs[site], normalized["patches"][site]
        declared = rates["from"] + rates["additional_rate"] if local_supply else 3. * rates["from"]
        if (not before["submerged"] or before["region_id"] != "LowerRiver"
                or abs(before["regrowth_per_second"] - rates["from"]) > 1e-6
                or abs(after["regrowth_per_second"] - rates["to"]) > 1e-6
                or abs(rates["to"] - declared) > 1e-6):
            raise ValueError(f"Unexpected aquatic forage rate or site for {site}")
        after["regrowth_per_second"] = before["regrowth_per_second"]
    initial = compare_island_baseline(reference, dict(trial, initial_patch_inputs=normalized))
    if not initial["matches"]:
        raise ValueError(f"More than the aquatic forage rates changed: {initial}")
    rules, trial_rules = (report["trait_evidence"]["cohorts"][0] for report in (reference, trial))
    if (any(value != trial_rules.get(key) for key, value in rules.items() if isinstance(value, bool))
            or reference["fauna_persistence_enabled"] != trial["fauna_persistence_enabled"]):
        raise ValueError("Aquatic regrowth comparison requires matched behavior rules")
    for report, run in zip((reference, trial), (reference_run, trial_run)):
        if not overview(run)["population_receipts_match"] or run["last_seconds"] < report["population_target_seconds"]:
            raise ValueError("Aquatic regrowth comparison requires completed regional life-cycle receipts")
    site = trial["forage_stock_audit_patch"]
    if reference["forage_stock_audit_patch"] != site or site not in changes:
        raise ValueError("Audit the same modified water stock in both runs")
    return {"matched_other_initial_inputs": initial, "declared_rates": changes,
            "population_samples": compare_population_samples(reference, trial),
            "regional_food": {"reference": check_log(reference_log), "trial": check_log(trial_log)},
            "water_food": {label: audit_fixed_water_stock(log, site, changes[site][key])
                           for label, log, key in (("reference", reference_log, "from"), ("trial", trial_log, "to"))}}


def compare_small_fish_capacity(reference_path, trial_path, reference_log, trial_log, reference_run, trial_run,
                                *, breeding_order=False, encounter=False):
    from check_island_population_receipts import check_log
    from summarize_fauna_runtime import compare_island_baseline, summarize

    reference, trial = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    initial = compare_island_baseline(reference, trial)
    placement = trial.get("small_fish_encounter")
    if encounter:
        if not placement or reference.get("small_fish_encounter") or initial["differences"] != ["initial_position"]:
            raise ValueError("The encounter comparison changes only its declared starting position")
        founder = str(placement["founder"])
        starts = [next(row for row in report["samples"][0]["agents"] if str(row["stable_id"]) == founder)
                  for report in (reference, trial)]
        positions = (POSITION.fullmatch(value).groups() for value in (placement["from"], placement["to"]))
        # The placement receipt precedes the first sample by one authority tick.
        offsets = [dist(tuple(map(float, raw)), tuple(map(float, POSITION.fullmatch(row["position"]).groups())))
                   for row, raw in zip(starts, positions, strict=True)]
        if ([str(agent) for agent in initial["agents_with_different_initial_position"]] != [founder]
                or any(row["species"] != "UnidentifiedFish" for row in starts)
                or max(offsets) > .2
                or not placement["wet_approach_samples"] or not all(row["wet"] for row in placement["wet_approach_samples"])):
            raise ValueError("The founder placement did not match its initial snapshots and surveyed wet approach")
        initial["placement_to_sample_offset_cm"] = offsets
    elif not initial["matches"] or placement or reference.get("small_fish_encounter"):
        raise ValueError("The capacity comparison requires matched initial conditions")
    fields = ("aquatic_forage_regrowth", "aquatic_neighborhoods", "aquatic_neighborhood_supply", "aquatic_species_limits",
              "fauna_persistence_enabled", "population_target_seconds", "forage_stock_audit_patch")
    if (not reference.get("aquatic_neighborhood_supply")
            or any(reference[field] != trial[field] for field in fields)
            or any(report.get("carp_capacity_change") for report in (reference, trial))):
        raise ValueError("The small-fish capacity comparison requires the same local supply, initial limits and duration")
    reference_change = reference.get("small_fish_capacity_change")
    change = trial["small_fish_capacity_change"]
    if (breeding_order or encounter) and reference_change != change:
        raise ValueError("The breeding order or encounter comparison requires an identical capacity change")
    if not (breeding_order or encounter) and reference_change:
        raise ValueError("The small-fish capacity reference must retain its original limit")
    species = "UnidentifiedFish"
    original_limit = reference["aquatic_species_limits"][species]
    if (change["from"] != original_limit or change["residents"] != original_limit
            or change["to"] - original_limit not in (2, 4)
            or not 0 < change["at"] < trial["population_target_seconds"]):
        raise ValueError(f"Invalid capacity change for a full LowerRiver population: {change}")

    rules, trial_rules = (report["trait_evidence"]["cohorts"][0] for report in (reference, trial))
    opportunity = "fauna_breeding_opportunity"
    if (rules.get(opportunity, False) != encounter or trial_rules.get(opportunity, False) != (breeding_order or encounter)
            or any(value != trial_rules.get(key) for key, value in rules.items() if isinstance(value, bool) and key != opportunity)):
        raise ValueError("Small-fish capacity comparison requires matched behavior rules")
    results = {}
    for label, report, run, path, log in zip(("reference", "trial"), (reference, trial), (reference_run, trial_run),
                                              (reference_path, trial_path), (reference_log, trial_log)):
        if not overview(run)["population_receipts_match"] or run["last_seconds"] < report["population_target_seconds"]:
            raise ValueError(f"Incomplete {label} population receipts")
        site = report["forage_stock_audit_patch"]
        rate = report["initial_patch_inputs"]["patches"][site]["regrowth_per_second"]
        carcasses = summarize(path, log, audit_carcasses=True)["carcass_balance_audit"]
        for site_name in report["aquatic_neighborhood_supply"]:
            intervals = run["managed_stock_intervals"][site_name]
            if not intervals or not all(row["consistent"] for row in intervals):
                raise ValueError(f"Managed water stock did not balance at {site_name} in {label}")
        results[label] = {"regional_food": check_log(log), "water_food": audit_fixed_water_stock(log, site, rate),
                          "carcass_payments": carcasses["payments"]}
    return {"matched_initial_inputs": initial, "small_fish_capacity_change": change, "breeding_order_changed": breeding_order,
            "ledgers": results, **({"founder_placement": placement} if encounter else {})}


def compare_rule_breeding_order(reference_path, trial_path, reference_log, trial_log, reference_run, trial_run):
    from check_island_population_receipts import check_log
    from summarize_fauna_runtime import compare_island_baseline, summarize

    reference, trial = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    initial = compare_island_baseline(reference, trial)
    for field in ("land_forage_regrowth", "land_forage_access", "fauna_persistence_enabled"):
        if reference.get(field) != trial.get(field):
            raise ValueError(f"Rule breeding order comparison changed {field}")
    rule = "fauna_breeding_opportunity"
    first = reference["trait_evidence"]["cohorts"][0]
    shared_rules = {key: value for key, value in first.items() if isinstance(value, bool) and key != rule}
    results = {}
    for enabled, report, run, path, log in zip((False, True), (reference, trial), (reference_run, trial_run),
                                              (reference_path, trial_path), (reference_log, trial_log), strict=True):
        cohorts = report["trait_evidence"]["cohorts"]
        if any(row.get(rule, False) != enabled or any(row.get(key) != value for key, value in shared_rules.items())
               for row in cohorts):
            raise ValueError("Rule breeding order comparison changed other behavior flags or did not keep the requested rule")
        if not overview(run)["population_receipts_match"] or run["last_seconds"] < report["population_target_seconds"]:
            raise ValueError(f"Incomplete population receipts for breeding order {enabled}")
        results["on" if enabled else "off"] = {
            "birth_requests": summarize_rule_breeding(log, cohorts),
            "regional_food": check_log(log),
            "carcass_payments": summarize(path, log, audit_carcasses=True)["carcass_balance_audit"]["payments"],
        }
    return {"initial_input_comparison": initial, "results": results}


def compare_trait_climate(reference_path, trial_path, reference_log, trial_log, reference_run, trial_run):
    from check_island_population_receipts import check_log
    from summarize_fauna_runtime import compare_island_baseline, summarize

    reference, trial = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    initial = compare_island_baseline(reference, trial)
    if not initial["matches"]:
        raise ValueError(f"Climate trial changed the initial island state: {initial}")
    first = reference["trait_evidence"]["cohorts"][0]
    rules = {key: value for key, value in first.items() if isinstance(value, bool)}
    regions = {"Grassland", "Highland", "Riverbank", "LowerRiver"}
    result = {"matched_initial_inputs": initial, "conditions": {}}
    for mode, rainfall, report, run, path, log in zip(("Dry", "Rain"), (0., .75), (reference, trial),
                                                     (reference_run, trial_run), (reference_path, trial_path),
                                                     (reference_log, trial_log), strict=True):
        condition = report["trait_climate"]
        cohorts = report["trait_evidence"]["cohorts"]
        if not rules.get("functional_traits") or any(any(row.get(key) != value for key, value in rules.items()) for row in cohorts):
            raise ValueError(f"Functional traits or another behavior rule differed in {mode}")
        samples = condition["samples"]
        if (condition["mode"] != mode or not samples or samples[-1]["completed_seconds"] < report["population_target_seconds"]
                or any(row["rainfall"].keys() != regions or any(abs(value - rainfall) > .001 for value in row["rainfall"].values())
                       for row in samples)):
            raise ValueError(f"The completed {mode} run did not use its declared regional climate")
        if len(run["species"]) != 16 or not overview(run)["population_receipts_match"]:
            raise ValueError(f"The {mode} trial lacks a complete 16-species life-cycle ledger")
        result["conditions"][mode] = {
            "rainfall": rainfall, "regions": sorted(regions), "from_seconds": samples[0]["completed_seconds"],
            "to_seconds": samples[-1]["completed_seconds"], "regional_food": check_log(log),
            "carcass_payments": summarize(path, log, audit_carcasses=True)["carcass_balance_audit"]["payments"],
            "offspring_by_region_and_generation": {species: row["offspring_by_natal_region_and_generation"]
                                                   for species, row in run["species"].items()},
        }
    return result


def compare_wolf_kin(reference_path, trial_path, reference_log, trial_log, reference_run, trial_run):
    from check_island_population_receipts import check_log
    from summarize_fauna_runtime import summarize

    reference, trial = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path))
    fields = ("initial_patch_inputs", "initial_backends", "initial_routes", "authored_capacities", "population_target_seconds",
              "fauna_persistence_enabled")
    if (reference["wolf_kin_layout"] != "Separated" or trial["wolf_kin_layout"] != "Shared"
            or any(reference[field] != trial[field] for field in fields)
            or reference["samples"][0]["population"] != trial["samples"][0]["population"]):
        raise ValueError("Wolf territory comparison requires matched species totals, food, travel and backends")
    baseline_rules, trial_rules = (report["trait_evidence"]["cohorts"][0] for report in (reference, trial))
    if any(value != trial_rules.get(key) for key, value in baseline_rules.items() if isinstance(value, bool)):
        raise ValueError("Wolf territory comparison requires identical ecological rules")

    queued = re.compile(r"\[EcoLife\]\[BirthQueued\] Region=(\w+) Predator=1 Parents=(\d+),(\d+) Due=([\d.]+)")
    fed = re.compile(r"\[Scavenge\] Eater=(\d+) Species=Wolf Carcass=(\d+) Amount=([\d.]+)")
    results = {}
    for label, report, run, path, log in zip(("separated", "shared"), (reference, trial), (reference_run, trial_run),
                                              (reference_path, trial_path), (reference_log, trial_log), strict=True):
        if report["errors"] or not overview(run)["population_receipts_match"] or run["last_seconds"] < report["population_target_seconds"]:
            raise ValueError(f"Incomplete territory evidence for {label}")
        wolves = run["species"]["Wolf"]
        offspring = {row["id"]: row for row in wolves["natural_offspring"]}
        generations = {row["id"]: row["generation"] for row in report["trait_evidence"]["cohorts"][0]["agents"]
                       if row["species"] == "Wolf"}
        generations.update({agent: row["generation"] for agent, row in offspring.items()})
        proposals = []
        paid = Counter()
        grassland_deer = Counter()
        for line in log.read_text(encoding="utf-8-sig", errors="replace").splitlines():
            if (reservation := queued.search(line)):
                region, first, second, due = reservation.groups()
                proposals.append({"region": region, "parents": [first, second], "due": float(due),
                                  "parent_generations": [generations[first], generations[second]]})
            if (meal := fed.search(line)):
                paid[meal[1]] += float(meal[3])
            if "[EcoTrait] " in line:
                event = json.loads(line.split("[EcoTrait] ", 1)[1])
                if event["species"] == "Herbivore" and event["region"] == "Grassland":
                    kind = event["event"]
                    if kind == "death":
                        kind = DEATH_CAUSES[event["death_cause"]]
                    grassland_deer[kind] += 1
        results[label] = {"layout": report["wolf_territory_layout"], "regional_food": check_log(log),
                          "carcass_payments": summarize(path, log, audit_carcasses=True)["carcass_balance_audit"]["payments"],
                          "queued_pairs": proposals, "offspring_carrion_energy": {agent: paid[agent] for agent in offspring},
                          "grassland_deer_events": grassland_deer,
                          "wolf_offspring": list(offspring.values()), "wolf_mate_samples": wolves["sampled_descendant_mating_opportunities"],
                          "final_regional_population": report["samples"][-1]["regional_population"]}
    return results


def compare_wolf_observer(reference_path, trial_path, reference_log, trial_log, reference, trial):
    from check_island_population_receipts import check_log
    from summarize_fauna_runtime import summarize

    reports = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    hold, leave = (report["wolf_observer"] for report in reports)
    world_fields = ("initial_patch_inputs", "initial_backends", "initial_routes", "authored_capacities", "wolf_prey_mix",
                    "wolf_territory_layout", "wolf_birth_after_separation", "population_target_seconds", "fauna_persistence_enabled")
    initial = [(tuple(report[field] for field in world_fields), report["samples"][0]["population"]) for report in reports]
    if initial[0] != initial[1] or any(hold[key] != leave[key] for key in ("subject", "requested_at")):
        raise ValueError("Wolf observer comparison requires equal starting populations, food and encounter settings")
    if (hold["mode"], leave["mode"]) != ("Hold", "Leave"):
        raise ValueError("Pass the stationary player report before the departing player report")
    flags = [{key: value for key, value in report["trait_evidence"]["cohorts"][0].items() if isinstance(value, bool)}
             for report in reports]
    if flags[0] != flags[1]:
        raise ValueError("Wolf observer comparison requires identical ecology rules")

    def prior_samples(report, observer):
        return [(row["completed_clock"]["authority_seconds"], row["regional_population"], row["stocks"],
                 [(agent["stable_id"], agent["position"], agent["energy"])
                  for agent in row["agents"] if agent["species"] == "Wolf" and agent["region"] == "Grassland"])
                for row in report["samples"] if row["completed_clock"]["authority_seconds"] < observer["intervention_at"]]

    hold_trace, leave_trace = (prior_samples(report, observer) for report, observer in zip(reports, (hold, leave), strict=True))
    first_difference = next(([left[0], right[0]] for left, right in zip(hold_trace, leave_trace) if left != right), None)
    matching_prefix = first_difference is None and len(hold_trace) == len(leave_trace)
    results = {}
    for observer, report, run, path, log in zip((hold, leave), reports, (reference, trial),
                                                (reference_path, trial_path), (reference_log, trial_log), strict=True):
        if report["errors"] or not overview(run)["population_receipts_match"] or run["last_seconds"] < report["population_target_seconds"]:
            raise ValueError(f"Incomplete wolf observer evidence for {observer['mode']}")
        start = observer["intervention_at"]
        together = [row for row in observer["samples"] if row["at"] < start]
        apart = [row for row in observer["samples"] if row["at"] >= start]
        if not together or not apart or apart[-1]["at"] < start + 34.:
            raise ValueError(f"Incomplete encounter window for {observer['mode']}")
        shift = dist(together[-1]["player_position_cm"][:2], apart[0]["player_position_cm"][:2])
        expected_shift = 0. if observer["mode"] == "Hold" else 4200.
        if abs(shift - expected_shift) >= 5.:
            raise ValueError(f"Unexpected player displacement for {observer['mode']}: {shift:.2f} cm")
        subject = observer["subject"]
        requests = [row for row in run["native_wolf_birth_requests"] if subject in row["parents"]]
        offspring = [row for row in run["species"]["Wolf"]["natural_offspring"] if subject in (row["parent_a"], row["parent_b"])]
        results[observer["mode"].lower()] = {
            "intervention_at": start, "player_displacement_cm": shift, "first_sample": together[0],
            "responses_after_intervention": Counter(row["response"] for row in apart),
            "last_player_evidence": max(row["last_evidence"] for row in apart),
            "peak_nutrition": max(row["forage"]["nutrition"] for row in apart),
            "carcass_selected_samples": sum(row["forage"]["carrion_target"] != "0" for row in apart),
            "wolf_forage": run["native_wolf_forage"]["wolves"][subject], "birth_requests": requests, "offspring": offspring,
            "regional_food": check_log(log), "carcass_payments": summarize(path, log, audit_carcasses=True)["carcass_balance_audit"]["payments"],
        }
    return {"matching_population_food_and_wolf_samples_before_intervention": matching_prefix,
            "first_divergent_sample_seconds": first_difference, **results}


def compare_hunt_frequency(reference_path, trial_path, reference_log, trial_log, reference, trial):
    from check_island_population_receipts import check_log
    from summarize_fauna_runtime import compare_island_baseline, summarize

    reports = [json.loads(path.read_text(encoding="utf-8-sig")) for path in (reference_path, trial_path)]
    initial = compare_island_baseline(*reports)
    if not initial["matches"] or "combat_repeat" in reports[0] or "combat_repeat" not in reports[1]:
        raise ValueError(f"Expected one and two hunts from the same initial conditions: {initial}")
    hunt_receipt = re.compile(r"\[(?:Eco Fauna|EcoCombat)\]\[(Carcass|CarcassClosed|DeathCommitted)\] Id=(\d+)\b")
    paired = []
    for report, run, report_path, log_path in zip(reports, (reference, trial), (reference_path, trial_path), (reference_log, trial_log)):
        if not overview(run)["population_receipts_match"] or run["last_seconds"] < report["population_target_seconds"]:
            raise ValueError("Hunt frequency requires complete population and lifecycle receipts")
        episodes = [report["combat_carrion"]]
        if "combat_repeat" in report:
            episodes.append(report["combat_repeat"])
        targets = [str(episode["victim"]) for episode in episodes]
        victims = {event["id"]: dict(event, species=species_name)
                   for species_name, row in run["species"].items() for event in row["player_hunt_victims"]}
        damage = {agent: amount for row in run["species"].values() for agent, amount in row["player_damage_by_target"].items()}
        if set(targets) != victims.keys() or damage != dict.fromkeys(targets, 100.):
            raise ValueError("Unexpected player damage or missing hunt death in the frequency comparison")
        resolved = []
        for episode, target in zip(episodes, targets):
            hits = [hit for hit in episode["damage"] if ".COMMITTED:" in hit["result"] and hit["applied"] > 0.]
            if episode["release_hp"] != 0 or len(hits) != 4 or any(hit["target"] != target for hit in hits):
                raise ValueError(f"Incomplete four-shot hunt for {target}")
            resolved.append({"start": episode["start_game_seconds"], "victim": victims[target],
                             "shots": [(hit["applied"], hit["hp"], hit.get("attacker_position_cm")) for hit in hits],
                             "witnesses": episode.get("player_attack_witnesses", {})})
        carcasses = summarize(report_path, log_path, audit_carcasses=True)
        target_carcasses = {target: carcasses["carcass_use"][target] for target in targets}
        with log_path.open(encoding="utf-8-sig", errors="replace") as log:
            target_counts = Counter(receipt.groups() for line in log if (receipt := hunt_receipt.search(line))
                                    and receipt[2] in targets)
        if any(target_counts[kind, target] != 1 for target in targets for kind in ("DeathCommitted", "Carcass", "CarcassClosed")):
            raise ValueError(f"Hunt deaths and carcasses must be created and closed exactly once: {target_counts}")
        paired.append({"episodes": resolved, "target_carcasses": target_carcasses,
                       "all_carcass_balances": carcasses["carcass_balance_audit"], "regional_food": check_log(log_path)})
    single_first = paired[0]["episodes"][0]
    repeat_first, repeat_second = paired[1]["episodes"]
    if (single_first["start"] != repeat_first["start"] or single_first["victim"] != repeat_first["victim"]
            or single_first["shots"] != repeat_first["shots"]):
        raise ValueError("The first hunt diverged before the additional intervention")
    intervention = repeat_second["start"]
    pre_hunt = [[(row["completed_clock"]["authority_seconds"], row["regional_population"], row["stocks"])
                 for row in report["samples"] if row["completed_clock"]["authority_seconds"] < intervention]
                for report in reports]
    species = {episode["victim"]["species"] for episode in paired[1]["episodes"]}
    return {"matched_initial_inputs": initial, "matching_population_and_stock_samples_before_repeat": pre_hunt[0] == pre_hunt[1],
            "samples_before_repeat": [len(rows) for rows in pre_hunt], "second_hunt_start": intervention,
            "reference": paired[0], "comparison": paired[1],
            "hunted_species_lineages": {name: {label: run["species"][name]["natural_offspring"]
                                               for label, run in zip(("reference", "comparison"), (reference, trial))}
                                        for name in sorted(species)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("log", type=Path)
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("REPORT", "LOG"))
    parser.add_argument("--overview", action="store_true", help="Show a compact result for all species")
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument("--forage-access-only", action="store_true", help="Verify that only declared food access points changed")
    comparison.add_argument("--forage-guild-only", action="store_true", help="Verify unchanged stock and geometry when the WestMeadow guild changes")
    comparison.add_argument("--aquatic-regrowth", action="store_true", help="Verify matched aquatic food regrowth and stock receipts")
    comparison.add_argument("--small-fish-capacity", action="store_true", help="Verify a capacity change at matched local aquatic supply")
    comparison.add_argument("--breeding-opportunity", action="store_true", help="Compare breeding order at matched supply and capacity")
    comparison.add_argument("--rule-breeding-order", action="store_true", help="Match rule-fauna reservations and births in an Off/On comparison")
    comparison.add_argument("--trait-climate", action="store_true", help="Compare descendant traits under dry and rainy conditions")
    comparison.add_argument("--small-fish-encounter", action="store_true", help="Compare a single founder relocation at matched food and capacity")
    comparison.add_argument("--wolf-kin", action="store_true", help="Verify equal island totals across authored wolf and deer territories")
    comparison.add_argument("--wolf-observer", action="store_true", help="Compare a stationary and departing player near a Native wolf")
    comparison.add_argument("--hunt-frequency", action="store_true", help="Compare one and two tracked player hunts")
    args = parser.parse_args()
    if args.forage_access_only and not args.compare:
        parser.error("--forage-access-only requires --compare")
    if args.forage_guild_only and not args.compare:
        parser.error("--forage-guild-only requires --compare")
    if args.hunt_frequency and not args.compare:
        parser.error("--hunt-frequency requires --compare")
    if args.aquatic_regrowth and not args.compare:
        parser.error("--aquatic-regrowth requires --compare")
    if args.wolf_kin and not args.compare:
        parser.error("--wolf-kin requires --compare")
    if args.wolf_observer and not args.compare:
        parser.error("--wolf-observer requires --compare")
    if args.rule_breeding_order and not args.compare:
        parser.error("--rule-breeding-order requires --compare")
    if args.trait_climate and not args.compare:
        parser.error("--trait-climate requires --compare")
    if (args.small_fish_capacity or args.breeding_opportunity or args.small_fish_encounter) and not args.compare:
        parser.error("Small-fish experiments require --compare")
    summary, founders = read_run(args.report, args.log)
    if args.compare:
        trial, comparison_founders = read_run(*args.compare)
        gene_rows = lambda rows: {key: tuple(row.get(field) for field in (*IMMUTABLE, *FUNCTIONAL_GENES, *SHAPE_GENES)) for key, row in rows.items()}
        matched_genes = gene_rows(founders) == gene_rows(comparison_founders)
        if not matched_genes and not args.wolf_kin:
            raise ValueError("Initial stable ID, lineage or genes differ between conditions")
        reference_hash = summary.get("initial_patch_input_hash")
        trial_hash = trial.get("initial_patch_input_hash")
        reference_visual = summary.get("visual_hunt_selection")
        trial_visual = trial.get("visual_hunt_selection")
        if reference_visual and trial_visual and reference_visual["policy"] != trial_visual["policy"]:
            if (reference_hash != trial_hash or reference_visual["candidate_ids"] != trial_visual["candidate_ids"]
                    or reference_visual["body_scales"] != trial_visual["body_scales"]
                    or reference_visual["visual_at_first_shot"]["mesh"] != trial_visual["visual_at_first_shot"]["mesh"]):
                raise ValueError("The two visual-hunt conditions used different starting candidates, food inputs or meshes")
        hunt_frequency = compare_hunt_frequency(args.report, args.compare[0], args.log, args.compare[1], summary, trial) \
            if args.hunt_frequency else None
        aquatic_regrowth = compare_aquatic_regrowth(args.report, args.compare[0], args.log, args.compare[1], summary, trial) \
            if args.aquatic_regrowth else None
        if args.small_fish_capacity or args.breeding_opportunity or args.small_fish_encounter:
            small_fish_capacity = compare_small_fish_capacity(args.report, args.compare[0], args.log, args.compare[1], summary, trial,
                                                              breeding_order=args.breeding_opportunity, encounter=args.small_fish_encounter)
        else:
            small_fish_capacity = None
        eagle_family_comparison = None
        if "eagle_families" in summary and "eagle_families" in trial:
            eagle_family_comparison = compare_eagle_family_layouts(args.report, args.compare[0])
        wolf_kin = compare_wolf_kin(args.report, args.compare[0], args.log, args.compare[1], summary, trial) if args.wolf_kin else None
        wolf_observer = compare_wolf_observer(args.report, args.compare[0], args.log, args.compare[1], summary, trial) \
            if args.wolf_observer else None
        rule_breeding_order = compare_rule_breeding_order(args.report, args.compare[0], args.log, args.compare[1], summary, trial) \
            if args.rule_breeding_order else None
        forage_guild = compare_forage_guild(args.report, args.compare[0], args.log, args.compare[1], summary, trial) \
            if args.forage_guild_only else None
        trait_climate = compare_trait_climate(args.report, args.compare[0], args.log, args.compare[1], summary, trial) \
            if args.trait_climate else None
        summary = {"matched_founders": len(founders) if matched_genes else None,
                   "matched_initial_patch_inputs": reference_hash == trial_hash if reference_hash and trial_hash else None,
                   "reference": overview(summary) if args.overview else summary,
                   "comparison": overview(trial) if args.overview else trial}
        if args.forage_access_only:
            summary["forage_access_layout_comparison"] = compare_forage_layouts(args.report, args.compare[0], args.log, args.compare[1])
        if hunt_frequency:
            summary["hunt_frequency_comparison"] = hunt_frequency
        if aquatic_regrowth:
            summary["aquatic_regrowth_comparison"] = aquatic_regrowth
        if small_fish_capacity:
            summary["small_fish_capacity_comparison"] = small_fish_capacity
        if eagle_family_comparison:
            summary["eagle_family_layout_comparison"] = eagle_family_comparison
        if wolf_kin:
            summary["wolf_kin_comparison"] = wolf_kin
        if wolf_observer:
            summary["wolf_observer_comparison"] = wolf_observer
        if rule_breeding_order:
            summary["rule_breeding_order_comparison"] = rule_breeding_order
        if forage_guild:
            summary["forage_guild_comparison"] = forage_guild
        if trait_climate:
            summary["trait_climate_comparison"] = trait_climate
    elif args.overview:
        summary = overview(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

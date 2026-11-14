"""Replay the geometry gates of sampled Unreal carp and mink scenarios."""

import argparse
import json
import math
from collections import deque
from pathlib import Path


def swim_center_bounds(bottom_cm, surface_cm, clearance_cm):
    """Return the interval available to a body center in a probed water column."""
    if not math.isfinite(clearance_cm) or clearance_cm <= 0 or surface_cm - bottom_cm < 2 * clearance_cm:
        return None
    return bottom_cm + clearance_cm, surface_cm - clearance_cm


def submerged(bottom_cm, surface_cm, target_z_cm):
    return bottom_cm < target_z_cm < surface_cm


def check_carp(case):
    fry_clearance = case["fry_clearance_cm"]
    shallow = case["previous_shelf_z_cm"]
    deep = case["lowered_shelf_z_cm"]
    during = case["phases"]["drawdown"]
    for name, phase in case["phases"].items():
        bottom, surface = phase["column_cm"]
        for label, z in (("previous", shallow), ("lowered", deep)):
            expected = label == "lowered" or name != "drawdown"
            if submerged(bottom, surface, z) != expected:
                raise AssertionError(f"Carp shelf {label} at {name} did not match the water level")
    bottom, surface = during["column_cm"]
    bounds = swim_center_bounds(bottom, surface, fry_clearance)
    if bounds is None or not bounds[0] <= deep <= bounds[1]:
        raise AssertionError("Lowered shelf does not fit the sampled fry clearance")
    for sample in case["fry_position_after_surface_drop"]:
        bounds = swim_center_bounds(*sample["water_column_cm"], sample["clearance_estimate_cm"])
        inside = bounds is not None and bounds[0] <= sample["position_cm"][2] <= bounds[1]
        if inside != sample["expected_inside"]:
            raise AssertionError("Sampled fry position does not match its water column")
    if not case["observed_drawdown_payments"] or any(
        row["resource_id"] != "IslandRiverSlowShelf" or row["amount"] <= 0
        for row in case["observed_drawdown_payments"]
    ):
        raise AssertionError("Missing authority payments on the lowered shelf")
    print(f"Carp seed {case['seed']}: shelf remains submerged and fits fry after drawdown")


def check_fry_surface_recovery(case):
    # Import outside module initialization to reuse the shared swim integration.
    from island_shore_reference_world import swim_step
    from island_water_reference_world import shallow_water_retreat, water_meal_geometry

    before, after = case["fry_position_after_surface_drop"][:2]
    position = tuple(before["position_cm"])
    clearance = before["clearance_estimate_cm"]
    column = tuple(before["water_column_cm"])
    if not position[2] > column[1] or not after["world_seconds"] > before["world_seconds"]:
        raise AssertionError("Expected a surface drop followed by a later position sample")

    def current_column(probe):
        if probe != position:
            raise AssertionError("A valid column must not trigger the nearby horizontal retreat probes")
        return column

    # Zero propulsion and flow isolate the vertical bound from unrecorded substeps.
    constrained = swim_step(position, position, 0., (0., 0., 0.), column, clearance, .05)
    stayed = shallow_water_retreat(position, clearance, 0., 1., .05, current_column,
                                   lambda *_: False)
    after_bounds = swim_center_bounds(*after["water_column_cm"], after["clearance_estimate_cm"])
    if (stayed != position or constrained is None or constrained[:2] != position[:2]
            or not after_bounds or not after_bounds[0] <= after["position_cm"][2] <= constrained[2] < column[1]):
        raise AssertionError("Expected the above-surface position to use the water bound, then remain submerged")
    meal = case["observed_drawdown_payments"][0]
    if meal["time"] <= after["authority_seconds"] or meal["amount"] <= 0:
        raise AssertionError("The first recorded drawdown meal must follow the submerged sample")
    if geometry := case.get("drawdown_meal_geometry"):
        patch = geometry["shelf_center_cm"]
        shelf_column = case["phases"]["drawdown"]["column_cm"]
        selected = geometry["first_selected_in_reach"]
        if (water_meal_geometry(position, patch, column, shelf_column)
                or not water_meal_geometry(selected["position_cm"], patch, selected["water_column_cm"], shelf_column)
                or after["world_seconds"] > selected["world_seconds"]
                or selected["authority_seconds"] >= meal["time"]):
            raise AssertionError("Expected blocked above-surface geometry and a valid shelf approach before payment")
        print(f"Carp seed {case['seed']}: selected shelf was {math.dist(selected['position_cm'], patch):.1f} cm away before payment")
    print(f"Carp seed {case['seed']}: above-surface body used depth limit in replay; "
          f"Unreal recovery and first shelf meal followed in {meal['time'] - after['authority_seconds']:.1f}s by authority clock")


def check_water_meal_boundaries():
    from island_water_reference_world import water_meal_geometry

    # A low water column can pass the separate meal gate even when it cannot fit an adult swimming body.
    water = (0., 2.)
    point = (0., 0., 1.)
    if not water_meal_geometry((35., 0., 1.), point, water, water):
        raise AssertionError("The meal geometry includes the exact reach and minimum column depth")
    position = (0., 0., 1.)
    if (water_meal_geometry((35.01, 0., 1.), point, water, water)
            or water_meal_geometry((0., 0., 2.01), point, water, water)
            or water_meal_geometry(position, (0., 0., 2.), water, water)
            or water_meal_geometry(position, point, water, (0., 1.99))):
        raise AssertionError("Meal geometry must reject excessive reach, exposure, and undersized water columns")


def check_water_payment_attempts(run):
    paid_attempts = 0
    unpaid_attempts = 0
    previous = -1.
    for row in run["attempts"]:
        at = row["at"]
        gate = row["gate"]
        if at <= previous:
            raise AssertionError("Expected time-ordered authority attempts for one swimmer")
        previous = at
        if gate == "Transaction":
            if (row["agent_column"] is None or row["meal_column"] is None
                    or not submerged(*row["meal_column"], row["meal_z_cm"])
                    or not row["agent_column"][0] <= row["agent_z_cm"] <= row["agent_column"][1]
                    or not 0. <= row["distance_squared_cm"] <= 35. ** 2
                    or min(row["agent_column"][1] - row["agent_column"][0],
                           row["meal_column"][1] - row["meal_column"][0]) < 2.):
                raise AssertionError(f"Payment reached a transaction outside the water or reach bounds: {row}")
            candidate = min(row["before"], row["meal_cap"], row["headroom"])
            expected = candidate if candidate >= .2 else 0.
        else:
            expected = 0.
        if not (math.isclose(row["paid"], expected, abs_tol=2e-6)
                and math.isclose(row["before"], row["paid"] + row["after"], abs_tol=2e-6)):
            raise AssertionError(f"Unexpected water meal transaction: {row}")
        if row["paid"] > 0:
            paid_attempts += 1
        else:
            unpaid_attempts += 1
    if not paid_attempts:
        raise AssertionError("Expected an actual payment in the selected swimmer audit")
    print(f"Seed {run['seed']}: {paid_attempts} paid and {unpaid_attempts} unpaid Unreal water attempts reconciled")


def check_water_meal_control(case):
    from island_water_reference_world import water_patch_payment

    rows = case["attempts"]
    if len(rows) != 7 or [r["at"] for r in rows] != list(range(100, 107)):
        raise AssertionError("Expected seven ordered authority water-meal control steps")
    for row in rows:
        column = case["bottom_cm"], row["surface_cm"]
        paid, after = water_patch_payment(row["position_cm"], row["point_cm"], column, column,
                                         still=row["still"], clear_sight=row["clear_sight"], stock=row["before"],
                                         meal_cap=row["meal_cap"], headroom=row["headroom"])
        if not math.isclose(paid, row["paid"], abs_tol=1e-6) or not math.isclose(after, row["after"], abs_tol=1e-6):
            raise AssertionError(f"Unreal and Python water-meal control mismatch: {row}")
    if any(row["paid"] for row in rows[:-1]) or rows[-1]["paid"] != 2. or rows[-1]["after"] != 8.:
        raise AssertionError("Expected six untouched transactions and one two-unit payment")
    print("Water meal control: six Unreal rejections and one restored payment matched Python")


def check_water_stock_ledger(run):
    from island_water_reference_world import FoodPatch

    stock = run["capacity"]
    seasonal = run.get("seasonal")
    model = FoodPatch((0, 0), 10., stock, run["regrowth_per_second"], 2.8, stock, rainfall_driven=not seasonal,
                      full_growth_depth_cm=seasonal["full_growth_depth_cm"] if seasonal else 0.,
                      dry_loss_per_second=seasonal["dry_loss_per_second"] if seasonal else 0.)
    updates = payments = 0
    update_at = -1.
    used_access = set()
    by_rain = {}
    seasonal_phases = []
    exposed = False
    for row in run["events"]:
        if row["kind"] == "growth":
            if (row["at"] <= update_at or row["delta"] < 0.
                    or not math.isclose(stock, row["before"], abs_tol=.002)):
                raise AssertionError(f"Growth must follow the last shared stock: {row}")
            update_at = row["at"]
            model.stock = row["before"]
            if seasonal:
                model.height_above_bottom_cm = row["height_cm"]
                exposed = not 0. < row["height_cm"] < row["depth_cm"]
                if not seasonal_phases or exposed != seasonal_phases[-1]:
                    seasonal_phases.append(exposed)
            model.regrow(main_depth_cm=row.get("depth_cm"), elapsed=row["delta"], rainfall=row["rainfall"])
            stock = model.stock
            if row["delta"] > 0. and stock < run["capacity"] - .001:
                rate = (row["after"] - row["before"]) / row["delta"]
                by_rain.setdefault(round(row["rainfall"], 2), []).append(rate)
            tolerance = 2e-6
            updates += 1
        else:
            if (row["kind"] != "payment" or exposed or abs(row["at"] - update_at) > .00051
                    or not 0. < row["amount"] <= stock + .001):
                raise AssertionError(f"Payment must draw from the latest authority stock: {row}")
            stock -= row["amount"]
            tolerance = .001
            payments += 1
            used_access.add(row["access"])
        if not math.isclose(stock, row["after"], abs_tol=tolerance):
            raise AssertionError(f"Water growth or payment ledger mismatch: {row}")
        # Consume the recorded balance to prevent quantization drift from 3-decimal receipts.
        stock = row["after"]
    if updates < 100 or payments < 2 or used_access != {0, 1}:
        raise AssertionError("Expected an authority trace with repeated growth and payments at both access points")
    print(f"Seed {run['seed']}: shared water ledger matched {updates} growth updates and {payments} payments")
    if seasonal:
        if seasonal_phases != [False, True, False]:
            raise AssertionError("Expected submerged, exposed, and restored seasonal stock phases")
        closed, reopened = (change["authority_seconds"] for change in seasonal["water_changes"])
        if not any(row["kind"] == "payment" and row["at"] > reopened for row in run["events"]):
            raise AssertionError("Expected an actual payment after seasonal water was restored")
        print(f"Seed {run['seed']}: seasonal shelf exposed after {closed:g}s and paid again after {reopened:g}s")
    if "rain_changes" in run:
        changes = run["rain_changes"]
        growth_rows = [row for row in run["events"] if row["kind"] == "growth"]
        observed = [round(row["rainfall"], 2) for i, row in enumerate(growth_rows)
                    if i == 0 or abs(row["rainfall"] - growth_rows[i - 1]["rainfall"]) > .01]
        if ([round(change["rainfall"], 2) for change in changes] != [.35, .85, .35]
                or observed != [.35, .85, .35] or set(by_rain) != {.35, .85}):
            raise AssertionError("Expected the actual river stock update to see the full rain pulse")
        dry, wet = (sum(by_rain[rain]) / len(by_rain[rain]) for rain in (.35, .85))
        if not math.isclose(wet - dry, run["regrowth_per_second"] * .25, abs_tol=2e-5):
            raise AssertionError("Uncapped measured growth did not follow the changed authority rainfall")
        print(f"Seed {run['seed']}: uncapped stock growth {dry:.5f}/s before/after and {wet:.5f}/s during the pulse")


def check_mink(case):
    normal = case["normal_surface_cm"]
    raised = case["raised_surface_cm"]
    previous = case["previous_bank_z_cm"]
    ramp = case["saved_ramp_shore_z_cm"]
    if not normal < previous < raised < ramp:
        raise AssertionError("Expected the high water to cover the previous bank and leave the saved ramp shore dry")
    events = case["observed_first_roundtrip"]
    expected = ["SwimEnter", "HabitatPatchEaten", "SwimExit", "SwimDryBankReached"]
    if [reason for _, reason in events] != expected or any(a[0] >= b[0] for a, b in zip(events, events[1:])):
        raise AssertionError("Mink round trip did not contain ordered authority receipts")
    if not case["raise_world_seconds"] <= case["dry_ground_arrival_world_seconds"] < case["restore_world_seconds"]:
        raise AssertionError("Mink arrival occurred after the raised-water trial")
    print(f"Mink seed {case['seed']}: previous bank flooded, saved ramp shore dry, round trip recorded")


GRID_MOVES = {"west": (-1, 0), "east": (1, 0), "south": (0, -1), "north": (0, 1)}


def water_grid_predecessors(start, passable, goal=None):
    if start not in passable:
        return {}
    predecessors = {start: None}
    queue = deque([start])
    while queue:
        cell = queue.popleft()
        if cell == goal:
            break
        x, y = cell
        for action, (dx, dy) in GRID_MOVES.items():
            neighbor = x + dx, y + dy
            if neighbor in passable and neighbor not in predecessors:
                predecessors[neighbor] = cell, action
                queue.append(neighbor)
    return predecessors


def connected_cells(start, passable):
    return set(water_grid_predecessors(start, passable))


def check_grid(run):
    checks = 0
    surveys = run["surveys"]
    if surveys.keys() != {"early_dry", "late_high", "receding"}:
        raise AssertionError("Expected low, high and receding water surveys")
    for phase, survey in surveys.items():
        grid = survey["depth_grid"]
        x0, y0 = grid["origin_cm"]
        spacing = survey["grid_cm"]
        depths = {(x, y): depth for x, y, depth in grid["samples"]}
        if len(depths) != len(grid["samples"]) or len(depths) != survey["wet_cells"]:
            raise AssertionError(f"Missing or duplicate water cells at {phase}")
        site_cells = {name: (round((x - x0) / spacing), round((y - y0) / spacing))
                      for name, (x, y, _) in grid["sites_cm"].items()}
        for species, sizes in survey["species"].items():
            for size, profile in sizes.items():
                clearance = profile["clearance_cm"]
                passable = {cell for cell, depth in depths.items() if depth >= 2 * clearance}
                sites = {}
                for name, cell in site_cells.items():
                    column = survey["site_water_cm"][name]
                    if cell in passable and column is not None and swim_center_bounds(*column, clearance) is not None:
                        sites[name] = cell
                reachable = {}
                food_range = profile["nominal_food_range_cm"]
                for pair, expected in profile["pairs"].items():
                    start, end = pair.split(":")
                    if start in sites and start not in reachable:
                        reachable[start] = connected_cells(sites[start], passable)
                    connected = end in sites and sites[end] in reachable.get(start, ())
                    if connected != expected["connected_depth_grid"]:
                        raise AssertionError(f"{run['seed']} {phase} {species} size {size}: {pair} disagrees")
                    from_position, to_position = (grid["sites_cm"][name] for name in (start, end))
                    distance = math.dist(from_position, to_position)
                    for time in ("day", "night"):
                        if (distance <= food_range[time]) != expected[f"within_nominal_{time}_food_range"]:
                            raise AssertionError(f"{phase} {species} {pair}: nominal {time} range disagrees")
                    checks += 1
    if not checks:
        raise AssertionError("Missing water-grid comparisons")
    print(f"Water grid seed {run['seed']}: {checks} species, size, phase and patch-pair checks matched")


def check_food_choice(run, *, expect_switch=True):
    """Recompute rule scores after the recorded water, sight and recent-block gates."""
    decisions = run["decisions"]
    if not decisions or not any(row["seeking"] for row in decisions):
        raise AssertionError("Expected an active food search for the tracked animal")
    for decision in decisions:
        if not decision["seeking"] and decision["candidates"]:
            raise AssertionError("Food candidates were evaluated while the animal was not seeking")
        best_score = 0.
        selected = ("None", 0)
        for candidate in decision["candidates"]:
            gate = candidate["gate"]
            distance, stock = candidate["distance_cm"], candidate["stock"]
            if distance > candidate["range_cm"]:
                if gate != "Range":
                    raise AssertionError("Out-of-range patch was not excluded")
                continue
            if stock < .2:
                if gate != "Stock":
                    raise AssertionError("Depleted patch was not excluded")
                continue
            if gate in {"Depth", "WetCorridor", "RecentBlock"}:
                continue
            if gate not in {"Visible", "Waterborne"}:
                raise AssertionError(f"Unexpected candidate gate {gate}")
            patch = candidate["patch"]
            score = min(stock, run["energy_per_meal"][patch]) / (1. + distance / run["walk_speed_cm_s"])
            if not math.isclose(score, candidate["score"], rel_tol=1e-7):
                raise AssertionError(f"Food score mismatch at {decision['at']} for {patch}")
            if score > best_score:
                best_score, selected = score, (patch, candidate.get("access", 0))
        if selected != (decision["selected_patch"], decision.get("access", 0)):
            raise AssertionError(f"Expected {selected} at {decision['at']}")
    for receipt in run["payments"]:
        choice = next((row for row in reversed(decisions) if row["at"] <= receipt["at"]), None)
        if receipt["amount"] <= 0:
            raise AssertionError("Food receipt must have a positive payment")
        if (choice is None or choice["selected_patch"] != receipt["patch"]
                or choice.get("access", 0) != receipt.get("access", 0)):
            raise AssertionError("Payment did not follow selection of the same patch")
    if expect_switch and not any(
            previous["remaining"] == 0 and previous["patch"] != current["patch"]
            for previous, current in zip(run["payments"], run["payments"][1:])):
        raise AssertionError("Expected a paid food switch following depletion")
    print(f"{run.get('species', 'CommonCarp')} food choice seed {run['seed']}: "
          f"{len(decisions)} decisions and {len(run['payments'])} receipts matched")


def check_small_fish_range(pair):
    control, split = pair["control"], pair["split"]
    if control["initial"] != split["initial"]:
        raise AssertionError("Tracked fish did not start with the same position, energy and body clearance")
    for run in (control, split):
        check_food_choice(run, expect_switch=False)
    misses = [candidate for decision in control["decisions"] for candidate in decision["candidates"]]
    if (not misses or any(candidate["gate"] != "Range" for candidate in misses)
            or not any(candidate["stock"] >= .2 for candidate in misses) or control["payments"]):
        raise AssertionError("Expected stocked but out-of-range resources during the control")
    if not split["payments"] or any(row["patch"] != pair["local_patch"] for row in split["payments"]):
        raise AssertionError("Expected payments at the newly reachable patch")
    expected = pair["expected_founder_receipts"]
    if any(set(run["founders_paid"]) != set(expected[name])
           for name, run in (("control", control), ("split", split))):
        raise AssertionError("Founder coverage changed in the replay")
    if control["authored_capacity"] != split["authored_capacity"] or not math.isclose(
            control["authored_regrowth"], split["authored_regrowth"], abs_tol=1e-6):
        raise AssertionError("The split altered the initial food or regrowth budget")


def check_small_fish_matched_population(pair):
    baseline, repeat, split = pair["runs"]
    if pair["changed_patches"] != ["IslandRiverDrift", "IslandRiverDriftForageNearRoots"]:
        raise AssertionError("Only the Drift forage allocation should differ")
    for field in ("capacity", "regrowth_per_second"):
        values = pair["authored_budget"][field]
        if not math.isclose(values["control"], values["split"], abs_tol=1e-6):
            raise AssertionError(f"The split altered authored {field}")
    for run in (baseline, repeat, split):
        steps, payments = run["steps"], run["payments"]
        if set(steps) != {"1", "1800", "3600"} or sum(steps["1"]["population"].values()) != 118:
            raise AssertionError("Expected a complete 60-minute island trial with 118 founders")
        for time, totals in payments["pay_by_time"].items():
            for species, total in totals.items():
                by_source = sum(amount for name, amount in payments["source_pay_by_time"][time].items()
                                if name.startswith(species + ":"))
                by_agent = sum(amount for name, amount in payments["per_agent_pay_by_time"][time].items()
                               if name.startswith(species + ":"))
                if not (math.isclose(total, by_source, abs_tol=.006)
                        and math.isclose(total, by_agent, abs_tol=.006)):
                    raise AssertionError("Aquatic receipts must balance by animal and by source")
    for run in (baseline, repeat):
        if run["payments"]["source_pay_by_time"]["3600"].get("UnidentifiedFish:IslandRiverDriftForageNearRoots"):
            raise AssertionError("Control reports unexpected split-patch payment")
    if split["payments"]["source_pay_by_time"]["3600"]["UnidentifiedFish:IslandRiverDriftForageNearRoots"] <= 0.:
        raise AssertionError("Expected actual receipt at the alternate patch")
    print(f"Seed {pair['seed']}: matched 60-minute aquatic receipt totals checked for three runs")


def check_shared_underwater_access(run):
    check_food_choice(run, expect_switch=False)
    if not run["payments"] or any(receipt["access"] != 1 for receipt in run["payments"]):
        raise AssertionError("Expected the tracked fish to eat at the extra access point")
    rows = run["shared_receipts_300"]
    previous_at, previous_stock = 0., run["budget"]
    access_points = set()
    shared_tick_points = {}
    for row in rows:
        if row["at"] < previous_at or row["patch"] != "IslandRiverDrift":
            raise AssertionError("Shared Drift receipts must be in authority order")
        reconstructed_before = row["remaining"] + row["amount"]
        if (not 0. < row["amount"] <= run["energy_per_meal"][row["patch"]] + .001
                or not 0. <= row["remaining"] <= run["budget"]):
            raise AssertionError("Drift receipt exceeded the menu or stock limit")
        if reconstructed_before > run["budget"] + .001 or (
                row["at"] == previous_at and not math.isclose(previous_stock, reconstructed_before, abs_tol=.0011)):
            raise AssertionError("Both points must draw from the same stock")
        access_points.add(row["access"])
        shared_tick_points.setdefault(row["at"], set()).add(row["access"])
        previous_at, previous_stock = row["at"], row["remaining"]
    if access_points != {0, 1}:
        raise AssertionError("Expected receipts at the original and extra coordinates")
    simultaneous = sum(len(points) > 1 for points in shared_tick_points.values())
    print(f"Seed {run['seed']}: {len(rows)} receipts reconciled against shared Drift stock; "
          f"{simultaneous} authority times paid both points")
    if "first_approach" in run:
        check_first_shared_approach(run)


def check_first_shared_approach(run):
    approach = run["first_approach"]
    control = approach["control"]["decisions"]
    extra = approach["extra_point"]["decisions"]
    before, selected, near, after = extra
    radius = approach["delivery_radius_cm"]
    point = run["access_cm"]
    original = approach["original_point_cm"]
    distances = [math.dist(row["position_cm"], point) for row in (selected, near, after)]
    payment = run["payments"][0]
    if (any(a["at"] != b["at"] for a, b in zip(control, extra))
            or not all(math.dist(a["position_cm"], b["position_cm"]) <= .002 for a, b in zip(control[:2], extra[:2]))
            or any(row["patch"] != "None" for row in control) or not all(row["seeking"] for row in control[1:])):
        raise AssertionError("Expected matching pre-choice positions and no feeding selection in the original layout")
    if (before["seeking"] or after["seeking"] or not all(row["seeking"] and row["access"] == 1
            and row["patch"] == payment["patch"] for row in (selected, near))
            or not distances[0] > radius >= distances[1] > distances[2]
            or math.dist(near["position_cm"], original) <= radius
            or not near["at"] < payment["at"] < after["at"]
            or payment["agent"] != approach["agent"] or payment["access"] != 1
            or after["energy_fraction"] <= near["energy_fraction"]):
        raise AssertionError("Expected alternate-point selection, approach, then actual authority payment")
    print(f"Seed {run['seed']}: first approach distances {', '.join(f'{d:.1f}' for d in distances)} cm; "
          f"alternate point paid {payment['amount']:.1f} at {payment['at']:g}s")


def check_small_fish_runtime_coverage(runs):
    expected = {
        "wet_travel_base60": {"IslandRiverDrift"},
        "drift_shared60": {"IslandRiverDrift"},
        "drift15_matched60": {"IslandRiverDrift", "IslandRiverDriftForageNearRoots"},
    }
    seen = set()
    for run in runs:
        seed, layout = run["seed"], run["layout"]
        positions = run["positions"]
        if len(positions) != 7 or run["clock_end"] != 3600 or (seed, layout) in seen:
            raise AssertionError("Expected one complete population run with the seven founder fish")
        seen.add((seed, layout))
        for rows in positions.values():
            if rows[0][0] != 1 or any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
                raise AssertionError("Expected ordered living position samples starting at authority second one")
        excursion = max(math.dist(row[1:], rows[0][1:]) for rows in positions.values() for row in rows)
        shelf_distance = min(math.dist(row[1:], run["shelf_cm"]) for rows in positions.values() for row in rows)
        payments = run["patch_payments"]
        sources = {patch for receipts in payments.values() for patch in receipts}
        if (not payments.keys() <= positions.keys() or any(v <= 0 for r in payments.values() for v in r.values())
                or sources != expected[layout] or excursion >= 200 or shelf_distance <= 7000):
            raise AssertionError(f"Observed small fish coverage changed for {seed} {layout}")
        print(f"Seed {seed} {layout}: sampled excursion up to {excursion / 100:.2f} m; "
              f"nearest shelf sample {shelf_distance / 100:.2f} m; patch payments at {', '.join(sorted(sources))}")
    if seen != {(seed, layout) for seed in (20000, 20017) for layout in expected}:
        raise AssertionError("Expected all six seed and layout combinations")


def replay_nursery(site_z_cm, reservation, probes):
    """Replay reservation continuity with parents and the other hatch gates held eligible."""
    for probe in probes:
        at = probe["at"]
        if at < reservation["reserved_at"]:
            continue
        column = probe["column_cm"]
        if column is None or not submerged(*column, site_z_cm):
            return "interrupted", at
        if at >= reservation["due_at"]:
            return "hatch_eligible", at
    return "pending", None


def check_nursery(run):
    for case in run["reservations"]:
        state, at = replay_nursery(case["site_z_cm"], case, case["probes"])
        if [state, at] != case["expected"]:
            raise AssertionError(f"Nursery reservation {case['site']} at {case['reserved_at']}: got {state} at {at}")
    interrupted = next(case for case in run["reservations"] if case["expected"][0] == "interrupted")
    original_column = interrupted["probes"][0]["column_cm"]
    control = [{**probe, "column_cm": original_column} for probe in interrupted["probes"]]
    state, at = replay_nursery(interrupted["site_z_cm"], interrupted, control)
    if state != "hatch_eligible" or at < interrupted["due_at"]:
        raise AssertionError("Continuous-submersion control did not remain eligible until the due time")
    print(f"Carp nursery seed {run['seed']}: interruption, unaffected hatch eligibility and new reservation matched")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture["schema_version"] != 1 or not any(fixture.get(key) for key in (
            "carp", "mink", "water_grid", "food_choice", "nursery", "small_fish_range", "small_fish_matched60",
            "shared_underwater_access", "small_fish_runtime_coverage", "water_payment_attempts", "water_meal_control",
            "water_stock_ledger")):
        parser.error("expected a water access fixture with schema_version 1")
    for case in fixture.get("carp", ()):
        check_carp(case)
        check_fry_surface_recovery(case)
    if fixture.get("carp"):
        check_water_meal_boundaries()
    for case in fixture.get("mink", ()):
        check_mink(case)
    for case in fixture.get("water_grid", ()):
        check_grid(case)
    for case in fixture.get("food_choice", ()):
        check_food_choice(case)
    for case in fixture.get("nursery", ()):
        check_nursery(case)
    for case in fixture.get("small_fish_range", ()):
        check_small_fish_range(case)
    for case in fixture.get("small_fish_matched60", ()):
        check_small_fish_matched_population(case)
    for case in fixture.get("shared_underwater_access", ()):
        check_shared_underwater_access(case)
    if "small_fish_runtime_coverage" in fixture:
        check_small_fish_runtime_coverage(fixture["small_fish_runtime_coverage"])
    for case in fixture.get("water_payment_attempts", ()):
        check_water_payment_attempts(case)
    if "water_meal_control" in fixture:
        check_water_meal_control(fixture["water_meal_control"])
    for case in fixture.get("water_stock_ledger", ()):
        check_water_stock_ledger(case)


if __name__ == "__main__":
    main()

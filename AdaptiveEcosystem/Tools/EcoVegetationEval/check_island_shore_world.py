"""Execute paired shoreline worlds using the latest island's measured endpoints."""

import argparse
import json
from math import dist, isclose
from pathlib import Path

from island_shore_reference_world import MinkReturnWorld, ShoreAnimal, ShoreForageWorld, SwimExit, step_toward, swim_step


def require(result, expected):
    if result != expected:
        raise AssertionError(f"expected {expected!r}, got {result!r}")


def make_world(run, with_bank):
    points = {"start": run["start_cm"], "root": run["root_cm"], "bank": run["extra_access_cm"]}
    connections = [("start", "root"), ("start", "bank")]
    access = ("root", "bank") if with_bank else ("root",)
    return ShoreForageWorld(points, connections, access, run["surface_z_cm"], run["stock_at_start"], run["meal_cap"])


def check_pair(pair):
    control, bank = pair["root_only"], pair["bank_access"]
    for field in ("start_cm", "root_cm", "surface_z_cm", "stock_at_start", "meal_cap", "wade_depth_cm"):
        require(control[field], bank[field])
    require(control["extra_access_cm"], None)
    require(control["payments"], [])
    world = make_world(bank, with_bank=False)
    for species, wade in bank["wade_depth_cm"].items():
        animal = ShoreAnimal("start", wade, 20., 100.)
        can_wade = control["active_water_routes"][species]["1.0"]["to_patch"]
        require(world.move(animal, "root"), "arrived" if can_wade else "blocked_depth")
        require(animal.position, "root" if can_wade else "start")
        if can_wade:
            require(world.move(animal, "start"), "arrived")
    horse = ShoreAnimal("start", bank["wade_depth_cm"]["Horse"], 20., 100.)
    require(world.eat(horse, "root"), ("ineligible", 0.))
    require(world.move(horse, "bank"), "arrived")
    require(world.eat(horse, "bank"), ("ineligible", 0.))
    require(world.stock, control["stock_at_end"])

    world = make_world(bank, with_bank=True)
    horse.position = "start"
    require(world.eat(horse, "bank"), ("outside_reach", 0.))
    require(world.move(horse, "bank"), "arrived")
    outcome, payment = world.eat(horse, "bank")
    require(outcome, "paid")
    first = bank["payments"][0]
    require(first["access"], 1)
    require(isclose(payment, first["amount"], abs_tol=.0005), True)
    require(isclose(world.stock, first["remaining"], abs_tol=.0005), True)
    require(isclose(horse.energy, 20. + payment), True)

    # Recession permits the root again. Both access points draw from the same patch.
    world.surface_z_cm = bank["root_cm"][2]
    second = ShoreAnimal("start", horse.wade_depth_cm, 99.5, 100.)
    require(world.move(second, "root"), "arrived")
    require(world.eat(second, "root"), ("paid", .5))
    require(isclose(world.stock, bank["stock_at_start"] - payment - .5), True)
    require(world.eat(second, "root"), ("below_minimum", 0.))
    require(world.move(second, "start"), "arrived")
    print(f"Seed {pair['seed']}: flood blocked the root for horse; bank paid {payment:.2f}; recession reopened the shared root")


def check_mink_exit(case):
    walk = case["dry_bank_walk"]
    shore, bank = walk["shore_cm"], walk["dry_bank_cm"]
    high = case["raised_surface_cm"]
    points = {"old_shore": (0., 0., case["previous_bank_z_cm"]), "shore": shore, "bank": bank}
    world = ShoreForageWorld(points, [("shore", "bank")], (), high, 0., 0.)
    mink = ShoreAnimal("shore", 0., 0., 100.)
    require(world.wadeable(mink, "old_shore"), False)
    require(world.move(mink, "bank"), "arrived")
    world.surface_z_cm = case["normal_surface_cm"]
    require(world.wadeable(mink, "old_shore"), True)
    world.surface_z_cm = bank[2] + 1.
    mink.position = "shore"
    require(world.move(mink, "bank"), "blocked_depth")

    first, second, *later = walk["samples"]
    if not later or second["at"] <= first["at"]:
        raise AssertionError("Expected early speed samples and later holdout points")
    speed = dist(first["position_cm"][:2], second["position_cm"][:2]) / (second["at"] - first["at"])
    length = dist(shore[:2], bank[:2])
    direction = [(end - start) / length for start, end in zip(shore[:2], bank[:2])]
    origin = first["position_cm"][:2]
    for sample in later:
        traveled = speed * (sample["at"] - first["at"])
        predicted = [start + axis * traveled for start, axis in zip(origin, direction)]
        if sample["position_cm"][2] <= high or dist(predicted, sample["position_cm"][:2]) > 3.:
            raise AssertionError(f"Held-out dry-bank sample diverged at {sample['at']}")
    # Compare against a sampled interval on the same PIE clock, not the gameplay event clock.
    eta = first["at"] + (dist(origin, bank[:2]) - 3.) / speed
    lower = walk["last_clearing_world_seconds"]
    upper = case["dry_ground_arrival_world_seconds"]
    # Continuous motion can enter the three-centimeter radius one tick before it is recorded.
    fixed_step_seconds = 1. / 30.
    if not lower - fixed_step_seconds <= eta <= upper < case["restore_world_seconds"]:
        raise AssertionError(f"Predicted dry-bank arrival {eta} falls outside [{lower}, {upper}]")
    print(f"Seed {case['seed']}: old shore blocked; saved-bank ETA {eta:.2f}s, sampled interval {lower:.2f}-{upper:.2f}s")


def check_mink_alternate_exit(case):
    wet_decision = None
    for decision in case["decisions"]:
        if decision["previous"]:
            require(decision["candidates"], [])
            require(decision["selected"], None)
            continue
        best = "None"
        best_distance = float("inf")
        for candidate in decision["candidates"]:
            gate, distance = candidate["gate"], candidate["distance_sq"]
            if gate in {"Shore", "Depth", "RecentBlock"}:
                require(distance, -1.)
                if gate == "RecentBlock":
                    require(decision["recent_block"], True)
                continue
            if gate == "Farther":
                require(distance >= best_distance, True)
                continue
            if gate not in {"Clear", "Occluded"} or not 0. <= distance < best_distance:
                raise AssertionError(f"Unexpected exit gate {gate} at {decision['at']}")
            if gate == "Clear":
                best, best_distance = candidate["patch"], distance
        require(decision["selected"], best)
        if isclose(decision["at"], case["alternate_exit_at"], abs_tol=1e-6):
            wet_decision = decision
    if (wet_decision is None or wet_decision["selected"] != case["platform_patch"]
            or not case["previous_bank_z_cm"] < case["raised_surface_cm"] < case["platform_z_cm"]
            or not case["alternate_exit_at"] < case["swim_exit_at"]):
        raise AssertionError("The flooded route did not produce the observed alternate choice and exit")
    clear = [candidate for candidate in wet_decision["candidates"] if candidate["gate"] == "Clear"]
    if len(clear) < 2 or not any(row["previous"] for row in case["decisions"] if row["at"] > wet_decision["at"]):
        raise AssertionError("Expected competing exits and later reuse of the selected route")
    print(f"Seed {case['seed']}: {len(case['decisions'])} exit decisions matched, including the alternate platform")


def check_mink_exit_cover(case):
    clear = case["clear_decision"]
    covered = case["covered_decision"]
    require(clear["previous"], False)
    require(covered["previous"], False)
    require(clear["recent_block"], False)
    require(covered["recent_block"], False)
    require(clear["at"], covered["at"])
    require(clear["clearance_cm"], covered["clearance_cm"])
    require({row["patch"]: row["distance_sq"] for row in clear["candidates"]},
            {row["patch"]: row["distance_sq"] for row in covered["candidates"]})
    near, far = clear["selected"], covered["selected"]
    if near == far:
        raise AssertionError("The covered exit should change the selected route")
    for decision, near_gate in ((clear, "Clear"), (covered, "Occluded")):
        candidates = {row["patch"]: row for row in decision["candidates"]}
        require(candidates[near]["gate"], near_gate)
        require(candidates[far]["gate"], "Clear")
        require(candidates[near]["distance_sq"] < candidates[far]["distance_sq"], True)
        selected = min((row for row in decision["candidates"] if row["gate"] == "Clear"),
                       key=lambda row: row["distance_sq"])
        require(selected["patch"], decision["selected"])
    require(case["swimming_at_restore"], True)
    require(case["exited_before_restore"], False)
    print(f"Seed {case['seed']}: sight cover changed the selection from {near} to {far}")


def check_mink_exit_budget(case):
    require(case["far_gate"], "Stamina")
    require(case["covered_near_gate"], "Occluded")
    require(case["covered_selected"], "None")
    require(case["clear_near_gate"], "Clear")
    require(case["clear_selected"], "IslandRiverSecondMinkShore")
    if case["stamina_at_restore"] < case["stamina_after_first_search"] - .001:
        raise AssertionError("Waiting for another exit spent swimming stamina")
    if not case["clear_alternate_at"] < case["clear_swim_exit_at"]:
        raise AssertionError("The reachable exit did not produce an actual landing")
    if not case["reopened_after_seconds"] <= 1. or case["resurfaced_stamina"] <= .8:
        raise AssertionError("The reopened route did not produce a prompt, low-cost exit")
    print(f"Seed {case['seed']}: unreachable exit rejected; nearby exit remained usable")


def check_mink_independent_exit(case):
    sensed = case["sensed"]
    surface = case["surface_cm"]
    exits = [SwimExit(row["id"], tuple(row["entry_cm"]), tuple(row["bank_cm"]), row["column_cm"])
             for row in sensed["exits"]]
    for exit_point in exits:
        entry = exit_point.entry_at_depth(case["clearance_cm"])
        actual = dist(sensed["position_cm"], entry)
        measured = case["authority_distance_sq_cm"][exit_point.name] ** .5
        if abs(actual - measured) > .025:
            raise AssertionError(f"Sampled entry geometry differs from authority: {exit_point.name}")
    cover = [tuple((center - 24., center + 24.) for center in case["cover_cm"])]
    for speed in case["swim_speed_range_cm_s"]:
        world = MinkReturnWorld(sensed["position_cm"], case["clearance_cm"], speed,
                                sensed["current_cm_s"], sensed["stamina"], exits)
        for blocked, boxes in ((True, cover), (False, ())):
            actual = world.choose_exit(surface, boxes)
            expected = case["covered_candidates"] if blocked else case["clear_candidates"]
            require(actual, expected)
            selected = "None" if world.target is None else world.target[0].name
            require(selected, case["covered_selected"] if blocked else case["clear_selected"])
            if blocked:
                world.swim_toward_exit(1.)
                require(world.position, tuple(sensed["position_cm"]))
                require(world.stamina, sensed["stamina"])
        world.swim_toward_exit(40.)
        require(world.phase, "exiting")
        require(world.land(world.target[0].bank[2] + 1.), False)
        require(world.phase, "swimming")
        world.choose_exit(surface)
        world.swim_toward_exit(1.)
        require(world.land(surface), True)
        require(world.phase, "ground")
        require(world.position, next(exit_point.bank for exit_point in exits
                                     if exit_point.name == case["clear_selected"]))
        require(world.stamina < sensed["stamina"], True)
        tired = MinkReturnWorld(sensed["position_cm"], case["clearance_cm"], speed,
                                sensed["current_cm_s"], .01, exits)
        require(tired.choose_exit(surface)[case["clear_selected"]], "Stamina")
        require(tired.target, None)
    near = next(exit_point for exit_point in exits if exit_point.name == case["clear_selected"])
    entry = near.entry_at_depth(case["clearance_cm"])
    start = sensed["position_cm"]
    length = dist(start, entry)
    following = tuple(35. * (b - a) / length for a, b in zip(start, entry))
    for current, gate in ((following, "Clear"), (tuple(-v for v in following), "Stamina")):
        world = MinkReturnWorld(start, case["clearance_cm"], 45., current, .08, exits)
        require(world.choose_exit(surface)[near.name], gate)
    print(f"Seed {case['seed']}: measured current and clearance reproduced covered wait and clear exit")


def check_mink_swim_track(case):
    # Calibrate propulsion from the first observed interval in each phase.
    start, calibration, *swimming = case["return_swim"]
    seconds = calibration["at"] - start["at"]
    speed = dist(start["position_cm"], [b - a * seconds for a, b in
                 zip(start["current_cm_s"], calibration["position_cm"])]) / seconds
    clearance = case["clearance_cm"]
    entry = case["entry_cm"]
    position = calibration["position_cm"]
    previous = calibration
    max_swim_error = 0.
    for row in swimming:
        seconds = row["at"] - previous["at"]
        position = swim_step(position, entry, speed, previous["current_cm_s"], row["column_cm"], clearance, seconds)
        if position is None:
            raise AssertionError("Return route became too shallow")
        max_swim_error = max(max_swim_error, dist(position, row["position_cm"]))
        expected_stamina = calibration["stamina"] - .025 * (row["at"] - calibration["at"])
        if abs(row["stamina"] - expected_stamina) > .0001:
            raise AssertionError("Swimming stamina must follow the measured time budget")
        previous = row
    if not swimming or max_swim_error > 2.5 or dist(position, entry) > 30.:
        raise AssertionError(f"Return swim diverged by {max_swim_error:.2f} cm")

    first, second, *holdout = case["exiting"]
    bank = case["bank_cm"]
    bank_center = (*bank[:2], bank[2] + clearance + 2.)
    speed = dist(first["position_cm"], second["position_cm"]) / (second["at"] - first["at"])
    max_exit_error = 0.
    for row in holdout:
        estimated = step_toward(second["position_cm"], bank_center, speed * (row["at"] - second["at"]))
        max_exit_error = max(max_exit_error, dist(estimated, row["position_cm"]))
        require(row["stamina"], first["stamina"])
    eta = second["at"] + max(0., dist(second["position_cm"], bank_center) - 2.) / speed
    if not holdout or max_exit_error > 2.5 or not holdout[-1]["at"] - 1. / 30. <= eta <= case["on_bank_at"]:
        raise AssertionError(f"Exit approach diverged by {max_exit_error:.2f} cm or missed landing interval")
    print(f"Seed {case['seed']}: swim holdout error {max_swim_error:.2f} cm; exit {max_exit_error:.2f} cm; "
          f"landing ETA {eta:.2f}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture["schema_version"] != 1 or not any(fixture.get(key) for key in (
            "shore_access", "mink", "mink_alternate_exit", "mink_exit_cover", "mink_exit_budget",
            "mink_independent_exit", "mink_swim_track")):
        parser.error("expected shoreline forage or mink exits with schema_version 1")
    for pair in fixture.get("shore_access", ()):
        check_pair(pair)
    for case in fixture.get("mink", ()):
        check_mink_exit(case)
    for case in fixture.get("mink_alternate_exit", ()):
        check_mink_alternate_exit(case)
    for case in fixture.get("mink_exit_cover", ()):
        check_mink_exit_cover(case)
    for case in fixture.get("mink_exit_budget", ()):
        check_mink_exit_budget(case)
    for case in fixture.get("mink_independent_exit", ()):
        check_mink_independent_exit(case)
    for case in fixture.get("mink_swim_track", ()):
        check_mink_swim_track(case)


if __name__ == "__main__":
    main()

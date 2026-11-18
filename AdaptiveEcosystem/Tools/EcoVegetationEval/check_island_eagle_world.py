"""Run controlled dives from measured Highland rat sites."""

import argparse
import json
from math import dist, isclose
from pathlib import Path

from island_eagle_reference_world import BoxObstacle, EagleDiveWorld, Rat


STEP_S = 1. / 30.


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def start_world(site, mass_ratio=.2, obstacles=()):
    x, y, z = site
    start = (x - 1200., y, z + 1830.)
    return EagleDiveWorld(start, Rat(tuple(site), mass_ratio, 12.6), obstacles=obstacles)


def queue_dive(world):
    check(world.request_dive() == "diving", "expected an unobstructed dive")
    for _ in range(100):
        outcome = world.step(STEP_S, world.rat.position)
        if outcome == "queued":
            check(dist(world.position, world.rat.position) <= world.reach_cm, "queued out of reach")
            return
        check(outcome == "diving", f"unexpected dive outcome {outcome}")
    raise AssertionError("dive did not reach the rat")


def finish_contact(world, velocity_x):
    locked_position = world.position
    for frame in range(1, 4):
        x, y, z = world.rat.position
        outcome = world.step(STEP_S, (x + velocity_x * STEP_S, y, z))
        check(world.position == locked_position, "eagle must hold position during windup")
        if frame < 3:
            check(outcome == "windup", "contact resolved before windup elapsed")
    return outcome


def check_site(site):
    still = start_world(site)
    queue_dive(still)
    check(finish_contact(still, 0.) == "captured" and not still.rat.alive, "stationary rat must be captured")
    check(isclose(still.carcass_stock, 12.6), "captured rat must create one finite stock")
    payments = [still.eat_at_carcass(headroom) for headroom in (3., 10., 10., 10.)]
    check(payments[:2] == [3., 5.] and isclose(sum(payments), 12.6) and payments[-1] == 0., "meal budget mismatch")

    escape = start_world(site)
    queue_dive(escape)
    check(finish_contact(escape, 220.) == "miss_range" and escape.rat.alive, "moving rat must escape reach")
    check(escape.eat_at_carcass(10.) == 0., "a miss must not create carcass stock")
    check(start_world(site, mass_ratio=.36).request_dive() == "size", "mass must constrain the dive request")

    x, y, z = site
    cover = start_world(site, obstacles=(((x - 600., y, z + 920.), 60.),))
    check(cover.request_dive() == "occluded", "intervening rock must hide the rat")
    sweep = start_world(site, obstacles=(((x - 600., y + 23., z + 933.), 16.),))
    check(sweep.request_dive() == "diving", "off-axis rock must leave the sightline clear")
    for _ in range(100):
        outcome = sweep.step(STEP_S, sweep.rat.position)
        if outcome != "diving":
            break
    check(outcome == "dive_blocked", "body sweep must catch an obstacle outside the sightline")
    late_cover = start_world(site)
    queue_dive(late_cover)
    hx, hy, hz = late_cover.position
    late_cover.obstacles = ((((hx + x) / 2., (hy + y) / 2., (hz + z) / 2. + 20.), 12.),)
    check(finish_contact(late_cover, 0.) == "miss_occluded" and late_cover.rat.alive, "contact must recheck sight")


def check_geometry(run):
    for row in run["rows"]:
        shape = row["obstacle"]
        boxes = () if shape is None else (BoxObstacle(tuple(shape["center_cm"]), shape["half_extent_cm"], shape["physical"]),)
        prey = Rat(tuple(row["prey_cm"]), .2, 12.6)
        world = EagleDiveWorld(tuple(row["start_cm"]), prey, boxes=boxes,
                               sweep_radius_cm=run["sweep_radius_cm"], eye_cm=run["eye_cm"], prey_eye_cm=run["prey_eye_cm"])
        blocked = any(box.physical and box.intersects(world.position, row["contact_cm"], world.sweep_radius_cm)
                      for box in boxes)
        check((world.visible(), blocked) == (row["clear"], row["body_blocked"]), f"Geometry mismatch: {row}")
        if not row["clear"]:
            check(world.request_dive() == "occluded" and prey.alive, "Sight cover must prevent starting a dive")
            continue
        if blocked:
            check(world.request_dive() == "diving", "Clear sight should allow an attempt")
            for _ in range(100):
                outcome = world.step(STEP_S, prey.position)
                if outcome != "diving":
                    break
            check(outcome == "dive_blocked" and prey.alive, "Physical cover must stop the moving body")
        else:
            queue_dive(world)
            check(finish_contact(world, 0.) == "captured", "Clear path must reach stationary prey")
    print(f"Seed {run['seed']}: {len(run['rows'])} Unreal sight and body probes matched and drove Python dive outcomes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    runs = [run for run in fixture["runs"] if run["condition"] == "near"]
    if not runs:
        parser.error("expected measured Highland rat sites")
    for run in runs:
        for site in run["founders"]["sites_cm"]:
            check_site(site)
        print(f"Seed {run['seed']}: stationary capture, escape during windup, body limit, cover and stock passed")
    for run in fixture.get("saved_geometry", ()):
        check_geometry(run)


if __name__ == "__main__":
    main()

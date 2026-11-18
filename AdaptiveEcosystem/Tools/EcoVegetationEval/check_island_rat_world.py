"""Check Python refuge decisions against Riverbank geometry and saved-island samples."""

import argparse
import hashlib
import json
import re
from math import dist, hypot
from pathlib import Path

from island_rat_reference_world import Hunter, RatRefugeWorld


APPROACH = re.compile(
    r"\[Eco Shelter Approach\] Agent=(\d+) At=([\d.]+) Patch=IslandRiverRatRefuge(\d+) "
    r"Mouth=X=([-.\d]+) Y=([-.\d]+) Z=([-.\d]+) Position=X=([-.\d]+) Y=([-.\d]+) Z=([-.\d]+)"
)


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def approach_pairs(log, sites):
    previous = {}
    for row in APPROACH.finditer(log):
        agent, at, site_index = row.group(1, 2, 3)
        agent, at, site_index = int(agent), float(at), sites[int(site_index)]["site_index"]
        mouth, position = (tuple(map(float, row.group(*groups))) for groups in ((4, 5, 6), (7, 8, 9)))
        prior = previous.get(agent)
        previous[agent] = at, position
        if prior and .015 <= at - prior[0] <= .018:
            yield {"agent": agent, "at": at, "start_cm": prior[1], "site": site_index, "mouth_cm": mouth}


def check_recorded(sites, rows):
    world = RatRefugeWorld(sites)
    for row in rows:
        route = world.choose_refuge(row["start_cm"])
        check(route is not None and route.via_mouth and route.site == row["site"]
              and dist(route.goal, row["mouth_cm"]) < .002, f"Different approach to {row}: {route}")


def check_sight(sites):
    count = 0
    for site in sites:
        world = RatRefugeWorld(sites, vision=site["rat_vision"])
        for case in site["sight_cases"]:
            clear = world.clear_sight(case["start_cm"], case["end_cm"], case["target_height_cm"])
            check(clear == case["clear"], f"Line trace differs at {site['site_index']}: {case}")
            count += 1
    return count


def check_surveyed(site):
    world = RatRefugeWorld([site])
    center = tuple((a + b) / 2. for a, b in zip(*site["mouths_cm"]))
    for row in site["rat_approaches"]:
        point = row["start_cm"]
        traversable = [tuple(mouth) for mouth, passed in zip(site["mouths_cm"], row["through_mouth"]) if passed]
        expected = center if row["direct"] else min(
            traversable, key=lambda mouth: dist(point, mouth) + dist(mouth, center), default=None)
        result = world.choose_refuge(point)
        check(result is not None and result.goal == expected, f"Wrong route for measured start {point}")


def check_controlled(site, vision):
    left, right = site["mouths_cm"]
    cx, cy, cz = tuple((a + b) / 2. for a, b in zip(left, right))
    dx, dy = right[0] - left[0], right[1] - left[1]
    length = hypot(dx, dy)

    def point(along, across):
        return (cx + (along * dx - across * dy) / length,
                cy + (along * dy + across * dx) / length, cz)

    center = point(0., 0.)
    check(RatRefugeWorld([site], vision=vision).sense(0., center, 0., 0., [Hunter(1, point(0., 100.))]) is None,
          "Tunnel wall must obstruct a nearby hunter")
    check(RatRefugeWorld([], vision=vision).sense(0., center, 0., 0., [Hunter(1, point(0., 100.))]) == 1,
          "Removing the wall should expose the same hunter")
    at_distance = Hunter(1, (left[0] - 580., left[1], left[2]))
    check(RatRefugeWorld([], vision=vision).sense(0., left, 180., 0., [at_distance]) == 1, "Daylight range")
    check(RatRefugeWorld([], vision=vision).sense(0., left, 180., 1., [at_distance]) is None, "Night range")
    check(RatRefugeWorld([], vision=vision).sense(0., left, 0., 0., [at_distance]) is None, "Rear field of view")
    nearby = Hunter(2, (left[0] - 85., left[1], left[2]))
    check(RatRefugeWorld([]).sense(0., left, 0., 0., [nearby, at_distance]) == 2, "Near awareness")
    inactive = Hunter(3, center, tailing_prey=False)
    check(RatRefugeWorld([]).sense(0., left, 0., 0., [inactive]) is None, "Inactive hunter")

    start = point(160., 100.)
    hunter = Hunter(1, point(160., 180.))
    world = RatRefugeWorld([site])
    check(world.sense(0., start, 0., .5, [hunter]) == 1, "Hunter should start flight")
    route = world.escape(0., start)
    check(route and route.via_mouth and route.goal == tuple(right), "Blocked direct path should choose near mouth")
    check(world.sense(.1, start, 0., .5, [hunter]) is None, "No scan before the .45-second interval")
    check(world.sense(.45, start, 0., .5, ()) is None and world.escape(.45, start) == route,
          "Retain last threat during brief loss of contact")
    check(world.escape(.8, tuple(right)).goal == center, "At the mouth, advance into the tunnel")
    check(world.escape(1.1, center).goal == center and world.escape(1.5, center) is None,
          "Threat expiry should release shelter intent")
    other_side = RatRefugeWorld([site]).choose_refuge(point(-160., -100.))
    check(other_side and other_side.via_mouth and other_side.goal == tuple(left), "Opposite entrance should work")
    large = RatRefugeWorld([site], body_scale=2.)
    check(large.sense(0., start, 0., .5, [hunter]) == 1, "Size should not prevent awareness")
    fallback = large.escape(0., start)
    check(fallback and fallback.site is None and abs(dist(start, fallback.goal) - 600.) < .001,
          "Body that cannot enter should choose a free escape direction")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--saved-root", type=Path, help="Also verify every usable consecutive pair from the source logs")
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != 1 or fixture.get("training_ready") is not False:
        parser.error("expected geometry and authority reference samples")
    vision = fixture["saved_sight_reference"][0]["sites"][0]["rat_vision"]
    for run in fixture["runs"]:
        for site in run["sites"]:
            check_surveyed(site)
            check_controlled(site, vision)
    print("Surveyed direct and routed paths, visual range, cover, threat memory and body clearance passed")
    sites = next(run["sites"] for run in fixture["runs"] if run["layout"] == "aligned")
    for run in fixture["saved_route_reference"]:
        rows = run["samples"]
        if args.saved_root:
            path = args.saved_root / run["log"]
            raw = path.read_bytes()
            check(hashlib.sha256(raw).hexdigest() == run["sha256"], f"Source log differs: {path}")
            rows = list(approach_pairs(raw.decode("utf-8-sig", errors="replace"), sites))
            check(len(rows) == run["consecutive_pairs"], f"Missing approach pairs: {path}")
        check_recorded(sites, rows)
        print(f"Seed {run['seed']}: {len(rows)} recorded mouth selections matched")
    for run in fixture["saved_sight_reference"]:
        print(f"Seed {run['seed']}: {check_sight(run['sites'])} Unreal sight traces matched")


if __name__ == "__main__":
    main()

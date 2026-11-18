"""Compare a level two-mouth refuge with Unreal's body sweeps and live position samples."""

import argparse
import json
from math import dist, hypot
from pathlib import Path


def fits_opening(body, scale, opening):
    radius = min(120., max(1., body["body_radius_cm"] * scale))
    sweep_center = max(radius + 1., body["sweep_height_cm"] * scale)
    return (2. * radius < opening["width"] and sweep_center + radius < opening["height"]
            and body["step_height_cm"] + 1. < opening["height"])


def tunnel_coordinates(point, site):
    left, right = site["mouths_cm"]
    dx, dy = right[0] - left[0], right[1] - left[1]
    length = hypot(dx, dy)
    center = [(a + b) * .5 for a, b in zip(left, right)]
    x, y, z = [a - b for a, b in zip(point, center)]
    along = (x * dx + y * dy) / length
    across = (y * dx - x * dy) / length
    return along, across, z


def position_in_tunnel(row, site):
    along, across, z = tunnel_coordinates(row["position_cm"], site)
    opening = site["opening_cm"]
    inside = abs(along) < opening["length"] / 2. and abs(across) < opening["width"] / 2. and abs(z) <= 1.
    return inside, dist((along, across, z), (0., 0., 0.))


def intersects_rectangle(start, end, bounds):
    low, high = 0., 1.
    for x, y, (lower, upper) in zip(start, end, bounds):
        if x == y:
            if not lower <= x <= upper:
                return False
            continue
        near, far = sorted(((lower - x) / (y - x), (upper - x) / (y - x)))
        low, high = max(low, near), min(high, far)
        if low > high:
            return False
    return True


def tunnel_walls(site, radius=0.):
    opening = site["opening_cm"]
    half_length = opening["length"] / 2.
    half_width = opening["width"] / 2.
    outer_edge = half_width + opening["wall_thickness"]
    # Expanded rectangles give a conservative planar sweep around the wall corners.
    along = (-half_length - radius, half_length + radius)
    return ((along, (half_width - radius, outer_edge + radius)),
            (along, (-outer_edge - radius, -half_width + radius)))


def check_approaches(site):
    opening, rat = site["opening_cm"], site["bodies"]["Rat"]
    walls = tunnel_walls(site, rat["body_radius_cm"])

    def traversable(points):
        return fits_opening(rat, 1., opening) and all(
            not intersects_rectangle(first, second, wall)
            for first, second in zip(points, points[1:]) for wall in walls)

    center = (0., 0.)
    mouths = [tunnel_coordinates(point, site)[:2] for point in site["mouths_cm"]]
    reroutes = 0
    for approach in site["rat_approaches"]:
        start = tunnel_coordinates(approach["start_cm"], site)[:2]
        direct = traversable((start, center))
        through_mouth = [traversable((start, mouth, center)) for mouth in mouths]
        if (direct, through_mouth) != (approach["direct"], approach["through_mouth"]):
            raise AssertionError(f"Site {site['site_index']}: approach sweeps differ at {start}")
        reroutes += not direct and any(through_mouth)
    return reroutes


def check_trial(run):
    sites = {site["site_index"]: site for site in run["sites"]}
    checks = 0
    reroutes = 0
    for site in sites.values():
        for species, body in site["bodies"].items():
            for scale, observed in site["crossings"][species].items():
                predicted = fits_opening(body, float(scale), site["opening_cm"])
                if [predicted, predicted] != observed:
                    raise AssertionError(f"Site {site['site_index']} {species} at scale {scale} disagrees")
                checks += len(observed)
        if "rat_approaches" in site:
            reroutes += check_approaches(site)
    targeted_arrivals = set()
    sampled_inside = set()
    for row in run["samples"]:
        site = sites[row["site_index"]]
        inside, distance = position_in_tunnel(row, site)
        if row["targeted"] and distance <= run["refuge_radius_cm"]:
            targeted_arrivals.add(row["id"])
        if inside:
            sampled_inside.add(row["id"])
    if sorted(targeted_arrivals) != run["observed_targeted_entry_ids"]:
        raise AssertionError("Targeted entry set does not match the authority samples")
    if sorted(sampled_inside) != run["observed_under_roof_ids"]:
        raise AssertionError("Positions under the roof do not match the surveyed tunnel")
    print(f"Seed {run['seed']} {run['layout']}: {checks} body sweeps, "
          f"{len(targeted_arrivals)} targeted arrivals, {len(sampled_inside)} sampled under the roof")
    if reroutes:
        print(f"  {reroutes} blocked direct approaches could reach the center through a mouth")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture["schema_version"] != 1 or not fixture.get("runs"):
        parser.error("expected Riverbank refuge samples with schema_version 1")
    for run in fixture["runs"]:
        check_trial(run)


if __name__ == "__main__":
    main()

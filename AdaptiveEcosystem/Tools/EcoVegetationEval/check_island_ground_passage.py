"""Step a measured island approach and commit forage only after regional arrival."""

import argparse
from dataclasses import dataclass
import json
from math import dist, isclose
from pathlib import Path

from check_forage_stock_parity import python_transaction


@dataclass
class PassageWorld:
    points: list
    source_region: str
    destination_region: str
    crossing_index: int
    speed_cm_s: float
    stock: float
    meal: float
    open_crossing: bool = True
    waypoint: int = 0
    offset_cm: float = 0.
    energy: float = 50.

    @property
    def region(self):
        return self.destination_region if self.waypoint >= self.crossing_index else self.source_region

    def step(self, seconds):
        remaining = seconds * self.speed_cm_s
        while remaining > 0. and self.waypoint < len(self.points) - 1:
            following = self.waypoint + 1
            if following == self.crossing_index and not self.open_crossing:
                return "blocked"
            edge = dist(self.points[self.waypoint], self.points[following])
            advance = min(remaining, edge - self.offset_cm)
            self.offset_cm += advance
            remaining -= advance
            if self.offset_cm >= edge:
                self.waypoint = following
                self.offset_cm = 0.
        return "arrived" if self.waypoint == len(self.points) - 1 else "moving"

    def eat(self):
        point = self.points[self.waypoint]
        if self.offset_cm > 0.:
            following = self.points[self.waypoint + 1]
            fraction = self.offset_cm / dist(point, following)
            point = tuple(a + (b - a) * fraction for a, b in zip(point, following))
        if self.region != self.destination_region or dist(point, self.points[-1]) > 35.:
            return 0.
        paid = min(self.stock, self.meal, 100. - self.energy)
        if paid < .2:
            return 0.
        self.stock -= paid
        self.energy += paid
        return paid


def check_case(run, scene):
    route = run["route_points_cm"]
    speed = scene["base_walk_cm_s"] * run["speed_gene"]
    patch = scene["patch"]
    world = PassageWorld(route, scene["source_region"], patch["region"], 2, speed, patch["capacity"], patch["energy_per_meal"])
    blocked = PassageWorld(route, scene["source_region"], patch["region"], 2, speed, patch["capacity"], patch["energy_per_meal"],
                           open_crossing=False)
    if not isclose(run["first_meal"]["granted_energy"], world.meal, abs_tol=1e-6):
        raise AssertionError("Unreal first meal disagrees with the authored meal cap")
    if world.eat() or blocked.step(120.) != "blocked" or blocked.eat() or blocked.stock != world.stock:
        raise AssertionError("An inaccessible patch must not pay")
    arrival, payment = None, None
    for second in range(1, 121):
        world.step(1.)
        if world.region == patch["region"] and arrival is None:
            arrival = second
        payment = world.eat()
        if payment:
            break
    observed_arrival = run["arrival"]["game_seconds"]
    observed_payment = run["first_meal"]["game_seconds"]
    if (arrival is None or payment != world.meal or not isclose(world.stock + payment, patch["capacity"])
            or not isclose(world.energy - 50., payment) or not arrival < second or not observed_arrival < observed_payment):
        raise AssertionError("Expected crossing before payment, with matching stock and energy")
    print(f"Seed {run['seed']}: crossing {arrival}s, first payment {second}s, paid {payment:.3f}; "
          f"Unreal crossing {observed_arrival}s, payment {observed_payment}s")


def check_recovering_patch(run, scene, authored_patch):
    patch = scene["patch"]
    recipe = (patch["capacity"], authored_patch["regrowth_per_second"], authored_patch["plant_dry_loss_per_second"],
              authored_patch["plant_moisture_need"], patch["energy_per_meal"],
              *authored_patch["plant_growth_temperature"], *authored_patch["plant_growth_rainfall"])
    starting_stock = .25

    def trial(soil_moisture):
        world = PassageWorld(run["route_points_cm"], scene["source_region"], patch["region"], 2,
                             scene["base_walk_cm_s"] * run["speed_gene"], starting_stock, patch["energy_per_meal"])
        for second in range(1, 121):
            # Match the order: update the patch, then settle the meal at this step.
            world.stock = python_transaction(14., .66, .72, soil_moisture, world.stock, 1., (), recipe)[-1]
            if world.step(1.) == "arrived":
                available = world.stock
                before = world.energy
                paid = world.eat()
                if not isclose(available, world.stock + paid) or not isclose(before + paid, world.energy):
                    raise AssertionError("Patch and energy must reconcile at the same arrival")
                return second, paid, world.stock
        raise AssertionError("No arrival on the open passage")

    dry = trial(.10)
    moist = trial(.55)
    if dry[0] != moist[0] or not 0. <= dry[1] < moist[1] <= patch["energy_per_meal"]:
        raise AssertionError("Soil moisture alone should change the meal at a matched arrival")
    print(f"Seed {run['seed']}: same arrival {dry[0]}s, dry paid {dry[1]:.3f} with {dry[2]:.3f} remaining, "
          f"moist paid {moist[1]:.3f} with {moist[2]:.3f} remaining")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--patch-inputs", type=Path, help="Use the authored patch settings in the 60-minute baseline")
    args = parser.parse_args()
    scene = json.loads(args.fixture.read_text(encoding="utf-8"))["ground_passage_reference"]
    for run in scene["runs"]:
        check_case(run, scene)
    if args.patch_inputs:
        baseline = json.loads(args.patch_inputs.read_text(encoding="utf-8"))
        patch = baseline["initial_patch_inputs"]["patches"]["IslandTransitionForbs"]
        for run in scene["runs"]:
            check_recovering_patch(run, scene, patch)


if __name__ == "__main__":
    main()

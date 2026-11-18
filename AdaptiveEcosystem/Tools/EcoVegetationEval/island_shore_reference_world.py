"""Execute shoreline movement and feeding against a shared forage stock."""

from dataclasses import dataclass
from math import dist

from check_river_rat_refuge import intersects_rectangle
from check_water_access_parity import swim_center_bounds


def step_toward(position, goal, max_distance):
    length = dist(position, goal)
    if length <= max_distance:
        return tuple(goal)
    return tuple(a + (b - a) * max_distance / length for a, b in zip(position, goal))


def swim_step(position, goal, speed, current, next_water_column, clearance, seconds):
    """Integrate one unobstructed stroke with sampled flow and depth limits."""
    propelled = step_toward(position, goal, speed * seconds)
    x, y, z = (point + flow * seconds for point, flow in zip(propelled, current))
    bottom, surface = next_water_column
    if swim_center_bounds(bottom, surface, clearance) is None:
        return None
    padding = min(clearance + .35, (surface - bottom) * .5)
    return x, y, max(bottom + padding, min(z, surface - padding))


@dataclass
class ShoreAnimal:
    position: str
    wade_depth_cm: float
    energy: float
    max_energy: float


class ShoreForageWorld:
    """Use explicit ground connections and finite stock for a single plant patch."""

    def __init__(self, points, connections, access_points, surface_z_cm, stock, meal_cap):
        self.points = points
        self.connections = {frozenset(edge) for edge in connections}
        self.access_points = tuple(access_points)
        self.surface_z_cm = surface_z_cm
        self.stock = stock
        self.meal_cap = meal_cap

    def wadeable(self, animal, node):
        depth = self.surface_z_cm - self.points[node][2]
        return depth <= animal.wade_depth_cm

    def move(self, animal, destination):
        edge = frozenset((animal.position, destination))
        if edge not in self.connections:
            return "no_connection"
        if not self.wadeable(animal, animal.position) or not self.wadeable(animal, destination):
            return "blocked_depth"
        animal.position = destination
        return "arrived"

    def eat(self, animal, access_point):
        if access_point not in self.access_points or not self.wadeable(animal, access_point):
            return "ineligible", 0.
        if dist(self.points[animal.position], self.points[access_point]) > 35.:
            return "outside_reach", 0.
        payment = min(self.stock, self.meal_cap, animal.max_energy - animal.energy)
        if payment < .2:
            return "below_minimum", 0.
        self.stock -= payment
        animal.energy += payment
        return "paid", payment


@dataclass(frozen=True)
class SwimExit:
    name: str
    entry: tuple
    bank: tuple
    column: tuple | None

    def entry_at_depth(self, clearance):
        bounds = swim_center_bounds(*self.column, clearance) if self.column is not None else None
        if bounds is None:
            return None
        return (*self.entry[:2], max(bounds[0], min(self.entry[2], bounds[1])))


class MinkReturnWorld:
    """Reduced water-to-land route model using measured exits and constant current."""

    stamina_per_second = .025

    def __init__(self, position, clearance, swim_speed, current, stamina, exits):
        self.position = tuple(position)
        self.clearance = clearance
        self.swim_speed = swim_speed
        self.current = tuple(current)
        self.stamina = stamina
        self.exits = tuple(exits)
        self.phase = "swimming"
        self.target = None

    def progress_speed(self, destination):
        length = dist(self.position, destination)
        if length == 0.:
            return self.swim_speed
        projected_flow = sum(flow * (b - a) / length
                             for flow, a, b in zip(self.current, self.position, destination))
        return max(0., self.swim_speed + projected_flow)

    def choose_exit(self, surface_cm, cover=()):
        if self.phase != "swimming":
            raise ValueError("Only a swimming mink can select a water exit")
        best_distance = float("inf")
        self.target = None
        candidates = {}
        for exit_point in self.exits:
            if exit_point.bank[2] < surface_cm:
                candidates[exit_point.name] = "Shore"
                continue
            entry = exit_point.entry_at_depth(self.clearance)
            if entry is None:
                candidates[exit_point.name] = "Depth"
                continue
            distance = dist(self.position, entry)
            if distance >= best_distance:
                candidates[exit_point.name] = "Farther"
                continue
            if any(intersects_rectangle(self.position, entry, obstacle) for obstacle in cover):
                candidates[exit_point.name] = "Occluded"
                continue
            budget = self.progress_speed(entry) * self.stamina / self.stamina_per_second
            if max(0., distance - 10.) > budget:
                candidates[exit_point.name] = "Stamina"
                continue
            candidates[exit_point.name] = "Clear"
            best_distance = distance
            self.target = (exit_point, entry)
        return candidates

    def swim_toward_exit(self, seconds):
        if self.target is None or self.phase != "swimming":
            return
        _, entry = self.target
        distance = dist(self.position, entry)
        speed = self.progress_speed(entry)
        available_seconds = min(seconds, self.stamina / self.stamina_per_second)
        travel = min(max(0., distance - 10.), speed * available_seconds)
        if travel > 0.:
            progress = travel / distance
            self.position = tuple(a + (b - a) * progress for a, b in zip(self.position, entry))
            self.stamina = max(0., self.stamina - travel / speed * self.stamina_per_second)
        if dist(self.position, entry) <= 10. + 1e-9:
            self.phase = "exiting"

    def land(self, surface_cm):
        if self.phase != "exiting":
            return False
        exit_point, _ = self.target
        if exit_point.bank[2] < surface_cm:
            self.phase = "swimming"
            self.target = None
            return False
        self.position = exit_point.bank
        self.phase = "ground"
        return True

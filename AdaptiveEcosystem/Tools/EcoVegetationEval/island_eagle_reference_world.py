"""Step an eagle dive and resolve moving prey at contact time."""

from dataclasses import dataclass
from math import dist


def intersects_sphere(start, end, center, radius):
    direction = tuple(b - a for a, b in zip(start, end))
    length_squared = sum(axis * axis for axis in direction)
    fraction = 0.
    if length_squared:
        projection = sum((c - a) * axis for a, c, axis in zip(start, center, direction))
        fraction = max(0., min(1., projection / length_squared))
    closest = tuple(a + fraction * axis for a, axis in zip(start, direction))
    return dist(closest, center) <= radius


@dataclass(frozen=True)
class BoxObstacle:
    center: tuple
    half_extent: float
    physical: bool

    def intersects(self, start, end, radius=0.):
        """Find the minimum squared distance from a segment to the box."""
        axes = tuple((a - c, b - a) for a, b, c in zip(start, end, self.center))
        lower, upper = -self.half_extent, self.half_extent
        knots = {0., 1.}
        for start_axis, delta in axes:
            if delta:
                for bound in (lower, upper):
                    t = (bound - start_axis) / delta
                    if 0. < t < 1.:
                        knots.add(t)

        def distance_sq(t):
            return sum(max(0., abs(a + v * t) - self.half_extent) ** 2 for a, v in axes)

        points = sorted(knots)
        if any(distance_sq(t) <= radius ** 2 for t in points):
            return True
        for left, right in zip(points, points[1:]):
            midpoint = (left + right) / 2.
            outside = []
            for a, v in axes:
                coordinate = a + v * midpoint
                if coordinate < lower:
                    outside.append((a - lower, v))
                elif coordinate > upper:
                    outside.append((a - upper, v))
            coefficient = sum(v * v for _, v in outside)
            if coefficient:
                minimum = -sum(a * v for a, v in outside) / coefficient
                if left < minimum < right and distance_sq(minimum) <= radius ** 2:
                    return True
        return False


@dataclass
class Rat:
    position: tuple
    mass_ratio: float
    carcass_energy: float
    alive: bool = True


@dataclass
class LandedCarcass:
    position: tuple
    remaining: float
    open_at: float
    expires_at: float
    exclusive_until: float
    killer: int
    places: int
    reset_at: float = 0.
    used_places: int = 0

    def debit(self, requested):
        """Debit shared stock after an authorized feeding action."""
        amount = min(self.remaining, max(0., requested))
        self.remaining -= amount
        return amount

    def bite(self, now, agent, position, *, grounded, stopped, clear, reach, requested):
        if (not grounded or not stopped or not clear or dist(position, self.position) > reach
                or not self.open_at <= now < self.expires_at
                or now < self.exclusive_until and agent != self.killer
                or self.remaining <= 0. or requested <= 0.):
            return 0.
        if now >= self.reset_at:
            self.reset_at = now + 1.
            self.used_places = 0
        if self.used_places >= self.places:
            return 0.
        self.used_places += 1
        return self.debit(requested)


class EagleDiveWorld:
    """Resolve one dive using the island profile's speed, reach and windup."""

    reach_cm = 95.
    sight_range_cm = 3200.
    cruise_height_cm = 2300.
    flight_speed_cm_s = 900.
    windup_s = .10
    rat_mass_limit = .35
    meal_cap = 5.

    def __init__(self, position, rat, *, obstacles=(), boxes=(), sweep_radius_cm=10.8,
                 eye_cm=35., prey_eye_cm=5.):
        self.position = position
        self.rat = rat
        self.obstacles = obstacles
        self.boxes = boxes
        self.sweep_radius_cm = sweep_radius_cm
        self.eye_cm = eye_cm
        self.prey_eye_cm = prey_eye_cm
        self.phase = "cruise"
        self.time_s = 0.
        self.contact_at = None
        self.carcass_stock = 0.

    def visible(self):
        x, y, z = self.position
        tx, ty, tz = self.rat.position
        start, end = (x, y, z + self.eye_cm), (tx, ty, tz + self.prey_eye_cm)
        return not (any(intersects_sphere(start, end, center, radius) for center, radius in self.obstacles)
                    or any(box.intersects(start, end) for box in self.boxes))

    def request_dive(self):
        if self.phase != "cruise" or not self.rat.alive:
            return "unavailable"
        if self.rat.mass_ratio > self.rat_mass_limit:
            return "size"
        height = self.position[2] - self.rat.position[2]
        if not self.reach_cm <= height <= self.cruise_height_cm:
            return "height"
        if dist(self.position, self.rat.position) > self.sight_range_cm:
            return "range"
        if not self.visible():
            return "occluded"
        self.phase = "dive"
        return "diving"

    def step(self, delta_s, rat_position):
        if delta_s <= 0.:
            raise ValueError("delta_s must advance simulation time")
        self.time_s += delta_s
        self.rat.position = rat_position
        if self.phase == "windup":
            if self.time_s + 1e-9 < self.contact_at:
                return "windup"
            self.phase = "landing"
            if not self.rat.alive:
                return "unavailable"
            if dist(self.position, rat_position) > self.reach_cm:
                return "miss_range"
            if not self.visible():
                return "miss_occluded"
            self.rat.alive = False
            self.carcass_stock = self.rat.carcass_energy
            return "captured"
        if self.phase != "dive":
            return self.phase
        if not self.rat.alive or not self.visible():
            self.phase = "landing"
            return "dive_cancelled"
        x, y, z = rat_position
        contact = (x, y, z + .38 * self.reach_cm)
        distance = dist(self.position, contact)
        fraction = min(1., self.flight_speed_cm_s * delta_s / distance) if distance else 1.
        destination = tuple(a + fraction * (b - a) for a, b in zip(self.position, contact))
        if (any(intersects_sphere(self.position, destination, center, radius + self.sweep_radius_cm)
                for center, radius in self.obstacles)
                or any(box.physical and box.intersects(self.position, destination, self.sweep_radius_cm)
                       for box in self.boxes)):
            self.phase = "landing"
            return "dive_blocked"
        self.position = destination
        if dist(destination, rat_position) <= self.reach_cm and self.visible():
            self.phase = "windup"
            self.contact_at = self.time_s + self.windup_s
            return "queued"
        return "diving"

    def eat_at_carcass(self, energy_headroom):
        """Pay a meal after arrival at the carcass in the reference scene."""
        payment = max(0., min(energy_headroom, self.meal_cap, self.carcass_stock))
        self.carcass_stock -= payment
        return payment

    def descend_to_clear_ground(self, ground_z, delta_s):
        """Advance a vertical landing once the bird is above a clear ground point."""
        if self.phase != "landing" or delta_s <= 0. or ground_z > self.position[2]:
            raise ValueError("Expected a landing above the ground with a positive time step")
        x, y, z = self.position
        next_z = max(ground_z, z - self.flight_speed_cm_s * .65 * delta_s)
        if next_z <= ground_z + 2.:
            self.position = x, y, ground_z
            self.phase = "grounded"
        else:
            self.position = x, y, next_z

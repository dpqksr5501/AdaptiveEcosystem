"""Experimental step-driven water-grid environment for Unreal comparison scenes."""

from dataclasses import dataclass, replace
from math import dist, floor

from check_water_access_parity import GRID_MOVES, connected_cells, submerged, swim_center_bounds, water_grid_predecessors


@dataclass
class FoodPatch:
    cell: tuple
    height_above_bottom_cm: float
    capacity: float
    regrowth_per_step: float
    meal_cap: float
    stock: float
    extra_points: tuple = ()
    rainfall_driven: bool = False
    full_growth_depth_cm: float = 0.
    dry_loss_per_second: float = 0.

    def access_points(self):
        return ((self.cell, self.height_above_bottom_cm), *self.extra_points)

    def regrow(self, *, main_depth_cm, elapsed, rainfall):
        before = self.stock
        if self.full_growth_depth_cm > 0.:
            if main_depth_cm is None:
                return 0.
            inundation = main_depth_cm - self.height_above_bottom_cm
            rate = -self.dry_loss_per_second
            if inundation > 0. and self.height_above_bottom_cm > 0.:
                rate = self.regrowth_per_step * min(1., inundation / self.full_growth_depth_cm)
        elif self.rainfall_driven:
            rate = self.regrowth_per_step * (.75 + .5 * min(1., max(0., rainfall)))
        else:
            submerged_main = main_depth_cm is not None and 0. < self.height_above_bottom_cm < main_depth_cm
            rate = self.regrowth_per_step if submerged_main else 0.
        self.stock = max(0., min(self.capacity, before + elapsed * rate))
        return self.stock - before


@dataclass(frozen=True)
class FoodTarget:
    patch: str
    access_index: int


RETREAT_DIRECTIONS = ("east", "west", "north", "south")
RETREAT_PROBE_CM = 18.


def water_meal_geometry(position, meal_point, agent_column, meal_column):
    """Check the runtime patch-meal geometry before sight and payment."""
    for column in (agent_column, meal_column):
        if column is None or swim_center_bounds(*column, 1.) is None:
            return False
    return (agent_column[0] <= position[2] <= agent_column[1]
            and submerged(*meal_column, meal_point[2]) and dist(position, meal_point) <= 35.)


def water_patch_payment(position, point, agent_column, meal_column, *, still, clear_sight, stock, meal_cap, headroom):
    """Resolve one selected aquatic patch after authority and hunger eligibility."""
    candidate = min(stock, meal_cap, headroom)
    if (not still or not clear_sight or candidate < .2
            or not water_meal_geometry(position, point, agent_column, meal_column)):
        return 0., stock
    return candidate, stock - candidate


def shallow_water_retreat(position, clearance, walk_speed, condition, delta, water_column_at, can_sweep):
    """Replay the horizontal recovery step when the current column cannot fit the body."""
    column = water_column_at(position)
    if column is not None and swim_center_bounds(*column, clearance) is not None:
        return position
    budget = min(RETREAT_PROBE_CM, walk_speed * min(delta, .1) * condition)
    best = position
    best_depth = 0.
    for direction in RETREAT_DIRECTIONS:
        dx, dy = GRID_MOVES[direction]
        x, y, z = position
        nearby = water_column_at((x + dx * RETREAT_PROBE_CM, y + dy * RETREAT_PROBE_CM, z))
        if nearby is None or swim_center_bounds(*nearby, clearance + .35) is None:
            continue
        depth = nearby[1] - nearby[0]
        end = x + dx * budget, y + dy * budget, z
        if depth > best_depth and can_sweep(position, end, max(.5, clearance - .2)):
            best, best_depth = end, depth
    return best


@dataclass(frozen=True)
class NurserySite:
    elevation_cm: float


@dataclass(frozen=True)
class NurseryReservation:
    site: str
    parents: tuple
    due_at: float


class NurseryLedger:
    """Track continuous immersion and birth eligibility for authored nursery points."""

    def __init__(self, sites):
        self.sites = dict(sites)
        self.pending = {}
        self.accepted_ids = set()
        self.parent_retry_at = {}
        self.now = float("-inf")

    def reserve(self, reservation_id, site, parents, now, due_at, column):
        if (now < self.now or due_at < now or reservation_id in self.accepted_ids
                or len(parents) != 2 or parents[0] == parents[1]):
            raise ValueError("Invalid nursery reservation")
        self.now = now
        if column is None or not submerged(*column, self.sites[site].elevation_cm):
            return False
        if any(now < self.parent_retry_at.get(parent, now) or any(
                parent in reservation.parents for reservation in self.pending.values()) for parent in parents):
            return False
        self.pending[reservation_id] = NurseryReservation(site, tuple(parents), due_at)
        self.accepted_ids.add(reservation_id)
        return True

    def update(self, now, columns):
        if now < self.now:
            raise ValueError("Nursery time moved backward")
        self.now = now
        events = {}
        for key, reservation in tuple(self.pending.items()):
            if now > reservation.due_at + 20.:
                events[key] = "expired"
            elif reservation.site in columns:
                column = columns[reservation.site]
                if column is None or not submerged(*column, self.sites[reservation.site].elevation_cm):
                    events[key] = "interrupted"
                    for parent in reservation.parents:
                        self.parent_retry_at[parent] = max(self.parent_retry_at.get(parent, now), now + 30.)
                elif now >= reservation.due_at:
                    events[key] = "hatch_eligible"
        for key in events:
            del self.pending[key]
        return events


class WaterGridWorld:
    """Execute one animal's movement and meals using sampled depths and patch stock."""

    def __init__(self, depths, start, clearance_cm, patches, energy, max_energy):
        self.depths = dict(depths)
        self.cell = start
        self.clearance_cm = clearance_cm
        self.patches = dict(patches)
        self.energy = energy
        self.max_energy = max_energy
        if not self.passable(start):
            raise ValueError("Start needs enough water for the body")

    def passable(self, cell):
        return swim_center_bounds(0., self.depths.get(cell, 0.), self.clearance_cm) is not None

    def route_to(self, goal):
        """Plan grid movement to a known waypoint; this does not reveal food to the animal."""
        passable = {cell for cell in self.depths if self.passable(cell)}
        previous = water_grid_predecessors(self.cell, passable, goal)
        if goal not in previous:
            return None
        route = []
        while goal != self.cell:
            goal, action = previous[goal]
            route.append(action)
        return tuple(reversed(route))

    def local_food_points(self, patch):
        if not self.passable(self.cell):
            return ()
        return tuple(index for index, (cell, height) in enumerate(patch.access_points())
                     if self.cell == cell and 0 < height < self.depths[cell])

    def reachable_food(self, patch):
        return bool(self.local_food_points(patch))

    def select_food(self, sense_range_cm, walk_speed_cm_s, grid_cm):
        target = self.select_food_target(sense_range_cm, walk_speed_cm_s, grid_cm)
        return target.patch if target else None

    def select_food_target(self, sense_range_cm, walk_speed_cm_s, grid_cm):
        """Rank submerged forage connected by water within the sensing radius."""
        x, y = self.cell
        radius = floor(sense_range_cm / grid_cm)
        passable = {(x + dx, y + dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)
                    if grid_cm * dist((0, 0), (dx, dy)) <= sense_range_cm and self.passable((x + dx, y + dy))}
        connected = connected_cells(self.cell, passable)
        best = None
        best_score = 0.
        for name, patch in self.patches.items():
            if patch.stock < .2:
                continue
            for index, (cell, height) in enumerate(patch.access_points()):
                distance_cm = grid_cm * dist(self.cell, cell)
                if cell not in connected or not 0 < height < self.depths[cell]:
                    continue
                score = min(patch.stock, patch.meal_cap) / (1. + distance_cm / walk_speed_cm_s)
                if score > best_score:
                    best, best_score = FoodTarget(name, index), score
        return best

    def observe(self):
        x, y = self.cell
        nearby_depth = {name: self.depths.get((x + dx, y + dy), 0.) for name, (dx, dy) in GRID_MOVES.items()}
        return {"depth_cm": self.depths.get(self.cell, 0.), "adjacent_depth_cm": nearby_depth,
                "energy": self.energy,
                "local_food": {name: patch.stock for name, patch in self.patches.items() if self.reachable_food(patch)}}

    def observe_foraging(self, sense_range_cm, walk_speed_cm_s, grid_cm):
        observation = self.observe()
        target = self.select_food_target(sense_range_cm, walk_speed_cm_s, grid_cm)
        observation["detected_food"] = None
        if target:
            (x, y), _ = self.patches[target.patch].access_points()[target.access_index]
            observation["detected_food"] = (target, (x - self.cell[0], y - self.cell[1]))
        return observation

    def set_depths(self, depths):
        """Apply a new depth field before the next decision."""
        self.depths = dict(depths)

    def step(self, action, target=None):
        if action not in GRID_MOVES and action not in {"wait", "eat"}:
            raise ValueError(f"Unknown water action: {action}")
        growth = self.advance_growth()
        outcome, amount = self.apply_action(action, target)
        return {"outcome": outcome, "amount": amount, "growth": growth, "observation": self.observe()}

    def advance_growth(self, *, elapsed=1., rainfall=0.):
        growth = {}
        for name, patch in self.patches.items():
            growth[name] = patch.regrow(main_depth_cm=self.depths.get(patch.cell), elapsed=elapsed, rainfall=rainfall)
        return growth

    def apply_action(self, action, target):
        outcome = "wait"
        amount = 0.
        if action in GRID_MOVES:
            x, y = self.cell
            dx, dy = GRID_MOVES[action]
            destination = x + dx, y + dy
            outcome = "blocked_depth"
            if self.passable(self.cell) and self.passable(destination):
                self.cell = destination
                outcome = "moved"
        elif action == "eat":
            requested_point = isinstance(target, FoodTarget)
            name = target.patch if requested_point else target
            patch = self.patches.get(name)
            outcome = "inaccessible"
            local = self.local_food_points(patch) if patch is not None else ()
            if local and (not requested_point or target.access_index in local):
                candidate = min(patch.stock, patch.meal_cap, self.max_energy - self.energy)
                outcome = "below_minimum"
                if candidate >= .2:
                    patch.stock -= candidate
                    self.energy += candidate
                    amount = candidate
                    outcome = "paid"
        return outcome, amount


class SharedWaterForaging:
    """Step several swimmers against one stock ledger in a fixed authority order."""

    def __init__(self, depths, patches, swimmers):
        if not swimmers:
            raise ValueError("A shared water scene needs at least one swimmer")
        self.patches = {name: replace(patch) for name, patch in patches.items()}
        self.swimmers = {
            agent: WaterGridWorld(depths, start, clearance, self.patches, energy, max_energy)
            for agent, (start, clearance, energy, max_energy) in swimmers.items()
        }

    def set_depths(self, depths):
        for world in self.swimmers.values():
            world.set_depths(depths)

    def step(self, requests, *, elapsed=1., rainfall=0.):
        if requests.keys() != self.swimmers.keys():
            raise ValueError("Supply one request per swimmer and step")
        if any(action not in GRID_MOVES and action not in {"wait", "eat"} for action, _ in requests.values()):
            raise ValueError("Unknown water action")
        if elapsed < 0.:
            raise ValueError("Water growth cannot run backward")
        growth = next(iter(self.swimmers.values())).advance_growth(elapsed=elapsed, rainfall=rainfall)
        results = {agent: world.apply_action(*requests[agent]) for agent, world in self.swimmers.items()}
        return {"growth": growth, "results": results,
                "observations": {agent: world.observe() for agent, world in self.swimmers.items()}}


class WaterForagingEpisode:
    """Resettable reference episode with depth changes applied before the affected decision."""

    def __init__(self, depth_schedule, start, clearance, patches, energy, max_energy, *,
                 sense_range, walk_speed, grid_cm, max_steps):
        if max_steps < 1 or 0 not in depth_schedule or any(step < 0 or step > max_steps for step in depth_schedule):
            raise ValueError("Depth schedule must start at zero and fit within the episode horizon")
        self.depth_schedule = {step: dict(depths) for step, depths in depth_schedule.items()}
        self.start = start
        self.clearance = clearance
        self.patches = {name: replace(patch) for name, patch in patches.items()}
        self.energy = energy
        self.max_energy = max_energy
        self.sense_range = sense_range
        self.walk_speed = walk_speed
        self.grid_cm = grid_cm
        self.max_steps = max_steps
        self.reset()

    def reset(self):
        self.steps = 0
        self.world = WaterGridWorld(self.depth_schedule[0], self.start, self.clearance,
                                    {name: replace(patch) for name, patch in self.patches.items()},
                                    self.energy, self.max_energy)
        return self.observe()

    def observe(self):
        return self.world.observe_foraging(self.sense_range, self.walk_speed, self.grid_cm)

    def step(self, action, target=None):
        if self.steps >= self.max_steps:
            raise RuntimeError("Reset the water episode before taking another action")
        result = self.world.step(action, target)
        self.steps += 1
        if self.steps in self.depth_schedule:
            self.world.set_depths(self.depth_schedule[self.steps])
        result["observation"] = self.observe()
        result["truncated"] = self.steps == self.max_steps
        return result

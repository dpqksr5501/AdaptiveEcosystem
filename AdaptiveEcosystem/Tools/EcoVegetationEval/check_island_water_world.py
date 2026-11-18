"""Run actions on Unreal depth samples using controlled body and stock inputs."""

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

from check_water_access_parity import GRID_MOVES, swim_center_bounds
from island_water_reference_world import FoodPatch, FoodTarget, NurseryLedger, NurserySite, WaterGridWorld
from island_water_reference_world import SharedWaterForaging, WaterForagingEpisode, shallow_water_retreat


def depths(survey):
    return {(x, y): depth for x, y, depth in survey["depth_grid"]["samples"]}


def check_body_clearance(low, high, species, start, move):
    small = low["species"][species]["0.75"]["clearance_cm"]
    adult = low["species"][species]["1.0"]["clearance_cm"]
    for survey, clearance, expected in ((low, small, "moved"), (low, adult, "blocked_depth"),
                                        (high, adult, "moved")):
        world = WaterGridWorld(depths(survey), start, clearance, {}, energy=0., max_energy=3.)
        result = world.step(move)
        if result["outcome"] != expected or (world.cell == start) != (expected == "blocked_depth"):
            raise AssertionError(f"{species}: expected {expected}")


def check_body_clearance_during_retreat(high, receded, species, start, move):
    dx, dy = GRID_MOVES[move]
    shelf = start[0] + dx, start[1] + dy
    return_move = {"east": "west", "south": "north"}[move]
    high_depths, low_depths = depths(high), depths(receded)
    low_depth = low_depths[shelf]
    meals = {}
    for size, profile in receded["species"][species].items():
        clearance = profile["clearance_cm"]
        target = FoodTarget("shelf", 0)
        patch = FoodPatch(shelf, low_depth / 2., 2., 0., .5, 2.)
        world = WaterGridWorld(high_depths, start, clearance, {"shelf": patch}, 0., 2.)
        if world.step(move)["outcome"] != "moved" or world.cell != shelf:
            raise AssertionError(f"{species} {size}: the high water should let the animal enter the shelf")

        world.set_depths(low_depths)
        fits = size == "0.75"
        local = world.observe_foraging(0., 52., high["grid_cm"])
        paid = world.step("eat", target)
        if ((local["detected_food"] is not None) != fits or paid["amount"] != (.5 if fits else 0.)
                or patch.stock + world.energy != 2.):
            raise AssertionError(f"{species} {size}: changed depth did not gate the same submerged stock")
        retreat = world.step(return_move)
        if retreat["outcome"] != ("moved" if fits else "blocked_depth") or world.cell != (start if fits else shelf):
            raise AssertionError(f"{species} {size}: unexpected retreat after drawdown")
        meals[size] = paid["amount"]
        world.set_depths(high_depths)
        if not fits and world.step(return_move)["outcome"] != "moved":
            raise AssertionError(f"{species} {size}: restored water should permit retreat")
        if world.cell != start or world.step("eat", target)["amount"]:
            raise AssertionError("Retreat must not leave a payable stale request for the shelf")
    print(f"{species}: receded shelf depth {low_depth:.3f} cm; meals by body scale {meals}")


def check_flood_food(low, high, receded):
    start, food_cell = (32, 37), (31, 37)
    clearance = low["species"]["CommonCarp"]["1.0"]["clearance_cm"]
    patch = FoodPatch(food_cell, height_above_bottom_cm=10., capacity=1., regrowth_per_step=.125,
                      meal_cap=.75, stock=.5)
    world = WaterGridWorld(depths(low), start, clearance, {"margin": patch}, energy=.5, max_energy=3.)
    if world.step("west")["outcome"] != "blocked_depth" or world.step("eat", "margin")["amount"] != 0.:
        raise AssertionError("Low water should block both swimming to and eating the resource")
    world.set_depths(depths(high))
    move = world.step("west")
    if move["outcome"] != "moved" or move["observation"]["local_food"] != {"margin": .625}:
        raise AssertionError("Flood should open the route and expose the local stock")
    for expected in ("paid", "below_minimum"):
        before = patch.stock
        result = world.step("eat", "margin")
        if result["outcome"] != expected or not math.isclose(before + result["growth"]["margin"],
                                                            patch.stock + result["amount"]):
            raise AssertionError("Food stock and energy payment disagree")
    world.set_depths(depths(receded))
    if world.observe()["local_food"] or world.step("eat", "margin")["amount"] != 0.:
        raise AssertionError("Recession should remove access to the margin")
    if world.energy != 1.25 or patch.stock != .125:
        raise AssertionError("Only the single successful meal should change animal energy")
    return world.energy


def check_flood_food_switch(low, high, receded):
    grid_cm = low["grid_cm"]
    profile = low["species"]["CommonCarp"]["1.0"]
    food_range = profile["nominal_food_range_cm"]["day"]
    bank = FoodPatch((31, 37), 10., 1., 0., .75, .75)
    channel = FoodPatch((33, 37), 10., 1., 0., .75, .5)
    world = WaterGridWorld(depths(low), (32, 37), profile["clearance_cm"], {"bank": bank, "channel": channel}, .5, 3.)

    def choice():
        return world.select_food(food_range, walk_speed_cm_s=52., grid_cm=grid_cm)

    if choice() != "channel":
        raise AssertionError("Dry bank should leave the channel food as the available choice")
    world.set_depths(depths(high))
    if choice() != "bank" or world.step("west")["outcome"] != "moved":
        raise AssertionError("Floodwater should open the richer bank food")
    if world.step("eat", "bank")["amount"] != .75 or choice() != "channel":
        raise AssertionError("The bank meal should deplete the patch and change the next choice")
    world.set_depths(depths(receded))
    if choice() is not None or world.step("east")["outcome"] != "blocked_depth":
        raise AssertionError("Recession should disconnect a fish left on the shallow margin")
    world.set_depths(depths(high))
    if choice() != "channel" or world.step("east")["outcome"] != "moved":
        raise AssertionError("Rising water should reconnect the route")
    if world.step("east")["outcome"] != "moved" or world.step("eat", "channel")["amount"] != .5:
        raise AssertionError("The fish should reach and eat the connected fallback resource")


def check_resettable_forage_episode(low, high, receded):
    start, bank, channel = (32, 37), (31, 37), (33, 37)
    profile = low["species"]["CommonCarp"]["1.0"]
    patches = {"bank": FoodPatch(bank, 10., 1., 0., .75, .75),
               "channel": FoodPatch(channel, 10., 1., 0., .75, .5)}
    actions = (
        ("wait", None), ("west", None), ("eat", FoodTarget("bank", 0)),
        ("east", None), ("wait", None), ("east", None),
        ("east", None), ("eat", FoodTarget("channel", 0)),
    )
    episode = WaterForagingEpisode({0: depths(low), 1: depths(high), 3: depths(receded), 5: depths(high)},
                                   start, profile["clearance_cm"], patches, .5, 3.,
                                   sense_range=profile["nominal_food_range_cm"]["day"], walk_speed=52.,
                                   grid_cm=low["grid_cm"], max_steps=len(actions))
    initial = episode.observe()
    trace = [episode.step(action, target) for action, target in actions]
    if [row["outcome"] for row in trace] != ["wait", "moved", "paid", "blocked_depth", "wait", "moved", "moved", "paid"]:
        raise AssertionError("Expected flooding, local depletion, drawdown block, and resumed access in order")
    if (initial["detected_food"][0].patch != "channel" or trace[0]["observation"]["detected_food"][0].patch != "bank"
            or trace[2]["observation"]["detected_food"] is not None
            or trace[-1]["observation"]["energy"] != 1.75 or not trace[-1]["truncated"]
            or any(row["truncated"] for row in trace[:-1])):
        raise AssertionError("The next observation must include current water and depletion before the next action")
    try:
        episode.step("wait")
    except RuntimeError:
        pass
    else:
        raise AssertionError("The ended episode must require a reset")
    if episode.reset() != initial or [episode.step(action, target) for action, target in actions] != trace:
        raise AssertionError("Reset must restore initial water, position, energy, stocks, and clock")
    print("Resettable carp episode: feed, drawdown, retry and exact replay matched")


def check_seasonal_food_stock():
    # Inputs and expected balances from AdaptiveEcosystem.Fauna.Water.SeasonalFoodStock.
    slot = (0, 0)
    patch = FoodPatch(slot, 30., 10., 1., 2., 0., full_growth_depth_cm=20., dry_loss_per_second=.5)
    world = SharedWaterForaging({slot: 20.}, {"shelf": patch}, {1: (slot, 3., 0., 20.), 2: (slot, 3., 0., 20.)})
    stock = world.patches["shelf"]
    waits = {1: ("wait", None), 2: ("wait", None)}
    previous = 0.
    for at, water_depth, expected in ((2., 20., 0.), (6., 40., 2.), (8., 50., 4.), (8., 50., 4.),
                                       (10., 20., 3.), (30., 20., 0.), (45., 50., 10.)):
        world.set_depths({slot: water_depth})
        before = stock.stock
        result = world.step(waits, elapsed=at - previous)
        if stock.stock != expected or result["growth"]["shelf"] != expected - before:
            raise AssertionError(f"Unexpected shared seasonal shelf stock at {at:g}s")
        for observation in result["observations"].values():
            if ("shelf" in observation["local_food"]) != (water_depth > 30.):
                raise AssertionError("An exposed shelf must hide the remaining stock from local foraging")
        previous = at
    world.set_depths({})
    if world.step(waits, elapsed=5.)["growth"]["shelf"] != 0. or stock.stock != 10.:
        raise AssertionError("Missing water probe must not be interpreted as measured exposure")
    world.set_depths({slot: 50.})
    requests = {agent: ("eat", FoodTarget("shelf", 0)) for agent in waits}
    result = world.step(requests, elapsed=0.)
    if result["results"] != {1: ("paid", 2.), 2: ("paid", 2.)} or stock.stock != 6.:
        raise AssertionError("Reinundated shelf must pay both swimmers from the recovered stock")
    print("Seasonal shelf: seven Unreal stock balances matched, then the recovered stock paid two swimmers")


def check_sensing_ignores_distant_connection():
    start, target = (0, 0), (2, 0)
    shore = {(0, 0): 20., (2, 0): 20., (0, 1): 20., (2, 1): 20.}
    outside_range = {(x, 2): 20. for x in range(3)}
    patch = FoodPatch(target, 10., 2., 0., .5, 2.)
    world = WaterGridWorld(shore, start, 3., {"probe": patch}, 0., 2.)
    initial = world.observe_foraging(200., 52., 100.)
    if initial["detected_food"] is not None or world.route_to(target) is not None:
        raise AssertionError("Expected disconnected water on either side of the barrier")
    world.set_depths({**shore, **outside_range})
    if world.route_to(target) is None or world.observe_foraging(200., 52., 100.) != initial:
        raise AssertionError("A connection outside the sensing radius must not reveal food through the barrier")
    world.set_depths({**shore, (1, 0): 20.})
    if world.observe_foraging(200., 52., 100.)["detected_food"] != (FoodTarget("probe", 0), (2, 0)):
        raise AssertionError("Opening the sensed local connection should reveal the food")


def check_short_retreat_after_drawdown(high, receded):
    # Use measured depth values at a carp shelf, at controlled centimeter-scale offsets.
    high_depths, low_depths = depths(high), depths(receded)
    shelf, river, dry_side = (65, 39), (64, 39), (66, 39)
    start = (0., 0., 4.)
    east, west, north, south = (18., 0., 4.), (-18., 0., 4.), (0., 18., 4.), (0., -18., 4.)
    columns = {start: (0., high_depths[shelf]), west: (0., low_depths[river]),
               east: (0., low_depths[dry_side]), north: (0., high_depths[river]), south: (0., low_depths[river])}
    small, adult = (receded["species"]["CommonCarp"][size]["clearance_cm"] for size in ("0.75", "1.0"))

    def retreat(clearance, blocked=()):
        return shallow_water_retreat(start, clearance, 52., .75, .2, columns.get,
                                     lambda origin, end, radius: end not in blocked and origin == start and radius == clearance - .2)

    if retreat(adult) != start:
        raise AssertionError("Sufficient current depth should bypass the short retreat")
    columns[start] = (0., low_depths[shelf])
    budget = 52. * .1 * .75
    if (retreat(small) != start or retreat(adult) != (0., budget, 4.)
            or retreat(adult, {(0., budget, 4.)}) != (-budget, 0., 4.)
            or retreat(adult, {(0., budget, 4.), (-budget, 0., 4.), (0., -budget, 4.)}) != start):
        raise AssertionError("Expected a collision-checked retreat to the deepest reachable nearby column")
    print("Carp short retreat: deeper probe selected; blocked sweep fell back; movement capped to 3.9 cm")


def check_measured_detour(run):
    source, destination = "IslandRiverDrift", "IslandRiverSlowShelf"
    routes = {}
    for phase, survey in run["surveys"].items():
        grid = survey["depth_grid"]
        spacing = survey["grid_cm"]
        profile = survey["species"]["UnidentifiedFish"]["1.0"]
        expected = profile["pairs"][f"{source}:{destination}"]

        def cell_at(site):
            return tuple(round((coordinate - origin) / spacing) for coordinate, origin in
                         zip(grid["sites_cm"][site], grid["origin_cm"]))

        start, end = cell_at(source), cell_at(destination)
        height = grid["sites_cm"][destination][2] - survey["site_water_cm"][destination][0]
        # This resource is a controlled probe for movement and payment, not an authored consumer assignment.
        patch = FoodPatch(end, height, 2., 0., .5, 2.)
        world = WaterGridWorld(depths(survey), start, profile["clearance_cm"], {"probe": patch}, 0., 2.)
        route = world.route_to(end)
        if (not expected["connected_depth_grid"] or not expected["straight_missing_water_samples"] or not route
                or len(route) * spacing <= expected["distance_cm"]):
            raise AssertionError(f"Expected a connected grid route around an interrupted straight corridor in {phase}")
        if "detour_edges" in survey:
            verify_swept_detour(survey["detour_edges"], start, route, profile["clearance_cm"])
        for time, food_range in profile["nominal_food_range_cm"].items():
            if (expected[f"within_nominal_{time}_food_range"]
                    or world.select_food_target(food_range, 52., spacing) is not None):
                raise AssertionError(f"Connected distant food should remain outside detection in {phase} {time}")
        target = FoodTarget("probe", 0)
        if world.step("eat", target)["amount"] or patch.stock != 2.:
            raise AssertionError("A known waypoint cannot pay at a distance")
        for action in route:
            if world.step(action)["outcome"] != "moved":
                raise AssertionError(f"Grid navigator produced an invalid step in {phase}")
        if (world.cell != end or world.select_food_target(0., 52., spacing) != target
                or world.step("eat", target)["amount"] != .5 or patch.stock != 1.5):
            raise AssertionError(f"Expected local detection and payment only after arriving in {phase}")
        routes[phase] = len(route)
    print(f"Seed {run['seed']}: known-waypoint detour executed in {routes} grid moves; distant food stayed outside detection")


def verify_swept_detour(probe, start, route, clearance):
    edges = probe["edges"]
    if len(edges) != len(route) or not math.isclose(probe["clearance_cm"], clearance):
        raise AssertionError("Expected one Unreal edge probe per planned move at the same body clearance")
    previous = None
    cell = start
    for row, action in zip(edges, route):
        dx, dy = GRID_MOVES[action]
        next_cell = cell[0] + dx, cell[1] + dy
        if (tuple(row["from"]) != cell or tuple(row["to"]) != next_cell
                or row["missing_water"] or row["samples"] < 2 or row["result"] != "clear"):
            raise AssertionError(f"Unreal depth or sweep rejected the grid edge {row}")
        bottom, surface = row["center_bounds_cm"]
        if bottom > surface or (previous and (bottom > previous[1] or surface < previous[0])):
            raise AssertionError("Adjacent swept edges have no overlapping body-center depths")
        previous = bottom, surface
        cell = next_cell
    if "joins" in probe:
        joins = probe["joins"]
        if len(joins) != len(edges) - 1:
            raise AssertionError("Missing an Unreal vertical sweep between route edges")
        for row, previous_edge, next_edge in zip(joins, edges, edges[1:]):
            start_z, end_z = row["from_z_cm"], row["to_z_cm"]
            bottom, surface = row["water_column_cm"]
            if (row["cell"] != previous_edge["to"] or row["cell"] != next_edge["from"] or not row["clear"]
                    or start_z != previous_edge["sweep_z_cm"] or end_z != next_edge["sweep_z_cm"]
                    or not bottom + clearance <= min(start_z, end_z) <= max(start_z, end_z) <= surface - clearance):
                raise AssertionError(f"Unreal vertical sweep or body clearance rejected the route join: {row}")


class LocalWaterExplorer:
    """Reference controller with only adjacent depths and its own movement history."""

    def __init__(self, clearance):
        self.clearance = clearance
        self.position = (0, 0)
        self.visited = {self.position}
        self.path = []

    def choose(self, observation):
        detected = observation["detected_food"]
        if detected and detected[1] == (0, 0):
            return "eat", detected[0]
        if not swim_center_bounds(0., observation["depth_cm"], self.clearance):
            return "wait", None
        x, y = self.position
        neighbors = {action: (x + dx, y + dy) for action, (dx, dy) in GRID_MOVES.items()
                     if swim_center_bounds(0., observation["adjacent_depth_cm"][action], self.clearance)}
        choices = [action for action, cell in neighbors.items() if cell not in self.visited]
        if detected:
            choices = [action for action in neighbors if GRID_MOVES[action] == detected[1]] or choices
        if choices:
            return choices[0], None
        if not self.path:
            return "wait", None
        if self.path[-1] in neighbors:
            return self.path[-1], None
        # Falling water can sever the old return path. Revisit reachable cells from here.
        self.path.clear()
        self.visited = {self.position}
        return next(iter(neighbors), "wait"), None

    def record_move(self, action):
        dx, dy = GRID_MOVES[action]
        x, y = self.position
        self.position = x + dx, y + dy
        self.visited.add(self.position)
        if self.path and self.path[-1] == action:
            self.path.pop()
        else:
            self.path.append(next(a for a, delta in GRID_MOVES.items() if delta == (-dx, -dy)))


def explore_for_food(world, food_range, spacing, step_budget):
    """Drive a grid probe from local observations and visit memory."""
    explorer = LocalWaterExplorer(world.clearance_cm)
    first_detection = None
    for moves in range(step_budget + 1):
        observation = world.observe_foraging(food_range, 52., spacing)
        detected = observation["detected_food"]
        if detected and first_detection is None:
            first_detection = moves
        action, target = explorer.choose(observation)
        if action == "eat":
            return first_detection, moves, world.step(action, target)
        if moves == step_budget or action == "wait":
            break
        if world.step(action)["outcome"] != "moved":
            raise AssertionError("An observed passable neighbor rejected movement")
        explorer.record_move(action)
    return first_detection, moves, None


def check_exploration_after_drawdown():
    start, middle, pocket, shelf = (0, 0), (-1, 0), (-2, 0), (-2, 1)
    water = {start: 25., middle: 25., pocket: 25.}
    patch = FoodPatch(shelf, 10., 2., 0., .5, 2.)
    world = WaterGridWorld(water, start, 3., {"shelf": patch}, 0., 2.)
    explorer = LocalWaterExplorer(world.clearance_cm)

    def advance(expected_action, expected_outcome):
        action, target = explorer.choose(world.observe_foraging(100., 52., 100.))
        if action != expected_action:
            raise AssertionError(f"Expected {expected_action} after local water update, got {action}")
        result = world.step(action, target)
        if result["outcome"] != expected_outcome:
            raise AssertionError(f"Expected {expected_outcome} for {action}, got {result['outcome']}")
        if action in GRID_MOVES:
            explorer.record_move(action)

    advance("west", "moved")
    advance("west", "moved")
    world.set_depths({**water, middle: 4.})
    advance("wait", "wait")
    if world.cell != pocket or patch.stock != 2. or world.energy != 0.:
        raise AssertionError("An isolated fish must hold position and receive no food")
    world.set_depths({**water, middle: 4., shelf: 20.})
    advance("north", "moved")
    advance("eat", "paid")
    if world.cell != shelf or world.energy != .5 or patch.stock != 1.5:
        raise AssertionError("Reconnected shelf must pay only after the fish arrives")
    print("Drawdown closed the remembered return route; local exploration waited and used a newly wetted connection")


def check_local_forage_exploration(run):
    source, destination = "IslandRiverDrift", "IslandRiverSlowShelf"
    results = {}
    for phase, survey in run["surveys"].items():
        grid = survey["depth_grid"]
        spacing = survey["grid_cm"]
        profile = survey["species"]["UnidentifiedFish"]["1.0"]
        start, end = [tuple(round((coordinate - origin) / spacing) for coordinate, origin in
                            zip(grid["sites_cm"][site], grid["origin_cm"])) for site in (source, destination)]
        height = grid["sites_cm"][destination][2] - survey["site_water_cm"][destination][0]
        counts = {}
        for time, food_range in profile["nominal_food_range_cm"].items():
            patch = FoodPatch(end, height, 2., 0., .5, 2.)
            world = WaterGridWorld(depths(survey), start, profile["clearance_cm"], {"probe": patch}, 0., 2.)
            first, moves, payment = explore_for_food(world, food_range, spacing, step_budget=2 * survey["wet_cells"])
            if (first is None or first <= 0 or first >= moves or world.cell != end or not payment
                    or payment["amount"] != .5 or patch.stock != 1.5 or world.energy != .5):
                raise AssertionError(f"Local exploration did not discover then eat at the destination in {phase} {time}")
            counts[time] = (first, moves)
        results[phase] = counts
    print(f"Seed {run['seed']}: local exploration (discovery, arrival) moves {results}")


def check_saved_drawdown(run):
    shelf = "IslandRiverSlowShelf"
    inlet = "IslandRiverInletPlants"
    cell = (0, 0)
    columns = run["columns_cm"]
    bottom = columns["normal"][0]
    if columns["normal"] != columns["restored"] or columns["drawdown"][0] != bottom:
        raise AssertionError("The drawdown must change only the water surface")
    patches = {
        name: FoodPatch(cell, patch["z_cm"] - bottom, patch["capacity"], 0., patch["meal_cap"], 0.)
        for name, patch in run["patches"].items()
    }
    world = WaterGridWorld({cell: columns["normal"][1] - bottom}, cell, run["clearance_cm"], patches,
                           energy=0., max_energy=100.)
    receipts = run["drawdown_receipts"]
    if not receipts or not run["hatch_at"] <= run["drawdown_at"] < run["restored_at"]:
        raise AssertionError("Expected post-hatch drawdown receipts")
    for phase, expected in (("normal", {shelf, inlet}), ("drawdown", {shelf}), ("restored", {shelf, inlet})):
        world.set_depths({cell: columns[phase][1] - bottom})
        if world.observe()["local_food"].keys() != expected:
            raise AssertionError(f"Unexpected reachable food during {phase}")
        if phase == "normal":
            continue
        if phase == "drawdown" and world.step("eat", inlet)["outcome"] != "inaccessible":
            raise AssertionError("Exposed inlet accepted a meal")
        phase_receipts = receipts if phase == "drawdown" else [run["first_restored_inlet_receipt"]]
        for receipt in phase_receipts:
            name = receipt["patch"]
            expected_patch = shelf if phase == "drawdown" else inlet
            at = receipt["at"]
            in_phase = (run["drawdown_at"] < at < run["restored_at"] if phase == "drawdown"
                        else at > run["restored_at"])
            if name != expected_patch or not in_phase:
                raise AssertionError(f"Unexpected authority receipt during {phase}")
            patch = patches[name]
            # Reconstruct available stock for this transaction from its printed receipt.
            # Intervening growth and competing fish are outside this single-cell replay.
            patch.stock = receipt["amount"] + receipt["remaining"]
            if patch.stock > patch.capacity + .001:
                raise AssertionError("Receipt exceeds the authored patch capacity")
            before_energy = world.energy
            result = world.step("eat", name)
            if (result["outcome"] != "paid" or not math.isclose(result["amount"], receipt["amount"], abs_tol=.001)
                    or not math.isclose(patch.stock, receipt["remaining"], abs_tol=.001)
                    or not math.isclose(world.energy - before_energy, result["amount"])):
                raise AssertionError(f"Stock or energy mismatch during {phase} at {at}")
    print(f"Seed {run['seed']}: saved shelf accessible through drawdown; {len(receipts)} shelf meals and inlet return matched")


def check_shared_forage_drawdown(run):
    main, extra = (0, 0), (1, 0)
    positions = (main, extra)
    sites = ("main", "extra")
    water = run["water"]
    elevations = [z - water["before"]["sites"][name]["bottom_cm"]
                  for z, name in zip(run["point_z_cm"], sites)]
    patch = FoodPatch(main, elevations[0], run["capacity"], 0., run["meal_cap"], run["capacity"],
                      extra_points=((extra, elevations[1]),))

    def phase_depths(phase):
        return {cell: site["surface_cm"] - site["bottom_cm"]
                for cell, site in zip(positions, (water[phase]["sites"][name] for name in sites))}

    world = WaterGridWorld(phase_depths("before"), extra, 3., {"drift": patch}, 0., 100.)

    def replay_payment(row):
        world.cell = positions[row["access"]]
        previous_energy = world.energy
        payment = world.step("eat", FoodTarget("drift", row["access"]))
        if (payment["outcome"] != "paid" or not math.isclose(payment["amount"], row["amount"], abs_tol=.001)
                or not math.isclose(patch.stock, row["remaining"], abs_tol=.001)
                or not math.isclose(world.energy - previous_energy, payment["amount"])):
            raise AssertionError(f"Unexpected shared forage receipt: {row}")

    first_tick = run["initial_shared_receipts"]
    if {row["access"] for row in first_tick} != {0, 1} or len({row["at"] for row in first_tick}) != 1:
        raise AssertionError("Both points must draw from the same stock in the first tick")
    check_shared_authority_tick(run, phase_depths, positions, elevations)
    for row in first_tick:
        replay_payment(row)

    world.set_depths(phase_depths("lowered"))
    world.cell = extra
    before = patch.stock
    if (world.step("eat", "drift")["outcome"] != "inaccessible" or patch.stock != before
            or world.select_food(1., 52., 100.) is not None):
        raise AssertionError("Exposed shared forage accepted a local request")
    world.cell = main
    if world.select_food(1., 52., 100.) != "drift":
        raise AssertionError("Drawdown also disrupted the submerged shared food")
    lowered_at = water["lowered"]["authority_seconds"]
    restored_at = water["restored"]["authority_seconds"]
    receipts = run["drawdown_receipts"]
    if not receipts or any(row["access"] != 0 or not lowered_at < row["at"] < restored_at for row in receipts):
        raise AssertionError("Expected submerged-only payments throughout drawdown")
    if phase_depths("before") != phase_depths("restored"):
        raise AssertionError("The original water depths did not return")
    reopened = run["first_reopened_receipt"]
    if reopened["access"] != 1 or reopened["at"] <= restored_at:
        raise AssertionError("Expected a payment at the reopened point")
    for row in receipts:
        # Reconstruct the stock between transactions from the authority receipts.
        patch.stock = row["amount"] + row["remaining"]
        replay_payment(row)
    world.set_depths(phase_depths("restored"))
    patch.stock = reopened["amount"] + reopened["remaining"]
    replay_payment(reopened)
    check_shared_forage_selection(run, phase_depths, positions, elevations)
    print(f"Seed {run['seed']}: one stock, {len(receipts)} submerged-only receipts and reopened extra access matched")


def check_shared_authority_tick(run, phase_depths, positions, elevations):
    main, extra = positions
    capacity = run["capacity"]
    patch = FoodPatch(main, elevations[0], capacity, .125, run["meal_cap"], capacity,
                      extra_points=((extra, elevations[1]),))
    receipts = run["initial_shared_receipts"]
    swimmers = {row["agent"]: (positions[row["access"]], 3., 0., 100.) for row in receipts}
    requests = {row["agent"]: ("eat", FoodTarget("drift", row["access"])) for row in reversed(receipts)}
    world = SharedWaterForaging(phase_depths("before"), {"drift": patch}, swimmers)
    stock = world.patches["drift"]
    first = world.step(requests)
    if (first["growth"]["drift"] != 0. or any(first["results"][row["agent"]] != ("paid", row["amount"])
            for row in receipts) or not math.isclose(stock.stock, receipts[-1]["remaining"], abs_tol=.001)):
        raise AssertionError("Joint step must match the ordered first Unreal payments for the same stock")

    world.set_depths(phase_depths("lowered"))
    before = stock.stock
    lowered = world.step(requests)
    expected_extra = {row["agent"] for row in receipts if row["access"] == 1}
    refused = {agent for agent, (outcome, _) in lowered["results"].items() if outcome == "inaccessible"}
    paid = sum(amount for _, amount in lowered["results"].values())
    if (refused != expected_extra or paid <= 0. or lowered["growth"]["drift"] != .125
            or not math.isclose(before + .125, stock.stock + paid)):
        raise AssertionError("Joint drawdown must reject exposed requests and regrow stock exactly once")
    print(f"Seed {run['seed']}: joint stock replay matched {len(receipts)} same-tick Unreal payments")

    # Ordinary Drift growth follows region weather even if one feeding point is exposed.
    drift = FoodPatch(main, elevations[0], capacity, .13, run["meal_cap"], 0.,
                      extra_points=((extra, elevations[1]),), rainfall_driven=True)
    weather_world = SharedWaterForaging(phase_depths("lowered"), {"drift": drift}, swimmers)
    waits = {agent: ("wait", None) for agent in requests}
    dry = weather_world.step(waits, elapsed=1., rainfall=.35)
    early_attempt = weather_world.step(requests, elapsed=0., rainfall=.35)
    if not math.isclose(weather_world.patches["drift"].stock, .12025) or any(
            amount for _, amount in early_attempt["results"].values()):
        raise AssertionError("Stock below the meal minimum must remain available for the next growth update")
    wet = weather_world.step(waits, elapsed=1., rainfall=.85)
    if (not math.isclose(dry["growth"]["drift"], .12025) or not math.isclose(wet["growth"]["drift"], .15275)
            or weather_world.patches["drift"].stock <= .2):
        raise AssertionError("The single shared stock should cross the meal minimum after the rain input changes")
    for row in receipts:
        visible = wet["observations"][row["agent"]]["local_food"]
        if ("drift" in visible) != (row["access"] == 0):
            raise AssertionError("Only a submerged access point should expose the grown stock")
    delivered = weather_world.step(requests, elapsed=0., rainfall=.85)
    if (not math.isclose(sum(amount for _, amount in delivered["results"].values()), .273)
            or weather_world.patches["drift"].stock != 0.):
        raise AssertionError("The grown stock should pay only the accessible shared request")


def check_shared_forage_selection(run, phase_depths, positions, elevations):
    main, extra = positions
    stock = run["capacity"]
    patch = FoodPatch(main, elevations[0], stock, 0., run["meal_cap"], stock,
                      extra_points=((extra, elevations[1]),))
    original = FoodTarget("drift", 0)
    alternative = FoodTarget("drift", 1)
    world = WaterGridWorld(phase_depths("before"), extra, 3., {"drift": patch}, 0., stock)

    def choose():
        # The two-cell control isolates access selection from the actual river travel distance.
        return world.select_food_target(100., 52., 100.)

    if choose() != alternative:
        raise AssertionError("The nearer submerged point should win at normal water")
    world.set_depths(phase_depths("lowered"))
    if (world.step("eat", alternative)["outcome"] != "inaccessible" or patch.stock != stock
            or choose() != original or world.step("west")["outcome"] != "moved"):
        raise AssertionError("Drawdown should reject the stale request and permit movement to the remaining point")
    if world.step("eat", alternative)["outcome"] != "inaccessible" or patch.stock != stock:
        raise AssertionError("Arrival at one point must not authorize a request targeting another")
    if world.step("eat", original)["outcome"] != "paid":
        raise AssertionError("The chosen submerged access should pay after arrival")
    world.set_depths(phase_depths("restored"))
    if world.step("east")["outcome"] != "moved" or choose() != alternative:
        raise AssertionError("Restoring the water should restore the nearer feeding choice")
    if world.step("eat", alternative)["outcome"] != "paid" or not math.isclose(patch.stock + world.energy, stock):
        raise AssertionError("Both requests must draw from one conserved stock")


def check_wet_shelf_ledger(run):
    ledger = run["wet_shelf_ledger"]
    shelf = run["patches"]["IslandRiverSlowShelf"]
    receipts = ledger["receipts"]
    if len(receipts) < 2 or ledger["initial_stock"] != shelf["capacity"]:
        raise AssertionError("The wet shelf ledger must begin at full stock")
    rate = ledger["authored_regrowth_per_second"] * (.75 + .5 * ledger["rainfall"])
    stock = ledger["initial_stock"]
    previous = receipts[0]["at"]
    child = run["fry_id"]
    first_depletion = None
    for row in receipts:
        at = row["at"]
        if at < previous:
            raise AssertionError(f"Unexpected shelf receipt order at {at}")
        stock = min(shelf["capacity"], stock + rate * (at - previous))
        payment = min(stock, shelf["meal_cap"])
        stock -= payment
        if (not math.isclose(payment, row["amount"], abs_tol=.001)
                or not math.isclose(stock, row["remaining"], abs_tol=.001)):
            raise AssertionError(f"Seed {run['seed']}, shelf at {at}: predicted {payment:g}, {stock:g}; got {row}")
        if stock <= .001 and first_depletion is None:
            first_depletion = at
        previous = at
    if first_depletion is None or not any(a["at"] == b["at"] and a["agent_id"] != child and b["agent_id"] == child
               for a, b in zip(receipts, receipts[1:])):
        raise AssertionError("Expected depletion and a shared-stock transaction with a founder before the fry")
    print(f"Seed {run['seed']}: shared shelf matched {len(receipts)} receipts, first depleted at {first_depletion:g}s")


def check_nursery_lifecycle(run):
    reservations = run["reservations"]
    sites = {row["site"]: NurserySite(row["site_z_cm"]) for row in reservations}
    ledger = NurseryLedger(sites)
    requests = defaultdict(list)
    probes = defaultdict(dict)
    for key, row in enumerate(reservations):
        requests[row["reserved_at"]].append(key)
        for probe in row["probes"]:
            probes[probe["at"]][row["site"]] = probe["column_cm"]

    outcomes = {}
    children = {}
    columns = dict(run["initial_columns_cm"])
    for now in sorted(requests.keys() | probes.keys()):
        columns.update(probes.get(now, {}))
        # Only compare the times when the corresponding nursery was probed.
        for key, state in ledger.update(now, probes.get(now, {})).items():
            outcomes[key] = [state, now]
            if state == "hatch_eligible":
                row = reservations[key]
                site = row["site"]
                bottom, surface = columns[site]
                patch = run["nursery_patches"][site]
                water = FoodPatch((0, 0), sites[site].elevation_cm - bottom,
                                  patch["capacity"], 0., patch["energy_per_meal"], 0.)
                children[key] = WaterGridWorld({(0, 0): surface - bottom}, (0, 0),
                                                run["fry_clearance_cm"], {site: water}, 0., 100.)
        for key in requests.get(now, ()):
            row = reservations[key]
            if not ledger.reserve(key, row["site"], row["parents"], now, row["due_at"], columns[row["site"]]):
                raise AssertionError(f"Unexpected reservation rejection at {now}: {row['site']}")
    expected = {key: row["expected"] for key, row in enumerate(reservations)}
    observed = {key: outcomes.get(key, ["pending", None]) for key in expected}
    if observed != expected or ledger.pending.keys() != {key for key in expected if expected[key][0] == "pending"}:
        raise AssertionError(f"Unexpected nursery outcomes: {observed}")
    interrupted, = (key for key, (status, _) in expected.items() if status == "interrupted")
    failed = reservations[interrupted]
    interrupted_at = outcomes[interrupted][1]
    dry_probe = next(probe for probe in failed["probes"] if probe["at"] == interrupted_at)
    trial = NurseryLedger(sites)
    site = failed["site"]
    parents = failed["parents"]
    wet = run["initial_columns_cm"][site]
    trial.reserve(interrupted, site, parents, failed["reserved_at"], failed["due_at"], wet)
    trial.update(interrupted_at, {site: dry_probe["column_cm"]})
    if (trial.reserve("retry", site, parents, interrupted_at + 29.999, interrupted_at + 65., wet)
            or not trial.reserve("retry", site, parents, interrupted_at + 30., interrupted_at + 65., wet)):
        raise AssertionError("A wet nursery must reopen for the parents at the retry boundary")

    key, = children
    site = reservations[key]["site"]
    born = run["observed_hatch"]
    meal = run["first_fry_receipt"]
    if not outcomes[key][1] == born["time"] < meal["at"] or meal["patch"] != site:
        raise AssertionError("First observed fry receipt must follow the unaffected hatch")
    world = children[key]
    patch = world.patches[site]
    # First meal access is evaluated from its recorded pre-transaction stock.
    patch.stock = meal["amount"] + meal["remaining"]
    received = world.step("eat", site)
    if (received["outcome"] != "paid" or not math.isclose(received["amount"], meal["amount"], abs_tol=.001)
            or not math.isclose(patch.stock, meal["remaining"], abs_tol=.001)):
        raise AssertionError(f"First fry meal did not reproduce: {meal}")
    print(f"Seed {run['seed']}: drawdown cancellation, unaffected hatch, new reservation and first fry meal matched")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    scenes = ("water_grid", "saved_drawdown", "nursery", "shared_forage_drawdown")
    if fixture["schema_version"] != 1 or not any(fixture.get(name) for name in scenes):
        parser.error("expected sampled water grids, drawdown or nursery with schema_version 1")
    check_sensing_ignores_distant_connection()
    check_exploration_after_drawdown()
    check_seasonal_food_stock()
    for run in fixture.get("water_grid", ()):
        low, high, receded = (run["surveys"][phase] for phase in ("early_dry", "late_high", "receding"))
        check_body_clearance(low, high, "CommonCarp", (64, 39), "east")
        check_body_clearance(low, high, "AriakeCatfish", (33, 4), "south")
        check_body_clearance(low, high, "UnidentifiedFish", (33, 4), "south")
        check_body_clearance_during_retreat(high, receded, "CommonCarp", (64, 39), "east")
        check_body_clearance_during_retreat(high, receded, "AriakeCatfish", (33, 4), "south")
        check_body_clearance_during_retreat(high, receded, "UnidentifiedFish", (33, 4), "south")
        check_short_retreat_after_drawdown(high, receded)
        energy = check_flood_food(low, high, receded)
        check_flood_food_switch(low, high, receded)
        check_resettable_forage_episode(low, high, receded)
        check_measured_detour(run)
        check_local_forage_exploration(run)
        print(f"Seed {run['seed']}: three fish body limits passed; energy after flood meal {energy:g}; recession blocked eating")
        print(f"Seed {run['seed']}: changing depth and depletion switched food and low water disconnected the fish")
    for run in fixture.get("saved_drawdown", ()):
        check_saved_drawdown(run)
        if "wet_shelf_ledger" in run:
            check_wet_shelf_ledger(run)
    for run in fixture.get("nursery", ()):
        check_nursery_lifecycle(run)
    for run in fixture.get("shared_forage_drawdown", ()):
        check_shared_forage_drawdown(run)


if __name__ == "__main__":
    main()

"""Measure how the current R9 policy receives changes in plant stock."""

import json
import sys
from hashlib import sha256
from pathlib import Path

import numpy as np

TRAINING_ROOT = Path(__file__).resolve().parents[3] / "herbivore_rl"
sys.path.insert(0, str(TRAINING_ROOT))

from env_v2 import r9_body as B
from env_v2 import r9_brains as BR
from env_v2 import vegetation_v1 as soil
from env_v2.r9_world import R9World


def observation_fixture(config, seed, world_type=R9World):
    world = world_type(config, [seed])
    deer = int(world.sp_lo[B.DEER])
    world.pos[0, deer] = (31., 31.)
    world.vel[:] = 0.
    world.disp[:] = 0.
    world.grass[:] = world.grass_cap[:] = world.grass_regen[:] = 0.
    world.root[:] = world.root_cap[:] = world.root_regen[:] = 0.
    cell = (0, 15, 15)
    world.grass[cell] = .2
    world.grass_cap[cell] = .5
    world.refresh()
    return world, deer, cell


def sample(world, deer, cell):
    obs = world.observe()[0, deer]
    return {"stock": float(world.grass[cell]), "food_here": float(obs[B.O_FOOD_HERE]),
            "food_density": float(obs[B.O_FOOD_DENSITY]), "grid_regrown": float(world.st["grid_regen"][0, 0])}


def run_case(config, seed, regen):
    world, deer, cell = observation_fixture(config, seed)
    world.grass_regen[cell] = regen
    before = sample(world, deer, cell)
    world.step(np.full((1, world.S), B.WATCH, dtype=np.int64))
    after = sample(world, deer, cell)
    expected_stock = .5 - (.5 - .2) * (1. - regen) ** world.D
    np.testing.assert_allclose(after["stock"], expected_stock, rtol=0., atol=1e-12)
    np.testing.assert_allclose(after["stock"] - before["stock"], after["grid_regrown"], rtol=0., atol=1e-12)
    assert (after["food_here"] > before["food_here"]) == (regen > 0.)
    assert (after["food_density"] > before["food_density"]) == (regen > 0.)
    return {"seed": seed, "per_step_regen": regen, "physics_steps": world.D, "before": before, "after": after}


def run_soil_history(config, seed, initial_rain):
    world, deer, cell = observation_fixture(config, seed)
    state = soil.Cell(moisture=.28)
    stock = float(world.grass[cell])
    capacity = float(world.grass_cap[cell])
    soil_config = soil.Config(enabled=True)
    habitat = soil.Habitat()
    dt = 2. / 15.
    snapshots = []
    for phase, rain, duration in (("exposure", initial_rain, 60), ("recovery", 0., 30)):
        weather = soil.Weather(rain=rain)
        growth = loss = 0.
        before = stock
        for _ in range(round(duration / dt)):
            stock, gained, lost = soil.advance(soil_config, weather, habitat, state, stock, capacity, .002, dt)
            growth += gained
            loss += lost
        np.testing.assert_allclose(stock, before + growth - loss, rtol=0., atol=1e-12)
        assert 0. <= stock <= capacity
        # Publish only the cell stock through R9's existing observation path.
        world.grass[cell] = stock
        world.refresh()
        observation = sample(world, deer, cell)
        assert observation.pop("grid_regrown") == 0.
        snapshots.append({"phase": phase, "rain": rain, "duration_seconds": duration,
                          "moisture": state.moisture, "growth": growth, "loss": loss, **observation})
    transactions = []
    world.E[0, deer] = .5
    world.refresh()
    request = np.full((1, world.S), B.WATCH, dtype=np.int64)
    for action in (B.WATCH, B.EAT):
        before = sample(world, deer, cell)
        already_paid = world.st["eaten_units"][0, B.DEER, B.GRASS]
        request[0, deer] = action
        world.step(request)
        after = sample(world, deer, cell)
        paid = float(world.st["eaten_units"][0, B.DEER, B.GRASS] - already_paid)
        np.testing.assert_allclose(after["stock"] + paid, before["stock"], rtol=0., atol=1e-12)
        assert (paid > 0) == (action == B.EAT)
        assert (after["food_here"] < before["food_here"]) == (action == B.EAT)
        assert (after["food_density"] < before["food_density"]) == (action == B.EAT)
        assert after["grid_regrown"] == 0.
        transactions.append({"action": int(action), "grass_paid": paid, "before": before, "after": after})
    return {"seed": seed, "initial_rain": initial_rain, "snapshots": snapshots, "transactions": transactions}


class FeedingTraceWorld(R9World):
    def _eat(self):
        energy = super()._eat()
        self.feeding_trace.append(self._gain_u[0].copy())
        return energy


def run_shared_stock(config, seed, stock, juvenile_first):
    world, first, cell = observation_fixture(config, seed, FeedingTraceWorld)
    juvenile, adult = (first, first + 1) if juvenile_first else (first + 1, first)
    slots = [adult, juvenile]
    world.pos[0, slots] = [(30.5, 31.), (31.5, 31.)]
    world.E[0, slots] = .5
    world.g_size[0, slots] = 1.
    world.born[0, slots] = world.t[0] - world.sb["maturity"][0, slots] * [2., .25]
    world.grass[cell] = stock
    world.refresh()
    assert world.alive[0, slots].all()

    world.feeding_trace = []
    request = np.full((1, world.S), B.WATCH, dtype=np.int64)
    request[0, slots] = B.EAT
    world.step(request)

    step_payments = np.stack(world.feeding_trace)[:, slots, B.GRASS]
    paid = step_payments.sum(axis=0)
    remaining = float(world.grass[cell])
    np.testing.assert_allclose(remaining + paid.sum(), stock, rtol=0., atol=1e-12)
    np.testing.assert_allclose(world.st["eaten_units"][0, B.DEER, B.GRASS], paid.sum(), rtol=0., atol=1e-12)
    assert (paid > 0.).all() == (stock >= world._eat_min)
    assert world.af[0, adult] >= 1. and world.af[0, juvenile] < 1.
    return {"seed": seed, "initial_stock": stock, "juvenile_first": juvenile_first,
            "adult_paid": float(paid[0]), "juvenile_paid": float(paid[1]), "remaining": remaining,
            "step_payments_adult_then_juvenile": step_payments.tolist()}


def run_mixed_stock(config, seed, schedule):
    world, deer, cell = observation_fixture(config, seed, FeedingTraceWorld)
    species = [B.DEER, B.BUFFALO]
    slots = [deer, int(world.sp_lo[B.BUFFALO])]
    world.pos[0, slots] = [(30.5, 31.), (31.5, 31.)]
    world.E[0, slots] = .5
    world.g_size[0, slots] = 1.
    world.born[0, slots] = world.t[0] - world.sb["maturity"][0, slots] * 2.
    stock = world._eat_min
    world.grass[cell] = stock
    world.refresh()
    assert world.alive[0, slots].all()

    world.feeding_trace = []
    for eaters in schedule:
        request = np.full((1, world.S), B.WATCH, dtype=np.int64)
        request[0, [slots[index] for index in eaters]] = B.EAT
        world.step(request)

    step_payments = np.stack(world.feeding_trace)[:, slots, B.GRASS]
    paid = step_payments.sum(axis=0)
    remaining = float(world.grass[cell])
    rates = world.sb["eat_rate"][0, slots, B.GRASS]
    expected = np.zeros_like(paid)
    if len(schedule[0]) == 2:
        expected = rates * min(1., stock / rates.sum())
    else:
        index, = schedule[0]
        expected[index] = min(stock, rates[index])
    np.testing.assert_allclose(paid, expected, rtol=0., atol=1e-12)
    np.testing.assert_allclose(remaining + paid.sum(), stock, rtol=0., atol=1e-12)
    np.testing.assert_allclose(world.st["eaten_units"][0, species, B.GRASS], paid, rtol=0., atol=1e-12)
    return {"seed": seed, "initial_stock": stock, "deer_paid": float(paid[0]), "buffalo_paid": float(paid[1]),
            "remaining": remaining, "step_payments_deer_then_buffalo": step_payments.tolist()}


def run_boar_food_switch(config, seed, root_stock, meat_stock=0., carcass_distance=None, brain=None, decisions=1):
    world, _, cell = observation_fixture(config, seed, FeedingTraceWorld)
    boar = int(world.sp_lo[B.BOAR])
    foods = [B.ROOT, B.MEAT, B.GRASS]
    world.pos[0, boar] = (31., 31.)
    world.E[0, boar] = .5
    world.root[cell] = world.root_cap[cell] = root_stock
    assert world.alive[0, boar] and not world.carc_ok.any()
    if carcass_distance is not None:
        world._add_carcass(0, (31. + carcass_distance, 31.), meat_stock,
                           int(world.kin_id[0, boar]) + 1, B.DEER, 999, 0, places=1)
    world.refresh()
    obs = world.observe()[0, boar]
    food_here = float(obs[B.O_FOOD_HERE])

    world.feeding_trace = []
    if brain is not None:
        world.set_controller(0, B.BOAR, BR.Controller(brain, False, "fauna_r2"))
    else:
        request = np.full((1, world.S), B.WATCH, dtype=np.int64)
        request[0, boar] = B.EAT
    actions = []
    first_payment = None
    carcass_min_distance = carcass_distance
    for decision in range(decisions):
        if brain is not None:
            request = world.decide()
        actions.append(B.ACTION_NAMES[request[0, boar]])
        _, _, done, _ = world.step(request)
        assert not done[0, boar], "Boar respawn would change the tracked individual"
        if first_payment is None and any(step[boar].sum() > 0 for step in world.feeding_trace[-world.D:]):
            first_payment = decision + 1
        if carcass_distance is not None:
            distance = np.linalg.norm(world.pos[0, boar] - [31. + carcass_distance, 31.])
            carcass_min_distance = min(carcass_min_distance, float(distance))
    step_payments = np.stack(world.feeding_trace)[:, boar, :][:, foods]
    remaining = np.array([world.root[cell], world.carc_meat[0].sum(), world.grass[cell]])
    decayed = float(world.st["meat_decayed"][0])
    paid = step_payments.sum(axis=0)
    np.testing.assert_allclose(remaining + paid + [0., decayed, 0.], [root_stock, meat_stock, .2],
                               rtol=0., atol=1e-12)
    np.testing.assert_allclose(world.st["eaten_units"][0, B.BOAR, foods], paid, rtol=0., atol=1e-12)
    return {"seed": seed, "initial_root": root_stock, "initial_meat": meat_stock, "initial_grass": .2,
            "carcass_distance": carcass_distance, "meat_decayed": decayed, "observed_food_here": food_here,
            "requested_action": actions[0], "decisions": decisions, "eat_requests": actions.count("EAT"),
            "first_payment_decision": first_payment, "end_position": world.pos[0, boar].tolist(),
            "min_sampled_distance_to_carcass_site": carcass_min_distance,
            "total_paid_root_meat_grass": paid.tolist(),
            "step_payments_root_meat_grass": step_payments.tolist(), "remaining_root_meat_grass": remaining.tolist()}


if __name__ == "__main__":
    config = B.load_r9_config(TRAINING_ROOT / "configs/v3_r9_fauna_motion.yaml")
    counts = {species: [int(species == "deer")] * 2 for species in B.species_of(config)}
    config = B.override(config, {"counts": counts, "world": {"shelters": {"fixed": [[57., 57., 2.]]}}})
    regen_cases = []
    soil_cases = []
    for seed in (44190, 44191):
        regen_cases.extend(run_case(config, seed, regen) for regen in (0., .1))
        dry, rain = (run_soil_history(config, seed, level) for level in (0., .7))
        for dry_sample, rain_sample in zip(dry["snapshots"], rain["snapshots"]):
            for field in ("moisture", "stock", "food_here", "food_density"):
                assert rain_sample[field] > dry_sample[field], field
        soil_cases.extend((dry, rain))
    shared_config = B.override(config, {"counts": {**counts, "deer": [2, 2]}})
    shared_cases = []
    for seed in (44190, 44191):
        for stock in (.059, .06, .08, .1):
            a, b = (run_shared_stock(shared_config, seed, stock, order) for order in (False, True))
            for field in ("step_payments_adult_then_juvenile", "remaining"):
                np.testing.assert_allclose(a[field], b[field], rtol=0., atol=1e-12)
            shared_cases.extend((a, b))
    mixed_config = B.override(config, {"counts": {**counts, "buffalo": [1, 1]}})
    schedules = {"simultaneous": ((0, 1), ()), "deer_first": ((0,), (1,)), "buffalo_first": ((1,), (0,))}
    mixed_cases = [{"schedule": name, **run_mixed_stock(mixed_config, seed, schedule)}
                   for seed in (44190, 44191) for name, schedule in schedules.items()]
    boar_counts = {species: [int(species == "boar")] * 2 for species in counts}
    boar_config = B.override(config, {"counts": boar_counts})
    switch_cases = []
    for seed in (44190, 44191):
        cases = (
            (.059, 0., None, [[0., 0., .036], [0., 0., .036]]),
            (.06, 0., None, [[.018, 0., 0.], [0., 0., .036]]),
            (.1, 0., None, [[.018, 0., 0.], [.018, 0., 0.]]),
            (.06, .2, .5, [[.018, 0., 0.], [0., .0059259259, 0.]]),
            (.06, .2, 5., [[.018, 0., 0.], [0., 0., .036]]),
            (.059, .003, .5, [[0., .003, 0.], [0., 0., .036]]),
        )
        for roots, meat, distance, expected in cases:
            case = run_boar_food_switch(boar_config, seed, roots, meat, distance)
            np.testing.assert_allclose(case["step_payments_root_meat_grass"], expected, rtol=0., atol=1e-12)
            switch_cases.append(case)
    pack_boar = TRAINING_ROOT / "results/v3/r9/packs/fauna_r2/boar/boar_r2_7154688.npz"
    fauna_config = B.load_r9_config(TRAINING_ROOT / "configs/v3_r9_fauna.yaml")
    fauna_config = B.override(fauna_config, {"counts": boar_counts,
                                           "world": {"shelters": {"fixed": [[57., 57., 2.]]}}})
    boar_brain = BR.load_brain(pack_boar, fauna_config, B.BOAR)
    learned_cases = [run_boar_food_switch(fauna_config, seed, roots, meat, distance, brain=boar_brain)
                     for seed in (44190, 44191) for roots, meat, distance, _ in cases]
    for case in learned_cases:
        if (case["initial_root"], case["initial_meat"], case["carcass_distance"]) == (.06, .2, .5):
            assert case["requested_action"] == "EAT"
            assert case["step_payments_root_meat_grass"][0][0] > 0.
            assert case["step_payments_root_meat_grass"][1][1] > 0.
        else:
            assert case["requested_action"].startswith("WALK_")
            assert not np.any(case["step_payments_root_meat_grass"])
    rollouts = [run_boar_food_switch(fauna_config, seed, .06, meat, distance, brain=boar_brain, decisions=120)
                for seed in (44190, 44191) for meat, distance in ((0., None), (.2, .5), (.2, 5.))]
    for case in rollouts:
        if case["initial_meat"] == 0.:
            assert case["first_payment_decision"] is None
        else:
            assert case["first_payment_decision"] is not None
            assert case["total_paid_root_meat_grass"][1] > 0.
    print(json.dumps({"r9_regrowth": regen_cases, "soil_helper_to_r9_observation": soil_cases,
                      "shared_stock_by_growth_stage": shared_cases, "shared_stock_by_species": mixed_cases,
                      "boar_food_switch": switch_cases,
                      "fauna_r2_boar_decisions": {"sha256": sha256(pack_boar.read_bytes()).hexdigest(),
                                                  "cases": learned_cases, "rollouts": rollouts}}, indent=2))

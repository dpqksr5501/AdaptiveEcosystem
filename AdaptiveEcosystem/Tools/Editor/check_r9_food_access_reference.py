"""Measure the existing R9 plant transaction across a nominal interior boundary."""

import json
import sys
from pathlib import Path

import numpy as np

TRAINING_ROOT = Path(__file__).resolve().parents[3] / "herbivore_rl"
sys.path.insert(0, str(TRAINING_ROOT))

from env_v2 import r9_body as B
from env_v2.r9_world import R9World


def run_case(config, seed, cross_boundary):
    world = R9World(config, [seed])
    deer = int(world.sp_lo[B.DEER])
    world.pos[0, deer] = (29.8, 31.)
    world.head[0, deer] = (1., 0.)
    world.E[0, deer] = .5
    world.vel[:] = 0.
    world.disp[:] = 0.
    world.grass[:] = world.grass_cap[:] = world.grass_regen[:] = 0.
    world.root[:] = world.root_cap[:] = world.root_regen[:] = 0.
    stock = .5
    world.grass[0, 15, 15] = world.grass_cap[0, 15, 15] = stock
    world.refresh()

    steps = []
    request = np.full((1, world.S), B.WATCH, dtype=np.int64)
    for action in (B.EAT, B.ACTION_GROUPS["walk"][0] if cross_boundary else B.WATCH, B.EAT):
        request[0, deer] = action
        world.step(request)
        paid = float(world.st["eaten_units"][0, B.DEER, B.GRASS])
        remaining = float(world.grass.sum())
        np.testing.assert_allclose(paid + remaining, stock, rtol=0., atol=1e-12)
        steps.append({"action": int(action), "position": world.pos[0, deer].tolist(),
                      "cumulative_grass_units_paid": paid, "remaining_grass": remaining})

    assert steps[0]["cumulative_grass_units_paid"] == 0.
    assert steps[1]["cumulative_grass_units_paid"] == 0.
    assert (steps[1]["position"][0] > 30.) == cross_boundary
    assert (steps[2]["cumulative_grass_units_paid"] > 0.) == cross_boundary
    return {"seed": seed, "nominal_boundary_x": 30., "crossing_requested": cross_boundary, "steps": steps}


if __name__ == "__main__":
    config = B.load_r9_config(TRAINING_ROOT / "configs/v3_r9_fauna_motion.yaml")
    counts = {species: [int(species == "deer")] * 2
              for species in ("deer", "wolf", "boar", "buffalo", "leopard", "fox")}
    config = B.override(config, {"counts": counts, "world": {"shelters": {"fixed": [[57., 57., 2.]]}}})
    print(json.dumps([run_case(config, seed, cross)
                      for seed in (44190, 44191) for cross in (False, True)], indent=2))

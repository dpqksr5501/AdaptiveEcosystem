"""Read the existing R9 shelter observation and movement contract on two development seeds."""

import json
import sys
from pathlib import Path

import numpy as np

TRAINING_ROOT = Path(__file__).resolve().parents[3] / "herbivore_rl"
sys.path.insert(0, str(TRAINING_ROOT))

from env_v2 import r9_body as B
from env_v2.r9_world import R9World


def run_case(config, seed):
    world = R9World(config, [seed])
    deer = int(world.sp_lo[B.DEER])
    start = np.array([35.05, 30.])
    world.pos[0, deer] = start
    world.head[0, deer] = (-1., 0.)
    world.vel[:] = 0.
    world.disp[:] = 0.
    world.refresh()

    def sample(action):
        obs = world.observe()[0, deer]
        return {"action": action, "position": world.pos[0, deer].tolist(),
                "shelter_forward": float(obs[B.O_SHELTER_X]), "inside": bool(obs[B.O_IN_SHELTER])}

    request = np.full((1, world.S), B.WATCH, dtype=np.int64)
    steps = [sample(None)]
    assert steps[0]["shelter_forward"] > .99 and not steps[0]["inside"]
    request[0, deer] = B.SHELTER
    world.step(request)
    steps.append(sample(int(B.SHELTER)))
    np.testing.assert_array_equal(world.pos[0, deer], start)
    assert not steps[-1]["inside"]

    request[0, deer] = B.ACTION_GROUPS["walk"][0]
    world.step(request)
    steps.append(sample(int(request[0, deer])))
    assert steps[-1]["inside"]
    return {"seed": seed, "shelter": [30., 30., 5.], "steps": steps}


if __name__ == "__main__":
    config = B.load_r9_config(TRAINING_ROOT / "configs/v3_r9_fauna_motion.yaml")
    counts = {species: [int(species == "deer")] * 2 for species in B.species_of(config)}
    config = B.override(config, {"counts": counts, "world": {"shelters": {"fixed": [[30., 30., 5.]]}}})
    print(json.dumps([run_case(config, seed) for seed in (44190, 44191)], indent=2))

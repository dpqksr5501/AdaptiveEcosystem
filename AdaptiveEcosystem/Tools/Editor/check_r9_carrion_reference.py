"""Exercise the unchanged R9 M1 carcass transaction with two development seeds.

Run from the repository root with the R9 Python dependencies installed:
    python AdaptiveEcosystem/Tools/Editor/check_r9_carrion_reference.py
"""

import argparse
import json
import sys
from hashlib import sha256
from pathlib import Path

import numpy as np

TRAINING_ROOT = Path(__file__).resolve().parents[3] / "herbivore_rl"
sys.path.insert(0, str(TRAINING_ROOT))

from env_v2 import r9_body as B
from env_v2 import r9_brains as BR
from env_v2.r9_world import R9World


def run_case(config, seed, places, request, wolf_positions, expected_eaters):
    world = R9World(config, [seed])
    deer = int(world.sp_lo[B.DEER])
    first_wolf = int(world.sp_lo[B.WOLF])
    wolves = [first_wolf, first_wolf + 1]
    world.pos[0, [deer, *wolves]] = [(50., 50.), *wolf_positions]
    world.E[0, wolves] = .5
    world.vel[:] = 0.
    world.disp[:] = 0.
    world.refresh()
    initial_stock = 4.
    world._add_carcass(0, (30., 30.), initial_stock, int(world.kin_id[0, deer]), B.DEER, 999, 0, places=places)
    actions = np.full((1, world.S), B.WATCH, dtype=np.int64)
    actions[0, wolves] = request
    world.step(actions)

    last_payment = world._gain_u[0, wolves, B.MEAT]
    paid = float(world.st["eaten_units"][0, B.WOLF, B.MEAT])
    remaining = float(world.carc_meat[0].sum())
    decayed = float(world.st["meat_decayed"][0])
    np.testing.assert_array_equal(world.pos[0, wolves], wolf_positions)
    np.testing.assert_array_equal(last_payment > 0., expected_eaters)
    np.testing.assert_allclose(initial_stock - paid - remaining - decayed, 0., rtol=0., atol=1e-12)
    return {
        "seed": seed, "places": places, "request": "eat" if request == B.EAT else "watch",
        "wolf_positions": wolf_positions, "last_step_meat_by_wolf": last_payment.tolist(),
        "total_meat_paid": paid, "meat_remaining": remaining, "meat_decayed": decayed,
    }


def run_learned_encounter(config, seed, brains, separation, initial_meat, leopard_health=1.):
    world = R9World(config, [seed], record=True)
    species = [B.WOLF, B.LEOPARD]
    slots = [int(world.sp_lo[kind]) for kind in species]
    world.pos[0, slots] = [(30. - separation / 2, 30.), (30. + separation / 2, 30.)]
    world.head[0, slots] = [(1., 0.), (-1., 0.)]
    world.E[0, slots] = .5
    world.hp[0, slots] = [1., leopard_health]
    world.born[0, slots] = world.t[0] - 2. * world.sb["maturity"][0, slots]
    world.vel[:] = 0.
    world.disp[:] = 0.
    for kind, brain in zip(species, brains):
        world.set_controller(0, kind, BR.Controller(brain, False, "fauna_r2"))
    if initial_meat:
        world._add_carcass(0, (30., 30.), initial_meat, 0, B.DEER, 999, 0, places=2)
    world.refresh()

    first_actions = None
    first_death = None
    minimum_distance = separation
    eat_requests = np.zeros(2, dtype=int)
    previous_positions = world.pos[0, slots].copy()
    path_length = np.zeros(2)
    for decision in range(1, 121):
        actions = world.decide()
        eat_requests += actions[0, slots] == B.EAT
        if first_actions is None:
            first_actions = [B.ACTION_NAMES[actions[0, slot]] for slot in slots]
        _, _, done, _ = world.step(actions)
        if done[0, slots].any():
            first_death = [name for name, died in zip(("wolf", "leopard"), done[0, slots]) if died]
            break  # Keep the observations scoped to the two founders.
        positions = world.pos[0, slots]
        path_length += np.linalg.norm(positions - previous_positions, axis=1)
        previous_positions = positions.copy()
        minimum_distance = min(minimum_distance, float(np.linalg.norm(world.pos[0, slots[0]] - world.pos[0, slots[1]])))

    paid = world.st["eaten_units"][0, species, B.MEAT]
    if first_death is None:
        np.testing.assert_allclose(paid.sum() + world.carc_meat[0].sum() + world.st["meat_decayed"][0],
                                   initial_meat, rtol=0., atol=1e-12)
    return {"seed": seed, "initial_separation": separation, "initial_meat": initial_meat,
            "initial_leopard_health": leopard_health, "path_length_wolf_then_leopard": path_length.tolist(),
            "decisions": decision, "first_actions": first_actions,
            "minimum_sampled_distance": minimum_distance, "eat_requests_wolf_then_leopard": eat_requests.tolist(),
            "paid_wolf_then_leopard": paid.tolist(),
            "bites": world.events["bites"], "first_death": first_death}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learned-encounter", action="store_true", help="Run the saved Fauna wolf and leopard policies")
    args = parser.parse_args()
    config = B.load_r9_config(TRAINING_ROOT / "configs/v3_r9_fauna_motion.yaml")
    counts = {"deer": [1, 1], "wolf": [2, 2], "boar": [0, 0], "buffalo": [0, 0], "leopard": [0, 0], "fox": [0, 0]}
    config = B.override(config, {"counts": counts, "world": {"shelters": {"fixed": [[57., 57., 2.]]}}})
    near = [(30.3, 30.), (30., 30.6)]
    far = [(35., 30.), (30., 35.)]
    cases = [(1, B.EAT, near, [True, False]), (2, B.EAT, near, [True, True]),
             (2, B.WATCH, near, [False, False]), (2, B.EAT, far, [False, False])]
    prescribed = [run_case(config, seed, *case) for seed in (44190, 44191) for case in cases]
    if not args.learned_encounter:
        print(json.dumps(prescribed))
        sys.exit(0)
    fauna_config = B.load_r9_config(TRAINING_ROOT / "configs/v3_r9_fauna.yaml")
    pair = {name: [int(name in ("wolf", "leopard"))] * 2 for name in counts}
    fauna_config = B.override(fauna_config, {"counts": pair, "world": {"shelters": {"fixed": [[57., 57., 2.]]}}})
    pack = TRAINING_ROOT / "results/v3/r9/packs/fauna_r2"
    paths = [pack / "wolf/wolf_r2_6989248.npz", pack / "leopard/leopard_r2_5633280.npz"]
    brains = [BR.load_brain(path, fauna_config, kind) for path, kind in zip(paths, (B.WOLF, B.LEOPARD))]
    learned = [run_learned_encounter(fauna_config, seed, brains, gap, meat)
               for seed in (44190, 44191) for gap in (1.5, 5.) for meat in (0., .2)]
    for case in learned:
        assert (case["paid_wolf_then_leopard"][1] > 0) == (case["initial_separation"] == 1.5 and case["initial_meat"] > 0)
    injured = [run_learned_encounter(fauna_config, seed, brains, 1.5, meat, leopard_health=.35)
               for seed in (44190, 44191) for meat in (0., .2)]
    print(json.dumps({"prescribed_meals": prescribed, "fauna_r2_wolf_leopard": {
        "brain_sha256": {path.name: sha256(path.read_bytes()).hexdigest() for path in paths},
        "cases": learned, "injured_leopard_cases": injured,
    }}))

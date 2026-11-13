"""R9 동물 세계 대조 덤프 (parity/dump_parity.py 를 저장소 파이썬으로 옮긴 판). 형식은 'R9DUMP 1' 그대로.

2026-11-13 세션 스크래치(SP/r9/ue_demo/fauna/{parity,integrate}/dump_fauna.py — 두 판이 같았음)에서 저장소로 옮겼다
(RL_R9_TURN_EFFORT_DESIGN.md 7-1). 이 파일이 있는 herbivore_rl 의 r9_world 를 그대로 싣는다 (경로 고정 없음):
  --config v3_r9.yaml              저장소 S′ 세 종 세계 (지금 C++ 코어의 기준과 같은지 확인용 — CORE_FAUNA.md 1 절)
  --config v3_r9_fauna.yaml        동물 세계 6 종 (body_common.fauna: R1·P1·R2·R3·R6·R7)
  --config v3_r9_fauna_motion.yaml 동물 세계 + 몸 움직임 M1 회전 한계 (body_common.motion — ParityChain chain_motion.txt, 설계 7-2)
  설정은 이름(configs/ 안), herbivore_rl 기준 상대 경로, 절대 경로 모두 된다.

    python -I -B -X utf8 results/v3/r9/dump_fauna.py --config v3_r9_fauna.yaml --seed 46901 --counts 24 4 8 6 2 4 --decisions 600 --out out/x.txt

두뇌: --brain deer=<npz> … (MLP — 몸 해시 검사는 --no-body-check 로 끌 수 있음, 데모 npz 를 S′ 저장소 세계에 쓸 때), 나머지 종은
      규칙 두뇌(RULE_DEER·RULE_WOLF·RULE_BOAR·RULE_BUFFALO·RULE_LEOPARD·RULE_FOX). --actions mix 면 결정의 일부를 무작위로 바꾼다.
더한 줄 (동물 세계일 때만 — S′ 덤프는 옛 줄 그대로):
  @scene   fauna_on · body_bite_k · body_hide · body_strike_k · body_gore · body_gore_r · body_camo · body_recover · fauna_c23 (NS·NS)
           · fauna_age23 (65) · const_fauna_*  (+ 모든 덤프에 body_recover)
  FULL     gore_cd (S) · carc_places (M) · pair_slot (짝 칸 번호 — 모든 덤프)
  @step    gore_permutation (그 스텝에 뽑은 들이받기 순서 — 들이받는 몸이 있는 장면은 스텝마다 뽑음)
  @scene   body_hash (NS, u64 — 종별 몸 해시 r9_body.body_hash: C++ 가 두뇌 머리글 body_hash 와 대조, 설계 7-2) — 모든 덤프
몸 움직임 줄 (body_common.motion 이 있을 때만 — 없으면 옛 줄 그대로, C++ 는 motion_on 이 없으면 꺼짐으로 읽음):
  @scene   motion_on · motion_turn · motion_effort (i64 0/1) · turn 이 켜지면 body_turn_c · body_turn_s · body_lat_u (NS, f64 %.17g —
           load_body 가 불러올 때 한 번 셈한 cos Δb · sin Δb · lat_accel_mps2/112.5, C++ 는 삼각함수를 부르지 않음, 설계 3-1)
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.dont_write_bytecode = True
REPO_HR = Path(__file__).resolve().parents[3]          # herbivore_rl/ (results/v3/r9/dump_fauna.py)
sys.path.insert(0, str(REPO_HR))

import numpy as np  # noqa: E402

from env_v2 import r9_body as B  # noqa: E402
from env_v2 import r9_brains as BR  # noqa: E402
from env_v2 import r9_life as L  # noqa: E402
from env_v2 import r9_world as W  # noqa: E402

SLOT_F64_2 = ("pos", "head", "vel", "disp", "dir_cmd", "knock_dir")
SLOT_F64 = ("E", "R", "stam", "hp", "born", "next_birth", "g_speed", "g_size", "resp_t")
SLOT_I64 = ("kin_id", "uid", "sex", "act", "bite_cd", "knock_left", "generation", "parent_a", "parent_b", "offspring")
SLOT_B = ("alive", "stam_lock", "mating")
GRIDS = ("grass", "grass_cap", "grass_regen", "root", "root_cap", "root_regen")
RULE_OF = {"deer": "RULE_DEER", "wolf": "RULE_WOLF", "boar": "RULE_BOAR", "buffalo": "RULE_BUFFALO", "leopard": "RULE_LEOPARD",
           "fox": "RULE_FOX"}


class Out:
    def __init__(self, path: Path):
        self.f = open(path, "w", encoding="ascii", newline="\n")

    def head(self, *words):
        self.f.write("@" + " ".join(str(w) for w in words) + "\n")

    def put(self, name: str, a, kind: str):
        if kind == "u64":
            a = np.asarray([int(x) for x in np.asarray(a, dtype=object).ravel()], dtype=np.uint64).reshape(np.shape(a))
        a = np.asarray(a)
        if kind == "f64":
            vals = " ".join("%.17g" % float(x) for x in a.ravel())
        elif kind == "f32":
            vals = " ".join("%.9g" % float(x) for x in a.astype(np.float32).ravel())
        elif kind == "u64":
            vals = " ".join(str(int(x)) for x in a.ravel())
        elif kind in ("i64", "b"):
            vals = " ".join(str(int(x)) for x in a.astype(np.int64).ravel())
        else:
            raise ValueError(kind)
        self.f.write(f"{name} {kind} {a.ndim} {' '.join(str(d) for d in a.shape)} {vals}\n".replace("  ", " "))

    def close(self):
        self.f.close()


class RecGen:
    """난수 발생기 감싸기: 부른 이름·결과를 (t, 이름, 값) 으로 남긴다. 흐름은 그대로."""

    def __init__(self, g, w, log, tag):
        self._g, self._w, self._log, self._tag = g, w, log, tag

    def __getattr__(self, name):
        f = getattr(self._g, name)

        def wrap(*a, **k):
            r = f(*a, **k)
            self._log.append((int(self._w.t[0]), self._tag + "_" + name, np.asarray(r, dtype=np.float64).ravel()))
            return r
        return wrap


def full_state(o: Out, w):
    o.put("t", w.t[:1], "i64")
    o.put("slot_sp", w.slot_sp, "i64")
    for n in SLOT_F64_2:
        o.put(n, getattr(w, n)[0], "f64")
    for n in SLOT_F64:
        o.put(n, getattr(w, n)[0], "f64")
    for n in SLOT_I64:
        o.put(n, getattr(w, n)[0], "i64")
    for n in SLOT_B:
        o.put(n, getattr(w, n)[0], "b")
    o.put("mem", w.mem[0], "f64")
    for n in GRIDS:
        o.put(n, getattr(w, n)[0], "f64")
    o.put("cover_cell", w.cover_cell[0], "b")
    o.put("carc_ok", w.carc_ok[0], "b")
    o.put("carc_pos", w.carc_pos[0], "f64")
    o.put("carc_meat", w.carc_meat[0], "f64")
    o.put("carc_meat0", w.carc_meat0[0], "f64")
    o.put("carc_t", w.carc_t[0], "f64")
    o.put("carc_kin", w.carc_kin[0], "i64")
    o.put("next_uid", w.next_uid[:1], "i64")
    if w.body.fauna:
        o.put("gore_cd", w.gore_cd[0], "i64")
        o.put("carc_places", w.carc_places[0], "i64")
    if w.life.pair_on.any():
        on = np.nonzero(w.life.pair_on[0])[0]
        o.put("pair", np.stack([w.life.pair_a[0, on], w.life.pair_b[0, on], w.life.pair_due[0, on].astype(np.int64)], 1), "i64")
        o.put("pair_slot", on, "i64")            # 짝 칸 번호 p (C++ Pair::Slot — 새 짝은 비어 있는 가장 낮은 칸)


def scene_const(o: Out, w, cfg, counts, seed, args):
    bd = w.body
    NS = w.NS
    o.put("seed", [seed], "i64")
    o.put("counts", counts, "i64")
    o.put("world_size", [w.size], "f64")
    o.put("cell", [w.cell], "f64")
    o.put("G", [w.G], "i64")
    o.put("sp_lo", w.sp_lo, "i64")
    o.put("sp_hi", w.sp_hi, "i64")
    o.put("carcass_slots", [w.M], "i64")
    o.put("run_mult", w.run_mult[0], "f64")
    o.put("juv_frac", w.juv_frac[0], "f64")
    o.put("kin_perm", w.kin_perm[0], "i64")
    o.put("s_w", [int(w.s_w[0])], "u64")
    o.put("s_q", [int(x) for x in w.s_q[0]], "u64")
    ok = w.cov_ok[0]
    o.put("shelters", np.c_[w.cov_c[0][ok], w.cov_r[0][ok]], "f64")
    for f in ("size0", "walk_speed", "run_speed", "accel", "stam_drain", "stam_recover", "see_r", "fov_cos", "head_down", "smell_r",
              "drain", "reserve_cap", "refill_e", "refill_frac", "weak_e", "weak_speed", "hp_regen", "bite_r", "maturity", "mass_kg",
              "food_density_ref", "food_here_ref", "max_founder_age", "founder_variation", "first_birth_base", "first_birth_spread",
              "female_frac", "child_female_frac"):
        o.put("body_" + f, getattr(bd, f), "f64")
    for f in ("has_hp", "shelter_enter", "counter", "growth_smooth"):
        o.put("body_" + f, getattr(bd, f), "b")
    for f in ("founder_kind", "sex_mode"):
        o.put("body_" + f, getattr(bd, f), "i64")
    o.put("body_eats", bd.eats, "b")
    o.put("body_eat_rate", bd.eat_rate, "f64")
    o.put("body_e_per_unit", bd.e_per_unit, "f64")
    o.put("body_bites", bd.bites, "b")
    o.put("diet_rank", w._diet_rank[[int(w.sp_lo[s]) for s in range(NS)]], "i64")
    cm = bd.common
    o.put("gait_drain", cm["gait_drain"], "f64")
    o.put("life_on", [0 if args.no_life else 1], "i64")
    ct, bt, bd2, cc = cm["counter"], cm["bite"], cm["bite_damage"], cm["carcass"]
    br, rz, rs = cm["breed"], cfg["randomize"], cfg["respawn"]
    consts = dict(
        stamina_lock=cm["stamina_lock"], stamina_unlock=cm["stamina_unlock"], wound_speed=cm["wound_speed"], eat_min=cm["eat_min"],
        bite_cone_cos=bt["cone_cos"], bite_approach_min=bt["approach_min"], bite_cooldown=bt["cooldown"],
        counter_hp_min=ct["hp_min"], counter_cone_cos=ct["cone_cos"], counter_damage=ct["damage"], counter_lerp0=ct["age_lerp"][0],
        counter_lerp1=ct["age_lerp"][1], counter_knock_step=ct["knock_step"], counter_knock_steps=ct["knock_steps"],
        counter_nobite_steps=ct["nobite_steps"], counter_self_damage=ct["self_damage"], bite_base=bd2["base"],
        carc_meat_frac=cc["meat_frac"], carc_kg_per_unit=cc["kg_per_unit"], carc_places=cc["places"], carc_eat_r=cc["eat_r"],
        carc_decay_steps=cc["decay_steps"], shelter_push=cm["shelter_push"],
        breed_e_min=br["e_min"], breed_hp_min=br["hp_min"], breed_gestation=br["gestation"], breed_recover=br["recover"],
        breed_retry=br["retry"], breed_cost=br["cost"], breed_child_e=br["child_e"], breed_child_fat=br["child_fat"],
        breed_scan_num=br["scan_num"], breed_scan_den=br["scan_den"], breed_generation_cap=br["generation_cap"], breed_clear_r=br["clear_r"],
        fat_init_lo=rz["fat_init"][0], fat_init_hi=rz["fat_init"][1], start_energy=rz["start_energy"],
        respawn_newborn_frac=rs["newborn_frac"], respawn_far_r=rs["far_r"], respawn_candidates=rs["candidates"],
        respawn_ring_r0=1.1, respawn_ring_dr=0.2, grass_regen_mult=float(w.grass_mult[0]), root_regen_mult=float(w.root_mult[0]))
    for k_, v_ in consts.items():
        o.put("const_" + k_, [float(v_)], "f64")
    for k_, v_ in B.OBS_NORM.items():
        o.put("norm_" + k_, [float(v_)], "f64")
    for k_, v_ in B.SENSE.items():
        o.put("sense_" + k_, [float(v_)], "f64")
    o.put("body_mate_r", bd.mate_r, "f64")
    o.put("body_birth_r", bd.birth_r, "f64")
    o.put("body_birth_grace", bd.birth_grace, "f64")
    o.put("body_pair_block", bd.pair_block, "b")
    o.put("body_birth_block", bd.birth_block, "b")
    o.put("body_pending_needs_parent", bd.pending_needs_parent, "b")
    o.put("dir8", B.DIR8, "f64")
    o.put("golden8", B.GOLDEN8, "f64")
    o.put("body_recover", np.asarray(w.rules.recover_sp, dtype=np.float64), "f64")
    o.put("body_hash", [B.body_hash(cfg, n) for n in w.names], "u64")     # 설계 7-2: 두뇌 머리글 body_hash 대조용 (모든 덤프)
    if bd.motion:                                                         # 몸 움직임 (TURN_EFFORT 3-1·7-1) — 블록이 있을 때만
        o.put("motion_on", [1], "i64")
        o.put("motion_turn", [int(bd.motion_turn)], "i64")
        o.put("motion_effort", [int(bd.motion_effort)], "i64")
        if bd.motion_turn:
            o.put("body_turn_c", bd.turn_c, "f64")
            o.put("body_turn_s", bd.turn_s, "f64")
            o.put("body_lat_u", bd.lat_u, "f64")
    if bd.fauna:
        fz = w._fz
        o.put("fauna_on", [1], "i64")
        for f in ("bite_k", "hide", "strike_k", "gore_r", "camo"):
            o.put("body_" + f, getattr(bd, f), "f64")
        o.put("body_gore", bd.gore, "b")
        o.put("fauna_c23", bd.c23, "f64")
        o.put("fauna_age23", L.AGE23, "f64")
        for k_ in ("gore_cone", "gore_appr", "gore_cd", "camo_s0", "camo_span", "cp_per", "cp_min", "cp_max"):
            o.put("const_fauna_" + k_, [float(fz[k_])], "f64")


def step_debug(o: Out, w):
    o.put("dbg_gait", w._gait[0], "i64")
    o.put("dbg_ekind", w._ekind[0], "i64")
    o.put("dbg_emult", w._emult[0], "f64")
    o.put("dbg_gain_u", w._gain_u[0], "f64")
    o.put("dbg_edge1", np.where(np.isfinite(w._edge1[0]), w._edge1[0], 1e300), "f64")
    o.put("dbg_vel_free", w._vel_free[0], "f64")


def load_mlp(path: str, cfg: dict, sp: int, check: bool) -> BR.MlpBrain:
    if check:
        return BR.load_brain(Path(path), cfg, sp)
    import json
    with np.load(Path(path), allow_pickle=False) as z:
        weights = {k: np.array(z[k]) for k in BR.NPZ_WEIGHT_KEYS}
        meta = json.loads(str(z["meta_json"][()]))
    return BR.MlpBrain(name=f"raw:{Path(path).name}", kind="mlp", species=sp, n_state=0, weights=weights, meta=meta)


def chain(a, w, o, log, rng_mix):
    """이어 돌리기 덤프 (--chain-every N): @decision d 마다 actions (d % N == 0 이면 FULL 상태·obs 도), @step d s 마다 그 스텝 난수
    (bite_permutation · gore_permutation · resp_*). C++ 은 @scene 에서 시작해 덤프 상태로 되돌리지 않고 끝까지 이어 돌린다."""
    st_of = {}

    def hook(world, dead, extra):
        o.head("step", st_of["d"], st_of["s"])
        for t_, name, val in [x for x in log if x[0] == int(world.t[0]) - 1]:
            o.put(name, val, "f64")
        dd = np.nonzero(dead[0])[0]
        if len(dd):
            o.put("dead", dd, "i64")
            o.put("dead_cause", world.dead_cause[0, dd], "i64")
        st_of["s"] += 1
    w.step_hook = hook
    for d in range(a.decisions):
        o.head("decision", d)
        if d % a.chain_every == 0:
            full_state(o, w)
            o.put("obs", w._obs[0], "f32")
        act = w.decide()
        if a.actions != "learned":
            r = rng_mix.integers(0, B.N_ACTIONS, act.shape)
            pick = np.ones(act.shape, bool) if a.actions == "random" else (rng_mix.random(act.shape) < a.mix_p)
            act = np.where(pick, r, act)
        o.put("actions", act[0], "i64")
        log.clear()
        st_of["d"], st_of["s"] = d, 0
        w.step(act)
    o.head("final")
    full_state(o, w)
    o.put("obs", w._obs[0], "f32")
    o.close()
    st = w.stats_snapshot()
    extra = ""
    if "gore" in st:
        extra = f" gore {int(st['gore'][0].sum())} bite_pairs {int(st['bite_pairs'][0].sum())} in_shelter {int(st['bite_in_shelter'][0].sum())}"
    print(a.out, "chain", a.decisions, "deaths", st["deaths"][0].tolist(), "bites", st["bites"][0].tolist(), "respawns",
          st["respawns"][0].tolist(), "births", int(w.life.births.sum()), extra)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="v3_r9_fauna.yaml")
    ap.add_argument("--seed", type=int, default=46901)
    ap.add_argument("--counts", type=int, nargs="+", required=True)
    ap.add_argument("--decisions", type=int, default=40)
    ap.add_argument("--skip", type=int, default=0)
    ap.add_argument("--actions", choices=("learned", "random", "mix"), default="mix")
    ap.add_argument("--mix-p", type=float, default=0.15)
    ap.add_argument("--no-life", action="store_true")
    ap.add_argument("--stochastic", action="store_true")
    ap.add_argument("--brain", action="append", default=[], help="<species>=<npz>")
    ap.add_argument("--no-body-check", action="store_true")
    ap.add_argument("--keep-first", type=int, default=-1)
    ap.add_argument("--keep-events", type=int, default=-1)
    ap.add_argument("--every", type=int, default=0)
    ap.add_argument("--per-kind", type=int, default=6)
    ap.add_argument("--chain-every", type=int, default=0,
                    help="이어 돌리기 덤프: 모든 결정의 행동·모든 스텝의 난수를 남기고 FULL 상태·관측은 이 간격(결정)마다만 (C++ chain 대조)")
    ap.add_argument("--out", type=str, required=True)
    a = ap.parse_args(argv)
    select = a.keep_first >= 0 or a.keep_events >= 0
    keep_first, keep_events = max(a.keep_first, 0), max(a.keep_events, 0)

    cp = Path(a.config)
    if not cp.is_absolute():
        cp = REPO_HR / cp if (REPO_HR / cp).is_file() else REPO_HR / "configs" / cp
    cfg = B.load_r9_config(cp)
    names = B.species_of(cfg)
    NS = len(names)
    if len(a.counts) != NS:
        raise SystemExit(f"--counts needs {NS} numbers ({names})")
    if a.no_life:
        W.R9World._breed = lambda self: L.BreedEvents.empty(self.K, self.S)
    w = W.R9World(cfg, [a.seed], counts=np.asarray([a.counts], np.int64))
    npz = dict(x.split("=", 1) for x in a.brain)
    mlp = {}
    for sp, n in enumerate(names):
        if n in npz:
            br = load_mlp(npz[n], cfg, sp, not a.no_body_check)
            mlp[sp] = br
            w.set_controller(0, sp, BR.Controller(br, bool(a.stochastic), "learned"))
        else:
            w.set_controller(0, sp, BR.Controller(BR.make_rule(RULE_OF[n], cfg, sp), bool(a.stochastic), "rule"))
    log: list = []
    w.rng_bite[0] = RecGen(w.rng_bite[0], w, log, "bite")
    w.rng_resp[0] = RecGen(w.rng_resp[0], w, log, "resp")
    if w.rng_gore[0] is not None:
        w.rng_gore[0] = RecGen(w.rng_gore[0], w, log, "gore")
    rng_mix = np.random.default_rng([a.seed, 777])
    o = Out(Path(a.out))
    o.f.write("R9DUMP 1\n")
    o.head("scene")
    scene_const(o, w, cfg, a.counts, a.seed, a)
    full_state(o, w)
    o.put("obs", w._obs[0], "f32")
    hooks: list = []

    def hook(world, dead, extra):
        hooks.append(True)
        if dumping[0]:
            d, s = dumping[1], len(hooks) - 1
            o.head("step", d, s)
            ev = [x for x in log if x[0] == int(world.t[0]) - 1]
            for t_, name, val in ev:
                o.put(name, val, "f64")
            resp = np.nonzero(extra["respawned"][0])[0]
            if len(resp):
                o.put("respawned", resp, "i64")
            dd = np.nonzero(dead[0])[0]
            if len(dd):
                o.put("dead", dd, "i64")
                o.put("dead_cause", world.dead_cause[0, dd], "i64")
            step_debug(o, world)
            full_state(o, world)
    w.step_hook = hook
    dumping = [False, -1]
    if a.chain_every > 0:
        return chain(a, w, o, log, rng_mix)
    real = o.f
    kept_ev = 0
    kept = []
    per_kind: dict = {}
    _snap = w.stats_snapshot

    def snap():
        s = _snap()
        s["life_births"] = int(w.life.births.sum())
        return s
    w.stats_snapshot = snap
    for d in range(a.skip + a.decisions):
        dumping[0] = d >= a.skip
        dumping[1] = d
        hooks.clear()
        on_grid = False
        if select:
            on_grid = a.every > 0 and (d - a.skip) % a.every == 0
            dumping[0] = d >= a.skip and ((d - a.skip) < keep_first or on_grid or kept_ev < keep_events)
            o.f = io.StringIO()
            st0 = w.stats_snapshot()
        if dumping[0]:
            o.head("decision", d)
            full_state(o, w)
            o.put("obs", w._obs[0], "f32")
            for sp, br in mlp.items():
                lo, hi = int(w.sp_lo[sp]), int(w.sp_hi[sp])
                al = np.nonzero(w.alive[0, lo:hi])[0] + lo
                o.put(f"logit_slots_{sp}", al, "i64")
                o.put(f"logits_{sp}", BR.forward_np(br.weights, w._obs[0, al]), "f32")
        act = w.decide()
        if a.actions != "learned":
            r = rng_mix.integers(0, B.N_ACTIONS, act.shape)
            pick = np.ones(act.shape, bool) if a.actions == "random" else (rng_mix.random(act.shape) < a.mix_p)
            act = np.where(pick, r, act)
        if dumping[0]:
            o.put("actions", act[0], "i64")
        log.clear()
        w.step(act)
        if select:
            buf, o.f = o.f, real
            if dumping[0]:
                st1 = w.stats_snapshot()
                ev = []
                for nm_, key in (("bite", "bites"), ("death", "deaths"), ("respawn", "respawns"), ("gore", "gore")):
                    if key in st1 and st1[key][0].sum() > st0[key][0].sum():
                        ev.append(nm_)
                if st1["eaten_units"][0][:, B.MEAT].sum() > st0["eaten_units"][0][:, B.MEAT].sum():
                    ev.append("meat")
                if st1["eaten_units"][0][:, B.ROOT].sum() > st0["eaten_units"][0][:, B.ROOT].sum():
                    ev.append("root")
                if st1["bites"][0][:, 2].sum() > st0["bites"][0][:, 2].sum():
                    ev.append("counter")
                if "bite_in_shelter" in st1 and st1["bite_in_shelter"][0].sum() > st0["bite_in_shelter"][0].sum():
                    ev.append("bite_in_shelter")
                if st1["life_births"] > st0["life_births"]:
                    ev.append("birth_credit")
                first = (d - a.skip) < keep_first or on_grid
                fresh = [e for e in ev if per_kind.get(e, 0) < a.per_kind]
                if first or (fresh and kept_ev < keep_events):
                    real.write(buf.getvalue())
                    kept.append((d, ev))
                    for e in ev:
                        per_kind[e] = per_kind.get(e, 0) + 1
                    if not first:
                        kept_ev += 1
    if select:
        print("kept decisions:", kept)
    if a.decisions:
        o.head("final")
        full_state(o, w)
        o.put("obs", w._obs[0], "f32")
    o.close()
    st = w.stats_snapshot()
    extra = ""
    if "gore" in st:
        extra = f" gore {st['gore'][0].tolist()} bite_pairs_sum {int(st['bite_pairs'][0].sum())} in_shelter {int(st['bite_in_shelter'][0].sum())}"
    print(a.out, "deaths[sp,cause]", st["deaths"][0].tolist(), "bites", st["bites"][0].tolist(), "respawns", st["respawns"][0].tolist(), extra)


if __name__ == "__main__":
    main()

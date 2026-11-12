"""R9 동물 세계 1 단계 보고 — 장면 S1·S2 와 자연 세계 N 의 상호작용 지표 (동물 설계 AdaptiveEcosystem/Docs/RL_Policy/
RL_R9_SPECIES_TRAITS.md 7-2 '1a'). 보고만 한다 — 어떤 숫자도 판정·합격선이 아니다.

    python -X utf8 results/v3/r9/fauna_report.py --flight ckpt/r9_fauna/flight/A                 # 시험 비행 결과 (약 30 분)
    python -X utf8 results/v3/r9/fauna_report.py --rules-only --only S1,S2 --worlds 8 --name smoke  # 규칙 두뇌만 (몸 점검)
    python -X utf8 results/v3/r9/fauna_report.py --brains wolf=ckpt/…/wolf.npz buffalo=ckpt/…/buffalo.npz

두뇌: --flight <dir> 의 flight.json (0 단계 v0 + 1·2 단계 마지막 판) 또는 --brains 종=npz. 없는 종은 옛 세 종이면 v0 (--start-dir),
그것도 없으면 규칙 두뇌. 학습 두뇌·규칙 두뇌 두 판을 나란히 적는다(--rules-only 면 규칙만). 행동은 가장 높은 칸(판정과 같음,
--stochastic 이면 확률).

S1 (T-A 장면, '할 수 있나'): 사슴·멧돼지·표범·여우 0, 물소 무리(어른 3 + 송아지 1, 나이비 0.2)를 가운데 3 단위 안, 늑대 n ∈
   {1,2,3,4,6} 을 8~12 단위 밖 한쪽에 무리로(물소 쪽을 봄). 칸마다 40 세계(시드 46680~46719) × 300 결정. 장면 세계는 다시 나기가
   없다(죽은 칸은 빈다 — 장면 도구일 뿐 몸 규칙은 같다). 칸마다 어른·송아지 죽임 몫, 늑대 죽음·HP 잃음(마리당), 받기 수,
   앞자리 몫 = 물소 3 단위 안에 있던 늑대 결정 가운데 그 물소의 정면 ±75.5°(반격 원뿔) 안에 있던 몫 [해석].
S2 (늑대 1 ↔ 표범 1): 은신처를 구석 작은 것 하나로 비우고 6 단위 마주 보게, 40 세계 × 150 결정: 누가 죽었나·둘 다·물림 수.
N (자연 세계): 학습 세계 꼴 20 세계(46680~46699) × 1,350 결정, 두 구성(기본 / buffalo_land 꼴: 사슴 0·2·4, 물소 4·6·8, 늑대 4·6).
   T-A 자연 · T-C 물소 방어 자세 · T-D 표범 먹잇감(Jacobs D) · T-H 종 사이 죽임 표 · T-K 감각 붐빔 · T-M 같은 종 모임 · C0-F9 속도.
   정의는 각 함수 머리말과 결과 JSON 'defs' 에 적는다.
결과: results/v3/r9/fauna_reports/<name>.json · .md. md 첫 줄 = "1 단계 평지 — 물소 물가는 2 단계, 첫 밤 결과는 정식 판정이 아님".
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402

from env_v2 import r9_body as B  # noqa: E402
from env_v2 import r9_brains as BR  # noqa: E402
from env_v2.r9_world import R9World, TAG_EVAL  # noqa: E402

FIRST_LINE = "1 단계 평지 — 물소 물가는 2 단계, 첫 밤 결과는 정식 판정이 아님"
SEEDS = (46680, 46720)                              # 7-3: fauna_report 장면·자연 세계
RULE = {0: "RULE_DEER", 1: "RULE_WOLF", 2: "RULE_BOAR", 3: "RULE_BUFFALO", 4: "RULE_LEOPARD", 5: "RULE_FOX"}
CORNER_SHELTER = [[57.0, 57.0, 2.0]]               # 장면: 은신처 하나를 구석에 작게 (사방 비움)
VEL_N = float(B.OBS_NORM["vel"])
APPR_MIN = 0.1                                      # 관측 단위 다가옴 문턱 (규칙 두뇌 approach 0.1 과 같은 뜻)
MIN_EVENTS = 30                                     # 7-2: 칸마다 사건 30 개 넘을 때만 비율을 적는다 [어림]


def _abs(p) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


class SceneWorld(R9World):
    """Scene world: the train world without respawn (a dead slot stays empty) so a scene counts its own individuals. Body rules are
    the world's; only the train-world 'instant respawn' bookkeeping is off."""

    def _respawn(self, dead):
        return np.zeros((self.K, self.S), dtype=bool)


def body_mass(w, k: int, s: int) -> float:
    """kg × g³ × Lerp(0.12, 1, age frac) — the R1 body mass (r9_life.mass_ratio)."""
    g = float(w.g_size[k, s])
    return float(w.sb["mass_kg"][k, s]) * g * g * g * (0.12 + 0.88 * float(w.af[k, s]))


def band(kg: float) -> str:
    return "<20kg" if kg < 20.0 else ("20-80kg" if kg <= 80.0 else ">80kg")


# --------------------------------------------------------------------------- #
# brains
# --------------------------------------------------------------------------- #

def flight_brains(flight: Path) -> dict:
    """{species: npz path} from flight.json: stage 0 v0 (deer, wolf, boar), stage 1 last npz (buffalo, leopard, fox), stage 2 wolf."""
    f = json.loads((flight / "flight.json").read_text(encoding="utf-8"))
    out = {}
    for st in f.get("stages", []):
        for name, r in (st.get("runs") or {}).items():
            if name in B.ALL_SPECIES and r.get("npz"):
                out[name] = str(_abs(r["npz"]))
    return out


def make_controllers(cfg, paths: dict, rules_only: bool, stochastic: bool) -> tuple[dict, dict]:
    """{species index: Controller} and labels. Learned when a path is given and loads in this config's body, else the rule brain."""
    names = B.species_of(cfg)
    ctr, lab = {}, {}
    for s, n in enumerate(names):
        p = None if rules_only else paths.get(n)
        if p:
            b = BR.load_brain(Path(p), cfg, s)
            ctr[s] = BR.Controller(b, bool(stochastic), f"mlp:{Path(p).name}")
            lab[n] = f"mlp:{Path(p).name}"
        else:
            ctr[s] = BR.Controller(BR.make_rule(RULE[s], cfg, s), bool(stochastic), f"rule:{RULE[s]}")
            lab[n] = f"rule:{RULE[s]}"
    return ctr, lab


def set_all(w, ctr: dict) -> None:
    for k in range(w.K):
        for s, c in ctr.items():
            if int(w.caps[s]) > 0:
                w.set_controller(k, s, c)


def scene_cfg(cfg, counts: dict) -> dict:
    patch = {"counts": {n: [int(counts.get(n, 0))] * 2 for n in B.species_of(cfg)},
             "world": {"shelters": {"fixed": CORNER_SHELTER}}}
    return B.override(cfg, patch)


def _install(w, k: int, s: int, pos, head, af: float) -> None:
    """Move an existing individual (scene set-up): position, head, still, full HP / stamina, age fraction af."""
    w.pos[k, s] = np.clip(np.asarray(pos, dtype=np.float64), 0.0, w.size)
    w.head[k, s] = head
    w.vel[k, s] = 0.0
    w.disp[k, s] = 0.0
    w.hp[k, s] = 1.0
    w.stam[k, s] = 1.0
    w.stam_lock[k, s] = False
    w.knock_left[k, s] = 0
    w.bite_cd[k, s] = 0
    w.gore_cd[k, s] = 0
    mat = float(w.sb["maturity"][k, s])
    w.born[k, s] = float(w.t[k]) - af * mat if af < 1.0 else float(w.t[k]) - 2.0 * mat


# --------------------------------------------------------------------------- #
# S1 — wolf pack vs buffalo herd
# --------------------------------------------------------------------------- #

def scene_s1(cfg, ctr, n_wolf: int, worlds: int, decisions: int) -> dict:
    """T-A 장면. See the module docstring. Front share = among wolf decisions within 3 units of an alive buffalo, the share inside that
    buffalo's counter cone (head · unit(buffalo → wolf) ≥ body_common.counter.cone_cos)."""
    W_, BU = B.WOLF, B.BUFFALO
    sc = scene_cfg(cfg, {"wolf": n_wolf, "buffalo": 4})
    seeds = [SEEDS[0] + i for i in range(worlds)]
    w = SceneWorld(sc, seeds, record=True)
    lo_w, lo_b = int(w.sp_lo[W_]), int(w.sp_lo[BU])
    c = np.array([30.0, 30.0])
    adults, calves = set(), set()
    for k in range(w.K):
        g = np.random.default_rng([int(w.seeds[k]), TAG_EVAL])
        for i in range(4):
            s = lo_b + i
            p = c if i == 3 else c + 1.5 * B.GOLDEN8[i]
            _install(w, k, s, p, B.DIR8[int(g.integers(0, 8))], 0.2 if i == 3 else 1.0)
            (calves if i == 3 else adults).add((k, int(w.uid[k, s])))
        j = int(g.integers(0, 8))
        d = float(g.uniform(8.0, 12.0))
        base = c + d * B.DIR8[j]
        perp = B.DIR8[(j + 2) % 8]
        for i in range(n_wolf):
            _install(w, k, lo_w + i, base + (i - 0.5 * (n_wolf - 1)) * 1.0 * perp, -B.DIR8[j], 1.0)
        w.mem[k] = 0.0
    w.refresh()
    set_all(w, ctr)
    cone = float(cfg["body_common"]["counter"]["cone_cos"])
    near_n = front_n = 0
    for _ in range(decisions):
        w.step(w.decide())
        for k in range(w.K):
            ws = [s for s in range(lo_w, lo_w + n_wolf) if w.alive[k, s]]
            bs = [s for s in range(lo_b, lo_b + 4) if w.alive[k, s]]
            if not ws or not bs:
                continue
            Pw, Pb, Hb = w.pos[k, ws], w.pos[k, bs], w.head[k, bs]
            dv = Pw[:, None, :] - Pb[None, :, :]                       # buffalo → wolf
            dd = np.sqrt((dv ** 2).sum(-1))
            near = dd <= 3.0
            cs = (dv * Hb[None, :, :]).sum(-1) / np.maximum(dd, 1e-9)
            nw = near.any(1)
            near_n += int(nw.sum())
            front_n += int((near & (cs >= cone)).any(1).sum())
    ev = w.events
    kill_a = sum(1 for e in ev["deaths"] if e["sp"] == BU and (e["k"], e["uid"]) in adults)
    kill_c = sum(1 for e in ev["deaths"] if e["sp"] == BU and (e["k"], e["uid"]) in calves)
    wolf_d = sum(1 for e in ev["deaths"] if e["sp"] == W_)
    st = w.stats_snapshot()
    nw_tot = n_wolf * w.K
    return dict(n_wolf=n_wolf, worlds=w.K, decisions=decisions, adult_kill_frac=kill_a / (3 * w.K), calf_kill_frac=kill_c / w.K,
                adult_kills=kill_a, calf_kills=kill_c, wolf_deaths=wolf_d, wolf_death_frac=wolf_d / nw_tot,
                wolf_hp_lost_per_wolf=float(st["strike_hp_by"][:, W_].sum()) / nw_tot,
                gores=int(st["gore"][:, BU, W_].sum()), gore_kills=int(st["gore"][:, BU, W_, 1].sum()),
                counters=int(st["bite_pairs"][:, W_, BU, 2].sum()), bites=int(st["bite_pairs"][:, W_, BU].sum()),
                front_share=(front_n / near_n) if near_n else None, near_decisions=near_n)


# --------------------------------------------------------------------------- #
# S2 — wolf 1 vs leopard 1
# --------------------------------------------------------------------------- #

def scene_s2(cfg, ctr, worlds: int, decisions: int) -> dict:
    W_, LE = B.WOLF, B.LEOPARD
    sc = scene_cfg(cfg, {"wolf": 1, "leopard": 1})
    w = SceneWorld(sc, [SEEDS[0] + i for i in range(worlds)], record=True)
    sw, sl = int(w.sp_lo[W_]), int(w.sp_lo[LE])
    c = np.array([30.0, 30.0])
    for k in range(w.K):
        g = np.random.default_rng([int(w.seeds[k]), TAG_EVAL])
        d = B.DIR8[int(g.integers(0, 8))]
        _install(w, k, sw, c - 3.0 * d, d, 1.0)
        _install(w, k, sl, c + 3.0 * d, -d, 1.0)
        w.mem[k] = 0.0
    w.refresh()
    set_all(w, ctr)
    for _ in range(decisions):
        w.step(w.decide())
    dead = {(e["k"], e["sp"]) for e in w.events["deaths"]}
    wd = sum(1 for k in range(w.K) if (k, W_) in dead)
    ld = sum(1 for k in range(w.K) if (k, LE) in dead)
    both = sum(1 for k in range(w.K) if (k, W_) in dead and (k, LE) in dead)
    st = w.stats_snapshot()
    bp = st["bite_pairs"].sum(0)
    causes = {}
    for e in w.events["deaths"]:
        key = f"{B.ALL_SPECIES[e['sp']]}:{e['cause']}"
        causes[key] = causes.get(key, 0) + 1
    return dict(worlds=w.K, decisions=decisions, wolf_died=wd, leopard_died=ld, both_died=both, none_died=w.K - len({k for k, _ in dead}),
                bites_wolf_on_leopard=int(bp[W_, LE].sum()), bites_leopard_on_wolf=int(bp[LE, W_].sum()),
                kills_wolf_on_leopard=int(bp[W_, LE, 0]), kills_leopard_on_wolf=int(bp[LE, W_, 0]), death_causes=causes)


# --------------------------------------------------------------------------- #
# N — natural world
# --------------------------------------------------------------------------- #

class NatStats:
    """Per-decision analysis of a natural (train-form) world. All distances in units, approach = displacement toward / 0.9 (the
    observation scale) > 0.1.
      T-A attack episodes on a buffalo: a (wolf, buffalo) pair 'closes' when the wolf is within 3 units and approaches; the episode
          opens when a pair has more than 4 closing decisions (cumulative since the last episode of that buffalo [해석]); participants =
          wolves that closed during it; it ends when no alive wolf is within 6 units for 8 decisions, or the buffalo dies (success =
          died by a wolf bite). Bins: pack size (participants 1·2·3·4·5+) × calf (af < 0.5 at the start) × world deer count ≤ 4 / > 4.
          Per bin: episodes, success share, participants' HP lost (join → end, ≥ 0) and deaths; start means of wolf E and deer within 10.
      T-C buffalo decisions with a threat (nearest alive wolf or leopard within 5 approaching): facing (head · unit(→threat) ≥ 0.7),
          fleeing (a RUN action whose direction points away), goring (a gore by this buffalo in the decision), mean distance to the
          other alive buffalo vs decisions without a threat.
      T-D leopard prey: kills (bite kills by leopards) by species and by mass band (death mass = meat × kg_per_unit / meat_frac),
          encounters = other-species bodies within 10 units of an alive leopard per decision; Jacobs D = (r − p) / (r + p − 2rp).
      T-H kill table from bite / gore events: killer species × dead species × cause (bite | counter | gore), per killer-species day.
      T-K deer decisions with an alive wolf or leopard within 10 units that the deer perceives (eye ∪ ear ∪ nose) but that is not
          among its 6 other-species slots (pushed out by nearer others).
      T-M leopards / foxes: nearest alive same-species distance per decision; joint attacks = target-decisions with ≥ 2 same-species
          bodies of that kind within 5 units approaching it (share of target-decisions with ≥ 1)."""

    def __init__(self, w):
        self.w = w
        K = w.K
        self.ep_open = {}                    # (k, buid) → dict
        self.pair = {}                       # (k, wuid, buid) → closing count
        self.episodes = []
        self.tc = dict(threat=0, facing=0, flee=0, gore=0, kin_d_threat=[], kin_d_calm=[])
        self.td_enc_sp = {}
        self.td_enc_band = {}
        self.tk = dict(near=0, miss=0)
        self.tm = {B.LEOPARD: dict(nn=[], targets=0, joint=0), B.FOX: dict(nn=[], targets=0, joint=0)}
        self.ev_i = dict(deaths=0, bites=0, gores=0)
        self.decisions = 0
        self.K = K

    def _new_events(self, key):
        lst = self.w.events.get(key, [])
        i = self.ev_i[key]
        self.ev_i[key] = len(lst)
        return lst[i:]

    def observe(self) -> None:
        w = self.w
        self.decisions += 1
        deaths = self._new_events("deaths")
        self._new_events("bites")
        gores = self._new_events("gores")
        dead_by = {(e["k"], e["uid"]): e for e in deaths}
        gorers = {(e["k"], e["gorer_uid"]) for e in gores}
        oth, _ = w.obs_maps()
        sp_of = w.slot_sp.astype(np.int64)
        pc = w._pc                                            # perception of the last decision end (the observation's own)
        self._ginv = np.full((w.K, w.S), -1, dtype=np.int64)
        kv, iv = np.nonzero(pc["valid"])
        self._ginv[kv, pc["ic"][kv, iv]] = iv
        for k in range(w.K):
            al = w.alive[k]
            P, Dp, H = w.pos[k], w.disp[k], w.head[k]
            idx = {s_: np.nonzero(al & (sp_of == s_))[0] for s_ in range(w.NS)}
            self._ta(k, idx, P, Dp, dead_by)
            self._tc(k, idx, P, Dp, H, gorers)
            self._td(k, idx, P, al, sp_of)
            self._tk(k, idx, P, oth[k])
            self._tm(k, idx, P, Dp, al, sp_of)

    @staticmethod
    def _appr(P, Dp, a, b):
        """approach of bodies a toward bodies b: (disp_a · unit(p_b − p_a)) / 0.9, (len a, len b); distances too."""
        dv = P[b][None, :, :] - P[a][:, None, :]
        dd = np.sqrt((dv ** 2).sum(-1))
        ap = (Dp[a][:, None, :] * dv).sum(-1) / np.maximum(dd, 1e-9) / VEL_N
        return dd, ap

    def _ta(self, k, idx, P, Dp, dead_by):
        w = self.w
        wl, bl = idx[B.WOLF], idx[B.BUFFALO]
        # close episodes whose buffalo is gone
        for key in [kk for kk in self.ep_open if kk[0] == k]:
            ep = self.ep_open[key]
            s = ep["slot"]
            if w.uid[k, s] != key[1] or not w.alive[k, s]:
                e = dead_by.get(key)
                ep["success"] = bool(e is not None and e["cause"] == "bite" and ep["killer_is_wolf"](e["killer"]))
                self._end(k, key, ep)
        if not len(wl) or not len(bl):
            return
        dd, ap = self._appr(P, Dp, wl, bl)
        close = (dd <= 3.0) & (ap > APPR_MIN)
        for bi, b in enumerate(bl):
            buid = int(w.uid[k, b])
            key = (k, buid)
            for wi, ws in enumerate(wl):
                pk = (k, int(w.uid[k, ws]), buid)
                if close[wi, bi]:
                    self.pair[pk] = self.pair.get(pk, 0) + 1
            ep = self.ep_open.get(key)
            if ep is None:
                if any(self.pair.get((k, int(w.uid[k, ws]), buid), 0) > 4 for ws in wl):
                    wolf_uids = {int(w.uid[k, s_]) for s_ in range(int(w.sp_lo[B.WOLF]), int(w.sp_hi[B.WOLF]))}
                    parts = {int(w.uid[k, ws]): float(w.hp[k, ws]) for wi, ws in enumerate(wl)
                             if self.pair.get((k, int(w.uid[k, ws]), buid), 0) > 0}
                    deer10 = int(((np.sqrt(((P[idx[B.DEER]] - P[b]) ** 2).sum(-1)) <= 10.0)).sum()) if len(idx[B.DEER]) else 0
                    ep = dict(slot=int(b), t0=int(w.t[k]), parts=parts, gap=0, calf=bool(w.af[k, b] < 0.5),
                              deer_world=int(w.counts[k, B.DEER]), deer10=deer10,
                              wolf_e=float(np.mean([w.E[k, ws] for ws in wl if int(w.uid[k, ws]) in parts])),
                              killer_is_wolf=(lambda u, ws_=frozenset(wolf_uids): int(u) in ws_), success=False)
                    self.ep_open[key] = ep
            else:
                for wi, ws in enumerate(wl):
                    u = int(w.uid[k, ws])
                    if close[wi, bi] and u not in ep["parts"]:
                        ep["parts"][u] = float(w.hp[k, ws])
                if (dd[:, bi] <= 6.0).any():
                    ep["gap"] = 0
                else:
                    ep["gap"] += 1
                    if ep["gap"] >= 8:
                        self._end(k, key, ep)

    def _end(self, k, key, ep):
        w = self.w
        alive_u = {int(w.uid[k, s]): s for s in range(int(w.sp_lo[B.WOLF]), int(w.sp_hi[B.WOLF])) if w.alive[k, s]}
        lost, dead = 0.0, 0
        for u, h0 in ep["parts"].items():
            if u in alive_u:
                lost += max(0.0, h0 - float(w.hp[k, alive_u[u]]))
            else:
                lost += h0
                dead += 1
        n = len(ep["parts"])
        self.episodes.append(dict(pack=("5+" if n >= 5 else str(n)), calf=ep["calf"], deer=("le4" if ep["deer_world"] <= 4 else "gt4"),
                                  success=ep["success"], hp_lost=lost, wolf_dead=dead, wolf_e=ep["wolf_e"], deer10=ep["deer10"],
                                  dur=int(w.t[k]) - ep["t0"]))
        for pk in [p for p in self.pair if p[0] == k and p[2] == key[1]]:
            del self.pair[pk]
        del self.ep_open[key]

    def _tc(self, k, idx, P, Dp, H, gorers):
        w = self.w
        bl = idx[B.BUFFALO]
        if not len(bl):
            return
        th = np.concatenate([idx[B.WOLF], idx[B.LEOPARD]])
        for b in bl:
            others = bl[bl != b]
            kin_d = float(np.mean(np.sqrt(((P[others] - P[b]) ** 2).sum(-1)))) if len(others) else None
            threat = None
            if len(th):
                dv = P[b][None, :] - P[th]
                dd = np.sqrt((dv ** 2).sum(-1))
                ap = (Dp[th] * dv).sum(-1) / np.maximum(dd, 1e-9) / VEL_N
                ok = (dd <= 5.0) & (ap > APPR_MIN)
                if ok.any():
                    threat = int(th[np.argmin(np.where(ok, dd, np.inf))])
            if threat is None:
                if kin_d is not None:
                    self.tc["kin_d_calm"].append(kin_d)
                continue
            self.tc["threat"] += 1
            u = P[threat] - P[b]
            u = u / max(float(np.sqrt((u ** 2).sum())), 1e-9)
            if float(H[b] @ u) >= 0.7:
                self.tc["facing"] += 1
            a = int(w.act[k, b])
            if B.RUN_FIRST <= a <= B.RUN_LAST and float(w.dir_cmd[k, b] @ u) < 0.0:
                self.tc["flee"] += 1
            if (k, int(w.uid[k, b])) in gorers:
                self.tc["gore"] += 1
            if kin_d is not None:
                self.tc["kin_d_threat"].append(kin_d)

    def _td(self, k, idx, P, al, sp_of):
        w = self.w
        for le in idx[B.LEOPARD]:
            dd = np.sqrt(((P - P[le]) ** 2).sum(-1))
            near = np.nonzero(al & (sp_of != B.LEOPARD) & (dd <= 10.0))[0]
            for j in near:
                n = B.ALL_SPECIES[int(sp_of[j])]
                self.td_enc_sp[n] = self.td_enc_sp.get(n, 0) + 1
                bd = band(body_mass(w, k, int(j)))
                self.td_enc_band[bd] = self.td_enc_band.get(bd, 0) + 1

    def _tk(self, k, idx, P, oth_k):
        """T-K: a predator the deer PERCEIVES (eye ∪ ear ∪ nose, the world's own perception) within 10 units but that the 6
        other-species slots pushed out (nearer others filled them). Unperceived predators are not crowding."""
        pr = np.concatenate([idx[B.WOLF], idx[B.LEOPARD]])
        if not len(pr):
            return
        pc = self.w._pc
        gi = self._ginv[k]
        perc = pc["perc"][k]
        for d in idx[B.DEER]:
            dd = np.sqrt(((P[pr] - P[d]) ** 2).sum(-1))
            nr = [int(x) for x in pr[dd <= 10.0] if gi[d] >= 0 and gi[int(x)] >= 0 and perc[gi[d], gi[int(x)]]]
            if not nr:
                continue
            self.tk["near"] += 1
            seen = set(int(x) for x in oth_k[d] if x >= 0)
            if any(x not in seen for x in nr):
                self.tk["miss"] += 1

    def _tm(self, k, idx, P, Dp, al, sp_of):
        for sp in (B.LEOPARD, B.FOX):
            lst = idx[sp]
            if not len(lst):
                continue
            tm = self.tm[sp]
            if len(lst) >= 2:
                dv = P[lst][:, None, :] - P[lst][None, :, :]
                dd = np.sqrt((dv ** 2).sum(-1)) + np.eye(len(lst)) * 1e9
                tm["nn"].extend(dd.min(1).tolist())
            tg = np.nonzero(al & (sp_of != sp))[0]
            if not len(tg):
                continue
            dd, ap = self._appr(P, Dp, lst, tg)
            att = ((dd <= 5.0) & (ap > APPR_MIN)).sum(0)
            tm["targets"] += int((att >= 1).sum())
            tm["joint"] += int((att >= 2).sum())

    def summary(self) -> dict:
        w = self.w
        st = w.stats_snapshot()
        names = w.names
        # T-A bins
        bins = {}
        for e in self.episodes:
            key = f"pack{e['pack']}|{'calf' if e['calf'] else 'adult'}|deer_{e['deer']}"
            b = bins.setdefault(key, dict(episodes=0, success=0, hp_lost=0.0, wolf_dead=0, wolf_e=[], deer10=[]))
            b["episodes"] += 1
            b["success"] += int(e["success"])
            b["hp_lost"] += e["hp_lost"]
            b["wolf_dead"] += e["wolf_dead"]
            b["wolf_e"].append(e["wolf_e"])
            b["deer10"].append(e["deer10"])
        for b in bins.values():
            n = b["episodes"]
            b["success_share"] = b["success"] / n if n > MIN_EVENTS else None
            b["wolf_e_mean"] = float(np.mean(b.pop("wolf_e")))
            b["deer10_mean"] = float(np.mean(b.pop("deer10")))
        # T-H kill table from events
        kt = {}
        for e in w.events["bites"]:
            bsp = names[e.get("biter_sp", B.WOLF)]
            psp = names[e["prey_sp"]]
            if e["outcome"] == "kill":
                kt[f"{bsp}>{psp}:bite"] = kt.get(f"{bsp}>{psp}:bite", 0) + 1
            elif e["outcome"] == "counter" and e["wolf_hp"] <= 0.0:
                kt[f"{psp}>{bsp}:counter"] = kt.get(f"{psp}>{bsp}:counter", 0) + 1
        for e in w.events.get("gores", []):
            if e["outcome"] == "kill":
                key = f"{names[e['gorer_sp']]}>{names[e['target_sp']]}:gore"
                kt[key] = kt.get(key, 0) + 1
        days = {n: float(st["alive_steps"][:, s].sum()) / float(B.DAY_STEPS) for s, n in enumerate(names)}
        per_day = {}
        for key, v in kt.items():
            ks = key.split(">")[0]
            per_day[key] = v / days[ks] if days[ks] > 0 else None
        le_deaths = [dict(cause=e["cause"], killer_sp=None, shelter_edge=e["shelter_edge"]) for e in w.events["deaths"]
                     if e["sp"] == B.LEOPARD]
        le_cause = {}
        for e in le_deaths:
            le_cause[e["cause"]] = le_cause.get(e["cause"], 0) + 1
        gh = st["gore_hp"].sum(0)
        bdays = days["buffalo"]
        # T-D
        kills_sp, kills_band = {}, {}
        kgu, mf = float(w.cfg["body_common"]["carcass"]["kg_per_unit"]), float(w.cfg["body_common"]["carcass"]["meat_frac"])
        lk = {(e["k"], e["prey_uid"]) for e in w.events["bites"] if e.get("biter_sp") == B.LEOPARD and e["outcome"] == "kill"}
        for e in w.events["deaths"]:
            if (e["k"], e["uid"]) in lk:
                n = names[e["sp"]]
                kills_sp[n] = kills_sp.get(n, 0) + 1
                bd = band(e["meat"] * kgu / mf)
                kills_band[bd] = kills_band.get(bd, 0) + 1

        def jacobs(kills, enc):
            kt_, et_ = sum(kills.values()), sum(enc.values())
            out = {}
            for c in sorted(set(kills) | set(enc)):
                r = kills.get(c, 0) / kt_ if kt_ else None
                p = enc.get(c, 0) / et_ if et_ else None
                if r is None or p is None or (r + p - 2 * r * p) == 0:
                    out[c] = dict(kills=kills.get(c, 0), enc=enc.get(c, 0), D=None)
                else:
                    out[c] = dict(kills=kills.get(c, 0), enc=enc.get(c, 0), D=(r - p) / (r + p - 2 * r * p))
            return out

        def dist(v):
            if not v:
                return None
            a = np.asarray(v)
            return dict(n=len(v), p10=float(np.quantile(a, 0.1)), median=float(np.median(a)), p90=float(np.quantile(a, 0.9)),
                        share_lt5=float((a < 5.0).mean()))

        tc = self.tc
        thr = tc["threat"]
        return dict(
            decisions=self.decisions, worlds=w.K,
            alive_days=days,
            deaths={n: dict(zip(("none", "bite", "counter", "starve"), st["deaths"][:, s].sum(0).tolist())) for s, n in enumerate(names)},
            T_A=dict(episodes=len(self.episodes), open_at_end=len(self.ep_open), bins=bins),
            T_C=dict(threat_decisions=thr, facing_share=tc["facing"] / thr if thr else None, flee_share=tc["flee"] / thr if thr else None,
                     gore_share=tc["gore"] / thr if thr else None,
                     kin_mean_dist_threat=float(np.mean(tc["kin_d_threat"])) if tc["kin_d_threat"] else None,
                     kin_mean_dist_calm=float(np.mean(tc["kin_d_calm"])) if tc["kin_d_calm"] else None),
            T_D=dict(by_species=jacobs(kills_sp, self.td_enc_sp), by_band=jacobs(kills_band, self.td_enc_band)),
            T_H=dict(kills=kt, kills_per_killer_day=per_day, leopard_death_causes=le_cause,
                     leopard_death_shelter_edge=[e["shelter_edge"] for e in le_deaths][:200],
                     bites_in_shelter={f"{names[i]}>{names[j]}": int(v) for (i, j), v in np.ndenumerate(st["bite_in_shelter"].sum(0)) if v},
                     buffalo_gore_hp_per_buffalo_day={n: (float(gh[B.BUFFALO, s]) / bdays if bdays > 0 else None)
                                                      for s, n in enumerate(names) if s != B.BUFFALO}),
            T_K=dict(deer_decisions_pred_within10=self.tk["near"],
                     miss_share=self.tk["miss"] / self.tk["near"] if self.tk["near"] else None),
            T_M={names[sp]: dict(nearest_same=dist(v["nn"]), target_decisions=v["targets"],
                                 joint_share=v["joint"] / v["targets"] if v["targets"] else None) for sp, v in self.tm.items()},
        )


def natural(cfg, ctr, form: str, worlds: int, decisions: int) -> dict:
    names = B.species_of(cfg)
    counts = None
    if form == "buffalo_land":
        counts = np.full((worlds, len(names)), -1, dtype=np.int64)
        for k in range(worlds):
            counts[k, B.DEER] = (0, 2, 4)[k % 3]
            counts[k, B.BUFFALO] = (4, 6, 8)[k % 3]
            counts[k, B.WOLF] = (4, 6)[k % 2]
    w = R9World(cfg, [SEEDS[0] + i for i in range(worlds)], counts=counts, record=True)
    set_all(w, ctr)
    ns = NatStats(w)
    t0 = time.time()
    for _ in range(decisions):
        w.step(w.decide())
        ns.observe()
    out = ns.summary()
    out["form"] = form
    out["seconds"] = round(time.time() - t0, 1)
    return out


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #

def speed_from_flight(flight: Path | None) -> dict | None:
    """C0-F9: decisions / s of the flight bundles (run meta dec_per_s)."""
    if flight is None or not (flight / "flight.json").exists():
        return None
    f = json.loads((flight / "flight.json").read_text(encoding="utf-8"))
    out = {}
    for st in f.get("stages", []):
        for name, r in (st.get("runs") or {}).items():
            if r.get("dec_per_s") is not None:
                out[name] = dict(dec_per_s=r["dec_per_s"], timesteps=r.get("timesteps"), wall_s=r.get("wall_s"), stop=r.get("stop"))
    return out


def _fmt(v, nd=3):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def to_md(rep: dict) -> str:
    L_ = [FIRST_LINE, "", f"- 만든 때 {rep['made']} · 설정 `{rep['config']}` · 두뇌 {json.dumps(rep['brains'], ensure_ascii=False)}",
          "- 보고만 한다(판정 아님). 칸마다 사건 30 개 넘을 때만 비율을 적는다. 정의는 JSON 'defs'.", ""]
    for brains, sec in rep["sets"].items():
        L_.append(f"## 두뇌 판: {brains}")
        L_.append("- " + " · ".join(f"{n} {v}" for n, v in sec.get("labels", {}).items()))
        if "S1" in sec:
            L_ += ["", "### S1 늑대 무리 대 물소 (어른 3 + 송아지 1)", "",
                   "| 늑대 | 어른 죽임 몫 | 송아지 죽임 몫 | 늑대 죽음 몫 | 늑대 HP 잃음/마리 | 받기 | 반격 | 앞자리 몫 |", "|---|---|---|---|---|---|---|---|"]
            for r in sec["S1"]:
                L_.append(f"| {r['n_wolf']} | {_fmt(r['adult_kill_frac'])} | {_fmt(r['calf_kill_frac'])} | {_fmt(r['wolf_death_frac'])} | "
                          f"{_fmt(r['wolf_hp_lost_per_wolf'])} | {r['gores']} | {r['counters']} | {_fmt(r['front_share'])} |")
            L_.append("- 현실 기준(MacNulty 2014): 혼자 0.01, 마리당 오즈 × 1.4. 기대: 1~2 마리는 낮고 늑대가 다침, 3~4 마리부터 오름. "
                      "이상 신호: 어른 1 마리 성공 ≥ 0.2.")
        if "S2" in sec:
            r = sec["S2"]
            L_ += ["", "### S2 늑대 1 ↔ 표범 1", "",
                   f"- 세계 {r['worlds']} · 늑대 죽음 {r['wolf_died']} · 표범 죽음 {r['leopard_died']} · 둘 다 {r['both_died']} · "
                   f"아무도 {r['none_died']} · 늑대→표범 물림 {r['bites_wolf_on_leopard']} · 표범→늑대 물림 {r['bites_leopard_on_wolf']}",
                   "- 기대: 대개 다치고 떨어짐. 이상 신호: '둘 다 죽음' 잦음."]
        for form in ("base", "buffalo_land"):
            key = f"N_{form}"
            if key not in sec:
                continue
            n = sec[key]
            L_ += ["", f"### 자연 세계 N ({form}) — {n['worlds']} 세계 × {n['decisions']} 결정 ({n['seconds']} 초)", ""]
            L_.append("- 죽음(종: 물림·반격·굶음): " + " · ".join(f"{s} {d['bite']}·{d['counter']}·{d['starve']}" for s, d in n["deaths"].items()))
            ta = n["T_A"]
            L_.append(f"- T-A 덤빔 {ta['episodes']} (끝나지 않음 {ta['open_at_end']}):")
            for k_, b in sorted(ta["bins"].items()):
                L_.append(f"  - {k_}: 덤빔 {b['episodes']} · 성공 {b['success']} (몫 {_fmt(b['success_share'])}) · 늑대 HP 잃음 "
                          f"{b['hp_lost']:.2f} · 늑대 죽음 {b['wolf_dead']} · 시작 E {b['wolf_e_mean']:.2f} · 10 단위 안 사슴 {b['deer10_mean']:.1f}")
            tc = n["T_C"]
            L_.append(f"- T-C 위협 결정 {tc['threat_decisions']}: 마주 봄 {_fmt(tc['facing_share'])} · 도망 {_fmt(tc['flee_share'])} · "
                      f"받기 {_fmt(tc['gore_share'])} · 동족 거리 위협 {_fmt(tc['kin_mean_dist_threat'], 2)} / 평소 {_fmt(tc['kin_mean_dist_calm'], 2)}")
            td = n["T_D"]
            L_.append("- T-D 표범 먹잇감 (죽임/만남/D): " + " · ".join(f"{c} {v['kills']}/{v['enc']}/{_fmt(v['D'], 2)}"
                                                         for c, v in td["by_species"].items()))
            L_.append("  - 무게 띠: " + " · ".join(f"{c} {v['kills']}/{v['enc']}/{_fmt(v['D'], 2)}" for c, v in td["by_band"].items()))
            th = n["T_H"]
            L_.append("- T-H 죽임 표: " + (" · ".join(f"{k_} {v}" for k_, v in sorted(th["kills"].items())) or "없음"))
            L_.append(f"  - 표범 죽음 원인 {th['leopard_death_causes']} · 은신처 안 물림 {th['bites_in_shelter']} · "
                      f"물소 받기 HP/물소-일 {json.dumps({k_: (round(v, 4) if v is not None else None) for k_, v in th['buffalo_gore_hp_per_buffalo_day'].items()})}")
            tk = n["T_K"]
            L_.append(f"- T-K 감각 붐빔: 포식자 10 단위 안 사슴 결정 {tk['deer_decisions_pred_within10']} 중 칸에 없던 몫 {_fmt(tk['miss_share'], 4)} "
                      "(≤ 1% 기대, > 5% 면 2 단계 칸 바꿈 앞당김)")
            for sp_, v in n["T_M"].items():
                nn = v["nearest_same"]
                L_.append(f"- T-M {sp_}: 가장 가까운 동족 {('중앙 ' + _fmt(nn['median'], 1) + ' · 5 단위 안 몫 ' + _fmt(nn['share_lt5'])) if nn else '—'} · "
                          f"함께 덤빔 몫 {_fmt(v['joint_share'])} (현실은 혼자 — 보고만)")
        L_.append("")
    if rep.get("C0_F9"):
        L_ += ["## C0-F9 속도 (시험 비행 묶음)", ""]
        for n, v in rep["C0_F9"].items():
            L_.append(f"- {n}: {_fmt(v['dec_per_s'], 0)} 결정/초 · {v['timesteps']} 결정 · 멈춤 {v['stop']}")
    L_.append("")
    L_.append("등록 문장: 사슴이 많은 세계에서 늑대가 어른 물소를 안 건드리는 것은 이상 신호가 아니다. '무리로 잡을 수 있나'는 장면 S1, "
              "'실제로 무리로 덤비나'는 buffalo_land 꼴 자연 세계로 본다.")
    return "\n".join(L_) + "\n"


DEFS = {
    "S1": scene_s1.__doc__, "N": NatStats.__doc__, "SceneWorld": SceneWorld.__doc__,
    "seeds": f"{SEEDS[0]}~{SEEDS[1] - 1} (7-3 fauna_report)", "actions": "greedy (판정과 같음) unless --stochastic",
}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flight", default=None, help="fauna_flight.py 결과 폴더 (flight.json)")
    ap.add_argument("--brains", nargs="*", default=[], help="종=npz … (flight 보다 우선)")
    ap.add_argument("--start-dir", default="ckpt/r9_fauna/start", help="옛 세 종 v0 (deer/wolf/boar_v0.npz)")
    ap.add_argument("--config", default="configs/v3_r9_fauna.yaml")
    ap.add_argument("--only", default="S1,S2,N")
    ap.add_argument("--worlds", type=int, default=None, help="장면 40·자연 20 대신 (스모크)")
    ap.add_argument("--decisions", type=int, default=None, help="S1 300·S2 150·N 1,350 대신 (스모크)")
    ap.add_argument("--wolves", default="1,2,3,4,6")
    ap.add_argument("--rules-only", action="store_true")
    ap.add_argument("--stochastic", action="store_true")
    ap.add_argument("--name", default=None)
    ap.add_argument("--out-dir", default=str(HERE.parent / "fauna_reports"))
    a = ap.parse_args(argv)
    cfg = B.load_r9_config(_abs(a.config))
    if len(B.species_of(cfg)) < 6:
        raise SystemExit("fauna_report needs the six-species animal config (configs/v3_r9_fauna.yaml)")
    flight = _abs(a.flight) if a.flight else None
    paths = {}
    sd = _abs(a.start_dir)
    for n in ("deer", "wolf", "boar"):
        if (sd / f"{n}_v0.npz").exists():
            paths[n] = str(sd / f"{n}_v0.npz")
    if flight is not None:
        paths.update(flight_brains(flight))
    for kv in a.brains:
        n, p = kv.split("=", 1)
        paths[n] = str(_abs(p))
    only = {x.strip() for x in a.only.split(",") if x.strip()}
    sets = {"rules": True} if (a.rules_only or not any(paths.values())) else {"learned": False, "rules": True}
    rep = dict(made=time.strftime("%Y-%m-%d %H:%M:%S"), config=a.config, brains=paths, first_line=FIRST_LINE, defs=DEFS, sets={},
               C0_F9=speed_from_flight(flight))
    t0 = time.time()
    for label, rules_only in sets.items():
        ctr, lab = make_controllers(cfg, paths, rules_only, a.stochastic)
        sec = dict(labels=lab)
        if "S1" in only:
            sec["S1"] = [scene_s1(cfg, ctr, int(n), a.worlds or 40, a.decisions or 300) for n in a.wolves.split(",")]
            print(f"[{label}] S1 {time.time() - t0:.0f}s", flush=True)
        if "S2" in only:
            sec["S2"] = scene_s2(cfg, ctr, a.worlds or 40, a.decisions or 150)
            print(f"[{label}] S2 {time.time() - t0:.0f}s", flush=True)
        if "N" in only:
            for form in ("base", "buffalo_land"):
                sec[f"N_{form}"] = natural(cfg, ctr, form, a.worlds or 20, a.decisions or 1350)
                print(f"[{label}] N {form} {time.time() - t0:.0f}s", flush=True)
        rep["sets"][label] = sec
    name = a.name or (f"flight_{flight.name}" if flight else time.strftime("report_%Y%m%d_%H%M"))
    od = _abs(a.out_dir)
    od.mkdir(parents=True, exist_ok=True)
    (od / f"{name}.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    (od / f"{name}.md").write_text(to_md(rep), encoding="utf-8")
    print(f"보고 {od / (name + '.md')} ({time.time() - t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

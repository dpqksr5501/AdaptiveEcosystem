"""v3 R3 결정적 확인표 — '멈추면 따라잡힘'과 '덤불에 닿으면 삶'이 추격 고정 (f)·늑대 은신처 진입 금지 (i)·지형 (h)이 켜진 세계에서
결정적으로 성립하는지 먼저 본다 (사전 등록 `PREREG.md` 16-3, 첫 실행 전 — 판정이 아니다). `results/v3/r0/chase_r0.py` 의 꼴이다.

    # herbivore_rl/ 에서 (몇 분)
    python results/v3/r3/chase_r3.py            # → results/v3/r3/chase_r3.json, chase_r3.md (두 번 돌려 같은지도 본다)

경기장: 판정 설정 `configs/v3_r3_on.yaml` 에서 배치만 난수 없이 고친 사본이다 — 맵 110 × 110(벽이 멀다), 늑대 하나(원거리형·플레이어
없음), 은신처 없음(사슴 (다)만 은신처 원 하나), 낮 고정, 지형은 맵 전체를 한 가지 땅으로 칠한다. 세계 규칙(추격 고정·진입 금지·지형 배수·
은신처 안전·청각·시야·먹는 시간)은 판정 세계 그대로다. 늑대는 (x 6, 가운데)에서 +x 쪽을 보고, 사슴 0 은 그 앞 D0 에서 늑대 쪽을 본다.
나머지 사슴은 먼 구석에 둔다(늑대 시야 밖). 세계 시드(33080~33083, 도구 점검 범위)는 결정 지연(jitter)·먹이 같은 것만 바꾼다.
- 늑대: 추격형(herb_speed × 0.8) · 잠행형(잠행 0.3 → 체감 거리 ≤ 6 이면 돌진 1.5 × 12스텝).
- 땅: 보통 · 눈 · 거친 땅(사슴 ×1·0.6·0.8, 늑대 ×1·0.85·0.9).
- 시작 거리 D0: 3·5·7·9.
- 사슴: (가) 계속 FLEE, (나) k 스텝 동안 FLEE 를 요청한 뒤 GRAZE(k = 0·4·8·16 — 0 은 처음부터 먹기, FLEE 잠금이 8 이라 4 는 대개 8 과
  같다), (다) 늑대 반대쪽 은신처(반지름 6, 가장자리까지 c = 3·6·10)로 HIDE.
적는 것: 잡힘과 그 스텝, 마지막 간격(잡혔으면 잡히기 직전 스텝, 아니면 끝), 가장 좁은 간격, 실제로 멈춘(GRAZE 로 바뀐) 스텝, 은신처에
닿은 스텝, 늑대가 원 둘레에 붙어 있던 스텝, 늑대가 원 안에 있던 스텝(늘 0), 사슴과 맵 벽 사이 가장 짧은 거리. 길이 MAX_STEPS = 90(12초).
결과의 결정성: 같은 경기장을 두 번 돌려 JSON 이 바이트까지 같은지 본다(`verify`). 판정 설정의 digest 를 지금 작업 트리에서 다시 재서 함께 적는다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: F401,E402
import numpy as np  # noqa: E402

CONFIG = "configs/v3_r3_on.yaml"
TRAIN_CONFIG = "configs/v3_r3.yaml"
SEEDS = (33080, 33081, 33082, 33083)
SIZE = 110.0
WOLF_X = 6.0
D0S = (3.0, 5.0, 7.0, 9.0)
WOLVES = ("chaser", "stalker")
TERRAINS = ("normal", "snow", "rough")
DEER = (("flee", None), ("stop", 0), ("stop", 4), ("stop", 8), ("stop", 16), ("hide", 3.0), ("hide", 6.0), ("hide", 10.0))
COVER_R = 6.0
CHASER_MULT = 0.8
MAX_STEPS = 90
RIM_TOL = 1e-3                     # 늑대가 원 둘레에 붙음: 0 ≤ (중심 거리 − r) < RIM_TOL (밀어낸 자리는 r + 1e-6)


def arena_cfg(wolf: str):
    """경기장 설정: 판정 설정 + 배치 덮기(맵 110, 늑대 하나, 원거리형·은신처·플레이어 없음, 낮 고정)."""
    from env_v2.config import load_v2_config

    cfg = load_v2_config(ROOT / CONFIG)
    rand = dict(cfg.rand, world_size=[SIZE, SIZE], predator_count=[1, 1], ranged_frac=[0.0, 0.0], cover_frac=[0.0, 0.0],
                pred_speed_mult=[CHASER_MULT, CHASER_MULT])
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    p = 1.0 if wolf == "stalker" else 0.0
    f["threats"] = dict(f["threats"], stalk_frac=[p, p], player_frac=0.0)
    f["daynight"] = dict(f["daynight"], fixed_day_frac=1.0)
    return cfg.replace(rand=rand, v2=dict(cfg.v2, features=f))


def setup(cfg, seed: int, terrain: str, d0: float, cover_c: float | None):
    """세계 하나: 사슴 0 과 늑대를 놓고 땅을 칠하고(은신처 원은 (다)만) 관측을 다시 만든다."""
    from env_v2 import repertoire as rep
    from env_v2.world import TERRAIN_NAMES, World

    w = World(cfg, seeds=[seed])
    if w.M != 1 or w.pred_is_player.any() or w.pred_ranged.any():
        raise ValueError(f"경기장에는 늑대 하나만 있어야 한다: M {w.M}")
    w.day_fixed = True
    w._daynight_update()
    y = SIZE / 2
    w.pos[:] = [SIZE - 1.0, SIZE - 1.0]
    w.pos[0] = [WOLF_X + d0, y]
    w.head[:] = [1.0, 0.0]
    w.head[0] = [-1.0, 0.0]
    w.pred_pos = np.array([[WOLF_X, y]])
    w.pred_head = np.array([[1.0, 0.0]])
    w.pred_vel = np.zeros((1, 2))
    if cover_c is not None:
        w.cov_c = np.array([[WOLF_X + d0 + cover_c + COVER_R, y]])
        w.cov_r = np.array([COVER_R])
    w.terrain_cell[:] = TERRAIN_NAMES.index(terrain)
    w.energy[:] = cfg.init_energy
    rs, rp = w._rs, w._rp
    rs.behavior[:] = rep.GRAZE
    rs.lock_left[:] = 0
    rs.arrived[:] = False
    w._rep_see[:] = rp["graze_head_down"]
    w._rep_see_last[:] = w._rep_see
    w._rep_still[:] = False
    w._rep_crouch[:] = False
    w._rep_cover = rep.cover_mult(rp, rs.behavior, w._rep_crouch)
    w._reset_stats()
    w._g = w._geometry()
    rep.perceive(rs, rp, w._g)
    w._obs = w._obs_from(w._g)
    return w


def chase(wolf: str, terrain: str, d0: float, deer: tuple, seed: int, cfg=None) -> dict:
    """한 시행 (모듈 docstring '적는 것')."""
    from env_v2 import repertoire as rep

    cfg = cfg or arena_cfg(wolf)
    kind, arg = deer
    w = setup(cfg, seed, terrain, d0, arg if kind == "hide" else None)
    out = dict(caught=False, caught_t=None, gap_end=None, gap_min=None, stop_t=None, reach_t=None, rim_steps=0, inside_steps=0,
               wall_min=None, jitter=int(w._rs.jitter[0]))
    gaps, walls = [], []
    fled = False
    for t in range(MAX_STEPS):
        if kind == "flee":
            r0 = rep.FLEE
        elif kind == "stop":
            r0 = rep.FLEE if t < arg else rep.GRAZE
        else:
            r0 = rep.HIDE
        req = np.full((w.N, 1), float(rep.GRAZE))
        req[0, 0] = r0
        gap = float(np.linalg.norm(w.pred_pos[0] - w.pos[0]))
        _, _, done, _ = w.step(req)
        if done[0]:
            out.update(caught=bool(w._pred_deaths > 0), caught_t=t, gap_end=round(gap, 3))
            break
        b = int(w.behavior[0])
        fled |= b == rep.FLEE
        if out["stop_t"] is None and fled and b == rep.GRAZE:
            out["stop_t"] = t
        if out["reach_t"] is None and len(w.cov_r) and bool(w._in_cover(w.pos[:1])[0]):
            out["reach_t"] = t
        g = float(np.linalg.norm(w.pred_pos[0] - w.pos[0]))
        gaps.append(g)
        walls.append(float(min(w.pos[0].min(), SIZE - w.pos[0].max())))
        if len(w.cov_r):
            e = float(np.linalg.norm(w.pred_pos[0] - w.cov_c[0]) - w.cov_r[0])
            out["rim_steps"] += int(0.0 <= e < RIM_TOL)
            out["inside_steps"] += int(e < 0.0)
    if not out["caught"]:
        out["gap_end"] = round(gaps[-1], 3) if gaps else None
    out["gap_min"] = round(min(gaps), 3) if gaps else out["gap_end"]
    out["wall_min"] = round(min(walls), 3) if walls else None
    return out


def deer_key(deer: tuple) -> str:
    kind, arg = deer
    return "flee" if kind == "flee" else (f"stop{arg}" if kind == "stop" else f"hide{arg:g}")


def table() -> dict:
    res = {}
    for wolf in WOLVES:
        cfg = arena_cfg(wolf)
        for terrain in TERRAINS:
            for deer in DEER:
                for d0 in D0S:
                    runs = [chase(wolf, terrain, d0, deer, s, cfg) for s in SEEDS]
                    res[f"{wolf}|{terrain}|{deer_key(deer)}|{d0:g}"] = dict(caught=sum(r["caught"] for r in runs), n=len(runs),
                                                                            runs=runs)
    return res


def digests() -> dict:
    """판정·학습 설정의 digest(지금 작업 트리, 사전 등록 1절·13-2 와 견준다)."""
    from env_v2.config import load_v2_config

    import invasion_r3 as inv

    out = {}
    for p in (CONFIG, TRAIN_CONFIG):
        cfg = load_v2_config(ROOT / p)
        out[p] = dict(config=inv.config_digest(cfg), world=inv.world_digest(cfg))
    return out


def summary_md(res: dict, meta: dict) -> str:
    def cell(key):
        v = res[key]
        return f"{v['caught']}/{v['n']}"

    def mean(key, f):
        xs = [r[f] for r in res[key]["runs"] if r[f] is not None]
        return f"{np.mean(xs):.1f}" if xs else "—"
    dg = meta["digests"]
    L = ["# v3 R3 결정적 확인표 — 멈추면 따라잡히나, 덤불에 닿으면 사나 (사전 등록 16-3, 판정 아님)", "",
         f"경기장: {CONFIG} 의 세계 규칙 그대로(추격 고정·늑대 진입 금지·지형·은신처 안전·청각·먹는 시간), 배치만 난수 없이 고쳤다 — 맵 "
         f"{SIZE:g}, 늑대 하나(x {WOLF_X:g}), 사슴 0 은 그 앞 D0, 낮, 땅은 한 가지로 칠함. 세계 시드 {list(SEEDS)}(도구 점검 범위). "
         f"길이 {MAX_STEPS}스텝(12초). 추격형 속력 = 초식 ×{CHASER_MULT}.",
         f"- 설정 digest(지금 작업 트리): 판정 `{CONFIG}` {dg[CONFIG]['config']} · world_digest {dg[CONFIG]['world']}, 학습 "
         f"`{TRAIN_CONFIG}` world_digest {dg[TRAIN_CONFIG]['world']}.",
         f"- 결정성: 같은 표를 두 번 돌려 JSON 이 바이트까지 {'같았다' if meta.get('repeat_identical') else '달랐다 — 확인 필요'}"
         f" (sha1 {meta.get('sha1', '—')}).", "",
         "값 = 잡힌 수 / 시행 수(시드 4개). 사슴: 계속 FLEE, stop k = k 스텝 FLEE 를 요청한 뒤 GRAZE(stop0 = 처음부터 먹기), hide c = 가장자리까지 "
         "c 인 은신처(늑대 반대쪽)로 HIDE.", ""]
    for wolf, wn in (("chaser", "추격형"), ("stalker", "잠행형")):
        L += [f"## {wn}", "", "| 땅 | 사슴 | " + " | ".join(f"D0 {d:g}" for d in D0S) + " |", "|---|---|" + "---|" * len(D0S)]
        for terrain, tn in (("normal", "보통"), ("snow", "눈"), ("rough", "거친 땅")):
            for deer in DEER:
                k = deer_key(deer)
                L.append(f"| {tn} | {k} | " + " | ".join(cell(f"{wolf}|{terrain}|{k}|{d:g}") for d in D0S) + " |")
        L.append("")
    L += ["## 세부 (시드 평균, D0 마다)", "",
          "| 늑대 | 땅 | 사슴 | D0 | 잡힘 | 잡힌 스텝 | 마지막 간격 | 가장 좁은 간격 | 멈춘 스텝 | 은신처 닿은 스텝 | 늑대 원 둘레 스텝 | 늑대 원 안 | 벽까지 최소 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, v in res.items():
        wolf, terrain, k, d = key.split("|")
        inside = sum(r["inside_steps"] for r in v["runs"])
        L.append(f"| {wolf} | {terrain} | {k} | {d} | {v['caught']}/{v['n']} | {mean(key, 'caught_t')} | {mean(key, 'gap_end')} | "
                 f"{mean(key, 'gap_min')} | {mean(key, 'stop_t')} | {mean(key, 'reach_t')} | {mean(key, 'rim_steps')} | {inside} | "
                 f"{mean(key, 'wall_min')} |")
    L += ["", "## 읽기", ""]
    for wolf, wn in (("chaser", "추격형"), ("stalker", "잠행형")):
        for terrain, tn in (("normal", "보통"), ("snow", "눈"), ("rough", "거친 땅")):
            def tot(k):
                c = sum(res[f"{wolf}|{terrain}|{k}|{d:g}"]["caught"] for d in D0S)
                n = sum(res[f"{wolf}|{terrain}|{k}|{d:g}"]["n"] for d in D0S)
                return c, n
            fl, st = tot("flee"), [tot(f"stop{k}") for k in (4, 8, 16)]
            hd = [tot(f"hide{c:g}") for c in (3.0, 6.0, 10.0)]
            after = sum(1 for d in D0S for c in (3.0, 6.0, 10.0) for r in res[f"{wolf}|{terrain}|hide{c:g}|{d:g}"]["runs"]
                        if r["caught"] and r["reach_t"] is not None and r["caught_t"] is not None and r["caught_t"] > r["reach_t"])
            L.append(f"- {wn}·{tn}: 계속 도망 {fl[0]}/{fl[1]} 잡힘, 멈춤(k 4·8·16) {sum(x[0] for x in st)}/{sum(x[1] for x in st)}, "
                     f"덤불로(c 3·6·10) {sum(x[0] for x in hd)}/{sum(x[1] for x in hd)} — 덤불에 닿은 뒤 잡힘 {after}.")
    inside = sum(r["inside_steps"] for v in res.values() for r in v["runs"])
    L += [f"- 늑대가 은신처 원 안에 있던 스텝: 모두 합쳐 {inside}(늘 0 이어야 한다)."]
    return "\n".join(L) + "\n"


def verify() -> tuple[dict, bool, str]:
    """표를 두 번 만들어 JSON 바이트가 같은지 본다. 반환 (표, 같음, sha1 앞 12자리)."""
    import hashlib

    a, b = table(), table()
    ja, jb = json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True)
    return a, ja == jb, hashlib.sha1(ja.encode()).hexdigest()[:12]


def main() -> int:
    sys.path.insert(0, str(HERE.parent))
    res, same, sha = verify()
    meta = dict(config=CONFIG, seeds=list(SEEDS), size=SIZE, wolf_x=WOLF_X, d0=list(D0S), cover_r=COVER_R, chaser_mult=CHASER_MULT,
                max_steps=MAX_STEPS, deer=[deer_key(d) for d in DEER], repeat_identical=same, sha1=sha, digests=digests())
    (HERE.parent / "chase_r3.json").write_text(json.dumps(dict(meta=meta, table=res), indent=1), encoding="utf-8")
    md = summary_md(res, meta)
    (HERE.parent / "chase_r3.md").write_text(md, encoding="utf-8")
    print(md)
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())

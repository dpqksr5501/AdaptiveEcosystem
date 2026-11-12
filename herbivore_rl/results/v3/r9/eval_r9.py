"""R9 평가 — 보정 관문 C0 · 이름표 새는 길 · J1 섞인 무리 · J2/J3 판정 · 장면 · 이상 · 바퀴 점검 · 요약
(설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 4-6·8·9·10절; 계산은 r9_eval_core.py).

`herbivore_rl/` 에서 (PYTHONUTF8=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1):
    python results/v3/r9/eval_r9.py calibrate --phase pick                 # C0-6 → 5 → 7 → 1 → 2 → 3 → 4 → 11 → 7b·7c (고르기 시드)
    python results/v3/r9/eval_r9.py calibrate --phase confirm              # 확인 시드에서 모든 관문 한 번 더 (고침은 관문마다 한 번)
    python results/v3/r9/eval_r9.py calibrate --gates C0-10 --c010-commands  # C0-10 짧은 학습 명령만 적는다 (여기서 돌리지 않음)
    python results/v3/r9/eval_r9.py calibrate --gates C0-10 --gamma 0.997 --brain -:deer=<npz> -:boar=<npz> -:wolf=<npz>
    #   C0-10 은 밤에만: run_night.py (밤 창 안에서 학습 6 묶음 → 이 잼 → --c010-choose → C0_STATE → 리그)
관문 정의 (2026-11-12 측정 전 등록, STATUS 2-1 문장 그대로 — S′ 세계·S4 규칙 두뇌): C0-6·C0-4 보고만, C0-5 먹은 양 기준(d 점수·동점 0.01),
C0-7 띠 ∧ 멸종 없음 ∧ |L0 끝 수 변화| < 20% · max(|log 비|) 점수·동점 0.05 · 0.012 등록 대조·0.005 보고, C0-1 섞인 무리(떨어지면 묻기),
C0-2 strict 사냥 성공률(한 번만 고침), C0-10 늑대 셋 조건 + 음성 대조 셋. 사냥 시도 = strict (r9_eval_core.strict_stats), 막힘 = L0 짝 비교.
    python results/v3/r9/eval_r9.py leak [--brain -:deer=...]               # 4-6 이름표 새는 길 (기본 스모크 시드 44180~44199)
    python results/v3/r9/eval_r9.py mixed --brain A:deer=… ×6               # 8-1 J1 (판정 시드 44800~44899, 잠금 파일)
    python results/v3/r9/eval_r9.py judge --brain A:deer=… ×6 --long --variants L0 L1 LS regen_0.5 regen_2.0 ratio   # 8-2 J2·J3
    python results/v3/r9/eval_r9.py scenes --form judge --seeds 44180 44189     # 8-3 (보고만, 스모크 시드)
    python results/v3/r9/eval_r9.py anomaly --form train --seeds 44180 44199    # 8-4 (스모크 시드)
    python results/v3/r9/eval_r9.py check --round 10 --brain A:deer=… ×6 --prev results/v3/r9/check/round08.json   # 8-5·9-4
    #   league_r9.py --check-cmd "results/v3/r9/eval_r9.py check --round {round} --branches {branch} --league-state {state}"
    #   (갈래마다 불림 → check/round10_A.json·_B.json, 둘 다 모이면 round10.json 에 멈춤 규칙. 직전 점검은 점검 폴더에서 찾는다)
    python results/v3/r9/eval_r9.py summary                                 # 9-2 판정 문장

시드 (10절): 판정 44800~44999 는 judge·mixed 만, 잠금 파일(eval/JUDGE_LOCK.json — 두뇌 sha256 6 개·설정 해시)이 같을 때만 쓴다.
판정 시드에서는 --set 덮어쓰기·세계 수·스텝 줄이기를 받지 않는다. 다른 명령은 판정 시드를 받으면 오류(시험 25). 판정 시드가 아닌 시드로
judge·mixed 를 돌리면 '판정 아님(시운전)'으로 적고 잠금을 쓰지 않는다. 95% 구간 = 세계 되뽑기 2,000 번·시드 44799.
두뇌 --brain 갈래:종=경로.npz (r9_brains.load_brain — 몸 해시가 다르면 거부). 규칙 두뇌 이름(RULE_DEER 등)도 종 칸에 쓸 수 있다.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
for _p in (ROOT, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

import r9_eval_core as C  # noqa: E402
from env_v2 import r9_body as B  # noqa: E402

DEER, WOLF, BOAR = B.DEER, B.WOLF, B.BOAR
SPECIES = B.SPECIES
OUT_CALIB = HERE.parent / "calib"
OUT_EVAL = HERE.parent / "eval"
OUT_CHECK = HERE.parent / "check"
LOCK_PATH = OUT_EVAL / C.LOCK_NAME

# --------------------------------------------------------------------------- #
# 보정 관문 (9-1) — 고칠 값 하나·후보·고르는 규칙을 등록한 그대로
# --------------------------------------------------------------------------- #

C0_ORDER = ("C0-6", "C0-5", "C0-7", "C0-1", "C0-2", "C0-3", "C0-4", "C0-11", "C0-7b", "C0-7c")
# 2026-11-12 측정 전 등록 (S′, 사용자 11-12 "1. 실전 세계랑 맞추고 2. 그렇게 해 3. 다 해") — 문장은 results/v3/r9/STATUS.md 2-1 그대로.
C0_SPEC = {
    "C0-6": dict(kind="report", form="train",
                 rule="보고만 (11-12): 먹는 속도 0.012 고정 — EAT 결정 몫·서서 먹은 몫·헛 EAT 몫·먹이 활동 몫·쉬는 시간 몫·기운 중앙·굶음"),
    "C0-5": dict(kind="decide", path=("food", "root", "regen_q"), cands=[1.0, 0.5, 2.0, 0.25, 4.0], tie=0.01, form="train",
                 rule="먹은 양 기준: 땅속 몫 ∈ [0.5, 0.8] ∧ Pianka(먹은 양) ∈ [0.2, 0.5] 후보 가운데 d = max(|땅속 − 0.65|, |Pianka − 0.35|) 가 "
                      "가장 작은 것, d 차 0.01 안은 표 차례 (1 → 0.5 → 2 → 0.25 → 4)"),
    "C0-7": dict(kind="decide", path=("food", "grass", "regen_base"), cands=[0.002, 0.0015, 0.0025, 0.001, 0.003], tie=0.05, form="judge",
                 neg_control=0.012, report_value=0.005,
                 rule="끝 수 비 [0.7, 2.5](두 종)·멸종 없음·|L0 끝 수 변화| < 20%(두 종) 후보 가운데 max(|log 사슴비|, |log 멧돼지비|) 가 가장 "
                      "작은 것, 0.05 안은 표 차례. 등록 조건: 0.012 는 띠에서 떨어져야, 0.005 는 보고"),
    "C0-1": dict(kind="check", form="train",
                 rule="섞인 무리: RULE_DEER ÷ ALWAYS_EAT 잡힘 비 ≤ 0.7 ∧ 세계 짝 차 95% 위 끝 < 0 — 떨어지면 멈추고 묻는다 (고칠 값 없음)"),
    "C0-2": dict(kind="direction", path=("species", "wolf", "run_mult"), base=[0.90, 1.05], high=[0.85, 1.00], low=[0.95, 1.10],
                 form="train", rule="strict 사냥 성공률 ∈ [0.10, 0.50]. 위로 넘치면 U[0.85, 1.00]·아래로 떨어지면 U[0.95, 1.10] 로 한 번만, "
                                    "그래도 띠 밖이면 멈추고 묻는다"),
    "C0-3": dict(kind="direction", path=("body_common", "counter", "cone_cos"), base=0.25, high=0.5, low=0.0, form="train",
                 rule="성체 물기 반격 몫 ∈ [0.2, 0.8]·성체 잡힘 > 0, 75.5° → 높으면 60°·낮으면 90°"),
    "C0-4": dict(kind="report", form="train", rule="보고만 (11-12): 규칙 늑대 E 중앙 (처음 띠 [0.3, 0.9] 와 견준 값 함께)"),
    "C0-11": dict(kind="reward", form="train", rule="RULE − HIDE 개체당 1,000 스텝 전체 보상 차 95% 아래 끝 > 0 (사슴·멧돼지), 못 넘으면 F 한 번"),
    "C0-7b": dict(kind="report", form="judge", rule="규칙 셋 30 분 공존 세계 몫·막힘 몫 (보고만)"),
    "C0-7c": dict(kind="report", form="judge", rule="(가) RANDOM 늑대 공존 ≤ 0.3 이어야 J2 가 떨어질 수 있는 판, 아니면 J2 주 기준 = 2 시간 판"),
    # 밤에만 (run_night.py). C0_STATE 에 고른 γ 를 적고 judge·mixed·check·리그가 YAML 과 다르면 거부한다(check_c0_state).
    "C0-10": dict(kind="night", path=("train", "ppo", "gamma"), cands=[0.997, 0.99], form="train",
                  rule="짧은 학습: 사슴 20M·멧돼지 10M 먹이 기준 + 늑대 10M 셋 조건(보상 짝 차 − RANDOM·− 늘 살피기 아래 끝 > 0, strict 성공률 "
                       "≥ 0.5 × 규칙, strict 사냥 죽임 κ ≥ 0.5 × 규칙), 음성 대조 RANDOM·NOHUNT·NOHUNT_RUN 이 떨어져야(등록 조건)"),
}
C05_BANDS = dict(root=(0.5, 0.8), pianka=(0.2, 0.5))
C05_CENTER = dict(root=0.65, pianka=0.35)
C07_BAND = (0.7, 2.5)
C07_L0_MAX = 0.20
C01_RATIO_MAX = 0.7
C02_BAND = (0.10, 0.50)
EVAL_FACING = {"randomize": {"rule_deer_facing": [0.9, 0.9]}}          # 7-5 평가·판정 f = 0.9 (뽑는 개수는 그대로)
REGEN_ONE = {"randomize": {"grass_regen_mult": [1.0, 1.0], "root_regen_mult": [1.0, 1.0]}}
PREY_MIX_RULE = 0.7                                                    # 7-4 0 바퀴 늑대 묶음 먹이: 규칙 70%·늘 먹기 30% (세계 번호로 [어림])

# 8-2 판정 배치 (먹이 = 사슴·멧돼지, 늑대)
BATCHES = {"L_A": ("A", "A"), "L_B": ("B", "B"), "X_AB": ("A", "B"), "X_BA": ("B", "A"), "RULE": ("rule", "rule"),
           "P_A": ("A", "rule"), "P_B": ("B", "rule"), "W_A": ("rule", "A"), "W_B": ("rule", "B")}
VARIANT_NAMES = ("L0", "L1", "LS", "regen_0.5", "regen_2.0", "ratio")
RATIO_SETS = (("ratio_20_10", (20, 10)), (None, (24, 6)), ("ratio_27_3", (27, 3)))


# --------------------------------------------------------------------------- #
# 공통
# --------------------------------------------------------------------------- #

def _p(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _patch_from(path: tuple, value) -> dict:
    d: dict = {}
    cur = d
    for key in path[:-1]:
        cur[key] = {}
        cur = cur[key]
    cur[path[-1]] = value
    return d


def _sets(cfg: dict, sets) -> dict:
    """`--set a.b.c=값`(YAML 값) 덮어쓰기."""
    import yaml

    for s in sets or []:
        key, val = s.split("=", 1)
        cfg = B.override(cfg, _patch_from(tuple(key.split(".")), yaml.safe_load(val)))
    return cfg


def load_cfgs(args) -> tuple[dict, dict]:
    ct = _sets(B.load_r9_config(_p(args.config)), args.set)
    cj = _sets(B.load_r9_config(_p(args.judge_config)), args.set)
    return ct, cj


def _seeds(a) -> list[int]:
    return C.seed_list(int(a[0]), int(a[1]))


def _fmt(x, nd=3) -> str:
    if x is None:
        return "-"
    if isinstance(x, bool):
        return "예" if x else "아니오"
    if isinstance(x, (list, tuple)):
        return "[" + ", ".join(_fmt(v, nd) for v in x) + "]"
    if isinstance(x, (float, np.floating)):
        return f"{float(x):.{nd}f}" if math.isfinite(float(x)) else str(float(x))
    return str(x)


def _write(out_dir: Path, name: str, obj: dict, md: list[str] | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    obj = dict(obj)
    obj.setdefault("metric_defs", dict(C.DEFS))         # 사냥 시도·막힘 정의 (r9_eval_core.DEFS — 기본 = 8-2 문장)
    p = out_dir / f"{name}.json"
    p.write_text(json.dumps(C.to_jsonable(obj), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if md is not None:
        (out_dir / f"{name}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return p


def spec_fn(cfg: dict, specs: dict, brains: dict, stochastic: bool = False):
    """specs {sp: spec | callable(k) → spec} → ctrl_fn(k, sp, seed) for r9_eval_core.run."""
    cache: dict = {}

    def fn(k, sp, seed):
        s = specs[sp](k) if callable(specs[sp]) else specs[sp]
        if (sp, s) not in cache:
            br = C.brain_for(s, sp, cfg, brains)
            cache[(sp, s)] = C.ctrl(br, stochastic and br.kind == "mlp", label=str(s))
        return cache[(sp, s)]
    return fn


def rule_specs() -> dict:
    return {DEER: "RULE_DEER", WOLF: "RULE_WOLF", BOAR: "RULE_BOAR"}


def counts_with(K: int, wolf=None, deer=None, boar=None) -> np.ndarray:
    c = np.full((K, 3), -1, dtype=np.int64)
    for sp, v in ((DEER, deer), (WOLF, wolf), (BOAR, boar)):
        if v is not None:
            c[:, sp] = [v(k) if callable(v) else v for k in range(K)]
    return c


def _rate_world(rec: dict, sp: int, what: str) -> tuple[np.ndarray, np.ndarray]:
    """Per-world (numerator, denominator) for check components (8-5)."""
    st = rec["st"]
    al = st["alive_steps"][:, sp].astype(np.float64)
    if what == "caught":
        return st["deaths"][:, sp, 1].astype(np.float64), al
    if what == "eaten":
        return st["eaten_e"][:, sp].sum(-1), al
    if what == "births":
        return st["birth_credits"][:, sp].astype(np.float64), al
    if what == "daily_kill":
        kills = np.zeros(int(rec["K"]))
        for e in rec["kills"]:
            kills[int(e["k"])] += 1
        return kills, al / float(B.DAY_STEPS)
    if what == "hp_loss":
        return st["wolf_hp_lost"].astype(np.float64), al / float(B.DAY_STEPS)
    raise ValueError(what)


# --------------------------------------------------------------------------- #
# calibrate (9-1)
# --------------------------------------------------------------------------- #

def gate_value_cfg(cfg: dict, gate: str, value) -> dict:
    sp = C0_SPEC[gate]
    if "path" not in sp or value is None:
        return cfg
    return B.override(cfg, _patch_from(sp["path"], value))


def _state_cfgs(ct: dict, cj: dict, state: dict) -> tuple[dict, dict]:
    for g, v in state.get("values", {}).items():
        if g in C0_SPEC and "path" in C0_SPEC[g]:
            ct, cj = gate_value_cfg(ct, g, v), gate_value_cfg(cj, g, v)
    if state.get("f_enabled"):
        f = {"reward": {"fallback_f": {"enabled": True}}}
        ct, cj = B.override(ct, f), B.override(cj, f)
    return ct, cj


def _current_value(gate: str, state: dict, cfg_t: dict):
    sp = C0_SPEC[gate]
    if gate in state.get("values", {}):
        return state["values"][gate]
    if sp["kind"] == "direction":
        return sp["base"]
    cur = cfg_t
    for key in sp["path"]:
        cur = cur[key]
    return cur


class GateCtx:
    """Seeds / steps / chunk for one calibration phase, and the configs with the values fixed so far."""

    def __init__(self, cfg_t, cfg_j, seeds_t, seeds_j, steps_t, steps_j, steps_c011, chunk, verbose=True):
        self.cfg_t, self.cfg_j = cfg_t, cfg_j
        self.seeds_t, self.seeds_j = seeds_t, seeds_j
        self.steps_t, self.steps_j, self.steps_c011 = steps_t, steps_j, steps_c011
        self.chunk = chunk
        self.verbose = verbose

    def log(self, *a):
        if self.verbose:
            print(*a, flush=True)


def c06_report(rec: dict) -> dict:
    """C0-6 보고 (S′ 2-1): 사슴·멧돼지마다 EAT 결정 몫, 서서 먹은 몫(산 스텝 중 EAT 이고 발밑에 먹을 것이 있음), 헛 EAT 몫(EAT 인데 발밑에
    없음), 먹이 활동 몫(EAT 결정 + E < 0.9 이고 food_dir 칸 하나라도 > 0 일 때의 걷기 결정 [어림]), 쉬는 시간 몫(WATCH 결정), 걷기 몫, 기운 중앙,
    굶음 / 1,000 개체-스텝. 처음 띠([0.3, 0.6]·멧돼지 [0.2, 0.6])와 견준 값도."""
    sm = C.species_metrics(rec)
    es = np.asarray(rec["eat_steps"]).sum(0)
    fd = np.asarray(rec["forage_dec"]).sum(0)
    out = {}
    for sp in (DEER, BOAR):
        nm = SPECIES[sp]
        s = sm[nm]
        al = max(float(es[sp, 0]), 1.0)
        dec = max(float(fd[sp, 0]), 1.0)
        out[nm] = dict(eat_dec_share=s["act_eat"], stand_eat_share=float(es[sp, 1]) / al, null_eat_share=float(es[sp, 2]) / al,
                       forage_share=float(fd[sp, 1]) / dec, rest_share=s["act_watch"], walk_share=s["act_walk"], run_share=s["act_run"],
                       shelter_share=s["act_shelter"], E_median=s["E_median"], starved_1k=s["starved_1k"])
    out["old_band"] = dict(deer=bool(0.3 <= out["deer"]["eat_dec_share"] <= 0.6), boar=bool(0.2 <= out["boar"]["eat_dec_share"] <= 0.6))
    return out


def m_c06(ctx: GateCtx, v=None) -> dict:
    """보고만 (11-12) — 고르지도 멈추지도 않는다. 학습 세계 꼴·늑대 없음·재생 배수 1·f 0.9, RULE_DEER·RULE_BOAR (S4)."""
    cfg = B.override(ctx.cfg_t, {**REGEN_ONE, **EVAL_FACING})
    K = len(ctx.seeds_t)
    rec = C.run(cfg, ctx.seeds_t, ctx.steps_t, spec_fn(cfg, rule_specs(), {}), counts=counts_with(K, wolf=0), scenes=False, chunk=ctx.chunk)
    rp = c06_report(rec)
    return dict(value=float(cfg["species"]["deer"]["eat_rate"]["grass"]), eat_share=rp["deer"]["eat_dec_share"],
                rest_share=rp["deer"]["rest_share"], forage_share=rp["deer"]["forage_share"], deer_E_median=rp["deer"]["E_median"],
                report=rp, ok=True)


def c05_units(eaten_e: np.ndarray, cfg: dict) -> dict:
    """C0-5 먹은 양 기준 (11-12, '2. 그렇게 해'): 먹은 양 = 먹은 에너지 ÷ 그 몸의 단위당 E (멧돼지 풀 0.05·땅속 0.15·고기 0.9, 사슴 풀 0.5).
    eaten_e (3 종, 3 먹이) = 세계 합. 통과 = 멧돼지 땅속 몫 ∈ [0.5, 0.8] ∧ Pianka(먹은 양 몫: 풀·땅속·고기) ∈ [0.2, 0.5].
    점수 d = max(|땅속 − 0.65|, |Pianka − 0.35|) (두 띠 반폭 0.15 — 같은 눈금)."""
    ee = np.asarray(eaten_e, dtype=np.float64)
    sh = {}
    for sp in (DEER, BOAR):
        epu = cfg["species"][SPECIES[sp]]["e_per_unit"]
        u = np.array([ee[sp, f] / float(epu[n]) if (n in epu and ee[sp, f] > 0) else 0.0 for f, n in enumerate(B.FOODS)])
        sh[sp] = u / u.sum() if u.sum() > 0 else np.full(3, np.nan)
    root = float(sh[BOAR][B.ROOT])
    pk = C.pianka(sh[DEER], sh[BOAR]) if np.isfinite(sh[DEER]).all() and np.isfinite(sh[BOAR]).all() else float("nan")
    ok = bool(math.isfinite(root) and C05_BANDS["root"][0] <= root <= C05_BANDS["root"][1]
              and math.isfinite(pk) and C05_BANDS["pianka"][0] <= pk <= C05_BANDS["pianka"][1])
    d = max(abs(root - C05_CENTER["root"]), abs(pk - C05_CENTER["pianka"])) if (math.isfinite(root) and math.isfinite(pk)) else float("inf")
    return dict(root_share=root, pianka=pk, ok=ok, score=d,
                units={SPECIES[sp]: {n: float(sh[sp][f]) for f, n in enumerate(B.FOODS)} for sp in (DEER, BOAR)})


def m_c05(ctx: GateCtx, v) -> dict:
    cfg = B.override(gate_value_cfg(ctx.cfg_t, "C0-5", v), {**REGEN_ONE, **EVAL_FACING})   # [해석] 재생 배수 1 (기본값을 정하는 관문)
    K = len(ctx.seeds_t)
    rec = C.run(cfg, ctx.seeds_t, ctx.steps_t, spec_fn(cfg, {DEER: "ALWAYS_EAT", WOLF: "RULE_WOLF", BOAR: "ALWAYS_EAT"}, {}),
                counts=counts_with(K, wolf=0), scenes=True, chunk=ctx.chunk)
    ee = rec["st"]["eaten_e"].sum(0)
    u = c05_units(ee, cfg)
    tot = float(ee[BOAR].sum())
    root_e = float(ee[BOAR, B.ROOT]) / tot if tot > 0 else float("nan")
    pk_e = C.pianka(ee[DEER] / max(ee[DEER].sum(), 1e-12), ee[BOAR] / max(tot, 1e-12)) if tot > 0 and ee[DEER].sum() > 0 else float("nan")
    cell = float(np.nanmean(rec["sc_cells_pianka"])) if np.isfinite(rec["sc_cells_pianka"]).any() else float("nan")
    sm = C.species_metrics(rec)
    return dict(value=v, root_share=u["root_share"], pianka=u["pianka"], units=u["units"], ok=u["ok"], score=u["score"],
                energy=dict(root_share=root_e, pianka=pk_e, boar={n: (float(ee[BOAR, f]) / tot if tot > 0 else float("nan"))
                                                                  for f, n in enumerate(B.FOODS)}),
                cell_pianka=cell, deer_starved_1k=sm["deer"]["starved_1k"], boar_starved_1k=sm["boar"]["starved_1k"])


def _c07_run(ctx: GateCtx, v, L0: bool) -> tuple[dict, dict]:
    cfg = B.override(gate_value_cfg(ctx.cfg_j, "C0-7", v), {"judge": {"wolf_packs": {"per_pack": 0}}})
    if L0:
        cfg = B.override(cfg, ctx.cfg_j["judge"]["variants"]["L0"])
    rec = C.run(cfg, ctx.seeds_j, ctx.steps_j, spec_fn(cfg, rule_specs(), {}), scenes=False, chunk=ctx.chunk,
                progress=f"C0-7 {v}{' L0' if L0 else ''}")
    return rec, C.population_metrics(rec)


def m_c07(ctx: GateCtx, v, with_l0: bool = True, train_form: bool = True) -> dict:
    """C0-7 (11-12): 판정 세계, 규칙 사슴·멧돼지(S4)만, 늑대 없음, 30 분. 상한 켬 판과 같은 시드 L0 판(상한 끔)을 짝으로.
    통과 = 끝 수 비(end_ratio) 두 종 ∈ [0.7, 2.5] ∧ 멸종 없음 ∧ |L0 끝 수 변화| < 20% (두 종, (L0 − 켬) ÷ 켬 — 고른 세계 합).
    점수 = max(|log 사슴비|, |log 멧돼지비|). 잔량·막힘 몫(scan·once)·L0 출생 증가·까닭별 막힌 기회·두 세계 번식률·새끼 굶음은 적기만."""
    rec, pm = _c07_run(ctx, v, False)
    sm = C.species_metrics(rec)
    rd, rb = pm["end_ratio"]["deer"], pm["end_ratio"]["boar"]
    ext = bool(pm["extinct_share"]["deer"] > 0 or pm["extinct_share"]["boar"] > 0)        # [해석] 세계 하나라도 멸종하면 실패
    lo, hi = C07_BAND
    band = bool(lo <= rd <= hi and lo <= rb <= hi)
    res = dict(value=v, end_ratio=dict(deer=rd, boar=rb), band_ok=band, extinct=ext, block_share_scan=pm["block_share_scan"],
               block_share_once=pm["block_share_once"], blocked_by_reason=pm["blocked_by_reason"], food_end=pm["food_end"],
               newborn_300=pm["newborn_300"], newborns=pm["newborns"], end_worlds=pm["end_worlds"],
               births_per_1k_eligible=dict(judge={s: sm[s]["births_per_1k_eligible"] for s in ("deer", "boar")}))
    l0_ok = None
    if with_l0:
        rec0, pm0 = _c07_run(ctx, v, True)
        ch = C.l0_change(pm["end_worlds"], pm0["end_worlds"])
        binc = {s: (pm0["newborns"][s] / pm["newborns"][s] - 1.0 if pm["newborns"][s] > 0 else float("nan")) for s in ("deer", "boar")}
        l0_ok = bool(all(math.isfinite(ch[s]) and abs(ch[s]) < C07_L0_MAX for s in ("deer", "boar")))
        res.update(L0_change={s: ch[s] for s in ("deer", "boar")}, L0_births_increase=binc, L0_end_ratio=pm0["end_ratio"],
                   L0_extinct=pm0["extinct_share"], L0_ok=l0_ok, L0_slot_cap_blocks=pm0["slot_cap_blocks"])
    res["ok"] = bool(band and not ext and bool(l0_ok))
    res["score"] = max(abs(math.log(rd)), abs(math.log(rb))) if (rd > 0 and rb > 0) else float("inf")
    if train_form:
        # 두 세계의 개체당 번식률: 학습 세계 꼴(늑대 없음, 같은 규칙 두뇌, 고르기 학습 시드) [해석]
        ct = B.override(gate_value_cfg(ctx.cfg_t, "C0-7", v), EVAL_FACING)
        rt = C.run(ct, ctx.seeds_t, ctx.steps_t, spec_fn(ct, rule_specs(), {}), counts=counts_with(len(ctx.seeds_t), wolf=0), scenes=False,
                   chunk=ctx.chunk)
        smt = C.species_metrics(rt)
        res["births_per_1k_eligible"]["train"] = {s: smt[s]["births_per_1k_eligible"] for s in ("deer", "boar")}
    return res


def m_c07_controls(ctx: GateCtx) -> dict:
    """C0-7 등록 조건 (11-12): 같은 고르기 시드에서 재생 0.012 판이 띠([0.7, 2.5], 두 종)에서 떨어져야 한다 — 통과하면 멈추고 묻는다.
    재생 0.005 판(켬·L0)은 기준 결과를 그대로 보고한다."""
    sp = C0_SPEC["C0-7"]
    neg = m_c07(ctx, sp["neg_control"], with_l0=False, train_form=False)
    rep = m_c07(ctx, sp["report_value"], with_l0=True, train_form=False)
    return dict(neg=neg, neg_fails_band=bool(not neg["band_ok"]), report=rep)


def m_c01(ctx: GateCtx, v=None) -> dict:
    """C0-1 (11-12, 섞인 무리): 학습 세계 꼴, 규칙 늑대·규칙 멧돼지 상대, 같은 세계 안 사슴을 RULE_DEER 반·ALWAYS_EAT 반(J1 해시·층 배정).
    통과 = 잡힘(1,000 사슴-스텝) 비 RULE ÷ ALWAYS_EAT ≤ 0.7 ∧ 세계 짝 차(RULE − ALWAYS_EAT) 95% 위 끝 < 0. 처음 정의(무리 따로·0.5)는 보고."""
    cfg = B.override(ctx.cfg_t, EVAL_FACING)
    rec = C.run(cfg, ctx.seeds_t, ctx.steps_t, spec_fn(cfg, rule_specs(), {}), scenes=False, chunk=ctx.chunk,
                split=dict(sp=DEER, first=C.rule_brain("RULE_DEER", cfg, DEER), second=C.rule_brain("ALWAYS_EAT", cfg, DEER)),
                progress="C0-1 섞인 무리")
    smx = C.split_metrics(rec)
    b = smx["d_bite"]
    ratio = b["first"] / b["second"] if b["second"] > 0 else float("nan")
    ok = bool(math.isfinite(ratio) and ratio <= C01_RATIO_MAX and math.isfinite(b["ci"][1]) and b["ci"][1] < 0)
    old = {}
    for nm in ("RULE_DEER", "ALWAYS_EAT"):
        r = C.run(cfg, ctx.seeds_t, ctx.steps_t, spec_fn(cfg, {DEER: nm, WOLF: "RULE_WOLF", BOAR: "RULE_BOAR"}, {}), scenes=False,
                  chunk=ctx.chunk)
        old[nm] = C.species_metrics(r)["deer"]["caught_1k"]
    old_ratio = old["RULE_DEER"] / old["ALWAYS_EAT"] if old["ALWAYS_EAT"] > 0 else float("nan")
    kills = sum(1 for e in rec["kills"] if int(e["prey_sp"]) == DEER)
    return dict(value=None, caught_rule=b["first"], caught_always_eat=b["second"], ratio=ratio, diff=b["diff"], diff_ci=b["ci"],
                deer_kills=kills, ok=ok, old=dict(caught_rule=old["RULE_DEER"], caught_always_eat=old["ALWAYS_EAT"], ratio=old_ratio,
                                                   ok=bool(math.isfinite(old_ratio) and old_ratio <= 0.5)))


def m_c02(ctx: GateCtx, v) -> dict:
    """C0-2 (11-12): 규칙 늑대 대 (규칙 70%·늘 먹기 30%) 먹이, 학습 세계 꼴. 통과 = strict 사냥 성공률 ∈ [0.10, 0.50].
    ALWAYS_EAT 사슴 잡힘·pair 성공률·사냥 죽임 κ 는 보고만."""
    cfg = B.override(gate_value_cfg(ctx.cfg_t, "C0-2", v), EVAL_FACING)
    is_rule = lambda k: (k % 10) < int(round(PREY_MIX_RULE * 10))     # noqa: E731  [어림] 세계 번호로 규칙 70%·늘 먹기 30%
    specs = {DEER: lambda k: "RULE_DEER" if is_rule(k) else "ALWAYS_EAT", WOLF: "RULE_WOLF",
             BOAR: lambda k: "RULE_BOAR" if is_rule(k) else "ALWAYS_EAT"}
    rec = C.run(cfg, ctx.seeds_t, ctx.steps_t, spec_fn(cfg, specs, {}), scenes=False, chunk=ctx.chunk)
    j3 = C.j3_metrics(rec)
    ae = np.array([not is_rule(k) for k in range(int(rec["K"]))])
    num, den = _rate_world(rec, DEER, "caught")
    caught = 1000.0 * C.ratio(num[ae], den[ae]) if ae.any() else float("nan")
    sr = j3["success_rate_strict"]
    lo, hi = C02_BAND
    ok = bool(math.isfinite(sr) and lo <= sr <= hi)
    direction = None if ok or not math.isfinite(sr) else ("high" if sr > hi else "low")
    return dict(value=v, success_rate=sr, success_ci=j3["success_strict_ci"], attempts=j3["strict_attempts"],
                enough_100=bool(j3["strict_attempts"] >= C.J3_MIN_STRICT), success_rate_pair=j3["success_rate_pair"],
                segments=j3["segments"], success_rate_episode=j3["success_rate_episode"], episodes=j3["episodes"],
                caught_always_eat=caught, kappa_all=j3["daily_kill"], kappa_hunt=j3["kappa_hunt"], kappa_run=j3["kappa_run"],
                kappa_traj4=j3["kappa_traj4"], kappa_incidental=j3["kappa_incidental"], ok=ok, direction=direction)


def m_c03(ctx: GateCtx, v) -> dict:
    cfg = B.override(gate_value_cfg(ctx.cfg_t, "C0-3", v), EVAL_FACING)
    rec = C.run(cfg, ctx.seeds_t, ctx.steps_t, spec_fn(cfg, rule_specs(), {}), scenes=False, chunk=ctx.chunk)
    bb = rec["boar_bites"].sum(0)                                         # (young/adult, kill/wound/counter)
    n_ad = float(bb[1].sum())
    share = float(bb[1, 2]) / n_ad if n_ad else float("nan")
    adult_caught = int(bb[1, 0])
    ok = bool(math.isfinite(share) and 0.2 <= share <= 0.8 and adult_caught > 0)
    # [해석] 성체가 한 번도 안 잡히면 반격이 센 쪽(→ 60°)으로 본다
    hi_ = (math.isfinite(share) and share > 0.8) or (adult_caught == 0 and (not math.isfinite(share) or share >= 0.2))
    lo_ = math.isfinite(share) and share < 0.2
    j3 = C.j3_metrics(rec)
    return dict(value=v, counter_share_adult=share, adult_bites=int(n_ad), adult_caught=adult_caught, juv_index=j3["juv_index"],
                ok=ok, direction=None if ok else ("high" if hi_ else ("low" if lo_ else None)))


def m_c04(ctx: GateCtx, v=None) -> dict:
    """보고만 (11-12): 규칙 늑대(학습 세계) E 중앙값 — 처음 띠 [0.3, 0.9] 와 견준 값 함께. 사체 고기 계수 0.6 그대로."""
    cfg = B.override(ctx.cfg_t, EVAL_FACING)
    rec = C.run(cfg, ctx.seeds_t, ctx.steps_t, spec_fn(cfg, rule_specs(), {}), scenes=False, chunk=ctx.chunk)
    med = C.species_metrics(rec)["wolf"]["E_median"]                    # [해석] 늑대 결정마다의 E 를 모은 중앙값
    return dict(value=None, wolf_E_median=med, old_band_ok=bool(math.isfinite(med) and 0.3 <= med <= 0.9), ok=True)


def m_c011(ctx: GateCtx, v=None) -> dict:
    cfg = B.override(ctx.cfg_t, EVAL_FACING)
    out = {}
    for sp, (a, b) in ((DEER, ("RULE_DEER", "HIDE_DEER")), (BOAR, ("RULE_BOAR", "HIDE_BOAR"))):
        rec = C.run(cfg, ctx.seeds_t, ctx.steps_c011, spec_fn(cfg, rule_specs(), {}), scenes=False, chunk=ctx.chunk, keep_rewards=True,
                    split=dict(sp=sp, first=C.rule_brain(a, cfg, sp), second=C.rule_brain(b, cfg, sp)), progress=f"C0-11 {SPECIES[sp]}")
        smx = C.split_metrics(rec)
        kp = rec["kept"]
        disc = {}
        for var in ("r_off", "r_on"):
            disc[var] = {}
            for g, nm in ((0, a), (1, b)):
                m = kp["alive"] & (kp["group"] == g)
                disc[var][nm] = C.discounted_means(kp[var].astype(np.float64), kp["done"], m)
        out[SPECIES[sp]] = dict(rule=a, hide=b, total_off=smx["r_off"], total_on=smx["r_on"], no_birth=smx["r_nb"], eaten=smx["eaten"],
                                caught=smx["d_bite"], discounted=disc)
    ok_off = all(out[s]["total_off"]["ci"][0] > 0 for s in ("deer", "boar"))
    ok_on = all(out[s]["total_on"]["ci"][0] > 0 for s in ("deer", "boar"))
    return dict(species=out, ok=bool(ok_off), ok_with_F=bool(ok_on))


def m_c07b(ctx: GateCtx, v=None) -> dict:
    rec = C.run(ctx.cfg_j, ctx.seeds_j, ctx.steps_j, spec_fn(ctx.cfg_j, rule_specs(), {}), scenes=False, chunk=ctx.chunk, progress="C0-7b")
    pm = C.population_metrics(rec)
    return dict(coexist=pm["coexist_share"], coexist_ci=pm["coexist_ci"], block_share=pm["block_share"], end_mean=pm["end_mean"], ok=True)


def m_c07c(ctx: GateCtx, v=None) -> dict:
    res = {}
    for tag, specs in (("ga_random_wolf", {DEER: "RULE_DEER", WOLF: "RANDOM", BOAR: "RULE_BOAR"}),
                       ("na_always_eat_prey", {DEER: "ALWAYS_EAT", WOLF: "RULE_WOLF", BOAR: "ALWAYS_EAT"})):
        rec = C.run(ctx.cfg_j, ctx.seeds_j, ctx.steps_j, spec_fn(ctx.cfg_j, specs, {}), scenes=False, chunk=ctx.chunk, progress=f"C0-7c {tag}")
        pm = C.population_metrics(rec)
        res[tag] = dict(coexist=pm["coexist_share"], coexist_ci=pm["coexist_ci"], block_share=pm["block_share"])
    can_fail = bool(res["ga_random_wolf"]["coexist"] <= 0.3)
    return dict(**res, j2_can_fail=can_fail, j2_primary="short" if can_fail else "long", ok=True)


MEASURE = {"C0-6": m_c06, "C0-5": m_c05, "C0-7": m_c07, "C0-1": m_c01, "C0-2": m_c02, "C0-3": m_c03, "C0-4": m_c04,
           "C0-11": m_c011, "C0-7b": m_c07b, "C0-7c": m_c07c}


def _with_state(ctx: GateCtx, base_t: dict, base_j: dict, state: dict) -> GateCtx:
    ctx.cfg_t, ctx.cfg_j = _state_cfgs(base_t, base_j, state)
    return ctx


def pick_by_rule(tried: list[dict], cands: list, tie: float = 0.0) -> dict | None:
    """정하는 관문의 고르기 (9-1, 11-12 등록): 통과한 후보 가운데 점수가 가장 작은 것, 그 점수와 차가 `tie` 안(< tie)인 후보는 동점 →
    표 차례에서 앞의 것. tie = 0 이면 같은 점수만 동점. 통과한 후보가 없으면 None."""
    okc = [r for r in tried if r["ok"]]
    if not okc:
        return None
    best = min(float(r["score"]) for r in okc)
    near = [r for r in okc if (float(r["score"]) - best < tie if tie > 0 else float(r["score"]) == best)]
    return min(near, key=lambda r: list(cands).index(r["value"]))


def pick_gate(gate: str, ctx: GateCtx, state: dict, cands=None) -> dict:
    """고르기 시드 (9-1): decide = 후보 모두 재고 규칙대로 고름 (고침 횟수에 안 넣음; C0-7 은 등록 조건 대조 0.012·보고 0.005 도 잰다),
    check (C0-1) = 통과·실패만, 떨어지면 멈추고 묻기, direction = 지금 값 → 못 넘으면 어긋난 쪽으로 한 번 고침, reward (C0-11) = 못 넘으면 F
    한 번, report = 적기만."""
    sp = C0_SPEC[gate]
    kind = sp["kind"]
    res = dict(gate=gate, kind=kind, rule=sp["rule"], tried=[])
    if kind == "decide":
        cl = list(cands or sp["cands"])
        for v in cl:
            r = MEASURE[gate](ctx, v)
            res["tried"].append(r)
            ctx.log(f"  {gate} {v}: {'띠 안' if r['ok'] else '띠 밖'} " + _brief(r))
        best = pick_by_rule(res["tried"], cl, float(sp.get("tie", 0.0)))
        if best is not None:
            res.update(status="pass", value=best["value"])
        else:
            res.update(status="ask_user", value=None, note="통과한 후보가 없다 — 표에 없는 값을 바꾸지 않고 멈추고 묻는다 (9-1)")
        if gate == "C0-7" and not cands:
            ctl = m_c07_controls(ctx)
            res["controls"] = ctl
            ctx.log(f"  C0-7 등록 조건: 0.012 띠 {'밖 (맞음)' if ctl['neg_fails_band'] else '안 → 멈추고 묻는다'} " + _brief(ctl["neg"])
                    + f" / 0.005 (보고) {'통과' if ctl['report']['ok'] else '못 넘음'} " + _brief(ctl["report"]))
            if not ctl["neg_fails_band"]:
                res.update(status="ask_user", value=None,
                           note="등록 조건 깨짐: 재생 0.012 판이 끝 수 띠를 통과 — 기준이 체 구실을 못 해 값을 고치지 않고 묻는다 (9-1)")
        return res
    if kind == "check":
        r = MEASURE[gate](ctx)
        res["tried"].append(r)
        ctx.log(f"  {gate}: {'통과' if r['ok'] else '못 넘음'} " + _brief(r))
        res.update(status="pass" if r["ok"] else "ask_user", value=None,
                   note=None if r["ok"] else "떨어지면 다른 후보로 넘어가지 않고 멈추고 사용자에게 묻는다 (11-12 등록)")
        return res
    if kind == "ordered":
        for i, v in enumerate(cands or sp["cands"]):
            r = MEASURE[gate](ctx, v)
            res["tried"].append(r)
            ctx.log(f"  {gate} {v}: {'통과' if r['ok'] else '못 넘음'} " + _brief(r))
            if r["ok"]:
                res.update(status="pass" if i == 0 else "fixed_pass", value=v, fixed=i > 0)
                return res
        res.update(status="fail", value=None)
        return res
    if kind == "direction":
        v = _current_value(gate, state, ctx.cfg_t)
        r = MEASURE[gate](ctx, v)
        res["tried"].append(r)
        ctx.log(f"  {gate} {v}: {'통과' if r['ok'] else '못 넘음'} " + _brief(r))
        if r["ok"]:
            res.update(status="pass", value=v)
            return res
        if state.get("fixed", {}).get(gate) or r.get("direction") is None:
            res.update(status="ask_user", value=v, note="이미 고친 관문이거나 어긋난 쪽을 정할 수 없음 — 멈추고 묻는다")
            return res
        v2 = sp[r["direction"]]
        r2 = MEASURE[gate](ctx, v2)
        res["tried"].append(r2)
        ctx.log(f"  {gate} {v2} (한 번 고침): {'통과' if r2['ok'] else '못 넘음'} " + _brief(r2))
        res.update(status="fixed_pass" if r2["ok"] else "ask_user", value=v2, fixed=True,
                   note=None if r2["ok"] else "미리 적은 후보로 한 번 고쳐도 띠 밖 — 멈추고 묻는다 (11-12 등록)")
        return res
    if kind == "reward":
        r = MEASURE[gate](ctx)
        res["tried"].append(r)
        if r["ok"]:
            res.update(status="pass", f_enabled=bool(state.get("f_enabled", False)))
        elif r["ok_with_F"] and not state.get("f_enabled"):
            res.update(status="fixed_pass", f_enabled=True, note="대비책 F 를 한 번 걸어 통과 (사용자 승인 11-10) — 보상만 바뀌어 같은 궤적에서 셈")
        else:
            res.update(status="fail", f_enabled=bool(state.get("f_enabled", False)), note="F 를 걸어도 못 넘음 → 띄우지 않는다")
        ctx.log(f"  {gate}: {res['status']} 사슴 차 {_fmt(r['species']['deer']['total_off']['ci'])} 멧돼지 차 {_fmt(r['species']['boar']['total_off']['ci'])}")
        return res
    r = MEASURE[gate](ctx)
    res["tried"].append(r)
    res.update(status="report")
    ctx.log(f"  {gate}: " + _brief(r))
    return res


def _brief(r: dict) -> str:
    keys = ("eat_share", "forage_share", "rest_share", "deer_E_median", "root_share", "pianka", "end_ratio", "L0_change", "extinct",
            "score", "ratio", "diff_ci", "caught_rule", "caught_always_eat", "success_rate", "attempts", "kappa_hunt", "counter_share_adult",
            "adult_caught", "wolf_E_median", "coexist", "j2_primary")
    return " ".join(f"{k} {_fmt(r[k]) if not isinstance(r[k], dict) else {a: round(b, 3) if isinstance(b, float) else b for a, b in r[k].items()}}"
                    for k in keys if k in r)


def _next_cand(gate: str, value):
    sp = C0_SPEC[gate]
    c = list(sp.get("cands", []))
    if value in c and c.index(value) + 1 < len(c):
        return c[c.index(value) + 1]
    return None


def cmd_calibrate(args) -> int:
    base_t, base_j = load_cfgs(args)
    gates = [g for g in C0_ORDER if g in (args.gates or C0_ORDER)]
    out_dir = _p(args.out) if args.out else OUT_CALIB
    if "C0-10" in (args.gates or []):
        return cmd_c010(args, base_t, base_j, out_dir)
    phase = args.phase
    st_t = args.seeds_train or (C.SEED_RANGES["pick_train"] if phase == "pick" else C.SEED_RANGES["confirm_train"])
    st_j = args.seeds_judge or (C.SEED_RANGES["pick_judge"] if phase == "pick" else C.SEED_RANGES["confirm_judge"])
    seeds_t, seeds_j = _seeds(st_t), _seeds(st_j)
    C.assert_calib_seeds(seeds_t + seeds_j, "calibrate")
    state_path = _p(args.state) if args.state else out_dir / "C0_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else dict(values={}, fixed={}, f_enabled=False,
                                                                                                j2_primary="short", history=[])
    ctx = GateCtx(None, None, seeds_t, seeds_j, args.steps_train, args.steps_judge, args.steps_c011, args.chunk)
    results, status = [], "ok"
    t0 = time.time()
    if phase == "pick":
        for g in gates:
            _with_state(ctx, base_t, base_j, state)
            print(f"{g} ({C0_SPEC[g]['rule']})", flush=True)
            r = pick_gate(g, ctx, state, cands=args.cands if args.cands and len(gates) == 1 else None)
            results.append(r)
            _apply(state, g, r)
            if r["status"] in ("fail", "ask_user"):
                status = r["status"]
                break
    else:
        for attempt in (0, 1):
            _with_state(ctx, base_t, base_j, state)
            fails = []
            results = []
            for g in gates:
                print(f"[확인 {attempt}] {g}", flush=True)
                v = _current_value(g, state, base_t) if "path" in C0_SPEC[g] else None
                r = MEASURE[g](ctx, v) if "path" in C0_SPEC[g] else MEASURE[g](ctx)
                ok = bool(r.get("ok", True))
                if g == "C0-11" and not ok and state.get("f_enabled"):
                    ok = bool(r.get("ok_with_F"))
                res = dict(gate=g, value=v, result=r, ok=ok)
                if g == "C0-7c":
                    state["j2_primary"] = r["j2_primary"]
                results.append(res)
                print(f"  {'통과' if ok else '못 넘음'} " + _brief(r), flush=True)
                if not ok:
                    fails.append(g)
            if not fails:
                status = "confirmed"
                break
            if attempt == 1 or any(state.get("fixed", {}).get(g) for g in fails):
                status = "ask_user"
                break
            # 고친 적 없는 관문만 한 번 고친다 → 확인 시드에서 모두 다시. S′ 검토 low: 고칠 내용은 사본에 모으고, 떨어진 관문이 모두 고칠 수 있을
            # 때만 상태에 넣는다 — 하나라도 묻기(C0-1 등)로 끝나면 잰 적 없는 값이 '지금 값'·'이미 고침'으로 남지 않게 history 에 제안으로만 적는다.
            new_values, new_fixed, new_f = dict(state["values"]), dict(state.get("fixed", {})), bool(state.get("f_enabled", False))
            proposed = {}
            for g in fails:
                sp = C0_SPEC[g]
                if sp["kind"] == "check":                     # C0-1 (11-12): 고칠 값이 없다 → 묻는다
                    status = "ask_user"
                    continue
                if sp["kind"] == "reward":
                    new_f = True
                    proposed[g] = "F"
                elif sp["kind"] == "direction":
                    d = next((x["result"].get("direction") for x in results if x["gate"] == g), None)
                    if d is None:
                        status = "ask_user"
                        continue
                    new_values[g] = proposed[g] = sp[d]
                elif sp["kind"] in ("decide", "ordered"):
                    nv = _next_cand(g, _current_value(g, state, base_t))
                    if nv is None:
                        status = "ask_user"
                        continue
                    new_values[g] = proposed[g] = nv
                new_fixed[g] = True
            if status == "ask_user":
                state.setdefault("proposed", []).append(dict(time=time.strftime("%Y-%m-%d %H:%M:%S"), fails=fails, proposed=proposed,
                                                             note="묻기로 끝나 넣지 않음 — 사람이 정한 뒤 넣는다"))
                break
            state["values"], state["fixed"], state["f_enabled"] = new_values, new_fixed, new_f
    state["history"].append(dict(phase=phase, time=time.strftime("%Y-%m-%d %H:%M:%S"), seeds_train=st_t, seeds_judge=st_j,
                                 gates=gates, status=status, values=dict(state["values"]), fixed=dict(state.get("fixed", {})),
                                 f_enabled=state.get("f_enabled", False)))
    if not args.no_state:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(C.to_jsonable(state), ensure_ascii=False, indent=1), encoding="utf-8")
    md = _calib_md(phase, gates, results, state, status, st_t, st_j, args)
    _write(out_dir, f"C0_{phase}{args.tag}", dict(phase=phase, status=status, results=results, state=state, seeds_train=st_t,
                                                  seeds_judge=st_j, steps=dict(train=args.steps_train, judge=args.steps_judge,
                                                                               c011=args.steps_c011), elapsed_s=time.time() - t0), md)
    (out_dir / f"C0_STATUS_append{args.tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0 if status in ("ok", "confirmed") else 2


def _apply(state: dict, gate: str, r: dict) -> None:
    if r.get("value") is not None and r["kind"] in ("decide", "ordered", "direction") and r["status"] in ("pass", "fixed_pass"):
        state["values"][gate] = r["value"]
    if r.get("fixed"):
        state.setdefault("fixed", {})[gate] = True
    if r["kind"] == "reward":
        state["f_enabled"] = bool(r.get("f_enabled", state.get("f_enabled", False)))
        if r["status"] == "fixed_pass":
            state.setdefault("fixed", {})[gate] = True
    if gate == "C0-7c" and r["tried"]:
        state["j2_primary"] = r["tried"][0]["j2_primary"]


def _calib_md(phase, gates, results, state, status, st_t, st_j, args) -> list[str]:
    L = [f"### R9 보정 관문 C0 — {'고르기' if phase == 'pick' else '확인'} ({time.strftime('%Y-%m-%d %H:%M')})", "",
         f"- 시드: 학습 세계 꼴 {st_t[0]}~{st_t[1]}, 판정 세계 꼴 {st_j[0]}~{st_j[1]}. 스텝: 학습 꼴 {args.steps_train} [어림], 판정 꼴 {args.steps_judge}, "
         f"C0-11 {args.steps_c011}. 결과 상태: **{status}**.", "- 관문마다 고칠 값은 하나, 후보·고르는 규칙은 설계 9-1 표 그대로. 고친 기록(한 번만):", ""]
    L.append("| 관문 | 규칙 | 결과 | 정한 값 | 고침 |")
    L.append("|---|---|---|---|---|")
    for r in results:
        g = r["gate"]
        if phase == "pick":
            L.append(f"| {g} | {C0_SPEC[g]['rule']} | {r['status']} | {_fmt(r.get('value', state['values'].get(g)))} | "
                     f"{_fmt(bool(state.get('fixed', {}).get(g, False)))} |")
        else:
            L.append(f"| {g} | {C0_SPEC[g]['rule']} | {'통과' if r['ok'] else '못 넘음'} | {_fmt(r.get('value'))} | "
                     f"{_fmt(bool(state.get('fixed', {}).get(g, False)))} |")
    L += ["", f"- 지금 값: {json.dumps(C.to_jsonable(state['values']), ensure_ascii=False)}, 대비책 F: {'켬' if state.get('f_enabled') else '끔'}, "
               f"J2 주 기준: {'2 시간 판' if state.get('j2_primary') == 'long' else '30 분'}."]
    L.append("- 재본 값(후보마다):")
    for r in results:
        rows = r.get("tried") or [r.get("result", {})]
        for x in rows:
            L.append(f"  - {r['gate']} {_fmt(x.get('value'))}: " + _brief(x))
        if r.get("controls"):
            ctl = r["controls"]
            L.append(f"  - {r['gate']} 등록 조건 0.012: 띠 {'밖 (맞음)' if ctl['neg_fails_band'] else '안 — 등록 조건 깨짐'} " + _brief(ctl["neg"]))
            L.append(f"  - {r['gate']} 보고 0.005: {'기준 통과' if ctl['report']['ok'] else '기준 못 넘음'} " + _brief(ctl["report"]))
        if r.get("note"):
            L.append(f"  - {r['gate']}: {r['note']}")
    if status == "ask_user":
        L.append("- **못 넘은 관문이 있다 — 표에 없는 값을 바꾸지 않고 띄우기 전에 사용자에게 묻는다 (9-1).**")
    return L


# --- C0-10 ------------------------------------------------------------------

C010_DECISIONS = dict(deer=20_000_000, boar=10_000_000, wolf=10_000_000)
C010_WOLF_SHARDS = 3
C010_WOLF_CONTROLS = ("RANDOM", "NOHUNT", "NOHUNT_RUN")          # 등록 조건 (11-12): 이 셋은 늑대 기준에서 떨어져야 한다
# 11-11 C0-9 (처음 세계, STATUS 3-0) 0 바퀴 꼴 결정/초 — S′ 세계-스텝이 1.8~2.3 배라 2.3 으로 나눈 값을 C0-9 다시 잴 때까지 [어림]으로 쓴다
C09_OLD_DPS = dict(deer=11_900.0, boar=3_530.0, wolf=3_758.0)
S_SLOWDOWN = 2.3
C010_WALL_FACTOR = 2.0                                          # 벽시계 안전 상한 = 2 × 어림 시간 (train.wall_cap_factor 와 같은 뜻)


def registered_speeds(decisions_json: str | None = None) -> tuple[dict, str]:
    """0 바퀴 꼴 결정/초 {deer, boar, wolf}: bundle_decisions.json 의 `speed_dps.round0` (C0-9 다시 등록 때 적는다) — 없으면
    11-11 값 ÷ 2.3 [어림]. (speeds, 출처)."""
    p = _p(decisions_json) if decisions_json else HERE.parent / "bundle_decisions.json"
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        sp = (d.get("speed_dps") or {}).get("round0")
        if sp and all(n in sp for n in SPECIES):
            return {n: float(sp[n]) for n in SPECIES}, f"{p} speed_dps.round0"
    except (OSError, ValueError):
        pass
    return {n: C09_OLD_DPS[n] / S_SLOWDOWN for n in SPECIES}, "11-11 C0-9 ÷ 2.3 [어림 — C0-9 다시 잰 뒤 speed_dps 로]"


def c010_plan(gammas=(0.997, 0.99), speeds: dict | None = None, fallback_f: bool = False, out: str = "ckpt/r9/c010",
              log_dir: str = "results/v3/r9/logs", config: str | None = None) -> list[dict]:
    """C0-10 짧은 학습 계획 (9-1): 두 γ 를 같은 시드로 따로 — 사슴 20M(규칙 상대), 멧돼지 10M(규칙 상대), 늑대 10M(규칙 70%·늘 먹기 30% 먹이,
    조각 3). train_r9.py 의 0 바퀴 상대 몫이 곧 이 상대라 --round 0. 학습 세계 시드 = 학습 풀(train.seeds). 갈래 C0_10_* 는 train.model_seeds 에
    없어 --model-seed 0 [해석: 두 γ 같은 모델 시드]. 차례: 먹이 넷(프로세스 4) → 늑대 둘(프로세스 6). est_s = 결정 ÷ 속도 × 1.1 (밤 창 판단),
    wall_hours = 2 × 결정 ÷ 속도 (안전 상한). F 를 걸면 --fallback-f 와 갈래 이름 끝 _F. config 를 주면 train_r9 에 --config 로 넘긴다
    (run_night --config — S′ 검토 low: 옮겨 적는 파일과 배우는 파일이 같게)."""
    if speeds is None:
        speeds, _src = registered_speeds()
    plan = []
    for stage, sps in (("prey", ("deer", "boar")), ("wolf", ("wolf",))):
        for g in gammas:
            tag = f"g{str(g).replace('.', '')}{'_F' if fallback_f else ''}"
            for sp in sps:
                dec = C010_DECISIONS[sp]
                hours = dec / float(speeds[sp]) / 3600.0
                wall = math.ceil(C010_WALL_FACTOR * hours * 10.0) / 10.0
                shards = C010_WOLF_SHARDS if sp == "wolf" else 1
                run = f"r9_c010_{tag}_{sp}"
                args = ["results/v3/r9/train_r9.py", "--species", sp, "--branch", f"C0_10_{tag}", "--model-seed", "0", "--round", "0",
                        "--decisions", str(dec), "--wall-hours", f"{wall:.1f}", "--gamma", str(g), "--run-name", run, "--out", out,
                        "--log-dir", log_dir]
                if shards > 1:
                    args += ["--shards", str(shards)]
                if fallback_f:
                    args.append("--fallback-f")
                if config:
                    args += ["--config", config]
                plan.append(dict(stage=stage, gamma=float(g), species=sp, branch=f"C0_10_{tag}", run=run, decisions=dec, procs=shards,
                                 est_s=hours * 3600.0 * 1.1, wall_hours=wall, args=args, out=out))
    return plan


def c010_commands(gammas=(0.997, 0.99), speeds: dict | None = None, fallback_f: bool = False) -> list[str]:
    """C0-10 짧은 학습 명령 (c010_plan 을 글로). 여기서 돌리지 않는다 — 밤 창 안에서 run_night.py 가 띄운다."""
    out = ["python " + " ".join(p["args"]) for p in c010_plan(gammas, speeds, fallback_f)]
    out.append("# 잼 (확인 시드 44050~44099): python results/v3/r9/eval_r9.py calibrate --gates C0-10 --gamma <γ> "
               "--brain -:deer=<npz> -:boar=<npz> -:wolf=<npz> ; 고르기: --c010-choose calib/C0-10_g0.997.json calib/C0-10_g0.99.json")
    out.append("# 밤 실행기: python -X utf8 results/v3/r9/spawn_detached.py --log results/v3/r9/logs/night.log --what \"night r9\" -- "
               "results/v3/r9/run_night.py --decisions-json results/v3/r9/bundle_decisions.json")
    return out


def _wolf_rew_world(rec: dict) -> tuple[np.ndarray, np.ndarray]:
    """Per-world wolf reward per 1,000 wolf-steps (개체당 보상 — 결정을 시작한 늑대의 보상 합 ÷ 늑대-스텝) and the step counts."""
    rew = np.asarray(rec["rew_sp"])[:, WOLF].astype(np.float64)
    stp = np.asarray(rec["steps_sp"])[:, WOLF].astype(np.float64)
    return np.where(stp > 0, 1000.0 * rew / np.maximum(stp, 1.0), np.nan), stp


def c010_wolf_side(rec: dict) -> dict:
    j3 = C.j3_metrics(rec)
    rw, stp = _wolf_rew_world(rec)
    num, den = _rate_world(rec, WOLF, "daily_kill")
    return dict(rew_1k_world=rw.tolist(), rew_1k=float(np.nansum(np.where(np.isfinite(rw), rw * stp, 0.0)) / max(float(stp.sum()), 1.0)),
                success_rate=j3["success_rate_strict"], attempts=j3["strict_attempts"], kappa_hunt=j3["kappa_hunt"],
                kappa_all=C.ratio(num, den), kappa_incidental=j3["kappa_incidental"], kappa_run=j3["kappa_run"],
                kappa_traj4=j3["kappa_traj4"], kills=j3["kills"], E_median=C.species_metrics(rec)["wolf"]["E_median"],
                scavenge_share=j3["scavenge_share"])


def _paired_diff(a: dict, b: dict) -> dict:
    x, y = np.asarray(a["rew_1k_world"], dtype=np.float64), np.asarray(b["rew_1k_world"], dtype=np.float64)
    m = np.isfinite(x) & np.isfinite(y)
    d, ci = C.boot_mean(x[m] - y[m])
    return dict(diff=d, ci=ci, worlds=int(m.sum()))


def c010_wolf_verdict(side: dict, rule: dict, random: dict, watch: dict) -> dict:
    """늑대 셋 조건 (11-12): (가) 개체당 보상 − RANDOM, − 늘 살피기 의 세계 짝 95% 아래 끝 둘 다 > 0 ∧ (나) strict 사냥 성공률 ≥ 0.5 ×
    RULE_WOLF ∧ (다) strict 사냥 죽임 κ ≥ 0.5 × RULE_WOLF. RANDOM 자신은 (가)의 RANDOM 차가 0 이라 늘 떨어진다."""
    dr, dw = _paired_diff(side, random), _paired_diff(side, watch)
    ga = bool(math.isfinite(dr["ci"][0]) and dr["ci"][0] > 0 and math.isfinite(dw["ci"][0]) and dw["ci"][0] > 0)
    sr, rr = side["success_rate"], rule["success_rate"]
    kh, rk = side["kappa_hunt"], rule["kappa_hunt"]
    gb = bool(math.isfinite(sr) and math.isfinite(rr) and sr >= 0.5 * rr)
    gc = bool(math.isfinite(kh) and math.isfinite(rk) and kh >= 0.5 * rk)
    return dict(minus_random=dr, minus_watch=dw, a_reward=ga, b_success=gb, c_kappa=gc, ok=bool(ga and gb and gc))


def c010_measure(cfg_t: dict, brains: dict, seeds, steps: int, chunk) -> dict:
    """C0-10 잼 (확인 시드): 짧게 배운 두뇌를 규칙 상대와 — 사슴 잡힘 ≤ 0.7 × ALWAYS_EAT·먹음 ≥ 0.7 ×·은신처 ≤ 0.6, 멧돼지 먹음 ≥ 0.7 ×·
    은신처 ≤ 0.6 (사양서 그대로). 늑대 (11-12): 먹이 규칙 70%·늘 먹기 30% 판에서 늑대 자리에 학습 늑대 / RULE_WOLF / RANDOM / 늘 살피기 /
    NOHUNT(사체 쪽 걷기) / NOHUNT_RUN(사체 쪽 뛰기) 을 같은 세계로 — 학습 늑대의 셋 조건과 음성 대조 셋이 떨어지는지(등록 조건)."""
    cfg = B.override(cfg_t, EVAL_FACING)
    out = {}

    def sm(specs, sp):
        rec = C.run(cfg, seeds, steps, spec_fn(cfg, specs, brains), scenes=False, chunk=chunk)
        return C.species_metrics(rec)[SPECIES[sp]], rec
    for sp, key in ((DEER, "-:deer"), (BOAR, "-:boar")):
        if key not in brains:
            continue
        base = rule_specs()
        m, _ = sm({**base, sp: "-"}, sp)
        ae, _ = sm({**base, sp: "ALWAYS_EAT"}, sp)
        ok = (m["eaten_x1000"] >= 0.7 * ae["eaten_x1000"]) and (m["in_shelter"] <= 0.6)
        if sp == DEER:
            ok = ok and (m["caught_1k"] <= 0.7 * ae["caught_1k"])
        out[SPECIES[sp]] = dict(brain=m, always_eat=ae, ok=bool(ok))
    is_rule = lambda k: (k % 10) < int(round(PREY_MIX_RULE * 10))   # noqa: E731
    prey = {DEER: lambda k: "RULE_DEER" if is_rule(k) else "ALWAYS_EAT", BOAR: lambda k: "RULE_BOAR" if is_rule(k) else "ALWAYS_EAT"}
    names = (["-"] if "-:wolf" in brains else []) + ["RULE_WOLF", "RANDOM", C.WATCH_ONLY, *[c for c in C010_WOLF_CONTROLS if c != "RANDOM"]]
    side = {}
    for nm in names:
        rec = C.run(cfg, seeds, steps, spec_fn(cfg, {**prey, WOLF: nm}, brains), scenes=False, chunk=chunk, progress=f"C0-10 늑대 {nm}")
        side[nm] = c010_wolf_side(rec)
    ref = (side["RULE_WOLF"], side["RANDOM"], side[C.WATCH_ONLY])
    controls = {c: c010_wolf_verdict(side[c], *ref) for c in C010_WOLF_CONTROLS}
    wolf = dict(rule=side["RULE_WOLF"], random=side["RANDOM"], watch=side[C.WATCH_ONLY],
                nohunt=side["NOHUNT"], nohunt_run=side["NOHUNT_RUN"], controls=controls,
                registration_ok=bool(not any(v["ok"] for v in controls.values())),
                scavenger_minus_rule=_paired_diff(side["NOHUNT"], side["RULE_WOLF"]))
    if "-" in side:
        wolf["brain"] = side["-"]
        wolf["learned"] = c010_wolf_verdict(side["-"], *ref)
        wolf["ok"] = bool(wolf["learned"]["ok"])
    else:
        wolf["ok"] = False
    out["wolf"] = wolf
    return out


def c010_choose(res: dict[str, dict]) -> dict:
    """9-1 C0-10 고르는 규칙: 두 γ 모두 넘으면 0.997, 하나만이면 그것. 먹이 종 기준을 둘 다 못 넘으면 F 걸고 둘 다 다시. 늑대만 못 넘으면 0 바퀴
    첫 10M 은 늘 먹기 먹이 100%. 11-12 등록 조건: 음성 대조 늑대(RANDOM·NOHUNT·NOHUNT_RUN)가 하나라도 기준을 통과하면 고르지 않고 묻는다."""
    reg = {g: r.get("wolf", {}).get("registration_ok", True) for g, r in res.items()}
    if not all(reg.values()):
        return dict(gamma=None, action="ask_user", why="음성 대조 늑대가 늑대 기준을 통과 — 기준이 체 구실을 못 함 (등록 조건, 11-12)")
    prey_ok = {g: all(r.get(s, {}).get("ok", False) for s in ("deer", "boar")) for g, r in res.items()}
    wolf_ok = {g: r.get("wolf", {}).get("ok", False) for g, r in res.items()}
    both = {g: prey_ok[g] and wolf_ok[g] for g in res}
    passing = [g for g in ("0.997", "0.99") if both.get(g)]
    if passing:
        return dict(gamma=float(passing[0]), action="pass")
    if not any(prey_ok.values()):
        return dict(gamma=None, action="enable_F_and_rerun_both")
    pg = [g for g in ("0.997", "0.99") if prey_ok.get(g)]
    return dict(gamma=float(pg[0]), action="wolf_round0_first10M_always_eat_100")


def cmd_c010(args, base_t, base_j, out_dir) -> int:
    if args.c010_commands:
        speeds, src = registered_speeds(getattr(args, "decisions_json", None))
        cmds = c010_commands(speeds=speeds)
        print("\n".join(cmds))
        _write(out_dir, "C0-10_commands", dict(commands=cmds, plan=c010_plan(speeds=speeds), speeds=speeds, speeds_from=src,
                                               note="학습 풀 43000~43999, 잼은 확인 시드 44050~44099 (9-1). 여기서 돌리지 않는다 — 밤 창 안에서만 "
                                                    "(run_night.py, STATUS 5절)."))
        return 0
    if args.c010_choose:
        res = {}
        for p in args.c010_choose:
            d = json.loads(_p(p).read_text(encoding="utf-8"))
            res[str(d["gamma"])] = d["result"]
        ch = c010_choose(res)
        print(json.dumps(ch, ensure_ascii=False))
        _write(out_dir, "C0-10_choice", dict(inputs=args.c010_choose, choice=ch))
        return 0
    seeds = _seeds(args.seeds_train or C.SEED_RANGES["confirm_train"])
    C.assert_calib_seeds(seeds, "calibrate C0-10")
    state_path = _p(args.state) if args.state else out_dir / "C0_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else dict(values={})
    # S′ 검토 medium: the short training read the YAML only — measure in the same world (C0 values already in the YAML; the γ
    # itself is not a world value). run_night's F attempt passes `--set reward.fallback_f.enabled=true`, so F matches as well.
    check_c0_state(base_t, base_j, "calibrate C0-10", path=state_path, skip_gates=("C0-10",))
    ct, _cj = _state_cfgs(base_t, base_j, {**state, "values": {g: v for g, v in state.get("values", {}).items() if g != "C0-10"}})
    brains = C.load_brains(C.parse_brain_args(args.brain), ct)
    r = c010_measure(ct, brains, seeds, args.steps_train, args.chunk)
    _write(out_dir, f"C0-10_g{args.gamma}{args.tag}", dict(gamma=args.gamma, seeds=[seeds[0], seeds[-1]], result=r))
    print(json.dumps(C.to_jsonable({k: v.get("ok") for k, v in r.items()}), ensure_ascii=False))
    return 0


# --------------------------------------------------------------------------- #
# leak (4-6)
# --------------------------------------------------------------------------- #

ACT_GROUP = np.zeros(B.N_ACTIONS, dtype=np.int64)
ACT_GROUP[B.WALK_FIRST:B.WALK_LAST + 1] = 1
ACT_GROUP[B.RUN_FIRST:B.RUN_LAST + 1] = 2
ACT_GROUP[B.SHELTER] = 3
ACT_GROUP[B.WATCH] = 4
ACT_GROUP_NAMES = ("eat", "walk", "run", "shelter", "watch")


def obs_invariance(cfg: dict, seeds, steps: int) -> dict:
    """4-6·12절 2·3 을 돌아가는 세계에서 다시: (i) 숨은 종 번호 sp 를 엉뚱한 값으로 바꾸고 관측을 다시 만들어도 같다, (ii) kin_id 순열을
    (사체 kin 과 함께) 바꿔도 같다, (iii) 정렬 동점 몫(같은 거리의 다른 종 칸 둘)."""
    from env_v2.r9_world import R9World

    w = R9World(cfg, list(seeds), record=False)
    fn = spec_fn(cfg, rule_specs(), {})
    for k in range(w.K):
        for sp in range(3):
            w.set_controller(k, sp, fn(k, sp, seeds[k]))
    for _ in range(int(steps) // w.D):
        w.step(w.decide())
    o0 = w.obs().copy()
    w.refresh()
    same0 = bool(np.array_equal(o0, w.obs()))
    sp_keep = w.sp.copy()
    w.sp[...] = -7
    w.refresh()
    same_sp = bool(np.array_equal(o0, w.obs()))
    w.sp[...] = sp_keep
    old = w.kin_perm.copy()
    kin_keep, carc_keep = w.kin_id.copy(), w.carc_kin.copy()
    newp = np.roll(old, 1, axis=1)
    mp = np.full((w.K, 3), -1, dtype=np.int8)
    for k in range(w.K):
        for s in range(3):
            mp[k, int(old[k, s])] = newp[k, s]
    w.kin_id = newp[np.arange(w.K)[:, None], w.slot_sp[None, :].astype(np.int64)].astype(np.int8)
    w.carc_kin = np.where(w.carc_kin >= 0, mp[np.arange(w.K)[:, None], np.maximum(w.carc_kin, 0)], -1).astype(np.int8)
    w.refresh()
    same_kin = bool(np.array_equal(o0, w.obs()))
    w.kin_id, w.carc_kin = kin_keep, carc_keep
    w.refresh()
    d = o0[..., [B.other_col(j, "dist") for j in range(B.N_OTHER)]]
    pres = o0[..., [B.other_col(j, "present") for j in range(B.N_OTHER)]] > 0.5
    tie = (pres[..., 1:] & pres[..., :-1] & (d[..., 1:] == d[..., :-1])).any(-1)
    has2 = pres[..., 1]
    return dict(refresh_same=same0, sp_poison_same=same_sp, kin_perm_same=same_kin,
                tie_share=float(tie[has2].mean()) if has2.any() else float("nan"), n_two_others=int(has2.sum()))


STAND_SPEED = 0.03          # 단위/스텝 — 소리 문턱과 같은 '서 있음' 기준


def cmd_leak(args) -> int:
    """4-6 이름표 새는 길: 종 X 를 두 두뇌(학습 두뇌 — 없으면 RANDOM — 와 규칙 두뇌)로 해시 반반 나눈 세계에서, 남이 본 X 개체의
    단서(크기·속력·눈에 안 보임)로 두뇌를 가르는 나무 분류기 AUC (같은 종·같은 행동 묶음 층마다, 세계 절반 학습·절반 시험).
    [해석] '정지 단서' = 서 있는(속력 < 0.03) 개체의 단서 — 판정은 서 있는 층(먹기·은신처·살피기)만 본다. 움직이는 층은 가속 기억처럼
    행동에서 나온 정당한 단서가 섞여 보고만 한다. + 관측 불변 점검 + 다시 남 자리(먼 꼴이 다른 종에서 20 단위 밖)."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.metrics import roc_auc_score

    ct, _cj = load_cfgs(args)
    seeds = _seeds(args.seeds)
    C.assert_not_judge_seeds(seeds, "leak")
    C.warn_calib_seeds(seeds, "leak")
    cfg = B.override(ct, EVAL_FACING)
    brains = C.load_brains(C.parse_brain_args(args.brain), cfg)
    out = dict(seeds=args.seeds, steps=args.steps, species={})
    far = []
    oc = {f: [B.other_col(j, f) for j in range(B.N_OTHER)] for f in ("present", "vel_x", "vel_y", "size", "not_seen")}
    for sp in range(3):
        key = next((k for k in brains if k.endswith(":" + SPECIES[sp])), None)
        first = brains[key] if key else C.rule_brain("RANDOM", cfg)
        second = C.rule_brain(C.RULE_OF[sp], cfg)
        rows = []

        def hook(w, rec, a, c0, sp=sp, rows=rows):
            if rec.n_dec % 3:
                return
            o = w.obs()
            oth, _kin = w.obs_maps()
            for j in range(B.N_OTHER):
                ki, ii = np.nonzero(w.alive & (oth[..., j] >= 0) & (o[..., oc["present"][j]] > 0.5))
                if not len(ki):
                    continue
                js = oth[ki, ii, j]
                m = (rec.ssp[js] == sp) & (rec.group[ki, js] >= 0)
                if not m.any():
                    continue
                ki, ii, js = ki[m], ii[m], js[m]
                spd = np.sqrt(o[ki, ii, oc["vel_x"][j]].astype(np.float64) ** 2 + o[ki, ii, oc["vel_y"][j]].astype(np.float64) ** 2)
                rows.append(np.stack([ki + c0, rec.group[ki, js], ACT_GROUP[w.act[ki, js]], o[ki, ii, oc["size"][j]], spd,
                                      o[ki, ii, oc["not_seen"][j]]], 1).astype(np.float64))
        rec = C.run(cfg, seeds, args.steps, spec_fn(cfg, rule_specs(), brains), split=dict(sp=sp, first=first, second=second),
                    scenes=False, chunk=args.chunk, on_decision=hook)
        far += [d for (_k, s, d) in rec["resp_far"]]
        X = np.concatenate(rows, 0) if rows else np.zeros((0, 6))
        half = len(seeds) // 2
        res = dict(first=first.name, second=second.name, n=int(len(X)), strata={}, moving={})
        standing = X[:, 4] * float(B.OBS_NORM["vel"]) < STAND_SPEED
        for gi, gname in [(i, n) for i, n in enumerate(ACT_GROUP_NAMES)] + [(i + 10, "move_" + n) for i, n in enumerate(ACT_GROUP_NAMES)]:
            m = (X[:, 2] == gi % 10) & (standing if gi < 10 else ~standing)
            dest = res["strata"] if gi < 10 else res["moving"]
            if gi < 10 and gname in ("walk", "run"):
                continue
            tr, te = m & (X[:, 0] < half), m & (X[:, 0] >= half)
            n0, n1 = int((X[te, 1] == 0).sum()), int((X[te, 1] == 1).sum())
            if min(n0, n1) < 50 or len(np.unique(X[tr, 1])) < 2:        # [어림] 층마다 시험 표본 50 미만이면 재지 않는다
                dest[gname] = dict(auc=None, n=[n0, n1])
                continue
            clf = HistGradientBoostingClassifier(max_iter=200, random_state=0).fit(X[tr][:, 3:6], X[tr, 1])
            auc = float(roc_auc_score(X[te, 1], clf.predict_proba(X[te][:, 3:6])[:, 1]))
            dest[gname] = dict(auc=auc, n=[n0, n1])
        out["species"][SPECIES[sp]] = res
        print(SPECIES[sp], {g: _fmt(v["auc"]) for g, v in res["strata"].items()}, flush=True)
    out["invariance"] = obs_invariance(cfg, seeds[:min(4, len(seeds))], min(args.steps, 200))
    out["respawn_far"] = dict(n=len(far), share_ge20=float(np.mean(np.asarray(far) >= 20.0)) if far else float("nan"))
    aucs = [v["auc"] for s in out["species"].values() for v in s["strata"].values() if v["auc"] is not None]
    inv = out["invariance"]
    out["ok"] = bool(inv["refresh_same"] and inv["sp_poison_same"] and inv["kin_perm_same"] and all(0.4 <= a <= 0.6 for a in aucs))
    md = ["# R9 이름표 새는 길 점검 (설계 4-6)", "", f"- 시드 {args.seeds[0]}~{args.seeds[1]}, {args.steps} 스텝. 층 = 본 개체의 종 × 그 결정 행동 묶음.",
          "- 서 있는(속력 < 0.03) 개체의 단서(크기·속력·눈에 안 보임)로 두 두뇌를 가르는 나무 분류기 AUC — 0.4~0.6 이면 새는 길 없음 [어림 띠].", ""]
    for s, v in out["species"].items():
        md.append(f"- {s} ({v['first']} 대 {v['second']}) 서 있는 층: " + ", ".join(f"{g} {_fmt(x['auc'])} (n {x['n']})" for g, x in v["strata"].items())
                  + " / 움직이는 층(보고만): " + ", ".join(f"{g[5:]} {_fmt(x['auc'])}" for g, x in v["moving"].items()))
    md += ["", f"- 관측 불변: 다시 만들기 {_fmt(inv['refresh_same'])}, sp 바꿈 {_fmt(inv['sp_poison_same'])}, kin 순열 {_fmt(inv['kin_perm_same'])}, "
               f"정렬 동점 몫 {_fmt(inv['tie_share'], 5)} (n {inv['n_two_others']})",
           f"- 먼 꼴 다시 남이 다른 종에서 20 단위 밖인 몫: {_fmt(out['respawn_far']['share_ge20'])} (n {out['respawn_far']['n']})",
           f"- 종합: {'새는 길 없음' if out['ok'] else '확인 필요'}"]
    _write(_p(args.out) if args.out else OUT_CALIB, f"leak{args.tag}", out, md)
    print("\n".join(md))
    return 0


# --------------------------------------------------------------------------- #
# mixed (8-1, J1)
# --------------------------------------------------------------------------- #

def _gate_judge_seeds(args, seeds, allowed, who, ct, cj, brain_paths, steps_req: dict) -> bool:
    jm = C.judge_seed_mode(seeds, allowed, who)
    if not jm:
        return False
    if args.set:
        raise C.JudgeSeedError(f"{who}: 판정 시드에서는 --set 덮어쓰기를 받지 않는다")
    for name, (got, want) in steps_req.items():
        if got != want:
            raise C.JudgeSeedError(f"{who}: 판정 시드에서는 등록한 {name} {want} 를 줄이거나 바꾸지 않는다 (받음 {got})")
    lock = _p(args.lock) if args.lock else LOCK_PATH
    if args.lock and not _under_temp(lock):
        # Fix 단계 검토 low: 다른 잠금 파일을 주면 같은 판정 시드를 다른 두뇌로 다시 쓸 수 있었다 (시험의 임시 폴더만 예외)
        raise C.JudgeSeedError(f"{who}: 판정 시드에서는 --lock 을 바꾸지 않는다 ({LOCK_PATH} 만)")
    check_c0_state(ct, cj, who)
    C.judge_gate(lock, brain_paths, ct, cj, who, seeds)
    return True


def _under_temp(p: Path) -> bool:
    import tempfile

    try:
        Path(p).resolve().relative_to(Path(tempfile.gettempdir()).resolve())
        return True
    except ValueError:
        return False


def check_c0_state(ct: dict, cj: dict, who: str, path: Path | None = None, skip_gates=(), skip_f: bool = False) -> dict | None:
    """Fix 단계 검토 low: the calibrated values (C0_STATE.json values · f_enabled) must already be written into the YAML that
    judge · mixed · check · league read — otherwise they would run with the first candidates silently. None = no C0_STATE yet
    (보정 전 시운전). S′ 검토 medium: the C0-10 short training (run_night) and the C0-10 measurement check the same way so the
    trained world and the measured world are the same — they skip the C0-10 γ itself (`skip_gates`) and, in run_night's F attempt,
    the F flag run_night wrote before training with --fallback-f (`skip_f`)."""
    p = Path(path) if path is not None else OUT_CALIB / "C0_STATE.json"
    if not p.exists():
        return None
    st = json.loads(p.read_text(encoding="utf-8"))
    bad = []
    for g, v in st.get("values", {}).items():
        sp = C0_SPEC.get(g)
        if not sp or "path" not in sp or v is None or g in skip_gates:
            continue
        for name, cfg in (("train", ct), ("judge", cj)):
            cur = cfg
            try:
                for key in sp["path"]:
                    cur = cur[key]
            except (KeyError, TypeError):
                continue
            a, b = np.asarray(cur, dtype=np.float64), np.asarray(v, dtype=np.float64)
            if a.shape != b.shape or not np.allclose(a, b, rtol=0.0, atol=1e-12):
                bad.append(f"{g} {name}: 설정 {cur} ≠ C0_STATE {v}")
    if not skip_f and bool(st.get("f_enabled", False)) != bool(ct["reward"]["fallback_f"]["enabled"]):
        bad.append(f"대비책 F: 설정 {ct['reward']['fallback_f']['enabled']} ≠ C0_STATE {st.get('f_enabled')}")
    if bad:
        raise SystemExit(f"{who}: 보정 관문 값(C0_STATE {p})이 설정 파일에 옮겨지지 않았다 — " + "; ".join(bad)
                         + ". configs/v3_r9.yaml 에 옮겨 적은 뒤 다시 돌린다")
    return st


def _need_seeds(args, who: str, judge_range) -> None:
    """Fix 단계 검토 low: judge·mixed no longer default to the judge seeds — a trial run without --seeds used to write the lock
    and spend the judge seeds."""
    if args.seeds is None:
        raise SystemExit(f"{who}: --seeds 를 꼭 적는다 (판정은 {judge_range[0]} {judge_range[1]}, 시운전은 개발·점검 시드)")


def mixed_counts(cfg: dict, K: int) -> np.ndarray:
    wc = [int(x) for x in cfg["eval_mixed"]["wolf_counts"]]
    return counts_with(K, wolf=lambda k: wc[k % len(wc)])


def cmd_mixed(args) -> int:
    ct, cj = load_cfgs(args)
    _need_seeds(args, "mixed", C.SEED_RANGES["judge_j1"])
    seeds = _seeds(args.seeds)
    steps = int(args.steps or ct["eval_mixed"]["steps"])
    paths = C.parse_brain_args(args.brain)
    cfg = B.override(ct, EVAL_FACING)
    brains = C.load_brains(paths, cfg)          # body-hash check first: a refused brain must not write the judge lock
    judged = _gate_judge_seeds(args, seeds, C.SEED_RANGES["judge_j1"], "mixed", ct, cj, paths,
                               dict(steps=(steps, int(ct["eval_mixed"]["steps"])),
                                    seeds=(tuple(args.seeds), C.SEED_RANGES["judge_j1"])))
    if not judged:
        check_c0_state(ct, cj, "mixed")
    branches = [b for b in (args.branches or C.BRANCHES) if all(f"{b}:{s}" in brains for s in SPECIES)]
    if not branches:
        raise SystemExit("mixed: 갈래 하나의 세 종 두뇌(--brain A:deer=… A:wolf=… A:boar=…)가 필요하다")
    K = len(seeds)
    counts = mixed_counts(cfg, K)
    out = dict(judged=judged, seeds=args.seeds, steps=steps, others=args.others, branches={})
    for b in branches:
        res = {}
        others = b if args.others == "final" else "rule"
        all_learned = None
        if args.others == "final":
            print(f"[{b}] 무리 전체 두뇌", flush=True)
            all_learned = C.run(cfg, seeds, steps, spec_fn(cfg, {s: b for s in range(3)}, brains), counts=counts, scenes=True,
                                chunk=args.chunk, progress=f"{b} all")
        for sp in (args.species or range(3)):
            sp = int(sp) if not isinstance(sp, str) else B.SPECIES_INDEX[sp]
            nm = SPECIES[sp]
            specs = {s: others for s in range(3)}
            print(f"[{b}] {nm}: 섞인 무리", flush=True)
            rmix = C.run(cfg, seeds, steps, spec_fn(cfg, specs, brains), counts=counts, scenes=False, chunk=args.chunk,
                         split=dict(sp=sp, first=brains[f"{b}:{nm}"], second=C.rule_brain(C.RULE_OF[sp], cfg)), progress=f"{b} {nm} mixed")
            rL = all_learned if all_learned is not None else C.run(cfg, seeds, steps, spec_fn(cfg, {**specs, sp: b}, brains), counts=counts,
                                                                    scenes=False, chunk=args.chunk)
            rR = C.run(cfg, seeds, steps, spec_fn(cfg, {**specs, sp: "rule"}, brains), counts=counts, scenes=False, chunk=args.chunk,
                       progress=f"{b} {nm} all-rule")
            smx = C.split_metrics(rmix)
            whole, whole_ci = C.boot_rate_diff(rL["rew_sp"][:, sp], rL["steps_sp"][:, sp], rR["rew_sp"][:, sp], rR["steps_sp"][:, sp])
            ga = bool(smx["r_nb"]["ci"][0] > 0)
            gb = bool(whole > 0)
            comp = dict(eaten=smx["eaten"], bite=smx["d_bite"], counter=smx["d_counter"], starve=smx["d_starve"])
            if sp == WOLF:
                comp["note"] = "늑대 하루 잡이·HP 손실은 무리 전체 비교의 j3/species 칸에 있다 (섞인 무리에서 늑대 개체별 잡이는 kills 의 wolf_uid 로)"
            res[nm] = dict(mixed=smx, whole_diff=whole, whole_ci=whole_ci, pass_a=ga, pass_b=gb, J1=bool(ga and gb), components=comp,
                           learned_species=C.species_metrics(rL)[nm], rule_species=C.species_metrics(rR)[nm])
            print(f"  (가) 번식 뺀 보상 차 {_fmt(smx['r_nb']['diff'])} {_fmt(smx['r_nb']['ci'])} (나) 전체 차 {_fmt(whole)} → "
                  f"{'통과' if ga and gb else '실패'}", flush=True)
        entry = dict(species=res)
        if all_learned is not None:
            entry["j3_train_form"] = C.j3_metrics(all_learned)
            entry["anomaly_train_form"] = C.anomaly_metrics(all_learned)
        out["branches"][b] = entry
    verdict = j1_verdict(out)
    out["J1"] = verdict
    md = _mixed_md(out)
    _write(_p(args.out) if args.out else OUT_EVAL, f"mixed{'_' + args.others if args.others != 'final' else ''}{args.tag}", out, md)
    print("\n".join(md))
    return 0


def j1_verdict(out: dict) -> dict:
    """9-2 J1: 세 종 × 두 갈래 6 가운데 5 이상 통과, 두 갈래 모두 실패한 종 없음 (두 갈래를 다 잰 때만 판정)."""
    cells = {(b, s): v["J1"] for b, e in out["branches"].items() for s, v in e["species"].items()}
    n = sum(cells.values())
    both_fail = [s for s in SPECIES if all((b, s) in cells and not cells[(b, s)] for b in C.BRANCHES)]
    complete = all((b, s) in cells for b in C.BRANCHES for s in SPECIES)
    return dict(cells={f"{b}:{s}": v for (b, s), v in cells.items()}, passed=int(n), complete=complete, both_branch_fail=both_fail,
                J1=bool(complete and n >= 5 and not both_fail))


def _mixed_md(out: dict) -> list[str]:
    L = [f"# R9 J1 — 종마다 규칙 두뇌보다 낫나 (섞인 무리, 설계 8-1) {'— 판정' if out['judged'] else '— 시운전 (판정 시드 아님)'}", "",
         f"- 시드 {out['seeds'][0]}~{out['seeds'][1]}, {out['steps']} 스텝, 학습 세계 꼴(다시 남), 늑대 2 + (k mod 5), 다른 두 종 = "
         f"{'같은 갈래 최종 두뇌' if out['others'] == 'final' else '규칙 두뇌(덧붙여 보기)'}. 배정 = 세계 시드·개체 ID 해시, 성별 × 어린/성체 층 반반.",
         "- (가) 번식 항을 뺀 보상(0.01·살아 있음 + 에너지 순변화 − 10·죽음) 개체당 1,000 스텝, 학습 − 규칙 95% 아래 끝 > 0. (나) 무리 전체 두뇌 − 무리 전체 규칙 (전체 보상) > 0.", "",
         "| 갈래 | 종 | (가) 차 | 95% | (나) 차 | 95% | 출산/자격 1k (학습·규칙) | 짝 조합 학×학·학×규·규×규 | 판정 |", "|---|---|---|---|---|---|---|---|---|"]
    for b, e in out["branches"].items():
        for s, v in e["species"].items():
            m = v["mixed"]
            L.append(f"| {b} | {s} | {_fmt(m['r_nb']['diff'])} | {_fmt(m['r_nb']['ci'])} | {_fmt(v['whole_diff'])} | {_fmt(v['whole_ci'])} | "
                     f"{_fmt(m['births_per_1k_eligible']['first'])}·{_fmt(m['births_per_1k_eligible']['second'])} | "
                     f"{m['pair_combo']['first_first']}·{m['pair_combo']['first_second']}·{m['pair_combo']['second_second']} | "
                     f"{'통과' if v['J1'] else '실패'} |")
    v = out["J1"]
    L += ["", f"- J1: 통과 {v['passed']}/6, 두 갈래 모두 실패한 종 {v['both_branch_fail'] or '없음'} → "
              f"{('**통과**' if v['J1'] else '**실패**') if v['complete'] else '두 갈래를 다 재지 않아 판정 안 함'}"]
    return L


# --------------------------------------------------------------------------- #
# judge (8-2, J2·J3)
# --------------------------------------------------------------------------- #

def batch_specs(batch: str) -> dict:
    prey, wolf = BATCHES[batch]
    return {DEER: prey, BOAR: prey, WOLF: wolf}


def run_batch(cfg: dict, seeds, steps: int, specs: dict, brains: dict, chunk, label: str, scenes: bool = True) -> dict:
    greedy = bool(cfg["judge"]["greedy"])
    t0 = time.time()
    rec = C.run(cfg, seeds, steps, spec_fn(cfg, specs, brains, stochastic=not greedy), scenes=scenes, chunk=chunk, progress=label)
    el = time.time() - t0
    res = dict(label=label, seeds=[seeds[0], seeds[-1]], worlds=len(seeds), steps=steps, greedy=greedy, elapsed_s=el,
               ms_per_world_step=1000.0 * el / max(1, len(seeds) * steps),
               species=C.species_metrics(rec), population=C.population_metrics(rec), j3=C.j3_metrics(rec))
    if scenes:
        res["scenes"] = C.scene_metrics(rec)
        res["anomaly"] = C.anomaly_metrics(rec)
    res["_pop"] = rec["pop"].sum(2).astype(np.int16)                  # (T, K, 3) for plots
    res["_pop_t"] = rec["pop_t"]
    return res


def cmd_judge(args) -> int:
    ct, cj = load_cfgs(args)
    jd = cj["judge"]
    _need_seeds(args, "judge", C.SEED_RANGES["judge_j2"])
    seeds_all = _seeds(args.seeds)
    steps = int(args.steps or jd["steps"])
    paths = C.parse_brain_args(args.brain)
    brains = C.load_brains(paths, cj)           # body-hash check first: a refused brain must not write the judge lock
    judged = _gate_judge_seeds(args, seeds_all, C.SEED_RANGES["judge_j2"], "judge", ct, cj, paths,
                               dict(steps=(steps, int(jd["steps"])), seeds=(tuple(args.seeds), C.SEED_RANGES["judge_j2"]),
                                    steps_long=(int(args.steps_long or jd["steps_long"]), int(jd["steps_long"]))))
    if not judged:
        check_c0_state(ct, cj, "judge")
    out_dir = _p(args.out) if args.out else OUT_EVAL
    batches = args.batches or list(BATCHES)
    have = {b for b in C.BRANCHES if all(f"{b}:{s}" in brains for s in SPECIES)}
    batches = [x for x in batches if all(v == "rule" or v in have for v in BATCHES[x])]
    out = dict(judged=judged, seeds=args.seeds, steps=steps, batches={}, long={}, variants={})
    pops = {}
    fb = [f"L_{b}" for b in (args.for_branches or C.BRANCHES)]          # long runs / variants of these branches (process split)
    if args.long_only:
        batches = []
    for bt in batches:
        print(f"[{bt}]", flush=True)
        r = run_batch(cj, seeds_all, steps, batch_specs(bt), brains, args.chunk, bt)
        pops[bt] = (r.pop("_pop"), r.pop("_pop_t"))
        out["batches"][bt] = r
        _brief_batch(bt, r)
    if args.long:
        nl = int(jd["worlds_long"])
        sl = seeds_all[:nl]
        stl = int(args.steps_long or jd["steps_long"])
        for bt in [x for x in fb if all(v in have for v in BATCHES[x])]:
            print(f"[{bt} 2 시간]", flush=True)
            r = run_batch(cj, sl, stl, batch_specs(bt), brains, args.chunk, bt + "_long")
            pops[bt + "_long"] = (r.pop("_pop"), r.pop("_pop_t"))
            out["long"][bt] = r
            _brief_batch(bt + "_long", r)
    for v in args.variants or []:
        for bt in [x for x in fb if all(y in have for y in BATCHES[x])]:
            if v == "ratio":
                nr = min(60, len(seeds_all))
                thirds = np.array_split(np.asarray(seeds_all[:nr]), 3)
                parts = {}
                for (vname, (dn, bn)), sd in zip(RATIO_SETS, thirds):
                    cfg = B.override(cj, cj["judge"]["variants"][vname]) if vname else cj
                    r = run_batch(cfg, [int(x) for x in sd], steps, batch_specs(bt), brains, args.chunk, f"{bt}_ratio_{dn}_{bn}")
                    r.pop("_pop"), r.pop("_pop_t")
                    parts[f"{dn}_{bn}"] = r
                out["variants"].setdefault("ratio", {})[bt] = parts
                continue
            cfg = B.override(cj, cj["judge"]["variants"][v])
            r = run_batch(cfg, seeds_all, steps, batch_specs(bt), brains, args.chunk, f"{bt}_{v}")
            pops[f"{bt}_{v}"] = (r.pop("_pop"), r.pop("_pop_t"))
            out["variants"].setdefault(v, {})[bt] = r
            _brief_batch(f"{bt}_{v}", r)
            if bt in out["batches"]:
                a = np.asarray(out["batches"][bt]["population"]["coexist_worlds"], dtype=np.float64)
                bb = np.asarray(r["population"]["coexist_worlds"], dtype=np.float64)
                r["paired_coexist_diff"] = C.boot_mean(bb - a)            # 같은 판정 시드 = 같은 시작 세계 → 세계별 짝 비교
    out["verdict"] = judge_verdict(out, _calib_state())
    tag = args.tag
    _write(out_dir, f"judge{tag}", out, _judge_md(out))
    np.savez_compressed(out_dir / f"judge{tag}_pop.npz", **{k: v[0] for k, v in pops.items()}, **{k + "__t": v[1] for k, v in pops.items()})
    print("\n".join(_judge_md(out)))
    return 0


def cmd_judge_merge(args) -> int:
    """Merge judge part files (`judge --batches … --tag _p1` run in separate processes, STATUS 판정 계획) into judge{tag}.json:
    the batch / long / variant dicts are unioned (a key present in two parts is an error), seeds·steps·judged must agree, the
    verdict is recomputed. The *_pop.npz files are merged the same way."""
    d = _p(args.out) if args.out else OUT_EVAL
    parts = [json.loads((d / f"judge{t}.json").read_text(encoding="utf-8")) for t in args.parts]
    if not parts:
        raise SystemExit("judge-merge: --parts 가 비었다")
    base = parts[0]
    out = dict(judged=base["judged"], seeds=base["seeds"], steps=base["steps"], batches={}, long={}, variants={}, parts=list(args.parts))
    for t, pt in zip(args.parts, parts):
        for key in ("judged", "seeds", "steps"):
            if pt.get(key) != base.get(key):
                raise SystemExit(f"judge-merge: {t} 의 {key} 가 다르다 ({pt.get(key)} ≠ {base.get(key)})")
        for grp in ("batches", "long"):
            for name, r in pt.get(grp, {}).items():
                if name in out[grp]:
                    raise SystemExit(f"judge-merge: {grp}.{name} 가 두 조각에 있다")
                out[grp][name] = r
        for v, by in pt.get("variants", {}).items():
            for name, r in by.items():
                if name in out["variants"].setdefault(v, {}):
                    raise SystemExit(f"judge-merge: variants.{v}.{name} 가 두 조각에 있다")
                out["variants"][v][name] = r
    for v, by in out["variants"].items():                          # 같은 판정 시드 = 같은 시작 세계 → 세계별 짝 비교
        for name, r in by.items():
            if v != "ratio" and "paired_coexist_diff" not in r and name in out["batches"]:
                a = np.asarray(out["batches"][name]["population"]["coexist_worlds"], dtype=np.float64)
                bb = np.asarray(r["population"]["coexist_worlds"], dtype=np.float64)
                r["paired_coexist_diff"] = C.boot_mean(bb - a)
    out["verdict"] = judge_verdict(out, _calib_state())
    _write(d, f"judge{args.tag}", out, _judge_md(out))
    arrs = {}
    for t in args.parts:
        pp = d / f"judge{t}_pop.npz"
        if pp.exists():
            with np.load(pp) as z:
                for k in z.files:
                    arrs.setdefault(k, z[k])
    if arrs:
        np.savez_compressed(d / f"judge{args.tag}_pop.npz", **arrs)
    print("\n".join(_judge_md(out)))
    return 0


def _brief_batch(name: str, r: dict) -> None:
    p, j = r["population"], r["j3"]
    print(f"  {name}: 공존 {_fmt(p['coexist_share'])} {_fmt(p['coexist_ci'])} 막힘 {_fmt(p['block_share'])} 끝 수 "
          f"{ {k: round(v, 1) for k, v in p['end_mean'].items()} } 성공률 {_fmt(j['success_rate'])} (구간 {j['segments']}) "
          f"하루 잡이 {_fmt(j['daily_kill'])} 새끼 지수 {_fmt(j['juv_index'])} ({r['ms_per_world_step']:.2f} ms/세계-스텝)", flush=True)


def _calib_state() -> dict:
    p = OUT_CALIB / "C0_STATE.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def judge_verdict(out: dict, calib: dict) -> dict:
    """9-2 J2·J3 (갈래 A·B 각각) + 9-3 가르기 읽기."""
    primary = calib.get("j2_primary", "short")
    v = dict(j2_primary=primary, branches={})
    for b in C.BRANCHES:
        L_ = out["batches"].get(f"L_{b}")
        if L_ is None:
            continue
        short = L_["population"]["coexist_share"]
        lg = out["long"].get(f"L_{b}")
        long_ = lg["population"]["coexist_share"] if lg else None
        ja = bool(short >= C.J2_SHORT_MIN)
        jb = bool(long_ is not None and long_ >= C.J2_LONG_MIN)
        j2 = jb if primary == "long" else bool(ja and jb)
        # 9-2 J2 읽기 (11-12): 같은 판정 시드 L0(상한 끔) 짝 비교가 주 기준 — 어느 종이든 |L0 끝 수 변화| ≥ 20% 면 '규칙이 받친 공존'.
        # L0 판이 없으면 None(미판정). 막힘 몫 ≥ 0.2 는 적기만 (rule_backed_block).
        L0v = out["variants"].get("L0", {}).get(f"L_{b}")
        l0c = None
        rb = None
        if L0v is not None and "end_worlds" in L_["population"] and "end_worlds" in L0v["population"]:
            l0c = C.l0_change(L_["population"]["end_worlds"], L0v["population"]["end_worlds"])
            rb = bool(any(math.isfinite(x) and abs(x) >= C.BLOCK_SHARE_FLAG for x in l0c.values()))
        v["branches"][b] = dict(J2_a=ja, J2_b=jb if long_ is not None else None, J2=j2 if long_ is not None else None,
                                coexist_short=short, coexist_long=long_, rule_backed=rb, l0_change=l0c,
                                rule_backed_block=L_["population"].get("rule_backed_block"),
                                block_share=L_["population"]["block_share"], J3=L_["j3"]["J3"], J3_ok=L_["j3"]["ok"],
                                J3_insufficient=L_["j3"]["insufficient"], J4=L_.get("anomaly", {}).get("J4", []))
        reading = []
        R = out["batches"].get("RULE")
        P_ = out["batches"].get(f"P_{b}")
        W_ = out["batches"].get(f"W_{b}")
        if R is not None and P_ is not None and W_ is not None:
            cl, cp, cw = short, P_["population"]["coexist_share"], W_["population"]["coexist_share"]
            if cp >= C.J2_SHORT_MIN > cl:
                reading.append("P 공존 높고 L 낮음 → 학습한 늑대가 너무 잘 잡는다(늑대 쪽) — 두뇌 탓하지 않고 보고 (15-2 질문 2)")
            if cw >= C.J2_SHORT_MIN > cl:
                reading.append("W 공존 높고 L 낮음 → 학습한 먹이가 늑대를 굶긴다(먹이 쪽) — 늑대 굶음 몫·성공률 함께")
            if R["population"]["coexist_share"] < C.J2_SHORT_MIN:
                reading.append("RULE 도 공존 낮음 → 세계 탓일 수도 규칙 늑대 탓일 수도 (2 × 2 로 본다)")
        if rb:
            reading.append(f"L0(상한 끔) 끝 수 변화 {({k: round(x, 3) for k, x in l0c.items()})} — 20% 넘는 종이 있어 '규칙이 받친 공존'")
        if L0v is not None and L0v["population"]["coexist_share"] < short - 0.15:          # [어림] '크게 떨어짐' = 0.15 넘게 (보고)
            reading.append("L0(상한 끔)에서 공존 몫이 크게 떨어짐 (보고)")
        LS = out["variants"].get("LS", {}).get(f"L_{b}")
        if LS is not None and abs(LS["population"]["coexist_share"] - short) > 0.15:
            reading.append("L 과 LS(확률 행동)가 크게 다름 → 결정적 행동끼리 교착·동기화 — 리플레이로 장면을 본다")
        v["branches"][b]["reading_9_3"] = reading
    for x in ("X_AB", "X_BA"):
        if x in out["batches"]:
            v.setdefault("J5", {})[x] = out["batches"][x]["population"]["coexist_share"]
    return v


def _judge_md(out: dict) -> list[str]:
    L = [f"# R9 판정 세계 J2·J3 (설계 8-2·9-2) {'— 판정' if out['judged'] else '— 시운전 (판정 시드 아님)'}", "",
         f"- 시드 {out['seeds'][0]}~{out['seeds'][1]}, {out['steps']} 스텝, 판정 세계 J, 가장 높은 칸. 2 시간 판 = 앞 50 세계 × 54,000 스텝.",
         "- 공존 세계 = 끝에 세 종 모두 '번식할 수 있는 쌍'(늑대: 근친 아닌 성숙 2 마리, 사슴·멧돼지: 근친 아닌 성숙 암수). 막힘 몫 = 콘텐츠 상한 막힘 ÷ (그것 + 맺은 짝).", "",
         "| 배치 | 공존 | 95% | 막힘 몫 | 끝 사슴·늑대·멧돼지 | 첫 멸종 중앙값 (스텝) | 준멸종 | 성공률 (구간) | 하루 잡이 | 새끼 지수 (잡힌 멧돼지) | 근접 동점 | ms/세계-스텝 |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def row(name, r):
        p, j = r["population"], r["j3"]
        em = p["end_mean"]
        fx = p["first_extinction_median"]
        return (f"| {name} | {_fmt(p['coexist_share'])} | {_fmt(p['coexist_ci'])} | {_fmt(p['block_share'])} | "
                f"{_fmt(em['deer'], 1)}·{_fmt(em['wolf'], 1)}·{_fmt(em['boar'], 1)} | {_fmt(fx['deer'], 0)}·{_fmt(fx['wolf'], 0)}·{_fmt(fx['boar'], 0)} | "
                f"{_fmt(p['quasi_extinct_share'])} | {_fmt(j['success_rate'])} ({j['segments']}) | {_fmt(j['daily_kill'])} | "
                f"{_fmt(j['juv_index'])} ({j['boar_kills']}) | {p['near_ties']} | {r['ms_per_world_step']:.2f} |")
    for n, r in out["batches"].items():
        L.append(row(n, r))
    for n, r in out["long"].items():
        L.append(row(n + " 2 시간", r))
    for v, d in out["variants"].items():
        for n, r in d.items():
            if v == "ratio":
                for part, rr in r.items():
                    L.append(row(f"{n} 먹이 비 {part}", rr))
            else:
                L.append(row(f"{n} {v}", r))
    ver = out.get("verdict", {})
    L += ["", f"판정 (J2 주 기준: {'2 시간 판' if ver.get('j2_primary') == 'long' else '30 분 + 2 시간'})", ""]
    for b, x in ver.get("branches", {}).items():
        L.append(f"- 갈래 {b}: J2 (가) 30 분 ≥ 0.6 {_fmt(x['J2_a'])}, (나) 2 시간 ≥ 0.4 {_fmt(x['J2_b'])} → J2 {_fmt(x['J2'])}"
                 f"{' — 규칙이 받친 공존(L0 끝 수 변화 ≥ 20%: ' + str(x.get('l0_change')) + ')' if x['rule_backed'] else ''}"
                 f"{' — L0 짝 판 없음(상한 기대 미판정)' if x['rule_backed'] is None else ''}; J3 {_fmt(x['J3'])} {x['J3_ok']}"
                 f"{' 표본 모자람 ' + str(list(x['J3_insufficient'])) if x['J3_insufficient'] else ''}; J4 꼼수 {x['J4'] or '없음'}")
        for s in x.get("reading_9_3", []):
            L.append(f"  - 9-3: {s}")
    if "J5" in ver:
        L.append(f"- J5 갈래 교차 공존: {ver['J5']}")
    L.append("- 은신처는 100% 안전한 피난처다(3-5) — '피난처가 받친 공존'일 수 있다.")
    return L


# --------------------------------------------------------------------------- #
# scenes (8-3) / anomaly (8-4)
# --------------------------------------------------------------------------- #

def _scenario(args):
    ct, cj = load_cfgs(args)
    seeds = _seeds(args.seeds)
    C.assert_not_judge_seeds(seeds, args.cmd)
    C.warn_calib_seeds(seeds, args.cmd)
    cfg = cj if args.form == "judge" else B.override(ct, EVAL_FACING)
    brains = C.load_brains(C.parse_brain_args(args.brain), cfg)
    specs = {DEER: args.deer, WOLF: args.wolf, BOAR: args.boar}
    stoch = args.form == "judge" and not bool(cfg["judge"]["greedy"])
    rec = C.run(cfg, seeds, args.steps, spec_fn(cfg, specs, brains, stochastic=stoch), scenes=True, chunk=args.chunk, progress=args.cmd)
    return rec, dict(form=args.form, seeds=args.seeds, steps=args.steps, specs={SPECIES[k]: v for k, v in specs.items()})


def cmd_scenes(args) -> int:
    rec, meta = _scenario(args)
    out = dict(meta, scenes=C.scene_metrics(rec))
    md = ["# R9 상호작용 장면 지표 (설계 8-3, 보고만)", "", f"- {meta}", ""] + [f"- {k}: {json.dumps(C.to_jsonable(v), ensure_ascii=False)}"
                                                                         for k, v in out["scenes"].items()]
    _write(_p(args.out) if args.out else OUT_EVAL / "dev", f"scenes_{args.form}{args.tag}", out, md)
    print("\n".join(md))
    return 0


def cmd_anomaly(args) -> int:
    rec, meta = _scenario(args)
    out = dict(meta, anomaly=C.anomaly_metrics(rec))
    a = out["anomaly"]
    md = ["# R9 이상 행동 점검 (설계 8-4)", "", f"- {meta}", "",
          "| 이상 | 값 | 문턱 | 넘음 |", "|---|---|---|---|"]
    th = C.ANOMALY_THRESHOLDS
    for k, val in (("corner", a["corner"]), ("wall_drive", a["wall_ratio"]), ("edge_stand", a["edge_stand"]), ("edge_kill", a["edge_ratio"]),
                   ("shield", a["shield"]), ("always_hide", a["always_hide"]), ("always_run", a["always_run"]), ("always_fight", a["always_fight"]),
                   ("surplus", a["surplus"]), ("arena", a["arena"])):
        md.append(f"| {k} | {_fmt(val) if not isinstance(val, dict) else json.dumps(C.to_jsonable(val))} | {th.get(k, '-')} | {_fmt(a['flags'][k])} |")
    md.append(f"| no_hunt | 구간/늑대-일 {_fmt(a['segments_per_wolf_day'])}, 늑대 굶음 몫 {_fmt(a['wolf_starve_share'])} | < 1 · > 0.5 | {_fmt(a['flags']['no_hunt'])} |")
    md += ["", f"- J4 (판정 문장에 '꼼수가 섞임'): {a['J4'] or '없음'}", f"- 반격 출처: {a['counter_source']}"]
    _write(_p(args.out) if args.out else OUT_EVAL / "dev", f"anomaly_{args.form}{args.tag}", out, md)
    print("\n".join(md))
    return 0


# --------------------------------------------------------------------------- #
# check (8-5, 9-4)
# --------------------------------------------------------------------------- #

CHECK_COMP = {DEER: (("caught", +1), ("eaten", -1), ("births", -1)), BOAR: (("caught", +1), ("eaten", -1), ("births", -1)),
              WOLF: (("daily_kill", -1), ("eaten", -1), ("births", -1), ("hp_loss", +1))}   # +1 = 높을수록 나쁨


def worse_ratio(new_n, new_d, old_n, old_d, sign: int) -> tuple[float, list[float]]:
    """9-4 (가): 새/옛 비를 나쁜 쪽 기준으로 (높을수록 나쁨이면 새/옛, 낮을수록 나쁨이면 옛/새), 같은 점검 세계 짝 되뽑기 구간."""
    def r(i):
        a, b = C.ratio(new_n[i], new_d[i]), C.ratio(old_n[i], old_d[i])
        if sign > 0:
            return a / b if b > 0 else float("nan")
        return b / a if a > 0 else float("nan")
    idx = np.arange(len(new_n))
    return r(idx), C.boot_ci(r, len(new_n))


def _check_name(rnd: int, branches, tag: str) -> str:
    return f"round{int(rnd):02d}{'_' + branches[0] if len(branches) == 1 else ''}{tag}"


def _load_prev(out_dir: Path, rnd: int, b: str, tag: str, given: str | None) -> dict | None:
    """Previous check of branch b: the given file, else round<rnd>_<b>.json, else the combined round<rnd>.json."""
    if given:
        return json.loads(_p(given).read_text(encoding="utf-8"))
    for nm in (_check_name(rnd, [b], tag), _check_name(rnd, ["A", "B"], tag)):
        f = out_dir / f"{nm}.json"
        if f.exists():
            d = json.loads(f.read_text(encoding="utf-8"))
            if b in d.get("branches", {}):
                return d
    return None


def cmd_check(args) -> int:
    """8-5 바퀴 끝 점검 (갈래 하나씩도 — league_r9 --check-cmd 가 갈래마다 부른다). 두뇌 = --brain 또는 --league-state 의 풀 마지막 판.
    직전 점검(라운드 − 2)·두 점검 전(− 4)은 --prev/--prev2 또는 점검 폴더에서 찾는다. 두 갈래가 다 모이면 멈춤 규칙(9-4)을 함께 쓴다."""
    ct, cj = load_cfgs(args)
    s_rule, s_cross, s_prev = _seeds(args.seeds), _seeds(args.cross_seeds), _seeds(args.preview_seeds)
    C.assert_not_judge_seeds(s_rule + s_cross + s_prev, "check")
    check_c0_state(ct, cj, "check")
    cfg = B.override(ct, EVAL_FACING)
    paths = C.parse_brain_args(args.brain)
    if args.league_state:
        lst = json.loads(_p(args.league_state).read_text(encoding="utf-8"))
        for b in (args.branches or C.BRANCHES):
            for sname in SPECIES:
                pool = lst.get("pools", {}).get(b, {}).get(sname) or []
                if f"{b}:{sname}" not in paths and pool:
                    paths[f"{b}:{sname}"] = pool[-1]["npz"]
    brains = C.load_brains(paths, cfg)
    branches = [b for b in (args.branches or C.BRANCHES) if all(f"{b}:{s}" in brains for s in SPECIES)]
    if not branches:
        raise SystemExit("check: 갈래 하나의 세 종 두뇌가 필요하다 (--brain 또는 --league-state)")
    out_dir = _p(args.out) if args.out else OUT_CHECK
    out = dict(round=args.round, seeds=dict(rule=args.seeds, cross=args.cross_seeds, preview=args.preview_seeds),
               steps=dict(rule=args.steps, cross=args.steps_cross, preview=args.steps_preview),
               brain_paths={k: v for k, v in paths.items() if k.split(":")[0] in branches}, branches={})
    prevs = {}
    for b in branches:
        prev = _load_prev(out_dir, args.round - 2, b, args.tag, args.prev)
        prev2 = _load_prev(out_dir, args.round - 4, b, args.tag, args.prev2)
        prevs[b] = prev
        e = dict(rule_perf={}, cross={}, preview=None)
        for sp in range(3):                               # 규칙 상대 성적 (멈춤 (가))
            specs = {**rule_specs(), sp: b}
            rec = C.run(cfg, s_rule, args.steps, spec_fn(cfg, specs, brains), scenes=False, chunk=args.chunk, progress=f"{b} {SPECIES[sp]} vs rule")
            comp = {}
            for name, sign in CHECK_COMP[sp]:
                n, d = _rate_world(rec, sp, name)
                comp[name] = dict(value=C.ratio(n, d), num=n.tolist(), den=d.tolist(), sign=sign)
            e["rule_perf"][SPECIES[sp]] = comp
        # 판정 세계 미리 보기 (멈춤 (나)·(다))
        rp = run_batch(cj, s_prev, args.steps_preview, {s: b for s in range(3)}, brains, args.chunk, f"{b} preview", scenes=False)
        rp.pop("_pop"), rp.pop("_pop_t")
        e["preview"] = dict(coexist=rp["population"]["coexist_share"], coexist_worlds=rp["population"]["coexist_worlds"], j3=rp["j3"],
                            block_share=rp["population"]["block_share"])
        # 판 교차 표 (돌기 신호): 먹이 판(사슴·멧돼지 같은 점검의 판) × 늑대 판 [해석: 한 판에서 사슴·멧돼지를 함께 잰다]
        vers = [("now", paths)]
        for tag, pj in (("prev", prev), ("prev2", prev2)):
            if pj is not None and all(f"{b}:{s}" in pj.get("brain_paths", {}) for s in SPECIES):
                vers.append((tag, pj["brain_paths"]))
        vbr = {tag: C.load_brains({f"{b}:{s}": pp[f"{b}:{s}"] for s in SPECIES}, cfg) for tag, pp in vers}
        tags = [t for t, _ in vers] + ["rule"]
        for pv in tags:
            for wv in tags:
                bb = {f"{tag}:{s}": vbr[tag][f"{b}:{s}"] for tag in {pv, wv} - {"rule"} for s in SPECIES}
                specs = {DEER: pv if pv != "rule" else "RULE_DEER", BOAR: pv if pv != "rule" else "RULE_BOAR",
                         WOLF: wv if wv != "rule" else "RULE_WOLF"}
                rec = C.run(cfg, s_cross, args.steps_cross, spec_fn(cfg, specs, bb), scenes=False, chunk=args.chunk)
                cell = {}
                for sp, name in ((DEER, "caught"), (BOAR, "caught"), (WOLF, "daily_kill")):
                    n, d = _rate_world(rec, sp, name)
                    cell[f"{SPECIES[sp]}_{name}"] = dict(value=C.ratio(n, d), num=n.tolist(), den=d.tolist())
                e["cross"][f"{pv}|{wv}"] = cell
        e["signals"] = check_signals(e, prev, b)
        out["branches"][b] = e
    if set(branches) >= {"A", "B"}:                       # 갈래 교차 (보고): A 먹이 × B 늑대 대 A × A 잡힘 비
        cross_rep = {}
        for pb, wb in (("A", "B"), ("B", "A")):
            rec_x = C.run(cfg, s_cross, args.steps_cross, spec_fn(cfg, {DEER: pb, BOAR: pb, WOLF: wb}, brains), scenes=False, chunk=args.chunk)
            n, d = _rate_world(rec_x, DEER, "caught")
            same = out["branches"][pb]["cross"]["now|now"]["deer_caught"]
            cross_rep[f"{pb}prey_{wb}wolf"] = dict(caught=C.ratio(n, d), same_branch=same["value"],
                                                   ratio=C.ratio(n, d) / same["value"] if same["value"] else float("nan"))
        out["branch_cross"] = cross_rep
    name = _check_name(args.round, branches, args.tag)
    out["stop"] = stop_rule(out, prevs)
    md = _check_md(out)
    _write(out_dir, name, out, md)
    if len(branches) == 1:                                # 다른 갈래 파일이 있으면 합쳐 멈춤 규칙을 다시 쓴다
        other = [b for b in C.BRANCHES if b != branches[0]][0]
        f = out_dir / f"{_check_name(args.round, [other], args.tag)}.json"
        if f.exists():
            od = json.loads(f.read_text(encoding="utf-8"))
            comb = dict(out, branches={**od["branches"], **out["branches"]}, brain_paths={**od["brain_paths"], **out["brain_paths"]})
            comb["stop"] = stop_rule(comb, {b: _load_prev(out_dir, args.round - 2, b, args.tag, None) for b in C.BRANCHES})
            _write(out_dir, _check_name(args.round, ["A", "B"], args.tag), comb, _check_md(comb))
    print("\n".join(md))
    return 0


def check_signals(e: dict, prev: dict | None, b: str) -> dict:
    """9-4 (가) 잊음·(나) 안정·(다) 현실 범위, 돌기 신호 (갈래 하나)."""
    sig = dict(forgetting={}, forgetting_any=None, stability=None, realism=bool(e["preview"]["j3"]["J3"]), rotation={})
    pe = prev["branches"].get(b) if prev else None
    if pe is not None:
        anyf = False
        for sp, comps in e["rule_perf"].items():
            for name, c in comps.items():
                o = pe["rule_perf"][sp][name]
                r, ci = worse_ratio(np.asarray(c["num"]), np.asarray(c["den"]), np.asarray(o["num"]), np.asarray(o["den"]), c["sign"])
                f = bool(math.isfinite(ci[0]) and ci[0] > 1.1)
                sig["forgetting"][f"{sp}.{name}"] = dict(ratio=r, ci=ci, forgetting=f)
                anyf |= f
        sig["forgetting_any"] = anyf
        a = np.asarray(e["preview"]["coexist_worlds"], dtype=np.float64)
        o = np.asarray(pe["preview"]["coexist_worlds"], dtype=np.float64)
        if len(a) == len(o):
            d, ci = C.boot_mean(a - o)
            sig["stability"] = dict(diff=d, ci=ci, stable=bool(ci[0] >= -0.15 and ci[1] <= 0.15))
    cr = e["cross"]
    if "now|prev2" in cr and "prev2|prev2" in cr:
        for sp_name, key, sign in (("deer", "deer_caught", +1), ("boar", "boar_caught", +1)):
            a, o = cr["now|prev2"][key], cr["prev2|prev2"][key]
            r, ci = worse_ratio(np.asarray(a["num"]), np.asarray(a["den"]), np.asarray(o["num"]), np.asarray(o["den"]), sign)
            sig["rotation"][sp_name] = dict(ratio=r, ci=ci, signal=bool(math.isfinite(ci[0]) and ci[0] > 1.2))
    if "prev2|now" in cr and "prev2|prev2" in cr:
        a, o = cr["prev2|now"]["wolf_daily_kill"], cr["prev2|prev2"]["wolf_daily_kill"]
        def rr(i, a=a, o=o):
            x, y = C.ratio(np.asarray(a["num"])[i], np.asarray(a["den"])[i]), C.ratio(np.asarray(o["num"])[i], np.asarray(o["den"])[i])
            return x / y if y > 0 else float("nan")
        idx = np.arange(len(a["num"]))
        ci = C.boot_ci(rr, len(a["num"]))
        sig["rotation"]["wolf"] = dict(ratio=rr(idx), ci=ci, signal=bool(math.isfinite(ci[1]) and ci[1] < 1.0 / 1.2))
    sig["rotation_any"] = any(v["signal"] for v in sig["rotation"].values()) if sig["rotation"] else None
    return sig


def stop_rule(out: dict, prevs: dict) -> dict:
    """9-4 멈춤 (10 바퀴부터, 두 갈래 모두 (가)·(나)·(다)) + 처방 (두 점검 연속 신호 → 섞는 비율)."""
    rnd = int(out["round"])
    br = out["branches"]
    ok = {}
    for b, e in br.items():
        s = e["signals"]
        ok[b] = bool(s["forgetting_any"] is False and s["stability"] is not None and s["stability"]["stable"] and s["realism"])
    stop = bool(rnd >= 10 and len(ok) == 2 and all(ok.values()))
    presc = {}
    for b, e in br.items():
        s = e["signals"]
        prev = (prevs or {}).get(b)
        ps = prev["branches"][b]["signals"] if prev and b in prev.get("branches", {}) else {}
        rot2 = bool(s.get("rotation_any") and ps.get("rotation_any"))
        fg2 = bool(s.get("forgetting_any") and ps.get("forgetting_any"))
        mix = None
        if rot2 and fg2:
            mix = dict(current=0.3, past=0.4, rule=0.3)
        elif rot2:
            mix = dict(current=0.4, past=0.4, rule=0.2)
        elif fg2:
            mix = dict(current=0.4, past=0.3, rule=0.3)
        presc[b] = dict(rotation_twice=rot2, forgetting_twice=fg2, mix=mix)
    return dict(round=rnd, branch_ok=ok, stop=stop, at_18=bool(rnd >= 18), prescription=presc)


def _check_md(out: dict) -> list[str]:
    L = [f"# R9 바퀴 끝 점검 — {out['round']} 바퀴 (설계 8-5·9-4)", "", f"- 시드 {out['seeds']} (점검 시드, 판정 시드 아님), 스텝 {out['steps']}.", ""]
    for b, e in out["branches"].items():
        s = e["signals"]
        L.append(f"## 갈래 {b}")
        for sp, comps in e["rule_perf"].items():
            L.append(f"- 규칙 상대 {sp}: " + ", ".join(f"{k} {_fmt(v['value'] * (1000.0 if k in ('caught', 'eaten', 'births') else 1.0))}"
                                                       f"{' /1k 스텝' if k in ('caught', 'eaten', 'births') else ' /늑대-일'}" for k, v in comps.items()))
        L.append(f"- 미리 보기 공존 {_fmt(e['preview']['coexist'])}, 막힘 {_fmt(e['preview']['block_share'])}, J3 {_fmt(e['preview']['j3']['J3'])}")
        L.append(f"- (가) 잊음: {_fmt(s['forgetting_any'])} {', '.join(k for k, v in s['forgetting'].items() if v['forgetting']) or ''}")
        L.append(f"- (나) 안정: {s['stability']}")
        L.append(f"- (다) 현실 범위: {_fmt(s['realism'])}; 돌기 신호: {_fmt(s.get('rotation_any'))} {s['rotation']}")
    st = out["stop"]
    L += ["", f"- 멈춤: {'**멈춘다**' if st['stop'] else '계속'} (갈래별 {st['branch_ok']}){' — 18 바퀴: 이 두뇌로 판정하고 \"아직 흔들린다\"를 적는다' if st['at_18'] and not st['stop'] else ''}",
          f"- 처방: {st['prescription']}"]
    if "branch_cross" in out:
        L.append(f"- 갈래 교차 (보고): {out['branch_cross']}")
    return L


# --------------------------------------------------------------------------- #
# summary (9-2)
# --------------------------------------------------------------------------- #

def cmd_summary(args) -> int:
    d = _p(args.out) if args.out else OUT_EVAL
    jp = d / f"judge{args.tag}.json"
    mp = d / f"mixed{args.tag}.json"
    judge = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else None
    mixed = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else None
    calib = _calib_state()
    S = dict(judge=bool(judge), mixed=bool(mixed), judged=bool((judge or {}).get("judged")) and bool((mixed or {}).get("judged")))
    j1 = (mixed or {}).get("J1", {}).get("J1")
    ver = (judge or {}).get("verdict", {})
    j2 = {b: x.get("J2") for b, x in ver.get("branches", {}).items()}
    j3 = {b: x.get("J3") for b, x in ver.get("branches", {}).items()}
    j4 = {b: x.get("J4") for b, x in ver.get("branches", {}).items()}
    rbs = [x.get("rule_backed") for x in ver.get("branches", {}).values()]
    rb = True if any(v is True for v in rbs) else (None if (not rbs or any(v is None for v in rbs)) else False)
    J2, J3 = _tri(j2), _tri(j3)
    sent = sentence(j1, J2, J3, rb, judge)
    S.update(J1=j1, J2=j2, J3=j3, J4=j4, rule_backed=rb, sentence=sent, calib=dict(values=calib.get("values"), f_enabled=calib.get("f_enabled"),
                                                                                    j2_primary=calib.get("j2_primary")))
    md = ["# R9 판정 요약 (설계 9-2)", "", f"- 판정 시드로 돈 결과인가: {_fmt(S['judged'])} (시운전이면 판정 문장이 아니다)",
          f"- J1 {_fmt(j1)}, J2 {j2}, J3 {j3}, J4 {j4}, 규칙이 받친 공존 {_fmt(rb)}", "", f"> {sent}"]
    if judge:
        md += [""] + _judge_md(judge)
    if mixed:
        md += [""] + _mixed_md(mixed)
    _write(d, f"summary{args.tag}", S, md)
    print("\n".join(md))
    return 0


def _tri(by_branch: dict) -> bool | None:
    """Both branches A·B: True if both pass, False if any failed, None if not judged (missing branch or a None value — e.g. J2
    without the 2-hour runs). Fix 단계 검토 low: None used to become False ('함께 살지 못했다')."""
    if not by_branch or len(by_branch) < 2 or any(v is None for v in by_branch.values()):
        return None if not any(v is False for v in (by_branch or {}).values()) else False
    return all(v is True for v in by_branch.values())


def sentence(j1, J2: bool | None, J3: bool | None, rule_backed: bool | None, judge) -> str:
    """9-2 결과 문장. J1·J2·J3 = True / False / None (안 잼)."""
    if j1 is False:
        return "J1 실패 — 실패한 종과 그 까닭(학습 곡선·이상 신호)을 적는다."
    missing = [n for n, x in (("J1", j1), ("J2", J2), ("J3", J3)) if x is None]
    if j1 and J2 is False:
        return "각 종은 규칙보다 잘 살지만 함께 살지 못했다. 9-3 으로 원인을 가른다."
    if missing:
        why = {"J1": "섞인 무리(mixed) 결과 없음", "J2": "2 시간 판이 없거나 갈래가 빠짐 (judge --long)", "J3": "판정 배치 L_A·L_B 없음"}
        return "판정에 필요한 결과가 다 모이지 않았다 — " + ", ".join(f"{n} 미판정({why[n]})" for n in missing) + "."
    if j1 and J2 and J3 is False:
        # [해석] 9-2 에 문장이 없다: J1·J2 통과, J3 만 실패
        return ("세 종이 각자 배운 두뇌로 한 무대에서 30 분·2 시간 함께 살았지만, 사냥 모습이 보정한 현실 범위 밖이다 "
                "(J3 실패 — 지표마다 '규칙보다 현실 쪽으로 움직였나'를 적는다).")
    if j1 and J2 and J3:
        s = "세 종이 각자 배운 두뇌로 한 무대에서 30 분·2 시간 함께 살았고, 사냥 모습이 보정한 현실 범위 안에 남았다."
        if rule_backed:
            br = (judge or {}).get("verdict", {}).get("branches", {})
            s += " 다만 공존은 언리얼 출생 상한이 받쳤다(상한 끈 판 끝 수 변화: " + ", ".join(
                f"{b} {({k: round(x, 3) for k, x in (v.get('l0_change') or {}).items()})}" for b, v in br.items()) + ")."
        elif rule_backed is None:
            s += " (상한 끈 L0 짝 판이 없어 상한이 받쳤는지는 판정하지 않았다.)"
        return s
    return "판정에 필요한 결과가 다 모이지 않았다 (J1·J2·J3 중 빈 것이 있다)."


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, seeds, steps):
        p.add_argument("--config", default="configs/v3_r9.yaml")
        p.add_argument("--judge-config", default="configs/v3_r9_judge.yaml")
        p.add_argument("--set", nargs="*", default=[], help="블록.키=값 덮어쓰기 (판정 시드에서는 받지 않음)")
        p.add_argument("--brain", nargs="*", default=[], help="갈래:종=경로.npz (예 A:deer=ckpt/r9/A/deer_r10.npz)")
        p.add_argument("--chunk", type=int, default=25, help="한 번에 돌리는 세계 수 (결과와 무관, 메모리용)")
        p.add_argument("--out", default=None)
        p.add_argument("--tag", default="")
        p.add_argument("--hunt-def", choices=C.HUNT_DEFS, default="strict",
                       help="사냥 시도 정의: strict = 8-2 (11-12 정함, 기본 — 사냥 구간을 같은 늑대끼리 묶음) · pair = 처음 문장(늑대-표적 쌍마다) · "
                            "episode = 거르기 없이 묶음 (pair·episode 는 보고만)")
        p.add_argument("--block-def", choices=C.BLOCK_DEFS, default="scan",
                       help="막힘 몫 셈 (보고만 — 주 기준은 같은 시드 L0 짝 비교, 11-12): scan = 5 초 짝 찾기마다 · once = 대기 한 번·상한 연속에 한 번")
        if seeds == "required":
            p.add_argument("--seeds", nargs=2, type=int, default=None, help="꼭 적는다 (판정 시드 기본값 없음)")
        elif seeds is not None:
            p.add_argument("--seeds", nargs=2, type=int, default=list(seeds))
        if steps is not None:
            p.add_argument("--steps", type=int, default=steps)
    p = sub.add_parser("calibrate")
    common(p, None, None)
    p.add_argument("--phase", choices=("pick", "confirm"), default="pick")
    p.add_argument("--gates", nargs="*", default=None, help=f"차례 {list(C0_ORDER)} (+ C0-10)")
    p.add_argument("--cands", nargs="*", type=float, default=None, help="관문 하나만 돌릴 때 후보 덮어쓰기 (스모크)")
    p.add_argument("--seeds-train", nargs=2, type=int, default=None)
    p.add_argument("--seeds-judge", nargs=2, type=int, default=None)
    p.add_argument("--steps-train", type=int, default=3000, help="[어림] 학습 세계 꼴 관문 스텝")
    p.add_argument("--steps-judge", type=int, default=13500)
    p.add_argument("--steps-c011", type=int, default=9000)
    p.add_argument("--state", default=None)
    p.add_argument("--no-state", action="store_true", help="상태 파일을 쓰지 않음 (스모크·시험)")
    p.add_argument("--gamma", type=float, default=0.997)
    p.add_argument("--c010-commands", action="store_true")
    p.add_argument("--c010-choose", nargs="*", default=None)
    p.add_argument("--decisions-json", default=None, help="C0-10 명령의 속도 (bundle_decisions.json 의 speed_dps.round0, C0-9 등록)")
    p = sub.add_parser("leak")
    common(p, C.SEED_RANGES["smoke"], 2000)              # S′ 검토 low: 기본값이 고르기 시드 44000~44049 를 소리 없이 쓰던 것 → 스모크
    p = sub.add_parser("mixed")
    common(p, "required", None)
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--branches", nargs="*", default=None)
    p.add_argument("--species", nargs="*", default=None)
    p.add_argument("--others", choices=("final", "rule"), default="final")
    p.add_argument("--lock", default=None)
    p = sub.add_parser("judge")
    common(p, "required", None)
    p.add_argument("--steps", type=int, default=None)
    p.add_argument("--steps-long", type=int, default=None)
    p.add_argument("--long", action="store_true")
    p.add_argument("--batches", nargs="*", default=None, help=f"{list(BATCHES)}")
    p.add_argument("--variants", nargs="*", default=[], help=f"{list(VARIANT_NAMES)}")
    p.add_argument("--long-only", action="store_true", help="30 분 배치 없이 2 시간 판(--long)·덧붙임 판만 (조각 나누기)")
    p.add_argument("--for-branches", nargs="*", default=None, help="2 시간 판·덧붙임 판을 돌릴 갈래 (기본 A B)")
    p.add_argument("--lock", default=None)
    for nm in ("scenes", "anomaly"):
        p = sub.add_parser(nm)
        common(p, C.SEED_RANGES["smoke"], 3000)          # S′ 검토 low: 처음 기본값 = 고르기 시드 44100~44139 → 스모크
        p.add_argument("--form", choices=("train", "judge"), default="judge")
        p.add_argument("--deer", default="RULE_DEER")
        p.add_argument("--wolf", default="RULE_WOLF")
        p.add_argument("--boar", default="RULE_BOAR")
    p = sub.add_parser("check")
    common(p, C.SEED_RANGES["check"], 3000)
    p.add_argument("--round", type=int, required=True)
    p.add_argument("--cross-seeds", nargs=2, type=int, default=[44200, 44239])
    p.add_argument("--steps-cross", type=int, default=1500)
    # 8-5 판정 세계 미리 보기 = 50 세계 (C0-9 등록 2026-11-11, STATUS 3절: 100 세계면 점검 하나가 1 시간을 넘는다)
    p.add_argument("--preview-seeds", nargs=2, type=int, default=[44200, 44249])
    p.add_argument("--steps-preview", type=int, default=13500)
    p.add_argument("--prev", default=None)
    p.add_argument("--prev2", default=None)
    p.add_argument("--branches", nargs="*", default=None)
    p.add_argument("--league-state", default=None, help="ckpt/r9/league_state.json — 풀 마지막 판을 두뇌로")
    p = sub.add_parser("summary")
    p.add_argument("--out", default=None)
    p.add_argument("--tag", default="")
    p = sub.add_parser("judge-merge", help="판정 조각(judge --tag _p1 …)을 judge{tag}.json 하나로")
    p.add_argument("--parts", nargs="+", required=True, help="조각 tag 들 (예 _p1 _p2 _p3 _p4)")
    p.add_argument("--out", default=None)
    p.add_argument("--tag", default="")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if hasattr(args, "hunt_def"):
        C.DEFS.update(hunt=args.hunt_def, block=args.block_def)
    return dict(calibrate=cmd_calibrate, leak=cmd_leak, mixed=cmd_mixed, judge=cmd_judge, scenes=cmd_scenes, anomaly=cmd_anomaly,
                check=cmd_check, summary=cmd_summary, **{"judge-merge": cmd_judge_merge})[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

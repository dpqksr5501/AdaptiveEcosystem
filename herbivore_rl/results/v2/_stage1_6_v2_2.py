"""1-6 v2.2 판정 묶음(학습 시드 5개, 전체 묶음) 집계 — 진단 JSON → results/v2/s1_6/stage1_6_v2_2.json.

사전 등록은 `results/v2/s1_6/PREREG.md` 다(학습 전, 2026-10-03). 이 파일은 그 문서를 옮긴 것이고, 둘이 어긋나면
PREREG 가 기준이다. 1-3 의 `results/v2/_stage1_v2_1.py` 를 일반화했다: 학습 시드 수·1차 지표·대조군을 표(상수)로 두고,
경계 지표(B3 = b3_truth), 10-03 사람 결정의 쓸모 규칙(결과 지표만, G_γ 는 보고), 두 C2-seg(E1-b·E2), 2차 지표 7개의
Holm 보정, B4 v1 기준선, B6·B7 롤아웃을 더했다.

하위 명령 (작업 디렉터리 herbivore_rl/):
    python results/v2/_stage1_6_v2_2.py b3defs   # 학습 전: B3 정의 고르기용 합성 정책 시험 → s1_6/b3_defs.json
    python results/v2/_stage1_6_v2_2.py b4base   # 학습 전: B4 v1 기준선(평가 시드 20 × 5000) → s1_6/b4_v1_baseline.json
    python results/v2/_stage1_6_v2_2.py b67 --seed <s>   # 학습 뒤: B6·B7 롤아웃(C0·C1′) → s1_6/b67_v2_2_s<s>.json
    python results/v2/_stage1_6_v2_2.py judge    # 학습·진단 뒤: 묶음 집계와 판정 → s1_6/stage1_6_v2_2.json
진단 명령 전문과 순서는 PREREG 10절이다. `--res`·`--cache`·`--ckpt`·`--out`·`--smoke` 는 도구 시험(scratchpad)용이다:
`--smoke` 는 평가 시드·스텝을 결과 meta 에서 읽고 E1-b·E2 재현 검사를 건너뛴다(판정에 쓰지 않는다).

실행 이름 접두사·학습 시드·출력 폴더 (10-03, 1-6 판정 재실행 `results/v2/s1_6b/PREREG.md` 5절): `--prefix P`(기본 v2_2)는
학습 시드 s 의 실행 이름을 `P_s<s>` 로 정한다 — 모델 `ckpt/v2/P_s<s>.zip`, 진단 `diag_P_s<s>`·`diag_P_s<s>_stoch`,
묶음 `diag_P/modecmp.json`, 보정 캐시 `runs/v2_diag/P_s<s>`. `--seeds`(judge, 기본 0 1 2 3 4)·`--seed`(b67)가 학습
시드다. `--sdir D`(기본 s1_6)는 B6·B7 결과 `<res>/D/b67_P_s<s>.json` 과 판정표 `<res>/D/stage1_6_P.json` 의 폴더다.
B3 정의 시험·B4 v1 기준선은 학습 전에 고정한 것이라 늘 `<res>/s1_6/` 의 것을 쓴다. 기본값이면 예전과 같은 파일을
읽고 같은 판정표를 낸다(10-03 확인: 기본 인자로 다시 낸 judge 출력이 `s1_6/stage1_6_v2_2.json` 과 generated·script
칸만 다르다). 예 (1-6 판정 재실행, 팔 a):
    python results/v2/_stage1_6_v2_2.py b67 --prefix v2_2a --sdir s1_6b --seed 5 --workers 3
    python results/v2/_stage1_6_v2_2.py judge --prefix v2_2a --sdir s1_6b --seeds 5 6 7 8 9

운영 정의 요약 (자세한 것은 PREREG 3~6절):
- 조건: 결정 모드 결과는 모두 config_digest efc8f775f1e1(`configs/v2_2.yaml` = Gate E2 V0_d0_95), 평가 시드
  10000~10019 × 5000스텝, γ 0.9916661555611042, 끝 600스텝 제외, 앞 제외 0. 확률 모드는 같은 조건에 stochastic.
  학습 시드마다 모든 결과의 model_sha1 이 같아야 한다. 하나라도 다르면 멈춘다.
- 묶음 유의: Δ = 대조군 − C0 의 (학습 시드 × 평가 시드) 행렬 IQM, 층화 부트스트랩(층 = 평가 시드) 2000회·시드 0 의
  95% CI 가 0 을 빼면 유의. 평가 시드마다 학습 시드 평균을 낸 짝지은 t 도 적는다.
- 크기: 학습 시드마다 C0 의 지표(평가 시드 20개 평균) ≥ 기준. B1 `b1` ≥ 0.3, B2 `b2` ≥ 0.1, B3 `b3_truth` ≥ 0.2.
  ceil(0.8·R) 시드(5시드면 4) 이상이면 성립.
- 쓸모(10-03 사람 결정): B1·B3 = 피식률이 C1′·C2 둘 다보다 유의하게 낮다. B2 = 아사율이 둘 다보다 유의하게 낮거나
  번식이 둘 다보다 유의하게 높다(같은 지표로 두 대조군을 모두 넘어야 한다). G_γ 는 보고만 한다.
- 입력 의존: B1 ← C4-pred_dist-fix, B2 ← C4-energy-fix, B3 ← C4-threat_recency-fix. 크기를 넘은 학습 시드 모두에서
  그 C4 의 같은 지표가 기준 아래이고 크기도 성립해야 성립.
- 학습 실패(5.0): Δ G_γ(C2-seg − C0) 묶음 CI 하한 > 0 이면 학습 실패. E1-b C2-seg 와 E2 A-허용 C2-seg 둘 다 본다.
  C5(Utility v2)는 아직 없다.
- 2차 지표 7개(Holm, m = 7): Δ = C0 − 기준(대조군·기준선·상수). p = 평가 시드마다 학습 시드 평균을 낸 Δ 의
  일표본 t(자유도 n−1) 양측 p. 통과 = Holm p < 0.05 이고 Δ 평균의 부호가 기대와 같고 Δ IQM CI 가 그 방향으로 0 을 뺀다.
- #29: 확률 − 결정의 G_γ·B1·B2·B3 와 결과 지표 Holm(`diagnose_v2.py modecmp`). 기록만 한다(판정은 결정 모드).
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch 보다 먼저

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import re  # noqa: E402
import warnings  # noqa: E402
from concurrent.futures import ProcessPoolExecutor  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

import numpy as np  # noqa: E402

from diagnose_v2 import (  # noqa: E402
    T_CRIT, clean, col_means, config_digest, excludes_zero, fmean, holm, iqm, model_fingerprint, paired, save_json,
    stratified_bootstrap_ci, t_pvalue,
)
from env.config import Config  # noqa: E402
from env.rollout import _init_worker  # noqa: E402
from env_v2.config import load_v2_config  # noqa: E402
from env_v2.rollout import build_policy, g_gamma, tail_steps  # noqa: E402
from env_v2.world import World  # noqa: E402

REF = ROOT / "results" / "v2"                 # 읽기 전용 기준 결과(E1-b, E2, v1 진단)
CONFIG = ROOT / "configs" / "v2_2.yaml"
DIGEST = "efc8f775f1e1"                        # configs/v2_2.yaml = results/v2/e2/configs/V0_d0_95.yaml
GAMMA = 0.9916661555611042
EVAL_SEEDS = list(range(10000, 10020))
EVAL_STEPS = 5000
TAIL = 600
REPS, BOOT_SEED = 2000, 0
SEEDS = (0, 1, 2, 3, 4)
SIZE_FRAC = 0.8                                # 5시드 중 4시드 → ceil(0.8·R)
ALPHA = 0.05

# 비교 대상 상수 (새로 찾지 않는다)
E2_C2 = [0.9709889334578663, 0.7849404966375042, 0.2182330585135458, 0.03358694847233987, 0.4913744307309694, 0.25]
E1B_SEG = {"bins": [[2, [0.5]], [4, [0.5]]], "dims": [4],
           "table": [0.31542835092418386, 0.3637107709426226, 0.5701967704178796, 0.43860151346232035]}
E2_SEG = {"bins": [[7, [0.5, 1.0]]], "dims": [5],
          "table": [0.11827442586893322, 0.6399210213275238, 0.1433532874090464]}
E2_C2_JSON = REF / "e2" / "V0" / "c2" / "constsearch.json"
E2_SEG_JSON = REF / "e2" / "V0" / "d0_95" / "a_allow.json"
E1B_SEG_JSON = REF / "e1" / "B1" / "r2_5_ew0_5" / "constsearch_seg.json"
V1_DIAG_JSON = REF / "diag_final" / "ablate.json"     # v1 학습 정책·Utility, v2.0 세계(= v1), 평가 시드 20 × 5000

# 1차 지표 (PREREG 3절). 열은 World.gait_stats / vigil_stats 의 이름이다.
PRIMARY = {
    "B1": {"col": "b1", "crit": 0.3, "outcomes": ["predation_rate"], "dep": "C4-pred_dist-fix",
           "cross": ["C4-pred_dist-perm", "C4-energy-fix", "C4-energy-perm", "C4-threat_recency-fix",
                     "C4-threat_recency-perm"]},
    "B2": {"col": "b2", "crit": 0.1, "outcomes": ["starve_rate", "repro"], "dep": "C4-energy-fix",
           "cross": ["C4-energy-perm", "C4-pred_dist-fix", "C4-pred_dist-perm", "C4-threat_recency-fix",
                     "C4-threat_recency-perm"]},
    "B3": {"col": "b3_truth", "crit": 0.2, "outcomes": ["predation_rate"], "dep": "C4-threat_recency-fix",
           "cross": ["C4-threat_recency-perm", "C4-pred_dist-fix", "C4-pred_dist-perm", "C4-energy-fix",
                     "C4-energy-perm"]},
}
USE_REFS = ("C1'", "C2")
# Δ = 대조군 − C0 가 이 부호면 C0 가 낫다
BETTER_IF_DELTA = {"g_gamma": -1, "predation_rate": +1, "starve_rate": +1, "repro": -1, "survival": -1}

# 2차 지표 (PREREG 6절). Δ = C0 − 기준, 기대 부호. 기준: ("control", 이름) | ("baseline", 키) | ("const", 값)
SECONDARY = [
    {"id": "B4", "col": "b4_narrow", "ref": ("baseline", "b4_v1"), "sign": -1,
     "what": "재탐지: 120° 결정 이동 도주 중 다음 스텝에 놓친 비율 − v1 학습 정책 기준선(같은 평가 시드)"},
    {"id": "B5", "col": "b5", "ref": ("control", "C4-energy-fix"), "sign": -1,
     "what": "경계와 배고픔: 관측적 기울기 b5 의 C0 − C4-energy 고정"},
    {"id": "B5′", "col": "b5p_truth", "ref": ("control", "C1'"), "sign": +1,
     "what": "위험과 경계: b5p_truth(반경 안 − 밖 P(경계))의 C0 − C1′"},
    {"id": "B6-hunger", "col": "b6_hunger", "ref": ("control", "C1'"), "sign": -1,
     "what": "FID 의 배고픔 기울기 C0 − C1′"},
    {"id": "B6-cover", "col": "b6_cover", "ref": ("control", "C1'"), "sign": +1,
     "what": "FID 의 은신처 거리 기울기 C0 − C1′"},
    {"id": "B7", "col": "b7", "ref": ("control", "C1'"), "sign": -1,
     "what": "무리 간격: 동족 중심 거리(반경 안 포식자 있음 − 없음)의 C0 − C1′"},
    {"id": "B8", "col": "b8", "ref": ("const", 0.5), "sign": -1,
     "what": "깜빡임: 실제 보행 전환(/초) − 0.5"},
]

OUT_COLS = ["mean_return", "g_gamma", "survival", "repro", "predation_rate", "starve_rate", "starve_share"]
GAIT_COLS = ["stop_frac", "walk_frac", "run_frac", "stall_frac", "stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd",
             "hungry_frac", "b1", "p_run_unseen", "p_run_d025", "p_run_d050", "p_run_d100",
             "b1_d025", "b1_d050", "b1_d100", "b2", "p_stop_hungry", "p_stop_full", "b8", "b8_cmd",
             "intake_per_step", "drain_per_step"]
VIG_COLS = ["vig_frac", "seg_seen_frac", "seg_recent_frac", "seg_calm_frac", "p_vig_seen", "p_vig_recent",
            "p_vig_calm", "b3", "b3_narrow", "b3_truth", "p_vig_recent_truth", "p_vig_calm_truth",
            "p_vig_near_truth", "seg_near_truth_frac", "seg_recent_truth_frac", "b4", "b4_n", "b4_narrow",
            "b4_narrow_n", "b4_wide", "b4_wide_n", "b4_vig", "b5", "p_vig_hungry", "p_vig_full", "b5p_pred",
            "b5p_pred_narrow", "b5p_truth", "b5p_ema", "b8_vig", "obs_wide_frac", "threat_mean"]
BEH_COLS = ["cohesion_mean", "flee_dist_mean", "flee_dist_std", "cover_frac", "react_pred", "react_hunger"]
B67_COLS = ["b6_hunger", "b6_cover", "b6_n", "b6_fid_mean", "b7", "b7_near_n", "b7_far_n", "b7_obs_narrow"]
COLS = OUT_COLS + GAIT_COLS + VIG_COLS + BEH_COLS + B67_COLS
KEY_COLS = OUT_COLS + ["stop_frac_cmd", "walk_frac_cmd", "run_frac_cmd", "hungry_frac", "b1", "b1_d025", "b1_d050",
                       "b1_d100", "b2", "p_stop_hungry", "p_stop_full", "b8", "b8_cmd", "vig_frac", "p_vig_seen",
                       "p_vig_recent", "p_vig_calm", "b3", "b3_narrow", "b3_truth", "b4", "b4_narrow", "b4_wide",
                       "b5", "b5p_pred", "b5p_pred_narrow", "b5p_truth", "b5p_ema", "b8_vig", "obs_wide_frac",
                       "flee_dist_std"]
# ablate·permute 에 있어야 하는 대조군 (PREREG 4절)
ABLATE_NAMES = ["C0", "C1", "C3-forage", "C3-cohesion", "C3-flee_dist", "C3-cover", "C3-speed", "C3-vigilance", "C1'"]
PERMUTE_NAMES = ["C4-pred_dist-fix", "C4-pred_dist-perm", "C4-energy-fix", "C4-energy-perm",
                 "C4-threat_recency-fix", "C4-threat_recency-perm"]
# B6·B7 롤아웃
B6_MIN_EVENTS = 30
B67_POLICIES = ("C0", "C1'")
VIDEO_STEPS = 1800
VIDEO_EVAL_SEED = 10000


# --------------------------------------------------------------------- #
# 공용
# --------------------------------------------------------------------- #


def load(p: Path) -> dict:
    if not p.exists():
        raise SystemExit(f"{p} 가 없다")
    return json.loads(p.read_text(encoding="utf-8"))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def vigilance_block() -> dict:
    """configs/v2_2.yaml 의 vigilance 블록 그대로 (B4 기준선 세계에 붙인다)."""
    return dict(load_v2_config(CONFIG).v2["features"]["vigilance"])


def pool(workers: int) -> ProcessPoolExecutor:
    return ProcessPoolExecutor(max_workers=max(1, workers), initializer=_init_worker)


def run_of(a, seed: int) -> str:
    """학습 시드 하나의 실행 이름 (`--prefix` + `_s<시드>`). 기본 v2_2_s<시드> 는 1-6 이름 그대로다."""
    return f"{a.prefix}_s{int(seed)}"


def sdir_of(a) -> Path:
    """B6·B7 결과와 판정표를 두는 폴더 `<res>/<--sdir>` (기본 s1_6)."""
    return Path(a.res) / a.sdir


def parse_seeds(tokens) -> list[int]:
    out = []
    for tok in tokens:
        a, sep, b = str(tok).partition(":")
        out.extend(range(int(a), int(b)) if sep else [int(a)])
    return out


# --------------------------------------------------------------------- #
# b3defs — 학습 전: B3 정의 고르기 (합성 정책, 보정 시드)
# --------------------------------------------------------------------- #

B3DEF_SEEDS = [100, 101, 102, 103, 104]
B3DEF_STEPS = 3000
B3DEF_KINDS = ["blind_m90", "blind_m96", "hungry_iid", "hungry_m90", "hungry_m96", "threat_rule", "threat_p30",
               "threat_plus_blind", "threat_p30_plus_hungry"]
B3DEF_COLS = ["vig_frac", "b3", "b3_narrow", "b3_truth", "p_vig_recent", "p_vig_calm", "p_vig_recent_truth",
              "p_vig_calm_truth", "seg_recent_frac", "seg_recent_truth_frac", "b5p_pred", "b5p_pred_narrow",
              "b5p_truth", "obs_wide_frac"]
B3DEF_NOTE = {
    "blind_m90": "포식자를 보지 않는 지속 경계: 직전 경계면 0.9 로 유지, 아니면 0.05 로 시작",
    "blind_m96": "같은 꼴, 유지 0.96 · 시작 0.01",
    "hungry_iid": "배고프면(energy<0.5) 결정마다 0.3, 아니면 0.02 (지속 없음)",
    "hungry_m90": "유지 0.9, 시작은 배고프면 0.05 · 아니면 0.005",
    "hungry_m96": "유지 0.96, 시작은 배고프면 0.03 · 아니면 0.002",
    "threat_rule": "최근 위협·안 보임(θ ≤ 관측 7 < 1)이면 경계 (Gate E2 C2-seg 꼴)",
    "threat_p30": "최근 위협·안 보임이면 0.3 확률로 경계",
    "threat_plus_blind": "threat_rule 또는 blind_m90",
    "threat_p30_plus_hungry": "threat_p30 또는 hungry_m90",
}


def _b3def_policy(kind: str, seed: int):
    rng = np.random.default_rng([seed, 777])
    prev = np.zeros(0, dtype=bool)

    def pol(obs):
        nonlocal prev
        if len(prev) != len(obs):
            prev = np.zeros(len(obs), dtype=bool)
        hungry = obs[:, 4] < 0.5
        recent = (obs[:, 7] >= 0.5) & (obs[:, 7] < 1.0)
        u = rng.random(len(obs))
        blind90 = u < np.where(prev, 0.9, 0.05)
        hm90 = u < np.where(prev, 0.9, np.where(hungry, 0.05, 0.005))
        v = {"blind_m90": blind90,
             "blind_m96": u < np.where(prev, 0.96, 0.01),
             "hungry_iid": u < np.where(hungry, 0.3, 0.02),
             "hungry_m90": hm90,
             "hungry_m96": u < np.where(prev, 0.96, np.where(hungry, 0.03, 0.002)),
             "threat_rule": recent,
             "threat_p30": recent & (u < 0.3),
             "threat_plus_blind": recent | blind90,
             "threat_p30_plus_hungry": (recent & (u < 0.3)) | hm90}[kind]
        prev = v
        a = np.empty((len(obs), 6))
        a[:, :5] = E2_C2[:5]
        a[:, 5] = np.where(v, 1.0, 0.0)
        return a
    return pol


def _b3def_job(args):
    kind, seed = args
    w = World(load_v2_config(CONFIG), seeds=[seed])
    pol = _b3def_policy(kind, seed)
    for _ in range(B3DEF_STEPS):
        w.step(pol(w.observe()))
    s = w.vigil_stats()
    return kind, seed, {c: s[c] for c in B3DEF_COLS}


def cmd_b3defs(a) -> int:
    jobs = [(k, s) for k in B3DEF_KINDS for s in B3DEF_SEEDS]
    with pool(a.workers) as ex:
        res = list(ex.map(_b3def_job, jobs))
    per = {k: {str(s): r for kk, s, r in res if kk == k} for k in B3DEF_KINDS}
    summ = {}
    for k in B3DEF_KINDS:
        rows = list(per[k].values())
        summ[k] = {c: {"mean": fmean([r[c] for r in rows]), "min": float(np.nanmin([r[c] for r in rows])),
                       "max": float(np.nanmax([r[c] for r in rows]))} for c in B3DEF_COLS}
        m = summ[k]
        print(f"{k:24s} 경계 {m['vig_frac']['mean']:.3f} | b3 {m['b3']['mean']:+.3f} "
              f"narrow {m['b3_narrow']['mean']:+.3f} [{m['b3_narrow']['min']:+.3f}, {m['b3_narrow']['max']:+.3f}] "
              f"truth {m['b3_truth']['mean']:+.3f} [{m['b3_truth']['min']:+.3f}, {m['b3_truth']['max']:+.3f}] | "
              f"b5p {m['b5p_pred']['mean']:+.3f} narrow {m['b5p_pred_narrow']['mean']:+.3f} "
              f"truth {m['b5p_truth']['mean']:+.3f}")
    out = Path(a.res) / "s1_6" / "b3_defs.json"
    save_json(out, {"generated": now(), "script": "python results/v2/_stage1_6_v2_2.py b3defs",
                    "config": "configs/v2_2.yaml", "config_digest": config_digest(load_v2_config(CONFIG)),
                    "seeds": B3DEF_SEEDS, "steps": B3DEF_STEPS, "base_action": E2_C2[:5],
                    "policies": B3DEF_NOTE, "summary": summ, "per_seed": per})
    print(f"저장: {out}")
    return 0


# --------------------------------------------------------------------- #
# b4base — 학습 전: B4 v1 기준선 (v1 세계 + 경계 장치, 경계는 쓰지 않음)
# --------------------------------------------------------------------- #

V1_STAT = ["mean_return", "survival", "repro", "predation_rate", "cohesion_mean", "flee_dist_mean", "flee_dist_std",
           "cover_frac", "react_pred", "react_hunger"]


def b4_world_cfg() -> Config:
    """v1 세계(configs/v2.yaml = v2.0, 기능 없음)에 v2_2.yaml 의 vigilance 블록만 붙인 설정. 경계 행동은 늘 0 이라
    경계가 일어나지 않고 동역학은 v1 과 같다(결과로 확인한다: World.stats() 10열이 diag_final 의 행과 같아야 한다).
    b4 는 vigil_stats 가 세므로 이 장치가 필요하다. 결정 관측은 늘 기본 FOV 120° 라 b4 = b4_narrow."""
    cfg = load_v2_config(ROOT / "configs" / "v2.yaml")
    return cfg.replace(v2=dict(cfg.v2, features={"vigilance": vigilance_block()}))


def _b4_job(args):
    cfg_dict, kind, seed, steps, gamma, tail = args
    cfg = Config(cfg_dict)
    spec = ({"kind": "learned", "model": str((ROOT / "ckpt" / "final.zip").resolve())} if kind == "v1_learned"
            else {"kind": "utility"})
    base = build_policy(spec, seed)
    w = World(cfg, seeds=[seed])
    N = w.N
    rew = np.empty((steps, N))
    done = np.empty((steps, N), dtype=bool)
    for t in range(steps):
        obs = w.observe()
        a4 = np.asarray(base(obs[:, :7]), dtype=np.float64)
        a = np.concatenate([a4, np.zeros((N, 1))], axis=1)        # vigilance 0 → 경계 없음
        _, r, d, _ = w.step(a)
        rew[t], done[t] = r, d
    s = w.stats()
    v = w.vigil_stats()
    row = {"seed": int(seed), **{c: float(s[c]) for c in V1_STAT}, "g_gamma": g_gamma(rew, done, gamma, tail, 0)}
    row.update({c: float(v[c]) for c in ("b4", "b4_n", "b4_narrow", "b4_narrow_n", "b4_wide_n", "vig_frac",
                                         "obs_wide_frac")})
    return kind, row


def cmd_b4base(a) -> int:
    cfg = b4_world_cfg()
    seeds = parse_seeds(a.eval_seeds) if a.eval_seeds else EVAL_SEEDS
    steps = a.eval_steps or EVAL_STEPS
    jobs = [(cfg.to_dict(), k, s, steps, GAMMA, TAIL) for k in ("v1_learned", "utility") for s in seeds]
    with pool(a.workers) as ex:
        res = list(ex.map(_b4_job, jobs))
    rows = {k: sorted([r for kk, r in res if kk == k], key=lambda r: r["seed"]) for k in ("v1_learned", "utility")}
    # v1 세계와 같은가: diag_final(v2.0 세계, 같은 정책·시드·스텝)의 World.stats() 10열과 G_γ 가 같아야 한다
    ref = load(V1_DIAG_JSON)
    same = {}
    for k, name in (("v1_learned", "C0"), ("utility", "Utility")):
        refrows = {r["seed"]: r for r in ref["per_seed"][name]}
        ok = []
        for r in rows[k]:
            rr = refrows.get(r["seed"])
            ok.append(bool(rr is not None and steps == ref["meta"]["eval_steps"]
                           and all(rr[c] == r[c] for c in V1_STAT + ["g_gamma"])))
        same[k] = {"all": bool(all(ok)), "per_seed": ok}
    summ = {k: {c: fmean([r[c] for r in rows[k]]) for c in ("b4", "b4_narrow", "b4_n", "b4_wide_n", "vig_frac",
                                                              "survival", "predation_rate", "g_gamma")}
            for k in rows}
    out = Path(a.res) / "s1_6" / "b4_v1_baseline.json"
    save_json(out, {
        "generated": now(), "script": "python results/v2/_stage1_6_v2_2.py b4base",
        "world": "configs/v2.yaml(v1 세계) + configs/v2_2.yaml 의 vigilance 블록, 경계 행동 0",
        "config_digest": config_digest(cfg), "eval_seeds": seeds, "eval_steps": steps, "gamma": GAMMA, "tail": TAIL,
        "policies": {"v1_learned": "ckpt/final.zip (결정 모드, 관측 앞 7개)", "utility": "Utility (관측 앞 7개)"},
        "model_sha1": model_fingerprint(ROOT / "ckpt" / "final.zip"),
        "same_as_v1_world": same, "summary": summ, "per_seed": rows})
    print(json.dumps({"same_as_v1_world": {k: v["all"] for k, v in same.items()}, "summary": summ},
                     ensure_ascii=False, indent=1))
    print(f"저장: {out}")
    return 0


# --------------------------------------------------------------------- #
# b67 — 학습 뒤: B6(FID)·B7(무리 간격) 롤아웃
# --------------------------------------------------------------------- #


def b67_specs(model: Path) -> dict:
    base = {"kind": "learned", "model": str(model.resolve())}
    return {"C0": base, "C1'": {"policy": base, "wrap": [{"kind": "act_permute", "salt": 0}]}}


def _ols(y: np.ndarray, X: np.ndarray) -> np.ndarray | None:
    A = np.c_[np.ones(len(y)), X]
    if len(y) < B6_MIN_EVENTS or np.linalg.matrix_rank(A) < A.shape[1]:
        return None
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return coef


def _b67_job(args):
    """`env_v2.rollout.rollout` 과 같은 순서(observe → 정책 → step)로 돌려 같은 궤적을 만들고, 결정 때 상태로
    B6·B7 을 센다. 세계를 바꾸는 호출은 하지 않는다(읽기만). G_γ·결과 지표는 진단 결과 행과 맞춰 본다."""
    cfg_dict, name, spec, seed, steps, gamma, tail, rec_vig = args
    cfg = Config(cfg_dict)
    pol = build_policy(spec, seed)
    w = World(cfg, seeds=[seed])
    N = w.N
    see_r = float(cfg.see_r)
    t_run = float(cfg.v2["features"]["speed"]["thresholds"][1])
    v_thr = float(cfg.v2["features"]["vigilance"]["threshold"])
    rew = np.empty((steps, N))
    done = np.empty((steps, N), dtype=bool)
    prev_run = np.zeros(N, dtype=bool)
    prev_ok = np.zeros(N, dtype=bool)
    fid, hun, cov = [], [], []
    dsum = np.zeros(2)                 # [반경 안 포식자 없음, 있음]
    dn = np.zeros(2)
    osum = np.zeros(2)                 # 120° 결정 관측 기준 [안 보임, 보임]
    on = np.zeros(2)
    eye = np.eye(N, dtype=bool)
    vig_count = []
    for t in range(steps):
        obs = w.observe()
        a = np.asarray(pol(obs), dtype=np.float64)
        w._check_action(a)
        # --- 결정 때 상태 (읽기만) ---
        P = w.pos
        near = w._near.copy()                          # 결정 위치에서 see_r 안 포식자 (FOV 무시, vigil_stats 와 같다)
        wide = w._wide.copy()                          # 결정 관측이 경계 시야(직전 스텝 경계)
        dx = P[:, 0][None, :] - P[:, 0][:, None]
        dy = P[:, 1][None, :] - P[:, 1][:, None]
        kin = (np.sqrt(dx * dx + dy * dy) <= see_r) & ~eye
        cnt = kin.sum(1)
        ok = cnt > 0
        cen = (kin.astype(np.float64) @ P) / np.maximum(cnt, 1)[:, None]
        dc = np.sqrt(((cen - P) ** 2).sum(1))
        for g in (0, 1):
            m = ok & (near == bool(g))
            dsum[g] += dc[m].sum()
            dn[g] += m.sum()
        seen = obs[:, 1] > 0
        for g in (0, 1):
            m = ok & ~wide & (seen == bool(g))
            osum[g] += dc[m].sum()
            on[g] += m.sum()
        vig = a[:, 5] > v_thr
        run = (a[:, 4] >= t_run) & ~vig                 # B1 의 '뛰기'와 같다: 경계가 아니고 명령이 뛰기
        onset = run & ~prev_run & prev_ok & seen
        if onset.any():
            fid.append(obs[onset, 2].astype(np.float64))
            hun.append(1.0 - obs[onset, 4].astype(np.float64))
            cov.append(obs[onset, 6].astype(np.float64))
        if rec_vig and t < VIDEO_STEPS:
            vig_count.append(int(vig.sum()))
        _, r, d, _ = w.step(a)
        rew[t], done[t] = r, d
        prev_run = run & ~d
        prev_ok = ~d
    s = w.stats()
    fid = np.concatenate(fid) if fid else np.empty(0)
    X = np.c_[np.concatenate(hun), np.concatenate(cov)] if len(fid) else np.empty((0, 2))
    coef = _ols(fid, X)
    nan = float("nan")
    row = {"seed": int(seed), "g_gamma": g_gamma(rew, done, gamma, tail, 0), "survival": float(s["survival"]),
           "predation_rate": float(s["predation_rate"]), "repro": float(s["repro"]),
           "b6_hunger": float(coef[1]) if coef is not None else nan,
           "b6_cover": float(coef[2]) if coef is not None else nan,
           "b6_n": int(len(fid)), "b6_fid_mean": float(fid.mean()) if len(fid) else nan,
           "b7": (dsum[1] / dn[1] - dsum[0] / dn[0]) if dn.all() else nan,
           "b7_near_n": int(dn[1]), "b7_far_n": int(dn[0]),
           "b7_obs_narrow": (osum[1] / on[1] - osum[0] / on[0]) if on.all() else nan}
    if rec_vig:
        row["vig_count_video"] = vig_count
    return name, row


def cmd_b67(a) -> int:
    model =Path(a.ckpt) / f"{run_of(a, a.seed)}.zip"
    if not model.exists():
        raise SystemExit(f"{model} 가 없다")
    dest = sdir_of(a) / f"b67_{run_of(a, a.seed)}.json"
    if dest.exists() and not a.overwrite:
        raise SystemExit(f"{dest} 가 이미 있다 — 덮지 않는다(--overwrite 로만)")
    cfg = load_v2_config(CONFIG)
    if config_digest(cfg) != DIGEST and not a.smoke:
        raise SystemExit(f"configs/v2_2.yaml 의 config_digest {config_digest(cfg)} ≠ {DIGEST}")
    seeds = parse_seeds(a.eval_seeds) if a.eval_seeds else EVAL_SEEDS
    steps = a.eval_steps or EVAL_STEPS
    specs = b67_specs(model)
    jobs = [(cfg.to_dict(), name, spec, s, steps, GAMMA, TAIL, name == "C0" and s == VIDEO_EVAL_SEED)
            for name, spec in specs.items() for s in seeds]
    with pool(a.workers) as ex:
        out = list(ex.map(_b67_job, jobs))
    rows = {name: sorted([r for n, r in out if n == name], key=lambda r: r["seed"]) for name in specs}
    save_json(dest, {"meta": {"generated": now(), "command": "python results/v2/_stage1_6_v2_2.py " + " ".join(sys.argv[1:]),
                              "config_digest": config_digest(cfg), "eval_seeds": seeds, "eval_steps": steps,
                              "gamma": GAMMA, "tail": TAIL, "model_sha1": model_fingerprint(model),
                              "specs": specs, "b6_min_events": B6_MIN_EVENTS},
                     "per_seed": rows})
    for name, rr in rows.items():
        print(f"  {name:5s} b6_hunger {fmean([r['b6_hunger'] for r in rr]):+.4f}  b6_cover "
              f"{fmean([r['b6_cover'] for r in rr]):+.4f}  b6_n {fmean([r['b6_n'] for r in rr]):.0f}  b7 "
              f"{fmean([r['b7'] for r in rr]):+.3f}  G {fmean([r['g_gamma'] for r in rr]):.3f}")
    print(f"저장: {dest}")
    return 0


# --------------------------------------------------------------------- #
# judge — 읽기와 조건 확인
# --------------------------------------------------------------------- #


class Cond:
    """평가 조건. 실제 판정은 상수 그대로, --smoke 는 C0 ablate meta 에서 읽는다."""

    def __init__(self, smoke: bool, first_meta: dict | None = None):
        self.smoke = smoke
        if smoke and first_meta:
            self.eval_seeds = list(first_meta["eval_seeds"])
            self.eval_steps = int(first_meta["eval_steps"])
            self.tail = int(first_meta["tail"])
            self.digest = first_meta["config_digest"]
        else:
            self.eval_seeds, self.eval_steps, self.tail, self.digest = EVAL_SEEDS, EVAL_STEPS, TAIL, DIGEST

    def check(self, d: dict, where: str, *, mode="deterministic", gamma=GAMMA, steps=None, tail=None, head=0):
        m = d["meta"]
        want = {"config_digest": self.digest, "eval_seeds": self.eval_seeds,
                "eval_steps": self.eval_steps if steps is None else steps,
                "tail": self.tail if tail is None else tail}
        for k, v in want.items():
            if m.get(k) != v:
                raise SystemExit(f"{where}: {k}={m.get(k)!r} 인데 {v!r} 이어야 한다")
        if abs(float(m["gamma"]) - gamma) > 1e-12:
            raise SystemExit(f"{where}: γ {m['gamma']} ≠ {gamma}")
        if int(m.get("head") or 0) != head or (m.get("act_mode") or "deterministic") != mode:
            raise SystemExit(f"{where}: head/act_mode 가 다르다 ({m.get('head')}, {m.get('act_mode')})")


def with_derived(row: dict) -> dict:
    r = dict(row)
    u = r.get("p_run_unseen")
    for k in ("d025", "d050", "d100"):
        p = r.get(f"p_run_{k}")
        r[f"b1_{k}"] = (p - u) if (p is not None and u is not None) else None
    return r


def rows_of(d: dict, name: str, seeds: list[int]) -> list[dict]:
    if name not in d["per_seed"]:
        raise SystemExit(f"결과에 {name} 행이 없다 ({list(d['per_seed'])})")
    rows = [with_derived(r) for r in d["per_seed"][name]]
    if [r["seed"] for r in rows] != seeds:
        raise SystemExit(f"{name}: 평가 시드 순서가 다르다")
    return rows


def vec(rows: list[dict], col: str) -> np.ndarray:
    return np.array([float("nan") if r.get(col) is None else float(r[col]) for r in rows], dtype=np.float64)


def same_rows(a: list[dict], b: list[dict], keys=None) -> bool:
    """두 행 목록이 같은가. keys 가 없으면 b 행의 모든 키(b 는 기준 결과)."""
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        for k in (keys or y.keys()):
            if x.get(k) != y.get(k):
                return False
    return True


def check_const(d: dict, where: str, best, bins=None, dims=None, base=None) -> None:
    if [float(x) for x in d["best"]] != [float(x) for x in best]:
        raise SystemExit(f"{where}: 상수가 사전 등록 값과 다르다 ({d['best']})")
    if bins is not None:
        if d.get("bins") != bins or d.get("dims") != dims or [float(x) for x in d.get("base_action", [])] != base:
            raise SystemExit(f"{where}: 구간·행동·바탕 상수가 사전 등록 값과 다르다")


def collect(a, cond_holder: list) -> tuple[dict, dict, dict, dict]:
    """학습 시드별 {대조군: 행 목록}(결정 모드), 확률 모드 C0, 재현 검사, G_0.998 참고."""
    res = Path(a.res)
    seeds = list(a.seeds)
    first = load(res / f"diag_{run_of(a, seeds[0])}" / "ablate.json")
    cond = Cond(a.smoke, first["meta"])
    cond_holder.append(cond)
    S = cond.eval_seeds
    det, stoch, repro, g998 = {}, {}, {}, {}
    if not a.smoke:
        e2c2, e2seg, e1seg = load(E2_C2_JSON), load(E2_SEG_JSON), load(E1B_SEG_JSON)
        cond.check(e2c2, "E2 C2")
        cond.check(e2seg, "E2 A-허용 C2-seg")
        check_const(e2c2, "E2 C2", E2_C2)
        check_const(e2seg, "E2 A-허용 C2-seg", E2_SEG["table"], E2_SEG["bins"], E2_SEG["dims"], E2_C2)
        check_const(e1seg, "E1-b C2-seg", E1B_SEG["table"], E1B_SEG["bins"], E1B_SEG["dims"], E2_C2[:5])
    for s in seeds:
        dd = res / f"diag_{run_of(a, s)}"
        abl, per, c2 = load(dd / "ablate.json"), load(dd / "permute.json"), load(dd / "constsearch.json")
        sg1, sg2 = load(dd / "c2seg_e1b.json"), load(dd / "c2seg_e2.json")
        files = ((abl, "ablate"), (per, "permute"), (c2, "constsearch"), (sg1, "c2seg_e1b"), (sg2, "c2seg_e2"))
        for d, w in files:
            cond.check(d, f"s{s} {w}")
        sha = {d["meta"].get("model_sha1") for d, _ in files}
        model = Path(a.ckpt) / f"{run_of(a, s)}.zip"
        if len(sha) != 1 or None in sha or (model.exists() and model_fingerprint(model) not in sha):
            raise SystemExit(f"s{s}: 모델 sha1 이 결과마다 다르거나 체크포인트와 다르다 {sha}")
        tmeta = model.with_suffix(".json")             # 학습 메타. config_digest 는 10-03 이후 학습에만 있다
        if tmeta.exists():
            td = load(tmeta).get("config_digest")
            if td is not None and td != cond.digest:
                raise SystemExit(f"s{s}: 학습 메타 config_digest {td} ≠ 평가 {cond.digest}")
        check_const(c2, f"s{s} C2", E2_C2)
        check_const(sg1, f"s{s} C2-seg E1-b", E1B_SEG["table"], E1B_SEG["bins"], E1B_SEG["dims"], E2_C2)
        check_const(sg2, f"s{s} C2-seg E2", E2_SEG["table"], E2_SEG["bins"], E2_SEG["dims"], E2_C2)
        missing = [n for n in ABLATE_NAMES if n not in abl["per_seed"]] + \
                  [n for n in PERMUTE_NAMES if n not in per["per_seed"]]
        if missing:
            raise SystemExit(f"s{s}: 사전 등록 대조군이 없다 {missing}")
        rows = {name: rows_of(abl, name, S) for name in ABLATE_NAMES}
        if rows_of(per, "C0", S) != rows["C0"]:
            raise SystemExit(f"s{s}: permute 의 C0 가 ablate 의 C0 와 다르다")
        for name in PERMUTE_NAMES:
            rows[name] = rows_of(per, name, S)
        rows["C2"] = rows_of(c2, "C2", S)
        rows["C2-seg-E1b"] = rows_of(sg1, "C2-seg", S)
        rows["C2-seg-E2"] = rows_of(sg2, "C2-seg", S)
        for d, w in ((c2, "constsearch"), (sg1, "c2seg_e1b"), (sg2, "c2seg_e2")):
            if rows_of(d, "C0", S) != rows["C0"]:
                raise SystemExit(f"s{s}: {w} 의 C0 가 ablate 의 C0 와 다르다")
        for d, w in ((sg1, "c2seg_e1b"), (sg2, "c2seg_e2")):
            if rows_of(d, "C2", S) != rows["C2"]:
                raise SystemExit(f"s{s}: {w} 의 C2 가 constsearch 의 C2 와 다르다")
        # B6·B7 롤아웃 → C0·C1′ 행에 붙인다 (같은 궤적인지 G_γ·결과 지표로 확인)
        b67 = load(sdir_of(a) / f"b67_{run_of(a, s)}.json")
        bm = b67["meta"]
        if (bm["config_digest"] != cond.digest or bm["eval_seeds"] != S or bm["eval_steps"] != cond.eval_steps
                or abs(bm["gamma"] - GAMMA) > 1e-12 or bm["tail"] != cond.tail or bm["model_sha1"] not in sha):
            raise SystemExit(f"s{s}: b67 조건이 진단 결과와 다르다")
        for name in B67_POLICIES:
            br = b67["per_seed"][name]
            if [r["seed"] for r in br] != S:
                raise SystemExit(f"s{s} b67 {name}: 평가 시드 순서가 다르다")
            for r, x in zip(rows[name], br):
                if any(r[c] != x[c] for c in ("g_gamma", "survival", "predation_rate", "repro")):
                    raise SystemExit(f"s{s} b67 {name} 시드 {x['seed']}: 진단 행과 궤적이 다르다")
                r.update({c: x[c] for c in B67_COLS})
                if "vig_count_video" in x:
                    r["vig_count_video"] = x["vig_count_video"]
        det[s] = rows
        if not a.smoke:
            repro[s] = {
                "C2 (E2 V0/c2)": same_rows(rows["C2"], rows_of(e2c2, "C2", S)),
                "C2-seg-E2 (E2 V0/d0_95 a_allow)": same_rows(rows["C2-seg-E2"], rows_of(e2seg, "C2-seg", S)),
                # E1-b 는 v2.1 세계(경계 열 없음)라 E1-b 행의 열만 맞춘다
                "C2-seg-E1b (E1-b B1 r2_5_ew0_5)": same_rows(rows["C2-seg-E1b"], rows_of(e1seg, "C2-seg", S)),
            }
        st = load(res / f"diag_{run_of(a, s)}_stoch" / "ablate.json")
        cond.check(st, f"s{s} stoch", mode="stochastic")
        if st["meta"].get("model_sha1") not in sha:
            raise SystemExit(f"s{s}: 확률 모드 결과의 모델이 다르다")
        stoch[s] = {name: rows_of(st, name, S) for name in st["per_seed"]}
        g = load(dd / "g998" / "c2seg_e2_g998.json")
        cond.check(g, f"s{s} g998", gamma=0.998, steps=10000, tail=tail_steps(0.998), head=500)
        if g["meta"].get("model_sha1") not in sha:
            raise SystemExit(f"s{s}: g998 결과의 모델이 다르다")
        g998[s] = {k: rows_of(g, k, S) for k in ("C0", "C2-seg", "C2")}
    return det, stoch, repro, g998


# --------------------------------------------------------------------- #
# 통계
# --------------------------------------------------------------------- #


def matrix(by_seed: dict, name: str, col: str, seeds) -> np.ndarray:
    return np.array([vec(by_seed[s][name], col) for s in seeds])


def paired_nan(a: np.ndarray, b: np.ndarray) -> dict:
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 2:
        return {"diff": float("nan"), "t": float("nan"), "sig": False, "n": int(ok.sum())}
    r = paired(a[ok], b[ok])
    r["n"] = int(ok.sum())
    return r


def bundle_delta(by_seed: dict, name: str, col: str, seeds, ref: str = "C0") -> dict:
    A, B = matrix(by_seed, name, col, seeds), matrix(by_seed, ref, col, seeds)
    D = A - B
    ci = stratified_bootstrap_ci(D, stat=iqm, reps=REPS, seed=BOOT_SEED)
    t_mean = paired_nan(col_means(A), col_means(B))
    return {"delta_iqm": ci, "delta_mean": fmean(D), "ci_excludes_0": excludes_zero(ci), "t_seedmean": t_mean,
            "per_seed": {s: {"mean": fmean(A[i]), "ref_mean": fmean(B[i]), **paired_nan(A[i], B[i])}
                         for i, s in enumerate(seeds)}}


def better(delta: dict, col: str) -> bool:
    """묶음 CI 로 C0 가 대조군보다 '낫다' (Δ = 대조군 − C0)."""
    ci = delta["delta_iqm"]
    if not delta["ci_excludes_0"]:
        return False
    return (ci["lo"] > 0) if BETTER_IF_DELTA[col] > 0 else (ci["hi"] < 0)


def second_test(D: np.ndarray, sign: int) -> dict:
    """2차 지표 하나: D = C0 − 기준 (R × T). 평가 시드마다 학습 시드 평균을 낸 값의 일표본 t, CI 는 D 의 IQM."""
    x = col_means(D)
    x = x[np.isfinite(x)]
    n = len(x)
    if n >= 2:
        r = paired(x, np.zeros(n))
        p = t_pvalue(r["t"], n - 1)
    else:
        r, p = {"diff": float("nan"), "t": float("nan"), "sig": False}, float("nan")
    ci = stratified_bootstrap_ci(D, stat=iqm, reps=REPS, seed=BOOT_SEED)
    dir_ok = bool(math.isfinite(r["diff"]) and np.sign(r["diff"]) == sign)
    ci_ok = bool(excludes_zero(ci) and ((ci["lo"] > 0) if sign > 0 else (ci["hi"] < 0)))
    return {"mean": r["diff"], "t": r["t"], "p": p, "n_eval_seeds": n, "delta_iqm": ci,
            "direction_ok": dir_ok, "ci_ok": ci_ok}


# --------------------------------------------------------------------- #
# 개입 곡선 (보정 표본 캐시 위, 결정 모드)
# --------------------------------------------------------------------- #

PD_GRID = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.7, 0.85, 1.0]
EN_GRID = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
TR_GRID = [0.0, 0.2, 0.4, 0.49, 0.5, 0.6, 0.75, 0.9, 0.99]


def act_split(a: np.ndarray, t_walk: float, t_run: float, v_thr: float) -> dict:
    a = np.asarray(a)
    s, v = a[:, 4], a[:, 5] > v_thr
    return {"stop": float(np.mean(s < t_walk)), "walk": float(np.mean((s >= t_walk) & (s < t_run))),
            "run": float(np.mean((s >= t_run) & ~v)), "vig": float(np.mean(v))}


def intervention(a, seed: int) -> dict:
    cal = Path(a.cache) / run_of(a, seed) / "calib.npz"
    with np.load(cal, allow_pickle=False) as z:
        obs = np.asarray(z["obs"], dtype=np.float32)
    cfg = load_v2_config(CONFIG)
    t_walk, t_run = (float(x) for x in cfg.v2["features"]["speed"]["thresholds"])
    v_thr = float(cfg.v2["features"]["vigilance"]["threshold"])
    pol = build_policy({"kind": "learned", "model": str((Path(a.ckpt) / f"{run_of(a, seed)}.zip").resolve())})

    def act(o):
        return np.concatenate([np.asarray(pol(o[i:i + 8192]), np.float64) for i in range(0, len(o), 8192)])

    def split(o):
        return act_split(act(o), t_walk, t_run, v_thr)

    seen = obs[:, 1] > 0
    out = {"samples": int(len(obs)), "seen_samples": int(seen.sum()), "actual_all": split(obs),
           "actual_seen": split(obs[seen]), "actual_unseen": split(obs[~seen]),
           "pred_dist_seen": [], "energy_all": [], "threat_unseen": []}
    for v in PD_GRID:
        o = obs[seen].copy()
        o[:, 2] = v
        out["pred_dist_seen"].append({"x": v, **split(o)})
    for v in EN_GRID:
        o = obs.copy()
        o[:, 4] = v
        out["energy_all"].append({"x": v, **split(o)})
    for v in TR_GRID:
        o = obs[~seen].copy()
        o[:, 7] = v
        out["threat_unseen"].append({"x": v, **split(o)})
    xs = np.array([p["x"] for p in out["energy_all"]])
    ys = np.array([p["vig"] for p in out["energy_all"]])
    out["b5_curve_slope"] = float(np.polyfit(xs, ys, 1)[0])          # B5 기술용: 관측 4 개입의 P(경계) 기울기
    return out


# --------------------------------------------------------------------- #
# judge 본체
# --------------------------------------------------------------------- #


def f(v, spec=".3f") -> str:
    return "—" if v is None or not np.isfinite(float(v)) else format(float(v), spec)


def ci_str(x: dict, spec: str) -> str:
    return f"{f(x['point'], spec)} [{f(x['lo'], spec)}, {f(x['hi'], spec)}]"


def cmd_judge(a) -> int:
    # 값이 모두 nan 인 열(경계를 쓰지 않는 상수 대조군의 경계 지표 등)의 부트스트랩 경고만 끈다
    warnings.filterwarnings("ignore", message="All-NaN slice encountered", category=RuntimeWarning)
    warnings.filterwarnings("ignore", message="Mean of empty slice", category=RuntimeWarning)
    res = Path(a.res)
    holder: list = []
    det, stoch, repro, g998 = collect(a, holder)
    cond = holder[0]
    seeds = list(a.seeds)
    R = len(seeds)
    need = math.ceil(SIZE_FRAC * R)
    names = list(det[seeds[0]].keys())

    controls = {}
    for name in names:
        entry = {"per_seed_mean": {s: {c: fmean(vec(det[s][name], c)) for c in COLS} for s in seeds}}
        if name != "C0":
            entry["vs_C0"] = {c: bundle_delta(det, name, c, seeds) for c in KEY_COLS}
            if name in B67_POLICIES:
                entry["vs_C0"].update({c: bundle_delta(det, name, c, seeds) for c in ("b6_hunger", "b6_cover", "b7")})
        else:
            entry["level"] = {c: stratified_bootstrap_ci(matrix(det, "C0", c, seeds), stat=iqm, reps=REPS,
                                                         seed=BOOT_SEED) for c in KEY_COLS + ["b6_hunger",
                                                                                              "b6_cover", "b7"]}
        controls[name] = entry
    c0 = controls["C0"]["per_seed_mean"]

    # ---- 1차: 크기 · 쓸모 · 입력 의존 ----
    size, usefulness, dependence, claims, sentences = {}, {}, {}, {}, {}
    for x, spec in PRIMARY.items():
        col, crit = spec["col"], spec["crit"]
        vals = {s: c0[s][col] for s in seeds}
        ok = {s: bool(np.isfinite(v) and v >= crit) for s, v in vals.items()}
        size[x] = {"col": col, "crit": crit, "per_seed": vals, "pass_per_seed": ok, "n_pass": sum(ok.values()),
                   "need": need, "holds": sum(ok.values()) >= need, "bundle_iqm": controls["C0"]["level"][col]}
        by_ref = {ref: {c: better(controls[ref]["vs_C0"][c], c) for c in spec["outcomes"]} for ref in USE_REFS}
        path = {c: all(by_ref[ref][c] for ref in USE_REFS) for c in spec["outcomes"]}
        g_rep = {ref: {"delta_iqm": controls[ref]["vs_C0"]["g_gamma"]["delta_iqm"],
                       "c0_higher": better(controls[ref]["vs_C0"]["g_gamma"], "g_gamma")} for ref in USE_REFS}
        usefulness[x] = {"outcomes": spec["outcomes"], "by_ref": by_ref, "by_outcome": path,
                         "holds": bool(any(path.values())), "g_gamma_report": g_rep,
                         "delta": {ref: {c: controls[ref]["vs_C0"][c]["delta_iqm"] for c in spec["outcomes"]}
                                   for ref in USE_REFS}}
        ctrl = spec["dep"]
        cm = controls[ctrl]["per_seed_mean"]
        per = {}
        for s in seeds:
            v = cm[s][col]
            per[s] = {"c0": c0[s][col], "c4": v, "c0_pass": ok[s],
                      "drops": bool(ok[s] and np.isfinite(v) and v < crit)}
        passed = [s for s in seeds if ok[s]]
        dependence[x] = {
            "control": ctrl, "per_seed": per,
            "holds": bool(size[x]["holds"] and all(per[s]["drops"] for s in passed)),
            "holds_in_passed_seeds": bool(passed and all(per[s]["drops"] for s in passed)),
            "c4_below_crit_all_seeds": bool(all(np.isfinite(per[s]["c4"]) and per[s]["c4"] < crit for s in seeds)),
            "report_only": {c: {s: controls[c]["per_seed_mean"][s][col] for s in seeds} for c in spec["cross"]}}
        claims[x] = {"size": size[x]["holds"], "useful": usefulness[x]["holds"],
                     "dependence": dependence[x]["holds"],
                     "holds": bool(size[x]["holds"] and usefulness[x]["holds"] and dependence[x]["holds"])}
        sentences[x] = verdict_sentence(x, spec, size[x], usefulness[x], dependence[x], claims[x])

    # ---- 학습 실패 (5.0) ----
    learn_fail = {}
    for seg in ("C2-seg-E1b", "C2-seg-E2"):
        lf = controls[seg]["vs_C0"]["g_gamma"]
        learn_fail[seg] = {
            "delta_seg_minus_c0": lf["delta_iqm"], "delta_mean": lf["delta_mean"], "t_seedmean": lf["t_seedmean"],
            "per_seed": lf["per_seed"],
            "c0_sig_lower": bool(lf["ci_excludes_0"] and lf["delta_iqm"]["lo"] > 0),
            "c0_sig_higher": bool(lf["ci_excludes_0"] and lf["delta_iqm"]["hi"] < 0),
            "seed_sig_lower": {s: bool(v["t"] is not None and np.isfinite(v["t"]) and v["diff"] > 0
                                       and v["t"] > T_CRIT) for s, v in lf["per_seed"].items()}}
    lf_any = any(v["c0_sig_lower"] for v in learn_fail.values())
    learn_fail_verdict = {"learning_failure": lf_any, "verdict": "학습 실패" if lf_any else "유의하게 낮지 않다",
                          "c5": "C5(Utility v2)는 아직 없다 — 이 칸은 비교하지 않는다"}

    # ---- 2차 (Holm) ----
    b4 = load(res / "s1_6" / "b4_v1_baseline.json")
    b4rows = {r["seed"]: r for r in b4["per_seed"]["v1_learned"]}
    b4ref = np.array([b4rows[s]["b4_narrow"] if s in b4rows else float("nan") for s in cond.eval_seeds])
    sec = {}
    for spec in SECONDARY:
        A = matrix(det, "C0", spec["col"], seeds)
        kind, ref = spec["ref"]
        if kind == "control":
            B = matrix(det, ref, spec["col"], seeds)
        elif kind == "baseline":
            B = np.tile(b4ref, (R, 1))
        else:
            B = np.full_like(A, float(ref))
        sec[spec["id"]] = {"what": spec["what"], "col": spec["col"], "ref": list(spec["ref"]),
                           "expected_sign": spec["sign"], **second_test(A - B, spec["sign"])}
    ph = holm([sec[k]["p"] for k in sec])
    for k, q in zip(sec, ph):
        sec[k]["p_holm"] = q
        sec[k]["pass"] = bool(math.isfinite(q) and q < ALPHA and sec[k]["direction_ok"] and sec[k]["ci_ok"])
    sec_extra = {
        "B5′_crit_0.2_seeds": sum(bool(np.isfinite(c0[s]["b5p_truth"]) and c0[s]["b5p_truth"] >= 0.2) for s in seeds),
        "B8_le_0.5_seeds": sum(bool(np.isfinite(c0[s]["b8"]) and c0[s]["b8"] <= 0.5) for s in seeds),
        "b4_v1_baseline_mean": fmean(b4ref), "b4_v1_same_as_v1_world": b4["same_as_v1_world"],
    }

    # ---- 행동 모드 (#29, 기록) ----
    mode = {}
    for c in ["g_gamma", "b1", "b2", "b3_truth", "b3_narrow", "b8", "b8_vig", "vig_frac", "survival", "starve_rate",
              "predation_rate", "repro", "run_frac_cmd", "stop_frac_cmd"]:
        Dm, Sm = matrix(det, "C0", c, seeds), matrix(stoch, "C0", c, seeds)
        t = paired_nan(col_means(Sm), col_means(Dm))
        ci = stratified_bootstrap_ci(Sm - Dm, stat=fmean, reps=REPS, seed=BOOT_SEED)
        row = {"det": fmean(Dm), "stoch": fmean(Sm), **t, "ci": ci, "ci_excludes_0": excludes_zero(ci),
               "per_seed_stoch": {s: fmean(Sm[i]) for i, s in enumerate(seeds)}}
        if c in ("g_gamma", "b1", "b2", "b3_truth"):
            row["sig"] = bool(t["sig"] and row["ci_excludes_0"])
        mode[c] = row
    mc = load(res / f"diag_{a.prefix}" / "modecmp.json")
    holm_rows = {c: mc["groups"][0]["cols"][c] for c in ("survival", "starve_rate", "predation_rate")}
    trigger = bool(any(mode[c]["sig"] for c in ("g_gamma", "b1", "b2", "b3_truth"))
                   or any(bool(r.get("verdict")) for r in holm_rows.values()))
    stoch_size = {x: {s: mode[PRIMARY[x]["col"]]["per_seed_stoch"][s] for s in seeds} for x in PRIMARY}

    # ---- 참고: G_0.998 ----
    g998_out = {name: bundle_delta(g998, name, "g_gamma", seeds) for name in ("C2-seg", "C2")}
    g998_out["C0_level"] = stratified_bootstrap_ci(matrix(g998, "C0", "g_gamma", seeds), stat=iqm, reps=REPS,
                                                   seed=BOOT_SEED)

    # ---- 개입 곡선 ----
    curves = {s: intervention(a, s) for s in seeds}

    # ---- 영상 (6.4): 시드·정지 화면 규칙 ----
    all3 = [s for s in seeds if all(size[x]["pass_per_seed"][s] for x in PRIMARY)]
    vseed = min(all3) if all3 else seeds[0]
    vrow = next((r for r in det[vseed]["C0"] if r["seed"] == VIDEO_EVAL_SEED), None)
    vc = (vrow or {}).get("vig_count_video")
    video = {"train_seed": vseed, "rule": "1차 세 지표의 크기를 모두 넘은 학습 시드 중 번호가 가장 작은 것, 없으면 첫 시드",
             "eval_seed": VIDEO_EVAL_SEED, "steps": VIDEO_STEPS,
             "png_step": int(np.argmax(vc)) if vc else None,
             "png_rule": "C0 칸에서 경계 개체 수가 가장 많은 스텝(같으면 이른 스텝)",
             "png_vig_count": int(max(vc)) if vc else None}

    stage1 = {"claims_all": bool(all(claims[x]["holds"] for x in PRIMARY)), "learning_failure": lf_any,
              "numeric_pass": bool(all(claims[x]["holds"] for x in PRIMARY) and not lf_any),
              "video": "사람 확인(S1~S3 가 C0 에서 보이고 C1′ 칸에서 사라지는지). 이 스크립트는 판정하지 않는다"}

    data = {
        "generated": now(), "script": "python results/v2/_stage1_6_v2_2.py " + " ".join(sys.argv[1:]),
        "prereg": f"results/v2/{a.sdir}/PREREG.md", "smoke": bool(a.smoke),
        "condition": {"config": "configs/v2_2.yaml", "config_digest": cond.digest, "gamma": GAMMA,
                      "eval_seeds": [cond.eval_seeds[0], cond.eval_seeds[-1]], "n_eval_seeds": len(cond.eval_seeds),
                      "eval_steps": cond.eval_steps, "tail": cond.tail, "train_seeds": seeds,
                      "models": {s: f"ckpt/v2/{run_of(a, s)}.zip" for s in seeds},
                      "model_sha1": {s: load(res / f"diag_{run_of(a, s)}" / "ablate.json")["meta"]["model_sha1"]
                                     for s in seeds},
                      "reps": REPS, "boot_seed": BOOT_SEED, "t_crit": T_CRIT, "size_need": need},
        "reproduction": repro if not a.smoke else "생략(smoke)",
        "controls": controls,
        "size": size, "usefulness": usefulness, "dependence": dependence, "claims": claims,
        "sentences": sentences, "learning_failure": {"by_seg": learn_fail, **learn_fail_verdict},
        "secondary": {"tests": sec, "holm_m": len(sec), "extra": sec_extra},
        "mode": {"cols": mode, "holm_outcomes": holm_rows, "trigger": trigger, "stoch_size": stoch_size},
        "g998": g998_out, "intervention": curves, "video": video, "stage1": stage1,
    }
    out = Path(a.out) if a.out else sdir_of(a) / f"stage1_6_{a.prefix}.json"
    if out.exists() and not a.overwrite:
        raise SystemExit(f"{out} 가 이미 있다 — 덮지 않는다(--overwrite 로만)")
    save_json(out, clean(data))
    print(f"저장: {out}")
    summary(clean(data))
    return 0


def disp(name: str) -> str:
    return name.replace("'", "′")


def verdict_sentence(x, spec, sz, us, dp, cl) -> str:
    """PREREG 9절 판정 문장 형식."""
    name = {"B1": "B1 위협 의존 보행", "B2": "B2 배고플 때 멈춰 먹기", "B3": "B3 놓친 직후 경계(b3_truth)"}[x]
    vals = " / ".join(f(v) for v in sz["per_seed"].values())
    s1 = (f"{name}: (1) 크기 {sz['n_pass']}/{len(sz['per_seed'])}시드가 {sz['crit']} 이상(필요 {sz['need']}, "
          f"시드별 {vals}) → {'성립' if sz['holds'] else '불성립'}")
    parts = []
    for c in spec["outcomes"]:
        d = " · ".join(f"{disp(ref)} Δ {ci_str(us['delta'][ref][c], '.5f')}{'*' if us['by_ref'][ref][c] else ''}"
                       for ref in USE_REFS)
        parts.append(f"{c}: {d}")
    s2 = (f"(2) 쓸모 {' / '.join(parts)} → {'성립' if us['holds'] else '불성립'} "
          f"(G_γ 보고: " + ", ".join(f"{disp(ref)} Δ {ci_str(us['g_gamma_report'][ref]['delta_iqm'], '.3f')}"
                                    for ref in USE_REFS) + ")")
    passed = [s for s, p in dp["per_seed"].items() if p["c0_pass"]]
    drops = [s for s in passed if dp["per_seed"][s]["drops"]]
    s3 = (f"(3) 입력 의존 {dp['control']}: 크기를 넘은 {len(passed)}시드 중 {len(drops)}시드가 기준 아래 "
          f"→ {'성립' if dp['holds'] else '불성립'}{'' if sz['holds'] else '(크기 불성립이라 불성립)'}")
    return f"{s1}. {s2}. {s3}. 판정: **{'성립' if cl['holds'] else '불성립'}**"


def summary(d: dict) -> None:
    print("재현 검사:", d["reproduction"])
    for x, s in d["sentences"].items():
        print(f"\n{s}")
    lf = d["learning_failure"]
    print("\n학습 실패:", lf["verdict"], {k: (v["delta_seg_minus_c0"]["point"], v["delta_seg_minus_c0"]["lo"],
                                             v["delta_seg_minus_c0"]["hi"]) for k, v in lf["by_seg"].items()})
    print("2차(Holm):")
    for k, v in d["secondary"]["tests"].items():
        print(f"  {k:10s} Δ {f(v['mean'], '+.4f')} t {f(v['t'], '+.2f')} p {f(v['p'], '.4f')} "
              f"Holm {f(v['p_holm'], '.4f')} CI [{f(v['delta_iqm']['lo'], '+.4f')}, {f(v['delta_iqm']['hi'], '+.4f')}]"
              f" → {'통과' if v['pass'] else '—'}")
    print("모드(#29) trigger:", d["mode"]["trigger"],
          {c: (f(r["det"]), f(r["stoch"]), f(r["t"], "+.2f"), r.get("sig")) for c, r in d["mode"]["cols"].items()
           if c in ("g_gamma", "b1", "b2", "b3_truth")})
    print("영상:", d["video"])
    print("1단계(수치):", d["stage1"])


# --------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------- #


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="1-6 v2.2 판정 묶음 집계 (PREREG: results/v2/s1_6/PREREG.md)")
    p.add_argument("cmd", nargs="?", default="judge", choices=["b3defs", "b4base", "b67", "judge"])
    p.add_argument("--res", default=str(REF), help="진단 결과·s1_6 의 뿌리 (기본 results/v2)")
    p.add_argument("--cache", default=str(ROOT / "runs" / "v2_diag"), help="보정 표본 캐시 뿌리")
    p.add_argument("--ckpt", default=str(ROOT / "ckpt" / "v2"), help="체크포인트 디렉터리")
    p.add_argument("--prefix", default="v2_2",
                   help="실행 이름 접두사: 학습 시드 s 의 모델·진단 이름이 <prefix>_s<s> (기본 v2_2 = 1-6)")
    p.add_argument("--sdir", default="s1_6",
                   help="b67 결과와 판정표 폴더 <res>/<sdir> (기본 s1_6. 1-6 판정 재실행은 s1_6b)")
    p.add_argument("--seeds", type=int, nargs="+", default=list(SEEDS), help="학습 시드 (judge)")
    p.add_argument("--seed", type=int, default=None, help="학습 시드 하나 (b67)")
    p.add_argument("--eval-seeds", nargs="+", default=None, help="b4base·b67 (기본 10000:10020)")
    p.add_argument("--eval-steps", type=int, default=None, help="b4base·b67 (기본 5000)")
    p.add_argument("--workers", type=int, default=10)
    p.add_argument("--out", default=None, help="judge 출력 JSON (기본 <res>/<sdir>/stage1_6_<prefix>.json)")
    p.add_argument("--overwrite", action="store_true", help="judge·b67 출력이 있으면 덮는다")
    p.add_argument("--smoke", action="store_true", help="도구 시험: 조건을 결과 meta 에서 읽고 재현 검사를 건너뛴다")
    a = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:  # pragma: no cover
        pass
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    if a.cmd == "b67" and a.seed is None:
        raise SystemExit("b67 은 --seed <학습 시드> 가 필요하다")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", a.prefix) or not re.fullmatch(r"[A-Za-z0-9_.-]+", a.sdir):
        raise SystemExit(f"--prefix {a.prefix!r}·--sdir {a.sdir!r} 는 경로 구분자 없는 이름이어야 한다")
    if len(set(a.seeds)) != len(a.seeds):
        raise SystemExit(f"--seeds 에 같은 시드가 두 번 있다 {a.seeds}")
    return {"b3defs": cmd_b3defs, "b4base": cmd_b4base, "b67": cmd_b67, "judge": cmd_judge}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

"""v3 R3 재학습 전 측정 다시 재기 — 늑대 먹는 시간 5스텝(0.67초, 배회) → 38스텝(5.07초, 제자리) 전후 (사람 결정 10-15 (B)).
사전 기록 `PREREG.md`(같은 폴더). 지표 정의·코드는 윗 폴더 `../eval_pre.py`(10-14 재학습 전 측정) 그대로 쓴다.

    # herbivore_rl/ 에서
    python results/v3/r3/pre/eat38/eval_eat38.py run --workers 16   # 본 측정 → eat38.json, eat38_raw.json, tables.md, tables_full.md
    python results/v3/r3/pre/eat38/eval_eat38.py tables             # eat38.json·eat38_raw.json 에서 표만 다시 쓴다
    python results/v3/r3/pre/eat38/eval_eat38.py smoke              # 탐색 시드 32000 × 200스텝, 저장하지 않는다

판정이 아니라 측정이다. 학습하지 않는다. 세계 안을 엿보는 것은 `../eval_pre.py` 의 `Spy`(기록만)와, 그 위에 늑대가 서서 먹은 늑대-스텝을
세는 `EatSpy`(기록만)뿐이다.

- 칸(정책 × 세계). 정책 이름은 `../eval_pre.py` 와 같다(rlf = R1b−F, rl = R1b, rbase = R_base(4, 0.9), c_graze·c_hide = 늘 먹기·늘 숨기).
  - 전(10-14 세계, 먹는 시간 5·배회): r3_cd5 × {rlf, rbase, c_graze, c_hide}, r3_fz_cd5 · rl, base · {rl, rlf}, night · {rl, rlf}, train_ref · rl.
    r3_cd5 = configs/v3_r3_on.yaml 에서 pred_eat_cd 5·threats.eat_in_place false 로 되돌린 세계 — 10-14 의 R3 판정 세계와 비트 같아야 한다.
    전 칸의 요약은 10-14 측정 `../pre.json` 의 같은 칸과 같아야 한다(도구가 확인해 eat38.json 의 repro 에 적는다).
  - 뒤(먹는 시간 38·제자리): r3 × {rlf, rbase, c_graze, c_hide}, r3_fz · rl(지금 configs/v3_r3_on.yaml), base_eat · rlf, night_eat · rlf
    (R1 판정 세계·밤잠 세계에 pred_eat_cd 38·eat_in_place true 를 메모리에서 더한 세계 — 지금 게임에 먹는 시간을 넣기 전 확인).
- 시드: 보정 20000~20019 × 3000스텝. 판정·예약 시드는 쓰지 않는다(`../eval_pre.py` 의 금지 목록으로 시작 전에 막는다).
- 짝 비교(같은 시드, 자유도 19): 뒤 − 전, 같은 정책. 그리고 지금 게임 전체 바뀜(night_eat · R1b−F − night · R1b, base_eat · R1b−F − base · R1b).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
OUT_DIR = HERE.parent
PRE_DIR = HERE.parents[1]                     # results/v3/r3/pre
ROOT = HERE.parents[5]                        # herbivore_rl
for p in (str(ROOT), str(PRE_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

import eval_pre as ep  # noqa: E402

R3_ON = "configs/v3_r3_on.yaml"
FZ = ["graze", "flee", "hide", "freeze"]
OLD_EAT = {"v1": {"pred_eat_cd": 5}, "features": {"threats": {"eat_in_place": False}}}     # 10-14 세계(먹는 시간 0.67초, 배회)
NEW_EAT = {"v1": {"pred_eat_cd": 38}, "features": {"threats": {"eat_in_place": True}}}     # 10-15 결정(5.07초, 제자리)
VARIANTS = {
    "r3": (R3_ON, None),
    "r3_fz": (R3_ON, {"allowed": FZ}),
    "r3_cd5": (R3_ON, OLD_EAT),
    "r3_fz_cd5": (R3_ON, dict(OLD_EAT, allowed=FZ)),
    "base": ("configs/v3_r1_on.yaml", None),
    "base_eat": ("configs/v3_r1_on.yaml", NEW_EAT),
    "night": ("configs/v3_real1_night_on.yaml", None),
    "night_eat": ("configs/v3_real1_night_on.yaml", NEW_EAT),
    "train_ref": ("configs/v3_r1.yaml", None),
}
KEY_POLICIES = ("rlf", "rbase", "c_graze", "c_hide")
OLD_CELLS = tuple(("r3_cd5", p) for p in KEY_POLICIES) + (("r3_fz_cd5", "rl"), ("base", "rl"), ("base", "rlf"), ("night", "rl"),
                                                           ("night", "rlf"), ("train_ref", "rl"))
NEW_CELLS = tuple(("r3", p) for p in KEY_POLICIES) + (("r3_fz", "rl"), ("base_eat", "rlf"), ("night_eat", "rlf"))
CELLS = OLD_CELLS + NEW_CELLS
# 뒤 − 전 (같은 정책·같은 시드) 와 지금 게임 전체 바뀜
PAIRS = tuple((f"r3|{p}", f"r3_cd5|{p}", f"R3 세계 · {ep.PNAME[p]}") for p in KEY_POLICIES) + (
    ("r3_fz|rl", "r3_fz_cd5|rl", "R3 세계(얼기 허용 사본) · R1b(얼기 씀)"),
    ("base_eat|rlf", "base|rlf", "R1 판정 세계 · R1b−F"),
    ("night_eat|rlf", "night|rlf", "R1 세계 + 밤잠 · R1b−F"))
GAME_PAIRS = (("night_eat|rlf", "night|rl", "R1 세계 + 밤잠: (R1b−F, 먹는 시간 38) − (R1b, 5)"),
              ("base_eat|rlf", "base|rl", "R1 판정 세계: (R1b−F, 먹는 시간 38) − (R1b, 5)"))
# 전 칸 → 10-14 측정(../pre.json)의 같은 칸
REPRO = {f"r3_cd5|{p}": f"r3|{p}" for p in KEY_POLICIES} | {"r3_fz_cd5|rl": "r3_fz|rl", "base|rl": "base|rl", "base|rlf": "base|rlf",
                                                            "night|rl": "night|rl", "night|rlf": "night|rlf",
                                                            "train_ref|rl": "train_ref|rl"}
VNAME = {"r3": "R3 세계(먹는 시간 38)", "r3_fz": "R3 세계 얼기 허용 사본(먹는 시간 38)", "r3_cd5": "R3 세계(먹는 시간 5, 10-14)",
         "r3_fz_cd5": "R3 세계 얼기 허용 사본(먹는 시간 5, 10-14)", "base": "R1 판정 세계(먹는 시간 5)",
         "base_eat": "R1 판정 세계(먹는 시간 38)", "night": "R1 세계 + 밤잠(먹는 시간 5)", "night_eat": "R1 세계 + 밤잠(먹는 시간 38)",
         "train_ref": "R1b 학습 세계"}
EAT_STEPS_PER_CATCH = 37                      # 38스텝 쿨다운 가운데 서서 먹는 스텝(잡은 다음 스텝부터 37스텝)

_EAT = {"wolf_steps": 0, "eat_steps": 0, "run": None, "still_max": 0, "rim_run": None, "rim_still_max": 0}


def load_variant(name: str):
    """`../eval_pre.py` 의 load_variant 에 v1 키 덮기(cfg.replace)를 더한 판."""
    from env_v2.config import load_v2_config

    path, mod = VARIANTS[name]
    cfg = load_v2_config(ROOT / path)
    if mod:
        if "v1" in mod:
            cfg = cfg.replace(**mod["v1"])
        v2 = dict(cfg.v2)
        if "features" in mod:
            f = {k: dict(v) for k, v in v2["features"].items()}
            for b, kv in mod["features"].items():
                f[b] = dict(f[b], **kv)
            v2["features"] = f
        if "allowed" in mod:
            tr = dict(v2["train"])
            rp = dict(tr["repertoire"])
            rp["allowed"] = list(mod["allowed"])
            tr["repertoire"] = rp
            v2["train"] = tr
        cfg = cfg.replace(v2=v2)
    return cfg


def _patch() -> None:
    """작업자 안에서 `eval_pre` 의 세계 목록·설정 읽기·Spy 를 이 도구의 것으로 바꾼다(기록만 — 세계 상태·난수를 바꾸지 않는다)."""
    if getattr(ep, "_eat38_patched", False):
        return
    ep.VARIANTS = dict(ep.VARIANTS, **VARIANTS)
    ep.load_variant = load_variant
    base = ep._spy_class()

    class EatSpy(base):
        """서서 먹은 늑대-스텝(이 스텝 첫머리 쿨다운 감소 뒤 cd > 0 인 보통 위협, 플레이어형 위협 제외)과 보통 위협-스텝을 센다. 그리고
        먹지 않는(쿨다운 0) 깨어 있는 늑대가 이어서 제자리(이번 스텝 이동 < STILL_TOL)인 가장 긴 스텝 수를 센다 — 어디서든(still_max)과
        은신처 원 둘레 바로 밖에서(rim_still_max, `../eval_pre.py` 의 끼임 정의). `../eval_pre.py` 의 끼임 최댓값은 먹는 늑대도 세므로 먹는
        시간 38 세계에서는 37 이 나온다(원 둘레에서 먹는 늑대) — 이 두 값이 먹는 늑대를 뺀 끼임이다."""

        def _step_predators_v3(self):
            cd0 = self.pred_cd.copy()
            old = self.pred_pos.copy()
            out = super()._step_predators_v3()
            wolf = ~self.pred_is_player
            eating = (cd0 >= 2) & wolf
            _EAT["wolf_steps"] += int(wolf.sum())
            _EAT["eat_steps"] += int(eating.sum())
            awake = ~self.pred_asleep if self._ps is not None else np.ones(self.M, dtype=bool)
            still = awake & wolf & ~eating & (np.sqrt(((self.pred_pos - old) ** 2).sum(1)) < ep.STILL_TOL)
            if len(self.cov_r):
                dx = self.pred_pos[:, 0:1] - self.cov_c[:, 0][None, :]
                dy = self.pred_pos[:, 1:2] - self.cov_c[:, 1][None, :]
                edge = (np.sqrt(dx * dx + dy * dy) - self.cov_r[None, :]).min(1)
                rim = (edge >= 0.0) & (edge < ep.RIM_TOL)
            else:
                rim = np.zeros(self.M, dtype=bool)
            for key, mask in (("run", still), ("rim_run", still & rim)):
                r = _EAT[key] if _EAT[key] is not None else np.zeros(self.M, dtype=np.int64)
                r = np.where(mask, r + 1, 0)
                _EAT[key] = r
                mk = "still_max" if key == "run" else "rim_still_max"
                _EAT[mk] = max(_EAT[mk], int(r.max()) if len(r) else 0)
            return out

    ep._SPY = EatSpy
    ep._eat38_patched = True


def job(args):
    _patch()
    _EAT.update(wolf_steps=0, eat_steps=0, run=None, still_max=0, rim_run=None, rim_still_max=0)
    r = ep.job(args)
    r["eat"] = {k: _EAT[k] for k in ("wolf_steps", "eat_steps", "still_max", "rim_still_max")}
    cfg = load_variant(args[0])
    th = cfg.v2["features"].get("threats", {})
    r["eat_cfg"] = dict(pred_eat_cd=int(cfg.pred_eat_cd), eat_in_place=bool(th.get("eat_in_place", False)))
    return r


def _map(jobs, workers):
    from env.rollout import _init_worker

    if workers <= 1:
        return [job(j) for j in jobs]
    with ProcessPoolExecutor(min(workers, len(jobs)), initializer=_init_worker) as ex:
        return list(ex.map(job, jobs, chunksize=1))


def _canon(x) -> str:
    return json.dumps(json.loads(json.dumps(x, default=ep._json_default)), sort_keys=True, ensure_ascii=False)


def eat_summary(rows: list[dict]) -> dict:
    """칸마다 서서 먹은 늑대-스텝 몫(시드 합)과 시드 평균, 설정 값."""
    w = sum(r["eat"]["wolf_steps"] for r in rows)
    e = sum(r["eat"]["eat_steps"] for r in rows)
    return dict(eat_share=e / w if w else None, eat_steps=e, wolf_steps=w,
                eat_share_seed_mean=float(np.mean([r["eat"]["eat_steps"] / r["eat"]["wolf_steps"] for r in rows
                                                   if r["eat"]["wolf_steps"]])),
                pred_eat_cd=rows[0]["eat_cfg"]["pred_eat_cd"], eat_in_place=rows[0]["eat_cfg"]["eat_in_place"],
                noneat_still_max=int(max(r["eat"]["still_max"] for r in rows)),
                noneat_rim_still_max=int(max(r["eat"]["rim_still_max"] for r in rows)))


def compare(summ: dict) -> dict:
    out = {}
    for a, b, lab in PAIRS + GAME_PAIRS:
        sa, sb = summ.get(a), summ.get(b)
        if sa is None or sb is None or sa["seeds"] != sb["seeds"]:
            continue
        c = {k: ep._paired(sa["per_seed"][k], sb["per_seed"][k]) for k in ep.PAIR_KEYS}
        c["flee_use"] = ep._paired(sa["per_seed"]["flee_use"], sb["per_seed"]["flee_use"])
        c["rel"] = {k: (sa[k] / sb[k] - 1.0) if sb[k] else None for k in ("pred_rate", "starve_rate", "death_rate")}
        out[f"{a}-{b}"] = dict(a=a, b=b, label=lab, **c)
    return out


def repro(summ: dict) -> dict:
    """전 칸의 요약이 10-14 측정(../pre.json)의 같은 칸과 글자 하나까지 같은가."""
    pre = json.loads((PRE_DIR / "pre.json").read_text(encoding="utf-8"))["summary"]
    out = {}
    for mine, theirs in REPRO.items():
        if mine in summ and theirs in pre:
            a, b = _canon(summ[mine]), _canon(pre[theirs])
            out[mine] = dict(pre_cell=theirs, same=a == b)
    return out


# --------------------------------------------------------------------- #
# 표
# --------------------------------------------------------------------- #

_f, _pc, _dt, _t = ep._f, ep._pc, ep._dt, ep._t


def _name(key):
    v, p = key.split("|")
    return f"{VNAME.get(v, v)} · {ep.PNAME.get(p, p)}"


def tables(agg: dict) -> str:
    S, C, E = agg["summary"], agg["compare"], agg["eat"]
    meta = agg.get("meta", {})
    seeds = meta.get("seeds", ["?"])
    L = ["# R3 재학습 전 측정 — 늑대 먹는 시간 5 → 38스텝 전후 (사람 결정 10-15)", "",
         f"자동 생성 표(`eval_eat38.py`). 정의는 `PREREG.md`(이 폴더)와 `../PREREG.md`. 보정 시드 {seeds[0]}~{seeds[-1]} × "
         f"{meta.get('steps', '?')}스텝, 세계당 사슴 128마리. '전' = 먹는 시간 5스텝(0.67초, 쿨다운 동안 배회 — 10-14 세계), "
         "'뒤' = 38스텝(5.07초, 그중 37스텝은 그 자리에 서서 먹음). 짝 차는 같은 시드의 뒤 − 전(자유도 19, 눈금 |t| ≥ 2.093).", ""]
    rp = agg.get("repro", {})
    if rp:
        bad = [k for k, v in rp.items() if not v["same"]]
        L += [f"재현 점검: 전 칸 {len(rp)}개의 요약이 10-14 측정(`../pre.json`)의 같은 칸과 " +
              ("모두 같다(글자 하나까지)." if not bad else f"다르다: {', '.join(bad)}."), ""]
    # 1. 생존·성과
    L += ["## 1. 생존·성과 (전 → 뒤)", "",
          "| 세계 · 정책 | 피식 /1000 | 아사 /1000 | 합 사망 /1000 | G_γ | 사용 GRAZE/FLEE/HIDE/FREEZE | 늑대 1마리 분당 포획 | 쿨다운 중 늑대-스텝 몫 (뒤: 서서 먹음, 전: 배회) |",
          "|---|---|---|---|---|---|---|---|"]
    for a, b, lab in PAIRS:
        for key, tag in ((b, "전"), (a, "뒤")):
            c = S.get(key)
            if c is None:
                continue
            u = c["use"]
            L.append(f"| {lab} ({tag}) | {_f(1000 * c['pred_rate'])} | {_f(1000 * c['starve_rate'])} | {_f(1000 * c['death_rate'])} | "
                     f"{_f(c['g_gamma'])} | " + "/".join(_pc(u[x], 1) for x in ("graze", "flee", "hide", "freeze"))
                     + f" | {_f(c['wolf']['catch_per_wolf_min'])} | {_pc(E[key]['eat_share'])} |")
    for key in ("base|rl", "night|rl", "train_ref|rl"):
        c = S.get(key)
        if c is None:
            continue
        u = c["use"]
        L.append(f"| {_name(key)} (지금 게임 두뇌, 보고만) | {_f(1000 * c['pred_rate'])} | {_f(1000 * c['starve_rate'])} | "
                 f"{_f(1000 * c['death_rate'])} | {_f(c['g_gamma'])} | " + "/".join(_pc(u[x], 1) for x in ("graze", "flee", "hide", "freeze"))
                 + f" | {_f(c['wolf']['catch_per_wolf_min'])} | {_pc(E[key]['eat_share'])} |")
    # 2. 짝 차
    L += ["", "## 2. 뒤 − 전 (같은 정책, 시드 짝 차와 t)", "",
          "| 비교 | Δ피식 /1000 (t) | Δ아사 /1000 (t) | Δ합 사망 /1000 (t) | ΔG_γ (t) | Δ포기율 A (t) | Δ늑대 분당 포획 (t) | Δ은신처 안 시간 (t) | Δ도주 묶음 /1000 (t) | 상대 피식 | 상대 아사 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for a, b, lab in PAIRS + GAME_PAIRS:
        c = C.get(f"{a}-{b}")
        if c is None:
            continue
        rel = c["rel"]
        L.append(f"| {lab} | {_dt(c['pred_rate'], 3, 1000)} | {_dt(c['starve_rate'], 3, 1000)} | {_dt(c['death_rate'], 3, 1000)} | "
                 f"{_dt(c['g_gamma'])} | {_dt(c['A'])} | {_dt(c['wolf_catch_min'])} | {_dt(c['in_cover_frac'])} | "
                 f"{_dt(c['bouts_per_1k'], 3)} | {_pc(rel['pred_rate'], 0)} | {_pc(rel['starve_rate'], 0)} |")
    # 3. 포기율 A 와 고른 행동별 뒤 잡힘
    L += ["", "## 3. 쫓기는 동안 도주 포기율 A 와 기회에서 고른 행동별 3초 안 잡힘 (전 → 뒤)", "",
          "| 세계 · 정책 | 기회 수 | A (시드 평균) | 같은 기회에서 원래 R1b 의 A | FLEE 3초 잡힘 (기회) | GRAZE 3초 잡힘 (기회) | HIDE 3초 잡힘 (기회) | GRAZE − FLEE 3초 (t, 시드) |",
          "|---|---|---|---|---|---|---|---|"]
    for a, b, lab in PAIRS:
        for key, tag in ((b, "전"), (a, "뒤")):
            c = S.get(key)
            if c is None:
                continue
            A, ao = c["A"], c.get("A_out", {})

            def oc(x):
                v = ao.get(x)
                return f"{_pc(v['caught3s'], 0)} ({v['n']})" if v else "—"
            cfa = A.get("cf_r1b")
            gm = c["A_out_graze_minus_flee"]
            L.append(f"| {lab} ({tag}) | {A['n_opp']} | {_pc(A['mean'])} | {_pc(cfa['mean']) if cfa else '—'} | {oc('flee')} | "
                     f"{oc('graze')} | {oc('hide')} | {_dt(gm)}, {gm.get('n')} |")
    # 4. 관문 니치 선택 확률
    L += ["", "## 4. 관문 니치 초안의 선택 확률 (보고만, 전 → 뒤)", "",
          "| 세계 · 정책 | U_ESC(FLEE∪HIDE) | U_KEEP | G1 P(니치)/P(교차) | U_RUN | U_LEAVE | U_HIDE′ |", "|---|---|---|---|---|---|---|"]
    for a, b, lab in PAIRS:
        for key, tag in ((b, "전"), (a, "뒤")):
            c = S.get(key)
            if c is None:
                continue
            gp, gu = c["g_p"], c["g_u"]
            L.append(f"| {lab} ({tag}) | {_f(c['u']['esc3'])} | {_f(gu['keep'])} | {_pc(gp['keep']['niche'], 0)}/{_pc(gp['keep']['cross'], 0)} | "
                     f"{_f(gu['run'])} | {_f(gu['leave'])} | {_f(c['u']['hide'])} |")
    # 5. 잠행형 돌진 확인표
    L += ["", "## 5. 잠행형 돌진 — 이어 사냥(직전 3초 안에 잡은 늑대)과 새 사냥 (전 → 뒤)", "",
          "| 세계 · 정책 | 끝난 돌진 | 이어 사냥 몫 | 이어 사냥 그 표적 잡음 | 새 사냥 그 표적 잡음 | 새 사냥: 이미 도주 중 / 감지하고 먹는 중 / 못 감지하고 먹는 중 (잡음) |",
          "|---|---|---|---|---|---|"]
    for a, b, lab in PAIRS:
        for key, tag in ((b, "전"), (a, "뒤")):
            c = S.get(key)
            if c is None:
                continue
            pz = c["pounce"]
            fo, fr = pz["_follow"]["follow"], pz["_follow"]["fresh"]

            def hit(d, cat):
                x = d.get(cat)
                return f"{_pc(x['hit'], 0)} ({x['n']})" if x else "—"
            L.append(f"| {lab} ({tag}) | {pz['_all']['n']} | {_pc(fo.get('share'), 0)} | {_pc(fo.get('_all', {}).get('hit'), 0)} | "
                     f"{_pc(fr.get('_all', {}).get('hit'), 0)} | {hit(fr, 'flee_run')} / {hit(fr, 'graze_seen')} / {hit(fr, 'graze_unseen')} |")
    # 6. 추격형 쫓김
    L += ["", "## 6. 추격형(근접 + 원거리)에게 쫓김이 시작된 사슴 — 안전에 닿기 전 잡힌 몫 (전 → 뒤)", "",
          "| 세계 · 정책 | 끝난 쫓김 | 잡힘 | 은신처 | 멀어짐 | 끝까지 도주 잡힘 (수) | 먹으러 멈춤 잡힘 (수) |", "|---|---|---|---|---|---|---|"]
    for a, b, lab in PAIRS:
        for key, tag in ((b, "전"), (a, "뒤")):
            c = S.get(key)
            if c is None:
                continue
            ch = c["chase"]["chaser_all"]

            def cat(x):
                v = ch["cats"].get(x)
                return f"{_pc(v['caught'], 0)} ({v['n']})" if v else "—"
            L.append(f"| {lab} ({tag}) | {ch['n_ended']} | {_pc(ch['caught'], 0)} | {_pc(ch['cover'], 0)} | {_pc(ch['far'], 0)} | "
                     f"{cat('kept')} | {cat('stop_graze')} |")
    # 7. T0
    L += ["", "## 7. 세계 점검 T0 — 땅별 개체-스텝당 잡힘 (전 → 뒤, R3 세계)", "",
          "| 정책 | 보통/눈/거친 땅 잡힘 /1000 (모아서) | 눈 − 보통 /1000 (t, 시드) | 거친 땅 − 보통 /1000 (t, 시드) |", "|---|---|---|---|"]
    for a, b, lab in PAIRS:
        for key, tag in ((b, "전"), (a, "뒤")):
            c = S.get(key)
            if c is None or "t0" not in c:
                continue
            t0 = c["t0"]
            pp = t0["pooled_per_1k"]
            L.append(f"| {lab} ({tag}) | " + "/".join(_f(pp[x]) for x in ("normal", "snow", "rough")) + " | "
                     f"{_dt(t0['snow_minus_normal'])}, {t0['snow_seeds']} | {_dt(t0['rough_minus_normal'])}, {t0['rough_seeds']} |")
    # 8. 밤·은신처
    L += ["", "## 8. 밤 피식·은신처 (전 → 뒤)", "",
          "| 세계 · 정책 | 낮/박명/밤 피식 /1000 | 늑대 잠듦 순간 8 안 사슴 | 은신처 안 시간 | 은신처 안 & 위협을 앎 | 은신처 안 포획 |", "|---|---|---|---|---|---|"]
    for a, b, lab in PAIRS:
        for key, tag in ((b, "전"), (a, "뒤")):
            c = S.get(key)
            if c is None:
                continue
            nt, so, sh = c["night"], c["sleep_onset"], c["shelter"]
            L.append(f"| {lab} ({tag}) | " + "/".join(_f(nt[p]["pred_per_1k"]) for p in ep.PHASES) + f" | {_pc(so['frac'])} ({so['n']}) | "
                     f"{_pc(sh['in_cover_frac'])} | {_pc(sh['cover_k_share'])} | {c['catch']['in_cover']} |")
    # 8-2. 늑대 끼임 (먹는 늑대를 뺀 판)
    L += ["", "### 8-2. 늑대 제자리·끼임 (전 → 뒤)", "",
          "`../eval_pre.py` 의 '가장 긴 끼임'은 원 둘레에서 서서 먹는 늑대도 세어 먹는 시간 38 세계에서는 37 이 된다. 아래 둘째·셋째 칸은 먹지 않는"
          "(쿨다운 0) 깨어 있는 늑대만 센 값이다. '원 안 위협-스텝'은 R3 세계에서는 늘 0 이어야 하는 점검 값이고, R1 두 세계는 진입 금지가 없어 늑대가 원을 "
          "지나다니므로 점검 값이 아니다.", "",
          "| 세계 · 정책 | 가장 긴 끼임 (`../eval_pre.py`, 먹는 늑대 포함) | 먹지 않는 늑대가 원 둘레에서 이어서 제자리 최대 | 먹지 않는 늑대가 어디서든 이어서 제자리 최대 | 원 안 위협-스텝 |",
          "|---|---|---|---|---|"]
    for a, b, lab in PAIRS:
        for key, tag in ((b, "전"), (a, "뒤")):
            c = S.get(key)
            if c is None:
                continue
            L.append(f"| {lab} ({tag}) | {c['wolf']['stuck_max_wolf']} | {E[key].get('noneat_rim_still_max', '—')} | "
                     f"{E[key].get('noneat_still_max', '—')} | {c['wolf']['inside_blocking']} |")
    # 9. 관측 범위
    O = agg.get("obs") or {}
    if O:
        L += ["", "## 9. 관측 범위 (R1b·R1b−F 칸, 기준 = 원래 R1b 의 R1 판정 세계 ∪ R1b 학습 세계)", "",
              "OUT·SUPPORT·SHIFT 정의는 `../PREREG.md` 2절 15. R3 세계는 청각 자르기를 풀어 J1 위반이 나오는 것이 정상이다.", "",
              "| 세계 · 정책 | OUT | SUPPORT | SHIFT | J1 위반 / 감지 표본 | [0,1] 밖 |", "|---|---|---|---|---|---|"]
        for key in [f"{v}|{p}" for v, p in CELLS if p in ep.OBS_POLICIES and v != "train_ref"]:
            o = O.get(key)
            if o is None:
                continue
            fg = o["flags"]
            L.append(f"| {_name(key)} | {', '.join(fg['out']) or '없음'} | {', '.join(fg['support']) or '없음'} | "
                     f"{', '.join(fg['shift']) or '없음'} | {o['j1']['viol']} / {o['j1']['seen']} | {o['out01']} |")
    # 10. R1b 가 얼었을 자리
    L += ["", "## 10. R1b 가 얼었을 자리에서 R1b−F 가 고른 것 (전 → 뒤)", "",
          "| 세계 | 결정 수 | R1b 가 FREEZE 를 골랐을 몫 | → GRAZE | → FLEE | → HIDE | 나머지 결정 같음 |", "|---|---|---|---|---|---|---|"]
    for key in ("r3_cd5|rlf", "r3|rlf", "base|rlf", "base_eat|rlf", "night|rlf", "night_eat|rlf"):
        c = S.get(key)
        if c is None or "cf" not in c:
            continue
        cf = c["cf"]
        az = cf["at_freeze"]
        L.append(f"| {VNAME[key.split('|')[0]]} | {cf['n_dec']} | {_pc(cf['freeze_share'])} | {_pc(az['graze'])} | {_pc(az['flee'])} | "
                 f"{_pc(az['hide'])} | {_pc(cf['same_elsewhere'], 2)} |")
    return "\n".join(L) + "\n"


def full_tables(agg: dict) -> str:
    """`../eval_pre.py` 의 전체 표(같은 정의)를 이 측정의 모든 칸으로 낸다."""
    ep.VNAME = dict(ep.VNAME, **VNAME)
    ep.EXTRA_CELLS = tuple(c for c in CELLS if c[0] != "r3")
    return ep.tables(agg, "R3 재학습 전 측정 — 늑대 먹는 시간 5 → 38스텝 전후, 전체 표 (`../eval_pre.py` 정의)")


def aggregate(results, names) -> dict:
    agg = ep.aggregate(results, names)
    cells = {}
    for r in results:
        cells.setdefault(f"{r['variant']}|{r['policy']}", []).append(r)
    agg["eat"] = {k: eat_summary(v) for k, v in cells.items()}
    agg["compare"] = dict(agg["compare"], **compare(agg["summary"]))
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "smoke", "tables"))
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    import os

    os.chdir(ROOT)
    _patch()
    from env_v2.world import obs_names

    names = list(obs_names(load_variant("r3")))
    if a.cmd == "tables":
        agg = json.loads((OUT_DIR / "eat38.json").read_text(encoding="utf-8"))
        agg["raw"] = json.loads((OUT_DIR / "eat38_raw.json").read_text(encoding="utf-8"))
        (OUT_DIR / "tables.md").write_text(tables(agg), encoding="utf-8")
        (OUT_DIR / "tables_full.md").write_text(full_tables(agg), encoding="utf-8")
        return
    seeds, steps = (ep.SMOKE_SEEDS, 200) if a.cmd == "smoke" else (ep.SEEDS, ep.STEPS)
    ep._check_seeds(seeds)
    jobs = [(v, p, s, steps) for v, p in CELLS for s in seeds]
    t0 = time.time()
    res = _map(jobs, a.workers)
    agg = aggregate(res, names)
    agg["meta"] = dict(model=ep.MODEL, seeds=seeds, steps=steps, variants=VARIANTS, cells=[list(c) for c in CELLS],
                       gamma=ep.GAMMA, tail=ep.TAIL, wall_sec=time.time() - t0, obs_names=names,
                       spy_fail=int(sum(r["spy_fail"] for r in res)),
                       eat_steps_per_catch=EAT_STEPS_PER_CATCH)
    agg.pop("_hist", None)
    if a.cmd == "smoke":
        agg["raw"] = [dict({k: v for k, v in r.items() if k not in ("obs", "bouts")}) for r in res]
        print(tables(agg))
        return
    agg["repro"] = repro(agg["summary"])
    drop = ("lengths", "len_sw", "len_death", "d_all", "d_purs")
    agg["raw"] = [dict({k: v for k, v in r.items() if k not in ("obs", "bouts")},
                       bouts={k: v for k, v in r["bouts"].items() if k not in drop}) for r in res]
    (OUT_DIR / "eat38.json").write_text(json.dumps({k: v for k, v in agg.items() if k != "raw"}, ensure_ascii=False, indent=1,
                                                   default=ep._json_default), encoding="utf-8")
    (OUT_DIR / "eat38_raw.json").write_text(json.dumps(agg["raw"], ensure_ascii=False, separators=(",", ":"),
                                                       default=ep._json_default), encoding="utf-8")
    (OUT_DIR / "tables.md").write_text(tables(agg), encoding="utf-8")
    (OUT_DIR / "tables_full.md").write_text(full_tables(agg), encoding="utf-8")
    print(f"wrote eat38.json in {time.time() - t0:.0f}s; repro " + json.dumps(agg["repro"], ensure_ascii=False))


if __name__ == "__main__":
    main()

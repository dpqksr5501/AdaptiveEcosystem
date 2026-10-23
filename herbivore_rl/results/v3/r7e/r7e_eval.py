"""v3 R7e — 이미 학습한 R7 두뇌를 '쫓김 사건' 단위 규칙으로 다시 점검·고르고 판정하는 도구 (사전 등록 results/v3/r7e/PREREG.md — 학습 없음).

사람 결정 10-24 "'쫓김 사건' 단위로 셈"(LIVE_GATE.md 변경 기록 (7), 셈 4d33c18 · 검토 71e7612)을 R7 두뇌에 적용한다. R7 도구(results/v3/r7/r7_eval.py —
두뇌 → 세계 키·세계 하나·워커·막음 통계·A5)와 R6 도구(r6_eval — 탐침·길 기록·길 지킴)를 불러 쓰고 R7e 에서 바뀐 곳만 여기 둔다(R6·R7 도구는 고치지 않는다):
  - 두뇌: R7 본 학습 결과 그대로(ckpt/v3/v3_r7_g995_s{0,1,2}_20m(.zip·_2m·_5m), 대조 v3_r7off_g995_s0_20m) — 파일 sha1 이 R7 이 잰 것과 같아야 받는다(R7_SHA1).
  - 시드: 새 점검 38220~38239 · 새 고르기 38200~38219 · 판정 N 38000~38099 · G 38000~38039 · 끼임 38000~38004. R7 이 이미 쓴(값을 본) 점검 38120~38139 ·
    고르기 38100~38119 는 어느 쓰임에도 없다. 판정 시드는 judge 명령으로만 돈다(run 은 점검·고르기·스모크 쓰임만 받는다).
  - 숨음·잡힘 비율 = 쫓김 사건 단위(live.episode_pair — LIVE_GATE 5-1 '쫓김 사건', env_v2/world.py flight.episode), GR 자리에 GE(1000 산 사슴-스텝당 사건 시작 —
    live.flight_rate_pair 'episodes'). 옛 도망 단위 숨음·잡힘 비율과 GR 은 보고만.
  - 점검 (c): 사건 숨음 비율 짝 t > −2 · 사건 잡힘 비율 짝 t < +2 · 잡힌 몫 짝 t < +2 · GF 짝 t < +2 · GE 짝 t < +2. (a)·(b)·결함은 R7 셈 그대로(r7_eval.early_check).
  - 고르기 자격: GF·GE 짝 t < +2. 순서: 사건 숨음 비율(쫓긴 사건 가운데, 전체 합) 큰 쪽 → 잡힌 몫 → 굶은 몫 → 모델 시드.
  - 판정: 1차 P1 = live.gate_live 의 P1_N_hide(사건 숨음 비율 짝 차이 > 0 ∧ t ≥ +t_crit(n₁ − 1) — n₁ 100 이면 +1.984), 지킴 18 칸 = R7 지킴에서 GR_reflee 자리에
    GE_episode_starts(GH 는 사건 잡힘 비율). GR·도망 단위 숨음·잡힘 비율·쫓긴 시간은 보고만.
판정 실행기는 R7 과 같은 파이썬 거울(live._world_multi → run_mirror.run_world — 쫓김 사건을 센다. C++ 평가기는 아직 사건도 판 5 도 못 센다).

    # herbivore_rl/ 에서 (PYTHONUTF8=1)
    python results/v3/r7e/r7e_eval.py checks --control                                    # ① 2M·5M 점검 (38220~38239) → logs/check_*.txt · logs/early_main.json
    python results/v3/r7e/r7e_eval.py select --models ckpt/v3/v3_r7_g995_s0_20m.zip ckpt/v3/v3_r7_g995_s1_20m.zip ckpt/v3/v3_r7_g995_s2_20m.zip  # ② (제외 시드는 뺀다)
    python results/v3/r7e/r7e_eval.py judge --model ckpt/v3/v3_r7_g995_s<고른 시드>_20m.zip --off ckpt/v3/v3_r7off_g995_s0_20m.zip              # ③
    # 도구 확인(판정 아님 — 스모크 시드 32080~32099 안, 짧은 길이, 임시 폴더. R7 학습 두뇌 대신 시작 두뇌 route0m5·obs21zero_m6 을 쓴다 — STATUS.md 3절)
    python results/v3/r7e/r7e_eval.py checks --control --ckpt-dir <임시>/ck --smoke 32080-32082 --smoke-steps 300 --out-dir <임시>/ck_out
    python results/v3/r7e/r7e_eval.py select --models route0m5 --smoke 32080-32082 --smoke-steps 300 --out-dir <임시>/sel
    python results/v3/r7e/r7e_eval.py judge --model route0m5 --off obs21zero_m6 --smoke 32080-32082 --smoke-steps 300 --out-dir <임시>/judge
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
R7_DIR = ROOT / "results" / "v3" / "r7"
for _p in (ROOT, R7_DIR, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import r7_eval as R7  # noqa: E402  ← r6_eval(env.torch_init·경로 adapt·mirror·r4·wild2·live)을 먼저 준비한다

R6, lv, re_, ad = R7.R6, R7.lv, R7.re_, R7.ad

OUT = HERE.parent / "runs"                          # git 밖 (herbivore_rl/.gitignore runs/)
LOGS = HERE.parent / "logs"
BRAINS = HERE.parent / "brains"
CK = R7.CK
LAM, FLIGHT_COST, GAMMA = R7.LAM, R7.FLIGHT_COST, R7.GAMMA
REGIONS = R7.REGIONS
R7_CONTROL = CK / "v3_r7off_g995_s0_20m.zip"        # R7 대조 '길 끔' 마지막 모델 (판 6 — 보고만)

# 쓰임 → (시드 처음, 끝, 길이, 세계) — 사전 등록 2절. 판정 세 칸은 R7 사전 등록 그대로(아무 두뇌로도 돌린 적 없음)
USES = {
    "judge_n": (38000, 38099, 1800, "N"),
    "judge_g": (38000, 38039, 3600, "G"),
    "stuck": (38000, 38004, 3600, "stuck"),
    "select": (38200, 38219, 1800, "N"),
    "check": (38220, 38239, 1800, "N"),
}
JUDGE_USES = ("judge_n", "judge_g", "stuck")         # judge 명령으로만 돈다 (run 은 받지 않는다)
R7_USED = ((38100, 38119), (38120, 38139))          # R7 이 이미 쓴 고르기·점검 시드 — 값을 봤으므로 R7e 쓰임에 없다
SMOKE_SEEDS = R7.SMOKE_SEEDS                        # 도구 확인 (32080~32099)

# R7 본 학습 산출 (파일 sha1 앞 12 — R7 점검·고르기 판 메타 model_sha1 과 같다. 다르면 다른 두뇌라 받지 않는다)
R7_SHA1 = {
    "v3_r7_g995_s0_20m": "55b867f76a8f", "v3_r7_g995_s0_20m_2m": "db009d32ac30", "v3_r7_g995_s0_20m_5m": "d071d1ecfb21",
    "v3_r7_g995_s1_20m": "12c8d90cf44c", "v3_r7_g995_s1_20m_2m": "f8e0597c0849", "v3_r7_g995_s1_20m_5m": "c99372a1b2e3",
    "v3_r7_g995_s2_20m": "2688c4afddb7", "v3_r7_g995_s2_20m_2m": "6af7bed76e51", "v3_r7_g995_s2_20m_5m": "9d2d44e93c2c",
    "v3_r7off_g995_s0_20m": "bdc05f6cfb26", "v3_r7off_g995_s0_20m_2m": "c6858848839f", "v3_r7off_g995_s0_20m_5m": "ed0475e9974d",
}

# 본 학습 2M·5M 점검 규칙 (사전 등록 4절 — R7 5-1 그대로, (c) 의 숨음·잡힘 비율은 사건 단위, GR → GE)
EARLY = dict(
    pi_move=0.05,          # (a) SHELTER 가 열린 길 결정에서 학습 표본 확률 π′(SHELTER) 평균이 route0 값에서 이보다 크게 움직임 (|차이| > 0.05) — R7 그대로
    ev_min=0.0,            # (b) 도주 스텝 가치망 설명 분산(λ 0.98 λ-수익 목표) > 0 — R7 그대로
    t_hide=-2.0,           # (c) 사건 숨음 비율 짝 t > −2
    t_caught_ratio=2.0,    # (c) 사건 잡힘 비율(쫓긴 사건 가운데) 짝 t < +2
    t_caught=2.0,          # (c) 잡힌 몫(사슴 가운데) 짝 t < +2 — R7 그대로
    t_gf=2.0,              # (c) GF 1000 산 사슴-스텝당 시작한 도망 짝 t < +2 — R7 그대로
    t_ge=2.0,              # (c) GE 1000 산 사슴-스텝당 시작한 쫓김 사건 짝 t < +2 — R7 의 GR 자리 (문턱은 GR 의 +2.0 그대로)
)
SELECT = dict(t_gf=2.0, t_ge=2.0)                   # 고르기 자격 (사전 등록 5절 — R7 6절의 GR 자리에 GE)
CHECK_AT = R7.CHECK_AT                              # (2, 5) 백만 스텝
FINAL_RE = R7.FINAL_RE                              # 고르기 후보 = R7 본 학습의 마지막 모델만

# 지킴 18 칸 (사전 등록 3-2 — R7 지킴에서 GR_reflee 자리에 GE_episode_starts. GH 는 이제 사건 잡힘 비율)
GUARDS = ("GH_flight_caught", "GN_caught", "GN_starved", "GN_alive", "GF_flight_starts", "GE_episode_starts", "GV_flee_time", "GC_flight_unsafe",
          "GT_flight_time", "GTr_truncated", "GG_caught", "GG_starved", "GG_alive", "GG_chase", "G4_catch_in_shelter", "G5_stuck", "G6_no_exploit",
          "A5_export")
REPORT_KEYS = ("REPORT_N_flight_hide", "REPORT_N_flight_caught", "GR_reflee")   # 판정 표에 '보고만' 으로 적는 칸 (옛 도망 단위·GR)
RATIO_KEYS = tuple(R6.RATIO_KEYS) + ("REPORT_N_flight_hide", "REPORT_N_flight_caught")

_ok_t = R6._ok_t
_q = R7._q
load, save = R6.load, R6.save


# --------------------------------------------------------------------- #
# 쓰임·두뇌
# --------------------------------------------------------------------- #

def use_plan(use: str, seeds=None, steps=None) -> dict:
    """쓰임 → dict(use, seeds, steps, world). smoke 만 --seeds·--steps 를 받고(SMOKE_SEEDS 안), 그 밖의 쓰임은 사전 등록 값만 쓴다."""
    if use == "smoke":
        if not seeds or not steps:
            raise SystemExit("--use smoke 는 --seeds 와 --steps 를 준다")
        lo, hi = SMOKE_SEEDS
        bad = [s for s in seeds if not lo <= int(s) <= hi]
        if bad:
            raise SystemExit(f"스모크 시드 {bad[:5]} 는 {lo}~{hi} 밖이다 (R7e 시드는 쓰임으로만 쓴다)")
        return dict(use=use, seeds=[int(s) for s in seeds], steps=int(steps), world="N")
    if use not in USES:
        raise SystemExit(f"--use {use} 는 {', '.join(list(USES) + ['smoke'])} 가운데 하나다")
    if seeds or steps:
        raise SystemExit(f"--use {use} 의 시드·길이는 사전 등록 값이다 (--seeds·--steps 는 smoke 만)")
    lo, hi, n, world = USES[use]
    return dict(use=use, seeds=list(range(lo, hi + 1)), steps=int(n), world=world)


def smoke_plan(use: str, seeds, steps: int) -> dict:
    """도구 확인용(판정 아님): 쓰임 use 의 세계(N·G·끼임)를 스모크 시드·길이로."""
    p = use_plan("smoke", seeds, steps)
    p.update(use=f"smoke_{use}", world=USES[use][3])
    return p


def sha1_12(path: Path) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:12]


def require_r7_model(path: Path) -> str:
    """R7 본 학습 산출(마지막·2M·5M·대조)이면 파일 sha1 이 R7 이 잰 것(R7_SHA1)과 같은지 본다 — 다르면 멈춘다. 이름이 R7 산출이 아니면 멈춘다."""
    stem = Path(path).stem
    want = R7_SHA1.get(stem)
    if want is None:
        raise SystemExit(f"{path}: R7 본 학습 산출(v3_r7_g995_s<0~2>_20m[_2m|_5m] · v3_r7off_g995_s0_20m[_2m|_5m])이 아니다 (사전 등록 1-1)")
    got = sha1_12(path)
    if got != want:
        raise SystemExit(f"{path}: sha1 {got} 이 R7 이 잰 두뇌({want})와 다르다 — 다른 파일이다 (사전 등록 1-1)")
    return got


def code_tags() -> dict:
    """셈 길 지문: 세계(live.eval_code_tag('python') — env_v2/world.py 의 쫓김 사건 셈 포함), R7·R6 도구와 이 도구 파일 sha256 앞 16."""
    t = R7.code_tags()
    return dict(world=t["world"], tool_r7=t["tool"], tool_r6=t["tool_r6"], tool_r7e=hashlib.sha256(HERE.read_bytes()).hexdigest()[:16])


def need_episode(res: dict, what: str = "") -> None:
    """판의 모든 세계 도망 기록에 쫓김 사건(flight.episode)이 있어야 한다 — 없으면 멈춘다(옛 판·사건을 못 세는 실행기)."""
    bad = [(w.get("seed"), w.get("region")) for w in res.get("worlds", []) if not lv.has_episode(lv.flight_of(w))]
    if bad:
        raise ValueError(f"{what} 판의 세계 {bad[:3]} 에 쫓김 사건(flight.episode)이 없다 — 지금 파이썬 실행기로 다시 돌린다")


def same_code(*runs: dict) -> None:
    """견주는 판들이 같은 세계 셈 길(meta.code.world — env_v2·policies·거울 파일 지문)로 잰 것인가. 다르면 멈춘다(돌리는 사이 세계 코드가 바뀌면 짝이 아니다)."""
    tags = {str(((r or {}).get("meta") or {}).get("code", {}).get("world")) for r in runs if r is not None}
    if len(tags) != 1:
        raise ValueError(f"견주는 판의 세계 셈 길 지문이 다르다 {sorted(tags)} — 같은 코드로 다시 돌린다 (판 파일을 지우고 이어 돌리기)")


def run_model(info: dict, text: str, plan: dict, workers: int, probe: bool = False, name: str = "") -> dict:
    """한 두뇌 · 한 쓰임 → {meta, worlds} (끼임은 {meta, summary}). 세계·워커는 R7 도구 그대로(r7_eval.make_items·run_items — 막음 통계 gate·탐침)."""
    import stuck_check

    spec = R7.resolve_model(text)
    items = R7.make_items(info, spec, plan, probe, tag=spec["label"])
    t0 = time.perf_counter()
    rows = R7.run_items(items, workers, name or spec["label"])
    meta = dict(prereg="r7e", name=name, use=plan["use"], world=plan["world"], seeds=plan["seeds"], steps=plan["steps"], regions=sorted(info["regions"]),
                model=text, model_path=lv.path_text(spec["path"]), model_sha1=sha1_12(spec["path"]), obs=spec["obs"], mask=spec["mask"], sets=spec["sets"],
                probe=bool(probe), snapshot=R6.SNAPSHOT.name, code=code_tags(), wall_s=round(time.perf_counter() - t0, 1), workers=int(workers))
    if plan["world"] == "stuck":
        return dict(meta=meta, summary=stuck_check.summarize([r for _, r in rows]))
    res = dict(meta=meta, worlds=[r for _, r in rows])
    need_episode(res, name)
    return res


def same_meta(path: Path, want: dict) -> bool:
    """이미 있는 판 파일이 같은 두뇌(sha1)·쓰임·시드·길이·세계 키·탐침·셈 길로 잰 것인가 (이어 돌리기)."""
    if not path.exists():
        return False
    m = load(path).get("meta") or {}
    return m.get("prereg") == "r7e" and all(m.get(k) == want.get(k) for k in ("use", "seeds", "steps", "model_sha1", "sets", "probe", "code"))


def ensure_run(info, text, use, workers, name, out_dir=OUT, probe=False, plan=None) -> dict:
    """판 파일이 같은 조건으로 이미 있으면 읽고, 없으면 돌려 쓴다."""
    plan = plan or use_plan(use)
    spec = R7.resolve_model(text)
    path = Path(out_dir) / f"{name}.json"
    want = dict(use=plan["use"], seeds=plan["seeds"], steps=plan["steps"], model_sha1=sha1_12(spec["path"]), sets=spec["sets"], probe=bool(probe),
                code=code_tags())
    if same_meta(path, want):
        print(f"  {name}: 같은 조건의 판이 있다 — 다시 쓴다 ({lv.path_text(path)})", flush=True)
        res = load(path)
        if "worlds" in res:
            need_episode(res, name)
        return res
    print(f"  {name}: {text} (판 {spec['mask']}) · {plan['use']} 시드 {plan['seeds'][0]}~{plan['seeds'][-1]} × 지역 {len(info['regions'])} × {plan['steps']} 스텝"
          f"{' · 탐침' if probe else ''}", flush=True)
    res = run_model(info, text, plan, workers, probe, name)
    save(res, path)
    return res


def prepare_info(out: Path = OUT) -> dict:
    """스냅숏 → <out>/world (R6·R7 과 같은 세계 — live.prepare)."""
    return R7.prepare_info(out)


# --------------------------------------------------------------------- #
# 사건 단위 셈 (live 의 관문 셈 그대로)
# --------------------------------------------------------------------- #

def ep_pair(cand: dict, cur: dict, key: str = "hide") -> dict:
    """사건 숨음 비율(key 'hide')·사건 잡힘 비율('caught') 짝 (live.episode_pair — 관문 P1·GH 와 같은 셈), 후보 − 기준."""
    return lv.episode_pair(cand, cur, key)


def ge_pair(cand: dict, cur: dict) -> dict:
    """GE 짝: 시드마다 1000 산 사슴-스텝당 시작한 쫓김 사건(지역 셋 합), 후보 − 기준 (live.flight_rate_pair 'episodes' — 관문 GE 와 같은 셈)."""
    return lv.flight_rate_pair(cand, cur, "episodes")


gf_pair, gr_pair, gate_pooled, none_seed = R7.gf_pair, R7.gr_pair, R7.gate_pooled, R7.none_seed


def ep_select_key(res: dict, model_seed: int) -> tuple:
    """고르기 순서: 사건 숨음 비율(쫓긴 사건 가운데, 전체 합) 큰 쪽 → 잡힌 몫 작은 쪽 → 굶은 몫 작은 쪽 → 모델 시드 작은 쪽."""
    f, p = lv.flight_pooled(res), re_.pooled(res)
    h = f["ep_hide_share"]
    return (-(h if h == h else -1.0), p["caught"], p["starved"], int(model_seed))


# --------------------------------------------------------------------- #
# 본 학습 2M·5M 점검 (사전 등록 4절)
# --------------------------------------------------------------------- #

def early_check(run: dict, base: dict, lam: float = LAM) -> dict:
    """점검 하나 (사전 등록 4-1): run = 점검 체크포인트 판(판 5 R7 · 판 6 대조), base = route0 판 (같은 점검 시드, 둘 다 --probe).
    (a)·(b)·결함·R5 보고 칸은 R7 셈 그대로(r7_eval.early_check). (c) = 사건 숨음 비율 짝 t > −2 · 사건 잡힘 비율 짝 t < +2 · 잡힌 몫 짝 t < +2 · GF 짝 t < +2 ·
    GE 짝 t < +2. R7 의 옛 (c)(도망 단위 숨음·잡힘 비율·GR)는 c_r7 에 보고만 남긴다."""
    need_episode(run, "점검")
    need_episode(base, "기준")
    same_code(run, base)
    r = R7.early_check(run, base, lam)
    E = EARLY
    hide, cr = ep_pair(run, base, "hide"), ep_pair(run, base, "caught")
    gn = re_.paired(re_.per_seed(run, "caught"), re_.per_seed(base, "caught"))
    gf, ge = gf_pair(run, base), ge_pair(run, base)
    parts = dict(hide=dict(hide, ok=_ok_t(hide, hide["t"] > E["t_hide"])), caught_ratio=dict(cr, ok=_ok_t(cr, cr["t"] < E["t_caught_ratio"])),
                 caught=dict(gn, ok=_ok_t(gn, gn["t"] < E["t_caught"])), gf=dict(gf, ok=_ok_t(gf, gf["t"] < E["t_gf"])),
                 ge=dict(ge, ok=_ok_t(ge, ge["t"] < E["t_ge"])))
    c = dict(ok=all(v["ok"] for v in parts.values()), parts=parts,
             rule=(f"사건 숨음 비율 짝 t > {E['t_hide']:+g} · 사건 잡힘 비율 짝 t < +{E['t_caught_ratio']:g} · 잡힌 몫 짝 t < +{E['t_caught']:g} · "
                   f"GF 짝 t < +{E['t_gf']:g} · GE 짝 t < +{E['t_ge']:g} (route0 대비)"))
    old = r.pop("c")
    fr, fb = lv.flight_pooled(run), lv.flight_pooled(base)
    r.update(c=c, c_r7=dict(old, note="보고만 — R7 의 옛 (c)(도망 단위 숨음·잡힘 비율·GR). 제외에 쓰지 않는다"),
             passed=bool((r["a"]["ok"] is not False) and r["b"]["ok"] and c["ok"] and not r["defect"]["hit"]),
             ep=dict(run={k: fr[k] for k in ("ep_started", "ep_chased", "ep_hidden", "ep_caught", "ep_hide_share", "ep_caught_share", "ep_per_1k",
                                             "ep_joined_cover", "ep_joined_other", "flights_per_episode")},
                     base={k: fb[k] for k in ("ep_started", "ep_chased", "ep_hidden", "ep_caught", "ep_hide_share", "ep_caught_share", "ep_per_1k",
                                              "ep_joined_cover", "ep_joined_other", "flights_per_episode")}))
    return r


def fmt_check(tag: str, r: dict) -> str:
    def yn(x):
        return "—" if x is None else ("통과" if x else "걸림")

    a, b, c = r["a"], r["b"], r["c"]
    lines = [f"{tag}: {'통과' if r['passed'] else '못 넘음'}" + (" · 결함" if r["defect"]["hit"] else "")]
    if r["route"]:
        lines.append(f"  (a) {yn(a['ok'])}: π′(SHELTER) {a['pe']:.4f} (route0 {a['pe_start']:.4f}, 차이 {a['moved']:+.4f}), π {a['pi']:.4f}, 두 칸 결정 {a['two_n']}")
    else:
        lines.append(f"  (a) —: {a['rule']}")
    lines.append(f"  (b) {yn(b['ok'])}: 도주 스텝 설명 분산(λ {b['lam']:g}) {b['ev']:+.4f} (route0 {b['ev_start']:+.4f}, 표본 {b['n']}) · 보고만 몬테카를로 "
                 f"{b['ev_mc']:+.4f} (route0 {b['ev_mc_start']:+.4f})")
    for k, nm in (("hide", "사건 숨음 비율"), ("caught_ratio", "사건 잡힘 비율"), ("caught", "잡힌 몫"), ("gf", "GF 1000 산 사슴-스텝당 시작한 도망"),
                  ("ge", "GE 1000 산 사슴-스텝당 시작한 쫓김 사건")):
        q = c["parts"][k]
        lines.append(f"  (c) {nm} {yn(q['ok'])}: {q['a']:.4f} 대 route0 {q['b']:.4f} (차이 {q['diff']:+.4f}, t {lv.tfmt(q['t'])}, 시드 {q['n']})")
    d = r["defect"]
    lines.append(f"  결함 {'있음' if d['hit'] else '없음'}: 얼기·잠 몫 {d['freeze_sleep']:.4g}, COVER 확률 최대 {d['cover_max']:.3g}, 마스크 밖 SHELTER {d['bad_shelter']}, "
                 f"반사 밖 두뇌 FLEE {d['gate_flee']} (덮기 밖 결정 {r['gate']['free_decisions']:,})")
    e, eb = r["ep"]["run"], r["ep"]["base"]
    lines.append(f"  사건 (전체 합): 사건 시작 {e['ep_started']} (route0 {eb['ep_started']}) · 쫓긴 사건 {e['ep_chased']} ({eb['ep_chased']}) · 숨음 {e['ep_hidden']} "
                 f"({eb['ep_hidden']}) · 잡힘 {e['ep_caught']} ({eb['ep_caught']}) · 이어진 도망 은신처 뒤 {e['ep_joined_cover']} ({eb['ep_joined_cover']}) · "
                 f"그 밖 뒤 {e['ep_joined_other']} ({eb['ep_joined_other']}) · 도망 ÷ 사건 {e['flights_per_episode']:.3f} ({eb['flights_per_episode']:.3f})")
    if r["route_stats"]:
        s = r["route_stats"]
        lines.append(f"  길: 결정 {s['decisions']} · SHELTER 고름 {s['picked_shelter']} (몫 {s['shelter_share']:.4f}) · 다시 고름 {s['redecide_feas']} · 무효 {s['invalid_shelter']}")
    old = r["c_r7"]["parts"]
    bits = []
    for k, nm, fmt in (("hide", "도망 단위 숨음 비율", ".4f"), ("caught_ratio", "도망 단위 잡힘 비율", ".4f"), ("gr", "GR 5 초 안 다시 도망(시드당)", ".1f")):
        q = old.get(k) or {}
        bits.append(f"{nm} " + (f"{q['a']:{fmt}} 대 {q['b']:{fmt}} (t {lv.tfmt(q['t'])})" if "diff" in q else "—"))
    lines.append("  보고만 (R7 옛 (c) 칸 — 제외에 쓰지 않는다): " + " · ".join(bits))
    lines.append(f"  보고만: 두뇌 스스로 뛴 도망(길 none) {'—' if r['none'] is None else r['none']} (route0 {r['none_base']}) · "
                 + " · ".join(f"{k} {x:.4f} (route0 {y:.4f}{' — R5 규칙이면 걸림' if hit else ''})" for k, (x, y, hit) in r["report_r5"].items()))
    return "\n".join(lines)


def main_check_rules(checks: dict, at) -> dict:
    """점검 모음 (사전 등록 4-2 — R7 5-2 그대로, (c) 칸만 사건 단위·GE). checks = {(시드 이름, k): early_check} (대조 'off' 는 넣지 않는다).
    제외 = (c)(사건 숨음 비율·사건 잡힘 비율·잡힌 몫·GF·GE) 가 2M·5M 가운데 한 번이라도 걸린 시드. 멈춤 = 결함 · 마지막 점검에서 모든 시드 (a) 안 움직임 ·
    남은 시드 모두 (b) 걸림 · 모든 시드 제외."""
    seeds = sorted({s for s, _ in checks if s != "off"})
    out: dict = dict(excluded={}, stop=False, why=[], defect=False)
    for s in seeds:
        bad = []
        for (ss, k), v in sorted(checks.items(), key=lambda kv: kv[0][1]):
            if ss == s and not v["c"]["ok"]:
                parts = [nm for nm, q in v["c"]["parts"].items() if q["ok"] is False]
                bad.append(f"{k}M (c) {'·'.join(parts)}")
        if bad:
            out["excluded"][s] = "(c) 걸림: " + ", ".join(bad)
    if any(v["defect"]["hit"] for v in checks.values()):
        out.update(stop=True, defect=True)
        out["why"].append("결함(얼기·잠·COVER·마스크 밖 SHELTER·반사 밖 두뇌 FLEE) — 멈추고 사람에게 알린다 (학습한 두뇌라 고치지 않고 R7e 실패로 보고)")
    k_last = max(at)
    last = {s: checks.get((s, k_last)) for s in seeds}
    if last and all(v is not None for v in last.values()):
        if not any(v["a"]["ok"] for v in last.values()):
            out["stop"] = True
            out["why"].append(f"{k_last}M 에서 모든 시드가 (a) 에서 움직이지 않았다 — '못 배움' (R7e 실패로 보고)")
        live = [s for s in seeds if s not in out["excluded"]]
        if live and all(not last[s]["b"]["ok"] for s in live):
            out["stop"] = True
            out["why"].append(f"{k_last}M 에서 남은 시드 모두 (b) 걸림 — 멈추고 사람에게 묻는다")
    if seeds and len(out["excluded"]) == len(seeds):
        out["stop"] = True
        out["why"].append("모든 R7 시드가 (c) 로 빠졌다 — R7e 실패로 보고 (고르기·판정을 하지 않는다)")
    return out


def ckpt_name(nm: str, k: int) -> str:
    """점검 이름('s0'·'s1'·'s2'·'off') · k → 체크포인트 파일 이름 (R7 launch_train.ps1 의 실행 이름 + _<k>m)."""
    run = "v3_r7off_g995_s0_20m" if nm == "off" else f"v3_r7_g995_{nm}_20m"
    return f"{run}_{k}m.zip"


def run_checks(seeds, control: bool, at, workers: int, ckpt_dir: Path, plan: dict | None, logs: Path, runs_dir: Path, verify_sha: bool = True) -> dict:
    """2M·5M 점검을 모두 돌린다 (사전 등록 4절 — 학습은 끝났으므로 기다리지 않는다. 체크포인트가 없거나 sha1 이 R7 과 다르면 멈춘다).
    기준 판 runs/early_base(route0, 탐침) → 체크포인트마다 runs/early_<이름>_<k>m → logs/check_<이름>_<k>m.txt, 모음 logs/early_main.json."""
    names = [f"s{s}" for s in seeds] + (["off"] if control else [])
    paths = {}
    for k in at:
        for nm in names:
            ck = Path(ckpt_dir) / ckpt_name(nm, k)
            if not ck.exists():
                raise SystemExit(f"체크포인트 {ck} 가 없다 — R7 본 학습 산출을 그대로 쓴다 (사전 등록 1-1)")
            if verify_sha:
                require_r7_model(ck)
            paths[(nm, k)] = ck
    info = prepare_info(runs_dir)
    base = ensure_run(info, "route0", "check", workers, "early_base", runs_dir, probe=True, plan=plan)
    checks, rows = {}, {}
    logs.mkdir(parents=True, exist_ok=True)

    def write(final: bool):
        summ = main_check_rules({kk: v for kk, v in checks.items() if kk[0] != "off"}, sorted({kk[1] for kk in checks}) if not final else list(at))
        lv.atomic_write_json(logs / "early_main.json", lv.jsonable(dict(rows=rows, rules=summ, lam=LAM, flight_cost=FLIGHT_COST, smoke=plan is not None,
                                                                         seeds=(plan or use_plan("check"))["seeds"],
                                                                         control_note="대조 '길 끔' 줄은 보고만 (제외·멈춤에 쓰지 않는다)")))
        return summ

    for k in at:
        for nm in names:
            ck, tag = paths[(nm, k)], f"{nm}_{k}m"
            t0 = time.time()
            res = ensure_run(info, str(ck), "check", workers, f"early_{tag}", runs_dir, probe=True, plan=plan)
            r = early_check(res, base, LAM)
            text = fmt_check(f"{tag} ({ck.name}, {time.time() - t0:.0f}초)", r)
            (logs / f"check_{tag}.txt").write_text(text + "\n", encoding="utf-8")
            print(text, flush=True)
            checks[(nm, k)] = r
            cp = r["c"]["parts"]
            rows[tag] = dict(passed=r["passed"], a=r["a"].get("ok"), b=r["b"]["ok"], c=r["c"]["ok"], defect=r["defect"]["hit"], model_sha1=res["meta"]["model_sha1"],
                             pe_shelter=r["a"].get("pe"), ev=r["b"]["ev"], hide_diff=cp["hide"]["diff"], hide_t=cp["hide"]["t"],
                             caught_ratio_t=cp["caught_ratio"]["t"], caught_t=cp["caught"]["t"], gf_diff=cp["gf"]["diff"], gf_t=cp["gf"]["t"],
                             ge_diff=cp["ge"]["diff"], ge_t=cp["ge"]["t"], gate_flee=r["defect"]["gate_flee"], none=r["none"],
                             report_flight_hide_t=(r["c_r7"]["parts"].get("hide") or {}).get("t"), report_gr_diff=(r["c_r7"]["parts"].get("gr") or {}).get("diff"),
                             report_gr_t=(r["c_r7"]["parts"].get("gr") or {}).get("t"))
            write(False)
    summ = write(True)
    print(f"제외 시드: {summ['excluded'] or '없음'} · 멈춤: {'예 — ' + ' / '.join(summ['why']) if summ['stop'] else '아니오'}", flush=True)
    return summ


# --------------------------------------------------------------------- #
# 고르기 (사전 등록 5절)
# --------------------------------------------------------------------- #

def select_guard(models: list, early_main: Path | None = None) -> None:
    """사전 등록 5절 막기: 후보는 R7 본 학습의 마지막 모델(v3_r7_g995_s<s>_20m.zip, sha1 이 R7 과 같음)만, R7e 점검 기록(results/v3/r7e/logs/early_main.json —
    스모크 아님·멈춤 아님·그 시드의 2M·5M 줄 있음)이 있어야 하고 그 기록이 제외한 시드는 받지 않는다."""
    early_main = LOGS / "early_main.json" if early_main is None else Path(early_main)
    if not early_main.exists():
        raise SystemExit(f"{lv.path_text(early_main)} 이 없다 — R7e 2M·5M 점검(r7e_eval.py checks)을 먼저 끝낸다 (사전 등록 4·5절)")
    d = json.loads(early_main.read_text(encoding="utf-8"))
    if d.get("smoke"):
        raise SystemExit(f"{lv.path_text(early_main)} 은 스모크 기록이다 — R7e 점검 기록이 아니다")
    if d.get("seeds") != use_plan("check")["seeds"]:
        raise SystemExit(f"{lv.path_text(early_main)} 의 점검 시드가 R7e 점검 시드(38220~38239)가 아니다")
    rules, rows = d.get("rules") or {}, d.get("rows") or {}
    if rules.get("stop"):
        raise SystemExit(f"R7e 점검이 멈춤이다 — {' / '.join(rules.get('why') or [])} (사전 등록 4-2 — 고르지 않는다)")
    excluded = rules.get("excluded") or {}
    for m in models:
        stem = Path(m).stem
        hit = re.match(FINAL_RE, stem)
        if not hit:
            raise SystemExit(f"고르기 후보 {m} 는 R7 본 학습의 마지막 모델(v3_r7_g995_s<시드>_20m.zip)이 아니다 (사전 등록 5절)")
        s = f"s{hit.group(1)}"
        if s in excluded:
            raise SystemExit(f"{m}: R7e 점검이 제외한 시드다 — {excluded[s]} ({lv.path_text(early_main)}, 사전 등록 4-2)")
        miss = [f"{k}M" for k in CHECK_AT if not rows.get(f"{s}_{k}m") or rows[f"{s}_{k}m"].get("missing")]
        if miss:
            raise SystemExit(f"{m}: R7e 점검 {', '.join(miss)} 기록이 없다 ({lv.path_text(early_main)}) — 점검을 마친 시드만 고른다 (사전 등록 4-2·5절)")
        p = Path(m)
        require_r7_model(p if p.is_absolute() else ROOT / p)


def select_rule(rows: list, base: dict) -> dict:
    """고르기 (사전 등록 5절). rows = [(모델 글, 모델 시드, 판)], base = route0 같은 고르기 시드 판.
    자격: GF 짝 t < +2.0 이고 GE 짝 t < +2.0 (route0 대비, 고르기 시드 20 짝). 자격 있는 모델 가운데 사건 숨음 비율(전체 합) 큰 쪽 → 잡힌 몫 작은 쪽 →
    굶은 몫 작은 쪽 → 모델 시드 작은 쪽(ep_select_key). 자격 있는 모델이 없으면 pick None(R7e 실패로 보고 — 판정하지 않는다). GR·도망 단위 숨음 비율은 보고만."""
    same_code(base, *[res for _, _, res in rows])
    out = []
    for m, seed, res in rows:
        gf, ge = gf_pair(res, base), ge_pair(res, base)
        gf_ok = _ok_t(gf, gf["t"] < SELECT["t_gf"])
        ge_ok = _ok_t(ge, ge["t"] < SELECT["t_ge"])
        out.append(dict(model=m, seed=int(seed), key=ep_select_key(res, seed), gf=gf, ge=ge, gr=gr_pair(res, base), hide=ep_pair(res, base, "hide"),
                        flight_hide=lv.flight_pooled(res)["hide_share"], ok=bool(gf_ok and ge_ok), gf_ok=gf_ok, ge_ok=ge_ok))
    ok = sorted([r for r in out if r["ok"]], key=lambda r: r["key"])
    return dict(rows=out, eligible=[r["model"] for r in ok], pick=ok[0]["model"] if ok else None, base_key=ep_select_key(base, -1),
                base_flight_hide=lv.flight_pooled(base)["hide_share"],
                rule=f"자격 GF 짝 t < +{SELECT['t_gf']:g} · GE 짝 t < +{SELECT['t_ge']:g} (route0 대비) → 사건 숨음 비율 큰 쪽 → 잡힌 몫 → 굶은 몫 → 모델 시드")


def picked_model(select_txt: Path | None = None) -> str | None:
    """results/v3/r7e/logs/select.txt 끝의 '고른 모델: …' (없거나 '없음' 이면 None)."""
    return R7.picked_model(LOGS / "select.txt" if select_txt is None else Path(select_txt))


def fmt_select(sel: dict) -> str:
    lines = ["| 모델 | 사건 숨음 비율(전체 합) | 잡힌 몫 | 굶은 몫 | GF 짝 차이 (t) | GE 짝 차이 (t) | 자격 | 보고만: 사건 숨음 비율 짝 차이 (t) · GR 시드당 (t) · "
             "도망 단위 숨음 비율 |", "|---|---|---|---|---|---|---|---|"]
    for r in sorted(sel["rows"], key=lambda r: r["key"]):
        k = r["key"]
        why = "예" if r["ok"] else "아니오 (" + " ".join(x for x, good in (("GF", r["gf_ok"]), ("GE", r["ge_ok"])) if not good) + ")"
        lines.append(f"| {r['model']} | {lv.pct(-k[0], 2)} | {k[1]:.4f} | {k[2]:.4f} | {_q(r['gf'], 1, '', 4)} | {_q(r['ge'], 1, '', 4)} | {why} | "
                     f"{_q(r['hide'], 100, '%p')} · {_q(r['gr'], 1, '', 1)} · {lv.pct(r['flight_hide'], 2)} |")
    bk = sel["base_key"]
    lines.append(f"| route0 (보고만) | {lv.pct(-bk[0], 2)} | {bk[1]:.4f} | {bk[2]:.4f} | | | | 도망 단위 숨음 비율 {lv.pct(sel['base_flight_hide'], 2)} |")
    lines += ["", f"규칙: {sel['rule']}", ""]
    lines.append(f"고른 모델: {sel['pick']}" if sel["pick"] else "고른 모델: 없음 — GF·GE 자격을 넘은 모델이 없다 (사전 등록 5절 — R7e 실패로 보고, 판정하지 않는다)")
    return "\n".join(lines)


# --------------------------------------------------------------------- #
# 판정 (사전 등록 3절)
# --------------------------------------------------------------------- #

def compare(cand: dict, other: dict, base: dict | None = None) -> dict:
    """보고만: 후보(R7) − 다른 판(같은 N 판정 시드). 사건 숨음·잡힘 비율·잡힌 몫·쫓긴 시간·GF·GE·GR(두 판 모두 길 기록이 있을 때만)·도망 단위 숨음 비율.
    base(route0)를 주면 그 판의 route0 대비 사건 숨음 비율·GF·GE·GR 도 적는다."""
    out = dict(hide=ep_pair(cand, other, "hide"), caught_ratio=ep_pair(cand, other, "caught"),
               caught=re_.paired(re_.per_seed(cand, "caught"), re_.per_seed(other, "caught")), chase=lv.flight_pair(cand, other),
               gf=gf_pair(cand, other), ge=ge_pair(cand, other), gr=gr_pair(cand, other), flight_hide=lv.hide_pair(cand, other, "hide"),
               flight=lv.flight_pooled(other), meta=other.get("meta"))
    if base is not None:
        out["vs_route0"] = dict(hide=ep_pair(other, base, "hide"), gf=gf_pair(other, base), ge=ge_pair(other, base), gr=gr_pair(other, base))
    return out


def verdict_of(c: dict, t1: float) -> tuple[str, str, list]:
    """판정 (사전 등록 3절): 1차 P1(c['P1_N_hide'] ok)이 아니면 기각, 지킴 18 칸(GUARDS) 가운데 ok 가 참이 아닌 칸이 하나라도 있으면(없는 칸 포함) 기각, 아니면 통과.
    보고만 칸(REPORT_KEYS — 옛 도망 단위·GR)은 보지 않는다. → (판정, 까닭, 걸린 지킴)."""
    p1 = c["P1_N_hide"]
    bad = [k for k in GUARDS if (c.get(k) or {}).get("ok") is not True]
    if p1.get("ok") is not True:
        return "기각", (f"1차 P1 실패: 사건 숨음 비율 R7 {lv.pct(p1.get('a', math.nan), 2)} 대 route0 {lv.pct(p1.get('b', math.nan), 2)} (짝 t "
                       f"{lv.tfmt(p1.get('t', math.nan))}, 문턱 +{t1:.3f}, 시드 {p1.get('n')}, 빠진 시드 {len(p1.get('dropped') or [])})"), bad
    if bad:
        return "기각", "지킴 실패: " + ", ".join(bad), bad
    return "통과", "1차 P1(사건 숨음 비율)·지킴 18 칸 모두 통과", bad


def judge(N: dict, G: dict, stuck: dict, a5: dict | None, others: dict | None = None) -> dict:
    """R7e 판정 (사전 등록 3절). N·G = {'candidate': R7 판, 'current': route0 판}, stuck = {'candidate', 'current'} 끼임 판, a5 = r7_eval.a5_check 결과(None 이면
    A5 를 통과로 두지 않는다), others = {'off': 대조 '길 끔', 'rule': '늘 SHELTER', 'r6': R6 고른 두뇌} (같은 N 판정 시드 — 보고만).
    1차 P1 = live.gate_live 의 P1_N_hide (쫓김 사건 단위 — 사건 숨음 비율 짝 차이 > 0 ∧ t ≥ +t_crit(n₁ − 1)), 지킴 18 칸(GUARDS) = GH(사건 잡힘 비율)·GN·GF·GE·
    GV·GC·GG·G4·G5·G6(live.gate_live) + GT·GTr(r6_eval.route_guards) + A5. 보고만 = 옛 도망 단위 숨음·잡힘 비율·GR·쫓긴 시간."""
    for w, d in (("N", N), ("G", G)):
        for who in ("candidate", "current"):
            need_episode(d[who], f"{w} {who}")
    same_code(N["candidate"], N["current"], G["candidate"], G["current"], stuck.get("candidate"), stuck.get("current"), *(others or {}).values())
    g = lv.gate_live(dict(N=N, G=G), stuck, None)
    if g.get("unit") != "episode":
        raise ValueError("live.gate_live 가 쫓김 사건 단위가 아니다 — 10-24 (7) 셈(4d33c18) 뒤의 live.py 를 쓴다")
    c = {k: v for k, v in g["criteria"].items() if k != "R_check"}
    rg = R6.route_guards(N["candidate"], N["current"])
    c["GT_flight_time"], c["GTr_truncated"] = rg["GT_flight_time"], rg["GTr_truncated"]
    gr = rg["GR_reflee"]
    c["GR_reflee"] = dict(gr, ok=None, rule="보고만 (R7e — 10-24 (7) GR 자리에 GE): " + str(gr.get("rule", "")))
    c["A5_export"] = (dict(a5, rule="두뇌 파일 다시 읽기: sha256·골든 로짓 오차 ≤ 허용·행동 같음·유한·관측 24·판 5·계약 0xad7bad5e1acaf071")
                      if a5 is not None else dict(ok=False, rule="A5 를 하지 않았다 (통과로 두지 않는다)"))
    for k in REPORT_KEYS:
        c[k] = dict(c[k], ok=None)
    p1 = c["P1_N_hide"]
    verdict, why, bad = verdict_of(c, g["t_crit_flight"])
    nc, nb = none_seed(N["candidate"]), none_seed(N["current"])
    rep: dict = dict(chase=c.pop("REPORT_N_chase", None), flight={w: g["report"]["flight"][w] for w in ("N", "G")},
                     pooled_N=g["report"]["pooled_N"], pooled_G=g["report"]["pooled_G"],
                     route=dict(candidate=R6.route_pooled(N["candidate"]), current=R6.route_pooled(N["current"])),
                     chase_decomp=R6.chase_decomp(N["candidate"], N["current"]), regions={},
                     gate=dict(N=gate_pooled(N["candidate"]), G=gate_pooled(G["candidate"])),
                     none=dict(candidate=None if nc is None else int(sum(nc.values())), current=None if nb is None else int(sum(nb.values())),
                               seeds=len(nc or {})))
    for r in REGIONS:
        a, b = R6.region_res(N["candidate"], r), R6.region_res(N["current"], r)
        if not a["worlds"]:
            continue
        rep["regions"][r] = dict(hide=ep_pair(a, b, "hide"), caught_ratio=ep_pair(a, b, "caught"),
                                 caught=re_.paired(re_.per_seed(a, "caught"), re_.per_seed(b, "caught")), gf=gf_pair(a, b), ge=ge_pair(a, b),
                                 gr=gr_pair(a, b), flight_hide=lv.hide_pair(a, b, "hide"), route=R6.route_pooled(a))
    for name, other in (others or {}).items():
        if other is not None:
            need_episode(other, name)
            rep[name] = compare(N["candidate"], other, N["current"])
    return dict(verdict=verdict, passed=verdict == "통과", why=why, failed=bad, criteria=dict(P1_N_hide=p1, **{k: c[k] for k in GUARDS if k in c}),
                report_criteria={k: c[k] for k in REPORT_KEYS}, n=g["n"], t_crit=g["t_crit"], n_g=g["n_g"], t_crit_g=g["t_crit_g"],
                n_flight=g["n_flight"], t_crit_flight=g["t_crit_flight"], dropped_flight=g["dropped_flight"], report=rep, early=EARLY, select=SELECT,
                unit=g["unit"], criterion=g["criterion"])


def _cell(k: str, v: dict) -> tuple[str, str, str, str]:
    """판정 표 한 줄의 R7 · route0 · 차이 · t 칸 (몫은 %, GR 은 시드당 수)."""
    if "diff" in v and "a" in v:
        if k in RATIO_KEYS:
            return f"{v['a'] * 100:.2f}%", f"{v['b'] * 100:.2f}%", f"{v['diff'] * 100:+.2f}%p", lv.tfmt(v["t"])
        if k == "GR_reflee":
            return f"{v['a']:.1f}", f"{v['b']:.1f}", f"{v['diff']:+.1f}", lv.tfmt(v["t"])
    return R6._cell(k, v)


def fmt_judge(res: dict, head: str = "") -> str:
    L = [f"# R7e 판정 — {res['verdict']}" + (f" ({head})" if head else ""), "",
         f"- {res['why']}",
         f"- 셈: 쫓김 사건 단위 (기준 판 {res['criterion']}). N 시드 {res['n']} (문턱 t_crit {res['t_crit']:.3f}), 사건 숨음 비율 짝 시드 {res['n_flight']} "
         f"(문턱 {res['t_crit_flight']:.3f}, 빠진 시드 {res['dropped_flight']}), G 시드 {res['n_g']} (문턱 {res['t_crit_g']:.3f})", "",
         "| 기준 | R7 | route0 | 차이 | t | 규칙 | 통과 |", "|---|---|---|---|---|---|---|"]
    for k, v in res["criteria"].items():
        a, b, d, t = _cell(k, v)
        L.append(f"| {k} | {a} | {b} | {d} | {t} | {v.get('rule', '')} | {'예' if v.get('ok') else '아니오'} |")
    L += ["", "## 보고만 (판정에 쓰지 않음)", "", "| 칸 | R7 | route0 | 차이 | t | 규칙 |", "|---|---|---|---|---|---|"]
    for k, v in res["report_criteria"].items():
        a, b, d, t = _cell(k, v)
        L.append(f"| {k} | {a} | {b} | {d} | {t} | {v.get('rule', '')} |")
    rep = res["report"]
    L.append("")
    ch = rep.get("chase")
    if ch:
        L.append(f"- N 쫓긴 시간(스스로 벗어난 도망, 시드 평균): R7 {ch['a']:.3f} 초 · route0 {ch['b']:.3f} 초 (차이 {ch['diff']:+.3f}, t {lv.tfmt(ch['t'])}, 시드 {ch['n']})")
    dc = rep["chase_decomp"]
    L.append(f"- 쫓긴 시간 전체 합 차이 {dc['total']:+.3f} 초 = 끝 까닭 섞임 {dc['mix']:+.3f} + 같은 까닭 안 {dc['within']:+.3f}")
    L += ["", "| 세계 | 두뇌 | 사건 시작 (1000 산 사슴-스텝당) | 쫓긴 사건 | 사건 숨음 비율 (숨음) | 사건 잡힘 비율 (잡힘) | 굶음·그 밖·잘림 | 지켜보는 중 판 끝 | "
          "이어진 도망 (은신처 뒤·그 밖 뒤) | 도망 ÷ 사건 | 5 초 창 안 죽음 (잡힘·굶음) | 도망 단위: 쫓긴 도망 · 숨음 비율 · 잡힘 비율 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for w in ("N", "G"):
        f = rep["flight"][w]
        for who in ("candidate", "current"):
            x = f[who]
            L.append(f"| {w} | {'R7' if who == 'candidate' else 'route0'} | {x['ep_started']} ({x['ep_per_1k']:.3f}) | {x['ep_chased']} | "
                     f"{lv.pct(x['ep_hide_share'], 2)} ({x['ep_hidden']}) | {lv.pct(x['ep_caught_share'], 2)} ({x['ep_caught']}) | "
                     f"{x['ep_starved']}·{x['ep_other']}·{x['ep_truncated']} | {x['ep_watching']} | {x['ep_joined_cover']}·{x['ep_joined_other']} | "
                     f"{x['flights_per_episode']:.3f} | {x['ep_window_caught']}·{x['ep_window_starved']} | "
                     f"{x['chased']} · {lv.pct(x['hide_share'], 2)} · {lv.pct(x['caught_share_chased'], 2)} |")
    L.append("")
    for who in ("candidate", "current"):
        s = rep["route"][who]
        L.append(f"- 길 ({'R7' if who == 'candidate' else 'route0'}, N): SHELTER 몫 {s['shelter_share']:.4f} · 도망 하나당 결정 {s['per_flight_decisions']:.3f} · "
                 f"다시 고름 {s['per_flight_redecide']:.4f} · 무효 {s['per_flight_invalid']:.4f} · 길 바꿈 {s['per_flight_switches']:.4f}")
    for w in ("N", "G"):
        x = rep["gate"][w]
        if x is not None:
            L.append(f"- 막음 통계 ({w}, R7): 덮기 밖 결정 {x['free_decisions']:,} · 그 가운데 두뇌 FLEE {x['brain_flee']} (마스크가 막아 0 이어야 한다)")
    nn = rep["none"]
    L.append(f"- 두뇌 스스로 뛴 도망(길 none, N 판 전체 — 시드 {nn['seeds']}): R7 {nn['candidate']} · route0 {nn['current']}")
    L += ["", "| 지역 | 사건 숨음 비율 R7 − route0 (t) | 사건 잡힘 비율 (t) | 잡힌 몫 (t) | GF (t) | GE (t) | GR 시드당 (t) | 도망 단위 숨음 비율 (t) | R7 SHELTER 몫 |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r, x in rep["regions"].items():
        L.append(f"| {r} | {_q(x['hide'], 100, '%p')} | {_q(x['caught_ratio'], 100, '%p')} | {_q(x['caught'], 100, '%p')} | {_q(x['gf'], 1, '', 4)} | "
                 f"{_q(x['ge'], 1, '', 4)} | {_q(x['gr'], 1, '', 1)} | {_q(x['flight_hide'], 100, '%p')} | {x['route']['shelter_share']:.4f} |")
    L.append("")
    for name, label in (("off", "대조 '길 끔'"), ("rule", "손 규칙 '늘 SHELTER'"), ("r6", "R6 고른 두뇌")):
        x = rep.get(name)
        if x is None:
            continue
        L.append(f"- R7 − {label}: 사건 숨음 비율 {_q(x['hide'], 100, '%p')} · 사건 잡힘 비율 {_q(x['caught_ratio'], 100, '%p')} · 잡힌 몫 "
                 f"{_q(x['caught'], 100, '%p')} · 쫓긴 시간 {_q(x['chase'], 1, ' 초', 3)} · GF {_q(x['gf'], 1, '', 4)} · GE {_q(x['ge'], 1, '', 4)} · "
                 f"GR {_q(x['gr'], 1, '/시드', 1)} · 도망 단위 숨음 비율 {_q(x['flight_hide'], 100, '%p')} (그 판의 사건 숨음 비율 "
                 f"{lv.pct(x['flight']['ep_hide_share'], 2)})")
        v0 = x.get("vs_route0")
        if v0:
            L.append(f"  - {label} − route0: 사건 숨음 비율 {_q(v0['hide'], 100, '%p')} · GF {_q(v0['gf'], 1, '', 4)} · GE {_q(v0['ge'], 1, '', 4)} · "
                     f"GR {_q(v0['gr'], 1, '/시드', 1)}")
    return "\n".join(L)


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #

def cmd_run(a) -> int:
    if a.use in JUDGE_USES:
        raise SystemExit(f"--use {a.use} 는 판정 시드다 — judge 명령으로만 돈다 (사전 등록 2·6절, 고른 모델이 있어야 한다)")
    seeds = R6.parse_seeds(a.seeds) if a.seeds else None
    plan = use_plan(a.use, seeds, a.steps)
    info = prepare_info(a.out_dir)
    res = ensure_run(info, a.model, a.use, a.workers, a.name, a.out_dir, a.probe, plan)
    if "worlds" in res:
        p, f = re_.pooled(res), lv.flight_pooled(res)
        g, nn = gate_pooled(res), none_seed(res)
        print(f"{a.name}: 세계 {p['worlds']} · 잡힘 {p['caught']:.4f} 굶음 {p['starved']:.4f} 산 {p['alive']:.4f} · 사건 시작 {f['ep_started']} 쫓긴 사건 {f['ep_chased']} "
              f"사건 숨음 비율 {lv.pct(f['ep_hide_share'], 2)} 사건 잡힘 비율 {lv.pct(f['ep_caught_share'], 2)} · 도망 시작 {f['started']} 도망 단위 숨음 비율 "
              f"{lv.pct(f['hide_share'], 2)} · 은신처 안 잡힘 {p['catch_cover']} · 막음 통계 "
              f"{'—' if g is None else str(g['brain_flee']) + ' / 덮기 밖 결정 ' + format(g['free_decisions'], ',')} · 길 none 도망 {'—' if nn is None else sum(nn.values())}",
              flush=True)
    else:
        print(f"{a.name}: 끼임 {re_.stuck_counts(res)}", flush=True)
    return 0


def cmd_checks(a) -> int:
    if a.smoke and a.out_dir is None:
        raise SystemExit("--smoke 는 --out-dir 을 함께 준다 (스모크 기록을 logs/ 에 쓰지 않는다)")
    if not a.smoke and Path(a.ckpt_dir).resolve() != CK.resolve():
        raise SystemExit("--ckpt-dir 는 스모크(도구 확인)에서만 바꾼다 — 점검은 R7 본 학습 산출(ckpt/v3)을 쓴다")
    plan = smoke_plan("check", R6.parse_seeds(a.smoke), a.smoke_steps) if a.smoke else None
    logs = Path(a.out_dir) if a.out_dir else LOGS
    runs_dir = (Path(a.out_dir) / "runs") if a.out_dir else OUT
    summ = run_checks(a.seeds, a.control, a.at, a.workers, a.ckpt_dir, plan, logs, runs_dir, verify_sha=not a.smoke)
    return 1 if summ["stop"] else 0


def _smoke_plans(a) -> dict | None:
    """--smoke 시드 --smoke-steps 길이 → 쓰임마다 스모크 계획 (도구 확인 — 판정 아님). 없으면 None (사전 등록 계획)."""
    if not a.smoke:
        return None
    seeds = R6.parse_seeds(a.smoke)
    return {u: smoke_plan(u, seeds, a.smoke_steps) for u in USES}


def cmd_select(a) -> int:
    sp = _smoke_plans(a)
    if sp and a.out_dir is None:
        raise SystemExit("--smoke 는 --out-dir 을 함께 준다 (스모크 기록을 logs/ 에 쓰지 않는다)")
    if not sp:
        select_guard(a.models)
    out_dir = Path(a.out_dir) if a.out_dir else OUT
    plan = sp["select"] if sp else None
    info = prepare_info(out_dir)
    rows = []
    for m in a.models:
        spec = R7.resolve_model(m)
        if spec["mask"] != 5:
            raise SystemExit(f"고르기 후보 {m} 는 마스크 판 {spec['mask']} 이다 — R7 두뇌(판 5)만 고른다")
        res = ensure_run(info, m, "select", a.workers, f"select_{spec['label']}", out_dir, plan=plan)
        rows.append((m, R6.model_seed_of(spec["label"]), res))
    base = ensure_run(info, "route0", "select", a.workers, "select_route0", out_dir, plan=plan)
    sel = select_rule(rows, base)
    text = fmt_select(sel)
    print(text)
    logs = out_dir if sp else LOGS
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "select.txt").write_text(text + "\n", encoding="utf-8")
    (logs / "select.json").write_text(json.dumps(lv.jsonable(sel), ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return 0 if sel["pick"] else 1


def cmd_judge(a) -> int:
    sp = _smoke_plans(a) or {}
    if sp and a.out_dir is None:
        raise SystemExit("--smoke 는 --out-dir 을 함께 준다 (스모크 판을 runs/ 에 쓰지 않는다)")
    if not sp:
        # 사전 등록 5·6절: 고른 모델 하나만 판정한다 (logs/select.txt 의 '고른 모델' 과 같은 파일이어야 한다)
        pk = picked_model()
        if pk is None:
            raise SystemExit("results/v3/r7e/logs/select.txt 에 고른 모델이 없다 — 먼저 r7e_eval.py select (사전 등록 5절. '없음' 이면 R7e 실패로 보고 — 판정하지 않는다)")
        if Path(R7.resolve_model(pk)["path"]).resolve() != Path(R7.resolve_model(a.model)["path"]).resolve():
            raise SystemExit(f"--model {a.model} 은 고른 모델 {pk} 가 아니다 (사전 등록 5·6절 — 고른 모델 하나만 판정한다)")
        require_r7_model(R7.resolve_model(a.model)["path"])
        if not a.off or Path(R7.resolve_model(a.off)["path"]).resolve() != R7_CONTROL.resolve():
            raise SystemExit(f"--off 는 R7 대조 '길 끔' 마지막 모델 {lv.path_text(R7_CONTROL)} 이다 (사전 등록 3-3)")
        require_r7_model(R7_CONTROL)
    spec = R7.resolve_model(a.model)
    if spec["mask"] != 5:
        raise SystemExit(f"--model {a.model} 은 마스크 판 {spec['mask']} 이다 — R7e 판정은 판 5 두뇌만 받는다")
    if a.off and R7.resolve_model(a.off)["mask"] != 6:
        raise SystemExit(f"--off {a.off} 는 대조 '길 끔'(판 6) 두뇌가 아니다")
    out_dir = Path(a.out_dir) if a.out_dir else OUT
    info = prepare_info(out_dir)
    W = a.workers
    runs = {}
    for key, text, use, name in (("N_r7", a.model, "judge_n", "judge_r7_N"), ("N_base", "route0", "judge_n", "judge_route0_N"),
                                 ("G_r7", a.model, "judge_g", "judge_r7_G"), ("G_base", "route0", "judge_g", "judge_route0_G"),
                                 ("S_r7", a.model, "stuck", "stuck_r7"), ("S_base", "route0", "stuck", "stuck_route0")):
        runs[key] = ensure_run(info, text, use, W, name, out_dir, plan=sp.get(use))
    others = dict(off=ensure_run(info, a.off, "judge_n", W, "judge_off_N", out_dir, plan=sp.get("judge_n")) if a.off else None,
                  rule=None if a.no_rule else ensure_run(info, "shelter_rule", "judge_n", W, "judge_rule_N", out_dir, plan=sp.get("judge_n")),
                  r6=None if a.no_r6 else ensure_run(info, "r6", "judge_n", W, "judge_r6_N", out_dir, plan=sp.get("judge_n")))
    a5 = R7.a5_check(spec["path"], out_dir / "brains" if sp else BRAINS)
    res = judge(dict(candidate=runs["N_r7"], current=runs["N_base"]), dict(candidate=runs["G_r7"], current=runs["G_base"]),
                dict(candidate=runs["S_r7"], current=runs["S_base"]), a5, others)
    res["models"] = dict(r7=a.model, r7_sha1=sha1_12(spec["path"]), base="route0", off=a.off, rule=None if a.no_rule else "shelter_rule",
                         r6=None if a.no_r6 else lv.path_text(R7.R6_PICK))
    text = fmt_judge(res, Path(a.model).name)
    print(text)
    out = Path(a.out) if a.out else (out_dir / "judge_smoke.md" if sp else HERE.parent / "judge.md")
    out.write_text(text + "\n", encoding="utf-8")
    out.with_suffix(".json").write_text(json.dumps(lv.jsonable(res), ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    return 0 if res["passed"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--use", required=True, help="check · select · smoke (판정 쓰임은 judge 명령으로만)")
    r.add_argument("--model", required=True, help="route0 · route0m5 · obs21zero · obs21zero_m6 · r6 · shelter_rule · 모델 zip")
    r.add_argument("--name", required=True)
    r.add_argument("--probe", action="store_true")
    r.add_argument("--seeds", default=None, help="smoke 만")
    r.add_argument("--steps", type=int, default=None, help="smoke 만")
    c = sub.add_parser("checks")
    c.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    c.add_argument("--control", action="store_true", help="대조 '길 끔' 체크포인트도 본다 (보고만)")
    c.add_argument("--at", type=int, nargs="+", default=list(CHECK_AT), help="체크포인트(백만 스텝)")
    c.add_argument("--ckpt-dir", type=Path, default=CK, help="스모크만 바꾼다")
    s = sub.add_parser("select")
    s.add_argument("--models", nargs="+", required=True)
    j = sub.add_parser("judge")
    j.add_argument("--model", required=True)
    j.add_argument("--off", default=None, help="대조 '길 끔' 모델 (판 6, 보고만 — 판정에서는 R7 대조 마지막 모델)")
    j.add_argument("--no-rule", action="store_true", help="'늘 SHELTER' 보고 줄을 돌리지 않는다")
    j.add_argument("--no-r6", action="store_true", help="'R7 − R6' 보고 줄을 돌리지 않는다")
    j.add_argument("--out", default=None)
    r.add_argument("--out-dir", type=Path, default=OUT)
    for p in (c, s, j):
        p.add_argument("--out-dir", type=Path, default=None, help="스모크 기록 폴더 (기본: 판 results/v3/r7e/runs, 기록 results/v3/r7e/logs)")
        p.add_argument("--smoke", default=None, help="도구 확인: 스모크 시드(32080~32099 안)로 돌린다 — 판정 아님. --out-dir 을 함께 준다")
        p.add_argument("--smoke-steps", type=int, default=300)
    for p in (r, c, s, j):
        p.add_argument("--workers", type=int, default=lv.default_workers())
    a = ap.parse_args(argv)
    return dict(run=cmd_run, checks=cmd_checks, select=cmd_select, judge=cmd_judge)[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

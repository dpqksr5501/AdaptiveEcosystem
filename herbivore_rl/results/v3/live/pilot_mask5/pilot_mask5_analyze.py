"""판 5 예비 측정 셈 (pilot_mask5.py analyze) — raw/<변형>.json.gz(live.py pilot 의 판정 세계 결과 그대로)에서 관문 크기를 고르는 표를 만든다.

셈은 모두 live.py 의 함수 그대로다: 시드마다 합(live.flight_seed — 지역 셋 분자·분모 합), 짝 차이(r4_eval.paired), 문턱(live.t_crit). 관문 칸을 빠르게 다시 세는
gate_fast 는 live.gate_live 의 t 칸(P1·GH·GN 셋·GF·GE·GV·GC·GG 넷)과 같은 셈이고, 진짜 후보마다 live.gate_live 와 값이 같은지 맞춰 본다(check_fast).
G4·G5·G6(은신처 안 잡힘·끼임·악용)은 t 칸이 아니라 여기서는 보고만 한다(G5 끼임은 예비 측정에서 세지 않는다).

같은 두뇌 두 번(A/A):
  (가) 그대로 두 번 — R7e 를 '더 견줄 두뇌'로 한 번 더 돌린 판(I_t20 same). 판정이 결정적이라 모든 칸 차이가 정확히 0 이어야 한다.
  (나) 시드를 섞은 같은 두뇌(부트스트랩) — 지금 두뇌의 시드 묶음(N·G 같은 시드) 100 개에서 '지금'과 '후보'를 따로 복원 추출해 판정 꼴(같은 시드 수·길이·
       문턱, 두 번 보기 포함)로 돌린다. 효과가 없는 두뇌가 우연히 1차를 넘을 몫·지킴이 우연히 걸릴 몫이다. 같은 시드끼리의 상관은 넣지 않는다(진짜 후보의
       짝 상관 r 은 거의 0 — 표 3).
"""

from __future__ import annotations

import gzip
import json
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
import pilot_mask5 as pm  # noqa: E402  (sys.path 는 pilot_mask5 가 맞춘다)
import live  # noqa: E402
import r4_eval as re_  # noqa: E402

OUT = HERE.parent
HS = (900, 1800, 2700, 3600)
STEP_S = live.STEP_S
Z = live._Z975 + 0.8416                                  # 양쪽 5%·검정력 80%
B_AA = 4000                                              # 시드 섞은 A/A 되풀이 수
FIELDS = ("n", "d_caught", "d_starved", "d_alive", "ep_chased", "ep_hidden", "ep_caught", "ep_started", "started", "live_steps", "flee_steps",
          "unsafe_n", "own_n", "own_contact", "f_chased", "f_hidden", "f_caught")
# 관문 t 칸: 이름 → (세계, 재료, 방향) — 방향 +1 = 나빠짐이 '커짐'(t < +문턱이어야 통과), −1 = '작아짐'(t > −문턱), 0 = 1차(t ≥ +문턱)
CELLS = {
    "P1_N_hide": ("N", "hide", 0), "GH_flight_caught": ("N", "ep_caught", 1), "GN_caught": ("N", "caught", 1), "GN_starved": ("N", "starved", 1),
    "GN_alive": ("N", "alive", -1), "GF_flight_starts": ("N", "gf", 1), "GE_episode_starts": ("N", "ge", 1), "GV_flee_time": ("N", "gv", 1),
    "GC_flight_unsafe": ("N", "gc", 1), "GG_caught": ("G", "caught", 1), "GG_starved": ("G", "starved", 1), "GG_alive": ("G", "alive", -1),
    "GG_chase": ("G", "chase", 1),
}
GUARDS = [k for k in CELLS if k != "P1_N_hide"]


@lru_cache(maxsize=None)
def tcrit(df: int) -> float:
    return live.t_crit(int(df))


# --------------------------------------------------------------------- #
# raw → 시드 표
# --------------------------------------------------------------------- #


def load_raw(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        d = json.load(f)
    res, models = {}, {}
    for c in d["captured"]:
        res.update(c["res"])
        models.update(c["models"])
    return dict(meta={k: v for k, v in d.items() if k != "captured"}, res=res, models=models)


def seed_table(res: dict, h: int) -> dict:
    """판 {meta, worlds} → 판정 길이 h 의 시드마다 합 {시드: {FIELDS}} (live.flight_seed 그대로 + 사슴 잡힘·굶음·산)."""
    A = live.at_horizon(res, h)
    fs = live.flight_seed(A, hide=True, episode=True)
    out = {}
    for w in A["worlds"]:
        s = int(w["seed"])
        a = out.setdefault(s, dict(n=0, d_caught=0, d_starved=0, d_alive=0))
        a["n"] += int(w["n"])
        a["d_caught"] += int(w["caught"])
        a["d_starved"] += int(w["starved"])
        a["d_alive"] += int(w["alive"])
    for s, f in fs.items():
        o = out[s]
        o.update(ep_chased=f["ep_chased"], ep_hidden=f["ep_hidden"], ep_caught=f["ep_caught"], ep_started=f["ep_started"], started=f["started"],
                 live_steps=f["live_steps"], flee_steps=f["flee_steps"], unsafe_n=f["unsafe_n"], own_n=f["own_n"], own_contact=f["own_contact"],
                 f_chased=f["chased"], f_hidden=f["hidden"], f_caught=f["caught"])
    return out


def to_arrays(tab: dict, seeds) -> dict:
    return {k: np.array([tab[s][k] for s in seeds], dtype=np.float64) for k in FIELDS}


def metric(a: dict, key: str):
    """시드 배열 → (값, 쓸 수 있음). live.gate_live 의 칸과 같은 셈 (분모 0 의 처리도 같다)."""
    n = a["n"]
    if key == "hide":
        return np.divide(a["ep_hidden"], a["ep_chased"], out=np.zeros_like(n), where=a["ep_chased"] > 0), a["ep_chased"] >= 1
    if key == "ep_caught":
        return np.divide(a["ep_caught"], a["ep_chased"], out=np.zeros_like(n), where=a["ep_chased"] > 0), a["ep_chased"] >= 1
    if key == "f_hide":
        return np.divide(a["f_hidden"], a["f_chased"], out=np.zeros_like(n), where=a["f_chased"] > 0), a["f_chased"] >= 1
    if key in ("caught", "starved", "alive"):
        return np.divide(a["d_" + key], n, out=np.zeros_like(n), where=n > 0), np.ones_like(n, dtype=bool)
    if key == "gf":
        return np.divide(1000.0 * a["started"], a["live_steps"], out=np.zeros_like(n), where=a["live_steps"] > 0), np.ones_like(n, dtype=bool)
    if key == "ge":
        return np.divide(1000.0 * a["ep_started"], a["live_steps"], out=np.zeros_like(n), where=a["live_steps"] > 0), np.ones_like(n, dtype=bool)
    if key == "gv":
        return np.divide(a["flee_steps"], a["live_steps"], out=np.zeros_like(n), where=a["live_steps"] > 0), np.ones_like(n, dtype=bool)
    if key == "gc":
        return np.divide(a["unsafe_n"], a["started"], out=np.zeros_like(n), where=a["started"] > 0), np.ones_like(n, dtype=bool)
    if key == "chase":
        return np.divide(a["own_contact"], a["own_n"], out=np.zeros_like(n), where=a["own_n"] > 0) * STEP_S, a["own_n"] >= 1
    raise KeyError(key)


def paired_arr(x: np.ndarray, y: np.ndarray) -> dict:
    """r4_eval.paired 와 같은 셈 (배열)."""
    d = x - y
    n = len(d)
    m = float(d.mean()) if n else float("nan")
    se = float(d.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    t = m / se if se > 0 else (0.0 if m == 0 else math.copysign(math.inf, m))
    sd = float(d.std(ddof=1)) if n > 1 else float("nan")
    r = float(np.corrcoef(x, y)[0, 1]) if n > 2 and x.std() > 0 and y.std() > 0 else float("nan")
    return dict(a=float(x.mean()) if n else float("nan"), b=float(y.mean()) if n else float("nan"), diff=m, se=se, t=t, n=n, sd=sd, r=r)


def cell(cand: dict, cur: dict, key: str) -> dict:
    xa, oka = metric(cand, key)
    xb, okb = metric(cur, key)
    ok = oka & okb
    return paired_arr(xa[ok], xb[ok])


def gate_fast(candN: dict, curN: dict, candG: dict, curG: dict, delta: float = 0.0) -> dict:
    """live.gate_live 의 t 칸만 같은 셈으로 (G4·G5·G6 빼고). 반환 = 칸마다 {diff, t, n, ok} + p1_ok·bad(걸린 지킴)·passed."""
    out = {}
    nN = len(curN["n"])
    nG = len(curG["n"])
    T, TG = tcrit(nN - 1), tcrit(nG - 1)
    for name, (w, key, sign) in CELLS.items():
        q = cell(candN, curN, key) if w == "N" else cell(candG, curG, key)
        if name == "P1_N_hide":
            thr = tcrit(q["n"] - 1)
            ok = q["n"] >= 2 and math.isfinite(q["se"]) and q["diff"] > 0 and q["diff"] >= delta and q["t"] >= thr
        else:
            if name in ("GH_flight_caught",):
                thr = tcrit(q["n"] - 1)
            elif name == "GG_chase":
                thr = tcrit(q["n"] - 1)
            else:
                thr = T if w == "N" else TG
            ok = q["n"] >= 2 and math.isfinite(q["se"]) and (q["t"] < thr if sign > 0 else q["t"] > -thr)
        out[name] = dict(q, thr=thr, ok=bool(ok))
    bad = [k for k in GUARDS if not out[k]["ok"]]
    return dict(cells=out, p1_ok=out["P1_N_hide"]["ok"], bad=bad, passed=bool(out["P1_N_hide"]["ok"] and not bad))


def check_fast(res: dict, cand: str, hN: int, seedsN, hG: int, seedsG, tabs) -> float:
    """gate_fast 가 live.gate_live 와 같은 t 를 내는지 (진짜 후보 하나) — 칸마다 |t 차이| 의 최댓값."""
    ev = {"N": dict(candidate=live.subset(live.at_horizon(res[f"{cand}:N"], hN), seedsN), current=live.subset(live.at_horizon(res["current:N"], hN), seedsN)),
          "G": dict(candidate=live.subset(live.at_horizon(res[f"{cand}:G"], hG), seedsG), current=live.subset(live.at_horizon(res["current:G"], hG), seedsG))}
    g = live.gate_live(ev, None, None)
    f = gate_fast(to_arrays(tabs[(cand, "N", hN)], seedsN), to_arrays(tabs[("current", "N", hN)], seedsN),
                  to_arrays(tabs[(cand, "G", hG)], seedsG), to_arrays(tabs[("current", "G", hG)], seedsG))
    worst = 0.0
    for k in CELLS:
        a, b = g["criteria"][k]["t"], f["cells"][k]["t"]
        if not (math.isfinite(a) and math.isfinite(b)):
            if not (a == b or (math.isnan(a) and math.isnan(b))):
                raise AssertionError(f"{cand} {k}: gate_live t {a} 대 gate_fast {b}")
            continue
        worst = max(worst, abs(a - b))
        if bool(g["criteria"][k]["ok"]) != bool(f["cells"][k]["ok"]):
            raise AssertionError(f"{cand} {k}: gate_live ok {g['criteria'][k]['ok']} 대 gate_fast {f['cells'][k]['ok']}")
    if worst > 1e-9:
        raise AssertionError(f"{cand}: gate_live 와 gate_fast 의 t 가 다르다 ({worst})")
    return worst


# --------------------------------------------------------------------- #
# 시드 섞은 A/A
# --------------------------------------------------------------------- #


def aa_null(tabs: dict, all_seeds, hN: int, nN: int, hG: int, nG: int, rng, B: int = B_AA, delta: float = 0.0) -> dict:
    """지금 두뇌끼리 관문 t 칸 (A/A — 효과가 없는 두뇌): 예비 시드 100 개의 시드 묶음(N·G 를 같은 시드로 묶음)에서 '지금'과 '후보'를 따로 복원 추출
    (부트스트랩)해 판정 꼴(nN·nG 시드, 같은 문턱)로 1차 우연 통과 몫·지킴이 하나라도 걸릴 몫·칸마다 걸릴 몫을 잰다. 두 번 보기(5-3): 앞 절반
    (live.seq_sizes) 짝 t ≤ 0 이면 중간 기각 — 그 몫과 두 번 보기로 끝까지 가서 통과할 몫도 적는다. 같은 시드끼리의 상관은 넣지 않는다(진짜 후보의 짝 상관
    r 은 거의 0 — 3절 표)."""
    seeds = list(all_seeds)
    allN = to_arrays(tabs[("current", "N", hN)], seeds)
    allG = to_arrays(tabs[("current", "G", hG)], seeds)
    m = len(seeds)
    k = live.seq_sizes(nN)
    cnt = dict(p1=0, anyg=0, passed=0, fut=0, passed_seq=0)
    per = {g: 0 for g in GUARDS}
    p1_t = []
    for _ in range(B):
        i = rng.integers(0, m, size=nN)
        j = rng.integers(0, m, size=nN)
        curN = {x: v[i] for x, v in allN.items()}
        cN = {x: v[j] for x, v in allN.items()}
        curG = {x: v[i[:nG]] for x, v in allG.items()}
        cG = {x: v[j[:nG]] for x, v in allG.items()}
        g = gate_fast(cN, curN, cG, curG, delta)
        cnt["p1"] += g["p1_ok"]
        cnt["anyg"] += bool(g["bad"])
        cnt["passed"] += g["passed"]
        p1_t.append(g["cells"]["P1_N_hide"]["t"])
        for x in g["bad"]:
            per[x] += 1
        if k:
            q = cell({x: v[:k] for x, v in cN.items()}, {x: v[:k] for x, v in curN.items()}, "hide")
            fut = q["n"] >= 2 and q["t"] <= -float(live.LIVE["seq_futility_t"] or 0.0)
            cnt["fut"] += fut
            cnt["passed_seq"] += (not fut) and g["passed"]
    return dict(B=B, hN=hN, nN=nN, hG=hG, nG=nG, p1_pass=cnt["p1"] / B, any_guard_fail=cnt["anyg"] / B, pass_all=cnt["passed"] / B,
                interim_k=k, interim_stop=cnt["fut"] / B, pass_all_seq=cnt["passed_seq"] / B,
                guard_fail={x: v / B for x, v in per.items()}, p1_t_sd=float(np.std(p1_t, ddof=1)), p1_t_mean=float(np.mean(p1_t)))


# --------------------------------------------------------------------- #
# 검정력·중간 판정
# --------------------------------------------------------------------- #


def power(d: float, sd: float, n: int, delta: float = 0.0) -> float:
    """짝 t 한쪽 검정력 P(t ≥ t_crit(n−1)) — 비중심 t (scipy). δ_H 가 있으면 관측 평균 ≥ δ 도 함께 (어림: 정규)."""
    from scipy import stats

    if not (sd > 0 and n >= 2):
        return float("nan")
    ncp = d / sd * math.sqrt(n)
    p = float(stats.nct.sf(tcrit(n - 1), n - 1, ncp))
    if delta > 0:
        p = min(p, float(stats.norm.sf((delta - d) / (sd / math.sqrt(n)))))
    return p


def futility_stop(d: float, sd: float, n: int) -> float:
    """중간 판정(앞 절반 짝 t ≤ 0 이면 기각)에서 멈출 몫 ≈ P(앞 절반 평균 차이 ≤ 0)."""
    from scipy import stats

    if not (sd > 0 and n >= 4):
        return float("nan")
    return float(stats.norm.cdf(-d / sd * math.sqrt(n // 2)))


def need(sd: float, d: float) -> int | None:
    return int(math.ceil((Z * sd / d) ** 2)) if sd == sd and d > 0 else None


# --------------------------------------------------------------------- #
# 시간
# --------------------------------------------------------------------- #


def times_of(pilot: dict, raw: dict) -> dict:
    t = dict(pilot.get("times") or {})
    walls = []
    sps_native = []
    for tag, r in raw["res"].items():
        for w in r["worlds"]:
            nat = w.get("native") or {}
            if nat.get("steps_per_s"):
                sps_native.append(float(nat["steps_per_s"]))
            walls.append(float(w.get("wall_s", 0.0)))
    t["native_steps_per_s_mean"] = float(np.mean(sps_native)) if sps_native else None
    t["native_worlds"] = len(sps_native)
    return t


# --------------------------------------------------------------------- #
# 본 셈
# --------------------------------------------------------------------- #


def fmt(x, nd=2, sign=True):
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{x:+.{nd}f}".replace("-", "−") if sign else f"{x:.{nd}f}"


def pp(x, nd=2):
    return fmt(None if x is None else x * 100.0, nd)


def main(a) -> int:
    raw_dir = Path(a.raw)
    files = sorted(raw_dir.glob("*.json.gz"))
    files = [f for f in files if ("_smoke" in f.name) == bool(getattr(a, "smoke", False))]
    rng = np.random.default_rng(20261027)
    summary: dict = dict(made_by="pilot_mask5_analyze.py", seeds=[34900, 34999], variants={}, aa={}, check_fast={})
    seeds_dir = OUT / "seeds"
    seeds_dir.mkdir(exist_ok=True)
    for fp in files:
        name = fp.name[: -len(".json.gz")]
        cache = fp.with_name(f"{name}.summary.json")                  # 변형 셈 저장 (raw 보다 새것이면 다시 쓴다 — raw 폴더 안, git 밖)
        if cache.exists() and cache.stat().st_mtime > max(fp.stat().st_mtime, HERE.stat().st_mtime):
            c = json.loads(cache.read_text(encoding="utf-8"))
            summary["variants"][name], summary["check_fast"][name] = c["V"], c["check_fast"]
            if c.get("aa"):
                summary["aa"][name] = c["aa"]
            print(f"[{name}] 저장된 셈 다시 씀", flush=True)
            continue
        print(f"[{name}] 읽는 중 …", flush=True)
        raw = load_raw(fp)
        res = raw["res"]
        brains = sorted({k.rsplit(":", 1)[0] for k in res})
        cands = [b for b in brains if b not in ("current", "same")]
        all_seeds = sorted({int(w["seed"]) for w in res["current:N"]["worlds"]})
        hs = sorted(int(h) for h in res["current:N"]["worlds"][0]["at"])
        ns = [n for n in (40, 60, 80, 100) if n <= len(all_seeds)] or [len(all_seeds)]
        tabs = {(b, w, h): seed_table(res[f"{b}:{w}"], h) for b in brains for w in ("N", "G") for h in hs}
        # 시드 표 저장 (git — 작게: 두뇌·세계·길이마다 FIELDS 순 배열)
        st = dict(variant=name, seeds=all_seeds, fields=list(FIELDS), models=raw["models"],
                  table={f"{b}:{w}:{h}": [[tabs[(b, w, h)][s][k] for k in FIELDS] for s in all_seeds] for (b, w, h) in tabs},
                  catch_cover={f"{b}:{w}": int(sum(x["catch_cover"] for x in res[f"{b}:{w}"]["worlds"])) for b in brains for w in ("N", "G")})
        with gzip.open(seeds_dir / f"{name}.json.gz", "wt", encoding="utf-8") as f:
            json.dump(st, f, separators=(",", ":"))
        pilot = json.loads((OUT / "variants" / name / "pilot.json").read_text(encoding="utf-8"))
        V: dict = dict(label=pm.VARIANTS.get(name.split("_fc")[0], {}).get("label", name), brains=brains, candidates=cands, seeds=[all_seeds[0], all_seeds[-1]],
                       models=raw["models"], times=times_of(pilot, raw), f_dec_T=pilot.get("f_dec_T"), wall_s=raw["meta"].get("wall_s"))
        # 1) 지금 두뇌 수준 (시드 100, 전체 합 — 판 길이마다)
        lvl = {}
        for w in ("N", "G"):
            for h in hs:
                A = to_arrays(tabs[("current", w, h)], all_seeds)
                lvl[f"{w}{h}"] = dict(ep_hide=float(A["ep_hidden"].sum() / A["ep_chased"].sum()), ep_caught=float(A["ep_caught"].sum() / A["ep_chased"].sum()),
                                      ep_chased_per_seed=float(A["ep_chased"].mean()), caught=float(A["d_caught"].sum() / A["n"].sum()),
                                      starved=float(A["d_starved"].sum() / A["n"].sum()), ge=float(1000 * A["ep_started"].sum() / A["live_steps"].sum()),
                                      gf=float(1000 * A["started"].sum() / A["live_steps"].sum()), gv=float(A["flee_steps"].sum() / A["live_steps"].sum()),
                                      hide_seed_sd=float(metric(A, "hide")[0].std(ddof=1)))
        V["current"] = lvl
        V["catch_cover"] = st["catch_cover"]
        # 2) 두뇌 − 지금: 모든 칸 × 판 길이 (시드 100)
        comp = {}
        for b in [x for x in brains if x != "current"]:
            for h in hs:
                cN, kN = to_arrays(tabs[(b, "N", h)], all_seeds), to_arrays(tabs[("current", "N", h)], all_seeds)
                cG, kG = to_arrays(tabs[(b, "G", h)], all_seeds), to_arrays(tabs[("current", "G", h)], all_seeds)
                row = {}
                for nm, (w, key, sign) in CELLS.items():
                    row[nm] = cell(cN, kN, key) if w == "N" else cell(cG, kG, key)
                row["REPORT_N_flight_hide"] = cell(cN, kN, "f_hide")
                row["G_hide"] = cell(cG, kG, "hide")
                comp[f"{b}@{h}"] = row
        V["vs_current"] = comp
        # 2-1) 지역마다 사건 숨음 비율 (전체 합, N 1800 — 어느 지역에서 바뀌나: 나무·날씨가 바뀐 지역인가, 그대로인 지역인가)
        reg = {}
        for b in brains:
            A = live.at_horizon(res[f"{b}:N"], 1800 if 1800 in hs else hs[-1])
            acc = {}
            for w in A["worlds"]:
                e = w["flight"]["episode"]
                x = acc.setdefault(w["region"], [0, 0, 0])
                x[0] += int(e["hidden"])
                x[1] += int(e["chased"])
                x[2] += int(e["caught"])
            reg[b] = {r: dict(hide=v[0] / v[1] if v[1] else float("nan"), caught=v[2] / v[1] if v[1] else float("nan"), chased=v[1]) for r, v in acc.items()}
        V["region_N1800"] = reg
        # 3) gate_fast = live.gate_live 맞춰 보기 (진짜 후보마다, 지금 관문 크기 N 1800 × 80 · G 3600 × 40)
        worst = 0.0
        hN0, hG0 = (1800 if 1800 in hs else hs[0]), hs[-1]
        for b in cands:
            worst = max(worst, check_fast(res, b, hN0, all_seeds[:80], hG0, all_seeds[:40], tabs))
        summary["check_fast"][name] = dict(candidates=len(cands), worst_t_diff=worst)
        # 4) 관문 꼴 판정 (예비 시드로 — 판정 아님): 판 길이·시드 수 조합마다
        gates = {}
        for b in cands:
            for hN in hs:
                for nN in ns:
                    for hG, nG in [(h, n) for h in (1800, 3600) if h in hs for n in (40, 60) if n <= len(all_seeds)] or [(hs[-1], len(all_seeds))]:
                        sN, sG = all_seeds[:nN], all_seeds[:nG]
                        g = gate_fast(to_arrays(tabs[(b, "N", hN)], sN), to_arrays(tabs[("current", "N", hN)], sN),
                                      to_arrays(tabs[(b, "G", hG)], sG), to_arrays(tabs[("current", "G", hG)], sG))
                        p = g["cells"]["P1_N_hide"]
                        k_int = live.seq_sizes(nN)
                        half = cell(to_arrays(tabs[(b, "N", hN)], sN[:k_int]), to_arrays(tabs[("current", "N", hN)], sN[:k_int]), "hide") if k_int else None
                        gates[f"{b}|N{hN}x{nN}|G{hG}x{nG}"] = dict(p1_diff=p["diff"], p1_t=p["t"], p1_ok=g["p1_ok"], bad=g["bad"], passed=g["passed"],
                                                                     bad_t={k: g["cells"][k]["t"] for k in g["bad"]},
                                                                     interim_t=half["t"] if half else None,
                                                                     interim_stop=bool(half and half["t"] <= -float(live.LIVE["seq_futility_t"] or 0.0)))
        V["gates"] = gates
        # 5) 시드 섞은 A/A (지금 두뇌끼리)
        aa = {}
        control = name.endswith("_off")                                  # 대조(끈 세계)는 크기 고르기 셈(A/A)에 넣지 않는다
        for hN, nN, hG, nG, dl in ((1800, 80, 3600, 40, 0.0), (1800, 80, 3600, 40, 0.01), (1800, 40, 3600, 40, 0.0), (1800, 60, 3600, 40, 0.0),
                                   (900, 80, 3600, 40, 0.0), (2700, 60, 3600, 40, 0.0), (3600, 80, 3600, 40, 0.0), (3600, 40, 3600, 40, 0.0),
                                   (1800, 100, 3600, 60, 0.0)):
            if control or hN not in hs or hG not in hs or max(nN, nG) > len(all_seeds):
                continue
            aa[f"N{hN}x{nN}|G{hG}x{nG}" + (f"|δ{dl * 100:g}%p" if dl else "")] = aa_null(tabs, all_seeds, hN, nN, hG, nG, rng, delta=dl)
        if aa:
            summary["aa"][name] = aa
        summary["variants"][name] = V
        cache.write_text(json.dumps(dict(V=V, check_fast=summary["check_fast"][name], aa=aa), ensure_ascii=False, default=float), encoding="utf-8")
        print(f"[{name}] 후보 {cands}, gate_fast = gate_live (|t 차이| 최대 {worst:.1e})", flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, separators=(",", ":"), default=float) + "\n", encoding="utf-8",
                                      newline="\n")
    print(f"-> {OUT / 'summary.json'}")
    import pilot_mask5_report as rp

    rp.write(summary, OUT / "pilot.md")
    print(f"-> {OUT / 'pilot.md'}")
    return 0

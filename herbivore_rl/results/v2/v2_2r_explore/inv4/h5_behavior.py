"""갈림 4 조사 H5 — 정책이 기억 입력(threat_recency, 관측 7)을 해롭게 쓰나 (inv4/MEMO.md 1절 H5 행, 기존 모델 분석).

    cd herbivore_rl
    python results/v2/v2_2r_explore/inv4/h5_behavior.py smoke       # 한 시드로 시간·일치 확인
    python results/v2/v2_2r_explore/inv4/h5_behavior.py run         # 잡을 돌려 h5_rows.jsonl 에 쌓는다(이어 돌리기)
    python results/v2/v2_2r_explore/inv4/h5_behavior.py summarize   # h5_behavior.json 을 만든다

모든 잡은 T1 세계(configs/v2_2r_t1.yaml), 탐색 시드 12000~12039 × 5000스텝, γ 학습값, 워커 4개다.
- (a) T1 모델 s20~22 의 C4 개입: 관측 7 고정 0(C4fix0), 관측 7 개체 간 순열(C4perm), 관측 7 고정 평균(C4fixm, 그 모델·모드
  C0 의 결정 때 threat_recency 평균 = eval_p1 의 threat_mean 시드 평균). 두 모드(결정, K24 유지 표본).
- (b) T0 모델 s20~22 를 T1 세계에서 관측 앞 7열만 넣어(probe_v2:obs_take) 두 모드로 돈다(T1w). 세계 동역학이 같으면
  G_γ 가 eval_p1 의 T0 C0 값과 같아야 한다.
- T1 C0 도 다시 돈다(추가 구간 지표를 얻으려고). 공개 열은 eval_p1 의 T1 C0 와 같아야 한다(일치 확인).

추가 지표 (공개 열 밖, 행의 "x"): 결정 때 구간(0 평시, 1 창 = 안 보임 & threat_recency > theta, 2 보임)은 World.step 0) 의
창과 같은 규칙이다(스텝마다 assert 로 확인). 실제 보행은 스텝 뒤 `World.gait`.
- cnt [구간 3, 배부름 2(배고픔, 배부름), 보행 3(정지, 걷기, 뛰기)] 개체-스텝 수
- pred·starve [구간 3]: 그 스텝 결정 때 구간별 피식·아사 사망 수 (둘 다면 피식으로 센다)
- trans [구간 3, 다음 구간 3 + 사망]: 스텝 뒤 관측의 구간 (죽은 개체는 사망 칸)
- esum [구간 3]: 결정 때 energy 합
- trb [안 보인 개체의 threat_recency 칸 TR_EDGES, 보행 3]: 기억 값별 보행 (창 = 마지막 두 칸)
- gsum·gn [구간 3, 보행 3]: 리턴-투-고 합과 개수 (G_γ 평균과 같은 범위, 끝 tail 스텝 제외)
- gcomp: G_γ 의 보상 성분별 몫(같은 사망 마스크로 성분마다 리턴-투-고를 낸 평균). alive(rew_alive), energy(순에너지
  변화), repro(번식), death_pred, death_starve(사망 페널티). 선형이라 합이 G_γ 다.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]          # herbivore_rl
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch보다 먼저

import argparse  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from concurrent.futures import as_completed  # noqa: E402

import numpy as np  # noqa: E402

from env_v2.world import HUNGRY, World  # noqa: E402

OUT = Path(__file__).resolve().parent
EXPLORE = OUT.parent
ROWS = OUT / "h5_rows.jsonl"
SUMMARY = OUT / "h5_behavior.json"
T1_CFG = ROOT / "configs" / "v2_2r_t1.yaml"
TRAIN_SEEDS = (20, 21, 22)
WORKERS = 4
STEPS = 5000
GAMMA = 0.9916661555611042
T_CRIT = 2.023
SEG = ("calm", "win", "seen")
GAITS = ("stop", "walk", "run")
FULL = ("hungry", "full")
# 안 보인 개체의 threat_recency 칸 경계. 창 문턱 theta 0.5 가 경계 하나라 마지막 두 칸이 창이다
TR_EDGES = (0.01, 0.1, 0.25, 0.5, 0.75)
COMP = ("alive", "energy", "repro", "death_pred", "death_starve")


# --------------------------------------------------------------------- #
# 추가 지표를 세는 세계 (코어는 고치지 않는다: 하위 클래스 + 워커 안에서 env_v2.rollout.World 이름만 바꾼다)
# --------------------------------------------------------------------- #


class TWorld(World):
    last = None

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        TWorld.last = self

    def _reset_stats(self) -> None:
        super()._reset_stats()
        self._x = {
            "cnt": np.zeros((3, 2, 3), dtype=np.int64),
            "pred": np.zeros(3, dtype=np.int64),
            "starve": np.zeros(3, dtype=np.int64),
            "trans": np.zeros((3, 4), dtype=np.int64),
            "esum": np.zeros(3),
            "trb": np.zeros((len(TR_EDGES) + 1, 3), dtype=np.int64),
        }
        self._xs = {"seg": [], "gait": [], "rew": [], "done": [], "caught": [], "starved": [], "repro": []}

    def _accumulate(self, a, rew, repro, caught, starved, done) -> None:
        self._x_last = (caught.copy(), starved.copy(), repro.copy())
        super()._accumulate(a, rew, repro, caught, starved, done)

    def step(self, a):
        theta = self._vw["theta"]
        seen = self._g["pred_count"] > 0
        win = ~seen & (self.threat > theta)
        seg = np.where(seen, 2, win.astype(np.int64))
        e0 = self.energy.copy()
        full = (e0 >= HUNGRY * self.cfg.max_energy).astype(np.int64)
        tr = self.threat.copy()
        out = super().step(a)
        _, rew, done, _ = out
        assert np.array_equal(self.window, win), "결정 때 창이 World.step 0) 과 다르다"
        caught, starved, repro = self._x_last
        gait = np.asarray(self.gait, dtype=np.int64)
        x = self._x
        x["cnt"] += np.bincount((seg * 2 + full) * 3 + gait, minlength=18).reshape(3, 2, 3)
        x["pred"] += np.bincount(seg[caught], minlength=3)
        x["starve"] += np.bincount(seg[starved & ~caught], minlength=3)
        seen2 = self._g["pred_count"] > 0
        seg2 = np.where(seen2, 2, (~seen2 & (self.threat > theta)).astype(np.int64))
        seg2 = np.where(done, 3, seg2)
        x["trans"] += np.bincount(seg * 4 + seg2, minlength=12).reshape(3, 4)
        x["esum"] += np.bincount(seg, weights=e0 / self.cfg.max_energy, minlength=3)
        un = ~seen
        trb = np.digitize(tr[un], TR_EDGES)
        x["trb"] += np.bincount(trb * 3 + gait[un], minlength=x["trb"].size).reshape(x["trb"].shape)
        xs = self._xs
        xs["seg"].append(seg.astype(np.int8))
        xs["gait"].append(gait.astype(np.int8))
        xs["rew"].append(np.array(rew, dtype=np.float64))
        xs["done"].append(np.array(done, dtype=bool))
        xs["caught"].append(caught)
        xs["starved"].append(starved & ~caught)
        xs["repro"].append(repro)
        return out

    def extras(self, gamma: float, tail: int) -> dict:
        from env_v2.rollout import discounted_return_to_go

        xs = {k: np.asarray(v) for k, v in self._xs.items()}
        T = len(xs["rew"])
        sl = slice(0, T - tail)
        G = discounted_return_to_go(xs["rew"], xs["done"], gamma)
        code = (xs["seg"][sl].astype(np.int64) * 3 + xs["gait"][sl]).ravel()
        gsum = np.bincount(code, weights=G[sl].ravel(), minlength=9).reshape(3, 3)
        gn = np.bincount(code, minlength=9).reshape(3, 3)
        cfg = self.cfg
        comps = {
            "alive": np.full_like(xs["rew"], cfg.rew_alive),
            "repro": cfg.rew_repro * xs["repro"].astype(np.float64),
            "death_pred": cfg.rew_death * xs["caught"].astype(np.float64),
            "death_starve": cfg.rew_death * xs["starved"].astype(np.float64),
        }
        comps["energy"] = xs["rew"] - sum(comps.values())
        gcomp = {k: float(discounted_return_to_go(v, xs["done"], gamma)[sl].mean()) for k, v in comps.items()}
        out = {k: v.tolist() for k, v in self._x.items()}
        out.update(gsum=gsum.tolist(), gn=gn.tolist(), gcomp=gcomp, g_check=float(G[sl].mean()))
        return out


def _job(args):
    """워커 잡 하나: (키, 설정 dict, 정책 스펙, 시드) → (키, 시드, 공개 행, 추가 지표)."""
    key, cfg_dict, spec, seed = args
    import env_v2.rollout as R
    from env.config import Config

    R.World = TWorld                                   # 이 워커 안에서만. rollout 본문은 그대로 쓴다
    r = R.rollout(Config(cfg_dict), R.build_policy(spec, seed), seed, STEPS, gamma=GAMMA)
    w = TWorld.last
    x = w.extras(GAMMA, R.tail_steps(GAMMA))
    return key, int(seed), R.public_row(r), x


# --------------------------------------------------------------------- #
# 잡 목록
# --------------------------------------------------------------------- #


def _learned(path: Path, mode: str) -> dict:
    from probe_v2 import MODES

    return {"kind": "learned", "model": str(Path(path).resolve()), **MODES[mode]}


def eval_p1() -> dict:
    return json.loads((EXPLORE / "eval_p1.json").read_text(encoding="utf-8"))


def job_specs() -> dict[str, tuple[dict, str]]:
    """키 → (정책 스펙, 모델 키). 순서 = 우선순위(판정에 쓰는 잡 먼저)."""
    from probe_v2 import model_path

    d1 = eval_p1()
    take = {"factory": "probe_v2:obs_take", "dims": list(range(7))}
    out: dict[str, tuple[dict, str]] = {}
    groups = []
    for m in ("hold", "det"):
        for s in TRAIN_SEEDS:
            t1, t0 = _learned(model_path("T1", s), m), _learned(model_path("T0", s), m)
            tm = float(np.mean([r["threat_mean"] for r in d1["rows"][f"T1_s{s}|C0|{m}"]]))
            groups.append({
                f"T1_s{s}|C4fix0|{m}": ({"policy": t1, "wrap": [{"kind": "obs_fix", "dims": [7], "values": [0.0]}]},
                                        f"T1_s{s}"),
                f"T1_s{s}|C4perm|{m}": ({"policy": t1, "wrap": [{"kind": "obs_permute", "dims": [7], "salt": 0}]},
                                        f"T1_s{s}"),
                f"T0_s{s}|T1w|{m}": ({"policy": t0, "wrap": [take]}, f"T0_s{s}"),
                f"T1_s{s}|C0|{m}": (t1, f"T1_s{s}"),
                f"T1_s{s}|C4fixm|{m}": ({"policy": t1, "wrap": [{"kind": "obs_fix", "dims": [7], "values": [tm]}]},
                                        f"T1_s{s}"),
            })
    kinds = ("C4fix0", "C4perm", "T1w", "C0", "C4fixm")
    for kind in kinds:
        for g in groups:
            for k, v in g.items():
                if f"|{kind}|" in k:
                    out[k] = v
    return out


def _fingerprints() -> dict[str, str]:
    from diagnose_v2 import model_fingerprint
    from probe_v2 import model_path

    return {f"{a}_s{s}": model_fingerprint(model_path(a, s)) for a in ("T0", "T1") for s in TRAIN_SEEDS}


def read_rows() -> list[dict]:
    if not ROWS.exists():
        return []
    return [json.loads(ln) for ln in ROWS.read_text(encoding="utf-8").splitlines() if ln.strip()]


def cmd_run(args) -> int:
    from diagnose_v2 import EXPLORE_SEEDS
    from env_v2.config import load_v2_config
    from env_v2.rollout import make_executor

    seeds = list(EXPLORE_SEEDS)
    cfg = load_v2_config(T1_CFG).to_dict()
    sha = _fingerprints()
    specs = job_specs()
    if args.only:
        specs = {k: v for k, v in specs.items() if any(f"|{o}|" in k for o in args.only)}
    have = {(r["key"], r["seed"]) for r in read_rows()
            if r.get("steps") == STEPS and r.get("gamma") == GAMMA and r.get("sha1") == sha[r["model"]]}
    todo = [(k, cfg, spec, s, mk) for k, (spec, mk) in specs.items() for s in seeds if (k, s) not in have]
    print(f"잡 {len(todo)}개 (이미 {len(have)}개), 워커 {args.workers}", flush=True)
    if not todo:
        return 0
    ex = make_executor(args.workers)
    t0 = time.time()
    done_n = 0
    try:
        futs = {ex.submit(_job, (k, c, sp, s)): mk for k, c, sp, s, mk in todo}
        with open(ROWS, "a", encoding="utf-8") as f:
            for fut in as_completed(futs):
                key, seed, row, x = fut.result()
                mk = futs[fut]
                f.write(json.dumps({"key": key, "seed": seed, "model": mk, "sha1": sha[mk], "steps": STEPS,
                                    "gamma": GAMMA, "row": row, "x": x}, ensure_ascii=False, allow_nan=True) + "\n")
                f.flush()
                done_n += 1
                if done_n % 20 == 0 or done_n == len(todo):
                    el = time.time() - t0
                    print(f"  {done_n}/{len(todo)} ({el:.0f}s, 남은 추정 {el / done_n * (len(todo) - done_n):.0f}s)",
                          flush=True)
    finally:
        ex.shutdown()
    return 0


def cmd_smoke(args) -> int:
    from env_v2.config import load_v2_config
    from probe_v2 import model_path

    cfg = load_v2_config(T1_CFG).to_dict()
    d1 = eval_p1()
    for key, spec in ((f"T1_s20|C0|hold", _learned(model_path("T1", 20), "hold")),
                      (f"T0_s20|C0|hold", {"policy": _learned(model_path("T0", 20), "hold"),
                                           "wrap": [{"factory": "probe_v2:obs_take", "dims": list(range(7))}]})):
        t = time.time()
        _, seed, row, x = _job((key, cfg, spec, 12000))
        ref = d1["rows"][key][0]
        print(f"{key} 시드 {seed}: {time.time() - t:.1f}s, g_gamma {row['g_gamma']:.12f} / eval_p1 {ref['g_gamma']:.12f}, "
              f"g_check {x['g_check']:.12f}, 성분 합 {sum(x['gcomp'].values()):.12f}")
        print("   같은 공개 열:", all(row.get(c) == ref.get(c) or (isinstance(ref.get(c), float) and math.isnan(ref[c])
                                                               and math.isnan(row.get(c, 0.0))) for c in ref))
    return 0


# --------------------------------------------------------------------- #
# 요약
# --------------------------------------------------------------------- #

WINDOW_COLS = ["win_frac", "p_stop_win", "p_stop_calm", "p_stop_win_full", "p_stop_calm_full", "b3_l",
               "p_stop_win_hungry", "p_stop_calm_hungry"]
GAIT_COLS = ["b1", "b2", "p_run_unseen", "p_run_d025", "p_run_d050", "p_run_d100", "stop_frac", "walk_frac",
             "run_frac", "stall_frac", "hungry_frac", "starve_share", "p_stop_hungry", "p_stop_full", "b8",
             "intake_per_step", "drain_per_step"]
OUTCOME_COLS = ["g_gamma", "predation_rate", "starve_rate", "survival", "repro", "mean_return", "cover_frac",
                "seg_seen_frac", "threat_mean"]
PUBLIC_COLS = OUTCOME_COLS + WINDOW_COLS + GAIT_COLS


def _r(x, y):
    return float(x) / float(y) if y else float("nan")


def derive(x: dict) -> dict:
    """추가 지표 수 → 비율 (시드 하나 또는 합친 수)."""
    cnt = np.asarray(x["cnt"], dtype=np.float64)
    pred, starve = np.asarray(x["pred"], float), np.asarray(x["starve"], float)
    trans, esum = np.asarray(x["trans"], float), np.asarray(x["esum"], float)
    gsum, gn = np.asarray(x["gsum"], float), np.asarray(x["gn"], float)
    trb = np.asarray(x["trb"], float)
    n_seg = cnt.sum((1, 2))
    n = n_seg.sum()
    out = {}
    for k, sg in enumerate(SEG):
        out[f"frac_{sg}"] = _r(n_seg[k], n)
        out[f"hungry_frac_{sg}"] = _r(cnt[k, 0].sum(), n_seg[k])
        out[f"energy_{sg}"] = _r(esum[k], n_seg[k])
        for gi, ga in enumerate(GAITS):
            out[f"p_{ga}_{sg}"] = _r(cnt[k, :, gi].sum(), n_seg[k])
            for fi, fu in enumerate(FULL):
                out[f"p_{ga}_{sg}_{fu}"] = _r(cnt[k, fi, gi], cnt[k, fi].sum())
        out[f"haz_pred_{sg}"] = 1000.0 * _r(pred[k], n_seg[k])          # 개체-스텝 1000 당
        out[f"haz_starve_{sg}"] = 1000.0 * _r(starve[k], n_seg[k])
        out[f"pred_share_{sg}"] = _r(pred[k], pred.sum())
        out[f"starve_share_{sg}"] = _r(starve[k], starve.sum())
        for j, sg2 in enumerate(SEG + ("dead",)):
            out[f"tr_{sg}_to_{sg2}"] = _r(trans[k, j], trans[k].sum())
        out[f"G_{sg}"] = _r(gsum[k].sum(), gn[k].sum())
        out[f"gfrac_{sg}"] = _r(gn[k].sum(), gn.sum())
        for gi, ga in enumerate(GAITS):
            out[f"G_{sg}_{ga}"] = _r(gsum[k, gi], gn[k, gi])
    lab = [f"<{TR_EDGES[0]}"] + [f"{a}-{b}" for a, b in zip(TR_EDGES[:-1], TR_EDGES[1:])] + [f">{TR_EDGES[-1]}"]
    nun = trb.sum()
    for b, lb in enumerate(lab):
        out[f"trb[{lb}]_frac"] = _r(trb[b].sum(), nun)
        for gi, ga in enumerate(GAITS):
            out[f"trb[{lb}]_p_{ga}"] = _r(trb[b, gi], trb[b].sum())
    if "gcomp" in x:
        for c in COMP:
            out[f"gc_{c}"] = float(x["gcomp"][c])
    return out


def pool(xs: list[dict]) -> dict:
    """시드별 수를 합친다(gcomp 는 시드 평균 — 시드마다 개체-스텝 수가 같다)."""
    keys = ("cnt", "pred", "starve", "trans", "esum", "trb", "gsum", "gn")
    out = {k: np.sum([np.asarray(x[k], dtype=np.float64) for x in xs], axis=0) for k in keys}
    out["gcomp"] = {c: float(np.mean([x["gcomp"][c] for x in xs])) for c in COMP}
    return out


def paired(a, b) -> dict:
    """짝 t (a − b), 탐색 시드마다 한 값. 둘 중 하나라도 nan 인 시드는 뺀다."""
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    m = np.isfinite(a) & np.isfinite(b)
    d = a[m] - b[m]
    n = len(d)
    sd = float(d.std(ddof=1)) if n > 1 else float("nan")
    t = float(d.mean() / (sd / math.sqrt(n))) if n > 1 and sd > 0 else float("nan")
    return {"a": float(np.mean(a[m])) if n else float("nan"), "b": float(np.mean(b[m])) if n else float("nan"),
            "diff": float(d.mean()) if n else float("nan"), "sd": sd, "t": t, "n": n,
            "sig": bool(math.isfinite(t) and abs(t) > T_CRIT)}


def cmd_summarize(args) -> int:
    from diagnose_v2 import EXPLORE_SEEDS

    seeds = list(EXPLORE_SEEDS)
    d1 = eval_p1()
    sha = _fingerprints()
    rows: dict[str, dict[int, dict]] = {}
    for r in read_rows():
        if r.get("steps") == STEPS and r.get("gamma") == GAMMA and r.get("sha1") == sha[r["model"]]:
            rows.setdefault(r["key"], {})[r["seed"]] = r
    complete = {k: v for k, v in rows.items() if all(s in v for s in seeds)}
    res = {"cond": {"seeds": [seeds[0], seeds[-1], len(seeds)], "steps": STEPS, "gamma": GAMMA, "hold_k": 24,
                    "world": "configs/v2_2r_t1.yaml", "sha1": sha, "eval_p1_cond_seeds_ok": d1["cond"]["seeds"] == seeds,
                    "eval_p1_cond_steps": d1["cond"]["steps"], "eval_p1_cond_gamma": d1["cond"]["gamma"],
                    "eval_p1_cond_hold_k": d1["cond"]["hold_k"],
                    "eval_p1_sha1_match": {k: d1["sha1"][k] == sha[k.split("|")[0]] for k in d1["sha1"]
                                           if k.startswith(("T0_", "T1_"))}},
           "incomplete": {k: len(v) for k, v in rows.items() if k not in complete}}

    def series(key, col, src="h5"):
        """키(모델 하나)의 시드순 값. src 'p1' 이면 eval_p1 행."""
        if src == "p1":
            rr = {r["seed"]: r for r in d1["rows"][key]}
            return np.array([rr[s].get(col, np.nan) for s in seeds], dtype=np.float64)
        rr = complete[key]
        if col in rr[seeds[0]]["row"]:
            return np.array([rr[s]["row"].get(col, np.nan) for s in seeds], dtype=np.float64)
        return np.array([derive(rr[s]["x"]).get(col, np.nan) for s in seeds], dtype=np.float64)

    def has(arm, kind, mode, src="h5"):
        ks = [f"{arm}_s{s}|{kind}|{mode}" for s in TRAIN_SEEDS]
        return all((k in d1["rows"]) if src == "p1" else (k in complete) for k in ks)

    def mm(arm, kind, mode, col, src="h5"):
        """모델 평균 시계열 (시드마다 세 모델의 평균)."""
        return np.nanmean([series(f"{arm}_s{s}|{kind}|{mode}", col, src) for s in TRAIN_SEEDS], axis=0)

    # 1) 일치 확인: h5 T1 C0 = eval_p1 T1 C0, h5 T0 T1w = eval_p1 T0 C0 (공개 열 전부, 시드별)
    parity = {}
    for mode in ("hold", "det"):
        for arm, kind in (("T1", "C0"), ("T0", "T1w")):
            for s in TRAIN_SEEDS:
                k, kp = f"{arm}_s{s}|{kind}|{mode}", f"{arm}_s{s}|C0|{mode}"
                if k not in complete:
                    continue
                ref = {r["seed"]: r for r in d1["rows"][kp]}
                cols = [c for c in ref[seeds[0]] if c != "seed"]
                diff_cols = {}
                for c in cols:
                    a = np.array([complete[k][sd]["row"].get(c, np.nan) for sd in seeds], dtype=np.float64)
                    b = np.array([ref[sd].get(c, np.nan) for sd in seeds], dtype=np.float64)
                    same = (a == b) | (np.isnan(a) & np.isnan(b))
                    if not same.all():
                        diff_cols[c] = {"n_seeds_diff": int((~same).sum()),
                                        "max_abs": float(np.nanmax(np.abs(a - b)))}
                gd = series(k, "g_gamma") - series(kp, "g_gamma", "p1")
                gchk = max(abs(complete[k][sd]["x"]["g_check"] - complete[k][sd]["row"]["g_gamma"]) for sd in seeds)
                gcs = max(abs(sum(complete[k][sd]["x"]["gcomp"].values()) - complete[k][sd]["row"]["g_gamma"])
                          for sd in seeds)
                parity[k] = {"vs": f"eval_p1 {kp}", "exact_all_public_cols": not diff_cols,
                             "n_cols": len(cols), "diff_cols": diff_cols,
                             "g_gamma_max_abs_diff": float(np.max(np.abs(gd))),
                             "g_check_max_abs": float(gchk), "gcomp_sum_max_abs": float(gcs)}
    res["parity"] = parity

    # 1b) 추가 지표 이름이 공개 열(window_stats)과 겹치는 6개는 정의가 같다(결정 때 창·배부름, 실제 정지). 시드마다 확인한다.
    #     겹치는 이름은 series()·tests 에서 공개 열 값을 쓴다
    overlap = {}
    for k, v in complete.items():
        for sd in seeds:
            dx = derive(v[sd]["x"])
            for c, val in dx.items():
                if c in v[sd]["row"]:
                    a, b = val, v[sd]["row"][c]
                    if not (math.isnan(a) and math.isnan(b)):
                        overlap[c] = max(overlap.get(c, 0.0), abs(a - b))
    res["derived_vs_public_max_abs"] = overlap

    # 1c) 보행 열(행동 4)의 학습 표준편차 σ = exp(log_std) — 모델 파일에서 읽는다(K24 칸 확률은 μ 와 σ 로 정해진다)
    from probe_v2 import model_path
    from stable_baselines3 import PPO

    res["speed_sigma"] = {f"{a}_s{s}": float(np.exp(PPO.load(model_path(a, s), device="cpu").policy.log_std
                                                      .detach().cpu().numpy()[4]))
                          for a in ("T0", "T1") for s in TRAIN_SEEDS}

    # 2) 판정: C4 − C0 (T1, 모델 평균 시계열의 짝 t, C0 = eval_p1 T1 C0)
    verdict = {}
    for mode in ("hold", "det"):
        c0 = mm("T1", "C0", mode, "g_gamma", "p1")
        per = {}
        for kind in ("C4fix0", "C4perm", "C4fixm"):
            if not has("T1", kind, mode):
                continue
            pm = {}
            for s in TRAIN_SEEDS:
                a = series(f"T1_s{s}|{kind}|{mode}", "g_gamma")
                b = series(f"T1_s{s}|C0|{mode}", "g_gamma", "p1")
                pm[f"s{s}"] = paired(a, b)
            per[kind] = {"model_mean": paired(mm("T1", kind, mode, "g_gamma"), c0), "per_model": pm}
        if has("T0", "T1w", mode):
            t0 = mm("T0", "T1w", mode, "g_gamma")
            per["T1_minus_T0"] = {"model_mean": paired(c0, t0),
                                  "per_model": {f"s{s}": {"T1": float(series(f"T1_s{s}|C0|{mode}", "g_gamma", "p1").mean()),
                                                          "T0": float(series(f"T0_s{s}|T1w|{mode}", "g_gamma").mean())}
                                                for s in TRAIN_SEEDS}}
            if has("T1", "C4fix0", mode):
                per["C4fix0_minus_T0"] = {"model_mean": paired(mm("T1", "C4fix0", mode, "g_gamma"), t0)}
            if has("T1", "C4perm", mode):
                per["C4perm_minus_T0"] = {"model_mean": paired(mm("T1", "C4perm", mode, "g_gamma"), t0)}
        verdict[mode] = per
    res["g_gamma_tests"] = verdict

    # 3) 행동 비교: T1(C0) − T0(T1w), 그리고 C4 − C0. 공개 열 + 추가 지표. 모델 평균(시드 평균의 세 모델 평균),
    #    모델별(시드 평균), 모델 평균 시계열의 짝 t. 추가 지표의 모델 값은 시드 합친 수로도 낸다(pooled).
    xcols = None
    beh = {}
    for mode in ("hold", "det"):
        conds = {"T1": ("T1", "C0"), "T0": ("T0", "T1w"), "T1_C4fix0": ("T1", "C4fix0"),
                 "T1_C4perm": ("T1", "C4perm"), "T1_C4fixm": ("T1", "C4fixm")}
        conds = {n: c for n, c in conds.items() if has(c[0], c[1], mode)}
        if not conds:
            continue
        if xcols is None:
            any_key = f"{next(iter(conds.values()))[0]}_s20|{next(iter(conds.values()))[1]}|{mode}"
            xcols = list(derive(complete[any_key][seeds[0]]["x"]))
        bm = {"conds": {}, "pooled": {}, "tests": {}}
        for n, (arm, kind) in conds.items():
            bm["conds"][n] = {}
            bm["pooled"][n] = {}
            for s in TRAIN_SEEDS:
                k = f"{arm}_s{s}|{kind}|{mode}"
                bm["pooled"][n][f"s{s}"] = derive(pool([complete[k][sd]["x"] for sd in seeds]))
            bm["pooled"][n]["model_mean"] = {c: float(np.nanmean([bm["pooled"][n][f"s{s}"][c] for s in TRAIN_SEEDS]))
                                             for c in xcols}
            for c in PUBLIC_COLS:
                per = {f"s{s}": float(np.nanmean(series(f"{arm}_s{s}|{kind}|{mode}", c))) for s in TRAIN_SEEDS}
                bm["conds"][n][c] = {"model_mean": float(np.mean(list(per.values()))), **per}
        pairs = [("T1", "T0"), ("T1_C4fix0", "T1"), ("T1_C4perm", "T1"), ("T1_C4fixm", "T1"), ("T1_C4fix0", "T0")]
        for a, b in pairs:
            if a not in conds or b not in conds:
                continue
            tt = {}
            for c in PUBLIC_COLS + xcols:
                tt[c] = paired(mm(*conds[a], mode, c), mm(*conds[b], mode, c))
            bm["tests"][f"{a}_minus_{b}"] = tt
        beh[mode] = bm
    res["behavior"] = beh

    # 4) G_γ 차의 보상 성분 분해 (T1 − T0, 모델 평균) — 선형이라 성분 차의 합이 G_γ 차다
    decomp = {}
    for mode in ("hold", "det"):
        if mode not in beh or "T1_minus_T0" not in beh[mode]["tests"]:
            continue
        tt = beh[mode]["tests"]["T1_minus_T0"]
        decomp[mode] = {c: {"T1": tt[f"gc_{c}"]["a"], "T0": tt[f"gc_{c}"]["b"], "diff": tt[f"gc_{c}"]["diff"],
                            "t": tt[f"gc_{c}"]["t"]} for c in COMP}
        decomp[mode]["sum_diff"] = float(sum(decomp[mode][c]["diff"] for c in COMP))
        decomp[mode]["g_gamma_diff"] = tt["g_gamma"]["diff"]
        # 구간 몫 분해 (기술용): G_γ = Σ_k gfrac_k · G_k → Δ = Σ Δgfrac_k·Ḡ_k + Σ ḡfrac_k·ΔG_k
        pm1, pm0 = beh[mode]["pooled"]["T1"]["model_mean"], beh[mode]["pooled"]["T0"]["model_mean"]
        sh = {}
        for sg in SEG:
            gf1, gf0, g1, g0 = pm1[f"gfrac_{sg}"], pm0[f"gfrac_{sg}"], pm1[f"G_{sg}"], pm0[f"G_{sg}"]
            sh[sg] = {"gfrac_T1": gf1, "gfrac_T0": gf0, "G_T1": g1, "G_T0": g0,
                      "mix": (gf1 - gf0) * (g1 + g0) / 2, "within": (gf1 + gf0) / 2 * (g1 - g0)}
        decomp[mode]["segments"] = sh
        decomp[mode]["seg_sum"] = float(sum(v["mix"] + v["within"] for v in sh.values()))
    res["g_decomposition"] = decomp
    res["note"] = ("g_gamma_tests 의 C0 는 eval_p1 의 T1_s2x|C0|{mode} 행이다. T0 는 T1 세계 obs_take 재실행(T1w). "
                   "behavior 의 T1 은 h5 재실행 C0(공개 열이 eval_p1 와 같은지는 parity). pooled = 시드 합친 수의 비율, "
                   "tests = 모델 평균 시계열(탐색 시드 40개)의 짝 t, 기준 2.023.")
    SUMMARY.write_text(json.dumps(res, ensure_ascii=False, indent=1, allow_nan=True), encoding="utf-8")
    print(f"썼다: {SUMMARY} (완료 키 {len(complete)}, 미완 {res['incomplete']})")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("smoke")
    r = sub.add_parser("run")
    r.add_argument("--workers", type=int, default=WORKERS)
    r.add_argument("--only", nargs="+", default=None, help="잡 종류만 (C4fix0 C4perm T1w C0 C4fixm)")
    sub.add_parser("summarize")
    args = p.parse_args(argv)
    if args.cmd == "run" and args.workers > WORKERS:
        raise SystemExit(f"워커는 최대 {WORKERS}개다")
    os.chdir(ROOT)
    return {"smoke": cmd_smoke, "run": cmd_run, "summarize": cmd_summarize}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

"""R7 GR 나누기 (보고만 — 사전 등록 PREREG.md 5-2 의 4 · 6절: 'GR 이 걸렸으면 GR 나누기(results/v3/r6/diag/diag.py 꼴)를 함께 보고한다').

R7 본 학습에서 고를 모델이 없었다(점검이 s0·s2 를 GR 로 뺐고, 남은 s1 의 마지막 모델도 고르기 자격 GR 에 걸렸다 — logs/early_main.json · logs/select.txt).
걸린 판을 같은 세계·같은 두뇌로 다시 돌리면서 세계의 도망 기록을 감싸(diag._Tracker — 통계 전용, 세계·궤적 그대로) 5 초 안 다시 시작한 도망 하나하나를
R6 진단과 같은 차례로 칸 하나에 넣는다:
  (다) 두뇌 스스로 뛰기 — 새 도망의 첫 FLEE 스텝이 반사가 아니다 (판 5 는 반사 밖 두뇌 FLEE 를 막으므로 R7 두뇌는 0 이어야 한다)
  (가) 은신처 들락날락 — 반사로 시작했고 지난 도망이 은신처로 끝났다 (끝 까닭 cover 이거나 마지막 FLEE 스텝 끝 위치가 은신처 원 안)
  (나) 그 밖 — 반사로 시작했고 지난 도망이 그 밖의 까닭으로 끝났다

판 (모두 argmax, 막기 없음 — 두뇌·세계 키는 r7_eval.make_items 그대로):
  check  (점검 시드 38120~38139): route0 · v3_r7_g995_s0_20m_5m · s1_20m_5m · s2_20m_5m (s0·s2 는 2M·5M 점검 (c) GR 로 빠졌다)
  select (고르기 시드 38100~38119): route0 · v3_r7_g995_s1_20m (고르기 자격 GR t +2.82 로 걸렸다)
확인: 다시 돌린 판이 점검·고르기 때의 판 파일(runs/early_*.json · runs/select_*.json)과 세계마다 같아야 한다(시작·다시 도망·쫓긴·숨음·잡힘·굶음·산). 다르면 멈춘다.
판정 시드 38000~38099 는 쓰지 않는다. 고르기·판정 결론(고른 모델 없음 — R7 실패)은 바꾸지 않는다.

    # herbivore_rl/ 에서
    PYTHONUTF8=1 python results/v3/r7/gr_split.py                                  # → gr_split.md · gr_split.json (판 파일 runs/gr_split/ — git 밖)
    PYTHONUTF8=1 python results/v3/r7/gr_split.py --smoke 32080-32081 --smoke-steps 300 --out-dir <임시>    # 도구 확인 (md·json 을 쓰지 않는다)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for _p in (ROOT, ROOT / "results" / "v3" / "r6", ROOT / "results" / "v3" / "r6" / "diag", HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import r7_eval as R7  # noqa: E402  (경로·torch 준비를 먼저 한다)
import diag as D  # noqa: E402  (R6 진단 — _Tracker · seed_parts · 칸 나누기)
import numpy as np  # noqa: E402

lv, re_, R6 = R7.lv, R7.re_, R7.R6
OUT = HERE.parent / "runs" / "gr_split"
MD, JS = HERE.parent / "gr_split.md", HERE.parent / "gr_split.json"
CK = "ckpt/v3/"
# (쓰임, 이름, 두뇌, 견줄 이미 있는 판 파일 이름)
PLAN = (
    ("check", "check_route0", "route0", "early_base"),
    ("check", "check_s0_5m", CK + "v3_r7_g995_s0_20m_5m.zip", "early_s0_5m"),
    ("check", "check_s1_5m", CK + "v3_r7_g995_s1_20m_5m.zip", "early_s1_5m"),
    ("check", "check_s2_5m", CK + "v3_r7_g995_s2_20m_5m.zip", "early_s2_5m"),
    ("select", "select_route0", "route0", "select_route0"),
    ("select", "select_s1_20m", CK + "v3_r7_g995_s1_20m.zip", "select_v3_r7_g995_s1_20m"),
)
LABEL = {"check_route0": "route0", "check_s0_5m": "R7 s0 5M (제외)", "check_s1_5m": "R7 s1 5M", "check_s2_5m": "R7 s2 5M (제외)",
         "select_route0": "route0", "select_s1_20m": "R7 s1 20M (자격 없음)"}


class _SplitPolicy:
    """바탕 정책 그대로(행동·마스크 같음) + 세계 도망 기록 감싸기(diag._Tracker — 읽기만)."""

    def __init__(self, base):
        self.base = base
        self.world = None
        self.tracker = None

    def __getattr__(self, name):
        if name in ("base", "world", "tracker"):
            raise AttributeError(name)
        return getattr(self.base, name)

    def bind_world(self, w) -> None:
        self.base.bind_world(w)
        self.world = w
        self.tracker = D._Tracker(w)

    def __call__(self, obs):
        return self.base(obs)

    def result(self) -> dict:
        return dict(dec={}, **self.tracker.result())


def _split_world(job: dict) -> dict:
    from env_v2 import rollout as ro

    holder: dict = {}
    orig = ro.build_policy

    def build(spec, seed=0):
        p = _SplitPolicy(orig(spec, seed))
        holder["p"] = p
        return p

    ro.build_policy = build
    try:
        out = lv._world_multi(job)
    finally:
        ro.build_policy = orig
    p = holder["p"]
    out["diag"] = p.result()
    w = p.world
    out["gate"] = w.flee_gate_stats() if getattr(w, "_fb", False) else None
    return out


def _split_job(item):
    tag, job = item
    return tag, _split_world(job)


def tool_sha() -> str:
    return hashlib.sha256(HERE.read_bytes()).hexdigest()[:16]


def run_one(info: dict, plan: dict, name: str, text: str, workers: int, out_dir: Path) -> dict:
    from concurrent.futures import as_completed

    from env_v2 import rollout as ro

    import gr_split as G                      # 워커가 이름으로 불러올 수 있게

    spec = R7.resolve_model(text)
    want = dict(use=plan["use"], seeds=plan["seeds"], steps=plan["steps"], model=text,
                model_sha1=hashlib.sha1(Path(spec["path"]).read_bytes()).hexdigest()[:12], sets=spec["sets"], code=R7.code_tags(), tool=tool_sha())
    path = Path(out_dir) / f"{name}.json"
    if path.exists():
        old = R7.load(path)
        if all((old.get("meta") or {}).get(k) == v for k, v in want.items()):
            print(f"  {name}: 같은 조건의 판이 있다 — 다시 쓴다", flush=True)
            return old
    items = [(tag, job) for _, tag, job in R7.make_items(info, spec, plan, False, tag=name)]
    print(f"  {name}: {text} (판 {spec['mask']}) · {plan['use']} 시드 {plan['seeds'][0]}~{plan['seeds'][-1]} × 지역 {len(info['regions'])} × "
          f"{plan['steps']} 스텝 ({len(items)} 세계)", flush=True)
    t0 = time.perf_counter()
    rows = [None] * len(items)
    ex = ro.make_executor(min(int(workers), len(items)))
    if ex is None:
        for k, it in enumerate(items):
            rows[k] = G._split_job(it)
    else:
        with ex:
            futs = {ex.submit(G._split_job, it): k for k, it in enumerate(items)}
            for n, f in enumerate(as_completed(futs), 1):
                rows[futs[f]] = f.result()
                if n % 30 == 0 or n == len(items):
                    print(f"    {name} {n}/{len(items)} ({time.perf_counter() - t0:.0f} 초)", flush=True)
    res = dict(meta=dict(want, name=name, obs=spec["obs"], mask=spec["mask"], model_path=lv.path_text(spec["path"]),
                         wall_s=round(time.perf_counter() - t0, 1), workers=int(workers)),
               worlds=[r for _, r in rows])
    R7.save(res, path)
    return res


def same_as(res: dict, path: Path) -> dict:
    """다시 돌린 판 = 점검·고르기 때 판(세계마다 시작·다시 도망·쫓긴·숨음·잡힘·굶음·산)."""
    return D.compare_early_base(res, path)


def analyse(runs: dict, base_name: str, names: list) -> dict:
    base = runs[base_name]
    parts = {k: D.seed_parts(runs[k]) for k in [base_name] + names}
    n = len(parts[base_name])
    T = lv.t_crit(n - 1) if n >= 2 else float("nan")
    out: dict = dict(n=n, t_crit=T, models={})
    for k in [base_name] + names:
        res, p = runs[k], parts[k]
        S = len(p)
        row = dict(label=LABEL[k], hide=lv.hide_pair(res, base, "hide"), caught_ratio=lv.hide_pair(res, base, "caught"),
                   GF=lv.flight_rate_pair(res, base, "starts"), GR=R6.route_guards(res, base)["GR_reflee"],
                   gr_cat={c: D.paired_of(p, parts[base_name], lambda x, c=c: x[c]) for c in D.CATS + ("ga_cover", "na_after_none")},
                   brain_starts=D.paired_of(p, parts[base_name], lambda x: x["brain"]))
        cells = D.pooled_cells(res)
        sub_na, sub_ga, sub_ga_new = Counter(), Counter(), Counter()
        for key, v in cells.items():
            _kind, cause, _circle, route, nc = key.split("|")
            c = D.cat_of(key)
            if c == "na":
                sub_na[f"{cause} · 길 {route}"] += v
            elif c == "ga":
                sub_ga[f"{'cover' if cause == 'cover' else cause + ' (원 안)'} · 길 {route}"] += v
                sub_ga_new["새 도망 첫 스텝 끝 원 안" if nc == "1" else "원 밖"] += v
        gap = np.sum([w["diag"]["gap"] for w in res["worlds"]], 0)
        row["sub"] = dict(na={x: v / S for x, v in sub_na.most_common()}, ga={x: v / S for x, v in sub_ga.most_common()},
                          ga_new={x: v / S for x, v in sub_ga_new.items()},
                          gap_mean_s=float((gap * np.arange(len(gap))).sum() / gap.sum() * lv.STEP_S) if gap.sum() else float("nan"))
        ex = {c: row["gr_cat"][c]["diff"] for c in D.CATS}
        tot = row["GR"]["diff"]
        row["excess"] = dict(total=tot, by=ex, ga_share=(ex["ga"] / tot if tot > 0 else None))
        gp = R7.gate_pooled(res)
        row["gate"] = gp
        out["models"][k] = row
    return out


def _cell(q: dict, kind: str, base: bool) -> str:
    if kind == "pct":
        v, d = f"{q['a'] * 100:.2f}%", f"{q['diff'] * 100:+.2f}%p"
    elif kind == "num":
        v, d = f"{q['a']:.4f}", f"{q['diff']:+.4f}"
    else:
        v, d = f"{q['a']:.1f}", f"{q['diff']:+.1f}"
    return v if base else f"{v} ({d}, t {lv.tfmt(q['t'])})"


def table(an: dict, base_name: str, names: list) -> list[str]:
    order = [base_name] + names
    M = an["models"]
    L = ["| 칸 | " + " | ".join(M[k]["label"] for k in order) + " |", "|---|" + "---|" * len(order)]
    for title, key, kind in (("숨음 비율 (쫓긴 도망 가운데)", "hide", "pct"), ("잡힘 비율 (쫓긴 도망 가운데)", "caught_ratio", "pct"),
                             ("GF (도망 시작 / 1000 산 사슴-스텝)", "GF", "num"), ("**GR 전체** (5 초 안 다시 도망, 시드당)", "GR", "cnt")):
        L.append(f"| {title} | " + " | ".join(_cell(M[k][key], kind, k == base_name) for k in order) + " |")
    for c in D.CATS:
        L.append(f"| {D.CAT_KO[c]} | " + " | ".join(_cell(M[k]["gr_cat"][c], "cnt", k == base_name) for k in order) + " |")
    L.append("| └ (가) 가운데 지난 끝 까닭 cover | " + " | ".join(_cell(M[k]["gr_cat"]["ga_cover"], "cnt", k == base_name) for k in order) + " |")
    L.append("| 두뇌 FLEE 로 시작한 도망 (시드당) | " + " | ".join(_cell(M[k]["brain_starts"], "cnt", k == base_name) for k in order) + " |")
    L.append("| 다시 도망 사이 평균 틈 (초) | " + " | ".join(f"{M[k]['sub']['gap_mean_s']:.2f}" for k in order) + " |")
    L.append("| 반사 밖 두뇌 FLEE (막음 통계, 판 합) | " + " | ".join(
        ("—" if M[k]["gate"] is None else f"{M[k]['gate']['brain_flee']}") for k in order) + " |")
    L.append("")
    for k in names:
        e = M[k]["excess"]
        if e["total"] > 0:
            L.append(f"- {M[k]['label']}: GR 초과분(route0 대비 시드 평균) {e['total']:+.1f} = " + " + ".join(f"{D.CAT_KO[c]} {e['by'][c]:+.1f}" for c in D.CATS)
                     + f" — (가) 몫 {e['ga_share'] * 100:.0f}%")
        else:
            L.append(f"- {M[k]['label']}: GR 초과분 없음 ({e['total']:+.1f})")
    L.append("")
    for k in order:
        s = M[k]["sub"]
        ga = " · ".join(f"{x} {v:.1f}" for x, v in list(s["ga"].items())[:5]) or "없음"
        na = " · ".join(f"{x} {v:.1f}" for x, v in list(s["na"].items())[:6]) or "없음"
        gn = " · ".join(f"{x} {v:.1f}" for x, v in s["ga_new"].items()) or "없음"
        L += [f"- {M[k]['label']} 속살 (시드당): (가) 지난 끝 까닭·길 {ga} / (가) 새 도망 시작 위치 {gn} / (나) 지난 끝 까닭·길 {na}"]
    return L


def fmt(an_c: dict, an_s: dict, meta: dict) -> str:
    sc, ss = an_c["models"], an_s["models"]
    c_names = [k for _, k, _, _ in PLAN if k.startswith("check_") and k != "check_route0"]
    s_names = [k for _, k, _, _ in PLAN if k.startswith("select_") and k != "select_route0"]

    def line(m):
        e = m["excess"]
        if e["total"] <= 0:
            return f"{m['label']} GR 초과분 없음"
        share = (f"초과분의 {e['ga_share'] * 100:.0f}% — (나) 가 줄어 (가) 혼자 초과분보다 크다" if e["ga_share"] > 1 else
                 f"초과분의 {e['ga_share'] * 100:.0f}%")
        out = m["sub"]["ga_new"].get("원 밖", 0.0)
        tot_ga = sum(m["sub"]["ga_new"].values())
        return (f"{m['label']}: GR 초과분 시드당 {e['total']:+.1f} = (가) 은신처 들락날락 {e['by']['ga']:+.1f}({share}) · "
                f"(나) 그 밖 {e['by']['na']:+.1f} · (다) 두뇌 스스로 뛰기 {e['by']['da']:+.1f}. (가) 의 새 도망 {tot_ga:.1f} 번 가운데 {out:.1f} 번은 "
                f"첫 스텝 끝이 은신처 원 밖이었다")

    main = [ss[k] for k in s_names] + [sc[k] for k in ("check_s0_5m", "check_s2_5m")]
    ga_main = all(m["excess"]["total"] > 0 and m["excess"]["by"]["ga"] >= 0.5 * m["excess"]["total"] for m in main)
    L = ["# R7 GR 나누기 — 고를 모델이 없었던 까닭 (보고만)", "",
         "**보고만이다. R7 결론(고른 모델 없음 → R7 실패, 판정하지 않음)은 그대로다.** 사전 등록 5-2 의 4 · 6절대로 GR 이 걸린 판을 나누어 보았다.", "",
         "## 결론 먼저", ""]
    L += [f"- {line(m)}." for m in main]
    s15 = sc["check_s1_5m"]
    L.append(f"- 견줌: 5M 점검을 넘은 {s15['label']} 은 GR 초과분이 시드당 {s15['excess']['total']:+.1f} 였다(짝 t {lv.tfmt(s15['GR']['t'])}). 같은 두뇌가 20M 까지 배운 뒤 "
             f"고르기 판에서 {ss['select_s1_20m']['excess']['total']:+.1f}(짝 t {lv.tfmt(ss['select_s1_20m']['GR']['t'])}) — 다른 시드 칸이라 바로 견줄 수는 없다(보고만).")
    if ga_main:
        L.append("- 쉽게 말해: 판 5 로 두뇌 스스로 뛰기는 0 이 되었다. 그런데 늘어난 '5 초 안 다시 뛰기'는 거의 모두 **은신처 원 안에서 끝난 도망 뒤 몇 초 안에(다시 도망 "
                 f"전체의 평균 틈 약 {sum(m['sub']['gap_mean_s'] for m in main) / len(main):.1f} 초) 도주 반사로 다시 뛴 것**(은신처 들락날락)이고, 다시 뛴 첫 걸음 끝은 거의 모두 은신처 원 밖이었다. 5M 점검에서는 은신처 쪽 길을 더 자주 고른 두뇌일수록 이 몫이 컸다. 10-23 사람 결정"
                 "('은신처 들락날락 때문에 GR 이 남으면 멈추고 사람에게 묻는다')에 해당한다.")
    else:
        L.append("- 늘어난 '5 초 안 다시 뛰기'의 주된 몫이 은신처 들락날락만은 아니다 — 칸별 값은 아래 표.")
    L += ["", "## 어떻게 쟀나", "",
          "- 세계: `r7_eval.make_items` 그대로(N = 스냅숏 거울 + 늑대 포만 끔, 1800 스텝, 두뇌의 마스크 판으로 세계 키 — R7 은 판 5). 막기·바꾸기 없이 같은 두뇌 argmax.",
          "- 셈: R6 진단 `results/v3/r6/diag/diag.py` 의 `_Tracker`(세계 도망 기록 감싸기 — 통계 전용) · `seed_parts` · 칸 나누기 그대로. 감싼 셈의 시작·다시 도망 수는 "
          "세계 기록과 세계마다 같았다(다르면 멈춘다).",
          f"- 확인: 다시 돌린 판이 점검·고르기 때 판과 세계마다 같은가 — {meta['same']}.",
          f"- 짝 t: 같은 시드 route0 대비(시드마다 지역 셋 합). 시드 20 이면 t_crit(19) = {an_c['t_crit']:.3f}. R7 점검·고르기 문턱은 +2.0.", "",
          "## 1. 고르기 판 (고르기 시드 38100~38119 — 자격 GR 에 걸린 s1 마지막 모델)", ""]
    L += table(an_s, "select_route0", s_names)
    L += ["", "## 2. 점검 판 (점검 시드 38120~38139 — 5M 체크포인트, s0·s2 는 GR 로 제외)", ""]
    L += table(an_c, "check_route0", c_names)
    L += ["", "## 3. 판단에 쓰지 않는 주의", "",
          "- 이 나누기는 결론을 바꾸지 않는다. 같은 학습에서 다른 체크포인트·다른 시드를 고르지 않는다(사전 등록 8절).",
          "- (가) 는 지금 두뇌(route0)에서도 GR 의 큰 몫이다 — 은신처로 끝난 도망 뒤 늑대가 아직 반사 거리 안이면 다시 뛰는 것은 세계 규칙(도주 반사)이 정한다.",
          "- 다음 갈래(사람 결정 — 사전 등록 8절): '은신처로 끝난 도망 뒤 다시 뛰기'를 GF·GR 에서 어떻게 셀지 다시 정하기, 관측 25(지금 길 한 칸), 또는 두 길 닫기.", "",
          f"- 판 파일: `results/v3/r7/runs/gr_split/` (git 밖). 도구 `gr_split.py` sha256 앞 16 `{meta['tool']}`. 걸린 시간 {meta['wall']}."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--workers", type=int, default=lv.default_workers())
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--smoke", default=None, help="도구 확인: 스모크 시드(32080~32099 안) — md·json 을 쓰지 않는다")
    ap.add_argument("--smoke-steps", type=int, default=300)
    a = ap.parse_args(argv)
    info = R7.prepare_info()
    t0 = time.perf_counter()
    runs, same = {}, {}
    for use, name, text, ref in PLAN:
        plan = R7.smoke_plan(use, R6.parse_seeds(a.smoke), a.smoke_steps) if a.smoke else R7.use_plan(use)
        runs[name] = run_one(info, plan, name, text, a.workers, a.out_dir)
        if not a.smoke:
            same[name] = same_as(runs[name], R7.OUT / f"{ref}.json")
            if same[name].get("ok") is not True:
                raise SystemExit(f"{name}: 다시 돌린 판이 {ref}.json 과 다르다 — {same[name]}")
    an_c = analyse(runs, "check_route0", [k for _, k, _, _ in PLAN if k.startswith("check_") and k != "check_route0"])
    an_s = analyse(runs, "select_route0", [k for _, k, _, _ in PLAN if k.startswith("select_") and k != "select_route0"])
    wall = sum(float(r["meta"].get("wall_s", 0.0)) for r in runs.values())
    meta = dict(tool=tool_sha(), wall=f"판 {len(runs)} 개 합 {wall / 60:.1f} 분 (워커 {a.workers})",
                same=("같음 (판 6 개 모두 세계마다 시작·다시 도망·쫓긴·숨음·잡힘·굶음·산이 같다)" if same and all(v.get("ok") for v in same.values())
                      else "보지 않음 (스모크)"),
                runs={k: dict(model=v["meta"]["model"], model_sha1=v["meta"]["model_sha1"], use=v["meta"]["use"], sets=v["meta"]["sets"],
                              wall_s=v["meta"]["wall_s"]) for k, v in runs.items()})
    text = fmt(an_c, an_s, meta)
    print(text)
    if not a.smoke:
        MD.write_text(text, encoding="utf-8")
        JS.write_text(json.dumps(lv.jsonable(dict(meta=meta, check=an_c, select=an_s)), ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
        print(f"→ {lv.path_text(MD)} · {lv.path_text(JS)} ({(time.perf_counter() - t0) / 60:.1f} 분)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

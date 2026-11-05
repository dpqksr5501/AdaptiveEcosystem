"""R5 장애물 관측 — 언리얼 C++ 와 파이썬 대조 (10-19, 계약 AdaptiveEcosystem/Docs/RL_Policy/POLICY_CONTRACT_V3.md 2-4).

    # herbivore_rl/ 에서 (언리얼 헤드리스 기록을 먼저 만든다 — 아래 '기록 만들기')
    python results/v3/r5/unreal_parity.py --logs <폴더> --parity s20000_zero s20010_zero s20000_baseprobe \
        --same s20000_base:s20000_zero s20000_base:s20000_baseprobe --out results/v3/r5/unreal_parity

두 가지를 본다.
  (1) 관측 대조: 통합 v3 모드 기록 '[EcoV3Obs]'(eco.IntegratedV3.ObsParityLog — 전역 스텝 N 개마다 산 사슴마다 한 줄: 자리·heading·위협을 앎·away·가장
      가까운 위협 자리 → C++ 의 E·N·가림·관측 세 칸 float 비트, 지역마다 원판 줄 하나)를 읽어, 같은 입력으로 파이썬 env_v2/world.py `obstacle_obs_values` 와
      `_obs_from` 의 세 칸 식을 다시 돌려 비트 단위로 견준다. 같이 보는 것:
        - away = 가장 가까운 위협 자리에서 다시 잰 −(j − p) ÷ max(|j − p|, 1e-9) (파이썬 `_geometry` 와 같은 식) — 위협 지각과 입력이 맞물리는가
        - 원판 = 파이썬 거울의 나무 배치 표(results/v3/wild2/trees/tree_layout.json, 무대 단위) — 언리얼 세계의 원판이 거울과 같은가
  (2) 결정 기록 같음: 두 판(예: 내장 두뇌 대 관측 21 새 열 0 두뇌)의 '[EcoV3I]' 기록 줄이 두뇌 id·결정 스텝 CPU 칸·설정 줄 '사슴 두뇌:'·'두뇌 시작' 말고
      모두 같은가 (같은 세션 시드).

기록 만들기 (편집기를 닫고, 빌드한 뒤 — 사슴 128, 241 초, 기본값 = 레벨 나무 + 날씨):
    UnrealEditor-Cmd.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=<S>
        [-EcoV3Brain=v3_r1_g995_s3_obs21zero] [-EcoV3ObsParityLog=75] -benchmark -fps=60 -seconds=241 -NullRHI -NoSound -unattended -nosplash -nopause
        -DisablePlugins=Bridge,Fab -abslog=<폴더>/<이름>_full.log
    10-29 부터 두뇌 인수가 없으면 기본 두뇌 R7e(관측 24)다 — 내장 R1b-F 판은 -EcoV3Brain=builtin 을 붙인다 (LIVE_ADAPT_SPEC.md 5.6).
출력: <out>.json (판마다 셈·처음 어긋남), <out>.md (표).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

LAYOUT = ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json"
EPS = 1e-9

# 숲 시야 칸 '| 잎 켬 r block 나무표 ' (10-22 — 켬 0/1, 반지름·문턱 단위 %.17g, 원판마다 나무 0/1 글자, 원판 없으면 '-')는 그 뒤 기록부터 있다. 옛 기록은 없음 = 끔
RE_DISC = re.compile(r"\[EcoV3Obs\] (\S+) 원판 \| 원판 (\d+) \| 몸 (\S+) \| 무대 (\S+) \| 가림 (\d) \| 두뇌 (\S+) 관측 (\d+) \| 분모 (\S+) (\S+) "
                     r"(?:\| 잎 (\d) (\S+) (\S+) (\S+) )?\|(.*)$")
RE_ROW = re.compile(r"\[EcoV3Obs\] (\S+) \| t (\d+) \| id (\d+) \| p (\S+) (\S+) \| h (\S+) (\S+) \| seen (\d) \| a (\S+) (\S+) \| j (\S+) (\S+) \| "
                    r"E (\S+) \| N (\S+) \| hid (\d) \| o ([0-9a-f]{8}) ([0-9a-f]{8}) ([0-9a-f]{8})")
RE_DIGEST = re.compile(r"\[EcoV3Obs\] (\S+) 결정 \| t (\d+) \| 사슴·스텝 (\d+) \| 지문 ([0-9a-f]{16})")
RE_STAMP = re.compile(r"^\[[^\]]*\]\[[^\]]*\]")
RE_BRAIN = re.compile(r"v3_[A-Za-z0-9_]+@[0-9a-f]{8}")
RE_CPU = re.compile(r"결정 스텝 CPU\(모든 지역\) 평균 [0-9.]+ ms/스텝, 최대 [0-9.]+ ms/프레임")


def _f(s: str) -> float:
    return float(s)


def find_log(folder: Path, name: str) -> Path:
    """<이름>_full.log (헤드리스 -abslog), 또는 저장소에 올린 고른 줄 <이름>.log·<이름>.log.gz."""
    for cand in (f"{name}_full.log", f"{name}.log", f"{name}.log.gz"):
        if (folder / cand).exists():
            return folder / cand
    raise SystemExit(f"{folder} 에 {name} 기록이 없다")


def log_lines(path: Path) -> list[str]:
    if path.suffix == ".gz":
        import gzip

        return gzip.decompress(path.read_bytes()).decode("utf-8", errors="replace").splitlines()
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def read_parity(path: Path) -> dict:
    """한 기록의 원판 줄(지역마다)과 사슴 줄."""
    discs, rows = {}, []
    for line in log_lines(path):
        if "[EcoV3Obs]" not in line:
            continue
        m = RE_DISC.search(line)
        if m:
            reg = m.group(1)
            d = [tuple(_f(x) for x in tok.split(",")) for tok in m.group(14).split()]
            if len(d) != int(m.group(2)):
                raise SystemExit(f"{path.name} {reg}: 원판 수 {m.group(2)} 인데 {len(d)} 개를 읽었다")
            foliage = None
            if m.group(10) == "1":                    # 숲 시야 켬 — 잎 원 중심 = 나무 원판 (C++ ObstacleObsInputOf 와 같은 표)
                trees = m.group(13)
                if len(trees) != len(d) or set(trees) - {"0", "1"}:
                    raise SystemExit(f"{path.name} {reg}: 숲 시야 나무 표 {trees!r} 가 원판 {len(d)} 개와 맞지 않는다")
                foliage = dict(trees=np.array([c == "1" for c in trees], dtype=bool), r=_f(m.group(11)), block=_f(m.group(12)))
            discs[reg] = dict(discs=np.array(d, dtype=np.float64).reshape(-1, 3), body_r=_f(m.group(3)), size=_f(m.group(4)),
                              block=m.group(5) == "1", brain=m.group(6), obs_dim=int(m.group(7)), escape_norm=_f(m.group(8)),
                              near_norm=_f(m.group(9)), foliage=foliage)
            continue
        m = RE_ROW.search(line)
        if m:
            g = m.groups()
            rows.append(dict(region=g[0], t=int(g[1]), id=int(g[2]), p=(_f(g[3]), _f(g[4])), h=(_f(g[5]), _f(g[6])), seen=g[7] == "1",
                             a=(_f(g[8]), _f(g[9])), j=(_f(g[10]), _f(g[11])), E=_f(g[12]), N=_f(g[13]), hid=g[14] == "1",
                             o=tuple(int(x, 16) for x in g[15:18])))
    return dict(discs=discs, rows=rows)


def _bits64(x: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(x, dtype=np.float64).view(np.uint64)


def check_parity(name: str, log: dict, layout: dict) -> dict:
    """파이썬으로 다시 잰다 (지역마다 한 번에)."""
    from env_v2.world import obstacle_obs_values

    out = dict(name=name, rows=len(log["rows"]), regions={}, bad=0, first_bad=None)
    lay = {r["region"]: np.array(r["discs"], dtype=np.float64).reshape(-1, 3) for r in layout["regions"]}
    for reg, meta in sorted(log["discs"].items()):
        rows = [r for r in log["rows"] if r["region"] == reg]
        n = len(rows)
        P = np.array([r["p"] for r in rows], dtype=np.float64).reshape(-1, 2)
        H = np.array([r["h"] for r in rows], dtype=np.float64).reshape(-1, 2)
        seen = np.array([r["seen"] for r in rows], dtype=bool)
        A = np.array([r["a"] for r in rows], dtype=np.float64).reshape(-1, 2)
        J = np.array([r["j"] for r in rows], dtype=np.float64).reshape(-1, 2)
        D = meta["discs"]
        fo = meta.get("foliage")
        fol = None if fo is None else (D[fo["trees"], :2], fo["r"], fo["block"])   # 숲 시야 켠 판: 가림 = 줄기 ∨ 잎 (world.py foliage 인자)
        e, nn, hid = obstacle_obs_values(P, H, seen, A, J, D, meta["body_r"], meta["size"], meta["block"], foliage=fol)
        o = np.empty((n, 3), dtype=np.float32)          # world.py `_obs_from` 세 칸 (float64 → float32)
        o[:, 0] = np.clip(e / meta["escape_norm"], 0.0, 1.0)
        o[:, 1] = np.clip(np.maximum(nn, 0.0) / meta["near_norm"], 0.0, 1.0)
        o[:, 2] = np.where(hid, 1.0, 0.0)
        cE = np.array([r["E"] for r in rows], dtype=np.float64)
        cN = np.array([r["N"] for r in rows], dtype=np.float64)
        cH = np.array([r["hid"] for r in rows], dtype=bool)
        cO = np.array([r["o"] for r in rows], dtype=np.uint32).reshape(-1, 3)
        okE = _bits64(e) == _bits64(cE)
        okN = _bits64(nn) == _bits64(cN)
        okH = hid == cH
        okO = (o.view(np.uint32) == cO).all(1)
        # away = 가장 가까운 위협 자리에서 다시 잰 단위벡터 (world.py _geometry: away = −[ex, ey] · 1/max(pd, EPS))
        ex, ey = J[:, 0] - P[:, 0], J[:, 1] - P[:, 1]
        pinv = 1.0 / np.maximum(np.sqrt(ex * ex + ey * ey), EPS)
        aw = np.stack([-ex * pinv, -ey * pinv], 1)
        okA = np.where(seen, (_bits64(aw) == _bits64(A)).all(1), (A == 0.0).all(1))
        ok = okE & okN & okH & okO & okA
        bad = int((~ok).sum())
        if bad and out["first_bad"] is None:
            k = int(np.flatnonzero(~ok)[0])
            out["first_bad"] = dict(region=reg, row=rows[k], py=dict(E=float(e[k]), N=float(nn[k]), hid=bool(hid[k]), o=o[k].view(np.uint32).tolist(),
                                                                     away=aw[k].tolist()))
        out["bad"] += bad
        ld = lay.get(reg)
        same_layout = ld is not None and ld.shape == D.shape and bool((_bits64(ld) == _bits64(D)).all())
        known = seen.sum()
        oo = cO.view(np.float32)
        out["regions"][reg] = dict(
            rows=n, bad=bad, bad_E=int((~okE).sum()), bad_N=int((~okN).sum()), bad_hidden=int((~okH).sum()), bad_obs=int((~okO).sum()),
            bad_away=int((~okA).sum()), discs=int(len(D)), discs_equal_layout=same_layout, body_r=meta["body_r"], size=meta["size"],
            block_sight=meta["block"], foliage=None if fo is None else dict(r=fo["r"], block=fo["block"], trees=int(fo["trees"].sum())),
            brain=meta["brain"], obs_dim=meta["obs_dim"], steps=len({r["t"] for r in rows}),
            known=int(known), hidden=int(cH.sum()), near_lt1=int((oo[:, 1] < 1.0).sum()), near_lt1_known=int(((oo[:, 1] < 1.0) & seen).sum()),
            escape_zero=int((oo[:, 0] == 0.0).sum()), escape_one=int((oo[:, 0] == 1.0).sum()),
            escape_mean_known=float(oo[seen, 0].mean()) if known else None,
            near_min=float(np.min(np.where(np.isinf(cN), np.nan, cN), initial=np.inf)) if np.isfinite(cN).any() else None)
    return out


def norm_v3i(path: Path, tag: str = "[EcoV3I]") -> list[str]:
    """'[EcoV3I]' 줄을 시각·두뇌 id·CPU 칸을 지운 꼴로. 설정 줄 '사슴 두뇌:'·'두뇌 시작'은 뺀다 (두뇌를 밝히는 줄이다).
    tag '[EcoV3Obs]' 면 사슴 줄만 (원판 줄은 두뇌 id·관측 칸 수를 적으므로 뺀다)."""
    out = []
    for line in log_lines(path):
        if tag not in line or (tag == "[EcoV3Obs]" and " 원판 |" in line):
            continue
        s = RE_STAMP.sub("", line)
        if "[EcoV3I] 사슴 두뇌:" in s or "[EcoV3I] 두뇌 시작" in s:
            continue
        s = RE_CPU.sub("결정 스텝 CPU …", RE_BRAIN.sub("<두뇌>", s))
        out.append(s)
    return out


def compare_same(a: Path, b: Path) -> dict:
    la, lb = norm_v3i(a), norm_v3i(b)
    diff = [i for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    first = None
    if diff:
        first = dict(line=diff[0], a=la[diff[0]][:300], b=lb[diff[0]][:300])
    brain_lines = sum(1 for s in la if " 두뇌 | " in s)
    # 두 판 모두 관측 대조 줄이 있으면 그것도 같아야 한다 (같은 세계 → 같은 세 칸)
    oa, ob = norm_v3i(a, "[EcoV3Obs]"), norm_v3i(b, "[EcoV3Obs]")
    obs_differ = None
    if oa and ob:
        obs_differ = sum(1 for x, y in zip(oa, ob) if x != y) + abs(len(oa) - len(ob))
    # 결정 지문 (스텝마다 사슴마다 id·읽음·마스크·요청·로짓 비트·실행 행동 — 시작부터 누적): 마지막 줄의 지역마다 값
    da = [RE_DIGEST.search(x).groups() for x in oa if RE_DIGEST.search(x)]
    db = [RE_DIGEST.search(x).groups() for x in ob if RE_DIGEST.search(x)]
    digest = None
    if da and db:
        last_a = {g[0]: (int(g[1]), int(g[2]), g[3]) for g in da}
        last_b = {g[0]: (int(g[1]), int(g[2]), g[3]) for g in db}
        digest = dict(lines=[len(da), len(db)], equal=da == db, last=last_a, decisions=sum(v[1] for v in last_a.values()))
    return dict(a=a.name, b=b.name, lines=[len(la), len(lb)], differ=len(diff) + abs(len(la) - len(lb)), first=first, brain_lines=brain_lines,
                obs_rows=[len(oa), len(ob)], obs_differ=obs_differ, digest=digest)


def write_md(path: Path, res: dict) -> None:
    L = ["# R5 장애물 관측 — 언리얼 대 파이썬 대조 (자동 생성 — results/v3/r5/unreal_parity.py)", ""]
    L.append("## 관측 대조 ('[EcoV3Obs]' 줄을 파이썬 obstacle_obs_values 로 다시 잼, 비트 단위)")
    L.append("")
    L.append("| 판 | 지역 | 두뇌 관측 | 줄 | 스텝 | 어긋남 (E·N·가림·세 칸·away) | 원판 = 거울 표 | 위협을 앎 | 가림 1 | 10 m 안 원판 | escape 0 · 1 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for p in res["parity"]:
        for reg, r in sorted(p["regions"].items()):
            L.append(f"| {p['name']} | {reg} | {r['obs_dim']} | {r['rows']} | {r['steps']} | {r['bad']} ({r['bad_E']}·{r['bad_N']}·{r['bad_hidden']}·{r['bad_obs']}·"
                     f"{r['bad_away']}) | {'같음' if r['discs_equal_layout'] else '다름'} ({r['discs']}) | {r['known']} | {r['hidden']} | {r['near_lt1']} | "
                     f"{r['escape_zero']} · {r['escape_one']} |")
    L.append("")
    L.append("## 결정 기록 같음 ('[EcoV3I]' 줄 — 두뇌 id·CPU 칸·설정 줄 '사슴 두뇌:'·'두뇌 시작' 뺌)")
    L.append("")
    L.append("| 판 A | 판 B | 줄 (A·B) | 다른 줄 | 두뇌 기록 줄 | 관측 대조 줄 (A·B) · 다른 줄 | 결정 지문 (사슴·스텝, 같음) |")
    L.append("|---|---|---|---|---|---|---|")
    for s in res["same"]:
        ob = "-" if s["obs_differ"] is None else f"{s['obs_rows'][0]}·{s['obs_rows'][1]} · {s['obs_differ']}"
        dg = "-" if not s["digest"] else f"{s['digest']['decisions']} · {'같음' if s['digest']['equal'] else '다름'} ({s['digest']['lines'][0]} 줄)"
        L.append(f"| {s['a']} | {s['b']} | {s['lines'][0]}·{s['lines'][1]} | {s['differ']} | {s['brain_lines']} | {ob} | {dg} |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="R5 장애물 관측 언리얼 대 파이썬 대조")
    p.add_argument("--logs", required=True, help="<이름>_full.log 가 있는 폴더")
    p.add_argument("--parity", nargs="*", default=[], help="관측 대조할 판 이름 (ObsParityLog 를 켠 판)")
    p.add_argument("--same", nargs="*", default=[], help="A:B — 결정 기록이 같아야 하는 두 판")
    p.add_argument("--out", default=None, help="출력 앞 이름 (.json·.md)")
    a = p.parse_args(argv)
    logs = Path(a.logs)
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    res = dict(parity=[], same=[])
    for name in a.parity:
        r = check_parity(name, read_parity(find_log(logs, name)), layout)
        res["parity"].append(r)
        print(f"{name}: 줄 {r['rows']} 어긋남 {r['bad']} | " + " · ".join(
            f"{reg} {x['rows']} (앎 {x['known']}, 가림 {x['hidden']}, 원판 {x['discs']} 표와 {'같음' if x['discs_equal_layout'] else '다름'})"
            for reg, x in sorted(r["regions"].items())))
        if r["first_bad"]:
            print("  처음 어긋남:", r["first_bad"])
    for pair in a.same:
        x, y = pair.split(":")
        s = compare_same(find_log(logs, x), find_log(logs, y))
        res["same"].append(s)
        print(f"{x} 대 {y}: 줄 {s['lines']} 다른 줄 {s['differ']}" + ("" if s["obs_differ"] is None else f" · 관측 대조 줄 {s['obs_rows']} 다른 줄 {s['obs_differ']}")
              + ("" if not s["digest"] else f" · 결정 지문 사슴·스텝 {s['digest']['decisions']} {'같음' if s['digest']['equal'] else '다름'}")
              + (f" — 처음 {s['first']}" if s["first"] else ""))
    if a.out:
        out = Path(a.out)
        out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
        write_md(out.with_suffix(".md"), res)
    bad = sum(r["bad"] for r in res["parity"]) + sum(s["differ"] + (s["obs_differ"] or 0) + (0 if not s["digest"] or s["digest"]["equal"] else 1)
                                                  for s in res["same"])
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

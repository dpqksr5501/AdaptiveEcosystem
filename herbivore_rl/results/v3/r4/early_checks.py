"""v3 R4 조기 중단 점검을 체크포인트가 생기는 대로 돌린다 (사전 등록 PREREG.md 5절 — 판정 아님, 멈춤 판단은 사람이 이 기록을 보고 한다).

    # herbivore_rl/ 에서 (학습과 함께 띄운다 — launch 는 STATUS.md)
    python results/v3/r4/early_checks.py --seeds 0 1 2 3 4 5 --at 2 5

시드·체크포인트(2M·5M)마다 `ckpt/v3/v3_r4_g995_s<시드>_20m_<k>m.zip` 이 생길 때까지 기다렸다가(파일 크기가 두 번 같으면 다 쓴 것으로 본다)
`r4_eval.run`(점검 세계 32050~32059 × 지역 셋 × 16분, 워커 --workers) → `r4_eval.check`(기준 판 runs/early_base.json) 를 하고
runs/early_s<시드>_<k>m.json 과 logs/check_s<시드>_<k>m.txt 를 쓴다. 끝에 logs/early_checks.json(시드·k → 멈춤·규칙) 을 쓴다. 학습 프로세스를 건드리지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
for p in (HERE.parent, ROOT, ROOT / "results" / "v3" / "mirror"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import r4_eval as E  # noqa: E402

CK = ROOT / "ckpt" / "v3"
CHECK_SEEDS = list(range(32050, 32060))


def wait_file(path: Path, timeout_s: float) -> bool:
    t0, last = time.time(), -1
    while time.time() - t0 < timeout_s:
        if path.exists():
            n = path.stat().st_size
            if n > 0 and n == last:
                return True
            last = n
        time.sleep(10)
    return False


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4, 5])
    ap.add_argument("--at", type=int, nargs="+", default=[2, 5], help="체크포인트(백만 스텝)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--timeout-min", type=float, default=120.0)
    a = ap.parse_args(argv)
    base = E.load(HERE.parent / "runs" / "early_base.json")
    out_all = {}
    logs = HERE.parent / "logs"
    for k in a.at:
        for s in a.seeds:
            ck = CK / f"v3_r4_g995_s{s}_20m_{k}m.zip"
            tag = f"s{s}_{k}m"
            if not wait_file(ck, a.timeout_min * 60):
                print(f"{tag}: 체크포인트 {ck.name} 가 {a.timeout_min:g}분 안에 없다 — 건너뜀", flush=True)
                out_all[tag] = dict(missing=True)
                continue
            t0 = time.time()
            res = E.run(ck, CHECK_SEEDS, 7200, a.workers)
            (HERE.parent / "runs").mkdir(exist_ok=True)
            (HERE.parent / "runs" / f"early_{tag}.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            r = E.check(res, base)
            lines = [f"{tag} ({ck.name}, {time.time() - t0:.0f}초): {'멈춤' if r['stop'] else '계속'}"]
            lines += [f"  {n}: {'걸림' if v['hit'] else '-'} ({v['text']})" for n, v in r["rules"].items()]
            p = r["run"]
            lines.append(f"  잡힘 {p['caught']:.4f} (R1b-F {r['base']['caught']:.4f}) 굶음 {p['starved']:.4f} ({r['base']['starved']:.4f}) "
                         f"산 {p['alive']:.4f} ({r['base']['alive']:.4f}) 숨기 {p['beh']['hide']:.4f} ({r['base']['beh']['hide']:.4f})")
            text = "\n".join(lines)
            (logs / f"check_{tag}.txt").write_text(text + "\n", encoding="utf-8")
            print(text, flush=True)
            out_all[tag] = dict(stop=r["stop"], rules={n: v["hit"] for n, v in r["rules"].items()},
                                run={kk: vv for kk, vv in p.items()}, base_caught=r["base"]["caught"])
            (logs / "early_checks.json").write_text(json.dumps(out_all, ensure_ascii=False, indent=1), encoding="utf-8")
    stops = sorted({t.split("_")[0] for t, v in out_all.items() if v.get("stop")})
    print(f"멈춤 시드: {stops or '없음'} ({len(stops)}개 — 3 개 이상이면 대응 1회, PREREG 5절)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""'가까운 위협 앞 얼기' 확인 시험의 판정 (results/v3/r0/PREREG.md 변경 기록 10-07 '보정 1회차 결과 ...').

invasion_r0.py run 의 FREEZE 결과(invasion.json)를 모드를 바꿔 읽는다:
  새 니치 = 기존 교차 모드(위협이 6 안이거나 빠를 때 도망 대신 얼기)
  새 교차 = 기존 니치 모드(위협이 멀고 느릴 때 얼기 — 거기서는 먹기가 이겨야 한다)
  니치 밖 = 기존 그대로
통과 = (1') 새 니치 8칸 중 5칸 이상 양수·유의 음수 0, (2') 니치 밖 5칸 이상 유의 음수, (3') 새 교차 5칸 이상 유의 음수.
판정 규칙과 문턱(T_CRIT, GATE_MIN_CELLS)은 invasion_r0.gate 를 그대로 쓴다.

    python results/v3/r0/freeze_near/judge_near.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import invasion_r0 as inv  # noqa: E402

SWAP = {"niche": "cross", "cross": "niche", "out": "out"}
EXPECT_SEEDS = list(range(12040, 12080))


def main() -> int:
    res = json.loads((HERE / "invasion.json").read_text(encoding="utf-8"))
    m = res["meta"]
    assert m["seeds"] == EXPECT_SEEDS, m["seeds"]
    assert m["config"].replace("\\", "/").endswith("configs/v3_r0_on.yaml"), m["config"]
    assert (m["theta"], m["approach"], m["steps"]) == (4.0, 0.9, 3000), m
    cells = m["cells"]
    swapped = {}
    for key, v in res["summary"].items():
        x, mode, c = key.split("|")
        if x == "freeze":
            swapped[f"freeze|{SWAP[mode]}|{c}"] = v
    out = {}
    for k in ("rew", "rew_did"):
        g = inv.gate(swapped, cells, key=k)["freeze"]
        out[k] = g
    rows = ["# '가까운 위협 앞 얼기' 확인 시험 — 판정", "",
            f"세계 `{m['config']}`, 시드 12040~12079 × {m['steps']}스텝, 거주 θ {m['theta']}·a {m['approach']}. "
            "모드를 바꿔 읽었다(새 니치 = 기존 교차, 새 교차 = 기존 니치).", "",
            "| 판정 | (1') 새 니치 양수 / 유의 음수 | (2') 니치 밖 유의 음수 | (3') 새 교차 유의 음수 | 결과 |",
            "|---|---|---|---|---|"]
    name = {"rew": "판정(보상 차)", "rew_did": "이중차(보고만)"}
    for k, g in out.items():
        rows.append(f"| {name[k]} | {g['niche_pos']}/8 · {g['niche_sig_neg']} | {g['out_sig_neg']} | "
                    f"{g['cross_sig_neg']} | {'통과' if g['pass_'] else '실패'} |")
    rows += ["", "칸별(새 니치 = 기존 교차 모드):", "", "| 칸 | 보상 차 평균 | t | 피식 차 | 얼기 사용 비율 |", "|---|---|---|---|---|"]
    for c in cells:
        v = res["summary"][f"freeze|cross|{c}"]
        t = v["rew"]["t"]
        rows.append(f"| {c} | {v['rew']['mean']:+.5f} | {'—' if t is None else f'{t:+.2f}'} | "
                    f"{v['pred']['mean']:+.5f} | {v['use_focal']:.3f} |")
    (HERE / "judge_near.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (HERE / "judge_near.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({k: {kk: g[kk] for kk in ("niche_pos", "niche_sig_neg", "out_sig_neg", "cross_sig_neg", "pass_")}
                      for k, g in out.items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

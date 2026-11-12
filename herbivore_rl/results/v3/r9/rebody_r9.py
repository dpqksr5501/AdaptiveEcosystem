"""R9 두뇌 몸 옮기기 — 같은 종 두뇌(npz)를 몸이 다른 세계로 옮기고 그 사실을 메타에 남긴다 (동물 설계
AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md 6-1).

    python -X utf8 results/v3/r9/rebody_r9.py --config configs/v3_r9_fauna.yaml --species deer \
        --src ckpt/r9_fauna/start/src/deer_r0_20013056.npz --out ckpt/r9_fauna/start/deer_v0.npz

- 같은 종 안에서만(메타 species 가 --species 와 같아야), 입출력 해시가 같아야 한다. 몸 해시 검사(`load_brain`)는 그대로다 —
  다른 몸 두뇌가 조용히 섞이는 일을 막는 검사이고, 이 도구가 그 사실을 메타 `init_from`(원래 경로·sha256·종·몸 해시·몸 표 해시·
  설정 요약)에 드러내 놓는 단 하나의 문이다.
- 결과 npz 는 --config 세계의 몸 해시를 지녀 그 세계의 `load_brain` 을 통과한다. 가중치는 한 비트도 바꾸지 않는다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env_v2 import r9_body as B  # noqa: E402
from env_v2 import r9_brains as BR  # noqa: E402


def _abs(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True, help="옮겨 갈 세계 설정 (예 configs/v3_r9_fauna.yaml)")
    ap.add_argument("--species", required=True, choices=list(B.ALL_SPECIES[:B.STAGE1_MAX_SPECIES]))
    ap.add_argument("--src", required=True, help="원래 npz (같은 종)")
    ap.add_argument("--out", required=True, help="새 npz")
    a = ap.parse_args(argv)
    cfg = B.load_r9_config(_abs(a.config))
    meta = BR.rebody_brain(_abs(a.src), cfg, a.species, _abs(a.out))
    BR.load_brain(_abs(a.out), cfg, a.species)                       # 옮긴 세계에서 실리는지 바로 확인
    print(json.dumps(dict(out=str(_abs(a.out)), species=meta["species"], body_hash=meta["body_hash"],
                          body_table_hash=meta["body_table_hash"], init_from=meta["init_from"]), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

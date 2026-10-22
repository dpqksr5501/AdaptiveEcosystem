"""동족 합 차례 (10-22) — 시험 도우미 (test_ 로 시작하지 않아 시험으로 모으지 않는다).

env_v2/world.py `_geometry` 는 10-22 부터 동족 무리 중심·분리의 j 합을 왼쪽부터 차례로 더한다(`_seq_sum` — C++ PerceiveKin 의 SumX·CX·CSum 과 같은
순서라 C++ 세계와 비트 단위로 같다). 그 전 코드(옛 커밋 사본 — 그리고 v1 env/world.py, v1 은 한 줄도 바꾸지 않는다)는 같은 두 줄을 행렬곱(MKL dgemm)·
np.sum(쌍 합)으로 더해 끝 비트(1e-15)가 다르고, 혼돈이라 수백 스텝 뒤 궤적이 갈린다. '옛 코드와 비트 동일' 시험은 옛 코드의 그 두 줄만 같은 차례 합으로
바꾼 판과 견준다(바꿈 말고는 옛 코드 그대로 — 두 줄이 정확히 한 번씩 있어야 바꾼다).
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]                  # herbivore_rl/

# 옛 두 줄 → world.py `_seq_sum`(np.cumsum(·, axis=1)[:, -1])과 같은 셈
LINES = (
    ("centroid = (kin_f @ self.pos) / np.maximum(kin_count, 1.0)[:, None]",
     "centroid = np.stack([np.cumsum(kin_f * self.pos[:, 0], axis=1)[:, -1], np.cumsum(kin_f * self.pos[:, 1], axis=1)[:, -1]], 1)"
     " / np.maximum(kin_count, 1.0)[:, None]"),
    ("separation = clamp_magnitude(-((c @ self.pos) - c.sum(1)[:, None] * P), 1.0)",
     "separation = clamp_magnitude(-(np.stack([np.cumsum(c * self.pos[:, 0], axis=1)[:, -1], np.cumsum(c * self.pos[:, 1], axis=1)[:, -1]], 1)"
     " - np.cumsum(c, axis=1)[:, -1][:, None] * P), 1.0)"),
)


def patch_source(src: str) -> str:
    """옛 world.py 원문의 동족 두 줄을 차례 합으로 바꾼다. 두 줄이 정확히 한 번씩 없으면 거부한다."""
    for old, new in LINES:
        if src.count(old) != 1:
            raise ValueError(f"동족 줄이 한 번이 아니다 ({src.count(old)}): {old}")
        src = src.replace(old, new)
    return src


def patch_tree(root: Path | None) -> Path | None:
    """git archive 로 푼 옛 herbivore_rl 사본(root)의 env_v2/world.py 에 차례 합을 넣는다. root 가 None 이면 그대로 (archive 실패 — 시험이 건너뛴다)."""
    if root is not None:
        p = Path(root) / "env_v2" / "world.py"
        p.write_text(patch_source(p.read_text(encoding="utf-8")), encoding="utf-8")
    return root


def world_v1():
    """v1 env/world.py 의 World 를 동족 차례 합으로 바꾼 사본 클래스 (env/world.py 는 고치지 않는다 — 원문을 읽어 다른 모듈 이름으로 싣는다).
    v2 의 '기능을 모두 끄면 v1 과 비트 동일' 시험이 쓴다."""
    name = "env._world_v1_kin_seq"
    mod = sys.modules.get(name)
    if mod is None:
        import env  # noqa: F401  ← 상대 import(.steering)를 env 꾸러미에서 찾는다

        path = ROOT / "env" / "world.py"
        mod = types.ModuleType(name)
        mod.__file__, mod.__package__ = str(path), "env"
        sys.modules[name] = mod
        exec(compile(patch_source(path.read_text(encoding="utf-8")), str(path), "exec"), mod.__dict__)
    return mod.World

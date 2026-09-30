"""torch를 쓰는 진입점(warmstart / train / tune_ppo)에서 **가장 먼저** import할 것.

    import env.torch_init  # noqa: F401  ← 다른 어떤 import보다 위

## 왜 필요한가

Anaconda 환경에 Intel OpenMP 런타임이 두 벌 있다:

    <anaconda>/Library/bin/libiomp5md.dll        ← MKL (numpy가 싣는다)
    <anaconda>/Lib/site-packages/torch/lib/...   ← torch가 싣는다

numpy를 먼저 import하면 MKL이 첫 번째를 싣고, 이어서 torch가 두 번째를 실으면서
`OMP: Error #15` 로 죽는다.

## 무엇을 했나

`KMP_DUPLICATE_LIB_OK=TRUE` 는 Intel이 "unsafe, unsupported" 라고 명시한 우회책이다.
그 경고가 가리키는 실제 위험은 **두 런타임이 각자 스레드 풀을 만들어 경합**하는 것이다.
그래서 플래그만 켜지 않고 **스레드 수를 1로 고정**한다. 병렬 영역이 없으면 경합할 것도
없다.

성능 손해도 없다. 이 프로젝트의 텐서는 7-64-64-4 MLP와 (128,7) 배치라 BLAS 스레딩이
이미 순손해다 (`env/rollout.py` 워커에서도 같은 이유로 1로 묶었다).

torch 설치 파일을 지우거나 바꾸지 않았다. 사용자의 다른 conda 환경에 영향을 주지 않기
위해서다.
"""

from __future__ import annotations

import os

# 반드시 numpy/torch가 DLL을 싣기 전에 설정되어야 한다.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
for _var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import torch  # noqa: E402

torch.set_num_threads(1)
torch.set_num_interop_threads(1) if torch.get_num_interop_threads() != 1 else None

__all__ = ["torch"]

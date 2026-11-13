#!/usr/bin/env bash
# R9 학습 환경 만들기 — 리눅스, sudo 없이 (안내 AdaptiveEcosystem/Docs/RL_Policy/R9_CLOUD_TRAINING.md 2 절).
#
#   bash herbivore_rl/results/v3/r9/cloud_setup.sh          (어느 폴더에서 불러도 됨)
#
# - herbivore_rl/.venv-r9/ 에 가상 환경 + CPU torch + requirements-r9.txt. 이미 있으면 빠진 것만 깐다(다시 불러도 됨).
# - python3 -m venv 가 안 되면(데비안·우분투에 python3-venv 가 없을 때 흔함) uv 를 ~/.local/bin 에 받아 쓴다. 인터넷만 있으면 되고 sudo 는 필요 없다.
# - 끝에 chain_r9.py check (환경·팩·자원 확인)를 돌린다.
# 바꿀 수 있는 값: R9_VENV(가상 환경 폴더) · R9_PYTHON_VERSION(uv 가 쓸 파이썬, 기본 3.12) · R9_CHECK_CONFIG(확인할 설정).
set -euo pipefail
cd "$(dirname "$0")/../../.."                    # herbivore_rl/
VENV=${R9_VENV:-.venv-r9}
PYVER=${R9_PYTHON_VERSION:-3.12}
CHECK_CONFIG=${R9_CHECK_CONFIG:-configs/v3_r9_fauna_motion.yaml}
TORCH="torch==2.11.0"
TORCH_INDEX=https://download.pytorch.org/whl/cpu
export PATH="$HOME/.local/bin:$PATH"
have() { command -v "$1" >/dev/null 2>&1; }
need_uv() {
  if ! have uv; then
    echo "[setup] uv 받기 (~/.local/bin)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
  fi
}

if [ ! -x "$VENV/bin/python" ]; then
  if python3 -m venv "$VENV" >/dev/null 2>&1 && "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
    echo "[setup] 가상 환경: python3 -m venv ($("$VENV/bin/python" --version))"
  else
    echo "[setup] python3 -m venv 를 못 씀 (ensurepip 없음 등) — uv 로 만든다"
    rm -rf "$VENV"
    need_uv
    uv venv --python "$PYVER" "$VENV"
  fi
fi
PY="$VENV/bin/python"
if "$PY" -m pip --version >/dev/null 2>&1; then
  INSTALL=("$PY" -m pip install --disable-pip-version-check)
else
  need_uv
  INSTALL=(uv pip install --python "$PY")
fi
if ! "$PY" -c "import torch" >/dev/null 2>&1; then
  echo "[setup] CPU torch 깔기"
  "${INSTALL[@]}" --index-url "$TORCH_INDEX" "$TORCH"
fi
"${INSTALL[@]}" -r requirements-r9.txt
echo "[setup] 파이썬: $(cd "$(dirname "$PY")" && pwd)/python"
PYTHONUTF8=1 "$PY" -X utf8 results/v3/r9/chain_r9.py check --pack results/v3/r9/packs/fauna_r2 --config "$CHECK_CONFIG"

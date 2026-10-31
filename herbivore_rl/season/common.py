"""시즌 파이프라인 공용 값과 설정 읽기 (SEASON 4.1, 4.2, 5.4).

- 경로: 학습·평가 산출물은 `runs/season/`(gitignore 대상), 요약은 `results/season/` 에 둔다(SEASON 4.1).
- 앵커: SR1 은 v1 `ckpt/final.zip` 과 v2.0 s0 20M `ckpt/v2/v2_0_s0.zip` 을 비교한다(SEASON 5.4). 앵커는 git 밖 단일
  파일이라 sha1 앞 12자리를 여기에 적고 실행기가 시작할 때 확인한다(#S15 추천값). v1 값은 SEASON 1.5 의 값이고,
  v2.0 s0 값은 2026-10-07 에 잰 값이다.
- 시드: 평가 10000~10019, 보류 10020~10039 (SEASON 4.2). 학습 세계 시드 풀 [0, 1000) 과 겹치지 않는다.
- 시즌 설정: SR1 의 합성 시즌은 `overrides.rand` 만 바꾼다(SEASON 4.1 허용 키). 기능은 켜지 않는다. 범위는 기본 범위
  안이어야 한다. `train` 블록은 B 와 같게 적는다(G 묶음과 B 묶음의 교체 주기·세계 고르기가 같아야 한다). 이 검사는 SR2
  변환기(범위 밖 값을 잘라 기록)와 달리 잘라 주지 않고 멈춘다.
- 코드 지문(`sim_digest`): 다른 작업이 `env_v2/` 를 계속 고치므로 평가 캐시 키와 학습 기록에 시뮬레이터·정책 코드의
  지문을 넣는다. 코드가 바뀌면 캐시한 앵커·K2-B 행을 다시 잰다(짝지은 t 는 같은 코드의 같은 세계를 전제로 한다).
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from env.config import DEFAULT_CONFIG
from env_v2.config import V2_CONFIG, load_v2_config

H = Path(__file__).resolve().parent.parent
SEASON_DIR = Path(__file__).resolve().parent / "seasons"
RUNS = H / "runs" / "season"
RESULTS = H / "results" / "season"
BASE_CONFIG = V2_CONFIG                         # B: configs/v2.yaml (기능이 모두 꺼진 v2.0, SEASON 4.1)
PPO_CONFIG = H / "configs" / "ppo_best.yaml"

ANCHORS = {
    "v1": H / "ckpt" / "final.zip",
    "v20": H / "ckpt" / "v2" / "v2_0_s0.zip",
}
ANCHOR_SHA1 = {
    "v1": "2f4d57e33107",       # SEASON 1.5 (컴파일된 v0 과 같은 가중치)
    "v20": "c4f52bb6e661",      # 2026-10-07 측정
}

SEASONS = {
    "a": SEASON_DIR / "season_a.yaml",      # 포식자가 많고 빠르다
    "b": SEASON_DIR / "season_b.yaml",      # 포식자가 적고 느리다
    "c": SEASON_DIR / "season_c.yaml",      # 땅이 넓고 원거리형이 많다
}

EVAL_SEEDS = tuple(range(10000, 10020))
HOLDOUT_SEEDS = tuple(range(10020, 10040))
EVAL_STEPS = 5000
SR1_STEPS = 2_000_000           # 시드당 학습량 (SEASON 4.1, 실제 2,031,616 timestep)
SR1_SEEDS = (0, 1)              # 통과 규칙의 학습 시드 2개 (SEASON 5.4)

# SR1 시즌 설정이 바꿀 수 있는 v1 키. rand 하위 키 6개만이다.
ALLOWED_OVERRIDE_KEYS = frozenset({"rand"})


def resolve_anchor(name_or_path: str) -> tuple[str, Path]:
    """앵커 이름(v1, v20) 또는 zip 경로 → (태그, 절대 경로). 경로면 태그는 파일 이름 줄기다."""
    if name_or_path in ANCHORS:
        return name_or_path, ANCHORS[name_or_path]
    p = Path(name_or_path)
    if not p.is_absolute():
        p = (H / p) if (H / p).exists() else p.resolve()
    for tag, path in ANCHORS.items():
        if p.resolve() == path.resolve():
            return tag, path
    return p.stem, p


def resolve_season(name_or_path: str) -> tuple[str, Path]:
    """시즌 이름(a, b, c) 또는 yaml 경로 → (태그, 경로). 경로면 태그는 파일 이름 줄기다."""
    if name_or_path in SEASONS:
        return name_or_path, SEASONS[name_or_path]
    p = Path(name_or_path)
    if not p.is_absolute() and not p.exists() and (H / p).exists():
        p = H / p
    return p.stem.replace("season_", ""), p


def check_season_yaml(path: str | Path) -> dict:
    """시즌 yaml 을 읽어 SR1 허용 규칙을 검사하고 원본 dict 를 돌려준다. 어기면 ValueError.

    - overrides 의 키는 ALLOWED_OVERRIDE_KEYS(rand) 뿐이다
    - rand 하위 키 6개를 모두 적는다. 각 값은 [lo, hi] 이고 lo ≤ hi 이며 기본 범위 안이다
    - features 는 비어 있다 (켠 기능이 있으면 B 와 관측·행동이 달라져 같은 앵커로 이어 학습할 수 없다)
    """
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    with open(DEFAULT_CONFIG, encoding="utf-8") as f:
        base_rand = yaml.safe_load(f)["rand"]
    over = raw.get("overrides") or {}
    bad = sorted(set(over) - ALLOWED_OVERRIDE_KEYS)
    if bad:
        raise ValueError(f"{path}: SR1 시즌은 overrides.rand 만 바꾼다. 허용하지 않는 키: {bad}")
    rand = over.get("rand") or {}
    missing = sorted(set(base_rand) - set(rand))
    if missing:
        raise ValueError(f"{path}: rand 하위 키 6개를 모두 적는다. 빠진 키: {missing}")
    unknown = sorted(set(rand) - set(base_rand), key=str)
    if unknown:
        raise ValueError(f"{path}: rand 에 기본 설정에 없는 하위 키가 있다: {unknown}")
    for k, (lo, hi) in rand.items():
        blo, bhi = base_rand[k]
        if not (blo <= lo <= hi <= bhi):
            raise ValueError(f"{path}: rand.{k} = [{lo}, {hi}] 는 기본 범위 [{blo}, {bhi}] 안이어야 한다")
    if raw.get("features"):
        raise ValueError(f"{path}: SR1 시즌은 기능을 켜지 않는다. 받은 값: {raw['features']!r}")
    with open(BASE_CONFIG, encoding="utf-8") as f:
        base_train = (yaml.safe_load(f) or {}).get("train")
    if raw.get("train") != base_train:
        raise ValueError(f"{path}: train 블록은 B({BASE_CONFIG.name})와 같아야 한다. "
                         f"받은 값: {raw.get('train')!r}, B: {base_train!r}")
    return raw


SIM_DIRS = ("env", "env_v2", "policies")


def sim_digest() -> str:
    """시뮬레이터·평가 정책 코드(`env/`, `env_v2/`, `policies/` 의 .py)의 sha1 앞 12자리. 주석만 바꿔도 달라진다."""
    h = hashlib.sha1()
    for d in SIM_DIRS:
        for p in sorted((H / d).glob("*.py")):
            h.update(p.relative_to(H).as_posix().encode() + b"\0")
            h.update(p.read_bytes())
    return h.hexdigest()[:12]


def load_season(path: str | Path):
    """시즌 yaml → Config (G). 허용 규칙을 먼저 검사한다."""
    check_season_yaml(path)
    return load_v2_config(path)


def load_base(path: str | Path | None = None):
    """B 설정 → Config. 기본은 configs/v2.yaml 이다."""
    return load_v2_config(path if path is not None else BASE_CONFIG)


def method_tag(method: str, kl_coef: float | None = None) -> str:
    """방식 → 파일 이름 조각. M3 은 KL 계수를 붙인다(0.1 → m3k0p1)."""
    m = method.lower()
    if method == "M3":
        return f"{m}k{format(float(kl_coef), 'g').replace('.', 'p')}"
    return m


def run_name(anchor_tag: str, season_tag: str | None, mtag: str, seed: int, steps: int = SR1_STEPS) -> str:
    """실행 이름. K2-B(시즌 없음)는 시즌 자리에 k2b 를 쓴다. 학습량이 2M 이 아니면 끝에 붙인다."""
    tail = "" if steps == SR1_STEPS else f"_{steps // 1000}k"
    return f"{anchor_tag}_{season_tag or 'k2b'}_{mtag}_s{seed}{tail}"


def train_path(anchor_tag: str, season_tag: str | None, mtag: str, seed: int, steps: int = SR1_STEPS,
               root: Path | None = None) -> Path:
    """후보 zip 경로. K2-B 는 (앵커, 방식, 시드)마다 하나라 시즌이 바뀌어도 같은 파일을 쓴다(SEASON 4.1 캐시)."""
    return (root or RUNS / "sr1" / "train") / f"{run_name(anchor_tag, season_tag, mtag, seed, steps)}.zip"

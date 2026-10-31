"""판정 평가 세계와 평가 묶음 (SEASON 4.2).

세 세계:
- G: 시즌 설정(학습에도 쓴다). A1(c) G_γ 비열등, A2 상수 붕괴, A4 결과 안전.
- Ge: G + 덮기 energy_drain 0, food_energy_per_unit 0, repro_threshold 2.0 (> max_energy 1.0). 키는
  `configs/default.yaml` 의 v1 키다. 에너지가 처음 값(init_energy 0.5)에 머물고 아사와 번식이 없다. A1(a)(b) 의 1차 양
  (피식률)과 재현 확인에 쓴다. 학습에는 쓰지 않는다(SEASON 2절).
  food_energy_per_unit 0 이면 `World._eat` 의 흡수 가능량 (max_energy − e)/0 이 +inf 가 되고 food_eat_rate 로 잘린다.
  에너지가 늘 0.5 라 분자가 0 이 되는 일(0/0 = nan)은 없다. 워커마다 numpy 0 나눗셈 경고가 한 번씩 나온다. 먹이는
  계속 줄고 다시 자란다. 에너지로 바뀌지 않을 뿐이다(테스트 레벨의 더미 먹이 격자와는 다르다).
- B: 기본 학습 설정(configs/v2.yaml). A3 망각.

평가 방식: 시드 10000~10019 × 5000스텝, 결정 모드(`policies.registry` learned, 언리얼 배포와 같다). 행동 4개 앵커
(v1·v2.0)는 표본 대상 열이 없어 V2 결정 R1 의 출시 모드 영향이 없다(SEASON 4.2). G_γ 는 앵커의 학습 γ 로 잰다.
보류 재확인은 시드 10020~10039 다.

판정 묶음 (`gate_bundle`, SEASON 4.2 "평가 묶음"):
- G: cand, cand_P(C1′ 행동 순열), cur, cur_P   (현재 ≠ 앵커이면 anchor, anchor_P 를 더한다)
- Ge: cand, cur, k2b
- B: cand, anchor
- 보류(`holdout_bundle`): Ge 에서 cand, cur, k2b
SR1 은 시즌 사슬이 없어 현재 = 앵커다. C1′ 스펙은 `diagnose_v2.control_specs` 의 것을 그대로 쓴다.

평가 행은 `EvalCache` 로 스펙마다 저장한다. 키는 (설정 지문, 스펙, 모델 sha1, 시드, 스텝, γ, 코드 지문) 다. 그래서 앵커와
K2-B 의 행은 후보마다 다시 재지 않는다(SEASON 4.1 "K2-B 캐시", 4.2 "앵커 × B 는 앵커마다 한 번"). 코드 지문
(`season.common.sim_digest`)은 캐시를 만들 때 한 번 잰다. `env_v2/` 등이 바뀌면 키가 달라져 옛 행을 쓰지 않는다.

    python -m season.eval_worlds --season a --anchor v1 --seeds 3 --steps 1000     # Ge 덮기 동작 확인 (SEASON 5.4)
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import env.torch_init  # noqa: F401  ← torch보다 먼저 (학습 정책을 이 프로세스에서도 싣는다)

import argparse
import hashlib
import json
import math

import numpy as np

from diagnose_v2 import config_digest, control_specs, model_fingerprint
from env_v2.rollout import make_executor, public_row, run_specs
from env_v2.world import ACT_DIM
from season.common import EVAL_STEPS, RUNS, load_base, load_season, resolve_anchor, resolve_season, sim_digest

GE_OVERRIDE = {"energy_drain": 0.0, "food_energy_per_unit": 0.0, "repro_threshold": 2.0}
WORLDS = ("G", "Ge", "B")
CACHE_VERSION = 2              # 2: 키에 코드 지문을 넣었다
DEFAULT_CACHE = RUNS / "cache" / "eval"


# --------------------------------------------------------------------- #
# 세계
# --------------------------------------------------------------------- #


def ge_config(cfg):
    """G → Ge. 덮는 키 셋만 바꾼 사본이다. repro_threshold 가 max_energy 이하면 번식이 남으므로 멈춘다."""
    if GE_OVERRIDE["repro_threshold"] <= float(cfg.max_energy):
        raise ValueError(f"Ge repro_threshold {GE_OVERRIDE['repro_threshold']} 는 max_energy {cfg.max_energy} 보다 커야 한다")
    return cfg.replace(**GE_OVERRIDE)


def world_configs(season: str | Path, base: str | Path | None = None) -> dict:
    """시즌 이름·경로 → {"G", "Ge", "B"} 설정."""
    _, path = resolve_season(str(season))
    g = load_season(path)
    return {"G": g, "Ge": ge_config(g), "B": load_base(base)}


# --------------------------------------------------------------------- #
# 스펙과 판정 묶음
# --------------------------------------------------------------------- #


def learned(model: str | Path) -> dict:
    """결정 모드 학습 정책 스펙. 경로는 절대 경로로 둔다(워커가 다른 작업 디렉터리에서 읽어도 같은 파일)."""
    return {"kind": "learned", "model": str(Path(model).resolve())}


def permuted(model: str | Path) -> dict:
    """C1′ 행동 순열 스펙. `diagnose_v2.control_specs` 의 C1′ 을 그대로 쓴다(평균 행동은 C1′ 에 쓰이지 않는다)."""
    return control_specs(learned(model), [0.0] * ACT_DIM)["C1'"]


def _same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def gate_bundle(cand, cur, k2b, anchor=None) -> dict[str, dict[str, dict]]:
    """판정 평가 묶음 {세계: {역할: 스펙}}. anchor 가 없거나 cur 와 같으면 G 의 앵커 행은 cur 행을 쓴다."""
    b = {
        "G": {"cand": learned(cand), "cand_P": permuted(cand), "cur": learned(cur), "cur_P": permuted(cur)},
        "Ge": {"cand": learned(cand), "cur": learned(cur), "k2b": learned(k2b)},
        "B": {"cand": learned(cand), "anchor": learned(anchor if anchor is not None else cur)},
    }
    if anchor is not None and not _same(anchor, cur):
        b["G"].update(anchor=learned(anchor), anchor_P=permuted(anchor))
    return b


def holdout_bundle(cand, cur, k2b) -> dict[str, dict[str, dict]]:
    """보류 시드 재확인 묶음 (Ge 에서 A1(a)(b) 를 다시 본다)."""
    return {"Ge": {"cand": learned(cand), "cur": learned(cur), "k2b": learned(k2b)}}


def spec_models(spec: dict) -> list[str]:
    base = spec.get("policy", spec)
    return [base["model"]] if base.get("kind") == "learned" else []


# --------------------------------------------------------------------- #
# 평가 행과 캐시
# --------------------------------------------------------------------- #


def slim_row(r: dict) -> dict:
    """롤아웃 행 → JSON 행. 공개 열(`public_row`)과 행동 차원별 평균·제곱 평균(act_mean, act_m2)을 남긴다.

    시드마다 개체-스텝 수가 같아 시드 평균이 곧 묶음 평균이다. 표준편차는 sqrt(평균 m2 − 평균²) 로 묶어 낸다(gate.py).
    """
    row = public_row(r)
    n = max(int(r["_act_n"]), 1)
    row["act_mean"] = (np.asarray(r["_act_sum"], dtype=np.float64) / n).tolist()
    row["act_m2"] = (np.asarray(r["_act_sq"], dtype=np.float64) / n).tolist()
    return row


class EvalCache:
    """스펙 하나 × 시드 목록의 평가 행을 JSON 파일 하나로 둔다. root 가 None 이면 캐시하지 않는다."""

    def __init__(self, root: str | Path | None = DEFAULT_CACHE):
        self.root = Path(root) if root is not None else None
        self._sha: dict[tuple, str | None] = {}
        self.code = sim_digest()

    def _model_sha1(self, path: str) -> str | None:
        p = Path(path)
        if not p.exists():
            return None
        st = p.stat()
        k = (str(p), st.st_mtime_ns, st.st_size)
        if k not in self._sha:
            self._sha[k] = model_fingerprint(p)
        return self._sha[k]

    def key(self, cfg, spec: dict, seeds, steps: int, gamma: float) -> str | None:
        """캐시 키. 모델 파일이 아직 없으면 None (캐시하지 않고 잴 수도 없다)."""
        if self.root is None:
            return None
        shas = {m: self._model_sha1(m) for m in spec_models(spec)}
        if any(v is None for v in shas.values()):
            return None
        payload = {"v": CACHE_VERSION, "config_digest": config_digest(cfg), "spec": spec, "model_sha1": shas,
                   "seeds": [int(s) for s in seeds], "steps": int(steps), "gamma": float(gamma), "code": self.code}
        return hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]

    def get(self, key: str | None) -> list[dict] | None:
        if key is None or self.root is None:
            return None
        p = self.root / f"{key}.json"
        if not p.exists():
            return None
        return json.loads(p.read_text(encoding="utf-8"))["rows"]

    def put(self, key: str | None, rows: list[dict], note: dict | None = None) -> None:
        if key is None or self.root is None:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f"{key}.json.tmp"
        tmp.write_text(json.dumps({"note": note or {}, "rows": rows}, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.root / f"{key}.json")


def missing_jobs(cfg, specs: dict[str, dict], seeds, steps: int, gamma: float, cache: EvalCache | None) -> int:
    """캐시에 없는 잡 수(스펙 × 시드). 모델이 아직 없는 스펙도 센다(실행기 --dry-run 추정용)."""
    n = 0
    for spec in specs.values():
        k = cache.key(cfg, spec, seeds, steps, gamma) if cache is not None else None
        if cache is None or cache.get(k) is None:
            n += len(list(seeds))
    return n


def evaluate(cfg, specs: dict[str, dict], seeds, steps: int, gamma: float, *, executor=None,
             workers: int | None = None, cache: EvalCache | None = None) -> dict[str, list[dict]]:
    """이름 → 스펙을 한 세계 설정에서 잰다. 캐시에 없는 스펙만 `run_specs` 한 번으로 돌린다. 이름 → 시드순 행."""
    seeds = [int(s) for s in seeds]
    out: dict[str, list[dict]] = {}
    todo: dict[str, dict] = {}
    keys: dict[str, str | None] = {}
    for name, spec in specs.items():
        k = cache.key(cfg, spec, seeds, steps, gamma) if cache is not None else None
        rows = cache.get(k) if cache is not None else None
        if rows is None:
            if spec_models(spec) and not all(Path(m).exists() for m in spec_models(spec)):
                raise FileNotFoundError(f"{name}: 모델이 없다 {spec_models(spec)}")
            todo[name], keys[name] = spec, k
        else:
            out[name] = rows
    if todo:
        res = run_specs(cfg, todo, seeds, steps, gamma=gamma, executor=executor, workers=workers)
        for name, rows in res.items():
            slim = [slim_row(r) for r in rows]
            out[name] = slim
            if cache is not None:
                cache.put(keys[name], slim, {"name": name, "spec": todo[name], "seeds": [seeds[0], seeds[-1]],
                                             "steps": steps, "gamma": gamma, "config_digest": config_digest(cfg),
                                             "code": cache.code})
    return {name: out[name] for name in specs}


def evaluate_bundle(bundle: dict[str, dict[str, dict]], cfgs: dict, seeds, steps: int, gamma: float, *,
                    executor=None, workers: int | None = None, cache: EvalCache | None = None,
                    prefix: str = "") -> dict[str, list[dict]]:
    """판정 묶음 → {"<prefix><세계>/<역할>": 행}. 세계마다 `evaluate` 를 한 번 부른다."""
    rows = {}
    for world, specs in bundle.items():
        res = evaluate(cfgs[world], specs, seeds, steps, gamma, executor=executor, workers=workers, cache=cache)
        rows.update({f"{prefix}{world}/{name}": r for name, r in res.items()})
    return rows


def ge_sanity(rows_list) -> dict:
    """Ge 덮기 확인 (SEASON 5.4 부수 확인): 아사 0, 번식 0. 받은 Ge 행 전체의 최댓값을 본다."""
    starve = max((float(r["starve_rate"]) for rows in rows_list for r in rows), default=0.0)
    repro = max((float(r["repro"]) for rows in rows_list for r in rows), default=0.0)
    return {"max_starve_rate": starve, "max_repro": repro, "ok": bool(starve == 0.0 and repro == 0.0)}


# --------------------------------------------------------------------- #
# 명령줄: Ge 동작 확인
# --------------------------------------------------------------------- #


def main(argv=None) -> int:
    from env_v2.rollout import model_gamma

    p = argparse.ArgumentParser(description="G·Ge·B 세계에서 앵커를 짧게 돌려 Ge 덮기 동작을 확인한다")
    p.add_argument("--season", default="a")
    p.add_argument("--anchor", default="v1")
    p.add_argument("--seeds", type=int, default=3, help="평가 시드 10000 부터 몇 개")
    p.add_argument("--steps", type=int, default=EVAL_STEPS)
    p.add_argument("--workers", type=int, default=1)
    args = p.parse_args(argv)

    _, anchor = resolve_anchor(args.anchor)
    gamma = model_gamma(anchor)
    cfgs = world_configs(args.season)
    seeds = range(10000, 10000 + args.seeds)
    ex = make_executor(args.workers)
    try:
        rows = evaluate_bundle({w: {"anchor": learned(anchor)} for w in WORLDS}, cfgs, seeds, args.steps, gamma,
                               executor=ex, cache=None)
    finally:
        if ex is not None:
            ex.shutdown()
    for k, rs in rows.items():
        m = {c: float(np.mean([r[c] for r in rs])) for c in ("predation_rate", "starve_rate", "repro", "survival",
                                                             "g_gamma")}
        print(f"{k:10s} " + "  ".join(f"{c} {v:.5g}" for c, v in m.items() if math.isfinite(v)))
    s = ge_sanity([rows["Ge/anchor"]])
    print(f"Ge 덮기: 최대 아사율 {s['max_starve_rate']}, 최대 번식 {s['max_repro']} → {'정상' if s['ok'] else '이상'}")
    return 0 if s["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())

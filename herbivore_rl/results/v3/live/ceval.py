"""네이티브 두뇌 평가 — 게임의 엔진 무관 세계 코드(AI/Policy/EcoWorldV3.h 의 Step 그대로)를 엔진 없이 돌리는 C++ 평가기
(AdaptiveEcosystem/Tools/EcoV3Eval)로 실시간 고리의 판정 세계를 여러 프로세스에서 최고 속도로 돈다 (10-21 사용자 '언리얼에서 도는 두뇌를 굳이
파이썬으로 다시 시험하지 말고 언리얼 자체에서 평가' — 게임 세계 하나는 자료가 너무 적다. 학습은 그대로 파이썬).

    # herbivore_rl/ 에서 (Anaconda base python, PYTHONUTF8=1). 평가기 빌드 먼저:
    powershell -ExecutionPolicy Bypass -File ../AdaptiveEcosystem/Tools/EcoV3Eval/build.ps1
    python results/v3/live/ceval.py selftest                       # PCG64 이어 받기 = numpy, 저장소 두뇌 파일 검사
    python results/v3/live/ceval.py compare --snapshot results/v3/live/pilot/eco_v3_snapshot_s20004_t475_e1.json \\
        --brain ../AdaptiveEcosystem/EcoBrains/v3_r1_g995_s3_obs21zero.json --seeds 34900-34904 --horizon 1800 --worlds N G --workers 4 \\
        --trace 1800                     # 결과 → AdaptiveEcosystem/Saved/EcoV3Eval/compare/<이름>/compare.json (git 밖)

live.py 와 같은 꼴 (나중에 live.py 가 바꿔 쓸 수 있게 — 이 파일은 live.py 를 고치지 않는다):
    items = ceval.eval_items(info, tag, model, seeds, steps, world, kind, horizons)   # = live.eval_items (adapt.make_jobs 그대로)
    with ceval.Pool(workers) as pool: out = pool.run(items, on_done)                   # = live.Pool.run → [(꼬리표, 세계 기록)]
  kind 'world'(r4_eval._one 칸)·'multi'(live._world_multi 칸 — 판정 길이마다 at)는 네이티브로, 그 밖('stuck'·'scale')은 파이썬(live._job)으로 돈다.
  model 은 모델 zip(그 가중치의 두뇌 파일을 EcoBrains·Saved/EcoBrains·캐시에서 찾고, 없으면 export_weights_v3 로 캐시에 쓴다) 또는 두뇌 파일 .json.
  live.py 판정 실행기 갈림(live.evaluator): LIVE evaluator 를 'ceval' 로 바꾸면 이 파일의 run_items(items, workers, on_done)·version() 을 쓴다.
  10-23 (LIVE_GATE.md 변경 기록 (6)): 1차 숨음 비율이 쓰는 숨은 뒤 10 초 지켜보기를 같은 날 C++ 도망 기록에 옮겨 평가기가 flight.hide 를 낸다(HIDE_WATCH
  참) — LIVE evaluator 기본값은 다시 'ceval' 이다(옮기기 전 잠깐 'python' 이었다).
  version() = 평가기 실행 파일·그 C++ 소스(include 닫힘)·이 파일·바탕 설정·파이썬 판정 셈 길(live.eval_code_tag('python'))의 sha256 — 판정 저장 열쇠.
  실행 파일이 소스(include 닫힘)보다 오래되면 쓰지 않는다(다시 빌드하라고 멈춘다).
  세계 설정은 허용 목록으로 본다: 바탕(REF_CFG — C++ 상수가 맞춘 판정 세계)과 다른 칸은 world 블록·시작 상태로 옮기는 칸(FREE_V1·FREE_FEATURES)이어야
  하고, 그 밖 칸이 다르면(예: wild_flight.route_fixed·quiet_end, threats·realism_night 계수) 거부한다 — C++ 이 제 상수로 다른 세계를 돌지 않게.
  숲 시야(features.obstacles.foliage, 10-21)는 C++ 에 옮겼다(EcoThreatModel.h FoliageChord·FoliageBlocked, EcoWorldV3.h FObstacleConfig::Foliage) — world 블록
  obstacle_rules 의 foliage·foliage_r·foliage_block 과 일의 foliage_trees(원판마다 나무 0/1)로 넘긴다. 도망길 COVER 그늘의 잎(route_fixed)은 파이썬 전용이라
  route_fixed 를 거부하는 것은 그대로다. compare --world-set 키=값 (route_rules.py 와 같은 점 경로 덮기)으로 숲 시야 세계를 견준다.

세계 하나 (파이썬 거울 실행기 run_mirror.run_world 와 같은 세계):
  1) 파이썬이 job 의 설정·시드로 World 를 만들고(reset — 시작 자리·방향·늑대 구성·은신처·원판), 스냅숏 먹이 지도를 덮는다(adapt.apply_snapshot_food).
  2) 그 세계에서 C++ 설정(스냅숏 지역 world 블록 꼴 — EcoV3Snapshot.cpp WorldConfigJson 과 같은 이름, adapt.FEATURE_MAPS 거꾸로)과 시작 상태(사슴 자리·방향·
     에너지·비축, 늑대 종류·자리·방향, 먹이 용량·먹이·재생률, numpy v1 난수 상태)를 뽑아 일 파일에 쓴다.
  3) C++ 은 같은 시작 상태를 입양(AdoptHerb·AdoptThreat — 행동 상태·밤잠은 파이썬과 같은 키로 다시 만든다)하고, 늑대 배회 선회를 numpy PCG64 를 이어 받아
     뽑는다(거울 세계의 스텝 안 난수는 그것뿐). 통합 모드처럼 산 사슴만 Step 에 넘기고, 언리얼 이동 제약(TraceMove 훅)은 없다(파이썬도 없다).
  기록 칸·뜻은 파이썬 판정 기록과 같다(잡힘·굶음·산·은신처 안·행동별 사슴-스텝·은신처 안 잡힘·사냥·날씨·도망 기록 flight·판정 길이마다 at) + 'native'(속도·두뇌).

파리티 — 10-22 부터 파이썬 거울 세계와 비트 단위로 같다:
  - 10-21 compare (스냅숏 s20004_t475_e1 · R1b-F + 0 열 관측 21 · 시드 34900~34904 × 지역 셋 × 1800 스텝 · N·G)에서 파이썬 그대로와 기록이 정확히 같은
    세계는 2/30 뿐이었다. 까닭은 하나였다: 파이썬 World._geometry 가 동족 무리 중심·분리를 행렬곱(MKL dgemm)·np.sum(쌍 합)으로 더하고 C++ PerceiveKin 은
    j 차례로 더해, 시작 상태가 같아도 스텝 0 의 그 두 칸만 끝 비트(1e-15~1e-14)가 달랐고 혼돈이라 223~769 스텝에 첫 이산 갈림이 났다. 그 두 칸만 같은
    차례 합으로 바꾼 진단(그때의 --py-seq-kin)과는 30/30 이 같았다(숲 시야 켬 900 스텝 18/18 도).
  - 10-22 world.py 가 그 두 칸을 C++ 과 같은 j 차례 합(`_seq_sum` — np.cumsum, 세계 스텝 +2.5~3.6 %)으로 더한다. 진단은 world.py 와 같아져 지웠다.
    같은 compare (진단 없이 world.py 그대로): N 15/15·G 15/15 세계 기록이 정확히 같고, 1800 스텝 궤적 셋(지역 셋 × 시드 34900 — 사슴 자리·heading·에너지·비축·
    관측 21·행동·요청·덮기·동족 무리 중심·분리, 늑대 자리·쿨다운·표적·잠)에 첫 비트 차이가 없다. 짝 z 는 모든 지표 0 (차이 0). 숲 시야 켬
    (--world-set features.obstacles.foliage.enabled=true ·r=3.0 ·block=2.0, 같은 시드 × 1800): N 15/15·G 15/15, 궤적 셋 비트 동일 (잎 놓침 lost_foliage
    네이티브 N 360·G 200). 시작 상태 옮기기·PCG64 이어 받기·Step·망(torch 와 argmax 동점 없음)이 같다.
  - 학습된 두뇌·가중치는 그대로다(바뀐 것은 동족 두 칸의 끝 비트 셈뿐 — 같은 세계의 통계는 그대로 같은 분포다). 옛 파이썬 판정 기록과는 세계마다 같지
    않을 수 있다(수백 스텝 뒤 갈림 — 판정 저장 열쇠에 world.py 바이트가 들어가 섞이지 않는다).
  그래서 compare 는 '기록이 정확히 같은 세계'(파리티 검사)·첫 갈림 스텝(궤적 대조)·지표별 통계 일치(z)를 보고한다.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
for p in (ROOT, ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4",
          ROOT / "results" / "v3" / "wild2", HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

import adapt as ad  # noqa: E402

PROJECT = ROOT.parent / "AdaptiveEcosystem"                                    # 언리얼 프로젝트 폴더
EXE = PROJECT / "Tools" / "EcoV3Eval" / "bin" / "EcoV3Eval.exe"
BUILD_PS1 = PROJECT / "Tools" / "EcoV3Eval" / "build.ps1"
CACHE = PROJECT / "Saved" / "EcoV3Eval"                                         # git 밖 (**/Saved/): 두뇌 파일 캐시·일 파일
BRAIN_FOLDERS = (PROJECT / "EcoBrains", PROJECT / "Saved" / "EcoBrains", CACHE / "brains")
NOSAT = dict(name="nosat", sets={"wild_satiation.enabled": False})             # N = G + 늑대 포만 끔 (live.NOSAT 와 같다)
NATIVE_KINDS = ("world", "multi")
JOBS_FORMAT, JOBS_VERSION = "eco_v3_eval_jobs", 1
WEATHER = ("clear", "rain", "snow")
# 기록 칸 (파이썬과 같은 칸 — r4_eval._one · live._world_multi)
WORLD_KEYS = ("seed", "region", "n", "caught", "starved", "alive", "shelter_steps", "live_steps", "beh_steps", "catch_cover", "catch_fled", "catches",
              "starve_fled", "hunt", "weather", "obstacles_n", "wall_s")
MULTI_KEYS = ("seed", "region", "n", "caught", "starved", "alive", "shelter_steps", "live_steps", "beh_steps", "catch_cover", "hunt", "wall_s")
EXE_SRC = PROJECT / "Tools" / "EcoV3Eval" / "EcoV3Eval.cpp"
INCLUDE_DIRS = (PROJECT / "Tools" / "EcoV3Eval", PROJECT / "Source" / "AdaptiveEcosystem" / "AI" / "Policy")   # build.ps1 의 /I 순서
VERSION_TAG = "ceval-1"                                                           # 셈 길 판 — 아래 지문 밖에서 결과를 바꾸는 고침이면 올린다
# 10-23 (results/v3/live/LIVE_GATE.md 변경 기록 (6)): 실시간 관문 1차 숨음 비율·지킴 GH 는 도망 기록의 숨은 뒤 10 초 지켜보기(파이썬 flight.hide —
# cover_then_caught 등, env_v2/world.py '숨은 뒤 지켜보기')를 쓴다. live.py 는 이 값이 참인 실행기만 판정에 쓴다(live.require_hide_watch).
# 같은 날 C++ 도망 기록(EcoWorldV3.h FlightUpdate·FlightReportOf — FFlightTrack::Watch)에 같은 정의로 옮겼고 평가기가 flight.hide 를 낸다(골든
# FlightGoldenVectorsV3.h 의 숨은 뒤 지켜보기 장면·칸, compare 의 flight.hide 까지 세계 기록 정확히 같음 — LIVE_GATE.md 변경 기록 (6) 10-23 덧붙임).
HIDE_WATCH = True

# 세계 설정 허용 목록 (world_block). REF_CFG = C++ 세계 상수가 맞춘 판정 세계 바탕 (live.TEMPLATE_OBS — 관측 21 거울, v3_wild3_mirror.yaml 과 세계가
# 비트 단위로 같다). 바탕과 달라도 되는 칸은 평가기가 world 블록·시작 상태(native_job)로 옮기는 칸뿐이다.
REF_CFG = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"
FREE_V1 = frozenset({"N", "rand", "pred_eat_cd", "food_cell", "food_patch_blur", "food_patch_threshold", "food_grad_blur", "food_regen_base",
                     "food_cover_regen_mult", "train_seeds", "eval_seeds"})       # v1 칸: 사슴 수·reset 뽑기(무대·늑대 수·속력·재생 — 시작 상태)·먹기 쿨다운·먹이 규칙
_FREE_EXTRA = {
    "threats": ("eat_in_place",),
    "realism_night": ("enabled",),
    "realism_shelter": ("enabled", "wolf_margin"),                                # shelter_safe·shelter_wolf_margin
    "daynight": ("periods", "twilight"),                                          # day_period·twilight_steps (실제 값 dn_period·dn_tw)
    "integrated_stage": ("*",),                                                   # 시작 배치 = 시작 상태, ema_den·day_offset 은 world 블록 (부활은 따로 거부)
    "wild_weather": ("region", "regions"),                                        # 날씨 kind·intensity (시간표는 바탕 그대로 null 이어야)
    "obstacles": ("fixed", "tree_per_ha", "tree_r", "rock_per_ha", "rock_r",      # 원판 = 시작 상태 discs
                  "foliage"),                                                     # 숲 시야 = obstacle_rules.foliage* + 일의 foliage_trees (10-22 C++ 에 옮김)
    "obstacle_obs": ("enabled",),                                                 # 관측 칸 수는 두뇌 계약이 정한다 (계수는 바탕 그대로)
}
FREE_FEATURES = {blk: frozenset(keys) | frozenset(_FREE_EXTRA.get(blk, ())) for blk, keys in ad.FEATURE_MAPS.values()}
for _blk, _keys in _FREE_EXTRA.items():
    FREE_FEATURES.setdefault(_blk, frozenset(_keys))
_MISSING = object()
_REF: dict = {}
_BRAIN_MEMO: dict = {}


# --------------------------------------------------------------------- #
# 평가기·두뇌 파일
# --------------------------------------------------------------------- #


def native_sources() -> list:
    """평가기 실행 파일을 만드는 소스: EcoV3Eval.cpp 와 그 #include "…" 닫힘 (build.ps1 의 /I 폴더에서 찾는다 — 표준 헤더 <…> 는 빼고)."""
    import re

    seen: dict = {}
    todo = [EXE_SRC]
    while todo:
        p = todo.pop()
        if p in seen:
            continue
        seen[p] = True
        for name in re.findall(r'^\s*#\s*include\s+"([^"]+)"', p.read_text(encoding="utf-8", errors="replace"), flags=re.M):
            for d in (p.parent,) + INCLUDE_DIRS:
                q = (d / name).resolve()
                if q.exists():
                    todo.append(q)
                    break
    return sorted(seen, key=lambda q: q.as_posix())


def exe_path() -> Path:
    """평가기 실행 파일. 없거나 소스(include 닫힘)보다 오래되면 멈춘다 (옛 실행 파일로 새 세계 코드를 잰 척하지 않게)."""
    if not EXE.exists():
        raise SystemExit(f"평가기 {EXE} 가 없다 — 먼저 빌드: powershell -ExecutionPolicy Bypass -File {BUILD_PS1}")
    t = EXE.stat().st_mtime
    newer = [p.name for p in native_sources() if p.stat().st_mtime > t]
    if newer:
        raise SystemExit(f"평가기 {EXE.name} 가 소스 {', '.join(newer)} 보다 오래되었다 — 다시 빌드: powershell -ExecutionPolicy Bypass -File {BUILD_PS1}")
    return EXE


def _live_module():
    """이 파일을 부른 live 모듈 — live.py 를 바로 돌리면 __main__ 이다(import live 는 설정이 기본값인 사본을 새로 만든다). 없으면 import live."""
    want = (HERE.parent / "live.py").resolve()
    for name in ("live", "__main__"):
        m = sys.modules.get(name)
        f = getattr(m, "__file__", None) if m is not None else None
        if f and Path(f).resolve() == want and callable(getattr(m, "_job", None)):
            return m
    import live

    return live


def version() -> str:
    """판정 셈 길 판 (live.eval_code_tag 가 판정 저장 열쇠에 넣는다): 평가기 실행 파일·C++ 소스(include 닫힘)·이 파일·바탕 설정(REF_CFG) 바이트와
    파이썬 판정 셈 길 판(live.eval_code_tag('python') — 시작 상태를 만드는 파이썬 세계·'stuck'·'scale' 파이썬 갈래)의 sha256."""
    h = hashlib.sha256(VERSION_TAG.encode())
    for p in [exe_path()] + native_sources() + [HERE, REF_CFG]:
        h.update(p.name.encode() + b"\0" + bytes.fromhex(file_sha256(p)))
    h.update(str(_live_module().eval_code_tag("python")).encode())
    return h.hexdigest()[:24]


def run_items(items: list, workers: int, on_done=None) -> list:
    """live.py 판정 실행기 갈림(live.eval_runner): 판정 일 목록 → [(꼬리표, 결과)] (items 순서). 두뇌는 일마다 job['model'] 에서 찾는다."""
    return Pool(workers).run(items, on_done)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_brain(path: Path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("format") != "eco_v3_brain":
        raise ValueError(f"{path} 는 두뇌 파일(eco_v3_brain)이 아니다")
    return d


def brain_for(model) -> Path:
    """모델 → 두뇌 파일. .json 이면 그대로, 모델 zip 이면 같은 zip(sha256 — 두뇌 파일 model.sha256)의 두뇌 파일을 찾고, 없으면 export_weights_v3 로
    캐시(Saved/EcoV3Eval/brains)에 쓴다(골든 600 스텝 한 번 — 다음부터 캐시)."""
    model = Path(model)
    if model.suffix.lower() == ".json":
        read_brain(model)
        return model
    if not model.exists():
        raise FileNotFoundError(f"모델 {model} 이 없다")
    st = model.stat()
    memo = (str(model.resolve()), st.st_size, st.st_mtime_ns)                  # 판정 일마다 같은 zip — 한 번만 찾는다
    if memo in _BRAIN_MEMO and _BRAIN_MEMO[memo].exists():
        return _BRAIN_MEMO[memo]
    out = _brain_for_zip(model)
    _BRAIN_MEMO[memo] = out
    return out


def _brain_for_zip(model: Path) -> Path:
    want = file_sha256(model)
    for folder in BRAIN_FOLDERS:
        if not folder.exists():
            continue
        for f in sorted(folder.glob("*.json")):
            try:
                b = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            if b.get("format") == "eco_v3_brain" and str(b.get("model", {}).get("sha256", "")).lower() == want:
                return f
    import export_weights_v3 as ex

    out = CACHE / "brains" / f"{model.stem}_{want[:12]}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(f".json.{os.getpid()}.tmp")
    ex.export_brain_file(model, tmp, world_label=f"ceval 캐시 ({model.name})")
    os.replace(tmp, out)
    return out


# --------------------------------------------------------------------- #
# 파이썬 거울 세계 → C++ 일 (설정·시작 상태)
# --------------------------------------------------------------------- #


def make_world(job: dict):
    """run_mirror.run_world 와 같은 세계 (reset + 스냅숏 먹이 지도 또는 언리얼 지도 덮기)."""
    from env.config import Config
    from env_v2.world import World

    import run_mirror as rm

    w = World(Config(job["cfg"]), seeds=[int(job["seed"])])
    if w.alive is None:
        raise ValueError("평가기는 부활 없는 판정 세계(integrated_stage.respawn false)만 받는다")
    if job.get("snap_food") is not None:
        ad.apply_snapshot_food(w, job["snap_food"])                 # adapt._patch_food 가 거울 실행기에 거는 덮기와 같다
    elif job.get("unreal_map") is not None:
        um = job["unreal_map"]
        rm.apply_unreal_map(w, int(um["seed"]), um["region"])
    return w


def _ref_dict() -> dict:
    if "cfg" not in _REF:
        from env_v2.config import load_v2_config

        _REF["cfg"] = load_v2_config(REF_CFG).to_dict()
    return _REF["cfg"]


def unsupported_settings(cfg: dict) -> list:
    """설정 dict (Config.to_dict 꼴) 가운데 평가기가 옮기지 않는데 바탕(REF_CFG)과 다른 칸 → '칸: 값 (바탕 값)' 목록 (빈 목록 = 받는다).
    허용 목록: v1 은 FREE_V1, 기능 블록은 FREE_FEATURES (켬/끔 칸도 목록에 있어야 바꿀 수 있다). 끈 기능의 계수는 세계가 읽지 않으므로 보지 않는다.
    선택 키(features.OPTIONAL_KEYS)는 끔 값으로 채워 견준다 — 끔 값을 적은 설정과 적지 않은 설정은 같은 세계다. v2.train 은 학습 칸(허용 행동은
    world_allowed 로 옮긴다)이라 보지 않는다."""
    from env_v2.features import with_optional

    ref = _ref_dict()
    out = []
    for k in sorted((set(cfg) | set(ref)) - {"v2"}):
        if k not in FREE_V1 and cfg.get(k, _MISSING) != ref.get(k, _MISSING):
            out.append(f"{k}: {cfg.get(k)!r} (바탕 {ref.get(k)!r})")
    fj = ((cfg.get("v2") or {}).get("features") or {})
    fr = ((ref.get("v2") or {}).get("features") or {})
    for name in sorted(set(fj) | set(fr)):
        free = FREE_FEATURES.get(name, frozenset())
        ja, ra = dict(fj.get(name) or {}), dict(fr.get(name) or {})
        on_j, on_r = bool(ja.pop("enabled", False)), bool(ra.pop("enabled", False))
        if on_j != on_r and not ({"enabled", "*"} & free):
            out.append(f"features.{name}.enabled: {on_j} (바탕 {on_r})")
        if not on_j or "*" in free:
            continue
        pj, pr = with_optional(name, ja), with_optional(name, ra)
        for d in (pj, pr):              # 숲 시야(obstacles.foliage)는 enabled 가 거짓이면 아래 칸과 상관없이 끈 세계다 — 끔은 끔끼리 같게 본다
            if isinstance(d.get("foliage"), dict) and not d["foliage"].get("enabled", False):
                d["foliage"] = None
        for k in sorted(set(pj) | set(pr)):
            if k not in free and pj.get(k, _MISSING) != pr.get(k, _MISSING):
                out.append(f"features.{name}.{k}: {pj.get(k, '(없음)')!r} (바탕 {pr.get(k, '(없음)')!r})")
    return out


def world_block(w, protected_refuges: bool = False) -> dict:
    """파이썬 세계 → 스냅숏 지역 world 블록 꼴 (EcoV3Snapshot.cpp WorldConfigJson 과 같은 이름 — adapt.convert 의 거꾸로). 평가기가 FWorldConfig 로 읽는다.
    seed = 파이썬 세계 시드(지연 해시·밤잠 지연 키 — 파이썬 세계와 같은 개체 키), rng_stream 0(쓰지 않는다 — 선회는 numpy 이어 받기).
    protected_refuges: 팀 은신처 생명주기(언리얼 통합 모드 켬 — 지워진 은신처가 없으면 은신처 안전은 파이썬 규칙 그대로, B 의 '은신처 밖 도착 HIDE 풀기'만 더한다)."""
    from env_v2.features import with_optional
    from env_v2.rep_policy import rep_params
    from env_v2.repertoire import BEHAVIOR_NAMES
    from env_v2.world import PT_CHASER, PT_STALKER

    cfg, f = w.cfg, w.features
    if w.pred_is_player.any() or w.pred_ranged.any() or np.asarray(getattr(w, "pred_nocturnal", np.zeros(w.M, dtype=bool))).any():
        raise ValueError("플레이어형·원거리형·야행성 위협이 있는 세계는 평가기가 받지 않는다 (통합 무대에 없다)")
    if not w._ist or w._ist["respawn"]:
        raise ValueError("통합 무대(부활 없음) 세계만 받는다")
    for name in ("realism_chase", "realism_terrain", "stare_down", "alarm", "food_v", "vigilance"):
        if f.enabled(name):
            raise ValueError(f"기능 {name} 은 C++ 세계에 없다 — 평가기가 받지 않는다")
    if w._zs is not None and not (w._zs["untargetable"] and w._zs["player_too"] and w._zs["block_predators"]):
        raise ValueError("realism_shelter 는 표적 제외·플레이어·진입 금지가 모두 켜진 세계만 받는다 (C++ bShelterSafe 하나)")
    if w._zv is not None and float(w._zv["kin_fov_deg"]) != float(cfg.fov_deg):
        raise ValueError("realism_vision.kin_fov_deg 가 기본과 다르다 — C++ 에 옮기지 않았다")
    if w._zf is not None and w._zf["frac_range"] is not None:
        raise ValueError("realism_cover_food.frac_range 는 C++ 에 없다")
    if w._wx is not None and w._wx["schedule"] is not None:
        raise ValueError("날씨 시간표는 평가기가 받지 않는다")
    if w._wf is not None and float(w._wf.get("flight_cost", 0.0)) > 0.0:
        raise ValueError("wild_flight.flight_cost 는 학습 세계 전용이다 (판정 세계에 없어야 한다)")
    if w._wf is not None and (w._wf.get("route_fixed") is not None or int(w._wf.get("quiet_end", 0) or 0) > 0 or w._wf.get("route")):
        # 10-21 도망길 측정(route_fixed·quiet_end)·10-22 두뇌 길(route — 관측 24·마스크 판 4)은 C++ 에 없다 — 'run' 도 세계는 같지만 도망길 기록(flight.route 등)을
        # 낼 수 없다
        raise ValueError(f"wild_flight.route_fixed {w._wf.get('route_fixed')!r}·quiet_end {w._wf.get('quiet_end')!r}·route {w._wf.get('route')!r} 는 "
                         "C++ 세계에 없다 — 평가기가 받지 않는다")
    bad = unsupported_settings(cfg.to_dict())
    if bad:
        raise ValueError(f"평가기가 옮기지 않는 세계 칸이 바탕({REF_CFG.name})과 다르다 — C++ 은 제 상수로 돈다: " + "; ".join(bad[:8])
                         + (f" 외 {len(bad) - 8}" if len(bad) > 8 else ""))
    kinds = w.pred_type.tolist()
    ist = w._ist
    rp = rep_params(cfg)
    world_list = tuple(BEHAVIOR_NAMES) if rp is None else tuple(rp["allowed"])
    wb = dict(world_size=float(w.size), seed=int(w.seed), rng_stream=0, num_herbivores=int(w.N),
              num_stalkers=int(sum(k == PT_STALKER for k in kinds)), num_chasers=int(sum(k == PT_CHASER for k in kinds)), num_ranged=0,
              num_nocturnal=0, player_proxy=False, pred_speed_mult=float(w.pred_speed_mult), pred_eat_cd=int(cfg.pred_eat_cd),
              eat_in_place=bool(w._eat_in_place), realism_night=w._zn is not None, respawn_dead=False,
              pred_ema_denominator=int(w.N if ist["ema_den"] is None else ist["ema_den"]), day_period=int(w.dn_period),
              day_offset=int(w.dn_offset), twilight_steps=int(w.dn_tw), shelter_safe=w._zs is not None,
              shelter_wolf_margin=float(w._zw_m), protected_refuges=bool(protected_refuges),
              world_allowed=[int(b in world_list) for b in BEHAVIOR_NAMES],
              food_rules=dict(cell=float(cfg.food_cell), patch_blur=int(cfg.food_patch_blur), patch_threshold=float(cfg.food_patch_threshold),
                              grad_blur=int(cfg.food_grad_blur), regen_base=float(cfg.food_regen_base), regen_mult=float(w.food_regen_mult),
                              cover_regen_mult=float(cfg.food_cover_regen_mult)))
    for sblock, (pblock, keys) in ad.FEATURE_MAPS.items():
        p = with_optional(pblock, f.params(pblock))
        blk = {}
        for k in keys:
            blk[k] = bool(f.enabled(pblock)) if k == "enabled" else p[k]
        wb[sblock] = blk
    # 숲 시야 (10-22, C++ FObstacleConfig::Foliage — 스냅숏 obstacle_rules 와 같은 이름, 끈 세계는 foliage false·켤 때 값). 나무 표는 native_job 의 foliage_trees
    fo = foliage_of(w)
    fdef = foliage_defaults()
    wb["obstacle_rules"]["foliage"] = fo is not None
    wb["obstacle_rules"]["foliage_r"] = float(fo["r"] if fo is not None else fdef["r"])
    wb["obstacle_rules"]["foliage_block"] = float(fo["block"] if fo is not None else fdef["block"])
    wx = wb["weather"]
    if w._wx is not None:
        wx["kind"], wx["intensity"] = WEATHER[int(w.weather_kind)], float(w.weather_intensity)
    else:
        wx["kind"], wx["intensity"] = "clear", 0.0
    wx["schedule_rows"] = 0
    return wb


def foliage_defaults() -> dict:
    """숲 시야 끔 값 (features.OPTIONAL_KEYS obstacles.foliage — r·block 은 켤 때 값)."""
    from env_v2.features import OPTIONAL_KEYS

    return dict(OPTIONAL_KEYS["obstacles"]["foliage"])


def foliage_of(w) -> dict | None:
    """숲 시야를 켠 세계면 그 블록 (world.py `_foliage_params` 결과 — r·block·trees), 아니면 None."""
    return None if w._ob is None else w._ob.get("foliage")


def foliage_trees(w) -> list:
    """숲 시야 나무 표 (원판마다 0/1, w.obstacles 순서 — world.py `_fol_centers` 와 같은 표: trees 'all' 이면 obstacle_tree, 아니면 그 목록). 끈 세계는 빈 목록."""
    fo = foliage_of(w)
    if fo is None:
        return []
    t = w.obstacle_tree if isinstance(fo["trees"], str) else np.asarray(fo["trees"], dtype=bool)
    if len(t) != len(w.obstacles):
        raise ValueError(f"숲 시야 나무 표 {len(t)} 가 원판 수 {len(w.obstacles)} 와 다르다")
    return [int(bool(x)) for x in t]


def native_job(job: dict, idx: int, horizons=None, trace: int = 0, protected_refuges: bool = False, rng: str = "pcg64",
               world=None) -> dict:
    """job (adapt.make_jobs 꼴) → 평가기 일 하나 (시작 상태 그대로)."""
    w = make_world(job) if world is None else world
    st = w.rng.bit_generator.state
    if st.get("bit_generator") != "PCG64" or st.get("has_uint32"):
        raise ValueError(f"v1 난수가 PCG64(32 비트 남김 없음)가 아니다: {st.get('bit_generator')}")
    wolves = [dict(kind="stalker" if int(t) == 1 else "chaser", x=float(p[0]), y=float(p[1]), hx=float(h[0]), hy=float(h[1]), slot=m,
                   speed=float(sp))
              for m, (t, p, h, sp) in enumerate(zip(w.pred_type.tolist(), w.pred_pos, w.pred_head, w.pred_speed))]
    reserve = w.reserve if getattr(w, "_wr", None) is not None else np.zeros(w.N)
    out = dict(id=int(idx), seed=int(job["seed"]), region=str(job.get("region", "")), steps=int(job["steps"]),
               horizons=[int(h) for h in (horizons or [])], trace=int(trace), world=world_block(w, protected_refuges),
               covers=np.c_[w.cov_c, w.cov_r].tolist(), discs=np.asarray(w.obstacles, dtype=np.float64).tolist(), foliage_trees=foliage_trees(w),
               food=dict(gw=int(w.gw), cell=float(w.cfg.food_cell), cap=w.food_cap.ravel().tolist(), food=w.food.ravel().tolist(),
                         regen=np.broadcast_to(w.regen_field, w.food_cap.shape).ravel().tolist()),
               deer=dict(x=w.pos[:, 0].tolist(), y=w.pos[:, 1].tolist(), hx=w.head[:, 0].tolist(), hy=w.head[:, 1].tolist(),
                         energy=w.energy.tolist(), reserve=np.asarray(reserve, dtype=np.float64).tolist(),
                         repro_cd=np.asarray(w.repro_cd).astype(int).tolist(), slot=list(range(w.N))),
               wolves=wolves,
               rng=dict(kind="pcg64", state=str(st["state"]["state"]), inc=str(st["state"]["inc"])) if rng == "pcg64" else dict(kind="native"))
    return out


# --------------------------------------------------------------------- #
# 돌리기 (평가기 프로세스 여러 개)
# --------------------------------------------------------------------- #


def run_native(jobs: list, brain: Path, workers: int, keep: Path | None = None, quiet: bool = True, on_done=None) -> list:
    """평가기 일 목록 (id 마다) → 기록 줄 목록 (id 순서). 일을 workers 묶음으로 나눠(id 차례로 돌려 담기) 프로세스마다 하나씩 돈다."""
    exe = exe_path()
    if not jobs:
        return []
    workers = max(1, min(int(workers), len(jobs)))
    run_dir = Path(keep) if keep is not None else CACHE / "runs" / f"r{datetime.now():%Y%m%dT%H%M%S}_{os.getpid()}"
    run_dir.mkdir(parents=True, exist_ok=True)
    chunks = [jobs[k::workers] for k in range(workers)]
    procs = []
    for k, ch in enumerate(chunks):
        jp, op, ep = run_dir / f"jobs_{k}.json", run_dir / f"out_{k}.jsonl", run_dir / f"err_{k}.log"
        jp.write_text(json.dumps(dict(format=JOBS_FORMAT, version=JOBS_VERSION, brain=str(Path(brain).resolve()), jobs=ch),
                                 separators=(",", ":")), encoding="utf-8")
        fh = open(ep, "w", encoding="utf-8")
        cmd = [str(exe), "--jobs", str(jp), "--out", str(op)] + (["--quiet"] if quiet else [])
        procs.append((subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT), fh, op, ep, len(ch)))
    rows: dict = {}
    errs = []
    for p, fh, op, ep, n in procs:
        rc = p.wait()
        fh.close()
        got = 0
        if op.exists():
            for line in op.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                rows[int(r["id"])] = r
                got += 1
                if "error" in r:
                    errs.append(f"id {r['id']}: {r['error']}")
                if on_done:
                    on_done()
        if rc not in (0, 1) or got != n:
            errs.append(f"평가기 종료 코드 {rc}, 기록 {got}/{n} — {ep.read_text(encoding='utf-8', errors='replace')[-800:]}")
    if errs:
        raise RuntimeError("네이티브 평가 실패: " + " | ".join(errs[:5]))
    if keep is None:
        for f in run_dir.iterdir():
            f.unlink(missing_ok=True)
        run_dir.rmdir()
    return [rows[int(j["id"])] for j in jobs]


def shape(kind: str, job: dict, row: dict, prep_s: float, brain: Path) -> dict:
    """평가기 기록 → 파이썬 세계 기록과 같은 칸 (kind 'world' = r4_eval._one, 'multi' = live._world_multi) + native."""
    rec = row["record"]
    keys = WORLD_KEYS if kind == "world" else MULTI_KEYS
    out = {k: copy.deepcopy(rec.get(k)) for k in keys}                 # 없는 칸은 None (파이썬도 weather·obstacles_n 이 없으면 None)
    out["region"] = job.get("region", rec.get("region"))
    if "flight" in rec:
        out["flight"] = rec["flight"]
    if kind == "multi":
        out["at"] = rec.get("at", {})
    out["native"] = dict(engine="EcoV3Eval", brain=Path(brain).name, steps=rec["steps"], steps_per_s=rec["steps_per_s"], prep_s=round(prep_s, 4),
                         rng_draws=rec["rng_draws"], mask_violations=rec["mask_violations"], obs_layout_mismatch=rec["obs_layout_mismatch"])
    return out


class Pool:
    """live.Pool 과 같은 꼴: run(items, on_done) → [(꼬리표, 기록)] (items 순서). 'world'·'multi' 는 네이티브 평가기(workers 프로세스),
    나머지는 파이썬(live._job, env_v2.rollout 워커 풀). brain 을 주면 모든 네이티브 일에 그 두뇌 파일을 쓴다(아니면 job['model'] 에서 찾는다)."""

    def __init__(self, workers: int, brain: Path | None = None, protected_refuges: bool = False, keep: Path | None = None):
        self.workers = max(1, int(workers))
        self.brain = Path(brain) if brain is not None else None
        self.protected_refuges = bool(protected_refuges)
        self.keep = keep
        self.timing: dict = {}

    def run(self, items: list, on_done=None) -> list:
        out = [None] * len(items)
        native = [k for k, it in enumerate(items) if it[0] in NATIVE_KINDS]
        other = [k for k, it in enumerate(items) if it[0] not in NATIVE_KINDS]
        if other:
            live = _live_module()                     # 부른 live 모듈 그대로 (live.py 를 바로 돌린 판도 사본을 만들지 않는다)
            with live.Pool(min(self.workers, len(other))) as pool:
                res = pool.run([items[k] for k in other], on_done=on_done)
            for k, r in zip(other, res):
                out[k] = r
        groups: dict = {}
        for k in native:
            b = self.brain if self.brain is not None else brain_for(items[k][2]["model"])
            groups.setdefault(str(b), []).append(k)
        t_prep = t_run = 0.0
        for b, ks in groups.items():
            jobs, preps = [], {}
            for k in ks:
                kind, tag, job = items[k]
                t0 = time.perf_counter()
                jobs.append(native_job(job, k, job.get("horizons") if kind == "multi" else None, protected_refuges=self.protected_refuges))
                preps[k] = time.perf_counter() - t0
            t_prep += sum(preps.values())
            t0 = time.perf_counter()
            rows = run_native(jobs, Path(b), self.workers, keep=self.keep, on_done=on_done)
            t_run += time.perf_counter() - t0
            for k, row in zip(ks, rows):
                kind, tag, job = items[k]
                out[k] = (tag, shape(kind, job, row, preps[k], Path(b)))
        self.timing = dict(prep_s=round(t_prep, 2), native_s=round(t_run, 2), native_worlds=len(native), python_worlds=len(other))
        return out

    def close(self, kill: bool = False) -> None:
        return None

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        return False


def eval_items(info: dict, tag: str, model: Path, seeds, steps: int, world: str, kind: str = "world", horizons=None,
               world_set: dict | None = None) -> list:
    """live.eval_items 와 같다: world 'N' = 포만 없는 세계(G + NOSAT), 'G' = 게임 세계. kind 'multi' 면 판정 길이마다 요약.
    world_set = 세계 덮기 {점 경로: 값} (apply_world_set — 예: 숲 시야 features.obstacles.foliage.enabled=true). 파이썬·네이티브가 같은 job['cfg'] 를 쓴다."""
    jobs = ad.make_jobs(info, Path(model), seeds, steps, True, NOSAT if world == "N" else None)
    for j in jobs:
        if horizons is not None:
            j["horizons"] = list(horizons)
        if world_set:
            apply_world_set(j["cfg"], world_set)
    return [(kind, f"{tag}:{world}", j) for j in jobs]


def parse_world_set(items) -> dict:
    """['키=값', …] → {점 경로: 값} (값은 YAML — true·3.0·null). results/v3/route/route_rules.py 의 --world-set 과 같은 꼴. 같은 키를 두 번 주면 멈춘다."""
    import yaml

    out: dict = {}
    for it in items or ():
        if "=" not in it:
            raise SystemExit(f"--world-set {it!r} 는 키=값 꼴이어야 한다")
        k, v = it.split("=", 1)
        k = k.strip()
        if not k or any(not x for x in k.split(".")):
            raise SystemExit(f"--world-set {it!r}: 키가 비었다")
        if k in out:
            raise SystemExit(f"--world-set {k} 를 두 번 주었다")
        out[k] = yaml.safe_load(v)
    return out


def apply_world_set(cfg: dict, sets: dict) -> None:
    """설정 dict(Config.to_dict 꼴)에 점 경로 덮기 (제자리, route_rules.apply_world_set 과 같은 뜻): features.<…> = cfg['v2']['features'][…], v2.<…> =
    cfg['v2'][…], 그 밖은 v1 칸. 중간 칸이 없거나 null 이면 빈 블록을 만든다. 중간 칸이 블록이 아니면 멈춘다."""
    for path, val in sets.items():
        ks = path.split(".")
        if ks[0] == "features":
            node, ks = cfg.setdefault("v2", {}).setdefault("features", {}), ks[1:]
        elif ks[0] == "v2":
            node, ks = cfg.setdefault("v2", {}), ks[1:]
        else:
            node = cfg
        if not ks:
            raise SystemExit(f"--world-set {path}: 칸 이름이 없다")
        for k in ks[:-1]:
            if node.get(k) is None:
                node[k] = {}
            if not isinstance(node[k], dict):
                raise SystemExit(f"--world-set {path}: 칸 {k} 가 블록이 아니다 ({node[k]!r})")
            node = node[k]
        node[ks[-1]] = val


# --------------------------------------------------------------------- #
# 대조 (파이썬 판정 세계 ↔ 네이티브)
# --------------------------------------------------------------------- #

METRICS = (("caught", lambda r: r["caught"]), ("starved", lambda r: r["starved"]), ("alive", lambda r: r["alive"]),
           ("shelter_steps", lambda r: r["shelter_steps"]), ("live_steps", lambda r: r["live_steps"]),
           ("graze_steps", lambda r: r["beh_steps"][0]), ("flee_steps_beh", lambda r: r["beh_steps"][1]), ("hide_steps", lambda r: r["beh_steps"][2]),
           ("catch_cover", lambda r: r["catch_cover"]), ("catch_fled", lambda r: r.get("catch_fled", 0)),
           ("hunt_starts", lambda r: r["hunt"]["starts"]), ("hunt_ends", lambda r: r["hunt"]["ends"]), ("hunt_success", lambda r: r["hunt"]["success"]),
           ("flight_started", lambda r: r["flight"]["started"]), ("flight_flee_steps", lambda r: r["flight"]["flee_steps"]),
           ("flight_reflex_steps", lambda r: r["flight"]["reflex_steps"]), ("flight_own_n", lambda r: r["flight"]["own_n"]),
           ("flight_own_contact", lambda r: r["flight"]["own_contact"]), ("flight_caught", lambda r: r["flight"]["n"]["caught"]),
           ("flight_unchased", lambda r: r["flight"]["n"]["unchased"]), ("flight_switch", lambda r: r["flight"]["n"]["switch"]),
           ("flight_stop", lambda r: r["flight"]["n"]["stop"]), ("flight_shelter_end", lambda r: r["flight"]["shelter_end"]),
           # 10-23 숨은 뒤 10 초 지켜보기 (flight.hide — 실시간 관문 1차 숨음 비율·지킴 GH 의 재료)
           ("flight_chased", lambda r: r["flight"]["hide"]["chased"]), ("flight_hidden", lambda r: r["flight"]["hide"]["hidden"]),
           ("flight_cover_then_caught", lambda r: r["flight"]["hide"]["cover_then_caught"]),
           ("flight_cover_then_starved", lambda r: r["flight"]["hide"]["cover_then_starved"]))


def stat_compare(py: list, nat: list) -> dict:
    """같은 (시드, 지역) 세계 짝. 지표마다 평균·짝 차이 평균·sd·z(짝 — 같은 시작 상태)·z(독립 두 표본 — 다른 난수 세계로 볼 때)·정확히 같은 세계 수."""
    key = lambda r: (int(r["seed"]), r["region"])  # noqa: E731
    pn = {key(r): r for r in py}
    nn = {key(r): r for r in nat}
    ks = sorted(set(pn) & set(nn))
    out = {}
    for name, fn in METRICS:
        a = np.array([float(fn(pn[k])) for k in ks])
        b = np.array([float(fn(nn[k])) for k in ks])
        d = b - a
        n = len(d)
        sd = float(d.std(ddof=1)) if n > 1 else float("nan")
        zp = float(d.mean() / (sd / math.sqrt(n))) if n > 1 and sd > 0 else (0.0 if n and d.mean() == 0 else float("nan"))
        va, vb = (float(a.var(ddof=1)) if n > 1 else 0.0), (float(b.var(ddof=1)) if n > 1 else 0.0)
        se2 = math.sqrt((va + vb) / n) if n > 0 else float("nan")
        zu = float((b.mean() - a.mean()) / se2) if n and se2 > 0 else (0.0 if n and b.mean() == a.mean() else float("nan"))
        out[name] = dict(py=float(a.mean()) if n else float("nan"), native=float(b.mean()) if n else float("nan"), diff=float(d.mean()) if n else float("nan"),
                         sd_diff=sd, z_paired=zp, z_unpaired=zu, same=int(np.count_nonzero(d == 0)), n=n)
    return out


def _only_left(a, b, pre: str = "") -> list:
    """a 에만 있는 칸 이름 (안쪽 dict 까지)."""
    out = []
    for k in a:
        if k not in b:
            out.append(pre + str(k))
        elif isinstance(a[k], dict) and isinstance(b[k], dict):
            out += _only_left(a[k], b[k], f"{pre}{k}.")
    return out


def _same(a, b) -> bool:
    """두 칸이 같은가 — dict 는 양쪽에 다 있는 칸만 견준다 (한쪽에만 있는 칸은 _only_left 로 따로 적는다)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return all(_same(a[k], b[k]) for k in a.keys() & b.keys())
    return a == b


def exact_worlds(py: list, nat: list) -> dict:
    """세계마다 기록 칸(네이티브 'native'·wall_s 빼고)이 정확히 같은가. 파이썬에만 있는 칸(네이티브가 아직 내지 않는 칸)은 python_only 에 적는다."""
    key = lambda r: (int(r["seed"]), r["region"])  # noqa: E731
    pn = {key(r): r for r in py}
    rows = []
    only = set()
    for r in nat:
        p = pn.get(key(r))
        if p is None:
            continue
        diff = [k for k in p if k not in ("wall_s", "native") and k in r and not _same(p[k], r[k])]
        only |= set(_only_left({k: v for k, v in p.items() if k != "wall_s"}, r))
        rows.append(dict(seed=key(r)[0], region=key(r)[1], same=not diff, differ=diff, caught=(p["caught"], r["caught"]),
                         starved=(p["starved"], r["starved"]), own_contact=(p.get("flight", {}).get("own_contact"), r.get("flight", {}).get("own_contact"))))
    return dict(worlds=len(rows), exact=sum(x["same"] for x in rows), python_only=sorted(only), rows=rows)


def python_trace(job: dict, model: Path, steps: int) -> list:
    """파이썬 거울 세계를 steps 스텝 돌리며 매 스텝 끝 상태 (평가기 trace 와 같은 칸). 첫 줄 = 시작 상태."""
    from env_v2 import rollout as ro

    w = make_world(job)
    if w._wf is not None:
        w.track_flight = True
    pol = ro.build_policy({"kind": "rep_learned", "path": str(model)}, int(job["seed"]))
    ro.forward_bind(pol, w)

    def snap(req):
        d = dict(t=int(w.t), dark=float(w.dark), pred_ema=float(w.pred_ema), x=w.pos[:, 0].tolist(), y=w.pos[:, 1].tolist(), hx=w.head[:, 0].tolist(),
                 hy=w.head[:, 1].tolist(), energy=w.energy.tolist(), reserve=(w.reserve if w._wr is not None else np.zeros(w.N)).tolist(),
                 behavior=w._rs.behavior.astype(int).tolist(), request=np.asarray(req).reshape(-1).astype(int).tolist(),
                 keep=np.asarray(w.wf_mode).astype(int).tolist() if w._wf is not None else [0] * w.N,
                 cause=w.death_cause.astype(int).tolist(), obs=np.asarray(w._obs, dtype=np.float64).tolist(),
                 **{k: np.asarray(w._g[k], dtype=np.float64).tolist() for k in VEC_KEYS},
                 wolves=dict(x=w.pred_pos[:, 0].tolist(), y=w.pred_pos[:, 1].tolist(), hx=w.pred_head[:, 0].tolist(), hy=w.pred_head[:, 1].tolist(),
                             cd=w.pred_cd.astype(int).tolist(), sat=np.asarray(getattr(w, "pred_sat", np.zeros(w.M))).astype(int).tolist(),
                             asleep=np.asarray(w.pred_asleep).astype(bool).tolist(),
                             target=np.asarray(getattr(w, "pred_target", np.full(w.M, -1))).astype(int).tolist()))
        return d

    a = np.asarray(pol(w.observe()), dtype=np.float64)
    out = [snap(a)]
    for _ in range(int(steps)):
        w.step(a)
        a = np.asarray(pol(w.observe()), dtype=np.float64)
        out.append(snap(a))
    return out


VEC_KEYS = ("to_centroid", "separation", "away_from_pred", "food_grad")     # 스텝 끝 지각 (조향 입력)


def trace_diff(py: list, nat: dict) -> dict:
    """궤적 대조: 스텝마다 사슴 자리·heading·에너지·비축 최대 차이(모든 슬롯 — 죽은 사슴은 양쪽 모두 죽은 자리에 멈춘다), 관측 최대 차이·행동이 다른
    사슴 수(스텝 첫머리에 산 사슴 — 파이썬은 죽은 행의 관측·행동 상태도 계속 계산하고 C++ 은 목록에서 빼므로 견주지 않는다), 다음 요청(스텝 끝 산 사슴,
    덮기 도주·웅크림 빼고)·덮기·죽음이 다른 수, 늑대 자리 최대 차이·쿨다운·표적·잠이 다른 수. 첫 갈림 = 자리 차이 > 1e-9 이거나 이산 칸이 다른 첫 스텝
    (0 = 시작 상태), 첫 비트 차이 = 실수 칸이 하나라도 다른 첫 스텝."""
    ns = [nat["init"]] + list(nat["trace"])
    rows = []
    first = None
    first_any = None
    alive0 = np.asarray(py[0]["cause"]) == 0
    for s in range(min(len(py), len(ns))):
        p, q = py[s], ns[s]
        f = lambda k: float(np.max(np.abs(np.asarray(p[k], dtype=np.float64) - np.asarray(q[k], dtype=np.float64)))) if len(p[k]) else 0.0  # noqa: E731
        pc, qc = np.asarray(p["cause"]), np.asarray(q["cause"])
        live_end = (pc == 0) & (qc == 0)
        keep_ok = live_end & (np.asarray(p["keep"]) < 2)
        ob = np.abs(np.asarray(p["obs"]) - np.asarray(q["obs"]))
        r = dict(t=p["t"], live=int(np.count_nonzero(pc == 0)), pos=max(f("x"), f("y")), head=max(f("hx"), f("hy")), energy=f("energy"),
                 reserve=f("reserve"), obs=float(ob[alive0].max()) if alive0.any() else 0.0,
                 behavior=int(np.count_nonzero((np.asarray(p["behavior"]) != np.asarray(q["behavior"])) & alive0)),
                 keep=int(np.count_nonzero(np.asarray(p["keep"]) != np.asarray(q["keep"]))),
                 cause=int(np.count_nonzero(pc != qc)),
                 request=int(np.count_nonzero((np.asarray(p["request"]) != np.asarray(q["request"])) & keep_ok)),
                 wolf_pos=max(float(np.max(np.abs(np.asarray(p["wolves"]["x"]) - np.asarray(q["wolves"]["x"])))),
                              float(np.max(np.abs(np.asarray(p["wolves"]["y"]) - np.asarray(q["wolves"]["y"]))))),
                 wolf_cd=int(np.count_nonzero(np.asarray(p["wolves"]["cd"]) != np.asarray(q["wolves"]["cd"]))),
                 wolf_asleep=int(np.count_nonzero(np.asarray(p["wolves"]["asleep"]) != np.asarray(q["wolves"]["asleep"]))),
                 wolf_target=int(np.count_nonzero(np.asarray(p["wolves"]["target"]) != np.asarray(q["wolves"]["target"]))) if s > 0 else 0,
                 dark=abs(p["dark"] - q["dark"]), pred_ema=abs(p["pred_ema"] - q["pred_ema"]))
        for k in VEC_KEYS:
            if k in p and k in q:
                dv = np.abs(np.asarray(p[k], dtype=np.float64) - np.asarray(q[k], dtype=np.float64)).max(1)
                r[k] = float(dv[alive0].max()) if alive0.any() else 0.0
                r[k + "_n"] = int(np.count_nonzero((dv > 0) & alive0))
        disc = r["behavior"] or r["keep"] or r["cause"] or r["request"] or r["wolf_cd"] or r["wolf_asleep"] or r["wolf_target"]
        if first is None and (r["pos"] > 1e-9 or r["wolf_pos"] > 1e-9 or disc):
            first = s
        if first_any is None and (r["pos"] > 0 or r["head"] > 0 or r["energy"] > 0 or r["obs"] > 0 or r["wolf_pos"] > 0 or disc):
            first_any = s
        rows.append(r)
        alive0 = pc == 0
    return dict(first_divergence=first, first_bit_difference=first_any, steps=len(rows), rows=rows)


def cmd_compare(a) -> int:
    import live

    t_all = time.perf_counter()
    snap_p = Path(a.snapshot)
    snap = live.read_snapshot(snap_p)
    brain = Path(a.brain).resolve()
    b = read_brain(brain)
    zip_p = ROOT / b["model"]["path"]
    if not zip_p.exists():
        raise SystemExit(f"두뇌 파일의 모델 zip {zip_p} 가 없다 — 파이썬 판정에 쓴다")
    wsha = ad.model_weights_sha256(zip_p)
    if wsha != b["weights_sha256"]:
        raise SystemExit(f"모델 zip 가중치 sha256 {wsha[:16]} 이 두뇌 파일 {b['weights_sha256'][:16]} 과 다르다")
    out_dir = Path(a.out) if a.out else CACHE / "compare" / f"cmp_{datetime.now():%Y%m%dT%H%M%S}"     # git 밖
    out_dir.mkdir(parents=True, exist_ok=True)
    info = live.prepare(snap_p, snap, out_dir / "prep", live.brain_folders(live.DEFAULT_ROOT))
    lo, hi = (int(x) for x in a.seeds.split("-"))
    seeds = list(range(lo, hi + 1))
    wset = parse_world_set(a.world_set)
    print(f"대조: 스냅숏 {snap_p.name}, 두뇌 {b['id']} (zip {b['model']['path']}), 시드 {lo}~{hi} × 지역 {list(info['regions'])}, 길이 {a.horizon}, "
          f"세계 {a.worlds}, 프로세스 {a.workers}, 세계 덮기 {' '.join(f'{k}={v!r}' for k, v in wset.items()) or '없음'}", flush=True)
    res: dict = dict(snapshot=snap_p.name, brain=b["id"], model=b["model"]["path"], seeds=[lo, hi], horizon=int(a.horizon), workers=int(a.workers),
                     regions=list(info["regions"]), world_set=wset, worlds={})
    out_json = out_dir / "compare.json"

    def save() -> None:
        # 단계마다 쓴다 (뒤 단계가 실패해도 앞 결과가 남게)
        res["wall_s"] = round(time.perf_counter() - t_all, 1)
        out_json.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    # 스냅숏 world 블록과 네이티브 설정 견주기 (지역마다, 시드·난수 갈래·포만(N)·팀 은신처 생명주기 빼고)
    cfg_diff = {}
    for world in a.worlds:
        items = eval_items(info, "cmp", zip_p, seeds[:1], 1, world, world_set=wset)
        for kind, tag, job in items:
            wb = world_block(make_world(job), protected_refuges=bool(a.protected_refuges))
            sw = next(r["world"] for r in snap["regions"] if r["region"] == job["region"])
            dd = []
            for k, v in sw.items():
                if k in ("seed", "rng_stream", "protected_refuges"):
                    continue
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        if kk in ("schedule_rows",) or (k == "wild_satiation" and kk == "enabled" and world == "N"):
                            continue
                        if k == "weather" and kk in ("kind", "intensity"):
                            continue
                        if wb.get(k, {}).get(kk) != vv:
                            dd.append(f"{k}.{kk}: 스냅숏 {vv!r} 네이티브 {wb.get(k, {}).get(kk)!r}")
                elif wb.get(k) != v:
                    dd.append(f"{k}: 스냅숏 {v!r} 네이티브 {wb.get(k)!r}")
            wx_s = next(r["world"]["weather"] for r in snap["regions"] if r["region"] == job["region"])
            if (wb["weather"]["kind"], wb["weather"]["intensity"]) != (wx_s["kind"], float(wx_s["intensity"]) if wx_s["kind"] != "clear" else 0.0):
                dd.append(f"weather: 스냅숏 {wx_s['kind']} {wx_s['intensity']} 네이티브 {wb['weather']['kind']} {wb['weather']['intensity']}")
            cfg_diff[f"{world}:{job['region']}"] = dd
    res["config_vs_snapshot"] = cfg_diff
    for k, dd in cfg_diff.items():
        print(f"  설정 {k}: {'스냅숏 세계와 같음' if not dd else '; '.join(dd)}", flush=True)
    for world in a.worlds:
        items = eval_items(info, "cmp", zip_p, seeds, int(a.horizon), world, world_set=wset)
        t0 = time.perf_counter()
        with live.Pool(int(a.workers)) as pool:
            py = [r for _, r in pool.run(copy.deepcopy(items))]     # 파이썬 일은 job 을 고친다(snap_food pop)
        t_py = time.perf_counter() - t0
        t0 = time.perf_counter()
        npool = Pool(int(a.workers), brain=brain, protected_refuges=bool(a.protected_refuges))
        nat = [r for _, r in npool.run(items)]
        t_nat = time.perf_counter() - t0
        st = stat_compare(py, nat)
        ex = exact_worlds(py, nat)
        wsteps = len(items) * int(a.horizon)
        py_rate = [int(a.horizon) / r["wall_s"] for r in py if r.get("wall_s")]
        nat_rate = [r["native"]["steps_per_s"] for r in nat]
        sp = dict(python_wall_s=round(t_py, 1), native_wall_s=round(t_nat, 1), native_prep_s=npool.timing.get("prep_s"),
                  native_run_s=npool.timing.get("native_s"), world_steps=wsteps,
                  python_world_steps_per_s_per_proc=float(np.mean(py_rate)) if py_rate else None,
                  native_world_steps_per_s_per_proc=float(np.mean(nat_rate)) if nat_rate else None,
                  python_world_steps_per_s_total=wsteps / t_py, native_world_steps_per_s_total=wsteps / t_nat)
        res["worlds"][world] = dict(stats=st, exact=ex, speed=sp, python=py, native=nat)
        print(f"\n세계 {world}: {len(items)} 세계 × {a.horizon} 스텝 — 기록이 정확히 같은 세계 {ex['exact']}/{ex['worlds']}", flush=True)
        print(f"  속도: 파이썬 {sp['python_world_steps_per_s_per_proc']:.0f} 세계-스텝/초/프로세스 (벽 {t_py:.1f}초), 네이티브 "
              f"{sp['native_world_steps_per_s_per_proc']:.0f} (벽 {t_nat:.1f}초, 준비 {sp['native_prep_s']}초)", flush=True)
        print(f"  {'지표':<20} {'파이썬':>10} {'네이티브':>10} {'짝차이':>9} {'sd':>8} {'z짝':>7} {'z독립':>7} 같음", flush=True)
        for name, v in st.items():
            print(f"  {name:<20} {v['py']:>10.3f} {v['native']:>10.3f} {v['diff']:>+9.3f} {v['sd_diff']:>8.3f} {v['z_paired']:>+7.2f} "
                  f"{v['z_unpaired']:>+7.2f} {v['same']}/{v['n']}", flush=True)
        save()
    if a.trace > 0:
        tr = {}
        world = a.worlds[0]
        items = eval_items(info, "cmp", zip_p, seeds[:1], int(a.trace), world, world_set=wset)
        for kind, tag, job in items:
            nj = native_job(job, 0, trace=int(a.trace), protected_refuges=bool(a.protected_refuges))
            row = run_native([nj], brain, 1)[0]
            t0 = time.perf_counter()
            d = trace_diff(python_trace(job, zip_p, int(a.trace)), row)
            name = job["region"]
            tr[name] = dict(first_divergence=d["first_divergence"], first_bit_difference=d["first_bit_difference"], rows=d["rows"],
                            wall_s=round(time.perf_counter() - t0, 1))
            fd = d["first_divergence"]
            print(f"\n궤적 {world}:{name} 시드 {job['seed']} {a.trace} 스텝: 첫 비트 차이 스텝 {d['first_bit_difference']}, 첫 갈림 스텝 {fd}", flush=True)
            for r in d["rows"][: (fd + 3 if fd is not None else 3)][-6:]:
                print(f"  t={r['t']:>4} 자리 {r['pos']:.3g} heading {r['head']:.3g} 에너지 {r['energy']:.3g} 관측 {r['obs']:.3g} 행동≠{r['behavior']} "
                      f"덮기≠{r['keep']} 요청≠{r['request']} 죽음≠{r['cause']} 늑대 {r['wolf_pos']:.3g} cd≠{r['wolf_cd']} 표적≠{r['wolf_target']} "
                      f"잠≠{r['wolf_asleep']} 무리중심 {r.get('to_centroid', 0):.3g} 분리 {r.get('separation', 0):.3g}", flush=True)
            res["trace"] = tr
            save()
    save()
    print(f"\n-> {out_json}", flush=True)
    return 0


def cmd_selftest(a) -> int:
    """PCG64 이어 받기 = numpy, 저장소 두뇌 파일(EcoBrains) 검사."""
    exe = exe_path()
    g = np.random.default_rng(34900)
    g.random(17)
    st = g.bit_generator.state["state"]
    want = [int(x) for x in g.bit_generator.random_raw(64)]
    got = [int(x) for x in subprocess.run([str(exe), "--pcg-selftest", str(st["state"]), str(st["inc"]), "64"], capture_output=True, text=True,
                                          check=True).stdout.split()]
    print(f"PCG64: {'같음' if got == want else '다름'} (64 개)")
    ok = got == want
    for f in sorted((PROJECT / "EcoBrains").glob("*.json")):
        r = subprocess.run([str(exe), "--brain-check", str(f)], capture_output=True, text=True)
        print(f"두뇌 {f.name}: {'통과 ' + r.stdout.strip() if r.returncode == 0 else '거부 ' + r.stderr.strip()}")
        ok = ok and r.returncode == 0
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("compare", help="파이썬 판정 세계와 네이티브 평가기를 같은 (스냅숏, 두뇌, 시드, 길이, 세계 N/G) 에서 견준다")
    c.add_argument("--snapshot", required=True)
    c.add_argument("--brain", required=True, help="두뇌 파일 .json (파이썬은 그 model.path zip 으로 돈다)")
    c.add_argument("--seeds", default="34900-34904")
    c.add_argument("--horizon", type=int, default=1800)
    c.add_argument("--worlds", nargs="+", default=["N", "G"], choices=["N", "G"])
    c.add_argument("--workers", type=int, default=4)
    c.add_argument("--trace", type=int, default=0, help="첫 세계(시드 처음 × 지역)의 궤적을 이만큼 스텝 대조 (0 = 끔)")
    c.add_argument("--protected-refuges", action="store_true", help="언리얼 팀 은신처 생명주기 칸도 켠다 (기본 끔 = 파이썬 세계 그대로)")
    c.add_argument("--world-set", action="append", default=[], metavar="키=값",
                   help="세계 덮기 (여러 번, 점 경로 = route_rules.py 와 같다) — 예: features.obstacles.foliage.enabled=true (숲 시야, 10-21)")
    c.add_argument("--out", default=None)
    sub.add_parser("selftest")
    a = ap.parse_args(argv)
    if a.cmd == "compare":
        return cmd_compare(a)
    return cmd_selftest(a)


if __name__ == "__main__":
    sys.exit(main())

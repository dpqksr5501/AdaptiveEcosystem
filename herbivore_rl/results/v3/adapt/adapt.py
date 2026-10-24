"""적응 고리 — 언리얼 환경 스냅숏 → 파이썬 거울 세계 → 지금 두뇌 짧게 이어 배우기 → 미리 적은 자동 관문 → 통과한 두뇌만 두뇌 파일
(10-18 사용자 '나무나 풀 같은 식생이 점점 변해서 환경이 달라지면 그 정보가 없는 상태로 사슴은 학습이 되어 있잖아? … 우리가 계획한 가중치 로더 써서 두뇌
바꿔 주는 기술을 한번 적용해 보자. 바뀌는 환경에 맞는 적응을 시키는 거지'). 관문 규칙은 results/v3/adapt/GATE.md (돌리기 전에 커밋), 쓰는 법·결과는 README.md.

    # herbivore_rl/ 에서 — 한 단계에 명령 하나 (<이름> = runs/<이름>/ 에 모든 산출물)
    python results/v3/adapt/adapt.py convert --snapshot <eco_v3_snapshot_*.json> --run <이름>   # 1) 스냅숏 → 거울 세계 (거부하면 멈춤)
    python results/v3/adapt/adapt.py check   --run <이름>                                      # 2) 재현 확인 (안 맞으면 학습하지 않는다)
    python results/v3/adapt/adapt.py train   --run <이름> [--steps 3000000] [--model-seeds 0 1]  # 3) 지금 두뇌에서 이어 배우기 (시드마다 프로세스 하나)
    python results/v3/adapt/adapt.py eval    --run <이름> --brain current                       # 4) 지금 두뇌 판정 판 (학습과 겹쳐 돌려도 된다)
    python results/v3/adapt/adapt.py select  --run <이름>                                      # 5) 후보 고르기 (고르기 세계)
    python results/v3/adapt/adapt.py eval    --run <이름> --brain candidate                     # 6) 후보 판정 판
    python results/v3/adapt/adapt.py stuck   --run <이름>                                      # 7) 끼임 세기 (지금·후보)
    python results/v3/adapt/adapt.py gate    --run <이름>                                      # 8) 관문 (GATE.md 규칙, 통과 = 0)
    python results/v3/adapt/adapt.py export  --run <이름>                                      # 9) 통과했을 때만 두뇌 파일 → AdaptiveEcosystem/Saved/EcoBrains/
    python results/v3/adapt/adapt.py all     --snapshot <파일> --run <이름>                     # 1~9 한 번에 (단계마다 걸린 시간 loop.json)
    python results/v3/adapt/adapt.py sense   --run <이름>                                      # 민감도 (가정 세계 — 게임에 없음, 보고만)

    # 언리얼 쪽 (스냅숏 쓰기 — EcoV3Snapshot.cpp, 명세 Docs/RL_Policy/SEASON_SNAPSHOT_SPEC.md 11절)
    #   PIE·단독 콘솔: eco.IntegratedV3.Snapshot            → <프로젝트>/Saved/EcoSnapshots/eco_v3_snapshot_s<세션>_t<스텝>.json
    #   헤드리스:      -EcoIntegratedV3 -EcoV3SnapshotAt=240 -EcoV3SnapshotOut=<파일>
    #   바꿔 끼우기:   eco.V3Brain.Load <내보낸 두뇌 이름>   (되돌리기 eco.V3Brain.Load builtin)

1) convert: 스냅숏을 검사하고(형식·판·계약 해시·두뇌 지문·지역 수) configs/v3_wild3_mirror.yaml(언리얼 통합 v3 기본값의 거울, 10-18 wild3/verify 로 확인)
   위에 바뀐 칸만 덮어 runs/<이름>/world.yaml(판정 세계 — 부활 없음)과 train.yaml(학습 세계 — R4 조리법: 학습 전용 40 m 밖 부활 + 지역 섞기)을 쓴다.
   스냅숏 칸마다 셋 중 하나다: (가) 대응표(MAPS)에 있는 칸 → 파이썬 설정 값으로 옮긴다, (나) 대응이 없는 칸 → 기준 스냅숏(reference_snapshot.json —
   거울이 맞춘 기본 게임 값)과 같아야 한다, 다르면 거부(파이썬에 그 규칙이 없다), (다) 기록만(IGNORE — 시드·시각·화면). 지역마다 날씨·원판(레벨 나무)·
   먹이 용량 격자(풀 — 언리얼 값 그대로 regions.json)를 싣는다. 은신처 원은 파이썬 세계가 놓는 자리와 같아야 한다(다르면 거부).
2) check: 지금 두뇌로 스냅숏 세계를 스냅숏 시각까지 돌려(시드 32050~32069 × 지역) 언리얼의 잡힘·굶음·산 수가 파이썬 분포 안인지 본다(지역마다 |z| ≤ 3).
3) train: 시작 = 스냅숏의 지금 두뇌(내장이면 R1b s3 zip — 가중치 sha256 을 맞춰 본다). train_v3.py 그대로(γ 0.995, ppo_best, 세계 8, ε 0.05, 1M 마다 저장),
   학습 세계의 먹이 지도는 스냅숏 지도(--train-food snapshot, 기본 — 지역마다 언리얼 용량 격자를 세계를 만들 때마다 덮는다) 또는 파이썬 난수 지도(random — R4 와 같다).
4)~8) 판정 세계 = world.yaml + 스냅숏 먹이 지도, 사슴 = 스냅숏 입양 수, 두뇌 argmax. 규칙·시드·문턱은 GATE.md 와 아래 GATE 상수(같은 값).
9) export: gate.json 이 통과일 때만 export_weights_v3.export_brain_file 로 두뇌 파일을 쓰고 파이썬에서 다시 읽어(sha256·골든 순전파) 확인한다.
sense: 지금 세계와 같은 규칙에 '가정' 하나씩만 바꾼 세계(덤불 빽빽·늑대가 짧게 덮치고 지침)에서 두 두뇌(R1b-F·R4)의 결과 차이를 잰다 — 두뇌 행동이 결과를
   바꿀 여지(적응이 값을 할 곳)를 보는 민감도이고, 새 세계 규칙을 만들지 않는다(있는 계수만 바꾼다). 판정이 아니다.
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
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
for p in (ROOT, ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r4", ROOT / "results" / "v3" / "wild2"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402
import yaml  # noqa: E402

TEMPLATE = ROOT / "configs" / "v3_wild3_mirror.yaml"        # 판정 세계 바탕 (언리얼 통합 v3 기본값의 거울)
R4_TRAIN = ROOT / "configs" / "v3_r4_train.yaml"            # 학습 조리법 (train 블록·부활 계수)
K2B_CONFIG = ROOT / "configs" / "v3_r1.yaml"                # 대조 K2-B: 지금 두뇌(R1b)를 배운 세계 그대로 같은 양 더 배우기
REFERENCE = HERE.parent / "reference_snapshot.json"         # 대응이 없는 칸의 기본 게임 값 (`reference` 명령으로 만든다)
RUNS = HERE.parent / "runs"
CKPT = ROOT / "ckpt" / "v3" / "adapt"
R1BF = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"       # 내장 두뇌 (PolicyWeightsV3.h = R1b s3, 세계 칸이 얼기를 막아 R1b-F)
R4 = ROOT / "ckpt" / "v3" / "v3_r4_g995_s0_20m.zip"
ECOBRAINS = ROOT.parent / "AdaptiveEcosystem" / "EcoBrains"         # 저장소에 올린 두뇌 파일
SAVED_BRAINS = ROOT.parent / "AdaptiveEcosystem" / "Saved" / "EcoBrains"   # 고리가 내보내는 곳 (git 밖, 언리얼이 찾는 폴더)
GATE_MD = HERE.parent / "GATE.md"
SNAPSHOT_FORMAT, SNAPSHOT_VERSION = "eco_v3_snapshot", 1
BEH = ("graze", "flee", "hide", "freeze", "sleep")

# 관문 (GATE.md 와 같은 값 — 바꾸면 GATE.md 변경 기록에 먼저 적는다)
GATE = dict(
    judge_seeds=(33000, 33099), judge_steps=7200,           # 판정: 시드 100 × 지역, 16 분
    select_seeds=(32060, 32079), select_steps=7200,         # 후보 고르기: 시드 20 × 지역, 16 분
    check_seeds=(32050, 32069),                             # 재현 확인: 시드 20 × 지역, 스냅숏 시각까지
    stuck_seeds=(33000, 33009), stuck_steps=7200,           # 끼임 세기: 시드 10 × 지역, 16 분
    t_crit=1.984, t_region=2.626, check_z=3.0, check_abs=3.0, shelter_x=2.0, use_min=0.01,
)
TRAIN_SEEDS = (32000, 32050)
SENSE_SEEDS = (32080, 32099)
DEFAULT_STEPS = 3_000_000

# --------------------------------------------------------------------- #
# 스냅숏 → 설정
# --------------------------------------------------------------------- #

# (가) 대응표: 스냅숏 지역 world.<블록> 의 칸 → 파이썬 features.<블록> 의 같은 이름 칸 (C++ 이 파이썬 이름을 그대로 쓴다). enabled 도 옮긴다.
FEATURE_MAPS = {
    "wild_flight": ("wild_flight", ("enabled", "alert_r", "flight_r", "safe_r", "approach", "alert_w", "rest_alert", "shelter_cos", "shelter_r",
                                    "crouch", "wall_margin", "hold_awake", "edge_r")),
    "wild_reserve": ("wild_reserve", ("enabled", "reserve_days", "init", "refill_e", "refill_frac", "weak_e", "weak_speed")),
    "wild_satiation": ("wild_satiation", ("enabled", "sat_days", "rest_speed")),
    "realism_vision": ("realism_vision", ("enabled", "threat_fov_deg")),
    "realism_hearing": ("realism_hearing", ("enabled", "s_silent", "s_quiet", "s_loud", "r_quiet", "r_loud", "roam_quiet", "cap_to_sight")),
    "shelter_food": ("realism_cover_food", ("enabled", "cap_frac", "regen_frac")),
    "pack_hunt": ("wild_pack", ("enabled", "join_r", "lead", "door_r", "door_cos", "wait_r")),
    "obstacle_rules": ("obstacles", ("enabled", "body_r", "block_sight", "no_food", "detour", "detour_block", "detour_free", "detour_probe",
                                     "detour_steps", "detour_help_block", "detour_help_drop")),
    "weather": ("wild_weather", ("enabled", "rain_sight", "rain_hear", "snow_sight", "snow_hear", "snow_deer_speed", "snow_wolf_speed",
                                 "obs_visibility")),
}
# (다) 기록만 (세계 규칙이 아니거나 다른 칸이 이미 옮긴다)
IGNORE_SETTINGS = {"seed", "weather_forest", "weather_highland", "weather_barren", "alert_dist_m", "panic_dist_m", "safe_dist_m",
                   "flight_hold_awake", "flight_edge_avoid", "wild_flight", "wild_reserve", "wild_satiation", "realism_vision", "realism_hearing",
                   "shelter_safe", "wolf_body_margin_m", "shelter_food", "pack_hunt", "obstacles", "obstacle_detour", "weather", "no_freeze",
                   "gradual_night", "wolf_eat_seconds", "wolf_eat_steps", "deer_per_region", "wolves_per_region", "stage_size_units", "pred_speed_mult",
                   "stage_trees", "obstacle_import", "social_control", "protected_refuges", "foliage"}
IGNORE_WORLD = {"seed", "rng_stream", "world_size", "num_herbivores", "num_stalkers", "num_chasers", "num_ranged", "num_nocturnal", "player_proxy",
                "pred_speed_mult", "pred_eat_cd", "eat_in_place", "realism_night", "respawn_dead", "day_period", "day_offset", "twilight_steps",
                "shelter_safe", "shelter_wolf_margin", "protected_refuges", "world_allowed", "food_rules"} | set(FEATURE_MAPS)


class Refused(SystemExit):
    """변환 거부 (까닭을 적고 멈춘다 — 학습하지 않는다)."""


def load_snapshot(path: Path) -> dict:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("format") != SNAPSHOT_FORMAT or int(d.get("version", -1)) != SNAPSHOT_VERSION:
        raise Refused(f"스냅숏 형식 {d.get('format')!r} 판 {d.get('version')!r} — {SNAPSHOT_FORMAT} 판 {SNAPSHOT_VERSION} 만 받는다")
    if not d.get("regions"):
        raise Refused("스냅숏에 지역 세계가 없다")
    return d


def scalar_fields(snap: dict) -> dict:
    """기준 스냅숏과 견줄 칸: settings 의 스칼라(IGNORE 밖) + 지역 world 의 스칼라(IGNORE 밖, 지역 이름별)."""
    out = {"settings": {k: v for k, v in snap["settings"].items() if k not in IGNORE_SETTINGS and not isinstance(v, (dict, list))}}
    out["world"] = {}
    for r in snap["regions"]:
        out["world"][r["region"]] = {k: v for k, v in r["world"].items() if k not in IGNORE_WORLD and not isinstance(v, (dict, list))}
    return out


def model_weights_sha256(path: Path) -> str:
    import export_weights_v3 as ex

    return hashlib.sha256(ex.weights_bytes(ex.extract(ex.load_model(Path(path))))).hexdigest()


def find_anchor(brain: dict) -> tuple[Path, str]:
    """스냅숏의 지금 두뇌 → 이어 배울 시작 모델 zip. 내장이면 R1b s3, 파일 두뇌면 저장소 두뇌 파일·내보낸 두뇌 파일에서 같은 가중치 sha256 의 모델 경로.
    zip 의 가중치 sha256 이 스냅숏 값과 다르면 거부한다."""
    want = str(brain.get("weights_sha256", ""))
    cands = [R1BF] if brain.get("builtin") else []
    for folder in (ECOBRAINS, SAVED_BRAINS):
        if folder.exists():
            for f in sorted(folder.glob("*.json")):
                try:
                    b = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if b.get("weights_sha256") == want and b.get("model", {}).get("path"):
                    cands.append(ROOT / b["model"]["path"])
    for c in cands:
        if c.exists() and model_weights_sha256(c) == want:
            return c, want
    raise Refused(f"지금 두뇌 {brain.get('id')} (가중치 sha256 {want[:16]}) 의 모델 zip 을 찾지 못했다 — 이어 배울 시작점이 없다")


def _set_feature(f: dict, block: str, key: str, val, log: list, src: str) -> None:
    if block not in f:
        raise Refused(f"바탕 설정에 기능 블록 {block} 이 없다 ({src})")
    old = f[block].get(key, None) if key in f[block] or key == "enabled" else "(없음)"
    if old == "(없음)":
        raise Refused(f"바탕 설정 {block} 에 칸 {key} 가 없다 ({src}) — 파이썬 대응이 없다")
    if isinstance(old, bool) or isinstance(val, bool):
        val = bool(val)
    elif isinstance(old, int) and not isinstance(old, bool) and float(val).is_integer():
        val = int(val)
    else:
        val = float(val)
    if old != val:
        log.append(dict(key=f"features.{block}.{key}", template=old, snapshot=val, src=src))
    f[block][key] = val


def convert(snap: dict, reference: dict | None, template: Path | None = None, start: Path | None = None, contract: str | None = None,
            recipe: Path | None = None) -> dict:
    """스냅숏 → {world: 판정 세계 설정 dict, train: 학습 세계 설정 dict, regions: 지역 자료, record: 변환 기록}. 거부는 Refused.
    실시간 고리(results/v3/live/live.py)용 선택 인자 — 주지 않으면 지금과 같다: template = 바탕 설정(고리는 관측 21 거울), start = 이어 배울 시작 모델
    zip(부르는 쪽이 고르고 확인했다 — 주면 find_anchor 를 쓰지 않는다), contract = 시작 모델이 맞춰야 할 계약 해시(없으면 스냅숏 맨 위 contract_hash),
    recipe = 학습 조리법 설정(train 블록·부활 계수, 없으면 R4)."""
    from env_v2.config import load_v2_config
    from env_v2.world import World
    from env.config import Config

    import export_weights_v3 as ex

    template = Path(template) if template is not None else TEMPLATE
    raw = yaml.safe_load(template.read_text(encoding="utf-8"))
    changed: list[dict] = []
    checks: list[str] = []
    S = snap["settings"]
    regs = snap["regions"]
    names = [r["region"] for r in regs]
    if len(set(names)) != len(names):
        raise Refused(f"지역 이름이 겹친다: {names}")
    w0 = regs[0]["world"]
    for r in regs[1:]:
        for k, v in r["world"].items():
            if k in ("rng_stream", "weather", "seed"):
                continue
            if v != w0[k]:
                raise Refused(f"지역 {r['region']} 의 세계 칸 {k} 가 {regs[0]['region']} 와 다르다 ({v!r} 대 {w0[k]!r}) — 지역마다 다른 규칙은 아직 옮기지 않는다")

    # 계약·두뇌
    if start is None:
        anchor, wsha = find_anchor(snap["brain"])
    else:
        anchor = Path(start)
        if not anchor.exists():
            raise Refused(f"시작 모델 {anchor} 가 없다")
        wsha = model_weights_sha256(anchor)
    from stable_baselines3 import PPO

    pol = PPO.load(str(anchor), device="cpu").policy
    chash = f"0x{ex.contract_hash(tuple(pol.rep_obs_names), int(getattr(pol, 'rep_mask_version', 1))):016x}"
    want = snap["contract_hash"] if contract is None else str(contract)
    if chash != want:
        raise Refused(f"계약 해시가 다르다: {'스냅숏' if contract is None else '바라는 계약'} {want} 대 시작 모델 {chash} — 관측·행동 계약이 다른 빌드다")
    checks.append(f"계약 해시 {chash} = 시작 모델")
    if start is None:
        checks.append(f"지금 두뇌 {snap['brain']['id']} = {_rel(anchor)} (가중치 sha256 {wsha[:16]})")
    else:
        checks.append(f"시작 모델 {_rel(anchor)} (가중치 sha256 {wsha[:16]}) — 지금 두뇌 {snap['brain']['id']} 에서 부르는 쪽이 골랐다")

    # (가) 대응표 — 무대·사슴·늑대·식사·낮밤·얼기
    ov = raw.setdefault("overrides", {})
    rand = ov.setdefault("rand", {})
    size = float(S["stage_size_units"])
    if any(float(r["size"]) != size or float(r["world"]["world_size"]) != size for r in regs):
        raise Refused("지역 무대 한 변이 설정과 다르다")
    for key, val in (("world_size", [size, size]), ("pred_speed_mult", [float(w0["pred_speed_mult"])] * 2),
                     ("food_regen_mult", [float(w0["food_rules"]["regen_mult"])] * 2)):
        if rand.get(key) != val:
            changed.append(dict(key=f"overrides.rand.{key}", template=rand.get(key), snapshot=val, src=f"settings/world"))
        rand[key] = val
    wolves = int(S["wolves_per_region"])
    stalk, chase = int(w0["num_stalkers"]), int(w0["num_chasers"])
    if (stalk, chase) != ((wolves + 1) // 2, wolves // 2) or int(w0["num_ranged"]) or int(w0["num_nocturnal"]) or w0["player_proxy"]:
        raise Refused(f"늑대 구성 잠행 {stalk}·추격 {chase}·원거리 {w0['num_ranged']}·야행 {w0['num_nocturnal']} 이 파이썬 wolf_kinds alternate 와 다르다")
    if rand.get("predator_count") != [wolves, wolves]:
        changed.append(dict(key="overrides.rand.predator_count", template=rand.get("predator_count"), snapshot=[wolves, wolves], src="settings"))
    rand["predator_count"] = [wolves, wolves]
    eat = int(w0["pred_eat_cd"])
    if ov.get("pred_eat_cd") != eat:
        changed.append(dict(key="overrides.pred_eat_cd", template=ov.get("pred_eat_cd"), snapshot=eat, src="world"))
    ov["pred_eat_cd"] = eat
    f = raw["features"]
    _set_feature(f, "threats", "eat_in_place", w0["eat_in_place"], changed, "world.eat_in_place")
    _set_feature(f, "realism_night", "enabled", w0["realism_night"], changed, "world.realism_night")
    if w0["respawn_dead"]:
        raise Refused("언리얼 세계가 죽은 사슴을 되살린다 — 판정 세계(부활 없음)와 다르다")
    period = int(w0["day_period"])
    if f["daynight"]["periods"] != [period]:
        changed.append(dict(key="features.daynight.periods", template=f["daynight"]["periods"], snapshot=[period], src="world"))
    f["daynight"]["periods"] = [period]
    tw = int(w0["twilight_steps"])
    if int(math.floor(float(f["daynight"]["twilight"]) * period + 0.5)) != tw:
        raise Refused(f"박명 {tw} 스텝이 파이썬 twilight {f['daynight']['twilight']} × {period} 와 다르다")
    _set_feature(f, "integrated_stage", "day_offset", w0["day_offset"], changed, "world.day_offset")
    # 허용 칸 = 실제 허용(지금 두뇌 ∧ 세계 칸, 지역 allowed). 세계 칸만 옮기면 두뇌에 없는 행동(잠)이 학습 목록에 들어가 새 두뇌가 그 행동을 배운다
    effs = {tuple(int(x) for x in r["allowed"]) for r in regs}
    if len(effs) != 1:
        raise Refused(f"지역마다 실제 허용 칸이 다르다: {sorted(effs)}")
    allowed = [b for b, on in zip(BEH, effs.pop()) if on]
    if "graze" not in allowed:
        raise Refused(f"실제 허용 칸 {allowed} 에 먹기가 없다")
    if raw["train"]["repertoire"]["allowed"] != allowed:
        changed.append(dict(key="train.repertoire.allowed", template=raw["train"]["repertoire"]["allowed"], snapshot=allowed, src="regions.allowed (두뇌 ∧ 세계)"))
    raw["train"]["repertoire"]["allowed"] = allowed
    if S.get("social_control"):
        raise Refused("팀 Social 행동 연결(eco.IntegratedV3.SocialControl 1)을 켠 세계다 — 파이썬에 그 규칙이 없다")
    # 숲 시야 (eco.IntegratedV3.Foliage, 10-22 C++ — 스냅숏 world.obstacle_rules.foliage·foliage_r·foliage_block, obstacles.foliage_trees). 파이썬
    # features.obstacles.foliage {enabled, r, block, trees} 대응(지역마다 나무 표·덤불 원판 덧붙이기)을 아직 옮기지 않았다 — 끈 세계로 조용히 바꾸지 않고
    # 거부한다. 켠 세계 = C++ FObstacleConfig::FoliageConfigured (장애물 ∧ 눈길 가림 ∧ 숲 시야). 옛 스냅숏(칸 없음)은 끈 세계다
    ob0 = w0["obstacle_rules"]
    if ob0.get("foliage") and ob0.get("enabled") and ob0.get("block_sight"):
        raise Refused(f"숲 시야(eco.IntegratedV3.Foliage 1 — 잎 r {ob0.get('foliage_r')}·block {ob0.get('foliage_block')})를 켠 세계다 — "
                      "adapt 대응(features.obstacles.foliage)을 아직 옮기지 않았다")
    # 은신처 안전·몸 여유
    _set_feature(f, "realism_shelter", "enabled", w0["shelter_safe"], changed, "world.shelter_safe")
    _set_feature(f, "realism_shelter", "wolf_margin", w0["shelter_wolf_margin"], changed, "world.shelter_wolf_margin")
    if w0["protected_refuges"]:
        bad = [r["region"] for r in regs if any(float(c[2]) <= 0.0 for c in r["covers"])]
        if bad:
            raise Refused(f"지워진 은신처(반지름 0)가 있다 {bad} — 팀 은신처 생명주기는 파이썬에 없다")
        checks.append("팀 은신처 생명주기(ProtectedRefuges) 켬 — 지워진 은신처 없음이라 세계가 같다")
    # 기능 블록 계수
    for sblock, (pblock, keys) in FEATURE_MAPS.items():
        for k in keys:
            _set_feature(f, pblock, k, w0[sblock][k], changed, f"world.{sblock}.{k}")
    if int(w0["weather"]["schedule_rows"]) != 0:
        raise Refused("날씨 시간표가 있다 — 스냅숏이 시간표를 싣지 않는다(고정 날씨만 옮긴다)")
    wx_regions = {}
    for r in regs:
        wx = r["world"]["weather"]
        wx_regions[r["region"]] = [str(wx["kind"]), float(wx["intensity"]) if str(wx["kind"]) != "clear" else 0.0]
    if f["wild_weather"].get("regions") != wx_regions:
        changed.append(dict(key="features.wild_weather.regions", template=f["wild_weather"].get("regions"), snapshot=wx_regions, src="regions.world.weather"))
    f["wild_weather"]["regions"] = wx_regions
    f["wild_weather"]["region"] = names[0]
    discs = {r["region"]: [[float(v) for v in t] for t in r["obstacles"]["discs"]] for r in regs}
    f["obstacles"]["fixed"] = discs[names[0]]

    # 먹이 규칙 (파이썬 v1 상수) — 다르면 거부 (컴파일 상수·학습 상수)
    deer = {int(r["deer"]["adopted"]) for r in regs}
    if len(deer) != 1:
        raise Refused(f"지역마다 사슴 수가 다르다 {sorted(deer)} — 판정 세계 N 은 하나다")
    N = deer.pop()
    raw["version"] = "3.adapt"
    tmp = HERE.parent / f".convert_tmp_{os.getpid()}.yaml"            # 프로세스마다 따로 (고리 둘이 겹쳐 돌아도)
    tmp.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    try:
        cfg = load_v2_config(tmp).replace(N=N)
    finally:
        tmp.unlink(missing_ok=True)
    fr = w0["food_rules"]
    for sk, pk in (("cell", "food_cell"), ("patch_blur", "food_patch_blur"), ("patch_threshold", "food_patch_threshold"),
                   ("grad_blur", "food_grad_blur"), ("regen_base", "food_regen_base"), ("cover_regen_mult", "food_cover_regen_mult")):
        if float(fr[sk]) != float(getattr(cfg, pk)):
            raise Refused(f"먹이 규칙 {sk} {fr[sk]} 이 파이썬 {pk} {getattr(cfg, pk)} 와 다르다 — 학습 상수다")
    checks.append("먹이 규칙(셀·패치·문턱·기울기·재생) = 파이썬 상수")

    # (나) 기준 스냅숏과 견주기
    if reference is not None:
        mine = scalar_fields(snap)
        for k, v in mine["settings"].items():
            if k in reference["settings"] and reference["settings"][k] != v:
                if k == "extra_cover_count" and v == 0:
                    # 10-25 저작 은신처 맵(조정자 bV3UseAuthoredShelters — 팀 생태계 맵 LV_JYU_Ecosystem·우리 복사본): v3 가 은신처를 놓지 않고(0) 레벨
                    # 은신처를 쓴다. 누가 놓았나는 세계 규칙이 아니다 — 세계 은신처 원은 아래 '은신처 원·먹이 격자'에서 파이썬 자리와 견주고 다르면 거부한다
                    checks.append("v3 가 놓는 은신처 0 (레벨 저작 은신처 맵) — 은신처 원은 파이썬 자리와 따로 견준다")
                    continue
                raise Refused(f"설정 {k} = {v!r} 가 기준 게임 값 {reference['settings'][k]!r} 과 다르고 파이썬 대응이 없다")
        ref_w = next(iter(reference["world"].values()))
        for reg, row in mine["world"].items():
            for k, v in row.items():
                if k in ref_w and ref_w[k] != v:
                    raise Refused(f"지역 {reg} 세계 칸 {k} = {v!r} 가 기준 게임 값 {ref_w[k]!r} 과 다르고 파이썬 대응이 없다")
        checks.append(f"대응표 밖 칸 {len(mine['settings'])} + 지역마다 {len(next(iter(mine['world'].values())))} 개 = 기준 게임 값")
    else:
        checks.append("기준 스냅숏 없음 — 대응표 밖 칸을 견주지 않았다 (reference 명령으로 만든다)")

    # 은신처 원·먹이 격자
    regions = {}
    for r in regs:
        c = copy.deepcopy(cfg.to_dict())
        c["v2"]["features"]["wild_weather"]["region"] = r["region"]
        c["v2"]["features"]["obstacles"]["fixed"] = discs[r["region"]]
        w = World(Config(c), seeds=[GATE["check_seeds"][0]])
        mine = sorted((round(float(x), 9), round(float(y), 9), round(float(rr), 9)) for (x, y), rr in zip(w.cov_c, w.cov_r))
        theirs = sorted((round(float(x), 9), round(float(y), 9), round(float(rr), 9)) for x, y, rr in r["covers"])
        if mine != theirs:
            raise Refused(f"지역 {r['region']} 은신처 원 {theirs} 이 파이썬 세계 {mine} 와 다르다 — 파이썬은 은신처를 정한 자리(quad)에만 놓는다")
        fd = r["food"]
        g = int(fd["gw"])
        if g != int(w.gw) or len(fd["cap"]) != g * g or len(fd["food"]) != g * g:
            raise Refused(f"지역 {r['region']} 먹이 격자 {g}×{g} 이 파이썬 {w.gw}×{w.gw} 와 다르다")
        cap = np.asarray(fd["cap"], dtype=np.float64)
        if not np.all(np.isfinite(cap)) or cap.min() < 0.0:
            raise Refused(f"지역 {r['region']} 먹이 용량에 음수·수가 아닌 값이 있다")
        rebuild = None
        import run_mirror as rm

        if r["region"] in rm.UNREAL_REGION_STREAM and int(r["world"]["rng_stream"]) == rm.UNREAL_REGION_STREAM[r["region"]]:
            # 보고만: 풀이 처음 그대로면 스냅숏 용량 = C++ 세계 난수(세션 시드·지역 갈래)로 다시 만든 지도 (배치·방향 확인 — 식생이 바뀌었으면 다르다)
            w2 = World(Config(c), seeds=[GATE["check_seeds"][0]])
            rm.apply_unreal_map(w2, int(snap["session_seed"]), r["region"])
            rebuild = float(np.abs(w2.food_cap - cap.reshape(g, g)).max())
            checks.append(f"{r['region']} 먹이 용량 ↔ C++ 난수로 다시 만든 지도: 최대 차이 {rebuild:.3g} (보고만 — 0 이면 풀이 처음 지도 그대로)")
        regions[r["region"]] = dict(region=r["region"], region_index=int(r["region_index"]), discs=discs[r["region"]],
                                    weather=wx_regions[r["region"]], covers=r["covers"], gw=g, cap=fd["cap"], food=fd["food"],
                                    cap_total=float(cap.sum()), food_total=float(np.sum(fd["food"])),
                                    python_cap_total=float(w.food_cap.sum()), cpp_rebuild_max_diff=rebuild,
                                    t=int(r["t"]), deer=r["deer"], wolves=r["wolves"],
                                    level_trees=int(r["obstacles"]["level_trees"]), level_trees_unmatched=int(r["obstacles"]["level_trees_unmatched"]))
    checks.append("은신처 원 = 파이썬 세계 (지역마다)")

    # 학습 세계 = 판정 세계 + R4 학습 바꿈 (학습 전용 부활, 학습 시드 풀, train 블록 + 지역 섞기)
    r4 = yaml.safe_load((Path(recipe) if recipe is not None else R4_TRAIN).read_text(encoding="utf-8"))
    train = copy.deepcopy(raw)
    train["version"] = "3.adapt.train"
    train["overrides"]["train_seeds"] = list(TRAIN_SEEDS)
    ist = train["features"]["integrated_stage"]
    for k in ("respawn", "respawn_safe_r", "respawn_tries"):
        ist[k] = r4["features"]["integrated_stage"][k]
    tb = copy.deepcopy(r4["train"])
    tb["repertoire"]["allowed"] = allowed
    tb["region_mix"] = dict(regions=names, weights=[1] * len(names), obstacles={n: discs[n] for n in names})
    train["train"] = tb
    record = dict(snapshot=dict(map=snap.get("map"), session_seed=snap["session_seed"], global_step=snap["global_step"],
                                sim_seconds=snap["sim_seconds"], why=snap.get("why"), brain=snap["brain"]["id"], tree_layout=snap.get("tree_layout")),
                  anchor=_rel(anchor), anchor_weights_sha256=wsha, N=N, regions=names,
                  changed=changed, checks=checks, template=_rel(template),
                  f_dec_note="f_dec·ent_coef_base 는 R4 학습 세계에서 잰 값 그대로 (규칙이 같은 세계 — 규칙이 바뀌면 train_v3.py measure-fdec 로 다시 잰다)")
    return dict(world=raw, train=train, regions=regions, record=record)


def run_dir(run: str) -> Path:
    return RUNS / run


def write_yaml(path: Path, d: dict, head: str) -> None:
    path.write_text(head + yaml.safe_dump(d, allow_unicode=True, sort_keys=False), encoding="utf-8", newline="\n")


def load_run(run: str) -> dict:
    d = run_dir(run)
    if not (d / "convert.json").exists():
        raise SystemExit(f"{d} 에 convert.json 이 없다 — convert 부터")
    rec = json.loads((d / "convert.json").read_text(encoding="utf-8"))
    if "refused" in rec:
        raise SystemExit(f"{d.name} 변환이 거부됐다: {rec['refused']}")
    return dict(record=rec, regions=json.loads((d / "regions.json").read_text(encoding="utf-8")), dir=d)


# --------------------------------------------------------------------- #
# 세계 돌리기 (거울 실행기 + 스냅숏 먹이 지도)
# --------------------------------------------------------------------- #


def apply_snapshot_food(w, cap, food=None) -> None:
    """세계 w 의 먹이 용량(과 먹이)을 스냅숏 격자로 덮고 관측을 다시 만든다. 언리얼 Cap 은 원판 밑·은신처 배수까지 건 최종 용량이라 배수를 다시 걸지 않는다.
    언리얼 셀 k = iy·gw + ix 는 파이썬 food_cap[iy, ix] 다(run_mirror.apply_unreal_map 과 같은 배치)."""
    g = int(w.gw)
    c = np.asarray(cap, dtype=np.float64)
    if c.size != g * g:
        raise ValueError(f"먹이 격자 {c.size} 칸이 세계 {g}×{g} 와 다르다")
    w.food_cap = c.reshape(g, g).copy()
    w.food = (np.asarray(food, dtype=np.float64).reshape(g, g) if food is not None else w.food_cap).copy()
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)


def snapshot_food_vec_env(Base, food: dict):
    """학습 세계 묶음 + 스냅숏 먹이 지도: 지역 섞기가 고른 지역의 언리얼 용량 격자를 세계를 만들 때마다(처음·교체) 덮는다. 나머지(시작 자리·늑대·부활)는 시드 그대로.
    train_v3.py 를 고치지 않으려고 그 모듈의 MultiWorldVecEnv 자리에 이 하위 클래스를 넣는다(train-one 프로세스 안에서만)."""

    class SnapshotFoodVecEnv(Base):
        def __init__(self, cfg, *args, **kw):
            super().__init__(cfg, *args, **kw)
            if self.region_history is None:
                raise SystemExit("--train-food snapshot 은 지역 섞기(train.region_mix) 세계에서만 쓴다")
            for k, w in enumerate(self.worlds):
                apply_snapshot_food(w, food[self.region_history[k][-1]])
                if self.rep is not None:
                    self._set_mask(k, w.observe())

        def _renew(self, k):
            super()._renew(k)
            w = self.worlds[k]
            apply_snapshot_food(w, food[self.region_history[k][-1]])
            return w.observe()

    return SnapshotFoodVecEnv


def _patch_food(cap) -> None:
    """이 프로세스의 거울 실행기·끼임 도구가 '언리얼 지도' 자리에서 스냅숏 지도를 쓰게 한다 (워커 안에서만 부른다)."""
    import run_mirror as rm

    rm.apply_unreal_map = lambda w, seed, region: apply_snapshot_food(w, cap)


def _world_one(job: dict) -> dict:
    """세계 하나 → 요약 (r4_eval._one 과 같은 칸). job['snap_food'] = 그 지역 스냅숏 용량."""
    import r4_eval

    _patch_food(job.pop("snap_food"))
    return r4_eval._one(job)


def _world_short(job: dict) -> dict:
    """재현 확인: 진단 없이 스냅숏 시각까지 → 잡힘·굶음·산."""
    import run_mirror as rm

    _patch_food(job.pop("snap_food"))
    res = rm.run_world(job)
    cause = np.asarray(res["meta"]["death_cause"])
    return dict(seed=res["meta"]["seed"], region=job["region"], n=res["meta"]["n"], caught=int((cause == 1).sum()),
                starved=int((cause == 2).sum()), alive=int((cause == 0).sum()), wall_s=res["meta"]["wall_s"])


def _stuck_one(job: dict) -> dict:
    import stuck_check

    _patch_food(job.pop("snap_food"))
    out = stuck_check.one(job)
    out["region"] = job["region"]
    return out


def world_cfg(info: dict, variant: dict | None = None):
    import run_mirror as rm

    cfg = rm.mirror_cfg(int(info["record"]["N"]), int(yaml.safe_load((info["dir"] / "world.yaml").read_text(encoding="utf-8"))["overrides"]["pred_eat_cd"]),
                        info["dir"] / "world.yaml")
    return cfg


def make_jobs(info: dict, model: Path, seeds, steps: int, diag: bool = True, variant: dict | None = None) -> list[dict]:
    cfg = world_cfg(info)
    base = cfg.to_dict()
    jobs = []
    for s in seeds:
        for name, r in info["regions"].items():
            c = copy.deepcopy(base)
            c["v2"]["features"]["wild_weather"]["region"] = name
            c["v2"]["features"]["obstacles"]["fixed"] = copy.deepcopy(r["discs"])
            if variant is not None:
                apply_variant(c, variant, r)
            jobs.append(dict(cfg=c, seed=int(s), steps=int(steps), model=str(model), log_every=int(steps) + 1, diag=diag, region=name,
                             unreal_map=dict(seed=int(info["record"]["snapshot"]["session_seed"]), region=name, snapshot=True), snap_food=r["cap"]))
    return jobs


def run_jobs(fn, jobs: list[dict], workers: int) -> list[dict]:
    from env_v2 import rollout as ro

    ex = ro.make_executor(min(int(workers), len(jobs)))
    if ex is None:
        return [fn(j) for j in jobs]
    with ex:
        return list(ex.map(fn, jobs))


def seed_list(lo_hi) -> list[int]:
    return list(range(int(lo_hi[0]), int(lo_hi[1]) + 1))


def eval_brain(info: dict, model: Path, seeds, steps: int, workers: int, variant: dict | None = None) -> dict:
    t0 = time.perf_counter()
    worlds = run_jobs(_world_one, make_jobs(info, model, seeds, steps, True, variant), workers)
    sha = hashlib.sha1(Path(model).read_bytes()).hexdigest()[:12]
    meta = dict(run=info["dir"].name, model=_rel(model), model_sha1=sha, seeds=[int(s) for s in seeds], regions=list(info["regions"]),
                steps=int(steps), variant=variant["name"] if variant else None, wall_s=round(time.perf_counter() - t0, 1))
    return dict(meta=meta, worlds=worlds)


def _rel(p) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


# --------------------------------------------------------------------- #
# 관문
# --------------------------------------------------------------------- #


def gate_eval(cur: dict, cand: dict, stuck_cur: dict | None, stuck_cand: dict | None, k2b: dict | None) -> dict:
    """GATE.md 규칙. 1차 P1(16분 잡힌 몫이 지금 두뇌보다 유의하게 낮다)과 지킴 G1~G6 이 모두 통과해야 통과. P1 을 넘으면 P1b(K2-B 보다도 낮다)를 본다 —
    K2-B 판이 없으면 '보류'(통과 아님)."""
    import r4_eval as re_

    T, TR = GATE["t_crit"], GATE["t_region"]
    c: dict = {}
    p = re_.paired(re_.per_seed(cand, "caught"), re_.per_seed(cur, "caught"))
    c["P1_caught"] = dict(p, ok=bool(p["diff"] < 0 and p["t"] <= -T), rule="후보 − 지금 < 0 이고 짝 t ≤ −1.984")
    p = re_.paired(re_.per_seed(cand, "starved"), re_.per_seed(cur, "starved"))
    c["G1_starved"] = dict(p, ok=bool(p["t"] < T), rule="짝 t < +1.984")
    p = re_.paired(re_.per_seed(cand, "alive"), re_.per_seed(cur, "alive"))
    c["G2_alive"] = dict(p, ok=bool(p["t"] > -T), rule="짝 t > −1.984")
    for r in sorted({w["region"] for w in cur["worlds"]}):
        for key, sign in (("caught", 1), ("starved", 1), ("alive", -1)):
            p = re_.paired(re_.per_seed(cand, key, r), re_.per_seed(cur, key, r))
            ok = p["t"] < TR if sign > 0 else p["t"] > -TR
            c[f"G3_{r}_{key}"] = dict(p, ok=bool(ok), rule="짝 t < +2.626" if sign > 0 else "짝 t > −2.626")
    a, b = re_.pooled(cand), re_.pooled(cur)
    c["G4_catch_in_shelter"] = dict(value=a["catch_cover"], ok=a["catch_cover"] == 0, rule="후보 판정 세계 모두 0")
    if stuck_cand is not None and stuck_cur is not None:
        sd, sw = re_.stuck_counts(stuck_cand), re_.stuck_counts(stuck_cur)
        c["G5_stuck"] = dict(candidate=sd, current=sw, ok=bool(sd["deer"] == 0 and sd["wolf"] <= sw["wolf"]), rule="사슴 원판 끼임 0, 늑대 원판 끼임 ≤ 지금")
    else:
        c["G5_stuck"] = dict(ok=None, rule="끼임 세기가 없다")
    use_ok = all(a["beh"][x] > GATE["use_min"] for x in ("graze", "flee", "hide"))
    c["G6_no_exploit"] = dict(shelter=a["shelter"], shelter_current=b["shelter"], beh=a["beh"],
                              ok=bool(a["shelter"] <= GATE["shelter_x"] * b["shelter"] and use_ok), rule="은신처 안 몫 ≤ 지금의 2배, 먹기·도망·숨기 모두 1% 넘게")
    if k2b is not None:
        p = re_.paired(re_.per_seed(cand, "caught"), re_.per_seed(k2b, "caught"))
        c["P1b_vs_k2b"] = dict(p, ok=bool(p["diff"] < 0 and p["t"] <= -T), rule="후보 − K2-B < 0 이고 짝 t ≤ −1.984 (그냥 더 배워서가 아님)")
    guards = [v["ok"] for k, v in c.items() if k.startswith("G")]
    if not c["P1_caught"]["ok"]:
        verdict = "기각"
        why = f"1차 P1 실패: 16분 잡힌 몫 후보 {c['P1_caught']['a']:.4f} 대 지금 {c['P1_caught']['b']:.4f} (짝 t {c['P1_caught']['t']:+.2f}, 문턱 −1.984)"
    elif None in guards:
        verdict, why = "보류", "끼임 세기가 없다 — stuck 을 돌린다"
    elif not all(guards):
        verdict = "기각"
        why = "지킴 기준 실패: " + ", ".join(k for k, v in c.items() if k.startswith("G") and v["ok"] is False)
    elif k2b is None:
        verdict, why = "보류", "P1·지킴 통과 — K2-B(같은 양을 원래 세계에서 더 배운 두뇌)를 재야 한다: train --control 뒤 eval --brain k2b"
    elif not c["P1b_vs_k2b"]["ok"]:
        verdict, why = "기각", "P1b 실패: K2-B 보다 덜 잡히지 않는다 — 스냅숏 정보 덕분이 아니라 그냥 더 배운 몫"
    else:
        verdict, why = "통과", "P1·P1b·지킴 G1~G6 모두 통과"
    rep = dict(pooled_candidate=a, pooled_current=b, shelter=re_.paired(re_.per_seed(cand, "shelter"), re_.per_seed(cur, "shelter")))
    return dict(verdict=verdict, passed=verdict == "통과", why=why, criteria=c, report=rep, rules=GATE,
                gate_md_sha256=hashlib.sha256(GATE_MD.read_bytes()).hexdigest() if GATE_MD.exists() else None)


def fmt_gate(g: dict) -> str:
    lines = ["| 기준 | 후보 | 지금 두뇌 | 차이 | t | 규칙 | 통과 |", "|---|---|---|---|---|---|---|"]
    for k, v in g["criteria"].items():
        if "diff" in v:
            ref = "K2-B" if k == "P1b_vs_k2b" else ""
            lines.append(f"| {k} | {v['a']:.4f} | {v['b']:.4f}{(' (' + ref + ')') if ref else ''} | {v['diff']:+.4f} ± {v['se']:.4f} | {v['t']:+.2f} | {v['rule']} | "
                         f"{'예' if v['ok'] else '아니오'} |")
        else:
            val = {x: y for x, y in v.items() if x not in ("ok", "rule")}
            lines.append(f"| {k} | {json.dumps(val, ensure_ascii=False)} | | | | {v['rule']} | {'—' if v['ok'] is None else ('예' if v['ok'] else '아니오')} |")
    lines += ["", f"**{g['verdict']}** — {g['why']}"]
    return "\n".join(lines)


# --------------------------------------------------------------------- #
# 두뇌 파일 확인 (파이썬에서 다시 읽기)
# --------------------------------------------------------------------- #


def verify_brain_file(path: Path) -> dict:
    """두뇌 파일을 다시 읽어 가중치 sha256 과 골든(관측 → 로짓·행동)을 numpy float32 순전파로 확인한다 (언리얼 로더와 같은 검사의 파이썬 판)."""
    import base64

    import export_weights_v3 as ex

    d = json.loads(Path(path).read_text(encoding="utf-8"))
    w, blob = {}, b""
    for L in d["layers"]:
        wb, bb = base64.b64decode(L["w_f32le_b64"]), base64.b64decode(L["b_f32le_b64"])
        blob += wb + bb
        w[L["weight"]] = np.frombuffer(wb, dtype="<f4").reshape(L["out"], L["in"])
        w[L["bias"]] = np.frombuffer(bb, dtype="<f4")
    sha_ok = hashlib.sha256(blob).hexdigest() == d["weights_sha256"]
    obs = np.asarray([c["obs"] for c in d["golden"]["cases"]], dtype=np.float32)
    mask = np.asarray([c["mask"] for c in d["golden"]["cases"]], dtype=bool)
    want = np.asarray([c["logits"] for c in d["golden"]["cases"]], dtype=np.float32)
    got = ex.forward_np(obs, w, np.float32)
    err = float(np.abs(got - want).max())
    act_ok = bool(np.array_equal(ex.masked_argmax(got, mask), np.asarray([c["action"] for c in d["golden"]["cases"]])))
    tol = float(d["golden"]["logit_tolerance"])
    return dict(file=_rel(path), id=d["id"], sha256_ok=sha_ok, golden=len(obs), max_logit_err=err, tolerance=tol, actions_ok=act_ok,
                finite=bool(np.all([np.all(np.isfinite(v)) for v in w.values()])), ok=bool(sha_ok and err <= tol and act_ok))


# --------------------------------------------------------------------- #
# 민감도 (가정 세계 — 보고만)
# --------------------------------------------------------------------- #

SHRUB_PER_HA = 150.0            # 덤불 빽빽: 무대 1.44 ha 에 약 216 그루, 반지름 1~2 m (가정 — 숲 속 관목층)
SHRUB_R = (0.5, 1.0)
SHRUB_TAG = 0x5348524255        # "SHRUB"


SHORT_SETS = {"integrated_stage.wolf_kinds": None, "threats.stalk_frac": [1.0, 1.0], "threats.pounce_steps": 8, "threats.exhaust_steps": 75}


def variants() -> dict:
    """가정 세계 (있는 규칙의 계수만 바꾼다 — 새 규칙 없음). dense = 지역마다 덤불 원판을 더함(세로 장애물 규칙: 이동·눈길을 막음, 1.44 ha 에 약 216 개,
    반지름 1~2 m), short = '늑대가 짧게 쫓다 그만둠'에 가장 가까운 지금 계수 — 늑대 넷 모두 잠행-돌진형(살금살금 다가가 덮침)이고 덮치기는 1.07 초(8 스텝,
    지금 12)만, 놓치면 10 초(75 스텝, 지금 30) 지쳐 쉼. both = 둘 다. 추격형의 '보이는 동안 끝까지 쫓기'는 이 세계에 없다(모두 잠행형).
    덮치기 8 스텝은 지금 두뇌의 사냥 성공률이 현실 띠(10~30%, 야생 2단계 명세)의 가운데쯤(21%)이 되는 값이다 — 시드 32080~32083 × 지역 × 240 초로
    6·8·10·12 스텝을 재서(7.5·21.2·45.3·63.4%, 지금 세계 70.7%) 골랐다(README '민감도')."""
    return {
        "base": dict(name="base"),
        "dense": dict(name="dense", shrubs=True),
        "short": dict(name="short", sets=SHORT_SETS),
        "both": dict(name="both", shrubs=True, sets=SHORT_SETS),
    }


def cmd_derive(a) -> int:
    """가정 세계 고리: 있는 고리(--run)의 세계에 변형 하나(--variant)를 구워 새 고리 폴더(--to)를 만든다. 언리얼에 없는 세계라 재현 확인은 하지 않는다."""
    src = load_run(a.run)
    v = variants()[a.variant]
    d = run_dir(a.to)
    d.mkdir(parents=True, exist_ok=True)
    world = yaml.safe_load((src["dir"] / "world.yaml").read_text(encoding="utf-8"))
    train = yaml.safe_load((src["dir"] / "train.yaml").read_text(encoding="utf-8"))
    regions = copy.deepcopy(src["regions"])
    size = float(world["overrides"]["rand"]["world_size"][0])
    for r in regions.values():
        if v.get("shrubs"):
            r["discs"] = list(r["discs"]) + shrub_discs(r["region_index"], size, r["covers"])
    for k, val in (v.get("sets") or {}).items():
        blk, key = k.split(".", 1)
        world["features"][blk][key] = val
        train["features"][blk][key] = val
    names = list(regions)
    world["features"]["obstacles"]["fixed"] = regions[names[0]]["discs"]
    train["features"]["obstacles"]["fixed"] = regions[names[0]]["discs"]
    train["train"]["region_mix"]["obstacles"] = {n: regions[n]["discs"] for n in names}
    head = f"# 가정 세계 고리 {a.to} = 고리 {a.run} + 변형 {a.variant} (results/v3/adapt/adapt.py derive — 게임에 없는 세계, 보고만)\n"
    write_yaml(d / "world.yaml", world, head)
    write_yaml(d / "train.yaml", train, head)
    (d / "regions.json").write_text(json.dumps(regions, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    rec = dict(src["record"], derived_from=a.run, variant=v)
    (d / "convert.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (d / "check.json").write_text(json.dumps(dict(ok=None, why="가정 세계 — 언리얼에 없어 재현 확인을 하지 않는다"), ensure_ascii=False) + "\n",
                                  encoding="utf-8", newline="\n")
    print(f"가정 세계 고리 {a.to}: 변형 {a.variant}, 원판 " + ", ".join(f"{n} {len(r['discs'])}" for n, r in regions.items()))
    return 0


def shrub_discs(region_index: int, size: float, covers) -> list:
    from env_v2.world import obstacle_layout

    g = np.random.default_rng([SHRUB_TAG, int(region_index)])
    cc = np.asarray([[c[0], c[1]] for c in covers], dtype=np.float64)
    cr = np.asarray([c[2] for c in covers], dtype=np.float64)
    out = obstacle_layout(g, float(size), cc, cr, dict(tree_per_ha=SHRUB_PER_HA, tree_r=list(SHRUB_R), rock_per_ha=0.0, rock_r=[0.25, 0.75], body_r=0.15))
    return [[float(x), float(y), float(r)] for x, y, r in out]


def apply_variant(c: dict, variant: dict, region: dict) -> None:
    f = c["v2"]["features"]
    if variant.get("shrubs"):
        size = float(c["rand"]["world_size"][0]) if "rand" in c else 60.0
        f["obstacles"]["fixed"] = list(f["obstacles"]["fixed"] or []) + shrub_discs(region["region_index"], size, region["covers"])
    for k, v in (variant.get("sets") or {}).items():
        blk, key = k.split(".", 1)
        f[blk][key] = v


# --------------------------------------------------------------------- #
# 명령
# --------------------------------------------------------------------- #


def cmd_reference(a) -> int:
    snap = load_snapshot(a.snapshot)
    d = scalar_fields(snap)
    d["made_from"] = dict(file=Path(a.snapshot).name, session_seed=snap["session_seed"], map=snap.get("map"),
                          note="기본 게임 설정(통합 v3 기본값 — configs/v3_wild3_mirror.yaml 가 맞춘 값, 10-18 results/v3/wild3/verify)")
    REFERENCE.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"-> {REFERENCE} (설정 {len(d['settings'])} 칸, 지역 세계 칸 {len(next(iter(d['world'].values())))} 개)")
    return 0


def cmd_convert(a) -> int:
    t0 = time.perf_counter()
    snap = load_snapshot(a.snapshot)
    ref = json.loads(REFERENCE.read_text(encoding="utf-8")) if REFERENCE.exists() else None
    d = run_dir(a.run)
    d.mkdir(parents=True, exist_ok=True)
    try:
        out = convert(snap, ref)
    except Refused as e:
        (d / "convert.json").write_text(json.dumps(dict(refused=str(e), snapshot=str(a.snapshot)), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"거부: {e}")
        return 2
    (d / "snapshot.json").write_text(Path(a.snapshot).read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    head = (f"# 적응 고리 {a.run} — 자동 생성 (results/v3/adapt/adapt.py convert, 손으로 고치지 않는다).\n"
            f"# 스냅숏 {Path(a.snapshot).name}: 지도 {snap.get('map')} 세션 {snap['session_seed']} 전역 스텝 {snap['global_step']}, 두뇌 {snap['brain']['id']}\n")
    write_yaml(d / "world.yaml", out["world"], head + "# 판정 세계 (부활 없음) = configs/v3_wild3_mirror.yaml + convert.json 'changed'. 지역마다 날씨·원판·먹이 지도는 regions.json\n")
    write_yaml(d / "train.yaml", out["train"], head + "# 학습 세계 = world.yaml + R4 학습 바꿈(학습 전용 40 m 밖 부활·학습 시드 32000~32049·train 블록 + 지역 섞기)\n")
    (d / "regions.json").write_text(json.dumps(out["regions"], ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    rec = dict(out["record"], wall_s=round(time.perf_counter() - t0, 2))
    (d / "convert.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"변환 끝 ({rec['wall_s']}초): 지역 {rec['regions']}, 사슴 {rec['N']}, 시작 두뇌 {rec['anchor']}, 바탕과 다른 칸 {len(rec['changed'])}")
    for c in rec["changed"]:
        print(f"  바뀜 {c['key']}: {c['template']} → {c['snapshot']}")
    for c in rec["checks"]:
        print(f"  확인 {c}")
    for n, r in out["regions"].items():
        print(f"  {n}: 날씨 {r['weather']}, 원판 {len(r['discs'])} (레벨 나무 {r['level_trees']}), 먹이 용량 합 {r['cap_total']:.2f} "
              f"(파이썬 시드 {GATE['check_seeds'][0]} 지도 {r['python_cap_total']:.2f}), 지금 먹이 {r['food_total']:.2f}, 사슴 입양 {r['deer']['adopted']} "
              f"잡힘 {r['deer']['caught']} 굶음 {r['deer']['starved']} (t {r['t']})")
    return 0


def check_eval(info: dict, seeds, workers: int) -> dict:
    """재현 확인의 셈(cmd_check, 실시간 고리 live.py 가 함께 쓴다): 시작 두뇌로 판정 세계(world.yaml)를 스냅숏 시각까지 시드 × 지역 돌려 언리얼의
    잡힘·굶음·산 수와 견준다. 규칙은 GATE.md 변경 기록 (1). 스냅숏 시각이 0 이면 ok=None."""
    t0 = time.perf_counter()
    steps = int(info["record"]["snapshot"]["global_step"])
    if steps <= 0:
        out = dict(ok=None, why="t = 0")
    else:
        model = ROOT / info["record"]["anchor"]
        seeds = [int(s) for s in seeds]
        jobs = make_jobs(info, model, seeds, steps, diag=False)
        res = run_jobs(_world_short, jobs, workers)
        rows, ok, ok_v0 = {}, True, True
        tot_py = {k: np.zeros(len(seeds)) for k in ("caught", "starved", "alive")}
        tot_ue = {k: 0.0 for k in tot_py}
        for name, r in info["regions"].items():
            sub = {x["seed"]: x for x in res if x["region"] == name}
            row = {}
            for key in ("caught", "starved", "alive"):
                v = np.asarray([sub[s][key] for s in seeds], dtype=np.float64)
                tot_py[key] += v
                u = float(r["deer"][key])
                tot_ue[key] += u
                m, sd = float(v.mean()), float(v.std(ddof=1))
                z = (u - m) / max(sd, 0.5)
                tol = max(GATE["check_z"] * sd, GATE["check_abs"])
                row[key] = dict(unreal=u, python_mean=m, python_sd=sd, python_min=float(v.min()), python_max=float(v.max()), z=z, tol=tol,
                                ok=bool(abs(u - m) <= tol), ok_v0=bool(abs(z) <= GATE["check_z"]))
                ok &= row[key]["ok"]
                ok_v0 &= row[key]["ok_v0"]
            rows[name] = row
        pooled = {}
        for key, v in tot_py.items():
            z = (tot_ue[key] - float(v.mean())) / max(float(v.std(ddof=1)), 0.5)
            pooled[key] = dict(unreal=tot_ue[key], python_mean=float(v.mean()), python_sd=float(v.std(ddof=1)), z=z, ok=bool(abs(z) <= GATE["check_z"]))
            ok &= pooled[key]["ok"]
        out = dict(ok=ok, steps=steps, seeds=[seeds[0], seeds[-1]], regions=rows, pooled=pooled,
                   rule=f"지역 합 잡힘·굶음·산 |z| ≤ {GATE['check_z']} (sd 바닥 0.5) 그리고 지역마다 |언리얼 − 파이썬 평균| ≤ max({GATE['check_z']}·sd, "
                        f"{GATE['check_abs']} 마리) — GATE.md 변경 기록 (1)",
                   ok_v0=ok_v0, rule_v0=f"(첫 초안 — 쓰지 않음) 지역마다 |z| ≤ {GATE['check_z']} (sd 바닥 0.5)")
    out["wall_s"] = round(time.perf_counter() - t0, 1)
    return out


def cmd_check(a) -> int:
    info = load_run(a.run)
    if int(info["record"]["snapshot"]["global_step"]) <= 0:
        print("스냅숏 시각이 0 — 견줄 결과가 없다(재현 확인 건너뜀, 통과로 두지 않는다)")
    out = check_eval(info, seed_list(GATE["check_seeds"]), a.workers)
    (info["dir"] / "check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    if out.get("regions"):
        for n, row in list(out["regions"].items()) + [("지역 합", out["pooled"])]:
            print(f"  {n}: " + " · ".join(f"{k} 언리얼 {v['unreal']:.0f} 파이썬 {v['python_mean']:.1f}±{v['python_sd']:.1f} (z {v['z']:+.2f}"
                                          + (f", 범위 {v['python_min']:.0f}~{v['python_max']:.0f}" if "python_min" in v else "") + f") {'예' if v['ok'] else '아니오'}"
                                          for k, v in row.items()))
        print(f"  (첫 초안 규칙 — 지역마다 |z| ≤ 3: {'통과' if out['ok_v0'] else '실패'}, 쓰지 않음)")
    print(f"재현 확인 {'통과' if out['ok'] else ('건너뜀' if out['ok'] is None else '실패 — 변환부터 고친다(학습하지 않는다)')} ({out['wall_s']}초)")
    return 0 if out["ok"] else 1


def train_cmdline(info: dict, seed: int, steps: int, control: bool) -> tuple[list[str], Path, Path]:
    run = info["dir"].name
    tag = "k2b" if control else "cand"
    name = f"adapt_{run}_{tag}_s{seed}_{steps // 1_000_000}m" if steps % 1_000_000 == 0 else f"adapt_{run}_{tag}_s{seed}_{steps}"
    out = CKPT / run / f"{name}.zip"
    log = info["dir"] / "logs" / f"train_{tag}_s{seed}.log"
    anchor = ROOT / info["record"]["anchor"]
    cfg = K2B_CONFIG if control else info["dir"] / "world.yaml".replace("world", "train")
    src = (f"적응 고리 {run}: 스냅숏 지금 두뇌 {info['record']['snapshot']['brain']} — "
           + ("K2-B 대조(원래 학습 세계 v3_r1, 같은 양)" if control else "스냅숏 세계(train.yaml)"))
    args = ["--config", str(cfg), "--seed", str(seed), "--steps", str(steps), "--init-from-model", str(anchor), "--init-source", src,
            "--run-name", name, "--out", str(out), "--tb", str(ROOT / "runs" / "v3_adapt"), "--threads", "1",
            "--ppo-config", str(ROOT / "configs" / "ppo_best.yaml")]
    return args, out, log


def cmd_train(a) -> int:
    info = load_run(a.run)
    (info["dir"] / "logs").mkdir(exist_ok=True)
    t0 = time.perf_counter()
    procs = []
    for s in a.model_seeds:
        args, out, log = train_cmdline(info, int(s), int(a.steps), a.control)
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(HERE), "train-one", "--run", a.run, "--train-food", "random" if a.control else a.train_food, "--"] + args
        env = dict(os.environ, PYTHONUTF8="1")
        fh = open(log, "w", encoding="utf-8")
        procs.append((s, out, log, fh, subprocess.Popen(cmd, cwd=str(ROOT), stdout=fh, stderr=subprocess.STDOUT, env=env)))
        print(f"학습 시작: 모델 시드 {s} → {out.relative_to(ROOT).as_posix()} (기록 {log.relative_to(ROOT).as_posix()})", flush=True)
    rows = []
    for s, out, log, fh, p in procs:
        rc = p.wait()
        fh.close()
        rows.append(dict(seed=int(s), rc=rc, model=_rel(out), log=_rel(log), ok=rc == 0 and out.exists()))
    rec = dict(control=bool(a.control), steps=int(a.steps), train_food="random" if a.control else a.train_food, runs=rows,
               wall_s=round(time.perf_counter() - t0, 1))
    name = "train_k2b.json" if a.control else "train.json"
    (info["dir"] / name).write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"학습 끝 ({rec['wall_s']}초): " + ", ".join(f"s{r['seed']} {'성공' if r['ok'] else '실패 rc ' + str(r['rc'])}" for r in rows))
    return 0 if all(r["ok"] for r in rows) else 1


def cmd_train_one(a) -> int:
    """학습 프로세스 하나 (train 이 띄운다): train_v3.main 을 그대로 부르고, --train-food snapshot 이면 학습 세계를 만들 때마다 그 지역 스냅숏 지도를 덮는다."""
    import train_v3

    info = load_run(a.run)
    if a.train_food == "snapshot":
        food = {n: r["cap"] for n, r in info["regions"].items()}
        train_v3.MultiWorldVecEnv = snapshot_food_vec_env(train_v3.MultiWorldVecEnv, food)
        print(f"학습 먹이 지도: 스냅숏 ({', '.join(food)})", flush=True)
    else:
        print("학습 먹이 지도: 파이썬 난수 지도 (시드마다)", flush=True)
    return int(train_v3.main(a.rest) or 0)


def trained(info: dict, control: bool = False) -> list[dict]:
    p = info["dir"] / ("train_k2b.json" if control else "train.json")
    if not p.exists():
        raise SystemExit(f"{p.name} 가 없다 — train{' --control' if control else ''} 부터")
    return [r for r in json.loads(p.read_text(encoding="utf-8"))["runs"] if r["ok"]]


def cmd_eval(a) -> int:
    info = load_run(a.run)
    if a.brain == "current":
        model = ROOT / info["record"]["anchor"]
    elif a.brain == "candidate":
        sel = info["dir"] / "select.json"
        if not sel.exists():
            raise SystemExit("select.json 이 없다 — select 부터")
        model = ROOT / json.loads(sel.read_text(encoding="utf-8"))["chosen"]
    elif a.brain == "k2b":
        rows = trained(info, control=True)
        model = ROOT / rows[0]["model"]
    else:
        model = Path(a.brain)
    res = eval_brain(info, model, seed_list(GATE["judge_seeds"]), GATE["judge_steps"], a.workers)
    out = info["dir"] / f"eval_{a.brain if a.brain in ('current', 'candidate', 'k2b') else Path(a.brain).stem}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    import r4_eval as re_

    p = re_.pooled(res)
    print(f"판정 판 {a.brain}: 세계 {p['worlds']} {res['meta']['wall_s']:.0f}초 · 잡힘 {p['caught']:.4f} 굶음 {p['starved']:.4f} 산 {p['alive']:.4f} "
          f"은신처 안 {p['shelter']:.4f} 숨기 {p['beh']['hide']:.4f} 은신처 안 잡힘 {p['catch_cover']} -> {out.name}")
    return 0


def cmd_select(a) -> int:
    import r4_eval as re_

    info = load_run(a.run)
    t0 = time.perf_counter()
    rows = []
    for r in trained(info):
        res = eval_brain(info, ROOT / r["model"], seed_list(GATE["select_seeds"]), GATE["select_steps"], a.workers)
        (info["dir"] / f"select_s{r['seed']}.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        p = re_.pooled(res)
        rows.append(dict(seed=r["seed"], model=r["model"], caught=p["caught"], starved=p["starved"], alive=p["alive"], hide=p["beh"]["hide"]))
        print(f"  고르기 s{r['seed']}: 잡힘 {p['caught']:.4f} 굶음 {p['starved']:.4f} 산 {p['alive']:.4f} 숨기 {p['beh']['hide']:.4f}", flush=True)
    if not rows:
        raise SystemExit("학습에 성공한 후보가 없다")
    rows.sort(key=lambda x: (x["caught"], x["starved"], x["seed"]))
    out = dict(chosen=rows[0]["model"], rule="고르기 세계 16분 잡힌 몫 최저 → 굶은 몫 → 시드 번호", rows=rows, wall_s=round(time.perf_counter() - t0, 1))
    (info["dir"] / "select.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"고른 후보: {out['chosen']} ({out['wall_s']}초)")
    return 0


def cmd_stuck(a) -> int:
    import stuck_check

    info = load_run(a.run)
    t0 = time.perf_counter()
    sel = json.loads((info["dir"] / "select.json").read_text(encoding="utf-8"))
    out = {}
    for tag, model in (("current", ROOT / info["record"]["anchor"]), ("candidate", ROOT / sel["chosen"])):
        jobs = make_jobs(info, model, seed_list(GATE["stuck_seeds"]), GATE["stuck_steps"], diag=False)
        for j in jobs:
            for k in ("log_every", "diag"):
                j.pop(k, None)
        res = run_jobs(_stuck_one, jobs, a.workers)
        s = stuck_check.summarize(res)
        out[tag] = dict(summary={k: v for k, v in s.items() if not k.startswith("worst")}, model=_rel(model))
        (info["dir"] / f"stuck_{tag}.json").write_text(json.dumps(dict(summary=s, model=_rel(model)), ensure_ascii=False, indent=1, default=str) + "\n",
                                                        encoding="utf-8", newline="\n")
        print(f"  끼임 {tag}: 사슴 {s['deer_stuck']} · 늑대 원판 {s['wolf_stuck']} · 늑대 은신처 둘레 {s['wolf_wall_stuck']} (세계 {s['worlds']})", flush=True)
    print(f"끼임 세기 끝 ({time.perf_counter() - t0:.0f}초)")
    return 0


def cmd_gate(a) -> int:
    info = load_run(a.run)
    d = info["dir"]

    def opt(name):
        p = d / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    cur, cand = opt("eval_current.json"), opt("eval_candidate.json")
    if cur is None or cand is None:
        raise SystemExit("eval_current.json·eval_candidate.json 이 있어야 한다")
    chk = opt("check.json")
    g = gate_eval(cur, cand, opt("stuck_current.json"), opt("stuck_candidate.json"), opt("eval_k2b.json"))
    if chk is not None and chk.get("ok") is False:
        g.update(verdict="기각", passed=False, why="재현 확인 실패 — " + g["why"])
    g["candidate"] = cand["meta"]["model"]
    g["current"] = cur["meta"]["model"]
    (d / "gate.json").write_text(json.dumps(g, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    text = fmt_gate(g)
    (d / "gate.md").write_text(f"# 관문 {a.run}\n\n후보 `{g['candidate']}` 대 지금 두뇌 `{g['current']}` (규칙 GATE.md)\n\n{text}\n", encoding="utf-8", newline="\n")
    print(text)
    return 0 if g["passed"] else 1


def cmd_export(a) -> int:
    import export_weights_v3 as ex

    info = load_run(a.run)
    gp = info["dir"] / "gate.json"
    g = json.loads(gp.read_text(encoding="utf-8")) if gp.exists() else None
    if g is None or not g.get("passed"):
        why = "관문 판정이 없다" if g is None else f"관문 {g['verdict']}: {g['why']}"
        rec = dict(exported=False, why=why, time=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        (info["dir"] / "export.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"내보내지 않는다 — {why}. 게임 두뇌는 그대로 ({info['record']['snapshot']['brain']}).")
        return 1
    model = ROOT / g["candidate"]
    out = (Path(a.out) if a.out else SAVED_BRAINS / f"{model.stem}.json")
    d = ex.export_brain_file(model, out, world_label=f"적응 고리 {a.run} (스냅숏 세계)")
    v = verify_brain_file(out)
    rec = dict(exported=v["ok"], file=_rel(out), id=d["id"], verify=v, load=f"eco.V3Brain.Load {out.stem}",
               time=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    (info["dir"] / "export.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"두뇌 파일 {out} ({d['id']}) — 다시 읽기 {'통과' if v['ok'] else '실패'} (골든 {v['golden']} 최대 오차 {v['max_logit_err']:.2e}). 언리얼: {rec['load']}")
    return 0 if v["ok"] else 1


def cmd_all(a) -> int:
    """1~9 한 번에. 지금 두뇌 판정 판은 학습과 겹쳐 돈다(계획 3.1). 단계마다 걸린 시간을 loop.json 에 적는다."""
    times = {}
    d = run_dir(a.run)

    def step(name, fn, ns):
        t0 = time.perf_counter()
        rc = fn(ns)
        times[name] = round(time.perf_counter() - t0, 1)
        print(f"== {name}: {times[name]}초 (rc {rc})", flush=True)
        (d / "loop.json").write_text(json.dumps(dict(steps=times, args=vars(a) | {"snapshot": str(a.snapshot) if a.snapshot else None}), ensure_ascii=False, indent=1, default=str) + "\n",
                                     encoding="utf-8", newline="\n")
        return rc

    base = dict(run=a.run, workers=a.workers)
    if a.snapshot is None:
        # 가정 세계 고리(derive 로 만든 폴더): 스냅숏이 없어 1·2 를 건너뛴다
        info = load_run(a.run)
        if "derived_from" not in info["record"]:
            raise SystemExit("--snapshot 이 없으면 derive 로 만든 고리만 받는다")
        print(f"가정 세계 고리 {a.run} (변형 {info['record']['variant']['name']}) — 변환·재현 확인 없음", flush=True)
    else:
        if step("1_convert", cmd_convert, argparse.Namespace(snapshot=a.snapshot, run=a.run)) != 0:
            return 2
        if step("2_check", cmd_check, argparse.Namespace(**base)) != 0:
            print("재현 확인 실패 — 학습하지 않는다")
            return 1
    # 3 학습 ‖ 4 지금 두뇌 판정 판 (학습 프로세스 수만큼 워커를 덜 쓴다)
    import threading

    tr_ns = argparse.Namespace(run=a.run, steps=a.steps, model_seeds=a.model_seeds, control=False, train_food=a.train_food)
    result = {}

    def _train():
        t0 = time.perf_counter()
        result["rc"] = cmd_train(tr_ns)
        result["s"] = round(time.perf_counter() - t0, 1)

    th_ = threading.Thread(target=_train)
    th_.start()
    step("4_eval_current", cmd_eval, argparse.Namespace(**base | {"workers": max(1, a.workers - len(a.model_seeds))}, brain="current"))
    th_.join()
    times["3_train"] = result["s"]
    if result["rc"] != 0:
        return 1
    step("5_select", cmd_select, argparse.Namespace(**base))
    step("6_eval_candidate", cmd_eval, argparse.Namespace(**base, brain="candidate"))
    step("7_stuck", cmd_stuck, argparse.Namespace(**base))
    rc = step("8_gate", cmd_gate, argparse.Namespace(run=a.run))
    g = json.loads((d / "gate.json").read_text(encoding="utf-8"))
    if g["verdict"] == "보류" and "K2-B" in g["why"]:
        sel = json.loads((d / "select.json").read_text(encoding="utf-8"))
        chosen_seed = next(r["seed"] for r in sel["rows"] if r["model"] == sel["chosen"])      # K2-B = 고른 후보와 같은 모델 시드
        step("8b_train_k2b", cmd_train, argparse.Namespace(run=a.run, steps=a.steps, model_seeds=[chosen_seed], control=True, train_food="random"))
        step("8c_eval_k2b", cmd_eval, argparse.Namespace(**base, brain="k2b"))
        rc = step("8d_gate", cmd_gate, argparse.Namespace(run=a.run))
    step("9_export", cmd_export, argparse.Namespace(run=a.run, out=None))
    total = sum(v for k, v in times.items() if k != "3_train")
    print(f"고리 끝: 단계 {times} — 벽시계 합 약 {total / 60:.1f}분 (학습은 지금 두뇌 판정과 겹침)")
    return rc


def cmd_sense(a) -> int:
    """민감도: 가정 세계마다 R1b-F(지금 두뇌) 대 R4(늑대를 알면 숨기를 4배 쓰는 두뇌)의 16분 잡힘·굶음·산 짝 차이 (시드 32080~32099 × 지역)."""
    import r4_eval as re_

    info = load_run(a.run)
    vs = variants()
    names = a.variants or list(vs)
    out_path = info["dir"] / "sense.json"
    out = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    seeds = seed_list(SENSE_SEEDS)
    for vn in names:
        v = vs[vn]
        runs = {}
        for tag, model in (("r1bf", ROOT / info["record"]["anchor"]), ("r4", R4)):
            res = eval_brain(info, model, seeds, GATE["judge_steps"], a.workers, variant=v)
            (info["dir"] / f"sense_{vn}_{tag}.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            runs[tag] = res
        row = dict(variant=v, seeds=list(SENSE_SEEDS), wall_s=sum(r["meta"]["wall_s"] for r in runs.values()))
        for key in ("caught", "starved", "alive", "shelter"):
            row[key] = re_.paired(re_.per_seed(runs["r4"], key), re_.per_seed(runs["r1bf"], key))
        row["pooled"] = {t: re_.pooled(r) for t, r in runs.items()}
        out[vn] = row
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
        pr, pb = row["pooled"]["r4"], row["pooled"]["r1bf"]
        print(f"[{vn}] 잡힘 R4 {pr['caught']:.4f} 대 R1b-F {pb['caught']:.4f} (차 {row['caught']['diff']:+.4f}, t {row['caught']['t']:+.2f}) · "
              f"굶음 {pr['starved']:.4f}/{pb['starved']:.4f} (t {row['starved']['t']:+.2f}) · 산 {pr['alive']:.4f}/{pb['alive']:.4f} · "
              f"사냥 성공률 {pr['hunt_success']:.3f}/{pb['hunt_success']:.3f} · 숨기 {pr['beh']['hide']:.3f}/{pb['beh']['hide']:.3f} ({row['wall_s']:.0f}초)",
              flush=True)
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "train-one":
        ap1 = argparse.ArgumentParser()
        ap1.add_argument("cmd")
        ap1.add_argument("--run", required=True)
        ap1.add_argument("--train-food", choices=("snapshot", "random"), default="snapshot")
        cut = argv.index("--")
        a1 = ap1.parse_args(argv[:cut])
        a1.rest = argv[cut + 1:]
        return cmd_train_one(a1)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("reference")
    s.add_argument("--snapshot", type=Path, required=True)
    s = sub.add_parser("convert")
    s.add_argument("--snapshot", type=Path, required=True)
    s.add_argument("--run", required=True)
    for name in ("check", "select", "stuck"):
        s = sub.add_parser(name)
        s.add_argument("--run", required=True)
        s.add_argument("--workers", type=int, default=16)
    s = sub.add_parser("train")
    s.add_argument("--run", required=True)
    s.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    s.add_argument("--model-seeds", type=int, nargs="+", default=[0, 1])
    s.add_argument("--control", action="store_true", help="K2-B 대조: 지금 두뇌를 원래 학습 세계(configs/v3_r1.yaml)에서 같은 양 더 배운다")
    s.add_argument("--train-food", choices=("snapshot", "random"), default="snapshot")
    s = sub.add_parser("eval")
    s.add_argument("--run", required=True)
    s.add_argument("--brain", required=True, help="current · candidate · k2b · 모델 .zip 경로")
    s.add_argument("--workers", type=int, default=16)
    s = sub.add_parser("gate")
    s.add_argument("--run", required=True)
    s = sub.add_parser("export")
    s.add_argument("--run", required=True)
    s.add_argument("--out", default=None)
    s = sub.add_parser("all")
    s.add_argument("--snapshot", type=Path, default=None, help="없으면 derive 로 만든 가정 세계 고리 (1·2 건너뜀)")
    s.add_argument("--run", required=True)
    s.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    s.add_argument("--model-seeds", type=int, nargs="+", default=[0, 1])
    s.add_argument("--train-food", choices=("snapshot", "random"), default="snapshot")
    s.add_argument("--workers", type=int, default=16)
    s = sub.add_parser("sense")
    s.add_argument("--run", required=True)
    s.add_argument("--variants", nargs="+", default=None, choices=list(variants()))
    s.add_argument("--workers", type=int, default=16)
    s = sub.add_parser("derive")
    s.add_argument("--run", required=True)
    s.add_argument("--variant", required=True, choices=[k for k in variants() if k != "base"])
    s.add_argument("--to", required=True)
    a = ap.parse_args(argv)
    return {"reference": cmd_reference, "convert": cmd_convert, "check": cmd_check, "train": cmd_train, "eval": cmd_eval, "select": cmd_select,
            "stuck": cmd_stuck, "gate": cmd_gate, "export": cmd_export, "all": cmd_all, "sense": cmd_sense, "derive": cmd_derive}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

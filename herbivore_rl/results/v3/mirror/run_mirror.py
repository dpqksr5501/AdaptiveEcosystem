"""언리얼 통합 v3 모드 거울 실행기 (10-15 사용자 '언리얼에서 돌리는 게 파이썬에서 돌리는 것과 얼마나 비슷한지 확인').

    # herbivore_rl/ 에서
    python results/v3/mirror/run_mirror.py --deer 128 --seeds 32000-32089          # → results/v3/mirror/runs/d128_e38_s32000-32089.json·.csv
    python results/v3/mirror/run_mirror.py --deer 64 --wolf-eat-steps 225 --seeds 33000-33089
    python results/v3/mirror/run_mirror.py --deer 128 --unreal-maps 20000-20002 --replicates 10 --seeds 32000-32089   # 같은 지도 짝 비교
    python results/v3/mirror/compare_unreal.py --unreal-dir <언리얼 기록 폴더>       # 언리얼 기록과 나란히 보기

세계 하나 = 언리얼 지역 무대 하나(configs/v3_unreal_mirror.yaml — 머리 주석에 무엇을 흉내 내고 무엇을 못 닫았는지 적었다). 시드마다 독립 세계를
1800스텝(240초) 돌린다. 두뇌는 R1b(ckpt/v3/v3_r1_g995_s3_20m.zip)를 배포 모드(마스크 argmax, env_v2/rollout.py RepLearned)로 쓴다 — 허용 = 모델
목록 ∩ 세계 목록이라 얼기가 막힌다. 언리얼 한 세션은 지역 3개라 견주기 도구는 시드를 앞에서부터 3개씩 묶어 한 세션으로 본다(--seeds 순서).
시드는 탐색 범위 32000~32099·33000~33099 만 받는다(판정 시드를 쓰지 않는다).

짝 비교(--unreal-maps, 선택): 언리얼 기록의 지역 무대와 같은 먹이 지도를 쓴다. 굶음은 먹이 지도 운이 크게 정하는데(언리얼 128마리에서 무너진
두 지역이 가장 가난한 두 지도다) 파이썬과 C++ 는 난수열이 달라 지도가 다르므로, C++ 세계 난수의 첫 Gw² 개(EcoWorldV3.h InitWorld →
FFoodGrid::Build 의 Noise — State = HashChain3(W3RG, 세션 시드, RngStream), NextU01 = (Mix64(State += 황금비 상수) >> 11) × 2^−53, 행 우선)를
옮겨 와 같은 블러·정규화·문턱으로 용량을 다시 만든다(세계 생성 뒤 food_cap·food 를 덮고 관측을 다시 만든다 — 실행기 쪽 덮기이고 세계 규칙이
아니다). 지역 → RngStream = 지역 번호 + 1(통합 레벨 로그 '지역 무대 <이름> (지역 번호 k)': Barren 0, Forest 1, Highland 2). 세션 시드는 언리얼
기록의 시드(보정 20000~20019 — 같은 지도를 만들 때만 쓴다)이고, 지도마다 파이썬 세계 --replicates 개를 서로 다른 탐색 시드로 돌린다. 나머지
(시작 자리 계획 난수·늑대 배회 선회·결정·밤잠 지연 키)는 옮기지 않는다 — 파이썬 난수다.

10초(75스텝)마다 한 줄. 정의는 언리얼 기록 줄 '[EcoV3I] <지역> | <t>초 ...'(EcoPolicyV3IntegratedSubsystem.cpp LogContext,
EcoPolicyV3IntegratedProcessors.cpp TallyEnergy)와 같다:
  t_s        = t × 8/60 초(t = 이 스텝이 끝난 뒤의 세계 t, 언리얼 Sim.T). 줄은 t 가 75 의 배수인 스텝 끝에 쓴다(Sim.T − LastLogT ≥ 75)
  alive      = 그 스텝 첫머리의 산 사슴(언리얼 '사슴 산' = 지난 프레임 끝 Ctx.AliveDeer — 그 스텝의 죽음만큼 늦다), alive_end = 스텝 끝 산 사슴
  n          = 처음 놓은 사슴 수(언리얼 AdoptedDeer)
  caught     = 누적 포획(언리얼 Stats.Caught — 잡힌 사슴 수), starved = 누적 굶음(언리얼 Stats.Starved — 잡히지 않고 E ≤ 0 이 된 사슴 수)
  food_pct   = 100 × 지금 먹이 합 ÷ 처음 합(= 셀 용량 합, 언리얼 '무대 먹이 처음의 %')
  energy_pct = 100 × 스텝 끝 산 사슴의 에너지(0~1 로 자름) 평균(없으면 0), hungry = 그중 에너지 < 0.15(언리얼 kStarvingEnergy)
  dark       = 스텝 끝 어둠 d, wolves_asleep = 자는 늑대 수(기록 전용)
출력: results/v3/mirror/runs/<이름>.json(세계마다 메타 + 줄)과 .csv(줄만). 같은 인자면 같은 결과다(벽시계 열 wall_s 만 다르다).

야생 1단계(10-15, results/v3/wild1/README.md): --config 로 다른 거울 설정(configs/v3_wild1_mirror.yaml)을, --disable 로 그 설정의 기능 블록 몇 개를 끈
판(규칙 하나씩 빼 보기)을 돌린다. --diag 를 주면 세계마다 meta['diag'] 에 진단을 더 적는다(동역학과 무관 — 기하에 사슴 × 늑대 보임 행렬을 남기는
World.keep_pair_vis 만 켠다): 행동별 산 사슴-스텝, 늑대 거리 구간(<5·5~10·10~15·15~30 m)별 깨어 있는 늑대 쌍과 그중 알아챈 쌍, 잡힘마다 그 스텝 행동·
마지막 5초(38스텝) 안에 도망쳤나·알아챘나, 굶음마다 마지막 5초 안에 도망쳤나, 늑대 수·하루 길이, 켠 규칙의 World.wild_stats().
10-16 더함(가장자리·은신처 진단, results/v3/wild1/README.md '가장자리·은신처 고침'): 잡힘 가운데 무대 가장자리 5 m(2.5 단위) 띠·모서리(두 벽
모두 10 m = 5 단위 안)·은신처 원 안에서 잡힌 수, 같은 늑대가 자기 지난 포획 자리 20 m(10 단위) 안에서 다시 잡은 수(잡은 늑대 = 이번 스텝에 쿨다운이
pred_eat_cd 로 막 찬 늑대 가운데 가장 가까운 늑대), 산 사슴-스텝 가운데 그 띠·모서리에 있던 수(자리 몫 기준), 도주가 풀린 수와 그 가운데
은신처 밖이고 깨어 있는 늑대가 실거리 wild_flight.safe_r 안에 남아 있던 수(스텝 끝 위치 — 덮기를 정한 기하와 같다).
10-17 더함(늑대 몸 여유, results/v3/wild1/README.md '늑대 몸 여유'): --wolf-margin 으로 설정의 realism_shelter.wolf_margin(단위)을 덮는다(설정에
realism_shelter.block_predators 가 켜져 있어야 한다). 진단에 은신처 둘레 밖 2 m(1 단위)·4 m(2 단위) 띠에서 잡힌 수(사슴이 원 밖이고 가장 가까운
둘레까지 그 거리 안), 늑대-스텝 가운데 늑대 중심이 원 안(|q − c| < r)·둘레 밖 1 m 안(|q − c| < r + 0.5)에 있던 수, 늑대 중심과 가장 가까운 둘레의
가장 작은 거리(단위, 원 안이면 음수)를 더 적는다(스텝 끝 위치, 플레이어형 위협 없음 — 거울 세계는 늑대뿐이다).
10-17 더함(야생 2단계, results/v3/wild2/README.md): 줄마다 누적 사냥 hunt_starts·hunt_ends·hunt_success(World.hunt_stats — 정의는 env_v2/world.py
모듈 docstring '야생 2단계', 언리얼 '[EcoV3I] <지역> 사냥·은신처 |' 줄과 같다)와 누적 shelter_steps(스텝 첫머리에 산 사슴 가운데 이동 뒤 위치가 은신처
원 안인 사슴-스텝)·live_steps(스텝 첫머리 산 사슴-스텝)를 더하고, 세계 메타에 hunt(마지막 hunt_stats)·shelter_steps·live_steps 를 적는다(동역학과 무관).
짝 비교 지도를 덮을 때 은신처 먹이 부족(realism_cover_food)을 켠 세계는 새 지도의 은신처 셀 용량에도 배수를 다시 건다(C++ FFoodGrid::Build 순서).
10-17 더함(야생 2단계 2 늑대 무리, configs/v3_wild2_pack_mirror.yaml): wild_pack 을 켠 세계는 메타에 pack(World.pack_stats — 앞장·도움·기다림·은신처 문
늑대-스텝, 늑대 포획과 협동 포획)을 적고, 10초 줄(JSON 만 — CSV 열은 그대로)에 같은 칸의 누적 pack_*을 더한다(동역학과 무관). 늑대 수는 설정의
rand.predator_count 다(메타 wolves).
10-17 더함(장애물 돌아가기, obstacles.detour): 돌아가기를 켠 세계는 10초 줄(JSON 만)에 누적 det_*(World.obstacle_stats()['detour'] — 방향을 바꾼·시작한·
빈 방향을 못 찾은 사슴·늑대-스텝, 돕기 그만둠)를 더한다(동역학과 무관). --set 블록.키=값(여러 번)으로 기능 블록 계수를 덮는다(예: obstacles.detour=false —
돌아가기를 넣기 전 판과 비트 동일, 메타 set).
10-17 더함(야생 2단계 3 세로 장애물, configs/v3_wild2_obstacle_mirror.yaml): obstacles 를 켠 세계는 메타에 obstacles(World.obstacle_stats — 원판 수·넓이,
사슴·늑대 미끄러짐·물러남·돌아섬, 눈길 가림 몫)를 적고 10초 줄(JSON 만)에 같은 칸의 누적 ob_* 를 더한다. 짝 비교 지도를 덮을 때 원판 밑 먹이 줄임(ob_food_factor)을 은신처 먹이 부족보다 먼저 다시 건다
(C++ FFoodGrid::Build 순서). --unreal-obstacles <파일 또는 폴더>(짝 비교에만): 언리얼 장애물 JSON(EcoPolicyV3IntegratedSubsystem ExportObstacles 꼴 —
지역마다 원판 x, y, r)의 지역 원판을 그 지도 세계의 obstacles.fixed 로 넣는다. 폴더면 세션마다 s<세션 시드>.json 을 읽는다.
10-18 더함(야생 3단계 지역 날씨, configs/v3_wild3_mirror.yaml): wild_weather 를 켠 설정의 짝 비교는 지도마다 wild_weather.region 을 그 지도의 지역으로 덮는다(날씨는
설정의 regions 표). 짝 비교가 아니면 설정의 region 그대로다(--set wild_weather.region=Highland 로 바꾼다). 세계 메타에 weather(World.weather_stats)를, realism_hearing 을
켠 세계는 heard_only_frac(위협을 들어서만 안 개체-스텝 몫, World.realism_stats)을 더 적는다(동역학과 무관).
10-18 더함(R4 사전 등록 results/v3/r4/PREREG.md): --model 로 두뇌 모델을 바꾼다(기본 R1b s3 그대로 — 메타 model 에 파일 이름).
10-18 더함(언리얼 날씨 짝 비교, results/v3/wild3/compare_weather.py): --diag 진단에 heard_live·live_obs(스텝 끝 관측에서 들어서만 안 **산** 사슴·스텝과 산 사슴·스텝 —
C++ 통합 모드 10초 여덟째 줄 '들어서만 안 사슴·스텝' 과 같은 정의. heard_only_frac 은 죽은 슬롯까지 N 으로 나눈다)를 더한다(동역학과 무관).
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: F401,E402  ← torch 보다 먼저
import numpy as np  # noqa: E402

CONFIG = ROOT / "configs" / "v3_unreal_mirror.yaml"
MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"
OUT = HERE.parent / "runs"
STEPS = 1800                         # 240초 (언리얼 비교 실행과 같다)
LOG_EVERY = 75                       # 10초 (언리얼 LogEverySteps = 반올림(10 ÷ 8/60))
STEP_SECONDS = 8.0 / 60.0            # 언리얼 kStepSeconds
STARVING = 0.15                      # 언리얼 kStarvingEnergy
SEED_RANGES = ((32000, 32099), (33000, 33099), (33100, 33199))   # 탐색 범위만 (판정 시드는 쓰지 않는다). 33100~33199 = R5 판정(10-19, results/v3/r5/PREREG.md)
UNREAL_SEED_RANGE = (20000, 20019)                # 짝 비교의 언리얼 세션 시드(보정 범위 — 같은 지도를 만들 때만)
# 언리얼 지역 → C++ 세계 난수 갈래 RngStream = 지역 번호 + 1 (EcoPolicyV3IntegratedSubsystem.cpp MakeRegionWorldConfig, 로그의 지역 번호)
UNREAL_REGION_STREAM = {"Barren": 1, "Forest": 2, "Highland": 3}
WORLD_RNG_TAG = 0x57335247                        # "W3RG" (EcoWorldV3.h kWorldRngTag)
GOLDEN64 = 0x9E3779B97F4A7C15                     # SplitMix64 증분 (FRng::NextU64)
ROW_KEYS = ("t_s", "step", "alive", "alive_end", "n", "caught", "starved", "food_pct", "energy_pct", "hungry", "dark",
            "wolves_asleep", "hunt_starts", "hunt_ends", "hunt_success", "shelter_steps", "live_steps")


def parse_seeds(text: str) -> list[int]:
    """'32000-32003' · '32000,32005' · 섞어 쓰기 → 시드 목록(적은 순서, 겹치면 실패). 탐색 범위 밖이면 실패."""
    out: list[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = (int(x) for x in part.split("-", 1))
            if b < a:
                raise ValueError(f"시드 범위 {part} 의 끝이 앞보다 작다")
            out.extend(range(a, b + 1))
        else:
            out.append(int(part))
    if not out:
        raise ValueError("시드가 없다")
    if len(set(out)) != len(out):
        raise ValueError(f"시드가 겹친다: {text}")
    bad = [s for s in out if not any(lo <= s <= hi for lo, hi in SEED_RANGES)]
    if bad:
        raise ValueError(f"시드 {bad[:5]} 는 탐색 범위 {SEED_RANGES} 밖이다(판정 시드를 쓰지 않는다)")
    return out


def parse_unreal_maps(text: str) -> list[int]:
    """짝 비교의 언리얼 세션 시드 '20000-20002' → 목록. 보정 범위 20000~20019 밖이거나 겹치면 실패."""
    out: list[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if part:
            a, _, b = part.partition("-")
            out.extend(range(int(a), int(b or a) + 1))
    lo, hi = UNREAL_SEED_RANGE
    if not out or len(set(out)) != len(out) or any(not lo <= s <= hi for s in out):
        raise ValueError(f"언리얼 세션 시드 {text} 는 {lo}~{hi} 안의 겹치지 않는 시드여야 한다")
    return out


def cpp_food_noise(session_seed: int, stream: int, n: int) -> np.ndarray:
    """C++ 세계 난수의 첫 n 개 (FRng, State = HashChain3(W3RG, Seed, RngStream)): k 번째(1 부터) = (Mix64(H + k·황금비) >> 11) × 2^−53.
    HashChain3 는 repertoire.mix_chain 과 같은 사슬이다(결정 지연 골든이 맞춘다)."""
    from env_v2 import repertoire as rep

    h = rep.mix_chain(np.uint64(WORLD_RNG_TAG), np.uint64(session_seed), np.uint64(stream))
    with np.errstate(over="ignore"):
        st = h + np.uint64(GOLDEN64) * np.arange(1, n + 1, dtype=np.uint64)
    return (rep._mix64(st) >> np.uint64(11)).astype(np.float64) * (1.0 / 9007199254740992.0)


def apply_unreal_map(w, session_seed: int, region: str) -> None:
    """세계 w 의 먹이 용량·먹이를 언리얼 지역 무대의 지도로 덮고 관측을 다시 만든다(모듈 docstring '짝 비교'). 식은 `World._build_world` 그대로
    (블러 food_patch_blur, 최소·최대 정규화, 문턱 food_patch_threshold). 은신처 셀·재생률은 은신처만 정하므로 그대로다."""
    from env_v2.steering import EPS

    cfg, g = w.cfg, w.gw
    noise = cpp_food_noise(session_seed, UNREAL_REGION_STREAM[region], g * g).reshape(g, g)   # C++ 셀 k = y·Gw + x
    m = w._smooth(noise, int(cfg.food_patch_blur))
    m = (m - m.min()) / max(m.max() - m.min(), EPS)
    t = float(cfg.food_patch_threshold)
    w.food_cap = np.clip((m - t) / (1.0 - t), 0.0, 1.0)
    if getattr(w, "_ob", None) is not None and w._ob["no_food"]:
        # 야생 2단계 3(세로 장애물): 원판 밑 먹이 줄임을 새 지도에 다시 건다(C++ FFoodGrid::Build 가 은신처 먹이 부족보다 먼저 거는 순서와 같다)
        w.food_cap = w.food_cap * w.ob_food_factor
    if getattr(w, "_zf", None) is not None:
        # 야생 2단계(은신처 먹이 부족, realism_cover_food): 새 지도에도 은신처 셀 용량 배수를 다시 건다(C++ FFoodGrid::Build 가 지도를 만든 뒤
        # 거는 순서와 같다). 재생률은 은신처만 정하므로 reset 때 값 그대로다
        w.food_cap = np.where(w.cover_food_cell, w.food_cap * w.cover_food_cap, w.food_cap)
    w.food = w.food_cap.copy()
    w._g = w._geometry()
    w._obs = w._obs_from(w._g)


def load_unreal_obstacles(path: Path, sessions) -> dict:
    """언리얼 장애물 JSON(파일 하나 = 모든 세션, 폴더 = 세션마다 s<시드>.json) → {(세션, 지역): [[x, y, r], …]}."""
    path = Path(path)
    out = {}
    for u in sessions:
        f = path / f"s{int(u)}.json" if path.is_dir() else path
        d = json.loads(f.read_text(encoding="utf-8"))
        for r in d["regions"]:
            out[(int(u), r["region"])] = [[float(v) for v in row] for row in r["discs"]]
    return out


def eat_steps_of_seconds(sec: float) -> int:
    """늑대 식사 초 → 결정 스텝 = 반올림(초 ÷ 8/60), 0.5 는 올림(C++ FEcoV3IntegratedSettings::WolfEatSteps, 5 초 → 38)."""
    return int(np.floor(sec / STEP_SECONDS + 0.5))


def parse_sets(items) -> tuple:
    """--set 블록.키=값 목록 → ((블록, 키, 값), …). 값은 JSON(true·false·수·목록), 아니면 문자열."""
    out = []
    for it in items or ():
        k, eq, v = it.partition("=")
        blk, dot, key = k.partition(".")
        if not (blk and dot and key and eq):
            raise ValueError(f"--set 은 블록.키=값 이어야 한다: {it!r}")
        try:
            val = json.loads(v)
        except json.JSONDecodeError:
            val = v
        out.append((blk, key, val))
    return tuple(out)


def mirror_cfg(deer: int, eat_steps: int, config: Path = CONFIG, disable=(), wolf_margin: float | None = None, sets=()):
    """거울 설정에 사슴 수 N(= 슬롯 수 = 피식 EMA 분모)과 늑대 먹는 시간(pred_eat_cd)을 덮는다. disable = 끌 기능 블록 이름들(설정에 켜져 있어야 한다).
    wolf_margin(단위, 10-17)을 주면 realism_shelter.wolf_margin 을 덮는다(설정에 realism_shelter.block_predators 가 켜져 있어야 한다).
    sets = ((블록, 키, 값), …) 기능 블록 계수 덮기(10-17 장애물 돌아가기 끈 판 obstacles.detour=false 등 — 블록이 설정에 있어야 한다)."""
    from env_v2.config import load_v2_config

    if deer < 1 or eat_steps < 1:
        raise ValueError(f"사슴 수와 먹는 시간은 1 이상이어야 한다: {deer}, {eat_steps}")
    cfg = load_v2_config(config).replace(N=int(deer), pred_eat_cd=int(eat_steps))
    if disable or wolf_margin is not None or sets:
        f = {k: dict(v) for k, v in cfg.v2["features"].items()}
        for blk, key, val in sets:
            if blk not in f:
                raise ValueError(f"--set 블록 {blk} 이 설정 {config} 에 없다")
            f[blk][key] = val
        for name in disable:
            if not f.get(name, {}).get("enabled"):
                raise ValueError(f"끌 기능 {name} 이 설정 {config} 에 켜져 있지 않다")
            f[name]["enabled"] = False
        if wolf_margin is not None:
            zs = f.get("realism_shelter", {})
            if not (zs.get("enabled") and zs.get("block_predators")):
                raise ValueError(f"--wolf-margin 은 realism_shelter.block_predators 를 켠 설정에만 쓴다: {config}")
            f["realism_shelter"] = dict(zs, wolf_margin=float(wolf_margin))
        cfg = cfg.replace(v2=dict(cfg.v2, features=f))
    return cfg


def config_digest(cfg) -> str:
    return hashlib.sha1(json.dumps(cfg.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:12]


def _row(w, alive_before: int, food0: float, shelter: list[int]) -> dict:
    e = np.clip(w.energy[w.alive] / w.cfg.max_energy, 0.0, 1.0)
    h = w.hunt_stats()
    extra = {}
    if getattr(w, "_wp", None) is not None:
        # 야생 2단계 2(10-17): 누적 늑대 무리 칸(언리얼 '[EcoV3I] <지역> 늑대 무리 |' 줄과 같은 정의). CSV 열(ROW_KEYS)에는 넣지 않는다
        ps = w.pack_stats()
        extra = dict(pack_wolf_steps=ps["wolf_steps"], pack_lead=ps["lead_n"], pack_help=ps["help_n"], pack_wait=ps["wait_n"],
                     pack_door=ps["door_n"], pack_catches=ps["catches"], pack_coop=ps["pack_catches"])
    if getattr(w, "_ob", None) is not None:
        # 야생 2단계 3(10-17): 누적 장애물 칸(언리얼 '[EcoV3I] <지역> 장애물 |' 줄과 같은 정의). CSV 열(ROW_KEYS)에는 넣지 않는다
        os_ = w.obstacle_stats()
        extra |= {f"ob_{k}": os_[k] for k in ("deer_steps", "deer_hit", "deer_back", "wolf_steps", "wolf_hit", "wolf_back", "wolf_dead",
                                             "eye_pairs", "eye_blocked", "tgt_pairs", "tgt_blocked")}
        if "detour" in os_:     # 10-17 돌아가기(obstacles.detour): 언리얼 일곱째 줄 끝 '돌아가기 |' 칸과 같은 정의
            extra |= {f"det_{k}": v for k, v in os_["detour"].items()}
    return extra | dict(t_s=round(w.t * STEP_SECONDS, 1), step=int(w.t), alive=int(alive_before), alive_end=int(w.alive.sum()),
                n=int(w.N), caught=int(w._pred_deaths), starved=int(w._starve_deaths),
                food_pct=float(100.0 * w.food.sum() / food0) if food0 > 0 else 0.0,
                energy_pct=float(100.0 * e.mean()) if len(e) else 0.0, hungry=int(np.count_nonzero(e < STARVING)),
                dark=float(w.dark), wolves_asleep=int(np.count_nonzero(w.pred_asleep)),
                hunt_starts=h["starts"], hunt_ends=h["ends"], hunt_success=h["success"],
                shelter_steps=int(shelter[0]), live_steps=int(shelter[1]))


DIAG_BANDS_M = (0.0, 5.0, 10.0, 15.0, 30.0)      # 진단: 늑대 거리 구간(m, 1 단위 = 2 m)
FLED_STEPS = 38                                   # 진단: '마지막 5초' = 반올림(5 ÷ 8/60)
EDGE_BAND = 2.5                                   # 진단: 가장자리 띠 5 m (단위)
CORNER_BAND = 5.0                                 # 진단: 모서리 = 두 벽 모두 10 m 안 (단위)
REPEAT_R = 10.0                                   # 진단: 같은 늑대 거듭 포획 = 자기 지난 포획 자리 20 m 안 (단위)
RING_BANDS = (1.0, 2.0)                           # 진단: 은신처 둘레 밖 띠 2 m·4 m (단위)
BODY_1M = 0.5                                     # 진단: 늑대 몸 여유 1 m (단위) — 설정 값과 상관없이 같은 잣대로 센다


class _Diag:
    """--diag 진단 모으개(모듈 docstring '야생 1단계'). 스텝 뒤 상태만 읽는다(동역학과 무관)."""

    def __init__(self, w):
        nb = len(DIAG_BANDS_M) - 1
        self.n_beh = np.zeros(5, dtype=np.int64)
        self.pairs = np.zeros(nb, dtype=np.int64)
        self.seen = np.zeros(nb, dtype=np.int64)
        self.last_flee = np.full(w.N, -(10 ** 9), dtype=np.int64)
        self.last_seen = np.full(w.N, -(10 ** 9), dtype=np.int64)
        self.catch_beh = np.zeros(5, dtype=np.int64)
        self.catch_fled = self.catch_saw = self.catches = 0
        self.starve_fled = self.starves = 0
        self.edges = np.asarray(DIAG_BANDS_M) / 2.0
        self.catch_edge = self.catch_corner = self.catch_cover = self.catch_repeat = 0
        self.occ_n = self.occ_edge = self.occ_corner = 0
        self.wolf_last: dict[int, np.ndarray] = {}
        self.panic_ends = self.panic_end_awake = 0
        self.prev_wf = w.wf_mode.copy() if getattr(w, "_wf", None) is not None else None
        self.catch_ring = [0] * len(RING_BANDS)
        self.wolf_steps = self.wolf_in_r = self.wolf_in_1m = 0
        self.wolf_edge_min = float("inf")
        self.heard_live = self.live_obs = 0       # 10-18: 들어서만 안 산 사슴·스텝 / 산 사슴·스텝 (스텝 끝 관측 — C++ FWorldStats::SenseHeardOnly·SenseLiveSteps)

    def after(self, w, live_before):
        from env_v2 import repertoire as rep

        beh = w._rs.behavior
        self.n_beh += np.bincount(beh[live_before], minlength=5)
        self.last_flee[live_before & (beh == rep.FLEE)] = w.t
        g, live = w._g, w.alive
        if w.M:
            awake = ~w.pred_asleep
            d = np.sqrt(((w.pos[:, None, :] - w.pred_pos[None, :, :]) ** 2).sum(-1))
            pv = g["wf_pvis"]
            self.last_seen[live_before & (pv & awake[None, :]).any(1)] = w.t
            m = live[:, None] & awake[None, :]
            if "rz_heard" in g:
                # 10-18 (야생 3단계 짝 비교): 들어서만 안 몫을 산 사슴으로만 센다(realism_stats heard_only_frac 은 죽은 슬롯까지 N 으로 나눈다).
                # C++ 통합 모드 10초 여덟째 줄 '들어서만 안 사슴·스텝' 과 같은 정의
                self.heard_live += int(np.count_nonzero(g["rz_heard"] & live))
                self.live_obs += int(np.count_nonzero(live))
            for b in range(len(self.edges) - 1):
                sel = m & (d >= self.edges[b]) & (d < self.edges[b + 1])
                self.pairs[b] += int(sel.sum())
                self.seen[b] += int((sel & pv).sum())
        sz = float(w.size)
        p = w.pos[live_before]
        ex_, ey_ = np.minimum(p[:, 0], sz - p[:, 0]), np.minimum(p[:, 1], sz - p[:, 1])
        self.occ_n += len(p)
        self.occ_edge += int(np.count_nonzero(np.minimum(ex_, ey_) <= EDGE_BAND))
        self.occ_corner += int(np.count_nonzero((ex_ <= CORNER_BAND) & (ey_ <= CORNER_BAND)))
        if self.prev_wf is not None:
            from env_v2.world import WF_PANIC

            ends = (self.prev_wf == WF_PANIC) & (w.wf_mode != WF_PANIC) & live
            self.panic_ends += int(np.count_nonzero(ends))
            if w.M and ends.any():
                near = ((d <= w._wf["safe_r"]) & awake[None, :]).any(1)
                self.panic_end_awake += int(np.count_nonzero(ends & near & ~g["in_cover"]))
            self.prev_wf = w.wf_mode.copy()
        if w.M and len(w.cov_r):
            # 10-17: 늑대 중심과 은신처 둘레 (스텝 끝 위치, 원 반지름 r — 여유와 상관없이 같은 잣대)
            de = (np.sqrt(((w.pred_pos[:, None, :] - w.cov_c[None, :, :]) ** 2).sum(-1)) - w.cov_r[None, :]).min(1)
            self.wolf_steps += len(de)
            self.wolf_in_r += int(np.count_nonzero(de < 0.0))
            self.wolf_in_1m += int(np.count_nonzero(de < BODY_1M))
            self.wolf_edge_min = min(self.wolf_edge_min, float(de.min()))
        for i in np.flatnonzero(live_before & ~live):
            fled = w.t - self.last_flee[i] <= FLED_STEPS
            if w.death_cause[i] == 1:
                q = w.pos[i]
                qe = (min(q[0], sz - q[0]), min(q[1], sz - q[1]))
                self.catch_edge += int(min(qe) <= EDGE_BAND)
                self.catch_corner += int(max(qe) <= CORNER_BAND)
                self.catch_cover += int(w._in_cover(q[None, :])[0]) if len(w.cov_r) else 0
                if len(w.cov_r):
                    dq = float((np.sqrt(((q[None, :] - w.cov_c) ** 2).sum(1)) - w.cov_r).min())
                    for b, band in enumerate(RING_BANDS):
                        self.catch_ring[b] += int(0.0 < dq <= band)
                if w.M:
                    cand = np.flatnonzero(w.pred_cd == int(w.cfg.pred_eat_cd))
                    cand = cand if len(cand) else np.arange(w.M)
                    m = int(cand[np.argmin(((w.pred_pos[cand] - q) ** 2).sum(1))])
                    last = self.wolf_last.get(m)
                    self.catch_repeat += int(last is not None and float(np.sqrt(((last - q) ** 2).sum())) <= REPEAT_R)
                    self.wolf_last[m] = q.copy()
                self.catches += 1
                self.catch_beh[beh[i]] += 1
                self.catch_fled += int(fled)
                self.catch_saw += int(w.t - self.last_seen[i] <= FLED_STEPS)
            else:
                self.starves += 1
                self.starve_fled += int(fled)

    def result(self, w) -> dict:
        out = dict(beh_steps=self.n_beh.tolist(), band_pairs=self.pairs.tolist(), band_seen=self.seen.tolist(),
                   catches=self.catches, catch_beh=self.catch_beh.tolist(), catch_fled=self.catch_fled, catch_saw=self.catch_saw,
                   starves=self.starves, starve_fled=self.starve_fled, wolves=int(w.M_base), period=int(w.dn_period), steps=int(w.t))
        out.update(catch_edge=self.catch_edge, catch_corner=self.catch_corner, catch_cover=self.catch_cover, catch_repeat=self.catch_repeat,
                   occ_n=self.occ_n, occ_edge=self.occ_edge, occ_corner=self.occ_corner, panic_ends=self.panic_ends,
                   panic_end_awake=self.panic_end_awake)
        out.update(heard_live=self.heard_live, live_obs=self.live_obs)
        out.update(catch_ring=list(self.catch_ring), wolf_steps=self.wolf_steps, wolf_in_r=self.wolf_in_r, wolf_in_1m=self.wolf_in_1m,
                   wolf_edge_min=None if self.wolf_edge_min == float("inf") else round(self.wolf_edge_min, 6))
        try:
            out["wild"] = w.wild_stats()
        except ValueError:
            pass
        return out


def run_world(job: dict) -> dict:
    """세계 하나(언리얼 지역 무대 하나): job = {cfg (설정 dict), seed, steps, model, log_every}. 메타 + 10초 줄."""
    from env.config import Config
    from env_v2 import rollout as ro
    from env_v2.world import PT_STALKER, World

    t0 = time.perf_counter()
    cfg = Config(job["cfg"])
    seed = int(job["seed"])
    w = World(cfg, seeds=[seed])
    if w.alive is None:
        raise ValueError("거울 설정은 integrated_stage.respawn false 여야 한다(부활 없음)")
    um = job.get("unreal_map")
    if um is not None:
        apply_unreal_map(w, int(um["seed"]), um["region"])          # 짝 비교: 언리얼 지역 무대와 같은 먹이 지도
    dg = None
    if job.get("diag"):
        w.keep_pair_vis = True                  # 진단 전용: 기하에 보임 행렬을 남긴다(관측·동역학은 그대로)
        w._g = w._geometry()
        w._obs = w._obs_from(w._g)
        dg = _Diag(w)
    pol = ro.build_policy({"kind": "rep_learned", "path": str(job["model"])}, seed)
    ro.forward_bind(pol, w)
    food0 = float(w.food.sum())
    meta = dict(seed=seed, n=int(w.N), eat_steps=int(cfg.pred_eat_cd), size=float(w.size), wolves=int(w.M),
                wolf_kinds=["stalker" if k == PT_STALKER else "chaser" for k in w.pred_type.tolist()],
                wolf_start=w.pred_pos.round(4).tolist(), covers=np.c_[w.cov_c, w.cov_r].round(4).tolist(),
                cover_frac=float(w.cover_frac_actual), stage_complete=w.stage_complete, period=int(w.dn_period),
                offset=int(w.dn_offset), dark0=float(w.dark), asleep0=int(np.count_nonzero(w.pred_asleep)),
                allowed=list(pol.allowed), food0=food0)
    if um is not None:
        meta["unreal_map"] = dict(um)
    rows = []
    shelter = [0, 0]                    # 누적 [은신처 원 안 산 사슴-스텝, 산 사슴-스텝] (스텝 첫머리에 산 사슴의 이동 뒤 위치 — C++ Prey.bInCover 와 같다)
    for _ in range(int(job["steps"])):
        live_before = w.alive
        alive_before = int(live_before.sum())
        w.step(np.asarray(pol(w.observe()), dtype=np.float64))
        shelter[0] += int(np.count_nonzero(live_before & w._in_cover(w.pos)))
        shelter[1] += alive_before
        if dg is not None:
            dg.after(w, live_before)
        if w.t % int(job["log_every"]) == 0:
            rows.append(_row(w, alive_before, food0, shelter))
    if dg is not None:
        meta["diag"] = dg.result(w)
    # 끝난 사냥이 없으면 rate 가 nan 이다 — 메타에는 None 으로 적는다(같은 인자면 같은 메타를 지키려고: nan != nan)
    meta["hunt"] = {k: (None if isinstance(v, float) and v != v else v) for k, v in w.hunt_stats().items()}
    meta["shelter_steps"], meta["live_steps"] = int(shelter[0]), int(shelter[1])
    if getattr(w, "_wp", None) is not None:
        meta["pack"] = w.pack_stats()       # 야생 2단계 2 늑대 무리 협동 통계(동역학과 무관)
    if getattr(w, "_ob", None) is not None:
        meta["obstacles"] = w.obstacle_stats()   # 야생 2단계 3 세로 장애물 통계(동역학과 무관)
    if getattr(w, "_wx", None) is not None:
        meta["weather"] = w.weather_stats()      # 야생 3단계 지역 날씨(지역·날씨·배수·날씨별 스텝, 동역학과 무관)
    if getattr(w, "_zh", None) is not None:
        rz = w.realism_stats()                   # 야생 3단계 진단(10-18): 들어서만 안 몫(빗소리가 발소리를 덮는 효과를 본다, 동역학과 무관)
        meta["heard_only_frac"] = None if rz["heard_only_frac"] != rz["heard_only_frac"] else rz["heard_only_frac"]
    meta["death_t"] = w.death_t.tolist()
    meta["death_cause"] = w.death_cause.tolist()
    meta["wall_s"] = round(time.perf_counter() - t0, 3)
    return dict(meta=meta, rows=rows)


def run(deer: int, eat_steps: int, seeds, *, steps: int = STEPS, workers: int | None = None, model: Path = MODEL,
        config: Path = CONFIG, log_every: int = LOG_EVERY, unreal_maps=None, replicates: int = 1, disable=(),
        diag: bool = False, wolf_margin: float | None = None, unreal_obstacles: Path | None = None, sets=()) -> dict:
    """시드마다 세계 하나를 (워커 풀로) 돌린다. 반환 {meta, worlds}(worlds 는 시드 순서 = 받은 순서).
    unreal_maps(언리얼 세션 시드 목록)를 주면 짝 비교: 지도 (세션 시드, 지역 Barren·Forest·Highland) 마다 replicates 개 세계를 seeds 의 앞에서부터
    차례로 쓴다(지도 i 의 j 번째 = seeds[i·replicates + j], 시드 수 = 세션 수 × 3 × replicates)."""
    from env_v2 import rollout as ro

    cfg = mirror_cfg(deer, eat_steps, config, disable, wolf_margin, sets)
    seeds = [int(s) for s in seeds]
    jobs = [dict(cfg=cfg.to_dict(), seed=s, steps=int(steps), model=str(model), log_every=int(log_every)) for s in seeds]
    if diag:
        for j in jobs:
            j["diag"] = True
    maps = None
    if unreal_maps is not None:
        maps = [(int(u), r) for u in unreal_maps for r in sorted(UNREAL_REGION_STREAM)]
        k = int(replicates)
        if k < 1 or len(seeds) != len(maps) * k:
            raise ValueError(f"짝 비교는 시드가 지도 {len(maps)}장 × replicates {k} = {len(maps) * k}개여야 한다. 받은 수 {len(seeds)}")
        obs = None
        if unreal_obstacles is not None:
            if not cfg.v2["features"].get("obstacles", {}).get("enabled"):
                raise ValueError(f"--unreal-obstacles 는 obstacles 를 켠 설정에만 쓴다: {config}")
            obs = load_unreal_obstacles(unreal_obstacles, unreal_maps)
        wx_on = bool(cfg.v2["features"].get("wild_weather", {}).get("enabled"))
        for i, (u, r) in enumerate(maps):
            for j in range(k):
                jobs[i * k + j]["unreal_map"] = dict(seed=u, region=r, replicate=j)
                if obs is not None or wx_on:
                    c = copy.deepcopy(jobs[i * k + j]["cfg"])
                    if obs is not None:
                        # 그 지도의 언리얼 원판을 fixed 로(무작위 배치 대신 — 난수를 뽑지 않는다)
                        c["v2"]["features"]["obstacles"]["fixed"] = obs[(u, r)]
                    if wx_on:
                        # 야생 3단계(10-18): 그 지도 지역의 날씨(설정의 wild_weather.regions 표 — 지역 이름이 없으면 세계를 만들 때 실패)
                        c["v2"]["features"]["wild_weather"]["region"] = r
                    jobs[i * k + j]["cfg"] = c
    elif unreal_obstacles is not None:
        raise ValueError("--unreal-obstacles 는 --unreal-maps(짝 비교)와 함께 쓴다")
    t0 = time.perf_counter()
    ex = ro.make_executor(ro.default_workers(len(jobs)) if workers is None else min(int(workers), len(jobs)))
    if ex is None:
        worlds = [run_world(j) for j in jobs]
    else:
        with ex:
            worlds = list(ex.map(run_world, jobs))
    meta = dict(config=str(Path(config).relative_to(ROOT)) if Path(config).is_relative_to(ROOT) else str(config),
                config_digest=config_digest(cfg), model=Path(model).name, deer=int(deer), eat_steps=int(eat_steps),
                eat_seconds=round(eat_steps * STEP_SECONDS, 3), steps=int(steps), log_every=int(log_every), seeds=seeds,
                session_size=3, wall_s=round(time.perf_counter() - t0, 2))
    if disable:
        meta["disable"] = list(disable)
    if wolf_margin is not None:
        meta["wolf_margin"] = float(wolf_margin)
    if sets:
        meta["set"] = [f"{b}.{k}={json.dumps(v)}" for b, k, v in sets]
    if maps is not None:
        meta.update(unreal_maps=[int(u) for u in unreal_maps], replicates=int(replicates))
    if unreal_obstacles is not None:
        meta["unreal_obstacles"] = str(unreal_obstacles)
    return dict(meta=meta, worlds=worlds)


def write(result: dict, name: str, out_dir: Path = OUT) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    jp, cp = out_dir / f"{name}.json", out_dir / f"{name}.csv"
    jp.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    with open(cp, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(("seed",) + ROW_KEYS)
        for wd in result["worlds"]:
            for r in wd["rows"]:
                wr.writerow((wd["meta"]["seed"],) + tuple(r[k] for k in ROW_KEYS))
    return jp, cp


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--deer", type=int, default=128, help="지역마다 사슴 수 N (128·64·32·16)")
    ap.add_argument("--wolf-eat-steps", type=int, default=38, help="늑대 식사 스텝 (5초 38, 30초 225, 60초 450)")
    ap.add_argument("--seeds", default="32000-32089", help="시드 (예: 32000-32089, 33000,33001). 3개씩 한 세션으로 본다")
    ap.add_argument("--steps", type=int, default=STEPS)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--name", default=None, help="출력 이름 (기본 d<N>_e<식사>_s<처음>-<끝>)")
    ap.add_argument("--out-dir", type=Path, default=OUT)
    ap.add_argument("--unreal-maps", default=None, help="짝 비교: 언리얼 세션 시드(예: 20000-20002)의 지역 먹이 지도를 쓴다")
    ap.add_argument("--replicates", type=int, default=1, help="짝 비교: 지도마다 파이썬 세계 수")
    ap.add_argument("--config", type=Path, default=CONFIG, help="거울 설정 (기본 configs/v3_unreal_mirror.yaml)")
    ap.add_argument("--disable", default="", help="설정에서 끌 기능 블록(쉼표, 예: wild_flight)")
    ap.add_argument("--diag", action="store_true", help="세계마다 진단(meta['diag'])을 더 적는다")
    ap.add_argument("--wolf-margin", type=float, default=None, help="realism_shelter.wolf_margin 덮기(단위, 1 단위 = 2 m. 10-17 늑대 몸 여유)")
    ap.add_argument("--unreal-obstacles", type=Path, default=None, help="짝 비교: 언리얼 장애물 JSON(파일 또는 s<세션>.json 폴더)의 지역 원판을 쓴다")
    ap.add_argument("--set", action="append", default=[], help="기능 블록 계수 덮기 블록.키=값 (예: obstacles.detour=false — 10-17 돌아가기 끈 판)")
    ap.add_argument("--model", type=Path, default=MODEL, help="두뇌 모델 .zip (기본 R1b s3 — 10-18 R4 언리얼 확인은 R4 모델을 준다)")
    a = ap.parse_args(argv)
    seeds = parse_seeds(a.seeds)
    um = parse_unreal_maps(a.unreal_maps) if a.unreal_maps else None
    disable = tuple(x.strip() for x in a.disable.split(",") if x.strip())
    config = a.config if a.config.is_absolute() else (ROOT / a.config)
    res = run(a.deer, a.wolf_eat_steps, seeds, steps=a.steps, workers=a.workers, unreal_maps=um, replicates=a.replicates,
              config=config, disable=disable, diag=a.diag, wolf_margin=a.wolf_margin, unreal_obstacles=a.unreal_obstacles,
              sets=parse_sets(a.set), model=a.model if a.model.is_absolute() else ROOT / a.model)
    name = a.name or (f"d{a.deer}_e{a.wolf_eat_steps}_s{seeds[0]}-{seeds[-1]}" if um is None else
                      f"pair_d{a.deer}_e{a.wolf_eat_steps}_u{um[0]}-{um[-1]}_k{a.replicates}_s{seeds[0]}-{seeds[-1]}")
    jp, cp = write(res, name, a.out_dir)
    walls = [wd["meta"]["wall_s"] for wd in res["worlds"]]
    print(f"{name}: 세계 {len(walls)}개, 전체 {res['meta']['wall_s']:.1f}초, 세계당 {np.mean(walls):.2f}초 (워커 안 벽시계)")
    last = [wd["rows"][-1] for wd in res["worlds"] if wd["rows"]]
    at = [next((r for r in wd["rows"] if r["t_s"] == 230.0), None) for wd in res["worlds"]]
    for wd, r in zip(res["worlds"], at):
        if r is not None:
            print(f"  시드 {wd['meta']['seed']}: 230초 산 {r['alive']}/{r['n']} 포획 {r['caught']} 굶음 {r['starved']} "
                  f"먹이 {r['food_pct']:.0f}% 에너지 {r['energy_pct']:.0f}%")
    if last:
        print(f"-> {jp}\n-> {cp}")


if __name__ == "__main__":
    main()

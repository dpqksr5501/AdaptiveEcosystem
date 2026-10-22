"""v3 야생 1단계 골든 내보내기 — 파이썬 야생 규칙(env_v2/world.py '야생 1단계')을 언리얼 C++ `EcoWorldV3.h` 와 대조할 골든 헤더를 만든다
(명세 `Docs/RL_Policy/RL_V3_WILD1_SPEC.md` 5절 '골든 시험').

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_wild.py
    # 시험용 다른 폴더
    python export_golden_v3_wild.py --out <폴더>

세계·시드:
  - 세계: configs/v3_wild1_mirror.yaml (사람 결정 10-15 (7) 야생 1단계 거울 세계). 계수는 그 세계가 읽은 값(`World._wr`)을 그대로 싣는다.
  - 시드: 탐색 시드 32090 하나(세계를 만들기만 하고 난수 궤적은 쓰지 않는다). 판정 시드는 쓰지 않는다.
  - C++ 와 파이썬은 난수열이 달라 궤적 대조는 하지 않는다(명세 5절). 대신 난수 없는 장면을 파이썬 함수 그대로 돌려 적는다.

묶음 (지금은 (w1) 지방 비축만 — 뒤 규칙은 같은 헤더에 묶음을 더한다):
  비축 한 번  `World._wild_reserve_step` 을 한 번 부른 사례. 입력 (e_new, 먹은 에너지, R) → 출력 (E, R). 모자람을 다 채움·못 채움·R 0,
              채움·빈자리로 자름·R 가득·문턱 아래·먹지 않음·문턱 정확히 같음 같은 끝 사례.
  굶음 열     걷기 대사만(스텝마다 e_new = E − energy_drain, 먹이 0)으로 E 0.5·R 가득에서 굶어 죽을 때까지. 죽는 스텝(명세: 2950)과
              100 스텝마다의 (E, R).
  섞음 열     정해진 먹이 무늬(스텝 t 의 먹은 에너지 = 0.03 if (t // 50) % 3 == 0 else 0, e_new = min(E − drain + 먹은 것, max_energy))로
              E 0.2·R 0.2 에서 600 스텝. 스텝마다 (E, R). C++ 은 같은 식으로 자기 출력을 이어 쓴다.
  포만 열     (w2) 늑대 포만. 거울 세계를 만든 뒤 사슴을 모두 (1, 1) 로, 늑대 둘(추격형·잠행형)을 무대 가운데 (30, 30) 로 옮기고, 낮(d = 0)·
              깨어 있음·밤잠 활동도 가득·속력 배수 1 로 두고, 막 잡은 늑대처럼 쿨다운 = pred_eat_cd(38)·배부름 = sat 스텝(450)에서
              `World._step_predators_v3` 만 500 번 부른다(사슴은 시야 밖이라 표적·포획이 없다). 스텝마다 늑대별 (쿨다운, 남은 배부름,
              배부름 훅, 지난 변위 크기). 변위 크기는 벽에 닿은 스텝만 속력보다 작다.
  지각 장면  R3 감지 (realism_vision 300°·realism_hearing 발소리, 거울 세계 값 그대로). 장면 12개 — 난수(시드 32092, 이 내보내기 전용)로
              늑대 둘의 자리·지난 변위(속력 0~0.75 단위/스텝)·전력 걸음 여부, 사슴 16의 자리(늑대 0 둘레 ±30)·heading·행동 시야 배수
              {1, 0.6, 0.3} 를 정하고 낮(d = 0)·깨어 있음에서 `World._geometry` 를 부른다. 늑대마다 소리 반경(`hearing_radius`), 사슴 × 늑대
              알아챔(wf_pvis — 관측과 같은 보임), 사슴마다 보이는 늑대 수·가장 가까운 거리(없으면 −1).
  도주 장면  (w3) 도주 반사 거리. 거울 세계(감지·포만 켬)에 장면 상태(사슴 자리·heading·시야 배수·지난 덮기·잠금, 늑대 자리·변위·전력 걸음·
              쿨다운·배부름·표적, 은신처)를 넣고 `World._geometry` → `World._wf_update` 를 부른다. 장면 = tests/test_wild1.py 의 반사 장면
              (사슴 2 를 (30, 30) 에 두고 늑대 0 을 +5·+8.5·먹는 중·배부름·이 사슴을 쫓음·은신처 안, 지난 도주 뒤 15·21, 반대쪽 은신처) 과
              벽·접근 장면 12개 + 난수 장면 16개(시드 32093). 사슴마다 다음 덮기·방향·잠금.
  늑대 몸 여유 (10-17, world.py 모듈 docstring (c″)): 은신처 진입 금지 경우(여유 0 — 10-16 칸 그대로)와 같은 원·같은 뽑기로, 거울 설정의 여유
              realism_shelter.wolf_margin(0.5 = 1 m)을 둔 세계의 밀어내기·접선·원 판정 64 경우. C++ 은 원 반지름에 여유를 더한 원 목록으로
              ShelterPush·ShelterTangent·InsideAnyDisc 를 불러 같은 값을 내야 한다(통합 모드가 위협 Step 에 넘기는 원 목록과 같은 꼴).
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

from env_v2.config import load_v2_config
from env_v2.world import World, hearing_radius, wf_edge_steer

HERE = Path(__file__).resolve().parent
WILD = HERE / "configs" / "v3_wild1_mirror.yaml"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
SEED = 32090
N = 16


def load_old():
    """10-15 야생 설정(10-16 고침 전): realism_shelter 끔, wild_flight 의 새 선택 키(hold_awake·edge_r)를 뺀다(코드 기본값 = 10-15 그대로).
    10-15 골든 칸(비축·포만·감지·도주 장면)은 이 설정으로 만들어 그대로 둔다(C++ 기본값 시험이 그대로 맞는다)."""
    cfg = load_v2_config(WILD)
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    f["realism_shelter"] = dict(f["realism_shelter"], enabled=False)
    f["wild_flight"] = {k: v for k, v in f["wild_flight"].items() if k not in ("hold_awake", "edge_r")}
    return cfg.replace(v2=dict(cfg.v2, features=f))


def d_lit(x) -> str:
    """double 리터럴: 파이썬 repr (다시 읽으면 같은 float64 가 되는 가장 짧은 표기)."""
    x = float(x)
    if not math.isfinite(x):
        raise SystemExit(f"헤더에 유한하지 않은 값: {x}")
    s = repr(x)
    return s if ("." in s or "e" in s or "inf" in s) else s + ".0"


def c_array(ctype: str, name: str, flat: list, per_line: int, fmt) -> str:
    if not flat:
        raise SystemExit(f"{name} 가 비었다 — C++ 배열은 크기 0 일 수 없다")
    lines = [f"\tinline constexpr {ctype} {name}[{len(flat)}] = {{"]
    for k in range(0, len(flat), per_line):
        lines.append("\t\t" + ", ".join(fmt(v) for v in flat[k:k + per_line]) + ",")
    lines.append("\t};")
    return "\n".join(lines)


def make_world() -> World:
    w = World(load_old().replace(N=N), seeds=[SEED])
    w.reset()
    if w._wr is None:
        raise SystemExit("v3_wild1_mirror.yaml 의 wild_reserve 가 꺼졌다")
    return w


def reserve_once(w: World, e_new: float, gain_e: float, r: float) -> tuple[float, float]:
    """`World._wild_reserve_step` 을 한 번(모든 행 같은 값) 부르고 0 행의 (E, R) 를 돌려준다."""
    w.reserve = np.full(w.N, float(r))
    e = w._wild_reserve_step(np.full(w.N, float(e_new)), np.full(w.N, float(gain_e)), None)
    return float(e[0]), float(w.reserve[0])


def reserve_cases(w: World) -> list[tuple[float, float, float, float, float]]:
    re = w._wr["refill_e"]
    ins = [
        (-0.002, 0.0, 1.0),            # 걷기 대사 한 스텝 — 다 채움
        (-0.002, 0.0, 0.0),            # R 0 — 못 채움, E 그대로
        (-0.01, 0.0, 0.001),           # R 이 모자람보다 작다 — R 0, E = 남은 모자람
        (-0.0054, 0.0, 0.001),         # 모자람 = R·C 정확히 (부동소수 경계 — 덮음 판정 want <= r0)
        (0.0, 0.0, 0.5),               # E 0 정확히 — 꺼내지 않음
        (0.8, 0.03, 0.5),              # 채움 (문턱 위, 먹음)
        (0.8, 0.03, 0.999),            # 빈자리 (1 − R)·C 로 자름
        (0.8, 0.03, 1.0),              # R 가득 — 채우지 않음
        (0.69, 0.03, 0.5),             # 문턱 아래 — 채우지 않음
        (0.8, 0.0, 0.5),               # 먹지 않음 — 채우지 않음
        (re, 0.02, 0.3),               # 문턱 정확히 — 채움 (e_out >= refill_e)
        (1.0, 0.06, 0.0),              # 배 가득·R 빈 — 한 스텝 최대 채움
        (-0.002, 0.03, 0.4),           # 먹었어도 대사로 0 밑 — 꺼내기만
        (0.5, 0.03, 0.2),              # 문턱 아래 보통
    ]
    out = []
    for e_new, g, r in ins:
        e_out, r_out = reserve_once(w, e_new, g, r)
        out.append((e_new, g, r, e_out, r_out))
    return out


def starve_chain(w: World) -> tuple[int, list[tuple[int, float, float]]]:
    drain = w.cfg.energy_drain
    E, R = float(w.cfg.init_energy), float(w._wr["init"])
    samples = [(0, E, R)]
    t = 0
    while True:
        t += 1
        e_new = min(E - drain + 0.0, w.cfg.max_energy)
        w.reserve = np.full(w.N, R)
        E = float(w._wild_reserve_step(np.full(w.N, e_new), np.zeros(w.N), None)[0])
        R = float(w.reserve[0])
        if t % 100 == 0:
            samples.append((t, E, R))
        if E <= 0.0 and R <= 0.0:
            samples.append((t, E, R))
            return t, samples
        if t > 100000:
            raise SystemExit("굶음 열이 끝나지 않는다")


def mixed_chain(w: World, steps: int = 600) -> list[tuple[float, float]]:
    drain = w.cfg.energy_drain
    E, R = 0.2, 0.2
    out = []
    for t in range(steps):
        g = 0.03 if (t // 50) % 3 == 0 else 0.0
        e_new = min(E - drain + g, w.cfg.max_energy)
        w.reserve = np.full(w.N, R)
        E = float(w._wild_reserve_step(np.full(w.N, e_new), np.full(w.N, g), None)[0])
        R = float(w.reserve[0])
        out.append((E, R))
    return out


def satiation_chain(steps: int = 500) -> tuple[World, list[list[tuple[int, int, bool, float]]]]:
    w = World(load_old().replace(N=N), seeds=[SEED + 1])
    w.reset()
    if w._ws is None:
        raise SystemExit("v3_wild1_mirror.yaml 의 wild_satiation 이 꺼졌다")
    w.pos[:] = [1.0, 1.0]
    w.pred_pos[:] = [30.0, 30.0]
    w.dark = 0.0
    w.pred_asleep[:] = False
    if getattr(w, "_zn", None) is not None:
        w._zn_act[:] = w._zn["ramp_steps"]
    w._pred_speed_mult = np.ones(w.M)
    w.pred_cd[:] = int(w.cfg.pred_eat_cd)
    w.pred_sat[:] = w._ws_sat_steps
    rows = []
    for _ in range(steps):
        w._step_predators_v3()
        rows.append([(int(w.pred_cd[m]), int(w.pred_sat[m]), bool(w.pred_sated[m]), float(np.hypot(*w.pred_vel[m])))
                     for m in range(w.M)])
    return w, rows


def perception_scenes(k_scenes: int = 12):
    w = World(load_old().replace(N=N), seeds=[SEED + 2])
    w.reset()
    if w._zv is None or w._zh is None:
        raise SystemExit("v3_wild1_mirror.yaml 의 realism_vision·realism_hearing 이 꺼졌다")
    rng = np.random.default_rng(SEED + 2)
    w.keep_pair_vis = True
    scenes = []
    for _ in range(k_scenes):
        w.pred_pos[:] = rng.uniform(20.0, 40.0, (w.M, 2))
        w.pos[:] = w.pred_pos[0] + rng.uniform(-30.0, 30.0, (w.N, 2))
        a = rng.uniform(0.0, 2.0 * np.pi, w.N)
        w.head[:] = np.stack([np.cos(a), np.sin(a)], 1)
        sp = rng.uniform(0.0, 0.75, w.M)
        b = rng.uniform(0.0, 2.0 * np.pi, w.M)
        w.pred_vel[:] = np.stack([sp * np.cos(b), sp * np.sin(b)], 1)
        w.pred_running[:] = rng.random(w.M) < 0.5
        w.pred_asleep[:] = False
        w._rep_see[:] = rng.choice([1.0, 0.6, 0.3], w.N)
        w.dark = 0.0
        w._see_pred = w.cfg.see_r
        g = w._geometry()
        hr = hearing_radius(w._zh, np.sqrt((w.pred_vel * w.pred_vel).sum(1)) / w.cfg.herb_speed, w.pred_running)
        dmin = np.where(np.isfinite(g["d_pred_min"]), g["d_pred_min"], -1.0)
        scenes.append(dict(pos=w.pos.copy(), head=w.head.copy(), see=w._rep_see.copy(), ppos=w.pred_pos.copy(),
                           pvel=w.pred_vel.copy(), run=w.pred_running.copy(), hr=hr, pvis=g["wf_pvis"].copy(),
                           count=g["pred_count"].copy(), dmin=dmin))
    return w, scenes


def _flight_world() -> World:
    w = World(load_old().replace(N=N), seeds=[SEED + 3])
    w.reset()
    if w._wf is None or w._ws is None:
        raise SystemExit("v3_wild1_mirror.yaml 의 wild_flight·wild_satiation 이 꺼졌다")
    return w


def _flight_run(w: World, sc: dict) -> dict:
    w.pos[:] = sc["pos"]
    w.head[:] = sc["head"]
    w._rep_see[:] = sc["see"]
    w.pred_pos[:] = sc["ppos"]
    w.pred_vel[:] = sc["pvel"]
    w.pred_running[:] = sc["run"]
    w.pred_cd[:] = sc["cd"]
    w.pred_sat[:] = sc["sat"]
    w.pred_target = np.asarray(sc["target"], dtype=np.int64).copy()
    w.pred_asleep[:] = False
    w.cov_c = np.asarray([c[:2] for c in sc["covers"]], dtype=np.float64).reshape(-1, 2)
    w.cov_r = np.asarray([c[2] for c in sc["covers"]], dtype=np.float64)
    w.dark = 0.0
    w._see_pred = w.cfg.see_r
    w._rs.lock_left[:] = sc["lock"]
    w._g = w._geometry()
    w.wf_mode[:] = sc["prev"]
    w._wf_update(np.zeros(w.N, dtype=bool))
    return dict(mode=w.wf_mode.copy(), dir=w.wf_dir.copy(), lock=w._rs.lock_left.copy())


def flight_scenes(k_random: int = 16):
    w = _flight_world()
    M = w.M
    scenes = []

    def base():
        pos = np.tile([55.0, 55.0], (w.N, 1)) + np.arange(w.N)[:, None] * np.array([0.0, -0.2])
        pos[:4] = [[30.0, 10.0], [30.0, 20.0], [30.0, 30.0], [30.0, 40.0]]
        return dict(pos=pos, head=np.tile([1.0, 0.0], (w.N, 1)), see=np.ones(w.N),
                    ppos=np.array([[35.0, 30.0], [-500.0, -500.0]])[:M].copy(), pvel=np.zeros((M, 2)),
                    run=np.zeros(M, dtype=bool), cd=np.zeros(M, dtype=np.int64), sat=np.zeros(M, dtype=np.int64),
                    target=np.full(M, -1), covers=[(0.0, 0.0, 0.5)], prev=np.zeros(w.N, dtype=np.int8), lock=np.full(w.N, 5))

    def wolf_at(dx, dy=0.0, cd=0, sat=0, target=-1, covers=None, prev2=0):
        sc = base()
        sc["ppos"][0] = sc["pos"][2] + np.array([dx, dy])
        sc["cd"][0], sc["sat"][0], sc["target"][0] = cd, sat, target
        if covers is not None:
            sc["covers"] = covers
        sc["prev"][2] = prev2
        return sc

    # tests/test_wild1.py 의 반사 장면 (test_reflex_triggers_only_on_hunting_wolves·test_panic_continues_until_safe_and_prefers_shelter)
    scenes.append(wolf_at(5.0))                                         # 사냥 중, 도주 거리 안 → 도주
    scenes.append(wolf_at(8.5))                                         # 경계 거리 안·도주 거리 밖 → 경계
    scenes.append(wolf_at(5.0, cd=10))                                  # 먹는 늑대 → 경계만
    scenes.append(wolf_at(5.0, sat=100))                                # 배부른 늑대 → 경계만
    scenes.append(wolf_at(8.5, target=2))                               # 이 사슴을 쫓음 → 도주
    scenes.append(wolf_at(5.0, covers=[(30.0, 30.0, 3.0)]))             # 은신처 안 → 웅크림
    scenes.append(wolf_at(-15.0, prev2=2))                              # 지난 도주, 바로 뒤 15 → 계속
    scenes.append(wolf_at(-21.0, prev2=2))                              # 지난 도주, 21 → 풀림·잠금 0
    scenes.append(wolf_at(5.0, covers=[(25.0, 35.0, 2.0)]))             # 반대쪽 ±60° 은신처 → 그쪽으로
    scenes.append(wolf_at(5.0, cd=10, covers=[(30.0, 30.0, 3.0)], prev2=3))   # 웅크림 → 먹는 늑대만: 풀림
    sc = wolf_at(0.0, 5.0)
    sc["pos"][2] = [30.0, 59.5]
    sc["ppos"][0] = [30.0, 54.5]
    scenes.append(sc)                                                   # 벽 여유 안: 벽 쪽 성분을 지운다
    sc = wolf_at(3.0, 4.0)
    sc["ppos"][0] = sc["pos"][2] + np.array([9.0, 12.0])
    sc["pvel"][0] = [-0.6, -0.8]
    scenes.append(sc)                                                   # 경계 거리 안 빠르게 다가옴(접근 높음) → 도주
    rng = np.random.default_rng(SEED + 3)
    for _ in range(k_random):
        ppos = rng.uniform(5.0, 55.0, (M, 2))
        pos = np.clip(ppos[0] + rng.uniform(-25.0, 25.0, (w.N, 2)), 0.0, 60.0)
        a = rng.uniform(0.0, 2.0 * np.pi, w.N)
        sp = rng.uniform(0.0, 0.7, M)
        b = rng.uniform(0.0, 2.0 * np.pi, M)
        cov = [(float(x), float(y), float(r)) for x, y, r in zip(rng.uniform(5, 55, 2), rng.uniform(5, 55, 2), rng.uniform(2, 6, 2))]
        scenes.append(dict(pos=pos, head=np.stack([np.cos(a), np.sin(a)], 1), see=rng.choice([1.0, 0.6, 0.3], w.N), ppos=ppos,
                           pvel=np.stack([sp * np.cos(b), sp * np.sin(b)], 1), run=rng.random(M) < 0.5,
                           cd=rng.choice([0, 0, 0, 10], M), sat=rng.choice([0, 0, 100], M),
                           target=np.where(rng.random(M) < 0.3, rng.integers(0, w.N, M), -1), covers=cov,
                           prev=rng.choice([0, 0, 1, 2, 3], w.N).astype(np.int8), lock=rng.choice([-1, 0, 5], w.N)))
    outs = [_flight_run(w, sc) for sc in scenes]
    return w, scenes, outs


def flight_fix_scenes(k_random: int = 16):
    """10-16 고친 도주 장면: 설정 값(hold_awake true, edge_r 5) 그대로의 세계로 10-15 장면 전부 + 고침 손 장면 + 가장자리 난수 장면."""
    w = World(load_v2_config(WILD).replace(N=N), seeds=[SEED + 3])
    w.reset()
    if not (w._wf["hold_awake"] and w._wf["edge_r"] > 0.0):
        raise SystemExit("v3_wild1_mirror.yaml 의 wild_flight.hold_awake·edge_r 가 꺼졌다")
    _, old_scenes, _ = flight_scenes(k_random)
    M = w.M
    scenes = []

    def base():
        return {k: (v.copy() if isinstance(v, np.ndarray) else list(v) if isinstance(v, list) else v) for k, v in old_scenes[0].items()}

    def at(deer_xy, wolf_xy, cd=0, sat=0, prev2=0):
        sc = base()
        sc["pos"][2] = deer_xy
        sc["ppos"][0] = wolf_xy
        sc["cd"][0], sc["sat"][0] = cd, sat
        sc["prev"][2] = prev2
        return sc

    # (a) 지난 도주를 깨어 있는 늑대가 붙잡는다
    scenes.append(at([30.0, 30.0], [40.0, 30.0], cd=10, prev2=2))      # 먹는 늑대 10 → 계속(그 늑대 반대)
    scenes.append(at([30.0, 30.0], [40.0, 30.0], sat=100, prev2=2))    # 배부른 늑대 10 → 계속
    scenes.append(at([30.0, 30.0], [51.0, 30.0], cd=10, prev2=2))      # 21 → 풀림
    scenes.append(at([30.0, 30.0], [35.0, 30.0], cd=10))               # 먹는 늑대는 도주를 일으키지 않는다(경계)
    # (b) 가장자리·모서리
    scenes.append(at([1.5, 30.0], [6.5, 30.0]))                         # 왼쪽 벽 앞, 늑대 안쪽 → 벽을 따라
    scenes.append(at([1.5, 1.5], [5.0, 6.0]))                           # 모서리, 늑대 대각선 안쪽 → 벽을 따라 빠져나옴
    scenes.append(at([58.0, 3.0], [53.0, 3.5]))                         # 오른쪽 아래 모서리
    scenes.append(at([3.0, 57.0], [3.5, 49.0], prev2=2))                # 위쪽 벽·왼쪽 모서리 근처, 지난 도주
    scenes.append(at([2.0, 30.0], [10.0, 30.0]))                        # 경계(8 — 도주 거리 밖) 방향도 굽힌다
    scenes.append(at([4.0, 20.0], [4.0, 14.0], cd=10, prev2=2))         # 가장자리를 따라 오는 먹는 늑대, 지난 도주
    hand = len(scenes)
    rng = np.random.default_rng(SEED + 7)
    for _ in range(k_random):
        ppos = rng.uniform(2.0, 58.0, (M, 2))
        pos = np.clip(ppos[0] + rng.uniform(-15.0, 15.0, (w.N, 2)), 0.0, 60.0)
        a = rng.uniform(0.0, 2.0 * np.pi, w.N)
        sp = rng.uniform(0.0, 0.7, M)
        b = rng.uniform(0.0, 2.0 * np.pi, M)
        cov = [(float(x), float(y), float(r)) for x, y, r in zip(rng.uniform(5, 55, 2), rng.uniform(5, 55, 2), rng.uniform(2, 6, 2))]
        scenes.append(dict(pos=pos, head=np.stack([np.cos(a), np.sin(a)], 1), see=rng.choice([1.0, 0.6, 0.3], w.N), ppos=ppos,
                           pvel=np.stack([sp * np.cos(b), sp * np.sin(b)], 1), run=rng.random(M) < 0.5,
                           cd=rng.choice([0, 0, 10], M), sat=rng.choice([0, 0, 100], M),
                           target=np.where(rng.random(M) < 0.3, rng.integers(0, w.N, M), -1), covers=cov,
                           prev=rng.choice([0, 1, 2, 2, 3], w.N).astype(np.int8), lock=rng.choice([-1, 0, 5], w.N)))
    scenes = list(old_scenes) + scenes
    outs = [_flight_run(w, sc) for sc in scenes]
    return w, scenes, outs, len(old_scenes) + hand


def edge_cases(n: int = 96, size: float = 60.0, edge_r: float = 5.0):
    """가장자리 굽히기 wf_edge_steer 골든: (x, y, dx, dy) → (ox, oy). 위치는 가장자리·모서리 쪽이 많게."""
    rng = np.random.default_rng(SEED + 8)

    def near(k):
        return np.where(rng.random(k) < 0.5, rng.uniform(0.0, 7.0, k), size - rng.uniform(0.0, 7.0, k))

    x = np.where(rng.random(n) < 0.7, near(n), rng.uniform(0.0, size, n))
    y = np.where(rng.random(n) < 0.7, near(n), rng.uniform(0.0, size, n))
    a = rng.uniform(0.0, 2.0 * np.pi, n)
    pos, d = np.stack([x, y], 1), np.stack([np.cos(a), np.sin(a)], 1)
    d[:4] = [[-1.0, 0.0], [1.0, 0.0], [0.0, -1.0], [0.0, 1.0]]          # 벽에 곧장(따라가는 성분 0 — 무대 가운데 쪽)
    pos[:4] = [[1.0, 30.0], [59.0, 40.0], [20.0, 0.5], [30.0, 59.5]]
    out = wf_edge_steer(pos, d, size, edge_r)
    return [(*pos[i], *d[i], *out[i]) for i in range(n)]


def shelter_cases(n: int = 64, margin: float = 0.0):
    """은신처 진입 금지 골든 (world.py `_rz_wall_push`·`_rz_wall_tangent`·`_rz_inside_disc`): 원 = 통합 무대 4개 + 겹친 원 하나.
    (qx, qy, px, py, vx, vy) → (밀어낸 qx, qy, 밀었나, 접선 x, y, q 원 안). margin = 늑대 몸 여유(10-17, (c″)). 0 이면 10-16 칸 그대로다
    (뽑기 순서는 여유와 상관없이 같다 — 이전 위치는 반지름 r + 여유 + 0.01~1.5)."""
    w = World(load_v2_config(WILD).replace(N=4), seeds=[SEED + 9])
    w._zw_m = float(margin)                     # 설정 값(0.5) 대신 이 경우의 여유. 0 이면 10-16 그대로
    w.cov_c = np.array([[15.0, 15.0], [45.0, 15.0], [15.0, 45.0], [45.0, 45.0], [20.0, 15.0]])
    w.cov_r = np.array([6.0, 6.0, 6.0, 6.0, 3.0])
    rng = np.random.default_rng(SEED + 9)
    rows = []
    for i in range(n):
        k = int(rng.integers(0, len(w.cov_r)))
        ang = rng.uniform(0.0, 2.0 * np.pi)
        u = np.array([np.cos(ang), np.sin(ang)])
        p = w.cov_c[k] + (w.cov_r[k] + margin + rng.uniform(0.01, 1.5)) * u
        if w._rz_inside_disc(p[None, :])[0]:
            p = w.cov_c[k] + (w.cov_r[k] + margin + 3.2) * u
        v = rng.uniform(-1.0, 1.0, 2) * rng.uniform(0.2, 1.2)
        if i % 4 == 0:
            v = (w.cov_c[k] - p) / np.linalg.norm(w.cov_c[k] - p) * 0.9     # 중심 쪽으로 곧장
        q = p + v
        if i == 1:
            q = w.cov_c[0].copy()                                          # 중심과 겹침 → 이전 위치 쪽
        qp, pushed = w._rz_wall_push(q[None, :], p[None, :], np.array([True]))
        t = w._rz_wall_tangent(p[None, :], v[None, :])
        rows.append((q[0], q[1], p[0], p[1], v[0], v[1], qp[0, 0], qp[0, 1], float(pushed[0]), t[0, 0], t[0, 1],
                     float(w._rz_inside_disc(q[None, :])[0])))
    return w, rows


def build_header() -> str:
    w = make_world()
    wr = w._wr
    cases = reserve_cases(w)
    starve_t, starve = starve_chain(w)
    mixed = mixed_chain(w)
    ws_w, sat = satiation_chain()
    types = [int(t) for t in ws_w.pred_type]
    pw, scenes = perception_scenes()
    zv, zh = pw._zv, pw._zh
    fw, fsc, fout = flight_scenes()
    wf = fw._wf
    xw, xsc, xout, xhand = flight_fix_scenes()
    edges = edge_cases()
    sw, srows = shelter_cases(margin=0.0)
    margin = float(World(load_v2_config(WILD).replace(N=4), seeds=[SEED])._zw_m)   # 거울 설정 realism_shelter.wolf_margin
    _, mrows = shelter_cases(margin=margin)
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_wild.py (손으로 고치지 않는다). 세계 configs/v3_wild1_mirror.yaml, 시드 32090.",
        "// v3 야생 1단계 골든 (명세 Docs/RL_Policy/RL_V3_WILD1_SPEC.md 5절). 검사는 Tests/EcoWildV3Test.cpp (AdaptiveEcosystem.Policy.V3.Wild.*).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoWorldV3::GoldenWild",
        "{",
        "\t// (w1) wild_reserve 계수 (파이썬 World._wr) · 하루 스텝 · 대사 · 용량 C = reserve_days × dn_period × energy_drain",
        f"\tinline constexpr double kReserveDays = {d_lit(wr['reserve_days'])};",
        f"\tinline constexpr double kReserveInit = {d_lit(wr['init'])};",
        f"\tinline constexpr double kRefillE = {d_lit(wr['refill_e'])};",
        f"\tinline constexpr double kRefillFrac = {d_lit(wr['refill_frac'])};",
        f"\tinline constexpr double kWeakE = {d_lit(wr['weak_e'])};",
        f"\tinline constexpr double kWeakSpeed = {d_lit(wr['weak_speed'])};",
        f"\tinline constexpr std::int32_t kDayPeriod = {int(w.dn_period)};",
        f"\tinline constexpr double kEnergyDrain = {d_lit(w.cfg.energy_drain)};",
        f"\tinline constexpr double kInitEnergy = {d_lit(w.cfg.init_energy)};",
        f"\tinline constexpr double kMaxEnergy = {d_lit(w.cfg.max_energy)};",
        f"\tinline constexpr double kReserveCap = {d_lit(w._wr_cap)};",
        "",
        "\t// 비축 한 번: 행마다 e_new, 먹은 에너지, R → E, R",
        f"\tinline constexpr std::int32_t kReserveCaseCount = {len(cases)};",
        c_array("double", "kReserveCases", [v for c in cases for v in c], 5, d_lit),
        "",
        "\t// 굶음 열: 걷기 대사만, E 0.5·R 가득에서. 죽는 스텝과 (스텝, E, R) 표본 (100 스텝마다 + 죽는 스텝)",
        f"\tinline constexpr std::int32_t kStarveDeathStep = {starve_t};",
        f"\tinline constexpr std::int32_t kStarveSampleCount = {len(starve)};",
        c_array("std::int32_t", "kStarveSampleStep", [s[0] for s in starve], 12, str),
        c_array("double", "kStarveSampleE", [s[1] for s in starve], 6, d_lit),
        c_array("double", "kStarveSampleR", [s[2] for s in starve], 6, d_lit),
        "",
        "\t// 섞음 열: E 0.2·R 0.2 에서, 스텝 t 의 먹은 에너지 = 0.03 if (t / 50) % 3 == 0 else 0. 스텝마다 (E, R)",
        "\tinline constexpr double kMixedStartE = 0.2;",
        "\tinline constexpr double kMixedStartR = 0.2;",
        "\tinline constexpr double kMixedGain = 0.03;",
        f"\tinline constexpr std::int32_t kMixedSteps = {len(mixed)};",
        c_array("double", "kMixedER", [v for p in mixed for v in p], 6, d_lit),
        "",
        "	// (w2) wild_satiation: sat 스텝 = wild_days_to_steps(sat_days, dn_period), rest_speed, 먹기 쿨다운, 늑대 기본 속력",
        f"	inline constexpr double kSatDays = {d_lit(ws_w._ws['sat_days'])};",
        f"	inline constexpr double kRestSpeed = {d_lit(ws_w._ws['rest_speed'])};",
        f"	inline constexpr std::int32_t kSatSteps = {int(ws_w._ws_sat_steps)};",
        f"	inline constexpr std::int32_t kPredEatCd = {int(ws_w.cfg.pred_eat_cd)};",
        f"	inline constexpr double kPredBaseSpeed = {d_lit(ws_w.pred_speed[0])};   // 늑대 기본 속력 (단위/스텝, 0.6 × 0.8)",
        "	// 포만 열: 늑대 슬롯마다 종류 (0 추격형, 1 잠행형 — world.py PT_CHASER·PT_STALKER), 스텝마다 늑대마다 (쿨다운, 남은 배부름, 배부름 0/1, 변위 크기)",
        f"	inline constexpr std::int32_t kSatWolves = {len(types)};",
        c_array("std::int32_t", "kSatWolfType", types, 8, str),
        f"	inline constexpr std::int32_t kSatChainSteps = {len(sat)};",
        c_array("std::int32_t", "kSatChainInt", [v for r in sat for c in r for v in (c[0], c[1], int(c[2]))], 12, str),
        c_array("double", "kSatChainVel", [c[3] for r in sat for c in r], 6, d_lit),
        "",
        "	// R3 감지 realism_vision·realism_hearing (거울 세계 값). 위협 시야 문턱 cos = cos(radians(threat_fov_deg) × 0.5)",
        f"	inline constexpr double kThreatFovDeg = {d_lit(zv['threat_fov_deg'])};",
        f"	inline constexpr double kThreatFovCos = {d_lit(zv['threat_cos'])};",
        f"	inline constexpr double kKinFovDeg = {d_lit(zv['kin_fov_deg'])};",
        f"	inline constexpr double kHearSSilent = {d_lit(zh['s_silent'])};",
        f"	inline constexpr double kHearSQuiet = {d_lit(zh['s_quiet'])};",
        f"	inline constexpr double kHearSLoud = {d_lit(zh['s_loud'])};",
        f"	inline constexpr double kHearRQuiet = {d_lit(zh['r_quiet'])};",
        f"	inline constexpr double kHearRLoud = {d_lit(zh['r_loud'])};",
        f"	inline constexpr bool kHearRoamQuiet = {'true' if zh['roam_quiet'] else 'false'};",
        f"	inline constexpr bool kHearCapToSight = {'true' if zh['cap_to_sight'] else 'false'};",
        f"	inline constexpr double kSeeR = {d_lit(pw.cfg.see_r)};",
        "	// 지각 장면: 장면마다 사슴 kPercN 의 (x, y, hx, hy, 시야 배수), 늑대 kPercM 의 (x, y, vx, vy, 전력 걸음 0/1, 소리 반경),",
        "	// 사슴 × 늑대 알아챔 0/1 (사슴 행 순서), 사슴마다 (보이는 수, 가장 가까운 거리 — 없으면 −1)",
        f"	inline constexpr std::int32_t kPercScenes = {len(scenes)};",
        f"	inline constexpr std::int32_t kPercN = {pw.N};",
        f"	inline constexpr std::int32_t kPercM = {pw.M};",
        c_array("double", "kPercDeer", [v for sc in scenes for i in range(pw.N) for v in
                                        (sc['pos'][i, 0], sc['pos'][i, 1], sc['head'][i, 0], sc['head'][i, 1], sc['see'][i])], 5, d_lit),
        c_array("double", "kPercWolf", [v for sc in scenes for m in range(pw.M) for v in
                                        (sc['ppos'][m, 0], sc['ppos'][m, 1], sc['pvel'][m, 0], sc['pvel'][m, 1],
                                         float(sc['run'][m]), sc['hr'][m])], 6, d_lit),
        c_array("std::int32_t", "kPercVis", [int(v) for sc in scenes for v in sc['pvis'].reshape(-1)], 16, str),
        c_array("std::int32_t", "kPercCount", [int(v) for sc in scenes for v in sc['count']], 16, str),
        c_array("double", "kPercDMin", [v for sc in scenes for v in sc['dmin']], 6, d_lit),
        "",
        "\t// (w3) wild_flight 계수 (단위)",
        f"\tinline constexpr double kFlightAlertR = {d_lit(wf['alert_r'])};",
        f"\tinline constexpr double kFlightFlightR = {d_lit(wf['flight_r'])};",
        f"\tinline constexpr double kFlightSafeR = {d_lit(wf['safe_r'])};",
        f"\tinline constexpr double kFlightApproach = {d_lit(wf['approach'])};",
        f"\tinline constexpr double kFlightAlertW = {d_lit(wf['alert_w'])};",
        f"\tinline constexpr bool kFlightRestAlert = {str(bool(wf['rest_alert'])).lower()};",
        f"\tinline constexpr double kFlightShelterCos = {d_lit(wf['shelter_cos'])};",
        f"\tinline constexpr double kFlightShelterR = {d_lit(wf['shelter_r'])};",
        f"\tinline constexpr bool kFlightCrouch = {str(bool(wf['crouch'])).lower()};",
        f"\tinline constexpr double kFlightWallMargin = {d_lit(wf['wall_margin'])};",
        f"\tinline constexpr double kFlightWorldSize = {d_lit(fw.size)};",
        "\t// 도주 장면: 장면마다 사슴 kFlightN 의 입력 (x, y, hx, hy, 시야 배수, 지난 덮기, 잠금)·출력 (다음 덮기, 방향 x, y, 잠금),",
        "\t// 늑대 kFlightM 의 (x, y, vx, vy, 전력 걸음, 쿨다운, 배부름, 표적), 은신처 kFlightCovers 개 (x, y, r — 없으면 r < 0). 앞 kFlightHandScenes 개는 손 장면",
        f"\tinline constexpr std::int32_t kFlightScenes = {len(fsc)};",
        "\tinline constexpr std::int32_t kFlightHandScenes = 12;",
        f"\tinline constexpr std::int32_t kFlightN = {fw.N};",
        f"\tinline constexpr std::int32_t kFlightM = {fw.M};",
        "\tinline constexpr std::int32_t kFlightCovers = 2;",
        c_array("double", "kFlightDeerIn", [v for sc in fsc for i in range(fw.N) for v in
                                            (sc['pos'][i, 0], sc['pos'][i, 1], sc['head'][i, 0], sc['head'][i, 1], sc['see'][i],
                                             float(sc['prev'][i]), float(sc['lock'][i]))], 7, d_lit),
        c_array("double", "kFlightDeerOut", [v for o in fout for i in range(fw.N) for v in
                                             (float(o['mode'][i]), o['dir'][i, 0], o['dir'][i, 1], float(o['lock'][i]))], 4, d_lit),
        c_array("double", "kFlightWolf", [v for sc in fsc for m in range(fw.M) for v in
                                          (sc['ppos'][m, 0], sc['ppos'][m, 1], sc['pvel'][m, 0], sc['pvel'][m, 1], float(sc['run'][m]),
                                           float(sc['cd'][m]), float(sc['sat'][m]), float(sc['target'][m]))], 8, d_lit),
        c_array("double", "kFlightCover", [v for sc in fsc for k in range(2) for v in
                                           (sc['covers'][k] if k < len(sc['covers']) else (0.0, 0.0, -1.0))], 6, d_lit),
        "",
        "\t// ---- 10-16 고침 (명세 11절): 설정 값 hold_awake·edge_r 의 도주 장면, 가장자리 굽히기, 은신처 진입 금지 ----",
        f"\tinline constexpr bool kFixHoldAwake = {str(bool(xw._wf['hold_awake'])).lower()};",
        f"\tinline constexpr double kFixEdgeR = {d_lit(xw._wf['edge_r'])};",
        "\t// 고친 도주 장면: 위 도주 장면과 같은 칸. 앞 kFlightScenes 개 = 10-15 장면(입력 같음), 그 뒤 고침 손 장면 (kFixHandScenes 까지), 그 뒤 난수 장면",
        f"\tinline constexpr std::int32_t kFixScenes = {len(xsc)};",
        f"\tinline constexpr std::int32_t kFixHandScenes = {xhand};",
        c_array("double", "kFixDeerIn", [v for sc in xsc for i in range(xw.N) for v in
                                         (sc['pos'][i, 0], sc['pos'][i, 1], sc['head'][i, 0], sc['head'][i, 1], sc['see'][i],
                                          float(sc['prev'][i]), float(sc['lock'][i]))], 7, d_lit),
        c_array("double", "kFixDeerOut", [v for o in xout for i in range(xw.N) for v in
                                          (float(o['mode'][i]), o['dir'][i, 0], o['dir'][i, 1], float(o['lock'][i]))], 4, d_lit),
        c_array("double", "kFixWolf", [v for sc in xsc for m in range(xw.M) for v in
                                       (sc['ppos'][m, 0], sc['ppos'][m, 1], sc['pvel'][m, 0], sc['pvel'][m, 1], float(sc['run'][m]),
                                        float(sc['cd'][m]), float(sc['sat'][m]), float(sc['target'][m]))], 8, d_lit),
        c_array("double", "kFixCover", [v for sc in xsc for k in range(2) for v in
                                        (sc['covers'][k] if k < len(sc['covers']) else (0.0, 0.0, -1.0))], 6, d_lit),
        "\t// 가장자리 굽히기 wf_edge_steer (무대 60, edge_r kFixEdgeR): (x, y, dx, dy, 나온 x, y)",
        f"\tinline constexpr std::int32_t kEdgeCases = {len(edges)};",
        c_array("double", "kEdgeCase", [v for r in edges for v in r], 6, d_lit),
        "\t// 은신처 진입 금지: 원 (x, y, r) × kShelterDiscCount, 경우 (qx, qy, px, py, vx, vy, 밀어낸 x, y, 밀었나, 접선 x, y, q 원 안)",
        f"\tinline constexpr std::int32_t kShelterDiscCount = {len(sw.cov_r)};",
        f"\tinline constexpr double kShelterWorldSize = {d_lit(sw.size)};",
        c_array("double", "kShelterDisc", [v for c, r in zip(sw.cov_c, sw.cov_r) for v in (c[0], c[1], r)], 6, d_lit),
        f"\tinline constexpr std::int32_t kShelterCases = {len(srows)};",
        c_array("double", "kShelterCase", [v for r in srows for v in r], 6, d_lit),
        "",
        "\t// ---- 10-17 늑대 몸 여유 (world.py (c″), 거울 설정 realism_shelter.wolf_margin) ----",
        "\t// 같은 원·같은 칸. C++ 은 반지름 + kShelterWolfMargin 인 원 목록으로 부른다 (통합 모드 FWorldConfig::ShelterWolfMargin 과 같은 꼴)",
        f"\tinline constexpr double kShelterWolfMargin = {d_lit(margin)};",
        f"\tinline constexpr std::int32_t kShelterMarginCases = {len(mrows)};",
        c_array("double", "kShelterMarginCase", [v for r in mrows for v in r], 6, d_lit),
        "}",
        "",
    ]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "WildGoldenVectorsV3.h"
    path.write_text(build_header(), encoding="utf-8", newline="\n")
    print(f"썼다: {path}")


if __name__ == "__main__":
    main()

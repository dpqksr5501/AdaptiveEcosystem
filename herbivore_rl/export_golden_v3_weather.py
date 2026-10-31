"""v3 야생 3단계 골든 내보내기 — 지역 날씨(wild_weather)를 언리얼 C++ 와 대조할 골든 헤더를 만든다 (명세 `Docs/RL_Policy/RL_V3_WILD2_SPEC.md` 11절).
C++ 쪽: EcoWorldV3.h `WeatherAt`·`WeatherMults`·`UpdateDayNight`·`SeePredNow`·`ObsVisibilityMult`·`WolfViewNow`·`BuildThreatInputs` 발소리 줄,
EcoThreatModel.h `Step` 의 `WeatherViewMult`·`WeatherSpeedMult`(무리 미리 보기 `PackPeek` 포함).

    # herbivore_rl/ 에서. 언리얼 모듈 폴더(AI/Policy)에 바로 쓴다
    python export_golden_v3_weather.py
    # 시험용 다른 폴더
    python export_golden_v3_weather.py --out <폴더>

세계·시드: configs/v3_wild3_mirror.yaml 에서 세로 장애물만 끈 세계(날씨만 따로 본다 — 원판·돌아가기는 장애물·돌아가기 골든이 본다). 사슴 16(지각)·24(한 스텝).
이 내보내기 전용 탐색 시드 32098(배수 난수·지각 장면)·32099(한 스텝 장면). 판정 시드는 쓰지 않는다.

묶음:
  설정     거울 설정 wild_weather 계수(세기 1 배수 여섯·obs_visibility)와 지역 표(Barren 맑음 0·Forest 비 1·Highland 눈 1), 탐지 반경 see_r·늑대 시야 pred_view_r·
           detect_night. C++ FWeatherConfig 기본값·kRegionWeatherDefaults·관측·위협 설정 기본값과 같아야 한다.
  배수     (계수 여섯, 날씨, 세기) → `weather_mults` 의 (시야, 사슴 청각, 사슴 이동, 위협 이동). 거울 계수 × (맑음 0, 비·눈 × 세기 9) + 난수 계수 24 사례.
  시간표   시간표(숲: 0 비 0.5 · 100 맑음 · 250 눈 1 · 900 비 1, 고지: 50 눈 0.3)를 둔 세계 셋(숲·고지·메마른 땅 — 표 없는 지역은 고정 날씨)에서 세계 t 마다
           `weather_at` → (날씨, 세기).
  낮밤     거울 세계(지역 셋 × obs_visibility 켬·끔)에 t 를 넣고 `_daynight_update` → 어둠 d·탐지 반경 `_see_pred`·관측 visibility `_vis`·늑대 시야 `_wx_view`·
           날씨·세기·배수 넷. C++ 은 InitWorld(같은 낮밤·날씨) → T = t → UpdateDayNight 로 같은 값을 내야 한다.
  지각     거울 세계(지역 셋 × 낮 225·밤 675, 장면 18)에 t 를 넣어 날씨·어둠을 정한 뒤 장면 상태(사슴 자리·heading·시야 배수, 늑대 자리·지난 변위·전력 걸음·잠)를
           넣고 `_geometry`. 늑대마다 소리 반경(hearing_radius × 사슴 청각 — C++ BuildThreatInputs 와 같은 값), 사슴 × 늑대 알아챔(wf_pvis), 사슴마다 보이는 수·가장
           가까운 거리(없으면 −1).
  한 스텝  거울 세계(늑대 4 = 순번 짝수 잠행·홀수 추격, 무리·은신처 안전·몸 여유·포만·제자리 식사)를 날씨 넷(숲 비 1·고지 눈 1·고지 눈 0.5·메마른 땅 맑음)으로
           만들고, 장면마다 낮(t 225 → d = 0)의 날씨를 `_daynight_update` 로 정한 뒤 상태를 넣어 `World._step_predators_v3` 를 한 번 부른다
           (export_golden_v3_pack.py 한 스텝 장면과 같은 상태 넣기). C++ 은 PackPeek → PackGoals → Step 을 늑대 순서로, In.WeatherViewMult·WeatherSpeedMult =
           그 날씨 배수로 불러 같은 값을 내야 한다.
"""

from __future__ import annotations

import argparse
import copy
import math
from pathlib import Path

import numpy as np

from env_v2 import repertoire as rep
from env_v2.config import load_v2_config
from env_v2.world import (PT_CHASER, PT_STALKER, ST_EXHAUST, ST_POUNCE, ST_ROAM, WX_CLEAR, WX_RAIN, WX_SNOW, World, hearing_radius, weather_at,
                          weather_mults)

import export_golden_v3_pack as gpack

HERE = Path(__file__).resolve().parent
WILD3 = HERE / "configs" / "v3_wild3_mirror.yaml"
DEFAULT_OUT = HERE.parent / "AdaptiveEcosystem" / "Source" / "AdaptiveEcosystem" / "AI" / "Policy"
SEED_CASE = 32098
SEED_STEP = 32099
N_PERC = 16
N_STEP = 24
M1_KEYS = ("rain_sight", "rain_hear", "snow_sight", "snow_hear", "snow_deer_speed", "snow_wolf_speed")
REGIONS = ("Barren", "Forest", "Highland")
MULT_I = (0.0, 0.1, 0.25, 0.3, 0.5, 0.7, 0.75, 0.9, 1.0)
MULT_RANDOM = 24
SCHEDULE = {"Forest": [[0, "rain", 0.5], [100, "clear", 0.0], [250, "snow", 1.0], [900, "rain", 1.0]], "Highland": [[50, "snow", 0.3]]}
SCHEDULE_T = (0, 1, 49, 50, 51, 99, 100, 101, 249, 250, 251, 899, 900, 901, 5000)
DAYNIGHT_T = (0, 10, 44, 45, 46, 100, 225, 400, 449, 450, 451, 470, 495, 600, 675, 899, 900, 1350, 1817)
PERC_T = (225, 675)                 # 낮 한가운데(d = 0)·밤 한가운데(d = 1) — 낮밤 900, 박명 45, day_offset 0
PERC_PER = 3                        # 지역·낮밤마다 장면 수
NOON = 225
STEP_SCENES = 80
STEP_WEATHER = (("Forest", None), ("Highland", None), ("Highland", ["snow", 0.5]), ("Barren", None))

d_lit = gpack.d_lit
c_array = gpack.c_array


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def base_cfg(n: int, **wx):
    """거울 설정에서 세로 장애물만 끈 설정 (날씨 블록은 wx 로 덮는다)."""
    cfg = load_v2_config(WILD3).replace(N=n)
    return _with(cfg, obstacles={"enabled": False}, wild_weather=wx)


def world(n: int, seed: int, **wx) -> World:
    w = World(base_cfg(n, **wx), seeds=[seed])
    w.reset()
    if w._wx is None or w._ob is not None:
        raise SystemExit("골든 세계는 wild_weather 켬·obstacles 끔이어야 한다")
    return w


def mirror_weather() -> dict:
    return dict(load_v2_config(WILD3).v2["features"]["wild_weather"])


# --------------------------------------------------------------------- #
# 배수·시간표·낮밤
# --------------------------------------------------------------------- #


def mult_cases(m1: dict):
    """(계수 여섯, 날씨, 세기) 사례와 weather_mults 결과."""
    cases = [(tuple(m1[k] for k in M1_KEYS), WX_CLEAR, 0.0)]
    for kind in (WX_RAIN, WX_SNOW):
        cases += [(tuple(m1[k] for k in M1_KEYS), kind, i) for i in MULT_I]
    rng = np.random.default_rng(SEED_CASE)
    for _ in range(MULT_RANDOM):
        m = tuple(float(v) for v in rng.uniform(0.05, 1.0, len(M1_KEYS)))
        kind = int(rng.choice([WX_RAIN, WX_SNOW]))
        cases.append((m, kind, float(rng.uniform(0.0, 1.0))))
    out = []
    for m, kind, i in cases:
        wx = dict(m1=dict(zip(M1_KEYS, m)))
        out.append((m, kind, i, weather_mults(wx, kind, i)))
    return out


def schedule_cases():
    """지역 셋 세계의 (고정 날씨, 시간표 줄, t → (날씨, 세기))."""
    out = []
    for r in REGIONS:
        w = world(4, SEED_CASE, region=r, schedule=SCHEDULE)
        const = w._wx["const"]
        rows = [] if r not in SCHEDULE else [(int(s), k, float(i)) for s, (k, i) in zip(w._wx["schedule"][0], w._wx["schedule"][1])]
        got = [weather_at(w._wx, t) for t in SCHEDULE_T]
        out.append(dict(region=r, const=const, rows=rows, got=got))
    return out


def daynight_cases():
    """지역 셋 × obs_visibility 켬·끔 세계에 t 를 넣은 _daynight_update 결과."""
    out = []
    for r in REGIONS:
        for vis in (True, False):
            w = world(4, SEED_CASE, region=r, obs_visibility=vis)
            for t in DAYNIGHT_T:
                w.t = int(t)
                w._daynight_update()
                out.append(dict(region=r, vis_on=vis, t=int(t), const=w._wx["const"], dark=float(w.dark), see=float(w._see_pred),
                                vis=float(w._vis), view=float(w._wx_view), kind=int(w.weather_kind), inten=float(w.weather_intensity),
                                mults=(float(w._wx_sight), float(w._wx_hear), float(w._wx_deer), float(w._wx_wolf))))
    return out, (int(w.dn_period), int(w.dn_offset), int(w.dn_tw))


# --------------------------------------------------------------------- #
# 지각 장면
# --------------------------------------------------------------------- #


def perception_scenes():
    """모듈 docstring '지각'. 지역 셋 × 낮밤 둘 × PERC_PER 장면."""
    rng = np.random.default_rng([SEED_CASE, 1])    # 배수 난수(SEED_CASE)와 다른 갈래
    scenes = []
    for r in REGIONS:
        w = world(N_PERC, SEED_CASE, region=r)
        w.keep_pair_vis = True
        for t in PERC_T:
            for _ in range(PERC_PER):
                w.t = int(t)
                w._daynight_update()           # 날씨·어둠·탐지 반경(결정 때 값)
                w.pred_pos[:] = rng.uniform(20.0, 40.0, (w.M, 2))
                w.pos[:] = w.pred_pos[0] + rng.uniform(-30.0, 30.0, (w.N, 2))
                a = rng.uniform(0.0, 2.0 * np.pi, w.N)
                w.head[:] = np.stack([np.cos(a), np.sin(a)], 1)
                sp = rng.uniform(0.0, 0.75, w.M)
                b = rng.uniform(0.0, 2.0 * np.pi, w.M)
                w.pred_vel[:] = np.stack([sp * np.cos(b), sp * np.sin(b)], 1)
                w.pred_running[:] = rng.random(w.M) < 0.5
                w.pred_asleep[:] = rng.random(w.M) < 0.2
                w._rep_see[:] = rng.choice([1.0, 0.6, 0.3], w.N)
                g = w._geometry()
                hr = hearing_radius(w._zh, np.sqrt((w.pred_vel * w.pred_vel).sum(1)) / w.cfg.herb_speed, w.pred_running)
                if w._wx_hear != 1.0:
                    hr = hr * w._wx_hear       # world.py _geometry 의 r_snd × w_h 와 같은 값
                dmin = np.where(np.isfinite(g["d_pred_min"]), g["d_pred_min"], -1.0)
                scenes.append(dict(region=r, t=int(t), dark=float(w.dark), see=float(w._see_pred), pos=w.pos.copy(), head=w.head.copy(),
                                   rsee=w._rep_see.copy(), ppos=w.pred_pos.copy(), pvel=w.pred_vel.copy(), run=w.pred_running.copy(),
                                   asleep=w.pred_asleep.copy(), hr=np.asarray(hr, dtype=np.float64), pvis=g["wf_pvis"].copy(),
                                   count=g["pred_count"].copy(), dmin=dmin))
    return scenes, w


# --------------------------------------------------------------------- #
# 한 스텝 장면 (export_golden_v3_pack.py 와 같은 상태 넣기)
# --------------------------------------------------------------------- #


def step_worlds():
    ws = []
    for r, override in STEP_WEATHER:
        wx = dict(region=r)
        if override is not None:
            regs = dict(mirror_weather()["regions"])
            regs[r] = override
            wx["regions"] = regs
        w = world(N_STEP, SEED_STEP, **wx)
        if w._wp is None or w.M != 4 or w.alive is None or w._rp is None or w._zs is None or not w._zw or w._ws is None or not w._eat_in_place:
            raise SystemExit("한 스텝 장면 세계는 늑대 4·무리·부활 없음·행동 레퍼토리·은신처 안전·진입 금지·포만·제자리 식사를 켠 세계여야 한다")
        if w._zc is not None or w._sd is not None or w._zt is not None or w._pred_ranged_v1.any():
            raise SystemExit("한 스텝 장면은 추격 고정·노려보기·지형·원거리형이 없어야 한다(C++ 위협 모델에 없다)")
        ws.append(w)
    return ws


def step_scenes():
    ws = step_worlds()
    rng = np.random.default_rng(SEED_STEP)
    w0 = ws[0]
    S, M, N = w0.size, w0.M, w0.N
    rp = w0._rp
    out = []
    for s in range(STEP_SCENES):
        wi = s % len(ws)
        w = ws[wi]
        q = np.zeros((M, 2))
        for m in range(M):
            for _ in range(200):
                c = rng.uniform(0.0, S, 2)
                if not w._rz_inside_disc(c[None, :])[0]:
                    break
            q[m] = c
        ang = rng.uniform(0, 2 * np.pi, M)
        head = np.stack([np.cos(ang), np.sin(ang)], 1)
        cd = np.zeros(M, dtype=np.int64)
        sat = np.zeros(M, dtype=np.int64)
        st = np.full(M, ST_ROAM, dtype=np.int8)
        left = np.zeros(M, dtype=np.int64)
        for m in range(M):
            u = rng.random()
            if u < 0.12:
                cd[m] = int(rng.integers(1, 39))
            elif u < 0.22:
                sat[m] = int(rng.integers(1, 451))
            elif u < 0.32 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_POUNCE, int(rng.integers(0, 13))
            elif u < 0.36 and w.pred_type[m] == PT_STALKER:
                st[m], left[m] = ST_EXHAUST, int(rng.integers(1, 31))
        # 사슴: 늑대 앞 시야 경계(14 단위) 둘레에 몇 마리 — 날씨 시야(× 0.9·0.7)가 표적을 바꾸는 장면이 생기게
        p = rng.uniform(0.0, S, (N, 2))
        for i in range(min(8, N)):
            m = int(rng.integers(0, M))
            p[i] = np.clip(q[m] + head[m] * rng.uniform(4.0, 16.0) + rng.normal(0.0, 2.0, 2), 0.0, S)
        mv = rng.normal(0.0, 1.0, (N, 2))
        mv = mv / np.maximum(np.linalg.norm(mv, axis=1, keepdims=True), 1e-9) * rng.choice([0.0, 0.24, 0.6], (N, 1), p=[0.2, 0.3, 0.5])

        def put(wd, q_):
            wd.t = NOON
            wd._daynight_update()              # 낮(d = 0)의 날씨·배수 — 아래 칸이 밤잠·어둠을 덮는다
            wd.pos = p.copy()
            wd._pack_p0 = p - mv
            wd._rs.behavior[:] = rep.GRAZE
            wd._rep_still = np.zeros(N, dtype=bool)
            wd._rep_cover = rep.cover_mult(rp, wd._rs.behavior, np.zeros(N, dtype=bool))
            wd.alive = np.ones(N, dtype=bool)
            wd.pred_pos, wd.pred_head = q_.copy(), head.copy()
            wd.pred_cd, wd.pred_sat = cd.copy(), sat.copy()
            wd.stalk_state, wd.stalk_left = st.copy(), left.copy()
            wd.pred_asleep = np.zeros(M, dtype=bool)
            wd._pred_speed_mult = np.ones(M)
            wd.dark = 0.0
            wd._zn_hunt = np.zeros(M, dtype=bool)
            wd._hunt_on = np.zeros(M, dtype=bool)

        if rng.random() < 0.4:
            wa = copy.deepcopy(w)
            put(wa, q)
            wa._step_predators_v3()
            hs = np.flatnonzero(wa.pack_help)
            if len(hs):
                m = int(hs[0])
                i = int(wa.pack_prey[m])
                sc = dict(p=p, disp=mv, cov=np.c_[w.cov_c, w.cov_r], wp=w._wp, margin=w._zw_m, size=S)
                goal = gpack._goal_point(sc, m, i)
                q = q.copy()
                q[m] = np.clip(goal + rng.uniform(-0.3, 0.3, 2), 0.0, S)
        put(w, q)
        in_cov = w._in_cover(w.pos)
        turns = copy.deepcopy(w.rng).uniform(-w.cfg.pred_wander_turn, w.cfg.pred_wander_turn, M)
        caught = w._step_predators_v3()
        k = np.full(M, -1, dtype=np.int64)
        got = w.pred_cd == int(w.cfg.pred_eat_cd)
        for m in np.flatnonzero(got):
            d = np.sqrt(((w.pos - q[m]) ** 2).sum(1)) * np.where(in_cov, w._rep_cover, 1.0)
            d = np.where(caught & ~in_cov, d, np.inf)
            k[m] = int(np.argmin(d))
        out.append(dict(kind=int(w.weather_kind), inten=float(w.weather_intensity), view=float(w._wx_view), wolf=float(w._wx_wolf),
                        q=q, head=head, cd=cd, sat=sat, st=st, left=left, p=p, mv=w.pos - w._pack_p0, in_cov=in_cov, turns=turns,
                        q1=w.pred_pos.copy(), head1=w.pred_head.copy(), cd1=w.pred_cd.copy(), sat1=w.pred_sat.copy(),
                        st1=w.stalk_state.copy(), left1=w.stalk_left.copy(), help=w.pack_help.copy(), wait=w.pack_wait.copy(),
                        door=w.pack_door.copy(), prey=w.pack_prey.copy(), target=w.pred_target.copy(), caught=k))
    for w in ws[1:]:
        if not (np.array_equal(w.cov_c, w0.cov_c) and np.array_equal(w.cov_r, w0.cov_r) and np.array_equal(w.pred_type, w0.pred_type)):
            raise SystemExit("날씨만 다른 세계들의 은신처·늑대 구성이 다르다")
    consts = dict(size=S, kinds=w0.pred_type.copy(), cov=np.c_[w0.cov_c, w0.cov_r], margin=w0._zw_m, eat_cd=int(w0.cfg.pred_eat_cd),
                  sat_steps=int(w0._ws_sat_steps), M=M, N=N, pred_speed_mult=float(w0.pred_speed_mult))
    return out, consts


# --------------------------------------------------------------------- #
# 헤더
# --------------------------------------------------------------------- #


def build_header() -> str:
    wx0 = mirror_weather()
    m1 = {k: float(wx0[k]) for k in M1_KEYS}
    probe = world(4, SEED_CASE)
    regions = {r: tuple(wx0["regions"][r]) for r in REGIONS}
    L = [
        "// 자동 생성 — herbivore_rl/export_golden_v3_weather.py (손으로 고치지 않는다). 세계 configs/v3_wild3_mirror.yaml (세로 장애물 끔), 시드 32098·32099.",
        "// v3 야생 3단계 지역 날씨 골든 (명세 Docs/RL_Policy/RL_V3_WILD2_SPEC.md 11절). 검사는 Tests/WeatherGoldenCheckV3.h (UE 시험 AdaptiveEcosystem.Policy.V3.Weather.*,",
        "// g++ 하네스 herbivore_rl/tests/cpp/weather_v3_main.cpp).",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace EcoWorldV3::GoldenWeather",
        "{",
        "\t// ---- 설정: 거울 wild_weather 계수 (C++ FWeatherConfig 기본값과 같아야 한다), 지역 표 (kRegionWeatherDefaults 와 같아야 한다) ----",
    ]
    for k in M1_KEYS:
        L.append(f"\tinline constexpr double kCfg_{k} = {d_lit(m1[k])};")
    L.append(f"\tinline constexpr bool kCfgObsVisibility = {'true' if wx0['obs_visibility'] else 'false'};")
    L.append(f"\tinline constexpr bool kCfgScheduleNone = {'true' if wx0.get('schedule') is None else 'false'};")
    L.append(f"\tinline constexpr std::int32_t kRegions = {len(REGIONS)};")
    L.append("\tinline constexpr const char* kRegionNames[" + str(len(REGIONS)) + "] = {" + ", ".join(f'"{r}"' for r in REGIONS) + "};")
    names = ("clear", "rain", "snow")
    L.append(c_array("std::int32_t", "kRegionKind", [names.index(regions[r][0]) for r in REGIONS], 3, str))
    L.append(c_array("double", "kRegionIntensity", [float(regions[r][1]) for r in REGIONS], 3, d_lit))
    L.append(f"\tinline constexpr double kSeeR = {d_lit(probe.cfg.see_r)};")
    L.append(f"\tinline constexpr double kPredViewR = {d_lit(probe.cfg.pred_view_r)};")
    L.append(f"\tinline constexpr double kDetectNight = {d_lit(probe._dn['detect_night'])};")

    # 배수
    mc = mult_cases(m1)
    L += ["", "\t// ---- 배수 (world.py weather_mults): 사례 c 의 kMultIn[8c..] = (계수 여섯, 날씨, 세기), kMultOut[4c..] = (시야, 사슴 청각, 사슴 이동, 위협 이동) ----",
          f"\tinline constexpr std::int32_t kMultCases = {len(mc)};",
          c_array("double", "kMultIn", [v for m, kind, i, _ in mc for v in (*m, float(kind), i)], 8, d_lit),
          c_array("double", "kMultOut", [v for *_, o in mc for v in o], 4, d_lit)]

    # 시간표
    sc = schedule_cases()
    rows = [(si, *row) for si, c in enumerate(sc) for row in c["rows"]]
    L += ["", "\t// ---- 시간표 (world.py weather_at): 세계 s (지역 kRegionNames[s]) 의 고정 날씨 kSchedConst[2s..] = (날씨, 세기), 줄 (세계, 시작 스텝, 날씨, 세기).",
          "\t//      kSchedT 마다 kSchedOut[2·(s·T + j)..] = (날씨, 세기) ----",
          f"\tinline constexpr std::int32_t kSchedWorlds = {len(sc)};",
          c_array("double", "kSchedConst", [v for c in sc for v in (float(c["const"][0]), float(c["const"][1]))], 2, d_lit),
          f"\tinline constexpr std::int32_t kSchedRows = {len(rows)};",
          c_array("double", "kSchedRow", [float(v) for r in rows for v in r], 4, d_lit),
          f"\tinline constexpr std::int32_t kSchedTimes = {len(SCHEDULE_T)};",
          c_array("std::int64_t", "kSchedT", list(SCHEDULE_T), 15, str),
          c_array("double", "kSchedOut", [float(v) for c in sc for kv in c["got"] for v in kv], 2, d_lit)]

    # 낮밤
    dn, (period, offset, tw) = daynight_cases()
    L += ["", f"\t// ---- 낮밤 (world.py _daynight_update, 낮밤 {period}·어긋남 {offset}·박명 {tw}): 사례 c 의 kDnIn[5c..] = (지역 번호, obs_visibility 0/1, t, 고정 날씨, 세기),",
          "\t//      kDnOut[10c..] = (어둠 d, 탐지 반경, visibility, 늑대 시야, 날씨, 세기, 시야, 사슴 청각, 사슴 이동, 위협 이동) ----",
          f"\tinline constexpr std::int32_t kDnPeriod = {period};",
          f"\tinline constexpr std::int32_t kDnOffset = {offset};",
          f"\tinline constexpr std::int32_t kDnTwilight = {tw};",
          f"\tinline constexpr std::int32_t kDnCases = {len(dn)};",
          c_array("double", "kDnIn", [v for c in dn for v in (float(REGIONS.index(c["region"])), float(c["vis_on"]), float(c["t"]),
                                                             float(c["const"][0]), float(c["const"][1]))], 5, d_lit),
          c_array("double", "kDnOut", [v for c in dn for v in (c["dark"], c["see"], c["vis"], c["view"], float(c["kind"]), c["inten"], *c["mults"])], 5, d_lit)]

    # 지각
    ps, pw = perception_scenes()
    zh = pw._zh
    L += ["", "\t// ---- 지각 (world.py _geometry): 장면 k 의 kPercScene[4k..] = (지역 번호, t, 어둠 d, 탐지 반경 _see_pred), 사슴 kPercN 의 (x, y, hx, hy, 시야 배수),",
          "\t//      늑대 kPercM 의 (x, y, vx, vy, 전력 걸음 0/1, 잠 0/1, 소리 반경 × 사슴 청각), 사슴 × 늑대 알아챔 0/1, 사슴마다 (보이는 수, 가장 가까운 거리 — 없으면 −1).",
          "\t//      R3 감지 계수는 거울 세계 값 (C++ FHearingConfig 기본값·위협 시야 300°) ----",
          f"\tinline constexpr double kThreatFovCos = {d_lit(pw._zv['threat_cos'])};",
          f"\tinline constexpr double kHerbSpeed = {d_lit(pw.cfg.herb_speed)};",
          f"\tinline constexpr double kHearRQuiet = {d_lit(zh['r_quiet'])};",
          f"\tinline constexpr double kHearRLoud = {d_lit(zh['r_loud'])};",
          f"\tinline constexpr bool kHearCapToSight = {'true' if zh['cap_to_sight'] else 'false'};",
          f"\tinline constexpr std::int32_t kPercScenes = {len(ps)};",
          f"\tinline constexpr std::int32_t kPercN = {pw.N};",
          f"\tinline constexpr std::int32_t kPercM = {pw.M};",
          c_array("double", "kPercScene", [v for s in ps for v in (float(REGIONS.index(s["region"])), float(s["t"]), s["dark"], s["see"])], 4, d_lit),
          c_array("double", "kPercDeer", [v for s in ps for i in range(pw.N) for v in
                                          (s["pos"][i, 0], s["pos"][i, 1], s["head"][i, 0], s["head"][i, 1], s["rsee"][i])], 5, d_lit),
          c_array("double", "kPercWolf", [v for s in ps for m in range(pw.M) for v in
                                          (s["ppos"][m, 0], s["ppos"][m, 1], s["pvel"][m, 0], s["pvel"][m, 1], float(s["run"][m]),
                                           float(s["asleep"][m]), s["hr"][m])], 7, d_lit),
          c_array("std::int32_t", "kPercVis", [int(v) for s in ps for v in s["pvis"].reshape(-1)], 16, str),
          c_array("std::int32_t", "kPercCount", [int(v) for s in ps for v in s["count"]], 16, str),
          c_array("double", "kPercDMin", [v for s in ps for v in s["dmin"]], 6, d_lit)]
    seen = int(sum(int(s["pvis"].sum()) for s in ps))
    L.append(f"\tinline constexpr std::int32_t kPercSeen = {seen};")

    # 한 스텝
    steps, c = step_scenes()
    M, N = c["M"], c["N"]
    kinds = [int(x) for x in c["kinds"]]
    if kinds != [PT_STALKER, PT_CHASER, PT_STALKER, PT_CHASER]:
        raise SystemExit(f"늑대 구성이 잠행·추격 번갈아가 아니다: {kinds}")
    in_d, in_i, prey_s, out_sd, out_si, wx_s = [], [], [], [], [], []
    catches = targets = 0
    for t in steps:
        wx_s += [float(t["kind"]), t["inten"], t["view"], t["wolf"]]
        for m in range(M):
            in_d += [t["q"][m, 0], t["q"][m, 1], t["head"][m, 0], t["head"][m, 1], t["turns"][m]]
            in_i += [int(t["cd"][m]), int(t["sat"][m]), int(t["st"][m]), int(t["left"][m])]
            out_sd += [t["q1"][m, 0], t["q1"][m, 1], t["head1"][m, 0], t["head1"][m, 1]]
            out_si += [int(t["cd1"][m]), int(t["sat1"][m]), int(t["st1"][m]), int(t["left1"][m]), int(t["help"][m]), int(t["wait"][m]),
                       int(t["door"][m]), int(t["prey"][m]), int(t["target"][m]), int(t["caught"][m])]
            catches += int(t["caught"][m] >= 0)
            targets += int(t["target"][m] >= 0)
        for i in range(N):
            prey_s += [t["p"][i, 0], t["p"][i, 1], t["mv"][i, 0], t["mv"][i, 1], float(t["in_cov"][i])]
    L += ["", "\t// ---- 한 스텝 (world.py _step_predators_v3, 늑대 4 = 순번 짝수 잠행·홀수 추격, 사슴 모두 먹기, 낮 d = 0) ----",
          "\t// 장면 s 의 날씨 kStepWeather[4s..] = (날씨, 세기, 늑대 시야 _wx_view, 위협 이동 _wx_wolf). 나머지 칸은 PackGoldenVectorsV3.h 한 스텝 장면과 같은 꼴",
          f"\tinline constexpr std::int32_t kStepScenes = {len(steps)};",
          f"\tinline constexpr std::int32_t kStepWolves = {M};",
          f"\tinline constexpr std::int32_t kStepPrey = {N};",
          f"\tinline constexpr double kStepWorldSize = {d_lit(c['size'])};",
          f"\tinline constexpr double kStepPredSpeedMult = {d_lit(c['pred_speed_mult'])};",
          f"\tinline constexpr double kStepWolfMargin = {d_lit(c['margin'])};",
          f"\tinline constexpr std::int32_t kStepEatCd = {c['eat_cd']};",
          f"\tinline constexpr std::int32_t kStepSatSteps = {c['sat_steps']};",
          f"\tinline constexpr std::int32_t kStepCatches = {catches};",
          f"\tinline constexpr std::int32_t kStepTargets = {targets};",
          f"\tinline constexpr std::int32_t kStepCoverCount = {len(c['cov'])};",
          c_array("double", "kStepCover", [v for row in c["cov"] for v in row], 6, d_lit),
          c_array("double", "kStepWeather", wx_s, 4, d_lit),
          c_array("double", "kStepWolfIn", in_d, 5, d_lit),
          c_array("std::int32_t", "kStepWolfInI", in_i, 16, str),
          c_array("double", "kStepPreyIn", prey_s, 5, d_lit),
          c_array("double", "kStepWolfOut", out_sd, 4, d_lit),
          c_array("std::int32_t", "kStepWolfOutI", out_si, 10, str),
          "}",
          ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "WeatherGoldenVectorsV3.h"
    path.write_text(build_header(), encoding="utf-8", newline="\n")
    print(f"썼다: {path}")


if __name__ == "__main__":
    main()

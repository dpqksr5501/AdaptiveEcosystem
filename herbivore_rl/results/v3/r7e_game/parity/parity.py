"""R7e 게임 시험(10-27, results/v3/r7e_game) 의 팀 통합 맵 판 — 언리얼 대 파이썬 거울 대조 (calm 거울: 10-27 게임 기본 GrazeCalm·RestKeep 켬).

    # herbivore_rl/ 에서 (PYTHONUTF8=1). 언리얼은 띄우지 않는다 — r7e_game.py run 이 남긴 스냅숏·기록 줄·사슴 줄(저장소 밖 scratch)만 읽는다
    python results/v3/r7e_game/parity/parity.py convert --runs <scratch>/r7e_game/runs --work <scratch>/r7e_parity
    python results/v3/r7e_game/parity/parity.py run     --runs <scratch>/r7e_game/runs --work <scratch>/r7e_parity --reps 6 --workers 14
    python results/v3/r7e_game/parity/parity.py run     ... --variant off --reps 2     # 참고: calm 두 규칙을 끈 거울 (같은 시드)
    python results/v3/r7e_game/parity/parity.py compare --runs <scratch>/r7e_game/runs --work <scratch>/r7e_parity --reps 6 --out results/v3/r7e_game/parity/parity

남은 일 'R7e unreal_parity 를 calm 거울로 다시 재기' (results/v3/r7e/unreal_parity.py — 10-24, calm 규칙 전 세계·240 초·세션 20010~20019) 를 10-27 게임 기본
세계(eco.IntegratedV3.GrazeCalm·RestKeep 1)로 다시 잰다.

1) convert — 언리얼 R7e 판 스냅숏(it_s<S>_r7e.json, 300 초 = 전역 스텝 2250)을 results/v3/adapt/adapt.py 의 convert(스냅숏 → 파이썬 거울 세계, 거부 규칙 그대로)
   로 두 번 옮긴다: 바탕 configs/v3_wild3_route5_mirror.yaml + R7e zip(계약 0xad7bad5e1acaf071) → R7e 세계, 바탕 configs/v3_wild3_mirror.yaml + R1b s3 zip(계약
   0x7eea0107339be4ce) → 지금 두뇌 세계. 확인: (가) 스냅숏 settings·지역 world 에 rest_keep·graze_calm 칸이 실리고 켬, (나) 옮긴 세계 = configs/v3_wild3_*calm_mirror.yaml
   (다른 칸은 version 과 바탕에 없는 선택 키 둘 — 그 값이 선택 키 기본값과 같을 때만), (다) 지금 두뇌 판 스냅숏(it_s<S>_cur.json)을 옮긴 세계·지역 자료(먹이 용량
   격자·원판·날씨·은신처)가 R7e 판 스냅숏의 것과 같다(두 언리얼 판이 같은 세계), (라) 먹이 용량 = C++ 난수로 다시 만든 처음 지도(최대 차이 0), (마) 세션마다 규칙 칸이
   같다. 지역 자료(용량 격자·원판·날씨)는 work/maps.json, 규칙은 work/world_<두뇌>.yaml.
2) run — 파이썬 거울: 세션 × 지역(Barren·Forest·Highland) 지도마다 반복 reps 개, 두 두뇌 같은 시드(짝). 시드는 예비 범위 34900~34999 만(관문 판정 35000~ 금지):
   지도 m(세션 순서 × 3 + 지역 순서)의 반복 j = 34900 + (m + 지도 수 × j) mod 100 — 한 반복 안 지도마다 다른 시드, 같은 지도는 반복마다 다른 시드.
   세계 = run_mirror.mirror_cfg(사슴 128, 늑대 식사 38 스텝, world_<두뇌>.yaml) + 그 지역 날씨·원판, 먹이 = 스냅숏 용량 격자(adapt.apply_snapshot_food), 2250 스텝.
   세계 하나 → work/py/<변형>_<두뇌>_s<S>_<지역>_k<j>.json (있으면 건너뛴다 — 이어 돌리기).
3) compare — 언리얼 판(it_s<S>_<cur|r7e>)은 r7e_game_analyze.run_record(300 초 기록 줄 + 스냅숏 + 사슴 줄 자리 셈)와 parse_log(60·120·180·240 초 기록 줄 — 시간마다
   대조)로, 파이썬 세계는 같은 열쇠의 지역 기록(아래 '파이썬 지역 기록')으로 만들어 r7e_game_analyze.METRICS 의 같은 셈 함수로 잰다(두 쪽이 같은 식).
   두뇌 차이(R7e − 지금): 언리얼 세션 짝(세션 = 지역 셋 합, n 24), 파이썬 (세션, 반복) 짝. 같은 방향·크기 z 는 results/v3/r7e/unreal_parity.py 와 같은 규칙:
   '같은 방향' = 파이썬 짝 t 가 양측 5% 문턱 밖일 때 언리얼 차이 부호가 같은가(언리얼 짝 t 가 문턱 안이면 '언리얼은 0 근처'), 문턱 안이면 '파이썬 0 근처'.
   크기 z = (언리얼 차이 − 파이썬 반복 차이 평균) ÷ 파이썬 반복 차이 표준편차 (반복 하나 = 언리얼과 같은 세션 24 개의 파이썬 세계) — |z| < 2 면 파이썬 반복 폭 안.

파이썬 지역 기록 (언리얼 기록 줄·스냅숏·사슴 줄과 같은 정의 — C++ 근거는 칸마다 주석):
  결과·도망 칸 = World.flight_stats(통합 v3 스냅숏 flight 와 같은 이름·정의)·hunt_stats·death_cause, 처음 30·60 초 잡힘 = 225·450 스텝 뒤 누적,
  행동 몫 beh = 스텝 뒤 실행 행동(산 사슴, 스텝 첫머리) — 기록 '구간 사용(개체·스텝)', 은신처 안 = 스텝 첫머리 산 사슴의 이동 뒤 자리(run_mirror 와 같다),
  덮기 keep_* = 그 스텝에 실행한 덮기(스텝 전 wf_mode — 기록 '덮기 개체·스텝'), 두뇌 칸 = 반사(도주·웅크림 덮기) 밖 스텝의 실행 행동, '늑대를 앎' = 결정 관측
  pred_count > 0 (C++ FEcoV3BrainTally), 쉬는 늑대 시야 = C++ TallyRestWolfView (스텝 끝 자리: 쉬는 늑대 = 사냥 중 아님·깨어 있음, 시야 반경 × 날씨 안·눈길 트임,
  은신처 밖, 경계 반경 안에 사냥 중 늑대 없음, 그중 이동 < 0.001 단위 = 멈춤), 길 = flight_stats route(R7e), 사슴 줄 자리 셈 = 결정 스텝마다 산 사슴의 자리·위협을
  앎(관측 seen)·가장 가까운 아는 위협 자리·몸 가장자리에서 가장 가까운 원판 가장자리(C++ '[EcoV3Obs]' 줄 p·seen·j·N) → r7e_game_analyze.position_stats.
  파이썬에 없는 칸(지형 막힘·결정 줄 수·마스크 위반)은 비운다.
출력: <out>.json (판마다 확인·지역 기록·셈), <out>.md (표, 자동). 원 자료(세계 JSON)는 work (저장소 밖).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[4]                                  # herbivore_rl/
for _p in (ROOT, ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "r7e_game"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

REGIONS = ("Barren", "Forest", "Highland")
STEP_S = 2.0 / 15.0
SECONDS = 300.0
STEPS = 2250                                            # 300 초 = 스냅숏 전역 스텝
CHECK_S = (60.0, 120.0, 180.0, 240.0, 300.0)            # 시간마다 대조 (기록 줄 10 초마다 — 그 가운데 60 초마다)
CHECK_STEPS = tuple(int(round(s / STEP_S)) for s in CHECK_S)
SEED_LO, SEED_HI = 34900, 34999                         # 파이썬 예비 범위만 (관문 판정 시드 35000~35199 쓰지 않음)
DEER, EAT_STEPS = 128, 38
BRAINS = {
    "cur": dict(label="내장 R1b-F (게임 기본)", unreal_id="v3_r1_g995_s3_20m@eca97f2e", model="ckpt/v3/v3_r1_g995_s3_20m.zip",
                template="configs/v3_wild3_mirror.yaml", calm="configs/v3_wild3_calm_mirror.yaml", contract="0x7eea0107339be4ce"),
    "r7e": dict(label="R7e 두 길·판 5", unreal_id="v3_r7_g995_s1_20m@40d8710d", model="ckpt/v3/v3_r7_g995_s1_20m.zip",
                template="configs/v3_wild3_route5_mirror.yaml", calm="configs/v3_wild3_route5_calm_mirror.yaml", contract="0xad7bad5e1acaf071"),
}
# calm 두 규칙 (configs/v3_wild3_*calm_mirror.yaml — results/v3/calm/make_calm_configs.py 의 셋). 변형 off = 이 칸을 끔 값으로 (참고 대조)
CALM_KEYS = (("repertoire", "graze_edge_r"), ("repertoire", "graze_edge_w"), ("repertoire", "graze_inertia"), ("repertoire", "graze_wall_margin"),
             ("wild_flight", "rest_keep"), ("wild_flight", "rest_keep_margin"), ("wild_flight", "rest_keep_band"), ("wild_flight", "rest_keep_asleep"))
VARIANTS = ("calm", "off")

# 대조 표의 칸 (r7e_game_analyze.METRICS 의 열쇠 — 파이썬에 없는 칸은 뺀다)
PARITY_KEYS = (
    ("결과", ("caught_share", "starved_share", "caught30", "caught60", "caught300", "hunt_rate", "hunts")),
    ("도망", ("ep_hide", "ep_caught", "ep_hide240", "chased_n", "gf", "ge", "run_s", "own_chase_s", "flee_share", "joined", "rt_pick", "rt_pick_all",
             "rt_shelter_exact", "end_0", "end_7")),
    ("평소", ("beh_0", "beh_1", "beh_2", "keep_alert", "keep_crouch", "restkeep", "in_shelter", "herd_nn", "herd_k10", "herd_alone", "energy", "food")),
    ("이상", ("spin", "calm_flips", "rv_stop", "rv_in", "seen_stop_out", "seen_stop_in", "cover_entries", "cover_quick5", "cover_quick1", "cover_short2",
             "still", "still_n", "obst_hit", "fast_flips", "fast_turn90", "pp_runs", "pp_long", "pp_wall", "pp_steps", "pp_deer")),
    ("두뇌", ("self_flee", "brain_hide", "brain_know_hide")),
)
REGION_KEYS = ("ep_hide", "ep_caught", "chased_n", "caught_share", "caught30", "gf", "run_s", "in_shelter", "brain_know_hide", "spin", "rv_stop", "pp_runs")
TIME_KEYS = ("caught300", "chased_n", "ep_hide", "ep_caught", "gf", "flee_share", "in_shelter", "beh_2")
HEAD_KEYS = ("ep_hide", "ep_caught", "gf", "caught_share", "run_s", "flee_share", "in_shelter", "beh_2", "brain_know_hide", "rt_pick_all", "hunt_rate",
             "spin", "rv_stop", "cover_quick5", "joined", "pp_runs")


def parse_sessions(text: str) -> list[int]:
    out: list[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def seed_of(m: int, j: int, n_maps: int) -> int:
    return SEED_LO + (m + n_maps * j) % (SEED_HI - SEED_LO + 1)


def seed_plan(sessions: list, reps: int) -> dict:
    """{(세션, 지역, 반복): 시드}. 한 반복 안 지도마다 다른 시드, 같은 지도는 반복마다 다른 시드여야 한다."""
    n_maps = len(sessions) * len(REGIONS)
    span = SEED_HI - SEED_LO + 1
    if n_maps > span:
        raise SystemExit(f"지도 {n_maps} 장이 예비 시드 {span} 개보다 많다")
    plan = {}
    for i, s in enumerate(sessions):
        for r_i, r in enumerate(REGIONS):
            m = i * len(REGIONS) + r_i
            for j in range(reps):
                plan[(s, r, j)] = seed_of(m, j, n_maps)
    for j in range(reps):
        sj = [v for (s, r, jj), v in plan.items() if jj == j]
        if len(set(sj)) != len(sj):
            raise SystemExit(f"반복 {j} 안에서 시드가 겹친다")
    for s in sessions:
        for r in REGIONS:
            sm = [plan[(s, r, j)] for j in range(reps)]
            if len(set(sm)) != len(sm):
                raise SystemExit(f"지도 ({s}, {r}) 의 반복 시드가 겹친다 {sm} — reps 를 줄인다")
    if not all(SEED_LO <= v <= SEED_HI for v in plan.values()):
        raise SystemExit("시드가 예비 범위 밖이다")
    return plan


def sha1_12(path: Path) -> str:
    return hashlib.sha1(Path(path).read_bytes()).hexdigest()[:12]


# --------------------------------------------------------------------- #
# 1) convert
# --------------------------------------------------------------------- #


def _diff(a, b, p: str = "") -> list:
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            q = f"{p}.{k}" if p else str(k)
            if k not in a:
                out.append((q, "<없음>", b[k]))
            elif k not in b:
                out.append((q, a[k], "<없음>"))
            else:
                out += _diff(a[k], b[k], q)
    elif a != b:
        out.append((p, a, b))
    return out


def cmd_convert(a) -> int:
    import adapt
    import yaml
    from env_v2.features import OPTIONAL_KEYS

    runs, work = Path(a.runs), Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    sessions = parse_sessions(a.sessions)
    ref = json.loads(adapt.REFERENCE.read_text(encoding="utf-8"))
    checks: list = []

    def check(ok: bool, what: str):
        checks.append(dict(ok=bool(ok), what=what))

    worlds: dict = {}
    maps: dict = {}
    changed_first: dict = {}
    conv_checks: dict = {}
    for s in sessions:
        snap7 = adapt.load_snapshot(runs / f"it_s{s}_r7e.json")
        snapc = adapt.load_snapshot(runs / f"it_s{s}_cur.json")
        for nm, sn in (("r7e", snap7), ("cur", snapc)):
            st = sn["settings"]
            ok = st.get("rest_keep") is True and st.get("graze_calm") is True
            blk = [(R["world"].get("wild_flight", {}).get("rest_keep"), R["world"].get("graze_calm")) for R in sn["regions"]]
            ok = ok and all(rk is True and isinstance(gc, dict) and gc.get("graze_edge_r", 0) > 0 for rk, gc in blk)
            check(ok and int(sn["global_step"]) == STEPS, f"s{s} {nm} 스냅숏: settings rest_keep {st.get('rest_keep')} · graze_calm {st.get('graze_calm')}, "
                                                          f"지역 world.wild_flight.rest_keep·graze_calm 실림 {len(blk)}/3, 전역 스텝 {sn['global_step']}")
            check(sn["brain"]["id"] == BRAINS[nm]["unreal_id"] and sn["brain"].get("contract_hash") == BRAINS[nm]["contract"],
                  f"s{s} {nm} 스냅숏 두뇌 {sn['brain']['id']} 계약 {sn['brain'].get('contract_hash')}")
        conv = {}
        for b, B in BRAINS.items():
            conv[b] = adapt.convert(snap7, ref, template=ROOT / B["template"], start=ROOT / B["model"], contract=B["contract"])
        conv_c = adapt.convert(snapc, ref, template=ROOT / BRAINS["cur"]["template"], start=ROOT / BRAINS["cur"]["model"], contract=BRAINS["cur"]["contract"])
        # (나) 옮긴 세계 = calm 거울 설정
        for b, B in BRAINS.items():
            cal = yaml.safe_load((ROOT / B["calm"]).read_text(encoding="utf-8"))
            d = _diff(conv[b]["world"], cal)
            bad = []
            for key, x, y in d:
                if key == "version":
                    continue
                parts = key.split(".")
                if len(parts) == 3 and parts[0] == "features" and x == "<없음>" and parts[2] in OPTIONAL_KEYS.get(parts[1], {}) \
                        and OPTIONAL_KEYS[parts[1]][parts[2]] == y:
                    continue          # 바탕에 없는 선택 키 — 옮긴 세계는 기본값(= calm 설정 값)
                bad.append((key, x, y))
            check(not bad, f"s{s} {b}: 옮긴 세계 = {B['calm']} (다른 칸 {len(d)} 개 가운데 version·기본값 선택 키 빼고 {len(bad)} 개{' ' + str(bad[:3]) if bad else ''})")
            if s == sessions[0]:
                changed_first[b] = conv[b]["record"]["changed"]
            conv_checks.setdefault(b, conv[b]["record"]["checks"]) if s == sessions[0] else None
        # (다) 두 언리얼 판(지금·R7e)이 같은 세계 — 지금 판 스냅숏을 옮긴 세계·지역 자료 = R7e 판 스냅숏의 것
        same_world = conv_c["world"] == conv["cur"]["world"]
        reg_keys = ("cap", "discs", "weather", "covers", "gw", "region_index")
        same_regs = all(conv_c["regions"][r][k] == conv[b]["regions"][r][k] for b in BRAINS for r in REGIONS for k in reg_keys)
        check(same_world and same_regs, f"s{s}: 지금 판 스냅숏을 옮긴 세계·지역 자료(용량·원판·날씨·은신처) = R7e 판 스냅숏의 것")
        # (라) 먹이 용량 = C++ 난수로 다시 만든 처음 지도
        rb = {r: conv["r7e"]["regions"][r]["cpp_rebuild_max_diff"] for r in REGIONS}
        check(all(v == 0.0 for v in rb.values()), f"s{s}: 먹이 용량 ↔ C++ 난수 처음 지도 최대 차이 {rb}")
        # (마) 세션마다 규칙 칸 같음 (지역 칸은 일마다 덮는다)
        for b in BRAINS:
            w = copy.deepcopy(conv[b]["world"])
            if b not in worlds:
                worlds[b] = w
            else:
                check(w == worlds[b], f"s{s} {b}: 옮긴 세계 규칙 = 첫 세션의 것")
        maps[str(s)] = {r: dict(cap=conv["r7e"]["regions"][r]["cap"], discs=conv["r7e"]["regions"][r]["discs"], weather=conv["r7e"]["regions"][r]["weather"],
                                covers=conv["r7e"]["regions"][r]["covers"], gw=conv["r7e"]["regions"][r]["gw"],
                                cap_sha=hashlib.sha256(np.asarray(conv["r7e"]["regions"][r]["cap"], dtype=np.float64).tobytes()).hexdigest()[:16])
                        for r in REGIONS}
        print(f"s{s}: 옮김 (어긋남 누적 {sum(1 for c in checks if not c['ok'])})", flush=True)
    for b, w in worlds.items():
        adapt.write_yaml(work / f"world_{b}.yaml", w, f"# R7e 게임 시험 파이썬 거울 — 언리얼 R7e 판 스냅숏(it_s{sessions[0]}_r7e.json)을 adapt.convert 로 옮긴 판정 세계 "
                                                      f"(바탕 {BRAINS[b]['template']}). 자동 생성 — parity.py convert\n")
    (work / "maps.json").write_text(json.dumps(maps), encoding="utf-8")
    out = dict(sessions=sessions, checks=checks, changed=changed_first, convert_checks=conv_checks,
               world_sha1={b: sha1_12(work / f"world_{b}.yaml") for b in worlds})
    (work / "convert.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    nbad = sum(1 for c in checks if not c["ok"])
    print(f"확인 {len(checks)} 칸 가운데 어긋남 {nbad}")
    for c in checks:
        if not c["ok"]:
            print("  어긋남:", c["what"])
    return 0 if nbad == 0 else 1


# --------------------------------------------------------------------- #
# 2) run — 파이썬 세계 하나
# --------------------------------------------------------------------- #


def _nearest_disc_edge(p: np.ndarray, discs: np.ndarray, body_r: float) -> np.ndarray:
    """몸 가장자리에서 가장 가까운 원판 가장자리까지 (C++ '[EcoV3Obs]' N = obstacle_obs_values 의 near). 원판이 없으면 inf."""
    if not len(discs) or not len(p):
        return np.full(len(p), np.inf)
    fx = p[:, 0:1] - discs[:, 0][None, :]
    fy = p[:, 1:2] - discs[:, 1][None, :]
    return (np.sqrt(fx * fx + fy * fy) - (discs[:, 2] + float(body_r))[None, :]).min(1)


def _seen_threat(w) -> tuple[np.ndarray, np.ndarray]:
    """결정 관측의 위협을 앎(seen = 가장 가까운 아는 위협이 있다 — 관측 1 의 보임)과 그 위협 자리 (모르면 0). C++ '[EcoV3Obs]' seen·j."""
    g = w._g
    seen = np.isfinite(g["d_pred_min"])
    J = np.zeros((w.N, 2))
    if w.M and seen.any():
        pv = g["wf_pvis"]
        d = np.sqrt(((w.pos[:, None, :] - w.pred_pos[None, :, :]) ** 2).sum(-1))
        j = np.where(pv, d, np.inf).argmin(1)
        J = np.where(seen[:, None], w.pred_pos[j], 0.0)
    return seen, J


def _cum(w, n_beh, shelter, live_n, rv) -> dict:
    """그 시각까지 누적 (언리얼 parse_log(t) 의 같은 열쇠)."""
    f = w.flight_stats()
    e = f["episode"]
    h = w.hunt_stats()
    cause = np.asarray(w.death_cause)
    return dict(n=int(w.N), caught=int((cause == 1).sum()), starved=int((cause == 2).sum()), alive=int(w.alive.sum()), started=int(f["started"]),
                live=int(f["live_steps"]), flee=int(f["flee_steps"]), reflex=int(f["reflex_steps"]), ep_started=int(e["started"]), ep_chased=int(e["chased"]),
                ep_hidden=int(e["hidden"]), ep_watching=int(e["watching"]), ep_caught=int(e["caught"]), ep_starved=int(e["starved"]),
                ep_truncated=int(e["truncated"]), ep_joined=int(e["joined"]), beh=[int(x) for x in n_beh], shelter_steps=int(shelter),
                hunt_starts=int(h["starts"]), hunt_ends=int(h["ends"]), hunt_success=int(h["success"]), rv_live=int(rv[0]), rv_in=int(rv[1]),
                rv_stop=int(rv[2]), live_check=int(live_n))


def py_world(job: dict) -> dict:
    """세계 하나 → 지역 기록 (300 초) + 시각마다 누적 + 메타. job = {cfg, seed, model, cap, steps, region, session, rep, brain, variant}."""
    import env.torch_init  # noqa: F401
    from env.config import Config
    from env_v2 import rollout as ro
    from env_v2.world import WF_ALERT, WF_PANIC, WF_REST, WF_SHELTER, World, FLIGHT_CAUSES

    import adapt
    import r7e_game_analyze as ra

    t0 = time.perf_counter()
    seed = int(job["seed"])
    w = World(Config(job["cfg"]), seeds=[seed])
    if w.alive is None:
        raise ValueError("거울 세계는 부활 없음이어야 한다")
    adapt.apply_snapshot_food(w, job["cap"])
    w.track_flight = True
    pol = ro.build_policy({"kind": "rep_learned", "path": str(job["model"])}, seed)
    ro.forward_bind(pol, w)
    food0 = float(w.food.sum())
    N, T = int(w.N), int(job["steps"])
    discs = np.asarray(w.obstacles, dtype=np.float64).reshape(-1, 3) if getattr(w, "obstacles", None) is not None else np.zeros((0, 3))
    body_r = float(w._ob["body_r"]) if getattr(w, "_ob", None) is not None else 0.0
    P = np.full((T + 1, N, 2), np.nan)
    S = np.zeros((T + 1, N), bool)
    J = np.full((T + 1, N, 2), np.nan)
    Nd = np.full((T + 1, N), np.inf)
    A = np.zeros((T + 1, N), bool)

    def rec_pos(t):
        a_ = w.alive.copy()
        sn, jj = _seen_threat(w)
        A[t] = a_
        P[t][a_] = w.pos[a_]
        S[t] = sn & a_
        J[t][a_] = jj[a_]
        Nd[t][a_] = _nearest_disc_edge(w.pos[a_], discs, body_r)

    rec_pos(0)
    n_beh = np.zeros(5, dtype=np.int64)
    brain_beh = np.zeros(5, dtype=np.int64)
    know_beh = np.zeros(5, dtype=np.int64)
    reflex_n = reflex_know = 0
    keep = np.zeros(5, dtype=np.int64)          # 그 스텝에 실행한 덮기 (스텝 전 wf_mode, 스텝 첫머리 산 사슴)
    shelter = live_n = 0
    rv = [0, 0, 0]
    caught_at = {}
    at = {}
    wf = w._wf
    alert2 = float(wf["alert_r"]) ** 2
    for _ in range(T):
        live0 = w.alive.copy()
        pos0 = w.pos.copy()
        mode0 = w.wf_mode.copy()
        know = np.asarray(w._g["pred_count"]) > 0
        w.step(np.asarray(pol(w.observe()), dtype=np.float64))
        beh = np.asarray(w._rs.behavior)
        n_beh += np.bincount(beh[live0], minlength=5)[:5]
        keep += np.bincount(mode0[live0], minlength=5)[:5]
        refl = live0 & ((mode0 == WF_PANIC) | (mode0 == WF_SHELTER))
        br = live0 & ~refl
        brain_beh += np.bincount(beh[br], minlength=5)[:5]
        know_beh += np.bincount(beh[br & know], minlength=5)[:5]
        reflex_n += int(refl.sum())
        reflex_know += int((refl & know).sum())
        shelter += int(np.count_nonzero(live0 & w._in_cover(w.pos)))
        live_n += int(live0.sum())
        # 쉬는 늑대 시야 (C++ TallyRestWolfView — 스텝 끝 자리, 이번 스텝에 죽은 사슴 빼고)
        lv = w.alive.copy()
        rv[0] += int(lv.sum())
        if w.M:
            hunt = w._wf_hunting()
            asleep = w.pred_asleep.copy() if getattr(w, "_ps", None) is not None else np.zeros(w.M, bool)
            dx = w.pred_pos[:, 0][None, :] - w.pos[:, 0:1]
            dy = w.pred_pos[:, 1][None, :] - w.pos[:, 1:2]
            d2 = dx * dx + dy * dy
            view = w._wf_view()
            near_h = ((d2 <= alert2) & hunt[None, :]).any(1)
            cand = (d2 <= view * view) & (~hunt & ~asleep)[None, :]
            cand = w._wf_los(cand)
            m = lv & ~w._in_cover(w.pos) & cand.any(1) & ~near_h
            rv[1] += int(m.sum())
            mv = w.pos - pos0
            rv[2] += int((m & ((mv * mv).sum(1) < 1e-6)).sum())
        rec_pos(int(w.t))
        if w.t in (225, 450):
            caught_at[int(w.t)] = int((np.asarray(w.death_cause) == 1).sum())
        if w.t in CHECK_STEPS:
            at[str(round(w.t * STEP_S, 1))] = _cum(w, n_beh, shelter, live_n, rv)
    end = _cum(w, n_beh, shelter, live_n, rv)
    f = w.flight_stats()
    rec = dict(end)
    rec.update(caught30=caught_at[225], caught60=caught_at[450], own_n=int(f["own_n"]), own_chase_steps=int(f["own_contact"]),
               causes=[int(f["n"][k]) for k in FLIGHT_CAUSES if k != "truncated"],
               keep_alert=int(keep[WF_ALERT]), keep_flee=int(keep[WF_PANIC]), keep_crouch=int(keep[WF_SHELTER]), restkeep_steps=int(keep[WF_REST]),
               brain_beh=[int(x) for x in brain_beh], brain_know_beh=[int(x) for x in know_beh], brain_steps=int(brain_beh.sum()),
               brain_know=int(know_beh.sum()), brain_reflex=int(reflex_n), brain_reflex_know=int(reflex_know))
    e = np.clip(w.energy[w.alive] / w.cfg.max_energy, 0.0, 1.0)
    rec.update(energy_pct=float(100.0 * e.mean()) if len(e) else 0.0, food_pct=float(100.0 * w.food.sum() / food0) if food0 > 0 else 0.0)
    if getattr(w, "_ob", None) is not None:
        os_ = w.obstacle_stats()
        rec.update(obst_deer_steps=int(os_["deer_steps"]), obst_deer_hit=int(os_["deer_hit"]))
    if "route" in f:
        rt = f["route"]
        rec.update(rt_choice=int(rt.get("choice", 0)), rt_picked_shelter=int(rt["picked"]["shelter"]), snap_pk_run=int(rt["picked"]["run"]),
                   snap_pk_shelter=int(rt["picked"]["shelter"]), snap_rt_run_exact=int(rt["steps"]["run"]), snap_rt_shelter_exact=int(rt["steps"]["shelter"]))
    try:
        ws = w.wild_stats()
        rec.update(restkeep_starts=int(ws.get("rest_starts", 0)), restband_turn=int(ws.get("band_turn_steps", 0)), restband_stop=int(ws.get("band_stop_steps", 0)))
    except ValueError:
        pass
    rec["c240"] = {k: at["240.0"][k] for k in ("ep_hidden", "ep_chased", "ep_caught", "started", "live")}
    rec.update(ra.position_stats(P, S, J, Nd, A))
    rec["live_check_ok"] = bool(end["live_check"] == end["live"])
    meta = dict(seed=seed, session=int(job["session"]), region=job["region"], rep=int(job["rep"]), brain=job["brain"], variant=job["variant"],
                model=Path(job["model"]).name, steps=T, n=N, wolves=int(w.M), discs=int(len(discs)), allowed=list(pol.allowed),
                wall_s=round(time.perf_counter() - t0, 2))
    return dict(meta=meta, rec=rec, at=at)


def _job_name(variant: str, b: str, s: int, r: str, j: int) -> str:
    return f"{variant}_{b}_s{s}_{r}_k{j}"


def make_jobs(work: Path, sessions: list, reps: int, variant: str, brains) -> list:
    import run_mirror as rm

    maps = json.loads((work / "maps.json").read_text(encoding="utf-8"))
    plan = seed_plan(sessions, reps)
    jobs = []
    for b in brains:
        cfg = rm.mirror_cfg(DEER, EAT_STEPS, work / f"world_{b}.yaml").to_dict()
        f = cfg["v2"]["features"]
        if variant == "off":
            from env_v2.features import OPTIONAL_KEYS

            for blk, key in CALM_KEYS:
                f[blk][key] = OPTIONAL_KEYS[blk][key]
        else:
            if not (f["wild_flight"].get("rest_keep") and f["repertoire"].get("graze_edge_r", 0) > 0):
                raise SystemExit(f"world_{b}.yaml 에 calm 규칙이 켜져 있지 않다")
        for s in sessions:
            for r in REGIONS:
                M = maps[str(s)][r]
                for j in range(reps):
                    c = copy.deepcopy(cfg)
                    c["v2"]["features"]["wild_weather"]["region"] = r
                    c["v2"]["features"]["obstacles"]["fixed"] = copy.deepcopy(M["discs"])
                    jobs.append(dict(name=_job_name(variant, b, s, r, j), cfg=c, seed=plan[(s, r, j)], model=str(ROOT / BRAINS[b]["model"]), cap=M["cap"],
                                     steps=STEPS, region=r, session=s, rep=j, brain=b, variant=variant))
    return jobs


def cmd_run(a) -> int:
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from env_v2 import rollout as ro

    work = Path(a.work)
    out = work / "py"
    out.mkdir(parents=True, exist_ok=True)
    sessions = parse_sessions(a.sessions)
    jobs = [j for j in make_jobs(work, sessions, a.reps, a.variant, a.brains) if not (out / f"{j['name']}.json").exists()]
    print(f"세계 {len(jobs)} 개 (이미 있는 것 뺌) · 일꾼 {a.workers}", flush=True)
    t0 = time.time()
    done = 0
    if a.workers <= 1:
        for j in jobs:
            name = j.pop("name")
            (out / f"{name}.json").write_text(json.dumps(py_world(j)), encoding="utf-8")
            done += 1
            print(f"{done}/{len(jobs)} {name}", flush=True)
        return 0
    with ProcessPoolExecutor(max_workers=int(a.workers), initializer=ro._init_worker) as ex:
        fut = {}
        for j in jobs:
            name = j.pop("name")
            fut[ex.submit(py_world, j)] = name
        for fu in as_completed(fut):
            name = fut[fu]
            res = fu.result()
            (out / f"{name}.json").write_text(json.dumps(res), encoding="utf-8")
            done += 1
            if done % 12 == 0 or done == len(jobs):
                el = time.time() - t0
                print(f"{done}/{len(jobs)} · {el:.0f} 초 · 남은 어림 {el / done * (len(jobs) - done):.0f} 초", flush=True)
    return 0


# --------------------------------------------------------------------- #
# 3) compare
# --------------------------------------------------------------------- #


def t_crit(df: int) -> float:
    from scipy import stats

    return float(stats.t.ppf(0.975, max(int(df), 1)))


def paired(d: list) -> dict:
    x = np.array([v for v in d if math.isfinite(v)], dtype=np.float64)
    n = len(x)
    if n == 0:
        return dict(diff=float("nan"), sd=float("nan"), t=float("nan"), n=0)
    m = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 1 else float("nan")
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    t = m / se if se and se > 0 else (0.0 if sd == 0 and m == 0 else float("nan"))
    return dict(diff=m, sd=sd, t=t, n=n)


def direction(up: dict, pp: dict, ud: float, pd: float) -> str:
    if not math.isfinite(pp["t"]) or pp["n"] < 2 or abs(pp["t"]) < t_crit(pp["n"] - 1):
        return "파이썬 0 근처"
    weak = not math.isfinite(up["t"]) or abs(up["t"]) < t_crit(up["n"] - 1)
    same = np.sign(ud) == np.sign(pd)
    return ("예" if same else "아니오") + (" (언리얼은 0 근처)" if weak else "")


def unreal_records(runs: Path, sessions: list) -> tuple[dict, dict, list]:
    """언리얼 판: run_record(300 초) + parse_log(60·120·180·240 초). 확인은 r7e_game_analyze.checks 와 같은 칸."""
    import r7e_game_analyze as ra

    recs, at = {}, {}
    for s in sessions:
        for b in BRAINS:
            n = f"it_s{s}_{b}"
            recs[("it", s, b)] = ra.run_record(runs, n, SECONDS)
            at[(s, b)] = {}
            for t in CHECK_S[:-1]:
                at[(s, b)][str(t)] = ra.parse_log(runs / f"{n}.ecov3.log", t)["regions"]
            at[(s, b)][str(SECONDS)] = recs[("it", s, b)]["regions"]
            print("언리얼 읽음", n, flush=True)
    chk = ra.checks(runs, recs, ["it"], sessions, SECONDS)
    return recs, at, chk


def _vals(regs: list, sessions: int) -> dict:
    import r7e_game_analyze as ra

    t = ra.total([ra.flat_region(r) for r in regs])
    t["_sessions"] = sessions
    return ra.values(t)


def compare(runs: Path, work: Path, sessions: list, reps: int, variants: list) -> dict:
    import r7e_game_analyze as ra

    recs, uat, chk = unreal_records(runs, sessions)
    py = work / "py"
    out = dict(sessions=sessions, reps=reps, checks=chk, variants={})
    # 언리얼 셈
    U = {}
    for b in BRAINS:
        U[b] = dict(pooled=_vals([recs[("it", s, b)]["regions"][r] for s in sessions for r in REGIONS], len(sessions)),
                    per_session={s: _vals([recs[("it", s, b)]["regions"][r] for r in REGIONS], 1) for s in sessions},
                    region={r: _vals([recs[("it", s, b)]["regions"][r] for s in sessions], len(sessions)) for r in REGIONS},
                    region_session={r: {s: _vals([recs[("it", s, b)]["regions"][r]], 1) for s in sessions} for r in REGIONS},
                    time={t: _vals([uat[(s, b)][t][r] for s in sessions for r in REGIONS], len(sessions)) for t in map(str, CHECK_S)})
    out["unreal"] = U
    out["unreal_runs"] = {f"it_s{s}_{b}": dict(log_vs_snapshot=recs[("it", s, b)].get("log_vs_snapshot"), brain_start=recs[("it", s, b)]["meta"]["brain_start"],
                                              deer_sha256=(recs[("it", s, b)].get("deer_meta") or {}).get("deer_sha256"))
                          for s in sessions for b in BRAINS}
    # 저장소 compare.json (r7e_game analyze) 의 300 초 지역 기록과 같은가
    cj = ROOT / "results" / "v3" / "r7e_game" / "compare.json"
    if cj.exists():
        old = json.loads(cj.read_text(encoding="utf-8"))["runs"]
        bad = []
        for s in sessions:
            for b in BRAINS:
                n = f"it_s{s}_{b}"
                for r in REGIONS:
                    a_ = recs[("it", s, b)]["regions"][r]
                    o_ = old[n]["regions"][r]
                    for k in ("ep_chased", "ep_hidden", "caught", "spin", "pp_runs", "rv_stop", "live", "shelter_steps"):
                        x, y = a_.get(k), o_.get(k)
                        if not (x == y or (isinstance(x, float) and isinstance(y, (int, float)) and abs(x - y) < 1e-6)):
                            bad.append(f"{n}.{r}.{k}: {x} ≠ {y}")
        out["checks"].append(dict(ok=not bad, what=f"다시 읽은 언리얼 300 초 지역 기록 = 저장소 results/v3/r7e_game/compare.json (판 {2 * len(sessions)} 개 × 지역 셋 × 8 칸"
                                                     f"{', 다름 ' + str(bad[:3]) if bad else ''})"))
    lut = {k: (n, pct, nd, g) for k, n, _, pct, nd, g in ra.METRICS}
    keys = [k for _, ks in PARITY_KEYS for k in ks]
    for variant in variants:
        W = {}
        metas = []
        for b in BRAINS:
            for s in sessions:
                for r in REGIONS:
                    for j in range(reps):
                        p = py / f"{_job_name(variant, b, s, r, j)}.json"
                        if not p.exists():
                            raise SystemExit(f"{p.name} 가 없다 — run 을 먼저 (변형 {variant}, reps {reps})")
                        d = json.loads(p.read_text(encoding="utf-8"))
                        W[(b, s, r, j)] = d
                        metas.append(d["meta"])
        plan = seed_plan(sessions, reps)
        bad_meta = [m for m in metas if m["seed"] != plan[(m["session"], m["region"], m["rep"])] or m["steps"] != STEPS or m["n"] != DEER
                    or m["model"] != Path(BRAINS[m["brain"]]["model"]).name or m["variant"] != variant]
        live_bad = sum(1 for d in W.values() if not d["rec"].get("live_check_ok"))
        V = dict(checks=[dict(ok=not bad_meta, what=f"파이썬 세계 {len(metas)} 개 메타(시드 계획·스텝 {STEPS}·사슴 {DEER}·모델·변형) 맞음 ({len(bad_meta)} 개 다름)"),
                         dict(ok=live_bad == 0, what=f"파이썬 산 사슴-스텝 두 셈(도망 기록 = 스텝 첫머리) 같음 (다름 {live_bad})")],
                 wall_s=dict(min=min(m["wall_s"] for m in metas), max=max(m["wall_s"] for m in metas), sum=round(sum(m["wall_s"] for m in metas), 1)),
                 seeds=sorted({m["seed"] for m in metas}))
        allowed = {(m["brain"], tuple(m["allowed"])) for m in metas}
        V["allowed"] = sorted([list(x) for x in allowed])
        P = {}
        for b in BRAINS:
            regs_all = [W[(b, s, r, j)]["rec"] for s in sessions for r in REGIONS for j in range(reps)]
            P[b] = dict(pooled=_vals(regs_all, len(sessions) * reps),
                        unit={(s, j): _vals([W[(b, s, r, j)]["rec"] for r in REGIONS], 1) for s in sessions for j in range(reps)},
                        rep={j: _vals([W[(b, s, r, j)]["rec"] for s in sessions for r in REGIONS], len(sessions)) for j in range(reps)},
                        region={r: _vals([W[(b, s, r, j)]["rec"] for s in sessions for j in range(reps)], len(sessions) * reps) for r in REGIONS},
                        region_unit={r: {(s, j): _vals([W[(b, s, r, j)]["rec"]], 1) for s in sessions for j in range(reps)} for r in REGIONS},
                        region_rep={r: {j: _vals([W[(b, s, r, j)]["rec"] for s in sessions], len(sessions)) for j in range(reps)} for r in REGIONS},
                        time={t: _vals([W[(b, s, r, j)]["at"][t] for s in sessions for r in REGIONS for j in range(reps)], len(sessions) * reps)
                              for t in map(str, CHECK_S)},
                        time_rep={t: {j: _vals([W[(b, s, r, j)]["at"][t] for s in sessions for r in REGIONS], len(sessions)) for j in range(reps)}
                                  for t in map(str, CHECK_S)})
        rows = {}
        for k in keys + [k for k in REGION_KEYS if k not in keys]:
            rows[k] = _row(k, U, P, sessions, reps, None)
        V["rows"] = rows
        V["region_rows"] = {r: {k: _row(k, U, P, sessions, reps, r) for k in REGION_KEYS} for r in REGIONS}
        V["time_rows"] = {t: {k: _trow(k, U, P, reps, t) for k in TIME_KEYS} for t in map(str, CHECK_S)}
        V["python"] = {b: dict(pooled=P[b]["pooled"], rep=P[b]["rep"], region=P[b]["region"]) for b in BRAINS}
        out["variants"][variant] = V
    out["lut"] = {k: dict(name=v[0], pct=v[1], nd=v[2], group=v[3]) for k, v in lut.items()}
    return out


def _row(k: str, U: dict, P: dict, sessions: list, reps: int, region: str | None) -> dict:
    if region is None:
        u = {b: U[b]["pooled"][k] for b in BRAINS}
        p = {b: P[b]["pooled"][k] for b in BRAINS}
        ud = [U["r7e"]["per_session"][s][k] - U["cur"]["per_session"][s][k] for s in sessions]
        pd_ = [P["r7e"]["unit"][(s, j)][k] - P["cur"]["unit"][(s, j)][k] for s in sessions for j in range(reps)]
        rep = {b: [P[b]["rep"][j][k] for j in range(reps)] for b in BRAINS}
    else:
        u = {b: U[b]["region"][region][k] for b in BRAINS}
        p = {b: P[b]["region"][region][k] for b in BRAINS}
        ud = [U["r7e"]["region_session"][region][s][k] - U["cur"]["region_session"][region][s][k] for s in sessions]
        pd_ = [P["r7e"]["region_unit"][region][(s, j)][k] - P["cur"]["region_unit"][region][(s, j)][k] for s in sessions for j in range(reps)]
        rep = {b: [P[b]["region_rep"][region][j][k] for j in range(reps)] for b in BRAINS}
    up, pp = paired(ud), paired(pd_)
    rd = np.array([rep["r7e"][j] - rep["cur"][j] for j in range(reps)], dtype=np.float64)
    rd = rd[np.isfinite(rd)]
    row = dict(unreal=u, python=p, unreal_pair=up, python_pair=pp)
    udiff = u["r7e"] - u["cur"]
    pdiff = p["r7e"] - p["cur"]
    row.update(unreal_diff=udiff, python_diff=pdiff)
    if len(rd) >= 2:
        sd = float(rd.std(ddof=1))
        row["rep_diff"] = dict(mean=float(rd.mean()), sd=sd, min=float(rd.min()), max=float(rd.max()))
        row["diff_z"] = (udiff - float(rd.mean())) / sd if sd > 0 and math.isfinite(udiff) else float("nan")
    else:
        row["rep_diff"] = None
        row["diff_z"] = float("nan")
    row["direction"] = direction(up, pp, udiff, pdiff) if math.isfinite(udiff) and math.isfinite(pdiff) else "—"
    lv = {}
    for b in BRAINS:
        v = np.array(rep[b], dtype=np.float64)
        v = v[np.isfinite(v)]
        if len(v) >= 2 and math.isfinite(u[b]):
            sd = float(v.std(ddof=1))
            lv[b] = dict(mean=float(v.mean()), sd=sd, min=float(v.min()), max=float(v.max()), z=(u[b] - float(v.mean())) / sd if sd > 0 else float("nan"))
    row["level"] = lv
    return row


def _trow(k: str, U: dict, P: dict, reps: int, t: str) -> dict:
    u = {b: U[b]["time"][t][k] for b in BRAINS}
    p = {b: P[b]["time"][t][k] for b in BRAINS}
    rd = np.array([P["r7e"]["time_rep"][t][j][k] - P["cur"]["time_rep"][t][j][k] for j in range(reps)], dtype=np.float64)
    rd = rd[np.isfinite(rd)]
    ud = u["r7e"] - u["cur"]
    sd = float(rd.std(ddof=1)) if len(rd) >= 2 else float("nan")
    return dict(unreal=u, python=p, unreal_diff=ud, python_diff=p["r7e"] - p["cur"],
                rep_diff=dict(mean=float(rd.mean()) if len(rd) else float("nan"), sd=sd, min=float(rd.min()) if len(rd) else float("nan"),
                              max=float(rd.max()) if len(rd) else float("nan")),
                diff_z=(ud - float(rd.mean())) / sd if len(rd) >= 2 and sd > 0 else float("nan"))


def _f(x, pct: bool, nd: int) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{100.0 * x:.{nd}f}%" if pct else f"{x:.{nd}f}"


def _d(x, pct: bool, nd: int) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{100.0 * x:+.{nd}f}%p" if pct else f"{x:+.{nd}f}"


def _t(x) -> str:
    return "—" if x is None or not math.isfinite(x) else f"{x:+.2f}".replace("-", "−")


def write_md(path: Path, res: dict, convert: dict) -> None:
    lut = res["lut"]
    S, k = res["sessions"], res["reps"]
    V = res["variants"]["calm"]
    L = ["# R7e 게임 시험 — 언리얼 통합 맵 대 파이썬 calm 거울 (자동 생성 — results/v3/r7e_game/parity/parity.py)", ""]
    L += ["## 조건", ""]
    L.append(f"- 언리얼: r7e_game 판 `it_s<S>_<cur|r7e>` (`/Game/Map/LV_Ecosystem_IntegrationTest`, 세션 {S[0]}~{S[-1]} {len(S)} 개 × 지역 셋, 사슴 128·늑대 4, 300 초 = "
             f"전역 스텝 {STEPS}, 게임 기본 = GrazeCalm·RestKeep 켬). 300 초 기록 줄·스냅숏·사슴 줄 + 60·120·180·240 초 기록 줄.")
    L.append(f"- 파이썬: R7e 판 스냅숏을 `adapt.convert` 로 옮긴 세계(지금 두뇌는 바탕 `{BRAINS['cur']['template']}`, R7e 는 `{BRAINS['r7e']['template']}`) = "
             f"`{BRAINS['cur']['calm']}` · `{BRAINS['r7e']['calm']}`, 지도마다 스냅숏 먹이 용량·원판·날씨, 반복 {k}(시드 {SEED_LO}~{SEED_HI} 안 "
             f"{len(V['seeds'])} 개 — 두 두뇌 같은 시드), {STEPS} 스텝.")
    L.append(f"- 두뇌: 지금 = {BRAINS['cur']['label']} (`{BRAINS['cur']['unreal_id']}`, `{BRAINS['cur']['model']}`), R7e = `{BRAINS['r7e']['unreal_id']}` "
             f"(`{BRAINS['r7e']['model']}`). 파이썬 허용 행동 {V['allowed']}.")
    L.append(f"- 셈: r7e_game_analyze.METRICS 의 같은 셈 함수(몫은 전체 합의 비). 짝 t 는 언리얼 세션 단위(n {len(S)}), 파이썬 (세션, 반복) 단위(n {len(S) * k}) — 판정이 아니라 방향 보기다.")
    L.append("- '같은 방향' = 파이썬 짝 t 가 양측 5% 문턱 밖일 때 언리얼 차이 부호가 같은가(언리얼 짝 t 가 문턱 안이면 '언리얼은 0 근처'), 문턱 안이면 '파이썬 0 근처'. "
             f"크기 z = (언리얼 차이 − 파이썬 반복 차이 평균) ÷ 파이썬 반복 차이 표준편차 (반복 하나 = 세션 {len(S)} 개) — |z| < 2 면 파이썬 반복 폭 안.")
    nb = [c for c in convert["checks"] if not c["ok"]]
    L.append(f"- 변환 확인 {len(convert['checks'])} 칸 가운데 어긋남 {len(nb)} — 스냅숏에 rest_keep·graze_calm 실림·켬, 옮긴 세계 = calm 거울 설정, 지금 판·R7e 판 같은 세계, "
             "먹이 용량 = C++ 처음 지도, 세션마다 규칙 같음.")
    for c in nb[:10]:
        L.append(f"  - 어긋남: {c['what']}")
    L.append("- 옮기며 바뀐 칸(바탕 → 스냅숏): " + ", ".join(f"`{c['key']}` {c['template']} → {c['snapshot']}" for c in convert["changed"]["r7e"]))
    allc = res["checks"] + V["checks"]
    nbad = [c for c in allc if not c["ok"]]
    L.append(f"- 언리얼·파이썬 확인 {len(allc)} 칸 가운데 어긋남 {len(nbad)} (r7e_game_analyze.checks — 두뇌 시작·바꿈 0·경고 0·기록 줄 = 스냅숏·스냅숏 계약·다시 돌림 지문, "
             "+ 다시 읽은 기록 = 저장소 compare.json, 파이썬 메타·산 사슴-스텝 셈)")
    for c in nbad[:10]:
        L.append(f"  - 어긋남: {c['what']}")
    L.append(f"- 파이썬 세계 하나 {V['wall_s']['min']:.0f}~{V['wall_s']['max']:.0f} 초 (합 {V['wall_s']['sum'] / 3600:.1f} 시간·CPU)")
    L.append("")

    def table(rows: dict, title: str, keyset):
        L.append(f"## {title}")
        L.append("")
        L.append("| 묶음 | 칸 | 언리얼 지금 → R7e | 언리얼 차이 (세션 짝 t) | 파이썬 지금 → R7e | 파이썬 차이 (짝 t) | 파이썬 반복 차이 [최소..최대] | 같은 방향 | 크기 z |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for grp, ks in keyset:
            for key in ks:
                if key not in rows:
                    continue
                m = lut[key]
                pct, nd = m["pct"], m["nd"]
                row = rows[key]
                u, p = row["unreal"], row["python"]
                if not any(math.isfinite(x) for x in list(u.values()) + list(p.values())):
                    continue
                rd = row["rep_diff"] or {}
                L.append(f"| {grp} | {m['name']} | {_f(u['cur'], pct, nd)} → {_f(u['r7e'], pct, nd)} | {_d(row['unreal_diff'], pct, nd)} ({_t(row['unreal_pair']['t'])}) | "
                         f"{_f(p['cur'], pct, nd)} → {_f(p['r7e'], pct, nd)} | {_d(row['python_diff'], pct, nd)} ({_t(row['python_pair']['t'])}) | "
                         f"{_d(rd.get('mean'), pct, nd)} [{_d(rd.get('min'), pct, nd)}..{_d(rd.get('max'), pct, nd)}] | {row['direction']} | {_t(row['diff_z'])} |")
        L.append("")

    table(V["rows"], "1. 두뇌 차이 (R7e − 지금) — 모든 지역, calm 거울", PARITY_KEYS)
    L.append("## 2. 두뇌마다 값 — 언리얼 대 파이썬 반복 (calm 거울)")
    L.append("")
    L.append("| 칸 | 두뇌 | 언리얼 | 파이썬 반복 평균 [최소..최대] | z |")
    L.append("|---|---|---|---|---|")
    for key in HEAD_KEYS:
        m = lut[key]
        for b in BRAINS:
            lv = V["rows"][key]["level"].get(b)
            if lv:
                L.append(f"| {m['name']} | {BRAINS[b]['label']} | {_f(V['rows'][key]['unreal'][b], m['pct'], m['nd'])} | {_f(lv['mean'], m['pct'], m['nd'])} "
                         f"[{_f(lv['min'], m['pct'], m['nd'])}..{_f(lv['max'], m['pct'], m['nd'])}] | {_t(lv['z'])} |")
    L.append("")
    L.append("## 3. 지역마다 (R7e − 지금, calm 거울)")
    L.append("")
    L.append("| 지역 | 칸 | 언리얼 지금 → R7e (차이, 세션 짝 t) | 파이썬 지금 → R7e (차이, 짝 t) | 같은 방향 | 크기 z |")
    L.append("|---|---|---|---|---|---|")
    for r in REGIONS:
        for key in REGION_KEYS:
            m = lut[key]
            row = V["region_rows"][r][key]
            u, p = row["unreal"], row["python"]
            L.append(f"| {r} | {m['name']} | {_f(u['cur'], m['pct'], m['nd'])} → {_f(u['r7e'], m['pct'], m['nd'])} ({_d(row['unreal_diff'], m['pct'], m['nd'])}, "
                     f"{_t(row['unreal_pair']['t'])}) | {_f(p['cur'], m['pct'], m['nd'])} → {_f(p['r7e'], m['pct'], m['nd'])} ({_d(row['python_diff'], m['pct'], m['nd'])}, "
                     f"{_t(row['python_pair']['t'])}) | {row['direction']} | {_t(row['diff_z'])} |")
    L.append("")
    L.append("## 4. 시간마다 (기록 줄 60 초마다 누적 — 언리얼 parse_log(t) 대 파이썬 같은 스텝, calm 거울)")
    L.append("")
    L.append("| 초 | 칸 | 언리얼 지금 → R7e (차이) | 파이썬 지금 → R7e (차이) | 파이썬 반복 차이 [최소..최대] | 크기 z |")
    L.append("|---|---|---|---|---|---|")
    for t in map(str, CHECK_S):
        for key in TIME_KEYS:
            m = lut[key]
            row = V["time_rows"][t][key]
            u, p, rd = row["unreal"], row["python"], row["rep_diff"]
            name = m["name"].replace("300 초까지 잡힘", "그때까지 잡힘")
            L.append(f"| {t} | {name} | {_f(u['cur'], m['pct'], m['nd'])} → {_f(u['r7e'], m['pct'], m['nd'])} ({_d(row['unreal_diff'], m['pct'], m['nd'])}) | "
                     f"{_f(p['cur'], m['pct'], m['nd'])} → {_f(p['r7e'], m['pct'], m['nd'])} ({_d(row['python_diff'], m['pct'], m['nd'])}) | "
                     f"{_d(rd['mean'], m['pct'], m['nd'])} [{_d(rd['min'], m['pct'], m['nd'])}..{_d(rd['max'], m['pct'], m['nd'])}] | {_t(row['diff_z'])} |")
    L.append("")
    if "off" in res["variants"]:
        O = res["variants"]["off"]
        ko = len({m for m in O["seeds"]})
        L.append(f"## 5. 참고 — calm 두 규칙을 끈 파이썬 거울 (같은 지도·같은 시드, 반복 {res.get('reps_off', '?')}) 과 calm 거울·언리얼")
        L.append("")
        L.append("calm 거울이 언리얼에 더 가까운지 보는 참고다 (언리얼은 calm 켬 판뿐). 값은 두뇌마다 모든 지역 합.")
        L.append("")
        L.append("| 칸 | 두뇌 | 언리얼 (calm 켬) | 파이썬 calm 켬 | 파이썬 calm 끔 |")
        L.append("|---|---|---|---|---|")
        for key in ("spin", "calm_flips", "rv_stop", "rv_in", "restkeep", "beh_0", "ep_hide", "ep_caught", "gf", "in_shelter", "cover_quick5", "pp_runs", "herd_nn"):
            m = lut[key]
            for b in BRAINS:
                L.append(f"| {m['name']} | {BRAINS[b]['label']} | {_f(V['rows'][key]['unreal'][b], m['pct'], m['nd'])} | {_f(V['rows'][key]['python'][b], m['pct'], m['nd'])} | "
                         f"{_f(O['rows'][key]['python'][b], m['pct'], m['nd'])} |")
        L.append("")
        L.append("- calm 끔 변형의 두뇌 차이 (R7e − 지금, 파이썬): " + ", ".join(
            f"{lut[k]['name']} {_d(O['rows'][k]['python_diff'], lut[k]['pct'], lut[k]['nd'])}" for k in ("ep_hide", "ep_caught", "gf", "spin", "rv_stop")) + f" (시드 {ko} 개)")
        L.append("")
    path.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def _clean(o):
    if isinstance(o, float):
        return None if not math.isfinite(o) else round(o, 7)
    if isinstance(o, (np.floating,)):
        return _clean(float(o))
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, dict):
        return {(k if isinstance(k, str) else "|".join(map(str, k)) if isinstance(k, tuple) else str(k)): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if isinstance(o, set):
        return sorted(o)
    return o


def cmd_compare(a) -> int:
    runs, work = Path(a.runs), Path(a.work)
    sessions = parse_sessions(a.sessions)
    variants = ["calm"] + (["off"] if a.reps_off else [])
    res = compare(runs, work, sessions, a.reps, ["calm"])
    if a.reps_off:
        r2 = compare_variant_only(runs, work, sessions, a.reps_off, res)
        res["variants"]["off"] = r2
        res["reps_off"] = a.reps_off
    convert = json.loads((work / "convert.json").read_text(encoding="utf-8"))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    res["convert"] = convert
    res["unreal_dir_note"] = "원 기록·스냅숏·사슴 줄은 저장소 밖 scratch (r7e_game README '파일')"
    res["python_world_sha1"] = convert.get("world_sha1")
    res["variants_run"] = variants
    slim = {k: v for k, v in res.items() if k not in ("unreal",)}
    slim["unreal"] = {b: dict(pooled=res["unreal"][b]["pooled"], region=res["unreal"][b]["region"], time=res["unreal"][b]["time"]) for b in BRAINS}
    out.with_suffix(".json").write_text(json.dumps(_clean(slim), ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    write_md(out.with_suffix(".md"), res, convert)
    V = res["variants"]["calm"]
    lut = res["lut"]
    for key in HEAD_KEYS:
        row = V["rows"][key]
        m = lut[key]
        print(f"{m['name']}: 언리얼 {_f(row['unreal']['cur'], m['pct'], m['nd'])} → {_f(row['unreal']['r7e'], m['pct'], m['nd'])} · 파이썬 "
              f"{_f(row['python']['cur'], m['pct'], m['nd'])} → {_f(row['python']['r7e'], m['pct'], m['nd'])} · {row['direction']} · z {_t(row['diff_z'])}")
    allc = res["checks"] + V["checks"] + (res["variants"].get("off", {}).get("checks") or [])
    nbad = sum(1 for c in allc if not c["ok"])
    print(f"확인 {len(allc)} 칸 가운데 어긋남 {nbad}")
    return 0 if nbad == 0 else 1


def compare_variant_only(runs: Path, work: Path, sessions: list, reps: int, base: dict) -> dict:
    """calm 끔 변형 (참고): 언리얼 쪽은 calm 판과 같은 기록을 다시 쓴다 (compare 를 한 번 더 부르면 언리얼을 다시 읽으므로, 파이썬 쪽만 셈)."""
    py = work / "py"
    U = base["unreal"]
    W = {}
    metas = []
    for b in BRAINS:
        for s in sessions:
            for r in REGIONS:
                for j in range(reps):
                    p = py / f"{_job_name('off', b, s, r, j)}.json"
                    if not p.exists():
                        raise SystemExit(f"{p.name} 가 없다 — run --variant off --reps {reps} 를 먼저")
                    d = json.loads(p.read_text(encoding="utf-8"))
                    W[(b, s, r, j)] = d
                    metas.append(d["meta"])
    P = {}
    for b in BRAINS:
        P[b] = dict(pooled=_vals([W[(b, s, r, j)]["rec"] for s in sessions for r in REGIONS for j in range(reps)], len(sessions) * reps),
                    unit={(s, j): _vals([W[(b, s, r, j)]["rec"] for r in REGIONS], 1) for s in sessions for j in range(reps)},
                    rep={j: _vals([W[(b, s, r, j)]["rec"] for s in sessions for r in REGIONS], len(sessions)) for j in range(reps)})
    keys = [k for _, ks in PARITY_KEYS for k in ks]
    plan = seed_plan(sessions, reps)
    bad_meta = [m for m in metas if m["seed"] != plan[(m["session"], m["region"], m["rep"])] or m["variant"] != "off"]
    return dict(rows={k: _row(k, U, P, sessions, reps, None) for k in keys}, seeds=sorted({m["seed"] for m in metas}),
                checks=[dict(ok=not bad_meta, what=f"파이썬 calm 끔 세계 {len(metas)} 개 메타 맞음 ({len(bad_meta)} 개 다름)")],
                wall_s=dict(sum=round(sum(m["wall_s"] for m in metas), 1)))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="R7e 게임 시험 — 언리얼 통합 맵 대 파이썬 calm 거울")
    sp = p.add_subparsers(dest="cmd", required=True)
    for name in ("convert", "run", "compare"):
        q = sp.add_parser(name)
        q.add_argument("--runs", required=True, help="r7e_game.py run 의 판 폴더 (it_s<S>_<두뇌>.json·.ecov3.log·.deer.npz)")
        q.add_argument("--work", required=True, help="저장소 밖 작업 폴더 (옮긴 세계·파이썬 세계 JSON)")
        q.add_argument("--sessions", default="20020-20043")
        if name == "run":
            q.add_argument("--reps", type=int, default=6)
            q.add_argument("--workers", type=int, default=12)
            q.add_argument("--variant", choices=VARIANTS, default="calm")
            q.add_argument("--brains", nargs="*", default=list(BRAINS))
        if name == "compare":
            q.add_argument("--reps", type=int, default=6)
            q.add_argument("--reps-off", type=int, default=0)
            q.add_argument("--out", required=True)
    a = p.parse_args(argv)
    return dict(convert=cmd_convert, run=cmd_run, compare=cmd_compare)[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

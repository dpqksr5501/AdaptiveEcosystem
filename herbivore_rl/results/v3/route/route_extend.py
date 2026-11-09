"""두뇌 길 시작 두뇌 route0 — 관측 21 두뇌 obs21zero(R1b-F + 장애물 세 칸 입력 열 0)에 두뇌 길 관측 세 칸(in_panic·shelter_reach·shelter_edge)의 입력 열을 0 으로
붙이고, 행동 칸 4(도주 중 SHELTER)를 칸 1(RUN)보다 로짓 2 작게 연다 (10-22 사용자 결정 '두 길 두뇌로 진행' — 설계
AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 16-6, zero_extend.py 와 같은 꼴).

    # herbivore_rl/ 에서 (모델 zip·두뇌 파일·확인 기록을 함께 쓴다)
    python results/v3/route/route_extend.py
    # 확인만 짧게 / 다른 곳에 (시험)
    python results/v3/route/route_extend.py --verify-steps 300 --out-model <zip> --brain-file <json> --verify-out <json>

무엇:
  - 정책망·가치망 첫 층(관측 → 64)을 21 열 → 24 열로 넓히고 새 세 열을 0 으로 둔다(관측은 0 이상이라 새 칸 × 0 = +0 — 로짓·가치가 같다).
  - 출력층: W2[4] = W2[1], B2[4] = B2[1] − 2. 칸 3 줄(COVER 자리, 판 4 에서 늘 막힘)은 원 두뇌 그대로.
  - 관측 이름 = 관측 21 + 세 칸, 마스크 판 4, 허용 목록 = 먹기·도망·숨기(판 4 는 얼기·잠이 막혀야 한다 — 원 목록의 얼기는 세계가 막던 것이라 결정은 같다).
    ε·엔트로피 배율·시작 로짓 인자는 그대로다(학습은 설정 값으로 다시 만든다 — train_v3.py --init-from-model).
그래서:
  - 배포(argmax): 도주 길 결정 줄 {RUN, SHELTER} 에서 SHELTER 로짓이 RUN 보다 2 작아 늘 RUN — 반사 방향 그대로. 도주 밖은 칸 3·4 를 허용 목록이 막고 새 칸이
    0 이다. 그래서 길을 켠 세계의 route0 궤적 = 길을 끈 세계의 obs21zero 궤적(비트 단위 — 아래 확인 1).
  - 학습 표본(ε 0.05 를 열린 칸에 균등하게 섞음): SHELTER 가 가능한 결정에서 π = (0.881, 0.119), π′ = (0.862, 0.138) (확인 2).
확인(기록 --verify-out, 기본 results/v3/route/brains/v3_r1_g995_s3_obs24route0.verify.json):
  1) 지역 셋(Barren·Forest·Highland, 언리얼 나무 원판 — r4_eval.region_discs) × 탐색 시드 VERIFY_SEEDS, 늑대 포만 켬(G)·끔(N) 거울에서 --verify-steps 스텝:
     길 켬 + route0 과 길 끔 + obs21zero 의 위치·늑대·에너지·덮기·덮기 방향·관측 앞 21 칸·보상·죽음·실행 행동이 스텝마다 같고 도망·야생·사냥 기록이 같다
  2) 길 켬 + route0 의 도주 길 결정(SHELTER 가능 두 칸)에서 π·π′ 의 RUN·SHELTER 평균, 결정 수, 고른 길(늘 RUN)
결정성: 모델 zip 은 SB3 저장 뒤 zip 항목 시각을 1980-01-01 로 고정해 다시 쓴다(zero_extend._deterministic_zip — 같은 코드·같은 원 모델이면 같은 바이트).
두뇌 파일은 언리얼 EcoBrains 에 아직 넣지 않는다(C++ 판 4 로더는 다음 단계) — results/v3/route/brains/ 에 쓴다.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch보다 먼저

import numpy as np  # noqa: E402
import torch as th  # noqa: E402

SRC_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"       # 관측 21 시작 두뇌 (R1b-F + 열 0 — results/v3/r5/zero_extend.py)
OFF_CONFIG = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"            # 길 끈 관측 21 거울
ROUTE_CONFIG = ROOT / "configs" / "v3_wild3_route_mirror.yaml"        # 길 켠 관측 24 거울 (make_route_configs.py)
OUT_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0.zip"
BRAIN_FILE = HERE.parent / "brains" / "v3_r1_g995_s3_obs24route0.json"
VERIFY_OUT = HERE.parent / "brains" / "v3_r1_g995_s3_obs24route0.verify.json"
WORLD_LABEL = ("R1b-F + 장애물·두뇌 길 관측 여섯 칸(입력 열 0) + 길 칸 4 = 칸 1 − 2 — 관측 24·마스크 판 4 시작 두뇌 route0. 배포 결정은 R1b-F 와 같다 "
               "(10-22 results/v3/route/route_extend.py)")
FIRST_LAYERS = ("mlp_extractor.policy_net.0.weight", "mlp_extractor.value_net.0.weight")
ACTION_W, ACTION_B = "action_net.weight", "action_net.bias"
SHELTER_BIAS = -2.0                      # B2[4] = B2[1] − 2 (설계 16-6 — −30 처럼 크게 묶으면 확률이 0 이라 기울기도 0 이다)
ROUTE_ALLOWED = ("graze", "flee", "hide")
VERIFY_SEEDS = (32090, 32091)            # 탐색 시드 칸(32000~32099) — 학습 32000~32049·판정 37000~ 와 겹치지 않는다
VERIFY_STEPS = 1800                      # 4 분
REGIONS = ("Barren", "Forest", "Highland")


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def route_extend(src_model: Path = SRC_MODEL, route_config: Path = ROUTE_CONFIG, out_model: Path = OUT_MODEL) -> dict:
    """원 모델(관측 21·판 2) → route0(관측 24·판 4). 반환: 기록 dict (경로·sha256·관측 이름·검사 값)."""
    from gymnasium import spaces
    from stable_baselines3 import PPO

    from env_v2.config import load_v2_config
    from env_v2.rep_policy import MASK_VERSION_ROUTE, ROUTE_SLOT_RESERVED, ROUTE_SLOT_RUN, ROUTE_SLOT_SHELTER, mask_version_of
    from env_v2.world import ROUTE_OBS_NAMES, obs_names

    zx = _module("_zero_extend_for_route", ROOT / "results" / "v3" / "r5" / "zero_extend.py")
    src_model, route_config, out_model = Path(src_model), Path(route_config), Path(out_model)
    if not src_model.exists():
        raise SystemExit(f"{src_model} 없음 (results/v3/r5/zero_extend.py 가 만든다)")
    prev = th.get_num_threads()
    th.set_num_threads(1)
    try:
        src = PPO.load(str(src_model), device="cpu")
        old_names = tuple(src.policy.rep_obs_names)
        new_names = tuple(obs_names(load_v2_config(route_config)))
        n_old, k = len(old_names), len(ROUTE_OBS_NAMES)
        if new_names[:n_old] != old_names or new_names[n_old:] != tuple(ROUTE_OBS_NAMES):
            raise SystemExit(f"{route_config} 관측 {list(new_names)} 이 원 모델 관측 {list(old_names)} + {list(ROUTE_OBS_NAMES)} 가 아니다")
        if int(src.policy.rep_mask_version) != 2 or mask_version_of(new_names) != MASK_VERSION_ROUTE:
            raise SystemExit("원 모델은 마스크 판 2, 새 관측은 판 4 여야 한다")
        old_state = {kk: v.detach().clone() for kk, v in src.policy.state_dict().items()}

        model = PPO.load(str(src_model), device="cpu")
        old_space = model.observation_space
        low = np.concatenate([old_space.low[:n_old], np.zeros(k, dtype=old_space.dtype), old_space.low[n_old:]])
        high = np.concatenate([old_space.high[:n_old], np.ones(k, dtype=old_space.dtype), old_space.high[n_old:]])
        model.observation_space = spaces.Box(low=low, high=high, dtype=old_space.dtype)
        model.policy_kwargs = dict(model.policy_kwargs, rep_obs_names=list(new_names), rep_mask_version=MASK_VERSION_ROUTE,
                                   rep_allowed=list(ROUTE_ALLOWED))
        model._setup_model()                     # PPO.load 와 같은 길로 새 관측 공간의 정책을 만든다 (가중치는 아래에서 바꾼다)
        new_state = model.policy.state_dict()
        for key, v in old_state.items():
            nv = new_state[key]
            if key in FIRST_LAYERS:
                if tuple(nv.shape) != (v.shape[0], v.shape[1] + k):
                    raise SystemExit(f"{key} 모양 {tuple(nv.shape)} — 기대 {(v.shape[0], v.shape[1] + k)}")
                w = th.zeros_like(nv)
                w[:, :n_old] = v
                new_state[key] = w
            elif tuple(nv.shape) == tuple(v.shape):
                new_state[key] = v.clone()
            else:
                raise SystemExit(f"{key} 모양이 바뀌었다 ({tuple(v.shape)} → {tuple(nv.shape)}) — 첫 층 말고는 그대로여야 한다")
        # 출력층: 칸 4(SHELTER) = 칸 1(RUN) 줄 그대로 + 편향 −2, 칸 3(COVER 자리) 은 원 두뇌 그대로
        new_state[ACTION_W][ROUTE_SLOT_SHELTER] = old_state[ACTION_W][ROUTE_SLOT_RUN]
        new_state[ACTION_B][ROUTE_SLOT_SHELTER] = old_state[ACTION_B][ROUTE_SLOT_RUN] + th.tensor(SHELTER_BIAS, dtype=old_state[ACTION_B].dtype)
        model.policy.load_state_dict(new_state, strict=True)
        model._last_obs = None
        model._last_original_obs = None
        model._last_episode_starts = None

        # 검사: 무작위 정책 입력에서 새 모델(24 칸) 로짓 0~3·가치 = 원 모델(앞 21 칸), 로짓 4 = 로짓 1 − 2
        rng = np.random.default_rng(32092)
        obs = rng.random((256, n_old + k), dtype=np.float32)
        mask = np.ones((256, 5), dtype=np.float32)
        with th.no_grad():
            tn, _ = model.policy.obs_to_tensor(np.concatenate([obs, mask], 1))
            to, _ = src.policy.obs_to_tensor(np.concatenate([obs[:, :n_old], mask], 1))
            lat_n = model.policy.mlp_extractor(model.policy.extract_features(tn))
            lat_o = src.policy.mlp_extractor(src.policy.extract_features(to))
            logit_n = model.policy.action_net(lat_n[0]).numpy()
            logit_o = src.policy.action_net(lat_o[0]).numpy()
            val_n = model.policy.value_net(lat_n[1]).numpy()
            val_o = src.policy.value_net(lat_o[1]).numpy()
        keep = [j for j in range(5) if j != ROUTE_SLOT_SHELTER]
        err_logit = float(np.abs(logit_n[:, keep] - logit_o[:, keep]).max())
        err_value = float(np.abs(val_n - val_o).max())
        gap = logit_n[:, ROUTE_SLOT_RUN] - logit_n[:, ROUTE_SLOT_SHELTER]
        err_gap = float(np.abs(gap - (-SHELTER_BIAS)).max())
        if err_logit > 1e-6 or err_value > 1e-6 or err_gap > 1e-5 or not (gap > 0.0).all():
            raise SystemExit(f"route0 검사 실패: 로짓 차 {err_logit:.3e}, 가치 차 {err_value:.3e}, 칸 1 − 칸 4 = 2 와의 차 {err_gap:.3e}")
        if not th.equal(new_state[ACTION_W][ROUTE_SLOT_RESERVED], old_state[ACTION_W][ROUTE_SLOT_RESERVED]):
            raise SystemExit("칸 3 줄이 바뀌었다")
    finally:
        th.set_num_threads(prev)
    out_model.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(out_model))
    zx._deterministic_zip(out_model)
    return dict(src=src_model, out=out_model, sha256=hashlib.sha256(out_model.read_bytes()).hexdigest(), obs_names=new_names,
                src_sha256=hashlib.sha256(src_model.read_bytes()).hexdigest(), err_logit=err_logit, err_value=err_value, err_gap=err_gap)


# --------------------------------------------------------------------- #
# 확인
# --------------------------------------------------------------------- #


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def region_configs(base, satiation: bool) -> dict:
    """지역마다 거울 설정: 날씨 지역 + 언리얼 나무 원판(results/v3/r4/r4_eval.region_discs), 늑대 포만 켬(G)·끔(N)."""
    r4 = _module("_r4_for_route_extend", ROOT / "results" / "v3" / "r4" / "r4_eval.py")
    discs = r4.region_discs()
    out = {}
    for reg in REGIONS:
        c = _with(base, wild_weather=dict(region=reg), obstacles=dict(fixed=discs[reg]))
        out[reg] = c if satiation else _with(c, wild_satiation=dict(enabled=False))
    return out


def _H(h, *arrs) -> None:
    for a in arrs:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())


def run_deploy(model, cfg, seed: int, steps: int, n_off: int | None = None) -> dict:
    """모델 argmax(배포·판정 모드 rep_learned) 롤아웃 한 판: 스텝마다 세계 기록의 해시(관측은 앞 n_off 칸), 끝 통계, 길 결정 표본(관측 24 세계만)."""
    from env_v2.rep_policy import policy_obs, rep_distribution
    from env_v2.rollout import RepLearned
    from env_v2.world import World

    w = World(cfg, seeds=[int(seed)])
    w.track_flight = True
    pol = RepLearned(model)
    pol.bind_world(w)
    n = w.obs_dim if n_off is None else int(n_off)
    route = "in_panic" in w.obs_names
    hs = hashlib.sha256()
    step_h = []
    pi_dec, pe_dec, n_dec, n_single, picked = [], [], 0, 0, []
    for _ in range(steps):
        obs = w.observe()
        a = pol(obs)
        if route:
            pk = w.rep_peek()
            m = pol.last_mask
            rd = np.asarray(pk["route_decide"], dtype=bool)
            two = rd & m[:, 1] & m[:, 4]
            n_dec += int(rd.sum())
            n_single += int((rd & ~m[:, 4]).sum())
            if two.any():
                pi, pe, _ = rep_distribution(model.policy, policy_obs(obs[two], m[two]))
                pi_dec.append(pi)
                pe_dec.append(pe)
            picked += a[rd, 0].astype(int).tolist()
        o, r, d, to = w.step(a)
        h = hashlib.sha256()
        _H(h, o[:, :n], r, d, to[:, :n], w.pos, w.pred_pos, w.energy, w.wf_mode, w.wf_dir, w.behavior)
        step_h.append(h.hexdigest())
        hs.update(h.digest())
    f = w.flight_stats()
    rt = f.pop("route", None)
    ws = w.wild_stats()
    stats = json.dumps(dict(flight=f, wild=ws, hunt=w.hunt_stats(), rng=str(w.rng.bit_generator.state)), sort_keys=True, default=str)
    hs.update(stats.encode())
    out = dict(hash=hs.hexdigest(), step_hash=step_h, stats=stats, flight=f)
    if route:
        out.update(route=rt, n_dec=n_dec, n_single=n_single, picked=picked,
                   pi=np.concatenate(pi_dec) if pi_dec else np.zeros((0, 5)), pi_eps=np.concatenate(pe_dec) if pe_dec else np.zeros((0, 5)))
    return out


def verify(route_model: Path, src_model: Path = SRC_MODEL, steps: int = VERIFY_STEPS, seeds=VERIFY_SEEDS) -> dict:
    """확인 1·2 (모듈 docstring). 반환: 기록 dict. 하나라도 다르면 멈춘다."""
    from stable_baselines3 import PPO

    from env_v2.config import load_v2_config

    prev = th.get_num_threads()
    th.set_num_threads(1)
    try:
        m_on, m_off = PPO.load(str(route_model), device="cpu"), PPO.load(str(src_model), device="cpu")
        n21 = len(m_off.policy.rep_obs_names)
        rows, PI, PE = [], [], []
        dec_tot = single_tot = 0
        picks: list[int] = []
        for sat in (False, True):
            on_cfgs = region_configs(load_v2_config(ROUTE_CONFIG), sat)
            off_cfgs = region_configs(load_v2_config(OFF_CONFIG), sat)
            for reg in REGIONS:
                for s in seeds:
                    a = run_deploy(m_on, on_cfgs[reg], s, steps, n21)
                    b = run_deploy(m_off, off_cfgs[reg], s, steps)
                    first = next((t for t, (x, y) in enumerate(zip(a["step_hash"], b["step_hash"])) if x != y), None)
                    same = a["hash"] == b["hash"] and first is None
                    rows.append(dict(world="G" if sat else "N", region=reg, seed=int(s), steps=int(steps), same=bool(same), first_diff=first,
                                     hash=a["hash"], started=a["flight"]["started"], reflex_steps=a["flight"]["reflex_steps"],
                                     route_decisions=a["n_dec"], route_choice=int(len(a["pi"])), route_single=a["n_single"],
                                     picked=a["route"]["picked"]))
                    if not same:
                        raise SystemExit(f"route0(길 켬) ≠ obs21zero(길 끔): {rows[-1]}")
                    PI.append(a["pi"])
                    PE.append(a["pi_eps"])
                    dec_tot += a["n_dec"]
                    single_tot += a["n_single"]
                    picks += a["picked"]
    finally:
        th.set_num_threads(prev)
    PI, PE = np.concatenate(PI), np.concatenate(PE)
    if set(picks) - {1}:
        raise SystemExit(f"route0 배포가 RUN 이 아닌 길 칸을 골랐다: {sorted(set(picks))}")
    return dict(route_model=str(Path(route_model).relative_to(ROOT).as_posix()) if Path(route_model).is_relative_to(ROOT) else Path(route_model).name,
                src_model=str(Path(src_model).relative_to(ROOT).as_posix()), steps=int(steps), seeds=[int(s) for s in seeds], regions=list(REGIONS),
                all_same=all(r["same"] for r in rows), runs=rows, route_decisions=int(dec_tot), route_choice=int(len(PI)),
                route_single=int(single_tot), picked_run=int(len(picks)),
                pi_run=float(PI[:, 1].mean()), pi_shelter=float(PI[:, 4].mean()), pi_shelter_min=float(PI[:, 4].min()),
                pi_shelter_max=float(PI[:, 4].max()), pi_eps_run=float(PE[:, 1].mean()), pi_eps_shelter=float(PE[:, 4].mean()),
                pi_other_max=float(PI[:, [0, 2, 3]].max()), expected=dict(pi_shelter=float(1.0 / (1.0 + np.exp(2.0))),
                                                                       pi_eps_shelter=float(0.95 / (1.0 + np.exp(2.0)) + 0.025)))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="두뇌 길 시작 두뇌 route0 (obs21zero + 새 입력 열 0 + 칸 4 = 칸 1 − 2)")
    p.add_argument("--src-model", default=str(SRC_MODEL))
    p.add_argument("--route-config", default=str(ROUTE_CONFIG))
    p.add_argument("--out-model", default=str(OUT_MODEL))
    p.add_argument("--brain-file", default=str(BRAIN_FILE), help="두뇌 파일 (빈 값이면 쓰지 않는다 — 언리얼 EcoBrains 에는 아직 넣지 않는다)")
    p.add_argument("--verify-out", default=str(VERIFY_OUT), help="확인 기록 (빈 값이면 확인하지 않는다)")
    p.add_argument("--verify-steps", type=int, default=VERIFY_STEPS)
    a = p.parse_args(argv)
    r = route_extend(Path(a.src_model), Path(a.route_config), Path(a.out_model))
    print(f"모델: {r['out']}  sha256 {r['sha256'][:16]}  관측 {len(r['obs_names'])}  (로짓 0~3 차 {r['err_logit']:.1e}, 가치 차 {r['err_value']:.1e}, "
          f"칸 1 − 칸 4 − 2 = {r['err_gap']:.1e})")
    if a.brain_file:
        import export_weights_v3 as ew

        d = ew.export_brain_file(Path(a.out_model), Path(a.brain_file), Path(a.route_config), world_label=WORLD_LABEL)
        g = d["golden"]
        kinds = {k: sum(c["kind"] == k for c in g["cases"]) for k in dict.fromkeys(c["kind"] for c in g["cases"])}
        print(f"두뇌 파일: {a.brain_file}  {d['id']}  관측 {d['obs_dim']}  판 {d['mask_version']}  계약 {d['contract_hash']}  골든 {g['count']} {kinds}")
    if a.verify_out:
        v = verify(Path(a.out_model), Path(a.src_model), a.verify_steps)
        v.update(sha256=r["sha256"], src_sha256=r["src_sha256"])
        Path(a.verify_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.verify_out).write_text(json.dumps(v, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        print(f"확인: 길 켬 route0 = 길 끔 obs21zero {sum(x['same'] for x in v['runs'])}/{len(v['runs'])} 판 × {v['steps']} 스텝 (G·N × 지역 셋 × 시드 "
              f"{v['seeds']}), 길 결정 {v['route_decisions']} (두 칸 {v['route_choice']}, RUN 한 칸 {v['route_single']}) 모두 RUN")
        print(f"표본 확률(두 칸 결정 평균): π RUN {v['pi_run']:.4f} SHELTER {v['pi_shelter']:.4f} · π′(ε 0.05) RUN {v['pi_eps_run']:.4f} "
              f"SHELTER {v['pi_eps_shelter']:.4f}  (기대 π SHELTER {v['expected']['pi_shelter']:.4f}, π′ {v['expected']['pi_eps_shelter']:.4f})")
        print(f"기록: {a.verify_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

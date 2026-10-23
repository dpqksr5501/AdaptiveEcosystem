"""R7 시작 두뇌 — 가중치는 그대로 두고 마스크 판만 붙인다 (10-23 사람 결정 '짧게 진단 후 R7' — 설계
AdaptiveEcosystem/Docs/RL_Policy/RL_V3_FLIGHT_ROUTE_DESIGN.md 17절, results/v3/route/route_extend.py 와 같은 꼴).

    # herbivore_rl/ 에서 (모델 zip 둘·판 5 두뇌 파일·확인 기록을 함께 쓴다)
    python results/v3/r7/r7_start.py
    # 확인만 짧게 / 다른 곳에 (시험)
    python results/v3/r7/r7_start.py --verify-steps 300 --out-model <zip> --out-model-off <zip> --brain-file "" --verify-out <json>

무엇:
  - route0m5 = route0(ckpt/v3/v3_r1_g995_s3_obs24route0.zip — 관측 24·판 4)의 정책·가치망을 바이트 그대로 두고 마스크 판만 5(= 판 4 + 반사 밖 두뇌 FLEE
    막음)로 붙인 R7 시작 두뇌 → ckpt/v3/v3_r1_g995_s3_obs24route0m5.zip, 두뇌 파일 results/v3/r7/brains/v3_r1_g995_s3_obs24route0m5.json(계약 관측 24·판 5,
    골든 세계 configs/v3_wild3_route5_mirror.yaml — 언리얼 EcoBrains 에는 넣지 않는다, C++ 판 5 로더는 R7 이 통과한 뒤).
  - obs21zero_m6 = obs21zero(ckpt/v3/v3_r1_g995_s3_obs21zero.zip — 관측 21·판 2)의 가중치 그대로 + 판 6(R7 대조 '길 끔' — 판 2 + 막기 + 덮기 줄 한 칸)
    → ckpt/v3/v3_r1_g995_s3_obs21zero_m6.zip. 판 6 은 파이썬 학습 대조 전용이라 두뇌 파일을 만들지 않는다.
  관측 이름·허용 목록·ε·엔트로피 배율·시작 로짓 인자는 원 모델 그대로다(학습은 설정 값으로 다시 만든다 — train_v3.py --init-from-model 은 판이 같아야 싣는다).
확인(기록 --verify-out, 기본 results/v3/r7/brains/v3_r1_g995_s3_obs24route0m5.verify.json):
  0) 가중치: 새 모델의 state_dict 텐서가 원 모델과 모두 같고(torch.equal), 가중치 바이트 sha256 이 같다. zip 안 policy.pth 바이트가 같은지도 적는다.
  1) 배포 argmax 가 지금 두뇌와 같은가: 지역 셋(Barren·Forest·Highland, 언리얼 나무 원판) × 늑대 포만 켬(G)·끔(N) × 탐색 시드 VERIFY_SEEDS × --verify-steps:
     - 옛 두뇌·옛 세계(route0·판 4 거울, obs21zero·판 2 거울)를 배포(argmax)로 돌리며, 결정마다 같은 로짓에서 새 판 마스크(덮기 밖 결정 행의 칸 1 막음)를
       씌운 argmax 를 함께 낸다. 다른 결정 = 지금 두뇌가 덮기 밖 결정에서 FLEE 를 고른 것 — 그 수와 몫(덮기 밖 결정당), 대신 고른 행동을 적는다.
       판 6 은 덮기(도주·웅크림) 줄도 한 칸으로 바뀌지만 실행기가 덮기 중 요청을 FLEE·HIDE 로 바꾸므로 궤적과 무관하다(따로 적지 않는다).
     - 새 두뇌·새 세계(route0m5·판 5 거울, obs21zero_m6·판 6 세계)를 배포로 돌려 궤적(산 사슴의 관측·보상·에너지·덮기·실행 행동, 위치·죽음·늑대,
       도망·야생·사냥 기록)이 옛 판과 스텝마다 같은지, 처음 달라진 스텝, 시작한 도망·두뇌 스스로 뛴 도망(길 none — 반사 스텝이 없는 도망)과 세계의 막음
       통계(덮기 밖 결정에서 두뇌가 낸 FLEE — 늘 0)를 적는다. 산 사슴의 다른 결정이 0 인 판은 궤적이 비트 단위로 같아야 한다(아니면 멈춘다).
       부활 없는 거울의 죽은 슬롯은 마스크의 덮기 밖 결정 행에 남아 그 argmax 만 바뀔 수 있다(시체는 움직이지 않고 아무것도 바꾸지 않는다 — 해시에서 빼고
       dead_slot_diff 로 따로 센다).
결정성: 모델 zip 은 SB3 저장 뒤 zip 항목 시각을 1980-01-01 로 고정해 다시 쓴다(zero_extend._deterministic_zip — 같은 코드·같은 원 모델이면 같은 바이트).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch보다 먼저

import numpy as np  # noqa: E402
import torch as th  # noqa: E402

ROUTE0 = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0.zip"            # 관측 24·판 4 (results/v3/route/route_extend.py)
OBS21ZERO = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"          # 관측 21·판 2 (results/v3/r5/zero_extend.py)
OUT_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs24route0m5.zip"      # R7 시작 두뇌 (판 5)
OUT_MODEL_OFF = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero_m6.zip"   # R7 대조 '길 끔' 시작 두뇌 (판 6)
ROUTE_CONFIG = ROOT / "configs" / "v3_wild3_route_mirror.yaml"           # 판 4 거울
ROUTE5_CONFIG = ROOT / "configs" / "v3_wild3_route5_mirror.yaml"         # 판 5 거울 (make_r7_configs.py)
OBS_CONFIG = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"               # 판 2 거울 (판 6 세계 = 이 거울 + brain_flee_outside_reflex false)
BRAIN_FILE = HERE.parent / "brains" / "v3_r1_g995_s3_obs24route0m5.json"
VERIFY_OUT = HERE.parent / "brains" / "v3_r1_g995_s3_obs24route0m5.verify.json"
WORLD_LABEL = ("route0 가중치 그대로(R1b-F + 장애물·두뇌 길 관측 여섯 칸 입력 열 0 + 길 칸 4 = 칸 1 − 2) + 마스크 판 5(반사 밖 두뇌 FLEE 막음) — R7 시작 두뇌 "
               "route0m5 (10-23 results/v3/r7/r7_start.py)")
VERIFY_SEEDS = (32090, 32091)            # 탐색 시드 칸(32000~32099) — route_extend.py 확인과 같은 시드(학습 32000~32049·판정 37000~ 와 겹치지 않는다)
VERIFY_STEPS = 1800                      # 4 분
REGIONS = ("Barren", "Forest", "Highland")
VERSIONS = {"route0m5": (4, 5), "obs21zero_m6": (2, 6)}     # 이름 → (원 판, 새 판)


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _weights_sha(state: dict) -> str:
    h = hashlib.sha256()
    for k in sorted(state):
        v = state[k].detach().cpu().contiguous()
        h.update(k.encode())
        h.update(str(v.dtype).encode())
        h.update(str(tuple(v.shape)).encode())
        h.update(v.numpy().tobytes())
    return h.hexdigest()


def _zip_entry(path: Path, name: str) -> bytes:
    with zipfile.ZipFile(path) as z:
        return z.read(name)


def relabel(src_model: Path, out_model: Path, new_version: int, src_version: int) -> dict:
    """원 모델의 가중치를 그대로 두고 마스크 판만 new_version 으로 붙인 zip 을 쓴다. 반환: 기록 dict (경로·sha256·가중치 지문·검사 값)."""
    from stable_baselines3 import PPO

    from env_v2.rep_policy import check_model_mask_version

    zx = _module("_zero_extend_for_r7", ROOT / "results" / "v3" / "r5" / "zero_extend.py")
    src_model, out_model = Path(src_model), Path(out_model)
    if not src_model.exists():
        raise SystemExit(f"{src_model} 없음 (route0 은 results/v3/route/route_extend.py, obs21zero 는 results/v3/r5/zero_extend.py 가 만든다)")
    prev = th.get_num_threads()
    th.set_num_threads(1)
    try:
        src = PPO.load(str(src_model), device="cpu")
        names = tuple(src.policy.rep_obs_names)
        if int(src.policy.rep_mask_version) != int(src_version):
            raise SystemExit(f"{src_model.name} 의 마스크 판이 {src.policy.rep_mask_version} 이다 — {src_version} 이어야 한다")
        check_model_mask_version(new_version, names)          # 판 5 는 관측 24(in_panic), 판 6 은 in_panic 없는 관측
        old_state = {k: v.detach().clone() for k, v in src.policy.state_dict().items()}
        model = PPO.load(str(src_model), device="cpu")
        model.policy_kwargs = dict(model.policy_kwargs, rep_mask_version=int(new_version))
        model._setup_model()                     # PPO.load 와 같은 길로 새 판의 정책을 만든다 (가중치는 아래에서 원 모델 것을 싣는다)
        model.policy.load_state_dict(old_state, strict=True)
        model._last_obs = None
        model._last_original_obs = None
        model._last_episode_starts = None
    finally:
        th.set_num_threads(prev)
    out_model.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(out_model))
    zx._deterministic_zip(out_model)
    # 다시 읽어 판·가중치를 본다
    new = PPO.load(str(out_model), device="cpu")
    if int(new.policy.rep_mask_version) != int(new_version) or tuple(new.policy.rep_obs_names) != names:
        raise SystemExit(f"{out_model.name}: 판 {new.policy.rep_mask_version} — {new_version} 이어야 한다")
    if tuple(new.policy.rep_allowed) != tuple(src.policy.rep_allowed):
        raise SystemExit(f"{out_model.name}: 허용 목록이 바뀌었다")
    ns = new.policy.state_dict()
    if set(ns) != set(old_state) or not all(th.equal(ns[k], old_state[k]) for k in old_state):
        raise SystemExit(f"{out_model.name}: 가중치가 원 모델과 다르다")
    return dict(src=src_model, out=out_model, src_version=int(src_version), version=int(new_version), obs_dim=len(names),
                allowed=list(new.policy.rep_allowed), sha256=hashlib.sha256(out_model.read_bytes()).hexdigest(),
                src_sha256=hashlib.sha256(src_model.read_bytes()).hexdigest(), weights_sha256=_weights_sha(ns),
                src_weights_sha256=_weights_sha(old_state),
                policy_pth_same=_zip_entry(out_model, "policy.pth") == _zip_entry(src_model, "policy.pth"))


# --------------------------------------------------------------------- #
# 확인 — 배포 argmax
# --------------------------------------------------------------------- #


def _H(h, *arrs) -> None:
    for a in arrs:
        a = np.ascontiguousarray(a)
        h.update(str(a.dtype).encode())
        h.update(str(a.shape).encode())
        h.update(a.tobytes())


def deploy(model, cfg, seed: int, steps: int, probe: bool) -> dict:
    """모델 argmax(배포·판정 모드 rep_learned) 롤아웃 한 판. 스텝마다 세계 기록의 해시(산 사슴 — 스텝 첫머리에 산 슬롯 — 의 관측·보상·에너지·덮기·덮기
    방향·실행 행동, 모든 슬롯의 죽음·위치, 늑대 위치), 끝 통계. 부활 없는 거울의 죽은 슬롯은 해시에서 뺀다 — 시체는 움직이지 않고 그 행동은 아무것도 바꾸지
    않지만(C++ 처리기는 목록에서 뺀다) 마스크의 덮기 밖 결정 행에는 들어 있어 판 5·6 에서 죽은 슬롯의 argmax 만 달라질 수 있다(dead_diff 로 따로 센다).
    probe 면 결정마다 같은 로짓에 '덮기 밖 결정 행의 칸 1 막음'을 씌운 argmax 를 함께 내어 산 사슴의 다른 결정(= 덮기 밖 결정에서 FLEE 를 고름)을 센다
    (세계는 원래 argmax 로 돈다)."""
    from env_v2.rep_policy import policy_obs, rep_argmax
    from env_v2.repertoire import BEHAVIOR_NAMES, FLEE
    from env_v2.rollout import RepLearned
    from env_v2.world import WF_PANIC, WF_SHELTER, World

    w = World(cfg, seeds=[int(seed)])
    w.track_flight = True
    pol = RepLearned(model)
    pol.bind_world(w)
    hs = hashlib.sha256()
    step_h = []
    free_n = diff_n = dead_diff = 0
    repl = Counter()
    for _ in range(steps):
        obs = w.observe()
        live = np.ones(w.N, dtype=bool) if w.alive is None else np.asarray(w.alive, dtype=bool).copy()
        if probe:
            pk = w.rep_peek()                   # 순수 (세계·난수 그대로)
        a = pol(obs)
        if probe:
            m = pol.last_mask
            over = ((w.wf_mode == WF_PANIC) | (w.wf_mode == WF_SHELTER)) & live
            reads = np.asarray(pk["reads"], dtype=bool)
            free = reads & ~over & live
            free_n += int(free.sum())
            dead_diff += int((reads & ~live & (a[:, 0] == float(FLEE))).sum())
            ch = free & (a[:, 0] == float(FLEE))
            if ch.any():
                mg = m[ch].copy()
                mg[:, FLEE] = False
                a2 = rep_argmax(model.policy, policy_obs(np.asarray(obs)[ch], mg))
                diff_n += int(ch.sum())
                repl.update(BEHAVIOR_NAMES[int(v)] for v in a2.tolist())
        o, r, d, to = w.step(a)
        h = hashlib.sha256()
        _H(h, o[live], r[live], d, to[live], w.pos, w.pred_pos, w.energy[live], w.wf_mode[live], w.wf_dir[live], w.behavior[live])
        step_h.append(h.hexdigest())
        hs.update(h.digest())
    f = w.flight_stats()
    rt = f.pop("route", None)
    gate = w.flee_gate_stats() if w._fb else None
    f.pop("hide", None)
    stats = json.dumps(dict(flight=f, wild=w.wild_stats(), hunt=w.hunt_stats(), rng=str(w.rng.bit_generator.state)), sort_keys=True, default=str)
    hs.update(stats.encode())
    none = int(sum(rt["by_route"]["none"]["n"].values())) if rt is not None else None
    return dict(hash=hs.hexdigest(), step_hash=step_h, started=int(f["started"]), reflex_steps=int(f["reflex_steps"]), none_flights=none,
                free=free_n, diff=diff_n, dead_diff=dead_diff, repl=dict(repl), gate=gate)


def verify(steps: int = VERIFY_STEPS, seeds=VERIFY_SEEDS, out_model: Path = OUT_MODEL, out_model_off: Path = OUT_MODEL_OFF) -> dict:
    """확인 1 (모듈 docstring). 반환: 기록 dict. 다른 결정이 0 인 판의 궤적이 다르면 멈춘다."""
    from stable_baselines3 import PPO

    from env_v2.config import load_v2_config

    rx = _module("_route_extend_for_r7", ROOT / "results" / "v3" / "route" / "route_extend.py")
    prev = th.get_num_threads()
    th.set_num_threads(1)
    pairs = {
        "route0m5": (PPO.load(str(ROUTE0), device="cpu"), load_v2_config(ROUTE_CONFIG), PPO.load(str(out_model), device="cpu"),
                     load_v2_config(ROUTE5_CONFIG)),
        "obs21zero_m6": (PPO.load(str(OBS21ZERO), device="cpu"), load_v2_config(OBS_CONFIG), PPO.load(str(out_model_off), device="cpu"),
                         _with(load_v2_config(OBS_CONFIG), wild_flight=dict(brain_flee_outside_reflex=False))),
    }
    out = {}
    try:
        for name, (m_old, base_old, m_new, base_new) in pairs.items():
            rows = []
            for sat in (False, True):
                old_cfgs, new_cfgs = rx.region_configs(base_old, sat), rx.region_configs(base_new, sat)
                for reg in REGIONS:
                    for s in seeds:
                        a = deploy(m_old, old_cfgs[reg], s, steps, probe=True)
                        b = deploy(m_new, new_cfgs[reg], s, steps, probe=False)
                        first = next((t for t, (x, y) in enumerate(zip(a["step_hash"], b["step_hash"])) if x != y), None)
                        same = a["hash"] == b["hash"] and first is None
                        row = dict(world="G" if sat else "N", region=reg, seed=int(s), steps=int(steps), same=bool(same), first_diff=first,
                                   free_decisions=a["free"], argmax_diff=a["diff"], dead_slot_diff=a["dead_diff"], repl=a["repl"],
                                   started_old=a["started"], started_new=b["started"],
                                   none_old=a["none_flights"], none_new=b["none_flights"], gate_new=b["gate"])
                        if a["diff"] == 0 and not same:
                            raise SystemExit(f"{name}: 다른 결정이 없는데 궤적이 다르다 — {row}")
                        if b["gate"] is None or b["gate"]["brain_flee"] != 0:
                            raise SystemExit(f"{name}: 새 판 세계에서 덮기 밖 두뇌 FLEE 가 0 이 아니다 — {row}")
                        rows.append(row)
            free = sum(r["free_decisions"] for r in rows)
            diff = sum(r["argmax_diff"] for r in rows)
            repl = Counter()
            for r in rows:
                repl.update(r["repl"])
            out[name] = dict(versions=list(VERSIONS[name]), runs=rows, worlds=len(rows), all_same=all(r["same"] for r in rows),
                             same_worlds=sum(r["same"] for r in rows), free_decisions=int(free), argmax_diff=int(diff),
                             dead_slot_diff=sum(r["dead_slot_diff"] for r in rows),
                             argmax_diff_per_1000_free=1000.0 * diff / free if free else float("nan"), repl=dict(repl),
                             # 두뇌 스스로 뛴 도망(길 none)은 길 기록이 있는 세계(판 4·5)만 센다 — 판 2·6 세계는 None
                             none_old=_sum_or_none(r["none_old"] for r in rows), none_new=_sum_or_none(r["none_new"] for r in rows),
                             started_old=sum(r["started_old"] for r in rows), started_new=sum(r["started_new"] for r in rows),
                             gate_free_new=sum(r["gate_new"]["free_decisions"] for r in rows),
                             gate_flee_new=sum(r["gate_new"]["brain_flee"] for r in rows))
    finally:
        th.set_num_threads(prev)
    return dict(steps=int(steps), seeds=[int(s) for s in seeds], regions=list(REGIONS), pairs=out)


def _sum_or_none(xs):
    xs = list(xs)
    return None if any(x is None for x in xs) else int(sum(xs))


def _rel(p: Path) -> str:
    p = Path(p).resolve()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else p.name


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="R7 시작 두뇌 (route0 → 판 5 route0m5, obs21zero → 판 6 obs21zero_m6 — 가중치 그대로)")
    p.add_argument("--out-model", default=str(OUT_MODEL))
    p.add_argument("--out-model-off", default=str(OUT_MODEL_OFF))
    p.add_argument("--brain-file", default=str(BRAIN_FILE), help="판 5 두뇌 파일 (빈 값이면 쓰지 않는다 — 언리얼 EcoBrains 에는 넣지 않는다)")
    p.add_argument("--verify-out", default=str(VERIFY_OUT), help="확인 기록 (빈 값이면 확인하지 않는다)")
    p.add_argument("--verify-steps", type=int, default=VERIFY_STEPS)
    a = p.parse_args(argv)
    recs = {"route0m5": relabel(ROUTE0, Path(a.out_model), 5, 4), "obs21zero_m6": relabel(OBS21ZERO, Path(a.out_model_off), 6, 2)}
    for k, r in recs.items():
        print(f"{k}: {_rel(r['out'])}  판 {r['src_version']} → {r['version']}  관측 {r['obs_dim']}  sha256 {r['sha256'][:16]}  가중치 지문 {r['weights_sha256'][:16]} "
              f"(원 모델 {r['src_weights_sha256'][:16]} — {'같다' if r['weights_sha256'] == r['src_weights_sha256'] else '다르다'}), "
              f"zip 안 policy.pth 바이트 {'같다' if r['policy_pth_same'] else '다르다'}")
    brain = None
    if a.brain_file:
        import export_weights_v3 as ew

        d = ew.export_brain_file(Path(a.out_model), Path(a.brain_file), ROUTE5_CONFIG, world_label=WORLD_LABEL)
        g = d["golden"]
        kinds = {k: sum(c["kind"] == k for c in g["cases"]) for k in dict.fromkeys(c["kind"] for c in g["cases"])}
        brain = dict(path=_rel(Path(a.brain_file)), id=d["id"], contract_hash=d["contract_hash"], mask_version=d["mask_version"], golden=g["count"],
                     kinds=kinds, weights_sha256=d["weights_sha256"])
        print(f"두뇌 파일: {_rel(Path(a.brain_file))}  {d['id']}  관측 {d['obs_dim']}  판 {d['mask_version']}  계약 {d['contract_hash']}  골든 {g['count']} {kinds}")
    if a.verify_out:
        v = verify(a.verify_steps, VERIFY_SEEDS, Path(a.out_model), Path(a.out_model_off))
        v["models"] = {k: dict(out=_rel(r["out"]), src=_rel(r["src"]), src_version=r["src_version"], version=r["version"], sha256=r["sha256"],
                               src_sha256=r["src_sha256"], weights_sha256=r["weights_sha256"], src_weights_sha256=r["src_weights_sha256"],
                               weights_same=r["weights_sha256"] == r["src_weights_sha256"], policy_pth_same=r["policy_pth_same"],
                               allowed=r["allowed"]) for k, r in recs.items()}
        v["brain_file"] = brain
        Path(a.verify_out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.verify_out).write_text(json.dumps(v, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        for k, x in v["pairs"].items():
            print(f"확인 {k} (판 {x['versions'][0]} → {x['versions'][1]}): 궤적 같은 판 {x['same_worlds']}/{x['worlds']} (G·N × 지역 셋 × 시드 {v['seeds']} × "
                  f"{v['steps']} 스텝), 덮기 밖 결정 {x['free_decisions']:,} 가운데 argmax 가 달라지는 결정 {x['argmax_diff']} "
                  f"({x['argmax_diff_per_1000_free']:.4f} / 1000, 대신 {x['repl'] or '—'}; 죽은 슬롯만 {x['dead_slot_diff']}), "
                  + (f"두뇌 스스로 뛴 도망(길 none) {x['none_old']} → {x['none_new']}, " if x["none_old"] is not None else "")
                  + f"시작한 도망 {x['started_old']} → {x['started_new']}, 새 판 세계의 덮기 밖 두뇌 FLEE {x['gate_flee_new']}")
        print(f"기록: {_rel(Path(a.verify_out))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

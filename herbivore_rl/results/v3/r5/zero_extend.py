"""R5 관측 21 시작 두뇌 — 지금 게임 두뇌 R1b-F 의 가중치에 새 관측 세 칸(escape_room·obstacle_near·threat_hidden)의 입력 열을 0 으로 붙인다
(10-19 사용자 '일단 두뇌가 나무 같은 장애물을 인지할 수 있게 바꿔', 계획서 AdaptiveEcosystem/Docs/RL_Policy/RL_V2_PLAN.md 10-19 (16) (b),
계약 Docs/RL_Policy/POLICY_CONTRACT_V3.md 2-4).

    # herbivore_rl/ 에서 (모델 zip 과 두뇌 파일을 함께 쓴다)
    python results/v3/r5/zero_extend.py
    # 다른 곳에 (시험)
    python results/v3/r5/zero_extend.py --out-model <zip> --brain-file <json>

무엇: 정책망·가치망의 첫 층(관측 → 64)만 18 열 → 21 열로 넓히고 새 세 열을 0 으로 둔다. 다른 가중치·편향·허용 목록(먹기·도망·숨기·얼기 — 얼기는 세계가 막아
R1b-F)·ε·엔트로피 배율은 그대로다. 그래서 관측 21 세계에서 이 모델의 로짓은 앞 18 칸만 본 R1b-F 의 로짓과 같다(새 칸 × 0 = +0 — 관측은 0 이상).
쓰는 곳 둘:
  (1) 언리얼 배관 확인 두뇌 `AdaptiveEcosystem/EcoBrains/v3_r1_g995_s3_obs21zero.json` (`export_weights_v3.py --brain-file` 과 같은 꼴, 골든 세계는 관측 21
      거울 configs/v3_wild3_obs_mirror.yaml). 이 두뇌를 넣으면 통합 모드가 관측 21 을 만들고 결정은 내장 R1b-F 와 같아야 한다(언리얼 시험·헤드리스 확인).
  (2) R5 이어 배우기 시작점 `ckpt/v3/v3_r1_g995_s3_obs21zero.zip` (train_v3.py --init-from-model — 관측 이름이 관측 21 설정과 같아 strict 로 실린다).
결정성: 모델 zip 은 SB3 저장 뒤 zip 항목 시각을 1980-01-01 로 고정해 다시 쓴다(같은 코드·같은 원 모델이면 같은 바이트 — tests/test_zero_brain_obs21.py).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import env.torch_init  # noqa: E402,F401  ← torch보다 먼저

import numpy as np  # noqa: E402
import torch as th  # noqa: E402

SRC_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_20m.zip"           # 지금 게임 두뇌 (R1b s3 — 통합 모드는 얼기를 세계가 막아 R1b-F)
OBS_CONFIG = ROOT / "configs" / "v3_wild3_obs_mirror.yaml"           # 관측 21 거울 세계 (언리얼과 같은 세계 + 세 칸)
OUT_MODEL = ROOT / "ckpt" / "v3" / "v3_r1_g995_s3_obs21zero.zip"
BRAIN_FILE = ROOT.parent / "AdaptiveEcosystem" / "EcoBrains" / "v3_r1_g995_s3_obs21zero.json"
WORLD_LABEL = ("R1b-F + 장애물 관측 세 칸(입력 열 0) — 관측 21 배관 확인·R5 이어 배우기 시작점. 결정은 R1b-F 와 같다 "
               "(10-19 results/v3/r5/zero_extend.py)")
FIRST_LAYERS = ("mlp_extractor.policy_net.0.weight", "mlp_extractor.value_net.0.weight")   # 관측을 받는 두 층 (특징 추출기 공유 — RepObsSlice)
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def _canonical_data(raw: bytes) -> bytes:
    """SB3 'data' JSON 의 직렬화 항목(':serialized:' 가 있는 dict)에서 사람이 읽을 설명 칸을 뺀다 — 설명 칸에는 메모리 주소가 들어 있어 실행마다
    바뀐다. 읽기(SB3 json_to_data)는 ':serialized:' 만 쓰므로 모델은 그대로다."""
    import json

    d = json.loads(raw)
    for k, v in d.items():
        if isinstance(v, dict) and ":serialized:" in v:
            d[k] = {kk: v[kk] for kk in (":type:", ":serialized:") if kk in v}
    return json.dumps(d, indent=4).encode()


def _deterministic_zip(path: Path) -> None:
    """zip 항목을 같은 순서·같은 압축으로 다시 쓰되 시각을 고정하고 'data' 를 정규 꼴로 (SB3 save 는 항목마다 지금 시각을, 설명 칸에 메모리 주소를 적는다)."""
    with zipfile.ZipFile(path) as z:
        items = [(i.filename, i.compress_type, z.read(i.filename)) for i in z.infolist()]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as out:
        for name, comp, data in items:
            if name == "data":
                data = _canonical_data(data)
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_TIME)
            info.compress_type = comp
            info.external_attr = 0o644 << 16
            out.writestr(info, data)
    path.write_bytes(buf.getvalue())


def zero_extend(src_model: Path = SRC_MODEL, obs_config: Path = OBS_CONFIG, out_model: Path = OUT_MODEL) -> dict:
    """원 모델(관측 18) → 관측 21 모델 (새 열 0). 반환: 기록 dict (경로·sha256·관측 이름·검사 값)."""
    from gymnasium import spaces
    from stable_baselines3 import PPO

    from env_v2.config import load_v2_config
    from env_v2.rep_policy import mask_version_of
    from env_v2.world import OBSTACLE_OBS_NAMES, obs_names

    src_model, obs_config, out_model = Path(src_model), Path(obs_config), Path(out_model)
    if not src_model.exists():
        raise SystemExit(f"{src_model} 없음")
    prev = th.get_num_threads()
    th.set_num_threads(1)
    try:
        src = PPO.load(str(src_model), device="cpu")
        old_names = tuple(src.policy.rep_obs_names)
        new_names = tuple(obs_names(load_v2_config(obs_config)))
        n_old = len(old_names)
        if new_names[:n_old] != old_names or new_names[n_old:] != tuple(OBSTACLE_OBS_NAMES):
            raise SystemExit(f"{obs_config} 관측 {list(new_names)} 이 원 모델 관측 {list(old_names)} + {list(OBSTACLE_OBS_NAMES)} 가 아니다")
        if mask_version_of(new_names) != int(src.policy.rep_mask_version):
            raise SystemExit("마스크 판이 바뀐다 — 관측 21 은 판 2 그대로여야 한다")
        old_state = {k: v.detach().clone() for k, v in src.policy.state_dict().items()}

        model = PPO.load(str(src_model), device="cpu")
        k = len(OBSTACLE_OBS_NAMES)
        old_space = model.observation_space
        low = np.concatenate([old_space.low[:n_old], np.zeros(k, dtype=old_space.dtype), old_space.low[n_old:]])
        high = np.concatenate([old_space.high[:n_old], np.ones(k, dtype=old_space.dtype), old_space.high[n_old:]])
        model.observation_space = spaces.Box(low=low, high=high, dtype=old_space.dtype)
        model.policy_kwargs = dict(model.policy_kwargs, rep_obs_names=list(new_names))
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
                new_state[key] = v
            else:
                raise SystemExit(f"{key} 모양이 바뀌었다 ({tuple(v.shape)} → {tuple(nv.shape)}) — 첫 층 말고는 그대로여야 한다")
        model.policy.load_state_dict(new_state, strict=True)
        # 원 모델 롤아웃의 마지막 관측(관측 18 + 마스크 모양)은 새 모델에 뜻이 없다 — 이어 배우기는 reset 으로 다시 만든다
        model._last_obs = None
        model._last_original_obs = None
        model._last_episode_starts = None

        # 검사: 무작위 정책 입력에서 새 모델(21 칸) 로짓·가치 = 원 모델(앞 18 칸) 로짓·가치
        rng = np.random.default_rng(32091)
        obs21 = rng.random((256, n_old + k), dtype=np.float32)
        mask = np.ones((256, 5), dtype=np.float32)
        p_new = np.concatenate([obs21, mask], 1)
        p_old = np.concatenate([obs21[:, :n_old], mask], 1)
        with th.no_grad():
            tn, _ = model.policy.obs_to_tensor(p_new)
            to, _ = src.policy.obs_to_tensor(p_old)
            lat_n = model.policy.mlp_extractor(model.policy.extract_features(tn))
            lat_o = src.policy.mlp_extractor(src.policy.extract_features(to))
            logit_n = model.policy.action_net(lat_n[0]).numpy()
            logit_o = src.policy.action_net(lat_o[0]).numpy()
            val_n = model.policy.value_net(lat_n[1]).numpy()
            val_o = src.policy.value_net(lat_o[1]).numpy()
        err_logit = float(np.abs(logit_n - logit_o).max())
        err_value = float(np.abs(val_n - val_o).max())
        if err_logit > 1e-6 or err_value > 1e-6:
            raise SystemExit(f"새 열 0 인데 로짓·가치가 다르다 (최대 {err_logit:.3e}·{err_value:.3e})")
    finally:
        th.set_num_threads(prev)
    out_model.parent.mkdir(parents=True, exist_ok=True)
    model.save(str(out_model))
    _deterministic_zip(out_model)
    return dict(src=src_model, out=out_model, sha256=hashlib.sha256(out_model.read_bytes()).hexdigest(), obs_names=new_names,
                err_logit=err_logit, err_value=err_value)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="R5 관측 21 시작 두뇌 (R1b-F + 새 입력 열 0)")
    p.add_argument("--src-model", default=str(SRC_MODEL))
    p.add_argument("--obs-config", default=str(OBS_CONFIG))
    p.add_argument("--out-model", default=str(OUT_MODEL))
    p.add_argument("--brain-file", default=str(BRAIN_FILE), help="언리얼 두뇌 파일 (빈 값이면 쓰지 않는다)")
    a = p.parse_args(argv)
    r = zero_extend(Path(a.src_model), Path(a.obs_config), Path(a.out_model))
    print(f"모델: {r['out']}  sha256 {r['sha256'][:16]}  관측 {len(r['obs_names'])}  (새 열 0 — 로짓 차 {r['err_logit']:.1e}, 가치 차 {r['err_value']:.1e})")
    if a.brain_file:
        import export_weights_v3 as ew

        d = ew.export_brain_file(Path(a.out_model), Path(a.brain_file), Path(a.obs_config), world_label=WORLD_LABEL)
        g = d["golden"]
        print(f"두뇌 파일: {a.brain_file}  {d['id']}  관측 {d['obs_dim']}  계약 {d['contract_hash']}  골든 {g['count']} (세계 {g['world_config']} 시드 {g['seed']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

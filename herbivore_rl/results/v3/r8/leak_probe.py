"""R8 학습 전 검토(11-05) — 이름표 새는 길 점검: 관측 동물 칸 하나(11 칸)만으로 늑대·짐승을 맞히는 비선형(나무) 분류기를
늑대의 숨은 상태(배회·먹기·탈진·덮침·추격·잠행)·짐승 상태(돌아다님·풀 뜯기·내달리기)별로 돌린다. 세계 절반 학습·절반 시험(개발 시드 41400~41439).
쉬는 상태(배회·탈진·먹기) 대 짐승이 0.5 근처면 겉모습·쉬는 몸놀림에 이름표가 없다. 사냥 상태(잠행·덮침·추격)의 차이는 설계 3-5 가 둔 행동 단서다.
끝에 P3 표본(가장 가까운 느낀 동물, 15 단위 안)의 늑대 상태 몫을 적는다.

`herbivore_rl/` 에서:  python results/v3/r8/leak_probe.py configs/v3_r8_pilot.yaml 2000 mix   (정책: eat | mix(먹기 80%·무작위 20%) | 모델 zip)
환경 변수 R8_PATCH='{"wolves": {"tired_speed": 0.2}}' 로 설정을 덮어 고치기 전 세계를 잴 수 있다. 약 3 분.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]          # herbivore_rl/
sys.path.insert(0, str(ROOT))
import env.torch_init  # noqa
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

from env_v2.r8_world import A0, NA, N_SLOTS, N_ACTIONS, K_WOLF, K_BEAST, R8World, load_r8_config, EAT

cfg_path = sys.argv[1]
steps = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
pol = sys.argv[3] if len(sys.argv) > 3 else "mix"
cfg = load_r8_config(ROOT / cfg_path)
import json as _j, os as _os
if _os.environ.get("R8_PATCH"):
    from env_v2.r8_world import override as _ov
    cfg = _ov(cfg, _j.loads(_os.environ["R8_PATCH"]))
seeds = list(range(41400, 41440))
w = R8World(cfg, seeds)
rng = np.random.default_rng(0)
model = None
if pol.endswith(".zip"):
    from stable_baselines3 import PPO
    model = PPO.load(str(ROOT / pol), device="cpu")

rows = []
# mode of each animal DURING the last sub-step (behaviour that produced adisp/ahead seen in the obs)
st = dict(eat=w.eat_left.copy(), tired=w.tired_left.copy(), pl=w.pounce_left.copy())
w.mode = np.full(w.kind.shape, -1)


def hook(wd, dead, ck):
    wolf = wd.kind == K_WOLF
    eat_ = st["eat"] > 0
    tired = (st["tired"] > 0) & ~eat_
    aim = (wd.target >= 0) & ~eat_ & ~tired
    pounce = aim & wd.stalker & ((st["pl"] > 0) | (wd.lock >= 0) | (wd.pounce_left != st["pl"]))
    stalk = aim & wd.stalker & ~pounce
    chase = aim & ~wd.stalker
    roam = ~eat_ & ~tired & ~aim
    m = np.full(wd.kind.shape, -1)
    m = np.where(wolf & eat_, 1, m)
    m = np.where(wolf & tired, 2, m)
    m = np.where(wolf & pounce, 3, m)
    m = np.where(wolf & chase, 4, m)
    m = np.where(wolf & stalk, 5, m)
    m = np.where(wolf & roam, 0, m)
    m = np.where(wd.kind == K_BEAST, 10 + wd.bstate, m)
    wd.mode = m
    st["eat"], st["tired"], st["pl"] = wd.eat_left.copy(), wd.tired_left.copy(), wd.pounce_left.copy()


w.step_hook = hook
for t in range(steps // w.D):
    obs = w.observe()
    kind = w.kind.copy()
    code = w.mode.copy()
    ids = w.obs_slot_anim  # (K,N,4)
    if t % 3 == 0 and t > 0:
        for j in range(N_SLOTS):
            kk, ii = np.nonzero(ids[..., j] >= 0)
            a = ids[kk, ii, j]
            feats = obs[kk, ii, A0 + j * NA: A0 + (j + 1) * NA]
            rows.append(np.concatenate([kk[:, None], kind[kk, a][:, None], code[kk, a][:, None], np.full((len(kk), 1), j), feats], 1))
    if model is not None:
        act, _ = model.predict(obs.reshape(-1, obs.shape[-1]), deterministic=True)
        act = np.asarray(act).reshape(w.K, w.N)
    elif pol == "eat":
        act = np.zeros((w.K, w.N), dtype=np.int64)
    else:
        act = np.where(rng.random((w.K, w.N)) < 0.8, EAT, rng.integers(0, N_ACTIONS, (w.K, w.N)))
    w.step(act)

X = np.concatenate(rows, 0)
world, kind, code, slot, F = X[:, 0], X[:, 1], X[:, 2], X[:, 3], X[:, 4:]
y = (kind == K_WOLF).astype(int)
tr = world < len(seeds) // 2
te = ~tr
names = ("present", "rel_x", "rel_y", "dist", "vel_x", "vel_y", "approach", "approach_mem", "facing", "size", "heard_only")
# derived speed for inspection
spd = np.sqrt(F[:, 4] ** 2 + F[:, 5] ** 2)
print(f"samples {len(X)} wolf {y.sum()} beast {(1 - y).sum()}")
labels = {0: "wolf_roam(no target)", 1: "wolf_eat", 2: "wolf_tired", 3: "wolf_pounce", 4: "wolf_chase", 5: "wolf_stalk_sneak",
          10: "beast_roam", 11: "beast_graze", 12: "beast_dash"}
for c, nm in labels.items():
    m = code == c
    if m.any():
        s = spd[m]
        print(f"  {nm:22s} n={m.sum():7d} |v| mean {s.mean():.3f} p1 {np.percentile(s,1):.3f} p50 {np.median(s):.3f} p99 {np.percentile(s,99):.3f} "
              f"frac(0.08<|v|<0.18) {np.mean((s > 0.08) & (s < 0.18)):.3f}  appr_mem {F[m,7].mean():+.3f} size {F[m,9].mean():.3f}")

clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.1, random_state=0).fit(F[tr], y[tr])
p = clf.predict_proba(F[te])[:, 1]
print(f"ALL states: AUC {roc_auc_score(y[te], p):.3f}")


def pair(wc, bc, title):
    m = np.isin(code, wc) | np.isin(code, bc)
    mt, mtr = m & te, m & tr
    if y[mt].min() == y[mt].max():
        return
    c2 = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.1, random_state=0).fit(F[mtr], y[mtr])
    auc = roc_auc_score(y[mt], c2.predict_proba(F[mt])[:, 1])
    # speed-only
    c3 = HistGradientBoostingClassifier(max_iter=200, random_state=0).fit(spd[mtr, None], y[mtr])
    auc_s = roc_auc_score(y[mt], c3.predict_proba(spd[mt, None])[:, 1])
    print(f"  {title:40s} AUC(all 11) {auc:.3f}  AUC(|v| only) {auc_s:.3f}  n_w {y[mt].sum()} n_b {(1 - y[mt]).sum()}")


print("pairwise (trained per pair, held-out worlds):")
pair([0], [10], "wolf roam  vs beast roam")
pair([1], [10, 11, 12], "wolf eat   vs all beasts")
pair([0], [10, 11, 12], "wolf roam  vs all beasts")
pair([2], [10, 11, 12], "wolf tired vs all beasts")
pair([2], [10], "wolf tired vs beast roam")
pair([1], [11], "wolf eat   vs beast graze")
pair([5], [10], "wolf stalk-sneak vs beast roam")
pair([4], [12], "wolf chase vs beast dash")
pair([3], [12], "wolf pounce vs beast dash")
pair([0, 1, 2], [10, 11, 12], "wolf NON-hunting vs all beasts")
pair([3, 4, 5], [10, 11, 12], "wolf hunting(aim) vs all beasts")

# share of wolf modes among P3 samples (closest perceived animal, slot 0, dist < 15 units)
m0 = (slot == 0) & (F[:, 3] < 15.0 / 20.0)
print("P3-like samples (slot0, <15u): wolf mode shares")
wm = m0 & (y == 1)
for c, nm in labels.items():
    if c < 10:
        print(f"  {nm:22s} {np.mean(code[wm] == c):.3f}")
print(f"  n wolf {wm.sum()} n beast {(m0 & (y == 0)).sum()}")


def single(wc, bc, title):
    m = (np.isin(code, wc) | np.isin(code, bc)) & te
    out = []
    for i, nm in enumerate(names):
        if F[m, i].std() < 1e-9:
            continue
        a = roc_auc_score(y[m], F[m, i])
        out.append((abs(a - 0.5), nm, a))
    out.sort(reverse=True)
    print(f"  {title}: " + ", ".join(f"{nm} {a:.3f}" for _, nm, a in out[:5]))


print("single-feature AUC (held-out worlds):")
single([1], [11], "wolf eat vs beast graze")
single([0], [10], "wolf roam vs beast roam")
single([2], [10], "wolf tired vs beast roam")
single([5], [10], "wolf stalk vs beast roam")

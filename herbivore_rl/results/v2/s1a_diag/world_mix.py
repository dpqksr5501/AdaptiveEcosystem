"""학습 시드별로 학습 중 본 세계(MultiWorldVecEnv 의 _pick_seed·나이 규칙을 흉내 냄)의 시간 가중 평균 매개변수를 낸다.
S1-a 진단(10-04): 나쁨 4개 food_regen_mult 1.153~1.227, 좋음 9개 1.254~1.414. 세계 스텝은 돌리지 않는다.
    PYTHONPATH=. python results/v2/s1a_diag/world_mix.py
"""
import numpy as np, json
from env_v2.config import load_v2_config
from env_v2.vec_env import MultiWorldVecEnv
from env_v2.world import World
cfg = load_v2_config("configs/v2_1.yaml")
runs = {"v2_1_s0":0,"v2_1_s1":1,"v2_1_s2":2,"t0_s20":20,"t0_s21":21,"t0_s22":22,"t0_s23":23,"t0_s24":24,"t0_s25":25,
        "c_s30":30,"c_s31":31,"c_s32":32,"c_s33":33,"c_s34":34}
label = {"t0_s24":"나쁨","c_s30":"나쁨","c_s31":"나쁨","c_s33":"나쁨","t0_s21":"경계"}
rd = cfg.rand
cache = {}
def params(seed):
    if seed not in cache:
        r = np.random.default_rng(seed)
        size = r.uniform(*rd["world_size"]); M = int(r.integers(rd["predator_count"][0], rd["predator_count"][1] + 1))
        psm = r.uniform(*rd["pred_speed_mult"]); rf = r.uniform(*rd["ranged_frac"]); cf = r.uniform(*rd["cover_frac"]); fr = r.uniform(*rd["food_regen_mult"])
        cache[seed] = dict(size=size, M=M, psm=psm, fr=fr, cf=cf)
    return cache[seed]
out = {}
for name, s in runs.items():
    # MultiWorldVecEnv 의 세계 고르기만 흉내 낸다(세계 스텝은 돌리지 않는다): 같은 클래스의 _pick_seed·나이 규칙
    v = MultiWorldVecEnv.__new__(MultiWorldVecEnv)
    v.K, v.T = 8, 4000
    v.pool = np.arange(0, 1000); v._meta = np.random.default_rng(s)
    seeds = []
    cur = []
    class W: pass
    v.worlds = []
    for _ in range(v.K):
        sd = v._pick_seed(exclude=[w.seed for w in v.worlds]); w = W(); w.seed = sd; v.worlds.append(w)
    age = np.array([(k * v.T) // v.K for k in range(v.K)])
    steps = 20021248 // (v.K * 128)
    w_fr = np.zeros(1); tot = 0.0; acc = {k: 0.0 for k in ("fr","M","psm","cf","size")}
    for t in range(steps):
        for k, w in enumerate(v.worlds):
            p = params(w.seed)
            for key in acc: acc[key] += p[key]
            age[k] += 1
            if age[k] >= v.T:
                others = [x.seed for j, x in enumerate(v.worlds) if j != k]
                w.seed = v._pick_seed(exclude=others); age[k] = 0
        tot += v.K
    out[name] = {k: acc[k] / tot for k in acc}
for name in runs:
    o = out[name]; print(f"{name:8s} {label.get(name,'좋음'):3s} fr {o['fr']:.3f}  M {o['M']:.2f}  psm {o['psm']:.3f}  cover {o['cf']:.3f}")

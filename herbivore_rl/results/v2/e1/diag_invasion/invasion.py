"""Gate E1 실패 원인 확인(스크래치): 소수 개체만 '가까우면 뛰기'를 쓸 때 그 개체가 덜 잡히는가."""
import env.torch_init  # noqa
import numpy as np, sys
from env_v2.config import load_v2_config
from env_v2.world import World

cfg = load_v2_config('configs/v2_1.yaml')
cfg.rand['pred_speed_mult'] = [float(sys.argv[2]), float(sys.argv[3])]
BASE = np.array([0.7305, 0.7111, float(sys.argv[1]), 0.0434, 0.5])   # 제안 팔 C2 (걷기)
F = 16                                                    # 실험군 슬롯 수
res = {k: [] for k in ('focal_pred', 'other_pred', 'focal_starve', 'other_starve', 'focal_rew', 'other_rew', 'fast_world')}
for s in range(10000, 10020):
    w = World(cfg, seeds=[s])
    focal = np.zeros(w.N, bool); focal[:F] = True
    cp = np.zeros(w.N); cs = np.zeros(w.N); rw = np.zeros(w.N)
    obs = w.observe()
    _orig = w._step_predators
    def _wrap(_o=_orig, _w=w):
        c = _o(); _w._last_caught = c; return c
    w._step_predators = _wrap
    for t in range(3000):
        a = np.tile(BASE, (w.N, 1))
        close = obs[:, 2] < 0.5
        a[focal & close, 4] = 1.0
        obs, rew, done, _ = w.step(a)
        rw += rew
        caught = w._last_caught
        cp += caught; cs += done & ~caught
    n = 3000
    res['focal_pred'].append(cp[focal].mean() / n); res['other_pred'].append(cp[~focal].mean() / n)
    res['focal_starve'].append(cs[focal].mean() / n); res['other_starve'].append(cs[~focal].mean() / n)
    res['focal_rew'].append(rw[focal].mean()); res['other_rew'].append(rw[~focal].mean())
    res['fast_world'].append(w.pred_speed_mult)
r = {k: np.array(v) for k, v in res.items()}
def paired(a, b):
    d = a - b; return d.mean(), d.mean() / (d.std(ddof=1) / np.sqrt(len(d)))
for name in ('pred', 'starve', 'rew'):
    m, t = paired(r['focal_' + name], r['other_' + name])
    print(f"{name}: focal {r['focal_'+name].mean():.5f} other {r['other_'+name].mean():.5f}  diff {m:+.5f}  t {t:+.2f}")
slow = r['fast_world'] < 0.8
for lab, msk in (('pred slower than run', slow), ('pred faster/equal', ~slow)):
    if msk.sum() > 1:
        d = r['focal_pred'][msk] - r['other_pred'][msk]
        print(f"{lab} (n={msk.sum()}): pred diff {d.mean():+.5f}  rel {d.mean()/r['other_pred'][msk].mean():+.1%}")

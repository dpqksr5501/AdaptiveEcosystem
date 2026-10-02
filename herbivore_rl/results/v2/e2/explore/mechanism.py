"""Gate E2 사전 등록 밖 탐색(판정에 쓰지 않음, 10-03 V0 판정 뒤): A-허용(d0_95)의 이득이 360° 시야인지, 멈춤인지,
위협 쪽 보기인지, 경계의 섭식 손실이 얼마인지. 보정 시드(재측정 100~119) × 3000스텝만 쓴다(평가 시드는 쓰지 않는다).

    PYTHONPATH=. python results/v2/e2/explore/mechanism.py > results/v2/e2/explore/mechanism.txt

- stop_recent: 최근 위협 구간에서 speed 0(경계 아님 — 먹고, 120°, heading 유지), 그 밖은 C2
- A_allow_fov120: A-허용 정책을 vigilance.fov_deg 120 사본에서(경계 = 정지·섭식 0·위협 쪽 보기, 시야는 그대로)
- A_allow_eat1: A-허용 정책을 vigilance.eat_mult 1.0 사본에서(경계 중에도 정지만큼 먹는다)
"""
import env.torch_init  # noqa
import json, sys, numpy as np
sys.path.insert(0, '.')
from env_v2.config import load_v2_config
from env_v2.rollout import run_specs
from diagnose_v2 import paired, seg_spec, parse_bins
def main():
    cfg = load_v2_config('results/v2/e2/configs/V0_d0_95.yaml')
    c2 = json.load(open('results/v2/e2/V0/c2/constsearch.json', encoding='utf-8'))['best']
    aa = json.load(open('results/v2/e2/V0/d0_95/a_allow.json', encoding='utf-8'))['best']
    bins = parse_bins(['threat_recency:0.5,1'], ['food_density','pred_count','pred_dist','kin_count','energy','recent_predation','cover_dist','threat_recency'])
    specs = {
      'C2': {'kind': 'fixed', 'action': c2},
      'A_allow': seg_spec(c2, bins, [5], aa),
      'stop_recent': seg_spec(c2[:5] + [0.0], bins, [4], [c2[4], 0.0, c2[4]]),
    }
    seeds = list(range(100, 120))
    res = run_specs(cfg, specs, seeds, 3000, workers=18)
    v = dict(cfg.v2); f = {k: dict(x) for k, x in v['features'].items()}; f['vigilance']['fov_deg'] = 120.0
    cfg120 = cfg.replace(v2=dict(v, features=f))
    res['A_allow_fov120'] = run_specs(cfg120, {'x': specs['A_allow']}, seeds, 3000, workers=18)['x']
    f2 = {k: dict(x) for k, x in v['features'].items()}; f2['vigilance']['eat_mult'] = 1.0
    cfgE = cfg.replace(v2=dict(v, features=f2))
    res['A_allow_eat1'] = run_specs(cfgE, {'x': specs['A_allow']}, seeds, 3000, workers=18)['x']
    cols = ['g_gamma', 'survival', 'predation_rate', 'starve_rate', 'vig_frac', 'stop_frac', 'seg_recent_frac', 'seg_seen_frac']
    for k, rows in res.items():
        print(k, {c: round(float(np.mean([r[c] for r in rows])), 5) for c in cols})
    for a, b in [('A_allow', 'C2'), ('A_allow', 'stop_recent'), ('A_allow', 'A_allow_fov120'), ('stop_recent', 'C2'), ('A_allow_fov120', 'C2'), ('A_allow_eat1', 'A_allow')]:
        out = {c: paired([r[c] for r in res[a]], [r[c] for r in res[b]]) for c in ['g_gamma', 'predation_rate', 'starve_rate', 'survival']}
        print(f'{a} - {b}:', {c: (round(o['diff'], 5), round(o['t'], 2)) for c, o in out.items()})

if __name__ == '__main__':
    main()

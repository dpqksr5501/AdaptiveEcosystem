"""A3 원인 가설 검사 — 계산만 하는 부분 (학습·롤아웃 없음).

H-지평: γ 의 유효 지평, 굶어 죽기까지 시간, 사망 보상 −10 의 현재 가치, 단순 모델의 할인 리턴 비교.
H-보상: 순에너지 보상(#4)과 정지 대사 0.714 가 만드는 즉시 보상 차.
H-스레드: --threads 3(시드 0~2) 대 --threads 1(그 밖 11개)의 나쁨 비율 차가 우연으로 흔한가(피셔 정확·초기하).

계수는 configs/default.yaml·configs/v2_1.yaml 에서 읽는다(load_v2_config).
실행(herbivore_rl 에서): python results/v2/s1a_diag/a3_analytic.py
산출: results/v2/s1a_diag/a3_analytic.json
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
H = HERE.parents[2]
sys.path.insert(0, str(H))

from scipy.stats import binom, fisher_exact, hypergeom  # noqa: E402

from env_v2.config import load_v2_config  # noqa: E402

GAMMA = 0.9916661555611042


def coefs():
    cfg = load_v2_config(H / "configs" / "v2_1.yaml")
    sp = cfg.v2["features"]["speed"]
    c_rest, c_move = sp["c_rest"], sp["c_move"]
    gs = sp["gait_speed"]
    drain_mult = [c_rest + c_move * v * v for v in gs]
    return dict(
        energy_drain=cfg.energy_drain, drain_mult=drain_mult, drain=[cfg.energy_drain * m for m in drain_mult],
        gait_eat=sp["gait_eat"], food_eat_rate=cfg.food_eat_rate, fepu=cfg.food_energy_per_unit,
        rew_alive=cfg.rew_alive, rew_energy=cfg.rew_energy, rew_death=cfg.rew_death, rew_repro=cfg.rew_repro,
        repro_threshold=cfg.repro_threshold, init_energy=cfg.init_energy, max_energy=cfg.max_energy,
        repro_cd=cfg.repro_cd, herb_speed=cfg.herb_speed, food_regen_base=cfg.food_regen_base,
        food_cover_regen_mult=cfg.food_cover_regen_mult, food_regen_mult=cfg.rand["food_regen_mult"],
    )


def horizon(c):
    g = GAMMA
    out = {"gamma": g, "eff_horizon_1_over_1mg": 1.0 / (1.0 - g), "half_life_steps": math.log(0.5) / math.log(g),
           "tail_ceil_5_over_1mg": math.ceil(5.0 / (1.0 - g))}
    rows = []
    for e0 in (0.5, 0.4, 0.3, 0.2, 0.1):
        r = {"e0": e0}
        for name, d in zip(("stop", "walk", "run"), c["drain"]):
            T = math.ceil(e0 / d - 1e-12)
            r[f"T_{name}"] = T
            r[f"death_pv_{name}"] = c["rew_death"] * g ** T
        rows.append(r)
    out["starve_time"] = rows
    return out


def immediate(c):
    """한 스텝 보상(배고픈 개체, energy ≤ 1 − 0.03 이라 흡수 상한에 걸리지 않음).

    빈 셀: 섭취 0. 먹이 많은 셀: 섭취 = food_eat_rate × gait_eat × fepu (정지 0.03, 걷기 0.015, 뛰기 0).
    순변화(#4, v2.1): alive + (섭취 − 대사). 획득량(v1 꼴, net_energy_reward false): alive + 섭취.
    """
    out = {}
    for cell, food in (("empty", 0.0), ("rich", 1.0)):
        for rew_kind in ("net", "gain"):
            vals = {}
            for i, name in enumerate(("stop", "walk", "run")):
                intake = (c["food_eat_rate"] * c["gait_eat"][i] * c["fepu"]) if food > 0 else 0.0
                e = intake - c["drain"][i] if rew_kind == "net" else intake
                vals[name] = c["rew_alive"] + c["rew_energy"] * e
            vals["stop_minus_walk"] = vals["stop"] - vals["walk"]
            out[f"{cell}_{rew_kind}"] = vals
    bias = c["drain"][1] - c["drain"][0]
    out["net_stop_bias_per_step"] = bias
    out["net_stop_bias_discounted_inf"] = bias / (1.0 - GAMMA)
    out["net_stop_bias_rel_alive"] = bias / c["rew_alive"]
    # 순변화 보상의 망원 합: Σ_{t<T} γ^t (e_{t+1} − e_t) = −e_0 + γ^{T−1} e_T + (1−γ)/γ Σ_{t=1}^{T−1} γ^t e_t
    out["telescoping_weight_per_energy_step"] = (1.0 - GAMMA) / GAMMA
    return out


def pv(r_per_step: float, n: int, start: int = 0) -> float:
    """Σ_{t=start}^{start+n−1} γ^t r."""
    g = GAMMA
    return r_per_step * g ** start * (1.0 - g ** n) / (1.0 - g)


def simple_model(c, v_cont_list=(0.0, 2.0)):
    """배고픈 개체(e0)가 빈 셀(먹이 0, 용량 0)에 있다. 두 전략의 할인 리턴(γ 학습값, 순변화 보상).

    STOP: 그 자리에서 계속 정지. 섭취 0 → T_s = ⌈e0/d_stop⌉ 스텝에 아사(−10). 이후 0.
    WALK(D): 걷기로 D 스텝 동안 먹이 없음(대사 d_walk) → 먹이 셀 도착(e1 = e0 − D·d_walk, e1 ≤ 0 이면 도중 아사).
      도착 뒤 정지해 상한 섭취(0.03 − d_stop/스텝)로 0.9 를 넘기면 번식 +10. 번식 뒤 가치 V_c (모르는 값, 0 과 2 두 경우).
    WALK_NOFOOD: 걷기로 끝내 먹이를 못 찾음 → ⌈e0/d_walk⌉ 스텝에 아사.
    """
    g = GAMMA
    d_stop, d_walk = c["drain"][0], c["drain"][1]
    a = c["rew_alive"]
    eat_net = c["food_eat_rate"] * c["gait_eat"][0] * c["fepu"] - d_stop
    out = []
    for e0 in (0.5, 0.4, 0.3):
        Ts = math.ceil(e0 / d_stop - 1e-12)
        V_stop = pv(a - d_stop, Ts) - e0 * 0 + c["rew_death"] * g ** (Ts - 1)
        Tw = math.ceil(e0 / d_walk - 1e-12)
        V_walk_nofood = pv(a - d_walk, Tw) + c["rew_death"] * g ** (Tw - 1)
        rec = {"e0": e0, "T_stop": Ts, "V_stop": V_stop, "T_walk_nofood": Tw, "V_walk_nofood": V_walk_nofood,
               "V_stop_minus_walk_nofood": V_stop - V_walk_nofood, "walk": []}
        for vc in v_cont_list:
            best = None
            for D in (0, 25, 50, 100, 150, 200, 249):
                e1 = e0 - D * d_walk
                if e1 <= 0:
                    continue
                n_eat = math.ceil((c["repro_threshold"] - e1) / eat_net + 1e-12)
                V = pv(a - d_walk, D) + pv(a + eat_net, n_eat, D) + g ** (D + n_eat - 1) * (c["rew_repro"] + vc)
                rec["walk"].append({"V_cont": vc, "D": D, "n_eat": n_eat, "V_walk": V, "minus_V_stop": V - V_stop})
            # 손익분기 D*: V_walk(D) = V_stop 이 되는 D (1 스텝 단위 탐색)
            for D in range(0, Tw):
                e1 = e0 - D * d_walk
                n_eat = math.ceil((c["repro_threshold"] - e1) / eat_net + 1e-12)
                V = pv(a - d_walk, D) + pv(a + eat_net, n_eat, D) + g ** (D + n_eat - 1) * (c["rew_repro"] + vc)
                if V < V_stop:
                    best = D
                    break
            rec[f"breakeven_D_Vc{vc:g}"] = best
        # 번식 없이 '배고픔만 면하는' 경우(먹이 셀에서 e 를 0.5 로만 회복하고 그 뒤 가치 V_c=0) — 순변화 보상만의 몫
        D = 50
        e1 = e0 - D * d_walk
        n_eat = max(0, math.ceil((0.5 - e1) / eat_net))
        rec["walk_D50_eat_to_0p5_noRepro"] = pv(a - d_walk, D) + pv(a + eat_net, n_eat, D)
        out.append(rec)
    return out


def threads_test():
    """시드 0~2(--threads 3) 3/3 좋음, --threads 1 은 11개 중 나쁨 4(s24, s30, s31, s33)·경계 1(s21)."""
    res = {}
    for label, bad1 in (("border_as_good", 4), ("border_as_bad", 5)):
        n3, bad3, n1 = 3, 0, 11
        table = [[bad3, n3 - bad3], [bad1, n1 - bad1]]
        _, p_two = fisher_exact(table, alternative="two-sided")
        _, p_less = fisher_exact(table, alternative="less")
        # 초기하: 14개 중 나쁨 K 개, 무작위로 3개를 뽑을 때 나쁨 0 개일 확률
        K = bad3 + bad1
        p_hyper = hypergeom(M=14, n=K, N=3).pmf(0)
        p_binom = binom(3, bad1 / n1).pmf(0)
        p_binom_pooled = binom(3, K / 14).pmf(0)
        # 같은 실패율(bad1/11)에서 0/n 이 단측 p < 0.05 가 되려면 threads 3 모델이 몇 개 필요한가 (피셔 단측)
        need = None
        for n in range(3, 60):
            if fisher_exact([[0, n], [bad1, n1 - bad1]], alternative="less")[1] < 0.05:
                need = n
                break
        need_binom = math.ceil(math.log(0.05) / math.log(1 - bad1 / n1))
        res[label] = {"table_[bad,notbad]_threads3_threads1": table, "fisher_p_two_sided": p_two,
                      "fisher_p_one_sided": p_less, "hypergeom_p0_of_3": p_hyper,
                      "binom_p0_of_3_at_threads1_rate": p_binom, "binom_p0_of_3_at_pooled_rate": p_binom_pooled,
                      "n_threads3_needed_fisher_one_sided_0fail": need,
                      "n_needed_binom_0fail_vs_known_rate": need_binom}
    return res


def main() -> None:
    c = coefs()
    out = {"generated_by": "results/v2/s1a_diag/a3_analytic.py", "coefs": c, "horizon": horizon(c),
           "immediate_reward": immediate(c), "simple_model": simple_model(c), "threads": threads_test()}
    (HERE / "a3_analytic.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out["horizon"], indent=1))
    print(json.dumps(out["immediate_reward"], indent=1))
    for r in out["simple_model"]:
        print({k: v for k, v in r.items() if k != "walk"})
        for w in r["walk"]:
            print("   ", w)
    print(json.dumps(out["threads"], indent=1))


if __name__ == "__main__":
    main()

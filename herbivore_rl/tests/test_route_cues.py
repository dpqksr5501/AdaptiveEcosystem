"""도망길 단서 측정 (results/v3/route/cues.py — 10-22 사용자 결정 '고를 단서부터 더 잼 (추천)', 판단 규칙 results/v3/route/CUES_RULE.md).

- 쫓긴 시작 표시(`chased_mask`): 스텝 끝 사냥 중인 늑대의 pred_target 과 같고(도망 기록 `_fl_tgt`), 시작 스텝에 쫓겼으면 그 도망 기록도 '쫓겼다'.
- 시작 고르기(`sample_onsets`): 시작마다 난수 하나(사슴 번호 차례)로 층별 확률 — 결정적이고 뽑힌 몫이 확률과 맞는다.
- 시작 단서(`onset_cues`): 다시 부른 도망길 기하가 세계가 남긴 route_* 훅과 비트 단위로 같다. 관측 21 칸 = OBS21. 시작에는 알아챈 사냥 중 늑대가 있다.
- 알 수 있음(P) 늑대 단서는 알아채지 못한 늑대(속도·걸음새·종류·표적, safe_r 밖이면 위치)를 바꿔도 그대로다. 특권(X) 칸은 P 칸의 정확한 일차식이 아니다.
- 단서 표: 알 수 있음(P)·특권(X) 표시가 모듈 docstring 표와 코드(CUE_KIND)에서 같고 겹치지 않는다.
- 교차 검증 겹(`folds`): 한 시드는 한 겹에만. 분류기는 비긴 시작을 맞추지 않는다. 무게 CI 는 무게가 같으면 보통 꼴과 같다.
- 판단 규칙(`decide`): 단서가 정답을 가르는 합성 자료 → 진행(넷 모두), 정답이 우연 → 두 길, 표본 부족·미리 정한 조건과 다름·연장 규칙 어김 → 판단 없음.
- 보고(`fmt`·`cmd_report`): 판단·표·어림 명령이 글에 들어간다. 중간 jsonl 은 개수만(눈가림), 덜 쓰인 끝 줄은 버린다.
시드는 탐색 32084~32099 만 쓴다.
"""

import env.torch_init  # noqa: F401  ← torch보다 먼저

import copy
import importlib.util
import json
import sys

import numpy as np
import pytest

from env.config import ROOT
from env_v2.config import load_v2_config
from env_v2.world import PT_CHASER, PT_STALKER, WF_PANIC, World

CFG = ROOT / "configs"
OBS = CFG / "v3_wild3_obs_mirror.yaml"

pytestmark = pytest.mark.filterwarnings("ignore:You have specified a mini-batch size")


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cu():
    d = ROOT / "results" / "v3" / "route"
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))
    import cues

    return cues


def _with(cfg, **blocks):
    f = {k: dict(v) for k, v in cfg.v2["features"].items()}
    for name, kw in blocks.items():
        f[name] = dict(f.get(name, {}), **kw)
    return cfg.replace(v2=dict(cfg.v2, features=f))


def _world(foliage: bool, seed: int):
    """거울 숲 지역(N 세계 — 늑대 포만 끔), 사슴 32, 길 고정 run, 도망 기록 켬. foliage 면 숲 시야 r 3·block 2."""
    r4 = _module("_r4_for_cues", ROOT / "results" / "v3" / "r4" / "r4_eval.py")
    ob = dict(fixed=r4.region_discs()["Forest"])
    if foliage:
        ob["foliage"] = dict(enabled=True, r=3.0, block=2.0)
    cfg = _with(load_v2_config(OBS).replace(N=32), wild_weather=dict(region="Forest"), obstacles=ob, wild_satiation=dict(enabled=False),
                wild_flight=dict(route_fixed="run"))
    w = World(cfg, seeds=[seed])
    w.track_flight = True
    return w


# --------------------------------------------------------------------- #
# 쫓긴 시작 표시·시작 고르기·시작 단서
# --------------------------------------------------------------------- #

@pytest.mark.parametrize("foliage,seed", [(True, 32091), (False, 32092)])
def test_chased_onset_selection_and_cues(cu, foliage, seed):
    """chased_mask = 스텝 끝 사냥 중 늑대의 표적(pred_target), 시작 스텝에 참이면 다음 스텝 도망 기록도 '쫓겼다'. 쫓긴 시작·쫓기지 않은 시작이 모두 나온다.
    시작 단서의 기하 점검은 늘 맞고(세계 route_* 훅과 같음), 단서 칸은 PERCEIVABLE + PRIV 그대로·유한하다. 도주 시작에는 경계 거리(30 m) 안에 알아챈
    사냥 중 늑대가 있다(반사의 시작 조건) — P 늑대 단서가 늘 채워진다. 쫓김 ⇔ n_targeting ≥ 1."""
    w = _world(foliage, seed)
    rng = np.random.default_rng(5)
    n_ch = n_un = 0
    pending = []
    for _ in range(1500):
        w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        for i in pending:                                   # 지난 스텝에 쫓기며 시작 → 이번 스텝 FLEE 를 실행했으면 도망 기록 '쫓겼다'
            if w.alive[i] and w._fl_len[i] > 0:
                assert w._fl_chased[i]
        pending = []
        tgt = np.where(w._wf_hunting(), w.pred_target, -1)
        want = np.zeros(w.N, dtype=bool)
        want[tgt[tgt >= 0]] = True
        want &= w.alive                                     # 이번 스텝에 죽은 사슴을 쫓던 기록은 지운다(거울 세계는 부활 없음)
        assert np.array_equal(cu.chased_mask(w), want)
        on = np.flatnonzero(w.route_onset & w.alive)
        for i in on:
            assert w.wf_mode[i] == WF_PANIC
            c, chk = cu.onset_cues(w, int(i))
            assert chk["all"], chk
            assert list(c) == list(cu.PERCEIVABLE + cu.PRIV) and all(np.isfinite(v) for v in c.values())
            assert c["obs_threat_hidden"] == pytest.approx(float(w._obs[i][w.obs_names.index("threat_hidden")]))
            assert c["n_noticed"] >= 1 and c["wolf_dist_m"] <= w._wf["alert_r"] * cu.M_PER_U + 1e-9
            assert -1.0 - 1e-12 <= c["wolf_bearing_cos"] <= 1.0 + 1e-12
            assert c["n_hunt_safe"] == c["n_noticed"] + c["n_unnoticed_safe"]      # 알아챈 늑대는 모두 safe_r 안(시야·발소리 ≤ 20)
            if want[i]:
                n_ch += 1
                if w._fl_len[i] == 0:                       # 열린 도망(두뇌 FLEE)이 없던 사슴만 — 다음 스텝이 새 도망의 첫 스텝
                    pending.append(int(i))
                assert c["n_targeting"] >= 1 and c["tgt_dist_m"] < cu.FAR_M
            else:
                n_un += 1
                assert c["n_targeting"] == 0
            if not foliage:
                assert c["foliage_5m"] == c["foliage_10m"] == c["in_foliage"] == 0.0
        if n_ch >= 12 and n_un >= 2:
            break
    assert n_ch >= 12 and n_un >= 2
    assert tuple(w.obs_names) == cu.OBS21


def test_sample_onsets_bernoulli(cu):
    """시작마다 균등 난수 하나(사슴 번호 차례)로 쫓김 p_ch·안 쫓김 p_un — 같은 열쇠면 같은 결과, 시작이 없으면 난수를 쓰지 않는다, 뽑힌 몫 ≈ 확률."""
    idx = np.arange(40)
    ch = idx % 5 == 0
    a = cu.sample_onsets(np.random.default_rng([1, 2]), idx, ch, 0.3, 0.05)
    b = cu.sample_onsets(np.random.default_rng([1, 2]), idx, ch, 0.3, 0.05)
    assert np.array_equal(a, b) and set(a) <= set(idx)
    u = np.random.default_rng([1, 2]).random(40)
    assert np.array_equal(a, idx[u < np.where(ch, 0.3, 0.05)])
    g = np.random.default_rng(9)
    s0 = g.bit_generator.state
    assert len(cu.sample_onsets(g, np.zeros(0, dtype=np.int64), np.zeros(0, dtype=bool), 0.5, 0.5)) == 0
    assert g.bit_generator.state == s0
    g = np.random.default_rng(3)
    n_c = n_u = 0
    for _ in range(4000):
        got = set(cu.sample_onsets(g, idx, ch, 0.3, 0.05).tolist())
        n_c += sum(1 for i in idx[ch] if i in got)
        n_u += sum(1 for i in idx[~ch] if i in got)
    assert n_c / (4000 * ch.sum()) == pytest.approx(0.3, abs=0.01) and n_u / (4000 * (~ch).sum()) == pytest.approx(0.05, abs=0.005)


def _first_onset_with_unnoticed(w, rng, safe_r, max_steps=1500):
    """도주 시작 가운데 알아채지 못한 늑대가 safe_r 밖에 있는 것 → (사슴, 그 늑대 목록)."""
    for _ in range(max_steps):
        w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
        for i in np.flatnonzero(w.route_onset & w.alive):
            pv = np.asarray(w._g["wf_pvis"][i], dtype=bool)
            d = np.sqrt(((w.pred_pos - w.pos[i][None, :]) ** 2).sum(1))
            far = np.flatnonzero(~pv & (d > safe_r + 1.0))
            if len(far) and pv.any():
                return int(i), far
    raise AssertionError("알아채지 못한 먼 늑대가 있는 도주 시작이 없다")


@pytest.mark.parametrize("foliage,seed", [(True, 32093), (False, 32094)])
def test_perceivable_cues_ignore_unnoticed_wolves(cu, foliage, seed):
    """P 단서 = 알아챈 사냥 중 늑대 + 반사 집합 S(safe_r 안)의 길 기하뿐: 알아채지 못한 늑대의 속도·걸음새와 safe_r 밖 위치, 모든 늑대의 종류·표적·덮침을
    바꿔도 P 칸은 비트 단위로 그대로다(기하 점검도 그대로). 특권 칸(종류·표적)은 바뀐다 — 흔든 것이 단서에 닿는다."""
    w = _world(foliage, seed)
    rng = np.random.default_rng(11)
    safe_r = float(w._wf["safe_r"])
    i, far = _first_onset_with_unnoticed(w, rng, safe_r)
    c0, k0 = cu.onset_cues(w, i)
    wc = copy.deepcopy(w)
    pv = np.asarray(wc._g["wf_pvis"][i], dtype=bool)
    g = np.random.default_rng(12)
    un = np.flatnonzero(~pv)
    wc.pred_vel = wc.pred_vel.copy()
    wc.pred_vel[un] = g.normal(0.0, 0.5, (len(un), 2))
    wc.pred_running = wc.pred_running.copy()
    wc.pred_running[un] = ~wc.pred_running[un]
    wc.pred_pos = wc.pred_pos.copy()
    for m in far:                                          # safe_r 밖 → 다른 safe_r 밖 자리
        for _ in range(200):
            x = g.uniform(1.0, wc.size - 1.0, 2)
            if np.sqrt(((x - wc.pos[i]) ** 2).sum()) > safe_r + 1.0:
                wc.pred_pos[m] = x
                break
    wc.pred_type = np.where(wc.pred_type == PT_STALKER, PT_CHASER, PT_STALKER).astype(wc.pred_type.dtype)
    wc._fl_tgt = np.where(np.arange(wc.M) % 2 == 0, i, -1).astype(np.int64)
    c1, k1 = cu.onset_cues(wc, i)
    assert k0["all"] and k1["all"]
    for k in cu.PERCEIVABLE:
        assert c1[k] == c0[k], (k, c0[k], c1[k])
    assert c1["wolf_stalker"] != c0["wolf_stalker"] and c1["n_targeting"] != c0["n_targeting"]


def test_privileged_not_linear_in_perceivable(cu):
    """실제 도주 시작(숲 시야 켬·끔)에서 변하는 X 칸 가운데 P 칸 + 상수의 정확한 일차식인 것이 없다(옛 n_unnoticed_safe = n_hunt_safe − n_noticed 같은 샘).
    같은 함수가 일부러 넣은 샘(X 칸 = 2·obs_pred_dist + 1)은 잡는다."""
    rows = []
    for foliage, seed in ((True, 32095), (False, 32096), (True, 32097)):
        w = _world(foliage, seed)
        rng = np.random.default_rng(seed)
        for _ in range(1500):
            w.step(rng.integers(0, 3, (w.N, 1)).astype(np.float64))
            for i in np.flatnonzero(w.route_onset & w.alive):
                c, _ = cu.onset_cues(w, int(i))
                rows.append([c[k] for k in cu.PERCEIVABLE + cu.PRIV])
    names = list(cu.PERCEIVABLE + cu.PRIV)
    X = np.array(rows)
    r = cu.x_linear_in_p(X, names)
    assert r["exact"] is not None and r["rows"] > r["rank"] + 1, r
    assert r["exact"] == [] and "n_unnoticed_safe" in r["checked"] and "n_hunt_safe" in r["checked"], r
    X2 = X.copy()
    X2[:, names.index("tgt_dist_m")] = 2.0 * X[:, names.index("obs_pred_dist")] + 1.0
    assert cu.x_linear_in_p(X2, names)["exact"] == ["tgt_dist_m"]


# --------------------------------------------------------------------- #
# 단서 표
# --------------------------------------------------------------------- #

def test_cue_table_flags(cu):
    """모듈 docstring 표의 P/X 와 코드 CUE_KIND 가 같다 — 모든 단서가 표에 있고, 관측 21 칸은 알 수 있음, 지역·늑대 종류·표적·알아챔과 무관한 늑대 값은
    특권, 겹침 없음. 머리 방향 단서는 cos(삼각함수 없음)."""
    assert not set(cu.PERCEIVABLE) & set(cu.PRIV)
    assert len(cu.PERCEIVABLE) == 21 + len(cu.GEO_P) and len(set(cu.PERCEIVABLE + cu.PRIV)) == len(cu.PERCEIVABLE + cu.PRIV)
    doc = {}
    for line in cu.__doc__.splitlines():
        s = line.strip()
        if not s.startswith("| ") or s.startswith("| 단서") or s.startswith("|---"):
            continue
        cells = [x.strip() for x in s.strip("|").split("|")]
        for name in cells[0].split("·"):
            doc[name.strip()] = cells[1]
    assert doc.pop("obs_<이름> × 21") == "P"
    for k in cu.GEO_P:
        assert doc.get(k) == "P", k
    for k in cu.PRIV + ("region",):
        assert doc.get(k) == "X", k
    assert set(doc) == set(cu.GEO_P) | set(cu.PRIV) | {"region"}
    for k in cu.PERCEIVABLE:
        assert cu.CUE_KIND[k] == "perceivable"
    for k in cu.PRIV + ("region",):
        assert cu.CUE_KIND[k] == "privileged"
    for k in ("wolf_stalker", "tgt_stalker", "n_targeting", "region", "n_hunt_safe", "n_unnoticed_safe", "wolf2_any_dist_m", "wolf_any_closing_ms"):
        assert cu.CUE_KIND[k] == "privileged"
    assert cu.CUE_KIND["wolf_closing_ms"] == "perceivable" and cu.CUE_KIND["wolf2_dist_m"] == "perceivable"      # 알아챈 늑대만
    assert "wolf_bearing_cos" in cu.GEO_P and "wolf_bearing_deg" not in cu.CUE_KIND
    names = list(cu.PERCEIVABLE + cu.PRIV) + ["region_A", "region_B"]
    assert set(names[j] for j in cu.feature_cols(names, "perc")) == set(cu.PERCEIVABLE)
    assert len(cu.feature_cols(names, "all")) == len(names)


# --------------------------------------------------------------------- #
# 교차 검증 겹·맞춤·CI
# --------------------------------------------------------------------- #

def test_groupkfold_no_seed_leakage(cu):
    """한 시드(지역 셋 모두)는 한 겹의 확인에만 있고 맞춤에는 없다. 모든 시작이 확인에 꼭 한 번. 시드가 둘 밑이면 겹 없음."""
    g = np.random.default_rng(1)
    seeds = np.repeat(np.arange(34900, 34940), g.integers(1, 12, 40))
    fl = cu.folds(seeds)
    assert len(fl) == cu.FOLDS
    seen = np.zeros(len(seeds), dtype=int)
    for tr, te in fl:
        assert not set(seeds[tr]) & set(seeds[te])
        assert len(tr) + len(te) == len(seeds)
        seen[te] += 1
    assert (seen == 1).all()
    assert len(cu.folds(seeds[:3] * 0 + 34900)) == 0
    assert len(cu.folds(np.array([1, 1, 2, 2, 3]))) == 3


@pytest.mark.parametrize("model", ["tree3", "logreg"])
def test_classifier_ignores_tied_rows(cu, model):
    """비긴 시작(정답이 정의상 RUN 으로 떨어짐)은 분류기 맞춤에 들어가지 않는다: 비기지 않은 시작이 x > 0 → SHELTER, x ≤ 0 → COVER 이고 같은 자리에 비긴 시작이
    다섯 배 있어도 RUN 을 고르지 않는다. 무게(1/p)가 큰 비긴 시작도 마찬가지."""
    g = np.random.default_rng(2)
    n = 300
    x = g.normal(size=n)
    real = np.where((x > 0)[:, None], [[40.0, 40.0, 10.0, 40.0]], [[40.0, 10.0, 40.0, 40.0]])
    xt = g.normal(size=5 * n)
    X = np.concatenate([x, xt])[:, None]
    R = np.concatenate([real, np.full((5 * n, 4), 20.0)])
    ok = np.ones((6 * n, 4), dtype=bool)
    wt = np.concatenate([np.ones(n), np.full(5 * n, 30.0)])
    f = cu.fit_model(model, X, R, ok, wt, cu.nontied(R, ok))
    z = np.linspace(-2, 2, 41)[:, None]
    pick = f(z, np.ones((41, 4), dtype=bool))
    assert not (pick == 0).any() and set(pick[z[:, 0] > 0.3]) == {2} and set(pick[z[:, 0] < -0.3]) == {1}


def test_cluster_ci_and_masked_pick(cu):
    """시드 묶음 CI 는 시드 안 차이가 같으면 시드 평균의 t 구간과 같고, 무게가 같으면 무게 없는 꼴과 같다. 무게 꼴 = 무게 평균 · Σ_g(Σ w(d − m))² 표준오차.
    고르기는 가능하지 않은 길을 고르지 않는다(모두 막히면 RUN)."""
    d = np.array([1.0, 1.0, 2.0, 2.0, 3.0, 3.0])
    g = np.array([1, 1, 2, 2, 3, 3])
    r = cu.cluster_ci(d, g)
    se = np.std([1.0, 2.0, 3.0], ddof=1) / np.sqrt(3)
    assert r["mean"] == pytest.approx(2.0) and r["se"] == pytest.approx(se) and r["hi"] == pytest.approx(2.0 + cu.lv.t_crit(2) * se)
    assert cu.cluster_ci(d, g, np.full(6, 7.0)) == pytest.approx(r)
    w = np.array([1.0, 3.0, 1.0, 1.0, 2.0, 2.0])
    d2 = np.array([0.0, 4.0, 1.0, 3.0, -1.0, 5.0])
    m = (w * d2).sum() / w.sum()
    s = np.array([(w[g == k] * (d2[g == k] - m)).sum() for k in (1, 2, 3)])
    r2 = cu.cluster_ci(d2, g, w)
    assert r2["mean"] == pytest.approx(m) and r2["se"] == pytest.approx(np.sqrt(1.5 * (s * s).sum()) / w.sum())
    ok = np.array([[True, False, True, True], [True, True, False, True], [True, False, False, True]])
    sc = np.array([[0.1, 0.9, 0.5], [0.2, 0.3, 0.9], [0.0, 1.0, 1.0]])
    assert cu._masked_pick(sc, ok, True).tolist() == [2, 1, 0]
    assert cu._masked_pick(-sc, ok, False).tolist() == [2, 1, 0]
    assert cu._masked_pick(np.full((1, 3), -np.inf), ok[:1], True).tolist() == [0]


# --------------------------------------------------------------------- #
# 판단 규칙 (합성 자료)
# --------------------------------------------------------------------- #

N_SYN_SEEDS = 34
SYN_SEEDS = (34900, 34900 + N_SYN_SEEDS - 1)


def _roll(steps, cause="cover"):
    return dict(len=int(steps), contact=int(steps), cause=cause, closed=True, n=int(steps), got=0)


def _onset(cu, vals, ok, cues, chased=True):
    """시작 하나: vals = 길 넷의 쫓긴 스텝(흐름 셋 같음), 가짜 = RUN 과 같다(잡음 없음)."""
    arms = {f"real{r}": [_roll(vals[r])] * 3 for r in range(4) if ok[r]}
    arms.update({f"fake{a}": [_roll(vals[0])] * 3 for a in (1, 2, 3) if ok[a]})
    c = {k: 0.0 for k in cu.PERCEIVABLE + cu.PRIV}
    c.update(cues)
    return dict(t=1, deer=0, chased=bool(chased), ok=list(ok), cues=c, check=dict(all=True), L0=0, roll=12 * int(max(vals)), arms=arms)


def _raw(cu, kind, n_seeds=N_SYN_SEEDS, per=10, per_un=6, regions=("A", "B", "C"), smoke=False):
    """합성 raw: 쫓긴 시작 kind 'signal' = shelter_margin_m 의 부호가 정답을 가른다(> 0 SHELTER, ≤ 0 COVER), 'noise' = 정답이 단서와 무관한 우연.
    쫓기지 않은 시작은 모두 비김(쫓긴 시간 0) — 모든 시작(무게)에서는 이득이 묽어진다. 머리 = 미리 정한 측정 조건(시드는 SYN_SEEDS)."""
    g = np.random.default_rng(3 if kind == "signal" else 4)
    worlds = []
    for s in range(n_seeds):
        for reg in regions:
            ons = []
            for _ in range(per):
                m = float(g.normal())
                if kind == "signal":
                    vals = [40, 40, 10, 40] if m > 0 else [25, 10, 45, 30]
                else:
                    b = int(g.integers(3))
                    vals = [40, 40, 40, 40]
                    vals[b] = 10
                ons.append(_onset(cu, vals, (True, True, True, True), dict(shelter_margin_m=m, obs_pred_dist=float(g.random()))))
            for _ in range(per_un):
                ons.append(_onset(cu, [0, 0, 0, 0], (True, True, True, True), dict(shelter_margin_m=float(g.normal()), obs_pred_dist=float(g.random())),
                                  chased=False))
            worlds.append(dict(seed=34900 + s, region=reg, region_index=0, p_chased=cu.P_CHASED, p_unchased=cu.P_UNCHASED, onsets=ons,
                               main_steps=600, roll_steps=1200 * per, onsets_seen=60, chased_seen=12, wall_s=10.0))
    head = dict(cu.prereg_head(), cond="on", seeds=[34900, 34900 + n_seeds - 1], code=dict(world="w", tool="t"), smoke=smoke)
    return dict(head=head, world_set=head["world_set"], max_steps=300, seeds=[34900, 34900 + n_seeds - 1], code=dict(world="w", tool="t"),
                worlds=worlds, sec_per_world_step=0.01, wall_s=1.0, workers=4, smoke=smoke)


@pytest.fixture(scope="module")
def synth(cu):
    mp = pytest.MonkeyPatch()
    mp.setattr(cu, "MODELS", ("tree3", "logreg", "regret"))       # 빠르게 (고르기·가장 좋은 모델 셈은 그대로)
    mp.setattr(cu, "PERM_REPEATS", 1)
    mp.setattr(cu, "SEEDS", SYN_SEEDS)
    try:                                                          # 셈하는 동안만 바꾼다 (다른 시험은 진짜 상수로)
        return {k: cu.analyze_cond(_raw(cu, k)) for k in ("signal", "noise")}
    finally:
        mp.undo()


def test_decision_rule_proceed_and_two_route(cu, synth, monkeypatch):
    """단서가 정답을 가르면 진행(가장 중요한 단서 = 그 단서, 쫓긴·비기지 않은 시작에서 늘 SHELTER 대비 ≥ 0.3 초·간격 ≥ 30 %·CI 위 끝 < 0, 모든 시작(무게)
    CI 위 끝 < 0), 정답이 우연이면 두 길. 쫓기지 않은 비긴 시작은 모든 시작 표의 무게 평균에만 들어간다."""
    monkeypatch.setattr(cu, "SEEDS", SYN_SEEDS)
    s = synth["signal"]
    assert s["chased"] == N_SYN_SEEDS * 3 * 10 and s["unchased"] == N_SYN_SEEDS * 3 * 6 and s["nontied"] == s["chased"]
    assert s["subsets"]["nontied"]["seeds"] == N_SYN_SEEDS and s["subsets"]["all"]["n"] == s["sampled"]
    d = cu.decide({"on": s})
    assert d["verdict"] == "proceed" and d["checks"] == [True, True, True, True], d
    assert d["top_cues"][0]["cue"] == "shelter_margin_m" and not d["top_cues"][0]["in_obs"]
    sub = s["subsets"]["nontied"]
    m = sub["models"]["perc"][d["model"]]
    assert m["mean"] <= 10 * cu.STEP_S + 0.05 and m["gap_frac"] >= 0.95 and m["acc"] >= 0.98          # 0 근처 몇 개는 문턱 사이에 떨어질 수 있다
    assert sub["base"]["fake_gain"] == pytest.approx(0.0) and sub["base"]["oracle_corr"] == pytest.approx(10 * cu.STEP_S)
    al = s["subsets"]["all"]
    w_ch, w_un = 1.0 / cu.P_CHASED, 1.0 / cu.P_UNCHASED
    share = 10 * w_ch / (10 * w_ch + 6 * w_un)                                                   # 무게로 본 쫓긴 몫
    assert al["base"]["shelter"] == pytest.approx(share * sub["base"]["shelter"])
    assert al["models"]["perc"][d["model"]]["mean"] == pytest.approx(share * m["mean"])
    assert s["subsets"]["unchased"]["models"]["perc"][d["model"]]["mean"] == 0.0
    assert s["x_from_p"]["exact"] is not None
    n = synth["noise"]
    d = cu.decide({"on": n})
    assert d["verdict"] == "two_route" and not d["checks"][0], d
    assert cu.decide({"off": s})["verdict"] is None                          # 판단 조건(on) 없음
    assert cu.decide({"on": dict(s, partial=True)})["verdict"] is None      # 중간
    assert cu.decide({"on": dict(s, code=None)})["verdict"] is None         # 지문 없음


def _cond(cu, gain=0.5, frac=0.4, hi=-0.2, hi_all=-0.01, n=3000, seeds=100, head=None, seed_list=None, base_nontied=None, worlds=None):
    m = dict(mean=3.0, vs_shelter=dict(mean=-gain, lo=-gain - 0.1, hi=hi, se=0.05, n=n, groups=seeds), gap=1.0, gap_frac=frac)
    ma = dict(mean=0.6, vs_shelter=dict(mean=-0.05, lo=-0.1, hi=hi_all, se=0.02, n=4 * n, groups=seeds), gap=0.2, gap_frac=frac)
    sub = dict(n=n, seeds=seeds, best=dict(perc="hgb"), models=dict(perc=dict(hgb=m)), importance=dict(perc=[
        dict(cue="cover_margin_m", imp=0.2, in_obs=False), dict(cue="obs_escape_room", imp=0.1, in_obs=True), dict(cue="x", imp=-0.1, in_obs=False)]))
    sl = list(range(cu.SEEDS[0], cu.SEEDS[1] + 1)) if seed_list is None else list(seed_list)
    return {"on": dict(partial=False, code=dict(world="w"), head=dict(cu.prereg_head(), **(head or {})), seed_list=sl, regions=3,
                       worlds=3 * len(sl) if worlds is None else worlds, base_nontied=n if base_nontied is None else base_nontied,
                       subsets=dict(nontied=sub, all=dict(n=4 * n, seeds=seeds, models=dict(perc=dict(hgb=ma)))))}


def test_decision_rule_thresholds(cu):
    """문턱 넷: 이득 < 0.3 초, 간격 몫 < 30 %, CI 위 끝 ≥ 0, 모든 시작 CI 위 끝 ≥ 0 가운데 하나면 두 길. 표본 < 1,000·시드 < 30 이면 판단 없음."""
    d = cu.decide(_cond(cu))
    assert d["verdict"] == "proceed" and d["checks"] == [True] * 4 and [r["cue"] for r in d["top_cues"]] == ["cover_margin_m", "obs_escape_room"]
    assert cu.decide(_cond(cu, gain=0.29))["verdict"] == "two_route"
    assert cu.decide(_cond(cu, frac=0.29))["verdict"] == "two_route"
    assert cu.decide(_cond(cu, hi=0.01))["verdict"] == "two_route"
    assert cu.decide(_cond(cu, frac=float("nan")))["verdict"] == "two_route"          # 간격 ≤ 0
    d = cu.decide(_cond(cu, hi_all=0.0))                                              # 쫓긴 시작에선 낫지만 모든 시작에선 아님
    assert d["verdict"] == "two_route" and d["checks"] == [True, True, True, False]
    assert cu.decide(_cond(cu, n=999))["verdict"] is None
    assert cu.decide(_cond(cu, seeds=29))["verdict"] is None


def test_decision_requires_preregistered_run(cu):
    """미리 정한 측정 조건(덮기·끝 규칙·흐름·롤아웃·판·고르기 확률·기본 두뇌·스냅숏)·판단 시드·세계 수와 다르거나 연기 시험이면 판단하지 않는다.
    연장 시드(36000~36199)는 판단 시드만의 쫓긴·비기지 않은 시작이 1,000 밑일 때만 받는다."""
    for h in (dict(world_set={"features.obstacles.foliage.enabled": True}), dict(quiet_end=15), dict(streams=2), dict(max_steps=120),
              dict(main_steps=900), dict(p_chased=cu.P_CHASED * 0.5), dict(p_unchased=1.0), dict(model_default=False), dict(snapshot="x.json")):
        d = cu.decide(_cond(cu, head=h))
        assert d["verdict"] is None and "미리 정한 측정 조건" in d["why"] and list(h)[0] in d["why"], (h, d)
    d = cu.decide(_cond(cu, head=dict(smoke=True)))
    assert d["verdict"] is None and "연기 시험" in d["why"]
    assert cu.decide(_cond(cu, seed_list=range(cu.SEEDS[0], cu.SEEDS[1] - 9)))["verdict"] is None        # 시드가 모자람
    assert cu.decide(_cond(cu, seed_list=range(34900, 35000)))["verdict"] is None                       # 다른 시드
    ext = range(cu.SEEDS[0], cu.EXT_SEEDS[1] + 1)
    d = cu.decide(_cond(cu, seed_list=ext, base_nontied=1500))                                          # 연장 조건이 아닌데 늘림
    assert d["verdict"] is None and "연장" in d["why"]
    assert cu.decide(_cond(cu, seed_list=ext, base_nontied=800))["verdict"] == "proceed"                 # 미리 정한 연장 한 번
    assert cu.decide(_cond(cu, worlds=299))["verdict"] is None                                           # 세계가 빠짐
    assert cu.SEEDS[0] > 35199 and cu.SMOKE["seeds"][1] < 35000                                           # 판단 시드 ≠ 탐색·관문 시드


# --------------------------------------------------------------------- #
# 보고
# --------------------------------------------------------------------- #

def test_report_formatting(cu, synth, tmp_path, monkeypatch):
    """보고 글: 조건 머리·부분 집합 넷 표·모델 이름·판단·새 관측 후보·본 측정 어림(확률·명령). cmd_report 는 raw → cues.json·cues.md, 중간 jsonl 은
    개수만(눈가림 — 모델 표 없음)·판단 없음, 연기 시험은 판단 없음."""
    monkeypatch.setattr(cu, "SEEDS", SYN_SEEDS)
    an = dict(conds={"on": synth["signal"], "off": synth["noise"]}, decision=cu.decide({"on": synth["signal"]}))
    an["plan"] = cu.plan(an["conds"], {"on": 0.005, "off": None})
    p = an["plan"]
    s = synth["signal"]
    lo, f = cu.wilson_lo(s["nontied"], s["chased"]), s["nontied"] / s["chased"]
    exp_ch = s["chased_seen"] / s["main_steps"] * cu.MAIN_STEPS * p["worlds"]
    want = max(cu.TARGET_NONTIED / (f * exp_ch), cu.MIN_N * cu.PLAN_FLOOR / (lo * exp_ch))          # 점 추정 목표, 아래 끝에서도 표본 조건 × 1.5
    assert p["p_chased"] == min(1.0, np.ceil(want * 100 - 1e-9) / 100) and p["p_chased"] >= p["p_chased_floor"]
    assert p["conds"]["on"]["sec_per_world_step"] == cu.REF_SEC_14W and p["wall_s"] > 0
    assert p["conds"]["off"]["p"] == [cu.P_CHASED * cu.COMPARE_SCALE, cu.P_UNCHASED * cu.COMPARE_SCALE]
    assert cu.wilson_lo(7, 15) == pytest.approx(0.3135, abs=1e-3)
    text = cu.fmt(an, dict(runs={}, smoke=False))
    for want in ("숲 시야 켬 (판단 조건)", "숲 시야 끔 (견줌)", "쫓기며 시작·비기지 않음 (판단 1~3 표본)", "모든 도주 시작", "쫓기지 않은 시작 (보고만)",
                 "모든 쫓긴 시작 (보고만)", "늘 SHELTER", "regret 직접", "진행 — 길 고르기 계약", "shelter_margin_m", "본 측정 어림", "--workers 14",
                 "순열 중요도", "| 지역 |", "P 가 X 를 새나"):
        assert want in text, want
    monkeypatch.setattr(cu, "MODELS", ("tree3",))
    monkeypatch.setattr(cu, "PERM_REPEATS", 1)
    raw = _raw(cu, "signal", n_seeds=6, per=3, per_un=2, smoke=True)
    (tmp_path / "raw_on.json").write_text(json.dumps(raw), encoding="utf-8")
    head = dict(raw["head"], world_set={}, cond="off")
    lines = [json.dumps({"head": head})] + [json.dumps(w) for w in raw["worlds"][:6]] + ['{"seed": 1, "regi']      # 덜 쓰인 끝 줄
    (tmp_path / "worlds_off.jsonl").write_text("\n".join(lines), encoding="utf-8")
    h, ws = cu._jsonl(tmp_path / "worlds_off.jsonl")
    assert h == head and len(ws) == 6
    assert cu.cmd_report(type("A", (), dict(out=str(tmp_path)))()) == 0
    md = (tmp_path / "cues.md").read_text(encoding="utf-8")
    js = json.loads((tmp_path / "cues.json").read_text(encoding="utf-8"))
    assert "중간 (측정 중)" in md and "눈가림" in md and "판단 없음" in md and "연기 시험" in js["decision"]["why"]
    assert js["conds"]["off"]["partial"] and js["conds"]["off"]["subsets"] is None and not js["conds"]["on"]["partial"]
    assert md.count("| 단서 | 모델 |") == len(cu.SUBSETS)                                      # 끝난 on 의 표 넷만 (중간 off 는 없음)

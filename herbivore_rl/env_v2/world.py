"""V2 학습 환경 World — v1 `env/world.py` 에서 출발한 사본.

v1 파일은 언리얼에 연결된 계약(관측 7·행동 4)의 원본이라 한 줄도 바꾸지 않는다
(`Docs/RL_Policy/RL_V2_PLAN.md` 결정 3). V2 기능(속도·경계·기억·대담함·환경 상호작용)은
이 사본에 **스위치로** 붙인다. 스위치를 모두 끈 이 World 는 같은 시드에서 v1 World 와
결과가 완전히 같아야 한다 — `tests/test_env_v2.py` 가 고정한다.

기능 스위치는 `configs/v2.yaml` 의 `features:` 블록이다(`env_v2/features.py`). 새 기능이 뽑는
난수는 기능마다 따로 둔 스트림 `self.feature_rng(name)` 에서만 뽑는다. v1 난수 호출 순서가 바뀌면
같은 시드의 세계가 조용히 달라지고, 기능끼리 스트림을 나눠 쓰면 기능 하나를 켜고 끌 때 다른 기능의
세계가 바뀌기 때문이다 (계획서 4.4, 4.8).
"""

from __future__ import annotations

import numpy as np

from .features import Features, _check_name, _check_part, feature_stream, features_of
from .steering import EPS, clamp_magnitude, normalize, steer

# 관측 열 인덱스 (§3.1). 이 순서가 언리얼 FEcoObservationFragment와 일치해야 한다.
OBS_FOOD_DENSITY = 0
OBS_PREDATOR_COUNT = 1
OBS_PREDATOR_DISTANCE = 2
OBS_KIN_COUNT = 3
OBS_ENERGY = 4
OBS_RECENT_PREDATION = 5
OBS_COVER_DISTANCE = 6
OBS_DIM = 7

ACT_DIM = 4  # forage, cohesion, flee_dist, cover (§3.2)


class World:
    """N=128 슬롯 고정, 죽으면 그 슬롯에 리스폰 (§4.3).

    `step()` 은 항상 [0,1] 행동을 받는다 (§1.3). (-3,3) 출력의 sigmoid 변환은
    VecEnv 래퍼(§6.2)의 책임이지 이 클래스의 책임이 아니다.
    """

    def __init__(self, cfg, seeds=None, meta_seed: int = 0):
        self.cfg = cfg
        if seeds is None:
            lo, hi = cfg.train_seeds
            seeds = range(lo, hi)
        self.seeds = np.asarray(list(seeds), dtype=np.int64)
        self.meta = np.random.default_rng(meta_seed)
        self.N = int(cfg.N)
        self.features: Features = features_of(cfg)
        self.reset()

    # ------------------------------------------------------------------ #
    # reset / 세계 생성
    # ------------------------------------------------------------------ #

    def reset(self) -> np.ndarray:
        """§4.4 — 시드 하나가 무작위화 파라미터와 세계 배치를 모두 결정한다 (§3.5)."""
        cfg = self.cfg
        seed = int(self.meta.choice(self.seeds))
        r = self.rng = np.random.default_rng(seed)
        self.seed = seed
        # 기능별 난수 스트림은 처음 쓸 때 만든다(feature_rng). 세계를 새로 뽑으면 처음부터 다시 시작한다.
        self._feature_rngs: dict[tuple[str, int], np.random.Generator] = {}

        rd = cfg.rand
        self.size = float(r.uniform(*rd["world_size"]))
        self.M = int(r.integers(rd["predator_count"][0], rd["predator_count"][1] + 1))
        self.pred_speed_mult = float(r.uniform(*rd["pred_speed_mult"]))
        self.ranged_frac = float(r.uniform(*rd["ranged_frac"]))
        self.cover_frac_target = float(r.uniform(*rd["cover_frac"]))
        self.food_regen_mult = float(r.uniform(*rd["food_regen_mult"]))

        self._build_world()
        self._reset_stats()
        self._g = self._geometry()
        self._obs = self._obs_from(self._g)
        return self._obs

    def feature_rng(self, name: str, part: int = 0) -> np.random.Generator:
        """기능 `name` 의 난수 스트림. 이 세계의 시드에서 나오고 다른 기능·v1 스트림과 독립이다.

        같은 기능에 나중에 난수를 더할 때는 새 `part` 를 쓴다 (`env_v2/features.py` 규칙 3).
        """
        _check_name(name)
        _check_part(part)                   # 캐시를 찾기 전에 검사한다(True·1.0 은 키 1 과 같게 해시된다)
        key = (name, int(part))
        g = self._feature_rngs.get(key)
        if g is None:
            g = self._feature_rngs[key] = feature_stream(self.seed, name, part)
        return g

    def _build_world(self) -> None:
        cfg, r = self.cfg, self.rng
        N, size = self.N, self.size

        # --- 먹이 격자 (§4.2) ---
        # 셀마다 독립 균등난수를 깔면 먹이가 온 맵에 고르게 깔려서 따라갈 기울기가
        # 백색잡음이 된다 (측정: forage가 아무 이득이 없었다). 저주파 노이즈를
        # 문턱값으로 잘라 **패치**를 만들고, 재생은 그 용량(capacity)을 향해 간다.
        # 그래야 고갈된 패치가 비어 있는 채로 남고 먹이 탐색이 실제 문제가 된다.
        self.gw = int(np.ceil(size / cfg.food_cell))
        m = self._smooth(r.random((self.gw, self.gw)), int(cfg.food_patch_blur))
        m = (m - m.min()) / max(m.max() - m.min(), EPS)
        t = float(cfg.food_patch_threshold)
        self.food_cap = np.clip((m - t) / (1.0 - t), 0.0, 1.0)
        self.food = self.food_cap.copy()
        cc = (np.arange(self.gw) + 0.5) * cfg.food_cell      # 셀 중심 좌표
        self._cell_x, self._cell_y = np.meshgrid(cc, cc)     # 둘 다 (gw,gw)

        # --- 은신처 (§4.2): 셀 마스크 면적이 목표 비율에 닿을 때까지 원을 놓는다 ---
        centers, radii = [], []
        mask = np.zeros((self.gw, self.gw), dtype=bool)
        for _ in range(int(cfg.cover_max_count)):
            if mask.mean() >= self.cover_frac_target:
                break
            c = r.uniform(0.0, size, 2)
            rad = float(r.uniform(cfg.cover_r_min, cfg.cover_r_max))
            centers.append(c)
            radii.append(rad)
            mask |= (self._cell_x - c[0]) ** 2 + (self._cell_y - c[1]) ** 2 <= rad * rad
        self.cov_c = np.asarray(centers, dtype=np.float64).reshape(-1, 2)
        self.cov_r = np.asarray(radii, dtype=np.float64).reshape(-1)
        self.cover_cell = mask
        self.cover_frac_actual = float(mask.mean())

        # 은신처 셀은 재생 속도 0.3배 (§4.2)
        self.regen_field = cfg.food_regen_base * self.food_regen_mult * np.where(
            self.cover_cell, cfg.food_cover_regen_mult, 1.0
        )

        # --- 초식 (§4.3) ---
        self.pos = r.uniform(0.0, size, (N, 2))
        ang = r.uniform(0.0, 2 * np.pi, N)
        self.head = np.stack([np.cos(ang), np.sin(ang)], 1)
        self.energy = np.full(N, float(cfg.init_energy))
        self.repro_cd = np.zeros(N, dtype=np.int32)

        # --- 포식자 (§4.2) ---
        M = self.M
        self.pred_pos = r.uniform(0.0, size, (M, 2))
        pang = r.uniform(0.0, 2 * np.pi, M)
        self.pred_head = np.stack([np.cos(pang), np.sin(pang)], 1)
        self.pred_ranged = r.random(M) < self.ranged_frac
        base = cfg.herb_speed * self.pred_speed_mult
        self.pred_speed = np.where(self.pred_ranged, base * cfg.pred_ranged_speed_mult, base)
        self.pred_catch_r = np.where(
            self.pred_ranged, cfg.pred_ranged_catch_r, cfg.pred_melee_catch_r
        )
        # 포식 후 식사 쿨다운. §4.4가 포식자 속도를 herb_speed의 1.0~1.4배로 고정하므로
        # 한번 붙잡히면 도주로는 벗어날 수 없다. 쿨다운이 포식 압력의 상한을 정한다.
        self.pred_cd = np.zeros(M, dtype=np.int32)

        # --- 지역 피식 EMA (§3.1) ---
        self.pred_ema = 0.0
        self.t = 0

    # ------------------------------------------------------------------ #
    # 기하 (관측과 조향이 공유한다)
    # ------------------------------------------------------------------ #

    def _smooth(self, arr: np.ndarray, br: int) -> np.ndarray:
        """반경 br 셀 박스 평균. SAT를 새로 만든다 (reset 시 1회용)."""
        g = self.gw
        sat = np.zeros((g + 1, g + 1))
        np.cumsum(np.cumsum(arr, 0), 1, out=sat[1:, 1:])
        return self._box_mean(sat, max(1, br))

    def _box_mean(self, sat: np.ndarray, br: int) -> np.ndarray:
        """SAT에서 반경 br 셀 정사각 평균. 경계는 잘린 창의 실제 면적으로 나눈다."""
        g = self.gw
        i = np.arange(g)
        r0, r1 = np.clip(i - br, 0, g), np.clip(i + br + 1, 0, g)
        c0, c1 = r0, r1  # 정방 격자라 행/열 인덱스가 같다
        box = (
            sat[np.ix_(r1, c1)] - sat[np.ix_(r0, c1)] - sat[np.ix_(r1, c0)] + sat[np.ix_(r0, c0)]
        )
        return box / ((r1 - r0)[:, None] * (c1 - c0)[None, :])

    def _food_fields(self) -> None:
        """먹이 밀도(관측용)와 기울기(조향용)를 격자 전체에 대해 한 번 계산한다.

        두 필드의 블러 반경이 **다르다**. 일부러 그렇게 뒀다:

        - `food_blur` (관측 idx0): 반경 `see_r`. §9.4의
          `IWorldFoodProvider::GetFoodDensity(Location, Radius)` 와 맞추기 위한 반경 평균이다
          (각도 제한 없음 — 언리얼 인터페이스가 반경만 받는다).
        - `_food_g*` (조향 `food_grad`): 반경 `food_grad_blur` 셀. see_r 블러(11×11셀)에서
          기울기를 뽑으면 한 셀을 먹어치워도 값이 0.8%밖에 안 변해서, 개체 전원이 초기
          고밀도 지점으로 몰린 뒤 같은 셀을 두고 경쟁한다. 측정 결과 `forage=1`이
          `forage=0`보다 **덜 먹었다**. 좁은 반경을 쓰면 국소 고갈이 기울기에 바로 잡혀
          비어버린 주변을 벗어나는 방향을 가리킨다.

        `food_grad` 는 관측이 아니라 §3.3의 기하 입력이므로 이 분리가 §3 계약을 건드리지
        않는다. 언리얼도 `GetFoodDensity` 와 `FoodGrad` 를 별도로 제공한다 (§9.4/§9.5).
        """
        cfg = self.cfg
        g = self.gw
        sat = np.zeros((g + 1, g + 1))
        np.cumsum(np.cumsum(self.food, 0), 1, out=sat[1:, 1:])
        self.food_blur = self._box_mean(sat, max(1, int(round(cfg.see_r / cfg.food_cell))))
        gy, gx = np.gradient(self._box_mean(sat, max(1, int(cfg.food_grad_blur))))
        self._food_gx, self._food_gy = gx, gy

    def _cover_edge(self, p: np.ndarray):
        """은신처 원까지의 (dx, dy, 가장자리까지 거리) — 전부 (n,K)."""
        dx = self.cov_c[:, 0][None, :] - p[:, 0:1]
        dy = self.cov_c[:, 1][None, :] - p[:, 1:2]
        return dx, dy, np.sqrt(dx * dx + dy * dy) - self.cov_r[None, :]

    def _in_cover(self, p: np.ndarray) -> np.ndarray:
        """위치 `p` (n,2)가 은신처 원 안인가. 관측과 포식자 판정이 같은 정의를 쓴다."""
        if not len(self.cov_r):
            return np.zeros(len(p), dtype=bool)
        return self._cover_edge(p)[2].min(1) <= 0.0

    def _cell_index(self, p: np.ndarray):
        """월드 좌표 → 격자 인덱스 (ix=열, iy=행)."""
        k = 1.0 / self.cfg.food_cell
        ix = np.clip((p[:, 0] * k).astype(np.int32), 0, self.gw - 1)
        iy = np.clip((p[:, 1] * k).astype(np.int32), 0, self.gw - 1)
        return ix, iy

    def _geometry(self, idx: np.ndarray | None = None, out: dict | None = None) -> dict:
        """행 `idx` (None이면 전체)의 기하 정보를 계산한다.

        `out` 을 주면 그 딕셔너리의 해당 행만 덮어쓴다 (§4.5 `_observe_subset` 경로).
        """
        cfg = self.cfg
        if idx is None:
            idx = np.arange(self.N)
            self._food_fields()
        P = self.pos[idx]
        Hd = self.head[idx]
        n = len(idx)
        ar = np.arange(n)
        hx, hy = Hd[:, 0:1], Hd[:, 1:2]

        # 쌍별 계산은 전부 (n, ·) 2D로 둔다. (n,N,2) 3D 임시배열을 만들면 스텝의 75%를
        # 여기서 쓴다 (측정). 합산은 행렬곱으로 내려보낸다.

        # --- 동족: 시야(거리 + 각도) 내, 자기 제외 (§3.1 idx3) ---
        dx = self.pos[:, 0][None, :] - P[:, 0:1]
        dy = self.pos[:, 1][None, :] - P[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        invd = 1.0 / np.maximum(dist, EPS)
        kin_vis = (dist <= cfg.see_r) & ((dx * hx + dy * hy) * invd >= cfg.fov_cos)
        kin_vis[ar, idx] = False
        kin_f = kin_vis.astype(np.float64)
        kin_count = kin_f.sum(1)
        centroid = (kin_f @ self.pos) / np.maximum(kin_count, 1.0)[:, None]
        to_centroid = np.where(kin_count[:, None] > 0, normalize(centroid - P), 0.0)

        # --- separation: 반경 내 이웃마다 (1 - d/R) * 멀어지는 단위벡터, 합 후 크기 1로 clamp ---
        # sum_j w_ij * (pos_j - P_i)/d_ij  =  (c @ pos) - rowsum(c) * P,  c = w/d
        wgt = np.clip(1.0 - dist / cfg.sep_radius, 0.0, None)
        wgt[ar, idx] = 0.0
        c = wgt * invd
        separation = clamp_magnitude(-((c @ self.pos) - c.sum(1)[:, None] * P), 1.0)

        # --- 포식자 (§3.1 idx1, idx2) ---
        if self.M > 0:
            ex = self.pred_pos[:, 0][None, :] - P[:, 0:1]
            ey = self.pred_pos[:, 1][None, :] - P[:, 1:2]
            pd = np.sqrt(ex * ex + ey * ey)
            pinv = 1.0 / np.maximum(pd, EPS)
            pvis = (pd <= cfg.see_r) & ((ex * hx + ey * hy) * pinv >= cfg.fov_cos)
            pred_count = pvis.sum(1)
            masked = np.where(pvis, pd, np.inf)
            j = masked.argmin(1)
            d_pred_min = masked[ar, j]
            seen = np.isfinite(d_pred_min)[:, None]
            away = np.where(
                seen, -np.stack([ex[ar, j], ey[ar, j]], 1) * pinv[ar, j][:, None], 0.0
            )
        else:
            pred_count = np.zeros(n, dtype=np.int64)
            d_pred_min = np.full(n, np.inf)
            away = np.zeros((n, 2))

        # --- 은신처 (§3.1 idx6) ---
        if len(self.cov_r):
            cx, cy, edge = self._cover_edge(P)
            k = edge.argmin(1)
            e = edge[ar, k]
            in_cover = e <= 0.0
            cover_dist = np.clip(np.maximum(e, 0.0) / cfg.obs_cover_norm, 0.0, 1.0)
            to_cover = np.where(
                in_cover[:, None], 0.0, normalize(np.stack([cx[ar, k], cy[ar, k]], 1))
            )
        else:
            in_cover = np.zeros(n, dtype=bool)
            cover_dist = np.ones(n)
            to_cover = np.zeros((n, 2))

        # --- 먹이 (§3.1 idx0) ---
        ix, iy = self._cell_index(P)
        food_density = self.food_blur[iy, ix]
        food_grad = normalize(np.stack([self._food_gx[iy, ix], self._food_gy[iy, ix]], 1))

        vals = dict(
            food_grad=food_grad,
            food_density=food_density,
            to_centroid=to_centroid,
            kin_count=kin_count,
            separation=separation,
            d_pred_min=d_pred_min,
            pred_count=pred_count,
            away_from_pred=away,
            to_cover=to_cover,
            cover_dist=cover_dist,
            in_cover=in_cover,
        )
        if out is None:
            return vals
        for key, v in vals.items():
            out[key][idx] = v
        return out

    # ------------------------------------------------------------------ #
    # 관측 (§3.1)
    # ------------------------------------------------------------------ #

    def _obs_from(self, g: dict, idx: np.ndarray | None = None) -> np.ndarray:
        """§3.1 — 7개, float32, [0,1]. 정규화 상수는 전부 고정값이다 (§1.2)."""
        cfg = self.cfg
        sl = slice(None) if idx is None else idx
        n = self.N if idx is None else len(idx)
        o = np.empty((n, OBS_DIM), dtype=np.float32)
        o[:, OBS_FOOD_DENSITY] = np.clip(g["food_density"][sl], 0.0, 1.0)
        o[:, OBS_PREDATOR_COUNT] = np.clip(g["pred_count"][sl] / cfg.obs_pred_count_norm, 0.0, 1.0)
        o[:, OBS_PREDATOR_DISTANCE] = np.clip(g["d_pred_min"][sl] / cfg.see_r, 0.0, 1.0)
        o[:, OBS_KIN_COUNT] = np.clip(g["kin_count"][sl] / cfg.obs_kin_count_norm, 0.0, 1.0)
        o[:, OBS_ENERGY] = np.clip(self.energy[sl] / cfg.max_energy, 0.0, 1.0)
        o[:, OBS_RECENT_PREDATION] = min(self.pred_ema, 1.0)
        o[:, OBS_COVER_DISTANCE] = g["cover_dist"][sl]
        return o

    def _observe_subset(self, idx: np.ndarray) -> np.ndarray:
        """§4.5 — 리스폰된 슬롯만 재계산한다."""
        self._geometry(idx, out=self._g)
        return self._obs_from(self._g, idx)

    def observe(self) -> np.ndarray:
        return self._obs

    # ------------------------------------------------------------------ #
    # step (§4.5)
    # ------------------------------------------------------------------ #

    def step(self, a: np.ndarray):
        """`a`: (N,4) in [0,1] (§1.3). 반환: obs, reward, done, terminal_obs."""
        cfg = self.cfg
        a = np.asarray(a, dtype=np.float64)
        rew = np.full(self.N, cfg.rew_alive)

        # 1) 초식 이동 — §3.3 조향 수식. 벽 경계(§4.2), 토러스 없음.
        v = steer(self._g, a, cfg)
        self.pos = np.clip(self.pos + v, 0.0, self.size)
        moving = np.linalg.norm(v, axis=1) > EPS
        self.head = np.where(moving[:, None], normalize(v), self.head)

        # 2) 포식자 이동 + 포획 판정
        caught = self._step_predators()

        # 3) 섭식 · 대사 (§3.4 "에너지 획득 +1.0 × 획득량")
        e_drained = self.energy - cfg.energy_drain
        gain = self._eat(e_drained)
        e_new = np.minimum(e_drained + gain * cfg.food_energy_per_unit, cfg.max_energy)
        rew += cfg.rew_energy * (e_new - e_drained)
        self.energy = e_new

        # 4) 번식 — energy > threshold AND repro_cd == 0 (§3.4)
        self.repro_cd = np.maximum(self.repro_cd - 1, 0)
        repro = (self.energy > cfg.repro_threshold) & (self.repro_cd == 0)
        if repro.any():
            rew += cfg.rew_repro * repro
            self.energy = np.where(repro, cfg.init_energy, self.energy)
            self.repro_cd = np.where(repro, int(cfg.repro_cd), self.repro_cd)

        # 5) 사망: 피식 또는 아사
        starved = self.energy <= 0.0
        done = caught | starved
        rew += cfg.rew_death * done

        # 6) 지역 피식 EMA (§3.1). §9.6과 맞춰 피식 사망만 센다.
        n_pred_deaths = int(caught.sum())
        self.pred_ema = (
            cfg.predation_ema_decay * self.pred_ema
            + (1.0 - cfg.predation_ema_decay) * (n_pred_deaths / self.N) * cfg.predation_ema_gain
        )

        # 7) 먹이 재생 (§4.2). 셀 용량(패치 구조)을 향해 자란다.
        #    은신처 셀은 이미 0.3배가 반영된 regen_field.
        self.food += self.regen_field * (self.food_cap - self.food)
        np.clip(self.food, 0.0, self.food_cap, out=self.food)

        self.t += 1
        self._accumulate(a, rew, repro, caught, starved, done)

        # 8) 관측 — 스텝당 observe() 한 번 (§4.5)
        g = self._geometry()
        obs = self._obs_from(g)
        self._g, self._obs = g, obs
        terminal_obs = obs.copy()
        if done.any():
            dead = np.flatnonzero(done)
            self._respawn(dead)
            obs[dead] = self._observe_subset(dead)

        return obs, rew, done, terminal_obs

    def _step_predators(self) -> np.ndarray:
        """포식자 2종 (§4.2). 은신처 안 초식은 거리가 `cover_hide_mult` 배로 보인다."""
        cfg = self.cfg
        if self.M == 0:
            return np.zeros(self.N, dtype=bool)

        ar = np.arange(self.M)
        dx = self.pos[:, 0][None, :] - self.pred_pos[:, 0:1]      # (M,N)
        dy = self.pos[:, 1][None, :] - self.pred_pos[:, 1:2]
        dist = np.sqrt(dx * dx + dy * dy)
        inv = 1.0 / np.maximum(dist, EPS)
        # 이번 스텝 이동 후 위치 기준. self._g는 이동 전 기하라 여기서 다시 판정한다.
        hide = np.where(self._in_cover(self.pos), cfg.cover_hide_mult, 1.0)[None, :]
        perceived = dist * hide
        self.pred_cd = np.maximum(self.pred_cd - 1, 0)
        hunting = self.pred_cd == 0
        vis = (
            (perceived <= cfg.pred_view_r)
            & (
                (dx * self.pred_head[:, 0:1] + dy * self.pred_head[:, 1:2]) * inv
                >= cfg.pred_fov_cos
            )
            & hunting[:, None]
        )

        # 추적: 시야 내 최근접(체감 거리 기준)
        masked = np.where(vis, perceived, np.inf)
        j = masked.argmin(1)
        has_target = np.isfinite(masked[ar, j])
        turn = self.rng.uniform(-cfg.pred_wander_turn, cfg.pred_wander_turn, self.M)
        c, s = np.cos(turn), np.sin(turn)
        wander = np.stack(
            [
                self.pred_head[:, 0] * c - self.pred_head[:, 1] * s,
                self.pred_head[:, 0] * s + self.pred_head[:, 1] * c,
            ],
            1,
        )
        chase = np.stack([dx[ar, j], dy[ar, j]], 1) * inv[ar, j][:, None]
        move = np.where(has_target[:, None], chase, wander)
        self.pred_pos = self.pred_pos + move * self.pred_speed[:, None]
        # 벽에서 반사 (§4.2 토러스 끄기)
        for axis in (0, 1):
            out_of = (self.pred_pos[:, axis] < 0.0) | (self.pred_pos[:, axis] > self.size)
            move[out_of, axis] *= -1.0
        self.pred_pos = np.clip(self.pred_pos, 0.0, self.size)
        self.pred_head = normalize(move)

        # 포획: 근접형은 결정적, 원거리형은 확률적 (§4.2). 포식자당 한 스텝 한 마리.
        hit = (perceived <= self.pred_catch_r[:, None]) & hunting[:, None]
        if self.pred_ranged.any():
            roll = self.rng.random((self.M, self.N)) < cfg.pred_ranged_catch_p
            hit &= np.where(self.pred_ranged[:, None], roll, True)
        hit_d = np.where(hit, perceived, np.inf)
        k = hit_d.argmin(1)
        got = np.isfinite(hit_d[ar, k])
        caught = np.zeros(self.N, dtype=bool)
        caught[k[got]] = True
        self.pred_cd[got] = int(cfg.pred_eat_cd)
        return caught

    def _eat(self, e_drained: np.ndarray) -> np.ndarray:
        """셀당 총 수요를 잔량에 비례 배분한다. 개체별 루프 없음 (§1.1).

        수요는 **흡수 가능량**으로 제한한다: 배부른 개체가 먹이를 계속 퍼가면 맵 전체가
        벗겨져서(측정: food가 0.02로 수렴) 먹이 탐색이 무의미해진다. 이렇게 두면 총
        소비량이 총 대사 수요를 따라가고 패치가 유지된다.
        """
        cfg = self.cfg
        want = np.clip(
            (cfg.max_energy - e_drained) / cfg.food_energy_per_unit, 0.0, cfg.food_eat_rate
        )
        ix, iy = self._cell_index(self.pos)
        flat = iy * self.gw + ix
        cells = self.gw * self.gw
        demand = np.bincount(flat, weights=want, minlength=cells)
        taken = np.minimum(demand, self.food.reshape(-1))
        frac = np.divide(taken, demand, out=np.zeros(cells), where=demand > 0)
        self.food -= taken.reshape(self.gw, self.gw)
        return want * frac[flat]

    def _respawn(self, dead: np.ndarray) -> None:
        """§4.3 — 죽은 슬롯에 랜덤 위치로 리스폰. 개체군 동역학은 넣지 않는다."""
        r, k = self.rng, len(dead)
        self.pos[dead] = r.uniform(0.0, self.size, (k, 2))
        ang = r.uniform(0.0, 2 * np.pi, k)
        self.head[dead] = np.stack([np.cos(ang), np.sin(ang)], 1)
        self.energy[dead] = self.cfg.init_energy
        self.repro_cd[dead] = 0

    # ------------------------------------------------------------------ #
    # 통계 (§7.2)
    # ------------------------------------------------------------------ #

    def _reset_stats(self) -> None:
        self._rew_total = 0.0
        self._repro_total = 0
        self._pred_deaths = 0
        self._starve_deaths = 0   # §7.2 열은 아니고 경제 보정용 진단 카운터
        self._life_sum = 0
        self._life_count = 0
        self._life_cur = np.zeros(self.N, dtype=np.int64)
        self._act_sum = np.zeros(ACT_DIM)
        self._flee_sq = 0.0
        self._cover_steps = 0
        self._agent_steps = 0
        self._a_pred = np.zeros(3)   # cohesion, flee_dist, cover — 포식자 보일 때
        self._n_pred = 0
        self._a_nopred = np.zeros(3)
        self._n_nopred = 0
        self._f_hungry, self._n_hungry = 0.0, 0
        self._f_full, self._n_full = 0.0, 0

    def _accumulate(self, a, rew, repro, caught, starved, done) -> None:
        self._rew_total += float(rew.sum())
        self._repro_total += int(repro.sum())
        self._pred_deaths += int(caught.sum())
        self._starve_deaths += int(starved.sum())
        self._life_cur += 1
        if done.any():
            self._life_sum += int(self._life_cur[done].sum())
            self._life_count += int(done.sum())
            self._life_cur[done] = 0
        self._agent_steps += self.N
        self._act_sum += a.sum(0)
        self._flee_sq += float((a[:, 2] ** 2).sum())
        self._cover_steps += int(self._g["in_cover"].sum())

        seen = self._g["pred_count"] > 0
        cols = a[:, [1, 2, 3]]
        self._a_pred += cols[seen].sum(0)
        self._n_pred += int(seen.sum())
        self._a_nopred += cols[~seen].sum(0)
        self._n_nopred += int((~seen).sum())

        hungry = self.energy < 0.5 * self.cfg.max_energy
        self._f_hungry += float(a[hungry, 0].sum())
        self._n_hungry += int(hungry.sum())
        self._f_full += float(a[~hungry, 0].sum())
        self._n_full += int((~hungry).sum())

    def stats(self) -> dict:
        """§7.2 반환 열."""
        n, steps = self.N, max(self.t, 1)
        agent_steps = max(self._agent_steps, 1)
        lives = self._life_sum + int(self._life_cur.sum())
        n_lives = self._life_count + n
        flee_mean = self._act_sum[2] / agent_steps
        flee_var = max(self._flee_sq / agent_steps - flee_mean**2, 0.0)

        def _d(sum_a, n_a, sum_b, n_b):
            if n_a == 0 or n_b == 0:
                return float("nan")
            return float(np.abs(sum_a / n_a - sum_b / n_b).mean())

        return dict(
            mean_return=self._rew_total / n,
            survival=lives / max(n_lives, 1),
            repro=self._repro_total / n,
            predation_rate=self._pred_deaths / (steps * n),
            cohesion_mean=self._act_sum[1] / agent_steps,
            flee_dist_mean=flee_mean,
            flee_dist_std=float(np.sqrt(flee_var)),
            cover_frac=self._cover_steps / agent_steps,
            react_pred=_d(self._a_pred, self._n_pred, self._a_nopred, self._n_nopred),
            react_hunger=_d(
                np.array([self._f_hungry]),
                self._n_hungry,
                np.array([self._f_full]),
                self._n_full,
            ),
        )

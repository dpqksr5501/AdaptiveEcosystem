"""R10 감각 S1 계산 (0 단계 사양 7 절). observe(world) → (N, 206) float32, 죽은·빈 칸은 0.

모두 머리 기준(x 머리, y 왼쪽)이고 절대 위치·맵 크기·종 이름은 들어가지 않는다 — 맵을 옮기거나 돌려도 같은 감각.
"""

from __future__ import annotations

import numpy as np

from r10 import contract as C
from r10 import species as S
from r10 import terrain as T

RAY_D = np.array([0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0, 12.0, 16.0, 24.0, 32.0, 48.0, 60.0])
FOOD_D = np.array([1.0, 2.5, 5.0, 9.0])
FOOD_SPREAD = np.radians(np.array([-15.0, 0.0, 15.0]))
AHEAD_M = 2.0
COVER_BLOCK = 0.7


def _food_weights(world) -> np.ndarray:
    """(N, 8) 먹이 층별 가중 = 종 카드 먹이 선호 (물먹이는 매체와 상관없이 정보로 느낀다)."""
    p = world.p["diet"]
    return np.stack([p[:, S.DIET_KEYS.index(k)] for k in T.FOOD_KINDS], axis=1)


def abs_height(world) -> np.ndarray:
    c = world.cidx(world.wk, world.x, world.y)
    gz = world.g_z[c]
    return np.where(world.airborne, gz + world.z, np.where(world.swimming, world.z, gz))


def _rot(hx, hy, ang):
    ca, sa = np.cos(ang), np.sin(ang)
    return hx * ca - hy * sa, hx * sa + hy * ca


def observe(world) -> np.ndarray:
    w = world
    N = w.N
    p = w.p
    al = w.alive
    obs = np.zeros((N, C.OBS_DIM), np.float64)
    idx = np.arange(N)
    c = w.cidx(w.wk, w.x, w.y)
    tsec = w.t * C.STEP_S
    light = 0.5 + 0.5 * np.cos(2 * np.pi * (tsec / (C.DAY_STEPS * C.STEP_S)))
    rain = w.weather[w.wk, 0]
    snow = w.weather[w.wk, 1]
    temp = w.weather[w.wk, 2]

    # ---------------------------------------------------------------- 자기 14
    lo, _ = C.SLICES["self"]
    mat = np.maximum(p["maturity_days"], 1e-6)
    adult = w.age_days >= mat
    depth_here = w.depth_at(c)
    bed, surf = w.g_bed[c], w.surface_at(c)
    col = np.maximum(surf - bed, 1e-6)
    self_v = np.stack([
        np.clip(w.E, 0, 1), np.clip(w.R, 0, 1), w.stam, np.clip(w.hp, 0, 1), np.clip(w.age_days / (2 * mat), 0, 1),
        (adult & ~w.pregnant & (w.birth_wait <= 0)).astype(float),
        np.where(w.pregnant, 1.0 - np.clip(w.preg_left / np.maximum(p["gestation_days"], 1e-6), 0, 1), 0.0),
        C.lg(w.speed, 1.0, 25.0),
        np.where(w.airborne, C.lg(w.z, 0.5, 60.0), 0.0),
        np.where(w.swimming, np.clip((w.z - bed) / col, 0, 1), 0.0),
        w.swimming.astype(float), w.g_shelter[c].astype(float), np.clip(w.breath, 0, 1), w.airborne.astype(float),
    ], axis=1)
    obs[:, lo:lo + 14] = self_v

    # ---------------------------------------------------------------- 몸 16
    lo, hi = C.SLICES["body"]
    obs[:, lo:hi] = w.body_vec

    # ---------------------------------------------------------------- 8 방향 × 6
    lo, _ = C.SLICES["dir"]
    fw = _food_weights(w)
    high_air = w.airborne & (w.z >= w.rules.air_clear_m)
    sight = p["sight_m"]
    smell = np.maximum(p["smell_m"], sight * 0.5)
    for j in range(C.N_DIR):
        dx, dy = _rot(w.hx, w.hy, np.radians(45.0 * j))
        # 갈 수 있는 거리: 이 몸으로 표본점을 차례로 지나갈 수 있는 마지막 거리 (시야 안)
        free = np.zeros(N)
        going = np.ones(N, bool)
        px, py = w.x, w.y
        cover_max = np.zeros(N)
        for d in RAY_D:
            tx, ty = w.x + dx * d, w.y + dy * d
            ok = np.where(high_air, w.inside(w.wk, tx, ty), np.where(
                w.airborne, w.inside(w.wk, tx, ty) & ~w.g_block[w.cidx(w.wk, tx, ty)], w._pass_ok(idx, px, py, tx, ty)))
            going &= ok & (d <= np.maximum(sight, 1.0))
            free = np.where(going, d, free)
            if d <= 4.0:
                cover_max = np.maximum(cover_max, w.g_cover[w.cidx(w.wk, tx, ty)])
            px, py = tx, ty
        ax, ay = w.x + dx * AHEAD_M, w.y + dy * AHEAD_M
        ca = w.cidx(w.wk, ax, ay)
        rise = w.g_z[ca] - w.g_z[c]
        dep = w.depth_at(ca)
        cur = w.g_cur[ca, 0] * dx + w.g_cur[ca, 1] * dy
        food = np.zeros(N)
        for d in FOOD_D:
            for s in FOOD_SPREAD:
                ex, ey = _rot(dx, dy, s)
                fx, fy = w.x + ex * d, w.y + ey * d
                cf = w.cidx(w.wk, fx, fy)
                inr = (d <= smell) & w.inside(w.wk, fx, fy)
                food += np.where(inr, (w.g_food[:, cf].T * fw).sum(axis=1), 0.0)
        base = lo + j * len(C.DIR_FIELDS)
        obs[:, base + 0] = C.lg(free, C.NORM["dist_m"]["ref"], C.NORM["dist_m"]["max"])
        obs[:, base + 1] = C.slg(rise, C.NORM["height_m"]["ref"], C.NORM["height_m"]["max"])
        obs[:, base + 2] = C.lg(dep, C.NORM["depth_m"]["ref"], C.NORM["depth_m"]["max"])
        obs[:, base + 3] = C.slg(cur, C.NORM["current_mps"]["ref"], C.NORM["current_mps"]["max"])
        obs[:, base + 4] = cover_max
        obs[:, base + 5] = food / (food + C.NORM["food"]["ref"])

    # ---------------------------------------------------------------- 발밑 6
    lo, _ = C.SLICES["here"]
    food_here = (w.g_food[:, c].T * fw).sum(axis=1)
    eats_meat = (p["diet"][:, S.DIET_KEYS.index("meat")] + p["diet"][:, S.DIET_KEYS.index("carrion")]) > 0
    meat_here = np.zeros(N)
    cw = w.carcass["wk"]
    live = (cw >= 0) & (w.carcass["meat"] > 0)
    if live.any():
        ci = np.nonzero(live)[0]
        for i in np.nonzero(al & eats_meat)[0]:
            m = ci[cw[ci] == w.wk[i]]
            if len(m):
                dd = np.hypot(w.carcass["x"][m] - w.x[i], w.carcass["y"][m] - w.y[i])
                meat_here[i] = w.carcass["meat"][m][dd <= 1.0 + p["radius_m"][i]].sum()
    shelter_d = np.where(w.g_shelter[c], 0.0, 60.0)
    for j in range(C.N_DIR):
        dx, dy = _rot(w.hx, w.hy, np.radians(45.0 * j))
        for d in RAY_D:
            hit = w.g_shelter[w.cidx(w.wk, w.x + dx * d, w.y + dy * d)] & w.inside(w.wk, w.x + dx * d, w.y + dy * d)
            shelter_d = np.where(hit & (d < shelter_d), d, shelter_d)
    obs[:, lo + 0] = food_here / (food_here + C.NORM["food"]["ref"])
    obs[:, lo + 1] = meat_here / (meat_here + 5.0)
    obs[:, lo + 2] = np.where(w.swimming, C.lg(surf - w.z, 0.25, 5.0), 0.0)
    obs[:, lo + 3] = np.where(w.swimming, C.lg(w.z - bed, 0.25, 5.0), np.where(w.airborne, C.lg(w.z, 0.5, 60.0), 0.0))
    obs[:, lo + 4] = w._slope_deg(c) / 90.0
    obs[:, lo + 5] = 1.0 - C.lg(shelter_d, C.NORM["dist_m"]["ref"], C.NORM["dist_m"]["max"])

    # ---------------------------------------------------------------- 다른 동물 8 × 12 · 같은 종 4
    K, Sl = w.K, w.S
    X, Y = w.x.reshape(K, Sl), w.y.reshape(K, Sl)
    dxm = X[:, None, :] - X[:, :, None]             # [k, i(나), j(상대)]
    dym = Y[:, None, :] - Y[:, :, None]
    dist = np.hypot(dxm, dym)
    HX, HY = w.hx.reshape(K, Sl), w.hy.reshape(K, Sl)
    ux = dxm / np.maximum(dist, 1e-6)
    uy = dym / np.maximum(dist, 1e-6)
    cosv = HX[:, :, None] * ux + HY[:, :, None] * uy
    AL = al.reshape(K, Sl)
    nv = p["night_vision"].reshape(K, Sl)
    sight_eff = (sight.reshape(K, Sl) * (nv + (1 - nv) * light) * np.where(rain.reshape(K, Sl) > 0.5, w.rules.rain_sight, 1.0))
    hiding = ((w.actions == C.A_HIDE) & (w.speed < 0.2)).reshape(K, Sl)
    rng_eff = sight_eff[:, :, None] * np.where(hiding[:, None, :], 0.5, 1.0)
    fov = p["fov_cos"].reshape(K, Sl)[:, :, None]
    swim = w.swimming.reshape(K, Sl)
    air = w.airborne.reshape(K, Sl)
    hz = abs_height(w).reshape(K, Sl)
    near_surf = (w.z >= w.surface_at(c) - 0.5).reshape(K, Sl)
    # 물 안팎: 물속 몸은 수면 가까이 있을 때만 물 밖 몸과 서로 보인다
    cross = swim[:, :, None] != swim[:, None, :]
    water_ok = ~cross | np.where(swim[:, None, :], near_surf[:, None, :], near_surf[:, :, None])
    # 가림: 중간 두 점의 시야 가림
    vis_cover = np.zeros_like(dist)
    for f in (0.33, 0.66):
        mx = X[:, :, None] + dxm * f
        my = Y[:, :, None] + dym * f
        wkk = np.broadcast_to(np.arange(K)[:, None, None], mx.shape)
        cc = w.cidx(wkk.ravel(), mx.ravel(), my.ravel()).reshape(mx.shape)
        vis_cover = np.maximum(vis_cover, w.g_cover[cc])
    either_air = air[:, :, None] | air[:, None, :]
    vis = (AL[:, :, None] & AL[:, None, :] & (dist <= rng_eff) & (cosv >= fov) & water_ok
           & ((vis_cover < COVER_BLOCK) | either_air | (dist < 2.0)))
    eye = np.eye(Sl, dtype=bool)[None]
    vis &= ~eye
    order = np.argsort(np.where(vis, dist, np.inf), axis=2, kind="stable")[:, :, :C.N_OTHER]
    VX, VY = w.vx.reshape(K, Sl), w.vy.reshape(K, Sl)
    spd = np.hypot(VX, VY)
    rad = p["radius_m"].reshape(K, Sl)
    mass = p["mass_kg"].reshape(K, Sl)
    sp = w.sp.reshape(K, Sl)
    lo, _ = C.SLICES["other"]
    kk = np.arange(K)[:, None]
    ii = np.arange(Sl)[None, :]
    for n in range(C.N_OTHER):
        jj = order[:, :, n]
        present = vis[kk, ii, jj]
        dd = dist[kk, ii, jj]
        rx, ry = dxm[kk, ii, jj], dym[kk, ii, jj]
        # 머리 기준으로 돌림
        lx = (rx * HX + ry * HY) / np.maximum(dd, 1e-6)
        ly = (-rx * HY + ry * HX) / np.maximum(dd, 1e-6)
        lgd = C.lg(dd, C.NORM["dist_m"]["ref"], C.NORM["dist_m"]["max"])
        rvx, rvy = VX[kk, jj] - VX, VY[kk, jj] - VY
        approach = -(rvx * rx + rvy * ry) / np.maximum(dd, 1e-6)
        to_me_x, to_me_y = -rx / np.maximum(dd, 1e-6), -ry / np.maximum(dd, 1e-6)
        facing = HX[kk, jj] * to_me_x + HY[kk, jj] * to_me_y
        f = np.stack([
            np.ones_like(dd), lgd * lx, lgd * ly,
            C.slg(approach, C.NORM["speed_mps"]["ref"], C.NORM["speed_mps"]["max"]),
            C.lg(spd[kk, jj], C.NORM["speed_mps"]["ref"], C.NORM["speed_mps"]["max"]),
            C.ratio(rad[kk, jj], rad), C.ratio(mass[kk, jj], mass),
            swim[kk, jj].astype(float), air[kk, jj].astype(float),
            C.slg(hz[kk, jj] - hz, C.NORM["height_m"]["ref"], C.NORM["height_m"]["max"]),
            (sp[kk, jj] == sp).astype(float), facing,
        ], axis=-1)
        f = np.where(present[..., None], f, 0.0)
        obs[:, lo + n * 12: lo + (n + 1) * 12] = f.reshape(N, 12)
    lo, _ = C.SLICES["kin"]
    kin = vis & (sp[:, :, None] == sp[:, None, :])
    cnt = kin.sum(axis=2)
    cx = np.where(kin, dxm, 0).sum(axis=2) / np.maximum(cnt, 1)
    cy = np.where(kin, dym, 0).sum(axis=2) / np.maximum(cnt, 1)
    cd = np.hypot(cx, cy)
    kl = C.lg(cd, C.NORM["dist_m"]["ref"], C.NORM["dist_m"]["max"])
    obs[:, lo + 0] = np.clip(cnt / C.NORM["kin_count_max"], 0, 1).reshape(N)
    obs[:, lo + 1] = (kl * (cx * HX + cy * HY) / np.maximum(cd, 1e-6)).reshape(N)
    obs[:, lo + 2] = (kl * (-cx * HY + cy * HX) / np.maximum(cd, 1e-6)).reshape(N)
    obs[:, lo + 3] = (C.lg(np.where(kin, spd[:, None, :], 0).sum(axis=2) / np.maximum(cnt, 1), 1.0, 25.0)).reshape(N)

    # ---------------------------------------------------------------- 환경 6
    lo, _ = C.SLICES["env"]
    trend = (w.level - w.level_prev)[w.wk] / C.STEP_S
    obs[:, lo + 0] = light
    obs[:, lo + 1] = rain
    obs[:, lo + 2] = snow
    obs[:, lo + 3] = temp
    obs[:, lo + 4] = C.slg(trend, 0.005, 0.1)
    obs[:, lo + 5] = 0.0

    obs = np.clip(obs, -1.0, 1.0) * w.omask * al[:, None]
    return obs.astype(np.float32)

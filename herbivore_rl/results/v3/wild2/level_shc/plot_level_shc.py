"""팀 PR ff8c8f4 의 나무(LV_SHC_RegionalWeatherTest)를 우리 무대(LV_Ecosystem_IntegrationTest 통합 v3 모드)와 겹쳐 그린다 (10-17). herbivore_rl/ 에서

    python results/v3/wild2/level_shc/plot_level_shc.py

입력(이 폴더): scan_LV_SHC_RegionalWeatherTest.json·scan_LV_Ecosystem_IntegrationTest.json(unreal_level_scan.py 결과),
v3_export_integration_s20000.json(통합 v3 모드 -EcoV3ObstacleExport — 무대 원점·원판·은신처 원).
두 맵은 같은 지형·같은 지역 상자·같은 먹이 자리(무대 중심)를 쓴다(스캔에서 확인) — 그래서 SHC 나무 자리를 통합 맵 무대 좌표로 그대로 옮긴다.

출력(이 폴더): stage_<지역>.png 셋(무대 + 둘레 50 m), map_overview.png(맵 전체), forest_trees.png(숲 지역의 나무 11 그루),
beech_tree_collision.png(나무 하나의 충돌 모양), summary.json(무대마다 우리 레벨 읽기가 집을 원판 수와 나무별 수치).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as fm  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Circle, Polygon, Rectangle  # noqa: E402
from scipy.spatial import ConvexHull  # noqa: E402

HERE = Path(__file__).resolve().parent
UNIT_CM = 200.0           # 무대 단위 1 = 200 cm (EcoRepertoireV3::kUnitCm)
MIN_R_CM, MIN_H_CM = 25.0, 50.0   # FEcoV3ObstacleScan::kMinRadiusCm·kMinHeightCm
BODY_Z_CM = 60.0          # 사슴 몸 높이 어림 (땅 위 60 cm 에서 충돌 단면을 잰다)

# 색 (dataviz 기본 범주 순서: 파랑·주황·청록·노랑·자홍 …) — 글자는 검정/회색 잉크
C_SHELTER = "#2a78d6"
C_DISC = "#eb6834"
C_DEER = "#1baf7a"
C_HULL = "#4a3aa7"
C_TRUNK = "#52514e"
C_GRASS = "#9a9890"
INK, INK2 = "#0b0b0b", "#52514e"


def use_korean_font() -> None:
    have = {f.name for f in fm.fontManager.ttflist}
    for name in ("Malgun Gothic", "NanumGothic", "Gulim", "Batang", "MS Gothic"):
        if name in have:
            matplotlib.rcParams["font.family"] = name
            matplotlib.rcParams["axes.unicode_minus"] = False
            return


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def hull_section(verts: np.ndarray, z: float) -> np.ndarray | None:
    """볼록 껍질 꼭짓점(메시 공간)을 높이 z 평면으로 자른 다각형 (가로 점들)."""
    if z <= verts[:, 2].min() or z >= verts[:, 2].max():
        return None
    hull = ConvexHull(verts)
    pts = []
    for s in hull.simplices:
        for i in range(3):
            a, b = verts[s[i]], verts[s[(i + 1) % 3]]
            if (a[2] - z) * (b[2] - z) <= 0 and a[2] != b[2]:
                t = (z - a[2]) / (b[2] - a[2])
                pts.append(a[:2] + (b[:2] - a[:2]) * t)
    if len(pts) < 3:
        return None
    P = np.array(pts)
    return P[ConvexHull(P).vertices]


def main() -> None:
    use_korean_font()
    shc = load("scan_LV_SHC_RegionalWeatherTest.json")
    integ = load("scan_LV_Ecosystem_IntegrationTest.json")
    export = load("v3_export_integration_s20000.json")

    beech_path = next(p for p in shc["meshes"] if "Beech_Tree" in p)
    beech = shc["meshes"][beech_path]
    hull = np.array(beech["simple_collision"]["verts_mesh_cm"], dtype=float)
    base = np.array(beech["render_base"]["base_verts_mesh_cm"], dtype=float)
    trunk_r_mesh = float(np.max(np.hypot(base[:, 0] - base[:, 0].mean(), base[:, 1] - base[:, 1].mean())))

    trees = []
    for a in shc["actors"]:
        for s in a.get("static_meshes", []):
            if not s["collides"]:
                continue
            for inst in s["instances"]:
                t, sc = np.array(inst["t"]), np.array(inst["s"])
                g0 = inst["ground_z"]["0"]
                lift = (g0 - t[2]) if g0 is not None else 0.0      # 줄기 밑이 땅 밑으로 묻힌 깊이 (+ 묻힘, − 떠 있음)
                zsec = (lift + BODY_Z_CM) / sc[2]                   # 땅 위 60 cm 의 메시 공간 높이
                sec = hull_section(hull, zsec)
                sec_w = None if sec is None else sec * sc[:2] + t[:2]
                eq_r = 0.0 if sec is None else float(np.sqrt(ConvexHull(sec * sc[:2]).volume / np.pi))
                trees.append({"label": a["label"], "x": t[0], "y": t[1], "z": t[2], "scale": sc.tolist(), "ground_z": g0,
                              "buried_cm": round(lift, 1), "reader_disc": inst.get("reader_disc"),
                              "trunk_r_cm": round(trunk_r_mesh * sc[0], 1), "body_section_eq_r_cm": round(eq_r, 1),
                              "body_section_world": None if sec_w is None else sec_w.tolist()})

    # 통합 맵 무대 (export) + 레벨 은신처 앵커·먹이 자리·풀 (integ 스캔)
    stages = {r["region"]: r for r in export["regions"]}
    anchors = [a for a in integ["actors"] if a["class"] == "EcoShelterAnchor"]
    grass = []
    for a in integ["actors"]:
        if a["class"] == "InstancedFoliageActor":
            for s in a["static_meshes"]:
                grass += [(i["t"][0], i["t"][1]) for i in s["instances"]]

    summary = {"source": "LV_SHC_RegionalWeatherTest 나무를 LV_Ecosystem_IntegrationTest 무대 좌표에 겹침 (두 맵은 같은 지형·지역·먹이 자리)",
               "beech_mesh": beech_path, "beech_agg_counts": beech["agg_counts"],
               "beech_hull_aabb_mesh_cm": [hull.min(0).round(2).tolist(), hull.max(0).round(2).tolist()],
               "beech_trunk_base_r_cm_at_scale1": round(trunk_r_mesh, 1), "stages": {}, "trees": []}
    for name, r in stages.items():
        ox, oy = r["origin_cm"][0], r["origin_cm"][1]
        size_cm = r["size"] * UNIT_CM
        kept = []
        for tr in trees:
            d = tr["reader_disc"]
            cx, cy = d["center_cm"][0] - ox, d["center_cm"][1] - oy
            inside = 0 <= cx <= size_cm and 0 <= cy <= size_cm
            if inside and d["r_cm"] >= MIN_R_CM and d["height_cm"] >= MIN_H_CM:
                kept.append(tr["label"])
        summary["stages"][name] = {"origin_cm": r["origin_cm"], "size_m": size_cm / 100, "discs_in_unreal_export": len(r["discs"]),
                                   "shc_trees_reader_would_keep": len(kept), "kept": kept, "covers": r["covers"]}
    for tr in trees:
        f = stages["Forest"]
        ox, oy, sz = f["origin_cm"][0], f["origin_cm"][1], f["size"] * UNIT_CM
        dx = max(ox - tr["x"], 0.0, tr["x"] - (ox + sz))
        dy = max(oy - tr["y"], 0.0, tr["y"] - (oy + sz))
        row = {k: v for k, v in tr.items() if k != "body_section_world"}
        row["dist_to_forest_stage_m"] = round(float(np.hypot(dx, dy)) / 100, 1)
        summary["trees"].append(row)
    (HERE / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    def draw_tree(ax, tr, s=1.0, labels=True):
        d = tr["reader_disc"]
        ax.add_patch(Circle((d["center_cm"][0] * s, d["center_cm"][1] * s), d["r_cm"] * s, fill=False, ec=C_DISC, lw=1.6, ls="--", zorder=3))
        if tr["body_section_world"]:
            ax.add_patch(Polygon(np.array(tr["body_section_world"]) * s, closed=True, fc=C_HULL, alpha=0.25, ec=C_HULL, lw=1.2, zorder=3))
        ax.add_patch(Circle((tr["x"] * s, tr["y"] * s), max(tr["trunk_r_cm"], 1) * s, fc=C_TRUNK, ec="none", zorder=4))
        if labels:
            ax.annotate(tr["label"].replace("Beech_Tree", "나무"), (tr["x"] * s, tr["y"] * s), xytext=(6, 6), textcoords="offset points",
                        fontsize=8, color=INK2, zorder=5)

    # ---- 무대 셋 ----
    margin = 5000.0
    for name, r in stages.items():
        ox, oy = r["origin_cm"][0], r["origin_cm"][1]
        size_cm = r["size"] * UNIT_CM
        fig, ax = plt.subplots(figsize=(8.2, 8.2), dpi=130)
        ax.add_patch(Rectangle((ox, oy), size_cm, size_cm, fc=C_DEER, alpha=0.12, ec=INK, lw=1.4, zorder=1))
        for (cx, cy, cr) in r["covers"]:
            ax.add_patch(Circle((ox + cx * UNIT_CM, oy + cy * UNIT_CM), cr * UNIT_CM, fc=C_SHELTER, alpha=0.18, ec=C_SHELTER, lw=1.4, zorder=2))
        for (x, y, rr) in r["discs"]:
            ax.add_patch(Circle((ox + x * UNIT_CM, oy + y * UNIT_CM), rr * UNIT_CM, fc=C_DISC, ec=C_DISC, zorder=3))
        for k, a in enumerate(anchors):
            x, y = a["loc"][0], a["loc"][1]
            if ox - margin <= x <= ox + size_cm + margin and oy - margin <= y <= oy + size_cm + margin:
                ax.plot(x, y, marker="x", ms=9, mew=2, color=C_SHELTER, zorder=4)
                ax.annotate(f"레벨 은신처 {a['label'][-2:]} (학습 범위 밖이라 뺌)", (x, y), xytext=(-150, 10 if k == 0 else -16), textcoords="offset points",
                            fontsize=8, color=INK2)
        gx = [g for g in grass if ox <= g[0] <= ox + size_cm and oy <= g[1] <= oy + size_cm]
        if gx:
            ax.scatter([g[0] for g in gx], [g[1] for g in gx], s=10, c=C_GRASS, zorder=2, label=f"충돌 없는 풀 {len(gx)} (원판 아님)")
        near = [tr for tr in trees if ox - margin <= tr["x"] <= ox + size_cm + margin and oy - margin <= tr["y"] <= oy + size_cm + margin]
        for tr in near:
            draw_tree(ax, tr)
        ax.plot(ox + size_cm / 2, oy + size_cm / 2, marker="+", ms=12, mew=2, color=INK, zorder=4)
        ax.annotate("먹이 자리 (무대 중심)", (ox + size_cm / 2, oy + size_cm / 2), xytext=(8, 4), textcoords="offset points", fontsize=8, color=INK2)
        ax.set_xlim(ox - margin, ox + size_cm + margin)
        ax.set_ylim(oy - margin, oy + size_cm + margin)
        ax.set_aspect("equal")
        ticks = np.arange(-margin, size_cm + margin + 1, 2000.0)
        ax.set_xticks(ox + ticks, [f"{t / 100:.0f}" for t in ticks])
        ax.set_yticks(oy + ticks, [f"{t / 100:.0f}" for t in ticks])
        ax.set_xlabel("무대 원점에서 x (m)", color=INK2)
        ax.set_ylabel("무대 원점에서 y (m)", color=INK2)
        ax.grid(color="#e4e3df", lw=0.6, zorder=0)
        n_keep = summary["stages"][name]["shc_trees_reader_would_keep"]
        ax.set_title(f"{name} 무대 (한 변 {size_cm / 100:.0f} m, 원점 {ox:.0f}, {oy:.0f} cm) — 원판 {len(r['discs'])} · SHC 나무 무대 안 {n_keep}",
                     fontsize=10, color=INK)
        handles = [Rectangle((0, 0), 1, 1, fc=C_DEER, alpha=0.3, ec=INK, label="사슴 128 시작 = 무대 전체 균등 (늑대 4 는 모든 사슴에서 28 m 밖)"),
                   Circle((0, 0), 1, fc=C_SHELTER, alpha=0.3, ec=C_SHELTER, label="은신처 원 4 (v3, 반경 12 m)")]
        if near:
            handles += [Circle((0, 0), 1, fc=C_TRUNK, label="나무 줄기 (그리기 메시 밑동, 반경 0.8 m)"),
                        Polygon([[0, 0], [1, 0], [1, 1]], fc=C_HULL, alpha=0.3, ec=C_HULL, label="충돌 단면 (땅 위 60 cm, 볼록 껍질)"),
                        Circle((0, 0), 1, fill=False, ec=C_DISC, ls="--", label="우리 레벨 읽기 원판이라면 (반경 13.8 m)")]
        if gx:
            handles.append(ax.collections[-1])
        ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.08), fontsize=8, frameon=False)
        fig.tight_layout()
        fig.savefig(HERE / f"stage_{name}.png")
        plt.close(fig)

    # ---- 맵 전체 ----
    fig, ax = plt.subplots(figsize=(9, 9), dpi=120)
    for a in shc["actors"]:
        if a["class"] == "EcologyRegion":
            o, e = a["bounds_origin"], a["bounds_extent"]
            ax.add_patch(Rectangle((o[0] - e[0], o[1] - e[1]), 2 * e[0], 2 * e[1], fill=False, ec=INK2, lw=1.0))
            ax.annotate(f"지역 {a['region_id']}", (o[0] - e[0] + 1500, o[1] + e[1] - 4000), fontsize=9, color=INK2)
    for name, r in stages.items():
        ox, oy = r["origin_cm"][0], r["origin_cm"][1]
        ax.add_patch(Rectangle((ox, oy), r["size"] * UNIT_CM, r["size"] * UNIT_CM, fc=C_DEER, alpha=0.5, ec=INK, lw=1.0))
        ax.annotate(f"{name} 무대", (ox + r["size"] * UNIT_CM + 1200, oy), fontsize=8, color=INK)
    ax.scatter([t["x"] for t in trees], [t["y"] for t in trees], s=18, c=C_DISC, label=f"SHC 나무 {len(trees)}")
    for a in shc["actors"]:
        lab = a["label"]
        if a["class"] == "PlayerStart":
            ax.plot(a["loc"][0], a["loc"][1], marker="^", ms=8, color=INK, label="PlayerStart (SHC)")
        if a["class"].startswith("BP_SHC_"):
            ax.plot(a["loc"][0], a["loc"][1], marker="s", ms=7, color=C_HULL)
            ax.annotate(lab.replace("BP_SHC_", "").replace("RegionalWeather", " 날씨") + f" → {a['vars'].get('RegionBounds', '').replace('Actor:', '')}",
                        (a["loc"][0], a["loc"][1]), xytext=(6, -12), textcoords="offset points", fontsize=8, color=INK2)
    for a in integ["actors"]:
        if a["class"] == "PlayerStart":
            ax.plot(a["loc"][0], a["loc"][1], marker="^", ms=8, color=INK2, mfc="none", label="PlayerStart (통합 맵)")
    ax.set_xlim(-76000, 76000)
    ax.set_ylim(-76000, 76000)
    ax.set_aspect("equal")
    t = np.arange(-75000, 75001, 25000)
    ax.set_xticks(t, [f"{v / 100:.0f}" for v in t])
    ax.set_yticks(t, [f"{v / 100:.0f}" for v in t])
    ax.set_xlabel("x (m)", color=INK2)
    ax.set_ylabel("y (m)", color=INK2)
    ax.grid(color="#e4e3df", lw=0.6)
    ax.set_title("맵 전체 (위에서): 지역 상자 셋, 우리 무대 셋(120 m), SHC 나무 11 — 나무는 모두 숲 지역, 무대 밖", fontsize=10, color=INK)
    ax.legend(loc="lower left", fontsize=8, frameon=False)
    fig.tight_layout()
    fig.savefig(HERE / "map_overview.png")
    plt.close(fig)

    # ---- 숲 지역 나무 ----
    f = stages["Forest"]
    ox, oy, sz = f["origin_cm"][0], f["origin_cm"][1], f["size"] * UNIT_CM
    fig, ax = plt.subplots(figsize=(11, 7.2), dpi=120)
    ax.add_patch(Rectangle((ox, oy), sz, sz, fc=C_DEER, alpha=0.15, ec=INK, lw=1.4))
    ax.annotate("숲 무대 (120 m)", (ox + 300, oy + sz - 1200), fontsize=9, color=INK)
    for (cx, cy, cr) in f["covers"]:
        ax.add_patch(Circle((ox + cx * UNIT_CM, oy + cy * UNIT_CM), cr * UNIT_CM, fc=C_SHELTER, alpha=0.2, ec=C_SHELTER, lw=1.0))
    for tr in trees:
        draw_tree(ax, tr)
    for a in shc["actors"]:
        if a["class"] == "PlayerStart":
            ax.plot(a["loc"][0], a["loc"][1], marker="^", ms=9, color=INK)
            ax.annotate("PlayerStart (SHC)", (a["loc"][0], a["loc"][1]), xytext=(6, -12), textcoords="offset points", fontsize=8, color=INK2)
    xs = [t["x"] for t in trees] + [ox, ox + sz]
    ys = [t["y"] for t in trees] + [oy, oy + sz]
    ax.set_xlim(min(xs) - 3000, max(xs) + 3000)
    ax.set_ylim(min(ys) - 3000, max(ys) + 3000)
    ax.set_aspect("equal")
    tx = np.arange(np.floor((min(xs) - 3000) / 5000) * 5000, max(xs) + 3001, 5000)
    ty = np.arange(np.floor((min(ys) - 3000) / 5000) * 5000, max(ys) + 3001, 5000)
    ax.set_xticks(tx, [f"{v / 100:.0f}" for v in tx])
    ax.set_yticks(ty, [f"{v / 100:.0f}" for v in ty])
    ax.set_xlabel("x (m)", color=INK2)
    ax.set_ylabel("y (m)", color=INK2)
    ax.grid(color="#e4e3df", lw=0.6)
    ax.set_title("숲 지역의 SHC 나무 11: 줄기(회색)·땅 위 60 cm 충돌 단면(보라)·우리 원판이라면(주황 점선)", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(HERE / "forest_trees.png")
    plt.close(fig)

    # ---- 나무 하나의 충돌 모양 ----
    sc = 2.0
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5.6), dpi=120)
    H = hull * sc / 100.0
    side = H[ConvexHull(H[:, [0, 2]]).vertices][:, [0, 2]]
    a1.add_patch(Polygon(side, closed=True, fc=C_HULL, alpha=0.2, ec=C_HULL, lw=1.4, label="단순 충돌 (볼록 껍질 1 개, 꼭짓점 32) 옆모습"))
    a1.add_patch(Rectangle((-trunk_r_mesh * sc / 100, 0), 2 * trunk_r_mesh * sc / 100, 2.0, fc=C_TRUNK, label="줄기 밑동 (그리기 메시, 반경 0.8 m)"))
    r_disc = trees[0]["reader_disc"]["r_cm"] / 100
    a1.plot([-r_disc, r_disc], [-0.4, -0.4], color=C_DISC, lw=2.5, label=f"우리 원판 지름 (반경 {r_disc:.1f} m)")
    a1.axhspan(0, 1.2, color=C_DEER, alpha=0.12, label="사슴 몸 높이 (0~1.2 m)")
    a1.set_xlim(-17, 17)
    a1.set_ylim(-1.5, 27)
    a1.set_aspect("equal")
    a1.set_xlabel("x (m, 크기 2 배)", color=INK2)
    a1.set_ylabel("줄기 밑에서 높이 (m)", color=INK2)
    a1.grid(color="#e4e3df", lw=0.6)
    a1.legend(loc="upper left", fontsize=8, frameon=False)
    a1.set_title("Beech_Tree 옆에서 (x-z)", fontsize=10, color=INK)
    for hz, ls in ((0.05, ":"), (0.6, "-"), (1.5, "--")):
        s = hull_section(hull, hz * 100 / sc)
        if s is not None:
            P = s * sc / 100
            a2.add_patch(Polygon(P, closed=True, fill=False, ec=C_HULL, lw=1.4, ls=ls,
                                 label=f"충돌 단면 {hz:.2f} m (같은 넓이 원 반경 {np.sqrt(ConvexHull(P).volume / np.pi):.1f} m)"))
    a2.add_patch(Circle((0, 0), trunk_r_mesh * sc / 100, fc=C_TRUNK, label="줄기 밑동 (반경 0.8 m)"))
    d0 = trees[0]["reader_disc"]
    a2.add_patch(Circle(((d0["center_cm"][0] - trees[0]["x"]) / 100, (d0["center_cm"][1] - trees[0]["y"]) / 100), d0["r_cm"] / 100, fill=False,
                        ec=C_DISC, ls="--", lw=1.6, label=f"우리 레벨 읽기 원판 (반경 {d0['r_cm'] / 100:.1f} m)"))
    a2.set_xlim(-16, 16)
    a2.set_ylim(-16, 16)
    a2.set_aspect("equal")
    a2.set_xlabel("x (m)", color=INK2)
    a2.set_ylabel("y (m)", color=INK2)
    a2.grid(color="#e4e3df", lw=0.6)
    a2.legend(loc="upper left", fontsize=8, frameon=False)
    a2.set_title("위에서 — 줄기 밑 높이 기준 (땅에 묻히면 더 넓은 단면이 땅에 닿는다)", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(HERE / "beech_tree_collision.png")
    plt.close(fig)

    for name, s in summary["stages"].items():
        print(f"{name}: 원판 {s['discs_in_unreal_export']} (언리얼 내보내기), SHC 나무 무대 안 {s['shc_trees_reader_would_keep']}")
    for tr in summary["trees"]:
        print(f"{tr['label']:12s} ({tr['x']:.0f}, {tr['y']:.0f}) 묻힘 {tr['buried_cm'] / 100:+.2f} m, 땅 위 60 cm 단면 반경 {tr['body_section_eq_r_cm'] / 100:.2f} m, "
              f"숲 무대까지 {tr['dist_to_forest_stage_m']} m")


if __name__ == "__main__":
    main()

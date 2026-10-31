"""레벨 읽기 전용 조사 (10-17, 팀 PR ff8c8f4 '지역별 비·눈 날씨 및 나무 장애물 배치' 확인). 언리얼 편집기 안의 파이썬으로 돈다(보통 파이썬이 아니다).
맵을 읽고 월드 파티션 액터를 모두 불러와 적기만 한다 — 저장하지 않는다(콘텐츠·설정·.uproject 를 바꾸지 않는다). 파이썬 플러그인은 명령줄로만 켠다.

    set ECO_SCAN_MAP=/Game/SHC/Maps/LV_SHC_RegionalWeatherTest
    set ECO_SCAN_OUT=<경로>/scan_LV_SHC_RegionalWeatherTest.json
    UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script=<이 파일> -EnablePlugins=PythonScriptPlugin,GeometryScripting
        -unattended -nopause -nosplash -NullRHI -NoSound

적는 것
- 액터마다: 클래스(경로)·이름표·자리·회전·크기·그리기 상자. 정적 메시(인스턴스 포함): 메시 경로, 충돌 켬/끔, WorldStatic·Pawn 응답, 프로필,
  우리 레벨 읽기 규칙(EcoPolicyV3IntegratedSubsystem::ScanStageObstacles)의 '충돌함' = 쿼리 충돌 ∧ WorldStatic 막음.
- 지역(AEcologyRegion): RegionId, 적어 둔 환경(기온·습도·강수·날씨), 강수가 재생을 바꾸는지. 트리거 상자 크기.
- 날씨·하늘 블루프린트(BP_*)의 변수 몇 개(SunSpeed, RegionBounds …)와 컴포넌트.
- 충돌하는 정적 메시 액터마다 줄기 밑·둘레 땅 높이(선 추적, 그 메시들은 빼고).
- 충돌하는 메시마다: 단순 충돌(볼록 껍질 등)의 꼭짓점(메시 공간, GeometryScripting), 그리기 상자, 바닥 25 cm 안 그리기 꼭짓점(줄기 굵기 어림).
  우리 원판(ObstacleCollisionBox: 메시 공간 단순 충돌 상자 → 전체 변환 → 가로 반폭 평균)도 인스턴스마다 계산해 둔다.
"""

import json
import math
import os
import traceback

import unreal

MAP = os.environ.get("ECO_SCAN_MAP", "/Game/SHC/Maps/LV_SHC_RegionalWeatherTest")
OUT = os.environ.get("ECO_SCAN_OUT", "scan.json")
SKIP_CLASSES = ("LandscapeStreamingProxy", "WorldPartitionHLOD")
BP_VARS = ("SunSpeed", "DynamicSun", "SunDefaultRotaion", "SunCurrentRotation", "WeatherManager", "RegionBounds", "RainfallIntensity",
           "SkyManager", "RainSystem", "RainSound", "CameraInsideRegion", "Rain", "bUseV3Policy", "V3DeerPerRegion", "bV3UseAuthoredShelters")
LOG = []


def log(s):
    LOG.append(str(s))
    unreal.log("[EcoLevelScan] " + str(s))


def vec(v):
    try:
        return [round(float(v.x), 3), round(float(v.y), 3), round(float(v.z), 3)]
    except Exception:
        return None


def rot(r):
    try:
        return [round(float(r.pitch), 3), round(float(r.yaw), 3), round(float(r.roll), 3)]
    except Exception:
        return None


def safe(fn):
    try:
        return fn()
    except Exception:
        return None


def enum_name(v):
    s = str(v)
    return s.split(".")[-1].split(":")[0].strip("<> ") if s else s


def collide_rule(c):
    """우리 레벨 읽기와 같은 조건: CollisionEnabledHasQuery ∧ WorldStatic 응답 = 막음."""
    ce = enum_name(safe(lambda: c.get_collision_enabled()))
    resp = enum_name(safe(lambda: c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_WORLD_STATIC)))
    return ce in ("QUERY_ONLY", "QUERY_AND_PHYSICS", "QUERY_AND_PROBE") and resp == "ECR_BLOCK", ce, resp


def transform_rows(c):
    """(이름, FTransform) 목록 — 보통 메시는 하나, 인스턴스 메시는 인스턴스마다."""
    if isinstance(c, unreal.InstancedStaticMeshComponent):
        n = c.get_instance_count()
        return [(i, c.get_instance_transform(i, True)) for i in range(n)]
    return [(-1, c.get_world_transform())]


def xf_row(t):
    return {"t": vec(t.translation), "r": rot(t.rotation.rotator()), "s": vec(t.scale3d)}


def simple_collision(mesh):
    """메시 공간 단순 충돌 꼭짓점 (GeometryScripting 이 켜졌을 때만)."""
    if not hasattr(unreal, "GeometryScript_Collision"):
        return None
    coll = unreal.GeometryScript_Collision.get_simple_collision_from_static_mesh(mesh)
    cnt = unreal.GeometryScript_Collision.get_simple_collision_shape_count(coll)
    dm = unreal.DynamicMesh()
    unreal.GeometryScript_Primitives.append_simple_collision_shapes(dm, unreal.GeometryScriptPrimitiveOptions(), unreal.Transform(), coll,
                                                                    unreal.GeometryScriptSimpleCollisionTriangulationOptions())
    r = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dm, True)
    pl = [x for x in r if isinstance(x, unreal.GeometryScriptVectorList)][0]
    pts = unreal.GeometryScript_List.convert_vector_list_to_array(pl)
    return {"shape_count": cnt, "verts_mesh_cm": [vec(p) for p in pts]}


def render_base_ring(mesh, z_max_cm=25.0):
    """바닥 z_max_cm 안의 그리기 꼭짓점 (줄기 밑동 굵기 어림)."""
    if not hasattr(unreal, "GeometryScript_AssetUtils"):
        return None
    dm = unreal.DynamicMesh()
    unreal.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(mesh, dm, unreal.GeometryScriptCopyMeshFromAssetOptions(), unreal.GeometryScriptMeshReadLOD())
    r = unreal.GeometryScript_MeshQueries.get_all_vertex_positions(dm, True)
    pl = [x for x in r if isinstance(x, unreal.GeometryScriptVectorList)][0]
    pts = unreal.GeometryScript_List.convert_vector_list_to_array(pl)
    zmin = min(p.z for p in pts)
    base = [vec(p) for p in pts if p.z <= zmin + z_max_cm]
    return {"n_verts": len(pts), "z_min": round(zmin, 3), "base_verts_mesh_cm": base}


def mesh_row(mesh):
    b = mesh.get_bounds()
    bs = safe(lambda: mesh.get_editor_property("body_setup"))
    agg = safe(lambda: bs.get_editor_property("agg_geom")) if bs else None
    counts = {}
    if agg is not None:
        for n in ("sphere_elems", "box_elems", "sphyl_elems", "convex_elems", "tapered_capsule_elems"):
            arr = safe(lambda: agg.get_editor_property(n))
            counts[n] = len(arr) if arr is not None else None
    row = {"path": mesh.get_path_name(), "render_bounds_origin": vec(b.origin), "render_bounds_extent": vec(b.box_extent),
           "collision_trace_flag": enum_name(safe(lambda: bs.get_editor_property("collision_trace_flag"))) if bs else None,
           "agg_counts": counts}
    try:
        row["simple_collision"] = simple_collision(mesh)
    except Exception as e:
        row["simple_collision"] = "ERR " + str(e)[:200]
    try:
        row["render_base"] = render_base_ring(mesh)
    except Exception as e:
        row["render_base"] = "ERR " + str(e)[:200]
    return row


def reader_disc(verts, t):
    """ObstacleCollisionBox 와 같은 계산: 메시 공간 상자(꼭짓점 상자) 여덟 꼭짓점 → 전체 변환 → 세계 상자 → (중심, 가로 반폭 평균, 높이)."""
    xs = [v[0] for v in verts]; ys = [v[1] for v in verts]; zs = [v[2] for v in verts]
    lo = (min(xs), min(ys), min(zs)); hi = (max(xs), max(ys), max(zs))
    W = []
    for cx in (lo[0], hi[0]):
        for cy in (lo[1], hi[1]):
            for cz in (lo[2], hi[2]):
                p = t.transform_location(unreal.Vector(cx, cy, cz))
                W.append((p.x, p.y, p.z))
    mn = [min(w[k] for w in W) for k in range(3)]
    mx = [max(w[k] for w in W) for k in range(3)]
    ext = [(mx[k] - mn[k]) / 2 for k in range(3)]
    return {"center_cm": [round((mn[k] + mx[k]) / 2, 2) for k in range(3)], "r_cm": round(0.5 * (ext[0] + ext[1]), 2), "height_cm": round(2 * ext[2], 2)}


def ground_z(ctx, x, y, ignore):
    h = unreal.SystemLibrary.line_trace_single_for_objects(ctx, unreal.Vector(x, y, 30000), unreal.Vector(x, y, -30000),
                                                           [unreal.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, ignore, unreal.DrawDebugTrace.NONE, True)
    if h is None:
        return None
    t = h.to_tuple()
    if not t[0]:
        return None
    v = [e for e in t if isinstance(e, unreal.Vector)]
    return round(v[1].z, 2) if len(v) > 1 else None


def main():
    world = unreal.EditorLoadingAndSavingUtils.load_map(MAP)
    log(f"map {MAP} loaded={world is not None}")
    descs = unreal.WorldPartitionBlueprintLibrary.get_actor_descs()
    unreal.WorldPartitionBlueprintLibrary.load_actors([d.guid for d in descs])
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
    log(f"actor descs {len(descs)}, loaded actors {len(actors)}")
    rows, meshes, collidable = [], {}, []
    class_counts = {}
    for a in actors:
        cls = a.get_class()
        cn = cls.get_name()
        class_counts[cn] = class_counts.get(cn, 0) + 1
        if cn in SKIP_CLASSES:
            continue
        o, e = a.get_actor_bounds(False)
        row = {"class": cn, "class_path": cls.get_path_name(), "label": a.get_actor_label(), "loc": vec(a.get_actor_location()),
               "rot": rot(a.get_actor_rotation()), "scale": vec(a.get_actor_scale3d()), "bounds_origin": vec(o), "bounds_extent": vec(e)}
        if isinstance(a, unreal.EcologyRegion):
            env = a.get_editor_property("environment_state")
            row["region_id"] = str(a.get_editor_property("region_id"))
            row["environment"] = {"temperature": env.temperature, "humidity": env.humidity, "rainfall": env.rainfall,
                                  "day_phase": enum_name(env.day_phase), "weather_state": enum_name(env.weather_state)}
            row["rainfall_affects_regeneration"] = safe(lambda: a.get_editor_property("rainfall_affects_regeneration"))
        if cn.startswith("BP_") or "Spawner" in cn:
            bp = {}
            for n in BP_VARS:
                v = safe(lambda: a.get_editor_property(n))
                if v is None:
                    continue
                bp[n] = ("Actor:" + v.get_actor_label()) if isinstance(v, unreal.Actor) else str(v)[:200]
            row["vars"] = bp
            row["components"] = [c.get_class().get_name() + ":" + c.get_name() for c in a.get_components_by_class(unreal.ActorComponent)]
        sm = []
        for c in a.get_components_by_class(unreal.StaticMeshComponent):
            m = c.static_mesh
            if m is None:
                continue
            ok, ce, resp = collide_rule(c)
            p = m.get_path_name()
            if p not in meshes and ok:
                meshes[p] = mesh_row(m)
            elif p not in meshes:
                meshes[p] = {"path": p, "render_bounds_extent": vec(m.get_bounds().box_extent), "note": "충돌 없음 — 꼭짓점 안 읽음"}
            xs = transform_rows(c)
            sm.append({"component": c.get_name(), "ism": isinstance(c, unreal.InstancedStaticMeshComponent), "mesh": p, "collides": ok,
                       "collision_enabled": ce, "resp_worldstatic": resp,
                       "resp_pawn": enum_name(safe(lambda: c.get_collision_response_to_channel(unreal.CollisionChannel.ECC_PAWN))),
                       "profile": str(safe(lambda: c.get_collision_profile_name())), "count": len(xs),
                       "instances": [dict(xf_row(t), i=i) for i, t in xs[:5000]]})
            if ok:
                collidable.append((a, c, p, xs))
        if sm:
            row["static_meshes"] = sm
        rows.append(row)
    # 우리 원판 계산과 땅 높이 (충돌하는 메시만)
    ignore = [a for a, _, _, _ in collidable]
    ctx = actors[0]
    for a, c, p, xs in collidable:
        sc = meshes[p].get("simple_collision")
        verts = sc.get("verts_mesh_cm") if isinstance(sc, dict) else None
        for row in rows:
            if row["label"] != a.get_actor_label():
                continue
            for s in row.get("static_meshes", []):
                if s["component"] != c.get_name():
                    continue
                for (i, t), inst in zip(xs, s["instances"]):
                    if verts:
                        inst["reader_disc"] = reader_disc(verts, t)
                    tx = t.translation
                    inst["ground_z"] = {"0": ground_z(ctx, tx.x, tx.y, ignore)}
                    for k, (dx, dy) in enumerate(((500, 0), (-500, 0), (0, 500), (0, -500))):
                        inst["ground_z"][f"{dx},{dy}"] = ground_z(ctx, tx.x + dx, tx.y + dy, ignore)
    out = {"map": MAP, "log": LOG, "actor_descs": len(descs), "loaded_actors": len(actors), "class_counts": class_counts,
           "actors": rows, "meshes": meshes}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"wrote {OUT} ({len(rows)} actors, {len(collidable)} collidable mesh components)")


try:
    main()
except Exception:
    unreal.log_error("[EcoLevelScan] FAILED " + traceback.format_exc())
    with open(OUT + ".err.txt", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())

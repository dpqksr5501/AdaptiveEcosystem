"""Measure and optionally save the four social ranges on the owned island."""

import json
import math
from pathlib import Path
import runpy
import traceback

import unreal as u


island = runpy.run_path(str(Path(__file__).with_name("author_jyu_island_fauna.py")))
get, put = (island[key] for key in ("get", "put"))
editor, levels, wp = (island[key] for key in ("editor", "levels", "wp"))
TARGET = island["TARGET"]
RANGES = {"Leopard": 430., "GoldenEagle": 620., "Mink": 320., "AriakeCatfish": 350.}
REPORT = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit/IslandSocialLayout.json"
apply = "-EcoApplyIslandSocialLayout" in u.SystemLibrary.get_command_line().split()


def vec(point):
    return list(point.to_tuple())


def trace_clear(world, start, finish):
    hits = u.SystemLibrary.line_trace_multi_for_objects(world, start, finish,
        [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True) or []
    for hit in hits:
        actor = hit.to_tuple()[9]
        if not actor or not actor.get_class().get_name().startswith("WaterBody"):
            return False
    return True


def local_samples(start, finish):
    return [start + (finish - start) * (i / 8.) for i in range(9)]


def ground_contact(world, a, b, kind):
    eye = u.Vector(0, 0, 20 if kind == "Mink" else 80)
    project = u.EcoCreatureAnimationBuilder.project_placement_point
    for point in local_samples(a, b):
        p = project(world, point)
        if p is None or abs(p.z - point.z) > 45. or not island["dry_ground"](world, p, 0., 20.):
            return False
    return trace_clear(world, a + eye, b + eye)


def water_contact(world, region, start, finish):
    depths = []
    for point in local_samples(start, finish):
        sample = u.EcoCreatureInspectionLibrary.inspect_fauna_water(world, region, point, 4.)
        if not sample:
            return None
        bottom, surface = sample[0].x, sample[0].y
        if not bottom + 10. < point.z < surface - 20.:
            return None
        depths.append([round(point.z - bottom, 1), round(surface - point.z, 1)])
    return depths if trace_clear(world, start, finish) else None


def trial_offsets(radius, angles):
    return [u.Vector(radius * math.cos(angle * math.pi / angles), radius * math.sin(angle * math.pi / angles), 0)
            for angle in range(2 * angles)]


def first_ground_peer(world, anchor, kind, occupied):
    project = u.EcoCreatureAnimationBuilder.project_placement_point
    for fraction in (.64, .52, .76, .45):
        for nudge in trial_offsets(RANGES[kind] * fraction, 8):
            candidate = project(world, anchor + nudge)
            if candidate is None or (candidate - anchor).length() >= RANGES[kind] * .85:
                continue
            if any((candidate - p).length() < 140. for p in occupied):
                continue
            if ground_contact(world, anchor, candidate, kind):
                return candidate
    return None


def first_water_peer(world, region, anchor, occupied):
    for radius in (170., 225., 125.):
        for nudge in trial_offsets(radius, 8):
            for z in (0., 12., -12.):
                candidate = anchor + nudge + u.Vector(0, 0, z)
                if any((candidate - p).length() < 60. for p in occupied):
                    continue
                depths = water_contact(world, region, anchor, candidate)
                if depths:
                    return candidate, depths
    return None, None


def author():
    world = editor.get_editor_world()
    if world.get_path_name().split(".")[0] != TARGET:
        raise RuntimeError(f"Open the owned island {TARGET}")
    descs = wp.get_actor_descs()
    prefix = TARGET.replace("/Game/", "/Game/__ExternalActors__/", 1) + "/"
    if not descs or any(not str(get(row, "actor_package")).startswith(prefix) for row in descs):
        raise RuntimeError("Actor packages are outside the owned island")
    wp.load_actors([get(row, "guid") for row in descs])
    runtime = island["common"]["runtime"]()
    groups = [row.copy() for row in get(runtime, "groups")]
    placements = {str(get(group, "region_id")): [row.copy() for row in get(group, "fauna")] for group in groups}
    founders = {region: {str(get(row, "species_id")): list(get(row, "spawn_points")) for row in rows}
                for region, rows in placements.items()}
    report = dict(map=TARGET, applied=False, runtime_actor=runtime.get_path_name(),
                  founders={region: {kind: list(map(vec, points)) for kind, points in rows.items()}
                            for region, rows in founders.items()},
                  perches=[{"species": str(get(site, "species_id")), "region": str(get(site, "region_id")),
                            "point": vec(get(site, "location"))} for site in get(runtime, "fauna_perches")],
                  shore=[{"id": str(get(patch, "id")), "landing": vec(get(patch, "shore_point")),
                          "entry": vec(get(patch, "water_entry_point")), "dry_bank": vec(get(patch, "dry_bank_point"))}
                         for patch in get(runtime, "fauna_habitat_patches")
                         if get(patch, "has_shore_entry") and "Mink" in map(str, get(patch, "consumers"))],
                  proposals={}, errors=[])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    for region, rows in founders.items():
        for kind, points in rows.items():
            if kind not in RANGES:
                continue
            occupied = [p for other, values in rows.items() if other != kind for p in values]
            # Preserve existing dry-bank access on both ends of the LowerRiver for mink.
            # Keep one founder on either side of the catfish reach, and both original animal counts for fish and eagle.
            anchor_order = list(range(len(points)))
            result = None
            for i in anchor_order:
                anchor = points[i]
                existing = [((p - anchor).length(), j) for j, p in enumerate(points) if j != i]
                ready = next((j for distance, j in sorted(existing) if 60. < distance <= RANGES[kind] * .85
                              and (water_contact(world, region, anchor, points[j]) if kind == "AriakeCatfish"
                                   else ground_contact(world, anchor, points[j], kind))), None)
                if ready is not None:
                    result = dict(points=points, anchor=anchor, candidate=points[ready], action="already_valid")
                    break
                if kind == "AriakeCatfish":
                    candidate, evidence = first_water_peer(world, region, anchor, occupied)
                else:
                    candidate = first_ground_peer(world, anchor, kind, [*occupied, *points])
                    evidence = None
                if candidate is None:
                    continue
                updated = list(points)
                if kind in ("Leopard", "Mink"):
                    updated.append(candidate)
                    action = "added_founder"
                else:
                    replacement = min(existing)[1]
                    updated[replacement] = candidate
                    action = "relocated_founder"
                result = dict(points=updated, anchor=anchor, candidate=candidate, action=action,
                              water_clearance_cm=evidence)
                break
            if result is None:
                report["errors"].append(f"No compatible {kind} contact in {region}")
                continue
            report["proposals"][kind] = {"region": region, "action": result["action"],
                "anchor": vec(result["anchor"]), "peer": vec(result["candidate"]),
                "distance_cm": round((result["candidate"] - result["anchor"]).length(), 1),
                "water_clearance_cm": result.get("water_clearance_cm"), "founders": len(result["points"])}
            facing = next(row for row in placements[region] if str(get(row, "species_id")) == kind)
            put(facing, spawn_points=result["points"])
    if apply and not report["errors"] and set(report["proposals"]) == set(RANGES):
        changed = any(row["action"] != "already_valid" for row in report["proposals"].values())
        if changed:
            runtime.modify()
            for group in groups:
                put(group, fauna=placements[str(get(group, "region_id"))])
            put(runtime, groups=groups)
            if not levels.save_current_level():
                report["errors"].append("Cannot save the owned island")
        report["applied"] = not report["errors"]
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report["errors"]:
        raise RuntimeError(str(report["errors"]))
    u.log(f"ECO_ISLAND_SOCIAL_LAYOUT applied={report['applied']} proposals={report['proposals']}")


if __name__ == "__main__":
    try:
        author()
    except Exception:
        u.log_error(traceback.format_exc())
    finally:
        u.SystemLibrary.quit_editor()

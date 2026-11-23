"""Read poses and capture close views of actual fauna in the saved island PIE."""

import json
from pathlib import Path
import re
import runpy
import time
import traceback

import unreal as u

camera_tools = runpy.run_path(str(Path(__file__).with_name("observe_island_social.py")))
point, view_obstruction = (camera_tools[name] for name in ("point", "view_obstruction"))


MAP = "/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed"
SPECIES = ("GoldenEagle", "Mink", "AriakeCatfish", "Leopard", "Crow", "CommonCarp", "UnidentifiedFish",
           "Rat", "Jackrabbit", "Fox", "Bighorn", "Horse", "Pig", "Buffalo", "Wolf", "Herbivore")
FISH = {"AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
command = u.SystemLibrary.get_command_line()
focus = re.search(r"-EcoAnimationSpecies=([a-zA-Z+,]+)", command)
if focus:
    SPECIES = tuple(focus[1].replace(",", "+").split("+"))
require_movement = "-EcoAnimationRequireMovement" in command
size_rank = re.search(r"-EcoAnimationSizeRank=(Small|Large)\b", command)
natural_growth = "-EcoAnimationNaturalGrowth" in command.split()
if natural_growth and (len(SPECIES) != 1 or size_rank):
    raise RuntimeError("Natural growth capture requires one species and no adult size ranking")
inspect_traits = "-EcoAnimationInspectTraits" in command.split()
editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
builder = u.EcoCreatureAnimationBuilder
folder = "IslandAnimationMoving" if require_movement else "IslandAnimationFocused" if focus else "IslandAnimation"
output_name = re.search(r"-EcoAnimationReport=([a-zA-Z0-9_]+)\b", command)
if output_name:
    folder = output_name[1]
out = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit" / folder
out.mkdir(parents=True, exist_ok=True)
report = {"map": MAP, "samples": {}, "error": None}
desired = {}
camera = None
target = None
target_started = 0.
next_sample = 0.
next_reposition = 0.
start = time.monotonic()
growth_phase = "juvenile"


def candidates(world):
    rows = {}
    for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor):
        if actor.get_editor_property("hidden") or not actor.get_editor_property("bound"):
            continue
        visual = actor.get_editor_property("visual_state")
        kind = str(visual.get_editor_property("species_id"))
        if kind not in SPECIES or not visual.get_editor_property("alive"):
            continue
        if (size_rank or natural_growth) and int(visual.stable_agent_id) != int(desired[kind]["id"]):
            continue
        if require_movement and visual.get_editor_property("velocity").length() <= 10.:
            continue
        mesh = next((c for c in (actor.get_editor_property("creature_mesh"), actor.get_editor_property("immature_mesh"))
                     if c.is_visible() and c.get_skeletal_mesh_asset()), None)
        if mesh is not None:
            rows.setdefault(kind, []).append((actor, mesh, visual))
    return rows


def finish(error=None):
    if inspect_traits and error is None:
        images = [file for row in report["samples"].values() for file in row["captures"]]
        if not images or not all(Path(file).is_file() for file in images):
            error = "Inspector screenshot did not reach the requested path"
    if natural_growth and error is None:
        phases = report["growth_captures"]
        if (set(phases) != {"juvenile", "grown"} or any(len(row["captures"]) != 3 for row in phases.values())
                or not all(Path(file).is_file() for row in phases.values() for file in row["captures"])):
            error = "Natural growth capture did not complete both stages"
    report["error"] = error
    report["missing"] = [kind for kind in SPECIES if not report["samples"].get(kind, {}).get("frames")]
    (out / "IslandAnimation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    u.unregister_slate_post_tick_callback(handle)
    levels.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def tick(_):
    global camera, target, target_started, next_sample, next_reposition, growth_phase
    try:
        if time.monotonic() - start > 205.:
            finish("Time limit")
            return
        world = editor.get_game_world()
        if not world:
            return
        now = u.GameplayStatics.get_time_seconds(world)
        if now < next_sample or now < .6:
            return
        next_sample = now + .075
        if size_rank and not desired:
            runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
            raw = runtime.capture_population_traits() if runtime else None
            if not raw:
                return
            living = json.loads(raw)["agents"]
            select = min if size_rank[1] == "Small" else max
            for kind in SPECIES:
                adults = [row for row in living if row["species"] == kind and row["maturity"] >= 1.]
                if not adults:
                    raise RuntimeError(f"No adult {kind} in the saved island")
                desired[kind] = select(adults, key=lambda row: row["visual_body_scale"])
            report["size_rank"] = size_rank[1]
            report["selected_authority_rows"] = desired
        if natural_growth:
            runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
            raw = runtime.capture_population_traits() if runtime else None
            living = [row for row in json.loads(raw)["agents"] if row["species"] == SPECIES[0]] if raw else []
            if not desired:
                newborns = [row for row in living if row["origin"] == 1 and row["generation"] > 0
                            and row["parent_a"] != "0" and row["parent_b"] != "0"]
                if not newborns:
                    return
                desired[SPECIES[0]] = min(newborns, key=lambda row: (row["born"], int(row["id"])))
                report["selected_authority_rows"] = desired
                report["growth_captures"] = {}
            lineage = desired[SPECIES[0]]
            current = next((row for row in living if row["id"] == lineage["id"]), None)
            if current is None:
                raise RuntimeError(f"Natural offspring {lineage['id']} died before the {growth_phase} capture")
            if growth_phase == "grown" and current["maturity"] < .7:
                next_sample = now + .5
                return
            if growth_phase == "grown" and not report["samples"]:
                u.GameplayStatics.set_global_time_dilation(world, 1.)
            for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor):
                if actor.get_editor_property("bound"):
                    state = actor.get_editor_property("visual_state")
                    hidden = int(state.stable_agent_id) != int(lineage["id"])
                    if actor.get_editor_property("hidden") != hidden:
                        actor.set_actor_hidden_in_game(hidden)
        rows = candidates(world)
        if "initial_visible_counts" not in report and rows:
            report["initial_visible_counts"] = {kind: len(items) for kind, items in rows.items()}
        if target is None or target not in rows or now - target_started > 1.9:
            target = next((kind for kind in SPECIES if kind in rows and kind not in report["samples"]), None)
            target_started = now
        if target is None:
            if not natural_growth and (now > 65. or len(report["samples"]) == len(SPECIES)):
                finish()
            elif now > next_reposition:
                next_reposition = now + 3.
                inspect = u.EcoCreatureInspectionLibrary
                for agent_id in inspect.get_authority_agent_ids(world):
                    result = inspect.capture_agent(world, agent_id)
                    raw = next((item for item in result if isinstance(item, str)), "") if isinstance(result, tuple) else result
                    data = json.loads(raw) if raw else {}
                    if data.get("species") not in SPECIES or data.get("species") in report["samples"]:
                        continue
                    if (size_rank or natural_growth) and int(agent_id) != int(desired[data["species"]]["id"]):
                        continue
                    player = u.GameplayStatics.get_player_controller(world, 0)
                    if not player:
                        break
                    pawn = player.get_controlled_pawn()
                    position = point(data["position"])
                    eye = position + u.Vector(650., 0., 350.)
                    if pawn:
                        pawn.set_actor_hidden_in_game(True)
                        pawn.character_movement.disable_movement()
                        pawn.set_actor_location(eye, False, True)
                    if camera:
                        camera.set_actor_location(eye, False, True)
                        camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye, position), False)
                    break
            return
        player = u.GameplayStatics.get_player_controller(world, 0)
        if not player:
            return
        audit = report["samples"].setdefault(target, {"frames": [], "captures": []})
        if "id" in audit:
            found = next((row for row in rows[target] if row[2].get_editor_property("stable_agent_id") == audit["id"]), None)
            if not found:
                target = None
                return
        else:
            found = max(rows[target], key=lambda row: row[2].get_editor_property("velocity").length())
        actor, mesh, visual = found
        audit["representation"] = actor.get_class().get_path_name()
        audit["mesh"] = mesh.get_skeletal_mesh_asset().get_path_name()
        if "id" not in audit:
            pawn = player.get_controlled_pawn()
            if pawn:
                pawn.set_actor_hidden_in_game(True)
                pawn.character_movement.disable_movement()
                pawn.set_actor_location(actor.get_actor_location() + u.Vector(650., 0., 900.), False, True)
        audit["id"] = visual.get_editor_property("stable_agent_id")
        center, extent, _ = u.SystemLibrary.get_component_bounds(mesh)
        radius = max(extent.x, extent.y, extent.z, 8.)
        if size_rank or natural_growth:
            # Compensate camera distance, not the creature, to keep an adult of scale 1 at a common reference framing.
            radius /= visual.body_scale
        across = actor.get_actor_right_vector() * (radius * 2.75)
        ahead = actor.get_actor_forward_vector() * (radius * .85)
        upper = u.Vector(0., 0., radius * (.42 if target in FISH else .8))
        views = (center + across + ahead + upper, center - across + ahead + upper,
                 center + across * .55 + u.Vector(0., 0., radius * 3.))
        allow_water = target in FISH or target == "Mink"
        aim_points = (center, center + u.Vector(0., 0., extent.z * .8))
        clear_view = next(((view, aim) for view in views for aim in aim_points
                           if not view_obstruction(world, view, aim, allow_water)), None)
        eye, aim = clear_view or (views[-1], center)
        if camera is None:
            camera = builder.spawn_visual_audit_actor(world, u.CameraActor, u.Transform(location=eye))
            if camera is None:
                raise RuntimeError("Island PIE camera could not be created")
            player.set_view_target_with_blend(camera, 0.)
            u.SystemLibrary.execute_console_command(world, "eco.Inspector.Visible 1" if inspect_traits else "showhud")
        if inspect_traits:
            hud = player.get_hud()
            if not isinstance(hud, u.EcoCreatureInspectorHUD) or not hud.select_agent_for_inspection(audit["id"]):
                raise RuntimeError(f"The island inspector could not select {audit['id']}")
        camera.set_actor_location(eye, False, True)
        camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye, aim), False)
        anim = mesh.get_anim_instance()
        profile = actor.get_editor_property("animation_profile")
        feet = list(profile.get_editor_property("foot_bones")) if profile else []
        foot_gaps = []
        for bone in feet:
            contact = mesh.get_socket_location(bone)
            ground = builder.project_placement_point(world, contact)
            foot_gaps.append(round(contact.z - ground.z, 2) if ground else None)
        support = builder.project_placement_point(world, center + u.Vector(0., 0., 150.))
        reference_bone = profile.get_editor_property("body_bone") if profile else None
        body = mesh.get_socket_location(reference_bone) if reference_bone else center
        sample = {"time": round(now, 3), "activity": str(visual.get_editor_property("activity")),
                  "speed": round(visual.get_editor_property("velocity").length(), 2), "foot_gaps_cm": foot_gaps,
                  "rendered": mesh.was_recently_rendered(.2), "clear_view": clear_view is not None,
                  "anim_class": anim.get_class().get_name() if anim else None,
                  "body_bone_clearance_cm": round(body.z - support.z, 2) if support else None,
                  "mesh_bounds_top_clearance_cm": round(center.z + extent.z - support.z, 2) if support else None,
                  "authority_z_cm": round(visual.get_editor_property("position").z, 2),
                  "body_scale": round(visual.get_editor_property("body_scale"), 3)}
        if size_rank:
            sample.update(actor_scale=actor.get_actor_scale3d().to_tuple(), mesh_world_scale=mesh.get_world_scale().to_tuple(),
                          bounds_half_cm=extent.to_tuple(), camera_distance_cm=(eye - aim).length())
        if isinstance(anim, u.EcoCreatureAnimInstance):
            sample.update(pose=anim.get_editor_property("animation_index"), ik=anim.get_editor_property("ground_ik_alpha"))
        audit["frames"].append(sample)
        capture_index = len(audit["captures"])
        if capture_index < 3 and now - target_started >= (.33, .84, 1.39)[capture_index] and sample["rendered"] and clear_view:
            file_stem = f"{target}_{audit['id']}_{growth_phase}" if natural_growth else target
            image = (out / f"{file_stem}_{capture_index}.png").as_posix()
            cmd = f'Shot showui -nosuffix filename="{image}"' if inspect_traits else f'HighResShot 1280x720 filename="{image}"'
            u.SystemLibrary.execute_console_command(world, cmd)
            audit["captures"].append(image)
        if natural_growth and len(audit["captures"]) == 3 and all(Path(file).is_file() for file in audit["captures"]):
            report["growth_captures"][growth_phase] = dict(audit, authority=current)
            if growth_phase == "grown":
                finish()
                return
            growth_phase = "grown"
            report["samples"].clear()
            target = None
            u.GameplayStatics.set_global_time_dilation(world, 4.)
    except Exception:
        finish(traceback.format_exc())


if not levels.load_level(MAP):
    raise RuntimeError(f"Could not open {MAP}")
levels.editor_request_begin_play()
handle = u.register_slate_post_tick_callback(tick)

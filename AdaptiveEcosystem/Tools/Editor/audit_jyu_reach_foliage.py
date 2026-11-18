"""Measure the saved riparian foliage layout and compare rendering at fixed camera positions."""

import json
from pathlib import Path
import time

import unreal as u


EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
LEVELS = u.get_editor_subsystem(u.LevelEditorSubsystem)
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)
MESHES = u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
OUT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / "ExpandedFaunaImport"
MAP = "/Game/JYU/Maps/LV_JYU_RiparianReach"
TARGET = u.Vector(4110., -4800., 100.)
PHASES = (
    ("Near", 1900., 70., True, False),
    ("Far", 10400., 15., True, False),
    ("NearOnA", 1900., 70., True, True),
    ("NearOffA", 1900., 70., False, True),
    ("NearOffB", 1900., 70., False, True),
    ("NearOnB", 1900., 70., True, True),
)


def inspect_component(component):
    mesh = component.get_editor_property("static_mesh")
    lods = mesh.get_num_lods()
    return {"component": component.get_class().get_name(), "mesh": mesh.get_path_name(),
            "instances": component.get_instance_count(),
            "cull_cm": [component.get_editor_property("instance_start_cull_distance"),
                        component.get_editor_property("instance_end_cull_distance")],
            "lod_triangles": [mesh.get_num_triangles(lod) for lod in range(lods)],
            "nanite_asset": MESHES.get_nanite_settings(mesh).get_editor_property("enabled"),
            "collision": str(component.get_collision_enabled()), "shadows": component.get_editor_property("cast_shadow")}


def main():
    if EDITOR.get_editor_world().get_name() != MAP.rsplit("/", 1)[-1] and not LEVELS.load_level(MAP):
        raise RuntimeError(f"Could not load {MAP}")
    editor_world = EDITOR.get_editor_world()
    settings = next(a for a in u.ObjectIterator(u.WorldSettings) if a.get_outermost() == editor_world.get_outermost())
    actors = ACTORS.get_all_level_actors()
    result = {"world_partition": bool(settings.get_editor_property("world_partition")),
              "hlod_actors": [a.get_actor_label() for a in actors if "HLOD" in a.get_class().get_name()
                              or a.get_class().get_name() == "LODActor"],
              "scenery_static_mesh_actors": sum(isinstance(a, u.StaticMeshActor)
                                                and a.get_actor_label().startswith("JYU Reach ") for a in actors)}
    LEVELS.editor_request_begin_play()
    started = time.monotonic()
    phase_start = 0
    phase_index = -1
    frame = 0
    camera = None
    components = []

    def finish(error=None):
        u.unregister_slate_post_tick_callback(handle)
        result["error"] = error
        (OUT / "ReachFoliagePerformance.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if error:
            u.log_error(f"ECO_REACH_FOLIAGE_FAILED {error}")
        else:
            u.log("ECO_REACH_FOLIAGE_VERIFIED")
        LEVELS.editor_request_end_play()
        u.SystemLibrary.quit_editor()

    def tick(_):
        nonlocal camera, phase_start, phase_index, frame
        world = EDITOR.get_game_world()
        try:
            if time.monotonic() - started > 115.:
                raise RuntimeError("Timed out waiting for foliage performance captures")
            if not world or u.GameplayStatics.get_time_seconds(world) < 2.:
                return
            frame += 1
            if camera is None:
                camera = u.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, u.CameraActor, u.Transform())
                u.GameplayStatics.get_player_controller(world, 0).set_view_target_with_blend(camera, 0.)
                foliage = u.GameplayStatics.get_all_actors_of_class(world, u.InstancedFoliageActor)
                forage = u.GameplayStatics.get_all_actors_of_class(world, u.EcoForagePatchVisual)
                result.update(canopy=[], forage=[], decor=[])
                for actor in foliage + forage:
                    for component in actor.get_components_by_class(u.InstancedStaticMeshComponent):
                        mesh = component.get_editor_property("static_mesh")
                        if not component.get_instance_count() or not mesh:
                            continue
                        category = ("forage" if isinstance(actor, u.EcoForagePatchVisual) else
                                    "canopy" if mesh.get_name() in ("SM_AutumnTree02", "SM_Birch") else "decor")
                        result[category].append(inspect_component(component))
                        if category != "decor":
                            components.append(component)
                if sum(c["instances"] for c in result["canopy"]) != 18 or len(forage) != 17:
                    raise RuntimeError("Unexpected saved canopy or forage count")
                if len(result["decor"]) != 11 or sum(c["instances"] for c in result["decor"]) != 110:
                    raise RuntimeError("Unexpected saved static scenery batches")
                for command in ("showhud", "eco.Creature.Labels 0", "eco.Sky.Link 0", "eco.IntegratedV3.WeatherVisuals 0"):
                    u.SystemLibrary.execute_console_command(world, command)
            if phase_index >= 0:
                label, _, _, _, profile = PHASES[phase_index]
                elapsed = frame - phase_start
                if elapsed == 30:
                    command = (f"csvprofile STARTFILE=ReachFoliage{label}.csv" if profile else
                               f'HighResShot 1280x720 filename="{(OUT / ("ReachFoliage" + label + ".png")).as_posix()}"')
                    u.SystemLibrary.execute_console_command(world, command)
                    if profile:
                        u.SystemLibrary.execute_console_command(world, "csvprofile START")
                if profile and elapsed == 130:
                    u.SystemLibrary.execute_console_command(world, "csvprofile STOP")
                if elapsed < (170 if profile else 60):
                    return
            phase_index += 1
            if phase_index == len(PHASES):
                finish()
                return
            _, distance, fov, visible, _ = PHASES[phase_index]
            phase_start = frame
            position = TARGET + u.Vector(-.62 * distance, -.49 * distance, .60 * distance)
            camera.set_actor_location(position, False, False)
            camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(position, TARGET), False)
            camera.get_component_by_class(u.CameraComponent).set_field_of_view(fov)
            controller = u.GameplayStatics.get_player_controller(world, 0)
            controller.set_view_target_with_blend(camera, 0.)
            for component in components:
                component.set_visibility(visible, False)
        except Exception as error:
            finish(str(error))

    handle = u.register_slate_post_tick_callback(tick)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        u.SystemLibrary.quit_editor()
        raise

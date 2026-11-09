"""Standalone PIE fixture for the fauna rigs. Run from the owned fauna map."""

import json
import math
import re
import time
from pathlib import Path

import unreal


editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
builder = unreal.EcoCreatureAnimationBuilder
activity = unreal.EcoSpeciesActivity
output = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "FaunaAudit"
output.mkdir(parents=True, exist_ok=True)
run_name = re.search(r"-FaunaMotionName=([A-Za-z0-9_]+)", unreal.SystemLibrary.get_command_line())
prefix = run_name.group(1) if run_name else "FlexibleMotion"
species = ("Rat", "Fox", "Pig", "Leopard", "Crow", "Buffalo", "Deer", "Wolf")
cases = ("flat", "walk", "turn", "reverse", "brake", "run", "feed", "special", "fly", "land", "death", "settled")
state = {"fixtures": [], "frames": {}, "captures": set(), "start": time.monotonic(), "last": 0.}
levels.editor_request_begin_play()


def spawn(world, cls, location):
    actor = builder.spawn_visual_audit_actor(world, cls, unreal.Transform(location=location))
    if not actor:
        raise RuntimeError(f"Could not spawn {cls}")
    return actor


def setup(world):
    player = unreal.GameplayStatics.get_player_controller(world, 0)
    # Keep the entire tilted plate above the map floor so the pose follows the same
    # collision surface that the IK and the marker measurements see.
    center = unreal.Vector(0., -5500., 250.)
    plate = spawn(world, unreal.StaticMeshActor, center)
    plate.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
    plate.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    plate.static_mesh_component.set_collision_profile_name("BlockAll")
    plate.set_actor_scale3d(unreal.Vector(16., 24., .3))
    camera_position = center + unreal.Vector(1150., -1300., 570.)
    camera = spawn(world, unreal.CameraActor, camera_position)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera_position, center + unreal.Vector(0., 0., 100.)), False)
    pawn = player.get_controlled_pawn()
    pawn.set_actor_hidden_in_game(True)
    pawn.character_movement.disable_movement()
    pawn.set_actor_location(camera_position, False, False)
    player.set_view_target_with_blend(camera, 0.)
    state["camera"] = camera
    for index, kind in enumerate(species):
        cls = unreal.load_class(None, f"/Game/JYU/Fauna/{kind}/BP_{kind}.BP_{kind}_C")
        position = center + unreal.Vector(-340., 265. * (index - 3), 15.)
        actor = spawn(world, cls, position)
        state["fixtures"].append((kind, actor, actor.get_editor_property("animation_profile"), position))
    state["plate"] = plate


def measure(world, actor, profile):
    mesh = actor.get_editor_property("creature_mesh")
    anim = mesh.get_anim_instance()
    if not isinstance(anim, unreal.EcoCreatureAnimInstance):
        if actor.get_editor_property("visual_state").get_editor_property("activity") != activity.CORPSE_SETTLED:
            raise RuntimeError(f"Unexpected animation instance {anim}")
        return {"settled": True, "body_yaw": round(actor.get_actor_rotation().yaw, 2)}
    gaps = []
    sides = {"l": [], "r": []}
    for bone in profile.get_editor_property("foot_bones"):
        contact = mesh.get_socket_location(bone)
        ground = builder.project_placement_point(world, contact)
        gaps.append(round(contact.z - ground.z, 2) if ground else None)
        tokens = re.split(r"[^a-z0-9]+", str(bone).lower())
        for side in sides:
            if side in tokens:
                sides[side].append((contact - actor.get_actor_location()).dot(actor.get_actor_right_vector()))
    side_gap = (sum(sides["r"]) / len(sides["r"]) - sum(sides["l"]) / len(sides["l"])) if all(sides.values()) else None
    return {"pose": anim.get_editor_property("animation_index"),
            "speed": round(anim.get_editor_property("speed_cm_per_second"), 2),
            "body_yaw": round(actor.get_actor_rotation().yaw, 2),
            "head_yaw": round(anim.get_editor_property("turn_head_rotation").yaw, 2),
            "ik": round(anim.get_editor_property("ground_ik_alpha"), 3),
            "valid_feet": sum(bool(anim.get_editor_property(f"ground_valid{i}")) for i in range(4)),
            "marker_gap_cm": gaps,
            "left_right_centroid_gap_cm": round(side_gap, 2) if side_gap is not None else None}


def drive(world, now, case, fraction, dt):
    pitch = 0. if case == "flat" else 12.
    state["plate"].set_actor_rotation(unreal.Rotator(pitch=pitch), False)
    frame = {}
    for index, (kind, actor, profile, position) in enumerate(state["fixtures"]):
        heading = 95. * fraction if case == "turn" else (-85. if case in ("reverse", "brake") else 0.)
        speed = {"walk": 115., "turn": 115., "reverse": 115., "brake": 115. * max(0., 1. - fraction * 3.)}.get(case, 0.)
        if case == "run":
            peak = min(580., 1.15 * actor.get_editor_property("run_speed"))
            speed = peak * max(0., min(fraction * 8., 1., (.75 - fraction) * 8.))
        direction = math.radians(heading)
        velocity = unreal.Vector(speed * math.cos(direction), speed * math.sin(direction), 0.)
        position.x += velocity.x * dt
        position.y += velocity.y * dt
        probe = unreal.Vector(position.x, position.y, state["plate"].get_actor_location().z + 200.)
        ground_point = builder.project_placement_point(world, probe)
        if not ground_point:
            raise RuntimeError(f"No support surface beneath {kind}")
        ground = ground_point.z
        action = activity.WANDER if speed > 0. else activity.HOLD
        height = 0.
        if case == "feed":
            action = activity.FORAGE if kind == "Pig" else activity.EAT
        elif case == "special":
            action = {"Fox": activity.ATTACK, "Leopard": activity.ATTACK, "Buffalo": activity.REST,
                      "Deer": activity.SLEEP, "Wolf": activity.SLEEP, "Crow": activity.TAKEOFF}.get(kind, activity.REST)
            height = 160. * fraction if kind == "Crow" else 0.
        elif kind == "Crow" and case in ("fly", "land"):
            action = activity.FLY if case == "fly" else activity.LAND
            height = 160. if case == "fly" else 160. * (1. - fraction)
        if case == "settled":
            action = activity.CORPSE_SETTLED
        if kind == "Rat" and case in ("death", "settled"):
            camera = state["camera"]
            target = unreal.Vector(position.x, position.y, ground + 3.)
            camera_pos = target + unreal.Vector(30., -48., 23.)
            camera.set_actor_location(camera_pos, False, False)
            camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera_pos, target), False)
        position.z = ground + height
        visual = unreal.EcoCreatureVisualState()
        for key, value in (("stable_agent_id", 920000 + index), ("species_id", "Herbivore" if kind == "Deer" else kind),
                           ("position", position), ("velocity", velocity), ("alive", case not in ("death", "settled")),
                           ("activity", action), ("eating", action == activity.EAT)):
            visual.set_editor_property(key, value)
        if not builder.update_visual_audit_actor(actor, profile, visual, dt):
            raise RuntimeError(f"Visual snapshot rejected for {kind}")
        frame[kind] = measure(world, actor, profile)
    state["frames"].setdefault(case, []).append({"time": round(now, 4), "animals": frame})


def finish(result):
    unreal.unregister_slate_post_tick_callback(handle)
    (output / f"{prefix}Metrics.json").write_text(json.dumps({"result": result, "frames": state["frames"]}, indent=2),
                                                   encoding="utf-8")
    unreal.log("FAUNA_MOTION_" + result)
    levels.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def verify():
    frames = state["frames"]
    for kind in species:
        yaw = [frame["animals"][kind]["body_yaw"] for frame in frames["turn"][-1:] + frames["reverse"]]
        jump = max(abs((after - before + 180.) % 360. - 180.) for before, after in zip(yaw, yaw[1:]))
        if jump > 36.02:
            raise RuntimeError(f"{kind} abrupt reversal jumped {jump:.2f} degrees in one frame")
        contacts = frames["walk"][-1]["animals"][kind]["valid_feet"]
        if contacts != (2 if kind == "Crow" else 4):
            raise RuntimeError(f"{kind} unexpected slope contacts: {contacts}")
        if kind in ("Leopard", "Buffalo"):
            for case in ("walk", "turn", "reverse", "brake", "run"):
                samples = frames[case]
                # Flat-to-walk tilts the whole test plate in one frame. Verify
                # steady slope contact after the collision and pose have updated.
                if case == "walk":
                    samples = [sample for sample in samples if sample["time"] - samples[0]["time"] > .05]
                gaps = [gap for sample in samples for gap in sample["animals"][kind]["marker_gap_cm"]
                        if gap is not None]
                if not gaps or min(gaps) < -5.:
                    raise RuntimeError(f"{kind} {case} foot marker exceeded 5 cm of ground penetration")
    for case, pose in (("special", 9), ("fly", 10), ("land", 11)):
        crow = frames[case][-1]["animals"]["Crow"]
        if crow["pose"] != pose or crow["valid_feet"] or crow["ik"] > .01:
            raise RuntimeError(f"Crow invalid {case} pose or foot contact")
    if not frames["settled"][-1]["animals"]["Rat"].get("settled"):
        raise RuntimeError("Rat did not hold the completed death pose")


def tick(_):
    try:
        if time.monotonic() - state["start"] > 100.:
            raise RuntimeError("PIE visual fixture timed out")
        world = editor.get_game_world()
        if not world or unreal.GameplayStatics.get_time_seconds(world) < 1.:
            return
        if "LV_JYU_Fauna" not in world.get_name():
            raise RuntimeError("Load the owned fauna map first")
        now = unreal.GameplayStatics.get_time_seconds(world)
        if not state["fixtures"]:
            setup(world)
            state["origin"] = now
            state["last"] = now
            return
        elapsed = (now - state["origin"]) / 1.8
        index = int(elapsed)
        if index >= len(cases):
            verify()
            finish("FINISHED")
            return
        case, fraction = cases[index], elapsed - index
        dt = min(.1, now - state["last"])
        state["last"] = now
        drive(world, now, case, fraction, dt)
        if case in ("turn", "feed", "fly", "death", "settled") and fraction >= .75 and case not in state["captures"]:
            state["captures"].add(case)
            image = (output / f"{prefix}_{case}.png").as_posix()
            unreal.SystemLibrary.execute_console_command(world, f'HighResShot 1280x720 filename="{image}"')
    except Exception as error:
        unreal.log_error(str(error))
        finish("FAILED")


handle = unreal.register_slate_post_tick_callback(tick)

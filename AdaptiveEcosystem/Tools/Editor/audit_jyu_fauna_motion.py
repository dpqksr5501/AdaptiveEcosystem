"""Standalone PIE fixture for the fauna rigs. Run from the owned fauna map."""

import json
import math
import re
from statistics import median
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
expanded = "-FaunaMotionExpanded" in unreal.SystemLibrary.get_command_line()
physical_slope = "-FaunaMotionPhysicalSlope" in unreal.SystemLibrary.get_command_line()
pig_only = "-FaunaMotionPig" in unreal.SystemLibrary.get_command_line()
straight_brake = "-FaunaMotionStraightBrake" in unreal.SystemLibrary.get_command_line()
support_match = re.search(r"-FaunaRestSupport=(Flat|Uphill|CrossSlope)", unreal.SystemLibrary.get_command_line())
support_case = support_match.group(1) if support_match else None
early_settle = "-FaunaSupportEarlySettle" in unreal.SystemLibrary.get_command_line()
verify_support = "-FaunaSupportVerify" in unreal.SystemLibrary.get_command_line()
continuity = "-FaunaMotionContinuity" in unreal.SystemLibrary.get_command_line()
verify_continuity = "-FaunaContinuityVerify" in unreal.SystemLibrary.get_command_line()
species = ("Bighorn", "Jackrabbit", "Horse", "Mink", "GoldenEagle", "AriakeCatfish", "CommonCarp", "UnidentifiedFish") if expanded else (
    "Rat", "Fox", "Pig", "Leopard", "Crow", "Buffalo", "Deer", "Wolf")
asset_root = "/Game/JYU/ExpandedFauna" if expanded else "/Game/JYU/Fauna"
map_name = "LV_JYU_ExpandedFauna" if expanded else "LV_JYU_Fauna"
if pig_only:
    species, asset_root, map_name = ("Pig",), "/Game/JYU/Pig", "LV_JYU_Pig"
cases = ("flat", "walk", "turn", "reverse", "brake", "run", "feed") + (("chew",) if pig_only else ()) + ("special", "fly") + (
    ("dive",) if expanded else ()) + ("land", "death", "settled")
if support_case:
    cases = ("flat", "special", "rise", "death", "settled")
    species = tuple(kind for kind in species if kind not in ("AriakeCatfish", "CommonCarp", "UnidentifiedFish"))
elif continuity:
    cases = ("steady", "halfturn", "hold", "slowjitter", "posejitter", "resume", "pitchflip")
state = {"fixtures": [], "frames": {}, "captures": set(), "start": time.monotonic(), "last": 0.}
map_path = f"/Game/JYU/Maps/{map_name}"
if editor.get_editor_world().get_name() != map_name and not levels.load_level(map_path):
    raise RuntimeError(f"Could not open {map_path}")
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
    center = unreal.Vector(0., -3200. if pig_only else -5500., 250.)
    def support(location, size, pitch=0.):
        plate = spawn(world, unreal.StaticMeshActor, location)
        plate.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        plate.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
        plate.static_mesh_component.set_collision_profile_name("BlockAll")
        plate.set_actor_scale3d(size)
        plate.set_actor_rotation(unreal.Rotator(pitch=pitch), False)
        return plate

    if support_case:
        plate = support(center, unreal.Vector(24., 32., .3), 12. if support_case == "Uphill" else 0.)
        if support_case == "CrossSlope":
            plate.set_actor_rotation(unreal.Rotator(roll=12.), False)
    elif physical_slope:
        plate = support(center + unreal.Vector(-600., 0., 0.), unreal.Vector(12., 26., .3))
        angle = math.radians(12.)
        # Both upper surfaces meet at X=0, Z=265. Neither moves during the run.
        ramp_center = center + unreal.Vector(700. * math.cos(angle) + 15. * math.sin(angle), 0.,
                                               15. + 700. * math.sin(angle) - 15. * math.cos(angle))
        support(ramp_center, unreal.Vector(14., 26., .3), 12.)
    else:
        plate = support(center, unreal.Vector(16., 24., .3))
    camera_position = center + (unreal.Vector(550., -620., 290.) if pig_only else unreal.Vector(1150., -1300., 570.))
    camera = spawn(world, unreal.CameraActor, camera_position)
    camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera_position, center + unreal.Vector(0., 0., 100.)), False)
    pawn = player.get_controlled_pawn()
    pawn.set_actor_hidden_in_game(True)
    pawn.character_movement.disable_movement()
    pawn.set_actor_location(camera_position, False, False)
    player.set_view_target_with_blend(camera, 0.)
    state["camera"] = camera
    if pig_only:
        unreal.SystemLibrary.execute_console_command(world, "showhud")
    for index, kind in enumerate(species):
        cls = unreal.load_class(None, f"{asset_root}/{kind}/BP_{kind}.BP_{kind}_C")
        position = center + unreal.Vector(-75. if physical_slope else -340., 0. if pig_only else 265. * (index - 3), 15.)
        actor = spawn(world, cls, position)
        state["fixtures"].append((kind, actor, actor.get_editor_property("animation_profile"), position))
    state["plate"] = plate


def measure(world, actor, profile):
    mesh = actor.get_editor_property("creature_mesh")
    anim = mesh.get_anim_instance()
    settled = not isinstance(anim, unreal.EcoCreatureAnimInstance)
    if settled:
        if actor.get_editor_property("visual_state").get_editor_property("activity") != activity.CORPSE_SETTLED:
            raise RuntimeError(f"Unexpected animation instance {anim}")
        if not support_case:
            return {"settled": True, "body_yaw": round(actor.get_actor_rotation().yaw, 2)}
    gaps = []
    markers_xy = []
    sides = {"l": [], "r": []}
    for bone in profile.get_editor_property("foot_bones"):
        contact = mesh.get_socket_location(bone)
        ground = builder.project_placement_point(world, contact)
        gaps.append(round(contact.z - ground.z, 2) if ground else None)
        markers_xy.append([round(contact.x, 3), round(contact.y, 3)])
        tokens = re.split(r"[^a-z0-9]+", str(bone).lower())
        for side in sides:
            if side in tokens:
                sides[side].append((contact - actor.get_actor_location()).dot(actor.get_actor_right_vector()))
    side_gap = (sum(sides["r"]) / len(sides["r"]) - sum(sides["l"]) / len(sides["l"])) if all(sides.values()) else None
    rotation = actor.get_actor_rotation()
    if support_case:
        body = mesh.get_socket_location(profile.get_editor_property("body_bone"))
        body_ground = builder.project_placement_point(world, body)
        relative = mesh.get_editor_property("relative_location")
        mesh_rotation = mesh.get_world_rotation()
        return {"pose": None if settled else anim.get_editor_property("animation_index"), "settled": settled,
                "marker_gap_cm": gaps, "body_gap_cm": round(body.z - body_ground.z, 2) if body_ground else None,
                "mesh_z": round(relative.z, 3), "mesh_pitch": round(mesh_rotation.pitch, 3), "mesh_roll": round(mesh_rotation.roll, 3)}
    return {"pose": anim.get_editor_property("animation_index"),
            "speed": round(anim.get_editor_property("speed_cm_per_second"), 2),
            "body_yaw": round(rotation.yaw, 2),
            "body_pitch": round(rotation.pitch, 2),
            "body_roll": round(rotation.roll, 2),
            "head_yaw": round(anim.get_editor_property("turn_head_rotation").yaw, 2),
            "turn_weight": round(actor.get_editor_property("visual_turn_amount"), 4),
            "ik": round(anim.get_editor_property("ground_ik_alpha"), 3),
            "valid_feet": sum(bool(anim.get_editor_property(f"ground_valid{i}")) for i in range(4)),
            "marker_gap_cm": gaps,
            "marker_xy_cm": markers_xy,
            "nominal_contact_cm": [height + profile.get_editor_property("foot_clearance_cm")
                                    for height in profile.get_editor_property("contact_heights")],
            "left_right_centroid_gap_cm": round(side_gap, 2) if side_gap is not None else None}


def drive(world, now, case, fraction, dt):
    pitch = 0. if case == "flat" else 12.
    if not physical_slope and not support_case and not continuity:
        state["plate"].set_actor_rotation(unreal.Rotator(pitch=pitch), False)
    frame = {}
    for index, (kind, actor, profile, position) in enumerate(state["fixtures"]):
        heading = 95. * fraction if case == "turn" else (-85. if case in ("reverse", "brake") else 0.)
        if case == "brake" and not straight_brake:
            heading += 52. * min(1., fraction * 3.)
        speed = {"walk": 115., "turn": 115., "reverse": 115., "brake": 115. * max(0., 1. - fraction * 3.)}.get(case, 0.)
        if case == "run":
            peak = min(580., 1.15 * actor.get_editor_property("run_speed"))
            speed = peak * max(0., min(fraction * 8., 1., (.75 - fraction) * 8.))
        direction = math.radians(heading)
        velocity = unreal.Vector(speed * math.cos(direction), speed * math.sin(direction), 0.)
        position.x += velocity.x * dt
        position.y += velocity.y * dt
        probe = unreal.Vector(position.x, position.y, state["plate"].get_actor_location().z + 500.)
        ground_point = builder.project_placement_point(world, probe)
        if not ground_point:
            raise RuntimeError(f"No support surface beneath {kind}")
        ground = ground_point.z
        action = activity.WANDER if speed > 0. else activity.HOLD
        height = 0.
        if case == "feed":
            action = activity.FORAGE if kind == "Pig" else activity.EAT
        elif case == "chew":
            action = activity.EAT
        elif kind == "GoldenEagle" and case in ("special", "fly", "dive", "land"):
            action = {"special": activity.TAKEOFF, "fly": activity.FLY, "dive": activity.ATTACK, "land": activity.LAND}[case]
            height = 160. * (fraction if case == "special" else (1. - fraction if case in ("dive", "land") else 1.))
            turn = math.radians(115. * fraction) if case == "fly" else 0.
            vertical = {"special": 60., "fly": 0., "dive": -160., "land": -65.}[case]
            velocity = unreal.Vector(100. * math.cos(turn), 100. * math.sin(turn), vertical)
        elif kind == "Mink" and case in ("special", "fly", "land"):
            action = {"special": activity.ENTER_WATER, "fly": activity.SWIM, "land": activity.EXIT_WATER}[case]
            height = 30.
        elif kind in ("AriakeCatfish", "CommonCarp", "UnidentifiedFish") and case in ("special", "fly", "land"):
            action = activity.WANDER
            velocity = unreal.Vector(45., 0., 0.)
            height = 30.
        elif case == "special":
            action = {"Fox": activity.ATTACK, "Leopard": activity.ATTACK, "Buffalo": activity.REST,
                      "Deer": activity.SLEEP, "Wolf": activity.SLEEP, "Crow": activity.TAKEOFF}.get(kind, activity.REST)
            height = 160. * fraction if kind == "Crow" else 0.
            if kind == "Crow":
                velocity = unreal.Vector(100., 0., 50.)
        elif kind == "Crow" and case in ("fly", "land"):
            action = activity.FLY if case == "fly" else activity.LAND
            height = 160. if case == "fly" else 160. * (1. - fraction)
            turn = math.radians(85. * fraction) if case == "fly" else math.radians(85.)
            velocity = unreal.Vector(100. * math.cos(turn), 100. * math.sin(turn), -65. if case == "land" else 0.)
        if case == "settled" or (support_case and early_settle and case == "death" and fraction >= .2):
            action = activity.CORPSE_SETTLED
        if support_case and case == "special":
            action = activity.REST
            height = 0.
            velocity = unreal.Vector()
        if continuity:
            frame_number = len(state["frames"].get(case, ()))
            side = -1. if frame_number % 2 else 1.
            heading = 0. if case == "steady" else 179.
            speed = 115.
            if case == "halfturn" and fraction < .34:
                heading *= side
            if case == "slowjitter":
                speed = actor.get_editor_property("idle_speed") * (.5 if fraction < .15 else 1. + side * .15)
                heading = 70. * side
            if case == "posejitter":
                speed = profile.get_editor_property("stationary_speed") * (1. + side * .10)
            direction = math.radians(heading)
            velocity = unreal.Vector(speed * math.cos(direction), speed * math.sin(direction), 0.)
            action = activity.REST if case in ("slowjitter", "posejitter") else activity.WANDER
            if case == "pitchflip" and kind in ("GoldenEagle", "Crow", "Mink", "AriakeCatfish", "CommonCarp", "UnidentifiedFish"):
                action = activity.FLY if kind in ("GoldenEagle", "Crow") else activity.SWIM
                velocity = unreal.Vector(-115., 0., 115. if fraction < .45 else -115.)
                height = 90.
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
        frame[kind]["support_x_cm"] = round(position.x, 2)
        frame[kind]["support_z_cm"] = round(ground, 2)
        frame[kind]["input_speed_cm_s"] = round(math.hypot(velocity.x, velocity.y), 2)
        if support_case:
            frame[kind]["corpse_requested"] = action == activity.CORPSE_SETTLED
    state["frames"].setdefault(case, []).append({"time": round(now, 4), "animals": frame})


def finish(result):
    unreal.unregister_slate_post_tick_callback(handle)
    try:
        report = {"result": result, "frames": state["frames"]}
        if "reverse" in state["frames"]:
            report["reversal"] = {kind: reversal_metrics(kind) for kind in species}
        if physical_slope and not support_case:
            report["near_contact_marker_drift_cm"] = contact_drift()
        if support_case and "settled" in state["frames"]:
            report["support"] = support_metrics()
        if continuity and "pitchflip" in state["frames"]:
            report["continuity"] = continuity_metrics()
        (output / f"{prefix}Metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        unreal.log("FAUNA_MOTION_" + result)
    except Exception as error:
        unreal.log_error(f"FAUNA_MOTION_FAILED writing metrics: {error}")
    finally:
        levels.editor_request_end_play()
        unreal.SystemLibrary.quit_editor()


def contact_drift():
    result = {}
    for kind in (kind for kind in species if kind in ("Bighorn", "Jackrabbit", "Horse", "Pig")):
        result[kind] = {}
        for case in ("walk", "turn", "reverse", "brake", "run"):
            frames = state["frames"].get(case, [])
            offsets = []
            for previous, current in zip(frames, frames[1:]):
                if not 0. < current["time"] - previous["time"] <= .025:
                    continue
                a, b = previous["animals"][kind], current["animals"][kind]
                if b["speed"] < 20. or min(a["ik"], b["ik"]) < .99:
                    continue
                for foot, nominal in enumerate(b["nominal_contact_cm"]):
                    before, after = a["marker_gap_cm"][foot], b["marker_gap_cm"][foot]
                    if before is not None and after is not None and max(abs(before - nominal), abs(after - nominal)) <= 2.:
                        offsets.append(math.dist(a["marker_xy_cm"][foot], b["marker_xy_cm"][foot]))
            if offsets:
                result[kind][case] = {"samples": len(offsets), "median": round(median(offsets), 3),
                                      "max": round(max(offsets), 3)}
    return result


def reversal_metrics(kind):
    samples = state["frames"]["turn"][-1:] + state["frames"]["reverse"]
    yaw = [sample["animals"][kind]["body_yaw"] for sample in samples]
    changes = [(after - before + 180.) % 360. - 180. for before, after in zip(yaw, yaw[1:])]
    intervals = [after["time"] - before["time"] for before, after in zip(samples, samples[1:])]
    return {"first_change_deg": round(changes[0], 2),
            "peak_change_deg": round(max(map(abs, changes)), 2),
            "peak_yaw_rate_deg_per_s": round(max(abs(step) / dt for step, dt in zip(changes, intervals) if dt > 0.), 1),
            "final_facing_error_deg": round(abs((yaw[-1] + 85. + 180.) % 360. - 180.), 2)}


def support_metrics():
    result = {}
    for kind in species:
        result[kind] = {}
        for case, frames in state["frames"].items():
            animals = [row["animals"][kind] for row in frames]
            gaps = [v for row in animals for v in row["marker_gap_cm"] if v is not None]
            lift = [row["mesh_z"] for row in animals]
            body = [row["body_gap_cm"] for row in animals if row["body_gap_cm"] is not None]
            resting = animals[-30:]
            torso = [row["body_gap_cm"] for row in resting if row["body_gap_cm"] is not None]
            result[kind][case] = {"min_marker_cm": min(gaps, default=None),
                                  "max_mesh_step_cm": round(max((abs(a-b) for a, b in zip(lift, lift[1:])), default=0.), 3),
                                  "max_body_step_cm": round(max((abs(a-b) for a, b in zip(body, body[1:])), default=0.), 3),
                                  "late_body_clearance_cm": median(torso) if torso else None,
                                  "late_body_drift_cm": round(max(torso)-min(torso), 3) if torso else None}
    return result


def continuity_metrics():
    results = {}
    for kind in species:
        phases = {case: [row["animals"][kind] for row in state["frames"][case]] for case in cases}
        signed_delta = lambda previous, current: (current - previous + 180.) % 360. - 180.
        first = phases["steady"][-1]["body_yaw"]
        half = phases["halfturn"]
        first_window = half[:max(1, round(len(half) / 9))]
        jitter = phases["slowjitter"][len(phases["slowjitter"]) // 4:]
        pose = [row["pose"] for row in phases["posejitter"][len(phases["posejitter"]) // 5:]]
        pitch = [row["body_pitch"] for row in phases["pitchflip"]]
        pitch_steps = [b-a for a,b in zip(pitch, pitch[1:])]
        results[kind] = {
            "halfturn_progress_200ms_deg": round(abs(signed_delta(first, first_window[-1]["body_yaw"])), 2),
            "halfturn_reversed_frames": sum(abs(delta) > .05 and delta * signed_delta(first, first_window[-1]["body_yaw"]) < 0.
                for delta in (signed_delta(a["body_yaw"], b["body_yaw"]) for a,b in zip(first_window, first_window[1:]))),
            "slow_heading_jitter_deg": round(max(abs(signed_delta(jitter[0]["body_yaw"], row["body_yaw"])) for row in jitter), 2),
            "stationary_pose_switches": sum(a != b for a,b in zip(pose, pose[1:])),
            "peak_pitch_step_deg": round(max(map(abs, pitch_steps)), 2),
            "peak_pitch_step_change_deg": round(max(abs(a-b) for a,b in zip(pitch_steps, pitch_steps[1:])), 2),
        }
    return results


def verify():
    if continuity:
        if verify_continuity:
            for kind, metrics in continuity_metrics().items():
                if (metrics["halfturn_progress_200ms_deg"] < 10. or metrics["halfturn_reversed_frames"] > 1
                        or metrics["slow_heading_jitter_deg"] > 3. or metrics["stationary_pose_switches"] > 1):
                    raise RuntimeError(f"{kind} orientation or pose failed continuity: {metrics}")
        return
    if support_case:
        for kind in species:
            if not state["frames"]["settled"][-1]["animals"][kind].get("settled"):
                raise RuntimeError(f"{kind} did not hold its final death pose on {support_case}")
        if verify_support and pig_only:
            metrics = support_metrics()["Pig"]
            for case in ("special", "rise", "death", "settled"):
                if metrics[case]["min_marker_cm"] < -.75 or metrics[case]["max_mesh_step_cm"] > 7.1:
                    raise RuntimeError(f"Pig {support_case} {case} ground contact exceeded tolerance: {metrics[case]}")
            if metrics["settled"]["late_body_drift_cm"] > .1:
                raise RuntimeError(f"Pig corpse moves after settling: {metrics['settled']}")
        if early_settle:
            frames = state["frames"]["death"]
            requested = next(row for row in frames if row["animals"]["Pig"]["corpse_requested"])
            settled = next(row for row in frames + state["frames"]["settled"] if row["animals"]["Pig"]["settled"])
            if settled["time"] - requested["time"] < 1.4:
                raise RuntimeError("The early corpse snapshot cut off the visible death clip")
        return
    frames = state["frames"]
    idle_speeds = {kind: actor.get_editor_property("idle_speed") for kind, actor, _, _ in state["fixtures"]}
    for kind in species:
        reversal = reversal_metrics(kind)
        if reversal["peak_yaw_rate_deg_per_s"] > 550. or reversal["final_facing_error_deg"] > 1.:
            raise RuntimeError(f"{kind} reversal exceeded the rate limit or did not converge: {reversal}")
        if abs(reversal["first_change_deg"]) >= reversal["peak_change_deg"] * .75:
            raise RuntimeError(f"{kind} reversal jumped to its peak rate: {reversal}")
        brake = [frame["animals"][kind] for frame in frames["brake"]]
        stop = next(index for index, frame in enumerate(brake) if frame["input_speed_cm_s"] <= idle_speeds[kind])
        if not straight_brake and abs(brake[stop - 1]["turn_weight"]) > .02 and abs(brake[stop]["turn_weight"]) < .01:
            raise RuntimeError(f"{kind} turn weight dropped immediately at a stop")
        expected = (4 if kind in ("Bighorn", "Jackrabbit", "Horse") else 0) if expanded else (2 if kind == "Crow" else 4)
        contacts = frames["walk"][-1]["animals"][kind]["valid_feet"]
        if contacts != expected:
            raise RuntimeError(f"{kind} unexpected slope contacts: {contacts}")
        if physical_slope and kind in ("Bighorn", "Jackrabbit", "Horse", "Pig"):
            walk = [sample["animals"][kind] for sample in frames["walk"]]
            if not (walk[0]["support_x_cm"] < 0. < walk[-1]["support_x_cm"]):
                raise RuntimeError(f"{kind} did not cross the fixed floor-to-ramp seam")
            for case in ("walk", "turn", "reverse", "brake", "run"):
                gaps = [gap for sample in frames[case] for gap in sample["animals"][kind]["marker_gap_cm"]
                        if gap is not None]
                if not gaps or min(gaps) < -.5:
                    raise RuntimeError(f"{kind} {case} marker crossed the support by more than 0.5 cm")
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
    if pig_only:
        for case, pose in (("feed", 4), ("chew", 1), ("special", 7)):
            if frames[case][-1]["animals"]["Pig"]["pose"] != pose:
                raise RuntimeError(f"Pig {case} pose did not play")
    else:
        bird = "GoldenEagle" if expanded else "Crow"
        for case, pose in (("special", 9), ("fly", 10), ("land", 11)):
            crow = frames[case][-1]["animals"][bird]
            if crow["pose"] != pose or crow["valid_feet"] or crow["ik"] > .01:
                raise RuntimeError(f"{bird} invalid {case} pose or foot contact")
        if max(abs(row["animals"][bird]["body_roll"]) for row in frames["fly"]) < .5:
            raise RuntimeError(f"{bird} turn lacks a flight bank")
    if expanded:
        for case, pose in (("special", 9), ("fly", 10), ("land", 11)):
            if frames[case][-1]["animals"]["Mink"]["pose"] != pose:
                raise RuntimeError(f"Mink did not select the {case} water pose")
        dive = frames["dive"][-1]["animals"]["GoldenEagle"]
        if dive["pose"] != 6 or dive["body_pitch"] >= -10. or dive["valid_feet"]:
            raise RuntimeError("Eagle dive lacks the talon pose or the downward orientation")
    settled = "Pig" if pig_only else "Jackrabbit" if expanded else "Rat"
    if not frames["settled"][-1]["animals"][settled].get("settled"):
        raise RuntimeError(f"{settled} did not hold the completed death pose")


def tick(_):
    try:
        if time.monotonic() - state["start"] > 100.:
            raise RuntimeError("PIE visual fixture timed out")
        world = editor.get_game_world()
        if not world or unreal.GameplayStatics.get_time_seconds(world) < 1.:
            return
        if map_name not in world.get_name():
            raise RuntimeError("Load the owned fauna map first")
        now = unreal.GameplayStatics.get_time_seconds(world)
        if not state["fixtures"]:
            setup(world)
            state["origin"] = now
            state["last"] = now
            return
        elapsed = (now - state["origin"]) / (3.0 if support_case else 1.8)
        index = int(elapsed)
        if index >= len(cases):
            verify()
            finish("FINISHED")
            return
        case, fraction = cases[index], elapsed - index
        dt = min(.1, now - state["last"])
        state["last"] = now
        drive(world, now, case, fraction, dt)
        captures = ("turn", "feed", "chew", "special", "death", "settled") if pig_only else ("turn", "feed", "fly", "death", "settled")
        if case in captures and fraction >= .75 and case not in state["captures"]:
            state["captures"].add(case)
            if pig_only:
                animal = state["fixtures"][0][1]
                subject = animal.get_actor_location() + unreal.Vector(0., 0., 40.)
                viewpoint = subject + unreal.Vector(280., -345., 135.)
                state["camera"].set_actor_location(viewpoint, False, True)
                state["camera"].set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(viewpoint, subject), False)
            image = (output / f"{prefix}_{case}.png").as_posix()
            unreal.SystemLibrary.execute_console_command(world, f'HighResShot 1280x720 filename="{image}"')
    except Exception as error:
        unreal.log_error(str(error))
        finish("FAILED")


handle = unreal.register_slate_post_tick_callback(tick)

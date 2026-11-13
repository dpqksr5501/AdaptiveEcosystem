"""Run PIE with audio enabled and exercise player or fauna foot contacts."""

import json
import re
import time
from pathlib import Path

import unreal as u


editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
builder = u.EcoCreatureAnimationBuilder
out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / "FaunaFootsteps"
run_name = re.search(r"-FaunaFootstepsName=([A-Za-z0-9_]+)", u.SystemLibrary.get_command_line())
if run_name:
    out /= run_name.group(1)
out.mkdir(parents=True, exist_ok=True)
surfaces = ("Grass", "Dry", "Snow", "Water", "Wet", "Stone", "Wood")
expanded = "-FaunaFootstepsExpanded" in u.SystemLibrary.get_command_line()
walk_speed = {"Rat": 55., "Fox": 130., "Pig": 130., "Leopard": 150., "Crow": 70.,
              "Buffalo": 100., "Deer": 300., "Wolf": 275.}
cases = [(f"player-{kind}-walk", 1.55) for kind in surfaces] + [("player-Grass-run", 1.1), ("player-Grass-sneak", 1.6)]
cases += [("player-Grass-rain", 1.55)]
cases += [(f"rig-{kind}", 2.7) for kind in walk_speed]
cases += [("silent-Crow", 1.2), ("distant-Rat", 1.8), ("distant-Buffalo", 1.8)]
if expanded:
    walk_speed = {"Bighorn": 95., "Jackrabbit": 70., "Horse": 135., "Mink": 95., "GoldenEagle": 70.}
    cases = [(f"rig-{kind}-{surface}", 3.0) for kind in walk_speed for surface in ("Grass", "Stone")]
    cases += [("silent-GoldenEagle", 1.2)]
state = {"world": None, "record": False, "reports": {}, "start": time.monotonic(), "index": -1}
map_name = "LV_JYU_ExpandedFauna" if expanded else "LV_JYU_Fauna"
map_path = f"/Game/JYU/Maps/{map_name}"
if editor.get_editor_world().get_name() != map_name and not levels.load_level(map_path):
    raise RuntimeError(f"Could not open {map_path}")
settings = u.get_default_object(u.load_class(None, "/Script/UnrealEd.LevelEditorPlaySettings"))
previous_sound = settings.get_editor_property("EnableGameSound")
settings.set_editor_property("EnableGameSound", True)
levels.editor_request_begin_play()


def spawn(world, cls, point):
    actor = builder.spawn_visual_audit_actor(world, cls, u.Transform(location=point))
    if not actor:
        raise RuntimeError(f"Could not spawn {cls}")
    return actor


def start(world):
    player = u.GameplayStatics.get_player_controller(world, 0)
    pawn = player.get_controlled_pawn() if player else None
    if not pawn:
        return False
    bridge = pawn.get_component_by_class(u.EcoPlayerEcologyComponent)
    if not bridge:
        raise RuntimeError(f"Missing player ecology component on {pawn.get_class().get_name()}")
    bridge.set_editor_property("use_keyboard_gait", False)
    strips = {actor.get_actor_label().removeprefix("Fauna_Footstep_"): actor.get_actor_location()
              for actor in u.GameplayStatics.get_all_actors_of_class(world, u.StaticMeshActor)
              if actor.get_actor_label().startswith("Fauna_Footstep_")}
    if set(strips) != set(surfaces):
        raise RuntimeError(f"Missing surface strips: {set(surfaces) - set(strips)}")
    runtime = u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureIntegrationSpawner)[0]
    region = next(region for region in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)
                  if str(region.get_editor_property("region_id")) == "FaunaMeadow")
    audio_set = runtime.get_editor_property("footstep_audio_set")
    if not audio_set:
        raise RuntimeError("Fauna footstep set is missing")
    for command in ("eco.Footsteps.Log 1", "eco.Senses.NoiseLog 1", "eco.Footsteps.HearingLog 1", "au.DisableAppVolume 1"):
        u.SystemLibrary.execute_console_command(world, command)
    u.AudioMixerLibrary.start_recording_output(world, 45.)
    state.update(world=world, player=player, pawn=pawn, strips=strips, bridge=bridge, audio=audio_set, region=region,
                 start_case=u.GameplayStatics.get_time_seconds(world), record=True)
    return True


def read(component):
    return {key: component.get_editor_property(key) for key in
            ("played_count", "notify_played_count", "distance_played_count", "last_volume", "last_playback_range")} | {
                "surface": str(component.get_editor_property("last_surface")),
                "wave": str(component.get_editor_property("last_sound"))}


def begin_case(world, label):
    pawn, player = state["pawn"], state["player"]
    group, kind, *mode = label.split("-")
    if group == "player":
        point = state["strips"][kind]
        pawn.character_movement.stop_movement_immediately()
        pawn.set_actor_location(point + u.Vector(0., -515., 97.), False, True)
        player.set_control_rotation(u.Rotator(pitch=-17., yaw=90.))
        index = {"walk": 0, "sneak": 1, "run": 2, "rain": 0}[mode[0]]
        if not builder.set_audit_player_gait(pawn, index):
            raise RuntimeError(f"Player gait rejected: {mode[0]}")
        if mode[0] == "rain":
            state["dry_weather"] = state["region"].get_environment_state()
            wet = state["region"].get_environment_state()
            wet.set_editor_property("rainfall", .9)
            state["region"].set_environment_state(wet)
    else:
        pawn.character_movement.disable_movement()
        if "camera" not in state:
            state["camera"] = spawn(world, u.CameraActor, pawn.get_actor_location())
            player.set_view_target_with_blend(state["camera"], 0.)
        surface = mode[0] if mode else "Grass"
        point = state["strips"][surface] + u.Vector(0., -520., 1.5)
        root = "ExpandedFauna" if expanded else "Fauna"
        cls = u.load_class(None, f"/Game/JYU/{root}/{kind}/BP_{kind}.BP_{kind}_C")
        actor = spawn(world, cls, point)
        state.update(actor=actor, point=point, profile=actor.get_editor_property("animation_profile"))
        state["footsteps"] = actor.get_editor_property("footsteps")
        state["footsteps"].set_editor_property("audio_set", state["audio"])
        state["baseline"] = read(state["footsteps"])
    u.log(f"ECO_FAUNA_AUDIO_BEGIN {label}")


def drive(world, label, elapsed, dt):
    group, kind, *_ = label.split("-")
    if group == "player":
        state["pawn"].add_movement_input(u.Vector(0., 1., 0.), 1., False)
        return
    position = state["point"] + u.Vector(0., elapsed * walk_speed[kind], 130. if group == "silent" else 0.)
    camera = state["camera"]
    viewpoint = position + (u.Vector(650., -85., 85.) if group == "distant" else u.Vector(165., -85., 85.))
    camera.set_actor_location(viewpoint, False, True)
    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(viewpoint, position), False)
    if expanded:
        state["player"].set_audio_listener_override(None, viewpoint, camera.get_actor_rotation())
    visual = u.EcoCreatureVisualState()
    for key, value in (("stable_agent_id", 990000 + state["index"]),
                       ("species_id", "Herbivore" if kind == "Deer" else kind),
                       ("region_id", "FaunaMeadow"), ("position", position),
                       ("velocity", u.Vector(0., walk_speed[kind], 0.)), ("alive", True),
                       ("activity", u.EcoSpeciesActivity.FLY if group == "silent" else u.EcoSpeciesActivity.WANDER)):
        visual.set_editor_property(key, value)
    if not builder.update_visual_audit_actor(state["actor"], state["profile"], visual, dt):
        raise RuntimeError(f"Rejected fixture for {kind}")


def record_case(label):
    if label.startswith("player-"):
        result = {"source": "native log", "surface_expected": "Wet" if label.endswith("-rain") else label.split("-")[1]}
        if "dry_weather" in state:
            state["region"].set_environment_state(state.pop("dry_weather"))
    else:
        result = read(state["footsteps"])
        for key in ("played_count", "notify_played_count", "distance_played_count"):
            result[key] -= state["baseline"][key]
    state["reports"][label] = result
    u.log("ECO_FAUNA_AUDIO_CASE " + label + " " + json.dumps(result))
    if label.startswith(("rig-", "silent-", "distant-")):
        state["actor"].destroy_actor()


def finish(error=None):
    u.unregister_slate_post_tick_callback(handle)
    if state["record"]:
        u.AudioMixerLibrary.stop_recording_output(state["world"], u.AudioRecordingExportType.WAV_FILE,
                                                  "FaunaFootstepsPIE", str(out))
    (out / "PlaybackAudit.json").write_text(json.dumps(dict(error=error, samples=state["reports"]), indent=2), encoding="utf-8")
    if error:
        u.log_error("ECO_FAUNA_AUDIO_FAILED " + error)
    else:
        u.log("ECO_FAUNA_AUDIO_FINISHED")
    levels.editor_request_end_play()
    settings.set_editor_property("EnableGameSound", previous_sound)
    u.SystemLibrary.quit_editor()


def tick(_):
    try:
        if time.monotonic() - state["start"] > 110.:
            raise RuntimeError("Timed out waiting for PIE footstep checks")
        world = editor.get_game_world()
        if not world or u.GameplayStatics.get_time_seconds(world) < 1.:
            return
        if state["world"] is None and not start(world):
            return
        now = u.GameplayStatics.get_time_seconds(world)
        index = state["index"]
        if index >= 0 and now - state["start_case"] >= cases[index][1]:
            record_case(cases[index][0])
        elif index >= 0:
            drive(world, cases[index][0], now - state["start_case"], min(.1, now - state["last"]))
            state["last"] = now
            return
        index += 1
        if index == len(cases):
            failed = []
            for label, report in state["reports"].items():
                silent = label.startswith("silent-") or label == "distant-Rat"
                if not label.startswith("player-") and (report["played_count"] > 0) == silent:
                    failed.append(label)
                if expanded and label.startswith("rig-") and report["surface"] != label.split("-")[-1]:
                    failed.append(label + " surface")
                if label.startswith("rig-"):
                    kind = label.split("-")[1]
                    trigger = "distance_played_count" if kind in ("Mink", "GoldenEagle") else "notify_played_count"
                    if report[trigger] == 0:
                        failed.append(label + " contact timing")
            finish("unexpected playback: " + ", ".join(failed) if failed else None)
            return
        state.update(index=index, start_case=now, last=now)
        begin_case(world, cases[index][0])
    except Exception as error:
        finish(str(error))


handle = u.register_slate_post_tick_callback(tick)

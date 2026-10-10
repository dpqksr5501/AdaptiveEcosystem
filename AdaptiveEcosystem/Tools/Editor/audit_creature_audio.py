"""PIE-only verification: follow a Forest then Barren animal with the observer camera.

No animal position, policy, vitals, or saved level is modified. Records the Unreal
master submix (no microphone) to Saved/FootstepAudioAudit and samples local counters.
Run in the editor console before Play. Finishes after two 6-second surface samples.
"""
import json
import os
import time
import unreal

OUT = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "FootstepAudioAudit")
os.makedirs(OUT, exist_ok=True)
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
STATE = {"phase": 0, "started": None, "recording": False, "deadline": time.monotonic() + 90, "samples": []}


def sample(delta):
    world = EDITOR.get_game_world()
    if not world:
        if time.monotonic() > STATE["deadline"]:
            unreal.unregister_slate_post_tick_callback(HANDLE)
            unreal.log_warning("FOOTSTEP_AUDIO_AUDIT_TIMEOUT_NO_PIE")
        return
    animals = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureRepresentationActor)
    surface = "Grass" if STATE["phase"] == 0 else "Dry"
    region = "Forest" if surface == "Grass" else "Barren"
    # Initially bring the observer into Barren to trigger the ordinary streaming source.
    player = unreal.GameplayStatics.get_player_controller(world, 0)
    if not player or not player.get_controlled_pawn():
        return
    candidates = [a for a in animals if str(a.get_editor_property("footsteps").get_editor_property("last_surface")) == surface
                  and a.get_velocity().length() > 40]
    if not candidates:
        if surface == "Dry":
            player.get_controlled_pawn().set_actor_location(unreal.Vector(34000, 0, 2400), False, False)
        if time.monotonic() > STATE["deadline"]:
            unreal.unregister_slate_post_tick_callback(HANDLE)
            unreal.log_warning("FOOTSTEP_AUDIO_AUDIT_TIMEOUT_MISSING_SURFACE " + surface)
        return
    target = min(candidates, key=lambda a: (0 if str(a.get_editor_property("visual_species_id")) == "Herbivore" else 1,
                                          a.get_editor_property("visual_state").get_editor_property("stable_agent_id")))
    point = target.get_actor_location()
    observer = point + unreal.Vector(400, 250, 1000)
    player.get_controlled_pawn().set_actor_location(observer, False, False)
    player.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(observer, point))
    if not STATE["recording"]:
        unreal.AudioMixerLibrary.start_recording_output(world, 8.0)
        STATE["recording"] = True
        STATE["started"] = time.monotonic()
        unreal.log("FOOTSTEP_AUDIO_AUDIT_RECORDING " + surface)
    if time.monotonic() - STATE["started"] >= 6:
        unreal.AudioMixerLibrary.stop_recording_output(world, unreal.AudioRecordingExportType.WAV_FILE,
                                                               "PIE_" + surface, OUT)
        STATE["samples"].append({"surface": surface, "actors": [{"agent": a.get_editor_property("visual_state").get_editor_property("stable_agent_id"),
            "species": str(a.get_editor_property("visual_species_id")), "count": a.get_editor_property("footsteps").get_editor_property("played_count"),
            "last_sound": str(a.get_editor_property("footsteps").get_editor_property("last_sound"))} for a in candidates]})
        STATE["recording"] = False
        STATE["phase"] += 1
        if STATE["phase"] >= 2:
            unreal.unregister_slate_post_tick_callback(HANDLE)
            with open(os.path.join(OUT, "PIE_PlaybackCounters.json"), "w", encoding="utf-8") as stream:
                json.dump(STATE["samples"], stream, indent=2, ensure_ascii=False)
            unreal.log("FOOTSTEP_AUDIO_AUDIT_FINISHED " + OUT)


def tick(delta):
    try:
        sample(delta)
    except Exception as error:
        unreal.unregister_slate_post_tick_callback(HANDLE)
        unreal.log_error("FOOTSTEP_AUDIO_AUDIT_FAILED " + str(error))


HANDLE = unreal.register_slate_post_tick_callback(tick)
unreal.log("FOOTSTEP_AUDIO_AUDIT_ARMED")

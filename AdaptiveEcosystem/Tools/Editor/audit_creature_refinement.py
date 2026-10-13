"""PIE-only observer/audio audit. Never edits logical animals or saved placement.
Run before Play; output is the master submix (no microphone) and local counters.
"""
import json
import time
from pathlib import Path
import unreal

OUT = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "CreatureRefinementAudit"
OUT.mkdir(exist_ok=True)
EDITOR = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
PHASES = [("Wolf", "Wolf", None), ("Grass", "Herbivore", "Grass"), ("Dry", "Herbivore", "Dry")]
STATE = {"phase": 0, "recording": False, "started": 0, "deadline": time.monotonic()+180, "samples": []}
for command in ("eco.Footsteps.Log 1", "eco.Senses.PreyLog 1", "eco.Senses.NoiseLog 1",
                "eco.Senses.DrawFOV 1", "eco.Senses.Debug 1", "eco.Senses.DrawLimit 2", "eco.Shelter.Log 1"):
    unreal.SystemLibrary.execute_console_command(EDITOR.get_editor_world(), command)

def counter(actor):
    component = actor.get_editor_property("footsteps")
    return {"agent": actor.get_editor_property("visual_state").get_editor_property("stable_agent_id"),
            "species": str(actor.get_editor_property("visual_species_id")),
            "notify": component.get_editor_property("notify_played_count"),
            "distance": component.get_editor_property("distance_played_count"),
            "surface": str(component.get_editor_property("last_surface")),
            "material": str(component.get_editor_property("last_material")),
            "sound": str(component.get_editor_property("last_sound"))}

def finish(reason):
    unreal.unregister_slate_post_tick_callback(HANDLE)
    (OUT / "PIE_PlaybackCounters.json").write_text(json.dumps({"result": reason, "samples": STATE["samples"]}, indent=2), encoding="utf-8")
    unreal.log("CREATURE_REFINEMENT_AUDIT_" + reason)

def sample(delta):
    world = EDITOR.get_game_world()
    if time.monotonic() > STATE["deadline"]:
        if world and STATE["recording"]:
            unreal.AudioMixerLibrary.stop_recording_output(world, unreal.AudioRecordingExportType.WAV_FILE, "Timeout", str(OUT))
        finish("TIMEOUT")
        return
    if not world:
        return
    player = unreal.GameplayStatics.get_player_controller(world, 0)
    if not player or not player.get_controlled_pawn():
        return
    label, species, surface = PHASES[STATE["phase"]]
    animals = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureRepresentationActor)
    candidates = [a for a in animals if str(a.get_editor_property("visual_species_id")) == species
                  and a.get_velocity().length() > 40
                  and (surface is None or str(a.get_editor_property("footsteps").get_editor_property("last_surface")) == surface)]
    if not candidates:
        if surface == "Dry":
            player.get_controlled_pawn().set_actor_location(unreal.Vector(34000, 0, 2400), False, False)
        return
    target = min(candidates, key=lambda a:a.get_editor_property("visual_state").get_editor_property("stable_agent_id"))
    point = target.get_actor_location()
    observer = point + unreal.Vector(400, 250, 650)
    player.get_controlled_pawn().set_actor_location(observer, False, False)
    player.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(observer, point))
    if not STATE["recording"]:
        STATE["baseline"] = counter(target)
        unreal.AudioMixerLibrary.start_recording_output(world, 8.)
        STATE["recording"] = True
        STATE["started"] = time.monotonic()
        unreal.log("CREATURE_REFINEMENT_RECORDING " + label)
    if time.monotonic()-STATE["started"] >= 6:
        unreal.AudioMixerLibrary.stop_recording_output(world, unreal.AudioRecordingExportType.WAV_FILE, "PIE_"+label, str(OUT))
        STATE["samples"].append({"phase": label, "baseline": STATE["baseline"], "actors": [counter(a) for a in candidates]})
        STATE["recording"] = False
        STATE["phase"] += 1
        if STATE["phase"] == len(PHASES):
            finish("FINISHED")

def tick(delta):
    try:
        sample(delta)
    except Exception as error:
        unreal.log_error("CREATURE_REFINEMENT_AUDIT_FAILED " + str(error))
        finish("FAILED")

HANDLE = unreal.register_slate_post_tick_callback(tick)
unreal.log("CREATURE_REFINEMENT_AUDIT_ARMED")

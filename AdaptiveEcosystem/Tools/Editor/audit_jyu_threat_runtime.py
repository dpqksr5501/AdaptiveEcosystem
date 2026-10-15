"""Read-only audit of actual Mass-backed creatures in copied-level standalone PIE.
No fixture spawn, creature teleport, policy injection, or saved asset writes.
"""
import json, time
from collections import Counter
from pathlib import Path
import unreal
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world = editor.get_game_world()
if not world or "LV_JYU_V3Integration" not in world.get_name():
    raise RuntimeError("Copied JYU PIE only")
out = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "ThreatAudit_20261016"
if "-JYUSocialV3Audit" in unreal.SystemLibrary.get_command_line():
    out = out.parent / "SocialV3_20261016"
out.mkdir(parents=True, exist_ok=True)
unreal.SystemLibrary.execute_console_command(world, "eco.Senses.NoiseLog 1")
if "-JYUSocialV3Audit" in unreal.SystemLibrary.get_command_line():
    for command in ("eco.Shelter.Log 1", "eco.Social.ActionAudit 1"):
        unreal.SystemLibrary.execute_console_command(world, command)
player = unreal.GameplayStatics.get_player_controller(world, 0)
original_view = player.get_view_target()
camera = None
if "-JYUThreatCamera" in unreal.SystemLibrary.get_command_line():
    camera = unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, unreal.CameraActor, unreal.Transform(location=original_view.get_actor_location()))
    if not camera: raise RuntimeError("Audit camera rejected")
    player.set_view_target_with_blend(camera, 0)
state = {"start": time.monotonic(), "next": 0, "samples": [], "captured": False}

def capture(actor):
    visual = actor.get_editor_property("visual_state")
    key = visual.get_editor_property("stable_agent_id")
    raw = unreal.EcoCreatureInspectionLibrary.capture_agent(world, key)
    if isinstance(raw, tuple): raw = next((v for v in raw if isinstance(v, str)), None)
    if not raw: return None
    data = json.loads(raw)
    data["region"] = str(visual.get_editor_property("region_id"))
    data["visual_speed_cm_s"] = visual.get_editor_property("velocity").length()
    mesh = actor.get_editor_property("creature_mesh")
    anim = mesh.get_anim_instance()
    data["animation_pose"] = anim.get_editor_property("animation_index") if anim else None
    return data

def finish(result):
    unreal.unregister_slate_post_tick_callback(handle)
    if camera:
        player.set_view_target_with_blend(original_view, 0)
        camera.destroy_actor()
    rows = [d for sample in state["samples"] for d in sample["deer"]]
    summary = {
        "samples": len(state["samples"]), "deer_records": len(rows),
        "detected_records": sum(d.get("native_threat_count", 0) > 0 for d in rows),
        "flight_override_counts": dict(Counter(d.get("flight_override", -1) for d in rows)),
        "executed_counts": dict(Counter(d.get("executed", -1) for d in rows)),
        "kin_alarm_records": sum(d.get("native_kin_alarm", 0) > 0 for d in rows),
        "heard_cue_records": sum("Hearing" in d.get("sense", "") for d in rows),
        "learned_policy_read_records": sum(d.get("committed_policy_read", False) for d in rows),
        "preview_fixture_records": sum(sample["preview_fixtures"] for sample in state["samples"]),
        "social_override_counts": dict(Counter(d.get("social_override", -1) for d in rows)),
        "shelter_state_counts": dict(Counter(d.get("shelter_state", -1) for d in rows)),
        "blind_social_reaction_records": sum(d.get("native_threat_count", 0) == 0 and d.get("social_override", 0) > 0 for d in rows),
        "policy_graze_to_social_flee_records": sum(d.get("request") == 0 and d.get("executed") == 1 and d.get("social_override") == 2 for d in rows),
    }
    (out / "ThreatRuntime.json").write_text(json.dumps({"result": result, "summary": summary, "samples": state["samples"]}, indent=2), encoding="utf-8")
    unreal.log("JYU_THREAT_AUDIT_" + result + " " + json.dumps(summary))

def tick(dt):
    try:
        elapsed = time.monotonic() - state["start"]
        if elapsed >= 35: finish("FINISHED"); return
        if elapsed < state["next"]: return
        state["next"] = elapsed + .5
        actors = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureRepresentationActor)
        bound = [a for a in actors if a.get_editor_property("bound")]
        fixtures = [a for a in bound if a.actor_has_tag("JYU.VisualAudit")]
        live = [a for a in bound if not a.actor_has_tag("JYU.VisualAudit") and a.get_editor_property("visual_state").get_editor_property("alive")]
        wolves = [a for a in live if str(a.get_editor_property("visual_species_id")) == "Wolf"]
        deer = [a for a in live if str(a.get_editor_property("visual_species_id")) == "Herbivore"]
        records = []
        for actor in deer:
            data = capture(actor)
            if data:
                data["nearest_visible_wolf_cm"] = min(((actor.get_actor_location() - wolf.get_actor_location()).length() for wolf in wolves), default=None)
                records.append(data)
        state["samples"].append({"elapsed": elapsed, "preview_fixtures": len(fixtures), "visible_wolves": len(wolves), "deer": records, "wolves": [d for a in wolves if (d := capture(a))]})
        if camera and wolves and deer:
            fleeing = [a for a in deer if a.get_editor_property("visual_state").get_editor_property("velocity").length() > 500]
            subject = min(fleeing or deer, key=lambda a: min((a.get_actor_location()-w.get_actor_location()).length() for w in wolves))
            wolf = min(wolves, key=lambda a: (subject.get_actor_location()-a.get_actor_location()).length())
            point = (subject.get_actor_location()+wolf.get_actor_location())*.5
            distance = (subject.get_actor_location()-wolf.get_actor_location()).length()
            span = max(900, distance*.8)
            location = point+unreal.Vector(0, -span, span*.6)
            camera.set_actor_location(location, False, False)
            camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(location, point+unreal.Vector(0,0,70)), False)
        if not state["captured"] and elapsed >= 12:
            state["captured"] = True
            unreal.SystemLibrary.execute_console_command(world, 'HighResShot 1280x720 filename="' + str(out / "ThreatRuntime.png").replace(chr(92), "/") + '"')
    except Exception as error:
        unreal.log_error("JYU_THREAT_AUDIT_FAILED " + str(error)); finish("FAILED")
handle = unreal.register_slate_post_tick_callback(tick)
unreal.log("JYU_THREAT_AUDIT_ARMED")

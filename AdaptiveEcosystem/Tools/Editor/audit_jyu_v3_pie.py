"""PIE-only audit: drives the real Player CharacterMovement, reads animal presentation.
Never edits creature Mass state, policy, resources, or saved level placement.
Records engine master submix only (no microphone).
"""
import json,time
from pathlib import Path
import unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
world=editor.get_game_world()
if not world or "LV_JYU_V3Integration" not in world.get_name(): raise RuntimeError("Run in copied JYU PIE only")
player=unreal.GameplayStatics.get_player_controller(world,0);pawn=player.get_controlled_pawn()
animals=unreal.GameplayStatics.get_all_actors_of_class(world,unreal.EcoCreatureRepresentationActor)
candidates=[a for a in animals if a.get_editor_property("bound") and a.get_editor_property("visual_state").get_editor_property("alive") and str(a.get_editor_property("visual_species_id"))=="Herbivore"]
if not candidates: raise RuntimeError("No visible live deer")
target=min(candidates,key=lambda a:(a.get_actor_location()-pawn.get_actor_location()).length())
point=target.get_actor_location();pawn.set_actor_location(point+unreal.Vector(-450,0,150),False,False)
player.set_control_rotation(unreal.MathLibrary.find_look_at_rotation(pawn.get_actor_location(),point))
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/"IntegrationV3";out.mkdir(exist_ok=True)
for cmd in ("eco.Footsteps.Log 1","eco.Senses.NoiseLog 1","au.DisableAppVolume 1","eco.Player.GaitLog 1"):
    unreal.SystemLibrary.execute_console_command(world,cmd)
bridges=pawn.get_components_by_class(unreal.EcoPlayerEcologyComponent)
bridge=bridges[0]
for component in bridges: component.set_editor_property("use_keyboard_gait",False)
unreal.log("JYU_AUDIO_AUDIT_VERSION_6 components="+str(len(bridges)))
bridge.set_editor_property("use_keyboard_gait",False)
state={"start":time.monotonic(),"next":0,"samples":[],"start_player":str(pawn.get_actor_location()),"components":len(bridges),"phase":-1}
unreal.log("JYU_SET_GAIT_DOC "+str(bridge.set_gait.__doc__))
unreal.AudioMixerLibrary.start_recording_output(world,10)
def finish(result):
    unreal.unregister_slate_post_tick_callback(handle)
    bridge.set_editor_property("use_keyboard_gait",True)
    unreal.AudioMixerLibrary.stop_recording_output(world,unreal.AudioRecordingExportType.WAV_FILE,"JYU_PIE_Master",str(out))
    (out/"JYUPIEAudit.json").write_text(json.dumps({"version":6,"components":len(bridges),"result":result,"samples":state["samples"],"start_player":state["start_player"],"end_player":str(pawn.get_actor_location())},indent=2),encoding="utf-8")
    unreal.log("JYU_PIE_AUDIT_"+result)
def tick(dt):
    try:
        elapsed=time.monotonic()-state["start"]
        phase=0 if elapsed<2 else 1 if elapsed<4 else 2
        requested=(unreal.EcoPlayerGait.WALK,unreal.EcoPlayerGait.SNEAK,unreal.EcoPlayerGait.RUN)[phase]
        if not unreal.EcoCreatureAnimationBuilder.set_audit_player_gait(pawn,phase): raise RuntimeError("Native player gait was rejected")
        if phase!=state["phase"]:
            state["phase"]=phase
            unreal.log("JYU_GAIT_REQUEST "+str(requested)+" RESULT "+str(bridge.get_editor_property("gait"))+" SPEED "+str(pawn.character_movement.max_walk_speed))
        if elapsed<6: pawn.add_movement_input(unreal.Vector(0,1,0),1,False)
        if elapsed>=state["next"]:
            state["next"]=elapsed+.5
            mesh=target.get_editor_property("creature_mesh");anim=mesh.get_anim_instance()
            feet=target.get_editor_property("footsteps")
            state["samples"].append({"elapsed":elapsed,"animation_class":anim.get_class().get_path_name() if anim else None,"pose":anim.get_editor_property("animation_index") if anim else None,"ik_alpha":anim.get_editor_property("ground_ik_alpha") if anim else None,"notify_count":feet.get_editor_property("notify_played_count"),"surface":str(feet.get_editor_property("last_surface")),"player_speed":pawn.get_velocity().length(),"player_grounded":pawn.character_movement.is_moving_on_ground(),"native_gait_index_verified":phase,"python_gait_readback":str(bridge.get_editor_property("gait")),"requested":str(requested),"keyboard":bridge.get_editor_property("use_keyboard_gait"),"animal_footsteps":sum(a.get_editor_property("footsteps").get_editor_property("notify_played_count") for a in animals)})
        if elapsed>=8:
            unreal.SystemLibrary.execute_console_command(world,"HighResShot 1280x720")
            finish("FINISHED")
    except Exception as error:
        unreal.log_error("JYU_PIE_AUDIT_FAILED "+str(error));finish("FAILED")
handle=unreal.register_slate_post_tick_callback(tick)
unreal.log("JYU_PIE_AUDIT_ARMED")

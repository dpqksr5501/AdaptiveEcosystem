"""Copied PIE only: real player CharacterMovement on the five saved material strips."""
import json,time
from pathlib import Path
import unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);world=editor.get_game_world()
if not world or "LV_JYU_V3Integration" not in world.get_name(): raise RuntimeError("Copied PIE only")
player=unreal.GameplayStatics.get_player_controller(world,0);pawn=player.get_controlled_pawn()
bridge=pawn.get_component_by_class(unreal.EcoPlayerEcologyComponent);bridge.set_editor_property("use_keyboard_gait",False)
strips={a.get_actor_label().replace("JYU_Surface_",""):a for a in unreal.GameplayStatics.get_all_actors_of_class(world,unreal.StaticMeshActor) if a.get_actor_label().startswith("JYU_Surface_")}
kinds=("Grass","Dry","Snow","Water","Wet")
if any(k not in strips for k in kinds): raise RuntimeError("Missing saved surface strips")
feet=pawn.get_component_by_class(unreal.EcoFootstepAudioComponent)
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/"IntegrationV3"
for cmd in ("eco.Footsteps.Log 1","au.DisableAppVolume 1"): unreal.SystemLibrary.execute_console_command(world,cmd)
unreal.AudioMixerLibrary.start_recording_output(world,12)
state={"start":time.monotonic(),"case":-1,"samples":[],"next":0}
def finish(result):
 unreal.unregister_slate_post_tick_callback(handle);bridge.set_editor_property("use_keyboard_gait",True)
 unreal.AudioMixerLibrary.stop_recording_output(world,unreal.AudioRecordingExportType.WAV_FILE,"JYU_Surface_Master",str(out))
 (out/"SurfaceAudioAudit.json").write_text(json.dumps({"result":result,"samples":state["samples"],"verification":"Native Eco Footstep Audio logs are authoritative for surface/count; Python component readbacks were not reliable in this audit"},indent=2),encoding="utf-8")
 unreal.log("JYU_SURFACE_AUDIO_"+result)
def tick(dt):
 try:
  elapsed=time.monotonic()-state["start"];index=int(elapsed/2)
  if index>=len(kinds):
   unreal.SystemLibrary.execute_console_command(world,'HighResShot 1280x720 filename="'+str(out/"SurfaceStrips.png").replace('\\','/')+'"');finish("FINISHED");return
  kind=kinds[index]
  if index!=state["case"]:
   state["case"]=index;point=strips[kind].get_actor_location()
   pawn.set_actor_location(point+unreal.Vector(0,-280,110),False,False);player.set_control_rotation(unreal.Rotator(pitch=-25,yaw=90,roll=0))
  if not unreal.EcoCreatureAnimationBuilder.set_audit_player_gait(pawn,0): raise RuntimeError("Movement bridge rejected")
  pawn.add_movement_input(unreal.Vector(0,1,0),1,False)
  if elapsed>=state["next"]:
   state["next"]=elapsed+.25
   state["samples"].append({"expected":kind,"elapsed":elapsed,"grounded":pawn.character_movement.is_moving_on_ground(),"python_readback_surface":str(feet.get_editor_property("last_surface")),"python_readback_count":feet.get_editor_property("played_count"),"speed":pawn.get_velocity().length()})
 except Exception as error: unreal.log_error("JYU_SURFACE_AUDIO_FAILED "+str(error));finish("FAILED")
handle=unreal.register_slate_post_tick_callback(tick)
unreal.log("JYU_SURFACE_AUDIO_ARMED")

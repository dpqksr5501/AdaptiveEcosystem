"""Copied-level PIE visual fixtures. Drives only passive representation state.
Two identical meshes/clips compare IK on/off on the same pitch. No creature Mass edits.
"""
import json,time,math
from pathlib import Path
import unreal
editor=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem);world=editor.get_game_world()
if not world or "LV_JYU_V3Integration" not in world.get_name(): raise RuntimeError("Copied JYU PIE only")
player=unreal.GameplayStatics.get_player_controller(world,0);pawn=player.get_controlled_pawn()
out=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/"IntegrationV3/IKVisual";out.mkdir(parents=True,exist_ok=True)
center=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,unreal.Vector(10000,45000,-1500))
if center is None: raise RuntimeError("Missing fixture ground")
profile=unreal.load_asset("/Game/JYU/Animation/DA_JYU_Deer_Animation")
reference=unreal.EcoCreatureAnimationProfile()
for name in ("locomotion","poses","foot_bones","ik_end_bones","contact_heights","body_bone","stationary_speed","minimum_pose_hold_seconds","max_foot_correction_cm","foot_clearance_cm"):
 reference.set_editor_property(name,profile.get_editor_property(name))
reference.set_editor_property("enable_ground_ik",False)
cls=unreal.load_class(None,"/Game/JYU/Creatures/BP_JYU_Deer.BP_JYU_Deer_C")
animcls=unreal.load_class(None,"/Game/JYU/Animation/ABP_JYU_Deer.ABP_JYU_Deer_C")
fixtures=[];plates=[]
for i in range(2):
 location=center+unreal.Vector(0,i*360,80)
 plate=unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world,unreal.StaticMeshActor,unreal.Transform(location=location))
 plate.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
 plate.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"));plate.set_actor_scale3d(unreal.Vector(8,3.2,.15));plates.append(plate)
 transform=unreal.Transform(location=location+unreal.Vector(0,0,7.5))
 actor=unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world,cls,transform)
 actor.set_actor_hidden_in_game(False)
 mesh=actor.get_editor_property("creature_mesh");mesh.set_anim_instance_class(animcls)
 fixtures.append(actor)
pawn.set_actor_hidden_in_game(True)
pawn.character_movement.disable_movement();pawn.set_actor_location(center+unreal.Vector(0,180,350),False,False)
camera_transform=unreal.Transform(location=center+unreal.Vector(450,920,260))
camera=unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world,unreal.CameraActor,camera_transform)
camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(camera.get_actor_location(),center+unreal.Vector(0,180,140)),False)
player.set_view_target_with_blend(camera,0)
A=unreal.EcoSpeciesActivity
cases=[("IdleFlat",A.HOLD,0,0),("GrazeSlope",A.GRAZE,0,4),("WalkSlope",A.FORAGE,360,4),("RunSlope",A.FLEE,900,4),("HideTransition",A.SHELTER_HOLD,0,4),("Sleep",A.SLEEP,0,4),("ReturnToWalk",A.FORAGE,360,4),("IdleSlope",A.HOLD,0,4),("IdleSlope8",A.HOLD,0,8),("IdleSlope12",A.HOLD,0,12),("HearingWhileGraze",A.GRAZE,0,4),("SightWhileGraze",A.GRAZE,0,4)]
state={"start":time.monotonic(),"case":-1,"samples":[],"next":0,"captured":set()}
def sample_feet(actor):
 mesh=actor.get_editor_property("creature_mesh");anim=mesh.get_anim_instance();result=[]
 for bone,end,neutral in zip(profile.get_editor_property("foot_bones"),profile.get_editor_property("ik_end_bones"),profile.get_editor_property("contact_heights")):
  contact=mesh.get_socket_location(bone)
  ground=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,contact)
  joint=mesh.get_parent_bone(end);root=mesh.get_parent_bone(joint)
  rootp=mesh.get_socket_location(root);jointp=mesh.get_socket_location(joint);endp=mesh.get_socket_location(end)
  result.append({"bone":str(bone),"marker_ground_gap":contact.z-ground.z-float(neutral) if ground else None,"upper_length":(jointp-rootp).length(),"lower_length":(endp-jointp).length(),"root":[rootp.x,rootp.y,rootp.z],"joint":[jointp.x,jointp.y,jointp.z],"end":[endp.x,endp.y,endp.z]})
 return {"pose":anim.get_editor_property("animation_index"),"ik_alpha":anim.get_editor_property("ground_ik_alpha"),"feet":result}
def finish(result):
 unreal.unregister_slate_post_tick_callback(handle)
 (out/"FootMetrics.json").write_text(json.dumps({"result":result,"samples":state["samples"]},indent=2),encoding="utf-8")
 unreal.log("JYU_IK_VISUAL_"+result)
def tick(dt):
 try:
  elapsed=time.monotonic()-state["start"];index=int(elapsed/3)
  if index>=len(cases): finish("FINISHED");return
  label,activity,speed,pitch=cases[index]
  if index!=state["case"]:
   state["case"]=index
   for plate in plates: plate.set_actor_rotation(unreal.Rotator(pitch=pitch,yaw=0,roll=0),False)
  for i,actor in enumerate(fixtures):
   visual=unreal.EcoCreatureVisualState()
   for name,value in (("stable_agent_id",900000+i),("species_id",unreal.Name("Herbivore")),("alive",True),("activity",activity),("velocity",unreal.Vector(speed,0,0)),("position",actor.get_actor_location()),("eating",activity==A.GRAZE)):
    visual.set_editor_property(name,value)
   if label in ("HearingWhileGraze","SightWhileGraze") and elapsed%3>=1.6:
    visual.set_editor_property("sense_source",unreal.EcoSenseSource.HEARING if label=="HearingWhileGraze" else unreal.EcoSenseSource.SIGHT)
   if not unreal.EcoCreatureAnimationBuilder.update_visual_audit_actor(actor,profile if i==0 else reference,visual,dt): raise RuntimeError("Fixture presentation rejected")
   actor.get_editor_property("identity_label").set_text(unreal.Text(("IK ON" if i==0 else "IK OFF")+" | "+label))
  if elapsed>=state["next"]:
   state["next"]=elapsed+.25
   state["samples"].append({"case":label,"elapsed":elapsed,"plate_rotation":str(plates[0].get_actor_rotation()),"on":sample_feet(fixtures[0]),"off":sample_feet(fixtures[1])})
  if elapsed%3>=2 and label not in state["captured"]:
   state["captured"].add(label)
   unreal.SystemLibrary.execute_console_command(world,'HighResShot 1280x720 filename="'+str(out/(label+'.png')).replace('\\','/')+'"')
 except Exception as error:
  unreal.log_error("JYU_IK_VISUAL_FAILED "+str(error));finish("FAILED")
handle=unreal.register_slate_post_tick_callback(tick)
unreal.log("JYU_IK_VISUAL_ARMED")

"""Author JYU-owned assets and configure only the duplicated integration level.
Run with Unreal's PythonScript commandlet or the editor Python console.
Never modifies vendor clips, team maps, or original footstep/material assets.
"""
import json
import math
from pathlib import Path
import unreal

ROOT="/Game/JYU"
LEVEL=ROOT+"/Maps/LV_JYU_V3Integration"
OWNER="JYU.V3Integration.v1"
tools=unreal.AssetToolsHelpers.get_asset_tools()
assets=unreal.EditorAssetLibrary
report={"level":LEVEL,"assets":[],"placements":[]}
def load(path):
    obj=unreal.load_asset(path)
    if not obj: raise RuntimeError("Missing asset: "+path)
    return obj
def owned(obj):
    if not obj.get_path_name().startswith(ROOT+"/"): raise RuntimeError("Outside JYU asset scope")
    tag=assets.get_metadata_tag(obj,"JYUOwner")
    if tag and str(tag)!=OWNER: raise RuntimeError("Different owner: "+obj.get_path_name())
    assets.set_metadata_tag(obj,"JYUOwner",OWNER)
    report["assets"].append(obj.get_path_name())
    return obj
def save(obj):
    if not assets.save_loaded_asset(obj,only_if_is_dirty=False): raise RuntimeError("Save failed: "+obj.get_path_name())
def duplicate(source,path):
    existing=unreal.load_asset(path)
    return owned(existing or assets.duplicate_asset(source,path))
def data(name,folder,cls):
    path=folder+"/"+name
    obj=unreal.load_asset(path)
    if not obj:
        factory=unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class",cls)
        obj=tools.create_asset(name,folder,cls,factory)
    return owned(obj)
def blueprint(name,folder,parent):
    path=folder+"/"+name
    obj=unreal.load_asset(path)
    if not obj:
        factory=unreal.BlueprintFactory();factory.set_editor_property("parent_class",parent)
        obj=tools.create_asset(name,folder,unreal.Blueprint,factory)
    return owned(obj)
def bpclass(bp): return unreal.BlueprintEditorLibrary.generated_class(bp)
def physical(name):
    folder=ROOT+"/Audio/Surfaces";obj=unreal.load_asset(folder+"/"+name)
    if not obj: obj=tools.create_asset(name,folder,unreal.PhysicalMaterial,unreal.PhysicalMaterialFactoryNew())
    owned(obj);save(obj);return obj

# Generated audio files are transformations of existing project recordings; the alarm is an authored synthetic cue.
audio=duplicate("/Game/Audio/Footsteps/Settings/DA_EcoFootsteps",ROOT+"/Audio/DA_JYU_Footsteps")
for kind in ("Snow","Water","Wet","Alarm"):
    path=ROOT+"/Audio/SW_JYU_"+kind
    sound=unreal.load_asset(path)
    if not sound:
        task=unreal.AssetImportTask()
        task.set_editor_property("filename",str(Path(unreal.Paths.project_content_dir())/"JYU"/"Audio"/"Source"/(kind+".wav")))
        task.set_editor_property("destination_path",ROOT+"/Audio")
        task.set_editor_property("destination_name","SW_JYU_"+kind)
        task.set_editor_property("automated",True);task.set_editor_property("save",True)
        tools.import_asset_tasks([task]);sound=load(path)
    owned(sound);save(sound)
    if kind!="Alarm": audio.set_editor_property(kind.lower(),[sound])
surfaces={kind:physical("PM_JYU_"+kind) for kind in ("Grass","Dry","Snow","Water","Wet")}
base_audio=load("/Game/Audio/Footsteps/Settings/DA_EcoFootsteps")
for kind,pm in surfaces.items():
    originals=list(base_audio.get_editor_property(kind.lower()+"_materials"))
    audio.set_editor_property(kind.lower()+"_materials",originals+[pm])
save(audio)

manifest=json.loads((Path(unreal.Paths.project_dir())/"Tools"/"Editor"/"Data"/"creature_foot_contacts.json").read_text(encoding="utf-8"))
characters={}
for kind in ("Deer","Wolf"):
    folder="/Game/AnimalVarietyPack/"+("Wolf" if kind=="Wolf" else "DeerStagAndDoe")+"/Animations"
    prefix="ANIM_Wolf" if kind=="Wolf" else "ANIM_DeerStag"
    names=["IdleBreathe","Bite" if kind=="Wolf" else "IdleGraze","IdleLookAround",
           "GoToRest","IdleBreathe","Sleep","Bite" if kind=="Wolf" else "AntlersAttack","IdleBreathe","Death"]
    profile=data("DA_JYU_"+kind+"_Animation",ROOT+"/Animation",unreal.EcoCreatureAnimationProfile)
    blend=load("/Game/Creatures/Integrated/BS_Eco"+kind+"_Turning")
    profile.set_editor_property("locomotion",blend)
    profile.set_editor_property("alarm_sound",load(ROOT+"/Audio/SW_JYU_Alarm"))
    clips=[]
    for i,name in enumerate(names):
        entry=unreal.EcoCreaturePoseClip()
        entry.set_editor_property("clip",load(folder+"/"+prefix+"_"+name))
        entry.set_editor_property("loop",i not in (3,6,8))
        entry.set_editor_property("blend_seconds",.2)
        clips.append(entry)
    profile.set_editor_property("poses",clips)
    profile.set_editor_property("foot_bones",[m["bone"] for m in manifest[kind]["Walk"]["markers"]])
    markers=manifest[kind]["Walk"]["markers"]
    profile.set_editor_property("ik_end_bones",[m["bone"].replace("Foot","HorseLink").replace("Finger0","Hand") for m in markers])
    profile.set_editor_property("contact_heights",[m["min_height"] for m in markers])
    profile.set_editor_property("body_bone",("Wolf" if kind=="Wolf" else "STAG")+"_-Pelvis")
    profile.set_editor_property("max_foot_correction_cm",12)
    profile.set_editor_property("foot_clearance_cm",.5)

    profile.set_editor_property("enable_ground_ik",True)
    save(profile)
    name="ABP_JYU_"+kind;abp=unreal.load_asset(ROOT+"/Animation/"+name)
    if not abp:
        factory=unreal.AnimBlueprintFactory()
        factory.set_editor_property("parent_class",unreal.EcoCreatureAnimInstance)
        factory.set_editor_property("target_skeleton",blend.get_editor_property("skeleton"))
        abp=tools.create_asset(name,ROOT+"/Animation",unreal.AnimBlueprint,factory)
    owned(abp)
    if not unreal.EcoCreatureAnimationBuilder.build_pose_graph(abp,profile): raise RuntimeError("Pose graph failed: "+kind)
    save(abp)
    bp=duplicate("/Game/Creatures/Integrated/BP_Eco"+kind,ROOT+"/Creatures/BP_JYU_"+kind)
    if not unreal.EcoCreatureAnimationBuilder.configure_behavior_representation(bp,profile,bpclass(abp)): raise RuntimeError("Representation setup failed: "+kind)
    save(bp)
    config=data("EC_JYU_V3_"+kind,ROOT+"/Config",unreal.MassEntityConfigAsset)
    if not unreal.EcoCreatureAnimationBuilder.configure_v3_entity_config(config,kind=="Wolf"): raise RuntimeError("Config failed: "+kind)
    save(config);characters[kind]=(bpclass(bp),config)

player=duplicate("/Game/ThirdPerson/Blueprints/BP_ThirdPersonCharacter",ROOT+"/Player/BP_JYU_Player")
if not unreal.EcoCreatureAnimationBuilder.add_player_ecology_component(player,audio): raise RuntimeError("Player bridge failed")
save(player)
mode=blueprint("BP_JYU_IntegrationGameMode",ROOT+"/Config",unreal.EcoCreatureIntegrationGameMode)
controller=load("/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController")
if not unreal.EcoCreatureAnimationBuilder.configure_integration_game_mode(mode,bpclass(player),bpclass(controller)): raise RuntimeError("GameMode failed")
save(mode)

# Preserve the visual shader and its six authored physical weights in our own material copies.
source_m="/Game/MWLandscapeAutoMaterial/Materials/MASTER/MTL_MWAM_AutoMaterial_MASTER"
source_mi="/Game/MWLandscapeAutoMaterial/Materials/Landscape/MI_Ecosystem_Landscape"
material=duplicate(source_m,ROOT+"/Materials/M_JYU_LandscapeSurface")
edit=unreal.MaterialEditingLibrary
outputs=[n for n in edit.get_material_expressions(material) if isinstance(n,unreal.MaterialExpressionLandscapePhysicalMaterialOutput)]
if len(outputs)!=1: raise RuntimeError("Landscape physical output topology changed")
entries=list(outputs[0].get_editor_property("inputs"))
for entry in entries:
    pm=entry.get_editor_property("physical_material");name=pm.get_name() if pm else ""
    kind="Snow" if "Snow" in name else "Water" if "Water" in name else "Grass" if "Grass" in name else "Dry"
    entry.set_editor_property("physical_material",surfaces[kind])
outputs[0].set_editor_property("inputs",entries);edit.recompile_material(material);save(material)
# Collision tiles may retain the original physical-material table until their next rebuild.
# Accept both original and owned identities, with the same surface meaning.
for node in edit.get_material_expressions(load(source_m)):
    if isinstance(node,unreal.MaterialExpressionLandscapePhysicalMaterialOutput):
        for entry in node.get_editor_property("inputs"):
            pm=entry.get_editor_property("physical_material")
            if not pm: continue
            name=pm.get_name()
            kind="Snow" if "Snow" in name else "Water" if "Water" in name else "Grass" if "Grass" in name else "Dry"
            bindings=list(audio.get_editor_property(kind.lower()+"_materials"))
            if pm not in bindings: bindings.append(pm);audio.set_editor_property(kind.lower()+"_materials",bindings)
save(audio)

instance=duplicate(source_mi,ROOT+"/Materials/MI_JYU_LandscapeSurface")
edit.set_material_instance_parent(instance,material);edit.update_material_instance(instance);save(instance)

if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(LEVEL): raise RuntimeError("Open the duplicated JYU level first")
world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if not world.get_path_name().startswith(LEVEL): raise RuntimeError("Refuse to edit a team level")
if not unreal.EcoCreatureAnimationBuilder.prepare_copied_world(world): raise RuntimeError("Load copied world failed")
actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
all_actors=actors.get_all_level_actors()
coordinators=[a for a in all_actors if isinstance(a,unreal.EcoCreatureIntegrationSpawner)]
if len(coordinators)!=1: raise RuntimeError("Expected exactly one copied coordinator")
runtime=coordinators[0]
runtime.set_editor_property("use_v3_policy",True)
runtime.set_editor_property("v3_deer_per_region",48)
runtime.set_editor_property("v3_use_authored_shelters",True)
runtime.set_editor_property("herbivore_actor_class",characters["Deer"][0])
runtime.set_editor_property("wolf_actor_class",characters["Wolf"][0])
runtime.set_editor_property("herbivore_config",characters["Deer"][1])
runtime.set_editor_property("wolf_config",characters["Wolf"][1])
runtime.set_editor_property("footstep_audio_set",audio)
runtime.set_actor_label("JYU_CreatureRuntime")
world.get_world_settings().set_editor_property("default_game_mode",bpclass(mode))
if not unreal.EcoCreatureAnimationBuilder.set_copied_landscape_material(world,instance): raise RuntimeError("Rebuild copied landscape material failed")
for actor in all_actors:
    report["placements"].append({"label":actor.get_actor_label(),"class":actor.get_class().get_name()})
groups=list(runtime.get_editor_property("groups"))
# Persistent authored anchors: this copied level does not generate extra cover at runtime.
existing={a.get_actor_label():a for a in all_actors}
for group in groups:
    center=group.get_editor_property("food_patch_position")
    region=str(group.get_editor_property("region_id"))
    for i in range(4):
        label="JYU_Shelter_"+region+"_"+str(i)
        angle=math.pi*.25+i*math.pi*.5
        hint=center+unreal.Vector(3000*math.sqrt(2)*math.cos(angle),3000*math.sqrt(2)*math.sin(angle),0)
        ground=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,hint)
        if ground is None: raise RuntimeError("No valid shelter ground: "+label)
        actor=existing.get(label) or actors.spawn_actor_from_class(unreal.EcoShelterAnchor,ground)
        actor.set_actor_label(label);actor.set_actor_location(ground,False,False)
        actor.set_editor_property("radius",1200);actor.set_editor_property("capacity",4);actor.set_editor_property("quality",.65)
        report["placements"].append({"label":label,"class":"EcoShelterAnchor","ground":[ground.x,ground.y,ground.z]})

points=list(groups[0].get_editor_property("herbivore_spawn_points")) if groups else []
for start in [a for a in all_actors if isinstance(a,unreal.PlayerStart)]:
    if points:
        hint=points[0]+unreal.Vector(-600,-300,0)
        ground=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,hint)
        if ground is not None: start.set_actor_location(ground+unreal.Vector(0,0,100),False,False)
    start.set_actor_label("JYU_PlayerStart")
# Walkable material test strips near the player spawn; each uses a saved owned material.
starts=[a for a in all_actors if isinstance(a,unreal.PlayerStart)]
if starts:
    origin=starts[0].get_actor_location()
    colors={"Grass":(.13,.24,.06),"Dry":(.26,.16,.09),"Snow":(.85,.9,.95),"Water":(.04,.23,.38),"Wet":(.07,.1,.09)}
    for i,(kind,color) in enumerate(colors.items()):
        name="M_JYU_Surface_"+kind;folder=ROOT+"/Materials"
        mat=unreal.load_asset(folder+"/"+name)
        if not mat:
            mat=tools.create_asset(name,folder,unreal.Material,unreal.MaterialFactoryNew())
            c=edit.create_material_expression(mat,unreal.MaterialExpressionConstant3Vector,-250,0)
            c.set_editor_property("constant",unreal.LinearColor(*color,1))
            edit.connect_material_property(c,"",unreal.MaterialProperty.MP_BASE_COLOR)
        owned(mat);mat.set_editor_property("phys_material",surfaces[kind]);edit.recompile_material(mat);save(mat)
        label="JYU_Surface_"+kind
        hint=origin+unreal.Vector(700+i*220,0,0)
        ground=unreal.EcoCreatureAnimationBuilder.project_placement_point(world,hint)
        if ground is None: raise RuntimeError("No test strip ground: "+kind)
        strip=existing.get(label) or actors.spawn_actor_from_class(unreal.StaticMeshActor,ground)
        strip.set_actor_label(label);strip.set_actor_location(ground+unreal.Vector(0,0,3),False,False)
        strip.set_actor_scale3d(unreal.Vector(2,8,.05))
        component=strip.static_mesh_component;component.set_static_mesh(load("/Engine/BasicShapes/Cube"));component.set_material(0,mat)
        report["placements"].append({"label":label,"class":"StaticMeshActor"})
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level(): raise RuntimeError("Copied level save failed")
saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))/"IntegrationV3"
saved.mkdir(parents=True,exist_ok=True)
(saved/"JYUAssetSetup.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
unreal.log("JYU_V3_ASSETS_AND_COPIED_LEVEL_READY")

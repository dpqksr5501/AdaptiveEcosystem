"""Connect rifle abilities to the existing common player and input assets.
The cube is a clearly named placeholder until the user's gun mesh is supplied.
Run in Editor: py <project>/Tools/Editor/setup_jwj_rifle.py
"""
import unreal as u
ROOT="/Game/JWJ/Weapons"
a=u.EditorAssetLibrary
t=u.AssetToolsHelpers.get_asset_tools()
def save(obj):
    assert a.save_loaded_asset(obj,False), obj.get_path_name()
def duplicate(src,dst):
    obj=u.load_asset(dst)
    return obj if obj else a.duplicate_asset(src,dst)
def cdo(bp):
    u.BlueprintEditorLibrary.compile_blueprint(bp)
    return u.get_default_object(bp.generated_class())
def create(name,cls,factory):
    obj=u.load_asset(ROOT+"/"+name)
    if obj:return obj,False
    obj=t.create_asset(name,ROOT,cls,factory)
    assert obj,name
    return obj,True

a.make_directory(ROOT)
weapon_factory=u.BlueprintFactory();weapon_factory.set_editor_property("parent_class",u.EcoWeaponActor)
weapon,fresh=create("BP_PlaceholderRifle",u.Blueprint,weapon_factory)
if fresh:
    obj=cdo(weapon)
    obj.set_editor_property("use_muzzle_point",True)
    obj.get_editor_property("static_mesh").set_relative_scale3d(u.Vector(.6,.06,.08))
    obj.get_editor_property("muzzle_point").set_relative_location(u.Vector(35,0,0),False,False)
    save(weapon)
f=u.DataAssetFactory();f.set_editor_property("data_asset_class",u.EcoWeaponDefinition)
data,fresh=create("DA_PlaceholderRifle",u.EcoWeaponDefinition,f)
if fresh:
    data.set_editor_property("static_mesh",u.load_asset("/Engine/BasicShapes/Cube"))
    save(data)
config=u.load_asset("/Game/JWJ/Gameplay/DA_EcoAbilityInputs_Common")
bindings=list(config.get_editor_property("ability_inputs"))
mapping,fresh=create("IMC_Rifle",u.InputMappingContext,u.InputMappingContext_Factory())
for name,key,ability in [("IA_AimRifle","RightMouseButton",u.EcoGameplayAbility_AimWeapon),("IA_FireRifle","LeftMouseButton",u.EcoGameplayAbility_FireWeapon)]:
    action,_=create(name,u.InputAction,u.InputAction_Factory())
    if not any(b.get_editor_property("action")==action for b in bindings):
        b=u.EcoAbilityInputBinding();b.set_editor_property("action",action);b.set_editor_property("ability",ability)
        b.set_editor_property("activation_event",u.TriggerEvent.STARTED);bindings.append(b)
    if fresh:
        k=u.Key();k.set_editor_property("key_name",key);mapping.map_key(action,k)
    save(action)
config.set_editor_property("ability_inputs",bindings);save(config);save(mapping)
pawn=u.load_asset("/Game/JWJ/Gameplay/BP_EcoPlayer_Common")
pcdo=cdo(pawn)
mesh=pcdo.mesh.get_editor_property("skeletal_mesh_asset")
assert u.EcoWeaponAuthoringLibrary.ensure_gun_socket(mesh,"hand_r")
save(mesh);pcdo.mesh.set_skeletal_mesh_asset(mesh)
pcdo.get_editor_property("ability_avatar").set_editor_property("input_config",config)
equipment=pcdo.get_editor_property("equipment")
if equipment.get_editor_property("initial_weapon") is None:
    equipment.set_editor_property("initial_weapon",data)
    equipment.set_editor_property("weapon_class",weapon.generated_class())
save(pawn)
controller=u.load_asset("/Game/JWJ/Gameplay/BP_EcoPlayerController_Common")
obj=cdo(controller);contexts=list(obj.get_editor_property("default_mapping_contexts"))
if mapping not in contexts:contexts.append(mapping)
obj.set_editor_property("default_mapping_contexts",contexts);save(controller)
# Existing GameMode already references the common Pawn and Controller.
# Clean only the unused assets created by the earlier isolated fixture.
for old in ["BP_RifleGameMode","BP_RifleController","BP_RiflePlayer","SK_RiflePlayer","DA_RifleInputs"]:
    path=ROOT+"/"+old
    if a.does_asset_exist(path):assert a.delete_asset(path),path
u.log("[EcoRifleSetup] PASS existing BP_EcoPlayer_Common and input/controller updated")
if "-RifleSetupQuit" in u.SystemLibrary.get_command_line():u.SystemLibrary.quit_editor()

"""Author owned common assets; team maps and their overrides are not saved."""
import unreal

lib = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
root = '/Game/Common/Gameplay'
lib.make_directory(root)
player = lib.load_asset(root + '/BP_EcoPlayer_Common') if lib.does_asset_exist(root + '/BP_EcoPlayer_Common') else None
if player is None:
    player = lib.duplicate_asset('/Game/JYU/Player/BP_JYU_Player', root + '/BP_EcoPlayer_Common')
if player is None:
    raise RuntimeError('Common player creation failed')
mode = lib.load_asset(root + '/BP_EcoGameMode_Common') if lib.does_asset_exist(root + '/BP_EcoGameMode_Common') else None
if mode is None:
    factory = unreal.BlueprintFactory()
    factory.set_editor_property('parent_class', unreal.AdaptiveEcosystemGameMode)
    mode = tools.create_asset('BP_EcoGameMode_Common', root, unreal.Blueprint, factory)
if mode is None:
    raise RuntimeError('Common mode creation failed')
cdo = unreal.get_default_object(mode.generated_class())
cdo.set_editor_property('default_pawn_class', player.generated_class())
cdo.set_editor_property('player_controller_class', unreal.load_class(None, '/Game/ThirdPerson/Blueprints/BP_ThirdPersonPlayerController.BP_ThirdPersonPlayerController_C'))
cdo.set_editor_property('hud_class', unreal.EcoCreatureInspectorHUD)
unreal.BlueprintEditorLibrary.compile_blueprint(mode)
for obj in [player, mode]:
    if not lib.save_loaded_asset(obj, only_if_is_dirty=False):
        raise RuntimeError('Save failed: ' + obj.get_path_name())

map_path = root + '/L_CommonGameplayTest'
if not lib.does_asset_exist(map_path):
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.new_level(map_path):
        raise RuntimeError('Test level creation failed')
    world = unreal.EditorLevelLibrary.get_editor_world()
    world.get_world_settings().set_editor_property('default_game_mode', mode.generated_class())
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, -50))
    floor.static_mesh_component.set_static_mesh(lib.load_asset('/Engine/BasicShapes/Cube'))
    floor.set_actor_scale3d(unreal.Vector(100, 100, 1))
    for x in [-200, 200, 600]:
        actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(x, 0, 120))
    actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 500), unreal.Rotator(-50, 0, 0))
    actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 500))
    if not levels.save_current_level():
        raise RuntimeError('Test map save failed')
unreal.log('COMMON_GAMEPLAY_ASSETS_CREATED')

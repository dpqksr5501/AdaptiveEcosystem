"""Editor-only asset generation. Never used by the game or PPO inference.
Existing assets are reused without overwriting their defaults or map contents.
Run using UnrealEditor-Cmd -EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities
  -ExecutePythonScript=<absolute path> -unattended -NullRHI.
"""
import json
import os
import unreal

ROOT = "/Game/Creatures/Demo"


def blueprint(name, parent_path, defaults=None):
    path = ROOT + "/" + name
    if unreal.EditorAssetLibrary.does_asset_exist(path):
        return unreal.EditorAssetLibrary.load_asset(path)
    factory = unreal.BlueprintFactory()
    factory.set_editor_property("parent_class", unreal.load_class(None, parent_path))
    bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, ROOT, unreal.Blueprint, factory)
    if not bp:
        raise RuntimeError("Could not create " + path)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    cls = unreal.BlueprintEditorLibrary.generated_class(bp)
    cdo = unreal.get_default_object(cls)
    for key, value in (defaults or {}).items():
        cdo.set_editor_property(key, value)
    if not unreal.EditorAssetLibrary.save_loaded_asset(bp, only_if_is_dirty=False):
        raise RuntimeError("Could not save " + path)
    return bp


def generate():
    wolf = blueprint("BP_EcoWolf", "/Script/AdaptiveEcosystem.EcoWolfRepresentation")
    herb = blueprint("BP_EcoHerbivore", "/Script/AdaptiveEcosystem.EcoHerbivoreRepresentation")
    wolf_class = unreal.BlueprintEditorLibrary.generated_class(wolf)
    herb_class = unreal.BlueprintEditorLibrary.generated_class(herb)
    demo = blueprint("BP_EcoCreatureDemoSpawner", "/Script/AdaptiveEcosystem.EcoCreatureDemoSpawner", {
        "wolf_actor_class": wolf_class, "herbivore_actor_class": herb_class,
        "herbivore_count": 8, "predator_count": 1, "spawn_radius": 2500.0,
    })
    map_path = ROOT + "/L_EcoCreatureDemo"
    if not unreal.EditorAssetLibrary.does_asset_exist(map_path):
        if not unreal.EditorLevelLibrary.new_level(map_path):
            raise RuntimeError("Could not create demo level")
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0, 0, -10))
        floor.set_actor_label("Demo flat floor - not navigation validation")
        floor.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
        floor.set_actor_scale3d(unreal.Vector(320, 320, 0.2))
        light = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1000), unreal.Rotator(-55, -25, 0))
        light.set_actor_label("Demo sun")
        light.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 1000))
        spawner = actors.spawn_actor_from_class(unreal.BlueprintEditorLibrary.generated_class(demo), unreal.Vector(0, 0, 0))
        spawner.set_actor_label("8 PPO herbivores and 1 rule-based wolf")
        actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(0, -3800, 2400), unreal.Rotator(-30, 90, 0))
        world = unreal.EditorLevelLibrary.get_editor_world()
        world.get_world_settings().set_editor_property("default_game_mode", unreal.GameModeBase)
        if not unreal.EditorLevelLibrary.save_current_level():
            raise RuntimeError("Could not save demo level")
    checks = {}
    for asset in (wolf, herb, demo):
        cls = unreal.BlueprintEditorLibrary.generated_class(asset)
        if not cls:
            raise RuntimeError("Blueprint has no generated class: " + asset.get_path_name())
        checks[asset.get_path_name()] = cls.get_path_name()
    checks[map_path] = "exists=" + str(unreal.EditorAssetLibrary.does_asset_exist(map_path))
    saved = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
    out = os.path.join(saved, "CreatureDemoAssets.json")
    with open(out, "w", encoding="utf-8") as stream:
        json.dump(checks, stream, indent=2, ensure_ascii=False)
    unreal.log("CREATURE_DEMO_ASSETS_OK " + json.dumps(checks))


try:
    generate()
finally:
    unreal.SystemLibrary.quit_editor()

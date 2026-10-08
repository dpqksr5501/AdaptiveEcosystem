"""Editor-only, idempotent creation of the opt-in networked animal slice.
Never called by the game. Existing M3/JYU/demo assets are left intact.
"""
import json
import os
import unreal

ROOT = "/Game/Creatures/Integrated"
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def load(path):
    asset = unreal.load_asset(path)
    if not asset:
        raise RuntimeError("Missing required asset: " + path)
    return asset


def bp(name, parent, defaults):
    path = ROOT + "/" + name
    asset = unreal.load_asset(path)
    if not asset:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property("parent_class", unreal.load_class(None, "/Script/AdaptiveEcosystem." + parent))
        asset = TOOLS.create_asset(name, ROOT, unreal.Blueprint, factory)
    unreal.BlueprintEditorLibrary.compile_blueprint(asset)
    cls = unreal.BlueprintEditorLibrary.generated_class(asset)
    if not cls:
        raise RuntimeError("Blueprint compilation failed: " + path)
    cdo = unreal.get_default_object(cls)
    for key, value in defaults.items():
        cdo.set_editor_property(key, value)
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Asset save failed: " + path)
    return cls


def animal(kind, mesh, folder, prefix, parent):
    idle = load(folder + "/" + prefix + "_IdleBreathe")
    walk = load(folder + "/" + prefix + "_Walk")
    run = load(folder + "/" + prefix + "_Run")
    name = "BS_Eco" + kind
    blend = unreal.load_asset(ROOT + "/" + name)
    if not blend:
        factory = unreal.BlendSpaceFactory1D()
        factory.set_editor_property("target_skeleton", idle.get_editor_property("skeleton"))
        blend = TOOLS.create_asset(name, ROOT, unreal.BlendSpace1D, factory)
    if not blend or not unreal.EcoCreatureBlendSpaceLibrary.configure_locomotion(blend, idle, walk, run, 300.0, 900.0):
        raise RuntimeError("Blend Space sample/skeleton/root-motion validation failed: " + kind)
    unreal.EditorAssetLibrary.save_loaded_asset(blend, only_if_is_dirty=False)
    cls = bp("BP_Eco" + kind, parent, {
        "visual_mesh": load(mesh), "locomotion_blend_space": blend,
        "death_animation": load(folder + "/" + prefix + "_Death"),
        "mesh_rotation": unreal.Rotator(0, 0, 0),
    })
    name = "DA_Eco" + kind
    config = unreal.load_asset(ROOT + "/" + name)
    if not config:
        factory = unreal.DataAssetFactory()
        factory.set_editor_property("data_asset_class", unreal.EcoCreatureEntityConfig)
        config = TOOLS.create_asset(name, ROOT, unreal.EcoCreatureEntityConfig, factory)
        config.configure_creature(kind == "Wolf")
        unreal.EditorAssetLibrary.save_loaded_asset(config, only_if_is_dirty=False)
    return cls, config


def generate():
    deer, deer_config = animal("Deer", "/Game/AnimalVarietyPack/DeerStagAndDoe/Meshes/SK_DeerStag",
        "/Game/AnimalVarietyPack/DeerStagAndDoe/Animations", "ANIM_DeerStag", "EcoHerbivoreRepresentation")
    wolf, wolf_config = animal("Wolf", "/Game/AnimalVarietyPack/Wolf/Meshes/SK_Wolf",
        "/Game/AnimalVarietyPack/Wolf/Animations", "ANIM_Wolf", "EcoWolfRepresentation")
    group_a = unreal.EcoCreatureSpawnGroup()
    group_a.set_editor_property("region_id", "Forest_A")
    group_a.set_editor_property("herbivores", 8)
    group_a.set_editor_property("wolves", 1)
    group_b = unreal.EcoCreatureSpawnGroup()
    group_b.set_editor_property("region_id", "Forest_B")
    group_b.set_editor_property("herbivores", 4)
    group_b.set_editor_property("wolves", 1)
    coordinator = bp("BP_EcoCreatureIntegration", "EcoCreatureIntegrationSpawner", {
        "herbivore_config": deer_config, "wolf_config": wolf_config,
        "herbivore_actor_class": deer, "wolf_actor_class": wolf,
        "groups": [group_a, group_b], "day_seconds": 30.0, "night_seconds": 30.0,
    })
    map_path = ROOT + "/L_EcoCreatureIntegration"
    if not unreal.EditorAssetLibrary.does_asset_exist(map_path):
        if not unreal.EditorLevelLibrary.new_level(map_path):
            raise RuntimeError("Could not create integration level")
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        floor = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(4000, 0, -20))
        floor.static_mesh_component.set_static_mesh(load("/Engine/BasicShapes/Cube"))
        floor.set_actor_scale3d(unreal.Vector(180, 100, 0.4))
        floor.set_actor_label("Integration ground - static query collision")
        light = actors.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 1500), unreal.Rotator(pitch=-55, yaw=-25, roll=0))
        light.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        light.light_component.set_editor_property("intensity", 5.0)
        sky = actors.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0,0,1000))
        sky.light_component.set_editor_property("mobility", unreal.ComponentMobility.MOVABLE)
        sky.light_component.set_editor_property("intensity", 1.0)
        for region_id, x, adjacent in (("Forest_A", 0, "Forest_B"), ("Forest_B", 8000, "Forest_A")):
            region = actors.spawn_actor_from_class(unreal.EcologyRegion, unreal.Vector(x, 0, 0))
            region.set_editor_property("region_id", region_id)
            region.set_editor_property("adjacent_region_ids", [adjacent])
            region.region_bounds.set_box_extent(unreal.Vector(4000, 4000, 500))
            region.set_actor_label(region_id + " - authoritative regional food")
            for y in (-1800, 1800):
                shelter = actors.spawn_actor_from_class(unreal.EcoShelterAnchor, unreal.Vector(x, y, 0))
                shelter.set_editor_property("capacity", 8)
                shelter.set_editor_property("radius", 500.0)
                shelter.set_actor_label(region_id + " authored refuge " + str(y))
        spawner = actors.spawn_actor_from_class(coordinator, unreal.Vector(0, 0, 0))
        spawner.set_actor_label("Server PPO + Social + Mass Bubble; client visual only")
        actors.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(0, -2800, 1800), unreal.Rotator(pitch=-30, yaw=90, roll=0))
        unreal.EditorLevelLibrary.get_editor_world().get_world_settings().set_editor_property("default_game_mode", unreal.EcoCreatureIntegrationGameMode)
        if not unreal.EditorLevelLibrary.save_current_level():
            raise RuntimeError("Could not save integration level")
    else:
        unreal.EditorLevelLibrary.load_level(map_path)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    for actor in actors.get_all_level_actors():
        # Python reflected Rotator positional fields differ from C++ constructor order.
        # Use named fields so the playable camera looks toward the animals, not skyward.
        if isinstance(actor, unreal.PlayerStart):
            actor.set_actor_rotation(unreal.Rotator(pitch=-30, yaw=90, roll=0), False)
        if isinstance(actor, unreal.DirectionalLight):
            actor.set_actor_rotation(unreal.Rotator(pitch=-55, yaw=-25, roll=0), False)
        if isinstance(actor, unreal.EcoCreatureIntegrationSpawner):
            # Store explicit placed-actor references as well as BP defaults. Native CDO edits
            # may be reinstanced when a new level triggers automatic Blueprint compilation.
            actor.set_editor_property("herbivore_config", deer_config)
            actor.set_editor_property("wolf_config", wolf_config)
            actor.set_editor_property("herbivore_actor_class", deer)
            actor.set_editor_property("wolf_actor_class", wolf)
            actor.set_editor_property("groups", [group_a, group_b])
            actor.set_editor_property("day_seconds", 30.0)
            actor.set_editor_property("night_seconds", 30.0)
            unreal.log("CREATURE_COORDINATOR_CONFIG " + str(actor.get_editor_property("herbivore_config")) + " " + str(actor.get_editor_property("wolf_config")))
    if not unreal.EditorLevelLibrary.save_current_level():
        raise RuntimeError("Could not save placed coordinator references")
    manifest = {"map": map_path, "deer_bp": deer.get_path_name(), "wolf_bp": wolf.get_path_name(),
        "herbivore_config": deer_config.get_path_name(), "wolf_config": wolf_config.get_path_name(),
        "blend_spaces": [ROOT + "/BS_EcoDeer", ROOT + "/BS_EcoWolf"], "initial_logical_count": 14}
    out = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "CreatureIntegrationAssets.json")
    with open(out, "w", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)
    unreal.log("CREATURE_INTEGRATION_ASSETS_OK " + json.dumps(manifest))


try:
    generate()
finally:
    unreal.SystemLibrary.quit_editor()

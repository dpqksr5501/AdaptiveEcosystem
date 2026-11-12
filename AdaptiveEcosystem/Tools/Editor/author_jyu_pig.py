"""Build a Pig-only setup with the locally installed Animal Variety Pack."""

from pathlib import Path
import runpy

import unreal


base = runpy.run_path(str(Path(__file__).with_name("setup_jyu_fauna.py")))
require, set_props, generated = (base[key] for key in ("require", "set_props", "generated"))
actors = base["ACTORS"]
assets = base["ASSETS"]
map_path = "/Game/JYU/Maps/LV_JYU_Pig"
owner = "JYU.Pig.20261113"
build_representation = base["build_representation"]
build_representation.__globals__.update(ROOT="/Game/JYU/Pig", OWNER=owner)


def pig_profile():
    pack = "/Game/AnimalVarietyPack/Pig"
    mesh = require(f"{pack}/Meshes/SK_Pig")
    skeleton = mesh.get_editor_property("skeleton")
    clips = {key: require(f"{pack}/Animations/ANIM_Pig_{key}") for key in base["PACK_CLIPS"]["Pig"]}
    for key, clip in clips.items():
        if clip.get_editor_property("skeleton") != skeleton or clip.get_play_length() <= 0.:
            raise RuntimeError(f"Pig source clip {key} has invalid duration or skeleton")
        if clip.get_editor_property("enable_root_motion"):
            raise RuntimeError(f"Pig source clip {key} enables root motion")
        unreal.log(f"ECO_PIG_SOURCE_CLIP {key} {clip.get_play_length():.3f}s")
    motion = ("IdleBreathe", "Walk", "Run", "IdleLookAround", "Chew", "Rest", "Death", "IdleLookAround")
    visual = build_representation("Pig", mesh, clips, motion, (130., 315.), True)
    return set_props(unreal.EcoFaunaSpecies(), species_id="Pig", visual_class=visual,
                     diet=unreal.EcoFaunaDiet.OMNIVORE, adult_mass=75., body_radius=30.,
                     walk_speed=130., run_speed=315., ground_acceleration=680., sight_range=1150.,
                     threat_sense_range=850., rooting_seconds=1.4, carrion_energy_per_meal=4.,
                     carrion_hunger_fraction=.83, scent_range=800., wade_depth=10., step_height=20.,
                     day_activity=.72, night_activity=.86, night_vision=.75, sprint_drain=.09,
                     defense_damage=18., offspring_guard_range=400., caregiver_follow_range=480.,
                     maturity_seconds=120., gestation=32., birth_recovery=140.,
                     death_settle_seconds=clips["Death"].get_play_length() + .1,
                     food_per_meal=.27, regional_limit=14)


def spawn(klass, x=0., y=0., z=0., pitch=0., yaw=0.):
    return actors.spawn_actor_from_class(klass, unreal.Vector(x, y, z), unreal.Rotator(pitch=pitch, yaw=yaw))


def make_map(profile):
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if assets.does_asset_exist(map_path):
        if not levels.load_level(map_path) or assets.get_metadata_tag(editor.get_editor_world(), "JYUOwner") != owner:
            raise RuntimeError(f"Unexpected existing map {map_path}")
        world = editor.get_editor_world()
        runtime = next(actor for actor in actors.get_all_level_actors()
                       if isinstance(actor, unreal.EcoCreatureIntegrationSpawner))
    else:
        unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        world = editor.get_editor_world()
        runtime = spawn(unreal.EcoCreatureIntegrationSpawner)
        floor = spawn(unreal.StaticMeshActor, z=-50.)
        floor.static_mesh_component.set_static_mesh(require("/Engine/BasicShapes/Cube"))
        floor.static_mesh_component.set_collision_profile_name("BlockAll")
        floor.set_actor_scale3d(unreal.Vector(120., 120., 1.))
        floor.set_editor_property("tags", ["Eco.VegetationGround"])
        region = spawn(unreal.EcologyRegion)
        set_props(region, region_id="PigMeadow", initial_food_amount=1100., food_capacity=2400.,
                  food_regeneration_rate=6.)
        region.get_editor_property("region_bounds").set_box_extent(unreal.Vector(5800., 5800., 2200.), False)
        start = spawn(unreal.PlayerStart, y=-1450., z=160., yaw=90.)
        start.set_actor_label("Pig Test View")
        sun = spawn(unreal.DirectionalLight, z=1800., pitch=-40., yaw=-30.)
        sun.get_component_by_class(unreal.DirectionalLightComponent).set_mobility(unreal.ComponentMobility.MOVABLE)
        spawn(unreal.SkyAtmosphere)
        spawn(unreal.SkyLight)

    set_props(world.get_world_settings(), default_game_mode=generated(require("/Game/JWJ/Gameplay/BP_EcoGameMode_Common")))
    group = set_props(unreal.EcoCreatureSpawnGroup(), region_id="PigMeadow", herbivores=6, wolves=1)
    group.set_editor_property("herbivore_spawn_points",
                              [unreal.Vector(-1500. + 280. * i, 1650., 0.) for i in range(6)])
    group.set_editor_property("wolf_spawn_points", [unreal.Vector(-2000., 2450., 0.)])
    group.set_editor_property("fauna", [set_props(unreal.EcoFaunaPlacement(), species_id="Pig", spawn_points=[
        unreal.Vector(x, y, 0.) for x, y in ((-340., -460.), (-70., -510.), (260., -420.), (570., -580.))])])
    patches = [set_props(unreal.EcoFaunaHabitatPatch(), id=name, region_id="PigMeadow", center=unreal.Vector(x, y, 0.),
                         consumers=["Pig"], capacity=capacity, regrowth_per_second=regrowth, energy_per_meal=energy)
               for name, x, y, capacity, regrowth, energy in (
                   ("FallenMast", -540., -260., 16., .13, 4.),
                   ("SoilInvertebrates", 700., -100., 10., .16, 3.))]
    set_props(runtime, use_v3_policy=True, enable_ecosystem_life=True, enable_waves=False,
              v3_deer_per_region=6, global_population_limit=40, fauna_habitat_stage=3,
              fauna_species=[profile], fauna_habitat_patches=patches, groups=[group],
              herbivore_config=require("/Game/JYU/Config/EC_JYU_V3_Deer"),
              wolf_config=require("/Game/JYU/Config/EC_JYU_V3_Wolf"),
              herbivore_actor_class=generated(require("/Game/JYU/Creatures/BP_JYU_Deer")),
              wolf_actor_class=generated(require("/Game/JYU/Creatures/BP_JYU_Wolf")))
    persistence = runtime.get_editor_property("fauna_persistence")
    runtime.set_editor_property("fauna_persistence", set_props(persistence, enabled=True))
    assets.set_metadata_tag(world, "JYUOwner", owner)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, map_path):
        raise RuntimeError(f"Could not save {map_path}")
    unreal.log(f"ECO_PIG_FIXTURE_READY {map_path}")


if __name__ == "__main__":
    make_map(pig_profile())

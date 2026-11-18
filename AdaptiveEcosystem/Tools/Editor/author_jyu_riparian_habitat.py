"""Add bank habitat and local underwater cover to an owned copy of the seasonal pool."""

import math
import random
from pathlib import Path
import runpy

import unreal as u


SOURCE = "/Game/JYU/Maps/LV_JYU_SeasonalWaterFood"
DESTINATION = "/Game/JYU/Maps/LV_JYU_RiparianHabitat"
REGION = "FaunaMeadow"
PREFIX = "JYU Riparian "
BASE = runpy.run_path(str(Path(__file__).with_name("setup_jyu_fauna.py")))
ASSETS, ACTORS, set_props, require = (BASE[key] for key in ("ASSETS", "ACTORS", "set_props", "require"))
LEVELS = u.get_editor_subsystem(u.LevelEditorSubsystem)


def add_bay(pool):
    if any(actor.get_actor_label() == PREFIX + "Vegetated Bay Input" for actor in ACTORS.get_all_level_actors()):
        return
    bay = ACTORS.spawn_actor_from_class(u.EcoVegetationHabitat, u.Vector(3710., -4435., 45.))
    bay.set_actor_label(PREFIX + "Vegetated Bay Input")
    bay.get_editor_property("bounds").set_box_extent(u.Vector(140., 112., 130.), False)
    set_props(bay, habitat_id="ExpandedVegetatedBay", region_id=REGION, plant=1, drainage=.24, shade=.4,
              priority=10, connected_fresh_water=True, supports_fauna_swimming=True, draw_water_surface=False,
              fauna_water_current=u.Vector(1.2, .25, 0.), fauna_water_temperature_c=19.,
              fauna_water_cover_density=.68, fauna_water_cover_height_cm=88.)
    for field in ("water_surface_z", "water_level_rise", "water_rain_rise_cm", "water_rise_seconds",
                  "water_high_seconds", "water_fall_seconds", "water_low_seconds"):
        bay.set_editor_property(field, pool.get_editor_property(field))


def water_material():
    folder = "/Game/JYU/Riparian"
    name = "M_RiparianWater"
    if ASSETS.does_asset_exist(f"{folder}/{name}"):
        return require(f"{folder}/{name}")
    material = u.AssetToolsHelpers.get_asset_tools().create_asset(name, folder, u.Material, u.MaterialFactoryNew())
    if not material:
        raise RuntimeError("Could not create the riparian water material")
    set_props(material, blend_mode=u.BlendMode.BLEND_TRANSLUCENT, two_sided=True)
    edit = u.MaterialEditingLibrary
    color = edit.create_material_expression(material, u.MaterialExpressionConstant3Vector, -250, 0)
    color.set_editor_property("constant", u.LinearColor(.065, .21, .18, 1.))
    if not edit.connect_material_property(color, "", u.MaterialProperty.MP_BASE_COLOR):
        raise RuntimeError("Could not connect water color")
    for index, (prop, value) in enumerate(((u.MaterialProperty.MP_OPACITY, .42), (u.MaterialProperty.MP_ROUGHNESS, .24),
                                          (u.MaterialProperty.MP_SPECULAR, .48)), 1):
        expression = edit.create_material_expression(material, u.MaterialExpressionConstant, -250, 100 * index)
        expression.set_editor_property("r", value)
        if not edit.connect_material_property(expression, "", prop):
            raise RuntimeError(f"Could not connect {prop}")
    edit.recompile_material(material)
    BASE["save"](material)
    return material


def add_bank_slopes():
    cube = require("/Engine/BasicShapes/Cube")
    mud = require("/Game/JYU/Fauna/Audio/M_Fauna_Wet")
    existing = {actor.get_actor_label() for actor in ACTORS.get_all_level_actors()}
    for label, center, size, rotation in (
        ("North Mud Bank", (4050., -4200., 45.), (1440., 180., 80.), u.Rotator(roll=25.)),
        ("South Mud Bank", (4300., -5400., 40.), (1100., 190., 80.), u.Rotator(roll=-25.)),
        ("East Mud Bank", (4920., -4800., 42.), (180., 1060., 80.), u.Rotator(pitch=-25.)),
    ):
        if PREFIX + label in existing:
            continue
        actor = ACTORS.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*center), rotation)
        actor.set_actor_label(PREFIX + label)
        actor.set_actor_scale3d(u.Vector(*(axis / 100. for axis in size)))
        actor.static_mesh_component.set_static_mesh(cube)
        actor.static_mesh_component.set_material(0, mud)
        actor.static_mesh_component.set_collision_profile_name("BlockAll")


def place_mesh(world, mesh, label, x, y, yaw, size, existing, collision=False):
    if PREFIX + label in existing:
        return
    position = u.EcoCreatureAnimationBuilder.project_placement_point(world, u.Vector(x, y, 310.))
    if position is None:
        raise RuntimeError(f"No terrain under {label} at {(x, y)}")
    actor = ACTORS.spawn_actor_from_class(u.StaticMeshActor, position, u.Rotator(yaw=yaw))
    actor.set_actor_label(PREFIX + label)
    actor.set_actor_scale3d(u.Vector(*size))
    component = actor.static_mesh_component
    component.set_static_mesh(mesh)
    component.set_collision_profile_name("BlockAll" if collision else "NoCollision")


def main():
    if not ASSETS.does_asset_exist(DESTINATION) and not ASSETS.duplicate_asset(SOURCE, DESTINATION):
        raise RuntimeError(f"Could not duplicate {SOURCE}")
    if not LEVELS.load_level(DESTINATION):
        raise RuntimeError(f"Could not load {DESTINATION}")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    runtime = next(a for a in ACTORS.get_all_level_actors() if isinstance(a, u.EcoCreatureIntegrationSpawner))
    pool = next(a for a in ACTORS.get_all_level_actors() if isinstance(a, u.EcoVegetationHabitat)
                and str(a.get_editor_property("habitat_id")) == "ExpandedFaunaPool")
    existing = {actor.get_actor_label() for actor in ACTORS.get_all_level_actors()}
    pool.set_editor_property("water_material", water_material())
    pool.get_editor_property("water_surface").set_editor_property("cast_shadow", False)
    add_bay(pool)

    assets = "/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes"
    grasses = [require(f"{assets}/Plants/SM_MWAM_Grass{k}") for k in "BCD"]
    stones = [require(f"{assets}/Cover/SM_MWAM_Stone{k}") for k in "ABD"]
    pine = require("/Game/SHC/Fab/STF/Pack03-LandscapePro/Environment/Foliage/Pines/pine02/SM_pine02")
    rng = random.Random(4391)
    stands = [("Bank", 3210., -4840., 6, 0.9), ("Bank", 3240., -5110., 7, 1.15),
              ("Bank", 3370., -4230., 7, 1.0), ("Shallows", 3710., -4435., 15, 1.2)]
    index = 0
    for label, x, y, count, scale in stands:
        for _ in range(count):
            angle, radius = rng.uniform(0., math.tau), rng.uniform(12., 70.)
            width = rng.uniform(.66, .93)
            place_mesh(world, rng.choice(grasses), f"{label} Plant {index:02}", x + radius * math.cos(angle),
                       y + radius * math.sin(angle), rng.uniform(-180., 180.), (width, width, scale * rng.uniform(.72, 1.3)), existing)
            index += 1
    for i, (x, y, size, collision) in enumerate(((3250., -4845., .6, True), (3290., -4930., .47, True),
                                                 (3190., -5135., .58, True), (3720., -4500., .32, False),
                                                 (3795., -4420., .30, False), (4610., -5095., .44, False),
                                                 (4665., -5120., .35, False))):
        place_mesh(world, stones[i % len(stones)], f"Stone {i:02}", x, y, rng.uniform(-180., 180.),
                   (size, size * .8, size * .64), existing, collision)
    for i, (x, y, size) in enumerate(((3100., -4920., .24), (3055., -5150., .31), (3295., -4205., .19))):
        place_mesh(world, pine, f"Bank Tree {i:02}", x, y, rng.uniform(-180., 180.), (size, size, size), existing)
    add_bank_slopes()

    patches = [p for p in runtime.get_editor_property("fauna_habitat_patches")
               if not str(p.get_editor_property("id")).startswith("RiparianHabitat")]
    for key, position, consumers, wet, capacity, recovery in (
        ("BankLitter", (3160., -4810., 0.), ["Mink", "Pig", "Fox", "Rat"], False, 9., .13),
        ("BayInvertebrates", (3730., -4400., 65.), ["CommonCarp", "UnidentifiedFish"], True, 9., .15),
        ("StoneMargin", (4620., -5050., 27.), ["CommonCarp", "AriakeCatfish"], True, 7., .12),
    ):
        patches.append(set_props(u.EcoFaunaHabitatPatch(), id="RiparianHabitat" + key, region_id=REGION,
                                 center=u.Vector(*position), consumers=consumers, submerged=wet, stage=1,
                                 capacity=capacity, regrowth_per_second=recovery, energy_per_meal=2.5))
    runtime.set_editor_property("fauna_habitat_patches", patches)
    ASSETS.set_metadata_tag(world, "JYUOwner", "JYU.RiparianHabitat")
    if not u.EditorLoadingAndSavingUtils.save_map(world, DESTINATION):
        raise RuntimeError(f"Could not save {DESTINATION}")
    u.log(f"ECO_RIPARIAN_HABITAT_READY {DESTINATION}")


if __name__ == "__main__":
    main()

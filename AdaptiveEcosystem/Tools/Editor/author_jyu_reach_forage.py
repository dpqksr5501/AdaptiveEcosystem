"""Add shared, edible plants and instanced trees to the owned riparian reach."""

import math
from pathlib import Path
import random
import runpy

import unreal as u


HERE = Path(__file__).parent
FORAGE = runpy.run_path(str(HERE / "author_jyu_herbivore_forage.py"))
ASSETS, ACTORS, LEVELS, set_props, require = (FORAGE[key] for key in ("ASSETS", "ACTORS", "LEVELS", "set_props", "require"))
CANOPY = runpy.run_path(str(HERE / "audit_jyu_riparian_asset_transfer.py"))["CANOPY_MESHES"]
REACH_HEIGHT = runpy.run_path(str(HERE / "author_jyu_riparian_reach.py"))["height"]
MAP = "/Game/JYU/Maps/LV_JYU_RiparianReach"
REGION = "FaunaMeadow"
PREFIX = "RiparianReachForage"
CLIMATE = "JYU Reach Climate"
FLOODPLAIN = "RiparianReachFloodplain"
SITES = (
    ("WestMeadow", "grass", 3060., -4680.), ("WestForbs", "forbs", 3110., -4420.),
    ("WestBrowse", "browse", 3200., -4290.), ("NorthSedges", "wet_meadow", 3820., -4260.),
    ("NorthForbs", "forbs", 4000., -4200.), ("NorthBrowse", "browse", 4190., -4270.),
    ("EastSedges", "wet_meadow", 4610., -4450.), ("EastMeadow", "grass", 4820., -4390.),
    ("SouthBrowse", "browse", 4600., -5340.), ("SouthSedges", "wet_meadow", 3990., -5380.),
    ("ApproachGrass", "grass", 2830., -4220.), ("ApproachForbs", "forbs", 2790., -3970.),
    ("UplandForbs", "forbs", -1845., -1400.), ("ScrubBrowse", "browse", -1220., -2170.),
    ("OpenMeadow", "grass", 1130., -1760.), ("FloodplainApproach", "wet_meadow", 1310., 1070.),
)


def add_canopy(world, rng):
    tools = u.AssetToolsHelpers.get_asset_tools()
    for role, sites, cull in (
        ("broadleaf", ((3110., -5250.), (3280., -5440.), (3570., -5460.), (3970., -5550.),
                       (4480., -5480.), (4840., -5390.), (5100., -5070.), (5080., -4580.)), (3800, 5600)),
        ("birch", ((2940., -5370.), (3090., -5500.), (3480., -5510.), (3720., -5530.), (4220., -5550.),
                   (4770., -5460.), (4990., -5340.), (5190., -4910.), (5000., -4370.), (4720., -4180.)), (4200, 6200)),
    ):
        mesh = require(CANOPY[role])
        folder, name = "/Game/JYU/Riparian", "FT_JYU_Reach_" + role
        path = f"{folder}/{name}"
        foliage = ASSETS.load_asset(path) if ASSETS.does_asset_exist(path) else tools.create_asset(
            name, folder, u.FoliageType_InstancedStaticMesh, u.FoliageType_InstancedStaticMeshFactory())
        if not foliage:
            raise RuntimeError(f"Could not create {path}")
        set_props(foliage, mesh=mesh, cull_distance=u.Int32Interval(*cull), cast_shadow=True)
        if not ASSETS.save_loaded_asset(foliage):
            raise RuntimeError(f"Could not save {path}")
        transforms = []
        bounds = mesh.get_bounding_box()
        for x, y in sites:
            ground = FORAGE["project"](world, x, y)
            if ground is None:
                raise RuntimeError(f"No canopy ground at {x}, {y}")
            scale = rng.uniform(320., 570.) / (bounds.max.z - bounds.min.z)
            transforms.append(u.Transform(location=ground - u.Vector(0., 0., bounds.min.z * scale),
                                          rotation=u.Rotator(yaw=rng.uniform(-180., 180.)), scale=u.Vector(scale, scale, scale)))
        u.InstancedFoliageActor.remove_all_instances(world, foliage)
        u.InstancedFoliageActor.add_instances(world, foliage, transforms)
        u.log(f"ECO_REACH_CANOPY {role} instances={len(transforms)}")


def batch_static_scenery(world):
    groups = {}
    for actor in ACTORS.get_all_level_actors():
        if not isinstance(actor, u.StaticMeshActor):
            continue
        label = actor.get_actor_label()
        if not label.startswith("JYU Reach ") or label.startswith(("JYU Reach Terrain", "JYU Reach floating_leaves ")):
            continue
        component = actor.static_mesh_component
        if component.get_collision_enabled() != u.CollisionEnabled.NO_COLLISION:
            raise RuntimeError(f"Reach scenery participates in collision: {label}")
        mesh = component.get_editor_property("static_mesh")
        groups.setdefault(mesh, []).append(actor)

    tools = u.AssetToolsHelpers.get_asset_tools()
    for mesh, actors in groups.items():
        name = "FT_JYU_ReachDecor_" + mesh.get_name()
        folder = "/Game/JYU/Riparian"
        path = f"{folder}/{name}"
        foliage = ASSETS.load_asset(path) if ASSETS.does_asset_exist(path) else tools.create_asset(
            name, folder, u.FoliageType_InstancedStaticMesh, u.FoliageType_InstancedStaticMeshFactory())
        if not foliage:
            raise RuntimeError(f"Could not create {path}")
        first = actors[0].static_mesh_component
        overrides = [first.get_material(i) for i in range(first.get_num_materials())]
        for actor in actors:
            component = actor.static_mesh_component
            if [component.get_material(i) for i in range(component.get_num_materials())] != overrides:
                raise RuntimeError(f"Scenery has inconsistent material overrides: {mesh.get_name()}")
        set_props(foliage, mesh=mesh, override_materials=overrides, cull_distance=u.Int32Interval(3500, 4800),
                  cast_shadow=True)
        if not ASSETS.save_loaded_asset(foliage):
            raise RuntimeError(f"Could not save {path}")
        u.InstancedFoliageActor.remove_all_instances(world, foliage)
        u.InstancedFoliageActor.add_instances(world, foliage, [a.get_actor_transform() for a in actors])
        for actor in actors:
            if not ACTORS.destroy_actor(actor):
                raise RuntimeError(f"Could not replace {actor.get_actor_label()} with a foliage instance")
        u.log(f"ECO_REACH_DECOR {mesh.get_name()} instances={len(actors)}")

    # The migrated birch log uses a material instance with an explicit usage override.
    # Keep the original Project_J material intact for its other placements.
    path = "/Game/JYU/Riparian/FT_JYU_ReachDecor_SM_WoodenLogs_Birch04"
    foliage = ASSETS.load_asset(path)
    if foliage:
        folder = "/Game/JYU/Riparian"
        source = require("/Game/Map_Resource/SkyTown/Materials/MI_BirchLogs01")
        local_path = folder + "/MI_JYU_ReachBirchLogs"
        material = ASSETS.load_asset(local_path) if ASSETS.does_asset_exist(local_path) else ASSETS.duplicate_asset(
            source.get_path_name().split(".")[0], local_path)
        if not material:
            raise RuntimeError("Could not create the local instanced log material")
        edit = u.MaterialEditingLibrary
        edit.set_material_usage_override(material, u.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES, True, True)
        overrides = list(foliage.get_editor_property("override_materials"))
        for index, override in enumerate(overrides):
            if override == source:
                overrides[index] = material
        foliage.set_editor_property("override_materials", overrides)
        if not ASSETS.save_loaded_asset(material) or not ASSETS.save_loaded_asset(foliage):
            raise RuntimeError("Could not save the local instanced log material")


def main():
    editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
    if editor.get_editor_world().get_name() != MAP.rsplit("/", 1)[-1] and not LEVELS.load_level(MAP):
        raise RuntimeError(f"Could not open {MAP}")
    world = editor.get_editor_world()
    existing = {a.get_actor_label(): a for a in ACTORS.get_all_level_actors()}
    runtime = next(a for a in existing.values() if isinstance(a, u.EcoCreatureIntegrationSpawner))
    guilds, prefs = FORAGE["GUILDS"], FORAGE["PREFERENCES"]
    profiles = list(runtime.get_editor_property("fauna_species"))
    for profile in profiles:
        species = str(profile.get_editor_property("species_id"))
        if species in prefs:
            set_props(profile, plant_preferences=dict(zip(guilds.values(), prefs[species])))
    runtime.set_editor_property("fauna_species", profiles)
    patches = [p for p in runtime.get_editor_property("fauna_habitat_patches")
               if not str(p.get_editor_property("id")).startswith(PREFIX)]
    visual_class, hidden = FORAGE["appearance_assets"]()
    meshes = {role: require(path) for role, path in FORAGE["MESHES"].items()}
    rng = random.Random(76391)
    for site, role, x, y in SITES:
        center = FORAGE["project"](world, x, y)
        if center is None:
            raise RuntimeError(f"No usable ground for {site}")
        thermal, rain, stock, recovery, plant_height = FORAGE["GROWTH"][role]
        moisture, dry_loss, residual = FORAGE["DRY_RESPONSE"][role]
        patch_id = PREFIX + site
        patches.append(set_props(u.EcoFaunaHabitatPatch(), id=patch_id, region_id=REGION, center=center, stage=1,
                                 plant_guild=guilds[role], consumers=list(prefs), capacity=stock,
                                 regrowth_per_second=recovery, energy_per_meal=2.8,
                                 plant_growth_temperature=u.Vector(*thermal), plant_growth_rainfall=u.Vector2D(*rain),
                                 plant_moisture_need=moisture, plant_dry_loss_per_second=dry_loss))
        mesh = meshes[role]
        bounds = mesh.get_bounding_box()
        browse = role == "browse"
        transforms = []
        for i in range(3 if browse else 5):
            angle, radius = rng.uniform(0., math.tau), 0. if i == 0 else rng.uniform(22., 54.)
            point = FORAGE["project"](world, center.x + radius * math.cos(angle), center.y + radius * math.sin(angle))
            if point is None:
                continue
            scale = plant_height * rng.uniform(.86, 1.18) / (bounds.max.z - bounds.min.z)
            transforms.append(u.Transform(location=point - center - u.Vector(0., 0., bounds.min.z * scale),
                                          rotation=u.Rotator(yaw=rng.uniform(-180., 180.)), scale=u.Vector(scale, scale, scale)))
        actor = existing.get(patch_id) or ACTORS.spawn_actor_from_class(visual_class, center)
        actor.set_actor_label(patch_id)
        actor.set_actor_location(center, False, False)
        set_props(actor, patch_id=patch_id, tags=[patch_id], full_plant_transforms=transforms,
                  residual_height_fraction=residual, keep_woody_stems=browse)
        leaves = actor.get_editor_property("plants")
        stems = actor.get_editor_property("woody_stems")
        leaves.set_static_mesh(mesh)
        stems.set_static_mesh(mesh if browse else None)
        leaves.set_material(1, hidden if browse else None)
        stems.set_material(0, hidden if browse else None)
        for component in (leaves, stems):
            component.set_cull_distances(2100, 3300)
            component.set_cast_shadow(browse)
        actor.rebuild_forage_preview()
    runtime.set_editor_property("fauna_habitat_patches", patches)
    center = next(p.get_editor_property("center") for p in patches if str(p.get_editor_property("id")) == FLOODPLAIN)
    mesh = require("/Game/Map_Resource/SkyTown/Meshes/SM_Seaweed02")
    bounds = mesh.get_bounding_box()
    actor = existing.get(FLOODPLAIN) or ACTORS.spawn_actor_from_class(visual_class, center)
    actor.set_actor_label(FLOODPLAIN)
    actor.set_actor_location(center, False, False)
    transforms = []
    # This shelf drains below the seasonal patch. Keep the rooted shoots low
    # enough to fit in the shallow water at the high-water crest.
    for dx, dy in ((-32., 5.), (-19., 0.), (0., -6.), (15., 4.), (38., 5.), (58., 8.)):
        x, y = center.x + dx, center.y + dy
        root = u.Vector(x, y, REACH_HEIGHT(x, y) - .5)
        if not 110. < root.z < 135.:
            raise RuntimeError(f"Seasonal shoot has no suitable shelf at {dx}, {dy}")
        full_height = min(rng.uniform(11., 16.), 140. - root.z)
        scale = full_height / (bounds.max.z - bounds.min.z)
        transforms.append(u.Transform(location=root - center - u.Vector(0., 0., bounds.min.z * scale),
                                      rotation=u.Rotator(yaw=rng.uniform(-180., 180.)), scale=u.Vector(scale, scale, scale)))
    set_props(actor, patch_id=FLOODPLAIN, tags=[FLOODPLAIN], full_plant_transforms=transforms,
              residual_height_fraction=.05, keep_woody_stems=False)
    foliage = actor.get_editor_property("plants")
    foliage.set_static_mesh(mesh)
    foliage.set_cull_distances(2100, 3300)
    foliage.set_cast_shadow(False)
    actor.rebuild_forage_preview()

    climate = existing.get(CLIMATE)
    for other in existing.values():
        if isinstance(other, u.EcoRegionEnvironmentAdapter) and other != climate:
            regions = [str(region) for region in other.get_editor_property("region_ids")]
            if (not regions or REGION in regions) and (other.get_editor_property("cycle_rainfall")
                                                       or other.get_editor_property("apply_authored_weather")):
                raise RuntimeError(f"{other.get_actor_label()} already writes weather for {REGION}")
    climate = climate or ACTORS.spawn_actor_from_class(u.EcoRegionEnvironmentAdapter, u.Vector())
    climate.set_actor_label(CLIMATE)
    set_props(climate, region_ids=[REGION], apply_authored_weather=False, cycle_rainfall=True,
              rain_cycle_seconds=160., dry_rainfall=0., wet_rainfall=.72)
    add_canopy(world, rng)
    batch_static_scenery(world)
    if not u.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError(f"Could not save {MAP}")
    u.log(f"ECO_REACH_FORAGE_READY patches={len(SITES)}")


if __name__ == "__main__":
    try:
        main()
    finally:
        u.SystemLibrary.quit_editor()

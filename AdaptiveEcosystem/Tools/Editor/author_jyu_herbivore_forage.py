"""Author visible, shared forage in an owned copy of the Project_J riparian map."""

import math
from pathlib import Path
import random
import runpy

import unreal as u


HERE = Path(__file__).parent
MESHES = runpy.run_path(str(HERE / "audit_jyu_riparian_asset_transfer.py"))["FORAGE_MESHES"]
BASE = runpy.run_path(str(HERE / "setup_jyu_fauna.py"))
ASSETS, ACTORS, set_props, require = (BASE[key] for key in ("ASSETS", "ACTORS", "set_props", "require"))
LEVELS = u.get_editor_subsystem(u.LevelEditorSubsystem)
SOURCE = "/Game/JYU/Maps/LV_JYU_RiparianProjectJ"
MAP = "/Game/JYU/Maps/LV_JYU_HerbivoreForage"
REGION = "FaunaMeadow"
PREFIX = "JYU Forage "
FOLDER = "/Game/JYU/Forage"
CLIMATE_LABEL = "JYU Forage Climate"
GUILDS = dict(grass=u.EcoFaunaPlantGuild.GRASS, forbs=u.EcoFaunaPlantGuild.FORBS,
              browse=u.EcoFaunaPlantGuild.BROWSE, wet_meadow=u.EcoFaunaPlantGuild.WET_MEADOW)
PREFERENCES = {
    "Horse": (1.45, .88, .68, 1.16),
    "Bighorn": (1.15, 1.40, 1.06, .91),
    "Jackrabbit": (.91, 1.29, 1.45, .88),
    "Buffalo": (1.18, 1.08, .79, 1.40),
}
GROWTH = {
    # Air temperature min/optimum/max, rain multipliers, capacity, recovery, plant height.
    "grass": ((2., 19., 38.), (.48, 1.14), 12., .17, 28.),
    "forbs": ((5., 17., 33.), (.22, 1.27), 9., .15, 40.),
    "browse": ((-3., 21., 43.), (.75, 1.10), 10., .12, 62.),
    "wet_meadow": ((2., 17., 36.), (.28, 1.36), 13., .18, 50.),
}
# Moisture need, dry biomass loss per simulated second, and residual height.
DRY_RESPONSE = {
    "grass": (.30, .16, .22),
    "forbs": (.43, .22, .12),
    "browse": (.25, .10, .20),
    "wet_meadow": (.54, .24, .30),
}
SITES = (
    ("HillsideForbs", "forbs", -1845., -1400.), ("HillsideGrass", "grass", -2040., -1480.),
    ("HillsideBrowse", "browse", -2110., -1650.),
    ("ScrubBrowse", "browse", -1220., -2170.), ("ScrubForbs", "forbs", -1040., -2220.),
    ("ScrubGrass", "grass", -1395., -2325.),
    ("MeadowGrass", "grass", 1130., -1760.), ("MeadowForbs", "forbs", 1285., -1850.),
    ("MeadowBrowse", "browse", 1500., -2010.), ("MeadowWetGrass", "wet_meadow", 1610., -1815.),
    ("FloodplainWetGrass", "wet_meadow", 1310., 1070.), ("FloodplainGrass", "grass", 1440., 1090.),
    ("FloodplainForbs", "forbs", 1580., 1170.),
    ("BankWetGrass", "wet_meadow", 3140., -4495.), ("BankForbs", "forbs", 3070., -4350.),
)


def project(world, x, y):
    for dx, dy in ((0., 0.), (40., 0.), (-40., 0.), (0., 45.), (0., -45.)):
        point = u.EcoCreatureAnimationBuilder.project_placement_point(world, u.Vector(x + dx, y + dy, 260.))
        if point is not None:
            return point
    return None


def appearance_assets():
    tools = u.AssetToolsHelpers.get_asset_tools()
    name = "BP_JYU_ForagePatchVisual"
    blueprint = ASSETS.load_asset(f"{FOLDER}/{name}") if ASSETS.does_asset_exist(f"{FOLDER}/{name}") else None
    if blueprint is None:
        factory = set_props(u.BlueprintFactory(), parent_class=u.EcoForagePatchVisual)
        blueprint = tools.create_asset(name, FOLDER, u.Blueprint, factory)
        if not blueprint or not ASSETS.save_loaded_asset(blueprint):
            raise RuntimeError("Cannot create the forage visual Blueprint")
    name = "M_JYU_ForageHiddenLayer"
    hidden = ASSETS.load_asset(f"{FOLDER}/{name}") if ASSETS.does_asset_exist(f"{FOLDER}/{name}") else None
    created = hidden is None
    edit = u.MaterialEditingLibrary
    if created:
        hidden = tools.create_asset(name, FOLDER, u.Material, u.MaterialFactoryNew())
        set_props(hidden, blend_mode=u.BlendMode.BLEND_MASKED)
        zero = set_props(edit.create_material_expression(hidden, u.MaterialExpressionConstant, -200, 0), r=0.)
        if not edit.connect_material_property(zero, "", u.MaterialProperty.MP_OPACITY_MASK):
            raise RuntimeError("Cannot mask the inactive shrub material slot")
    if created or not hidden.get_editor_property("used_with_instanced_static_meshes"):
        edit.set_material_usage(hidden, u.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)
        edit.recompile_material(hidden)
        if not ASSETS.save_loaded_asset(hidden):
            raise RuntimeError("Cannot save the shrub layer material")
    return BASE["generated"](blueprint), hidden


def main():
    if not ASSETS.does_asset_exist(MAP) and not ASSETS.duplicate_asset(SOURCE, MAP):
        raise RuntimeError(f"Could not duplicate {SOURCE}")
    if not LEVELS.load_level(MAP):
        raise RuntimeError(f"Could not open {MAP}")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    existing = {a.get_actor_label(): a for a in ACTORS.get_all_level_actors()}
    runtime = next(a for a in existing.values() if isinstance(a, u.EcoCreatureIntegrationSpawner))
    meshes = {role: require(path) for role, path in MESHES.items()}
    visual_class, hidden = appearance_assets()
    shrub_slots = meshes["browse"].get_editor_property("static_materials")
    if len(shrub_slots) != 2 or "Vegetation" not in shrub_slots[0].material_interface.get_name() or "Bark" not in shrub_slots[1].material_interface.get_name():
        raise RuntimeError("Browse mesh leaf and bark slot layout changed")
    if runtime.get_editor_property("fauna_habitat_stage") < 1:
        raise RuntimeError("Forage requires the owned habitat runtime")
    profiles = list(runtime.get_editor_property("fauna_species"))
    found = set()
    for profile in profiles:
        species = str(profile.get_editor_property("species_id"))
        if species in PREFERENCES:
            set_props(profile, plant_preferences=dict(zip(GUILDS.values(), PREFERENCES[species])))
            found.add(species)
    if found != set(PREFERENCES):
        raise RuntimeError(f"Missing ground forage profiles: {set(PREFERENCES) - found}")
    runtime.set_editor_property("fauna_species", profiles)
    previous = {str(p.get_editor_property("id")): p for p in runtime.get_editor_property("fauna_habitat_patches")}
    patches = [patch for patch_id, patch in previous.items() if not patch_id.startswith("HerbForage")]
    rng = random.Random(41729)
    for site, role, x, y in SITES:
        patch_id = "HerbForage" + site
        old_patch = previous.get(patch_id)
        center = old_patch.get_editor_property("center") if old_patch else project(world, x, y)
        if center is None:
            raise RuntimeError(f"No navigable ground for {site}")
        thermal, rain, stock, recovery, plant_height = GROWTH[role]
        moisture, dry_loss, residual = DRY_RESPONSE[role]
        patches.append(set_props(u.EcoFaunaHabitatPatch(), id=patch_id, region_id=REGION, center=center,
                                 stage=1, plant_guild=GUILDS[role], consumers=list(PREFERENCES),
                                 capacity=stock, regrowth_per_second=recovery, energy_per_meal=2.8,
                                 plant_growth_temperature=u.Vector(*thermal), plant_growth_rainfall=u.Vector2D(*rain),
                                 plant_moisture_need=moisture, plant_dry_loss_per_second=dry_loss))
        mesh = meshes[role]
        bounds = mesh.get_bounding_box()
        label = PREFIX + "Patch " + site
        actor = existing.get(label)
        transforms = []
        for i in range(4 if role != "browse" else 2):
            angle, radius = rng.uniform(0., math.tau), 0. if i == 0 else rng.uniform(17., 52.)
            scale = plant_height * rng.uniform(.85, 1.15) / (bounds.max.z - bounds.min.z)
            rotation = u.Rotator(yaw=rng.uniform(-180., 180.))
            if actor:
                continue
            legacy = existing.get(PREFIX + site + f" {i:02}")
            if legacy:
                location = legacy.get_actor_location()
                rotation = legacy.get_actor_rotation()
                size = legacy.get_actor_scale3d()
            else:
                ground = project(world, center.x + radius * math.cos(angle), center.y + radius * math.sin(angle))
                if ground is None:
                    continue
                location = ground - u.Vector(0., 0., bounds.min.z * scale)
                size = u.Vector(scale, scale, scale)
            transform = u.Transform(location=location - center, rotation=rotation, scale=size)
            transforms.append(transform)
        if actor:
            transforms = list(actor.get_editor_property("full_plant_transforms"))
        if not transforms:
            raise RuntimeError(f"No visual planting transforms for {site}")
        actor = actor or ACTORS.spawn_actor_from_class(visual_class, center)
        if not isinstance(actor, u.EcoForagePatchVisual):
            raise RuntimeError(f"Unexpected actor for {label}")
        actor.set_actor_label(label)
        actor.set_actor_location(center, False, False)
        browse = role == "browse"
        set_props(actor, patch_id=patch_id, tags=[patch_id], full_plant_transforms=transforms,
                  residual_height_fraction=residual, keep_woody_stems=browse)
        leaves = actor.get_editor_property("plants")
        stems = actor.get_editor_property("woody_stems")
        leaves.set_static_mesh(mesh)
        stems.set_static_mesh(mesh if browse else None)
        leaves.set_material(1, hidden if browse else None)
        stems.set_material(0, hidden if browse else None)
        actor.rebuild_forage_preview()
    for label, actor in existing.items():
        if label.startswith(PREFIX) and isinstance(actor, u.StaticMeshActor):
            ACTORS.destroy_actor(actor)
    climate = existing.get(CLIMATE_LABEL)
    for other in existing.values():
        if not isinstance(other, u.EcoRegionEnvironmentAdapter) or other == climate:
            continue
        regions = [str(region) for region in other.get_editor_property("region_ids")]
        if ((not regions or REGION in regions)
                and (other.get_editor_property("cycle_rainfall") or other.get_editor_property("apply_authored_weather"))):
            raise RuntimeError(f"{other.get_actor_label()} already writes weather for {REGION}")
    if climate is None:
        climate = ACTORS.spawn_actor_from_class(u.EcoRegionEnvironmentAdapter, u.Vector())
    climate.set_actor_label(CLIMATE_LABEL)
    set_props(climate, region_ids=[REGION], apply_authored_weather=False, cycle_rainfall=True,
              rain_cycle_seconds=160., dry_rainfall=0., wet_rainfall=.72)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    ASSETS.set_metadata_tag(world, "JYUOwner", "JYU.HerbivoreForage")
    if not u.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError(f"Could not save {MAP}")
    u.log(f"ECO_HERBIVORE_FORAGE_READY {MAP} sites={len(SITES)}")


if __name__ == "__main__":
    main()

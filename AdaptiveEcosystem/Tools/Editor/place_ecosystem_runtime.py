"""Author opt-in runtime actors in the team's map; preserve terrain, foliage and source targets.

Run from the Editor Python console after loading all map cells. Re-running updates
only actors bearing our ownership tag and matching label. A complete geometry
preflight happens before changes. Review the manifest and restart PIE after edits.
"""
import json
import math
import os
import unreal

MAP = "/Game/Map/LV_Ecosystem_IntegrationTest"
ROOT = "/Game/Creatures/Integrated/"
TAG = "EcoProductionPlacementV1"
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
WORLD = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
if not WORLD.get_path_name().startswith(MAP + "."):
    raise RuntimeError("Open the authored integration map and load its cells first")
ALL = ACTORS.get_all_level_actors()


def named(label, cls=None):
    found = [a for a in ALL if a.get_actor_label() == label]
    if len(found) != 1 or (cls and not isinstance(found[0], cls)):
        raise RuntimeError("Expected one authored " + label)
    return found[0]


def ground(x, y, z=0):
    result = unreal.EcoCreatureLevelLibrary.probe_ground(WORLD, unreal.Vector(x, y, z))
    if not result.valid:
        raise RuntimeError("No safe ground: " + str((x, y, z)))
    return result.position


def xyz(v):
    return [v.x, v.y, v.z]


def owned(label, cls, point, folder):
    matches = [a for a in ALL if a.get_actor_label() == label]
    if matches:
        if len(matches) != 1 or TAG not in [str(t) for t in matches[0].tags] or not isinstance(matches[0], cls):
            raise RuntimeError("Refusing to overwrite unrelated actor: " + label)
        actor = matches[0]
        actor.modify()
        actor.set_actor_location(point, False, False)
    else:
        actor = ACTORS.spawn_actor_from_class(cls, point)
        actor.set_actor_label(label)
        actor.set_editor_property("tags", [unreal.Name(TAG)])
        ALL.append(actor)
    # Logic, shelter leases and exclusion metadata must survive camera streaming.
    actor.set_editor_property("is_spatially_loaded", False)
    actor.set_folder_path("EcologyRuntime/" + folder)
    return actor


specs = [
    {"id": "Forest", "food": 1400.0, "capacity": 2000.0, "temperature": 20.0, "humidity": 0.7,
     "neighbors": ["Barren"], "arrival": (34000, 30000), "patch": (34200, 46500),
     "deer": [(33700,45400),(34000,45600),(34400,45600),(34700,45400),(33700,45900),(34100,46100),(34500,46000),(34800,45800)],
     "wolves": [(35100,47100)]},
    {"id": "Barren", "food": 500.0, "capacity": 1000.0, "temperature": 30.0, "humidity": 0.2,
     "neighbors": ["Forest", "Highland"], "arrival": (34000,20000), "patch": (34000,1000),
     "deer": [(33400,0),(34000,0),(34600,0),(34000,600)], "wolves": [(35000,2500)]},
    {"id": "Highland", "food": 600.0, "capacity": 1200.0, "temperature": -5.0, "humidity": 0.4,
     "neighbors": ["Barren"], "arrival": (34000,-30000), "patch": (34000,-49000),
     "deer": [(33400,-50000),(34000,-50000),(34600,-50000),(34000,-49400)], "wolves": [(35000,-47500)]},
]
if any(isinstance(a, unreal.EcoMassNetworkBootstrap) for a in ALL):
    raise RuntimeError("M3 bootstrap cannot share this coordinator")
foreign = [a for a in ALL if isinstance(a, unreal.EcoCreatureIntegrationSpawner) and TAG not in [str(t) for t in a.tags]]
if foreign:
    raise RuntimeError("An unrelated creature coordinator already exists")
for spec in specs:
    trigger = named("TV_Region_" + spec["id"], unreal.TriggerBox)
    spec["bounds"] = trigger.get_actor_bounds(False)
    spec["arrival_ground"] = ground(*spec["arrival"])
    spec["patch_ground"] = ground(*spec["patch"])
    spec["deer_ground"] = [ground(*p) for p in spec["deer"]]
    spec["wolf_ground"] = [ground(*p) for p in spec["wolves"]]
    center, extent = spec["bounds"]
    for point in [spec["arrival_ground"], spec["patch_ground"]] + spec["deer_ground"] + spec["wolf_ground"]:
        if any(abs(p-c) >= e-1 for p,c,e in zip(xyz(point), xyz(center), xyz(extent))):
            raise RuntimeError("Placement outside authored region " + spec["id"])

# These two explicitly authored refuges sit inside the existing shrub patch.
# Keep the team's TP as the reference; no procedural cover generation or fake wall.
source_shelter = named("TP_Shelter_Forest_01", unreal.TargetPoint)
refuges = [("Eco_Shelter_Forest_01", (33300,45100)), ("Eco_Shelter_Forest_02", (34200,44400))]
shelter_points = []
for label, xy in refuges:
    point = ground(*xy)
    for i in range(4):
        slot = ground(point.x + math.cos(i*math.pi/2)*150, point.y + math.sin(i*math.pi/2)*150, point.z)
        # Current Social slots are a horizontal ring. Reject unsuitable steep authoring.
        if abs(slot.z-point.z) > 35:
            raise RuntimeError("Shelter ring needs flatter ground: " + label)
    shelter_points.append((label, point))

deer_bp = unreal.load_class(None, ROOT + "BP_EcoDeer.BP_EcoDeer_C")
wolf_bp = unreal.load_class(None, ROOT + "BP_EcoWolf.BP_EcoWolf_C")
deer_config = unreal.load_asset(ROOT + "DA_EcoDeer")
wolf_config = unreal.load_asset(ROOT + "DA_EcoWolf")
if not all((deer_bp, wolf_bp, deer_config, wolf_config)):
    raise RuntimeError("Missing tested creature assets")
observer = named("PlayerStart", unreal.PlayerStart)

with unreal.ScopedEditorTransaction("생태계 지역·은신처·동물 런타임 배치"):
    groups = []
    for spec in specs:
        center, extent = spec["bounds"]
        region = owned("Eco_Region_" + spec["id"], unreal.EcologyRegion, center, "Regions")
        region.region_bounds.set_box_extent(extent)
        region.set_editor_property("region_id", spec["id"])
        region.set_editor_property("adjacent_region_ids", spec["neighbors"])
        region.set_editor_property("arrival_offset", spec["arrival_ground"] - center)
        region.set_editor_property("initial_food_amount", spec["food"])
        region.set_editor_property("food_capacity", spec["capacity"])
        environment = region.get_editor_property("environment_state")
        environment.set_editor_property("temperature", spec["temperature"])
        environment.set_editor_property("humidity", spec["humidity"])
        environment.set_editor_property("rainfall", 0.0)
        region.set_editor_property("environment_state", environment)
        group = unreal.EcoCreatureSpawnGroup()
        group.set_editor_property("region_id", spec["id"])
        group.set_editor_property("herbivores", len(spec["deer_ground"]))
        group.set_editor_property("wolves", len(spec["wolf_ground"]))
        group.set_editor_property("herbivore_spawn_points", spec["deer_ground"])
        group.set_editor_property("wolf_spawn_points", spec["wolf_ground"])
        group.set_editor_property("use_food_patch_position", True)
        group.set_editor_property("food_patch_position", spec["patch_ground"])
        groups.append(group)
        food_hint = owned("Eco_FoodHint_" + spec["id"], unreal.TargetPoint, spec["patch_ground"], "ResourceHints")
    for label, point in shelter_points:
        shelter = owned(label, unreal.EcoShelterAnchor, point, "Shelters")
        shelter.set_editor_property("capacity", 4)
        shelter.set_editor_property("radius", 150.0)
        shelter.set_editor_property("quality", 0.65)
        shelter.set_actor_rotation(unreal.Rotator(pitch=0, yaw=-90, roll=0), False)
    spawner = owned("Eco_CreatureRuntime", unreal.EcoCreatureIntegrationSpawner, unreal.Vector(), "Coordinator")
    spawner.set_editor_property("herbivore_config", deer_config)
    spawner.set_editor_property("wolf_config", wolf_config)
    spawner.set_editor_property("herbivore_actor_class", deer_bp)
    spawner.set_editor_property("wolf_actor_class", wolf_bp)
    spawner.set_editor_property("groups", groups)
    spawner.set_editor_property("enable_waves", False)
    spawner.set_editor_property("global_population_limit", 64)
    spawner.set_editor_property("use_habitat_streaming", True)
    spawner.set_editor_property("habitat_streaming_radius", 10000.0)
    spawner.set_editor_property("day_seconds", 60.0)
    spawner.set_editor_property("night_seconds", 60.0)
    WORLD.get_world_settings().set_editor_property("default_game_mode", unreal.EcoCreatureIntegrationGameMode)
    # Keep the observer inside the existing 50m replication bubble at initial spawn.
    observer.modify()
    observer.set_editor_property("is_spatially_loaded", False)
    observer.set_actor_location(unreal.Vector(34200, 48500, -600), False, False)
    observer.set_actor_rotation(unreal.Rotator(pitch=-25, yaw=-90, roll=0), False)
    # Existing water exclusions must remain available to the authority's direct writer.
    for actor in ALL:
        if isinstance(actor, unreal.NavModifierVolume) and actor.get_editor_property("area_class") == unreal.NavArea_Null.static_class():
            actor.set_editor_property("is_spatially_loaded", False)
if not unreal.EditorLevelLibrary.save_current_level():
    raise RuntimeError("Failed to save map/external actors")
manifest = {"map": MAP, "tag": TAG, "initial_agents": 19, "regions": [], "shelters": [],
            "observer_position": xyz(observer.get_actor_location()),
            "original_shelter_target": source_shelter.get_actor_label(), "water_targets": [a.get_actor_label() for a in ALL if a.get_actor_label().startswith("TP_Water_")]}
for spec in specs:
    manifest["regions"].append({"id": spec["id"], "bounds_center": xyz(spec["bounds"][0]), "bounds_extent": xyz(spec["bounds"][1]),
        "arrival": xyz(spec["arrival_ground"]), "food_patch": xyz(spec["patch_ground"]),
        "herbivores": [xyz(p) for p in spec["deer_ground"]], "wolves": [xyz(p) for p in spec["wolf_ground"]]})
for label, point in shelter_points:
    manifest["shelters"].append({"label": label, "position": xyz(point), "capacity": 4, "radius": 150, "quality": 0.65})
path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "EcosystemRuntimePlacement.json")
with open(path, "w", encoding="utf-8") as stream:
    json.dump(manifest, stream, ensure_ascii=False, indent=2)
unreal.log("ECOSYSTEM_RUNTIME_PLACEMENT_OK " + path)
# Put the editor camera near the authored shrub patch.
unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(
    unreal.Vector(34200, 41000, 800), unreal.Rotator(pitch=-25, yaw=90, roll=0))

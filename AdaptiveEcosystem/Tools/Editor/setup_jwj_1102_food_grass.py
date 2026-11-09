"""Survey the existing JWJ level; pass -JWJFoodGrassApply to save the selected setup."""
import json
import math
from pathlib import Path

import unreal as u


MAP = "/Game/JWJ/1102_Integration_JWJ"
SOURCE = "JWJ_WildlifeTest"
MEADOW = "JWJ_HuntingMeadow"
FIELD = "/Game/JYU/Ecosystem/BP_JYU_VegetationField"
OWNER = "JWJ.FoodGrass.20261108"
APPLY = "-JWJFoodGrassApply" in u.SystemLibrary.get_command_line().split()
OUT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / "JWJFoodGrass_20261108"
OUT.mkdir(parents=True, exist_ok=True)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
actor_service = u.get_editor_subsystem(u.EditorActorSubsystem)


def coordinates(point):
    return [point.x, point.y, point.z]


def ground(point):
    result = u.EcoCreatureAnimationBuilder.project_placement_point(world, point)
    if isinstance(result, tuple):
        result = next((value for value in result if isinstance(value, u.Vector)), None) if result[0] else None
    return result if isinstance(result, u.Vector) else None


def route_points(start, end):
    distance = math.hypot(end.x - start.x, end.y - start.y)
    steps = math.ceil((distance - 8000) / 250)
    if steps < 1:
        return []
    points = []
    for index in range(steps + 1):
        fraction = (4000 + (distance - 8000) * index / steps) / distance
        point = ground(start + (end - start) * fraction)
        if point is None or (points and abs(point.z - points[-1].z) > 100):
            return []
        points.append(point)
    return points


def spawn(cls, label, point):
    actor = actor_service.spawn_actor_from_class(cls, point)
    if actor is None:
        raise RuntimeError("Actor creation failed: " + label)
    actor.set_actor_label(label)
    actor.set_editor_property("tags", [OWNER])
    actor.set_editor_property("is_spatially_loaded", False)
    return actor


if not levels.load_level(MAP):
    raise RuntimeError("Existing 1102 level could not be loaded")
world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
if world.get_path_name() != MAP + ".1102_Integration_JWJ":
    raise RuntimeError("Unexpected level")
if not u.EcoCreatureAnimationBuilder.prepare_copied_world(world):
    raise RuntimeError("1102 partition could not be prepared")
actors = actor_service.get_all_level_actors()
runtimes = [actor for actor in actors if isinstance(actor, u.EcoCreatureIntegrationSpawner)]
assert len(runtimes) == 1, "Expected one existing runtime"
runtime = runtimes[0]
assert runtime.get_editor_property("use_v3_policy"), "Existing Native runtime required"
groups = list(runtime.get_editor_property("groups"))
group_ids = [str(group.get_editor_property("region_id")) for group in groups]
regions = {str(actor.region_id): actor for actor in actors if isinstance(actor, u.EcologyRegion)}
assert len(regions) == sum(isinstance(actor, u.EcologyRegion) for actor in actors), "Duplicate RegionId"
assert SOURCE in regions and len(regions) <= 4 and set(group_ids) == set(regions)
assert len(group_ids) == len(regions), "Expected one spawn group per existing region"
routes = [actor for actor in actors if isinstance(actor, u.EcoHerdMigrationRoute)]
habitats = [actor for actor in actors if isinstance(actor, u.EcoVegetationHabitat)]
field_class = u.EditorAssetLibrary.load_blueprint_class(FIELD)
assert field_class, "Missing JYU Field class"
cdo = u.get_default_object(field_class)
field_settings = {key: str(cdo.get_editor_property(key)) for key in (
    "patch_mesh", "patch_material", "patch_width_cm", "patch_height_cm", "detail_radius_cm", "candidates_per_cell")}
assert "GrassA" in field_settings["patch_mesh"] and "MI_JYU_EcosystemGrass" in field_settings["patch_material"]

source = regions[SOURCE]
origin = source.get_actor_location()
centers = {name: actor.get_actor_location() for name, actor in regions.items()}
new_regions = {}
new_routes = {}
surveys = {}
existing_pairs = {frozenset((str(route.from_region), str(route.to_region))) for route in routes
                  if route.is_valid_route() and route.get_editor_property("enabled")
                  and route.get_editor_property("bidirectional")}
candidate_sites = (
    (MEADOW, 15000, 0),
    ("JWJ_SouthRange", 0, -15000),
    ("JWJ_WestRange", -15000, 0),
    ("JWJ_NorthRange", 0, 15000),
    ("JWJ_SouthwestRange", -15000, -15000),
    ("JWJ_SoutheastRange", 15000, -15000),
)
for name, dx, dy in candidate_sites:
    if len(centers) == 4:
        break
    if name in centers:
        continue
    site = ground(origin + u.Vector(dx, dy, 0))
    if site is None or any(abs(site.x - point.x) < 12400 and abs(site.y - point.y) < 12400
                           for point in centers.values()):
        surveys[name] = "missing ground or overlapping bounds"
        continue
    samples = [ground(site + u.Vector(x, y, 0)) for x in range(-6000, 6001, 2000)
               for y in range(-6000, 6001, 2000)]
    if any(point is None or abs(point.z - site.z) > 2000 for point in samples):
        surveys[name] = "ground samples exceed region vertical bounds"
        continue
    points = route_points(origin, site)
    if not points:
        surveys[name] = "no continuous direct corridor"
        continue
    surveys[name] = {"ground_samples": len(samples), "route_samples": len(points)}
    centers[name] = new_regions[name] = site
    new_routes[name] = points

for name, center in centers.items():
    if name == SOURCE or name in new_routes or frozenset((SOURCE, name)) in existing_pairs:
        continue
    points = route_points(origin, center)
    if points:
        new_routes[name] = points

report = {
    "map": MAP, "mode": "apply" if APPLY else "survey", "field": FIELD, "field_settings": field_settings,
    "existing_field": str(runtime.get_editor_property("vegetation_field_class")),
    "existing_regions": {name: coordinates(actor.get_actor_location()) for name, actor in regions.items()},
    "existing_routes": [route.get_actor_label() for route in routes],
    "groups": {str(group.get_editor_property("region_id")): [group.get_editor_property("herbivores"),
               group.get_editor_property("wolves")] for group in groups},
    "proposed_regions": {name: coordinates(point) for name, point in new_regions.items()},
    "proposed_routes": {name: [coordinates(point) for point in points] for name, points in new_routes.items()},
    "surveys": surveys, "saved": False,
}
report_path = OUT / ("Apply.json" if APPLY else "Survey.json")
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
assert len(centers) == 4, "Four terrain-checked regions required"
assert all(name == SOURCE or name in new_routes or frozenset((SOURCE, name)) in existing_pairs
           for name in centers), "Each region needs a validated route to the source"

if APPLY:
    for name, site in new_regions.items():
        actor = spawn(u.EcologyRegion, name, site)
        actor.set_editor_property("region_id", name)
        actor.region_bounds.set_box_extent(u.Vector(6200, 6200, 2500), False)
        actor.set_editor_property("environment_state", source.get_editor_property("environment_state"))
        regions[name] = actor
        group = u.EcoCreatureSpawnGroup()
        for key, value in {"region_id": name, "herbivores": 8, "wolves": 1,
                           "use_food_patch_position": True, "food_patch_position": site}.items():
            group.set_editor_property(key, value)
        groups.append(group)

    for name, points in new_routes.items():
        route = spawn(u.EcoHerdMigrationRoute, "JWJ_Route_" + name, points[0])
        for key, value in {"from_region": SOURCE, "to_region": name, "points": points,
                           "bidirectional": True, "shares_habitat_reports": True}.items():
            route.set_editor_property(key, value)
        assert route.is_valid_route(), "Invalid route: " + name

    grass_class = u.EditorAssetLibrary.load_blueprint_class("/Game/JYU/Ecosystem/BP_JYU_GrassHabitat")
    assert grass_class, "Missing JYU grass soil preset"
    for name, region in regions.items():
        current = set(map(str, region.get_editor_property("adjacent_region_ids")))
        wanted = set(current)
        wanted.update((set(regions) - {SOURCE}) if name == SOURCE else {SOURCE})
        if wanted != current:
            region.modify()
            region.set_editor_property("adjacent_region_ids", sorted(wanted))
        if any(str(actor.get_editor_property("region_id")) == name and actor.is_valid_habitat()
               for actor in habitats):
            continue
        habitat = spawn(grass_class, "JWJ_Grass_" + name, centers[name])
        habitat.set_editor_property("region_id", name)
        extent = region.region_bounds.get_unscaled_box_extent()
        habitat.get_editor_property("bounds").set_box_extent(extent, False)
        assert habitat.is_valid_habitat(), "Invalid soil preset: " + name

    settings = {"groups": groups, "enable_vegetation": True,
                "vegetation_field_class": field_class, "enable_herd_journeys": True}
    runtime.modify()
    for key, value in settings.items():
        runtime.set_editor_property(key, value)
    assert levels.save_current_level(), "1102 level save failed"
    report["saved"] = True
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
u.log("JWJ_FOOD_GRASS_" + ("SAVED" if APPLY else "SURVEY_READY"))

"""Sample the same owned map with and without expanded fauna, without saving edits."""

import json
from pathlib import Path
import re
import time

import unreal


MAP = "/Game/JYU/Maps/LV_JYU_ExpandedFauna"
REGIONAL_MAP = "/Game/JYU/Maps/LV_JYU_ExpandedWaterPassage"
NEW = {"Bighorn", "Jackrabbit", "Horse", "Mink", "GoldenEagle", "AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
command = unreal.SystemLibrary.get_command_line()
pig_followup = "-EcoPigFollowup" in command
pig_network = "-EcoPigNetwork" in command
pig_threat = "-EcoPigThreat" in command
pig_thermal = re.search(r"-EcoPigThermal=(Cool|Dry|Wet)", command)
pig_thermal = pig_thermal.group(1) if pig_thermal else None
pig_capture = pig_thermal and "-EcoPigThermalCapture" in command
if pig_followup or pig_thermal or pig_network or pig_threat:
    MAP = "/Game/JYU/Maps/LV_JYU_Pig"
    NEW = {"Pig"}
mode = "Baseline" if "-EcoExpandedBaseline" in command else "Expanded"
run = re.search(r"-EcoExpandedRun=([A-Za-z0-9_]+)", command)
duration = re.search(r"-EcoExpandedDuration=(\d+)", command)
seconds = int(duration.group(1)) if duration else 420
checkpoint = re.search(r"-EcoExpandedCheckpoint=(Save|Load)", command)
checkpoint = checkpoint.group(1) if checkpoint else None
crest = re.search(r"-EcoExpandedExpectCrest=(Dynamic|Closed)", command)
crest = crest.group(1) if crest else None
output = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "ExpandedFaunaImport"
output.mkdir(parents=True, exist_ok=True)
name = run.group(1) if run else mode
water_audio = "-EcoExpandedWaterAudio" in command
mink_cover = re.search(r"-EcoExpandedMinkCover=(Clear|Screen|Vegetation)", command)
mink_cover = mink_cover.group(1) if mink_cover else None
mink_low_demand = "-EcoExpandedMinkLowDemand" in command
food_intent = re.search(r"-EcoExpandedFoodIntent=(Alternate|Occluded|Expired)", command)
food_intent = food_intent.group(1) if food_intent else None
eagle_fatigue = re.search(r"-EcoExpandedFlightFatigue=(Normal|Rapid)", command)
eagle_fatigue = eagle_fatigue.group(1) if eagle_fatigue else None
floating_fixture = "-EcoExpandedFloatingFixture" in command
rain_fixture = "-EcoExpandedRainWater" in command
seasonal_stock = "-EcoExpandedAuditSeasonalStock" in command
seasonal_feeding = "-EcoExpandedSeasonalFeeding" in command
projectj_riparian = "-EcoExpandedRiparianProjectJ" in command
forage_case = re.search(r"-EcoExpandedForage=(Natural|Choice|Depleted|WeatherCycle)", command)
forage_case = forage_case.group(1) if forage_case else None
weather_forage_sites = ("HerbForageBankWetGrass", "HerbForageBankForbs", "HerbForageHillsideBrowse")
forage_network = "-EcoExpandedForageNetwork" in command
pie_network = forage_network or pig_network
forage_weather_change = 28. if forage_network else 40.
capture_forage = "-EcoExpandedCaptureForage" in command
audit_riparian = "-EcoExpandedAuditRiparian" in command or projectj_riparian
capture_riparian = "-EcoExpandedCaptureRiparian" in command
capture_riparian_detail = "-EcoExpandedCaptureRiparianDetail" in command
riparian_feeding = "-EcoExpandedRiparianFeeding" in command
if seasonal_stock:
    MAP = "/Game/JYU/Maps/LV_JYU_SeasonalWaterFood"
if audit_riparian:
    MAP = "/Game/JYU/Maps/LV_JYU_RiparianProjectJ" if projectj_riparian else "/Game/JYU/Maps/LV_JYU_RiparianHabitat"
if forage_case:
    MAP = "/Game/JYU/Maps/LV_JYU_HerbivoreForage"
    NEW.add("Buffalo")
static_water = "-EcoExpandedStaticWater" in command
regional_water = re.search(r"-EcoExpandedRegionalWater=(Open|Closed|Closing)", command)
regional_water = regional_water.group(1) if regional_water else None
regional_species = re.search(r"-EcoExpandedRegionalSpecies=([A-Za-z]+)", command)
regional_species = regional_species.group(1) if regional_species else "AriakeCatfish"
regional_food_patch = {"AriakeCatfish": "ExpandedWaterConnectedShelf", "CommonCarp": "ExpandedWaterMacrophyteEdge",
                       "UnidentifiedFish": "ExpandedWaterLittoralNursery"}[regional_species]
regional_suffix = "" if regional_species == "AriakeCatfish" else f"_{regional_species}"
regional_slot = ("JYU_ExpandedWaterAudit_SmallFish" if regional_species == "UnidentifiedFish"
                 else f"JYU_ExpandedFauna_RegionalWaterAudit{regional_suffix}")
author_regional_weather = "-EcoExpandedAuthorRegionalWater" in command
if author_regional_weather:
    regional_water = "Rain"
nest = re.search(r"-EcoExpandedNestFixture=(Supported|NoSite|Return)", command)
nest = nest.group(1) if nest else None
slot = ("JYU_PigFollowupAudit" if pig_followup else "JYU_HerbivoreForageAudit" if forage_case else "JYU_SeasonalWaterFoodAudit" if seasonal_stock else "JYU_ExpandedFauna_NestAudit" if nest else regional_slot if regional_water
        else "JYU_ExpandedFauna_Audit")
editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)


def kind(profile):
    return str(profile.get_editor_property("species_id"))


def authority_details(inspection, world, ids):
    result = {}
    for stable_id in ids:
        value = inspection.capture_agent(world, stable_id)
        if isinstance(value, tuple):
            value = value[-1]
        if isinstance(value, str) and value:
            row = json.loads(value)
            if row.get("species") in NEW:
                result[str(stable_id)] = row
    return result


def inspect_seasonal_stock(runtime):
    stock = runtime.inspect_fauna_habitat_stock("ExpandedWaterSeasonalShelf")
    if stock is None:
        raise RuntimeError("Missing the authored seasonal shelf stock")
    return float(stock[-1] if isinstance(stock, tuple) else stock)


def checkpoint_state(inspection, world, ids, runtime):
    result = {"ids": sorted(ids), "fauna": {stable_id: {key: row[key] for key in ("species", "position", "rule_fauna")}
                                             for stable_id, row in authority_details(inspection, world, ids).items()}}
    if seasonal_stock:
        result["seasonal_stock"] = inspect_seasonal_stock(runtime)
    if pig_followup:
        result["pig_stock"] = {}
        for patch in runtime.get_editor_property("fauna_habitat_patches"):
            patch_id = str(patch.get_editor_property("id"))
            stock = runtime.inspect_fauna_habitat_stock(patch_id)
            if stock is None:
                raise RuntimeError(f"Missing pig food stock {patch_id}")
            result["pig_stock"][patch_id] = float(stock[-1] if isinstance(stock, tuple) else stock)
    if forage_case:
        result["forage"] = {}
        for site, visual in state["forage_visuals"].items():
            stock = runtime.inspect_fauna_habitat_stock(site)
            if stock is None:
                raise RuntimeError(f"Checkpoint forage stock missing at {site}")
            result["forage"][site] = [float(stock[-1] if isinstance(stock, tuple) else stock), visual.get_forage_fraction()]
    return result


def configure_regional_water(runtime):
    west_id, east_id, boundary = "FaunaMeadow", "FaunaWaterEast", 4170.
    west = next(actor for actor in actors.get_all_level_actors() if isinstance(actor, unreal.EcologyRegion)
                and str(actor.get_editor_property("region_id")) == west_id)
    east = actors.spawn_actor_from_class(unreal.EcologyRegion, unreal.Vector())
    for region, region_id, neighbor, minimum, maximum in ((west, west_id, east_id, -11800., boundary),
                                                          (east, east_id, west_id, boundary, 11800.)):
        region.set_actor_location(unreal.Vector((minimum + maximum) * .5, 0., 0.), False, True)
        region.get_editor_property("region_bounds").set_box_extent(unreal.Vector((maximum - minimum) * .5, 11800., 3500.), False)
        region.set_editor_property("region_id", region_id)
        region.set_editor_property("adjacent_region_ids", [neighbor])
    east_group = unreal.EcoCreatureSpawnGroup()
    east_group.set_editor_property("region_id", east_id)
    east_group.set_editor_property("herbivores", 0)
    east_group.set_editor_property("wolves", 0)
    groups = list(runtime.get_editor_property("groups"))
    west_group = next(group for group in groups if str(group.get_editor_property("region_id")) == west_id)
    west_fauna, east_fauna = [], []
    for placement in west_group.get_editor_property("fauna"):
        if kind(placement) == regional_species:
            placement.set_editor_property("spawn_points", [unreal.Vector(3920., -4800., 60.)])
        (east_fauna if kind(placement) == "CommonCarp" and regional_species != "CommonCarp" else west_fauna).append(placement)
    west_group.set_editor_property("fauna", west_fauna)
    east_group.set_editor_property("fauna", east_fauna)
    runtime.set_editor_property("groups", [*groups, east_group])
    for profile in (profiles := list(runtime.get_editor_property("fauna_species"))):
        if kind(profile) == regional_species:
            profile.set_editor_property("meal_start_fraction", .88)
            profile.set_editor_property("maintenance", .55)
    runtime.set_editor_property("fauna_species", profiles)
    source = next(actor for actor in actors.get_all_level_actors() if isinstance(actor, unreal.EcoVegetationHabitat)
                  and str(actor.get_editor_property("habitat_id")) == "ExpandedFaunaPool")
    destination = actors.spawn_actor_from_class(unreal.EcoVegetationHabitat, source.get_actor_location())
    destination.get_editor_property("bounds").set_box_extent(source.get_editor_property("bounds").get_unscaled_box_extent(), False)
    for field in ("plant", "drainage", "connected_fresh_water", "supports_fauna_swimming",
                  "fauna_water_current", "fauna_water_temperature_c"):
        destination.set_editor_property(field, source.get_editor_property(field))
    destination.set_editor_property("habitat_id", "ExpandedFaunaPoolEast")
    destination.set_editor_property("region_id", east_id)
    for water in (source, destination):
        water.set_editor_property("water_level_rise", 0.)
        water.set_editor_property("water_surface_z", 110. if regional_water in ("Closed", "Rain") else 142.)
        if regional_water == "Rain":
            water.set_editor_property("water_rain_rise_cm", 32.)
    if regional_water == "Rain":
        weather = actors.spawn_actor_from_class(unreal.EcoRegionEnvironmentAdapter, unreal.Vector())
        for field, value in dict(region_ids=[west_id, east_id], cycle_rainfall=True, rain_cycle_seconds=80.,
                                 dry_rainfall=0., wet_rainfall=1.).items():
            weather.set_editor_property(field, value)
    patches = []
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        if patch.get_editor_property("submerged"):
            patch_id = str(patch.get_editor_property("id"))
            if regional_species == "UnidentifiedFish" and patch_id == regional_food_patch:
                patch.set_editor_property("center", unreal.Vector(4345., -4720., 90.))
            if patch.get_editor_property("center").x > boundary:
                patch.set_editor_property("region_id", east_id)
            if patch_id != regional_food_patch:
                patch.set_editor_property("consumers", [consumer for consumer in patch.get_editor_property("consumers")
                                                        if str(consumer) != regional_species])
        if patch.get_editor_property("consumers"):
            patches.append(patch)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    route = actors.spawn_actor_from_class(unreal.EcoHerdMigrationRoute, unreal.Vector())
    route.set_editor_property("from_region", west_id)
    route.set_editor_property("to_region", east_id)
    route.set_editor_property("allow_rule_fauna_passage", True)
    route.set_editor_property("rule_fauna_water_passage", True)
    route.set_editor_property("points", [unreal.Vector(x, -4800., z) for x, z in
                                        ((3920., 65.), (4090., 105.), (4150., 126.), (4190., 126.), (4350., 55.))])


created_regional_map = False
level_path = MAP
if author_regional_weather:
    created_regional_map = not unreal.EditorAssetLibrary.does_asset_exist(REGIONAL_MAP)
    if not created_regional_map:
        level_path = REGIONAL_MAP
loaded = editor.get_editor_world()
if (not loaded or loaded.get_path_name().split(".")[0] != level_path) and not levels.load_level(level_path):
    raise RuntimeError(f"Cannot open {level_path}")
runtime = next(actor for actor in actors.get_all_level_actors() if isinstance(actor, unreal.EcoCreatureIntegrationSpawner))
if pig_thermal:
    region = next(actor for actor in actors.get_all_level_actors() if isinstance(actor, unreal.EcologyRegion)
                  and str(actor.get_editor_property("region_id")) == "PigMeadow")
    climate = region.get_environment_state()
    climate.set_editor_property("temperature", 19. if pig_thermal == "Cool" else 38.)
    climate.set_editor_property("rainfall", .9 if pig_thermal == "Wet" else .0)
    region.set_environment_state(climate)
    cooling_sites = {str(site.get_editor_property("id")): (site.get_editor_property("center"), site.get_editor_property("radius"))
                     for site in runtime.get_editor_property("fauna_cooling_sites")}
if forage_case and forage_case != "Natural":
    climate = next(a for a in actors.get_all_level_actors() if a.get_actor_label() == "JYU Forage Climate")
    climate.set_editor_property("cycle_rainfall", False)
if forage_case in ("Choice", "Depleted"):
    for profile in (profiles := list(runtime.get_editor_property("fauna_species"))):
        if kind(profile) == "Horse":
            profile.set_editor_property("meal_start_fraction", .86)
            profile.set_editor_property("maintenance", .65)
            profile.set_editor_property("routine_home_radius", 70.)
    runtime.set_editor_property("fauna_species", profiles)
    for group in (groups := list(runtime.get_editor_property("groups"))):
        for placement in (placements := list(group.get_editor_property("fauna"))):
            if kind(placement) == "Horse":
                placement.set_editor_property("spawn_points", [unreal.Vector(1210., -1805., 0.)])
        group.set_editor_property("fauna", placements)
    runtime.set_editor_property("groups", groups)
    for patch in (patches := list(runtime.get_editor_property("fauna_habitat_patches"))):
        patch_id = str(patch.get_editor_property("id"))
        if not patch_id.startswith("HerbForage"):
            continue
        if patch_id not in ("HerbForageMeadowGrass", "HerbForageMeadowForbs"):
            patch.set_editor_property("consumers", [c for c in patch.get_editor_property("consumers") if str(c) != "Horse"])
        if forage_case == "Depleted" and patch_id == "HerbForageMeadowGrass":
            patch.set_editor_property("capacity", .1)
            patch.set_editor_property("regrowth_per_second", 0.)
    runtime.set_editor_property("fauna_habitat_patches", patches)
if forage_case == "WeatherCycle":
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    for patch in patches:
        if str(patch.get_editor_property("id")) in weather_forage_sites:
            patch.set_editor_property("consumers", ["Horse"])
    runtime.set_editor_property("fauna_habitat_patches", patches)
if capture_riparian_detail:
    # Show the high-water cover in the same daylight as the ordinary bank capture.
    for habitat in actors.get_all_level_actors():
        if isinstance(habitat, unreal.EcoVegetationHabitat) and habitat.get_editor_property("supports_fauna_swimming"):
            habitat.set_editor_property("water_surface_z", 142.)
            habitat.set_editor_property("water_level_rise", 0.)
if regional_water and (not author_regional_weather or created_regional_map):
    configure_regional_water(runtime)
if riparian_feeding:
    feeding_sites = {"CommonCarp": ("RiparianHabitatBayInvertebrates", (3690., -4420., 65.)),
                     "AriakeCatfish": ("RiparianHabitatStoneMargin", (4580., -5020., 25.))}
    for profile in (profiles := list(runtime.get_editor_property("fauna_species"))):
        if kind(profile) in feeding_sites:
            profile.set_editor_property("meal_start_fraction", .88)
            profile.set_editor_property("maintenance", .28)
            profile.set_editor_property("routine_home_radius", 75.)
    runtime.set_editor_property("fauna_species", profiles)
    for group in (groups := list(runtime.get_editor_property("groups"))):
        for placement in (placements := list(group.get_editor_property("fauna"))):
            if kind(placement) in feeding_sites:
                placement.set_editor_property("spawn_points", [unreal.Vector(*feeding_sites[kind(placement)][1])])
        group.set_editor_property("fauna", placements)
    runtime.set_editor_property("groups", groups)
    patches = []
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        patch_id = str(patch.get_editor_property("id"))
        eligible = [consumer for consumer in patch.get_editor_property("consumers")
                    if str(consumer) not in feeding_sites or feeding_sites[str(consumer)][0] == patch_id]
        if eligible:
            patch.set_editor_property("consumers", eligible)
            patches.append(patch)
    runtime.set_editor_property("fauna_habitat_patches", patches)
if seasonal_feeding:
    # Hold one carp near the shelf. Existing food remains available to other species.
    for profile in (profiles := list(runtime.get_editor_property("fauna_species"))):
        if kind(profile) == "CommonCarp":
            profile.set_editor_property("meal_start_fraction", .88)
            profile.set_editor_property("maintenance", .28)
            profile.set_editor_property("routine_home_radius", 75.)
    runtime.set_editor_property("fauna_species", profiles)
    for group in (groups := list(runtime.get_editor_property("groups"))):
        for placement in (placements := list(group.get_editor_property("fauna"))):
            if kind(placement) == "CommonCarp":
                placement.set_editor_property("spawn_points", [unreal.Vector(4015., -4700., 80.)])
        group.set_editor_property("fauna", placements)
    runtime.set_editor_property("groups", groups)
    patches = []
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        if str(patch.get_editor_property("id")) != "ExpandedWaterSeasonalShelf":
            patch.set_editor_property("consumers", [consumer for consumer in patch.get_editor_property("consumers")
                                                    if str(consumer) != "CommonCarp"])
        if patch.get_editor_property("consumers"):
            patches.append(patch)
    runtime.set_editor_property("fauna_habitat_patches", patches)
if eagle_fatigue == "Rapid":
    for profile in (profiles := list(runtime.get_editor_property("fauna_species"))):
        if kind(profile) == "GoldenEagle":
            profile.set_editor_property("sprint_drain", .65)
    runtime.set_editor_property("fauna_species", profiles)
if mode == "Baseline":
    profiles = [profile for profile in runtime.get_editor_property("fauna_species") if kind(profile) not in NEW]
    for profile in profiles:
        profile.set_editor_property("prey_rules", [rule for rule in profile.get_editor_property("prey_rules")
                                                   if kind(rule) not in NEW])
    runtime.set_editor_property("fauna_species", profiles)
    runtime.set_editor_property("fauna_perches", [perch for perch in runtime.get_editor_property("fauna_perches")
                                                  if kind(perch) not in NEW])
    for group in (groups := list(runtime.get_editor_property("groups"))):
        group.set_editor_property("fauna", [placement for placement in group.get_editor_property("fauna")
                                            if kind(placement) not in NEW])
    runtime.set_editor_property("groups", groups)
    runtime.set_editor_property("fauna_habitat_patches", [patch for patch in runtime.get_editor_property("fauna_habitat_patches")
                                if not str(patch.get_editor_property("id")).startswith("ExpandedWater")])
if static_water:
    for actor in actors.get_all_level_actors():
        if isinstance(actor, unreal.EcoVegetationHabitat):
            actor.set_editor_property("water_level_rise", 0.)
if rain_fixture:
    pool = next(actor for actor in actors.get_all_level_actors()
                if isinstance(actor, unreal.EcoVegetationHabitat)
                and str(actor.get_editor_property("habitat_id")) == "ExpandedFaunaPool")
    pool.set_editor_property("water_level_rise", 0.)
    pool.set_editor_property("water_rain_rise_cm", 32.)
    weather = actors.spawn_actor_from_class(unreal.EcoRegionEnvironmentAdapter, unreal.Vector())
    weather.set_editor_property("region_ids", ["FaunaMeadow"])
    weather.set_editor_property("cycle_rainfall", True)
    weather.set_editor_property("rain_cycle_seconds", 120.)
    weather.set_editor_property("dry_rainfall", 0.)
    weather.set_editor_property("wet_rainfall", 1.)
if nest:
    # Test the ordinary breeding and provision transactions with finite food and
    # both founders initially on the same collision platform.
    for profile in (profiles := list(runtime.get_editor_property("fauna_species"))):
        if kind(profile) == "GoldenEagle":
            for field, value in dict(nestling_seconds=35., gestation=10., maintenance=.9,
                                     day_activity=.05, night_activity=.05, can_dive_hunt=False,
                                     routine_home_radius=35., meal_start_fraction=.89,
                                     meal_stop_fraction=.96).items():
                profile.set_editor_property(field, value)
    runtime.set_editor_property("fauna_species", profiles)
    points = [unreal.Vector(-80., -3400., 360.), unreal.Vector(-20., -3400., 360.)]
    if nest == "Return":
        points[1] = unreal.Vector(200., -3400., 0.)
    for group in (groups := list(runtime.get_editor_property("groups"))):
        for placement in (placements := list(group.get_editor_property("fauna"))):
            if kind(placement) == "GoldenEagle":
                placement.set_editor_property("spawn_points", points)
        group.set_editor_property("fauna", placements)
    runtime.set_editor_property("groups", groups)
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    for index, point in enumerate(points):
        patch = unreal.EcoFaunaHabitatPatch()
        for field, value in dict(id=f"ExpandedNestControl{index}", region_id="FaunaMeadow",
                                 center=point, consumers=["GoldenEagle"], capacity=220., energy_per_meal=14.).items():
            patch.set_editor_property(field, value)
        patches.append(patch)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    perches = list(runtime.get_editor_property("fauna_perches"))
    for perch in perches:
        if kind(perch) == "GoldenEagle" and perch.get_editor_property("location").x < 0.:
            perch.set_editor_property("nest_id", "None" if nest == "NoSite" else "ExpandedEagleWestNest")
    runtime.set_editor_property("fauna_perches", perches)
if "-EcoExpandedCrestFixture" in command:
    # Identical initial conditions for the high/low treatment. The fish still
    # chooses and reaches food through the ordinary authority rules.
    for profile in (profiles := list(runtime.get_editor_property("fauna_species"))):
        if kind(profile) == "AriakeCatfish":
            profile.set_editor_property("meal_start_fraction", .87)
            profile.set_editor_property("maintenance", .45)
    runtime.set_editor_property("fauna_species", profiles)
    for group in (groups := list(runtime.get_editor_property("groups"))):
        for placement in (placements := list(group.get_editor_property("fauna"))):
            if kind(placement) == "AriakeCatfish":
                placement.set_editor_property("spawn_points", [unreal.Vector(3950., -4700., 25.)])
        group.set_editor_property("fauna", placements)
    runtime.set_editor_property("groups", groups)
    patches = []
    for patch in runtime.get_editor_property("fauna_habitat_patches"):
        if str(patch.get_editor_property("id")).startswith("ExpandedWater") and str(
                patch.get_editor_property("id")) != "ExpandedWaterConnectedShelf":
            patch.set_editor_property("consumers", [consumer for consumer in patch.get_editor_property("consumers")
                                                     if str(consumer) != "AriakeCatfish"])
        if patch.get_editor_property("consumers"):
            patches.append(patch)
    runtime.set_editor_property("fauna_habitat_patches", patches)
if "-EcoExpandedMinkFixture" in command or mink_cover:
    # Unsaved encounter with accessible small fish and a physically separated
    # adult carp. Ground food and the alternative shore entry still exist.
    profiles = list(runtime.get_editor_property("fauna_species"))
    for profile in profiles:
        if kind(profile) == "Mink":
            profile.set_editor_property("meal_start_fraction", .88)
            profile.set_editor_property("maintenance", .04 if mink_low_demand else .75)
        elif mink_cover and kind(profile) == "UnidentifiedFish":
            profile.set_editor_property("routine_home_radius", 10.)
    runtime.set_editor_property("fauna_species", profiles)
    groups = list(runtime.get_editor_property("groups"))
    for group in groups:
        placements = list(group.get_editor_property("fauna"))
        for placement in placements:
            points = {"Mink": [(3250., -4550., 0.)],
                      "UnidentifiedFish": [(3500., -4540., 70.), (3525., -4590., 75.)]}.get(kind(placement))
            if mink_cover and kind(placement) == "UnidentifiedFish":
                points = [(3500., -4525., 70.), (3525., -4600., 75.)]
            if points:
                placement.set_editor_property("spawn_points", [unreal.Vector(*point) for point in points])
        group.set_editor_property("fauna", placements)
    runtime.set_editor_property("groups", groups)
    patches = list(runtime.get_editor_property("fauna_habitat_patches"))
    for patch in patches:
        if str(patch.get_editor_property("id")) == "ExpandedWaterShoreForage":
            patch.set_editor_property("capacity", .25)
            patch.set_editor_property("regrowth_per_second", 0.)
    runtime.set_editor_property("fauna_habitat_patches", patches)
    if mink_cover == "Screen":
        screen = actors.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(3455., -4537., 48.))
        screen.static_mesh_component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
        screen.static_mesh_component.set_collision_profile_name("BlockAll")
        screen.set_actor_scale3d(unreal.Vector(.08, .44, .96))
    if mink_cover == "Vegetation":
        pool = next(a for a in actors.get_all_level_actors() if isinstance(a, unreal.EcoVegetationHabitat)
                    and str(a.get_editor_property("habitat_id")) == "ExpandedFaunaPool")
        cover = actors.spawn_actor_from_class(unreal.EcoVegetationHabitat, unreal.Vector(3500., -4525., 45.))
        cover.get_editor_property("bounds").set_box_extent(unreal.Vector(30., 25., 130.), False)
        for field, value in dict(habitat_id="AuditMinkVegetation", region_id="FaunaMeadow", priority=20,
                                 connected_fresh_water=True, supports_fauna_swimming=True, draw_water_surface=False,
                                 fauna_water_cover_density=.97, fauna_water_cover_height_cm=120.).items():
            cover.set_editor_property(field, value)
        for field in ("water_surface_z", "water_level_rise", "water_rise_seconds", "water_high_seconds",
                      "water_fall_seconds", "water_low_seconds", "fauna_water_current"):
            cover.set_editor_property(field, pool.get_editor_property(field))
if floating_fixture:
    # Rapid starvation of one shoreline swimmer in an unsaved scene exercises
    # floating stock and its movement without modifying player combat or Mass.
    runtime.set_editor_property("starvation_grace_seconds", 0.)
    runtime.set_editor_property("starvation_damage_per_second", 125.)
    profiles = list(runtime.get_editor_property("fauna_species"))
    for profile in profiles:
        if kind(profile) == "Mink":
            profile.set_editor_property("maintenance", 42.)
    runtime.set_editor_property("fauna_species", profiles)
    groups = list(runtime.get_editor_property("groups"))
    for group in groups:
        placements = list(group.get_editor_property("fauna"))
        for placement in placements:
            if kind(placement) == "Mink":
                placement.set_editor_property("spawn_points", [unreal.Vector(3325., -4550., 0.)])
        group.set_editor_property("fauna", placements)
    runtime.set_editor_property("groups", groups)

state = {"start": time.monotonic(), "last": -5., "next_detail": 0., "frames": 0, "checkpoint": None,
         "crest_states": [], "previously_living": set(), "recent_deaths": {}, "rain_observations": {},
         "nest_children": {}, "nest_parent_returned": False, "water_arrivals": [], "water_transfer_counts": [],
         "water_control_phase": 0, "mink_entry": None, "food_intent": None, "pig_founders": {}, "pig_growth": {},
         "pig_spacing": [], "pig_cooling": {}, "pig_client": {}, "pig_threat": {}, "seasonal_stock": [], "riparian": {},
         "floating_plant_levels": [], "plant_forage": {}}


def finish(error=None):
    unreal.unregister_slate_post_tick_callback(handle)
    path = output / f"{name}_status.json"
    path.write_text(json.dumps({"mode": mode, "frames": state["frames"], "checkpoint": state["checkpoint"],
                                "crest_states": state["crest_states"],
                                "rain_observations": state["rain_observations"],
                                "nest_children": state["nest_children"],
                                "nest_parent_returned": state["nest_parent_returned"],
                                "water_arrivals": state["water_arrivals"], "water_transfer_counts": state["water_transfer_counts"],
                                "mink_entry": state["mink_entry"],
                                "food_intent": state["food_intent"],
                                "pig_founders": state["pig_founders"], "pig_growth": state["pig_growth"],
                                "pig_spacing": state["pig_spacing"],
                                "pig_cooling": state["pig_cooling"],
                                "pig_client": state["pig_client"],
                                "pig_threat": state["pig_threat"],
                                "seasonal_stock": state["seasonal_stock"],
                                "riparian": state["riparian"],
                                "floating_plant_levels": state["floating_plant_levels"],
                                "plant_forage": state["plant_forage"],
                                "error": error}, indent=2), encoding="utf-8")
    if error:
        unreal.log_error(f"ECO_EXPANDED_AUDIT_FAILED {error}")
    else:
        unreal.log(f"ECO_EXPANDED_AUDIT_READY {name} frames={state['frames']}")
    levels.editor_request_end_play()
    unreal.SystemLibrary.quit_editor()


def measure_forage_geometry(actor, site, expected):
    plants = actor.get_editor_property("plants")
    stems = actor.get_editor_property("woody_stems")
    full = actor.get_editor_property("full_plant_transforms")
    if not full or plants.get_instance_count() != len(full):
        raise RuntimeError(f"Missing plant instances in {site}")
    actual = sum(plants.get_instance_transform(i, False).scale3d.z / t.scale3d.z for i, t in enumerate(full)) / len(full)
    if actor.get_editor_property("keep_woody_stems"):
        if stems.get_instance_count() != len(full) or any(
                abs(stems.get_instance_transform(i, False).scale3d.z - t.scale3d.z) > .0001 for i, t in enumerate(full)):
            raise RuntimeError(f"Woody stems changed with edible stock in {site}")
    if abs(actual - expected) > .001:
        raise RuntimeError(f"Foliage scale differs from stock at {site}: {actual} vs {expected}")
    return actual


def tick(_):
    try:
        if time.monotonic() - state["start"] > max(140., seconds):
            raise RuntimeError("Timed out waiting for an ecology world")
        client_world = None
        if pie_network:
            worlds = [w for w in unreal.ObjectIterator(unreal.World) if "/UEDPIE_" in w.get_path_name()
                      and w.get_name().endswith(MAP.rsplit("/", 1)[-1])]
            world = next((w for w in worlds if unreal.GameplayStatics.get_game_mode(w)), None)
            client_world = next((w for w in worlds if w != world and unreal.GameplayStatics.get_player_controller(w, 0)), None)
            if not client_world and time.monotonic() - state["start"] > 35.:
                raise RuntimeError("Could not find the connected PIE client")
        else:
            world = editor.get_game_world()
        if not world:
            return
        game_state = unreal.GameplayStatics.get_game_state(world)
        if not isinstance(game_state, unreal.EcoGameState):
            return
        live_runtime = next(iter(unreal.GameplayStatics.get_all_actors_of_class(
            world, unreal.EcoCreatureIntegrationSpawner)), None)
        if live_runtime is None or not live_runtime.is_runtime_ready():
            if unreal.GameplayStatics.get_time_seconds(world) >= 35.:
                raise RuntimeError("Authority did not initialize; inspect the first Eco Setup error")
            return
        if pig_network:
            controller = next(iter(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerController)), None)
            pawn = controller.get_controlled_pawn() if controller else None
            if pawn and pawn.get_path_name() != state.get("pig_viewer"):
                # A fixed observer keeps the client within the ordinary Mass relevance radius.
                pawn.character_movement.set_movement_mode(unreal.MovementMode.MOVE_FLYING)
                pawn.set_actor_location(unreal.Vector(0., -1440., 150.), False, True)
                state["pig_viewer"] = pawn.get_path_name()
        if state["frames"] == 0:
            unreal.SystemLibrary.execute_console_command(world, "eco.Inspection.GameplayReasons 1")
            if water_audio:
                pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
                if not pawn:
                    return
                pawn.set_actor_location(unreal.Vector(3480., -4190., 135.), False, True)
                unreal.SystemLibrary.execute_console_command(world, "eco.Footsteps.Log 1")
        inspection = unreal.EcoCreatureInspectionLibrary
        ids = inspection.get_authority_agent_ids(world)
        summary = game_state.get_ecology_summary()
        now = summary.get_editor_property("time").get_editor_property("server_time_seconds")
        if pig_capture and not state.get("pig_camera"):
            controller = unreal.GameplayStatics.get_player_controller(world, 0)
            location = unreal.Vector(40., -1870., 590.)
            camera = unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, unreal.CameraActor,
                                                                                unreal.Transform(location=location))
            camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(location, unreal.Vector(40., -950., 20.)), False)
            controller.set_view_target_with_blend(camera, 0.)
            unreal.SystemLibrary.execute_console_command(world, "eco.Creature.Labels 0")
            unreal.SystemLibrary.execute_console_command(world, "showhud")
            state["pig_camera"] = True
        if pig_capture and now >= 8. and not state.get("pig_captured"):
            image = (output / f"{name}.png").as_posix()
            unreal.SystemLibrary.execute_console_command(world, f'HighResShot 1280x720 filename="{image}"')
            state["pig_captured"] = True
        if pig_threat and 1. <= now < 4.:
            pawn = unreal.GameplayStatics.get_player_pawn(world, 0)
            if pawn:
                if not state.get("pig_run_started"):
                    pawn.set_actor_location(unreal.Vector(-1400., -510., 104.), False, True)
                    if not unreal.EcoCreatureAnimationBuilder.set_audit_player_gait(pawn, 2):
                        raise RuntimeError("Pig threat test could not set the real player gait")
                    state["pig_run_started"] = True
                pawn.add_movement_input(unreal.Vector(1., 0., 0.), 1., False)
        if forage_case and not state["plant_forage"]:
            patches = {str(p.get_editor_property("id")): p
                       for p in live_runtime.get_editor_property("fauna_habitat_patches")
                       if str(p.get_editor_property("id")).startswith("HerbForage")}
            sites = {site: str(patch.get_editor_property("plant_guild")) for site, patch in patches.items()}
            scenery = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoForagePatchVisual)
            visible = {str(actor.get_editor_property("patch_id")): actor for actor in scenery}
            if len(sites) != 15 or len(set(sites.values())) != 4 or set(sites) != set(visible) or len(scenery) != 15:
                raise RuntimeError(f"Invalid visual patch inventory: gameplay={list(sites)}, visual={list(visible)}")
            state["forage_visuals"] = visible
            state["forage_capacities"] = {site: patch.get_editor_property("capacity") for site, patch in patches.items()}
            state["forage_region"] = next(a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcologyRegion)
                                          if str(a.get_editor_property("region_id")) == "FaunaMeadow")
            state["plant_forage"] = {"sites": sites, "minimum_stock": {site: 1e9 for site in sites}, "appearance": []}
            if capture_forage:
                unreal.SystemLibrary.execute_console_command(world, "eco.Creature.Labels 0")
                unreal.SystemLibrary.execute_console_command(world, "showhud")
                controller = unreal.GameplayStatics.get_player_controller(world, 0)
                location = unreal.Vector(1420., -2205., 255.)
                camera = unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, unreal.CameraActor,
                                                                                    unreal.Transform(location=location))
                camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(location, unreal.Vector(1350., -1785., 20.)), False)
                controller.set_view_target_with_blend(camera, 0.)
        if forage_case == "WeatherCycle":
            phase = "wet" if now >= forage_weather_change else "dry"
            if state.get("forage_weather") != phase:
                region = state["forage_region"]
                environment = region.get_environment_state()
                environment.set_editor_property("rainfall", .9 if phase == "wet" else 0.)
                environment.set_editor_property("humidity", .85 if phase == "wet" else .05)
                environment.set_editor_property("temperature", 17. if phase == "wet" else 25.)
                region.set_environment_state(environment)
                state["forage_weather"] = phase
        if capture_forage and now >= 8. and not state.get("forage_capture"):
            image = (output / f"{name}.png").as_posix()
            unreal.SystemLibrary.execute_console_command(world, f'HighResShot 1280x720 filename="{image}"')
            state["forage_capture"] = True
        if audit_riparian and not state["riparian"]:
            def current(x, y):
                sample = inspection.inspect_fauna_water(world, "FaunaMeadow", unreal.Vector(x, y, 65.), 4.)
                if sample is None:
                    raise RuntimeError(f"Missing swimmable habitat at {(x, y)}")
                return sample[1].length()
            bank_meshes = len([a for a in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor)
                               if a.get_actor_label().startswith("JYU Riparian ")])
            bay, open_water = current(3730., -4400.), current(3970., -4750.)
            patch_stocks = {}
            for suffix in ("BankLitter", "BayInvertebrates", "StoneMargin"):
                stock = live_runtime.inspect_fauna_habitat_stock("RiparianHabitat" + suffix)
                patch_stocks[suffix] = float(stock[-1] if isinstance(stock, tuple) else stock) if stock is not None else 0.
            if not (bank_meshes >= 40 and 0. < bay < open_water and all(v > 0. for v in patch_stocks.values())):
                raise RuntimeError(f"Riparian habitat is incomplete: {bank_meshes}, {bay}, {open_water}, {patch_stocks}")
            state["riparian"] = {"meshes": bank_meshes, "bay_current": bay, "open_current": open_water, "stock": patch_stocks}
            if projectj_riparian:
                scenery = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.StaticMeshActor)
                assets = {a.static_mesh_component.get_editor_property("static_mesh").get_path_name().split(".")[0]
                          for a in scenery if a.get_actor_label().startswith("JYU Riparian ")
                          and a.static_mesh_component.get_editor_property("static_mesh")}
                state["riparian"]["projectj_meshes"] = sorted(asset for asset in assets if asset.startswith("/Game/Map_Resource/"))
                state["floating_plants"] = [a for a in scenery if a.get_actor_label().startswith("JYU Riparian ProjectJ Duckweed ")]
                if len(state["riparian"]["projectj_meshes"]) != 9 or len(state["floating_plants"]) != 6:
                    raise RuntimeError("Project_J placements are incomplete")
            if capture_riparian:
                controller = unreal.GameplayStatics.get_player_controller(world, 0)
                unreal.SystemLibrary.execute_console_command(world, "eco.Creature.Labels 0")
                unreal.SystemLibrary.execute_console_command(world, "showhud")
                location = (unreal.Vector(3460., -4770., 345.) if capture_riparian_detail
                            else unreal.Vector(2990., -5170., 415.))
                target = (unreal.Vector(3730., -4430., 52.) if capture_riparian_detail else unreal.Vector(3715., -4710., 68.))
                camera = unreal.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, unreal.CameraActor,
                                                                                    unreal.Transform(location=location))
                camera.set_actor_rotation(unreal.MathLibrary.find_look_at_rotation(location, target), False)
                controller.set_view_target_with_blend(camera, 0.)
        if capture_riparian and now >= 12. and not state.get("riparian_capture"):
            image = (output / f"{name}.png").as_posix()
            unreal.SystemLibrary.execute_console_command(world, f'HighResShot 1280x720 filename="{image}"')
            state["riparian_capture"] = True
        if food_intent and 10. <= now < 28.:
            intent = state["food_intent"]
            intent_kind = unreal.EcoFaunaFoodIntent.LIVE_PREY
            if not intent:
                details = authority_details(inspection, world, ids)
                hunter = next(int(i) for i, row in details.items() if row["species"] == "Mink")
                fish = sorted(int(i) for i, row in details.items() if row["species"] == "UnidentifiedFish")
                intent = {"hunter": hunter, "target": fish[0 if food_intent == "Occluded" else 1],
                          "malformed_rejected": not live_runtime.submit_fauna_food_intent(hunter, intent_kind, hunter, "None"),
                          "accepted": [], "next": 0.}
                state["food_intent"] = intent
            if now >= intent["next"] and (food_intent != "Expired" or not intent["accepted"]):
                if not live_runtime.submit_fauna_food_intent(intent["hunter"], intent_kind, intent["target"], "None"):
                    raise RuntimeError(f"Expected an admitted preference request for {intent['target']}")
                intent["accepted"].append(now)
                intent["next"] = now + 1.
        if regional_water == "Closing":
            control_phase = 2 if now >= 55. else 1 if now >= 24. else 0
            if control_phase != state["water_control_phase"]:
                for pool in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoVegetationHabitat):
                    if pool.get_editor_property("supports_fauna_swimming"):
                        pool.set_editor_property("water_surface_z", 110. if control_phase == 1 else 142.)
                state["water_control_phase"] = control_phase
        # R7e is applied at the first decision boundary after the spawner reports ready.
        regional_save_time = 23. if regional_suffix else 25.
        checkpoint_time = 4. if checkpoint == "Load" else 21. if nest else regional_save_time if regional_water else 75.
        if checkpoint and state["checkpoint"] is None and now >= checkpoint_time:
            filename = ("PigFollowupCheckpointState.json" if pig_followup else "HerbivoreForageCheckpointState.json" if forage_case else "SeasonalWaterFoodCheckpointState.json" if seasonal_stock else "ExpandedNestCheckpointState.json" if nest else f"ExpandedRegionalWaterCheckpointState{regional_suffix}.json"
                        if regional_water else "ExpandedCheckpointState.json")
            expected = output / filename
            if checkpoint == "Save" and live_runtime.save_ecosystem(slot):
                saved = checkpoint_state(inspection, world, ids, live_runtime)
                if forage_case and not any(fraction < .9 for _, fraction in saved["forage"].values()):
                    raise RuntimeError("Checkpoint did not capture depleted forage")
                expected.write_text(json.dumps(saved, indent=2), encoding="utf-8")
                state["checkpoint"] = {"saved_ids": len(ids), "rule_fauna": len(saved["fauna"])}
            elif checkpoint == "Save" and regional_water:
                raise RuntimeError(f"Could not save regional checkpoint {slot} at {now:.2f}s")
            elif checkpoint == "Load":
                if not live_runtime.load_ecosystem(slot):
                    raise RuntimeError("Expanded checkpoint restore rejected")
                ids = inspection.get_authority_agent_ids(world)
                restored = checkpoint_state(inspection, world, ids, live_runtime)
                if restored != json.loads(expected.read_text(encoding="utf-8")):
                    (output / "ExpandedCheckpointMismatch.json").write_text(json.dumps(restored, indent=2), encoding="utf-8")
                    raise RuntimeError("Restored authority IDs or rule-fauna state differ")
                state["checkpoint"] = {"restored_ids": len(ids), "rule_fauna": len(restored["fauna"])}
                return
        if now < state["last"] + (.5 if pig_threat else 1. if floating_fixture or mink_cover or eagle_fatigue or pig_network else 5.) and now < seconds:
            return
        state["last"] = now
        if pig_network and client_world:
            if inspection.get_authority_agent_ids(client_world):
                raise RuntimeError("Pig client ran authority ecology")
            client_game_state = unreal.GameplayStatics.get_game_state(client_world)
            if isinstance(client_game_state, unreal.EcoGameState):
                client_summary = client_game_state.get_ecology_summary()
                for actor in unreal.GameplayStatics.get_all_actors_of_class(client_world, unreal.EcoCreatureRepresentationActor):
                    view = actor.get_editor_property("visual_state")
                    if not actor.get_editor_property("bound") or kind(view) != "Pig":
                        continue
                    agent_id = int(view.get_editor_property("stable_agent_id"))
                    mesh = actor.get_editor_property("creature_mesh")
                    animation = mesh.get_anim_instance()
                    if agent_id in ids and mesh.get_skeletal_mesh_asset() and animation:
                        revision = client_summary.get_editor_property("revision")
                        entry = state["pig_client"].setdefault(str(agent_id), {
                            "mesh": mesh.get_skeletal_mesh_asset().get_name(), "anim": animation.get_class().get_name(),
                            "body_scale": view.get_editor_property("body_scale"), "revisions": []})
                        if revision > 0 and revision not in entry["revisions"]:
                            entry["revisions"].append(revision)
        if forage_case:
            appearance = {}
            for site, low in state["plant_forage"]["minimum_stock"].items():
                stock = live_runtime.inspect_fauna_habitat_stock(site)
                if stock is None:
                    raise RuntimeError(f"Missing live forage stock for {site}")
                stock = float(stock[-1] if isinstance(stock, tuple) else stock)
                state["plant_forage"]["minimum_stock"][site] = min(low, stock)
                actor = state["forage_visuals"][site]
                capacity = state["forage_capacities"][site]
                fraction = actor.get_forage_fraction()
                if abs(stock / capacity - fraction) > .002:
                    raise RuntimeError(f"Visual forage fraction differs from authority at {site}: {fraction}, stock={stock}/{capacity}")
                residual = .001 if actor.get_editor_property("keep_woody_stems") else actor.get_editor_property("residual_height_fraction")
                expected = residual + (1. - residual) * fraction
                foliage_scale = expected
                if not forage_network:
                    foliage_scale = measure_forage_geometry(actor, site, expected)
                appearance[site] = {"stock": stock, "fraction": fraction, "foliage_scale": foliage_scale}
            rainfall = state["forage_region"].get_environment_state().get_editor_property("rainfall")
            row = {"time": now, "rain": rainfall, "sites": appearance}
            if client_world:
                client_game_state = unreal.GameplayStatics.get_game_state(client_world)
                if isinstance(client_game_state, unreal.EcoGameState):
                    row["client_revision"] = client_game_state.get_ecology_summary().get_editor_property("revision")
                replicas = {str(a.get_editor_property("patch_id")): a for a in
                            unreal.GameplayStatics.get_all_actors_of_class(client_world, unreal.EcoForagePatchVisual)}
                if "network" not in state["plant_forage"]:
                    pawn = unreal.GameplayStatics.get_player_pawn(client_world, 0)
                    viewer = pawn.get_actor_location() if pawn else None
                    state["plant_forage"]["network"] = {}
                    for site in weather_forage_sites:
                        authority = state["forage_visuals"][site]
                        replica = replicas.get(site)
                        state["plant_forage"]["network"][site] = {
                            "replicates": authority.get_editor_property("replicates"),
                            "hidden": authority.get_editor_property("hidden"),
                            "cull_cm": authority.get_editor_property("net_cull_distance_squared") ** .5,
                            "viewer_cm": (viewer - authority.get_actor_location()).length() if viewer is not None else None,
                            "client_role": str(replica.get_local_role()) if replica else None,
                        }
                row["client"] = {site: replicas[site].get_forage_fraction() for site in weather_forage_sites if site in replicas}
                if inspection.get_authority_agent_ids(client_world):
                    raise RuntimeError("The client ran logical ecology")
                for site, fraction in row["client"].items():
                    replica = replicas[site]
                    residual = .001 if replica.get_editor_property("keep_woody_stems") else replica.get_editor_property("residual_height_fraction")
                    measure_forage_geometry(replica, site, residual + (1. - residual) * fraction)
            state["plant_forage"]["appearance"].append(row)
        if projectj_riparian:
            sample = inspection.inspect_fauna_water(world, "FaunaMeadow", unreal.Vector(3560., -4420., 65.), 2.)
            if sample is None:
                raise RuntimeError("Could not measure the water under the floating vegetation")
            level = sample[0].y
            offsets = [plant.get_actor_location().z - level for plant in state["floating_plants"]]
            if min(offsets) < .2 or max(offsets) > 4.:
                raise RuntimeError(f"Floating plants detached from authoritative water at {now}: level={level}, offsets={offsets}")
            state["floating_plant_levels"].append([now, level, min(offsets), max(offsets)])
        if seasonal_stock:
            state["seasonal_stock"].append([now, inspect_seasonal_stock(live_runtime)])
        populations = {}
        for row in summary.get_editor_property("species"):
            totals = populations.setdefault(kind(row), {})
            for key in ("population", "births", "deaths", "migration_in", "migration_out"):
                totals[key] = totals.get(key, 0) + row.get_editor_property(key)
            if regional_water and kind(row) == regional_species:
                counts = [str(row.get_editor_property("region_id")), row.get_editor_property("migration_in"),
                          row.get_editor_property("migration_out")]
                if counts not in state["water_transfer_counts"]:
                    state["water_transfer_counts"].append(counts)
        observed = {}
        authority = {}
        dead = {}
        water = {}
        if hasattr(inspection, "inspect_fauna_water"):
            for zone, x in (("west", 3850.), ("crest", 4170.), ("east", 4440.)):
                values = inspection.inspect_fauna_water(
                    world, "FaunaMeadow", unreal.Vector(x, -4800., 115.), 6.)
                if values is None:
                    water[zone] = {"usable": False}
                else:
                    column, current = values
                    water[zone] = dict(usable=True, bottom=column.x, surface=column.y, current=current.length())
            crest_states = state["crest_states"]
            usable = water["crest"]["usable"]
            if not crest_states or usable != crest_states[-1]:
                crest_states.append(usable)
        rainfall = None
        if rain_fixture:
            region = next((row for row in summary.get_editor_property("regions")
                           if str(row.get_editor_property("region_id")) == "FaunaMeadow"), None)
            if region is not None:
                rainfall = region.get_editor_property("environment").get_editor_property("rainfall")
            if rainfall is not None and (rainfall < .01 or rainfall > .99):
                phase = "dry" if rainfall < .01 else "wet"
                state["rain_observations"][phase] = {"rainfall": rainfall, "surface": water["west"]["surface"],
                                                     "crest_usable": water["crest"]["usable"]}
        if now >= state["next_detail"]:
            authority = authority_details(inspection, world, ids)
            if pig_threat:
                for agent_id, row in authority.items():
                    heard = next((event for event in row.get("gameplay_reason_history", ()) if event["reason"] == "ThreatHeard"), None)
                    if heard:
                        state["pig_threat"].setdefault(agent_id, {"heard_at": heard["time"]})
            if pig_thermal:
                for agent_id, row in authority.items():
                    events = row.get("gameplay_reason_history", ())
                    if not any(event["reason"] == "CoolingSiteRest" and now - event["time"] < .25 for event in events):
                        continue
                    xyz = dict(re.findall(r"([XYZ])=(-?\d+(?:\.\d+)?)", row["position"]))
                    if not xyz and row["position"] != "V(0)":
                        raise RuntimeError(f"Unexpected pig position {row['position']}")
                    position = unreal.Vector(*(float(xyz.get(axis, 0.)) for axis in "XYZ"))
                    for site, (center, radius) in cooling_sites.items():
                        if (position - center).length() <= radius + 3.:
                            state["pig_cooling"].setdefault(site, {}).setdefault(agent_id, round(now, 3))
            if pig_followup:
                for agent_id, row in authority.items():
                    details = row["rule_fauna"]
                    if int(details["parent_a"]) == 0:
                        if state["frames"] == 0:
                            state["pig_founders"][agent_id] = {key: details[key] for key in
                                                                ("size_gene", "speed_gene", "caution_gene", "sociability_gene")}
                    else:
                        scale = row["body_scale"]
                        child = state["pig_growth"].setdefault(agent_id, {"initial": scale, "largest": scale})
                        child["largest"] = max(child["largest"], scale)
                    for event in row.get("gameplay_reason_history", ()):
                        if event["reason"] == "ConspecificSpacing" and event["time"] < 15.:
                            pair = [int(agent_id), int(event["related_id"]), event["amount"]]
                            if pair not in state["pig_spacing"]:
                                state["pig_spacing"].append(pair)
            if mink_cover and not state["mink_entry"]:
                for hunter, row in authority.items():
                    if row["species"] != "Mink":
                        continue
                    detail = row["rule_fauna"]
                    if detail["swimming"] and detail["shore_phase"] == 1 and int(detail["prey"]) > 0:
                        state["mink_entry"] = {"hunter": hunter, "prey": str(detail["prey"]), "time": now,
                                               "energy": row["energy"]}
                        break
            if regional_water:
                for agent_id, row in authority.items():
                    if row["species"] == regional_species and row["region"] == "FaunaWaterEast" and agent_id not in state["water_arrivals"]:
                        state["water_arrivals"].append(agent_id)
            if nest:
                for child_id, row in authority.items():
                    if row["species"] == "GoldenEagle" and int(row["rule_fauna"]["parent_a"]) > 0:
                        child = state["nest_children"].setdefault(child_id, {"time": now, "position": row["position"],
                                                                             "phases": []})
                        phase = row["rule_fauna"]["flight_phase"]
                        if not child["phases"] or child["phases"][-1] != phase:
                            child["phases"].append(phase)
                        if nest == "Return":
                            parent = authority.get(str(row["rule_fauna"]["parent_b"]))
                            if parent and "Z=360.00" in parent["position"] and parent["rule_fauna"]["flight_phase"] == 0:
                                state["nest_parent_returned"] = True
            living = set(authority)
            for stable_id in state["previously_living"] - living:
                state["recent_deaths"][stable_id] = now + 35.
            state["previously_living"] = living
            state["recent_deaths"] = {key: until for key, until in state["recent_deaths"].items() if now <= until}
            dead = authority_details(inspection, world, sorted(map(int, state["recent_deaths"])))
            state["next_detail"] = now + (1. if floating_fixture or nest or regional_water or mink_cover or eagle_fatigue
                                          or pig_followup or pig_thermal or pig_threat else 15.)
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureRepresentationActor):
            if not actor.get_editor_property("bound"):
                continue
            view = actor.get_editor_property("visual_state")
            species = kind(view)
            if species not in NEW:
                continue
            stable_id = int(view.get_editor_property("stable_agent_id"))
            p = view.get_editor_property("position")
            mesh = actor.get_editor_property("creature_mesh")
            anim = mesh.get_anim_instance()
            if pig_threat and str(stable_id) in state["pig_threat"] and view.get_editor_property("activity") == unreal.EcoSpeciesActivity.FLEE:
                speed = view.get_editor_property("velocity").length()
                if speed > 40.:
                    state["pig_threat"][str(stable_id)].setdefault("flee_speed", speed)
            row = {"species": species, "pos": [p.x, p.y, p.z], "activity": str(view.get_editor_property("activity")),
                   "energy": view.get_editor_property("normalized_energy"), "body": view.get_editor_property("body_scale"),
                   "maturity": view.get_editor_property("maturity"), "anim": anim.get_class().get_name() if anim else None}
            if isinstance(anim, unreal.EcoCreatureAnimInstance):
                row["pose"] = anim.get_editor_property("animation_index")
                row["ik"] = anim.get_editor_property("ground_ik_alpha")
            observed[str(stable_id)] = row
        with (output / f"{name}.jsonl").open("a" if state["frames"] else "w", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": now, "authority_count": len(ids),
                                     "populations": populations, "agents": observed, "authority": authority,
                                     "dead": dead, "water": water, "rainfall": rainfall}) + "\n")
        state["frames"] += 1
        if now >= seconds:
            if forage_case == "Natural" and seconds >= 120:
                rain = [row["rain"] for row in state["plant_forage"]["appearance"]]
                if min(rain) > .01 or max(rain) < .7:
                    raise RuntimeError("The owned forage map did not progress from dry weather to rain")
            if forage_case == "WeatherCycle":
                rows = state["plant_forage"]["appearance"]
                dry = min((row for row in rows if row["rain"] < .01), key=lambda row: abs(row["time"] - (forage_weather_change - 3.)))
                wet = rows[-1]
                for site in weather_forage_sites:
                    initial, dried, recovered = (row["sites"][site] for row in (rows[0], dry, wet))
                    if wet["rain"] < .8 or initial["foliage_scale"] - dried["foliage_scale"] < .12 or recovered["foliage_scale"] - dried["foliage_scale"] < .12:
                        raise RuntimeError(f"Forage did not visibly dry and recover at {site}: {initial}, {dried}, {recovered}")
                    if forage_network:
                        if not wet.get("client_revision"):
                            raise RuntimeError("PIE client never received the ecology summary")
                        client_dry, client_wet = dry.get("client", {}).get(site), wet.get("client", {}).get(site)
                        if (client_dry is None or client_wet is None or client_wet - client_dry < .12
                                or abs(client_dry - dried["fraction"]) > .04 or abs(client_wet - recovered["fraction"]) > .04):
                            raise RuntimeError(f"Client forage did not follow the server at {site}: {client_dry}, {client_wet}")
            if projectj_riparian and seconds >= 80 and max(row[1] for row in state["floating_plant_levels"]) - min(row[1] for row in state["floating_plant_levels"]) < 30.:
                raise RuntimeError("The floating vegetation check did not exercise the full rise")
            if seasonal_stock:
                samples = state["seasonal_stock"]
                if any(stock != 0. for at, stock in samples if static_water or at < 40.):
                    raise RuntimeError("Exposed seasonal food regenerated without flooding")
                if not static_water and not seasonal_feeding:
                    peak = max(stock for at, stock in samples if 70. <= at <= 100.)
                    if peak <= .5 or samples[-1][1] >= peak:
                        raise RuntimeError(f"Seasonal stock did not recover on flooding and fall after exposure: {samples}")
            if checkpoint and state["checkpoint"] is None:
                raise RuntimeError("Requested checkpoint operation did not complete")
            expected_crest = {"Dynamic": [False, True, False], "Closed": [False]}.get(crest)
            if expected_crest and state["crest_states"][:len(expected_crest)] != expected_crest:
                raise RuntimeError(f"Crest {crest}: measured {state['crest_states']}, expected {expected_crest}")
            if crest == "Closed" and any(state["crest_states"]):
                raise RuntimeError("Static low-water crest opened")
            if rain_fixture:
                dry, wet = (state["rain_observations"].get(phase) for phase in ("dry", "wet"))
                if not dry or not wet or abs(wet["surface"] - dry["surface"] - 32.) > 1.:
                    raise RuntimeError(f"Rainfall did not raise the water by 32 cm: {state['rain_observations']}")
                if dry["crest_usable"] or not wet["crest_usable"]:
                    raise RuntimeError(f"Rain did not open the crest: {state['rain_observations']}")
            if nest and bool(state["nest_children"]) != (nest != "NoSite"):
                raise RuntimeError(f"Nest {nest}: unexpected children {state['nest_children']}")
            if nest == "Return" and not state["nest_parent_returned"]:
                raise RuntimeError("Ground-level parent did not land on the nest platform")
            if nest == "Supported" and not any("Z=360.00" in child["position"] and child["phases"][0] == 0
                                              and any(phase > 0 for phase in child["phases"][1:])
                                              and child["phases"][-1] == 0
                                              for child in state["nest_children"].values()):
                raise RuntimeError(f"No hatch, departure and landing on the same ID: {state['nest_children']}")
            if regional_water:
                expected = regional_water != "Closed"
                counts = state["water_transfer_counts"]
                transfers = {(region, incoming, outgoing) for region, incoming, outgoing in counts if incoming or outgoing}
                expected_transfers = {("FaunaMeadow", 0, 1), ("FaunaWaterEast", 1, 0)} if expected else set()
                if len(state["water_arrivals"]) != int(expected) or transfers != expected_transfers:
                    raise RuntimeError(f"Regional water {regional_water}: arrivals={state['water_arrivals']} counters={counts}")
                if regional_water == "Closing" and state["crest_states"] != [True, False, True]:
                    raise RuntimeError(f"No closing and reopening was measured: {state['crest_states']}")
            if food_intent:
                intent, entry = state["food_intent"], state["mink_entry"]
                matches = intent and entry and int(entry["prey"]) == intent["target"]
                if not intent or not entry or not intent["accepted"] or not intent["malformed_rejected"] \
                        or matches != (food_intent == "Alternate"):
                    raise RuntimeError(f"Unexpected proposal outcome for {food_intent}: {intent}, entry={entry}")
            if pig_thermal:
                expected = {"Cool": None, "Dry": "PigShade", "Wet": "PigWetBank"}[pig_thermal]
                recorded = state["pig_cooling"]
                if (expected is None and recorded) or (expected is not None and expected not in recorded):
                    raise RuntimeError(f"Unexpected cooling-site use for {pig_thermal}: {recorded}")
            if pig_network and not any(len(row["revisions"]) > 1 and row["body_scale"] > 0. for row in state["pig_client"].values()):
                raise RuntimeError("PIE client did not render any authority Pig ID with its model and animation")
            if pig_threat and not any("flee_speed" in row for row in state["pig_threat"].values()):
                raise RuntimeError(f"No pig fled after a real player footstep: {state['pig_threat']}")
            if pig_followup and not checkpoint:
                founders = state["pig_founders"]
                if len(founders) != 4 or len({row["size_gene"] for row in founders.values()}) < 2:
                    raise RuntimeError(f"No individual founder variation: {founders}")
                if not any(child["largest"] > child["initial"] + .1 for child in state["pig_growth"].values()):
                    raise RuntimeError(f"No observed piglet growth: {state['pig_growth']}")
                # The author spawns alternating female and male founders in the same placement.
                female_founders = set(sorted(map(int, founders))[::2])
                male_range = 640. * .18
                female_at_range = any({a, b}.issubset(female_founders) and distance > male_range
                                      for a, b, distance in state["pig_spacing"])
                male_too_far = any(not {a, b}.issubset(female_founders) and distance > male_range + .1
                                   for a, b, distance in state["pig_spacing"])
                if not female_at_range or male_too_far:
                    raise RuntimeError(f"Unexpected founder spacing at authored distances: {state['pig_spacing']}")
            finish()
    except Exception as error:
        finish(f"{type(error).__name__}: {error}")


if author_regional_weather:
    world = editor.get_editor_world()
    owner = "JYU.ExpandedWaterPassage"
    if created_regional_map:
        unreal.EditorAssetLibrary.set_metadata_tag(world, "JYUOwner", owner)
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, REGIONAL_MAP):
            raise RuntimeError(f"Cannot save {REGIONAL_MAP}")
    if unreal.EditorAssetLibrary.get_metadata_tag(world, "JYUOwner") != owner:
        raise RuntimeError(f"Unexpected owner for {REGIONAL_MAP}")
    unreal.log(f"ECO_EXPANDED_REGIONAL_MAP_READY {REGIONAL_MAP}")
else:
    levels.editor_request_begin_play()
    handle = unreal.register_slate_post_tick_callback(tick)

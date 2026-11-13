"""Install the validated fauna and riparian setup in the owned team-terrain copy."""

import json
from pathlib import Path
import random
import traceback

import unreal as u


TARGET = "/Game/JYU/Maps/LV_JYU_IntegrationR7eFauna"
DONOR = "/Game/JYU/Maps/LV_JYU_RiparianReach"
OWNER = "JYU.IntegrationR7eAudit"
TAG = "JYU.IntegrationFauna"
REGION = "Forest"
NEW_SPECIES = {"Bighorn", "Jackrabbit", "Horse", "Mink", "GoldenEagle", "AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
PATCH_FIELDS = (
    "id", "region_id", "center", "submerged", "aquatic_nursery", "has_shore_entry", "shore_point", "water_entry_point",
    "stage", "sheltered_species", "shelter_radius", "entrance_radius", "consumers", "capacity", "regrowth_per_second",
    "plant_guild", "plant_growth_temperature", "plant_growth_rainfall", "plant_moisture_need", "plant_dry_loss_per_second",
    "seasonal_full_growth_depth_cm", "seasonal_dry_loss_per_second", "energy_per_meal",
)
editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
actors = u.get_editor_subsystem(u.EditorActorSubsystem)
assets = u.EditorAssetLibrary
wp = u.WorldPartitionBlueprintLibrary


def get(obj, field):
    return obj.get_editor_property(field)


def put(obj, **fields):
    for field, value in fields.items():
        obj.set_editor_property(field, value)


def actor_list(cls):
    return [actor for actor in actors.get_all_level_actors() if isinstance(actor, cls)]


def transform_at(transform, position):
    return u.Transform(location=position, rotation=transform.rotation.rotator(), scale=transform.scale3d)


def unit_transform(position):
    return u.Transform(location=position, rotation=u.Rotator(), scale=u.Vector(1., 1., 1.))


def mesh_slots(component):
    return [component.get_material(i) for i in range(component.get_num_materials())]


def runtime():
    spawners = actor_list(u.EcoCreatureIntegrationSpawner)
    if len(spawners) != 1:
        raise RuntimeError(f"Expected one ecosystem spawner, found {len(spawners)}")
    return spawners[0]


def donor_snapshot():
    if not levels.load_level(DONOR):
        raise RuntimeError(f"Cannot load {DONOR}")
    source = runtime()
    result = {key: list(get(source, key)) for key in ("fauna_species",)}
    result["footstep_audio_set"] = get(source, "footstep_audio_set")
    result["patches"] = [{key: get(p, key) for key in PATCH_FIELDS} for p in get(source, "fauna_habitat_patches")]
    for p in result["patches"]:
        p["consumers"] = list(p["consumers"])
    group, = list(get(source, "groups"))
    result["placements"] = {str(get(row, "species_id")): list(get(row, "spawn_points"))
                            for row in get(group, "fauna") if str(get(row, "species_id")) in NEW_SPECIES}
    result["forage"] = []
    for a in actor_list(u.EcoForagePatchVisual):
        components = [get(a, key) for key in ("plants", "woody_stems")]
        result["forage"].append((a.get_class(), str(get(a, "patch_id")), a.get_actor_location(),
                                 list(get(a, "full_plant_transforms")), get(a, "residual_height_fraction"),
                                 get(a, "keep_woody_stems"),
                                 [(get(c, "static_mesh"), mesh_slots(c), get(c, "cast_shadow")) for c in components]))
    result["foliage"] = {}
    types = {get(t, "mesh").get_path_name(): t for path in assets.list_assets("/Game/JYU/Riparian", recursive=False)
             if "/FT_JYU_Reach" in path for t in (assets.load_asset(path),) if t}
    for a in actor_list(u.InstancedFoliageActor):
        for c in a.get_components_by_class(u.InstancedStaticMeshComponent):
            mesh = get(c, "static_mesh")
            foliage_type = types.get(mesh.get_path_name()) if mesh else None
            if foliage_type and c.get_instance_count():
                result["foliage"].setdefault(foliage_type, []).extend(
                    c.get_instance_transform(i, True) for i in range(c.get_instance_count()))
    if set(result["placements"]) != NEW_SPECIES or len(result["forage"]) != 17:
        raise RuntimeError("The saved riparian donor is incomplete")
    if len(result["foliage"]) != 13 or sum(map(len, result["foliage"].values())) != 128:
        raise RuntimeError("Expected 110 scenery instances and 18 trees")
    return result


def load_target():
    if not levels.load_level(TARGET):
        raise RuntimeError(f"Cannot load {TARGET}")
    world = editor.get_editor_world()
    if assets.get_metadata_tag(world, "EcoAuditOwner") != OWNER:
        raise RuntimeError(f"Unexpected owner for {world.get_path_name()}")
    descs = wp.get_actor_descs()
    external_root = "/Game/__ExternalActors__/JYU/Maps/LV_JYU_IntegrationR7eFauna/"
    if not descs or any(not str(get(row, "actor_package")).startswith(external_root) for row in descs):
        raise RuntimeError("The target external actors are not isolated")
    wp.load_actors([get(row, "guid") for row in descs])
    return world


def ground(world, point):
    result = u.EcoCreatureAnimationBuilder.project_placement_point(world, point)
    if result is None:
        raise RuntimeError(f"No ground at {point}")
    return result


def spawn(cls, label, transform):
    actor = actors.spawn_actor_from_class(cls, transform.translation, transform.rotation.rotator())
    if not actor:
        raise RuntimeError(f"Could not place {label}")
    actor.set_actor_label(label)
    actor.set_actor_scale3d(transform.scale3d)
    put(actor, tags=[TAG])
    return actor


def main():
    donor = donor_snapshot()
    world = load_target()
    spawner = runtime()
    groups = list(get(spawner, "groups"))
    forest, = [g for g in groups if str(get(g, "region_id")) == REGION]
    for actor in actors.get_all_level_actors():
        if any(str(tag) == TAG for tag in get(actor, "tags")):
            actors.destroy_actor(actor)
    result = author_existing_lake(world, spawner, groups, forest, donor)
    assets.set_metadata_tag(world, "EcoIntegratedFauna", TAG)
    if not levels.save_current_level():
        raise RuntimeError(f"Could not save {TARGET}")
    out = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit/IntegrationFaunaAuthoring.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    u.log(f"ECO_INTEGRATION_FAUNA_AUTHORED {result}")


def author_existing_lake(world, spawner, groups, forest, donor):
    rng = random.Random(6841)
    markers = {a.get_actor_label(): a.get_actor_location() for a in actor_list(u.TargetPoint)}
    west, east = markers["TP_Water_02"], markers["TP_Water_01"]
    if abs(west.z - east.z) > 1.:
        raise RuntimeError("Existing east lake markers disagree on surface elevation")
    level = west.z
    # The ground trough begins west of the actual rendered shoreline. The visible lake
    # edge is surveyed independently, then each authored point is placed on collision.
    bank = ((50600., 41440.), (51500., 41010.), (52400., 40920.), (53300., 40960.),
            (54200., 41150.), (55100., 41640.))
    def p(x, y, depth=0.):
        return u.Vector(float(x), float(y), level - depth)

    def floor(x, y):
        return ground(world, p(x, y))

    def wet(x, y, above_bed=30.):
        bottom = floor(x, y)
        if bottom.z + above_bed > level - 9.:
            raise RuntimeError(f"Insufficient water at {x}, {y}")
        return bottom + u.Vector(0., 0., above_bed)

    def shoreline(y):
        for (lo_y, lo_x), (hi_y, hi_x) in zip(bank, bank[1:]):
            if y <= hi_y:
                alpha = max(0., (y - lo_y) / (hi_y - lo_y))
                return floor(lo_x + (hi_x - lo_x) * alpha, y)
        return floor(bank[-1][1], y)

    def place_ground(x, y, height=level):
        for dx, dy in ((0., 0.), (90., 0.), (-90., 0.), (0., 100.), (0., -100.), (180., 100.), (-180., -100.)):
            point = u.EcoCreatureAnimationBuilder.project_placement_point(world, u.Vector(x + dx, y + dy, height))
            if point is not None:
                return point
        raise RuntimeError(f"No walkable founding site near {x}, {y}")

    # These overlapping logical windows cover only sampled ground on the west side.
    # The level's existing lake is the sole visible surface. Neither window draws a plane.
    for label, x, y, ex, ey, flow, cover in (
        ("Forest Lake West Water", 42600, 53200, 1150, 2100, 1.1, .12),
        ("Forest Lake West Littoral", 41900, 53200, 350, 1750, .35, .62),
    ):
        a = spawn(u.EcoVegetationHabitat, label, unit_transform(p(x, y, 180.)))
        get(a, "bounds").set_box_extent(u.Vector(ex, ey, 500.), False)
        put(a, habitat_id=label.replace(" ", ""), region_id=REGION, connected_fresh_water=True,
            supports_fauna_swimming=True, draw_water_surface=False, water_surface_z=level,
            water_surface_size_cm=u.Vector2D(800., 800.), fauna_water_current=u.Vector(flow, 0., 0.),
            priority=10 if cover > .5 else 0, plant=1, fauna_water_cover_density=cover,
            fauna_water_cover_height_cm=45., is_spatially_loaded=False)
        if not a.is_valid_habitat():
            raise RuntimeError(f"Invalid lake habitat {label}")

    for foliage_type in donor["foliage"]:
        u.InstancedFoliageActor.remove_all_instances(world, foliage_type)
    foliage_count = 0
    # Leave breaks for the open bank and separate wet vegetation from the upper canopy.
    clusters = ((51200., 380.), (52940., 480.), (54650., 330.))
    for foliage_type in donor["foliage"]:
        mesh = get(foliage_type, "mesh")
        name = mesh.get_name()
        if name in ("SM_AutumnTree02", "SM_Birch"):
            heights, setback, counts = (340., 540.), (-850., -280.), (4, 0, 5)
        elif "Cattail" in name:
            heights, setback, counts = (65., 112.), (-80., 70.), (3, 7, 2)
        elif "Seaweed" in name:
            heights, setback, counts = (22., 37.), (680., 1220.), (5, 2, 6)
        elif name in ("SM_GrassSky03", "SM_ForestShrub02") or "fern" in name:
            heights, setback, counts = (32., 83.), (-670., -150.), (4, 2, 5)
        else:
            continue
        box = mesh.get_bounding_box()
        transforms = []
        for (center, spread), count in zip(clusters, counts):
            for _ in range(count):
                y = center + rng.uniform(-spread, spread)
                edge = shoreline(y)
                base = floor(edge.x + rng.uniform(*setback), y)
                depth = level - base.z
                if "Seaweed" in name and not 55. <= depth <= 480.:
                    continue
                scale = rng.uniform(*heights) / (box.max.z - box.min.z)
                # The rendered lake edge and collision shelf diverge here. Keep the emergent
                # props on the exposed visual bank when the bed is too deep for their height.
                if "Cattail" in name and depth > 60. and base.x > edge.x - 60.:
                    base = floor(edge.x - 120., y)
                transforms.append(u.Transform(location=base - u.Vector(0., 0., box.min.z * scale),
                                              rotation=u.Rotator(yaw=rng.uniform(-180., 180.)), scale=u.Vector(scale, scale, scale)))
        if transforms:
            u.InstancedFoliageActor.add_instances(world, foliage_type, transforms)
            foliage_count += len(transforms)

    placements = {REGION: {
        "AriakeCatfish": [wet(42100., 52300., 25.), wet(42400., 52600., 31.), wet(42540., 52920., 22.)],
        "CommonCarp": [wet(x, y, z) for x, y, z in ((42800., 53800., 60.), (42930., 53730., 88.), (43100., 54000., 69.),
                                                     (42700., 53970., 98.), (43220., 54140., 77.), (42950., 54270., 62.))],
        "UnidentifiedFish": [wet(x, y, z) for x, y, z in ((41820., 52150., 80.), (41890., 52210., 89.), (41960., 52160., 100.),
                                                          (41845., 52315., 70.), (41945., 52385., 115.), (42040., 52290., 95.),
                                                          (41880., 52515., 105.))],
        "Mink": [floor(40550., 52750.), floor(40620., 53550.)],
        "Horse": [place_ground(x, y) for x, y in ((39940., 51680.), (39720., 51770.), (40080., 51840.),
                                                   (39870., 52080.), (40110., 52150.))],
        "Jackrabbit": [place_ground(40200., 54900.), place_ground(39660., 55540.)],
        "GoldenEagle": [floor(34900., 51500.), floor(35000., 52000.)],
    }}
    upland = next(g for g in groups if str(get(g, "region_id")) == "Highland")
    anchor = get(upland, "herbivore_spawn_points")[0]
    placements["Highland"] = {
        "Bighorn": [place_ground(anchor.x + x, anchor.y + y, anchor.z) for x, y in
                    ((-580., 820.), (-370., 770.), (-180., 960.), (-280., 1150.), (-730., 1080.))],
        "Jackrabbit": [place_ground(anchor.x + x, anchor.y + y, anchor.z) for x, y in
                       ((1200., 1500.), (2110., 930.), (1600., 320.))],
    }
    for group in groups:
        region = str(get(group, "region_id"))
        rows = [row for row in get(group, "fauna") if str(get(row, "species_id")) not in NEW_SPECIES]
        for kind, points in sorted(placements.get(region, {}).items()):
            row = u.EcoFaunaPlacement()
            put(row, species_id=kind, spawn_points=points)
            rows.append(row)
        put(group, fauna=rows)
    schedule = get(forest, "schedule")
    put(schedule, region_population_limit=max(96, get(schedule, "region_population_limit")))
    put(forest, schedule=schedule)

    patches = [q for q in get(spawner, "fauna_habitat_patches")
               if not str(get(q, "id")).startswith(("RiparianReach", "ForestLake"))]
    fields_by_id = {str(fields["id"]): fields for fields in donor["patches"]}
    points = {"Gravel": wet(42100., 52300., 27.), "Macrophytes": wet(42800., 53850., 44.),
              "Littoral": wet(41900., 52600., 23.), "DriftingInsects": p(42000., 52900., 20.)}
    for suffix, center in points.items():
        patch = u.EcoFaunaHabitatPatch()
        put(patch, **dict(fields_by_id["RiparianReach" + suffix], id="ForestLake" + suffix, region_id=REGION, center=center))
        patches.append(patch)
    for index, y in enumerate((52500., 54600.), 1):
        # Keep the feeding points, but leave the bank crossing unset until the
        # visual water and the existing landscape meet within the amphibious step limit.
        edge = shoreline(y)
        patch = u.EcoFaunaHabitatPatch()
        put(patch, id=f"ForestLakeMinkFood{index}", region_id=REGION,
            center=wet(max(41900., edge.x + 820.), y, 18.), submerged=True, stage=1,
            consumers=["Mink", "AriakeCatfish"], capacity=12., regrowth_per_second=.16, energy_per_meal=3.)
        patches.append(patch)
    sites = [row for row in donor["forage"] if row[1].startswith("RiparianReachForage")]
    bank_sites = ((50850., 510.), (51130., 810.), (51680., 460.), (51900., 1010.), (52250., 350.), (52440., 710.),
                  (52880., 970.), (53780., 570.), (54090., 870.), (54410., 410.), (54770., 770.), (55100., 480.))
    upland_sites = ((-540., 980.), (-340., 1270.), (1280., 1420.), (1990., 900.))
    for index, (cls, name, _, transforms, residual, woody, components) in enumerate(sites):
        if index < len(bank_sites):
            y, setback = bank_sites[index]
            x = min(41320., shoreline(y).x - setback)
            center = place_ground(x, y)
            region = REGION
        else:
            dx, dy = upland_sites[index - len(bank_sites)]
            center = place_ground(anchor.x + dx, anchor.y + dy, anchor.z)
            region = "Highland"
        patch_id = name.replace("RiparianReach", "ForestLake")
        patch = u.EcoFaunaHabitatPatch()
        put(patch, **dict(fields_by_id[name], id=patch_id, region_id=region, center=center))
        patches.append(patch)
        mesh = components[0][0]
        adapted = []
        for transform in transforms:
            t = transform.translation
            position = place_ground(center.x + t.x, center.y + t.y, center.z) - center
            position.z -= mesh.get_bounding_box().min.z * transform.scale3d.z
            adapted.append(transform_at(transform, position))
        a = spawn(cls, patch_id, unit_transform(center))
        put(a, patch_id=patch_id, full_plant_transforms=adapted, residual_height_fraction=residual,
            keep_woody_stems=woody, is_spatially_loaded=False)
        for field, (static_mesh, materials, shadows) in zip(("plants", "woody_stems"), components):
            c = get(a, field)
            c.set_static_mesh(static_mesh)
            c.set_cull_distances(2100, 3300)
            c.set_cast_shadow(shadows)
            for i, material in enumerate(materials):
                c.set_material(i, material)
        a.rebuild_forage_preview()

    profiles = {str(get(profile, "species_id")): profile for profile in get(spawner, "fauna_species")}
    for profile in donor["fauna_species"]:
        if str(get(profile, "species_id")) in NEW_SPECIES or str(get(profile, "species_id")) == "Fox":
            profiles[str(get(profile, "species_id"))] = profile
    put(spawner, groups=groups, fauna_species=list(profiles.values()), fauna_habitat_patches=patches,
        fauna_perches=[row for row in get(spawner, "fauna_perches") if str(get(row, "species_id")) != "GoldenEagle"],
        footstep_audio_set=donor["footstep_audio_set"], fauna_habitat_stage=max(1, get(spawner, "fauna_habitat_stage")),
        global_population_limit=max(128, get(spawner, "global_population_limit")))
    return {"map": TARGET, "region": REGION, "lake_surface_cm": level, "profiles": len(profiles),
            "forage_visuals": len(sites), "water_habitats": 2, "foliage_instances": foliage_count,
            "founders_by_region": {region: {kind: len(points) for kind, points in rows.items()} for region, rows in placements.items()},
            "mink_entries": sum(str(get(row, "id")).startswith("ForestLakeMinkEntry") for row in patches),
            "water_samples": {key: [v.x, v.y, v.z] for key, v in points.items()}}


if __name__ == "__main__":
    try:
        main()
    except Exception:
        u.log_error(traceback.format_exc())
    finally:
        u.SystemLibrary.quit_editor()

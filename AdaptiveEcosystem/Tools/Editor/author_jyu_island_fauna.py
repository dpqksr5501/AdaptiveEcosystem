"""Add fauna and forage to the owned World Partition copy of the team island."""

from collections import Counter
import json
import math
from pathlib import Path
import random
import runpy
import traceback

import unreal as u


common = runpy.run_path(str(Path(__file__).with_name("author_jyu_integration_fauna.py")))
get, put, transform_at = (common[key] for key in ("get", "put", "transform_at"))
editor, levels, actors, wp = (common[key] for key in ("editor", "levels", "actors", "wp"))
TARGET = "/Game/JYU/Maps/LV_JYU_IslandEcosystem"
TAG = "JYU.IslandFauna"
REPORT = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit/IslandFaunaAuthoring.json"


def v(x, y, z):
    return u.Vector(float(x), float(y), float(z))


def spawn(cls, label, point):
    actor = actors.spawn_actor_from_class(cls, point)
    if not actor:
        raise RuntimeError(f"Unable to place {label}")
    actor.set_actor_label(label)
    put(actor, tags=[TAG], is_spatially_loaded=False)
    return actor


def all_actors(cls):
    return common["actor_list"](cls)


def bed_at(world, point):
    hits = u.SystemLibrary.line_trace_multi_for_objects(world, point + v(0, 0, 350), point - v(0, 0, 1100),
        [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True) or []
    for hit in hits:
        data = hit.to_tuple()
        component = data[10]
        if component and "Landscape" in component.get_class().get_name():
            return data[5]
    return None


def dry_ground(world, point, radius=0., clearance=30.):
    """Reject ground below any existing water collision across the entire footprint."""
    offsets = [v(0, 0, 0)]
    for ring in range(1, math.ceil(radius / 220.) + 1):
        distance = min(radius, ring * 220.)
        steps = max(8, math.ceil(math.tau * distance / 220.))
        offsets.extend(v(distance * math.cos(i * math.tau / steps), distance * math.sin(i * math.tau / steps), 0)
                       for i in range(steps))
    for offset in offsets:
        position = point + offset
        hits = u.SystemLibrary.line_trace_multi_for_objects(world, position + v(0, 0, 1400), position - v(0, 0, 1800),
            [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True) or []
        ground_z, water_z = None, float("-inf")
        for hit in hits:
            data = hit.to_tuple()
            component = data[10]
            if not component:
                continue
            if "Landscape" in component.get_class().get_name() and ground_z is None:
                ground_z = data[5].z
            if component.get_owner().get_class().get_name().startswith("WaterBody"):
                water_z = max(water_z, data[5].z)
        if ground_z is None or ground_z <= water_z + clearance:
            return False
    return True


def ground(world, point):
    for dx, dy in ((0, 0), (-100, 0), (100, 0), (0, 100), (0, -100), (-200, 80), (200, -80)):
        adjusted = point + v(dx, dy, 0)
        place = u.EcoCreatureAnimationBuilder.project_placement_point(world, adjusted)
        if place is not None:
            return place
    raise RuntimeError(f"No spawn ground at {point}")


def river_frames(world, river):
    spline = river.get_component_by_class(u.SplineComponent)
    length = spline.get_spline_length()
    # Cross-sections across the upstream freshwater reach. The estuary and waterfall are outside it.
    frames = []
    for fraction in (.055, .075, .095, .115, .135, .155, .175, .195, .215, .235):
        distance = fraction * length
        center = spline.get_location_at_distance_along_spline(distance, u.SplineCoordinateSpace.WORLD)
        tangent = spline.get_direction_at_distance_along_spline(distance, u.SplineCoordinateSpace.WORLD)
        side = v(-tangent.y, tangent.x, 0)
        bed = bed_at(world, center)
        if bed is None or not 55. < center.z - bed.z < 350.:
            raise RuntimeError(f"Unexpected river depth at {center}")
        frames.append((center, tangent, side, bed.z))
    return frames


def lake_shore(world, lake):
    spline = lake.get_component_by_class(u.SplineComponent)
    level = lake.get_actor_location().z
    center, _ = lake.get_actor_bounds(False)
    result = []
    length = spline.get_spline_length()
    sections = max(10, min(36, math.ceil(length / 1800.)))
    for index in range(sections):
        edge = spline.get_location_at_distance_along_spline(length * (index + .5) / sections, u.SplineCoordinateSpace.WORLD)
        direction = v(edge.x - center.x, edge.y - center.y, 0)
        direction = direction / direction.length()
        result.append((v(edge.x, edge.y, level), direction))
    return result


def find_shore(world, surface, outward, first, last):
    """Find the first wet-to-dry terrain transition in this cross-section."""
    wet = None
    for offset in range(first, last + 1, 80):
        bed = bed_at(world, surface + outward * offset)
        if bed is None:
            continue
        if bed.z < surface.z - 8.:
            wet = offset
        elif wet is not None:
            return surface + outward * ((wet + offset) * .5)
    return None


def water_habitat(label, region, center, extent, rotation, flow, cover):
    actor = spawn(u.EcoVegetationHabitat, label, center - v(0, 0, 100))
    actor.set_actor_rotation(rotation, False)
    get(actor, "bounds").set_box_extent(extent, False)
    put(actor, habitat_id=label, region_id=region, connected_fresh_water=True, supports_fauna_swimming=True,
        draw_water_surface=False, water_surface_z=center.z, water_surface_size_cm=u.Vector2D(800., 800.),
        fauna_water_current=flow, fauna_water_temperature_c=18.5, priority=20, plant=1,
        fauna_water_cover_density=cover, fauna_water_cover_height_cm=35.)
    if not actor.is_valid_habitat():
        raise RuntimeError(f"Invalid authored habitat {label}")


def forage_visual(world, template, name, center):
    cls, _, _, transforms, residual, woody, components = template
    mesh = components[0][0]
    mapped = []
    for transform in transforms:
        delta = transform.translation
        point = ground(world, center + v(delta.x * 1.7, delta.y * 1.7, 0)) - center
        point.z -= mesh.get_bounding_box().min.z * transform.scale3d.z
        mapped.append(transform_at(transform, point))
    actor = spawn(cls, name, center)
    put(actor, patch_id=name, full_plant_transforms=mapped, residual_height_fraction=residual, keep_woody_stems=woody)
    for field, (mesh, materials, shadow) in zip(("plants", "woody_stems"), components):
        component = get(actor, field)
        component.set_static_mesh(mesh)
        component.set_cull_distances(3300, 5200)
        component.set_cast_shadow(shadow)
        for i, material in enumerate(materials):
            component.set_material(i, material)
    actor.rebuild_forage_preview()


def dress_banks(world, donor, frames, lakes, rng):
    counts = Counter()
    shores = []
    for surface, _, side, _ in frames:
        for outward in (side, side * -1.):
            edge = find_shore(world, surface, outward, 0, 5800)
            if edge is not None:
                shores.append((edge, outward))
                counts["river_banks"] += 1
    for lake in lakes:
        for surface, outward in lake:
            edge = find_shore(world, surface, outward, -1440, 960)
            if edge is not None:
                shores.append((edge, outward))
                counts["lake_banks"] += 1
    for foliage_type in donor["foliage"]:
        u.InstancedFoliageActor.remove_all_instances(world, foliage_type)
        mesh = get(foliage_type, "mesh")
        name = mesh.get_name()
        if "Cattail" in name:
            size, mode = (70., 135.), "emergent"
        elif "Seaweed" in name:
            size, mode = (25., 62.), "submerged"
        elif name in ("SM_Birch", "SM_AutumnTree02"):
            size, mode = (310., 620.), "canopy"
        elif "Fern" in name or "fern" in name or name in ("SM_GrassSky03", "SM_ForestShrub02"):
            size, mode = (25., 105.), "buffer"
        elif "Stone" in name or "Roots" in name or "WoodenLogs" in name:
            size, mode = (50., 160.), "structure"
        else:
            continue
        box = mesh.get_bounding_box()
        transforms = []
        for index, (surface, side) in enumerate(shores):
            if (index + len(name)) % 5 == 0:
                continue
            alpine = surface.z > 1000.
            if alpine and (mode == "canopy" or (mode == "buffer" and "fern" in name.lower())):
                continue
            if mode == "emergent":
                offsets, depth_range, quantity = (-520., 80.), (-12., 125.), rng.randint(18, 36)
            elif mode == "submerged":
                offsets, depth_range, quantity = (-1250., -80.), (45., 280.), rng.randint(22, 43)
            elif mode == "structure":
                offsets, depth_range, quantity = (-320., 240.), (-80., 140.), rng.randint(1, 3)
            else:
                offsets = (120., 1700.) if mode == "buffer" else (350., 1900.)
                depth_range, quantity = (-700., -16.), rng.randint(5, 13) if mode == "buffer" else rng.randint(1, 5)
            if alpine and mode in ("buffer", "emergent"):
                quantity = max(1, quantity // 3)
            along = v(-side.y, side.x, 0)
            for _ in range(quantity):
                for _attempt in range(8):
                    location = surface + side * rng.uniform(*offsets) + along * rng.uniform(-620., 620.)
                    bed = bed_at(world, location)
                    if bed is None or not depth_range[0] <= surface.z - bed.z <= depth_range[1]:
                        continue
                    if mode in ("canopy", "buffer") and not dry_ground(world, bed, 65. if mode == "canopy" else 0., 25.):
                        continue
                    dimension = (box.max.z - box.min.z if mode != "structure" else
                                 max(box.max.x - box.min.x, box.max.y - box.min.y, box.max.z - box.min.z))
                    height = rng.uniform(*size)
                    if mode == "emergent":
                        height = max(height, surface.z - bed.z + rng.uniform(45., 90.))
                    elif alpine and mode == "buffer":
                        height *= .55
                    scale = height / dimension
                    transforms.append(u.Transform(location=bed - v(0, 0, box.min.z * scale),
                        rotation=u.Rotator(yaw=rng.uniform(-180., 180.)), scale=v(scale, scale, scale)))
                    break
        if mode == "submerged":
            for index, cross in ((1, -320.), (2, 330.), (5, -260.), (6, 385.), (9, -380.)):
                surface, tangent, side, _ = frames[index]
                for _ in range(rng.randint(25, 40)):
                    point = surface + side * (cross + rng.uniform(-160., 160.)) + tangent * rng.uniform(-640., 640.)
                    bed = bed_at(world, point)
                    if bed is None or not 65. <= surface.z - bed.z <= 235.:
                        continue
                    scale = rng.uniform(32., 69.) / (box.max.z - box.min.z)
                    transforms.append(u.Transform(location=bed - v(0, 0, box.min.z * scale),
                        rotation=u.Rotator(yaw=rng.uniform(-180., 180.)), scale=v(scale, scale, scale)))
        if transforms:
            u.InstancedFoliageActor.add_instances(world, foliage_type, transforms)
            counts[mode] += len(transforms)
    return dict(counts)


def author_dry_refuges(world, groups):
    positions = []
    brush = u.load_asset("/Game/Map_Resource/SkyTown/Meshes/SM_ForestShrub02")
    rock = u.load_asset("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Cover/SM_MWAM_StoneB")
    for region_id in ("Snowfield", "Grassland", "Riverbank", "Highland"):
        center = get(groups[region_id], "food_patch_position")
        candidates = ((-2250,-1100),(1900,-1600),(-1700,1900),(1900,1700),(-2300,400),(1800,250))
        count = 0
        for dx, dy in candidates:
            point = u.EcoCreatureAnimationBuilder.project_placement_point(world, center + v(dx,dy,0))
            if point is None or not dry_ground(world, point, 1040., 65.):
                continue
            if any((point - previous).length() < 2350. for previous in positions):
                continue
            actor = spawn(u.EcoRefugeHabitat, f"IslandDryRefuge_{region_id}_{count}", point)
            put(actor, radius=860., quality=.65, capacity=4, natural_layout=True,
                brush_mesh=brush, boulder_mesh=rock, natural_boulder_count=4 if region_id in ("Snowfield","Highland") else 2,
                brush_height=95. if region_id in ("Snowfield","Highland") else 137., layout_seed=731 + len(positions)*43)
            actor.rebuild_habitat()
            positions.append(point)
            count += 1
            if count == 2:
                break
    return positions


def author():
    donor = common["donor_snapshot"]()
    if not levels.load_level(TARGET):
        raise RuntimeError(TARGET)
    world = editor.get_editor_world()
    descs = wp.get_actor_descs()
    prefix = "/Game/__ExternalActors__/JYU/Maps/LV_JYU_IslandEcosystem/"
    if not descs or any(not str(get(desc, "actor_package")).startswith(prefix) for desc in descs):
        raise RuntimeError("World Partition actors are not isolated in the owned island copy")
    wp.load_actors([get(desc, "guid") for desc in descs])
    for actor in actors.get_all_level_actors():
        if actor.actor_has_tag(TAG):
            actors.destroy_actor(actor)
    runtime = common["runtime"]()
    group_list = list(get(runtime, "groups"))
    groups = {str(get(g, "region_id")): g for g in group_list}
    existing = {a.get_actor_label(): a for a in actors.get_all_level_actors()}
    frames = river_frames(world, existing["WaterBodyRiver"])
    lakes = [lake_shore(world, existing[name]) for name in ("WaterBodyLake", "WaterBodyLake2")]
    rng = random.Random(41293)
    river_region = "LowerRiver"
    first, last = frames[0][0], frames[-1][0]
    anchor = (first + last) * .5 + v(0, 0, 200)
    env = u.RegionEnvironmentState()
    put(env, temperature=16., humidity=.69, rainfall=.35)
    region = spawn(u.EcologyRegion, river_region, anchor)
    put(region, region_id=river_region, environment_state=env, initial_food_amount=350., food_capacity=600., food_regeneration_rate=1.3)
    get(region, "region_bounds").set_box_extent(v(abs(last.x-first.x)*.5+2200, 6600, 1200), False)
    group = groups.get(river_region) or u.EcoCreatureSpawnGroup()
    put(group, region_id=river_region, herbivores=0, wolves=0, rules_only=True)
    groups[river_region] = group
    # Keep the existing Native stage and deer policy untouched. This reach has its own rules-only roster.
    for i, (center, tangent, _, _) in enumerate(frames):
        half_length = (frames[min(i + 1, len(frames)-1)][0] - frames[max(0, i - 1)][0]).length()
        half_length = max(720., half_length * (.54 if i in (0, len(frames)-1) else .29))
        speed = (12., 7., 4., 9., 14., 5., 3., 8., 11., 5.)[i]
        water_habitat(f"IslandLowerRiver{i:02d}", river_region, center, v(half_length, 420., 350.),
                      u.MathLibrary.find_look_at_rotation(v(0, 0, 0), v(tangent.x, tangent.y, 0)),
                      v(tangent.x*speed, tangent.y*speed, 0), .62 if i in (2, 5, 6, 9) else .18)

    def river_point(index, cross, height):
        surface, _, side, _ = frames[index]
        point = surface + side * cross
        bed = bed_at(world, point)
        if bed is None or point.z - bed.z < height + 12.:
            raise RuntimeError(f"River point has inadequate depth at {point}")
        return bed + v(0, 0, height)

    def bank(index, side_sign):
        surface, _, side, _ = frames[index]
        for sign in (side_sign, -side_sign):
            for width in (580., 760., 1000., 1300., 1650., 2100., 2900., 3900., 5200.):
                point = surface + side * (sign * width)
                bed = bed_at(world, point)
                if bed is not None and bed.z >= surface.z - 35.:
                    projection = u.EcoCreatureAnimationBuilder.project_placement_point(world, bed)
                    if projection is not None and abs(projection.z - bed.z) < 15.:
                        return projection
        raise RuntimeError(f"No usable river bank at frame {index}")

    roster = {river_region: {
        "AriakeCatfish": [river_point(i, side, z) for i, side, z in ((2,-70.,25.),(5,100.,27.),(6,-120.,28.))],
        "CommonCarp": [river_point(i, side, z) for i, side, z in ((0,-115.,58.),(0,10.,62.),(0,120.,68.),(1,-130.,59.),(1,20.,70.),(1,145.,65.))],
        "UnidentifiedFish": [river_point(i, side, z) for i, side, z in ((5,60.,95.),(5,140.,88.),(5,200.,83.),(6,25.,96.),(6,80.,101.),(6,135.,95.),(6,195.,87.))],
        "Mink": [bank(2, -1.), bank(7, 1.)]},
        "Grassland": {"Horse": [ground(world, get(groups["Grassland"], "food_patch_position") + v(x,y,0)) for x,y in
                               ((-1350,-970),(-920,-780),(-530,-540),(-800,-270),(-1260,-430))]},
        "Highland": {"Bighorn": [ground(world, get(groups["Highland"], "food_patch_position") + v(x,y,0)) for x,y in
                                ((-550,-500),(-350,-570),(-200,-430),(-360,-220),(-650,-290))],
                     "GoldenEagle": [ground(world, get(groups["Highland"], "food_patch_position") + v(x,y,0)) for x,y in ((-1200,500),(1400,900))]},
        "Riverbank": {"Jackrabbit": [ground(world, get(groups["Riverbank"], "food_patch_position") + v(x,y,0)) for x,y in
                                  ((-900,-420),(720,-800),(-500,1400),(1150,900))]},
    }
    donor_profiles = {str(get(p, "species_id")): p for p in donor["fauna_species"]}
    land = get(groups["Grassland"], "food_patch_position")
    scrub = get(groups["Riverbank"], "food_patch_position")
    for region_id, center, species in (("Grassland",land,(("Pig",4),("Buffalo",4),("Crow",3))),
                                       ("Riverbank",scrub,(("Fox",2),("Rat",6),("Leopard",1)))):
        rows = roster[region_id]
        for order, (kind, count) in enumerate(species):
            rows[kind] = [ground(world, center + v(650. + 460. * order + (index % 2) * 360. + rng.uniform(-90., 90.),
                                                  450. + 420. * order + (index // 2) * 360. + rng.uniform(-90., 90.), 0))
                          for index in range(count)]
    for region_id, group in groups.items():
        placements = []
        for kind, points in sorted(roster.get(region_id, {}).items()):
            row = u.EcoFaunaPlacement()
            put(row, species_id=kind, spawn_points=points)
            placements.append(row)
        schedule = get(group, "schedule")
        put(schedule, region_population_limit=max(48, get(schedule, "region_population_limit")))
        put(group, fauna=placements, schedule=schedule)

    stock = []
    samples = {}
    for name, index, side, height, consumers, nursery in (
        ("InletPlants",0,-120.,56.,["CommonCarp"],True), ("QuietMargin",1,140.,55.,["CommonCarp","UnidentifiedFish"],True),
        ("GravelInsects",2,-110.,27.,["AriakeCatfish"],False), ("Roots",5,140.,26.,["AriakeCatfish","Mink"],True),
        ("Drift",6,120.,91.,["UnidentifiedFish","CommonCarp"],False), ("SlowShelf",9,-115.,57.,["CommonCarp","UnidentifiedFish"],True),
    ):
        point = river_point(index, side, height)
        patch = u.EcoFaunaHabitatPatch()
        put(patch, id="IslandRiver"+name, region_id=river_region, center=point, submerged=True, aquatic_nursery=nursery,
            stage=1, consumers=consumers, capacity=16. if nursery else 11., regrowth_per_second=.18 if nursery else .13, energy_per_meal=2.8)
        stock.append(patch)
        samples[name] = [point.x,point.y,point.z]
    templates = {row[1]: row for row in donor["forage"]}
    fields = {str(row["id"]): row for row in donor["patches"]}
    forage = (
        (river_region,bank(1,1.),"NorthSedges"), (river_region,bank(4,-1.),"SouthBrowse"),
        (river_region,bank(7,1.),"NorthForbs"), (river_region,bank(9,-1.),"EastSedges"),
        ("Grassland",land+v(-850,-430,0),"WestMeadow"),("Grassland",land+v(-380,-180,0),"OpenMeadow"),
        ("Grassland",land+v(780,510,0),"FloodplainApproach"),("Grassland",land+v(390,1070,0),"ApproachForbs"),
        ("Highland",get(groups["Highland"],"food_patch_position")+v(-540,-500,0),"UplandForbs"),
        ("Highland",get(groups["Highland"],"food_patch_position")+v(50,-550,0),"ScrubBrowse"),
        ("Riverbank",scrub+v(-720,-180,0),"WestBrowse"),("Riverbank",scrub+v(640,850,0),"WestForbs"),
    )
    for region_id, hint, suffix in forage:
        point = ground(world, hint)
        if not dry_ground(world, point, 170., 25.):
            point = next((candidate for dx, dy in ((-450,0),(450,0),(0,-450),(0,450),(-850,350),(850,-350))
                          if (candidate := u.EcoCreatureAnimationBuilder.project_placement_point(world, hint + v(dx,dy,0)))
                          is not None and dry_ground(world, candidate, 170., 25.)), None)
            if point is None:
                continue
        donor_name = "RiparianReachForage" + suffix
        name = "IslandForage" + suffix
        patch = u.EcoFaunaHabitatPatch()
        put(patch, **dict(fields[donor_name], id=name, region_id=region_id, center=point))
        stock.append(patch)
        forage_visual(world, templates[donor_name], name, point)
    scenery = dress_banks(world, donor, frames, lakes, rng)
    refuge_positions = author_dry_refuges(world, groups)
    put(runtime, groups=list(groups.values()), fauna_species=list(donor_profiles.values()), fauna_habitat_patches=stock,
        footstep_audio_set=donor["footstep_audio_set"], fauna_habitat_stage=1, global_population_limit=160,
        v3_use_authored_shelters=True)
    if not levels.save_current_level():
        raise RuntimeError("Unable to save island")
    result = {"map": TARGET, "river": river_region, "water_samples": samples, "forage": len(stock) - len(samples), "foliage": scenery,
              "dry_refuges": [[p.x,p.y,p.z] for p in refuge_positions],
              "founders": {region: {kind:len(points) for kind, points in rows.items()} for region,rows in roster.items()},
              "river_view": [first.x,first.y,first.z]}
    surface, _, side, _ = frames[2]
    edge = find_shore(world, surface, side * -1., 0, 5800)
    if edge is None:
        edge = bank(2, -1.)
    result["river_shore_view"] = [edge.x, edge.y, edge.z]
    result["lake_views"] = []
    for lake in lakes:
        surface, outward = lake[0]
        edge = find_shore(world, surface, outward, -1440, 960)
        if edge is not None:
            eye = edge + outward * 2400. + v(0, 0, 2300)
            target = edge - outward * 1800.
            result["lake_views"].append([[eye.x, eye.y, eye.z], [target.x, target.y, target.z]])
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result,indent=2),encoding="utf-8")
    u.log(f"ECO_ISLAND_FAUNA_AUTHORED {result}")


if __name__ == "__main__":
    try:
        author()
    except Exception:
        u.log_error(traceback.format_exc())
    finally:
        u.SystemLibrary.quit_editor()

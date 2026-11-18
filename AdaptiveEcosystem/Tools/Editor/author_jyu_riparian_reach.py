"""Author and verify a connected freshwater reach in an owned map copy."""

import json
import math
from pathlib import Path
import random
import runpy
import time

import unreal as u


HERE = Path(__file__).parent
BASE = runpy.run_path(str(HERE / "setup_jyu_fauna.py"))
ASSETS, ACTORS, set_props, require = (BASE[key] for key in ("ASSETS", "ACTORS", "set_props", "require"))
MESHES = runpy.run_path(str(HERE / "audit_jyu_riparian_asset_transfer.py"))["MESHES"]
LEVELS = u.get_editor_subsystem(u.LevelEditorSubsystem)
EDITOR = u.get_editor_subsystem(u.UnrealEditorSubsystem)
SOURCE = "/Game/JYU/Maps/LV_JYU_RiparianProjectJ"
MAP = "/Game/JYU/Maps/LV_JYU_RiparianReach"
BED = "/Game/JYU/Riparian/SM_JYU_RiparianReachBed"
REGION = "FaunaMeadow"
PREFIX = "JYU Reach "
OUT = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / "ExpandedFaunaImport"


def height(x, y):
    center = -4830. + 66. * math.sin((x - 3600.) / 225.)
    offset = abs(y - center)
    crest = 103. * math.exp(-((x - 4170.) / 119.) ** 2)
    bank = 150. * min(1., max(0., (offset - 150.) / 330.))
    shelf = 53. * math.exp(-((x - 3730.) / 208.) ** 2 - ((y + 4500.) / 119.) ** 2)
    edge = min(x - 2880., 5320. - x, y + 5630., -3970. - y)
    fade = min(1., max(0., edge / 125.))
    end_bank = max(0., 1. - min(abs(x - 3360.), abs(x - 4840.)) / 190.) * 148.
    return .6 + fade * max(3., 8. + crest + bank + shelf, end_bank)


def bed_mesh():
    if ASSETS.does_asset_exist(BED):
        return require(BED)
    xs, ys = list(range(2880, 5321, 20)), list(range(-5630, -3969, 20))
    mesh = u.DynamicMesh()
    buffers = u.GeometryScriptSimpleMeshBuffers()
    buffers.vertices = [u.Vector(x - 4100., y + 4800., height(x, y)) for y in ys for x in xs]
    buffers.uv0 = [u.Vector2D(x / 140., y / 140.) for y in ys for x in xs]
    triangles, materials = [], []
    for j, y in enumerate(ys[:-1]):
        for i, x in enumerate(xs[:-1]):
            a = j * len(xs) + i
            c = a + len(xs)
            triangles.extend((u.IntVector(a, c, a + 1), u.IntVector(a + 1, c, c + 1)))
            z = height(x + 10., y + 10.)
            materials.extend([2 if z > 146. else 1 if z > 82. and abs(x - 4170.) > 145. else 0] * 2)
    buffers.triangles = triangles
    mesh.append_buffers_to_mesh(buffers)
    for index, material in enumerate(materials):
        if material:
            mesh.set_triangle_material_id(index, material)
    options = set_props(u.GeometryScriptCreateNewStaticMeshAssetOptions(), enable_collision=True, enable_recompute_normals=True,
                        collision_mode=u.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE)
    asset, _ = u.GeometryScript_NewAssetUtils.create_new_static_mesh_asset_from_mesh(mesh, BED, options)
    if not asset:
        raise RuntimeError("Could not create the riverbed mesh")
    for index, name in enumerate(("Stone", "Wet", "Grass")):
        asset.set_material(index, require(f"/Game/JYU/Fauna/Audio/M_Fauna_{name}"))
    ASSETS.save_loaded_asset(asset)
    return asset


def terrain_materials():
    edit = u.MaterialEditingLibrary
    tools = u.AssetToolsHelpers.get_asset_tools()
    ground = "/Game/SHC/Fab/MWLandscapeAutoMaterial/Textures/Ground/TEX_MWAM_"
    materials = []
    for surface, texture, tint in (("Stone", "Rock", (.72, .69, .61)), ("Wet", "Rock", (.59, .48, .34)),
                                   ("Grass", "Grass", (.71, .75, .56))):
        name = "M_JYU_Reach" + surface
        folder = "/Game/JYU/Riparian"
        material = ASSETS.load_asset(f"{folder}/{name}") if ASSETS.does_asset_exist(f"{folder}/{name}") else None
        if material is None:
            material = tools.create_asset(name, folder, u.Material, u.MaterialFactoryNew())
            source = require(f"/Game/JYU/Fauna/Audio/M_Fauna_{surface}")
            material.set_editor_property("phys_material", source.get_editor_property("phys_material"))
            sample = edit.create_material_expression(material, u.MaterialExpressionTextureSample, -500, -100)
            sample.set_editor_property("texture", require(ground + texture + "_col"))
            color = edit.create_material_expression(material, u.MaterialExpressionConstant3Vector, -500, 100)
            color.set_editor_property("constant", u.LinearColor(*tint, 1.))
            multiply = edit.create_material_expression(material, u.MaterialExpressionMultiply, -230, 0)
            edit.connect_material_expressions(sample, "RGB", multiply, "A")
            edit.connect_material_expressions(color, "", multiply, "B")
            edit.connect_material_property(multiply, "", u.MaterialProperty.MP_BASE_COLOR)
            roughness = edit.create_material_expression(material, u.MaterialExpressionConstant, -230, 180)
            roughness.set_editor_property("r", .82)
            edit.connect_material_property(roughness, "", u.MaterialProperty.MP_ROUGHNESS)
            edit.recompile_material(material)
            ASSETS.save_loaded_asset(material)
        materials.append(material)
    return materials


def author():
    if not ASSETS.does_asset_exist(MAP):
        duplicate = ASSETS.duplicate_asset(SOURCE, MAP)
        if not duplicate or not u.EditorLoadingAndSavingUtils.save_map(duplicate, MAP):
            raise RuntimeError(f"Could not duplicate {SOURCE}")
        u.log("ECO_RIPARIAN_REACH_DUPLICATED")
        return
    if EDITOR.get_editor_world().get_name() != MAP.rsplit("/", 1)[-1] and not LEVELS.load_level(MAP):
        raise RuntimeError(f"Could not load {MAP}")
    world = EDITOR.get_editor_world()
    terrain = bed_mesh()
    for actor in ACTORS.get_all_level_actors():
        label = actor.get_actor_label()
        if label.startswith((PREFIX, "JYU Riparian ", "JYU Water Passage ")):
            ACTORS.destroy_actor(actor)
    bed = ACTORS.spawn_actor_from_class(u.StaticMeshActor, u.Vector(4100., -4800., 0.))
    bed.set_actor_label(PREFIX + "Terrain")
    bed.static_mesh_component.set_static_mesh(terrain)
    bed.static_mesh_component.set_collision_profile_name("BlockAll")
    for index, material in enumerate(terrain_materials()):
        bed.static_mesh_component.set_material(index, material)

    pool = next(a for a in ACTORS.get_all_level_actors() if isinstance(a, u.EcoVegetationHabitat)
                and str(a.get_editor_property("habitat_id")) == "ExpandedFaunaPool")
    set_props(pool, fauna_water_current=u.Vector(9., 0., 0.))
    surface = pool.get_editor_property("water_surface")
    surface.set_mobility(u.ComponentMobility.MOVABLE)
    surface.set_editor_property("cast_shadow", False)
    for label, xy, extent, flow, temp, density, cover in (
        ("Backwater", (3715., -4490.), (190., 155.), 1.4, 19., .66, 68.),
        ("DeepPool", (4520., -4800.), (215., 175.), 2.4, 18., .25, 38.),
        ("Riffle", (4170., -4840.), (112., 225.), 18., 20., 0., 0.),
    ):
        habitat = ACTORS.spawn_actor_from_class(u.EcoVegetationHabitat, u.Vector(*xy, 65.))
        habitat.set_actor_label(PREFIX + label)
        habitat.get_editor_property("bounds").set_box_extent(u.Vector(*extent, 145.), False)
        set_props(habitat, habitat_id="RiparianReach" + label, region_id=REGION, plant=1, drainage=.3,
                  priority=10, connected_fresh_water=True, supports_fauna_swimming=True, draw_water_surface=False,
                  fauna_water_current=u.Vector(flow, 0., 0.), fauna_water_temperature_c=temp,
                  fauna_water_cover_density=density, fauna_water_cover_height_cm=cover)
        for field in ("water_surface_z", "water_level_rise", "water_rain_rise_cm", "water_rise_seconds",
                      "water_high_seconds", "water_fall_seconds", "water_low_seconds"):
            habitat.set_editor_property(field, pool.get_editor_property(field))

    runtime = next(a for a in ACTORS.get_all_level_actors() if isinstance(a, u.EcoCreatureIntegrationSpawner))
    patches = [p for p in runtime.get_editor_property("fauna_habitat_patches")
               if not str(p.get_editor_property("id")).startswith(("ExpandedWater", "RiparianHabitat", "RiparianReach"))]
    for label, xy, z, consumers, nursery, seasonal, shore in (
        ("Gravel", (3890., -4920.), 62., ["AriakeCatfish", "CommonCarp"], True, False, None),
        ("Macrophytes", (4500., -4910.), 53., ["CommonCarp"], True, False, None),
        ("Littoral", (3800., -4600.), 78., ["UnidentifiedFish"], True, False, None),
        ("DriftingInsects", (3670., -4730.), 96., ["UnidentifiedFish", "CommonCarp"], False, False, None),
        ("Floodplain", (3760., -4500.), 126., ["CommonCarp", "UnidentifiedFish"], False, True, None),
        ("WestShore", (3525., -4680.), 84., ["Mink", "AriakeCatfish"], False, False,
         ((3365., -4680.), (3460., -4680., 92.))),
        ("EastShore", (4680., -4860.), 82., ["Mink", "CommonCarp"], False, False,
         ((4835., -4860.), (4740., -4860., 92.))),
    ):
        patch = set_props(u.EcoFaunaHabitatPatch(), id="RiparianReach" + label, region_id=REGION,
                          center=u.Vector(*xy, z), consumers=consumers, submerged=True, stage=1,
                          aquatic_nursery=nursery, capacity=12., regrowth_per_second=.16, energy_per_meal=3.)
        if seasonal:
            set_props(patch, seasonal_full_growth_depth_cm=10., seasonal_dry_loss_per_second=.20)
        if shore:
            set_props(patch, has_shore_entry=True, shore_point=u.Vector(*shore[0], 155.), water_entry_point=u.Vector(*shore[1]))
        patches.append(patch)
    patches.append(set_props(u.EcoFaunaHabitatPatch(), id="RiparianReachLeafLitter", region_id=REGION,
                             center=u.Vector(3220., -4600., 150.), consumers=["Mink", "Fox", "Pig", "Rat"],
                             stage=1, capacity=10., regrowth_per_second=.13, energy_per_meal=2.5))
    runtime.set_editor_property("fauna_habitat_patches", patches)
    for group in (groups := list(runtime.get_editor_property("groups"))):
        for placement in (placements := list(group.get_editor_property("fauna"))):
            kind = str(placement.get_editor_property("species_id"))
            if kind == "UnidentifiedFish":
                placement.set_editor_property("spawn_points", [u.Vector(3720., -4610., 75.), u.Vector(3880., -4590., 75.)])
            elif kind == "Mink":
                placement.set_editor_property("spawn_points", [u.Vector(3040., -4220., 150.), u.Vector(3190., -4410., 150.)])
        group.set_editor_property("fauna", placements)
    runtime.set_editor_property("groups", groups)

    library = {role: require(path) for role, path in MESHES.items()}
    library["meadow"] = require("/Game/Map_Resource/SkyTown/Meshes/SM_GrassSky03")
    library["shrub"] = require("/Game/Map_Resource/SkyTown/Meshes/SM_ForestShrub02")
    library["stone"] = require("/Game/SHC/Fab/MWLandscapeAutoMaterial/Meshes/Cover/SM_MWAM_StoneB")
    use_mesh = runpy.run_path(str(HERE / "author_jyu_riparian_projectj.py"))["use_mesh"]
    rng = random.Random(6841)
    for role, xy, spread, count, size, upright in (
        ("stone", (4140., -4860.), (92., 175.), 17, (20., 62.), False),
        ("stone", (3890., -4940.), (124., 64.), 9, (28., 77.), False),
        ("submerged_a", (3770., -4560.), (95., 77.), 12, (27., 64.), True),
        ("submerged_b", (4500., -4900.), (110., 100.), 10, (29., 65.), True),
        ("cattail_a", (3700., -4430.), (156., 42.), 8, (84., 132.), True),
        ("cattail_b", (4520., -4530.), (130., 45.), 7, (77., 127.), True),
        ("floating_leaves", (3660., -4550.), (84., 53.), 5, (45., 84.), False),
        ("meadow", (3850., -4290.), (190., 49.), 15, (28., 58.), True),
        ("fern", (3210., -4590.), (92., 100.), 7, (41., 66.), True),
        ("shrub", (3470., -4320.), (190., 61.), 8, (68., 143.), True),
        ("shrub", (4700., -5210.), (135., 75.), 7, (70., 151.), True),
        ("leaf_litter", (3220., -4600.), (58., 42.), 8, (25., 48.), False),
        ("fallen_log", (4450., -5080.), (0., 0.), 1, (215., 215.), False),
        ("root_mat", (3895., -5050.), (0., 0.), 1, (110., 110.), False),
    ):
        for index in range(count):
            x, y = (xy[i] + rng.uniform(-spread[i], spread[i]) for i in range(2))
            floating = role == "floating_leaves"
            z = 111.5 if floating else height(x, y)
            actor = ACTORS.spawn_actor_from_class(u.StaticMeshActor, u.Vector(x, y, z))
            actor.set_actor_label(f"{PREFIX}{role} {xy[0]:.0f} {index:02}")
            if floating:
                actor.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
                actor.static_mesh_component.set_absolute(False, False, True)
            scale = rng.uniform(*size)
            bottom = use_mesh(actor, library[role], **({"height": scale} if upright else {"width": scale}))
            actor.set_actor_location_and_rotation(u.Vector(x, y, z - bottom), u.Rotator(yaw=rng.uniform(0., 360.)), False, False)
            if floating:
                keep = u.AttachmentRule.KEEP_WORLD
                if not actor.attach_to_component(surface, "None", keep, keep, keep, False):
                    raise RuntimeError("Could not attach floating leaves")
    ASSETS.set_metadata_tag(world, "JYUOwner", "JYU.RiparianReach")
    if not u.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError(f"Could not save {MAP}")
    u.log("ECO_RIPARIAN_REACH_AUTHORED")


def audit():
    if EDITOR.get_editor_world().get_name() != MAP.rsplit("/", 1)[-1] and not LEVELS.load_level(MAP):
        raise RuntimeError(f"Could not load {MAP}")
    inspection = u.EcoCreatureInspectionLibrary
    high_view = "-EcoRiparianReachHighView" in u.SystemLibrary.get_command_line()
    measure_area = "-EcoRiparianReachArea" in u.SystemLibrary.get_command_line()
    if high_view:
        for habitat in ACTORS.get_all_level_actors():
            if isinstance(habitat, u.EcoVegetationHabitat) and habitat.get_editor_property("supports_fauna_swimming"):
                set_props(habitat, water_surface_z=142., water_level_rise=0.)
    LEVELS.editor_request_begin_play()
    start = time.monotonic()
    result = {"samples": [], "captures": [], "error": None}
    camera = None
    forage_visuals = {}
    capacities = {}
    shelf_roots = []
    region = None

    def finish(error=None):
        u.unregister_slate_post_tick_callback(handle)
        result["error"] = error
        OUT.mkdir(parents=True, exist_ok=True)
        name = "ReachHabitatArea" if measure_area else "RiparianReachHighView" if high_view else "RiparianReachAudit"
        (OUT / f"{name}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        if error:
            u.log_error(f"ECO_RIPARIAN_REACH_FAILED {error}")
        else:
            u.log("ECO_RIPARIAN_REACH_VERIFIED")
        LEVELS.editor_request_end_play()
        u.SystemLibrary.quit_editor()

    def tick(_):
        nonlocal camera, region
        try:
            if time.monotonic() - start > 115.:
                raise RuntimeError("Timed out waiting for reach audit")
            world = EDITOR.get_game_world()
            if not world:
                return
            now = u.GameplayStatics.get_time_seconds(world)
            runtime = next(iter(u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureIntegrationSpawner)), None)
            if runtime is None or not runtime.is_runtime_ready():
                if now >= 8.:
                    raise RuntimeError("Authority did not initialize on the authored reach")
                return
            if camera is None:
                region = next(a for a in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)
                              if str(a.get_editor_property("region_id")) == REGION)
                camera = u.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, u.CameraActor, u.Transform())
                u.GameplayStatics.get_player_controller(world, 0).set_view_target_with_blend(camera, 0.)
                u.SystemLibrary.execute_console_command(world, "eco.Creature.Labels 0")
                # Keep the same scene lighting for all reference captures, without editing the map clock.
                u.SystemLibrary.execute_console_command(world, "eco.Sky.Link 0")
                u.SystemLibrary.execute_console_command(world, "eco.IntegratedV3.WeatherVisuals 0")
                u.SystemLibrary.execute_console_command(world, "showhud")
                forage_visuals.update({str(a.get_editor_property("patch_id")): a for a in
                                       u.GameplayStatics.get_all_actors_of_class(world, u.EcoForagePatchVisual)
                                       if str(a.get_editor_property("patch_id")).startswith("RiparianReachForage")
                                       or str(a.get_editor_property("patch_id")) == "RiparianReachFloodplain"})
                capacities.update({str(p.get_editor_property("id")): p.get_editor_property("capacity")
                                   for p in runtime.get_editor_property("fauna_habitat_patches")
                                   if str(p.get_editor_property("id")).startswith("RiparianReachForage")
                                   or str(p.get_editor_property("id")) == "RiparianReachFloodplain"})
                if set(forage_visuals) != set(capacities):
                    raise RuntimeError("Reach forage visuals and authority patches do not match")
                result["forage_instances"] = {site: actor.get_editor_property("plants").get_instance_count()
                                              for site, actor in forage_visuals.items()}
                shelf = forage_visuals["RiparianReachFloodplain"]
                bottom = shelf.get_editor_property("plants").get_editor_property("static_mesh").get_bounding_box().min.z
                for shoot in shelf.get_editor_property("full_plant_transforms"):
                    root = shelf.get_actor_location() + shoot.translation + u.Vector(0., 0., bottom * shoot.scale3d.z)
                    shelf_roots.append(root)
                foliage_actors = u.GameplayStatics.get_all_actors_of_class(world, u.InstancedFoliageActor)
                result["canopy_instances"] = {c.get_editor_property("static_mesh").get_name(): c.get_instance_count()
                                              for a in foliage_actors for c in a.get_components_by_class(u.InstancedStaticMeshComponent)
                                              if c.get_editor_property("static_mesh") and c.get_instance_count()}
            captures = (
                ("Low", 12., (3160., -5570., 980.), (4110., -4800., 70.)),
                ("Receded", 137., (3160., -5570., 980.), (4110., -4800., 70.)),
            ) if not high_view else (
                ("High", 12., (3160., -5570., 980.), (4110., -4800., 70.)),
                ("Underwater", 20., (4380., -4755., 105.), (4510., -4890., 36.)),
            )
            for label, capture_at, eye, target in (() if measure_area else captures):
                if capture_at - 2. <= now < capture_at and label not in result["captures"]:
                    eye, target = u.Vector(*eye), u.Vector(*target)
                    camera.set_actor_location(eye, False, False)
                    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye, target), False)
                if now >= capture_at and label not in result["captures"]:
                    image = (OUT / f"RiparianReach{label}.png").as_posix()
                    u.SystemLibrary.execute_console_command(world, f'HighResShot 1280x720 filename="{image}"')
                    result["captures"].append(label)
            if result["samples"] and now - result["samples"][-1]["time"] < 2.:
                return
            row = {"time": now, "columns": {}, "rainfall": region.get_environment_state().get_editor_property("rainfall")}
            for label, point in (("Riffle", (4170., -4840.)), ("DeepPool", (4520., -4800.)),
                                 ("Backwater", (3715., -4600.)), ("Floodplain", (3760., -4500.)),
                                 ("WestEntry", (3460., -4680.)), ("EastEntry", (4740., -4860.))):
                sample = inspection.inspect_fauna_water(world, REGION, u.Vector(*point, 80.), 6.)
                if sample is not None:
                    column, flow = sample
                    row["columns"][label] = {"bottom": column.x, "surface": column.y, "flow": flow.length()}
                else:
                    row["columns"][label] = None
            stock = runtime.inspect_fauna_habitat_stock("RiparianReachFloodplain")
            row["floodplain_stock"] = float(stock[-1] if isinstance(stock, tuple) else stock)
            stock = runtime.inspect_fauna_habitat_stock("RiparianReachWestShore")
            row["west_shore_stock"] = float(stock[-1] if isinstance(stock, tuple) else stock)
            row["forage"] = {}
            row["plant_height"] = {}
            for site, actor in forage_visuals.items():
                stock = runtime.inspect_fauna_habitat_stock(site)
                stock = float(stock[-1] if isinstance(stock, tuple) else stock)
                fraction = actor.get_forage_fraction()
                if abs(stock / capacities[site] - fraction) > .003:
                    raise RuntimeError(f"Reach forage visual and authority differ at {site}")
                plants = actor.get_editor_property("plants")
                stems = actor.get_editor_property("woody_stems")
                full = actor.get_editor_property("full_plant_transforms")
                residual = actor.get_editor_property("residual_height_fraction")
                browse = actor.get_editor_property("keep_woody_stems")
                actual = []
                for i, base in enumerate(full):
                    scale = plants.get_instance_transform(i, False).scale3d.z / base.scale3d.z
                    expected = (.001 + .999 * min(1., max(0., fraction * len(full) - i)) if browse else
                                residual + (1. - residual) * fraction)
                    if abs(scale - expected) > .002:
                        raise RuntimeError(f"Unexpected plant height at {site}: {scale} != {expected}")
                    if browse and abs(stems.get_instance_transform(i, False).scale3d.z - base.scale3d.z) > .0001:
                        raise RuntimeError(f"Woody stem changed height at {site}")
                    actual.append(scale)
                row["forage"][site] = stock
                row["plant_height"][site] = sum(actual) / len(actual)
            row["population"] = len(inspection.get_authority_agent_ids(world))
            if row["columns"]["DeepPool"]["surface"] >= 141.:
                for root in shelf_roots:
                    column = inspection.inspect_fauna_water(world, REGION, root, .5)
                    if column is None or abs(column[0].x - root.z) > 2.:
                        raise RuntimeError(f"Seasonal shoot root differs from the collision bed: {root}, {column}")
            if measure_area:
                surface = row["columns"]["DeepPool"]["surface"]
                phase = "low" if surface == 110. else "high" if surface == 142. else None
                areas = result.setdefault("water_area", {})
                if phase and phase not in areas:
                    areas[phase] = sample_water_area(inspection, world, surface)
            result["samples"].append(row)
            if high_view and now >= 24.:
                if not row["columns"]["Floodplain"] or not row["columns"]["Riffle"]:
                    raise RuntimeError("The high-water capture is missing its flooded habitat")
                finish()
                return
            if now < 142.:
                return
            if measure_area and set(result["water_area"]) != {"low", "high"}:
                raise RuntimeError("Both water levels must be sampled")
            rows = result["samples"]
            open_riffle = [bool(r["columns"]["Riffle"]) for r in rows]
            peak_stock = max(r["floodplain_stock"] for r in rows)
            if open_riffle[0] or not any(open_riffle) or open_riffle[-1]:
                raise RuntimeError("Riffle did not close, open and close again")
            if not all(r["columns"]["DeepPool"] and r["columns"]["Backwater"] for r in rows):
                raise RuntimeError("A perennial refuge lost its water column")
            if not all(r["columns"]["WestEntry"] and r["columns"]["EastEntry"] for r in rows):
                raise RuntimeError("A shore entry lost its authored water column")
            if rows[0]["floodplain_stock"] != 0. or peak_stock <= .5 or rows[-1]["floodplain_stock"] >= peak_stock:
                raise RuntimeError("Floodplain food did not recover during flooding and decline after exposure")
            if min(r["west_shore_stock"] for r in rows) >= rows[0]["west_shore_stock"]:
                raise RuntimeError("Fauna did not consume the shore food patch")
            site = "RiparianReachForageNorthSedges"
            dry = [r["forage"][site] for r in rows if r["rainfall"] < .01 and r["time"] < 60.]
            wet = [r["forage"][site] for r in rows if r["rainfall"] > .65]
            if not dry or not wet or min(dry) >= dry[0] or max(wet) <= min(dry):
                raise RuntimeError(f"The north bank forage did not dry and recover: {dry}, {wet}")
            finish()
        except Exception as error:
            finish(str(error))

    handle = u.register_slate_post_tick_callback(tick)


def sample_water_area(inspection, world, surface):
    step = 20
    depths = {}
    for x in range(3370, 4840, step):
        for y in range(-5310, -4280, step):
            water = inspection.inspect_fauna_water(world, REGION, u.Vector(x, y, 80.), .5)
            if water is not None:
                depths[(x, y)] = water[0].y - water[0].x
    result = {"surface_cm": surface, "grid_cm": step, "minimum_depth_cm": {}}
    for depth in (5.2, 9.1, 12.):
        remaining = {xy for xy, local_depth in depths.items() if local_depth >= depth}
        components = []
        while remaining:
            frontier = [remaining.pop()]
            for x, y in frontier:
                for xy in ((x + step, y), (x - step, y), (x, y + step), (x, y - step)):
                    if xy in remaining:
                        remaining.remove(xy)
                        frontier.append(xy)
            components.append(round(len(frontier) * (step / 100.) ** 2, 2))
        result["minimum_depth_cm"][str(depth)] = sorted(components, reverse=True)
    return result


if __name__ == "__main__":
    if "-EcoRiparianReachAudit" in u.SystemLibrary.get_command_line():
        audit()
    else:
        try:
            author()
        finally:
            u.SystemLibrary.quit_editor()

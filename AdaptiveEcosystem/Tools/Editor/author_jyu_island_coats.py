"""Author tint-compatible copies of the saved island's materials and its coat palette."""
import hashlib
import json
from pathlib import Path
import traceback

import unreal as u

MAP = "/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed"
ROOT = "/Game/JYU/Ecosystem/IslandCoats"
OWNER = "JYU.IslandCoats.v1"
BODY = {"Herbivore": .34, "Wolf": .30, "Leopard": .32, "Fox": .38, "Pig": .23,
        "Buffalo": .23, "Horse": .36, "Bighorn": .41, "Jackrabbit": .38, "Rat": .26, "Mink": .25,
        "Crow": .14, "GoldenEagle": .27, "AriakeCatfish": .28, "CommonCarp": .38, "UnidentifiedFish": .32}
SUBTLE = {"Crow", "GoldenEagle", "AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
# Baseline estimates for the owned level's snow, grass, rocks and river beds.
BACKGROUND = {"Snowfield": .73, "Grassland": .36, "Highland": .32, "Riverbank": .25,
              "LowerRiver": .29, "ZGrasslandRiverTransit": .34, "Lake": .30}

assets = u.EditorAssetLibrary
edit = u.MaterialEditingLibrary
tools = u.AssetToolsHelpers.get_asset_tools()
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
out = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit" / "CoatAuthoring.json"
out.parent.mkdir(parents=True, exist_ok=True)
report = {"slots": {}, "materials": {}, "error": None}
variants = {}


def save(asset):
    if not assets.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {asset.get_path_name()}")


def require_owned(asset):
    if not asset or assets.get_metadata_tag(asset, "JYUOwner") != OWNER:
        raise RuntimeError(f"Expected owned coat asset, got {asset}")
    return asset


def colour_connection(material):
    prop = u.MaterialProperty.MP_BASE_COLOR
    direct = edit.get_material_property_input_node(material, prop)
    if direct and not material.get_editor_property("use_material_attributes"):
        return direct, edit.get_material_property_input_node_output_name(material, prop), None, prop
    nodes = []
    for flag in ("MP_FRONT_MATERIAL", "MP_MATERIAL_ATTRIBUTES"):
        channel = getattr(u.MaterialProperty, flag, None)
        node = edit.get_material_property_input_node(material, channel) if channel else None
        if node:
            nodes.append(node)
    if not nodes:
        prop = u.MaterialProperty.MP_EMISSIVE_COLOR
        unlit = edit.get_material_property_input_node(material, prop)
        if unlit:
            return unlit, edit.get_material_property_input_node_output_name(material, prop), None, prop
    inspected = {}
    while nodes:
        node = nodes.pop(0)
        if node.get_name() in inspected:
            continue
        pins = edit.get_material_expression_input_names(node)
        inputs = edit.get_inputs_for_material_expression(material, node)
        inspected[node.get_name()] = list(pins)
        for name, source in zip(pins, inputs):
            token = "".join(filter(str.isalnum, str(name))).lower()
            if source and token in {"basecolor", "basecolour", "diffuse", "diffusealbedo", "diffusecolor", "albedo"}:
                result = edit.get_input_node_output_name_for_material_expression(node, source)
                pin = next((part for part in result if isinstance(part, str)), "") if isinstance(result, tuple) else result
                return source, pin or "", node, str(name)
        nodes.extend(candidate for candidate in inputs if candidate)
    raise RuntimeError(f"Unsupported base color path {material.get_path_name()} {inspected}")


def variant(source):
    path = source.get_path_name()
    if path in variants:
        return variants[path]
    key = hashlib.sha1(path.encode()).hexdigest()[:10]
    target = f"{ROOT}/Materials/{source.get_name()}_Coat_{key}"
    if assets.does_asset_exist(target):
        v = require_owned(assets.load_asset(target))
    else:
        if isinstance(source, u.MaterialInstanceConstant):
            parent = variant(source.get_editor_property("parent"))
            v = assets.duplicate_asset(path, target)
            if not v:
                raise RuntimeError(f"Could not copy {path}")
            edit.set_material_instance_parent(v, parent)
            edit.update_material_instance(v)
        elif isinstance(source, u.Material):
            colour_connection(source)
            v = assets.duplicate_asset(path, target)
            if not v:
                raise RuntimeError(f"Could not copy {path}")
            original, pin, target_node, target_pin = colour_connection(v)
            tint = edit.create_material_expression(v, u.MaterialExpressionVectorParameter, 150, 850)
            tint.set_editor_property("parameter_name", "EcoInheritedSurfaceTint")
            tint.set_editor_property("default_value", u.LinearColor(1, 1, 1, 1))
            tint.set_editor_property("use_custom_primitive_data", True)
            tint.set_editor_property("primitive_data_index", 8)
            blend = edit.create_material_expression(v, u.MaterialExpressionMultiply, 450, 850)
            wired = (edit.connect_material_expressions(original, pin, blend, "A")
                     and edit.connect_material_expressions(tint, "", blend, "B"))
            output = (edit.connect_material_expressions(blend, "", target_node, target_pin) if target_node
                      else edit.connect_material_property(blend, "", target_pin))
            if not wired or not output:
                raise RuntimeError(f"Could not connect coat expression for {path}")
            edit.set_material_usage(v, u.MaterialUsage.MATUSAGE_SKELETAL_MESH)
            edit.recompile_material(v)
        else:
            raise RuntimeError(f"Unsupported material class {path}")
        assets.set_metadata_tag(v, "JYUOwner", OWNER)
        save(v)
    variants[path] = v
    report["materials"][path] = v.get_path_name()
    return v


def mesh_materials(mesh):
    return [(str(slot.get_editor_property("material_slot_name")), slot.get_editor_property("material_interface"))
            for slot in mesh.get_editor_property("materials")] if mesh else []


def main():
    if not levels.load_level(MAP):
        raise RuntimeError("Could not open owned island")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    spawner = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
    if not spawner:
        raise RuntimeError("Missing island integration spawner")
    classes = {"Herbivore": spawner.get_editor_property("herbivore_actor_class"),
               "Wolf": spawner.get_editor_property("wolf_actor_class")}
    classes.update({str(species.get_editor_property("species_id")): species.get_editor_property("visual_class")
                    for species in spawner.get_editor_property("fauna_species")})
    if set(classes) != set(BODY):
        raise RuntimeError(f"Unexpected roster {sorted(classes)}")
    replacements = {}
    for species, cls in classes.items():
        default = u.get_default_object(cls)
        sources = mesh_materials(default.get_editor_property("visual_mesh"))
        for appearance in default.get_editor_property("appearance_variants"):
            sources += mesh_materials(appearance.get_editor_property("mesh"))
            sources += [(m.get_name(), m) for m in appearance.get_editor_property("growth_materials") if m]
        report["slots"][species] = []
        for slot, source in sources:
            if not source or any(token in (slot + source.get_name()).lower()
                                 for token in ("eye", "teeth", "tooth", "tongue", "claw", "horn", "antler")):
                continue
            replacements[source] = variant(source)
            report["slots"][species].append(source.get_path_name())
        if not report["slots"][species]:
            raise RuntimeError(f"No pigment surface for {species}: {sources}")

    path = f"{ROOT}/DA_IslandCoatPalette"
    if assets.does_asset_exist(path):
        palette = require_owned(assets.load_asset(path))
    else:
        factory = u.DataAssetFactory()
        factory.set_editor_property("data_asset_class", u.EcoCreatureCoatPalette)
        palette = tools.create_asset(path.rsplit("/", 1)[-1], ROOT, u.EcoCreatureCoatPalette, factory)
        assets.set_metadata_tag(palette, "JYUOwner", OWNER)
    surfaces = {}
    for name, luminance in BODY.items():
        surface = u.EcoCoatSurface()
        surface.set_editor_property("base_luminance", luminance)
        surface.set_editor_property("subtle", name in SUBTLE)
        surfaces[u.Name(name)] = surface
    palette.set_editor_property("species", surfaces)
    palette.set_editor_property("region_luminance", {u.Name(name): value for name, value in BACKGROUND.items()})
    palette.set_editor_property("materials", replacements)
    save(palette)
    spawner.modify()
    spawner.set_editor_property("coat_palette", palette)
    if not levels.save_current_level():
        raise RuntimeError("Could not save island palette assignment")


try:
    main()
    u.log("ECO_ISLAND_COATS_AUTHORED")
except Exception:
    report["error"] = traceback.format_exc()
    u.log_error(report["error"])
finally:
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    u.SystemLibrary.quit_editor()

"""Add a neutral-by-default freshness tint to the owned JYU foliage material."""
import unreal

PATH = "/Game/JYU/Ecosystem/M_JYU_EcosystemGrass"
MARKER = "JYU freshness from vegetation cell"
lib = unreal.MaterialEditingLibrary
assets = unreal.EditorAssetLibrary
material = assets.load_asset(PATH)
if not material:
    raise RuntimeError(f"Missing owned material {PATH}")
channel = unreal.MaterialProperty.MP_BASE_COLOR
base = lib.get_material_property_input_node(material, channel)
if not base:
    raise RuntimeError("Base Color input is required")


def expression(kind, x, y, **properties):
    node = lib.create_material_expression(material, kind, x, y)
    for key, value in properties.items():
        node.set_editor_property(key, value)
    return node


def connect(source, target, target_pin, source_pin=""):
    pins = [str(pin) for pin in lib.get_material_expression_input_names(target)]
    if target_pin not in pins and len(pins) == 1:
        target_pin = pins[0]
    if not lib.connect_material_expressions(source, source_pin, target, target_pin):
        raise RuntimeError(f"Cannot connect {target_pin} in {pins}")


if base.get_editor_property("desc") != MARKER:
    base_pin = lib.get_material_property_input_node_output_name(material, channel)
    fresh = expression(unreal.MaterialExpressionPerInstanceCustomData, 1500, 1050,
                       data_index=3, const_default_value=128/255)
    pixel = expression(unreal.MaterialExpressionVertexInterpolator, 1700, 1050)
    connect(fresh, pixel, "VS")
    delta = expression(unreal.MaterialExpressionSubtract, 1950, 1050, const_b=128/255)
    connect(pixel, delta, "A")
    shift = expression(unreal.MaterialExpressionConstant3Vector, 1950, 1200,
                       constant=unreal.LinearColor(-.65, .34, .62, 1))
    multiply = expression(unreal.MaterialExpressionMultiply, 2180, 1050)
    connect(delta, multiply, "A")
    connect(shift, multiply, "B")
    tint = expression(unreal.MaterialExpressionAdd, 2410, 1050, const_b=1)
    connect(multiply, tint, "A")
    result = expression(unreal.MaterialExpressionMultiply, 3100, 100, desc=MARKER)
    connect(base, result, "A", base_pin)
    connect(tint, result, "B")
    if not lib.connect_material_property(result, "", channel):
        raise RuntimeError("Cannot connect freshness output")
    lib.recompile_material(material)
    if not assets.save_loaded_asset(material, only_if_is_dirty=False):
        raise RuntimeError(f"Cannot save {PATH}")
unreal.log("JYU_PLANT_FRESHNESS_READY")

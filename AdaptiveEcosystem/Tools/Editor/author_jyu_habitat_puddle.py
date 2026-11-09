"""Author only the owned shallow-water material used by JYU's instanced puddles."""
import unreal


FOLDER = "/Game/JYU/Ecosystem/Natural"
NAME = "M_EcoHabitatPuddle"
PATH = f"{FOLDER}/{NAME}"
assets = unreal.EditorAssetLibrary
materials = unreal.MaterialEditingLibrary
material = (assets.load_asset(PATH) if assets.does_asset_exist(PATH)
            else unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                NAME, FOLDER, unreal.Material, unreal.MaterialFactoryNew()))
if not material:
    raise RuntimeError(f"Cannot author {PATH}")

materials.delete_all_material_expressions(material)
material.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
materials.set_material_usage(material, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)


def expression(kind, **properties):
    node = materials.create_material_expression(material, kind)
    for key, value in properties.items():
        node.set_editor_property(key, value)
    return node


def connect(source, target, pin):
    inputs = [str(value) for value in materials.get_material_expression_input_names(target)]
    if pin not in inputs:
        matches = [name for name in inputs if pin.lower() in name.lower()]
        if len(inputs) == 1:
            pin = inputs[0]
        elif len(matches) == 1:
            pin = matches[0]
    if not materials.connect_material_expressions(source, "", target, pin):
        raise RuntimeError(f"Cannot connect {pin} in {inputs}")


def output(node, channel):
    if not materials.connect_material_property(node, "", channel):
        raise RuntimeError(f"Cannot connect {channel}")


color = expression(unreal.MaterialExpressionConstant3Vector,
                   constant=unreal.LinearColor(.045, .09, .10, 1))
output(color, unreal.MaterialProperty.MP_BASE_COLOR)
output(expression(unreal.MaterialExpressionConstant, r=.17), unreal.MaterialProperty.MP_ROUGHNESS)
uv = expression(unreal.MaterialExpressionTextureCoordinate)
center = expression(unreal.MaterialExpressionConstant2Vector, r=.5, g=.5)
distance = expression(unreal.MaterialExpressionDistance)
connect(uv, distance, "A")
connect(center, distance, "B")
radius = expression(unreal.MaterialExpressionMultiply, const_b=2.5)
connect(distance, radius, "A")
inverse = expression(unreal.MaterialExpressionOneMinus)
connect(radius, inverse, "Input")
edge = expression(unreal.MaterialExpressionSaturate)
connect(inverse, edge, "Input")
fade = expression(unreal.MaterialExpressionDepthFade, fade_distance_default=5.)
connect(edge, fade, "Opacity")
output(fade, unreal.MaterialProperty.MP_OPACITY)
materials.recompile_material(material)
if not assets.save_loaded_asset(material, only_if_is_dirty=False):
    raise RuntimeError(f"Cannot save {PATH}")
unreal.log("JYU_HABITAT_PUDDLE_SAVED")

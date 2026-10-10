"""Read-only parent graph audit for the authored integration landscape."""
import json
from pathlib import Path
import unreal
instance = unreal.load_asset("/Game/MWLandscapeAutoMaterial/Materials/Landscape/MI_Ecosystem_Landscape")
chain = []
material = instance
while isinstance(material, unreal.MaterialInstanceConstant):
    chain.append(material.get_path_name())
    material = material.get_editor_property("parent")
nodes = []
for node in unreal.MaterialEditingLibrary.get_material_expressions(material):
    record = {"name": node.get_name(), "class": node.get_class().get_name(), "desc": node.get_editor_property("desc"),
              "inputs": [n.get_name() if n else None for n in unreal.MaterialEditingLibrary.get_inputs_for_material_expression(material, node)],
              "input_names": list(unreal.MaterialEditingLibrary.get_material_expression_input_names(node)),
              "output_names": list(unreal.MaterialEditingLibrary.get_material_expression_output_names(node))}
    for property_name in ("parameter_name", "material_function"):
        try:
            value = node.get_editor_property(property_name)
            record[property_name] = value.get_path_name() if isinstance(value, unreal.Object) else str(value)
        except Exception:
            pass
    nodes.append(record)
saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
(saved / "LandscapeAudioMaterialAudit.json").write_text(json.dumps({"chain": chain, "parent": material.get_path_name(), "nodes": nodes}, indent=2), encoding="utf-8")
unreal.log("LANDSCAPE_AUDIO_MATERIAL_AUDIT_OK")

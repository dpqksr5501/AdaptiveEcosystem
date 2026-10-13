"""Owned landscape material copy: reuse the existing six physical surface weights.
No biome-coordinate approximation, height/sculpt edit, or vendor master mutation.
"""
import json
from pathlib import Path
import unreal

ROOT = "/Game/Audio/Footsteps/Surfaces"
SOURCE_MI = "/Game/MWLandscapeAutoMaterial/Materials/Landscape/MI_Ecosystem_Landscape"
SOURCE_M = "/Game/MWLandscapeAutoMaterial/Materials/MASTER/MTL_MWAM_AutoMaterial_MASTER"
unreal.EditorAssetLibrary.make_directory(ROOT)
tools = unreal.AssetToolsHelpers.get_asset_tools()
edit = unreal.MaterialEditingLibrary
def physical(name):
    asset = unreal.load_asset(ROOT + "/" + name)
    if not asset:
        asset = tools.create_asset(name, ROOT, unreal.PhysicalMaterial, unreal.PhysicalMaterialFactoryNew())
    if not asset:
        raise RuntimeError("Physical material missing: " + name)
    unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False)
    return asset
grass, dry = physical("PM_EcoGrass"), physical("PM_EcoDry")
material = unreal.load_asset(ROOT + "/M_EcoLandscapeFootsteps")
if not material:
    material = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_M, ROOT + "/M_EcoLandscapeFootsteps")
# Edit only our copy: reuse the original six physical weights, preserving visual shader links.
for node in list(edit.get_material_expressions(material)):
    if str(node.get_editor_property("desc")).startswith("EcoFootsteps_"):
        edit.delete_material_expression(material, node)
outputs = [n for n in edit.get_material_expressions(material)
           if isinstance(n, unreal.MaterialExpressionLandscapePhysicalMaterialOutput)]
if len(outputs) != 1:
    raise RuntimeError("Review changed physical output topology")
output = outputs[0]
entries = list(output.get_editor_property("inputs"))
if len(entries) != 6:
    raise RuntimeError("Expected authored six-surface output")
report = []
for index, entry in enumerate(entries):
    existing = entry.get_editor_property("physical_material")
    name = existing.get_name() if existing else ""
    if name not in ("PM_MW_Rocks", "PM_MW_Stones", "PM_MW_Grass", "PM_MW_Dirt",
                    "PM_MW_Snow", "PM_MW_Water", "PM_EcoGrass", "PM_EcoDry"):
        raise RuntimeError("Unrecognized physical surface: " + name)
    value = grass if name in ("PM_MW_Grass", "PM_EcoGrass") else dry
    entry.set_editor_property("physical_material", value)
    report.append({"index": index, "physical_material": value.get_path_name()})
output.set_editor_property("inputs", entries)
edit.recompile_material(material)
instance = unreal.load_asset(ROOT + "/MI_EcoLandscapeFootsteps")
if not instance:
    instance = unreal.EditorAssetLibrary.duplicate_asset(SOURCE_MI, ROOT + "/MI_EcoLandscapeFootsteps")
edit.set_material_instance_parent(instance, material); edit.update_material_instance(instance)
for asset in (material, instance):
    if not unreal.EditorAssetLibrary.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError("Material save failed")
audio = unreal.load_asset("/Game/Audio/Footsteps/Settings/DA_EcoFootsteps")
audio.set_editor_property("grass_materials", [grass]); audio.set_editor_property("dry_materials", [dry])
unreal.EditorAssetLibrary.save_loaded_asset(audio, only_if_is_dirty=False)
changed = []
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
for actor in actors:
    if isinstance(actor, unreal.LandscapeProxy):
        current = actor.get_editor_property("landscape_material")
        if current and current.get_path_name().split(".")[0] in (SOURCE_MI, ROOT + "/MI_EcoLandscapeFootsteps"):
            actor.set_editor_property("landscape_material", instance)
            changed.append(actor.get_actor_label())
if not changed:
    raise RuntimeError("Open the authored ecosystem level first")
if not unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level():
    raise RuntimeError("Landscape actor/map save failed")
saved = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
(saved / "LandscapeFootstepSetup.json").write_text(json.dumps({"changed": changed, "instance": instance.get_path_name(),
    "physical_outputs": report, "weights": "Original six MWAM weights; PhysicalMaterial references changed only"}, indent=2), encoding="utf-8")
unreal.log("LANDSCAPE_FOOTSTEP_SETUP_OK " + str(len(changed)))

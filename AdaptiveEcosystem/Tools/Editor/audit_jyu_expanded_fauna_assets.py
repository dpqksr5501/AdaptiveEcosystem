"""Measure imported rigs and sample their animations before choosing game clips."""

import json
from pathlib import Path
import runpy

import unreal


def xyz(vector):
    return [round(vector.x, 3), round(vector.y, 3), round(vector.z, 3)]


def audit_bound_materials():
    edit = unreal.MaterialEditingLibrary
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    dependency_options = unreal.AssetRegistryDependencyOptions(include_hard_package_references=True)
    sets = {
        "Fauna": ("Deer", "Wolf", "Pig", "Fox", "Crow", "Leopard", "Buffalo", "Rat"),
        "ExpandedFauna": ("Bighorn", "Jackrabbit", "Horse", "Mink", "GoldenEagle", "AriakeCatfish", "CommonCarp", "UnidentifiedFish"),
        "Pig": ("Pig",),
    }
    results, missing = {}, []
    for group, species in sets.items():
        for kind in species:
            key = f"{group}/{kind}"
            klass = unreal.load_class(None, f"/Game/JYU/{key}/BP_{kind}.BP_{kind}_C")
            if not klass and kind in ("Deer", "Wolf"):
                klass = unreal.load_class(None, f"/Game/JYU/Creatures/BP_JYU_{kind}.BP_JYU_{kind}_C")
            if not klass:
                missing.append(key)
                continue
            defaults = unreal.get_default_object(klass)
            component = defaults.get_editor_property("creature_mesh")
            mesh = defaults.get_editor_property("visual_mesh") or component.get_skeletal_mesh_asset()
            row = {"mesh": mesh.get_path_name() if mesh else None, "slots": []}
            results[key] = row
            if not mesh:
                missing.append(key + ":mesh")
                continue
            for index, slot in enumerate(mesh.get_editor_property("materials")):
                name = str(slot.get_editor_property("material_slot_name"))
                material = component.get_material(index) or slot.get_editor_property("material_interface")
                if not material:
                    missing.append(key + ":" + name)
                    continue
                base = material
                while isinstance(base, unreal.MaterialInstance):
                    base = base.get_editor_property("parent")
                textures = set()
                if isinstance(base, unreal.Material):
                    textures.update(texture.get_path_name() for texture in edit.get_used_textures(base) if texture)
                if isinstance(material, unreal.MaterialInstanceConstant):
                    for parameter in edit.get_texture_parameter_names(material):
                        texture = edit.get_material_instance_texture_parameter_value(material, parameter)
                        if texture:
                            textures.add(texture.get_path_name())
                texture_references = set()
                for owner in {asset.get_path_name().split(".", 1)[0] for asset in (material, base) if asset}:
                    for dependency in registry.get_dependencies(owner, dependency_options) or ():
                        for asset_data in registry.get_assets_by_package_name(dependency):
                            if str(asset_data.asset_class_path.asset_name).startswith("Texture"):
                                texture_references.add(f"{dependency}.{asset_data.asset_name}")
                row["slots"].append({"slot": name, "material": material.get_path_name(),
                                     "parent": base.get_path_name() if base else None, "textures": sorted(textures),
                                     "texture_package_references": sorted(texture_references)})
            row["animation_class"] = str(defaults.get_editor_property("behavior_animation_class"))
            row["animation_notifies"] = defaults.get_editor_property("use_footstep_notifies")
    folder = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "FaunaAudit"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "BoundMaterials.json").write_text(json.dumps({"bindings": results, "missing": missing}, indent=2), encoding="utf-8")
    unreal.log(f"ECO_FAUNA_MATERIAL_AUDIT {len(results)} representations {len(missing)} missing")


def audit():
    importer = runpy.run_path(str(Path(__file__).with_name("import_jyu_expanded_fauna.py")))
    poses = unreal.AnimPoseExtensions
    world_space = unreal.AnimPoseSpaces.WORLD
    options = unreal.AnimPoseEvaluationOptions()
    report = {}
    for kind in importer["SOURCES"]:
        assets = importer["assets_at"](f'{importer["ROOT"]}/{kind}/Imported')
        meshes = [asset for asset in assets if isinstance(asset, unreal.SkeletalMesh)]
        clips = [asset for asset in assets if isinstance(asset, unreal.AnimSequence)]
        rigs = []
        for mesh in meshes:
            skeleton = mesh.get_editor_property("skeleton")
            pose = poses.get_reference_pose(skeleton)
            bones = poses.get_bone_names(pose)
            rig = {
                "mesh": mesh.get_path_name(),
                "materials": [str(slot.get_editor_property("material_slot_name"))
                              for slot in mesh.get_editor_property("materials")],
                "bones": {str(bone): xyz(poses.get_bone_pose(pose, bone, world_space).translation) for bone in bones},
            }
            if kind in ("Horse", "GoldenEagle", "AriakeCatfish", "CommonCarp", "UnidentifiedFish"):
                probes = [bone for bone in bones if any(word in str(bone).lower() for word in
                          ("hoof", "wing1", "wing3", "head", "skull", "neck", "hips", "hand", "foot", "tail", "bone"))]
                probes = (probes or bones)[:32]
                rig["samples"] = {}
                for clip in clips:
                    if clip.get_editor_property("skeleton") != skeleton:
                        continue
                    frames = []
                    for index in range(round(clip.get_play_length() * 24) + 1):
                        time = min(clip.get_play_length(), index / 24)
                        sample = poses.get_anim_pose_at_time(clip, time, options)
                        frames.append([round(time, 4), *[xyz(poses.get_bone_pose(sample, bone, world_space).translation)
                                                        for bone in probes]])
                    rig["samples"][clip.get_name()] = {"probes": [str(bone) for bone in probes], "frames": frames}
            rigs.append(rig)
        report[kind] = rigs
    path = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "ExpandedFaunaImport" / "rig_report.json"
    path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    unreal.log(f"ECO_EXPANDED_RIG_REPORT {path}")


if __name__ == "__main__":
    if "-EcoFaunaBoundMaterials" in unreal.SystemLibrary.get_command_line():
        audit_bound_materials()
    else:
        audit()

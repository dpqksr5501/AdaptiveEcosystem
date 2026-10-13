"""Read-only asset/contact audit. Run through the editor's Python console."""
import json
from pathlib import Path
import unreal

out = Path(unreal.Paths.project_saved_dir()) / "CreatureContactAudit.json"
report = {"animals": {}, "landscapes": [], "layer_infos": []}
options = unreal.AnimPoseEvaluationOptions()
for kind, folder, prefix in (
    ("Wolf", "/Game/AnimalVarietyPack/Wolf/Animations", "ANIM_Wolf"),
    ("Deer", "/Game/AnimalVarietyPack/DeerStagAndDoe/Animations", "ANIM_DeerStag"),
):
    clips = {}
    suffixes = ["Walk", "WalkTurnL", "WalkTurnR", "Run"] + (["RunTurnL", "RunTurnR"] if kind == "Wolf" else [])
    for suffix in suffixes:
        clip = unreal.load_asset(folder + "/" + prefix + "_" + suffix)
        pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, 0.0, options)
        bones = [str(n) for n in unreal.AnimPoseExtensions.get_bone_names(pose)]
        candidates = [b for b in bones if any(s in b.lower() for s in ("foot", "hoof", "paw", "toe", "hand", "finger0"))]
        length = clip.get_play_length()
        samples = {b: [] for b in candidates}
        for index in range(121):
            time = length * index / 120
            pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(clip, time, options)
            for bone in candidates:
                p = unreal.AnimPoseExtensions.get_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD).translation
                samples[bone].append([round(time, 6), round(p.x, 4), round(p.y, 4), round(p.z, 4)])
        clips[suffix] = {"asset": clip.get_path_name(), "length": length, "bones": bones, "samples": samples}
    report["animals"][kind] = clips
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    if isinstance(actor, unreal.LandscapeProxy):
        material = actor.get_editor_property("landscape_material")
        report["landscapes"].append({"actor": actor.get_actor_label(), "material": material.get_path_name() if material else None})
registry = unreal.AssetRegistryHelpers.get_asset_registry()
for data in registry.get_assets_by_class(unreal.TopLevelAssetPath("/Script/Landscape", "LandscapeLayerInfoObject"), True):
    layer = data.get_asset()
    physical = layer.get_editor_property("phys_material")
    report["layer_infos"].append({"asset": layer.get_path_name(), "physical": physical.get_path_name() if physical else None})
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
unreal.log("CREATURE_CONTACT_AUDIT_OK " + str(out))

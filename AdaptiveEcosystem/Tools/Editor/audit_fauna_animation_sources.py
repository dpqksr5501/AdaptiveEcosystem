"""Read the owned fauna source rigs and loop seams without editing assets."""

import json
import math
from pathlib import Path

import unreal as u


def rotation_step(a, b):
    dot = abs(sum(getattr(a, axis) * getattr(b, axis) for axis in "xyzw"))
    return round(2. * math.degrees(math.acos(min(1., dot))), 2)


def audit(kind, folder, names):
    result = {}
    pose = u.AnimPoseExtensions
    options = u.AnimPoseEvaluationOptions()
    for name in names:
        clip = u.load_asset(f"{folder}/{name}")
        if not clip:
            raise RuntimeError(f"Missing {folder}/{name}")
        duration = clip.get_play_length()
        count = max(2, round(duration * 60))
        samples = [pose.get_anim_pose_at_time(clip, duration * index / count, options) for index in range(count + 1)]
        bones = [str(bone) for bone in pose.get_bone_names(samples[0])]
        ground_parts = ("toe", "foot", "leg", "hoof") if kind in ("GoldenEagle", "Bighorn") else ("toebase", "handindex", "paw")
        tracked = [bone for bone in bones if bone in ("Root", "Hips", "Tail01", "DEF-thigh_R", "DEF-thigh_L")
                   or any(part in bone.lower() for part in ground_parts)]
        tracks = {}
        for bone in tracked:
            rotations = [pose.get_bone_pose(sample, bone, u.AnimPoseSpaces.LOCAL).rotation for sample in samples]
            positions = [pose.get_bone_pose(sample, bone, u.AnimPoseSpaces.WORLD).translation for sample in samples]
            tracks[bone] = {"wrap_deg": rotation_step(rotations[-1], rotations[0]),
                            "peak_step_deg": max(rotation_step(a, b) for a, b in zip(rotations, rotations[1:])),
                            "z_start": positions[0].z, "z_end": positions[-1].z,
                            "z_min": min(pos.z for pos in positions), "z_max": max(pos.z for pos in positions)}
        result[name] = {"duration": duration, "tracks": tracks, "bones": bones}
    return result


def rig_parents(kind):
    folder = f"/Game/JYU/ExpandedFauna/{kind}"
    cls = u.load_class(None, f"{folder}/BP_{kind}.BP_{kind}_C")
    mesh = u.get_default_object(cls).get_editor_property("visual_mesh")
    component = u.SkeletalMeshComponent()
    component.set_skeletal_mesh_asset(mesh)
    return {str(bone): str(component.get_parent_bone(bone)) for bone in
            (component.get_bone_name(index) for index in range(component.get_num_bones()))}


try:
    mink = "/Game/JYU/ExpandedFauna/Mink/Imported"
    rat = "/Game/JYU/Fauna/Rat"
    report = {"Mink": audit("Mink", mink, [f"cotw_american_mink_Anim_american_mink_{name}" for name in
              ("idle_01", "startwalk_fwd_01", "startrun_fwd_01", "startsprint_fwd_01")]),
              "Rat": audit("Rat", rat, ("ANIM_Rat_SlowGait", "Imported/ANIM_Rat_Run")),
              "GoldenEagle": audit("GoldenEagle", "/Game/JYU/ExpandedFauna/GoldenEagle", ("ANIM_GoldenEagle_PreviewStep",)),
              "Bighorn": audit("Bighorn", "/Game/JYU/ExpandedFauna/Bighorn", ("Imported/BigHorn_Animated_Anim_Walk",))}
    report["rig_parents"] = {kind: rig_parents(kind) for kind in ("GoldenEagle", "Bighorn")}
    output = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit" / "AnimationSourceSeams.json"
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    u.log("FAUNA_ANIMATION_SOURCE_AUDIT_FINISHED")
finally:
    u.SystemLibrary.quit_editor()

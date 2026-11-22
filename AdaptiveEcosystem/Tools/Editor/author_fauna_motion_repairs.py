"""Prepare the owned, in-place locomotion assets for Mink and Rat."""

from pathlib import Path
import math
import re
import runpy

import unreal as u


SETUP = runpy.run_path(str(Path(__file__).with_name("setup_jyu_expanded_fauna.py")))
POSE = u.AnimPoseExtensions
LOCAL = u.AnimPoseSpaces.LOCAL
WORLD = u.AnimPoseSpaces.WORLD
OPTIONS = u.AnimPoseEvaluationOptions()
PAWS = ("LeftHandIndex1", "RightHandIndex1", "LeftFootToeBase", "RightFootToeBase")
THIGHS = {"DEF-thigh_R", "DEF-thigh_L"}


def load(path):
    asset = u.load_asset(path)
    if not asset:
        raise RuntimeError(f"Missing {path}")
    return asset


def periodic_track(samples, bone, seam, smooth):
    track = [POSE.get_bone_pose(sample, bone, LOCAL) for sample in samples]
    count = len(track) - 1
    # Close the measured seam with a raised-cosine overlap. The first frame
    # stays exact, and the overlap does not create a new velocity step.
    for index in range(count - seam + 1, count + 1):
        phase = (index - (count - seam)) / seam
        track[index] = track[index].lerp(track[0], .5 - .5 * math.cos(math.pi * phase))
    if smooth:
        source = track[:-1]
        for index, current in enumerate(source):
            left = source[(index - 2) % count].lerp(source[(index - 1) % count], .75)
            right = source[(index + 2) % count].lerp(source[(index + 1) % count], .75)
            current = current.lerp(left.lerp(right, .5), .75)
            original = source[index]
            original.rotation = current.rotation
            track[index] = original
        track[-1] = track[0]
    return track


def bake(folder, name, mesh, source, dry_mink, smooth_bones=()):
    factory = SETUP["set_props"](u.AnimSequenceFactory(), target_skeleton=mesh.get_editor_property("skeleton"),
                                 preview_skeletal_mesh=mesh)
    clip = SETUP["create_owned"](folder, name, u.AnimSequence, factory)
    duration = source.get_play_length()
    rate = 60
    count = round(duration * rate)
    if count < 8:
        raise RuntimeError(f"Expected enough gait pose samples in {source.get_name()}")
    samples = [POSE.get_anim_pose_at_time(source, duration * i / count, OPTIONS) for i in range(count + 1)]
    bones = POSE.get_bone_names(samples[0])
    root = bones[0]
    seam = max(2, min(9, count // 3))
    controller = clip.get_editor_property("controller")
    controller.open_bracket(f"Repair {name} locomotion loop", False)
    try:
        controller.remove_all_bone_tracks(False)
        controller.set_frame_rate(u.FrameRate(rate, 1), False)
        controller.set_number_of_frames(u.FrameNumber(count), False)
        for bone in bones:
            track = periodic_track(samples, bone, seam, str(bone) in smooth_bones)
            if dry_mink and bone == root:
                for i, key in enumerate(track):
                    # Mink's imported +Z points down. Put the lowest authored
                    # paw on the visual floor after the component is upright.
                    source_frame = samples[i]
                    downward = max(POSE.get_bone_pose(source_frame, paw, WORLD).translation.z for paw in PAWS)
                    baseline = POSE.get_bone_pose(source_frame, root, LOCAL).translation
                    translation = key.translation
                    normalized_z = baseline.z - downward - .4
                    if i > count - seam:
                        phase = (i - (count - seam)) / seam
                        weight = .5 - .5 * math.cos(math.pi * phase)
                        first_floor = max(POSE.get_bone_pose(samples[0], paw, WORLD).translation.z for paw in PAWS)
                        first_z = POSE.get_bone_pose(samples[0], root, LOCAL).translation.z - first_floor - .4
                        normalized_z = (1. - weight) * normalized_z + weight * first_z
                    translation.z = normalized_z
                    key.translation = translation
                    track[i] = key
            if not controller.add_bone_curve(bone, False) or not controller.set_bone_track_keys(
                    bone, [key.translation for key in track], [key.rotation for key in track],
                    [key.scale3d for key in track], False):
                raise RuntimeError(f"Could not write {name}/{bone}")
    finally:
        controller.close_bracket(False)
    SETUP["set_props"](clip, enable_root_motion=False, force_root_lock=not dry_mink,
                       rate_scale=source.get_editor_property("rate_scale"))
    SETUP["save"](clip)
    return clip


def representation(folder, kind):
    bp = load(f"{folder}/BP_{kind}")
    defaults = u.get_default_object(SETUP["generated"](bp))
    return bp, defaults.get_editor_property("visual_mesh"), defaults.get_editor_property("animation_profile")


def repair_mink():
    folder = "/Game/JYU/ExpandedFauna/Mink"
    bp, mesh, profile = representation(folder, "Mink")
    prefix = folder + "/Imported/cotw_american_mink_Anim_american_mink_"
    source = [load(prefix + name) for name in ("idle_01", "startwalk_fwd_01", "startsprint_fwd_01")]
    idle = POSE.get_anim_pose_at_time(source[0], 0., OPTIONS)
    body = POSE.get_bone_pose(idle, "Hips", WORLD).translation
    if min(POSE.get_bone_pose(idle, paw, WORLD).translation.z for paw in PAWS) <= body.z:
        raise RuntimeError("Mink source no longer matches the inverted rig")
    clips = [bake(folder, f"ANIM_Mink_Ground{label}", mesh, clip, True) for label, clip in
             zip(("Idle", "Walk", "Run"), source)]
    blend = load(f"{folder}/BS_Mink")
    if not u.EcoCreatureBlendSpaceLibrary.configure_locomotion(blend, *clips, 75., 280.):
        raise RuntimeError("Mink locomotion blend configuration failed")
    bind = POSE.get_reference_pose(mesh.get_editor_property("skeleton"))
    direction = POSE.get_bone_pose(bind, "Head", WORLD).translation - POSE.get_bone_pose(bind, "Hips", WORLD).translation
    yaw = math.atan2(direction.y, direction.x)
    forward = u.Vector(math.cos(yaw), math.sin(yaw), 0.)
    basis = u.MathLibrary.multiply_quat_quat(u.Rotator(roll=180.).quaternion(), u.Rotator(yaw=-math.degrees(yaw)).quaternion())
    if not u.EcoCreatureBlendSpaceLibrary.configure_representation(bp, blend, basis.rotator(), forward):
        raise RuntimeError("Mink upright visual basis configuration failed")
    profile.set_editor_property("body_bone", "Hips")
    # Collapsing to the existing rest clip remains unchanged; movement and the
    # standing idle use the owned normalized blend samples.
    SETUP["save"](profile)
    SETUP["save"](blend)
    SETUP["save"](bp)


def repair_ground_gait(kind, clip_paths, speeds, track_names):
    folder = f"/Game/JYU/Fauna/{kind}"
    _, mesh, _ = representation(folder, kind)
    source = [load(f"{folder}/{path}") for path in clip_paths]
    clips = [bake(folder, f"ANIM_{kind}_Stable_{label}", mesh, clip, False, track_names) for label, clip in
             zip(("Walk", "Run"), source[1:])]
    base = SETUP["BASE"]
    contact_clip = base["contact_clip"]
    contact_clip.__globals__["ROOT"] = "/Game/JYU/Fauna"
    limbs = base["rat_rig"](mesh)[2] if kind == "Rat" else base["bone_legs"](kind)
    for clip in clips:
        contact_clip(kind, clip, limbs)
    blend = load(f"{folder}/BS_{kind}")
    if not u.EcoCreatureBlendSpaceLibrary.configure_locomotion(blend, source[0], *clips, *speeds):
        raise RuntimeError(f"{kind} locomotion blend configuration failed")
    if kind == "Rat":
        # The idle and fast-gait clips have very different thigh angles.
        # Ease the sample weights on entry as well as smoothing the gait keys.
        blend.set_editor_property("target_weight_interpolation_speed_per_sec", 5.)
    SETUP["save"](blend)


def rebuild_ground_graph(folder, kind, bp, profile):
    anim = load(f"{folder}/ABP_{kind}")
    if not u.EcoCreatureAnimationBuilder.build_pose_graph(anim, profile):
        raise RuntimeError(f"{kind} ground IK graph rejected the foot chains")
    if not u.EcoCreatureAnimationBuilder.configure_behavior_representation(bp, profile, SETUP["generated"](anim)):
        raise RuntimeError(f"Failed to bind {kind} ground IK graph")
    for asset in (profile, anim, bp):
        SETUP["save"](asset)


def repair_eagle_contacts():
    folder = "/Game/JYU/ExpandedFauna/GoldenEagle"
    bp, mesh, profile = representation(folder, "GoldenEagle")
    rig = u.SkeletalMeshComponent()
    rig.set_skeletal_mesh_asset(mesh)
    feet = ("toe2_3_fk_L", "toe2_3_fk_R")
    ends = tuple(str(rig.get_parent_bone(foot)) for foot in feet)
    if ends != ("foot_FK_L", "foot_FK_R"):
        raise RuntimeError(f"Unexpected eagle ground chains: {ends}")
    SETUP["set_props"](profile, body_bone="HIP", foot_bones=feet, ik_end_bones=ends,
                       contact_heights=[35., 35.], foot_clearance_cm=.45,
                       max_foot_correction_cm=8., enable_ground_ik=True)
    rebuild_ground_graph(folder, "GoldenEagle", bp, profile)


def repair_bighorn_contacts():
    folder = "/Game/JYU/ExpandedFauna/Bighorn"
    bp, mesh, profile = representation(folder, "Bighorn")
    idle = load(f"{folder}/Imported/BigHorn_Animated_Anim_Stand_Breathing_01")
    blend = load(f"{folder}/BS_Bighorn")
    gait = runpy.run_path(str(Path(__file__).with_name("bighorn_footfall_gait.py")))
    defaults = u.get_default_object(SETUP["generated"](bp))
    gait["configure"](SETUP, mesh, idle, blend, profile, defaults.get_editor_property("mesh_forward_axis"))
    rebuild_ground_graph(folder, "Bighorn", bp, profile)


try:
    command = u.SystemLibrary.get_command_line()
    if "-EcoApplyFaunaMotionRepairs" not in command:
        raise RuntimeError("Use -EcoApplyFaunaMotionRepairs to apply owned asset repairs")
    available = {"Mink", "Rat", "Buffalo", "GoldenEagle", "Bighorn"}
    requested = re.search(r"-EcoFaunaMotionSpecies=([A-Za-z+]+)\b", command)
    kinds = set(requested[1].split("+")) if requested else available
    if not kinds or not kinds <= available:
        raise RuntimeError(f"Expected one or more of {sorted(available)}")
    if "Mink" in kinds:
        repair_mink()
    if "Rat" in kinds:
        repair_ground_gait("Rat", ("Imported/ANIM_Rat_Idle", "ANIM_Rat_SlowGait", "Imported/ANIM_Rat_Run"),
                           (55., 220.), THIGHS)
    if "Buffalo" in kinds:
        buffalo_limbs = {f"bip01_{side}_{joint}" for side in "lr" for joint in
                         ("forearm", "upperarm", "thigh", "calf", "horselink")}
        repair_ground_gait("Buffalo", ("Imported/ANIM_Buffalo_Idle", "ANIM_Buffalo_Walk", "ANIM_Buffalo_Trot"),
                           (100., 240.), buffalo_limbs)
    if "GoldenEagle" in kinds:
        repair_eagle_contacts()
    if "Bighorn" in kinds:
        repair_bighorn_contacts()
    u.log("FAUNA_MOTION_ASSETS_REPAIRED")
finally:
    u.SystemLibrary.quit_editor()

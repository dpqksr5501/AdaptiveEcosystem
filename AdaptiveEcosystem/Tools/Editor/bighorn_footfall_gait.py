"""Author Bighorn locomotion with world-stationary stance at the sample speed."""

import math

import unreal as u


FOLDER = "/Game/JYU/ExpandedFauna/Bighorn"
FEET = ("RigLFLegAnkle", "RigRFLegAnkle", "RigLBLegAnkle", "RigRBLegAnkle")
POSE = u.AnimPoseExtensions
WORLD = u.AnimPoseSpaces.WORLD
LOCAL = u.AnimPoseSpaces.LOCAL
ML = u.MathLibrary
GAITS = (
    ("Walk", 135., .70, .53, 9., (0., .5, .75, .25)),
    # Two whole compression frames of stance with diagonal half-cycle pairs.
    ("Run", 570., .40, 1. / 6., 19., (0., .5, .5, 0.)),
)


def gait_offset(phase, speed, duration, stance, lift):
    """Return in-place longitudinal and vertical offsets for a footfall phase."""
    stride = speed * duration * stance
    if phase < stance:
        return stride * .5 - phase * speed * duration, 0.
    t = (phase - stance) / (1. - stance)
    # Match the backward velocity at liftoff and touchdown so the swing can
    # reverse direction without a step in position or velocity.
    x = stride * (t*t*(3. - 2.*t) - .5) - speed * duration * (1. - stance) * t * (1. - t) * (1. - 2.*t)
    return x, lift * math.sin(math.pi * t)**2


def save_gait(setup, mesh, pose, forward, name, speed, duration, stance, lift, phases, turn):
    rig = u.SkeletalMeshComponent()
    rig.set_skeletal_mesh_asset(mesh)
    local = lambda bone: POSE.get_bone_pose(pose, bone, LOCAL)
    world = lambda bone: POSE.get_bone_pose(pose, bone, WORLD)
    pelvis = "RigPelvis"
    parent_up = ML.quat_rotate_vector(ML.quat_inversed(world(rig.get_parent_bone(pelvis)).rotation), u.Vector(0., 0., 1.))
    body_drop = 13.
    # Bake at 60 Hz while keeping the length on the project's 30 Hz
    # compression grid. Both model and platform rates get whole frames.
    rate = 60
    frames = 2 * round(duration * 30)
    duration = frames / rate
    rotations = {}
    max_reach_error = 0.
    for foot, phase_shift in zip(FEET, phases):
        end = rig.get_parent_bone(foot)
        joint = rig.get_parent_bone(end)
        root = rig.get_parent_bone(joint)
        parent = rig.get_parent_bone(root)
        base = (world(root), world(joint), world(end))
        hip, knee, ankle = [bone.translation for bone in base]
        upper, lower = (knee-hip).length(), (ankle-knee).length()
        parent_inverse = ML.quat_inversed(world(parent).rotation)
        rows = ([], [], [])
        target_bias = u.Vector(0., 0., body_drop)
        neutral = ankle + target_bias - hip
        longitudinal = neutral.dot(forward)
        lateral = neutral - forward * longitudinal
        span = math.sqrt(max(0., (upper + lower - .2)**2 - lateral.dot(lateral)))
        half_stride = speed * duration * stance * .5
        center_span = max(0., span - half_stride - 4.)
        contact_center = ankle + target_bias + forward * (min(max(longitudinal, -center_span), center_span) - longitudinal)
        for frame in range(frames + 1):
            phase = ((frame % frames) / frames + phase_shift) % 1.
            x, z = gait_offset(phase, speed, duration, stance, lift)
            # Turning samples use the same contact phase, with the stance
            # path arcing modestly toward the direction of traversal.
            travel = (forward * x).rotate_angle_axis(turn * (x / max(1., speed * duration)), u.Vector(0., 0., 1.))
            goal = contact_center + travel + u.Vector(0., 0., z)
            axis = (goal - hip).normal()
            length = min(max((goal - hip).length(), abs(upper-lower) + .02), upper+lower-.02)
            if phase < stance:
                max_reach_error = max(max_reach_error, abs((goal-hip).length() - length))
            knee_offset = knee - hip
            bend = (knee_offset - axis * knee_offset.dot(axis)).normal()
            projection = (upper*upper + length*length - lower*lower) / (2.*length)
            solved_knee = hip + axis*projection + bend * math.sqrt(max(0., upper*upper - projection*projection))
            solved_ankle = hip + axis*length
            thigh = ML.multiply_quat_quat(ML.quat_find_between_vectors(knee-hip, solved_knee-hip), base[0].rotation)
            shin = ML.multiply_quat_quat(ML.quat_find_between_vectors(ankle-knee, solved_ankle-solved_knee), base[1].rotation)
            for row, value in zip(rows, (ML.multiply_quat_quat(parent_inverse, thigh),
                    ML.multiply_quat_quat(ML.quat_inversed(thigh), shin),
                    ML.multiply_quat_quat(ML.quat_inversed(shin), base[2].rotation))):
                row.append(value)
        rotations.update(zip(map(str, (root, joint, end)), rows))

    if max_reach_error > 2.:
        raise RuntimeError(f"{name} stance requires {max_reach_error:.2f} cm beyond the rig's reach")
    factory = setup["set_props"](u.AnimSequenceFactory(), target_skeleton=mesh.get_editor_property("skeleton"), preview_skeletal_mesh=mesh)
    clip = setup["create_owned"](FOLDER, name, u.AnimSequence, factory)
    controller = clip.get_editor_property("controller")
    controller.open_bracket(f"Bake {name} footfall cycle", False)
    try:
        controller.remove_all_bone_tracks(False)
        controller.set_frame_rate(u.FrameRate(rate, 1), False)
        controller.set_number_of_frames(u.FrameNumber(frames), False)
        for bone in POSE.get_bone_names(pose):
            transform = local(bone)
            location = transform.translation - parent_up * body_drop if str(bone) == pelvis else transform.translation
            keys = rotations.get(str(bone), [transform.rotation] * (frames + 1))
            if not controller.add_bone_curve(bone, False) or not controller.set_bone_track_keys(
                    bone, [location] * (frames + 1), keys, [transform.scale3d] * (frames + 1), False):
                raise RuntimeError(f"Could not write {name}/{bone}")
    finally:
        controller.close_bracket(False)
    setup["set_props"](clip, enable_root_motion=False, force_root_lock=True)
    lib = u.AnimationLibrary
    track = "EcoFaunaFootsteps"
    if track in [str(value) for value in lib.get_animation_notify_track_names(clip)]:
        lib.remove_animation_notify_track(clip, track)
    lib.add_animation_notify_track(clip, track, u.LinearColor(.2, .8, .3, 1.))
    for foot, phase in zip(FEET, phases):
        when = max(.005, duration * (-phase % 1.))
        notify = lib.add_animation_notify_event(clip, track, when, u.EcoAnimNotifyFootstep)
        if not notify:
            raise RuntimeError(f"Could not attach {foot} footfall to {name}")
        notify.set_editor_property("foot_bone", foot)
    setup["save"](clip)
    u.log(f"BIGHORN_GAIT_STANCE_REACH {name} {max_reach_error:.3f} cm")
    return clip


def configure(setup, mesh, idle, blend, profile, forward):
    forward = u.Vector(forward.x, forward.y, 0.).normal()
    if forward.length() < .99:
        raise RuntimeError("Bighorn requires a horizontal mesh facing axis")
    pose = POSE.get_anim_pose_at_time(idle, 0., u.AnimPoseEvaluationOptions())
    walk_duration = GAITS[0][2]
    # Blend Space advances a weighted cycle length. A long source idle would
    # slow the short walk cycle even at ordinary, slightly sub-sample speeds.
    blend_idle = setup["sample_clip"]("Bighorn", mesh, "PlantedIdle", idle, 0., walk_duration, True)
    clips = []
    for label, speed, cycle, stance, lift, phases in GAITS:
        for suffix, turn in (("", 0.), ("Left", -36.), ("Right", 36.)):
            clips.append(save_gait(setup, mesh, pose, forward, f"ANIM_Bighorn_Planted{label}{suffix}",
                                   speed, cycle, stance, lift, phases, turn))
    if not u.EcoCreatureBlendSpaceLibrary.configure_turning(blend, blend_idle, *clips, 135., 570.):
        raise RuntimeError("Could not bind Bighorn footfall cycles")
    heights = [max(0., min(50., POSE.get_bone_pose(pose, foot, WORLD).translation.z)) for foot in FEET]
    setup["set_props"](profile, contact_heights=heights, max_plant_correction_cm=12.)
    setup["save"](blend)

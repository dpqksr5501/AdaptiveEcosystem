"""Build the opt-in fauna map and its editable species presentation assets."""

import math
import re
import runpy
import shutil
from pathlib import Path
from zipfile import ZipFile

import unreal


ROOT = "/Game/JYU/Fauna"
MAP = "/Game/JYU/Maps/LV_JYU_Fauna"
OWNER = "JYU.Fauna.20261108"
VAULT = Path(r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\FabLibrary")
ASSETS = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()
ACTORS = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
POSE = unreal.AnimPoseExtensions
WORLD_SPACE = unreal.AnimPoseSpaces.WORLD
LOCAL_SPACE = unreal.AnimPoseSpaces.LOCAL

PACK_CLIPS = {
    "Pig": ["IdleBreathe", "Walk", "Run", "IdleLookAround", "SniffleforFood", "Chew", "Rest", "Death",
            "WalkTurnL", "WalkTurnR", "RunTurnL", "RunTurnR"],
    "Fox": ["IdleBreathe", "Walk", "Run", "IdleLookAround", "Resting", "Sleeping", "Death", "Bite",
            "WalkTurnL", "WalkTurnR", "RunTurnL", "RunTurnR"],
    "Crow": ["IdleLookAround", "Walk", "Hop", "IdleScratchWing", "EatSomething", "DeathGrounded",
             "TakeOff", "Fly", "Landing"],
}


def set_props(obj, **values):
    for name, value in values.items():
        obj.set_editor_property(name, value)
    return obj


def configure_crow_orientation(blueprint):
    set_props(unreal.get_default_object(generated(blueprint)), flight_pitch_limit=22., flight_bank_limit=18.)


def require(path):
    asset = unreal.load_asset(path)
    if not asset:
        raise RuntimeError(f"Missing asset {path}")
    return asset


def save(asset):
    if not ASSETS.save_loaded_asset(asset, only_if_is_dirty=False):
        raise RuntimeError(f"Could not save {asset.get_path_name()}")


def create_owned(folder, name, cls, factory):
    path = f"{folder}/{name}"
    asset = unreal.load_asset(path) if ASSETS.does_asset_exist(path) else None
    if asset:
        if ASSETS.get_metadata_tag(asset, "JYUOwner") != OWNER:
            raise RuntimeError(f"Unexpected existing asset {path}")
        return asset
    asset = TOOLS.create_asset(name, folder, cls, factory)
    if not asset:
        raise RuntimeError(f"Failed to create {path}")
    ASSETS.set_metadata_tag(asset, "JYUOwner", OWNER)
    return asset


def duplicate_owned(source, path):
    if ASSETS.does_asset_exist(path):
        asset = require(path)
        if ASSETS.get_metadata_tag(asset, "JYUOwner") != OWNER:
            raise RuntimeError(f"Unexpected existing asset {path}")
        return asset
    asset = ASSETS.duplicate_asset(source, path)
    if not asset:
        raise RuntimeError(f"Failed to duplicate {source} to {path}")
    ASSETS.set_metadata_tag(asset, "JYUOwner", OWNER)
    return asset


def generated(asset):
    cls = unreal.BlueprintEditorLibrary.generated_class(asset)
    if not cls:
        raise RuntimeError(f"No generated class {asset.get_path_name()}")
    return cls


def import_fbx(folder, name, source, skeleton=None):
    path = f"{folder}/{name}"
    replace = False
    if ASSETS.does_asset_exist(path):
        asset = require(path)
        if ASSETS.get_metadata_tag(asset, "JYUOwner") != OWNER:
            raise RuntimeError(f"Unexpected existing import {path}")
        bound_skeleton = asset.get_editor_property("skeleton")
        if bound_skeleton and (not skeleton or bound_skeleton == skeleton):
            return asset
        replace = True
    staging = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "FaunaImport" / source.parent.name
    staging.mkdir(parents=True, exist_ok=True)
    staged = staging / source.name
    if not staged.exists():
        shutil.copy2(source, staged)
    options = set_props(unreal.FbxImportUI(), automated_import_should_detect_type=False, import_as_skeletal=True)
    if skeleton:
        set_props(options, mesh_type_to_import=unreal.FBXImportType.FBXIT_ANIMATION, import_mesh=False,
                  import_animations=True, skeleton=skeleton, import_materials=False, import_textures=False)
    else:
        set_props(options, mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH, import_mesh=True,
                  import_animations=False, import_materials=True, import_textures=True, create_physics_asset=True)
    task = set_props(unreal.AssetImportTask(), filename=str(staged), destination_path=folder, destination_name=name,
                     automated=True, options=options, factory=unreal.FbxFactory(), save=True, replace_existing=replace)
    TOOLS.import_asset_tasks([task])
    asset = require(path)
    ASSETS.set_metadata_tag(asset, "JYUOwner", OWNER)
    save(asset)
    if not skeleton:
        # The FBX task saves its primary object only. Keep generated dependencies loadable in a fresh process.
        for dependency in (asset.get_editor_property("skeleton"), asset.get_editor_property("physics_asset")):
            if not dependency:
                raise RuntimeError(f"Missing FBX dependency {path}")
            save(dependency)
        ASSETS.save_directory(folder, only_if_is_dirty=False)
    return asset


def configure_fab_body_material(material):
    edit = unreal.MaterialEditingLibrary
    changed = False
    if material.get_editor_property("blend_mode") != unreal.BlendMode.BLEND_OPAQUE:
        # The FBX opacity texture imports as translucent on the solid body.
        set_props(material, blend_mode=unreal.BlendMode.BLEND_OPAQUE)
        changed = True
    emissive = unreal.MaterialProperty.MP_EMISSIVE_COLOR
    base = edit.get_material_property_input_node(material, unreal.MaterialProperty.MP_BASE_COLOR)
    glow = edit.get_material_property_input_node(material, emissive)
    if isinstance(base, unreal.MaterialExpressionTextureSample) and isinstance(glow, unreal.MaterialExpressionTextureSample):
        if base.get_editor_property("texture") == glow.get_editor_property("texture"):
            # FBX wired the same diffuse map to both inputs. Keep it only as reflected color.
            zero = edit.create_material_expression(material, unreal.MaterialExpressionConstant, -240, 420)
            set_props(zero, r=0.)
            if not edit.connect_material_property(zero, "", emissive):
                raise RuntimeError(f"Could not clear the imported emissive on {material.get_path_name()}")
            changed = True
    if changed:
        edit.recompile_material(material)
        save(material)


def import_fab(kind):
    if kind == "Buffalo":
        listing, prefix = "Buffalo_A2-3ae82f01", "Buffalo_A2"
        suffixes = ["Idle", "Lying", "Die", "Turnleft"]
    else:
        listing, prefix = "Leopard_Hybrid_A2-3506d61b", "Leopard_Hybrid_A2"
        suffixes = ["Idle1", "Idle2", "Walk", "Run", "Atk1"]
    source = VAULT / listing / "fbx" / "source_extracted" / "FbxMaya_extracted" / "FbxMaya"
    folder = f"{ROOT}/{kind}/Imported"
    mesh = import_fbx(folder, "SK_" + kind, source / (prefix + ".Fbx"))
    skeleton = mesh.get_editor_property("skeleton")
    for slot in mesh.get_editor_property("materials"):
        material = slot.get_editor_property("material_interface")
        if isinstance(material, unreal.Material) and material.get_path_name().startswith(folder + "/"):
            configure_fab_body_material(material)
    clips = {}
    for suffix in suffixes:
        clip = import_fbx(folder, f"ANIM_{kind}_{suffix}", source / f"{prefix}_{suffix}_Motion.Fbx", skeleton)
        if clip.get_editor_property("enable_root_motion") or not clip.get_editor_property("force_root_lock"):
            set_props(clip, enable_root_motion=False, force_root_lock=True)
            save(clip)
        clips[suffix] = clip
    return mesh, clips


def bone_legs(kind):
    if kind == "Crow":
        return [(f"CROW_-{side}-Foot", f"CROW_-{side}-HorseLink") for side in ("L", "R")]
    if kind in ("Buffalo", "Leopard"):
        front = "hand_end" if kind == "Buffalo" else "finger0"
        return [(f"bip01_{side}_{contact}", f"bip01_{side}_{end}") for side in ("l", "r")
                for contact, end in ((front, "hand"), ("foot", "horselink"))]
    prefix = {"Pig": "PIG", "Fox": "Fox", "Deer": "STAG", "Wolf": "Wolf"}[kind]
    return [(f"{prefix}_-{side}-{contact}", f"{prefix}_-{side}-{end}") for side in ("L", "R")
            for contact, end in (("Finger0", "Hand"), ("Foot", "HorseLink"))]


def rat_rig(mesh):
    pose = POSE.get_reference_pose(mesh.get_editor_property("skeleton"))
    names = {re.sub(r"[^a-z0-9]", "", str(bone).lower()): str(bone) for bone in POSE.get_bone_names(pose)}
    component = unreal.SkeletalMeshComponent()
    component.set_skeletal_mesh_asset(mesh)
    legs = [(names[key], str(component.get_parent_bone(names[key])))
            for key in ("deffronttoel", "deffronttoer", "deftoel", "deftoer")]
    points = [bone_transform(pose, toe).translation for toe, _ in legs]
    direction = (points[0] + points[1] - points[2] - points[3]) * .5
    yaw = math.degrees(math.atan2(direction.y, direction.x))
    forward = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.)
    return pose, names, legs, yaw, forward, points


def rat_death(mesh, idle):
    reference, names, legs, _, forward, _ = rat_rig(mesh)
    pose = POSE.get_anim_pose_at_time(idle, 0., unreal.AnimPoseEvaluationOptions())
    root = str(POSE.get_bone_names(reference)[0])
    base = bone_transform(pose, root, LOCAL_SPACE)
    pivot = bone_transform(pose, names["defspine007"]).translation
    contacts = [bone_transform(pose, toe).translation for toe, _ in legs]
    contacts.extend(bone_transform(pose, name).translation for key, name in names.items() if key.startswith("def"))
    floor = min(point.z for point in contacts)
    lib = unreal.MathLibrary

    def sample(t):
        ease = t * t * (3. - 2. * t)
        roll = lib.quat_make_from_rotation_vector(forward * (86. * ease))
        lift = floor - min((pivot + lib.quat_rotate_vector(roll, point - pivot)).z for point in contacts)
        translation = pivot + lib.quat_rotate_vector(roll, base.translation - pivot) + unreal.Vector(0., 0., lift)
        return translation, lib.multiply_quat_quat(roll, base.rotation), base.scale3d

    return bake_pose("Rat", mesh, "FallSide", 24, root, sample, pose)


def import_rat():
    folder = f"{ROOT}/Rat/Imported"
    mesh_path = f"{folder}/SK_Rat"
    clips = {name: f"{folder}/ANIM_Rat_{name}" for name in ("Idle", "Run", "Jump")}
    if ASSETS.does_asset_exist(mesh_path) and all(ASSETS.does_asset_exist(path) for path in clips.values()):
        return require(mesh_path), {name: require(path) for name, path in clips.items()}
    staging = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "FaunaImport" / "Rat"
    staging.mkdir(parents=True, exist_ok=True)
    textures = ("BaseColor", "Normal", "Roughness")
    with ZipFile(Path.home() / "Desktop" / "mouse.zip") as archive:
        for entry, name in [("source/mouse model.fbx", "SK_Rat.fbx"),
                            *((f"textures/DefaultMaterial_{kind}.png", f"T_Rat_{kind}.png") for kind in textures)]:
            destination = staging / name
            with archive.open(entry) as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)
    options = set_props(unreal.FbxImportUI(), automated_import_should_detect_type=False, import_as_skeletal=True,
                        mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH, import_mesh=True,
                        import_animations=True, import_materials=False, import_textures=False, create_physics_asset=True)
    task = set_props(unreal.AssetImportTask(), filename=str(staging / "SK_Rat.fbx"), destination_path=folder,
                     automated=True, options=options, factory=unreal.FbxFactory(), save=False, replace_existing=False)
    TOOLS.import_asset_tasks([task])
    mesh = next(obj for obj in task.get_objects() if isinstance(obj, unreal.SkeletalMesh))
    imported = [obj for obj in unreal.ObjectIterator(unreal.AnimSequence) if obj.get_path_name().startswith(folder + "/")]
    unreal.log(f"ECO_RAT_IMPORTED {mesh.get_name()} {[obj.get_name() for obj in imported]}")
    selected = {}
    for kind, pattern in (("Idle", "idolanimtion"), ("Run", "runcycle"), ("Jump", "rigjump")):
        clip = next(obj for obj in imported if re.sub(r"[^a-z0-9]", "", obj.get_name().lower()).endswith(pattern))
        if not ASSETS.rename_loaded_asset(clip, clips[kind]):
            raise RuntimeError(f"Could not name Rat {kind}")
        set_props(clip, enable_root_motion=False, force_root_lock=True)
        selected[kind] = clip
    if mesh.get_name() != "SK_Rat" and not ASSETS.rename_loaded_asset(mesh, mesh_path):
        raise RuntimeError("Could not name Rat mesh")
    material = create_owned(folder, "M_Rat", unreal.Material, unreal.MaterialFactoryNew())
    edit = unreal.MaterialEditingLibrary
    properties = (("BaseColor", unreal.MaterialProperty.MP_BASE_COLOR), ("Normal", unreal.MaterialProperty.MP_NORMAL),
                  ("Roughness", unreal.MaterialProperty.MP_ROUGHNESS))
    for index, (kind, prop) in enumerate(properties):
        texture_task = set_props(unreal.AssetImportTask(), filename=str(staging / f"T_Rat_{kind}.png"),
                                 destination_path=folder, automated=True, save=False, replace_existing=False)
        TOOLS.import_asset_tasks([texture_task])
        texture = next(obj for obj in texture_task.get_objects() if isinstance(obj, unreal.Texture2D))
        if kind != "BaseColor":
            texture.set_editor_property("srgb", False)
        if kind == "Normal":
            texture.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        expression = edit.create_material_expression(material, unreal.MaterialExpressionTextureSample, -280, 200 * index)
        expression.set_editor_property("texture", texture)
        if kind == "Normal":
            expression.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
        elif kind == "Roughness":
            expression.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR)
        edit.connect_material_property(expression, "R" if kind == "Roughness" else "RGB", prop)
        ASSETS.set_metadata_tag(texture, "JYUOwner", OWNER)
        save(texture)
    edit.recompile_material(material)
    slots = mesh.get_editor_property("materials")
    for index, slot in enumerate(slots):
        slot.set_editor_property("material_interface", material)
        slots[index] = slot
    mesh.set_editor_property("materials", slots)
    for asset in [material, mesh, mesh.get_editor_property("skeleton"), mesh.get_editor_property("physics_asset"), *selected.values()]:
        if asset:
            ASSETS.set_metadata_tag(asset, "JYUOwner", OWNER)
            save(asset)
    return mesh, selected


def bone_transform(pose, name, space=WORLD_SPACE):
    return POSE.get_bone_pose(pose, name, space)


def rig_basis(mesh):
    pose = POSE.get_reference_pose(mesh.get_editor_property("skeleton"))
    bones = [str(name) for name in POSE.get_bone_names(pose)]
    pelvis = next(name for name in bones if name.lower().endswith("pelvis"))
    head = next(name for name in bones if name.lower().endswith("head"))
    neck = next(name for name in bones if name.lower().endswith("neck"))
    direction = bone_transform(pose, head).translation - bone_transform(pose, pelvis).translation
    yaw = math.degrees(math.atan2(direction.y, direction.x))
    forward = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.)
    return pose, bones, pelvis, neck, yaw, forward


def bake_pose(kind, mesh, label, frames, bone, sample, base_pose=None):
    folder = f"{ROOT}/{kind}"
    name = f"ANIM_{kind}_{label}"
    path = f"{folder}/{name}"
    if base_pose is None and ASSETS.does_asset_exist(path):
        return require(path)
    factory = set_props(unreal.AnimSequenceFactory(), target_skeleton=mesh.get_editor_property("skeleton"),
                        preview_skeletal_mesh=mesh)
    clip = create_owned(folder, name, unreal.AnimSequence, factory)
    controller = clip.get_editor_property("controller")
    controller.open_bracket("Bake fauna presentation pose", False)
    try:
        if base_pose is not None:
            controller.remove_all_bone_tracks(False)
        controller.set_frame_rate(unreal.FrameRate(30, 1), False)
        controller.set_number_of_frames(unreal.FrameNumber(frames), False)
        if base_pose is not None:
            for name in POSE.get_bone_names(base_pose):
                if str(name) == bone:
                    continue
                transform = bone_transform(base_pose, name, LOCAL_SPACE)
                if not controller.add_bone_curve(name, False) or not controller.set_bone_track_keys(
                    name, [transform.translation] * (frames + 1), [transform.rotation] * (frames + 1),
                    [transform.scale3d] * (frames + 1), False,
                ):
                    raise RuntimeError(f"Base pose track rejected {kind}/{name}")
        keys = [sample(frame / frames) for frame in range(frames + 1)]
        translations, rotations, scales = (list(track) for track in zip(*keys))
        if not controller.add_bone_curve(bone, False) or not controller.set_bone_track_keys(
            bone, translations, rotations, scales, False
        ):
            raise RuntimeError(f"Pose track rejected {kind}/{bone}")
    finally:
        controller.close_bracket(False)
    save(clip)
    return clip


def feed_pose(kind, mesh, idle=None):
    pose, bones, _, joint, _, forward = rig_basis(mesh)
    base_pose = POSE.get_anim_pose_at_time(idle, 0., unreal.AnimPoseEvaluationOptions()) if idle else None
    if base_pose is not None:
        pose = base_pose
    if kind == "Buffalo":
        # The imported neck also carries the forequarters. Rotate downstream of that branch.
        joint = next(name for name in bones if name.lower().endswith("head"))
    rig = unreal.SkeletalMeshComponent()
    rig.set_skeletal_mesh_asset(mesh)
    parent = bone_transform(pose, str(rig.get_parent_bone(joint)))
    base = bone_transform(pose, joint)
    local = bone_transform(pose, joint, LOCAL_SPACE)
    lib = unreal.MathLibrary
    inverse = lib.quat_inversed(parent.rotation)
    right = unreal.Vector(-forward.y, forward.x, 0.)

    def sample(t):
        angle = (35. if kind == "Buffalo" else 24.) + 3. * math.cos(math.tau * t)
        tilt = lib.quat_make_from_rotation_vector(right * angle)
        return local.translation, lib.multiply_quat_quat(inverse, lib.multiply_quat_quat(tilt, base.rotation)), local.scale3d

    return bake_pose(kind, mesh, "Feed", 33, joint, sample, base_pose)


def leopard_death(mesh):
    pose, bones, pelvis, _, _, forward = rig_basis(mesh)
    body = next(bone for bone in bones if bone.lower() == "bip01")
    rig = unreal.SkeletalMeshComponent()
    rig.set_skeletal_mesh_asset(mesh)
    parent = bone_transform(pose, str(rig.get_parent_bone(body)))
    base = bone_transform(pose, body)
    local = bone_transform(pose, body, LOCAL_SPACE)
    pivot = bone_transform(pose, pelvis).translation
    contacts = [bone_transform(pose, foot).translation for foot, _ in bone_legs("Leopard")]
    head = next(bone for bone in bones if bone.lower().endswith("head"))
    contacts.extend((pivot, bone_transform(pose, head).translation))
    floor = min(contact.z for contact in contacts)
    lib = unreal.MathLibrary
    inverse = lib.quat_inversed(parent.rotation)

    def sample(t):
        turn = lib.quat_make_from_rotation_vector(forward * (85. * t * t * (3. - 2. * t)))
        points = [pivot + lib.quat_rotate_vector(turn, point - pivot) for point in contacts]
        lift = floor - min(point.z for point in points)
        position = pivot + lib.quat_rotate_vector(turn, base.translation - pivot) + unreal.Vector(0., 0., lift)
        return (lib.inverse_transform_location(parent, position),
                lib.multiply_quat_quat(inverse, lib.multiply_quat_quat(turn, base.rotation)), local.scale3d)

    return bake_pose("Leopard", mesh, "FallSide", 23, body, sample)


def buffalo_gait(mesh, speed, name, cycle, stance, lift, phases):
    """Bake a four-beat walk or diagonal trot with planted stance travel."""
    folder = f"{ROOT}/Buffalo"
    path = f"{folder}/{name}"
    if ASSETS.does_asset_exist(path):
        return require(path)
    factory = set_props(unreal.AnimSequenceFactory(), target_skeleton=mesh.get_editor_property("skeleton"),
                        preview_skeletal_mesh=mesh)
    sequence = create_owned(folder, name, unreal.AnimSequence, factory)
    pose, _, _, _, _, forward = rig_basis(mesh)
    rig = unreal.SkeletalMeshComponent()
    rig.set_skeletal_mesh_asset(mesh)
    math_lib = unreal.MathLibrary
    controller = sequence.get_editor_property("controller")
    frames = round(cycle * 30)
    controller.open_bracket("Bake buffalo gait", False)
    try:
        controller.set_frame_rate(unreal.FrameRate(30, 1), False)
        controller.set_number_of_frames(unreal.FrameNumber(frames), False)
        for index, (_, end) in enumerate(bone_legs("Buffalo")):
            joint = str(rig.get_parent_bone(end))
            root = str(rig.get_parent_bone(joint))
            parent = str(rig.get_parent_bone(root))
            chain = (root, joint, end)
            base = [bone_transform(pose, bone) for bone in chain]
            locals_ = [bone_transform(pose, bone, LOCAL_SPACE) for bone in chain]
            hip, knee, ankle = [x.translation for x in base]
            first = (knee - hip).length()
            second = (ankle - knee).length()
            parent_inverse = math_lib.quat_inversed(bone_transform(pose, parent).rotation)
            rotations = [[], [], []]
            for frame in range(frames + 1):
                phase = (frame % frames / frames + phases[index]) % 1.
                stride = speed * cycle * stance
                if phase < stance:
                    distance = stride * (.5 - phase / stance)
                    height = 0.
                else:
                    alpha = (phase - stance) / (1. - stance)
                    distance = stride * (-.5 + alpha * alpha * (3. - 2. * alpha))
                    height = lift * math.sin(math.pi * alpha)
                target = ankle + forward * distance + unreal.Vector(0., 0., height)
                direction = (target - hip).normal()
                length = min(max((target - hip).length(), abs(first - second) + .1), first + second - .1)
                bend = ((knee - hip) - direction * (knee - hip).dot(direction)).normal()
                projection = (first * first + length * length - second * second) / (2. * length)
                new_knee = hip + direction * projection + bend * math.sqrt(max(0., first * first - projection * projection))
                new_ankle = hip + direction * length
                thigh = math_lib.multiply_quat_quat(math_lib.quat_find_between_vectors(knee - hip, new_knee - hip), base[0].rotation)
                shin = math_lib.multiply_quat_quat(math_lib.quat_find_between_vectors(ankle - knee, new_ankle - new_knee), base[1].rotation)
                for row, rotation in zip(rotations, (
                    math_lib.multiply_quat_quat(parent_inverse, thigh),
                    math_lib.multiply_quat_quat(math_lib.quat_inversed(thigh), shin),
                    math_lib.multiply_quat_quat(math_lib.quat_inversed(shin), base[2].rotation),
                )):
                    row.append(rotation)
            for bone, transform, values in zip(chain, locals_, rotations):
                if not controller.add_bone_curve(bone, False) or not controller.set_bone_track_keys(
                    bone, [transform.translation] * (frames + 1), values, [transform.scale3d] * (frames + 1), False
                ):
                    raise RuntimeError(f"Gait track rejected {bone}")
    finally:
        controller.close_bracket(False)
    save(sequence)
    return sequence


def contact_clip(kind, source, legs):
    lib = unreal.AnimationLibrary
    folder = f"{ROOT}/{kind}/FootContacts"
    path = source.get_path_name()
    clip = source if path.startswith(f"{ROOT}/{kind}/") else duplicate_owned(path, f"{folder}/{source.get_name()}_Contacts")
    track = "EcoFaunaFootsteps"
    length = clip.get_play_length()
    # Sample the raw rig, independently of runtime IK. Mark entry into the low part
    # of each foot's cycle, on the downward stroke, including loop wrap.
    count = 48
    options = unreal.AnimPoseEvaluationOptions()
    frames = [POSE.get_anim_pose_at_time(clip, length * index / count, options) for index in range(count)]
    marks = []
    for bone, _ in legs:
        values = [bone_transform(frame, bone).translation.z for frame in frames]
        floor, top = min(values), max(values)
        if top - floor < .05:
            continue
        threshold = floor + .20 * (top - floor)
        crossing = [index for index in range(count)
                    if values[index - 1] > threshold >= values[index] and values[(index + 1) % count] < threshold]
        if crossing:
            index = max(crossing, key=lambda i: values[i - 1] - values[i])
            marks.append((bone, max(.005, length * index / count)))
    if track in [str(name) for name in lib.get_animation_notify_track_names(clip)]:
        lib.remove_animation_notify_track(clip, track)
    if kind == "Buffalo":
        # The generated walk and diagonal trot have exact stance phases.
        phases = (.25, .0, .75, .50) if clip.get_name().endswith("_Walk") else (.0, .50, .50, .0)
        marks = [(bone, max(.005, length * (-phase % 1.))) for (bone, _), phase in zip(legs, phases)]
    if marks:
        lib.add_animation_notify_track(clip, track, unreal.LinearColor(.2, .8, .3, 1.))
        for bone, when in marks:
            notify = lib.add_animation_notify_event(clip, track, when, unreal.EcoAnimNotifyFootstep)
            if not notify:
                raise RuntimeError(f"Could not author {kind} foot contact {bone}")
            notify.set_editor_property("foot_bone", bone)
    save(clip)
    unreal.log(f"ECO_FAUNA_FOOT_MARKERS {kind} {clip.get_name()} {marks}")
    return clip, bool(marks)


def build_representation(kind, mesh, clips, keys, speeds, b_turning=False):
    folder = f"{ROOT}/{kind}"
    idle, walk, run, look, eat, rest, death, attack = (clips[key] for key in keys)
    skeleton = mesh.get_editor_property("skeleton")

    if kind == "Rat":
        reference, names, legs, yaw, forward, points = rat_rig(mesh)
        bones = list(names.values())
        pelvis, neck = names["torso"], names["defspine010"]
    else:
        reference, bones, pelvis, neck, yaw, forward = rig_basis(mesh)
        if kind == "Buffalo":
            neck = next(name for name in bones if name.lower().endswith("head"))
        legs = bone_legs(kind)
    if any(bone not in bones for leg in legs for bone in leg):
        raise RuntimeError(f"Missing contact chain in {kind}: {legs}")
    movement = [walk, run]
    if b_turning:
        movement.extend(clips[key] for key in ("WalkTurnL", "WalkTurnR", "RunTurnL", "RunTurnR"))
    contacts = [contact_clip(kind, clip, legs) for clip in movement]
    authored = [clip for clip, _ in contacts]
    if b_turning:
        factory = set_props(unreal.BlendSpaceFactoryNew(), target_skeleton=skeleton)
        blend = create_owned(folder, "BS_" + kind, unreal.BlendSpace, factory)
        valid = unreal.EcoCreatureBlendSpaceLibrary.configure_turning(blend, idle, authored[0], authored[2], authored[3],
            authored[1], authored[4], authored[5], *speeds)
    else:
        factory = set_props(unreal.BlendSpaceFactory1D(), target_skeleton=skeleton)
        blend = create_owned(folder, "BS_" + kind, unreal.BlendSpace1D, factory)
        valid = unreal.EcoCreatureBlendSpaceLibrary.configure_locomotion(blend, idle, *authored, *speeds)
    if not valid:
        raise RuntimeError(f"Invalid locomotion set {kind}")
    heights = {contact: [] for contact, _ in legs}
    for index in range(31):
        sample = POSE.get_anim_pose_at_time(walk, walk.get_play_length() * index / 30., unreal.AnimPoseEvaluationOptions())
        for contact in heights:
            heights[contact].append(bone_transform(sample, contact).translation.z)
    factory = set_props(unreal.DataAssetFactory(), data_asset_class=unreal.EcoCreatureAnimationProfile)
    profile = create_owned(folder, f"DA_{kind}_Animation", unreal.EcoCreatureAnimationProfile, factory)
    pose_assets = [idle, eat, look, rest, clips.get("SniffleforFood", look), rest, attack, rest, death]
    if kind == "Crow":
        pose_assets += [clips["TakeOff"], clips["Fly"], clips["Landing"]]
    poses = [set_props(unreal.EcoCreaturePoseClip(), clip=clip, loop=index not in (6, 8, 9, 11),
                        blend_seconds=.16 if index in (6, 8, 9, 11) else .25)
             for index, clip in enumerate(pose_assets)]
    set_props(profile, locomotion=blend, poses=poses, enable_ground_ik=True,
              foot_bones=[foot for foot, _ in legs], ik_end_bones=[end for _, end in legs], body_bone=pelvis,
              turn_head_bone=neck, stationary_speed=min(25., speeds[0] * .25),
              contact_heights=[max(0., min(50., min(samples))) for samples in heights.values()],
              max_foot_correction_cm={"Rat": 2., "Crow": 5., "Buffalo": 28., "Leopard": 28.}.get(kind, 12.))
    save(profile)
    factory = set_props(unreal.AnimBlueprintFactory(), parent_class=unreal.EcoCreatureAnimInstance, target_skeleton=skeleton)
    abp = create_owned(folder, "ABP_" + kind, unreal.AnimBlueprint, factory)
    if not unreal.EcoCreatureAnimationBuilder.build_pose_graph(abp, profile):
        raise RuntimeError(f"Invalid animation graph {kind}")
    save(abp)
    factory = set_props(unreal.BlueprintFactory(), parent_class=unreal.EcoCreatureRepresentationActor)
    bp = create_owned(folder, "BP_" + kind, unreal.Blueprint, factory)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    mesh_scale = .6 if kind == "Leopard" else 1.
    mesh_offset = unreal.Vector()
    if kind == "Rat":
        length = ((points[0] + points[1] - points[2] - points[3]) * .5).length()
        mesh_scale = 15. / max(1., length)
        center = sum(points[1:], points[0]) * .25
        angle = math.radians(-yaw)
        mesh_offset = unreal.Vector(-mesh_scale * (math.cos(angle) * center.x - math.sin(angle) * center.y),
                                    -mesh_scale * (math.sin(angle) * center.x + math.cos(angle) * center.y),
                                    -mesh_scale * min(point.z for point in points))
    if kind == "Leopard":
        # The FBX rig and clips carry the source scene's XY placement on the pelvis branch.
        pivot = bone_transform(reference, pelvis).translation
        angle = math.radians(-yaw)
        mesh_offset = unreal.Vector(
            -mesh_scale * (math.cos(angle) * pivot.x - math.sin(angle) * pivot.y),
            -mesh_scale * (math.sin(angle) * pivot.x + math.cos(angle) * pivot.y), 0.)
    set_props(unreal.get_default_object(generated(bp)), visual_species_id=kind, visual_mesh=mesh, death_animation=death,
              idle_speed=8., run_speed=speeds[1] * .8, mesh_offset=mesh_offset, visual_mesh_scale=mesh_scale,
              soften_abrupt_facing=True)
    if kind == "Crow":
        configure_crow_orientation(bp)
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_representation(bp, blend, unreal.Rotator(yaw=-yaw), forward):
        raise RuntimeError(f"Representation facing setup failed {kind}")
    if not unreal.EcoCreatureAnimationBuilder.configure_behavior_representation(bp, profile, generated(abp)):
        raise RuntimeError(f"Representation graph setup failed {kind}")
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_footstep_notifies(bp, all(found for _, found in contacts)):
        raise RuntimeError(f"Footstep notify configuration failed {kind}")
    save(blend)
    save(bp)
    unreal.log(f"ECO_FAUNA_ASSET_READY {kind} yaw={yaw:.2f} contact={list(heights)}")
    return generated(bp)


def configure_species():
    keys = {
        "Pig": ("IdleBreathe", "Walk", "Run", "IdleLookAround", "Chew", "Rest", "Death", "IdleLookAround"),
        "Fox": ("IdleBreathe", "Walk", "Run", "IdleLookAround", "Feed", "Sleeping", "Death", "Bite"),
        "Crow": ("IdleLookAround", "Walk", "Hop", "IdleScratchWing", "EatSomething", "IdleScratchWing", "DeathGrounded", "IdleLookAround"),
        "Leopard": ("Idle1", "Walk", "Run", "Idle2", "Feed", "Idle2", "FallSide", "Atk1"),
        "Buffalo": ("Idle", "Walk", "Trot", "Idle", "Feed", "Lying", "Die", "Turnleft"),
        "Rat": ("Idle", "Walk", "Run", "Idle", "Idle", "Idle", "FallSide", "Idle"),
    }
    tuning = {
        "Pig": (130., 315., 30., 75., 120., .27, 14),
        "Fox": (130., 420., 23., 7., 135., .18, 8),
        "Crow": (70., 145., 15., .55, 105., .16, 16),
        "Leopard": (150., 530., 31., 60., 170., .2, 6),
        "Buffalo": (100., 240., 65., 450., 220., .32, 12),
        "Rat": (55., 220., 3.5, .25, 50., .08, 24),
    }
    acceleration = {"Pig": 680., "Fox": 1100., "Crow": 430., "Leopard": 1250., "Buffalo": 420., "Rat": 850.}
    activity = {
        "Pig": (.72, .86, .75), "Fox": (.53, .94, .85), "Crow": (.94, .12, .42),
        "Leopard": (.58, .90, .88), "Buffalo": (.94, .62, .67), "Rat": (.48, .97, .80),
    }
    species = []
    for kind, options in tuning.items():
        walk, run, radius, mass, maturity, food, limit = options
        if kind == "Rat":
            mesh, clips = import_rat()
            walk_clip = duplicate_owned(clips["Run"].get_path_name(), f"{ROOT}/Rat/ANIM_Rat_SlowGait")
            set_props(walk_clip, rate_scale=.45)
            save(walk_clip)
            clips["Walk"] = walk_clip
            clips["FallSide"] = rat_death(mesh, clips["Idle"])
        elif kind in PACK_CLIPS:
            root = f"/Game/AnimalVarietyPack/{kind}"
            mesh = require(f"{root}/Meshes/SK_{kind}")
            clips = {key: require(f"{root}/Animations/ANIM_{kind}_{key}") for key in PACK_CLIPS[kind]}
        else:
            mesh, clips = import_fab(kind)
            if kind == "Buffalo":
                clips["Walk"] = buffalo_gait(mesh, walk, "ANIM_Buffalo_Walk", 1.13, .68, 13., (.25, .0, .75, .50))
                clips["Trot"] = buffalo_gait(mesh, run, "ANIM_Buffalo_Trot", .65, .58, 18., (.0, .50, .50, .0))
        if kind in ("Fox", "Leopard", "Buffalo"):
            clips["Feed"] = feed_pose(kind, mesh, clips["Idle"] if kind == "Buffalo" else None)
        if kind == "Leopard":
            clips["FallSide"] = leopard_death(mesh)
        representation = build_representation(kind, mesh, clips, keys[kind], (walk, run), kind in ("Pig", "Fox"))
        diet = unreal.EcoFaunaDiet.CARNIVORE if kind in ("Fox", "Leopard") else (
            unreal.EcoFaunaDiet.OMNIVORE if kind in ("Pig", "Crow", "Rat") else unreal.EcoFaunaDiet.HERBIVORE)
        rules = []
        if kind == "Fox":
            rules.append(set_props(unreal.EcoFaunaPreyRule(), species_id="Crow", max_prey_mass_ratio=.45))
            rules.append(set_props(unreal.EcoFaunaPreyRule(), species_id="Rat", max_prey_mass_ratio=.4, preference=1.9))
        if kind == "Leopard":
            rules.append(set_props(unreal.EcoFaunaPreyRule(), species_id="Pig", max_prey_mass_ratio=1.6))
            rules.append(set_props(unreal.EcoFaunaPreyRule(), species_id="Rat", max_prey_mass_ratio=.1,
                                   preference=.14, max_pursuit_start=320.))
            rules.append(set_props(unreal.EcoFaunaPreyRule(), species_id="Buffalo", max_prey_mass_ratio=1.8,
                                   max_healthy_maturity=.35, max_injured_maturity=.55, guard_radius=400., preference=.45))
        entry = set_props(unreal.EcoFaunaSpecies(), species_id=kind, visual_class=representation, diet=diet,
                          prey_rules=rules, adult_mass=mass, body_radius=radius, walk_speed=walk, run_speed=run,
                          maturity_seconds=maturity, food_per_meal=food, regional_limit=limit,
                          attack_reach=75. if kind == "Fox" else 125., ground_acceleration=acceleration[kind])
        day, night, vision = activity[kind]
        set_props(entry, day_activity=day, night_activity=night, night_vision=vision)
        if kind == "Pig":
            set_props(entry, rooting_seconds=1.4, carrion_energy_per_meal=4., sprint_drain=.09, wade_depth=10., defense_damage=18.,
                      offspring_guard_range=400., allow_second_parent_guard=True)
        if kind == "Fox":
            set_props(entry, sight_range=1350., sight_half_angle=100., carrion_energy_per_meal=7., carrion_hunger_fraction=.86,
                      sprint_drain=.095, maintenance=.26, attack_windup=.22, attack_recovery=2.8, scent_range=1000.)
        if kind == "Leopard":
            set_props(entry, sight_range=1750., sight_half_angle=83., stalk_range=1250., sprint_drain=.16,
                      carrion_energy_per_meal=9., carrion_hunger_fraction=.78, attack_windup=.42, scent_range=750.)
        if kind == "Buffalo":
            set_props(entry, caregiver_follow_range=850., eye_height=120., sweep_height=90., wade_depth=35.,
                      sprint_drain=.14, feeding_places=4, carrion_lifetime=36., defense_damage=32., offspring_guard_range=650.)
        if kind == "Rat":
            set_props(entry, eye_height=5., sweep_height=5., step_height=4., sight_range=800., wade_depth=1.,
                      sprint_drain=.17, fatigue_recovery=.21, maintenance=.14, adult_carrion_energy=13.,
                      death_settle_seconds=.85, carrion_lifetime=12., feeding_places=1,
                      gestation=15., birth_recovery=55.)
        if kind == "Crow":
            set_props(entry, locomotion=unreal.EcoFaunaLocomotion.FLIGHT, sight_range=2000.,
                      carrion_energy_per_meal=3.5, carrion_hunger_fraction=.9, flight_cruise_height=1200.,
                      flight_ceiling=3000., flight_speed=650., sprint_drain=.08, eye_height=23.,
                      adult_carrion_energy=19., feeding_places=1)
        species.append(entry)
    return species


def native_representation(kind):
    """Use the native species' existing clips and IK with the same neck anticipation layer."""
    folder = f"{ROOT}/{kind}"
    profile = duplicate_owned(f"/Game/JYU/Animation/DA_JYU_{kind}_Animation", f"{folder}/DA_{kind}_Animation")
    bp = duplicate_owned(f"/Game/JYU/Creatures/BP_JYU_{kind}", f"{folder}/BP_{kind}")
    mesh = unreal.get_default_object(generated(bp)).get_editor_property("visual_mesh")
    _, _, _, neck, _, _ = rig_basis(mesh)
    set_props(profile, turn_head_bone=neck)
    original_blend = profile.get_editor_property("locomotion")
    blend = duplicate_owned(original_blend.get_path_name(), f"{folder}/BS_{kind}")
    set_props(profile, locomotion=blend)
    save(profile)
    factory = set_props(unreal.AnimBlueprintFactory(), parent_class=unreal.EcoCreatureAnimInstance,
                        target_skeleton=mesh.get_editor_property("skeleton"))
    abp = create_owned(folder, "ABP_" + kind, unreal.AnimBlueprint, factory)
    if not unreal.EcoCreatureAnimationBuilder.build_pose_graph(abp, profile):
        raise RuntimeError(f"Invalid native animation graph {kind}")
    save(abp)
    if not unreal.EcoCreatureAnimationBuilder.configure_behavior_representation(bp, profile, generated(abp)):
        raise RuntimeError(f"Native representation graph setup failed {kind}")
    defaults = unreal.get_default_object(generated(bp))
    set_props(defaults, soften_abrupt_facing=True)
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_representation(bp, blend,
            defaults.get_editor_property("mesh_rotation"), defaults.get_editor_property("mesh_forward_axis")):
        raise RuntimeError(f"Native blend setup failed {kind}")
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_footstep_notifies(bp, True):
        raise RuntimeError(f"Native footstep setup failed {kind}")
    save(blend)
    save(bp)
    return generated(bp)


def make_map(species):
    native_deer, native_wolf = native_representation("Deer"), native_representation("Wolf")
    editor = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if ASSETS.does_asset_exist(MAP):
        if not levels.load_level(MAP) or ASSETS.get_metadata_tag(editor.get_editor_world(), "JYUOwner") != OWNER:
            raise RuntimeError(f"Unexpected existing map {MAP}")
        world = editor.get_editor_world()
        runtime = next(actor for actor in ACTORS.get_all_level_actors() if isinstance(actor, unreal.EcoCreatureIntegrationSpawner))
        runtime.set_editor_property("fauna_species", species)
    else:
        unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        world = editor.get_editor_world()
        runtime = ACTORS.spawn_actor_from_class(unreal.EcoCreatureIntegrationSpawner, unreal.Vector())
        set_props(runtime, use_v3_policy=True, enable_ecosystem_life=True, enable_waves=False, v3_deer_per_region=48,
                  global_population_limit=96, host_visual_distance=20000., client_visual_distance=8000., fauna_species=species,
                  herbivore_config=require("/Game/JYU/Config/EC_JYU_V3_Deer"), wolf_config=require("/Game/JYU/Config/EC_JYU_V3_Wolf"))
        floor = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(0., 0., -50.))
        floor.static_mesh_component.set_static_mesh(require("/Engine/BasicShapes/Cube"))
        floor.static_mesh_component.set_collision_profile_name("BlockAll")
        floor.set_actor_scale3d(unreal.Vector(240., 240., 1.))
        for name, location, angle in (
            ("Slope8", (-1450., 500., 35.), 8.), ("Slope12", (1450., 500., 43.), 12.),
        ):
            ramp = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*location), unreal.Rotator(pitch=angle))
            ramp.set_actor_label(name)
            ramp.static_mesh_component.set_static_mesh(require("/Engine/BasicShapes/Cube"))
            ramp.static_mesh_component.set_collision_profile_name("BlockAll")
            ramp.set_actor_scale3d(unreal.Vector(6., 5., .3))
        region = ACTORS.spawn_actor_from_class(unreal.EcologyRegion, unreal.Vector())
        set_props(region, region_id="FaunaMeadow", initial_food_amount=1800., food_capacity=3600., food_regeneration_rate=8.)
        region.get_editor_property("region_bounds").set_box_extent(unreal.Vector(11800., 11800., 3500.), False)
        group = set_props(unreal.EcoCreatureSpawnGroup(), region_id="FaunaMeadow", herbivores=48, wolves=2)
        group.set_editor_property("herbivore_spawn_points", [unreal.Vector(-5000. + 260. * (i % 8), 3400. + 300. * (i // 8), 0.) for i in range(48)])
        group.set_editor_property("wolf_spawn_points", [unreal.Vector(-4700., 6100., 0.), unreal.Vector(-4280., 6100., 0.)])
        positions = (("Pig", -1100., 700., 4), ("Fox", -500., -300., 2), ("Crow", 500., 100., 6),
                     ("Leopard", -1800., 1600., 2), ("Buffalo", 1300., 1100., 4))
        placements = [set_props(unreal.EcoFaunaPlacement(), species_id=kind,
                                spawn_points=[unreal.Vector(x + 260. * (i % 3), y + 290. * (i // 3), 0.) for i in range(count)])
                      for kind, x, y, count in positions]
        set_props(group, fauna=placements)
        set_props(runtime, groups=[group])
        ACTORS.spawn_actor_from_class(unreal.PlayerStart, unreal.Vector(0., -2000., 160.), unreal.Rotator(yaw=90.))
        ACTORS.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0., 0., 2000.), unreal.Rotator(pitch=-42., yaw=-30.))
        ACTORS.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector())
        ACTORS.spawn_actor_from_class(unreal.SkyLight, unreal.Vector())
    world.get_world_settings().set_editor_property("default_game_mode", generated(require("/Game/JWJ/Gameplay/BP_EcoGameMode_Common")))
    set_props(runtime, herbivore_actor_class=native_deer, wolf_actor_class=native_wolf, v3_deer_per_region=48,
              enable_player_combat=True, global_population_limit=112)
    groups = runtime.get_editor_property("groups")
    for index, group in enumerate(groups):
        schedule = set_props(group.get_editor_property("schedule"), region_population_limit=112)
        group.set_editor_property("schedule", schedule)
        placements = list(group.get_editor_property("fauna"))
        if not any(str(entry.get_editor_property("species_id")) == "Rat" for entry in placements):
            rat_sites = [unreal.Vector(x + 145. * (i % 2), y + 125. * (i // 2), 0.)
                         for x, y in ((-850., -550.), (480., -350.), (-1750., 1550.))
                         for i in range(4)]
            placements.append(set_props(unreal.EcoFaunaPlacement(), species_id="Rat", spawn_points=rat_sites))
            group.set_editor_property("fauna", placements)
        groups[index] = group
    runtime.set_editor_property("groups", groups)
    runpy.run_path(str(Path(__file__).with_name("author_jyu_fauna_balance.py")))["configure"](world, runtime)
    runpy.run_path(str(Path(__file__).with_name("author_jyu_fauna_footsteps.py")))["configure"](world, runtime)
    for actor in ACTORS.get_all_level_actors():
        if isinstance(actor, unreal.DirectionalLight):
            actor.get_component_by_class(unreal.DirectionalLightComponent).set_mobility(unreal.ComponentMobility.MOVABLE)
        if isinstance(actor, unreal.StaticMeshActor):
            mesh = actor.static_mesh_component.get_editor_property("static_mesh")
            if mesh and mesh.get_path_name() == "/Engine/BasicShapes/Cube.Cube":
                tags = list(actor.get_editor_property("tags"))
                if "Eco.VegetationGround" not in [str(tag) for tag in tags]:
                    actor.set_editor_property("tags", [*tags, "Eco.VegetationGround"])
    ASSETS.set_metadata_tag(world, "JYUOwner", OWNER)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError("Could not save fauna map")
    unreal.log("ECO_FAUNA_MAP_READY " + MAP)


if __name__ == "__main__":
    if "-EcoFaunaCrowOrientation" in unreal.SystemLibrary.get_command_line():
        crow = require(ROOT + "/Crow/BP_Crow")
        configure_crow_orientation(crow)
        save(crow)
        unreal.log("ECO_FAUNA_CROW_ORIENTATION_READY")
    else:
        editor_world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        unreal.SystemLibrary.execute_console_command(editor_world, "Interchange.FeatureFlags.Import.FBX 0")
        make_map(configure_species())

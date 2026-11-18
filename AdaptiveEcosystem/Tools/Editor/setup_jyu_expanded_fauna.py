"""Author the expanded species and a local copy of the existing fauna fixture."""

import math
from pathlib import Path
import runpy

import unreal


HERE = Path(__file__).parent
IMPORT = runpy.run_path(str(HERE / "import_jyu_expanded_fauna.py"))
BASE = runpy.run_path(str(HERE / "setup_jyu_fauna.py"))
ROOT, OWNER = IMPORT["ROOT"], IMPORT["OWNER"]
BASE["create_owned"].__globals__.update(ROOT=ROOT, OWNER=OWNER)
set_props, save, generated = (BASE[key] for key in ("set_props", "save", "generated"))
create_owned = BASE["create_owned"]
ASSETS, ACTORS, POSE = (BASE[key] for key in ("ASSETS", "ACTORS", "POSE"))
MAP = "/Game/JYU/Maps/LV_JYU_ExpandedFauna"
SOURCE_MAP = "/Game/JYU/Maps/LV_JYU_Fauna"
LOCAL = unreal.AnimPoseSpaces.LOCAL
WORLD = unreal.AnimPoseSpaces.WORLD

# Radius in cm, mass in kg, walk and run in cm/s. Values are for this fixture.
TUNING = {
    "Bighorn": (29., 70., 135., 570.),
    "Jackrabbit": (10., 3., 90., 430.),
    "Horse": (42., 400., 150., 700.),
    "Mink": (9., 1., 75., 280.),
    "GoldenEagle": (24., 5., 55., 145.),
    "AriakeCatfish": (4., .14, 42., 95.),
    "CommonCarp": (7., .9, 52., 125.),
    "UnidentifiedFish": (4., .05, 36., 82.),
}

SOURCE_POSES = {
    "Bighorn": ("Stand_Breathing_01", "Walk", "Run", "Stand_Idle_02", "Stand_Eating_01",
                "Lying_Breathing_01", "Death_Stand_R01"),
    "Jackrabbit": ("jackrabbit_idle_05", "jackrabbit_walk_fwd_01", "jackrabbit_sprint_fwd_01",
                   "jackrabbit_idle_04", "jackrabbit_idle_eating", "jackrabbit_idle_static_pose_01",
                   "jackrabbit_dead_reaction_01"),
    "Mink": ("idle_01", "startwalk_fwd_01", "startsprint_fwd_01", "idle_alerted_look_01",
             "idle_eat_01", "rest_idle_01", "dead_carry_pose_01"),
}

TURN_CLIPS = {
    "Bighorn": ("WalkL", "WalkR", "RunL", "RunR"),
    "Jackrabbit": ("walk_fwd_bank_lft", "walk_fwd_bank_rgt", "sprint_fwd_bank_lft", "sprint_fwd_bank_rgt"),
}


def find_clip(clips, suffix):
    matches = [clip for clip in clips if clip.get_name().endswith("_" + suffix)]
    if matches:
        shortest = min(len(clip.get_name()) for clip in matches)
        matches = [clip for clip in matches if len(clip.get_name()) == shortest]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one clip ending with {suffix!r}, got {len(matches)}")
    return matches[0]


def rename_eagle_source():
    folder = f"{ROOT}/GoldenEagle/Imported"
    for suffix, new in (("_Anim", "ANIM_GoldenEagle_SourceTake"), ("_PhysicsAsset", "PHYS_GoldenEagle"),
                        ("_Skeleton", "SKEL_GoldenEagle"), ("", "SK_GoldenEagle")):
        original = f"{folder}/FALCON_Rooted{suffix}"
        destination = f"{folder}/{new}"
        if not ASSETS.does_asset_exist(destination):
            BASE["require"](original)
            if not ASSETS.rename_asset(original, destination):
                raise RuntimeError(f"Could not rename {original}")
            save(BASE["require"](destination))
    mesh = BASE["require"](f"{folder}/SK_GoldenEagle")
    skeleton = mesh.get_editor_property("skeleton")
    if not skeleton:
        raise RuntimeError("GoldenEagle mesh has no imported skeleton")
    take_path = f"{folder}/ANIM_GoldenEagle_SourceTake"
    take = BASE["require"](take_path)
    if take.get_editor_property("skeleton") != skeleton:
        # Reimport cannot recover an existing animation whose target skeleton is missing.
        # Only this script's own failed output is replaceable.
        if ASSETS.get_metadata_tag(take, "JYUOwner") != OWNER:
            raise RuntimeError(f"Unexpected owner for {take_path}")
        recovery_path = f"{folder}/ANIM_GoldenEagle_Recovery"
        staging = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
        source = staging / "ExpandedFaunaImport/GoldenEagle/source/FALCON_Rooted.fbx"
        options = set_props(unreal.FbxImportUI(), automated_import_should_detect_type=False,
                            mesh_type_to_import=unreal.FBXImportType.FBXIT_ANIMATION,
                            import_mesh=False, import_animations=True, skeleton=skeleton,
                            import_materials=False, import_textures=False)
        task = set_props(unreal.AssetImportTask(), filename=str(source), destination_path=folder,
                         destination_name="ANIM_GoldenEagle_Recovery", automated=True, save=False,
                         replace_existing=False, options=options, factory=unreal.FbxFactory())
        IMPORT["TOOLS"].import_asset_tasks([task])
        repaired = next((asset for asset in task.get_objects() if isinstance(asset, unreal.AnimSequence)), None)
        if not repaired or repaired.get_editor_property("skeleton") != skeleton:
            raise RuntimeError("GoldenEagle source take did not bind to its skeleton")
        if not ASSETS.delete_asset(take_path) or not ASSETS.rename_asset(recovery_path, take_path):
            raise RuntimeError("Could not replace the owned failed GoldenEagle take")
        take = BASE["require"](take_path)
        ASSETS.set_metadata_tag(take, "JYUOwner", OWNER)
        set_props(take, enable_root_motion=False, force_root_lock=True)
        save(take)


def mesh_and_clips(kind):
    assets = IMPORT["assets_at"](f"{ROOT}/{kind}/Imported")
    meshes = {asset.get_path_name(): asset for asset in assets if isinstance(asset, unreal.SkeletalMesh)}
    if kind == "CommonCarp":
        mesh = next(item for item in meshes.values() if item.get_name() == "Object_7")
    elif len(meshes) == 1:
        mesh = next(iter(meshes.values()))
    else:
        raise RuntimeError(f"Expected one primary mesh for {kind}: {list(meshes)}")
    skeleton = mesh.get_editor_property("skeleton")
    clips = {asset.get_path_name(): asset for asset in assets if isinstance(asset, unreal.AnimSequence)
             and asset.get_editor_property("skeleton") == skeleton}
    return mesh, list(clips.values())


def sample_clip(kind, mesh, label, source, start, end, close_loop=False):
    if start < 0. or end < start or end > source.get_play_length() + .001:
        raise ValueError(f"Invalid {kind} source range {start}..{end}")
    name = f"ANIM_{kind}_{label}"
    folder = f"{ROOT}/{kind}"
    skeleton = mesh.get_editor_property("skeleton")
    factory = set_props(unreal.AnimSequenceFactory(), target_skeleton=skeleton, preview_skeletal_mesh=mesh)
    clip = create_owned(folder, name, unreal.AnimSequence, factory)
    controller = clip.get_editor_property("controller")
    frames = max(1, round((end - start) * 30))
    options = unreal.AnimPoseEvaluationOptions()
    samples = [POSE.get_anim_pose_at_time(source, start + (end - start) * index / frames, options)
               for index in range(frames + 1)]
    controller.open_bracket(f"Bake {kind} {label}", False)
    try:
        controller.remove_all_bone_tracks(False)
        controller.set_frame_rate(unreal.FrameRate(30, 1), False)
        controller.set_number_of_frames(unreal.FrameNumber(frames), False)
        for bone in POSE.get_bone_names(samples[0]):
            track = [POSE.get_bone_pose(sample, bone, LOCAL) for sample in samples]
            if close_loop:
                blend_count = max(1, min(5, frames // 4))
                for offset in range(1, blend_count + 1):
                    index = frames - blend_count + offset
                    track[index] = track[index].lerp(track[0], offset / blend_count)
            if not controller.add_bone_curve(bone, False) or not controller.set_bone_track_keys(
                    bone, [key.translation for key in track], [key.rotation for key in track],
                    [key.scale3d for key in track], False):
                raise RuntimeError(f"Could not bake {kind} {label} {bone}")
    finally:
        controller.close_bracket(False)
    set_props(clip, enable_root_motion=False, force_root_lock=True)
    save(clip)
    return clip


def select_poses(kind, mesh, clips):
    if kind in SOURCE_POSES:
        water = [find_clip(clips, name) for name in ("swim_surface_dive_fwd", "swim_fwd_underwater_01",
                 "swim_fwd_underwater_surface_transitions_01")] if kind == "Mink" else []
        return [find_clip(clips, name) for name in SOURCE_POSES[kind]], water
    if len(clips) != 1:
        raise RuntimeError(f"Expected one source take for {kind}")
    source = clips[0]
    length = source.get_play_length()
    cut = lambda label, start, end, loop=False: sample_clip(kind, mesh, label, source, start, end, loop)
    if kind == "Horse":
        idle = cut("Idle", 29.8, 31.1, True)
        walk = cut("Walk", 10.0, 11.3, True)
        run = cut("PreviewRun", .25, 1.05, True)
        graze = cut("LowerHead", 26.2, 28.9, True)
        return [idle, walk, run, idle, graze, idle, idle], []
    if kind == "GoldenEagle":
        perched = cut("PreviewPerch", 5., 6.25, True)
        step = cut("PreviewStep", 16., 16.8, True)
        flight = cut("PreviewFlap", .4, 1.25, True)
        return [perched, step, step, perched, perched, perched, perched], [
            cut("PreviewTakeoff", 19.8, length), flight, cut("PreviewLand", 2., 3.4)]
    swim_start, swim_end = {"AriakeCatfish": (2.8, 4.8), "CommonCarp": (6.1, 8.85)}.get(kind, (0., length))
    swim = cut("Swim", swim_start, swim_end, True)
    idle = cut("Hold", .25, .25)
    return [idle, swim, swim, idle, idle, idle, idle], []


RIG_ANCHORS = {
    "Bighorn": ("RigPelvis", "RigHead"),
    "Jackrabbit": ("Hips", "Head"),
    "Horse": ("Hips", "Head"),
    "Mink": ("Hips", "Head"),
    "GoldenEagle": ("HIP", "SKULL"),
}
GROUND_CONTACTS = {
    "Bighorn": ("RigLFLegAnkle", "RigRFLegAnkle", "RigLBLegAnkle", "RigRBLegAnkle"),
    "Horse": ("LeftFingerBase", "RightFingerBase", "LeftFootHoof", "RightFootHoof"),
    "Jackrabbit": ("LeftHandIndex1", "RightHandIndex1", "LeftToeBase", "RightToeBase"),
}


def ground_contacts(kind, mesh, walk, bones):
    contacts = GROUND_CONTACTS.get(kind)
    if not contacts:
        return {}
    component = unreal.SkeletalMeshComponent()
    component.set_skeletal_mesh_asset(mesh)
    feet = [bones[name.casefold()] for name in contacts]
    ends = [str(component.get_parent_bone(foot)) for foot in feet]
    options = unreal.AnimPoseEvaluationOptions()
    frames = [POSE.get_anim_pose_at_time(walk, walk.get_play_length() * index / 30., options) for index in range(31)]
    return dict(enable_ground_ik=True, foot_bones=feet, ik_end_bones=ends,
                body_bone=RIG_ANCHORS[kind][0], turn_head_bone=RIG_ANCHORS[kind][1],
                foot_clearance_cm=3.5 if kind == "Horse" else 1.75,
                max_foot_correction_cm=26. if kind == "Horse" else 18.,
                contact_heights=[max(0., min(50., min(POSE.get_bone_pose(frame, foot, WORLD).translation.z
                                                     for frame in frames))) for foot in feet])


def resting_death(kind, mesh, idle, forward, body):
    """Bake a visual roll where the source has no death clip."""
    pose = POSE.get_anim_pose_at_time(idle, 0., unreal.AnimPoseEvaluationOptions())
    names = POSE.get_bone_names(pose)
    root = str(names[0])
    root_local = POSE.get_bone_pose(pose, root, LOCAL)
    support = names[1:]
    if kind == "GoldenEagle":
        # The FBX carries remote IK poles and duplicate control chains far below the mesh.
        support = [bone for bone in support if str(bone).casefold().startswith(
            ("hip", "chest", "skull", "belly", "wing", "flightfeather", "toe", "foot", "leg"))
            and "_ik" not in str(bone).casefold() and not str(bone).casefold().startswith("hip_")]
    elif kind == "Horse":
        support = [bone for bone in support if str(bone) != "Align"]
    positions = [POSE.get_bone_pose(pose, bone, WORLD).translation for bone in support]
    aquatic = kind in ("AriakeCatfish", "CommonCarp", "UnidentifiedFish")
    pivot = sum(positions[1:], positions[0]) / len(positions) if aquatic else POSE.get_bone_pose(pose, body, WORLD).translation
    floor = min(point.z for point in positions)
    math_library = unreal.MathLibrary

    def sample(t):
        ease = t * t * (3. - 2. * t)
        roll = math_library.quat_make_from_rotation_vector(forward * (85. * ease))
        rotate = lambda point: pivot + math_library.quat_rotate_vector(roll, point - pivot)
        translation = rotate(root_local.translation)
        if not aquatic:
            translation.z += floor * (1. - ease) - min(rotate(point).z for point in positions)
        return translation, math_library.multiply_quat_quat(roll, root_local.rotation), root_local.scale3d

    return BASE["bake_pose"](kind, mesh, "FallbackDeathRoll", 39, root, sample, pose)


def configure_representation(kind, mesh, clips):
    folder = f"{ROOT}/{kind}"
    skeleton = mesh.get_editor_property("skeleton")
    core, flight = select_poses(kind, mesh, clips)
    idle, walk, run, look, eat, rest, death = core
    reference = POSE.get_reference_pose(skeleton)
    bones = {str(bone).casefold(): str(bone) for bone in POSE.get_bone_names(reference)}
    body, head = (bones.get(name.casefold()) for name in RIG_ANCHORS.get(kind, ("", "")))
    get_location = lambda bone: POSE.get_bone_pose(reference, bone, WORLD).translation
    water_forward = unreal.Vector(0., 1., 0.) if kind == "UnidentifiedFish" else unreal.Vector(-1., 0., 0.)
    direction = (get_location(head) - get_location(body)) if body and head else water_forward
    yaw = math.degrees(math.atan2(direction.y, direction.x))
    forward = unreal.Vector(math.cos(math.radians(yaw)), math.sin(math.radians(yaw)), 0.)
    if kind not in SOURCE_POSES:
        death = resting_death(kind, mesh, idle, forward, body)
    speeds = TUNING.get(kind, (5., .1, 45., 100.))[2:]
    contacts = ground_contacts(kind, mesh, walk, bones)
    movement = [walk, run]
    movement.extend(find_clip(clips, name) for name in TURN_CLIPS.get(kind, ()))
    has_footstep_notifies = False
    if contacts:
        legs = list(zip(contacts["foot_bones"], contacts["ik_end_bones"]))
        authored = [BASE["contact_clip"](kind, clip, legs) for clip in movement]
        movement = [clip for clip, _ in authored]
        has_footstep_notifies = all(found for _, found in authored)
    walk, run = movement[:2]
    if kind in TURN_CLIPS:
        factory = set_props(unreal.BlendSpaceFactoryNew(), target_skeleton=skeleton)
        blend = create_owned(folder, f"BS_{kind}", unreal.BlendSpace, factory)
        wl, wr, rl, rr = movement[2:]
        configured = unreal.EcoCreatureBlendSpaceLibrary.configure_turning(
            blend, idle, walk, wl, wr, run, rl, rr, *speeds)
    else:
        factory = set_props(unreal.BlendSpaceFactory1D(), target_skeleton=skeleton)
        blend = create_owned(folder, f"BS_{kind}", unreal.BlendSpace1D, factory)
        configured = unreal.EcoCreatureBlendSpaceLibrary.configure_locomotion(blend, idle, walk, run, *speeds)
    if not configured:
        raise RuntimeError(f"Could not build blend space for {kind}")
    save(blend)
    factory = set_props(unreal.DataAssetFactory(), data_asset_class=unreal.EcoCreatureAnimationProfile)
    profile = create_owned(folder, f"DA_{kind}_Animation", unreal.EcoCreatureAnimationProfile, factory)
    attack = sample_clip(kind, mesh, "PreviewTalons", clips[0], 2.15, 2.9) if kind == "GoldenEagle" else look
    slots = [idle, eat, look, rest, look, rest, attack, rest, death, *flight]
    poses = [set_props(unreal.EcoCreaturePoseClip(), clip=clip, loop=index not in (6, 8, 9, 11), blend_seconds=.18)
             for index, clip in enumerate(slots)]
    set_props(profile, locomotion=blend, poses=poses, enable_ground_ik=False, stationary_speed=min(18., speeds[0] * .2))
    set_props(profile, **contacts)
    save(profile)
    factory = set_props(unreal.AnimBlueprintFactory(), parent_class=unreal.EcoCreatureAnimInstance, target_skeleton=skeleton)
    abp = create_owned(folder, f"ABP_{kind}", unreal.AnimBlueprint, factory)
    if not unreal.EcoCreatureAnimationBuilder.build_pose_graph(abp, profile):
        raise RuntimeError(f"Could not build AnimBP for {kind}")
    save(abp)
    factory = set_props(unreal.BlueprintFactory(), parent_class=unreal.EcoCreatureRepresentationActor)
    bp = create_owned(folder, f"BP_{kind}", unreal.Blueprint, factory)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    scale = {"GoldenEagle": .012, "UnidentifiedFish": .24}.get(kind, 1.)
    defaults = unreal.get_default_object(generated(bp))
    aquatic = kind in ("AriakeCatfish", "CommonCarp", "UnidentifiedFish")
    set_props(defaults, visual_species_id=kind, visual_mesh=mesh,
              death_animation=death, idle_speed=5., run_speed=speeds[1] * .8, soften_abrupt_facing=True,
              visual_mesh_scale=scale, always_swimming=aquatic,
              swim_pitch_limit=38. if aquatic or kind == "Mink" else 0.,
              flight_pitch_limit=50. if kind == "GoldenEagle" else 0.,
              flight_bank_limit=24. if kind == "GoldenEagle" else 0.)
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_representation(bp, blend, unreal.Rotator(yaw=-yaw), forward):
        raise RuntimeError(f"Could not configure facing for {kind}")
    if not unreal.EcoCreatureAnimationBuilder.configure_behavior_representation(bp, profile, generated(abp)):
        raise RuntimeError(f"Could not configure representation for {kind}")
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_footstep_notifies(bp, has_footstep_notifies):
        raise RuntimeError(f"Could not configure footstep source for {kind}")
    save(bp)
    return generated(bp)


def configure_species(kind, representation):
    radius, mass, walk, run = TUNING[kind]
    profile = set_props(unreal.EcoFaunaSpecies(), species_id=kind, visual_class=representation,
                        body_radius=radius, adult_mass=mass, walk_speed=walk, run_speed=run, regional_limit=10,
                        individual_response=True, death_settle_seconds=unreal.get_default_object(representation)
                        .get_editor_property("death_animation").get_play_length() + .1)
    if kind in ("AriakeCatfish", "CommonCarp"):
        catfish = kind == "AriakeCatfish"
        return set_props(profile, locomotion=unreal.EcoFaunaLocomotion.SWIMMING,
                         diet=unreal.EcoFaunaDiet.CARNIVORE if catfish else unreal.EcoFaunaDiet.OMNIVORE,
                         carrion_energy_per_meal=1.5 if catfish else 0.,
                         spawning_temperature_c=unreal.Vector2D(0., 40.) if catfish else unreal.Vector2D(17., 23.),
                         max_nursery_current=18. if catfish else 12.,
                         swim_depth_fraction=.82 if catfish else .56, day_activity=.26 if catfish else .8,
                         night_activity=.93 if catfish else .85, sight_range=450., routine_home_radius=275.,
                         maturity_seconds=180., gestation=35., birth_recovery=105., maintenance=.12)
    if kind == "UnidentifiedFish":
        # Provisional freshwater gameplay guild. The art's species and salinity are unknown.
        return set_props(profile, locomotion=unreal.EcoFaunaLocomotion.SWIMMING,
                         diet=unreal.EcoFaunaDiet.OMNIVORE, swim_depth_fraction=.21,
                         day_activity=.88, night_activity=.52, sight_range=325.,
                         routine_home_radius=230., regional_limit=8, max_nursery_current=10.,
                         maturity_seconds=125., gestation=24., birth_recovery=100., maintenance=.10)
    if kind == "GoldenEagle":
        prey = [
            set_props(unreal.EcoFaunaPreyRule(), species_id="Jackrabbit", max_prey_mass_ratio=.7, preference=1.),
            set_props(unreal.EcoFaunaPreyRule(), species_id="Rat", max_prey_mass_ratio=.35, preference=.55),
        ]
        return set_props(profile, locomotion=unreal.EcoFaunaLocomotion.FLIGHT, diet=unreal.EcoFaunaDiet.CARNIVORE,
                         prey_rules=prey, can_dive_hunt=True, attack_reach=95., attack_windup=.10,
                         carrion_energy_per_meal=5., flight_speed=900., flight_cruise_height=2300.,
                         flight_ceiling=5500., day_activity=1., night_activity=.16, sight_range=3200.,
                         nestling_seconds=90.)
    if kind == "Mink":
        rat = set_props(unreal.EcoFaunaPreyRule(), species_id="Rat", max_prey_mass_ratio=.5)
        hare = set_props(unreal.EcoFaunaPreyRule(), species_id="Jackrabbit", max_prey_mass_ratio=.65,
                         max_healthy_maturity=.28, max_injured_maturity=.42, preference=.55)
        prey = [rat, hare,
                set_props(unreal.EcoFaunaPreyRule(), species_id="UnidentifiedFish", max_prey_mass_ratio=.12, preference=1.05),
                set_props(unreal.EcoFaunaPreyRule(), species_id="AriakeCatfish", max_prey_mass_ratio=.2, preference=.85),
                set_props(unreal.EcoFaunaPreyRule(), species_id="CommonCarp", max_prey_mass_ratio=.3,
                          max_healthy_maturity=.4, max_injured_maturity=.5, preference=.75)]
        return set_props(profile, diet=unreal.EcoFaunaDiet.CARNIVORE, prey_rules=prey,
                         locomotion=unreal.EcoFaunaLocomotion.AMPHIBIOUS,
                         attack_reach=27., attack_windup=.13, carrion_energy_per_meal=4., habitat_carrion_range=520.,
                         sight_range=850., scent_range=700., eye_height=15., sweep_height=23., step_height=12.,
                         day_activity=.45, night_activity=.9, ground_turn_degrees_per_second=340.)
    if kind == "Jackrabbit":
        return set_props(profile, ground_turn_degrees_per_second=425., ground_acceleration=1100.,
                         eye_height=23., sweep_height=24., step_height=13., maturity_seconds=105.,
                         gestation=23., birth_recovery=85., day_activity=.35, night_activity=.95)
    if kind == "Bighorn":
        return set_props(profile, ground_turn_degrees_per_second=200., ground_acceleration=700.,
                         step_height=34., sweep_height=80., eye_height=102., defense_damage=20.,
                         social_neighbor_radius=640., social_spacing=125.,
                         offspring_guard_range=420., caregiver_follow_range=520., day_activity=.9, night_activity=.48)
    return set_props(profile, ground_turn_degrees_per_second=120., min_ground_normal_z=.86, ground_acceleration=380.,
                     step_height=25., sweep_height=120., eye_height=154., defense_damage=31.,
                     social_neighbor_radius=850., social_spacing=220.,
                     offspring_guard_range=510., caregiver_follow_range=740., day_activity=.9, night_activity=.68)


EXTERNAL_MATERIALS = {
    "Jackrabbit": (("Material_001", "eu_hare_dif", None), ("Material_002", "eu_rabbit_whiskers", None)),
    "Horse": (("Horse_Body", "difuse", "normal"), ("HorseHair", None, None)),
    "Mink": (("Material_001", "american_mink_chestnut", None),),
    "GoldenEagle": (("Material_001", "FALCON_diffuse", "normalmap"),),
}
OPACITY_TEXTURES = {
    ("Jackrabbit", "Material_002"): ("eu_rabbit_cards_alpha", "A"),
    ("Horse", "HorseHair"): ("Horse_PCB", "A"),
    ("GoldenEagle", "Material_001"): ("alpha_trans", "R"),
}


def configure_horse_coat_roughness(material):
    edit = unreal.MaterialEditingLibrary
    prop = unreal.MaterialProperty.MP_ROUGHNESS
    if edit.get_material_property_input_node(material, prop):
        return
    roughness = edit.create_material_expression(material, unreal.MaterialExpressionConstant, -460, 330)
    set_props(roughness, r=.7)
    if not edit.connect_material_property(roughness, "", prop):
        raise RuntimeError(f"Could not connect coat roughness on {material.get_path_name()}")


def connect_external_textures(kind, mesh):
    if kind not in EXTERNAL_MATERIALS:
        return
    directory = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()))
    directory = directory / "ExpandedFaunaImport" / kind / "textures"
    folder = f"{ROOT}/{kind}/Textures"
    slots = {str(slot.get_editor_property("material_slot_name")): slot.get_editor_property("material_interface")
             for slot in mesh.get_editor_property("materials")}
    edit = unreal.MaterialEditingLibrary
    for slot, diffuse, normal in EXTERNAL_MATERIALS[kind]:
        material = slots[slot]
        edit.delete_all_material_expressions(material)
        opacity = OPACITY_TEXTURES.get((kind, slot))
        set_props(material, blend_mode=unreal.BlendMode.BLEND_MASKED if opacity else unreal.BlendMode.BLEND_OPAQUE)
        if kind == "Horse" and slot == "HorseHair":
            # The source card texture contains packed data and opacity, with no hair albedo.
            tint = edit.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, -460, -240)
            set_props(tint, constant=unreal.LinearColor(.032, .014, .008, 1.))
            set_props(material, two_sided=True)
            if not edit.connect_material_property(tint, "", unreal.MaterialProperty.MP_BASE_COLOR):
                raise RuntimeError("Could not connect the horse hair tint")
        channels = [(diffuse, "RGB", unreal.MaterialProperty.MP_BASE_COLOR),
                    (normal, "RGB", unreal.MaterialProperty.MP_NORMAL)]
        if opacity:
            channels.append((*opacity, unreal.MaterialProperty.MP_OPACITY_MASK))
        for prefix, output, prop in channels:
            if prefix is None:
                continue
            is_normal = prop == unreal.MaterialProperty.MP_NORMAL
            source, = sorted(path for path in directory.iterdir() if path.name.startswith(prefix))
            name = "T_" + kind + "_" + prefix
            target = f"{folder}/{name}"
            if not ASSETS.does_asset_exist(target):
                task = set_props(unreal.AssetImportTask(), filename=str(source), destination_path=folder,
                                 destination_name=name, automated=True, save=False, replace_existing=False)
                IMPORT["TOOLS"].import_asset_tasks([task])
            texture = BASE["require"](target)
            ASSETS.set_metadata_tag(texture, "JYUOwner", OWNER)
            sample = edit.create_material_expression(material, unreal.MaterialExpressionTextureSample, -460, -240 if is_normal else 0)
            set_props(sample, texture=texture)
            if is_normal:
                set_props(texture, compression_settings=unreal.TextureCompressionSettings.TC_NORMALMAP, srgb=False)
                set_props(sample, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
            elif kind == "Horse" and slot == "HorseHair":
                set_props(texture, compression_settings=unreal.TextureCompressionSettings.TC_MASKS,
                          srgb=False, compression_no_alpha=False)
                set_props(sample, sampler_type=unreal.MaterialSamplerType.SAMPLERTYPE_MASKS)
            if not edit.connect_material_property(sample, output, prop):
                raise RuntimeError(f"Could not connect {kind} {slot} texture")
            save(texture)
        if kind == "Horse" and slot == "Horse_Body":
            configure_horse_coat_roughness(material)
        edit.recompile_material(material)
        save(material)


def fixture_box(label, position, size, pitch=0.):
    actor = next((actor for actor in ACTORS.get_all_level_actors() if actor.get_actor_label() == label), None)
    if actor is None:
        actor = ACTORS.spawn_actor_from_class(unreal.StaticMeshActor, unreal.Vector(*position), unreal.Rotator(pitch=pitch))
        actor.set_actor_label(label)
    actor.set_actor_location_and_rotation(unreal.Vector(*position), unreal.Rotator(pitch=pitch), False, False)
    component = actor.get_editor_property("static_mesh_component")
    component.set_static_mesh(unreal.load_asset("/Engine/BasicShapes/Cube"))
    component.set_collision_profile_name("BlockAll")
    actor.set_actor_scale3d(unreal.Vector(*(axis / 100. for axis in size)))


def add_seasonal_water_food(patches):
    patch_id = "ExpandedWaterSeasonalShelf"
    result = [patch for patch in patches if str(patch.get_editor_property("id")) != patch_id]
    result.append(set_props(unreal.EcoFaunaHabitatPatch(), id=patch_id, region_id="FaunaMeadow",
                            center=unreal.Vector(4100., -4700., 125.), submerged=True, stage=1,
                            consumers=["CommonCarp", "UnidentifiedFish"], capacity=12., energy_per_meal=2.5,
                            regrowth_per_second=.30, seasonal_full_growth_depth_cm=12., seasonal_dry_loss_per_second=.24))
    return result


def configure_map(species):
    if not ASSETS.does_asset_exist(MAP):
        if not ASSETS.duplicate_asset(SOURCE_MAP, MAP):
            raise RuntimeError(f"Could not duplicate {SOURCE_MAP}")
    levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not levels.load_level(MAP):
        raise RuntimeError(f"Could not load {MAP}")
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    ASSETS.set_metadata_tag(world, "JYUOwner", OWNER)
    runtime = next(actor for actor in ACTORS.get_all_level_actors() if isinstance(actor, unreal.EcoCreatureIntegrationSpawner))
    configure_audio(runtime)
    configured = {str(item.get_editor_property("species_id")): item for item in runtime.get_editor_property("fauna_species")}
    configured.update({str(item.get_editor_property("species_id")): item for item in species})
    fox = configured["Fox"]
    rules = [rule for rule in fox.get_editor_property("prey_rules") if str(rule.get_editor_property("species_id")) != "Jackrabbit"]
    rules.append(set_props(unreal.EcoFaunaPreyRule(), species_id="Jackrabbit", max_prey_mass_ratio=.7,
                           max_healthy_maturity=.65, max_injured_maturity=1., preference=.7))
    fox.set_editor_property("prey_rules", rules)
    runtime.set_editor_property("fauna_species", list(configured.values()))
    runtime.set_editor_property("global_population_limit", 150)
    positions = {
        "Bighorn": [(-1800, -1500, 0), (-2200, -1600, 0)],
        "Jackrabbit": [(-1100, -2200, 0), (-1500, -2400, 0)],
        "Horse": [(1000, -1800, 0), (1700, -1900, 0)],
        "Mink": [(2850, -4200, 0), (2970, -4350, 0)],
        "GoldenEagle": [(500, -3000, 0), (1000, -3250, 0)],
        "AriakeCatfish": [(3820, -4880, 20), (3980, -4950, 20)],
        "CommonCarp": [(4340, -4800, 35), (4490, -4900, 35)],
        "UnidentifiedFish": [(3720, -4410, 75), (3880, -4500, 85)],
    }
    groups = list(runtime.get_editor_property("groups"))
    index = next(i for i, item in enumerate(groups) if str(item.get_editor_property("region_id")) == "FaunaMeadow")
    group = groups[index]
    placements = [item for item in group.get_editor_property("fauna") if str(item.get_editor_property("species_id")) not in positions]
    placements.extend(set_props(unreal.EcoFaunaPlacement(), species_id=kind,
                                spawn_points=[unreal.Vector(*point) for point in points]) for kind, points in positions.items())
    group.set_editor_property("fauna", placements)
    group.set_editor_property("schedule", set_props(group.get_editor_property("schedule"), region_population_limit=150))
    groups[index] = group
    runtime.set_editor_property("groups", groups)
    actor_label = "JYU Expanded Fauna Water Fixture"
    water = next((actor for actor in ACTORS.get_all_level_actors() if actor.get_actor_label() == actor_label), None)
    if water is None:
        water = ACTORS.spawn_actor_from_class(unreal.EcoVegetationHabitat, unreal.Vector(4100., -4800., 45.))
        water.set_actor_label(actor_label)
    water.get_editor_property("bounds").set_box_extent(unreal.Vector(740., 520., 130.), False)
    set_props(water, habitat_id="ExpandedFaunaPool", region_id="FaunaMeadow", plant=1, drainage=.2,
              connected_fresh_water=True, supports_fauna_swimming=True, water_surface_z=110.,
              water_surface_size_cm=unreal.Vector2D(1480., 1040.), fauna_water_current=unreal.Vector(5., 0., 0.),
              water_level_rise=32., water_low_seconds=40., water_rise_seconds=30.,
              water_high_seconds=25., water_fall_seconds=45.)
    # The transverse shelf is exposed at low water. Its submerged approaches
    # support a continuous collision sweep in both directions at high water.
    fixture_box("JYU Water Passage Crest", (4170., -4800., 105.), (30., 1050., 12.))
    fixture_box("JYU Water Passage West Ramp", (4033., -4800., 53.), (267., 1050., 12.), 24.)
    fixture_box("JYU Water Passage East Ramp", (4307., -4800., 53.), (267., 1050., 12.), -24.)
    fixture_box("JYU Bighorn Steep Ground", (-2080., -1770., 91.), (300., 300., 14.), 36.)
    fixture_box("JYU Bighorn Ledge", (-2215., -1770., 159.), (95., 300., 17.))
    fixture_box("JYU Rabbit Low Step", (-1290., -2530., 5.), (65., 160., 10.))
    fixture_box("JYU Horse Gentle Ground", (1420., -2120., 45.), (360., 300., 12.), 15.)
    perches = []
    for index, (x, y, height) in enumerate(((-50., -3400., 360.), (2450., -2950., 440.)), 1):
        fixture_box(f"JYU Eagle Perch {index} Support", (x, y, (height - 24.) / 2.), (56., 56., height - 24.))
        fixture_box(f"JYU Eagle Perch {index} Platform", (x, y, height - 12.), (138., 138., 24.))
        perch = set_props(unreal.EcoFaunaPerch(), species_id="GoldenEagle", region_id="FaunaMeadow",
                          location=unreal.Vector(x, y, height))
        if index == 1:
            perch.set_editor_property("nest_id", "ExpandedEagleWestNest")
        perches.append(perch)
    runtime.set_editor_property("fauna_perches", perches)
    patches = [patch for patch in runtime.get_editor_property("fauna_habitat_patches")
               if not str(patch.get_editor_property("id")).startswith("ExpandedWater")]
    for suffix, point, consumers in (
        ("BenthicInsects", (3830., -4770., 22.), ["AriakeCatfish", "CommonCarp"]),
        ("MacrophyteEdge", (4455., -4810., 46.), ["CommonCarp"]),
        ("RootMargin", (3980., -5040., 63.), ["AriakeCatfish"]),
        ("ConnectedShelf", (4345., -4720., 59.), ["AriakeCatfish", "CommonCarp"]),
        ("LittoralNursery", (3810., -4410., 72.), ["UnidentifiedFish"]),
        ("SurfaceInvertebrates", (3650., -4700., 87.), ["UnidentifiedFish"]),
    ):
        patches.append(set_props(unreal.EcoFaunaHabitatPatch(), id="ExpandedWater" + suffix,
                                 region_id="FaunaMeadow", center=unreal.Vector(*point), submerged=True, stage=1,
                                 aquatic_nursery=suffix in ("MacrophyteEdge", "RootMargin", "LittoralNursery"),
                                 consumers=consumers, capacity=18., regrowth_per_second=.20, energy_per_meal=3.))
    patches.append(set_props(unreal.EcoFaunaHabitatPatch(), id="ExpandedWaterShoreForage",
                             region_id="FaunaMeadow", center=unreal.Vector(3550., -4550., 48.),
                             submerged=True, has_shore_entry=True, shore_point=unreal.Vector(3325., -4550., 0.),
                             water_entry_point=unreal.Vector(3410., -4550., 65.),
                             consumers=["Mink", "AriakeCatfish"], capacity=22., regrowth_per_second=.25,
                             energy_per_meal=5.))
    patches.append(set_props(unreal.EcoFaunaHabitatPatch(), id="ExpandedWaterSouthBank",
                             region_id="FaunaMeadow", center=unreal.Vector(3580., -5190., 30.),
                             submerged=True, has_shore_entry=True, shore_point=unreal.Vector(3570., -5360., 0.),
                             water_entry_point=unreal.Vector(3570., -5270., 39.),
                             consumers=["Mink"], capacity=10., regrowth_per_second=.12, energy_per_meal=4.))
    runtime.set_editor_property("fauna_habitat_patches", patches)
    preview_name = "JYU Unidentified Fish Animation Preview"
    actor = next((item for item in ACTORS.get_all_level_actors() if item.get_actor_label() == preview_name), None)
    if actor is not None:
        ACTORS.destroy_actor(actor)
    if not unreal.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError(f"Could not save {MAP}")
    unreal.log(f"ECO_EXPANDED_MAP_READY {MAP}")


def configure_audio(runtime):
    source = BASE["require"]("/Game/JYU/Fauna/Audio/DA_FaunaFootsteps")
    audio = BASE["duplicate_owned"](source.get_path_name(), f"{ROOT}/DA_ExpandedFaunaFootsteps")
    profiles = dict(source.get_editor_property("profiles"))
    templates = {"Bighorn": "Herbivore", "Jackrabbit": "Rat", "Horse": "Buffalo", "Mink": "Fox", "GoldenEagle": "Crow"}
    for species, template in templates.items():
        value = next(profile for name, profile in profiles.items() if str(name) == template)
        walk, run = TUNING[species][2:]
        profiles[unreal.Name(species)] = set_props(value, walk_speed=walk, run_speed=run)
    audio.set_editor_property("profiles", profiles)
    save(audio)
    runtime.set_editor_property("footstep_audio_set", audio)


def fix_skeletal_material_usage():
    edit = unreal.MaterialEditingLibrary
    usage = unreal.MaterialUsage.MATUSAGE_SKELETAL_MESH
    paths = ("/Game/JYU/Fauna/Rat/Imported/M_Rat",
             f"{ROOT}/AriakeCatfish/Imported/QS1317-W02-1-1_animation/Materials/Material",
             f"{ROOT}/UnidentifiedFish/Imported/animated_low_poly_fish/Materials/Material_006")
    for path in paths:
        material = BASE["require"](path)
        if isinstance(material, unreal.Material):
            edit.set_base_material_usage(material, usage, True)
            edit.recompile_material(material)
        elif isinstance(material, unreal.MaterialInstanceConstant):
            edit.set_material_usage_override(material, usage, True, True)
            edit.update_material_instance(material)
        else:
            raise RuntimeError(f"Unexpected material class at {path}")
        if not edit.has_material_usage(material, usage):
            raise RuntimeError(f"Could not enable skeletal mesh usage on {path}")
        save(material)
    unreal.log("ECO_RIPARIAN_SKELETAL_MATERIALS_READY")


def main():
    if "-EcoExpandedFixSkeletalMaterialUsage" in unreal.SystemLibrary.get_command_line():
        fix_skeletal_material_usage()
        return
    if "-EcoExpandedSeasonalWaterFood" in unreal.SystemLibrary.get_command_line():
        destination = "/Game/JYU/Maps/LV_JYU_SeasonalWaterFood"
        if not ASSETS.does_asset_exist(destination) and not ASSETS.duplicate_asset(MAP, destination):
            raise RuntimeError(f"Could not duplicate {MAP} to {destination}")
        levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        if not levels.load_level(destination):
            raise RuntimeError(f"Could not load {destination}")
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        runtime = next(actor for actor in ACTORS.get_all_level_actors() if isinstance(actor, unreal.EcoCreatureIntegrationSpawner))
        runtime.set_editor_property("fauna_habitat_patches", add_seasonal_water_food(runtime.get_editor_property("fauna_habitat_patches")))
        ASSETS.set_metadata_tag(world, "JYUOwner", "JYU.SeasonalWaterFood")
        if not unreal.EditorLoadingAndSavingUtils.save_map(world, destination):
            raise RuntimeError(f"Could not save {destination}")
        unreal.log("ECO_EXPANDED_SEASONAL_WATER_FOOD_READY")
        return
    if "-EcoExpandedFixHorseMaterial" in unreal.SystemLibrary.get_command_line():
        mesh, _ = mesh_and_clips("Horse")
        connect_external_textures("Horse", mesh)
        unreal.log("ECO_HORSE_HAIR_MATERIAL_READY")
        return
    if "-EcoExpandedConfigureMapOnly" in unreal.SystemLibrary.get_command_line():
        visuals = {kind: unreal.load_class(None, f"{ROOT}/{kind}/BP_{kind}.BP_{kind}_C") for kind in TUNING}
        missing = [kind for kind, visual in visuals.items() if not visual]
        if missing:
            raise RuntimeError(f"Missing configured visual classes: {', '.join(missing)}")
        configure_map([configure_species(kind, visual) for kind, visual in visuals.items()])
        return
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, "Interchange.FeatureFlags.Import.FBX 0")
    species = []
    errors = []
    for kind in TUNING:
        try:
            if kind == "GoldenEagle":
                rename_eagle_source()
            mesh, clips = mesh_and_clips(kind)
            connect_external_textures(kind, mesh)
            representation = configure_representation(kind, mesh, clips)
            species.append(configure_species(kind, representation))
            unreal.log(f"ECO_EXPANDED_PRESENTATION_READY {kind}")
        except Exception as error:
            errors.append(kind)
            unreal.log_warning(f"ECO_EXPANDED_PRESENTATION_FAILED {kind}: {error}")
    if errors:
        raise RuntimeError(f"Failed species presentation: {', '.join(errors)}")
    configure_map(species)


if __name__ == "__main__":
    main()

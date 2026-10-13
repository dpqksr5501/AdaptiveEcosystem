"""Read-only audit of imported anatomical forward and turn animation root orientation."""
import unreal
import math

for mesh_path in (
    "/Game/AnimalVarietyPack/Wolf/Meshes/SK_Wolf",
    "/Game/AnimalVarietyPack/DeerStagAndDoe/Meshes/SK_DeerStag",
):
    mesh = unreal.load_asset(mesh_path)
    pose = unreal.AnimPoseExtensions.get_reference_pose(mesh.get_editor_property("skeleton"))
    names = unreal.AnimPoseExtensions.get_bone_names(pose)
    unreal.log("FACING_AUDIT " + mesh_path)
    for name in names:
        if any(word in str(name).lower() for word in ("head", "pelvis", "root", "neck", "tail", "spine")):
            transform = unreal.AnimPoseExtensions.get_bone_pose(pose, name, unreal.AnimPoseSpaces.WORLD)
            unreal.log("FACING_BONE " + str(name) + " " + str(transform.translation))

for kind, folder, prefix in (
    ("Wolf", "/Game/AnimalVarietyPack/Wolf/Animations", "ANIM_Wolf"),
    ("Deer", "/Game/AnimalVarietyPack/DeerStagAndDoe/Animations", "ANIM_DeerStag"),
):
    # Imported deer has no RunTurn clips. Avoid editor-only existence helpers
    # here: the same read-only audit also runs in a paused PIE world.
    suffixes = ("WalkTurnL", "WalkTurnR", "RunTurnL", "RunTurnR") if kind == "Wolf" else ("WalkTurnL", "WalkTurnR")
    for suffix in suffixes:
        path = folder + "/" + prefix + "_" + suffix
        animation = unreal.load_asset(path)
        for time in (0.0, animation.sequence_length / 2.0, animation.sequence_length):
            pose = unreal.AnimPoseExtensions.get_anim_pose_at_time(animation, time, unreal.AnimPoseEvaluationOptions())
            root = unreal.AnimPoseExtensions.get_bone_pose(pose, "root", unreal.AnimPoseSpaces.WORLD)
            unreal.log("FACING_CLIP " + kind + " " + suffix + " " + str(time) + " " + str(root))

world = unreal.EditorLevelLibrary.get_game_world()
if world:
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureRepresentationActor):
        velocity = actor.get_velocity()
        if math.hypot(velocity.x, velocity.y) <= 5:
            continue
        mesh = actor.get_editor_property("creature_mesh")
        prefix = "Wolf_-" if str(actor.get_editor_property("visual_species_id")) == "Wolf" else "STAG_-"
        delta = mesh.get_socket_location(prefix + "Head") - mesh.get_socket_location(prefix + "Pelvis")
        error = (math.degrees(math.atan2(delta.y, delta.x) - math.atan2(velocity.y, velocity.x)) + 180) % 360 - 180
        unreal.log("FACING_LIVE_ANATOMY " + actor.get_name() + " error=" + str(error) + " mesh=" + str(mesh.get_relative_transform().rotation))

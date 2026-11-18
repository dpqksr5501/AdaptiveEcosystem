"""Dress the owned riparian fixture with selected, migrated Project_J meshes."""

import math
from pathlib import Path
import random
import runpy

import unreal as u


HERE = Path(__file__).parent
MESHES = runpy.run_path(str(HERE / "audit_jyu_riparian_asset_transfer.py"))["MESHES"]
SOURCE = "/Game/JYU/Maps/LV_JYU_RiparianHabitat"
MAP = "/Game/JYU/Maps/LV_JYU_RiparianProjectJ"
PREFIX = "JYU Riparian ProjectJ "
ASSETS = u.EditorAssetLibrary
ACTORS = u.get_editor_subsystem(u.EditorActorSubsystem)


def use_mesh(actor, mesh, height=None, width=None):
    component = actor.static_mesh_component
    component.set_static_mesh(mesh)
    component.set_collision_profile_name("NoCollision")
    bounds = mesh.get_bounding_box()
    extent = bounds.max - bounds.min
    scale = height / extent.z if height is not None else width / max(extent.x, extent.y)
    actor.set_actor_scale3d(u.Vector(scale, scale, scale))
    # The fern's source mesh has spare slots pointing at the editor checker material.
    for i in range(len(mesh.get_editor_property("static_materials"))):
        if mesh.get_material(i).get_name() == "WorldGridMaterial":
            component.set_material(i, mesh.get_material(0))
    return bounds.min.z * scale


def main():
    if not ASSETS.does_asset_exist(MAP) and not ASSETS.duplicate_asset(SOURCE, MAP):
        raise RuntimeError(f"Could not duplicate {SOURCE}")
    if not u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(MAP):
        raise RuntimeError(f"Could not open {MAP}")
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    loaded = {role: u.load_asset(package) for role, package in MESHES.items()}
    if not all(isinstance(mesh, u.StaticMesh) for mesh in loaded.values()):
        raise RuntimeError("Expected the nine verified Project_J meshes")
    existing = {actor.get_actor_label(): actor for actor in ACTORS.get_all_level_actors()}
    pool = next(a for a in existing.values() if isinstance(a, u.EcoVegetationHabitat)
                and str(a.get_editor_property("habitat_id")) == "ExpandedFaunaPool")
    surface = pool.get_editor_property("water_surface")
    surface.set_mobility(u.ComponentMobility.MOVABLE)
    rng = random.Random(5861)

    for label, actor in sorted(existing.items()):
        if label.startswith("JYU Riparian Shallows Plant"):
            use_mesh(actor, loaded[rng.choice(("submerged_a", "submerged_b"))], height=rng.uniform(52., 81.))
        elif label.startswith("JYU Riparian Bank Plant"):
            use_mesh(actor, loaded["fern"], height=rng.uniform(38., 62.))

    def add(label, role, x, y, yaw, width=None, height=None, pitch=0., floating=False):
        name = PREFIX + label
        if floating:
            level = surface.get_world_location().z + 1.5
        else:
            for dx, dy in ((0., 0.), (30., 0.), (-30., 0.), (0., -35.), (0., 35.), (-50., -30.)):
                ground = u.EcoCreatureAnimationBuilder.project_placement_point(world, u.Vector(x + dx, y + dy, 310.))
                if ground is not None:
                    x, y, level = ground.x, ground.y, ground.z
                    break
            else:
                raise RuntimeError(f"No clear terrain under {name} near {(x, y)}")
        actor = existing.get(name) or ACTORS.spawn_actor_from_class(u.StaticMeshActor, u.Vector(x, y, level))
        actor.set_actor_label(name)
        component = actor.static_mesh_component
        if floating:
            component.set_mobility(u.ComponentMobility.MOVABLE)
            component.set_absolute(False, False, True)
        bottom = use_mesh(actor, loaded[role], height, width)
        actor.set_actor_location_and_rotation(u.Vector(x, y, level - bottom), u.Rotator(pitch=pitch, yaw=yaw), False, False)
        if floating and actor.get_attach_parent_actor() != pool:
            keep = u.AttachmentRule.KEEP_WORLD
            if not actor.attach_to_component(surface, "None", keep, keep, keep, False):
                raise RuntimeError(f"Could not attach {name} to the water surface")

    cattails = ((3395., -4785.), (3410., -4840.), (3380., -4910.), (3435., -4995.),
                (3680., -4370.), (3750., -4380.), (3800., -4355.), (4660., -5245.))
    for i, (x, y) in enumerate(cattails):
        add(f"Cattail {i:02}", "cattail_a" if i % 3 else "cattail_b", x, y, rng.uniform(-180., 180.),
            height=rng.uniform(107., 159.))
    for i, (x, y) in enumerate(((3555., -4380.), (3620., -4410.), (3700., -4460.), (3750., -4355.),
                               (4680., -5130.), (4620., -5185.))):
        add(f"Duckweed {i:02}", "floating_leaves", x, y, rng.uniform(-180., 180.),
            width=rng.uniform(66., 118.), floating=True)
    for i in range(9):
        angle = i * math.tau / 9.
        radius = rng.uniform(12., 52.)
        add(f"Leaf Litter {i:02}", "leaf_litter", 3160. + radius * math.cos(angle), -4810. + radius * math.sin(angle),
            rng.uniform(-180., 180.), width=rng.uniform(22., 38.))
    add("Fallen Birch West", "fallen_log", 3290., -5005., 24., width=256.)
    add("Fallen Birch East", "fallen_log", 4675., -5080., -44., width=208.)
    add("Bank Roots", "root_mat", 3350., -4865., 170., height=162., pitch=-38.)

    ASSETS.set_metadata_tag(world, "JYUOwner", "JYU.RiparianProjectJ")
    if not u.EditorLoadingAndSavingUtils.save_map(world, MAP):
        raise RuntimeError(f"Could not save {MAP}")
    u.log(f"ECO_RIPARIAN_PROJECTJ_READY {MAP}")


if __name__ == "__main__":
    main()

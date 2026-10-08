"""Focused editor update: only integrated animal BP defaults and new 2D BS assets.
Preserves region/map edits, EntityConfig GUIDs, spawn groups and original animations.
Can be imported by the full generator or run from the editor Python console.
"""
import unreal

ROOT = "/Game/Creatures/Integrated"


def load(path):
    asset = unreal.load_asset(path)
    if not asset:
        raise RuntimeError("Missing asset: " + path)
    return asset


def configure(kind, blueprint):
    folder, prefix = ("/Game/AnimalVarietyPack/Wolf/Animations", "ANIM_Wolf") if kind == "Wolf" else (
        "/Game/AnimalVarietyPack/DeerStagAndDoe/Animations", "ANIM_DeerStag")
    clips = [load(folder + "/" + prefix + "_" + suffix)
             for suffix in ("IdleBreathe", "Walk", "WalkTurnL", "WalkTurnR", "Run")]
    run_turns = [load(folder + "/" + prefix + "_" + suffix) for suffix in ("RunTurnL", "RunTurnR")] if kind == "Wolf" else [None, None]
    name = "BS_Eco" + kind + "_Turning"
    blend = unreal.load_asset(ROOT + "/" + name)
    if not blend:
        factory = unreal.BlendSpaceFactoryNew()
        factory.set_editor_property("target_skeleton", clips[0].get_editor_property("skeleton"))
        blend = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, ROOT, unreal.BlendSpace, factory)
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_turning(blend, *clips, *run_turns, 300.0, 900.0):
        raise RuntimeError("2D BS skeleton/in-place validation failed: " + kind)
    if not unreal.EditorAssetLibrary.save_loaded_asset(blend, only_if_is_dirty=False):
        raise RuntimeError("Could not save " + name)
    unreal.BlueprintEditorLibrary.compile_blueprint(blueprint)
    # Both imported skeletons: pelvis -> head is +Y. Actor's movement forward is +X.
    if not unreal.EcoCreatureBlendSpaceLibrary.configure_representation(
        blueprint, blend, unreal.Rotator(pitch=0, yaw=-90, roll=0), unreal.Vector(0, 1, 0)):
        raise RuntimeError("BP defaults did not survive compilation: " + kind)
    if not unreal.EditorAssetLibrary.save_loaded_asset(blueprint, only_if_is_dirty=False):
        raise RuntimeError("Could not save animal BP: " + kind)
    unreal.log("CREATURE_LOCOMOTION_OK " + kind + " " + blend.get_path_name() + " meshYaw=-90 forward=+Y")
    return blend


def update():
    for kind in ("Deer", "Wolf"):
        configure(kind, load(ROOT + "/BP_Eco" + kind))


if __name__ == "__main__":
    update()

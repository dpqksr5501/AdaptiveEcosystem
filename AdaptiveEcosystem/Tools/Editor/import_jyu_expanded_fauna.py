"""Import the local expanded-fauna sources into an isolated JYU content folder."""

import json
import os
import shutil
from pathlib import Path
from zipfile import ZipFile

import unreal


ROOT = "/Game/JYU/ExpandedFauna"
OWNER = "JYU.ExpandedFauna"
DESKTOP = Path(os.environ.get("ECO_FAUNA_SOURCE", str(Path.home() / "Desktop" / "Add_Animal")))
VAULT = Path(os.environ.get("ECO_FAUNA_FISH_SOURCE",
    r"C:\ProgramData\Epic\EpicGamesLauncher\VaultCache\FabLibrary\Animated_Low_poly_Fish-b99b6056"))
SOURCES = {
    "Bighorn": ("bighorn-animated-cel-shading-3d-model.zip", "source/BigHorn Animated.fbx"),
    "Jackrabbit": ("hare-from-cotw-game.zip", "source/jackrabithare.fbx"),
    "Horse": ("horse.zip", "source/full.fbx"),
    "Mink": ("cotw-american-mink.zip", "source/cotw american mink.fbx"),
    "GoldenEagle": ("mouse.zip", "source/FALCON.fbx"),
    "AriakeCatfish": ("cc0-ariake-stream-catfis-animation.zip", "source/QS1317-W02-1-1_animation.glb"),
    "CommonCarp": (None, "cc0____carp_cyprinus_carpio_animation.glb"),
    "UnidentifiedFish": (None, VAULT / "glb" / "converted" / "animated_low_poly_fish.glb"),
}
ASSETS = unreal.EditorAssetLibrary
TOOLS = unreal.AssetToolsHelpers.get_asset_tools()


def props(obj, **values):
    for name, value in values.items():
        obj.set_editor_property(name, value)
    return obj


def stage_source(kind, archive, member, staging):
    if not archive:
        return DESKTOP / member
    directory = staging / kind
    with ZipFile(DESKTOP / archive) as source:
        for entry in [member, *(name for name in source.namelist() if name.startswith("textures/") and not name.endswith("/"))]:
            destination = directory / entry
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source.open(entry) as content, destination.open("wb") as output:
                shutil.copyfileobj(content, output)
    return directory / member


def assets_at(folder):
    if not ASSETS.does_directory_exist(folder):
        return []
    return [asset for path in ASSETS.list_assets(folder, recursive=True) if (asset := unreal.load_asset(path))]


def import_source(kind, source):
    folder = f"{ROOT}/{kind}/Imported"
    if not source.is_file():
        raise FileNotFoundError(source)
    existing = assets_at(folder)
    if existing:
        if any(ASSETS.get_metadata_tag(asset, "JYUOwner") != OWNER for asset in existing):
            raise RuntimeError(f"Import directory contains an asset without the expected owner: {folder}")
        return existing

    if kind == "GoldenEagle":
        # Unreal's legacy FBX importer strips the Blender "Armature" wrapper.
        # This rig has sibling deform and control branches beneath that wrapper.
        # Retain it as the shared root, without changing the binary node offsets.
        data = source.read_bytes()
        wrapper = b"Armature\x00\x01Model"
        if data.count(wrapper) != 1:
            raise RuntimeError("Expected a single Falcon armature wrapper")
        source = source.with_name("FALCON_Rooted.fbx")
        source.write_bytes(data.replace(wrapper, b"FalcRoot\x00\x01Model"))

    task = props(unreal.AssetImportTask(), filename=str(source), destination_path=folder,
                 automated=True, save=False, replace_existing=False)
    if source.suffix.lower() == ".fbx":
        options = props(unreal.FbxImportUI(), automated_import_should_detect_type=False,
                        mesh_type_to_import=unreal.FBXImportType.FBXIT_SKELETAL_MESH,
                        import_as_skeletal=True, import_mesh=True, import_animations=True,
                        import_materials=True, import_textures=True, create_physics_asset=True)
        task.set_editor_property("options", options)
        task.set_editor_property("factory", unreal.FbxFactory())
    TOOLS.import_asset_tasks([task])
    imported = {asset.get_path_name(): asset for asset in [*task.get_objects(), *assets_at(folder)]}
    for asset in tuple(imported.values()):
        if isinstance(asset, unreal.SkeletalMesh):
            for field in ("skeleton", "physics_asset"):
                dependency = asset.get_editor_property(field)
                if dependency and dependency.get_path_name().startswith(folder + "/"):
                    imported[dependency.get_path_name()] = dependency
    for asset in imported.values():
        if not asset.get_path_name().startswith(folder + "/"):
            continue
        ASSETS.set_metadata_tag(asset, "JYUOwner", OWNER)
        if isinstance(asset, unreal.AnimSequence):
            props(asset, enable_root_motion=False, force_root_lock=True)
        if not ASSETS.save_loaded_asset(asset, only_if_is_dirty=False):
            raise RuntimeError(f"Could not save {asset.get_path_name()}")
    return list(imported.values())


def describe(assets):
    rows = []
    for asset in sorted(assets, key=lambda item: item.get_path_name()):
        row = {"type": asset.get_class().get_name(), "path": asset.get_path_name()}
        if isinstance(asset, (unreal.SkeletalMesh, unreal.AnimSequence)):
            skeleton = asset.get_editor_property("skeleton")
            row["skeleton"] = skeleton.get_path_name() if skeleton else None
        if isinstance(asset, unreal.AnimSequence):
            row["duration"] = asset.get_play_length()
        rows.append(row)
    return rows


def main():
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    unreal.SystemLibrary.execute_console_command(world, "Interchange.FeatureFlags.Import.FBX 0")
    staging = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "ExpandedFaunaImport"
    staging.mkdir(parents=True, exist_ok=True)
    report = {}
    for kind, (archive, member) in SOURCES.items():
        try:
            assets = import_source(kind, stage_source(kind, archive, member, staging))
            rows = describe(assets)
            report[kind] = {"assets": rows}
            if not any(row["type"] == "SkeletalMesh" for row in rows) or not any(row["type"] == "AnimSequence" for row in rows):
                report[kind]["error"] = "The import must provide a skeletal mesh and an animation sequence"
        except Exception as error:
            report[kind] = {"error": str(error)}
        unreal.log(f"ECO_EXPANDED_IMPORT {kind}: {report[kind].get('error', 'OK')}")
    (staging / "import_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if any("error" in entry for entry in report.values()):
        raise RuntimeError("Expanded fauna import incomplete. See Saved/ExpandedFaunaImport/import_report.json")


if __name__ == "__main__":
    main()

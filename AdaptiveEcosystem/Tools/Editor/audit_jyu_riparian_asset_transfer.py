"""Resolve selected Project_J packages, or verify them after migration."""

import json
from pathlib import Path
import re

import unreal as u


SKYTOWN = "/Game/Map_Resource/SkyTown/Meshes"
NATURE = "/Game/Map_Resource/ProceduralNaturePack/Meshes"
MESHES = {
    "cattail_a": f"{SKYTOWN}/SM_GrassSky06_Cattail01",
    "cattail_b": f"{SKYTOWN}/SM_GrassSky06_Cattail04",
    "submerged_a": f"{SKYTOWN}/SM_Seaweed02",
    "submerged_b": f"{SKYTOWN}/SM_Seaweed04",
    "floating_leaves": f"{SKYTOWN}/SM_Duckweed01",
    "leaf_litter": f"{SKYTOWN}/SM_LeavesGround02",
    "fallen_log": f"{SKYTOWN}/SM_WoodenLogs_Birch04",
    "root_mat": f"{SKYTOWN}/SM_Roots01",
    "fern": f"{NATURE}/leaves/leaves_fern_01",
}
FORAGE_MESHES = {
    "grass": f"{SKYTOWN}/SM_GrassSky02",
    "forbs": "/Game/Map_Resource/MedievalVillage/Meshes/Scatter/SM_Flower_001",
    "browse": f"{SKYTOWN}/SM_ForestShrub02",
    "wet_meadow": f"{SKYTOWN}/SM_GrassSky03",
}
CANOPY_MESHES = {
    "broadleaf": f"{SKYTOWN}/SM_AutumnTree02",
    "birch": "/Game/Map_Resource/MedCastle/Landscape/Mesh/Foliage/SM_Birch",
}


def inspect():
    command = u.SystemLibrary.get_command_line()
    manifest = re.search(r'-RiparianAssetManifest="?([^"\r\n]+?\.json)"?(?:\s|$)', command)
    if not manifest:
        raise RuntimeError("Expected -RiparianAssetManifest=<output.json>")
    path = Path(manifest.group(1))
    selection = (CANOPY_MESHES if "-EcoRiparianCanopyAssets" in command else
                 FORAGE_MESHES if "-EcoHerbivoreAssets" in command else MESHES)
    registry = u.AssetRegistryHelpers.get_asset_registry()
    registry.scan_paths_synchronous(sorted({p.rsplit("/", 1)[0] for p in selection.values()}), True)
    content = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_content_dir()))
    hard = u.AssetRegistryDependencyOptions(include_hard_package_references=True)
    packages, missing, mounts = set(), set(), set()
    pending = list(selection.values())
    while pending:
        package = pending.pop()
        if package in packages or package in missing:
            continue
        file = content / (package.removeprefix("/Game/") + ".uasset")
        if not file.is_file():
            missing.add(package)
            continue
        if not registry.get_assets_by_package_name(package):
            registry.scan_files_synchronous([str(file)], True)
        packages.add(package)
        for dependency in registry.get_dependencies(package, hard) or ():
            dependency = str(dependency)
            if dependency.startswith("/Game/"):
                pending.append(dependency)
            elif not dependency.startswith(("/Script/", "/Engine/")):
                mounts.add(dependency)
    if missing:
        raise RuntimeError(f"Missing package dependencies: {sorted(missing)}")

    meshes = {}
    for role, package in selection.items():
        asset = u.load_asset(package)
        if not isinstance(asset, u.StaticMesh):
            raise RuntimeError(f"Missing static mesh {package}")
        bounds = asset.get_bounding_box()
        slots = [asset.get_material(i) for i in range(len(asset.get_editor_property("static_materials")))]
        if not slots or not all(slots):
            raise RuntimeError(f"Missing material slot on {package}")
        meshes[role] = {"package": package, "bounds": [[v.x, v.y, v.z] for v in (bounds.min, bounds.max)],
                        "materials": [slot.get_path_name() for slot in slots]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"meshes": meshes, "packages": sorted(packages), "mounts": sorted(mounts)}, indent=2), encoding="utf-8")
    u.log(f"ECO_RIPARIAN_ASSET_MANIFEST meshes={len(meshes)} packages={len(packages)} mounts={len(mounts)}")


if __name__ == "__main__":
    inspect()

"""Create isolated World Partition copies for the Integration_JwJ R7e audit."""
import json
from pathlib import Path
import traceback

import unreal as u

SOURCE = "/Game/JWJ/Integration_JwJ"
DONOR = "/Game/JYU/Maps/LV_JYU_Fauna"
ROOT = "/Game/JYU/Maps/"
TARGETS = ("LV_JYU_IntegrationR7e", "LV_JYU_IntegrationR7eFauna")
OWNER = "JYU.IntegrationR7eAudit"
assets = u.EditorAssetLibrary
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
actors = u.get_editor_subsystem(u.EditorActorSubsystem)
result = {"source": SOURCE, "donor": DONOR, "maps": [], "completed": False}
out = Path(u.Paths.project_saved_dir()).resolve() / "ProjectAudit_20261112/IntegrationR7eAuthoring.json"


def property_value(obj, native, python):
    try:
        return obj.get_editor_property(native)
    except Exception:
        return obj.get_editor_property(python)


def assign(obj, native, python, value):
    try:
        obj.set_editor_property(native, value)
    except Exception:
        obj.set_editor_property(python, value)


def spawner():
    found = [actor for actor in actors.get_all_level_actors()
             if isinstance(actor, u.EcoCreatureIntegrationSpawner)]
    if len(found) != 1:
        raise RuntimeError(f"Expected one authored spawner, got {len(found)}")
    return found[0]


try:
    if not levels.load_level(DONOR):
        raise RuntimeError("Unable to load existing fauna profiles")
    donor = spawner()
    profiles = list(property_value(donor, "FaunaSpecies", "fauna_species"))
    donor_groups = list(property_value(donor, "Groups", "groups"))
    counts = {str(row.get_editor_property("species_id")): len(row.get_editor_property("spawn_points"))
              for group in donor_groups for row in group.get_editor_property("fauna")}
    if set(counts) != {"Buffalo", "Crow", "Fox", "Leopard", "Pig", "Rat"}:
        raise RuntimeError(f"Unexpected donor fauna {counts}")
    for index, target_name in enumerate(TARGETS):
        target = ROOT + target_name
        if assets.does_asset_exist(target):
            if not levels.load_level(target):
                raise RuntimeError(f"Unable to load {target}")
            if assets.get_metadata_tag(editor.get_editor_world(), "EcoAuditOwner") != OWNER:
                raise RuntimeError(f"Existing target is outside this audit: {target}")
        elif not levels.new_level_from_template(target, SOURCE):
            raise RuntimeError(f"World Partition copy failed: {target}")
        world = editor.get_editor_world()
        if world.get_path_name().split(".")[0] != target:
            raise RuntimeError(f"Unexpected world {world.get_path_name()}")
        descs = u.WorldPartitionBlueprintLibrary.get_actor_descs()
        external_root = "/Game/__ExternalActors__/JYU/Maps/" + target_name + "/"
        packages = [str(desc.get_editor_property("actor_package")) for desc in descs]
        if not packages or any(not package.startswith(external_root) for package in packages):
            raise RuntimeError(f"External actor packages were not isolated: {packages[:5]}")
        u.WorldPartitionBlueprintLibrary.load_actors([desc.get_editor_property("guid") for desc in descs])
        runtime = spawner()
        groups = list(property_value(runtime, "Groups", "groups"))
        details = {"target": target, "external_actor_count": len(packages),
                   "groups": [{"region": str(g.get_editor_property("region_id")),
                               "deer": g.get_editor_property("herbivores"),
                               "wolves": g.get_editor_property("wolves")} for g in groups]}
        result["maps"].append(details)
        runtime.modify()
        assign(runtime, "bUseV3Policy", "use_v3_policy", True)
        assign(runtime, "V3DeerPerRegion", "v3_deer_per_region", 8)
        assign(runtime, "bEnableEcosystemLife", "enable_ecosystem_life", True)
        assign(runtime, "bEnableWaves", "enable_waves", False)
        migration = property_value(runtime, "Migration", "migration")
        migration.set_editor_property("enabled", False)
        assign(runtime, "Migration", "migration", migration)
        if index == 1:
            assign(runtime, "FaunaSpecies", "fauna_species", profiles)
            forest = next(g for g in groups if str(g.get_editor_property("region_id")) == "Forest")
            anchor = forest.get_editor_property("herbivore_spawn_points")[0]
            placements = []
            for order, (kind, count) in enumerate(sorted(counts.items())):
                points = [anchor + u.Vector(-1400. + order * 460. + (i % 4) * 90.,
                                             -900. - (i // 4) * 120., 0.) for i in range(count)]
                placement = u.EcoFaunaPlacement()
                placement.set_editor_property("species_id", kind)
                placement.set_editor_property("spawn_points", points)
                placements.append(placement)
            forest.set_editor_property("fauna", placements)
            assign(runtime, "Groups", "groups", groups)
            details["added_fauna"] = counts
        assets.set_metadata_tag(world, "EcoAuditOwner", OWNER)
        assets.set_metadata_tag(world, "EcoAuditSource", SOURCE)
        if not u.EditorLevelLibrary.save_current_level():
            raise RuntimeError(f"Unable to save {target}")
    result["completed"] = True
except Exception:
    result["error"] = traceback.format_exc()
    u.log_error(result["error"])
finally:
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if not result["completed"]:
        raise RuntimeError("Integration R7e copy audit authoring failed")

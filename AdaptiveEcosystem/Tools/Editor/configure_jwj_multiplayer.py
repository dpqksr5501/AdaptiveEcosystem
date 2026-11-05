"""Configure the user-authorized JWJ map in place. Other maps and policy assets are read-only.
Run via -run=pythonscript -script=<this file>; add -EcoJWJApply to save.
"""
import json
import math
import shutil
from pathlib import Path
import unreal

MAP = "/Game/JWJ/Integration_JwJ"
MODE = "/Game/JWJ/Multiplayer/BP_JWJ_MultiplayerGameMode"
OWNER = "JWJ.Multiplayer.20261024"
apply = "-EcoJWJApply" in unreal.SystemLibrary.get_command_line()
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
assets = unreal.EditorAssetLibrary
root = Path(unreal.Paths.project_dir())
output = root / "Saved/Network20261024"
output.mkdir(parents=True, exist_ok=True)
if not levels.load_level(MAP):
    raise RuntimeError("Unable to load user-authorized JWJ map")
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
all_actors = actors.get_all_level_actors()
runtimes = [a for a in all_actors if isinstance(a, unreal.EcoCreatureIntegrationSpawner)]
starts = [a for a in all_actors if isinstance(a, unreal.PlayerStart)]
if len(runtimes) != 1 or not starts:
    raise RuntimeError("Expected one existing Creature coordinator and at least one PlayerStart")
runtime = runtimes[0]
flags = {key: str(runtime.get_editor_property(key)) for key in (
    "use_v3_policy", "herbivore_config", "wolf_config",
    "enable_waves", "enable_ecosystem_life", "use_habitat_streaming"
)}
settings = world.get_world_settings()
old_mode = settings.get_editor_property("default_game_mode")
report = {"map": MAP, "apply": apply, "previous_game_mode": str(old_mode),
          "coordinator": runtime.get_actor_label(), "preserved_runtime": flags,
          "existing_player_starts": len(starts), "new_player_starts": []}
report["policy_configs"] = {}
for field in ("herbivore_config", "wolf_config"):
    asset = runtime.get_editor_property(field)
    traits = asset.get_editor_property("config").get_editor_property("traits") if asset else []
    report["policy_configs"][field] = {"asset": asset.get_path_name() if asset else None, "traits": [
        {"type": trait.get_class().get_name(),
         "species_ai": trait.get_editor_property("use_species_ai"),
         "predator": trait.get_editor_property("predator")}
        for trait in traits if isinstance(trait, unreal.EcoCreatureNetworkTrait)]}
groups = list(runtime.get_editor_property("groups"))
regions = {str(a.get_editor_property("region_id")): a for a in all_actors if isinstance(a, unreal.EcologyRegion)}
def describe_group(group):
    return {"region": str(group.get_editor_property("region_id")),
            "herbivores": group.get_editor_property("herbivores"), "wolves": group.get_editor_property("wolves"),
            "deer_points": len(group.get_editor_property("herbivore_spawn_points")),
            "wolf_points": len(group.get_editor_property("wolf_spawn_points"))}
report["groups_before"] = [describe_group(g) for g in groups]

if apply:
    backup = output / "BeforeJWJMultiplayer"
    backup.mkdir(exist_ok=True)
    source_map = root / "Content/JWJ/Integration_JwJ.umap"
    if not (backup / source_map.name).exists():
        shutil.copy2(source_map, backup / source_map.name)
    bp = unreal.load_asset(MODE)
    if bp is None:
        factory = unreal.BlueprintFactory()
        factory.set_editor_property("parent_class", unreal.EcoCreatureIntegrationGameMode)
        bp = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            "BP_JWJ_MultiplayerGameMode", "/Game/JWJ/Multiplayer", unreal.Blueprint, factory)
    if bp is None:
        raise RuntimeError("Cannot create JWJ multiplayer GameMode")
    owner = str(assets.get_metadata_tag(bp, "JWJOwner"))
    if owner and owner != OWNER:
        raise RuntimeError("Existing GameMode belongs to another author")
    assets.set_metadata_tag(bp, "JWJOwner", OWNER)
    generated = unreal.BlueprintEditorLibrary.generated_class(bp)
    cdo = unreal.get_default_object(generated)
    original_class = old_mode or unreal.load_class(
        None, "/Game/ThirdPerson/Blueprints/BP_ThirdPersonGameMode.BP_ThirdPersonGameMode_C")
    if not original_class:
        raise RuntimeError("Cannot resolve original player/controller/HUD defaults")
    original = unreal.get_default_object(original_class)
    for field in ("default_pawn_class", "player_controller_class", "hud_class", "spectator_class"):
        value = original.get_editor_property(field)
        if value:
            cdo.set_editor_property(field, value)
    cdo.set_editor_property("game_session_class", unreal.EcoGameSession)
    unreal.BlueprintEditorLibrary.compile_blueprint(bp)
    if not assets.save_loaded_asset(bp, only_if_is_dirty=False):
        raise RuntimeError("GameMode save failed")
    settings.set_editor_property("default_game_mode", generated)
    origin = next((a for a in starts if OWNER not in [str(t) for t in a.tags]), starts[0])
    base = origin.get_actor_location()
    if not unreal.EcoJWJMultiplayerAuthoring.load_start_terrain(world, base):
        raise RuntimeError("Cannot load the authorized JWJ start terrain")

    # Repair incomplete authored arrays without changing counts, policies, food or existing points.
    report["completed_spawn_points"] = []
    for group in groups:
        region_id = str(group.get_editor_property("region_id"))
        region = regions[region_id]
        bounds = region.get_editor_property("region_bounds")
        extent = bounds.get_unscaled_box_extent()
        transform = bounds.get_world_transform()
        for field, required in (("herbivore_spawn_points", group.get_editor_property("herbivores")),
                                ("wolf_spawn_points", group.get_editor_property("wolves"))):
            points = list(group.get_editor_property(field))
            if not points or len(points) >= required:
                continue  # Empty arrays already have a supported ring fallback; preserve it.
            anchor = points[0]
            if not unreal.EcoJWJMultiplayerAuthoring.load_start_terrain(world, anchor):
                raise RuntimeError("Cannot load habitat ground")
            for candidate in range(160):
                angle = candidate * 2.399963
                radius = 180 + (candidate // 12) * 100
                hint = anchor + unreal.Vector(math.cos(angle) * radius, math.sin(angle) * radius, 0)
                result = unreal.EcoCreatureAnimationBuilder.project_placement_point(world, hint)
                point = next((p for p in result if isinstance(p, unreal.Vector)), None) if isinstance(result, tuple) else result
                success = not isinstance(result, tuple) or next((v for v in result if isinstance(v, bool)), False)
                if not success or not isinstance(point, unreal.Vector):
                    continue
                local = unreal.MathLibrary.inverse_transform_location(transform, point)
                if abs(local.x) > extent.x or abs(local.y) > extent.y or abs(local.z) > extent.z:
                    continue
                if any((point - previous).length() < 110 for previous in points):
                    continue
                points.append(point)
                report["completed_spawn_points"].append({"region": region_id, "field": field,
                                                         "position": {"x": point.x, "y": point.y, "z": point.z}})
                if len(points) >= required:
                    break
            if len(points) < required:
                raise RuntimeError("Not enough valid habitat ground: " + region_id)
            group.set_editor_property(field, points)
    runtime.set_editor_property("groups", groups)
    for i in range(10):
        label = "JWJ_Multiplayer_PlayerStart_" + str(i + 2).zfill(2)
        existing = next((a for a in starts if a.get_actor_label() == label and OWNER in [str(t) for t in a.tags]), None)
        if existing:
            continue
        x, y = base.x + (i % 4 - 1.5) * 220, base.y + (i // 4 + 1) * 220
        result = unreal.EcoCreatureAnimationBuilder.project_placement_point(
            world, unreal.Vector(x, y, base.z))
        point = result if isinstance(result, unreal.Vector) else next(
            (p for p in result if isinstance(p, unreal.Vector)), None) if isinstance(result, tuple) else None
        success = not isinstance(result, tuple) or next((v for v in result if isinstance(v, bool)), False)
        if not success or point is None:
            raise RuntimeError("Ground missing for " + label + "; level not saved")
        start = actors.spawn_actor_from_class(unreal.PlayerStart, point + unreal.Vector(0, 0, 110),
                                              origin.get_actor_rotation())
        start.set_actor_label(label)
        start.tags = [unreal.Name(OWNER)]
        start.set_editor_property("is_spatially_loaded", False)
        report["new_player_starts"].append({"label": label, "position": str(start.get_actor_location())})
    for key, previous in flags.items():
        if str(runtime.get_editor_property(key)) != previous:
            raise RuntimeError("Unexpected policy/runtime setting mutation: " + key)
    if not levels.save_current_level():
        raise RuntimeError("JWJ level save failed")
    report["game_mode"] = generated.get_path_name()
    report["total_player_starts"] = len([a for a in actors.get_all_level_actors() if isinstance(a, unreal.PlayerStart)])
    report["groups_after"] = [describe_group(g) for g in groups]

(output / ("JWJConfiguration.json" if apply else "JWJAudit.json")).write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
unreal.log("[EcoSession] JWJ_CONFIGURED " + json.dumps(report, ensure_ascii=False))

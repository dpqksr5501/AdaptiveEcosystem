"""Read-only inventory of the level author's World Partition integration map."""
import json
import os
import unreal

MAP = "/Game/Map/LV_Ecosystem_IntegrationTest"
levels = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
if not levels.get_current_level().get_outer().get_path_name().startswith(MAP + "."):
    if not levels.load_level(MAP):
        raise RuntimeError("Could not load integration map")
# UE 5.8 exposes loaded actors here; verify loaded/all counts in World Partition UI.
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors()
rows = []
for actor in actors:
    center, extent = actor.get_actor_bounds(False)
    row = {"label": actor.get_actor_label(), "name": actor.get_name(), "class": actor.get_class().get_path_name(),
           "position": [actor.get_actor_location().x, actor.get_actor_location().y, actor.get_actor_location().z], "rotation": str(actor.get_actor_rotation()),
           "center": [center.x, center.y, center.z], "extent": [extent.x, extent.y, extent.z],
           "tags": [str(t) for t in actor.tags], "folder": str(actor.get_folder_path())}
    for key in dir(actor):
        if any(word in key.lower() for word in ("region", "weather", "shelter", "auto_cycle", "day_night")):
            try:
                value = actor.get_editor_property(key)
                row[key] = str(value)
            except Exception:
                pass
    rows.append(row)
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
report = {"map": MAP, "world": world.get_path_name(), "actors": rows,
          "game_mode": str(world.get_world_settings().get_editor_property("default_game_mode"))}
path = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "EcosystemLevelAudit.json")
with open(path, "w", encoding="utf-8") as stream:
    json.dump(report, stream, ensure_ascii=False, indent=2)
unreal.log("ECOSYSTEM_LEVEL_AUDIT_OK actors=" + str(len(rows)) + " report=" + path)

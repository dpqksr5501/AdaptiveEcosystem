"""Sample the existing island in PIE and optionally round-trip its experience checkpoint."""

from collections import Counter
import json
from pathlib import Path
import re
import runpy
import time
import traceback

import unreal as u


MAP = "/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed"
editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
inspect = u.EcoCreatureInspectionLibrary
command = u.SystemLibrary.get_command_line()
config = re.search(r"-EcoFaunaExperience=([012])\b", command)
mode = int(config[1]) if config else 0
visit_config = re.search(r"-EcoFaunaFoodVisits=([012])\b", command)
visit_mode = int(visit_config[1]) if visit_config else None
interaction_config = re.search(r"-EcoFaunaInteractions=([012])\b", command)
interaction_mode = int(interaction_config[1]) if interaction_config else None
match = re.search(r"-EcoExperienceAudit=(Observe|Save|Load)\b", command)
action = match[1] if match else "Observe"
slot_match = re.search(r"-EcoExperienceSlot=([A-Za-z0-9_]{1,24})\b", command)
slot = slot_match[1] if slot_match else "IslandExperienceAudit"
duration_arg = re.search(r"-EcoExperienceSeconds=(\d{2,3})\b", command)
duration = int(duration_arg[1]) if duration_arg else 65
out = Path(u.Paths.project_saved_dir()).resolve() / "FaunaExperienceAudit"
report = {"mode": mode, "action": action, "slot": slot, "duration": duration,
          "coverage": {}, "outcome_coverage": {}, "development_coverage": {}, "interspecies_coverage": {},
          "food_visit_mode": visit_mode, "food_visit_coverage": {},
          "interaction_mode": interaction_mode, "interaction_coverage": {}, "errors": []}
started = time.monotonic()
first_time = None
callback = None
last_save_attempt = -1.0
next_sample = 0.0
interaction_events = set()
interaction_reasons = {
    "FaunaAlarmEmitted", "FaunaAlarmHeard", "FaunaWaterThreatSeen", "FaunaEscapeSeen",
    "FaunaRespondedToCue", "FaunaCueConfirmed", "FaunaDefenseOpportunity",
    "FaunaAttackIntercepted", "FaunaDefenseIntercepted", "FaunaMealResumedAfterCue",
    "FaunaProtectionNeighbor", "FaunaCarrionProvision",
}


def snapshot(world):
    species, kinds, outcomes = Counter(), Counter(), Counter()
    remembered, development, shapes, interspecies, food_visits = {}, {}, {}, {}, {}
    for agent_id in inspect.get_authority_agent_ids(world):
        value = inspect.capture_agent(world, agent_id)
        raw = next((item for item in value if isinstance(item, str)), "") if isinstance(value, tuple) else value
        if not raw:
            continue
        data = json.loads(raw)
        species[data["species"]] += 1
        for event in data.get("gameplay_reason_history", ()):
            if event["reason"] in interaction_reasons:
                interaction_events.add((data["species"], agent_id, event["reason"], event["time"]))
        entries = data.get("experience", [])
        encounters = data.get("interspecies", [])
        if encounters:
            interspecies[str(agent_id)] = {"species": data["species"], "entries": encounters}
        if data.get("food_visits"):
            food_visits[str(agent_id)] = {"species": data["species"], "entries": data["food_visits"]}
        if "development" in data:
            development[str(agent_id)] = {"species": data["species"], **data["development"]}
        shapes[str(agent_id)] = data.get("body_condition", 1)
        if entries:
            remembered[str(agent_id)] = {"species": data["species"], "entries": entries}
            kinds.update(entry["activity"] for entry in entries)
            outcomes.update(entry["last_outcome"] for entry in entries if "last_outcome" in entry)
    return {"species": dict(species), "activity_counts": dict(kinds), "latest_outcome_counts": dict(outcomes),
            "memory": remembered, "development": development, "shapes": shapes, "interspecies": interspecies,
            "food_visits": food_visits}


def finish():
    for species, _, reason, _ in sorted(interaction_events):
        counts = report["interaction_coverage"].setdefault(species, {})
        counts[reason] = counts.get(reason, 0) + 1
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{slot}_{mode}_{action}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if callback is not None:
        u.unregister_slate_post_tick_callback(callback)
    levels.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def tick(_delta):
    global first_time, last_save_attempt, next_sample
    try:
        if time.monotonic() - started > max(140, duration + 90):
            raise RuntimeError("Island experience audit timed out")
        world = editor.get_game_world()
        if not world:
            return
        runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
        if not runtime or not inspect.get_authority_agent_ids(world):
            return
        now = u.GameplayStatics.get_time_seconds(world)
        if first_time is None:
            first_time = now
            report["food_visit_mode"] = runtime.get_editor_property("fauna_food_visit_mode")
            report["interaction_mode"] = runtime.get_editor_property("fauna_interaction_mode")
            if visit_mode is not None and report["food_visit_mode"] != visit_mode:
                raise RuntimeError("Food visit override was not applied")
            if interaction_mode is not None and report["interaction_mode"] != interaction_mode:
                raise RuntimeError("Fauna interaction override was not applied")
            if interaction_mode is not None:
                u.SystemLibrary.execute_console_command(world, "eco.Inspection.GameplayReasons 1")
            report["initial"] = snapshot(world)
            if len(report["initial"]["species"]) != 16:
                raise RuntimeError("Expected all 16 authored island species")
            if "-EcoAuditGameplayCues" in command:
                registry = u.AssetRegistryHelpers.get_asset_registry()
                registry.wait_for_completion()
                cue_classes = [u.TopLevelAssetPath("/Script/GameplayAbilities", name)
                               for name in ("GameplayCueNotify_Actor", "GameplayCueNotify_Static")]
                cues = registry.get_derived_class_names(cue_classes, set())
                report["gameplay_cue_classes"] = sorted(str(cue.package_name) for cue in cues
                                                        if str(cue.package_name).startswith("/Game/"))
                if any(not path.startswith("/Game/GameplayCues/") for path in report["gameplay_cue_classes"]):
                    raise RuntimeError("Existing project GameplayCue assets are outside the configured search path")
        if action == "Load":
            if now < first_time + 1.0:
                return
            saved = json.loads((out / f"{slot}_{mode}_Save.json").read_text(encoding="utf-8"))
            if saved["errors"] or not runtime.load_ecosystem(slot):
                raise RuntimeError("Experience checkpoint could not be restored")
            report["restored"] = snapshot(world)
            if report["restored"]["memory"] != saved["final"]["memory"]:
                raise RuntimeError("Restored experience differs from saved experience")
            if report["restored"]["development"] != saved["final"]["development"]:
                raise RuntimeError("Restored development differs from saved development")
            if report["restored"]["interspecies"] != saved["final"]["interspecies"]:
                raise RuntimeError("Restored interspecies experience differs from saved experience")
            if report["restored"]["food_visits"] != saved["final"]["food_visits"]:
                raise RuntimeError("Restored food visits differ from saved visits")
            if report["restored"]["shapes"] != saved["final"]["shapes"]:
                raise RuntimeError("Restored presentation differs from saved body condition")
            finish()
            return
        if now >= next_sample:
            next_sample = now + (2.0 if report["interaction_mode"] else 15.0)
            sample = snapshot(world)
            for entry in sample["food_visits"].values():
                species = entry["species"]
                previous = report["food_visit_coverage"].get(species, [])
                report["food_visit_coverage"][species] = sorted(set(previous) |
                    {f"{row['kind']}/{row['medium']}" for row in entry["entries"]})
            for entry in sample["interspecies"].values():
                seen = set(report["interspecies_coverage"].get(entry["species"], []))
                seen.update(f"{row['kind']}/{row['medium']}/{row['other_species']}" for row in entry["entries"])
                report["interspecies_coverage"][entry["species"]] = sorted(seen)
            for entry in sample["memory"].values():
                seen = set(report["coverage"].get(entry["species"], []))
                seen.update(site["activity"] for site in entry["entries"])
                report["coverage"][entry["species"]] = sorted(seen)
                outcomes = set(report["outcome_coverage"].get(entry["species"], []))
                outcomes.update(site["last_outcome"] for site in entry["entries"] if "last_outcome" in site)
                report["outcome_coverage"][entry["species"]] = sorted(outcomes)
            for key, entry in sample["development"].items():
                seen = set(report["development_coverage"].get(entry["species"], []))
                if entry["condition"] != 0:
                    seen.add("BodyCondition")
                if sample["shapes"][key] != 1:
                    seen.add("VisibleBodyCondition")
                if entry["exploration_at"] >= 0:
                    seen.add("Exploration")
                if entry["partners"]:
                    seen.add("Relationships")
                if entry.get("last_social_at", -1) >= 0:
                    seen.add("ReciprocalExchange")
                report["development_coverage"][entry["species"]] = sorted(seen)
        if now < first_time + duration:
            return
        if action == "Save":
            if last_save_attempt >= 0 and now < last_save_attempt + 1.0:
                return
            last_save_attempt = now
            if not runtime.save_ecosystem(slot):
                return
        report["final"] = snapshot(world)
        if bool(report["final"]["memory"]) != (mode > 0):
            raise RuntimeError("Observed experience does not match selected mode")
        if mode == 0 and report["final"]["interspecies"]:
            raise RuntimeError("Interspecies outcomes were recorded in mode 0")
        if bool(report["final"]["food_visits"]) != (report["food_visit_mode"] > 0):
            raise RuntimeError("Completed food visits do not match the selected visit mode")
        if "-EcoEncounterAudit" in command and mode > 0 and not report["final"]["interspecies"]:
            raise RuntimeError("Expected interspecies samples in the island snapshot")
        if report["interaction_mode"] == 0 and interaction_events:
            raise RuntimeError("Fauna interaction events were recorded in mode 0")
        if report["interaction_mode"] == 1 and any(reason in {
            "FaunaRespondedToCue", "FaunaAttackIntercepted", "FaunaMealResumedAfterCue"
        } for _, _, reason, _ in interaction_events):
            raise RuntimeError("Fauna interactions changed behavior in observe mode")
        if mode < 2 and any(value != 1 for value in report["final"]["shapes"].values()):
            raise RuntimeError("Body condition was applied outside apply mode")
        if mode == 2 and any("BodyCondition" not in report["development_coverage"].get(species, [])
                             for species in report["initial"]["species"]):
            raise RuntimeError("Expected observed nutritional development in every island species")
        finish()
    except Exception:
        report["errors"].append(traceback.format_exc())
        u.log_error(report["errors"][-1])
        finish()


try:
    if editor.get_editor_world().get_name() != MAP.rsplit("/", 1)[-1]:
        raise RuntimeError(f"Open {MAP} before starting the audit")
    if "-EcoPreviewIslandFoodVisitLayout" in command.split():
        author = runpy.run_path(str(Path(__file__).with_name("author_jyu_island_fauna.py")))
        report["preview_food_visit_layout"] = author["apply_food_visit_layout"](
            editor.get_editor_world(), author["common"]["runtime"]())
    levels.editor_request_begin_play()
    callback = u.register_slate_post_tick_callback(tick)
except Exception:
    report["errors"].append(traceback.format_exc())
    u.log_error(report["errors"][-1])
    finish()

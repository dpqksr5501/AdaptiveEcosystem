"""Headless long-run measurement on the configured map, with optional transient deer-only setup."""
import json
from pathlib import Path
import re
import time
import traceback
import unreal as u

command = u.SystemLibrary.get_command_line()
name = re.search(r"-DeerAuditRun=(\w+)", command).group(1)
duration = int(re.search(r"-DeerAuditSeconds=(\d+)", command).group(1))
mode = re.search(r"-DeerAuditMode=(\w+)", command).group(1)
out = Path(u.Paths.project_saved_dir()).resolve() / "ProjectAudit_20261112" / f"{name}.json"
state = {"name": name, "mode": mode, "target_seconds": duration, "samples": [], "completed": False}
started = time.monotonic()
configured = False
origin = None
next_sample = 0.
track_intake = "-DeerAuditTrackIntake" in command
legacy_feed = "-DeerAuditLegacyFeed" in command
native = None
previous_step = 0
last_legacy_dump = -1.
deer_ids = set()
previous_alive = set()
species_by_id = {}
intake = {"total": 0., "steps_captured": 0, "missed_steps": 0, "by_region": {},
          "brain_ids": [], "other_writers": {}, "capture_errors": 0}
brains = set()
other_writers = {}


def capture_agent(world, agent):
    raw = u.EcoCreatureInspectionLibrary.capture_agent(world, agent)
    if isinstance(raw, tuple):
        raw = next((item for item in raw if isinstance(item, str)), "")
    return json.loads(raw) if raw else None


def record_intake(world):
    global native, previous_step, previous_alive
    if native is None:
        native = next((obj for obj in u.ObjectIterator(u.EcoPolicyV3IntegratedSubsystem)
                       if obj.get_outer() == world), None)
        if native is None:
            return
    step = int(json.loads(native.capture_step_performance())["native_steps_total"])
    if step <= previous_step:
        return
    intake["missed_steps"] += step - previous_step - 1
    previous_step = step
    intake["steps_captured"] += 1
    living = set(u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world))
    for agent in sorted((living - species_by_id.keys()) | (deer_ids & (living | previous_alive))):
        row = capture_agent(world, agent)
        if row is None:
            intake["capture_errors"] += 1
            continue
        kind = row["species"]
        species_by_id[agent] = kind
        if kind != "Herbivore":
            other_writers.setdefault(kind, set()).add(row.get("movement", "unreported"))
            continue
        deer_ids.add(agent)
        brains.add(row.get("brain", "unreported"))
        if agent in living and row.get("hp", 0) > 0:
            amount = row.get("last_intake", 0.)
            region = row.get("region", "unknown")
            intake["total"] += amount
            intake["by_region"][region] = intake["by_region"].get(region, 0.) + amount
    previous_alive = living


def write():
    temporary = out.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    for attempt in range(8):
        try:
            temporary.replace(out)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(.025 * (attempt + 1))


def tick(_):
    global configured, origin, next_sample, last_legacy_dump
    world = None
    try:
        world = next((world for world in u.ObjectIterator(u.World)
                      if u.GameplayStatics.get_game_state(world)
                      and u.GameplayStatics.get_player_controller(world, 0)), None)
        if world is None:
            if time.monotonic() - started > 90:
                raise RuntimeError("No standalone game world")
            return True
        spawner = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
        if not spawner:
            if time.monotonic() - started > 90:
                raise RuntimeError("No integration spawner")
            return True
        ready = spawner.is_runtime_ready()
        if not configured:
            if mode == "deer_only":
                if ready:
                    raise RuntimeError("Authority initialized before the deer-only setup")
                spawner.set_editor_property("EnabledSpecies", u.EcoEnabledSpecies.DEER_ONLY)
                if spawner.get_editor_property("FaunaSpecies"):
                    raise RuntimeError("Deer-only fixture requires an empty rule-fauna roster")
            configured = True
            state["map"] = world.get_path_name()
            state["configuration"] = {}
            for key in ("EnabledSpecies", "bUseV3Policy", "bEnableEcosystemLife", "bEnableWaves",
                        "bEnableHerdJourneys", "GlobalPopulationLimit"):
                try:
                    state["configuration"][key] = str(spawner.get_editor_property(key))
                except Exception as exc:
                    state["configuration"][key] = str(exc)
            write()
        now = u.GameplayStatics.get_time_seconds(world)
        if not ready:
            if origin is not None or now > 35.:
                raise RuntimeError("Authority not ready or stopped")
            return True
        if origin is None:
            u.GameplayStatics.set_global_time_dilation(world, 4.)
            state["dilation"] = u.GameplayStatics.get_global_time_dilation(world)
            origin = now
        elapsed = now - origin
        if track_intake:
            record_intake(world)
        if legacy_feed and elapsed - last_legacy_dump >= 1.:
            u.SystemLibrary.execute_console_command(world, "eco.Integration.Dump details")
            last_legacy_dump = elapsed
        if elapsed >= next_sample or elapsed >= duration:
            summary = u.GameplayStatics.get_game_state(world).get_ecology_summary()
            species = {}
            regional_species = {}
            for row in summary.get_editor_property("species"):
                kind = str(row.get_editor_property("species_id"))
                region = str(row.get_editor_property("region_id"))
                counts = {key: row.get_editor_property(key) for key in ("population", "births", "deaths")}
                regional_species.setdefault(region, {})[kind] = counts
                totals = species.setdefault(kind, dict.fromkeys(counts, 0))
                for key, value in counts.items():
                    totals[key] += value
            regions = {str(row.get_editor_property("region_id")): {
                key: row.get_editor_property(key) for key in ("population", "food_amount")
            } for row in summary.get_editor_property("regions")}
            if not species or not regions:
                return True
            visible_deer = {}
            for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor):
                visual = actor.get_editor_property("visual_state")
                if not actor.get_editor_property("bound") or not visual.get_editor_property("alive"):
                    continue
                if str(visual.get_editor_property("species_id")) != "Herbivore":
                    continue
                visible_deer[int(visual.get_editor_property("stable_agent_id"))] = [
                    round(visual.get_editor_property("normalized_energy"), 4),
                    round(visual.get_editor_property("maturity"), 4),
                ]
            state["samples"].append({
                "seconds": round(elapsed, 3), "step": summary.get_editor_property("step_id"),
                "species": species, "regions": regions, "regional_species": regional_species,
                "visible_deer": visible_deer,
                "authority_ids": sorted(u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)),
            })
            while next_sample <= elapsed:
                next_sample += 30.
            state["completed"] = elapsed >= duration
            if track_intake:
                intake["brain_ids"] = sorted(brains)
                intake["other_writers"] = {key: sorted(values) for key, values in other_writers.items()}
                state["native_deer_intake"] = intake
            write()
        if state["completed"]:
            u.log(f"DEER_LONG_AUDIT Complete {name} {elapsed:.2f} game seconds")
            u.SystemLibrary.execute_console_command(world, "QUIT")
            return False
        return True
    except Exception:
        state["error"] = traceback.format_exc()
        write()
        u.log_error(state["error"])
        if world:
            u.SystemLibrary.execute_console_command(world, "QUIT")
        else:
            u.SystemLibrary.quit_editor()
        return False


handle = u.register_ticker_callback(tick, 0.)

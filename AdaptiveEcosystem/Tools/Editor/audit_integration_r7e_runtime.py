"""Headless long-run measurement and transient configuration comparisons on owned maps."""
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
speed_match = re.search(r"-DeerAuditDilation=(1|4)\b", command)
dilation = float(speed_match.group(1)) if speed_match else 4.
out = Path(u.Paths.project_saved_dir()).resolve() / "ProjectAudit_20261112" / f"{name}.json"
state = {"name": name, "mode": mode, "target_seconds": duration, "samples": [], "completed": False}
started = time.monotonic()
configured = False
origin = None
next_sample = 0.
track_intake = "-DeerAuditTrackIntake" in command
track_reasons = "-DeerAuditTrackReasons" in command
probe_seams = "-DeerAuditProbeSeams" in command
legacy_feed = "-DeerAuditLegacyFeed" in command
native = None
previous_step = 0
last_legacy_dump = -1.
deer_ids = set()
wolf_ids = set()
wolf_meat = {}
previous_alive = set()
species_by_id = {}
intake = {"total": 0., "steps_captured": 0, "missed_steps": 0, "by_region": {},
          "brain_ids": [], "other_writers": {}, "capture_errors": 0}
brains = set()
other_writers = {}
reason_totals = {}
reason_windows = {}
next_reason_sample = 0.


def capture_agent(world, agent):
    raw = u.EcoCreatureInspectionLibrary.capture_agent(world, agent)
    if isinstance(raw, tuple):
        raw = next((item for item in raw if isinstance(item, str)), "")
    return json.loads(raw) if raw else None


def sample_region_seams(world, regions):
    """Read terrain near adjacent AABB faces. Passage movement still needs a swept test."""
    samples = []
    for source in regions:
        for target in regions:
            if target["id"] <= source["id"] or not (
                target["id"] in source["adjacent"] or source["id"] in target["adjacent"]
            ):
                continue
            for axis, along in ((0, 1), (1, 0)):
                center_a, center_b = source["center_cm"], target["center_cm"]
                extent_a, extent_b = source["extent_cm"], target["extent_cm"]
                side = 1 if center_b[axis] >= center_a[axis] else -1
                face_a = center_a[axis] + side * extent_a[axis]
                face_b = center_b[axis] - side * extent_b[axis]
                if abs(face_a - face_b) > 10.:
                    continue
                low = max(center_a[along] - extent_a[along], center_b[along] - extent_b[along])
                high = min(center_a[along] + extent_a[along], center_b[along] + extent_b[along])
                if high <= low:
                    continue
                row = {"from": source["id"], "to": target["id"], "axis": axis,
                       "face_cm": face_a, "tested": 0, "grounded_pairs": 0, "examples": []}
                for index in range(1, 151):
                    at = low + index * (high - low) / 151.
                    endpoints = []
                    row["tested"] += 1
                    for cross in (face_a - side * 10., face_b + side * 10.):
                        xy = (cross, at) if axis == 0 else (at, cross)
                        hit = u.EcoCreatureAnimationBuilder.project_placement_point(world, u.Vector(*xy, center_a[2]))
                        if isinstance(hit, tuple):
                            hit = None if any(isinstance(v, bool) and not v for v in hit) else next(
                                (v for v in hit if isinstance(v, u.Vector)), None)
                        if not isinstance(hit, u.Vector):
                            break
                        endpoints.append([hit.x, hit.y, hit.z])
                    if len(endpoints) == 2:
                        row["grounded_pairs"] += 1
                        if len(row["examples"]) < 12:
                            row["examples"].append(endpoints)
                samples.append(row)
    return samples


def configure_food_comparison(world, spawner, with_patches):
    if world.get_name() != "LV_JYU_IntegrationR7eFauna":
        raise RuntimeError("Food comparison requires the owned integration fauna copy")
    if not spawner.get_editor_property("FaunaSpecies") or spawner.get_editor_property("FaunaHabitatPatches"):
        raise RuntimeError("Food comparison requires the original mixed roster and no authored patches")
    forest = next(group for group in spawner.get_editor_property("Groups")
                  if str(group.get_editor_property("RegionId")) == "Forest")
    anchor = forest.get_editor_property("HerbivoreSpawnPoints")[0]
    patches, placements = [], []
    if with_patches:
        # Identical map coordinates for all seeds. No animal positions, outcomes or learned scores enter placement.
        for column, dx in enumerate((-1200., 0., 1200.)):
            for row, dy in enumerate((-1650., -750., 150.)):
                ground = u.EcoCreatureAnimationBuilder.project_placement_point(world, anchor + u.Vector(dx, dy, 0.))
                if isinstance(ground, tuple):
                    if any(isinstance(value, bool) and not value for value in ground):
                        continue
                    ground = next((value for value in ground if isinstance(value, u.Vector)), None)
                if not isinstance(ground, u.Vector):
                    continue
                name = f"AuditForage_{column}_{row}"
                patch = u.EcoFaunaHabitatPatch()
                consumers = ["Fox", "Crow", "Pig"] + (["Rat"] if (column + row) % 2 else [])
                for key, value in dict(Id=name, RegionId="Forest", Center=ground, Stage=2, Consumers=consumers,
                                       Capacity=24., RegrowthPerSecond=.44, EnergyPerMeal=4.).items():
                    patch.set_editor_property(key, value)
                patches.append(patch)
                placements.append({"id": name, "position_cm": [ground.x, ground.y, ground.z], "consumers": consumers})
        if not patches:
            raise RuntimeError("Food comparison found no projected ground")
    # The stage gates some behaviors, so both conditions must run the same stage.
    spawner.set_editor_property("FaunaHabitatStage", 2)
    spawner.set_editor_property("FaunaHabitatPatches", patches)
    state["food_comparison"] = {"stage": 2, "patches": placements}


def record_reasons(world):
    living = set(u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world))
    for agent in sorted(living | reason_windows.keys()):
        row = capture_agent(world, agent)
        if not row:
            reason_windows.pop(agent, None)
            continue
        previous = reason_windows.get(agent, set())
        current = {
            (event["time"], event["region"], event["reason"], event["related_id"], event["amount"])
            for event in row.get("gameplay_reason_history", [])
        }
        if current:
            reason_windows[agent] = current
        if current - previous:
            totals = reason_totals.setdefault(row["species"], {})
            for _, _, reason, _, _ in current - previous:
                totals[reason] = totals.get(reason, 0) + 1


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
    for agent in sorted((living - species_by_id.keys()) | ((deer_ids | wolf_ids) & (living | previous_alive))):
        row = capture_agent(world, agent)
        if row is None:
            intake["capture_errors"] += 1
            continue
        kind = row["species"]
        species_by_id[agent] = kind
        if kind == "Wolf":
            wolf_ids.add(agent)
            life = row.get("life")
            if life:
                totals = wolf_meat.setdefault(agent, {})
                for key in ("meat_issued", "meat_consumed", "meat_wasted"):
                    totals[key] = max(totals.get(key, 0.), life.get(key, 0.))
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
    global configured, origin, next_sample, last_legacy_dump, next_reason_sample
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
            elif mode in ("food_control", "food_patches"):
                if ready:
                    raise RuntimeError("Authority initialized before the food comparison setup")
                configure_food_comparison(world, spawner, mode == "food_patches")
            configured = True
            state["map"] = world.get_path_name()
            state["configuration"] = {}
            for key in ("EnabledSpecies", "bUseV3Policy", "bEnableEcosystemLife", "bEnableWaves",
                        "bEnableHerdJourneys", "GlobalPopulationLimit", "FaunaHabitatStage"):
                try:
                    state["configuration"][key] = str(spawner.get_editor_property(key))
                except Exception as exc:
                    state["configuration"][key] = str(exc)
            if track_reasons:
                try:
                    state["fauna_profiles"] = [{
                        "species": str(profile.get_editor_property("SpeciesId")),
                        "diet": str(profile.get_editor_property("Diet")),
                        "maintenance": profile.get_editor_property("Maintenance"),
                        "prey": [str(rule.get_editor_property("SpeciesId"))
                                 for rule in profile.get_editor_property("PreyRules")],
                        "sight_cm": profile.get_editor_property("SightRange"),
                        "scent_cm": profile.get_editor_property("ScentRange"),
                        "carrion_scent_limit_cm": profile.get_editor_property("HabitatCarrionRange"),
                    } for profile in spawner.get_editor_property("FaunaSpecies")]
                except Exception as exc:
                    state["fauna_profiles_error"] = str(exc)
            write()
        now = u.GameplayStatics.get_time_seconds(world)
        if not ready:
            if origin is not None or now > 35.:
                raise RuntimeError("Authority not ready or stopped")
            return True
        if origin is None:
            if track_reasons:
                u.SystemLibrary.execute_console_command(world, "eco.Inspection.GameplayReasons 1")
                state["sampled_gameplay_reasons"] = reason_totals
                try:
                    state["region_geometry"] = []
                    for region in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion):
                        center, extent = region.get_actor_bounds(False)
                        state["region_geometry"].append({
                            "id": str(region.get_editor_property("RegionId")),
                            "adjacent": [str(key) for key in region.get_editor_property("AdjacentRegionIds")],
                            "center_cm": [center.x, center.y, center.z],
                            "extent_cm": [extent.x, extent.y, extent.z],
                        })
                    state["authored_passages"] = [{
                        "from": str(route.get_editor_property("FromRegion")),
                        "to": str(route.get_editor_property("ToRegion")),
                        "enabled": route.get_editor_property("bEnabled"),
                        "rule_fauna": route.get_editor_property("bAllowRuleFaunaPassage"),
                        "shares_habitat_reports": route.get_editor_property("bSharesHabitatReports"),
                        "waypoints": len(route.get_editor_property("Points")),
                    } for route in u.GameplayStatics.get_all_actors_of_class(world, u.EcoHerdMigrationRoute)]
                except Exception as exc:
                    state["region_geometry_error"] = str(exc)
                if probe_seams and "region_geometry_error" not in state:
                    try:
                        state["region_seam_samples"] = sample_region_seams(world, state["region_geometry"])
                    except Exception as exc:
                        state["region_seam_error"] = str(exc)
            u.GameplayStatics.set_global_time_dilation(world, dilation)
            state["dilation"] = u.GameplayStatics.get_global_time_dilation(world)
            origin = now
        elapsed = now - origin
        if track_intake:
            record_intake(world)
        if track_reasons and elapsed >= next_reason_sample:
            record_reasons(world)
            next_reason_sample = elapsed + 1.
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
            if state["completed"]:
                u.SystemLibrary.execute_console_command(world, "eco.Integration.Dump")
            if track_intake:
                intake["brain_ids"] = sorted(brains)
                intake["other_writers"] = {key: sorted(values) for key, values in other_writers.items()}
                state["native_deer_intake"] = intake
                state["sampled_native_wolf_meat"] = {
                    key: sum(totals.get(key, 0.) for totals in wolf_meat.values())
                    for key in ("meat_issued", "meat_consumed", "meat_wasted")
                }
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

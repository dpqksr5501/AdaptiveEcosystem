"""Unsaved PIE fixture on the owned integration copy. Exercises an actual ground seam."""
import json
from pathlib import Path
import re
import runpy
import time
import traceback

import unreal as u


MAP = "/Game/JYU/Maps/LV_JYU_IntegrationR7eFauna"
OWNER = "JYU.IntegrationR7eAudit"
editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
actors = u.get_editor_subsystem(u.EditorActorSubsystem)
world = editor.get_editor_world()
if not world or world.get_path_name().split(".")[0] != MAP:
    raise RuntimeError("Open the owned integration copy before running the fixture")
if u.EditorAssetLibrary.get_metadata_tag(world, "EcoAuditOwner") != OWNER:
    raise RuntimeError("The map does not have the owned audit marker")

run = re.search(r"-DeerAuditPassageName=(\w+)", u.SystemLibrary.get_command_line())
name = run.group(1) if run else "Continuation_PassagePIE"
waypoint_fixture = "-DeerAuditPassageApproach" in u.SystemLibrary.get_command_line()
horse_fixture = "-EcoExpandedHorsePassage" in u.SystemLibrary.get_command_line()
patch_fixture = horse_fixture or "-DeerAuditPassagePatch" in u.SystemLibrary.get_command_line()
species = "Horse" if horse_fixture else "Fox"
out = Path(u.Paths.project_saved_dir()).resolve() / "ProjectAudit_20261112" / (name + ".json")
state = {"completed": False, "samples": [], "species": species, "fixture": (
    f"Unsaved PIE, one {species} and a temporary food patch at a measured ground seam"
    if patch_fixture else "Unsaved PIE, same roster, one fox and two rats placed at a measured ground seam"
)}


def ground(x, y):
    hit = u.EcoCreatureAnimationBuilder.project_placement_point(world, u.Vector(x, y, 3000.))
    if isinstance(hit, tuple):
        if any(isinstance(value, bool) and not value for value in hit):
            return None
        hit = next((value for value in hit if isinstance(value, u.Vector)), None)
    return hit if isinstance(hit, u.Vector) else None


def xyz(point):
    return [point.x, point.y, point.z]


def setup():
    descs = u.WorldPartitionBlueprintLibrary.get_actor_descs()
    u.WorldPartitionBlueprintLibrary.load_actors([row.get_editor_property("guid") for row in descs])
    spawner, = (actor for actor in actors.get_all_level_actors() if isinstance(actor, u.EcoCreatureIntegrationSpawner))
    groups = list(spawner.get_editor_property("Groups"))
    by_id = {str(group.get_editor_property("RegionId")): group for group in groups}
    origin, destination = by_id["Barren"], by_id["Forest"]
    if horse_fixture:
        spawner.set_editor_property("GlobalPopulationLimit", 84)
        author = runpy.run_path(str(Path(__file__).with_name("setup_jyu_expanded_fauna.py")))
        visual = u.load_class(None, "/Game/JYU/ExpandedFauna/Horse/BP_Horse.BP_Horse_C")
        if not visual:
            raise RuntimeError("Author the expanded horse representation before this test")
        profile = author["configure_species"]("Horse", visual)
        profile.set_editor_property("maintenance", .65)
        profiles = [p for p in spawner.get_editor_property("FaunaSpecies")
                    if str(p.get_editor_property("SpeciesId")) != species]
        spawner.set_editor_property("FaunaSpecies", [*profiles, profile])
    for x in (32000., 32500., 31500., 33000., 31000., 33500.):
        start_y = 22200. if waypoint_fixture else 24500.
        points = [ground(x + dx, y) for dx, y in (
            (0., 24990.), (0., 25010.), (0., start_y), (0., 25320.), (120., 25450.)
        )]
        approach = [ground(x, y) for y in (22800., 23500., 24200.)] if waypoint_fixture else []
        if all(points) and all(approach) and abs(points[0].z - points[1].z) <= 10. and (
            waypoint_fixture or abs(points[0].z - points[2].z) <= 180.
        ):
            break
    else:
        raise RuntimeError("No available loaded ground near the seam")
    entry, exit, fox_start, rat_start_a, rat_start_b = points
    placements = list(destination.get_editor_property("Fauna"))
    fox = next(p for p in placements if str(p.get_editor_property("SpeciesId")) == "Fox")
    rat = next(p for p in placements if str(p.get_editor_property("SpeciesId")) == "Rat")
    fox_points = list(fox.get_editor_property("SpawnPoints"))
    rat_points = list(rat.get_editor_property("SpawnPoints"))
    if len(fox_points) < 2 or len(rat_points) < 2 or origin.get_editor_property("Fauna"):
        raise RuntimeError("Expected the original audit roster")
    if not horse_fixture:
        fox.set_editor_property("SpawnPoints", fox_points[1:])
    if patch_fixture:
        patch = u.EcoFaunaHabitatPatch()
        for key, value in dict(Id="PassageAuditInsects", RegionId="Forest", Center=rat_start_a, Stage=2,
                               Consumers=[species] if horse_fixture else ["Fox", "Crow", "Pig"],
                               Capacity=24., RegrowthPerSecond=.44,
                               EnergyPerMeal=4.).items():
            patch.set_editor_property(key, value)
        spawner.set_editor_property("FaunaHabitatStage", 2)
        spawner.set_editor_property("FaunaHabitatPatches", [patch])
        state["patch_center"] = xyz(rat_start_a)
    else:
        rat.set_editor_property("SpawnPoints", [rat_start_a, rat_start_b, *rat_points[2:]])
    destination.set_editor_property("Fauna", placements)
    emigrant = u.EcoFaunaPlacement()
    emigrant.set_editor_property("SpeciesId", species)
    emigrant.set_editor_property("SpawnPoints", [fox_start])
    origin.set_editor_property("Fauna", [emigrant])
    spawner.set_editor_property("Groups", groups)
    route = actors.spawn_actor_from_class(u.EcoHerdMigrationRoute, entry)
    if not route:
        raise RuntimeError("Could not create the unsaved route")
    route.set_editor_property("FromRegion", "Barren")
    route.set_editor_property("ToRegion", "Forest")
    route.set_editor_property("Points", [*approach, entry, exit])
    route.set_editor_property("bAllowRuleFaunaPassage", True)
    route.set_editor_property("bSharesHabitatReports", True)
    state["entry"], state["exit"] = xyz(entry), xyz(exit)
    state["fox_start"] = xyz(fox_start)
    state["approach"] = [xyz(point) for point in approach]


def inspect(game, key):
    raw = u.EcoCreatureInspectionLibrary.capture_agent(game, key)
    if isinstance(raw, tuple):
        raw = next((value for value in raw if isinstance(value, str)), "")
    return json.loads(raw) if raw else {}


def finish(error=None):
    if error:
        state["error"] = error
    state["completed"] = not error
    out.write_text(json.dumps(state, indent=2), encoding="utf-8")
    if error:
        u.log_error(error)
    levels.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def tick(_):
    try:
        if time.monotonic() > state["deadline"]:
            raise RuntimeError("Timed out waiting for the physical passage")
        game = editor.get_game_world()
        if not game:
            return
        now = u.GameplayStatics.get_time_seconds(game)
        if now < state.get("next", 0.):
            return
        state["next"] = now + 1.
        if "id" not in state:
            for key in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(game):
                row = inspect(game, key)
                if row.get("species") == species and row.get("region") == "Barren":
                    state["id"] = key
                    u.SystemLibrary.execute_console_command(game, "eco.Inspection.GameplayReasons 1")
                    if horse_fixture:
                        migration = next((item for item in u.ObjectIterator(u.EcoHerdMigrationSubsystem)
                                          if item.get_outer() == game), None)
                        if migration is None or not migration.apply_food_fraction_for_audit("Barren", 0., True):
                            raise RuntimeError("Horse test could not apply its explicit origin forage shortage")
                    u.GameplayStatics.set_global_time_dilation(game, 4.)
                    break
            if horse_fixture and "id" not in state and now >= 15.:
                raise RuntimeError("Horse did not spawn. Inspect the first authority setup error.")
            return
        row = inspect(game, state["id"])
        state["samples"].append({
            "seconds": now, "region": row.get("region"), "hp": row.get("hp"),
            "reasons": row.get("gameplay_reason_history", []),
        })
        arrivals = [event for event in row.get("gameplay_reason_history", []) if event["reason"] == "PassageArrived"]
        if len(arrivals) > 1:
            raise RuntimeError("The same journey issued more than one arrival")
        if len(arrivals) == 1 and row.get("region") == "Forest":
            state.setdefault("arrival", arrivals[0])
        if any(event["reason"] == "PassageWaypoint" for event in row.get("gameplay_reason_history", [])):
            state["observed_waypoint"] = True
        if "arrival" in state:
            if waypoint_fixture and not state.get("observed_waypoint"):
                raise RuntimeError("The distant-start fixture did not observe a waypoint advance")
            meal_reason = "HabitatPatchEaten" if patch_fixture else "CarrionEaten"
            meals = [event for event in row.get("gameplay_reason_history", [])
                     if event["reason"] == meal_reason and event["region"] == "Forest"
                     and event["time"] >= state["arrival"]["time"]]
            if not meals and now < state["arrival"]["time"] + 90.:
                return
            if patch_fixture and not meals:
                raise RuntimeError(f"The {species} crossed the seam but did not eat from the destination patch")
            state["post_arrival_food_records"] = meals
            u.unregister_slate_post_tick_callback(handle)
            finish()
        elif now >= 220.:
            raise RuntimeError("The agent did not commit the authored crossing")
    except Exception:
        u.unregister_slate_post_tick_callback(handle)
        finish(traceback.format_exc())


try:
    setup()
    state["deadline"] = time.monotonic() + 125.
    handle = u.register_slate_post_tick_callback(tick)
    levels.editor_request_begin_play()
except Exception:
    finish(traceback.format_exc())

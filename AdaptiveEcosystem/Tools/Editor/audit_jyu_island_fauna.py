"""Verify saved island fauna and render the existing freshwater reach in PIE."""

from collections import Counter
import json
from pathlib import Path
import time
import traceback

import unreal as u


editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
out = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit"
authored = json.loads((out / "IslandFaunaAuthoring.json").read_text(encoding="utf-8"))
inspect = u.EcoCreatureInspectionLibrary
result = {"errors": [], "samples": [], "capture_files": []}
started = time.monotonic()
next_sample = 0.
camera = None
origin = u.Vector(*authored["river_view"])


def finish():
    (out / "IslandFaunaPIE.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    u.unregister_slate_post_tick_callback(handle)
    u.log(f"ECO_ISLAND_FAUNA_PIE errors={result['errors']}")
    levels.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def set_camera(world, eye, target):
    global camera
    if not camera:
        camera = u.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, u.CameraActor, u.Transform())
    camera.set_actor_location(eye, False, True)
    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye, target), False)
    pc = u.GameplayStatics.get_player_controller(world, 0)
    pc.set_view_target_with_blend(camera, 0.)
    for command in ("eco.Creature.Labels 0", "ShowFlag.HUD 0", "ShowFlag.Particles 0"):
        u.SystemLibrary.execute_console_command(world, command)


def capture(world, name):
    path = out / (name + ".png")
    u.SystemLibrary.execute_console_command(world, f'HighResShot 1920x1080 filename="{path.as_posix()}"')
    result["capture_files"].append(path.name)


def tick(_):
    global next_sample
    try:
        if time.monotonic() - started > 170.:
            raise RuntimeError("Island PIE timed out")
        world = editor.get_game_world()
        if not world:
            return
        now = u.GameplayStatics.get_time_seconds(world)
        if now < next_sample:
            return
        runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
        if not runtime or not runtime.is_runtime_ready():
            if now > 16.:
                result["water_on_failure"] = {name: str(inspect.inspect_fauna_water(world, authored["river"], u.Vector(*pos), 3.))
                    for name, pos in authored["water_samples"].items()}
                raise RuntimeError("Island authority did not initialize")
            return
        population, fish, river_native = Counter(), {}, []
        aquatic = {"AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
        for agent in inspect.get_authority_agent_ids(world):
            value = inspect.capture_agent(world, agent)
            raw = next((item for item in value if isinstance(item, str)), "") if isinstance(value, tuple) else value
            if raw:
                row = json.loads(raw)
                kind = row.get("species", "unknown")
                if row.get("hp", 0) > 0:
                    population[kind] += 1
                    if kind in ("Herbivore", "Wolf") and row.get("region") == authored["river"]:
                        river_native.append(str(agent))
                    if kind in aquatic:
                        fish[str(agent)] = row.get("position")
                if row.get("brain") and kind == "Herbivore":
                    result["deer_brain"] = row["brain"]
        water = {}
        for name, pos in authored["water_samples"].items():
            sample = inspect.inspect_fauna_water(world, authored["river"], u.Vector(*pos), 3.)
            if sample:
                bounds, flow = sample
                water[name] = [bounds.y - bounds.x, flow.length()]
        stocks = {}
        patches = runtime.get_editor_property("fauna_habitat_patches")
        for patch in patches:
            key = str(patch.get_editor_property("id"))
            stock = runtime.inspect_fauna_habitat_stock(key)
            if stock is not None:
                stocks[key] = float(stock[-1] if isinstance(stock, tuple) else stock)
        result["samples"].append({"time": now, "population": population, "fish": fish, "water": water, "stocks": stocks,
                                  "river_native": river_native})
        count = len(result["samples"])
        if count == 2:
            u.SystemLibrary.execute_console_command(world, "showhud")
            set_camera(world, origin + u.Vector(-2100., -3600., 4200.), origin + u.Vector(2600., 850., 0.))
        elif count == 7:
            capture(world, "IslandFauna_RiverAndLake")
        elif count == 8:
            edge = u.Vector(*authored["river_shore_view"])
            set_camera(world, edge + u.Vector(-1250., -1500., 480.), edge + u.Vector(900., 850., 35.))
        elif count == 13:
            capture(world, "IslandFauna_Riverbank")
        elif count == 14:
            drift = u.Vector(*authored["water_samples"]["Drift"])
            set_camera(world, drift + u.Vector(-510., 55., 10.), drift + u.Vector(430., 120., -25.))
        elif count == 18:
            capture(world, "IslandFauna_Underwater")
        elif count == 19:
            point = u.Vector(*authored["dry_refuges"][2])
            set_camera(world, point + u.Vector(-1500., 950., 850.), point + u.Vector(1350., 650., 0.))
        elif count == 22:
            capture(world, "IslandFauna_Grassland")
        elif count == 23:
            point = u.Vector(*authored["dry_refuges"][-2])
            set_camera(world, point + u.Vector(-1000., -1600., 750.), point + u.Vector(1600., 800., 0.))
        elif count == 26:
            capture(world, "IslandFauna_Highland")
        elif count in (27, 31):
            index = (count - 27) // 4
            eye, target = authored["lake_views"][index]
            set_camera(world, u.Vector(*eye), u.Vector(*target))
        elif count in (30, 34):
            capture(world, f"IslandFauna_Lake{(count - 30) // 4 + 1}")
        if now >= 175.:
            first = result["samples"][0]
            if any(row["river_native"] for row in result["samples"]):
                result["errors"].append("Native land animals entered the rules-only river region")
            missing = set().union(*(set(row) for row in authored["founders"].values())) - set(first["population"])
            if missing:
                result["errors"].append(f"Missing initial species {sorted(missing)}")
            if len(water) != len(authored["water_samples"]):
                result["errors"].append(f"Missing valid water columns: {sorted(set(authored['water_samples'])-set(water))}")
            moving = {agent for agent, pos in first["fish"].items()
                      if len({row["fish"].get(agent) for row in result["samples"] if row["fish"].get(agent)}) > 2}
            result["moving_fish"] = len(moving)
            if not moving:
                result["errors"].append("No fish movement detected")
            finish()
            return
        next_sample = now + 5.
    except Exception:
        result["errors"].append(traceback.format_exc())
        finish()


if __name__ == "__main__":
    if editor.get_editor_world().get_name() != "LV_JYU_IslandEcosystem":
        raise RuntimeError("Open the island copy first")
    levels.editor_request_begin_play()
    handle = u.register_slate_post_tick_callback(tick)

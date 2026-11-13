"""Read-only client-side check for the owned expanded fauna map."""

import json
from pathlib import Path
import re
import time

import unreal


command = unreal.SystemLibrary.get_command_line()
client_name = re.search(r"-EcoExpandedClient=([A-Za-z0-9_]+)", command)
server_fixture = "-EcoExpandedNetworkServer" in command
if not client_name and not server_fixture:
    raise RuntimeError("Use -EcoExpandedClient=<audit name> or -EcoExpandedNetworkServer")
name = client_name.group(1) if client_name else "Server"
regional_water = "-EcoExpandedClientWaterPassage" in command
check_food_intent = "-EcoExpandedCheckFoodIntent" in command
map_name = "LV_JYU_ExpandedWaterPassage" if regional_water else "LV_JYU_ExpandedFauna"
new_species = {"Bighorn", "Jackrabbit", "Horse", "Mink", "GoldenEagle", "AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
output = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "ExpandedFaunaImport"
output.mkdir(parents=True, exist_ok=True)
state = {"start": time.monotonic(), "joined": None, "next": 0., "visuals": {}, "summary": set(), "water_heights": [],
         "authority": 0, "native_steps": 0, "revisions": set(), "water_migration": {}, "fish_regions": {},
         "food_intent_rejected": None}


def finish(error=None):
    unreal.unregister_slate_post_tick_callback(handle)
    data = {key: sorted(value) if isinstance(value, set) else value for key, value in state.items()
            if key not in ("start", "joined", "next")}
    data["error"] = error
    (output / f"{name}_client.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    if error:
        unreal.log_error(f"ECO_EXPANDED_CLIENT_FAILED {name} {error}")
    else:
        unreal.log(f"ECO_EXPANDED_CLIENT_READY {name} {len(state['visuals'])} visual IDs")
    if regional_water:
        world = next((w for w in unreal.ObjectIterator(unreal.World)
                      if w.get_name() == map_name and unreal.GameplayStatics.get_player_controller(w, 0)), None)
        if world:
            unreal.SystemLibrary.execute_console_command(world, "quit")


def tick(_):
    try:
        now = time.monotonic()
        if now - state["start"] > (105. if regional_water else 75.):
            raise RuntimeError("Client did not receive the required updates before the audit deadline")
        if now < state["next"]:
            return
        state["next"] = now + 1.
        world = next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name() == map_name
                      and unreal.GameplayStatics.get_player_controller(w, 0)), None)
        game_state = unreal.GameplayStatics.get_game_state(world) if world else None
        if not isinstance(game_state, unreal.EcoGameState):
            return
        summary = game_state.get_ecology_summary()
        if summary.get_editor_property("revision") <= 0:
            return
        state["revisions"].add(summary.get_editor_property("revision"))
        state["summary"].update(str(row.get_editor_property("species_id")) for row in summary.get_editor_property("species"))
        if regional_water:
            for row in summary.get_editor_property("species"):
                if str(row.get_editor_property("species_id")) == "AriakeCatfish":
                    state["water_migration"][str(row.get_editor_property("region_id"))] = [
                        row.get_editor_property("migration_in"), row.get_editor_property("migration_out")]
        state["joined"] = state["joined"] or now
        state["authority"] = max(state["authority"], len(unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)))
        native = next((subsystem for subsystem in unreal.ObjectIterator(unreal.EcoPolicyV3IntegratedSubsystem)
                       if subsystem.get_outer() == world), None)
        if native:
            state["native_steps"] = max(state["native_steps"],
                                        json.loads(native.capture_step_performance()).get("native_steps_total", 0))
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureRepresentationActor):
            if not actor.get_editor_property("bound"):
                continue
            visual = actor.get_editor_property("visual_state")
            species = str(visual.get_editor_property("species_id"))
            if species not in new_species:
                continue
            mesh = actor.get_editor_property("creature_mesh")
            asset, animation = mesh.get_skeletal_mesh_asset(), mesh.get_anim_instance()
            if asset and animation:
                stable_id = str(visual.get_editor_property("stable_agent_id"))
                state["visuals"][stable_id] = dict(
                    species=species, mesh=asset.get_name(), animation=animation.get_class().get_name(),
                    body=visual.get_editor_property("body_scale"), activity=str(visual.get_editor_property("activity")))
                if regional_water and species == "AriakeCatfish":
                    side = "east" if visual.get_editor_property("position").x > 4170. else "west"
                    sides = state["fish_regions"].setdefault(stable_id, [])
                    if side not in sides:
                        sides.append(side)
        for water in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoVegetationHabitat):
            center = water.get_actor_location()
            if abs(center.x - 4100.) < 1. and abs(center.y + 4800.) < 1.:
                surface = water.get_component_by_class(unreal.StaticMeshComponent)
                if surface:
                    state["water_heights"].append(round(surface.get_world_location().z, 2))
        if check_food_intent and state["food_intent_rejected"] is None:
            hunter = next((int(i) for i, row in state["visuals"].items() if row["species"] == "Mink"), None)
            prey = next((int(i) for i, row in state["visuals"].items() if row["species"] == "UnidentifiedFish"), None)
            runtime = next(iter(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureIntegrationSpawner)), None)
            if hunter and prey and runtime:
                state["food_intent_rejected"] = not runtime.submit_fauna_food_intent(
                    hunter, unreal.EcoFaunaFoodIntent.LIVE_PREY, prey, "None")
                if not state["food_intent_rejected"]:
                    raise RuntimeError("Client food preference request reached authority")
        if now - state["joined"] >= 18.:
            if not new_species.issubset(state["summary"]) or not state["visuals"] or len(state["revisions"]) < 2:
                raise RuntimeError("Missing completed species counts, visual proxies, or replicated revisions")
            if state["authority"] or state["native_steps"]:
                raise RuntimeError("Client ran logical ecology")
            if check_food_intent and not state["food_intent_rejected"]:
                return
            if regional_water:
                migration = state["water_migration"]
                heights = state["water_heights"]
                if (migration.get("FaunaMeadow") != [0, 1] or migration.get("FaunaWaterEast") != [1, 0]
                        or not any(sides == ["west", "east"] for sides in state["fish_regions"].values())
                        or not heights or max(heights) - min(heights) < 20.):
                    return
            finish()
    except Exception as error:
        finish(f"{type(error).__name__}: {error}")


if server_fixture:
    # Move only the test viewers. Authority fauna, food, clocks and replication stay untouched.
    world = next(w for w in unreal.ObjectIterator(unreal.World) if w.get_name() == map_name
                 and unreal.GameplayStatics.get_game_mode(w))
    runtime = next(iter(unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureIntegrationSpawner)))
    seen = {}

    def observe_server(_):
        now = unreal.GameplayStatics.get_time_seconds(world)
        for controller in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.PlayerController):
            pawn = controller.get_controlled_pawn()
            if not pawn:
                continue
            key = pawn.get_path_name()
            if key not in seen:
                seen[key] = now
            if now - seen[key] > 6. and seen[key] >= 0.:
                pawn.set_actor_location(unreal.Vector(3950., -4100., 135.), False, True)
                seen[key] = -1.
                unreal.log(f"ECO_EXPANDED_NETWORK_WATER_VIEW {key}")

    runtime.on_runtime_sample.add_callable(observe_server)
else:
    handle = unreal.register_slate_post_tick_callback(tick)

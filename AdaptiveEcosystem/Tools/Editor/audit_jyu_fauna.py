"""Read-only samples from the running fauna map, including a real network client."""

import json
import re
from pathlib import Path

import unreal


command = unreal.SystemLibrary.get_command_line()
name = re.search(r"-FaunaAuditName=([A-Za-z0-9_]+)", command)
if not name:
    raise RuntimeError("Missing -FaunaAuditName")

output = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "FaunaAudit"
output.mkdir(parents=True, exist_ok=True)
expected = {"Pig", "Fox", "Crow", "Leopard", "Buffalo", "Rat", "Herbivore", "Wolf"}
samples = {"species": {}, "summary": {}, "max_crow_agl_cm": 0., "authority": None, "status": "waiting"}
last_sample = -1.


def tick(_):
    global last_sample
    world = next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name() == "LV_JYU_Fauna"
                  and unreal.GameplayStatics.get_game_state(w)), None)
    if not world:
        return
    now = unreal.GameplayStatics.get_time_seconds(world)
    if now < last_sample + .25:
        return
    last_sample = now
    summary = unreal.GameplayStatics.get_game_state(world).get_ecology_summary()
    phase = str(summary.get_editor_property("time").get_editor_property("day_cycle").get_editor_property("phase")).split(".")[-1].split(":")[0].rstrip(">")
    for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureRepresentationActor):
        if not actor.get_editor_property("bound"):
            continue
        visual = actor.get_editor_property("visual_state")
        kind = str(visual.get_editor_property("species_id"))
        activity = str(visual.get_editor_property("activity")).split(".")[-1].split(":")[0].rstrip(">")
        mesh = actor.get_editor_property("creature_mesh")
        anim = mesh.get_anim_instance()
        row = samples["species"].setdefault(kind, {"ids": [], "activities": [], "min_maturity": 1.,
                                                   "max_speed_cm_s": 0., "max_ik": 0., "max_head_yaw": 0., "agents": {}})
        stable_id = visual.get_editor_property("stable_agent_id")
        if visual.get_editor_property("alive"):
            phase_counts = row.setdefault("phase_activity_samples", {}).setdefault(phase, {})
            phase_counts[activity] = phase_counts.get(activity, 0) + 1
        maturity = visual.get_editor_property("maturity")
        energy = visual.get_editor_property("normalized_energy")
        agent = row["agents"].setdefault(str(stable_id), {"first_seen": now, "min_maturity": maturity, "activities": {}})
        agent["min_maturity"] = min(agent["min_maturity"], maturity)
        agent["min_energy"] = min(agent.get("min_energy", 1.), energy)
        agent["max_energy"] = max(agent.get("max_energy", 0.), energy)
        agent["activities"].setdefault(activity, now)
        if stable_id not in row["ids"]:
            row["ids"].append(stable_id)
        if activity not in row["activities"]:
            row["activities"].append(activity)
        row["min_maturity"] = min(row["min_maturity"], maturity)
        row["max_speed_cm_s"] = max(row["max_speed_cm_s"], actor.get_velocity().length())
        if isinstance(anim, unreal.EcoCreatureAnimInstance):
            row["max_ik"] = max(row["max_ik"], anim.get_editor_property("ground_ik_alpha"))
            row["max_head_yaw"] = max(row["max_head_yaw"], abs(anim.get_editor_property("turn_head_rotation").yaw))
        if kind == "Crow" and activity in ("TAKEOFF", "FLY", "LAND"):
            position = actor.get_actor_location()
            ground = unreal.EcoCreatureAnimationBuilder.project_placement_point(world, position)
            if ground:
                samples["max_crow_agl_cm"] = max(samples["max_crow_agl_cm"], position.z - ground.z)
    for entry in summary.get_editor_property("species"):
        kind = str(entry.get_editor_property("species_id"))
        samples["summary"][kind] = {key: entry.get_editor_property(key) for key in ("population", "births", "deaths")}
    samples["authority"] = len(unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(world))
    player = unreal.GameplayStatics.get_player_controller(world, 0)
    pawn = player.get_controlled_pawn() if player else None
    if pawn and pawn.player_state:
        equipment = pawn.get_component_by_class(unreal.EcoEquipmentComponent)
        samples["player"] = {"state_class": pawn.player_state.get_class().get_name(),
                             "weapon_equipped": bool(equipment and equipment.get_editor_property("weapon"))}
    proxies = unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureHitProxy)
    for kind, row in samples["species"].items():
        sizes = [proxy.get_editor_property("shape").get_unscaled_capsule_radius() for proxy in proxies
                 if proxy.get_editor_property("stable_agent_id") in row["ids"]]
        if sizes:
            ranges = samples.setdefault("server_hit_proxy_radius_cm", {})
            prior = ranges.get(kind, [min(sizes), max(sizes)])
            ranges[kind] = [min(prior[0], min(sizes)), max(prior[1], max(sizes))]
    samples["world_seconds"] = now
    samples["status"] = "observed" if expected.issubset(samples["species"]) else "partial"
    if int(now) != int(now - .25):
        (output / (name.group(1) + ".json")).write_text(json.dumps(samples, indent=2), encoding="utf-8")


handle = unreal.register_slate_post_tick_callback(tick)

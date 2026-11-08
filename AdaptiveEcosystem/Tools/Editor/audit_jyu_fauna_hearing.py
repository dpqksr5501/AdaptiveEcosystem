"""Local dedicated-server fixture. Only moves the player; uses normal movement input and noise."""

import json
import re
import time
from pathlib import Path

import unreal as u


command = u.SystemLibrary.get_command_line()
server = "-FaunaHearingServer" in command
observer = "-FaunaHearingObserver" in command
focus = "-FaunaHearingFocusWolf" in command
run = re.search(r"-FaunaHearingRun=(\w+)", command)
if not run:
    raise RuntimeError("Pass -FaunaHearingRun with the same new label on both peers")
output = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir())) / "FaunaFootsteps"
output.mkdir(parents=True, exist_ok=True)
packet = output / f"{run.group(1)}Movement.json"
species = ("Rat", "Fox", "Pig", "Crow", "Leopard", "Buffalo", "Herbivore", "Wolf")
cases = [(kind, side) for side in (1, -1) for kind in species]
if focus:
    cases = [("Wolf", 1)] * 10
state = {"deadline": time.monotonic() + 75., "phase": -1}


def inspect(world, key):
    raw = u.EcoCreatureInspectionLibrary.capture_agent(world, key)
    if isinstance(raw, tuple):
        raw = next((value for value in raw if isinstance(value, str)), "")
    return json.loads(raw) if raw else {}


def target(world, kind):
    candidates = []
    for key in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world):
        row = inspect(world, key)
        if row.get("species") != kind or row.get("hp", 0.) <= 0.:
            continue
        coords = {axis: float(value) for axis, value in re.findall(r"([XYZ])=([-+\d.]+)", row.get("position", ""))}
        if not coords or abs(coords.get("Z", 0.)) > 80.:
            continue
        candidates.append((key, u.Vector(*(coords.get(axis, 0.) for axis in "XYZ"))))
    return min(candidates, key=lambda row: row[1].length(), default=None)


def wolf_course(world, now):
    if "wolf" not in state:
        state["wolf"] = target(world, "Wolf")
    if not state["wolf"]:
        return None
    key = state["wolf"][0]
    row = inspect(world, key)
    if not row.get("native_world_position") or row.get("hp", 0.) <= 0.:
        state.pop("wolf")
        return None
    position = u.Vector(*row["native_world_position"])
    course = state.get("course")
    if not course or now - course[1] >= .18:
        delta = position - course[0] if course else u.Vector()
        direction = u.Vector(delta.x, delta.y, 0.).normal() if delta.length() > 4. else (course[2] if course else u.Vector(1, 0, 0))
        state["course"] = (position, now, direction)
    return key, position, state["course"][2]


def tick(_):
    if time.monotonic() > state["deadline"]:
        u.log_error("ECO_FAUNA_HEARING_TIMEOUT")
        return False
    try:
        world = next((world for world in u.ObjectIterator(u.World) if world.get_name() == "LV_JYU_Fauna"
                      and u.GameplayStatics.get_game_state(world)), None)
        if not world:
            return True
        player = u.GameplayStatics.get_player_controller(world, 0)
        pawn = player.get_controlled_pawn() if player else None
        if not pawn:
            return True
        bridge = pawn.get_component_by_class(u.EcoPlayerEcologyComponent)
        if not bridge:
            raise RuntimeError("Player ecology component missing")
        now = u.GameplayStatics.get_time_seconds(world)
        if server:
            if "origin" not in state:
                u.SystemLibrary.execute_console_command(world, "eco.Senses.NoiseLog 1")
                u.SystemLibrary.execute_console_command(world, "eco.Footsteps.HearingLog 1")
                state["origin"] = now + .7
                if focus:
                    bridge.set_gait(u.EcoPlayerGait.RUN)
            course = wolf_course(world, now) if focus else None
            phase = int((now - state["origin"]) / 2.15)
            if now < state["origin"] or phase == state["phase"]:
                return True
            if phase >= len(cases):
                packet.write_text(json.dumps({"done": True}), encoding="utf-8")
                u.log("ECO_FAUNA_HEARING_FIXTURE_FINISHED")
                return False
            state["phase"] = phase
            kind, side = cases[phase]
            chosen = course if focus else target(world, kind)
            if not chosen:
                u.log_warning(f"ECO_FAUNA_HEARING_TARGET_UNAVAILABLE species={kind}")
                return True
            key, position, *path = chosen
            direction = path[0] if path else u.Vector(side, 0., 0.)
            start = position - direction * (350. if focus else 530.) + u.Vector(-direction.y, direction.x, 0.) * (90. if focus else 135.)
            ground = u.EcoCreatureAnimationBuilder.project_placement_point(world, start)
            if not ground:
                return True
            pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(ground + u.Vector(0., 0., 97.), False, True)
            u.log(f"ECO_FAUNA_HEARING_PHASE phase={phase} species={kind} target={key} side={side}")
            packet.write_text(json.dumps({"phase": phase, "direction": [direction.x, direction.y]}), encoding="utf-8")
        elif observer:
            if "listening" not in state:
                remote = next((actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.Character)
                               if actor != pawn and actor.player_state and actor.get_component_by_class(u.EcoPlayerEcologyComponent)), None)
                if remote:
                    player.set_view_target_with_blend(remote, 0.)
                    u.SystemLibrary.execute_console_command(world, "eco.Footsteps.Log 1")
                    u.SystemLibrary.execute_console_command(world, "au.DisableAppVolume 1")
                    u.log(f"ECO_FAUNA_HEARING_OBSERVER {remote.get_name()}")
                    state["listening"] = True
        elif packet.exists():
            try:
                data = json.loads(packet.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                return True
            if data.get("done"):
                u.log("ECO_FAUNA_HEARING_CLIENT_FINISHED")
                return False
            if data["phase"] != state["phase"]:
                state["phase"] = data["phase"]
                bridge.set_editor_property("use_keyboard_gait", False)
                bridge.set_gait(u.EcoPlayerGait.RUN)
            pawn.add_movement_input(u.Vector(*data["direction"], 0.), 1., False)
        return True
    except Exception as error:
        u.log_error(f"ECO_FAUNA_HEARING_FIXTURE_FAILED {error}")
        return False


handle = u.register_ticker_callback(tick, 0.)

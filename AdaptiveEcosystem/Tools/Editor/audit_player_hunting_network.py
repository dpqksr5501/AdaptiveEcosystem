"""Dedicated melee fixture using the configured player input and real collision receipts."""
import json
import math
from pathlib import Path
import re
import time
import traceback

import unreal as u


command = u.SystemLibrary.get_command_line()
is_server = "-huntingnetworkserver" in command.lower()
name = "Server" if is_server else re.search(r"-HuntingNetworkClient=(\w+)", command).group(1)
tag = re.search(r"-HuntingEvidenceTag=(\w+)", command)
out = Path(u.Paths.project_saved_dir()).resolve() / "PlayerHunting_20261105" / (tag.group(1) if tag else "Network")
out.mkdir(parents=True, exist_ok=True)

action = u.load_asset("/Game/Variant_Combat/Input/Actions/IA_ComboAttack")
data = u.load_asset("/Game/JWJ/Gameplay/DA_EcoUnarmedCombo")
montage = data.get_editor_property("montage")
steps = data.get_editor_property("steps")
sections = [str(step.get_editor_property("section")) for step in steps]
lengths = [u.load_asset(f"/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_0{index}").get_play_length()
           for index in range(1, len(steps)+1)]
state = dict(deadline=time.monotonic()+140., world=None, next_sample=0., samples=[], events=[],
             attack_inputs=0, next_attack=0., next_combo_press=0., pose_samples=[])


def write(filename, value):
    target = out / filename
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(target)


def read(filename):
    try:
        return json.loads((out / filename).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def event(value):
    receipt = dict(result=str(value.result), id=int(value.target_stable_agent_id),
                   damage=value.applied_damage, step=value.step_id, execution=value.attack_execution_id)
    state["events"].append(receipt)
    u.log("HUNTING_NETWORK_OWNER_RECEIPT "+json.dumps(receipt))
    if name == "ClientA" and "DEATH_COMMITTED" in receipt["result"]:
        write("ClientADeathReceived.json", dict(target=receipt["id"]))


def finish(ok, error=None):
    if state.get("finished"):
        return
    state["finished"] = True
    write(name+".json", dict(result="PASS" if ok else "FAIL", error=error, samples=state["samples"],
                            events=state["events"], attack_inputs=state["attack_inputs"], target=state.get("target"),
                            pose_samples=state["pose_samples"],
                            fixture="Authority player placement; configured GAS input; unchanged animal/HP/asset data"))
    u.log("HUNTING_NETWORK_"+name+"_"+("PASS" if ok else "FAIL"))
    if state["world"]:
        u.SystemLibrary.execute_console_command(state["world"], "QUIT")
    else:
        u.SystemLibrary.quit_editor()


def inspect(world, key):
    raw = u.EcoCreatureInspectionLibrary.capture_agent(world, key)
    if isinstance(raw, tuple):
        raw = next((value for value in raw if isinstance(value, str)), None)
    return json.loads(raw) if raw else {}


def choose_wolf(world, ids):
    for key in ids:
        row = inspect(world, key)
        if row.get("species") == "Wolf" and row.get("region") == "JWJ_WildlifeTest" and row.get("hp", 0) > 0:
            return row
    return None


def place(pc, ground, offset):
    pawn = pc.get_controlled_pawn()
    movement = pawn.character_movement
    movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
    pawn.set_actor_location(ground+offset, False, True)
    movement.stop_movement_immediately()
    facing = u.MathLibrary.find_look_at_rotation(ground+u.Vector(offset.x, offset.y, 0.), ground)
    pawn.set_actor_rotation(facing, True)
    pc.set_control_rotation(facing)


def server_tick(world, runtime, players, ids, now):
    state["max_players"] = max(state.get("max_players", 0), len(players))
    stats = runtime.get_combat_diagnostics()
    if "started" in state:
        reports = [read(peer+".json") for peer in ("ClientA", "ClientB")]
        if now-state["started"] > 55. or all(reports):
            assert stats.hunting_deaths == 1, f"Expected one server hunting death, got {stats.hunting_deaths}"
            assert stats.player_hits > 0, "Wolf did not commit damage to the remote player"
            assert state["max_players"] >= 2, "Two real connections required"
            for peer, report in zip(("ClientA", "ClientB"), reports):
                assert report and report["result"] == "PASS", f"{peer} did not pass"
            finish(True)
            return
    marker = read("ClientAReady.json")
    if not marker:
        return
    attacker = next((pc for pc in players
                     if pc.get_controlled_pawn().player_state.get_editor_property("player_id") == marker["player_id"]), None)
    if not attacker:
        return
    if "target" not in state:
        wolf = choose_wolf(world, ids)
        assert wolf, "No live wolf in JWJ_WildlifeTest"
        state.update(target=int(wolf["stable_id"]), initial_hp=wolf["hp"], started=now)
        write("Session.json", dict(target=state["target"], initial_hp=state["initial_hp"]))
    elapsed = now-state["started"]
    wolf = inspect(world, state["target"])
    if stats.hunting_deaths and "death_at" not in state:
        state["death_at"] = now
        u.log("HUNTING_NETWORK_DEATH "+str(state["target"]))
    if "death_at" in state and "retaliation" not in state:
        # The previous combo can still have an active hit window after the killing blow.
        # Keep the next wolf out of the fixture until the owner and authority have finished that attack.
        death_receipt = read("ClientADeathReceived.json")
        pawn = attacker.get_controlled_pawn()
        anim = pawn.mesh.get_anim_instance()
        hit = pawn.get_component_by_class(u.EcoMeleeHitComponent)
        if (not death_receipt or death_receipt["target"] != state["target"]
                or not anim or anim.montage_is_playing(montage)
                or hit.get_editor_property("active_step") >= 0):
            return
        alternate = choose_wolf(world, ids)
        assert alternate, "No surviving wolf for retaliation"
        state["retaliation"] = int(alternate["stable_id"])
    if "retaliation" in state:
        wolf = inspect(world, state["retaliation"])
    if wolf.get("native_world_position") and wolf.get("hp", 0) > 0:
        ground = u.Vector(*wolf["native_world_position"])
        for pc in players:
            pawn = pc.get_controlled_pawn()
            pawn.player_state.set_invulnerable("death_at" not in state or pc != attacker)
            if pc != attacker:
                place(pc, ground, u.Vector(-410., 300., 100.))
            elif "death_at" in state:
                # This player stays within bite reach while the wolf chooses and validates its own attack.
                phase = (now-state["death_at"])*.6
                place(pc, ground, u.Vector(130.*math.cos(phase), 130.*math.sin(phase), 96.))
            else:
                # Align the human attack plane with the wolf capsule. Flying holds that height against gravity.
                place(pc, ground, u.Vector(-63., 0., 62.))
    if now >= state.get("next_pose", 0.) and "death_at" not in state:
        state["next_pose"] = now+.05
        pawn = attacker.get_controlled_pawn()
        hit = pawn.get_component_by_class(u.EcoMeleeHitComponent)
        active = hit.get_editor_property("active_step")
        if 0 <= active < len(steps):
            socket = steps[active].get_editor_property("socket")
            position = pawn.mesh.get_socket_location(socket)
            state["pose_samples"].append(dict(elapsed=elapsed, step=active, target_hp=wolf.get("hp"),
                                               target=wolf.get("native_world_position"), socket=[position.x, position.y, position.z]))


def client_tick(world, player, visuals, now):
    pawn = player.get_controlled_pawn()
    pawn_path = pawn.get_path_name()
    if state.get("pawn_path") != pawn_path:
        hit = pawn.get_component_by_class(u.EcoMeleeHitComponent)
        assert hit, "Expected configured melee component"
        state["pawn_path"] = pawn_path
        state["receipt_delegate"] = hit.on_damage_outcome
        state["receipt_delegate"].add_callable_unique(event)
        u.log("HUNTING_NETWORK_BOUND "+hit.get_path_name())
    if name == "ClientA" and not state.get("ready"):
        write("ClientAReady.json", dict(player_id=pawn.player_state.get_editor_property("player_id")))
        state["ready"] = True
    packet = read("Session.json")
    if not packet:
        return
    target = packet["target"]
    state["target"] = target
    started = state.setdefault("connected_at", now)
    assert now-started < (58. if name == "ClientA" else 20.), "Client did not see the required hunting outcomes"
    stats = pawn.player_state
    own_death = [row for row in state["events"] if "DEATH_COMMITTED" in row["result"]]
    visible = any(int(actor.visual_state.stable_agent_id) == target for actor in visuals)
    if name == "ClientA" and visible and not own_death:
        anim = pawn.mesh.get_anim_instance()
        avatar = pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
        if not anim or not avatar:
            return
        def press():
            avatar.release_configured_action(action)
            avatar.press_configured_action(action)
            state["attack_inputs"] += 1
        if not anim.montage_is_playing(montage) and now >= state["next_attack"]:
            press()
            state["next_attack"] = now+2.
        elif anim.montage_is_playing(montage):
            section = str(anim.montage_get_current_section(montage))
            if section in sections[:-1]:
                index = sections.index(section)
                fraction = (anim.montage_get_position(montage)-sum(lengths[:index]))/lengths[index]
                # Re-press within the authored input window to cover client montage replication skew.
                if .36 < fraction < .66 and now >= state["next_combo_press"]:
                    press()
                    state["next_combo_press"] = now+.085
    if not state["samples"]:
        return
    saw_death = any(row["deaths"] > 0 for sample in state["samples"] for row in sample["species"]
                    if row["region"] == "JWJ_WildlifeTest" and row["species"] == "Wolf")
    if not saw_death or not any(sample["visuals"] for sample in state["samples"]):
        return
    if name == "ClientA":
        owner_hurt = any(sample["local_hp"] < 100. for sample in state["samples"])
        if not own_death or not (owner_hurt or stats.get_health() < 100.) or not read("ClientB.json"):
            return
        commits = [row for row in state["events"] if "COMMITTED" in row["result"] and "DEATH" not in row["result"]]
        assert len(own_death) == 1 and own_death[0]["id"] == target, "One owner death receipt for the exact target required"
        assert all(row["id"] == target for row in commits), "Other targets cannot substitute for the selected wolf"
        assert abs(sum(row["damage"] for row in commits)-packet["initial_hp"]) < .01, "Damage must match authority HP"
        assert len({(row["execution"], row["step"]) for row in commits}) == len(commits), "Duplicate damage per attack step"
        assert any(row["step"] > 0 for row in commits), "Authoritative combo did not advance"
    else:
        assert "-HuntingLateClient" in command, "Observer must connect after the death committed"
        assert not state["events"], "Observer received the attacker's owner-only receipts"
    assert all(not row["authority_agents"] and not row["hit_proxies"] for row in state["samples"]), "Client gained authority"
    finish(True)


def tick():
    now = time.monotonic()
    assert now < state["deadline"], "Network fixture timed out waiting for authoritative damage and replication"
    if not is_server:
        server_report = read("Server.json")
        assert not server_report or server_report["result"] == "PASS", "Server ended without satisfying the fixture"
    world = next((world for world in u.ObjectIterator(u.World)
                  if world.get_name() == "1102_Integration_JWJ" and u.GameplayStatics.get_game_state(world)
                  and (is_server or u.GameplayStatics.get_player_controller(world, 0))), None)
    state["world"] = world
    if not world:
        return
    runtimes = u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureIntegrationSpawner)
    if not runtimes or not runtimes[0].is_runtime_ready():
        return
    runtime = runtimes[0]
    players = [pc for pc in u.GameplayStatics.get_all_actors_of_class(world, u.PlayerController)
               if pc.get_controlled_pawn() and pc.get_controlled_pawn().player_state]
    player = u.GameplayStatics.get_player_controller(world, 0)
    if not is_server and player not in players:
        return
    ids = u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)
    visuals = [actor for actor in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor)
               if actor.get_editor_property("bound")]
    if now >= state["next_sample"]:
        state["next_sample"] = now+.5
        summary = u.GameplayStatics.get_game_state(world).get_ecology_summary()
        stats = runtime.get_combat_diagnostics()
        state["samples"].append(dict(elapsed=now-state.setdefault("sample_started", now), players=len(players),
                                     authority_agents=len(ids), visuals=len(visuals), hunting_deaths=stats.hunting_deaths,
                                     player_hits=stats.player_hits,
                                     hit_proxies=len(u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureHitProxy)),
                                     local_hp=None if is_server else player.get_controlled_pawn().player_state.get_health(),
                                     species=[dict(region=str(row.region_id), species=str(row.species_id),
                                                   population=row.population, deaths=row.deaths) for row in summary.species]))
    if is_server:
        server_tick(world, runtime, players, ids, now)
    else:
        client_tick(world, player, visuals, now)


def ticker(_):
    if state.get("finished") or state.get("in_tick"):
        return not state.get("finished")
    state["in_tick"] = True
    try:
        tick()
    except Exception:
        finish(False, traceback.format_exc())
    finally:
        state["in_tick"] = False
    return not state.get("finished")


handle = u.register_ticker_callback(ticker, 0.)

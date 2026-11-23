"""Run the dedicated rifle fixture with live client representations and owner receipts."""
import unreal as u
import time,json,re,traceback,math
from pathlib import Path
cmd=u.SystemLibrary.get_command_line()
server="-RifleNetworkServer" in cmd
saved_island = "-RifleSavedIsland" in cmd.split()
shared_target = "-RifleSharedTarget" in cmd.split()
rule_ambush = "-RifleRuleAmbush" in cmd.split()
restore_checkpoint = "-RifleRestoreCheckpoint" in cmd.split()
slot_match = re.search(r"-RifleCheckpointSlot=(\w+)", cmd)
checkpoint_slot = slot_match[1] if slot_match else None
map_name = "LV_JYU_IslandEcosystemRefreshed" if saved_island else "1102_Integration_JWJ"
name=("RestoredServer" if restore_checkpoint else "Server") if server else re.search(r"-RifleNetworkClient=(\w+)",cmd).group(1)
tag=re.search(r"-RifleEvidenceTag=(\w+)",cmd)
out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_saved_dir()))/"RifleValidation"/(tag.group(1) if tag else "Network");out.mkdir(parents=True,exist_ok=True)
u.log("[EcoRifleNetwork] Starting "+name)
state={"world":None,"deadline":time.monotonic()+155,"events":[],"next":0,"shots":0,"accepted":0,"samples":[]}
if not rule_ambush:
    aim_action=u.load_asset("/Game/JWJ/Weapons/IA_AimRifle")
    fire_action=u.load_asset("/Game/JWJ/Weapons/IA_FireRifle")
def inspect(w,key):
    raw=u.EcoCreatureInspectionLibrary.capture_agent(w,key)
    if isinstance(raw,tuple):raw=next(v for v in raw if isinstance(v,str))
    return json.loads(raw) if raw else {}
def shot(execution,muzzle,end):state["accepted"]+=1
def event(v):state["events"].append({"result":str(v.result),"damage":v.applied_damage,"id":int(v.target_stable_agent_id)})


def committed_damage(stable_id):
    return sum(row["damage"] for row in state["events"]
               if row["id"] == stable_id and ".COMMITTED:" in row["result"] and row["damage"] > 0.)


def shared_lane_offsets(world, target_id, target_position):
    # Keep both shooters on the saved island. Move the firing lanes when another
    # live body would intercept a shot intended for the shared target.
    blockers = []
    for proxy in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureHitProxy):
        identity = proxy.get_editor_property("stable_agent_id")
        position = proxy.get_actor_location()
        if identity <= 0 or identity == target_id or (position - target_position).length() > 1000.:
            continue
        radius = proxy.get_editor_property("shape").get_scaled_capsule_radius()
        blockers.append((position - target_position, radius + 110.))
    for angle in (0., 30., -30., 60., -60., 90., -90., 120., -120., 150., -150., 180.):
        cosine, sine = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        lanes = [u.Vector(-650. * cosine - side * sine, -650. * sine + side * cosine, 96.)
                 for side in (-180., 180.)]
        clear = True
        for lane in lanes:
            for blocker, radius in blockers:
                fraction = (blocker.x * lane.x + blocker.y * lane.y) / (lane.x * lane.x + lane.y * lane.y)
                if (0. < fraction < 1. and math.hypot(blocker.x - fraction * lane.x, blocker.y - fraction * lane.y) < radius):
                    clear = False
                    break
            if not clear:
                break
        if clear:
            return lanes
    return None


def authority_seconds(world):
    summary = u.GameplayStatics.get_game_state(world).get_ecology_summary()
    return summary.get_editor_property("time").get_editor_property("server_time_seconds")
def finish(ok,error=""):
    (out/(name+".json")).write_text(json.dumps({"result":"PASS" if ok else "FAIL","error":error,"events":state["events"],"samples":state["samples"],"input_shots":state["shots"],"accepted":state["accepted"]},indent=2))
    u.log("[EcoRifleNetwork] "+name+" "+("PASS" if ok else "FAIL "+error))
    state["done"]=True
    world=state["world"] or next((w for w in u.ObjectIterator(u.World) if u.GameplayStatics.get_game_state(w)),None)
    if world:u.SystemLibrary.execute_console_command(world,"QUIT")


def observe_late_join(world, runtime, packet):
    if "survivor" not in packet:
        return
    assert not runtime.capture_population_traits(), "Late client can read the authority-only trait survey"
    assert not u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world), "Late client contains logical authority"
    visuals = [actor.visual_state for actor in u.GameplayStatics.get_all_actors_of_class(
        world, u.EcoCreatureRepresentationActor) if actor.get_editor_property("bound")]
    assert not any(visual.alive and int(visual.stable_agent_id) == packet["target"] for visual in visuals), (
        "Late client saw the killed animal alive")
    survivor = next((visual for visual in visuals if visual.alive and int(visual.stable_agent_id) == packet["survivor"]), None)
    if survivor is None:
        return
    assert abs(survivor.body_scale - packet["body_scale"]) < .00001, "Late client received a different body scale"
    assert abs(survivor.coat_tone - packet["coat_tone"]) < .00001, "Late client received a different coat tone"
    state["samples"].append({"survivor": packet["survivor"], "body_scale": survivor.body_scale,
                             "coat_tone": survivor.coat_tone,
                             "dead_target_not_alive": packet["target"], "authority_agents": 0})
    finish(True)


def prepare_late_join(world, runtime, players, state_packet):
    traits = json.loads(runtime.capture_population_traits())
    survivor = next(row for row in traits["agents"] if row["species"] == "Wolf" and row["region"] == "Riverbank"
                    and (not restore_checkpoint or int(row["id"]) == state["restored_survivor"]))
    point = u.Vector(*inspect(world, int(survivor["id"]))["native_world_position"])
    for player in players:
        pawn = player.get_controlled_pawn()
        pawn.player_state.set_invulnerable(True)
        pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
        pawn.set_actor_location(point + u.Vector(-500, 0, 96), False, True)
        pawn.character_movement.stop_movement_immediately()
    state_packet.update(survivor=int(survivor["id"]), body_scale=survivor["visual_body_scale"],
                        coat_tone=survivor["visual_coat_tone"])


def hunt_checkpoint_snapshot(world, runtime, target, survivor=None):
    traits = json.loads(runtime.capture_population_traits())
    fields = ("species", "region", "parent_a", "parent_b", "generation", "offspring", "origin", "born", "sex", "size_gene",
              "speed_gene", "caution_gene", "sociability_gene", "coat_gene", "visual_body_scale", "visual_maturity",
              "visual_coat_tone")
    living = {row["id"]: {field: row[field] for field in fields} for row in traits["agents"]}
    if survivor is None:
        survivor = next(int(agent) for agent, row in living.items() if row["species"] == "Wolf" and row["region"] == "Riverbank")
    dead = inspect(world, target)
    assert dead.get("hp") == 0. and str(target) not in living, "Checkpoint target is not a committed dead creature"
    stocks = {}
    # Dedicated game processes expose stock by patch ID, but not the editor's authoring array.
    for key in ("IslandRiverDrift", "IslandRiverRoots", "IslandForageWestMeadow"):
        stock = runtime.inspect_fauna_habitat_stock(key)
        if isinstance(stock, tuple):
            assert stock[0], f"Checkpoint fixture could not read stock for {key}"
            stock = stock[-1]
        assert stock is not None, f"Checkpoint fixture could not read stock for {key}"
        stocks[key] = stock
    return {"epoch": traits["epoch"], "authority_seconds": traits["completed_seconds"], "target": target,
            "fauna_breeding_opportunity": traits.get("fauna_breeding_opportunity", False),
            "functional_traits": traits["functional_traits"], "coat_palette": traits["coat_palette"],
            "coat_selection": traits["coat_selection"],
            "dead": {key: dead[key] for key in ("species", "region", "position", "hp")}, "survivor": survivor,
            "living_traits": living, "patch_stock": stocks}


def tick_restored_checkpoint(world, runtime):
    packet_path = out / "RestoredSession.json"
    if not server:
        try:
            packet = json.loads(packet_path.read_text())
        except (OSError, ValueError):
            return
        observe_late_join(world, runtime, packet)
        return
    if "restored_at" not in state:
        # The queued startup brain is applied at the first Native decision, after actor readiness.
        raw_startup = runtime.capture_population_traits()
        if not raw_startup:
            return
        startup = json.loads(raw_startup)
        if not any(row["species"] == "Herbivore" and row.get("native_adopted") for row in startup["agents"]):
            return
        saved = json.loads((out / "Checkpoint.json").read_text())
        assert runtime.load_ecosystem(checkpoint_slot), "Fresh authority failed to restore the hunt checkpoint"
        restored = hunt_checkpoint_snapshot(world, runtime, saved["target"], saved["survivor"])
        (out / "RestoredCheckpoint.json").write_text(json.dumps(restored, indent=2), encoding="utf-8")
        mismatched = [key for key, value in saved.items() if key != "epoch" and restored[key] != value]
        assert not mismatched, f"Restored authority differed in {mismatched}"
        state.update(restored_at=restored["authority_seconds"], restored_target=restored["target"],
                     restored_survivor=restored["survivor"])
        u.log("[EcoRifleNetwork] Restored authority ready")
    players = [pc for pc in u.GameplayStatics.get_all_actors_of_class(world, u.PlayerController)
               if (pawn := pc.get_controlled_pawn()) and pawn.player_state]
    elapsed = authority_seconds(world) - state["restored_at"]
    if players and not (out / "RestoredClient.json").exists():
        packet = {"target": state["restored_target"]}
        prepare_late_join(world, runtime, players, packet)
        packet_path.write_text(json.dumps(packet), encoding="utf-8")
    if elapsed >= 25. and (out / "RestoredClient.json").exists():
        client = json.loads((out / "RestoredClient.json").read_text())
        target = inspect(world, state["restored_target"])
        assert not target or target.get("hp") == 0., "Restored authority resurrected the hunted creature"
        assert client["result"] == "PASS" and runtime.get_combat_diagnostics().hunting_deaths == 0, (
            "Restore replayed the old death or the restored client failed")
        state["samples"].append({"authority_elapsed": elapsed, "new_hunting_deaths": 0})
        finish(True)


def read_packet(filename):
    try:
        return json.loads((out / filename).read_text())
    except (OSError, ValueError):
        return None


def isolate_riverbank_rain(world):
    regions = {str(region.get_editor_property("region_id")): region
               for region in u.GameplayStatics.get_all_actors_of_class(world, u.EcologyRegion)}
    for adapter in u.GameplayStatics.get_all_actors_of_class(world, u.EcoRegionEnvironmentAdapter):
        targets = [str(value) for value in adapter.get_editor_property("region_ids")] or list(regions)
        if "Riverbank" not in targets:
            continue
        remaining = [target for target in targets if target != "Riverbank"]
        if remaining:
            adapter.set_editor_property("region_ids", remaining)
        else:
            adapter.set_editor_property("cycle_rainfall", False)
            adapter.set_editor_property("apply_authored_weather", False)
    region = regions["Riverbank"]
    weather = region.get_environment_state()
    weather.set_editor_property("rainfall", .8)
    weather.set_editor_property("weather_state", u.EcoWeatherState.RAIN)
    region.set_environment_state(weather)
    return region.get_environment_state().get_editor_property("rainfall")


def ground_approach(world, pawn, position, offset):
    ground = u.EcoCreatureAnimationBuilder.project_placement_point(world, position + offset)
    if ground is None or abs(ground.z - position.z) > 40.:
        return None
    center = ground + u.Vector(0., 0., pawn.capsule_component.get_scaled_capsule_half_height())
    if u.SystemLibrary.line_trace_single_for_objects(world, position + u.Vector(0., 0., 40.), center,
            [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, False):
        return None
    return center


def creature_position(agent):
    return u.Vector(*map(float, re.findall(r"[XYZ]=([-+\d.eE]+)", agent["position"])))


def tick_ambush_client(world, runtime):
    pawn = u.GameplayStatics.get_player_pawn(world, 0)
    if not pawn or not isinstance(pawn.player_state, u.EcoPlayerState):
        return
    if not state.get("bound"):
        player_id = pawn.player_state.get_editor_property("player_id")
        (out / (name + "_Pawn.json")).write_text(json.dumps({"player_id": player_id}))
        state["bound"] = True
    packet = read_packet("AmbushSession.json")
    if not packet:
        return
    seen = state.setdefault("activities", {})
    for representation in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor):
        if not representation.get_editor_property("bound"):
            continue
        visual = representation.visual_state
        if int(visual.stable_agent_id) == packet["leopard"]:
            label = str(visual.get_editor_property("activity"))
            for phase in ("Stalk", "Attack"):
                if phase.upper() in label.upper():
                    seen.setdefault(phase, int(visual.sequence))
            break
    if not read_packet("AmbushContact.json"):
        return
    health = pawn.player_state.get_health()
    expected = packet["health"][name] - (20. if name == "A" else 0.)
    if set(seen) != {"Stalk", "Attack"} or abs(health - expected) > .01:
        return
    assert seen["Stalk"] < seen["Attack"], "Replicated attack did not follow the stalk"
    assert not u.EcoCreatureInspectionLibrary.get_authority_agent_ids(world), "Client contains authority creatures"
    assert not runtime.capture_population_traits(), "Client can read authority traits"
    state["samples"].append({"leopard": packet["leopard"], "health": health, "activities": seen, "authority_agents": 0})
    finish(True)


def tick_ambush_server(world, runtime):
    trial = state.setdefault("ambush", {"positions": {}, "activities": []})
    if "rain" not in trial:
        assert "-EcoRuleFaunaPlayerAmbush" in cmd.split(), "Ambush opt-in is missing"
        trial["rain"] = isolate_riverbank_rain(world)
    players = {}
    for role in ("A", "B"):
        ready = read_packet(role + "_Pawn.json")
        if not ready:
            return
        for controller in u.GameplayStatics.get_all_actors_of_class(world, u.PlayerController):
            pawn = controller.get_controlled_pawn()
            if pawn and isinstance(pawn.player_state, u.EcoPlayerState) and (
                    pawn.player_state.get_editor_property("player_id") == ready["player_id"]):
                players[role] = pawn
                break
    if len(players) != 2:
        assert "contact" in trial or "leopard" not in trial, "A player left before verified contact"
        if "contact" in trial and all(read_packet(role + ".json") for role in ("A", "B")):
            state["samples"].append(trial["contact"])
            finish(True)
        return
    assert players["A"] != players["B"], "Both roles mapped to the same player"
    now = u.GameplayStatics.get_time_seconds(world)
    if now < trial.get("next_sample", 0.):
        return
    trial["next_sample"] = now + .15
    health = {role: pawn.player_state.get_health() for role, pawn in players.items()}
    if "leopard" not in trial:
        for identity in (71, 72):
            agent = inspect(world, identity)
            if not agent or agent["species"] != "Leopard" or agent["region"] != "Riverbank" or agent["hp"] <= 0.:
                continue
            position = creature_position(agent)
            previous = trial["positions"].get(identity)
            trial["positions"][identity] = position
            if previous is None or agent.get("energy_fraction", 1.) >= .79:
                continue
            heading = position - previous
            heading.z = 0.
            if heading.length() < 5.:
                continue
            heading = heading * (1. / heading.length())
            offsets = {"A": heading * 320., "B": heading * 625. + u.Vector(-heading.y, heading.x, 0.) * 80.}
            centers = {role: ground_approach(world, pawn, position, offsets[role]) for role, pawn in players.items()}
            if any(center is None for center in centers.values()):
                continue
            for role, pawn in players.items():
                pawn.character_movement.stop_movement_immediately()
                assert pawn.set_actor_location(centers[role], False, True), "Failed to place player on verified ground"
            packet = {"leopard": identity, "start": now, "health": health, "rain": trial["rain"],
                      "initial_distances_cm": {role: (point - position).length() for role, point in centers.items()}}
            trial.update(packet)
            (out / "AmbushSession.json").write_text(json.dumps(packet))
            u.log(f"[EcoRifleNetwork] Ambush staged {packet}")
            return
        return
    agent = inspect(world, trial["leopard"])
    assert agent and now - trial["start"] < 18., f"Ambush did not settle: {trial['activities'][-12:]}, {health}"
    assert health["B"] == trial["health"]["B"], "The observer received damage"
    trial["activities"].append({"time": now, "activity": agent["activity"], "health": health,
                               "distance_cm": (creature_position(agent) - players["A"].get_actor_location()).length()})
    if "contact" in trial:
        assert health == trial["contact"]["health_after"], "Damage was charged again"
        if all(read_packet(role + ".json") for role in ("A", "B")):
            state["samples"].append(trial["contact"])
            finish(True)
        return
    if health["A"] == trial["health"]["A"]:
        return
    assert abs(trial["health"]["A"] - health["A"] - 20.) < .01, "Expected one contact damage charge"
    assert all(any(phase in row["activity"] for row in trial["activities"]) for phase in ("Stalk", "Attack")), (
        "Server damage did not have an observed stalk and preparation")
    trial["contact"] = {"leopard": trial["leopard"], "rain": trial["rain"], "health_before": trial["health"],
                        "health_after": health, "initial_distances_cm": trial["initial_distances_cm"],
                        "activities": trial["activities"][:]}
    (out / "AmbushContact.json").write_text(json.dumps(trial["contact"], indent=2))


def tick(dt):
    try:
        assert time.monotonic()<state["deadline"],"network timeout"
        w=next((w for w in u.ObjectIterator(u.World) if w.get_name()==map_name and u.GameplayStatics.get_game_state(w) and (server or u.GameplayStatics.get_player_controller(w,0))),None)
        state["world"]=w
        if not w:return
        runtimes=u.GameplayStatics.get_all_actors_of_class(w,u.EcoCreatureIntegrationSpawner)
        if not runtimes or not runtimes[0].is_runtime_ready():return
        runtime=runtimes[0]
        if rule_ambush:
            if server:
                tick_ambush_server(w, runtime)
            else:
                tick_ambush_client(w, runtime)
            return
        if restore_checkpoint:
            tick_restored_checkpoint(w, runtime)
            return
        if server and not state.get("logging"):
            u.SystemLibrary.execute_console_command(w,"Log LogTemp Verbose")
            u.SystemLibrary.execute_console_command(w,"eco.Inspection.GameplayReasons 1")
            state["logging"]=True
        if server:
            pcs=[p for p in u.GameplayStatics.get_all_actors_of_class(w,u.PlayerController)
                 if (pawn := p.get_controlled_pawn()) and pawn.player_state]
            if len(pcs)<2 and "start" not in state:return
            if "target" not in state:
                animals=[inspect(w,k) for k in u.EcoCreatureInspectionLibrary.get_authority_agent_ids(w)]
                wolves = [a for a in animals if a.get("species") == "Wolf" and a.get("hp", 0) > 0]
                target = next((a for a in wolves if saved_island and int(a["stable_id"]) == 49), wolves[0])
                if saved_island:
                    traits = json.loads(runtime.capture_population_traits())
                    assert len({row["species"] for row in traits["agents"]}) == 16, "Server trait survey missed a species"
                state["target"]=int(target["stable_id"]);state["hp"]=target["hp"];state["start"]=time.time()
            animal=inspect(w,state["target"]);elapsed=time.time()-state["start"]
            if animal.get("hp",0)>0:
                point=u.Vector(*animal["native_world_position"])
                active_client = "B" if elapsed < 9 else "A"
                try:
                    player_id = json.loads((out/(active_client+"_Pawn.json")).read_text())["player_id"]
                except (OSError, ValueError):
                    player_id = None
                lanes = shared_lane_offsets(w, state["target"], point) if shared_target and elapsed >= 9. else None
                state["shared_lanes_clear"] = lanes is not None
                for i,pc in enumerate(pcs):
                    pawn=pc.get_controlled_pawn();pawn.player_state.set_invulnerable(True)
                    pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
                    active = pawn.player_state.get_editor_property("player_id") == player_id if player_id is not None else i == 0
                    offset = u.Vector(-650 if active else -1500,0,96)
                    if lanes:
                        offset = lanes[0 if active else 1]
                    pawn.set_actor_location(point+offset,False,True)
                    pawn.character_movement.stop_movement_immediately()
                    pawn.set_actor_rotation(u.Rotator(0,0,0),True)
            elif shared_target and "death_time" not in state:
                state["death_time"] = authority_seconds(w)
            if (checkpoint_slot and "death_time" in state and not state.get("checkpoint_saved")
                    and runtime.get_combat_diagnostics().hunting_deaths == 1):
                assert authority_seconds(w) < state["death_time"] + 4., "No checkpoint boundary while the carcass was fresh"
                if runtime.save_ecosystem(checkpoint_slot):
                    snapshot = hunt_checkpoint_snapshot(w, runtime, state["target"])
                    (out / "Checkpoint.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
                    state["checkpoint_saved"] = True
            if shared_target and elapsed > 21.:
                if "original_players" not in state:
                    state["original_players"] = [json.loads((out/(peer+"_Pawn.json")).read_text())["player_id"]
                                                 for peer in ("A", "B")]
                shooter, observer = state["original_players"]
                present = {pc.get_controlled_pawn().player_state.get_editor_property("player_id") for pc in pcs}
                if observer in present and shooter not in present:
                    state["shooter_departed"] = True
                    if present - {observer}:
                        state["observer_overlapped_late"] = True
            if elapsed>=state.get("next_packet",0):
                state["next_packet"]=elapsed+.06
                packet={"target":state["target"],"start":state["start"],"position":animal.get("native_world_position")}
                if shared_target:
                    packet["hp"] = animal.get("hp", 0.)
                    packet["shared_phase"] = "miss" if elapsed < 9. else "first_hits" if packet["hp"] > 40. else "finish"
                    packet["shared_lanes_clear"] = state.get("shared_lanes_clear", False)
                if saved_island and elapsed >= 23. and (not shared_target or state.get("shooter_departed")):
                    assert runtime.get_combat_diagnostics().hunting_deaths == 1, "Expected exactly one committed hunting death"
                    prepare_late_join(w, runtime, pcs, packet)
                (out/"Session.json").write_text(json.dumps(packet))
            if 7<elapsed<8:assert animal.get("hp")==state["hp"],"hidden client damaged the target"
            if elapsed>23:
                assert runtime.get_combat_diagnostics().damage_committed>0,"visible client never applied damage"
                if saved_island:
                    assert elapsed < 70., "Returning client did not receive the authoritative survivor"
                    late_report = out / "Late.json"
                    if not late_report.exists():
                        return
                    assert json.loads(late_report.read_text())["result"] == "PASS", "Returning client did not pass"
                if shared_target and authority_seconds(w) < state["death_time"] + 25.:
                    return
                if shared_target:
                    assert state.get("observer_overlapped_late"), "The observer did not stay online through the new connection"
                if checkpoint_slot:
                    assert state.get("checkpoint_saved"), "No checkpoint was saved after the hunt"
                state["samples"].append({"target":state["target"],"hidden_phase_hp":state["hp"],"committed":runtime.get_combat_diagnostics().damage_committed,
                                         "deaths":runtime.get_combat_diagnostics().hunting_deaths,
                                         "shooter_departed":state.get("shooter_departed",False),
                                         "observer_overlapped_late":state.get("observer_overlapped_late",False)})
                finish(True)
        else:
            if not (out/"Session.json").exists():return
            try:
                session=json.loads((out/"Session.json").read_text())
            except (OSError, ValueError):
                return
            if name == "Late":
                observe_late_join(w, runtime, session)
                return
            elapsed=time.time()-session["start"]
            pc=u.GameplayStatics.get_player_controller(w,0);pawn=pc.get_controlled_pawn()
            if not pawn or not pawn.player_state:return
            fire=pawn.get_component_by_class(u.EcoWeaponFireComponent)
            if not state.get("bound"):
                fire.on_damage_outcome.add_callable(event)
                fire.on_shot.add_callable(shot)
                (out/(name+"_Pawn.json")).write_text(json.dumps({"player_id":pawn.player_state.get_editor_property("player_id")}))
                state["bound"]=True
            visuals=[v for v in u.GameplayStatics.get_all_actors_of_class(w,u.EcoCreatureRepresentationActor) if v.get_editor_property("bound")]
            if name=="B" and not shared_target:
                for v in visuals:v.set_actor_hidden_in_game(True)
            target=next((v for v in visuals if int(v.visual_state.stable_agent_id)==session["target"]),None)
            if shared_target and target:
                # Observe the actual body state, including the dead body before the proxy retires.
                status = "alive" if target.visual_state.alive else "dead"
                if status not in state.setdefault("seen_body_states", {}):
                    state["seen_body_states"][status] = {"id": session["target"], "sequence": target.visual_state.sequence,
                                                         "body_scale": target.visual_state.body_scale}
            avatar=pawn.get_component_by_class(u.EcoAbilityAvatarComponent)
            equipment=pawn.get_component_by_class(u.EcoEquipmentComponent)
            aim=pawn.get_component_by_class(u.EcoAimComponent)
            if equipment.get_editor_property("weapon") and not aim.get_editor_property("aiming") and elapsed>=state.get("next_aim",0):
                state["next_aim"]=elapsed+.5
                avatar.release_configured_action(aim_action)
                avatar.press_configured_action(aim_action)
            if session.get("position") and (target or name=="B") and 2<elapsed<20:
                camera=pawn.get_component_by_class(u.CameraComponent)
                deliberate_miss = name == "B" and (not shared_target or session.get("shared_phase") == "miss")
                point=(pawn.get_actor_location()+u.Vector(0,6000,300)
                       if deliberate_miss else u.Vector(*session["position"])+u.Vector(0,0,45))
                pc.set_control_rotation(u.MathLibrary.find_look_at_rotation(camera.get_world_location(),point))
                allowed=(name=="B" and 3<elapsed<7) or (name=="A" and 10<elapsed<19)
                if shared_target and 10. < elapsed < 20.:
                    allowed = session.get("shared_lanes_clear") and target and target.visual_state.alive and (session["shared_phase"] == "finish"
                              or session["shared_phase"] == "first_hits" and not committed_damage(session["target"]))
                if allowed and elapsed>=state["next"]:
                    state["next"]=elapsed+.6
                    avatar.release_configured_action(fire_action)
                    avatar.press_configured_action(fire_action)
                    state["shots"]+=1
            if elapsed>21:
                assert state["shots"]>0,"configured fire input never sent"
                assert not u.EcoCreatureInspectionLibrary.get_authority_agent_ids(w),"client contains logical authority"
                if saved_island:
                    assert not runtime.capture_population_traits(), "Client can read the authority-only trait survey"
                if shared_target:
                    if elapsed < 33. and "dead" not in state.get("seen_body_states", {}):
                        return
                    assert committed_damage(session["target"]) > 0., "No owner damage delivered for the shared target"
                    assert set(state.get("seen_body_states", {})) == {"alive", "dead"}, "Client missed the target life-to-death representation"
                    live, dead = (state["seen_body_states"][status] for status in ("alive", "dead"))
                    assert dead["sequence"] > live["sequence"], "Death representation did not advance the target sequence"
                    sample = {"target_damage":committed_damage(session["target"]),"body_states":state["seen_body_states"]}
                    if name == "B":
                        late_report = out / "Late.json"
                        if not late_report.exists() or "survivor" not in session:
                            assert elapsed < 65., "The resident observer never saw a completed late connection"
                            return
                        try:
                            late = json.loads(late_report.read_text())
                        except (OSError, ValueError):
                            return
                        observer_survivor = next((actor.visual_state for actor in visuals if actor.visual_state.alive
                                                  and int(actor.visual_state.stable_agent_id) == session["survivor"]), None)
                        if not observer_survivor:
                            assert elapsed < 65., "The observer never received the late client's survivor"
                            return
                        assert late["result"] == "PASS" and late["samples"][0]["survivor"] == session["survivor"]
                        assert abs(late["samples"][0]["body_scale"] - observer_survivor.body_scale) < .00001
                        assert not target or not target.visual_state.alive, "The target appeared alive after the new connection"
                        sample["observed_late_survivor"] = session["survivor"]
                    state["samples"].append(sample)
                    finish(True)
                    return
                if name=="A":assert any("COMMITTED" in e["result"] for e in state["events"]),"owner outcome not delivered"
                else:
                    assert state["accepted"]>0,"deliberate miss was never approved"
                    assert not any(e["damage"]>0 for e in state["events"]),"deliberate miss committed damage"
                state["samples"].append({"visuals":len(visuals),"input_shots":state["shots"]});finish(True)
    except Exception:finish(False,traceback.format_exc())
def ticker(dt):
    if state.get("in_tick") or state.get("done"):
        return not state.get("done",False)
    state["in_tick"]=True
    try:
        tick(dt)
    finally:
        state["in_tick"]=False
    return not state.get("done",False)
handle=u.register_ticker_callback(ticker,0.0)

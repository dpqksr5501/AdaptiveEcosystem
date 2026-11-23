"""Compare the saved island authority's morphology payload with two PIE clients."""

from collections import defaultdict, deque
import json
from pathlib import Path
import re
import time
import traceback

import unreal as u


MAP = "LV_JYU_IslandEcosystemRefreshed"
SPECIES = ("GoldenEagle", "Mink", "Leopard", "Fox", "Crow", "Rat", "Jackrabbit", "Bighorn",
           "Horse", "Pig", "Buffalo", "Wolf", "AriakeCatfish", "CommonCarp", "UnidentifiedFish", "Herbivore")
FIELDS = ("body_scale", "maturity", "coat_tone", "body_condition", "appearance", "inherited_length", "inherited_width",
          "body_development")
NEUTRAL_BODY = 0x80808080
OFFSETS = (u.Vector(-360., -160., 130.), u.Vector(360., 160., 130.))
command = u.SystemLibrary.get_command_line()
label = re.search(r"(?:^|\s)-EcoMorphologyRun=(\w+)\b", command)
if not label:
    raise RuntimeError("Set -EcoMorphologyRun to a fresh report name")
output = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit" / label[1]
output.mkdir(parents=True, exist_ok=False)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
inspection = u.EcoCreatureInspectionLibrary
started = time.monotonic()
report = {"map": MAP, "samples": [], "error": None}
history = defaultdict(deque)
next_sample = 0.
queue = deque()
focus = None
focus_since = 0.
initialized = False


def inspect_agent(world, stable_id):
    result = inspection.capture_agent(world, stable_id)
    raw = next((item for item in result if isinstance(item, str)), "") if isinstance(result, tuple) else result
    return json.loads(raw) if raw else {}


def capture_position(world, stable_id):
    row = inspect_agent(world, stable_id)
    if not row:
        return None
    values = row.get("native_world_position") or [float(value) for value in re.findall(r"[XYZ]=([-+\d.eE]+)", row["position"])]
    return u.Vector(*values)


def client_row(world, stable_id):
    actor = next((item for item in u.GameplayStatics.get_all_actors_of_class(world, u.EcoCreatureRepresentationActor)
                  if item.get_editor_property("bound") and not item.get_editor_property("hidden")
                  and int(item.visual_state.stable_agent_id) == stable_id), None)
    if not actor:
        return None
    state = actor.visual_state
    if not state.alive or state.sequence < 2:
        return None
    visible = []
    for name in ("creature_mesh", "immature_mesh"):
        component = actor.get_editor_property(name)
        if not component.is_visible():
            continue
        component.set_editor_property("visibility_based_anim_tick_option",
                                      u.VisibilityBasedAnimTickOption.ALWAYS_TICK_POSE_AND_REFRESH_BONES)
        mesh = component.get_skeletal_mesh_asset()
        animation = component.get_anim_instance()
        if not mesh or not animation:
            return None
        _, extent, _ = u.SystemLibrary.get_component_bounds(component)
        relative = component.get_editor_property("relative_scale3d").to_tuple()
        world_scale = component.get_world_scale().to_tuple()
        if not all(abs(actual - local * state.body_scale) < .0001 for local, actual in zip(relative, world_scale)):
            raise RuntimeError(f"Mesh component scale does not inherit BodyScale for {stable_id}/{name}")
        if min(extent.to_tuple()) <= 0.:
            raise RuntimeError(f"Empty component bounds for {stable_id}/{name}")
        visible.append({"component": name, "asset": mesh.get_path_name(), "animation": animation.get_class().get_path_name(),
                        "relative_scale": relative, "world_scale": world_scale, "bounds_half_cm": extent.to_tuple()})
    if not visible:
        return None
    body = actor.get_visual_body_development()
    displaced = actor.get_displaced_joint_count()
    if body != NEUTRAL_BODY and displaced < 2:
        return None
    actor_scale = actor.get_actor_scale3d().to_tuple()
    if not all(abs(value - state.body_scale) < .0001 for value in actor_scale):
        raise RuntimeError(f"Actor scale differs from the received BodyScale for {stable_id}")
    inspected = inspect_agent(world, stable_id)
    if not inspected or "visual_maturity" not in inspected:
        return None
    if inspected["authority"] or {"life", "development", "size_gene", "parent_a"} & inspected.keys():
        raise RuntimeError(f"The passive inspection record exposes logical state for {stable_id}")
    if abs(inspected["body_scale"] - state.body_scale) > .00001 or abs(inspected["visual_maturity"] - state.maturity) > .00001:
        # A newly arrived replication sample can precede the next representation update.
        return None
    return {"world": world.get_path_name(), "actor": actor.get_path_name(), "species": str(state.species_id),
            "id": stable_id, "actor_scale": actor_scale, "sequence": state.sequence, "meshes": visible,
            "body_scale": state.body_scale, "maturity": state.maturity, "coat_tone": state.coat_tone,
            "body_condition": state.body_condition, "appearance": state.appearance,
            "inherited_length": state.inherited_length, "inherited_width": state.inherited_width,
            "body_development": body, "displaced_joints": displaced}


def choose_targets(agents, functional_traits):
    by_species = defaultdict(list)
    for row in agents:
        by_species[row["species"]].append(row)
    if set(by_species) != set(SPECIES):
        raise RuntimeError(f"Incomplete initial island species {sorted(by_species)}")
    juvenile = max((row for row in by_species["Herbivore"] if 0. < row["maturity"] < .85),
                   key=lambda row: row["energy"])
    queue.append(("juvenile", juvenile))
    for species in SPECIES:
        adults = [row for row in by_species[species] if row["maturity"] >= 1.]
        def shape(row):
            return (row["visual_body_development"],) if functional_traits else (row["visual_body_scale"],)

        small = min(adults, key=shape)
        large = max(adults, key=shape)
        if shape(small) == shape(large):
            raise RuntimeError(f"No distinct adult proportions for {species}")
        queue.extend((("small_adult", small), ("large_adult", large)))
    queue.append(("growing", juvenile))


def finish(error=None):
    report["error"] = error
    uses = defaultdict(set)
    for sample in report["samples"]:
        for row in sample["clients"]:
            uses[row["actor"]].add(row["id"])
    report["rebound_actors"] = {actor: sorted(ids) for actor, ids in uses.items() if len(ids) > 1}
    (output / "IslandMorphology.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    u.log(f"ECO_ISLAND_MORPHOLOGY {'FAIL' if error else 'PASS'} {len(report['samples'])}")
    u.unregister_slate_post_tick_callback(handle)
    levels.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def tick(_):
    global next_sample, focus, focus_since, initialized
    try:
        if time.monotonic() - started > 155.:
            raise RuntimeError(f"PIE deadline, current target {focus[0:2] if focus else None}")
        worlds = [w for w in u.ObjectIterator(u.World) if "/UEDPIE_" in w.get_path_name() and w.get_name().endswith(MAP)]
        authority = next((w for w in worlds if u.GameplayStatics.get_game_mode(w)), None)
        clients = sorted((w for w in worlds if w != authority and u.GameplayStatics.get_player_controller(w, 0)),
                         key=lambda w: w.get_path_name())
        if not authority or len(clients) != 2:
            return
        now = u.GameplayStatics.get_time_seconds(authority)
        if now < next_sample:
            return
        next_sample = now + .14
        runtime = u.GameplayStatics.get_actor_of_class(authority, u.EcoCreatureIntegrationSpawner)
        raw = runtime.capture_population_traits() if runtime else None
        if not raw:
            return
        traits = json.loads(raw)
        agents = {int(row["id"]): row for row in traits["agents"]}
        viewers = sorted((pc for pc in u.GameplayStatics.get_all_actors_of_class(authority, u.PlayerController)
                          if pc.get_controlled_pawn()), key=lambda pc: pc.get_path_name())
        if len(viewers) != 2:
            return
        if not initialized:
            choose_targets(agents.values(), traits["functional_traits"])
            report.update(epoch=traits["epoch"], initial_population=len(agents), functional_traits=traits["functional_traits"],
                          clients=[w.get_path_name() for w in clients])
            initialized = True
        for world in clients:
            remote = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
            if not remote or not remote.is_runtime_ready():
                return
            if remote.capture_population_traits() or inspection.get_authority_agent_ids(world):
                raise RuntimeError("A client exposes authority state")
        if focus is None:
            if not queue:
                first = report["samples"][0]["authority"]
                last = report["samples"][-1]["authority"]
                if first["id"] != last["id"] or last["visual_maturity"] <= first["visual_maturity"]:
                    raise RuntimeError("Juvenile growth did not reach the actual representations")
                finish()
                return
            focus = queue.popleft()
            focus_since = now
        phase, initial = focus
        stable_id = int(initial["id"])
        row = agents.get(stable_id)
        if not row:
            raise RuntimeError(f"Target {stable_id} ({initial['species']}) died before visual sampling")
        recent = history[stable_id]
        recent.append((now, row))
        while recent[0][0] < now - 1.:
            recent.popleft()
        location = capture_position(authority, stable_id)
        if location is not None:
            for viewer, offset in zip(viewers, OFFSETS):
                pawn = viewer.get_controlled_pawn()
                pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
                pawn.set_actor_location(location + offset, False, True)
                pawn.character_movement.stop_movement_immediately()
        if now - focus_since < .42:
            return
        observed = [client_row(world, stable_id) for world in clients]
        for received in observed:
            if received is None:
                break
            match = next((sample for _, sample in reversed(recent) if all(
                abs(received[name] - sample[f"visual_{name}"]) < .00001 for name in FIELDS)), None)
            if match is None:
                break
            if received["species"] != match["species"]:
                raise RuntimeError(f"Client representation uses a different species for {stable_id}")
            received["matched_sample_seconds"] = match["sample_seconds"]
        else:
            report["samples"].append({"phase": phase, "time": now, "authority": row, "clients": observed})
            focus = None
            return
        if now - focus_since > 5.:
            raise RuntimeError(f"Two clients did not match {phase} {initial['species']} {stable_id}: {observed}")
    except Exception:
        finish(traceback.format_exc())


if not editor.get_editor_world().get_name().endswith(MAP):
    raise RuntimeError("Launch the network audit on the saved owned island")
levels.editor_request_begin_play()
handle = u.register_slate_post_tick_callback(tick)

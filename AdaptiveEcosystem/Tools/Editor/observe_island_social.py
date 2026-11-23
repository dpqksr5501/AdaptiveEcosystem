"""Camera-only observation and rendered reply evidence for the island network audit."""

from collections import defaultdict
from itertools import combinations
import json
import re

import unreal as u


RANGES = {
    "Leopard": 430, "GoldenEagle": 620, "Mink": 320, "AriakeCatfish": 350,
    "Fox": 400, "Rat": 240, "Bighorn": 540, "Crow": 620,
    "Jackrabbit": 350, "UnidentifiedFish": 300, "CommonCarp": 450,
    "Wolf": 650, "Herbivore": 750, "Horse": 650, "Buffalo": 700, "Pig": 480,
}
FISH = {"AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
SMALL = FISH | {"Mink", "Rat", "Fox", "Jackrabbit", "Crow", "GoldenEagle"}
PRIORITY = {"Leopard", "GoldenEagle", "Mink", "AriakeCatfish"}
CALM = {"Hold", "Wander", "Graze", "Rest", "SatedRest", "Regroup", "Fly", "Swim"}


def point(text):
    values = dict(re.findall(r"([XYZ])=([-+\d.eE]+)", text))
    return u.Vector(*(float(values.get(axis, 0)) for axis in "XYZ"))


def view_obstruction(world, origin, target, allow_water):
    hits = u.SystemLibrary.line_trace_multi_for_objects(world, origin, target,
        [u.ObjectTypeQuery.OBJECT_TYPE_QUERY1], False, [], u.DrawDebugTrace.NONE, True) or []
    for hit in hits:
        obj = hit.to_tuple()[9]
        kind = obj.get_class().get_name() if obj else "UnknownWorldStatic"
        if not (allow_water and kind.startswith("WaterBody")):
            return kind
    return None


def locate_pairs(agents):
    buckets = defaultdict(list)
    for row in agents:
        kind = row["species"]
        if kind not in RANGES or row.get("hp", 0.) <= 0. or row["activity"].split("::")[-1] not in CALM:
            continue
        if row.get("presentation_eating") or row.get("sense", "").split("::")[-1] != "None":
            continue
        rule = row.get("rule_fauna", {})
        medium = "water" if kind in FISH or rule.get("swimming") else "air" if rule.get("flight_phase") else "ground"
        if rule.get("shore_phase") or (medium == "air" and rule.get("flight_phase") != 2):
            continue
        buckets[kind, row["region"], medium].append((row, point(row["position"])))
    best = {}
    for (kind, _, medium), rows in buckets.items():
        for (a, left), (b, right) in combinations(rows, 2):
            distance = (left - right).length()
            if distance > RANGES[kind] * 1.12 or (medium == "ground" and abs(left.z - right.z) > 120):
                continue
            signal = int(a.get("social_signal", 0) > 0 or b.get("social_signal", 0) > 0)
            last_done = max(a.get("development", {}).get("last_social_at", -1),
                            b.get("development", {}).get("last_social_at", -1))
            score = (-signal, last_done, distance)
            if kind not in best or score < best[kind][0]:
                best[kind] = (score, medium, a, b, left, right)
    return best


def covered_by_clients(out):
    known = set()
    for name in ("ClientA", "ClientB"):
        try:
            known.update(json.loads((out / f"{name}_SocialProgress.json").read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return known


def write_json(path, payload):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    try:
        tmp.replace(path)
        return True
    except OSError:
        return False


def position_observers(world, out, agents, state, elapsed, late_join=False):
    """Only steer normal peers' viewpoints. No writes to wildlife or its memory."""
    watches = state.setdefault("social_watches", {})
    cooldown = state.setdefault("social_camera_retry", {})
    if elapsed >= state.get("social_refresh", 0):
        state["social_pairs"] = locate_pairs(agents)
        state["social_known"] = covered_by_clients(out)
        state["social_refresh"] = elapsed + 1.
    best, known = state["social_pairs"], state["social_known"]
    controllers = u.GameplayStatics.get_all_actors_of_class(world, u.PlayerController)
    occupied = set()
    focused = set()
    for controller in controllers:
        pawn = controller.get_controlled_pawn()
        if not pawn:
            continue
        key = controller.get_path_name()
        slots = state.setdefault("social_slots", {})
        if key not in slots:
            name = "ClientA" if not slots else "ClientB"
            slots[key] = name
            movement = pawn.get_component_by_class(u.CharacterMovementComponent)
            if movement:
                movement.disable_movement()
        name = slots[key]
        kind, since = watches.get(key, (None, elapsed))
        if late_join:
            visits = state.setdefault("late_social_visits", {})
            observed = state.setdefault("late_social_observed", {})
            first = visits.setdefault(name, elapsed)
            if (out / f"{name}_SocialProgress.json").exists():
                observed.setdefault(name, elapsed)
            if elapsed >= first + 24. or elapsed >= observed.get(name, elapsed) + 3.:
                (out / f"{name}_SocialView.json").unlink(missing_ok=True)
                continue
            choices = [candidate for candidate in best if candidate not in occupied]
            pending = [candidate for candidate in choices if best[candidate][0][0] < 0]
            if kind not in choices or (pending and kind not in pending) or elapsed - since >= 7.:
                pool = pending or choices
                kind = min(pool, key=lambda candidate: best[candidate][0], default=None)
                since = elapsed
            if kind is None:
                continue
        elif kind and kind not in known and elapsed - since >= 24:
            cooldown[kind] = elapsed + 8.
        if not late_join and (not state.get("social_released") or state.get("social_opening_game_end")):
            opening = state["social_opening"][name]
            if opening not in best:
                continue  # Keep the last observation position while the opening pair is exchanging signals.
            kind, since = opening, elapsed
        elif not late_join and (kind not in best or kind in known or kind in occupied or elapsed - since >= 24):
            options = [k for k in RANGES if k in best and k not in known and k not in occupied
                       and elapsed >= cooldown.get(k, 0.)]
            pool = [k for k in options if k in PRIORITY] or options
            active = [k for k in pool if best[k][0][0] < 0]
            kind = next(iter(active or pool), None)
            if kind is None:
                kind = next(iter(k for k in best if k not in occupied and k not in known), None)
            if not kind:
                continue
            since = elapsed
        watches[key] = (kind, since)
        occupied.add(kind)
        focused.add(key)
        _, medium, a, b, left, right = best[kind]
        center = (left + right) * .5
        lift = 9 if medium == "water" else 24 if kind in SMALL else 95
        aim = center + u.Vector(0, 0, lift)
        lateral = right - left
        perpendicular = u.Vector(lateral.y, -lateral.x, 0)
        horizontal = perpendicular.length()
        axis = perpendicular / horizontal if horizontal > .1 else u.Vector(1, 0, 0)
        distance = max(470 if kind in SMALL else 580, lateral.length() * .95)
        height = 8 if medium == "water" else 155 if kind == "Mink" else 85 if kind in SMALL else 180
        candidates = [aim + axis.rotate_angle_axis(angle, u.Vector(0, 0, 1)) * distance + u.Vector(0, 0, height)
                      for angle in (0., 180., 45., -45., 135., -135., 90., -90.)]
        eye = next((p for p in candidates if not view_obstruction(world, p, aim, medium == "water")), candidates[0])
        # The authored third-person rig has a 400 cm boom. Keep the pawn between the expected eye and the pair.
        into_view = (aim - eye) / (aim - eye).length()
        pawn.set_actor_location(eye + into_view * 400., False, True)
        controller.set_control_rotation(u.MathLibrary.find_look_at_rotation(eye, aim))
        write_json(out / f"{name}_SocialView.json", dict(aim=list(aim.to_tuple()), eye=list(eye.to_tuple()), species=kind,
                   ids=[a["stable_id"], b["stable_id"]]))
        pair = [a["stable_id"], b["stable_id"]]
        previous = state.setdefault("social_target_keys", {}).get(key)
        if previous != (kind, pair):
            state["social_target_keys"][key] = (kind, pair)
            state["observer_targets"].append(dict(elapsed=elapsed, client=name, species=kind, ids=pair, medium=medium))
    return focused


def sample_client(game, elapsed, state, out, name):
    if elapsed < state.get("social_next", 0):
        return
    state["social_next"] = elapsed + .17
    pc = u.GameplayStatics.get_player_controller(game, 0)
    camera = u.GameplayStatics.get_player_camera_manager(game, 0)
    game_state = u.GameplayStatics.get_game_state(game)
    if not pc or not camera or not game_state:
        return
    try:
        view = json.loads((out / f"{name}_SocialView.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        view = None
    pawn = pc.get_controlled_pawn()
    desired_eye = None
    previous_camera = state.get("social_fixture_camera")
    if view is None and previous_camera and pawn:
        pc.set_view_target_with_blend(pawn, 0.)
        previous_camera.destroy_actor()
        state.pop("social_fixture_camera")
    if view and pawn:
        target = u.Vector(*view["aim"])
        location = pawn.get_actor_location()
        if (target - location).length() < 1600.:
            desired_eye = u.Vector(*view["eye"])
            if view["species"] == "Mink":
                viewpoints = [target + u.Vector(x, y, 420) for x, y in ((115, 75), (-115, -75), (0, 0))]
                desired_eye = next((p for p in viewpoints if not view_obstruction(game, p, target, True)), desired_eye)
            fixture_camera = state.get("social_fixture_camera")
            if fixture_camera is None:
                fixture_camera = u.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(
                    game, u.CameraActor, u.Transform(location=desired_eye))
                if not fixture_camera:
                    raise RuntimeError("Local island observer camera could not be created")
                state["social_fixture_camera"] = fixture_camera
                pc.set_view_target_with_blend(fixture_camera, 0.)
            fixture_camera.set_actor_location(desired_eye, False, True)
            fixture_camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(desired_eye, target), False)
    width, height = pc.get_viewport_size()
    if width <= 0 or height <= 0:
        return
    eye = camera.get_camera_location()
    if view and desired_eye is not None and not state.get("social_ready") and (eye - desired_eye).length() < 25.:
        point_on_screen = u.GameplayStatics.project_world_to_screen(pc, u.Vector(*view["aim"]), True)
        if point_on_screen and 0 < point_on_screen.x < width and 0 < point_on_screen.y < height:
            state["social_ready"] = write_json(out / f"{name}_SocialReady.json", view["species"])
    now = float(game_state.get_server_world_time_seconds())
    seen = state.setdefault("social_rendered", {})
    counts = state.setdefault("social_client_samples", {})
    last_roles = state.setdefault("social_last_roles", {})
    transitions = state.setdefault("social_transitions", [])
    for actor in u.GameplayStatics.get_all_actors_of_class(game, u.EcoCreatureRepresentationActor):
        if actor.get_editor_property("hidden") or not actor.get_editor_property("bound"):
            continue
        visual = actor.get_editor_property("visual_state")
        role = visual.get_editor_property("social_signal")
        kind = str(visual.get_editor_property("species_id"))
        stable_id = str(visual.get_editor_property("stable_agent_id"))
        if last_roles.get(stable_id, 0) != role:
            transitions.append(dict(id=stable_id, species=kind, role=role, time=now))
            last_roles[stable_id] = role
        if role != 2:
            continue
        reject = counts.setdefault(kind, dict(replies=0, mesh_ready=0, inside_view=0, clear=0))
        reject["replies"] += 1
        components = [actor.get_editor_property(key) for key in ("creature_mesh", "immature_mesh")]
        mesh = next((c for c in components if c.is_visible() and c.get_skeletal_mesh_asset() and c.was_recently_rendered(.24)), None)
        if not mesh:
            continue
        reject["mesh_ready"] += 1
        center, box, _ = u.SystemLibrary.get_component_bounds(mesh)
        pixel = u.GameplayStatics.project_world_to_screen(pc, center, True)
        if not pixel:
            continue
        extents = [u.GameplayStatics.project_world_to_screen(pc, center + offset, True) for offset in
                   (u.Vector(box.x, 0, 0), u.Vector(0, box.y, 0), u.Vector(0, 0, box.z))]
        radius = max((max(abs(p.x - pixel.x), abs(p.y - pixel.y)) for p in extents if p), default=0.)
        if radius < 2:
            continue
        candidates = []
        for sample in (center, center + u.Vector(0, 0, box.z * .55), center + u.Vector(0, 0, box.z * .85)):
            projected = u.GameplayStatics.project_world_to_screen(pc, sample, True)
            if projected and 0 < projected.x < width and 0 < projected.y < height:
                candidates.append((sample, projected))
        if not candidates:
            continue
        reject["inside_view"] += 1
        for sample, projected in candidates:
            obstruction = view_obstruction(game, eye, sample, kind in FISH or kind == "Mink")
            if not obstruction:
                pixel = projected
                break
        else:
            blockers = reject.setdefault("blockers", {})
            blockers[obstruction] = blockers.get(obstruction, 0) + 1
            continue
        reject["clear"] += 1
        entry = dict(id=stable_id, species=kind, server_time=now, pixel=[pixel.x, pixel.y], viewport=[width, height],
                     mesh=mesh.get_skeletal_mesh_asset().get_path_name(), pixel_radius=radius,
                     eye=list(eye.to_tuple()), yaw=visual.get_editor_property("social_yaw"))
        rows = seen.setdefault(kind, [])
        if len(rows) < 8 and (not rows or now - rows[-1]["server_time"] > 1.):
            rows.append(entry)
    if len(seen) != state.get("social_written", 0):
        progress = out / f"{name}_SocialProgress.json"
        if write_json(progress, sorted(seen)):
            state["social_written"] = len(seen)

"""Check the saved team-terrain fauna map in a fresh standalone PIE world."""

from collections import Counter
import json
from pathlib import Path
import time
import traceback

import unreal as u


MAP = "LV_JYU_IntegrationR7eFauna"
SPECIES = {"Herbivore", "Wolf", "Pig", "Fox", "Crow", "Leopard", "Buffalo", "Rat", "Bighorn", "Jackrabbit", "Horse",
           "Mink", "GoldenEagle", "AriakeCatfish", "CommonCarp", "UnidentifiedFish"}
NETWORK = "-EcoIntegratedFaunaNetwork" in u.SystemLibrary.get_command_line()
editor = u.get_editor_subsystem(u.UnrealEditorSubsystem)
levels = u.get_editor_subsystem(u.LevelEditorSubsystem)
inspect = u.EcoCreatureInspectionLibrary
out = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit"
authored = json.loads((out / "IntegrationFaunaAuthoring.json").read_text(encoding="utf-8"))
lake_surface = authored["lake_surface_cm"]
report = {"map": MAP, "samples": [], "visible_species": [], "errors": []}
visible = set()
started = time.monotonic()
next_sample = 0.
camera = None


def obj(world, cls):
    return u.GameplayStatics.get_all_actors_of_class(world, cls)


def finish():
    file = "IntegrationFaunaNetwork.json" if NETWORK else "IntegrationFaunaPIE.json"
    (out / file).write_text(json.dumps(report, indent=2), encoding="utf-8")
    u.unregister_slate_post_tick_callback(handle)
    u.log(f"ECO_INTEGRATION_FAUNA_PIE errors={report['errors']}")
    levels.editor_request_end_play()
    u.SystemLibrary.quit_editor()


def set_camera(world, eye, target):
    global camera
    if camera is None:
        camera = u.EcoCreatureAnimationBuilder.spawn_visual_audit_actor(world, u.CameraActor, u.Transform())
    camera.set_actor_location(eye, False, False)
    camera.set_actor_rotation(u.MathLibrary.find_look_at_rotation(eye, target), False)
    u.GameplayStatics.get_player_controller(world, 0).set_view_target_with_blend(camera, 0.)
    for command in ("eco.Creature.Labels 0", "ShowFlag.HUD 0", "ShowFlag.Particles 0"):
        u.SystemLibrary.execute_console_command(world, command)


def screenshot(world, label):
    u.SystemLibrary.execute_console_command(world, f'HighResShot 1920x1080 filename="{(out / label).as_posix()}"')


def check_client():
    for client in u.ObjectIterator(u.World):
        if client == editor.get_editor_world() or not u.GameplayStatics.get_player_controller(client, 0):
            continue
        if not u.GameplayStatics.get_game_state(client) or MAP not in client.get_name():
            continue
        if u.GameplayStatics.get_game_state(client).has_authority():
            continue
        pawn = u.GameplayStatics.get_player_pawn(client, 0)
        if pawn:
            pawn.set_actor_location(u.Vector(36400., 53100., lake_surface + 200.), False, True)
        patches = obj(client, u.EcoForagePatchVisual)
        counts = Counter(str(a.get_editor_property("visual_state").get_editor_property("species_id"))
                         for a in obj(client, u.EcoCreatureRepresentationActor))
        report["client"] = {"authority_agents": len(inspect.get_authority_agent_ids(client)),
                            "patch_fractions": {str(a.get_editor_property("patch_id")): a.get_forage_fraction() for a in patches},
                            "representations": dict(counts)}
        return


def tick(_):
    global next_sample
    try:
        if time.monotonic() - started > 170.:
            raise RuntimeError("Timed out waiting for the integrated map")
        world = (next((w for w in u.ObjectIterator(u.World) if MAP in w.get_name()
                       and (game_state := u.GameplayStatics.get_game_state(w)) and game_state.has_authority()), None)
                 if NETWORK else editor.get_game_world())
        if not world:
            return
        now = u.GameplayStatics.get_time_seconds(world)
        if now < next_sample:
            return
        runtime = u.GameplayStatics.get_actor_of_class(world, u.EcoCreatureIntegrationSpawner)
        if not runtime or not runtime.is_runtime_ready():
            if now > 18.:
                if runtime:
                    report["water_on_failure"] = {
                        str(p.get_editor_property("id")): str(inspect.inspect_fauna_water(world, "Forest", p.get_editor_property("center"), 1.))
                        for p in runtime.get_editor_property("fauna_habitat_patches") if p.get_editor_property("submerged")}
                    report["habitats"] = [{"name": a.get_name(), "at": str(a.get_actor_location()),
                                           "extent": str(a.get_editor_property("bounds").get_unscaled_box_extent()),
                                           "valid": a.is_valid_habitat(),
                                           "component": str(a.get_editor_property("bounds").get_world_location()),
                                           "region": str(a.get_editor_property("region_id")),
                                           "z": a.get_editor_property("water_surface_z"),
                                           "swim": a.get_editor_property("supports_fauna_swimming"),
                                           "fresh": a.get_editor_property("connected_fresh_water")} for a in obj(world, u.EcoVegetationHabitat)]
                    report["patch_centers"] = [str(p.get_editor_property("center")) for p in runtime.get_editor_property("fauna_habitat_patches") if p.get_editor_property("submerged")]
                    report["tagged"] = [[a.get_name(), str(a.get_actor_location())] for a in obj(world, u.StaticMeshActor)
                                        if a.actor_has_tag("JYU.IntegrationFauna")]
                raise RuntimeError("Saved map never initialized its authority")
            return
        population = Counter()
        for agent in inspect.get_authority_agent_ids(world):
            result = inspect.capture_agent(world, agent)
            raw = next((item for item in result if isinstance(item, str)), "") if isinstance(result, tuple) else result
            if raw:
                row = json.loads(raw)
                if row.get("hp", 0) > 0:
                    population[row.get("species", "unknown")] += 1
                if row.get("brain") and row.get("species") == "Herbivore":
                    report["deer_brain"] = row["brain"]
        for actor in obj(world, u.EcoCreatureRepresentationActor):
            state = actor.get_editor_property("visual_state")
            kind = str(state.get_editor_property("species_id"))
            mesh = actor.get_editor_property("creature_mesh")
            if mesh.get_skeletal_mesh_asset() and all(mesh.get_material(i) for i in range(mesh.get_num_materials())):
                visible.add(kind)
        report["visible_species"] = sorted(visible & SPECIES)
        stocks = {}
        for visual in obj(world, u.EcoForagePatchVisual):
            name = str(visual.get_editor_property("patch_id"))
            stock = runtime.inspect_fauna_habitat_stock(name)
            if stock is not None:
                stocks[name] = [float(stock[-1] if isinstance(stock, tuple) else stock), visual.get_forage_fraction()]
        water = {}
        for key, point in authored["water_samples"].items():
            sample = inspect.inspect_fauna_water(world, "Forest", u.Vector(*point), 6.)
            if sample:
                column, flow = sample
                water[key] = [column.y - column.x, column.y, flow.length()]
        report["samples"].append({"time": now, "population": dict(population), "stocks": stocks, "water": water})
        count = len(report["samples"])
        if NETWORK:
            check_client()
        elif count == 2:
            set_camera(world, u.Vector(37300., 50700., 1400.), u.Vector(42300., 53300., lake_surface))
        elif count == 19:
            screenshot(world, "IntegrationFauna_ExistingLake.png")
        elif count == 20:
            set_camera(world, u.Vector(39500., 50300., -1050.), u.Vector(41300., 52700., lake_surface))
        elif count == 23:
            screenshot(world, "IntegrationFauna_ExistingLakeBank.png")
        elif count == 26:
            set_camera(world, u.Vector(41800., 52700., lake_surface - 70.), u.Vector(42300., 53200., lake_surface - 210.))
        elif count == 29:
            screenshot(world, "IntegrationFauna_ExistingLakeUnderwater.png")
        if now >= 145.:
            all_species = set().union(*(r["population"] for r in report["samples"]))
            if not SPECIES <= all_species:
                report["errors"].append(f"Missing authority species: {sorted(SPECIES - all_species)}")
            if not NETWORK and not SPECIES <= visible:
                report["errors"].append(f"Missing representations: {sorted(SPECIES - visible)}")
            if len(stocks) != authored["forage_visuals"]:
                report["errors"].append(f"Wrong number of visible forage patches: {len(stocks)}")
            if set(water) != set(authored["water_samples"]) or any(abs(row[1] - lake_surface) > .1 for row in water.values()):
                report["errors"].append("Lake samples do not match the existing surface")
            if any(a.get_editor_property("draw_water_surface") for a in obj(world, u.EcoVegetationHabitat)):
                report["errors"].append("An extra surface was added over the existing lake")
            if NETWORK:
                client = report.get("client", {})
                if client.get("authority_agents") != 0 or len(client.get("patch_fractions", {})) != authored["forage_visuals"] or not client.get("representations"):
                    report["errors"].append("Client did not receive forage and creature proxies with zero authority agents")
            finish()
            return
        next_sample = now + 4.5
    except Exception:
        report["errors"].append(traceback.format_exc())
        finish()


if __name__ == "__main__":
    if editor.get_editor_world().get_name() != MAP:
        raise RuntimeError(f"Open {MAP} before running the audit")
    levels.editor_request_begin_play()
    handle = u.register_slate_post_tick_callback(tick)

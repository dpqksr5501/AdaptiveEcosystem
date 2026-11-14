"""Exercise the owned fauna map through a real checkpoint and accelerated population run."""

import json
import re
from pathlib import Path

import unreal


command = unreal.SystemLibrary.get_command_line()
match = re.search(r"-FaunaRecovery=(save|load|long)", command)
if not match:
    raise RuntimeError("Specify -FaunaRecovery=save, load or long")
mode = match.group(1)
run = re.search(r"-FaunaRecoveryRun=([A-Za-z0-9_]+)", command)
prefix = run.group(1) if run else "PackRecovery"


def requested_int(name):
    match = re.search(rf"-{name}=([0-9]+)\b", command)
    return int(match.group(1)) if match else None


slot = f"{prefix}_1108" if run else "FaunaPackValidation_1108"
output = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())) / "FaunaAudit"
output.mkdir(parents=True, exist_ok=True)
state = {"samples": [], "action": None, "dilation": 1.,
         "requested_stage": requested_int("EcoFaunaHabitatStage"),
         "seed": requested_int("EcoV3Seed"),
         "persistence": requested_int("EcoFaunaPersistence"),
         "routine_mask": requested_int("EcoAdaptiveRoutineMask"),
         "pursuit_fix": requested_int("EcoFaunaPursuitFix"),
         "carrion_access": requested_int("EcoFaunaCarrionAccess"),
         "attack_advance": bool(re.search(r"-EcoFaunaAttackAdvance\b", command)),
         "follow_wounded": bool(re.search(r"-EcoFaunaFollowWounded\b", command))}
last_sample = -30.
seen_juveniles = {}
seen_mature = set()
shock_at = requested_int("FaunaFoodShockAt")
shock_until = shock_at + (requested_int("FaunaFoodShockDuration") or 0) if shock_at is not None else None
next_shock = shock_at
dilation = requested_int("CauseDilation")
if dilation is None:
    dilation = 4
if dilation < 1:
    raise RuntimeError("Specify a positive -CauseDilation")
dilation_applied = False


def write():
    (output / f"{prefix}_{mode}.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def snapshot(world):
    summary = unreal.GameplayStatics.get_game_state(world).get_ecology_summary()
    row = {
        "seconds": round(unreal.GameplayStatics.get_time_seconds(world), 3),
        "step": summary.get_editor_property("step_id"),
        "food": {str(entry.get_editor_property("region_id")): entry.get_editor_property("food_amount")
                 for entry in summary.get_editor_property("regions")},
        "species": {str(entry.get_editor_property("species_id")): {
            key: entry.get_editor_property(key) for key in ("population", "births", "deaths")
        } for entry in summary.get_editor_property("species")},
        "ids": sorted(unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)),
    }
    if mode == "long":
        adult_counts = {}
        activity_counts = {}
        predators = []
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world, unreal.EcoCreatureRepresentationActor):
            visual = actor.get_editor_property("visual_state")
            if not actor.get_editor_property("bound") or not visual.get_editor_property("alive"):
                continue
            agent = visual.get_editor_property("stable_agent_id")
            kind = str(visual.get_editor_property("species_id"))
            activity = str(visual.get_editor_property("activity")).split(".")[-1].split(":")[0].rstrip(">")
            counts = activity_counts.setdefault(kind, {})
            counts[activity] = counts.get(activity, 0) + 1
            if kind in ("Fox", "Leopard"):
                position = actor.get_actor_location()
                predators.append({"id": agent, "species": kind, "xy": [round(position.x), round(position.y)],
                                  "energy": round(visual.get_editor_property("normalized_energy"), 3),
                                  "activity": str(visual.get_editor_property("activity"))})
            if visual.get_editor_property("maturity") < .999:
                seen_juveniles[agent] = kind
            else:
                seen_mature.add(agent)
                adult_counts[kind] = adult_counts.get(kind, 0) + 1
        row["visible_adults"] = adult_counts
        row["visible_activities"] = activity_counts
        row["visible_predators"] = predators
        row["observed_maturation"] = {
            kind: sum(agent in seen_mature for agent, juvenile_kind in seen_juveniles.items() if juvenile_kind == kind)
            for kind in set(seen_juveniles.values())
        }
    return row


def tick(_):
    global last_sample, next_shock, dilation_applied
    world = next((w for w in unreal.ObjectIterator(unreal.World) if w.get_name() == "LV_JYU_Fauna"
                  and unreal.GameplayStatics.get_game_state(w)), None)
    if not world:
        return
    authority = unreal.GameplayStatics.get_actor_of_class(world, unreal.EcoCreatureIntegrationSpawner)
    now = unreal.GameplayStatics.get_time_seconds(world)
    if not authority or (not state["samples"] and not unreal.EcoCreatureInspectionLibrary.get_authority_agent_ids(world)):
        return
    if mode == "long" and not dilation_applied:
        unreal.GameplayStatics.set_global_time_dilation(world, float(dilation))
        state["dilation"] = unreal.GameplayStatics.get_global_time_dilation(world)
        dilation_applied = True
    if mode == "long" and next_shock is not None and next_shock <= shock_until and now >= next_shock:
        migration = next((item for item in unreal.ObjectIterator(unreal.EcoHerdMigrationSubsystem)
                          if item.get_outer() == world), None)
        ok = migration is not None and migration.apply_food_fraction_for_audit("FaunaMeadow", .25, False)
        event = {"applied": ok, "seconds": round(now, 3), "remaining_fraction": .25}
        state.setdefault("food_shocks", []).append(event)
        next_shock += 30
        write()
        if not ok:
            raise RuntimeError("Fauna food shock transaction rejected")
    if now >= last_sample + 30.:
        last_sample = now
        state["samples"].append(snapshot(world))
        write()
    if state["action"] or (mode == "save" and now < 150.):
        return
    if mode == "save":
        ok = authority.save_ecosystem(slot)
        state["action"] = {"ok": ok, "saved": snapshot(world)}
    elif mode == "load":
        saved = json.loads((output / f"{prefix}_save.json").read_text(encoding="utf-8"))["action"]
        before = snapshot(world)
        ok = authority.load_ecosystem(slot)
        after = snapshot(world)
        state["action"] = {"ok": ok, "before": before, "after": after,
                           "same_ids": after["ids"] == saved["saved"]["ids"],
                           "same_population": after["species"] == saved["saved"]["species"],
                           "same_step": after["step"] == saved["saved"]["step"]}
    else:
        return
    write()
    unreal.log(f"FAUNA_RECOVERY {mode} {state['action']['ok']}")


handle = unreal.register_slate_post_tick_callback(tick)

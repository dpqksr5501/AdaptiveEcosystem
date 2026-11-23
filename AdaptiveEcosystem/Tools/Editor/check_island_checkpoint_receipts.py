"""Check a saved island checkpoint against its paired save and restore evidence."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib


def read_checkpoint(path, runtime, versions=(16,), *, rule_suffix=""):
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"Truncated island checkpoint: {path}")
    magic, version, size, crc = struct.unpack_from("<4I", data)
    if magic != 0x45434F31 or version not in versions or size != len(data) - 16 or crc != zlib.crc32(data[16:]):
        raise ValueError(f"Invalid island checkpoint header or payload: {path}")
    offset = 16
    strings = []
    for _ in range(2):
        if offset + 4 > len(data):
            raise ValueError(f"Missing checkpoint map or runtime field: {path}")
        length, = struct.unpack_from("<i", data, offset)
        offset += 4
        if not 1 <= length <= len(data) - offset or data[offset + length - 1] != 0:
            raise ValueError(f"Invalid checkpoint map or runtime field: {path}")
        strings.append(data[offset:offset + length - 1].decode("ascii"))
        offset += length
    map_name, recorded_runtime = strings
    if map_name != "/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed":
        raise ValueError(f"Unexpected map: {map_name}")
    with runtime.open("rb") as binary:
        runtime_hash = hashlib.file_digest(binary, "md5").hexdigest()
    if (runtime_hash + rule_suffix).lower() != recorded_runtime.lower():
        raise ValueError("Checkpoint runtime differs from the supplied Unreal module")
    return {"version": version, "payload_bytes": size, "map": map_name, "runtime_md5": runtime_hash}


def read_receipt(log, verb, slot):
    content = log.read_text(encoding="utf-8-sig", errors="replace")
    pattern = rf"\[EcoCheckpoint\] {verb} Slot={re.escape(slot)} Agents=(\d+) Step=(\d+) Native=(\d+)"
    matches = re.findall(pattern, content)
    rows = re.findall(rf"\[EcoCheckpoint\] {verb}Region=(\w+) Food=([\d.]+)", content)
    regions = dict(rows)
    if len(matches) != 1 or not rows or len(rows) != len(regions):
        raise ValueError(f"Expected one {verb} receipt and unique Native region rows: {log}")
    agents, step, native = matches[0]
    return {"agents": int(agents), "step": int(step), "native_step": int(native), "native_region_stock": regions}


def trait_rule_suffix(report):
    """Mirror the runtime identity using rule flags recorded by authority."""
    cohorts = report.get("trait_evidence", {}).get("cohorts", [])
    rules = cohorts[0] if cohorts else report
    suffix = "+FunctionalTraits" if rules.get("functional_traits") else ""
    if rules.get("coat_palette"):
        if not isinstance(rules.get("coat_selection"), bool):
            raise ValueError("Missing camouflage mode for a checkpoint with a coat palette")
        suffix += "+CoatSelection" if rules["coat_selection"] else "+CoatNeutral"
    return suffix


def check_network_hunt(args, header, slot):
    saved, restored = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.save_report, args.load_report))
    if saved["epoch"] == restored["epoch"] or {k: v for k, v in saved.items() if k != "epoch"} != {
            k: v for k, v in restored.items() if k != "epoch"}:
        raise AssertionError("Expected a fresh authority epoch and a matching hunt checkpoint snapshot")
    if not saved["living_traits"] or not saved["patch_stock"] or saved["dead"]["hp"] != 0.:
        raise AssertionError("Checkpoint lacked living traits, resource stock or the dead target")
    if args.fauna_breeding_rule and (not saved.get("fauna_breeding_opportunity")
                                   or any("offspring" not in row for row in saved["living_traits"].values())):
        raise AssertionError("Expected authority rule and offspring counts in the network checkpoint")
    receipt = read_receipt(args.save_log, "Saved", slot)
    if receipt != read_receipt(args.load_log, "Loaded", slot):
        raise AssertionError("Native regional stocks or checkpoint step changed across restore")
    old_log = args.save_log.read_text(encoding="utf-8-sig", errors="replace")
    new_log = args.load_log.read_text(encoding="utf-8-sig", errors="replace")
    before_save = old_log.split(f"[EcoCheckpoint] Saved Slot={slot} ", 1)[0]
    target = saved["target"]
    issue_pattern = rf"\[Eco Fauna\]\[Carcass\] Id={target} .* Remaining=([\d.]+)"
    payout_pattern = rf"\[Eco Fauna\]\[Scavenge\].* Carcass={target} Amount=([\d.]+)"
    close_pattern = rf"\[Eco Fauna\]\[CarcassClosed\] Id={target} Unused=([\d.]+) At=([\d.]+) Reason=(\w+)"
    issued = re.findall(issue_pattern, before_save)
    closes = re.findall(close_pattern, new_log)
    if (len(issued) != 1 or re.search(close_pattern, before_save) or len(closes) != 1
            or re.search(issue_pattern, new_log) or re.search(rf"\[EcoCombat\]\[DeathCommitted\] Id={target}\b", new_log)):
        raise AssertionError("Target carcass was not pending at save or was duplicated on restore")
    unused, close_time, reason = closes[0]
    before = sum(map(float, re.findall(payout_pattern, before_save)))
    after = sum(map(float, re.findall(payout_pattern, new_log)))
    remaining = float(issued[0]) - before
    if float(close_time) <= saved["authority_seconds"] or abs(remaining - after - float(unused)) > .02:
        raise AssertionError("Restored carcass did not preserve its pending balance")
    return {"slot": slot, **header, **receipt, "epoch_before": saved["epoch"], "epoch_after": restored["epoch"],
            "observed_living": len(saved["living_traits"]), "authored_patches": len(saved["patch_stock"]),
            "target": target, "remaining_at_save": remaining, "paid_after_restore": after, "unused_at_close": float(unused),
            "closed_at": float(close_time), "close_reason": reason}


def check_breeding(args, header, slot):
    saved, restored = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.save_report, args.load_report))
    if any(report["errors"] for report in (saved, restored)):
        raise AssertionError("Expected successful breeding save and restore reports")
    before, after = (report["breeding_checkpoint"] for report in (saved, restored))
    if (before["mode"], after["mode"]) != ("Save", "Load") or any(row["slot"] != slot for row in (before, after)):
        raise AssertionError("The breeding reports do not match the checkpoint slot")
    snapshot, loaded = before["snapshot"], after["snapshot"]
    if (snapshot["epoch"] == loaded["epoch"] or not snapshot["breeding_rule"] or not snapshot["stocks"]
            or {key: value for key, value in snapshot.items() if key != "epoch"} !=
            {key: value for key, value in loaded.items() if key != "epoch"}):
        raise AssertionError("Restored living traits, counts, stock or nursery reservation changed")
    reservation = snapshot["reservation"]
    hatch = before["hatch"]
    if (hatch != after["hatch"] or hatch["id"] in snapshot["living"] or not snapshot["at"] < reservation["due"] <= hatch["born"]
            or any(hatch[key] != reservation[key] for key in ("species", "region", "parent_a", "parent_b"))):
        raise AssertionError("The resumed simulation did not commit the same pending hatch")
    receipt = read_receipt(args.save_log, "Saved", slot)
    if receipt != read_receipt(args.load_log, "Loaded", slot):
        raise AssertionError("Native regional stocks or checkpoint step changed across restore")
    hatch_line = (f"[Eco Fauna][NaturalBirth] Child={hatch['id']} Species={hatch['species']} "
                  f"Parents={hatch['parent_a']},{hatch['parent_b']} Generation={hatch['generation']}")
    for log, marker in ((args.save_log, "Saved"), (args.load_log, "Loaded")):
        _, found, continued = log.read_text(encoding="utf-8-sig", errors="replace").partition(f"[EcoCheckpoint] {marker} Slot={slot} ")
        if not found or continued.count(hatch_line) != 1:
            raise AssertionError(f"Expected one authority hatch receipt after {marker.lower()}: {log}")
    client = after.get("client_visual")
    if args.require_client_visual and not client:
        raise AssertionError("No connected client observed the restored hatch")
    if client and (client["id"] != int(hatch["id"]) or client["authority_agents"] or client["at"] < hatch["born"]
                   or not 0. <= client["maturity"] < 1. or abs(client["authority_body_scale"] - client["body_scale"]) > 1e-5):
        raise AssertionError("Client did not receive the matching juvenile body presentation")
    return {"slot": slot, **header, **receipt, "authority_seconds": snapshot["at"],
            "epoch_before": snapshot["epoch"], "epoch_after": loaded["epoch"], "authored_patches": len(snapshot["stocks"]),
            "reservation": reservation, "continued_hatch": hatch, **({"client_visual": client} if client else {})}


def check_meal_fork(args, header, slot):
    from check_island_trait_cohorts import HABITAT_MEAL, PATCH_ACCESS_RECEIPT, PATCH_MEAL, audit_fixed_water_stock, region_balances

    saved, loaded = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.save_report, args.load_report))
    access, control = (report["small_fish_meal_fork"] for report in (saved, loaded))
    if (saved["errors"] or loaded["errors"] or access["slot"] != slot or control["slot"] != slot
            or access["mode"] != "Save" or control["mode"] != "Load"):
        raise AssertionError("The access and control reports must use the same completed checkpoint")
    before, restored = access["snapshot"], control["snapshot"]
    child = before["child"]
    if (before["epoch"] == restored["epoch"] or before["living"][child]["generation"] != 2
            or {key: value for key, value in before.items() if key != "epoch"} !=
            {key: value for key, value in restored.items() if key != "epoch"}):
        raise AssertionError("The control did not start from the same 2nd-generation animal and authority state")
    change = saved["small_fish_meal_access"]
    site = change["site"]
    loaded_change = loaded.get("small_fish_meal_access", {})
    transfer = loaded_change.get("regrowth_transfer", {})
    donor = "IslandRootsSmallFishNursery"
    if (site != "IslandRiverDrift" or change["child"] != child or len(change["points_cm"]) != 4
            or change["stock_before"] != change["stock_after"] or change["stock_after"] != before["stocks"][site]
            or saved["initial_patch_inputs"] != loaded["initial_patch_inputs"]
            or access["end"]["at"] != control["end"]["at"]):
        raise AssertionError("The fork must preserve the original conditions before the same-length comparison")
    if loaded_change:
        patches = loaded["initial_patch_inputs"]["patches"]
        if ({key: value for key, value in loaded_change.items() if key != "regrowth_transfer"} != change
                or set(transfer) != {site, donor}
                or any(pair["from"] != patches[name]["regrowth_per_second"] for name, pair in transfer.items())
                or not 0. < transfer[donor]["to"] < transfer[donor]["from"] or transfer[site]["to"] <= transfer[site]["from"]
                or abs(sum(pair["to"] - pair["from"] for pair in transfer.values())) > 1e-7
                or any(not patches[name]["submerged"] or patches[name]["seasonal_full_growth_depth_cm"] > 0.
                       or patches[name]["region_id"] != "LowerRiver" for name in transfer)):
            raise AssertionError("The restored treatment must keep the same access points and combined regrowth")
    receipt = read_receipt(args.save_log, "Saved", slot)
    if receipt != read_receipt(args.load_log, "Loaded", slot):
        raise AssertionError("The control did not restore Native regional stock and step counters")

    results = {}
    loaded_label = "transfer" if transfer else "control"
    for label, verb, log, fork, report in (("access", "Saved", args.save_log, access, saved),
                                         (loaded_label, "Loaded", args.load_log, control, loaded)):
        snapshot, end = fork["snapshot"], fork["end"]
        marker = f"[EcoCheckpoint] {verb} Slot={slot} "
        _, _, continued = log.read_text(encoding="utf-8-sig", errors="replace").partition(marker)
        events = defaultdict(list)
        payments = Counter()
        donor_paid = Counter()
        target_paid = 0.
        for line in continued.splitlines():
            if "[EcoTrait] " in line:
                row = json.loads(line.split("[EcoTrait] ", 1)[1])
                if row["epoch"] == snapshot["epoch"]:
                    events[row["event"]].append(row)
            if (meal := HABITAT_MEAL.search(line)) and meal[1] == "Aquatic":
                if meal[5] == child:
                    target_paid += float(meal[10])
                if meal[2] == donor and float(meal[10]) > 0.:
                    donor_paid[meal[5]] += float(meal[10])
            if (meal := PATCH_MEAL.search(line)) and meal[1] == site and (point := PATCH_ACCESS_RECEIPT.search(line)):
                payments[int(point[2])] += 1
        start_rows = list(snapshot["living"].values())
        end_rows = list(end["living"].values())
        balances = region_balances({"agents": start_rows}, {"agents": end_rows}, events)
        if any(row["unexplained"] for region in balances.values() for row in region.values()):
            raise AssertionError(f"Population receipts did not balance after {label} checkpoint")
        if label == "control" and payments.keys() - {0}:
            raise AssertionError("The restored control used an added access point")
        patches = report["initial_patch_inputs"]["patches"]
        rates = {name: transfer[name]["to"] if label == "transfer" else patches[name]["regrowth_per_second"]
                 for name in (site, donor)}
        results[label] = {"population": len(end_rows), "child_at_end": end["living"].get(child),
                          "child_deaths": [row for row in events["death"] if row["id"] == child],
                          "child_paid_energy": round(target_paid, 6), "drift_payments_by_access": payments,
                          "drift_stock": audit_fixed_water_stock(log, site, rates[site], after_marker=marker,
                                                                 opening_stock=snapshot["stocks"][site], closing_stock=end["stocks"][site])}
        if transfer:
            results[label]["roots_payments_by_agent"] = {agent: round(paid, 6) for agent, paid in donor_paid.items()}
            results[label]["roots_stock_replay"] = audit_fixed_water_stock(
                log, donor, rates[donor], after_marker=marker, opening_stock=snapshot["stocks"][donor],
                replay_from=site, capacity=patches[donor]["capacity"], closing_stock=end["stocks"][donor])
    return {"slot": slot, **header, **receipt, "fork_seconds": before["at"], "child": child, "change": change,
            "runs": results, **({"regrowth_transfer": transfer} if transfer else {})}


def check_wolf_rejoin(log, report, child, lineage, epoch):
    from check_island_trait_cohorts import NATIVE_WOLF_PROVISION

    cycle = report["wolf_rejoin"]
    before, away, after = (cycle[key] for key in ("before", "away", "after"))
    leaving, remaining, returned = (str(cycle[key]) for key in ("leaving", "remaining", "returned"))
    if (cycle["epoch"] != epoch or before.keys() != {leaving, remaining} or after.keys() != {returned, remaining}
            or (cycle["away_connected"], cycle["after_connected"]) != (1, 2)
            or not cycle["initial_at"] < cycle["away_at"] <= cycle["return_requested_at"] < cycle["returned_at"]
            or cycle["return_requested_at"] - cycle["away_at"] < 3.
            or returned == remaining or leaving == remaining
            or any(lineage[key] != value for key, value in cycle["authority_identity"].items())):
        raise AssertionError("The authority or the restored wolf changed during the two-client rejoin")
    observations = [*before.values(), away, *after.values()]
    if (any(row["id"] != int(child) or row["authority_agents"]
            or abs(row["body_scale"] - row["authority_body_scale"]) > 1e-5 for row in observations)
            or not before[remaining]["sequence"] <= away["sequence"] <= after[remaining]["sequence"]
            or after[returned]["maturity"] <= before[leaving]["maturity"]):
        raise AssertionError("The remaining or rejoined observer received stale or authoritative wolf state")

    text = log.read_text(encoding="utf-8-sig", errors="replace")
    started, departure, rest = text.partition("ECO_WOLF_REJOIN_LEAVE ")
    absent, returning, reconnected = rest.partition("ECO_WOLF_REJOIN_RETURN ")
    listener = re.search(r"Def:GameNetDriver (\w+) IpNetDriver listening on port (\d+)", started)
    if not departure or not returning or not listener:
        raise AssertionError("The rejoin did not log a real loopback network cycle")
    driver, port = listener.groups()
    accepted = re.compile(rf"NotifyAcceptedConnection: .* RemoteAddr: 127\.0\.0\.1:(\d+), .*"
                          rf"Def:GameNetDriver {re.escape(driver)}, IsServer: YES")
    disconnected = list(re.finditer(rf"RemoveClientConnection - Removed address 127\.0\.0\.1:(\d+) .*"
                                   rf"Def:GameNetDriver {re.escape(driver)}, IsServer: YES", absent))
    new = list(accepted.finditer(reconnected))
    initial = accepted.findall(started)
    if (len(initial) != 2 or len(set(initial)) != 2 or len(disconnected) != 1 or disconnected[0][1] not in initial
            or len(new) != 1 or new[0][1] in initial or f"World NetDriver shutdown {driver} " in started + absent
            or f"World NetDriver shutdown {driver} " in reconnected[:new[0].start()]):
        raise AssertionError("Expected one departure and one new connection on the original dedicated net driver")
    continued_provisions = [float(meal[4]) for line in absent[disconnected[0].end():].splitlines()
                            if (meal := NATIVE_WOLF_PROVISION.search(line)) and meal[2] == child]
    if not continued_provisions or any(at > cycle["return_requested_at"] + 1e-6 for at in continued_provisions):
        raise AssertionError("No authoritative provisions were confirmed during the client absence")
    return {"server_port": int(port), "players": [2, 1, 2], "epoch": epoch, "child": child,
            "away_at": cycle["away_at"], "return_requested_at": cycle["return_requested_at"],
            "returned_at": cycle["returned_at"], "provisions_while_away": continued_provisions,
            "returned_visual": after[returned], "witness_visual": after[remaining]}


def check_wolf_provisioning(args, header, slot):
    from check_island_trait_cohorts import NATIVE_WOLF_PROVISION, check_native_wolf_provision

    saved, restored = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.save_report, args.load_report))
    before, after = (report["wolf_checkpoint"] for report in (saved, restored))
    if (saved["errors"] or restored["errors"] or (before["mode"], after["mode"]) != ("Save", "Load")
            or any(row["slot"] != slot for row in (before, after))):
        raise AssertionError("Expected successful Native wolf save and restore reports from the same slot")
    source, target = before["snapshot"], after["snapshot"]
    if (source["epoch"] == target["epoch"] or not source["provisioning"] or before["child"] != after["child"]
            or source.get("birth_after_separation", False) != args.wolf_birth_rule
            or any(key != "epoch" and target[key] != value for key, value in source.items())):
        raise AssertionError("Wolf lineage, energy, stock or the active rule changed at restore")
    receipt = read_receipt(args.save_log, "Saved", slot)
    if receipt != read_receipt(args.load_log, "Loaded", slot):
        raise AssertionError("Native region stock or step changed on wolf checkpoint restore")
    child = before["child"]
    birth = source["living"][child]
    previous = before["last_payment"]
    if not birth["generation"] or not previous["time"] <= source["at"] < previous["time"] + 1.:
        raise AssertionError("Wolf checkpoint did not capture the dependent during its feeding cooldown")

    resumed = []
    def provision_rows(contents):
        return [match.groups() for line in contents.splitlines()
                if (match := NATIVE_WOLF_PROVISION.search(line)) and match[2] == child]

    for verb, log, run in (("Saved", args.save_log, before), ("Loaded", args.load_log, after)):
        old, marker, continued = log.read_text(encoding="utf-8-sig", errors="replace").partition(f"[EcoCheckpoint] {verb} Slot={slot} ")
        historical = provision_rows(old)
        payments = check_native_wolf_provision(provision_rows(continued), {"birth": [birth]}, True)[child]
        if (not marker or not payments or payments[0]["at"] != run["next_payment"]["time"]
                or any(row["at"] < previous["time"] + 1. for row in payments)
                or (verb == "Saved" and (not historical or float(historical[-1][3]) != previous["time"]))
                or (verb == "Loaded" and historical)):
            raise AssertionError(f"Missing or duplicate parent provision at the {verb.lower()} checkpoint boundary")
        resumed.append(payments)
    if resumed[0][0] != resumed[1][0]:
        raise AssertionError("The first provision after restore differs from uninterrupted play")
    client = after["client_visual"]
    if (client["authority_agents"] or client["id"] != int(child) or client["at"] < resumed[1][0]["at"]
            or abs(client["body_scale"] - client["authority_body_scale"]) > 1e-5):
        raise AssertionError("Client observation did not match the restored juvenile")

    reject_report, reject_log = args.wolf_rejection
    report = json.loads(reject_report.read_text(encoding="utf-8-sig"))
    rejection = report["wolf_checkpoint"]
    text = reject_log.read_text(encoding="utf-8-sig", errors="replace")
    disabled_rule = "birth_after_separation" if args.wolf_birth_rule else "provisioning"
    if (report["errors"] or rejection["mode"] != "Reject" or rejection["slot"] != slot
            or not rejection["rejected"] or not rejection["unchanged"]
            or rejection.get("disabled_rule", "provisioning") != disabled_rule
            or (args.wolf_birth_rule and (not rejection["provisioning"] or rejection["birth_after_separation"]))
            or text.count("[EcoCheckpoint] Load rejected: runtime image or fauna rule mismatch") != 1
            or f"[EcoCheckpoint] Loaded Slot={slot} " in text):
        raise AssertionError(f"Authority did not reject the checkpoint without {disabled_rule} while preserving its current state")
    result = {"slot": slot, **header, **receipt, "authority_seconds": source["at"], "epoch_before": source["epoch"],
              "epoch_after": target["epoch"], "child": child, "prior_payment": previous,
              "first_resumed_payment": resumed[1][0], "resumed_payment_counts": [len(rows) for rows in resumed],
              "client_visual": client, "disabled_rule_rejected": True, "disabled_rule": disabled_rule}
    if args.require_wolf_rejoin:
        result["rejoin"] = check_wolf_rejoin(args.load_log, restored, child, birth, target["epoch"])
    return result


def check_wolf_birth_fork(args, header, slot):
    from check_island_trait_cohorts import NATIVE_WOLF_BIRTH_QUEUE, summarize_native_wolf_birth_requests
    from check_island_population_receipts import check_log

    leave_report, leave_log = args.wolf_birth_fork
    paths = (args.save_report, args.load_report, leave_report)
    logs = (args.save_log, args.load_log, leave_log)
    reports = [json.loads(path.read_text(encoding="utf-8-sig")) for path in paths]
    forks = [report["wolf_birth_fork"] for report in reports]
    baseline = forks[0]["snapshot"]
    reservation = forks[0]["reservation"]
    receipt = read_receipt(logs[0], "Saved", slot)
    start = baseline["at"]
    before_save, _, _ = logs[0].read_text(encoding="utf-8-sig").partition(f"[EcoCheckpoint] Saved Slot={slot} ")
    queued = set()
    for line in before_save.splitlines():
        match = NATIVE_WOLF_BIRTH_QUEUE.search(line)
        if match and match[1] == "Grassland":
            _, first, second, due = match.groups()
            queued.add((first, second, float(due)))
    if ((*reservation["parents"], reservation["due"]) not in queued or not start < reservation["due"]
            or not baseline["birth_after_separation"] or not baseline["provisioning"]
            or (baseline["living"][reservation["subject"]]["generation"] > 0) != (reservation["cohort"] == "Descendant")):
        raise AssertionError("The source world did not save a live wolf reservation for the requested parent cohort")

    results = {}
    for mode, fork, report, log in zip(("Save", "Hold", "Leave"), forks, reports, logs, strict=True):
        restored = mode != "Save"
        verb = "Loaded" if restored else "Saved"
        snapshot = fork["snapshot"]
        if (report["errors"] or fork["mode"] != mode or fork["slot"] != slot
                or fork["reservation"] != reservation or fork["player_position"] != forks[0]["player_position"]
                or (snapshot["epoch"] != baseline["epoch"]) != restored
                or any(key != "epoch" and snapshot[key] != value for key, value in baseline.items())
                or read_receipt(log, verb, slot) != receipt):
            raise AssertionError(f"The {mode.lower()} run did not start from the saved authority state")
        observer = fork["observer"]["samples"]
        if not observer or observer[0]["at"] != start or observer[-1]["at"] < reservation["due"]:
            raise AssertionError(f"The {mode.lower()} observer did not cover the pending birth")
        player_offset = sum((a - b) ** 2 for a, b in zip(observer[0]["player_position_cm"][:2], fork["player_position"][:2])) ** .5
        if abs(player_offset - (4200. if mode == "Leave" else 0.)) > 5.:
            raise AssertionError(f"The {mode.lower()} branch did not apply its expected player position")
        end = fork["end"]
        terminal, *_ = summarize_native_wolf_birth_requests(
            snapshot["living"], log, start, end["at"], resume_marker=f"[EcoCheckpoint] {verb} Slot={slot} ", reservation=reservation)
        if terminal["outcome"] == "no_terminal_receipt":
            raise AssertionError(f"The saved wolf reservation has no terminal receipt in {mode.lower()}")
        if (terminal["outcome"] == "deferred" and
                terminal["reconstructed_population"] != terminal["authority_population"]):
            raise AssertionError(f"The Native prey count does not reconcile with the {mode.lower()} population")
        results[mode.lower()] = {"epoch": snapshot["epoch"], "end_seconds": end["at"], "player_offset_cm": player_offset,
                                 "terminal": terminal, "regional_food": check_log(log),
                                 "min_player_distance_cm": min(row["distance_xy_cm"] for row in observer),
                                 "last_observed_player_evidence": max(row["last_evidence"] for row in observer),
                                 "responses": dict(Counter(row["response"] for row in observer)),
                                 "end_grassland_population": dict(Counter(row["species"] for row in end["living"].values()
                                                                           if row["region"] == "Grassland"))}
        if terminal["outcome"] == "born":
            continued = log.read_text(encoding="utf-8-sig").partition(f"[EcoCheckpoint] {verb} Slot={slot} ")[2]
            births = []
            for line in continued.splitlines():
                if "[EcoTrait] " not in line:
                    continue
                event = json.loads(line.split("[EcoTrait] ", 1)[1])
                if event["event"] == "birth" and event["id"] == terminal["child"]:
                    births.append(event)
            birth, = births
            if (birth["generation"] != max(terminal["parent_generations"]) + 1
                    or birth["id"] in snapshot["living"] or not birth["hp"] > 0):
                raise AssertionError(f"The {mode.lower()} branch did not produce a new live wolf generation")
            fields = ("id", "parent_a", "parent_b", "generation", "born", "speed_gene", "size_gene", "body_scale",
                      "speed_scale", "visual_body_scale")
            results[mode.lower()]["newborn"] = {key: birth[key] for key in fields}
            results[mode.lower()]["newborn_at_end"] = end["living"].get(birth["id"])
    return {"slot": slot, **header, **receipt, "saved_at": start, "reservation": reservation, **results}


def check_wolf_descendant(args, header, slot):
    saved, restored = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.save_report, args.load_report))
    before = saved["wolf_descendant_save"]
    after = restored["wolf_descendant_restore"]
    start = after["snapshot"]
    child = before["child_state"]
    if (saved["errors"] or restored["errors"] or before["slot"] != slot or after["slot"] != slot
            or before["epoch"] == start["epoch"] or before["at"] != start["at"]
            or before["region_food"] != start["region_food"] or child != start["child_state"]
            or child["generation"] < 2 or not child["hp"] > 0):
        raise AssertionError("The Native wolf descendant did not restore its exact living state")
    receipt = read_receipt(args.save_log, "Saved", slot)
    if receipt != read_receipt(args.load_log, "Loaded", slot):
        raise AssertionError("Native region balances or the simulation step changed at descendant restore")
    client = after["client_visual"]
    if (client["id"] != int(child["id"]) or client["authority_agents"] or client["at"] <= start["at"]
            or abs(client["body_scale"] - client["authority_body_scale"]) > 1e-5):
        raise AssertionError("The connected client did not receive the descendant's authority body scale")
    old_text = args.save_log.read_text(encoding="utf-8-sig").partition(f"[EcoCheckpoint] Saved Slot={slot} ")[0]
    new_text = args.load_log.read_text(encoding="utf-8-sig")
    birth = rf"\[EcoLife\]\[NaturalBirth\] Child={child['id']} Parents={child['parent_a']},{child['parent_b']} Generation={child['generation']}\b"
    if len(re.findall(birth, old_text)) != 1 or re.search(birth, new_text):
        raise AssertionError("The descendant lacked its original birth receipt or was born again on restore")
    return {"slot": slot, **header, **receipt, "saved_at": before["at"], "saved_epoch": before["epoch"],
            "restored_epoch": start["epoch"], "child": child, "client_visual": client}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkpoint", "runtime", "save_report", "load_report", "save_log", "load_log"):
        parser.add_argument(name, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--network-hunt", action="store_true", help="Verify a dedicated hunt and restored pending carcass")
    mode.add_argument("--breeding", action="store_true", help="Verify a resumed aquatic hatch at the same breeding rule")
    mode.add_argument("--meal-fork", action="store_true", help="Compare post-hatch access and a control from the same authority checkpoint")
    mode.add_argument("--wolf-provisioning", action="store_true", help="Verify saved Native wolf nutrition, cooldown and client presentation")
    mode.add_argument("--wolf-birth-fork", nargs=2, type=Path, metavar=("LEAVE_REPORT", "LEAVE_LOG"),
                      help="Compare a saved Native wolf birth reservation against Hold and Leave restores")
    mode.add_argument("--wolf-descendant", action="store_true", help="Verify a Native wolf descendant and its client presentation after restore")
    parser.add_argument("--wolf-rejection", type=Path, nargs=2, metavar=("REPORT", "LOG"), help="Verify rejection without the wolf provisioning rule")
    parser.add_argument("--require-wolf-rejoin", action="store_true", help="Also require a real socket departure and rejoin with a second observer")
    parser.add_argument("--wolf-birth-rule", action="store_true", help="Require restore and rejection checks for the Native wolf birth rule")
    parser.add_argument("--fauna-breeding-rule", action="store_true", help="Require the rule in a dedicated hunt checkpoint")
    parser.add_argument("--require-client-visual", action="store_true", help="Require a connected client to see the resumed hatch")
    args = parser.parse_args()
    if args.fauna_breeding_rule and not (args.network_hunt or args.wolf_provisioning or args.wolf_birth_fork or args.wolf_descendant):
        parser.error("--fauna-breeding-rule requires a network hunt or Native wolf checkpoint")
    if bool(args.wolf_rejection) != args.wolf_provisioning:
        parser.error("--wolf-provisioning requires the paired --wolf-rejection receipts")
    if args.require_wolf_rejoin and not args.wolf_provisioning:
        parser.error("--require-wolf-rejoin requires --wolf-provisioning")
    if args.wolf_birth_rule and not args.wolf_provisioning:
        parser.error("--wolf-birth-rule requires --wolf-provisioning")
    if args.require_client_visual and not args.breeding:
        parser.error("--require-client-visual requires --breeding")
    slot = args.checkpoint.stem
    wolf_checkpoint = args.wolf_provisioning or args.wolf_birth_fork or args.wolf_descendant
    versions = (16, 24) if args.network_hunt or args.breeding or args.meal_fork or wolf_checkpoint else (16,)
    suffix = "+FaunaBreedingOpportunity" if args.breeding or args.fauna_breeding_rule or args.meal_fork else ""
    if wolf_checkpoint:
        suffix += "+NativeWolfProvisioning"
    if args.wolf_birth_rule or args.wolf_birth_fork or args.wolf_descendant:
        suffix += "+NativeWolfBirthAfterSeparation"
    saved_report = json.loads(args.save_report.read_text(encoding="utf-8-sig"))
    suffix += trait_rule_suffix(saved_report)
    header = read_checkpoint(args.checkpoint, args.runtime, versions, rule_suffix=suffix)
    if args.wolf_birth_fork:
        print(json.dumps(check_wolf_birth_fork(args, header, slot), indent=2))
        return
    if args.wolf_descendant:
        print(json.dumps(check_wolf_descendant(args, header, slot), indent=2))
        return
    if args.wolf_provisioning:
        print(json.dumps(check_wolf_provisioning(args, header, slot), indent=2))
        return
    if args.network_hunt:
        print(json.dumps(check_network_hunt(args, header, slot), indent=2))
        return
    if args.breeding:
        print(json.dumps(check_breeding(args, header, slot), indent=2))
        return
    if args.meal_fork:
        print(json.dumps(check_meal_fork(args, header, slot), indent=2))
        return
    saved, restored = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.save_report, args.load_report))
    if (saved["errors"] or restored["errors"] or saved["checkpoint_slot"] != slot or restored["checkpoint_slot"] != slot
            or saved["checkpoint_mode"] != "Save" or restored["checkpoint_mode"] != "Load"):
        raise AssertionError("Expected successful reports from the same save and restore slot")
    snapshot = saved["checkpoint_state"]
    required = {"agents", "stock", "river_environment", "wet_patch_geometry", "forage_soil_moisture"}
    if any(not snapshot.get(key) for key in required) or snapshot != restored["checkpoint_state"]:
        raise AssertionError("Required save and restore snapshots differ")
    if not restored["checkpoint_environment_compared"] or not restored["resumed_hatches"]:
        raise AssertionError("Expected an environment comparison and a hatch after restore")
    receipt = read_receipt(args.save_log, "Saved", slot)
    if receipt != read_receipt(args.load_log, "Loaded", slot):
        raise AssertionError("Native regional stocks or checkpoint step changed across restore")
    print(json.dumps({"slot": slot, **header, **receipt, "observed_agents": len(snapshot["agents"]),
                      "authored_patches": len(snapshot["stock"]), "wet_patches": len(snapshot["wet_patch_geometry"]),
                      "resumed_hatches": restored["resumed_hatches"]}, indent=2))


if __name__ == "__main__":
    main()

"""Check recorded air scans, contact outcomes and feeding receipts."""

import argparse
from collections import Counter
import json
from math import isclose
from pathlib import Path

from island_eagle_reference_world import EagleDiveWorld, LandedCarcass, Rat


def check_landing(attempt):
    outcome = attempt["outcome"]
    geometry = outcome["landing_and_stock"]
    created, grounded, first_meal = geometry["event_log_lines"]
    if not created < grounded < first_meal:
        raise AssertionError("Expected authority creation, landing, and feeding in that order")

    bank = geometry["grounded_position_cm"]
    start = geometry["vertical_start"]
    if start is not None:
        world = EagleDiveWorld(start["position_cm"], Rat(tuple(bank), .2, 0., alive=False))
        world.phase = "landing"
        world.descend_to_clear_ground(bank[2], 1. / 60.)
        if world.phase != "landing":
            raise AssertionError("Bird landed before it could descend to ground")
        world.descend_to_clear_ground(bank[2], geometry["grounded_pie_seconds"] - start["at"] - 1. / 60.)
        if world.phase != "grounded" or world.position != tuple(bank):
            raise AssertionError("Vertical descent missed the observed landing interval")

    opened = outcome["at"] + .85
    stock = LandedCarcass(tuple(bank), geometry["initial_stock"], opened, opened + 12.,
                          opened + 2.5, attempt["hunter"], 1)
    # Use a shared point to isolate authority transaction rules from continuous reach.
    for gate in ("grounded", "stopped", "clear"):
        eligible = dict(grounded=True, stopped=True, clear=True)
        eligible[gate] = False
        if stock.bite(opened, attempt["hunter"], bank, reach=95., requested=5., **eligible) != 0.:
            raise AssertionError(f"The {gate} prerequisite did not block the bite")
    for payment in outcome["payments"]:
        amount = stock.bite(payment["at"], attempt["hunter"], bank, grounded=True, stopped=True,
                            clear=True, reach=95., requested=5.)
        if not (isclose(amount, payment["amount"], abs_tol=.001)
                and isclose(stock.remaining, payment["remaining"], abs_tol=.001)):
            raise AssertionError("Recalculated payment or remaining stock differs from the authority record")


def check_shared_bites():
    at = 10.
    point = (0., 0., 0.)
    stock = LandedCarcass(point, 10., at, at + 12., at + 2.5, 100, 1)
    cases = (
        (9.9, 100, point, 5., 0.),
        (10., 37, point, 3.5, 0.),
        (10., 100, point, 5., 5.),
        (12.5, 37, (101., 0., 0.), 3.5, 0.),
        (12.5, 37, point, 3.5, 3.5),
        (12.5, 100, point, 5., 0.),
        (13.5, 100, point, 5., 1.5),
        (13.6, 37, point, 3.5, 0.),
    )
    for now, agent, position, cap, expected in cases:
        amount = stock.bite(now, agent, position, grounded=True, stopped=True, clear=True, reach=100., requested=cap)
        if amount != expected:
            raise AssertionError(f"Shared bite at {now} gave {amount} instead of {expected}")
    if stock.remaining != 0.:
        raise AssertionError("Sharing did not account for all stock")
    spoiled = LandedCarcass(point, 10., at, at + 12., at + 2.5, 100, 1)
    if spoiled.bite(at + 12., 37, point, grounded=True, stopped=True, clear=True, reach=100., requested=3.5):
        raise AssertionError("An expired carcass with unused stock must not pay a meal")


def check_attempt(attempt):
    hunter, prey = attempt["hunter"], attempt["prey"]
    candidates = attempt["candidates"]
    scores = {row["prey"]: row["score"] for row in candidates}
    # Audit scores are rounded. Either member of a displayed tie can win.
    if prey not in scores or max(scores.values()) - scores[prey] > .001:
        raise AssertionError(f"Hunter {hunter}: selected prey {prey} outside best scored candidates")
    if not attempt["selected_at"] <= attempt["queued_at"]:
        raise AssertionError("Contact must follow selection")
    outcome = attempt["outcome"]
    if outcome["event"] == "Miss":
        if outcome["reason"] != "HuntOutOfReach" or outcome["gap_cm"] <= outcome["reach_cm"]:
            raise AssertionError("Miss disagrees with the measured contact gap")
        return
    if outcome["event"] != "HuntCaptured" or outcome["at"] <= attempt["queued_at"]:
        raise AssertionError("Capture must follow a queued contact")
    if not outcome["payments"]:
        raise AssertionError("Expected payments on this captured prey's carcass")
    previous = outcome["at"]
    for payment in outcome["payments"]:
        if payment["at"] <= previous or payment["amount"] <= 0 or payment["remaining"] < 0:
            raise AssertionError("Expected ordered, positive payments after capture")
        previous = payment["at"]
    check_landing(attempt)


def check_mixed_stock(run):
    verified = 0
    shared_times = set()
    for record in run["carcasses"]:
        rows = record["payments"]
        species = {row["species"] for row in rows}
        if len(species) < 2 or not species.intersection({"Crow", "GoldenEagle"}):
            raise AssertionError("Expected a bird and another species sharing this carcass")
        closure = record["closure"]
        stock = LandedCarcass((0., 0., 0.), record["initial_stock"], 0., closure["at"], 0., 0, 1)
        last_line = record["created_line"]
        last_time = 0.
        totals = Counter()
        species_at_time = {}
        for row in rows:
            if not last_line < row["line"] < closure["line"] or row["amount"] <= 0.:
                raise AssertionError("Payments must be ordered between creation and closure")
            if row["at"] is not None:
                if not last_time <= row["at"] <= closure["at"]:
                    raise AssertionError("Authority payment time is outside the ledger interval")
                last_time = row["at"]
                participants = species_at_time.setdefault(last_time, set())
                participants.add(row["species"])
                if len(participants) > 1:
                    shared_times.add((record["id"], last_time))
            # The authority records successful requests only. Native payments have no time.
            paid = stock.debit(row["amount"])
            if (not isclose(paid, row["amount"], abs_tol=.002)
                    or not isclose(stock.remaining, row["remaining"], abs_tol=.002)):
                raise AssertionError(f"Carcass {record['id']}: stock mismatch at line {row['line']}")
            totals[row["species"]] += paid
            last_line = row["line"]
            verified += 1
        if not isclose(stock.remaining, closure["unused_stock"], abs_tol=.002):
            raise AssertionError("Unused stock at closure must equal the final remaining stock")
        print(f"  Carcass {record['id']} {record['prey']}: feeding totals {dict(sorted(totals.items()))}; "
              f"{closure['reason']} with {closure['unused_stock']:g} unused")
    print(f"Seed {run['seed']} {run['mode']}: {verified} shared payments reconciled; "
          f"{len(shared_times)} same-time cross-species groups")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture["schema_version"] != 1 or not fixture["runs"]:
        parser.error("expected eagle hunt reference data with schema_version 1")
    for run in fixture["runs"]:
        captures = 0
        for attempt in run["attempts"]:
            check_attempt(attempt)
            captures += attempt["outcome"]["event"] == "HuntCaptured"
        if not run["attempts"]:
            raise AssertionError("Expected observed dive and contact attempts")
        print(f"Seed {run['seed']} {run['condition']}: {captures} captures, {len(run['attempts']) - captures} misses")
    check_shared_bites()
    print("Landing, finite stock, shared feeding places and killer priority passed")
    for run in fixture.get("mixed_species_stock", ()):
        check_mixed_stock(run)


if __name__ == "__main__":
    main()

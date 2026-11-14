"""Verify that a footstep disturbance and subsequent feeding are tracked separately."""

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from math import acos, atan2, cos, degrees, dist, hypot, isclose, pi, radians, sin
from pathlib import Path

from check_island_ground_passage import PassageWorld


@dataclass(frozen=True)
class HearingProfile:
    range_cm: float
    threshold: float
    occluded_range_scale: float

    def signal(self, distance_cm, emitted_range_cm, loudness, weather_scale, occluded):
        reach = min(self.range_cm, emitted_range_cm) * max(0., min(weather_scale, 1.5))
        if occluded:
            reach *= self.occluded_range_scale
        signal = loudness * (1. - distance_cm / reach) if distance_cm < reach else 0.
        return signal if signal >= self.threshold else 0.


def simulate_passage(ground, run, mode, signal):
    patch = ground["patch"]
    world = PassageWorld(run["route_points_cm"], ground["source_region"], patch["region"], 2,
                         ground["base_walk_cm_s"] * run["speed_gene"], patch["capacity"], patch["energy_per_meal"])
    heard_at = 22.
    threat_until = heard_at + 1.5 if signal > 0. else 0.
    paused = 0
    for tick in range(1, 241):
        now = (tick - 1) * .5
        if heard_at <= now < threat_until:
            # This controlled path pauses while alert; it has no free avoidance steering.
            paused += 1
            continue
        world.step(.5)
        paid = world.eat()
        if paid:
            if paid != world.meal or abs(world.stock + paid - patch["capacity"]) > 1e-8:
                raise AssertionError("Meal and stock must reconcile")
            return tick * .5, paused
    raise AssertionError(f"{mode}: passage never resumed to its food")


def check_acoustic_control(runs, ground, profile):
    hearing = HearingProfile(profile["hearing_range"], profile["hearing_threshold"], profile["occluded_hearing"])
    terrain = {run["seed"]: run for run in ground["runs"]}
    for seed, route in terrain.items():
        by_mode = {run["mode"]: run for run in runs if run["seed"] == seed}
        sneaking = max(by_mode["Sneak"]["footstep_loudness"])
        running = min(by_mode["Run"]["footstep_loudness"])
        emitted_range, = by_mode["Run"]["footstep_ranges_cm"]
        controls = {
            "still": (0., 1., False), "sneak": (sneaking, 1., False), "run": (running, 1., False),
            "occluded_run": (running, 1., True), "reduced_hearing_run": (running, .5, False),
        }
        signals = {name: hearing.signal(700., emitted_range, *settings) for name, settings in controls.items()}
        outcomes = {name: simulate_passage(ground, route, name, signal) for name, signal in signals.items()}
        baseline = outcomes["still"]
        if baseline[1] or any(outcomes[name] != baseline for name in ("sneak", "occluded_run", "reduced_hearing_run")):
            raise AssertionError("Silent and below-threshold conditions must not pause the passage")
        if outcomes["run"] != (baseline[0] + 1.5, 3):
            raise AssertionError("The audible footstep should interrupt movement for three half-second steps")
        print(f"Seed {seed}: open running signal {signals['run']:.3f} paused passage 1.5s; "
              "quiet, occluded and reduced-hearing controls matched the baseline")


def first_after(run, reason, after):
    return next(event["authority_seconds"] for event in run["jackrabbit_events"]
                if event["reason"] == reason and event["authority_seconds"] > after)


def check_measured_hearing(capture, profile):
    hearing = HearingProfile(profile["hearing_range"], profile["hearing_threshold"], profile["occluded_hearing"])
    for run in capture:
        if not run["reactions"]:
            raise AssertionError(f"Seed {run['seed']}: expected at least one measured reaction")
        for event in run["reactions"]:
            distance = dist(event["source_cm"], event["listener_cm"])
            expected = hearing.signal(distance, event["range_cm"], event["loudness"], event["weather"], event["occluded"])
            # Tolerate coordinate serialization and Unreal's float arithmetic.
            if expected <= 0. or not isclose(expected, event["signal"], abs_tol=.00003):
                raise AssertionError(f"Seed {run['seed']}: acoustic mismatch at {event['at']}s: {expected} vs {event['signal']}")
        print(f"Seed {run['seed']}: {len(run['reactions'])} measured footstep reactions matched")


def check_measured_avoidance(capture):
    for run in capture:
        samples = run["movement_samples"]
        first = next(i for i, sample in enumerate(samples) if sample["activity"] == "Flee")
        end = next(i for i in range(first + 1, len(samples)) if samples[i]["activity"] != "Flee")
        before, start, last, resumed = (samples[i] for i in (first - 2, first - 1, end - 1, end))
        a, b, c = (row["position_cm"] for row in (before, start, last))
        approach = (b[0] - a[0], b[1] - a[1])
        flee = (c[0] - b[0], c[1] - b[1])
        approach_length, flee_length = hypot(*approach), hypot(*flee)
        if approach_length <= 0. or flee_length <= 0.:
            raise AssertionError("Expected movement before and during avoidance")
        cosine = sum(x * y for x, y in zip(approach, flee)) / (approach_length * flee_length)
        turn = degrees(acos(max(-1., min(1., cosine))))
        first_reaction = run["reactions"][0]
        source = first_reaction["source_cm"]
        source_distance_change = dist(c, source) - dist(first_reaction["listener_cm"], source)
        next_waypoint = next(e["at"] for e in run["passage_events"]
                             if e["reason"] == "PassageWaypoint" and e["at"] > resumed["completed_authority_seconds"])
        arrival = next(e["at"] for e in run["passage_events"] if e["reason"] == "PassageArrived" and e["at"] >= next_waypoint)
        if not (start["completed_authority_seconds"] <= first_reaction["at"] < resumed["completed_authority_seconds"]
                and turn > 10. and source_distance_change > 0.):
            raise AssertionError("Expected a turn and motion away from the first noise before passage resumed")
        print(f"Seed {run['seed']}: turn {turn:.1f} degrees, net displacement {flee_length / 100.:.2f}m, "
              f"first source {source_distance_change / 100.:.2f}m farther away, waypoint {next_waypoint}s, arrival {arrival}s")


def simulate_avoidance(capture, ground, route, hearing, *, muted=False):
    """Generate movement after hearing; the known corridor is rejoined at the entry."""
    first = capture["reactions"][0]
    start = first["listener_cm"]
    lookahead = route["route_points_cm"][1]
    x, y, z = start
    yaw = atan2(lookahead[1] - y, lookahead[0] - x)
    speed_scale = route["speed_gene"]
    speed = ground["base_walk_cm_s"] * speed_scale
    run_speed = 430. * speed_scale
    dt = .05
    source = first["source_cm"]
    heard = 0
    threat_until = 0.
    events = iter(capture["reactions"] if not muted else ())
    event = next(events, None)
    for tick in range(160):
        time = first["at"] + tick * dt
        while event is not None and event["at"] <= time + 1e-7:
            if hearing.signal(dist((x, y, z), event["source_cm"]), event["range_cm"], event["loudness"],
                              event["weather"], event["occluded"]) > 0.:
                heard += 1
                source = event["source_cm"]
                threat_until = event["at"] + 1.5 * capture["caution_gene"]
            event = next(events, None)
        if time >= threat_until:
            break
        desired_yaw = atan2(y - source[1], x - source[0])
        delta = (desired_yaw - yaw + pi) % (2. * pi) - pi
        max_turn = radians(425.) * (1. - .55 * min(1., speed / 430.)) * dt
        yaw += max(-max_turn, min(max_turn, delta))
        speed = min(run_speed, speed + 1100. * speed_scale * dt)
        x += cos(yaw) * speed * dt
        y += sin(yaw) * speed * dt
    else:
        raise AssertionError("The test animal did not clear its alert")

    patch = ground["patch"]
    points = [start, *route["route_points_cm"][1:]]
    if (x, y, z) != tuple(start):
        points.insert(0, (x, y, z))
    crossing_index = len(points) - 2
    world = PassageWorld(points, ground["source_region"], patch["region"], crossing_index,
                         ground["base_walk_cm_s"] * speed_scale, patch["capacity"], patch["energy_per_meal"])
    for second in range(1, 121):
        world.step(1.)
        payment = world.eat()
        if payment:
            if payment != world.meal or not isclose(world.stock + payment, patch["capacity"]):
                raise AssertionError("Rejoined passage must debit the same food stock once")
            return heard, dist(start, (x, y, z)), time + second, payment
    raise AssertionError("Rejoined passage did not reach food")


def check_active_avoidance(captures, ground, profile):
    hearing = HearingProfile(profile["hearing_range"], profile["hearing_threshold"], profile["occluded_hearing"])
    passages = {row["seed"]: row for row in ground["runs"]}
    for row in captures:
        route = passages[row["seed"]]
        heard, displacement, payment_time, paid = simulate_avoidance(row, ground, route, hearing)
        muted = simulate_avoidance(row, ground, route, hearing, muted=True)
        if heard <= 0 or displacement <= 0. or payment_time <= muted[2] or paid != muted[3] or muted[:2] != (0, 0.):
            raise AssertionError("Expected an audible detour and unchanged food payment")
        print(f"Seed {row['seed']}: Python heard {heard}, detoured {displacement / 100.:.2f}m, paid {paid:.3f} at {payment_time:.2f}s")


def compare(runs):
    by_seed = defaultdict(dict)
    for run in runs:
        seed, mode = run["seed"], run["mode"]
        if mode in by_seed[seed]:
            raise AssertionError(f"Duplicate {seed} {mode} run")
        by_seed[seed][mode] = run
    if len(by_seed) != 2:
        raise AssertionError("Expected both island seeds")
    payment_shift = []
    for seed, modes in sorted(by_seed.items()):
        still, sneak, run = (modes[name] for name in ("Still", "Sneak", "Run"))
        if not still["start"] == sneak["start"] == run["start"]:
            raise AssertionError(f"Seed {seed}: player starting locations differ")
        if still["footstep_loudness"] or still["avoidance_count"] or still["peak_displacement_cm"] > .01:
            raise AssertionError(f"Seed {seed}: stationary control moved or emitted footsteps")
        if (not sneak["footstep_loudness"] or not run["footstep_loudness"]
                or run["footstep_ranges_cm"] != sneak["footstep_ranges_cm"]
                or min(run["footstep_loudness"]) <= max(sneak["footstep_loudness"])):
            raise AssertionError(f"Seed {seed}: expected louder running with the same emitted range")
        if sneak["jackrabbit_reaction_signals"] or not run["jackrabbit_reaction_signals"]:
            raise AssertionError(f"Seed {seed}: expected a jackrabbit hearing response only to running")
        heard = first_after(run, "ThreatHeard", 20.)
        control_waypoint = first_after(still, "PassageWaypoint", heard)
        run_waypoint = first_after(run, "PassageWaypoint", heard)
        if run_waypoint <= control_waypoint:
            raise AssertionError(f"Seed {seed}: expected the first post-noise waypoint to be later")
        for candidate in (still, sneak, run):
            meal = candidate["first_payment"]
            if (meal["patch"] != "IslandTransitionForbs" or meal["amount"] != 2.8
                    or meal["at"] <= first_after(candidate, "PassageArrived", 20.)):
                raise AssertionError(f"Seed {seed}: expected first payment only after arrival")
        if still["first_payment"] != sneak["first_payment"]:
            raise AssertionError(f"Seed {seed}: sneak payment disagrees with stationary control")
        shift = run["first_payment"]["at"] - still["first_payment"]["at"]
        payment_shift.append(shift)
        print(f"Seed {seed}: running waypoint shift {run_waypoint - control_waypoint:+g}s, first payment shift {shift:+g}s")
    if min(payment_shift) >= 0. or max(payment_shift) <= 0.:
        raise AssertionError("The two seeds should preserve opposite feeding-time outcomes")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("--ground", type=Path, help="Run an additional acoustic control on measured passage geometry")
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != 1 or not fixture.get("runs"):
        parser.error("expected an island player passage fixture")
    compare(fixture["runs"])
    if "measured_hearing" in fixture:
        check_measured_hearing(fixture["measured_hearing"], fixture["jackrabbit_hearing_profile"])
        check_measured_avoidance(fixture["measured_hearing"])
    if args.ground:
        ground = json.loads(args.ground.read_text(encoding="utf-8"))["ground_passage_reference"]
        check_acoustic_control(fixture["runs"], ground, fixture["jackrabbit_hearing_profile"])
        check_active_avoidance(fixture["measured_hearing"], ground, fixture["jackrabbit_hearing_profile"])


if __name__ == "__main__":
    main()

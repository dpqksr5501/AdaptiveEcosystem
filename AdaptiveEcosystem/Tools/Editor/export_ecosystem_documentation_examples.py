"""Publish small, verbatim excerpts of actual QA snapshots; no Unreal/mutation/training."""
import argparse
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[2]
source = root / "Saved/EcosystemLife_20261023"
target = root / "Docs/RL_Policy/Examples"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def excerpt(snapshot_name, report_name, choose, output_name, fixture, provenance):
    path = source / snapshot_name
    snapshot, report = read(path), read(source / report_name)
    if report.get("result") != "FINISHED" or snapshot.get("training_ready") is not False:
        raise RuntimeError("Actual finished, non-training QA snapshot required")
    agents = choose(snapshot["agents"], report)
    regions = []
    for original in snapshot["regions"]:
        cells = original["logical_cells"]
        if len(cells) != 900:
            raise RuntimeError("Expected actual 900-cell region")
        region = {key: value for key, value in original.items() if key != "logical_cells"}
        region["logical_cells"] = [cells[index] for index in (0, 29, 435, 899)]
        region["documentation_excerpt"] = {"partial": True, "source_cell_count": len(cells),
                                             "selected_indices": [0, 29, 435, 899]}
        regions.append(region)
    result = {
        "documentation_schema": "ecosystem-life-actual-excerpt-v1",
        **provenance, "partial": True, "training_ready": False,
        "golden_vector": False, "restorable_world": False, "fixture": fixture,
        "source_snapshot": "Saved/EcosystemLife_20261023/" + snapshot_name,
        "source_snapshot_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "source_report": report_name, "source_schema": snapshot["schema"],
        "source_agent_count": len(snapshot["agents"]),
        "selection": "Selected agents verbatim; all three regions with original metadata and four verbatim cells each. Missing entries are omitted, never zero-filled.",
        "policy_input_warning": "Full agent diagnostics and world truth are NOT an observation schema. Preserve the existing versioned encoder/mask contract.",
        "agents": agents, "regions": regions,
    }
    target.mkdir(parents=True, exist_ok=True)
    (target / output_name).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return dict(file=output_name, agents=len(agents), cells=sum(len(r["logical_cells"]) for r in regions))


def family(agents, _report):
    child = next(a for a in agents if a.get("life", {}).get("origin") == 1)
    ids = (child["life"]["parent_a"], child["life"]["parent_b"], child["stable_id"])
    lookup = {a["stable_id"]: a for a in agents}
    selected = [lookup[key] for key in ids]
    if not all(a["life"]["generation"] < child["life"]["generation"] for a in selected[:2]):
        raise RuntimeError("Actual parent/child generation evidence required")
    return selected


def unknown(agents, report):
    victim = next(a for a in agents if a["stable_id"] == str(report["subject"]))
    if victim["life"]["unknown_fear"] <= 0 or victim["life"]["last_damage_attacker_known"]:
        raise RuntimeError("Actual unknown-source damage experience required")
    return [victim]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-implementation-commit", required=True)
    parser.add_argument("--capture-date", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--release-date", required=True, type=datetime.date.fromisoformat)
    args = parser.parse_args()
    commit = subprocess.check_output(["git", "rev-parse", "--verify", args.source_implementation_commit + "^{commit}"],
                                     cwd=root.parent, text=True).strip()
    provenance = {"release_date": str(args.release_date), "source_capture_date": str(args.capture_date),
                  "source_implementation_commit": commit}
    results = [excerpt("LifeRestart_LearningSnapshot.json", "FinalSave_Life.json", family,
                       "ecosystem_life_family_actual_20261024.json",
                       "Authored climate/natural birth; observed after birth, not a newborn initialization Golden", provenance),
               excerpt("Encounter_ambush_LearningSnapshot.json", "Encounter_ambush.json", unknown,
                       "ecosystem_life_unknown_damage_actual_20261024.json",
                       "Explicit authority pawn ambush fixture; actual TryStrike, not natural encounter distribution", provenance)]
    print(json.dumps(results))


if __name__ == "__main__":
    main()

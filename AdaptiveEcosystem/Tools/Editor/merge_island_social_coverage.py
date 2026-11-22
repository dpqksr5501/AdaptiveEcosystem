"""Join already validated per-species screen witnesses from several island sessions."""

import argparse
import hashlib
import json
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[2]
MAP = "LV_JYU_IslandEcosystemRefreshed"
MAP_FILE = PROJECT / "Content/JYU/Maps" / (MAP + ".umap")
COORDINATOR = PROJECT / "Content/__ExternalActors__/JYU/Maps" / MAP / "7/XP/95YS5AJG2FLA5LQ9TZ4HLQ.uasset"
SCOPE = "Saved island; rendered social reply matched to reciprocal authority event"


def merge(folders):
    evidence, runs = {}, {}
    expected = None
    for folder in folders:
        report_path = folder / "Relevance.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report["scope"] != SCOPE or not report["concurrent_clients"]["passed"] or not all(
                client["passed"] for client in report["clients"]):
            raise RuntimeError(f"Expected two validated observation clients in {report_path}")
        trial = report["all_island_social"]
        if expected is None:
            expected = set(trial["expected"])
        elif expected != set(trial["expected"]):
            raise RuntimeError(f"Roster differs in {report_path}")
        if len(expected) != 16:
            raise RuntimeError("The saved island needs an initial roster of 16 species")
        runs[folder.name] = dict(report=str(report_path.resolve()),
                                 matched_species=sorted(trial["evidence"]),
                                 authority_completed=report["social_experience"]["server_exchanges"])
        for species, witnesses in trial["evidence"].items():
            if species in expected and species not in evidence:
                client, received = next(iter(witnesses.items()))
                evidence[species] = dict(received, run=folder.name, client=client)
    missing = expected - set(evidence)
    clients = {row["client"] for row in evidence.values()}
    return dict(map=MAP, runs=runs, initial_species=sorted(expected), visible_species=len(evidence),
                missing=sorted(missing), witnesses=evidence, passed=not missing and clients=={"ClientA", "ClientB"},
                current_layout_sha256={str(path.relative_to(PROJECT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                       for path in (MAP_FILE, COORDINATOR)})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=PROJECT / "Saved/IslandSocialAll16Coverage.json")
    args = parser.parse_args()
    result = merge(args.folders)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Visible matched replies: {result['visible_species']}/16; missing: {', '.join(result['missing']) or 'none'}")
    raise SystemExit(int(not result["passed"]))

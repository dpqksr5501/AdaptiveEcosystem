"""Compare inherited surface traits across matched neutral and vision-selection island runs."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean

from check_island_trait_cohorts import read_run
from summarize_fauna_runtime import compare_island_baseline


def read_case(report_path, log_path, enabled):
    data = json.loads(report_path.read_text(encoding="utf-8-sig"))
    cohorts = data["trait_evidence"]["cohorts"]
    if any(not row["coat_palette"] or row["coat_selection"] != enabled for row in cohorts):
        raise ValueError(f"Wrong selection mode in {report_path}")
    summary, founders = read_run(report_path, log_path)
    by_species = defaultdict(list)
    for row in founders.values():
        by_species[row["species"]].append(row)
    if len(by_species) != 16:
        raise ValueError(f"Incomplete species roster in {report_path}")
    for species, rows in by_species.items():
        tones = {row["visual_coat_tone"] for row in rows}
        if len(tones) < 2 or any(abs(row["visual_coat_tone"] - (row["coat_gene"] - .85) / .3) > .5 / 255 + 1e-9 for row in rows):
            raise ValueError(f"Coat initialization or quantization failed for {species} in {report_path}")
    if len(summary["species"]) != 16:
        raise ValueError("The completed population report lacks all 16 species")
    births = defaultdict(list)
    observed = Counter()
    for line in log_path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if "[EcoTrait] " in line:
            row = json.loads(line.split("[EcoTrait] ", 1)[1])
            if row["event"] == "birth":
                births[row["species"], row["region"], row["generation"]].append(row["coat_gene"])
        for marker in ("HuntCoatContrast", "HuntWaterCoatContrast"):
            if f"Reason={marker}" in line:
                observed[marker] += 1
    return data, founders, {
        "events": summary["events"],
        "parents_and_survivors": {name: {key: row[key] for key in (
            "births_with_both_parents_linked", "parent_contribution_means", "surviving_adult_founder_means", "final_alive")}
                                  for name, row in summary["species"].items()},
        "birth_groups": [{"species": name, "region": region, "generation": generation, "count": len(values), "coat_mean": mean(values)}
                         for (name, region, generation), values in sorted(births.items())],
        "reported_contrast_rejections": dict(observed),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("neutral_report", type=Path)
    parser.add_argument("neutral_log", type=Path)
    parser.add_argument("selection_report", type=Path)
    parser.add_argument("selection_log", type=Path)
    args = parser.parse_args()
    control, c_founders, c = read_case(args.neutral_report, args.neutral_log, False)
    treatment, t_founders, t = read_case(args.selection_report, args.selection_log, True)
    baseline = compare_island_baseline(control, treatment)
    if not baseline["matches"] or {k: v["coat_gene"] for k, v in c_founders.items()} != {k: v["coat_gene"] for k, v in t_founders.items()}:
        raise ValueError(f"Pair did not begin with the same conditions and founder genetics: {baseline}")
    print(json.dumps({"matched_baseline": baseline, "neutral": c, "selection": t}, indent=2))


if __name__ == "__main__":
    main()

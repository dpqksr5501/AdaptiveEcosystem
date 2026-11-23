"""Compare snowfield camouflage, survival and natural lineages in paired island runs."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
from statistics import mean, median

from check_island_trait_cohorts import DEATH_CAUSES, FUNCTIONAL_GENES, IMMUTABLE, SHAPE_GENES, read_run
from summarize_fauna_runtime import compare_island_baseline


SIGHT_MARKER = "[Eco Snow Coat Sight] "
REGION = "Snowfield"
DEER = "Herbivore"


def load_run(root, seed, label, selected):
    report_path = root / f"Island_{seed}_{label}" / "IslandFaunaPIE.json"
    log_path = root / "IslandAccessBaseline" / f"{seed}_{label}.log"
    report = json.loads(report_path.read_text(encoding="utf-8-sig"))
    cohorts = report["trait_evidence"]["cohorts"]
    if any(not row["coat_palette"] or row["coat_selection"] != selected for row in cohorts):
        raise ValueError(f"Unexpected camouflage setting in {report_path}")
    summary, founders = read_run(report_path, log_path)
    deer = summary["species"][DEER]
    if deer["births_with_both_parents_linked"] != len(deer["natural_offspring"]):
        raise ValueError(f"Unlinked deer parent in {report_path}")
    living = {row["id"]: row for row in cohorts[-1]["agents"] if row["species"] == DEER and row["hp"] > 0.}
    deaths = {}
    sight = []
    seen_sight = set()
    begin = cohorts[0]["completed_seconds"]
    end = cohorts[-1]["completed_seconds"]
    with log_path.open(encoding="utf-8-sig", errors="replace") as log:
        for line in log:
            if SIGHT_MARKER in line:
                fields = line.split(SIGHT_MARKER, 1)[1].strip()
                if fields in seen_sight:
                    continue
                seen_sight.add(fields)
                row = dict(field.split("=", 1) for field in fields.split())
                if begin <= float(row["At"]) <= end:
                    sight.append(row)
            elif "[EcoTrait] " in line and '"event":"death"' in line:
                row = json.loads(line.split("[EcoTrait] ", 1)[1])
                if (row["species"] == DEER and row["epoch"] == cohorts[0]["epoch"]
                        and begin < row["sample_seconds"] <= end):
                    deaths[row["id"]] = row
    if not sight or (not selected and any(row["Visible"] != "1" for row in sight)):
        raise ValueError(f"Invalid or missing pre-camouflage sight opportunities in {log_path}")
    return report, founders, deer["natural_offspring"], living, deaths, sight


def tone_group(coat, cutoff):
    return "bright" if coat >= cutoff else "dark"


def coat_distribution(rows, cutoff):
    genes = [row["coat_gene"] for row in rows]
    return {
        "count": len(genes),
        "bright": sum(tone_group(gene, cutoff) == "bright" for gene in genes),
        "mean_coat": mean(genes) if genes else None,
    }


def summarize_run(run, snow_founders, cutoff):
    report, _, births, living, deaths, sight = run
    cohorts = report["trait_evidence"]["cohorts"]
    begin = cohorts[0]["completed_seconds"]
    end = cohorts[-1]["completed_seconds"]
    families = defaultdict(list)
    snow_births = defaultdict(list)
    for row in births:
        for parent_id in (row["parent_a"], row["parent_b"]):
            families[parent_id].append(row)
        if row["region"] == REGION:
            snow_births[row["generation"]].append(row)
    founder_groups = defaultdict(list)
    for agent_id, row in snow_founders.items():
        founder_groups[tone_group(row["coat_gene"], cutoff)].append(agent_id)

    life = {}
    for group, ids in founder_groups.items():
        reproductive = [agent_id for agent_id in ids if families[agent_id]]
        observed_deaths = [deaths[agent_id] for agent_id in ids if agent_id in deaths]
        causes = Counter(DEATH_CAUSES[row["death_cause"]] for row in observed_deaths)
        life[group] = {
            "founders": len(ids),
            "alive_at_end_any_region": sum(agent_id in living for agent_id in ids),
            "alive_at_end_in_snow": sum(agent_id in living and living[agent_id]["region"] == REGION for agent_id in ids),
            "death_cause_counts": dict(causes),
            "mean_seconds_alive_within_run": (
                sum(row["sample_seconds"] - begin for row in observed_deaths)
                + (end - begin) * sum(agent_id in living for agent_id in ids)
            ) / len(ids) if len(observed_deaths) + sum(agent_id in living for agent_id in ids) == len(ids) else None,
            "parents_with_any_offspring": len(reproductive),
            "parent_contributions_all_regions": sum(len(families[agent_id]) for agent_id in reproductive),
            "parent_contributions_in_snow": sum(row["region"] == REGION for agent_id in reproductive for row in families[agent_id]),
        }

    detection = {}
    for group in ("dark", "bright"):
        checks = [row for row in sight if tone_group(float(row["Coat"]), cutoff) == group]
        episodes = []
        last_check = {}
        for row in checks:
            pair = row["Wolf"], row["Deer"]
            at = float(row["At"])
            visible = row["Visible"] == "1"
            previous = last_check.get(pair)
            if previous is None or at - previous[0] > 1.:
                episode = len(episodes)
                episodes.append(visible)
            else:
                episode = previous[1]
                episodes[episode] |= visible
            last_check[pair] = at, episode
        detection[group] = {
            "candidate_steps": len(checks),
            "visible_steps": sum(row["Visible"] == "1" for row in checks),
            "unique_wolf_deer_pairs": len(last_check),
            "episodes": len(episodes),
            "episodes_visible_at_least_once": sum(episodes),
        }

    return {
        "end_seconds": end,
        "wolf_sight_in_snow": detection,
        "snow_founder_outcomes": life,
        "births_in_snow_by_generation": {generation: coat_distribution(rows, cutoff)
                                        for generation, rows in sorted(snow_births.items())},
        "living_in_snow": coat_distribution([row for row in living.values() if row["region"] == REGION], cutoff),
        "max_deer_generation_any_region": max((row["generation"] for row in births), default=0),
        "last_eligible_wolf_sight_seconds": float(sight[-1]["At"]),
        "last_sample_with_living_snow_wolf": max(
            (sample["completed_seconds"] for sample in cohorts
             if any(row["species"] == "Wolf" and row["region"] == REGION and row["hp"] > 0.
                    for row in sample["agents"])),
            default=None,
        ),
    }


def compare(root, seed, neutral_label, selected_label):
    neutral = load_run(root, seed, neutral_label, False)
    selected = load_run(root, seed, selected_label, True)
    baseline = compare_island_baseline(neutral[0], selected[0])
    founder_fields = (*IMMUTABLE, *FUNCTIONAL_GENES, *SHAPE_GENES, "sex", "region")
    neutral_profiles = {agent_id: tuple(row.get(key) for key in founder_fields) for agent_id, row in neutral[1].items()}
    selected_profiles = {agent_id: tuple(row.get(key) for key in founder_fields) for agent_id, row in selected[1].items()}
    if not baseline["matches"] or neutral_profiles != selected_profiles:
        raise ValueError(f"Unequal starting conditions for {seed}: {baseline}")
    snow_founders = {agent_id: row for agent_id, row in neutral[1].items()
                     if row["species"] == DEER and row["region"] == REGION}
    cutoff = median(row["coat_gene"] for row in snow_founders.values())
    geometry_fields = ("Wolf", "Deer", "At", "Distance", "Perceived", "NeutralRange", "Coat")
    neutral_geometry = {tuple(row[field] for field in geometry_fields) for row in neutral[-1]}
    matched = Counter()
    changed_examples = []
    for row in selected[-1]:
        if tuple(row[field] for field in geometry_fields) in neutral_geometry:
            matched["checked"] += 1
            matched["rejected"] += row["Visible"] == "0"
            if row["Visible"] == "0" and len(changed_examples) < 3:
                changed_examples.append(row)
    return {
        "seed": seed, "baseline": baseline,
        "bright_threshold_founder_median": cutoff,
        "snow_founders": coat_distribution(snow_founders.values(), cutoff),
        "same_recorded_sight_geometry": dict(matched),
        "same_geometry_rejection_examples": changed_examples,
        "neutral": summarize_run(neutral, snow_founders, cutoff),
        "selected": summarize_run(selected, snow_founders, cutoff),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_directory", type=Path)
    parser.add_argument("seed", type=int, nargs="+")
    parser.add_argument("--neutral-label", default="SnowCoatNeutral")
    parser.add_argument("--selected-label", default="SnowCoatSelected")
    args = parser.parse_args()
    results = [compare(args.audit_directory, seed, args.neutral_label, args.selected_label) for seed in args.seed]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

"""Compare paired ecosystem runs without Unreal or a policy model."""
import collections
import json
import pathlib
import statistics
import sys


TRAITS = {"size_gene": (.9, 1.1), "speed_gene": (.9, 1.1),
          "caution_gene": (.85, 1.15), "sociability_gene": (.85, 1.15), "coat_gene": (.85, 1.15)}
FOUNDER_FIELDS = ("born", "sex", *TRAITS)


def deer(sample):
    return [a for a in sample["agents"] if a["species"] == "Herbivore"]


def founders(report):
    return {a["stable_id"]: (a["region"], *(a["life"][field] for field in FOUNDER_FIELDS))
            for a in deer(report["samples"][0]) if a["life"]["generation"] == 0}


def summarize(report, enabled):
    samples = report["samples"]
    assert report["result"] == "FINISHED", report["error"]
    assert samples[-1]["simulation_elapsed"] >= report["fixed_step_simulation_target"]
    assert all(f["habitat_dynamics"] == enabled for s in samples for f in s["fields"])
    policy = {(a["brain"], a["policy_obs_dim"], a["policy_mask_version"])
              for s in samples for a in deer(s)}
    assert len(policy) == 1, "The comparison needs one active policy per run"
    seen = {a["stable_id"]: a["life"] for s in samples for a in deer(s)}
    cohorts = collections.defaultdict(list)
    linked = 0
    for life in seen.values():
        assert all(lo <= life[gene] <= hi for gene, (lo, hi) in TRAITS.items())
        cohorts[life["generation"]].append(life["size_gene"])
        parents = [seen.get(life[key]) for key in ("parent_a", "parent_b")]
        if life["generation"] and all(parents):
            linked += 1
            assert life["generation"] == max(p["generation"] for p in parents) + 1
            for gene in TRAITS:
                parent_mean = statistics.mean(p[gene] for p in parents)
                assert abs(life[gene] - parent_mean) <= (.015 if gene == "coat_gene" else .02) + 1e-9
    return {"seconds": samples[-1]["simulation_elapsed"], "linked_births": linked, "policy": next(iter(policy)),
            "surviving_deer": sum(a["hp"] > 0 for a in deer(samples[-1])),
            "cohorts": {generation: {"count": len(values), "mean_size_gene": statistics.mean(values)}
                        for generation, values in sorted(cohorts.items())}}


def main(folder):
    results = {}
    for seed in (23, 47):
        baseline, dynamics = (json.loads((folder / f"{mode}{seed}_Life.json").read_bytes())
                              for mode in ("Baseline", "Dynamics"))
        assert baseline["seed"] == dynamics["seed"] == seed
        initial = founders(baseline)
        assert initial and initial == founders(dynamics), f"Seed {seed} has different founder cohorts"
        results[seed] = {"matched_founders": len(initial), "baseline": summarize(baseline, False),
                         "dynamics": summarize(dynamics, True)}
        assert results[seed]["baseline"]["policy"] == results[seed]["dynamics"]["policy"]
    assert sum(pair["dynamics"]["linked_births"] for pair in results.values()) > 0
    result = {"matched_founders_and_valid_inheritance": True,
              "scope": "Habitat rules compared as a bundle; two seeds are descriptive.",
              "pairs": results}
    output = json.dumps(result, indent=2)
    (folder / "HabitatComparison.json").write_text(output + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main(pathlib.Path(sys.argv[1]))

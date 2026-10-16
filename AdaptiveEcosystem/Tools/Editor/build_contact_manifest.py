"""Derive cyclic landing candidates from editor-sampled component-space foot heights.
No hardcoded animation phase or source asset mutation. Writes a reviewable manifest.
"""
import json
from pathlib import Path

saved = Path(__file__).resolve().parents[2] / "Saved"
data = json.loads((saved / "CreatureContactAudit.json").read_text(encoding="utf-8"))
result = {}
for kind, clips in data["animals"].items():
    result[kind] = {}
    for suffix, clip in clips.items():
        markers = []
        for bone, rows in clip["samples"].items():
            if not (bone.endswith("-Foot") or bone.endswith("-Finger0")):
                continue
            heights = [r[3] for r in rows[:-1]]  # Cyclic sample; remove duplicated last frame.
            low, high = min(heights), max(heights)
            if high-low < .5:
                raise RuntimeError("No lifted foot in " + kind + " " + suffix + " " + bone)
            threshold = low + .15*(high-low)
            entries = [i for i, z in enumerate(heights) if z <= threshold and heights[i-1] > threshold]
            if len(entries) != 1:
                raise RuntimeError("Review ambiguous contact: " + kind + " " + suffix + " " + bone + " " + str(entries))
            index = entries[0]
            markers.append({"bone": bone, "time": max(.001, rows[index][0]), "sample_height": heights[index],
                            "min_height": low, "max_height": high, "threshold": threshold})
        if len(markers) != 4:
            raise RuntimeError("Expected four authored feet: " + kind + " " + suffix)
        result[kind][suffix] = {"source": clip["asset"], "length": clip["length"],
                                "markers": sorted(markers, key=lambda m: (m["time"], m["bone"]))}
(saved / "CreatureContactManifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
for kind, clips in result.items():
    for suffix, clip in clips.items():
        print(kind, suffix, [(m["bone"], m["time"]) for m in clip["markers"]])

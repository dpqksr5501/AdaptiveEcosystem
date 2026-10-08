"""Validate completed native server/two-client evidence; no engine launch or edits."""
import json
import re
from pathlib import Path
from collections import Counter

saved = Path(__file__).resolve().parents[2] / "Saved"
logs = saved / "Logs"
report = {}

def check(condition, message):
    if not condition:
        raise RuntimeError(message)

server = (logs / "CreatureRejoinServer.log").read_text(encoding="utf-8", errors="replace")
check(server.count("Join succeeded:") == 2, "Both clients must join the same server log")
check("Test duration completed; Ready=1" in server, "Server must finish normally")
check("[Eco Footstep Audio]" not in server, "Dedicated server must have no local audio")
check("[Eco FootstepNoise]" in server and "[Eco PreySense]" in server, "Authority must own noise/perception")
check(not re.search(r'NetMode=1 LogicalOwned=\d+ Visuals=[1-9]', server), "Dedicated must have no visual actors")
for name in ("CreatureRejoinServer", "CreatureRejoinClientA", "CreatureRejoinClientB"):
    text = (logs / (name+".log")).read_text(encoding="utf-8", errors="replace")
    check(not re.search(r'\b(?:Error|Fatal):', text), name + " contains errors")
    if name.endswith("Server"):
        continue
    check("Test duration completed; Ready=1 Step=0" in text, name + " must finish as a passive client")
    check("[Eco FootstepNoise]" not in text and "[Eco PreySense]" not in text, name + " generated authority senses")
    check(not re.search(r'NetMode=3 LogicalOwned=[1-9]', text), name + " owns logical entities")
    events = re.findall(r'\[Eco Footstep Audio\] NetMode=3 Id=(\d+) Region=(\w+) Surface=(\w+) Material=(\w+) Trigger=(\w+).*Count=(\d+)', text)
    check(events, name + " has no playback evidence")
    check(all(event[4] == "Notify" for event in events), name + " mixes Notify/distance playback")
    counts = Counter((e[1],e[2],e[3]) for e in events)
    for region,surface,material in (("Forest","Grass","PM_EcoGrass"),("Barren","Dry","PM_EcoDry"),("Highland","Dry","PM_EcoDry")):
        check(counts[(region,surface,material)] > 0, name + " missing " + region + " physical material playback")
    resets = 0
    previous = {}
    for agent,region,surface,material,trigger,count in events:
        count = int(count)
        resets += agent in previous and count < previous[agent]
        previous[agent] = count
    errors = [float(v) for v in re.findall(r'\[Eco Facing\].*Error=([\d.]+)',text)]
    check(errors and max(errors) <= 15.05, name + " facing regression")
    report[name] = {"audio_starts": len(events), "surfaces": {"/".join(k):v for k,v in counts.items()},
                    "representation_count_resets": resets, "max_facing_error": max(errors), "logical_step": 0}
report["server"] = {"joins": 2, "logical_noise_events": server.count("[Eco FootstepNoise]"),
                    "prey_sources": dict(Counter(re.findall(r'\[Eco PreySense\].*Source=(\d)', server))),
                    "local_audio_starts": 0, "visual_actors": 0,
                    "completion": re.findall(r'Test duration completed; Ready=1 Step=(\d+)', server)}
(saved / "CreatureRejoinValidation.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2))

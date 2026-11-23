"""Verify the saved Bighorn clips against moving world-space stance targets."""

import json
import math
from pathlib import Path
import runpy
import statistics

import unreal as u


def audit():
    setup = runpy.run_path(str(Path(__file__).with_name("bighorn_footfall_gait.py")))
    folder, pose, world = (setup[key] for key in ("FOLDER", "POSE", "WORLD"))
    cls = u.load_class(None, f"{folder}/BP_Bighorn.BP_Bighorn_C")
    forward = u.get_default_object(cls).get_editor_property("mesh_forward_axis")
    options = u.AnimPoseEvaluationOptions()
    clips = {}
    for label, speed, _, stance, _, phases in setup["GAITS"]:
        for suffix, turn in (("", 0.), ("Left", -36.), ("Right", 36.)):
            name = f"ANIM_Bighorn_Planted{label}{suffix}"
            asset = u.load_asset(f"{folder}/{name}")
            duration = asset.get_play_length()
            count = round(duration * 120)
            rows = [pose.get_anim_pose_at_time(asset, duration * i / count, options) for i in range(count + 1)]
            distances = []
            for foot, shift in zip(setup["FEET"], phases):
                for index in range(count):
                    phase = (index / count + shift) % 1.
                    if not .02 < phase < stance - 1./count - .02:
                        continue
                    def position(row):
                        phase = (row/count + shift) % 1.
                        x, _ = setup["gait_offset"](phase, speed, duration, stance, 0.)
                        intended = (forward * x).rotate_angle_axis(turn * (x / (speed * duration)), u.Vector(0, 0, 1))
                        return pose.get_bone_pose(rows[row], foot, world).translation - intended
                    distances.append((position(index + 1) - position(index)).length())
            clips[name] = dict(stance_samples=len(distances), median_cm=round(statistics.median(distances), 3),
                               maximum_cm=round(max(distances), 3), duration_seconds=duration)
    out = Path(u.Paths.project_saved_dir()).resolve() / "FaunaAudit" / "BighornFootfallClips.json"
    out.write_text(json.dumps(clips, indent=2), encoding="utf-8")
    if any(not math.isfinite(row["maximum_cm"]) or row["maximum_cm"] > 1.2 for row in clips.values()):
        raise RuntimeError("Bighorn stance drift exceeded 1.2cm per 120Hz sample")
    u.log("BIGHORN_FOOTFALL_CLIPS_VERIFIED")


try:
    audit()
finally:
    u.SystemLibrary.quit_editor()

"""Check a saved island checkpoint against its paired save and restore evidence."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib


def read_checkpoint(path, runtime):
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError(f"Truncated island checkpoint: {path}")
    magic, version, size, crc = struct.unpack_from("<4I", data)
    if magic != 0x45434F31 or version != 16 or size != len(data) - 16 or crc != zlib.crc32(data[16:]):
        raise ValueError(f"Invalid island checkpoint header or payload: {path}")
    offset = 16
    strings = []
    for _ in range(2):
        if offset + 4 > len(data):
            raise ValueError(f"Missing checkpoint map or runtime field: {path}")
        length, = struct.unpack_from("<i", data, offset)
        offset += 4
        if not 1 <= length <= len(data) - offset or data[offset + length - 1] != 0:
            raise ValueError(f"Invalid checkpoint map or runtime field: {path}")
        strings.append(data[offset:offset + length - 1].decode("ascii"))
        offset += length
    map_name, recorded_runtime = strings
    if map_name != "/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed":
        raise ValueError(f"Unexpected map: {map_name}")
    with runtime.open("rb") as binary:
        runtime_hash = hashlib.file_digest(binary, "md5").hexdigest()
    if runtime_hash.lower() != recorded_runtime.lower():
        raise ValueError("Checkpoint runtime differs from the supplied Unreal module")
    return {"version": version, "payload_bytes": size, "map": map_name, "runtime_md5": runtime_hash}


def read_receipt(log, verb, slot):
    content = log.read_text(encoding="utf-8-sig", errors="replace")
    pattern = rf"\[EcoCheckpoint\] {verb} Slot={re.escape(slot)} Agents=(\d+) Step=(\d+) Native=(\d+)"
    matches = re.findall(pattern, content)
    rows = re.findall(rf"\[EcoCheckpoint\] {verb}Region=(\w+) Food=([\d.]+)", content)
    regions = dict(rows)
    if len(matches) != 1 or not rows or len(rows) != len(regions):
        raise ValueError(f"Expected one {verb} receipt and unique Native region rows: {log}")
    agents, step, native = matches[0]
    return {"agents": int(agents), "step": int(step), "native_step": int(native), "native_region_stock": regions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("checkpoint", "runtime", "save_report", "load_report", "save_log", "load_log"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    slot = args.checkpoint.stem
    header = read_checkpoint(args.checkpoint, args.runtime)
    saved, restored = (json.loads(path.read_text(encoding="utf-8-sig")) for path in (args.save_report, args.load_report))
    if (saved["errors"] or restored["errors"] or saved["checkpoint_slot"] != slot or restored["checkpoint_slot"] != slot
            or saved["checkpoint_mode"] != "Save" or restored["checkpoint_mode"] != "Load"):
        raise AssertionError("Expected successful reports from the same save and restore slot")
    snapshot = saved["checkpoint_state"]
    required = {"agents", "stock", "river_environment", "wet_patch_geometry", "forage_soil_moisture"}
    if any(not snapshot.get(key) for key in required) or snapshot != restored["checkpoint_state"]:
        raise AssertionError("Required save and restore snapshots differ")
    if not restored["checkpoint_environment_compared"] or not restored["resumed_hatches"]:
        raise AssertionError("Expected an environment comparison and a hatch after restore")
    receipt = read_receipt(args.save_log, "Saved", slot)
    if receipt != read_receipt(args.load_log, "Loaded", slot):
        raise AssertionError("Native regional stocks or checkpoint step changed across restore")
    print(json.dumps({"slot": slot, **header, **receipt, "observed_agents": len(snapshot["agents"]),
                      "authored_patches": len(snapshot["stock"]), "wet_patches": len(snapshot["wet_patch_geometry"]),
                      "resumed_hatches": restored["resumed_hatches"]}, indent=2))


if __name__ == "__main__":
    main()

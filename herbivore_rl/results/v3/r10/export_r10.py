"""R10 언리얼 내보내기 — 종 카드 → species.txt, 배운 두뇌 npz → <종>.r10brain (언리얼 C++ EcoR10Core.h 가 읽는다).

    python -X utf8 results/v3/r10/export_r10.py --brains-dir ckpt/r10/all1 --out ../AdaptiveEcosystem/Saved/R10Demo

- species.txt ('R10SPECIES 1'): 종마다 world._set_body 가 슬롯에 넣는 값 그대로(흔들기 없음) + 몸 벡터 18 + 행동 마스크 24 + 감각 마스크 206.
  값은 repr (되읽으면 비트 같음). 종 차례 = 카드 파일 이름 차례.
- <종>.r10brain ('R10BRAIN 1'): 첫 줄 JSON 머리글(io_hash·크기·카드 sha·payload sha256·결정 수) + float32 W0,B0,W1,B1,W2,B2 (행 우선, 작은 끝).
  --brains-dir 에서 종마다 <종>_<결정>.npz 가운데 결정 수가 가장 큰 것. 없으면 그 종은 두뇌 없음 → 언리얼은 공통 규칙 두뇌.
- 기본 출력 <저장소>/AdaptiveEcosystem/Saved/R10Demo (git 제외 — **/Saved/).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]          # herbivore_rl
REPO = ROOT.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from r10 import contract as C  # noqa: E402
from r10 import species as S  # noqa: E402

BODY_KEYS = ("mass_kg", "radius_m", "walk_mps", "run_mps", "swim_mps", "swim_fast_mps", "fly_mps", "cruise_mps", "dive_mps",
             "accel_mps2", "turn_dps", "lat_accel_mps2", "max_slope_deg", "step_m", "stamina_s", "stamina_recover_s",
             "burst_mps", "burst_s", "burst_exhaust_mps", "burst_exhaust_s")   # = world.World._BODY
MEDIUM_NUM = ("wade_depth_m", "swim_depth_frac", "cruise_height_m", "ceiling_m", "takeoff_s")
DEFAULT_OUT = REPO / "AdaptiveEcosystem" / "Saved" / "R10Demo"


def card_sha(card: dict) -> str:
    """train_r10.sha 와 같은 카드 지문."""
    return hashlib.sha256(json.dumps(card, sort_keys=True, default=str).encode()).hexdigest()[:16]


def species_params(c: dict) -> dict:
    """world.World._set_body 가 슬롯 하나에 넣는 값 (같은 식, 흔들기 없음)."""
    out = {}
    for k in BODY_KEYS:
        v = c["body"].get(k)
        out[k] = 0.0 if v is None else float(v)
    for k in ("ground", "swim", "fly", "needs_water"):
        out[k] = bool(c["medium"][k])
    for k in MEDIUM_NUM:
        v = c["medium"].get(k)
        out[k] = 0.0 if v is None else float(v)
    out["sight_m"] = float(c["senses"]["sight_m"])
    out["fov_cos"] = math.cos(math.radians(min(c["senses"]["fov_deg"], 360.0) / 2.0))
    out["smell_m"] = float(c["senses"]["smell_m"])
    out["night_vision"] = float(c["senses"]["night_vision"])
    out["rate_per_s"] = float(c["eat"]["rate_per_s"])
    out["energy_per_unit"] = float(c["eat"]["energy_per_unit"])
    out["drain_per_step"] = c["metabolism"]["drain_per_day"] / C.DAY_STEPS
    out["reserve_days"] = float(c["metabolism"]["reserve_days"])
    out["run_cost"] = float(c["metabolism"]["run_cost"])
    out["swim_cost"] = float(c["metabolism"].get("swim_cost") or 1.0)
    out["fly_cost"] = float(c["metabolism"].get("fly_cost") or 1.0)
    for k in ("kill_mass_ratio", "reach_m", "attack_cd_s", "defense", "counter_reach_m"):
        out[k] = float(c["combat"][k])
    for k in ("maturity_days", "litter", "gestation_days"):
        out[k] = float(c["life"][k])
    burst = c["body"].get("burst_mps") is not None
    out["has_burst"] = burst
    out["diet"] = [float(c["diet"][k]) for k in S.DIET_KEYS]
    out["body_vec"] = [float(v) for v in S.body_vector(c)]               # float32 값을 double 로 (되읽으면 같은 float32)
    out["amask"] = [int(v) for v in C.action_mask(c["medium"], burst)]
    out["omask"] = [int(v) for v in C.obs_mask(c["medium"], burst)]
    return out


def species_table_text(cards: list) -> str:
    lines = ["R10SPECIES 1", f"io_hash {C.io_hash()}", f"count {len(cards)}"]
    for c in cards:
        p = species_params(c)
        lines.append(f"species {c['id']}")
        if c.get("name_ko"):
            lines.append(f"name_ko {c['name_ko']}")
        lines.append(f"# card_sha {card_sha(c)}")
        for k, v in p.items():
            if k in ("diet", "body_vec", "amask", "omask"):
                lines.append(k + " " + " ".join(repr(float(x)) if k != "amask" and k != "omask" else str(int(x)) for x in v))
            elif isinstance(v, bool):
                lines.append(f"{k} {int(v)}")
            else:
                lines.append(f"{k} {float(v)!r}")
        lines.append("end")
    return "\n".join(lines) + "\n"


def brain_bytes(weights: dict, species: str, meta: dict | None = None, card: dict | None = None) -> bytes:
    """numpy 가중치(W0 (h1, 206) …) → R10BRAIN 1 바이트."""
    w = {k: np.ascontiguousarray(np.asarray(weights[k], dtype="<f4")) for k in ("W0", "B0", "W1", "B1", "W2", "B2")}
    h1, h2 = int(w["W0"].shape[0]), int(w["W1"].shape[0])
    assert w["W0"].shape == (h1, C.OBS_DIM) and w["W1"].shape == (h2, h1) and w["W2"].shape == (C.N_ACTIONS, h2)
    payload = b"".join(w[k].tobytes() for k in ("W0", "B0", "W1", "B1", "W2", "B2"))
    meta = meta or {}
    head = {"format": "R10BRAIN 1", "io_hash": C.io_hash(), "species": species, "obs_dim": C.OBS_DIM, "n_actions": C.N_ACTIONS,
            "h1": h1, "h2": h2, "activation": "tanh", "card_sha": meta.get("card_sha", ""),
            "card_sha_now": card_sha(card) if card else "", "decisions": int(meta.get("decisions", 0)),
            "git": meta.get("git", ""), "payload_bytes": len(payload), "payload_sha256": hashlib.sha256(payload).hexdigest()}
    return (json.dumps(head, ensure_ascii=True, separators=(", ", ": ")) + "\n").encode("ascii") + payload


def read_npz(path) -> tuple[dict, dict]:
    with np.load(path, allow_pickle=False) as z:
        meta = json.loads(str(z["meta_json"][()]))
        if meta.get("io_hash") != C.io_hash():
            raise ValueError(f"{path}: io_hash {meta.get('io_hash')} != contract {C.io_hash()}")
        return {k: np.array(z[k]) for k in ("W0", "B0", "W1", "B1", "W2", "B2")}, meta


def pick_brains(folder: Path, ids) -> dict:
    """종마다 <종>_<결정>.npz 가운데 결정 수가 가장 큰 것."""
    best = {}
    for p in folder.glob("*.npz"):
        m = re.fullmatch(r"(.+)_(\d+)", p.stem)
        if not m or m.group(1) not in ids:
            continue
        n = int(m.group(2))
        if m.group(1) not in best or n > best[m.group(1)][0]:
            best[m.group(1)] = (n, p)
    return {k: v[1] for k, v in best.items()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cards", default=str(S.SPECIES_DIR))
    ap.add_argument("--brains-dir", default=None, help="종_결정.npz 폴더 (없으면 종 표만)")
    ap.add_argument("--brain", nargs="*", default=[], help="종=npz (덮어쓰기)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    cards = S.load_all(a.cards)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    order = sorted(cards)
    (out / "species.txt").write_text(species_table_text([cards[k] for k in order]), encoding="utf-8")
    picks = pick_brains(Path(a.brains_dir), set(order)) if a.brains_dir else {}
    for spec in a.brain:
        sid, _, path = spec.partition("=")
        picks[sid] = Path(path)
    manifest = {"io_hash": C.io_hash(), "species": order, "brains": {}}
    for sid in order:
        p = picks.get(sid)
        if p is None:
            manifest["brains"][sid] = None
            continue
        weights, meta = read_npz(p)
        data = brain_bytes(weights, sid, meta, cards[sid])
        (out / f"{sid}.r10brain").write_bytes(data)
        same = meta.get("card_sha") == card_sha(cards[sid])
        manifest["brains"][sid] = {"src": str(p), "decisions": int(meta.get("decisions", 0)), "card_sha_match": same}
        print(f"{sid:14s} {p.name:24s} 결정 {int(meta.get('decisions', 0)):>10,}{'' if same else '  (카드 바뀜 — 배운 범위 확인)'}")
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    none = [k for k in order if manifest["brains"][k] is None]
    print(f"종 표 {len(order)} 종 → {out / 'species.txt'} · 두뇌 {len(order) - len(none)} 개" + (f" · 규칙 두뇌: {', '.join(none)}" if none else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())

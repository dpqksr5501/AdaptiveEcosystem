"""R9 데모 두뇌 npz → .r9brain (C++ EcoR9Core.h 가 읽는 꼴). 실행 전에 한 번만 돌린다(게임 실행 중에는 파이썬을 쓰지 않음).
2026-11-13 세션 스크래치(SP/r9/ue_demo/export_brains.py)에서 저장소로 옮겼다 — swap_brain.py 가 이 파일의 export() 를 쓴다
(RL_R9_TURN_EFFORT_DESIGN.md 7-1). 경로는 이 파일이 있는 herbivore_rl 기준이고, 내보낼 곳 --out 은 반드시 준다.

    python -I -B -X utf8 results/v3/r9/export_brains.py --out <폴더>
        # 옛 세 종 데모 두뇌 ckpt/r9_fauna/start/src/{deer_r0_20013056,wolf_r0_7845120,boar_r0_10027008}.npz → <out>/{deer,wolf,boar}.r9brain
    python -I -B -X utf8 results/v3/r9/export_brains.py --fauna [--flight <폴더>] [--start <폴더>] --out <폴더>
        # 동물 세계 (2026-11-13): 시험 비행 결과 → <out>/fauna/{buffalo,leopard,fox}.r9brain (+ 옛 세 종)
        #   새 종 셋 = <flight>/<종>_r*_*.npz (train_r9 snapshot 이름 '<종>_r<바퀴>_<결정 수>.npz' — 통합 05:50 확인) 또는 fl_*_<종>*.npz
        #             가운데 결정 수(meta decisions)가 가장 큰 것 (기본 herbivore_rl/ckpt/r9_fauna/flight/A)
        #   늑대   = <flight>/ 의 같은 꼴 늑대 판이 있으면 그것 (2 단계 동물 세계 학습), 없으면 <start>/wolf_v0.npz
        #   사슴·멧돼지 = <start>/{deer,boar}_v0.npz (rebody — S′ 가중치 그대로, 메타만 동물 세계. 기본 herbivore_rl/ckpt/r9_fauna/start)
        #   장면 파일(fauna/scene.txt)은 이 스크립트가 만들지 않는다 (dump_fauna.py → swap_brain.py --scene).

파일 꼴 (리틀 엔디언):
  1 줄: JSON 머리 (ASCII, 끝에 '\\n'). format "R9BRAIN 1", species, obs_dim 115, hidden [64, 64], n_actions 19,
        activation tanh, shapes, payload_bytes, payload_sha256(아래 본문의 sha256), source_npz·source_npz_sha256,
        io_hash·body_hash·decisions(npz meta_json 그대로), obs_names(115), action_names(19).
  본문: float32 W0 (64,115) · B0 (64) · W1 (64,64) · B1 (64) · W2 (19,64) · B2 (19), 행 우선(C 차례), 사이 틈 없음.
순전파 = r9_brains.forward_np 와 같음: logits = W2·tanh(W1·tanh(W0·x + B0) + B1) + B2, 관측 변환 없음.
종 = 파이썬 ALL_SPECIES 앞 여섯 (deer wolf boar buffalo leopard fox — 언리얼 코어 종 번호와 같은 차례).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
HRL = HERE.parents[2]                                             # herbivore_rl/ (results/v3/r9/export_brains.py)
CK = HRL / "ckpt" / "r9_fauna" / "start" / "src"                # SPECIES_START.md: demo ckpt/A 의 시작 판 복사본
SRC = {"deer": CK / "deer_r0_20013056.npz", "wolf": CK / "wolf_r0_7845120.npz", "boar": CK / "boar_r0_10027008.npz"}
SPECIES = ("deer", "wolf", "boar", "buffalo", "leopard", "fox")   # 언리얼 코어 SpDeer 0 … SpFox 5
OLD = SPECIES[:3]
NEW = SPECIES[3:]
FLIGHT = HRL / "ckpt" / "r9_fauna" / "flight" / "A"
START = HRL / "ckpt" / "r9_fauna" / "start"
ORDER = ("W0", "B0", "W1", "B1", "W2", "B2")
WANT = {"W0": (64, 115), "B0": (64,), "W1": (64, 64), "B1": (64,), "W2": (19, 64), "B2": (19,)}


def export(sp: str, src: Path, out_dir: Path) -> Path:
    raw = src.read_bytes()
    z = np.load(src, allow_pickle=False)
    meta = json.loads(str(z["meta_json"]))
    if meta.get("species") != sp:
        raise SystemExit(f"{src}: species {meta.get('species')} != {sp}")
    arrs = []
    for k in ORDER:
        a = np.asarray(z[k])
        if a.dtype != np.float32 or tuple(a.shape) != WANT[k]:
            raise SystemExit(f"{src}: {k} {a.dtype} {a.shape} != float32 {WANT[k]}")
        arrs.append(np.ascontiguousarray(a.astype("<f4")))
    payload = b"".join(a.tobytes(order="C") for a in arrs)
    obs_names = list(meta["obs_names"])
    act_names = list(meta["action_names"])
    if len(obs_names) != 115 or len(act_names) != 19:
        raise SystemExit(f"{src}: obs_names {len(obs_names)} action_names {len(act_names)}")
    head = {
        "format": "R9BRAIN 1",
        "species": sp,
        "obs_dim": 115,
        "hidden": [64, 64],
        "n_actions": 19,
        "activation": "tanh",
        "layout": "float32 little-endian, W0 B0 W1 B1 W2 B2, row-major (out, in)",
        "shapes": {k: list(WANT[k]) for k in ORDER},
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "source_npz": src.name,
        "source_npz_sha256": hashlib.sha256(raw).hexdigest(),
        "io_hash": meta.get("io_hash"),
        "body_hash": meta.get("body_hash"),
        "decisions": meta.get("decisions"),
        "round": meta.get("round"),
        "branch": meta.get("branch"),
        "obs_names": obs_names,
        "action_names": act_names,
    }
    if meta.get("init_from"):
        # rebody 두뇌 (동물 세계 몸 메타 + S′ 가중치) — 어디서 왔는지 남긴다 (C++ 은 읽지 않음)
        # 평평한 글 칸만 (C++ 머리 읽기는 키 이름으로 찾는다 — 겹친 객체에 같은 키 이름을 두지 않음)
        head["rebody_from_species"] = meta["init_from"].get("species")
        head["rebody_from_body_hash"] = meta["init_from"].get("body_hash")
        head["rebody_from_sha256"] = meta["init_from"].get("sha256")
    line = json.dumps(head, ensure_ascii=True, separators=(", ", ": "))
    assert "\n" not in line
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{sp}.r9brain"
    out.write_bytes(line.encode("ascii") + b"\n" + payload)
    # 되읽기 확인: 본문을 다시 풀어 npz 와 비트까지 같은지
    back = out.read_bytes()
    nl = back.index(b"\n")
    body = back[nl + 1:]
    off = 0
    for k, a in zip(ORDER, arrs):
        n = a.size * 4
        b = np.frombuffer(body[off:off + n], dtype="<f4").reshape(a.shape)
        if not np.array_equal(b.view(np.uint32), a.view(np.uint32)):
            raise SystemExit(f"{out}: {k} 되읽기 다름")
        off += n
    if off != len(body):
        raise SystemExit(f"{out}: 본문 길이 {len(body)} != {off}")
    print(f"{out}  {len(back)} bytes  payload_sha256 {head['payload_sha256'][:16]}…  body_hash {head['body_hash']}")
    return out


def newest_flight(flight: Path, sp: str) -> Path | None:
    """<flight>/<종>_r*_*.npz · fl_*_<종>*.npz 가운데 meta decisions 가 가장 큰 것 (같으면 나중 파일). 없으면 None.
    train_r9.py 의 snapshot 이름은 '<종>_r<바퀴>_<결정 수>.npz' 다 (run 이름 fl_A_<종> 은 .json 에만 붙음 — 통합 05:50 확인)."""
    best, best_key = None, None
    cands = sorted(set(flight.glob(f"{sp}_r*_*.npz")) | set(flight.glob(f"fl_*_{sp}*.npz")))
    for p in cands:
        try:
            meta = json.loads(str(np.load(p, allow_pickle=False)["meta_json"]))
        except Exception as e:  # noqa: BLE001 — 덜 써진 파일은 건너뛴다 (학습이 쓰는 중일 수 있음)
            print(f"  건너뜀 {p.name}: {e}")
            continue
        if meta.get("species") != sp:
            continue
        key = (int(meta.get("decisions") or 0), p.stat().st_mtime)
        if best_key is None or key > best_key:
            best, best_key = p, key
    return best


def fauna_sources(flight: Path, start: Path) -> dict[str, Path]:
    src: dict[str, Path] = {}
    for sp in NEW:
        p = newest_flight(flight, sp)
        if p is None:
            raise SystemExit(f"{flight}: {sp}_r*_*.npz · fl_*_{sp}*.npz 없음 — 1 단계 학습 결과를 기다리거나 --flight 를 준다")
        src[sp] = p
    wolf = newest_flight(flight, "wolf")
    src["wolf"] = wolf if wolf is not None else start / "wolf_v0.npz"
    for sp in ("deer", "boar"):
        src[sp] = start / f"{sp}_v0.npz"
    for sp in SPECIES:
        if not src[sp].exists():
            raise SystemExit(f"{src[sp]} 없음")
    return {sp: src[sp] for sp in SPECIES}


def main(argv: list[str]) -> int:
    out_dir = None                                   # 저장소 안(results/)에 쓰지 않게 --out 을 반드시 받는다
    flight, start, fauna = FLIGHT, START, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--fauna":
            fauna = True
            i += 1
        elif a in ("--flight", "--start", "--out") and i + 1 < len(argv):
            v = Path(argv[i + 1])
            if a == "--flight":
                flight = v
            elif a == "--start":
                start = v
            else:
                out_dir = v
            i += 2
        else:
            print(__doc__)
            return 2
    if out_dir is None:
        print(__doc__)
        return 2
    if not fauna:
        for sp, src in SRC.items():
            export(sp, src, out_dir)
        return 0
    srcs = fauna_sources(flight, start)
    for sp, src in srcs.items():
        print(f"{sp:8s} ← {src}")
        export(sp, src, out_dir / "fauna")
    print(f"동물 세계 두뇌 여섯 → {out_dir / 'fauna'} (장면 파일 fauna/scene.txt 는 따로 — swap_brain.py --scene)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

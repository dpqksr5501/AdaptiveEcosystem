"""R9 데모 두뇌 바꾸기: 학습 결과 npz 하나(또는 여럿) → 언리얼이 읽는 .r9brain 으로 바꿔 <프로젝트>/Saved/R9Demo/brains/ 에 넣는다.

    python -I -B -X utf8 results/v3/r9/swap_brain.py <새 두뇌.npz> [<다른 종 npz> ...] [--out <폴더>] [--fauna] [--scene <동물 세계 scene.txt>]
                                                    [--no-body-check]

- 2026-11-13 세션 스크래치(SP/r9/ue_demo/swap_brain.py)에서 저장소로 옮겼다(RL_R9_TURN_EFFORT_DESIGN.md 7-1). 같은 폴더의 export_brains.py 를
  쓴다. --out 기본 = 이 저장소의 AdaptiveEcosystem/Saved/R9Demo/brains.
- 종(deer/wolf/boar/buffalo/leopard/fox)은 npz 의 meta_json 에서 읽는다. 115 → 64 → 64 → 19 · tanh 꼴이 아니면 거부한다 (export_brains.py 와 같은 검사·되읽기 확인).
- 동물 세계 (2026-11-13): 물소·표범·여우 두뇌는 늘 <out>/fauna/ 로 간다. 사슴·늑대·멧돼지 두뇌는 --fauna 를 줄 때만 <out>/fauna/ 로
  (동물 세계에서 배운·rebody 한 옛 종 두뇌 — 없으면 언리얼이 <out> 의 S′ 두뇌를 쓴다). --scene 은 그 파일을 <out>/fauna/scene.txt 로 넣는다.
  언리얼은 fauna/ 에 새 종 두뇌 셋 + scene.txt 가 다 있어야 동물 장면으로 돈다 (eco.R9Demo.Fauna 1 기본, 아니면 지금 세 종).
- 몸 해시 대조 (설계 7-2·9 절 'C++ 에 다른 몸의 두뇌가 조용히 실림'): 두뇌가 들어갈 폴더의 장면(새 --scene, 아니면 그 폴더에 이미 있는
  scene.txt)에 dump_fauna.py 가 쓴 `body_hash` 줄이 있으면, npz 메타 body_hash 가 그 종 값과 다를 때 아무것도 바꾸지 않고 거부한다
  (motion 장면에 옛 몸 두뇌 · 옛 장면에 motion 두뇌 모두). 줄이 없는 옛 장면은 대조하지 않고 알린다. --no-body-check 로 끈다.
- 앞 파일은 <종>.r9brain.bak (scene.txt.bak) 으로 남긴다. 언리얼은 Play(또는 판 다시 시작) 때 두뇌를 읽으므로, 바꾼 뒤 Play 를 다시 누르면 된다.
- 게임 실행 중에는 파이썬을 쓰지 않는다 — 이 스크립트는 Play 전에 파일만 바꾼다.
- 주의: 언리얼 코어(EcoR9Core.h)는 학습 세계 b3b8e668 + S__N (+ 동물 세계 1 단계 몸 규칙) 을 옮긴 것이다. 관측·행동 뜻이나 세계 규칙이 바뀐 학습의 두뇌는
  모양이 같아도 엉뚱하게 움직일 수 있다 (같은 115 칸 이름인지는 확인하지만 규칙 차이는 잡지 못함). 몸 움직임(motion) 두뇌는 C++ 코어가 motion 줄을
  읽게 된 뒤(설계 10-8)에만 넣는다.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DEFAULT_OUT = HERE.parents[3] / "AdaptiveEcosystem" / "Saved" / "R9Demo" / "brains"   # <저장소>/AdaptiveEcosystem/Saved/R9Demo/brains
SPECIES = ("deer", "wolf", "boar", "buffalo", "leopard", "fox")
NEW = SPECIES[3:]


def load_exporter():
    spec = importlib.util.spec_from_file_location("r9_export_brains", HERE / "export_brains.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def ref_obs_names(out_dir: Path):
    """지금 쓰는 두뇌 머리의 obs_names (사슴 → 아무 종). 칸 이름 차례가 다르면 거부한다."""
    for d in (out_dir, out_dir / "fauna"):
        for sp in SPECIES:
            ref = d / f"{sp}.r9brain"
            if ref.exists():
                line = ref.read_bytes().split(b"\n", 1)[0]
                return json.loads(line.decode("ascii")).get("obs_names")
    return None


def scene_info(path: Path) -> dict | None:
    """@scene 구역의 body_hash (종 차례 u64 → '0x…' 글) 와 motion_on / motion_turn. 파일이 없으면 None."""
    if not path.exists():
        return None
    info: dict = {"path": str(path), "body_hash": None, "motion_on": 0, "motion_turn": 0}
    in_scene = False
    with open(path, "r", encoding="ascii") as f:
        for line in f:
            if line.startswith("@"):
                if in_scene:
                    break
                in_scene = line.startswith("@scene")
                continue
            if not in_scene:
                continue
            name = line.split(" ", 1)[0]
            if name == "body_hash":
                p = line.split()
                n = int(p[3])
                info["body_hash"] = [f"0x{int(x):016x}" for x in p[4:4 + n]]
            elif name in ("motion_on", "motion_turn"):
                info[name] = int(line.split()[-1])
    return info


def main(argv: list[str]) -> int:
    out_dir = DEFAULT_OUT
    srcs: list[Path] = []
    fauna_old = False
    scene: Path | None = None
    body_check = True
    i = 0
    while i < len(argv):
        if argv[i] == "--out" and i + 1 < len(argv):
            out_dir = Path(argv[i + 1])
            i += 2
            continue
        if argv[i] == "--scene" and i + 1 < len(argv):
            scene = Path(argv[i + 1])
            i += 2
            continue
        if argv[i] == "--fauna":
            fauna_old = True
            i += 1
            continue
        if argv[i] == "--no-body-check":
            body_check = False
            i += 1
            continue
        srcs.append(Path(argv[i]))
        i += 1
    if not srcs and scene is None:
        print(__doc__)
        return 2
    if scene is not None:
        text = scene.read_bytes()
        if b"@scene" not in text[:4096]:
            raise SystemExit(f"{scene}: '@scene' 구역이 없음 — R9DUMP 장면 파일이 아님")
    ex = load_exporter()
    ref_names = ref_obs_names(out_dir)
    # 1) 모두 검사한 뒤에만 쓴다 (하나라도 거부되면 아무것도 바꾸지 않음)
    plan = []
    for src in srcs:
        with np.load(src, allow_pickle=False) as z:
            meta = json.loads(str(z["meta_json"]))
        sp = meta.get("species")
        if sp not in SPECIES:
            raise SystemExit(f"{src}: species {sp!r} 를 모름")
        if ref_names is not None and list(meta.get("obs_names", [])) != list(ref_names):
            raise SystemExit(f"{src}: 관측 칸 이름·차례가 지금 두뇌와 다름 — 언리얼 코어가 주는 눈과 맞지 않아 거부")
        dest = out_dir / "fauna" if (sp in NEW or fauna_old) else out_dir
        sc = scene if (scene is not None and dest == out_dir / "fauna") else dest / "scene.txt"
        info = scene_info(sc)
        if body_check and info is not None and info["body_hash"] is not None:
            want = info["body_hash"][SPECIES.index(sp)] if SPECIES.index(sp) < len(info["body_hash"]) else None
            if want is None or meta.get("body_hash") != want:
                raise SystemExit(f"{src}: body_hash {meta.get('body_hash')} != 장면 {sc} 의 {sp} 몸 {want} "
                                 f"(장면 motion_on={info['motion_on']} turn={info['motion_turn']}) — 다른 몸의 두뇌라 거부 "
                                 "(rebody_r9.py 로 그 몸에 옮기거나 맞는 장면을 --scene 으로; 끄려면 --no-body-check)")
        elif info is not None and info["body_hash"] is None:
            print(f"  알림: {sc} 에 body_hash 줄이 없음 (옛 장면) — {sp} 두뇌 몸 해시를 대조하지 않음")
        plan.append((sp, src, dest))
    # 2) 쓰기
    out_dir.mkdir(parents=True, exist_ok=True)
    for sp, src, dest in plan:
        dest.mkdir(parents=True, exist_ok=True)
        old = dest / f"{sp}.r9brain"
        if old.exists():
            shutil.copy2(old, dest / f"{sp}.r9brain.bak")
        ex.export(sp, src, dest)
    if scene is not None:
        dest = out_dir / "fauna"
        dest.mkdir(parents=True, exist_ok=True)
        old = dest / "scene.txt"
        if old.exists():
            shutil.copy2(old, dest / "scene.txt.bak")
        shutil.copy2(scene, old)
        inf = scene_info(old)
        print(f"{old}  {len(text)} bytes (동물 세계 장면, motion_on={inf['motion_on']} turn={inf['motion_turn']})")
    fd = out_dir / "fauna"
    have = [sp for sp in NEW if (fd / f"{sp}.r9brain").exists()]
    ready = len(have) == len(NEW) and (fd / "scene.txt").exists()
    print("바꿈 — 언리얼에서 Play 를 다시 누르면 새 두뇌로 돈다 (되돌리기: .bak 을 원래 이름으로)")
    print(f"동물 세계: {'준비됨 — 물소·표범·여우도 함께 돈다' if ready else '아직 (fauna/ 에 buffalo·leopard·fox.r9brain + scene.txt 가 다 있어야 함) — 지금 세 종으로 돈다'}"
          f" · 있는 새 종 두뇌 {have}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

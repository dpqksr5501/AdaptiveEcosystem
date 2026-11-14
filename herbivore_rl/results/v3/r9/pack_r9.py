"""R9 두뇌 팩 — 이어 학습의 출발 판·돌려받는 판을 한 폴더에 묶고 확인한다 (클라우드 학습 안내
AdaptiveEcosystem/Docs/RL_Policy/R9_CLOUD_TRAINING.md 3 절).

    python -X utf8 results/v3/r9/pack_r9.py make   --src <판 폴더> --name <팩 이름> --config <설정> [--versions last|all] [--reports <폴더> …]
    python -X utf8 results/v3/r9/pack_r9.py verify <팩 폴더> [--config <설정>]
    python -X utf8 results/v3/r9/pack_r9.py show   <팩 폴더>

- 팩 = `manifest.json` + 종 폴더(<종>/<종>_r<바퀴>_<결정>.zip·.npz·.json) + 선택 `reports/`. 종마다 이어 배울 zip 하나와 상대 판 목록(npz,
  오래된 것부터)을 적는다. 모든 파일의 sha256 을 manifest 에 남겨, 받은 쪽이 같은 출발점인지 확인한다.
- `ckpt/` 는 git 밖이라 출발 판을 팩으로 저장소에 넣는다(종마다 zip 0.5~0.9 MB + npz 60 KB). history.json(1 MB 넘음)은 넣지 않는다.
- verify 는 sha256·npz 계약(모양·이름·io_hash·종)을 보고, --config 를 주면 몸 해시가 그 세계와 같은지(아니면 rebody 가 필요한지) 적는다.
  가중치는 읽기만 하고 바꾸지 않는다. 몸이 다른 세계로 옮기는 일은 chain_r9.py 가 rebody_r9 와 같은 길(`rebody_brain`)로 한다.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PACK_FORMAT = "r9-pack"
PACK_VERSION = 1
SNAP_RE = re.compile(r"^(?P<sp>[a-z]+)_r(?P<round>\d+)_(?P<dec>\d+)$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p: Path, base: Path) -> str:
    return p.resolve().relative_to(base.resolve()).as_posix()


def abs_root(p: str | Path) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def git_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.strip() or "?"
    except Exception:  # noqa: BLE001
        return "?"


def snapshots(folder: Path, sp: str, below_round: int | None = None) -> list[tuple[int, int, Path]]:
    """`<sp>_r<바퀴>_<결정>.npz` 판을 (바퀴, 결정) 차례로. below_round 를 주면 그 바퀴보다 앞 판만."""
    out = []
    if not folder.is_dir():
        return out
    for p in folder.glob(f"{sp}_r*_*.npz"):
        m = SNAP_RE.match(p.stem)
        if not m or m["sp"] != sp:
            continue
        r = int(m["round"])
        if below_round is not None and r >= below_round:
            continue
        out.append((r, int(m["dec"]), p))
    return sorted(out)


def _brain_info(npz: Path, cfg: dict | None, sp: str) -> dict:
    """npz 계약 확인 + 몸 해시. cfg 가 있으면 그 세계 몸과 같은지."""
    from env_v2 import r9_body as B
    from env_v2 import r9_brains as BR

    _, meta = BR._read_npz(npz, BR._species_index(sp))
    info = {"body_hash": meta["body_hash"], "round": int(meta["round"]), "decisions": int(meta["decisions"]),
            "branch": meta["branch"], "config_digest": meta["config_digest"]}
    if cfg is not None:
        info["same_body"] = meta["body_hash"] == B.hash_hex(B.body_hash(cfg, BR._species_index(sp)))
    return info


def make(src: Path, dst: Path, config: str, species: list[str] | None, versions: str, reports: list[Path], note: str,
         extra: dict | None = None) -> dict:
    """판 폴더 src(<종>_r<바퀴>_<결정>.zip/.npz/.json) → 팩 dst. 종마다 가장 늦은 판(zip 이 있는 것)을 이어 배울 판으로."""
    from env_v2 import r9_body as B
    from env_v2 import r9_brains as BR

    if dst.exists():
        raise FileExistsError(f"{dst} 가 이미 있다 — 다른 이름을 쓰거나 지운 뒤 다시")
    cfg = B.load_r9_config(abs_root(config))
    sps = species or [sp for sp in B.ALL_SPECIES[:B.STAGE1_MAX_SPECIES] if snapshots(src, sp)]
    if not sps:
        raise FileNotFoundError(f"{src} 에 <종>_r<바퀴>_<결정>.npz 판이 없다")
    dst.mkdir(parents=True)
    man = {"format": PACK_FORMAT, "version": PACK_VERSION, "name": dst.name, "created": dt.datetime.now().isoformat(timespec="seconds"),
           "git_sha": git_sha(), "config": Path(config).as_posix(), "config_digest": BR.config_digest(cfg),
           "body_table_hash": B.hash_hex(B.body_table_hash(cfg)), "source": str(src), "note": note, "species": {}, "files": {}}
    if extra:
        man.update(extra)
    try:
        for sp in sps:
            snaps = [s for s in snapshots(src, sp) if s[2].with_suffix(".zip").exists()]
            if not snaps:
                raise FileNotFoundError(f"{src}: {sp} 판에 zip 이 없다 (이어 배울 수 없음)")
            last = snaps[-1][2]
            keep = [s[2] for s in snapshots(src, sp)] if versions == "all" else [last]
            d = dst / sp
            d.mkdir()
            for npz in keep:
                for ext in (".npz", ".json"):
                    if npz.with_suffix(ext).exists():
                        shutil.copy2(npz.with_suffix(ext), d / npz.with_suffix(ext).name)
            shutil.copy2(last.with_suffix(".zip"), d / last.with_suffix(".zip").name)
            vers = []
            for npz in keep:
                info = _brain_info(d / npz.name, cfg, sp)
                if not info["same_body"]:
                    raise ValueError(f"{npz} 의 몸 해시가 --config {config} 의 {sp} 몸과 다르다 — 그 판을 만든 설정을 주어야 한다")
                vers.append({"npz": f"{sp}/{npz.name}", "round": info["round"], "decisions": info["decisions"], "body_hash": info["body_hash"]})
            man["species"][sp] = {"zip": f"{sp}/{last.with_suffix('.zip').name}", "versions": vers}
        for r in reports:
            if r.is_dir():
                for p in sorted(r.rglob("*")):
                    if p.is_file() and not p.name.endswith(".history.json"):
                        q = dst / "reports" / r.name / p.relative_to(r)
                        q.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(p, q)
            elif r.is_file():
                (dst / "reports").mkdir(exist_ok=True)
                shutil.copy2(r, dst / "reports" / r.name)
        for p in sorted(dst.rglob("*")):
            if p.is_file() and p.name != "manifest.json":
                man["files"][rel(p, dst)] = sha256(p)
        (dst / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    except BaseException:
        shutil.rmtree(dst, ignore_errors=True)
        raise
    return man


def load_manifest(pack: Path) -> dict:
    mp = pack / "manifest.json"
    if not mp.exists():
        raise FileNotFoundError(f"{mp} 가 없다 (팩 폴더가 아님)")
    man = json.loads(mp.read_text(encoding="utf-8"))
    if man.get("format") != PACK_FORMAT or int(man.get("version", -1)) != PACK_VERSION:
        raise ValueError(f"{mp}: format {man.get('format')!r} v{man.get('version')} 은 {PACK_FORMAT} v{PACK_VERSION} 이 아니다")
    return man


def verify(pack: Path, config: str | None = None) -> dict:
    """{"ok": bool, "problems": [...], "species": {종: {"same_body": bool|None, "versions": n}}}. 문제가 있으면 ok False."""
    from env_v2 import r9_body as B

    man = load_manifest(pack)
    problems = []
    for name, want in man["files"].items():
        p = pack / name
        if not p.is_file():
            problems.append(f"없는 파일 {name}")
        elif sha256(p) != want:
            problems.append(f"sha256 다름 {name}")
    listed = {rel(p, pack) for p in pack.rglob("*") if p.is_file() and p.name != "manifest.json"}
    for name in sorted(listed - set(man["files"])):
        problems.append(f"manifest 에 없는 파일 {name}")
    cfg = B.load_r9_config(abs_root(config)) if config else None
    out = {}
    for sp, ent in man["species"].items():
        if not (pack / ent["zip"]).is_file():
            problems.append(f"{sp}: 이어 배울 zip 없음 {ent['zip']}")
        same = []
        for v in ent["versions"]:
            try:
                info = _brain_info(pack / v["npz"], cfg, sp)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{sp}: {v['npz']} 계약 실패 — {exc}")
                continue
            if info["body_hash"] != v["body_hash"]:
                problems.append(f"{sp}: {v['npz']} 몸 해시가 manifest 와 다름")
            same.append(info.get("same_body"))
        out[sp] = {"versions": len(ent["versions"]), "same_body": None if cfg is None else all(bool(s) for s in same)}
    return {"ok": not problems, "problems": problems, "species": out, "config": man["config"], "config_digest": man["config_digest"],
            "name": man["name"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make", help="판 폴더 → 팩")
    m.add_argument("--src", required=True, help="판 폴더 (예 ckpt/r9_cloud/<줄>/<줄>)")
    m.add_argument("--name", required=True, help="팩 이름 (폴더 이름)")
    m.add_argument("--config", required=True, help="그 판들을 만든 세계 설정")
    m.add_argument("--out-dir", default=str(HERE / "packs"))
    m.add_argument("--species", nargs="*", default=None)
    m.add_argument("--versions", choices=("last", "all"), default="last", help="상대 판 목록: 마지막 판만 | 모든 판")
    m.add_argument("--reports", nargs="*", default=[], help="같이 넣을 보고·기록 폴더/파일 (history.json 은 뺌)")
    m.add_argument("--note", default="")
    v = sub.add_parser("verify", help="sha256·npz 계약·(설정을 주면) 몸 해시")
    v.add_argument("pack")
    v.add_argument("--config", default=None)
    s = sub.add_parser("show", help="manifest 요약")
    s.add_argument("pack")
    a = ap.parse_args(argv)
    if a.cmd == "make":
        man = make(abs_root(a.src), abs_root(a.out_dir) / a.name, a.config, a.species, a.versions, [abs_root(r) for r in a.reports], a.note)
        print(json.dumps({"pack": str(abs_root(a.out_dir) / a.name), "species": {k: v["zip"] for k, v in man["species"].items()},
                          "files": len(man["files"])}, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "verify":
        r = verify(abs_root(a.pack), a.config)
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 0 if r["ok"] else 1
    man = load_manifest(abs_root(a.pack))
    print(f"{man['name']} · {man['created']} · git {man['git_sha']} · 설정 {man['config']} ({man['config_digest']})")
    for sp, ent in man["species"].items():
        vs = ", ".join(f"r{x['round']}:{x['decisions']:,}" for x in ent["versions"])
        print(f"  {sp:8s} zip {Path(ent['zip']).name} · 상대 판 {vs}")
    if man.get("note"):
        print(f"  메모: {man['note']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

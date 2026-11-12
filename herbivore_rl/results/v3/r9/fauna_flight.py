"""R9 동물 세계 시험 비행 — 첫 밤 한 번 (동물 설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_SPECIES_TRAITS.md 6-3·9-6). 정식 풀 밖,
S′ 관문 전 값이다. 결과는 '몸 숫자가 맞나' 확인용이고 판정이 아니다.

    python -X utf8 results/v3/r9/spawn_detached.py --log results/v3/r9/logs/fauna_flight_A.log --what "fauna flight A" \
        -- results/v3/r9/fauna_flight.py --branch A
    python -X utf8 results/v3/r9/fauna_flight.py --branch A --dry-run          # 명령만 출력

단계 (각 단계 끝마다 <out>/<branch>/flight.json 을 다시 쓴다 — 명령·시작/끝·멈춤 이유·결과 판 경로·sha256):
  0 (수 초)   옛 세 종 데모 두뇌를 `rebody_r9.py` 로 동물 세계 몸에 옮긴다 → <start>/{deer,wolf,boar}_v0.npz (메타 init_from)
  1 (약 1.4 시간, 프로세스 6 개) 물소 10M(조각 2, 멧돼지 zip 에서)·표범 5M(조각 2, 늑대 zip)·여우 5M(조각 2, 늑대 zip) 동시에.
              상대: 옛 세 종 = v0 100%, 새 종끼리 = 규칙 두뇌 100%. 학습률 3e-4 (0 바퀴 값)
  2 (약 1.1 시간) 늑대 10M(조각 3, 데모 늑대 zip 이어 배우기, 학습률 1e-4). 상대: 사슴·멧돼지 v0, 물소·표범·여우 = 1 단계 마지막 판
  3 (약 30 분) `fauna_report.py --flight <out>/<branch>` (장면 S1·S2·자연 세계 N)
한 묶음이라도 stop ∈ {error, nan, cut} 이면 그 단계에서 멈추고 flight.json 에 적는다. 각 묶음의 화면 기록은
results/v3/r9/logs/fl_<branch>_<종>.log, 학습 기록 줄은 results/v3/r9/logs/fl_<branch>_<종>.log.jsonl.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
LOGS = HERE.parent / "logs"

OLD3 = ("deer", "wolf", "boar")
NEW3 = ("buffalo", "leopard", "fox")
SRC_STEM = {"deer": "deer_r0_20013056", "wolf": "wolf_r0_7845120", "boar": "boar_r0_10027008"}   # 데모 두뇌 (STATUS 0 절)
# 1 단계 (6-3): 종 → (출발 zip 의 종, 결정 수, 조각)
STAGE1 = {"buffalo": ("boar", 10_000_000, 2), "leopard": ("wolf", 5_000_000, 2), "fox": ("wolf", 5_000_000, 2)}
STAGE2 = ("wolf", "wolf", 10_000_000, 3)


def _abs(p) -> Path:
    q = Path(p)
    return q if q.is_absolute() else ROOT / q


def _rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Flight:
    def __init__(self, a):
        self.a = a
        self.branch = str(a.branch)
        self.out = _abs(a.out)                    # train_r9 --out (it adds /<branch>)
        self.dir = self.out / self.branch
        self.src = _abs(a.src_dir)
        self.start = _abs(a.start_dir)
        self.cfg = a.config
        self.state = dict(branch=self.branch, config=a.config, gamma=a.gamma, out=_rel(self.dir), stages=[],
                          started=time.strftime("%Y-%m-%d %H:%M:%S"), stop=None,
                          note="시험 비행 — 정식 풀 밖, S′ 관문 전 값. 판정 아님 (RL_R9_SPECIES_TRAITS.md 6-3)")
        self.path = self.dir / "flight.json"

    # --- bookkeeping ---
    def save(self) -> None:
        if self.a.dry_run:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")

    def stage(self, name: str) -> dict:
        st = dict(stage=name, started=time.strftime("%Y-%m-%d %H:%M:%S"), commands=[], runs={}, finished=None, stop=None)
        self.state["stages"].append(st)
        self.save()
        return st

    def end(self, st: dict, stop: str | None = None) -> None:
        st["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        st["stop"] = stop
        if stop:
            self.state["stop"] = f"{st['stage']}: {stop}"
        self.save()

    # --- commands ---
    def py(self) -> list[str]:
        return [sys.executable, "-X", "utf8"]

    def train_cmd(self, sp: str, init_sp: str, decisions: int, shards: int, pool: Path, shares: dict, lr: float | None,
                  wall: float) -> list[str]:
        c = self.py() + [str(HERE.parent / "train_r9.py"), "--config", self.cfg, "--species", sp, "--branch", self.branch,
                         "--round", "0", "--gamma", str(self.a.gamma), "--init", str(self.src / f"{SRC_STEM[init_sp]}.zip"),
                         "--init-species", init_sp, "--pool", str(pool), "--shares", json.dumps(shares, separators=(",", ":")),
                         "--decisions", str(int(decisions)), "--wall-hours", str(wall), "--shards", str(int(shards)),
                         "--out", str(self.out), "--run-name", f"fl_{self.branch}_{sp}"]
        if lr is not None:
            c += ["--learning-rate", str(lr)]
        if self.a.decisions_scale != 1.0:
            i = c.index("--decisions")
            c[i + 1] = str(max(1, int(int(decisions) * self.a.decisions_scale)))
        return c

    def run_parallel(self, st: dict, cmds: dict) -> dict:
        """Start every command (no window), wait for all; returns {name: run meta dict or None}."""
        procs = {}
        for name, cmd in cmds.items():
            st["commands"].append(dict(name=name, cmd=cmd))
            if self.a.dry_run:
                print(" ".join(f'"{x}"' if (" " in x or "{" in x) else x for x in cmd))
                continue
            LOGS.mkdir(parents=True, exist_ok=True)
            lf = open(LOGS / f"fl_{self.branch}_{name}.log", "w", encoding="utf-8")
            env = dict(os.environ, PYTHONUTF8="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            procs[name] = (subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT,
                                            creationflags=flags), lf)
        self.save()
        out = {}
        for name, (p, lf) in procs.items():
            rc = p.wait()
            lf.close()
            meta_p = self.dir / f"fl_{self.branch}_{name}.json"
            meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else None
            last = (meta or {}).get("snapshots") or []
            npz = _abs(last[-1]["npz"]) if last else None
            st["runs"][name] = dict(rc=rc, stop=(meta or {}).get("stop"), meta=_rel(meta_p) if meta else None,
                                    timesteps=(meta or {}).get("timesteps"), wall_s=(meta or {}).get("wall_s"),
                                    dec_per_s=(meta or {}).get("dec_per_s"),
                                    npz=_rel(npz) if npz else None, npz_sha256=sha256(npz) if npz and npz.exists() else None)
            out[name] = st["runs"][name]
        self.save()
        return out

    # --- stages ---
    def stage0(self) -> dict:
        st = self.stage("0 rebody")
        v0 = {}
        for sp in OLD3:
            src = self.src / f"{SRC_STEM[sp]}.npz"
            dst = self.start / f"{sp}_v0.npz"
            cmd = self.py() + [str(HERE.parent / "rebody_r9.py"), "--config", self.cfg, "--species", sp, "--src", str(src),
                               "--out", str(dst)]
            st["commands"].append(dict(name=sp, cmd=cmd))
            v0[sp] = dst
            if self.a.dry_run:
                print(" ".join(cmd))
                continue
            r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if r.returncode != 0:
                st["runs"][sp] = dict(rc=r.returncode, error=r.stderr[-4000:])
                self.end(st, f"rebody {sp} failed")
                return {}
            st["runs"][sp] = dict(rc=0, npz=_rel(dst), npz_sha256=sha256(dst), src=_rel(src), src_sha256=sha256(src))
        self.end(st)
        return v0

    def run(self) -> int:
        a = self.a
        for sp in OLD3:
            for ext in (".zip", ".npz"):
                p = self.src / f"{SRC_STEM[sp]}{ext}"
                if not p.exists() and not a.dry_run:
                    raise FileNotFoundError(f"{p} 가 없다 — SPECIES_START.md '시작 판 복사' 를 먼저")
        v0 = self.stage0()
        if not v0:
            return 1
        # stage 1
        st = self.stage("1 buffalo·leopard·fox")
        pool0 = self.dir / "pool_f0.json"
        if not a.dry_run:
            self.dir.mkdir(parents=True, exist_ok=True)
            pool0.write_text(json.dumps({"pool": {sp: [str(v0[sp])] for sp in OLD3}}, indent=1), encoding="utf-8")
        cmds = {}
        for sp, (init_sp, dec, shards) in STAGE1.items():
            shares = {o: {"current": 1.0} for o in OLD3}
            shares.update({o: {"rule": 1.0} for o in NEW3 if o != sp})
            cmds[sp] = self.train_cmd(sp, init_sp, dec, shards, pool0, shares, None, a.wall_hours_1)
        res = self.run_parallel(st, cmds)
        bad = [n for n, r in res.items() if r["stop"] not in ("target", "wall_clock")]
        if bad and not a.dry_run:
            self.end(st, "stop " + ", ".join(f"{n}={res[n]['stop']}" for n in bad))
            return 1
        self.end(st)
        # stage 2
        st = self.stage("2 wolf")
        pool1 = self.dir / "pool_f1.json"
        if not a.dry_run:
            pool = {"deer": [str(v0["deer"])], "boar": [str(v0["boar"])]}
            pool.update({sp: [str(_abs(res[sp]["npz"]))] for sp in NEW3})
            pool1.write_text(json.dumps({"pool": pool}, indent=1), encoding="utf-8")
        sp, init_sp, dec, shards = STAGE2
        shares = {o: {"current": 1.0} for o in ("deer", "boar") + NEW3}
        res2 = self.run_parallel(st, {sp: self.train_cmd(sp, init_sp, dec, shards, pool1, shares, 1e-4, a.wall_hours_2)})
        if not a.dry_run and res2[sp]["stop"] not in ("target", "wall_clock"):
            self.end(st, f"stop wolf={res2[sp]['stop']}")
            return 1
        self.end(st)
        # stage 3
        st = self.stage("3 report")
        cmd = self.py() + [str(HERE.parent / "fauna_report.py"), "--flight", str(self.dir), "--config", self.cfg]
        st["commands"].append(dict(name="report", cmd=cmd))
        if a.dry_run:
            print(" ".join(cmd))
            return 0
        LOGS.mkdir(parents=True, exist_ok=True)
        with open(LOGS / f"fl_{self.branch}_report.log", "w", encoding="utf-8") as lf:
            rc = subprocess.run(cmd, cwd=str(ROOT), stdout=lf, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0).returncode
        st["runs"]["report"] = dict(rc=rc)
        self.end(st, None if rc == 0 else f"report rc {rc}")
        self.state["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self.save()
        return 0 if rc == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--branch", default="A")
    ap.add_argument("--config", default="configs/v3_r9_fauna.yaml")
    ap.add_argument("--src-dir", default="ckpt/r9_fauna/start/src", help="데모 두뇌 zip·npz (SPECIES_START.md 시작 판 복사)")
    ap.add_argument("--start-dir", default="ckpt/r9_fauna/start", help="0 단계 rebody 결과 {deer,wolf,boar}_v0.npz")
    ap.add_argument("--out", default="ckpt/r9_fauna/flight", help="train_r9 --out (그 아래 <branch>/)")
    ap.add_argument("--gamma", type=float, default=0.99, help="시험 비행 = 데모와 같은 0.99 (C0-10 전) [판단]")
    ap.add_argument("--wall-hours-1", type=float, default=4.0)
    ap.add_argument("--wall-hours-2", type=float, default=3.0)
    ap.add_argument("--decisions-scale", type=float, default=1.0, help="스모크용 결정 수 배율 (기본 1 = 6-3 값)")
    ap.add_argument("--dry-run", action="store_true", help="명령만 출력")
    a = ap.parse_args(argv)
    return Flight(a).run()


if __name__ == "__main__":
    sys.exit(main())

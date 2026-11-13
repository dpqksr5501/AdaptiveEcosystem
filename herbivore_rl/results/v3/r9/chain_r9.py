"""R9 이어 학습 실행기 — 팩에서 출발해 여러 종이 바퀴마다 함께 이어 배운다. 윈도우·리눅스(클라우드) 어디서나 같은 명령
(안내 AdaptiveEcosystem/Docs/RL_Policy/R9_CLOUD_TRAINING.md).

    python -X utf8 results/v3/r9/chain_r9.py check  --pack <팩> --config <설정> [--line <줄>]
    python -X utf8 results/v3/r9/chain_r9.py run    --pack <팩> --config <설정> --line <줄> [--rounds N] [--detach] [--smoke] [--dry-run]
    python -X utf8 results/v3/r9/chain_r9.py status --line <줄>
    python -X utf8 results/v3/r9/chain_r9.py stop   --line <줄> [--now]
    python -X utf8 results/v3/r9/chain_r9.py pack   --line <줄> [--name <팩 이름>]

같은 꼴: 2026-11-13 세션 스크래치의 fauna_chain.py(지금 몸)·motion_chain.py(M1). 다른 점은 경로·파이썬을 박지 않고, 끊겨도 같은 명령으로
이어 가며, 결과를 팩으로 돌려준다는 것이다.
- 바퀴 r: 종마다 자기 앞 바퀴 마지막 zip(바퀴 1 = 팩 zip)에서 `train_r9.py` 로 이어 배운다. 상대 = 다른 종의 팩 판 + 바퀴 r 앞의 모든 판
  (묶음 시작 때 고정, 설정 'later' 몫 current 0.5 · past 0.3 · rule 0.2). 모든 종이 끝나면 자연 세계 N 보고(`fauna_report.py --only N`).
- 팩 몸이 --config 세계 몸과 다르면(예: 지금 몸 팩 → M1 설정) 상대 npz 를 `rebody_brain` 으로 옮겨 `<줄 폴더>/start/` 에 둔다(가중치 그대로).
- 줄 이름(`--line`)은 소문자로 시작한다. 이 PC 리그 갈래 A·B 와 겹치지 않게 모델 시드 기본값 = 100 + crc32(줄) % 900.
- 처음 `run` 이 `plan.json` 을 쓴다. 다시 띄울 때 고정 값(팩·설정·종·모델 시드·γ·결정 수·판 간격·상대 몫)이 다르면 거부한다(`--replan` 은 기록을 남기고 바꿈).
  바퀴 수·끝 시각·조각 수·벽시계 상한은 다시 띄울 때 바꿔도 된다.
- 끊김: 묶음 끝 기록이 `cut`(메모리 부족·조각 프로세스 잃음)이거나 끝 기록 없이 판만 남았으면(컴퓨터가 꺼짐) 그 바퀴 판을 `_partial/` 로 옮기고
  앞 바퀴 마지막 판에서 다시(종마다 최대 3 번). `error`·`nan` 이면 멈추고 사람이 본다. 돌던 학습 프로세스가 살아 있으면 새로 띄우지 않고 기다린다.
- 멈춤: `stop`(= `<줄 폴더>/STOP`) 은 다음 바퀴를 안 띄운다. `stop --now` 는 도는 묶음도 끝낸다(그 바퀴는 다음에 처음부터).

줄 폴더 `<--out>/<줄>/`: plan.json · state.json · chain.log · runner.out · start/ · <줄>/(판 zip·npz·json, 묶음 끝 기록) · logs/ · eval/ · _partial/.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import pack_r9 as P  # noqa: E402

LINE_RE = re.compile(r"^[a-z][a-z0-9-]{1,23}$")
DEFAULT_OUT = "ckpt/r9_cloud"
SPECIES6 = ("deer", "wolf", "boar", "buffalo", "leopard", "fox")
SHARES = {"current": 0.5, "past": 0.3, "rule": 0.2}            # 설정 train.opponents.later 와 같음
SHARDS_FULL = {"deer": 1, "wolf": 2, "boar": 1, "buffalo": 2, "leopard": 2, "fox": 2}   # 이 PC 이어 학습과 같음
PROC_GB = 0.45                                       # 학습·조각 프로세스 하나 어림 (STATUS 3-1 · 11-13 이어 학습 0.35~0.41 GB)
OK_STOPS = ("target", "wall_clock")
MAX_ATTEMPTS = 3
STOPPED = 3                                          # run_round: 사람이 stop --now 로 멈춤 (평가하지 않고 끝)
FIXED = ("pack", "pack_manifest_sha256", "config", "config_digest", "species", "model_seed", "gamma", "decisions", "snapshot_every",
         "shares")
POLL_S = 20


# ---------------------------------------------------------------- 공통

def now() -> dt.datetime:
    return dt.datetime.now()


def child_env() -> dict:
    return dict(os.environ, PYTHONUTF8="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                PYTHONDONTWRITEBYTECODE="1")


def no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def root_rel(p: Path) -> str:
    """herbivore_rl 안이면 상대 경로(다른 컴퓨터에서도 같은 글자), 밖이면 절대 경로."""
    try:
        return p.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(p.resolve())


def model_seed_for(line: str) -> int:
    return 100 + zlib.crc32(line.encode()) % 900


def pid_alive(pid: int, marker: str | None = None) -> bool:
    """pid 가 살아 있고 (marker 를 주면) 명령 줄에 marker 가 들어 있는지."""
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil is not None:
        try:
            p = psutil.Process(int(pid))
            if p.status() == psutil.STATUS_ZOMBIE:
                return False
            return marker is None or marker in " ".join(p.cmdline())
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
            return False
    if os.name == "nt":
        return False
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def kill_tree(pid: int) -> None:
    try:
        import psutil

        p = psutil.Process(int(pid))
        kids = p.children(recursive=True)
        for c in kids + [p]:
            try:
                c.kill()
            except psutil.NoSuchProcess:
                pass
    except Exception:  # noqa: BLE001
        try:
            os.kill(int(pid), signal.SIGTERM)
        except OSError:
            pass


class Line:
    """줄 폴더 하나의 경로와 기록."""

    def __init__(self, out: str, line: str):
        if not LINE_RE.match(line):
            raise SystemExit(f"줄 이름 {line!r}: 소문자로 시작하고 소문자·숫자·'-' 만, 2~24 글자 (A·B 는 이 PC 리그 갈래)")
        self.name = line
        self.dir = P.abs_root(out) / line
        self.snaps = self.dir / line                 # train_r9 --out <줄 폴더> --branch <줄> → <줄 폴더>/<줄>/
        self.logs = self.dir / "logs"
        self.eval = self.dir / "eval"
        self.start = self.dir / "start"
        self.partial = self.dir / "_partial"
        self.plan_path = self.dir / "plan.json"
        self.state_path = self.dir / "state.json"
        self.log_path = self.dir / "chain.log"
        self.lock = self.dir / "runner.pid"
        self.stop_path = self.dir / "STOP"

    def run_name(self, sp: str, r: int) -> str:
        return f"ch_{self.name}_{sp}_r{r}"

    def meta(self, sp: str, r: int) -> dict | None:
        p = self.snaps / f"{self.run_name(sp, r)}.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def log(self, msg: str) -> None:
        line = f"[{now():%m-%d %H:%M:%S}] {msg}"
        print(line, flush=True)
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8")) if self.state_path.exists() else {}

    def save_state(self, **kw) -> dict:
        s = self.state()
        s.update(kw, updated=now().isoformat(timespec="seconds"))
        self.state_path.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
        return s


# ---------------------------------------------------------------- 계획

def build_plan(a, line: Line) -> dict:
    from env_v2 import r9_body as B
    from env_v2 import r9_brains as BR

    pack = P.abs_root(a.pack)
    man = P.load_manifest(pack)
    cfg = B.load_r9_config(P.abs_root(a.config))
    in_cfg = list(B.species_of(cfg))
    species = list(a.species) if a.species else [sp for sp in in_cfg if sp in man["species"]]
    miss = [sp for sp in species if sp not in man["species"] or sp not in in_cfg]
    if miss:
        raise SystemExit(f"종 {miss}: 팩({sorted(man['species'])})과 설정({in_cfg}) 둘 다에 있어야 한다")
    smoke = bool(a.smoke)
    plan = {
        "line": line.name, "created": now().isoformat(timespec="seconds"), "git_sha": P.git_sha(),
        "pack": root_rel(pack), "pack_name": man["name"], "pack_manifest_sha256": P.sha256(pack / "manifest.json"),
        "config": Path(a.config).as_posix(), "config_digest": BR.config_digest(cfg), "species": species,
        "model_seed": int(a.model_seed if a.model_seed is not None else model_seed_for(line.name)),
        "gamma": float(a.gamma), "decisions": int(60_000 if smoke else a.decisions),
        "snapshot_every": int(30_000 if smoke else a.snapshot_every),
        "shares": json.loads(a.shares) if a.shares else SHARES, "smoke": smoke,
    }
    return plan


def check_plan(line: Line, plan: dict, replan: bool) -> dict:
    """처음이면 plan.json 을 쓰고, 있으면 고정 값이 같은지 본다."""
    if not line.plan_path.exists():
        line.dir.mkdir(parents=True, exist_ok=True)
        line.plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        return plan
    old = json.loads(line.plan_path.read_text(encoding="utf-8"))
    diff = {k: (old.get(k), plan.get(k)) for k in FIXED if old.get(k) != plan.get(k)}
    if diff and not replan:
        raise SystemExit("plan.json 과 고정 값이 다르다 (같은 줄은 같은 조건으로 이어 간다). 다른 줄 이름을 쓰거나 --replan:\n" +
                         "\n".join(f"  {k}: {o!r} → {n!r}" for k, (o, n) in diff.items()))
    if diff:
        hist = old.get("replans", [])
        hist.append({"at": now().isoformat(timespec="seconds"), "changed": {k: list(v) for k, v in diff.items()}})
        plan = dict(plan, replans=hist, created=old.get("created"))
        line.plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
        line.log("--replan: " + ", ".join(diff))
        return plan
    return old


def shards_for(spec: str, species: list[str], cpus: int, avail_gb: float | None) -> dict:
    if spec == "auto":
        full = {sp: SHARDS_FULL[sp] for sp in species}
        need = sum(full.values())
        ok_cpu = cpus >= need - 1
        ok_mem = avail_gb is None or need * PROC_GB <= 0.8 * avail_gb
        return full if ok_cpu and ok_mem else {sp: 1 for sp in species}
    if spec.isdigit():
        return {sp: int(spec) for sp in species}
    d = json.loads(spec)
    return {sp: int(d.get(sp, 1)) for sp in species}


def machine() -> dict:
    cpus = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    info = {"cpus": cpus, "python": sys.version.split()[0], "platform": sys.platform, "ram_gb": None, "avail_gb": None}
    try:
        import psutil

        vm = psutil.virtual_memory()
        info.update(ram_gb=round(vm.total / 2**30, 1), avail_gb=round(vm.available / 2**30, 1))
    except Exception:  # noqa: BLE001
        pass
    return info


def run_metas(line: "Line", sp: str) -> list[Path]:
    """이 종의 묶음 끝 기록 `ch_<줄>_<종>_r<바퀴>.json` (history.json 빼고), 바퀴 차례."""
    pat = re.compile(rf"^ch_{re.escape(line.name)}_{sp}_r(\d+)\.json$")
    found = [(int(m[1]), p) for p in line.snaps.glob(f"ch_{line.name}_{sp}_r*.json") if (m := pat.match(p.name))]
    return [p for _, p in sorted(found)]


def disk_free_gb(p: Path) -> float:
    while not p.exists():
        p = p.parent
    return shutil.disk_usage(p).free / 2**30


# ---------------------------------------------------------------- 출발 판

def prepare_start(line: Line, plan: dict, dry: bool) -> dict:
    """{종: (이어 배울 zip, [상대 판 npz …])}. 팩 몸이 설정 몸과 다르면 npz 를 rebody 해 start/ 에."""
    import numpy as np

    from env_v2 import r9_body as B
    from env_v2 import r9_brains as BR

    pack = P.abs_root(plan["pack"])
    man = P.load_manifest(pack)
    cfg = B.load_r9_config(P.abs_root(plan["config"]))
    out = {}
    for sp in plan["species"]:
        ent = man["species"][sp]
        want = B.hash_hex(B.body_hash(cfg, BR._species_index(sp)))
        vers = []
        for i, v in enumerate(ent["versions"]):
            src = pack / v["npz"]
            if v["body_hash"] == want:
                vers.append(src)
                continue
            dst = line.start / f"{sp}_s{i}.npz"
            if not dry:
                src_sha = P.sha256(src)
                if dst.exists():
                    with np.load(dst, allow_pickle=False) as z:
                        old = json.loads(str(z["meta_json"][()]))
                    if old.get("init_from", {}).get("sha256") != src_sha or old.get("body_hash") != want:
                        raise SystemExit(f"{dst} 가 이 팩·설정의 rebody 가 아니다 — 지우고 다시 (또는 다른 줄 이름)")
                else:
                    BR.rebody_brain(src, cfg, sp, dst)
                    BR.load_brain(dst, cfg, sp)
                    line.log(f"rebody {sp}: {v['npz']} (몸 {v['body_hash']}) → start/{dst.name} (몸 {want})")
            vers.append(dst)
        out[sp] = (pack / ent["zip"], vers)
    return out


def last_zip(line: Line, start: dict, sp: str, r: int) -> Path:
    """바퀴 r 이 이어 받을 zip = 바퀴 r 앞 마지막 판(zip 이 있는 것), 없으면 팩 zip."""
    for _, _, npz in reversed(P.snapshots(line.snaps, sp, below_round=r)):
        if npz.with_suffix(".zip").exists():
            return npz.with_suffix(".zip")
    return start[sp][0]


def pool_for(line: Line, plan: dict, start: dict, sp: str, r: int) -> dict:
    return {o: [str(p) for p in start[o][1]] + [str(x[2]) for x in P.snapshots(line.snaps, o, below_round=r)]
            for o in plan["species"] if o != sp}


# ---------------------------------------------------------------- 묶음

def train_cmd(line: Line, plan: dict, sp: str, r: int, init: Path, pool_file: Path, shards: int, wall_h: float) -> list[str]:
    shares = {o: plan["shares"] for o in plan["species"] if o != sp}
    return [sys.executable, "-X", "utf8", str(HERE / "train_r9.py"), "--config", plan["config"], "--species", sp,
            "--branch", line.name, "--model-seed", str(plan["model_seed"]), "--round", str(r), "--gamma", str(plan["gamma"]),
            "--init", str(init), "--init-species", sp, "--pool", str(pool_file), "--shares", json.dumps(shares, separators=(",", ":")),
            "--decisions", str(plan["decisions"]), "--wall-hours", f"{wall_h:.3f}", "--shards", str(shards),
            "--out", str(line.dir), "--log-dir", str(line.logs), "--run-name", line.run_name(sp, r),
            "--snapshot-every", str(plan["snapshot_every"])]


def move_partial(line: Line, sp: str, r: int, label: str) -> int:
    """바퀴 r 의 이 종 판·끝 기록·학습 줄을 _partial/r<r>_<종>_<label>/ 로. 옮긴 파일 수."""
    d = line.partial / f"r{r}_{sp}_{label}"
    n = 0
    files = [x[2] for x in P.snapshots(line.snaps, sp) if x[0] == r]
    files = [f.with_suffix(e) for f in files for e in (".npz", ".zip", ".json")]
    name = line.run_name(sp, r)
    files += [line.snaps / f"{name}.json", line.snaps / f"{name}.history.json", line.logs / f"{name}.log.jsonl",
              line.logs / f"{name}.log", line.logs / f"{name}.out"]
    for f in files:
        if f.exists():
            d.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(d / f.name))
            n += 1
    return n


def species_status(line: Line, sp: str, r: int) -> str:
    """ok | cut | error | partial | none."""
    m = line.meta(sp, r)
    if m is not None:
        st = m.get("stop")
        return "ok" if st in OK_STOPS else ("cut" if st == "cut" else "error")
    return "partial" if any(x[0] == r for x in P.snapshots(line.snaps, sp)) else "none"


def run_eval(line: Line, plan: dict, start: dict, r: int, eval_args: list[str]) -> str:
    brains = []
    for sp in plan["species"]:
        s = P.snapshots(line.snaps, sp, below_round=r + 1)
        brains.append(f"{sp}={s[-1][2] if s else start[sp][1][-1]}")
    line.eval.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-X", "utf8", str(HERE / "fauna_report.py"), "--config", plan["config"], "--only", "N", *eval_args,
           "--name", f"ch_r{r}", "--out-dir", str(line.eval), "--brains", *brains]
    with (line.eval / f"ch_r{r}.out").open("w", encoding="utf-8") as f:
        rc = subprocess.run(cmd, cwd=str(ROOT), env=child_env(), stdout=f, stderr=subprocess.STDOUT, creationflags=no_window()).returncode
    head = ""
    md = line.eval / f"ch_r{r}.md"
    if md.exists():
        head = next((x[2:] for x in md.read_text(encoding="utf-8").splitlines() if x.startswith("- 죽음")), "")
    return f"rc {rc} · {head}"


def run_chain(a) -> int:
    line = Line(a.out, a.line)
    if line.lock.exists():
        try:
            pid = int(line.lock.read_text().split()[0])
        except (ValueError, IndexError):
            pid = -1
        if pid != os.getpid() and pid_alive(pid, "chain_r9"):
            raise SystemExit(f"줄 {line.name} 실행기가 이미 돈다 (pid {pid}). 보기: chain_r9.py status --line {line.name}")
    plan = check_plan(line, build_plan(a, line), a.replan)
    mc = machine()
    shards = shards_for(a.shards, plan["species"], mc["cpus"], mc.get("avail_gb"))
    rounds = 2 if plan["smoke"] else a.rounds
    wall_h = 0.15 if plan["smoke"] else a.wall_hours
    eval_args = ["--worlds", "2", "--decisions", "60"] if plan["smoke"] else ["--worlds", str(a.eval_worlds)]
    until = dt.datetime.fromisoformat(a.until) if a.until else None
    line.dir.mkdir(parents=True, exist_ok=True)
    line.lock.write_text(f"{os.getpid()} {now().isoformat(timespec='seconds')}\n", encoding="utf-8")
    try:
        start = prepare_start(line, plan, dry=False)
        line.logs.mkdir(parents=True, exist_ok=True)
        line.log(f"시작 · 줄 {line.name} · 팩 {plan['pack_name']} · 설정 {plan['config']} ({plan['config_digest']}) · 종 {','.join(plan['species'])} · "
                 f"바퀴 {rounds} 까지 · 종마다 {plan['decisions']:,} 결정 (벽시계 {wall_h} h) · 판 {plan['snapshot_every']:,} 마다 · "
                 f"모델 시드 {plan['model_seed']} · 조각 {shards} · CPU {mc['cpus']} · 메모리 {mc.get('avail_gb')}/{mc.get('ram_gb')} GB · "
                 f"파이썬 {mc['python']} · git {P.git_sha()}")
        prev_wall = None
        for r in range(1, rounds + 1):
            ev = line.eval / f"ch_r{r}.md"
            done = all(species_status(line, sp, r) == "ok" for sp in plan["species"])
            if done and ev.exists():
                continue
            if line.stop_path.exists():
                line.log(f"STOP 파일 — 바퀴 {r} 안 띄움 ({line.stop_path.read_text(encoding='utf-8').strip()[:200]})")
                line.save_state(phase="stopped", round=r - 1, running={})
                return 0
            if until is not None and not done:
                est = dt.timedelta(hours=prev_wall if prev_wall else wall_h)
                if now() + est > until:
                    line.log(f"끝 시각 {until:%m-%d %H:%M} 전에 바퀴 {r} 를 못 끝냄 (어림 {est}) — 멈춤")
                    line.save_state(phase="until", round=r - 1, running={})
                    return 0
            t0 = time.time()
            rc = run_round(line, plan, start, r, shards, wall_h)
            if rc == STOPPED:
                return 0
            if rc != 0:
                return rc
            prev_wall = (time.time() - t0) / 3600
            if not ev.exists():
                line.save_state(phase="eval", round=r, running={})
                line.log(f"바퀴 {r} 평가(자연 세계 N): {run_eval(line, plan, start, r, eval_args)}")
            if a.round_hook:
                hook = a.round_hook.format(round=r, line_dir=str(line.dir), config=plan["config"], python=sys.executable)
                h = subprocess.run(hook, shell=True, cwd=str(ROOT), env=child_env())
                if h.returncode != 0:
                    line.stop_path.write_text(f"바퀴 {r} 뒤 --round-hook rc {h.returncode}: {hook}\n", encoding="utf-8")
                    line.log(f"--round-hook rc {h.returncode} — STOP 쓰고 멈춤")
                    line.save_state(phase="hook_stop", round=r, running={})
                    return 0
            line.save_state(phase="round_done", round=r, running={})
        line.log(f"끝 — 바퀴 {rounds} 까지 다 돎. 돌려줄 팩: chain_r9.py pack --line {line.name}")
        line.save_state(phase="done", round=rounds, running={})
        return 0
    finally:
        try:
            if line.lock.exists() and line.lock.read_text().split()[0] == str(os.getpid()):
                line.lock.unlink()
        except OSError:
            pass


def run_round(line: Line, plan: dict, start: dict, r: int, shards: dict, wall_h: float) -> int:
    attempts = line.state().get("attempts", {})
    running = {k: int(v) for k, v in line.state().get("running", {}).items()}
    while True:
        procs = {}                                    # 종 → (Popen | None, pid, 파일)
        for sp in plan["species"]:
            name = line.run_name(sp, r)
            st = species_status(line, sp, r)
            if st == "ok":
                continue
            if st == "error":
                m = line.meta(sp, r) or {}
                line.log(f"바퀴 {r} {sp}: 끝 기록 stop={m.get('stop')} — 멈춤, 사람이 본다 ({line.snaps / (name + '.json')})")
                line.save_state(phase="error", round=r, running={}, attempts=attempts)
                return 2
            pid = running.get(name)
            if pid and pid_alive(pid, name):
                procs[sp] = (None, pid, None)
                line.log(f"바퀴 {r} {sp}: 이미 도는 묶음 pid {pid} 를 기다림")
                continue
            k = attempts.get(name, 0)                 # 띄운 횟수 (처음 포함, 최대 MAX_ATTEMPTS)
            if k >= MAX_ATTEMPTS:
                line.log(f"바퀴 {r} {sp}: {k} 번 띄웠는데 끝나지 않음 ({st}) — 멈춤, 사람이 본다 ({line.logs / (name + '.out')})")
                line.save_state(phase="error", round=r, running={}, attempts=attempts)
                return 2
            if st in ("cut", "partial"):
                n = move_partial(line, sp, r, f"try{k}")
                line.log(f"바퀴 {r} {sp}: 끊긴 시도 {k} ({st}, 파일 {n} 개 → _partial/) — 앞 판에서 다시")
            attempts[name] = k + 1
            init = last_zip(line, start, sp, r)
            pool = pool_for(line, plan, start, sp, r)
            pf = line.logs / f"pool_{name}.json"
            pf.write_text(json.dumps({"pool": pool}, indent=1), encoding="utf-8")
            cmd = train_cmd(line, plan, sp, r, init, pf, shards[sp], wall_h)
            out = (line.logs / f"{name}.out").open("w", encoding="utf-8")
            p = subprocess.Popen(cmd, cwd=str(ROOT), env=child_env(), stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT,
                                 creationflags=no_window())
            procs[sp] = (p, p.pid, out)
            line.log(f"바퀴 {r} {sp}: 시작 pid {p.pid} · 이어 받음 {root_rel(init)} · 상대 판 {({o: len(v) for o, v in pool.items()})} · "
                     f"조각 {shards[sp]}")
        if not procs:
            return 0
        line.save_state(phase="train", round=r, running={line.run_name(sp, r): v[1] for sp, v in procs.items()}, attempts=attempts)
        left = dict(procs)
        while left:
            if (line.dir / "STOP_NOW").exists():
                for sp, (p, pid, out) in left.items():
                    kill_tree(pid)
                    if p is not None:
                        p.wait(timeout=60)
                    if out is not None:
                        out.close()
                    name = line.run_name(sp, r)
                    move_partial(line, sp, r, f"stop{now():%m%d%H%M%S}")
                    attempts[name] = max(0, attempts.get(name, 1) - 1)    # 사람이 멈춘 것은 띄운 횟수에 넣지 않음
                line.log(f"stop --now — 바퀴 {r} 묶음 {sorted(left)} 끝냄 (다음에 이 바퀴를 처음부터)")
                (line.dir / "STOP_NOW").unlink(missing_ok=True)
                line.save_state(phase="stopped", round=r - 1, running={}, attempts=attempts)
                return STOPPED
            for sp in list(left):
                p, pid, out = left[sp]
                end = (p.poll() is not None) if p is not None else not pid_alive(pid, line.run_name(sp, r))
                if not end:
                    continue
                if out is not None:
                    out.close()
                del left[sp]
                m = line.meta(sp, r) or {}
                snaps = [x for x in P.snapshots(line.snaps, sp) if x[0] == r]
                line.log(f"바퀴 {r} {sp}: 끝 rc {p.returncode if p is not None else '?'} · 멈춤 {m.get('stop')} · "
                         f"{(m.get('timesteps') or 0) / 1e6:.2f}M · {m.get('dec_per_s', 0):.0f}/s · 판 {len(snaps)} 개 · "
                         f"최신 {snaps[-1][2].name if snaps else '-'}")
            if left:
                time.sleep(POLL_S)
        running = {}
        if all(species_status(line, sp, r) == "ok" for sp in plan["species"]):
            line.save_state(phase="trained", round=r, running={}, attempts=attempts)
            return 0
        # cut·partial·error 가 남음 → 다시 돈다 (error 는 맨 위에서 멈춤)


# ---------------------------------------------------------------- 명령

def cmd_check(a) -> int:
    bad, warn = [], []
    mc = machine()
    print(f"파이썬 {mc['python']} ({sys.executable}) · {mc['platform']} · CPU {mc['cpus']} · 메모리 {mc.get('avail_gb')}/{mc.get('ram_gb')} GB")
    if sys.version_info < (3, 10):
        bad.append("파이썬 3.10 이상이 필요하다")
    elif sys.version_info < (3, 12):
        warn.append("확인한 파이썬은 3.12·3.13 이다 — 학습 줄기는 3.10 문법이지만 판정 도구 eval_r9.py 는 3.12 문법 (cloud_setup.sh 는 3.12 를 받는다)")
    vers = {}
    for mod in ("numpy", "yaml", "torch", "stable_baselines3", "gymnasium", "psutil"):
        try:
            vers[mod] = getattr(__import__(mod), "__version__", "?")
        except Exception as exc:  # noqa: BLE001
            bad.append(f"{mod} 를 못 읽음: {exc}")
    print("패키지 " + " · ".join(f"{k} {v}" for k, v in vers.items()))
    if "torch" in vers and "+cu" in vers["torch"]:
        warn.append("torch 가 CUDA 판이다 — 이 학습은 CPU 만 쓴다(설치 용량만 큼). requirements-r9.txt 의 CPU 판 권장")
    if bad:
        print("\n".join("✗ " + b for b in bad))
        return 1
    free = disk_free_gb(P.abs_root(a.out))
    print(f"디스크 남음 {free:.1f} GB ({P.abs_root(a.out)})")
    if free < 5:
        warn.append("디스크가 5 GB 보다 적다 — 바퀴마다 판이 종마다 5 개 × 0.7 MB 쌓인다(10 바퀴 ≈ 0.3 GB) + 기록")
    r = P.verify(P.abs_root(a.pack), a.config)
    print(f"팩 {r['name']} (설정 {r['config']} · {r['config_digest']}): " + ("확인 통과" if r["ok"] else "문제 있음"))
    for p in r["problems"]:
        bad.append(f"팩: {p}")
    for sp, s in r["species"].items():
        print(f"  {sp:8s} 상대 판 {s['versions']} · " + ("이 설정 몸 그대로" if s["same_body"] else "몸 다름 → run 이 rebody 해 쓴다"))
    from env_v2 import r9_body as B

    cfg = B.load_r9_config(P.abs_root(a.config))
    species = list(a.species) if a.species else [sp for sp in B.species_of(cfg) if sp in r["species"]]
    sh = shards_for(a.shards, species, mc["cpus"], mc.get("avail_gb"))
    n = sum(sh.values())
    print(f"동시 프로세스 {n} (조각 {sh}) · 어림 메모리 {n * PROC_GB:.1f} GB + 평가 0.3 GB")
    if mc.get("avail_gb") is not None and n * PROC_GB > 0.8 * mc["avail_gb"]:
        warn.append("남은 메모리가 빠듯하다 — --shards 1 또는 --species 로 줄이기")
    if mc["cpus"] < n:
        warn.append(f"CPU {mc['cpus']} < 프로세스 {n} — 느려지기만 하고 결과는 같다(조각 수는 결과를 바꾸지 않음)")
    if a.line:
        line = Line(a.out, a.line)
        if line.plan_path.exists():
            old = json.loads(line.plan_path.read_text(encoding="utf-8"))
            print(f"줄 {line.name}: plan.json 있음 (만든 때 {old.get('created')}, 모델 시드 {old.get('model_seed')}) — run 은 이어 간다")
        else:
            print(f"줄 {line.name}: 새 줄 (모델 시드 {a.model_seed if a.model_seed is not None else model_seed_for(line.name)})")
    for w in warn:
        print("! " + w)
    for b in bad:
        print("✗ " + b)
    print("결과: " + ("통과" if not bad else "실패"))
    return 0 if not bad else 1


def cmd_run(a) -> int:
    line = Line(a.out, a.line)
    if a.dry_run:
        plan = build_plan(a, line)
        mc = machine()
        shards = shards_for(a.shards, plan["species"], mc["cpus"], mc.get("avail_gb"))
        start = prepare_start(line, plan, dry=True)
        print(json.dumps(plan, ensure_ascii=False, indent=1))
        r = 1
        while all(species_status(line, sp, r) == "ok" for sp in plan["species"]):
            r += 1
        for sp in plan["species"]:
            print(subprocess.list2cmdline(train_cmd(line, plan, sp, r, last_zip(line, start, sp, r), line.logs / f"pool_{line.run_name(sp, r)}.json",
                                                    shards[sp], 0.15 if plan["smoke"] else a.wall_hours)))
        return 0
    if a.detach:
        line.dir.mkdir(parents=True, exist_ok=True)
        argv = [x for x in sys.argv[1:] if x != "--detach"]
        out = (line.dir / "runner.out").open("a", encoding="utf-8")
        kw = dict(cwd=str(ROOT), env=child_env(), stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
        if os.name == "nt":
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008   # DETACHED_PROCESS
        else:
            kw["start_new_session"] = True
        p = subprocess.Popen([sys.executable, "-X", "utf8", str(Path(__file__).resolve()), *argv], **kw)
        print(f"띄움 pid {p.pid} · 기록 {line.dir / 'runner.out'} · 보기: python -X utf8 results/v3/r9/chain_r9.py status --line {line.name}"
              + ("" if a.out == DEFAULT_OUT else f" --out {a.out}"))
        return 0
    return run_chain(a)


def cmd_status(a) -> int:
    line = Line(a.out, a.line)
    if not line.plan_path.exists():
        print(f"줄 {line.name}: 아직 없음 ({line.dir})")
        return 1
    plan = json.loads(line.plan_path.read_text(encoding="utf-8"))
    st = line.state()
    lock = line.lock.read_text().split()[0] if line.lock.exists() else None
    alive = bool(lock) and pid_alive(int(lock), "chain_r9")
    print(f"줄 {line.name} · 팩 {plan['pack_name']} · 설정 {plan['config']} · 모델 시드 {plan['model_seed']} · "
          f"실행기 {'도는 중 pid ' + lock if alive else '멈춤'} · 단계 {st.get('phase')} · 바퀴 {st.get('round')} · 갱신 {st.get('updated')}")
    if line.stop_path.exists():
        print("STOP 있음: " + line.stop_path.read_text(encoding="utf-8").strip()[:300])
    for sp in plan["species"]:
        s = P.snapshots(line.snaps, sp)
        last = s[-1] if s else None
        ms = run_metas(line, sp)
        m = json.loads(ms[-1].read_text(encoding="utf-8")) if ms else {}
        run = [n for n, pid in st.get("running", {}).items() if f"_{sp}_r" in n and pid_alive(pid, n)]
        print(f"  {sp:8s} 최신 판 {last[2].name if last else '-'} · 끝난 묶음 {m.get('run', '-')} ({m.get('stop', '-')}, "
              f"{m.get('dec_per_s', 0):.0f}/s, 누적 {(m.get('cum_timesteps') or 0) / 1e6:.1f}M)" + (" · 도는 중" if run else ""))
    evs = sorted(line.eval.glob("ch_r*.md"), key=lambda p: int(p.stem[4:])) if line.eval.exists() else []
    if evs:
        head = next((x[2:] for x in evs[-1].read_text(encoding="utf-8").splitlines() if x.startswith("- 죽음")), "")
        print(f"마지막 평가 {evs[-1].name}: {head}")
    if line.log_path.exists():
        print("--- chain.log 끝 8 줄")
        print("\n".join(line.log_path.read_text(encoding="utf-8").splitlines()[-8:]))
    return 0


def cmd_stop(a) -> int:
    line = Line(a.out, a.line)
    line.dir.mkdir(parents=True, exist_ok=True)
    line.stop_path.write_text(f"{now().isoformat(timespec='seconds')} 사람이 멈춤{' (--now)' if a.now else ''}\n", encoding="utf-8")
    if a.now:
        (line.dir / "STOP_NOW").write_text("1\n", encoding="utf-8")
        lock = line.lock.read_text().split()[0] if line.lock.exists() else None
        if not (lock and pid_alive(int(lock), "chain_r9")):
            for name, pid in line.state().get("running", {}).items():
                if pid_alive(pid, name):
                    kill_tree(pid)
            (line.dir / "STOP_NOW").unlink(missing_ok=True)
    print(f"STOP 씀: {line.stop_path} — 다시 띄우려면 이 파일을 지우고 같은 run 명령")
    return 0


def cmd_pack(a) -> int:
    line = Line(a.out, a.line)
    plan = json.loads(line.plan_path.read_text(encoding="utf-8"))
    st = line.state()
    rounds = sorted({x[0] for sp in plan["species"] for x in P.snapshots(line.snaps, sp)})
    if not rounds:
        raise SystemExit(f"{line.snaps} 에 판이 없다")
    name = a.name or f"{line.name}_r{rounds[-1]}"
    reports = [line.eval, line.logs, line.plan_path, line.state_path, line.log_path] + [m for sp in plan["species"] for m in run_metas(line, sp)]
    reports = [p for p in reports if p.exists()]
    extra = {"line": line.name, "rounds": rounds, "model_seed": plan["model_seed"], "from_pack": plan["pack_name"],
             "from_pack_manifest_sha256": plan["pack_manifest_sha256"], "phase": st.get("phase"), "smoke": plan.get("smoke", False)}
    man = P.make(line.snaps, P.abs_root(a.out_dir) / name, plan["config"], plan["species"], a.versions, reports, a.note, extra)
    size = sum((P.abs_root(a.out_dir) / name / f).stat().st_size for f in man["files"])
    print(f"팩 {P.abs_root(a.out_dir) / name} · 종 {len(man['species'])} · 파일 {len(man['files'])} · {size / 2**20:.1f} MB")
    print("돌려주기: 저장소 안이면 그 폴더를 새 가지(r9-train/<줄>)에 커밋해 push (R9_CLOUD_TRAINING.md 6 절)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, line_required=True):
        p.add_argument("--out", default=DEFAULT_OUT, help="줄 폴더들의 부모 (herbivore_rl 기준, 기본 ckpt/r9_cloud — git 밖)")
        p.add_argument("--line", required=line_required, default=None, help="줄 이름 (예 dots1)")

    def train_opts(p):
        p.add_argument("--pack", required=True, help="출발 팩 폴더 (예 results/v3/r9/packs/fauna_r2)")
        p.add_argument("--config", required=True, help="학습 세계 설정 (예 configs/v3_r9_fauna_motion.yaml)")
        p.add_argument("--species", nargs="*", default=None, help="배울 종 (기본 = 팩과 설정에 다 있는 종)")
        p.add_argument("--model-seed", type=int, default=None, help="기본 100 + crc32(줄) % 900")
        p.add_argument("--shards", default="auto", help="auto | 숫자 | JSON {종: n} (결과는 같고 속도·메모리만 바뀜)")

    c = sub.add_parser("check", help="환경·팩·자원 확인 (학습 안 함)")
    common(c, line_required=False)
    train_opts(c)

    r = sub.add_parser("run", help="이어 학습 (끊긴 곳부터 이어 감)")
    common(r)
    train_opts(r)
    r.add_argument("--rounds", type=int, default=10, help="이 바퀴까지 (다시 띄울 때 늘려도 됨)")
    r.add_argument("--decisions", type=int, default=5_000_000, help="종마다 바퀴당 결정 수 (고정)")
    r.add_argument("--snapshot-every", type=int, default=1_000_000, help="판 저장 간격 (고정)")
    r.add_argument("--wall-hours", type=float, default=4.0, help="묶음 하나의 벽시계 상한")
    r.add_argument("--gamma", type=float, default=0.99)
    r.add_argument("--shares", default=None, help="상대 몫 JSON (기본 current 0.5 · past 0.3 · rule 0.2)")
    r.add_argument("--until", default=None, help="이 시각(ISO, 예 2026-11-20T09:00) 전에 못 끝낼 바퀴는 안 띄움")
    r.add_argument("--eval-worlds", type=int, default=10)
    r.add_argument("--round-hook", default=None, help="바퀴마다 평가 뒤 실행할 셸 명령 ({round} {line_dir} {config} {python}); 0 아니면 STOP")
    r.add_argument("--smoke", action="store_true", help="아주 작게 2 바퀴 (설치 확인용; --out 을 따로 주기를 권함)")
    r.add_argument("--dry-run", action="store_true", help="계획과 다음 바퀴 명령만 보이기")
    r.add_argument("--detach", action="store_true", help="창 없이 떨어진 프로세스로 띄우고 바로 돌아옴")
    r.add_argument("--replan", action="store_true", help="고정 값을 바꿔 이어 감 (plan.json 에 기록)")

    s = sub.add_parser("status", help="진행 보기")
    common(s)
    t = sub.add_parser("stop", help="다음 바퀴 안 띄움 (--now: 도는 묶음도 끝냄)")
    common(t)
    t.add_argument("--now", action="store_true")
    k = sub.add_parser("pack", help="이 줄의 마지막 판을 돌려줄 팩으로")
    common(k)
    k.add_argument("--name", default=None, help="기본 <줄>_r<마지막 바퀴>")
    k.add_argument("--out-dir", default=str(HERE / "packs"))
    k.add_argument("--versions", choices=("last", "all"), default="last")
    k.add_argument("--note", default="")
    return ap


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    if getattr(a, "smoke", False) and a.out == DEFAULT_OUT:
        a.out = DEFAULT_OUT + "_smoke"                # 설치 확인 판이 진짜 줄과 섞이지 않게
    return {"check": cmd_check, "run": cmd_run, "status": cmd_status, "stop": cmd_stop, "pack": cmd_pack}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

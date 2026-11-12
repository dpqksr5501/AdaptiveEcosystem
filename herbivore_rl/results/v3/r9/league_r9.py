"""R9 league — rounds and bundles of the three species, two independent branches A·B (design AdaptiveEcosystem/Docs/RL_Policy/
RL_R9_MULTISPECIES_DESIGN.md 7-1~7-9, 9-4, 11절).

    python results/v3/r9/league_r9.py --dry-run                      # draw one round (no launch, no state write)
    python results/v3/r9/league_r9.py --decisions-json results/v3/r9/bundle_decisions.json --rounds 10
Started detached by `launch_league.ps1` (spawn_detached.py: no console window, new process group, out of the job object).

Round r (7-1·7-3):
  1 prey bundle   deer A · deer B · boar A · boar B learn at once (4 processes). Opponents (wolf + the other prey species) are fixed
                  brains picked from the branch's own pool when a world is renewed (7-4, r9_vec_env).
  2 wolf bundle   wolf A · wolf B (each `--shards` processes: 1 learner + shard workers, 7-3). Prey = fixed brains from the pool,
                  including this round's prey snapshots.
  3 check         even rounds: optional `--check-cmd` (8-5 / 9-4 — eval_r9.py check, another agent's tool). Without it the league
                  records 'check skipped'. The stop rule (9-4) is read by people/eval; the league halts after `--rounds`.
Branches never share pools (7-2). Pool entries = every snapshot of a finished bundle (in-bundle 10M / 5M + end), versions in order.

Before each launch (7-9, STATUS 5절 밤 창 — 사용자 11-10 '학습은 밤에만'): (1) no live process already carries the run name (same
check as R8 watch_train `alive`: command line), (2) night window (--window HH:MM-HH:MM, default 22:00-09:00, may wrap midnight):
a bundle starts only inside the window and only when its estimated wall clock (registered decisions ÷ registered speed × 1.1 —
`speed_dps` in the decisions JSON, C0-9; without it the wall cap / 2) ends before the window end, else it waits for the next window
start, (3) no Unreal Editor / UBT / ShaderCompileWorker / LiveCodingConsole / MSBuild (any project) is running — the league waits and
logs, it never stops them, (4) free commit memory ≥ 1.5 × (--proc-mem-gb × processes to start) + 6 GB (Windows GetPerformanceInfo).
Running processes ≤ --max-procs (6). A bundle already running is never stopped (a window end does not cut it). Waiting reasons go to
league_events.log, the state file (`waiting`) and logs/progress.md. The even-round check follows the same window rule unless
--check-anytime (a check is not training).

State `ckpt/r9/league_state.json` (atomic rewrite): round, stage, runs (status, pid, start copy + sha256, pool file), pools per branch
and species (zip, npz, sha256), latest zip per branch·species, prescriptions (9-4 shares per branch from a round), events. The meta
RNG is a pure function of (model seed, round, segment, species) (r9_vec_env) — nothing to save. A bundle that was cut (PC restart,
crash) is re-run from its start copy (`<out>/<branch>/start/<run>.zip`, copied once before the first launch) after its partial
snapshot files are removed (7-9 — same seed, same decisions → same result). A bundle still running when the league restarts is
adopted (waited for), not launched twice.

Bundle decisions (7-3) must be registered (STATUS.md after C0-9) — `--decisions-json` {"round0": {deer, boar, wolf}, "later": {…}}
or cfg.train.bundle_decisions. Not registered → refuse (dry-run shows '미등록'). Wall cap = train.wall_cap_factor × planned hours
(round 0: prey 3.5 h · wolf 4 h, later 0.75 h).
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env_v2 import r9_body as B  # noqa: E402
from env_v2 import r9_brains as BR  # noqa: E402

CKPT = ROOT / "ckpt" / "r9"
LOGS = HERE.parent / "logs"
TRAIN = HERE.parent / "train_r9.py"
CFG_DEFAULT = "configs/v3_r9.yaml"
PREY, WOLF_STAGE = "prey", "wolf"
STAGES = (PREY, WOLF_STAGE)
STAGE_SPECIES = {PREY: ("deer", "boar"), WOLF_STAGE: ("wolf",)}
PLANNED_H = {(0, PREY): 3.5, (0, WOLF_STAGE): 4.0, "later": 0.75}          # 7-3 표
UNREAL_NAMES = ("unrealeditor", "unrealbuildtool", "ue4editor", "shadercompileworker", "livecodingconsole", "msbuild")
WINDOW_DEFAULT = "22:00-09:00"                     # STATUS 5절 밤 창 (11-12 등록)
EST_FACTOR = 1.1                                   # 묶음 어림 벽시계 = 등록 결정 수 ÷ 등록 속도 × 1.1
GB = 1024 ** 3


def now_s() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def rel(p) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def absp(p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_name(branch: str, species: str, round_: int) -> str:
    return f"r9_{branch}_{species}_r{round_}"


# --------------------------------------------------------------------------- #
# night window (STATUS 5절, 11-12 등록) — pure functions (clock injected, tests)
# --------------------------------------------------------------------------- #

def parse_window(text: str) -> tuple[int, int]:
    """'HH:MM-HH:MM' → (start minute, end minute) of the day. start == end is refused (no window). Hours 0~23 and minutes 0~59
    are checked separately (검토 low: '22:60' used to be read as 23:00)."""
    try:
        a, b = str(text).split("-")
        sa, sb = [int(x) for x in a.split(":")], [int(x) for x in b.split(":")]
        if len(sa) != 2 or len(sb) != 2:
            raise ValueError("HH:MM")
    except (ValueError, IndexError) as e:
        raise ValueError(f"창은 HH:MM-HH:MM 꼴 (받음 {text!r})") from e
    if not all(0 <= h < 24 and 0 <= m < 60 for h, m in (sa, sb)):
        raise ValueError(f"창 {text!r}: 시는 0~23, 분은 0~59")
    st, en = sa[0] * 60 + sa[1], sb[0] * 60 + sb[1]
    if st == en:
        raise ValueError(f"창 {text!r}: 시작 ≠ 끝")
    return st, en


def window_length_s(win: tuple[int, int]) -> float:
    st, en = win
    return float(((en - st) % 1440) * 60)


def current_window(now: dt.datetime, win: tuple[int, int]) -> tuple[dt.datetime, dt.datetime] | None:
    """(start, end) datetimes of the window that contains `now`, or None (outside). Wrapping windows (22:00-09:00) work."""
    st, en = win
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    for back in (0, 1):
        s0 = day0 - dt.timedelta(days=back) + dt.timedelta(minutes=st)
        e0 = s0 + dt.timedelta(seconds=window_length_s(win))
        if s0 <= now < e0:
            return s0, e0
    return None


def next_window_start(now: dt.datetime, win: tuple[int, int]) -> dt.datetime:
    """First window start strictly after `now` (or today's start if still ahead)."""
    st, _en = win
    s0 = now.replace(hour=0, minute=0, second=0, microsecond=0) + dt.timedelta(minutes=st)
    return s0 if s0 > now else s0 + dt.timedelta(days=1)


def window_check(now: dt.datetime, win: tuple[int, int], est_s: float, grace_s: float = 1800.0) -> tuple[bool, str]:
    """May a bundle of estimated wall clock `est_s` start at `now`? Inside the window and now + est ≤ window end. A bundle longer than
    the whole window can never fit — it may start only in the first `grace_s` of a window [해석: 막히지 않게, 기록함]."""
    cw = current_window(now, win)
    nxt = next_window_start(now, win)
    if cw is None:
        return False, f"밤 창 밖 (다음 창 시작 {nxt:%m-%d %H:%M})"
    s0, e0 = cw
    if now + dt.timedelta(seconds=float(est_s)) <= e0:
        return True, ""
    if float(est_s) > window_length_s(win) and (now - s0).total_seconds() <= grace_s:
        return True, f"어림 {est_s / 3600:.1f} h 가 창 길이보다 길어 창 시작 {grace_s / 60:.0f} 분 안에만 띄운다"
    return False, f"어림 {est_s / 3600:.2f} h 로는 창 끝 {e0:%H:%M} 전에 못 끝남 (다음 창 시작 {nxt:%m-%d %H:%M})"


def launch_gate(now: dt.datetime, win: tuple[int, int] | None, est_s: float, unreal: list[str], free_bytes: int | None, n_procs: int,
                proc_mem_gb: float) -> str | None:
    """None if a bundle may start now, else the reason to wait (STATUS 5절 (1)~(4), 7-9). win None = no window (점검 --check-anytime)."""
    if win is not None:
        ok, why = window_check(now, win, est_s)
        if not ok:
            return why
    if unreal:
        return "언리얼/UBT/셰이더/라이브 코딩/MSBuild 가 돌고 있다 (끄지 않고 기다림): " + ", ".join(unreal[:4])
    need = 1.5 * float(proc_mem_gb) * int(n_procs) * GB + 6.0 * GB
    if free_bytes is not None and free_bytes < need:
        return f"남은 커밋 메모리 {free_bytes / GB:.1f} GB < 필요 {need / GB:.1f} GB"
    return None


def append_progress(log_dir: Path, line: str) -> None:
    """logs/progress.md 에 한 줄 덧붙인다 (지켜보기 watch_r9 가 다시 쓰면 그 쪽 '기다림' 칸이 상태 파일의 `waiting` 을 보여 준다)."""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "progress.md").open("a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# machine checks (7-9)
# --------------------------------------------------------------------------- #

def commit_free_bytes() -> int | None:
    """Free commit charge = CommitLimit − CommitTotal (Windows GetPerformanceInfo); None elsewhere / on failure."""
    if os.name != "nt":
        return None

    class PI(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("CommitTotal", ctypes.c_size_t), ("CommitLimit", ctypes.c_size_t),
                    ("CommitPeak", ctypes.c_size_t), ("PhysicalTotal", ctypes.c_size_t), ("PhysicalAvailable", ctypes.c_size_t),
                    ("SystemCache", ctypes.c_size_t), ("KernelTotal", ctypes.c_size_t), ("KernelPaged", ctypes.c_size_t),
                    ("KernelNonpaged", ctypes.c_size_t), ("PageSize", ctypes.c_size_t), ("HandleCount", ctypes.c_ulong),
                    ("ProcessCount", ctypes.c_ulong), ("ThreadCount", ctypes.c_ulong)]
    pi = PI()
    pi.cb = ctypes.sizeof(PI)
    try:
        ok = ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(pi), pi.cb)
    except (AttributeError, OSError):
        return None
    if not ok:
        return None
    return int(pi.CommitLimit - pi.CommitTotal) * int(pi.PageSize)


def unreal_running() -> list[str]:
    try:
        import psutil
    except ImportError:
        return []
    out = []
    for pr in psutil.process_iter(["name", "pid"]):
        n = (pr.info.get("name") or "").lower()
        if n.startswith(UNREAL_NAMES):
            out.append(f"{pr.info['name']}({pr.info['pid']})")
    return out


def live_runs(names) -> dict:
    """{run name: pid} of live processes whose command line carries `--run-name <name>` (two-copies check, R8 watch `alive`)."""
    try:
        import psutil
    except ImportError:
        return {}
    want = set(names)
    me = os.getpid()
    out = {}
    for pr in psutil.process_iter(["pid", "cmdline"]):
        try:
            cl = pr.info.get("cmdline") or []
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if pr.info["pid"] == me or "--run-name" not in cl:
            continue
        i = cl.index("--run-name")
        if i + 1 < len(cl) and cl[i + 1] in want and any("train_r9.py" in c for c in cl):
            out[cl[i + 1]] = int(pr.info["pid"])
    return out


def pid_alive(pid: int, marker: str) -> bool:
    try:
        import psutil
    except ImportError:
        return False
    try:
        pr = psutil.Process(int(pid))
        return marker in " ".join(pr.cmdline()) and pr.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


# --------------------------------------------------------------------------- #
# league
# --------------------------------------------------------------------------- #

class League:
    def __init__(self, args):
        self.args = args
        self.cfg_path = absp(args.config)
        self.cfg = B.load_r9_config(self.cfg_path)
        tr = self.cfg["train"]
        self.out = absp(args.out)
        self.logs = absp(args.log_dir)
        self.state_path = absp(args.state) if args.state else self.out / "league_state.json"
        self.branches = list(args.branches)
        self.shards = int(args.shards if args.shards is not None else tr["wolf_shards"])
        self.wall_factor = float(tr["wall_cap_factor"])
        self.window = None if getattr(args, "no_window", False) else parse_window(getattr(args, "window", WINDOW_DEFAULT))
        self.clock = dt.datetime.now                  # injected in tests
        self._unreal = unreal_running
        self._free = commit_free_bytes
        self.speeds = None
        self.decisions = self._decisions()
        self._check_c0_state()
        self.state = self._load_state()

    def _check_c0_state(self) -> None:
        """Fix 단계 검토 low: the C0 calibrated values (results/v3/r9/calib/C0_STATE.json) must already be in the YAML the
        league trains with — eval_r9.check_c0_state refuses otherwise (dry-run only prints the refusal)."""
        if str(HERE.parent) not in sys.path:
            sys.path.insert(0, str(HERE.parent))
        import eval_r9 as EV  # noqa: E402  (lazy: numpy / eval core only when the league starts)

        try:
            EV.check_c0_state(self.cfg, self.cfg, "league")      # the league trains with this one YAML only
        except SystemExit as e:
            if not self.args.dry_run:
                raise
            print(f"[dry-run] {e}", flush=True)

    # --- registry ---
    def _decisions(self) -> dict | None:
        if self.args.decisions_json:
            d = json.loads(absp(self.args.decisions_json).read_text(encoding="utf-8"))
        else:
            d = self.cfg["train"].get("bundle_decisions")
        if not d:
            return None
        for key in ("round0", "later"):
            if key not in d or any(n not in d[key] for n in B.SPECIES):
                raise ValueError(f"bundle decisions need {{round0, later}} × {{deer, wolf, boar}}: {d}")
        sp = d.get("speed_dps")                        # C0-9 등록 속도 (결정/초) — 없으면 밤 창 어림은 벽시계 상한 / 2
        if sp and all(k in sp and all(n in sp[k] for n in B.SPECIES) for k in ("round0", "later")):
            self.speeds = {k: {n: float(v) for n, v in sp[k].items()} for k in ("round0", "later")}
        return {k: {n: int(v) for n, v in d[k].items()} for k in ("round0", "later")}

    def est_seconds(self, spec: dict) -> float:
        """밤 창 판단용 묶음 어림 벽시계 (STATUS 5절): 등록 결정 수 ÷ 등록 속도 × 1.1, 속도 미등록이면 벽시계 상한 / 2."""
        if self.speeds is not None and spec.get("decisions"):
            v = self.speeds["round0" if int(spec["round"]) == 0 else "later"][spec["species"]]
            if v > 0:
                return float(spec["decisions"]) / v * EST_FACTOR
        return float(spec["wall_hours"]) * 3600.0 / 2.0

    def bundle_decisions(self, round_: int, species: str) -> int | None:
        if self.decisions is None:
            return None
        return self.decisions["round0" if round_ == 0 else "later"][species]

    def planned_hours(self, round_: int, stage: str) -> float:
        return PLANNED_H[(0, stage)] if round_ == 0 else PLANNED_H["later"]

    # --- state ---
    def _new_state(self) -> dict:
        return dict(version=1, created=now_s(), config=rel(self.cfg_path), config_digest=BR.config_digest(self.cfg),
                    io_hash=B.hash_hex(B.io_hash()), branches=self.branches, round=0, stage=PREY, halted=None,
                    meta_rng="default_rng([model_seed, round, segment, species]) — pure function, nothing saved",
                    runs={}, pools={b: {n: [] for n in B.SPECIES} for b in self.branches},
                    latest={b: {n: None for n in B.SPECIES} for b in self.branches},
                    prescriptions={b: [] for b in self.branches}, checks=[], events=[])

    def _load_state(self) -> dict:
        if self.state_path.exists():
            st = json.loads(self.state_path.read_text(encoding="utf-8"))
            if st.get("config_digest") != BR.config_digest(self.cfg) and not self.args.dry_run:
                raise ValueError(f"state {self.state_path} was made with config digest {st.get('config_digest')}, "
                                 f"now {BR.config_digest(self.cfg)} — a changed world needs a new league (state file)")
            return st
        return self._new_state()

    def save(self) -> None:
        if self.args.dry_run:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def event(self, msg: str) -> None:
        line = f"{now_s()} {msg}"
        try:
            print(line, flush=True)
        except (OSError, ValueError):                # closed / broken stdout must not stop the league
            pass
        if self.args.dry_run:
            return
        self.state["events"].append(line)
        self.state["events"] = self.state["events"][-400:]
        self.logs.mkdir(parents=True, exist_ok=True)
        with (self.logs / "league_events.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    # --- plan ---
    def shares_for(self, branch: str, round_: int) -> dict | None:
        best = None
        for p in self.state["prescriptions"].get(branch, []):
            if int(p["from_round"]) <= round_ and (best is None or int(p["from_round"]) >= int(best["from_round"])):
                best = p
        return None if best is None else {"*": best["shares"]}

    def plan_stage(self, round_: int, stage: str) -> list[dict]:
        specs = []
        for sp_name in STAGE_SPECIES[stage]:
            for br in self.branches:
                name = run_name(br, sp_name, round_)
                bdir = self.out / br
                latest = self.state["latest"][br][sp_name]
                procs = self.shards if stage == WOLF_STAGE else 1
                dec = self.bundle_decisions(round_, sp_name)
                wall = self.wall_factor * self.planned_hours(round_, stage)
                spec = dict(run=name, branch=br, species=sp_name, round=round_, stage=stage, decisions=dec, wall_hours=wall,
                            procs=procs, shards=procs, init_src=latest,
                            start_copy=rel(bdir / "start" / f"{name}.zip") if round_ > 0 else None,
                            pool_file=rel(bdir / "pools" / f"{name}.json"), shares=self.shares_for(br, round_),
                            pool_sizes={n: len(self.state["pools"][br][n]) for n in B.SPECIES})
                if round_ > 0 and not latest and not self.args.dry_run:
                    raise RuntimeError(f"{name}: round {round_} needs the previous {sp_name} bundle of branch {br}")
                spec["cmd"] = self.train_cmd(spec)
                specs.append(spec)
        return specs

    def train_cmd(self, spec: dict) -> list[str]:
        cmd = [sys.executable, "-X", "utf8", rel(TRAIN), "--config", rel(self.cfg_path), "--species", spec["species"],
               "--branch", spec["branch"], "--round", str(spec["round"]),
               "--decisions", str(spec["decisions"] if spec["decisions"] is not None else "미등록"),
               "--wall-hours", f"{spec['wall_hours']:.3f}", "--run-name", spec["run"], "--pool", spec["pool_file"],
               "--shards", str(spec["shards"]), "--out", rel(self.out), "--log-dir", rel(self.logs)]
        if spec["start_copy"]:
            cmd += ["--init", spec["start_copy"]]
        if spec["shares"]:
            cmd += ["--shares", json.dumps(spec["shares"], separators=(",", ":"))]
        if self.args.train_extra:
            cmd += self.args.train_extra.split()
        return cmd

    # --- run files ---
    def run_meta(self, spec: dict) -> dict | None:
        p = self.out / spec["branch"] / f"{spec['run']}.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def finished(self, spec: dict) -> str | None:
        """'done' | 'failed' | 'cut' (transient failure — re-run from the start copy) | None (not finished)."""
        m = self.run_meta(spec)
        if m is None:
            return None
        if m.get("stop") == "cut":
            return "cut"
        if m.get("stop") in ("target", "wall_clock") and not m.get("error"):
            ok = all(absp(s["npz"]).exists() and absp(s["zip"]).exists() for s in m.get("snapshots", []))
            return "done" if ok and m.get("snapshots") else "failed"
        return "failed"

    def clean_partial(self, spec: dict) -> None:
        bdir = self.out / spec["branch"]
        pat = re.compile(rf"^{re.escape(spec['species'])}_r{spec['round']}_\d+\.(zip|npz|json)$")
        gone = []
        for f in bdir.glob(f"{spec['species']}_r{spec['round']}_*"):
            if pat.match(f.name):
                f.unlink()
                gone.append(f.name)
        for f in (bdir / f"{spec['run']}.history.json", bdir / f"{spec['run']}.json"):
            if f.exists():
                f.unlink()
                gone.append(f.name)
        if gone:
            self.event(f"{spec['run']}: 끊긴 묶음의 조각 파일 {len(gone)} 개를 지우고 시작 사본에서 처음부터 다시")

    def prepare(self, spec: dict) -> None:
        """Start copy (once) and pool file (once) — both fixed for the bundle so a re-run sees the same inputs."""
        rs = self.state["runs"].setdefault(spec["run"], dict(status="planned", attempts=0))
        if spec["start_copy"]:
            dst = absp(spec["start_copy"])
            if not dst.exists():
                if not spec["init_src"]:
                    raise RuntimeError(f"{spec['run']}: no previous bundle zip to copy as the start copy")
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(absp(spec["init_src"]), dst)
            rs["start_copy"] = spec["start_copy"]
            rs["start_sha256"] = sha256(dst)
        pf = absp(spec["pool_file"])
        if not pf.exists():
            pf.parent.mkdir(parents=True, exist_ok=True)
            pool = {n: [e["npz"] for e in self.state["pools"][spec["branch"]][n]] for n in B.SPECIES if n != spec["species"]}
            pf.write_text(json.dumps(dict(run=spec["run"], made=now_s(), pool=pool,
                                          sha256={n: [e["sha256_npz"] for e in self.state["pools"][spec["branch"]][n]]
                                                  for n in pool}), ensure_ascii=False, indent=1), encoding="utf-8")
        rs["pool_file"] = spec["pool_file"]

    # --- launching ---
    def precheck(self, n_procs: int, est_s: float = 0.0, window: bool = True) -> str | None:
        """None if launching n_procs processes is fine now, else the reason to wait (STATUS 5절 밤 창 · 7-9)."""
        return launch_gate(self.clock(), self.window if window else None, est_s, self._unreal(), self._free(), n_procs,
                           float(self.args.proc_mem_gb))

    def note_wait(self, why: str) -> None:
        """기다리는 까닭을 이벤트·상태 파일(`waiting` — watch_r9 가 progress.md 에 보여 줌)·progress.md 에 남긴다."""
        self.event(f"기다림: {why}")
        if self.args.dry_run:
            return
        self.state["waiting"] = dict(since=self.state.get("waiting", {}).get("since") or now_s(), reason=why, at=now_s())
        self.save()
        append_progress(self.logs, f"- {now_s()} 리그 기다림: {why}")

    def launch(self, spec: dict) -> subprocess.Popen:
        self.logs.mkdir(parents=True, exist_ok=True)
        log = self.logs / f"train_{spec['run']}.log"
        env = dict(os.environ, PYTHONUTF8="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        base = 0
        if os.name == "nt":
            base = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        lf = log.open("a", encoding="utf-8")
        kw = dict(cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, close_fds=True)
        try:
            child = subprocess.Popen(spec["cmd"], creationflags=base | (subprocess.CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
            brk = 1
        except OSError:
            child = subprocess.Popen(spec["cmd"], creationflags=base, **kw)
            brk = 0
        lf.close()
        line = (f"train {spec['run']} cmd_pid {os.getpid()} python_pid {child.pid} log {rel(log)} started "
                f"{time.strftime('%Y-%m-%dT%H:%M:%S')} no_window breakaway={brk}")
        with (self.logs / "pids.txt").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        rs = self.state["runs"][spec["run"]]
        rs.update(status="running", pid=child.pid, started=now_s(), attempts=int(rs.get("attempts", 0)) + 1, procs=spec["procs"])
        self.save()
        self.event(f"띄움 {spec['run']} pid {child.pid} ({spec['procs']} 프로세스, {spec['decisions']} 결정, 상한 {spec['wall_hours']:.2f}h)")
        return child

    def run_stage(self, round_: int, stage: str) -> bool:
        specs = self.plan_stage(round_, stage)
        if any(s["decisions"] is None for s in specs):
            raise RuntimeError("묶음 결정 수가 등록되지 않았다 (C0-9 → STATUS.md, --decisions-json)")
        self.state["round"], self.state["stage"] = round_, stage
        for s in specs:
            self.prepare(s)
        self.save()
        todo = []
        for s in specs:
            f = self.finished(s)
            if f == "done":
                self.state["runs"][s["run"]]["status"] = "done"
            elif f == "failed":                 # NaN / error: a re-run would repeat it (same seed) — people decide
                self.state["runs"][s["run"]]["status"] = "failed"
                self.save()
                self.event(f"{s['run']}: 실패한 묶음(NaN·오류) — 리그를 멈춘다. 사람이 보고 끝 기록(.json)을 치우면 다시 돈다")
                return False
            elif f == "cut":                    # memory / lost shard worker: not the seed's fault — re-run (bounded)
                rs0 = self.state["runs"][s["run"]]
                if int(rs0.get("attempts", 0)) >= int(self.args.max_attempts):
                    rs0["status"] = "failed"
                    self.save()
                    self.event(f"{s['run']}: 일시 실패(cut)로 {rs0['attempts']} 번 띄워 멈춘다")
                    return False
                self.clean_partial(s)
                todo.append(s)
            else:
                todo.append(s)
        running: dict = {}                     # run → (spec, Popen | pid)
        adopted = live_runs([s["run"] for s in todo])
        for s in todo:
            if s["run"] in adopted:
                running[s["run"]] = (s, int(adopted[s["run"]]))
                self.event(f"{s['run']}: 이미 도는 프로세스 pid {adopted[s['run']]} 를 기다린다 (두 벌 막음)")
        queue = [s for s in todo if s["run"] not in running]
        for s in queue:
            if any((self.out / s["branch"]).glob(f"{s['species']}_r{round_}_*")):
                self.clean_partial(s)
        last_wait = 0.0
        while queue or running:
            # finished processes
            for name in list(running):
                s, h = running[name]
                alive = (h.poll() is None) if isinstance(h, subprocess.Popen) else pid_alive(h, name)
                if alive:
                    continue
                del running[name]
                f = self.finished(s)
                rs = self.state["runs"][name]
                rs["finished"] = now_s()
                if f == "done":
                    rs["status"] = "done"
                    m = self.run_meta(s)
                    self.event(f"끝 {name}: {m['timesteps'] / 1e6:.2f}M 결정, {m['wall_s'] / 60:.1f} 분, 멈춤 {m['stop']}")
                    if m["stop"] == "wall_clock":
                        self.event(f"{name}: 벽시계 상한에 닿음 (9-5 신호, 다음 묶음은 그대로)")
                elif f == "failed":
                    rs["status"] = "failed"
                    self.save()
                    self.event(f"{name}: 실패 (NaN·오류) — 리그를 멈춘다")
                    return False
                else:
                    # --max-attempts = 띄운 횟수 상한 (처음 포함: 3 이면 다시 2 번)
                    if int(rs.get("attempts", 0)) >= int(self.args.max_attempts):
                        rs["status"] = "failed"
                        self.save()
                        self.event(f"{name}: {rs['attempts']} 번 띄워 모두 끊겨 멈춘다")
                        return False
                    why = "일시 실패(cut: 메모리·조각 작업 프로세스)" if f == "cut" else "끝 기록 없이 끝남"
                    self.event(f"{name}: {why} — 시작 사본에서 다시")
                    self.clean_partial(s)
                    queue.append(s)
                self.save()
            # launch while room
            while queue:
                busy = sum(running[n][0]["procs"] for n in running)
                s = queue[0]
                if busy + s["procs"] > int(self.args.max_procs) and running:
                    break
                dup = live_runs([s["run"]])
                if dup:
                    running[s["run"]] = (s, int(dup[s["run"]]))
                    queue.pop(0)
                    self.event(f"{s['run']}: 이미 도는 프로세스 pid {dup[s['run']]} 를 기다린다 (두 벌 막음)")
                    continue
                why = self.precheck(s["procs"], self.est_seconds(s))
                if why:
                    if time.time() - last_wait > 600.0:
                        self.note_wait(f"{s['run']} — {why}")
                        last_wait = time.time()
                    break
                if self.state.get("waiting"):
                    self.state["waiting"] = None
                running[s["run"]] = (s, self.launch(queue.pop(0)))
            if queue or running:
                time.sleep(float(self.args.poll))
        return True

    def add_to_pools(self, round_: int, stage: str) -> None:
        for s in self.plan_stage(round_, stage):
            m = self.run_meta(s)
            pool = self.state["pools"][s["branch"]][s["species"]]
            have = {e["npz"] for e in pool}
            for snap in sorted(m["snapshots"], key=lambda e: e["decisions"]):
                if snap["npz"] in have:
                    continue
                pool.append(dict(v=len(pool), round=round_, decisions=snap["decisions"], zip=snap["zip"], npz=snap["npz"],
                                 sha256_zip=snap["sha256_zip"], sha256_npz=snap["sha256_npz"], run=s["run"]))
            self.state["latest"][s["branch"]][s["species"]] = pool[-1]["zip"]
            self.event(f"풀 {s['branch']}·{s['species']}: 판 {len(pool)} 개 (이번 묶음 {len(m['snapshots'])} 개)")
        self.save()

    def run_check(self, round_: int) -> None:
        if not self.args.check_cmd:
            self.state["checks"].append(dict(round=round_, status="skipped", at=now_s(),
                                             note="eval_r9.py check 준비 전 — --check-cmd 로 켠다 (8-5)"))
            self.event(f"{round_} 바퀴 점검 건너뜀 (--check-cmd 없음)")
            self.save()
            return
        per_branch = "{branch}" in self.args.check_cmd            # without {branch}: one call for both branches (9-4 needs both)
        brs = self.branches if per_branch else ["+".join(self.branches)]
        # Fix 단계 (C0-9): the per-branch checks run AT THE SAME TIME (7-9 '점검은 학습이 쉬는 동안 따로, 프로세스 4 개') — one after
        # the other they took ~2 × the C0-9 check time. --check-procs counts the processes of all branches together.
        est = float(self.args.check_est_hours) * 3600.0 * EST_FACTOR
        why = self.precheck(int(self.args.check_procs), est, window=not self.args.check_anytime)
        last_wait = 0.0
        while why:
            if time.time() - last_wait > 600.0:
                self.note_wait(f"점검 {round_} 바퀴 — {why}")
                last_wait = time.time()
            time.sleep(max(60.0, float(self.args.poll)))
            why = self.precheck(int(self.args.check_procs), est, window=not self.args.check_anytime)
        if self.state.get("waiting"):
            self.state["waiting"] = None
        env = dict(os.environ, PYTHONUTF8="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        kids = []
        for br in brs:
            cmd = self.args.check_cmd.format(round=round_, branch=br, state=str(self.state_path), out=str(self.out))
            self.event(f"점검 {round_} 바퀴 {br}: {cmd}")
            log = self.logs / f"check_r{round_}_{br}.log"
            lf = log.open("a", encoding="utf-8")
            kids.append((br, log, lf, subprocess.Popen([sys.executable, "-X", "utf8"] + cmd.split(), cwd=str(ROOT), env=env,
                                                       stdout=lf, stderr=subprocess.STDOUT, creationflags=flags)))
        for br, log, lf, ch in kids:
            rc = ch.wait()
            lf.close()
            self.state["checks"].append(dict(round=round_, branch=br, status="ok" if rc == 0 else f"rc={rc}", at=now_s(), log=rel(log)))
            self.save()

    # --- main loop ---
    def dry_run(self) -> int:
        r0 = int(self.state["round"])
        n = int(self.args.plan_rounds)
        from env_v2.r9_vec_env import opponent_shares          # lazy: pulls SB3/torch, only the dry-run needs it

        print(f"# R9 리그 차례 (dry-run — 띄우지 않고 상태 파일도 쓰지 않음) {now_s()}")
        print(f"설정 {rel(self.cfg_path)} (digest {BR.config_digest(self.cfg)}), 상태 {rel(self.state_path)}"
              f"{' (있음)' if self.state_path.exists() else ' (없음 — 새로 시작)'}, 갈래 {self.branches}, 늑대 조각 {self.shards}, "
              f"동시 프로세스 상한 {self.args.max_procs}, 프로세스당 메모리 어림 {self.args.proc_mem_gb} GB")
        if self.decisions is None:
            print("묶음 결정 수: 미등록 (C0-9 뒤 STATUS.md·--decisions-json 에 등록해야 띄운다)")
        free = commit_free_bytes()
        print(f"지금 확인: 언리얼/UBT/MSBuild {unreal_running() or '없음'}, 남은 커밋 메모리 "
              f"{'모름' if free is None else f'{free / GB:.1f} GB'}")
        if self.window is None:
            print("밤 창: 없음 (--no-window — 시험·스모크만)")
        else:
            cw = current_window(self.clock(), self.window)
            print(f"밤 창 {self.args.window} (길이 {window_length_s(self.window) / 3600:.1f} h): 지금 {'창 안 — 끝 ' + f'{cw[1]:%H:%M}' if cw else '창 밖'}, "
                  f"다음 창 시작 {next_window_start(self.clock(), self.window):%m-%d %H:%M}. 속도 "
                  f"{'등록 (speed_dps)' if self.speeds else '미등록 → 어림 = 벽시계 상한 / 2'}")
        tr = self.cfg["train"]
        for r in range(r0, r0 + n):
            print(f"\n## {r} 바퀴")
            for i, stage in enumerate(STAGES, 1):
                specs = self.plan_stage(r, stage)
                procs = sum(s["procs"] for s in specs)
                waves = []
                cur, busy = [], 0
                for s in specs:
                    if cur and busy + s["procs"] > int(self.args.max_procs):
                        waves.append(cur)
                        cur, busy = [], 0
                    cur.append(s["run"])
                    busy += s["procs"]
                waves.append(cur)
                print(f"{i}. {'먹이' if stage == PREY else '늑대'} 묶음 — 프로세스 {procs} 개, 띄우는 무리 {waves}")
                for s in specs:
                    learner = B.SPECIES_INDEX[s["species"]]
                    opp = []
                    for o in range(3):
                        if o == learner:
                            continue
                        sh = opponent_shares(self.cfg, r, learner, o, s["shares"])
                        opp.append(f"{B.SPECIES[o]} {sh} (풀 {s['pool_sizes'][B.SPECIES[o]]} 판)")
                    print(f"   - {s['run']}: 세계 {tr['worlds'][s['species']]}, 결정 {s['decisions'] or '미등록'}, "
                          f"상한 {s['wall_hours']:.2f}h, 조각 {s['shards']}, "
                          f"시작 {(s['start_copy'] + ' ← ' + (s['init_src'] or '앞 바퀴 끝 판(아직 없음)')) if s['start_copy'] else '새로(처음부터)'}, "
                          f"lr {tr['ppo']['learning_rate_round0'] if r == 0 else tr['ppo']['learning_rate']}"
                          f"{', 첫 롤아웃 가치망만' if r > 0 else ''}")
                    print(f"     상대: {'; '.join(opp)}; 방식 확률 {tr['opponent_stochastic']}")
                    print(f"     밤 창 어림 {self.est_seconds(s) / 3600:.2f} h → 지금 띄우면: "
                          f"{self.precheck(s['procs'], self.est_seconds(s)) or '띄움'}")
                    print(f"     명령: {' '.join(s['cmd'][1:])}")
                print("   띄우기 전 확인: 두 벌(실행 이름) · 밤 창(어림이 창 끝 전에 끝남) · 언리얼/UBT/셰이더/라이브 코딩/MSBuild · "
                      "커밋 메모리 ≥ 1.5 × 어림 × 프로세스 + 6 GB")
                print(f"   끝나면: 판(zip·npz) sha256 → 풀 {self.branches} 각 {STAGE_SPECIES[stage]} 에 차례로 추가, 다음 묶음 시작 사본")
            print(f"3. 점검: {'짝수 바퀴 — ' + (self.args.check_cmd or 'eval_r9.py check (--check-cmd 없으면 건너뜀)') if r % 2 == 0 else '없음(홀수 바퀴)'}")
        print(f"\n멈춤: --rounds {self.args.rounds} 바퀴 끝에 멈추고 멈춤 규칙(9-4)을 본다 (최대 {self.args.max_rounds})")
        return 0

    def run(self) -> int:
        if self.args.dry_run:
            return self.dry_run()
        if self.decisions is None:
            print("묶음 결정 수가 등록되지 않았다 (C0-9 뒤 --decisions-json). 띄우지 않는다.", flush=True)
            return 2
        last = min(int(self.args.rounds), int(self.args.max_rounds))
        self.state["halted"] = None
        self.save()
        self.event(f"리그 시작: {self.state['round']} 바퀴 {self.state['stage']} 묶음부터 {last} 바퀴까지 (pid {os.getpid()})")
        while int(self.state["round"]) <= last:
            r = int(self.state["round"])
            stage0 = self.state["stage"]
            start = STAGES.index(stage0) if stage0 in STAGES else len(STAGES)      # 'check' = both bundles done
            for stage in STAGES[start:]:
                ok = self.run_stage(r, stage)
                if not ok:
                    self.state["halted"] = f"failed at round {r} {stage}"
                    self.save()
                    return 1
                self.add_to_pools(r, stage)
            if r % 2 == 0:
                self.state["stage"] = "check"
                self.save()
                self.run_check(r)
            self.state["round"], self.state["stage"] = r + 1, PREY
            self.save()
            self.event(f"{r} 바퀴 끝")
        self.state["halted"] = f"rounds_done ({last})"
        self.save()
        self.event(f"{last} 바퀴까지 끝 — 멈춤 규칙(9-4) 점검 뒤 --rounds 를 늘려 이어 간다")
        return 0


def acquire_lock(path: Path) -> bool:
    try:
        import psutil
    except ImportError:
        psutil = None
    if path.exists():
        try:
            pid = int(path.read_text(encoding="utf-8").split()[0])
        except (ValueError, IndexError):
            pid = None
        if pid and psutil is not None and pid_alive(pid, "league_r9.py") and pid != os.getpid():
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{os.getpid()} {now_s()}\n", encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=CFG_DEFAULT)
    ap.add_argument("--state", default=None, help="상태 파일 (기본 <out>/league_state.json)")
    ap.add_argument("--out", default=str(CKPT))
    ap.add_argument("--log-dir", default=str(LOGS))
    ap.add_argument("--branches", nargs="+", default=["A", "B"])
    ap.add_argument("--rounds", type=int, default=10, help="이 바퀴까지 하고 멈춘다 (7-8: 10 바퀴 끝 첫 점검)")
    ap.add_argument("--max-rounds", type=int, default=18)
    ap.add_argument("--decisions-json", default=None, help="C0-9 로 등록한 묶음 결정 수 {round0: {…}, later: {…}}")
    ap.add_argument("--shards", type=int, default=None, help="늑대 묶음 조각 수 (기본 train.wolf_shards)")
    ap.add_argument("--max-procs", type=int, default=6, help="동시 프로세스 상한 (7-9, STATUS 등록)")
    ap.add_argument("--proc-mem-gb", type=float, default=0.5,
                    help="프로세스 최대 메모리 (C0-9 실측 최대 작업 집합 0.44 GB → 0.5, STATUS 3절 등록)")
    ap.add_argument("--max-attempts", type=int, default=3, help="묶음 하나를 띄우는 횟수 상한 (처음 포함 — 3 이면 다시 2 번)")
    ap.add_argument("--poll", type=float, default=15.0)
    ap.add_argument("--check-cmd", default=None, help="짝수 바퀴 점검 명령 (python 인자; {round} {branch} {state} {out}). 예: "
                    "'results/v3/r9/eval_r9.py check --round {round} --league-state {state}' ({branch} 가 없으면 한 번만)")
    ap.add_argument("--check-procs", type=int, default=4)
    ap.add_argument("--check-anytime", action="store_true", help="점검은 학습이 아니라 밤 창 밖에서도 띄운다 (언리얼·메모리 조건은 그대로)")
    ap.add_argument("--check-est-hours", type=float, default=2.4, help="점검 하나의 어림 벽시계 (STATUS 3-0: 50 세계 1.2~2.4 시간)")
    ap.add_argument("--window", default=WINDOW_DEFAULT, help="밤 창 HH:MM-HH:MM (STATUS 5절, 자정 넘김 됨). 묶음은 이 안에서만 시작")
    ap.add_argument("--no-window", action="store_true", help="[시험·스모크 전용] 밤 창을 보지 않는다 — 실제 학습에는 쓰지 않는다")
    ap.add_argument("--train-extra", default=None, help="train_r9.py 에 덧붙일 인자 (스모크용)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--plan-rounds", type=int, default=1, help="dry-run 이 그릴 바퀴 수")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    lg = League(args)
    if args.dry_run:
        return lg.run()
    lock = lg.state_path.with_suffix(".lock")
    if not acquire_lock(lock):
        print(f"다른 리그가 같은 상태 파일로 돈다 ({lock}) — 두 벌 띄우지 않는다", flush=True)
        return 3
    try:
        return lg.run()
    finally:
        try:
            if lock.exists() and lock.read_text(encoding="utf-8").split()[0] == str(os.getpid()):
                lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())

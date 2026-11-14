"""R9 밤 실행기 — C0-10 짧은 학습 → 잼 → γ 고르기 → C0_STATE → (통과) 리그, (떨어짐) 멈추고 적기 (설계 AdaptiveEcosystem/Docs/RL_Policy/
RL_R9_MULTISPECIES_DESIGN.md 9-1 C0-10, STATUS.md 2-1·5절 밤 창).

    python results/v3/r9/run_night.py --dry-run                                  # 계획만 찍는다 (띄우지 않고 상태 파일도 쓰지 않음)
    python -X utf8 results/v3/r9/spawn_detached.py --append --log results/v3/r9/logs/night.log --what "night r9" -- \\
        results/v3/r9/run_night.py --decisions-json results/v3/r9/bundle_decisions.json
    (또는 launch_league.ps1 -Night …)

차례 (상태 파일 ckpt/r9/night_state.json 에 단계마다 적는다 — 끊겨도 다시 띄우면 이어 간다):
  1 train   C0-10 짧은 학습 6 묶음 (eval_r9.c010_plan): 먹이 넷(γ 0.997·0.99 × 사슴 20M·멧돼지 10M, 프로세스 4)을 함께 → 늑대 둘(10M, 조각 3,
            프로세스 6)을 함께. 단계마다 시작 조건(league_r9.launch_gate): 밤 창 안이고 지금 + 어림(결정 ÷ 등록 속도 × 1.1, 속도 미등록이면
            11-11 값 ÷ 2.3 [어림])이 창 끝 전, 언리얼·UBT·셰이더·라이브 코딩·MSBuild 가 없음(끄지 않고 기다림), 남은 커밋 메모리 ≥ 1.5 ×
            (프로세스 메모리 × 띄울 수) + 6 GB. 이미 돌던 묶음은 창이 끝나도 끊지 않는다. 같은 이름이 이미 돌면 기다린다(두 벌 막음).
            끝 기록 없이 끝났거나 stop=cut 이면 조각 파일을 지우고 다시(띄움 최대 --max-attempts), NaN·오류면 멈춘다.
  2 eval    γ 마다 `eval_r9.py calibrate --gates C0-10 --gamma γ --brain -:deer=… -:boar=… -:wolf=…` (확인 시드 44050~44099 — 학습이 아니라
            창과 무관, 언리얼·메모리 조건만) → calib/C0-10_g<γ><tag>.json
  3 choose  eval_r9.c010_choose (9-1 등록 규칙 + 11-12 등록 조건) → calib/C0-10_choice<tag>.json, C0_STATE.json 에 γ (values.C0-10)·F 기록
            - pass: γ 와 F 를 configs/v3_r9.yaml 에 옮겨 적는다(--no-write-config 면 다를 때 멈춤 — 리그는 C0_STATE 와 YAML 이 다르면 거부)
            - enable_F_and_rerun_both: 대비책 F(사용자 승인 11-10, 한 번)를 걸고 1 부터 다시(갈래 이름 _F). F 를 이미 C0-11 에서 걸었거나 이미 F
              판이면 멈춤
            - wolf_round0_first10M_always_eat_100 (늑대만 못 넘음): 등록 처방은 '0 바퀴 늑대 묶음 첫 10M 은 늘 먹기 먹이 100%' 인데 리그가 묶음을 둘로
              나누는 기능이 아직 없다 → 멈추고 calib/C0-10_FAIL.md 에 적는다 [남은 일]
            - ask_user (음성 대조 늑대가 기준 통과 = 등록 조건 깨짐): 멈춤
  4 league  league_r9.py 를 spawn_detached 로 띄운다(--rounds 10, 등록 결정 수, --check-cmd, 같은 --window) + watch_r9.py. 리그가 묶음마다 다시
            밤 창·언리얼·메모리를 본다.
떨어지거나 멈추면 logs/progress.md·logs/night_events.log·calib/C0-10_FAIL.md 에 까닭을 적는다. 이 실행기는 학습을 밤 창 밖에서 띄우지 않는다.

띄우기 전 조건 (학습·잼·고르기 단계): 보정 관문 확인(calibrate --phase confirm 이 confirmed), C0_STATE 값이 --config/--judge-config 에 옮겨져 있음
(C0-10 γ 자신과 F 판의 F 는 빼고 — 배운 세계 = 잰 세계, 잼도 같은 검사), S′ C0-9 등록(speed_dps, --no-league 면 보지 않음).
멈춤 셋 (S′ 검토): precondition = 단계를 바꾸지 않음(조건을 맞추고 다시 띄우면 그 단계부터) · transient(잼 rc ≠ 0, 리그 띄움 실패) = 다시 띄우면 멈춘
단계부터 · needs_user(NaN·오류, 끊김 반복, 고르기 멈춤, 옮겨 적기 필요) = 다시 띄워도 멈춰 있고 `--resume-from {train,eval,choose,league}` 로 이어 간다.
학습·잼·리그 모두 --config 파일을 읽는다(옮겨 적는 파일과 같음).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/
for _p in (ROOT, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import eval_r9 as EV  # noqa: E402
import league_r9 as LG  # noqa: E402
from env_v2 import r9_body as B  # noqa: E402

CKPT = ROOT / "ckpt" / "r9"
LOGS = HERE.parent / "logs"
CALIB = HERE.parent / "calib"
GAMMAS = (0.997, 0.99)
CHECK_CMD = ("results/v3/r9/eval_r9.py check --round {round} --branches {branch} --league-state {state} "
             "--preview-seeds 44200 44249")
PHASES = ("train", "eval", "choose", "league", "done", "stopped")
STOP_KINDS = ("precondition", "transient", "needs_user")


def now_s() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def rel(p) -> str:
    return LG.rel(p)


def absp(p) -> Path:
    return LG.absp(p)


# --------------------------------------------------------------------------- #
# pure helpers (tests)
# --------------------------------------------------------------------------- #

def gamma_tag(g: float) -> str:
    return str(g)


def after_choice(choice: dict, state: dict, c0_state: dict) -> tuple[str, str]:
    """(다음 단계, 까닭). choice = eval_r9.c010_choose 결과. state = 밤 상태(attempt 'base'|'F'), c0_state = calib/C0_STATE.json."""
    act = choice.get("action")
    if act == "pass":
        return "league", f"γ {choice['gamma']} 통과 — 등록 결정 수로 리그"
    if act == "enable_F_and_rerun_both":
        if state.get("attempt") == "F":
            return "stopped", "대비책 F 를 걸고 다시 배워도 먹이 종 기준을 못 넘음 — 띄우지 않는다 (9-1)"
        if c0_state.get("f_enabled"):
            return "stopped", "먹이 종 기준을 두 γ 모두 못 넘음 — 대비책 F 는 이미 C0-11 에서 걸었다(한 번만, 사용자 승인 11-10) → 멈추고 묻는다"
        return "train", "먹이 종 기준을 두 γ 모두 못 넘음 → 대비책 F 를 한 번 걸고 C0-10 을 다시 (사용자 승인 11-10)"
    if act == "wolf_round0_first10M_always_eat_100":
        return "stopped", (f"늑대만 못 넘음 (먹이 γ {choice.get('gamma')}) — 등록 처방 '0 바퀴 늑대 묶음 첫 10M 은 늘 먹기 먹이 100%' 를 리그가 아직 "
                           "나눠 돌리지 못한다 → 멈추고 묻는다 [남은 일]")
    return "stopped", f"고르기 결과 {act}: {choice.get('why', '')} → 멈추고 묻는다"


def set_yaml_values(text: str, gamma: float | None = None, fallback_f: bool | None = None) -> str:
    """configs/v3_r9.yaml 글에서 train.ppo `gamma:` 와 reward.fallback_f `enabled:` 줄만 바꾼다 (주석·나머지 그대로). 줄을 못 찾으면 ValueError."""
    lines = text.split("\n")
    if gamma is not None:
        idx = [i for i, ln in enumerate(lines) if re.match(r"^\s+gamma:\s*[0-9.eE+-]+", ln)]
        if len(idx) != 1:
            raise ValueError(f"gamma 줄이 하나가 아니다 ({len(idx)})")
        i = idx[0]
        lines[i] = re.sub(r"^(\s+gamma:\s*)[0-9.eE+-]+", lambda m: m.group(1) + repr(float(gamma)), lines[i])
    if fallback_f is not None:
        fi = [i for i, ln in enumerate(lines) if re.match(r"^\s+fallback_f:\s*(#.*)?$", ln)]
        if len(fi) != 1:
            raise ValueError(f"fallback_f 줄이 하나가 아니다 ({len(fi)})")
        for j in range(fi[0] + 1, min(fi[0] + 4, len(lines))):
            if re.match(r"^\s+enabled:\s*(true|false)", lines[j]):
                lines[j] = re.sub(r"(enabled:\s*)(true|false)", lambda m: m.group(1) + ("true" if fallback_f else "false"), lines[j])
                break
        else:
            raise ValueError("fallback_f 아래 enabled 줄을 못 찾음")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# runner
# --------------------------------------------------------------------------- #

class Night:
    def __init__(self, args):
        self.args = args
        self.cfg_path = absp(args.config)
        self.jcfg_path = absp(args.judge_config)
        self.out = absp(args.c010_out)
        self.logs = absp(args.log_dir)
        self.calib = absp(args.calib_dir)
        self.state_path = absp(args.state) if args.state else CKPT / "night_state.json"
        self.window = LG.parse_window(args.window)
        self.clock = dt.datetime.now
        self._unreal = LG.unreal_running
        self._free = LG.commit_free_bytes
        self.speeds, self.speeds_from = EV.registered_speeds(args.decisions_json)
        self.state = self._load()

    # --- state ---
    def _load(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return dict(version=1, created=now_s(), phase="train", attempt="base", runs={}, evals={}, choice=None, note=None, events=[],
                    league=None)

    def save(self) -> None:
        if self.args.dry_run:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def event(self, msg: str, progress: bool = False) -> None:
        line = f"{now_s()} {msg}"
        try:
            print(line, flush=True)
        except (OSError, ValueError):
            pass
        if self.args.dry_run:
            return
        self.state["events"] = (self.state.get("events") or [])[-300:] + [line]
        self.logs.mkdir(parents=True, exist_ok=True)
        with (self.logs / "night_events.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        if progress:
            LG.append_progress(self.logs, f"- {line} (밤 실행기)")
        self.save()

    # --- plan ---
    def plan(self) -> list[dict]:
        return EV.c010_plan(GAMMAS, self.speeds, self.state.get("attempt") == "F", out=rel(self.out), log_dir=rel(self.logs),
                            config=rel(self.cfg_path))

    def meta(self, spec: dict) -> dict | None:
        p = self.out / spec["branch"] / f"{spec['run']}.json"
        try:
            return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
        except json.JSONDecodeError:
            return None

    def finished(self, spec: dict) -> str | None:
        m = self.meta(spec)
        if m is None:
            return None
        if m.get("stop") == "cut":
            return "cut"
        if m.get("stop") in ("target", "wall_clock") and not m.get("error") and m.get("snapshots"):
            ok = all(absp(s["npz"]).exists() for s in m["snapshots"])
            return "done" if ok else "failed"
        return "failed"

    def clean_partial(self, spec: dict) -> None:
        bdir = self.out / spec["branch"]
        pat = re.compile(rf"^{re.escape(spec['species'])}_r0_\d+\.(zip|npz|json)$")
        gone = [f for f in bdir.glob(f"{spec['species']}_r0_*") if pat.match(f.name)]
        gone += [f for f in (bdir / f"{spec['run']}.history.json", bdir / f"{spec['run']}.json") if f.exists()]
        for f in gone:
            f.unlink()
        if gone:
            self.event(f"{spec['run']}: 끊긴 묶음 조각 파일 {len(gone)} 개를 지우고 처음부터 다시")

    def gate(self, n_procs: int, est_s: float, window: bool = True) -> str | None:
        return LG.launch_gate(self.clock(), self.window if window else None, est_s, self._unreal(), self._free(), n_procs,
                              float(self.args.proc_mem_gb))

    def wait_gate(self, what: str, n_procs: int, est_s: float, window: bool = True) -> None:
        last = 0.0
        while True:
            why = self.gate(n_procs, est_s, window)
            if why is None:
                if self.state.get("note", "") and str(self.state["note"]).startswith("기다림"):
                    self.state["note"] = None
                return
            if time.time() - last > 600.0:
                self.state["note"] = f"기다림 ({what}): {why}"
                self.event(f"기다림 ({what}): {why}", progress=True)
                last = time.time()
            time.sleep(float(self.args.poll))

    def _popen(self, args: list[str], log: Path) -> subprocess.Popen:
        env = dict(os.environ, PYTHONUTF8="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1",
                   PYTHONDONTWRITEBYTECODE="1")
        flags = (subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP) if os.name == "nt" else 0
        log.parent.mkdir(parents=True, exist_ok=True)
        lf = log.open("a", encoding="utf-8")
        try:
            return subprocess.Popen([sys.executable, "-X", "utf8", *args], cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=lf,
                                    stderr=subprocess.STDOUT, creationflags=flags, close_fds=True)
        finally:
            lf.close()

    # --- 1 train ---
    def train(self) -> bool:
        plan = self.plan()
        for stage in ("prey", "wolf"):
            specs = [p for p in plan if p["stage"] == stage]
            while True:
                todo = []
                for s in specs:
                    f = self.finished(s)
                    rs = self.state["runs"].setdefault(s["run"], dict(status="planned", attempts=0))
                    if f == "done":
                        if rs.get("status") != "done":
                            m = self.meta(s)
                            rs.update(status="done", finished=now_s(), stop=m.get("stop"))
                            if m.get("stop") == "wall_clock":
                                self.event(f"{s['run']}: 벽시계 상한에 닿아 {m.get('timesteps', 0) / 1e6:.1f}M 결정에서 끝 (9-5 신호, 그대로 잰다)",
                                           progress=True)
                        continue
                    if f == "failed":
                        rs["status"] = "failed"
                        self.stop(f"C0-10 학습 {s['run']} 실패(NaN·오류) — 사람이 본다 (끝 기록 {rel(self.out / s['branch'] / (s['run'] + '.json'))})")
                        return False
                    todo.append(s)
                if not todo:
                    break
                live = LG.live_runs([s["run"] for s in todo])
                launch = []
                for s in todo:
                    rs = self.state["runs"][s["run"]]
                    if s["run"] in live:
                        rs.update(status="running", pid=int(live[s["run"]]))
                        continue
                    if self.finished(s) == "cut" or rs.get("status") == "running":
                        if int(rs.get("attempts", 0)) >= int(self.args.max_attempts):
                            self.stop(f"C0-10 학습 {s['run']}: {rs.get('attempts')} 번 띄워 모두 끊김 — 멈춘다 (고친 뒤 --resume-from train 이면 "
                                      "띄움 수를 0 부터 다시 센다)")
                            return False
                    self.clean_partial(s)
                    launch.append(s)
                if launch:
                    est = max(x["est_s"] for x in launch)
                    procs = sum(x["procs"] for x in launch)              # 메모리 조건은 새로 띄울 프로세스 수로 (리그와 같음)
                    self.wait_gate(f"C0-10 {stage} {len(launch)} 묶음", procs, est)
                    for s in launch:
                        rs = self.state["runs"][s["run"]]
                        ch = self._popen(s["args"], self.logs / f"train_{s['run']}.log")
                        rs.update(status="running", pid=ch.pid, started=now_s(), attempts=int(rs.get("attempts", 0)) + 1)
                        self.event(f"띄움 C0-10 {s['run']} pid {ch.pid} ({s['decisions'] / 1e6:.0f}M 결정, 어림 {s['est_s'] / 3600:.2f} h, "
                                   f"상한 {s['wall_hours']} h)", progress=True)
                self.state["note"] = f"C0-10 {stage} 학습 중"
                self.save()
                while any(LG.pid_alive(int(self.state["runs"][s["run"]].get("pid", 0)), s["run"]) for s in todo):
                    time.sleep(float(self.args.poll))
        return True

    # --- 2 eval ---
    def brain_paths(self, g: float) -> dict[str, str]:
        out = {}
        for s in self.plan():
            if abs(s["gamma"] - g) > 1e-12:
                continue
            m = self.meta(s) or {}
            snaps = sorted(m.get("snapshots", []), key=lambda e: e["decisions"])
            if snaps:
                out[f"-:{s['species']}"] = snaps[-1]["npz"]
        return out

    def eval_file(self, g: float) -> Path:
        return self.calib / f"C0-10_g{gamma_tag(g)}{'_F' if self.state.get('attempt') == 'F' else ''}.json"

    def evaluate(self) -> bool:
        kids = []
        todo = [g for g in GAMMAS if not self.eval_file(g).exists()]
        if todo:
            self.wait_gate("C0-10 잼", len(todo), 0.0, window=False)
        for g in todo:
            br = self.brain_paths(g)
            if len(br) != 3:
                self.stop(f"C0-10 잼: γ {g} 두뇌가 다 있지 않다 ({sorted(br)})")
                return False
            args = ["results/v3/r9/eval_r9.py", "calibrate", "--gates", "C0-10", "--gamma", gamma_tag(g), "--out", rel(self.calib),
                    "--config", rel(self.cfg_path), "--judge-config", rel(self.jcfg_path), "--state", rel(self.c0_state_path()),
                    "--tag", "_F" if self.state.get("attempt") == "F" else "", "--brain", *[f"{k}={v}" for k, v in sorted(br.items())]]
            if self.state.get("attempt") == "F":
                args += ["--set", "reward.fallback_f.enabled=true"]
            ch = self._popen(args, self.logs / f"c010_eval_g{gamma_tag(g)}.log")
            self.event(f"C0-10 잼 γ {g} pid {ch.pid}", progress=True)
            kids.append((g, ch))
        for g, ch in kids:
            rc = ch.wait()
            if rc != 0 or not self.eval_file(g).exists():
                self.stop(f"C0-10 잼 γ {g} 실패 (rc {rc}) — logs/c010_eval_g{gamma_tag(g)}.log (다시 띄우면 잼부터 다시)", kind="transient")
                return False
            self.state["evals"][gamma_tag(g)] = rel(self.eval_file(g))
        self.save()
        return True

    # --- 3 choose ---
    def c0_state_path(self) -> Path:
        return self.calib / "C0_STATE.json"

    def choose(self) -> str:
        res = {}
        for g in GAMMAS:
            d = json.loads(self.eval_file(g).read_text(encoding="utf-8"))
            res[str(d["gamma"])] = d["result"]
        ch = EV.c010_choose(res)
        tag = "_F" if self.state.get("attempt") == "F" else ""
        EV._write(self.calib, f"C0-10_choice{tag}", dict(inputs=[rel(self.eval_file(g)) for g in GAMMAS], choice=ch, attempt=self.state.get("attempt")))
        self.state["choice"] = ch
        sp = self.c0_state_path()
        c0 = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else dict(values={}, fixed={}, f_enabled=False, history=[])
        nxt, why = after_choice(ch, self.state, c0)
        self.event(f"C0-10 고르기: {json.dumps(ch, ensure_ascii=False)} → {why}", progress=True)
        if nxt == "train":                                   # F 를 걸고 다시
            c0["f_enabled"] = True
            c0.setdefault("fixed", {})["C0-10"] = True
            c0.setdefault("history", []).append(dict(phase="C0-10", time=now_s(), status="enable_F", choice=ch))
            self._write_c0(c0)
            self.state["attempt"] = "F"
            self.state["evals"] = {}
            return "train"
        if nxt == "league":
            c0.setdefault("values", {})["C0-10"] = float(ch["gamma"])
            c0.setdefault("history", []).append(dict(phase="C0-10", time=now_s(), status="pass", choice=ch,
                                                     f_enabled=bool(c0.get("f_enabled"))))
            self._write_c0(c0)
            if not self.sync_config(float(ch["gamma"]), bool(c0.get("f_enabled"))):
                return "stopped"
            return "league"
        c0.setdefault("history", []).append(dict(phase="C0-10", time=now_s(), status="stopped", choice=ch, why=why))
        self._write_c0(c0)
        self.stop(why)
        return "stopped"

    def _write_c0(self, c0: dict) -> None:
        if self.args.dry_run:
            return
        p = self.c0_state_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(c0, ensure_ascii=False, indent=1), encoding="utf-8")

    def sync_config(self, gamma: float, f_on: bool) -> bool:
        cfg = B.load_r9_config(self.cfg_path)
        same = abs(float(cfg["train"]["ppo"]["gamma"]) - gamma) < 1e-12 and bool(cfg["reward"]["fallback_f"]["enabled"]) == f_on
        if same:
            return True
        if not self.args.write_config:
            self.stop(f"고른 γ {gamma}·F {f_on} 가 {rel(self.cfg_path)} 와 다르다 — 옮겨 적은 뒤 `--resume-from league` 로 다시 띄운다 "
                      "(--no-write-config)")
            return False
        txt = self.cfg_path.read_text(encoding="utf-8")
        new = set_yaml_values(txt, gamma=gamma, fallback_f=f_on)
        self.cfg_path.write_text(new, encoding="utf-8")
        chk = B.load_r9_config(self.cfg_path)
        if abs(float(chk["train"]["ppo"]["gamma"]) - gamma) > 1e-12 or bool(chk["reward"]["fallback_f"]["enabled"]) != f_on:
            self.cfg_path.write_text(txt, encoding="utf-8")
            self.stop("설정 옮겨 적기 확인 실패 — 되돌리고 멈춘다")
            return False
        self.event(f"{rel(self.cfg_path)}: train.ppo.gamma = {gamma}, reward.fallback_f.enabled = {f_on} 로 옮겨 적음 (C0_STATE 와 같게)", progress=True)
        return True

    # --- 4 league ---
    def league_args(self) -> list[str]:
        a = self.args
        la = ["results/v3/r9/league_r9.py", "--config", rel(self.cfg_path), "--rounds", str(a.rounds), "--max-procs", str(a.max_procs),
              "--proc-mem-gb", str(a.proc_mem_gb), "--window", a.window, "--check-cmd", a.check_cmd]
        if a.decisions_json:
            la += ["--decisions-json", a.decisions_json]
        if a.check_anytime:
            la.append("--check-anytime")
        return la

    def launch_league(self) -> bool:
        spawn = ["results/v3/r9/spawn_detached.py", "--append", "--log", "results/v3/r9/logs/league.log", "--what", "league r9", "--"]
        p = self._popen(spawn + self.league_args(), self.logs / "night_spawn.log")
        rc = p.wait()
        self.event(f"리그 띄움 (spawn_detached rc {rc}): {' '.join(self.league_args())}", progress=True)
        if not self.args.no_watch:
            w = self._popen(["results/v3/r9/spawn_detached.py", "--append", "--log", "results/v3/r9/logs/watch.log", "--what", "watch r9", "--",
                             "results/v3/r9/watch_r9.py", "--interval", "300"], self.logs / "night_spawn.log")
            w.wait()
        self.state["league"] = dict(started=now_s(), rc=rc)
        return rc == 0

    def stop(self, why: str, kind: str = "needs_user") -> None:
        """멈춤 셋 (S′ 검토 medium — 멈춤이 상태 파일에 영영 남아 이어 하기가 안 되던 것):
        - precondition: 띄우기 전 조건(보정 확인·C0 값 옮겨 적기·S′ C0-9 등록)이 안 맞음 → 단계를 바꾸지 않는다. 조건을 맞추고 다시 띄우면 그 단계부터.
        - transient: 일시 실패(잼 rc ≠ 0, 리그 띄움 실패) → phase stopped + phase_before. 다시 띄우면 phase_before 부터 다시 본다.
        - needs_user: 사람이 보고 정할 것(NaN·오류, 끊김 반복, 두뇌 빠짐, 고르기 멈춤, 옮겨 적기 필요) → phase stopped. 다시 띄워도 멈춰 있고,
          `--resume-from {train,eval,choose,league}` 로 이어 간다."""
        if kind not in STOP_KINDS:
            raise ValueError(f"모르는 멈춤 종류 {kind}")
        if kind != "precondition":
            if self.state.get("phase") != "stopped":
                self.state["phase_before"] = self.state.get("phase")
            self.state["phase"] = "stopped"
        self.state["stop_kind"] = kind
        self.state["note"] = why
        self.event(f"멈춤({kind}): {why}", progress=True)
        if self.args.dry_run:
            return
        if kind != "precondition":
            self.calib.mkdir(parents=True, exist_ok=True)
            with (self.calib / "C0-10_FAIL.md").open("a", encoding="utf-8") as f:
                f.write(f"- {now_s()} (단계 {self.state.get('attempt')}, {kind}): {why}\n")
        self.save()

    def resume(self) -> str | None:
        """다시 띄울 때 멈춘 상태를 푼다. None = 이어 감, 글 = 멈춘 채 끝낼 까닭."""
        ph = self.state.get("phase")
        rf = getattr(self.args, "resume_from", None)
        if rf:
            if ph not in ("stopped", "done") and ph != rf:
                self.event(f"--resume-from {rf}: 단계 {ph} 에서 {rf} 로 옮김 (사람 지시)", progress=True)
            elif ph in ("stopped", "done"):
                self.event(f"--resume-from {rf}: 멈춤({self.state.get('stop_kind')}) 뒤 {rf} 부터 이어 감 (사람 확인)", progress=True)
            self.state.update(phase=rf, stop_kind=None, note=None)
            if rf == "train":                                # 사람이 고친 뒤: 끝나지 않은 묶음의 띄움 수를 0 부터 다시 센다
                for rs in self.state.get("runs", {}).values():
                    if rs.get("status") != "done":
                        rs["attempts"] = 0
            self.save()
            return None
        if ph != "stopped":
            return None
        kind = self.state.get("stop_kind")
        before = self.state.get("phase_before")
        if kind in ("transient", "precondition") and before in ("train", "eval", "choose", "league"):
            self.event(f"일시 멈춤({kind}) 뒤 다시 띄움 → 단계 {before} 부터 다시 본다", progress=True)
            self.state.update(phase=before, stop_kind=None, note=None)
            self.save()
            return None
        return (f"사람 확인이 필요한 멈춤({kind or '종류 기록 없음'}): {self.state.get('note') or ''} — 고친 뒤 "
                f"`--resume-from {{train,eval,choose,league}}` 로 이어 간다")

    # --- preconditions ---
    def gates_confirmed(self) -> str | None:
        """None if the C0 gates were confirmed (calib/C0_STATE.json history: phase confirm, status confirmed — STATUS 6절 3), else why."""
        sp = self.c0_state_path()
        if not sp.exists():
            return f"보정 관문 상태 {rel(sp)} 가 없다 — C0 고르기·확인 뒤에 C0-10 (STATUS 6절)"
        st = json.loads(sp.read_text(encoding="utf-8"))
        if not any(h.get("phase") == "confirm" and h.get("status") == "confirmed" for h in st.get("history", [])):
            return "보정 관문 확인(calibrate --phase confirm)이 'confirmed' 로 끝나지 않았다 — C0-10 을 띄우지 않는다"
        return None

    def decisions_registered(self) -> str | None:
        """None if the bundle decisions JSON carries the S′ C0-9 registration (`speed_dps`), else why (STATUS 3절: 그때까지 리그를 띄우지 않는다)."""
        try:
            d = json.loads(absp(self.args.decisions_json).read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return f"묶음 결정 수 파일을 못 읽음: {self.args.decisions_json}"
        if not (d.get("speed_dps") or {}).get("round0"):
            return "묶음 결정 수가 S′ C0-9 로 다시 등록되지 않았다(speed_dps 없음 — 11-11 값은 처음 세계 것, STATUS 3절)"
        return None

    # --- main loop ---
    def c0_synced(self) -> str | None:
        """None if the C0 values (calib/C0_STATE.json) are already in the YAML the short training reads, else why (S′ 검토 medium:
        C0-10 학습은 YAML 만 읽고 잼은 C0_STATE 를 입힌 세계에서 재므로, 옮겨 적지 않으면 배운 세계와 잰 세계가 달라진다). C0-10 γ 자신과 F 판에서
        이 실행기가 미리 적은 f_enabled 는 비교에서 뺀다 (F 판 학습은 --fallback-f, 잼은 --set 으로 F 를 건다)."""
        try:
            ct, cj = B.load_r9_config(self.cfg_path), B.load_r9_config(self.jcfg_path)
            EV.check_c0_state(ct, cj, "C0-10 학습", path=self.c0_state_path(), skip_gates=("C0-10",),
                              skip_f=self.state.get("attempt") == "F")
        except SystemExit as e:
            return str(e)
        return None

    def prechecks(self) -> str | None:
        """학습·잼·고르기 전 조건 (멈추면 precondition — 단계를 바꾸지 않는다). 묶음 결정 수 S′ C0-9 등록(speed_dps)도 C0-10 전에 본다:
        STATUS 0절 차례가 C0-9(다시) → … → C0-10 이고 README 2절 3 이 '등록이 없으면 밤 실행기를 띄우지 않는다' 로 정했다(--no-league 면 리그 단계가
        없으니 보지 않는다)."""
        return self.gates_confirmed() or self.c0_synced() or (self.decisions_registered() if self.args.league else None)

    # --- main loop ---
    def run(self) -> int:
        self.event(f"밤 실행기 시작: 단계 {self.state['phase']} (pid {os.getpid()}), 창 {self.args.window}, 속도 {self.speeds_from}")
        why = self.resume()
        if why:
            self.event(f"밤 실행기 끝: 멈춰 있음 — {why}", progress=True)
            return 2
        if not self.args.skip_gate_check and self.state["phase"] in ("train", "eval", "choose"):
            why = self.prechecks()
            if why:
                self.stop(why, kind="precondition")
                self.event(f"밤 실행기 끝: 단계 {self.state['phase']} 그대로 — 조건을 맞춘 뒤 다시 띄우면 이어 간다", progress=True)
                return 2
        while self.state["phase"] not in ("done", "stopped"):
            ph = self.state["phase"]
            if ph == "train":
                ok = self.train()
                if ok:
                    self.state["phase"] = "eval"
            elif ph == "eval":
                if self.evaluate():
                    self.state["phase"] = "choose"
            elif ph == "choose":
                self.state["phase"] = self.choose()
            elif ph == "league":
                if not self.args.league:
                    self.state["phase"] = "done"
                    self.state["note"] = "C0-10 통과 — --no-league 라 리그는 띄우지 않음"
                    continue
                why = None if self.args.skip_gate_check else self.decisions_registered()
                if why:
                    self.stop(why, kind="precondition")
                    self.event("밤 실행기 끝: 단계 league 그대로 — 등록 뒤 다시 띄우면 리그부터", progress=True)
                    return 2
                if not self.league_synced():
                    break
                if self.launch_league():
                    self.state["phase"] = "done"
                else:
                    self.stop(f"리그 띄움 실패 (spawn_detached rc {self.state['league'].get('rc')}) — logs/night_spawn.log", kind="transient")
            else:
                raise RuntimeError(f"모르는 단계 {ph}")
            self.save()
        self.event(f"밤 실행기 끝: {self.state['phase']} — {self.state.get('note') or ''}", progress=True)
        return 0 if self.state["phase"] == "done" else 2

    def league_synced(self) -> bool:
        """리그 전에 C0_STATE 의 γ (values.C0-10)·F 가 YAML 과 같은지 다시 본다 (사람이 옮겨 적은 뒤 --resume-from league 로 이어 갈 때도). 다르면
        sync_config 가 옮겨 적거나(--no-write-config 면) 멈춘다."""
        sp = self.c0_state_path()
        if not sp.exists():
            return True
        c0 = json.loads(sp.read_text(encoding="utf-8"))
        g = (c0.get("values") or {}).get("C0-10")
        if g is None:
            return True
        return self.sync_config(float(g), bool(c0.get("f_enabled")))

    def dry_run(self) -> int:
        now = self.clock()
        cw = LG.current_window(now, self.window)
        print(f"# R9 밤 실행기 차례 (dry-run — 띄우지 않고 상태 파일도 쓰지 않음) {now:%Y-%m-%d %H:%M}")
        print(f"상태 {rel(self.state_path)} {'(있음 — 단계 ' + str(self.state['phase']) + ', ' + str(self.state.get('attempt')) + ')' if self.state_path.exists() else '(없음 — 처음부터)'}")
        print(f"밤 창 {self.args.window}: 지금 {'창 안, 끝 ' + f'{cw[1]:%H:%M}' if cw else '창 밖'} · 다음 창 시작 {LG.next_window_start(now, self.window):%m-%d %H:%M}")
        print(f"속도 (결정/초): {({k: round(v) for k, v in self.speeds.items()})} — {self.speeds_from}")
        free = self._free()
        print(f"지금 확인: 언리얼/UBT/MSBuild {self._unreal() or '없음'}, 남은 커밋 메모리 {'모름' if free is None else f'{free / LG.GB:.1f} GB'}")
        plan = self.plan()
        for stage in ("prey", "wolf"):
            specs = [p for p in plan if p["stage"] == stage]
            est = max(p["est_s"] for p in specs)
            procs = sum(p["procs"] for p in specs)
            print(f"\n## 1. C0-10 학습 — {'먹이 넷' if stage == 'prey' else '늑대 둘'} (함께, 프로세스 {procs}, 어림 {est / 3600:.2f} h)")
            print(f"   지금 띄우면: {self.gate(procs, est) or '띄움'}")
            for p in specs:
                print(f"   - {p['run']}: {self.finished(p) or '아직'} · {p['decisions'] / 1e6:.0f}M · 어림 {p['est_s'] / 3600:.2f} h · 상한 {p['wall_hours']} h")
                print(f"     python {' '.join(p['args'])}")
        print("\n## 2. 잼 (확인 시드 44050~44099, 창과 무관 — 언리얼·메모리만)")
        for g in GAMMAS:
            print(f"   - γ {g}: eval_r9.py calibrate --gates C0-10 --gamma {g} --brain -:deer=<npz> -:boar=<npz> -:wolf=<npz> → {rel(self.eval_file(g))}")
        print("\n## 3. 고르기 (9-1 + 11-12 등록 조건) → calib/C0-10_choice.json, C0_STATE.json values.C0-10")
        print("   pass → γ·F 를 configs/v3_r9.yaml 에 옮겨 적고 리그 / 먹이 둘 다 떨어짐 → F 한 번(C0-11 에서 걸었으면 멈춤) / 늑대만 → 멈춤(처방 미구현) / "
              "대조 늑대 통과 → 멈춤")
        print(f"\n## 4. 리그: python {' '.join(self.league_args())}" + ("" if self.args.no_watch else " + watch_r9.py --interval 300"))
        print(f"\n띄우기 전 조건: 보정 관문 확인 — {self.gates_confirmed() or '됨'}; C0 값 옮겨 적기 — {self.c0_synced() or '됨'}; "
              f"묶음 결정 수 S′ 등록 — {self.decisions_registered() or '됨'}")
        if self.state.get("phase") == "stopped":
            print(f"멈춰 있음 ({self.state.get('stop_kind')}, 앞 단계 {self.state.get('phase_before')}): {self.state.get('note')}")
        return 0


def acquire_lock(path: Path) -> bool:
    if path.exists():
        try:
            pid = int(path.read_text(encoding="utf-8").split()[0])
        except (ValueError, IndexError):
            pid = None
        if pid and pid != os.getpid() and LG.pid_alive(pid, "run_night.py"):
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{os.getpid()} {now_s()}\n", encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="configs/v3_r9.yaml", help="학습·잼·리그가 모두 이 파일을 읽고, 고른 γ·F 도 여기에 옮겨 적는다")
    ap.add_argument("--judge-config", default="configs/v3_r9_judge.yaml", help="C0 값 옮겨 적기 확인·잼에 쓰는 판정 꼴 설정")
    ap.add_argument("--resume-from", choices=("train", "eval", "choose", "league"), default=None,
                    help="사람 확인 멈춤(needs_user) 뒤 이 단계부터 이어 간다 (train 이면 끝나지 않은 묶음의 띄움 수를 0 부터)")
    ap.add_argument("--state", default=None, help="기본 ckpt/r9/night_state.json")
    ap.add_argument("--c010-out", default="ckpt/r9/c010")
    ap.add_argument("--log-dir", default=str(LOGS))
    ap.add_argument("--calib-dir", default=str(CALIB))
    ap.add_argument("--decisions-json", default="results/v3/r9/bundle_decisions.json")
    ap.add_argument("--window", default=LG.WINDOW_DEFAULT, help="밤 창 HH:MM-HH:MM (STATUS 5절)")
    ap.add_argument("--check-anytime", action="store_true", help="리그 점검은 창 밖에서도 (학습 아님)")
    ap.add_argument("--rounds", type=int, default=10)
    ap.add_argument("--max-procs", type=int, default=6)
    ap.add_argument("--proc-mem-gb", type=float, default=0.5)
    ap.add_argument("--max-attempts", type=int, default=3)
    ap.add_argument("--check-cmd", default=CHECK_CMD)
    ap.add_argument("--poll", type=float, default=30.0)
    ap.add_argument("--no-write-config", dest="write_config", action="store_false",
                    help="고른 γ·F 를 configs 에 옮겨 적지 않는다 (다르면 멈춤)")
    ap.add_argument("--no-watch", action="store_true")
    ap.add_argument("--no-league", dest="league", action="store_false", help="C0-10 만 하고 리그는 띄우지 않는다")
    ap.add_argument("--skip-gate-check", action="store_true", help="[시험 전용] 보정 관문 확인·묶음 등록 검사를 건너뛴다")
    ap.add_argument("--dry-run", action="store_true")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    nr = Night(args)
    if args.dry_run:
        return nr.dry_run()
    lock = nr.state_path.with_suffix(".lock")
    if not acquire_lock(lock):
        print(f"다른 밤 실행기가 같은 상태 파일로 돈다 ({lock}) — 두 벌 띄우지 않는다", flush=True)
        return 3
    try:
        return nr.run()
    finally:
        try:
            if lock.exists() and lock.read_text(encoding="utf-8").split()[0] == str(os.getpid()):
                lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    sys.exit(main())

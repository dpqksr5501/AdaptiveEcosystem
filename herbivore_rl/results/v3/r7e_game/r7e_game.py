"""게임 기본 두뇌(내장 R1b-F) 대 최신 두뇌 R7e — 헤드리스 언리얼에서 같은 조건으로 견준다 (10-27 사용자 '최신 두뇌로 갈아껴서 한번 테스트해봐').

    # herbivore_rl/ 에서 (PYTHONUTF8=1). 언리얼은 이 도구가 띄운다 (창 없음 — -NullRHI, -windowed 쓰지 않음)
    python results/v3/r7e_game/r7e_game.py run --out <scratch>/r7e_game/runs --sessions 20020-20031 --parallel 4
    python results/v3/r7e_game/r7e_game.py analyze --runs <scratch>/r7e_game/runs --sessions 20020-20031 --out results/v3/r7e_game/compare

두 맵 (MAPS):
  it  = 팀 통합 맵 /Game/Map/LV_Ecosystem_IntegrationTest (팀 날씨 출처 없음 — 같은 세션·같은 두뇌면 바이트 같은 결정적 비교). 300 초 스냅숏도 쓴다.
  jyu = 사용자가 지금 쓰는 조연우 맵 복사본 /Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem, 맵 값 그대로 (식생 soil-v1·팀 life·무리 이주·팀 비 순환을 환경 감시가
        v3 날씨로 옮김 — level_jyu_eco 의 '전체 모드'). 팀 비를 실제 시간으로 읽어 같은 세션도 판마다 조금 다르다 → 세션 여러 개 합으로 본다.
        스냅숏은 식생·life 때문에 거부되므로 쓰지 않는다 (기록 줄만).
두 두뇌 (BRAINS): cur = 내장 R1b-F (v3_r1_g995_s3_20m@eca97f2e, 관측 18·판 2 — 10-28 까지의 게임 기본. 10-29 부터 기본 두뇌가 R7e 라
  -EcoV3Brain=builtin 으로 명시한다 — 이 측정 때(10-27)는 두뇌 인수 없음이었다. 같은 두뇌라 같은 판),
  r7e = -EcoV3Brain=v3_r7_g995_s1_20m (AdaptiveEcosystem/EcoBrains/v3_r7_g995_s1_20m.json, id v3_r7_g995_s1_20m@40d8710d, 계약 0xad7bad5e1acaf071, 관측 24·판 5).
같은 인수 (모두): -game -EcoIntegratedV3 -ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=3 -EcoV3DeerPerRegion=128 -EcoV3Seed=<세션>
  -EcoV3ObsParityLog=1 (사슴 줄 '[EcoV3Obs] <지역> | t … | p … | h … | seen …' 을 결정 스텝마다 — 측정 전용, 결정은 그대로) -benchmark -fps=30 -seconds=<초+1>
  -NullRHI -NoSound -unattended -nosplash -nopause -DisablePlugins=Bridge,Fab -abslog=<폴더>/<이름>.log
  (it 만 -EcoV3SnapshotAt=<초> -EcoV3SnapshotOut=<폴더>/<이름>.json). AutoAdapt 는 기본 끔 그대로 (Saved/EcoAdapt 에 쓰지 않는다 — 앞뒤 목록으로 확인).
빌드 잠금 약속: 판 묶음(wave)을 띄우기 전마다 잠금 파일(LOCK)이 있거나 UnrealBuildTool·dotnet(UBT)·ShaderCompileWorker·LiveCoding 이 돌면 없어질 때까지
  기다린다 (이 도구가 띄운 언리얼의 자식은 빼고). 묶음 하나 = 같은 맵의 세션 짝(두 두뇌)들 — 짝은 같은 빌드 안에서 돈다. 묶음 앞뒤 DLL 시각을 적는다.
  묶음이 끝나면 잠금을 다시 보고 다음 묶음 전에 WAVE_GAP 초 쉰다(다른 워크플로가 잠금을 걸 틈). 판 하나가 TIMEOUT 초를 넘으면 그 PID 만 끝낸다.
뽑기 (extract): 판이 끝나면 원 기록에서 사슴 줄을 지역마다 npz(t·id·p·h·seen·j·N)로, 나머지 줄을 <이름>.ecov3.log 로 남기고 원 기록을 지운다
  (줄 수 확인 뒤). 사슴 줄 내용 지문(sha256, 시각 머리 뺀 '[EcoV3Obs]' 부터)을 <이름>.meta.json 에 남긴다 — 같은 시드 다시 돌림 비교용.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                                  # herbivore_rl/
PROJ = ROOT.parent / "AdaptiveEcosystem"
UE = Path("C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe")
UPROJECT = PROJ / "AdaptiveEcosystem.uproject"
DLL = PROJ / "Binaries" / "Win64" / "UnrealEditor-AdaptiveEcosystem.dll"
LOCK = Path("C:/Users/Sinhyeok/AppData/Local/Temp/claude/C--kwon-univ-3-1-GameContentsCapstoneDesign-AdaptiveEcosystem/"
            "929c780f-6f46-4644-81c6-914789098bd9/scratchpad/ue_build.lock")
MAPS = {"it": "/Game/Map/LV_Ecosystem_IntegrationTest", "jyu": "/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem"}
MAP_LABEL = {"it": "팀 통합 맵 (LV_Ecosystem_IntegrationTest)", "jyu": "조연우 맵 복사본 (LV_EcoV3_JYUEcosystem, 맵 값 그대로)"}
R7E = "v3_r7_g995_s1_20m"
BRAINS = {"cur": dict(label="내장 R1b-F (10-28 까지 게임 기본)", id="v3_r1_g995_s3_20m@eca97f2e", args=["-EcoV3Brain=builtin"]),   # 10-29 기본 = R7e → 명시
          "r7e": dict(label="R7e 두 길·판 5", id="v3_r7_g995_s1_20m@40d8710d", args=[f"-EcoV3Brain={R7E}"])}
COMMON = ["-benchmark", "-fps=30", "-NullRHI", "-NoSound", "-unattended", "-nosplash", "-nopause", "-DisablePlugins=Bridge,Fab"]
SECONDS = 300
TIMEOUT = 600                                           # 판 하나 10 분 (빌드 잠금 약속)
WAVE_GAP = 20
REGIONS = ("Barren", "Forest", "Highland")

RE_DEER = re.compile(r"\[EcoV3Obs\] (\w+) \| t (\d+) \| id (\d+) \| p (\S+) (\S+) \| h (\S+) (\S+) \| seen (\d) \| a (\S+) (\S+) \| j (\S+) (\S+) \| "
                     r"E (\S+) \| N (\S+) \| hid (\d)")


def parse_sessions(text: str) -> list[int]:
    out: list[int] = []
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


# --------------------------------------------------------------------- #
# 빌드 잠금·막는 프로세스
# --------------------------------------------------------------------- #

OURS: set[int] = set()


def blockers() -> list[str]:
    import psutil

    out = []
    if LOCK.exists():
        out.append(f"잠금 파일 {LOCK.name}")
    for p in psutil.process_iter(["pid", "name", "ppid"]):
        try:
            n = (p.info["name"] or "").lower()
            if p.info["ppid"] in OURS:
                continue
            if n.startswith("unrealbuildtool") or n.startswith("shadercompileworker") or n.startswith("livecoding"):
                out.append(f"{p.info['name']} {p.info['pid']}")
            elif n == "dotnet.exe":
                cl = " ".join(p.cmdline() or [])
                if "UnrealBuildTool" in cl:
                    out.append(f"dotnet(UBT) {p.info['pid']}")
        except Exception:
            continue
    return out


def wait_clear(log) -> float:
    t0 = time.time()
    said = None
    while True:
        b = blockers()
        if not b:
            return time.time() - t0
        if b != said:
            log(f"  기다림: {', '.join(b)}")
            said = b
        time.sleep(10)


def dll_stamp() -> str:
    st = DLL.stat()
    return datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds") + f" {st.st_size}"


# --------------------------------------------------------------------- #
# 띄우기
# --------------------------------------------------------------------- #


def unreal_cmd(map_key: str, session: int, brain: str, out: Path, name: str, seconds: int, obs_log: bool = True) -> list[str]:
    cmd = [str(UE), str(UPROJECT), MAPS[map_key], "-game", "-EcoIntegratedV3", "-ini:Engine:[ConsoleVariables]:eco.IntegratedPolicyVersion=3",
           "-EcoV3DeerPerRegion=128", f"-EcoV3Seed={int(session)}"]
    if obs_log:
        cmd.append("-EcoV3ObsParityLog=1")
    cmd += BRAINS[brain]["args"]
    if map_key == "it":
        cmd += [f"-EcoV3SnapshotAt={seconds}", f"-EcoV3SnapshotOut={(out / f'{name}.json').as_posix()}"]
    cmd += COMMON + [f"-seconds={seconds + 1}", f"-abslog={(out / f'{name}.log').as_posix()}"]
    return cmd


def extract(out: Path, name: str) -> dict:
    """원 기록 → 지역마다 사슴 줄 npz + 나머지 줄 .ecov3.log + 지문. 원 기록은 줄 수 확인 뒤 지운다."""
    from array import array

    raw = out / f"{name}.log"
    rows: dict = {}
    keep = []
    h = hashlib.sha256()
    n_deer = 0
    n_lines = 0
    with open(raw, encoding="utf-8", errors="replace") as f:
        for line in f:
            n_lines += 1
            k = line.find("[EcoV3Obs] ")
            if k >= 0 and "| id " in line:
                m = RE_DEER.search(line, k)
                if m:
                    body = line[k:].rstrip("\r\n")
                    h.update(body.encode("utf-8"))
                    h.update(b"\n")
                    g = m.groups()
                    R = rows.get(g[0])
                    if R is None:
                        R = rows[g[0]] = dict(t=array("l"), id=array("q"), p=array("d"), h=array("f"), seen=array("b"), j=array("f"), N=array("f"))
                    R["t"].append(int(g[1]))
                    R["id"].append(int(g[2]))
                    R["p"].extend((float(g[3]), float(g[4])))
                    R["h"].extend((float(g[5]), float(g[6])))
                    R["seen"].append(int(g[7]))
                    R["j"].extend((float(g[10]), float(g[11])))
                    R["N"].append(float(g[13]))
                    n_deer += 1
                    continue
            keep.append(line)
    meta = dict(name=name, raw_lines=n_lines, deer_rows=n_deer, deer_sha256=h.hexdigest(), regions={})
    arrays = {}
    for reg, R in rows.items():
        arrays[f"{reg}_t"] = np.frombuffer(R["t"], dtype=np.int32 if R["t"].itemsize == 4 else np.int64).astype(np.int32)
        arrays[f"{reg}_id"] = np.frombuffer(R["id"], dtype=np.int64)
        arrays[f"{reg}_p"] = np.frombuffer(R["p"], dtype=np.float64).reshape(-1, 2)
        arrays[f"{reg}_h"] = np.frombuffer(R["h"], dtype=np.float32).reshape(-1, 2)
        arrays[f"{reg}_seen"] = np.frombuffer(R["seen"], dtype=np.int8).astype(np.uint8)
        arrays[f"{reg}_j"] = np.frombuffer(R["j"], dtype=np.float32).reshape(-1, 2)
        arrays[f"{reg}_N"] = np.frombuffer(R["N"], dtype=np.float32)
        meta["regions"][reg] = dict(rows=len(R["t"]), t_min=int(arrays[f"{reg}_t"].min()), t_max=int(arrays[f"{reg}_t"].max()))
    np.savez_compressed(out / f"{name}.deer.npz", **arrays)
    (out / f"{name}.ecov3.log").write_text("".join(keep), encoding="utf-8")
    meta["kept_lines"] = len(keep)
    ok = meta["kept_lines"] + n_deer == n_lines and n_deer > 0
    meta["extract_ok"] = bool(ok)
    if ok:
        raw.unlink()
    (out / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return meta


def launch(job: dict, log) -> dict:
    import psutil

    out = Path(job["out"])
    name = job["name"]
    (out / f"{name}.cmd.txt").write_text(subprocess.list2cmdline(job["cmd"]) + "\n", encoding="utf-8")
    t0 = time.time()
    with open(out / f"{name}.out", "wb") as fo:
        p = subprocess.Popen(job["cmd"], stdout=fo, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        OURS.add(p.pid)
        log(f"  시작 {name} pid {p.pid}")
        try:
            rc = p.wait(timeout=job.get("timeout", TIMEOUT))
        except subprocess.TimeoutExpired:
            log(f"  시간 넘김 {name} pid {p.pid} — 이 PID 만 끝냄")
            try:
                psutil.Process(p.pid).kill()
            except Exception:
                pass
            p.wait()
            rc = "timeout"
    res = dict(name=name, pid=p.pid, rc=rc, wall_s=round(time.time() - t0, 1))
    if (out / f"{name}.log").exists() and job.get("extract", True):
        try:
            m = extract(out, name)
            res.update(deer_rows=m["deer_rows"], extract_ok=m["extract_ok"])
        except Exception as e:  # noqa: BLE001
            res.update(extract_error=repr(e))
    if not job.get("extract", True) and rc == 0:
        (out / f"{name}.done").write_text(json.dumps(res, ensure_ascii=False) + "\n", encoding="utf-8")
    log(f"  끝 {name}: 코드 {rc} · {res['wall_s']} 초 · 사슴 줄 {res.get('deer_rows')}")
    return res


def make_jobs(a) -> list[list[dict]]:
    """묶음 목록: 같은 맵의 세션 짝(두뇌 둘)을 parallel 개씩. 맵을 번갈아 둔다. 첫 묶음 앞에 확인 판 묶음."""
    out = Path(a.out)
    sessions = parse_sessions(a.sessions)
    per = max(1, a.parallel // 2)

    def done(n: str) -> bool:
        return a.skip_existing and ((out / f"{n}.meta.json").exists() or (out / f"{n}.done").exists())

    waves: list[list[dict]] = []
    if a.checks:
        s0 = sessions[0]
        chk = [("it", s0, "cur", f"it_s{s0}_cur_obsoff", False), ("it", s0, "r7e", f"it_s{s0}_r7e_b", True),
               ("jyu", s0, "cur", f"jyu_s{s0}_cur_b", True), ("jyu", s0, "r7e", f"jyu_s{s0}_r7e_b", True)]
        w = [dict(name=n, map=m, session=s, brain=b, out=str(out), extract=o, cmd=unreal_cmd(m, s, b, out, n, a.seconds, obs_log=o))
             for m, s, b, n, o in chk if not done(n)]
        if w:
            waves.append(w)
    groups = {m: [sessions[i:i + per] for i in range(0, len(sessions), per)] for m in a.maps}
    for k in range(max(len(g) for g in groups.values())):
        for m in a.maps:
            if k < len(groups[m]):
                w = []
                for s in groups[m][k]:
                    for b in a.brains:
                        n = f"{m}_s{s}_{b}{a.suffix}"
                        if not done(n):
                            w.append(dict(name=n, map=m, session=s, brain=b, out=str(out), cmd=unreal_cmd(m, s, b, out, n, a.seconds)))
                if w:
                    waves.append(w)
    return waves


def cmd_run(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "run_log.txt", "a", encoding="utf-8")

    def log(msg: str):
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    waves = make_jobs(a)
    log(f"시작: 묶음 {len(waves)} 개 · 판 {sum(len(w) for w in waves)} 개 · 맵 {a.maps} · 세션 {a.sessions} · {a.seconds} 초 · 동시 {a.parallel}")
    head = subprocess.run(["git", "-C", str(ROOT.parent), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(ROOT.parent), "status", "--porcelain", "--", "AdaptiveEcosystem/Source"], capture_output=True,
                           text=True).stdout.strip()
    log(f"HEAD {head} · 작업 트리 Source 변경: {dirty.replace(chr(10), ' | ') or '없음'}")
    record = []
    for i, w in enumerate(waves):
        waited = wait_clear(log)
        d0 = dll_stamp()
        log(f"묶음 {i + 1}/{len(waves)} ({', '.join(j['name'] for j in w)}) — 기다린 {waited:.0f} 초 · DLL {d0}")
        with ThreadPoolExecutor(max_workers=len(w)) as ex:
            res = list(ex.map(lambda j: launch(j, log), w))
        d1 = dll_stamp()
        if d1 != d0:
            log(f"  주의: 묶음 중 DLL 바뀜 {d0} → {d1}")
        rec = dict(wave=i + 1, dll_before=d0, dll_after=d1, waited_s=round(waited, 1), jobs=res)
        record.append(rec)
        with open(out / "waves.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if i + 1 < len(waves):
            time.sleep(WAVE_GAP)
    bad = [j for r in record for j in r["jobs"] if j["rc"] != 0 or not j.get("extract_ok", True)]
    log(f"끝: 판 {sum(len(r['jobs']) for r in record)} 개, 문제 {len(bad)} {[(j['name'], j['rc']) for j in bad]}")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--sessions", default="20020-20031")
    r.add_argument("--maps", nargs="+", default=["it", "jyu"], choices=sorted(MAPS))
    r.add_argument("--brains", nargs="+", default=["cur", "r7e"], choices=sorted(BRAINS))
    r.add_argument("--parallel", type=int, default=4)
    r.add_argument("--seconds", type=int, default=SECONDS)
    r.add_argument("--checks", action="store_true", help="첫 묶음에 확인 판 넷 (it 사슴 줄 끔·it 다시 돌림·jyu 다시 돌림 둘)")
    r.add_argument("--skip-existing", action="store_true")
    r.add_argument("--suffix", default="", help="판 이름 뒤에 붙임 (예 _c = 빌드가 바뀐 뒤 같은 세션 다시 돌림 — 사슴 줄 지문을 견준다)")
    x = sub.add_parser("extract")
    x.add_argument("--out", required=True)
    x.add_argument("names", nargs="+")
    y = sub.add_parser("analyze")
    y.add_argument("--runs", required=True)
    y.add_argument("--sessions", default="20020-20031")
    y.add_argument("--seconds", type=int, default=SECONDS)
    y.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "run":
        return cmd_run(a)
    if a.cmd == "extract":
        for n in a.names:
            print(extract(Path(a.out), n))
        return 0
    import r7e_game_analyze as an  # noqa: E402  (같은 폴더)

    return an.cmd_analyze(a)


if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parent))
    sys.exit(main())

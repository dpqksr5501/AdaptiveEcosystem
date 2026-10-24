"""팀 생태계 맵 복사본에서 우리가 해 오던 시험 (10-25, 사용자 '그 사람 레벨디자인을 그대로 복사해와서 우리 레벨에서 테스트하자 — 우리가 하던 방식의
테스트를 그사람 맵을 받아와서 하자').

맵 = /Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem (조연우 LV_JYU_Ecosystem 의 우리 복사본, f46685d — results/v3/jyu_map/README.md). 레벨·C++·팀 에셋·기본 두뇌·
기본 설정은 바꾸지 않는다. 두 모드는 실행 인수로만 고른다.

    # herbivore_rl/ 에서 (PYTHONUTF8=1). 언리얼은 이 도구가 띄운다 (Git Bash 경로 바꿈과 무관 — subprocess 가 인수를 그대로 넘긴다)
    python results/v3/level_jyu_eco/level_jyu_eco.py unreal --mode control --sessions 20010-20019 --out <폴더> [--rerun 20010] [--parallel 5]
    python results/v3/level_jyu_eco/level_jyu_eco.py unreal --mode full    --sessions 20010-20019 --out <폴더>
    python results/v3/level_jyu_eco/level_jyu_eco.py mirror  --sessions 20010-20019 --replicates 10          # 파이썬 거울 두 두뇌 → runs/ (git 밖)
    python results/v3/level_jyu_eco/level_jyu_eco.py convert --control <폴더> --sessions 20010-20019         # adapt.convert 로 스냅숏마다 거울 변환
    python results/v3/level_jyu_eco/level_jyu_eco.py compare --control <폴더> --full <폴더> --sessions 20010-20019 --replicates 10 \
        --out results/v3/level_jyu_eco/parity

모드 (MODES):
  control 대조 모드 = 우리 v3 규칙 + 이 맵의 지형·은신처·나무(없음)·시작 날씨. 팀 기능 넷을 실행 인수로 끈다:
          -EcoEcosystemLife=0 (팀 life — 조정자 BeginPlay 가 읽는다), -EcoV3EnvWatch=0 (팀 비 순환을 v3 날씨로 옮기지 않음 — 시작 날씨 고정),
          ExecCmds 'eco.HerdMigration 0' (무리 이주 새 출발), ExecCmds 'setnopec EcoCreatureIntegrationSpawner bEnableVegetation False'
          (식생 soil-v1 — 끄는 인수가 없어서 엔진 콘솔 명령으로 이 Play 의 조정자 값만 끈다. 0 프레임에 들어가고 v3 무대는 8 프레임에 만들어지며
          식생 켬은 무대를 만들 때만 읽는다(EcoPolicyV3IntegratedSubsystem.cpp). 맵 파일·C++ 는 그대로. 콘솔 명령 SETNOPEC = 편집 알림 없이 값만 바꿈).
          240 초 스냅숏(-EcoV3SnapshotAt=240)을 쓴다 — 식생·life 가 켜져 있으면 스냅숏이 거부되므로, 스냅숏이 써진 것이 끈 확인이다.
  full    전체 모드 = 맵에 저장된 그대로(식생 soil-v1·life·무리 이주·팀 비 순환을 우리 환경 감시가 v3 날씨로 옮김). 스냅숏은 거부되므로 쓰지 않고
          기록(-abslog) 240 초 줄에서 같은 지표를 읽는다. 팀 날씨 감시가 실제 시간 1 초마다 돌아 같은 시드도 판마다 조금 다르다(jyu_map/README.md).
  full_nolife · full_noveg · full_noenv · full_nomig  전체 모드에서 팀 기능 하나씩만 끈 판(life · 식생 · 환경 감시 · 무리 이주) — 전체 모드와 대조 모드의
          차이가 어디서 오나 보는 '하나씩 빼 보기'(판정 아님). compare 의 --full-nolife 등으로 넣는다.
  모두: -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=<세션> [-EcoV3Brain=v3_r7_g995_s1_20m] -benchmark -fps=30 -seconds=241 -NullRHI
  -NoSound -unattended -nosplash -nopause -DisablePlugins=Bridge,Fab -abslog=<폴더>/s<세션>_<두뇌>.log. 두뇌 cur = 게임 기본(내장 R1b-F), r7e = R7e 두 길·판 5.

셈: results/v3/r7e/unreal_parity.py 와 같다 (그 모듈을 불러 쓴다 — 지역 기록·합·짝 t·같은 방향·크기 z, 언리얼 스냅숏 확인). 다른 것은 셋:
  - 나무 배치 표 대신 '나무 없음' 표(no_trees.json — 지역마다 원판 0). 이 맵에는 나무가 없다. 파이썬 거울도 obstacles.fixed = [] 로 같은 세계.
  - 파이썬 거울 결과는 이 폴더 runs/ (git 밖). 시드는 r7e 와 같은 탐색 범위 32000~ 앞에서부터(세계가 달라 값이 다르다).
  - 전체 모드는 스냅숏이 없어 기록 줄에서 읽는다(log_record). 같은 판의 대조 모드 스냅숏과 기록 줄이 모든 칸에서 같은지 먼저 확인한다(log_vs_snapshot).
기록 줄 칸 (240 초 줄, EcoPolicyV3IntegratedSubsystem.cpp LogContext 들):
  '<지역> | 240.0초 … 사슴 산 a/n … 포획 x (누적 caught) 굶음 y (누적 starved) … 무대 먹이 처음의 f% · 사슴 에너지 평균 e% …'
  '<지역> 도망 | … 누적 시작 started … 반사 스텝 reflex/flee … 쫓긴 사건 chased 중 숨음 hidden (지켜보는 중 watching) · 잡힘 · 굶음 · 잘림 · 이어진 도망 joined'
     → 사건 시작 ep_started = started − joined (스냅숏 episode.started 와 같다 — log_vs_snapshot 이 본다)
  '<지역> 사냥·은신처 | … 누적 shelter/live' (live = 스텝 첫머리 산 사슴-스텝 = 스냅숏 flight.live_steps)
  '<지역> 경계 거리 | … 은신처 안 잡힘 x (누적 c)', '<지역> 날씨 | … 날씨 스텝 누적 맑음 · 비 · 눈'
  끼임 = 10 초 줄마다 '지형 검사 이동 m, 막힘 사슴 a 늑대 b' 의 a·b 합(구간 값 — 240 초까지). 이 맵에는 원판이 없어 원판 끼임은 0 이다(세계 원판 0).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                                  # herbivore_rl/
for _p in (ROOT, ROOT / "results" / "v3" / "mirror", ROOT / "results" / "v3" / "r7e", ROOT / "results" / "v3" / "adapt", ROOT / "results" / "v3" / "live"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

UE = Path("C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe")
UPROJECT = ROOT.parent / "AdaptiveEcosystem" / "AdaptiveEcosystem.uproject"
MAP = "/Game/EcoTest/Maps/LV_EcoV3_JYUEcosystem"
RUNS = HERE.parent / "runs"                             # git 밖 (herbivore_rl/.gitignore runs/)
NO_TREES = HERE.parent / "no_trees.json"                # 지역마다 원판 0 (이 맵의 나무 = 없음)
R7E_BRAIN = "v3_r7_g995_s1_20m"
VEG_OFF = "setnopec EcoCreatureIntegrationSpawner bEnableVegetation False"
MODES = {
    "control": ["-EcoEcosystemLife=0", "-EcoV3EnvWatch=0", f"-ExecCmds=eco.HerdMigration 0, {VEG_OFF}"],
    "full": [],
    # 전체 모드에서 팀 기능 하나씩만 끈 판 (하나씩 빼 보기 — 전체 모드와 대조 모드의 차이가 어디서 오나, 판정 아님)
    "full_nolife": ["-EcoEcosystemLife=0"],
    "full_noveg": [f"-ExecCmds={VEG_OFF}"],
    "full_noenv": ["-EcoV3EnvWatch=0"],
    "full_nomig": ["-ExecCmds=eco.HerdMigration 0"],
}
VARIANTS = (("full_nolife", "life 만 끔"), ("full_noveg", "식생 soil-v1 만 끔"), ("full_noenv", "환경 감시(팀 비 순환 → v3 날씨)만 끔"),
            ("full_nomig", "무리 이주만 끔"))
COMMON = ["-benchmark", "-fps=30", "-seconds=241", "-NullRHI", "-NoSound", "-unattended", "-nosplash", "-nopause", "-DisablePlugins=Bridge,Fab"]
REGIONS = ("Barren", "Forest", "Highland")
BRAIN_ARGS = {"cur": [], "r7e": [f"-EcoV3Brain={R7E_BRAIN}"]}


def up():
    """r7e/unreal_parity 모듈 — 나무 배치 표·거울 폴더만 이 맵 것으로 바꿔 쓴다 (셈·확인은 그대로)."""
    import unreal_parity as m

    m.LAYOUT = NO_TREES
    m.RUNS = RUNS
    return m


def parse_sessions(text: str) -> list[int]:
    import run_mirror as rm

    return rm.parse_unreal_maps(text)


# --------------------------------------------------------------------- #
# 언리얼 띄우기
# --------------------------------------------------------------------- #


def unreal_cmd(mode: str, session: int, brain: str, out: Path, name: str, extra=()) -> list[str]:
    cmd = [str(UE), str(UPROJECT), MAP, "-game", "-EcoIntegratedV3", "-EcoV3DeerPerRegion=128", f"-EcoV3Seed={int(session)}"]
    cmd += BRAIN_ARGS[brain] + MODES[mode]
    if mode == "control":
        cmd += ["-EcoV3SnapshotAt=240", f"-EcoV3SnapshotOut={(out / f'{name}.json').as_posix()}"]
    cmd += list(extra) + COMMON + [f"-abslog={(out / f'{name}.log').as_posix()}"]
    return cmd


def _launch(job: dict) -> dict:
    out = Path(job["out"])
    t0 = time.perf_counter()
    (out / f"{job['name']}.cmd.txt").write_text(subprocess.list2cmdline(job["cmd"]) + "\n", encoding="utf-8")
    with open(out / f"{job['name']}.out", "wb") as fo:
        try:
            rc = subprocess.run(job["cmd"], stdout=fo, stderr=subprocess.STDOUT, timeout=job.get("timeout", 900)).returncode
        except subprocess.TimeoutExpired:
            rc = "timeout"
    return dict(name=job["name"], rc=rc, wall_s=round(time.perf_counter() - t0, 1))


def cmd_unreal(a) -> int:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    sessions = parse_sessions(a.sessions)
    jobs = []
    for s in sessions:
        for b in a.brains:
            name = f"s{s}_{b}"
            if a.skip_existing and (out / f"{name}.log").exists():
                continue
            jobs.append(dict(name=name, out=str(out), cmd=unreal_cmd(a.mode, s, b, out, name, a.extra)))
    for s in parse_sessions(a.rerun) if a.rerun else []:
        for b in a.brains:
            name = f"s{s}_{b}_b"
            jobs.append(dict(name=name, out=str(out), cmd=unreal_cmd(a.mode, s, b, out, name, a.extra)))
    t0 = time.perf_counter()
    print(f"언리얼 {a.mode} 판 {len(jobs)} 개, 동시 {a.parallel} → {out}", flush=True)
    res = []
    with ThreadPoolExecutor(max_workers=max(1, int(a.parallel))) as ex:
        for r in ex.map(_launch, jobs):
            print(f"  {r['name']}: 끝 코드 {r['rc']} · {r['wall_s']} 초", flush=True)
            res.append(r)
    (out / f"launch_{a.mode}.json").write_text(json.dumps(dict(mode=a.mode, map=MAP, jobs=res, wall_s=round(time.perf_counter() - t0, 1),
                                                                 args=dict(sessions=sessions, brains=a.brains, extra=a.extra)),
                                                            ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    bad = [r for r in res if r["rc"] != 0]
    print(f"합 {time.perf_counter() - t0:.0f} 초, 실패 {len(bad)}", flush=True)
    return 1 if bad else 0


# --------------------------------------------------------------------- #
# 기록 줄 → 지역 기록 (전체 모드는 이것뿐, 대조 모드는 스냅숏과 견줘 확인)
# --------------------------------------------------------------------- #

RE_MAIN = re.compile(r"\[EcoV3I\] (\S+) \| ([\d.]+)초 .*?\| 사슴 산 (\d+)/(\d+) \|")
RE_CUM = re.compile(r"포획 \d+ \(누적 (\d+)\) 굶음 \d+ \(누적 (\d+)\)")
RE_FOOD = re.compile(r"무대 먹이 처음의 ([\d.]+)% · 사슴 에너지 평균 ([\d.]+)%")
RE_TERR = re.compile(r"지형 검사 이동 (\d+), 막힘 사슴 (\d+) 늑대 (\d+)")
RE_FL = re.compile(r"\[EcoV3I\] (\S+) 도망 \| 240\.0초 \|")
RE_FL_START = re.compile(r"누적 시작 (\d+) · 끝 (\d+) · 열린 (\d+)")
RE_FL_REFLEX = re.compile(r"반사 스텝 (\d+)/(\d+)")
RE_FL_EP = re.compile(r"쫓긴 사건 (\d+) 중 숨음 (\d+) \(지켜보는 중 (\d+)\) · 잡힘 (\d+) · 굶음 (\d+) · 잘림 (\d+) · 이어진 도망 (\d+)")
RE_HUNT = re.compile(r"\[EcoV3I\] (\S+) 사냥·은신처 \| 240\.0초 \|.*은신처 안 사슴·스텝: 구간 \d+/\d+ \([\d.]+%\) · 누적 (\d+)/(\d+)")
RE_ALERT = re.compile(r"\[EcoV3I\] (\S+) 경계 거리 \| 240\.0초 \|.*은신처 안 잡힘 \d+ \(누적 (\d+)\)")
RE_WX = re.compile(r"\[EcoV3I\] (\S+) 날씨 \| 240\.0초 \| (\S+) ([\d.]+) .*날씨 스텝 누적 맑음 (\d+) · 비 (\d+) · 눈 (\d+)")
RE_STAGE = re.compile(r"\[EcoV3I\] 지역 무대 (\S+) \(지역 번호 (\d+)\):.*은신처 (\d+) \(레벨 (\d+) \+ v3 (\d+)")
RE_START = re.compile(r"\[EcoV3I\] 두뇌 시작 \| [\d.]+초 \(전역 스텝 \d+\) \| (\S+)")


def read_log(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def log_record(path: Path) -> dict:
    """기록 하나(-abslog) → {regions: {지역: 기록}, 판 칸}. 지역 기록 열쇠는 r7e unreal_parity.record 와 같고(ep_other 없음) 더한 칸이 있다."""
    txt = read_log(path)
    lines = [s for s in txt.splitlines() if "LogEcoPolicyV3I" in s]
    regs: dict = {}

    def R(reg):
        return regs.setdefault(reg, dict(region=reg, terr_moves=0, terr_deer=0, terr_wolf=0))

    for s in lines:
        m = RE_MAIN.search(s)
        if m:
            reg, t = m.group(1), float(m.group(2))
            r = R(reg)
            g = RE_TERR.search(s)
            if g and t <= 240.0 + 1e-6:
                r["terr_moves"] += int(g.group(1))
                r["terr_deer"] += int(g.group(2))
                r["terr_wolf"] += int(g.group(3))
            if abs(t - 240.0) < 1e-6:
                r.update(alive=int(m.group(3)), n=int(m.group(4)))
                c = RE_CUM.search(s)
                if c:
                    r.update(caught=int(c.group(1)), starved=int(c.group(2)))
                f = RE_FOOD.search(s)
                if f:
                    r.update(food_pct=float(f.group(1)), energy_pct=float(f.group(2)))
            continue
        m = RE_FL.search(s)
        if m:
            r = R(m.group(1))
            a, b, e = RE_FL_START.search(s), RE_FL_REFLEX.search(s), RE_FL_EP.search(s)
            r.update(started=int(a.group(1)), reflex=int(b.group(1)), flee=int(b.group(2)))
            ep = [int(x) for x in e.groups()]
            r.update(ep_chased=ep[0], ep_hidden=ep[1], ep_watching=ep[2], ep_caught=ep[3], ep_starved=ep[4], ep_truncated=ep[5], ep_joined=ep[6],
                     ep_started=int(a.group(1)) - ep[6])
            continue
        m = RE_HUNT.search(s)
        if m:
            R(m.group(1)).update(shelter_steps=int(m.group(2)), live=int(m.group(3)))
            continue
        m = RE_ALERT.search(s)
        if m:
            R(m.group(1)).update(caught_in_cover=int(m.group(2)))
            continue
        m = RE_WX.search(s)
        if m:
            R(m.group(1)).update(weather=m.group(2), weather_x=float(m.group(3)), wx_steps=[int(m.group(4)), int(m.group(5)), int(m.group(6))])
            continue
        m = RE_STAGE.search(s)
        if m:
            R(m.group(1)).update(region_index=int(m.group(2)), covers_at_build=int(m.group(3)))
    warn = [s for s in lines if "LogEcoPolicyV3I: Warning" in s or "LogEcoPolicyV3I: Error" in s]
    starts = [x.group(1) for x in (RE_START.search(s) for s in lines) if x]
    out = dict(log=Path(path).name, regions=regs, lines=len(lines), warnings=len(warn), warn_first=[w[w.find("LogEcoPolicyV3I"):][:240] for w in warn[:5]],
               brain_start=starts, brain_swaps=sum(1 for s in lines if "[EcoV3I] 두뇌 바꿈 |" in s),
               life_lines=txt.count("[EcoLife]"), vegetation_enabled=txt.count("[EcoVegetation] Enabled"),
               snapshot_rejected=txt.count("RL snapshot v1 rejected"), env_changes=sum(1 for s in lines if "환경 바뀜 #" in s),
               migration_lines=txt.count("[HerdMigration]"), migration_plans=len(set(re.findall(r"\[HerdMigration\] Plan=(\d+)", txt))),
               migration_settled=len(set(re.findall(r"\[HerdMigration\] Plan=(\d+) Herd=\d+ State=Settled", txt))),
               herd_migration_cvar=next((s.split("eco.HerdMigration = ")[1].strip().strip('"') for s in txt.splitlines() if "eco.HerdMigration = " in s),
                                        "맵 값"))
    missing = [reg for reg, r in regs.items() if "ep_chased" not in r or "live" not in r or "n" not in r]
    if missing or sorted(regs) != sorted(REGIONS):
        raise ValueError(f"{path}: 240 초 기록 줄이 빠진 지역 {missing} (지역 {sorted(regs)})")
    return out


LOG_SNAP_KEYS = ("n", "caught", "starved", "started", "live", "flee", "reflex", "ep_started", "ep_chased", "ep_hidden", "ep_watching", "ep_caught",
                 "ep_starved", "ep_truncated", "ep_joined")


def snap_record(R: dict) -> dict:
    """스냅숏 지역 → 기록 줄과 같은 열쇠 (r7e unreal_parity.record + 은신처 안 잡힘·은신처 스텝)."""
    rec = up().record(R["deer"]["adopted"], R["deer"]["caught"], R["deer"]["starved"], R["flight"])
    rec.update(caught_in_cover=int(R["deer"]["caught_in_cover"]), shelter_steps=int(R["deer"]["shelter_steps"]))
    return rec


def log_vs_snapshot(log: dict, snap: dict) -> list[str]:
    """같은 판의 기록 줄 지역 기록과 스냅숏 지역 기록이 다른 칸 (빈 목록 = 모두 같음)."""
    bad = []
    for R in snap["regions"]:
        a, b = log["regions"][R["region"]], snap_record(R)
        for k in LOG_SNAP_KEYS + ("caught_in_cover", "shelter_steps"):
            if a.get(k) != b.get(k):
                bad.append(f"{R['region']}.{k}: 기록 {a.get(k)} 스냅숏 {b.get(k)}")
    return bad


# --------------------------------------------------------------------- #
# 파이썬 거울 (r7e unreal_parity mirror 그대로 — 나무 없음 표, 이 폴더 runs/)
# --------------------------------------------------------------------- #


def cmd_mirror(a) -> int:
    RUNS.mkdir(parents=True, exist_ok=True)
    return up().cmd_mirror(argparse.Namespace(sessions=a.sessions, replicates=a.replicates, workers=a.workers, brains=a.brains))


# --------------------------------------------------------------------- #
# 스냅숏 → 거울 변환 (adapt.convert · 실시간 고리 변환 길)
# --------------------------------------------------------------------- #


def convert_one(path: Path) -> dict:
    """스냅숏 하나를 (가) 실시간 고리 변환 길(live.resolve_start → 묶음 바탕 설정·시작 모델 → adapt.convert)로, 지금 두뇌(R1b-F)면 (나) adapt.py convert
    기본 길(관측 18 거울)로도 바꿔 본다. 반환 = 길마다 {ok, refused | changed·checks·regions}."""
    import adapt as ad
    import live as lv

    snap = ad.load_snapshot(path)
    ref = json.loads(ad.REFERENCE.read_text(encoding="utf-8")) if ad.REFERENCE.exists() else None
    out = dict(snapshot=Path(path).name, brain=snap["brain"]["id"])

    def pack(c: dict) -> dict:
        regs = {k: dict(covers=v["covers"], discs=len(v["discs"]), weather=v["weather"], cap_total=v["cap_total"], python_cap_total=v["python_cap_total"],
                        cpp_rebuild_max_diff=v["cpp_rebuild_max_diff"], level_trees=v["level_trees"]) for k, v in c["regions"].items()}
        return dict(ok=True, changed=[f"{x['key']}: {json.dumps(x['template'], ensure_ascii=False)} → {json.dumps(x['snapshot'], ensure_ascii=False)}"
                                      for x in c["record"]["changed"]], checks=c["record"]["checks"], regions=regs, N=c["record"]["N"])

    try:
        start = lv.resolve_start(snap, lv.brain_folders(lv.DEFAULT_ROOT))
        prof = lv.profile_of(start["start_contract"])
        lv.check_snapshot_route(snap, prof)
        c = ad.convert(snap, ref, template=prof["template"], start=start["zip"], contract=start["start_contract"], recipe=prof["recipe"])
        out["live"] = dict(pack(c), profile=prof["name"], start=Path(start["zip"]).name)
    except ad.Refused as e:
        out["live"] = dict(ok=False, refused=str(e))
    if snap["brain"].get("builtin"):
        try:
            out["adapt"] = pack(ad.convert(snap, ref))
        except ad.Refused as e:
            out["adapt"] = dict(ok=False, refused=str(e))
    return out


def cmd_convert(a) -> int:
    d = Path(a.control)
    res = [convert_one(d / f"s{s}_{b}.json") for s in parse_sessions(a.sessions) for b in BRAIN_ARGS]
    bad = [(r["snapshot"], k, r[k]["refused"]) for r in res for k in ("live", "adapt") if k in r and not r[k]["ok"]]
    for r in res:
        print(r["snapshot"], {k: ("통과" if r[k]["ok"] else "거부") for k in ("live", "adapt") if k in r})
    if a.out:
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"거부 {len(bad)}" + "".join(f"\n  {x}" for x in bad))
    return 1 if bad else 0


# --------------------------------------------------------------------- #
# 비교
# --------------------------------------------------------------------- #

X_METRICS = (("사건 숨음 비율", "ep_hide", True, 2), ("사건 잡힘 비율", "ep_caught", True, 2), ("GF (1000 산 사슴-스텝당 도망 시작)", "gf", False, 3),
             ("GE (1000 산 사슴-스텝당 사건 시작)", "ge", False, 3), ("잡힌 몫 (사슴 가운데)", "caught_share", True, 2),
             ("굶은 몫 (사슴 가운데)", "starved_share", True, 2), ("은신처 안 사슴-스텝 몫", "shelter_share", True, 2),
             ("실행 FLEE 몫 (산 사슴-스텝)", "flee_share", True, 2))


def pool_x(recs: list) -> dict:
    """r7e unreal_parity.pool + 굶은 몫·은신처 몫·먹이·에너지 (기록 줄 지역 기록 — 스냅숏 기록도 같은 열쇠)."""
    m = up()
    out = m.pool(recs)
    s = out["sums"]
    out["starved_share"] = m.ratio(s.get("starved", 0), s["n"])
    out["shelter_share"] = m.ratio(s.get("shelter_steps", 0), s["live"]) if "shelter_steps" in s else float("nan")
    for k in ("food_pct", "energy_pct"):
        v = [r[k] for r in recs if r.get(k) is not None]
        out[k] = float(np.mean(v)) if v else float("nan")
    return out


def mode_summary(runs: dict, sessions: list) -> dict:
    """기록 줄 지역 기록 → 두뇌마다 모든 지역 셈 + 세션 셈 + 지역마다 셈."""
    out = {}
    for b in BRAIN_ARGS:
        units = {s: [runs[b][s]["regions"][r] for r in REGIONS] for s in sessions}
        out[b] = dict(all=pool_x([x for s in sessions for x in units[s]]), sessions={s: pool_x(units[s]) for s in sessions},
                      regions={reg: pool_x([runs[b][s]["regions"][reg] for s in sessions]) for reg in REGIONS})
    return out


def full_vs_control(ctl: dict, full: dict, sessions: list) -> dict:
    """언리얼만: 두뇌마다 전체 − 대조 (세션 짝 t — 같은 세션 시드), 두 모드에서 R7e − 지금 (세션 짝 t)."""
    m = up()
    res = {}
    for _, key, _, _ in X_METRICS:
        row = dict(control={b: ctl[b]["all"][key] for b in BRAIN_ARGS}, full={b: full[b]["all"][key] for b in BRAIN_ARGS})
        row["mode_pair"] = {b: m.paired({s: full[b]["sessions"][s][key] for s in sessions}, {s: ctl[b]["sessions"][s][key] for s in sessions})
                            for b in BRAIN_ARGS}
        row["brain_pair"] = {md: m.paired({s: d["r7e"]["sessions"][s][key] for s in sessions}, {s: d["cur"]["sessions"][s][key] for s in sessions})
                             for md, d in (("control", ctl), ("full", full))}
        res[key] = row
    return res


def load_mode(folder: Path, sessions: list, snapshots: bool) -> tuple[dict, list]:
    """폴더의 s<S>_<두뇌>.log → {두뇌: {세션: 기록}}, 확인 줄. snapshots 면 같은 판 스냅숏과 기록 줄을 견준다."""
    runs = {b: {} for b in BRAIN_ARGS}
    checks = []
    for s in sessions:
        for b in BRAIN_ARGS:
            lg = log_record(folder / f"s{s}_{b}.log")
            if snapshots:
                snap = json.loads((folder / f"s{s}_{b}.json").read_text(encoding="utf-8"))
                bad = log_vs_snapshot(lg, snap)
                checks.append(dict(ok=not bad, what=f"s{s}_{b}: 기록 줄 = 스냅숏 (지역마다 {len(LOG_SNAP_KEYS) + 2} 칸)" + (f" — 다름 {bad[:3]}" if bad else "")))
            runs[b][s] = lg
    return runs, checks


def run_facts(runs: dict, sessions: list) -> dict:
    """두뇌마다 판 확인 칸 합 (life 줄·식생 켬 줄·스냅숏 거부·환경 바뀜·이주 줄·경고·두뇌 시작/바꿈·무대 만들 때 은신처·은신처 안 잡힘·지형 막힘·240 초 날씨)."""
    out = {}
    for b in BRAIN_ARGS:
        rs = [runs[b][s] for s in sessions]
        regs = [x for r in rs for x in r["regions"].values()]
        out[b] = dict(runs=len(rs), life_lines=sum(r["life_lines"] for r in rs), vegetation_enabled=sum(r["vegetation_enabled"] for r in rs),
                      snapshot_rejected=sum(r["snapshot_rejected"] for r in rs), env_changes=sum(r["env_changes"] for r in rs),
                      migration_lines=sum(r["migration_lines"] for r in rs), migration_plans=sum(r["migration_plans"] for r in rs),
                      migration_settled=sum(r["migration_settled"] for r in rs), migration_runs=sum(1 for r in rs if r["migration_plans"]),
                      warnings=sum(r["warnings"] for r in rs),
                      warn_first=next((r["warn_first"] for r in rs if r["warn_first"]), []),
                      brain_start=sorted({x for r in rs for x in r["brain_start"]}), brain_swaps=sum(r["brain_swaps"] for r in rs),
                      herd_migration_cvar=sorted({str(r["herd_migration_cvar"]) for r in rs}),
                      covers_at_build={reg: sorted({r["regions"][reg].get("covers_at_build") for r in rs}) for reg in REGIONS},
                      caught_in_cover=sum(x.get("caught_in_cover", 0) for x in regs), terr_deer=sum(x["terr_deer"] for x in regs),
                      terr_wolf=sum(x["terr_wolf"] for x in regs), terr_moves=sum(x["terr_moves"] for x in regs),
                      weather_240={reg: sorted({f"{r['regions'][reg].get('weather')} {r['regions'][reg].get('weather_x')}" for r in rs}) for reg in REGIONS},
                      wx_steps={reg: np.sum([r["regions"][reg].get("wx_steps", [0, 0, 0]) for r in rs], axis=0).tolist() for reg in REGIONS})
    return out


def cmd_compare(a) -> int:
    m = up()
    sessions = parse_sessions(a.sessions)
    k = int(a.replicates)
    ctl_dir, full_dir = Path(a.control), Path(a.full)
    res = m.compare(ctl_dir, sessions, k)                     # 대조 모드 스냅숏 대 파이썬 거울 (r7e 셈·확인 그대로, 나무 없음 표)
    res["map"] = MAP
    res["modes"] = {mode: [y for x in unreal_cmd(mode, 0, "cur", Path("<폴더>"), "s<세션>_<두뇌>")[3:]
                           for y in (("-EcoV3Seed=<세션>", f"[-EcoV3Brain={R7E_BRAIN}]") if x == "-EcoV3Seed=0" else (x,))] for mode in MODES}
    ctl_runs, ctl_checks = load_mode(ctl_dir, sessions, snapshots=True)
    full_runs, _ = load_mode(full_dir, sessions, snapshots=False)
    res["log_vs_snapshot"] = ctl_checks
    ctl, full = mode_summary(ctl_runs, sessions), mode_summary(full_runs, sessions)
    res["control_log"] = ctl
    res["full_log"] = full
    res["facts"] = dict(control=run_facts(ctl_runs, sessions), full=run_facts(full_runs, sessions))
    res["full_vs_control"] = full_vs_control(ctl, full, sessions)
    res["variants"] = {}
    for vname, vlabel in VARIANTS:
        vdir = getattr(a, vname, None)
        if not vdir:
            continue
        vruns, _ = load_mode(Path(vdir), sessions, snapshots=False)
        vs = mode_summary(vruns, sessions)
        rows = {}
        for _, key, _, _ in X_METRICS:
            rows[key] = dict(value={b: vs[b]["all"][key] for b in BRAIN_ARGS},
                             vs_full={b: m.paired({s: vs[b]["sessions"][s][key] for s in sessions}, {s: full[b]["sessions"][s][key] for s in sessions})
                                      for b in BRAIN_ARGS},
                             brain_pair=m.paired({s: vs["r7e"]["sessions"][s][key] for s in sessions}, {s: vs["cur"]["sessions"][s][key] for s in sessions}))
        res["variants"][vname] = dict(label=vlabel, rows=rows, facts=run_facts(vruns, sessions),
                                      regions={b: {reg: {k2: vs[b]["regions"][reg][k2] for k2 in ("ep_hide", "ep_caught", "caught_share", "food_pct", "energy_pct")}
                                                     for reg in REGIONS} for b in BRAIN_ARGS})
    G = res["groups"]["모든 지역"]["sums"]
    res["python_extra"] = {b: dict(starved_share=m.ratio(G["python"][b]["starved"], G["python"][b]["n"]),
                                   unreal_starved_share=m.ratio(G["unreal"][b]["starved"], G["unreal"][b]["n"])) for b in BRAIN_ARGS}
    rr = []
    for p in sorted(full_dir.glob("s*_*_b.log")):
        s, b = int(p.stem[1:].split("_")[0]), p.stem.split("_")[1]
        if s in full_runs[b]:
            x = log_record(p)
            diff = {reg: {kk: (full_runs[b][s]["regions"][reg].get(kk), x["regions"][reg].get(kk)) for kk in LOG_SNAP_KEYS
                          if full_runs[b][s]["regions"][reg].get(kk) != x["regions"][reg].get(kk)} for reg in REGIONS}
            rr.append(dict(name=p.stem, against=f"s{s}_{b}", same=not any(diff.values()), diff={r: v for r, v in diff.items() if v}))
    res["full_rerun"] = rr
    res["checks_ok"] = bool(res["checks_ok"]) and all(c["ok"] for c in ctl_checks)
    out = Path(a.out)
    out.with_suffix(".json").write_text(json.dumps(m._jsonable(res), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    write_md(out.with_suffix(".md"), res)
    Gm = res["groups"]["모든 지역"]
    for name, key, pct, nd in m.METRICS[:5]:
        row = Gm[key]
        print(f"{name}: 언리얼 {m._f(row['unreal']['cur'], pct, nd)} → {m._f(row['unreal']['r7e'], pct, nd)} · 파이썬 {m._f(row['python']['cur'], pct, nd)} → "
              f"{m._f(row['python']['r7e'], pct, nd)} · 크기 z {m._t(row.get('diff_z'))}")
    print("확인 모두 통과" if res["checks_ok"] else "확인 어긋남 있음 — md 머리 확인")
    return 0 if res["checks_ok"] else 1


# --------------------------------------------------------------------- #
# 표
# --------------------------------------------------------------------- #


def write_md(path: Path, res: dict) -> None:
    m = up()
    _f, _d, _t = m._f, m._d, m._t
    S, k = res["sessions"], res["replicates"]
    B = m.BRAINS
    G = res["groups"]["모든 지역"]
    FV = res["full_vs_control"]
    L = ["# 팀 생태계 맵 복사본에서 우리 시험 — 언리얼 대조·전체 모드 대 파이썬 거울 (자동 생성 — results/v3/level_jyu_eco/level_jyu_eco.py)", ""]
    L += ["## 요약 (자동)", ""]
    for name, key, pct, nd in m.METRICS[:5]:
        r = G[key]
        L.append(f"- 대조 모드 {name}: 언리얼 {_f(r['unreal']['cur'], pct, nd)} → {_f(r['unreal']['r7e'], pct, nd)} ({_d(r['unreal_diff'], pct, nd)}, 세션 짝 t "
                 f"{_t(r['unreal_pair']['t'])}), 파이썬 거울 {_f(r['python']['cur'], pct, nd)} → {_f(r['python']['r7e'], pct, nd)} "
                 f"({_d(r['python']['r7e'] - r['python']['cur'], pct, nd)}, 짝 t {_t(r['python_pair']['t'])}) — 같은 방향: {r['direction']}, 크기 z {_t(r['diff_z'])}.")
    for name, key, pct, nd in X_METRICS[:2]:
        r = FV[key]
        bp = r["brain_pair"]["full"]
        L.append(f"- 전체 모드(언리얼만) {name}: 지금 {_f(r['full']['cur'], pct, nd)} → R7e {_f(r['full']['r7e'], pct, nd)} ({_d(bp['diff'], pct, nd)}, 세션 짝 t "
                 f"{_t(bp['t'])}) — 대조 모드 두뇌 차이 {_d(r['brain_pair']['control']['diff'], pct, nd)} (t {_t(r['brain_pair']['control']['t'])}).")
    L.append("- '같은 방향' = 파이썬 차이가 짝 t 문턱(양측 5%) 밖일 때 언리얼 차이 부호가 같은가 (언리얼 짝 t 가 문턱 안이면 '언리얼은 0 근처'). 파이썬 차이가 문턱 "
             "안이면 '파이썬 0 근처'(견줄 방향 없음). 크기 z = (언리얼 차이 − 파이썬 반복 차이 평균) ÷ 파이썬 반복 차이 표준편차 (반복 하나 = 언리얼과 같은 세션 수의 "
             "파이썬 세계) — |z| < 2 면 파이썬 반복 폭 안. 전체 모드는 파이썬과 견주지 않는다(판정 아님 — 언리얼끼리 차이만).")
    L += ["", "## 조건", ""]
    L.append(f"- 맵 `{res['map']}` (조연우 `LV_JYU_Ecosystem` 의 우리 복사본 — 레벨 설정 그대로). 세션 {S[0]}~{S[-1]}({len(S)} 개 × 지역 셋), 지역마다 사슴 "
             f"{m.DEER}·늑대 {m.WOLVES}, 240 초(전역 스텝 {m.STEPS}), 헤드리스 `-benchmark -fps=30 -NullRHI`. 두 두뇌 같은 세션 시드.")
    for mode, label in (("control", "대조 모드"), ("full", "전체 모드")):
        L.append(f"- {label} 인수: `{' '.join(x if ' ' not in x else chr(34) + x + chr(34) for x in res['modes'][mode])}`")
    L.append("  - 대조 모드는 팀 life·환경 감시(팀 비 순환을 v3 날씨로)·무리 이주·식생 soil-v1 을 끈다. 식생은 끄는 인수가 없어서 엔진 콘솔 명령 `setnopec` 으로 이 Play 의 "
             "조정자 값만 끈다(맵 파일·C++ 그대로). 240 초 스냅숏이 써진 것이 식생·life 를 끈 확인이다(켜져 있으면 스냅숏이 거부된다).")
    L.append("  - 전체 모드는 맵에 저장된 그대로다. 스냅숏이 거부되므로 쓰지 않고 기록 240 초 줄에서 같은 지표를 읽는다(대조 모드에서 기록 줄 = 스냅숏 확인).")
    L.append(f"- 파이썬: `results/v3/mirror/run_mirror.py` 짝 비교 — 같은 지역 먹이 지도(C++ 난수)·원판 0(이 맵에 나무 없음, `no_trees.json`)·지역 시작 날씨"
             f"(Forest 비 1 · Barren 맑음 · Highland 눈 1)·은신처 넷, 지도마다 반복 {k}(두 두뇌 같은 시드 {res['python_meta']['cur']['seeds'][0]}~ 탐색 범위), 1800 스텝.")
    L.append(f"- 두뇌: 지금 = {B['cur']['label']} (`{B['cur']['unreal_id']}`, 파이썬 `{B['cur']['model']}` · `{B['cur']['config']}`), R7e = "
             f"`{B['r7e']['unreal_id']}` (언리얼 `-EcoV3Brain={R7E_BRAIN}`, 파이썬 `{B['r7e']['model']}` · `{B['r7e']['config']}`).")
    L.append("- 셈: `results/v3/r7e/unreal_parity.py` 그대로(몫은 전체 합의 비, 짝 t 는 언리얼 세션 단위·파이썬 (세션, 반복) 단위) — 판정이 아니라 방향 보기다.")
    nfail = sum(len(r["checks_failed"]) for r in res["unreal_runs"])
    ncheck = sum(r["checks"] for r in res["unreal_runs"])
    nlv = sum(1 for c in res["log_vs_snapshot"] if c["ok"])
    L.append(f"- 확인(대조 모드): 언리얼 판 {len(res['unreal_runs'])} 개 확인 {ncheck} 칸 가운데 어긋남 {nfail} (스냅숏 스텝·두뇌 id·관측·판·두 길·막음·R7e 가중치 "
             "sha256·설정 = 거울 칸·지역 날씨 = 거울 표·원판 0 = 나무 없음 표·은신처 넷 = 거울 자리·240 초 기록 줄 사건 칸 = 스냅숏·두뇌 시작 줄·두뇌 바꿈 0·EcoV3I "
             f"경고/오류 0) · 기록 줄 지역 기록 = 스냅숏 {nlv}/{len(res['log_vs_snapshot'])} 판"
             + "".join(f" · 같은 시드 다시 돌림 {x['name']} 대 {x['against']}: {'지역 기록 모두 같음' if x['same'] else '다름'}" for x in res["rerun"]))
    for r in res["unreal_runs"]:
        for cc in r["checks_failed"]:
            L.append(f"  - {r['name']}: {cc['what']}")
    for c in res["log_vs_snapshot"]:
        if not c["ok"]:
            L.append(f"  - {c['what']}")
    L += ["", "## 1. 대조 모드 두뇌 차이 (R7e − 지금) — 모든 지역", ""]
    L.append("| 칸 | 언리얼 지금 | 언리얼 R7e | 언리얼 차이 (세션 짝 t) | 파이썬 지금 | 파이썬 R7e | 파이썬 차이 (짝 t) | 파이썬 반복 차이 [최소..최대] | 같은 방향 | 크기 z |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for name, key, pct, nd in m.METRICS + m.ROUTE_ROWS:
        row = G[key]
        u, p = row["unreal"], row["python"]
        if "unreal_pair" in row:
            up_, pp, rd = row["unreal_pair"], row["python_pair"], row["python_rep_diff"]
            L.append(f"| {name} | {_f(u['cur'], pct, nd)} | {_f(u['r7e'], pct, nd)} | {_d(row['unreal_diff'], pct, nd)} ({_t(up_['t'])}, n {up_['n']}) | "
                     f"{_f(p['cur'], pct, nd)} | {_f(p['r7e'], pct, nd)} | {_d(p['r7e'] - p['cur'], pct, nd)} ({_t(pp['t'])}, n {pp['n']}) | "
                     f"{_d(rd['mean'], pct, nd)} [{_d(rd['min'], pct, nd)}..{_d(rd['max'], pct, nd)}] | {row['direction']} | {_t(row['diff_z'])} |")
        else:
            lv = row["level"].get("r7e")
            zz = f" (반복 [{_f(lv['min'], pct, nd)}..{_f(lv['max'], pct, nd)}], z {_t(lv['z'])})" if lv else ""
            L.append(f"| {name} (R7e 만) | {_f(u['cur'], pct, nd)} | {_f(u['r7e'], pct, nd)} | — | {_f(p['cur'], pct, nd)} | {_f(p['r7e'], pct, nd)}{zz} | — | — | — | — |")
    su, sp = G["sums"]["unreal"], G["sums"]["python"]
    L.append("")
    L.append(f"- 쫓긴 사건 수: 언리얼 지금 {su['cur']['ep_chased']} · R7e {su['r7e']['ep_chased']} (세션 {len(S)}) / 파이썬 지금 {sp['cur']['ep_chased']} · "
             f"R7e {sp['r7e']['ep_chased']} (세션 {len(S)} × 반복 {k})")
    L.append(f"- 반사 밖 두뇌 FLEE 스텝(실행 FLEE − 반사): 언리얼 지금 {su['cur']['flee'] - su['cur']['reflex']} · R7e {su['r7e']['flee'] - su['r7e']['reflex']} / "
             f"파이썬 지금 {sp['cur']['flee'] - sp['cur']['reflex']} · R7e {sp['r7e']['flee'] - sp['r7e']['reflex']} (판 5 는 반사 밖 FLEE 를 막는다 — R7e 는 0 이어야 한다)")
    if "rt_run" in su["r7e"]:
        L.append(f"- R7e 길 고름(적용된 길 결정): 언리얼 RUN {su['r7e']['pk_run']} · SHELTER {su['r7e']['pk_shelter']} / 파이썬 RUN {sp['r7e']['pk_run']} · "
                 f"SHELTER {sp['r7e']['pk_shelter']}")
    L += ["", "## 2. 대조 모드 두뇌마다 값 — 언리얼 대 파이썬 반복", ""]
    L.append("| 칸 | 두뇌 | 언리얼 | 파이썬 반복 평균 [최소..최대] | z |")
    L.append("|---|---|---|---|---|")
    for name, key, pct, nd in m.METRICS[:5] + m.ROUTE_ROWS[:1]:
        for b in B:
            lv = G[key]["level"].get(b)
            if lv:
                L.append(f"| {name} | {B[b]['label']} | {_f(G[key]['unreal'][b], pct, nd)} | {_f(lv['mean'], pct, nd)} [{_f(lv['min'], pct, nd)}.."
                         f"{_f(lv['max'], pct, nd)}] | {_t(lv['z'])} |")
    PX = res["python_extra"]
    for b in B:
        L.append(f"| 굶은 몫 (사슴 가운데) | {B[b]['label']} | {_f(PX[b]['unreal_starved_share'], True, 2)} | {_f(PX[b]['starved_share'], True, 2)} (반복 전체 합) | — |")
    L += ["", "## 3. 대조 모드 지역마다 (R7e − 지금)", ""]
    L.append("| 지역 | 칸 | 언리얼 지금 → R7e (차이, 세션 짝 t) | 파이썬 지금 → R7e (차이, 짝 t) | 같은 방향 | 크기 z |")
    L.append("|---|---|---|---|---|---|")
    for reg in REGIONS:
        g = res["groups"][reg]
        for name, key, pct, nd in m.METRICS[:3]:
            row = g[key]
            u, p = row["unreal"], row["python"]
            L.append(f"| {reg} | {name} | {_f(u['cur'], pct, nd)} → {_f(u['r7e'], pct, nd)} ({_d(row['unreal_diff'], pct, nd)}, {_t(row['unreal_pair']['t'])}) | "
                     f"{_f(p['cur'], pct, nd)} → {_f(p['r7e'], pct, nd)} ({_d(p['r7e'] - p['cur'], pct, nd)}, {_t(row['python_pair']['t'])}) | {row['direction']} | "
                     f"{_t(row['diff_z'])} |")
        su_, sp_ = g["sums"]["unreal"], g["sums"]["python"]
        L.append(f"| {reg} | 쫓긴 사건 수 (지금 · R7e) | {su_['cur']['ep_chased']} · {su_['r7e']['ep_chased']} | {sp_['cur']['ep_chased']} · {sp_['r7e']['ep_chased']} | | |")
    L += ["", "## 4. 대조 모드 언리얼 세션마다 (지역 셋 합)", ""]
    L.append("| 세션 | 쫓긴 사건 (지금 · R7e) | 사건 숨음 비율 지금 → R7e | 사건 잡힘 비율 지금 → R7e | GF 지금 → R7e |")
    L.append("|---|---|---|---|---|")
    us = G["unreal_sessions"]
    for s in S:
        a_, b_ = us["cur"][s], us["r7e"][s]
        L.append(f"| {s} | {a_['chased']} · {b_['chased']} | {_f(a_['ep_hide'], True, 1)} → {_f(b_['ep_hide'], True, 1)} | {_f(a_['ep_caught'], True, 1)} → "
                 f"{_f(b_['ep_caught'], True, 1)} | {_f(a_['gf'], False, 3)} → {_f(b_['gf'], False, 3)} |")
    L += ["", "## 5. 전체 모드 대 대조 모드 (언리얼만 — 판정 아님)", ""]
    L.append("같은 세션 시드끼리 짝을 지었다. 전체 모드는 팀 날씨 감시가 실제 시간으로 돌아 같은 시드도 판마다 조금 다르다(아래 7절 다시 돌림).")
    L.append("")
    L.append("| 칸 | 지금: 대조 → 전체 (차이, 세션 짝 t) | R7e: 대조 → 전체 (차이, 세션 짝 t) | 두뇌 차이 R7e − 지금: 대조 (t) | 두뇌 차이: 전체 (t) |")
    L.append("|---|---|---|---|---|")
    for name, key, pct, nd in X_METRICS:
        r = FV[key]
        cells = []
        for b in B:
            mp = r["mode_pair"][b]
            cells.append(f"{_f(r['control'][b], pct, nd)} → {_f(r['full'][b], pct, nd)} ({_d(mp['diff'], pct, nd)}, {_t(mp['t'])})")
        bc, bf = r["brain_pair"]["control"], r["brain_pair"]["full"]
        L.append(f"| {name} | {cells[0]} | {cells[1]} | {_d(bc['diff'], pct, nd)} ({_t(bc['t'])}) | {_d(bf['diff'], pct, nd)} ({_t(bf['t'])}) |")
    L.append("")
    L.append("- 차이 칸은 세션마다 낸 몫의 짝 차이 평균이라, 모든 세션 합으로 낸 앞 두 칸의 차와 조금 다를 수 있다.")
    L += ["", "### 지역마다 (기록 줄, 모든 세션 합)", ""]
    L.append("| 지역 | 두뇌 | 모드 | 쫓긴 사건 | 사건 숨음 비율 | 사건 잡힘 비율 | GF | 잡힌 몫 | 굶은 몫 | 240 초 무대 먹이 (처음의 %) | 240 초 사슴 에너지 평균 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for reg in REGIONS:
        for b in B:
            for md, lab in (("control_log", "대조"), ("full_log", "전체")):
                x = res[md][b]["regions"][reg]
                L.append(f"| {reg} | {B[b]['label']} | {lab} | {x['sums']['ep_chased']} | {_f(x['ep_hide'], True, 2)} | {_f(x['ep_caught'], True, 2)} | "
                         f"{_f(x['gf'], False, 3)} | {_f(x['caught_share'], True, 2)} | {_f(x['starved_share'], True, 2)} | {_f(x['food_pct'], False, 1)} | "
                         f"{_f(x['energy_pct'], False, 1)}% |")
    if res.get("variants"):
        L += ["", "### 전체 모드에서 팀 기능 하나씩만 끈 판 (언리얼만 — 차이가 어디서 오나, 판정 아님)", ""]
        L.append("값 = 모든 세션 합 (지금 · R7e). 괄호 = 전체 모드와의 세션 짝 차이(t). 전체 모드 자체가 판마다 흔들리므로(7절) 작은 차이는 그 흔들림일 수 있다.")
        L.append("")
        L.append("| 판 | " + " | ".join(f"{name}" for name, _, _, _ in X_METRICS[:5]) + " |")
        L.append("|---|" + "---|" * 5)

        def cell(v, b, pct, nd, pair=None):
            return _f(v[b], pct, nd) + (f" ({_d(pair['diff'], pct, nd)}, {_t(pair['t'])})" if pair else "")

        L.append("| 대조 모드 (넷 모두 끔) | " + " | ".join(f"{_f(FV[key]['control']['cur'], pct, nd)} · {_f(FV[key]['control']['r7e'], pct, nd)}"
                                                       for _, key, pct, nd in X_METRICS[:5]) + " |")
        L.append("| 전체 모드 (넷 모두 켬) | " + " | ".join(f"{_f(FV[key]['full']['cur'], pct, nd)} · {_f(FV[key]['full']['r7e'], pct, nd)}"
                                                       for _, key, pct, nd in X_METRICS[:5]) + " |")
        for vname, v in res["variants"].items():
            L.append(f"| 전체 − {v['label']} | " + " | ".join(
                cell(v["rows"][key]["value"], "cur", pct, nd, v["rows"][key]["vs_full"]["cur"]) + " · "
                + cell(v["rows"][key]["value"], "r7e", pct, nd, v["rows"][key]["vs_full"]["r7e"])
                for _, key, pct, nd in X_METRICS[:5]) + " |")
        L.append("")
        L.append("| 판 | 두뇌 차이 R7e − 지금: 사건 숨음 비율 (t) | 사건 잡힘 비율 (t) | GF (t) | Highland 240 초 먹이 (처음의 %) 지금 · R7e | Highland 잡힌 몫 지금 · R7e |")
        L.append("|---|---|---|---|---|---|")

        def brow(label, hide, caught, gf, reg):
            return (f"| {label} | {_d(hide['diff'], True, 2)} ({_t(hide['t'])}) | {_d(caught['diff'], True, 2)} ({_t(caught['t'])}) | "
                    f"{_d(gf['diff'], False, 3)} ({_t(gf['t'])}) | {_f(reg['cur']['food_pct'], False, 1)} · {_f(reg['r7e']['food_pct'], False, 1)} | "
                    f"{_f(reg['cur']['caught_share'], True, 2)} · {_f(reg['r7e']['caught_share'], True, 2)} |")

        for md, lab in (("control", "대조 모드"), ("full", "전체 모드")):
            src = res[f"{md}_log"]
            L.append(brow(lab, FV["ep_hide"]["brain_pair"][md], FV["ep_caught"]["brain_pair"][md], FV["gf"]["brain_pair"][md],
                          {b: src[b]["regions"]["Highland"] for b in BRAIN_ARGS}))
        for vname, v in res["variants"].items():
            r = v["rows"]
            L.append(brow(f"전체 − {v['label']}", r["ep_hide"]["brain_pair"], r["ep_caught"]["brain_pair"], r["gf"]["brain_pair"],
                          {b: v["regions"][b]["Highland"] for b in BRAIN_ARGS}))
    L += ["", "## 6. 그 밖의 칸 — 끼임·은신처 안 잡힘·경고·모드 확인 (언리얼 기록 줄, 두뇌마다 판 합)", ""]
    F = res["facts"]
    L.append("| 칸 | 대조 지금 | 대조 R7e | 전체 지금 | 전체 R7e |")
    L.append("|---|---|---|---|---|")
    rows = (("판 수", "runs"), ("은신처 안 잡힘 (누적 합)", "caught_in_cover"), ("끼임: 지형 막힘 사슴 (10 초 구간 합)", "terr_deer"),
            ("끼임: 지형 막힘 늑대", "terr_wolf"), ("지형 검사 이동 (합)", "terr_moves"), ("EcoV3I 경고·오류 줄", "warnings"), ("두뇌 바꿈 줄", "brain_swaps"),
            ("[EcoLife] 줄 (팀 life)", "life_lines"), ("[EcoVegetation] 켬 줄 (지역마다 하나)", "vegetation_enabled"), ("환경 바뀜 줄", "env_changes"),
            ("무리 이주 [HerdMigration] 줄", "migration_lines"), ("무리 이주 계획 수 (Plan)", "migration_plans"),
            ("무리 이주 도착한 계획 (Settled)", "migration_settled"), ("이주 계획이 있던 판", "migration_runs"))
    for lab, key in rows:
        L.append(f"| {lab} | {F['control']['cur'][key]} | {F['control']['r7e'][key]} | {F['full']['cur'][key]} | {F['full']['r7e'][key]} |")
    L.append(f"| eco.HerdMigration 값 | {F['control']['cur']['herd_migration_cvar']} | {F['control']['r7e']['herd_migration_cvar']} | "
             f"{F['full']['cur']['herd_migration_cvar']} | {F['full']['r7e']['herd_migration_cvar']} |")
    L.append(f"| 두뇌 시작 줄 | {F['control']['cur']['brain_start']} | {F['control']['r7e']['brain_start']} | {F['full']['cur']['brain_start']} | "
             f"{F['full']['r7e']['brain_start']} |")
    for reg in REGIONS:
        L.append(f"| 무대 만들 때 은신처 {reg} | {F['control']['cur']['covers_at_build'][reg]} | {F['control']['r7e']['covers_at_build'][reg]} | "
                 f"{F['full']['cur']['covers_at_build'][reg]} | {F['full']['r7e']['covers_at_build'][reg]} |")
    for reg in REGIONS:
        L.append(f"| 날씨 스텝 맑음·비·눈 {reg} (판 합) | {F['control']['cur']['wx_steps'][reg]} | {F['control']['r7e']['wx_steps'][reg]} | "
                 f"{F['full']['cur']['wx_steps'][reg]} | {F['full']['r7e']['wx_steps'][reg]} |")
    for md in ("control", "full"):
        for b in B:
            if F[md][b]["warn_first"]:
                L.append(f"- {md} {b} 첫 경고: `{F[md][b]['warn_first'][0]}`")
    L += ["", "## 7. 전체 모드 같은 시드 다시 돌림", ""]
    if res.get("full_rerun"):
        for x in res["full_rerun"]:
            L.append(f"- {x['name']} 대 {x['against']}: " + ("지역 기록 모두 같음" if x["same"] else
                                                          "다름 — " + "; ".join(f"{reg} " + ", ".join(f"{kk} {v[0]}→{v[1]}" for kk, v in d.items())
                                                                                for reg, d in x["diff"].items())))
    else:
        L.append("- 없음")
    path.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="팀 생태계 맵 복사본에서 우리 시험 (모듈 docstring)")
    sp = p.add_subparsers(dest="cmd", required=True)
    u = sp.add_parser("unreal", help="언리얼 헤드리스 판 (모드·세션·두뇌)")
    u.add_argument("--mode", choices=list(MODES), required=True)
    u.add_argument("--sessions", required=True)
    u.add_argument("--brains", nargs="+", default=list(BRAIN_ARGS), choices=list(BRAIN_ARGS))
    u.add_argument("--out", required=True)
    u.add_argument("--rerun", default=None, help="같은 시드 다시 돌림 (이름 s<S>_<두뇌>_b)")
    u.add_argument("--parallel", type=int, default=5)
    u.add_argument("--extra", nargs="*", default=[], help="더 넣을 언리얼 인수 (진단용)")
    u.add_argument("--skip-existing", action="store_true")
    mm = sp.add_parser("mirror", help="파이썬 거울 (두 두뇌, 언리얼 세션의 지도, 원판 0)")
    mm.add_argument("--sessions", required=True)
    mm.add_argument("--replicates", type=int, default=10)
    mm.add_argument("--workers", type=int, default=None)
    mm.add_argument("--brains", nargs="*", default=list(BRAIN_ARGS))
    cv = sp.add_parser("convert", help="대조 모드 스냅숏 → 거울 변환 (실시간 고리 길·adapt 기본 길)")
    cv.add_argument("--control", required=True)
    cv.add_argument("--sessions", required=True)
    cv.add_argument("--out", default=None)
    c = sp.add_parser("compare", help="대조 모드 대 파이썬 거울 + 전체 모드 대 대조 모드")
    c.add_argument("--control", required=True)
    c.add_argument("--full", required=True)
    c.add_argument("--sessions", required=True)
    c.add_argument("--replicates", type=int, default=10)
    c.add_argument("--out", required=True)
    for vname, vlabel in VARIANTS:
        c.add_argument(f"--{vname.replace('_', '-')}", dest=vname, default=None, help=f"전체 모드에서 {vlabel} 판 폴더 (선택)")
    a = p.parse_args(argv)
    return {"unreal": cmd_unreal, "mirror": cmd_mirror, "convert": cmd_convert, "compare": cmd_compare}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())

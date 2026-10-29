"""R7e 두 길 두뇌(관측 24·마스크 판 5) — 언리얼 통합 v3 단독 실행 대 파이썬 거울 (10-24, R5 `results/v3/r5/unreal_parity.py` 꼴).

    # herbivore_rl/ 에서 (PYTHONUTF8=1). 언리얼 기록을 먼저 만든다 — 아래 '기록 만들기'
    python results/v3/r7e/unreal_parity.py mirror --sessions 20010-20019 --replicates 10          # 파이썬 거울 두 두뇌 → runs/parity_*.json (git 밖)
    python results/v3/r7e/unreal_parity.py compare --unreal <스냅숏·기록 폴더> --sessions 20010-20019 --replicates 10 --out results/v3/r7e/unreal_parity

R7e 판정(`judge.md` — 파이썬 판 5 거울 N 세계)을 통과한 두뇌 v3_r7_g995_s1_20m 을 언리얼 통합 v3 게임에 처음부터 건 판과, 게임 기본 두뇌(내장 R1b-F) 판을
같은 세션 시드로 돌려 쫓김 사건 셈(사건 숨음·잡힘 비율)·GF·GE·잡힌 몫을 모으고, 파이썬 거울에서 같은 조건(같은 지역 먹이 지도·나무 원판·지역 날씨·사슴 128·늑대 4·
늑대 포만 켬 — 게임 기본값)으로 돌린 값과 견준다. 언리얼은 판 수가 적다(세션 하나 = 지역 무대 셋). 그래서 판정이 아니라 '같은 방향·같은 크기 근처'인지만 본다.

두뇌 (BRAINS):
  cur = 게임 기본 두뇌 내장 R1b-F(관측 18·판 2, 통합 모드가 얼기를 막는다). 파이썬 = ckpt/v3/v3_r1_g995_s3_20m.zip · configs/v3_wild3_mirror.yaml
        (R7e 판정의 route0 과 같은 행동이다 — route0 = 같은 가중치 + 0 칸, 길 켬 + 늘 RUN 은 끈 세계와 궤적이 같다. tests/test_route2_v3.py·Route.ZeroIdentity)
  r7e = v3_r7_g995_s1_20m(관측 24·판 5 — 두 길 + 반사 밖 두뇌 FLEE 막음). 언리얼은 -EcoV3Brain= 로 첫 결정 스텝부터 건다. 파이썬 =
        ckpt/v3/v3_r7_g995_s1_20m.zip · configs/v3_wild3_route5_mirror.yaml(판 5 거울 — 두 길·막음은 두뇌가 정하는 게임과 같은 세계)
언리얼 값: 판마다 -EcoV3SnapshotAt=240 스냅숏(전역 스텝 1800)의 지역 flight(파이썬 world.py flight_stats 와 같은 이름·정의 — 지금 열린 도망·사건은 잘림·
  지켜본 만큼)·deer(입양·잡힘·굶음). 기록(-abslog)에서는 10 초 줄 '[EcoV3I] <지역> 도망 | 240.0초' 의 쫓긴 사건 칸이 스냅숏과 같은지, 두뇌 시작 줄·
  두뇌 바꿈·EcoV3I 경고/오류 줄 수를 본다.
파이썬 값: results/v3/mirror/run_mirror.run(짝 비교 — 언리얼 세션 시드의 지역 먹이 지도를 C++ 난수로 다시 만들고, 원판 = 나무 배치 표
  results/v3/wild2/trees/tree_layout.json, 지역 날씨 = 설정 표) 지도마다 replicates 개(시드는 탐색 범위 32000~32099·33000~33099·33100~33199 의 앞에서부터,
  두 두뇌 같은 시드 — 짝). 1800 스텝 뒤 flight_stats.
셈 (두 쪽 같은 셈 — 몫은 전체 합의 비, 판정의 시드 평균과 셈이 다르다):
  사건 숨음 비율 = Σ숨음 사건 ÷ Σ쫓긴 사건, 사건 잡힘 비율 = Σ잡힘 사건 ÷ Σ쫓긴 사건 (LIVE_GATE 5-1 '쫓김 사건' — 1차 P1·GH 의 몫)
  GF = 1000 × Σ시작한 도망 ÷ Σ산 사슴-스텝, GE = 1000 × Σ시작한 쫓김 사건 ÷ Σ산 사슴-스텝, 잡힌 몫 = Σ잡힌 사슴 ÷ Σ처음 사슴
  반사 밖 두뇌 FLEE 몫 = (Σ실행 FLEE 스텝 − Σ반사 스텝) ÷ Σ산 사슴-스텝 (판 5 두뇌는 0 이어야 한다), SHELTER 길 몫 = 반사 길 스텝 가운데 SHELTER (길 기록 판만)
짝: 언리얼은 세션(지역 셋 합)마다 r7e − cur, 짝 t(세션 수). 파이썬은 (세션, 반복)마다 같은 셈, 짝 t. 크기 비교: 파이썬 반복 j 마다 언리얼과 같은 세션 수를
  모은 값(반복 수만큼)의 평균 [최소..최대]·표준편차, z = (언리얼 − 파이썬 평균) ÷ 파이썬 반복 표준편차 (wild3/compare_weather.py 와 같은 꼴).

기록 만들기 (편집기를 닫고, 빌드한 뒤 — 기본값 = 레벨 나무 + 날씨 + 늑대 포만, 지역마다 사슴 128·늑대 4, 241 초):
    UnrealEditor-Cmd.exe <uproject> /Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3 -EcoV3DeerPerRegion=128 -EcoV3Seed=<S>
        [-EcoV3Brain=v3_r7_g995_s1_20m] -EcoV3SnapshotAt=240 -EcoV3SnapshotOut=<폴더>/s<S>_<cur|r7e>.json
        -benchmark -fps=30 -seconds=241 -NullRHI -NoSound -unattended -nosplash -nopause -DisablePlugins=Bridge,Fab -abslog=<폴더>/s<S>_<cur|r7e>.log
    Git Bash 면 MSYS_NO_PATHCONV=1 (안 주면 /Game/... 가 윈도 경로로 바뀌어 지도를 못 연다). 같은 시드 다시 돌림은 s<S>_r7e_b 로 두면 견준다.
    10-29 부터 두뇌 인수가 없으면 기본 두뇌 R7e 다 — cur(내장 R1b-F) 판은 -EcoV3Brain=builtin 을 붙인다 (LIVE_ADAPT_SPEC.md 5.6).
출력: <out>.json (판마다 지역 칸·확인·셈), <out>.md (표).
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                                  # herbivore_rl/
for _p in (ROOT, ROOT / "results" / "v3" / "mirror"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import numpy as np  # noqa: E402

RUNS = HERE.parent / "runs"                             # git 밖 (herbivore_rl/.gitignore runs/)
LAYOUT = ROOT / "results" / "v3" / "wild2" / "trees" / "tree_layout.json"
BRAIN_FILE = HERE.parent / "brains" / "v3_r7_g995_s1_20m.json"
SEED_TEXT = "32000-32099,33000-33099,33100-33199"       # run_mirror 탐색 범위 (판정 시드 38000~ 는 쓰지 않는다)
REGIONS = ("Barren", "Forest", "Highland")
STEPS = 1800                                            # 240 초 = 스냅숏 전역 스텝
DEER, EAT_STEPS, WOLVES = 128, 38, 4                    # 게임 기본값 (스냅숏 settings 로 확인)
COVERS = sorted([[15, 15, 6], [45, 15, 6], [15, 45, 6], [45, 45, 6]])   # 거울 integrated_stage quad (반경 = 0.1 × 60)
JUDGE_G = ("18.51%", "10.10%", "11.11%", "12.25%")      # 참고: judge.md G 세계(포만 켬, 480 초, 판정 시드 38000~38039) 사건 숨음·잡힘 비율 R7 · route0

BRAINS = {
    "cur": dict(label="내장 R1b-F", unreal_id="v3_r1_g995_s3_20m@eca97f2e", builtin=True, obs=18, mask=2, route=False, gate=False,
                model="ckpt/v3/v3_r1_g995_s3_20m.zip", config="configs/v3_wild3_mirror.yaml"),
    "r7e": dict(label="R7e 두 길·판 5", unreal_id="v3_r7_g995_s1_20m@40d8710d", builtin=False, obs=24, mask=5, route=True, gate=True,
                model="ckpt/v3/v3_r7_g995_s1_20m.zip", config="configs/v3_wild3_route5_mirror.yaml"),
}
EP_KEYS = ("started", "chased", "hidden", "caught", "starved", "other", "truncated", "watching", "joined")
# 표의 칸: (이름, 셈 열쇠, 몫이면 100 곱함, 소수 자리)
METRICS = (("사건 숨음 비율", "ep_hide", True, 2), ("사건 잡힘 비율", "ep_caught", True, 2), ("GF (1000 산 사슴-스텝당 도망 시작)", "gf", False, 3),
           ("GE (1000 산 사슴-스텝당 사건 시작)", "ge", False, 3), ("잡힌 몫 (사슴 가운데)", "caught_share", True, 2),
           ("반사 밖 두뇌 FLEE 몫 (산 사슴-스텝)", "self_flee", True, 3), ("실행 FLEE 몫 (산 사슴-스텝)", "flee_share", True, 2))
ROUTE_ROWS = (("길 결정 가운데 SHELTER 고름 (적용된 결정)", "picked_shelter", True, 1), ("반사 길 스텝 가운데 SHELTER", "shelter_route", True, 1))
RE_FLIGHT240 = re.compile(r"\[EcoV3I\] (\S+) 도망 \| 240\.0초 \|.*쫓긴 사건 (\d+) 중 숨음 (\d+) \(지켜보는 중 (\d+)\) · 잡힘 (\d+) · 굶음 (\d+) · 잘림 (\d+)")
RE_START = re.compile(r"\[EcoV3I\] 두뇌 시작 \| [\d.]+초 \(전역 스텝 \d+\) \| (\S+)")


# --------------------------------------------------------------------- #
# 지역 기록 하나 → 셈 재료
# --------------------------------------------------------------------- #


def record(n: int, caught: int, starved: int, f: dict) -> dict:
    """지역 무대 하나(언리얼 스냅숏 지역·파이썬 세계)의 셈 재료. f = flight_stats 꼴(started·live_steps·flee_steps·reflex_steps·episode·route)."""
    e = f["episode"]
    r = dict(n=int(n), caught=int(caught), starved=int(starved), started=int(f["started"]), live=int(f["live_steps"]), flee=int(f["flee_steps"]),
             reflex=int(f["reflex_steps"]), **{f"ep_{k}": int(e[k]) for k in EP_KEYS})
    rt = f.get("route")
    if rt is not None:
        r.update(rt_run=int(rt["steps"]["run"]), rt_shelter=int(rt["steps"]["shelter"]), pk_run=int(rt["picked"]["run"]),
                 pk_shelter=int(rt["picked"]["shelter"]), refled=int(rt["refled"]))
    return r


def ratio(x: float, y: float) -> float:
    return x / y if y else float("nan")


def pool(recs: list) -> dict:
    """지역 기록 여럿의 합과 몫 (모듈 docstring '셈')."""
    s: dict = {}
    for r in recs:
        for k, v in r.items():
            if isinstance(v, int):
                s[k] = s.get(k, 0) + v
    out = dict(sums=s, ep_hide=ratio(s["ep_hidden"], s["ep_chased"]), ep_caught=ratio(s["ep_caught"], s["ep_chased"]),
               gf=ratio(1000.0 * s["started"], s["live"]), ge=ratio(1000.0 * s["ep_started"], s["live"]), caught_share=ratio(s["caught"], s["n"]),
               self_flee=ratio(s["flee"] - s["reflex"], s["live"]), flee_share=ratio(s["flee"], s["live"]))
    if "rt_run" in s and len([r for r in recs if "rt_run" in r]) == len(recs):
        out["shelter_route"] = ratio(s["rt_shelter"], s["rt_run"] + s["rt_shelter"])
        out["picked_shelter"] = ratio(s["pk_shelter"], s["pk_run"] + s["pk_shelter"])
    return out


def t_crit(df: int) -> float:
    """양측 5% t 문턱 (보고용 — 판정 아님)."""
    from scipy import stats

    return float(stats.t.ppf(0.975, max(int(df), 1)))


def direction(row: dict) -> str:
    """'같은 방향' 칸: 파이썬 차이가 짝 t 문턱 안이면 '파이썬 0 근처'(견줄 방향이 없다), 아니면 언리얼 차이의 부호가 같은가 (언리얼 짝 t 가 문턱 안이면 그렇게 적는다)."""
    pp, up = row["python_pair"], row["unreal_pair"]
    if not math.isfinite(pp["t"]) or abs(pp["t"]) < t_crit(pp["n"] - 1):
        return "파이썬 0 근처"
    weak = not math.isfinite(up["t"]) or abs(up["t"]) < t_crit(up["n"] - 1)
    same = np.sign(row["unreal_diff"]) == np.sign(pp["diff"])
    return ("예" if same else "아니오") + (" (언리얼은 0 근처)" if weak else "")


def paired(a: dict, b: dict) -> dict:
    """같은 열쇠의 짝 차이 a − b: 평균·표준오차·t·수 (r4_eval.paired 와 같은 식)."""
    keys = sorted(a)
    if keys != sorted(b):
        raise ValueError("두 판의 짝 열쇠가 다르다")
    d = np.array([a[k] - b[k] for k in keys], dtype=np.float64)
    d = d[np.isfinite(d)]
    n = len(d)
    m = float(d.mean()) if n else float("nan")
    se = float(d.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    t = m / se if se and se > 0 else float("nan")
    return dict(diff=m, se=se, t=t, n=n)


# --------------------------------------------------------------------- #
# 언리얼 (스냅숏·기록)
# --------------------------------------------------------------------- #


def read_text(path: Path) -> str:
    if path.suffix == ".gz":
        return gzip.decompress(path.read_bytes()).decode("utf-8", errors="replace")
    return path.read_text(encoding="utf-8", errors="replace")


def brain_weights_sha() -> str:
    return json.loads(BRAIN_FILE.read_text(encoding="utf-8"))["weights_sha256"]


def weather_table() -> dict:
    """거울 설정의 지역 날씨 표 (configs/v3_wild3_mirror.yaml wild_weather.regions)."""
    import yaml

    d = yaml.safe_load((ROOT / BRAINS["cur"]["config"]).read_text(encoding="utf-8"))
    return {k: (v[0], float(v[1])) for k, v in d["features"]["wild_weather"]["regions"].items()}


def unreal_run(folder: Path, name: str, brain: str, layout: dict, wx: dict) -> dict:
    """언리얼 판 하나 (s<S>_<두뇌>): 스냅숏 지역 기록 + 확인. 기록 파일이 있으면 그 확인도."""
    snap_path = folder / f"{name}.json"
    snap = json.loads(read_text(snap_path if snap_path.exists() else folder / f"{name}.json.gz"))
    B = BRAINS[brain]
    checks: list = []

    def check(ok: bool, what: str):
        checks.append(dict(ok=bool(ok), what=what))

    br = snap["brain"]
    check(int(snap["global_step"]) == STEPS, f"스냅숏 전역 스텝 {snap['global_step']} = {STEPS}")
    check(br["id"] == B["unreal_id"] and bool(br["builtin"]) == B["builtin"], f"두뇌 {br['id']} (내장 {br['builtin']})")
    check(int(br.get("obs_dim", 18)) == B["obs"] and int(br.get("mask_version", 2)) == B["mask"] and bool(br.get("route", False)) == B["route"]
          and bool(br.get("flee_gate", False)) == B["gate"], f"관측 {br.get('obs_dim')} · 판 {br.get('mask_version')} · 길 {br.get('route')} · 막음 {br.get('flee_gate')}")
    if brain == "r7e":
        check(br["weights_sha256"] == brain_weights_sha(), f"가중치 sha256 {br['weights_sha256'][:12]} = 두뇌 파일 {BRAIN_FILE.name}")
    st = snap["settings"]
    want = dict(deer_per_region=DEER, wolves_per_region=WOLVES, stage_size_units=60, wolf_eat_steps=EAT_STEPS, wild_flight=True, wild_satiation=True,
                wild_reserve=True, realism_vision=True, realism_hearing=True, shelter_safe=True, shelter_food=True, pack_hunt=True, obstacles=True,
                obstacle_detour=True, weather=True, foliage=False, no_freeze=True, social_control=False, gradual_night=True, flight_hold_awake=True,
                flight_edge_avoid=True)
    bad = {k: st.get(k) for k, v in want.items() if st.get(k) != v}
    check(not bad, "설정 = 게임 기본값(거울 설정과 같은 칸)" + (f" — 다른 칸 {bad}" if bad else ""))
    lay = {r["region"]: np.array(r["discs"], dtype=np.float64).reshape(-1, 3) for r in layout["regions"]}
    regions = {}
    for R in snap["regions"]:
        reg = R["region"]
        wf = R["world"]["wild_flight"]
        check(bool(wf.get("route", False)) == B["route"] and bool(not wf.get("brain_flee_outside_reflex", True)) == B["gate"],
              f"{reg} 세계 두 길 {wf.get('route')} · 반사 밖 두뇌 FLEE {wf.get('brain_flee_outside_reflex')}")
        w = R["world"]["weather"]
        check((w["kind"], float(w["intensity"])) == wx[reg], f"{reg} 날씨 {w['kind']} {w['intensity']} = 거울 표")
        D = np.array(R["obstacles"]["discs"], dtype=np.float64).reshape(-1, 3)
        ld = lay.get(reg, np.zeros((0, 3)))
        check(ld.shape == D.shape and bool((ld.view(np.uint64) == D.view(np.uint64)).all()), f"{reg} 원판 {len(D)} 개 = 나무 배치 표 (비트 단위)")
        check(sorted([[round(c[0]), round(c[1]), round(c[2])] for c in R["covers"]]) == COVERS, f"{reg} 은신처 {R['covers']}")
        check(bool(R["flight"]["on"]), f"{reg} 도망 기록 켬")
        rec = record(R["deer"]["adopted"], R["deer"]["caught"], R["deer"]["starved"], R["flight"])
        rec["region"] = reg
        regions[reg] = rec
    out = dict(name=name, brain=brain, session=int(snap["session_seed"]), regions=regions, checks=checks, snapshot=snap_path.name)
    log = next((p for p in (folder / f"{name}.log", folder / f"{name}.log.gz") if p.exists()), None)
    if log is not None:
        txt = read_text(log)
        lines = [s for s in txt.splitlines() if "LogEcoPolicyV3I" in s]
        warn = [s for s in lines if "LogEcoPolicyV3I: Warning" in s or "LogEcoPolicyV3I: Error" in s]
        swaps = [s for s in lines if "[EcoV3I] 두뇌 바꿈 |" in s]
        m = [RE_START.search(s) for s in lines]
        start = [x.group(1) for x in m if x]
        check(start == [B["unreal_id"]], f"기록 두뇌 시작 줄 {start}")
        check(not swaps, f"두뇌 바꿈 줄 {len(swaps)}")
        check(not warn, f"EcoV3I 경고·오류 줄 {len(warn)}" + (f" — 처음 {warn[0][:200]}" if warn else ""))
        f240 = {}
        for s in lines:
            g = RE_FLIGHT240.search(s)
            if g:
                f240[g.group(1)] = tuple(int(x) for x in g.groups()[1:])
        same = all(f240.get(reg) == (r["ep_chased"], r["ep_hidden"], r["ep_watching"], r["ep_caught"], r["ep_starved"], r["ep_truncated"])
                   for reg, r in regions.items())
        check(same and len(f240) == len(regions), "240 초 기록 줄의 쫓긴 사건 칸 = 스냅숏")
        out["log"] = log.name
        out["log_lines"] = len(lines)
    return out


# --------------------------------------------------------------------- #
# 파이썬 거울
# --------------------------------------------------------------------- #


def seeds_for(sessions: list, k: int) -> list:
    import run_mirror as rm

    seeds = rm.parse_seeds(SEED_TEXT)
    n = len(sessions) * len(REGIONS) * int(k)
    if n > len(seeds):
        raise SystemExit(f"세계 {n} 개에 쓸 탐색 시드가 {len(seeds)} 개뿐이다 — 세션이나 반복을 줄인다")
    return seeds[:n]


def run_name(brain: str, sessions: list, k: int) -> Path:
    return RUNS / f"parity_{brain}_u{sessions[0]}-{sessions[-1]}_k{k}.json"


def sha1_12(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:12]


def cmd_mirror(a) -> int:
    import run_mirror as rm

    sessions = rm.parse_unreal_maps(a.sessions)
    k = int(a.replicates)
    seeds = seeds_for(sessions, k)
    RUNS.mkdir(parents=True, exist_ok=True)
    for b in a.brains:
        B = BRAINS[b]
        res = rm.run(DEER, EAT_STEPS, seeds, workers=a.workers, model=ROOT / B["model"], config=ROOT / B["config"], unreal_maps=sessions, replicates=k,
                     unreal_obstacles=LAYOUT)
        worlds = []
        for w in res["worlds"]:
            m = w["meta"]
            cause = np.asarray(m["death_cause"])
            worlds.append(dict(seed=m["seed"], unreal_map=m["unreal_map"], n=m["n"], caught=int((cause == 1).sum()), starved=int((cause == 2).sum()),
                               flight=m["flight"], wall_s=m["wall_s"]))
        out = dict(meta=dict(res["meta"], brain=b, model_sha1=sha1_12(ROOT / B["model"])), worlds=worlds)
        p = run_name(b, sessions, k)
        p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{b}: 세계 {len(worlds)} · {res['meta']['wall_s']:.0f} 초 → {p}")
    return 0


def python_runs(sessions: list, k: int) -> dict:
    out = {}
    seeds = seeds_for(sessions, k)
    for b, B in BRAINS.items():
        p = run_name(b, sessions, k)
        if not p.exists():
            raise SystemExit(f"{p} 가 없다 — 먼저 mirror 를 돌린다")
        d = json.loads(p.read_text(encoding="utf-8"))
        m = d["meta"]
        if (m["model"] != Path(B["model"]).name or Path(m["config"]).as_posix() != B["config"] or m["unreal_maps"] != sessions
                or int(m["replicates"]) != k or m["seeds"] != seeds or m["steps"] != STEPS or m["deer"] != DEER or m["eat_steps"] != EAT_STEPS):
            raise SystemExit(f"{p.name} 의 조건이 이 비교와 다르다: {m}")
        out[b] = d
    return out


# --------------------------------------------------------------------- #
# 비교
# --------------------------------------------------------------------- #


def summarize(units: dict) -> dict:
    """{열쇠: [지역 기록 …]} → {열쇠: 셈}."""
    return {u: pool(rs) for u, rs in units.items()}


def compare(unreal_dir: Path, sessions: list, k: int) -> dict:
    layout = json.loads(LAYOUT.read_text(encoding="utf-8"))
    wx = weather_table()
    U = {b: {} for b in BRAINS}
    runs = []
    for s in sessions:
        for b in BRAINS:
            r = unreal_run(unreal_dir, f"s{s}_{b}", b, layout, wx)
            if r["session"] != s:
                raise SystemExit(f"{r['name']}: 세션 시드 {r['session']} ≠ {s}")
            U[b][s] = r
            runs.append(r)
    # 같은 시드 다시 돌림 (있으면): 지역 기록이 모두 같은가
    rerun = []
    for p in sorted(unreal_dir.glob("s*_r7e_b.json")) + sorted(unreal_dir.glob("s*_cur_b.json")):
        name = p.stem
        b = name.split("_")[1]
        s = int(name[1:].split("_")[0])
        if s in U[b]:
            r2 = unreal_run(unreal_dir, name, b, layout, wx)
            rerun.append(dict(name=name, against=U[b][s]["name"], same=r2["regions"] == U[b][s]["regions"]))
    P = python_runs(sessions, k)
    res = dict(sessions=sessions, replicates=k, brains={b: {kk: v for kk, v in B.items()} for b, B in BRAINS.items()},
               python_meta={b: dict(P[b]["meta"], unreal_obstacles=LAYOUT.relative_to(ROOT).as_posix()) for b in BRAINS}, rerun=rerun,
               unreal_runs=[dict(name=r["name"], brain=r["brain"], session=r["session"], log=r.get("log"), regions=r["regions"],
                                 checks_failed=[c for c in r["checks"] if not c["ok"]], checks=len(r["checks"])) for r in runs])
    groups = (("모든 지역", REGIONS),) + tuple((reg, (reg,)) for reg in REGIONS)
    res["groups"] = {}
    for gname, regs in groups:
        g = {}
        # 언리얼: 세션 단위
        u_units = {b: {s: [U[b][s]["regions"][r] for r in regs] for s in sessions} for b in BRAINS}
        u_sum = {b: summarize(u_units[b]) for b in BRAINS}
        u_all = {b: pool([x for s in sessions for x in u_units[b][s]]) for b in BRAINS}
        # 파이썬: (세션, 반복) 단위, 반복마다 세션 모음
        p_units = {b: {} for b in BRAINS}
        for b in BRAINS:
            for w in P[b]["worlds"]:
                um = w["unreal_map"]
                if um["region"] in regs:
                    p_units[b].setdefault((int(um["seed"]), int(um["replicate"])), []).append(record(w["n"], w["caught"], w["starved"], w["flight"]))
        p_sum = {b: summarize(p_units[b]) for b in BRAINS}
        p_all = {b: pool([x for v in p_units[b].values() for x in v]) for b in BRAINS}
        p_rep = {b: {j: pool([x for (s, jj), v in p_units[b].items() if jj == j for x in v]) for j in range(k)} for b in BRAINS}
        for _, key, _, _ in METRICS + ROUTE_ROWS:
            row = dict(unreal={b: u_all[b].get(key) for b in BRAINS}, python={b: p_all[b].get(key) for b in BRAINS})
            if all(key in u_sum[b][s] for b in BRAINS for s in sessions):
                row["unreal_pair"] = paired({s: u_sum["r7e"][s][key] for s in sessions}, {s: u_sum["cur"][s][key] for s in sessions})
                row["python_pair"] = paired({u: p_sum["r7e"][u][key] for u in p_sum["r7e"]}, {u: p_sum["cur"][u][key] for u in p_sum["cur"]})
                diffs = np.array([p_rep["r7e"][j][key] - p_rep["cur"][j][key] for j in range(k)], dtype=np.float64)
                row["python_rep_diff"] = dict(mean=float(diffs.mean()), sd=float(diffs.std(ddof=1)) if k > 1 else float("nan"),
                                              min=float(diffs.min()), max=float(diffs.max()))
                ud = row["unreal"]["r7e"] - row["unreal"]["cur"]
                rd = row["python_rep_diff"]
                row["unreal_diff"] = ud
                row["diff_z"] = (ud - rd["mean"]) / rd["sd"] if rd["sd"] and rd["sd"] > 0 else float("nan")
                row["direction"] = direction(row)
            row["level"] = {}
            for b in BRAINS:
                v = np.array([p_rep[b][j].get(key, np.nan) for j in range(k)], dtype=np.float64)
                if np.isfinite(v).all() and row["unreal"][b] is not None:
                    sd = float(v.std(ddof=1)) if k > 1 else float("nan")
                    row["level"][b] = dict(mean=float(v.mean()), sd=sd, min=float(v.min()), max=float(v.max()),
                                           z=(row["unreal"][b] - float(v.mean())) / sd if sd > 0 else float("nan"))
            g[key] = row
        g["sums"] = dict(unreal={b: u_all[b]["sums"] for b in BRAINS}, python={b: p_all[b]["sums"] for b in BRAINS})
        if gname == "모든 지역":
            g["unreal_sessions"] = {b: {s: {kk: v for kk, v in u_sum[b][s].items() if kk != "sums"} | dict(chased=u_sum[b][s]["sums"]["ep_chased"])
                                        for s in sessions} for b in BRAINS}
        res["groups"][gname] = g
    res["checks_ok"] = all(not r["checks_failed"] for r in res["unreal_runs"]) and all(x["same"] for x in rerun)
    return res


def _f(x, pct: bool, nd: int) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{100.0 * x:.{nd}f}%" if pct else f"{x:.{nd}f}"


def _d(x, pct: bool, nd: int) -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return "—"
    return f"{100.0 * x:+.{nd}f}%p" if pct else f"{x:+.{nd}f}"


def _t(x) -> str:
    return "—" if x is None or not math.isfinite(x) else f"{x:+.2f}".replace("-", "−")


def write_md(path: Path, res: dict) -> None:
    S, k = res["sessions"], res["replicates"]
    G = res["groups"]["모든 지역"]
    L = ["# R7e 두 길 두뇌 — 언리얼 통합 v3 대 파이썬 거울 (자동 생성 — results/v3/r7e/unreal_parity.py)", ""]
    h, c, gf = G["ep_hide"], G["ep_caught"], G["gf"]
    L += ["## 요약 (자동)", ""]
    L.append(f"- 사건 숨음 비율: 언리얼 {_f(h['unreal']['cur'], True, 2)} → {_f(h['unreal']['r7e'], True, 2)} ({_d(h['unreal_diff'], True, 2)}, 세션 짝 t "
             f"{_t(h['unreal_pair']['t'])}), 파이썬 거울 {_f(h['python']['cur'], True, 2)} → {_f(h['python']['r7e'], True, 2)} "
             f"({_d(h['python']['r7e'] - h['python']['cur'], True, 2)}) — 같은 방향: {h['direction']}, 크기 z {_t(h['diff_z'])}.")
    L.append(f"- 사건 잡힘 비율: 언리얼 {_d(c['unreal_diff'], True, 2)} (짝 t {_t(c['unreal_pair']['t'])}), 파이썬 {_d(c['python']['r7e'] - c['python']['cur'], True, 2)} "
             f"(짝 t {_t(c['python_pair']['t'])}) — 같은 방향: {c['direction']}, 크기 z {_t(c['diff_z'])}.")
    L.append(f"- GF: 언리얼 {_d(gf['unreal_diff'], False, 3)} (짝 t {_t(gf['unreal_pair']['t'])}), 파이썬 {_d(gf['python']['r7e'] - gf['python']['cur'], False, 3)} "
             f"(짝 t {_t(gf['python_pair']['t'])}) — 같은 방향: {gf['direction']}, 크기 z {_t(gf['diff_z'])}.")
    L.append(f"- 참고(세계·셈이 다름): 판정 `judge.md` G 세계(포만 켬, 480 초, 판정 시드 — 시드 평균) 사건 숨음 비율 R7 {JUDGE_G[0]} · route0 {JUDGE_G[1]}, "
             f"사건 잡힘 비율 {JUDGE_G[2]} · {JUDGE_G[3]}.")
    L.append("- '같은 방향' = 파이썬 차이가 짝 t 문턱(양측 5%) 밖일 때 언리얼 차이 부호가 같은가 (언리얼 짝 t 가 문턱 안이면 '언리얼은 0 근처'). 파이썬 차이가 문턱 "
             "안이면 '파이썬 0 근처'(견줄 방향 없음). 크기 z = (언리얼 차이 − 파이썬 반복 차이 평균) ÷ 파이썬 반복 차이 표준편차 (반복 하나 = 언리얼과 같은 세션 수의 "
             "파이썬 세계) — |z| < 2 면 파이썬 반복 폭 안.")
    L += ["", "## 조건", ""]
    L.append(f"- 언리얼: `/Game/Map/LV_Ecosystem_IntegrationTest -game -EcoIntegratedV3`, 세션 {S[0]}~{S[-1]}({len(S)} 개 × 지역 셋), 지역마다 사슴 {DEER}·늑대 {WOLVES}, "
             f"240 초(전역 스텝 {STEPS}) 스냅숏, `-benchmark -fps=30 -NullRHI`, 기본값(레벨 나무 + 지역 날씨 + 늑대 포만 켬). 두 두뇌 같은 세션 시드.")
    L.append(f"- 파이썬: `results/v3/mirror/run_mirror.py` 짝 비교 — 같은 지역 먹이 지도(C++ 난수)·나무 배치 표·지역 날씨, 지도마다 반복 {k}(두 두뇌 같은 시드 "
             f"{res['python_meta']['cur']['seeds'][0]}~ 탐색 범위), 1800 스텝.")
    L.append(f"- 두뇌: 지금 = {BRAINS['cur']['label']} (언리얼 내장 `{BRAINS['cur']['unreal_id']}`, 파이썬 `{BRAINS['cur']['model']}` · `{BRAINS['cur']['config']}`), "
             f"R7e = `{BRAINS['r7e']['unreal_id']}` (언리얼 `-EcoV3Brain=v3_r7_g995_s1_20m` 첫 결정 스텝부터, 파이썬 `{BRAINS['r7e']['model']}` · "
             f"`{BRAINS['r7e']['config']}`).")
    L.append("- 셈: 몫은 전체 합의 비(판정 표의 시드 평균과 셈이 다르다). 짝 t 는 언리얼 세션 단위(지역 셋 합), 파이썬 (세션, 반복) 단위 — 판정이 아니라 방향 보기다.")
    nfail = sum(len(r["checks_failed"]) for r in res["unreal_runs"])
    ncheck = sum(r["checks"] for r in res["unreal_runs"])
    L.append(f"- 확인: 언리얼 판 {len(res['unreal_runs'])} 개 확인 {ncheck} 칸 가운데 어긋남 {nfail} (스냅숏 스텝·두뇌 id·관측·판·두 길·막음·R7e 가중치 sha256·"
             "설정 = 거울 칸·지역 날씨 = 거울 표·원판 = 나무 배치 표(비트)·은신처 넷·240 초 기록 줄 사건 칸 = 스냅숏·두뇌 시작 줄·두뇌 바꿈 0·EcoV3I 경고/오류 0)"
             + "".join(f" · 같은 시드 다시 돌림 {x['name']} 대 {x['against']}: {'지역 기록 모두 같음' if x['same'] else '다름'}" for x in res["rerun"]))
    for r in res["unreal_runs"]:
        for cc in r["checks_failed"]:
            L.append(f"  - {r['name']}: {cc['what']}")
    L.append("")
    L.append("## 1. 두뇌 차이 (R7e − 지금) — 모든 지역")
    L.append("")
    L.append("| 칸 | 언리얼 지금 | 언리얼 R7e | 언리얼 차이 (세션 짝 t) | 파이썬 지금 | 파이썬 R7e | 파이썬 차이 (짝 t) | 파이썬 반복 차이 [최소..최대] | 같은 방향 | 크기 z |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for name, key, pct, nd in METRICS + ROUTE_ROWS:
        row = G[key]
        u, p = row["unreal"], row["python"]
        if "unreal_pair" in row:
            up, pp, rd = row["unreal_pair"], row["python_pair"], row["python_rep_diff"]
            L.append(f"| {name} | {_f(u['cur'], pct, nd)} | {_f(u['r7e'], pct, nd)} | {_d(row['unreal_diff'], pct, nd)} ({_t(up['t'])}, n {up['n']}) | "
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
                 f"SHELTER {sp['r7e']['pk_shelter']} (참고: 판정 N 세계 SHELTER 몫 0.5276 — judge.md '길 (R7, N)')")
    L.append("")
    L.append("## 2. 두뇌마다 값 — 언리얼 대 파이썬 반복")
    L.append("")
    L.append("| 칸 | 두뇌 | 언리얼 | 파이썬 반복 평균 [최소..최대] | z |")
    L.append("|---|---|---|---|---|")
    for name, key, pct, nd in METRICS[:5] + ROUTE_ROWS[:1]:
        for b in BRAINS:
            lv = G[key]["level"].get(b)
            if lv:
                L.append(f"| {name} | {BRAINS[b]['label']} | {_f(G[key]['unreal'][b], pct, nd)} | {_f(lv['mean'], pct, nd)} [{_f(lv['min'], pct, nd)}.."
                         f"{_f(lv['max'], pct, nd)}] | {_t(lv['z'])} |")
    L.append("")
    L.append("## 3. 지역마다 (R7e − 지금)")
    L.append("")
    L.append("| 지역 | 칸 | 언리얼 지금 → R7e (차이, 세션 짝 t) | 파이썬 지금 → R7e (차이, 짝 t) | 같은 방향 | 크기 z |")
    L.append("|---|---|---|---|---|---|")
    for reg in REGIONS:
        g = res["groups"][reg]
        for name, key, pct, nd in METRICS[:3]:
            row = g[key]
            u, p = row["unreal"], row["python"]
            L.append(f"| {reg} | {name} | {_f(u['cur'], pct, nd)} → {_f(u['r7e'], pct, nd)} ({_d(row['unreal_diff'], pct, nd)}, {_t(row['unreal_pair']['t'])}) | "
                     f"{_f(p['cur'], pct, nd)} → {_f(p['r7e'], pct, nd)} ({_d(p['r7e'] - p['cur'], pct, nd)}, {_t(row['python_pair']['t'])}) | {row['direction']} | "
                     f"{_t(row['diff_z'])} |")
        su_, sp_ = g["sums"]["unreal"], g["sums"]["python"]
        L.append(f"| {reg} | 쫓긴 사건 수 (지금 · R7e) | {su_['cur']['ep_chased']} · {su_['r7e']['ep_chased']} | {sp_['cur']['ep_chased']} · {sp_['r7e']['ep_chased']} | | |")
    L.append("")
    L.append("## 4. 언리얼 세션마다 (지역 셋 합)")
    L.append("")
    L.append("| 세션 | 쫓긴 사건 (지금 · R7e) | 사건 숨음 비율 지금 → R7e | 사건 잡힘 비율 지금 → R7e | GF 지금 → R7e |")
    L.append("|---|---|---|---|---|")
    us = G["unreal_sessions"]
    for s in S:
        a, b = us["cur"][s], us["r7e"][s]
        L.append(f"| {s} | {a['chased']} · {b['chased']} | {_f(a['ep_hide'], True, 1)} → {_f(b['ep_hide'], True, 1)} | {_f(a['ep_caught'], True, 1)} → "
                 f"{_f(b['ep_caught'], True, 1)} | {_f(a['gf'], False, 3)} → {_f(b['gf'], False, 3)} |")
    path.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, (np.floating,)):
        return _jsonable(float(o))
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return o


def cmd_compare(a) -> int:
    import run_mirror as rm

    sessions = rm.parse_unreal_maps(a.sessions)
    res = compare(Path(a.unreal), sessions, int(a.replicates))
    G = res["groups"]["모든 지역"]
    for name, key, pct, nd in METRICS:
        row = G[key]
        print(f"{name}: 언리얼 {_f(row['unreal']['cur'], pct, nd)} → {_f(row['unreal']['r7e'], pct, nd)} · 파이썬 {_f(row['python']['cur'], pct, nd)} → "
              f"{_f(row['python']['r7e'], pct, nd)}" + (f" · 크기 z {_t(row['diff_z'])}" if "diff_z" in row else ""))
    print("확인 모두 통과" if res["checks_ok"] else "확인 어긋남 있음 — md 머리 확인")
    if a.out:
        out = Path(a.out)
        out.with_suffix(".json").write_text(json.dumps(_jsonable(res), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        write_md(out.with_suffix(".md"), res)
    return 0 if res["checks_ok"] else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="R7e 두 길 두뇌 언리얼 대 파이썬 거울")
    sp = p.add_subparsers(dest="cmd", required=True)
    m = sp.add_parser("mirror", help="파이썬 거울 (두 두뇌, 언리얼 세션의 지도)")
    m.add_argument("--sessions", required=True)
    m.add_argument("--replicates", type=int, default=10)
    m.add_argument("--workers", type=int, default=None)
    m.add_argument("--brains", nargs="*", default=list(BRAINS))
    c = sp.add_parser("compare", help="언리얼 스냅숏·기록 대 파이썬 거울")
    c.add_argument("--unreal", required=True, help="s<S>_<cur|r7e>.json(스냅숏)·.log 가 있는 폴더")
    c.add_argument("--sessions", required=True)
    c.add_argument("--replicates", type=int, default=10)
    c.add_argument("--out", default=None)
    a = p.parse_args(argv)
    return cmd_mirror(a) if a.cmd == "mirror" else cmd_compare(a)


if __name__ == "__main__":
    sys.exit(main())

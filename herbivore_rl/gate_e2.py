"""Gate E2 — v2.2 경계·threat_recency 의 행동 게이트 (계획서 1-5, 4.2·4.3·4.4, 5.0, 6.2, 9절, 10절 #1·#5·#18).
사전 등록: results/v2/e2/PREREG.md

    python gate_e2.py configs --round V0                            # 회차의 감쇠 후보 설정(+ #18 변형 설정) 생성
    python -u gate_e2.py run --round V0 --c2 --workers 18           # 회차의 C2 하나 (상수는 감쇠와 무관하다)
    python -u gate_e2.py run --round V0 --cand d0_95 --workers 6    # 후보 하나: E2a A·B 갈래, E2b, #18, G_0.998
    python gate_e2.py judge                                          # 모든 회차 판정표 judge_e2.md·judge_e2.json

- 세계는 configs/v2_2.yaml(v2.1 + vigilance). 회차·후보마다 vigilance 의 decay(후보)와 보정 계수(eat_mult)만 바꾼
  사본을 `configs` 가 results/v2/e2/configs/<회차>_<후보>.yaml 로 만든다. #18 변형은 threat_flee 만 1 로 둔 사본
  (<회차>_<후보>_tf1.yaml)이고 E2b 의 '계속 뛰기 + 위협 반대 항' 보고 팔에만 쓴다.
- 구간(C2-seg)은 관측 7 threat_recency 하나의 문턱 [θ, 1] 이다(`SEG_BIN`): s0 평시(tr < θ), s1 최근 위협·안 보임
  (θ ≤ tr < 1), s2 포식자 보임(tr = 1). 포식자가 보이면 tr = 1 이고 안 보이면 tr ≤ decay < 1 이라(env_v2/world.py
  `_perceive`) 'tr ≥ 1' 은 '관측 1 > 0' 과 같다(tests/test_gate_e2.py). 그래서 θ 와 decay 는 C2-seg 에게 '놓친 뒤
  몇 스텝까지 최근인가'(K = floor(ln θ / ln decay))로만 보인다.
- 계산은 모두 `diagnose_v2.py constsearch` 가 한다(이 파일은 명령을 만들어 부르고 결과 JSON 을 판정한다). 실행한
  명령 전문은 디렉터리마다 `run.json` 에 남는다. 판정 규칙은 PREREG.md 와 같고, 어긋나면 PREREG.md 가 기준이다.
- 판정에 쓰는 값은 평가 시드 10000~10019 × 5000스텝, 결정적 상수 정책, γ_train = configs/ppo_best.yaml 의 γ
  (0.9916661555611042), 끝 600스텝 제외. G_0.998(10000스텝, 앞 500·끝 2500 제외)은 보고만 한다(5.0).
  출력은 results/v2/e2/ 아래다. 기존 결과·캐시를 덮지 않는다.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "results" / "v2" / "e2"
BASE_CONFIG = ROOT / "configs" / "v2_2.yaml"

# threat_recency 감쇠 후보 (PREREG 1절). 반감기 6.6 / 13.5 / 27.4 스텝. 제안값(v2_2.yaml 시작값)은 0.95.
DECAYS = (0.9, 0.95, 0.975)
PROPOSAL_DECAY = 0.95
# '최근 위협' 문턱 θ (계획서 1-5 'threat_recency > θ'). 고정한다(후보 아님). env_v2/world.py RECENT_THREAT 와 같다.
THETA = 0.5
# 회차: V0 제안값, V1·V2 보정(5.0 최대 2회). 보정 대상은 9절의 섭식 손실(eat_mult)과 반경 배수(view_r_mult)뿐이다.
ROUNDS = ("V0", "V1", "V2")
ROUND_COEF = {
    "V0": {"eat_mult": 0.0, "view_r_mult": 1.0},
    "V1": {"eat_mult": 0.5, "view_r_mult": 1.0},
    "V2": {"eat_mult": 0.5, "view_r_mult": 1.5},
}
ROUND_LABEL = {"V0": "V0 제안값 (경계 섭식 0, 반경 ×1)", "V1": "V1 보정 1회차 (경계 섭식 0.5)",
               "V2": "V2 보정 2회차 (경계 섭식 0.5, 경계 반경 ×1.5)"}
MAX_ROUNDS = len(ROUNDS)

# C2-seg 구간 (diagnose_v2 --seg-bins). 구간 id 0 평시, 1 최근 위협·안 보임, 2 포식자 보임
SEG_BIN = f"threat_recency:{THETA:g},1"
SEGMENT_LABEL = ("평시", "최근 위협·안 보임", "포식자 보임")
S_CALM, S_RECENT, S_SEEN = 0, 1, 2
N_SEG = len(SEGMENT_LABEL)

# 행동 열 (configs/v2_2.yaml: forage, cohesion, flee_dist, cover, speed, vigilance)
A_FLEE, A_SPEED, A_VIG = 2, 4, 5
ACT_DIM = 6
RUN = 1.0          # speed 뛰기 (≥ 2/3)
NO_VIG = 0.0       # vigilance 끔 (≤ 0.5)
VIG = 1.0          # vigilance 켬 (> 0.5)
E2B_FLEE = 1.0     # E2b 의 flee_dist: 포식자가 보이면 늘 도주 분기 (d_pred < 1.0·see_r). 안 보이면 효과 없음
THREAT_FLEE_VARIANT = 1.0   # 10절 #18 변형 팔의 threat_flee (× flee_weight)

# C2 탐색 시작점 (PREREG 2절): E1-b 가 고른 v2.1 C2(results/v2/e1/judge_e1b.json final.c2), v1 최적 상수 + 걷기,
# v1 학습 전 최고 상수 + 걷기(diagnose_v2 기본 enqueue). vigilance 는 0.25(경계 아님 띠의 가운데, diagnose_v2
# PRETRAIN_EXTRA). 경계를 늘 켜는 상수는 섭식 0 이라 굶는다.
E1B_C2 = (0.9709889334578663, 0.7849404966375042, 0.2182330585135458, 0.03358694847233987, 0.4913744307309694)
V1_C2 = (0.4207, 0.8656, 0.1054, 0.0044)
V1_PRETRAIN_BEST = (0.39, 0.99, 0.92, 0.15)
VIG_OFF_START = 0.25
C2_ENQUEUE = (E1B_C2 + (VIG_OFF_START,), V1_C2 + (0.5, VIG_OFF_START), V1_PRETRAIN_BEST + (0.5, VIG_OFF_START))

# 판정 기준 (PREREG 3절)
T_CRIT = 2.093                    # 평가 시드 20개 짝지은 t, 자유도 19, 양측 5%
VIG_FRAC_RANGE = (0.01, 0.5)      # 9절 '경계 비율 0 근처·과반' = 환경 실패 신호. 허용 C2-seg 의 경계 비율이 이 안


# --------------------------------------------------------------------- #
# 이름·경로
# --------------------------------------------------------------------- #


def rel(p: Path) -> str:
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(p).as_posix()


def _num_tag(x: float) -> str:
    return f"{float(x):g}".replace(".", "_")


def cand_name(decay: float) -> str:
    """감쇠 후보 이름: 0.95 → d0_95."""
    return f"d{_num_tag(decay)}"


def decay_of(cand: str) -> float:
    for d in DECAYS:
        if cand_name(d) == cand:
            return d
    raise ValueError(f"모르는 후보 {cand!r}. 쓸 수 있는 후보: {', '.join(cand_name(d) for d in DECAYS)}")


def config_path(rnd: str, decay: float, out: Path | None = None, threat_flee: float = 0.0) -> Path:
    out = OUT if out is None else out
    tf = f"_tf{_num_tag(threat_flee)}" if threat_flee else ""
    return out / "configs" / f"{rnd}_{cand_name(decay)}{tf}.yaml"


def window_steps(decay: float, theta: float = THETA) -> int:
    """놓친 뒤 '최근 위협'(tr ≥ θ)에 머무는 스텝 수 K: 포식자를 놓친 뒤 k 번째 관측의 tr = decay^k ≥ θ 인 가장 큰 k."""
    k = 0
    while decay ** (k + 1) >= theta:
        k += 1
    return k


# --------------------------------------------------------------------- #
# 회차·후보 설정
# --------------------------------------------------------------------- #


def round_config(rnd: str, decay: float, threat_flee: float = 0.0, base: Path = BASE_CONFIG) -> dict:
    """configs/v2_2.yaml 에서 vigilance 의 decay·eat_mult·threat_flee 만 바꾼 설정 dict (PREREG 1절).

    반경 배수(V2 회차)는 아직 구현하지 않았다(PREREG 4절: V2 에 가면 구현한 뒤 만든다) — NotImplementedError.
    """
    if rnd not in ROUND_COEF:
        raise ValueError(f"모르는 회차 {rnd!r}. 쓸 수 있는 회차: {', '.join(ROUNDS)}")
    if float(decay) not in DECAYS:
        raise ValueError(f"감쇠 {decay} 는 후보 {DECAYS} 밖이다")
    coef = ROUND_COEF[rnd]
    if coef["view_r_mult"] != 1.0:
        raise NotImplementedError(f"{rnd} 회차의 경계 반경 배수 ×{coef['view_r_mult']:g} 는 아직 구현하지 않았다 "
                                  "(PREREG 4절: 그 회차에 가면 env_v2 에 구현하고 테스트한 뒤 설정을 만든다)")
    with open(base, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    vg = d["features"]["vigilance"]
    vg["decay"] = float(decay)
    vg["eat_mult"] = float(coef["eat_mult"])
    vg["threat_flee"] = float(threat_flee)
    return d


def check_base(base: Path = BASE_CONFIG) -> None:
    """바탕 설정의 vigilance 규칙값이 PREREG 1절과 같은지 본다(문턱 0.5, 시야 360°). 다르면 ValueError."""
    with open(base, encoding="utf-8") as f:
        vg = yaml.safe_load(f)["features"]["vigilance"]
    if not vg.get("enabled") or float(vg["threshold"]) != 0.5 or float(vg["fov_deg"]) != 360.0:
        raise ValueError(f"{rel(base)} 의 vigilance 가 PREREG 1절(켬, 문턱 0.5, 시야 360°)과 다르다: {vg}")


def write_config(rnd: str, decay: float, out: Path | None = None, threat_flee: float = 0.0,
                 base: Path = BASE_CONFIG) -> Path:
    """회차·후보 설정 yaml 을 쓴다. 같은 파일이 있으면 내용이 같을 때만 두고, 다르면 덮지 않는다(FileExistsError)."""
    from env_v2.config import load_v2_config
    from env_v2.world import World
    check_base(base)
    d = round_config(rnd, decay, threat_flee, base)
    vg = d["features"]["vigilance"]
    path = config_path(rnd, decay, out, threat_flee)
    head = [
        f"# Gate E2 {rnd} 후보 {cand_name(decay)}{' #18 변형' if threat_flee else ''} — gate_e2.py configs 가 "
        f"{rel(base)} 에서 만들었다. 손으로 고치지 않는다.",
        f"# 바꾼 계수(그 밖은 {rel(base)} 와 같다): vigilance.decay = {vg['decay']!r} (반감기 "
        f"{math.log(0.5) / math.log(vg['decay']):.1f}스텝, θ {THETA:g} 에서 놓친 뒤 {window_steps(vg['decay'])}스텝까지 최근 위협),",
        f"#   vigilance.eat_mult = {vg['eat_mult']!r} (회차 {rnd}), vigilance.threat_flee = {vg['threat_flee']!r}"
        + (" (10절 #18 변형 — E2b 보고 팔 전용)" if threat_flee else " (끔)"),
        "",
    ]
    text = "\n".join(head) + yaml.safe_dump(d, sort_keys=False, allow_unicode=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != text:
            raise FileExistsError(f"{rel(path)} 가 이미 있고 내용이 다르다. 덮지 않는다")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    w = World(load_v2_config(path), seeds=[0])
    assert w._vg["decay"] == float(decay) and w._vg["threat_flee"] == float(threat_flee), w._vg
    return path


# --------------------------------------------------------------------- #
# 명령 (diagnose_v2 constsearch 인자)
# --------------------------------------------------------------------- #

# 도구 시험(--smoke)용 작은 조건. 판정 실행에는 쓰지 않는다(run.json 에 smoke 로 남는다).
SMOKE_SEARCH = ["--trials", "3", "--top-k", "2", "--search-seeds", "0:1", "--search-steps", "700",
                "--rescore-seeds", "100:101", "--rescore-steps", "700"]
SMOKE_EVAL = ["--eval-seeds", "10000:10002", "--eval-steps", "1300"]


def _fmt(x) -> str:
    return repr(float(x))


def _vals(v) -> list[str]:
    return [_fmt(x) for x in v]


def forbid_action(c2) -> list[float]:
    """경계 금지 바탕: C2 의 앞 5개 + vigilance 0 (PREREG 2절 A-금지·B-금지)."""
    return [float(x) for x in list(c2)[:A_VIG]] + [NO_VIG]


def e2b_base(c2) -> list[float]:
    """E2b 바탕 상수: C2 의 forage·cohesion·cover·speed, flee_dist 1.0, vigilance 0 (PREREG 2절)."""
    c = [float(x) for x in c2]
    return [c[0], c[1], E2B_FLEE, c[3], c[A_SPEED], NO_VIG]


def e2b_table(c2, arm: str) -> list[float]:
    """E2b 구간표 [s0 speed, s0 vig, s1 speed, s1 vig, s2 speed, s2 vig]. 평시 = C2 보행, 보임 = 뛰기,
    최근 위협·안 보임 = 경계(arm 'vig', speed 는 C2 값이지만 경계가 우선) 또는 뛰기(arm 'run')."""
    s = float(c2[A_SPEED])
    if arm not in ("vig", "run"):
        raise ValueError(arm)
    s1 = [s, VIG] if arm == "vig" else [RUN, NO_VIG]
    return [s, NO_VIG, *s1, RUN, NO_VIG]


def tab_table(b_allow, arm: str) -> list[float]:
    """E2b-표(보고): B-허용 구간표에서 최근 위협 구간만 경계(그 구간 speed 그대로) 또는 뛰기로 바꾼다."""
    t = [float(x) for x in b_allow]
    if len(t) != 2 * N_SEG:
        raise ValueError(f"B-허용 구간표는 값 {2 * N_SEG}개다: {t}")
    if arm not in ("vig", "run"):
        raise ValueError(arm)
    t[2 * S_RECENT:2 * S_RECENT + 2] = [t[2 * S_RECENT], VIG] if arm == "vig" else [RUN, NO_VIG]
    return t


def seg_args(dims) -> list[str]:
    return ["--seg-bins", SEG_BIN, "--seg-dims", *dims]


def c2_commands(cfg: Path, d: Path, workers: int, smoke: bool = False) -> list[tuple[str, list[str]]]:
    """회차의 C2 (PREREG 2절). 탐색·재측정·평가 조건은 diagnose_v2 기본값이다."""
    enq = []
    for v in C2_ENQUEUE:
        enq += ["--enqueue", *_vals(v)]
    search = SMOKE_SEARCH + SMOKE_EVAL if smoke else []
    return [("constsearch", ["constsearch", "--config", rel(cfg), "--workers", str(workers), "--out", rel(d),
                             *enq, *search])]


def cand_commands(cfg: Path, cfg_tf: Path, d: Path, workers: int, c2=None, a_allow=None, b_forbid=None,
                  b_allow=None, smoke: bool = False) -> list[tuple[str, list[str]]]:
    """후보 하나의 단계별 diagnose_v2 인자 (PREREG 2절·7절). 앞 단계 결과가 있어야 뒤 단계 인자가 정해진다.

    c2 = 회차 C2 best(6), a_allow = A-허용 구간표(3), b_forbid = B-금지 구간표(3), b_allow = B-허용 구간표(6).
    """
    if c2 is None:
        return []
    common = ["--config", rel(cfg), "--workers", str(workers)]
    search = SMOKE_SEARCH + SMOKE_EVAL if smoke else []
    ev = SMOKE_EVAL if smoke else []
    g9 = ev[:2] if smoke else []
    o, og = ["--out", rel(d)], ["--out", rel(d / "g998")]
    c2 = [float(x) for x in c2]
    fa = forbid_action(c2)
    sv = ["speed", "vigilance"]
    steps: list[tuple[str, list[str]]] = [
        ("a_forbid", ["constsearch", *common, *o, "--tag", "a_forbid", "--const-action", *_vals(fa), *ev]),
        ("a_allow", ["constsearch", *common, *o, "--tag", "a_allow", *seg_args(["vigilance"]),
                     "--base-action", *_vals(c2), *search]),
        ("b_forbid", ["constsearch", *common, *o, "--tag", "b_forbid", *seg_args(["speed"]),
                      "--base-action", *_vals(fa), *search]),
    ]
    if b_forbid is not None:
        bf = [float(x) for x in b_forbid]
        enq = ["--enqueue", *_vals([c2[A_SPEED], c2[A_VIG]] * N_SEG),
               "--enqueue", *_vals([x for s in bf for x in (s, c2[A_VIG])])]
        steps.append(("b_allow", ["constsearch", *common, *o, "--tag", "b_allow", *seg_args(sv),
                                  "--base-action", *_vals(c2), *enq, *search]))
    for arm in ("vig", "run"):
        steps.append((f"e2b_{arm}", ["constsearch", *common, *o, "--tag", f"e2b_{arm}", *seg_args(sv),
                                     "--base-action", *_vals(e2b_base(c2)),
                                     "--const-action", *_vals(e2b_table(c2, arm)), *ev]))
    steps.append(("tf/e2b_run18", ["constsearch", "--config", rel(cfg_tf), "--workers", str(workers),
                                   "--out", rel(d / "tf"), "--tag", "e2b_run18", *seg_args(sv),
                                   "--base-action", *_vals(e2b_base(c2)),
                                   "--const-action", *_vals(e2b_table(c2, "run")), *ev]))
    if b_allow is not None:
        for arm in ("vig", "run"):
            steps.append((f"e2b_tab_{arm}", ["constsearch", *common, *o, "--tag", f"e2b_tab_{arm}", *seg_args(sv),
                                             "--base-action", *_vals(c2),
                                             "--const-action", *_vals(tab_table(b_allow, arm)), *ev]))
    steps.append(("g998/a_forbid", ["constsearch", *common, *og, "--tag", "a_forbid", "--g998",
                                    "--const-action", *_vals(fa), *g9]))
    if a_allow is not None:
        steps.append(("g998/a_allow", ["constsearch", *common, *og, "--tag", "a_allow", "--g998",
                                       *seg_args(["vigilance"]), "--base-action", *_vals(c2),
                                       "--const-action", *_vals(a_allow), *g9]))
    if b_forbid is not None:
        steps.append(("g998/b_forbid", ["constsearch", *common, *og, "--tag", "b_forbid", "--g998",
                                        *seg_args(["speed"]), "--base-action", *_vals(fa),
                                        "--const-action", *_vals(b_forbid), *g9]))
    if b_allow is not None:
        steps.append(("g998/b_allow", ["constsearch", *common, *og, "--tag", "b_allow", "--g998", *seg_args(sv),
                                       "--base-action", *_vals(c2), "--const-action", *_vals(b_allow), *g9]))
    for arm in ("vig", "run"):
        steps.append((f"g998/e2b_{arm}", ["constsearch", *common, *og, "--tag", f"e2b_{arm}", "--g998",
                                          *seg_args(sv), "--base-action", *_vals(e2b_base(c2)),
                                          "--const-action", *_vals(e2b_table(c2, arm)), *g9]))
    return steps


# --------------------------------------------------------------------- #
# 실행
# --------------------------------------------------------------------- #


def load_json(path: Path) -> dict | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _best(path: Path):
    d = load_json(path)
    return None if d is None else d["best"]


def _execute(d: Path, steps_fn, digests: dict[str, str], label: str, smoke: bool) -> int:
    """`steps_fn()` 이 내는 단계를 앞에서부터 하나씩 돌린다. 끝난 단계는 run.json 에 남고 다시 돌리지 않는다.

    digests: 단계 이름 앞부분('tf/' 등) → 그 단계가 써야 하는 설정 digest. 기본 키는 "".
    """
    d.mkdir(parents=True, exist_ok=True)
    log = d / "run.log"
    record = load_json(d / "run.json") or {"label": label, "config_digest": digests, "smoke": bool(smoke),
                                           "steps": []}
    if bool(record.get("smoke")) != bool(smoke):
        raise SystemExit(f"{rel(d)} 는 {'도구 시험' if record.get('smoke') else '판정'} 실행 기록이다. 섞지 않는다")
    if record.get("config_digest") != digests:
        raise SystemExit(f"{rel(d)} 는 다른 설정({record.get('config_digest')})으로 잰 기록이다. 덮지 않는다")
    done = {s["stem"] for s in record["steps"] if s.get("returncode") == 0}
    while True:
        todo = [(stem, a) for stem, a in steps_fn() if stem not in done]
        if not todo:
            break
        stem, a = todo[0]
        res = d / f"{stem}.json"
        prev = load_json(res)
        want = digests.get(stem.split("/")[0] + "/", digests[""])
        if prev is not None:
            if prev.get("meta", {}).get("config_digest") != want:
                raise SystemExit(f"{rel(res)} 는 다른 설정의 결과다. 덮지 않는다")
            raise SystemExit(f"{rel(res)} 가 이미 있는데 run.json 에 기록이 없다. 확인 뒤 지우고 다시 돌린다")
        cmd = [sys.executable, "-u", "diagnose_v2.py", *a]
        line = "python diagnose_v2.py " + " ".join(a)
        print(f"[{label}] {line}", flush=True)
        t0 = time.time()
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"\n$ {line}\n")
            f.flush()
            rc = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT).returncode
        record["steps"].append({"stem": stem, "command": line, "returncode": rc,
                                "elapsed_s": round(time.time() - t0, 1),
                                "finished": datetime.now(timezone.utc).isoformat(timespec="seconds")})
        record["python"] = platform.python_version()
        (d / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        if rc != 0:
            raise SystemExit(f"실패 (종료 코드 {rc}): {line}. 로그 {rel(log)}")
        got = (load_json(res) or {}).get("meta", {}).get("config_digest")
        if got != want:
            raise SystemExit(f"{rel(res)} 의 config_digest {got} 가 기대값 {want} 와 다르다")
        done.add(stem)
    print(f"[{label}] 끝", flush=True)
    return 0


def cmd_run(args) -> int:
    from diagnose_v2 import config_digest
    from env_v2.config import load_v2_config
    out = Path(args.out) if args.out else OUT
    rnd = args.round
    if bool(args.c2) == bool(args.cand):
        raise SystemExit("--c2 와 --cand <후보> 중 하나만 준다")
    prop = config_path(rnd, PROPOSAL_DECAY, out)
    if not prop.exists():
        raise SystemExit(f"{rel(prop)} 가 없다. 먼저 gate_e2.py configs --round {rnd} 로 만든다")
    prop_digest = config_digest(load_v2_config(prop))
    c2_dir = out / rnd / "c2"
    if args.c2:
        return _execute(c2_dir, lambda: c2_commands(prop, c2_dir, args.workers, args.smoke),
                        {"": prop_digest}, f"{rnd}/c2", args.smoke)
    try:
        decay = decay_of(args.cand)
    except ValueError as e:
        raise SystemExit(str(e))
    cfg, cfg_tf = config_path(rnd, decay, out), config_path(rnd, decay, out, THREAT_FLEE_VARIANT)
    for p in (cfg, cfg_tf):
        if not p.exists():
            raise SystemExit(f"{rel(p)} 가 없다. 먼저 gate_e2.py configs --round {rnd} 로 만든다")
    c2 = load_json(c2_dir / "constsearch.json")
    if c2 is None:
        raise SystemExit(f"{rel(c2_dir / 'constsearch.json')} 가 없다. 먼저 gate_e2.py run --round {rnd} --c2")
    if c2["meta"]["config_digest"] != prop_digest:
        raise SystemExit(f"{rel(c2_dir)} 의 C2 는 이 회차의 제안 후보 설정에서 잰 것이 아니다")
    d = out / rnd / args.cand

    def steps():
        return cand_commands(cfg, cfg_tf, d, args.workers, c2["best"], _best(d / "a_allow.json"),
                             _best(d / "b_forbid.json"), _best(d / "b_allow.json"), smoke=args.smoke)

    digests = {"": config_digest(load_v2_config(cfg)), "tf/": config_digest(load_v2_config(cfg_tf)),
               "g998/": config_digest(load_v2_config(cfg))}
    return _execute(d, steps, digests, f"{rnd}/{args.cand}", args.smoke)


def cmd_configs(args) -> int:
    out = Path(args.out) if args.out else OUT
    for decay in DECAYS:
        for tf in (0.0, THREAT_FLEE_VARIANT):
            try:
                p = write_config(args.round, decay, out, tf)
            except (ValueError, FileExistsError, NotImplementedError) as err:
                raise SystemExit(str(err))
            print(f"{rel(p)}  (후보 {cand_name(decay)}, 놓친 뒤 {window_steps(decay)}스텝까지 최근 위협"
                  f"{', #18 변형' if tf else ''})")
    return 0


# --------------------------------------------------------------------- #
# 판정 (순수 함수 — tests/test_gate_e2.py)
# --------------------------------------------------------------------- #


def _f(v) -> float:
    """JSON 값 → float. diagnose_v2 는 nan·inf 를 null 로 쓴다."""
    return float("nan") if v is None else float(v)


def rows_of(d: dict) -> list[dict]:
    """constsearch 결과의 평가 행 (C2 또는 C2-seg)."""
    return d["per_seed"][d["kind"]]


def mean_of(d: dict, col: str) -> float:
    return _f(d["eval"]["mean"].get(col))


def paired_col(a: dict, b: dict, col: str) -> dict:
    """평가 시드를 짝지은 t (diagnose_v2.paired 와 같은 식). a − b. 시드가 다르면 ValueError."""
    import numpy as np

    from diagnose_v2 import paired
    ra, rb = rows_of(a), rows_of(b)
    sa, sb = [r["seed"] for r in ra], [r["seed"] for r in rb]
    if sa != sb:
        raise ValueError(f"짝지을 평가 시드가 다르다: {sa[:3]}… vs {sb[:3]}…")
    return paired(np.asarray([_f(r.get(col)) for r in ra]), np.asarray([_f(r.get(col)) for r in rb]))


def higher(t: dict) -> bool:
    """'유의하게 높다': Δ > 0 이고 t > T_CRIT (E1 과 같은 규칙)."""
    return bool(t["diff"] > 0 and math.isfinite(t["t"]) and t["t"] > T_CRIT)


def lower(t: dict) -> bool:
    return bool(t["diff"] < 0 and math.isfinite(t["t"]) and t["t"] < -T_CRIT)


def vig_values(d: dict) -> list[float]:
    """결과 정책의 구간별 vigilance 값 (구간 순서 s0 평시, s1 최근, s2 보임). 상수면 같은 값 셋."""
    names = d["meta"]["act_names"]
    k = names.index("vigilance")
    if d["kind"] == "C2-seg":
        dims = list(d["dims"])
        if k in dims:
            return [float(row[dims.index(k)]) for row in d["best_table"]]
        return [float(d["base_action"][k])] * N_SEG
    return [float(d["best"][k])] * N_SEG


def speed_values(d: dict) -> list[float]:
    names = d["meta"]["act_names"]
    k = names.index("speed")
    if d["kind"] == "C2-seg":
        dims = list(d["dims"])
        if k in dims:
            return [float(row[dims.index(k)]) for row in d["best_table"]]
        return [float(d["base_action"][k])] * N_SEG
    return [float(d["best"][k])] * N_SEG


OUTCOME_COLS = ("g_gamma", "survival", "repro", "predation_rate", "starve_rate", "mean_return")


def judge_e2a(allow: dict, forbid: dict, threshold: float, g998_allow: dict | None = None,
              g998_forbid: dict | None = None) -> dict:
    """E2a 한 갈래 (PREREG 3.1·3.2): 허용 C2-seg vs 금지. (i) G_γ 유의하게 높다 (ii) 구간별 경계 상태가 둘 이상
    (iii) 허용 C2-seg 의 경계 비율이 VIG_FRAC_RANGE 안. 통과 = 셋 다."""
    t = paired_col(allow, forbid, "g_gamma")
    states = [v > threshold for v in vig_values(allow)]
    vf = mean_of(allow, "vig_frac")
    out = dict(diff=t["diff"], t=t["t"], higher=higher(t), vig=vig_values(allow), speed=speed_values(allow),
               states=states, distinct=len(set(states)) >= 2, vig_frac=vf,
               frac_ok=bool(VIG_FRAC_RANGE[0] <= vf <= VIG_FRAC_RANGE[1]), over=bool(vf > VIG_FRAC_RANGE[1]),
               forbid_speed=speed_values(forbid),
               outcome={c: dict(allow=mean_of(allow, c), forbid=mean_of(forbid, c), **paired_col(allow, forbid, c))
                        for c in OUTCOME_COLS})
    out["pass"] = bool(out["higher"] and out["distinct"] and out["frac_ok"])
    if g998_allow is not None and g998_forbid is not None:
        g = paired_col(g998_allow, g998_forbid, "g_gamma")
        out["g998"] = dict(allow=mean_of(g998_allow, "g_gamma"), forbid=mean_of(g998_forbid, "g_gamma"),
                           diff=g["diff"], t=g["t"], higher=higher(g))
        # 5.0 '0.998 에서만 통과': γ_train 의 (i) 만 실패하고 G_0.998 로는 높고 (ii)(iii) 은 통과
        out["g998_only"] = bool(not out["higher"] and out["g998"]["higher"] and out["distinct"] and out["frac_ok"])
    else:
        out["g998"], out["g998_only"] = None, False
    return out


def judge_e2b(vig: dict, run: dict, g998_vig: dict | None = None, g998_run: dict | None = None) -> dict:
    """E2b (PREREG 3.4): '최근 위협·안 보임' 구간에서 경계(V) vs 계속 뛰기(R), 나머지 동일.
    통과 = V 가 G_γ 에서 유의하게 높고(Δ > 0, t > 2.093) 피식률에서 유의하게 낮다(Δ < 0, t < −2.093)."""
    tg, tp = paired_col(vig, run, "g_gamma"), paired_col(vig, run, "predation_rate")
    out = dict(g=dict(vig=mean_of(vig, "g_gamma"), run=mean_of(run, "g_gamma"), **tg),
               pred=dict(vig=mean_of(vig, "predation_rate"), run=mean_of(run, "predation_rate"), **tp),
               g_win=higher(tg), pred_win=lower(tp),
               outcome={c: dict(vig=mean_of(vig, c), run=mean_of(run, c), **paired_col(vig, run, c))
                        for c in OUTCOME_COLS})
    out["pass"] = bool(out["g_win"] and out["pred_win"])
    if g998_vig is not None and g998_run is not None:
        g = paired_col(g998_vig, g998_run, "g_gamma")
        out["g998"] = dict(vig=mean_of(g998_vig, "g_gamma"), run=mean_of(g998_run, "g_gamma"), diff=g["diff"],
                           t=g["t"])
    else:
        out["g998"] = None
    return out


def judge_t18(vig: dict, run: dict, run18: dict) -> dict:
    """10절 #18 보고 (PREREG 3.7): 계속 뛰기 + 위협 반대 항(R18) − 경계(V), R18 − 계속 뛰기(R).
    '크게 이긴다' = R18 이 V 와 R 둘 다보다 G_γ 에서 유의하게 높다 → 조향 계약 변경안 후보(결정은 사람)."""
    out = {}
    for name, ref in (("vs_vig", vig), ("vs_run", run)):
        out[name] = {c: paired_col(run18, ref, c) for c in ("g_gamma", "predation_rate", "survival")}
    out["run18"] = {c: mean_of(run18, c) for c in OUTCOME_COLS}
    out["big_win"] = bool(higher(out["vs_vig"]["g_gamma"]) and higher(out["vs_run"]["g_gamma"]))
    return out


def select(cands: dict[str, dict], key: str) -> str | None:
    """회차 안 후보 선택 (PREREG 3.3): 갈래 key('A'·'B') 를 통과한 후보 가운데 제안 감쇠(0.95)를 먼저, 아니면 t 가
    가장 큰 후보."""
    ok = {k: v for k, v in cands.items() if v.get(key) and v[key]["pass"]}
    if not ok:
        return None
    if cand_name(PROPOSAL_DECAY) in ok:
        return cand_name(PROPOSAL_DECAY)
    return max(ok, key=lambda k: ok[k][key]["t"])


def next_round(history: list[dict]) -> dict:
    """앞 회차 판정 → 다음 (PREREG 4절의 기계적 규칙). history = 회차 순서의 판정 dict 목록.

    반환: {"action": "pass" | "stop" | "calibrate", "round": 다음 회차, "reason": ...}.
    """
    last = history[-1]
    rnd = last["round"]
    if last.get("selected_A"):
        return {"action": "pass", "reason": f"{rnd} 에서 {last['selected_A']} 가 E2a(A 갈래)를 통과"}
    cands = last["cands"]
    g9 = [k for k, v in cands.items() if v["A"].get("g998_only")]
    if g9:
        return {"action": "stop", "reason": f"{', '.join(g9)}: γ_train 에서는 E2a 실패, G_0.998 로만 통과 — 5.0 "
                                            "'0.998 에서만 통과'라 보정 회차를 쓰지 않고 멈춰 보고한다(0.998 재탐색은 사람 결정)"}
    if last.get("selected_B"):
        return {"action": "stop", "reason": f"A 갈래는 모두 실패, B 갈래(보행도 구간별)에서 {last['selected_B']} 가 통과 — "
                                            "실패가 '상수 보행' 제약 때문일 수 있어 환경 보정을 하지 않고 멈춰 보고한다(사람 결정)"}
    prop = cands.get(cand_name(PROPOSAL_DECAY))
    if prop is not None and (prop["A"]["over"] or prop["B"]["over"]):
        return {"action": "stop", "reason": "기준 후보(0.95)의 허용 C2-seg 경계 비율이 0.5 를 넘는다(9절 '과반') — "
                                            "경계를 더 싸게 하는 보정은 반대 방향이라 멈춰 보고한다"}
    if len(history) >= MAX_ROUNDS:
        return {"action": "stop", "reason": "보정 2회 뒤에도 E2a 를 통과한 후보가 없다(5.0). 멈추고 보고한다"}
    nxt = ROUNDS[len(history)]
    coef = ROUND_COEF[nxt]
    for r in history:
        if ROUND_COEF[r["round"]] == coef:
            return {"action": "stop", "reason": f"다음 회차 {nxt} 의 계수가 {r['round']} 와 같다. 멈추고 보고한다"}
    note = "" if coef["view_r_mult"] == 1.0 else " (경계 반경 배수는 구현이 먼저 필요하다, PREREG 4절)"
    return {"action": "calibrate", "round": nxt,
            "reason": f"{rnd}: A·B 갈래 모두 통과한 후보 없음 → {nxt}: 경계 섭식 배수 {coef['eat_mult']:g}, "
                      f"경계 반경 ×{coef['view_r_mult']:g}{note}"}


def load_candidate(rnd: str, decay: float, out: Path | None = None, threshold: float = 0.5) -> dict:
    """후보 디렉터리의 결과를 읽어 판정한다. 모자란 결과는 missing 에 적는다."""
    out = OUT if out is None else out
    d = out / rnd / cand_name(decay)
    names = ["a_forbid", "a_allow", "b_forbid", "b_allow", "e2b_vig", "e2b_run", "tf/e2b_run18", "e2b_tab_vig",
             "e2b_tab_run", "g998/a_forbid", "g998/a_allow", "g998/b_forbid", "g998/b_allow", "g998/e2b_vig",
             "g998/e2b_run"]
    r = {n: load_json(d / f"{n}.json") for n in names}
    info = dict(cand=cand_name(decay), decay=float(decay), window=window_steps(decay),
                half_life=math.log(0.5) / math.log(decay), missing=[n for n in names if r[n] is None])
    core = ["a_forbid", "a_allow", "b_forbid", "b_allow", "e2b_vig", "e2b_run"]
    if any(r[n] is None for n in core):
        return info
    info["A"] = judge_e2a(r["a_allow"], r["a_forbid"], threshold, r["g998/a_allow"], r["g998/a_forbid"])
    info["B"] = judge_e2a(r["b_allow"], r["b_forbid"], threshold, r["g998/b_allow"], r["g998/b_forbid"])
    info["E2b"] = judge_e2b(r["e2b_vig"], r["e2b_run"], r["g998/e2b_vig"], r["g998/e2b_run"])
    info["t18"] = judge_t18(r["e2b_vig"], r["e2b_run"], r["tf/e2b_run18"]) if r["tf/e2b_run18"] else None
    info["E2b_tab"] = (judge_e2b(r["e2b_tab_vig"], r["e2b_tab_run"])
                       if r["e2b_tab_vig"] and r["e2b_tab_run"] else None)
    info["tables"] = {"a_allow": r["a_allow"]["best"], "b_forbid": r["b_forbid"]["best"],
                      "b_allow": r["b_allow"]["best"]}
    vs = {}
    for n in ("a_forbid", "a_allow", "b_forbid", "b_allow", "e2b_vig", "e2b_run", "e2b_tab_vig", "e2b_tab_run"):
        if r[n] is not None:
            vs[n] = {c: mean_of(r[n], c) for c in VIGIL_SHOW + GAIT_SHOW}
    info["vigil"] = vs
    info["a_forbid_g"] = [_f(x["g_gamma"]) for x in rows_of(r["a_forbid"])]
    info["a_forbid_seeds"] = [x["seed"] for x in rows_of(r["a_forbid"])]
    info["base_ok"] = _check_bases(r)
    rj = load_json(d / "run.json") or {}
    info["commands"] = [s["command"] for s in rj.get("steps", [])]
    info["elapsed_s"] = sum(s.get("elapsed_s", 0) for s in rj.get("steps", []))
    return info


VIGIL_SHOW = ["vig_frac", "seg_seen_frac", "seg_recent_frac", "seg_calm_frac", "p_vig_seen", "p_vig_recent",
              "p_vig_calm", "b3", "b3_narrow", "b3_truth", "b4_narrow", "b4_narrow_n", "b4_wide", "b5p_pred_narrow",
              "b5p_truth", "b8_vig", "obs_wide_frac", "threat_mean"]
GAIT_SHOW = ["stop_frac", "walk_frac", "run_frac", "stall_frac", "hungry_frac", "starve_share", "b1", "b2", "b8"]


def _check_bases(r: dict) -> bool:
    """정책 구성이 PREREG 2절과 같은지: A·B 허용의 바탕 = C2, 금지의 바탕 = C2 + vigilance 0, E2b 바탕·표."""
    fa = [float(x) for x in r["a_forbid"]["best"]]
    c2 = [float(x) for x in r["a_allow"]["base_action"]]
    ok = fa == forbid_action(c2)
    ok &= [float(x) for x in r["b_forbid"]["base_action"]] == fa
    ok &= [float(x) for x in r["b_allow"]["base_action"]] == c2
    for arm in ("vig", "run"):
        e = r[f"e2b_{arm}"]
        ok &= [float(x) for x in e["base_action"]] == e2b_base(c2)
        ok &= [float(x) for x in e["best"]] == e2b_table(c2, arm)
    return bool(ok)


def load_round(rnd: str, out: Path | None = None) -> dict | None:
    """회차의 C2 와 후보들을 읽어 판정한다. 끝나지 않은 후보는 incomplete 로 둔다."""
    out = OUT if out is None else out
    if not config_path(rnd, PROPOSAL_DECAY, out).exists():
        return None
    from env_v2.config import load_v2_config
    from env_v2.world import World
    thr = World(load_v2_config(config_path(rnd, PROPOSAL_DECAY, out)), seeds=[0])._vg["threshold"]
    c2 = load_json(out / rnd / "c2" / "constsearch.json")
    res = dict(round=rnd, coef=ROUND_COEF[rnd], c2=None, cands={}, incomplete=[])
    if c2 is None:
        res["incomplete"].append("c2")
        return res
    res["c2"] = dict(best=c2["best"], **{k: mean_of(c2, k) for k in OUTCOME_COLS},
                     **{k: mean_of(c2, k) for k in ("vig_frac", "walk_frac", "stop_frac", "run_frac", "starve_share",
                                                     "hungry_frac", "b1", "b2")},
                     search=c2.get("search", {}).get("rescore"))
    c2_g = [_f(x["g_gamma"]) for x in rows_of(c2)]
    for decay in DECAYS:
        info = load_candidate(rnd, decay, out, thr)
        if "A" not in info:
            res["incomplete"].append(info["cand"])
        else:
            # 상수의 G_γ 는 감쇠와 무관하다(PREREG 2절): A-금지가 C2(vigilance ≤ 문턱이면 같은 세계)와 비트 단위로 같다
            same_world = float(c2["best"][A_VIG]) <= thr
            info["c2_check"] = (info["a_forbid_g"] == c2_g) if same_world else None
        res["cands"][info["cand"]] = info
    if not res["incomplete"]:
        res["selected_A"] = select(res["cands"], "A")
        res["selected_B"] = select(res["cands"], "B")
    return res


# --------------------------------------------------------------------- #
# 판정표
# --------------------------------------------------------------------- #


def f3(x, nd=3) -> str:
    return "—" if x is None or not math.isfinite(float(x)) else f"{float(x):.{nd}f}"


def ok(b) -> str:
    return "통과" if b else "실패"


def _states(s) -> str:
    return "·".join("경계" if x else "—" for x in s)


def _gait(v: float) -> str:
    return "정지" if v < 1 / 3 else ("걷기" if v < 2 / 3 else "뛰기")


def md_round(r: dict) -> list[str]:
    L = [f"## {ROUND_LABEL.get(r['round'], r['round'])}", ""]
    if r["c2"]:
        c = r["c2"]
        L += [f"- C2 (감쇠와 무관, 6차원 112 trial): [{', '.join(f'{x:.3f}' for x in c['best'])}] — 보행 "
              f"{_gait(c['best'][A_SPEED])}, 경계 {'켬' if c['best'][A_VIG] > 0.5 else '끔'}. G_γ {f3(c['g_gamma'])}, "
              f"수명 {f3(c['survival'], 1)}, 피식률 {f3(c['predation_rate'], 5)}, 아사율 {f3(c['starve_rate'], 5)}, "
              f"걷기 {f3(c['walk_frac'])}", ""]
    if r["incomplete"]:
        L += [f"- 끝나지 않은 것: {', '.join(r['incomplete'])}", ""]
    cands = {k: v for k, v in r["cands"].items() if "A" in v}
    if not cands:
        return L
    L += ["### E2a (판정 = A 갈래: 구간별 vigilance + 바탕 C2 vs C2·vigilance 0, 5.0 공통 규칙과 같다)", "",
          "| 후보 | 반감기 (K) | A 구간별 경계 [평시·최근·보임] | G_γ 금지 → 허용 (Δ, t) | (i) | (ii) | 경계 비율 | (iii) | "
          "G_0.998 Δ (t) | A 판정 |", "|---" * 10 + "|"]
    for k, v in cands.items():
        a = v["A"]
        g9 = a.get("g998")
        g9s = "—" if not g9 else f"{g9['diff']:+.3f} ({g9['t']:+.2f})"
        L.append(f"| {k} | {v['half_life']:.1f} ({v['window']}) | {_states(a['states'])} "
                 f"({', '.join(f'{x:.2f}' for x in a['vig'])}) | {f3(a['outcome']['g_gamma']['forbid'])} → "
                 f"{f3(a['outcome']['g_gamma']['allow'])} ({a['diff']:+.3f}, {a['t']:+.2f}) | {ok(a['higher'])} | "
                 f"{ok(a['distinct'])} | {f3(a['vig_frac'])} | {ok(a['frac_ok'])} | {g9s} | "
                 f"**{'PASS' if a['pass'] else 'FAIL'}** |")
    L += ["", "### E2a B 갈래 (보고·멈춤 조건: 보행도 구간별 — 경계 허용 speed+vigilance vs 경계 금지 speed)", "",
          "| 후보 | B-금지 보행 [평시·최근·보임] | B-허용 보행 / 경계 | G_γ 금지 → 허용 (Δ, t) | (i) | (ii) | 경계 비율 | (iii) | "
          "G_0.998 Δ (t) | B 판정 |", "|---" * 10 + "|"]
    for k, v in cands.items():
        b = v["B"]
        g9 = b.get("g998")
        g9s = "—" if not g9 else f"{g9['diff']:+.3f} ({g9['t']:+.2f})"
        L.append(f"| {k} | {'·'.join(_gait(x) for x in b['forbid_speed'])} | "
                 f"{'·'.join(_gait(x) for x in b['speed'])} / {_states(b['states'])} | "
                 f"{f3(b['outcome']['g_gamma']['forbid'])} → {f3(b['outcome']['g_gamma']['allow'])} "
                 f"({b['diff']:+.3f}, {b['t']:+.2f}) | {ok(b['higher'])} | {ok(b['distinct'])} | {f3(b['vig_frac'])} | "
                 f"{ok(b['frac_ok'])} | {g9s} | **{'PASS' if b['pass'] else 'FAIL'}** |")
    L += ["", "### E2b ('최근 위협·안 보임' 구간에서 경계 V vs 계속 뛰기 R. 평시 = C2 보행, 보임 = 뛰기·도주 분기 1.0)", "",
          "| 후보 | G_γ R → V (Δ, t) | 피식률 R → V (Δ, t) | 수명 R → V | 아사율 R → V | G_0.998 Δ (t) | E2b 판정 |",
          "|---" * 7 + "|"]
    for k, v in cands.items():
        e = v["E2b"]
        o = e["outcome"]
        g9 = e.get("g998")
        g9s = "—" if not g9 else f"{g9['diff']:+.3f} ({g9['t']:+.2f})"
        L.append(f"| {k} | {f3(e['g']['run'])} → {f3(e['g']['vig'])} ({e['g']['diff']:+.3f}, {e['g']['t']:+.2f}) | "
                 f"{f3(e['pred']['run'], 5)} → {f3(e['pred']['vig'], 5)} ({e['pred']['diff']:+.5f}, "
                 f"{e['pred']['t']:+.2f}) | {f3(o['survival']['run'], 1)} → {f3(o['survival']['vig'], 1)} | "
                 f"{f3(o['starve_rate']['run'], 5)} → {f3(o['starve_rate']['vig'], 5)} | {g9s} | "
                 f"**{'PASS' if e['pass'] else 'FAIL'}** |")
    L += ["", "### 보고 (판정 아님): #18 변형, E2b-표", "",
          "| 후보 | R18 G_γ | R18 − V G_γ (t) | R18 − R G_γ (t) | R18 − V 피식률 (t) | #18 크게 이김 | "
          "E2b-표 G_γ R → V (Δ, t) | E2b-표 피식률 Δ (t) |", "|---" * 8 + "|"]
    for k, v in cands.items():
        t18, tb = v.get("t18"), v.get("E2b_tab")
        if t18:
            s18 = (f"{f3(t18['run18']['g_gamma'])} | {t18['vs_vig']['g_gamma']['diff']:+.3f} "
                   f"({t18['vs_vig']['g_gamma']['t']:+.2f}) | {t18['vs_run']['g_gamma']['diff']:+.3f} "
                   f"({t18['vs_run']['g_gamma']['t']:+.2f}) | {t18['vs_vig']['predation_rate']['diff']:+.5f} "
                   f"({t18['vs_vig']['predation_rate']['t']:+.2f}) | {'예' if t18['big_win'] else '아니오'}")
        else:
            s18 = "— | — | — | — | —"
        stb = (f"{f3(tb['g']['run'])} → {f3(tb['g']['vig'])} ({tb['g']['diff']:+.3f}, {tb['g']['t']:+.2f}) | "
               f"{tb['pred']['diff']:+.5f} ({tb['pred']['t']:+.2f})") if tb else "— | —"
        L.append(f"| {k} | {s18} | {stb} |")
    L += ["", "### 보조 지표 (판정 아님, 평가 시드 평균. 360° 치우침 주의: World.vigil_stats)", "",
          "| 후보 | 정책 | 경계 | 구간 보임 / 최근 / 평시 | P(경계) 보임 / 최근 / 평시 | b3_narrow | b3_truth | b4_narrow (n) | "
          "정지 / 걷기 / 뛰기 | 아사 비중 | B1 | B2 |", "|---" * 12 + "|"]
    for k, v in cands.items():
        for n in ("a_forbid", "a_allow", "b_forbid", "b_allow", "e2b_vig", "e2b_run"):
            m = v["vigil"].get(n)
            if not m:
                continue
            L.append(f"| {k} | {n} | {f3(m['vig_frac'])} | {f3(m['seg_seen_frac'])} / {f3(m['seg_recent_frac'])} / "
                     f"{f3(m['seg_calm_frac'])} | {f3(m['p_vig_seen'])} / {f3(m['p_vig_recent'])} / "
                     f"{f3(m['p_vig_calm'])} | {f3(m['b3_narrow'])} | {f3(m['b3_truth'])} | {f3(m['b4_narrow'])} "
                     f"({f3(m['b4_narrow_n'], 0)}) | {f3(m['stop_frac'])} / {f3(m['walk_frac'])} / {f3(m['run_frac'])} | "
                     f"{f3(m['starve_share'])} | {f3(m['b1'])} | {f3(m['b2'])} |")
    L.append("")
    checks = [f"{k} 바탕 {'맞음' if v['base_ok'] else '틀림'}, C2 비트 일치 "
              f"{'—' if v.get('c2_check') is None else ('맞음' if v['c2_check'] else '틀림')}" for k, v in cands.items()]
    L.append("- 구성 검사(PREREG 2절): " + "; ".join(checks))
    if "selected_A" in r:
        L.append(f"- 회차 선택: A 갈래 {r['selected_A'] or '없음'}, B 갈래 {r['selected_B'] or '없음'}")
    return L


def judge_all(out: Path | None = None) -> tuple[dict, list[str]]:
    """모든 회차를 판정한다 → (판정 json 내용, 판정표 md 줄). 파일은 쓰지 않는다."""
    out = OUT if out is None else out
    history, rounds = [], {}
    for rnd in ROUNDS:
        r = load_round(rnd, out)
        if r is None:
            break
        rounds[rnd] = r
        if r["incomplete"]:
            break
        history.append(r)
        r["next"] = next_round(history)
        if r["next"]["action"] != "calibrate":
            break
    final = None
    if history and not history[-1]["incomplete"]:
        last = history[-1]
        nx = last["next"]
        if nx["action"] == "pass":
            k = last["selected_A"]
            c = last["cands"][k]
            final = dict(E2a="PASS", round=last["round"], cand=k, decay=c["decay"], theta=THETA,
                         window=c["window"], eat_mult=last["coef"]["eat_mult"],
                         view_r_mult=last["coef"]["view_r_mult"], c2=last["c2"]["best"],
                         a_allow=c["tables"]["a_allow"], b_allow=c["tables"]["b_allow"],
                         E2b="PASS" if c["E2b"]["pass"] else "FAIL", e2b_cand=k)
        elif nx["action"] == "stop":
            k = last.get("selected_B")
            final = dict(E2a="FAIL", round=last["round"], reason=nx["reason"])
            if k:
                c = last["cands"][k]
                final.update(cand_B=k, decay_B=c["decay"], E2b="PASS" if c["E2b"]["pass"] else "FAIL",
                             e2b_cand=k)
            else:
                e = last["cands"].get(cand_name(PROPOSAL_DECAY), {}).get("E2b")
                final.update(E2b=None if e is None else ("PASS" if e["pass"] else "FAIL"),
                             e2b_cand=cand_name(PROPOSAL_DECAY), e2b_note="E2a 실패 — E2b 는 제안 후보(0.95) 값을 보고만")
    data = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "theta": THETA,
            "decays": list(DECAYS), "t_crit": T_CRIT, "vig_frac_range": list(VIG_FRAC_RANGE),
            "rounds": rounds, "final": final}
    L = ["# Gate E2 판정표 (gate_e2.py judge 가 만든다. 손으로 고치지 않는다)", "",
         "- 사전 등록: `results/v2/e2/PREREG.md`. 평가 시드 10000~10019 × 5000스텝, 결정적 상수 정책, G_γ 는 γ_train"
         "(0.9917), 괄호 t 는 평가 시드 짝지은 t(자유도 19, 기준 2.093)",
         f"- 구간(관측 7 threat_recency, θ {THETA:g}): s0 평시(tr < θ), s1 최근 위협·안 보임(θ ≤ tr < 1), s2 포식자 보임"
         "(tr = 1). K = 놓친 뒤 최근 위협에 머무는 스텝 수",
         f"- E2a 기준(갈래마다): (i) 허용 G_γ 가 금지보다 높고 t > {T_CRIT} (ii) 구간별 경계 상태가 둘 이상 (iii) 허용의 "
         f"경계 비율 {VIG_FRAC_RANGE[0]}~{VIG_FRAC_RANGE[1]}. 판정 갈래는 A, B 는 멈춤 조건",
         "- E2b 기준: 경계(V)가 계속 뛰기(R)보다 G_γ 에서 유의하게 높고(t > 2.093) 피식률에서 유의하게 낮다(t < −2.093)", ""]
    for r in rounds.values():
        L += md_round(r)
        if "next" in r:
            L.append(f"- 다음: {r['next']['action']} — {r['next']['reason']}")
        L.append("")
    if final:
        L += ["## 종합", ""]
        if final["E2a"] == "PASS":
            L.append(f"- **E2a PASS** ({final['round']}, {final['cand']}: decay {final['decay']:g}, θ {THETA:g}, "
                     f"K {final['window']}, 경계 섭식 {final['eat_mult']:g}, 반경 ×{final['view_r_mult']:g})")
        else:
            L.append(f"- **E2a FAIL** ({final['round']}) — {final['reason']}")
        if final.get("E2b"):
            L.append(f"- **E2b {final['E2b']}** (후보 {final['e2b_cand']}){'. ' + final['e2b_note'] if final.get('e2b_note') else ''}")
        L.append("")
    return data, L


def cmd_judge(args) -> int:
    out = Path(args.out) if args.out else OUT
    data, L = judge_all(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "judge_e2.json").write_text(json.dumps(data, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    (out / "judge_e2.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--out", default=None, help="출력 디렉터리. 기본 results/v2/e2 (시험 실행은 다른 곳에)")
    p = argparse.ArgumentParser(description="Gate E2 — v2.2 경계 행동 게이트 (계획서 1-5)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("configs", parents=[common], help="회차의 감쇠 후보 설정(+ #18 변형) yaml 을 만든다")
    s.add_argument("--round", required=True, choices=ROUNDS)
    s = sub.add_parser("run", parents=[common], help="C2 또는 후보 하나를 돌린다 (끊기면 같은 명령으로 이어 간다)")
    s.add_argument("--round", required=True, choices=ROUNDS)
    s.add_argument("--c2", action="store_true", help="회차의 C2 (후보보다 먼저)")
    s.add_argument("--cand", default=None, help=f"후보 이름: {', '.join(cand_name(d) for d in DECAYS)}")
    s.add_argument("--workers", type=int, default=6)
    s.add_argument("--smoke", action="store_true", help="도구 시험(작은 조건). --out 을 결과 디렉터리 밖으로 준다")
    sub.add_parser("judge", parents=[common], help="모든 회차를 판정해 판정표(judge_e2.json·md)를 만든다")
    return p


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:  # pragma: no cover
        pass
    args = build_parser().parse_args(argv)
    return {"configs": cmd_configs, "run": cmd_run, "judge": cmd_judge}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())

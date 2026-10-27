"""r7e_game.py analyze — 판마다 기록 줄(.ecov3.log)·사슴 줄(.deer.npz)·스냅숏(it 만)을 읽어 지역 기록을 만들고, 맵·두뇌마다 합·세션 짝 차이를 낸다.

셈 (몫은 모두 '전체 합의 비' — 세션·지역 셋을 더한 뒤 나눈다. 세션 짝은 세션마다(지역 셋 합) R7e − 지금, 평균·표준편차·t):
  결과   잡힌 몫 = Σ잡힘 ÷ Σ사슴(입양, 팀 life 출생 포함), 굶은 몫, 처음 30·60 초 잡힘(세션당 지역 셋 합 마리), 늑대 사냥 성공률 = Σ성공 ÷ Σ끝난 사냥
  도망   사건 숨음 비율 = Σ숨은 사건 ÷ Σ쫓긴 사건 (숨음 = 은신처 끝 + 10 초 안 잡힘·다시 안 뜀 — 지켜보는 중 포함, 8e5417f 와 같은 셈),
         사건 잡힘 비율, GF = 1000 × Σ도망 시작 ÷ Σ산 사슴-스텝, GE = 사건 시작(= 도망 시작 − 이어진 도망), 달린 시간 = Σ실행 FLEE 스텝 × 2/15 초 ÷ Σ도망 시작,
         스스로 벗어난 도망의 쫓긴 시간(기록 누적 줄 — 0.1 초 반올림), 도망 끝 까닭 몫(10 초 줄 구간 합), 이어진 도망 몫 = Σ이어진 도망 ÷ Σ도망 시작
         ('도망이 끝나고 곧 또 뜀' — 사건 묶기 규칙의 이음), 길(R7e): 반사 길 스텝 가운데 SHELTER(누적 줄 % × 스텝 — 1 % 반올림, it 은 스냅숏 정확값도),
         SHELTER 가 열린 결정 가운데 SHELTER 고름
  평소   행동 몫 = 10 초 줄 '구간 사용(개체·스텝)' 합 (먹기·도망·숨기·얼기·잠 — v3 에 '쉬기' 행동은 없다. 쉬는 늑대 곁 '거리 두기'·경계·웅크림은 반사 덮기 몫으로 따로),
         은신처 안 사슴-스텝 몫(세계 셈), 무리 = 1 초(8 스텝)마다 산 사슴끼리 가장 가까운 이웃 거리 평균(m)·10 m 안 이웃 수 평균·10 m 안 이웃 없는 몫
  이상   빙빙 = 10-27 고침 측정(ba53b6f '빙빙 3.17% → 0.04%')과 같은 대리 정의 — 평소(이 스텝과 앞 38 스텝 위협 안 봄, 이동 ≤ 0.25 단위) 스텝 가운데
           8 스텝 창에서 135° 넘는 뒤집힘 ≥ 2 이고 자리 이동 < 1 단위인 스텝 몫, 평소 뒤집힘 / 1000 평소 스텝
         쉬는 늑대 시야 안 멈춤 = 기록 줄 '쉬는 늑대 시야' 누적 멈춤 ÷ 산 사슴-스텝 (ba53b6f '3.05% → 0.12%' 와 같은 셈)
         은신처 들락날락 = 사슴 자리로 은신처 원(반지름 6 단위 = 12 m) 안팎을 세어 — 나간 뒤 5 초(38 스텝) 안 다시 들어감 ÷ 나감, 1 초(8 스텝) 안 ÷ 나감,
           2 초(15 스텝) 이하 머묾 ÷ 끝난 머묾
         멈춤·끼임 = 은신처 밖에서 보이는 늑대 15 m(7.5 단위) 안인데 1 초(8 스텝) 넘게 이동 < 2 cm(0.01 단위)인 일 / 1000 '늑대 15 m 안·은신처 밖' 스텝,
           그 가운데 벽(가장자리 0.5 단위 안)·나무(줄기 원판 가장자리 0.3 단위 안) 붙은 일. 지형 막힘(사슴)·줄기 닿음은 기록 줄 셈
         달리기 방향 떨림 = 이어진 두 '빠른'(이동 > 0.25 단위) 스텝의 이동 방향이 135° 넘게 바뀐 몫 / 1000 빠른 스텝 짝
  두뇌   결정 수 = '[EcoV3Obs] <지역> 결정' 줄 사슴·스텝 누적, 마스크 위반 누적, 반사 밖 두뇌 FLEE 몫(판 5 는 0 이어야)
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import numpy as np

STEP_S = 2.0 / 15.0
SIZE = 60.0
COVERS = np.array([[15.0, 15.0], [45.0, 15.0], [15.0, 45.0], [45.0, 45.0]])
COVER_R = 6.0
BEH = ("먹기", "도망", "숨기", "얼기", "잠")
CAUSES = ("은신처", "나무", "시야각 밖", "시야 밖", "다른 사슴으로", "사냥 그만둠", "끝까지 쫓김", "안 쫓김", "잡힘", "굶음")
REGIONS = ("Barren", "Forest", "Highland")
PREV = dict(it240=("11.47%", "20.69%", "+9.22 %p"), jyu_control=("11.55%", "20.90%"), jyu_full240=("17.08%", "32.91%"))

R_MAIN = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) \| ([\d.]+)초 .*?\| 사슴 산 (\d+)/(\d+) \| 지금 행동:.*? \| 구간 사용\(개체·스텝\):(.*?) \| 늑대 (\d+):"
                    r".*?\| 포획 (\d+) \(누적 (\d+)\) 굶음 (\d+) \(누적 (\d+)\) \| 먹이: 구간 먹은 양 ([\d.]+) .*?무대 먹이 처음의 ([\d.]+)% · 사슴 에너지 평균 ([\d.]+)%"
                    r".*?\| 지형 검사 이동 (\d+), 막힘 사슴 (\d+) 늑대 (\d+) \| .*?마스크 위반 (\d+)")
R_BEH = re.compile(r"(먹기|도망|숨기|얼기|잠) (\d+)")
R_KEEP = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 경계 거리 \| ([\d.]+)초 \|.*?\| 구간 경계\(멀어짐\) 시작 (\d+) · 도망 시작 (\d+) · 은신처 웅크림 시작 (\d+) \| "
                    r"덮기 개체·스텝 경계 (\d+) 도망 (\d+) 웅크림 (\d+) \(두뇌 (\d+)\) \| 끝난 도망 (\d+) \(은신처에서 (\d+)\), 평균 [\d.]+초 · 도망 중 죽음 (\d+) \| "
                    r"잡힌 사슴 (\d+): 경계 중 (\d+) · 도망 중 (\d+) · 웅크림 중 (\d+) · 덮기 밖 (-?\d+) \|.*?은신처 안 잡힘 \d+ \(누적 (\d+)\)")
R_RESTKEEP = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 거리 두기 \| ([\d.]+)초 \|.*?\| 구간 시작 (\d+) · 끝 (\d+) · 개체·스텝 (\d+) · 그 중 잡힘 (\d+) \| "
                        r"띠가 방향을 바꾼 개체·스텝 (\d+) \(멈춤 (\d+)\)")
R_RESTVIEW = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 쉬는 늑대 시야 \| ([\d.]+)초 \|.*?누적 (\d+) 중 시야 안 (\d+) \([\d.]+%\) · 멈춤 (\d+)")
R_HUNT = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 사냥·은신처 \| ([\d.]+)초 \| 사냥 누적: 시작 (\d+) · 끝 (\d+) · 성공 (\d+) · 사냥 밖 포획 (\d+)"
                    r".*?은신처 안 사슴·스텝: 구간 \d+/\d+ \([\d.]+%\) · 누적 (\d+)/(\d+)")
R_OBST = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 장애물 \| ([\d.]+)초 \| 원판 (\d+) .*?누적 사슴·스텝 (\d+): 닿음 (\d+) .*?늑대·스텝 (\d+): 닿음 (\d+)")
R_WX = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 날씨 \| ([\d.]+)초 \| .*?날씨 스텝 누적 맑음 (\d+) · 비 (\d+) · 눈 (\d+)")
R_BRAIN = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 두뇌 \| ([\d.]+)초 \| 두뇌 (\S+).*?\| 구간 두뇌 스텝\(도주 반사 밖\) (\d+): (.*?) \| 그중 늑대를 앎 (\d+): (.*?) \| "
                     r"반사 스텝 (\d+) \(늑대를 앎 (\d+)\)")
R_ROUTE = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 길 \| ([\d.]+)초 \| (.*?) \| 구간 .*? \| 누적 (?:길 RUN (\d+)% · 은신처 (\d+)% \(반사 사슴-스텝 (\d+)\)|길 반사 스텝 없음)"
                     r" · 길 결정 (\d+) · 은신처 고름 (\d+)/(\d+) \(열린 결정\) · 무효 (\d+) · 도주 시작 (\d+) · 바꿈 (\d+)")
R_FLIGHT = re.compile(r"\[EcoV3I\] (Barren|Forest|Highland) 도망 \| ([\d.]+)초 \| 구간 시작 (\d+) · 끝 (\d+) \(스스로: (.*?)\) · 평균 ([\d.]+)초 · "
                      r"스스로 벗어난 도망 (\d+)번 쫓긴 ([\d.]+)초 \|.*?누적 시작 (\d+) · 끝 (\d+) · 열린 (\d+) · 스스로 벗어남 (\d+) \([\d.]+%\) 쫓긴 ([\d.]+)초 · "
                      r"은신처 원 안에서 끝 (\d+) · 반사 스텝 (\d+)/(\d+) · 쫓긴 도망 (\d+) 중 숨음 (\d+) \(지켜보는 중 (\d+)\) · 숨은 뒤 10초 안 잡힘 (\d+)·굶음 (\d+) · "
                      r"쫓긴 사건 (\d+) 중 숨음 (\d+) \(지켜보는 중 (\d+)\) · 잡힘 (\d+) · 굶음 (\d+) · 잘림 (\d+) · 이어진 도망 (\d+)")
R_CAUSE = re.compile(r"(은신처|나무|시야각 밖|시야 밖|다른 사슴으로|사냥 그만둠|끝까지 쫓김|안 쫓김|잡힘|굶음) (\d+)")
R_DEC = re.compile(r"\[EcoV3Obs\] (Barren|Forest|Highland) 결정 \| t (\d+) \| 사슴·스텝 (\d+) \| 지문 ([0-9a-f]+)")
R_START = re.compile(r"\[EcoV3I\] 두뇌 시작 \| [\d.]+초 \(전역 스텝 (\d+)\) \| (\S+) \((.*?)\)")


def _close(a: float, b: float) -> bool:
    return abs(a - b) < 1e-6


# --------------------------------------------------------------------- #
# 기록 줄 → 지역 기록
# --------------------------------------------------------------------- #


def parse_log(path: Path, t_end: float) -> dict:
    txt = Path(path).read_text(encoding="utf-8", errors="replace")
    lines = txt.splitlines()
    regs = {r: dict(region=r, beh=[0] * 5, causes=[0] * len(CAUSES), brain_beh=[0] * 5, brain_know_beh=[0] * 5, brain_steps=0, brain_know=0,
                    brain_reflex=0, brain_ids=set(), keep_alert=0, keep_flee=0, keep_crouch=0, keep_brain=0, alert_starts=0, panic_starts=0,
                    crouch_starts=0, restkeep_steps=0, restkeep_starts=0, restband_turn=0, restband_stop=0, terr_moves=0, terr_deer=0,
                    terr_wolf=0, eaten=0.0, int_ended=0, int_own_n=0, int_own_s=0.0, int_len_s=0.0, caught_by_keep=[0, 0, 0, 0])
            for r in REGIONS}
    seen_t = {r: set() for r in REGIONS}
    dec = {r: (0, 0, "") for r in REGIONS}
    T_end_steps = int(round(t_end / STEP_S))
    for s in lines:
        if "[EcoV3" not in s:
            continue
        m = R_MAIN.search(s)
        if m:
            reg, t = m.group(1), float(m.group(2))
            R = regs[reg]
            if t <= t_end + 1e-6:
                for b, n in R_BEH.findall(m.group(5)):
                    R["beh"][BEH.index(b)] += int(n)
                R["terr_moves"] += int(m.group(14))
                R["terr_deer"] += int(m.group(15))
                R["terr_wolf"] += int(m.group(16))
                R["eaten"] += float(m.group(11))
            for tt, key in ((30.0, "caught30"), (60.0, "caught60"), (240.0, "caught240")):
                if _close(t, tt):
                    R[key] = int(m.group(8))
            if _close(t, 240.0):
                R["n240"] = int(m.group(4))
            if _close(t, t_end):
                R.update(alive=int(m.group(3)), n=int(m.group(4)), wolves=int(m.group(6)), caught=int(m.group(8)), starved=int(m.group(10)),
                         food_pct=float(m.group(12)), energy_pct=float(m.group(13)), mask_viol=int(m.group(17)))
                seen_t[reg].add("main")
            continue
        m = R_KEEP.search(s)
        if m:
            R = regs[m.group(1)]
            if float(m.group(2)) <= t_end + 1e-6:
                g = [int(x) for x in m.groups()[2:]]
                R["alert_starts"] += g[0]; R["panic_starts"] += g[1]; R["crouch_starts"] += g[2]
                R["keep_alert"] += g[3]; R["keep_flee"] += g[4]; R["keep_crouch"] += g[5]; R["keep_brain"] += g[6]
                for k in range(4):
                    R["caught_by_keep"][k] += g[11 + k] if k < 3 else g[14]
            if _close(float(m.group(2)), t_end):
                R["caught_in_cover"] = int(m.group(18))
                seen_t[m.group(1)].add("keep")
            continue
        m = R_RESTKEEP.search(s)
        if m:
            R = regs[m.group(1)]
            if float(m.group(2)) <= t_end + 1e-6:
                R["restkeep_starts"] += int(m.group(3)); R["restkeep_steps"] += int(m.group(5))
                R["restband_turn"] += int(m.group(7)); R["restband_stop"] += int(m.group(8))
            continue
        m = R_RESTVIEW.search(s)
        if m:
            if _close(float(m.group(2)), t_end):
                regs[m.group(1)].update(rv_live=int(m.group(3)), rv_in=int(m.group(4)), rv_stop=int(m.group(5)))
            continue
        m = R_HUNT.search(s)
        if m:
            t = float(m.group(2))
            if _close(t, 240.0):
                regs[m.group(1)].update(live240=int(m.group(8)))
            if _close(t, t_end):
                regs[m.group(1)].update(hunt_starts=int(m.group(3)), hunt_ends=int(m.group(4)), hunt_success=int(m.group(5)), hunt_outside=int(m.group(6)),
                                        shelter_steps=int(m.group(7)), live=int(m.group(8)))
                seen_t[m.group(1)].add("hunt")
            continue
        m = R_OBST.search(s)
        if m:
            if _close(float(m.group(2)), t_end):
                regs[m.group(1)].update(discs=int(m.group(3)), obst_deer_steps=int(m.group(4)), obst_deer_hit=int(m.group(5)),
                                        obst_wolf_steps=int(m.group(6)), obst_wolf_hit=int(m.group(7)))
            continue
        m = R_WX.search(s)
        if m:
            if _close(float(m.group(2)), t_end):
                regs[m.group(1)].update(wx_clear=int(m.group(3)), wx_rain=int(m.group(4)), wx_snow=int(m.group(5)))
            continue
        m = R_BRAIN.search(s)
        if m:
            R = regs[m.group(1)]
            if float(m.group(2)) <= t_end + 1e-6:
                R["brain_ids"].add(m.group(3))
                R["brain_steps"] += int(m.group(4))
                for b, n in re.findall(r"(먹기|도망|숨기|얼기|잠) (\d+) \(", m.group(5)):
                    R["brain_beh"][BEH.index(b)] += int(n)
                R["brain_know"] += int(m.group(6))
                for b, n in re.findall(r"(먹기|도망|숨기|얼기|잠) (\d+) \(", m.group(7)):
                    R["brain_know_beh"][BEH.index(b)] += int(n)
                R["brain_reflex"] += int(m.group(8))
            continue
        m = R_ROUTE.search(s)
        if m:
            if _close(float(m.group(2)), t_end):
                S = int(m.group(6) or 0)
                regs[m.group(1)].update(route_mode=m.group(3), rt_steps=S, rt_shelter_pct=int(m.group(5) or 0), rt_shelter_est=round(S * int(m.group(5) or 0) / 100),
                                        rt_decisions=int(m.group(7)), rt_picked_shelter=int(m.group(8)), rt_choice=int(m.group(9)), rt_invalid=int(m.group(10)),
                                        rt_onsets=int(m.group(11)), rt_switches=int(m.group(12)))
            continue
        m = R_FLIGHT.search(s)
        if m:
            reg, t = m.group(1), float(m.group(2))
            R = regs[reg]
            if t <= t_end + 1e-6:
                for c, n in R_CAUSE.findall(m.group(5)):
                    R["causes"][CAUSES.index(c)] += int(n)
                ended = int(m.group(4))
                R["int_ended"] += ended
                R["int_len_s"] += ended * float(m.group(6))
                R["int_own_n"] += int(m.group(7))
                R["int_own_s"] += int(m.group(7)) * float(m.group(8))
            g = [int(x) if "." not in x else float(x) for x in m.groups()[8:]]
            cum = dict(started=g[0], ended=g[1], open=g[2], own_n=g[3], own_chase_s=g[4], shelter_end=g[5], reflex=g[6], flee=g[7], fl_chased=g[8],
                       fl_hidden=g[9], fl_watching=g[10], cover_caught=g[11], cover_starved=g[12], ep_chased=g[13], ep_hidden=g[14], ep_watching=g[15],
                       ep_caught=g[16], ep_starved=g[17], ep_truncated=g[18], ep_joined=g[19])
            if _close(t, 240.0):
                R["c240"] = cum
            if _close(t, t_end):
                R.update(cum)
                R["ep_started"] = cum["started"] - cum["ep_joined"]
                R["own_chase_steps"] = round(cum["own_n"] * cum["own_chase_s"] / STEP_S)
                seen_t[reg].add("flight")
            continue
        m = R_DEC.search(s)
        if m:
            t = int(m.group(2))
            if t <= T_end_steps and t >= dec[m.group(1)][0]:
                dec[m.group(1)] = (t, int(m.group(3)), m.group(4))
            continue
    for r in REGIONS:
        regs[r]["decisions_t"], regs[r]["decisions"], regs[r]["decision_hash"] = dec[r]
        regs[r]["brain_ids"] = sorted(regs[r]["brain_ids"])
        miss = {"main", "flight", "hunt", "keep"} - seen_t[r]
        if miss:
            raise ValueError(f"{path}: {r} 의 {t_end} 초 줄 없음 {sorted(miss)}")
    starts = [(int(x.group(1)), x.group(2), x.group(3)) for x in (R_START.search(s) for s in lines) if x]
    warn = [s for s in lines if ("LogEcoPolicyV3I: Warning" in s or "LogEcoPolicyV3I: Error" in s or "LogEcoV3Brain: Warning" in s
                                 or "LogEcoV3Brain: Error" in s)]
    meta = dict(brain_start=starts, brain_swaps=sum(1 for s in lines if "[EcoV3I] 두뇌 바꿈 |" in s), warnings=len(warn),
                warn_first=[w[w.find("Log"):][:200] for w in warn[:3]], env_changes=sum(1 for s in lines if "환경 바뀜 #" in s),
                life_lines=txt.count("[EcoLife]"), vegetation_enabled=txt.count("[EcoVegetation] Enabled"),
                migration_plans=len(set(re.findall(r"\[HerdMigration\] Plan=(\d+)", txt))), watcher_lines=sum(1 for s in lines if "파이썬 감시" in s),
                team_weather_start=sum(1 for s in lines if "시작 날씨 | 팀 날씨 출처" in s), snapshot_rejected=txt.count("rejected"),
                ecoadapt_mentions=txt.count("Saved/EcoAdapt"))
    return dict(regions=regs, meta=meta)


# --------------------------------------------------------------------- #
# 사슴 줄 → 자리 셈
# --------------------------------------------------------------------- #


def _ang(a, b):
    na = np.linalg.norm(a, axis=-1)
    nb = np.linalg.norm(b, axis=-1)
    ok = (na > 1e-9) & (nb > 1e-9)
    c = np.where(ok, (a * b).sum(-1) / np.where(ok, na * nb, 1), 1)
    return np.where(ok, np.degrees(np.arccos(np.clip(c, -1, 1))), np.nan)


def _runs(x: np.ndarray):
    """bool (T, N) 의 열마다 True 연속 구간 [(열, 시작, 길이)]."""
    out = []
    T, N = x.shape
    pad = np.zeros((1, N), bool)
    d = np.diff(np.vstack([pad, x, pad]).astype(np.int8), axis=0)
    for i in range(N):
        st = np.flatnonzero(d[:, i] == 1)
        en = np.flatnonzero(d[:, i] == -1)
        for a, b in zip(st, en):
            out.append((i, int(a), int(b - a)))
    return out


def grid(z, reg: str, T_end: int, discs: np.ndarray | None):
    t = z[f"{reg}_t"]
    keep = t <= T_end
    t = t[keep]
    ids = z[f"{reg}_id"][keep]
    ts = np.unique(t)
    uid, col = np.unique(ids, return_inverse=True)
    row = t - ts[0]
    T, N = int(ts[-1] - ts[0] + 1), len(uid)
    if len(ts) != T:
        raise ValueError(f"{reg}: 사슴 줄 스텝이 이어지지 않음")
    P = np.full((T, N, 2), np.nan)
    P[row, col] = z[f"{reg}_p"][keep]
    S = np.zeros((T, N), bool)
    S[row, col] = z[f"{reg}_seen"][keep] == 1
    J = np.full((T, N, 2), np.nan)
    J[row, col] = z[f"{reg}_j"][keep]
    Nd = np.full((T, N), np.inf)
    Nd[row, col] = z[f"{reg}_N"][keep]
    A = np.zeros((T, N), bool)
    A[row, col] = True
    return P, S, J, Nd, A


def position_stats(P, S, J, Nd, A) -> dict:
    T, N = A.shape
    P0 = np.nan_to_num(P)
    disp = P0[1:] - P0[:-1]
    dl = np.linalg.norm(disp, axis=-1)
    live = A[:-1] & A[1:]
    # --- 평소·빙빙 (ba53b6f 측정과 같은 대리 정의 — spin_ue.metrics) ---
    s = S[:-1].astype(int)
    cs = np.cumsum(np.vstack([np.zeros((1, N), int), s]), 0)
    win = cs[1:] - cs[np.maximum(np.arange(1, T) - 39, 0)]
    calm = live & (win == 0) & (dl <= 0.25)
    mv = dl > 1e-6
    pair = np.zeros_like(calm)
    pair[1:] = calm[1:] & calm[:-1] & mv[1:] & mv[:-1]
    ad = np.full(calm.shape, np.nan)
    ad[1:] = _ang(disp[1:], disp[:-1])
    flip = pair & (np.nan_to_num(ad) > 135)
    W = 8
    spin = np.zeros_like(calm)
    for t in range(W, T - 1):
        cnt = flip[t - W + 1:t + 1].sum(0)
        net = np.linalg.norm(P0[t + 1] - P0[t - W + 1], axis=-1)
        sp = (cnt >= 2) & (net < 1.0) & calm[t]
        spin[t - W + 1:t + 1] |= sp[None, :]
    # --- 달리기 방향 떨림 ---
    fast = live & (dl > 0.25)
    fpair = np.zeros_like(fast)
    fpair[1:] = fast[1:] & fast[:-1]
    fflip = fpair & (np.nan_to_num(ad) > 135)
    fturn90 = fpair & (np.nan_to_num(ad) > 90)
    # 핑퐁 = 빠른 뒤집힘이 3 스텝 넘게 잇달아 (달리며 한 걸음마다 거꾸로 — 구석·벽에 몰려 제자리에서 왔다 갔다). 시작 자리가 벽 1 단위(2 m) 안이면 벽 핑퐁
    pp = [r for r in _runs(fflip) if r[2] >= 3]
    wall1 = np.minimum(P0, SIZE - P0).min(-1) < 1.0
    pp_wall = sum(1 for (i, a, n) in pp if wall1[a, i])
    pp_long = sum(1 for (i, a, n) in pp if n >= 8)
    pp_deer = len({i for (i, a, n) in pp})
    # --- 은신처 들락날락 (스텝 끝 자리) ---
    #   눈에 보이는 들락날락만 센다: 원 안(< 6 단위)에 들어오면 '안', 원 밖으로 1 단위(2 m) 넘게 나가야 '밖' (가장자리에서 웅크린 채 몇 cm 흔들리는 것은 빼는 걸침).
    #   걸침 없는 원 가장자리 깜빡임(1 초 안 다시 들어감)은 따로 센다 (cover_flicker)
    dc = np.min(np.linalg.norm(P0[:, :, None, :] - COVERS[None, None, :, :], axis=-1), axis=-1)
    inside = A & (dc < COVER_R)
    entries = exits = quick5 = quick1 = stays = short2 = flicker = raw_exits = 0
    for i in range(N):
        a = np.flatnonzero(A[:, i])
        if len(a) < 2:
            continue
        seg = dc[a[0]:a[-1] + 1, i]
        x = inside[a[0]:a[-1] + 1, i].astype(np.int8)
        d = np.diff(x)
        ren, rex = np.flatnonzero(d == 1) + 1, np.flatnonzero(d == -1) + 1
        raw_exits += len(rex)
        for e in ren:
            prev = rex[rex < e]
            flicker += bool(len(prev)) and (e - prev[-1]) <= 8
        st = bool(seg[0] < COVER_R)
        en, ex = [], []
        for k in range(1, len(seg)):
            if not st and seg[k] < COVER_R:
                st = True
                en.append(k)
            elif st and seg[k] > COVER_R + 1.0:
                st = False
                ex.append(k)
        en, ex = np.array(en, int), np.array(ex, int)
        entries += len(en)
        exits += len(ex)
        for e in en:
            prev = ex[ex < e]
            if len(prev):
                gap = e - prev[-1]
                quick5 += gap <= 38
                quick1 += gap <= 8
        for e in en:
            nxt = ex[ex > e]
            if len(nxt):
                stays += 1
                short2 += (nxt[0] - e) <= 15
    # --- 늑대 곁 멈춤·끼임 ---
    td = np.linalg.norm(np.nan_to_num(P[1:] - J[1:]), axis=-1)
    near = live & S[1:] & (td <= 7.5) & ~inside[1:]
    still = near & (dl < 0.01)
    wall = np.minimum(P0[1:], SIZE - P0[1:]).min(-1) < 0.5
    tree = Nd[1:] < 0.3
    seen_stop = live & S[1:] & (dl < 1e-3)
    seen_stop_in = int((seen_stop & inside[1:]).sum())
    seen_stop_out = int((seen_stop & ~inside[1:]).sum())
    ev = [r for r in _runs(still) if r[2] >= 8]
    ev_steps = sum(r[2] for r in ev)
    ev_wall = sum(1 for (i, a, n) in ev if wall[a:a + n, i].any())
    ev_tree = sum(1 for (i, a, n) in ev if tree[a:a + n, i].any())
    # --- 무리 (8 스텝마다) ---
    nn_sum = k10_sum = alone = cnt = 0.0
    for t in range(0, T, 8):
        idx = np.flatnonzero(A[t])
        if len(idx) < 2:
            continue
        X = P0[t, idx]
        D = np.linalg.norm(X[:, None, :] - X[None, :, :], axis=-1)
        np.fill_diagonal(D, np.inf)
        nn = D.min(1)
        k10 = (D < 5.0).sum(1)
        nn_sum += float(nn.sum())
        k10_sum += float(k10.sum())
        alone += float((k10 == 0).sum())
        cnt += len(idx)
    return dict(live_pairs=int(live.sum()), calm=int(calm.sum()), calm_pairs=int(pair.sum()), calm_flips=int(flip.sum()), spin=int((spin & calm).sum()),
                spin_deer=int(spin.any(0).sum()), fast=int(fast.sum()), fast_pairs=int(fpair.sum()), fast_flips=int(fflip.sum()), fast_turn90=int(fturn90.sum()),
                pp_runs=len(pp), pp_steps=int(sum(r[2] for r in pp)), pp_wall=int(pp_wall), pp_long=int(pp_long), pp_deer=int(pp_deer),
                cover_entries=entries, cover_exits=exits, cover_quick5=int(quick5), cover_quick1=int(quick1), cover_stays=stays, cover_short2=int(short2),
                cover_raw_exits=int(raw_exits), cover_flicker=int(flicker),
                inside_steps=int((inside[1:] & live).sum()), near=int(near.sum()), seen_stop_in=seen_stop_in, seen_stop_out=seen_stop_out, still_events=len(ev), still_steps=int(ev_steps), still_wall=ev_wall,
                still_tree=ev_tree, herd_n=int(cnt), herd_nn_sum=nn_sum, herd_k10_sum=k10_sum, herd_alone=int(alone), deer_ids=int(N))


# --------------------------------------------------------------------- #
# 판 하나
# --------------------------------------------------------------------- #


def snap_regions(snap: dict) -> dict:
    out = {}
    for R in snap["regions"]:
        f = R["flight"]
        e = f["episode"]
        rt = f.get("route") or {}
        out[R["region"]] = dict(n=R["deer"]["adopted"], caught=R["deer"]["caught"], starved=R["deer"]["starved"], alive=R["deer"]["alive"],
                                live=f["live_steps"], started=f["started"], flee=f["flee_steps"], reflex=f["reflex_steps"], ep_started=e["started"],
                                ep_chased=e["chased"], ep_hidden=e["hidden"], ep_watching=e["watching"], ep_caught=e["caught"], ep_starved=e["starved"],
                                ep_truncated=e["truncated"], ep_joined=e["joined"], shelter_steps=R["deer"]["shelter_steps"],
                                caught_in_cover=R["deer"]["caught_in_cover"], own_n=f["own_n"], own_contact=f["own_contact"],
                                n_cause={k: v for k, v in f["n"].items()}, steps_cause=f["steps"], contact_cause=f["contact"],
                                rt_run_exact=(rt.get("steps") or {}).get("run"), rt_shelter_exact=(rt.get("steps") or {}).get("shelter"),
                                pk_run=(rt.get("picked") or {}).get("run"), pk_shelter=(rt.get("picked") or {}).get("shelter"), rt_choice=rt.get("choice"),
                                behavior_steps=R["deer"]["behavior_steps"], covers=R["covers"], discs=R["obstacles"]["discs"])
    return out


LOG_SNAP_KEYS = ("n", "caught", "starved", "alive", "live", "started", "flee", "reflex", "ep_started", "ep_chased", "ep_hidden", "ep_watching", "ep_caught",
                 "ep_starved", "ep_truncated", "ep_joined", "shelter_steps", "caught_in_cover", "own_n")


def run_record(folder: Path, name: str, t_end: float, with_pos: bool = True) -> dict:
    lg = parse_log(folder / f"{name}.ecov3.log", t_end)
    out = dict(name=name, meta=lg["meta"], regions=lg["regions"])
    mp = folder / f"{name}.meta.json"
    if mp.exists():
        out["deer_meta"] = json.loads(mp.read_text(encoding="utf-8"))
    sp = folder / f"{name}.json"
    snap = None
    if sp.exists():
        snap = json.loads(sp.read_text(encoding="utf-8"))
        sr = snap_regions(snap)
        out["snapshot"] = dict(global_step=snap["global_step"], brain=snap["brain"], settings=snap["settings"], regions=sr)
        bad = []
        for r in REGIONS:
            for k in LOG_SNAP_KEYS:
                if lg["regions"][r].get(k) != sr[r].get(k):
                    bad.append(f"{r}.{k}: 기록 {lg['regions'][r].get(k)} 스냅숏 {sr[r].get(k)}")
            # 끝 까닭 합 = 스냅숏 n (잘림 빼고)
            cn = sr[r]["n_cause"]
            names = ("cover", "obstacle", "fov", "range", "switch", "stop", "held", "unchased", "caught", "starved")
            if [cn[k] for k in names] != lg["regions"][r]["causes"]:
                bad.append(f"{r}.끝 까닭: 기록 {lg['regions'][r]['causes']} 스냅숏 {[cn[k] for k in names]}")
            for k in ("pk_run", "pk_shelter", "rt_run_exact", "rt_shelter_exact"):
                if sr[r].get(k) is not None:
                    lg["regions"][r][f"snap_{k}"] = int(sr[r][k])
            if sr[r].get("rt_choice") is not None and "rt_choice" in lg["regions"][r] and lg["regions"][r]["rt_choice"] != sr[r]["rt_choice"]:
                bad.append(f"{r}.길 열린 결정: 기록 {lg['regions'][r].get('rt_choice')} 스냅숏 {sr[r]['rt_choice']}")
        out["log_vs_snapshot"] = bad
    if with_pos and (folder / f"{name}.deer.npz").exists():
        z = np.load(folder / f"{name}.deer.npz")
        T_end = int(round(t_end / STEP_S))
        for r in REGIONS:
            discs = None
            P, S, J, Nd, A = grid(z, r, T_end, discs)
            out["regions"][r].update(position_stats(P, S, J, Nd, A))
    return out


# --------------------------------------------------------------------- #
# 합·몫·짝
# --------------------------------------------------------------------- #


def total(recs: list) -> dict:
    s: dict = {}
    for r in recs:
        for k, v in r.items():
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                s[k] = s.get(k, 0) + v
            elif isinstance(v, list) and v and all(isinstance(x, (int, float)) for x in v):
                s[k] = [a + b for a, b in zip(s.get(k, [0] * len(v)), v)]
    return s


def ratio(a, b):
    return a / b if b else float("nan")


# (열쇠, 이름, 셈 함수(합 → 값), 몫이면 100 곱함, 소수 자리, 묶음)
def _beh_share(i):
    return lambda s: ratio(s["beh"][i], sum(s["beh"]))


def _cause_share(i):
    return lambda s: ratio(s["causes"][i], sum(s["causes"]))


METRICS = [
    # 결과
    ("caught_share", "잡힌 몫 (사슴 가운데)", lambda s: ratio(s["caught"], s["n"]), True, 2, "결과"),
    ("starved_share", "굶은 몫", lambda s: ratio(s["starved"], s["n"]), True, 2, "결과"),
    ("alive_share", "300 초에 산 몫", lambda s: ratio(s["alive"], s["n"]), True, 1, "결과"),
    ("caught30", "처음 30 초 잡힘 (세션당 마리)", lambda s: s["caught30"] / s["_sessions"], False, 2, "결과"),
    ("caught60", "처음 60 초 잡힘 (세션당 마리)", lambda s: s["caught60"] / s["_sessions"], False, 2, "결과"),
    ("caught300", "300 초까지 잡힘 (세션당 마리)", lambda s: s["caught"] / s["_sessions"], False, 2, "결과"),
    ("hunt_rate", "늑대 사냥 성공률 (끝난 사냥 가운데)", lambda s: ratio(s["hunt_success"], s["hunt_ends"]), True, 1, "결과"),
    ("hunts", "늑대 사냥 시작 (세션당)", lambda s: s["hunt_starts"] / s["_sessions"], False, 1, "결과"),
    # 도망
    ("ep_hide", "사건 숨음 비율", lambda s: ratio(s["ep_hidden"], s["ep_chased"]), True, 2, "도망"),
    ("ep_caught", "사건 잡힘 비율", lambda s: ratio(s["ep_caught"], s["ep_chased"]), True, 2, "도망"),
    ("ep_hide240", "사건 숨음 비율 (240 초 — 8e5417f 와 같은 길이)", lambda s: ratio(s["c240_ep_hidden"], s["c240_ep_chased"]), True, 2, "도망"),
    ("chased_n", "쫓긴 사건 (세션당)", lambda s: s["ep_chased"] / s["_sessions"], False, 1, "도망"),
    ("gf", "GF 도망 시작 (1000 산 사슴-스텝당)", lambda s: ratio(1000.0 * s["started"], s["live"]), False, 3, "도망"),
    ("ge", "GE 사건 시작 (1000 산 사슴-스텝당)", lambda s: ratio(1000.0 * s["ep_started"], s["live"]), False, 3, "도망"),
    ("run_s", "도망 한 번 달린 시간 (초)", lambda s: ratio(s["flee"] * STEP_S, s["started"]), False, 2, "도망"),
    ("own_chase_s", "스스로 벗어난 도망의 쫓긴 시간 (초)", lambda s: ratio(s["own_chase_steps"] * STEP_S, s["own_n"]), False, 2, "도망"),
    ("flee_share", "도망 중인 몫 (산 사슴-스텝)", lambda s: ratio(s["flee"], s["live"]), True, 2, "도망"),
    ("joined", "이어진 도망 몫 (도망이 끝나고 곧 또 뜀 — 도망 시작 가운데)", lambda s: ratio(s["ep_joined"], s["started"]), True, 1, "도망"),
    ("rt_shelter", "반사 길 스텝 가운데 SHELTER (R7e, 기록 % 반올림)", lambda s: ratio(s["rt_shelter_est"], s["rt_steps"]), True, 1, "도망"),
    ("rt_pick", "SHELTER 가 열린 결정 가운데 SHELTER 고름 (R7e)", lambda s: ratio(s["rt_picked_shelter"], s["rt_choice"]), True, 1, "도망"),
    ("rt_pick_all", "길 결정 가운데 SHELTER 고름 (R7e, 스냅숏 — 8e5417f '53.9%' 와 같은 셈)",
     lambda s: ratio(s["snap_pk_shelter"], s["snap_pk_shelter"] + s["snap_pk_run"]), True, 1, "도망"),
    ("rt_shelter_exact", "반사 길 스텝 가운데 SHELTER (R7e, 스냅숏 정확값)",
     lambda s: ratio(s["snap_rt_shelter_exact"], s["snap_rt_shelter_exact"] + s["snap_rt_run_exact"]), True, 1, "도망"),
] + [(f"end_{i}", f"도망 끝 까닭: {c}", _cause_share(i), True, 1, "도망 끝") for i, c in enumerate(CAUSES)] + [
    # 평소
] + [(f"beh_{i}", f"행동 몫: {b}", _beh_share(i), True, 1, "평소") for i, b in enumerate(BEH)] + [
    ("keep_alert", "반사 덮기: 경계(먹으며 멀어짐) 몫", lambda s: ratio(s["keep_alert"], s["live"]), True, 2, "평소"),
    ("keep_crouch", "반사 덮기: 은신처 웅크림 몫", lambda s: ratio(s["keep_crouch"], s["live"]), True, 2, "평소"),
    ("restkeep", "거리 두기(쉬는 늑대) 몫", lambda s: ratio(s["restkeep_steps"], s["live"]), True, 2, "평소"),
    ("in_shelter", "은신처 안 몫 (세계 셈)", lambda s: ratio(s["shelter_steps"], s["live"]), True, 2, "평소"),
    ("herd_nn", "가장 가까운 사슴까지 (m)", lambda s: ratio(2.0 * s["herd_nn_sum"], s["herd_n"]), False, 2, "평소"),
    ("herd_k10", "10 m 안 사슴 수", lambda s: ratio(s["herd_k10_sum"], s["herd_n"]), False, 2, "평소"),
    ("herd_alone", "10 m 안에 다른 사슴 없음", lambda s: ratio(s["herd_alone"], s["herd_n"]), True, 2, "평소"),
    ("energy", "300 초 사슴 기운 평균 (지역 평균, %)", lambda s: s["energy_pct"] / s["_regions"], False, 1, "평소"),
    ("food", "300 초 무대 먹이 (처음의 %, 지역 평균)", lambda s: s["food_pct"] / s["_regions"], False, 1, "평소"),
    # 이상
    ("spin", "제자리 빙빙 (평소 스텝 가운데)", lambda s: ratio(s["spin"], s["calm"]), True, 3, "이상"),
    ("calm_flips", "평소 걷기 뒤집힘 (1000 평소 스텝당)", lambda s: ratio(1000.0 * s["calm_flips"], s["calm"]), False, 2, "이상"),
    ("rv_stop", "쉬는 늑대 시야 안 멈춤 (산 사슴-스텝)", lambda s: ratio(s["rv_stop"], s["rv_live"]), True, 3, "이상"),
    ("rv_in", "쉬는 늑대 시야 안 (산 사슴-스텝)", lambda s: ratio(s["rv_in"], s["rv_live"]), True, 2, "이상"),
    ("seen_stop_out", "늑대가 보이는데 은신처 밖에서 멈춤 (산 사슴-스텝)", lambda s: ratio(s["seen_stop_out"], s["live_pairs"]), True, 2, "이상"),
    ("seen_stop_in", "늑대가 보이는데 은신처 안에서 멈춤 — 웅크려 숨음 (산 사슴-스텝)", lambda s: ratio(s["seen_stop_in"], s["live_pairs"]), True, 2, "이상"),
    ("cover_entries", "은신처 들어감 (1000 산 사슴-스텝당)", lambda s: ratio(1000.0 * s["cover_entries"], s["live_pairs"]), False, 2, "이상"),
    ("cover_quick5", "은신처 나간 뒤 5 초 안 다시 들어감 (나감 가운데)", lambda s: ratio(s["cover_quick5"], s["cover_exits"]), True, 1, "이상"),
    ("cover_quick1", "은신처 나간 뒤 1 초 안 다시 들어감 (나감 가운데)", lambda s: ratio(s["cover_quick1"], s["cover_exits"]), True, 1, "이상"),
    ("cover_short2", "은신처에 2 초 이하 머묾 (끝난 머묾 가운데)", lambda s: ratio(s["cover_short2"], s["cover_stays"]), True, 1, "이상"),
    ("cover_flicker", "  (참고) 원 가장자리 깜빡임 — 걸침 없이 나간 뒤 1 초 안 다시 (나감 가운데)", lambda s: ratio(s["cover_flicker"], s["cover_raw_exits"]), True, 1,
     "이상"),
    ("still", "늑대 15 m 안 은신처 밖 1 초 넘게 제자리 (1000 그런 스텝당 번)", lambda s: ratio(1000.0 * s["still_events"], s["near"]), False, 2, "이상"),
    ("still_n", "  그런 일 (세션당 번)", lambda s: s["still_events"] / s["_sessions"], False, 2, "이상"),
    ("still_wall", "  그 가운데 벽 붙음 (세션당 번)", lambda s: s["still_wall"] / s["_sessions"], False, 2, "이상"),
    ("still_tree", "  그 가운데 나무 붙음 (세션당 번)", lambda s: s["still_tree"] / s["_sessions"], False, 2, "이상"),
    ("terr_deer", "지형 막힘 사슴 (세션당 번)", lambda s: s["terr_deer"] / s["_sessions"], False, 1, "이상"),
    ("obst_hit", "줄기 닿음 (사슴-스텝 가운데, 나무 있는 맵)", lambda s: ratio(s.get("obst_deer_hit", 0), s.get("obst_deer_steps", 0)), True, 3, "이상"),
    ("fast_flips", "달리기 방향 135° 넘게 뒤집힘 (1000 빠른 스텝 짝당)", lambda s: ratio(1000.0 * s["fast_flips"], s["fast_pairs"]), False, 2, "이상"),
    ("fast_turn90", "달리기 방향 90° 넘게 꺾임 (1000 빠른 스텝 짝당)", lambda s: ratio(1000.0 * s["fast_turn90"], s["fast_pairs"]), False, 1, "이상"),
    ("pp_runs", "핑퐁 — 달리며 3 스텝 넘게 잇달아 거꾸로 (세션당 번)", lambda s: s["pp_runs"] / s["_sessions"], False, 1, "이상"),
    ("pp_long", "  그 가운데 1 초(8 스텝) 넘게 이어짐 (세션당 번)", lambda s: s["pp_long"] / s["_sessions"], False, 1, "이상"),
    ("pp_wall", "  그 가운데 벽 2 m 안에서 시작 (몫)", lambda s: ratio(s["pp_wall"], s["pp_runs"]), True, 1, "이상"),
    ("pp_steps", "  핑퐁 사슴-스텝 (산 사슴-스텝 가운데)", lambda s: ratio(s["pp_steps"], s["live_pairs"]), True, 3, "이상"),
    ("pp_deer", "  핑퐁을 한 사슴 (세션당 마리)", lambda s: s["pp_deer"] / s["_sessions"], False, 1, "이상"),
    # 두뇌
    ("decisions", "두뇌 결정 (세션당 사슴·스텝)", lambda s: s["decisions"] / s["_sessions"], False, 0, "두뇌"),
    ("mask_viol", "마스크 위반 (허용 안 된 행동)", lambda s: s["mask_viol"], False, 0, "두뇌"),
    ("self_flee", "반사 밖 두뇌 FLEE (산 사슴-스텝)", lambda s: ratio(s["brain_beh"][1], s["live"]), True, 3, "두뇌"),
    ("brain_hide", "두뇌 스텝 가운데 숨기 (반사 밖)", lambda s: ratio(s["brain_beh"][2], s["brain_steps"]), True, 1, "두뇌"),
    ("brain_know_hide", "  늑대를 알 때 숨기", lambda s: ratio(s["brain_know_beh"][2], s["brain_know"]), True, 1, "두뇌"),
]


def flat_region(r: dict) -> dict:
    """지역 기록 → 합할 숫자 칸 (240 초 누적은 c240_ 앞붙임)."""
    out = {k: v for k, v in r.items() if isinstance(v, (int, float, list)) and not isinstance(v, bool)}
    for k, v in (r.get("c240") or {}).items():
        out[f"c240_{k}"] = v
    out["_regions"] = 1
    return out


def values(s: dict) -> dict:
    out = {}
    for key, _, f, *_ in METRICS:
        try:
            out[key] = float(f(s))
        except (KeyError, ZeroDivisionError, TypeError):
            out[key] = float("nan")
    return out


def paired(d: list) -> dict:
    x = np.array([v for v in d if math.isfinite(v)], dtype=np.float64)
    n = len(x)
    if n == 0:
        return dict(diff=float("nan"), sd=float("nan"), t=float("nan"), n=0, pos=0)
    m = float(x.mean())
    sd = float(x.std(ddof=1)) if n > 1 else float("nan")
    se = sd / math.sqrt(n) if n > 1 else float("nan")
    t = m / se if se and se > 0 else float("nan")
    return dict(diff=m, sd=sd, t=t, n=n, pos=int((x > 0).sum()), neg=int((x < 0).sum()), mn=float(x.min()), mx=float(x.max()))


def compare(recs: dict, maps: list, sessions: list) -> dict:
    """recs[(map, session, brain)] = 판 기록 → 맵마다 {pooled{brain}, by_region{region}{brain}, pair{metric}, per_session}."""
    out = {}
    for mp in maps:
        ss = [s for s in sessions if (mp, s, "cur") in recs and (mp, s, "r7e") in recs]
        res = dict(sessions=ss, pooled={}, by_region={}, pair={}, pair_region={}, per_session={})
        for b in ("cur", "r7e"):
            regs = [flat_region(recs[(mp, s, b)]["regions"][r]) for s in ss for r in REGIONS]
            tot = total(regs)
            tot["_sessions"] = len(ss)
            res["pooled"][b] = values(tot)
            res["by_region"].setdefault(b, {})
            for r in REGIONS:
                t2 = total([flat_region(recs[(mp, s, b)]["regions"][r]) for s in ss])
                t2["_sessions"] = len(ss)
                res["by_region"][b][r] = values(t2)
        per = {}
        for s in ss:
            per[s] = {}
            for b in ("cur", "r7e"):
                t = total([flat_region(recs[(mp, s, b)]["regions"][r]) for r in REGIONS])
                t["_sessions"] = 1
                per[s][b] = values(t)
        res["per_session"] = per
        for key, *_ in METRICS:
            res["pair"][key] = paired([per[s]["r7e"][key] - per[s]["cur"][key] for s in ss])
        for r in REGIONS:
            res["pair_region"][r] = {}
            for key, *_ in METRICS:
                d = []
                for s in ss:
                    a = flat_region(recs[(mp, s, "r7e")]["regions"][r]); a["_sessions"] = 1
                    c = flat_region(recs[(mp, s, "cur")]["regions"][r]); c["_sessions"] = 1
                    d.append(values(total([a]))[key] - values(total([c]))[key])
                res["pair_region"][r][key] = paired(d)
        out[mp] = res
    return out


# --------------------------------------------------------------------- #
# 확인
# --------------------------------------------------------------------- #


def checks(folder: Path, recs: dict, maps: list, sessions: list, t_end: float) -> list:
    out = []

    def add(ok, what):
        out.append(dict(ok=bool(ok), what=what))

    want = {"cur": "v3_r1_g995_s3_20m@eca97f2e", "r7e": "v3_r7_g995_s1_20m@40d8710d"}
    for (mp, s, b), R in sorted(recs.items()):
        m = R["meta"]
        ids = sorted({x for r in REGIONS for x in R["regions"][r]["brain_ids"]})
        start_ids = [x[1] for x in m["brain_start"]]
        add(start_ids == [want[b]] and ids == [want[b]] and m["brain_swaps"] == 0,
            f"{R['name']}: 두뇌 시작 {start_ids} · 10 초 줄 두뇌 {ids} · 바꿈 {m['brain_swaps']} (기대 {want[b]})")
        if b == "r7e":
            st = m["brain_start"][0][2] if m["brain_start"] else ""
            add("관측 24 도망길·반사 밖 도망 막음" in st and "파일 v3_r7_g995_s1_20m.json" in st, f"{R['name']}: 시작 줄 '{st[:90]}'")
            modes = {R["regions"][r].get("route_mode") for r in REGIONS}
            add(modes == {"두 길 켬 (판 5 — 반사 밖 도망 막음)"}, f"{R['name']}: 길 줄 {modes}")
        mv = sum(R["regions"][r].get("mask_viol", -1) for r in REGIONS)
        add(mv == 0, f"{R['name']}: 마스크 위반 {mv}")
        add(m["warnings"] == 0, f"{R['name']}: EcoV3I·EcoV3Brain 경고/오류 {m['warnings']} {m['warn_first']}")
        add(m["watcher_lines"] == 0, f"{R['name']}: 파이썬 감시 줄 {m['watcher_lines']} (AutoAdapt 끔)")
        dm = R.get("deer_meta") or {}
        add(dm.get("extract_ok") is True, f"{R['name']}: 사슴 줄 뽑기 {dm.get('extract_ok')} ({dm.get('deer_rows')} 줄)")
        T_end = int(round(t_end / STEP_S))
        add(all(R["regions"][r]["decisions_t"] == T_end for r in REGIONS), f"{R['name']}: 결정 줄 마지막 스텝 {[R['regions'][r]['decisions_t'] for r in REGIONS]} = {T_end}")
        if "snapshot" in R:
            sn = R["snapshot"]
            add(sn["global_step"] == T_end, f"{R['name']}: 스냅숏 전역 스텝 {sn['global_step']}")
            add(sn["brain"]["id"] == want[b], f"{R['name']}: 스냅숏 두뇌 {sn['brain']['id']} 계약 {sn['brain'].get('contract_hash')}")
            if b == "r7e":
                add(sn["brain"].get("contract_hash") == "0xad7bad5e1acaf071" and sn["brain"].get("mask_version") == 5 and sn["brain"].get("obs_dim") == 24,
                    f"{R['name']}: 스냅숏 계약 {sn['brain'].get('contract_hash')} 판 {sn['brain'].get('mask_version')} 관측 {sn['brain'].get('obs_dim')}")
            add(not R["log_vs_snapshot"], f"{R['name']}: 기록 줄 = 스냅숏 ({len(R['log_vs_snapshot'])} 칸 다름 {R['log_vs_snapshot'][:3]})")
        if mp == "jyu":
            add(m["team_weather_start"] == 3, f"{R['name']}: 팀 날씨 출처로 시작한 지역 {m['team_weather_start']}/3")
            add(m["vegetation_enabled"] > 0, f"{R['name']}: 식생 켬 줄 {m['vegetation_enabled']} (맵 값 그대로 = 켬)")
    # 다시 돌림·사슴 줄 끔
    s0 = sessions[0]
    a, b_ = folder / f"it_s{s0}_r7e.meta.json", folder / f"it_s{s0}_r7e_b.meta.json"
    if a.exists() and b_.exists():
        x, y = json.loads(a.read_text(encoding="utf-8")), json.loads(b_.read_text(encoding="utf-8"))
        add(x["deer_sha256"] == y["deer_sha256"], f"it s{s0} r7e 다시 돌림: 사슴 줄 지문 {x['deer_sha256'][:12]} · {y['deer_sha256'][:12]}")
        sa = json.loads((folder / f"it_s{s0}_r7e.json").read_text(encoding="utf-8"))
        sb = json.loads((folder / f"it_s{s0}_r7e_b.json").read_text(encoding="utf-8"))
        add([R["deer"] for R in sa["regions"]] == [R["deer"] for R in sb["regions"]] and [R["flight"] for R in sa["regions"]] == [R["flight"] for R in sb["regions"]],
            f"it s{s0} r7e 다시 돌림: 스냅숏 지역 deer·flight 같음")
    # 빌드가 바뀐 뒤 같은 세션 다시 돌림 (<이름>_c): 통합 맵은 바이트가 같아야 한다 — 세계가 같은 빌드인지
    for mc in sorted(folder.glob("it_s*_c.meta.json")):
        base = folder / mc.name.replace("_c.meta.json", ".meta.json")
        if base.exists():
            x, y = json.loads(base.read_text(encoding="utf-8")), json.loads(mc.read_text(encoding="utf-8"))
            add(x["deer_sha256"] == y["deer_sha256"], f"{mc.name[:-10]} (빌드 바뀐 뒤 다시 돌림): 사슴 줄 지문 {x['deer_sha256'][:12]} · {y['deer_sha256'][:12]}")
    on, off = folder / f"it_s{s0}_cur.json", folder / f"it_s{s0}_cur_obsoff.json"
    if on.exists() and off.exists():
        sa = json.loads(on.read_text(encoding="utf-8"))
        sb = json.loads(off.read_text(encoding="utf-8"))
        same = all(Ra["deer"] == Rb["deer"] and Ra["flight"] == Rb["flight"] and Ra["food"]["food"] == Rb["food"]["food"]
                   for Ra, Rb in zip(sa["regions"], sb["regions"]))
        add(same, f"it s{s0} 지금 두뇌: 사슴 줄 기록 켬(-EcoV3ObsParityLog=1)·끔 스냅숏 deer·flight·먹이 칸 같음 (측정 기록이 세계를 바꾸지 않음)")
    return out


def rerun_spread(folder: Path, recs: dict, s0: int, t_end: float) -> dict:
    """jyu 같은 세션·같은 두뇌 다시 돌림의 흔들림 (팀 비 실시간)."""
    out = {}
    for b in ("cur", "r7e"):
        n1, n2 = f"jyu_s{s0}_{b}", f"jyu_s{s0}_{b}_b"
        if not ((folder / f"{n2}.ecov3.log").exists() and ("jyu", s0, b) in recs):
            continue
        r2 = run_record(folder, n2, t_end)
        v = []
        for R in (recs[("jyu", s0, b)], r2):
            t = total([flat_region(R["regions"][r]) for r in REGIONS])
            t["_sessions"] = 1
            v.append(values(t))
        d1 = (folder / f"{n1}.meta.json")
        sha = [json.loads((folder / f"{n}.meta.json").read_text(encoding="utf-8"))["deer_sha256"][:12] for n in (n1, n2) if (folder / f"{n}.meta.json").exists()]
        out[b] = dict(first=v[0], second=v[1], deer_sha=sha, same_bytes=len(set(sha)) == 1 and d1.exists())
    return out


# --------------------------------------------------------------------- #
# 표
# --------------------------------------------------------------------- #


def fmt(v: float, pct: bool, nd: int) -> str:
    if not math.isfinite(v):
        return "—"
    return f"{100 * v:.{nd}f}%" if pct else f"{v:.{nd}f}"


def fmt_d(v: float, pct: bool, nd: int) -> str:
    if not math.isfinite(v):
        return "—"
    return (f"{100 * v:+.{nd}f} %p" if pct else f"{v:+.{nd}f}")


def fmt_t(t: float) -> str:
    return "—" if not math.isfinite(t) else f"{t:+.2f}"


def md_tables(cmp: dict, chk: list, spread: dict, meta: dict) -> str:
    L = []
    for mp, res in cmp.items():
        from r7e_game import MAP_LABEL  # noqa: E402

        L.append(f"\n## {MAP_LABEL[mp]} — 세션 {res['sessions'][0]}~{res['sessions'][-1]} ({len(res['sessions'])} 개) × 지역 셋, {meta['seconds']} 초\n")
        L.append("| 묶음 | 칸 | 지금 (R1b-F) | R7e | 세션 짝 차이 R7e − 지금 (t, 늘어난 세션/줄어든 세션) |")
        L.append("|---|---|---|---|---|")
        for key, name, _, pct, nd, grp in METRICS:
            a, b = res["pooled"]["cur"][key], res["pooled"]["r7e"][key]
            if not (math.isfinite(a) or math.isfinite(b)):
                continue
            p = res["pair"][key]
            L.append(f"| {grp} | {name} | {fmt(a, pct, nd)} | {fmt(b, pct, nd)} | {fmt_d(p['diff'], pct, nd)} ({fmt_t(p['t'])}, {p.get('pos', 0)}/{p.get('neg', 0)}) |")
        L.append("")
        L.append(f"### 지역마다 ({MAP_LABEL[mp]})\n")
        keys = ("ep_hide", "ep_caught", "chased_n", "caught_share", "caught30", "caught60", "hunt_rate", "gf", "run_s", "joined", "rt_pick", "beh_0", "beh_2",
                "in_shelter", "herd_nn", "spin", "rv_stop", "cover_quick5", "still", "fast_flips", "pp_runs", "pp_long")
        L.append("| 지역 | 칸 | 지금 | R7e | 세션 짝 차이 (t) |")
        L.append("|---|---|---|---|---|")
        lut = {k: (n, pct, nd) for k, n, _, pct, nd, _ in METRICS}
        for r in REGIONS:
            for key in keys:
                n, pct, nd = lut[key]
                a, b = res["by_region"]["cur"][r][key], res["by_region"]["r7e"][r][key]
                p = res["pair_region"][r][key]
                L.append(f"| {r} | {n} | {fmt(a, pct, nd)} | {fmt(b, pct, nd)} | {fmt_d(p['diff'], pct, nd)} ({fmt_t(p['t'])}) |")
        L.append("")
        L.append(f"### 세션마다 ({MAP_LABEL[mp]}, 지역 셋 합)\n")
        L.append("| 세션 | 쫓긴 사건 지금 · R7e | 사건 숨음 비율 지금 → R7e | 잡힌 마리 지금 · R7e | 처음 30 초 잡힘 지금 · R7e |")
        L.append("|---|---|---|---|---|")
        for s, v in res["per_session"].items():
            L.append(f"| {s} | {v['cur']['chased_n']:.0f} · {v['r7e']['chased_n']:.0f} | {fmt(v['cur']['ep_hide'], True, 1)} → {fmt(v['r7e']['ep_hide'], True, 1)} | "
                     f"{fmt(v['cur']['caught300'], False, 0)} · {fmt(v['r7e']['caught300'], False, 0)} | {fmt(v['cur']['caught30'], False, 0)} · {fmt(v['r7e']['caught30'], False, 0)} |")
    if spread:
        L.append("\n## 조연우 맵 같은 세션 다시 돌림 (팀 비를 실제 시간으로 읽어 생기는 흔들림)\n")
        L.append("| 두뇌 | 칸 | 첫 판 | 다시 돌림 | 사슴 줄 바이트 같음 |")
        L.append("|---|---|---|---|---|")
        lut = {k: (n, pct, nd) for k, n, _, pct, nd, _ in METRICS}
        for b, v in spread.items():
            for key in ("ep_hide", "chased_n", "caught300", "caught30", "gf", "spin", "rv_stop"):
                n, pct, nd = lut[key]
                L.append(f"| {b} | {n} | {fmt(v['first'][key], pct, nd)} | {fmt(v['second'][key], pct, nd)} | {'예' if v['same_bytes'] else '아니오'} {v['deer_sha']} |")
    L.append("\n## 확인\n")
    bad = [c for c in chk if not c["ok"]]
    L.append(f"- 확인 {len(chk)} 칸 가운데 어긋남 {len(bad)}")
    for c in bad[:30]:
        L.append(f"  - 어긋남: {c['what']}")
    for c in chk:
        if c["what"].startswith("it s") or "다시 돌림" in c["what"] or "사슴 줄 기록 켬" in c["what"] or "DLL" in c["what"] or "끝 코드" in c["what"] or "빌드 바뀐 뒤" in c["what"]:
            L.append(f"  - {'맞음' if c['ok'] else '어긋남'}: {c['what']}")
    return "\n".join(L) + "\n"


def cmd_analyze(a) -> int:
    from r7e_game import parse_sessions  # noqa: E402

    folder = Path(a.runs)
    sessions = parse_sessions(a.sessions)
    recs = {}
    for mp in ("it", "jyu"):
        for s in sessions:
            for b in ("cur", "r7e"):
                n = f"{mp}_s{s}_{b}"
                if (folder / f"{n}.ecov3.log").exists():
                    recs[(mp, s, b)] = run_record(folder, n, a.seconds)
                    print("읽음", n, flush=True)
    maps = [m for m in ("it", "jyu") if any(k[0] == m for k in recs)]
    cmp = compare(recs, maps, sessions)
    chk = checks(folder, recs, maps, sessions, a.seconds)
    spread = rerun_spread(folder, recs, sessions[0], a.seconds)
    meta = dict(seconds=a.seconds, sessions=sessions, runs=sorted(k for k in (f"{m}_s{s}_{b}" for (m, s, b) in recs)))
    wf = folder / "waves.jsonl"
    waves = [json.loads(x) for x in wf.read_text(encoding="utf-8").splitlines() if x.strip()] if wf.exists() else []
    dlls = sorted({w["dll_before"] for w in waves} | {w["dll_after"] for w in waves})
    jobs = [j for w in waves for j in w["jobs"]]
    meta.update(dll_stamps=dlls, waves=len(waves), jobs=len(jobs), bad_jobs=[j["name"] for j in jobs if j["rc"] != 0],
                wall_s=dict(min=min((j["wall_s"] for j in jobs), default=None), max=max((j["wall_s"] for j in jobs), default=None)))
    per_dll = {}
    for w in waves:
        for j in w["jobs"]:
            per_dll.setdefault(w["dll_before"], []).append(j["name"])
    meta["dll_runs"] = {k: sorted(v) for k, v in per_dll.items()}
    chk.append(dict(ok=all(w["dll_before"] == w["dll_after"] for w in waves),
                    what=f"묶음마다 앞뒤 DLL 시각 같음 — 두뇌 짝은 같은 빌드 안 (묶음 {len(waves)} 개, DLL {len(dlls)} 가지: "
                         + "; ".join(f"{k} 판 {len(v)} 개" for k, v in per_dll.items()) + ")"))
    chk.append(dict(ok=not meta["bad_jobs"], what=f"언리얼 끝 코드 0 (판 {len(jobs)} 개, 문제 {meta['bad_jobs']})"))
    # 판 목록 (확인 판 포함): 명령줄·끝 코드·걸린 시간·PID·DLL·사슴 줄 수·지문 — 원 기록은 저장소 밖
    run_index = []
    for w in waves:
        for j in w["jobs"]:
            mp = folder / f"{j['name']}.meta.json"
            dm = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
            cp = folder / f"{j['name']}.cmd.txt"
            run_index.append(dict(name=j["name"], rc=j["rc"], wall_s=j["wall_s"], pid=j["pid"], dll=w["dll_before"],
                                  deer_rows=dm.get("deer_rows"), deer_sha256=dm.get("deer_sha256"),
                                  cmd=cp.read_text(encoding="utf-8").strip() if cp.exists() else None))
    md = md_tables(cmp, chk, spread, meta)
    outp = Path(a.out)

    def clean(o):
        if isinstance(o, float):
            return None if not math.isfinite(o) else round(o, 6)
        if isinstance(o, dict):
            return {str(k): clean(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [clean(v) for v in o]
        if isinstance(o, set):
            return sorted(o)
        return o

    runs = {f"{m}_s{s}_{b}": dict(meta=R["meta"], regions={r: {k: v for k, v in R["regions"][r].items()} for r in REGIONS},
                                  deer_sha256=(R.get("deer_meta") or {}).get("deer_sha256"), log_vs_snapshot=R.get("log_vs_snapshot"))
            for (m, s, b), R in recs.items()}
    outp.with_suffix(".json").write_text(json.dumps(clean(dict(meta=meta, metrics=[dict(key=k, name=n, pct=p, nd=d, group=g) for k, n, _, p, d, g in METRICS],
                                                              compare=cmp, checks=chk, rerun_jyu=spread, run_index=run_index, runs=runs)), ensure_ascii=False, separators=(",", ":")) + "\n",
                                         encoding="utf-8", newline="\n")
    outp.with_suffix(".md").write_text("# R1b-F 대 R7e — 헤드리스 언리얼 (자동 생성 — r7e_game.py analyze)\n" + md, encoding="utf-8", newline="\n")
    print(md)
    return 0

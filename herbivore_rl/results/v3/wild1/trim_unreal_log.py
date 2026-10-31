"""언리얼 전체 기록(-abslog)에서 비교에 쓰는 줄만 남긴다 (10-16, results/v3/mirror/unreal_logs 와 같은 꼴에 야생 줄을 더함).

    python results/v3/wild1/trim_unreal_log.py <출력 폴더> <전체 기록>...     # 이름 d<사슴>_s<세션 시드>_k0[.full].log → <출력>/d.._s.._k0.log

남기는 줄: 'Command Line'(-abslog 칸은 뺀다), [EcoV3I] 설정·계획·시작 줄, 10초 첫 줄 '[EcoV3I] <지역> | <t>초 ...', 셋째 줄 '<지역> 경계 거리 |',
넷째 줄 '<지역> 야생 |', 늑대 잠·깸 사건 줄, EcoV3I 경고·오류. 둘째 줄 '<지역> 얼기·식사 |'는 뺀다(비교에 쓰지 않고 길다).
k0 = 옛 경계 거리 실험(KeepAway, 857da45 에서 도주 반사로 바뀌어 없어짐)을 켜지 않았다는 뜻이고 compare_unreal.py 이름 꼴을 그대로 쓰려고 붙인다.
"""

import io
import re
import sys
from pathlib import Path

SECOND = re.compile(r'\[EcoV3I\] \S+ 얼기·식사 \| [\d.]+초')
MAIN = re.compile(r'\[EcoV3I\] \S+ \| [\d.]+초')


def trim(src: Path, out_dir: Path) -> str:
    keep, other = [], 0
    for line in io.open(src, "rb").read().decode("utf-8", "replace").splitlines():
        if "LogInit: Command Line:" in line:
            keep.append(re.sub(r'\s+-abslog=\S+', '', line[line.index("LogInit:"):]))
        elif "[EcoV3I]" in line:
            if not SECOND.search(line):
                keep.append(line)
        elif ("Error:" in line or "Ensure" in line or "Fatal" in line) and "UnifiedErrorTest" not in line:
            other += 1
    name = src.name.replace(".full.log", ".log")
    (out_dir / name).write_text("\n".join(keep) + "\n", encoding="utf-8")
    main = sum(1 for k in keep if MAIN.search(k))
    wild = sum(1 for k in keep if " 야생 | " in k)
    warn = sum(1 for k in keep if "Warning:" in k or "Error:" in k)
    return f"{name}: 줄 {len(keep)} (10초 첫 줄 {main}, 야생 {wild}, EcoV3I 경고·오류 {warn}) · 다른 Error/Ensure/Fatal 줄 {other}"


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for p in sys.argv[2:]:
        print(trim(Path(p), out))

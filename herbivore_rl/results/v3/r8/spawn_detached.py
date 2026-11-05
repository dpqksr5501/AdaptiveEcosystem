"""창 없는 떨어진 프로세스로 파이썬 스크립트 하나를 띄우고 바로 끝난다 (launch_train.ps1·launch_watch.ps1 이 부른다).

    python -X utf8 results/v3/r8/spawn_detached.py --log results/v3/r8/logs/train_r8_p_s0.log --what "train r8_p_s0" -- results/v3/r8/train_r8.py --config ...

- 왜: 11-05 16:59 에 `cmd.exe` 를 WMI 로 띄운 학습 넷과 지켜보기가 17:05:09~19 에 2~4 초 간격으로 콘솔 창 닫힘(CTRL_CLOSE, 화면 기록
  `forrtl: error (200): program aborting due to window-CLOSE event`)으로 죽었다. 콘솔 창이 있으면 창을 닫는 쪽(사람·다른 프로그램)에 학습이 같이 죽는다.
- 그래서 자식을 `CREATE_NO_WINDOW`(창 없는 콘솔 — 닫을 창이 없다, 자식의 git 등도 창을 띄우지 않는다)·`CREATE_NEW_PROCESS_GROUP`(Ctrl+C 묶음에서 빠짐)로 띄우고,
  되면 `CREATE_BREAKAWAY_FROM_JOB`(부모의 작업 묶음에서 빠짐)도 쓴다. 화면 출력은 --log 파일로, PID 는 logs/pids.txt 에 한 줄(기존 꼴) 덧붙인다.
- 환경: PYTHONUTF8=1. 작업 폴더: herbivore_rl/. 자식은 이 스크립트를 띄운 파이썬과 같은 파이썬이다.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[3]                              # herbivore_rl/


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True, help="화면 기록 (herbivore_rl/ 기준)")
    ap.add_argument("--what", required=True, help="pids.txt 줄 머리 (예 'train r8_p_s0', 'watch')")
    ap.add_argument("--append", action="store_true", help="화면 기록을 덮어쓰지 않고 덧붙인다")
    ap.add_argument("--pidfile", default=str(HERE.parent / "logs" / "pids.txt"))
    ap.add_argument("rest", nargs=argparse.REMAINDER, help="-- 뒤에 파이썬 인자")
    args = ap.parse_args(argv)
    rest = args.rest[1:] if args.rest and args.rest[0] == "--" else args.rest
    if not rest:
        ap.error("띄울 스크립트가 없다 (-- 뒤에 적는다)")
    log = (ROOT / args.log) if not Path(args.log).is_absolute() else Path(args.log)
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONUTF8="1")
    base = 0
    if os.name == "nt":
        base = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    with log.open("a" if args.append else "w", encoding="utf-8") as lf:
        kw = dict(cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=lf, stderr=subprocess.STDOUT, close_fds=True)
        try:
            child = subprocess.Popen([sys.executable, *rest], creationflags=base | (subprocess.CREATE_BREAKAWAY_FROM_JOB if os.name == "nt" else 0), **kw)
            breakaway = True
        except OSError:
            child = subprocess.Popen([sys.executable, *rest], creationflags=base, **kw)
            breakaway = False
    time.sleep(1.0)
    rc = child.poll()
    rel = log.relative_to(ROOT).as_posix() if log.is_relative_to(ROOT) else str(log)
    line = (f"{args.what} cmd_pid {os.getpid()} python_pid {child.pid} log {rel} started {time.strftime('%Y-%m-%dT%H:%M:%S')}"
            f" no_window breakaway={int(breakaway)}" + (f" EXITED rc={rc}" if rc is not None else ""))
    with Path(args.pidfile).open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)
    return 0 if rc in (None, 0) else 1


if __name__ == "__main__":
    sys.exit(main())

# R9 리그 띄우기 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R9_MULTISPECIES_DESIGN.md 7-9, 상태 results/v3/r9/STATUS.md).
# 리그 조정 프로세스 league_r9.py 하나와 지켜보기 watch_r9.py 하나를 이 셸과 떨어진 프로세스로 띄운다(R8 launch_train.ps1 과 같은 길):
#   WMI Win32_Process.Create(창 숨김) → spawn_detached.py → 창 없는 콘솔(CREATE_NO_WINDOW)·새 프로세스 묶음·작업 묶음 밖.
#   리그가 묶음마다 학습 프로세스를 같은 방식(창 없음)으로 띄우고 기다린다. 셸·세션이 끝나도 이어진다. 11-05 콘솔 창 닫힘 사고 때문이다.
# 화면 기록 results/v3/r9/logs/league.log·watch.log, 학습 기록 results/v3/r9/logs/<실행>.log.jsonl, 진행표 results/v3/r9/logs/progress.md,
# PID 목록 results/v3/r9/logs/pids.txt, 상태 ckpt/r9/league_state.json, 판 ckpt/r9/<갈래>/<종>_r<바퀴>_<결정 수>.zip·npz.
# 다른 python·언리얼 프로세스는 건드리지 않는다. 언리얼/UBT 가 돌면 리그가 띄우지 않고 기다린다(끄지 않는다).
#   powershell -ExecutionPolicy Bypass -File results/v3/r9/launch_league.ps1 -DecisionsJson results/v3/r9/bundle_decisions.json -Rounds 10
#   -DryRun 이면 리그 차례만 그린다(league_r9.py --dry-run, 이 셸에서). -NoWatch 면 지켜보기를 띄우지 않는다.
# 밤 창(STATUS 5절, 사용자 11-10 '학습은 밤에만'): 리그는 -Window(기본 22:00-09:00) 안에서, 묶음 어림 벽시계가 창 끝 전에 끝날 때만 묶음을 시작한다.
#   -CheckAnytime 이면 짝수 바퀴 점검(학습 아님)은 창 밖에서도 띄운다. 언리얼·UBT·셰이더·라이브 코딩·MSBuild 가 돌면 끄지 않고 기다린다.
# -Night: 리그 대신 밤 실행기 run_night.py 를 띄운다 — C0-10 짧은 학습 6 묶음(밤 창) → 잼 → γ 고르기 → C0_STATE → 통과하면 같은 인자로 리그 + 지켜보기.
#   powershell -ExecutionPolicy Bypass -File results/v3/r9/launch_league.ps1 -Night -DecisionsJson results/v3/r9/bundle_decisions.json -Rounds 10 -CheckCmd "…"
param(
    [string]$DecisionsJson = '',
    [int]$Rounds = 10,
    [int]$Shards = 0,
    [int]$MaxProcs = 6,
    [double]$ProcMemGB = 0.5,
    [string]$CheckCmd = '',
    [string]$Baseline = '',
    [switch]$NoWatch,
    [switch]$DryRun,
    [string]$Window = '22:00-09:00',
    [switch]$CheckAnytime,
    [switch]$Night
)

$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$py = 'C:\Users\Sinhyeok\anaconda3\python.exe'
$logDir = Join-Path $root 'results\v3\r9\logs'
$pidFile = Join-Path $logDir 'pids.txt'

$leagueArgs = "results/v3/r9/league_r9.py --rounds $Rounds --max-procs $MaxProcs --proc-mem-gb $ProcMemGB --window $Window"
if ($DecisionsJson) { $leagueArgs += " --decisions-json $DecisionsJson" }
if ($Shards -gt 0) { $leagueArgs += " --shards $Shards" }
if ($CheckCmd) { $leagueArgs += " --check-cmd `"$CheckCmd`"" }
if ($CheckAnytime) { $leagueArgs += " --check-anytime" }
if ($Night) {
    $leagueArgs = "results/v3/r9/run_night.py --rounds $Rounds --max-procs $MaxProcs --proc-mem-gb $ProcMemGB --window $Window"
    if ($DecisionsJson) { $leagueArgs += " --decisions-json $DecisionsJson" }
    if ($CheckCmd) { $leagueArgs += " --check-cmd `"$CheckCmd`"" }
    if ($CheckAnytime) { $leagueArgs += " --check-anytime" }
    if ($NoWatch) { $leagueArgs += " --no-watch" }
}

if ($DryRun) {
    Push-Location $root
    try { & $py -X utf8 ($leagueArgs.Split(' ') + '--dry-run') } finally { Pop-Location }
    return
}
if (-not $DecisionsJson) { throw "묶음 결정 수가 없다 (-DecisionsJson, C0-9 뒤 STATUS.md 에 등록한 값)" }
if (-not (Test-Path (Join-Path $root $DecisionsJson))) { throw "없는 파일: $DecisionsJson" }
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Launch([string]$argsText, [string]$log, [string]$what) {
    $cmd = "`"$py`" -X utf8 results/v3/r9/spawn_detached.py --append --log $log --what `"$what`" -- $argsText"
    $si = New-CimInstance -Namespace root/cimv2 -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow = [uint16]0}
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $root; ProcessStartupInformation = $si}
    if ($r.ReturnValue -ne 0) { throw "띄우기 실패 ($what): WMI 반환 $($r.ReturnValue)" }
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 250
        $line = Get-Content -Path $pidFile -Encoding utf8 -ErrorAction SilentlyContinue | Where-Object { $_ -like "$what cmd_pid $($r.ProcessId) *" } | Select-Object -Last 1
        if ($line) { break }
    }
    if (-not $line) { $line = "$what 띄우개 pid $($r.ProcessId) — pids.txt 줄을 10 초 안에 못 봤다" }
    Write-Output $line
}

if ($Night) {
    Launch $leagueArgs "results\v3\r9\logs\night.log" "night r9"
    return
}
Launch $leagueArgs "results\v3\r9\logs\league.log" "league r9"
if (-not $NoWatch) {
    $watchArgs = "results/v3/r9/watch_r9.py --interval 300"
    if ($Baseline) { $watchArgs += " --baseline $Baseline" }
    Launch $watchArgs "results\v3\r9\logs\watch.log" "watch r9"
}

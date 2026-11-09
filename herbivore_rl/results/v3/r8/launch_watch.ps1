# R8 본 학습 지켜보기 띄우기 (watch_train.py — 진행표 logs/progress.md, 체크포인트 점검 checkpoints/, 곡선 checkpoints/curve.png).
# 학습과 같은 방식(WMI 창 숨김 → spawn_detached.py 가 창 없는 콘솔로)으로 셸과 떨어진 프로세스로 띄운다. 화면 기록 results/v3/r8/logs/watch.log(덧붙임), PID 는 logs/pids.txt 에 'watch' 줄.
#   powershell -ExecutionPolicy Bypass -File results/v3/r8/launch_watch.ps1
#   -DryRun 이면 띄우지 않고 명령만 적는다. 학습 프로세스는 건드리지 않는다(읽기만).
param(
    [string]$Extra = '',
    [switch]$DryRun
)

$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$py = 'C:\Users\Sinhyeok\anaconda3\python.exe'
$logDir = Join-Path $root 'results\v3\r8\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$pidFile = Join-Path $logDir 'pids.txt'
$log = 'results/v3/r8/logs/watch.log'
$argsText = "results/v3/r8/watch_train.py $Extra".Trim()
$what = 'watch'
$cmd = "`"$py`" -X utf8 results/v3/r8/spawn_detached.py --append --log $log --what $what -- $argsText"
if ($DryRun) { Write-Output "[DryRun] watch :: $argsText >> $log"; return }
$si = New-CimInstance -Namespace root/cimv2 -ClassName Win32_ProcessStartup -ClientOnly -Property @{ShowWindow = [uint16]0}
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $root; ProcessStartupInformation = $si}
if ($r.ReturnValue -ne 0) { throw "띄우기 실패 (watch): WMI 반환 $($r.ReturnValue)" }
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 250
    $line = Get-Content -Path $pidFile -Encoding utf8 -ErrorAction SilentlyContinue | Where-Object { $_ -like "$what cmd_pid $($r.ProcessId) *" } | Select-Object -Last 1
    if ($line) { break }
}
if (-not $line) { $line = "$what 띄우개 pid $($r.ProcessId) — pids.txt 줄을 10 초 안에 못 봤다" }
Write-Output $line

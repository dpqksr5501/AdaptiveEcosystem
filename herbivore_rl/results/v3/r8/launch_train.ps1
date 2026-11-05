# R8 본 학습 띄우기 (설계 AdaptiveEcosystem/Docs/RL_Policy/RL_R8_LEARN_DANGER_DESIGN.md 7절, 상태 results/v3/r8/STATUS.md).
# 학습마다 프로세스 하나를 이 셸과 떨어진 프로세스로 띄운다(WMI Win32_Process.Create — 셸·세션이 끝나도 학습은 이어진다).
# 11-05 고침: 처음 띄운 판(16:59)이 17:05 에 콘솔 창 닫힘(CTRL_CLOSE)으로 죽었다. 이제 WMI 로는 창 숨김(ShowWindow 0) 띄우개 spawn_detached.py 만 띄우고,
# 그것이 학습을 창 없는 콘솔(CREATE_NO_WINDOW)·새 프로세스 묶음으로 띄운 뒤 끝난다 — 닫을 창이 없다.
# 화면 기록 results/v3/r8/logs/train_<실행 이름>.log, 학습 기록 results/v3/r8/logs/<실행 이름>.log.jsonl, 모델 ckpt/r8/<실행 이름>*.zip,
# PID 목록 results/v3/r8/logs/pids.txt(spawn_detached.py 가 적는다). 다른 python·언리얼 프로세스는 건드리지 않는다.
#   powershell -ExecutionPolicy Bypass -File results/v3/r8/launch_train.ps1 -Steps 250000000 -WallHours 10
#   -DryRun 이면 띄우지 않고 명령만 적는다. -NoControl 이면 대조 H0 를 뺀다. 이미 있는 실행 이름의 끝 모델이 있으면 멈춘다.
param(
    [int[]]$Seeds = @(0, 1, 2),
    [long]$Steps = 250000000,
    [double]$WallHours = 10.0,
    [string]$Prefix = 'r8_p',
    [switch]$NoControl,
    [switch]$DryRun
)

$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$py = 'C:\Users\Sinhyeok\anaconda3\python.exe'
$logDir = Join-Path $root 'results\v3\r8\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$pidFile = Join-Path $logDir 'pids.txt'

function Launch([string]$argsText, [string]$log, [string]$what) {
    $cmd = "`"$py`" -X utf8 results/v3/r8/spawn_detached.py --log $log --what `"$what`" -- $argsText"
    if ($DryRun) { Write-Output "[DryRun] $what :: $argsText > $log"; return }
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
function Train([string]$cfg, [int]$seed, [string]$run) {
    if (-not (Test-Path (Join-Path $root $cfg))) { throw "없는 파일: $cfg" }
    if (Test-Path (Join-Path $root "ckpt/r8/$run.zip")) { throw "이미 있는 실행: ckpt/r8/$run.zip — 덮어쓰지 않는다 (사람이 정한다)" }
    $a = "results/v3/r8/train_r8.py --config $cfg --seed $seed --steps $Steps --wall-hours $WallHours --run-name $run"
    Launch $a "results\v3\r8\logs\train_$run.log" "train $run"
}

foreach ($s in $Seeds) {
    Train 'configs/v3_r8_pilot.yaml' $s "${Prefix}_s${s}"
}
if (-not $NoControl) {
    Train 'configs/v3_r8_pilot_h0.yaml' 0 'r8_h0_s0'
}

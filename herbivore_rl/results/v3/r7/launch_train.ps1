# v3 R7 학습 띄우기 (사전 등록 results/v3/r7/PREREG.md 3·5절). 학습마다 프로세스 하나를 이 셸과 떨어진 프로세스로 띄운다(WMI Win32_Process.Create —
# 셸·세션이 끝나도 학습은 이어진다). 화면 기록 results/v3/r7/logs/train_<실행 이름>.log, 체크포인트 ckpt/v3/<실행 이름>*.zip, PID 목록 logs/pids.txt.
#   powershell -ExecutionPolicy Bypass -File results/v3/r7/launch_train.ps1 -Checks      # 본 학습 20M × 시드 0~2 + 대조 '길 끔' 20M × 1 + 2M·5M 점검
#   -DryRun 이면 띄우지 않고 명령만 적는다. -Checks 면 본 학습 점검(early_checks.py)도 떨어진 프로세스로 띄운다.
# R6(results/v3/r6/launch_train.ps1)와 달리 조기 점검 6 조합(-Phase combos)이 없다 — λ 0.98 · 도주 비용 0 은 R6 조기 점검이 고른 값으로 고정했다
# (configs/ppo_r6_lam098.yaml · configs/v3_r7_train.yaml 의 flight_cost 0.0). 이미 있는 실행 이름의 끝 모델이 있으면 덮어쓰지 않고 멈춘다.
param(
    [int[]]$Seeds = @(0, 1, 2),
    [switch]$NoControl,
    [switch]$Checks,
    [switch]$DryRun
)

$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$py = (Get-Command python).Source
$logDir = Join-Path $root 'results\v3\r7\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$pidFile = Join-Path $logDir 'pids.txt'
$ppo = 'configs/ppo_r6_lam098.yaml'
$src5 = 'route0m5 = route0 가중치 그대로(R1b-F + 장애물·두뇌 길 관측 여섯 칸 입력 열 0 + 칸 4 = 칸 1 − 2) + 마스크 판 5(반사 밖 두뇌 FLEE 막음) (results/v3/r7/r7_start.py), 목록 graze·flee·hide — R7 시작 두뇌'
$src6 = 'obs21zero_m6 = obs21zero(R1b s3 + 장애물 관측 세 칸 입력 열 0) 가중치 그대로 + 마스크 판 6 (results/v3/r7/r7_start.py), 목록 graze·flee·hide·freeze — 설정이 얼기를 막는다, R7 대조 길 끔 시작 두뇌'

function Launch([string]$argsText, [string]$log, [string]$what) {
    $cmd = "cmd.exe /c `"set PYTHONUTF8=1&& `"$py`" $argsText > $log 2>&1`""
    if ($DryRun) { Write-Output "[DryRun] $what :: $argsText > $log"; return }
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $root}
    Start-Sleep -Milliseconds 500
    $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($r.ProcessId)" | Where-Object { $_.Name -like 'python*' } | Select-Object -First 1
    $line = "$what cmd_pid $($r.ProcessId) python_pid $($child.ProcessId) log $log started $(Get-Date -Format s)"
    Add-Content -Path $pidFile -Value $line -Encoding utf8
    Write-Output $line
}
function Train([string]$cfg, [int]$seed, [long]$steps, [string]$init, [string]$src, [string]$run, [string]$tb) {
    foreach ($f in @($cfg, $ppo, $init)) {
        if (-not (Test-Path (Join-Path $root $f))) { throw "없는 파일: $f" }
    }
    if (Test-Path (Join-Path $root "ckpt/v3/$run.zip")) { throw "이미 있는 실행: ckpt/v3/$run.zip — 덮어쓰지 않는다 (사람이 정한다)" }
    $a = "train_v3.py --config $cfg --seed $seed --steps $steps --init-from-model $init --init-source `"$src`" --run-name $run --tb $tb --threads 1 --ppo-config $ppo"
    Launch $a "results\v3\r7\logs\train_$run.log" "train $run"
}

foreach ($s in $Seeds) {
    Train 'configs/v3_r7_train.yaml' $s 20000000 'ckpt/v3/v3_r1_g995_s3_obs24route0m5.zip' $src5 "v3_r7_g995_s${s}_20m" 'runs/v3_r7'
}
if (-not $NoControl) {
    Train 'configs/v3_r7off_train.yaml' 0 20000000 'ckpt/v3/v3_r1_g995_s3_obs21zero_m6.zip' $src6 'v3_r7off_g995_s0_20m' 'runs/v3_r7'
}
if ($Checks) {
    $ctl = if ($NoControl) { '' } else { ' --control' }
    Launch "results/v3/r7/early_checks.py --seeds $($Seeds -join ' ')$ctl --at 2 5" 'results\v3\r7\logs\early_checks_main.log' 'early_checks main'
}

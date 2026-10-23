# v3 R6 학습 띄우기 (사전 등록 results/v3/r6/PREREG.md 3·5절). 학습마다 프로세스 하나를 이 셸과 떨어진 프로세스로 띄운다(WMI Win32_Process.Create —
# 셸·세션이 끝나도 학습은 이어진다). 화면 기록 results/v3/r6/logs/train_<실행 이름>.log, 체크포인트 ckpt/v3/<실행 이름>*.zip, PID 목록 logs/pids.txt.
#   powershell -ExecutionPolicy Bypass -File results/v3/r6/launch_train.ps1 -Phase combos -Checks              # 조기 점검 6 조합 (λ 95·98 × c 0·0027·005, 5M, 모델 시드 0)
#   powershell -ExecutionPolicy Bypass -File results/v3/r6/launch_train.ps1 -Phase main -Lam 95 -Cost 0027 -Checks   # 본 학습 20M × 시드 0~2 + 대조 '길 끔' 20M × 1
#   -DryRun 이면 띄우지 않고 명령만 적는다. -Checks 면 조기 점검(early_checks.py)도 떨어진 프로세스로 띄운다.
param(
    [ValidateSet('combos', 'main')][string]$Phase = 'combos',
    [ValidateSet('95', '98')][string]$Lam = '95',
    [ValidateSet('0', '0027', '005')][string]$Cost = '0',
    [int[]]$Seeds = @(0, 1, 2),
    [switch]$NoControl,
    [switch]$Checks,
    [switch]$DryRun
)

$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$py = (Get-Command python).Source
$logDir = Join-Path $root 'results\v3\r6\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$pidFile = Join-Path $logDir 'pids.txt'
$src0 = 'route0 = R1b-F + 장애물·두뇌 길 관측 여섯 칸 입력 열 0 + 칸 4 = 칸 1 − 2 (results/v3/route/route_extend.py), 목록 graze·flee·hide — R6 두 길 시작 두뇌'
$srcOff = 'obs21zero = R1b s3 (게임 두뇌) + 장애물 관측 세 칸 입력 열 0 (results/v3/r5/zero_extend.py), 목록 graze·flee·hide·freeze — 설정이 얼기를 막아 R1b-F 로 시작, R6 대조 길 끔 시작 두뇌'

function Config-Of([bool]$route, [string]$c) {
    $stem = if ($route) { 'v3_r6_train' } else { 'v3_r6off_train' }
    if ($c -eq '0') { return "configs/$stem.yaml" } else { return "configs/${stem}_c$c.yaml" }
}
function Ppo-Of([string]$l) {
    if ($l -eq '95') { return 'configs/ppo_best.yaml' } else { return 'configs/ppo_r6_lam098.yaml' }
}
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
function Train([string]$cfg, [string]$ppo, [int]$seed, [long]$steps, [string]$init, [string]$src, [string]$run, [string]$tb) {
    foreach ($f in @($cfg, $ppo, $init)) {
        if (-not (Test-Path (Join-Path $root $f))) { throw "없는 파일: $f" }
    }
    $a = "train_v3.py --config $cfg --seed $seed --steps $steps --init-from-model $init --init-source `"$src`" --run-name $run --tb $tb --threads 1 --ppo-config $ppo"
    Launch $a "results\v3\r6\logs\train_$run.log" "train $run"
}

if ($Phase -eq 'combos') {
    foreach ($l in @('95', '98')) {
        foreach ($c in @('0', '0027', '005')) {
            Train (Config-Of $true $c) (Ppo-Of $l) 0 5000000 'ckpt/v3/v3_r1_g995_s3_obs24route0.zip' $src0 "v3_r6e_l${l}_c${c}_s0_5m" 'runs/v3_r6e'
        }
    }
    if ($Checks) { Launch 'results/v3/r6/early_checks.py combos' 'results\v3\r6\logs\early_checks_combos.log' 'early_checks combos' }
} else {
    foreach ($s in $Seeds) {
        Train (Config-Of $true $Cost) (Ppo-Of $Lam) $s 20000000 'ckpt/v3/v3_r1_g995_s3_obs24route0.zip' $src0 "v3_r6_g995_s${s}_20m" 'runs/v3_r6'
    }
    if (-not $NoControl) {
        Train (Config-Of $false $Cost) (Ppo-Of $Lam) 0 20000000 'ckpt/v3/v3_r1_g995_s3_obs21zero.zip' $srcOff 'v3_r6off_g995_s0_20m' 'runs/v3_r6'
    }
    if ($Checks) {
        $ctl = if ($NoControl) { '' } else { ' --control' }
        Launch "results/v3/r6/early_checks.py main --seeds $($Seeds -join ' ')$ctl --at 2 5 --cost $Cost --lam $Lam" 'results\v3\r6\logs\early_checks_main.log' 'early_checks main'
    }
}

# v3 R5 본 학습 띄우기 (사전 등록 results/v3/r5/PREREG.md 3절). 모델 시드마다 프로세스 하나를 이 셸과 떨어진 프로세스로 띄운다(WMI Win32_Process.Create —
# 셸·세션이 끝나도 학습은 이어진다). 화면 기록 results/v3/r5/logs/train_s<시드>.log, 체크포인트 ckpt/v3/v3_r5_g995_s<시드>_20m*.zip, PID 목록 logs/pids.txt.
#   powershell -ExecutionPolicy Bypass -File results/v3/r5/launch_train.ps1                 # 시드 0~5
#   powershell -ExecutionPolicy Bypass -File results/v3/r5/launch_train.ps1 -Seeds 6,7,8,9,10,11 -PpoConfig configs/ppo_r5_lr3.yaml   # 대응 1회(PREREG 5절) 꼴 — 그 PPO 설정은 그때 만든다
param([int[]]$Seeds = @(0, 1, 2, 3, 4, 5), [string]$PpoConfig = "configs/ppo_best.yaml")

$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)))
$py = (Get-Command python).Source
$src = 'R1b s3 (게임 두뇌) + 장애물 관측 세 칸 입력 열 0 (results/v3/r5/zero_extend.py), 목록 graze·flee·hide·freeze — R5 설정이 얼기를 막아 R1b-F 로 시작'
$pidFile = Join-Path $root 'results\v3\r5\logs\pids.txt'
foreach ($s in $Seeds) {
    $run = "v3_r5_g995_s${s}_20m"
    $log = "results\v3\r5\logs\train_s$s.log"
    $args_ = "train_v3.py --config configs/v3_r5_train.yaml --seed $s --steps 20000000 --init-from-model ckpt/v3/v3_r1_g995_s3_obs21zero.zip " +
             "--init-source `"$src`" --run-name $run --tb runs/v3_r5 --threads 1 --ppo-config $PpoConfig"
    $cmd = "cmd.exe /c `"set PYTHONUTF8=1&& `"$py`" $args_ > $log 2>&1`""
    $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $cmd; CurrentDirectory = $root}
    Start-Sleep -Milliseconds 500
    $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($r.ProcessId)" | Where-Object { $_.Name -like 'python*' } | Select-Object -First 1
    $line = "seed $s cmd_pid $($r.ProcessId) python_pid $($child.ProcessId) run $run log $log started $(Get-Date -Format s)"
    Add-Content -Path $pidFile -Value $line -Encoding utf8
    Write-Output $line
}

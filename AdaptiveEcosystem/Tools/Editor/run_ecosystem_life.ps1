param([ValidateSet('observe','save','load')][string]$Mode='observe',
    [ValidatePattern('^[A-Za-z0-9_]+$')][string]$Name='Observe',
    [int]$Seed=23,[ValidateRange(10,3600)][double]$Duration=120,
    [ValidateRange(0,3600)][double]$SimulationSeconds=0,[switch]$Benchmark,
    [ValidateSet(-1,0,1)][int]$Life=-1,
    [ValidateRange(1,60)][double]$SampleSeconds=5,[switch]$Csv,
    [ValidatePattern('^[A-Za-z0-9_]+$')][string]$Slot='LifeRestart',
    [ValidateRange(-1,12)][int]$Wolves=-1,
    [ValidateSet('','Barren','Forest','Highland')][string]$DroughtRegion='',
    [double]$SaveAt=75,[string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskOut=Join-Path $taskRoot 'Saved/EcosystemLife_20261023'
New-Item -ItemType Directory -Path $taskOut -Force|Out-Null
$taskBusy=Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue
if($taskBusy){throw 'An engine/build process is running; no process was stopped.'}
if($Benchmark -and ($Mode -ne 'observe' -or $SimulationSeconds -le 0)){throw 'Fixed-step benchmark requires an explicit simulation-only observe target'}
if($DroughtRegion -and $Mode -ne 'observe'){throw 'Development drought is a separate observation fixture, not a checkpoint trial'}
$taskExit=if($SimulationSeconds -gt 0){$SimulationSeconds+60}else{$Duration+45}
$taskArguments=@((Join-Path $taskRoot 'AdaptiveEcosystem.uproject'),'/Game/JYU/Maps/LV_JYU_Ecosystem',
    '-server','-NullRHI','-unattended','-nop4','-nosplash',"-EcoV3Seed=$Seed",'-EcoV3SocialControl=0','-LifeAuditQuitOnFinish',
    "-EcoIntegrationExitAfter=$taskExit","-LifeAuditMode=$Mode","-LifeAuditName=$Name","-LifeAuditDuration=$Duration",
    "-LifeAuditSimulationSeconds=$SimulationSeconds","-LifeAuditSaveAt=$SaveAt",
    "-LifeAuditSampleSeconds=$SampleSeconds",
    "-LifeAuditSlot=$Slot",
    "-ExecCmds=py $taskRoot/Tools/Editor/audit_ecosystem_life.py","-abslog=$taskOut/$Name.log")
if($Benchmark){$taskArguments+=@('-benchmark','-fps=60','-novsync')}
if($Life -ge 0){$taskArguments+="-EcoEcosystemLife=$Life"}
if($Csv){$taskArguments+='-LifeAuditCsv'}
if($Wolves -ge 0){$taskArguments+="-EcoV3Wolves=$Wolves"}
if($DroughtRegion){$taskArguments+="-LifeAuditDrought=$DroughtRegion"}
$taskQuoted=$taskArguments|ForEach-Object{'"'+$_.Replace('"','\"')+'"'}
$taskStart=Get-Date
$taskProcess=Start-Process (Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe') -ArgumentList ($taskQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $taskRoot
while(-not $taskProcess.WaitForExit(5000)){}
if($taskProcess.ExitCode -ne 0){throw "Authority process exit=$($taskProcess.ExitCode); inspect $Name.log"}
$taskReportPath=Join-Path $taskOut ($Name+'_Life.json')
if(-not(Test-Path $taskReportPath) -or (Get-Item $taskReportPath).LastWriteTime -lt $taskStart){throw 'Missing fresh observer report'}
$taskReport=Get-Content $taskReportPath -Raw|ConvertFrom-Json
if($taskReport.result -ne 'FINISHED'){throw "Life audit failed: $($taskReport.error)"}
$taskLog=Get-Content (Join-Path $taskOut ($Name+'.log')) -Raw
if($taskLog -match 'Runtime stopped|receipt rejected|LIFE_AUDIT_ERROR'){throw 'Authority runtime/observer failed'}
Write-Output ("LIFE_RUN_FINISHED Name={0} Seed={1} Alive={2} NaturalChildren={3}" -f $Name,$Seed,$taskReport.alive_at_end,$taskReport.natural_child_ids.Count)

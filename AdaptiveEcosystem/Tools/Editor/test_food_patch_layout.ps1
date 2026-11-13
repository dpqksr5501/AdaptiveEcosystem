# Bounded S0/S1 observation in the existing 1102 map. Never saves map/assets or stops another engine.
param(
    [string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8',
    [ValidatePattern('^[A-Za-z0-9_]+$')][string]$AuditFolder='FoodPatchLayout',
    [ValidateSet('Profile','Feeding')][string]$Mode='Profile',
    [ValidateRange(30,3600)][int]$Duration=65,
    [int]$Seed=23,
    [switch]$PatchLayout,
    [ValidatePattern('^[A-Za-z0-9_]+$')][string]$Region='JWJ_HuntingMeadow'
)
$ErrorActionPreference='Stop'
$taskBusy=Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue
if($taskBusy){throw 'Engine/build active; no process started or stopped.'}
if($Mode -eq 'Profile' -and $Duration -lt 65){throw 'Complete CSV profile requires at least 65 seconds.'}
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskOut=Join-Path $taskRoot ('Saved/'+$AuditFolder)
if(Test-Path (Join-Path $taskOut 'PIE_Runtime.json')){throw 'Choose a fresh evidence folder; previous runtime evidence is preserved.'}
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
$taskMode=if($Mode -eq 'Profile'){'-VegetationGrassProfile'}else{'-VegetationGrassFeedingCheck'}
$taskPatch=if($PatchLayout){'-VegetationPatchLayout'}else{'-VegetationPatchLayoutDisabled'}
$taskArgs=@((Join-Path $taskRoot 'AdaptiveEcosystem.uproject'),'/Game/JWJ/1102_Integration_JWJ',
    '-unattended','-nop4','-nosplash','-NoSound','-nosteam','-d3d11','-windowed','-ResX=1280','-ResY=720',
    "-EcoV3Seed=$Seed",'-VegetationPIE','-VegetationAuthored',$taskMode,$taskPatch,
    '-VegetationMap=1102_Integration_JWJ',"-VegetationGrassRegion=$Region","-VegetationAuditFolder=$AuditFolder",
    "-VegetationAuditDuration=$Duration","-ExecCmds=py $PSScriptRoot/audit_vegetation_runtime.py","-abslog=$taskOut/PIE.log")
$taskQuoted=@($taskArgs|ForEach-Object {'"'+$_+'"'})
$taskStart=[DateTime]::UtcNow
$taskProcess=Start-Process (Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.exe') -ArgumentList ($taskQuoted -join ' ') -WindowStyle Hidden -WorkingDirectory $taskRoot -PassThru
$taskDeadline=$taskStart.AddSeconds($Duration+240)
while(-not $taskProcess.WaitForExit(5000)){if([DateTime]::UtcNow -gt $taskDeadline){throw 'Observation timeout; no engine was killed. Inspect its log before continuing.'}}
@{ProcessId=$taskProcess.Id;ExitCode=$taskProcess.ExitCode;StartedUtc=$taskStart;EndedUtc=[DateTime]::UtcNow;
    Mode=$Mode;PatchLayout=[bool]$PatchLayout;Seed=$Seed;Duration=$Duration;Arguments=$taskArgs} |
    ConvertTo-Json -Depth 5 | Set-Content (Join-Path $taskOut 'Process.json') -Encoding utf8
if($taskProcess.ExitCode -ne 0){throw 'Engine exited abnormally; inspect PIE.log.'}
$taskReport=Get-Content (Join-Path $taskOut 'PIE_Runtime.json') -Raw|ConvertFrom-Json
if($taskReport.result -ne 'FINISHED'){throw "Observer failed: $($taskReport.error)"}
if($Mode -eq 'Profile'){
    & (Join-Path $EngineRoot 'Engine/Binaries/ThirdParty/Python3/Win64/python.exe') (Join-Path $PSScriptRoot 'summarize_vegetation_evidence.py') --grass-profile $AuditFolder
    if($LASTEXITCODE -ne 0){throw 'Profile evidence gate failed.'}
}
Write-Output "FOOD_PATCH_LAYOUT_FINISHED Mode=$Mode PatchLayout=$PatchLayout Folder=$AuditFolder"

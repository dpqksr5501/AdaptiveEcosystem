param([ValidateSet('automation','assets','harmless','ambush','chase','pie','recovery')][string]$Check,
    [string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskOut=Join-Path $taskRoot 'Saved/EcosystemLife_20261023'
New-Item -ItemType Directory -Path $taskOut -Force|Out-Null
if(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue){throw 'Engine/build busy; no process stopped'}
$taskArgs=@((Join-Path $taskRoot 'AdaptiveEcosystem.uproject'),'-unattended','-nop4','-nosplash',"-abslog=$taskOut/Validation_$Check.log")
$taskExe='UnrealEditor-Cmd.exe'
$taskReport=$null
switch($Check){
    automation {
        $taskArgs+=@('-NullRHI','-ExecCmds=Automation RunTests AdaptiveEcosystem;Quit','-TestExit=Automation Test Queue Empty',"-ReportExportPath=$taskOut/AutomationFinal")
        $taskReport=Join-Path $taskOut 'AutomationFinal/index.json'
    }
    assets {
        $taskArgs+=@('-NullRHI',"-ExecutePythonScript=$taskRoot/Tools/Editor/audit_jyu_ecosystem_assets.py",'-EcosystemAssetAuditFolder=EcosystemLife_20261023')
        $taskReport=Join-Path $taskOut 'AssetReload.json'
    }
    pie {
        $taskExe='UnrealEditor.exe'
        $taskArgs=@($taskArgs[0],'/Game/JYU/Maps/LV_JYU_Ecosystem')+$taskArgs[1..($taskArgs.Length-1)]
        $taskArgs+=@('-d3d11','-windowed','-ResX=1280','-ResY=720','-EcoV3Seed=23','-VegetationPIE','-VegetationAuthored','-VegetationLifeFocus','-VegetationMap=LV_JYU_Ecosystem','-VegetationAuditFolder=EcosystemLife_20261023','-VegetationAuditName=PIE','-VegetationAuditDuration=125',"-ExecCmds=py $taskRoot/Tools/Editor/audit_vegetation_runtime.py")
        $taskReport=Join-Path $taskOut 'PIE_Runtime.json'
    }
    recovery {
        $taskArgs+=@('/Game/JYU/Maps/LV_JYU_Ecosystem','-game','-NullRHI','-EcoV3Seed=23','-EcoV3Wolves=2','-EcoIntegrationExitAfter=110','-EcosystemAuditQuitOnFinish',"-ExecCmds=py $taskRoot/Tools/Editor/audit_ecosystem_recovery.py")
        $taskReport=Join-Path $taskOut 'Recovery.json'
    }
    default {
        $taskArgs+=@('/Game/JYU/Maps/LV_JYU_Ecosystem','-game','-NullRHI','-EcoV3Seed=23','-EcoV3Wolves=0','-EcoIntegrationExitAfter=90','-EcosystemAuditQuitOnFinish',"-EncounterTrial=$Check", "-ExecCmds=py $taskRoot/Tools/Editor/audit_ecosystem_encounters.py")
        $taskReport=Join-Path $taskOut ("Encounter_$Check.json")
    }
}
$taskQuoted=$taskArgs|ForEach-Object{'"'+$_.Replace('"','\"')+'"'}
$taskStart=Get-Date
$taskProcess=Start-Process (Join-Path $EngineRoot "Engine/Binaries/Win64/$taskExe") -ArgumentList ($taskQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $taskRoot
while(-not $taskProcess.WaitForExit(5000)){}
if($taskProcess.ExitCode -ne 0){throw "Engine process failed: $Check exit=$($taskProcess.ExitCode)"}
if(-not(Test-Path $taskReport) -or (Get-Item $taskReport).LastWriteTime -lt $taskStart){throw "Fresh report missing: $Check"}
$taskJson=Get-Content $taskReport -Raw|ConvertFrom-Json
if($Check -eq 'automation'){
    if($taskJson.failed -ne 0 -or $taskJson.notRun -ne 0 -or $taskJson.succeeded -lt 219){throw 'Automation gate failed'}
}elseif($Check -eq 'assets'){
    if(-not $taskJson.passed){throw 'Asset reload gate failed'}
}elseif($taskJson.result -ne 'FINISHED'){throw "Observer failed: $($taskJson.error)"}
Write-Output "ECOSYSTEM_VALIDATION_FINISHED $Check"

param(
    [ValidateSet('automation','baseline','hunt','drought','save','load','wolf','deer','health')][string]$Check='automation',
    [ValidateRange(20,3600)][int]$SimulationSeconds=1800,
    [int]$Seed=23,
    [string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8'
)
$ErrorActionPreference='Stop'
$huntingRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$huntingOut=Join-Path $huntingRoot 'Saved/PlayerHunting_20261105'
New-Item -ItemType Directory -Force $huntingOut | Out-Null
if(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue){throw 'Engine/build busy; no process stopped'}
$huntingArguments=@((Join-Path $huntingRoot 'AdaptiveEcosystem.uproject'),'/Game/JWJ/1102_Integration_JWJ','-NullRHI','-unattended','-nop4','-nosplash',"-EcoV3Seed=$Seed")
$huntingExe='UnrealEditor-Cmd.exe'
$huntingReport=$null
if($Check -eq 'automation'){
    $huntingArguments+=@('-ExecCmds=Automation RunTests AdaptiveEcosystem;Quit','-TestExit=Automation Test Queue Empty',"-ReportExportPath=$huntingOut/AutomationFinal")
    $huntingReport=Join-Path $huntingOut 'AutomationFinal/index.json'
}elseif($Check -in @('wolf','deer','health')){
    $huntingExe='UnrealEditor.exe'
    $huntingScript=if($Check -eq 'health'){'verify_player_hunting_health.py'}else{'run_current_hunting_pie.py'}
    if($Check -eq 'deer'){$huntingArguments+='-HuntingSpecies=Herbivore'}
    $huntingArguments+="-ExecCmds=py $huntingRoot/Tools/Editor/$huntingScript"
    $huntingReport=Join-Path $huntingOut $(if($Check -eq 'health'){'PIE_PlayerHealth.json'}elseif($Check -eq 'deer'){'PIE_Hunting_Herbivore.json'}else{'PIE_Hunting_Wolf.json'})
}else{
    $huntingArguments+=@('-game','-benchmark','-fps=30',"-HuntingAudit=$Check","-HuntingSeconds=$SimulationSeconds",
        "-EcoIntegrationExitAfter=$($SimulationSeconds+90)","-ExecCmds=py $huntingRoot/Tools/Editor/audit_player_hunting_loop.py")
    $huntingReport=Join-Path $huntingOut "Loop_$($Check)_$Seed.json"
}
$huntingArguments+="-abslog=$huntingOut/Check_$($Check)_$Seed.log"
$huntingQuoted=$huntingArguments|ForEach-Object{'"'+$_+'"'}
$huntingStarted=Get-Date
$huntingProcess=Start-Process (Join-Path $EngineRoot "Engine/Binaries/Win64/$huntingExe") -ArgumentList ($huntingQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $huntingRoot
while(-not $huntingProcess.WaitForExit(5000)){}
if($huntingProcess.ExitCode -ne 0){throw "Test process failed: $Check exit=$($huntingProcess.ExitCode)"}
if(-not(Test-Path $huntingReport) -or (Get-Item $huntingReport).LastWriteTime -lt $huntingStarted){throw "Fresh report missing: $Check"}
$huntingResult=Get-Content -Raw $huntingReport | ConvertFrom-Json
if($Check -eq 'automation'){
    if($huntingResult.failed -ne 0 -or $huntingResult.notRun -ne 0){throw 'Automation failed; inspect report'}
    Write-Output "AUTOMATION_PASS success=$($huntingResult.succeeded) warnings=$($huntingResult.succeededWithWarnings)"
}else{
    if($huntingResult.result -ne 'PASS'){throw "Verification failed: $($huntingResult.error)"}
    Write-Output "HUNTING_CHECK_PASS $Check Seed=$Seed"
}

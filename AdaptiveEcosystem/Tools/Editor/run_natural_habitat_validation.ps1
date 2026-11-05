param([ValidateSet('Automation','Play','Ecology','Persistence','Network','Authoring','Transfer','Population','PopulationPlay')][string]$Mode='Automation',
    [ValidatePattern('^[A-Za-z0-9_]+$')][string]$AuditFolder='NaturalHabitatRelease_20261030')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskOut=Join-Path $taskRoot ('Saved/'+$AuditFolder)
if(Test-Path (Join-Path $taskOut 'HoldBeforeNextRun.txt')){throw 'Queued validation held after normal exit for policy-boundary review. No process stopped.'}
New-Item -ItemType Directory -Path $taskOut -Force|Out-Null
$taskEngine='C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64'
function Run-Natural([string]$Name,[string[]]$Extra,[bool]$Render=$false){
    if(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue){throw 'Engine/build busy. No process stopped.'}
    $taskExe=if($Render){'UnrealEditor.exe'}else{'UnrealEditor-Cmd.exe'}
    $taskArgs=@("$taskRoot/AdaptiveEcosystem.uproject",'-unattended','-nop4','-nosplash',"-abslog=$taskOut/$Name.log")+$Extra
    $taskProcess=Start-Process "$taskEngine/$taskExe" -ArgumentList (($taskArgs|ForEach-Object{'"'+$_+'"'}) -join ' ') -WindowStyle Hidden -WorkingDirectory $taskRoot -PassThru
    "STARTED $Name PID=$($taskProcess.Id)"
    while(-not $taskProcess.WaitForExit(5000)){}
    "EXITED $Name Code=$($taskProcess.ExitCode)"
    if($taskProcess.ExitCode -ne 0){throw "Engine failure: $Name"}
}
if($Mode -eq 'Population'){
    Run-Natural 'PopulationAuthoring' @('-NullRHI',"-ExecCmds=py $taskRoot/Tools/Editor/author_jyu_natural_population.py")
    if((Get-Content "$taskRoot/Saved/NaturalPopulation_20261030/PopulationAuthoring.json" -Raw|ConvertFrom-Json).result -ne 'FINISHED'){throw 'Population authoring failed'}
}elseif($Mode -eq 'Authoring'){
    Run-Natural 'Authoring' @('-NullRHI',"-ExecCmds=py $taskRoot/Tools/Editor/apply_jyu_natural_habitats.py")
    Run-Natural 'PresentationAuthoring' @('-NullRHI',"-ExecCmds=py $taskRoot/Tools/Editor/author_jyu_natural_presentation.py")
    if((Get-Content "$taskRoot/Saved/NaturalHabitat_20261030/PresentationAuthoring.json" -Raw|ConvertFrom-Json).result -ne 'FINISHED'){throw 'Owned presentation authoring failed'}
    Run-Natural 'PopulationAuthoring' @('-NullRHI',"-ExecCmds=py $taskRoot/Tools/Editor/author_jyu_natural_population.py")
    if((Get-Content "$taskRoot/Saved/NaturalPopulation_20261030/PopulationAuthoring.json" -Raw|ConvertFrom-Json).result -ne 'FINISHED'){throw 'Population authoring failed'}
}elseif($Mode -eq 'Transfer'){
    Run-Natural 'TransferFixture' @('-NullRHI','-EcoV3Wolves=0',"-HabitatTransferAuditFolder=$AuditFolder","-ExecCmds=py $taskRoot/Tools/Editor/test_natural_habitat_transfer.py")
    $taskReport=Get-Content "$taskOut/TransferFixture.json" -Raw|ConvertFrom-Json
    if($taskReport.result -ne 'FINISHED'){throw "Transfer fixture failed: $($taskReport.error)"}
}elseif($Mode -eq 'Automation'){
    Run-Natural 'AutomationFinal' @('-NullRHI','-ExecCmds=Automation RunTests AdaptiveEcosystem;Quit','-TestExit=Automation Test Queue Empty',"-ReportExportPath=$taskOut/AutomationFinal")
    $taskReport=Get-Content "$taskOut/AutomationFinal/index.json" -Raw|ConvertFrom-Json
    "AUTOMATION success=$($taskReport.succeeded) warning=$($taskReport.succeededWithWarnings) failed=$($taskReport.failed) notRun=$($taskReport.notRun)"
    if($taskReport.failed -or $taskReport.notRun){throw 'Automation failed'}
}elseif($Mode -in @('Play','PopulationPlay')){
    $taskFocus=if($Mode -eq 'PopulationPlay'){'-PopulationFocus'}else{'-NoPopulationFocus'}
    Run-Natural 'NaturalPIE' @('/Game/JYU/Maps/LV_JYU_Ecosystem','-d3d11','-windowed','-ResX=1280','-ResY=720','-VegetationPIE','-VegetationAuthored','-VegetationMap=LV_JYU_Ecosystem',"-VegetationAuditFolder=$AuditFolder",'-VegetationAuditName=NaturalPIE','-VegetationAuditDuration=165',$taskFocus,"-ExecCmds=py $taskRoot/Tools/Editor/audit_natural_habitat_play.py") $true
    $taskReport=Get-Content "$taskOut/NaturalPIE_Runtime.json" -Raw|ConvertFrom-Json
    if($taskReport.result -ne 'FINISHED'){throw "PIE observer: $($taskReport.error)"}
}elseif($Mode -eq 'Ecology'){
    foreach($taskName in @('Natural23','Natural47','Drought23','NoPredators47')){
        $taskSeed=if($taskName -match '47'){47}else{23}
        $taskSeconds=if($taskName -eq 'Natural23'){1800}else{600}
        $taskArgs=@('/Game/JYU/Maps/LV_JYU_Ecosystem','-server','-NullRHI','-benchmark','-fps=60','-novsync',"-EcoV3Seed=$taskSeed",'-LifeAuditQuitOnFinish',"-LifeAuditName=$taskName","-LifeAuditFolder=$AuditFolder",'-LifeAuditDuration=1200',"-LifeAuditSimulationSeconds=$taskSeconds",'-LifeAuditSampleSeconds=10',"-EcoIntegrationExitAfter=$($taskSeconds+60)","-ExecCmds=py $taskRoot/Tools/Editor/audit_ecosystem_life.py")
        if($taskName -in @('Drought23','NoPredators47')){$taskArgs+='-EcoV3Wolves=0'}
        if($taskName -eq 'Drought23'){$taskArgs+='-LifeAuditDrought=Barren'}
        Run-Natural $taskName $taskArgs
        $taskReport=Get-Content "$taskOut/${taskName}_Life.json" -Raw|ConvertFrom-Json
        "ECOLOGY $taskName result=$($taskReport.result) alive=$($taskReport.alive_at_end)"
        if($taskReport.result -ne 'FINISHED'){throw "Observer failed: $($taskReport.error)"}
    }
}elseif($Mode -eq 'Network'){
    & "$taskRoot/Tools/Editor/test_vegetation_network.ps1" -Map /Game/JYU/Maps/LV_JYU_Ecosystem -AuthoredWeather -ChildCoverage -AuditFolder ($AuditFolder+'_Network') -OverlapClients -ClientAAt 10 -ClientBAt 95 -Duration 140 -ExitAfter 190
}elseif($Mode -eq 'Persistence'){
    foreach($taskName in @('Save','Load')){
        $taskDuration=if($taskName -eq 'Save'){95}else{20}
        Run-Natural $taskName @('/Game/JYU/Maps/LV_JYU_Ecosystem','-server','-NullRHI','-EcoV3Wolves=0','-LifeAuditQuitOnFinish',"-LifeAuditMode=$($taskName.ToLower())", "-LifeAuditName=$taskName","-LifeAuditFolder=$AuditFolder", "-LifeAuditDuration=$taskDuration",'-LifeAuditSaveAt=75',"-LifeAuditSlot=$AuditFolder",'-LifeAuditSampleSeconds=5',"-EcoIntegrationExitAfter=$($taskDuration+45)","-ExecCmds=py $taskRoot/Tools/Editor/audit_ecosystem_life.py")
        $taskReport=Get-Content "$taskOut/${taskName}_Life.json" -Raw|ConvertFrom-Json
        if($taskReport.result -ne 'FINISHED'){throw "Persistence failed: $($taskReport.error)"}
    }
}

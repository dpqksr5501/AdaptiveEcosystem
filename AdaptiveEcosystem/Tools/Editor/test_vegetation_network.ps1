# Dedicated authority + two successive late joins. All exits are normal timed exits.
param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8',
    [ValidateSet('/Game/JYU/Maps/LV_JYU_HerdMigration','/Game/JYU/Maps/LV_JYU_Ecosystem')][string]$Map='/Game/JYU/Maps/LV_JYU_HerdMigration',
    [switch]$AuthoredWeather,[ValidatePattern('^[A-Za-z0-9_]+$')][string]$AuditFolder='Vegetation_20261023',
    [double]$Duration=125,[double]$ExitAfter=180,
    [int]$Seed=23,
    [switch]$OverlapClients,
    [ValidateRange(10,600)][double]$ClientAAt=30,[ValidateRange(45,600)][double]$ClientBAt=95)
$ErrorActionPreference='Stop'
foreach($taskValue in @($Duration,$ExitAfter,$ClientAAt,$ClientBAt)){
    if([double]::IsNaN($taskValue) -or [double]::IsInfinity($taskValue)){throw 'Run times must be finite; no engine process was started'}
}
if($Duration -lt 20 -or $Duration -gt 3600 -or $ExitAfter -gt 7200 -or $ExitAfter -le $Duration+10){throw 'Observer must finish at least 10 seconds before the bounded server exit'}
if($ClientBAt -le $ClientAAt+35 -or $ExitAfter -le $ClientBAt+45){throw 'Client join times must leave separate 30-second sessions before server exit'}
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskOut=Join-Path $taskRoot ('Saved/'+$AuditFolder)
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
$taskProject=Join-Path $taskRoot 'AdaptiveEcosystem.uproject'
$taskEngine=Join-Path $EngineRoot 'Engine/Binaries/Win64'
$taskBusy=Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue
if($taskBusy){throw 'Engine/build still running; no process stopped and no new run started.'}
function Start-VegetationProcess([string]$Exe,[string[]]$Arguments){
    $quoted=@($Arguments|ForEach-Object {'"'+$_+'"'})
    Start-Process $Exe -ArgumentList ($quoted -join ' ') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru
}
$taskStarted=[DateTime]::UtcNow
$taskServerLog=Join-Path $taskOut 'Server.log'
$taskMode=if($AuthoredWeather){'-VegetationAuthored'}else{'-EcoVegetation'}
$taskMapName=($Map -split '/')[-1]
$taskConnectionMode=if($OverlapClients){'-VegetationOverlapExpected'}else{'-VegetationSequentialExpected'}
$taskServer=Start-VegetationProcess "$taskEngine/UnrealEditor-Cmd.exe" @($taskProject,$Map,
    '-server','-NullRHI','-unattended','-nop4','-port=7777',$taskMode,$taskConnectionMode,'-EcoV3DeerPerRegion=48','-EcoV3SocialControl=0',"-EcoV3Seed=$Seed",
    "-EcoIntegrationExitAfter=$ExitAfter",'-EcoIntegrationObserverCycle','-VegetationAuditName=Server',"-VegetationAuditDuration=$Duration",
    "-VegetationMap=$taskMapName","-VegetationAuditFolder=$AuditFolder",
    "-ExecCmds=py $taskRoot/Tools/Editor/audit_vegetation_runtime.py","-AbsLog=$taskServerLog")
$taskReadyDeadline=[DateTime]::UtcNow.AddSeconds(90)
while($true){
    if($taskServer.HasExited){throw 'Server exited before ready; inspect first error.'}
    if((Test-Path $taskServerLog) -and (Get-Item $taskServerLog).LastWriteTimeUtc -ge $taskStarted -and
        (Get-Content $taskServerLog -Raw) -match '\[Eco Integration\] NetMode=1 LogicalOwned=[1-9]'){break}
    if([DateTime]::UtcNow -gt $taskReadyDeadline){throw 'Readiness timeout; leave the normal server exit timer running.'}
    Start-Sleep -Seconds 1
}
$taskResults=@()
$taskClients=@()
foreach($entry in @(@{Name='ClientA';At=$ClientAAt},@{Name='ClientB';At=$ClientBAt})){
    while(([DateTime]::UtcNow-$taskStarted).TotalSeconds -lt $entry.At){
        if($taskServer.HasExited){throw 'Server exited before join'}
        Start-Sleep -Seconds 1
    }
    $taskClientStart=[DateTime]::UtcNow
    $taskLifetime=if($OverlapClients -and $entry.Name -eq 'ClientA'){$ClientBAt-$ClientAAt+40}else{30}
    $taskProbe=$taskLifetime-4
    $taskClient=Start-VegetationProcess "$taskEngine/UnrealEditor.exe" @($taskProject,'127.0.0.1:7777','-game','-d3d11','-unattended','-nop4','-windowed',
        '-ResX=960','-ResY=540','-NoSound',"-EcoIntegrationExitAfter=$taskLifetime","-VegetationClientDuration=$taskProbe","-VegetationClientName=$($entry.Name)",
        "-VegetationMap=$taskMapName","-VegetationAuditFolder=$AuditFolder",
        "-ExecCmds=py $taskRoot/Tools/Editor/audit_vegetation_client.py","-AbsLog=$(Join-Path $taskOut ($entry.Name+'.log'))")
    $taskClients+=@{Name=$entry.Name;Process=$taskClient;Started=$taskClientStart;Lifetime=$taskLifetime}
}
foreach($taskEntry in $taskClients){
    $taskClient=$taskEntry.Process;$taskClientStart=$taskEntry.Started
    $taskDeadline=$taskClientStart.AddSeconds($taskEntry.Lifetime+70)
    while(-not $taskClient.WaitForExit(5000)){if([DateTime]::UtcNow -gt $taskDeadline){throw 'Client timeout; do not kill it.'}}
    if($taskClient.ExitCode -ne 0){throw "Client exit=$($taskClient.ExitCode)"}
    $taskReport=Join-Path $taskOut ($taskEntry.Name+'_Client.json')
    if(-not(Test-Path $taskReport) -or (Get-Item $taskReport).LastWriteTimeUtc -lt $taskClientStart){throw 'Missing fresh client evidence'}
    $taskObserved=Get-Content $taskReport -Raw|ConvertFrom-Json
    if(-not $taskObserved.passed){throw 'Client received visuals/authority check failed; server timer left running.'}
    $taskResults+=@{Name=$taskEntry.Name;ExitCode=$taskClient.ExitCode;AuthorityAgents=$taskObserved.authority_agents;Fields=$taskObserved.best.fields;StartedUtc=$taskClientStart;Lifetime=$taskEntry.Lifetime}
    Write-Output "$($taskEntry.Name) normal exit; authority=$($taskObserved.authority_agents), fields=$($taskObserved.best.fields.Count)"
}
$taskDeadline=$taskStarted.AddSeconds($ExitAfter+120)
while(-not $taskServer.WaitForExit(5000)){if([DateTime]::UtcNow -gt $taskDeadline){throw 'Server timeout; do not kill it.'}}
if($taskServer.ExitCode -ne 0){throw "Server exit=$($taskServer.ExitCode)"}
$taskRuntimePath=Join-Path $taskOut 'Server_Runtime.json'
if(-not(Test-Path $taskRuntimePath) -or (Get-Item $taskRuntimePath).LastWriteTimeUtc -lt $taskStarted){throw 'Missing fresh server observer evidence'}
$taskRuntime=Get-Content $taskRuntimePath -Raw|ConvertFrom-Json
if($taskRuntime.result -ne 'FINISHED'){throw 'Server observer did not finish'}
$taskRaw=Get-Content $taskServerLog -Raw
if($taskRaw -match 'Runtime stopped|receipt rejected|VEGETATION_AUDIT_ERROR'){throw 'Server contract/observer failure'}
if($AuthoredWeather -and $taskRaw -match 'Accessed None|NULL AttachComponent'){throw 'Legacy visual weather still active in the authored map'}
$taskResults+=@{Name='Server';ExitCode=$taskServer.ExitCode;Samples=$taskRuntime.samples.Count}
$taskResults|ConvertTo-Json -Depth 10|Set-Content (Join-Path $taskOut 'NetworkProcesses.json') -Encoding utf8
$taskPython=Join-Path $EngineRoot 'Engine/Binaries/ThirdParty/Python3/Win64/python.exe'
& $taskPython (Join-Path $PSScriptRoot 'validate_vegetation_relevance.py') $taskOut
if($LASTEXITCODE -ne 0){throw 'Client near-field delivery/region-transition evidence failed; inspect Relevance.json'}
Write-Output 'VEGETATION_NETWORK_FINISHED'

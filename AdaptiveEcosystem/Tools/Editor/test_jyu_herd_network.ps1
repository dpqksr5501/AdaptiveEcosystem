# One authoritative native simulation, two successive real clients, native timed exits only.
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskOut=Join-Path $taskRoot 'Saved/HerdMigration_20261022'
$taskEngine='C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64'
$taskProject=Join-Path $taskRoot 'AdaptiveEcosystem.uproject'
$taskBusy=Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue
if($taskBusy){throw 'An engine/build process is already running; no process was stopped.'}
function Start-HerdProcess([string]$Exe,[string[]]$Arguments){
    $quoted=@($Arguments|ForEach-Object {'"'+$_+'"'})
    Start-Process $Exe -ArgumentList ($quoted -join ' ') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru
}
$taskStarted=[DateTime]::UtcNow
$taskLog=Join-Path $taskOut 'NetworkServer.log'
$server=Start-HerdProcess "$taskEngine/UnrealEditor-Cmd.exe" @($taskProject,'/Game/JYU/Maps/LV_JYU_HerdMigration',
    '-server','-NullRHI','-unattended','-nop4','-port=7777','-EcoV3DeerPerRegion=48','-EcoV3SocialControl=0',
    '-EcoIntegrationExitAfter=190','-EcoIntegrationObserverCycle','-HerdAuditName=Server','-HerdAuditDuration=165',
    "-ExecCmds=py $taskRoot/Tools/Editor/audit_herd_migration_runtime.py","-AbsLog=$taskLog")
$deadline=[DateTime]::UtcNow.AddSeconds(65)
while($true){
    if($server.HasExited){throw 'Server exited before ready; inspect its first error.'}
    if((Test-Path $taskLog) -and (Get-Item $taskLog).LastWriteTimeUtc -ge $taskStarted -and
        (Get-Content $taskLog -Raw) -match '\[Eco Integration\] NetMode=1 LogicalOwned=[1-9]'){break}
    if([DateTime]::UtcNow -gt $deadline){throw 'Server readiness timeout; leave its normal exit timer running.'}
    Start-Sleep -Milliseconds 500
}
$results=@()
foreach($entry in @(@{Name='ClientA';At=35},@{Name='ClientB';At=110})){
    while(([DateTime]::UtcNow-$taskStarted).TotalSeconds -lt $entry.At){
        if($server.HasExited){throw 'Server exited before scheduled join'}
        Start-Sleep -Seconds 1
    }
    $clientStart=[DateTime]::UtcNow
    $client=Start-HerdProcess "$taskEngine/UnrealEditor.exe" @($taskProject,'127.0.0.1:7777','-game','-d3d11','-unattended','-nop4','-windowed',
        '-ResX=960','-ResY=540','-NoSound','-EcoIntegrationExitAfter=25',"-HerdClientName=$($entry.Name)",
        "-ExecCmds=py $taskRoot/Tools/Editor/audit_herd_migration_client.py","-AbsLog=$(Join-Path $taskOut ($entry.Name+'.log'))")
    $clientDeadline=[DateTime]::UtcNow.AddSeconds(90)
    while(-not $client.WaitForExit(5000)){if([DateTime]::UtcNow -gt $clientDeadline){throw 'Client deadline exceeded; do not kill engine processes.'}}
    if($client.ExitCode -ne 0){throw "Client failed with $($client.ExitCode)"}
    $report=Join-Path $taskOut ($entry.Name+'_Client.json')
    if(-not(Test-Path $report) -or (Get-Item $report).LastWriteTimeUtc -lt $clientStart){throw 'Missing new client observation'}
    $observed=Get-Content $report -Raw|ConvertFrom-Json
    if(-not $observed.passed){throw 'Client authority/representation/refuge validation failed; leave server timed exit running.'}
    $results+=@{Name=$entry.Name;ExitCode=$client.ExitCode;AuthorityAgents=$observed.authority_agents;Visuals=$observed.visuals.Count;Refuges=$observed.ready}
    Write-Output "$($entry.Name) normal exit; visuals=$($observed.visuals.Count), authority=$($observed.authority_agents)"
}
$serverDeadline=$taskStarted.AddSeconds(260)
while(-not $server.WaitForExit(5000)){if([DateTime]::UtcNow -gt $serverDeadline){throw 'Server deadline exceeded; do not kill it.'}}
if($server.ExitCode -ne 0){throw "Server failed with $($server.ExitCode)"}
$runtime=Get-Content (Join-Path $taskOut 'Server_Runtime.json') -Raw|ConvertFrom-Json
if($runtime.summary.result -ne 'FINISHED' -or $runtime.summary.region_transfers.Count -eq 0){throw 'No completed migration observations on server'}
$raw=Get-Content $taskLog -Raw
if($raw -match 'Runtime stopped|receipt rejected'){throw 'Server resource/population contract failed'}
$results+=@{Name='Server';ExitCode=$server.ExitCode;RegionTransfers=$runtime.summary.region_transfers.Count}
$results|ConvertTo-Json -Depth 5|Set-Content (Join-Path $taskOut 'NetworkProcesses.json') -Encoding utf8
Write-Output 'HERD_NETWORK_FINISHED'

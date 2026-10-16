# Dedicated refuge simulation with two successive real client joins. Native timed exits only.
$ErrorActionPreference='Stop'
$ecoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$ecoOut=Join-Path $ecoRoot 'Saved/RefugeSafety_20261016'
$ecoBusy=@(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue)
if($ecoBusy.Count){throw ($ecoBusy|Out-String)}
function Start-RefugeEngine([string]$Exe,[string[]]$Arguments){
 $ecoQuoted=@($Arguments|ForEach-Object {'"'+$_+'"'})
 Start-Process $Exe -ArgumentList ($ecoQuoted -join ' ') -WorkingDirectory $ecoRoot -WindowStyle Hidden -PassThru
}
$ecoEngine='C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64'
$ecoProject=Join-Path $ecoRoot 'AdaptiveEcosystem.uproject'
$ecoServerLog=Join-Path $ecoOut 'Server.log'
$ecoStartUtc=[DateTime]::UtcNow
$ecoServer=Start-RefugeEngine "$ecoEngine/UnrealEditor-Cmd.exe" @($ecoProject,'/Game/JYU/Maps/LV_JYU_RefugeSafety','-server','-NullRHI','-unattended','-nop4','-port=7777','-EcoIntegratedV3','-EcoIntegrationExitAfter=110','-ExecCmds=eco.Shelter.Log 1',"-AbsLog=$ecoServerLog")
$ecoDeadline=[DateTime]::UtcNow.AddSeconds(65)
while($true){
 if($ecoServer.HasExited){throw 'Server exited before ready; inspect the first error.'}
 if((Test-Path $ecoServerLog) -and (Get-Item $ecoServerLog).LastWriteTimeUtc -ge $ecoStartUtc -and (Get-Content $ecoServerLog -Raw) -match '\[Eco Integration\] NetMode=1 LogicalOwned=[1-9]'){break}
 if([DateTime]::UtcNow -gt $ecoDeadline){throw 'Readiness timeout. Leave the native timed exit running.'}
 Start-Sleep -Milliseconds 500
}
$ecoResults=@()
foreach($ecoName in @('ClientA','ClientB')){
 $ecoClientStart=[DateTime]::UtcNow
 $ecoClient=Start-RefugeEngine "$ecoEngine/UnrealEditor.exe" @($ecoProject,'127.0.0.1:7777','-game','-d3d11','-unattended','-nop4','-windowed','-ResX=960','-ResY=540','-EcoIntegratedV3','-EcoIntegrationExitAfter=12','-NoSound',"-RefugeClientName=$ecoName","-ExecCmds=py $ecoRoot/Tools/Editor/audit_jyu_refuge_client.py","-AbsLog=$(Join-Path $ecoOut ($ecoName+'.log'))")
 if(-not $ecoClient.WaitForExit(90000)){throw 'Client timeout. Do not kill the engine.'}
 if($ecoClient.ExitCode -ne 0){throw "$ecoName exited with $($ecoClient.ExitCode)"}
 $ecoClientReport=Join-Path $ecoOut ($ecoName+'_Refuges.json')
 if(-not (Test-Path $ecoClientReport) -or (Get-Item $ecoClientReport).LastWriteTimeUtc -lt $ecoClientStart){throw "$ecoName did not produce a new observation report. Leave the native server timed exit running."}
 $ecoObserved=Get-Content $ecoClientReport -Raw|ConvertFrom-Json
 if(-not $ecoObserved.passed){throw "$ecoName refuge replication failed. Leave the native server timed exit running."}
 $ecoResults+=@{Name=$ecoName;ExitCode=$ecoClient.ExitCode;Refuges=$ecoObserved.count;Ready=$ecoObserved.ready;Visible=$ecoObserved.visible;Passed=$ecoObserved.passed}
 Write-Output "$ecoName normal exit $($ecoClient.ExitCode)"
}
if(-not $ecoServer.WaitForExit(150000)){throw 'Server timeout. Do not kill the engine.'}
if($ecoServer.ExitCode -ne 0){throw "Server exited with $($ecoServer.ExitCode)"}
$ecoResults+=@{Name='Server';ExitCode=$ecoServer.ExitCode}
$ecoResults|ConvertTo-Json|Set-Content (Join-Path $ecoOut 'NetworkProcesses.json') -Encoding utf8
Write-Output 'REFUGE_NETWORK_FINISHED'

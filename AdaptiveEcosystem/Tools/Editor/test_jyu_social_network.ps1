# Run from the repository root. Each engine process exits using its own integration timer.
$ErrorActionPreference='Stop'
$ecoProjectRoot=(Resolve-Path 'AdaptiveEcosystem').Path
$ecoProject=Join-Path $ecoProjectRoot 'AdaptiveEcosystem.uproject'
$ecoOut=Join-Path $ecoProjectRoot 'Saved/SocialV3_20261016'
$ecoActive=@(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue)
if($ecoActive.Count){throw ($ecoActive|Out-String)}
function Start-Eco([string]$Exe,[string[]]$Arguments){
 $ecoQuoted=@($Arguments|ForEach-Object {'"'+$_+'"'})
 Start-Process $Exe -ArgumentList ($ecoQuoted -join ' ') -WorkingDirectory $ecoProjectRoot -WindowStyle Hidden -PassThru
}
$ecoEngine='C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64'
$ecoServerLog=Join-Path $ecoOut 'Server.log'
$ecoStartUtc=[DateTime]::UtcNow
$ecoServer=Start-Eco "$ecoEngine/UnrealEditor-Cmd.exe" @($ecoProject,'/Game/JYU/Maps/LV_JYU_V3Integration','-server','-NullRHI','-unattended','-nop4','-port=7777','-EcoIntegratedV3','-EcoIntegrationExitAfter=110','-ExecCmds=eco.Senses.NoiseLog 1,eco.Shelter.Log 1,eco.Social.ActionAudit 1',"-AbsLog=$ecoServerLog")
$ecoDeadline=[DateTime]::UtcNow.AddSeconds(65)
while($true){
 if($ecoServer.HasExited){throw 'Server exited before ready; inspect first error.'}
 if((Test-Path $ecoServerLog) -and (Get-Item $ecoServerLog).LastWriteTimeUtc -ge $ecoStartUtc -and (Get-Content $ecoServerLog -Raw) -match '\[Eco Integration\] NetMode=1 LogicalOwned=[1-9]'){break}
 if([DateTime]::UtcNow -gt $ecoDeadline){throw 'Server readiness timeout. Leave native timed exit running.'}
 Start-Sleep -Milliseconds 500
}
$ecoResults=@()
foreach($ecoName in @('ClientA','ClientB')){
 if($ecoServer.HasExited){throw 'Server ended before next client'}
 $ecoClient=Start-Eco "$ecoEngine/UnrealEditor.exe" @($ecoProject,'127.0.0.1:7777','-game','-d3d11','-unattended','-nop4','-windowed','-ResX=960','-ResY=540','-EcoIntegratedV3','-EcoIntegrationExitAfter=12','-NoSound',"-AbsLog=$(Join-Path $ecoOut ($ecoName+'.log'))")
 if(-not $ecoClient.WaitForExit(90000)){throw 'Client timed out. Do not kill engine.'}
 $ecoResults+=@{Name=$ecoName;ExitCode=$ecoClient.ExitCode}
 Write-Output "$ecoName normal exit $($ecoClient.ExitCode)"
}
if(-not $ecoServer.WaitForExit(150000)){throw 'Server timed out. Do not kill engine.'}
$ecoResults+=@{Name='Server';ExitCode=$ecoServer.ExitCode}
$ecoResults|ConvertTo-Json|Set-Content (Join-Path $ecoOut 'NetworkProcessResults.json') -Encoding utf8
Write-Output 'NETWORK_AUDIT_FINISHED'

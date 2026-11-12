param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$huntingRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$huntingOut=Join-Path $huntingRoot 'Saved/PlayerHunting_20261105/Network'
New-Item -ItemType Directory -Force $huntingOut | Out-Null
if(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue){throw 'Engine/build busy; nothing stopped'}
function Start-HuntingPeer([string]$Executable,[string]$Destination,[string]$Name,[string[]]$Options){
    $huntingArgs=@((Join-Path $huntingRoot 'AdaptiveEcosystem.uproject'),$Destination,'-NullRHI','-nosteam','-unattended','-nop4','-nosplash','-EcoV3Seed=23',
        '-EcoIntegrationExitAfter=140',"-ExecCmds=py $huntingRoot/Tools/Editor/audit_player_hunting_network.py","-abslog=$huntingOut/$Name.log")+$Options
    $huntingQuoted=$huntingArgs|ForEach-Object{'"'+$_+'"'}
    Start-Process (Join-Path $EngineRoot "Engine/Binaries/Win64/$Executable") -ArgumentList ($huntingQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $huntingRoot
}
$huntingStarted=Get-Date
$huntingServer=Start-HuntingPeer 'UnrealEditor-Cmd.exe' '/Game/JWJ/1102_Integration_JWJ' 'Server' @('-server','-port=7787','-HuntingNetworkServer')
$huntingDeadline=(Get-Date).AddSeconds(75)
while($true){
    if($huntingServer.HasExited){throw 'Dedicated server exited before readiness'}
    $serverLog=Get-Item -LiteralPath "$huntingOut/Server.log" -ErrorAction SilentlyContinue
    if($serverLog -and $serverLog.LastWriteTime -ge $huntingStarted -and
        (Select-String -LiteralPath $serverLog.FullName -Pattern 'Authority ready:' -Quiet)){break}
    if((Get-Date) -gt $huntingDeadline){throw 'Server readiness timeout; normal exit timer left running'}
    Start-Sleep -Seconds 1
}
$huntingA=Start-HuntingPeer 'UnrealEditor.exe' '127.0.0.1:7787?EcoProtocol=1' 'ClientA' @('-game','-HuntingNetworkClient=ClientA')
Start-Sleep -Seconds 15
$huntingB=Start-HuntingPeer 'UnrealEditor.exe' '127.0.0.1:7787?EcoProtocol=1' 'ClientB' @('-game','-HuntingNetworkClient=ClientB')
$huntingFailures=[System.Collections.Generic.List[string]]::new()
foreach($huntingPeer in @(@{Name='ClientA';Process=$huntingA},@{Name='ClientB';Process=$huntingB},@{Name='Server';Process=$huntingServer})){
    while(-not $huntingPeer.Process.WaitForExit(5000)){}
    try{
        if($huntingPeer.Process.ExitCode -ne 0){throw "$($huntingPeer.Name) exited with $($huntingPeer.Process.ExitCode)"}
        $huntingReport=Join-Path $huntingOut ($huntingPeer.Name+'.json')
        if(-not(Test-Path $huntingReport) -or (Get-Item $huntingReport).LastWriteTime -lt $huntingStarted){throw "Fresh report missing: $($huntingPeer.Name)"}
        $huntingResult=Get-Content -Raw $huntingReport | ConvertFrom-Json
        if($huntingResult.result -ne 'PASS'){throw "$($huntingPeer.Name) failed: $($huntingResult.error)"}
        Write-Output "HUNTING_NETWORK_PASS $($huntingPeer.Name)"
    }catch{
        $huntingFailures.Add($_.Exception.Message)
    }
}
if($huntingFailures.Count){throw ($huntingFailures -join [Environment]::NewLine)}

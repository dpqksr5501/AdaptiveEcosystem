param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8', [switch]$RenderedClients)
$ErrorActionPreference='Stop'
$healthRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$healthOut=Join-Path $healthRoot 'Saved/HealthBarValidation/Network'
New-Item -ItemType Directory -Force $healthOut | Out-Null
if(Get-Process UnrealEditor,UnrealEditor-Cmd,UnrealBuildTool,dotnet,MSBuild,ShaderCompileWorker,LiveCodingConsole -ErrorAction SilentlyContinue){throw 'Engine/build busy; nothing stopped'}
$healthRunStarted=Get-Date
$healthRunId=[guid]::NewGuid().ToString('N')
if(Test-Path "$healthOut/Session.json"){Remove-Item -LiteralPath "$healthOut/Session.json"}
function Start-HealthPeer([string]$Exe,[string]$Destination,[string]$Name,[string[]]$Options){
    $healthArgs=@("$healthRoot/AdaptiveEcosystem.uproject",$Destination,'-nosteam','-unattended','-nop4','-nosplash','-EcoV3Seed=23',
        '-EcoIntegrationExitAfter=145',"-HealthBarRun=$healthRunId", "-ExecCmds=py $healthRoot/Tools/Editor/verify_health_bar_network.py","-abslog=$healthOut/$Name.log")+$Options
    $healthQuoted=$healthArgs|ForEach-Object{'"'+$_+'"'}
    Start-Process (Join-Path $EngineRoot "Engine/Binaries/Win64/$Exe") -ArgumentList ($healthQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $healthRoot
}
$healthServer=Start-HealthPeer 'UnrealEditor-Cmd.exe' '/Game/JWJ/1102_Integration_JWJ?game=/Game/JWJ/Gameplay/BP_EcoGameMode_Common.BP_EcoGameMode_Common_C' 'Server' @('-server','-NullRHI','-port=7795','-HealthBarServer')
$healthDeadline=(Get-Date).AddSeconds(80)
while($true){
    if($healthServer.HasExited){throw 'Server exited before readiness'}
    if((Test-Path "$healthOut/Server.log") -and (Get-Content -Raw "$healthOut/Server.log") -match 'Authority ready:'){break}
    if((Get-Date) -gt $healthDeadline){throw 'Readiness timeout; normal exit timer remains running'}
    Start-Sleep -Seconds 1
}
$healthClientOptions=if($RenderedClients){@('-d3d11','-windowed','-ResX=1280','-ResY=720','-HealthBarRender')}else{@('-NullRHI')}
$healthA=Start-HealthPeer 'UnrealEditor.exe' '127.0.0.1:7795?EcoProtocol=1?Name=HealthA' 'A' (@('-game','-HealthBarClient=A')+$healthClientOptions)
$healthB=Start-HealthPeer 'UnrealEditor.exe' '127.0.0.1:7795?EcoProtocol=1?Name=HealthB' 'B' (@('-game','-HealthBarClient=B')+$healthClientOptions)
foreach($healthPeer in @(@{Name='A';P=$healthA},@{Name='B';P=$healthB},@{Name='Server';P=$healthServer})){
    while(-not $healthPeer.P.WaitForExit(1000)){}
    if($healthPeer.P.ExitCode -ne 0){throw "Peer failed: $($healthPeer.Name)"}
    $healthReport=Join-Path $healthOut ($healthPeer.Name+'.json')
    if(-not(Test-Path $healthReport) -or (Get-Item $healthReport).LastWriteTime -lt $healthRunStarted){throw 'Fresh report missing'}
    $healthResult=Get-Content -Raw $healthReport|ConvertFrom-Json
    if($healthResult.run_id -ne $healthRunId -or $healthResult.result -ne 'PASS'){throw "$($healthPeer.Name): $($healthResult.error)"}
    Write-Output "HEALTH_BAR_NETWORK_PASS $($healthPeer.Name)"
}

param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$viewRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$viewOut=Join-Path $viewRoot 'Saved/ClientVisualDistanceValidation'
New-Item -ItemType Directory -Force $viewOut | Out-Null
if(Get-Process UnrealEditor,UnrealEditor-Cmd,UnrealBuildTool,dotnet,MSBuild,ShaderCompileWorker,LiveCodingConsole -ErrorAction SilentlyContinue){throw 'Engine/build busy; nothing stopped'}
$viewStarted=Get-Date
foreach($viewName in @('Session','Server','Client')){
    $viewOld=Join-Path $viewOut ($viewName+'.json')
    if(Test-Path $viewOld){Remove-Item -LiteralPath $viewOld}
}
function Start-ViewPeer([string]$Exe,[string]$Destination,[string]$Name,[string[]]$Options){
    $viewArgs=@("$viewRoot/AdaptiveEcosystem.uproject",$Destination,'-nosteam','-unattended','-nop4','-nosplash','-NullRHI','-EcoV3Seed=23',
        '-EcoV3Wolves=0','-EcoIntegrationExitAfter=160',"-ExecCmds=py $viewRoot/Tools/Editor/verify_client_visual_distance.py","-abslog=$viewOut/$Name.log")+$Options
    $viewQuoted=$viewArgs|ForEach-Object{'"'+$_+'"'}
    Start-Process (Join-Path $EngineRoot "Engine/Binaries/Win64/$Exe") -ArgumentList ($viewQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $viewRoot
}
$viewServer=Start-ViewPeer 'UnrealEditor-Cmd.exe' '/Game/JYU/Maps/LV_JYU_HerdMigration' 'Server' @('-server','-port=7796','-VisualDistanceServer')
$viewDeadline=(Get-Date).AddSeconds(80)
while($true){
    if($viewServer.HasExited){throw 'Server exited before readiness'}
    if((Test-Path "$viewOut/Server.log") -and (Get-Content -Raw "$viewOut/Server.log") -match 'Authority ready:'){break}
    if((Get-Date) -gt $viewDeadline){throw 'Readiness timeout; normal exit timer remains running'}
    Start-Sleep -Seconds 1
}
$viewClient=Start-ViewPeer 'UnrealEditor.exe' '127.0.0.1:7796?EcoProtocol=1?Name=ViewRange' 'Client' @('-game')
foreach($viewPeer in @(@{Name='Client';P=$viewClient},@{Name='Server';P=$viewServer})){
    while(-not $viewPeer.P.WaitForExit(1000)){}
    if($viewPeer.P.ExitCode -ne 0){throw "Peer failed: $($viewPeer.Name)"}
    $viewReport=Join-Path $viewOut ($viewPeer.Name+'.json')
    if(-not(Test-Path $viewReport) -or (Get-Item $viewReport).LastWriteTime -lt $viewStarted){throw 'Fresh report missing'}
    $viewResult=Get-Content -Raw $viewReport|ConvertFrom-Json
    if($viewResult.result -ne 'PASS'){throw "$($viewPeer.Name): $($viewResult.error)"}
    Write-Output "CLIENT_VISUAL_DISTANCE_PASS $($viewPeer.Name)"
}

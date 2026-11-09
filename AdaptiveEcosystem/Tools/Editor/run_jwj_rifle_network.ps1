param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$rifleRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$rifleOut=Join-Path $rifleRoot 'Saved/RifleValidation/Network'
New-Item -ItemType Directory -Force $rifleOut | Out-Null
if(Get-Process UnrealEditor,UnrealEditor-Cmd,UnrealBuildTool,dotnet,MSBuild,ShaderCompileWorker,LiveCodingConsole -ErrorAction SilentlyContinue){throw 'Engine/build busy; nothing stopped'}
# Remove only a previous fixture session marker, never gameplay files.
if(Test-Path "$rifleOut/Session.json"){Remove-Item -LiteralPath "$rifleOut/Session.json"}
function Start-RiflePeer([string]$Exe,[string]$Destination,[string]$Name,[string[]]$Options){
 $rifleArgs=@("$rifleRoot/AdaptiveEcosystem.uproject",$Destination,'-NullRHI','-nosteam','-unattended','-nop4','-nosplash','-EcoV3Seed=23','-EcoIntegrationExitAfter=150',"-ExecCmds=py $rifleRoot/Tools/Editor/verify_jwj_rifle_network.py","-abslog=$rifleOut/$Name.log")+$Options
 $rifleQuoted=$rifleArgs|ForEach-Object{'"'+$_+'"'}
 Start-Process (Join-Path $EngineRoot "Engine/Binaries/Win64/$Exe") -ArgumentList ($rifleQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $rifleRoot
}
$rifleStart=Get-Date
$rifleServer=Start-RiflePeer 'UnrealEditor-Cmd.exe' '/Game/JWJ/1102_Integration_JWJ?game=/Game/JWJ/Gameplay/BP_EcoGameMode_Common.BP_EcoGameMode_Common_C' 'Server' @('-server','-port=7793','-RifleNetworkServer')
$rifleDeadline=(Get-Date).AddSeconds(80)
while($true){
 if($rifleServer.HasExited){throw 'Server exited before readiness'}
 if((Test-Path "$rifleOut/Server.log") -and (Get-Content -Raw "$rifleOut/Server.log") -match 'Authority ready:'){break}
 if((Get-Date) -gt $rifleDeadline){throw 'Readiness timeout; native exit timer left running'}
 Start-Sleep -Seconds 1
}
$rifleA=Start-RiflePeer 'UnrealEditor.exe' '127.0.0.1:7793?EcoProtocol=1?Name=RifleA' 'A' @('-game','-RifleNetworkClient=A')
$rifleB=Start-RiflePeer 'UnrealEditor.exe' '127.0.0.1:7793?EcoProtocol=1?Name=RifleB' 'B' @('-game','-RifleNetworkClient=B')
foreach($riflePeer in @(@{Name='A';P=$rifleA},@{Name='B';P=$rifleB},@{Name='Server';P=$rifleServer})){
 while(-not $riflePeer.P.WaitForExit(1000)){}
 if($riflePeer.P.ExitCode -ne 0){throw "Peer failed: $($riflePeer.Name)"}
 $rifleReport=Join-Path $rifleOut ($riflePeer.Name+'.json')
 if(-not(Test-Path $rifleReport) -or (Get-Item $rifleReport).LastWriteTime -lt $rifleStart){throw 'Fresh report missing'}
 $rifleResult=Get-Content $rifleReport -Raw|ConvertFrom-Json
 if($rifleResult.result -ne 'PASS'){throw "$($riflePeer.Name): $($rifleResult.error)"}
 Write-Output "RIFLE_NETWORK_PASS $($riflePeer.Name)"
}

param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8', [ValidatePattern('^[A-Za-z0-9_]+$')][string]$EvidenceTag='Network',
    [switch]$SavedIsland, [switch]$SharedTarget, [switch]$CheckpointRoundTrip, [switch]$RuleAmbush,
    [switch]$FaunaBreedingOpportunity)
$ErrorActionPreference='Stop'
if($SharedTarget -and !$SavedIsland){throw 'SharedTarget requires the saved island fixture'}
if($CheckpointRoundTrip -and !$SharedTarget){throw 'CheckpointRoundTrip requires SharedTarget'}
if($FaunaBreedingOpportunity -and !$CheckpointRoundTrip){throw 'FaunaBreedingOpportunity requires the island checkpoint round trip'}
if($RuleAmbush -and (!$SavedIsland -or $SharedTarget)){throw 'RuleAmbush requires SavedIsland without SharedTarget'}
$rifleRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$rifleOut=Join-Path $rifleRoot "Saved/RifleValidation/$EvidenceTag"
$rifleCheckpointSlot="NetworkHunt_$EvidenceTag"
$rifleCheckpoint=Join-Path $rifleRoot "Saved/Ecosystem/$rifleCheckpointSlot.eco"
if($CheckpointRoundTrip -and ($rifleCheckpointSlot.Length -gt 48 -or (Test-Path -LiteralPath $rifleCheckpoint))){
 throw 'Use a fresh checkpoint tag with at most 36 characters'
}
if($SavedIsland -and (Test-Path -LiteralPath $rifleOut)){throw 'Use a fresh evidence tag for the saved island fixture'}
New-Item -ItemType Directory -Force $rifleOut | Out-Null
if(Get-Process UnrealEditor,UnrealEditor-Cmd,UnrealBuildTool,dotnet,MSBuild,ShaderCompileWorker,LiveCodingConsole -ErrorAction SilentlyContinue){throw 'Engine/build busy; nothing stopped'}
# Remove only the previous fixture coordination markers.
foreach($marker in 'Session.json','A_Pawn.json','B_Pawn.json'){
 if(Test-Path "$rifleOut/$marker"){Remove-Item -LiteralPath "$rifleOut/$marker"}
}
function Start-RiflePeer([string]$Exe,[string]$Destination,[string]$Name,[string[]]$Options){
 $rifleArgs=@("$rifleRoot/AdaptiveEcosystem.uproject",$Destination,'-NullRHI','-nosteam','-unattended','-nop4','-nosplash','-EcoV3Seed=23','-EcoIntegrationExitAfter=150',"-RifleEvidenceTag=$EvidenceTag",'-ini:Engine:[ConsoleVariables]:eco.Senses.NoiseLog=1',"-ExecCmds=py $rifleRoot/Tools/Editor/verify_jwj_rifle_network.py","-abslog=$rifleOut/$Name.log")+$Options
 if($SavedIsland){
  $rifleArgs=@($rifleArgs | Where-Object { $_ -ne '-EcoV3Seed=23' })+@('-EcoV3Seed=20000','-RifleSavedIsland','-EcoV3AutoAdapt=0','-EcoTraitAudit')
 }
 if($SharedTarget){$rifleArgs+='-RifleSharedTarget'}
 if($RuleAmbush){
  $rifleArgs+='-RifleRuleAmbush'
  if($Options -contains '-server'){$rifleArgs+='-EcoRuleFaunaPlayerAmbush'}
 }
 if($CheckpointRoundTrip){$rifleArgs+="-RifleCheckpointSlot=$rifleCheckpointSlot"}
 if($FaunaBreedingOpportunity -and $Options -contains '-server'){$rifleArgs+='-EcoFaunaBreedingOpportunity'}
 $rifleQuoted=$rifleArgs|ForEach-Object{'"'+$_+'"'}
 Start-Process (Join-Path $EngineRoot "Engine/Binaries/Win64/$Exe") -ArgumentList ($rifleQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $rifleRoot
}
$rifleStart=Get-Date
$rifleMap=if($SavedIsland){'/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed'}else{'/Game/JWJ/1102_Integration_JWJ?game=/Game/JWJ/Gameplay/BP_EcoGameMode_Common.BP_EcoGameMode_Common_C'}
function Wait-RifleAuthority($Process,[string]$LogName,[string]$Marker){
 $rifleDeadline=(Get-Date).AddSeconds(80)
 while($true){
  if($Process.HasExited){throw "$LogName exited before readiness"}
  $rifleServerLog=Get-Item -LiteralPath "$rifleOut/$LogName.log" -ErrorAction SilentlyContinue
  if($rifleServerLog -and $rifleServerLog.LastWriteTime -ge $rifleStart -and
     (Select-String -LiteralPath $rifleServerLog.FullName -SimpleMatch $Marker -Quiet)){return}
  if((Get-Date) -gt $rifleDeadline){throw "$LogName readiness timeout; native exit timer left running"}
  Start-Sleep -Seconds 1
 }
}
$rifleServer=Start-RiflePeer 'UnrealEditor-Cmd.exe' $rifleMap 'Server' @('-server','-port=7793','-RifleNetworkServer')
Wait-RifleAuthority $rifleServer 'Server' 'Authority ready:'
$rifleA=Start-RiflePeer 'UnrealEditor.exe' '127.0.0.1:7793?EcoProtocol=5?Name=RifleA' 'A' @('-game','-RifleNetworkClient=A')
$rifleB=Start-RiflePeer 'UnrealEditor.exe' '127.0.0.1:7793?EcoProtocol=5?Name=RifleB' 'B' @('-game','-RifleNetworkClient=B')
$rifleFailures=[System.Collections.Generic.List[string]]::new()
function Confirm-RiflePeer($riflePeer){
 while(-not $riflePeer.P.WaitForExit(1000)){}
 try{
  if($riflePeer.P.ExitCode -ne 0){throw "Peer failed: $($riflePeer.Name)"}
  $rifleReport=Join-Path $rifleOut ($riflePeer.Name+'.json')
  if(-not(Test-Path $rifleReport) -or (Get-Item $rifleReport).LastWriteTime -lt $rifleStart){throw "Fresh report missing: $($riflePeer.Name)"}
  $rifleResult=Get-Content $rifleReport -Raw|ConvertFrom-Json
  if($rifleResult.result -ne 'PASS'){throw "$($riflePeer.Name): $($rifleResult.error)"}
  Write-Output "RIFLE_NETWORK_PASS $($riflePeer.Name)"
 }catch{$rifleFailures.Add($_.Exception.Message)}
}
Confirm-RiflePeer @{Name='A';P=$rifleA}
if(!$SharedTarget){Confirm-RiflePeer @{Name='B';P=$rifleB}}
if($SavedIsland -and !$RuleAmbush -and !$rifleFailures.Count -and !$rifleServer.HasExited){
 $rifleLate=Start-RiflePeer 'UnrealEditor.exe' '127.0.0.1:7793?EcoProtocol=5?Name=RifleA' 'Late' @('-game','-RifleNetworkClient=Late')
 Confirm-RiflePeer @{Name='Late';P=$rifleLate}
}
if($SharedTarget){Confirm-RiflePeer @{Name='B';P=$rifleB}}
Confirm-RiflePeer @{Name='Server';P=$rifleServer}
$serverNoise=@(Select-String -LiteralPath "$rifleOut/Server.log" -SimpleMatch 'Tag=Player.Shot').Count
$clientNoise=@(Select-String -LiteralPath "$rifleOut/A.log","$rifleOut/B.log" -SimpleMatch 'Tag=Player.Shot').Count
Write-Output "RIFLE_ECOLOGY_NOISE server=$serverNoise clients=$clientNoise"
if($clientNoise -ne 0 -or (!$RuleAmbush -and $serverNoise -eq 0)){$rifleFailures.Add('Shot noise authority check failed')}
if($RuleAmbush -and !$rifleFailures.Count){
 $authority=(Get-Content -LiteralPath "$rifleOut/Server.json" -Raw | ConvertFrom-Json).samples[-1]
 $hits=@(Select-String -LiteralPath "$rifleOut/Server.log" -Pattern '\[EcoCombat\]\[FaunaPlayerHit\] Id=(\d+).* Paid=([\d.]+)')
 $clientHits=@(Select-String -LiteralPath "$rifleOut/A.log","$rifleOut/B.log" -SimpleMatch '[EcoCombat][FaunaPlayerHit]')
 if($hits.Count -ne 1 -or $clientHits.Count -ne 0 -or $serverNoise -ne 0 -or
    [long]$hits[0].Matches[0].Groups[1].Value -ne $authority.leopard -or [double]$hits[0].Matches[0].Groups[2].Value -ne 20){
  $rifleFailures.Add('Ambush needs one server contact from the witnessed leopard and no shots')
 }
}
if($SharedTarget -and !$rifleFailures.Count){
 $serverResult=Get-Content -LiteralPath "$rifleOut/Server.json" -Raw | ConvertFrom-Json
 $aResult=Get-Content -LiteralPath "$rifleOut/A.json" -Raw | ConvertFrom-Json
 $bResult=Get-Content -LiteralPath "$rifleOut/B.json" -Raw | ConvertFrom-Json
 $targetId=[long]$serverResult.samples[-1].target
 $deaths=@(Select-String -LiteralPath "$rifleOut/Server.log" -Pattern "\[EcoCombat\]\[DeathCommitted\] Id=$targetId(?: |$)")
 $issued=@(Select-String -LiteralPath "$rifleOut/Server.log" -Pattern "\[Eco Fauna\]\[Carcass\] Id=$targetId(?: |$)")
 $closed=@(Select-String -LiteralPath "$rifleOut/Server.log" -Pattern "\[Eco Fauna\]\[CarcassClosed\] Id=$targetId(?: |$)")
 $commits=@(Select-String -LiteralPath "$rifleOut/Server.log" -Pattern '\[EcoCombat\]\[Outcome\].* Target=(\d+) Result=1 Applied=(\d+\.\d+)')
 $serverTotal=0.0
 foreach($commit in $commits){
  if([long]$commit.Matches[0].Groups[1].Value -ne $targetId){throw 'Shared trial committed damage to another target'}
  $serverTotal+=[double]$commit.Matches[0].Groups[2].Value
 }
 $clientTotal=$aResult.samples[-1].target_damage+$bResult.samples[-1].target_damage
 if(!$targetId -or !$serverResult.samples[-1].shooter_departed -or !$serverResult.samples[-1].observer_overlapped_late -or
    !$bResult.samples[-1].observed_late_survivor -or $clientTotal -ne 100 -or $serverTotal -ne 100 -or $commits.Count -ne 4 -or
    $deaths.Count -ne 1 -or $issued.Count -ne 1 -or $closed.Count -ne 1){
  $rifleFailures.Add('Shared target damage, death or carcass transaction did not balance')
 }else{
  $paid=@(Select-String -LiteralPath "$rifleOut/Server.log" -Pattern "\[Eco Fauna\]\[Scavenge\].* Carcass=$targetId Amount=(\d+\.\d+)")
  $paidEnergy=0.0
  foreach($payment in $paid){$paidEnergy+=[double]$payment.Matches[0].Groups[1].Value}
  if($issued[0].Line -notmatch ' Remaining=(\d+\.\d+)' -or !$Matches[1]){throw 'Missing shared carcass reserve'}
  $stock=[double]$Matches[1]
  if($closed[0].Line -notmatch ' Unused=(\d+\.\d+)' -or !$Matches[1]){throw 'Missing final carcass stock'}
  $unused=[double]$Matches[1]
  if([Math]::Abs($stock-$paidEnergy-$unused) -gt .02){throw 'Shared carcass payout exceeded its reserve'}
  [pscustomobject]@{target=$targetId;damage=@{A=$aResult.samples[-1].target_damage;B=$bResult.samples[-1].target_damage};
     death_count=$deaths.Count;carcass_stock=$stock;carcass_paid=$paidEnergy;carcass_unused=$unused;payments=$paid.Count} |
      ConvertTo-Json | Set-Content -LiteralPath "$rifleOut/SharedLedger.json" -Encoding utf8
 }
}
if($rifleFailures.Count){throw ($rifleFailures -join [Environment]::NewLine)}
if($CheckpointRoundTrip){
 if(!(Test-Path -LiteralPath $rifleCheckpoint) -or (Get-Item -LiteralPath $rifleCheckpoint).LastWriteTime -lt $rifleStart){
  throw 'The hunt did not produce a fresh checkpoint'
 }
 $rifleRestored=Start-RiflePeer 'UnrealEditor-Cmd.exe' $rifleMap 'RestoredServer' @('-server','-port=7794','-RifleNetworkServer','-RifleRestoreCheckpoint')
 Wait-RifleAuthority $rifleRestored 'RestoredServer' '[EcoRifleNetwork] Restored authority ready'
 $rifleRestoredClient=Start-RiflePeer 'UnrealEditor.exe' '127.0.0.1:7794?EcoProtocol=5?Name=RestoredObserver' 'RestoredClient' @('-game','-RifleNetworkClient=RestoredClient','-RifleRestoreCheckpoint')
 Confirm-RiflePeer @{Name='RestoredClient';P=$rifleRestoredClient}
 Confirm-RiflePeer @{Name='RestoredServer';P=$rifleRestored}
 if($rifleFailures.Count){throw ($rifleFailures -join [Environment]::NewLine)}
 $rifleChecker=Join-Path $PSScriptRoot 'check_island_checkpoint_receipts.py'
 $rifleRuntime=Join-Path $rifleRoot 'Binaries/Win64/UnrealEditor-AdaptiveEcosystem.dll'
 $rifleRule=@(if($FaunaBreedingOpportunity){'--fauna-breeding-rule'})
 $rifleValidated=python -B $rifleChecker $rifleCheckpoint $rifleRuntime "$rifleOut/Checkpoint.json" "$rifleOut/RestoredCheckpoint.json" `
    "$rifleOut/Server.log" "$rifleOut/RestoredServer.log" --network-hunt @rifleRule
 if($LASTEXITCODE -ne 0){throw 'Network hunt checkpoint receipts did not match'}
 $rifleValidated | Set-Content -LiteralPath "$rifleOut/RestoredLedger.json" -Encoding utf8
}

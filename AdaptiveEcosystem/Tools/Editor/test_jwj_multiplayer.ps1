# Run from the repository root. All engine processes use their own normal-exit timer.
param([ValidateSet('Smoke','Capacity','Disconnect')][string]$Scenario='Smoke', [int]$Port=7787, [switch]$Packaged)
$ErrorActionPreference='Stop'
$ecoProjectRoot=(Resolve-Path 'AdaptiveEcosystem').Path
$ecoProject=Join-Path $ecoProjectRoot 'AdaptiveEcosystem.uproject'
$ecoEditor=if($Packaged){Join-Path $ecoProjectRoot 'Saved/JWJMultiplayerPackage/Windows/AdaptiveEcosystem/Binaries/Win64/AdaptiveEcosystem.exe'}else{'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe'}
if(-not(Test-Path $ecoEditor)){throw 'Game executable missing. Build the matching package first.'}
$ecoWorkingDirectory=if($Packaged){Join-Path $ecoProjectRoot 'Saved/JWJMultiplayerPackage/Windows'}else{$ecoProjectRoot}
$ecoProjectArguments=@(if(-not $Packaged){$ecoProject})
$ecoRunPrefix=if($Packaged){'Package'+$Scenario}else{$Scenario}
$ecoOutput=Join-Path $ecoProjectRoot ('Saved/Network20261024/'+$ecoRunPrefix+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $ecoOutput -Force | Out-Null
$ecoActive=@(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,AdaptiveEcosystem*,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue)
if($ecoActive.Count){throw ($ecoActive|Out-String)}
$ecoProcesses=[System.Collections.Generic.List[object]]::new()
function Start-Eco([string]$Name,[string]$Address,[int]$Seconds,[string[]]$Extra=@()) {
    $ecoLog=Join-Path $ecoOutput ($Name+'.log')
    $ecoArguments=$ecoProjectArguments+@($Address,'-game','-NullRHI','-nosteam','-unattended','-nop4','-nosplash','-nosound',
        '-EcoSessionNoUI','-EcoSessionAudit',('-port='+$Port),('-EcoIntegrationExitAfter='+$Seconds),
        '-ExecCmds=t.MaxFPS 10,eco.Integration.LogDetails 1',('-AbsLog='+$ecoLog))+$Extra
    $ecoQuoted=@($ecoArguments|ForEach-Object {'"'+$_+'"'})
    $ecoProcess=Start-Process $ecoEditor -ArgumentList ($ecoQuoted -join ' ') -WorkingDirectory $ecoWorkingDirectory -WindowStyle Hidden -PassThru
    $ecoEntry=[pscustomobject]@{Name=$Name;Process=$ecoProcess;Log=$ecoLog}
    $ecoProcesses.Add($ecoEntry)
    return $ecoEntry
}
function Wait-EcoLog($Entry,[string]$Pattern,[int]$Seconds=80) {
    $ecoDeadline=[DateTime]::UtcNow.AddSeconds($Seconds)
    while([DateTime]::UtcNow -lt $ecoDeadline) {
        if(Test-Path $Entry.Log) {
            $ecoText=Get-Content -LiteralPath $Entry.Log -Raw -Encoding UTF8
            if($ecoText -match $Pattern){return}
            if($ecoText -match 'Fatal error:|Assertion failed:'){throw ($Entry.Name+' crashed; '+$Entry.Log)}
        }
        if($Entry.Process.HasExited){throw ($Entry.Name+' exited before expected evidence; '+$Entry.Log)}
        Start-Sleep -Milliseconds 500
    }
    throw ($Entry.Name+' evidence timeout; leave its native timed exit running. '+$Entry.Log)
}
function Wait-EcoExit($Entry,[int]$Seconds=360) {
    if(-not $Entry.Process.WaitForExit($Seconds*1000)){throw ($Entry.Name+' timed out. Do not kill engine. '+$Entry.Log)}
    if($Entry.Process.ExitCode -ne 0){throw ($Entry.Name+' exit '+$Entry.Process.ExitCode+'; '+$Entry.Log)}
}

$ecoHostSeconds=if($Scenario -eq 'Capacity'){300}elseif($Scenario -eq 'Disconnect'){35}else{125}
$ecoHost=Start-Eco 'Host' '/Game/JWJ/Integration_JwJ' $ecoHostSeconds @('-EcoSessionAutoHost','-EcoSessionLAN','-EcoSessionRoom=JWJ_Local_Audit','-EcoIntegrationObserverCycle')
Wait-EcoLog $ecoHost '\[EcoSession\]\[Runtime\].*NetMode=2.*Capacity=11'
Wait-EcoLog $ecoHost '\[Eco Integration\] NetMode=2 LogicalOwned=[1-9]'
Write-Output ('HOST_READY '+$ecoOutput)

if($Scenario -eq 'Smoke') {
    $ecoFirst=Start-Eco 'SearchJoin' '/Game/JWJ/Integration_JwJ' 22 @('-EcoSessionAutoFind','-EcoSessionAutoJoin','-EcoSessionLAN','-EcoSessionLeaveAfter=7','-EcoSessionAutoRejoin')
    Wait-EcoLog $ecoFirst '\[EcoSession\]\[Runtime\].*NetMode=3.*State=6'
    Wait-EcoLog $ecoFirst '\[Eco Integration\] NetMode=3 LogicalOwned=0 Visuals=[1-9].*Step=0'
    Wait-EcoExit $ecoFirst 100
    $ecoCycleLog=Get-Content $ecoFirst.Log -Raw -Encoding UTF8
    if(([regex]::Matches($ecoCycleLog,'\[EcoSession\]\[Runtime\].*NetMode=3.*State=6')).Count -lt 2 -or
        $ecoCycleLog -notmatch '\[EcoSession\] State=7') {throw 'Explicit LeaveSession/rejoin cycle did not complete'}
    Wait-EcoLog $ecoHost '\[EcoSession\]\[Departure\] Players=1'
    $ecoRejoin=Start-Eco 'SearchRejoin' '/Game/JWJ/Integration_JwJ' 18 @('-EcoSessionAutoFind','-EcoSessionAutoJoin','-EcoSessionLAN')
    Wait-EcoLog $ecoRejoin '\[EcoSession\]\[Runtime\].*NetMode=3.*State=6'
    Wait-EcoLog $ecoRejoin '\[Eco Integration\] NetMode=3 LogicalOwned=0 Visuals=[1-9].*Step=0'
    Wait-EcoExit $ecoRejoin 100
}
elseif($Scenario -eq 'Capacity') {
    for($ecoIndex=1;$ecoIndex -le 10;$ecoIndex++) {
        $ecoClient=Start-Eco ('Client'+$ecoIndex.ToString('00')) ('127.0.0.1:'+$Port+'?EcoProtocol=1') 200
        Wait-EcoLog $ecoClient '\[Eco Integration\] NetMode=3 LogicalOwned=0 Visuals=[1-9].*Step=0'
        Write-Output ('CLIENT_READY '+$ecoIndex)
    }
    Wait-EcoLog $ecoHost '\[EcoSession\]\[Admission\] Players=11 Capacity=11 NetMode=2'
    $ecoOverflow=Start-Eco 'Overflow' ('127.0.0.1:'+$Port+'?EcoProtocol=1') 15
    Wait-EcoLog $ecoOverflow 'Server full\.|ServerFull|ECO_SESSION_FULL'
    $ecoWrong=Start-Eco 'WrongProtocol' ('127.0.0.1:'+$Port+'?EcoProtocol=0') 15
    Wait-EcoLog $ecoWrong 'ECO_INCOMPATIBLE_PROTOCOL'
    Write-Output 'CAPACITY_AND_PROTOCOL_REJECTION_OBSERVED'
}
else {
    $ecoClient=Start-Eco 'HostDisconnect' '/Game/JWJ/Integration_JwJ' 45 @('-EcoSessionAutoFind','-EcoSessionAutoJoin','-EcoSessionLAN')
    Wait-EcoLog $ecoClient '\[EcoSession\]\[Runtime\].*NetMode=3.*State=6'
    Wait-EcoExit $ecoHost 90
    Wait-EcoLog $ecoClient '\[EcoSession\] NetworkFailure='
    Wait-EcoLog $ecoClient '\[EcoSession\]\[Runtime\].*NetMode=0.*State=8.*Ready=1'
}
foreach($ecoEntry in $ecoProcesses){Wait-EcoExit $ecoEntry 380}
$ecoUnexpected=@($ecoProcesses|Where-Object {(Get-Content $_.Log -Raw -Encoding UTF8) -match 'Runtime stopped:|Fatal error:|Assertion failed:'})
if($ecoUnexpected.Count){throw ('Unexpected runtime failure: '+(($ecoUnexpected|ForEach-Object {$_.Log}) -join ', '))}
$ecoResults=@($ecoProcesses|ForEach-Object {
    $ecoLogText=Get-Content -LiteralPath $_.Log -Raw -Encoding UTF8
    [pscustomobject]@{Name=$_.Name;ExitCode=$_.Process.ExitCode;Log=$_.Log;
        ClientVisualsAndNoAuthority=($ecoLogText -match '\[Eco Integration\] NetMode=3 LogicalOwned=0 Visuals=[1-9].*Step=0');
        Fatal=($ecoLogText -match 'Fatal error:|Assertion failed:')}
})
[pscustomobject]@{Scenario=$Scenario;Packaged=[bool]$Packaged;HostSlots=11;RemoteClients=if($Scenario -eq 'Capacity'){10}else{1};
    Provider='NULL';Transport='IP loopback';SteamServiceTest=$false;Results=$ecoResults} |
    ConvertTo-Json -Depth 6 | Set-Content (Join-Path $ecoOutput 'Results.json') -Encoding utf8
Write-Output ('JWJ_MULTIPLAYER_PASS '+$ecoOutput)

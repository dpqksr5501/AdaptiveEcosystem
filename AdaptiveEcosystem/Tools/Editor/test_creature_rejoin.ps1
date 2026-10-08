param(
    [string]$EngineRoot = 'C:/Program Files/Epic Games/UE_5.8',
    [int]$ClientSeconds = 42,
    [int]$ServerSeconds = 160
)
$ErrorActionPreference = 'Stop'
$ecoProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$ecoProject = Join-Path $ecoProjectRoot 'AdaptiveEcosystem.uproject'
$ecoLogs = Join-Path $ecoProjectRoot 'Saved/Logs'
$ecoServerLog = Join-Path $ecoLogs 'CreatureRejoinServer.log'
$ecoActive = @(Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^(UnrealBuildTool|dotnet|UnrealEditor|UnrealEditor-Cmd|LiveCodingConsole|MSBuild|ShaderCompileWorker)\.exe$'
})
if ($ecoActive.Count) { throw 'Finish existing Unreal/build processes before this test.' }
if ($ClientSeconds -lt 36 -or $ServerSeconds -lt 2*$ClientSeconds+55) { throw 'Allow two complete regional cycles plus startup time.' }

function Start-EcoTest([string]$Executable, [string[]]$Arguments) {
    $ecoQuoted = @($Arguments | ForEach-Object { '"' + $_ + '"' })
    Start-Process -FilePath $Executable -ArgumentList ($ecoQuoted -join ' ') -WorkingDirectory $ecoProjectRoot -WindowStyle Hidden -PassThru
}
$ecoStartedUtc = [DateTime]::UtcNow
$ecoServer = Start-EcoTest (Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe') @(
    $ecoProject, '/Game/Map/LV_Ecosystem_IntegrationTest', '-server', '-NullRHI', '-unattended', '-nop4', '-port=7777',
    '-EcoIntegrationObserverCycle', "-EcoIntegrationExitAfter=$ServerSeconds",
    '-ExecCmds=eco.Senses.PreyLog 1,eco.Senses.NoiseLog 1,eco.Footsteps.Log 1,eco.Shelter.Log 1', "-AbsLog=$ecoServerLog"
)
$ecoDeadline = [DateTime]::UtcNow.AddSeconds(60)
while ($true) {
    if ($ecoServer.HasExited) { throw 'Server exited before initialization; inspect its first error.' }
    if ((Test-Path -LiteralPath $ecoServerLog) -and
        (Get-Item -LiteralPath $ecoServerLog).LastWriteTimeUtc -ge $ecoStartedUtc -and
        (Get-Content -LiteralPath $ecoServerLog -Raw) -match '\[Eco Integration\] NetMode=1 LogicalOwned=[1-9]') { break }
    if ([DateTime]::UtcNow -gt $ecoDeadline) { throw 'Server did not initialize; leave it to its timed exit and inspect logs.' }
    Start-Sleep -Milliseconds 500
}
$ecoResults = @()
foreach ($ecoName in @('CreatureRejoinClientA', 'CreatureRejoinClientB')) {
    if ($ecoServer.HasExited) { throw 'Server lifetime ended before the next join.' }
    $ecoClient = Start-EcoTest (Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.exe') @(
        $ecoProject, '127.0.0.1:7777', '-game', '-unattended', '-nop4', '-windowed', '-ResX=960', '-ResY=540',
        '-EcoIntegrationObserverCycle', "-EcoIntegrationExitAfter=$ClientSeconds",
        '-ExecCmds=eco.Footsteps.Log 1,eco.Creature.FacingAudit 1,sg.ViewDistanceQuality 0,sg.ShadowQuality 0,sg.GlobalIlluminationQuality 0',
        "-AbsLog=$(Join-Path $ecoLogs ($ecoName+'.log'))"
    )
    # Timed native fixture exits gracefully. No force-stop or overlapping builds.
    if (-not $ecoClient.WaitForExit(90000)) { throw "Client did not exit normally: $ecoName" }
    $ecoResults += @{ Name=$ecoName; ExitCode=$ecoClient.ExitCode }
    Write-Output "$ecoName finished with exit $($ecoClient.ExitCode)"
}
if (-not $ecoServer.WaitForExit(120000)) { throw 'Server did not reach its normal timed exit.' }
$ecoResults += @{ Name='CreatureRejoinServer'; ExitCode=$ecoServer.ExitCode }
$ecoResults | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $ecoProjectRoot 'Saved/CreatureRejoinProcessResults.json') -Encoding utf8
Write-Output 'CREATURE_REJOIN_PROCESSES_FINISHED'

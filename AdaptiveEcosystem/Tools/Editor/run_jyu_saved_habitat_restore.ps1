param(
    [int]$Seed = 20017,
    [string]$EngineRoot = 'C:/Program Files/Epic Games/UE_5.8',
    [switch]$PrepareOnly
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$project = Join-Path $root 'AdaptiveEcosystem.uproject'
$editor = Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.exe'
$dll = Join-Path $root 'Binaries/Win64/UnrealEditor-AdaptiveEcosystem.dll'
$audit = Join-Path $PSScriptRoot 'audit_jyu_island_fauna.py'
$map = '/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed'
$slot = "IslandSavedHabitat_$Seed"
$checkpoint = Join-Path $root "Saved/Ecosystem/$slot.eco"
$baseline = Join-Path $root 'Saved/FaunaAudit/IslandAccessBaseline'
$snapshot = Join-Path $baseline "${slot}_snapshot.json"
$report = Join-Path $root "Saved/FaunaAudit/${slot}_load/IslandFaunaPIE.json"
$log = Join-Path $baseline "${Seed}_transition_saved_checkpoint_load.log"

foreach ($file in @($project, $editor, $dll, $audit, $checkpoint, $snapshot)) {
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing file $file" }
}
$reader = [IO.BinaryReader]::new([IO.File]::OpenRead($checkpoint))
try {
    $magic = $reader.ReadUInt32()
    $version = $reader.ReadUInt32()
    $payloadLength = $reader.ReadUInt32()
    $null = $reader.ReadUInt32() # The Unreal loader verifies CRC.
    if ($magic -ne 0x45434f31 -or $version -notin @(14, 15, 16) -or $payloadLength -ne ($reader.BaseStream.Length - 16)) {
        throw 'Unexpected checkpoint header.'
    }
    $mapLength = $reader.ReadInt32()
    if ($mapLength -ne ($map.Length + 1)) { throw 'Unexpected checkpoint map length.' }
    $savedMap = [Text.Encoding]::ASCII.GetString($reader.ReadBytes($mapLength)).TrimEnd([char]0)
    $hashLength = $reader.ReadInt32()
    if ($hashLength -ne 33) { throw 'Unexpected checkpoint runtime hash length.' }
    $savedHash = [Text.Encoding]::ASCII.GetString($reader.ReadBytes($hashLength)).TrimEnd([char]0)
}
finally {
    $reader.Dispose()
}
if ($savedMap -cne $map) { throw "Checkpoint belongs to $savedMap" }
if ((Get-FileHash -Algorithm MD5 -LiteralPath $dll).Hash -ine $savedHash) {
    throw 'Checkpoint belongs to a different runtime DLL. Use a save from this build.'
}
Write-Output "Checkpoint and Editor DLL match for $slot."
if ($PrepareOnly) { return }

if (Get-Process UnrealEditor,UnrealEditor-Cmd,UnrealBuildTool,dotnet,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue) {
    throw 'An Unreal Editor or build process is still running.'
}
$argsList = @($project, $map, '-unattended', '-nop4',
    '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities', '-D3D12', '-RenderOffscreen', '-nosound',
    '-benchmark', '-fps=30', '-EcoV3AutoAdapt=0', "-EcoV3Seed=$Seed", '-EcoIslandAccessAudit',
    '-EcoIslandVerifySavedShelf', '-EcoIslandFeedingHistory', '-EcoIslandVerifySavedMinkShore',
    '-EcoIslandVerifyEaglePerch', '-EcoIslandVerifyHighBank', '-EcoFaunaHuntAudit', '-EcoIslandTransitionRegion',
    '-EcoIslandTransitionApproach', '-EcoIslandTransitionControl', '-EcoIslandTransitionHabitat',
    '-EcoIslandHabitatRiverWeather', '-EcoIslandHabitatRiverApproach', '-EcoIslandVerifySavedHabitat',
    '-EcoIslandCheckpoint=Load', "-abslog=$log", "-ExecCmds=py $audit")
$arguments = ($argsList | ForEach-Object { '"' + $_ + '"' }) -join ' '
$started = [DateTime]::UtcNow
$process = Start-Process -FilePath $editor -ArgumentList $arguments -WorkingDirectory $root -WindowStyle Hidden -PassThru
Write-Output "Island restore PID=$($process.Id). Log: $log"
$process.WaitForExit()
if ($process.ExitCode -ne 0) { throw "Editor exited with $($process.ExitCode). Inspect $log" }
if (!(Test-Path -LiteralPath $report) -or (Get-Item -LiteralPath $report).LastWriteTimeUtc -lt $started) {
    throw "No fresh restore report. Inspect $log"
}
$data = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
if ($data.errors -or !$data.checkpoint_environment_compared -or !$data.checkpoint_resumed_habitat_meals) {
    throw "Restore audit did not pass. Inspect $report"
}
Write-Output "Restored environment and subsequent feeding verified. Report: $report"

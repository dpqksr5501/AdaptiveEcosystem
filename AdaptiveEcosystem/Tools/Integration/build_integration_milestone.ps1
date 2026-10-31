param(
    [ValidateSet('A','B','C','D','E','F','Final')][string]$Milestone = 'Final',
    [string]$EngineRoot = 'C:\Program Files\Epic Games\UE_5.8'
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$busyNames = @('UnrealBuildTool.exe','dotnet.exe','UnrealEditor.exe','UnrealEditor-Cmd.exe',
    'LiveCodingConsole.exe','MSBuild.exe','ShaderCompileWorker.exe')
$active = Get-CimInstance Win32_Process | Where-Object { $_.Name -in $busyNames }
if ($active) {
    $active | Select-Object Name,ProcessId,CommandLine | Format-Table -AutoSize
    throw 'An engine/build process is running. No process was stopped and no new build was started.'
}
$outputDir = Join-Path $projectRoot 'Saved\IntegrationBuilds'
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$logPath = Join-Path $outputDir ("Milestone_{0}_{1}.log" -f $Milestone,(Get-Date -Format 'yyyyMMdd_HHmmss'))
# UE 5.8 initializes UBA even with -NoUBA. GoogleDriveFS can hold memgroups
# open inside the synced checkout; isolate each completed build's transient store.
$ubaRoot = Join-Path ([IO.Path]::GetTempPath()) ('AdaptiveEcosystemUBT\' + [guid]::NewGuid().ToString('N'))
$ubt = Join-Path $EngineRoot 'Engine\Binaries\DotNET\UnrealBuildTool\UnrealBuildTool.exe'
# Keep logs in the project; this disposable executor store is never source/content.
& $ubt AdaptiveEcosystemEditor Win64 Development "-Project=$projectRoot\AdaptiveEcosystem.uproject" `
    -WaitMutex -NoHotReload -NoUBA "-UBARootDir=$ubaRoot" 2>&1 | Tee-Object -FilePath $logPath
$buildExitCode = $LASTEXITCODE
Write-Output "Build log: $logPath"
if ($buildExitCode -ne 0) { throw "UBT failed with exit code $buildExitCode. Automation tests were not run." }

param([ValidateRange(80,600)][int]$Duration=90)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskOut=Join-Path $taskRoot 'Saved/EcosystemLife_20261023'
$taskArchive=Join-Path $taskRoot 'Saved/EcosystemLifePackage/Windows'
$taskExe=Join-Path $taskArchive 'AdaptiveEcosystem.exe'
if(-not(Test-Path $taskExe)){throw 'Build/cook/archive must succeed before packaged smoke'}
if(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker,AdaptiveEcosystem -ErrorAction SilentlyContinue){throw 'Engine/game/build busy; no process stopped'}
$taskLog=Join-Path $taskOut 'PackagedSmoke.log'
$taskArgs=@('/Game/JYU/Maps/LV_JYU_Ecosystem','-d3d11','-windowed','-ResX=1280','-ResY=720',
    '-unattended','-NoSound','-EcoV3Seed=23','-EcoIntegrationObserverCycle',
    "-EcoIntegrationExitAfter=$Duration",'-EcoIntegrationCaptureAt=75',"-abslog=$taskLog")
$taskStart=Get-Date
$taskQuoted=$taskArgs|ForEach-Object{'"'+$_+'"'}
$taskProcess=Start-Process $taskExe -ArgumentList ($taskQuoted -join ' ') -WindowStyle Hidden -PassThru -WorkingDirectory $taskArchive
while(-not $taskProcess.WaitForExit(5000)){}
if($taskProcess.ExitCode -ne 0){throw "Packaged process exit=$($taskProcess.ExitCode); preserve first error"}
if(-not(Test-Path $taskLog) -or (Get-Item $taskLog).LastWriteTime -lt $taskStart){throw 'Fresh packaged log missing'}
$taskText=Get-Content $taskLog -Raw
if($taskText -notmatch 'Authority ready:' -or $taskText -notmatch 'Test duration completed; Ready=1' -or
    $taskText -match 'Runtime stopped|Fatal error|Accessed None|Log\w+: Error:|Failed to find object.*(?:Rain_System|NS_Blizzard|A_Rain_Cue)'){
    throw 'Packaged authority/render smoke failed; inspect first error'
}
$taskScreens=Join-Path $taskArchive 'AdaptiveEcosystem/Saved/Screenshots'
$taskCapture=Get-ChildItem $taskScreens -Recurse -File -Filter '*.png' -ErrorAction SilentlyContinue|
    Where-Object {$_.LastWriteTime -ge $taskStart}|Select-Object -First 1
if(-not $taskCapture){throw 'Packaged rendered screenshot missing'}
Write-Output "ECOSYSTEM_PACKAGED_SMOKE_FINISHED $($taskCapture.FullName)"

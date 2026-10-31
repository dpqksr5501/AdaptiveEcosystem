param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue){throw 'Engine/build busy; no process stopped'}
$taskOut=Join-Path $taskRoot 'Saved/EcosystemLife_20261023'
$taskArchive=Join-Path $taskRoot 'Saved/EcosystemLifePackage'
New-Item -ItemType Directory -Path $taskOut -Force|Out-Null
$taskUba=Join-Path ([IO.Path]::GetTempPath()) ('AdaptiveEcosystemUBT/'+[guid]::NewGuid().ToString('N'))
& (Join-Path $EngineRoot 'Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe') AdaptiveEcosystem Win64 Development "-Project=$taskRoot/AdaptiveEcosystem.uproject" -WaitMutex -NoHotReload -NoUBA "-UBARootDir=$taskUba" 2>&1|Tee-Object (Join-Path $taskOut 'GameBuild.log')
if($LASTEXITCODE -ne 0){throw 'Direct game target UBT failed; inspect first compiler error'}
if(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue){throw 'Game UBT has not released its processes; packaging not started'}
# Compilation is already complete. UAT handles cook/stage/archive only.
& (Join-Path $EngineRoot 'Engine/Build/BatchFiles/RunUAT.bat') BuildCookRun "-project=$taskRoot/AdaptiveEcosystem.uproject" -noP4 -unattended -utf8output -nocompile -nocompileuat -nocompileeditor -skipbuild -platform=Win64 -clientconfig=Development -target=AdaptiveEcosystem -cook -map=/Game/JYU/Maps/LV_JYU_Ecosystem -stage -pak -package -archive "-archivedirectory=$taskArchive" 2>&1|Tee-Object (Join-Path $taskOut 'Package.log')
if($LASTEXITCODE -ne 0){throw 'Cook/stage failed; preserve outputs and inspect first error'}
$taskExe=Join-Path $taskArchive 'Windows/AdaptiveEcosystem.exe'
if(-not(Test-Path $taskExe)){throw 'Successful archive did not contain expected executable'}
Write-Output "ECOSYSTEM_PACKAGE_FINISHED $taskExe"

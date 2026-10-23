param([string]$OutputPath)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskBusy=Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue
if($taskBusy){throw 'Wait for all engine/build processes to finish; nothing was stopped.'}
$taskVsWhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio/Installer/vswhere.exe'
$taskVs=& $taskVsWhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if(-not $taskVs){throw 'VC toolchain not found'}
$taskVcVars=Join-Path $taskVs 'VC/Auxiliary/Build/vcvars64.bat'
$taskPolicy=Join-Path $taskRoot 'Source/AdaptiveEcosystem/AI/Policy'
$taskBin=Join-Path $taskRoot 'Saved/Vegetation_20261023/Evaluator'
New-Item -ItemType Directory -Path $taskBin -Force|Out-Null
$taskExe=Join-Path $taskBin 'EcoVegetationEval.exe'
$taskSource=Join-Path $PSScriptRoot 'EcoVegetationEval.cpp'
$taskObject=Join-Path $taskBin 'EcoVegetationEval.obj'
if(-not $OutputPath){$OutputPath=Join-Path $taskRoot 'Saved/Vegetation_20261023/EngineFree.json'}
$taskCl="cl /nologo /O2 /std:c++20 /EHsc /utf-8 /W3 /permissive- /fp:precise /DNDEBUG /I`"$taskPolicy`" /Fo`"$taskObject`" /Fe`"$taskExe`" `"$taskSource`""
cmd /c "`"$taskVcVars`" >nul && $taskCl"
if($LASTEXITCODE -ne 0){throw 'Engine-free evaluator compilation failed'}
& $taskExe | Set-Content -LiteralPath $OutputPath -Encoding utf8
if($LASTEXITCODE -ne 0){throw 'Engine-free conservation check failed'}
Write-Output "Evaluation: $OutputPath"

# EcoV3Eval 빌드 — 엔진 없는 네이티브 두뇌 평가기 (EcoV3Eval.cpp 머리 주석).
# VS 2022 를 vswhere 로 찾아 vcvars64 환경에서 cl /O2 /std:c++20 으로 컴파일한다. include 는 언리얼 모듈의 AI/Policy 헤더(엔진 무관)뿐이다.
#   powershell -ExecutionPolicy Bypass -File AdaptiveEcosystem/Tools/EcoV3Eval/build.ps1          → Tools/EcoV3Eval/bin/EcoV3Eval.exe
#   ... build.ps1 -DebugBuild                                                                   → /Od /Zi (진단용)
# 부동소수점은 /fp:precise (기본 — 묶어 곱하기·재배열 없음. 파이썬 거울 세계와 같은 IEEE 식).
param([switch]$DebugBuild)
$ErrorActionPreference = 'Stop'

$here = $PSScriptRoot
$policy = (Resolve-Path (Join-Path $here '..\..\Source\AdaptiveEcosystem\AI\Policy')).Path
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path $vswhere)) { throw "vswhere 가 없다: $vswhere" }
$req = 'Microsoft.VisualStudio.Component.VC.Tools.x86.x64'
$vs = & $vswhere -version '[17.0,18.0)' -products '*' -requires $req -property installationPath | Select-Object -First 1
if (-not $vs) { throw 'VS 2022 (VC 도구 x64) 를 찾지 못했다' }
$vcvars = Join-Path $vs 'VC\Auxiliary\Build\vcvars64.bat'
if (-not (Test-Path $vcvars)) { throw "vcvars64.bat 이 없다: $vcvars" }
$env:PATH = (Split-Path $vswhere) + ';' + $env:PATH   # vcvars64 가 vswhere 를 PATH 에서 찾는다

$bin = Join-Path $here 'bin'
New-Item -ItemType Directory -Force $bin | Out-Null
$obj = Join-Path $bin 'obj'
New-Item -ItemType Directory -Force $obj | Out-Null
$opt = if ($DebugBuild) { '/Od /Zi' } else { '/O2' }
$src = Join-Path $here 'EcoV3Eval.cpp'
$exe = Join-Path $bin 'EcoV3Eval.exe'
$cl = "cl /nologo $opt /std:c++20 /EHsc /utf-8 /W3 /permissive- /fp:precise /DNDEBUG /I`"$policy`" /I`"$here`" /Fo`"$obj\\`" /Fe`"$exe`" `"$src`""
Write-Host "[EcoV3Eval] VS: $vs"
Write-Host "[EcoV3Eval] $cl"
cmd /c "`"$vcvars`" >nul && $cl"
if ($LASTEXITCODE -ne 0) { throw "cl 실패 (종료 코드 $LASTEXITCODE)" }
Write-Host "[EcoV3Eval] 빌드 끝: $exe"

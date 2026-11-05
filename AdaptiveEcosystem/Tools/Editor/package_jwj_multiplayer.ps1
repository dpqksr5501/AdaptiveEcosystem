param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8', [bool]$LocalShaderWorkers=$true)
$ErrorActionPreference='Stop'
$ecoRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$ecoProject=Join-Path $ecoRoot 'AdaptiveEcosystem.uproject'
$ecoOutput=Join-Path $ecoRoot 'Saved/Network20261024'
$ecoArchive=Join-Path $ecoRoot 'Saved/JWJMultiplayerPackage'
New-Item -ItemType Directory -Path $ecoOutput -Force | Out-Null
function Assert-EcoIdle {
    if(Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,AdaptiveEcosystem*,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue) {
        throw 'Engine/build busy. No process was stopped.'
    }
}
Assert-EcoIdle
& (Join-Path $EngineRoot 'Engine/Binaries/DotNET/UnrealBuildTool/UnrealBuildTool.exe') AdaptiveEcosystem Win64 Development "-Project=$ecoProject" -WaitMutex -NoHotReload -NoUBA *> (Join-Path $ecoOutput 'GameBuild.log')
if($LASTEXITCODE -ne 0){throw 'Direct Game UBT failed. Inspect Saved/Network20261024/GameBuild.log.'}
Assert-EcoIdle
# UBT compilation is complete; UAT only cooks, stages and archives this user-authorized map.
# Keep build infrastructure local by default; no distributed shader compiler license is required.
$ecoCookOptions=if($LocalShaderWorkers){@('-AdditionalCookerOptions=-ini:Engine:[ConsoleVariables]:r.ShaderCompiler.AllowDistributedCompilation=0')}else{@()}
& (Join-Path $EngineRoot 'Engine/Build/BatchFiles/RunUAT.bat') BuildCookRun "-project=$ecoProject" -noP4 -unattended -utf8output -nocompile -nocompileuat -nocompileeditor -skipbuild -platform=Win64 -clientconfig=Development -target=AdaptiveEcosystem -cook -map=/Game/JWJ/Integration_JwJ -stage -pak -package -archive "-archivedirectory=$ecoArchive" @ecoCookOptions *> (Join-Path $ecoOutput 'Package.log')
if($LASTEXITCODE -ne 0){throw 'Cook/stage/archive failed. Inspect Saved/Network20261024/Package.log; outputs preserved.'}
$ecoExe=Join-Path $ecoArchive 'Windows/AdaptiveEcosystem.exe'
if(-not(Test-Path $ecoExe)){throw 'Archive executable missing.'}
$ecoConfig=Get-Content (Join-Path $ecoRoot 'Config/DefaultEngine.ini') -Raw
if($ecoConfig -match '(?m)^SteamDevAppId=(\d+)\s*$') {
    $ecoAppId=$Matches[1]
    # Development package only. Steam reads this beside the actual game executable.
    [IO.File]::WriteAllText((Join-Path $ecoArchive 'Windows/AdaptiveEcosystem/Binaries/Win64/steam_appid.txt'),$ecoAppId)
}
Write-Output ('JWJ_PACKAGE_FINISHED '+$ecoExe)

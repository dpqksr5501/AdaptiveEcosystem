[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z][A-Za-z0-9_]{0,23}$')][string]$Label,
    [ValidateSet('FocusedMinkRamp', 'Full', 'Population')][string]$Mode = 'Full',
    [ValidateRange(60,3600)][int]$PopulationSeconds = 3600,
    [int[]]$Seed = @(20000, 20017),
    [switch]$PassageAudit,
    [switch]$HuntAudit,
    [switch]$PopulationWithoutForageSoil,
    [switch]$Headless,
    [ValidateRange(1,2147483647)][int]$GroundFoodAuditAgent,
    [ValidateRange(1,2147483647)][int]$WaterFoodAuditAgent,
    [ValidateSet(0,4)][int]$FeedingRoutineMask,
    [string]$EngineRoot = 'C:/Program Files/Epic Games/UE_5.8',
    [string[]]$Scenario = @()
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$project = Join-Path $projectRoot 'AdaptiveEcosystem.uproject'
$script = Join-Path $PSScriptRoot 'audit_jyu_island_fauna.py'
$output = Join-Path $projectRoot 'Saved/FaunaAudit'
$logDir = Join-Path $output 'IslandAccessBaseline'
$editor = Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.exe'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$scenarioArgs = @()
if ($PSBoundParameters.ContainsKey('GroundFoodAuditAgent')) {
    $scenarioArgs += "-EcoGroundFoodAuditAgent=$GroundFoodAuditAgent"
}
if ($PSBoundParameters.ContainsKey('WaterFoodAuditAgent')) {
    $scenarioArgs += "-EcoIslandWaterFoodAuditAgent=$WaterFoodAuditAgent"
}
if ($PopulationWithoutForageSoil -and $Mode -ne 'Population') { throw 'Soil control requires Population mode' }
if ($PSBoundParameters.ContainsKey('FeedingRoutineMask')) {
    if ($Mode -ne 'Full') { throw 'Feeding routine comparison requires Full mode' }
    $scenarioArgs += "-EcoAdaptiveRoutineMask=$FeedingRoutineMask"
}
foreach ($option in $Scenario) {
    if ($option -notmatch '^-EcoIsland[A-Za-z0-9]+(?:=[A-Za-z0-9_,.+-]+)?$' -or
        $option -match '^-EcoIsland(?:AuditLabel|FocusMinkRamp|PopulationWithoutForageSoil|SaveHighlandApproach|SaveGrasslandPassage|HoldGrasslandPassage|SaveDriftForage|SaveDeepShelf|SaveMinkBankLayout|SaveMinkBankSurface|SaveRiverRatRefuge|SaveDeerPresentation|SaveWeatherPresentation|Save(Snow|Grassland)StageBounds|.*Author)') {
        throw "Invalid scenario option for a labeled PIE run: $option"
    }
    $scenarioArgs += $option
}
$checkpointRuns = @($Scenario | Where-Object { $_ -match '^-EcoIslandCheckpointRun(?:=|$)' })
if ($checkpointRuns.Count -and ($checkpointRuns.Count -ne 1 -or
    $checkpointRuns[0] -cnotmatch '^-EcoIslandCheckpointRun=[A-Za-z0-9_]{1,24}$' -or
    ('-EcoIslandCheckpoint=Save' -notin $Scenario -and '-EcoIslandCheckpoint=Load' -notin $Scenario))) {
    throw 'CheckpointRun needs one name and a Save or Load scenario'
}
$renderArgs = @('-D3D12', '-RenderOffscreen')
if ($Headless) { $renderArgs = @('-NullRHI', '-EcoIslandNoCapture') }
if ($PassageAudit -or $HuntAudit) {
    $scenarioArgs += '-EcoFaunaHuntAudit'
}
if ($Mode -eq 'FocusedMinkRamp') {
    $renderArgs = @('-NullRHI')
    $scenarioArgs += @('-EcoIslandSecondMinkTrial=0', '-EcoIslandSecondMinkNearStart',
        '-EcoIslandSecondMinkDeepBudget', '-EcoIslandSecondMinkFlood', '-EcoIslandSecondMinkFloodCoverBank',
        '-EcoIslandSecondMinkFloodPlatform', '-EcoIslandSecondMinkFloodRamp', '-EcoIslandFocusMinkRamp')
}
if ($Mode -eq 'Population') {
    $forageComparison = @('-EcoIslandTrialWaterForageSplit','-EcoIslandWaterForageSmallFish',
        '-EcoIslandWaterForageFromDrift','-EcoIslandWaterForageSplitPercent=15')
    $onlyForageComparison = $Scenario.Count -eq $forageComparison.Count -and
        @($forageComparison | Where-Object { $_ -notin $Scenario }).Count -eq 0
    $onlyForageComparison = $onlyForageComparison -or
        ($Scenario.Count -eq 1 -and $Scenario[0] -eq '-EcoIslandWaterForageShared')
    $driftAudit = @('-EcoIslandWaterForageShared','-EcoIslandAuditDriftStock')
    $driftRainAudit = $driftAudit + '-EcoIslandDriftRainPulse'
    $driftSeasonalAudit = $driftAudit + '-EcoIslandDriftSeasonalTrial'
    $driftVisualAudit = $driftSeasonalAudit + '-EcoIslandDriftVisualTrial'
    $driftSurfaceAudit = $driftVisualAudit + '-EcoIslandDriftSurfaceTrial'
    $driftShoreAudit = $driftSurfaceAudit + '-EcoIslandDriftShoreTrial'
    $isDriftSurfaceAudit = $Scenario.Count -eq $driftSurfaceAudit.Count -and
        @($driftSurfaceAudit | Where-Object { $_ -notin $Scenario }).Count -eq 0
    $isDriftShoreAudit = $Scenario.Count -eq $driftShoreAudit.Count -and
        @($driftShoreAudit | Where-Object { $_ -notin $Scenario }).Count -eq 0
    $isDriftVisualAudit = $Scenario.Count -eq $driftVisualAudit.Count -and
        @($driftVisualAudit | Where-Object { $_ -notin $Scenario }).Count -eq 0
    $isDriftVisualAudit = $isDriftVisualAudit -or $isDriftSurfaceAudit -or $isDriftShoreAudit
    $onlyForageComparison = $onlyForageComparison -or
        ($Scenario.Count -eq $driftAudit.Count -and @($driftAudit | Where-Object { $_ -notin $Scenario }).Count -eq 0) -or
        ($Scenario.Count -eq $driftRainAudit.Count -and @($driftRainAudit | Where-Object { $_ -notin $Scenario }).Count -eq 0) -or
        ($Scenario.Count -eq $driftSeasonalAudit.Count -and @($driftSeasonalAudit | Where-Object { $_ -notin $Scenario }).Count -eq 0) -or
        $isDriftVisualAudit
    if (($Scenario.Count -and !$onlyForageComparison) -or $PassageAudit) {
        throw 'Population accepts the saved island or the fixed small-fish forage comparison'
    }
    if ($isDriftVisualAudit) {
        if ($PopulationSeconds -lt 300) { throw 'Drift visual comparison needs at least 300 game seconds' }
    } else {
        $renderArgs = @('-NullRHI')
    }
    $scenarioArgs += "-EcoIslandPopulationSeconds=$PopulationSeconds"
    if ($PopulationWithoutForageSoil) { $scenarioArgs += '-EcoIslandPopulationWithoutForageSoil' }
}

foreach ($value in $Seed) {
    if (Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue) {
        throw 'Unreal editor or build is active'
    }
    $log = Join-Path $logDir "${value}_$Label.log"
    $report = Join-Path $output "Island_${value}_$Label/IslandFaunaPIE.json"
    $arguments = @("`"$project`"", '/Game/JYU/Maps/LV_JYU_IslandEcosystemRefreshed',
        '-unattended', '-nop4', '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities',
        '-nosound', '-benchmark', '-fps=30', '-EcoV3AutoAdapt=0', "-EcoV3Seed=$value",
        '-EcoIslandAccessAudit', '-EcoIslandVerifySavedShelf', '-EcoIslandFeedingHistory',
        '-EcoIslandVerifySavedMinkShore', '-EcoIslandVerifyEaglePerch', '-EcoIslandVerifyHighBank',
        "-EcoIslandAuditLabel=$Label", "-abslog=`"$log`"", "-ExecCmds=`"py $script`"")
    $started = [DateTime]::UtcNow
    $process = Start-Process -FilePath $editor -ArgumentList ($arguments + $renderArgs + $scenarioArgs) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0 -or !(Test-Path -LiteralPath $report) -or
        (Get-Item -LiteralPath $report).LastWriteTimeUtc -lt $started) {
        throw "Unreal did not write a fresh report for seed $value. See $log"
    }
    $data = Get-Content -Raw -Encoding utf8 -LiteralPath $report | ConvertFrom-Json
    if ($data.errors -or !$data.samples.Count -or ($Mode -eq 'FocusedMinkRamp' -and !$data.focused_mink_ramp) -or
        ($Mode -eq 'Population' -and $data.samples[-1].completed_clock.authority_seconds -lt $PopulationSeconds)) {
        throw "Audit failed for seed $value. See $report. $($data.errors -join ' ')"
    }
    if ($isDriftVisualAudit -and !$Headless) {
        foreach ($phase in @('before', 'exposed', 'recovered', 'late')) {
            $image = Join-Path (Split-Path -Parent $report) "Drift_$phase.png"
            if (!(Test-Path -LiteralPath $image) -or (Get-Item -LiteralPath $image).LastWriteTimeUtc -lt $started) {
                throw "No fresh Drift visual capture at $phase for seed $value. See $log"
            }
        }
    }
    if ('-EcoIslandCheckpointFinalBank' -in $Scenario) {
        if ('-EcoIslandShiftRatCheckpointMouth' -in $Scenario) {
            if (!$data.checkpoint_rejected_shifted_rat_mouth -or !(Select-String -LiteralPath $log -Pattern '[EcoCheckpoint] Load rejected: fauna habitat layout or clock mismatch' -SimpleMatch -Quiet)) {
                throw "Shifted rat-mouth checkpoint did not produce the expected layout rejection for seed $value. See $log"
            }
        } else {
            if (!$data.checkpoint_state.wet_patch_geometry -or !$data.checkpoint_state.stock) {
                throw "Waterbank checkpoint lacked water access geometry or stock for seed $value. See $report"
            }
            if ('-EcoIslandCheckpoint=Load' -in $Scenario) {
                $drawdown = '-EcoIslandWaterForageSharedDrawdown' -in $Scenario
                if (!$data.checkpoint_environment_compared -or
                    (!$drawdown -and !$data.resumed_hatches) -or
                    ($drawdown -and (!$data.shared_forage_drawdown.restored -or !$data.checkpoint_resumed_shared_meals))) {
                    throw "Waterbank restore lacked matching environment or its expected post-restore events for seed $value. See $report"
                }
            }
        }
    }
    if ($data.combat_carrion.mode -eq 'Rifle') {
        $targetId = [long]$data.combat_carrion.victim
        $committedDeath = Select-String -LiteralPath $log -Pattern "[EcoCombat][DeathCommitted] Id=$targetId " -SimpleMatch -Quiet
        $sharedStock = Select-String -LiteralPath $log -Pattern "[Eco Fauna][Carcass] Id=$targetId " -SimpleMatch -Quiet
        if (!$committedDeath -or !$sharedStock) {
            throw "Rifle trial lacked a committed death or shared carcass for seed $value and target $targetId. See $log"
        }
    }
    if ($data.combat_carrion.mode -eq 'RiflePresent') {
        $targetId = [long]$data.combat_carrion.victim
        if (Select-String -LiteralPath $log -Pattern "[EcoCombat][DeathCommitted] Id=$targetId " -SimpleMatch -Quiet) {
            throw "No-fire control registered a hunting death for seed $value and target $targetId. See $log"
        }
    }
    [pscustomobject]@{
        Seed = $value
        Mode = $Mode
        WallSeconds = [Math]::Round(([DateTime]::UtcNow - $started).TotalSeconds, 1)
        Samples = $data.samples.Count
        DryGroundReached = $data.focused_mink_ramp.dry_ground_reached_at_high_water
        Report = $report
        Log = $log
    }
}

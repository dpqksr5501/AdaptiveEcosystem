param(
    [ValidateSet('Crest','RainWater','RegionalWater','WaterHunt','WaterCover','WaterVegetation','RiparianHabitat','RiparianProjectJ','HerbivoreForage','ForageWeather','ForageNetwork','ForagePersistence','FoodIntent','Nest','Population','Persistence','Animation','SeasonalWaterFood','SeasonalWaterPersistence','PigThermal','PigPersistence','PigNetwork','PigThreat','PigPopulation')]
    [string]$Mode = 'Crest',
    [int]$Seed = 20000,
    [ValidateSet('AriakeCatfish','CommonCarp','UnidentifiedFish')][string]$RegionalSpecies = 'AriakeCatfish',
    [switch]$ProjectJRiparian,
    [ValidateRange(300,7200)][int]$PopulationSeconds = 3600,
    [string]$EngineRoot = 'C:/Program Files/Epic Games/UE_5.8'
)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$project = Join-Path $projectRoot 'AdaptiveEcosystem.uproject'
$map = '/Game/JYU/Maps/LV_JYU_ExpandedFauna'
$output = Join-Path $projectRoot 'Saved/ExpandedFaunaImport'
$editorDirectory = Join-Path $EngineRoot 'Engine/Binaries/Win64'
New-Item -ItemType Directory -Path $output -Force | Out-Null

function Invoke-ExpandedEditor([string]$Name, [string[]]$Extra, [switch]$Render) {
    if (Get-Process UnrealBuildTool,dotnet,UnrealEditor,UnrealEditor-Cmd,LiveCodingConsole,MSBuild,ShaderCompileWorker -ErrorAction SilentlyContinue) {
        throw 'An Unreal process is already running.'
    }
    $log = Join-Path $output "$Name.log"
    $exe = if ($Render) { 'UnrealEditor.exe' } else { 'UnrealEditor-Cmd.exe' }
    $arguments = @($project, $map, '-unattended', '-nop4', '-nosound',
        '-EnablePlugins=PythonScriptPlugin,EditorScriptingUtilities', "-abslog=$log") + $Extra
    $quoted = ($arguments | ForEach-Object { '"' + $_ + '"' }) -join ' '
    $process = Start-Process (Join-Path $editorDirectory $exe) -ArgumentList $quoted -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru
    Write-Output "$Name PID=$($process.Id)"
    while (!$process.WaitForExit(5000)) {}
    if ($process.ExitCode -ne 0) { throw "$Name exited with $($process.ExitCode)." }
    if ($Render -and !(Select-String -LiteralPath $log -Pattern 'FAUNA_MOTION_FINISHED' -Quiet)) {
        throw "Animation validation failed. Inspect $log."
    }
}

function Invoke-ExpandedRuntime([string]$Name, [int]$Seconds, [string[]]$Extra, [switch]$RealtimeNetwork) {
    $script = Join-Path $PSScriptRoot 'audit_jyu_expanded_fauna_runtime.py'
    $started = [DateTime]::UtcNow
    $clockArgs = if ($RealtimeNetwork) { @('-nosteam') } else { @('-benchmark','-fps=30','-novsync') }
    Invoke-ExpandedEditor $Name (@('-NullRHI','-EcoV3AutoAdapt=0',
        "-EcoV3Seed=$Seed","-EcoExpandedRun=$Name","-EcoExpandedDuration=$Seconds","-ExecCmds=py $script") + $clockArgs + $Extra)
    $path = Join-Path $output "${Name}_status.json"
    if (!(Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).LastWriteTimeUtc -lt $started) {
        throw "Missing fresh runtime report $path."
    }
    $report = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($report.error -or $report.frames -lt 1) { throw "$Name failed. $($report.error)" }
    Write-Output "$Name samples=$($report.frames)"
}

switch ($Mode) {
    'PigPopulation' {
        $run = "PigFollowupCurrent$Seed"
        Invoke-ExpandedRuntime $run 300 @('-EcoPigFollowup')
        $log = Join-Path $output "$run.log"
        foreach ($patch in 'FallenMast','SoilInvertebrates','HerbaceousRoots') {
            if (!(Select-String -LiteralPath $log -SimpleMatch "Patch=$patch Species=Pig" -Quiet)) {
                throw "Pig did not consume $patch."
            }
        }
        $series = Join-Path $output "$run.jsonl"
        if (!(Select-String -LiteralPath $series -SimpleMatch 'EcoSpeciesActivity.REGROUP' -Quiet)) {
            throw 'Pig caregiver following was not observed.'
        }
    }
    'PigThreat' {
        Invoke-ExpandedRuntime "PigFollowupThreat$Seed" 12 @('-EcoPigThreat')
    }
    'PigThermal' {
        foreach ($condition in 'Cool','Dry','Wet') {
            Invoke-ExpandedRuntime "PigThermal$condition$Seed" 40 @("-EcoPigThermal=$condition")
        }
    }
    'PigPersistence' {
        Invoke-ExpandedRuntime "PigFollowupSave$Seed" 80 @('-EcoPigFollowup','-EcoExpandedCheckpoint=Save')
        Invoke-ExpandedRuntime "PigFollowupLoad$Seed" 88 @('-EcoPigFollowup','-EcoExpandedCheckpoint=Load')
    }
    'PigNetwork' {
        $pie = '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.LevelEditorPlaySettings]:'
        Invoke-ExpandedRuntime "PigFollowupNetwork$Seed" 26 @('-EcoPigNetwork',
            "${pie}PlayNetMode=PIE_Client", "${pie}RunUnderOneProcess=True", "${pie}PlayNumberOfClients=1") -RealtimeNetwork
    }
    'ForagePersistence' {
        Invoke-ExpandedRuntime "HerbivoreForageSave$Seed" 80 @('-EcoExpandedForage=Natural','-EcoExpandedCheckpoint=Save')
        Invoke-ExpandedRuntime "HerbivoreForageLoad$Seed" 88 @('-EcoExpandedForage=Natural','-EcoExpandedCheckpoint=Load')
    }
    'ForageNetwork' {
        $pie = '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.LevelEditorPlaySettings]:'
        Invoke-ExpandedRuntime "HerbivoreForageNetwork$Seed" 56 @('-EcoExpandedForage=WeatherCycle','-EcoExpandedForageNetwork',
            "${pie}PlayNetMode=PIE_Client", "${pie}RunUnderOneProcess=True", "${pie}PlayNumberOfClients=1") -RealtimeNetwork
    }
    'ForageWeather' {
        $run = "HerbivoreForageWeatherCycle$Seed"
        Invoke-ExpandedRuntime $run 90 @('-EcoExpandedForage=WeatherCycle')
        $log = Join-Path $output "$run.log"
        if (Select-String -LiteralPath $log -Pattern '\[PatchMeal\] Patch=HerbForage(BankWetGrass|BankForbs|HillsideBrowse) ' -Quiet) {
            throw 'Animals fed on the weather-only comparison sites.'
        }
    }
    'HerbivoreForage' {
        Invoke-ExpandedRuntime "HerbivoreForageNatural$Seed" 140 @('-EcoExpandedForage=Natural')
        foreach ($case in 'Choice','Depleted') {
            Invoke-ExpandedRuntime "HerbivoreForage$case$Seed" 95 @("-EcoExpandedForage=$case")
        }
        $choices = foreach ($case in 'Choice','Depleted') {
            $log = Join-Path $output "HerbivoreForage$case$Seed.log"
            $meal = Select-String -LiteralPath $log -Pattern '\[PatchMeal\] Patch=(HerbForage\w+) Species=Horse Agent=(\d+) Amount=' | Select-Object -First 1
            if (!$meal) { throw "No committed plant meal in $case" }
            $meal.Matches[0].Groups
        }
        if ($choices[1].Value -ne 'HerbForageMeadowGrass' -or $choices[4].Value -ne 'HerbForageMeadowForbs' -or $choices[2].Value -ne $choices[5].Value) {
            throw 'Expected the same horse to choose grass when present and use forbs when grass is depleted.'
        }
    }
    'RiparianProjectJ' {
        $feeding = "RiparianProjectJFeeding$Seed"
        Invoke-ExpandedRuntime $feeding 145 @('-EcoExpandedRiparianProjectJ','-EcoExpandedRiparianFeeding','-EcoExpandedExpectCrest=Dynamic')
        $log = Join-Path $output "$feeding.log"
        foreach ($meal in @('Patch=RiparianHabitatBayInvertebrates Species=CommonCarp', 'Patch=RiparianHabitatStoneMargin Species=AriakeCatfish')) {
            if (!(Select-String -LiteralPath $log -SimpleMatch $meal -Quiet)) { throw "Missing committed meal $meal" }
        }
    }
    'RiparianHabitat' {
        Invoke-ExpandedRuntime "RiparianHabitat$Seed" 100 @('-EcoExpandedAuditRiparian')
        $feeding = "RiparianHabitatFeeding$Seed"
        Invoke-ExpandedRuntime $feeding 95 @('-EcoExpandedAuditRiparian','-EcoExpandedRiparianFeeding')
        $log = Join-Path $output "$feeding.log"
        foreach ($meal in @('Patch=RiparianHabitatBayInvertebrates Species=CommonCarp', 'Patch=RiparianHabitatStoneMargin Species=AriakeCatfish')) {
            if (!(Select-String -LiteralPath $log -SimpleMatch $meal -Quiet)) { throw "Missing committed meal $meal" }
        }
    }
    'WaterVegetation' {
        $name = if ($ProjectJRiparian) { 'ProjectJWaterVegetation' } else { 'WaterVegetation' }
        $mapFlags = @()
        if ($ProjectJRiparian) { $mapFlags += '-EcoExpandedRiparianProjectJ' }
        $clear = "${name}Clear$Seed"
        $vegetated = "${name}Dense$Seed"
        Invoke-ExpandedRuntime $clear 115 (@('-EcoExpandedMinkCover=Clear','-EcoFaunaHuntAudit') + $mapFlags)
        Invoke-ExpandedRuntime $vegetated 115 (@('-EcoExpandedMinkCover=Vegetation','-EcoFaunaHuntAudit') + $mapFlags)
        $a = (Get-Content -LiteralPath (Join-Path $output "${clear}_status.json") -Raw | ConvertFrom-Json).mink_entry
        $b = (Get-Content -LiteralPath (Join-Path $output "${vegetated}_status.json") -Raw | ConvertFrom-Json).mink_entry
        $log = Join-Path $output "$vegetated.log"
        if (!$a -or !$b -or $a.hunter -ne $b.hunter -or $a.prey -eq $b.prey -or
            !(Select-String -LiteralPath $log -SimpleMatch "Hunter=$($a.hunter) Target=$($a.prey) Medium=Water Event=Reject Reason=HuntWaterVegetationCover" -Quiet) -or
            !(Select-String -LiteralPath $log -SimpleMatch "Eater=$($b.hunter) Species=Mink Carcass=$($b.prey) Amount=" -Quiet)) {
            throw 'Expected vegetated water to change which prey is seen, captured, and eaten by the same mink.'
        }
    }
    'SeasonalWaterFood' {
        Invoke-ExpandedRuntime "SeasonalWaterFoodCycle$Seed" 140 @('-EcoExpandedAuditSeasonalStock')
        Invoke-ExpandedRuntime "SeasonalWaterFoodDry$Seed" 140 @('-EcoExpandedAuditSeasonalStock','-EcoExpandedStaticWater')
    }
    'SeasonalWaterPersistence' {
        Invoke-ExpandedRuntime "SeasonalWaterSave$Seed" 140 @('-EcoExpandedAuditSeasonalStock','-EcoExpandedCheckpoint=Save')
        Invoke-ExpandedRuntime "SeasonalWaterRestore$Seed" 140 @('-EcoExpandedAuditSeasonalStock','-EcoExpandedCheckpoint=Load')
        Invoke-ExpandedRuntime "SeasonalWaterFeeding$Seed" 140 @('-EcoExpandedAuditSeasonalStock','-EcoExpandedSeasonalFeeding')
        $log = Join-Path $output "SeasonalWaterFeeding$Seed.log"
        if (!(Select-String -LiteralPath $log -SimpleMatch 'Patch=ExpandedWaterSeasonalShelf Species=CommonCarp' -Quiet)) {
            throw 'The carp did not consume seasonal stock while the shelf was inundated.'
        }
    }
    'FoodIntent' {
        foreach ($case in @('Alternate','Occluded','Expired')) {
            $cover = if ($case -eq 'Occluded') { 'Screen' } else { 'Clear' }
            Invoke-ExpandedRuntime "FoodIntent$case$Seed" 95 @("-EcoExpandedMinkCover=$cover","-EcoExpandedFoodIntent=$case",'-EcoFaunaHuntAudit')
        }
        $alternate = "FoodIntentAlternate$Seed"
        $report = Get-Content -LiteralPath (Join-Path $output "${alternate}_status.json") -Raw | ConvertFrom-Json
        $log = Join-Path $output "$alternate.log"
        $hunter = $report.mink_entry.hunter
        $prey = $report.mink_entry.prey
        $captures = @(Select-String -LiteralPath $log -SimpleMatch "Hunter=$hunter Mink Prey=$prey UnidentifiedFish")
        if ($captures.Count -ne 1 -or !(Select-String -LiteralPath $log -SimpleMatch "Eater=$hunter Species=Mink Carcass=$prey Amount=" -Quiet)) {
            throw 'Expected the selected animal to be captured once and supply a committed meal.'
        }
    }
    'WaterCover' {
        $clear = "MinkClearFinal$Seed"
        $screen = "MinkScreenFinal$Seed"
        $low = "MinkLowDemand$Seed"
        Invoke-ExpandedRuntime $clear 115 @('-EcoExpandedMinkCover=Clear','-EcoFaunaHuntAudit')
        Invoke-ExpandedRuntime $screen 115 @('-EcoExpandedMinkCover=Screen','-EcoFaunaHuntAudit')
        Invoke-ExpandedRuntime $low 115 @('-EcoExpandedMinkCover=Clear','-EcoExpandedMinkLowDemand','-EcoFaunaHuntAudit')
        $visible = (Get-Content -LiteralPath (Join-Path $output "${clear}_status.json") -Raw | ConvertFrom-Json).mink_entry
        $occluded = (Get-Content -LiteralPath (Join-Path $output "${screen}_status.json") -Raw | ConvertFrom-Json).mink_entry
        $sated = (Get-Content -LiteralPath (Join-Path $output "${low}_status.json") -Raw | ConvertFrom-Json).mink_entry
        if (!$visible -or !$occluded -or $visible.hunter -ne $occluded.hunter -or $visible.prey -eq $occluded.prey -or $sated) {
            throw 'Expected the same hunter to select different prey with a screen and stay out at low demand.'
        }
        $screenLog = Join-Path $output "$screen.log"
        if (!(Select-String -LiteralPath $screenLog -SimpleMatch "Hunter=$($visible.hunter) Target=$($visible.prey) Medium=Water Event=Reject Reason=HuntOccluded" -Quiet) -or
            !(Select-String -LiteralPath $screenLog -SimpleMatch "Eater=$($occluded.hunter) Species=Mink Carcass=$($occluded.prey) Amount=" -Quiet)) {
            throw 'Expected direct occlusion evidence and a committed meal from the alternate prey.'
        }
    }
    'RegionalWater' {
        $prefix = if ($RegionalSpecies -eq 'AriakeCatfish') { 'RegionalWater' } else { "RegionalWater$RegionalSpecies" }
        $food = @{ AriakeCatfish = 'ExpandedWaterConnectedShelf'; CommonCarp = 'ExpandedWaterMacrophyteEdge'; UnidentifiedFish = 'ExpandedWaterLittoralNursery' }[$RegionalSpecies]
        $shared = @("-EcoExpandedRegionalSpecies=$RegionalSpecies",'-EcoFaunaHuntAudit')
        $open = $shared + '-EcoExpandedRegionalWater=Open'
        Invoke-ExpandedRuntime "${prefix}Open$Seed" 145 ($open + '-EcoExpandedCheckpoint=Save')
        Invoke-ExpandedRuntime "${prefix}Restore$Seed" 145 ($open + '-EcoExpandedCheckpoint=Load')
        Invoke-ExpandedRuntime "${prefix}Closed$Seed" 145 ($shared + '-EcoExpandedRegionalWater=Closed')
        Invoke-ExpandedRuntime "${prefix}Closing$Seed" 145 ($shared + '-EcoExpandedRegionalWater=Closing')
        foreach ($name in @("${prefix}Open$Seed", "${prefix}Restore$Seed", "${prefix}Closing$Seed")) {
            $log = Join-Path $output "$name.log"
            $arrived = Select-String -LiteralPath $log -Pattern "PassageArrived\] Id=(\d+) Species=$RegionalSpecies Region=FaunaWaterEast" | Select-Object -First 1
            if (!$arrived) { throw "Missing committed fish arrival in $name." }
            $fish = $arrived.Matches[0].Groups[1].Value
            $meal = Select-String -LiteralPath $log -SimpleMatch "Patch=$food Species=$RegionalSpecies Agent=$fish Amount=" | Where-Object LineNumber -gt $arrived.LineNumber | Select-Object -First 1
            if (!$meal) {
                throw "The arriving fish $fish did not eat at the destination in $name."
            }
            if ($name -eq "${prefix}Closing$Seed") {
                $released = Select-String -LiteralPath $log -SimpleMatch "Id=$fish Species=$RegionalSpecies Region=FaunaMeadow Event=WaterReservationReleased" | Select-Object -First 1
                if (!$released -or $released.LineNumber -ge $arrived.LineNumber) { throw 'Missing reservation release before retry.' }
            }
        }
    }
    'Nest' {
        $fixture = @('-EcoExpandedNestFixture=Supported','-EcoFaunaHuntAudit')
        Invoke-ExpandedRuntime "NestSave$Seed" 135 ($fixture + '-EcoExpandedCheckpoint=Save')
        Invoke-ExpandedRuntime "NestLoad$Seed" 135 ($fixture + '-EcoExpandedCheckpoint=Load')
        Invoke-ExpandedRuntime "NestNoSite$Seed" 135 @('-EcoExpandedNestFixture=NoSite','-EcoFaunaHuntAudit')
        Invoke-ExpandedRuntime "NestParentReturn$Seed" 135 @('-EcoExpandedNestFixture=Return','-EcoFaunaHuntAudit')
        foreach ($run in @("NestSave$Seed", "NestLoad$Seed")) {
            $log = Join-Path $output "$run.log"
            $hatch = Select-String -LiteralPath $log -Pattern 'NestHatch.*Child=(\d+) Species=GoldenEagle HeightZ=360\.0' | Select-Object -First 1
            if (!$hatch) { throw "No committed hatch in $run." }
            $child = $hatch.Matches[0].Groups[1].Value
            if (!(Select-String -LiteralPath $log -SimpleMatch "[ParentMeal] Species=GoldenEagle Agent=$child Amount=" -Quiet)) {
                throw "No parent-to-child energy transfer for $child in $run."
            }
        }
    }
    'RainWater' {
        Invoke-ExpandedRuntime "RainWater$Seed" 135 @('-EcoExpandedRainWater')
    }
    'Crest' {
        Invoke-ExpandedRuntime "CrestDynamic$Seed" 155 @('-EcoExpandedCrestFixture','-EcoExpandedExpectCrest=Dynamic')
        Invoke-ExpandedRuntime "CrestClosed$Seed" 155 @('-EcoExpandedCrestFixture','-EcoExpandedExpectCrest=Closed','-EcoExpandedStaticWater')
        $meal = 'Patch=ExpandedWaterConnectedShelf Species=AriakeCatfish'
        $dynamicMeal = Select-String -LiteralPath (Join-Path $output "CrestDynamic$Seed.log") -SimpleMatch $meal -Quiet
        $closedMeal = Select-String -LiteralPath (Join-Path $output "CrestClosed$Seed.log") -SimpleMatch $meal -Quiet
        if (!$dynamicMeal -or $closedMeal) {
            throw 'The control fish must feed across the crest only when the passage opens.'
        }
    }
    'Population' {
        Invoke-ExpandedRuntime "Baseline$Seed" $PopulationSeconds @('-EcoExpandedBaseline','-EcoFaunaHuntAudit')
        Invoke-ExpandedRuntime "Expanded$Seed" $PopulationSeconds @('-EcoFaunaHuntAudit')
    }
    'WaterHunt' {
        $name = "MinkWaterHunt$Seed"
        Invoke-ExpandedRuntime $name 205 @('-EcoExpandedMinkFixture','-EcoFaunaHuntAudit')
        $log = Join-Path $output "$Name.log"
        $kill = Select-String -LiteralPath $log -Pattern 'Hunter=(\d+) Mink Prey=(\d+) UnidentifiedFish' | Select-Object -First 1
        if (!$kill) { throw 'The controlled water hunter did not capture the available small fish.' }
        $hunter, $prey = $kill.Matches[0].Groups[1].Value, $kill.Matches[0].Groups[2].Value
        if (!(Select-String -LiteralPath $log -SimpleMatch "Eater=$hunter Species=Mink Carcass=$prey Amount=" -Quiet)) {
            throw 'The captured fish did not supply a committed meal to the hunter.'
        }
    }
    'Persistence' {
        Invoke-ExpandedRuntime "Save$Seed" 100 @('-EcoExpandedCheckpoint=Save')
        Invoke-ExpandedRuntime "Restore$Seed" 120 @('-EcoExpandedCheckpoint=Load')
    }
    'Animation' {
        $script = Join-Path $PSScriptRoot 'audit_jyu_fauna_motion.py'
        Invoke-ExpandedEditor 'ExpandedFaunaMotion' @('-D3D11','-RenderOffscreen','-FaunaMotionExpanded',
            '-FaunaMotionName=ExpandedFaunaMotion',"-ExecCmds=py $script") -Render
        Invoke-ExpandedEditor 'ExpandedFaunaPhysicalSlope' @('-D3D11','-RenderOffscreen','-benchmark','-fps=60',
            '-FaunaMotionExpanded','-FaunaMotionPhysicalSlope','-FaunaMotionName=ExpandedFaunaPhysicalSlope',
            "-ExecCmds=py $script") -Render
    }
}

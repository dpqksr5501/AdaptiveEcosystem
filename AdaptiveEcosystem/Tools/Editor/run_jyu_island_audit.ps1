[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z][A-Za-z0-9_]{0,23}$')][string]$Label,
    [ValidateSet('FocusedMinkRamp', 'Full', 'Population')][string]$Mode = 'Full',
    [ValidateRange(60,3600)][int]$PopulationSeconds = 3600,
    [int[]]$Seed = @(20000, 20017),
    [ValidateRange(1,3)][int]$HabitatStage,
    [switch]$PassageAudit,
    [switch]$HuntAudit,
    [ValidateSet(0,1)][int]$HeritableFlight,
    [ValidateSet(0,1)][int]$FunctionalTraits,
    [ValidateSet(0,1)][int]$CoatSelection,
    [switch]$SnowCoatSightAudit,
    [ValidateSet(0,1)][int]$HeritableMaintenance,
    [switch]$AquaticNurseryApproach,
    [switch]$FaunaBreedingOpportunity,
    [switch]$BreedingCheckpointClient,
    [switch]$WolfCheckpointRejoin,
    [switch]$AquaticPatchMealRotation,
    [switch]$LandPlantMealRotation,
    [switch]$AquaticMealAudit,
    [switch]$PredatorContinuity,
    [switch]$NativeWolfProvisioning,
    [switch]$NativeWolfBirthAfterSeparation,
    [ValidateSet(0,1)][int]$FaunaPersistence,
    [ValidateSet(0,1,2)][int]$FaunaInteractionMode,
    [switch]$CoveredRefugeForage,
    [switch]$CoveredRefugeMealRotation,
    [switch]$PopulationWithoutForageSoil,
    [switch]$Headless,
    [ValidateRange(1,2147483647)][int]$GroundFoodAuditAgent,
    [ValidateRange(1,2147483647)][int]$WaterFoodAuditAgent,
    [ValidatePattern('^[A-Za-z][A-Za-z0-9_]{0,63}$')][string]$ForageStockAuditPatch,
    [ValidateSet(0,4)][int]$FeedingRoutineMask,
    [ValidateSet('HabitatRules','LandPlantMealRotation')][string]$CheckpointMismatchRule = 'HabitatRules',
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
if ($PSBoundParameters.ContainsKey('CoatSelection')) { $scenarioArgs += "-EcoCoatSelection=$CoatSelection" }
if ($SnowCoatSightAudit) {
    if ($Mode -ne 'Population' -or !$PSBoundParameters.ContainsKey('CoatSelection')) {
        throw 'Snow coat sight audit requires Population mode and an explicit CoatSelection'
    }
    $scenarioArgs += '-EcoSnowCoatSightAudit'
}
if ($PSBoundParameters.ContainsKey('HabitatStage')) {
    if ($Mode -ne 'Population') { throw 'Habitat stage comparison requires Population mode' }
    $scenarioArgs += "-EcoFaunaHabitatStage=$HabitatStage"
}
$traitAudit = $PSBoundParameters.ContainsKey('HeritableFlight') -or $PSBoundParameters.ContainsKey('HeritableMaintenance') -or
    $PSBoundParameters.ContainsKey('FunctionalTraits') -or $PSBoundParameters.ContainsKey('CoatSelection') -or
    $PSBoundParameters.ContainsKey('FaunaPersistence') -or
    $AquaticNurseryApproach -or $FaunaBreedingOpportunity -or $AquaticPatchMealRotation -or $LandPlantMealRotation -or
    $AquaticMealAudit -or $PredatorContinuity -or $CoveredRefugeForage -or $NativeWolfProvisioning -or $NativeWolfBirthAfterSeparation
if ($traitAudit) {
    if ($Mode -ne 'Population' -and '-EcoIslandCheckpoint=Save' -notin $Scenario -and '-EcoIslandCheckpoint=Load' -notin $Scenario) {
        throw 'Trait audit requires Population mode or an island checkpoint'
    }
    $scenarioArgs += '-EcoTraitAudit'
}
if ($PSBoundParameters.ContainsKey('HeritableFlight')) {
    $scenarioArgs += "-EcoHeritableFlight=$HeritableFlight"
}
if ($PSBoundParameters.ContainsKey('FunctionalTraits')) {
    $scenarioArgs += "-EcoFunctionalTraits=$FunctionalTraits"
}
if ($PSBoundParameters.ContainsKey('HeritableMaintenance')) {
    $scenarioArgs += "-EcoHeritableMaintenance=$HeritableMaintenance"
}
if ($AquaticNurseryApproach) {
    $scenarioArgs += '-EcoAquaticNurseryApproach'
}
if ($FaunaBreedingOpportunity) {
    $scenarioArgs += '-EcoFaunaBreedingOpportunity'
}
if ($AquaticPatchMealRotation) {
    $scenarioArgs += '-EcoAquaticPatchMealRotation'
}
if ($LandPlantMealRotation) {
    $scenarioArgs += '-EcoLandPlantMealRotation'
}
if ($AquaticMealAudit) {
    $scenarioArgs += '-EcoIslandAuditAquaticMeals'
}
if ($PredatorContinuity) {
    $scenarioArgs += '-EcoPredatorContinuity'
}
if ($NativeWolfProvisioning) {
    $scenarioArgs += '-EcoNativeWolfProvisioning'
}
if ($NativeWolfBirthAfterSeparation) {
    $scenarioArgs += '-EcoNativeWolfBirthAfterSeparation'
}
if ($PSBoundParameters.ContainsKey('FaunaPersistence')) {
    $scenarioArgs += "-EcoFaunaPersistence=$FaunaPersistence"
}
if ($PSBoundParameters.ContainsKey('FaunaInteractionMode')) {
    $scenarioArgs += "-EcoFaunaInteractions=$FaunaInteractionMode"
}
if ('-EcoIslandAuditPlayerAttackWitness' -cin $Scenario -and $FaunaInteractionMode -notin @(1,2)) {
    throw 'The player attack witness audit requires record-only or applied fauna interactions'
}
if ($CoveredRefugeForage) {
    $scenarioArgs += '-EcoCoveredRefugeForage'
}
if ($CoveredRefugeMealRotation) {
    if (!$CoveredRefugeForage) { throw 'Meal rotation trial requires covered refuge forage' }
    $scenarioArgs += '-EcoCoveredRefugeMealRotation'
}
if ($PSBoundParameters.ContainsKey('GroundFoodAuditAgent')) {
    $scenarioArgs += "-EcoGroundFoodAuditAgent=$GroundFoodAuditAgent"
}
if ($PSBoundParameters.ContainsKey('WaterFoodAuditAgent')) {
    $scenarioArgs += "-EcoIslandWaterFoodAuditAgent=$WaterFoodAuditAgent"
}
if ($ForageStockAuditPatch) {
    if ($Mode -ne 'Population') { throw 'Forage stock audit requires Population mode' }
    $scenarioArgs += "-EcoIslandForageStockAuditPatch=$ForageStockAuditPatch"
}
if ($PopulationWithoutForageSoil -and $Mode -ne 'Population') { throw 'Soil control requires Population mode' }
if ($PSBoundParameters.ContainsKey('FeedingRoutineMask')) {
    if ($Mode -ne 'Full') { throw 'Feeding routine comparison requires Full mode' }
    $scenarioArgs += "-EcoAdaptiveRoutineMask=$FeedingRoutineMask"
}
$ruleAmbush = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandAuditRuleAmbush(?:=(DayClear|DayRain|NightClear|NightRain))?$' })
if ($ruleAmbush) {
    if ($Mode -ne 'Full' -or $ruleAmbush.Count -ne 1) { throw 'Choose one rule fauna ambush scene in Full mode' }
    $scenarioArgs += '-EcoRuleFaunaPlayerAmbush'
}
foreach ($option in $Scenario) {
    if ($option -notmatch '^-EcoIsland[A-Za-z0-9]+(?:=[A-Za-z0-9_,.+-]+)?$' -or
        $option -match '^-EcoIsland(?:AuditLabel|FocusMinkRamp|PopulationWithoutForageSoil|SaveHighlandApproach|SaveGrasslandPassage|HoldGrasslandPassage|SaveDriftForage|SaveDeepShelf|SaveMinkBankLayout|SaveMinkBankSurface|SaveRiverRatRefuge|SaveDeerPresentation|SaveWeatherPresentation|Save(Snow|Grassland)StageBounds|.*Author)') {
        throw "Invalid scenario option for a labeled PIE run: $option"
    }
    $scenarioArgs += $option
}
$landForageRegrowth = '-EcoIslandLandForageRegrowth' -cin $Scenario
$aquaticForageRegrowth = '-EcoIslandAquaticForageRegrowth' -cin $Scenario
$aquaticNeighborhoods = '-EcoIslandAquaticNeighborhoods' -cin $Scenario
$aquaticNeighborhoodSupply = '-EcoIslandAquaticNeighborhoodSupply' -cin $Scenario
$carpCapacity = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandOpenCarpCapacityAt=[1-9]\d*$' })
$smallFishCapacity = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandOpenSmallFishCapacityAt=[1-9]\d*(?:,[24])?$' })
$smallFishCapacityIncrease = if ($smallFishCapacity -cmatch ',4$') { 4 } else { 2 }
$smallFishEncounter = '-EcoIslandSmallFishEncounter' -cin $Scenario
$smallFishMealAccess = '-EcoIslandSmallFishMealAccess' -cin $Scenario
$smallFishMealFork = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandSmallFishMealFork=(Save|Load),[A-Za-z0-9_]{1,20}$' })
$mealForkLoad = $smallFishMealFork -cmatch '=Load,'
$mealTransfer = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandSmallFishMealTransfer=0\.\d+$' })
if ($mealTransfer.Count -gt 1 -or ($mealTransfer.Count -and !$mealForkLoad)) {
    throw 'The Drift regrowth transfer requires a restored post-hatch checkpoint'
}
if ($smallFishMealFork.Count -gt 1 -or ($smallFishMealFork.Count -and (!$smallFishEncounter -or $Seed.Count -ne 1 -or
    $smallFishMealAccess -eq [bool]$mealForkLoad -or $ForageStockAuditPatch -cne 'IslandRiverDrift'))) {
    throw 'The post-hatch fork requires the same encounter trial and audits Drift with access added only in Save'
}
if ($smallFishMealAccess -and (!$smallFishEncounter -or $ForageStockAuditPatch -cne 'IslandRiverDrift' -or $PopulationSeconds -lt 840)) {
    throw 'The post-hatch feeding comparison requires the matched encounter layout and the Drift stock audit'
}
if ($smallFishEncounter -and (!$FaunaBreedingOpportunity -or '-EcoIslandOpenSmallFishCapacityAt=630,4' -cnotin $Scenario)) {
    throw 'The small-fish encounter comparison requires the four-place aquatic capacity trial with the same breeding rule'
}
$breedingCheckpoint = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandBreedingCheckpoint=(Save|Load),[A-Za-z0-9_]{1,20}$' })
$breedingLoad = $breedingCheckpoint -cmatch '=Load,'
$wolfCheckpointArg = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandWolfCheckpoint=(Save|Load|Reject),[A-Za-z0-9_]{1,20}$' })
$wolfCheckpointLoad = $wolfCheckpointArg -cmatch '=Load,'
$wolfCheckpointReject = $wolfCheckpointArg -cmatch '=Reject,'
$wolfCheckpointRejectBirth = '-EcoIslandWolfCheckpointRejectBirthRule' -cin $Scenario
$wolfCheckpointPreyMix = '-EcoIslandWolfPreyMix' -cin $Scenario
$wolfDescendantRestore = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandWolfDescendantRestore=[A-Za-z0-9_]{1,20},[A-Za-z0-9_]{1,24}$' })
if ($WolfCheckpointRejoin -and !$wolfCheckpointLoad) { throw 'WolfCheckpointRejoin requires a wolf checkpoint Load' }
if ($wolfCheckpointRejectBirth -and (!$wolfCheckpointReject -or $NativeWolfBirthAfterSeparation)) {
    throw 'WolfCheckpointRejectBirthRule requires a Reject run with the birth rule disabled'
}
if ($wolfCheckpointArg.Count -gt 1 -or ($wolfCheckpointArg.Count -and ($Mode -ne 'Population' -or $Seed.Count -ne 1 -or
    $PopulationSeconds -lt 90 -or [bool]$NativeWolfProvisioning -ne (!$wolfCheckpointReject -or $wolfCheckpointRejectBirth) -or
    @($Scenario | Where-Object { $_ -cin @('-EcoIslandWolfKin=Shared', '-EcoIslandWolfCarrionSurvey', '-EcoIslandNativeForageApproach') }).Count -ne 3 -or
    $Scenario.Count -ne (4 + [int]$wolfCheckpointRejectBirth + [int]$wolfCheckpointPreyMix)))) {
    throw 'The wolf checkpoint requires the 90-second shared wolf survey with only the rule under rejection disabled'
}
if ($BreedingCheckpointClient -and !$breedingLoad) { throw 'BreedingCheckpointClient requires the restored hatch trial' }
if ($breedingCheckpoint.Count -gt 1 -or ($breedingCheckpoint.Count -and (!$FaunaBreedingOpportunity -or
    !$aquaticNeighborhoodSupply -or '-EcoIslandOpenSmallFishCapacityAt=630,4' -cnotin $Scenario -or
    $PopulationSeconds -lt 840 -or $Seed.Count -ne 1))) {
    throw 'The breeding checkpoint requires one seed and the matched four-place trial through 840 seconds'
}
if ($aquaticForageRegrowth -and ($Mode -ne 'Population' -or
    $Scenario.Count -ne (1 + $carpCapacity.Count + $smallFishCapacity.Count + $breedingCheckpoint.Count + [int]$smallFishEncounter +
        [int]$smallFishMealAccess + $smallFishMealFork.Count + $mealTransfer.Count + [int]$aquaticNeighborhoods + [int]$aquaticNeighborhoodSupply) -or !$AquaticMealAudit)) {
    throw 'Aquatic forage regrowth requires Population mode and aquatic meal receipts with optional carp capacity or local habitat changes'
}
if ($carpCapacity.Count -gt 1 -or (($carpCapacity.Count -or $aquaticNeighborhoods) -and !$aquaticForageRegrowth)) {
    throw 'A carp capacity or local aquatic habitat change requires its matching regrowth trial'
}
if ($aquaticNeighborhoodSupply -and !($aquaticNeighborhoods -and $aquaticForageRegrowth)) {
    throw 'Local aquatic supply requires the matched neighborhood and regrowth layout'
}
if ($smallFishCapacity.Count -gt 1 -or ($smallFishCapacity.Count -and !$aquaticNeighborhoodSupply)) {
    throw 'The small-fish capacity change requires the local supply comparison'
}
$landForageAccess = ('-EcoIslandLandForageAccess' -cin $Scenario -or
    '-EcoIslandLandForageAccess=Dispersed' -cin $Scenario)
$landWetMeadowGuild = '-EcoIslandWestMeadowWetGuild' -cin $Scenario
if ($landWetMeadowGuild -and (!$landForageRegrowth -or !$landForageAccess)) {
    throw 'The wet meadow guild comparison requires the matched land regrowth and access scenario'
}
if ($landForageAccess -and !$landForageRegrowth) { throw 'Land forage access requires the matched regrowth scenario' }
if ($landForageRegrowth -and ($Mode -ne 'Population' -or $Scenario.Count -ne (1 + [int]$landForageAccess + [int]$landWetMeadowGuild) -or
    $HabitatStage -ne 2 -or !$HuntAudit)) {
    throw 'Land forage regrowth and access need an isolated Population scenario with HabitatStage 2 and HuntAudit'
}
$checkpointRuns = @($Scenario | Where-Object { $_ -match '^-EcoIslandCheckpointRun(?:=|$)' })
if ($checkpointRuns.Count -and ($checkpointRuns.Count -ne 1 -or
    $checkpointRuns[0] -cnotmatch '^-EcoIslandCheckpointRun=[A-Za-z0-9_]{1,24}$' -or
    ('-EcoIslandCheckpoint=Save' -notin $Scenario -and '-EcoIslandCheckpoint=Load' -notin $Scenario))) {
    throw 'CheckpointRun needs one name and a Save or Load scenario'
}
if ('-EcoIslandTraitCheckpointMismatch' -in $Scenario -and
    ('-EcoIslandCheckpoint=Load' -notin $Scenario -or !$traitAudit)) {
    throw 'A trait mismatch test needs a checkpoint load and an explicit alternate trait rule'
}
if ($PSBoundParameters.ContainsKey('CheckpointMismatchRule') -and '-EcoIslandTraitCheckpointMismatch' -notin $Scenario) {
    throw 'CheckpointMismatchRule requires the trait checkpoint mismatch scenario'
}
if ('-EcoIslandTraitCheckpointResume' -in $Scenario -and
    ('-EcoIslandCheckpoint=Load' -notin $Scenario -or !$traitAudit)) {
    throw 'Trait checkpoint resumption needs a checkpoint load with trait diagnostics'
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
    $traitHunt = $traitAudit -and $Scenario.Count -ge 2 -and
        '-EcoIslandSavedPlayerCombat' -in $Scenario -and
        @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandCombatCarrion=Rifle(?:Present)?$' }).Count -eq 1 -and
        @($Scenario | Where-Object { $_ -cnotmatch '^-EcoIsland(?:SavedPlayerCombat|CombatCarrion=Rifle(?:Present)?|CombatVictim=[1-9]\d*|CombatStart=\d+|CombatRepeat=\d+,[1-9]\d*|CombatClearApproach|CombatIsolateTarget|AuditHuntCarrion|AuditPlayerAttackWitness|CombatSelection=(?:Largest|Blind|VisibleLargest|VisibleSmallest)|CombatSelectionLayout=[1-9]\d*|RecoveryAfterHunt=\d+|RecoveryPairFixture)$' }).Count -eq 0
    $wolfLineage = $traitAudit -and $Scenario.Count -eq 1 -and $Scenario[0] -ceq '-EcoIslandTraitWolfLineage'
    if ($wolfLineage) {
        $scenarioArgs += @('-EcoIntegratedV3', '-EcoV3DeerPerRegion=28', '-EcoV3Wolves=2', '-EcoFaunaBirthAudit')
    }
    $minkRootsTrials = @('-EcoIslandMinkRootsWatch', '-EcoIslandMinkRootsNursery', '-EcoIslandMinkRootsShelf', '-EcoIslandMinkRootsSeasonalShelf')
    $territoryHunt = $Scenario.Count -eq 3 -and @($Scenario | Where-Object { $_ -cin $minkRootsTrials }).Count -eq 1
    $predatorTerritories = $traitAudit -and ($Scenario.Count -eq 2 -or $territoryHunt) -and
        '-EcoIslandWolfTerritory' -cin $Scenario -and '-EcoIslandPredatorBreedingAtRoots' -cin $Scenario
    $wolfFoodSurvey = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandWolfFoodSurvey=([1-9]\d*)$' })
    $wolfDescendantSave = @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandWolfDescendantSave=[A-Za-z0-9_]{1,20}$' })
    $wolfDescendantOptions = $wolfDescendantSave.Count + $wolfDescendantRestore.Count
    $wolfFoodAndCarrionSurvey = $wolfDescendantOptions -le 1 -and $Scenario.Count -eq (5 + $wolfDescendantOptions) -and $wolfFoodSurvey.Count -eq 1 -and
        '-EcoIslandWolfPreyMix' -cin $Scenario -and '-EcoIslandNativeForageApproach' -cin $Scenario
    $wolfFoodApproach = $Scenario.Count -eq 3 -and '-EcoIslandNativeForageApproach' -cin $Scenario
    $wolfPreyMix = $Scenario.Count -eq 4 -and '-EcoIslandWolfPreyMix' -cin $Scenario -and '-EcoIslandNativeForageApproach' -cin $Scenario
    $wolfObserver = $Scenario.Count -eq 5 -and '-EcoIslandWolfPreyMix' -cin $Scenario -and
        '-EcoIslandNativeForageApproach' -cin $Scenario -and
        @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandWolfObserver=(?:Hold|Leave),\d+,[1-9]\d*$' }).Count -eq 1
    $wolfBirthFork = $Scenario.Count -eq 5 -and '-EcoIslandWolfPreyMix' -cin $Scenario -and
        '-EcoIslandNativeForageApproach' -cin $Scenario -and
        @($Scenario | Where-Object { $_ -cmatch '^-EcoIslandWolfBirthFork=(?:Save|Hold|Leave),[A-Za-z0-9_]{1,20},(?:Founder|Descendant)$' }).Count -eq 1
    $wolfCarrionSurvey = $traitAudit -and '-EcoIslandWolfKin=Shared' -cin $Scenario -and '-EcoIslandWolfCarrionSurvey' -cin $Scenario -and
        ($Scenario.Count -eq 2 -or $wolfFoodApproach -or $wolfPreyMix -or $wolfFoodAndCarrionSurvey -or $wolfObserver -or $wolfBirthFork -or $wolfCheckpointArg.Count -eq 1)
    $wolfTerritory = $predatorTerritories -or $wolfCarrionSurvey -or
        ($traitAudit -and ($Scenario.Count -eq 2 -or $wolfFoodApproach) -and $wolfFoodSurvey.Count -eq 1 -and '-EcoIslandWolfKin=Shared' -cin $Scenario) -or
        ($traitAudit -and $Scenario.Count -eq 1 -and $Scenario[0] -cmatch '^-EcoIsland(?:WolfTerritory|WolfKin=(?:Separated|Shared))$')
    if ($wolfTerritory) {
        $scenarioArgs += '-EcoFaunaBirthAudit'
    }
    if ($wolfTerritory -and $wolfFoodSurvey.Count) {
        $scenarioArgs += ($wolfFoodSurvey[0] -creplace '^-EcoIslandWolfFoodSurvey=', '-EcoIslandNativeFoodProbe=')
    }
    $localNurseries = $traitAudit -and $Scenario.Count -eq 1 -and $Scenario[0] -ceq '-EcoIslandLocalNurseries'
    $traitClimate = $traitAudit -and $Scenario.Count -eq 1 -and $Scenario[0] -cmatch '^-EcoIslandTraitClimate=(Dry|Rain)$'
    $predatorHabitat = $traitAudit -and $Scenario.Count -eq 1 -and
        $Scenario[0] -cin @('-EcoIslandPredatorBreedingHabitat', '-EcoIslandPredatorBreedingSites', '-EcoIslandPredatorBreedingAtRoots')
    $buffaloGuardTrial = $traitAudit -and $HuntAudit -and $Scenario.Count -eq 1 -and $Scenario[0] -cmatch '^-EcoIslandBuffaloGuardTrial(?:=Calf)?$'
    $eagleFamilies = $traitAudit -and $Scenario.Count -eq 1 -and
        $Scenario[0] -cmatch '^-EcoIslandEagleFamilies=(Landscape|PreyRoute|Provisioned)$'
    $minkNearPrey = $traitAudit -and $Scenario.Count -eq 1 -and
        $Scenario[0] -cin @('-EcoIslandMinkNearPrey', '-EcoIslandMinkNearSurfacePrey', '-EcoIslandMinkBankWatch', '-EcoIslandMinkRootsWatch')
    $refugeOptions = @('-EcoIslandCoveredRefugeFood', '-EcoIslandCoveredRefugeEnergyBudget',
        '-EcoIslandCoveredRefugeCaregiver', '-EcoIslandAuditRefugeMeals')
    $refugeFood = $traitAudit -and '-EcoIslandCoveredRefugeFood' -cin $Scenario -and
        @($Scenario | Where-Object { $_ -cnotin $refugeOptions }).Count -eq 0
    $acceptedPopulationScenario = $onlyForageComparison -or $traitHunt -or $wolfLineage -or $wolfTerritory -or
        $localNurseries -or $traitClimate -or $predatorHabitat -or $buffaloGuardTrial -or $eagleFamilies -or $minkNearPrey -or $refugeFood -or $landForageRegrowth -or $aquaticForageRegrowth
    if (($Scenario.Count -and !$acceptedPopulationScenario) -or $PassageAudit) {
        throw 'Population accepts the saved island and the fixed forage, trait hunt, wolf lineage or territory, nursery, predator habitat, mink prey, covered refuge food, or land forage regrowth fixtures'
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
    if ($BreedingCheckpointClient -or $wolfCheckpointLoad -or $wolfDescendantRestore.Count) {
        $pie = '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.LevelEditorPlaySettings]:'
        $arguments = @($arguments | Where-Object { $_ -cnotin @('-benchmark', '-fps=30') })
        if ($BreedingCheckpointClient) { $arguments += '-EcoIslandBreedingCheckpointClient' }
        $clientCount = if ($WolfCheckpointRejoin) { 2 } else { 1 }
        $arguments += @('-nosteam', "${pie}PlayNetMode=PIE_Client",
                        "${pie}RunUnderOneProcess=True", "${pie}PlayNumberOfClients=$clientCount")
        if ($WolfCheckpointRejoin) { $arguments += @("${pie}ServerPort=17837", '-EcoIslandWolfRejoinPort=17837') }
    }
    $started = [DateTime]::UtcNow
    $process = Start-Process -FilePath $editor -ArgumentList ($arguments + $renderArgs + $scenarioArgs) -WindowStyle Hidden -Wait -PassThru
    if ($process.ExitCode -ne 0 -or !(Test-Path -LiteralPath $report) -or
        (Get-Item -LiteralPath $report).LastWriteTimeUtc -lt $started) {
        throw "Unreal did not write a fresh report for seed $value. See $log"
    }
    $data = Get-Content -Raw -Encoding utf8 -LiteralPath $report | ConvertFrom-Json
    if ($Mode -eq 'Population' -and $PSBoundParameters.ContainsKey('FunctionalTraits') -and
        (!$data.trait_evidence.cohorts.Count -or
         @($data.trait_evidence.cohorts | Where-Object { $null -eq $_.functional_traits -or [int]$_.functional_traits -ne $FunctionalTraits }).Count)) {
        throw "Authority functional trait setting did not match $FunctionalTraits for seed $value. See $report"
    }
    if ($data.errors -or !$data.samples.Count -or ($Mode -eq 'FocusedMinkRamp' -and !$data.focused_mink_ramp) -or
        ($Mode -eq 'Population' -and !$wolfCheckpointReject -and !$WolfCheckpointRejoin -and !$wolfBirthFork -and !$wolfDescendantRestore.Count -and
        $data.samples[-1].completed_clock.authority_seconds -lt $PopulationSeconds)) {
        throw "Audit failed for seed $value. See $report. $($data.errors -join ' ')"
    }
    if ($wolfCarrionSurvey -and !$wolfCheckpointArg.Count -and !$wolfBirthFork -and !$wolfDescendantRestore.Count -and (!$data.wolf_carrion_survey.Count -or !$data.wolf_carrion_survey[0].wolves.Count)) {
        throw "The survey did not capture the starting Native wolves for seed $value. See $report"
    }
    if ($wolfCarrionSurvey -and !$wolfCheckpointArg.Count -and !$wolfBirthFork -and !$wolfDescendantRestore.Count -and [bool]$data.wolf_carrion_survey[0].provisioning_enabled -ne [bool]$NativeWolfProvisioning) {
        throw "The Native wolf provisioning flag does not match the survey request for seed $value. See $report"
    }
    if ($wolfCarrionSurvey -and !$wolfCheckpointArg.Count -and !$wolfBirthFork -and !$wolfDescendantRestore.Count -and [bool]$data.wolf_birth_after_separation -ne [bool]$NativeWolfBirthAfterSeparation) {
        throw "The Native wolf birth flag does not match the survey request for seed $value. See $report"
    }
    if ($wolfBirthFork -and (!$data.wolf_birth_fork.reservation -or !$data.wolf_birth_fork.snapshot.birth_after_separation -or
        !$data.wolf_birth_fork.snapshot.provisioning -or !$data.wolf_birth_fork.end)) {
        throw "The Native wolf birth fork did not capture its authority start and end. See $report"
    }
    if ($WolfCheckpointRejoin -and (!$data.wolf_rejoin.returned_at -or !$data.wolf_rejoin.after.Count)) {
        throw "The two-client Native wolf run missed its rejoin evidence. See $report"
    }
    if ($wolfDescendantRestore.Count -and (!$data.wolf_descendant_restore.snapshot -or !$data.wolf_descendant_restore.client_visual)) {
        throw "The connected client did not observe the restored Native wolf descendant. See $report"
    }
    if ($isDriftVisualAudit -and !$Headless) {
        foreach ($phase in @('before', 'exposed', 'recovered', 'late')) {
            $image = Join-Path (Split-Path -Parent $report) "Drift_$phase.png"
            if (!(Test-Path -LiteralPath $image) -or (Get-Item -LiteralPath $image).LastWriteTimeUtc -lt $started) {
                throw "No fresh Drift visual capture at $phase for seed $value. See $log"
            }
        }
    }
    if ($ruleAmbush) {
        $leopard = $data.rule_ambush.leopard
        if (!$leopard) { throw "No eligible leopard was staged. See $report" }
        $hit = Select-String -LiteralPath $log -Pattern "[EcoCombat][FaunaPlayerHit] Id=$leopard " -SimpleMatch -Quiet
        if ('-EcoIslandAuditRuleAmbush=DayClear' -cin $ruleAmbush) {
            $intent = Select-String -LiteralPath $log -Pattern "[EcoCombat][FaunaStalk] Id=$leopard ","[EcoCombat][FaunaWindup] Id=$leopard " -SimpleMatch -Quiet
            if ($hit -or $intent) { throw "The staged leopard engaged a player in clear daylight. See $log" }
        } elseif (!$hit) {
            throw "The staged leopard did not commit the player hit. See $log"
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
    if ('-EcoIslandTraitCheckpointMismatch' -in $Scenario) {
        $rejection = if ($CheckpointMismatchRule -eq 'LandPlantMealRotation') {
            'runtime image or fauna rule mismatch'
        } else {
            'fauna habitat layout or clock mismatch'
        }
        if (!$data.checkpoint_rejected_trait_mismatch -or
            !(Select-String -LiteralPath $log -Pattern "[EcoCheckpoint] Load rejected: $rejection" -SimpleMatch -Quiet)) {
            throw "Trait checkpoint did not reject the changed fauna rule for seed $value. See $log"
        }
    }
    foreach ($episode in @($data.combat_carrion, $data.combat_repeat) | Where-Object { $_.mode -eq 'Rifle' }) {
        $targetId = [long]$episode.victim
        $committedDeath = Select-String -LiteralPath $log -Pattern "[EcoCombat][DeathCommitted] Id=$targetId " -SimpleMatch -Quiet
        $sharedStock = Select-String -LiteralPath $log -Pattern "[Eco Fauna][Carcass] Id=$targetId " -SimpleMatch -Quiet
        if (!$committedDeath -or !$sharedStock) {
            throw "Rifle trial lacked a committed death or shared carcass for seed $value and target $targetId. See $log"
        }
    }
    if ($Scenario -match '^-EcoIslandCombatRepeat=' -and
        (!$data.combat_repeat -or $data.combat_repeat.last_live_target_region -ne $data.combat_carrion.last_live_target_region)) {
        throw "Repeat rifle trial failed to register both hunts in the same region for seed $value. See $report"
    }
    if ('-EcoIslandRecoveryPairFixture' -cin $Scenario -and
        !(Select-String -LiteralPath $log -Pattern '[EcoLife][RecoveryRejected] Region=Grassland Species=Pig Reason=NotEmpty' -SimpleMatch -Quiet)) {
        throw "The occupied-region release was not rejected for seed $value. See $log"
    }
    if ($data.combat_selection.policy -in @('VisibleLargest', 'VisibleSmallest') -and
        (!$data.combat_selection.first_shot_visual.mesh -or
         $data.combat_selection.first_shot_visual.target -ne $data.combat_selection.target)) {
        throw "Visual selection lacked the target's live skeletal representation for seed $value. See $report"
    }
    if ('-EcoIslandAuditHuntCarrion' -in $Scenario -and
        @($data.hunt_carrion_observations | Where-Object target_confirmed_dead).Count -lt 20) {
        throw "Hunt carrion audit lacked at least twenty post-death samples for seed $value. See $report"
    }
    if ('-EcoIslandAuditHuntCarrion' -in $Scenario -and $data.combat_repeat -and
        @($data.combat_repeat.hunt_carrion_observations | Where-Object target_confirmed_dead).Count -lt 20) {
        throw "Repeat hunt carrion audit lacked at least twenty post-death samples for seed $value. See $report"
    }
    if ($data.combat_carrion.mode -eq 'RiflePresent') {
        $targetId = [long]$data.combat_carrion.victim
        if (Select-String -LiteralPath $log -Pattern "[EcoCombat][DeathCommitted] Id=$targetId " -SimpleMatch -Quiet) {
            throw "No-fire control registered a hunting death for seed $value and target $targetId. See $log"
        }
    }
    if ('-EcoIslandAuditPlayerAttackWitness' -cin $Scenario) {
        $witnesses = @($data.combat_carrion.player_attack_witnesses.PSObject.Properties)
        if (!$witnesses.Count) { throw "No authority witnesses were recorded for seed $value. See $report" }
        if ($FaunaInteractionMode -eq 1 -and @($witnesses.Value.reasons | Where-Object reason -eq 'PlayerAttackWitnessEscape').Count) {
            throw "Record-only mode applied an escape in seed $value. See $report"
        }
    }
    if ($PSBoundParameters.ContainsKey('HabitatStage') -and $data.initial_patch_inputs.active_stage -ne $HabitatStage) {
        throw "Authority habitat stage differed from the requested stage for seed $value. See $report"
    }
    if ($ForageStockAuditPatch -and ($data.forage_stock_audit_patch -cne $ForageStockAuditPatch -or
        !$data.initial_patch_inputs.patches.PSObject.Properties[$ForageStockAuditPatch])) {
        throw "Authority did not audit the requested forage stock for seed $value. See $report"
    }
    if ($LandPlantMealRotation -and $Mode -eq 'Population' -and
        (!$data.trait_evidence.cohorts.Count -or @($data.trait_evidence.cohorts | Where-Object { !$_.land_plant_meal_rotation }).Count)) {
        throw "Authority land plant meal rotation was disabled in seed $value. See $report"
    }
    if ($breedingCheckpoint.Count -and (!$data.breeding_checkpoint.snapshot.breeding_rule -or !$data.breeding_checkpoint.hatch)) {
        throw "Authority did not complete the breeding checkpoint and witnessed hatch. See $report"
    }
    if ($BreedingCheckpointClient -and !$data.breeding_checkpoint.client_visual) {
        throw "The restored hatch was not verified on a connected client. See $report"
    }
    if ($FaunaBreedingOpportunity -and !$breedingLoad -and !$mealForkLoad -and !$wolfCheckpointArg.Count -and !$wolfBirthFork -and !$wolfDescendantRestore.Count -and $Mode -eq 'Population' -and
        (!$data.trait_evidence.cohorts.Count -or @($data.trait_evidence.cohorts | Where-Object { !$_.fauna_breeding_opportunity }).Count)) {
        throw "Authority fauna breeding opportunity was disabled in seed $value. See $report"
    }
    if ($aquaticNeighborhoodSupply) {
        $supplyChanges = @($data.aquatic_neighborhood_supply.PSObject.Properties)
        if ($supplyChanges.Count -ne 4) { throw "Expected four local aquatic supply changes. See $report" }
        foreach ($change in $supplyChanges) {
            $rate = $data.initial_patch_inputs.patches.PSObject.Properties[$change.Name].Value.regrowth_per_second
            if ($null -eq $rate -or [Math]::Abs($rate - $change.Value.to) -gt .00001) {
                throw "Authority local aquatic supply mismatch for $($change.Name) in seed $value. See $report"
            }
        }
    }
    if ($landForageRegrowth -or $aquaticForageRegrowth) {
        $changes = if ($landForageRegrowth) { @($data.land_forage_regrowth.PSObject.Properties) } else {
            @($data.aquatic_forage_regrowth.PSObject.Properties)
        }
        $expectedPatches = if ($landForageRegrowth) { 7 } else { 5 }
        if ($changes.Count -ne $expectedPatches) { throw "Expected $expectedPatches staged food patches for seed $value. See $report" }
        foreach ($change in $changes) {
            $rate = $data.initial_patch_inputs.patches.PSObject.Properties[$change.Name].Value.regrowth_per_second
            if ($aquaticNeighborhoodSupply -and $data.aquatic_neighborhood_supply.PSObject.Properties[$change.Name]) {
                $rate = $data.aquatic_neighborhood_supply.PSObject.Properties[$change.Name].Value.from
            }
            if ($null -eq $rate -or [Math]::Abs($rate - $change.Value.to) -gt 0.00001 -or
                [Math]::Abs($rate - 3 * $change.Value.from) -gt 0.00001) {
                throw "Authority food regrowth mismatch for $($change.Name) in seed $value. See $report"
            }
        }
    }
    if ($carpCapacity.Count -and (!$data.carp_capacity_change -or
        $data.carp_capacity_change.to -ne (2 + $data.carp_capacity_change.from))) {
        throw "Authority did not apply the carp-specific capacity treatment. See $report"
    }
    if ($smallFishCapacity.Count -and !$breedingLoad -and !$mealForkLoad -and (!$data.small_fish_capacity_change -or
        $data.small_fish_capacity_change.from -ne $data.small_fish_capacity_change.residents -or
        $data.small_fish_capacity_change.to -ne ($smallFishCapacityIncrease + $data.small_fish_capacity_change.from))) {
        throw "Authority did not apply the small-fish capacity treatment to an occupied habitat. See $report"
    }
    if ($smallFishEncounter -and !$mealForkLoad -and (!$data.small_fish_encounter.wet_approach_samples.Count -or
        @($data.small_fish_encounter.wet_approach_samples | Where-Object { !$_.wet }).Count)) {
        throw "Authority did not verify a wet approach to the saved nursery. See $report"
    }
    if (($smallFishMealAccess -or $mealTransfer.Count) -and (!$data.small_fish_meal_access -or $data.small_fish_meal_access.points_cm.Count -ne 4 -or
        $data.small_fish_meal_access.stock_before -ne $data.small_fish_meal_access.stock_after)) {
        throw "Post-hatch Drift access did not preserve the existing stock. See $report"
    }
    if ($mealTransfer.Count -and !$data.small_fish_meal_access.regrowth_transfer) {
        throw "The restored authority did not transfer regrowth. See $report"
    }
    if ($smallFishMealFork.Count -and (!$data.small_fish_meal_fork.snapshot -or !$data.small_fish_meal_fork.end)) {
        throw "Authority did not complete its portion of the matched post-hatch comparison. See $report"
    }
    if ($aquaticNeighborhoods) {
        $sites = $data.initial_patch_inputs.patches
        $local = $data.aquatic_neighborhoods
        $catfish = $sites.PSObject.Properties[$local.catfish.patch].Value
        $nursery = $sites.PSObject.Properties[$local.small_fish.patch].Value
        $source = $sites.PSObject.Properties[$local.small_fish.source].Value
        if (!$catfish.submerged -or !$nursery.aquatic_nursery -or
            $nursery.capacity -ne $local.small_fish.capacity -or ($source.capacity + $nursery.capacity) -ne 11.0) {
            throw "Authority did not apply the two aquatic neighborhoods and the shared starting capacity. See $report"
        }
    }
    if ($landForageAccess) {
        $changes = @($data.land_forage_access.PSObject.Properties)
        if ($changes.Count -ne 2) { throw "Expected two shared land food sites for seed $value. See $report" }
        foreach ($change in $changes) {
            if (@($change.Value.authority_points_cm).Count -ne 2) {
                throw "Authority ground check omitted an access point at $($change.Name). See $report"
            }
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
